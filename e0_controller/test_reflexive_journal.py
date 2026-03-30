"""
Tests for E₀ Reflexive Journal & Stufe 4b Representation (C50)
================================================================
Closes Bridge 4 Stufe 4b: reflexive actions are represented in the
self-exposition — E₀ can explain what it has done to itself.

Tests cover:
1. ReflexiveJournalEntry dataclass
2. ReflexiveJournal — record, mark_restored, queries, format
3. build_self_exposition Section 5 — reflexive history rendering
4. Session integration — journal wired and populated
5. Exposition with live SelfGraph + journal end-to-end
"""

import shutil
import tempfile
import unittest

from e0_controller.primitives import Outcome
from e0_controller.landscape import Landscape
from e0_controller.self_graph import SelfGraph, ALL_COMPONENTS, CORE_COMPONENTS
from e0_controller.canon_loader import load_canon
from e0_controller.canon_self_bridge import build_self_exposition
from e0_controller.reflexive_action import (
    ReflexiveAction,
    ReflexiveActionResult,
    ReflexiveJournal,
    ReflexiveJournalEntry,
    apply_reflexive_actions,
)
from e0_controller.dual_reflection import (
    DualReflectionReport,
    SelfGraphDiagnosis,
    ComponentAssessment,
    diagnose_self_graph,
)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _make_action(component="curvature", flag="curvature_modulation",
                 old=True, new=False, reason="test"):
    return ReflexiveAction(
        component=component, flag_name=flag,
        old_value=old, new_value=new, reason=reason,
    )


def _make_result(actions=None, skipped=None):
    return ReflexiveActionResult(
        actions_taken=actions or [],
        skipped=skipped or [],
    )


def _make_landscape():
    L = Landscape()
    L.add_edge("A", "B", delta=1.0, resistance=1.0)
    L.add_edge("B", "C", delta=1.0, resistance=1.0)
    return L


# ──────────────────────────────────────────────
# 1. ReflexiveJournalEntry
# ──────────────────────────────────────────────

class TestReflexiveJournalEntry(unittest.TestCase):

    def test_fields(self):
        a = _make_action()
        e = ReflexiveJournalEntry(iteration=3, action=a)
        self.assertEqual(e.iteration, 3)
        self.assertIs(e.action, a)
        self.assertFalse(e.restored)

    def test_restored_default_false(self):
        e = ReflexiveJournalEntry(iteration=0, action=_make_action())
        self.assertFalse(e.restored)

    def test_restored_settable(self):
        e = ReflexiveJournalEntry(iteration=0, action=_make_action(),
                                  restored=True)
        self.assertTrue(e.restored)


# ──────────────────────────────────────────────
# 2. ReflexiveJournal
# ──────────────────────────────────────────────

class TestReflexiveJournal(unittest.TestCase):

    def test_empty_journal(self):
        j = ReflexiveJournal()
        self.assertEqual(j.total_actions, 0)
        self.assertEqual(j.active_count, 0)
        self.assertEqual(j.entries, [])
        self.assertEqual(j.current_state(), [])

    def test_record_returns_count(self):
        j = ReflexiveJournal()
        r = _make_result(actions=[_make_action(), _make_action("overlap")])
        self.assertEqual(j.record(r, iteration=1), 2)
        self.assertEqual(j.total_actions, 2)

    def test_record_empty_result(self):
        j = ReflexiveJournal()
        r = _make_result()
        self.assertEqual(j.record(r, iteration=0), 0)
        self.assertEqual(j.total_actions, 0)

    def test_entries_returns_copy(self):
        j = ReflexiveJournal()
        j.record(_make_result(actions=[_make_action()]), 0)
        entries = j.entries
        entries.clear()
        self.assertEqual(j.total_actions, 1)

    def test_active_deactivations(self):
        j = ReflexiveJournal()
        j.record(_make_result(actions=[_make_action()]), 0)
        self.assertEqual(j.active_count, 1)
        self.assertEqual(len(j.active_deactivations), 1)

    def test_mark_restored(self):
        j = ReflexiveJournal()
        j.record(_make_result(actions=[_make_action()]), 0)
        count = j.mark_restored(0)
        self.assertEqual(count, 1)
        self.assertEqual(j.active_count, 0)

    def test_mark_restored_wrong_iteration(self):
        j = ReflexiveJournal()
        j.record(_make_result(actions=[_make_action()]), 0)
        count = j.mark_restored(99)
        self.assertEqual(count, 0)
        self.assertEqual(j.active_count, 1)

    def test_mark_restored_idempotent(self):
        j = ReflexiveJournal()
        j.record(_make_result(actions=[_make_action()]), 0)
        j.mark_restored(0)
        count = j.mark_restored(0)
        self.assertEqual(count, 0)

    def test_current_state_single_deactivation(self):
        j = ReflexiveJournal()
        j.record(_make_result(actions=[_make_action()]), 0)
        state = j.current_state()
        self.assertEqual(state, [("curvature", False)])

    def test_current_state_after_restore(self):
        j = ReflexiveJournal()
        j.record(_make_result(actions=[_make_action()]), 0)
        j.mark_restored(0)
        state = j.current_state()
        self.assertEqual(state, [("curvature", True)])

    def test_current_state_multiple(self):
        j = ReflexiveJournal()
        a1 = _make_action("curvature", "curvature_modulation")
        a2 = _make_action("overlap", "overlap_modulation")
        j.record(_make_result(actions=[a1, a2]), 0)
        state = j.current_state()
        self.assertEqual(state, [("curvature", False), ("overlap", False)])

    def test_multi_iteration_record(self):
        j = ReflexiveJournal()
        j.record(_make_result(actions=[_make_action()]), 0)
        j.record(_make_result(actions=[
            _make_action("overlap", "overlap_modulation"),
        ]), 1)
        self.assertEqual(j.total_actions, 2)
        self.assertEqual(j.active_count, 2)

    def test_format_empty(self):
        j = ReflexiveJournal()
        self.assertIn("No reflexive actions", j.format())

    def test_format_with_entry(self):
        j = ReflexiveJournal()
        j.record(_make_result(actions=[_make_action(reason="q=-0.80")]), 0)
        fmt = j.format()
        self.assertIn("Iteration 0", fmt)
        self.assertIn("Deactivated", fmt)
        self.assertIn("curvature", fmt)
        self.assertIn("[active]", fmt)

    def test_format_restored_entry(self):
        j = ReflexiveJournal()
        j.record(_make_result(actions=[_make_action()]), 0)
        j.mark_restored(0)
        fmt = j.format()
        self.assertIn("[restored]", fmt)

    def test_non_deactivation_not_in_active(self):
        """Reactivation (old=False, new=True) should not be an active deactivation."""
        j = ReflexiveJournal()
        reactivation = _make_action(old=False, new=True)
        j.record(_make_result(actions=[reactivation]), 0)
        self.assertEqual(j.total_actions, 1)
        self.assertEqual(j.active_count, 0)


# ──────────────────────────────────────────────
# 3. build_self_exposition Section 5
# ──────────────────────────────────────────────

class TestExpositionSection5(unittest.TestCase):
    """Section 5 of self-exposition renders reflexive history."""

    def setUp(self):
        self.cl = load_canon("ontodynamics")

    def test_without_journal(self):
        expo = build_self_exposition(self.cl)
        self.assertIn("WHAT I HAVE DONE TO MYSELF", expo)
        self.assertIn("No reflexive self-modifications", expo)

    def test_with_empty_journal(self):
        j = ReflexiveJournal()
        expo = build_self_exposition(self.cl, reflexive_journal=j)
        self.assertIn("No reflexive self-modifications", expo)

    def test_with_populated_journal(self):
        j = ReflexiveJournal()
        j.record(_make_result(actions=[_make_action(reason="q=-0.90")]), 0)
        expo = build_self_exposition(self.cl, reflexive_journal=j)
        self.assertIn("WHAT I HAVE DONE TO MYSELF", expo)
        self.assertIn("Deactivated", expo)
        self.assertIn("curvature", expo)
        self.assertIn("operational reflexivity", expo)

    def test_shows_active_count(self):
        j = ReflexiveJournal()
        j.record(_make_result(actions=[_make_action()]), 0)
        expo = build_self_exposition(self.cl, reflexive_journal=j)
        self.assertIn("1 modulation", expo)

    def test_shows_current_state(self):
        j = ReflexiveJournal()
        j.record(_make_result(actions=[_make_action()]), 0)
        expo = build_self_exposition(self.cl, reflexive_journal=j)
        self.assertIn("DEACTIVATED", expo)

    def test_restored_journal(self):
        j = ReflexiveJournal()
        j.record(_make_result(actions=[_make_action()]), 0)
        j.mark_restored(0)
        expo = build_self_exposition(self.cl, reflexive_journal=j)
        self.assertIn("restored", expo.lower())

    def test_all_five_sections_present(self):
        sg = SelfGraph()
        j = ReflexiveJournal()
        expo = build_self_exposition(self.cl, sg=sg, reflexive_journal=j)
        self.assertIn("WHAT I BELIEVE", expo)
        self.assertIn("HOW I OPERATE", expo)
        self.assertIn("CANON COVERAGE", expo)
        self.assertIn("STRUCTURAL INSIGHT", expo)
        self.assertIn("WHAT I HAVE DONE TO MYSELF", expo)

    def test_journal_with_self_graph(self):
        """Both sg and journal produce a comprehensive exposition."""
        sg = SelfGraph()
        for _ in range(10):
            sg.self_historize(list(ALL_COMPONENTS), Outcome.SUCCESS)
        j = ReflexiveJournal()
        j.record(_make_result(actions=[_make_action(reason="q=-0.50")]), 0)
        expo = build_self_exposition(self.cl, sg=sg, reflexive_journal=j)
        self.assertGreater(len(expo), 3000)
        self.assertIn("Deactivated", expo)
        self.assertIn("historization", expo)

    def test_canon_l7_mentioned_when_active(self):
        """Active deactivations reference canon L7 reflexivity."""
        j = ReflexiveJournal()
        j.record(_make_result(actions=[_make_action()]), 0)
        expo = build_self_exposition(self.cl, reflexive_journal=j)
        self.assertIn("L7", expo)


# ──────────────────────────────────────────────
# 4. Session integration
# ──────────────────────────────────────────────

def _success_fn(state, target):
    return Outcome.SUCCESS


class TestSessionJournal(unittest.TestCase):
    """Session creates and wires the reflexive journal."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="e0_journal_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_session_has_journal(self):
        from e0_controller.session import Session
        L = _make_landscape()
        s = Session("j-test", L, _success_fn, base_dir=self.tmpdir)
        self.assertIsNotNone(s.reflexive_journal)
        self.assertIsInstance(s.reflexive_journal, ReflexiveJournal)

    def test_journal_starts_empty(self):
        from e0_controller.session import Session
        L = _make_landscape()
        s = Session("j-empty", L, _success_fn, base_dir=self.tmpdir)
        self.assertEqual(s.reflexive_journal.total_actions, 0)

    def test_journal_survives_iterate(self):
        """After iterate(), journal still exists and is accessible."""
        from e0_controller.session import Session
        L = _make_landscape()
        L.add_edge("C", "GOAL", delta=1.0, resistance=1.0)
        s = Session("j-iter", L, _success_fn, base_dir=self.tmpdir)
        s.iterate("A", goal="GOAL", max_cycles=10, max_iterations=2)
        self.assertIsNotNone(s.reflexive_journal)


# ──────────────────────────────────────────────
# 5. End-to-end: SelfGraph → diagnose → journal → exposition
# ──────────────────────────────────────────────

class TestEndToEnd(unittest.TestCase):
    """Full chain from self-graph diagnosis through journal to exposition."""

    def test_harmful_component_appears_in_exposition(self):
        """Harmful curvature → journal entry → visible in exposition."""
        sg = SelfGraph()
        L = Landscape(curvature_modulation=True)
        L.add_edge("A", "B", delta=1.0, resistance=1.0)

        # Make curvature harmful (edge: curvature→transition_field)
        for _ in range(15):
            sg.self_historize(["curvature", "transition_field"],
                             Outcome.FAILURE)
        for _ in range(15):
            sg.self_historize(list(CORE_COMPONENTS), Outcome.SUCCESS)

        diag = diagnose_self_graph(sg)
        report = DualReflectionReport(
            domain_report=None, self_diagnosis=diag,
        )
        result = apply_reflexive_actions(report, L)

        # Record in journal
        j = ReflexiveJournal()
        j.record(result, iteration=0)

        # Build exposition
        cl = load_canon("ontodynamics")
        expo = build_self_exposition(cl, sg=sg, reflexive_journal=j)

        self.assertIn("WHAT I HAVE DONE TO MYSELF", expo)
        self.assertIn("Deactivated", expo)
        self.assertIn("curvature", expo)
        self.assertIn("DEACTIVATED", expo)

    def test_restore_reflected_in_exposition(self):
        """After restore, exposition shows 'restored' status."""
        sg = SelfGraph()
        L = Landscape(curvature_modulation=True, overlap_modulation=True)
        L.add_edge("A", "B", delta=1.0, resistance=1.0)

        for _ in range(15):
            sg.self_historize(
                ["curvature", "overlap", "transition_field"],
                Outcome.FAILURE,
            )
        for _ in range(15):
            sg.self_historize(list(CORE_COMPONENTS), Outcome.SUCCESS)

        diag = diagnose_self_graph(sg)
        report = DualReflectionReport(
            domain_report=None, self_diagnosis=diag,
        )
        result = apply_reflexive_actions(report, L)

        j = ReflexiveJournal()
        j.record(result, iteration=0)

        # Restore
        result.restore(L)
        j.mark_restored(0)

        cl = load_canon("ontodynamics")
        expo = build_self_exposition(cl, sg=sg, reflexive_journal=j)

        self.assertIn("restored", expo.lower())
        # No active deactivations should be shown
        self.assertNotIn("DEACTIVATED", expo)

    def test_exposition_length_grows_with_journal(self):
        """Exposition is longer when journal has entries."""
        cl = load_canon("ontodynamics")
        sg = SelfGraph()

        expo_no_journal = build_self_exposition(cl, sg=sg)

        j = ReflexiveJournal()
        j.record(_make_result(actions=[_make_action(reason="q=-0.50")]), 0)
        expo_with_journal = build_self_exposition(
            cl, sg=sg, reflexive_journal=j,
        )

        self.assertGreater(len(expo_with_journal), len(expo_no_journal))


# ──────────────────────────────────────────────
# 6. Edge cases
# ──────────────────────────────────────────────

class TestEdgeCases(unittest.TestCase):

    def test_journal_multiple_iterations_same_component(self):
        """Same component deactivated in multiple iterations."""
        j = ReflexiveJournal()
        j.record(_make_result(actions=[_make_action()]), 0)
        j.mark_restored(0)
        j.record(_make_result(actions=[_make_action()]), 1)
        self.assertEqual(j.total_actions, 2)
        self.assertEqual(j.active_count, 1)
        state = j.current_state()
        self.assertEqual(state, [("curvature", False)])

    def test_format_no_crash_with_many_entries(self):
        j = ReflexiveJournal()
        for i in range(100):
            j.record(_make_result(actions=[_make_action()]), i)
        fmt = j.format()
        self.assertIsInstance(fmt, str)
        self.assertGreater(len(fmt), 100)

    def test_build_exposition_no_crash_none_journal(self):
        cl = load_canon("ontodynamics")
        expo = build_self_exposition(cl, reflexive_journal=None)
        self.assertIn("WHAT I HAVE DONE TO MYSELF", expo)


if __name__ == "__main__":
    unittest.main()
