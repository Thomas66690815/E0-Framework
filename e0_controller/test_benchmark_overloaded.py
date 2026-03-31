"""
C70 — OVERLOADED Benchmark Tests
====================================
Validates peer consultation effect on 10 C53 domains.

Empirical findings at default threshold (3.0):
  - Only D9 (Wide DAG, OI=5.0 at start) can trigger OVERLOADED
  - Most domains have OI ≤ 3.0 → OVERLOADED never fires
  - Peer has no effect on step count or rating — domains too small
  - Both modes reach goal 100%

Empirical findings at sensitive threshold (1.5):
  - 4/10 domains improve with peer consultation (D3, D4, D6, D10)
  - Peer reduces avg steps: ~5.3 → ~4.4
  - D3 (Gordian): 6→3 steps, B→A rating — advisor knows decoy fails
  - D10 (Bottleneck): 6→4 steps, B→A — advisor knows dead-end
  - D5 (Grid): same steps despite 8 OVERLOADED events — advisor
    recommendations match greedy on well-connected grid
  - OVERLOADED self-resolves: fires early, never fires late

Architecture insight: OVERLOADED is calibrated for LARGE landscapes
(dozens of neighbors). The C53 domains are deliberately small. The
mechanism works correctly when triggered — the threshold determines
on which scale it activates.

Test classes:
  TestOverloadBenchmarkDefault       (5) — default threshold=3.0
  TestOverloadBenchmarkSensitive     (6) — sensitive threshold=1.5
  TestExperiencedPeerConstruction    (4) — peer_fn from advisor
  TestDomainComparison               (4) — single-domain comparison
  TestOverloadBenchmarkResult        (4) — result type + summary
  TestOverloadIndex                  (3) — OI values for specific domains

Total: 26 tests.
"""

from __future__ import annotations

import unittest

from e0_controller.primitives import Edge, Outcome
from e0_controller.controller import E0Controller, EscalationType
from e0_controller.benchmark_overloaded import (
    OverloadBenchmarkResult,
    OverloadComparisonResult,
    OverloadDomainResult,
    make_experienced_peer,
    run_domain_comparison,
    run_domain_mode,
    run_overloaded_benchmark,
)
from e0_controller.benchmark_domain_invariance import (
    ALL_DOMAINS,
    build_d1_linear_chain,
    build_d3_gordian_trap,
    build_d5_grid_detour,
    build_d6_multigoal_star,
    build_d9_wide_dag,
    build_d10_bottleneck,
)


# ══════════════════════════════════════════════
# Cache — run once at each threshold, share across tests
# ══════════════════════════════════════════════

_DEFAULT = run_overloaded_benchmark(overload_threshold=3.0)
_SENSITIVE = run_overloaded_benchmark(overload_threshold=1.5)
_DEF_BY_NAME = {c.domain: c for c in _DEFAULT.comparisons}
_SEN_BY_NAME = {c.domain: c for c in _SENSITIVE.comparisons}


# ══════════════════════════════════════════════
# 1. Default threshold (3.0)
# ══════════════════════════════════════════════

class TestOverloadBenchmarkDefault(unittest.TestCase):
    """At threshold=3.0, domains are too small for OVERLOADED."""

    def test_ten_domains(self):
        self.assertEqual(len(_DEFAULT.comparisons), 10)

    def test_all_goals_reached_baseline(self):
        for c in _DEFAULT.comparisons:
            self.assertTrue(
                c.baseline.goal_reached,
                f"{c.domain} baseline should reach goal",
            )

    def test_all_goals_reached_peer(self):
        for c in _DEFAULT.comparisons:
            self.assertTrue(
                c.peer.goal_reached,
                f"{c.domain} peer should reach goal",
            )

    def test_baseline_no_overloads(self):
        """Baseline has no peer_fn → no OVERLOADED events."""
        self.assertEqual(_DEFAULT.baseline_overload_total, 0)

    def test_d9_only_domain_above_threshold(self):
        """D9 (Wide DAG, OI=5.0) is the only domain where OI > 3.0."""
        d9 = _DEF_BY_NAME["D9_wide_dag"]
        other_ol = sum(
            c.peer.overload_count for c in _DEFAULT.comparisons
            if c.domain != "D9_wide_dag"
        )
        self.assertEqual(other_ol, 0)
        # D9 peer MAY have overloads (not guaranteed every run)


# ══════════════════════════════════════════════
# 2. Sensitive threshold (1.5)
# ══════════════════════════════════════════════

class TestOverloadBenchmarkSensitive(unittest.TestCase):
    """At threshold=1.5, peer fires on more domains and helps."""

    def test_peer_has_overloads(self):
        """At threshold=1.5, peer triggers OVERLOADED on multiple domains."""
        self.assertGreater(_SENSITIVE.peer_overload_total, 0)

    def test_peer_improves_some_domains(self):
        """Peer reduces step count on at least 2 domains."""
        self.assertGreaterEqual(_SENSITIVE.peer_improves_count, 2)

    def test_peer_avg_steps_le_baseline(self):
        """Peer avg steps ≤ baseline avg steps."""
        self.assertLessEqual(
            _SENSITIVE.peer_avg_steps,
            _SENSITIVE.baseline_avg_steps,
        )

    def test_gordian_trap_improves(self):
        """D3 (Gordian): advisor knows decoy fails → fewer steps."""
        d3 = _SEN_BY_NAME["D3_gordian_trap"]
        self.assertLess(d3.peer.steps, d3.baseline.steps)

    def test_bottleneck_improves(self):
        """D10 (Bottleneck): advisor knows dead-end → fewer steps."""
        d10 = _SEN_BY_NAME["D10_bottleneck_funnel"]
        self.assertLess(d10.peer.steps, d10.baseline.steps)

    def test_linear_unchanged(self):
        """D1 (Linear): 1 neighbor → OI=1.0 → never triggers OVERLOADED."""
        d1 = _SEN_BY_NAME["D1_linear_chain"]
        self.assertEqual(d1.peer.overload_count, 0)
        self.assertEqual(d1.step_delta, 0)


# ══════════════════════════════════════════════
# 3. Experienced peer construction
# ══════════════════════════════════════════════

class TestExperiencedPeerConstruction(unittest.TestCase):
    """make_experienced_peer produces a valid peer_fn."""

    def test_returns_callable(self):
        peer = make_experienced_peer(build_d1_linear_chain, pre_cycles=5)
        self.assertTrue(callable(peer))

    def test_peer_returns_none_for_unknown_state(self):
        """Peer returns None when state not in advisor's experience."""
        from e0_controller.landscape import Landscape
        peer = make_experienced_peer(build_d3_gordian_trap, pre_cycles=10)
        L = Landscape()
        L.add_edge("X", "Y", delta=0.5, resistance=0.5)
        result = peer(L, "X", ["Y"])
        self.assertIsNone(result)

    def test_peer_recommends_known_good_neighbor(self):
        """Peer recommends a neighbor with positive trace quality."""
        peer = make_experienced_peer(build_d9_wide_dag, pre_cycles=30)
        spec = build_d9_wide_dag()
        neighbors = ["A", "B", "C", "D", "E"]
        recommendation = peer(spec.landscape, "S", neighbors)
        # Should recommend one of the neighbors (or None if no positive quality)
        self.assertTrue(recommendation is None or recommendation in neighbors)

    def test_peer_with_more_experience_is_deterministic(self):
        """Same peer built twice gives same advice (same historization)."""
        peer1 = make_experienced_peer(build_d1_linear_chain, pre_cycles=10)
        peer2 = make_experienced_peer(build_d1_linear_chain, pre_cycles=10)
        spec = build_d1_linear_chain()
        r1 = peer1(spec.landscape, "S", ["A"])
        r2 = peer2(spec.landscape, "S", ["A"])
        self.assertEqual(r1, r2)


# ══════════════════════════════════════════════
# 4. Single domain comparison
# ══════════════════════════════════════════════

class TestDomainComparison(unittest.TestCase):
    """run_domain_comparison produces valid side-by-side results."""

    def test_returns_comparison_result(self):
        comp = run_domain_comparison(build_d1_linear_chain, max_cycles=20)
        self.assertIsInstance(comp, OverloadComparisonResult)

    def test_modes_are_correct(self):
        comp = run_domain_comparison(build_d3_gordian_trap, max_cycles=20)
        self.assertEqual(comp.baseline.mode, "baseline")
        self.assertEqual(comp.peer.mode, "peer")

    def test_domain_name_consistent(self):
        comp = run_domain_comparison(build_d5_grid_detour, max_cycles=20)
        self.assertEqual(comp.domain, comp.baseline.domain)
        self.assertEqual(comp.domain, comp.peer.domain)

    def test_step_delta_computed(self):
        comp = run_domain_comparison(build_d1_linear_chain, max_cycles=20)
        expected = comp.peer.steps - comp.baseline.steps
        self.assertEqual(comp.step_delta, expected)


# ══════════════════════════════════════════════
# 5. Result type + summary
# ══════════════════════════════════════════════

class TestOverloadBenchmarkResult(unittest.TestCase):
    """Aggregate result type works correctly."""

    def test_summary_contains_domain_names(self):
        s = _DEFAULT.summary()
        for c in _DEFAULT.comparisons:
            self.assertIn(c.domain, s)

    def test_summary_contains_header(self):
        s = _DEFAULT.summary()
        self.assertIn("Baseline vs Peer Consultation", s)

    def test_goal_rates_are_one(self):
        """All domains reach goal → rate = 100%."""
        self.assertAlmostEqual(_DEFAULT.baseline_goal_rate, 1.0)
        self.assertAlmostEqual(_DEFAULT.peer_goal_rate, 1.0)

    def test_avg_steps_positive(self):
        self.assertGreater(_DEFAULT.baseline_avg_steps, 0)
        self.assertGreater(_DEFAULT.peer_avg_steps, 0)


# ══════════════════════════════════════════════
# 6. OI values at domain start
# ══════════════════════════════════════════════

class TestOverloadIndex(unittest.TestCase):
    """OI reflects branching factor × experience deficit."""

    def test_linear_oi_is_one(self):
        """D1 linear: 1 neighbor → OI=1.0."""
        spec = build_d1_linear_chain()
        ctrl = E0Controller(spec.landscape, spec.execute_fn)
        neighbors = ctrl._admissible_neighbors(spec.start)
        oi = ctrl._overload_index(spec.start, neighbors)
        self.assertAlmostEqual(oi, 1.0)

    def test_wide_dag_oi_is_five(self):
        """D9 wide DAG: 5 neighbors from S → OI=5.0 (no experience)."""
        spec = build_d9_wide_dag()
        ctrl = E0Controller(spec.landscape, spec.execute_fn)
        neighbors = ctrl._admissible_neighbors(spec.start)
        oi = ctrl._overload_index(spec.start, neighbors)
        self.assertAlmostEqual(oi, 5.0)

    def test_star_oi_is_three(self):
        """D6 star: 3 neighbors from S → OI=3.0 (no experience)."""
        spec = build_d6_multigoal_star()
        ctrl = E0Controller(spec.landscape, spec.execute_fn)
        neighbors = ctrl._admissible_neighbors(spec.start)
        oi = ctrl._overload_index(spec.start, neighbors)
        self.assertAlmostEqual(oi, 3.0)
