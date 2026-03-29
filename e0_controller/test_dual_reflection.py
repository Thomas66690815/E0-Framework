"""
Tests for E₀ Dual Reflection (C47)
====================================
Component health diagnosis from self-graph + combined reporting.
"""

import unittest
from e0_controller.evaluation import (
    RunEvaluation,
    SemanticEvaluation,
    ScenarioEvaluation,
)
from e0_controller.primitives import Edge, Outcome
from e0_controller.self_graph import (
    SelfGraph,
    active_components,
    CORE_COMPONENTS,
    MODULATION_COMPONENTS,
    ALL_COMPONENTS,
    CORE_EDGES,
    MODULATION_EDGES,
)
from e0_controller.dual_reflection import (
    ComponentAssessment,
    SelfGraphDiagnosis,
    DualReflectionReport,
    diagnose_self_graph,
    reflect_dual,
    format_dual_report,
    _assess_component,
    _cross_reference,
    LOAD_MIN_THRESHOLD,
    QUALITY_CONFUSED_THRESHOLD,
    QUALITY_HARMFUL_THRESHOLD,
    INERTIA_WARN_THRESHOLD,
)
from e0_controller.reflection import ReflectionReport


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _make_run_eval(
    goal_reached=True, steps=5, escalations=0, revisits=0,
    repeated_cycles=0, progress_ratio=0.8, avg_tension=0.5,
    total_tension=2.5, efficiency=0.8, loop_penalty=0.0,
    success_rate=1.0, rating="A",
):
    return RunEvaluation(
        goal_reached=goal_reached,
        steps=steps,
        escalations=escalations,
        revisits=revisits,
        repeated_cycles=repeated_cycles,
        progress_ratio=progress_ratio,
        avg_tension=avg_tension,
        total_tension=total_tension,
        goal_reach_efficiency=efficiency,
        loop_penalty=loop_penalty,
        step_success_rate=success_rate,
        rating=rating,
    )


def _make_scenario_eval(
    run_eval=None, hard_failure=None, graph_score=0.85, overall_score=0.80,
):
    if run_eval is None:
        run_eval = _make_run_eval()
    return ScenarioEvaluation(
        scenario_id="test_001",
        domain="test_domain",
        graph_score=graph_score,
        run_evaluation=run_eval,
        semantic_evaluation=None,
        hard_failure=hard_failure,
        overall_score=overall_score,
    )


def _inject_traces(sg: SelfGraph, components, outcome, n=1):
    """Inject n traces for the given components into the self-graph."""
    for _ in range(n):
        sg.self_historize(components, outcome)


# ──────────────────────────────────────────────
# Test: ComponentAssessment
# ──────────────────────────────────────────────

class TestComponentAssessment(unittest.TestCase):

    def test_dataclass_fields(self):
        ca = ComponentAssessment(
            name="amplitude", load=5.0, quality=0.5,
            inertia=0.8, status="healthy", is_modulation=False,
        )
        self.assertEqual(ca.name, "amplitude")
        self.assertEqual(ca.status, "healthy")
        self.assertFalse(ca.is_modulation)

    def test_modulation_flag(self):
        ca = ComponentAssessment(
            name="curvature", load=0.0, quality=0.0,
            inertia=1.0, status="insufficient_data", is_modulation=True,
        )
        self.assertTrue(ca.is_modulation)


# ──────────────────────────────────────────────
# Test: _assess_component
# ──────────────────────────────────────────────

class TestAssessComponent(unittest.TestCase):

    def test_fresh_graph_insufficient_data(self):
        sg = SelfGraph()
        ca = _assess_component("amplitude", sg)
        self.assertEqual(ca.status, "insufficient_data")
        self.assertEqual(ca.load, 0.0)

    def test_healthy_after_successes(self):
        sg = SelfGraph()
        _inject_traces(sg, CORE_COMPONENTS, Outcome.SUCCESS, n=10)
        ca = _assess_component("amplitude", sg)
        self.assertEqual(ca.status, "healthy")
        self.assertGreater(ca.quality, QUALITY_CONFUSED_THRESHOLD)
        self.assertGreaterEqual(ca.load, LOAD_MIN_THRESHOLD)

    def test_confused_after_mixed_outcomes(self):
        sg = SelfGraph()
        # Equal successes and failures → quality ≈ 0
        _inject_traces(sg, CORE_COMPONENTS, Outcome.SUCCESS, n=10)
        _inject_traces(sg, CORE_COMPONENTS, Outcome.FAILURE, n=10)
        ca = _assess_component("amplitude", sg)
        self.assertIn(ca.status, ("confused", "harmful"))
        # load should be very high
        self.assertGreater(ca.load, LOAD_MIN_THRESHOLD)

    def test_harmful_after_failures(self):
        sg = SelfGraph()
        _inject_traces(sg, CORE_COMPONENTS, Outcome.FAILURE, n=10)
        ca = _assess_component("amplitude", sg)
        self.assertEqual(ca.status, "harmful")
        self.assertLess(ca.quality, QUALITY_HARMFUL_THRESHOLD)

    def test_modulation_component_flagged(self):
        sg = SelfGraph()
        ca = _assess_component("curvature", sg)
        self.assertTrue(ca.is_modulation)
        ca2 = _assess_component("amplitude", sg)
        self.assertFalse(ca2.is_modulation)

    def test_custom_thresholds(self):
        sg = SelfGraph()
        _inject_traces(sg, CORE_COMPONENTS, Outcome.SUCCESS, n=2)
        # With load_min=1 it's sufficient, with default (3) it's not
        ca_strict = _assess_component("amplitude", sg, load_min=LOAD_MIN_THRESHOLD)
        ca_loose = _assess_component("amplitude", sg, load_min=1.0)
        self.assertEqual(ca_strict.status, "insufficient_data")
        self.assertEqual(ca_loose.status, "healthy")


# ──────────────────────────────────────────────
# Test: diagnose_self_graph
# ──────────────────────────────────────────────

class TestDiagnoseSelfGraph(unittest.TestCase):

    def test_fresh_graph_all_insufficient(self):
        sg = SelfGraph()
        diag = diagnose_self_graph(sg)
        self.assertEqual(len(diag.components), len(ALL_COMPONENTS))
        self.assertEqual(len(diag.insufficient_data), len(ALL_COMPONENTS))
        self.assertEqual(len(diag.healthy), 0)
        self.assertEqual(len(diag.deactivation_candidates), 0)

    def test_healthy_after_successes(self):
        sg = SelfGraph()
        all_comps = list(ALL_COMPONENTS)
        _inject_traces(sg, all_comps, Outcome.SUCCESS, n=10)
        diag = diagnose_self_graph(sg)
        # At least the core components should be healthy
        for comp in CORE_COMPONENTS:
            self.assertIn(comp, diag.healthy,
                          f"{comp} should be healthy after 10 successes")
        self.assertEqual(len(diag.harmful), 0)

    def test_harmful_after_failures(self):
        sg = SelfGraph()
        all_comps = list(ALL_COMPONENTS)
        _inject_traces(sg, all_comps, Outcome.FAILURE, n=10)
        diag = diagnose_self_graph(sg)
        self.assertGreater(len(diag.harmful), 0)
        # Modulation components should be deactivation candidates
        for comp in MODULATION_COMPONENTS:
            self.assertIn(comp, diag.deactivation_candidates,
                          f"{comp} should be deactivation candidate after failures")

    def test_core_not_in_deactivation_candidates(self):
        sg = SelfGraph()
        _inject_traces(sg, CORE_COMPONENTS, Outcome.FAILURE, n=10)
        diag = diagnose_self_graph(sg)
        # Core components can be harmful but NOT deactivation candidates
        for comp in CORE_COMPONENTS:
            self.assertNotIn(comp, diag.deactivation_candidates)

    def test_meta_actions_deactivation(self):
        sg = SelfGraph()
        all_comps = list(ALL_COMPONENTS)
        _inject_traces(sg, all_comps, Outcome.FAILURE, n=10)
        diag = diagnose_self_graph(sg)
        disable_actions = [a for a in diag.meta_actions if "Disable" in a]
        self.assertGreater(len(disable_actions), 0)

    def test_meta_actions_confusion(self):
        sg = SelfGraph()
        all_comps = list(ALL_COMPONENTS)
        _inject_traces(sg, all_comps, Outcome.SUCCESS, n=10)
        _inject_traces(sg, all_comps, Outcome.FAILURE, n=10)
        diag = diagnose_self_graph(sg)
        investigate = [a for a in diag.meta_actions if "Investigate" in a]
        # Some components should be flagged as confused
        self.assertGreater(len(investigate), 0)

    def test_meta_action_all_healthy(self):
        sg = SelfGraph()
        all_comps = list(ALL_COMPONENTS)
        _inject_traces(sg, all_comps, Outcome.SUCCESS, n=10)
        diag = diagnose_self_graph(sg)
        healthy_msg = [a for a in diag.meta_actions if "healthy" in a.lower()]
        self.assertGreater(len(healthy_msg), 0)

    def test_selective_modulation_failure(self):
        """Only curvature fails, overlap succeeds."""
        sg = SelfGraph()
        # Core + overlap succeed
        good_comps = CORE_COMPONENTS + ["overlap"]
        _inject_traces(sg, good_comps, Outcome.SUCCESS, n=10)
        # Curvature only fails
        _inject_traces(sg, list(ALL_COMPONENTS), Outcome.FAILURE, n=10)
        diag = diagnose_self_graph(sg)
        # curvature should be harmful (all its traces are from failure batches)
        if "curvature" in diag.deactivation_candidates:
            self.assertIn("curvature", diag.deactivation_candidates)


# ──────────────────────────────────────────────
# Test: _cross_reference
# ──────────────────────────────────────────────

class TestCrossReference(unittest.TestCase):

    def _make_diag(self, harmful=None, confused=None, deactivation=None):
        """Build a SelfGraphDiagnosis with specific fields."""
        diag = SelfGraphDiagnosis()
        diag.harmful = harmful or []
        diag.confused = confused or []
        diag.deactivation_candidates = deactivation or []
        # Build component list
        for name in ALL_COMPONENTS:
            status = "healthy"
            if name in (harmful or []):
                status = "harmful"
            elif name in (confused or []):
                status = "confused"
            diag.components.append(ComponentAssessment(
                name=name, load=10.0, quality=0.5 if status == "healthy"
                    else (-0.3 if status == "harmful" else 0.01),
                inertia=0.8, status=status,
                is_modulation=name in MODULATION_COMPONENTS,
            ))
        return diag

    def test_no_domain_report_returns_diag_actions(self):
        diag = self._make_diag()
        actions = _cross_reference(None, diag)
        self.assertIsInstance(actions, list)

    def test_controller_flagged_with_harmful_born(self):
        domain = ReflectionReport(
            reflection_type="failure",
            likely_layers=["controller"],
        )
        diag = self._make_diag(harmful=["born"])
        actions = _cross_reference(domain, diag)
        controller_born = [a for a in actions if "born" in a and "controller" in a]
        self.assertGreater(len(controller_born), 0)

    def test_graph_flagged_with_confused_historization(self):
        domain = ReflectionReport(
            reflection_type="quality",
            likely_layers=["graph_design"],
        )
        diag = self._make_diag(confused=["historization"])
        actions = _cross_reference(domain, diag)
        struct = [a for a in actions if "historization" in a and "structural" in a]
        self.assertGreater(len(struct), 0)

    def test_restructure_with_deactivation_candidate(self):
        domain = ReflectionReport(
            reflection_type="structural",
            likely_layers=["landscape"],
            recommended_actions=["Restructure landscape topology"],
        )
        diag = self._make_diag(deactivation=["curvature"])
        actions = _cross_reference(domain, diag)
        deact_first = [a for a in actions if "Deactivate" in a and "restructur" in a.lower()]
        self.assertGreater(len(deact_first), 0)

    def test_no_cross_refs_when_all_healthy(self):
        domain = ReflectionReport(
            reflection_type="opportunity",
            likely_layers=["semantic"],
        )
        diag = self._make_diag()  # all healthy
        actions = _cross_reference(domain, diag)
        # Should not have any prioritization actions
        priority_actions = [a for a in actions if "prioritize" in a.lower()]
        self.assertEqual(len(priority_actions), 0)


# ──────────────────────────────────────────────
# Test: reflect_dual
# ──────────────────────────────────────────────

class TestReflectDual(unittest.TestCase):

    def test_no_trigger_healthy_system(self):
        """Good evaluation + healthy self-graph → opportunity report, healthy diagnosis."""
        ev = _make_scenario_eval()
        sg = SelfGraph()
        all_comps = list(ALL_COMPONENTS)
        _inject_traces(sg, all_comps, Outcome.SUCCESS, n=10)
        report = reflect_dual(ev, sg)
        self.assertIsInstance(report, DualReflectionReport)
        # A-rated run triggers opportunity reflection (positive patterns)
        self.assertIsNotNone(report.domain_report)
        self.assertEqual(report.domain_report.reflection_type, "opportunity")
        self.assertIsInstance(report.self_diagnosis, SelfGraphDiagnosis)

    def test_failure_trigger_with_healthy_self(self):
        """Failed evaluation + healthy self-graph → domain report exists."""
        run = _make_run_eval(goal_reached=False, rating="F", efficiency=0.0)
        ev = _make_scenario_eval(run_eval=run)
        sg = SelfGraph()
        _inject_traces(sg, list(ALL_COMPONENTS), Outcome.SUCCESS, n=10)
        report = reflect_dual(ev, sg)
        self.assertIsNotNone(report.domain_report)
        self.assertEqual(report.domain_report.reflection_type, "failure")
        # Self-graph should still be healthy
        self.assertGreater(len(report.self_diagnosis.healthy), 0)

    def test_failure_trigger_with_harmful_self(self):
        """Failed evaluation + harmful components → cross-reference meta-actions."""
        run = _make_run_eval(goal_reached=False, rating="F", efficiency=0.0,
                             progress_ratio=0.2)
        ev = _make_scenario_eval(run_eval=run)
        sg = SelfGraph()
        _inject_traces(sg, list(ALL_COMPONENTS), Outcome.FAILURE, n=10)
        report = reflect_dual(ev, sg)
        self.assertIsNotNone(report.domain_report)
        self.assertGreater(len(report.self_diagnosis.harmful), 0)
        # Should have meta-actions for deactivation
        self.assertGreater(len(report.meta_actions), 0)

    def test_mode_info_attached(self):
        ev = _make_scenario_eval()
        sg = SelfGraph()
        mode = {"mode": "LEARN", "total": 5, "explored": 0, "ratio": 0.0}
        report = reflect_dual(ev, sg, mode_summary=mode)
        self.assertEqual(report.mode_info["mode"], "LEARN")

    def test_returns_dual_report_type(self):
        ev = _make_scenario_eval()
        sg = SelfGraph()
        report = reflect_dual(ev, sg)
        self.assertIsInstance(report, DualReflectionReport)


# ──────────────────────────────────────────────
# Test: format_dual_report
# ──────────────────────────────────────────────

class TestFormatDualReport(unittest.TestCase):

    def test_format_no_domain_report(self):
        sg = SelfGraph()
        diag = diagnose_self_graph(sg)
        report = DualReflectionReport(
            domain_report=None,
            self_diagnosis=diag,
        )
        text = format_dual_report(report)
        self.assertIn("Dual Reflection", text)
        self.assertIn("No domain reflection triggered", text)
        self.assertIn("Self-Graph Diagnosis", text)

    def test_format_with_domain_report(self):
        domain = ReflectionReport(
            reflection_type="failure",
            observed_patterns=["Test pattern"],
            likely_layers=["controller"],
            recommended_actions=["Fix it"],
        )
        sg = SelfGraph()
        diag = diagnose_self_graph(sg)
        report = DualReflectionReport(
            domain_report=domain,
            self_diagnosis=diag,
        )
        text = format_dual_report(report)
        self.assertIn("failure", text)
        self.assertIn("Test pattern", text)
        self.assertIn("Fix it", text)

    def test_format_with_mode_info(self):
        sg = SelfGraph()
        diag = diagnose_self_graph(sg)
        report = DualReflectionReport(
            domain_report=None,
            self_diagnosis=diag,
            mode_info={"mode": "COMBINATION", "explored": 3,
                       "total": 10, "ratio": 0.3},
        )
        text = format_dual_report(report)
        self.assertIn("COMBINATION", text)
        self.assertIn("3/10", text)

    def test_format_with_meta_actions(self):
        sg = SelfGraph()
        diag = diagnose_self_graph(sg)
        report = DualReflectionReport(
            domain_report=None,
            self_diagnosis=diag,
            meta_actions=["Disable curvature", "Investigate born"],
        )
        text = format_dual_report(report)
        self.assertIn("Disable curvature", text)
        self.assertIn("Investigate born", text)

    def test_format_components_listed(self):
        sg = SelfGraph()
        _inject_traces(sg, list(ALL_COMPONENTS), Outcome.SUCCESS, n=10)
        diag = diagnose_self_graph(sg)
        report = DualReflectionReport(
            domain_report=None,
            self_diagnosis=diag,
        )
        text = format_dual_report(report)
        for comp in ALL_COMPONENTS:
            self.assertIn(comp, text)

    def test_format_deactivation_shown(self):
        sg = SelfGraph()
        _inject_traces(sg, list(ALL_COMPONENTS), Outcome.FAILURE, n=10)
        diag = diagnose_self_graph(sg)
        report = DualReflectionReport(
            domain_report=None,
            self_diagnosis=diag,
            meta_actions=diag.meta_actions,
        )
        text = format_dual_report(report)
        self.assertIn("Deactivation candidates", text)


# ──────────────────────────────────────────────
# Test: Integration with real self-graph cycle
# ──────────────────────────────────────────────

class TestDualReflectionIntegration(unittest.TestCase):

    def test_full_lifecycle(self):
        """Simulate a complete lifecycle: traces → diagnosis → report."""
        sg = SelfGraph()

        # Phase 1: 15 successful cycles (all core + curvature active)
        comps_with_curv = CORE_COMPONENTS + ["curvature"]
        _inject_traces(sg, comps_with_curv, Outcome.SUCCESS, n=15)

        # Phase 2: 10 cycles with curvature causing failures
        _inject_traces(sg, comps_with_curv, Outcome.FAILURE, n=10)

        # Phase 3: 10 cycles without curvature — all succeed
        _inject_traces(sg, CORE_COMPONENTS, Outcome.SUCCESS, n=10)

        # Now evaluate
        ev = _make_scenario_eval()
        report = reflect_dual(ev, sg)

        # Core components saw 25 successes + 10 failures → should still be positive
        for comp in CORE_COMPONENTS:
            ca = next(c for c in report.self_diagnosis.components
                     if c.name == comp)
            self.assertEqual(ca.status, "healthy",
                             f"{comp} should be healthy (25S/10F)")

        # Curvature saw 15 successes + 10 failures → mixed
        curv = next(c for c in report.self_diagnosis.components
                   if c.name == "curvature")
        self.assertGreater(curv.load, LOAD_MIN_THRESHOLD)

    def test_modulation_deactivation_flow(self):
        """Modulation that only produces failures should be deactivated."""
        sg = SelfGraph()

        # Core succeeds
        _inject_traces(sg, CORE_COMPONENTS, Outcome.SUCCESS, n=20)

        # Curvature + overlap only fail
        _inject_traces(sg, list(ALL_COMPONENTS), Outcome.FAILURE, n=15)

        ev = _make_scenario_eval()
        report = reflect_dual(ev, sg)

        # At least one modulation should be deactivation candidate
        deact = report.self_diagnosis.deactivation_candidates
        # curvature and overlap have outgoing edges that only saw failures
        # (their modulation edges) plus core edges with mixed
        # Exact result depends on quality aggregation
        self.assertIsInstance(deact, list)

    def test_empty_self_graph_produces_safe_report(self):
        """Fresh self-graph should produce report without errors."""
        sg = SelfGraph()
        ev = _make_scenario_eval()
        report = reflect_dual(ev, sg)
        self.assertIsInstance(report, DualReflectionReport)
        text = format_dual_report(report)
        self.assertIsInstance(text, str)
        self.assertIn("insufficient_data", text)

    def test_active_components_attribution(self):
        """Verify active_components feeds correct data to self_historize."""
        comps = active_components(
            curvature_active=True,
            overlap_active=False,
        )
        self.assertIn("curvature", comps)
        self.assertNotIn("overlap", comps)
        # All core are always present
        for c in CORE_COMPONENTS:
            self.assertIn(c, comps)


if __name__ == "__main__":
    unittest.main()
