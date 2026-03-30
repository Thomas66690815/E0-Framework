"""
Tests for E₀ Reflexive Action (C49)
=====================================
Closes the reflexive loop: diagnosis → concrete landscape mutation.

Tests cover:
1. ReflexiveAction dataclass
2. ReflexiveActionResult (undo, summary)
3. plan_reflexive_actions (what should happen)
4. apply_reflexive_actions (what does happen)
5. Session.iterate() integration — Step 7
6. Core component protection
7. End-to-end with live SelfGraph diagnosis
8. Edge cases
"""

import shutil
import tempfile
import unittest
from unittest.mock import patch

from e0_controller.primitives import Outcome
from e0_controller.landscape import Landscape
from e0_controller.self_graph import (
    SelfGraph,
    CORE_COMPONENTS,
    MODULATION_COMPONENTS,
)
from e0_controller.dual_reflection import (
    ComponentAssessment,
    SelfGraphDiagnosis,
    DualReflectionReport,
    diagnose_self_graph,
)
from e0_controller.reflexive_action import (
    ReflexiveAction,
    ReflexiveActionResult,
    plan_reflexive_actions,
    apply_reflexive_actions,
    _MODULATION_FLAGS,
)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _make_landscape(curvature=False, overlap=False):
    """Build a minimal triangle landscape with modulation flags."""
    L = Landscape(
        curvature_modulation=curvature,
        overlap_modulation=overlap,
    )
    L.add_edge("A", "B", delta=0.5, resistance=0.3)
    L.add_edge("B", "C", delta=0.5, resistance=0.3)
    L.add_edge("A", "C", delta=0.8, resistance=0.5)
    return L


def _inject_traces(sg, components, outcome, n=1):
    for _ in range(n):
        sg.self_historize(components, outcome)


def _make_diagnosis(
    deactivation_candidates=None,
    harmful=None,
    components=None,
):
    """Build a SelfGraphDiagnosis with specified candidates."""
    if deactivation_candidates is None:
        deactivation_candidates = []
    if harmful is None:
        harmful = []
    if components is None:
        components = []
    return SelfGraphDiagnosis(
        components=components,
        deactivation_candidates=deactivation_candidates,
        harmful=harmful,
    )


def _make_report(diagnosis):
    """Wrap a diagnosis into a DualReflectionReport."""
    return DualReflectionReport(
        domain_report=None,
        self_diagnosis=diagnosis,
    )


# ──────────────────────────────────────────────
# 1. ReflexiveAction dataclass
# ──────────────────────────────────────────────

class TestReflexiveAction(unittest.TestCase):

    def test_fields(self):
        a = ReflexiveAction(
            component="curvature",
            flag_name="curvature_modulation",
            old_value=True, new_value=False,
            reason="quality=-0.8",
        )
        self.assertEqual(a.component, "curvature")
        self.assertEqual(a.flag_name, "curvature_modulation")
        self.assertTrue(a.old_value)
        self.assertFalse(a.new_value)

    def test_is_deactivation_true(self):
        a = ReflexiveAction("curvature", "curvature_modulation",
                            old_value=True, new_value=False, reason="harmful")
        self.assertTrue(a.is_deactivation)

    def test_is_deactivation_false_for_reactivation(self):
        a = ReflexiveAction("curvature", "curvature_modulation",
                            old_value=False, new_value=True, reason="restored")
        self.assertFalse(a.is_deactivation)

    def test_is_deactivation_false_for_noop(self):
        a = ReflexiveAction("curvature", "curvature_modulation",
                            old_value=False, new_value=False, reason="already off")
        self.assertFalse(a.is_deactivation)


# ──────────────────────────────────────────────
# 2. ReflexiveActionResult
# ──────────────────────────────────────────────

class TestReflexiveActionResult(unittest.TestCase):

    def test_empty_result(self):
        r = ReflexiveActionResult()
        self.assertFalse(r.any_changes)
        self.assertEqual(len(r.actions_taken), 0)
        self.assertEqual(len(r.skipped), 0)

    def test_any_changes_true(self):
        r = ReflexiveActionResult(
            actions_taken=[ReflexiveAction(
                "curvature", "curvature_modulation",
                True, False, "harmful",
            )]
        )
        self.assertTrue(r.any_changes)

    def test_restore_reverses_changes(self):
        L = _make_landscape(curvature=True, overlap=True)
        self.assertTrue(L.curvature_modulation)
        self.assertTrue(L.overlap_modulation)

        r = ReflexiveActionResult(actions_taken=[
            ReflexiveAction("curvature", "curvature_modulation",
                            True, False, "harmful"),
            ReflexiveAction("overlap", "overlap_modulation",
                            True, False, "harmful"),
        ])
        # Simulate the deactivation
        L.curvature_modulation = False
        L.overlap_modulation = False
        self.assertFalse(L.curvature_modulation)

        count = r.restore(L)
        self.assertEqual(count, 2)
        self.assertTrue(L.curvature_modulation)
        self.assertTrue(L.overlap_modulation)

    def test_restore_order_reversed(self):
        """Restore applies in reverse order (last action undone first)."""
        L = _make_landscape(curvature=True)
        r = ReflexiveActionResult(actions_taken=[
            ReflexiveAction("curvature", "curvature_modulation",
                            True, False, "first"),
        ])
        L.curvature_modulation = False
        r.restore(L)
        self.assertTrue(L.curvature_modulation)

    def test_summary_no_actions(self):
        r = ReflexiveActionResult()
        self.assertIn("No reflexive actions", r.summary())

    def test_summary_with_deactivation(self):
        r = ReflexiveActionResult(actions_taken=[
            ReflexiveAction("curvature", "curvature_modulation",
                            True, False, "quality=-0.8"),
        ])
        s = r.summary()
        self.assertIn("Deactivated", s)
        self.assertIn("curvature", s)

    def test_summary_with_skipped(self):
        r = ReflexiveActionResult(skipped=["overlap"])
        s = r.summary()
        self.assertIn("Skipped", s)
        self.assertIn("overlap", s)


# ──────────────────────────────────────────────
# 3. plan_reflexive_actions
# ──────────────────────────────────────────────

class TestPlanReflexiveActions(unittest.TestCase):

    def test_no_candidates_no_actions(self):
        L = _make_landscape(curvature=True)
        diag = _make_diagnosis(deactivation_candidates=[])
        actions = plan_reflexive_actions(diag, L)
        self.assertEqual(len(actions), 0)

    def test_curvature_candidate_active(self):
        L = _make_landscape(curvature=True)
        diag = _make_diagnosis(
            deactivation_candidates=["curvature"],
            components=[ComponentAssessment(
                name="curvature", load=10.0, quality=-0.8,
                inertia=0.5, status="harmful", is_modulation=True,
            )],
        )
        actions = plan_reflexive_actions(diag, L)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].component, "curvature")
        self.assertTrue(actions[0].old_value)
        self.assertFalse(actions[0].new_value)

    def test_curvature_candidate_already_inactive(self):
        L = _make_landscape(curvature=False)
        diag = _make_diagnosis(deactivation_candidates=["curvature"])
        actions = plan_reflexive_actions(diag, L)
        self.assertEqual(len(actions), 0)

    def test_overlap_candidate_active(self):
        L = _make_landscape(overlap=True)
        diag = _make_diagnosis(deactivation_candidates=["overlap"])
        actions = plan_reflexive_actions(diag, L)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].component, "overlap")

    def test_both_candidates(self):
        L = _make_landscape(curvature=True, overlap=True)
        diag = _make_diagnosis(
            deactivation_candidates=["curvature", "overlap"],
        )
        actions = plan_reflexive_actions(diag, L)
        self.assertEqual(len(actions), 2)
        names = {a.component for a in actions}
        self.assertEqual(names, {"curvature", "overlap"})

    def test_core_component_ignored(self):
        """Core components in deactivation_candidates are not planned."""
        L = _make_landscape(curvature=True)
        diag = _make_diagnosis(
            deactivation_candidates=["amplitude", "born", "historization"],
        )
        actions = plan_reflexive_actions(diag, L)
        self.assertEqual(len(actions), 0)

    def test_unknown_component_ignored(self):
        L = _make_landscape()
        diag = _make_diagnosis(deactivation_candidates=["nonexistent_module"])
        actions = plan_reflexive_actions(diag, L)
        self.assertEqual(len(actions), 0)

    def test_reason_includes_quality(self):
        L = _make_landscape(curvature=True)
        diag = _make_diagnosis(
            deactivation_candidates=["curvature"],
            components=[ComponentAssessment(
                name="curvature", load=15.0, quality=-0.6,
                inertia=0.3, status="harmful", is_modulation=True,
            )],
        )
        actions = plan_reflexive_actions(diag, L)
        self.assertIn("quality=", actions[0].reason)
        self.assertIn("-0.6", actions[0].reason)


# ──────────────────────────────────────────────
# 4. apply_reflexive_actions
# ──────────────────────────────────────────────

class TestApplyReflexiveActions(unittest.TestCase):

    def test_deactivates_curvature(self):
        L = _make_landscape(curvature=True)
        diag = _make_diagnosis(deactivation_candidates=["curvature"])
        report = _make_report(diag)

        result = apply_reflexive_actions(report, L)
        self.assertTrue(result.any_changes)
        self.assertFalse(L.curvature_modulation)

    def test_deactivates_overlap(self):
        L = _make_landscape(overlap=True)
        diag = _make_diagnosis(deactivation_candidates=["overlap"])
        report = _make_report(diag)

        result = apply_reflexive_actions(report, L)
        self.assertTrue(result.any_changes)
        self.assertFalse(L.overlap_modulation)

    def test_deactivates_both(self):
        L = _make_landscape(curvature=True, overlap=True)
        diag = _make_diagnosis(
            deactivation_candidates=["curvature", "overlap"],
        )
        report = _make_report(diag)

        result = apply_reflexive_actions(report, L)
        self.assertEqual(len(result.actions_taken), 2)
        self.assertFalse(L.curvature_modulation)
        self.assertFalse(L.overlap_modulation)

    def test_skips_already_inactive(self):
        L = _make_landscape(curvature=False)
        diag = _make_diagnosis(deactivation_candidates=["curvature"])
        report = _make_report(diag)

        result = apply_reflexive_actions(report, L)
        self.assertFalse(result.any_changes)
        self.assertIn("curvature", result.skipped)

    def test_mixed_active_and_inactive(self):
        L = _make_landscape(curvature=True, overlap=False)
        diag = _make_diagnosis(
            deactivation_candidates=["curvature", "overlap"],
        )
        report = _make_report(diag)

        result = apply_reflexive_actions(report, L)
        self.assertEqual(len(result.actions_taken), 1)
        self.assertEqual(result.actions_taken[0].component, "curvature")
        self.assertIn("overlap", result.skipped)
        self.assertFalse(L.curvature_modulation)

    def test_no_candidates_no_changes(self):
        L = _make_landscape(curvature=True, overlap=True)
        diag = _make_diagnosis(deactivation_candidates=[])
        report = _make_report(diag)

        result = apply_reflexive_actions(report, L)
        self.assertFalse(result.any_changes)
        # modulations untouched
        self.assertTrue(L.curvature_modulation)
        self.assertTrue(L.overlap_modulation)

    def test_undo_after_apply(self):
        L = _make_landscape(curvature=True, overlap=True)
        diag = _make_diagnosis(
            deactivation_candidates=["curvature", "overlap"],
        )
        report = _make_report(diag)

        result = apply_reflexive_actions(report, L)
        self.assertFalse(L.curvature_modulation)
        self.assertFalse(L.overlap_modulation)

        # Undo
        restored = result.restore(L)
        self.assertEqual(restored, 2)
        self.assertTrue(L.curvature_modulation)
        self.assertTrue(L.overlap_modulation)


# ──────────────────────────────────────────────
# 5. Core component protection
# ──────────────────────────────────────────────

class TestCoreProtection(unittest.TestCase):

    def test_modulation_flags_only_contain_modulations(self):
        """_MODULATION_FLAGS should never contain core components."""
        for comp in CORE_COMPONENTS:
            self.assertNotIn(comp, _MODULATION_FLAGS)

    def test_modulation_flags_contain_known_modulations(self):
        for comp in MODULATION_COMPONENTS:
            self.assertIn(comp, _MODULATION_FLAGS)

    def test_core_in_candidates_never_applied(self):
        """Even if diagnosis lists core components, no action is taken."""
        L = _make_landscape(curvature=True)
        all_core = list(CORE_COMPONENTS)
        diag = _make_diagnosis(deactivation_candidates=all_core)
        report = _make_report(diag)
        result = apply_reflexive_actions(report, L)
        self.assertFalse(result.any_changes)
        # curvature stays on — it wasn't targeted as core
        self.assertTrue(L.curvature_modulation)


# ──────────────────────────────────────────────
# 6. End-to-end with live SelfGraph diagnosis
# ──────────────────────────────────────────────

class TestEndToEnd(unittest.TestCase):

    def test_harmful_curvature_deactivated(self):
        """Full chain: SelfGraph → diagnose → reflexive action."""
        sg = SelfGraph()
        L = _make_landscape(curvature=True)

        # Make curvature harmful: many failures (edge: curvature→transition_field)
        for _ in range(15):
            sg.self_historize(["curvature", "transition_field"], Outcome.FAILURE)
        # Make core components healthy
        for _ in range(15):
            sg.self_historize(list(CORE_COMPONENTS), Outcome.SUCCESS)

        diag = diagnose_self_graph(sg)
        self.assertIn("curvature", diag.deactivation_candidates)

        report = DualReflectionReport(
            domain_report=None,
            self_diagnosis=diag,
        )
        result = apply_reflexive_actions(report, L)
        self.assertTrue(result.any_changes)
        self.assertFalse(L.curvature_modulation)

    def test_healthy_curvature_stays_active(self):
        """No deactivation when curvature performs well."""
        sg = SelfGraph()
        L = _make_landscape(curvature=True)

        for _ in range(15):
            sg.self_historize(["curvature", "transition_field"], Outcome.SUCCESS)
        for _ in range(15):
            sg.self_historize(list(CORE_COMPONENTS), Outcome.SUCCESS)

        diag = diagnose_self_graph(sg)
        self.assertNotIn("curvature", diag.deactivation_candidates)

        report = DualReflectionReport(
            domain_report=None,
            self_diagnosis=diag,
        )
        result = apply_reflexive_actions(report, L)
        self.assertFalse(result.any_changes)
        self.assertTrue(L.curvature_modulation)

    def test_confused_component_not_deactivated(self):
        """Confused (q≈0) components are NOT deactivated — only harmful ones."""
        sg = SelfGraph()
        L = _make_landscape(curvature=True)

        # Mixed: half success, half failure → confused
        for _ in range(10):
            sg.self_historize(["curvature", "transition_field"], Outcome.SUCCESS)
        for _ in range(10):
            sg.self_historize(["curvature", "transition_field"], Outcome.FAILURE)
        for _ in range(15):
            sg.self_historize(list(CORE_COMPONENTS), Outcome.SUCCESS)

        diag = diagnose_self_graph(sg)
        # Confused shouldn't appear in deactivation_candidates
        self.assertNotIn("curvature", diag.deactivation_candidates)

        report = DualReflectionReport(
            domain_report=None,
            self_diagnosis=diag,
        )
        result = apply_reflexive_actions(report, L)
        self.assertFalse(result.any_changes)
        self.assertTrue(L.curvature_modulation)

    def test_restore_after_end_to_end(self):
        """Full chain with undo."""
        sg = SelfGraph()
        L = _make_landscape(curvature=True, overlap=True)

        for _ in range(15):
            sg.self_historize(["curvature", "overlap", "transition_field"], Outcome.FAILURE)
        for _ in range(15):
            sg.self_historize(list(CORE_COMPONENTS), Outcome.SUCCESS)

        diag = diagnose_self_graph(sg)
        report = DualReflectionReport(
            domain_report=None,
            self_diagnosis=diag,
        )
        result = apply_reflexive_actions(report, L)
        # Both deactivated
        self.assertFalse(L.curvature_modulation)
        self.assertFalse(L.overlap_modulation)

        # Undo
        result.restore(L)
        self.assertTrue(L.curvature_modulation)
        self.assertTrue(L.overlap_modulation)


def _success_fn(state, target):
    return Outcome.SUCCESS


def _make_session_landscape():
    """Simple A → B → C → GOAL for Session tests."""
    L = Landscape()
    L.add_edge("A", "B", delta=1.0, resistance=1.0)
    L.add_edge("B", "C", delta=1.0, resistance=1.0)
    L.add_edge("C", "GOAL", delta=1.0, resistance=1.0)
    return L


# ──────────────────────────────────────────────
# 7. Session integration
# ──────────────────────────────────────────────

class TestSessionIntegration(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="e0_reflex_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_iteration_result_has_reflexive_results(self):
        """IterationResult has reflexive_results field."""
        from e0_controller.session import IterationResult
        ir = IterationResult(
            results=[], verdicts=[], reflections=[],
            final_map=None, iterations=0, stop_reason="test",
        )
        self.assertIsInstance(ir.reflexive_results, list)
        self.assertEqual(len(ir.reflexive_results), 0)

    def test_session_has_self_graph(self):
        """Session.__init__ creates a SelfGraph."""
        from e0_controller.session import Session
        L = _make_session_landscape()
        s = Session("reflex-sg", L, _success_fn, base_dir=self.tmpdir)
        self.assertIsNotNone(s.self_graph)
        self.assertIsNotNone(s.controller.self_graph)

    def test_session_iterate_produces_reflexive_results(self):
        """Session.iterate() populates reflexive_results list."""
        from e0_controller.session import Session
        L = _make_session_landscape()
        s = Session("reflex-iter", L, _success_fn, base_dir=self.tmpdir)
        result = s.iterate("A", goal="GOAL", max_cycles=10,
                           max_iterations=2)
        # reflexive_results should have same length as other per-iteration lists
        self.assertEqual(
            len(result.reflexive_results),
            len(result.verdicts),
        )

    def test_session_iterate_reflexive_results_are_optional(self):
        """Each reflexive_result is either None or ReflexiveActionResult."""
        from e0_controller.session import Session
        L = _make_session_landscape()
        s = Session("reflex-opt", L, _success_fn, base_dir=self.tmpdir)
        result = s.iterate("A", goal="GOAL", max_cycles=10,
                           max_iterations=2)
        for rr in result.reflexive_results:
            if rr is not None:
                self.assertIsInstance(rr, ReflexiveActionResult)

    def test_backward_compat_default_empty(self):
        """IterationResult defaults to empty reflexive_results."""
        from e0_controller.session import IterationResult
        ir = IterationResult(
            results=[], verdicts=[], reflections=[],
            final_map=None, iterations=0, stop_reason="budget",
        )
        self.assertEqual(ir.reflexive_results, [])


# ──────────────────────────────────────────────
# 8. Edge cases
# ──────────────────────────────────────────────

class TestEdgeCases(unittest.TestCase):

    def test_empty_diagnosis(self):
        L = _make_landscape(curvature=True)
        diag = SelfGraphDiagnosis()
        report = _make_report(diag)
        result = apply_reflexive_actions(report, L)
        self.assertFalse(result.any_changes)

    def test_repeated_apply_idempotent(self):
        """Applying same diagnosis twice — second time is no-op."""
        L = _make_landscape(curvature=True)
        diag = _make_diagnosis(deactivation_candidates=["curvature"])
        report = _make_report(diag)

        r1 = apply_reflexive_actions(report, L)
        self.assertTrue(r1.any_changes)
        self.assertFalse(L.curvature_modulation)

        r2 = apply_reflexive_actions(report, L)
        self.assertFalse(r2.any_changes)
        self.assertIn("curvature", r2.skipped)

    def test_summary_format_no_crash(self):
        """Summary works for all combinations."""
        for actions, skipped in [
            ([], []),
            ([ReflexiveAction("curvature", "curvature_modulation",
                              True, False, "test")], []),
            ([], ["overlap"]),
            ([ReflexiveAction("curvature", "curvature_modulation",
                              True, False, "test")], ["overlap"]),
        ]:
            r = ReflexiveActionResult(actions_taken=actions, skipped=skipped)
            s = r.summary()
            self.assertIsInstance(s, str)
            self.assertTrue(len(s) > 0)


if __name__ == "__main__":
    unittest.main()
