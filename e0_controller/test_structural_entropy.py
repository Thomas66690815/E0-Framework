"""
Tests for structural_entropy.py — Structural Temperature + Inscription Threshold.

C115: Type 1 forgetting — non-inscription of routine transitions.
"""

import math
import unittest

from e0_controller.primitives import Edge, Outcome
from e0_controller.historization import Historization
from e0_controller.structural_entropy import (
    structural_temperature,
    novelty,
    inscription_threshold,
    should_inscribe,
    dormancy_threshold,
    _signal,
)


def _make_edge(src: str = "A", tgt: str = "B") -> Edge:
    return Edge(source=src, target=tgt)


def _hist_with_experience(edges_outcomes: list, rho: float = 0.95) -> Historization:
    """Build a Historization with specific edge/outcome history."""
    h = Historization(rho=rho)
    for edge, outcome in edges_outcomes:
        h.update(edge, outcome)
    return h


class TestStructuralTemperature(unittest.TestCase):
    """T_s = m̄ / q̄ — self-calibrating measure of system confusion."""

    def test_virgin_system(self):
        """No historized edges → T_s = 0."""
        h = Historization()
        self.assertEqual(structural_temperature(h), 0.0)

    def test_single_edge_pure_success(self):
        """One edge, one success → high quality, T_s is finite and low."""
        e = _make_edge()
        h = _hist_with_experience([(e, Outcome.SUCCESS)])
        T = structural_temperature(h)
        self.assertGreater(T, 0.0)
        # trace_quality = 1.0 (pure success), trace_load = 1.0
        # T_s = 1.0 / (1.0 + ε) ≈ 1.0
        self.assertAlmostEqual(T, 1.0, places=5)

    def test_contradictory_edge_is_hotter(self):
        """An edge with mixed outcomes → low |quality| → higher T_s."""
        e = _make_edge()
        pure = _hist_with_experience([(e, Outcome.SUCCESS)] * 10)
        mixed = _hist_with_experience(
            [(e, Outcome.SUCCESS), (e, Outcome.FAILURE)] * 5
        )
        T_pure = structural_temperature(pure)
        T_mixed = structural_temperature(mixed)
        self.assertGreater(T_mixed, T_pure)

    def test_multiple_edges_averaging(self):
        """T_s averages over all historized edges."""
        e1 = _make_edge("A", "B")
        e2 = _make_edge("C", "D")
        h = Historization()
        h.update(e1, Outcome.SUCCESS)
        h.update(e2, Outcome.FAILURE)
        T = structural_temperature(h)
        # Both edges have |quality| = 1.0 (one pure success, one pure fail)
        # mean load > 0, mean |quality| ≈ 1.0 → T ≈ mean_load
        self.assertGreater(T, 0.0)

    def test_temperature_increases_with_confusion(self):
        """Pure success vs mixed → mixed has higher T_s."""
        e = _make_edge()
        pure = _hist_with_experience([(e, Outcome.SUCCESS)] * 10)
        mixed = _hist_with_experience(
            [(e, Outcome.SUCCESS)] * 10 + [(e, Outcome.FAILURE)] * 10
        )
        T_pure = structural_temperature(pure)
        T_mixed = structural_temperature(mixed)
        self.assertGreater(T_mixed, T_pure)


class TestNovelty(unittest.TestCase):
    """novelty(e, outcome) = |signal(outcome) − trace_quality(e)|"""

    def test_signal_values(self):
        self.assertEqual(_signal(Outcome.SUCCESS), 1.0)
        self.assertEqual(_signal(Outcome.FAILURE), -1.0)

    def test_virgin_edge_any_outcome_novel(self):
        """Virgin edge (quality ≈ 0) → novelty ≈ 1 for SUCCESS or FAILURE."""
        e = _make_edge()
        h = Historization()
        self.assertAlmostEqual(novelty(e, Outcome.SUCCESS, h), 1.0, places=5)
        self.assertAlmostEqual(novelty(e, Outcome.FAILURE, h), 1.0, places=5)

    def test_expected_success_low_novelty(self):
        """Edge with pure success history → SUCCESS has low novelty."""
        e = _make_edge()
        h = _hist_with_experience([(e, Outcome.SUCCESS)] * 20)
        n = novelty(e, Outcome.SUCCESS, h)
        # quality ≈ 1.0, signal = 1.0, novelty ≈ 0
        self.assertLess(n, 0.1)

    def test_unexpected_failure_high_novelty(self):
        """Edge with pure success history → FAILURE has high novelty."""
        e = _make_edge()
        h = _hist_with_experience([(e, Outcome.SUCCESS)] * 20)
        n = novelty(e, Outcome.FAILURE, h)
        # quality ≈ 1.0, signal = -1.0, novelty ≈ 2.0
        self.assertGreater(n, 1.8)

    def test_novelty_range(self):
        """Novelty is in [0, 2]."""
        e = _make_edge()
        for outcomes in [
            [(e, Outcome.SUCCESS)] * 10,
            [(e, Outcome.FAILURE)] * 10,
            [(e, Outcome.SUCCESS), (e, Outcome.FAILURE)] * 5,
        ]:
            h = _hist_with_experience(outcomes)
            for o in [Outcome.SUCCESS, Outcome.FAILURE]:
                n = novelty(e, o, h)
                self.assertGreaterEqual(n, 0.0)
                self.assertLessEqual(n, 2.0 + 1e-9)

    def test_contradictory_edge_moderate_novelty(self):
        """Mixed history → quality ≈ 0 → novelty ≈ 1 for either outcome."""
        e = _make_edge()
        h = _hist_with_experience(
            [(e, Outcome.SUCCESS), (e, Outcome.FAILURE)] * 20
        )
        n_s = novelty(e, Outcome.SUCCESS, h)
        n_f = novelty(e, Outcome.FAILURE, h)
        # quality ≈ 0, so both should be ≈ 1
        self.assertAlmostEqual(n_s, 1.0, delta=0.15)
        self.assertAlmostEqual(n_f, 1.0, delta=0.15)


class TestInscriptionThreshold(unittest.TestCase):
    """ε(e) = ε₀(T_s) · (1 − exp(−m/μ))"""

    def test_virgin_edge_zero_threshold(self):
        """Virgin edge (m = 0) → ε = 0 regardless of T_s."""
        e = _make_edge()
        h = Historization()
        eps = inscription_threshold(e, h, T_s=10.0, mu=5.0)
        self.assertAlmostEqual(eps, 0.0, places=10)

    def test_cold_system_zero_threshold(self):
        """T_s = 0 → ε₀ = 0 → ε = 0 for any edge."""
        e = _make_edge()
        h = _hist_with_experience([(e, Outcome.SUCCESS)] * 20)
        eps = inscription_threshold(e, h, T_s=0.0, mu=5.0)
        self.assertAlmostEqual(eps, 0.0, places=10)

    def test_hot_system_experienced_edge_high_threshold(self):
        """High T_s + high trace_load → ε close to 1."""
        e = _make_edge()
        h = _hist_with_experience([(e, Outcome.SUCCESS)] * 50)
        eps = inscription_threshold(e, h, T_s=50.0, mu=5.0)
        # ε₀ ≈ 1 - exp(-10) ≈ 1.0, load_factor ≈ 1.0
        self.assertGreater(eps, 0.9)

    def test_threshold_increases_with_load(self):
        """More experience on edge → higher threshold."""
        e = _make_edge()
        thresholds = []
        for n in [1, 5, 10, 20]:
            h = _hist_with_experience([(e, Outcome.SUCCESS)] * n)
            thresholds.append(inscription_threshold(e, h, T_s=5.0, mu=5.0))
        for i in range(1, len(thresholds)):
            self.assertGreater(thresholds[i], thresholds[i - 1])

    def test_threshold_increases_with_temperature(self):
        """Higher T_s → higher threshold for same edge."""
        e = _make_edge()
        h = _hist_with_experience([(e, Outcome.SUCCESS)] * 10)
        eps_cold = inscription_threshold(e, h, T_s=0.5, mu=5.0)
        eps_warm = inscription_threshold(e, h, T_s=5.0, mu=5.0)
        eps_hot = inscription_threshold(e, h, T_s=50.0, mu=5.0)
        self.assertLess(eps_cold, eps_warm)
        self.assertLess(eps_warm, eps_hot)

    def test_threshold_range(self):
        """ε is always in [0, 1)."""
        e = _make_edge()
        for n in [0, 1, 5, 50]:
            h = _hist_with_experience([(e, Outcome.SUCCESS)] * n if n > 0 else [])
            for T in [0.0, 1.0, 10.0, 100.0]:
                eps = inscription_threshold(e, h, T_s=T, mu=5.0)
                self.assertGreaterEqual(eps, 0.0)
                self.assertLess(eps, 1.0)


class TestShouldInscribe(unittest.TestCase):
    """Integration: novelty > threshold → inscribe."""

    def test_virgin_edge_always_inscribed(self):
        """First encounter is always inscribed."""
        e = _make_edge()
        h = Historization()
        self.assertTrue(should_inscribe(e, Outcome.SUCCESS, h))
        self.assertTrue(should_inscribe(e, Outcome.FAILURE, h))

    def test_routine_success_not_inscribed(self):
        """After many successes, another success is routine → not inscribed."""
        e = _make_edge()
        # Build substantial history
        h = _hist_with_experience([(e, Outcome.SUCCESS)] * 30)
        # T_s is moderate (pure success → high quality → relatively low T_s)
        # But edge has high load → high threshold
        # novelty(SUCCESS) ≈ 0 (expected) → should NOT inscribe
        result = should_inscribe(e, Outcome.SUCCESS, h)
        self.assertFalse(result)

    def test_surprise_failure_always_inscribed(self):
        """After many successes, a failure is surprising → inscribed."""
        e = _make_edge()
        h = _hist_with_experience([(e, Outcome.SUCCESS)] * 30)
        result = should_inscribe(e, Outcome.FAILURE, h)
        self.assertTrue(result)

    def test_explicit_temperature(self):
        """Can pass T_s explicitly to avoid recomputation."""
        e = _make_edge()
        h = _hist_with_experience([(e, Outcome.SUCCESS)] * 10)
        # With T_s=0 → everything inscribed (cold system)
        self.assertTrue(should_inscribe(e, Outcome.SUCCESS, h, T_s=0.0))

    def test_early_history_inscribes_surprise(self):
        """With only 1 experience, opposite outcome is still inscribed."""
        e = _make_edge()
        h = _hist_with_experience([(e, Outcome.SUCCESS)])
        # Same outcome after 1 experience: quality ≈ 1, novelty ≈ 0 → not inscribed
        # This is correct: even with 1 experience, the same outcome is expected
        self.assertFalse(should_inscribe(e, Outcome.SUCCESS, h))
        # Opposite outcome is a surprise → inscribed
        self.assertTrue(should_inscribe(e, Outcome.FAILURE, h))

    def test_mixed_history_inscribes_both(self):
        """Contradictory history → quality ≈ 0 → novelty ≈ 1 → inscribed."""
        e = _make_edge()
        h = _hist_with_experience(
            [(e, Outcome.SUCCESS), (e, Outcome.FAILURE)] * 15
        )
        # quality ≈ 0, so any definite outcome has novelty ≈ 1
        # threshold depends on T_s (which is high for contradictory)
        # but novelty of 1 should still exceed threshold
        # This tests the balance — contradictory edges keep learning
        self.assertTrue(should_inscribe(e, Outcome.SUCCESS, h))


class TestDormancyThreshold(unittest.TestCase):
    """τ_dormant = ⌈log(θ_trace) / log(ρ)⌉"""

    def test_default_rho(self):
        """ρ = 0.95 → ~90 cycles."""
        tau = dormancy_threshold(0.95)
        self.assertEqual(tau, math.ceil(math.log(0.01) / math.log(0.95)))
        self.assertAlmostEqual(tau, 90, delta=1)

    def test_slow_decay(self):
        """ρ = 0.99 → ~459 cycles."""
        tau = dormancy_threshold(0.99)
        self.assertAlmostEqual(tau, 459, delta=1)

    def test_fast_decay(self):
        """ρ = 0.90 → ~44 cycles."""
        tau = dormancy_threshold(0.90)
        self.assertAlmostEqual(tau, 44, delta=1)

    def test_minimum_one(self):
        """Always at least 1 cycle."""
        tau = dormancy_threshold(0.5)
        self.assertGreaterEqual(tau, 1)

    def test_invalid_rho(self):
        """ρ outside (0,1) raises ValueError."""
        with self.assertRaises(ValueError):
            dormancy_threshold(0.0)
        with self.assertRaises(ValueError):
            dormancy_threshold(1.0)
        with self.assertRaises(ValueError):
            dormancy_threshold(-0.5)

    def test_custom_floor(self):
        """Different trace_floor → different τ_dormant."""
        tau_strict = dormancy_threshold(0.95, trace_floor=0.001)
        tau_loose = dormancy_threshold(0.95, trace_floor=0.1)
        self.assertGreater(tau_strict, tau_loose)


class TestShouldInscribeEdgeCases(unittest.TestCase):
    """Edge cases and property verification."""

    def test_partial_outcome(self):
        """PARTIAL outcome has signal = 0, moderate novelty."""
        e = _make_edge()
        h = _hist_with_experience([(e, Outcome.SUCCESS)] * 20)
        n = novelty(e, Outcome.PARTIAL, h)
        # quality ≈ 1.0, signal(PARTIAL) = 0, novelty ≈ 1.0
        self.assertAlmostEqual(n, 1.0, delta=0.1)

    def test_multiple_edges_independent(self):
        """Inscription decision for one edge doesn't affect another."""
        e1 = _make_edge("A", "B")
        e2 = _make_edge("C", "D")
        h = _hist_with_experience([(e1, Outcome.SUCCESS)] * 30)
        # e1 has history → routine success not inscribed
        self.assertFalse(should_inscribe(e1, Outcome.SUCCESS, h))
        # e2 is virgin → always inscribed
        self.assertTrue(should_inscribe(e2, Outcome.SUCCESS, h))

    def test_temperature_with_many_edges(self):
        """T_s averages correctly over many edges."""
        edges = [_make_edge(f"S{i}", f"S{i+1}") for i in range(20)]
        h = Historization()
        for e in edges:
            for _ in range(5):
                h.update(e, Outcome.SUCCESS)
        T = structural_temperature(h)
        self.assertGreater(T, 0.0)
        self.assertLess(T, 100.0)  # sanity bound


if __name__ == "__main__":
    unittest.main()
