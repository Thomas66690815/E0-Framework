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


def _has_openai() -> bool:
    """Check if the openai package is importable."""
    try:
        import openai  # noqa: F401
        return True
    except ImportError:
        return False


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


def _can_run_llm() -> bool:
    """True only if both openai is installed and an API key is available."""
    return _has_openai() and _has_api_key()


SKIP_MSG = "openai package or OPENAI_API_KEY not available — skipping live LLM tests"

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

@unittest.skipUnless(_can_run_llm(), SKIP_MSG)
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

@unittest.skipUnless(_can_run_llm(), SKIP_MSG)
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

@unittest.skipUnless(_can_run_llm(), SKIP_MSG)
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

@unittest.skipUnless(_can_run_llm(), SKIP_MSG)
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

@unittest.skipUnless(_can_run_llm(), SKIP_MSG)
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
            hybrid_geometry="goal_reaching",
        )
        cls.trace = cls.ctrl.run(start=START, goal=GOAL, max_cycles=30)

    def test_hybrid_goal_reached(self):
        """Hybrid controller reaches the goal (LLM-dependent, may be flaky)."""
        self.assertTrue(
            GOAL in self.trace.path,
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


# ──────────────────────────────────────────────
# Test Class 6: Multi-Goal Landscape Bootstrapping
# ──────────────────────────────────────────────

GOAL2 = "ALTERNATIVE_DELIVERED"
MULTI_TASK = (
    "Analyze a competitor's product announcement and produce EITHER a structured "
    "briefing for the executive team OR an alternative quick summary for the "
    "engineering team, depending on which path is more feasible."
)

@unittest.skipUnless(_can_run_llm(), SKIP_MSG)
class TestLiveMultiGoalLandscape(unittest.TestCase):
    """LLM builds a landscape with multiple goal states."""

    @classmethod
    def setUpClass(cls):
        cls.config = _build_config()
        cls.adapter = E0LLMAdapter(config=cls.config)
        cls.scenario = _load_scenario()
        sc_block = cls.scenario.as_prompt_block() if cls.scenario else ""
        cls.all_goals = {GOAL, GOAL2}
        cls.proposal = cls.adapter.build_landscape(
            MULTI_TASK, START, GOAL, goals=cls.all_goals,
            scenario_block=sc_block,
        )
        cls.landscape = materialize_landscape(cls.proposal)

    def test_both_goals_in_landscape(self):
        """Both goal states are present in the landscape."""
        for g in self.all_goals:
            self.assertIn(g, self.landscape.states,
                          f"Goal {g} not in landscape states")

    def test_start_present(self):
        """Start state is present."""
        self.assertIn(START, self.landscape.states)

    def test_at_least_one_goal_reachable(self):
        """At least one goal must be reachable from start."""
        from e0_controller.graph_validation import goal_reachable
        any_reachable = any(
            goal_reachable(self.landscape, START, g) for g in self.all_goals
        )
        self.assertTrue(any_reachable,
                        "No goal is reachable from start in multi-goal landscape")

    def test_proposal_has_edges(self):
        """LLM proposes at least 4 edges."""
        self.assertGreaterEqual(len(self.proposal.edges), 4)


# ──────────────────────────────────────────────
# Test Class 7: Multi-Goal Hybrid Run
# ──────────────────────────────────────────────

@unittest.skipUnless(_can_run_llm(), SKIP_MSG)
class TestLiveMultiGoalHybridRun(unittest.TestCase):
    """Hybrid controller with multi-goal reaches one of the goals via LLM."""

    @classmethod
    def setUpClass(cls):
        cls.config = _build_config()
        cls.adapter = E0LLMAdapter(config=cls.config)
        cls.scenario = _load_scenario()
        sc_block = cls.scenario.as_prompt_block() if cls.scenario else ""
        cls.all_goals = {GOAL, GOAL2}

        cls.proposal = cls.adapter.build_landscape(
            MULTI_TASK, START, GOAL, goals=cls.all_goals,
            scenario_block=sc_block,
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
            hybrid_horizon=3,
            hybrid_goals=cls.all_goals,
            hybrid_geometry="goal_reaching",
        )
        cls.trace = cls.ctrl.run(start=START, goal=GOAL, max_cycles=20)

    def test_reaches_a_goal(self):
        """Hybrid controller reaches one of the goal states."""
        self.assertIn(
            self.trace.path[-1], {GOAL, GOAL2},
            f"Hybrid did not reach any goal. Path: {' → '.join(self.trace.path)}"
        )

    def test_has_overlay_data(self):
        """At least one step carries amplitude overlay data."""
        overlay_count = sum(
            1 for s in self.trace.steps if s.overlay is not None
        )
        self.assertGreater(overlay_count, 0,
                           "No overlay data — multi-goal hybrid was inactive")

    def test_path_not_trivial(self):
        """Path has at least 2 entries (start + goal)."""
        self.assertGreaterEqual(len(self.trace.path), 2)

    def test_result_log_matches_steps(self):
        """Result log has one entry per step."""
        self.assertEqual(len(self.result_log), len(self.trace.steps))


# ──────────────────────────────────────────────
# Test Class 7: Beipackzettel Provenance (Live LLM)
# ──────────────────────────────────────────────

BEIPACKZETTEL_TEXT = """\
Ibuprofen 400 mg Filmtabletten.
Wirkstoff: Ibuprofen.

Anwendungsgebiete: Leichte bis mäßig starke Schmerzen wie Kopfschmerzen,
Zahnschmerzen, Regelschmerzen. Fieber.

Dosierung: Erwachsene und Jugendliche ab 12 Jahren: 1 Tablette (400 mg)
alle 6-8 Stunden. Maximale Tagesdosis: 1200 mg (3 Tabletten).
Bei unzureichender Wirkung NICHT die Dosis eigenmächtig erhöhen.

Gegenanzeigen: Überempfindlichkeit gegen Ibuprofen oder andere NSAR.
Bestehende Magen-Darm-Geschwüre. Schwere Leber- oder Niereninsuffizienz.
Letztes Drittel der Schwangerschaft.

Wechselwirkungen: ASS (Acetylsalicylsäure): Ibuprofen kann die
thrombozytenaggregationshemmende Wirkung von ASS abschwächen.
Gleichzeitige Anwendung erhöht das Risiko gastrointestinaler Blutungen.

Nebenwirkungen:
Häufig (1-10%): Magen-Darm-Beschwerden, Übelkeit, Sodbrennen.
Gelegentlich (0.1-1%): Magengeschwür, Magenblutung.
Selten (<0.1%): Schwere Hautreaktionen, Niereninsuffizienz.
Sehr selten (<0.01%): Kardiovaskuläre Ereignisse bei Langzeitanwendung.
"""

BEIPACKZETTEL_START = "KOPFSCHMERZ"
BEIPACKZETTEL_GOAL = "GESUND"


@unittest.skipUnless(_can_run_llm(), SKIP_MSG)
class TestLiveProvenanceBeipackzettel(unittest.TestCase):
    """Live LLM pipeline with full provenance chain.

    This is the non-circular validation:
    - The LLM reads a real Beipackzettel and generates the landscape
    - Every step is recorded in a ProvenanceLog
    - The provenance log is saved as JSON for external review
    - A third party can verify: prompt → response → landscape → result
    """

    @classmethod
    def setUpClass(cls):
        from e0_controller.provenance import ProvenanceLog

        cls.log = ProvenanceLog(source_id="beipackzettel-ibuprofen-live")
        cls.log.record_input(BEIPACKZETTEL_TEXT)

        config = LLMConfig(model="gpt-5.4-mini", temperature=0.2, max_tokens=2048)
        cls.adapter = E0LLMAdapter(config=config, provenance=cls.log)

        cls.proposal = cls.adapter.build_landscape(
            task=BEIPACKZETTEL_TEXT,
            start=BEIPACKZETTEL_START,
            goal=BEIPACKZETTEL_GOAL,
        )
        cls.landscape = materialize_landscape(cls.proposal)
        cls.log.record_landscape(
            cls.landscape, BEIPACKZETTEL_START, BEIPACKZETTEL_GOAL,
        )

        cls.task_map = task_map_from_proposal(cls.proposal)
        cls.result_log: list[TransitionResult] = []
        execute_fn = cls.adapter.as_execute_fn(
            cls.task_map, result_log=cls.result_log,
        )

        # Run 1: goal_reaching geometry
        cls.ctrl_goal = E0Controller(
            cls.landscape, execute_fn,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=4,
            hybrid_goals={BEIPACKZETTEL_GOAL},
            hybrid_geometry="goal_reaching",
        )
        cls.trace_goal = cls.ctrl_goal.run(
            start=BEIPACKZETTEL_START,
            goal=BEIPACKZETTEL_GOAL,
            max_cycles=20,
        )
        cls.log.record_run(cls.trace_goal, {
            "goal": BEIPACKZETTEL_GOAL,
            "hybrid_geometry": "goal_reaching",
            "hybrid_mode": "amplitude_on_disagree",
            "hybrid_horizon": 4,
        })

        # Run 2: simple geometry (same landscape, different geometry)
        cls.result_log_simple: list[TransitionResult] = []
        execute_fn_simple = cls.adapter.as_execute_fn(
            cls.task_map, result_log=cls.result_log_simple,
        )
        cls.ctrl_simple = E0Controller(
            cls.landscape, execute_fn_simple,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=4,
            hybrid_goals={BEIPACKZETTEL_GOAL},
            hybrid_geometry="simple",
        )
        cls.trace_simple = cls.ctrl_simple.run(
            start=BEIPACKZETTEL_START,
            goal=BEIPACKZETTEL_GOAL,
            max_cycles=20,
        )
        cls.log.record_run(cls.trace_simple, {
            "goal": BEIPACKZETTEL_GOAL,
            "hybrid_geometry": "simple",
            "hybrid_mode": "amplitude_on_disagree",
            "hybrid_horizon": 4,
        })

        # Evaluation
        goal_reached_gr = BEIPACKZETTEL_GOAL in cls.trace_goal.path
        goal_reached_simple = BEIPACKZETTEL_GOAL in cls.trace_simple.path
        cls.log.record_evaluation({
            "goal_reached_goal_reaching": goal_reached_gr,
            "goal_reached_simple": goal_reached_simple,
            "path_goal_reaching": cls.trace_goal.path,
            "path_simple": cls.trace_simple.path,
            "geometry_difference_observed": goal_reached_gr != goal_reached_simple,
            "llm_model": config.model,
        })

        # Save provenance log
        import tempfile
        cls._provenance_dir = os.path.join(
            os.path.dirname(__file__), "..", "provenance",
        )
        os.makedirs(cls._provenance_dir, exist_ok=True)
        cls._provenance_path = os.path.join(
            cls._provenance_dir, "beipackzettel_live.json",
        )
        cls.log.save(cls._provenance_path)

    def test_provenance_chain_complete(self):
        """All 6 stages recorded."""
        self.assertTrue(self.log.chain_complete(),
                        self.log.chain_summary())

    def test_llm_call_recorded(self):
        """At least one LLM call was recorded with full prompt."""
        self.assertGreaterEqual(len(self.log.llm_calls), 1)
        call = self.log.llm_calls[0]
        self.assertIn("E₀", call.system_prompt)
        self.assertIn("Ibuprofen", call.user_prompt)
        self.assertTrue(len(call.raw_response) > 50)

    def test_proposal_has_states_and_edges(self):
        """LLM-generated proposal is structurally valid."""
        self.assertGreaterEqual(self.log.proposal.state_count, 5)
        self.assertGreaterEqual(self.log.proposal.edge_count, 6)

    def test_landscape_has_start_and_goal(self):
        """Materialized landscape includes start and goal."""
        self.assertEqual(self.log.landscape.start, BEIPACKZETTEL_START)
        self.assertEqual(self.log.landscape.goal, BEIPACKZETTEL_GOAL)
        self.assertTrue(self.log.landscape.goal_reachable)

    def test_goal_reaching_succeeds(self):
        """goal_reaching geometry finds the therapeutic goal."""
        self.assertIn(
            BEIPACKZETTEL_GOAL, self.trace_goal.path,
            f"goal_reaching failed. Path: {' → '.join(self.trace_goal.path)}",
        )

    def test_two_runs_recorded(self):
        """Both geometry runs are in the provenance log."""
        self.assertEqual(len(self.log.runs), 2)
        geos = [r.controller_config["hybrid_geometry"] for r in self.log.runs]
        self.assertIn("goal_reaching", geos)
        self.assertIn("simple", geos)

    def test_provenance_log_saved(self):
        """Provenance log was written to disk as valid JSON."""
        self.assertTrue(os.path.exists(self._provenance_path))
        from e0_controller.provenance import ProvenanceLog
        restored = ProvenanceLog.load(self._provenance_path)
        self.assertTrue(restored.chain_complete())
        self.assertEqual(restored.source_id, "beipackzettel-ibuprofen-live")

    def test_evaluation_contains_geometry_comparison(self):
        """Evaluation records both geometry outcomes."""
        findings = self.log.evaluation.findings
        self.assertIn("goal_reached_goal_reaching", findings)
        self.assertIn("goal_reached_simple", findings)
        self.assertIn("path_goal_reaching", findings)
        self.assertIn("path_simple", findings)

    def test_input_fingerprinted(self):
        """Input text has a stable SHA-256 fingerprint."""
        import hashlib
        expected = hashlib.sha256(BEIPACKZETTEL_TEXT.encode()).hexdigest()
        self.assertEqual(self.log.input.sha256, expected)


if __name__ == "__main__":
    unittest.main()
