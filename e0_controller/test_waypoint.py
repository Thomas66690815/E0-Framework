"""
E₀ Controller — Tests: Goal-with-Continuations Domain (Phase 3p)
================================================================
Unit tests for the goal-with-continuations (waypoint) domain.

Purpose: Close H4 from the Summation Geometry Comparison by providing
a domain where the goal state has rich outgoing edges, so that
first_arrival genuinely differs from prefix geometry.

Waypoint Domain:

        ┌──(0.4/0.8)──→ P ──(0.3/0.6)──→ G ──(0.2/0.4)──→ Y1 ──(0.5/0.3)──→ G  (loop)
        │                                  │
  START─┤                                  └──(0.3/0.5)──→ Y2 ──(0.2/0.4)──→ END
        │
        └──(0.3/0.5)──→ W ──(0.2/0.3)──→ G
                                          │
                                 (same outgoing: Y1, Y2)

Key design:
  - Goal G has 2 outgoing edges → not terminal
  - Post-goal loop G→Y1→G inflates prefix path counts
  - first_arrival stops at G → immune to post-goal inflation
  - simple also includes post-goal paths (no state repeat filter here)
  - Two routes to G: START→P→G (via P) and START→W→G (via W)
  - Greedy picks W (lower initial cost), but both reach G

Expected geometry divergence:
  - prefix: counts G→Y1→G loops → inflated intensity for actions
    whose continuations wander through the loop
  - first_arrival: stops at G → cleaner intensity measurement
  - simple: allows G→Y1→... and G→Y2→... but no G→Y1→G (revisit G)
"""

from __future__ import annotations

import math
import unittest

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller, HybridMode
from e0_controller.amplitude_overlay import (
    analyze_controller_state,
    _enumerate_continuations,
    _filter_paths_by_first_action,
    GEOMETRIES,
)


# ──────────────────────────────────────────────
# Waypoint Domain Builder
# ──────────────────────────────────────────────

def build_waypoint_landscape() -> Landscape:
    """
    Build the goal-with-continuations (waypoint) domain.

    Goal state G has outgoing edges to Y1 and Y2.
    Y1 loops back to G (creates post-goal cycle).
    Y2 leads to END (post-goal continuation).

    Two routes to G:
      - START → P → G  (longer, higher initial cost)
      - START → W → G  (shorter, lower initial cost → greedy picks this)
    """
    L = Landscape()

    # Route 1: START → P → G
    L.add_edge("START", "P", delta=0.4, resistance=0.8)    # S = 0.32
    L.add_edge("P", "G", delta=0.3, resistance=0.6)        # S = 0.18

    # Route 2: START → W → G  (cheaper first hop → greedy favorite)
    L.add_edge("START", "W", delta=0.3, resistance=0.5)    # S = 0.15
    L.add_edge("W", "G", delta=0.2, resistance=0.3)        # S = 0.06

    # Post-goal continuations from G
    L.add_edge("G", "Y1", delta=0.2, resistance=0.4)       # S = 0.08
    L.add_edge("G", "Y2", delta=0.3, resistance=0.5)       # S = 0.15

    # Y1 loops back to G (the key loop that distinguishes geometries)
    L.add_edge("Y1", "G", delta=0.5, resistance=0.3)       # S = 0.15

    # Y2 leads to END (terminal)
    L.add_edge("Y2", "END", delta=0.2, resistance=0.4)     # S = 0.08

    # Cross-link: P → W (creates v_rot asymmetry for non-trivial phase)
    L.add_edge("P", "W", delta=0.5, resistance=1.5)        # S = 0.75 (heavy)

    return L


def waypoint_success(source: str, target: str) -> Outcome:
    return Outcome.SUCCESS


# ──────────────────────────────────────────────
# Test Class 1: Domain Structure
# ──────────────────────────────────────────────

class TestWaypointDomainStructure(unittest.TestCase):
    """Verify the waypoint domain has the expected topology."""

    def setUp(self):
        self.L = build_waypoint_landscape()

    def test_all_edges_exist(self):
        """All designed edges are present."""
        expected = [
            ("START", "P"), ("P", "G"),
            ("START", "W"), ("W", "G"),
            ("G", "Y1"), ("G", "Y2"),
            ("Y1", "G"), ("Y2", "END"),
            ("P", "W"),
        ]
        for s, t in expected:
            self.assertIsNotNone(
                self.L.difference(s, t),
                f"Edge {s}→{t} missing"
            )

    def test_goal_is_not_terminal(self):
        """G has outgoing edges (the core design requirement)."""
        ctrl = E0Controller(self.L, waypoint_success)
        neighbors = ctrl._admissible_neighbors("G")
        self.assertGreaterEqual(len(neighbors), 2)
        self.assertIn("Y1", neighbors)
        self.assertIn("Y2", neighbors)

    def test_end_is_terminal(self):
        """END has no outgoing edges."""
        ctrl = E0Controller(self.L, waypoint_success)
        neighbors = ctrl._admissible_neighbors("END")
        self.assertEqual(neighbors, [])

    def test_post_goal_loop_exists(self):
        """Y1 → G edge exists (post-goal cycle)."""
        self.assertIsNotNone(self.L.difference("Y1", "G"))
        self.assertIsNotNone(self.L.difference("G", "Y1"))

    def test_two_routes_to_goal(self):
        """START has two forward options toward G: P and W."""
        ctrl = E0Controller(self.L, waypoint_success)
        neighbors = ctrl._admissible_neighbors("START")
        self.assertIn("P", neighbors)
        self.assertIn("W", neighbors)


# ──────────────────────────────────────────────
# Test Class 2: Geometry Differentiation (H4)
# ──────────────────────────────────────────────

class TestGeometryDifferentiation(unittest.TestCase):
    """
    The core H4 tests: first_arrival genuinely differs from prefix
    when the goal has continuations.
    """

    def setUp(self):
        self.L = build_waypoint_landscape()
        self.ctrl = E0Controller(self.L, waypoint_success, alpha=2.0)

    def test_prefix_includes_post_goal_paths(self):
        """prefix geometry includes paths that pass through G and continue."""
        paths = _enumerate_continuations(
            self.ctrl, "START", horizon_edges=4, geometry="prefix"
        )
        # Find paths that go through G and continue
        post_goal = [p for p in paths if "G" in p[:-1]]  # G not at end
        self.assertGreater(len(post_goal), 0,
                           "prefix should include paths passing through G")

    def test_first_arrival_stops_at_goal(self):
        """first_arrival geometry stops extending once G is reached."""
        paths = _enumerate_continuations(
            self.ctrl, "START", horizon_edges=4,
            geometry="first_arrival", goals={"G"}
        )
        for path in paths:
            if "G" in path[1:]:  # G appears (not as start)
                g_idx = path[1:].index("G") + 1
                # G must be the last state in this path
                self.assertEqual(
                    path[g_idx], path[-1],
                    f"Path {path} continues past goal G"
                )

    def test_prefix_has_more_paths_than_first_arrival(self):
        """prefix produces more paths because it explores post-goal structure."""
        prefix_paths = _enumerate_continuations(
            self.ctrl, "START", horizon_edges=4, geometry="prefix"
        )
        fa_paths = _enumerate_continuations(
            self.ctrl, "START", horizon_edges=4,
            geometry="first_arrival", goals={"G"}
        )
        self.assertGreater(
            len(prefix_paths), len(fa_paths),
            f"prefix ({len(prefix_paths)} paths) should exceed "
            f"first_arrival ({len(fa_paths)} paths)"
        )

    def test_prefix_and_first_arrival_intensities_differ(self):
        """Amplitude intensities genuinely differ between prefix and first_arrival."""
        report_prefix = analyze_controller_state(
            self.ctrl, "START", horizon_edges=4, geometry="prefix"
        )
        report_fa = analyze_controller_state(
            self.ctrl, "START", horizon_edges=4,
            geometry="first_arrival", goals={"G"}
        )

        # Extract intensity for the same action from both reports
        def get_intensity(report, action):
            for info in report.action_infos:
                if info.action == action:
                    return info.intensity
            return 0.0

        # At least one action should have different intensity
        actions = ["P", "W"]
        diffs = []
        for a in actions:
            i_prefix = get_intensity(report_prefix, a)
            i_fa = get_intensity(report_fa, a)
            diffs.append(abs(i_prefix - i_fa))

        self.assertGreater(
            max(diffs), 0.001,
            "prefix and first_arrival should produce different intensities "
            "when goal has continuations"
        )

    def test_simple_and_first_arrival_differ(self):
        """simple also differs from first_arrival (it allows post-goal non-repeat paths)."""
        simple_paths = _enumerate_continuations(
            self.ctrl, "START", horizon_edges=4, geometry="simple"
        )
        fa_paths = _enumerate_continuations(
            self.ctrl, "START", horizon_edges=4,
            geometry="first_arrival", goals={"G"}
        )
        # simple allows G→Y1, G→Y2→END etc. without revisiting
        # first_arrival stops at G
        # So simple should have more paths too
        simple_through_G = [p for p in simple_paths if "G" in p[:-1]]
        self.assertGreater(len(simple_through_G), 0,
                           "simple should include paths continuing past G")

    def test_all_three_geometries_at_start(self):
        """All three geometries produce valid reports at START."""
        for geo in GEOMETRIES:
            goals = {"G"} if geo == "first_arrival" else None
            report = analyze_controller_state(
                self.ctrl, "START", horizon_edges=4,
                geometry=geo, goals=goals
            )
            self.assertEqual(report.current, "START")
            self.assertGreater(len(report.action_infos), 0)
            # Check probabilities sum to ≈1
            total_p = sum(a.probability for a in report.action_infos)
            self.assertAlmostEqual(total_p, 1.0, places=5,
                                   msg=f"{geo}: probabilities should sum to 1.0")


# ──────────────────────────────────────────────
# Test Class 3: Post-Goal Loop Effects
# ──────────────────────────────────────────────

class TestPostGoalLoopEffects(unittest.TestCase):
    """
    Tests that the G→Y1→G loop has measurable impact on prefix
    but NOT on first_arrival.
    """

    def setUp(self):
        self.L = build_waypoint_landscape()
        self.ctrl = E0Controller(self.L, waypoint_success, alpha=2.0)

    def test_prefix_at_goal_sees_loop_paths(self):
        """At state G, prefix geometry includes G→Y1→G loop paths."""
        paths = _enumerate_continuations(
            self.ctrl, "G", horizon_edges=3, geometry="prefix"
        )
        loop_paths = [p for p in paths if p.count("G") > 1]
        self.assertGreater(len(loop_paths), 0,
                           "prefix at G should include Y1→G loop paths")

    def test_first_arrival_at_goal_stops_immediately(self):
        """At state G (which IS a goal), first_arrival returns no paths
        because we're already at the goal and depth > 0 stops extension.
        But depth=0 is the start, so the first hop from G is still enumerated."""
        paths = _enumerate_continuations(
            self.ctrl, "G", horizon_edges=3,
            geometry="first_arrival", goals={"G"}
        )
        # When current IS the goal, depth=0 so the first check doesn't fire.
        # But after one hop to Y1 or Y2, if they reach G again (Y1→G), that stops.
        # So paths like [G, Y1, G] should appear but not [G, Y1, G, Y1]
        for path in paths:
            # Count how many times G appears after position 0
            g_after_start = [i for i, s in enumerate(path) if s == "G" and i > 0]
            if g_after_start:
                # G re-appears → must be at the end (first_arrival stops there)
                self.assertEqual(g_after_start[-1], len(path) - 1,
                                 f"Path {path} continues past re-arrival at G")

    def test_simple_at_goal_excludes_loop_revisit(self):
        """simple geometry at G allows G→Y1 but not G→Y1→G (revisit G)."""
        paths = _enumerate_continuations(
            self.ctrl, "G", horizon_edges=3, geometry="simple"
        )
        for path in paths:
            # No state should appear twice
            self.assertEqual(
                len(path), len(set(path)),
                f"simple path has repeat: {path}"
            )


# ──────────────────────────────────────────────
# Test Class 4: Hybrid Controller on Waypoint Domain
# ──────────────────────────────────────────────

class TestWaypointHybridController(unittest.TestCase):
    """Test hybrid controller behavior on the waypoint domain."""

    def test_greedy_reaches_goal(self):
        """Greedy mode reaches G via W (cheapest route)."""
        L = build_waypoint_landscape()
        ctrl = E0Controller(
            L, waypoint_success,
            hybrid_mode=HybridMode.GREEDY,
        )
        trace = ctrl.run("START", goal="G", max_cycles=10)
        self.assertEqual(trace.path[-1], "G")
        # Greedy should prefer W (lower tension: S=0.15 vs S=0.32)
        self.assertEqual(trace.path[1], "W")

    def test_hybrid_also_reaches_goal(self):
        """Hybrid mode also reaches G."""
        L = build_waypoint_landscape()
        ctrl = E0Controller(
            L, waypoint_success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=4,
            hybrid_goals={"G"},
        )
        trace = ctrl.run("START", goal="G", max_cycles=10)
        self.assertEqual(trace.path[-1], "G")

    def test_overlay_present_in_hybrid_run(self):
        """Hybrid run attaches overlay reports to steps."""
        L = build_waypoint_landscape()
        ctrl = E0Controller(
            L, waypoint_success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=4,
            hybrid_goals={"G"},
        )
        trace = ctrl.run("START", goal="G", max_cycles=10)
        # At least the first step should have an overlay
        self.assertIsNotNone(trace.steps[0].overlay)


if __name__ == "__main__":
    unittest.main()
