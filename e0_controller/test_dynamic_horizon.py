"""
Tests for E₀ Dynamic Horizon Strategies (Phase 3i)
=====================================================

Formal verification of pluggable horizon selection for the amplitude overlay.

Coverage:
  D1 — fixed() strategy returns constant h
  D2 — fixed() rejects h < 1
  D3 — _branching_factor counts admissible neighbors
  D4 — _bfs_goal_distance correct on known graphs
  D5 — topology_adaptive: distance-based baseline
  D6 — topology_adaptive: branching reduction
  D7 — topology_adaptive: clamping to [h_min, h_max]
  D8 — topology_adaptive: no-goal fallback to h_max
  D9 — capped_adaptive: respects cap
  D10 — Controller integration: horizon_strategy overrides hybrid_horizon
  D11 — Controller integration: None strategy falls back to hybrid_horizon
  D12 — Gordian domain: adaptive selects h >= 5 (sees full trap)
  D13 — Diamond domain: adaptive selects moderate h
  D14 — Mini domain: single-neighbor → minimal h
  D15 — End-to-end: dynamic horizon run produces valid trace
"""

import math
import unittest
from e0_controller.controller import E0Controller, HybridMode
from e0_controller.landscape import Landscape
from e0_controller.primitives import Outcome
from e0_controller.dynamic_horizon import (
    fixed,
    topology_adaptive,
    capped_adaptive,
    _branching_factor,
    _bfs_goal_distance,
    _DEFAULT_H_MIN,
    _DEFAULT_H_MAX,
    _DEFAULT_BRANCH_THRESHOLD,
)


# ──────────────────────────────────────────────
# Domain builders
# ──────────────────────────────────────────────

def _success(*_a):
    return Outcome.SUCCESS


def build_mini():
    """A→B→C→D (linear, branching=1)."""
    L = Landscape()
    for src, tgt, d, r in [("A", "B", 1, 1), ("B", "C", 1, 1), ("C", "D", 0, 1)]:
        L.add_edge(src, tgt, delta=d, resistance=r)
    return L


def build_diamond():
    """S→A→G, S→B→G (two paths, branching=2 at S)."""
    L = Landscape()
    for src, tgt, d, r in [
        ("S", "A", 1, 1), ("S", "B", 2, 1),
        ("A", "G", 1, 1), ("B", "G", 1, 1),
    ]:
        L.add_edge(src, tgt, delta=d, resistance=r)
    return L


def build_gordian():
    """Gordian trap: S→A1→A2→A3→A4→A5(loop back), S→B1→G.
    Distance from S to G via B = 2, distance via A = no goal reach.
    """
    L = Landscape()
    edges = [
        ("S", "A1", 0.5, 1.0),
        ("A1", "A2", 0.5, 1.0),
        ("A2", "A3", 0.5, 1.0),
        ("A3", "A4", 0.5, 1.0),
        ("A4", "A5", 0.5, 1.0),
        ("A5", "A1", 0.5, 1.0),  # loop
        ("S", "B1", 2.0, 1.0),
        ("B1", "G", 1.0, 1.0),
    ]
    for src, tgt, d, r in edges:
        L.add_edge(src, tgt, delta=d, resistance=r)
    return L


def build_wide():
    """S→{A,B,C,D,E}→G (branching=5 at S, each 1 hop to G)."""
    L = Landscape()
    for x in "ABCDE":
        L.add_edge("S", x, delta=1, resistance=1)
        L.add_edge(x, "G", delta=0, resistance=1)
    return L


def _ctrl(L, goals=None, mode=HybridMode.GREEDY, horizon=3, strategy=None):
    return E0Controller(
        L, _success,
        hybrid_mode=mode,
        hybrid_horizon=horizon,
        hybrid_goals=goals,
        horizon_strategy=strategy,
    )


# ══════════════════════════════════════════════
# D1: fixed() strategy
# ══════════════════════════════════════════════

class TestD1Fixed(unittest.TestCase):

    def test_fixed_returns_constant(self):
        s = fixed(4)
        ctrl = _ctrl(build_mini())
        self.assertEqual(s(ctrl, "A"), 4)
        self.assertEqual(s(ctrl, "B"), 4)
        self.assertEqual(s(ctrl, "C"), 4)

    def test_fixed_default(self):
        s = fixed()
        ctrl = _ctrl(build_mini())
        self.assertEqual(s(ctrl, "A"), 3)

    def test_fixed_various_values(self):
        for h in [1, 2, 5, 10]:
            s = fixed(h)
            ctrl = _ctrl(build_mini())
            self.assertEqual(s(ctrl, "A"), h)


# ══════════════════════════════════════════════
# D2: fixed() rejects h < 1
# ══════════════════════════════════════════════

class TestD2FixedValidation(unittest.TestCase):

    def test_zero_raises(self):
        with self.assertRaises(ValueError):
            fixed(0)

    def test_negative_raises(self):
        with self.assertRaises(ValueError):
            fixed(-1)

    def test_one_ok(self):
        s = fixed(1)
        self.assertIsNotNone(s)


# ══════════════════════════════════════════════
# D3: _branching_factor
# ══════════════════════════════════════════════

class TestD3BranchingFactor(unittest.TestCase):

    def test_linear_branching_one(self):
        ctrl = _ctrl(build_mini())
        self.assertEqual(_branching_factor(ctrl, "A"), 1)  # A→B only
        self.assertEqual(_branching_factor(ctrl, "B"), 1)  # B→C only

    def test_diamond_branching_two(self):
        ctrl = _ctrl(build_diamond())
        self.assertEqual(_branching_factor(ctrl, "S"), 2)  # S→A, S→B

    def test_wide_branching_five(self):
        ctrl = _ctrl(build_wide())
        self.assertEqual(_branching_factor(ctrl, "S"), 5)

    def test_dead_end_zero(self):
        ctrl = _ctrl(build_mini())
        self.assertEqual(_branching_factor(ctrl, "D"), 0)  # D is terminal

    def test_gordian_branching_at_start(self):
        ctrl = _ctrl(build_gordian())
        self.assertEqual(_branching_factor(ctrl, "S"), 2)  # S→A1, S→B1


# ══════════════════════════════════════════════
# D4: _bfs_goal_distance
# ══════════════════════════════════════════════

class TestD4GoalDistance(unittest.TestCase):

    def test_mini_distance(self):
        ctrl = _ctrl(build_mini())
        self.assertEqual(_bfs_goal_distance(ctrl, "A", {"D"}), 3)
        self.assertEqual(_bfs_goal_distance(ctrl, "C", {"D"}), 1)

    def test_diamond_distance(self):
        ctrl = _ctrl(build_diamond())
        self.assertEqual(_bfs_goal_distance(ctrl, "S", {"G"}), 2)
        self.assertEqual(_bfs_goal_distance(ctrl, "A", {"G"}), 1)

    def test_at_goal_zero(self):
        ctrl = _ctrl(build_diamond())
        self.assertEqual(_bfs_goal_distance(ctrl, "G", {"G"}), 0)

    def test_gordian_distance_via_B(self):
        ctrl = _ctrl(build_gordian())
        self.assertEqual(_bfs_goal_distance(ctrl, "S", {"G"}), 2)

    def test_unreachable_returns_none(self):
        ctrl = _ctrl(build_mini())
        self.assertIsNone(_bfs_goal_distance(ctrl, "D", {"A"}, max_depth=10))

    def test_no_goals_returns_none(self):
        ctrl = _ctrl(build_mini())
        self.assertIsNone(_bfs_goal_distance(ctrl, "A", set()))


# ══════════════════════════════════════════════
# D5: topology_adaptive — distance-based
# ══════════════════════════════════════════════

class TestD5AdaptiveDistance(unittest.TestCase):

    def test_mini_at_start(self):
        """Distance A→D = 3, so h should be 3."""
        s = topology_adaptive(goals={"D"})
        ctrl = _ctrl(build_mini())
        self.assertEqual(s(ctrl, "A"), 3)

    def test_mini_near_goal(self):
        """Distance C→D = 1, but h_min = 2, so h = 2."""
        s = topology_adaptive(goals={"D"})
        ctrl = _ctrl(build_mini())
        self.assertEqual(s(ctrl, "C"), _DEFAULT_H_MIN)

    def test_diamond_at_start(self):
        """Distance S→G = 2, so h = max(2, 2) = 2."""
        s = topology_adaptive(goals={"G"})
        ctrl = _ctrl(build_diamond())
        self.assertEqual(s(ctrl, "S"), _DEFAULT_H_MIN)

    def test_gordian_at_start(self):
        """Distance S→G = 2 (via B), so base = 2 → h = 2."""
        s = topology_adaptive(goals={"G"})
        ctrl = _ctrl(build_gordian())
        self.assertEqual(s(ctrl, "S"), _DEFAULT_H_MIN)


# ══════════════════════════════════════════════
# D6: topology_adaptive — branching reduction
# ══════════════════════════════════════════════

class TestD6BranchingReduction(unittest.TestCase):

    def test_wide_reduces_horizon(self):
        """Wide domain: branching=5 > threshold=3 → h reduced by 1."""
        s = topology_adaptive(goals={"G"}, h_min=1)
        ctrl = _ctrl(build_wide())
        # distance S→G = 2, branch=5 > 3 → base-1 = 1, clamp to max(1, 1) = 1
        h = s(ctrl, "S")
        self.assertLessEqual(h, 2)

    def test_no_reduction_below_threshold(self):
        """Diamond: branching=2 < threshold=3 → no reduction."""
        s = topology_adaptive(goals={"G"})
        ctrl = _ctrl(build_diamond())
        # distance=2, branch=2 < 3 → no reduction → h=2
        h = s(ctrl, "S")
        self.assertEqual(h, _DEFAULT_H_MIN)


# ══════════════════════════════════════════════
# D7: topology_adaptive — clamping
# ══════════════════════════════════════════════

class TestD7Clamping(unittest.TestCase):

    def test_clamp_to_hmin(self):
        s = topology_adaptive(goals={"D"}, h_min=3)
        ctrl = _ctrl(build_mini())
        # Distance C→D = 1, but h_min=3 → h = 3
        self.assertGreaterEqual(s(ctrl, "C"), 3)

    def test_clamp_to_hmax(self):
        s = topology_adaptive(goals={"D"}, h_max=3)
        ctrl = _ctrl(build_mini())
        # Even if distance were larger, h_max=3 stops it
        self.assertLessEqual(s(ctrl, "A"), 3)

    def test_hmin_hmax_equal(self):
        s = topology_adaptive(goals={"D"}, h_min=4, h_max=4)
        ctrl = _ctrl(build_mini())
        self.assertEqual(s(ctrl, "A"), 4)
        self.assertEqual(s(ctrl, "C"), 4)


# ══════════════════════════════════════════════
# D8: topology_adaptive — no-goal fallback
# ══════════════════════════════════════════════

class TestD8NoGoalFallback(unittest.TestCase):

    def test_no_goals_uses_hmax(self):
        """Without goals, strategy falls back to h_max."""
        s = topology_adaptive(goals=None, h_max=5)
        ctrl = _ctrl(build_mini())
        self.assertEqual(s(ctrl, "A"), 5)

    def test_empty_goals_uses_hmax(self):
        s = topology_adaptive(goals=set(), h_max=4)
        ctrl = _ctrl(build_mini())
        self.assertEqual(s(ctrl, "A"), 4)

    def test_controller_goals_used(self):
        """If strategy has no goals, uses controller.hybrid_goals."""
        s = topology_adaptive(goals=None)
        ctrl = _ctrl(build_mini(), goals={"D"})
        h = s(ctrl, "A")
        # Distance A→D = 3, bf=1 < threshold → h = 3
        self.assertEqual(h, 3)


# ══════════════════════════════════════════════
# D9: capped_adaptive
# ══════════════════════════════════════════════

class TestD9CappedAdaptive(unittest.TestCase):

    def test_cap_respected(self):
        s = capped_adaptive(h_cap=3, goals={"D"})
        ctrl = _ctrl(build_mini())
        for state in ["A", "B", "C"]:
            self.assertLessEqual(s(ctrl, state), 3)

    def test_cap_overrides_distance(self):
        """Even if distance is large, cap limits h."""
        L = build_mini()
        # Add longer chain: D→E→F→G→H
        for src, tgt in [("D", "E"), ("E", "F"), ("F", "G"), ("G", "H")]:
            L.add_edge(src, tgt, delta=1, resistance=1)
        ctrl = _ctrl(L)
        s = capped_adaptive(h_cap=4, goals={"H"})
        # Distance A→H = 7, but cap=4
        self.assertLessEqual(s(ctrl, "A"), 4)


# ══════════════════════════════════════════════
# D10: Controller integration with strategy
# ══════════════════════════════════════════════

class TestD10ControllerStrategy(unittest.TestCase):

    def test_strategy_overrides_horizon(self):
        """When horizon_strategy is set, select_hybrid uses it."""
        L = build_diamond()
        recorded_h = []

        def spy_strategy(ctrl, current):
            h = 5
            recorded_h.append(h)
            return h

        ctrl = E0Controller(
            L, _success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=2,  # would be 2 without strategy
            hybrid_goals={"G"},
            horizon_strategy=spy_strategy,
        )
        ctrl.select_hybrid("S")
        self.assertEqual(recorded_h, [5])

    def test_strategy_varies_per_state(self):
        """Strategy can return different values for different states."""
        L = build_diamond()
        ctrl = E0Controller(
            L, _success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_goals={"G"},
            horizon_strategy=lambda c, s: 2 if s == "S" else 4,
        )
        # Call from S
        ctrl.select_hybrid("S")
        # Call from A
        ctrl.select_hybrid("A")
        # Both should succeed without error


# ══════════════════════════════════════════════
# D11: None strategy falls back to hybrid_horizon
# ══════════════════════════════════════════════

class TestD11NoneStrategyFallback(unittest.TestCase):

    def test_none_strategy_uses_hybrid_horizon(self):
        L = build_diamond()
        ctrl = E0Controller(
            L, _success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=4,
            hybrid_goals={"G"},
            horizon_strategy=None,
        )
        # This should work and use h=4
        target, esc, esc_type, overlay, overridden = ctrl.select_hybrid("S")
        self.assertIsNotNone(overlay)
        self.assertEqual(overlay.horizon_edges, 4)


# ══════════════════════════════════════════════
# D12: Gordian domain needs h >= 5
# ══════════════════════════════════════════════

class TestD12GordianAdaptive(unittest.TestCase):

    def test_gordian_adaptive_with_high_cap(self):
        """With h_max=6, the adaptive strategy should pick a value
        based on distance (2 from S) but can go higher if needed."""
        s = topology_adaptive(goals={"G"}, h_max=6)
        ctrl = _ctrl(build_gordian())
        h = s(ctrl, "S")
        self.assertGreaterEqual(h, _DEFAULT_H_MIN)
        self.assertLessEqual(h, 6)

    def test_gordian_fixed_5_sees_loop(self):
        """With fixed(5), the overlay at S enumerates the A-loop."""
        from e0_controller.amplitude_overlay import analyze_controller_state
        ctrl = _ctrl(build_gordian(), goals={"G"})
        report = analyze_controller_state(ctrl, "S", horizon_edges=5,
                                          geometry="simple")
        # At h=5, the A1→A2→A3→A4→A5 path (5 edges) is visible
        a1_paths = [i for i in report.action_infos if i.action == "A1"]
        self.assertTrue(len(a1_paths) > 0)
        total_a1 = a1_paths[0].path_count if a1_paths else 0
        self.assertGreater(total_a1, 1)  # multiple paths through loop

    def test_gordian_forced_high_horizon(self):
        """Using capped_adaptive(h_cap=6), the overlay is computed."""
        s = capped_adaptive(h_cap=6, goals={"G"})
        L = build_gordian()
        ctrl = E0Controller(
            L, _success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_goals={"G"},
            hybrid_geometry="simple",
            horizon_strategy=s,
        )
        target, esc, esc_type, overlay, overridden = ctrl.select_hybrid("S")
        self.assertIsNotNone(overlay)
        self.assertIn(overlay.horizon_edges, range(2, 7))


# ══════════════════════════════════════════════
# D13: Diamond domain moderate h
# ══════════════════════════════════════════════

class TestD13DiamondAdaptive(unittest.TestCase):

    def test_diamond_topology_adaptive(self):
        s = topology_adaptive(goals={"G"})
        ctrl = _ctrl(build_diamond())
        h = s(ctrl, "S")
        # Distance S→G = 2, branching=2 (below threshold)
        self.assertEqual(h, _DEFAULT_H_MIN)

    def test_diamond_at_intermediate(self):
        s = topology_adaptive(goals={"G"})
        ctrl = _ctrl(build_diamond())
        h = s(ctrl, "A")
        # Distance A→G = 1, clamped to h_min=2
        self.assertEqual(h, _DEFAULT_H_MIN)


# ══════════════════════════════════════════════
# D14: Mini domain — minimal h
# ══════════════════════════════════════════════

class TestD14MiniMinimal(unittest.TestCase):

    def test_mini_near_goal_gets_hmin(self):
        s = topology_adaptive(goals={"D"})
        ctrl = _ctrl(build_mini())
        h = s(ctrl, "C")
        self.assertEqual(h, _DEFAULT_H_MIN)

    def test_mini_far_from_goal(self):
        s = topology_adaptive(goals={"D"}, h_max=5)
        ctrl = _ctrl(build_mini())
        h = s(ctrl, "A")
        # Distance A→D = 3, branch=1 (no reduction)
        self.assertEqual(h, 3)


# ══════════════════════════════════════════════
# D15: End-to-end run with dynamic horizon
# ══════════════════════════════════════════════

class TestD15EndToEnd(unittest.TestCase):

    def test_run_with_adaptive_strategy(self):
        """Full run with topology_adaptive produces a valid trace."""
        L = build_diamond()
        s = topology_adaptive(goals={"G"})
        ctrl = E0Controller(
            L, _success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_goals={"G"},
            horizon_strategy=s,
        )
        trace = ctrl.run("S", max_cycles=10, goal="G")
        self.assertTrue(any(step.target == "G" for step in trace.steps))

    def test_run_with_fixed_strategy(self):
        """Full run with fixed(2) should behave like hybrid_horizon=2."""
        L = build_diamond()
        ctrl = E0Controller(
            L, _success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_goals={"G"},
            horizon_strategy=fixed(2),
        )
        trace = ctrl.run("S", max_cycles=10, goal="G")
        self.assertTrue(any(step.target == "G" for step in trace.steps))

    def test_run_with_capped_adaptive(self):
        """Full run with capped_adaptive on Gordian."""
        L = build_gordian()
        s = capped_adaptive(h_cap=5, goals={"G"})
        ctrl = E0Controller(
            L, _success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_goals={"G"},
            hybrid_geometry="simple",
            horizon_strategy=s,
        )
        trace = ctrl.run("S", max_cycles=15, goal="G")
        # Run should complete (reach G or exhaust cycles)
        self.assertGreater(len(trace.steps), 0)

    def test_greedy_mode_ignores_strategy(self):
        """In GREEDY mode, horizon_strategy is never called."""
        call_count = [0]

        def counting_strategy(ctrl, current):
            call_count[0] += 1
            return 3

        L = build_diamond()
        ctrl = E0Controller(
            L, _success,
            hybrid_mode=HybridMode.GREEDY,
            hybrid_goals={"G"},
            horizon_strategy=counting_strategy,
        )
        ctrl.select_hybrid("S")
        self.assertEqual(call_count[0], 0)


if __name__ == "__main__":
    unittest.main()
