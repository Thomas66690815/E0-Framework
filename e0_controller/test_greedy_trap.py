"""
Tests for the greedy-trap walkthrough demo.

Verifies the core claim: greedy gets trapped, hybrid reaches GOAL.
"""

import unittest

from .controller import E0Controller, HybridMode
from .demo_greedy_trap import build_trap_landscape, always_success


class TestGreedyTrapWalkthrough(unittest.TestCase):
    """Tests for the README walkthrough scenario."""

    def test_greedy_trapped_in_loop(self):
        """Greedy mode gets trapped in the A↔C cycle."""
        L = build_trap_landscape()
        ctrl = E0Controller(
            landscape=L,
            execute_fn=always_success,
            hybrid_mode=HybridMode.GREEDY,
            alpha=0.5,
            recent_k=2,
        )
        trace = ctrl.run("A", goal="GOAL", max_cycles=10)
        self.assertNotEqual(trace.path[-1], "GOAL")
        # Should bounce between A and C
        self.assertIn("C", trace.path)
        self.assertNotIn("B", trace.path)

    def test_hybrid_reaches_goal(self):
        """Hybrid mode overrides greedy and reaches GOAL."""
        L = build_trap_landscape()
        ctrl = E0Controller(
            landscape=L,
            execute_fn=always_success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=4,
            hybrid_goals={"GOAL"},
            alpha=0.5,
            recent_k=2,
        )
        trace = ctrl.run("A", goal="GOAL", max_cycles=10)
        self.assertEqual(trace.path[-1], "GOAL")
        self.assertEqual(len(trace.steps), 4)
        self.assertEqual(trace.path, ["A", "B", "E", "G", "GOAL"])

    def test_hybrid_override_at_step_one(self):
        """The amplitude override happens at the first step (A→B vs A→C)."""
        L = build_trap_landscape()
        ctrl = E0Controller(
            landscape=L,
            execute_fn=always_success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=4,
            hybrid_goals={"GOAL"},
            alpha=0.5,
            recent_k=2,
        )
        trace = ctrl.run("A", goal="GOAL", max_cycles=10)
        step0 = trace.steps[0]
        self.assertTrue(step0.hybrid_overridden)
        self.assertIsNotNone(step0.overlay)
        self.assertEqual(step0.overlay.deterministic_choice, "C")
        self.assertEqual(step0.overlay.amplitude_choice, "B")
        self.assertEqual(step0.target, "B")

    def test_no_override_after_step_one(self):
        """After the override, the forward path has no disagreement."""
        L = build_trap_landscape()
        ctrl = E0Controller(
            landscape=L,
            execute_fn=always_success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=4,
            hybrid_goals={"GOAL"},
            alpha=0.5,
            recent_k=2,
        )
        trace = ctrl.run("A", goal="GOAL", max_cycles=10)
        # Steps 2-4 should not be overridden (only one forward edge each)
        for step in trace.steps[1:]:
            self.assertFalse(step.hybrid_overridden)


if __name__ == "__main__":
    unittest.main()
