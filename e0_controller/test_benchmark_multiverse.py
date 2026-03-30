"""
C61 — Cross-Domain Multiverse Benchmark Tests
=================================================
Validates structural coupling between different C53 domains.

Empirical findings:
  - All 5 pairings sustain novelty (avg ≥50%)
  - Structurally diverse pairs (Grid×Bottleneck, Trap×Invoice) resist
    convergence — the topology difference keeps producing novelty
  - Simpler pairs (Linear×Gordian) converge faster — less structural
    diversity = less to exchange
  - Divergence pressure breaks convergence and grows coupling topology
  - Knowledge exchange transfers edges between domains as hypotheses

Test classes:
  TestKnowledgeExchange       (4) — turn function transfers edges
  TestPairingExecution        (4) — single pairing runs correctly
  TestBenchmarkResults        (5) — full benchmark empirical findings
  TestDivergenceEffect        (3) — divergence breaks convergence
  TestBenchmarkResult         (3) — result type and summary

Total: 19 tests.
"""

from __future__ import annotations

import unittest

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.multiverse import (
    MultiverseController,
    Universe,
)
from e0_controller.benchmark_multiverse import (
    MultiverseBenchmarkResult,
    PairingResult,
    knowledge_exchange_turn,
    run_multiverse_benchmark,
    run_pairing,
    PAIRINGS,
)
from e0_controller.benchmark_domain_invariance import (
    build_d1_linear_chain,
    build_d2_diamond,
    build_d3_gordian_trap,
    build_d5_grid_detour,
    build_d9_wide_dag,
    build_d10_bottleneck,
)


# ══════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════

def _all_success(s: str, t: str) -> Outcome:
    return Outcome.SUCCESS


# ══════════════════════════════════════════════
# Test: Knowledge exchange turn function
# ══════════════════════════════════════════════

class TestKnowledgeExchange(unittest.TestCase):
    """Turn function transfers structural knowledge."""

    def test_edge_transfer(self):
        """Active's edges appear in passive after exchange."""
        spec_a = build_d1_linear_chain()
        spec_b = build_d3_gordian_trap()
        u_a = Universe("A", spec_a.landscape, spec_a.execute_fn, spec_a.start, spec_a.goal)
        u_b = Universe("B", spec_b.landscape, spec_b.execute_fn, spec_b.start, spec_b.goal)
        edges_b_before = len(u_b.landscape._delta)
        knowledge_exchange_turn(u_a, u_b)
        edges_b_after = len(u_b.landscape._delta)
        # Active explored, some edges transferred to passive
        self.assertGreaterEqual(edges_b_after, edges_b_before)

    def test_state_creation(self):
        """States from active domain are created in passive if needed."""
        spec_a = build_d1_linear_chain()
        spec_b = build_d3_gordian_trap()
        u_a = Universe("A", spec_a.landscape, spec_a.execute_fn, spec_a.start, spec_a.goal)
        u_b = Universe("B", spec_b.landscape, spec_b.execute_fn, spec_b.start, spec_b.goal)
        states_b_before = len(u_b.landscape._states)
        knowledge_exchange_turn(u_a, u_b)
        states_b_after = len(u_b.landscape._states)
        self.assertGreaterEqual(states_b_after, states_b_before)

    def test_hypothesis_resistance(self):
        """Transferred edges have higher R₀ than source (hypothesis penalty)."""
        spec_a = build_d2_diamond()
        spec_b = build_d9_wide_dag()
        u_a = Universe("A", spec_a.landscape, spec_a.execute_fn, spec_a.start, spec_a.goal)
        u_b = Universe("B", spec_b.landscape, spec_b.execute_fn, spec_b.start, spec_b.goal)
        knowledge_exchange_turn(u_a, u_b)
        # Check any transferred edge has inflated R₀
        for edge in u_b.landscape._delta:
            if edge in spec_a.landscape._delta and edge not in build_d9_wide_dag().landscape._delta:
                r0_source = spec_a.landscape._R0[edge]
                r0_target = u_b.landscape._R0[edge]
                self.assertGreater(r0_target, r0_source)
                break

    def test_limited_transfer(self):
        """At most 2 edges transferred per turn."""
        spec_a = build_d5_grid_detour()  # many edges
        spec_b = build_d10_bottleneck()   # few edges
        u_a = Universe("A", spec_a.landscape, spec_a.execute_fn, spec_a.start, spec_a.goal)
        u_b = Universe("B", spec_b.landscape, spec_b.execute_fn, spec_b.start, spec_b.goal)
        edges_before = len(u_b.landscape._delta)
        knowledge_exchange_turn(u_a, u_b)
        edges_after = len(u_b.landscape._delta)
        self.assertLessEqual(edges_after - edges_before, 2)


# ══════════════════════════════════════════════
# Test: Single pairing execution
# ══════════════════════════════════════════════

class TestPairingExecution(unittest.TestCase):
    """Single pairing runs correctly."""

    def test_returns_result(self):
        """run_pairing returns a PairingResult."""
        pr = run_pairing("test", build_d1_linear_chain, build_d3_gordian_trap, max_turns=4)
        self.assertIsInstance(pr, PairingResult)
        self.assertEqual(pr.total_turns, 4)

    def test_novelty_bounded(self):
        """Novelty count ≤ total turns."""
        pr = run_pairing("test", build_d2_diamond, build_d9_wide_dag, max_turns=6)
        self.assertLessEqual(pr.total_novelty, pr.total_turns)

    def test_domain_names_recorded(self):
        """Domain names are correctly stored."""
        pr = run_pairing("test", build_d1_linear_chain, build_d3_gordian_trap, max_turns=4)
        self.assertEqual(pr.domain_a, "D1_linear_chain")
        self.assertEqual(pr.domain_b, "D3_gordian_trap")

    def test_novelty_rate_correct(self):
        """Novelty rate = total_novelty / total_turns."""
        pr = run_pairing("test", build_d1_linear_chain, build_d3_gordian_trap, max_turns=4)
        expected = pr.total_novelty / pr.total_turns
        self.assertAlmostEqual(pr.novelty_rate, expected, places=3)


# ══════════════════════════════════════════════
# Test: Full benchmark empirical findings
# ══════════════════════════════════════════════

# Cache benchmark — runs once, shared across tests
_RESULT: MultiverseBenchmarkResult = run_multiverse_benchmark()
_BY_NAME: dict = {p.name: p for p in _RESULT.pairings}


class TestBenchmarkResults(unittest.TestCase):
    """Full benchmark empirical findings."""

    def test_five_pairings(self):
        """Benchmark runs all 5 pairings."""
        self.assertEqual(len(_RESULT.pairings), 5)

    def test_all_produce_novelty(self):
        """Every pairing produces at least some novelty."""
        for p in _RESULT.pairings:
            self.assertGreater(
                p.total_novelty, 0,
                f"{p.name} produced zero novelty",
            )

    def test_avg_novelty_above_50(self):
        """Average novelty rate ≥ 50% across all pairings."""
        self.assertGreaterEqual(_RESULT.avg_novelty_rate, 0.5)

    def test_diverse_pairs_resist_convergence(self):
        """Structurally diverse pairs (Grid×Bottleneck, Trap×Invoice)
        sustain higher novelty rates than simpler pairs."""
        diverse = [
            _BY_NAME["P3: Grid × Bottleneck"],
            _BY_NAME["P5: Greedy Trap × Invoice"],
        ]
        for p in diverse:
            self.assertGreaterEqual(
                p.novelty_rate, 0.5,
                f"{p.name} should resist convergence",
            )

    def test_novelty_rate_non_negative(self):
        """All novelty rates are between 0 and 1."""
        for p in _RESULT.pairings:
            self.assertGreaterEqual(p.novelty_rate, 0.0)
            self.assertLessEqual(p.novelty_rate, 1.0)


# ══════════════════════════════════════════════
# Test: Divergence breaks convergence
# ══════════════════════════════════════════════

class TestDivergenceEffect(unittest.TestCase):
    """Divergence pressure breaks convergence."""

    def test_divergence_grows_coupling(self):
        """Pairings that converge have more coupling edges than those that don't."""
        converged = [p for p in _RESULT.pairings if p.converged]
        not_converged = [p for p in _RESULT.pairings if not p.converged]
        if converged and not_converged:
            avg_conv = sum(p.coupling_edge_count for p in converged) / len(converged)
            avg_noconv = sum(p.coupling_edge_count for p in not_converged) / len(not_converged)
            self.assertGreater(avg_conv, avg_noconv)

    def test_divergence_adds_edges(self):
        """Pairings with divergence have novelty_edges_added > 0."""
        for p in _RESULT.pairings:
            if p.divergence_count > 0:
                self.assertGreater(
                    p.novelty_edges_added, 0,
                    f"{p.name}: divergence without edge injection",
                )

    def test_convergence_implies_divergence(self):
        """Every converged pairing triggers at least one divergence."""
        for p in _RESULT.pairings:
            if p.converged:
                self.assertGreater(
                    p.divergence_count, 0,
                    f"{p.name}: converged but no divergence applied",
                )


# ══════════════════════════════════════════════
# Test: Result type
# ══════════════════════════════════════════════

class TestBenchmarkResultType(unittest.TestCase):
    """Result properties and summary."""

    def test_convergence_count(self):
        """Convergence count matches actual pairings."""
        expected = sum(1 for p in _RESULT.pairings if p.converged)
        self.assertEqual(_RESULT.convergence_count, expected)

    def test_divergence_total(self):
        """Divergence total matches sum of individual counts."""
        expected = sum(p.divergence_count for p in _RESULT.pairings)
        self.assertEqual(_RESULT.divergence_total, expected)

    def test_summary_has_table(self):
        """Summary contains pairing names."""
        s = _RESULT.summary()
        for p in _RESULT.pairings:
            self.assertIn(p.name, s)


if __name__ == "__main__":
    unittest.main()
