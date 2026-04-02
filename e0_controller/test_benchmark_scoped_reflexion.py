"""
Tests for C103: Scoped Reflexion Benchmark
============================================
Runs all 10 standard domains under GLOBAL (C57) vs SCOPED (C101)
and validates structural properties of the comparison.

Tests cover:
  1. Goal reach invariance: both modes reach all 10 goals
  2. No regression: scoped never worse than global
  3. Proposal economy: scoped ≤ global proposals
  4. Fresh degeneration: on fresh landscapes, scoped ≡ global
  5. Benchmark structure: result types well-formed
  6. Summary output: human-readable, contains all domains
  7. Locality metrics: scoped reports meaningful locality values
"""

import unittest

from e0_controller.benchmark_scoped_reflexion import (
    ScopedBenchmarkResult,
    ScopedComparison,
    ScopedResult,
    run_scoped_benchmark,
)


# Run once, share across all tests
_RESULT: ScopedBenchmarkResult = run_scoped_benchmark(max_cycles=50)
_BY_DOMAIN = {c.domain: c for c in _RESULT.comparisons}


# ══════════════════════════════════════════════
# 1. Goal reach invariance
# ══════════════════════════════════════════════

class TestGoalReachInvariance(unittest.TestCase):
    """Both modes must reach all 10 goals — regression guard."""

    def test_global_all_goals(self):
        self.assertEqual(_RESULT.global_goal_count, 10)

    def test_scoped_all_goals(self):
        self.assertEqual(_RESULT.scoped_goal_count, 10)

    def test_equal_goal_reach(self):
        self.assertEqual(_RESULT.equal_goal_reach_count, 10)

    def test_per_domain_both_reach(self):
        for c in _RESULT.comparisons:
            with self.subTest(domain=c.domain):
                self.assertTrue(c.global_result.goal_reached)
                self.assertTrue(c.scoped_result.goal_reached)


# ══════════════════════════════════════════════
# 2. No regression
# ══════════════════════════════════════════════

class TestNoRegression(unittest.TestCase):
    """Scoped reflexion never degrades performance."""

    def test_scoped_never_loses_goal(self):
        """If global reaches goal, scoped does too."""
        for c in _RESULT.comparisons:
            with self.subTest(domain=c.domain):
                if c.global_result.goal_reached:
                    self.assertTrue(c.scoped_result.goal_reached,
                                    f"Scoped lost goal on {c.domain}")

    def test_equal_or_fewer_proposals_all(self):
        """Scoped produces ≤ proposals on all domains."""
        self.assertEqual(_RESULT.equal_or_fewer_count, 10)

    def test_steps_bounded(self):
        """Scoped steps within ±2 of global (bounded overhead)."""
        for c in _RESULT.comparisons:
            with self.subTest(domain=c.domain):
                self.assertLessEqual(abs(c.steps_delta), 2,
                                     f"{c.domain}: steps_delta={c.steps_delta}")


# ══════════════════════════════════════════════
# 3. Fresh degeneration
# ══════════════════════════════════════════════

class TestFreshDegeneration(unittest.TestCase):
    """On fresh landscapes (minimal historization), scoped ≡ global."""

    def test_connected_domains_no_reflexion(self):
        """D1-D5, D7-D9: connected → no frontier → 0 proposals both modes."""
        connected = ["D1_linear_chain", "D2_diamond", "D3_gordian_trap",
                      "D4_greedy_trap", "D5_grid_detour",
                      "D7_invoice_process", "D8_nested_cycles",
                      "D9_wide_dag"]
        for name in connected:
            c = _BY_DOMAIN[name]
            with self.subTest(domain=name):
                self.assertEqual(c.global_result.proposals, 0)
                self.assertEqual(c.scoped_result.proposals, 0)

    def test_identical_ratings_connected(self):
        """Connected domains have same rating in both modes."""
        for c in _RESULT.comparisons:
            if c.global_result.proposals == 0 and c.scoped_result.proposals == 0:
                with self.subTest(domain=c.domain):
                    self.assertEqual(c.global_result.rating,
                                     c.scoped_result.rating)

    def test_identical_steps_connected(self):
        """Connected domains have same steps in both modes."""
        for c in _RESULT.comparisons:
            if c.global_result.proposals == 0 and c.scoped_result.proposals == 0:
                with self.subTest(domain=c.domain):
                    self.assertEqual(c.global_result.steps,
                                     c.scoped_result.steps)


# ══════════════════════════════════════════════
# 4. Frontier domains
# ══════════════════════════════════════════════

class TestFrontierDomains(unittest.TestCase):
    """Domains with frontier disconnection trigger reflexion."""

    def test_frontier_domains_have_proposals(self):
        """D6 and D10 trigger proposals in at least one mode."""
        frontier_domains = ["D6_multigoal_star", "D10_bottleneck_funnel"]
        for name in frontier_domains:
            c = _BY_DOMAIN[name]
            with self.subTest(domain=name):
                total = c.global_result.proposals + c.scoped_result.proposals
                self.assertGreater(total, 0,
                                   f"{name}: expected proposals on frontier domain")

    def test_frontier_scoped_has_locality(self):
        """Frontier domains report locality metrics when scoped."""
        for c in _RESULT.comparisons:
            if c.scoped_result.scope_count > 0:
                with self.subTest(domain=c.domain):
                    self.assertGreaterEqual(c.scoped_result.avg_locality, 0.0)
                    self.assertLess(c.scoped_result.avg_locality, 1.0)

    def test_fresh_frontier_low_locality(self):
        """Frontier on fresh landscape → locality near 0 (global degeneration)."""
        for c in _RESULT.comparisons:
            if c.scoped_result.scope_count > 0:
                with self.subTest(domain=c.domain):
                    self.assertLess(c.scoped_result.avg_locality, 0.3,
                                    f"{c.domain}: expected low locality on fresh")


# ══════════════════════════════════════════════
# 5. Benchmark structure
# ══════════════════════════════════════════════

class TestBenchmarkStructure(unittest.TestCase):
    """Result types are well-formed."""

    def test_10_comparisons(self):
        self.assertEqual(len(_RESULT.comparisons), 10)

    def test_comparison_types(self):
        for c in _RESULT.comparisons:
            self.assertIsInstance(c, ScopedComparison)
            self.assertIsInstance(c.global_result, ScopedResult)
            self.assertIsInstance(c.scoped_result, ScopedResult)

    def test_modes(self):
        for c in _RESULT.comparisons:
            self.assertEqual(c.global_result.mode, "GLOBAL")
            self.assertEqual(c.scoped_result.mode, "SCOPED")

    def test_domain_names_match(self):
        for c in _RESULT.comparisons:
            self.assertEqual(c.domain, c.global_result.domain)
            self.assertEqual(c.domain, c.scoped_result.domain)

    def test_efficiency_range(self):
        for c in _RESULT.comparisons:
            for r in [c.global_result, c.scoped_result]:
                with self.subTest(domain=c.domain, mode=r.mode):
                    self.assertGreaterEqual(r.efficiency, 0.0)
                    self.assertLessEqual(r.efficiency, 1.0)

    def test_global_locality_negative(self):
        """GLOBAL mode reports -1 for locality (not applicable)."""
        for c in _RESULT.comparisons:
            self.assertEqual(c.global_result.avg_locality, -1.0)
            self.assertEqual(c.global_result.max_locality, -1.0)
            self.assertEqual(c.global_result.scope_count, 0)


# ══════════════════════════════════════════════
# 6. Summary output
# ══════════════════════════════════════════════

class TestSummary(unittest.TestCase):
    """Summary output is human-readable."""

    def test_summary_contains_header(self):
        s = _RESULT.summary()
        self.assertIn("Scoped Reflexion Benchmark", s)

    def test_summary_contains_all_domains(self):
        s = _RESULT.summary()
        for c in _RESULT.comparisons:
            self.assertIn(c.domain, s)

    def test_summary_contains_goal_counts(self):
        s = _RESULT.summary()
        self.assertIn("GLOBAL=10/10", s)
        self.assertIn("SCOPED=10/10", s)


if __name__ == "__main__":
    unittest.main()
