"""
Tests for Amplitude Mass Trap Detection
=========================================
Validates the path_count_imbalance detector across OverlayReport,
RunEvaluation, reflection quality triggers, and self-tuning
horizon inversion.

Tests cover:
  1. OverlayReport.path_count_imbalance property
  2. RunEvaluation.path_count_imbalance_max field
  3. Reflection should_reflect mass_trap_suspect trigger
  4. Reflection _reflect_quality mass trap pattern
  5. Self-tuning horizon inversion under mass trap
  6. Self-tuning confidence_threshold increase under mass trap
  7. RunFieldSummary.path_count_imbalance_max extraction
  8. _extract_imbalance_max from trace overlays
"""

import unittest
from unittest.mock import MagicMock

from e0_controller.amplitude_overlay import ActionAmplitudeInfo, OverlayReport
from e0_controller.controller import RunTrace, StepResult, Outcome, EscalationType
from e0_controller.evaluation import RunEvaluation, ScenarioEvaluation, evaluate_run
from e0_controller.reflection import (
    should_reflect,
    reflect,
    _MASS_TRAP_IMBALANCE_THRESHOLD,
)
from e0_controller.self_tuning import (
    RunFieldSummary,
    compute_parameter_sensitivities,
    _extract_imbalance_max,
    TUNABLE_PARAMS,
)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _make_overlay(path_counts, current="X"):
    """Build an OverlayReport with specified path counts per action."""
    infos = []
    total_intensity = 0.0
    for i, count in enumerate(path_counts):
        action = f"A{i}"
        intensity = float(count)  # simplified: intensity ~ path_count
        total_intensity += intensity
        infos.append(ActionAmplitudeInfo(
            action=action,
            direct_s_eff=1.0,
            penalized_s=1.0,
            path_count=count,
            paths=[["X", action]] * count,
            psi_total=complex(count, 0),
            intensity=intensity,
        ))
    # Normalise probabilities
    for info in infos:
        info.probability = info.intensity / total_intensity if total_intensity > 0 else 0.0
    return OverlayReport(
        current=current,
        horizon_edges=3,
        geometry="simple",
        admissible_actions=[f"A{i}" for i in range(len(path_counts))],
        deterministic_choice="A0",
        deterministic_escalated=False,
        action_infos=infos,
    )


def _make_run_eval(path_count_imbalance_max=1.0, repeated_cycles=0,
                   goal_reached=True, steps=10, efficiency=0.7,
                   loop_penalty=0.0, rating="B"):
    """Build a RunEvaluation with controllable mass trap fields."""
    return RunEvaluation(
        goal_reached=goal_reached, steps=steps, escalations=0,
        revisits=0, repeated_cycles=repeated_cycles,
        progress_ratio=0.8, avg_tension=1.0, total_tension=10.0,
        goal_reach_efficiency=efficiency, loop_penalty=loop_penalty,
        step_success_rate=1.0, rating=rating,
        path_count_imbalance_max=path_count_imbalance_max,
    )


def _make_scenario_eval(path_count_imbalance_max=1.0, repeated_cycles=0,
                        goal_reached=True, efficiency=0.7,
                        loop_penalty=0.0, rating="B"):
    """Build a ScenarioEvaluation with mass trap fields."""
    run = _make_run_eval(
        path_count_imbalance_max=path_count_imbalance_max,
        repeated_cycles=repeated_cycles,
        goal_reached=goal_reached,
        efficiency=efficiency,
        loop_penalty=loop_penalty,
        rating=rating,
    )
    return ScenarioEvaluation(
        scenario_id="test", domain="test",
        graph_score=0.8,
        run_evaluation=run,
        semantic_evaluation=None,
        hard_failure=None,
        overall_score=0.7,
    )


def _make_field_summary(**overrides):
    """Build a RunFieldSummary with sensible defaults."""
    defaults = dict(
        v_mean=0.5, v_max=1.0, v_total=5.0,
        num_states=5, num_edges=10,
        steps=10, escalations=0, repeated_cycles=0,
        unique_states_visited=5,
        path_count_imbalance_max=1.0,
    )
    defaults.update(overrides)
    return RunFieldSummary(**defaults)


# ──────────────────────────────────────────────
# 1. OverlayReport.path_count_imbalance
# ──────────────────────────────────────────────

class TestOverlayPathCountImbalance(unittest.TestCase):
    """OverlayReport.path_count_imbalance computes max/min path count ratio."""

    def test_balanced_actions(self):
        """Equal path counts → imbalance 1.0."""
        overlay = _make_overlay([5, 5, 5])
        self.assertAlmostEqual(overlay.path_count_imbalance, 1.0)

    def test_moderate_imbalance(self):
        """3:1 ratio → imbalance 3.0."""
        overlay = _make_overlay([6, 2])
        self.assertAlmostEqual(overlay.path_count_imbalance, 3.0)

    def test_severe_imbalance(self):
        """12:1 ratio → mass trap territory."""
        overlay = _make_overlay([12, 1])
        self.assertAlmostEqual(overlay.path_count_imbalance, 12.0)

    def test_single_action(self):
        """One action → imbalance 1.0 (no comparison possible)."""
        overlay = _make_overlay([5])
        self.assertAlmostEqual(overlay.path_count_imbalance, 1.0)

    def test_zero_path_actions_excluded(self):
        """Actions with 0 paths are excluded from ratio."""
        overlay = _make_overlay([10, 0, 5])
        # Only [10, 5] count → ratio 2.0
        self.assertAlmostEqual(overlay.path_count_imbalance, 2.0)

    def test_empty_actions(self):
        """No actions → imbalance 1.0."""
        overlay = _make_overlay([])
        self.assertAlmostEqual(overlay.path_count_imbalance, 1.0)

    def test_threshold_constant(self):
        """Mass trap threshold is 3.0."""
        self.assertEqual(_MASS_TRAP_IMBALANCE_THRESHOLD, 3.0)


# ──────────────────────────────────────────────
# 2. RunEvaluation.path_count_imbalance_max
# ──────────────────────────────────────────────

class TestRunEvalImbalance(unittest.TestCase):
    """RunEvaluation carries and preserves path_count_imbalance_max."""

    def test_default_is_one(self):
        """Default imbalance is 1.0 (no trap)."""
        r = RunEvaluation(
            goal_reached=True, steps=5, escalations=0, revisits=0,
            repeated_cycles=0, progress_ratio=1.0, avg_tension=1.0,
            total_tension=5.0, goal_reach_efficiency=1.0,
            loop_penalty=0.0, step_success_rate=1.0, rating="A",
        )
        self.assertAlmostEqual(r.path_count_imbalance_max, 1.0)

    def test_evaluate_run_passes_through(self):
        """evaluate_run() accepts and rounds path_count_imbalance_max."""
        r = evaluate_run(
            path=["A", "B", "C"], steps=2, escalation_count=0,
            revisit_count=0, success_rate=1.0, avg_tension=1.0,
            total_tension=2.0, reached_goal=True, happy_path_length=2,
            path_count_imbalance_max=5.67891,
        )
        self.assertAlmostEqual(r.path_count_imbalance_max, 5.6789)


# ──────────────────────────────────────────────
# 3. Reflection: should_reflect mass trap trigger
# ──────────────────────────────────────────────

class TestReflectionMassTrapTrigger(unittest.TestCase):
    """should_reflect fires quality trigger on mass trap conditions."""

    def test_no_trigger_without_cycles(self):
        """High imbalance alone does NOT trigger — needs looping."""
        ev = _make_scenario_eval(path_count_imbalance_max=10.0, repeated_cycles=0)
        decision = should_reflect(ev)
        if decision.reflect:
            self.assertNotIn("mass trap", decision.reason)

    def test_no_trigger_without_imbalance(self):
        """Looping alone does NOT trigger mass trap — needs imbalance."""
        ev = _make_scenario_eval(path_count_imbalance_max=1.0, repeated_cycles=3,
                                 loop_penalty=0.1)
        decision = should_reflect(ev)
        if decision.reflect:
            self.assertNotIn("mass trap", decision.reason)

    def test_triggers_on_imbalance_plus_cycles(self):
        """High imbalance + cycles → mass trap suspect quality trigger."""
        ev = _make_scenario_eval(path_count_imbalance_max=5.0, repeated_cycles=2,
                                 loop_penalty=0.1)
        decision = should_reflect(ev)
        self.assertTrue(decision.reflect)
        self.assertIn("mass trap", decision.reason)
        self.assertEqual(decision.reflection_type, "quality")

    def test_threshold_exact(self):
        """At exactly 3.0 imbalance — does NOT trigger (> not >=)."""
        ev = _make_scenario_eval(path_count_imbalance_max=3.0, repeated_cycles=1,
                                 loop_penalty=0.05)
        decision = should_reflect(ev)
        if decision.reflect:
            self.assertNotIn("mass trap", decision.reason)


# ──────────────────────────────────────────────
# 4. Reflection: _reflect_quality mass trap pattern
# ──────────────────────────────────────────────

class TestReflectionMassTrapPattern(unittest.TestCase):
    """reflect() produces mass trap pattern in quality report."""

    def test_quality_report_contains_mass_trap_pattern(self):
        """When mass trap fires, reflection report has the pattern."""
        ev = _make_scenario_eval(path_count_imbalance_max=8.0, repeated_cycles=3,
                                 loop_penalty=0.15)
        report = reflect(ev)
        patterns_text = " ".join(report.observed_patterns)
        self.assertIn("mass trap", patterns_text.lower())

    def test_quality_report_recommends_horizon_reduction(self):
        """Mass trap report recommends reducing hybrid_horizon."""
        ev = _make_scenario_eval(path_count_imbalance_max=8.0, repeated_cycles=3,
                                 loop_penalty=0.15)
        report = reflect(ev)
        actions_text = " ".join(report.recommended_actions)
        self.assertIn("hybrid_horizon", actions_text.lower())

    def test_quality_report_evidence_has_imbalance(self):
        """Evidence includes path_count_imbalance_max value."""
        ev = _make_scenario_eval(path_count_imbalance_max=6.5, repeated_cycles=2,
                                 loop_penalty=0.1)
        report = reflect(ev)
        evidence_text = " ".join(report.evidence)
        self.assertIn("imbalance", evidence_text.lower())


# ──────────────────────────────────────────────
# 5. Self-tuning: horizon inversion
# ──────────────────────────────────────────────

class TestSelfTuningHorizonInversion(unittest.TestCase):
    """compute_parameter_sensitivities inverts horizon under mass trap."""

    def test_normal_case_horizon_increase(self):
        """Without mass trap, weak field → suggest horizon increase."""
        # tau_eff = v_mean / v_max = 0.3 / 1.0 = 0.3 → weak field
        fs = _make_field_summary(v_mean=0.3, v_max=1.0, path_count_imbalance_max=1.0)
        # tau_eff < 0.5 → direction "increase"
        sensitivities = compute_parameter_sensitivities(
            fs, {"hybrid_horizon": 3})
        horizon = next(s for s in sensitivities if s.name == "hybrid_horizon")
        self.assertEqual(horizon.suggested_direction, "increase")

    def test_mass_trap_horizon_decrease(self):
        """With loop + imbalance → suggest horizon DECREASE."""
        fs = _make_field_summary(
            repeated_cycles=3, path_count_imbalance_max=6.0)
        sensitivities = compute_parameter_sensitivities(
            fs, {"hybrid_horizon": 5})
        horizon = next(s for s in sensitivities if s.name == "hybrid_horizon")
        self.assertEqual(horizon.suggested_direction, "decrease")

    def test_mass_trap_confidence_increase(self):
        """With loop + imbalance → suggest confidence_threshold INCREASE."""
        fs = _make_field_summary(
            repeated_cycles=3, path_count_imbalance_max=6.0)
        sensitivities = compute_parameter_sensitivities(
            fs, {"confidence_threshold": 0.3})
        conf = next(s for s in sensitivities if s.name == "confidence_threshold")
        self.assertEqual(conf.suggested_direction, "increase")

    def test_no_inversion_without_looping(self):
        """High imbalance but no loops → normal horizon logic."""
        fs = _make_field_summary(
            repeated_cycles=0, path_count_imbalance_max=10.0)
        sensitivities = compute_parameter_sensitivities(
            fs, {"hybrid_horizon": 3})
        horizon = next(s for s in sensitivities if s.name == "hybrid_horizon")
        # tau_loop = 0, so mass trap doesn't fire — normal logic applies
        self.assertNotEqual(horizon.suggested_direction, "decrease")


# ──────────────────────────────────────────────
# 6. _extract_imbalance_max from trace
# ──────────────────────────────────────────────

class TestExtractImbalanceMax(unittest.TestCase):
    """_extract_imbalance_max reads worst imbalance from trace overlays."""

    def test_no_overlays(self):
        """Trace without overlays → default 1.0."""
        trace = RunTrace(steps=[
            StepResult(tau=0, source="A", target="B",
                       outcome=Outcome.SUCCESS, s_eff=1.0,
                       r_eff_before=1.0, r_eff_after=1.0,
                       candidates=["B"]),
        ])
        self.assertAlmostEqual(_extract_imbalance_max(trace), 1.0)

    def test_with_overlays(self):
        """Trace with overlay → extracts max imbalance."""
        overlay1 = _make_overlay([3, 3])   # imbalance 1.0
        overlay2 = _make_overlay([12, 1])  # imbalance 12.0
        trace = RunTrace(steps=[
            StepResult(tau=0, source="A", target="B",
                       outcome=Outcome.SUCCESS, s_eff=1.0,
                       r_eff_before=1.0, r_eff_after=1.0,
                       candidates=["B"], overlay=overlay1),
            StepResult(tau=1, source="B", target="C",
                       outcome=Outcome.SUCCESS, s_eff=1.0,
                       r_eff_before=1.0, r_eff_after=1.0,
                       candidates=["C"], overlay=overlay2),
        ])
        self.assertAlmostEqual(_extract_imbalance_max(trace), 12.0)

    def test_mixed_overlay_and_none(self):
        """Steps with and without overlays → only reads available ones."""
        overlay = _make_overlay([8, 2])  # imbalance 4.0
        trace = RunTrace(steps=[
            StepResult(tau=0, source="A", target="B",
                       outcome=Outcome.SUCCESS, s_eff=1.0,
                       r_eff_before=1.0, r_eff_after=1.0,
                       candidates=["B"]),
            StepResult(tau=1, source="B", target="C",
                       outcome=Outcome.SUCCESS, s_eff=1.0,
                       r_eff_before=1.0, r_eff_after=1.0,
                       candidates=["C"], overlay=overlay),
        ])
        self.assertAlmostEqual(_extract_imbalance_max(trace), 4.0)


# ──────────────────────────────────────────────
# 7. RunFieldSummary integration
# ──────────────────────────────────────────────

class TestFieldSummaryImbalance(unittest.TestCase):
    """RunFieldSummary carries and computes from path_count_imbalance_max."""

    def test_default_is_one(self):
        """Default value is 1.0."""
        fs = _make_field_summary()
        self.assertAlmostEqual(fs.path_count_imbalance_max, 1.0)

    def test_custom_value(self):
        """Custom value persists."""
        fs = _make_field_summary(path_count_imbalance_max=7.5)
        self.assertAlmostEqual(fs.path_count_imbalance_max, 7.5)


if __name__ == "__main__":
    unittest.main()
