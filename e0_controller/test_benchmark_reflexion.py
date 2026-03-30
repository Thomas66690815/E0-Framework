"""
C58 — Reflexion Benchmark Tests
==================================
Validates reflexion impact across all 10 C53 domains × 3 Stufen.

Key findings:
  - All 10 domains reach goal under all 3 Stufen (no frontier gaps)
  - Reactive reflexion (S1R) never produces proposals (no stuckness)
  - Proactive reflexion (S2) improves D6 and D10 (shortcut proposals)
  - 8/10 domains: reflexion is neutral (all connected, no frontier)
  - D10: proactive achieves rating upgrade B→A (6→2 steps)

Test classes:
  TestGoalReachInvariance    (3) — all Stufen reach all goals
  TestReactiveNeutral        (3) — S1R never proposes on connected domains
  TestProactiveAdvantage     (4) — D6/D10 benefit from proactive
  TestNeutralDomains         (4) — 8 domains where reflexion is irrelevant
  TestBenchmarkStructure     (3) — result types and summary
  TestDomainSpecificInsights (3) — D10 rating upgrade, D6 step reduction

Total: 20 tests.
"""

from __future__ import annotations

import unittest

from e0_controller.benchmark_reflexion import (
    DomainComparison,
    ReflexionBenchmarkResult,
    StufeResult,
    run_reflexion_benchmark,
    _run_domain,
)
from e0_controller.benchmark_domain_invariance import (
    ALL_DOMAINS,
    build_d1_linear_chain,
    build_d2_diamond,
    build_d3_gordian_trap,
    build_d4_greedy_trap,
    build_d5_grid_detour,
    build_d6_multigoal_star,
    build_d7_invoice,
    build_d8_nested_cycles,
    build_d9_wide_dag,
    build_d10_bottleneck,
)


# Run benchmark once, share across all tests
_RESULT: ReflexionBenchmarkResult = run_reflexion_benchmark()
_BY_DOMAIN = {c.domain: c for c in _RESULT.comparisons}


# ══════════════════════════════════════════════
# Test: Goal reach invariance
# ══════════════════════════════════════════════

class TestGoalReachInvariance(unittest.TestCase):
    """All 10 domains reach goal under every Stufe."""

    def test_s1_all_goals(self):
        """Stufe 1 (standard) reaches all 10 goals."""
        self.assertEqual(_RESULT.s1_goal_count, 10)

    def test_s1r_all_goals(self):
        """Stufe 1R (reactive) reaches all 10 goals."""
        self.assertEqual(_RESULT.s1r_goal_count, 10)

    def test_s2_all_goals(self):
        """Stufe 2 (proactive) reaches all 10 goals."""
        self.assertEqual(_RESULT.s2_goal_count, 10)


# ══════════════════════════════════════════════
# Test: Reactive is neutral on connected domains
# ══════════════════════════════════════════════

class TestReactiveNeutral(unittest.TestCase):
    """Reactive reflexion never proposes on connected domains."""

    def test_no_reactive_proposals(self):
        """S1R generates 0 proposals across all 10 domains."""
        total_proposals = sum(c.s1r.proposals for c in _RESULT.comparisons)
        self.assertEqual(total_proposals, 0)

    def test_reactive_same_as_standard(self):
        """S1R results match S1 exactly (same steps, same rating)."""
        for c in _RESULT.comparisons:
            self.assertEqual(c.s1.rating, c.s1r.rating,
                             f"{c.domain}: rating mismatch")
            self.assertEqual(c.s1.steps, c.s1r.steps,
                             f"{c.domain}: steps mismatch")

    def test_reactive_never_helps(self):
        """reflexion_helps is never triggered by reactive alone."""
        # If S1 already reaches goal and S1R doesn't improve,
        # reflexion_helps only triggers if S2 improves
        for c in _RESULT.comparisons:
            s1r_better = (c.s1r.goal_reached and not c.s1.goal_reached)
            self.assertFalse(s1r_better, f"{c.domain}: S1R should not beat S1")


# ══════════════════════════════════════════════
# Test: Proactive advantage on specific domains
# ══════════════════════════════════════════════

class TestProactiveAdvantage(unittest.TestCase):
    """D6 and D10 benefit from proactive reflexion."""

    def test_d10_proactive_fewer_steps(self):
        """D10: proactive uses fewer steps than standard."""
        c = _BY_DOMAIN["D10_bottleneck_funnel"]
        self.assertLess(c.s2.steps, c.s1.steps)

    def test_d10_proactive_generates_proposals(self):
        """D10: proactive generates proposals (shortcut edges)."""
        c = _BY_DOMAIN["D10_bottleneck_funnel"]
        self.assertGreater(c.s2.proposals, 0)

    def test_d6_proactive_fewer_steps(self):
        """D6: proactive uses fewer or equal steps."""
        c = _BY_DOMAIN["D6_multigoal_star"]
        self.assertLessEqual(c.s2.steps, c.s1.steps)

    def test_proactive_advantage_count(self):
        """At least 2 domains show proactive advantage."""
        self.assertGreaterEqual(_RESULT.proactive_advantage_count, 2)


# ══════════════════════════════════════════════
# Test: Neutral domains (reflexion irrelevant)
# ══════════════════════════════════════════════

class TestNeutralDomains(unittest.TestCase):
    """8 domains where reflexion has no effect."""

    NEUTRAL_DOMAINS = [
        "D1_linear_chain", "D2_diamond", "D3_gordian_trap",
        "D4_greedy_trap", "D5_grid_detour", "D7_invoice_process",
        "D8_nested_cycles", "D9_wide_dag",
    ]

    def test_neutral_no_proposals(self):
        """Neutral domains: no proposals under any Stufe."""
        for name in self.NEUTRAL_DOMAINS:
            c = _BY_DOMAIN[name]
            self.assertEqual(c.s1.proposals, 0, f"{name}: S1 proposals")
            self.assertEqual(c.s1r.proposals, 0, f"{name}: S1R proposals")
            self.assertEqual(c.s2.proposals, 0, f"{name}: S2 proposals")

    def test_neutral_same_rating(self):
        """Neutral domains: same rating across all Stufen."""
        for name in self.NEUTRAL_DOMAINS:
            c = _BY_DOMAIN[name]
            self.assertEqual(c.s1.rating, c.s2.rating,
                             f"{name}: S1 vs S2 rating")

    def test_neutral_same_steps(self):
        """Neutral domains: same steps across all Stufen."""
        for name in self.NEUTRAL_DOMAINS:
            c = _BY_DOMAIN[name]
            self.assertEqual(c.s1.steps, c.s2.steps,
                             f"{name}: S1 vs S2 steps")

    def test_neutral_reflexion_does_not_help(self):
        """Neutral domains: reflexion_helps is False."""
        for name in self.NEUTRAL_DOMAINS:
            c = _BY_DOMAIN[name]
            self.assertFalse(c.reflexion_helps, f"{name} should be neutral")


# ══════════════════════════════════════════════
# Test: Benchmark structure
# ══════════════════════════════════════════════

class TestBenchmarkStructure(unittest.TestCase):
    """Result types and summary formatting."""

    def test_result_has_10_comparisons(self):
        """Benchmark produces exactly 10 domain comparisons."""
        self.assertEqual(len(_RESULT.comparisons), 10)

    def test_summary_format(self):
        """Summary string is valid and non-empty."""
        s = _RESULT.summary()
        self.assertIn("Reflexion Benchmark", s)
        self.assertIn("Goal reach", s)
        self.assertIn("S1=", s)

    def test_all_domains_present(self):
        """All 10 C53 domain names appear in results."""
        names = {c.domain for c in _RESULT.comparisons}
        self.assertEqual(len(names), 10)


# ══════════════════════════════════════════════
# Test: Domain-specific insights
# ══════════════════════════════════════════════

class TestDomainSpecificInsights(unittest.TestCase):
    """Specific structural insights from the benchmark."""

    def test_d10_rating_upgrade(self):
        """D10: proactive upgrades rating (efficiency improvement)."""
        c = _BY_DOMAIN["D10_bottleneck_funnel"]
        # S2 should have better or equal rating
        rank = {"A": 0, "B": 1, "C": 2, "D": 3, "F": 4}
        self.assertLessEqual(rank[c.s2.rating], rank[c.s1.rating])

    def test_connected_domains_no_frontier(self):
        """All C53 domains are connected — no frontier gaps exist.
        This explains why reactive reflexion never triggers."""
        # Confirmed by: S1R proposals = 0 across all domains
        self.assertEqual(
            sum(c.s1r.proposals for c in _RESULT.comparisons), 0,
        )

    def test_proactive_shortcut_mechanism(self):
        """Proactive creates shortcuts via goal-proximity proposals.
        This is different from frontier-bridging — it's topology enrichment."""
        # Domains where proactive proposes: proposals > 0 and goal reached
        enriched = [c for c in _RESULT.comparisons if c.s2.proposals > 0]
        for c in enriched:
            self.assertTrue(c.s2.goal_reached)
            self.assertLessEqual(c.s2.steps, c.s1.steps)


if __name__ == "__main__":
    unittest.main()
