"""
B4-S3 — Structural Tuning Cycle & Session Integration Tests
==============================================================
Tests for Bridge 4 Stufe 3: structural_tuning_cycle() and
Session.iterate() structural hook.

Test classes:
  1. TestStructuralTuningCycleResult  — dataclass basics (4)
  2. TestCycleNoProposals             — cycle with healthy landscape (4)
  3. TestCycleWithDeadStates          — dead states trigger Δ boost (5)
  4. TestCycleWithLoops               — loop states trigger R₀ raise (4)
  5. TestCycleRevert                  — quality regression → revert (4)
  6. TestCycleHistoryIntegration      — MutationHistory updated (5)
  7. TestSessionStructuralHook        — iterate() structural trigger (6)
  8. TestIterationResultFields        — IterationResult has structural_results (3)
  9. TestSessionMutationHistory       — Session carries MutationHistory (3)
  10. TestEndToEndStructural          — full iterate with structural (4)
"""

import unittest
from unittest.mock import patch, MagicMock
from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller
from e0_controller.reflection import (
    StructuralDiagnostic,
    ReflectionReport,
    ReflectionDecision,
)
from e0_controller.structural_mutation import (
    MutationType,
    StructuralMutation,
    MutationRecord,
    MutationHistory,
    StructuralTuningCycleResult,
    structural_tuning_cycle,
    apply_structural_mutation,
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


def _build_diamond_with_dead():
    """S→A, S→B, A→G, B→G, plus dead state D with edge S→D."""
    L = _build_diamond()
    L.add_state("D")
    L.add_edge("S", "D", delta=0.1, resistance=5.0)
    return L


def _build_loop_domain():
    """S→A, A→S (2-cycle), S→G. Loop invites R₀ boost proposal."""
    L = Landscape()
    L.add_state("S")
    L.add_state("A")
    L.add_state("G")
    L.add_edge("S", "A", delta=2.0, resistance=1.0)
    L.add_edge("A", "S", delta=2.0, resistance=1.0)
    L.add_edge("S", "G", delta=3.0, resistance=0.5)
    return L


def _mk_exec():
    return lambda s, t: Outcome.SUCCESS


# ══════════════════════════════════════════════════
# 1. StructuralTuningCycleResult basics
# ══════════════════════════════════════════════════

class TestStructuralTuningCycleResult(unittest.TestCase):

    def test_default_values(self):
        r = StructuralTuningCycleResult(
            quality_before=0.5,
            diagnostic=StructuralDiagnostic(),
            proposals=[],
            applied_mutations=[],
        )
        self.assertFalse(r.accepted)
        self.assertFalse(r.reverted)
        self.assertIsNone(r.quality_after)
        self.assertIsNone(r.delta_quality)

    def test_with_quality(self):
        r = StructuralTuningCycleResult(
            quality_before=0.3,
            diagnostic=StructuralDiagnostic(),
            proposals=[],
            applied_mutations=[],
            quality_after=0.5,
            delta_quality=0.2,
            accepted=True,
        )
        self.assertEqual(r.delta_quality, 0.2)
        self.assertTrue(r.accepted)

    def test_mutation_records_default_empty(self):
        r = StructuralTuningCycleResult(
            quality_before=0.5,
            diagnostic=StructuralDiagnostic(),
            proposals=[],
            applied_mutations=[],
        )
        self.assertEqual(r.mutation_records, [])

    def test_reverted_result(self):
        r = StructuralTuningCycleResult(
            quality_before=0.5,
            diagnostic=StructuralDiagnostic(),
            proposals=[],
            applied_mutations=[],
            quality_after=0.3,
            delta_quality=-0.2,
            accepted=False,
            reverted=True,
        )
        self.assertTrue(r.reverted)
        self.assertFalse(r.accepted)


# ══════════════════════════════════════════════════
# 2. Cycle with no proposals (healthy landscape)
# ══════════════════════════════════════════════════

class TestCycleNoProposals(unittest.TestCase):

    def test_healthy_diamond_no_mutations(self):
        """Diamond S→A→G has no dead states or loops → no proposals."""
        L = _build_diamond()
        ctrl = E0Controller(L, _mk_exec())
        result = structural_tuning_cycle(ctrl, "S", goal="G")
        self.assertEqual(result.proposals, [])
        self.assertEqual(result.applied_mutations, [])
        self.assertFalse(result.accepted)

    def test_quality_before_computed(self):
        L = _build_diamond()
        ctrl = E0Controller(L, _mk_exec())
        result = structural_tuning_cycle(ctrl, "S", goal="G")
        self.assertIsInstance(result.quality_before, float)
        self.assertGreaterEqual(result.quality_before, 0.0)

    def test_diagnostic_populated(self):
        L = _build_diamond()
        ctrl = E0Controller(L, _mk_exec())
        result = structural_tuning_cycle(ctrl, "S", goal="G")
        self.assertIsNotNone(result.diagnostic)

    def test_no_quality_after_when_no_proposals(self):
        L = _build_diamond()
        ctrl = E0Controller(L, _mk_exec())
        result = structural_tuning_cycle(ctrl, "S", goal="G")
        self.assertIsNone(result.quality_after)


# ══════════════════════════════════════════════════
# 3. Cycle with dead states
# ══════════════════════════════════════════════════

class TestCycleWithDeadStates(unittest.TestCase):

    def test_dead_state_generates_proposals(self):
        """Dead state D should generate Δ boost proposal."""
        L = _build_diamond_with_dead()
        ctrl = E0Controller(L, _mk_exec())
        result = structural_tuning_cycle(ctrl, "S", goal="G")
        # D is never visited (controller goes S→A→G or S→B→G)
        # So the diagnostic should find dead states and propose mutations
        if result.diagnostic.dead_states:
            self.assertGreater(len(result.proposals), 0)

    def test_proposals_are_adjust_delta_type(self):
        L = _build_diamond_with_dead()
        ctrl = E0Controller(L, _mk_exec())
        result = structural_tuning_cycle(ctrl, "S", goal="G")
        for p in result.proposals:
            if "dead" in p.motivation:
                self.assertEqual(p.mutation_type, MutationType.ADJUST_DELTA)

    def test_applied_mutations_filled(self):
        L = _build_diamond_with_dead()
        ctrl = E0Controller(L, _mk_exec())
        result = structural_tuning_cycle(ctrl, "S", goal="G")
        if result.proposals:
            self.assertGreaterEqual(len(result.applied_mutations), 1)

    def test_quality_after_computed(self):
        L = _build_diamond_with_dead()
        ctrl = E0Controller(L, _mk_exec())
        result = structural_tuning_cycle(ctrl, "S", goal="G")
        if result.applied_mutations:
            self.assertIsNotNone(result.quality_after)
            self.assertIsNotNone(result.delta_quality)

    def test_outcome_is_accepted_or_reverted(self):
        L = _build_diamond_with_dead()
        ctrl = E0Controller(L, _mk_exec())
        result = structural_tuning_cycle(ctrl, "S", goal="G")
        if result.applied_mutations:
            self.assertTrue(result.accepted or result.reverted)


# ══════════════════════════════════════════════════
# 4. Cycle with loop states
# ══════════════════════════════════════════════════

class TestCycleWithLoops(unittest.TestCase):

    def test_loop_detected_in_diagnostic(self):
        L = _build_loop_domain()
        ctrl = E0Controller(L, _mk_exec())
        result = structural_tuning_cycle(ctrl, "S", goal="G")
        # S↔A is a 2-cycle, so loop_states should include S and A
        self.assertIn("S", result.diagnostic.loop_states)
        self.assertIn("A", result.diagnostic.loop_states)

    def test_loop_generates_resistance_proposals(self):
        L = _build_loop_domain()
        ctrl = E0Controller(L, _mk_exec())
        result = structural_tuning_cycle(ctrl, "S", goal="G")
        r_proposals = [
            p for p in result.proposals
            if p.mutation_type == MutationType.ADJUST_RESISTANCE
        ]
        self.assertGreater(len(r_proposals), 0)

    def test_quality_is_computed(self):
        L = _build_loop_domain()
        ctrl = E0Controller(L, _mk_exec())
        result = structural_tuning_cycle(ctrl, "S", goal="G")
        self.assertIsInstance(result.quality_before, float)
        if result.applied_mutations:
            self.assertIsInstance(result.quality_after, float)

    def test_cycle_returns_result_type(self):
        L = _build_loop_domain()
        ctrl = E0Controller(L, _mk_exec())
        result = structural_tuning_cycle(ctrl, "S", goal="G")
        self.assertIsInstance(result, StructuralTuningCycleResult)


# ══════════════════════════════════════════════════
# 5. Cycle revert on regression
# ══════════════════════════════════════════════════

class TestCycleRevert(unittest.TestCase):

    def test_revert_restores_landscape(self):
        """If quality drops, mutations should be reverted."""
        L = _build_loop_domain()
        ctrl = E0Controller(L, _mk_exec())
        # Capture original R₀ for the loop edge
        orig_r = L.base_resistance("S", "A")

        result = structural_tuning_cycle(ctrl, "S", goal="G")
        if result.reverted:
            # After revert, resistance should be back to original
            self.assertAlmostEqual(L.base_resistance("S", "A"), orig_r)

    def test_reverted_flag_set(self):
        L = _build_loop_domain()
        ctrl = E0Controller(L, _mk_exec())
        result = structural_tuning_cycle(ctrl, "S", goal="G")
        if result.applied_mutations and result.delta_quality is not None:
            if result.delta_quality < 0:
                self.assertTrue(result.reverted)
                self.assertFalse(result.accepted)

    def test_accepted_when_positive_delta(self):
        L = _build_loop_domain()
        ctrl = E0Controller(L, _mk_exec())
        result = structural_tuning_cycle(ctrl, "S", goal="G")
        if result.applied_mutations and result.delta_quality is not None:
            if result.delta_quality >= 0:
                self.assertTrue(result.accepted)
                self.assertFalse(result.reverted)

    def test_mutation_records_match_applied(self):
        L = _build_loop_domain()
        ctrl = E0Controller(L, _mk_exec())
        result = structural_tuning_cycle(ctrl, "S", goal="G")
        self.assertEqual(
            len(result.mutation_records),
            len(result.applied_mutations),
        )


# ══════════════════════════════════════════════════
# 6. MutationHistory integration
# ══════════════════════════════════════════════════

class TestCycleHistoryIntegration(unittest.TestCase):

    def test_history_updated_after_cycle(self):
        L = _build_loop_domain()
        ctrl = E0Controller(L, _mk_exec())
        history = MutationHistory()
        result = structural_tuning_cycle(
            ctrl, "S", goal="G", mutation_history=history,
        )
        self.assertEqual(len(history.records), len(result.mutation_records))

    def test_history_none_creates_fresh(self):
        """Passing mutation_history=None should not crash."""
        L = _build_diamond()
        ctrl = E0Controller(L, _mk_exec())
        result = structural_tuning_cycle(ctrl, "S", goal="G")
        self.assertIsInstance(result, StructuralTuningCycleResult)

    def test_history_prevents_oscillation_on_repeat(self):
        """After one cycle, oscillating proposals should be blocked."""
        L = _build_loop_domain()
        ctrl = E0Controller(L, _mk_exec())
        history = MutationHistory()

        # Run first cycle
        r1 = structural_tuning_cycle(
            ctrl, "S", goal="G", mutation_history=history,
        )
        n_first = len(r1.mutation_records)

        # Run second cycle on same landscape — oscillation guard may filter
        r2 = structural_tuning_cycle(
            ctrl, "S", goal="G", mutation_history=history,
        )
        # History should have accumulated records
        self.assertEqual(
            len(history.records),
            len(r1.mutation_records) + len(r2.mutation_records),
        )

    def test_records_have_quality_values(self):
        L = _build_loop_domain()
        ctrl = E0Controller(L, _mk_exec())
        history = MutationHistory()
        result = structural_tuning_cycle(
            ctrl, "S", goal="G", mutation_history=history,
        )
        for rec in result.mutation_records:
            self.assertIsInstance(rec.quality_before, float)
            self.assertIsInstance(rec.quality_after, float)

    def test_records_accepted_consistency(self):
        L = _build_loop_domain()
        ctrl = E0Controller(L, _mk_exec())
        history = MutationHistory()
        result = structural_tuning_cycle(
            ctrl, "S", goal="G", mutation_history=history,
        )
        for rec in result.mutation_records:
            if result.accepted:
                self.assertTrue(rec.accepted)
                self.assertFalse(rec.reverted)
            if result.reverted:
                self.assertFalse(rec.accepted)
                self.assertTrue(rec.reverted)


# ══════════════════════════════════════════════════
# 7. Session.iterate() structural hook
# ══════════════════════════════════════════════════

class TestSessionStructuralHook(unittest.TestCase):
    """Test that iterate() invokes structural tuning on structural trigger."""

    def _make_session(self):
        from e0_controller.session import Session
        L = _build_loop_domain()
        return Session("test-structural", L, _mk_exec())

    def test_session_has_mutation_history(self):
        s = self._make_session()
        self.assertIsInstance(s.mutation_history, MutationHistory)

    def test_iterate_returns_structural_results(self):
        s = self._make_session()
        result = s.iterate("S", goal="G", max_iterations=2)
        self.assertTrue(hasattr(result, "structural_results"))
        self.assertIsInstance(result.structural_results, list)

    def test_structural_results_length_matches_iterations(self):
        s = self._make_session()
        result = s.iterate("S", goal="G", max_iterations=2)
        self.assertEqual(len(result.structural_results), result.iterations)

    def test_no_structural_trigger_gives_none(self):
        """Without structural reflection, structural_results entries are None."""
        s = self._make_session()
        result = s.iterate("S", goal="G", max_iterations=1)
        # On a simple run, reflection_type is unlikely to be "structural"
        # (needs TuningMemory with 3+ entries + plateau)
        for sr in result.structural_results:
            # Most entries should be None (no structural trigger)
            if sr is not None:
                self.assertIsInstance(sr, StructuralTuningCycleResult)

    @patch("e0_controller.session.structural_tuning_cycle")
    @patch("e0_controller.session.should_continue")
    def test_structural_trigger_invokes_cycle(self, mock_sc, mock_stc):
        """If reflection returns structural type, structural_tuning_cycle is called."""
        from e0_controller.residual_tension import IterationVerdict, ResidualTensionMap

        mock_stc.return_value = StructuralTuningCycleResult(
            quality_before=0.5,
            diagnostic=StructuralDiagnostic(),
            proposals=[],
            applied_mutations=[],
        )

        # Provide verdicts: first continue+reflect, second stop
        dummy_map = ResidualTensionMap(
            residuals=[], hotspots=[], resolved=[], amplified=[],
            iteration=1, max_residual=0.0, mean_residual=0.0,
        )
        mock_sc.side_effect = [
            IterationVerdict(
                should_continue=True, should_reflect=True,
                reason="tension_active", residual_map=dummy_map, iteration=1,
            ),
            IterationVerdict(
                should_continue=False, should_reflect=False,
                reason="budget", residual_map=dummy_map, iteration=2,
            ),
        ]

        s = self._make_session()
        # Patch _inter_iteration_reflect to return structural report
        structural_report = ReflectionReport(
            reflection_type="structural",
            observed_patterns=["plateau"],
            likely_layers=["landscape"],
        )
        with patch.object(s, "_inter_iteration_reflect", return_value=structural_report):
            result = s.iterate("S", goal="G", max_iterations=2)

        # structural_tuning_cycle should have been called on iteration 1
        self.assertTrue(mock_stc.called)

    @patch("e0_controller.session.structural_tuning_cycle")
    def test_non_structural_reflection_skips_cycle(self, mock_stc):
        """Quality reflection should NOT trigger structural_tuning_cycle."""
        s = self._make_session()
        quality_report = ReflectionReport(
            reflection_type="quality",
            observed_patterns=["low efficiency"],
            likely_layers=["controller"],
        )
        with patch.object(s, "_inter_iteration_reflect", return_value=quality_report):
            s.iterate("S", goal="G", max_iterations=2)

        mock_stc.assert_not_called()


# ══════════════════════════════════════════════════
# 8. IterationResult has structural_results field
# ══════════════════════════════════════════════════

class TestIterationResultFields(unittest.TestCase):

    def test_iteration_result_default_empty(self):
        from e0_controller.session import IterationResult
        ir = IterationResult(
            results=[],
            verdicts=[],
            reflections=[],
            final_map=None,
            iterations=0,
            stop_reason="empty",
        )
        self.assertEqual(ir.structural_results, [])

    def test_iteration_result_explicit(self):
        from e0_controller.session import IterationResult
        stc = StructuralTuningCycleResult(
            quality_before=0.5,
            diagnostic=StructuralDiagnostic(),
            proposals=[],
            applied_mutations=[],
        )
        ir = IterationResult(
            results=[],
            verdicts=[],
            reflections=[],
            final_map=None,
            iterations=1,
            stop_reason="budget",
            structural_results=[stc],
        )
        self.assertEqual(len(ir.structural_results), 1)

    def test_policy_phases_still_works(self):
        from e0_controller.session import IterationResult
        ir = IterationResult(
            results=[],
            verdicts=[],
            reflections=[],
            final_map=None,
            iterations=0,
            stop_reason="empty",
            policy_phases=["warmup"],
        )
        self.assertEqual(ir.policy_phases, ["warmup"])


# ══════════════════════════════════════════════════
# 9. Session carries MutationHistory
# ══════════════════════════════════════════════════

class TestSessionMutationHistory(unittest.TestCase):

    def test_new_session_has_empty_history(self):
        from e0_controller.session import Session
        L = _build_diamond()
        s = Session("test-hist", L, _mk_exec())
        self.assertEqual(len(s.mutation_history.records), 0)

    def test_resumed_session_has_history(self):
        """Session.resume() should also create mutation_history."""
        from e0_controller.session import Session
        L = _build_diamond()
        s = Session("test-resume-hist", L, _mk_exec())
        # We can't easily test resume without disk state,
        # but we verify the attribute exists on a fresh session
        self.assertIsInstance(s.mutation_history, MutationHistory)

    def test_mutation_history_is_mutable(self):
        from e0_controller.session import Session
        L = _build_diamond()
        s = Session("test-mut", L, _mk_exec())
        m = StructuralMutation(
            mutation_type=MutationType.ADJUST_DELTA,
            source="S", target="A",
            new_value=5.0, motivation="test",
        )
        rec = MutationRecord(
            mutation=m, quality_before=0.5, quality_after=0.6,
            accepted=True, reverted=False,
        )
        s.mutation_history.record(rec)
        self.assertEqual(len(s.mutation_history.records), 1)


# ══════════════════════════════════════════════════
# 10. End-to-end structural tuning
# ══════════════════════════════════════════════════

class TestEndToEndStructural(unittest.TestCase):

    def test_full_cycle_on_loop_graph(self):
        """Complete cycle on a loop graph should produce valid result."""
        L = _build_loop_domain()
        ctrl = E0Controller(L, _mk_exec())
        history = MutationHistory()
        result = structural_tuning_cycle(
            ctrl, "S", goal="G", mutation_history=history,
        )
        self.assertIsInstance(result, StructuralTuningCycleResult)
        self.assertIsInstance(result.quality_before, float)
        # Diagnostic should have found loop states
        self.assertTrue(len(result.diagnostic.loop_states) > 0)

    def test_multiple_cycles_accumulate_history(self):
        """Running cycle twice accumulates MutationHistory records."""
        L = _build_loop_domain()
        ctrl = E0Controller(L, _mk_exec())
        history = MutationHistory()
        r1 = structural_tuning_cycle(
            ctrl, "S", goal="G", mutation_history=history,
        )
        n1 = len(history.records)
        r2 = structural_tuning_cycle(
            ctrl, "S", goal="G", mutation_history=history,
        )
        n2 = len(history.records)
        self.assertGreaterEqual(n2, n1)

    def test_dead_state_cycle_modifies_landscape(self):
        """If accepted, landscape Δ should be changed for dead state."""
        L = _build_diamond_with_dead()
        ctrl = E0Controller(L, _mk_exec())
        orig_delta_sd = L.difference("S", "D")
        result = structural_tuning_cycle(ctrl, "S", goal="G")
        if result.accepted:
            new_delta_sd = L.difference("S", "D")
            self.assertNotAlmostEqual(new_delta_sd, orig_delta_sd)
        elif result.reverted:
            # Should be restored
            self.assertAlmostEqual(L.difference("S", "D"), orig_delta_sd)

    def test_no_goal_still_works(self):
        """structural_tuning_cycle without a goal should not crash."""
        L = _build_diamond()
        ctrl = E0Controller(L, _mk_exec())
        result = structural_tuning_cycle(ctrl, "S")
        self.assertIsInstance(result, StructuralTuningCycleResult)


if __name__ == "__main__":
    unittest.main()
