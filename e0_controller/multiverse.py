"""
E₀ Multiverse — Coupled Systems with Novelty-Gated Historization (C60)
========================================================================
Problem: When two E₀ systems interact, they converge within 5–6 turns.
Consensus without novelty is indistinguishable from stagnation.
Further exploration stops — the systems don't see the next edges.

Insight (from C54 Coupling Theorem): A closed system (all SUCCESS)
reinforces existing paths and cannot escape traps.  Consensus without
novelty IS a closed system on the coupling level.

Solution — three mechanisms from existing E₀ primitives:

  1. Novelty-Gated Outcome:
       Consensus without structural novelty = FAILURE.
       → R_eff rises on stale coupling edges → system moves away.

  2. Coupling Frontier Reflexion:
       When all coupling edges are expensive (high R_eff) →
       propose new coupling modes via topology reflexion (P4 §6).

  3. Divergence Pressure:
       When convergence detected → inject new exploration territory
       into both universes → create structural difference that didn't
       exist before.

Architecture:

  Universe_A ←→ Coupling Landscape ←→ Universe_B

  The coupling landscape is a standard E₀ landscape whose
  outcomes are determined by NoveltyGate, not by domain execution.

Usage:
  from e0_controller.multiverse import (
      Universe, MultiverseController, MultiverseResult,
  )

  ctrl = MultiverseController(universe_a, universe_b)
  result = ctrl.run(max_turns=20)
  print(result.summary())
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Set, Tuple

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller, RunTrace


# ══════════════════════════════════════════════
# Landscape snapshot
# ══════════════════════════════════════════════

@dataclass(frozen=True)
class LandscapeSnapshot:
    """Frozen structural metrics of a landscape at a point in time."""
    state_count: int
    edge_count: int
    total_delta: float

    @classmethod
    def capture(cls, landscape: Landscape) -> LandscapeSnapshot:
        return cls(
            state_count=len(landscape._states),
            edge_count=len(landscape._delta),
            total_delta=sum(landscape._delta.values()) if landscape._delta else 0.0,
        )


# ══════════════════════════════════════════════
# Novelty gate
# ══════════════════════════════════════════════

class NoveltyGate:
    """Evaluates whether an interaction produced structural novelty.

    Novelty = new states, new edges, or significant Δ growth in
    either universe.  Consensus without growth = FAILURE.

    This is the central mechanism: it makes unproductive agreement
    expensive via historization, breaking the convergence trap.
    """

    def __init__(self, delta_threshold: float = 0.0):
        self.delta_threshold = delta_threshold

    def evaluate(
        self,
        before_a: LandscapeSnapshot,
        after_a: LandscapeSnapshot,
        before_b: LandscapeSnapshot,
        after_b: LandscapeSnapshot,
    ) -> Outcome:
        """SUCCESS if novelty detected, FAILURE if stagnant consensus."""
        new_states = (
            (after_a.state_count - before_a.state_count)
            + (after_b.state_count - before_b.state_count)
        )
        new_edges = (
            (after_a.edge_count - before_a.edge_count)
            + (after_b.edge_count - before_b.edge_count)
        )
        delta_growth = (
            (after_a.total_delta - before_a.total_delta)
            + (after_b.total_delta - before_b.total_delta)
        )

        if new_states > 0 or new_edges > 0 or delta_growth > self.delta_threshold:
            return Outcome.SUCCESS
        return Outcome.FAILURE


# ══════════════════════════════════════════════
# Universe
# ══════════════════════════════════════════════

@dataclass
class Universe:
    """One E₀ system in the multiverse."""
    name: str
    landscape: Landscape
    execute_fn: Callable[[str, str], Outcome]
    start: str
    goal: str


# ══════════════════════════════════════════════
# Turn result
# ══════════════════════════════════════════════

TurnFn = Callable[[Universe, Universe], None]
"""Signature for custom turn functions: (active, passive) → None.
The function modifies landscapes as needed.  NoveltyGate measures
what changed via before/after snapshots."""


@dataclass
class MultiverseTurn:
    """Result of one multiverse interaction turn."""
    turn: int
    active: str           # name of the active universe
    novel: bool           # did NoveltyGate detect novelty?
    outcome: Outcome      # SUCCESS (novel) or FAILURE (stale)


# ══════════════════════════════════════════════
# Multiverse result
# ══════════════════════════════════════════════

@dataclass
class MultiverseResult:
    """Complete multiverse run result."""
    turns: List[MultiverseTurn] = field(default_factory=list)
    convergence_turn: Optional[int] = None
    divergence_count: int = 0
    novelty_edges_added: int = 0

    @property
    def total_turns(self) -> int:
        return len(self.turns)

    @property
    def total_novelty(self) -> int:
        return sum(1 for t in self.turns if t.novel)

    @property
    def converged(self) -> bool:
        return self.convergence_turn is not None

    @property
    def novelty_rate(self) -> float:
        if not self.turns:
            return 0.0
        return self.total_novelty / len(self.turns)

    def summary(self) -> str:
        lines = [
            "Multiverse Run",
            "=" * 40,
            f"Turns: {self.total_turns}",
            f"Novelty: {self.total_novelty}/{self.total_turns}"
            f" ({self.novelty_rate:.0%})",
        ]
        if self.converged:
            lines.append(
                f"Convergence at turn {self.convergence_turn}"
            )
        if self.divergence_count > 0:
            lines.append(
                f"Divergence pressure applied: {self.divergence_count}x"
                f" ({self.novelty_edges_added} edges added)"
            )
        # Per-turn detail
        lines.append("")
        for t in self.turns:
            marker = "+" if t.novel else "-"
            lines.append(
                f"  T{t.turn:>2} [{t.active}] {marker}"
            )
        return "\n".join(lines)


# ══════════════════════════════════════════════
# Multiverse controller
# ══════════════════════════════════════════════

class MultiverseController:
    """Orchestrates two coupled E₀ systems with novelty-gated historization.

    Central mechanism: Consensus without novelty = FAILURE.
    This reverses the natural convergence tendency by making
    unproductive agreement expensive via historization.

    When convergence is detected (N consecutive turns without novelty),
    divergence pressure injects new exploration territory:
    1. A new coupling mode in the coupling landscape (fresh low-R edges)
    2. New exploration edges in each universe (unfamiliar territory)
    """

    def __init__(
        self,
        universe_a: Universe,
        universe_b: Universe,
        *,
        convergence_window: int = 3,
        max_steps_per_turn: int = 10,
        coupling_delta: float = 1.0,
        coupling_resistance: float = 0.5,
    ):
        self.a = universe_a
        self.b = universe_b
        self.convergence_window = convergence_window
        self.max_steps_per_turn = max_steps_per_turn
        self.gate = NoveltyGate()
        self.coupling = self._build_coupling(coupling_delta, coupling_resistance)
        self.turns: List[MultiverseTurn] = []
        self._divergence_count = 0

    def _build_coupling(
        self, delta: float, resistance: float,
    ) -> Landscape:
        """Build the coupling landscape between two universes.

        Initial topology: two poles with bidirectional coupling.
        Historized independently — outcomes from NoveltyGate.
        """
        L = Landscape()
        L.add_edge(self.a.name, self.b.name, delta=delta, resistance=resistance)
        L.add_edge(self.b.name, self.a.name, delta=delta, resistance=resistance)
        return L

    # ── Single turn ──────────────────────────

    def turn(
        self,
        turn_fn: Optional[TurnFn] = None,
    ) -> MultiverseTurn:
        """Execute one multiverse turn.

        1. Pick active universe (alternating A/B)
        2. Snapshot both universes
        3. Execute turn (custom or default)
        4. Snapshot again
        5. NoveltyGate evaluates
        6. Historize coupling edge
        """
        turn_number = len(self.turns)
        active = self.a if turn_number % 2 == 0 else self.b
        passive = self.b if turn_number % 2 == 0 else self.a

        # Snapshot before
        snap_a_before = LandscapeSnapshot.capture(self.a.landscape)
        snap_b_before = LandscapeSnapshot.capture(self.b.landscape)

        # Execute
        if turn_fn is not None:
            turn_fn(active, passive)
        else:
            self._default_turn(active)

        # Snapshot after
        snap_a_after = LandscapeSnapshot.capture(self.a.landscape)
        snap_b_after = LandscapeSnapshot.capture(self.b.landscape)

        # Evaluate novelty
        outcome = self.gate.evaluate(
            snap_a_before, snap_a_after,
            snap_b_before, snap_b_after,
        )
        novel = outcome == Outcome.SUCCESS

        # Historize coupling edge
        coupling_edge = Edge(active.name, passive.name)
        self.coupling.historization.update(coupling_edge, outcome)

        result = MultiverseTurn(
            turn=turn_number,
            active=active.name,
            novel=novel,
            outcome=outcome,
        )
        self.turns.append(result)
        return result

    def _default_turn(self, active: Universe) -> None:
        """Default turn: run controller for a few cycles."""
        ctrl = E0Controller(
            active.landscape, active.execute_fn,
            alpha=2.0, recent_k=3,
        )
        ctrl.run(
            active.start,
            max_cycles=self.max_steps_per_turn,
            goal=active.goal,
        )

    # ── Convergence detection ────────────────

    def detect_convergence(self) -> bool:
        """Have the last N turns produced no novelty?"""
        if len(self.turns) < self.convergence_window:
            return False
        recent = self.turns[-self.convergence_window:]
        return all(not t.novel for t in recent)

    # ── Divergence pressure ──────────────────

    def apply_divergence_pressure(self) -> int:
        """Break convergence by injecting new exploration territory.

        Two E₀-native mechanisms:

        1. New coupling mode: add an intermediate state in the
           coupling landscape with fresh (low-R) edges.  This gives
           the system a new, cheap interaction pathway.

        2. Exploration edges: for each universe, find a pair of
           existing states with no direct edge and add one with
           high Δ (strong structural difference = interesting).

        Returns the number of new edges added across all landscapes.
        """
        added = 0
        self._divergence_count += 1

        # 1. New coupling mode
        mode = f"mode_{self._divergence_count}"
        self.coupling.add_edge(
            self.a.name, mode, delta=1.5, resistance=0.3,
        )
        self.coupling.add_edge(
            mode, self.b.name, delta=1.5, resistance=0.3,
        )
        added += 2

        # 2. Exploration edges in each universe
        for u in [self.a, self.b]:
            new = self._inject_exploration_edge(u)
            added += new

        return added

    def _inject_exploration_edge(self, universe: Universe) -> int:
        """Add one edge between disconnected states in a universe.

        Picks the pair (s1 → s2) where s1 has the fewest outgoing
        edges (least explored) and s2 is not directly reachable from s1.
        Uses high Δ to create structural tension toward this new edge.

        Returns 1 if an edge was added, 0 if all pairs already connected.
        """
        L = universe.landscape
        states = sorted(L._states)
        if len(states) < 2:
            return 0

        # Sort states by outgoing edge count (ascending = least explored first)
        outgoing_count = {
            s: sum(1 for e in L._delta if e.source == s)
            for s in states
        }
        states_by_exploration = sorted(states, key=lambda s: outgoing_count[s])

        for s1 in states_by_exploration:
            for s2 in states:
                if s1 == s2:
                    continue
                edge = Edge(s1, s2)
                if edge not in L._delta:
                    L.add_edge(s1, s2, delta=1.0, resistance=0.3)
                    return 1
        return 0

    # ── Full run ─────────────────────────────

    def run(
        self,
        max_turns: int = 20,
        turn_fn: Optional[TurnFn] = None,
    ) -> MultiverseResult:
        """Run the multiverse until max_turns.

        When convergence is detected, divergence pressure is applied
        DURING the next turn (between before/after snapshots) so the
        NoveltyGate registers the injected edges as structural novelty.
        This creates the explore-after-consensus dynamic that prevents
        premature convergence.
        """
        result = MultiverseResult()
        diverge_next = False

        for _ in range(max_turns):
            if diverge_next:
                base_fn = turn_fn

                def _diverge_turn(active, passive, _base=base_fn):
                    added = self.apply_divergence_pressure()
                    result.divergence_count += 1
                    result.novelty_edges_added += added
                    if _base is not None:
                        _base(active, passive)

                t = self.turn(turn_fn=_diverge_turn)
                diverge_next = False
            else:
                t = self.turn(turn_fn=turn_fn)

            result.turns.append(t)

            if self.detect_convergence():
                if result.convergence_turn is None:
                    result.convergence_turn = t.turn
                diverge_next = True

        return result

    # ── Inspection ───────────────────────────

    def coupling_resistance(self, source: str, target: str) -> float:
        """Current effective resistance on a coupling edge."""
        return self.coupling.effective_resistance(source, target)

    def coupling_quality(self, source: str, target: str) -> float:
        """Trace quality on a coupling edge."""
        edge = Edge(source, target)
        return self.coupling.historization.trace_quality(edge)
