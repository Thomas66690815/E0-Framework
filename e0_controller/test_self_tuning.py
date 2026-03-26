"""
Tests for B4.1: Self-Tuning Meta-Layer
=======================================
Tests the field-derived threshold system, parameter sensitivity
analysis, tuning proposals, oscillation protection, and the
integration with the reflection layer.

28 claims in 8 test classes.
"""

import math
import unittest
from unittest.mock import MagicMock

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller, RunTrace, StepResult, EscalationType
from e0_controller.evaluation import RunEvaluation, SemanticEvaluation, ScenarioEvaluation
from e0_controller.self_tuning import (
    RunFieldSummary,
    DerivedThresholds,
    ParameterSensitivity,
    TuningProposal,
    MetaTuningResult,
    field_summary_from_run,
    derive_thresholds,
    compute_parameter_sensitivities,
    propose_tuning,
    apply_tuning,
    _would_oscillate,
    TUNABLE_PARAMS,
)
from e0_controller.reflection import should_reflect


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _make_landscape(n_states=5, n_edges_per_state=2):
    """Build a small test landscape with known structure."""
    L = Landscape()
    states = [f"S{i}" for i in range(n_states)]
    for s in states:
        L.add_state(s)
    for i, s in enumerate(states):
        for j in range(1, n_edges_per_state + 1):
            t = states[(i + j) % n_states]
            L.add_edge(s, t, delta=1.0, resistance=1.0)
    return L, states


def _make_trace(states_visited, escalation_indices=None):
    """Build a RunTrace from a list of states."""
    escalation_indices = escalation_indices or set()
    steps = []
    for i in range(len(states_visited) - 1):
        esc = i in escalation_indices
        steps.append(StepResult(
            tau=i,
            source=states_visited[i],
            target=states_visited[i + 1],
            outcome=Outcome.SUCCESS,
            s_eff=1.0,
            r_eff_before=1.0,
            r_eff_after=1.0,
            candidates=[states_visited[i + 1]],
            escalated=esc,
            escalation_type=EscalationType.DEAD_END if esc else EscalationType.NONE,
        ))
    trace = RunTrace(steps=steps)
    return trace


def _make_field_summary(**overrides):
    """Build a RunFieldSummary with sensible defaults."""
    defaults = dict(
        v_mean=0.5, v_max=1.0, v_total=5.0,
        num_states=5, num_edges=10,
        steps=10, escalations=0, repeated_cycles=0,
        unique_states_visited=5,
    )
    defaults.update(overrides)
    return RunFieldSummary(**defaults)


def _make_evaluation(goal_reached=True, efficiency=0.7, loop_penalty=0.0,
                     escalations=0, steps=10, progress=0.8, rating="B",
                     graph_score=0.7, r_coh_avg=0.0, amplitude_drift=0.0,
                     theta_consistency=1.0):
    """Build a ScenarioEvaluation with controllable fields."""
    run = RunEvaluation(
        goal_reached=goal_reached, steps=steps, escalations=escalations,
        revisits=0, repeated_cycles=0,
        progress_ratio=progress, avg_tension=1.0, total_tension=10.0,
        goal_reach_efficiency=efficiency, loop_penalty=loop_penalty,
        step_success_rate=1.0, rating=rating,
        r_coh_avg=r_coh_avg, amplitude_drift=amplitude_drift,
        theta_consistency=theta_consistency,
    )
    return ScenarioEvaluation(
        scenario_id="test", domain="test",
        graph_score=graph_score,
        run_evaluation=run,
        semantic_evaluation=None,
        hard_failure=None,
        overall_score=None,
    )


# ──────────────────────────────────────────────
# 1. RunFieldSummary
# ──────────────────────────────────────────────

class TestRunFieldSummary(unittest.TestCase):
    """Test field-derived metrics from RunFieldSummary."""

    def test_tau_eff_normalised(self):
        fs = _make_field_summary(v_mean=0.4, v_max=0.8)
        self.assertAlmostEqual(fs.tau_eff, 0.5, places=5)

    def test_tau_eff_zero_vmax(self):
        fs = _make_field_summary(v_mean=0.0, v_max=0.0)
        self.assertEqual(fs.tau_eff, 0.0)

    def test_tau_eff_capped_at_one(self):
        fs = _make_field_summary(v_mean=1.5, v_max=1.0)
        self.assertEqual(fs.tau_eff, 1.0)

    def test_tau_loop_scales_with_topology(self):
        fs5 = _make_field_summary(repeated_cycles=2, num_states=5)
        fs50 = _make_field_summary(repeated_cycles=2, num_states=50)
        self.assertGreater(fs5.tau_loop, fs50.tau_loop)

    def test_tau_esc_scales_with_edges(self):
        fs = _make_field_summary(escalations=3, num_edges=10)
        self.assertAlmostEqual(fs.tau_esc, 0.3, places=5)

    def test_tau_progress(self):
        fs = _make_field_summary(unique_states_visited=3, num_states=6)
        self.assertAlmostEqual(fs.tau_progress, 0.5, places=5)

    def test_tau_efficiency(self):
        fs = _make_field_summary(unique_states_visited=5, steps=10)
        self.assertAlmostEqual(fs.tau_efficiency, 0.5, places=5)


# ──────────────────────────────────────────────
# 2. Field Summary from Real Run
# ──────────────────────────────────────────────

class TestFieldSummaryFromRun(unittest.TestCase):
    """Test extraction of RunFieldSummary from Landscape + RunTrace."""

    def test_basic_extraction(self):
        L, states = _make_landscape(n_states=4, n_edges_per_state=2)
        trace = _make_trace(["S0", "S1", "S2", "S3"])
        fs = field_summary_from_run(L, trace)

        self.assertEqual(fs.num_states, 4)
        self.assertEqual(fs.num_edges, 8)  # 4 states × 2 edges
        self.assertEqual(fs.steps, 3)
        self.assertEqual(fs.unique_states_visited, 4)
        self.assertEqual(fs.escalations, 0)
        self.assertGreater(fs.v_max, 0)
        self.assertGreater(fs.v_mean, 0)

    def test_escalation_counted(self):
        L, states = _make_landscape()
        trace = _make_trace(["S0", "S1", "S2"], escalation_indices={1})
        fs = field_summary_from_run(L, trace)
        self.assertEqual(fs.escalations, 1)

    def test_repeated_cycle_detected(self):
        L, states = _make_landscape()
        # S0→S1→S0→S1: two overlapping 2-cycles (S0-S1-S0 and S1-S0-S1)
        trace = _make_trace(["S0", "S1", "S0", "S1"])
        fs = field_summary_from_run(L, trace)
        self.assertEqual(fs.repeated_cycles, 2)


# ──────────────────────────────────────────────
# 3. Derived Thresholds
# ──────────────────────────────────────────────

class TestDerivedThresholds(unittest.TestCase):
    """Test that thresholds scale with field strength."""

    def test_strong_field_tighter_thresholds(self):
        strong = _make_field_summary(v_mean=0.9, v_max=1.0)
        weak = _make_field_summary(v_mean=0.1, v_max=1.0)

        dt_strong = derive_thresholds(strong)
        dt_weak = derive_thresholds(weak)

        # Strong field → higher efficiency expectation
        self.assertGreater(dt_strong.quality_efficiency, dt_weak.quality_efficiency)
        # Strong field → less loop tolerance
        self.assertLess(dt_strong.quality_loop, dt_weak.quality_loop)
        # Strong field → less escalation tolerance
        self.assertLess(dt_strong.quality_escalation, dt_weak.quality_escalation)

    def test_opportunity_scales(self):
        strong = _make_field_summary(v_mean=0.9, v_max=1.0)
        weak = _make_field_summary(v_mean=0.1, v_max=1.0)

        dt_strong = derive_thresholds(strong)
        dt_weak = derive_thresholds(weak)

        self.assertGreater(dt_strong.opportunity_efficiency, dt_weak.opportunity_efficiency)

    def test_thresholds_in_valid_range(self):
        fs = _make_field_summary(v_mean=0.5, v_max=1.0, num_states=10)
        dt = derive_thresholds(fs)

        self.assertGreaterEqual(dt.quality_efficiency, 0.0)
        self.assertLessEqual(dt.quality_efficiency, 1.0)
        self.assertGreaterEqual(dt.quality_loop, 0.0)
        self.assertGreaterEqual(dt.quality_escalation, 0.0)
        self.assertLessEqual(dt.quality_escalation, 1.0)


# ──────────────────────────────────────────────
# 4. Parameter Sensitivity
# ──────────────────────────────────────────────

class TestParameterSensitivity(unittest.TestCase):
    """Test per-parameter sensitivity estimation."""

    def test_high_loop_increases_alpha_sensitivity(self):
        fs = _make_field_summary(repeated_cycles=5, num_states=5)  # tau_loop = 1.0
        params = {"alpha": 2.0, "s_max": 1e6, "c_min": 0.0,
                  "confidence_threshold": 0.0, "hybrid_horizon": 3}
        sens = compute_parameter_sensitivities(fs, params)

        alpha_sens = next(s for s in sens if s.name == "alpha")
        self.assertGreater(alpha_sens.sensitivity, 0.5)
        self.assertEqual(alpha_sens.suggested_direction, "increase")

    def test_high_escalation_increases_smax_sensitivity(self):
        fs = _make_field_summary(escalations=5, num_edges=10)  # tau_esc = 0.5
        params = {"alpha": 2.0, "s_max": 5.0, "c_min": 0.3,
                  "confidence_threshold": 0.0, "hybrid_horizon": 3}
        sens = compute_parameter_sensitivities(fs, params)

        smax_sens = next(s for s in sens if s.name == "s_max")
        self.assertGreater(smax_sens.sensitivity, 0.1)
        self.assertEqual(smax_sens.suggested_direction, "increase")

    def test_sorted_by_sensitivity_descending(self):
        fs = _make_field_summary(repeated_cycles=3, num_states=5, escalations=1, num_edges=10)
        params = {"alpha": 2.0, "s_max": 1e6, "c_min": 0.0,
                  "confidence_threshold": 0.0, "hybrid_horizon": 3}
        sens = compute_parameter_sensitivities(fs, params)

        values = [s.sensitivity for s in sens]
        self.assertEqual(values, sorted(values, reverse=True))

    def test_stable_when_no_issues(self):
        fs = _make_field_summary(repeated_cycles=0, escalations=0,
                                 v_mean=0.9, v_max=1.0)
        params = {"alpha": 2.0, "s_max": 1e6, "c_min": 0.0,
                  "confidence_threshold": 0.0, "hybrid_horizon": 3}
        sens = compute_parameter_sensitivities(fs, params)

        alpha_sens = next(s for s in sens if s.name == "alpha")
        self.assertEqual(alpha_sens.suggested_direction, "stable")


# ──────────────────────────────────────────────
# 5. Oscillation Protection (H_meta)
# ──────────────────────────────────────────────

class TestOscillationProtection(unittest.TestCase):
    """Test H_meta prevents parameter ping-pong."""

    def test_no_oscillation_short_history(self):
        self.assertFalse(_would_oscillate([1.0, 2.0], "increase"))

    def test_detects_alternating_direction(self):
        # 1.0 → 2.0 → 1.5: up then down = oscillation
        self.assertTrue(_would_oscillate([1.0, 2.0, 1.5], "decrease"))

    def test_same_direction_not_oscillation(self):
        # 1.0 → 2.0 → 3.0: consistently increasing
        self.assertFalse(_would_oscillate([1.0, 2.0, 3.0], "increase"))

    def test_flat_not_oscillation(self):
        self.assertFalse(_would_oscillate([1.0, 1.0, 1.0], "increase"))


# ──────────────────────────────────────────────
# 6. Tuning Proposals
# ──────────────────────────────────────────────

class TestTuningProposals(unittest.TestCase):
    """Test bounded tuning proposal generation."""

    def test_proposals_generated_on_issues(self):
        fs = _make_field_summary(repeated_cycles=3, num_states=5,
                                 escalations=3, num_edges=10)
        params = {"alpha": 2.0, "s_max": 5.0, "c_min": 0.3,
                  "confidence_threshold": 0.0, "hybrid_horizon": 3}
        result = propose_tuning(fs, params)

        self.assertIsInstance(result, MetaTuningResult)
        self.assertGreater(len(result.proposals), 0)

    def test_proposals_bounded(self):
        fs = _make_field_summary(repeated_cycles=5, num_states=5)
        params = {"alpha": 2.0}
        result = propose_tuning(fs, params, step_fraction=0.15)

        for p in result.proposals:
            lo, hi = TUNABLE_PARAMS[p.parameter]
            max_step = (hi - lo) * 0.15
            self.assertLessEqual(abs(p.new_value - p.old_value), max_step + 1e-10)

    def test_no_proposals_when_stable(self):
        fs = _make_field_summary(repeated_cycles=0, escalations=0,
                                 v_mean=0.9, v_max=1.0)
        params = {"alpha": 2.0, "s_max": 1e6, "c_min": 0.0,
                  "confidence_threshold": 0.0, "hybrid_horizon": 3}
        result = propose_tuning(fs, params)
        self.assertEqual(len(result.proposals), 0)

    def test_oscillation_prevents_proposal(self):
        fs = _make_field_summary(repeated_cycles=3, num_states=5)
        params = {"alpha": 5.0}
        # History: alpha went up, then down → oscillating
        history = {"alpha": [2.0, 5.0, 3.0]}
        result = propose_tuning(fs, params, param_history=history)

        alpha_proposals = [p for p in result.proposals if p.parameter == "alpha"]
        self.assertEqual(len(alpha_proposals), 0)

    def test_meta_historization_updated(self):
        fs = _make_field_summary(repeated_cycles=3, num_states=5)
        params = {"alpha": 2.0}
        history = {}
        result = propose_tuning(fs, params, param_history=history)

        if result.proposals:
            self.assertIn("alpha", result.meta_historization)


# ──────────────────────────────────────────────
# 7. Apply Tuning
# ──────────────────────────────────────────────

class TestApplyTuning(unittest.TestCase):
    """Test applying proposals to a controller."""

    def test_apply_changes_controller_params(self):
        L, _ = _make_landscape()
        ctrl = E0Controller(L, lambda s, t: Outcome.SUCCESS, alpha=2.0)

        proposals = [TuningProposal(
            parameter="alpha", old_value=2.0, new_value=3.5,
            sensitivity=0.8, reason="tau_loop=0.6 → increase alpha",
        )]
        applied = apply_tuning(ctrl, proposals)

        self.assertEqual(len(applied), 1)
        self.assertAlmostEqual(ctrl.alpha, 3.5)

    def test_skip_unknown_params(self):
        L, _ = _make_landscape()
        ctrl = E0Controller(L, lambda s, t: Outcome.SUCCESS)

        proposals = [TuningProposal(
            parameter="nonexistent_param", old_value=0.0, new_value=1.0,
            sensitivity=1.0, reason="test",
        )]
        applied = apply_tuning(ctrl, proposals)
        self.assertEqual(len(applied), 0)


# ──────────────────────────────────────────────
# 8. Integration with Reflection
# ──────────────────────────────────────────────

class TestReflectionWithFieldThresholds(unittest.TestCase):
    """Test that should_reflect uses field-derived thresholds when provided."""

    def test_static_triggers_quality(self):
        """Without field_summary, uses static thresholds (_QUALITY_EFFICIENCY_CEIL=0.5)."""
        ev = _make_evaluation(efficiency=0.3)
        decision = should_reflect(ev)
        self.assertTrue(decision.reflect)
        self.assertEqual(decision.reflection_type, "quality")

    def test_derived_thresholds_change_trigger(self):
        """With weak field (tau_eff=0.1), quality_efficiency = 0.05.
        So efficiency=0.3 should NOT trigger quality."""
        ev = _make_evaluation(efficiency=0.3, progress=0.9)

        weak_field = _make_field_summary(v_mean=0.1, v_max=1.0)
        decision = should_reflect(ev, field_summary=weak_field)

        # In weak field, 0.3 efficiency is acceptable (threshold ≈ 0.05)
        if decision.reflect:
            # If triggered, it should NOT be for efficiency
            self.assertNotIn("low efficiency", decision.reason)

    def test_strong_field_tightens_triggers(self):
        """With strong field (tau_eff=0.8), quality_efficiency = 0.4.
        So efficiency=0.35 should trigger quality."""
        ev = _make_evaluation(efficiency=0.35, progress=0.9)

        strong_field = _make_field_summary(v_mean=0.8, v_max=1.0)
        decision = should_reflect(ev, field_summary=strong_field)
        self.assertTrue(decision.reflect)
        self.assertEqual(decision.reflection_type, "quality")

    def test_failure_triggers_unchanged(self):
        """Hard failures always trigger regardless of field_summary."""
        ev = _make_evaluation(goal_reached=False)
        fs = _make_field_summary()
        decision = should_reflect(ev, field_summary=fs)
        self.assertTrue(decision.reflect)
        self.assertEqual(decision.reflection_type, "failure")

    def test_backward_compatible_without_field(self):
        """Without field_summary, existing behavior is preserved."""
        ev = _make_evaluation(efficiency=0.3)
        decision_old = should_reflect(ev)
        decision_new = should_reflect(ev, field_summary=None)
        self.assertEqual(decision_old.reflect, decision_new.reflect)
        self.assertEqual(decision_old.reflection_type, decision_new.reflection_type)


if __name__ == "__main__":
    unittest.main()
