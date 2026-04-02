"""
Scoped Reflexion (C101)
==========================
Historization-driven locality for reflexive edge proposals.

Core insight: Global reflexion is the degenerate case of a fresh system.
As historization accumulates, reflexion should become local — because the
system's experience defines a natural scope.  "Global" and "local" are
not modes to choose; they are endpoints of a continuum governed by
trace_load.

Analogy (user): Physical laws were historized early and act globally
*because* they were the first inscriptions — global was local back then.
Later transitions are local and distinguishable from global.

Mechanism:
  locality = mean_load / (mean_load + μ)       ∈ [0, 1)
  radius   = max(1, ceil((1 − locality) × D))  where D = graph diameter
  scope    = BFS neighborhood of `current` within radius

When trace_load ≈ 0 (fresh):  locality ≈ 0, radius ≈ D → global
When trace_load >> μ:          locality → 1, radius → 1 → immediate neighbors only

Scoped reflexion replaces two things:
  1. Candidate selection: only states within scope
  2. Pattern extraction: only edges within scope inform parameters

Falsifiable claim: On historized landscapes, scoped reflexion produces
fewer proposals with higher or equal hit rate compared to global reflexion.
On fresh landscapes, scoped reflexion degenerates to global (no regression).

Usage:
  from e0_controller.scoped_reflexion import (
      compute_reflexion_scope,
      scoped_propose_edges,
      run_with_scoped_reflexion,
  )

  scope = compute_reflexion_scope(landscape, current)
  proposals = scoped_propose_edges(landscape, current, goal, scope)

  trace, proposals, scopes = run_with_scoped_reflexion(
      landscape, execute_fn, "S", "GOAL",
  )
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from statistics import median
from typing import Callable, Dict, List, Optional, Set, Tuple

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller, RunTrace
from e0_controller.reflexive_edge_proposal import (
    EdgePattern,
    ProposedEdge,
    apply_proposals,
    is_frontier,
    _bfs_reachable,
    _goal_proximity,
)


# ══════════════════════════════════════════════
# Types
# ══════════════════════════════════════════════

@dataclass
class ReflexionScope:
    """Historization-derived scope for reflexive proposals.

    Attributes:
        center: The node from which the scope radiates.
        radius: BFS depth limit (large for fresh, small for historized).
        included_states: States within the scope boundary.
        locality: Degree of localization [0, 1). 0 = global, →1 = fully local.
        mean_load: Mean trace_load across all edges (diagnostic).
        rationale: Human-readable explanation.
    """
    center: str
    radius: int
    included_states: Set[str] = field(default_factory=set)
    locality: float = 0.0
    mean_load: float = 0.0
    rationale: str = ""

    @property
    def is_global(self) -> bool:
        """True if scope covers all states in the landscape."""
        return self.locality < 0.05

    @property
    def scope_size(self) -> int:
        return len(self.included_states)


# ══════════════════════════════════════════════
# Scope computation
# ══════════════════════════════════════════════

def _bfs_neighborhood(
    landscape: Landscape,
    center: str,
    radius: int,
) -> Set[str]:
    """BFS neighborhood: states reachable within `radius` hops (undirected)."""
    visited: Set[str] = {center}
    frontier: Set[str] = {center}
    for _ in range(radius):
        next_frontier: Set[str] = set()
        for node in frontier:
            # Outgoing edges
            for edge in landscape._delta:
                if edge.source == node and edge.target not in visited:
                    next_frontier.add(edge.target)
                elif edge.target == node and edge.source not in visited:
                    next_frontier.add(edge.source)
        visited.update(next_frontier)
        frontier = next_frontier
        if not frontier:
            break
    return visited


def _graph_diameter_estimate(landscape: Landscape) -> int:
    """Estimate graph diameter via BFS from a sample of nodes.

    Uses undirected reachability. Returns max eccentricity over
    sampled nodes. If graph is disconnected, returns max over
    the largest component.
    """
    states = sorted(landscape.states)
    if len(states) <= 1:
        return 1

    # Build adjacency (undirected) for fast BFS
    adj: Dict[str, Set[str]] = {s: set() for s in states}
    for edge in landscape._delta:
        adj[edge.source].add(edge.target)
        adj[edge.target].add(edge.source)

    max_dist = 1
    # Sample up to 5 nodes for efficiency
    sample = states[:min(5, len(states))]
    for start in sample:
        dist: Dict[str, int] = {start: 0}
        queue = deque([start])
        while queue:
            node = queue.popleft()
            for nb in adj.get(node, ()):
                if nb not in dist:
                    dist[nb] = dist[node] + 1
                    queue.append(nb)
        if dist:
            max_dist = max(max_dist, max(dist.values()))

    return max(max_dist, 1)


def compute_reflexion_scope(
    landscape: Landscape,
    current: str,
    *,
    goal: Optional[str] = None,
    mu: float = 5.0,
) -> ReflexionScope:
    """Compute reflexion scope from historization state.

    The scope is the union of BFS neighborhoods from `current` and
    `goal` (if provided), both limited by the historization-derived
    radius.  Including the goal neighborhood ensures that proposals
    can bridge disconnected regions — the system needs to know both
    where it IS and where it NEEDS TO GO.

    Parameters:
        landscape: Current landscape (with historization)
        current: Center node for scope
        goal: Optional goal node (if given, its neighborhood is included)
        mu: Half-load parameter (same as inertia_factor default).
            When mean_load == mu, locality = 0.5.

    Returns:
        ReflexionScope with included_states, locality, and radius.
    """
    hist = landscape.historization
    edges = list(landscape._delta.keys())

    if not edges:
        return ReflexionScope(
            center=current,
            radius=1,
            included_states={current},
            locality=0.0,
            mean_load=0.0,
            rationale="No edges — trivial scope",
        )

    # Compute mean trace_load across all edges
    loads = [hist.trace_load(e) for e in edges]
    mean_load = sum(loads) / len(loads)

    # Locality: saturating function of mean_load
    # locality ∈ [0, 1), approaches 1 as mean load grows
    locality = mean_load / (mean_load + mu)

    # Graph diameter (cached idea: we compute once per call, cheap enough)
    diameter = _graph_diameter_estimate(landscape)

    # Radius: inversely proportional to locality
    # Fresh (locality≈0): radius ≈ diameter (global)
    # Historized (locality→1): radius → 1 (immediate neighborhood)
    radius = max(1, math.ceil((1.0 - locality) * diameter))

    # BFS neighborhood: center + goal (both within radius)
    included = _bfs_neighborhood(landscape, current, radius)
    if goal is not None and goal in landscape.states:
        included |= _bfs_neighborhood(landscape, goal, radius)

    return ReflexionScope(
        center=current,
        radius=radius,
        included_states=included,
        locality=round(locality, 4),
        mean_load=round(mean_load, 4),
        rationale=(
            f"mean_load={mean_load:.2f}, μ={mu}, "
            f"locality={locality:.3f}, "
            f"diameter={diameter}, radius={radius}, "
            f"scope={len(included)}/{len(landscape.states)} states"
        ),
    )


# ══════════════════════════════════════════════
# Scoped pattern extraction
# ══════════════════════════════════════════════

def scoped_experienced_pattern(
    landscape: Landscape,
    scope: ReflexionScope,
) -> EdgePattern:
    """Extract Δ/R₀ patterns from edges within scope only.

    Like experienced_pattern() but restricted to edges whose source
    AND target are both within scope.included_states.
    """
    hist = landscape.historization
    deltas: List[float] = []
    resistances: List[float] = []
    total_in_scope = 0

    for edge in landscape._delta:
        if edge.source in scope.included_states and edge.target in scope.included_states:
            total_in_scope += 1
            load = hist.trace_load(edge)
            if load > 0:
                quality = hist.trace_quality(edge)
                if quality > 0:  # more success than failure
                    deltas.append(landscape._delta[edge])
                    resistances.append(landscape._R0[edge])

    if not deltas:
        # No local success — fall back to scope-wide medians
        scope_deltas = sorted(
            landscape._delta[e]
            for e in landscape._delta
            if e.source in scope.included_states and e.target in scope.included_states
        )
        scope_r0s = sorted(
            landscape._R0[e]
            for e in landscape._R0
            if e.source in scope.included_states and e.target in scope.included_states
        )
        return EdgePattern(
            median_delta=scope_deltas[len(scope_deltas) // 2] if scope_deltas else 0.3,
            median_r0=scope_r0s[len(scope_r0s) // 2] if scope_r0s else 0.5,
            sample_size=0,
            coverage=0.0,
        )

    return EdgePattern(
        median_delta=median(deltas),
        median_r0=median(resistances),
        sample_size=len(deltas),
        coverage=len(deltas) / max(total_in_scope, 1),
    )


# ══════════════════════════════════════════════
# Scoped proposal engine
# ══════════════════════════════════════════════

def _find_scoped_candidates(
    landscape: Landscape,
    current: str,
    scope: ReflexionScope,
) -> List[str]:
    """States within scope not directly reachable from current."""
    reachable = {e.target for e in landscape._delta if e.source == current}
    return [
        s for s in scope.included_states
        if s != current and s not in reachable
    ]


def scoped_propose_edges(
    landscape: Landscape,
    current: str,
    goal: str,
    scope: Optional[ReflexionScope] = None,
    *,
    max_proposals: int = 5,
    proactive: bool = True,
    mu: float = 5.0,
) -> List[ProposedEdge]:
    """Propose edges within historization-derived scope.

    If scope is None, computes it from landscape state.
    Scoped version of propose_edges(): candidates and pattern extraction
    are both restricted to the scope boundary.

    Parameters:
        landscape: Current landscape
        current: Current position (proposal source)
        goal: Navigation goal
        scope: Pre-computed scope (or None → auto-compute)
        max_proposals: Maximum proposals
        proactive: Use median R₀ (True) or inflate by confidence (False)
        mu: Half-load parameter for scope computation
    """
    if scope is None:
        scope = compute_reflexion_scope(landscape, current, goal=goal, mu=mu)

    candidates = _find_scoped_candidates(landscape, current, scope)
    if not candidates:
        return []

    pattern = scoped_experienced_pattern(landscape, scope)
    confidence = min(pattern.coverage, 0.8)

    if proactive:
        r0_scaled = pattern.median_r0
    else:
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
                f"Scoped (locality={scope.locality:.2f}, "
                f"radius={scope.radius}, "
                f"{scope.scope_size} states): "
                f"Δ={pattern.median_delta:.2f}, "
                f"R₀={pattern.median_r0:.2f}, "
                f"confidence={confidence:.2f} "
                f"from {pattern.sample_size} local edges"
            ),
        ))

    # Prioritize: targets closer to goal first
    proposals.sort(key=lambda p: _goal_proximity(landscape, p.target, goal))

    return proposals[:max_proposals]


# ══════════════════════════════════════════════
# Integrated scoped runner
# ══════════════════════════════════════════════

ExecuteFn = Callable[[str, str], Outcome]


def run_with_scoped_reflexion(
    landscape: Landscape,
    execute_fn: ExecuteFn,
    start: str,
    goal: str,
    max_cycles: int = 50,
    max_proposals: int = 5,
    mu: float = 5.0,
) -> Tuple[RunTrace, List[ProposedEdge], List[ReflexionScope]]:
    """Run with historization-scoped proactive reflexion.

    Like run_with_proactive_reflexion (C57) but proposals are scoped
    by the system's historization state.  Fresh systems get global
    proposals, historized systems get local proposals.

    Returns:
        (trace, all_proposals, all_scopes)
        all_scopes: scope computed at each frontier (diagnostic trace)
    """
    all_proposals: List[ProposedEdge] = []
    all_scopes: List[ReflexionScope] = []
    proposed_from: Set[str] = set()

    ctrl = E0Controller(landscape, execute_fn, alpha=2.0, recent_k=3)
    trace = RunTrace()
    current = start

    for cycle in range(max_cycles):
        if current == goal:
            break

        # Proactive: at every frontier, propose with scope
        if current not in proposed_from and is_frontier(landscape, current, goal):
            scope = compute_reflexion_scope(landscape, current, goal=goal, mu=mu)
            all_scopes.append(scope)

            proposals = scoped_propose_edges(
                landscape, current, goal, scope,
                max_proposals=max_proposals,
                proactive=True,
                mu=mu,
            )
            proposed_from.add(current)
            if proposals:
                apply_proposals(landscape, proposals)
                all_proposals.extend(proposals)
                ctrl = E0Controller(
                    landscape, execute_fn, alpha=2.0, recent_k=3,
                )

        step = ctrl.cycle(current)
        if step is None:
            break
        trace.steps.append(step)
        current = step.target

    return trace, all_proposals, all_scopes
