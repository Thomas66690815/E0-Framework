"""
C60 — Multiverse Tests
=========================
Validates coupled E₀ systems with novelty-gated historization.

Key properties tested:
  - LandscapeSnapshot captures structural metrics correctly
  - NoveltyGate distinguishes novelty from stagnation
  - Coupling landscape historizes with NoveltyGate outcomes
  - Convergence detection after N stale turns
  - Divergence pressure injects new exploration territory
  - Full run: convergence → divergence → continued exploration
  - Coupling R_eff rises on stale edges (FAILURE historization)

Test classes:
  TestLandscapeSnapshot      (5) — capture metrics
  TestNoveltyGate            (5) — evaluate structural novelty
  TestCouplingLandscape      (4) — construction and historization
  TestMultiverseTurn         (4) — single turn execution
  TestConvergenceDetection   (4) — window-based convergence
  TestDivergencePressure     (5) — injection of exploration territory
  TestMultiverseRun          (5) — full orchestration
  TestMultiverseResult       (3) — result properties and summary

Total: 35 tests.
"""

from __future__ import annotations

import unittest

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.multiverse import (
    LandscapeSnapshot,
    MultiverseController,
    MultiverseResult,
    MultiverseTurn,
    NoveltyGate,
    Universe,
)


# ══════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════

def _simple_landscape(states=("S", "A", "GOAL"), edges=None):
    """Build a simple landscape for testing."""
    L = Landscape()
    if edges is None:
        edges = [("S", "A", 0.5, 0.3), ("A", "GOAL", 0.5, 0.3)]
    for s, t, d, r in edges:
        L.add_edge(s, t, delta=d, resistance=r)
    for s in states:
        L.add_state(s)
    return L


def _all_success(source: str, target: str) -> Outcome:
    return Outcome.SUCCESS


def _make_universe(name, states=("S", "A", "GOAL"), edges=None):
    """Build a named universe with a simple landscape."""
    L = _simple_landscape(states, edges)
    return Universe(
        name=name,
        landscape=L,
        execute_fn=_all_success,
        start="S",
        goal="GOAL",
    )


# ══════════════════════════════════════════════
# Test: LandscapeSnapshot
# ══════════════════════════════════════════════

class TestLandscapeSnapshot(unittest.TestCase):
    """Snapshot captures structural metrics correctly."""

    def test_empty_landscape(self):
        """Empty landscape has zero metrics."""
        L = Landscape()
        snap = LandscapeSnapshot.capture(L)
        self.assertEqual(snap.state_count, 0)
        self.assertEqual(snap.edge_count, 0)
        self.assertAlmostEqual(snap.total_delta, 0.0)

    def test_simple_landscape(self):
        """Captures correct counts for a simple landscape."""
        L = _simple_landscape()
        snap = LandscapeSnapshot.capture(L)
        self.assertEqual(snap.state_count, 3)
        self.assertEqual(snap.edge_count, 2)
        self.assertAlmostEqual(snap.total_delta, 1.0)

    def test_after_adding_edge(self):
        """Snapshot reflects newly added edges."""
        L = _simple_landscape()
        snap1 = LandscapeSnapshot.capture(L)
        L.add_edge("S", "GOAL", delta=1.0, resistance=0.5)
        snap2 = LandscapeSnapshot.capture(L)
        self.assertEqual(snap2.edge_count, snap1.edge_count + 1)
        self.assertGreater(snap2.total_delta, snap1.total_delta)

    def test_after_adding_state(self):
        """Snapshot reflects newly added states."""
        L = _simple_landscape()
        snap1 = LandscapeSnapshot.capture(L)
        L.add_state("NEW")
        snap2 = LandscapeSnapshot.capture(L)
        self.assertEqual(snap2.state_count, snap1.state_count + 1)

    def test_frozen(self):
        """Snapshot is immutable."""
        L = _simple_landscape()
        snap = LandscapeSnapshot.capture(L)
        with self.assertRaises(AttributeError):
            snap.state_count = 999


# ══════════════════════════════════════════════
# Test: NoveltyGate
# ══════════════════════════════════════════════

class TestNoveltyGate(unittest.TestCase):
    """NoveltyGate distinguishes novelty from stagnation."""

    def setUp(self):
        self.gate = NoveltyGate()
        self.base = LandscapeSnapshot(state_count=3, edge_count=2, total_delta=1.0)

    def test_no_change_is_failure(self):
        """Identical before/after = FAILURE."""
        result = self.gate.evaluate(self.base, self.base, self.base, self.base)
        self.assertEqual(result, Outcome.FAILURE)

    def test_new_edge_is_success(self):
        """New edge in universe A = SUCCESS."""
        after = LandscapeSnapshot(state_count=3, edge_count=3, total_delta=1.5)
        result = self.gate.evaluate(self.base, after, self.base, self.base)
        self.assertEqual(result, Outcome.SUCCESS)

    def test_new_state_is_success(self):
        """New state in universe B = SUCCESS."""
        after = LandscapeSnapshot(state_count=4, edge_count=2, total_delta=1.0)
        result = self.gate.evaluate(self.base, self.base, self.base, after)
        self.assertEqual(result, Outcome.SUCCESS)

    def test_delta_growth_above_threshold(self):
        """Δ growth above threshold = SUCCESS."""
        gate = NoveltyGate(delta_threshold=0.5)
        after = LandscapeSnapshot(state_count=3, edge_count=2, total_delta=1.8)
        result = gate.evaluate(self.base, after, self.base, self.base)
        self.assertEqual(result, Outcome.SUCCESS)

    def test_delta_growth_below_threshold(self):
        """Δ growth below threshold = FAILURE (no structural change)."""
        gate = NoveltyGate(delta_threshold=1.0)
        after = LandscapeSnapshot(state_count=3, edge_count=2, total_delta=1.3)
        result = gate.evaluate(self.base, after, self.base, self.base)
        self.assertEqual(result, Outcome.FAILURE)


# ══════════════════════════════════════════════
# Test: Coupling landscape
# ══════════════════════════════════════════════

class TestCouplingLandscape(unittest.TestCase):
    """Coupling landscape construction and historization."""

    def setUp(self):
        self.a = _make_universe("Alpha")
        self.b = _make_universe("Beta")
        self.ctrl = MultiverseController(self.a, self.b)

    def test_initial_topology(self):
        """Coupling has two poles, two edges."""
        L = self.ctrl.coupling
        self.assertIn("Alpha", L._states)
        self.assertIn("Beta", L._states)
        self.assertEqual(len(L._delta), 2)

    def test_bidirectional(self):
        """Coupling edges exist in both directions."""
        L = self.ctrl.coupling
        self.assertIn(Edge("Alpha", "Beta"), L._delta)
        self.assertIn(Edge("Beta", "Alpha"), L._delta)

    def test_failure_increases_resistance(self):
        """FAILURE historization raises R_eff on coupling edge."""
        edge = Edge("Alpha", "Beta")
        r_before = self.ctrl.coupling.effective_resistance("Alpha", "Beta")
        self.ctrl.coupling.historization.update(edge, Outcome.FAILURE)
        r_after = self.ctrl.coupling.effective_resistance("Alpha", "Beta")
        self.assertGreater(r_after, r_before)

    def test_success_decreases_resistance(self):
        """SUCCESS historization lowers R_eff on coupling edge."""
        edge = Edge("Alpha", "Beta")
        # First add some FAILURE to create room for decrease
        for _ in range(3):
            self.ctrl.coupling.historization.update(edge, Outcome.FAILURE)
        r_before = self.ctrl.coupling.effective_resistance("Alpha", "Beta")
        for _ in range(5):
            self.ctrl.coupling.historization.update(edge, Outcome.SUCCESS)
        r_after = self.ctrl.coupling.effective_resistance("Alpha", "Beta")
        self.assertLess(r_after, r_before)


# ══════════════════════════════════════════════
# Test: Single turn
# ══════════════════════════════════════════════

class TestMultiverseTurn(unittest.TestCase):
    """Single multiverse turn execution."""

    def setUp(self):
        self.a = _make_universe("Alpha")
        self.b = _make_universe("Beta")
        self.ctrl = MultiverseController(self.a, self.b)

    def test_turn_returns_result(self):
        """Turn produces a MultiverseTurn."""
        def noop(active, passive):
            pass
        t = self.ctrl.turn(turn_fn=noop)
        self.assertIsInstance(t, MultiverseTurn)
        self.assertEqual(t.turn, 0)

    def test_alternating_active(self):
        """Turns alternate between Alpha and Beta."""
        def noop(active, passive):
            pass
        t0 = self.ctrl.turn(turn_fn=noop)
        t1 = self.ctrl.turn(turn_fn=noop)
        self.assertEqual(t0.active, "Alpha")
        self.assertEqual(t1.active, "Beta")

    def test_novel_turn(self):
        """Turn with structural change is detected as novel."""
        def add_edge(active, passive):
            active.landscape.add_edge("A", "NEW", delta=0.5, resistance=0.3)
        t = self.ctrl.turn(turn_fn=add_edge)
        self.assertTrue(t.novel)
        self.assertEqual(t.outcome, Outcome.SUCCESS)

    def test_stale_turn(self):
        """Turn without change is detected as stale."""
        def noop(active, passive):
            pass
        t = self.ctrl.turn(turn_fn=noop)
        self.assertFalse(t.novel)
        self.assertEqual(t.outcome, Outcome.FAILURE)


# ══════════════════════════════════════════════
# Test: Convergence detection
# ══════════════════════════════════════════════

class TestConvergenceDetection(unittest.TestCase):
    """Window-based convergence detection."""

    def test_not_converged_initially(self):
        """No convergence before any turns."""
        a = _make_universe("A")
        b = _make_universe("B")
        ctrl = MultiverseController(a, b, convergence_window=3)
        self.assertFalse(ctrl.detect_convergence())

    def test_not_converged_with_novelty(self):
        """No convergence when recent turns have novelty."""
        a = _make_universe("A")
        b = _make_universe("B")
        ctrl = MultiverseController(a, b, convergence_window=2)
        counter = [0]
        def sometimes_novel(active, passive):
            if counter[0] % 2 == 0:
                active.landscape.add_edge(
                    "A", f"N{counter[0]}", delta=0.5, resistance=0.3,
                )
            counter[0] += 1
        ctrl.turn(turn_fn=sometimes_novel)  # novel
        ctrl.turn(turn_fn=sometimes_novel)  # stale
        self.assertFalse(ctrl.detect_convergence())

    def test_converged_after_window(self):
        """Convergence after N consecutive stale turns."""
        a = _make_universe("A")
        b = _make_universe("B")
        ctrl = MultiverseController(a, b, convergence_window=3)
        def noop(active, passive):
            pass
        for _ in range(3):
            ctrl.turn(turn_fn=noop)
        self.assertTrue(ctrl.detect_convergence())

    def test_novel_turn_resets(self):
        """One novel turn after stale streak resets convergence."""
        a = _make_universe("A")
        b = _make_universe("B")
        ctrl = MultiverseController(a, b, convergence_window=2)
        def noop(active, passive):
            pass
        ctrl.turn(turn_fn=noop)
        ctrl.turn(turn_fn=noop)
        self.assertTrue(ctrl.detect_convergence())
        # Now add novelty
        def novel(active, passive):
            active.landscape.add_edge("S", "X", delta=1.0, resistance=0.5)
        ctrl.turn(turn_fn=novel)
        self.assertFalse(ctrl.detect_convergence())


# ══════════════════════════════════════════════
# Test: Divergence pressure
# ══════════════════════════════════════════════

class TestDivergencePressure(unittest.TestCase):
    """Injection of exploration territory."""

    def setUp(self):
        self.a = _make_universe("A")
        self.b = _make_universe("B")
        self.ctrl = MultiverseController(self.a, self.b)

    def test_adds_coupling_mode(self):
        """Divergence adds a new mode state to coupling landscape."""
        before = len(self.ctrl.coupling._states)
        self.ctrl.apply_divergence_pressure()
        after = len(self.ctrl.coupling._states)
        self.assertGreater(after, before)

    def test_adds_coupling_edges(self):
        """Divergence adds new edges to coupling landscape."""
        before = len(self.ctrl.coupling._delta)
        self.ctrl.apply_divergence_pressure()
        after = len(self.ctrl.coupling._delta)
        self.assertGreaterEqual(after, before + 2)

    def test_adds_universe_edges(self):
        """Divergence adds exploration edges to universes."""
        edges_a_before = len(self.a.landscape._delta)
        edges_b_before = len(self.b.landscape._delta)
        self.ctrl.apply_divergence_pressure()
        edges_a_after = len(self.a.landscape._delta)
        edges_b_after = len(self.b.landscape._delta)
        total_new = (edges_a_after - edges_a_before) + (edges_b_after - edges_b_before)
        self.assertGreater(total_new, 0)

    def test_returns_count(self):
        """Returns total number of new edges."""
        added = self.ctrl.apply_divergence_pressure()
        self.assertGreaterEqual(added, 3)  # 2 coupling + 1+ universe

    def test_multiple_divergences(self):
        """Multiple divergence applications create distinct modes."""
        self.ctrl.apply_divergence_pressure()
        self.ctrl.apply_divergence_pressure()
        self.assertIn("mode_1", self.ctrl.coupling._states)
        self.assertIn("mode_2", self.ctrl.coupling._states)


# ══════════════════════════════════════════════
# Test: Full run
# ══════════════════════════════════════════════

class TestMultiverseRun(unittest.TestCase):
    """Full multiverse orchestration."""

    def test_max_turns_respected(self):
        """Run stops after max_turns."""
        a = _make_universe("A")
        b = _make_universe("B")
        ctrl = MultiverseController(a, b)
        result = ctrl.run(max_turns=5, turn_fn=lambda a, p: None)
        self.assertEqual(result.total_turns, 5)

    def test_convergence_triggers_divergence(self):
        """Stale turns trigger divergence pressure."""
        a = _make_universe("A")
        b = _make_universe("B")
        ctrl = MultiverseController(a, b, convergence_window=2)
        result = ctrl.run(max_turns=6, turn_fn=lambda a, p: None)
        self.assertGreater(result.divergence_count, 0)

    def test_divergence_produces_novelty(self):
        """After divergence, the injected edges count as novelty."""
        a = _make_universe("A")
        b = _make_universe("B")
        ctrl = MultiverseController(a, b, convergence_window=2)
        # Stale turns → convergence → divergence adds edges → next turn sees novelty
        result = ctrl.run(max_turns=6, turn_fn=lambda a, p: None)
        # The divergence pressure adds edges, so the turn AFTER divergence
        # should see novelty (from the injected edges)
        self.assertGreater(result.total_novelty, 0)

    def test_novel_turns_prevent_divergence(self):
        """Consistently novel turns never trigger divergence."""
        a = _make_universe("A")
        b = _make_universe("B")
        ctrl = MultiverseController(a, b, convergence_window=3)
        counter = [0]
        def always_novel(active, passive):
            counter[0] += 1
            active.landscape.add_edge(
                "S", f"X{counter[0]}", delta=0.5, resistance=0.3,
            )
        result = ctrl.run(max_turns=6, turn_fn=always_novel)
        self.assertEqual(result.divergence_count, 0)
        self.assertEqual(result.total_novelty, 6)

    def test_coupling_landscape_grows(self):
        """Coupling landscape accumulates modes from divergence."""
        a = _make_universe("A")
        b = _make_universe("B")
        ctrl = MultiverseController(a, b, convergence_window=2)
        ctrl.run(max_turns=10, turn_fn=lambda a, p: None)
        # Should have original 2 states + modes from divergence
        self.assertGreater(len(ctrl.coupling._states), 2)


# ══════════════════════════════════════════════
# Test: MultiverseResult
# ══════════════════════════════════════════════

class TestMultiverseResult(unittest.TestCase):
    """Result properties and summary."""

    def test_novelty_rate(self):
        """Novelty rate computed correctly."""
        result = MultiverseResult(turns=[
            MultiverseTurn(0, "A", True, Outcome.SUCCESS),
            MultiverseTurn(1, "B", False, Outcome.FAILURE),
            MultiverseTurn(2, "A", True, Outcome.SUCCESS),
            MultiverseTurn(3, "B", False, Outcome.FAILURE),
        ])
        self.assertAlmostEqual(result.novelty_rate, 0.5)

    def test_empty_result(self):
        """Empty result has zero novelty rate."""
        result = MultiverseResult()
        self.assertEqual(result.total_turns, 0)
        self.assertAlmostEqual(result.novelty_rate, 0.0)

    def test_summary_contains_key_info(self):
        """Summary includes turn count, novelty, convergence."""
        result = MultiverseResult(
            turns=[MultiverseTurn(0, "A", False, Outcome.FAILURE)] * 4,
            convergence_turn=2,
            divergence_count=1,
            novelty_edges_added=4,
        )
        s = result.summary()
        self.assertIn("Turns: 4", s)
        self.assertIn("Convergence at turn 2", s)
        self.assertIn("Divergence pressure applied: 1x", s)


if __name__ == "__main__":
    unittest.main()
