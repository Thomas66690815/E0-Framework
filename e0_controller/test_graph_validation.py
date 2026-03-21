"""Tests for graph_validation (Phase 3c)."""

import unittest
from e0_controller.landscape import Landscape
from e0_controller.graph_validation import (
    goal_reachable,
    find_happy_path,
    find_recovery_edges,
    detect_traps,
    detect_trivial_loops,
    graph_quality,
)
from e0_controller.primitives import Edge


def _make_linear() -> Landscape:
    """A → B → C (simple chain, no recovery)."""
    L = Landscape()
    L.add_edge("A", "B", delta=0.3, resistance=0.5)
    L.add_edge("B", "C", delta=0.4, resistance=0.6)
    return L


def _make_with_recovery() -> Landscape:
    """A → B → C with error state E → B (recovery)."""
    L = _make_linear()
    L.add_edge("A", "E", delta=0.3, resistance=1.5)
    L.add_edge("E", "B", delta=0.4, resistance=1.0)
    return L


def _make_with_trap() -> Landscape:
    """A → B → C, A → TRAP (no outgoing)."""
    L = _make_linear()
    L.add_edge("A", "TRAP", delta=0.3, resistance=1.5)
    return L


def _make_with_loop() -> Landscape:
    """A → B → C, B ↔ D (2-cycle)."""
    L = _make_linear()
    L.add_edge("B", "D", delta=0.3, resistance=0.5)
    L.add_edge("D", "B", delta=0.3, resistance=0.5)
    return L


def _make_disconnected() -> Landscape:
    """A → B, C → D (two components, goal D unreachable from A)."""
    L = Landscape()
    L.add_edge("A", "B", delta=0.3, resistance=0.5)
    L.add_edge("C", "D", delta=0.4, resistance=0.6)
    return L


def _make_self_loop() -> Landscape:
    """A → A (self-loop), A → B."""
    L = Landscape()
    L.add_edge("A", "A", delta=0.1, resistance=0.1)
    L.add_edge("A", "B", delta=0.3, resistance=0.5)
    return L


# ──────────────────────────────────────────────
# Reachability
# ──────────────────────────────────────────────

class TestGoalReachable(unittest.TestCase):

    def test_linear_reachable(self):
        L = _make_linear()
        self.assertTrue(goal_reachable(L, "A", "C"))

    def test_linear_not_reverse(self):
        L = _make_linear()
        self.assertFalse(goal_reachable(L, "C", "A"))

    def test_disconnected(self):
        L = _make_disconnected()
        self.assertFalse(goal_reachable(L, "A", "D"))

    def test_same_start_goal(self):
        L = _make_linear()
        self.assertTrue(goal_reachable(L, "A", "A"))

    def test_unknown_state(self):
        L = _make_linear()
        self.assertFalse(goal_reachable(L, "A", "UNKNOWN"))


# ──────────────────────────────────────────────
# Happy Path
# ──────────────────────────────────────────────

class TestHappyPath(unittest.TestCase):

    def test_linear_path(self):
        L = _make_linear()
        path = find_happy_path(L, "A", "C")
        self.assertEqual(path, ["A", "B", "C"])

    def test_shortest_chosen(self):
        """With recovery edge present, happy path is still shortest."""
        L = _make_with_recovery()
        path = find_happy_path(L, "A", "C")
        self.assertEqual(path, ["A", "B", "C"])

    def test_no_path(self):
        L = _make_disconnected()
        path = find_happy_path(L, "A", "D")
        self.assertIsNone(path)

    def test_same_start_goal(self):
        L = _make_linear()
        path = find_happy_path(L, "A", "A")
        self.assertEqual(path, ["A"])


# ──────────────────────────────────────────────
# Recovery Edges
# ──────────────────────────────────────────────

class TestRecoveryEdges(unittest.TestCase):

    def test_recovery_found(self):
        L = _make_with_recovery()
        happy = find_happy_path(L, "A", "C")
        recovery = find_recovery_edges(L, happy)
        self.assertEqual(len(recovery), 1)
        self.assertEqual(recovery[0], Edge("E", "B"))

    def test_no_recovery_in_linear(self):
        L = _make_linear()
        happy = find_happy_path(L, "A", "C")
        recovery = find_recovery_edges(L, happy)
        self.assertEqual(len(recovery), 0)


# ──────────────────────────────────────────────
# Trap Detection
# ──────────────────────────────────────────────

class TestTraps(unittest.TestCase):

    def test_trap_detected(self):
        L = _make_with_trap()
        traps = detect_traps(L)
        self.assertIn("TRAP", traps)

    def test_goal_is_trap_ok(self):
        """Goal state C has no outgoing edges — that's fine."""
        L = _make_linear()
        traps = detect_traps(L)
        self.assertIn("C", traps)  # C is technically a dead-end
        # But graph_quality excludes goal from traps

    def test_connected_no_traps(self):
        L = _make_with_loop()
        traps = detect_traps(L)
        # C is a dead-end, everything else has outgoing
        self.assertEqual(traps, ["C"])


# ──────────────────────────────────────────────
# Trivial Loops
# ──────────────────────────────────────────────

class TestTrivialLoops(unittest.TestCase):

    def test_two_cycle_detected(self):
        L = _make_with_loop()
        loops = detect_trivial_loops(L)
        self.assertEqual(len(loops), 1)
        self.assertEqual(loops[0], ("B", "D"))

    def test_self_loop_detected(self):
        L = _make_self_loop()
        loops = detect_trivial_loops(L)
        self.assertIn(("A", "A"), loops)

    def test_no_loops_in_linear(self):
        L = _make_linear()
        loops = detect_trivial_loops(L)
        self.assertEqual(len(loops), 0)


# ──────────────────────────────────────────────
# Composite Quality
# ──────────────────────────────────────────────

class TestGraphQuality(unittest.TestCase):

    def test_linear_quality(self):
        L = _make_linear()
        q = graph_quality(L, "A", "C")
        self.assertTrue(q.ok())
        self.assertTrue(q.reachable)
        self.assertEqual(q.happy_path, ["A", "B", "C"])
        self.assertEqual(q.happy_path_length, 2)
        self.assertEqual(q.recovery_count, 0)
        # Score: 0.5 (reachable) + 0.2 (short path) + 0.15 (no non-happy states)
        #        + 0.1 (no traps, C excluded as goal) + 0.05 (no loops) = 1.0
        self.assertAlmostEqual(q.score, 1.0, places=2)

    def test_with_recovery_quality(self):
        L = _make_with_recovery()
        q = graph_quality(L, "A", "C")
        self.assertTrue(q.ok())
        self.assertGreater(q.recovery_count, 0)
        # E is the only non-happy state, and has a recovery edge → coverage=1.0
        self.assertGreaterEqual(q.score, 0.95)

    def test_disconnected_quality(self):
        L = _make_disconnected()
        q = graph_quality(L, "A", "D")
        self.assertFalse(q.ok())
        self.assertFalse(q.reachable)
        self.assertEqual(q.score, 0.0)
        self.assertTrue(any("CRITICAL" in w for w in q.warnings))

    def test_trap_warns(self):
        L = _make_with_trap()
        q = graph_quality(L, "A", "C")
        self.assertTrue(q.ok())
        # TRAP is not goal, so it's a real trap
        self.assertIn("TRAP", q.traps)
        self.assertTrue(any("trap" in w.lower() for w in q.warnings))

    def test_loop_warns(self):
        L = _make_with_loop()
        q = graph_quality(L, "A", "C")
        self.assertTrue(q.ok())
        self.assertEqual(len(q.trivial_loops), 1)
        self.assertTrue(any("loop" in w.lower() for w in q.warnings))

    def test_summary_text(self):
        L = _make_linear()
        q = graph_quality(L, "A", "C")
        text = q.summary()
        self.assertIn("Graph Quality Score", text)
        self.assertIn("Reachable: True", text)

    def test_quality_of_incident_mock_graph(self):
        """Validate the mock incident-postmortem graph structure."""
        L = Landscape()
        states = [
            "RAW_INCIDENT_REPORT", "TIMELINE_PARSED", "IMPACT_IDENTIFIED",
            "TRIGGER_HYPOTHESIZED", "ROOT_CAUSE_ANALYZED",
            "MITIGATIONS_IDENTIFIED", "FOLLOWUPS_DRAFTED",
            "POSTMORTEM_ASSEMBLED", "POSTMORTEM_DELIVERED",
            "TIMELINE_INCOMPLETE", "LOGS_INSUFFICIENT",
            "CAUSE_AMBIGUOUS", "HUMAN_REVIEW",
        ]
        for s in states:
            L.add_state(s)
        edges = [
            ("RAW_INCIDENT_REPORT", "TIMELINE_PARSED", 0.3, 0.5),
            ("TIMELINE_PARSED", "IMPACT_IDENTIFIED", 0.4, 0.7),
            ("IMPACT_IDENTIFIED", "TRIGGER_HYPOTHESIZED", 0.5, 0.9),
            ("TRIGGER_HYPOTHESIZED", "ROOT_CAUSE_ANALYZED", 0.6, 1.1),
            ("ROOT_CAUSE_ANALYZED", "MITIGATIONS_IDENTIFIED", 0.4, 0.8),
            ("MITIGATIONS_IDENTIFIED", "FOLLOWUPS_DRAFTED", 0.3, 0.6),
            ("FOLLOWUPS_DRAFTED", "POSTMORTEM_ASSEMBLED", 0.3, 0.4),
            ("POSTMORTEM_ASSEMBLED", "POSTMORTEM_DELIVERED", 0.1, 0.2),
            ("RAW_INCIDENT_REPORT", "TIMELINE_INCOMPLETE", 0.3, 1.5),
            ("TIMELINE_INCOMPLETE", "LOGS_INSUFFICIENT", 0.2, 1.8),
            ("LOGS_INSUFFICIENT", "HUMAN_REVIEW", 0.4, 2.0),
            ("HUMAN_REVIEW", "TIMELINE_PARSED", 0.3, 0.8),
            ("TIMELINE_INCOMPLETE", "TIMELINE_PARSED", 0.4, 1.2),
            ("TRIGGER_HYPOTHESIZED", "CAUSE_AMBIGUOUS", 0.4, 1.6),
            ("CAUSE_AMBIGUOUS", "ROOT_CAUSE_ANALYZED", 0.5, 1.4),
        ]
        for s, t, d, r in edges:
            L.add_edge(s, t, delta=d, resistance=r)

        q = graph_quality(L, "RAW_INCIDENT_REPORT", "POSTMORTEM_DELIVERED")
        self.assertTrue(q.ok())
        self.assertTrue(q.reachable)
        self.assertEqual(q.happy_path_length, 8)
        self.assertGreater(q.recovery_count, 0)
        # Good graph — should score well
        self.assertGreater(q.score, 0.7)


if __name__ == "__main__":
    unittest.main()
