"""
Tests for E₀ Reflection Layer (Phase 3g)
==========================================
Unit tests for ReflectionDecision, ReflectionReport,
should_reflect(), reflect(), and formatting.
"""

import json
import unittest
from e0_controller.evaluation import (
    RunEvaluation,
    SemanticEvaluation,
    ScenarioEvaluation,
)
from e0_controller.llm_adapter import LLMConfig, LLMResponseError, TransitionResult
from e0_controller.primitives import Outcome
from e0_controller.reflection import (
    ReflectionDecision,
    ReflectionReport,
    should_reflect,
    reflect,
    reflect_with_llm,
    format_reflection_report,
    _build_evidence_block,
    _build_result_samples,
    _parse_reflection_response,
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


# ──────────────────────────────────────────────
# Test: LLM Reflection Helpers
# ──────────────────────────────────────────────

class TestBuildEvidenceBlock(unittest.TestCase):

    def test_basic_structure(self):
        ev = _make_scenario_eval()
        text = _build_evidence_block(ev)
        self.assertIn("Domain: test_domain", text)
        self.assertIn("Graph Score: 0.85", text)
        self.assertIn("Run Dynamics:", text)
        self.assertIn("Rating: A", text)
        self.assertIn("Goal Reached: True", text)

    def test_includes_semantic_when_present(self):
        sem = _make_sem_eval(coverage=0.7, missing=["risks"], grounding=1)
        ev = _make_scenario_eval(sem_eval=sem)
        text = _build_evidence_block(ev)
        self.assertIn("Semantic Evaluation:", text)
        self.assertIn("Coverage: 70%", text)
        self.assertIn("Missing: risks", text)

    def test_omits_semantic_when_absent(self):
        ev = _make_scenario_eval(sem_eval=None)
        text = _build_evidence_block(ev)
        self.assertNotIn("Semantic Evaluation:", text)


class TestBuildResultSamples(unittest.TestCase):

    def test_empty_log(self):
        self.assertIn("no transition", _build_result_samples(None))
        self.assertIn("no transition", _build_result_samples([]))

    def test_formats_samples(self):
        log = [
            TransitionResult(outcome=Outcome.SUCCESS, result="Did the thing", confidence=0.9),
            TransitionResult(outcome=Outcome.FAILURE, result="Failed here", confidence=0.3),
        ]
        text = _build_result_samples(log)
        self.assertIn("[1]", text)
        self.assertIn("SUCCESS", text)
        self.assertIn("[2]", text)
        self.assertIn("FAILURE", text)

    def test_truncates_long_result(self):
        log = [TransitionResult(outcome=Outcome.SUCCESS, result="x" * 300, confidence=0.5)]
        text = _build_result_samples(log, max_samples=1)
        self.assertIn("...", text)

    def test_max_samples_respected(self):
        log = [TransitionResult(outcome=Outcome.SUCCESS, result=f"r{i}", confidence=0.5)
               for i in range(10)]
        text = _build_result_samples(log, max_samples=3)
        self.assertIn("[3]", text)
        self.assertNotIn("[4]", text)
        self.assertIn("7 more", text)


class TestParseReflectionResponse(unittest.TestCase):

    def test_valid_json(self):
        data = {
            "observed_patterns": ["loop detected"],
            "likely_layers": ["controller"],
            "evidence": ["cycles=3"],
            "recommended_actions": ["add breaker"],
            "preservations": [],
        }
        report = _parse_reflection_response(json.dumps(data), "failure")
        self.assertEqual(report.reflection_type, "failure")
        self.assertEqual(report.observed_patterns, ["loop detected"])
        self.assertEqual(report.likely_layers, ["controller"])
        self.assertEqual(report.recommended_actions, ["add breaker"])

    def test_json_in_markdown_fence(self):
        inner = json.dumps({"observed_patterns": ["a"], "likely_layers": ["b"],
                            "evidence": [], "recommended_actions": [], "preservations": []})
        raw = f"```json\n{inner}\n```"
        report = _parse_reflection_response(raw, "quality")
        self.assertEqual(report.reflection_type, "quality")
        self.assertEqual(report.observed_patterns, ["a"])

    def test_invalid_json_raises(self):
        with self.assertRaises(LLMResponseError):
            _parse_reflection_response("not json at all", "failure")

    def test_non_dict_raises(self):
        with self.assertRaises(LLMResponseError):
            _parse_reflection_response("[1,2,3]", "failure")

    def test_missing_keys_default_empty(self):
        report = _parse_reflection_response("{}", "opportunity")
        self.assertEqual(report.observed_patterns, [])
        self.assertEqual(report.recommended_actions, [])


# ──────────────────────────────────────────────
# Test: LLM-Backed Reflection
# ──────────────────────────────────────────────

def _mock_llm_response():
    """Return a valid JSON string as an LLM would."""
    return json.dumps({
        "observed_patterns": ["LLM found a loop"],
        "likely_layers": ["controller", "graph_design"],
        "evidence": ["loop_penalty=0.40"],
        "recommended_actions": ["Break the loop"],
        "preservations": [],
    })


class TestReflectWithLLM(unittest.TestCase):

    def test_basic_llm_reflection(self):
        ev = _make_scenario_eval(
            run_eval=_make_run_eval(goal_reached=False, rating="F"),
            hard_failure="Goal not reached",
        )
        decision = ReflectionDecision(
            reflect=True, reason="Hard failure",
            priority="high", reflection_type="failure",
        )
        call_fn = lambda sys, usr, cfg: _mock_llm_response()
        config = LLMConfig()
        report = reflect_with_llm(ev, decision, call_fn, config)
        self.assertEqual(report.reflection_type, "failure")
        self.assertEqual(report.observed_patterns, ["LLM found a loop"])
        self.assertIn("controller", report.likely_layers)

    def test_llm_receives_evidence_in_prompt(self):
        ev = _make_scenario_eval(
            run_eval=_make_run_eval(rating="C", efficiency=0.3),
        )
        decision = ReflectionDecision(
            reflect=True, reason="low efficiency",
            priority="medium", reflection_type="quality",
        )
        captured = {}
        def spy_fn(sys_prompt, user_prompt, cfg):
            captured["system"] = sys_prompt
            captured["user"] = user_prompt
            return _mock_llm_response()

        reflect_with_llm(ev, decision, spy_fn, LLMConfig())
        self.assertIn("E₀ Reflection Layer", captured["system"])
        self.assertIn("quality", captured["user"])
        self.assertIn("Efficiency: 0.30", captured["user"])

    def test_llm_receives_result_samples(self):
        ev = _make_scenario_eval()
        decision = ReflectionDecision(
            reflect=True, reason="test",
            priority="low", reflection_type="opportunity",
        )
        log = [TransitionResult(outcome=Outcome.SUCCESS, result="some output", confidence=0.8)]
        captured = {}
        def spy_fn(sys_prompt, user_prompt, cfg):
            captured["user"] = user_prompt
            return _mock_llm_response()

        reflect_with_llm(ev, decision, spy_fn, LLMConfig(), result_log=log)
        self.assertIn("some output", captured["user"])


class TestReflectWithLLMFallback(unittest.TestCase):

    def test_llm_path_used_when_call_fn_provided(self):
        """reflect() uses LLM when call_fn + config are given."""
        run = _make_run_eval(goal_reached=False, rating="F")
        ev = _make_scenario_eval(run_eval=run, hard_failure="Goal not reached")
        used_llm = {"called": False}

        def mock_fn(sys, usr, cfg):
            used_llm["called"] = True
            return _mock_llm_response()

        report = reflect(ev, call_fn=mock_fn, config=LLMConfig())
        self.assertTrue(used_llm["called"])
        self.assertEqual(report.observed_patterns, ["LLM found a loop"])

    def test_fallback_on_llm_error(self):
        """reflect() falls back to rules when LLM fails."""
        run = _make_run_eval(goal_reached=False, rating="F")
        ev = _make_scenario_eval(run_eval=run, hard_failure="Goal not reached")

        def failing_fn(sys, usr, cfg):
            raise LLMResponseError("API down", raw_response="")

        report = reflect(ev, call_fn=failing_fn, config=LLMConfig())
        self.assertIsNotNone(report)
        self.assertEqual(report.reflection_type, "failure")
        # Rule-based should still find patterns
        self.assertTrue(len(report.observed_patterns) > 0)

    def test_no_call_fn_uses_rules(self):
        """reflect() without call_fn uses rule-based path."""
        run = _make_run_eval(goal_reached=False, rating="F")
        ev = _make_scenario_eval(run_eval=run)
        report = reflect(ev)
        self.assertIsNotNone(report)
        self.assertEqual(report.reflection_type, "failure")

    def test_no_trigger_returns_none_even_with_llm(self):
        """reflect() returns None when no trigger, regardless of LLM."""
        run = _make_run_eval(rating="B", efficiency=0.6, progress_ratio=0.7)
        sem = _make_sem_eval(coverage=0.8)
        ev = _make_scenario_eval(run_eval=run, sem_eval=sem, graph_score=0.75)
        report = reflect(ev, call_fn=lambda s, u, c: _mock_llm_response(), config=LLMConfig())
        self.assertIsNone(report)


if __name__ == "__main__":
    unittest.main()
