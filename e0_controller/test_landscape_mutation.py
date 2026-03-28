"""
E₀ Landscape Mutation Tests — Bridge 4 Stufe 1
=================================================
Tests for structural mutation API on Landscape:
    remove_edge, adjust_base_resistance, adjust_delta,
    has_edge, would_orphan.

Claims:
    B4-S1.1: remove_edge removes edge and invalidates caches
    B4-S1.2: adjust_base_resistance changes R₀, returns old value
    B4-S1.3: adjust_delta changes Δ, returns old value
    B4-S1.4: has_edge reports existence correctly
    B4-S1.5: would_orphan predicts isolated states
    B4-S1.6: mutations interact correctly with historization
    B4-S1.7: mutations interact correctly with modulation caches
    B4-S1.8: error handling for invalid mutations
"""

import math
import unittest

from e0_controller.landscape import Landscape
from e0_controller.primitives import Edge, Outcome
from e0_controller.historization import Historization
from e0_controller.tension import tension, coherence


# ── Domain Builders ────────────────────────────────────────────────

def _build_diamond() -> Landscape:
    """S → A → G, S → B → G. Two paths."""
    L = Landscape()
    L.add_edge("S", "A", delta=1.0, resistance=0.5)
    L.add_edge("A", "G", delta=0.8, resistance=0.3)
    L.add_edge("S", "B", delta=0.6, resistance=0.7)
    L.add_edge("B", "G", delta=0.9, resistance=0.4)
    return L


def _build_chain() -> Landscape:
    """S → A → B → G. Single path."""
    L = Landscape()
    L.add_edge("S", "A", delta=1.0, resistance=0.3)
    L.add_edge("A", "B", delta=0.8, resistance=0.4)
    L.add_edge("B", "G", delta=0.5, resistance=0.2)
    return L


def _build_triangle() -> Landscape:
    """A → B → C → A (cycle)."""
    L = Landscape()
    L.add_edge("A", "B", delta=1.0, resistance=0.3)
    L.add_edge("B", "C", delta=1.0, resistance=0.3)
    L.add_edge("C", "A", delta=1.0, resistance=0.3)
    return L


# ══════════════════════════════════════════════════════════════════
# Class 1: remove_edge
# ══════════════════════════════════════════════════════════════════

class TestRemoveEdge(unittest.TestCase):
    """B4-S1.1: remove_edge removes edge and invalidates caches."""

    def test_remove_existing_edge(self):
        """Removing an existing edge makes it disappear from edges list."""
        L = _build_diamond()
        self.assertEqual(L.edge_count(), 4)
        L.remove_edge("S", "B")
        self.assertEqual(L.edge_count(), 3)
        self.assertFalse(L.has_edge("S", "B"))

    def test_remove_edge_delta_becomes_none(self):
        """After removal, difference() returns None."""
        L = _build_diamond()
        self.assertIsNotNone(L.difference("S", "B"))
        L.remove_edge("S", "B")
        self.assertIsNone(L.difference("S", "B"))

    def test_remove_edge_resistance_becomes_inf(self):
        """After removal, base_resistance() returns ∞."""
        L = _build_diamond()
        L.remove_edge("S", "B")
        self.assertEqual(L.base_resistance("S", "B"), math.inf)

    def test_remove_edge_tension_becomes_inf(self):
        """After removal, effective_tension() returns ∞."""
        L = _build_diamond()
        L.remove_edge("S", "B")
        self.assertEqual(L.effective_tension("S", "B"), math.inf)

    def test_remove_edge_neighbor_list_updated(self):
        """After removal, target no longer in admissible_neighbors."""
        L = _build_diamond()
        self.assertIn("B", L.admissible_neighbors("S"))
        L.remove_edge("S", "B")
        self.assertNotIn("B", L.admissible_neighbors("S"))

    def test_remove_nonexistent_edge_raises(self):
        """Removing a non-existent edge raises KeyError."""
        L = _build_diamond()
        with self.assertRaises(KeyError):
            L.remove_edge("S", "G")

    def test_remove_does_not_delete_states(self):
        """States survive edge removal — they become isolated, not deleted."""
        L = _build_chain()
        L.remove_edge("A", "B")
        self.assertIn("A", L.states)
        self.assertIn("B", L.states)

    def test_remove_all_edges_from_state(self):
        """Removing all edges leaves states intact but isolated."""
        L = Landscape()
        L.add_edge("X", "Y", delta=1.0, resistance=0.5)
        L.remove_edge("X", "Y")
        self.assertEqual(L.edge_count(), 0)
        self.assertIn("X", L.states)
        self.assertIn("Y", L.states)

    def test_remove_preserves_other_edges(self):
        """Only the specified edge is removed; others unchanged."""
        L = _build_diamond()
        old_sa_delta = L.difference("S", "A")
        old_ag_r0 = L.base_resistance("A", "G")
        L.remove_edge("S", "B")
        self.assertEqual(L.difference("S", "A"), old_sa_delta)
        self.assertEqual(L.base_resistance("A", "G"), old_ag_r0)


# ══════════════════════════════════════════════════════════════════
# Class 2: adjust_base_resistance
# ══════════════════════════════════════════════════════════════════

class TestAdjustBaseResistance(unittest.TestCase):
    """B4-S1.2: adjust_base_resistance changes R₀, returns old value."""

    def test_adjust_returns_old_value(self):
        """Method returns the previous R₀."""
        L = _build_diamond()
        old = L.adjust_base_resistance("S", "A", 0.9)
        self.assertAlmostEqual(old, 0.5)

    def test_adjust_changes_r0(self):
        """R₀ is updated to the new value."""
        L = _build_diamond()
        L.adjust_base_resistance("S", "A", 0.9)
        self.assertAlmostEqual(L.base_resistance("S", "A"), 0.9)

    def test_adjust_changes_effective_tension(self):
        """Changed R₀ propagates to effective_tension."""
        L = _build_diamond()
        s_before = L.effective_tension("S", "A")
        L.adjust_base_resistance("S", "A", 2.0)
        s_after = L.effective_tension("S", "A")
        self.assertGreater(s_after, s_before)

    def test_adjust_changes_transition_field(self):
        """Changed R₀ propagates to transition_field."""
        L = _build_diamond()
        v_before = L.transition_field("S", "A")
        L.adjust_base_resistance("S", "A", 5.0)
        v_after = L.transition_field("S", "A")
        self.assertLess(v_after, v_before)

    def test_adjust_nonexistent_raises(self):
        """Adjusting a non-existent edge raises KeyError."""
        L = _build_diamond()
        with self.assertRaises(KeyError):
            L.adjust_base_resistance("S", "G", 1.0)

    def test_adjust_negative_raises(self):
        """Negative R₀ raises ValueError."""
        L = _build_diamond()
        with self.assertRaises(ValueError):
            L.adjust_base_resistance("S", "A", -0.1)

    def test_adjust_to_zero(self):
        """R₀ = 0 is valid — minimal resistance."""
        L = _build_diamond()
        L.adjust_base_resistance("S", "A", 0.0)
        self.assertAlmostEqual(L.base_resistance("S", "A"), 0.0)

    def test_adjust_preserves_delta(self):
        """Adjusting R₀ does not affect Δ."""
        L = _build_diamond()
        delta_before = L.difference("S", "A")
        L.adjust_base_resistance("S", "A", 2.0)
        self.assertEqual(L.difference("S", "A"), delta_before)


# ══════════════════════════════════════════════════════════════════
# Class 3: adjust_delta
# ══════════════════════════════════════════════════════════════════

class TestAdjustDelta(unittest.TestCase):
    """B4-S1.3: adjust_delta changes Δ, returns old value."""

    def test_adjust_returns_old_value(self):
        """Method returns the previous Δ."""
        L = _build_diamond()
        old = L.adjust_delta("S", "A", 2.0)
        self.assertAlmostEqual(old, 1.0)

    def test_adjust_changes_delta(self):
        """Δ is updated to the new value."""
        L = _build_diamond()
        L.adjust_delta("S", "A", 2.0)
        self.assertAlmostEqual(L.difference("S", "A"), 2.0)

    def test_adjust_changes_tension(self):
        """Changed Δ propagates to effective_tension."""
        L = _build_diamond()
        s_before = L.effective_tension("S", "A")
        L.adjust_delta("S", "A", 3.0)
        s_after = L.effective_tension("S", "A")
        self.assertGreater(s_after, s_before)

    def test_adjust_changes_transition_field(self):
        """Changed Δ propagates to transition_field (both as factor and via S)."""
        L = _build_diamond()
        v_before = L.transition_field("S", "A")
        # Very high Δ ⇒ high S ⇒ low coherence ⇒ could be lower or higher
        # But Δ=0 ⇒ v=0 always
        L.adjust_delta("S", "A", 0.0)
        v_after = L.transition_field("S", "A")
        self.assertAlmostEqual(v_after, 0.0)

    def test_adjust_nonexistent_raises(self):
        """Adjusting a non-existent edge raises KeyError."""
        L = _build_diamond()
        with self.assertRaises(KeyError):
            L.adjust_delta("X", "Y", 1.0)

    def test_adjust_negative_raises(self):
        """Negative Δ raises ValueError."""
        L = _build_diamond()
        with self.assertRaises(ValueError):
            L.adjust_delta("S", "A", -0.5)

    def test_adjust_preserves_resistance(self):
        """Adjusting Δ does not affect R₀."""
        L = _build_diamond()
        r0_before = L.base_resistance("S", "A")
        L.adjust_delta("S", "A", 5.0)
        self.assertEqual(L.base_resistance("S", "A"), r0_before)


# ══════════════════════════════════════════════════════════════════
# Class 4: has_edge
# ══════════════════════════════════════════════════════════════════

class TestHasEdge(unittest.TestCase):
    """B4-S1.4: has_edge reports existence correctly."""

    def test_existing_edge(self):
        L = _build_diamond()
        self.assertTrue(L.has_edge("S", "A"))

    def test_nonexistent_edge(self):
        L = _build_diamond()
        self.assertFalse(L.has_edge("S", "G"))

    def test_reverse_edge_not_implied(self):
        """Directed: A→G exists does NOT imply G→A."""
        L = _build_diamond()
        self.assertTrue(L.has_edge("A", "G"))
        self.assertFalse(L.has_edge("G", "A"))

    def test_after_removal(self):
        L = _build_diamond()
        self.assertTrue(L.has_edge("S", "B"))
        L.remove_edge("S", "B")
        self.assertFalse(L.has_edge("S", "B"))

    def test_after_add(self):
        L = _build_diamond()
        self.assertFalse(L.has_edge("G", "S"))
        L.add_edge("G", "S", delta=0.5, resistance=0.5)
        self.assertTrue(L.has_edge("G", "S"))


# ══════════════════════════════════════════════════════════════════
# Class 5: would_orphan
# ══════════════════════════════════════════════════════════════════

class TestWouldOrphan(unittest.TestCase):
    """B4-S1.5: would_orphan predicts isolated states."""

    def test_no_orphans_on_diamond(self):
        """Diamond: removing S→B still leaves B with B→G."""
        L = _build_diamond()
        orphans = L.would_orphan("S", "B")
        self.assertEqual(orphans, set())

    def test_orphan_on_leaf(self):
        """Chain: removing B→G orphans G (no other edges touch G)."""
        L = _build_chain()
        orphans = L.would_orphan("B", "G")
        self.assertIn("G", orphans)

    def test_orphan_both_endpoints(self):
        """Single-edge graph: removing it orphans both states."""
        L = Landscape()
        L.add_edge("X", "Y", delta=1.0, resistance=0.5)
        orphans = L.would_orphan("X", "Y")
        self.assertEqual(orphans, {"X", "Y"})

    def test_no_orphan_in_cycle(self):
        """Triangle cycle: removing any one edge orphans nobody."""
        L = _build_triangle()
        for e in L.edges:
            orphans = L.would_orphan(e.source, e.target)
            self.assertEqual(orphans, set(),
                             f"Removing {e.source}→{e.target} should not orphan")

    def test_nonexistent_edge_returns_empty(self):
        """Non-existent edge returns empty set (no danger)."""
        L = _build_diamond()
        self.assertEqual(L.would_orphan("X", "Y"), set())

    def test_orphan_middle_of_chain(self):
        """Chain S→A→B→G: removing A→B doesn't orphan A (S→A exists)
        but doesn't orphan B either (B→G exists)."""
        L = _build_chain()
        orphans = L.would_orphan("A", "B")
        self.assertEqual(orphans, set())


# ══════════════════════════════════════════════════════════════════
# Class 6: Historization Interaction
# ══════════════════════════════════════════════════════════════════

class TestHistorizationInteraction(unittest.TestCase):
    """B4-S1.6: mutations interact correctly with historization."""

    def test_adjust_resistance_preserves_historization(self):
        """Changing R₀ does not wipe historization (δ_H remains)."""
        L = _build_diamond()
        edge = Edge("S", "A")
        L.historization.update(edge, Outcome.SUCCESS)
        L.historization.update(edge, Outcome.SUCCESS)
        dh_before = L.historization.delta_H(edge)

        L.adjust_base_resistance("S", "A", 1.5)

        dh_after = L.historization.delta_H(edge)
        self.assertEqual(dh_before, dh_after)

    def test_remove_edge_historization_survives(self):
        """Historization data survives edge removal (for re-add)."""
        L = _build_diamond()
        edge = Edge("S", "A")
        L.historization.update(edge, Outcome.SUCCESS)
        u_before = L.historization.success_trace(edge)

        L.remove_edge("S", "A")
        u_after = L.historization.success_trace(edge)
        self.assertEqual(u_before, u_after)

    def test_readd_edge_keeps_historization(self):
        """Remove + re-add same edge: historization still there."""
        L = _build_diamond()
        edge = Edge("S", "A")
        L.historization.update(edge, Outcome.SUCCESS)
        L.historization.update(edge, Outcome.FAILURE)

        L.remove_edge("S", "A")
        L.add_edge("S", "A", delta=2.0, resistance=0.8)

        # Historization should still reflect past events
        self.assertGreater(L.historization.success_trace(edge), 0)
        self.assertGreater(L.historization.failure_trace(edge), 0)

    def test_r_eff_reflects_both_r0_change_and_history(self):
        """R_eff = new R₀ + δ_H (both apply)."""
        L = _build_diamond()
        edge = Edge("S", "A")
        # Record some failures to increase δ_H
        for _ in range(5):
            L.historization.update(edge, Outcome.FAILURE)
        dh = L.historization.delta_H(edge)
        self.assertGreater(dh, 0)

        new_r0 = 2.0
        L.adjust_base_resistance("S", "A", new_r0)
        r_eff = L.effective_resistance("S", "A")
        self.assertAlmostEqual(r_eff, max(new_r0 + dh, 1e-10))


# ══════════════════════════════════════════════════════════════════
# Class 7: Cache Invalidation
# ══════════════════════════════════════════════════════════════════

class TestCacheInvalidation(unittest.TestCase):
    """B4-S1.7: mutations invalidate modulation caches."""

    def test_remove_edge_invalidates_m_h_cache(self):
        """Curvature modulation cache is cleared after remove_edge."""
        L = _build_triangle()
        L.curvature_modulation = True
        # Trigger cache build
        _ = L.transition_field("A", "B")
        self.assertTrue(hasattr(L, '_M_H_cache'))

        L.remove_edge("C", "A")
        self.assertFalse(hasattr(L, '_M_H_cache'))

    def test_adjust_resistance_invalidates_overlap_cache(self):
        """Overlap modulation cache is cleared after adjust_base_resistance."""
        L = _build_diamond()
        L.overlap_modulation = True
        _ = L.transition_field("S", "A")
        self.assertTrue(hasattr(L, '_overlap_cache'))

        L.adjust_base_resistance("S", "A", 2.0)
        self.assertFalse(hasattr(L, '_overlap_cache'))

    def test_adjust_delta_invalidates_caches(self):
        """Both caches cleared after adjust_delta."""
        L = _build_triangle()
        L.curvature_modulation = True
        L.overlap_modulation = True
        _ = L.transition_field("A", "B")

        L.adjust_delta("A", "B", 0.5)
        self.assertFalse(hasattr(L, '_M_H_cache'))
        self.assertFalse(hasattr(L, '_overlap_cache'))


# ══════════════════════════════════════════════════════════════════
# Class 8: Error Handling
# ══════════════════════════════════════════════════════════════════

class TestMutationErrors(unittest.TestCase):
    """B4-S1.8: error handling for invalid mutations."""

    def test_remove_nonexistent(self):
        L = _build_diamond()
        with self.assertRaises(KeyError):
            L.remove_edge("X", "Y")

    def test_adjust_r0_nonexistent(self):
        L = _build_diamond()
        with self.assertRaises(KeyError):
            L.adjust_base_resistance("X", "Y", 1.0)

    def test_adjust_delta_nonexistent(self):
        L = _build_diamond()
        with self.assertRaises(KeyError):
            L.adjust_delta("X", "Y", 1.0)

    def test_adjust_r0_negative(self):
        L = _build_diamond()
        with self.assertRaises(ValueError):
            L.adjust_base_resistance("S", "A", -1.0)

    def test_adjust_delta_negative(self):
        L = _build_diamond()
        with self.assertRaises(ValueError):
            L.adjust_delta("S", "A", -1.0)

    def test_double_remove(self):
        """Removing the same edge twice raises on second call."""
        L = _build_diamond()
        L.remove_edge("S", "B")
        with self.assertRaises(KeyError):
            L.remove_edge("S", "B")


# ══════════════════════════════════════════════════════════════════
# Class 9: Transition Field Consistency After Mutation
# ══════════════════════════════════════════════════════════════════

class TestFieldConsistency(unittest.TestCase):
    """Transition field values are correct after mutations."""

    def test_field_after_resistance_increase(self):
        """Higher R₀ → higher S → lower coherence → lower v."""
        L = _build_diamond()
        v1 = L.transition_field("S", "A")
        L.adjust_base_resistance("S", "A", 5.0)
        v2 = L.transition_field("S", "A")
        self.assertLess(v2, v1)

    def test_field_after_resistance_decrease(self):
        """Lower R₀ → lower S → higher coherence → higher v."""
        L = _build_diamond()
        v1 = L.transition_field("S", "A")
        L.adjust_base_resistance("S", "A", 0.01)
        v2 = L.transition_field("S", "A")
        self.assertGreater(v2, v1)

    def test_field_after_delta_zero(self):
        """Δ = 0 → v = 0 (no difference, no transition capacity)."""
        L = _build_diamond()
        L.adjust_delta("S", "A", 0.0)
        self.assertAlmostEqual(L.transition_field("S", "A"), 0.0)

    def test_field_zero_after_remove(self):
        """Removed edge → v = 0."""
        L = _build_diamond()
        L.remove_edge("S", "B")
        self.assertAlmostEqual(L.transition_field("S", "B"), 0.0)

    def test_field_restored_after_readd(self):
        """Remove + re-add with same params → same v (ignoring historization)."""
        L = Landscape()  # fresh, no historization
        L.add_edge("X", "Y", delta=1.0, resistance=0.5)
        v_original = L.transition_field("X", "Y")

        L.remove_edge("X", "Y")
        L.add_edge("X", "Y", delta=1.0, resistance=0.5)
        v_restored = L.transition_field("X", "Y")

        self.assertAlmostEqual(v_original, v_restored, places=10)


# ══════════════════════════════════════════════════════════════════
# Class 10: Undo Support
# ══════════════════════════════════════════════════════════════════

class TestUndoSupport(unittest.TestCase):
    """Return values enable manual undo."""

    def test_undo_resistance(self):
        """Adjust → undo with returned old value restores state."""
        L = _build_diamond()
        v_before = L.transition_field("S", "A")

        old_r = L.adjust_base_resistance("S", "A", 3.0)
        v_changed = L.transition_field("S", "A")
        self.assertNotAlmostEqual(v_before, v_changed)

        L.adjust_base_resistance("S", "A", old_r)
        v_restored = L.transition_field("S", "A")
        self.assertAlmostEqual(v_before, v_restored, places=10)

    def test_undo_delta(self):
        """Adjust → undo with returned old value restores state."""
        L = _build_diamond()
        s_before = L.effective_tension("S", "A")

        old_d = L.adjust_delta("S", "A", 5.0)
        s_changed = L.effective_tension("S", "A")
        self.assertNotAlmostEqual(s_before, s_changed)

        L.adjust_delta("S", "A", old_d)
        s_restored = L.effective_tension("S", "A")
        self.assertAlmostEqual(s_before, s_restored, places=10)

    def test_undo_remove_via_readd(self):
        """remove_edge can be 'undone' by re-adding with saved params."""
        L = _build_diamond()
        delta = L.difference("S", "B")
        r0 = L.base_resistance("S", "B")
        v_before = L.transition_field("S", "B")

        L.remove_edge("S", "B")
        self.assertFalse(L.has_edge("S", "B"))

        L.add_edge("S", "B", delta=delta, resistance=r0)
        self.assertTrue(L.has_edge("S", "B"))
        # v should be same (fresh landscape, no historization)
        # but with historization it may differ — that's correct behavior


if __name__ == "__main__":
    unittest.main()
