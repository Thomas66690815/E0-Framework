"""
E₀ Controller — Graph Validation (Phase 3c)
=============================================
Quality checks for LLM-bootstrapped Landscapes.

Validates structural properties of a proposed or materialized
graph BEFORE the controller runs, catching degenerate topologies
that would cause loops, dead-ends, or unreachable goals.

Checks implemented:
    1. goal_reachable(L, start, goal)   — BFS reachability
    2. find_happy_path(L, start, goal)  — shortest forward path
    3. find_recovery_edges(L, happy)    — edges back onto happy path
    4. detect_traps(L)                  — states with no outgoing edges
    5. detect_trivial_loops(L)          — self-loops or 2-cycles
    6. graph_quality(L, start, goal)    — composite quality report
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from .primitives import Edge
from .landscape import Landscape


# ──────────────────────────────────────────────
# 1. Goal Reachability (BFS)
# ──────────────────────────────────────────────

def goal_reachable(L: Landscape, start: str, goal: str) -> bool:
    """Return True if *goal* is reachable from *start* via directed edges."""
    if start not in L.states or goal not in L.states:
        return False
    visited: Set[str] = set()
    queue: deque[str] = deque([start])
    while queue:
        node = queue.popleft()
        if node == goal:
            return True
        if node in visited:
            continue
        visited.add(node)
        for neighbor in L.admissible_neighbors(node):
            if neighbor not in visited:
                queue.append(neighbor)
    return False


# ──────────────────────────────────────────────
# 2. Happy Path (BFS shortest path)
# ──────────────────────────────────────────────

def find_happy_path(
    L: Landscape, start: str, goal: str,
) -> Optional[List[str]]:
    """Return the shortest path from *start* to *goal*, or None.

    Uses BFS on the directed edge structure — shortest in hop count,
    not in tension.  This is the "ideal" forward path the graph offers.
    """
    if start not in L.states or goal not in L.states:
        return None
    if start == goal:
        return [start]

    visited: Set[str] = set()
    queue: deque[List[str]] = deque([[start]])
    while queue:
        path = queue.popleft()
        node = path[-1]
        if node == goal:
            return path
        if node in visited:
            continue
        visited.add(node)
        for neighbor in L.admissible_neighbors(node):
            if neighbor not in visited:
                queue.append(path + [neighbor])
    return None


# ──────────────────────────────────────────────
# 3. Recovery Edges
# ──────────────────────────────────────────────

def find_recovery_edges(
    L: Landscape, happy_path: List[str],
) -> List[Edge]:
    """Return edges that lead from non-happy states back onto the happy path.

    A recovery edge is any edge (a → b) where:
      - a is NOT on the happy path
      - b IS on the happy path
    These are the "rescue routes" back to normal flow.
    """
    happy_set = set(happy_path)
    recovery: List[Edge] = []
    for edge in L.edges:
        if edge.source not in happy_set and edge.target in happy_set:
            recovery.append(edge)
    return recovery


# ──────────────────────────────────────────────
# 4. Trap Detection
# ──────────────────────────────────────────────

def detect_traps(L: Landscape) -> List[str]:
    """Return states with no outgoing edges (dead ends).

    A trap state absorbs the controller — it can never leave.
    The goal state is excluded (being a terminal is correct).
    """
    traps: List[str] = []
    for state in sorted(L.states):
        neighbors = L.admissible_neighbors(state)
        if not neighbors:
            traps.append(state)
    return traps


# ──────────────────────────────────────────────
# 5. Trivial Loop Detection
# ──────────────────────────────────────────────

def detect_trivial_loops(L: Landscape) -> List[Tuple[str, str]]:
    """Return 2-cycles: pairs (a, b) where a→b and b→a both exist.

    Self-loops (a→a) are included as (a, a).
    Each pair is reported once (sorted order).
    """
    edge_set = {(e.source, e.target) for e in L.edges}
    loops: List[Tuple[str, str]] = []
    seen: Set[Tuple[str, str]] = set()

    for (a, b) in edge_set:
        if a == b:
            # Self-loop
            key = (a, a)
            if key not in seen:
                seen.add(key)
                loops.append(key)
        elif (b, a) in edge_set:
            # 2-cycle
            key = (min(a, b), max(a, b))
            if key not in seen:
                seen.add(key)
                loops.append(key)

    return sorted(loops)


# ──────────────────────────────────────────────
# 6. Composite Quality Report
# ──────────────────────────────────────────────

@dataclass
class GraphQuality:
    """Result of graph_quality() — a composite structural assessment."""

    reachable: bool
    happy_path: Optional[List[str]]
    happy_path_length: int
    recovery_edges: List[Edge]
    recovery_count: int
    traps: List[str]
    trivial_loops: List[Tuple[str, str]]
    state_count: int
    edge_count: int
    score: float  # 0.0–1.0, higher is better

    @property
    def warnings(self) -> List[str]:
        """Human-readable warnings for structural issues."""
        w: List[str] = []
        if not self.reachable:
            w.append("CRITICAL: goal is not reachable from start")
        if self.happy_path is None:
            w.append("CRITICAL: no happy path exists")
        if self.traps:
            w.append(f"WARN: {len(self.traps)} trap state(s): {self.traps}")
        if self.trivial_loops:
            formatted = [f"{a}↔{b}" for a, b in self.trivial_loops]
            w.append(f"WARN: {len(self.trivial_loops)} trivial loop(s): {formatted}")
        if self.recovery_count == 0 and self.reachable:
            w.append("INFO: no recovery edges — failure may be unrecoverable")
        return w

    def ok(self) -> bool:
        """True if no critical issues (goal reachable, happy path exists)."""
        return self.reachable and self.happy_path is not None

    def summary(self) -> str:
        """Compact text summary for console output."""
        lines = [
            f"Graph Quality Score: {self.score:.2f}",
            f"  States: {self.state_count}, Edges: {self.edge_count}",
            f"  Reachable: {self.reachable}",
            f"  Happy path: {self.happy_path_length} steps"
            if self.happy_path else "  Happy path: NONE",
            f"  Recovery edges: {self.recovery_count}",
            f"  Traps: {len(self.traps)}",
            f"  Trivial loops: {len(self.trivial_loops)}",
        ]
        for w in self.warnings:
            lines.append(f"  ⚠ {w}")
        return "\n".join(lines)


def graph_quality(
    L: Landscape,
    start: str,
    goal: str,
) -> GraphQuality:
    """Run all structural checks and produce a composite quality report.

    Score heuristic (0.0–1.0):
      - Starts at 0.0 if goal unreachable
      - Base 0.5 if reachable
      - +0.2 if happy path ≤ 10 hops
      - +0.15 if at least 1 recovery edge per non-happy state
      - +0.1 if no traps (excluding goal)
      - +0.05 if no trivial loops
    """
    reachable = goal_reachable(L, start, goal)
    happy = find_happy_path(L, start, goal)

    happy_len = len(happy) - 1 if happy else 0  # edges, not nodes

    if happy:
        recovery = find_recovery_edges(L, happy)
    else:
        recovery = []

    traps_all = detect_traps(L)
    # Goal being a trap is fine (it's terminal)
    traps = [t for t in traps_all if t != goal]

    loops = detect_trivial_loops(L)

    state_count = len(L.states)
    edge_count = L.edge_count()

    # ── Score calculation ──
    score = 0.0
    if not reachable:
        # Unreachable graph gets 0 — no partial credit
        pass
    else:
        score += 0.5

        if happy_len <= 10:
            score += 0.2
        else:
            score += 0.1  # reachable but long

        # Recovery coverage: how many non-happy states have a path back?
        if happy:
            happy_set = set(happy)
            non_happy = [s for s in L.states if s not in happy_set]
            if non_happy:
                recovery_targets = {e.source for e in recovery}
                coverage = len(recovery_targets) / len(non_happy)
                score += 0.15 * coverage
            else:
                score += 0.15  # no non-happy states = perfect

        if not traps:
            score += 0.1

        if not loops:
            score += 0.05

    score = min(score, 1.0)

    return GraphQuality(
        reachable=reachable,
        happy_path=happy,
        happy_path_length=happy_len,
        recovery_edges=recovery,
        recovery_count=len(recovery),
        traps=traps,
        trivial_loops=loops,
        state_count=state_count,
        edge_count=edge_count,
        score=round(score, 3),
    )


def graph_quality_multigoal(
    L: Landscape,
    start: str,
    goals: Set[str],
) -> GraphQuality:
    """Like graph_quality but for multiple goal states.

    Uses the closest reachable goal for happy-path computation.
    All goals in *goals* that are terminal (no outgoing edges) are
    excluded from trap detection.
    """
    # Find closest reachable goal
    best_gq: Optional[GraphQuality] = None
    for g in sorted(goals):
        gq = graph_quality(L, start, g)
        if gq.reachable:
            if best_gq is None or gq.happy_path_length < best_gq.happy_path_length:
                best_gq = gq

    if best_gq is not None:
        # Re-check traps: exclude all goals (not just the single one)
        traps_all = detect_traps(L)
        traps = [t for t in traps_all if t not in goals]
        # Check reachability to ALL goals
        all_reachable = all(goal_reachable(L, start, g) for g in goals)
        return GraphQuality(
            reachable=all_reachable,
            happy_path=best_gq.happy_path,
            happy_path_length=best_gq.happy_path_length,
            recovery_edges=best_gq.recovery_edges,
            recovery_count=best_gq.recovery_count,
            traps=traps,
            trivial_loops=best_gq.trivial_loops,
            state_count=best_gq.state_count,
            edge_count=best_gq.edge_count,
            score=best_gq.score,
        )

    # No goal reachable
    return graph_quality(L, start, next(iter(goals)))
