"""
C55 — Amplitude Benchmark Tests
==================================
Proves structural claims about all three controller modes
across the 10 benchmark domains.

Key finding: AMPLITUDE_ON_DISAGREE is NOT domain-invariant.
D5 (grid) and D8 (nested cycles) fail under amplitude override.
BORN_SAMPLING inherits these failures stochastically.

Test classes:
  TestGreedyBaseline        (3) — confirms C53 GREEDY results
  TestAmplitudeMode         (5) — AMPLITUDE_ON_DISAGREE behavior
  TestBornSampling          (5) — BORN_SAMPLING behavior
  TestCrossModeDominance    (4) — greedy vs amplitude comparison
  TestAmplitudeFailures     (6) — why D5/D8 fail under amplitude

Total: 23 tests.
"""

from __future__ import annotations

import random
import unittest

from e0_controller.benchmark_amplitude import (
    AmplitudeBenchmarkResult,
    BornTrialSummary,
    ModeResult,
    _run_one,
    _run_born_trials,
    run_amplitude_benchmark,
    results_to_dict,
)
from e0_controller.benchmark_domain_invariance import (
    ALL_DOMAINS,
    build_all_domains,
    build_d5_grid_detour,
    build_d8_nested_cycles,
    build_d3_gordian_trap,
    build_d4_greedy_trap,
    build_d10_bottleneck,
)
from e0_controller.controller import E0Controller, HybridMode


class TestGreedyBaseline(unittest.TestCase):
    """GREEDY baseline matches C53 domain-invariance benchmark."""

    @classmethod
    def setUpClass(cls):
        cls.result = run_amplitude_benchmark(born_trials=5)

    def test_greedy_all_goals(self):
        """GREEDY reaches all 10 goals (C53 confirmed)."""
        for r in self.result.greedy:
            self.assertTrue(r.goal_reached, f"{r.domain}: goal not reached")

    def test_greedy_worst_rating_B(self):
        """GREEDY worst rating is B (same as C53)."""
        worst = max(
            (r.rating for r in self.result.greedy),
            key=lambda x: "ABCDF".index(x),
        )
        self.assertIn(worst, {"A", "B"})

    def test_greedy_no_overrides(self):
        """GREEDY mode never overrides."""
        for r in self.result.greedy:
            self.assertEqual(r.hybrid_overrides, 0,
                             f"{r.domain}: greedy should not override")


class TestAmplitudeMode(unittest.TestCase):
    """AMPLITUDE_ON_DISAGREE mode properties."""

    @classmethod
    def setUpClass(cls):
        cls.result = run_amplitude_benchmark(born_trials=5)

    def test_amplitude_reaches_most_domains(self):
        """Amplitude mode reaches at least 8 of 10 goals."""
        reached = sum(1 for r in self.result.amplitude if r.goal_reached)
        self.assertGreaterEqual(reached, 8)

    def test_amplitude_improves_some_domains(self):
        """Amplitude mode improves rating on at least 2 domains vs greedy."""
        improvements = 0
        for g, a in zip(self.result.greedy, self.result.amplitude):
            if "ABCDF".index(a.rating) < "ABCDF".index(g.rating):
                improvements += 1
        self.assertGreaterEqual(improvements, 2)

    def test_amplitude_has_overrides(self):
        """At least some domains see amplitude overrides."""
        total_overrides = sum(r.hybrid_overrides for r in self.result.amplitude)
        self.assertGreater(total_overrides, 0)

    def test_amplitude_not_domain_invariant(self):
        """AMPLITUDE_ON_DISAGREE is NOT domain-invariant: not all goals reached."""
        all_reached = all(r.goal_reached for r in self.result.amplitude)
        self.assertFalse(all_reached,
                         "If amplitude now reaches all goals, update this test")

    def test_amplitude_d3_d4_d10_improved(self):
        """Domains with traps benefit from amplitude override."""
        trap_domains = {"D3_gordian_trap", "D4_greedy_trap", "D10_bottleneck_funnel"}
        for g, a in zip(self.result.greedy, self.result.amplitude):
            if g.domain in trap_domains:
                self.assertTrue(a.goal_reached,
                                f"{a.domain}: trap domain should still reach goal")
                self.assertLessEqual(
                    "ABCDF".index(a.rating),
                    "ABCDF".index(g.rating),
                    f"{a.domain}: amplitude should not be worse on trap domains",
                )


class TestBornSampling(unittest.TestCase):
    """BORN_SAMPLING mode properties."""

    @classmethod
    def setUpClass(cls):
        cls.result = run_amplitude_benchmark(born_trials=20)

    def test_born_most_domains_high_reach(self):
        """At least 8 domains have ≥ 90% goal-reach rate under Born."""
        high_reach = sum(1 for b in self.result.born if b.goal_reach_rate >= 0.9)
        self.assertGreaterEqual(high_reach, 8)

    def test_born_simple_domains_always_reach(self):
        """Simple domains (D1, D2, D9) reach goal in all Born trials."""
        always = {"D1_linear_chain", "D2_diamond", "D9_wide_dag"}
        for b in self.result.born:
            if b.domain in always:
                self.assertEqual(b.goal_reach_rate, 1.0,
                                 f"{b.domain}: should always reach under Born")

    def test_born_d5_low_reach(self):
        """D5 (grid) has low goal-reach under Born — grid is hard for sampling."""
        for b in self.result.born:
            if b.domain == "D5_grid_detour":
                self.assertLess(b.goal_reach_rate, 0.5,
                                "D5 grid should be hard for Born sampling")

    def test_born_has_overrides(self):
        """Born mode produces overrides (every non-escalated step is override)."""
        for b in self.result.born:
            self.assertGreater(b.mean_overrides, 0,
                               f"{b.domain}: Born should always override")

    def test_born_variance_in_ratings(self):
        """At least some domains show rating variance across Born trials."""
        has_variance = False
        for b in self.result.born:
            if b.best_rating != b.worst_rating:
                has_variance = True
                break
        self.assertTrue(has_variance, "Born should show rating variance")


class TestCrossModeDominance(unittest.TestCase):
    """Cross-mode comparison: greedy dominance properties."""

    @classmethod
    def setUpClass(cls):
        cls.result = run_amplitude_benchmark(born_trials=10)

    def test_greedy_dominates_amplitude_on_goal_reach(self):
        """GREEDY reaches strictly more goals than AMPLITUDE."""
        g_goals = sum(1 for r in self.result.greedy if r.goal_reached)
        a_goals = sum(1 for r in self.result.amplitude if r.goal_reached)
        self.assertGreater(g_goals, a_goals)

    def test_amplitude_has_lower_steps_when_succeeding(self):
        """On domains where amplitude succeeds, it uses ≤ steps vs greedy."""
        fewer_or_equal = 0
        compared = 0
        for g, a in zip(self.result.greedy, self.result.amplitude):
            if a.goal_reached and g.goal_reached:
                compared += 1
                if a.steps <= g.steps:
                    fewer_or_equal += 1
        # At least half of successful domains use fewer/equal steps
        self.assertGreaterEqual(fewer_or_equal, compared // 2)

    def test_greedy_is_domain_invariant(self):
        """GREEDY is domain-invariant: all goals, no mode worse than B."""
        for r in self.result.greedy:
            self.assertTrue(r.goal_reached)
            self.assertIn(r.rating, {"A", "B"})

    def test_amplitude_not_domain_invariant(self):
        """AMPLITUDE is NOT domain-invariant."""
        self.assertFalse(all(r.goal_reached for r in self.result.amplitude))


class TestAmplitudeFailures(unittest.TestCase):
    """Diagnose why D5 and D8 fail under amplitude override."""

    def test_d5_greedy_succeeds(self):
        """D5 is solvable by greedy."""
        spec = build_d5_grid_detour()
        r = _run_one(spec, HybridMode.GREEDY)
        self.assertTrue(r.goal_reached)
        self.assertEqual(r.rating, "A")

    def test_d5_amplitude_fails(self):
        """D5 fails under amplitude override — grid navigation is harmed."""
        spec = build_d5_grid_detour()
        r = _run_one(spec, HybridMode.AMPLITUDE_ON_DISAGREE, horizon=3)
        self.assertFalse(r.goal_reached)

    def test_d5_amplitude_has_overrides(self):
        """D5 amplitude failure involves override decisions."""
        spec = build_d5_grid_detour()
        r = _run_one(spec, HybridMode.AMPLITUDE_ON_DISAGREE, horizon=3)
        self.assertGreater(r.hybrid_overrides, 0)

    def test_d8_greedy_succeeds(self):
        """D8 is solvable by greedy."""
        spec = build_d8_nested_cycles()
        r = _run_one(spec, HybridMode.GREEDY)
        self.assertTrue(r.goal_reached)
        self.assertEqual(r.rating, "A")

    def test_d8_amplitude_fails(self):
        """D8 fails under amplitude override — cycle trapped."""
        spec = build_d8_nested_cycles()
        r = _run_one(spec, HybridMode.AMPLITUDE_ON_DISAGREE, horizon=3)
        self.assertFalse(r.goal_reached)

    def test_d8_amplitude_high_overrides(self):
        """D8 failure shows many overrides — amplitude persistently misleads."""
        spec = build_d8_nested_cycles()
        r = _run_one(spec, HybridMode.AMPLITUDE_ON_DISAGREE, horizon=3)
        self.assertGreater(r.hybrid_overrides, 5,
                           "D8 should show persistent misleading overrides")


if __name__ == "__main__":
    unittest.main()
