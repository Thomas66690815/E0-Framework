"""Tests for demo_self_graph.py — Self-Graph Demo (C147)."""

from __future__ import annotations

import pytest

from e0_controller.primitives import Outcome
from e0_controller.self_graph import (
    SelfGraph, active_components,
    CORE_COMPONENTS, MODULATION_COMPONENTS,
    ALL_COMPONENTS, CORE_EDGES, MODULATION_EDGES,
)
from e0_controller.dual_reflection import diagnose_self_graph
from e0_controller.reflexive_action import apply_reflexive_actions
from e0_controller.dual_reflection import DualReflectionReport
from e0_controller.controller import E0Controller
from e0_controller.demo_self_graph import (
    build_approval_domain,
    _execute_approval,
    run_demo,
)


# ── Structure ────────────────────────────────────────────────────

class TestSelfGraphStructure:
    def test_component_counts(self):
        assert len(CORE_COMPONENTS) == 6
        assert len(MODULATION_COMPONENTS) == 2
        assert len(ALL_COMPONENTS) == 8

    def test_edge_counts(self):
        assert len(CORE_EDGES) == 6
        assert len(MODULATION_EDGES) == 2

    def test_active_components_core_only(self):
        comps = active_components(overlap_active=False)
        # In default (GREEDY) mode, amplitude/born not active
        assert "realization" in comps
        assert "historization" in comps
        assert "transition_field" in comps
        assert "inertia" in comps
        assert "amplitude" in comps  # default: amplitude_active=True
        assert "born" in comps        # default: born_active=True

    def test_active_components_with_overlap(self):
        comps = active_components(overlap_active=True)
        assert "overlap" in comps
        for c in ["realization", "historization", "transition_field", "inertia"]:
            assert c in comps


# ── Domain ───────────────────────────────────────────────────────

class TestApprovalDomain:
    def test_domain_has_5_edges(self):
        L = build_approval_domain()
        assert L.edge_count() == 5

    def test_domain_states(self):
        L = build_approval_domain()
        expected = {"SUBMIT", "REVIEW", "EVALUATE", "RECOMMEND",
                    "APPROVED", "DONE"}
        assert set(L.states) == expected

    def test_execute_always_succeeds(self):
        assert _execute_approval("SUBMIT", "REVIEW") == Outcome.SUCCESS
        assert _execute_approval("REVIEW", "EVALUATE") == Outcome.SUCCESS

    def test_controller_reaches_done(self):
        L = build_approval_domain()
        ctrl = E0Controller(L, _execute_approval, alpha=2.0, recent_k=3)
        trace = ctrl.run("SUBMIT", max_cycles=20, goal="DONE")
        assert "DONE" in trace.path


# ── Mechanism: Differential Sampling ─────────────────────────────

class TestMechanism:
    def test_core_only_success_quality_positive(self):
        sg = SelfGraph()
        comps = active_components(overlap_active=False)
        for _ in range(20):
            sg.self_historize(comps, Outcome.SUCCESS)
        assert sg.component_quality("amplitude") == pytest.approx(1.0)
        assert sg.component_load("overlap") == 0.0

    def test_overlap_only_failure_quality_negative(self):
        sg = SelfGraph()
        core = active_components(overlap_active=False)
        both = active_components(overlap_active=True)
        # 20 success core-only
        for _ in range(20):
            sg.self_historize(core, Outcome.SUCCESS)
        # 10 failure with overlap
        for _ in range(10):
            sg.self_historize(both, Outcome.FAILURE)
        assert sg.component_quality("overlap") == pytest.approx(-1.0)
        assert sg.component_quality("amplitude") > 0

    def test_core_recovers_after_failures(self):
        sg = SelfGraph()
        core = active_components(overlap_active=False)
        both = active_components(overlap_active=True)
        for _ in range(20):
            sg.self_historize(core, Outcome.SUCCESS)
        for _ in range(10):
            sg.self_historize(both, Outcome.FAILURE)
        q_before = sg.component_quality("amplitude")
        for _ in range(10):
            sg.self_historize(core, Outcome.SUCCESS)
        q_after = sg.component_quality("amplitude")
        assert q_after > q_before

    def test_overlap_quality_unchanged_by_core_only(self):
        sg = SelfGraph()
        core = active_components(overlap_active=False)
        both = active_components(overlap_active=True)
        for _ in range(20):
            sg.self_historize(core, Outcome.SUCCESS)
        for _ in range(10):
            sg.self_historize(both, Outcome.FAILURE)
        q_overlap = sg.component_quality("overlap")
        # 10 more core-only successes — overlap untouched
        for _ in range(10):
            sg.self_historize(core, Outcome.SUCCESS)
        assert sg.component_quality("overlap") == pytest.approx(q_overlap)


# ── Diagnosis ────────────────────────────────────────────────────

class TestDiagnosis:
    @pytest.fixture
    def sg_with_harmful_overlap(self):
        sg = SelfGraph()
        core = active_components(overlap_active=False)
        both = active_components(overlap_active=True)
        for _ in range(20):
            sg.self_historize(core, Outcome.SUCCESS)
        for _ in range(10):
            sg.self_historize(both, Outcome.FAILURE)
        for _ in range(10):
            sg.self_historize(core, Outcome.SUCCESS)
        return sg

    def test_overlap_classified_harmful(self, sg_with_harmful_overlap):
        diag = diagnose_self_graph(sg_with_harmful_overlap)
        assert "overlap" in diag.harmful

    def test_core_classified_healthy(self, sg_with_harmful_overlap):
        diag = diagnose_self_graph(sg_with_harmful_overlap)
        for c in CORE_COMPONENTS:
            assert c in diag.healthy

    def test_curvature_insufficient_data(self, sg_with_harmful_overlap):
        diag = diagnose_self_graph(sg_with_harmful_overlap)
        assert "curvature" in diag.insufficient_data

    def test_deactivation_candidate_is_overlap(self, sg_with_harmful_overlap):
        diag = diagnose_self_graph(sg_with_harmful_overlap)
        assert diag.deactivation_candidates == ["overlap"]


# ── Reflexive Action ─────────────────────────────────────────────

class TestReflexiveAction:
    def test_overlap_deactivated(self):
        sg = SelfGraph()
        core = active_components(overlap_active=False)
        both = active_components(overlap_active=True)
        for _ in range(20):
            sg.self_historize(core, Outcome.SUCCESS)
        for _ in range(10):
            sg.self_historize(both, Outcome.FAILURE)
        diag = diagnose_self_graph(sg)
        L = build_approval_domain()
        L.overlap_modulation = True
        report = DualReflectionReport(
            domain_report=None,
            self_diagnosis=diag,
            meta_actions=list(diag.meta_actions),
        )
        result = apply_reflexive_actions(report, L)
        assert result.any_changes
        assert L.overlap_modulation is False


# ── End-to-End Controller ────────────────────────────────────────

class TestEndToEnd:
    def test_self_graph_accumulates_via_controller(self):
        sg = SelfGraph()
        L = build_approval_domain()
        L.overlap_modulation = True
        for _ in range(5):
            ctrl = E0Controller(L, _execute_approval, alpha=2.0, recent_k=3)
            ctrl.self_graph = sg
            ctrl.run("SUBMIT", max_cycles=20, goal="DONE")
        # Always-active components accumulate in GREEDY mode
        assert sg.component_load("transition_field") > 0
        assert sg.component_load("overlap") > 0
        assert sg.component_quality("transition_field") == pytest.approx(1.0)
        # amplitude/born stay at zero in GREEDY mode (C151)
        assert sg.component_load("amplitude") == 0
        assert sg.component_load("born") == 0

    def test_all_healthy_when_all_succeed(self):
        sg = SelfGraph()
        L = build_approval_domain()
        for _ in range(10):
            ctrl = E0Controller(L, _execute_approval, alpha=2.0, recent_k=3)
            ctrl.self_graph = sg
            ctrl.run("SUBMIT", max_cycles=20, goal="DONE")
        diag = diagnose_self_graph(sg)
        # Always-active components should be healthy
        from e0_controller.self_graph import ALWAYS_ACTIVE_COMPONENTS
        for c in ALWAYS_ACTIVE_COMPONENTS:
            assert c in diag.healthy
        # amplitude/born should be insufficient_data in GREEDY mode
        assert "amplitude" in diag.insufficient_data
        assert "born" in diag.insufficient_data


# ── Full Demo ────────────────────────────────────────────────────

class TestRunDemo:
    def test_demo_returns_results(self, capsys):
        result = run_demo(use_entropy=False)
        assert result["overlap_harmful"] is True
        assert result["overlap_quality"] == pytest.approx(-1.0)
        assert result["core_quality"] > 0
        assert result["has_deactivation"] is True
        assert len(result["convergence"]) == 30

    def test_demo_convergence_quality(self, capsys):
        result = run_demo(use_entropy=False)
        final = result["convergence"][-1]
        assert final["core_q"] == pytest.approx(1.0)
