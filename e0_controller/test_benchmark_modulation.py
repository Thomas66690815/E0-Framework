"""
C100 — Modulation Benchmark Tests
====================================
Proves that modulation (C98 overlap + C99 inertia) preserves
domain-invariance on 10 standard domains AND provides measurable
benefit on 4 stress domains designed to exercise each modulation.

Test classes:
  TestStressDomainIntegrity    (4)  — each stress domain well-formed
  TestAllDomainsReachGoal      (3)  — all 14 goals reached in every mode
  TestDomainInvariance         (5)  — cross-domain invariance assertions
  TestOverlapEffect            (4)  — overlap changes behavior on target domains
  TestInertiaEffect            (4)  — inertia changes behavior on target domains
  TestModulationNeutrality     (3)  — standard domains unchanged
  TestModulationComposition    (3)  — overlap + inertia compose cleanly
  TestBenchmarkInfrastructure  (3)  — runner, output, JSON serialization

Total: 29 tests.
"""

import unittest

from e0_controller.benchmark_modulation import (
    MODES,
    STRESS_DOMAINS,
    ModulationComparison,
    ModulationResult,
    build_all_modulation_domains,
    build_d11_confused_fork,
    build_d12_triangle_bypass,
    build_d13_confused_grid,
    build_d14_overlap_ladder,
    results_to_dict,
    run_benchmark,
    run_modulation_comparison,
    run_modulation_domain,
)
from e0_controller.benchmark_domain_invariance import ALL_DOMAINS


class TestStressDomainIntegrity(unittest.TestCase):
    """Each stress domain spec is internally consistent."""

    def test_exactly_4_stress_domains(self):
        self.assertEqual(len(STRESS_DOMAINS), 4)

    def test_unique_names(self):
        specs = [b() for b in STRESS_DOMAINS]
        names = [s.name for s in specs]
        self.assertEqual(len(names), len(set(names)))

    def test_start_and_goal_in_states(self):
        for builder in STRESS_DOMAINS:
            spec = builder()
            self.assertIn(spec.start, spec.landscape.states, spec.name)
            self.assertIn(spec.goal, spec.landscape.states, spec.name)

    def test_all_14_domains_buildable(self):
        domains = build_all_modulation_domains()
        self.assertEqual(len(domains), 14)


class TestAllDomainsReachGoal(unittest.TestCase):
    """Central safety claim: all 14 domains reach goal in every mode."""

    @classmethod
    def setUpClass(cls):
        cls.comparisons = run_benchmark(max_cycles=50)

    def test_all_goals_baseline(self):
        for c in self.comparisons:
            self.assertTrue(c.baseline.goal_reached,
                            f"{c.domain} BASELINE: goal not reached")

    def test_all_goals_overlap(self):
        for c in self.comparisons:
            self.assertTrue(c.overlap.goal_reached,
                            f"{c.domain} OVERLAP: goal not reached")

    def test_all_goals_full(self):
        for c in self.comparisons:
            self.assertTrue(c.full.goal_reached,
                            f"{c.domain} FULL: goal not reached")


class TestDomainInvariance(unittest.TestCase):
    """Cross-domain invariance assertions."""

    @classmethod
    def setUpClass(cls):
        cls.comparisons = run_benchmark(max_cycles=50)

    def test_no_mode_increases_steps_on_standard(self):
        """On standard D1-D10, modulation never costs extra steps."""
        for c in self.comparisons[:10]:
            self.assertLessEqual(c.steps_delta_overlap, 0,
                                 f"{c.domain}: OVERLAP added steps")
            self.assertLessEqual(c.steps_delta_full, 0,
                                 f"{c.domain}: FULL added steps")

    def test_no_mode_breaks_efficiency(self):
        """No mode should have 0 efficiency (all reach goal)."""
        for c in self.comparisons:
            self.assertGreater(c.baseline.efficiency, 0, c.domain)
            self.assertGreater(c.overlap.efficiency, 0, c.domain)
            self.assertGreater(c.full.efficiency, 0, c.domain)

    def test_at_least_one_path_change(self):
        """Modulation is not vacuous — it must change at least one path."""
        any_overlap = any(c.path_changed_overlap for c in self.comparisons)
        any_full = any(c.path_changed_full for c in self.comparisons)
        self.assertTrue(any_overlap, "Overlap changed no paths at all")
        self.assertTrue(any_full, "Full changed no paths at all")

    def test_full_changes_more_or_equal_to_overlap(self):
        """FULL includes overlap + inertia, so it should change >= OVERLAP."""
        n_overlap = sum(1 for c in self.comparisons if c.path_changed_overlap)
        n_full = sum(1 for c in self.comparisons if c.path_changed_full)
        self.assertGreaterEqual(n_full, n_overlap)

    def test_14_domains_total(self):
        self.assertEqual(len(self.comparisons), 14)


class TestOverlapEffect(unittest.TestCase):
    """Overlap modulation changes behavior on specific domains."""

    @classmethod
    def setUpClass(cls):
        cls.comparisons = {
            c.domain: c for c in run_benchmark(max_cycles=50)
        }

    def test_d6_overlap_saves_steps(self):
        """D6: overlap avoids failing G2 path → fewer steps."""
        c = self.comparisons["D6_multigoal_star"]
        self.assertLess(c.overlap.steps, c.baseline.steps)
        self.assertTrue(c.path_changed_overlap)

    def test_d12_overlap_prefers_supported(self):
        """D12: overlap selects bypass-supported path."""
        c = self.comparisons["D12_triangle_bypass"]
        self.assertTrue(c.path_changed_overlap)
        self.assertIn("B", c.overlap.path,
                       "Overlap should prefer B (triangle supported)")

    def test_d12_baseline_does_not_use_b(self):
        """D12: baseline goes through A (no overlap awareness)."""
        c = self.comparisons["D12_triangle_bypass"]
        self.assertIn("A", c.baseline.path)

    def test_d14_overlap_neutral(self):
        """D14: overlap ladder — both routes reach goal, may or may not change."""
        c = self.comparisons["D14_overlap_ladder"]
        self.assertTrue(c.overlap.goal_reached)
        self.assertTrue(c.full.goal_reached)


class TestInertiaEffect(unittest.TestCase):
    """Inertia modulation uniquely changes behavior on stress domains."""

    @classmethod
    def setUpClass(cls):
        cls.comparisons = {
            c.domain: c for c in run_benchmark(max_cycles=50)
        }

    def test_d11_inertia_flips_choice(self):
        """D11: baseline picks cheaper confused A, FULL picks clean B."""
        c = self.comparisons["D11_confused_fork"]
        self.assertTrue(c.path_changed_full,
                        "FULL should change D11 path (inertia flips)")
        self.assertFalse(c.path_changed_overlap,
                         "OVERLAP alone should not change D11 (no triangles)")

    def test_d11_baseline_picks_confused(self):
        """D11: baseline goes through A (lower R₀ despite confusion)."""
        c = self.comparisons["D11_confused_fork"]
        self.assertIn("A", c.baseline.path)

    def test_d11_full_avoids_confused(self):
        """D11: FULL avoids A in favor of B."""
        c = self.comparisons["D11_confused_fork"]
        self.assertIn("B", c.full.path)

    def test_d13_inertia_detours(self):
        """D13: FULL takes clean detour instead of confused direct route."""
        c = self.comparisons["D13_confused_grid"]
        self.assertTrue(c.path_changed_full,
                        "FULL should change D13 path (inertia detour)")


class TestModulationNeutrality(unittest.TestCase):
    """Standard domains D1-D10 should be unchanged by modulation."""

    @classmethod
    def setUpClass(cls):
        cls.standard = run_modulation_comparison(ALL_DOMAINS, max_cycles=50)

    def test_standard_domains_same_steps_overlap(self):
        """Overlap doesn't change steps on 8+ of 10 standard domains."""
        unchanged = sum(1 for c in self.standard
                        if c.steps_delta_overlap == 0)
        self.assertGreaterEqual(unchanged, 8,
                                f"Only {unchanged}/10 standard domains unchanged by OVERLAP")

    def test_standard_domains_same_steps_full(self):
        """Full doesn't change steps on 8+ of 10 standard domains."""
        unchanged = sum(1 for c in self.standard
                        if c.steps_delta_full == 0)
        self.assertGreaterEqual(unchanged, 8,
                                f"Only {unchanged}/10 standard domains unchanged by FULL")

    def test_standard_domains_never_worse(self):
        """No standard domain gets worse (more steps) with any modulation."""
        for c in self.standard:
            self.assertLessEqual(c.steps_delta_overlap, 0,
                                 f"{c.domain} OVERLAP: +{c.steps_delta_overlap} steps")
            self.assertLessEqual(c.steps_delta_full, 0,
                                 f"{c.domain} FULL: +{c.steps_delta_full} steps")


class TestModulationComposition(unittest.TestCase):
    """Overlap and inertia compose cleanly without interference."""

    @classmethod
    def setUpClass(cls):
        cls.comparisons = {
            c.domain: c for c in run_benchmark(max_cycles=50)
        }

    def test_full_includes_overlap_changes(self):
        """Every path change in OVERLAP also appears in FULL."""
        for name, c in self.comparisons.items():
            if c.path_changed_overlap:
                # FULL should also differ from baseline
                self.assertTrue(c.path_changed_full,
                                f"{name}: OVERLAP changed path but FULL didn't")

    def test_d6_full_same_as_overlap(self):
        """D6: adding inertia doesn't undo overlap's improvement."""
        c = self.comparisons["D6_multigoal_star"]
        self.assertEqual(c.overlap.steps, c.full.steps)

    def test_d12_full_same_as_overlap(self):
        """D12: adding inertia doesn't undo overlap's path preference."""
        c = self.comparisons["D12_triangle_bypass"]
        self.assertEqual(c.overlap.path, c.full.path)


class TestBenchmarkInfrastructure(unittest.TestCase):
    """Runner, output, serialization work correctly."""

    def test_three_modes(self):
        self.assertEqual(MODES, ["BASELINE", "OVERLAP", "FULL"])

    def test_json_output(self):
        comparisons = run_benchmark(max_cycles=50)
        d = results_to_dict(comparisons)
        self.assertEqual(d["benchmark"], "modulation_c100")
        self.assertEqual(len(d["domains"]), 14)
        self.assertIn("baseline", d["domains"][0])
        self.assertIn("overlap", d["domains"][0])
        self.assertIn("full", d["domains"][0])

    def test_single_domain_runner(self):
        spec = build_d11_confused_fork()
        result = run_modulation_domain(spec, "FULL", max_cycles=50)
        self.assertIsInstance(result, ModulationResult)
        self.assertTrue(result.goal_reached)
        self.assertEqual(result.mode, "FULL")


if __name__ == "__main__":
    unittest.main()
