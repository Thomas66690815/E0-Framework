"""
Tests for E₀ Observation Controller (C95)
==========================================
Navigation, projection, historization learning.
"""

from __future__ import annotations

import math
import unittest

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.observation import (
    DEPTHS,
    DEPTH_INDEX,
    encode_state,
    decode_state,
)
from e0_controller.observation_controller import (
    ObservationController,
    StepResult,
)


# ── Helpers ──────────────────────────────────────────────

def _triangle() -> Landscape:
    """A→B→C→A, 3 nodes, 3 edges."""
    L = Landscape()
    L.add_edge("A", "B", delta=0.5, resistance=0.3)
    L.add_edge("B", "C", delta=0.5, resistance=0.3)
    L.add_edge("C", "A", delta=0.5, resistance=0.3)
    return L


def _greedy_trap() -> Landscape:
    """S→A, A↔C, A→B→D→GOAL. 6 nodes."""
    L = Landscape()
    L.add_edge("S", "A", delta=0.3, resistance=0.4)
    L.add_edge("A", "B", delta=0.3, resistance=0.5)
    L.add_edge("B", "D", delta=0.3, resistance=0.5)
    L.add_edge("D", "GOAL", delta=0.2, resistance=0.3)
    L.add_edge("A", "C", delta=0.2, resistance=0.4)
    L.add_edge("C", "A", delta=0.2, resistance=0.4)
    return L


# ══════════════════════════════════════════════════════════
# 1. Initialization
# ══════════════════════════════════════════════════════════

class TestInit(unittest.TestCase):

    def test_starts_at_global_topo(self):
        oc = ObservationController(_triangle())
        self.assertEqual(oc.current, "g:topo")
        self.assertEqual(oc.scope, "g")
        self.assertEqual(oc.depth, "topo")
        self.assertEqual(oc.depth_index, 0)

    def test_focused_node_none_at_init(self):
        oc = ObservationController(_triangle())
        self.assertIsNone(oc.focused_node)

    def test_history_empty_at_init(self):
        oc = ObservationController(_triangle())
        self.assertEqual(oc.history, [])

    def test_custom_depths(self):
        oc = ObservationController(_triangle(), depths=["topo", "field"])
        self.assertEqual(oc.current, "g:topo")
        # deepen should go to field
        r = oc.deepen()
        self.assertTrue(r.success)
        self.assertEqual(oc.depth, "field")
        # deepen again should fail (only 2 depths)
        r = oc.deepen()
        self.assertFalse(r.success)

    def test_repr(self):
        oc = ObservationController(_triangle())
        self.assertIn("g:topo", repr(oc))


# ══════════════════════════════════════════════════════════
# 2. Navigation Primitives
# ══════════════════════════════════════════════════════════

class TestNavigation(unittest.TestCase):

    def test_deepen(self):
        oc = ObservationController(_triangle())
        r = oc.deepen()
        self.assertTrue(r.success)
        self.assertEqual(oc.depth, "field")
        self.assertEqual(oc.scope, "g")

    def test_deepen_chain(self):
        oc = ObservationController(_triangle())
        for expected in ["field", "dyn", "mech", "intf"]:
            r = oc.deepen()
            self.assertTrue(r.success)
            self.assertEqual(oc.depth, expected)

    def test_deepen_at_max_fails(self):
        oc = ObservationController(_triangle())
        for _ in range(4):
            oc.deepen()
        r = oc.deepen()
        self.assertFalse(r.success)
        self.assertEqual(oc.depth, "intf")

    def test_retreat(self):
        oc = ObservationController(_triangle())
        oc.deepen()
        r = oc.retreat()
        self.assertTrue(r.success)
        self.assertEqual(oc.depth, "topo")

    def test_retreat_at_min_fails(self):
        oc = ObservationController(_triangle())
        r = oc.retreat()
        self.assertFalse(r.success)
        self.assertEqual(oc.depth, "topo")

    def test_focus(self):
        oc = ObservationController(_triangle())
        r = oc.focus("A")
        self.assertTrue(r.success)
        self.assertEqual(oc.scope, "n:A")
        self.assertEqual(oc.focused_node, "A")
        self.assertEqual(oc.depth, "topo")

    def test_focus_nonexistent_node_fails(self):
        oc = ObservationController(_triangle())
        r = oc.focus("NONEXISTENT")
        self.assertFalse(r.success)
        self.assertEqual(oc.scope, "g")

    def test_defocus(self):
        oc = ObservationController(_triangle())
        oc.focus("B")
        r = oc.defocus()
        self.assertTrue(r.success)
        self.assertEqual(oc.scope, "g")
        self.assertIsNone(oc.focused_node)

    def test_defocus_from_global_fails(self):
        oc = ObservationController(_triangle())
        r = oc.defocus()
        self.assertFalse(r.success)

    def test_move_between_neighbors(self):
        oc = ObservationController(_triangle())
        oc.focus("A")
        # A→B is a domain edge
        r = oc.move("B")
        self.assertTrue(r.success)
        self.assertEqual(oc.focused_node, "B")

    def test_move_non_neighbor_fails(self):
        oc = ObservationController(_triangle())
        oc.focus("A")
        # A→C is not a domain edge (only C→A exists)
        r = oc.move("C")
        self.assertFalse(r.success)
        self.assertEqual(oc.focused_node, "A")

    def test_move_from_global_acts_as_focus(self):
        """move() from global is structurally identical to focus()."""
        oc = ObservationController(_triangle())
        r = oc.move("A")
        self.assertTrue(r.success)
        self.assertEqual(oc.focused_node, "A")

    def test_navigate_arbitrary(self):
        oc = ObservationController(_triangle())
        r = oc.navigate("g:field")
        self.assertTrue(r.success)
        self.assertEqual(oc.current, "g:field")

    def test_navigate_inadmissible_fails(self):
        oc = ObservationController(_triangle())
        # Cross-transition: scope + depth at once
        r = oc.navigate("n:A:field")
        self.assertFalse(r.success)

    def test_focus_then_deepen(self):
        """Canonical observation pattern: focus, then deepen."""
        oc = ObservationController(_triangle())
        oc.focus("A")
        oc.deepen()
        self.assertEqual(oc.scope, "n:A")
        self.assertEqual(oc.depth, "field")


# ══════════════════════════════════════════════════════════
# 3. History & Trajectory
# ══════════════════════════════════════════════════════════

class TestHistory(unittest.TestCase):

    def test_history_records_previous_states(self):
        oc = ObservationController(_triangle())
        oc.deepen()
        oc.deepen()
        self.assertEqual(oc.history, ["g:topo", "g:field"])

    def test_history_not_recorded_on_failure(self):
        oc = ObservationController(_triangle())
        oc.retreat()  # fails
        self.assertEqual(oc.history, [])

    def test_history_is_copy(self):
        oc = ObservationController(_triangle())
        oc.deepen()
        h = oc.history
        h.append("junk")
        self.assertEqual(len(oc.history), 1)


# ══════════════════════════════════════════════════════════
# 4. StepResult
# ══════════════════════════════════════════════════════════

class TestStepResult(unittest.TestCase):

    def test_success_result_has_finite_costs(self):
        oc = ObservationController(_triangle())
        r = oc.deepen()
        self.assertTrue(r.success)
        self.assertLess(r.r_eff, math.inf)
        self.assertLess(r.s_eff, math.inf)
        self.assertGreater(r.r_eff, 0)
        self.assertGreater(r.s_eff, 0)

    def test_failure_result_has_infinite_costs(self):
        oc = ObservationController(_triangle())
        r = oc.retreat()  # fails
        self.assertFalse(r.success)
        self.assertEqual(r.r_eff, math.inf)
        self.assertEqual(r.s_eff, math.inf)

    def test_result_tracks_previous_and_current(self):
        oc = ObservationController(_triangle())
        r = oc.deepen()
        self.assertEqual(r.previous, "g:topo")
        self.assertEqual(r.current, "g:field")


# ══════════════════════════════════════════════════════════
# 5. Historization (Observer Learning)
# ══════════════════════════════════════════════════════════

class TestObserverLearning(unittest.TestCase):

    def test_repeated_deepen_lowers_resistance(self):
        oc = ObservationController(_triangle())
        r1 = oc.deepen()
        r_first = r1.r_eff

        oc.retreat()
        r2 = oc.deepen()
        r_second = r2.r_eff

        self.assertLess(r_second, r_first)

    def test_repeated_focus_lowers_resistance(self):
        oc = ObservationController(_triangle())
        r1 = oc.focus("A")
        r_first = r1.r_eff

        oc.defocus()
        r2 = oc.focus("A")
        r_second = r2.r_eff

        self.assertLess(r_second, r_first)

    def test_unfocused_node_stays_harder(self):
        oc = ObservationController(_triangle())
        # Focus on A three times
        for _ in range(3):
            oc.focus("A")
            oc.defocus()

        r_a = oc.resistance_to("n:A:topo")
        r_b = oc.resistance_to("n:B:topo")
        self.assertLess(r_a, r_b)


# ══════════════════════════════════════════════════════════
# 6. Projection (project)
# ══════════════════════════════════════════════════════════

class TestProjection(unittest.TestCase):

    def test_topo_has_nodes_and_edges(self):
        oc = ObservationController(_triangle())
        p = oc.project()
        self.assertEqual(p["scope"], "g")
        self.assertEqual(p["depth"], "topo")
        self.assertEqual(sorted(p["nodes"]), ["A", "B", "C"])
        self.assertEqual(len(p["edges"]), 3)
        self.assertNotIn("field", p)
        self.assertNotIn("dynamics", p)

    def test_field_adds_scalar_data(self):
        oc = ObservationController(_triangle())
        oc.deepen()
        p = oc.project()
        self.assertIn("field", p)
        self.assertEqual(len(p["field"]), 3)
        for key, val in p["field"].items():
            self.assertIn("delta", val)
            self.assertIn("R0", val)
            self.assertIn("R_eff", val)
            self.assertIn("S_eff", val)

    def test_dyn_adds_historization(self):
        oc = ObservationController(_triangle())
        oc.deepen()
        oc.deepen()
        p = oc.project()
        self.assertIn("dynamics", p)
        self.assertIn("field", p)  # cumulative

    def test_mech_and_intf_are_extension_points(self):
        oc = ObservationController(_triangle())
        for _ in range(4):
            oc.deepen()
        p = oc.project()
        self.assertIn("mechanism", p)
        self.assertIn("interference", p)
        # Currently empty dicts — extension points
        self.assertEqual(p["mechanism"], {})
        self.assertEqual(p["interference"], {})

    def test_local_scope_limits_visibility(self):
        oc = ObservationController(_greedy_trap())
        oc.focus("A")
        p = oc.project()
        # A has neighbors: S (incoming), B, C (outgoing)
        self.assertIn("A", p["nodes"])
        self.assertIn("B", p["nodes"])
        self.assertIn("C", p["nodes"])
        self.assertIn("S", p["nodes"])
        # D and GOAL are not visible from A's neighborhood
        self.assertNotIn("D", p["nodes"])
        self.assertNotIn("GOAL", p["nodes"])

    def test_global_scope_shows_all(self):
        oc = ObservationController(_greedy_trap())
        p = oc.project()
        self.assertEqual(len(p["nodes"]), 6)

    def test_local_field_values_correct(self):
        domain = _triangle()
        oc = ObservationController(domain)
        oc.focus("A")
        oc.deepen()
        p = oc.project()
        # A→B edge visible
        self.assertIn("A→B", p["field"])
        self.assertAlmostEqual(p["field"]["A→B"]["delta"], 0.5)
        self.assertAlmostEqual(p["field"]["A→B"]["R0"], 0.3)

    def test_dyn_with_historization(self):
        """After running domain transitions, dynamics layer shows traces."""
        domain = _triangle()
        # Simulate some domain historization
        domain.historization.update(Edge("A", "B"), Outcome.SUCCESS)
        domain.historization.update(Edge("A", "B"), Outcome.SUCCESS)
        domain.historization.update(Edge("B", "C"), Outcome.FAILURE)

        oc = ObservationController(domain)
        oc.deepen()
        oc.deepen()
        p = oc.project()
        self.assertGreater(p["dynamics"]["A→B"]["success_trace"], 0)
        self.assertAlmostEqual(p["dynamics"]["A→B"]["failure_trace"], 0)
        self.assertGreater(p["dynamics"]["A→B"]["trace_load"], 0)
        self.assertGreater(p["dynamics"]["B→C"]["failure_trace"], 0)


# ══════════════════════════════════════════════════════════
# 7. Options
# ══════════════════════════════════════════════════════════

class TestOptions(unittest.TestCase):

    def test_options_from_global_topo(self):
        oc = ObservationController(_triangle())
        opts = oc.options()
        # From g:topo: deepen to g:field + focus on A, B, C
        self.assertEqual(len(opts), 4)
        targets = {o["target"] for o in opts}
        self.assertIn("g:field", targets)
        self.assertIn("n:A:topo", targets)
        self.assertIn("n:B:topo", targets)
        self.assertIn("n:C:topo", targets)

    def test_options_sorted_by_tension(self):
        oc = ObservationController(_triangle())
        opts = oc.options()
        tensions = [o["s_eff"] for o in opts]
        self.assertEqual(tensions, sorted(tensions))

    def test_options_at_local_scope(self):
        oc = ObservationController(_triangle())
        oc.focus("A")
        opts = oc.options()
        targets = {o["target"] for o in opts}
        # From n:A:topo: deepen to n:A:field, defocus to g:topo, move to B (A→B exists)
        self.assertIn("n:A:field", targets)
        self.assertIn("g:topo", targets)
        self.assertIn("n:B:topo", targets)
        # A→C does not exist, so n:C:topo not in options
        self.assertNotIn("n:C:topo", targets)


# ══════════════════════════════════════════════════════════
# 8. Resistance/Tension queries
# ══════════════════════════════════════════════════════════

class TestCostQueries(unittest.TestCase):

    def test_resistance_to_adjacent(self):
        oc = ObservationController(_triangle())
        r = oc.resistance_to("g:field")
        self.assertGreater(r, 0)
        self.assertLess(r, math.inf)

    def test_resistance_to_non_adjacent(self):
        oc = ObservationController(_triangle())
        r = oc.resistance_to("n:A:field")
        self.assertEqual(r, math.inf)

    def test_tension_to_adjacent(self):
        oc = ObservationController(_triangle())
        t = oc.tension_to("g:field")
        self.assertGreater(t, 0)
        self.assertLess(t, math.inf)


# ══════════════════════════════════════════════════════════
# 9. Composite Observation Patterns
# ══════════════════════════════════════════════════════════

class TestCompositePatterns(unittest.TestCase):

    def test_drill_down_pattern(self):
        """Focus → deepen → deepen → deepen: explore one node deeply."""
        oc = ObservationController(_triangle())
        oc.focus("B")
        oc.deepen()
        oc.deepen()
        oc.deepen()
        self.assertEqual(oc.scope, "n:B")
        self.assertEqual(oc.depth, "mech")
        p = oc.project()
        self.assertIn("mechanism", p)
        self.assertIn("field", p)

    def test_survey_pattern(self):
        """Deepen → focus A → move B → move C: survey at field depth."""
        domain = _triangle()
        oc = ObservationController(domain)
        oc.deepen()        # g:topo → g:field
        oc.focus("A")      # g:field → n:A:field
        oc.move("B")       # n:A:field → n:B:field (A→B exists)
        oc.move("C")       # n:B:field → n:C:field (B→C exists)
        self.assertEqual(oc.scope, "n:C")
        self.assertEqual(oc.depth, "field")
        self.assertEqual(len(oc.history), 4)

    def test_zoom_in_out_pattern(self):
        """Focus → deepen → retreat → defocus: quick inspection."""
        oc = ObservationController(_triangle())
        oc.focus("A")
        oc.deepen()
        self.assertEqual(oc.current, "n:A:field")
        oc.retreat()
        self.assertEqual(oc.current, "n:A:topo")
        oc.defocus()
        self.assertEqual(oc.current, "g:topo")

    def test_learning_trajectory(self):
        """Repeated traversal of the same edge lowers its resistance."""
        oc = ObservationController(_triangle())
        # First deepen: observe g:topo→g:field
        r1 = oc.deepen()
        r_first = r1.r_eff
        oc.retreat()

        # Second deepen: same edge, now with historization
        r2 = oc.deepen()
        r_second = r2.r_eff
        self.assertLess(r_second, r_first)


if __name__ == "__main__":
    unittest.main()
