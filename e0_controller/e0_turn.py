"""
E₀ E0Turn (C292)
=================
Persistent turn loop — the universal coupling between E₀ and the world.

Architecture:
    SELECT    E₀ selects the next action from current state
    EXECUTE   E₂ executes the action and returns (new_state, outcome)
    HISTORIZE E₀ learns from the outcome; Landscape evolves
    LOOP      repeat from new_state

    This is the canonical E₀ execution cycle. E2Port abstracts the
    domain: factory floor, traffic network, LLM conversation, API call —
    all are E2Port implementations. E₀ does not know the difference.

Relationship to existing primitives:
    - E0Controller provides SELECT + HISTORIZE (via cycle())
    - E2Port provides EXECUTE (C292)
    - E0Turn wires them into a persistent loop with:
        * TurnResult dataclass (full turn record)
        * run_turn(state) → single synchronous turn
        * run(start, max_turns) → iterator over turns
        * save/load JSON persistence (same pattern as C291)
        * inertia_threshold hook for E1 escalation signaling

LLM integration note:
    To use an LLM as the execution target, implement E2Port where
    execute() generates a prompt, calls the LLM, and evaluates the
    response. E₀ historizes the quality of that response over time.
    This is the "E₀ = Skeleton, LLM = Muscle" pattern.

Usage:
    landscape = Landscape.fully_connected(["idle", "run", "done"])
    port = MyDomainPort()
    session = E0Turn(landscape, port)

    for turn in session.run(start="idle", max_turns=50):
        print(turn)
        if turn.state_after == "done":
            break

    session.save("turn_session.json")
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from .controller import E0Controller, EscalationType
from .e2_port import E2Port, ExecutionResult
from .landscape import Landscape
from .primitives import Edge, Outcome


# ── TurnResult ────────────────────────────────────────────────────────────────

@dataclass
class TurnResult:
    """Complete record of one E₀ turn (SELECT → EXECUTE → HISTORIZE).

    Fields:
        turn_index      sequential turn number (0-based)
        state_before    state at start of turn (E₀ source)
        action          label selected by E₀ (intended target state)
        state_after     actual state returned by E2Port after execution
        outcome         E₀ Outcome (SUCCESS / FAILURE / PARTIAL)
        escalated       True when E₀ could not find a valid next action
        escalation_type why escalation occurred (K12 enum)
        payload         arbitrary domain data from E2Port (E₀ ignores this)
        inertia_low     True when inertia_factor(edge) < inertia_threshold
                        → hint that E1 (LLM / human) should be involved

    Note: state_after may differ from action when the domain reports an
    unexpected transition (e.g., actuator fault, external interruption).
    E₀ historizes (state_before → action), not (state_before → state_after).
    The actual new_state is tracked in state_after for session continuity.
    """
    turn_index: int
    state_before: str
    action: Optional[str]           # None when escalated with no candidates
    state_after: str
    outcome: Optional[Outcome]      # None when escalated with no candidates
    escalated: bool = False
    escalation_type: EscalationType = EscalationType.NONE
    payload: Any = field(default=None)
    inertia_low: bool = False       # E1 callout hint

    def to_dict(self) -> dict:
        return {
            "turn_index": self.turn_index,
            "state_before": self.state_before,
            "action": self.action,
            "state_after": self.state_after,
            "outcome": self.outcome.name if self.outcome else None,
            "escalated": self.escalated,
            "escalation_type": self.escalation_type.name,
            "inertia_low": self.inertia_low,
            # payload intentionally excluded — may not be JSON-serializable
        }

    def __repr__(self) -> str:
        esc = f" [ESC:{self.escalation_type.name}]" if self.escalated else ""
        il = " [LOW_I]" if self.inertia_low else ""
        oc = self.outcome.name if self.outcome else "—"
        return (
            f"Turn({self.turn_index}): "
            f"{self.state_before} →[{self.action}]→ {self.state_after} "
            f"| {oc}{esc}{il}"
        )


# ── E0Turn ────────────────────────────────────────────────────────────────────

class E0Turn:
    """Persistent turn loop — E₀ coupled to an E2Port.

    The session owns the controller lifecycle and provides a clean
    interface for domain-agnostic operation.

    Args:
        landscape:          E₀ Landscape (states + edges + historization)
        e2_port:            execution boundary (implements E2Port ABC)
        inertia_threshold:  float in (0, 1]. When inertia_factor(edge) < this
                            value, TurnResult.inertia_low = True as a hint
                            that E1 (LLM / human) should be involved.
                            Default 0.3 (low trace_load → uncertain edge).
        controller_kwargs:  extra kwargs forwarded to E0Controller (alpha,
                            hybrid_mode, max_escalation_R, etc.)

    Controller lifecycle:
        E0Turn creates exactly one E0Controller.
        The controller's execute_fn is a closure around e2_port.execute()
        that captures the ExecutionResult for each turn.
    """

    def __init__(
        self,
        landscape: Landscape,
        e2_port: E2Port,
        inertia_threshold: float = 0.3,
        controller_kwargs: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._landscape = landscape
        self._port = e2_port
        self._inertia_threshold = inertia_threshold
        self._turn_count = 0
        self._history: List[TurnResult] = []

        # Mutable capture slot — updated by _capture_execute each turn
        self._last_exec: Optional[ExecutionResult] = None

        # Wire E2Port into E0Controller via execute_fn closure
        kwargs = controller_kwargs or {}
        self._controller = E0Controller(
            landscape,
            self._capture_execute,
            **kwargs,
        )

    # ── Internal execute_fn (bridges E2Port → E0Controller) ──────────────────

    def _capture_execute(self, state: str, action: str) -> Outcome:
        """Called by E0Controller.cycle() as execute_fn.

        Delegates to E2Port.execute(), captures the ExecutionResult for
        post-cycle use (new_state, payload), returns Outcome to E0.
        """
        result = self._port.execute(state, action)
        self._last_exec = result
        return result.outcome

    # ── Core turn primitive ───────────────────────────────────────────────────

    def run_turn(self, state: str) -> TurnResult:
        """Execute one complete E₀ turn from state.

        Flow: SELECT → EXECUTE (via E2Port) → HISTORIZE → return TurnResult

        The controller handles SELECT + HISTORIZE internally via cycle().
        E2Port.execute() is called as the execute_fn, captured via closure.

        Returns a TurnResult. On complete dead-end (no candidates), the
        turn is recorded as escalated with no action.
        """
        self._last_exec = None
        turn_idx = self._turn_count

        step = self._controller.cycle(state)

        if step is None:
            # Total dead-end: no admissible transitions from this state
            result = TurnResult(
                turn_index=turn_idx,
                state_before=state,
                action=None,
                state_after=state,
                outcome=None,
                escalated=True,
                escalation_type=EscalationType.DEAD_END,
                inertia_low=False,
            )
            self._turn_count += 1
            self._history.append(result)
            return result

        # Determine actual new state from E2Port result
        new_state = (
            self._last_exec.new_state
            if self._last_exec is not None
            else step.target
        )
        payload = self._last_exec.payload if self._last_exec else None

        # Compute inertia_low hint for E1 escalation
        edge = Edge(step.source, step.target)
        inertia = self._landscape.historization.inertia_factor(edge)
        inertia_low = inertia < self._inertia_threshold

        result = TurnResult(
            turn_index=turn_idx,
            state_before=step.source,
            action=step.target,
            state_after=new_state,
            outcome=step.outcome,
            escalated=step.escalated,
            escalation_type=step.escalation_type,
            payload=payload,
            inertia_low=inertia_low,
        )
        self._turn_count += 1
        self._history.append(result)
        return result

    # ── Multi-turn loop ───────────────────────────────────────────────────────

    def run(
        self,
        start: str,
        max_turns: int = 100,
        goal: Optional[str] = None,
    ) -> Iterator[TurnResult]:
        """Run E₀ session for up to max_turns turns.

        Yields one TurnResult per turn. Stops when:
        - goal state is reached (if specified)
        - max_turns exceeded
        - dead-end (escalated with no candidates)

        Args:
            start:      initial state
            max_turns:  upper bound on turns
            goal:       optional terminal state (string label)

        Yields:
            TurnResult for each turn executed

        Example:
            for turn in session.run("idle", max_turns=50, goal="done"):
                if turn.inertia_low:
                    inject_llm_suggestion(turn)
        """
        current = start
        for _ in range(max_turns):
            if goal is not None and current == goal:
                break
            turn = self.run_turn(current)
            yield turn
            if turn.escalated and turn.action is None:
                break  # total dead-end
            current = turn.state_after

    # ── Diagnostics ───────────────────────────────────────────────────────────

    def status(self) -> dict:
        """Return session status snapshot.

        Includes turn count, port identity, landscape size,
        and summary of recent turns.
        """
        last = self._history[-1] if self._history else None
        return {
            "port_id": self._port.port_id(),
            "turn_count": self._turn_count,
            "inertia_threshold": self._inertia_threshold,
            "landscape_states": len(self._landscape.states),
            "landscape_edges": len(self._landscape.edges),
            "last_turn": last.to_dict() if last else None,
            "escalation_count": sum(
                1 for t in self._history if t.escalated
            ),
            "success_count": sum(
                1 for t in self._history
                if t.outcome is not None and t.outcome == Outcome.SUCCESS
            ),
            "failure_count": sum(
                1 for t in self._history
                if t.outcome is not None and t.outcome == Outcome.FAILURE
            ),
            "inertia_low_count": sum(
                1 for t in self._history if t.inertia_low
            ),
        }

    def history(self) -> List[TurnResult]:
        """Return list of all TurnResults in order."""
        return list(self._history)

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self, path: str) -> None:
        """Save session metadata to JSON.

        Saves: port_id, turn_count, inertia_threshold, turn history.
        Does NOT save Landscape (use Landscape serialization separately).
        """
        data = {
            "version": 1,
            "port_id": self._port.port_id(),
            "turn_count": self._turn_count,
            "inertia_threshold": self._inertia_threshold,
            "history": [t.to_dict() for t in self._history],
        }
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load_history(cls, path: str) -> dict:
        """Load session metadata from JSON (deserialization helper).

        Returns the raw dict. Full session restoration requires
        re-supplying Landscape and E2Port (not serialized here).

        Usage:
            data = E0Turn.load_history("session.json")
            session = E0Turn(landscape, port)
            session._turn_count = data["turn_count"]
        """
        return json.loads(Path(path).read_text(encoding="utf-8"))
