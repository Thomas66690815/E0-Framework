"""
Reflexive Edge Proposal (C56)
================================
When the controller is stuck at a frontier, this module proposes
hypothesis edges based on accumulated experience.

Core insight: Historisierung informiert Topologie, nicht nur Widerstand.

Pipeline:
  1. Detect frontier (controller stuck — no forward progress)
  2. Find candidate targets (known states not directly reachable)
  3. Estimate parameters from successful edge patterns
  4. Propose hypothesis edges with confidence-scaled parameters
  5. Apply to landscape; navigation validates or falsifies

Usage:
  from e0_controller.reflexive_edge_proposal import (
      propose_edges, apply_proposals, run_with_reflexion,
  )

  # Standalone proposal:
  proposals = propose_edges(landscape, "FRONTIER", "GOAL")
  apply_proposals(landscape, proposals)

  # Integrated run:
  trace, proposals = run_with_reflexion(
      landscape, execute_fn, "S", "GOAL",
  )
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from statistics import median
from typing import Callable, Dict, List, Optional, Set, Tuple

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller, HybridMode, RunTrace


# ══════════════════════════════════════════════
# Types
# ══════════════════════════════════════════════

@dataclass
class ProposedEdge:
    """A hypothesis edge derived from reflexion."""
    source: str
    target: str
    delta: float
    resistance: float
    confidence: float       # 0..1; higher = more certain
    rationale: str


@dataclass
class EdgePattern:
    """Statistical summary of successful edge parameters."""
    median_delta: float
    median_r0: float
    sample_size: int         # how many successful edges informed this
    coverage: float          # fraction of all edges that are successful


@dataclass
class ReflexionResult:
    """Outcome of a reflexive edge proposal cycle."""
    proposals: List[ProposedEdge]
    pattern: EdgePattern
    edges_added: int
    frontier_node: str


# ══════════════════════════════════════════════
# Pattern extraction
# ══════════════════════════════════════════════

def experienced_pattern(landscape: Landscape) -> EdgePattern:
    """Extract Δ/R₀ patterns from successfully historized edges.

    Looks at all edges with trace_load > 0 and trace_quality > 0
    (more successes than failures). Returns median Δ and R₀ as the
    "what has worked" template.
    """
    hist = landscape.historization
    deltas: List[float] = []
    resistances: List[float] = []

    for edge in landscape._delta:
        load = hist.trace_load(edge)
        if load > 0:
            quality = hist.trace_quality(edge)
            if quality > 0:  # more success than failure
                deltas.append(landscape._delta[edge])
                resistances.append(landscape._R0[edge])

    total_edges = len(landscape._delta)

    if not deltas:
        # No successful experience — use landscape-wide medians as fallback
        all_deltas = sorted(landscape._delta.values())
        all_r0s = sorted(landscape._R0.values())
        return EdgePattern(
            median_delta=all_deltas[len(all_deltas) // 2] if all_deltas else 0.3,
            median_r0=all_r0s[len(all_r0s) // 2] if all_r0s else 0.5,
            sample_size=0,
            coverage=0.0,
        )

    return EdgePattern(
        median_delta=median(deltas),
        median_r0=median(resistances),
        sample_size=len(deltas),
        coverage=len(deltas) / max(total_edges, 1),
    )


# ══════════════════════════════════════════════
# Frontier detection
# ══════════════════════════════════════════════

def is_frontier(landscape: Landscape, current: str, goal: str) -> bool:
    """Is `current` a frontier node — no forward path to goal?

    A node is a frontier if goal is not reachable from it via
    existing edges (BFS).
    """
    return not _bfs_reachable(landscape, current, goal)


def _bfs_reachable(landscape: Landscape, start: str, target: str) -> bool:
    """Check if target is reachable from start via existing edges."""
    visited: Set[str] = set()
    queue = deque([start])
    while queue:
        node = queue.popleft()
        if node == target:
            return True
        if node in visited:
            continue
        visited.add(node)
        for edge in landscape._delta:
            if edge.source == node and edge.target not in visited:
                queue.append(edge.target)
    return False


def _outgoing_neighbors(landscape: Landscape, node: str) -> Set[str]:
    """All direct neighbors reachable from node."""
    return {e.target for e in landscape._delta if e.source == node}


# ══════════════════════════════════════════════
# Candidate selection
# ══════════════════════════════════════════════

def find_candidate_targets(
    landscape: Landscape,
    current: str,
) -> List[str]:
    """States in the landscape not directly reachable from current."""
    reachable = _outgoing_neighbors(landscape, current)
    return [s for s in landscape.states
            if s != current and s not in reachable]


def _goal_proximity(
    landscape: Landscape,
    target: str,
    goal: str,
) -> int:
    """Lower is better. 0=is goal, 1=has path to goal, 2=no path."""
    if target == goal:
        return 0
    if _bfs_reachable(landscape, target, goal):
        return 1
    return 2


# ══════════════════════════════════════════════
# Proposal engine
# ══════════════════════════════════════════════

def propose_edges(
    landscape: Landscape,
    current: str,
    goal: str,
    max_proposals: int = 5,
    proactive: bool = False,
) -> List[ProposedEdge]:
    """Propose hypothesis edges from current based on experience.

    Pipeline:
      1. Find candidate targets (known states not directly reachable)
      2. Extract parameter pattern from successful edges
      3. Scale resistance by confidence (reactive) or use median (proactive)
      4. Sort by goal proximity (prefer targets closer to goal)

    proactive: if True, use median R₀ directly (best guess, competitive
      with existing edges).  Reactive mode inflates R₀ by confidence
      (low confidence → cautious hypothesis).
    """
    candidates = find_candidate_targets(landscape, current)
    if not candidates:
        return []

    pattern = experienced_pattern(landscape)
    confidence = min(pattern.coverage, 0.8)  # cap: never fully certain

    if proactive:
        # Proactive: median R₀ is the best-guess estimate —
        # "ich ordne es ein mit dem was ich habe"
        r0_scaled = pattern.median_r0
    else:
        # Reactive: low confidence → inflate R₀ (more cautious)
        r0_scaled = pattern.median_r0 / max(confidence, 0.1)

    proposals = []
    for target in candidates:
        proposals.append(ProposedEdge(
            source=current,
            target=target,
            delta=pattern.median_delta,
            resistance=r0_scaled,
            confidence=round(confidence, 3),
            rationale=(
                f"Pattern: Δ={pattern.median_delta:.2f}, "
                f"R₀={pattern.median_r0:.2f}, "
                f"confidence={confidence:.2f} "
                f"from {pattern.sample_size} successful edges"
            ),
        ))

    # Prioritize: targets closer to goal first
    proposals.sort(key=lambda p: _goal_proximity(landscape, p.target, goal))

    return proposals[:max_proposals]


def apply_proposals(
    landscape: Landscape,
    proposals: List[ProposedEdge],
) -> int:
    """Add proposed edges to landscape. Returns count of edges added."""
    added = 0
    for p in proposals:
        if not landscape.has_edge(p.source, p.target):
            landscape.add_edge(p.source, p.target,
                               delta=p.delta, resistance=p.resistance)
            added += 1
    return added


# ══════════════════════════════════════════════
# Detection: is the controller stuck?
# ══════════════════════════════════════════════

def detect_stuckness(trace: RunTrace, window: int = 8) -> bool:
    """Is the controller cycling without progress?

    True if the last `window` steps visit at most ⌊window·⅔⌋
    distinct states — indicating a loop.  A 4-node cycle in an
    8-step window yields 4 unique ≤ 5 → stuck.
    """
    if len(trace.steps) < window:
        return False
    recent = [s.target for s in trace.steps[-window:]]
    return len(set(recent)) <= max(window * 2 // 3, 2)


# ══════════════════════════════════════════════
# Integrated run
# ══════════════════════════════════════════════

ExecuteFn = Callable[[str, str], Outcome]


def run_with_reflexion(
    landscape: Landscape,
    execute_fn: ExecuteFn,
    start: str,
    goal: str,
    max_cycles: int = 50,
    proposal_trigger: int = 8,
    max_proposals: int = 5,
    stuckness_window: int = 8,
) -> Tuple[RunTrace, List[ProposedEdge]]:
    """Run controller with reflexive edge proposal on stuckness.

    Phase 1: Run normally for up to `proposal_trigger` cycles.
    If stuck (cycling without progress) AND goal unreachable:
      → Propose edges from current position
      → Apply proposals to landscape
      → Continue running for remaining cycles

    Returns (trace, proposals_applied).
    """
    all_proposals: List[ProposedEdge] = []

    ctrl = E0Controller(landscape, execute_fn, alpha=2.0, recent_k=3)
    trace = RunTrace()
    current = start
    proposal_applied = False

    for cycle in range(max_cycles):
        # Goal check
        if current == goal:
            break

        # Reflexion trigger: stuck + goal unreachable + not yet proposed
        if (not proposal_applied
                and cycle >= proposal_trigger
                and detect_stuckness(trace, stuckness_window)
                and is_frontier(landscape, current, goal)):
            proposals = propose_edges(
                landscape, current, goal, max_proposals,
            )
            if proposals:
                apply_proposals(landscape, proposals)
                all_proposals.extend(proposals)
                proposal_applied = True
                # Rebuild controller to pick up new edges
                ctrl = E0Controller(
                    landscape, execute_fn, alpha=2.0, recent_k=3,
                )

        step = ctrl.cycle(current)
        if step is None:
            break
        trace.steps.append(step)
        current = step.target

    return trace, all_proposals


def run_with_proactive_reflexion(
    landscape: Landscape,
    execute_fn: ExecuteFn,
    start: str,
    goal: str,
    max_cycles: int = 50,
    max_proposals: int = 5,
) -> Tuple[RunTrace, List[ProposedEdge]]:
    """Run with proactive reflexion: reflect BEFORE navigation, not after.

    Stufe-2 insight: "Wenn ich ein neues Thema habe, reflektiere ich dieses
    zuerst mit dem was ich habe und leite daraus erst meine möglichen
    Kanten ab.  Das ist der Schritt BEVOR ich in eine Falle tappe."

    At EVERY step, before choosing an edge:
      - Is current a frontier (no path to goal)?  → Propose immediately.
      - No stuckness detection needed, no warmup.
      - Can propose at MULTIPLE frontier nodes (cascading gaps).

    Key structural differences from run_with_reflexion (C56 reactive):
      - No proposal_trigger delay
      - No stuckness_window
      - Proposes at every new frontier, not just once
      - proposed_from set prevents infinite re-proposal at same node

    Returns (trace, all_proposals_applied).
    """
    all_proposals: List[ProposedEdge] = []
    proposed_from: Set[str] = set()

    ctrl = E0Controller(landscape, execute_fn, alpha=2.0, recent_k=3)
    trace = RunTrace()
    current = start

    for cycle in range(max_cycles):
        if current == goal:
            break

        # PROACTIVE: at every arrival, check if this is new terrain
        if current not in proposed_from and is_frontier(landscape, current, goal):
            proposals = propose_edges(
                landscape, current, goal, max_proposals,
                proactive=True,
            )
            proposed_from.add(current)
            if proposals:
                apply_proposals(landscape, proposals)
                all_proposals.extend(proposals)
                # Rebuild controller to pick up new edges
                ctrl = E0Controller(
                    landscape, execute_fn, alpha=2.0, recent_k=3,
                )

        step = ctrl.cycle(current)
        if step is None:
            break
        trace.steps.append(step)
        current = step.target

    return trace, all_proposals
