"""
Tests for Falsification Benchmark (Phase C — S4)
=================================================
Validates the four falsification targets from benchmark_falsification.py.

Results summary (C272):

  F1 — Exploration Depth (SC-5):   E₀ ✓ at all depths 5–500, Greedy ✗
  F2 — Ossification (SC-6/SC-8):   E₀ ADAPTED at all warmup levels 5–200
  F3 — Dense Branching (SC-11):    E₀ ✓ at b=2 only, boundary at b≥3
  F4 — Non-Markov Paths (SC-1/3):  CONFIRMED LIMIT (0% for both methods)

Test classes (4 classes, 13 tests):
  TestF1ExplorationDepth      — 3 tests
  TestF2Ossification          — 3 tests
  TestF3DenseBranching        — 3 tests
  TestF4HistoryDependentFork  — 4 tests
"""
from __future__ import annotations

import unittest

from e0_controller.benchmark_falsification import (
    build_exploration_gauntlet,
    build_dense_tree,
    build_history_fork,
    run_e0,
    run_greedy,
    run_f2_multi_episode,
    E0Controller,
)


# ══════════════════════════════════════════════
# F1 — Exploration Depth Limit (SC-5)
# ══════════════════════════════════════════════

class TestF1ExplorationDepth(unittest.TestCase):
    """E₀ should reach GOAL through distractor-filled gauntlets."""

    def test_e0_reaches_goal_at_depth_10(self):
        domain = build_exploration_gauntlet(depth=10)
        result = run_e0(domain, max_cycles=40)
        self.assertTrue(result.goal_reached,
                        f"E₀ failed at depth=10 in {result.steps} steps")

    def test_e0_reaches_goal_at_depth_100(self):
        domain = build_exploration_gauntlet(depth=100)
        result = run_e0(domain, max_cycles=400)
        self.assertTrue(result.goal_reached,
                        f"E₀ failed at depth=100 in {result.steps} steps")

    def test_greedy_stuck_at_depth_10(self):
        """Greedy has no revisit penalty — gets stuck in distractor loops."""
        domain = build_exploration_gauntlet(depth=10)
        result = run_greedy(domain, max_cycles=40)
        self.assertFalse(result.goal_reached,
                         "Greedy should NOT reach goal (no revisit penalty)")


# ══════════════════════════════════════════════
# F2 — Ossification Under Non-Stationarity (SC-6/SC-8)
# ══════════════════════════════════════════════

class TestF2Ossification(unittest.TestCase):
    """E₀ should adapt when the environment switches paths."""

    def test_adapts_after_short_warmup(self):
        result = run_f2_multi_episode(switch_at=999999,
                                      warmup_episodes=5,
                                      test_episodes=10)
        self.assertTrue(result["adapted"],
                        f"E₀ ossified after 5 warmup episodes, "
                        f"phase2 goal rate={result['phase2_goal_rate']:.0%}")

    def test_adapts_after_long_warmup(self):
        result = run_f2_multi_episode(switch_at=999999,
                                      warmup_episodes=200,
                                      test_episodes=10)
        self.assertTrue(result["adapted"],
                        f"E₀ ossified after 200 warmup episodes, "
                        f"phase2 goal rate={result['phase2_goal_rate']:.0%}")

    def test_phase1_always_succeeds(self):
        result = run_f2_multi_episode(switch_at=999999,
                                      warmup_episodes=50,
                                      test_episodes=10)
        self.assertEqual(result["phase1_goal_rate"], 1.0,
                         "Phase 1 (warmup) should always reach goal")


# ══════════════════════════════════════════════
# F3 — Dense Branching Interference (SC-11)
# ══════════════════════════════════════════════

class TestF3DenseBranching(unittest.TestCase):
    """E₀ advantage degrades with branching factor."""

    def test_e0_succeeds_at_b2(self):
        domain = build_dense_tree(branching=2, depth=4)
        result = run_e0(domain, max_cycles=domain.node_count * 6)
        self.assertTrue(result.goal_reached,
                        f"E₀ should succeed at b=2 d=4 "
                        f"({result.steps}/{domain.node_count * 6} steps)")

    def test_greedy_fails_at_b2(self):
        domain = build_dense_tree(branching=2, depth=4)
        result = run_greedy(domain, max_cycles=domain.node_count * 6)
        self.assertFalse(result.goal_reached,
                         "Greedy should fail at b=2 d=4 (no revisit penalty)")

    def test_boundary_at_b3(self):
        """At b≥3, the branching factor overwhelms the penalty mechanism."""
        domain = build_dense_tree(branching=3, depth=3)
        result = run_e0(domain, max_cycles=domain.node_count * 6)
        # This is the documented structural boundary — E₀ fails here
        self.assertFalse(result.goal_reached,
                         f"E₀ should fail at b=3 d=3 (structural boundary), "
                         f"got {result.steps} steps")


# ══════════════════════════════════════════════
# F4 — History-Dependent Fork (SC-1/SC-3)
# ══════════════════════════════════════════════

class TestF4HistoryDependentFork(unittest.TestCase):
    """E₀ cannot learn non-Markov path dependencies — confirmed limit."""

    def _run_loop(self, max_cycles: int = 200):
        """Run E₀ on the loop domain, return executor stats."""
        domain = build_history_fork()
        ctrl = E0Controller(domain.landscape, domain.execute_fn,
                            alpha=2.0, recent_k=3)
        ctrl.run(domain.start, max_cycles=max_cycles, goal="_UNREACHABLE_")
        return domain.execute_fn

    def test_oracle_succeeds(self):
        """Forcing KEY path yields 100% TRY success — the path matters."""
        domain = build_history_fork()
        current = "S"
        oracle_path = {"S": "KEY", "KEY": "GATE", "GATE": "TRY",
                       "TRY": "S", "ALT": "GATE"}
        for _ in range(200):
            target = oracle_path.get(current)
            if target is None:
                break
            domain.execute_fn(current, target)
            current = target
        ex = domain.execute_fn
        self.assertGreater(ex.try_attempts, 0, "Oracle should attempt TRY")
        self.assertEqual(ex.try_successes, ex.try_attempts,
                         f"Oracle should have 100% success rate, "
                         f"got {ex.try_successes}/{ex.try_attempts}")

    def test_e0_zero_success_rate(self):
        """E₀ cannot discover the KEY path — 0% TRY success."""
        ex = self._run_loop(200)
        self.assertEqual(ex.try_successes, 0,
                         f"E₀ should have 0% TRY success (structural limit), "
                         f"got {ex.try_successes}/{ex.try_attempts}")

    def test_e0_learns_to_avoid_try(self):
        """E₀ learns to avoid GATE→TRY after failures (fewer attempts)."""
        ex_e0 = self._run_loop(200)

        # Greedy baseline: never learns, tries every cycle
        domain_gr = build_history_fork()
        L = domain_gr.landscape
        current = "S"
        for _ in range(200):
            neighbors = sorted(
                [(e.target, L._delta[e] * L._R0[e])
                 for e in L.edges if e.source == current],
                key=lambda x: x[1],
            )
            if not neighbors:
                break
            target = neighbors[0][0]
            domain_gr.execute_fn(current, target)
            current = target
        ex_gr = domain_gr.execute_fn

        self.assertLess(ex_e0.try_attempts, ex_gr.try_attempts,
                        f"E₀ should attempt TRY fewer times than greedy "
                        f"(avoids failures), E₀={ex_e0.try_attempts} "
                        f"vs Greedy={ex_gr.try_attempts}")

    def test_confirmed_structural_limit(self):
        """SC-1/SC-3: edge-local historization cannot learn path dependencies.

        This is the key falsification result. E₀'s historization inscribes
        outcomes on the edge that was just executed. S→ALT always succeeds
        (regardless of later GATE→TRY failure), so nothing at the S decision
        point differentiates ALT from KEY.
        """
        ex = self._run_loop(200)
        self.assertEqual(ex.try_successes, 0,
                         "Confirmed: E₀ cannot learn non-Markov path deps")
        self.assertGreater(ex.try_attempts, 0,
                           "E₀ should have attempted TRY at least once")


if __name__ == "__main__":
    unittest.main()
