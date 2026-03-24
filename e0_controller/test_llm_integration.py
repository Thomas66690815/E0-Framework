"""
E₀ LLM Integration Tests (Phase 3q)
=====================================
Live LLM tests that validate the full pipeline against the OpenAI API.

These tests are SKIPPED unless OPENAI_API_KEY is set in the environment
or in a .env file.  They make real API calls and verify:

  1. Landscape bootstrapping returns a valid, connected graph
  2. Transition execution produces parseable, sensible results
  3. Semantic coverage > 0% against a scenario packet
  4. Full controller run reaches the goal
  5. Evaluation rating ≥ C on a live run
  6. Hybrid mode also reaches goal with overlay data

Run:
    # Only runs if OPENAI_API_KEY is available:
    python -m unittest e0_controller.test_llm_integration -v

    # Explicit:
    OPENAI_API_KEY=sk-... python -m unittest e0_controller.test_llm_integration -v
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

from e0_controller.llm_adapter import (
    E0LLMAdapter,
    LLMConfig,
    LandscapeProposal,
    TransitionResult,
    materialize_landscape,
    task_map_from_proposal,
)
from e0_controller.graph_validation import graph_quality
from e0_controller.controller import E0Controller, HybridMode
from e0_controller.evaluation import evaluate_scenario, evaluate_semantics
from e0_controller.scenario_loader import load_scenario, find_scenario, ScenarioPacket


def _has_api_key() -> bool:
    """Check if an OpenAI API key is available."""
    if os.environ.get("OPENAI_API_KEY"):
        return True
    env_path = os.path.join(os.getcwd(), ".env")
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("OPENAI_API_KEY="):
                    val = line.strip().split("=", 1)[1].strip()
                    if val:
                        return True
    return False


SKIP_MSG = "OPENAI_API_KEY not available — skipping live LLM tests"

# ──────────────────────────────────────────────
# Scenario & config
# ──────────────────────────────────────────────

TASK = (
    "Analyze a competitor's product announcement and produce a structured "
    "briefing for the executive team."
)
START = "RAW_ANNOUNCEMENT"
GOAL = "BRIEFING_DELIVERED"


def _load_scenario() -> ScenarioPacket | None:
    """Try to load the competitor-brief scenario."""
    path = find_scenario("competitor_brief")
    if path:
        return load_scenario(path)
    return None


def _build_config() -> LLMConfig:
    return LLMConfig(model="gpt-5.4-mini", temperature=0.2)


# ──────────────────────────────────────────────
# Test Class 1: Landscape Bootstrapping
# ──────────────────────────────────────────────

@unittest.skipUnless(_has_api_key(), SKIP_MSG)
class TestLiveLandscapeBootstrap(unittest.TestCase):
    """LLM builds a valid landscape from a task description."""

    @classmethod
    def setUpClass(cls):
        cls.config = _build_config()
        cls.adapter = E0LLMAdapter(config=cls.config)
        cls.scenario = _load_scenario()
        sc_block = cls.scenario.as_prompt_block() if cls.scenario else ""
        cls.proposal = cls.adapter.build_landscape(
            TASK, START, GOAL, scenario_block=sc_block,
        )
        cls.landscape = materialize_landscape(cls.proposal)
        cls.gq = graph_quality(cls.landscape, START, GOAL)

    def test_proposal_has_states(self):
        """LLM proposes at least 4 states."""
        self.assertGreaterEqual(len(self.proposal.states), 4)

    def test_proposal_has_edges(self):
        """LLM proposes at least 4 edges."""
        self.assertGreaterEqual(len(self.proposal.edges), 4)

    def test_start_and_goal_present(self):
        """Start and goal states are in the landscape."""
        self.assertIn(START, self.landscape.states)
        self.assertIn(GOAL, self.landscape.states)

    def test_goal_reachable(self):
        """Goal is reachable from start (critical structural property)."""
        self.assertTrue(self.gq.reachable,
                        "Goal not reachable from start — graph is disconnected")

    def test_happy_path_exists(self):
        """A happy path (shortest path) exists."""
        self.assertIsNotNone(self.gq.happy_path,
                             "No happy path found in LLM-generated landscape")

    def test_graph_quality_score_positive(self):
        """Graph quality score is reasonable (> 0.3)."""
        self.assertGreater(self.gq.score, 0.3)


# ──────────────────────────────────────────────
# Test Class 2: Transition Execution
# ──────────────────────────────────────────────

@unittest.skipUnless(_has_api_key(), SKIP_MSG)
class TestLiveTransitionExecution(unittest.TestCase):
    """LLM can execute individual transitions and return parseable results."""

    @classmethod
    def setUpClass(cls):
        cls.config = _build_config()
        cls.adapter = E0LLMAdapter(config=cls.config)

    def test_execute_returns_valid_outcome(self):
        """execute_transition returns SUCCESS/FAILURE/PARTIAL."""
        from e0_controller.primitives import Outcome
        result = self.adapter.execute_transition(
            source="RAW_ANNOUNCEMENT",
            target="TEXT_PARSED",
            task="Parse the announcement text into structured sections.",
        )
        self.assertIsInstance(result, TransitionResult)
        self.assertIn(result.outcome, [Outcome.SUCCESS, Outcome.FAILURE, Outcome.PARTIAL])

    def test_execute_returns_text(self):
        """execute_transition produces non-empty result text."""
        result = self.adapter.execute_transition(
            source="RAW_ANNOUNCEMENT",
            target="TEXT_PARSED",
            task="Parse the announcement text into structured sections.",
        )
        self.assertTrue(len(result.result) > 0,
                        "LLM returned empty result text")

    def test_confidence_in_range(self):
        """Confidence is clamped to [0, 1]."""
        result = self.adapter.execute_transition(
            source="TEXT_PARSED",
            target="KEY_FACTS_EXTRACTED",
            task="Extract key facts from parsed announcement text.",
        )
        self.assertGreaterEqual(result.confidence, 0.0)
        self.assertLessEqual(result.confidence, 1.0)

    def test_extract_delta_parseable(self):
        """extract_delta returns a float in [0, 1]."""
        delta_est = self.adapter.extract_delta(
            source="RAW_ANNOUNCEMENT",
            target="TEXT_PARSED",
            description="Parse raw text into structured sections.",
        )
        self.assertGreaterEqual(delta_est.delta, 0.0)
        self.assertLessEqual(delta_est.delta, 1.0)
        self.assertIsInstance(delta_est.reasoning, str)

    def test_estimate_resistance_positive(self):
        """estimate_resistance returns a value > 0."""
        res = self.adapter.estimate_resistance(
            source="RAW_ANNOUNCEMENT",
            target="TEXT_PARSED",
            description="Parse raw text into structured sections.",
        )
        self.assertGreater(res.resistance, 0.0)


# ──────────────────────────────────────────────
# Test Class 3: Full Controller Run
# ──────────────────────────────────────────────

@unittest.skipUnless(_has_api_key(), SKIP_MSG)
class TestLiveControllerRun(unittest.TestCase):
    """Full controller run with real LLM reaches the goal."""

    @classmethod
    def setUpClass(cls):
        cls.config = _build_config()
        cls.adapter = E0LLMAdapter(config=cls.config)
        cls.scenario = _load_scenario()
        sc_block = cls.scenario.as_prompt_block() if cls.scenario else ""

        # Build landscape
        cls.proposal = cls.adapter.build_landscape(
            TASK, START, GOAL, scenario_block=sc_block,
        )
        cls.landscape = materialize_landscape(cls.proposal)
        cls.task_map = task_map_from_proposal(cls.proposal)

        # Setup execute function
        cls.result_log: list[TransitionResult] = []
        execute_fn = cls.adapter.as_execute_fn(
            cls.task_map,
            scenario_block=sc_block,
            result_log=cls.result_log,
        )

        # Run controller (greedy mode)
        cls.ctrl = E0Controller(cls.landscape, execute_fn, alpha=2.0, recent_k=3)
        cls.trace = cls.ctrl.run(start=START, goal=GOAL, max_cycles=20)

    def test_goal_reached(self):
        """Controller reaches the goal state."""
        self.assertTrue(
            self.trace.path[-1] == GOAL,
            f"Expected goal {GOAL}, got {self.trace.path[-1]}. "
            f"Path: {' → '.join(self.trace.path)}"
        )

    def test_no_empty_path(self):
        """Path has at least 2 entries (start + goal)."""
        self.assertGreaterEqual(len(self.trace.path), 2)

    def test_success_rate_reasonable(self):
        """Success rate from LLM transitions is at least 50%."""
        metrics = self.trace.metrics()
        self.assertGreaterEqual(metrics["success_rate"], 0.5)

    def test_result_log_matches_steps(self):
        """Result log has one entry per step."""
        self.assertEqual(len(self.result_log), len(self.trace.steps))

    def test_all_results_have_text(self):
        """Every transition result contains non-empty text."""
        for i, res in enumerate(self.result_log):
            self.assertTrue(
                len(res.result) > 0,
                f"Step {i+1} has empty LLM result text",
            )


# ──────────────────────────────────────────────
# Test Class 4: Semantic Evaluation
# ──────────────────────────────────────────────

@unittest.skipUnless(_has_api_key(), SKIP_MSG)
class TestLiveSemanticEvaluation(unittest.TestCase):
    """Evaluation layer produces meaningful ratings from live LLM output."""

    @classmethod
    def setUpClass(cls):
        cls.config = _build_config()
        cls.adapter = E0LLMAdapter(config=cls.config)
        cls.scenario = _load_scenario()
        if cls.scenario is None:
            raise unittest.SkipTest("Scenario file not found")

        sc_block = cls.scenario.as_prompt_block()
        cls.proposal = cls.adapter.build_landscape(
            TASK, START, GOAL, scenario_block=sc_block,
        )
        cls.landscape = materialize_landscape(cls.proposal)
        cls.task_map = task_map_from_proposal(cls.proposal)
        cls.gq = graph_quality(cls.landscape, START, GOAL)

        cls.result_log: list[TransitionResult] = []
        execute_fn = cls.adapter.as_execute_fn(
            cls.task_map,
            scenario_block=sc_block,
            result_log=cls.result_log,
        )

        ctrl = E0Controller(cls.landscape, execute_fn, alpha=2.0, recent_k=3)
        cls.trace = ctrl.run(start=START, goal=GOAL, max_cycles=20)

    def test_semantic_coverage_positive(self):
        """At least some required outputs are covered."""
        sem = evaluate_semantics(self.result_log, self.scenario)
        self.assertGreater(sem.required_outputs_covered, 0.0,
                           f"No required outputs covered. Missing: {sem.missing_outputs}")

    def test_completeness_above_threshold(self):
        """Completeness score > 0.3 (coverage + confidence blend)."""
        sem = evaluate_semantics(self.result_log, self.scenario)
        self.assertGreater(sem.completeness_score, 0.3)

    def test_no_unsupported_claims(self):
        """LLM does not produce markers of unsupported claims."""
        sem = evaluate_semantics(self.result_log, self.scenario)
        self.assertEqual(sem.grounding_warnings, 0,
                         f"Found {sem.grounding_warnings} unsupported claim marker(s)")

    def test_evaluation_rating_at_least_c(self):
        """Overall evaluation rating is A, B, or C (not D or F)."""
        reached = self.trace.path[-1] == GOAL if self.trace.path else False
        metrics = self.trace.metrics()
        ev = evaluate_scenario(
            scenario_id="live_test",
            domain="competitor_brief",
            gq=self.gq,
            path=self.trace.path,
            steps=int(metrics["steps"]),
            escalation_count=int(metrics["escalation_count"]),
            revisit_count=int(metrics["revisit_count"]),
            success_rate=metrics["success_rate"],
            avg_tension=metrics["avg_tension"],
            total_tension=self.trace.total_tension,
            reached_goal=reached,
            result_log=self.result_log,
            scenario=self.scenario,
        )
        self.assertIn(ev.run_evaluation.rating, ["A", "B", "C"],
                      f"Rating {ev.run_evaluation.rating} is below C. "
                      f"Warnings: {ev.run_evaluation.warnings}")

    def test_overall_score_exists(self):
        """If goal reached, overall score is computed (not None)."""
        reached = self.trace.path[-1] == GOAL if self.trace.path else False
        if not reached:
            self.skipTest("Goal not reached — score is None by design")
        metrics = self.trace.metrics()
        ev = evaluate_scenario(
            scenario_id="live_test_score",
            domain="competitor_brief",
            gq=self.gq,
            path=self.trace.path,
            steps=int(metrics["steps"]),
            escalation_count=int(metrics["escalation_count"]),
            revisit_count=int(metrics["revisit_count"]),
            success_rate=metrics["success_rate"],
            avg_tension=metrics["avg_tension"],
            total_tension=self.trace.total_tension,
            reached_goal=reached,
            result_log=self.result_log,
            scenario=self.scenario,
        )
        self.assertIsNotNone(ev.overall_score)
        self.assertGreater(ev.overall_score, 0.0)


# ──────────────────────────────────────────────
# Test Class 5: Hybrid Mode Live Run
# ──────────────────────────────────────────────

@unittest.skipUnless(_has_api_key(), SKIP_MSG)
class TestLiveHybridRun(unittest.TestCase):
    """Hybrid (amplitude) controller also reaches goal with live LLM."""

    @classmethod
    def setUpClass(cls):
        cls.config = _build_config()
        cls.adapter = E0LLMAdapter(config=cls.config)
        cls.scenario = _load_scenario()
        sc_block = cls.scenario.as_prompt_block() if cls.scenario else ""

        cls.proposal = cls.adapter.build_landscape(
            TASK, START, GOAL, scenario_block=sc_block,
        )
        cls.landscape = materialize_landscape(cls.proposal)
        cls.task_map = task_map_from_proposal(cls.proposal)

        cls.result_log: list[TransitionResult] = []
        execute_fn = cls.adapter.as_execute_fn(
            cls.task_map,
            scenario_block=sc_block,
            result_log=cls.result_log,
        )

        cls.ctrl = E0Controller(
            cls.landscape, execute_fn, alpha=2.0, recent_k=3,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_goals={GOAL},
        )
        cls.trace = cls.ctrl.run(start=START, goal=GOAL, max_cycles=20)

    def test_hybrid_goal_reached(self):
        """Hybrid controller reaches the goal."""
        self.assertTrue(
            self.trace.path[-1] == GOAL,
            f"Hybrid did not reach {GOAL}. Path: {' → '.join(self.trace.path)}"
        )

    def test_hybrid_has_overlay_data(self):
        """At least one step has overlay data (amplitude analysis)."""
        overlay_count = sum(
            1 for s in self.trace.steps if s.overlay is not None
        )
        self.assertGreater(overlay_count, 0,
                           "No overlay data found in any step — hybrid was inactive")

    def test_hybrid_metrics_present(self):
        """Trace metrics include hybrid override tracking."""
        metrics = self.trace.metrics()
        self.assertIn("hybrid_override_count", metrics)
        self.assertIn("hybrid_override_rate", metrics)


if __name__ == "__main__":
    unittest.main()
