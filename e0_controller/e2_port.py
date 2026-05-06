"""
E₀ E2Port (C292)
=================
Universal execution interface — the boundary between E₀ and the world.

Design principle:
    E₀ decides what to do (select_next). The world executes it and
    reports back. E2Port is the contract for that report.

    Anything that can take an (action, state) pair and return
    (new_state, Outcome) is E2-compatible:
        - API call        — HTTP request, outcome from status code
        - Tool call       — LLM tool, outcome from tool result
        - Sensor reading  — read sensor, outcome from threshold check
        - Database query  — query, outcome from row count
        - LLM generation  — prompt, outcome from response quality
        - Physical device — actuator, outcome from feedback signal
        - Conversation    — generate reply, outcome from user response

    E₀ does not know which one it is talking to. It only historizes
    (source_state, action) → Outcome. Structure emerges from that.

Interface contract:
    execute(state, action)  → ExecutionResult
    port_id()               → unique identifier (used in diagnostics)
    can_execute(state, action) → bool  (admissibility filter)

ExecutionResult:
    new_state   — state after execution (may equal state on FAILURE)
    outcome     — SUCCESS / FAILURE / PARTIAL
    payload     — arbitrary domain data (sensor reading, LLM output, etc.)
                  E₀ ignores payload — it belongs to E2/E1 processing

Relationship to DifferenzPort:
    DifferenzPort (C288) = INPUT protocol: how Δ enters E₀
    E2Port (C292)        = OUTPUT protocol: how E₀ acts on the world
    Together they form the full E₀ coupling loop:

        Δ → [DifferenzPort] → E₀ → [E2Port] → World → Outcome → E₀

Usage:
    class MyPort(E2Port):
        def port_id(self) -> str: return "my_domain"
        def execute(self, state, action):
            result = run_my_system(state, action)
            return ExecutionResult(
                new_state=result.next_state,
                outcome=Outcome.SUCCESS if result.ok else Outcome.FAILURE,
                payload=result.raw_data,
            )

    port = MyPort()
    session = E0Session(landscape, port)
    for turn in session.run(start="idle", max_turns=100):
        print(turn)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from .primitives import Outcome


@dataclass
class ExecutionResult:
    """Result of one E2 execution.

    Fields:
        new_state   — state after execution (may == source on FAILURE)
        outcome     — SUCCESS / FAILURE / PARTIAL (canonical E₀ Outcome)
        payload     — arbitrary domain data; E₀ does not inspect this
        error       — optional error message when execution fails at port level
    """
    new_state: str
    outcome: Outcome
    payload: Any = field(default=None)
    error: Optional[str] = field(default=None)


class E2Port(ABC):
    """Abstract base: execution boundary between E₀ and the world.

    Every domain (factory control, traffic management, conversation,
    database query, API call) implements this interface. E₀ only sees
    (state, action, outcome) — domain specifics remain in E2.

    Subclasses must implement:
        port_id()   — unique string identifier
        execute()   — the domain action

    Subclasses may override:
        can_execute() — admissibility filter (default: always True)
    """

    @abstractmethod
    def port_id(self) -> str:
        """Unique identifier for this execution port.

        Used in diagnostics and session metadata. Should be stable
        across sessions (same domain → same id).
        """

    @abstractmethod
    def execute(self, state: str, action: str) -> ExecutionResult:
        """Execute action from state; return result.

        Args:
            state:  current state label (as E₀ knows it)
            action: target state / action label selected by E₀

        Returns:
            ExecutionResult with new_state, outcome, optional payload.

        Contract:
            - MUST NOT raise (catch all domain errors, return FAILURE)
            - new_state SHOULD equal action on SUCCESS
            - new_state MAY equal state on FAILURE (no movement)
            - new_state MAY be a third state (unexpected transition)
        """

    def can_execute(self, state: str, action: str) -> bool:
        """Admissibility filter: can this action be executed from state?

        Default: always True (E₀'s Landscape admissibility is sufficient).
        Override to add domain-level constraints (e.g., resource availability,
        physical limits, permission checks).

        Note: returning False for an action that E₀ selected causes that
        action to be skipped and recorded as FAILURE for that edge.
        """
        return True


# ── Built-in implementations ──────────────────────────────────────────────────

class LambdaE2Port(E2Port):
    """E2Port backed by a plain function — for tests and demos.

    Args:
        fn:     Callable[(state, action) → ExecutionResult | Outcome | str]
                  ExecutionResult  → used directly
                  Outcome          → wrapped as ExecutionResult(new_state=action, ...)
                  str              → interpreted as new_state with SUCCESS
        name:   port_id (default: "lambda")

    Example:
        port = LambdaE2Port(lambda s, a: Outcome.SUCCESS)
        port = LambdaE2Port(lambda s, a: ExecutionResult("done", Outcome.SUCCESS))
    """

    def __init__(self, fn, name: str = "lambda") -> None:
        self._fn = fn
        self._name = name

    def port_id(self) -> str:
        return self._name

    def execute(self, state: str, action: str) -> ExecutionResult:
        raw = self._fn(state, action)
        if isinstance(raw, ExecutionResult):
            return raw
        if isinstance(raw, Outcome):
            new_state = action if raw != Outcome.FAILURE else state
            return ExecutionResult(new_state=new_state, outcome=raw)
        if isinstance(raw, str):
            return ExecutionResult(new_state=raw, outcome=Outcome.SUCCESS)
        raise TypeError(
            f"LambdaE2Port fn must return ExecutionResult, Outcome, or str; "
            f"got {type(raw).__name__}"
        )
