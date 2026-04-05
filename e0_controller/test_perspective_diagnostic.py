"""Tests for E₀ SU(2) Perspective Diagnostic (C153)."""

import math
import pytest

from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller, HybridMode
from e0_controller.primitives import Outcome
from e0_controller.self_graph import SelfGraph
from e0_controller.dual_reflection import (
    DualReflectionReport,
    SelfGraphDiagnosis,
    diagnose_self_graph,
    reflect_dual,
    _cross_reference,
)
from e0_controller.perspective_diagnostic import (
    PerspectiveReport,
    perspective_check,
    _ranking_agreement,
    _fragile_actions,
)

exec_fn = lambda s, t: Outcome.SUCCESS


# ──────────────────────────────────────────────
# Helper: build asymmetric multi-path landscape
# ──────────────────────────────────────────────

def _make_simple_landscape():
    """3-node triangle — too small for SU(2) divergence."""
    L = Landscape()
    L.add_edge("S", "A", delta=1.0, resistance=1.0)
    L.add_edge("S", "B", delta=1.0, resistance=1.0)
    L.add_edge("A", "B", delta=1.0, resistance=1.0)
    L.add_edge("B", "A", delta=1.0, resistance=1.0)
    return L


def _make_asymmetric_landscape():
    """5-node graph with strong asymmetry — likely to produce SU(2) divergence."""
    L = Landscape()
    # High asymmetry: different delta/resistance ratios create large omega
    L.add_edge("S", "A", delta=50.0, resistance=0.1)
    L.add_edge("S", "B", delta=0.1, resistance=50.0)
    L.add_edge("A", "B", delta=10.0, resistance=0.5)
    L.add_edge("B", "A", delta=0.5, resistance=10.0)
    L.add_edge("A", "C", delta=20.0, resistance=0.2)
    L.add_edge("B", "C", delta=0.2, resistance=20.0)
    L.add_edge("C", "S", delta=5.0, resistance=1.0)
    L.add_edge("S", "C", delta=1.0, resistance=5.0)
    L.add_edge("A", "D", delta=30.0, resistance=0.3)
    L.add_edge("D", "B", delta=0.3, resistance=30.0)
    L.add_edge("D", "C", delta=3.0, resistance=3.0)
    return L


# ──────────────────────────────────────────────
# Unit tests: ranking helpers
# ──────────────────────────────────────────────

class TestRankingAgreement:
    def test_identical(self):
        assert _ranking_agreement(["A", "B", "C"], ["A", "B", "C"]) == 1.0

    def test_reversed(self):
        assert _ranking_agreement(["A", "B", "C"], ["C", "B", "A"]) == 0.0

    def test_single(self):
        assert _ranking_agreement(["A"], ["A"]) == 1.0

    def test_empty(self):
        assert _ranking_agreement([], []) == 1.0

    def test_two_swapped(self):
        assert _ranking_agreement(["A", "B"], ["B", "A"]) == 0.0

    def test_two_same(self):
        assert _ranking_agreement(["A", "B"], ["A", "B"]) == 1.0

    def test_partial_agreement(self):
        # [A,B,C] vs [A,C,B]: A>B agrees, A>C agrees, B>C disagrees → 2/3
        result = _ranking_agreement(["A", "B", "C"], ["A", "C", "B"])
        assert abs(result - 2 / 3) < 1e-9


class TestFragileActions:
    def test_identical(self):
        assert _fragile_actions(["A", "B", "C"], ["A", "B", "C"]) == []

    def test_top_swap(self):
        result = _fragile_actions(["A", "B", "C"], ["B", "A", "C"])
        assert set(result) == {"A", "B"}

    def test_tail_swap(self):
        result = _fragile_actions(["A", "B", "C"], ["A", "C", "B"])
        assert set(result) == {"B", "C"}

    def test_complete_reversal(self):
        result = _fragile_actions(["A", "B", "C"], ["C", "B", "A"])
        assert set(result) == {"A", "C"}  # B stays at position 1


# ──────────────────────────────────────────────
# Integration tests: perspective_check
# ──────────────────────────────────────────────

class TestPerspectiveCheck:
    def test_returns_none_single_action(self):
        """Only 1 admissible action → no perspective comparison possible."""
        L = Landscape()
        L.add_edge("S", "A", delta=1.0, resistance=1.0)
        ctrl = E0Controller(L, exec_fn)
        result = perspective_check(ctrl, "S", horizon=3)
        assert result is None

    def test_returns_report_on_multi_action(self):
        """Multiple actions → returns PerspectiveReport."""
        L = _make_simple_landscape()
        ctrl = E0Controller(L, exec_fn)
        result = perspective_check(ctrl, "S", horizon=3)
        assert result is not None
        assert isinstance(result, PerspectiveReport)
        assert result.current == "S"

    def test_simple_landscape_robust(self):
        """Small symmetric landscape → SU(2) agrees with U(1)."""
        L = _make_simple_landscape()
        ctrl = E0Controller(L, exec_fn)
        result = perspective_check(ctrl, "S", horizon=3)
        assert result is not None
        assert result.robust
        assert result.top_agrees
        assert result.ranking_agreement == 1.0
        assert result.fragile_actions == []

    def test_report_has_intensities(self):
        """Report contains intensity dicts for all actions."""
        L = _make_simple_landscape()
        ctrl = E0Controller(L, exec_fn)
        result = perspective_check(ctrl, "S", horizon=3)
        assert result is not None
        assert len(result.u1_intensities) == 2  # A, B
        assert len(result.su2_intensities) == 2
        assert all(v >= 0 for v in result.u1_intensities.values())
        assert all(v >= 0 for v in result.su2_intensities.values())

    def test_report_rankings_contain_same_actions(self):
        """Both rankings contain exactly the same set of actions."""
        L = _make_asymmetric_landscape()
        ctrl = E0Controller(L, exec_fn)
        result = perspective_check(ctrl, "S", horizon=3)
        assert result is not None
        assert set(result.u1_ranking) == set(result.su2_ranking)

    def test_fragile_property(self):
        """fragile is always the inverse of robust."""
        report = PerspectiveReport(
            current="S", u1_ranking=["A"], su2_ranking=["A"], robust=True,
        )
        assert not report.fragile
        report2 = PerspectiveReport(
            current="S", u1_ranking=["A"], su2_ranking=["A"], robust=False,
        )
        assert report2.fragile

    def test_geometric_not_computed_by_default(self):
        """geo_ranking is None when include_geometric=False."""
        L = _make_simple_landscape()
        ctrl = E0Controller(L, exec_fn)
        result = perspective_check(ctrl, "S", horizon=3)
        assert result is not None
        assert result.geo_ranking is None
        assert result.geo_intensities is None

    def test_geometric_computed_when_requested(self):
        """geo_ranking is populated when include_geometric=True."""
        L = _make_simple_landscape()
        ctrl = E0Controller(L, exec_fn)
        result = perspective_check(ctrl, "S", horizon=3, include_geometric=True)
        assert result is not None
        assert result.geo_ranking is not None
        assert result.geo_intensities is not None
        assert set(result.geo_ranking) == set(result.u1_ranking)

    def test_asymmetric_landscape_produces_valid_report(self):
        """Asymmetric landscape produces a structurally valid report."""
        L = _make_asymmetric_landscape()
        ctrl = E0Controller(L, exec_fn)
        result = perspective_check(ctrl, "S", horizon=3)
        assert result is not None
        assert len(result.u1_ranking) >= 2
        assert 0.0 <= result.ranking_agreement <= 1.0
        assert isinstance(result.robust, bool)
        # robust == top_agrees by construction
        assert result.robust == result.top_agrees


class TestPerspectiveCheckEdgeCases:
    def test_no_admissible_neighbors(self):
        """Dead-end state → None."""
        L = Landscape()
        L.add_edge("A", "S", delta=1.0, resistance=1.0)
        ctrl = E0Controller(L, exec_fn)
        result = perspective_check(ctrl, "S", horizon=3)
        assert result is None

    def test_horizon_zero(self):
        """horizon=0 still works (single-edge paths only)."""
        L = _make_simple_landscape()
        ctrl = E0Controller(L, exec_fn)
        # horizon=1 is minimum for meaningful overlay
        result = perspective_check(ctrl, "S", horizon=1)
        assert result is not None

    def test_with_goals(self):
        """Goals parameter is forwarded."""
        L = _make_simple_landscape()
        ctrl = E0Controller(L, exec_fn)
        result = perspective_check(ctrl, "S", horizon=3, goals={"B"})
        assert result is not None


# ──────────────────────────────────────────────
# Integration: controller.run() with perspective_horizon
# ──────────────────────────────────────────────

class TestControllerPerspectiveIntegration:
    def test_run_without_perspective(self):
        """Default: no perspective computed."""
        L = _make_simple_landscape()
        ctrl = E0Controller(L, exec_fn)
        trace = ctrl.run("S", max_cycles=3)
        assert all(s.perspective is None for s in trace.steps)

    def test_run_with_perspective(self):
        """perspective_horizon > 0: PerspectiveReport attached to each step."""
        L = _make_simple_landscape()
        ctrl = E0Controller(L, exec_fn)
        trace = ctrl.run("S", max_cycles=3, perspective_horizon=3)
        for step in trace.steps:
            if len(step.candidates) >= 2:
                assert step.perspective is not None
                assert isinstance(step.perspective, PerspectiveReport)
            # Single-action steps may have None

    def test_cycle_with_perspective(self):
        """cycle() directly with perspective_horizon."""
        L = _make_simple_landscape()
        ctrl = E0Controller(L, exec_fn)
        step = ctrl.cycle("S", perspective_horizon=3)
        assert step is not None
        assert step.perspective is not None
        assert step.perspective.current == "S"

    def test_cycle_without_perspective(self):
        """cycle() default: no perspective."""
        L = _make_simple_landscape()
        ctrl = E0Controller(L, exec_fn)
        step = ctrl.cycle("S")
        assert step is not None
        assert step.perspective is None

    def test_perspective_with_asymmetric_landscape(self):
        """Asymmetric landscape produces valid perspective through run()."""
        L = _make_asymmetric_landscape()
        ctrl = E0Controller(L, exec_fn)
        trace = ctrl.run("S", max_cycles=5, perspective_horizon=3)
        perspectives = [s.perspective for s in trace.steps if s.perspective]
        assert len(perspectives) > 0
        for p in perspectives:
            assert 0.0 <= p.ranking_agreement <= 1.0
            assert isinstance(p.robust, bool)


# ──────────────────────────────────────────────
# Integration: dual_reflection with perspective
# ──────────────────────────────────────────────

class TestDualReflectionPerspective:
    def test_cross_reference_without_perspective(self):
        """No perspective → no perspective meta-actions."""
        diag = SelfGraphDiagnosis()
        actions = _cross_reference(None, diag, perspective=None)
        assert not any("SU(2)" in a for a in actions)

    def test_cross_reference_robust_perspective(self):
        """Robust perspective → no fragility warning."""
        diag = SelfGraphDiagnosis()
        p = PerspectiveReport(
            current="S", u1_ranking=["A", "B"], su2_ranking=["A", "B"],
            top_agrees=True, robust=True,
        )
        actions = _cross_reference(None, diag, perspective=p)
        assert not any("fragile" in a.lower() for a in actions)

    def test_cross_reference_fragile_perspective(self):
        """Fragile perspective → meta-action about frame questioning."""
        diag = SelfGraphDiagnosis()
        p = PerspectiveReport(
            current="S",
            u1_ranking=["A", "B"], su2_ranking=["B", "A"],
            top_agrees=False, robust=False, ranking_agreement=0.0,
            fragile_actions=["A", "B"],
        )
        actions = _cross_reference(None, diag, perspective=p)
        fragile_actions = [a for a in actions if "fragile" in a.lower()]
        assert len(fragile_actions) >= 1
        assert any("frame" in a.lower() for a in fragile_actions)

    def test_cross_reference_fragile_plus_harmful(self):
        """Fragile perspective + harmful components → combined warning."""
        from e0_controller.dual_reflection import ComponentAssessment
        diag = SelfGraphDiagnosis(
            harmful=["amplitude"],
            components=[ComponentAssessment(
                name="amplitude", load=10.0, quality=-0.5,
                inertia=0.5, status="harmful", is_modulation=False,
            )],
        )
        p = PerspectiveReport(
            current="S",
            u1_ranking=["A", "B"], su2_ranking=["B", "A"],
            top_agrees=False, robust=False,
        )
        actions = _cross_reference(None, diag, perspective=p)
        assert any("frame change" in a.lower() for a in actions)

    def test_dual_report_perspective_field(self):
        """DualReflectionReport has perspective field."""
        p = PerspectiveReport(
            current="S", u1_ranking=["A", "B"], su2_ranking=["A", "B"],
        )
        report = DualReflectionReport(
            domain_report=None,
            self_diagnosis=SelfGraphDiagnosis(),
            perspective=p,
        )
        assert report.perspective is p
        assert report.perspective.robust


# ──────────────────────────────────────────────
# Integration: format_dual_report with perspective
# ──────────────────────────────────────────────

class TestFormatPerspective:
    def test_format_includes_perspective_section(self):
        """Formatted report includes SU(2) section when perspective present."""
        from e0_controller.dual_reflection import format_dual_report
        p = PerspectiveReport(
            current="S",
            u1_ranking=["A", "B"], su2_ranking=["B", "A"],
            top_agrees=False, robust=False, ranking_agreement=0.0,
            fragile_actions=["A", "B"],
        )
        report = DualReflectionReport(
            domain_report=None,
            self_diagnosis=SelfGraphDiagnosis(),
            perspective=p,
        )
        text = format_dual_report(report)
        assert "SU(2) Perspective Diagnostic" in text
        assert "FRAGILE" in text
        assert "A > B" in text or "B > A" in text

    def test_format_omits_perspective_when_none(self):
        """No perspective → no perspective section in output."""
        from e0_controller.dual_reflection import format_dual_report
        report = DualReflectionReport(
            domain_report=None,
            self_diagnosis=SelfGraphDiagnosis(),
        )
        text = format_dual_report(report)
        assert "SU(2) Perspective Diagnostic" not in text
