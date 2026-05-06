"""
E₀ LlmE2Port (C293)
====================
E2Port implementation where the LLM is the execution target.

This is the "E₀ = Skeleton, LLM = Muscle" principle made concrete:

    E₀ selects which transition to take (SELECT)
    LlmE2Port asks the LLM to execute that transition (EXECUTE)
    E₀ historizes the outcome (HISTORIZE)

The LLM does the generative, domain-specific work. E₀ tracks quality
over time and learns which transitions are reliable vs. uncertain.

Architecture:
    LlmE2Port wraps E0LLMAdapter.execute_transition() as an E2Port.
    The task description contextualizes the transition (domain semantics).
    LLM response → TransitionResult → ExecutionResult (E2Port contract).

    State labels in E₀ are the domain states. The LLM receives them
    as (source, target, task) and reports outcome + result text.

LlmE2Port.execute() contract:
    - NEVER raises (catches all LLM errors, returns FAILURE)
    - payload = TransitionResult.result (the LLM's natural-language output)
    - new_state = action on SUCCESS/PARTIAL, state on FAILURE

Testing strategy (no API key required):
    - LlmE2Port accepts an injectable `call_fn` parameter
    - Tests use `LambdaE2Port`-style fakes via call_fn
    - Live integration test uses `openai_call` (skipped without OPENAI_API_KEY)

Usage:
    from e0_controller.llm_e2_port import LlmE2Port
    from e0_controller.e0_turn import E0Turn
    from e0_controller.landscape import Landscape
    from e0_controller.llm_adapter import LLMConfig

    landscape = Landscape.fully_connected(
        ["PROBLEM_STATED", "ANALYSIS_DONE", "SOLUTION_DRAFTED", "DELIVERED"]
    )
    port = LlmE2Port(
        task="Draft an executive briefing on Q2 supply chain disruptions.",
        config=LLMConfig(model="gpt-5.4-mini"),
    )
    session = E0Turn(landscape, port)
    for turn in session.run(start="PROBLEM_STATED", goal="DELIVERED"):
        print(turn)
        if turn.inertia_low:
            print(f"  LLM output: {turn.payload[:80]}...")
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from .e2_port import E2Port, ExecutionResult
from .llm_adapter import E0LLMAdapter, LLMConfig, LLMCallFn, openai_call
from .primitives import Outcome


# ──────────────────────────────────────────────────────────────────────────────

class LlmE2Port(E2Port):
    """E2Port backed by E0LLMAdapter.execute_transition().

    The LLM is the execution engine. E₀ tracks which transitions it
    executes reliably (SUCCESS → R_eff decreases → path preferred) and
    which are uncertain (FAILURE → R_eff increases → path avoided).

    Args:
        task:           Domain-level task description. Sent to LLM as
                        context for every transition. Keep concise.
        config:         LLMConfig (model, temperature, max_tokens).
                        Defaults to gpt-5.4-mini if not specified.
        name:           Port identifier (default: "llm").
        call_fn:        Injectable LLM backend — defaults to openai_call.
                        Override for testing without API key.
        scenario_block: Optional pre-formatted scenario context (same as
                        E0LLMAdapter.execute_transition scenario_block).
        memos_summary:  Optional MemOS summary dict for LLM context.

    Payload:
        ExecutionResult.payload = TransitionResult.result (LLM's text output).
        Inspect turn.payload to see what the LLM actually produced.
    """

    def __init__(
        self,
        task: str,
        config: Optional[LLMConfig] = None,
        name: str = "llm",
        call_fn: Optional[LLMCallFn] = None,
        scenario_block: str = "",
        memos_summary: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._task = task
        self._config = config or LLMConfig()
        self._name = name
        self._scenario_block = scenario_block
        self._memos_summary = memos_summary

        # Build adapter with injected call_fn (enables testing without API key)
        self._adapter = E0LLMAdapter(config=self._config, call_fn=call_fn)

    # ── E2Port interface ──────────────────────────────────────────────────────

    def port_id(self) -> str:
        return self._name

    def execute(self, state: str, action: str) -> ExecutionResult:
        """Ask the LLM to execute the transition from state to action.

        Args:
            state:  source state label (E₀'s current state)
            action: target state label (E₀'s selected action)

        Returns:
            ExecutionResult with:
                new_state  = action on SUCCESS/PARTIAL, state on FAILURE
                outcome    = TransitionResult.outcome
                payload    = TransitionResult.result (LLM's text)
                error      = error message if LLM call failed

        Contract: NEVER raises. All LLM errors → FAILURE outcome.
        """
        try:
            result = self._adapter.execute_transition(
                source=state,
                target=action,
                task=self._task,
                memos_summary=self._memos_summary,
                scenario_block=self._scenario_block,
            )
        except Exception as exc:
            # LLM failure → FAILURE outcome, state unchanged
            return ExecutionResult(
                new_state=state,
                outcome=Outcome.FAILURE,
                payload=None,
                error=str(exc),
            )

        # Map outcome → new_state
        new_state = action if result.outcome != Outcome.FAILURE else state

        return ExecutionResult(
            new_state=new_state,
            outcome=result.outcome,
            payload=result.result,  # LLM's natural-language output
            error=None,
        )

    # ── Configuration ─────────────────────────────────────────────────────────

    def task(self) -> str:
        """Return the task description."""
        return self._task

    def with_task(self, task: str) -> "LlmE2Port":
        """Return a new LlmE2Port with updated task (immutable update)."""
        return LlmE2Port(
            task=task,
            config=self._config,
            name=self._name,
            call_fn=self._adapter._call,
            scenario_block=self._scenario_block,
            memos_summary=self._memos_summary,
        )

    def with_memos(self, memos_summary: Dict[str, Any]) -> "LlmE2Port":
        """Return a new LlmE2Port with updated MemOS summary."""
        return LlmE2Port(
            task=self._task,
            config=self._config,
            name=self._name,
            call_fn=self._adapter._call,
            scenario_block=self._scenario_block,
            memos_summary=memos_summary,
        )

    def status(self) -> dict:
        """Diagnostic snapshot of port configuration."""
        return {
            "port_id": self._name,
            "task": self._task,
            "model": self._config.model,
            "temperature": self._config.temperature,
            "has_memos": self._memos_summary is not None,
            "has_scenario": bool(self._scenario_block),
        }
