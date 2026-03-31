"""
Tests for C73 Primitive Extensions
===================================

Two new primitives derived from C72 Chess insights:
1. Landscape.fully_connected() — uniform-initialization factory
2. Historization.strategy_profile() — learned-strategy extraction

Tests: 18 across 4 classes.
"""

import unittest

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.historization import Historization


# ══════════════════════════════════════════════
# 1. Landscape.fully_connected()
# ══════════════════════════════════════════════

class TestFullyConnectedConstruction(unittest.TestCase):
    """Verify the factory builds a correct fully connected graph."""

    def test_three_states(self):
        la = Landscape.fully_connected(["A", "B", "C"])
        self.assertEqual(la.states, {"A", "B", "C"})
        self.assertEqual(la.edge_count(), 6)  # 3 * 2

    def test_six_states_edge_count(self):
        states = [f"S{i}" for i in range(6)]
        la = Landscape.fully_connected(states)
        self.assertEqual(la.edge_count(), 30)  # 6 * 5

    def test_default_delta_and_resistance(self):
        la = Landscape.fully_connected(["X", "Y"])
        self.assertAlmostEqual(la.difference("X", "Y"), 0.5)
        self.assertAlmostEqual(la.base_resistance("X", "Y"), 1.0)

    def test_custom_delta_and_resistance(self):
        la = Landscape.fully_connected(["A", "B"], delta=0.3, resistance=0.7)
        self.assertAlmostEqual(la.difference("A", "B"), 0.3)
        self.assertAlmostEqual(la.base_resistance("A", "B"), 0.7)

    def test_single_state_no_edges(self):
        la = Landscape.fully_connected(["ONLY"])
        self.assertEqual(la.states, {"ONLY"})
        self.assertEqual(la.edge_count(), 0)

    def test_empty_states(self):
        la = Landscape.fully_connected([])
        self.assertEqual(la.states, set())
        self.assertEqual(la.edge_count(), 0)

    def test_is_landscape_instance(self):
        la = Landscape.fully_connected(["A", "B"])
        self.assertIsInstance(la, Landscape)
        self.assertIsInstance(la.historization, Historization)


class TestFullyConnectedEquivalence(unittest.TestCase):
    """Verify factory produces identical result to manual construction."""

    def test_matches_manual_build(self):
        states = ["MATERIAL", "KING_SAFETY", "CENTER", "ACTIVITY"]
        # Factory
        auto = Landscape.fully_connected(states, delta=0.5, resistance=1.0)
        # Manual (old chess_e0 pattern)
        manual = Landscape()
        for s in states:
            manual.add_state(s)
        for a in states:
            for b in states:
                if a != b:
                    manual.add_edge(a, b, delta=0.5, resistance=1.0)
        # Compare
        self.assertEqual(auto.states, manual.states)
        self.assertEqual(auto.edge_count(), manual.edge_count())
        for e in auto.edges:
            self.assertAlmostEqual(
                auto.difference(e.source, e.target),
                manual.difference(e.source, e.target),
            )
            self.assertAlmostEqual(
                auto.base_resistance(e.source, e.target),
                manual.base_resistance(e.source, e.target),
            )


# ══════════════════════════════════════════════
# 2. Historization.strategy_profile()
# ══════════════════════════════════════════════

class TestStrategyProfileBasic(unittest.TestCase):
    """Verify strategy_profile returns correct rankings."""

    def setUp(self):
        self.H = Historization()
        self.good = Edge("A", "B")
        self.bad = Edge("C", "D")
        self.mixed = Edge("E", "F")
        # Build history
        for _ in range(5):
            self.H.update(self.good, Outcome.SUCCESS)
        for _ in range(5):
            self.H.update(self.bad, Outcome.FAILURE)
        for _ in range(3):
            self.H.update(self.mixed, Outcome.SUCCESS)
        for _ in range(3):
            self.H.update(self.mixed, Outcome.FAILURE)

    def test_returns_list_of_triples(self):
        profile = self.H.strategy_profile()
        self.assertIsInstance(profile, list)
        for entry in profile:
            self.assertEqual(len(entry), 3)

    def test_sorted_by_quality_descending(self):
        profile = self.H.strategy_profile()
        qualities = [q for _, q, _ in profile]
        self.assertEqual(qualities, sorted(qualities, reverse=True))

    def test_good_edge_first(self):
        profile = self.H.strategy_profile()
        self.assertEqual(profile[0][0], self.good)

    def test_bad_edge_last(self):
        profile = self.H.strategy_profile()
        self.assertEqual(profile[-1][0], self.bad)

    def test_quality_signs(self):
        profile = self.H.strategy_profile()
        by_edge = {e: q for e, q, _ in profile}
        self.assertGreater(by_edge[self.good], 0.5)
        self.assertLess(by_edge[self.bad], -0.5)
        # Mixed: not extreme in either direction (λ_f > λ_s shifts it slightly negative)
        self.assertGreater(by_edge[self.mixed], -0.5)
        self.assertLess(by_edge[self.mixed], 0.5)

    def test_top_n_limits_results(self):
        profile = self.H.strategy_profile(top_n=1)
        self.assertEqual(len(profile), 1)
        self.assertEqual(profile[0][0], self.good)

    def test_top_n_zero_returns_all(self):
        all_profile = self.H.strategy_profile(top_n=0)
        self.assertEqual(len(all_profile), 3)


class TestStrategyProfileEdgeCases(unittest.TestCase):
    """Edge cases for strategy_profile."""

    def test_empty_historization(self):
        H = Historization()
        self.assertEqual(H.strategy_profile(), [])

    def test_explicit_edge_list(self):
        H = Historization()
        e1 = Edge("X", "Y")
        e2 = Edge("Y", "Z")
        H.update(e1, Outcome.SUCCESS)
        H.update(e2, Outcome.FAILURE)
        # Only ask about e1
        profile = H.strategy_profile(edges=[e1])
        self.assertEqual(len(profile), 1)
        self.assertEqual(profile[0][0], e1)

    def test_untouched_edges_excluded(self):
        H = Historization()
        e_used = Edge("A", "B")
        e_unused = Edge("C", "D")
        H.update(e_used, Outcome.SUCCESS)
        profile = H.strategy_profile(edges=[e_used, e_unused])
        edges_in_profile = [e for e, _, _ in profile]
        self.assertIn(e_used, edges_in_profile)
        self.assertNotIn(e_unused, edges_in_profile)


if __name__ == "__main__":
    unittest.main()
