"""
Tests for C209: Evidence Interpreter.

Template-based prose generation from structured evidence dicts.

Test structure:
    TestInterpretTrace          — trace metrics → assessment
    TestInscriptionSummary      — edge-level inscription narrative
    TestInscriptionStats        — global inscription overview
    TestDomainCrossings         — crossing counts → narrative
    TestEvidenceDispatch        — signature-based type detection
    TestUncertaintyEvidence     — harmful/confused/insufficient
    TestDecisionEvidence        — navigation decisions
    TestPatternEvidence         — resistance drop
    TestSelfGraphEvidence       — component health
    TestTaskEvidence            — task landscape progress
    TestDeadEndEvidence         — dead-end request
    TestDreamEvidence           — dream equivalence
    TestGenericEvidence         — unrecognized evidence
    TestInterpretPanel          — full panel interpretation
    TestEndToEnd                — real pipeline integration
"""

import pytest
from e0_controller.evidence_interpreter import (
    interpret_trace,
    interpret_inscription_summary,
    interpret_inscription_stats,
    interpret_domain_crossings,
    interpret_evidence,
    interpret_panel,
    _interpret_uncertainty,
    _interpret_decision,
    _interpret_pattern,
    _interpret_status_self_graph,
    _interpret_status_task,
    _interpret_request_deadend,
    _interpret_dream,
    _interpret_generic,
)


# ── Trace Metrics ──────────────────────────────────────────────────────


class TestInterpretTrace:
    """Trace quality/load/inertia → prose."""

    def test_strong_confirmed(self):
        result = interpret_trace(quality=0.7, load=20.0)
        assert "strongly confirmed" in result
        assert "well-traveled" in result

    def test_ambiguous(self):
        result = interpret_trace(quality=0.0, load=3.0)
        assert "ambiguous" in result

    def test_strongly_contradicted(self):
        result = interpret_trace(quality=-0.8, load=10.0)
        assert "strongly contradicted" in result

    def test_barely_visited(self):
        result = interpret_trace(quality=0.3, load=1.0)
        assert "barely visited" in result

    def test_heavily_traversed(self):
        result = interpret_trace(quality=0.1, load=50.0)
        assert "heavily traversed" in result

    def test_high_inertia(self):
        result = interpret_trace(quality=0.5, load=10.0, inertia=0.9)
        assert "High inertia" in result

    def test_low_inertia(self):
        result = interpret_trace(quality=0.5, load=10.0, inertia=0.2)
        assert "malleable" in result

    def test_no_inertia(self):
        result = interpret_trace(quality=0.5, load=10.0)
        assert "inertia" not in result.lower() or "load" in result

    def test_moderate_inertia(self):
        result = interpret_trace(quality=0.5, load=10.0, inertia=0.5)
        assert "Moderate inertia" in result

    def test_leaning_problematic(self):
        result = interpret_trace(quality=-0.3, load=8.0)
        assert "problematic" in result


# ── Inscription Summary ────────────────────────────────────────────────


class TestInscriptionSummary:
    """Edge-level inscription narrative."""

    def test_no_traversals(self):
        result = interpret_inscription_summary({"count": 0})
        assert "no recorded traversals" in result

    def test_with_edge_label(self):
        result = interpret_inscription_summary({"count": 0}, edge_label="A→B")
        assert "A→B" in result

    def test_single_traversal(self):
        summary = {
            "count": 1,
            "modes": {"explore_en": 1},
            "roles": {"bridge": 1},
            "success_rate": 1.0,
            "domain_pairs": {},
            "last_tau": 42,
        }
        result = interpret_inscription_summary(summary)
        assert "1 time" in result
        assert "explore_en" in result
        assert "100%" in result

    def test_multiple_traversals(self):
        summary = {
            "count": 15,
            "modes": {"explore_canon": 10, "explore_en": 5},
            "roles": {"bridge": 8, "exploration": 5, "revisit": 2},
            "success_rate": 0.73,
            "domain_pairs": {"Canon→EN": 6, "EN→Canon": 2},
            "last_tau": 150,
        }
        result = interpret_inscription_summary(summary)
        assert "15 times" in result
        assert "explore_canon" in result
        assert "bridge" in result
        assert "73%" in result
        assert "Domain crossings" in result

    def test_low_success_rate(self):
        summary = {
            "count": 5,
            "modes": {"greedy": 5},
            "roles": {"exploration": 5},
            "success_rate": 0.15,
            "domain_pairs": {},
            "last_tau": 20,
        }
        result = interpret_inscription_summary(summary)
        assert "very low success rate" in result

    def test_high_success_rate(self):
        summary = {
            "count": 10,
            "modes": {"greedy": 10},
            "roles": {"bridge": 10},
            "success_rate": 0.9,
            "domain_pairs": {},
            "last_tau": 100,
        }
        result = interpret_inscription_summary(summary)
        assert "high success rate" in result


# ── Inscription Stats ──────────────────────────────────────────────────


class TestInscriptionStats:
    """Global inscription overview narrative."""

    def test_no_inscriptions(self):
        result = interpret_inscription_stats({"total_inscriptions": 0})
        assert "No inscriptions" in result

    def test_basic_stats(self):
        stats = {
            "total_inscriptions": 176,
            "inscribed_edges": 140,
            "domain_crossing_count": 95,
            "role_totals": {"bridge": 129, "exploration": 45, "revisit": 2},
            "mode_totals": {"explore_canon": 80, "explore_en": 60, "greedy": 36},
        }
        result = interpret_inscription_stats(stats)
        assert "176 inscriptions" in result
        assert "140 edges" in result
        assert "95" in result
        assert "bridge" in result
        assert "explore_canon" in result
        assert "exploration" in result

    def test_single_inscription(self):
        stats = {
            "total_inscriptions": 1,
            "inscribed_edges": 1,
            "domain_crossing_count": 0,
            "role_totals": {"bridge": 1},
            "mode_totals": {"greedy": 1},
        }
        result = interpret_inscription_stats(stats)
        assert "1 inscription " in result
        assert "1 edge" in result

    def test_no_crossings(self):
        stats = {
            "total_inscriptions": 20,
            "inscribed_edges": 15,
            "domain_crossing_count": 0,
            "role_totals": {"exploration": 20},
            "mode_totals": {"greedy": 20},
        }
        result = interpret_inscription_stats(stats)
        assert "crossing" not in result.lower()


# ── Domain Crossings ──────────────────────────────────────────────────


class TestDomainCrossings:
    """Domain crossing narrative."""

    def test_no_crossings(self):
        result = interpret_domain_crossings({})
        assert "No domain crossings" in result

    def test_single_axis(self):
        result = interpret_domain_crossings({"EN↔Canon": 50})
        assert "50" in result
        assert "EN↔Canon" in result

    def test_multiple_axes(self):
        crossings = {"EN↔Canon": 104, "EN↔Bootstrap": 55, "Canon↔Bootstrap": 37}
        result = interpret_domain_crossings(crossings, total_steps=400)
        assert "196" in result  # total
        assert "49%" in result  # 196/400
        assert "EN↔Canon" in result

    def test_dominant_axis(self):
        crossings = {"EN↔Canon": 100, "EN↔Bootstrap": 20}
        result = interpret_domain_crossings(crossings)
        assert "dominates" in result

    def test_balanced_axes(self):
        crossings = {"EN↔Canon": 50, "EN↔Bootstrap": 45}
        result = interpret_domain_crossings(crossings)
        assert "dominates" not in result


# ── Evidence Dispatch ──────────────────────────────────────────────────


class TestEvidenceDispatch:
    """Signature-based type detection."""

    def test_empty_evidence(self):
        assert "No evidence" in interpret_evidence({})

    def test_uncertainty_routed(self):
        evidence = {"status": "harmful", "quality": -0.5, "load": 10.0}
        result = interpret_evidence(evidence)
        assert "harmful" in result

    def test_decision_routed(self):
        evidence = {"source": "A", "target": "B", "outcome": "SUCCESS"}
        result = interpret_evidence(evidence)
        assert "A" in result and "B" in result

    def test_pattern_routed(self):
        evidence = {"r_eff_before": 0.8, "r_eff_after": 0.3, "drop_pct": 0.625}
        result = interpret_evidence(evidence)
        assert "dropped" in result

    def test_self_graph_routed(self):
        evidence = {"healthy": ["x"], "confused": ["y"]}
        result = interpret_evidence(evidence)
        assert "Self-graph" in result

    def test_task_routed(self):
        evidence = {"task": "T", "goal_reached": True, "states": [], "edge_count": 0, "steps": 1, "success_rate": 1.0, "avg_tension": 0.1}
        result = interpret_evidence(evidence)
        assert "Goal reached" in result

    def test_deadend_routed(self):
        evidence = {"state": "X", "admissible_neighbors": [], "goal": "Y"}
        result = interpret_evidence(evidence)
        assert "Dead end" in result

    def test_dream_routed(self):
        evidence = {"own_state": "A", "partner_state": "B", "trace_quality": 0.5}
        result = interpret_evidence(evidence)
        assert "equivalence" in result

    def test_generic_fallback(self):
        evidence = {"custom_field": 42, "other": "val"}
        result = interpret_evidence(evidence)
        assert "Evidence:" in result
        assert "custom_field" in result

    def test_context_param_accepted(self):
        """context parameter is accepted (future use)."""
        result = interpret_evidence({"x": 1}, context="navigation")
        assert len(result) > 0


# ── Uncertainty Evidence ───────────────────────────────────────────────


class TestUncertaintyEvidence:
    """Harmful/confused/insufficient_data."""

    def test_harmful(self):
        evidence = {"status": "harmful", "quality": -0.7, "load": 15.2}
        result = _interpret_uncertainty(evidence)
        assert "harmful" in result
        assert "-0.700" in result

    def test_confused(self):
        evidence = {"status": "confused", "quality": -0.1, "load": 8.0}
        result = _interpret_uncertainty(evidence)
        assert "confusion" in result

    def test_insufficient(self):
        evidence = {"status": "insufficient_data", "load": 1.5}
        result = _interpret_uncertainty(evidence)
        assert "Insufficient" in result

    def test_unknown_status(self):
        evidence = {"status": "novel", "quality": 0.0, "load": 0.0}
        result = _interpret_uncertainty(evidence)
        assert "novel" in result


# ── Decision Evidence ──────────────────────────────────────────────────


class TestDecisionEvidence:
    """Navigation decision narratives."""

    def test_basic_decision(self):
        evidence = {"source": "A", "target": "B", "outcome": "SUCCESS", "s_eff": 0.3}
        result = _interpret_decision(evidence)
        assert "A → B" in result
        assert "SUCCESS" in result

    def test_high_tension(self):
        evidence = {"source": "A", "target": "B", "outcome": "SUCCESS", "s_eff": 0.7}
        result = _interpret_decision(evidence)
        assert "High effective tension" in result

    def test_with_rejected(self):
        evidence = {"source": "A", "target": "B", "outcome": "FAILURE",
                     "s_eff": 0.2, "rejected": ["C", "D"]}
        result = _interpret_decision(evidence)
        assert "Rejected 2 alternatives" in result
        assert "C" in result

    def test_multiple_candidates(self):
        evidence = {"source": "A", "target": "B", "outcome": "SUCCESS",
                     "s_eff": 0.4, "candidates": ["B", "C", "D"]}
        result = _interpret_decision(evidence)
        assert "3 candidates" in result


# ── Pattern Evidence ───────────────────────────────────────────────────


class TestPatternEvidence:
    """Resistance drop patterns."""

    def test_dramatic_drop(self):
        evidence = {"r_eff_before": 0.9, "r_eff_after": 0.2, "drop_pct": 0.78}
        result = _interpret_pattern(evidence)
        assert "dramatic" in result
        assert "0.900" in result
        assert "\u221278.0%" in result

    def test_significant_drop(self):
        evidence = {"r_eff_before": 0.8, "r_eff_after": 0.6, "drop_pct": 0.25}
        result = _interpret_pattern(evidence)
        assert "significant" in result

    def test_moderate_drop(self):
        evidence = {"r_eff_before": 0.5, "r_eff_after": 0.45, "drop_pct": 0.10}
        result = _interpret_pattern(evidence)
        assert "moderate" in result

    def test_minor_drop(self):
        evidence = {"r_eff_before": 0.5, "r_eff_after": 0.48, "drop_pct": 0.04}
        result = _interpret_pattern(evidence)
        assert "minor" in result


# ── Self-Graph Evidence ────────────────────────────────────────────────


class TestSelfGraphEvidence:
    """Component health assessment."""

    def test_all_healthy(self):
        evidence = {"healthy": ["a", "b", "c"], "confused": [], "harmful": []}
        result = _interpret_status_self_graph(evidence)
        assert "3 components" in result
        assert "Healthy: 3" in result

    def test_mixed(self):
        evidence = {
            "healthy": ["a"],
            "confused": ["b", "c"],
            "harmful": ["d"],
            "insufficient_data": ["e"],
            "meta_actions": ["retrain_b"],
        }
        result = _interpret_status_self_graph(evidence)
        assert "5 components" in result
        assert "Confused: 2" in result
        assert "Harmful: 1" in result
        assert "retrain_b" in result


# ── Task Evidence ──────────────────────────────────────────────────────


class TestTaskEvidence:
    """Task landscape progress."""

    def test_goal_reached(self):
        evidence = {
            "task": "route_optimization",
            "goal_reached": True,
            "steps": 12,
            "success_rate": 0.83,
            "avg_tension": 0.234,
            "states": list(range(8)),
            "edge_count": 15,
        }
        result = _interpret_status_task(evidence)
        assert "Goal reached" in result
        assert "route_optimization" in result
        assert "83%" in result

    def test_goal_not_reached(self):
        evidence = {
            "task": "planning",
            "goal_reached": False,
            "steps": 5,
            "success_rate": 0.4,
            "avg_tension": 0.5,
            "states": ["A", "B"],
            "edge_count": 3,
        }
        result = _interpret_status_task(evidence)
        assert "not yet reached" in result


# ── Dead End Evidence ──────────────────────────────────────────────────


class TestDeadEndEvidence:
    """Dead-end request."""

    def test_dead_end(self):
        evidence = {"state": "node_X", "admissible_neighbors": [], "goal": "target_Y"}
        result = _interpret_request_deadend(evidence)
        assert "Dead end" in result
        assert "node_X" in result
        assert "target_Y" in result


# ── Dream Evidence ─────────────────────────────────────────────────────


class TestDreamEvidence:
    """Dream equivalence."""

    def test_dream_equivalence(self):
        evidence = {"own_state": "EN:cat", "partner_state": "DE:Katze", "trace_quality": 0.6}
        result = _interpret_dream(evidence)
        assert "EN:cat" in result
        assert "DE:Katze" in result
        assert "equivalence" in result


# ── Generic Evidence ───────────────────────────────────────────────────


class TestGenericEvidence:
    """Unrecognized evidence structures."""

    def test_empty(self):
        assert "No evidence" in _interpret_generic({})

    def test_mixed_types(self):
        evidence = {"score": 0.42, "items": [1, 2, 3], "nested": {"a": 1}, "name": "test"}
        result = _interpret_generic(evidence)
        assert "score=0.420" in result
        assert "items: 3 items" in result
        assert "nested: 1 entries" in result
        assert "name=test" in result


# ── Panel Interpretation ───────────────────────────────────────────────


class TestInterpretPanel:
    """Full panel interpretation."""

    def test_panel_with_evidence(self):
        from e0_controller.ui_emitter import UIPanel

        panel = UIPanel(
            intent="uncertainty",
            perception="emphasis",
            language_act="warning",
            data_source="self_graph.quality",
            suggested_visual="heatmap",
            urgency=0.75,
            label="Component Health Alert",
            evidence={"status": "harmful", "quality": -0.5, "load": 12.0},
        )
        result = interpret_panel(panel)
        assert "Component Health Alert" in result
        assert "warning" in result
        assert "0.75" in result
        assert "harmful" in result

    def test_panel_without_evidence(self):
        from e0_controller.ui_emitter import UIPanel

        panel = UIPanel(
            intent="status",
            perception="positioning",
            language_act="assertion",
            data_source="trace",
            suggested_visual="text",
            urgency=0.2,
            label="Status",
            evidence={},
        )
        result = interpret_panel(panel)
        assert "Status" in result
        assert "No evidence" not in result  # empty evidence → no prose line


# ── End-to-End ─────────────────────────────────────────────────────────


class TestEndToEnd:
    """Real pipeline integration."""

    def test_emitter_to_interpretation(self):
        """UISpec panels → interpreted prose."""
        from e0_controller.communication import CommunicationIntent, IntentType, IntentReport
        from e0_controller.ui_emitter import emit_ui_spec

        intents = [
            CommunicationIntent(
                type=IntentType.UNCERTAINTY,
                urgency=0.7,
                subject="navigation_policy",
                summary="Mixed signals from navigation",
                evidence={"status": "confused", "quality": -0.1, "load": 8.0},
            ),
            CommunicationIntent(
                type=IntentType.DECISION,
                urgency=0.4,
                subject="edge_choice",
                summary="Selected edge A→B",
                evidence={"source": "A", "target": "B", "outcome": "SUCCESS",
                          "s_eff": 0.35, "candidates": ["B", "C"]},
            ),
        ]
        report = IntentReport(intents=intents)
        spec = emit_ui_spec(report, context="C209 integration test")

        # Each panel's evidence should be interpretable
        for panel in spec.panels:
            prose = interpret_panel(panel)
            assert len(prose) > 20
            assert panel.label in prose

    def test_inscription_stats_narrative(self):
        """Real inscription stats → narrative."""
        stats = {
            "total_inscriptions": 176,
            "inscribed_edges": 140,
            "domain_crossing_count": 95,
            "role_totals": {"bridge": 129, "exploration": 45, "revisit": 2},
            "mode_totals": {"explore_canon": 80, "explore_en": 60, "greedy": 36},
        }
        result = interpret_inscription_stats(stats)
        # Should read like a paragraph
        assert result.endswith(".")
        assert "176" in result
        assert "bridge" in result

    def test_all_evidence_types_produce_prose(self):
        """Every known evidence type produces non-empty prose."""
        examples = [
            {"status": "harmful", "quality": -0.5, "load": 10.0},
            {"status": "confused", "quality": 0.0, "load": 5.0},
            {"status": "insufficient_data", "load": 1.0},
            {"source": "A", "target": "B", "outcome": "SUCCESS", "s_eff": 0.5},
            {"r_eff_before": 0.8, "r_eff_after": 0.3, "drop_pct": 0.625},
            {"healthy": ["a"], "confused": ["b"]},
            {"task": "T", "goal_reached": True, "states": [], "edge_count": 0,
             "steps": 1, "success_rate": 1.0, "avg_tension": 0.1},
            {"state": "X", "admissible_neighbors": [], "goal": "Y"},
            {"own_state": "A", "partner_state": "B", "trace_quality": 0.5},
            {"random_key": 42},
        ]
        for evidence in examples:
            result = interpret_evidence(evidence)
            assert len(result) > 10, f"Empty output for {evidence}"
            assert result.endswith(".") or result.endswith(":"), f"No sentence ending: {result}"
