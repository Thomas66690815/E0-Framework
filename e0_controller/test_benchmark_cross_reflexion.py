"""
C69 — Cross-Reflexion Benchmark Tests
========================================
Compares knowledge_exchange_turn (C61) vs cross_reflexion_turn (C62)
on the same 5 domain pairings.

Empirical finding:
  Knowledge exchange wins ALL 5 pairings.  Reason: edge copying fires
  every turn (unconditional), while cross-reflexion only fires at
  frontiers (stuck, no path to goal).  Early turns produce no frontier
  → no structural change → fast convergence at T2.

  This reveals a key constraint of C62: frontier-gated coupling trades
  precision (edges only when needed) for frequency (too few injections
  to sustain novelty).  The discount doesn't help if you never fire.

  The architecture implication: a HYBRID strategy (copy + create) or
  relaxing the frontier gate may be needed for C62 to compete.

Test classes:
  TestComparisonPairingExecution    (5) — per-pairing comparison runs
  TestExchangeBeatsReflexion        (5) — empirical finding: exchange wins
  TestReflexionConvergesEarly       (3) — cross-reflexion converges fast
  TestComparisonBenchmarkResult     (4) — aggregate metrics + summary
  TestCrossReflexionTurnFunction    (4) — turn function mechanics
  TestComparisonMetrics             (4) — delta/wins/avg computations

Total: 25 tests.
"""

from __future__ import annotations

import unittest

from e0_controller.primitives import Outcome
from e0_controller.multiverse import MultiverseController, Universe
from e0_controller.cross_reflexion import cross_reflexion_turn
from e0_controller.benchmark_multiverse import (
    PairingResult,
    knowledge_exchange_turn,
    PAIRINGS,
)
from e0_controller.benchmark_cross_reflexion import (
    ComparisonBenchmarkResult,
    ComparisonPairingResult,
    run_comparison_benchmark,
    run_comparison_pairing,
    _run_pairing_with_turn_fn,
)
from e0_controller.benchmark_domain_invariance import (
    build_d1_linear_chain,
    build_d2_diamond,
    build_d3_gordian_trap,
    build_d4_greedy_trap,
    build_d5_grid_detour,
    build_d7_invoice,
    build_d9_wide_dag,
    build_d10_bottleneck,
)


# ══════════════════════════════════════════════
# Cache — run benchmark once, share across tests
# ══════════════════════════════════════════════

_RESULT: ComparisonBenchmarkResult = run_comparison_benchmark()
_BY_NAME: dict = {p.name: p for p in _RESULT.pairings}


# ══════════════════════════════════════════════
# 1. Per-pairing comparison execution
# ══════════════════════════════════════════════

class TestComparisonPairingExecution(unittest.TestCase):
    """Each pairing runs under both strategies and returns valid results."""

    def test_all_five_pairings_present(self):
        self.assertEqual(len(_RESULT.pairings), 5)

    def test_each_has_exchange_and_reflexion(self):
        for p in _RESULT.pairings:
            self.assertIsInstance(p.exchange, PairingResult)
            self.assertIsInstance(p.reflexion, PairingResult)

    def test_both_run_same_turns(self):
        """Both strategies execute the same number of turns (12)."""
        for p in _RESULT.pairings:
            self.assertEqual(p.exchange.total_turns, 12)
            self.assertEqual(p.reflexion.total_turns, 12)

    def test_novelty_rates_bounded(self):
        for p in _RESULT.pairings:
            for r in [p.exchange, p.reflexion]:
                self.assertGreaterEqual(r.novelty_rate, 0.0)
                self.assertLessEqual(r.novelty_rate, 1.0)

    def test_domain_names_match(self):
        """Both strategies report the same domain names."""
        for p in _RESULT.pairings:
            self.assertEqual(p.exchange.domain_a, p.reflexion.domain_a)
            self.assertEqual(p.exchange.domain_b, p.reflexion.domain_b)


# ══════════════════════════════════════════════
# 2. Empirical: exchange beats reflexion
# ══════════════════════════════════════════════

class TestExchangeBeatsReflexion(unittest.TestCase):
    """Knowledge exchange produces more novelty than cross-reflexion.

    This is the key finding: unconditional edge copying (every turn)
    outperforms frontier-gated edge creation (only when stuck).
    """

    def test_exchange_higher_avg_novelty(self):
        self.assertGreater(
            _RESULT.exchange_avg_novelty,
            _RESULT.reflexion_avg_novelty,
        )

    def test_exchange_wins_majority(self):
        """Exchange wins at least 3 of 5 pairings."""
        self.assertGreaterEqual(_RESULT.exchange_wins, 3)

    def test_reflexion_wins_none(self):
        """Cross-reflexion wins zero pairings."""
        self.assertEqual(_RESULT.reflexion_wins, 0)

    def test_exchange_avg_above_50(self):
        """Exchange sustains ≥50% avg novelty."""
        self.assertGreaterEqual(_RESULT.exchange_avg_novelty, 0.5)

    def test_reflexion_avg_below_exchange(self):
        """Novelty delta is negative (exchange wins overall)."""
        self.assertLess(_RESULT.avg_novelty_delta, 0.0)


# ══════════════════════════════════════════════
# 3. Reflexion converges early
# ══════════════════════════════════════════════

class TestReflexionConvergesEarly(unittest.TestCase):
    """Cross-reflexion converges fast because frontier gate rarely fires."""

    def test_all_reflexion_converge(self):
        """All cross-reflexion pairings converge (frontier too rare)."""
        for p in _RESULT.pairings:
            self.assertTrue(
                p.reflexion.converged,
                f"{p.name} reflexion should converge",
            )

    def test_reflexion_converges_before_exchange(self):
        """Where both converge, reflexion converges earlier."""
        for p in _RESULT.pairings:
            if p.exchange.converged and p.reflexion.converged:
                self.assertLessEqual(
                    p.reflexion.convergence_turn,
                    p.exchange.convergence_turn,
                    f"{p.name}: reflexion should converge ≤ exchange",
                )

    def test_reflexion_has_more_divergence_events(self):
        """Cross-reflexion triggers more divergence pressure
        (converges early → divergence kicks in → repeat)."""
        total_exch = sum(p.exchange.divergence_count for p in _RESULT.pairings)
        total_refl = sum(p.reflexion.divergence_count for p in _RESULT.pairings)
        self.assertGreater(total_refl, total_exch)


# ══════════════════════════════════════════════
# 4. Result type and summary
# ══════════════════════════════════════════════

class TestComparisonBenchmarkResult(unittest.TestCase):
    """Aggregate result type works correctly."""

    def test_summary_contains_pairing_names(self):
        s = _RESULT.summary()
        for p in _RESULT.pairings:
            self.assertIn(p.name, s)

    def test_summary_contains_header(self):
        s = _RESULT.summary()
        self.assertIn("Edge Copying vs Edge Creation", s)

    def test_summary_contains_winner(self):
        s = _RESULT.summary()
        self.assertIn("exch", s)

    def test_novelty_delta_computed(self):
        """novelty_delta = reflexion - exchange."""
        for p in _RESULT.pairings:
            expected = p.reflexion.novelty_rate - p.exchange.novelty_rate
            self.assertAlmostEqual(p.novelty_delta, expected, places=6)


# ══════════════════════════════════════════════
# 5. Cross-reflexion turn function mechanics
# ══════════════════════════════════════════════

class TestCrossReflexionTurnFunction(unittest.TestCase):
    """cross_reflexion_turn works as a MultiverseController turn function."""

    def test_runs_without_error(self):
        """Can execute a single cross-reflexion pairing."""
        result = _run_pairing_with_turn_fn(
            "test", build_d1_linear_chain, build_d3_gordian_trap,
            cross_reflexion_turn, max_turns=4,
        )
        self.assertIsInstance(result, PairingResult)

    def test_reflexion_produces_some_novelty(self):
        """Cross-reflexion does produce SOME novelty (not zero)."""
        result = _run_pairing_with_turn_fn(
            "test", build_d5_grid_detour, build_d10_bottleneck,
            cross_reflexion_turn, max_turns=12,
        )
        self.assertGreater(result.total_novelty, 0)

    def test_reflexion_grows_coupling_topology(self):
        """Divergence pressure injects coupling edges."""
        result = _run_pairing_with_turn_fn(
            "test", build_d2_diamond, build_d9_wide_dag,
            cross_reflexion_turn, max_turns=12,
        )
        self.assertGreater(result.coupling_edge_count, 0)

    def test_exchange_runs_independently(self):
        """Knowledge exchange also works with _run_pairing_with_turn_fn."""
        result = _run_pairing_with_turn_fn(
            "test", build_d4_greedy_trap, build_d7_invoice,
            knowledge_exchange_turn, max_turns=4,
        )
        self.assertIsInstance(result, PairingResult)


# ══════════════════════════════════════════════
# 6. Comparison metrics
# ══════════════════════════════════════════════

class TestComparisonMetrics(unittest.TestCase):
    """Aggregate metric properties computed correctly."""

    def test_exchange_avg_matches_manual(self):
        manual = sum(p.exchange.novelty_rate for p in _RESULT.pairings) / 5
        self.assertAlmostEqual(_RESULT.exchange_avg_novelty, manual, places=6)

    def test_reflexion_avg_matches_manual(self):
        manual = sum(p.reflexion.novelty_rate for p in _RESULT.pairings) / 5
        self.assertAlmostEqual(_RESULT.reflexion_avg_novelty, manual, places=6)

    def test_wins_sum_to_five(self):
        ties = len(_RESULT.pairings) - _RESULT.reflexion_wins - _RESULT.exchange_wins
        self.assertEqual(
            _RESULT.reflexion_wins + _RESULT.exchange_wins + ties, 5,
        )

    def test_avg_delta_matches_component_deltas(self):
        manual = _RESULT.reflexion_avg_novelty - _RESULT.exchange_avg_novelty
        self.assertAlmostEqual(_RESULT.avg_novelty_delta, manual, places=6)
