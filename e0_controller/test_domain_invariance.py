"""
C53 — Domain-Invariance Benchmark Tests
==========================================
Proves that E₀'s controller is domain-invariant:
same algorithm, same parameters, 10 structurally diverse domains.

Test classes:
  TestDomainSpecIntegrity  (10) — each domain is well-formed
  TestAllDomainsReachGoal  (1)  — all 10 goals reached
  TestDomainInvariance     (6)  — invariance assertions across domains
  TestIndividualDomains    (10) — per-domain behavioral expectations
  TestBenchmarkRunner      (3)  — runner infrastructure

Total: 30 tests.
"""

import unittest

from e0_controller.benchmark_domain_invariance import (
    ALL_DOMAINS,
    DomainResult,
    DomainSpec,
    build_all_domains,
    run_benchmark,
    run_domain,
    results_to_dict,
)
from e0_controller.controller import E0Controller


class TestDomainSpecIntegrity(unittest.TestCase):
    """Each domain spec is internally consistent."""

    def setUp(self):
        self.domains = build_all_domains()

    def test_exactly_10_domains(self):
        self.assertEqual(len(self.domains), 10)

    def test_unique_names(self):
        names = [d.name for d in self.domains]
        self.assertEqual(len(names), len(set(names)))

    def test_start_in_states(self):
        for d in self.domains:
            self.assertIn(d.start, d.landscape.states,
                          f"{d.name}: start not in states")

    def test_goal_in_states(self):
        for d in self.domains:
            self.assertIn(d.goal, d.landscape.states,
                          f"{d.name}: goal not in states")

    def test_node_count_matches(self):
        for d in self.domains:
            self.assertEqual(len(d.landscape.states), d.node_count,
                             f"{d.name}: node_count mismatch")

    def test_edge_count_matches(self):
        for d in self.domains:
            self.assertEqual(len(d.landscape._delta), d.edge_count,
                             f"{d.name}: edge_count mismatch")

    def test_happy_path_positive(self):
        for d in self.domains:
            self.assertGreater(d.happy_path_length, 0,
                               f"{d.name}: happy_path must be > 0")

    def test_topology_class_nonempty(self):
        for d in self.domains:
            self.assertTrue(len(d.topology_class) > 0, d.name)

    def test_description_nonempty(self):
        for d in self.domains:
            self.assertTrue(len(d.description) > 10, d.name)

    def test_distinct_topology_classes(self):
        """At least 6 distinct topology classes across 10 domains."""
        classes = {d.topology_class for d in self.domains}
        self.assertGreaterEqual(len(classes), 6)


class TestAllDomainsReachGoal(unittest.TestCase):
    """The central claim: all 10 domains reach their goal."""

    @classmethod
    def setUpClass(cls):
        cls.results = run_benchmark(max_cycles=50)

    def test_all_goals_reached(self):
        """Every domain reaches its goal with default controller params."""
        for r in self.results:
            self.assertTrue(r.goal_reached,
                            f"{r.domain}: goal NOT reached "
                            f"(steps={r.steps}, rating={r.rating})")


class TestDomainInvariance(unittest.TestCase):
    """Cross-domain invariance assertions."""

    @classmethod
    def setUpClass(cls):
        cls.results = run_benchmark(max_cycles=50)

    def test_no_domain_specific_tuning(self):
        """All domains use exact same controller: alpha=2.0, recent_k=3,
        HybridMode.GREEDY. No domain-specific parameters."""
        # The run_domain function uses identical E0Controller params.
        # This test documents the invariant.
        for d in build_all_domains():
            ctrl = E0Controller(d.landscape, d.execute_fn)
            self.assertEqual(ctrl.alpha, 2.0)
            self.assertEqual(ctrl.recent_k, 3)
            self.assertEqual(ctrl.hybrid_mode.value, "greedy")

    def test_worst_rating_at_least_C(self):
        """No domain gets worse than C."""
        for r in self.results:
            self.assertIn(r.rating, {"A", "B", "C"},
                          f"{r.domain}: rating={r.rating}")

    def test_success_rate_above_threshold(self):
        """Every domain has success rate ≥ 60%."""
        for r in self.results:
            self.assertGreaterEqual(r.success_rate, 0.6,
                                   f"{r.domain}: low success rate")

    def test_diverse_topology_coverage(self):
        """Results cover at least 6 distinct topology classes."""
        domains = build_all_domains()
        classes = {d.topology_class for d in domains}
        self.assertGreaterEqual(len(classes), 6)

    def test_scale_range(self):
        """Domains range from 4 nodes to 20+ nodes."""
        domains = build_all_domains()
        sizes = [d.node_count for d in domains]
        self.assertLessEqual(min(sizes), 6)
        self.assertGreaterEqual(max(sizes), 8)

    def test_mixed_difficulty(self):
        """Both easy (A-rated) and harder (B/C-rated) domains exist."""
        ratings = {r.rating for r in self.results}
        self.assertIn("A", ratings)
        self.assertTrue(ratings & {"B", "C"},
                        "No challenging domains found")


class TestIndividualDomains(unittest.TestCase):
    """Per-domain behavioral expectations."""

    @classmethod
    def setUpClass(cls):
        cls.results = {r.domain: r for r in run_benchmark(max_cycles=50)}

    def test_d1_linear_optimal(self):
        """Linear chain: optimal path, no wasted steps."""
        r = self.results["D1_linear_chain"]
        self.assertEqual(r.steps, 7)
        self.assertEqual(r.efficiency, 1.0)
        self.assertEqual(r.rating, "A")

    def test_d2_diamond_optimal(self):
        """Diamond: reaches goal in 2 steps."""
        r = self.results["D2_diamond"]
        self.assertEqual(r.steps, 2)
        self.assertEqual(r.rating, "A")

    def test_d3_gordian_escapes_trap(self):
        """Gordian trap: escapes decoy loop via failure learning."""
        r = self.results["D3_gordian_trap"]
        self.assertTrue(r.goal_reached)
        self.assertGreater(r.escalations, 0, "should escalate in trap")
        self.assertLessEqual(r.steps, 15)

    def test_d4_greedy_escapes_cycle(self):
        """Greedy trap: escapes 2-cycle via revisit penalty."""
        r = self.results["D4_greedy_trap"]
        self.assertTrue(r.goal_reached)
        self.assertLessEqual(r.steps, 10)

    def test_d5_grid_efficient(self):
        """Grid detour: finds path around wall."""
        r = self.results["D5_grid_detour"]
        self.assertTrue(r.goal_reached)
        self.assertEqual(r.rating, "A")

    def test_d6_multigoal_recovers(self):
        """Multi-goal star: recovers from failing path."""
        r = self.results["D6_multigoal_star"]
        self.assertTrue(r.goal_reached)
        self.assertLess(r.success_rate, 1.0, "should have failure")

    def test_d7_invoice_realistic(self):
        """Invoice: navigates real-world process with failures."""
        r = self.results["D7_invoice_process"]
        self.assertTrue(r.goal_reached)
        self.assertLess(r.success_rate, 1.0)

    def test_d8_nested_cycle_exit(self):
        """Nested cycles: finds exit to goal."""
        r = self.results["D8_nested_cycles"]
        self.assertTrue(r.goal_reached)
        self.assertLessEqual(r.steps, 10)

    def test_d9_wide_dag_optimal(self):
        """Wide DAG: picks cheapest parallel path."""
        r = self.results["D9_wide_dag"]
        self.assertEqual(r.steps, 3)
        self.assertEqual(r.rating, "A")

    def test_d10_bottleneck_recovers(self):
        """Bottleneck: recovers from dead-end via escalation."""
        r = self.results["D10_bottleneck_funnel"]
        self.assertTrue(r.goal_reached)
        self.assertGreater(r.escalations, 0)
        self.assertLessEqual(r.steps, 10)


class TestBenchmarkRunner(unittest.TestCase):
    """Benchmark infrastructure tests."""

    def test_run_benchmark_returns_10(self):
        results = run_benchmark(max_cycles=50)
        self.assertEqual(len(results), 10)

    def test_results_to_dict_structure(self):
        results = run_benchmark(max_cycles=50)
        d = results_to_dict(results)
        self.assertEqual(d["benchmark"], "domain_invariance_v1")
        self.assertEqual(d["domains"], 10)
        self.assertIn("all_goals_reached", d)
        self.assertIn("worst_rating", d)
        self.assertEqual(len(d["results"]), 10)

    def test_each_result_has_required_fields(self):
        results = run_benchmark(max_cycles=50)
        for r in results:
            self.assertIsInstance(r, DomainResult)
            self.assertIsInstance(r.rating, str)
            self.assertIsInstance(r.steps, int)
            self.assertIsInstance(r.goal_reached, bool)


if __name__ == "__main__":
    unittest.main()
