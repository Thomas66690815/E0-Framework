"""
B4-S2 — Structural Mutation Infrastructure Tests
===================================================
Tests for Bridge 4 Stufe 2: StructuralMutation, MutationHistory,
propose_structural_mutations(), apply/revert, admissibility.
Tests for Bridge 4 Stufe 4a: Identity Invariant.

Test classes:
  1. TestStructuralMutation       — dataclass, describe() (5)
  2. TestMutationType             — enum values (4)
  3. TestAdmissibility            — is_admissible gate (12)
  4. TestApplyMutation            — apply on Landscape (8)
  5. TestRevertMutation           — undo applied mutations (6)
  6. TestProposalLogic            — diagnostic → proposals (8)
  7. TestMutationRecord           — audit trail (4)
  8. TestMutationHistory          — bounded log + oscillation (10)
  9. TestHistorySerialization     — to_dict / from_dict (4)
  10. TestEndToEnd                — propose → apply → revert cycle (5)
  11. TestIdentityCheck           — dataclass + bool semantics (4)
  12. TestReachableStates         — BFS helper (5)
  13. TestCheckIdentityInvariant  — invariant verification (7)
  14. TestCheckIdentityAfterMutation — prospective check (5)
  15. TestIdentityInTuningCycle     — integration with real controller (4)
"""

import unittest
from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.reflection import StructuralDiagnostic
from e0_controller.structural_mutation import (
    MutationType,
    StructuralMutation,
    MutationRecord,
    MutationHistory,
    IdentityViolation,
    IdentityCheck,
    is_admissible,
    apply_structural_mutation,
    revert_structural_mutation,
    propose_structural_mutations,
    check_identity_invariant,
    check_identity_after_mutation,
    _reachable_states,
    _MAX_MUTATIONS_PER_CYCLE,
    structural_tuning_cycle,
)


# ── Helpers ──

def _build_diamond():
    """S→A, S→B, A→G, B→G."""
    L = Landscape()
    L.add_state("S")
    L.add_state("A")
    L.add_state("B")
    L.add_state("G")
    L.add_edge("S", "A", delta=3.0, resistance=1.0)
    L.add_edge("S", "B", delta=2.0, resistance=1.0)
    L.add_edge("A", "G", delta=4.0, resistance=0.5)
    L.add_edge("B", "G", delta=3.0, resistance=0.8)
    return L


def _build_chain():
    """A→B→C (linear)."""
    L = Landscape()
    L.add_state("A")
    L.add_state("B")
    L.add_state("C")
    L.add_edge("A", "B", delta=2.0, resistance=1.0)
    L.add_edge("B", "C", delta=2.0, resistance=1.0)
    return L


def _build_loop_domain():
    """S→A, A→S (2-cycle), S→G."""
    L = Landscape()
    L.add_state("S")
    L.add_state("A")
    L.add_state("G")
    L.add_edge("S", "A", delta=2.0, resistance=1.0)
    L.add_edge("A", "S", delta=2.0, resistance=1.0)
    L.add_edge("S", "G", delta=3.0, resistance=0.5)
    return L


def _build_leaf_domain():
    """S→A, S→B. B is a leaf (only one edge reaching it)."""
    L = Landscape()
    L.add_state("S")
    L.add_state("A")
    L.add_state("B")
    L.add_edge("S", "A", delta=2.0, resistance=1.0)
    L.add_edge("S", "B", delta=2.0, resistance=1.0)
    L.add_edge("A", "S", delta=1.0, resistance=1.0)
    return L


# ══════════════════════════════════════════════════════════════════
# Class 1: StructuralMutation dataclass
# ══════════════════════════════════════════════════════════════════

class TestStructuralMutation(unittest.TestCase):
    """B4-S2.1: StructuralMutation dataclass and describe()."""

    def test_edge_property(self):
        m = StructuralMutation(MutationType.ADJUST_RESISTANCE, "S", "A")
        self.assertEqual(m.edge, Edge("S", "A"))

    def test_describe_remove(self):
        m = StructuralMutation(MutationType.REMOVE_EDGE, "S", "A")
        self.assertIn("remove", m.describe())
        self.assertIn("S→A", m.describe())

    def test_describe_add(self):
        m = StructuralMutation(MutationType.ADD_EDGE, "X", "Y",
                               add_delta=2.0, add_resistance=1.0)
        desc = m.describe()
        self.assertIn("add", desc)
        self.assertIn("X→Y", desc)

    def test_describe_adjust_resistance(self):
        m = StructuralMutation(MutationType.ADJUST_RESISTANCE, "S", "A",
                               old_value=1.0, new_value=1.5)
        self.assertIn("R₀", m.describe())

    def test_describe_adjust_delta(self):
        m = StructuralMutation(MutationType.ADJUST_DELTA, "S", "A",
                               old_value=2.0, new_value=3.0)
        self.assertIn("Δ", m.describe())


# ══════════════════════════════════════════════════════════════════
# Class 2: MutationType enum
# ══════════════════════════════════════════════════════════════════

class TestMutationType(unittest.TestCase):
    """B4-S2.2: MutationType enum values."""

    def test_remove_edge_value(self):
        self.assertEqual(MutationType.REMOVE_EDGE.value, "remove_edge")

    def test_add_edge_value(self):
        self.assertEqual(MutationType.ADD_EDGE.value, "add_edge")

    def test_adjust_resistance_value(self):
        self.assertEqual(MutationType.ADJUST_RESISTANCE.value, "adjust_resistance")

    def test_adjust_delta_value(self):
        self.assertEqual(MutationType.ADJUST_DELTA.value, "adjust_delta")


# ══════════════════════════════════════════════════════════════════
# Class 3: Admissibility Gate
# ══════════════════════════════════════════════════════════════════

class TestAdmissibility(unittest.TestCase):
    """B4-S2.3: is_admissible() enforces E₀ constraints."""

    def test_remove_existing_admissible(self):
        L = _build_diamond()
        m = StructuralMutation(MutationType.REMOVE_EDGE, "S", "A")
        self.assertTrue(is_admissible(m, L))

    def test_remove_nonexistent_inadmissible(self):
        L = _build_diamond()
        m = StructuralMutation(MutationType.REMOVE_EDGE, "A", "B")
        self.assertFalse(is_admissible(m, L))

    def test_remove_would_orphan_inadmissible(self):
        """Removing the only edge to a leaf blocks the mutation."""
        L = _build_chain()  # A→B→C: removing B→C orphans C
        m = StructuralMutation(MutationType.REMOVE_EDGE, "B", "C")
        self.assertFalse(is_admissible(m, L))

    def test_add_new_edge_admissible(self):
        L = _build_diamond()
        m = StructuralMutation(MutationType.ADD_EDGE, "A", "B",
                               add_delta=1.0, add_resistance=0.5)
        self.assertTrue(is_admissible(m, L))

    def test_add_existing_inadmissible(self):
        L = _build_diamond()
        m = StructuralMutation(MutationType.ADD_EDGE, "S", "A",
                               add_delta=1.0, add_resistance=0.5)
        self.assertFalse(is_admissible(m, L))

    def test_add_negative_delta_inadmissible(self):
        L = _build_diamond()
        m = StructuralMutation(MutationType.ADD_EDGE, "A", "B",
                               add_delta=-1.0, add_resistance=0.5)
        self.assertFalse(is_admissible(m, L))

    def test_add_missing_delta_inadmissible(self):
        L = _build_diamond()
        m = StructuralMutation(MutationType.ADD_EDGE, "A", "B",
                               add_resistance=0.5)
        self.assertFalse(is_admissible(m, L))

    def test_adjust_r_existing_admissible(self):
        L = _build_diamond()
        m = StructuralMutation(MutationType.ADJUST_RESISTANCE, "S", "A",
                               new_value=2.0)
        self.assertTrue(is_admissible(m, L))

    def test_adjust_r_nonexistent_inadmissible(self):
        L = _build_diamond()
        m = StructuralMutation(MutationType.ADJUST_RESISTANCE, "X", "Y",
                               new_value=2.0)
        self.assertFalse(is_admissible(m, L))

    def test_adjust_r_negative_inadmissible(self):
        L = _build_diamond()
        m = StructuralMutation(MutationType.ADJUST_RESISTANCE, "S", "A",
                               new_value=-1.0)
        self.assertFalse(is_admissible(m, L))

    def test_adjust_delta_admissible(self):
        L = _build_diamond()
        m = StructuralMutation(MutationType.ADJUST_DELTA, "S", "A",
                               new_value=5.0)
        self.assertTrue(is_admissible(m, L))

    def test_adjust_delta_negative_inadmissible(self):
        L = _build_diamond()
        m = StructuralMutation(MutationType.ADJUST_DELTA, "S", "A",
                               new_value=-2.0)
        self.assertFalse(is_admissible(m, L))


# ══════════════════════════════════════════════════════════════════
# Class 4: Apply Mutation
# ══════════════════════════════════════════════════════════════════

class TestApplyMutation(unittest.TestCase):
    """B4-S2.4: apply_structural_mutation() on Landscape."""

    def test_apply_adjust_resistance(self):
        L = _build_diamond()
        m = StructuralMutation(MutationType.ADJUST_RESISTANCE, "S", "A",
                               new_value=2.0)
        result = apply_structural_mutation(m, L)
        self.assertAlmostEqual(L.base_resistance("S", "A"), 2.0)
        self.assertAlmostEqual(result.old_value, 1.0)

    def test_apply_adjust_delta(self):
        L = _build_diamond()
        m = StructuralMutation(MutationType.ADJUST_DELTA, "S", "A",
                               new_value=5.0)
        result = apply_structural_mutation(m, L)
        self.assertAlmostEqual(L.difference("S", "A"), 5.0)
        self.assertAlmostEqual(result.old_value, 3.0)

    def test_apply_remove_edge(self):
        L = _build_diamond()
        m = StructuralMutation(MutationType.REMOVE_EDGE, "S", "A")
        apply_structural_mutation(m, L)
        self.assertFalse(L.has_edge("S", "A"))

    def test_apply_add_edge(self):
        L = _build_diamond()
        m = StructuralMutation(MutationType.ADD_EDGE, "A", "B",
                               add_delta=1.5, add_resistance=0.5)
        apply_structural_mutation(m, L)
        self.assertTrue(L.has_edge("A", "B"))
        self.assertAlmostEqual(L.difference("A", "B"), 1.5)

    def test_apply_returns_mutation(self):
        L = _build_diamond()
        m = StructuralMutation(MutationType.ADJUST_RESISTANCE, "S", "A",
                               new_value=2.0)
        result = apply_structural_mutation(m, L)
        self.assertIs(result, m)

    def test_apply_inadmissible_raises(self):
        L = _build_diamond()
        m = StructuralMutation(MutationType.REMOVE_EDGE, "X", "Y")
        with self.assertRaises(ValueError):
            apply_structural_mutation(m, L)

    def test_apply_remove_stores_old_values(self):
        """Remove fills in old R₀ and Δ for potential re-add."""
        L = _build_diamond()
        m = StructuralMutation(MutationType.REMOVE_EDGE, "S", "A")
        apply_structural_mutation(m, L)
        self.assertAlmostEqual(m.old_value, 1.0)
        self.assertAlmostEqual(m.add_delta, 3.0)

    def test_apply_preserves_other_edges(self):
        L = _build_diamond()
        m = StructuralMutation(MutationType.ADJUST_RESISTANCE, "S", "A",
                               new_value=2.0)
        r_sb_before = L.base_resistance("S", "B")
        apply_structural_mutation(m, L)
        self.assertAlmostEqual(L.base_resistance("S", "B"), r_sb_before)


# ══════════════════════════════════════════════════════════════════
# Class 5: Revert Mutation
# ══════════════════════════════════════════════════════════════════

class TestRevertMutation(unittest.TestCase):
    """B4-S2.5: revert_structural_mutation() undoes changes."""

    def test_revert_adjust_resistance(self):
        L = _build_diamond()
        m = StructuralMutation(MutationType.ADJUST_RESISTANCE, "S", "A",
                               new_value=2.0)
        apply_structural_mutation(m, L)
        self.assertAlmostEqual(L.base_resistance("S", "A"), 2.0)
        revert_structural_mutation(m, L)
        self.assertAlmostEqual(L.base_resistance("S", "A"), 1.0)

    def test_revert_adjust_delta(self):
        L = _build_diamond()
        m = StructuralMutation(MutationType.ADJUST_DELTA, "S", "A",
                               new_value=5.0)
        apply_structural_mutation(m, L)
        revert_structural_mutation(m, L)
        self.assertAlmostEqual(L.difference("S", "A"), 3.0)

    def test_revert_remove_readds(self):
        L = _build_diamond()
        m = StructuralMutation(MutationType.REMOVE_EDGE, "S", "A")
        apply_structural_mutation(m, L)
        self.assertFalse(L.has_edge("S", "A"))
        revert_structural_mutation(m, L)
        self.assertTrue(L.has_edge("S", "A"))
        self.assertAlmostEqual(L.difference("S", "A"), 3.0)
        self.assertAlmostEqual(L.base_resistance("S", "A"), 1.0)

    def test_revert_add_removes(self):
        L = _build_diamond()
        m = StructuralMutation(MutationType.ADD_EDGE, "A", "B",
                               add_delta=1.0, add_resistance=0.5)
        apply_structural_mutation(m, L)
        self.assertTrue(L.has_edge("A", "B"))
        revert_structural_mutation(m, L)
        self.assertFalse(L.has_edge("A", "B"))

    def test_revert_restores_field(self):
        """Field value is restored after apply+revert."""
        L = _build_diamond()
        v_before = L.transition_field("S", "A")
        m = StructuralMutation(MutationType.ADJUST_RESISTANCE, "S", "A",
                               new_value=3.0)
        apply_structural_mutation(m, L)
        revert_structural_mutation(m, L)
        v_after = L.transition_field("S", "A")
        self.assertAlmostEqual(v_before, v_after, places=10)

    def test_double_revert_is_idempotent_for_remove(self):
        """Reverting a remove twice re-adds again (add_edge overwrites)."""
        L = _build_diamond()
        m = StructuralMutation(MutationType.REMOVE_EDGE, "S", "A")
        apply_structural_mutation(m, L)
        revert_structural_mutation(m, L)
        self.assertTrue(L.has_edge("S", "A"))
        # Second revert just overwrites — no error
        revert_structural_mutation(m, L)
        self.assertTrue(L.has_edge("S", "A"))


# ══════════════════════════════════════════════════════════════════
# Class 6: Proposal Logic
# ══════════════════════════════════════════════════════════════════

class TestProposalLogic(unittest.TestCase):
    """B4-S2.6: propose_structural_mutations() from diagnostics."""

    def test_dead_state_produces_delta_boost(self):
        L = _build_diamond()
        diag = StructuralDiagnostic(dead_states=["B"])
        proposals = propose_structural_mutations(diag, L)
        # Should propose boosting Δ on S→B (edge leading to B)
        deltas = [p for p in proposals
                  if p.mutation_type == MutationType.ADJUST_DELTA
                  and p.target == "B"]
        self.assertGreater(len(deltas), 0)
        self.assertGreater(deltas[0].new_value, deltas[0].old_value)

    def test_loop_state_produces_r_increase(self):
        L = _build_loop_domain()
        diag = StructuralDiagnostic(loop_states=["S", "A"])
        proposals = propose_structural_mutations(diag, L)
        r_adj = [p for p in proposals
                 if p.mutation_type == MutationType.ADJUST_RESISTANCE]
        self.assertGreater(len(r_adj), 0)
        self.assertGreater(r_adj[0].new_value, r_adj[0].old_value)

    def test_empty_diagnostic_no_proposals(self):
        L = _build_diamond()
        diag = StructuralDiagnostic()
        proposals = propose_structural_mutations(diag, L)
        self.assertEqual(len(proposals), 0)

    def test_proposals_are_admissible(self):
        L = _build_diamond()
        diag = StructuralDiagnostic(dead_states=["A", "B"])
        proposals = propose_structural_mutations(diag, L)
        for p in proposals:
            self.assertTrue(is_admissible(p, L), f"Inadmissible: {p.describe()}")

    def test_bounded_to_max_per_cycle(self):
        """At most _MAX_MUTATIONS_PER_CYCLE proposals per call."""
        L = Landscape()
        # Many states, many dead
        for s in "SABCDEFGH":
            L.add_state(s)
        L.add_edge("S", "A", delta=1.0, resistance=1.0)
        L.add_edge("S", "B", delta=1.0, resistance=1.0)
        L.add_edge("S", "C", delta=1.0, resistance=1.0)
        L.add_edge("S", "D", delta=1.0, resistance=1.0)
        L.add_edge("S", "E", delta=1.0, resistance=1.0)
        L.add_edge("A", "S", delta=1.0, resistance=1.0)
        L.add_edge("B", "S", delta=1.0, resistance=1.0)
        diag = StructuralDiagnostic(dead_states=["A", "B", "C", "D", "E"])
        proposals = propose_structural_mutations(diag, L)
        self.assertLessEqual(len(proposals), _MAX_MUTATIONS_PER_CYCLE)

    def test_proposals_have_motivation(self):
        L = _build_diamond()
        diag = StructuralDiagnostic(dead_states=["B"])
        proposals = propose_structural_mutations(diag, L)
        for p in proposals:
            self.assertTrue(len(p.motivation) > 0)

    def test_oscillation_filter(self):
        """History with oscillating R₀ on S→A blocks new proposal."""
        L = _build_loop_domain()
        history = MutationHistory()
        # Simulate two alternating R₀ changes: up, down
        m1 = StructuralMutation(MutationType.ADJUST_RESISTANCE, "S", "A",
                                old_value=1.0, new_value=1.5)
        m2 = StructuralMutation(MutationType.ADJUST_RESISTANCE, "S", "A",
                                old_value=1.5, new_value=1.0)
        history.record(MutationRecord(mutation=m1, accepted=True))
        history.record(MutationRecord(mutation=m2, accepted=True))

        diag = StructuralDiagnostic(loop_states=["S", "A"])
        proposals = propose_structural_mutations(diag, L, mutation_history=history)
        # S→A R₀ adjustment should be blocked
        sa_r = [p for p in proposals
                if p.source == "S" and p.target == "A"
                and p.mutation_type == MutationType.ADJUST_RESISTANCE]
        self.assertEqual(len(sa_r), 0)

    def test_loop_dedup(self):
        """2-cycle S↔A: only one proposal for the loop pair, not two."""
        L = _build_loop_domain()
        diag = StructuralDiagnostic(loop_states=["S", "A"])
        proposals = propose_structural_mutations(diag, L)
        r_proposals = [p for p in proposals
                       if p.mutation_type == MutationType.ADJUST_RESISTANCE]
        # Should have exactly 1 (deduplicated pair)
        self.assertEqual(len(r_proposals), 1)


# ══════════════════════════════════════════════════════════════════
# Class 7: MutationRecord
# ══════════════════════════════════════════════════════════════════

class TestMutationRecord(unittest.TestCase):
    """B4-S2.7: MutationRecord audit trail."""

    def test_delta_quality_computed(self):
        m = StructuralMutation(MutationType.ADJUST_RESISTANCE, "S", "A")
        r = MutationRecord(mutation=m, quality_before=0.5, quality_after=0.7)
        self.assertAlmostEqual(r.delta_quality, 0.2)

    def test_delta_quality_none_if_no_after(self):
        m = StructuralMutation(MutationType.ADJUST_RESISTANCE, "S", "A")
        r = MutationRecord(mutation=m, quality_before=0.5)
        self.assertIsNone(r.delta_quality)

    def test_default_not_accepted(self):
        m = StructuralMutation(MutationType.REMOVE_EDGE, "S", "A")
        r = MutationRecord(mutation=m)
        self.assertFalse(r.accepted)

    def test_negative_delta(self):
        m = StructuralMutation(MutationType.ADJUST_RESISTANCE, "S", "A")
        r = MutationRecord(mutation=m, quality_before=0.7, quality_after=0.3)
        self.assertLess(r.delta_quality, 0)


# ══════════════════════════════════════════════════════════════════
# Class 8: MutationHistory
# ══════════════════════════════════════════════════════════════════

class TestMutationHistory(unittest.TestCase):
    """B4-S2.8: MutationHistory bounded log + oscillation detection."""

    def test_record_appends(self):
        h = MutationHistory()
        m = StructuralMutation(MutationType.ADJUST_RESISTANCE, "S", "A")
        h.record(MutationRecord(mutation=m))
        self.assertEqual(len(h.records), 1)

    def test_bounded_capacity(self):
        h = MutationHistory(max_records=3)
        for i in range(5):
            m = StructuralMutation(MutationType.ADJUST_RESISTANCE, "S", "A",
                                   old_value=float(i), new_value=float(i + 1))
            h.record(MutationRecord(mutation=m))
        self.assertEqual(len(h.records), 3)

    def test_oscillation_detected(self):
        h = MutationHistory()
        m1 = StructuralMutation(MutationType.ADJUST_RESISTANCE, "S", "A",
                                old_value=1.0, new_value=1.5)
        m2 = StructuralMutation(MutationType.ADJUST_RESISTANCE, "S", "A",
                                old_value=1.5, new_value=1.0)
        h.record(MutationRecord(mutation=m1, accepted=True))
        h.record(MutationRecord(mutation=m2, accepted=True))

        new_proposal = StructuralMutation(MutationType.ADJUST_RESISTANCE, "S", "A",
                                          new_value=1.5)
        self.assertTrue(h.would_oscillate(new_proposal))

    def test_no_oscillation_with_fewer_than_two(self):
        h = MutationHistory()
        m1 = StructuralMutation(MutationType.ADJUST_RESISTANCE, "S", "A",
                                old_value=1.0, new_value=1.5)
        h.record(MutationRecord(mutation=m1, accepted=True))
        new_proposal = StructuralMutation(MutationType.ADJUST_RESISTANCE, "S", "A",
                                          new_value=2.0)
        self.assertFalse(h.would_oscillate(new_proposal))

    def test_oscillation_add_remove(self):
        """Add then remove same edge = oscillation."""
        h = MutationHistory()
        m1 = StructuralMutation(MutationType.ADD_EDGE, "X", "Y")
        h.record(MutationRecord(mutation=m1, accepted=True))
        remove = StructuralMutation(MutationType.REMOVE_EDGE, "X", "Y")
        self.assertTrue(h.would_oscillate(remove))

    def test_oscillation_remove_add(self):
        """Remove then add same edge = oscillation."""
        h = MutationHistory()
        m1 = StructuralMutation(MutationType.REMOVE_EDGE, "X", "Y")
        h.record(MutationRecord(mutation=m1, accepted=True))
        add = StructuralMutation(MutationType.ADD_EDGE, "X", "Y")
        self.assertTrue(h.would_oscillate(add))

    def test_accepted_count(self):
        h = MutationHistory()
        m = StructuralMutation(MutationType.ADJUST_RESISTANCE, "S", "A")
        h.record(MutationRecord(mutation=m, accepted=True))
        h.record(MutationRecord(mutation=m, accepted=False))
        h.record(MutationRecord(mutation=m, accepted=True))
        self.assertEqual(h.accepted_count(), 2)

    def test_reverted_count(self):
        h = MutationHistory()
        m = StructuralMutation(MutationType.ADJUST_RESISTANCE, "S", "A")
        h.record(MutationRecord(mutation=m, reverted=True))
        h.record(MutationRecord(mutation=m, reverted=False))
        self.assertEqual(h.reverted_count(), 1)

    def test_edge_mutation_count(self):
        h = MutationHistory()
        m1 = StructuralMutation(MutationType.ADJUST_RESISTANCE, "S", "A")
        m2 = StructuralMutation(MutationType.ADJUST_DELTA, "S", "A")
        m3 = StructuralMutation(MutationType.ADJUST_RESISTANCE, "S", "B")
        h.record(MutationRecord(mutation=m1))
        h.record(MutationRecord(mutation=m2))
        h.record(MutationRecord(mutation=m3))
        self.assertEqual(h.edge_mutation_count("S", "A"), 2)
        self.assertEqual(h.edge_mutation_count("S", "B"), 1)

    def test_different_edges_no_oscillation(self):
        """Oscillation detection is per-edge: S→A history doesn't affect S→B."""
        h = MutationHistory()
        m1 = StructuralMutation(MutationType.ADJUST_RESISTANCE, "S", "A",
                                old_value=1.0, new_value=1.5)
        m2 = StructuralMutation(MutationType.ADJUST_RESISTANCE, "S", "A",
                                old_value=1.5, new_value=1.0)
        h.record(MutationRecord(mutation=m1, accepted=True))
        h.record(MutationRecord(mutation=m2, accepted=True))

        # S→B should not be affected
        sb = StructuralMutation(MutationType.ADJUST_RESISTANCE, "S", "B",
                                new_value=2.0)
        self.assertFalse(h.would_oscillate(sb))


# ══════════════════════════════════════════════════════════════════
# Class 9: History Serialization
# ══════════════════════════════════════════════════════════════════

class TestHistorySerialization(unittest.TestCase):
    """B4-S2.9: MutationHistory to_dict / from_dict roundtrip."""

    def test_empty_roundtrip(self):
        h = MutationHistory()
        d = h.to_dict()
        h2 = MutationHistory.from_dict(d)
        self.assertEqual(len(h2.records), 0)

    def test_roundtrip_with_records(self):
        h = MutationHistory()
        m = StructuralMutation(MutationType.ADJUST_RESISTANCE, "S", "A",
                               old_value=1.0, new_value=1.5,
                               motivation="test")
        h.record(MutationRecord(mutation=m, quality_before=0.5,
                                quality_after=0.7, accepted=True))
        d = h.to_dict()
        h2 = MutationHistory.from_dict(d)
        self.assertEqual(len(h2.records), 1)
        self.assertEqual(h2.records[0].mutation.source, "S")
        self.assertEqual(h2.records[0].mutation.mutation_type,
                         MutationType.ADJUST_RESISTANCE)
        self.assertTrue(h2.records[0].accepted)

    def test_max_records_preserved(self):
        h = MutationHistory(max_records=42)
        d = h.to_dict()
        h2 = MutationHistory.from_dict(d)
        self.assertEqual(h2.max_records, 42)

    def test_roundtrip_preserves_add_edge_fields(self):
        h = MutationHistory()
        m = StructuralMutation(MutationType.ADD_EDGE, "X", "Y",
                               add_delta=2.5, add_resistance=0.8)
        h.record(MutationRecord(mutation=m, accepted=True))
        d = h.to_dict()
        h2 = MutationHistory.from_dict(d)
        rec = h2.records[0].mutation
        self.assertAlmostEqual(rec.add_delta, 2.5)
        self.assertAlmostEqual(rec.add_resistance, 0.8)


# ══════════════════════════════════════════════════════════════════
# Class 10: End-to-End Cycle
# ══════════════════════════════════════════════════════════════════

class TestEndToEnd(unittest.TestCase):
    """B4-S2.10: propose → apply → revert full cycle."""

    def test_propose_apply_accept(self):
        """Dead state → proposal → apply → Δ increased."""
        L = _build_diamond()
        old_delta = L.difference("S", "B")
        diag = StructuralDiagnostic(dead_states=["B"])
        proposals = propose_structural_mutations(diag, L)
        self.assertGreater(len(proposals), 0)

        for p in proposals:
            apply_structural_mutation(p, L)

        # B should now have higher Δ on incoming edge
        new_delta = L.difference("S", "B")
        self.assertGreater(new_delta, old_delta)

    def test_propose_apply_revert(self):
        """Full cycle: apply then revert restores original."""
        L = _build_diamond()
        original_r = L.base_resistance("S", "A")
        original_delta = L.difference("S", "A")

        diag = StructuralDiagnostic(dead_states=["A"])
        proposals = propose_structural_mutations(diag, L)

        for p in proposals:
            apply_structural_mutation(p, L)

        # Something changed
        changed = (L.base_resistance("S", "A") != original_r or
                   L.difference("S", "A") != original_delta)
        self.assertTrue(changed)

        # Revert all
        for p in reversed(proposals):
            revert_structural_mutation(p, L)

        self.assertAlmostEqual(L.base_resistance("S", "A"), original_r)
        self.assertAlmostEqual(L.difference("S", "A"), original_delta)

    def test_loop_fix_cycle(self):
        """Loop diagnostic → R₀ increase → loop resistance higher."""
        L = _build_loop_domain()
        old_r_sa = L.base_resistance("S", "A")

        diag = StructuralDiagnostic(loop_states=["S", "A"])
        proposals = propose_structural_mutations(diag, L)

        for p in proposals:
            apply_structural_mutation(p, L)

        # At least one edge in the loop should have higher R₀
        r_sa = L.base_resistance("S", "A")
        r_as = L.base_resistance("A", "S")
        self.assertTrue(r_sa > old_r_sa or r_as > 1.0)

    def test_history_tracks_cycle(self):
        """Mutations are recordable in MutationHistory."""
        L = _build_diamond()
        history = MutationHistory()
        diag = StructuralDiagnostic(dead_states=["B"])
        proposals = propose_structural_mutations(diag, L)

        for p in proposals:
            apply_structural_mutation(p, L)
            rec = MutationRecord(mutation=p, quality_before=0.5,
                                 quality_after=0.6, accepted=True)
            history.record(rec)

        self.assertEqual(history.accepted_count(), len(proposals))

    def test_multiple_cycles_with_oscillation_protection(self):
        """Two opposing cycles: second cycle's proposal is blocked."""
        L = _build_loop_domain()
        history = MutationHistory()

        # Cycle 1: loop → R₀ up
        diag1 = StructuralDiagnostic(loop_states=["S", "A"])
        p1 = propose_structural_mutations(diag1, L, mutation_history=history)
        for p in p1:
            apply_structural_mutation(p, L)
            history.record(MutationRecord(mutation=p, accepted=True))

        # Manually revert to simulate "it got worse"
        for p in reversed(p1):
            revert_structural_mutation(p, L)
            history.record(MutationRecord(
                mutation=StructuralMutation(
                    mutation_type=p.mutation_type,
                    source=p.source, target=p.target,
                    old_value=p.new_value, new_value=p.old_value,
                ),
                accepted=True))

        # Cycle 2: same diagnostic — should be blocked by oscillation
        diag2 = StructuralDiagnostic(loop_states=["S", "A"])
        p2 = propose_structural_mutations(diag2, L, mutation_history=history)
        # The same edge adjustment should be blocked
        same_edge = [p for p in p2
                     if p.source == p1[0].source and p.target == p1[0].target
                     and p.mutation_type == p1[0].mutation_type]
        self.assertEqual(len(same_edge), 0)


# ══════════════════════════════════════════════════════════════════
# Class 11: IdentityCheck dataclass
# ══════════════════════════════════════════════════════════════════

class TestIdentityCheck(unittest.TestCase):
    """B4-S4a.11: IdentityCheck dataclass + bool semantics."""

    def test_ok_is_truthy(self):
        ic = IdentityCheck(ok=True)
        self.assertTrue(ic)
        self.assertTrue(ic.ok)

    def test_violation_is_falsy(self):
        ic = IdentityCheck(
            ok=False,
            violations=[IdentityViolation.GOAL_UNREACHABLE],
            details=["goal not reachable"],
        )
        self.assertFalse(ic)
        self.assertFalse(ic.ok)

    def test_empty_violations_when_ok(self):
        ic = IdentityCheck(ok=True)
        self.assertEqual(len(ic.violations), 0)
        self.assertEqual(len(ic.details), 0)

    def test_multiple_violations(self):
        ic = IdentityCheck(
            ok=False,
            violations=[
                IdentityViolation.GOAL_UNREACHABLE,
                IdentityViolation.DEAD_END_CREATED,
            ],
            details=["goal gone", "dead end at X"],
        )
        self.assertEqual(len(ic.violations), 2)
        self.assertEqual(len(ic.details), 2)


# ══════════════════════════════════════════════════════════════════
# Class 12: _reachable_states BFS helper
# ══════════════════════════════════════════════════════════════════

class TestReachableStates(unittest.TestCase):
    """B4-S4a.12: _reachable_states() BFS correctness."""

    def test_diamond_all_reachable(self):
        L = _build_diamond()  # S→A, S→B, A→G, B→G
        r = _reachable_states(L, "S")
        self.assertEqual(r, {"S", "A", "B", "G"})

    def test_chain_from_start(self):
        L = _build_chain()  # A→B→C
        r = _reachable_states(L, "A")
        self.assertEqual(r, {"A", "B", "C"})

    def test_chain_from_middle(self):
        L = _build_chain()
        r = _reachable_states(L, "B")
        self.assertEqual(r, {"B", "C"})  # A not reachable from B

    def test_chain_from_end(self):
        L = _build_chain()
        r = _reachable_states(L, "C")
        self.assertEqual(r, {"C"})  # terminal node

    def test_loop_domain(self):
        L = _build_loop_domain()  # S→A, A→S, S→G
        r = _reachable_states(L, "S")
        self.assertEqual(r, {"S", "A", "G"})


# ══════════════════════════════════════════════════════════════════
# Class 13: check_identity_invariant
# ══════════════════════════════════════════════════════════════════

class TestCheckIdentityInvariant(unittest.TestCase):
    """B4-S4a.13: check_identity_invariant() verifies E₀ identity."""

    def test_diamond_ok(self):
        """Diamond graph: goal reachable, no dead ends."""
        L = _build_diamond()
        ic = check_identity_invariant(L, "S", goal="G")
        self.assertTrue(ic.ok)
        self.assertEqual(len(ic.violations), 0)

    def test_goal_unreachable_after_edge_removal(self):
        """Remove both paths to G → goal unreachable."""
        L = _build_diamond()
        L.remove_edge("A", "G")
        L.remove_edge("B", "G")
        ic = check_identity_invariant(L, "S", goal="G")
        self.assertFalse(ic.ok)
        self.assertIn(IdentityViolation.GOAL_UNREACHABLE, ic.violations)

    def test_dead_end_detected(self):
        """Chain A→B→C: C has no out-edges and is not goal → dead end."""
        L = _build_chain()
        ic = check_identity_invariant(L, "A", goal=None)
        self.assertFalse(ic.ok)
        self.assertIn(IdentityViolation.DEAD_END_CREATED, ic.violations)
        self.assertTrue(any("C" in d for d in ic.details))

    def test_dead_end_ok_if_goal(self):
        """Chain A→B→C: C is terminal but it's the goal → allowed."""
        L = _build_chain()
        ic = check_identity_invariant(L, "A", goal="C")
        self.assertTrue(ic.ok)

    def test_no_goal_given_ok(self):
        """Loop domain S→A, A→S, S→G: no dead ends (G excluded from dead-end
        check only when it IS the goal). Without goal, G is a dead end."""
        L = _build_loop_domain()
        ic = check_identity_invariant(L, "S", goal=None)
        # G has no outgoing edges and goal is None → dead end
        self.assertFalse(ic.ok)
        self.assertIn(IdentityViolation.DEAD_END_CREATED, ic.violations)

    def test_loop_domain_with_goal(self):
        """Loop domain with G as goal: G terminal is allowed."""
        L = _build_loop_domain()
        ic = check_identity_invariant(L, "S", goal="G")
        self.assertTrue(ic.ok)

    def test_both_violations_at_once(self):
        """Isolated goal + dead end: multiple violations."""
        L = Landscape()
        L.add_state("S")
        L.add_state("A")
        L.add_state("G")
        L.add_edge("S", "A", delta=1.0, resistance=1.0)
        # G unreachable (no edge to G)
        # A is a dead end (no outgoing edges)
        ic = check_identity_invariant(L, "S", goal="G")
        self.assertFalse(ic.ok)
        self.assertIn(IdentityViolation.GOAL_UNREACHABLE, ic.violations)
        self.assertIn(IdentityViolation.DEAD_END_CREATED, ic.violations)


# ══════════════════════════════════════════════════════════════════
# Class 14: check_identity_after_mutation (prospective)
# ══════════════════════════════════════════════════════════════════

class TestCheckIdentityAfterMutation(unittest.TestCase):
    """B4-S4a.14: check_identity_after_mutation() speculative check."""

    def test_safe_mutation_passes(self):
        """Adjusting R₀ preserves identity."""
        L = _build_diamond()
        m = StructuralMutation(MutationType.ADJUST_RESISTANCE, "S", "A",
                               new_value=2.0)
        ic = check_identity_after_mutation(m, L, "S", goal="G")
        self.assertTrue(ic.ok)
        # Landscape restored
        self.assertAlmostEqual(L.base_resistance("S", "A"), 1.0)

    def test_landscape_restored_after_check(self):
        """Landscape must be identical before and after prospective check."""
        L = _build_diamond()
        delta_before = L.difference("S", "A")
        r_before = L.base_resistance("S", "A")

        m = StructuralMutation(MutationType.ADJUST_DELTA, "S", "A",
                               new_value=10.0)
        check_identity_after_mutation(m, L, "S", goal="G")

        self.assertAlmostEqual(L.difference("S", "A"), delta_before)
        self.assertAlmostEqual(L.base_resistance("S", "A"), r_before)

    def test_inadmissible_mutation_returns_not_ok(self):
        """Non-admissible mutation → IdentityCheck with ok=False."""
        L = _build_diamond()
        m = StructuralMutation(MutationType.REMOVE_EDGE, "X", "Y")
        ic = check_identity_after_mutation(m, L, "S", goal="G")
        self.assertFalse(ic.ok)

    def test_dangerous_remove_detected(self):
        """Removing the only *reachable* path to G should fail identity check."""
        # S→A→G, A→S (cycle), B→G (keeps G non-orphaned but B unreachable from S)
        L = Landscape()
        L.add_state("S")
        L.add_state("A")
        L.add_state("B")
        L.add_state("G")
        L.add_edge("S", "A", delta=2.0, resistance=1.0)
        L.add_edge("A", "G", delta=2.0, resistance=1.0)
        L.add_edge("A", "S", delta=1.0, resistance=1.0)
        L.add_edge("B", "G", delta=1.0, resistance=1.0)  # non-orphan edge

        m = StructuralMutation(MutationType.REMOVE_EDGE, "A", "G")
        ic = check_identity_after_mutation(m, L, "S", goal="G")
        self.assertFalse(ic.ok)
        self.assertIn(IdentityViolation.GOAL_UNREACHABLE, ic.violations)
        # Landscape restored
        self.assertTrue(L.has_edge("A", "G"))

    def test_remove_creating_dead_end_detected(self):
        """Removing edge that creates a dead non-goal state."""
        # S→A, S→B, A→B. Remove A→B → A becomes dead end (no goal given).
        L = Landscape()
        L.add_state("S")
        L.add_state("A")
        L.add_state("B")
        L.add_edge("S", "A", delta=2.0, resistance=1.0)
        L.add_edge("S", "B", delta=2.0, resistance=1.0)
        L.add_edge("A", "B", delta=2.0, resistance=1.0)

        m = StructuralMutation(MutationType.REMOVE_EDGE, "A", "B")
        ic = check_identity_after_mutation(m, L, "S", goal=None)
        self.assertFalse(ic.ok)
        self.assertIn(IdentityViolation.DEAD_END_CREATED, ic.violations)
        # Landscape restored
        self.assertTrue(L.has_edge("A", "B"))


# ══════════════════════════════════════════════════════════════════
# Class 15: Integration — Identity in structural_tuning_cycle
# ══════════════════════════════════════════════════════════════════

class TestIdentityInTuningCycle(unittest.TestCase):
    """B4-S4a.15: Identity check in live structural_tuning_cycle runs."""

    @staticmethod
    def _exec():
        return lambda s, t: Outcome.SUCCESS

    def test_clean_cycle_identity_check_present(self):
        """structural_tuning_cycle returns identity_check when mutations applied."""
        from e0_controller.controller import E0Controller
        L = _build_diamond()
        ctrl = E0Controller(L, self._exec(), s_max=10.0)
        result = structural_tuning_cycle(ctrl, "S", goal="G")
        if result.applied_mutations:
            self.assertIsNotNone(result.identity_check)
            self.assertTrue(result.identity_check.ok)

    def test_identity_check_on_loop_fix(self):
        """Loop-fix mutations preserve identity (goal stays reachable)."""
        from e0_controller.controller import E0Controller
        L = _build_loop_domain()  # S→A, A→S, S→G
        ctrl = E0Controller(L, self._exec(), s_max=10.0)
        history = MutationHistory()
        result = structural_tuning_cycle(
            ctrl, "S", goal="G", mutation_history=history,
        )
        if result.applied_mutations and result.accepted:
            self.assertIsNotNone(result.identity_check)
            self.assertTrue(result.identity_check.ok)

    def test_identity_check_none_when_no_proposals(self):
        """When no proposals generated, identity_check is None."""
        from e0_controller.controller import E0Controller
        L = _build_diamond()
        ctrl = E0Controller(L, self._exec(), s_max=10.0)
        result = structural_tuning_cycle(ctrl, "S", goal="G")
        if not result.proposals:
            self.assertIsNone(result.identity_check)

    def test_identity_check_field_exists(self):
        """StructuralTuningCycleResult always has identity_check field."""
        from e0_controller.controller import E0Controller
        L = _build_diamond()
        ctrl = E0Controller(L, self._exec(), s_max=10.0)
        result = structural_tuning_cycle(ctrl, "S", goal="G")
        self.assertTrue(hasattr(result, "identity_check"))


if __name__ == "__main__":
    unittest.main()
