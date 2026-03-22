"""
Tests for E₀ Reflection Layer (Phase 3g)
==========================================
Unit tests for ReflectionDecision, ReflectionReport,
should_reflect(), reflect(), and formatting.
"""

import unittest
from e0_controller.evaluation import (
    RunEvaluation,
    SemanticEvaluation,
    ScenarioEvaluation,
)
from e0_controller.reflection import (
    ReflectionDecision,
    ReflectionReport,
    should_reflect,
    reflect,
    format_reflection_report,
)


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


def _make_sem_eval(coverage=1.0, missing=None, grounding=0, uncertainty=0):
    return SemanticEvaluation(
        required_outputs_covered=coverage,
        missing_outputs=missing or [],
        grounding_warnings=grounding,
        uncertainty_marks=uncertainty,
        completeness_score=coverage * 0.8,
    )


def _make_scenario_eval(
    run_eval=None, sem_eval=None,
    hard_failure=None, graph_score=0.85,
    overall_score=0.80,
):
    if run_eval is None:
        run_eval = _make_run_eval()
    return ScenarioEvaluation(
        scenario_id="test_001",
        domain="test_domain",
        graph_score=graph_score,
        run_evaluation=run_eval,
        semantic_evaluation=sem_eval,
        hard_failure=hard_failure,
        overall_score=overall_score,
    )


# ──────────────────────────────────────────────
# Test: should_reflect — Failure Triggers
# ──────────────────────────────────────────────

class TestFailureTriggers(unittest.TestCase):

    def test_hard_failure_triggers(self):
        ev = _make_scenario_eval(hard_failure="Graph: goal not reachable")
        dec = should_reflect(ev)
        self.assertTrue(dec.reflect)
        self.assertEqual(dec.reflection_type, "failure")
        self.assertEqual(dec.priority, "high")

    def test_goal_not_reached_triggers(self):
        run = _make_run_eval(goal_reached=False, rating="F")
        ev = _make_scenario_eval(run_eval=run)
        dec = should_reflect(ev)
        self.assertTrue(dec.reflect)
        self.assertEqual(dec.reflection_type, "failure")

    def test_severe_loop_triggers(self):
        run = _make_run_eval(repeated_cycles=5, loop_penalty=0.4, rating="C")
        ev = _make_scenario_eval(run_eval=run)
        dec = should_reflect(ev)
        self.assertTrue(dec.reflect)
        self.assertEqual(dec.reflection_type, "failure")
        self.assertIn("loop", dec.reason.lower())


# ──────────────────────────────────────────────
# Test: should_reflect — Quality Triggers
# ──────────────────────────────────────────────

class TestQualityTriggers(unittest.TestCase):

    def test_low_efficiency_triggers(self):
        run = _make_run_eval(efficiency=0.3, rating="C")
        ev = _make_scenario_eval(run_eval=run)
        dec = should_reflect(ev)
        self.assertTrue(dec.reflect)
        self.assertEqual(dec.reflection_type, "quality")
        self.assertEqual(dec.priority, "medium")

    def test_weak_semantic_coverage_triggers(self):
        run = _make_run_eval(efficiency=0.6, rating="B")
        sem = _make_sem_eval(coverage=0.4, missing=["risks", "actions"])
        ev = _make_scenario_eval(run_eval=run, sem_eval=sem)
        dec = should_reflect(ev)
        self.assertTrue(dec.reflect)
        self.assertEqual(dec.reflection_type, "quality")
        self.assertIn("semantic", dec.reason.lower())

    def test_high_escalation_triggers(self):
        run = _make_run_eval(escalations=4, steps=5, efficiency=0.6, rating="C")
        ev = _make_scenario_eval(run_eval=run)
        dec = should_reflect(ev)
        self.assertTrue(dec.reflect)
        self.assertEqual(dec.reflection_type, "quality")

    def test_low_progress_triggers(self):
        run = _make_run_eval(progress_ratio=0.3, efficiency=0.6, rating="C")
        ev = _make_scenario_eval(run_eval=run)
        dec = should_reflect(ev)
        self.assertTrue(dec.reflect)
        self.assertEqual(dec.reflection_type, "quality")


# ──────────────────────────────────────────────
# Test: should_reflect — Opportunity Triggers
# ──────────────────────────────────────────────

class TestOpportunityTriggers(unittest.TestCase):

    def test_perfect_run_triggers_opportunity(self):
        run = _make_run_eval(rating="A", efficiency=1.0)
        sem = _make_sem_eval(coverage=1.0, uncertainty=2)
        ev = _make_scenario_eval(run_eval=run, sem_eval=sem, graph_score=0.95)
        dec = should_reflect(ev)
        self.assertTrue(dec.reflect)
        self.assertEqual(dec.reflection_type, "opportunity")
        self.assertEqual(dec.priority, "low")

    def test_high_efficiency_alone_triggers(self):
        run = _make_run_eval(rating="B", efficiency=0.9)
        ev = _make_scenario_eval(run_eval=run)
        dec = should_reflect(ev)
        self.assertTrue(dec.reflect)
        self.assertEqual(dec.reflection_type, "opportunity")


# ──────────────────────────────────────────────
# Test: should_reflect — No Trigger
# ──────────────────────────────────────────────

class TestNoTrigger(unittest.TestCase):

    def test_mediocre_run_no_trigger(self):
        # B-rated, medium efficiency, no extremes
        run = _make_run_eval(
            rating="B", efficiency=0.6, progress_ratio=0.7,
            escalations=0, loop_penalty=0.0,
        )
        sem = _make_sem_eval(coverage=0.8)
        ev = _make_scenario_eval(run_eval=run, sem_eval=sem, graph_score=0.75)
        dec = should_reflect(ev)
        self.assertFalse(dec.reflect)


# ──────────────────────────────────────────────
# Test: reflect() — Full Pipeline
# ──────────────────────────────────────────────

class TestReflect(unittest.TestCase):

    def test_failure_reflection_has_actions(self):
        run = _make_run_eval(
            goal_reached=False, repeated_cycles=3, loop_penalty=0.3,
            rating="F", efficiency=0.0, progress_ratio=0.3,
        )
        ev = _make_scenario_eval(run_eval=run, hard_failure="Goal not reached")
        report = reflect(ev)
        self.assertIsNotNone(report)
        self.assertEqual(report.reflection_type, "failure")
        self.assertTrue(len(report.observed_patterns) > 0)
        self.assertTrue(len(report.recommended_actions) > 0)

    def test_quality_reflection_identifies_layers(self):
        run = _make_run_eval(
            efficiency=0.25, loop_penalty=0.2, repeated_cycles=2,
            escalations=3, steps=6, rating="C",
        )
        sem = _make_sem_eval(coverage=0.5, missing=["actions"], grounding=2)
        ev = _make_scenario_eval(run_eval=run, sem_eval=sem)
        report = reflect(ev)
        self.assertIsNotNone(report)
        self.assertEqual(report.reflection_type, "quality")
        self.assertTrue(len(report.likely_layers) > 0)

    def test_opportunity_reflection_has_preservations(self):
        run = _make_run_eval(
            rating="A", efficiency=1.0, escalations=0,
            repeated_cycles=0, steps=4,
        )
        sem = _make_sem_eval(coverage=1.0, uncertainty=3)
        ev = _make_scenario_eval(
            run_eval=run, sem_eval=sem, graph_score=0.95)
        report = reflect(ev)
        self.assertIsNotNone(report)
        self.assertEqual(report.reflection_type, "opportunity")
        self.assertTrue(len(report.preservations) > 0)

    def test_no_trigger_returns_none(self):
        run = _make_run_eval(
            rating="B", efficiency=0.6, progress_ratio=0.7,
        )
        sem = _make_sem_eval(coverage=0.8)
        ev = _make_scenario_eval(run_eval=run, sem_eval=sem, graph_score=0.75)
        report = reflect(ev)
        self.assertIsNone(report)


# ──────────────────────────────────────────────
# Test: Report Formatting
# ──────────────────────────────────────────────

class TestFormatting(unittest.TestCase):

    def test_single_report_renders(self):
        report = ReflectionReport(
            reflection_type="failure",
            observed_patterns=["Goal not reached", "3 repeated cycles"],
            likely_layers=["graph_design", "controller"],
            evidence=["loop_penalty=0.30"],
            recommended_actions=["Add cycle breaker"],
        )
        text = format_reflection_report([report], domains=["Incident"])
        self.assertIn("Reflection Layer Report", text)
        self.assertIn("Incident", text)
        self.assertIn("FAILURE", text)
        self.assertIn("Add cycle breaker", text)

    def test_multi_report_has_summary(self):
        r1 = ReflectionReport(
            reflection_type="failure",
            observed_patterns=["fail"],
            recommended_actions=["fix"],
        )
        r2 = ReflectionReport(
            reflection_type="opportunity",
            observed_patterns=["strong"],
            preservations=["keep this"],
        )
        text = format_reflection_report([r1, r2], domains=["A", "B"])
        self.assertIn("Reflection Summary", text)
        self.assertIn("failure: 1", text)
        self.assertIn("opportunity: 1", text)

    def test_empty_reports_list(self):
        text = format_reflection_report([])
        self.assertIn("Reflection Layer Report", text)


if __name__ == "__main__":
    unittest.main()
