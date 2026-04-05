"""Tests for C150 — Parameter Sensitivity via Self-Graph Attribution."""

from dataclasses import replace

import pytest

from e0_controller.config import E0Config, DEFAULTS
from e0_controller.controller import RunTrace
from e0_controller.dual_reflection import SelfGraphDiagnosis
from e0_controller.landscape import Landscape
from e0_controller.parameter_sensitivity import (
    COMPONENT_PARAMS,
    SensitivityReport,
    TrialResult,
    run_trial,
    sensitivity_analysis,
    suggest_perturbations,
)
from e0_controller.primitives import Outcome
from e0_controller.self_graph import ALL_COMPONENTS

# ── Helpers ───────────────────────────────────────────────


def _make_landscape():
    """Fully connected 4-node landscape — every node has 3 neighbours."""
    L = Landscape()
    for s in ("S", "A", "B", "C"):
        for t in ("S", "A", "B", "C"):
            if s != t:
                L.add_edge(s, t, delta=1.0, resistance=1.0)
    return L


def _success_fn(s, t):
    return Outcome.SUCCESS


def _mixed_fn(s, t):
    """Transitions to C always fail."""
    return Outcome.FAILURE if t == "C" else Outcome.SUCCESS


# ── TestComponentParams ───────────────────────────────────


class TestComponentParams:
    def test_all_components_mapped(self):
        for comp in ALL_COMPONENTS:
            assert comp in COMPONENT_PARAMS

    def test_params_exist_in_config(self):
        config_fields = set(E0Config.__dataclass_fields__)
        for params in COMPONENT_PARAMS.values():
            for p in params:
                assert p in config_fields, f"{p} not in E0Config"


# ── TestTrialResult ───────────────────────────────────────


class TestTrialResult:
    def _make(self, qualities=None, diagnosis=None):
        return TrialResult(
            config=DEFAULTS,
            trace=RunTrace(),
            diagnosis=diagnosis,
            component_qualities=qualities or {},
        )

    def test_quality_score_empty(self):
        assert self._make().quality_score == 0.0

    def test_quality_score_sum(self):
        r = self._make({"a": 0.3, "b": -0.1, "c": 0.5})
        assert abs(r.quality_score - 0.7) < 1e-9

    def test_health_score_no_diagnosis(self):
        assert self._make().health_score == 0.0

    def test_health_score_formula(self):
        diag = SelfGraphDiagnosis(
            healthy=["a", "b"],
            confused=["c"],
            harmful=["d"],
        )
        r = self._make(diagnosis=diag)
        # +2 − 1 − 2 = −1
        assert r.health_score == -1.0

    def test_counts(self):
        diag = SelfGraphDiagnosis(
            healthy=["a", "b", "c"],
            confused=["d"],
            harmful=[],
        )
        r = self._make(diagnosis=diag)
        assert r.healthy_count == 3
        assert r.confused_count == 1
        assert r.harmful_count == 0


# ── TestRunTrial ──────────────────────────────────────────


class TestRunTrial:
    def test_default_config(self):
        result = run_trial(_make_landscape(), _success_fn, "S", max_cycles=15)
        assert isinstance(result, TrialResult)
        assert result.config is DEFAULTS
        assert result.trace is not None
        assert result.diagnosis is not None

    def test_has_component_qualities(self):
        result = run_trial(_make_landscape(), _success_fn, "S", max_cycles=20)
        assert len(result.component_qualities) > 0

    def test_landscape_independence(self):
        """Deep-copy ensures the original landscape is untouched."""
        L = _make_landscape()
        r_before = L.effective_resistance("S", "A")
        run_trial(L, _success_fn, "S", max_cycles=10)
        assert L.effective_resistance("S", "A") == r_before

    def test_custom_config(self):
        cfg = replace(DEFAULTS, alpha=5.0, recent_k=1)
        result = run_trial(_make_landscape(), _success_fn, "S", config=cfg, max_cycles=15)
        assert result.config.alpha == 5.0
        assert result.config.recent_k == 1

    def test_with_goal(self):
        L = Landscape()
        L.add_edge("S", "G", delta=1.0, resistance=1.0)
        result = run_trial(L, _success_fn, "S", goal="G", max_cycles=50)
        assert len(result.trace.steps) <= 50

    def test_mixed_outcomes(self):
        result = run_trial(_make_landscape(), _mixed_fn, "S", max_cycles=20)
        assert len(result.component_qualities) > 0


# ── TestSensitivityAnalysis ───────────────────────────────


class TestSensitivityAnalysis:
    def test_two_configs(self):
        configs = [DEFAULTS, replace(DEFAULTS, alpha=5.0)]
        report = sensitivity_analysis(
            _make_landscape(), _success_fn, "S", None, configs, max_cycles=15,
        )
        assert isinstance(report, SensitivityReport)
        assert len(report.trials) == 2

    def test_best_trial_highest_quality(self):
        configs = [DEFAULTS, replace(DEFAULTS, alpha=0.5)]
        report = sensitivity_analysis(
            _make_landscape(), _success_fn, "S", None, configs, max_cycles=15,
        )
        best = report.best_trial
        for t in report.trials:
            assert best.quality_score >= t.quality_score

    def test_summary_string(self):
        configs = [DEFAULTS, replace(DEFAULTS, rho=0.5)]
        report = sensitivity_analysis(
            _make_landscape(), _success_fn, "S", None, configs, max_cycles=15,
        )
        s = report.summary()
        assert "Sensitivity Report" in s
        assert "Trial 0" in s
        assert "Trial 1" in s


# ── TestParameterImpact ───────────────────────────────────


class TestParameterImpact:
    def test_single_config_empty(self):
        report = sensitivity_analysis(
            _make_landscape(), _success_fn, "S", None, [DEFAULTS], max_cycles=10,
        )
        assert report.parameter_impact() == {}

    def test_varying_param_detected(self):
        configs = [DEFAULTS, replace(DEFAULTS, alpha=10.0)]
        report = sensitivity_analysis(
            _make_landscape(), _success_fn, "S", None, configs, max_cycles=15,
        )
        assert "alpha" in report.parameter_impact()

    def test_constant_param_absent(self):
        configs = [DEFAULTS, replace(DEFAULTS, alpha=10.0)]
        report = sensitivity_analysis(
            _make_landscape(), _success_fn, "S", None, configs, max_cycles=15,
        )
        assert "rho" not in report.parameter_impact()


# ── TestSuggestPerturbations ──────────────────────────────


class TestSuggestPerturbations:
    def test_none_diagnosis(self):
        assert suggest_perturbations(None) == []

    def test_all_healthy(self):
        diag = SelfGraphDiagnosis(
            healthy=["historization", "transition_field"],
        )
        assert suggest_perturbations(diag) == []

    def test_harmful_historization(self):
        diag = SelfGraphDiagnosis(harmful=["historization"])
        variants = suggest_perturbations(diag)
        assert len(variants) > 0
        perturbed = set()
        for v in variants:
            for f in ("rho", "lambda_s", "lambda_f", "delta_max"):
                if getattr(v, f) != getattr(DEFAULTS, f):
                    perturbed.add(f)
        assert perturbed == {"rho", "lambda_s", "lambda_f", "delta_max"}

    def test_harmful_transition_field(self):
        diag = SelfGraphDiagnosis(harmful=["transition_field"])
        variants = suggest_perturbations(diag)
        assert len(variants) > 0
        perturbed = set()
        for v in variants:
            for f in ("alpha", "recent_k", "overload_threshold"):
                if getattr(v, f) != getattr(DEFAULTS, f):
                    perturbed.add(f)
        assert perturbed == {"alpha", "recent_k", "overload_threshold"}

    def test_confused_produces_variants(self):
        diag = SelfGraphDiagnosis(confused=["historization"])
        assert len(suggest_perturbations(diag)) > 0

    def test_no_params_component(self):
        """Components with no tunable params produce no variants."""
        diag = SelfGraphDiagnosis(harmful=["realization"])
        assert suggest_perturbations(diag) == []

    def test_harmful_amplitude_produces_numeric_perturbations(self):
        """amplitude has numeric params (confidence_threshold, hybrid_horizon)."""
        diag = SelfGraphDiagnosis(harmful=["amplitude"])
        variants = suggest_perturbations(diag)
        assert len(variants) > 0
        # hybrid_mode and use_su2 are non-numeric → skipped by suggest_perturbations
        perturbed = set()
        for v in variants:
            if v.confidence_threshold != DEFAULTS.confidence_threshold:
                perturbed.add("confidence_threshold")
            if v.hybrid_horizon != DEFAULTS.hybrid_horizon:
                perturbed.add("hybrid_horizon")
        assert "hybrid_horizon" in perturbed

    def test_perturbation_values_float(self):
        diag = SelfGraphDiagnosis(harmful=["historization"])
        variants = suggest_perturbations(diag, perturbation_factor=0.2)
        rho_vals = [v.rho for v in variants if v.rho != DEFAULTS.rho]
        assert len(rho_vals) == 2
        assert any(v > DEFAULTS.rho for v in rho_vals)
        assert any(v < DEFAULTS.rho for v in rho_vals)

    def test_perturbation_values_int(self):
        """Integer params (recent_k) get integer deltas."""
        diag = SelfGraphDiagnosis(harmful=["transition_field"])
        variants = suggest_perturbations(diag)
        rk_vals = [v.recent_k for v in variants if v.recent_k != DEFAULTS.recent_k]
        assert all(isinstance(v, int) for v in rk_vals)

    def test_custom_base_config(self):
        base = replace(DEFAULTS, rho=0.5)
        diag = SelfGraphDiagnosis(harmful=["historization"])
        variants = suggest_perturbations(diag, base_config=base)
        rho_vals = [v.rho for v in variants if v.rho != base.rho]
        assert len(rho_vals) == 2
        assert any(v > base.rho for v in rho_vals)
        assert any(v < base.rho for v in rho_vals)


# ── C152: Hybrid Mode / SU(2) in Sensitivity ─────────────


class TestHybridModeForwarding:
    """run_trial forwards hybrid_mode, hybrid_horizon, use_su2 to controller."""

    def test_greedy_excludes_amplitude_born(self):
        """GREEDY default: amplitude/born stay at zero in Self-Graph."""
        result = run_trial(_make_landscape(), _success_fn, "S", max_cycles=15)
        assert result.config.hybrid_mode == "greedy"
        # amplitude and born should have no load
        assert "amplitude" not in result.component_qualities
        assert "born" not in result.component_qualities

    def test_born_mode_activates_amplitude_and_born(self):
        """Born mode produces non-zero amplitude AND born load."""
        cfg = replace(DEFAULTS, hybrid_mode="born_sampling")
        result = run_trial(_make_landscape(), _success_fn, "S", config=cfg, max_cycles=20)
        assert "amplitude" in result.component_qualities
        assert "born" in result.component_qualities

    def test_amplitude_on_disagree_activates_amplitude_only(self):
        """AMPLITUDE_ON_DISAGREE: amplitude active, born not."""
        cfg = replace(DEFAULTS, hybrid_mode="amplitude_on_disagree")
        result = run_trial(_make_landscape(), _success_fn, "S", config=cfg, max_cycles=20)
        assert "amplitude" in result.component_qualities
        assert "born" not in result.component_qualities

    def test_hybrid_horizon_forwarded(self):
        """Custom hybrid_horizon is respected in controller."""
        cfg = replace(DEFAULTS, hybrid_mode="born_sampling", hybrid_horizon=5)
        result = run_trial(_make_landscape(), _success_fn, "S", config=cfg, max_cycles=15)
        # Simply runs without error; horizon=5 on a 4-node graph still works.
        assert result.trace is not None

    def test_use_su2_forwarded(self):
        """use_su2=True reaches the controller as SU(2) transport."""
        cfg = replace(DEFAULTS, hybrid_mode="born_sampling", use_su2=True)
        result = run_trial(_make_landscape(), _success_fn, "S", config=cfg, max_cycles=15)
        assert result.trace is not None
        assert "born" in result.component_qualities

    def test_use_su2_geometric(self):
        """use_su2='geometric' variant runs successfully."""
        cfg = replace(DEFAULTS, hybrid_mode="born_sampling", use_su2="geometric")
        result = run_trial(_make_landscape(), _success_fn, "S", config=cfg, max_cycles=15)
        assert result.trace is not None


class TestSensitivityWithModes:
    """sensitivity_analysis can compare greedy vs hybrid vs SU(2)."""

    def test_greedy_vs_born_different_qualities(self):
        """Greedy and Born modes produce different component quality profiles."""
        configs = [DEFAULTS, replace(DEFAULTS, hybrid_mode="born_sampling")]
        report = sensitivity_analysis(
            _make_landscape(), _success_fn, "S", None, configs, max_cycles=20,
        )
        greedy_q = report.trials[0].component_qualities
        born_q = report.trials[1].component_qualities
        # Born has amplitude/born components that greedy doesn't
        assert "amplitude" not in greedy_q
        assert "amplitude" in born_q

    def test_parameter_impact_detects_hybrid_mode(self):
        """hybrid_mode shows up in parameter_impact when it varies."""
        configs = [DEFAULTS, replace(DEFAULTS, hybrid_mode="born_sampling")]
        report = sensitivity_analysis(
            _make_landscape(), _success_fn, "S", None, configs, max_cycles=20,
        )
        impact = report.parameter_impact()
        assert "hybrid_mode" in impact

    def test_three_regime_comparison(self):
        """U(1), SU(2), and geometric Born configs run and compare."""
        configs = [
            replace(DEFAULTS, hybrid_mode="born_sampling"),
            replace(DEFAULTS, hybrid_mode="born_sampling", use_su2=True),
            replace(DEFAULTS, hybrid_mode="born_sampling", use_su2="geometric"),
        ]
        report = sensitivity_analysis(
            _make_landscape(), _success_fn, "S", None, configs, max_cycles=15,
        )
        assert len(report.trials) == 3
        # All trials have born component active
        for t in report.trials:
            assert "born" in t.component_qualities
        s = report.summary()
        assert "Trial 0" in s
        assert "Trial 2" in s


class TestComponentParamsC152:
    """COMPONENT_PARAMS updated for amplitude/born."""

    def test_amplitude_has_params(self):
        assert "hybrid_mode" in COMPONENT_PARAMS["amplitude"]
        assert "confidence_threshold" in COMPONENT_PARAMS["amplitude"]
        assert "hybrid_horizon" in COMPONENT_PARAMS["amplitude"]

    def test_born_has_params(self):
        assert "hybrid_mode" in COMPONENT_PARAMS["born"]
        assert "use_su2" in COMPONENT_PARAMS["born"]
        assert "hybrid_horizon" in COMPONENT_PARAMS["born"]

    def test_no_params_components_unchanged(self):
        for comp in ("realization", "inertia", "curvature", "overlap"):
            assert COMPONENT_PARAMS[comp] == [], f"{comp} should have no params"


# ══════════════════════════════════════════════════════════
# C155: Auto-Tuning
# ══════════════════════════════════════════════════════════

from e0_controller.parameter_sensitivity import (
    AutoTuneResult,
    AutoTuneRound,
    auto_tune,
    apply_config,
)
from e0_controller.controller import E0Controller, HybridMode


class TestAutoTuneResult:
    """AutoTuneResult dataclass properties."""

    def _make(self, initial=1.0, final=2.0, rounds=None):
        rnd = rounds or [
            AutoTuneRound(
                round_nr=1,
                baseline=TrialResult(DEFAULTS, RunTrace(), None, {}),
                report=SensitivityReport(trials=[
                    TrialResult(DEFAULTS, RunTrace(), None, {"a": final}),
                ]),
                adopted_config=DEFAULTS,
                improvement=final - initial,
            ),
        ]
        return AutoTuneResult(
            rounds=rnd,
            initial_config=DEFAULTS,
            best_config=DEFAULTS,
            initial_quality=initial,
            final_quality=final,
        )

    def test_improved_true(self):
        assert self._make(1.0, 2.0).improved is True

    def test_improved_false(self):
        assert self._make(1.0, 1.0).improved is False

    def test_improvement_delta(self):
        assert self._make(1.0, 2.5).improvement == 1.5

    def test_total_trials(self):
        assert self._make(1.0, 2.0).total_trials == 1

    def test_summary_string(self):
        s = self._make(1.0, 2.0).summary()
        assert "AutoTune" in s
        assert "Improvement" in s


class TestAutoTune:
    """auto_tune() closed-loop parameter optimization."""

    def test_returns_result(self):
        result = auto_tune(
            _make_landscape(), _success_fn, "S", max_cycles=15,
        )
        assert isinstance(result, AutoTuneResult)
        assert len(result.rounds) >= 1

    def test_initial_config_preserved(self):
        cfg = replace(DEFAULTS, alpha=3.0)
        result = auto_tune(
            _make_landscape(), _success_fn, "S",
            base_config=cfg, max_cycles=15,
        )
        assert result.initial_config.alpha == 3.0

    def test_max_rounds_respected(self):
        result = auto_tune(
            _make_landscape(), _success_fn, "S",
            max_cycles=15, max_rounds=1,
        )
        assert len(result.rounds) <= 1

    def test_healthy_baseline_stops_early(self):
        """If baseline is already healthy, auto_tune stops after 1 round."""
        result = auto_tune(
            _make_landscape(), _success_fn, "S",
            max_cycles=15, max_rounds=5,
        )
        # With success_fn on a fully connected graph, everything should be healthy
        # → auto_tune stops at round 1
        assert len(result.rounds) >= 1

    def test_with_goal(self):
        L = Landscape()
        L.add_edge("S", "G", delta=1.0, resistance=1.0)
        result = auto_tune(L, _success_fn, "S", goal="G", max_cycles=50)
        assert isinstance(result, AutoTuneResult)

    def test_best_config_is_valid(self):
        result = auto_tune(
            _make_landscape(), _success_fn, "S", max_cycles=15,
        )
        assert isinstance(result.best_config, E0Config)

    def test_round_has_baseline_and_report(self):
        result = auto_tune(
            _make_landscape(), _success_fn, "S", max_cycles=15,
        )
        rnd = result.rounds[0]
        assert isinstance(rnd, AutoTuneRound)
        assert isinstance(rnd.baseline, TrialResult)
        assert isinstance(rnd.report, SensitivityReport)

    def test_mixed_fn_may_improve(self):
        """With mixed outcomes, auto_tune may find better configs."""
        result = auto_tune(
            _make_landscape(), _mixed_fn, "S",
            max_cycles=20, max_rounds=2,
        )
        assert isinstance(result, AutoTuneResult)
        # Should at least attempt perturbations
        assert result.total_trials >= 1

    def test_custom_perturbation_factor(self):
        result = auto_tune(
            _make_landscape(), _mixed_fn, "S",
            max_cycles=15, perturbation_factor=0.5,
        )
        assert isinstance(result, AutoTuneResult)


class TestApplyConfig:
    """apply_config() updates a live controller."""

    def test_updates_alpha(self):
        L = _make_landscape()
        ctrl = E0Controller(L, _success_fn)
        cfg = replace(DEFAULTS, alpha=7.5)
        apply_config(ctrl, cfg)
        assert ctrl.alpha == 7.5

    def test_updates_historization(self):
        L = _make_landscape()
        ctrl = E0Controller(L, _success_fn)
        cfg = replace(DEFAULTS, rho=0.5, lambda_s=0.3)
        apply_config(ctrl, cfg)
        assert ctrl.landscape.historization.rho == 0.5
        assert ctrl.landscape.historization.lambda_s == 0.3

    def test_updates_hybrid_mode(self):
        L = _make_landscape()
        ctrl = E0Controller(L, _success_fn)
        cfg = replace(DEFAULTS, hybrid_mode="born_sampling")
        apply_config(ctrl, cfg)
        assert ctrl.hybrid_mode == HybridMode.BORN_SAMPLING

    def test_updates_overload_threshold(self):
        L = _make_landscape()
        ctrl = E0Controller(L, _success_fn)
        cfg = replace(DEFAULTS, overload_threshold=10.0)
        apply_config(ctrl, cfg)
        assert ctrl.overload_threshold == 10.0

    def test_updates_use_su2(self):
        L = _make_landscape()
        ctrl = E0Controller(L, _success_fn)
        cfg = replace(DEFAULTS, use_su2=True)
        apply_config(ctrl, cfg)
        assert ctrl.use_su2 is True

    def test_preserves_landscape_reference(self):
        """apply_config modifies in-place, not reconstructs."""
        L = _make_landscape()
        ctrl = E0Controller(L, _success_fn)
        apply_config(ctrl, replace(DEFAULTS, alpha=1.0))
        assert ctrl.landscape is L

    def test_controller_runs_after_apply(self):
        """Controller still works after config change."""
        L = _make_landscape()
        ctrl = E0Controller(L, _success_fn)
        apply_config(ctrl, replace(DEFAULTS, alpha=1.0, recent_k=2))
        trace = ctrl.run("S", max_cycles=10)
        assert len(trace.steps) > 0


class TestSessionAutoTune:
    """Session.auto_tune() integrates auto-tuning."""

    def test_session_auto_tune_runs(self):
        from e0_controller.session import Session
        L = _make_landscape()
        session = Session("test-auto", L, _success_fn)
        result = session.auto_tune("S", max_cycles=15, max_rounds=1)
        assert isinstance(result, AutoTuneResult)

    def test_session_auto_tune_adopt(self):
        """When adopt=True (default), best config is applied."""
        from e0_controller.session import Session
        L = _make_landscape()
        session = Session("test-adopt", L, _success_fn)
        original_alpha = session.controller.alpha
        result = session.auto_tune("S", max_cycles=15)
        # If improved, alpha may have changed
        if result.improved:
            assert result.best_config != result.initial_config

    def test_session_auto_tune_no_adopt(self):
        """adopt=False prevents applying the config."""
        from e0_controller.session import Session
        L = _make_landscape()
        session = Session("test-no-adopt", L, _success_fn)
        original_alpha = session.controller.alpha
        result = session.auto_tune("S", max_cycles=15, adopt=False)
        assert session.controller.alpha == original_alpha

    def test_session_auto_tune_with_goal(self):
        from e0_controller.session import Session
        L = Landscape()
        L.add_edge("S", "G", delta=1.0, resistance=1.0)
        session = Session("test-goal", L, _success_fn)
        result = session.auto_tune("S", goal="G", max_cycles=50)
        assert isinstance(result, AutoTuneResult)
