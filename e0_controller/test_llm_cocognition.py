"""
Tests for E₀ LLM Co-Cognition (C71)
====================================

Deterministic tests for the co-cognition pipeline using mock universes.
No API key required — these run as part of the standard test suite.

Live LLM co-cognition tests are in live_test_cocognition.py.
"""

from __future__ import annotations

import unittest

from e0_controller.primitives import Outcome
from e0_controller.landscape import Landscape
from e0_controller.multiverse import Universe
from e0_controller.llm_cocognition import (
    CoCognitionResult,
    run_cocognition_from_universes,
)


# ══════════════════════════════════════════════
# Test Fixtures
# ══════════════════════════════════════════════

def _make_linear_universe(name: str = "Alpha") -> Universe:
    """Linear: A → B → C → D (3 edges, 4 states)."""
    la = Landscape()
    for s in ["A", "B", "C", "D"]:
        la.add_state(s)
    la.add_edge("A", "B", delta=0.5, resistance=1.0)
    la.add_edge("B", "C", delta=0.5, resistance=1.0)
    la.add_edge("C", "D", delta=0.5, resistance=1.0)
    return Universe(name, la, lambda s, t: Outcome.SUCCESS, "A", "D")


def _make_branching_universe(name: str = "Beta") -> Universe:
    """Branching: A → C → D, A → E → D (4 edges, 4 states)."""
    lb = Landscape()
    for s in ["A", "C", "D", "E"]:
        lb.add_state(s)
    lb.add_edge("A", "C", delta=0.6, resistance=0.8)
    lb.add_edge("C", "D", delta=0.4, resistance=1.2)
    lb.add_edge("A", "E", delta=0.7, resistance=0.5)
    lb.add_edge("E", "D", delta=0.3, resistance=1.0)
    return Universe(name, lb, lambda s, t: Outcome.SUCCESS, "A", "D")


def _make_disjoint_universe(name: str = "Gamma") -> Universe:
    """Disjoint: X → Y → Z (no overlap with Alpha)."""
    lc = Landscape()
    for s in ["X", "Y", "Z"]:
        lc.add_state(s)
    lc.add_edge("X", "Y", delta=0.8, resistance=0.5)
    lc.add_edge("Y", "Z", delta=0.8, resistance=0.5)
    return Universe(name, lc, lambda s, t: Outcome.SUCCESS, "X", "Z")


# Module-level cache: run once, test multiple properties
_RESULT: CoCognitionResult = run_cocognition_from_universes(
    _make_linear_universe(),
    _make_branching_universe(),
    max_turns=6,
    max_nav_cycles=10,
)

_DISJOINT: CoCognitionResult = run_cocognition_from_universes(
    _make_linear_universe("Linear"),
    _make_disjoint_universe(),
    max_turns=6,
    max_nav_cycles=10,
)


# ══════════════════════════════════════════════
# Test Class 1: CoCognitionResult properties
# ══════════════════════════════════════════════

class TestCoCognitionResult(unittest.TestCase):
    """CoCognitionResult computes derived metrics correctly."""

    def test_total_enrichment_is_sum(self):
        self.assertEqual(
            _RESULT.total_enrichment,
            _RESULT.a_new_edges + _RESULT.b_new_edges,
        )

    def test_novelty_rate_in_range(self):
        self.assertGreaterEqual(_RESULT.novelty_rate, 0.0)
        self.assertLessEqual(_RESULT.novelty_rate, 1.0)

    def test_summary_contains_universe_names(self):
        s = _RESULT.summary()
        self.assertIn("Alpha", s)
        self.assertIn("Beta", s)

    def test_summary_contains_enrichment(self):
        s = _RESULT.summary()
        self.assertIn("enrichment", s.lower())

    def test_summary_contains_structural_distance(self):
        s = _RESULT.summary()
        self.assertIn("Structural distance", s)


# ══════════════════════════════════════════════
# Test Class 2: Mock co-cognition pipeline
# ══════════════════════════════════════════════

class TestMockCoCognition(unittest.TestCase):
    """Co-cognition with overlapping mock universes."""

    def test_both_reach_goal(self):
        self.assertTrue(_RESULT.a_reached_goal)
        self.assertTrue(_RESULT.b_reached_goal)

    def test_alpha_gains_edges(self):
        self.assertGreater(_RESULT.a_new_edges, 0)

    def test_beta_gains_edges(self):
        self.assertGreater(_RESULT.b_new_edges, 0)

    def test_structural_distance_decreases(self):
        self.assertLess(
            _RESULT.structural_distance_after,
            _RESULT.structural_distance_before,
        )

    def test_initial_distance_positive(self):
        self.assertGreater(_RESULT.structural_distance_before, 0.0)

    def test_multiverse_ran_turns(self):
        self.assertEqual(_RESULT.multiverse_result.total_turns, 6)

    def test_some_turns_novel(self):
        self.assertGreater(_RESULT.multiverse_result.total_novelty, 0)


# ══════════════════════════════════════════════
# Test Class 3: Disjoint universes
# ══════════════════════════════════════════════

class TestDisjointCoCognition(unittest.TestCase):
    """Co-cognition with completely disjoint topologies."""

    def test_initial_distance_is_one(self):
        self.assertAlmostEqual(
            _DISJOINT.structural_distance_before, 1.0, places=5,
        )

    def test_both_still_reach_goal(self):
        self.assertTrue(_DISJOINT.a_reached_goal)
        self.assertTrue(_DISJOINT.b_reached_goal)

    def test_enrichment_from_disjoint(self):
        self.assertGreater(_DISJOINT.total_enrichment, 0)

    def test_distance_decreases_after_exchange(self):
        self.assertLess(
            _DISJOINT.structural_distance_after,
            _DISJOINT.structural_distance_before,
        )


# ══════════════════════════════════════════════
# Test Class 4: Structural distance evolution
# ══════════════════════════════════════════════

class TestStructuralDistanceEvolution(unittest.TestCase):
    """Knowledge exchange reduces structural distance."""

    def test_overlapping_converge_to_zero(self):
        self.assertAlmostEqual(
            _RESULT.structural_distance_after, 0.0, places=5,
        )

    def test_disjoint_converge_but_not_zero(self):
        # Disjoint start at 1.0 — after exchange they share states
        # but may not reach 0.0 if not all edges transfer
        self.assertLess(
            _DISJOINT.structural_distance_after,
            _DISJOINT.structural_distance_before,
        )

    def test_distance_never_increases_overlapping(self):
        # After knowledge exchange, distance should not increase
        self.assertLessEqual(
            _RESULT.structural_distance_after,
            _RESULT.structural_distance_before,
        )


# ══════════════════════════════════════════════
# Test Class 5: Navigation traces
# ══════════════════════════════════════════════

class TestNavigationTraces(unittest.TestCase):
    """Post-coupling navigation produces valid traces."""

    def test_trace_a_starts_at_start(self):
        self.assertEqual(_RESULT.trace_a.path[0], "A")

    def test_trace_a_ends_at_goal(self):
        self.assertEqual(_RESULT.trace_a.path[-1], "D")

    def test_trace_b_starts_at_start(self):
        self.assertEqual(_RESULT.trace_b.path[0], "A")

    def test_trace_b_ends_at_goal(self):
        self.assertEqual(_RESULT.trace_b.path[-1], "D")

    def test_traces_have_steps(self):
        self.assertGreater(len(_RESULT.trace_a.steps), 0)
        self.assertGreater(len(_RESULT.trace_b.steps), 0)


# ══════════════════════════════════════════════
# Test Class 6: Enrichment properties
# ══════════════════════════════════════════════

class TestEnrichmentProperties(unittest.TestCase):
    """Enrichment metrics are consistent."""

    def test_final_edges_ge_initial(self):
        self.assertGreaterEqual(_RESULT.a_final_edges, _RESULT.a_initial_edges)
        self.assertGreaterEqual(_RESULT.b_final_edges, _RESULT.b_initial_edges)

    def test_final_states_ge_initial(self):
        self.assertGreaterEqual(_RESULT.a_final_states, _RESULT.a_initial_states)
        self.assertGreaterEqual(_RESULT.b_final_states, _RESULT.b_initial_states)

    def test_new_edges_nonnegative(self):
        self.assertGreaterEqual(_RESULT.a_new_edges, 0)
        self.assertGreaterEqual(_RESULT.b_new_edges, 0)

    def test_initial_edge_counts_correct(self):
        self.assertEqual(_RESULT.a_initial_edges, 3)  # linear: 3
        self.assertEqual(_RESULT.b_initial_edges, 4)  # branching: 4


if __name__ == "__main__":
    unittest.main()
