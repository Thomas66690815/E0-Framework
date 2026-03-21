"""
E₀ LLM Adapter — Unit Tests (Mock-based)
==========================================
Tests use a mock LLM call function — no API key required.
"""

from __future__ import annotations

import json
import unittest

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller
from e0_controller.memory_os import E0MemoryOS
from e0_controller.llm_adapter import (
    E0LLMAdapter,
    LLMConfig,
    LLMResponseError,
    DeltaEstimate,
    ProposedState,
    TransitionResult,
    ResistanceEstimate,
    LandscapeProposal,
    _parse_json_response,
    _normalize_state_name,
    materialize_landscape,
    task_map_from_proposal,
)
from e0_controller.domain_invoice import build_invoice_landscape


# ──────────────────────────────────────────────
# Mock LLM Functions
# ──────────────────────────────────────────────

def mock_delta_call(system: str, user: str, config: LLMConfig) -> str:
    """Returns a fixed delta estimate."""
    return json.dumps({
        "delta": 0.45,
        "reasoning": "Moderate structural change required."
    })


def mock_propose_call(system: str, user: str, config: LLMConfig) -> str:
    """Returns fixed state proposals."""
    return json.dumps({
        "states": [
            {"name": "DATA_VERIFIED", "description": "Data has been verified", "estimated_delta": 0.3},
            {"name": "AMOUNT_MATCHED", "description": "Amount matches PO", "estimated_delta": 0.2},
        ]
    })


def mock_execute_success(system: str, user: str, config: LLMConfig) -> str:
    """Always returns SUCCESS."""
    return json.dumps({
        "outcome": "SUCCESS",
        "result": "Transition completed successfully.",
        "confidence": 0.95,
    })


def mock_execute_failure(system: str, user: str, config: LLMConfig) -> str:
    """Always returns FAILURE."""
    return json.dumps({
        "outcome": "FAILURE",
        "result": "Could not find matching customer.",
        "confidence": 0.3,
    })


def mock_execute_partial(system: str, user: str, config: LLMConfig) -> str:
    """Always returns PARTIAL."""
    return json.dumps({
        "outcome": "PARTIAL",
        "result": "Some data extracted but ambiguous.",
        "confidence": 0.6,
    })


def mock_execute_with_fences(system: str, user: str, config: LLMConfig) -> str:
    """Returns JSON wrapped in markdown fences."""
    return '```json\n{"outcome": "SUCCESS", "result": "Done.", "confidence": 0.9}\n```'


# ──────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────

class TestParseJson(unittest.TestCase):
    """JSON parsing handles various LLM output formats."""

    def test_plain_json(self):
        data = _parse_json_response('{"delta": 0.5}')
        self.assertEqual(data["delta"], 0.5)

    def test_markdown_fenced(self):
        data = _parse_json_response('```json\n{"delta": 0.5}\n```')
        self.assertEqual(data["delta"], 0.5)

    def test_fenced_no_lang(self):
        data = _parse_json_response('```\n{"delta": 0.5}\n```')
        self.assertEqual(data["delta"], 0.5)

    def test_whitespace_tolerance(self):
        data = _parse_json_response('  \n  {"delta": 0.5}  \n  ')
        self.assertEqual(data["delta"], 0.5)

    def test_invalid_json_raises_llm_response_error(self):
        """Broken JSON raises LLMResponseError with raw_response."""
        with self.assertRaises(LLMResponseError) as cm:
            _parse_json_response("this is not json at all")
        self.assertIn("this is not json at all", cm.exception.raw_response)

    def test_empty_string_raises_llm_response_error(self):
        with self.assertRaises(LLMResponseError):
            _parse_json_response("")

    def test_required_keys_pass(self):
        data = _parse_json_response('{"delta": 0.5}', required_keys=["delta"])
        self.assertEqual(data["delta"], 0.5)

    def test_required_keys_missing_raises(self):
        with self.assertRaises(LLMResponseError) as cm:
            _parse_json_response('{"foo": 1}', required_keys=["delta"])
        self.assertIn("delta", str(cm.exception))

    def test_non_object_raises(self):
        """JSON array instead of object → LLMResponseError."""
        with self.assertRaises(LLMResponseError) as cm:
            _parse_json_response('[1, 2, 3]')
        self.assertIn("object", str(cm.exception))


class TestNormalizeStateName(unittest.TestCase):
    """_normalize_state_name handles various LLM outputs."""

    def test_already_upper(self):
        self.assertEqual(_normalize_state_name("DATA_EXTRACTED"), "DATA_EXTRACTED")

    def test_lowercase_to_upper(self):
        self.assertEqual(_normalize_state_name("data extracted"), "DATA_EXTRACTED")

    def test_hyphens_to_underscores(self):
        self.assertEqual(_normalize_state_name("human-review"), "HUMAN_REVIEW")

    def test_extra_whitespace(self):
        self.assertEqual(_normalize_state_name("  AMOUNT OK  "), "AMOUNT_OK")

    def test_multiple_underscores_collapsed(self):
        self.assertEqual(_normalize_state_name("A__B___C"), "A_B_C")


class TestExtractDelta(unittest.TestCase):
    """extract_delta returns structured DeltaEstimate."""

    def setUp(self):
        self.adapter = E0LLMAdapter(call_fn=mock_delta_call)

    def test_basic_delta(self):
        result = self.adapter.extract_delta(
            "DATA_EXTRACTED", "CUSTOMER_FOUND",
            "Look up customer in database")
        self.assertIsInstance(result, DeltaEstimate)
        self.assertAlmostEqual(result.delta, 0.45)
        self.assertIn("structural", result.reasoning.lower())

    def test_delta_clamped_high(self):
        """Delta > 1.0 is clamped to 1.0."""
        def over_one(s, u, c):
            return '{"delta": 1.5, "reasoning": "extreme"}'
        adapter = E0LLMAdapter(call_fn=over_one)
        result = adapter.extract_delta("A", "B", "test")
        self.assertLessEqual(result.delta, 1.0)

    def test_delta_clamped_low(self):
        """Delta < 0.0 is clamped to 0.0."""
        def neg(s, u, c):
            return '{"delta": -0.3, "reasoning": "negative"}'
        adapter = E0LLMAdapter(call_fn=neg)
        result = adapter.extract_delta("A", "B", "test")
        self.assertGreaterEqual(result.delta, 0.0)

    def test_with_memos_summary(self):
        """MemOS summary is forwarded to the prompt."""
        captured = {}
        def capture(system, user, config):
            captured["user"] = user
            return '{"delta": 0.3, "reasoning": "ok"}'
        adapter = E0LLMAdapter(call_fn=capture)
        summary = {"current_state": "X", "admissible_neighbors": {}}
        adapter.extract_delta("X", "Y", "test", memos_summary=summary)
        self.assertIn("X", captured["user"])


class TestProposeStates(unittest.TestCase):
    """propose_states returns structured ProposedState list."""

    def setUp(self):
        self.adapter = E0LLMAdapter(call_fn=mock_propose_call)

    def test_basic_proposal(self):
        result = self.adapter.propose_states(
            "DATA_EXTRACTED",
            "Verify the extracted invoice data")
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], ProposedState)
        self.assertEqual(result[0].name, "DATA_VERIFIED")

    def test_empty_proposal(self):
        """Empty states list is handled gracefully."""
        def empty(s, u, c):
            return '{"states": []}'
        adapter = E0LLMAdapter(call_fn=empty)
        result = adapter.propose_states("X", "test")
        self.assertEqual(result, [])

    def test_invalid_names_filtered(self):
        """State names that don't match UPPER_SNAKE_CASE are skipped."""
        def bad_names(s, u, c):
            return json.dumps({"states": [
                {"name": "good_state", "description": "ok", "estimated_delta": 0.3},
                {"name": "!!!invalid!!!", "description": "bad", "estimated_delta": 0.5},
                {"name": "", "description": "empty", "estimated_delta": 0.1},
            ]})
        adapter = E0LLMAdapter(call_fn=bad_names)
        result = adapter.propose_states("X", "test")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "GOOD_STATE")

    def test_duplicate_names_deduped(self):
        """Duplicate state names (after normalization) are filtered."""
        def dupes(s, u, c):
            return json.dumps({"states": [
                {"name": "DATA_OK", "description": "first", "estimated_delta": 0.3},
                {"name": "data ok", "description": "second", "estimated_delta": 0.4},
            ]})
        adapter = E0LLMAdapter(call_fn=dupes)
        result = adapter.propose_states("X", "test")
        self.assertEqual(len(result), 1)

    def test_delta_clamped_in_proposal(self):
        """estimated_delta > 1.0 is clamped."""
        def over(s, u, c):
            return json.dumps({"states": [
                {"name": "BIG", "description": "over", "estimated_delta": 5.0},
            ]})
        adapter = E0LLMAdapter(call_fn=over)
        result = adapter.propose_states("X", "test")
        self.assertLessEqual(result[0].estimated_delta, 1.0)


class TestExecuteTransition(unittest.TestCase):
    """execute_transition returns structured TransitionResult."""

    def test_success(self):
        adapter = E0LLMAdapter(call_fn=mock_execute_success)
        result = adapter.execute_transition(
            "PDF_LOADED", "DATA_EXTRACTED",
            "Extract invoice data from PDF")
        self.assertIsInstance(result, TransitionResult)
        self.assertEqual(result.outcome, Outcome.SUCCESS)
        self.assertGreater(result.confidence, 0.9)

    def test_failure(self):
        adapter = E0LLMAdapter(call_fn=mock_execute_failure)
        result = adapter.execute_transition(
            "DATA_EXTRACTED", "CUSTOMER_FOUND",
            "Find customer in database")
        self.assertEqual(result.outcome, Outcome.FAILURE)
        self.assertIn("customer", result.result.lower())

    def test_partial(self):
        adapter = E0LLMAdapter(call_fn=mock_execute_partial)
        result = adapter.execute_transition("A", "B", "test")
        self.assertEqual(result.outcome, Outcome.PARTIAL)

    def test_markdown_fences(self):
        """JSON inside markdown fences is parsed correctly."""
        adapter = E0LLMAdapter(call_fn=mock_execute_with_fences)
        result = adapter.execute_transition("A", "B", "test")
        self.assertEqual(result.outcome, Outcome.SUCCESS)

    def test_confidence_clamped(self):
        """Confidence > 1.0 is clamped."""
        def over(s, u, c):
            return '{"outcome": "SUCCESS", "result": "ok", "confidence": 2.5}'
        adapter = E0LLMAdapter(call_fn=over)
        result = adapter.execute_transition("A", "B", "test")
        self.assertLessEqual(result.confidence, 1.0)

    def test_unknown_outcome_defaults_to_failure(self):
        """Unknown outcome string defaults to FAILURE."""
        def bad(s, u, c):
            return '{"outcome": "MAYBE", "result": "unclear", "confidence": 0.5}'
        adapter = E0LLMAdapter(call_fn=bad)
        result = adapter.execute_transition("A", "B", "test")
        self.assertEqual(result.outcome, Outcome.FAILURE)


class TestAsExecuteFn(unittest.TestCase):
    """as_execute_fn returns a controller-compatible callback."""

    def test_basic_callback(self):
        adapter = E0LLMAdapter(call_fn=mock_execute_success)
        task_map = {"PDF_LOADED→DATA_EXTRACTED": "Extract data from PDF"}
        fn = adapter.as_execute_fn(task_map)
        outcome = fn("PDF_LOADED", "DATA_EXTRACTED")
        self.assertEqual(outcome, Outcome.SUCCESS)

    def test_missing_task_uses_default(self):
        """Edge not in task_map gets a default description."""
        captured = {}
        def capture(system, user, config):
            captured["user"] = user
            return '{"outcome": "SUCCESS", "result": "ok", "confidence": 0.9}'
        adapter = E0LLMAdapter(call_fn=capture)
        fn = adapter.as_execute_fn({})
        fn("A", "B")
        self.assertIn("Transition from A to B", captured["user"])

    def test_dynamic_summary_provider(self):
        """summary_provider is called per execute, takes precedence over static."""
        call_count = [0]
        captured_prompts = []

        def capture(system, user, config):
            captured_prompts.append(user)
            return '{"outcome": "SUCCESS", "result": "ok", "confidence": 0.9}'

        def provider():
            call_count[0] += 1
            return {"step": call_count[0], "current_state": f"STATE_{call_count[0]}"}

        adapter = E0LLMAdapter(call_fn=capture)
        fn = adapter.as_execute_fn(
            {"A→B": "test", "B→C": "test2"},
            memos_summary={"should": "be ignored"},
            summary_provider=provider,
        )
        fn("A", "B")
        fn("B", "C")
        self.assertEqual(call_count[0], 2)
        # Dynamic summary used, not static
        self.assertIn("STATE_1", captured_prompts[0])
        self.assertIn("STATE_2", captured_prompts[1])
        self.assertNotIn("be ignored", captured_prompts[0])


class TestControllerIntegration(unittest.TestCase):
    """LLM adapter integrates with Controller + MemOS (all mocked)."""

    def test_full_loop_with_mock(self):
        """Complete: build landscape → controller → mock LLM execute → run."""
        L = build_invoice_landscape()
        adapter = E0LLMAdapter(call_fn=mock_execute_success)

        task_map = {
            "RECEIVED→PDF_LOADED": "Load the PDF file",
            "PDF_LOADED→DATA_EXTRACTED": "Extract invoice data via OCR",
            "DATA_EXTRACTED→CUSTOMER_FOUND": "Look up customer in system",
            "CUSTOMER_FOUND→AMOUNT_OK": "Validate invoice amount",
            "AMOUNT_OK→CONTRACT_MATCH": "Match to contract",
            "CONTRACT_MATCH→POLICY_OK": "Check compliance policies",
            "POLICY_OK→APPROVED": "Approve invoice",
        }
        execute = adapter.as_execute_fn(task_map)

        ctrl = E0Controller(L, execute)
        trace = ctrl.run(start="RECEIVED", goal="APPROVED", max_cycles=15)

        self.assertEqual(trace.path[-1], "APPROVED")
        self.assertGreater(trace.metrics()["success_rate"], 0.9)

    def test_memos_summary_in_loop(self):
        """MemOS summary is generated and usable in the adapter context."""
        import tempfile, shutil
        tmp = tempfile.mkdtemp()
        try:
            L = build_invoice_landscape()
            ctrl = E0Controller(L, lambda s, t: Outcome.SUCCESS)
            trace = ctrl.run(start="RECEIVED", goal="APPROVED", max_cycles=10)

            memos = E0MemoryOS(base_dir=tmp)
            ctx = memos.snapshot_from_runtime("test-llm", L, ctrl, trace)
            memos.save_context(ctx)

            # Generate summary
            summary = memos.summarize_for_llm(ctx, "RECEIVED", landscape=L)
            self.assertIn("current_state", summary)
            self.assertIn("admissible_neighbors", summary)

            # Summary is valid context for adapter
            adapter = E0LLMAdapter(call_fn=mock_execute_success)
            result = adapter.execute_transition(
                "RECEIVED", "PDF_LOADED",
                "Load PDF", memos_summary=summary)
            self.assertEqual(result.outcome, Outcome.SUCCESS)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestLLMConfig(unittest.TestCase):
    """LLMConfig handles API key resolution."""

    def test_explicit_key(self):
        c = LLMConfig(api_key="sk-test-123")
        self.assertEqual(c.resolve_api_key(), "sk-test-123")

    def test_missing_key_raises(self):
        import os
        old = os.environ.pop("OPENAI_API_KEY", None)
        # Temporarily override cwd so .env file is not found
        old_cwd = os.getcwd()
        os.chdir(os.path.dirname(__file__))
        try:
            c = LLMConfig()
            with self.assertRaises(RuntimeError):
                c.resolve_api_key()
        finally:
            os.chdir(old_cwd)
            if old is not None:
                os.environ["OPENAI_API_KEY"] = old


# ──────────────────────────────────────────────
# Phase 3b: estimate_resistance
# ──────────────────────────────────────────────

def mock_resistance_call(system: str, user: str, config: LLMConfig) -> str:
    return json.dumps({"resistance": 1.5, "reasoning": "Hard transition."})


def mock_resistance_negative(system: str, user: str, config: LLMConfig) -> str:
    return json.dumps({"resistance": -0.3, "reasoning": "Negative."})


class TestEstimateResistance(unittest.TestCase):
    """Phase 3b: LLM estimates R₀."""

    def test_basic_resistance(self):
        adapter = E0LLMAdapter(call_fn=mock_resistance_call)
        est = adapter.estimate_resistance("A", "B", "Do something")
        self.assertIsInstance(est, ResistanceEstimate)
        self.assertAlmostEqual(est.resistance, 1.5)
        self.assertEqual(est.reasoning, "Hard transition.")

    def test_negative_floored(self):
        adapter = E0LLMAdapter(call_fn=mock_resistance_negative)
        est = adapter.estimate_resistance("A", "B", "Negative test")
        self.assertGreaterEqual(est.resistance, 0.01)

    def test_missing_key_raises(self):
        def bad_fn(s, u, c):
            return json.dumps({"foo": 1})
        adapter = E0LLMAdapter(call_fn=bad_fn)
        with self.assertRaises(LLMResponseError):
            adapter.estimate_resistance("A", "B", "Test")


# ──────────────────────────────────────────────
# Phase 3b: build_landscape
# ──────────────────────────────────────────────

def mock_build_landscape_call(system: str, user: str, config: LLMConfig) -> str:
    return json.dumps({
        "states": ["START", "MIDDLE", "GOAL", "ERROR"],
        "edges": [
            {"source": "START", "target": "MIDDLE", "delta": 0.4, "resistance": 0.8,
             "description": "First step"},
            {"source": "MIDDLE", "target": "GOAL", "delta": 0.3, "resistance": 0.5,
             "description": "Complete"},
            {"source": "START", "target": "ERROR", "delta": 0.2, "resistance": 2.0,
             "description": "Error path"},
            {"source": "ERROR", "target": "MIDDLE", "delta": 0.5, "resistance": 1.5,
             "description": "Recovery"},
        ],
    })


class TestBuildLandscape(unittest.TestCase):
    """Phase 3b: LLM designs state graphs."""

    def test_basic_build(self):
        adapter = E0LLMAdapter(call_fn=mock_build_landscape_call)
        proposal = adapter.build_landscape("Do a thing", "START", "GOAL")
        self.assertIsInstance(proposal, LandscapeProposal)
        self.assertIn("START", proposal.states)
        self.assertIn("GOAL", proposal.states)
        self.assertEqual(len(proposal.edges), 4)

    def test_materialize(self):
        adapter = E0LLMAdapter(call_fn=mock_build_landscape_call)
        proposal = adapter.build_landscape("Do a thing", "START", "GOAL")
        L = materialize_landscape(proposal)
        self.assertEqual(len(L.states), 4)
        self.assertEqual(L.edge_count(), 4)
        self.assertIsNotNone(L.difference("START", "MIDDLE"))
        self.assertAlmostEqual(L.base_resistance("START", "MIDDLE"), 0.8)

    def test_task_map(self):
        adapter = E0LLMAdapter(call_fn=mock_build_landscape_call)
        proposal = adapter.build_landscape("Do a thing", "START", "GOAL")
        tm = task_map_from_proposal(proposal)
        self.assertIn("START→MIDDLE", tm)
        self.assertEqual(tm["START→MIDDLE"], "First step")

    def test_ensures_start_goal(self):
        """Even if LLM forgets start/goal states, they are added."""
        def missing_fn(s, u, c):
            return json.dumps({
                "states": ["ONLY_ONE"],
                "edges": [],
            })
        adapter = E0LLMAdapter(call_fn=missing_fn)
        proposal = adapter.build_landscape("Task", "MY_START", "MY_GOAL")
        self.assertIn("MY_START", proposal.states)
        self.assertIn("MY_GOAL", proposal.states)

    def test_delta_clamped(self):
        def extreme_fn(s, u, c):
            return json.dumps({
                "states": ["A", "B"],
                "edges": [{"source": "A", "target": "B",
                           "delta": 5.0, "resistance": -1.0}],
            })
        adapter = E0LLMAdapter(call_fn=extreme_fn)
        proposal = adapter.build_landscape("Task", "A", "B")
        self.assertLessEqual(proposal.edges[0]["delta"], 1.0)
        self.assertGreaterEqual(proposal.edges[0]["resistance"], 0.01)

    def test_full_round_trip(self):
        """Build landscape → materialize → run controller."""
        adapter = E0LLMAdapter(call_fn=mock_build_landscape_call)
        proposal = adapter.build_landscape("Do a thing", "START", "GOAL")
        L = materialize_landscape(proposal)
        tm = task_map_from_proposal(proposal)

        # Use success mock for execution
        exec_adapter = E0LLMAdapter(call_fn=mock_execute_success)
        execute_fn = exec_adapter.as_execute_fn(tm)

        ctrl = E0Controller(L, execute_fn)
        trace = ctrl.run(start="START", goal="GOAL", max_cycles=10)

        self.assertIn("GOAL", trace.path)
        self.assertGreater(len(trace.steps), 0)


# ──────────────────────────────────────────────
# Phase 3b: compare_runs
# ──────────────────────────────────────────────

class TestCompareRuns(unittest.TestCase):
    """Phase 3b: MemOS run comparison."""

    def test_compare_basic(self):
        import shutil
        import tempfile
        tmp = tempfile.mkdtemp()
        try:
            memos = E0MemoryOS(base_dir=tmp)
            L = build_invoice_landscape()

            # Run A (mock success)
            def all_success(src, tgt):
                return Outcome.SUCCESS
            ctrl_a = E0Controller(L, all_success, alpha=0.0, recent_k=0)
            trace_a = ctrl_a.run(start="RECEIVED", goal="APPROVED", max_cycles=15)
            memos.save_run("session-a", trace_a, goal="APPROVED")

            # Run B (same landscape, will have same path)
            ctrl_b = E0Controller(L, all_success, alpha=0.0, recent_k=0)
            trace_b = ctrl_b.run(start="RECEIVED", goal="APPROVED", max_cycles=15)
            memos.save_run("session-b", trace_b, goal="APPROVED")

            result = memos.compare_runs("session-a", "session-b")
            self.assertIn("comparison", result)
            self.assertTrue(result["comparison"]["path_identical"])
            self.assertEqual(result["comparison"]["step_difference"], 0)
            self.assertAlmostEqual(result["comparison"]["path_jaccard"], 1.0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_compare_empty_session(self):
        import shutil
        import tempfile
        tmp = tempfile.mkdtemp()
        try:
            memos = E0MemoryOS(base_dir=tmp)
            result = memos.compare_runs("nonexistent-a", "nonexistent-b")
            self.assertEqual(result["a"]["steps"], 0)
            self.assertEqual(result["b"]["steps"], 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
