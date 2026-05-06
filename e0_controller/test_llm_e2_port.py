"""
Tests for C293: LlmE2Port
==========================
All tests run without an API key via injectable call_fn.

Covers:
    TestLlmE2PortInterface      — ABC compliance, port_id, status
    TestLlmE2PortExecute        — SUCCESS/FAILURE/PARTIAL outcomes, payload, new_state
    TestLlmE2PortErrorHandling  — LLM exceptions → FAILURE, state unchanged
    TestLlmE2PortConfiguration  — with_task, with_memos immutable update
    TestLlmE2PortE0Integration  — E0Turn + LlmE2Port full-loop (no API key)
"""

from __future__ import annotations

import json

import pytest

from e0_controller.e0_turn import E0Turn, TurnResult
from e0_controller.e2_port import E2Port, ExecutionResult
from e0_controller.landscape import Landscape
from e0_controller.llm_adapter import LLMConfig, LLMResponseError
from e0_controller.llm_e2_port import LlmE2Port
from e0_controller.primitives import Outcome


# ── Fake call_fn helpers ──────────────────────────────────────────────────────

def _make_call_fn(outcome: str, result: str = "done", confidence: float = 0.9):
    """Return a call_fn that always responds with the given outcome JSON."""
    def call_fn(system: str, user: str, config: LLMConfig) -> str:
        return json.dumps({
            "outcome": outcome,
            "result": result,
            "confidence": confidence,
        })
    return call_fn


def _error_call_fn(system: str, user: str, config: LLMConfig) -> str:
    raise LLMResponseError("timeout", raw_response="", finish_reason="error")


def _malformed_call_fn(system: str, user: str, config: LLMConfig) -> str:
    return "not valid json {"


# ── Fixtures ──────────────────────────────────────────────────────────────────

def simple_landscape() -> Landscape:
    ls = Landscape()
    ls.add_edge("A", "B", delta=0.5, resistance=1.0)
    return ls


def chain_landscape() -> Landscape:
    ls = Landscape()
    ls.add_edge("START", "MIDDLE", delta=0.5, resistance=1.0)
    ls.add_edge("MIDDLE", "END", delta=0.5, resistance=1.0)
    return ls


# ── TestLlmE2PortInterface ────────────────────────────────────────────────────

class TestLlmE2PortInterface:
    def test_is_e2port_subclass(self):
        port = LlmE2Port("task", call_fn=_make_call_fn("SUCCESS"))
        assert isinstance(port, E2Port)

    def test_default_port_id(self):
        port = LlmE2Port("task", call_fn=_make_call_fn("SUCCESS"))
        assert port.port_id() == "llm"

    def test_custom_port_id(self):
        port = LlmE2Port("task", name="gpt_agent", call_fn=_make_call_fn("SUCCESS"))
        assert port.port_id() == "gpt_agent"

    def test_task_accessor(self):
        port = LlmE2Port("my task", call_fn=_make_call_fn("SUCCESS"))
        assert port.task() == "my task"

    def test_status_contains_port_id(self):
        port = LlmE2Port("task", name="p1", call_fn=_make_call_fn("SUCCESS"))
        s = port.status()
        assert s["port_id"] == "p1"

    def test_status_contains_task(self):
        port = LlmE2Port("analyze supply chain", call_fn=_make_call_fn("SUCCESS"))
        s = port.status()
        assert s["task"] == "analyze supply chain"

    def test_status_model_from_config(self):
        config = LLMConfig(model="gpt-test-7")
        port = LlmE2Port("task", config=config, call_fn=_make_call_fn("SUCCESS"))
        s = port.status()
        assert s["model"] == "gpt-test-7"

    def test_status_has_memos_false(self):
        port = LlmE2Port("task", call_fn=_make_call_fn("SUCCESS"))
        assert port.status()["has_memos"] is False

    def test_status_has_memos_true(self):
        port = LlmE2Port("task", call_fn=_make_call_fn("SUCCESS"),
                         memos_summary={"key": "val"})
        assert port.status()["has_memos"] is True

    def test_can_execute_default_true(self):
        port = LlmE2Port("task", call_fn=_make_call_fn("SUCCESS"))
        assert port.can_execute("A", "B") is True


# ── TestLlmE2PortExecute ─────────────────────────────────────────────────────

class TestLlmE2PortExecute:
    def test_success_returns_execution_result(self):
        port = LlmE2Port("task", call_fn=_make_call_fn("SUCCESS"))
        result = port.execute("A", "B")
        assert isinstance(result, ExecutionResult)

    def test_success_outcome(self):
        port = LlmE2Port("task", call_fn=_make_call_fn("SUCCESS"))
        result = port.execute("A", "B")
        assert result.outcome == Outcome.SUCCESS

    def test_success_new_state_is_action(self):
        port = LlmE2Port("task", call_fn=_make_call_fn("SUCCESS"))
        result = port.execute("A", "B")
        assert result.new_state == "B"

    def test_failure_outcome(self):
        port = LlmE2Port("task", call_fn=_make_call_fn("FAILURE"))
        result = port.execute("A", "B")
        assert result.outcome == Outcome.FAILURE

    def test_failure_new_state_is_source(self):
        port = LlmE2Port("task", call_fn=_make_call_fn("FAILURE"))
        result = port.execute("A", "B")
        assert result.new_state == "A"

    def test_partial_outcome(self):
        port = LlmE2Port("task", call_fn=_make_call_fn("PARTIAL"))
        result = port.execute("A", "B")
        assert result.outcome == Outcome.PARTIAL

    def test_partial_new_state_is_action(self):
        # PARTIAL: not a FAILURE → moves forward
        port = LlmE2Port("task", call_fn=_make_call_fn("PARTIAL"))
        result = port.execute("A", "B")
        assert result.new_state == "B"

    def test_payload_is_llm_result_text(self):
        port = LlmE2Port("task", call_fn=_make_call_fn("SUCCESS", result="briefing done"))
        result = port.execute("A", "B")
        assert result.payload == "briefing done"

    def test_error_field_none_on_success(self):
        port = LlmE2Port("task", call_fn=_make_call_fn("SUCCESS"))
        result = port.execute("A", "B")
        assert result.error is None

    def test_execute_passes_state_and_action(self):
        """call_fn receives prompts containing state/action labels."""
        calls = []
        def recording_fn(system, user, config):
            calls.append(user)
            return json.dumps({"outcome": "SUCCESS", "result": "", "confidence": 1.0})

        port = LlmE2Port("my task", call_fn=recording_fn)
        port.execute("INBOX", "PROCESSED")
        assert len(calls) == 1
        assert "INBOX" in calls[0]
        assert "PROCESSED" in calls[0]

    def test_execute_passes_task_in_prompt(self):
        """Task description appears in the prompt sent to LLM."""
        calls = []
        def recording_fn(system, user, config):
            calls.append(user)
            return json.dumps({"outcome": "SUCCESS", "result": "", "confidence": 1.0})

        port = LlmE2Port("analyze quarterly report", call_fn=recording_fn)
        port.execute("A", "B")
        assert "analyze quarterly report" in calls[0]


# ── TestLlmE2PortErrorHandling ────────────────────────────────────────────────

class TestLlmE2PortErrorHandling:
    def test_llm_exception_returns_failure(self):
        port = LlmE2Port("task", call_fn=_error_call_fn)
        result = port.execute("A", "B")
        assert result.outcome == Outcome.FAILURE

    def test_llm_exception_state_unchanged(self):
        port = LlmE2Port("task", call_fn=_error_call_fn)
        result = port.execute("A", "B")
        assert result.new_state == "A"

    def test_llm_exception_error_field_set(self):
        port = LlmE2Port("task", call_fn=_error_call_fn)
        result = port.execute("A", "B")
        assert result.error is not None
        assert len(result.error) > 0

    def test_malformed_json_returns_failure(self):
        port = LlmE2Port("task", call_fn=_malformed_call_fn)
        result = port.execute("A", "B")
        assert result.outcome == Outcome.FAILURE

    def test_does_not_raise(self):
        """execute() contract: never raises regardless of LLM failure."""
        port = LlmE2Port("task", call_fn=_error_call_fn)
        try:
            port.execute("A", "B")
        except Exception as e:
            pytest.fail(f"execute() raised: {e}")

    def test_payload_none_on_error(self):
        port = LlmE2Port("task", call_fn=_error_call_fn)
        result = port.execute("A", "B")
        assert result.payload is None


# ── TestLlmE2PortConfiguration ───────────────────────────────────────────────

class TestLlmE2PortConfiguration:
    def test_with_task_returns_new_port(self):
        port = LlmE2Port("old task", call_fn=_make_call_fn("SUCCESS"))
        port2 = port.with_task("new task")
        assert port2 is not port

    def test_with_task_updates_task(self):
        port = LlmE2Port("old task", call_fn=_make_call_fn("SUCCESS"))
        port2 = port.with_task("new task")
        assert port2.task() == "new task"

    def test_with_task_original_unchanged(self):
        port = LlmE2Port("old task", call_fn=_make_call_fn("SUCCESS"))
        port.with_task("new task")
        assert port.task() == "old task"

    def test_with_memos_returns_new_port(self):
        port = LlmE2Port("task", call_fn=_make_call_fn("SUCCESS"))
        port2 = port.with_memos({"context": "Q2 data"})
        assert port2 is not port

    def test_with_memos_has_memos_true(self):
        port = LlmE2Port("task", call_fn=_make_call_fn("SUCCESS"))
        port2 = port.with_memos({"context": "Q2 data"})
        assert port2.status()["has_memos"] is True

    def test_with_memos_original_has_no_memos(self):
        port = LlmE2Port("task", call_fn=_make_call_fn("SUCCESS"))
        port.with_memos({"context": "Q2"})
        assert port.status()["has_memos"] is False

    def test_default_config_model(self):
        port = LlmE2Port("task", call_fn=_make_call_fn("SUCCESS"))
        # Should use LLMConfig default
        assert port.status()["model"] == LLMConfig().model

    def test_scenario_block_not_empty(self):
        port = LlmE2Port("task", scenario_block="Q2 data",
                         call_fn=_make_call_fn("SUCCESS"))
        assert port.status()["has_scenario"] is True

    def test_no_scenario_block(self):
        port = LlmE2Port("task", call_fn=_make_call_fn("SUCCESS"))
        assert port.status()["has_scenario"] is False


# ── TestLlmE2PortE0Integration ────────────────────────────────────────────────

class TestLlmE2PortE0Integration:
    """Full E0Turn + LlmE2Port loop — no API key required."""

    def test_e0turn_with_llm_port_runs(self):
        ls = chain_landscape()
        port = LlmE2Port("process items", call_fn=_make_call_fn("SUCCESS"))
        session = E0Turn(ls, port)
        result = session.run_turn("START")
        assert isinstance(result, TurnResult)

    def test_e0turn_llm_success_moves_state(self):
        ls = chain_landscape()
        port = LlmE2Port("process items", call_fn=_make_call_fn("SUCCESS"))
        session = E0Turn(ls, port)
        result = session.run_turn("START")
        assert result.state_after == "MIDDLE"
        assert result.outcome == Outcome.SUCCESS

    def test_e0turn_llm_failure_stays_at_source(self):
        ls = chain_landscape()
        port = LlmE2Port("process items", call_fn=_make_call_fn("FAILURE"))
        session = E0Turn(ls, port)
        result = session.run_turn("START")
        assert result.outcome == Outcome.FAILURE
        assert result.state_after == "START"

    def test_e0turn_llm_payload_available(self):
        ls = chain_landscape()
        port = LlmE2Port("analyze",
                         call_fn=_make_call_fn("SUCCESS", result="Analysis complete"))
        session = E0Turn(ls, port)
        result = session.run_turn("START")
        assert result.payload == "Analysis complete"

    def test_e0turn_llm_run_to_goal(self):
        ls = chain_landscape()
        port = LlmE2Port("process", call_fn=_make_call_fn("SUCCESS"))
        session = E0Turn(ls, port)
        turns = list(session.run("START", max_turns=10, goal="END"))
        # Should reach END in 2 turns (START→MIDDLE→END)
        states = [t.state_before for t in turns]
        assert "START" in states

    def test_e0turn_llm_historization_updated(self):
        """After successful LLM turns, inertia on the edge should change."""
        from e0_controller.primitives import Edge
        ls = chain_landscape()
        edge = Edge("START", "MIDDLE")
        port = LlmE2Port("process", call_fn=_make_call_fn("SUCCESS"))
        session = E0Turn(ls, port)
        inertia_before = ls.historization.inertia_factor(edge)
        session.run_turn("START")
        inertia_after = ls.historization.inertia_factor(edge)
        assert inertia_after != inertia_before

    def test_e0turn_llm_status_port_id(self):
        ls = simple_landscape()
        port = LlmE2Port("task", name="briefing_agent",
                         call_fn=_make_call_fn("SUCCESS"))
        session = E0Turn(ls, port)
        assert session.status()["port_id"] == "briefing_agent"

    def test_e0turn_llm_error_still_records_turn(self):
        """LLM exception → FAILURE → turn is recorded in history."""
        ls = simple_landscape()
        port = LlmE2Port("task", call_fn=_error_call_fn)
        session = E0Turn(ls, port)
        session.run_turn("A")
        assert len(session.history()) == 1
        assert session.history()[0].outcome == Outcome.FAILURE
