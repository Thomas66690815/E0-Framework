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
        diag = SelfGraphDiagnosis(harmful=["amplitude"])
        assert suggest_perturbations(diag) == []

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
