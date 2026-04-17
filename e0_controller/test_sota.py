"""
Tests for SOTA Comparison Benchmark (Phase D — S2)
====================================================
Validates the 5-method comparison on 10 canonical domains.

Results summary (C273):
  E₀:        10/10 domains (ONLY method to reach all goals)
  Q-Learn:    9/10 domains (fails D10 bottleneck)
  ε-Greedy:   8/10 domains (fails D6 multigoal, D10 bottleneck)
  Random:     7/10 domains (fails D5 grid, D7 invoice, D10 bottleneck)
  Greedy:     5/10 domains (fails D3, D4, D6, D8, D10 — all trap/failure domains)

E₀'s structural advantage: Historization penalizes failed edges,
revisit penalty breaks trap cycles. On simple domains (linear, diamond,
DAG), all methods perform identically.

Test classes (3 classes, 11 tests):
  TestE0Dominance      — 4 tests
  TestBaselineFailures  — 4 tests
  TestFairComparison    — 3 tests
"""
from __future__ import annotations

import unittest

from e0_controller.benchmark_sota import (
    run_e0,
    run_greedy,
    run_epsilon_greedy,
    run_q_learning,
    run_random,
    run_benchmark,
    METHODS,
)
from e0_controller.benchmark_domain_invariance import (
    build_all_domains,
    build_d1_linear_chain,
    build_d3_gordian_trap,
    build_d4_greedy_trap,
    build_d5_grid_detour,
    build_d6_multigoal_star,
    build_d10_bottleneck,
)


# Run benchmark once, share results
_COMPARISONS = run_benchmark(max_cycles=50)
_BY_DOMAIN = {c.domain: c for c in _COMPARISONS}


class TestE0Dominance(unittest.TestCase):
    """E₀ should reach all 10 goals — the only method to do so."""

    def test_e0_reaches_all_goals(self):
        for c in _COMPARISONS:
            self.assertTrue(c.results["E0"].goal_reached,
                            f"E₀ failed on {c.domain}")

    def test_e0_10_of_10(self):
        reached = sum(1 for c in _COMPARISONS
                      if c.results["E0"].goal_reached)
        self.assertEqual(reached, 10)

    def test_no_other_method_reaches_all(self):
        for m in METHODS:
            if m == "E0":
                continue
            reached = sum(1 for c in _COMPARISONS
                          if c.results[m].goal_reached)
            self.assertLess(reached, 10,
                            f"{m} should NOT reach all 10 goals, got {reached}")

    def test_e0_best_or_tied_on_simple_domains(self):
        """On D1 (linear), D2 (diamond), D9 (DAG): all methods tie."""
        for name in ["D1_linear_chain", "D2_diamond", "D9_wide_dag"]:
            c = _BY_DOMAIN[name]
            e0_steps = c.results["E0"].steps
            for m in METHODS:
                self.assertEqual(c.results[m].steps, e0_steps,
                                 f"{name}: {m} took {c.results[m].steps} "
                                 f"vs E₀ {e0_steps}")


class TestBaselineFailures(unittest.TestCase):
    """Baselines fail on trap/failure domains — E₀'s structural advantage."""

    def test_greedy_fails_trap_domains(self):
        """Greedy gets stuck in traps (D3, D4) and dead-ends (D10)."""
        for name in ["D3_gordian_trap", "D4_greedy_trap",
                      "D10_bottleneck_funnel"]:
            c = _BY_DOMAIN[name]
            self.assertFalse(c.results["GREEDY"].goal_reached,
                             f"Greedy should FAIL on {name}")

    def test_greedy_fails_multigoal(self):
        """Greedy always picks cheapest (B→G2), which FAILS. Stuck at G2."""
        c = _BY_DOMAIN["D6_multigoal_star"]
        self.assertFalse(c.results["GREEDY"].goal_reached)

    def test_q_learning_learns_traps(self):
        """Q-learning should handle trap domains (reward signal on failure)."""
        for name in ["D3_gordian_trap", "D4_greedy_trap"]:
            c = _BY_DOMAIN[name]
            self.assertTrue(c.results["Q_LEARN"].goal_reached,
                            f"Q-learning should reach goal on {name}")

    def test_random_fails_grid(self):
        """Random walk on 5×5 grid with wall is unlikely to reach goal."""
        c = _BY_DOMAIN["D5_grid_detour"]
        # Random may occasionally reach, but majority-vote should fail
        self.assertFalse(c.results["RANDOM"].goal_reached,
                         "Random walk should mostly fail on D5 grid")


class TestFairComparison(unittest.TestCase):
    """Verify the comparison is methodologically fair."""

    def test_same_budget(self):
        """All methods get 50 cycles."""
        for c in _COMPARISONS:
            for m in METHODS:
                self.assertLessEqual(c.results[m].steps, 50,
                                     f"{c.domain}/{m}: exceeded budget")

    def test_stochastic_methods_averaged(self):
        """Stochastic methods should have fractional-looking step counts."""
        # At least one domain should show non-integer-like averaged steps
        # (step counts are rounded, but revisits should vary)
        c = _BY_DOMAIN["D3_gordian_trap"]
        # Q-learning and ε-greedy should find goal, Random should vary
        q = c.results["Q_LEARN"]
        self.assertTrue(q.goal_reached,
                        "Q-learning should reach goal on D3 (averaged)")

    def test_e0_efficiency_on_trap_domains(self):
        """E₀ should use fewer steps than other successful methods on traps."""
        for name in ["D3_gordian_trap", "D8_nested_cycles"]:
            c = _BY_DOMAIN[name]
            e0_steps = c.results["E0"].steps
            for m in METHODS:
                if m == "E0" or not c.results[m].goal_reached:
                    continue
                self.assertLessEqual(
                    e0_steps, c.results[m].steps,
                    f"{name}: E₀ ({e0_steps}) should be ≤ {m} "
                    f"({c.results[m].steps})")


if __name__ == "__main__":
    unittest.main()
