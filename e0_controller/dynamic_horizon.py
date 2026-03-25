"""
E₀ Dynamic Horizon Strategies (Phase 3i)
============================================

Pluggable horizon selection for the amplitude overlay.

Instead of a single global hybrid_horizon, the controller can use a
strategy function that returns the horizon per decision point:

    h = strategy(controller, current)

This module provides:

  fixed(h)              — constant horizon (backwards-compatible default)
  topology_adaptive     — adjusts based on branching factor and goal distance
  capped_adaptive       — topology_adaptive with explicit ceiling

All strategies return an integer h >= 1.

Design principles (from E₀ canon):
  - Bounded computation: O(k^h) path enumeration must stay small
  - Admissibility-preserving: selecting h does NOT change which actions are valid
  - Geometry-independent: strategy picks depth; geometry picks path filter
"""

from __future__ import annotations

import math
from typing import Callable, Optional, Protocol, Set

# Forward reference — avoids circular import at runtime.
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .controller import E0Controller


# ──────────────────────────────────────────────
# Protocol & type alias
# ──────────────────────────────────────────────

class HorizonStrategy(Protocol):
    """Callable that computes the horizon for a given decision point."""
    def __call__(self, controller: "E0Controller", current: str) -> int: ...


# ──────────────────────────────────────────────
# 1. Fixed strategy (default — backwards-compatible)
# ──────────────────────────────────────────────

def fixed(h: int = 3) -> HorizonStrategy:
    """Return a strategy that always returns the same horizon."""
    if h < 1:
        raise ValueError(f"Horizon must be >= 1, got {h}")

    def _fixed(controller: "E0Controller", current: str) -> int:
        return h
    return _fixed


# ──────────────────────────────────────────────
# 2. Topology-adaptive strategy
# ──────────────────────────────────────────────

# Conservative defaults — keep O(k^h) manageable.
_DEFAULT_H_MIN = 2
_DEFAULT_H_MAX = 6
_DEFAULT_BRANCH_THRESHOLD = 3   # branching factor above which h is reduced


def _branching_factor(controller: "E0Controller", state: str) -> int:
    """Number of admissible neighbors from the given state."""
    return len(controller._admissible_neighbors(state))


def _bfs_goal_distance(
    controller: "E0Controller",
    start: str,
    goals: Set[str],
    max_depth: int = 20,
) -> Optional[int]:
    """Shortest path length (in edges) from start to any goal state.

    Returns None if no goal is reachable within max_depth.
    Uses BFS on the admissible neighbor graph.
    """
    if start in goals:
        return 0
    visited = {start}
    frontier = [start]
    depth = 0
    while frontier and depth < max_depth:
        depth += 1
        next_frontier = []
        for node in frontier:
            for nbr in controller._admissible_neighbors(node):
                if nbr in goals:
                    return depth
                if nbr not in visited:
                    visited.add(nbr)
                    next_frontier.append(nbr)
        frontier = next_frontier
    return None


def topology_adaptive(
    goals: Optional[Set[str]] = None,
    h_min: int = _DEFAULT_H_MIN,
    h_max: int = _DEFAULT_H_MAX,
    branch_threshold: int = _DEFAULT_BRANCH_THRESHOLD,
) -> HorizonStrategy:
    """Horizon that adapts to local branching factor and goal distance.

    Rules:
      1. Start from the distance to the nearest goal (clamped to [h_min, h_max]).
         If no goal info, start from h_max.
      2. If the local branching factor > branch_threshold, reduce by 1
         (to limit O(k^h) blowup).
      3. Clamp result to [h_min, h_max].

    This captures two key insights from the E₀ evidence:
      - Gordian trap needs h >= 5 (distance ~ 5 edges to goal)
      - Diamond domain converges at h ~ 4
      - High branching pushes cost up → reduce h adaptively
    """
    effective_goals = goals or set()

    def _topology_adaptive(controller: "E0Controller", current: str) -> int:
        # Use controller.hybrid_goals if strategy goals not provided.
        goal_set = effective_goals or (controller.hybrid_goals or set())

        # Base: distance to goal (or h_max if unknown)
        if goal_set:
            dist = _bfs_goal_distance(controller, current, goal_set, max_depth=h_max)
            base = dist if dist is not None else h_max
        else:
            base = h_max

        # Adjust for branching
        bf = _branching_factor(controller, current)
        if bf > branch_threshold:
            base -= 1

        return max(h_min, min(h_max, base))

    return _topology_adaptive


# ──────────────────────────────────────────────
# 3. Capped adaptive (convenience wrapper)
# ──────────────────────────────────────────────

def capped_adaptive(
    h_cap: int = 5,
    goals: Optional[Set[str]] = None,
    h_min: int = _DEFAULT_H_MIN,
    branch_threshold: int = _DEFAULT_BRANCH_THRESHOLD,
) -> HorizonStrategy:
    """Topology-adaptive with an explicit ceiling.

    Useful when the domain is known to need at most h_cap depth.
    """
    return topology_adaptive(
        goals=goals,
        h_min=h_min,
        h_max=h_cap,
        branch_threshold=branch_threshold,
    )
