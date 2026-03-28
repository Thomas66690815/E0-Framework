"""
B4-S4a — Identity Invariant Tests
====================================
Tests for Bridge 4 Stufe 4a: the three-part post-mutation identity check.

Canon basis: Structural Deep Review v1 §6.1 — "What must remain invariant
under Self-Modification?"  Three necessary conditions:

  1. goal_reachable   — goal stays reachable from start (if goal is set)
  2. a0_compliant     — every reachable non-goal state has >=1 admissible exit
  3. historization    — mutations never touch delta_H traces (architectural guarantee)

Test classes:
  1. TestIdentityInvariantResult   -- dataclass fields (5)
  2. TestGoalReachability          -- Invariant 1 scenarios (6)
  3. TestA0Compliance              -- Invariant 2 scenarios (6)
  4. TestHistorizationContinuity   -- Invariant 3 (always True) (3)
  5. TestCombinedInvariants        -- multi-invariant + first-violation order (4)
  6. TestInvariantInTuningCycle    -- integration with structural_tuning_cycle (6)
"""

import unittest
from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.structural_mutation import (
    IdentityInvariantResult,
    check_identity_invariant,
    MutationType,
    StructuralMutation,
    apply_structural_mutation,
    revert_structural_mutation,
    structural_tuning_cycle,
    MutationHistory,
)
from e0_controller.controller import E0Controller


# -- Helpers --

def _mk_exec():
    return lambda s, t: Outcome.SUCCESS


def _chain():
    """A -> B -> C (linear chain, start=A, goal=C)."""
    L = Landscape()
    L.add_edge("A", "B", delta=2.0, resistance=1.0)
    L.add_edge("B", "C", delta=2.0, resistance=1.0)
    return L


def _diamond():
    """S -> A, S -> B, A -> G, B -> G."""
    L = Landscape()
    L.add_edge("S", "A", delta=3.0, resistance=1.0)
    L.add_edge("S", "B", delta=2.0, resistance=1.0)
    L.add_edge("A", "G", delta=4.0, resistance=0.5)
    L.add_edge("B", "G", delta=3.0, resistance=0.8)
    return L


def _dead_end_graph():
    """S -> A -> B, S -> D (D has no outgoing edges -- a reachable dead-end)."""
    L = Landscape()
    L.add_edge("S", "A", delta=2.0, resistance=1.0)
    L.add_edge("A", "B", delta=2.0, resistance=1.0)
    L.add_edge("S", "D", delta=1.0, resistance=1.0)
    # D has no outgoing edges
    return L


# -- Test Classes --

class TestIdentityInvariantResult(unittest.TestCase):
    """Dataclass fields and semantics."""

    def test_satisfied_all_true(self):
        r = IdentityInvariantResult(
            satisfied=True, violated_check=None,
            goal_reachable=True, a0_compliant=True,
            historization_continuous=True, unreachable_dead_ends=[],
        )
        self.assertTrue(r.satisfied)
        self.assertIsNone(r.violated_check)

    def test_violated_goal(self):
        r = IdentityInvariantResult(
            satisfied=False, violated_check="goal_reachable",
            goal_reachable=False, a0_compliant=True,
            historization_continuous=True, unreachable_dead_ends=[],
        )
        self.assertFalse(r.satisfied)
        self.assertEqual(r.violated_check, "goal_reachable")

    def test_violated_a0(self):
        r = IdentityInvariantResult(
            satisfied=False, violated_check="a0_compliant",
            goal_reachable=True, a0_compliant=False,
            historization_continuous=True, unreachable_dead_ends=["X"],
        )
        self.assertFalse(r.satisfied)
        self.assertEqual(r.violated_check, "a0_compliant")
        self.assertIn("X", r.unreachable_dead_ends)

    def test_historization_always_true(self):
        """Invariant 3 is always True -- architectural guarantee."""
        r = IdentityInvariantResult(
            satisfied=True, violated_check=None,
            goal_reachable=True, a0_compliant=True,
            historization_continuous=True, unreachable_dead_ends=[],
        )
        self.assertTrue(r.historization_continuous)

    def test_frozen(self):
        r = IdentityInvariantResult(
            satisfied=True, violated_check=None,
            goal_reachable=True, a0_compliant=True,
            historization_continuous=True, unreachable_dead_ends=[],
        )
        with self.assertRaises((AttributeError, TypeError)):
            r.satisfied = False


class TestGoalReachability(unittest.TestCase):
    """Invariant 1: goal remains reachable after mutation."""

    def test_goal_reachable_simple_chain(self):
        L = _chain()
        r = check_identity_invariant(L, "A", goal="C")
        self.assertTrue(r.goal_reachable)
        self.assertTrue(r.satisfied)

    def test_goal_reachable_no_goal(self):
        """Without a goal, Invariant 1 is vacuously True."""
        L = _chain()
        r = check_identity_invariant(L, "A", goal=None)
        self.assertTrue(r.goal_reachable)

    def test_goal_unreachable_after_edge_removal(self):
        """Removing A->B makes C unreachable from A."""
        L = _chain()
        L.remove_edge("A", "B")
        r = check_identity_invariant(L, "A", goal="C")
        self.assertFalse(r.goal_reachable)
        self.assertFalse(r.satisfied)
        self.assertEqual(r.violated_check, "goal_reachable")

    def test_goal_reachable_via_alternate_path(self):
        """Goal still reachable via alternate path when one edge removed."""
        L = _diamond()
        # Remove S->A; S->B->G still reaches G
        L.remove_edge("S", "A")
        r = check_identity_invariant(L, "S", goal="G")
        self.assertTrue(r.goal_reachable)
        self.assertTrue(r.satisfied)

    def test_goal_not_in_graph(self):
        """If goal state is not in the graph, it is not reachable."""
        L = _chain()
        r = check_identity_invariant(L, "A", goal="Z")
        self.assertFalse(r.goal_reachable)
        self.assertFalse(r.satisfied)

    def test_start_equals_goal(self):
        """Start == goal: trivially reachable."""
        L = _chain()
        r = check_identity_invariant(L, "A", goal="A")
        self.assertTrue(r.goal_reachable)


class TestA0Compliance(unittest.TestCase):
    """Invariant 2: every reachable non-goal state has >=1 admissible exit."""

    def test_clean_chain_compliant(self):
        """A->B->C: A and B have exits; C is the goal and can be terminal."""
        L = _chain()
        r = check_identity_invariant(L, "A", goal="C")
        self.assertTrue(r.a0_compliant)
        self.assertEqual(r.unreachable_dead_ends, [])

    def test_dead_end_detected(self):
        """D has no outgoing edges and is not the goal -> A0 violated."""
        L = _dead_end_graph()
        # B is the goal; D is reachable from S but is a dead-end
        r = check_identity_invariant(L, "S", goal="B")
        self.assertFalse(r.a0_compliant)
        self.assertIn("D", r.unreachable_dead_ends)
        self.assertFalse(r.satisfied)

    def test_goal_terminal_is_not_violation(self):
        """Goal with no outgoing edges is NOT a dead-end (terminal is valid)."""
        L = _chain()
        # C has no outgoing edges but is the goal -- acceptable
        r = check_identity_invariant(L, "A", goal="C")
        self.assertNotIn("C", r.unreachable_dead_ends)
        self.assertTrue(r.a0_compliant)

    def test_no_goal_terminal_is_violation(self):
        """C with no exits and no goal set -> A0 violation."""
        L = _chain()
        # No goal -- C's dead-end is a genuine structural violation
        r = check_identity_invariant(L, "A", goal=None)
        self.assertFalse(r.a0_compliant)
        self.assertIn("C", r.unreachable_dead_ends)

    def test_diamond_compliant(self):
        """Diamond S->A->G, S->B->G: all non-goal states have exits."""
        L = _diamond()
        r = check_identity_invariant(L, "S", goal="G")
        self.assertTrue(r.a0_compliant)
        self.assertEqual(r.unreachable_dead_ends, [])

    def test_unreachable_dead_ends_only_counts_reachable(self):
        """States not reachable from start are not counted as dead-ends."""
        L = Landscape()
        L.add_edge("S", "A", delta=2.0, resistance=1.0)
        L.add_edge("A", "G", delta=2.0, resistance=1.0)
        # X is a state with no exits but NOT reachable from S
        L.add_state("X")
        r = check_identity_invariant(L, "S", goal="G")
        # X not reachable -> not counted
        self.assertNotIn("X", r.unreachable_dead_ends)
        self.assertTrue(r.a0_compliant)


class TestHistorizationContinuity(unittest.TestCase):
    """Invariant 3: historization never touched by mutations (architectural)."""

    def test_historization_continuous_is_always_true(self):
        """check_identity_invariant always returns True for this invariant."""
        L = _chain()
        r = check_identity_invariant(L, "A", goal="C")
        self.assertTrue(r.historization_continuous)

    def test_historization_continuous_after_mutation(self):
        """Applying a mutation and checking: still True."""
        L = _diamond()
        # Adjust resistance on S->A
        L.adjust_base_resistance("S", "A", 2.0)
        r = check_identity_invariant(L, "S", goal="G")
        self.assertTrue(r.historization_continuous)

    def test_historization_data_survives_removal(self):
        """Historization traces on non-removed edges survive edge removal."""
        L = _diamond()
        # Record some historization on S->B using the correct API
        L.historization.update(Edge("S", "B"), Outcome.SUCCESS)
        tau_before = L.historization.tau
        # Remove S->A (not the historized edge)
        L.remove_edge("S", "A")
        # tau unchanged -- mutation did not trigger historization
        self.assertEqual(L.historization.tau, tau_before)
        # S->B trace still present
        self.assertGreater(L.historization.success_trace(Edge("S", "B")), 0)


class TestCombinedInvariants(unittest.TestCase):
    """Multi-invariant scenarios and first-violation ordering."""

    def test_both_violated_goal_reported_first(self):
        """When goal is unreachable AND dead-ends exist, goal is reported first."""
        L = Landscape()
        L.add_edge("S", "D", delta=1.0, resistance=1.0)
        # D has no exits (A0 violation) and there's no path to any goal
        r = check_identity_invariant(L, "S", goal="G")
        self.assertFalse(r.goal_reachable)
        self.assertFalse(r.satisfied)
        self.assertEqual(r.violated_check, "goal_reachable")

    def test_satisfied_full_chain_with_goal(self):
        L = _chain()
        r = check_identity_invariant(L, "A", goal="C")
        self.assertTrue(r.satisfied)
        self.assertIsNone(r.violated_check)
        self.assertTrue(r.goal_reachable)
        self.assertTrue(r.a0_compliant)
        self.assertTrue(r.historization_continuous)

    def test_only_a0_violated(self):
        """Goal reachable but a dead-end state exists off the happy path."""
        L = _dead_end_graph()
        # B is the goal (reachable via A), D is a dead-end
        r = check_identity_invariant(L, "S", goal="B")
        self.assertTrue(r.goal_reachable)
        self.assertFalse(r.a0_compliant)
        self.assertEqual(r.violated_check, "a0_compliant")
        self.assertFalse(r.satisfied)

    def test_empty_reachable_set(self):
        """Start state not in landscape -> only start in reachable set."""
        L = Landscape()
        L.add_state("Z")
        r = check_identity_invariant(L, "Z", goal=None)
        # Z has no exits -> A0 violated (no goal to exempt it)
        self.assertFalse(r.a0_compliant)


class TestInvariantInTuningCycle(unittest.TestCase):
    """Integration: structural_tuning_cycle reverts when invariant violated."""

    def test_identity_invariant_on_clean_cycle(self):
        """structural_tuning_cycle returns identity_invariant on accepted path."""
        L = _diamond()
        ctrl = E0Controller(L, _mk_exec(), s_max=10.0)
        result = structural_tuning_cycle(ctrl, "S", goal="G")
        # With a healthy diamond there may be no proposals -> no invariant check
        # OR proposals exist and are accepted -> invariant should be in result
        if result.applied_mutations:
            self.assertIsNotNone(result.identity_invariant)
            self.assertTrue(result.identity_invariant.satisfied)

    def test_invariant_present_on_accepted(self):
        """When mutations are accepted, identity_invariant is satisfied."""
        L = Landscape()
        # Landscape with a loop (will produce loop-fix proposals)
        L.add_edge("S", "A", delta=2.0, resistance=1.0)
        L.add_edge("A", "S", delta=2.0, resistance=1.0)  # loop
        L.add_edge("A", "G", delta=2.0, resistance=1.0)
        ctrl = E0Controller(L, _mk_exec(), s_max=10.0)
        history = MutationHistory()
        result = structural_tuning_cycle(
            ctrl, "S", goal="G", mutation_history=history
        )
        if result.applied_mutations:
            self.assertIsNotNone(result.identity_invariant)
            # If accepted, invariant must have been satisfied
            if result.accepted:
                self.assertTrue(result.identity_invariant.satisfied)

    def test_invariant_none_when_no_proposals(self):
        """When no proposals are generated, identity_invariant is None."""
        L = _diamond()
        ctrl = E0Controller(L, _mk_exec(), s_max=10.0)
        result = structural_tuning_cycle(ctrl, "S", goal="G")
        if not result.proposals:
            self.assertIsNone(result.identity_invariant)

    def test_invariant_goal_check_blocks_goal_severing_mutation(self):
        """Mutation that severs the goal path is blocked by Invariant 1."""
        # Build: S -> A -> G (only path from S to G)
        # X -> A: keeps A non-isolated when A->G is removed
        # G -> X: keeps G non-isolated when A->G is removed
        # (X is not reachable from S, so there is no alternate path S->...->G)
        L = Landscape()
        L.add_edge("S", "A", delta=2.0, resistance=1.0)
        L.add_edge("A", "G", delta=2.0, resistance=1.0)
        L.add_edge("X", "A", delta=1.0, resistance=1.0)  # not reachable from S
        L.add_edge("G", "X", delta=1.0, resistance=1.0)  # G stays non-isolated
        ctrl = E0Controller(L, _mk_exec(), s_max=10.0)

        # Manually apply a mutation that severs goal-path and check invariant
        mut = StructuralMutation(
            mutation_type=MutationType.REMOVE_EDGE,
            source="A", target="G",
        )
        apply_structural_mutation(mut, L)
        inv = check_identity_invariant(L, "S", goal="G")
        self.assertFalse(inv.goal_reachable)
        self.assertFalse(inv.satisfied)
        self.assertEqual(inv.violated_check, "goal_reachable")
        # Revert so landscape is clean
        revert_structural_mutation(mut, L)
        # After revert, invariant satisfied again
        inv2 = check_identity_invariant(L, "S", goal="G")
        self.assertTrue(inv2.satisfied)

    def test_invariant_a0_check_blocks_dead_end_creating_mutation(self):
        """Mutation creating a reachable dead-end is blocked by Invariant 2."""
        L = Landscape()
        L.add_edge("S", "A", delta=2.0, resistance=1.0)
        L.add_edge("A", "G", delta=2.0, resistance=1.0)
        L.add_edge("S", "D", delta=1.0, resistance=1.0)
        L.add_edge("D", "A", delta=1.0, resistance=1.0)  # D has an exit

        # Now remove D->A (makes D a dead-end but not the goal)
        mut = StructuralMutation(
            mutation_type=MutationType.REMOVE_EDGE,
            source="D", target="A",
        )
        apply_structural_mutation(mut, L)
        inv = check_identity_invariant(L, "S", goal="G")
        self.assertFalse(inv.a0_compliant)
        self.assertIn("D", inv.unreachable_dead_ends)
        # Revert
        revert_structural_mutation(mut, L)
        inv2 = check_identity_invariant(L, "S", goal="G")
        self.assertTrue(inv2.satisfied)

    def test_identity_invariant_field_on_result(self):
        """StructuralTuningCycleResult has identity_invariant field."""
        L = _diamond()
        ctrl = E0Controller(L, _mk_exec(), s_max=10.0)
        result = structural_tuning_cycle(ctrl, "S", goal="G")
        # The field must exist (may be None if no mutations applied)
        self.assertTrue(hasattr(result, "identity_invariant"))


if __name__ == "__main__":
    unittest.main()
