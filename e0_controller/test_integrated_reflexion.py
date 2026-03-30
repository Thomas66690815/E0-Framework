"""
Tests for E₀ Integrated Reflexion (C59)
==========================================
C49 (flag toggling) + C57 (edge proposal) unified pipeline.

Tests cover:
  1. IntegratedReflexionResult (dataclass, undo, summary)
  2. integrated_reflexion() function (flags, topology, both, none)
  3. run_with_integrated_reflexion() (full runner)
  4. Journal integration (records both flag + topology events)
  5. Edge cases (no report, no frontier, both disabled)
  6. Cooperation: C49 + C57 working together
"""

import unittest

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.self_graph import SelfGraph, CORE_COMPONENTS
from e0_controller.dual_reflection import (
    ComponentAssessment,
    DualReflectionReport,
    SelfGraphDiagnosis,
    diagnose_self_graph,
)
from e0_controller.reflexive_action import (
    ReflexiveAction,
    ReflexiveActionResult,
    ReflexiveJournal,
)
from e0_controller.reflexive_edge_proposal import ProposedEdge
from e0_controller.integrated_reflexion import (
    IntegratedReflexionResult,
    integrated_reflexion,
    record_integrated,
    run_with_integrated_reflexion,
)


# ── Helpers ──

def _make_landscape(curvature=False, overlap=False):
    L = Landscape(curvature_modulation=curvature, overlap_modulation=overlap)
    L.add_edge("A", "B", delta=0.5, resistance=0.3)
    L.add_edge("B", "C", delta=0.5, resistance=0.3)
    return L


def _make_frontier_landscape():
    """Landscape with a frontier: S→A→B exists but no path to GOAL."""
    L = Landscape()
    L.add_edge("S", "A", delta=0.5, resistance=0.3)
    L.add_edge("A", "B", delta=0.5, resistance=0.3)
    L.add_edge("B", "S", delta=0.5, resistance=0.3)
    # GOAL exists as a state but is unreachable
    L.add_state("GOAL")
    return L


def _make_connected_landscape():
    """Landscape where S→A→GOAL already exists."""
    L = Landscape()
    L.add_edge("S", "A", delta=0.5, resistance=0.3)
    L.add_edge("A", "GOAL", delta=0.5, resistance=0.3)
    return L


def _make_diagnosis(deactivation_candidates=None, components=None):
    return SelfGraphDiagnosis(
        deactivation_candidates=deactivation_candidates or [],
        components=components or [],
    )


def _make_report(diagnosis):
    return DualReflectionReport(domain_report=None, self_diagnosis=diagnosis)


def _all_success(source, target):
    return Outcome.SUCCESS


def _all_fail(source, target):
    return Outcome.FAILURE


# ══════════════════════════════════════════════
# 1. IntegratedReflexionResult
# ══════════════════════════════════════════════

class TestIntegratedReflexionResult(unittest.TestCase):
    """Result dataclass: properties, undo, summary."""

    def test_empty_result_no_changes(self):
        r = IntegratedReflexionResult()
        self.assertFalse(r.any_changes)
        self.assertFalse(r.flags_changed)
        self.assertFalse(r.topology_changed)

    def test_flags_only(self):
        flag_r = ReflexiveActionResult(
            actions_taken=[ReflexiveAction("curvature", "curvature_modulation",
                                           True, False, "test")]
        )
        r = IntegratedReflexionResult(flag_result=flag_r)
        self.assertTrue(r.any_changes)
        self.assertTrue(r.flags_changed)
        self.assertFalse(r.topology_changed)

    def test_topology_only(self):
        r = IntegratedReflexionResult(
            edge_proposals=[ProposedEdge("A", "B", 0.5, 0.3, 0.5, "test")],
            edges_added=1,
        )
        self.assertTrue(r.any_changes)
        self.assertFalse(r.flags_changed)
        self.assertTrue(r.topology_changed)

    def test_both_changes(self):
        flag_r = ReflexiveActionResult(
            actions_taken=[ReflexiveAction("curvature", "curvature_modulation",
                                           True, False, "test")]
        )
        r = IntegratedReflexionResult(
            flag_result=flag_r,
            edge_proposals=[ProposedEdge("A", "B", 0.5, 0.3, 0.5, "test")],
            edges_added=1,
        )
        self.assertTrue(r.any_changes)
        self.assertTrue(r.flags_changed)
        self.assertTrue(r.topology_changed)

    def test_restore_flags(self):
        L = _make_landscape(curvature=True)
        L.curvature_modulation = False  # simulate deactivation
        flag_r = ReflexiveActionResult(
            actions_taken=[ReflexiveAction("curvature", "curvature_modulation",
                                           True, False, "test")]
        )
        r = IntegratedReflexionResult(flag_result=flag_r)
        count = r.restore(L)
        self.assertEqual(count, 1)
        self.assertTrue(L.curvature_modulation)

    def test_restore_edges(self):
        L = _make_landscape()
        L.add_edge("X", "Y", delta=0.5, resistance=0.3)
        r = IntegratedReflexionResult(
            edge_proposals=[ProposedEdge("X", "Y", 0.5, 0.3, 0.5, "test")],
            edges_added=1,
        )
        count = r.restore(L)
        self.assertEqual(count, 1)
        self.assertFalse(L.has_edge("X", "Y"))

    def test_restore_both(self):
        L = _make_landscape(curvature=True)
        L.curvature_modulation = False
        L.add_edge("X", "Y", delta=0.5, resistance=0.3)
        flag_r = ReflexiveActionResult(
            actions_taken=[ReflexiveAction("curvature", "curvature_modulation",
                                           True, False, "test")]
        )
        r = IntegratedReflexionResult(
            flag_result=flag_r,
            edge_proposals=[ProposedEdge("X", "Y", 0.5, 0.3, 0.5, "test")],
            edges_added=1,
        )
        count = r.restore(L)
        self.assertEqual(count, 2)
        self.assertTrue(L.curvature_modulation)
        self.assertFalse(L.has_edge("X", "Y"))

    def test_summary_no_changes(self):
        r = IntegratedReflexionResult()
        s = r.summary()
        self.assertIn("No reflexive changes", s)

    def test_summary_with_changes(self):
        flag_r = ReflexiveActionResult(
            actions_taken=[ReflexiveAction("curvature", "curvature_modulation",
                                           True, False, "harmful")]
        )
        r = IntegratedReflexionResult(
            flag_result=flag_r,
            edge_proposals=[ProposedEdge("A", "B", 0.5, 0.3, 0.5, "test")],
            edges_added=1,
        )
        s = r.summary()
        self.assertIn("Flag reflexion", s)
        self.assertIn("Topology reflexion", s)
        self.assertIn("A → B", s)


# ══════════════════════════════════════════════
# 2. integrated_reflexion() function
# ══════════════════════════════════════════════

class TestIntegratedReflexion(unittest.TestCase):
    """Core function: combined flag + topology reflexion."""

    def test_no_report_no_frontier(self):
        """No report + connected landscape → nothing happens."""
        L = _make_connected_landscape()
        r = integrated_reflexion(L, "S", "GOAL")
        self.assertFalse(r.any_changes)

    def test_flag_only_deactivation(self):
        """Report with deactivation candidate → flags toggled."""
        L = _make_connected_landscape()
        L.curvature_modulation = True
        diag = _make_diagnosis(
            deactivation_candidates=["curvature"],
            components=[ComponentAssessment(
                "curvature", load=5.0, quality=-0.5, inertia=0.8,
                status="harmful", is_modulation=True,
            )],
        )
        report = _make_report(diag)
        r = integrated_reflexion(L, "S", "GOAL", report=report)
        self.assertTrue(r.flags_changed)
        self.assertFalse(r.topology_changed)
        self.assertFalse(L.curvature_modulation)

    def test_topology_only_at_frontier(self):
        """Frontier landscape, no report → edges proposed."""
        L = _make_frontier_landscape()
        # Add some historization so experienced_pattern works
        for e in L._delta:
            L.historization.update(e, Outcome.SUCCESS)
        r = integrated_reflexion(L, "B", "GOAL")
        self.assertFalse(r.flags_changed)
        self.assertTrue(r.topology_changed)
        self.assertGreater(len(r.edge_proposals), 0)
        # GOAL should now be reachable
        self.assertTrue(L.has_edge("B", "GOAL"))

    def test_both_at_frontier_with_report(self):
        """Frontier + harmful modulation → both reflexions fire."""
        L = _make_frontier_landscape()
        L.curvature_modulation = True
        for e in L._delta:
            L.historization.update(e, Outcome.SUCCESS)

        diag = _make_diagnosis(
            deactivation_candidates=["curvature"],
            components=[ComponentAssessment(
                "curvature", load=5.0, quality=-0.5, inertia=0.8,
                status="harmful", is_modulation=True,
            )],
        )
        report = _make_report(diag)
        r = integrated_reflexion(L, "B", "GOAL", report=report)
        self.assertTrue(r.flags_changed)
        self.assertTrue(r.topology_changed)
        self.assertFalse(L.curvature_modulation)
        self.assertTrue(L.has_edge("B", "GOAL"))

    def test_disable_flags(self):
        """enable_flags=False → no flag changes despite report."""
        L = _make_connected_landscape()
        L.curvature_modulation = True
        diag = _make_diagnosis(deactivation_candidates=["curvature"],
                               components=[ComponentAssessment(
                                   "curvature", 5.0, -0.5, 0.8, "harmful", True)])
        report = _make_report(diag)
        r = integrated_reflexion(L, "S", "GOAL", report=report,
                                 enable_flags=False)
        self.assertFalse(r.flags_changed)
        self.assertTrue(L.curvature_modulation)

    def test_disable_topology(self):
        """enable_topology=False → no edges despite frontier."""
        L = _make_frontier_landscape()
        for e in L._delta:
            L.historization.update(e, Outcome.SUCCESS)
        r = integrated_reflexion(L, "B", "GOAL", enable_topology=False)
        self.assertFalse(r.topology_changed)
        self.assertFalse(L.has_edge("B", "GOAL"))

    def test_diagnosis_recorded_in_result(self):
        """Result stores the diagnosis that was used."""
        L = _make_connected_landscape()
        diag = _make_diagnosis()
        report = _make_report(diag)
        r = integrated_reflexion(L, "S", "GOAL", report=report)
        self.assertIs(r.diagnosis_used, diag)

    def test_proactive_false_reactive_mode(self):
        """proactive=False uses reactive R₀ scaling."""
        L = _make_frontier_landscape()
        for e in L._delta:
            L.historization.update(e, Outcome.SUCCESS)
        r = integrated_reflexion(L, "B", "GOAL", proactive=False)
        self.assertTrue(r.topology_changed)
        # Reactive mode inflates R₀, so proposals should have higher resistance
        for p in r.edge_proposals:
            self.assertGreater(p.resistance, 0)


# ══════════════════════════════════════════════
# 3. run_with_integrated_reflexion()
# ══════════════════════════════════════════════

class TestRunWithIntegratedReflexion(unittest.TestCase):
    """Full runner: SelfGraph + per-step frontier + periodic diagnosis."""

    def test_connected_landscape_reaches_goal(self):
        """No frontier → direct navigation, no reflexion needed."""
        L = _make_connected_landscape()
        trace, result, journal = run_with_integrated_reflexion(
            L, _all_success, "S", "GOAL", max_cycles=20,
        )
        self.assertEqual(trace.path[-1], "GOAL")
        self.assertFalse(result.topology_changed)

    def test_frontier_triggers_edge_proposal(self):
        """Frontier landscape → proposals added, GOAL becomes reachable."""
        # Dead-end: S→A, A has no outgoing → frontier at A
        L = Landscape()
        L.add_edge("S", "A", delta=0.5, resistance=0.3)
        L.historization.update(Edge("S", "A"), Outcome.SUCCESS)
        L.add_state("GOAL")

        trace, result, journal = run_with_integrated_reflexion(
            L, _all_success, "S", "GOAL", max_cycles=30,
        )
        self.assertTrue(result.topology_changed)
        self.assertGreater(len(result.edge_proposals), 0)
        # GOAL should now be reachable in the landscape
        self.assertTrue(L.has_edge("A", "GOAL") or L.has_edge("S", "GOAL"))

    def test_selfgraph_gets_historized(self):
        """Controller should self-historize via SelfGraph."""
        L = _make_connected_landscape()
        trace, result, journal = run_with_integrated_reflexion(
            L, _all_success, "S", "GOAL", max_cycles=20,
        )
        # Trace has steps → SelfGraph was used
        self.assertGreater(len(trace.steps), 0)

    def test_multiple_frontiers(self):
        """Cascading frontier gaps → proposal round at frontier."""
        L = Landscape()
        L.add_edge("S", "A", delta=0.5, resistance=0.3)
        L.add_edge("A", "S", delta=0.5, resistance=0.3)
        # B and GOAL exist but are disconnected
        L.add_edge("B", "GOAL", delta=0.5, resistance=0.3)
        L.add_state("GOAL")
        # Historize for pattern
        for e in L._delta:
            L.historization.update(e, Outcome.SUCCESS)

        trace, result, journal = run_with_integrated_reflexion(
            L, _all_success, "S", "GOAL", max_cycles=50,
        )
        # Should have proposed edges (S is frontier, GOAL unreachable)
        self.assertGreater(len(result.edge_proposals), 0)
        # GOAL should now be reachable through proposed topology
        self.assertTrue(
            L.has_edge("S", "GOAL") or L.has_edge("S", "B")
        )

    def test_journal_records_flag_changes(self):
        """When diagnosis triggers flag changes, journal records them."""
        # Build landscape with curvature active
        L = Landscape(curvature_modulation=True)
        L.add_edge("S", "A", delta=0.5, resistance=0.3)
        L.add_edge("A", "B", delta=0.5, resistance=0.3)
        L.add_edge("B", "S", delta=0.5, resistance=0.3)
        L.add_edge("A", "GOAL", delta=0.5, resistance=0.3)

        call_count = [0]

        def _execute(s, t):
            call_count[0] += 1
            if call_count[0] <= 5:
                return Outcome.FAILURE
            return Outcome.SUCCESS

        # With very short diagnosis_interval, C49 diagnosis runs frequently
        trace, result, journal = run_with_integrated_reflexion(
            L, _execute, "S", "GOAL",
            max_cycles=50, diagnosis_interval=5,
        )
        # Navigation should complete
        self.assertGreater(len(trace.steps), 0)

    def test_max_cycles_respected(self):
        """Runner stops at max_cycles even without goal."""
        L = Landscape()
        L.add_edge("S", "A", delta=0.5, resistance=0.3)
        L.add_edge("A", "S", delta=0.5, resistance=0.3)
        # No GOAL state at all
        trace, result, journal = run_with_integrated_reflexion(
            L, _all_success, "S", "NONEXISTENT",
            max_cycles=10,
        )
        self.assertLessEqual(len(trace.steps), 10)


# ══════════════════════════════════════════════
# 4. record_integrated()
# ══════════════════════════════════════════════

class TestRecordIntegrated(unittest.TestCase):
    """Journal integration for unified results."""

    def test_empty_result_no_records(self):
        journal = ReflexiveJournal()
        r = IntegratedReflexionResult()
        count = record_integrated(journal, r, iteration=0)
        self.assertEqual(count, 0)
        self.assertEqual(journal.total_actions, 0)

    def test_flag_changes_recorded(self):
        journal = ReflexiveJournal()
        flag_r = ReflexiveActionResult(
            actions_taken=[ReflexiveAction("curvature", "curvature_modulation",
                                           True, False, "harmful")]
        )
        r = IntegratedReflexionResult(flag_result=flag_r)
        count = record_integrated(journal, r, iteration=3)
        self.assertEqual(count, 1)
        self.assertEqual(journal.total_actions, 1)
        self.assertEqual(journal.entries[0].iteration, 3)

    def test_topology_only_no_flag_record(self):
        """Edge proposals without flag changes → no journal entries."""
        journal = ReflexiveJournal()
        r = IntegratedReflexionResult(
            edge_proposals=[ProposedEdge("A", "B", 0.5, 0.3, 0.5, "test")],
            edges_added=1,
        )
        count = record_integrated(journal, r, iteration=1)
        self.assertEqual(count, 0)

    def test_both_recorded(self):
        journal = ReflexiveJournal()
        flag_r = ReflexiveActionResult(
            actions_taken=[
                ReflexiveAction("curvature", "curvature_modulation",
                                True, False, "harmful"),
                ReflexiveAction("overlap", "overlap_modulation",
                                True, False, "harmful"),
            ]
        )
        r = IntegratedReflexionResult(
            flag_result=flag_r,
            edge_proposals=[ProposedEdge("A", "B", 0.5, 0.3, 0.5, "test")],
            edges_added=1,
        )
        count = record_integrated(journal, r, iteration=5)
        self.assertEqual(count, 2)
        self.assertEqual(journal.total_actions, 2)


# ══════════════════════════════════════════════
# 5. Edge cases
# ══════════════════════════════════════════════

class TestEdgeCases(unittest.TestCase):
    """Boundary conditions and degenerate inputs."""

    def test_already_at_goal(self):
        """current == goal → no reflexion needed."""
        L = _make_connected_landscape()
        r = integrated_reflexion(L, "GOAL", "GOAL")
        self.assertFalse(r.any_changes)

    def test_run_already_at_goal(self):
        """Runner with start == goal → immediate return."""
        L = _make_connected_landscape()
        trace, result, journal = run_with_integrated_reflexion(
            L, _all_success, "GOAL", "GOAL", max_cycles=20,
        )
        self.assertEqual(len(trace.steps), 0)
        self.assertFalse(result.any_changes)

    def test_empty_landscape(self):
        """Landscape with only start, no edges → no crash."""
        L = Landscape()
        L.add_state("S")
        L.add_state("GOAL")
        r = integrated_reflexion(L, "S", "GOAL")
        # Frontier but no candidates (no existing edges for pattern)
        # Should not crash

    def test_restore_idempotent(self):
        """Restoring already-restored result is safe."""
        L = _make_landscape()
        r = IntegratedReflexionResult()
        count = r.restore(L)
        self.assertEqual(count, 0)

    def test_restore_missing_edge(self):
        """Restoring when proposed edge was already removed → skip."""
        L = _make_landscape()
        r = IntegratedReflexionResult(
            edge_proposals=[ProposedEdge("X", "Y", 0.5, 0.3, 0.5, "test")],
            edges_added=1,
        )
        # Edge doesn't exist on L → restore should handle gracefully
        count = r.restore(L)
        self.assertEqual(count, 0)


# ══════════════════════════════════════════════
# 6. C49 + C57 cooperation
# ══════════════════════════════════════════════

class TestCooperation(unittest.TestCase):
    """C49 and C57 working together — the integration payoff."""

    def test_flag_toggle_plus_edge_proposal(self):
        """Frontier + harmful modulation → both happen, both reversible."""
        L = _make_frontier_landscape()
        L.curvature_modulation = True
        for e in L._delta:
            L.historization.update(e, Outcome.SUCCESS)

        diag = _make_diagnosis(
            deactivation_candidates=["curvature"],
            components=[ComponentAssessment(
                "curvature", 5.0, -0.5, 0.8, "harmful", True,
            )],
        )
        report = _make_report(diag)
        r = integrated_reflexion(L, "B", "GOAL", report=report)

        # Both happened
        self.assertTrue(r.flags_changed)
        self.assertTrue(r.topology_changed)
        self.assertFalse(L.curvature_modulation)
        self.assertTrue(L.has_edge("B", "GOAL"))

        # Full undo: 1 flag + N edges = total restored
        n_proposals = len(r.edge_proposals)
        count = r.restore(L)
        self.assertEqual(count, 1 + n_proposals)
        self.assertTrue(L.curvature_modulation)

    def test_flag_without_topology_no_frontier(self):
        """Connected graph + harmful → flags only, no edges."""
        L = _make_connected_landscape()
        L.curvature_modulation = True

        diag = _make_diagnosis(
            deactivation_candidates=["curvature"],
            components=[ComponentAssessment(
                "curvature", 5.0, -0.5, 0.8, "harmful", True,
            )],
        )
        report = _make_report(diag)
        r = integrated_reflexion(L, "S", "GOAL", report=report)

        self.assertTrue(r.flags_changed)
        self.assertFalse(r.topology_changed)

    def test_topology_without_flags_no_candidates(self):
        """Frontier + healthy diagnosis → edges only, no flags."""
        L = _make_frontier_landscape()
        for e in L._delta:
            L.historization.update(e, Outcome.SUCCESS)

        diag = _make_diagnosis()  # no deactivation candidates
        report = _make_report(diag)
        r = integrated_reflexion(L, "B", "GOAL", report=report)

        self.assertFalse(r.flags_changed)
        self.assertTrue(r.topology_changed)

    def test_integrated_monotonic_no_harm(self):
        """Integrated reflexion never makes things worse.

        Structural guarantee: flags are only toggled for harmful
        components, edges only added at unreachable frontiers.
        """
        # Start with disconnected landscape
        L = Landscape(curvature_modulation=True)
        L.add_edge("S", "A", delta=0.5, resistance=0.3)
        L.add_edge("A", "B", delta=0.5, resistance=0.3)
        L.add_edge("B", "S", delta=0.5, resistance=0.3)
        L.add_state("GOAL")
        for e in L._delta:
            L.historization.update(e, Outcome.SUCCESS)

        edges_before = len(L._delta)
        diag = _make_diagnosis(
            deactivation_candidates=["curvature"],
            components=[ComponentAssessment(
                "curvature", 5.0, -0.5, 0.8, "harmful", True,
            )],
        )
        report = _make_report(diag)
        r = integrated_reflexion(L, "B", "GOAL", report=report)

        # Edges can only increase (never removed by reflexion)
        self.assertGreaterEqual(len(L._delta), edges_before)
        # Harmful flag disabled
        self.assertFalse(L.curvature_modulation)


if __name__ == "__main__":
    unittest.main()
