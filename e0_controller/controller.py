"""
E₀ Controller — Core Loop
============================
The deterministic transition logic.

Spec coverage: §18 (Selection), §17 (Historization Update),
               Revisit-Penalty (v0.2 addition).

Core function implemented:
    6. select_next(x)           — Greedy + Revisit-Penalty + Escalation
    7. update_historization(…)  — handled via Landscape.historization.update()

Controller loop:
    select → execute → historize → repeat
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from .primitives import Edge, Outcome
from .landscape import Landscape


@dataclass
class StepResult:
    """One completed controller cycle."""
    tau: int                     # step number
    source: str                  # where we were
    target: str                  # where we went
    outcome: Outcome             # what happened
    s_eff: float                 # tension of chosen edge
    r_eff_before: float          # R_eff before historization update
    r_eff_after: float           # R_eff after historization update
    candidates: List[str]        # who was admissible
    escalated: bool = False      # was this an escalation?


@dataclass
class RunTrace:
    """Complete trace of a controller run."""
    steps: List[StepResult] = field(default_factory=list)

    @property
    def path(self) -> List[str]:
        """Sequence of visited states."""
        if not self.steps:
            return []
        states = [self.steps[0].source]
        for s in self.steps:
            states.append(s.target)
        return states

    @property
    def total_tension(self) -> float:
        return sum(s.s_eff for s in self.steps if not math.isinf(s.s_eff))

    @property
    def outcomes(self) -> Dict[str, int]:
        counts = {"SUCCESS": 0, "FAILURE": 0, "PARTIAL": 0}
        for s in self.steps:
            counts[s.outcome.name] += 1
        return counts

    def summary(self) -> str:
        lines = [f"RunTrace: {len(self.steps)} steps"]
        lines.append(f"  Path: {' → '.join(self.path)}")
        lines.append(f"  Outcomes: {self.outcomes}")
        lines.append(f"  Total tension: {self.total_tension:.4f}")
        escalations = sum(1 for s in self.steps if s.escalated)
        if escalations:
            lines.append(f"  Escalations: {escalations}")
        return "\n".join(lines)


# Type for the execution callback
ExecuteFn = Callable[[str, str], Outcome]


class E0Controller:
    """
    Deterministic E₀ Controller v0.1

    Implements greedy transition selection with:
    - Revisit-penalty: penalize recently visited states
    - Escalation: when no admissible neighbor exists
    - Historization: learn from each transition outcome

    Parameters:
        landscape: The Landscape L_t
        execute_fn: Callback (source, target) → Outcome
        alpha: Revisit-penalty weight (default 2.0)
        recent_k: Number of recent states to penalize (default 3)
        max_escalation_R: Maximum R₀ to assign during escalation (default 5.0)
    """

    def __init__(
        self,
        landscape: Landscape,
        execute_fn: ExecuteFn,
        alpha: float = 2.0,
        recent_k: int = 3,
        max_escalation_R: float = 5.0,
    ):
        self.landscape = landscape
        self.execute_fn = execute_fn
        self.alpha = alpha
        self.recent_k = recent_k
        self.max_escalation_R = max_escalation_R
        self._recent: List[str] = []   # sliding window of recent states

    def _update_recent(self, state: str) -> None:
        """Maintain sliding window of recently visited states."""
        self._recent.append(state)
        if len(self._recent) > self.recent_k:
            self._recent = self._recent[-self.recent_k:]

    def _penalized_tension(self, x: str, y: str) -> float:
        """
        S_revisit(x→y) = S_eff(x→y) + α · 𝟙[y ∈ recent(k)]

        Adds penalty for revisiting recently-seen states.
        This breaks oscillation cycles like A↔B.
        """
        s_eff = self.landscape.effective_tension(x, y)
        if math.isinf(s_eff):
            return math.inf
        if y in self._recent:
            s_eff += self.alpha
        return s_eff

    def select_next(self, current: str) -> Tuple[Optional[str], bool]:
        """
        Function 6: select_next(x) → (next_state, escalated?)

        §18: p* = argmin S_eff(p)

        Strategy: Greedy + Revisit-Penalty + Escalation.
        1. Get admissible neighbors.
        2. Pick argmin of penalized tension.
        3. If empty → escalation: pick overall nearest state.
        """
        neighbors = self.landscape.admissible_neighbors(current)

        if neighbors:
            # Greedy with revisit-penalty
            best = min(neighbors, key=lambda y: self._penalized_tension(current, y))
            return best, False

        # --- Escalation ---
        # No admissible neighbors. This is a dead-end.
        # Strategy: find the most reachable state from the full landscape
        # and create an escalation edge.
        all_states = self.landscape.states - {current}
        if not all_states:
            return None, True  # nowhere to go at all

        # Pick the state with lowest existing tension from any other state
        # that has outgoing edges (i.e., it's not also a dead-end).
        # Simple escalation: jump to a state that has outgoing edges.
        viable = []
        for s in all_states:
            out = self.landscape.admissible_neighbors(s)
            if out:
                viable.append(s)

        if not viable:
            return None, True  # entire landscape is dead

        # Among viable, pick the one with most outgoing edges
        # (most potential for progress)
        best_esc = max(viable, key=lambda s: len(self.landscape.admissible_neighbors(s)))

        # Create an escalation edge: high Δ, bounded R
        esc_delta = 1.0  # escalation always has Δ = 1.0 (maximal difference)
        self.landscape.add_edge(current, best_esc,
                                delta=esc_delta,
                                resistance=self.max_escalation_R)
        return best_esc, True

    def cycle(self, current: str) -> Optional[StepResult]:
        """
        One complete controller cycle:
            select → execute → historize → report

        Returns None if no transition is possible.
        """
        target, escalated = self.select_next(current)
        if target is None:
            return None

        edge = Edge(current, target)

        # Capture R_eff before
        r_eff_before = self.landscape.effective_resistance(current, target)
        s_eff = self.landscape.effective_tension(current, target)

        # Execute
        outcome = self.execute_fn(current, target)

        # Historize (Function 7)
        self.landscape.historization.update(edge, outcome)
        self.landscape.historization.record(
            edge, outcome, r_eff_before,
            self.landscape.effective_resistance(current, target)
        )

        # Capture R_eff after
        r_eff_after = self.landscape.effective_resistance(current, target)

        # Update recent window
        self._update_recent(current)

        candidates = self.landscape.admissible_neighbors(current)

        return StepResult(
            tau=self.landscape.historization.tau,
            source=current,
            target=target,
            outcome=outcome,
            s_eff=s_eff,
            r_eff_before=r_eff_before,
            r_eff_after=r_eff_after,
            candidates=candidates,
            escalated=escalated,
        )

    def run(
        self,
        start: str,
        max_cycles: int = 50,
        goal: Optional[str] = None,
    ) -> RunTrace:
        """
        Run the controller from start.

        Stops when:
        - goal state is reached (if specified)
        - max_cycles exceeded
        - no transition possible (complete dead-end)
        """
        trace = RunTrace()
        current = start

        for _ in range(max_cycles):
            # Check goal
            if goal and current == goal:
                break

            step = self.cycle(current)
            if step is None:
                break  # complete dead-end, no escalation possible

            trace.steps.append(step)
            current = step.target

        return trace
