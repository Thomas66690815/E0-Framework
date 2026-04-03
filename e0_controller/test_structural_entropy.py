"""
Tests for structural_entropy.py — Structural Temperature, Inscription Threshold,
Anchor Analysis, and Decay Candidates.

C115: Type 1 forgetting — non-inscription of routine transitions.
C116: Type 2 forgetting — anchor analysis + decay candidates.
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
    anchor_score,
    state_dormancy,
    find_decay_candidates,
    find_anchors,
    DecayCandidate,
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


# ===================================================================
# C116: Anchor Analysis + Decay Candidates
# ===================================================================

def _build_landscape_edges(state_pairs):
    """Build edges from (source, target) pairs."""
    return [Edge(source=s, target=t) for s, t in state_pairs]


class TestAnchorScore(unittest.TestCase):
    """anchor_score(s) = |q̄_s| · m_max(s) · log(1 + degree(s))"""

    def test_no_incident_edges(self):
        """Isolated state → score = 0."""
        h = Historization()
        score = anchor_score("lonely", h, [])
        self.assertEqual(score, 0.0)

    def test_single_successful_edge(self):
        """One edge, one success → score > 0."""
        e = _make_edge("A", "B")
        h = _hist_with_experience([(e, Outcome.SUCCESS)])
        score = anchor_score("A", h, [e])
        self.assertGreater(score, 0.0)

    def test_hub_scores_higher_than_leaf(self):
        """State with more connections → higher score (log(1+degree))."""
        e1 = _make_edge("HUB", "A")
        e2 = _make_edge("HUB", "B")
        e3 = _make_edge("HUB", "C")
        e_leaf = _make_edge("LEAF", "X")
        h = Historization()
        # Same experience on all edges
        for e in [e1, e2, e3, e_leaf]:
            for _ in range(5):
                h.update(e, Outcome.SUCCESS)
        all_edges = [e1, e2, e3, e_leaf]
        score_hub = anchor_score("HUB", h, all_edges)
        score_leaf = anchor_score("LEAF", h, all_edges)
        self.assertGreater(score_hub, score_leaf)

    def test_strong_quality_scores_higher(self):
        """State with clear outcomes → higher score than mixed."""
        e_clear = _make_edge("CLEAR", "X")
        e_mixed = _make_edge("MIXED", "Y")
        h = Historization()
        for _ in range(10):
            h.update(e_clear, Outcome.SUCCESS)
        for _ in range(5):
            h.update(e_mixed, Outcome.SUCCESS)
            h.update(e_mixed, Outcome.FAILURE)
        all_edges = [e_clear, e_mixed]
        score_clear = anchor_score("CLEAR", h, all_edges)
        score_mixed = anchor_score("MIXED", h, all_edges)
        self.assertGreater(score_clear, score_mixed)

    def test_incoming_edges_count(self):
        """Edges where state is target also contribute to score."""
        e_out = _make_edge("S", "A")
        e_in = _make_edge("B", "S")
        h = Historization()
        for _ in range(5):
            h.update(e_out, Outcome.SUCCESS)
            h.update(e_in, Outcome.SUCCESS)
        score = anchor_score("S", h, [e_out, e_in])
        # degree = 2, both edges contribute
        score_one = anchor_score("S", h, [e_out])
        self.assertGreater(score, score_one)

    def test_score_nonnegative(self):
        """Score is always ≥ 0."""
        e = _make_edge("A", "B")
        h = _hist_with_experience([(e, Outcome.FAILURE)] * 10)
        score = anchor_score("A", h, [e])
        self.assertGreaterEqual(score, 0.0)


class TestStateDormancy(unittest.TestCase):
    """How many cycles since any incident edge was last touched."""

    def test_just_touched(self):
        """Edge touched at current τ → dormancy = 0."""
        e = _make_edge("A", "B")
        h = Historization()
        h.update(e, Outcome.SUCCESS)
        dorm = state_dormancy("A", h, [e])
        self.assertEqual(dorm, 0)

    def test_dormancy_increases_with_time(self):
        """Other edges advance τ → dormancy of untouched state grows."""
        e_active = _make_edge("A", "B")
        e_other = _make_edge("C", "D")
        h = Historization()
        h.update(e_active, Outcome.SUCCESS)  # τ = 1, A last touched at 1
        for _ in range(10):
            h.update(e_other, Outcome.SUCCESS)  # τ = 2..11
        dorm = state_dormancy("A", h, [e_active])
        self.assertEqual(dorm, 10)

    def test_no_historized_edges(self):
        """State with edges but no historization → dormancy = τ."""
        e = _make_edge("A", "B")
        h = Historization()
        # Advance τ via other edges
        other = _make_edge("X", "Y")
        for _ in range(5):
            h.update(other, Outcome.SUCCESS)
        dorm = state_dormancy("A", h, [e])
        self.assertEqual(dorm, 5)

    def test_multiple_edges_uses_most_recent(self):
        """Dormancy uses the most recently touched incident edge."""
        e1 = _make_edge("A", "B")
        e2 = _make_edge("A", "C")
        h = Historization()
        h.update(e1, Outcome.SUCCESS)  # τ = 1
        for _ in range(5):
            h.update(Edge("X", "Y"), Outcome.SUCCESS)  # τ = 2..6
        h.update(e2, Outcome.SUCCESS)  # τ = 7
        for _ in range(3):
            h.update(Edge("X", "Y"), Outcome.SUCCESS)  # τ = 8..10
        dorm = state_dormancy("A", h, [e1, e2])
        self.assertEqual(dorm, 3)  # 10 - 7 = 3


class TestFindDecayCandidates(unittest.TestCase):
    """Integration: identify states eligible for structural decay."""

    def _build_simple_graph(self):
        """A→B→C→D with varying experience levels."""
        edges = [
            _make_edge("A", "B"),
            _make_edge("B", "C"),
            _make_edge("C", "D"),
        ]
        states = {"A", "B", "C", "D"}
        return states, edges

    def test_no_candidates_in_fresh_system(self):
        """Fresh system with recent activity → no decay candidates."""
        states, edges = self._build_simple_graph()
        h = Historization()
        for e in edges:
            h.update(e, Outcome.SUCCESS)
        candidates = find_decay_candidates(states, h, edges)
        # Everything was just touched → dormancy = 0 → no candidates
        self.assertEqual(len(candidates), 0)

    def test_dormant_weak_state_is_candidate(self):
        """A state that is both weak and dormant → decay candidate."""
        e_weak = _make_edge("WEAK", "X")
        e_strong = _make_edge("STRONG", "Y")
        h = Historization()
        # WEAK: single touch
        h.update(e_weak, Outcome.SUCCESS)
        # Make WEAK dormant by advancing τ
        for _ in range(100):
            h.update(e_strong, Outcome.SUCCESS)

        all_edges = [e_weak, e_strong]
        states = {"WEAK", "STRONG", "X", "Y"}
        candidates = find_decay_candidates(
            states, h, all_edges, theta_base=0.5
        )
        candidate_states = {c.state for c in candidates}
        self.assertIn("WEAK", candidate_states)
        self.assertNotIn("STRONG", candidate_states)

    def test_protected_states_excluded(self):
        """Start/goal/current states are never candidates."""
        e = _make_edge("START", "X")
        h = Historization()
        h.update(e, Outcome.SUCCESS)
        for _ in range(100):
            h.update(_make_edge("A", "B"), Outcome.SUCCESS)
        candidates = find_decay_candidates(
            {"START", "X", "A", "B"}, h, [e, _make_edge("A", "B")],
            protected={"START"}
        )
        self.assertTrue(all(c.state != "START" for c in candidates))

    def test_sorted_by_score_ascending(self):
        """Candidates are sorted weakest-first."""
        e1 = _make_edge("W1", "X")
        e2 = _make_edge("W2", "Y")
        e3 = _make_edge("W2", "Z")  # W2 has more edges → higher score
        h = Historization()
        h.update(e1, Outcome.SUCCESS)
        h.update(e2, Outcome.SUCCESS)
        h.update(e3, Outcome.SUCCESS)
        for _ in range(100):
            h.update(_make_edge("A", "B"), Outcome.SUCCESS)

        all_edges = [e1, e2, e3, _make_edge("A", "B")]
        candidates = find_decay_candidates(
            {"W1", "W2", "X", "Y", "Z", "A", "B"},
            h, all_edges, theta_base=0.1
        )
        if len(candidates) >= 2:
            for i in range(1, len(candidates)):
                self.assertGreaterEqual(
                    candidates[i].anchor_score,
                    candidates[i - 1].anchor_score
                )

    def test_hot_system_prunes_more(self):
        """Higher T_s raises θ_decay → more candidates."""
        e = _make_edge("S", "T")
        h = Historization()
        h.update(e, Outcome.SUCCESS)
        for _ in range(100):
            h.update(_make_edge("X", "Y"), Outcome.SUCCESS)

        all_edges = [e, _make_edge("X", "Y")]
        states = {"S", "T", "X", "Y"}
        cold = find_decay_candidates(states, h, all_edges, T_s=0.1)
        hot = find_decay_candidates(states, h, all_edges, T_s=10.0)
        self.assertGreaterEqual(len(hot), len(cold))

    def test_decay_candidate_has_correct_fields(self):
        """DecayCandidate dataclass has all required fields."""
        e = _make_edge("A", "B")
        h = Historization()
        h.update(e, Outcome.SUCCESS)
        for _ in range(100):
            h.update(_make_edge("X", "Y"), Outcome.SUCCESS)
        candidates = find_decay_candidates(
            {"A", "B", "X", "Y"}, h,
            [e, _make_edge("X", "Y")]
        )
        for c in candidates:
            self.assertIsInstance(c.state, str)
            self.assertIsInstance(c.anchor_score, float)
            self.assertIsInstance(c.dormancy, int)
            self.assertIsInstance(c.incident_edge_count, int)


class TestFindAnchors(unittest.TestCase):
    """Identify anchor states that will survive decay."""

    def test_well_experienced_state_is_anchor(self):
        """State with deep, clear experience → anchor."""
        e1 = _make_edge("ANCHOR", "A")
        e2 = _make_edge("ANCHOR", "B")
        e3 = _make_edge("ANCHOR", "C")
        h = Historization()
        for e in [e1, e2, e3]:
            for _ in range(20):
                h.update(e, Outcome.SUCCESS)
        all_edges = [e1, e2, e3]
        anchors = find_anchors({"ANCHOR", "A", "B", "C"}, h, all_edges)
        self.assertIn("ANCHOR", anchors)

    def test_virgin_state_not_anchor(self):
        """State with no experience → not an anchor."""
        h = Historization()
        anchors = find_anchors({"VIRGIN"}, h, [])
        self.assertNotIn("VIRGIN", anchors)

    def test_anchor_set_is_subset_of_states(self):
        """Anchors must be a subset of provided states."""
        e = _make_edge("A", "B")
        h = _hist_with_experience([(e, Outcome.SUCCESS)] * 20)
        anchors = find_anchors({"A", "B"}, h, [e])
        self.assertTrue(anchors.issubset({"A", "B"}))

    def test_anchors_and_candidates_partition(self):
        """States are either anchors, candidates, or protected — no overlap."""
        e1 = _make_edge("A", "B")
        e2 = _make_edge("C", "D")
        h = Historization()
        for _ in range(20):
            h.update(e1, Outcome.SUCCESS)
        h.update(e2, Outcome.SUCCESS)
        for _ in range(100):
            h.update(_make_edge("X", "Y"), Outcome.SUCCESS)

        all_edges = [e1, e2, _make_edge("X", "Y")]
        states = {"A", "B", "C", "D", "X", "Y"}
        anchors = find_anchors(states, h, all_edges)
        candidates = find_decay_candidates(states, h, all_edges)
        candidate_states = {c.state for c in candidates}
        # No state is both anchor and candidate
        self.assertEqual(len(anchors & candidate_states), 0)


if __name__ == "__main__":
    unittest.main()
