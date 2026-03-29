"""
E₀ Mode Controller — Unit Tests (C46)
=======================================
Tests for OperatingMode enum and ModeController class.
"""

from __future__ import annotations

import unittest

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.historization import Historization
from e0_controller.mode_controller import ModeController, OperatingMode


def _make_landscape(*edges, inertia=False, rho=1.0):
    """Create a simple landscape with the given edges.

    Uses rho=1.0 by default so trace counts are exact (no decay).
    """
    ls = Landscape(inertia_modulation=inertia, historization=Historization(rho=rho))
    nodes = set()
    for src, tgt in edges:
        nodes.add(src)
        nodes.add(tgt)
    for n in sorted(nodes):
        ls.add_state(n)
    for src, tgt in edges:
        ls.add_edge(src, tgt, delta=0.5, resistance=1.0)
    return ls


def _inject_traces(ls, edge, u_count, f_count):
    """Inject success/failure traces on an edge."""
    for _ in range(u_count):
        ls.historization.update(edge, Outcome.SUCCESS)
    for _ in range(f_count):
        ls.historization.update(edge, Outcome.FAILURE)


# ──────────────────────────────────────────────
# 1. OperatingMode Enum
# ──────────────────────────────────────────────

class TestOperatingMode(unittest.TestCase):

    def test_values(self):
        self.assertEqual(OperatingMode.LEARN.value, "learn")
        self.assertEqual(OperatingMode.EXECUTE.value, "execute")
        self.assertEqual(OperatingMode.COMBINATION.value, "combination")

    def test_all_members(self):
        self.assertEqual(len(OperatingMode), 3)

    def test_from_value(self):
        self.assertEqual(OperatingMode("learn"), OperatingMode.LEARN)
        self.assertEqual(OperatingMode("execute"), OperatingMode.EXECUTE)
        self.assertEqual(OperatingMode("combination"), OperatingMode.COMBINATION)


# ──────────────────────────────────────────────
# 2. Edge-Level Assessment
# ──────────────────────────────────────────────

class TestEdgeAssessment(unittest.TestCase):

    def test_virgin_edge_needs_llm(self):
        ls = _make_landscape(("A", "B"))
        mc = ModeController(ls)
        self.assertTrue(mc.edge_needs_llm(Edge("A", "B")))

    def test_explored_edge_does_not_need_llm(self):
        ls = _make_landscape(("A", "B"))
        _inject_traces(ls, Edge("A", "B"), 6, 0)  # load=6 > μ=5
        mc = ModeController(ls)
        self.assertFalse(mc.edge_needs_llm(Edge("A", "B")))

    def test_edge_load_matches_trace_load(self):
        ls = _make_landscape(("A", "B"))
        _inject_traces(ls, Edge("A", "B"), 3, 2)
        mc = ModeController(ls)
        expected = ls.historization.trace_load(Edge("A", "B"))
        self.assertAlmostEqual(mc.edge_load(Edge("A", "B")), expected)

    def test_edge_above_mu_is_explored(self):
        ls = _make_landscape(("A", "B"))
        _inject_traces(ls, Edge("A", "B"), 5, 0)  # load=5 = μ
        mc = ModeController(ls)
        self.assertTrue(mc.edge_explored(Edge("A", "B")))

    def test_edge_just_below_mu_needs_llm(self):
        ls = _make_landscape(("A", "B"))
        _inject_traces(ls, Edge("A", "B"), 4, 0)  # load=4 < μ=5
        mc = ModeController(ls)
        self.assertTrue(mc.edge_needs_llm(Edge("A", "B")))

    def test_custom_mu(self):
        ls = _make_landscape(("A", "B"))
        _inject_traces(ls, Edge("A", "B"), 3, 0)  # load = 3
        mc_low = ModeController(ls, mu=2.0)
        mc_high = ModeController(ls, mu=10.0)
        self.assertTrue(mc_low.edge_explored(Edge("A", "B")))
        self.assertFalse(mc_high.edge_explored(Edge("A", "B")))


# ──────────────────────────────────────────────
# 3. Coverage Statistics
# ──────────────────────────────────────────────

class TestCoverage(unittest.TestCase):

    def test_empty_landscape(self):
        ls = Landscape()
        mc = ModeController(ls)
        cov = mc.coverage()
        self.assertEqual(cov["total"], 0)
        self.assertEqual(cov["ratio"], 0.0)

    def test_all_unexplored(self):
        ls = _make_landscape(("A", "B"), ("B", "C"), ("C", "A"))
        mc = ModeController(ls)
        cov = mc.coverage()
        self.assertEqual(cov["total"], 3)
        self.assertEqual(cov["explored"], 0)
        self.assertEqual(cov["unexplored"], 3)
        self.assertAlmostEqual(cov["ratio"], 0.0)

    def test_all_explored(self):
        ls = _make_landscape(("A", "B"), ("B", "C"))
        for e in [Edge("A", "B"), Edge("B", "C")]:
            _inject_traces(ls, e, 6, 0)
        mc = ModeController(ls)
        cov = mc.coverage()
        self.assertEqual(cov["explored"], 2)
        self.assertAlmostEqual(cov["ratio"], 1.0)

    def test_partial_coverage(self):
        ls = _make_landscape(("A", "B"), ("B", "C"), ("A", "C"))
        _inject_traces(ls, Edge("A", "B"), 6, 0)  # explored
        # B→C and A→C remain unexplored
        mc = ModeController(ls)
        cov = mc.coverage()
        self.assertEqual(cov["explored"], 1)
        self.assertEqual(cov["unexplored"], 2)
        self.assertAlmostEqual(cov["ratio"], 1 / 3, places=4)


# ──────────────────────────────────────────────
# 4. Mode Determination
# ──────────────────────────────────────────────

class TestCurrentMode(unittest.TestCase):

    def test_empty_landscape_is_learn(self):
        ls = Landscape()
        mc = ModeController(ls)
        self.assertEqual(mc.current_mode(), OperatingMode.LEARN)

    def test_all_virgin_is_learn(self):
        ls = _make_landscape(("A", "B"), ("B", "C"), ("C", "A"),
                             ("A", "C"), ("C", "B"))
        mc = ModeController(ls)
        self.assertEqual(mc.current_mode(), OperatingMode.LEARN)

    def test_all_explored_is_execute(self):
        ls = _make_landscape(("A", "B"), ("B", "C"))
        for e in [Edge("A", "B"), Edge("B", "C")]:
            _inject_traces(ls, e, 6, 0)
        mc = ModeController(ls)
        self.assertEqual(mc.current_mode(), OperatingMode.EXECUTE)

    def test_mostly_unexplored_is_learn(self):
        """With default learn_ratio=0.8, ≥80% unexplored → LEARN."""
        ls = _make_landscape(("A", "B"), ("B", "C"), ("C", "A"),
                             ("A", "C"), ("C", "B"))
        # 0 of 5 explored → 100% unexplored → LEARN
        mc = ModeController(ls)
        self.assertEqual(mc.current_mode(), OperatingMode.LEARN)
        # 1 of 5 explored → 80% unexplored → borderline, use explicit ratio
        _inject_traces(ls, Edge("A", "B"), 6, 0)
        mc2 = ModeController(ls, learn_ratio=0.75)  # need >75% unexplored
        self.assertEqual(mc2.current_mode(), OperatingMode.LEARN)

    def test_half_explored_is_combination(self):
        """50% explored → not enough for EXECUTE, not enough for LEARN → COMBINATION."""
        ls = _make_landscape(("A", "B"), ("B", "C"), ("C", "A"), ("A", "C"))
        _inject_traces(ls, Edge("A", "B"), 6, 0)
        _inject_traces(ls, Edge("B", "C"), 6, 0)
        mc = ModeController(ls)
        self.assertEqual(mc.current_mode(), OperatingMode.COMBINATION)

    def test_one_unexplored_is_combination(self):
        """One edge remaining unexplored → not EXECUTE."""
        ls = _make_landscape(("A", "B"), ("B", "C"))
        _inject_traces(ls, Edge("A", "B"), 6, 0)
        mc = ModeController(ls)
        mode = mc.current_mode()
        self.assertEqual(mode, OperatingMode.COMBINATION)

    def test_custom_learn_ratio(self):
        """Lower learn_ratio makes LEARN harder to trigger."""
        ls = _make_landscape(("A", "B"), ("B", "C"), ("C", "A"))
        # All unexplored
        mc_strict = ModeController(ls, learn_ratio=0.5)
        self.assertEqual(mc_strict.current_mode(), OperatingMode.LEARN)
        # Explore 1 of 3 → 67% unexplored, but learn_ratio=0.5 means
        # need ≥50% unexplored for LEARN → ratio_explored=0.33 ≤ 0.5 → LEARN
        _inject_traces(ls, Edge("A", "B"), 6, 0)
        self.assertEqual(mc_strict.current_mode(), OperatingMode.LEARN)

    def test_mode_evolves_with_experience(self):
        """Mode transitions: LEARN → COMBINATION → EXECUTE as edges get explored."""
        ls = _make_landscape(("A", "B"), ("B", "C"), ("C", "A"),
                             ("A", "C"), ("C", "B"))
        mc = ModeController(ls)

        # Phase 1: all virgin → LEARN
        self.assertEqual(mc.current_mode(), OperatingMode.LEARN)

        # Phase 2: some explored → COMBINATION
        _inject_traces(ls, Edge("A", "B"), 6, 0)
        _inject_traces(ls, Edge("B", "C"), 6, 0)
        _inject_traces(ls, Edge("C", "A"), 6, 0)
        self.assertEqual(mc.current_mode(), OperatingMode.COMBINATION)

        # Phase 3: all explored → EXECUTE
        _inject_traces(ls, Edge("A", "C"), 6, 0)
        _inject_traces(ls, Edge("C", "B"), 6, 0)
        self.assertEqual(mc.current_mode(), OperatingMode.EXECUTE)


# ──────────────────────────────────────────────
# 5. Edge Lists
# ──────────────────────────────────────────────

class TestEdgeLists(unittest.TestCase):

    def test_unexplored_edges(self):
        ls = _make_landscape(("A", "B"), ("B", "C"))
        _inject_traces(ls, Edge("A", "B"), 6, 0)
        mc = ModeController(ls)
        unexplored = mc.unexplored_edges()
        self.assertEqual(len(unexplored), 1)
        self.assertEqual(unexplored[0], Edge("B", "C"))

    def test_explored_edges(self):
        ls = _make_landscape(("A", "B"), ("B", "C"))
        _inject_traces(ls, Edge("A", "B"), 6, 0)
        mc = ModeController(ls)
        explored = mc.explored_edges()
        self.assertEqual(len(explored), 1)
        self.assertEqual(explored[0], Edge("A", "B"))

    def test_all_edges_consistent(self):
        ls = _make_landscape(("A", "B"), ("B", "C"), ("C", "A"))
        mc = ModeController(ls)
        total = len(mc.unexplored_edges()) + len(mc.explored_edges())
        self.assertEqual(total, 3)


# ──────────────────────────────────────────────
# 6. Neighbor Filtering
# ──────────────────────────────────────────────

class TestNeighborFiltering(unittest.TestCase):

    def test_neighbors_needing_llm(self):
        ls = _make_landscape(("A", "B"), ("A", "C"))
        _inject_traces(ls, Edge("A", "B"), 6, 0)
        mc = ModeController(ls)
        needs_llm = mc.neighbors_needing_llm("A")
        self.assertEqual(needs_llm, ["C"])

    def test_neighbors_autonomous(self):
        ls = _make_landscape(("A", "B"), ("A", "C"))
        _inject_traces(ls, Edge("A", "B"), 6, 0)
        mc = ModeController(ls)
        autonomous = mc.neighbors_autonomous("A")
        self.assertEqual(autonomous, ["B"])

    def test_no_outgoing_edges(self):
        ls = _make_landscape(("A", "B"))
        mc = ModeController(ls)
        self.assertEqual(mc.neighbors_needing_llm("B"), [])
        self.assertEqual(mc.neighbors_autonomous("B"), [])

    def test_all_neighbors_explored(self):
        ls = _make_landscape(("A", "B"), ("A", "C"))
        _inject_traces(ls, Edge("A", "B"), 6, 0)
        _inject_traces(ls, Edge("A", "C"), 6, 0)
        mc = ModeController(ls)
        self.assertEqual(mc.neighbors_needing_llm("A"), [])
        self.assertEqual(len(mc.neighbors_autonomous("A")), 2)


# ──────────────────────────────────────────────
# 7. Summary
# ──────────────────────────────────────────────

class TestSummary(unittest.TestCase):

    def test_summary_contains_all_keys(self):
        ls = _make_landscape(("A", "B"))
        mc = ModeController(ls)
        s = mc.summary()
        for key in ("mode", "mu", "learn_ratio", "total",
                    "explored", "unexplored", "ratio"):
            self.assertIn(key, s)

    def test_summary_mode_value(self):
        ls = _make_landscape(("A", "B"))
        mc = ModeController(ls)
        self.assertEqual(mc.summary()["mode"], "learn")

    def test_summary_reflects_state(self):
        ls = _make_landscape(("A", "B"))
        _inject_traces(ls, Edge("A", "B"), 6, 0)
        mc = ModeController(ls)
        s = mc.summary()
        self.assertEqual(s["mode"], "execute")
        self.assertEqual(s["explored"], 1)
        self.assertEqual(s["mu"], 5.0)


# ──────────────────────────────────────────────
# 8. Controller Integration
# ──────────────────────────────────────────────

class TestControllerIntegration(unittest.TestCase):

    def test_controller_has_mode_controller_attribute(self):
        from e0_controller.controller import E0Controller
        ls = _make_landscape(("A", "B"), ("B", "A"))
        ctrl = E0Controller(ls, lambda s, t: Outcome.SUCCESS)
        self.assertIsNone(ctrl.mode_controller)

    def test_attach_mode_controller(self):
        from e0_controller.controller import E0Controller
        ls = _make_landscape(("A", "B"), ("B", "A"))
        ctrl = E0Controller(ls, lambda s, t: Outcome.SUCCESS)
        mc = ModeController(ls)
        ctrl.mode_controller = mc
        self.assertIsNotNone(ctrl.mode_controller)
        self.assertEqual(ctrl.mode_controller.current_mode(), OperatingMode.LEARN)

    def test_mode_evolves_during_run(self):
        """Running the controller builds traces → mode changes."""
        from e0_controller.controller import E0Controller
        # Use rho=0.9 (real decay) with mu=2.0 (low threshold)
        ls = _make_landscape(("A", "B"), ("B", "A"), rho=0.9)
        ctrl = E0Controller(ls, lambda s, t: Outcome.SUCCESS)
        mc = ModeController(ls, mu=2.0)
        ctrl.mode_controller = mc

        # Before run: LEARN
        self.assertEqual(mc.current_mode(), OperatingMode.LEARN)

        # Run enough cycles to explore edges with ρ-decay
        ctrl.run("A", max_cycles=20)

        # After run: should have accumulated enough traces
        self.assertNotEqual(mc.current_mode(), OperatingMode.LEARN)


# ──────────────────────────────────────────────
# 9. Bootstrapper Integration
# ──────────────────────────────────────────────

class TestBootstrapperIntegration(unittest.TestCase):

    def test_bootstrapped_landscape_mode(self):
        """Bootstrapped landscape with initial traces starts in EXECUTE or COMBINATION."""
        from e0_controller.bootstrapper import bootstrap_landscape
        spec = {
            "nodes": ["A", "B", "C"],
            "edges": [
                {"from": "A", "to": "B", "delta": 0.5, "resistance": 1.0,
                 "initial_U": 6.0, "initial_F": 1.0, "confidence": 0.9},
                {"from": "B", "to": "C", "delta": 0.5, "resistance": 1.0,
                 "initial_U": 5.0, "initial_F": 1.0, "confidence": 0.8},
            ],
        }
        ls = bootstrap_landscape(spec)
        mc = ModeController(ls)
        # Both edges have load ≥ 5 → should be EXECUTE
        self.assertEqual(mc.current_mode(), OperatingMode.EXECUTE)

    def test_bootstrapped_low_confidence_is_combination(self):
        """Low confidence reduces effective traces → COMBINATION."""
        from e0_controller.bootstrapper import bootstrap_landscape
        spec = {
            "nodes": ["A", "B", "C"],
            "edges": [
                {"from": "A", "to": "B", "delta": 0.5, "resistance": 1.0,
                 "initial_U": 6.0, "initial_F": 1.0, "confidence": 0.9},
                {"from": "B", "to": "C", "delta": 0.5, "resistance": 1.0,
                 "initial_U": 2.0, "initial_F": 1.0, "confidence": 0.3},
            ],
        }
        ls = bootstrap_landscape(spec)
        mc = ModeController(ls)
        # A→B has load ~7 (explored), B→C has load ~3 (unexplored)
        mode = mc.current_mode()
        self.assertEqual(mode, OperatingMode.COMBINATION)


if __name__ == "__main__":
    unittest.main()
