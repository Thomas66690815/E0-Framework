"""
E₀ Controller — Residual Tension & Iteration Control (C37)
============================================================
Maps unresolved structural tension after a controller run and
decides whether to continue iterating.

Canonical foundation:
    Axiom A₀ — if Δ > 0 and a path with finite R exists,
    non-transition is structurally unstable.

    Applied to the iteration level: if high residual tension
    with admissible paths remains after a run, "stop now" is
    structurally unstable → iterate.

Core concepts:
    ResidualTension   — per-edge tension snapshot with change info
    ResidualTensionMap — full landscape tension picture after a run
    IterationVerdict  — should we continue, reflect, or present?

    compute_residual_map()  — build map from landscape + trace
    should_continue()       — Axiom A₀ applied to iteration level

The iteration count is not prescribed. It emerges from the
landscape's tension structure — the system iterates until
tension equilibrium, stagnation, or budget.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from .primitives import Edge
from .landscape import Landscape
from .controller import RunTrace


# ──────────────────────────────────────────────
# 1. Data structures
# ──────────────────────────────────────────────

@dataclass
class ResidualTension:
    """Per-edge tension snapshot after a controller run."""
    edge: Edge
    s_eff: float              # current effective tension
    delta_s: float            # change vs. run start (positive = grew)
    f_trace: float            # accumulated failure history
    visited: bool             # was this edge traversed in the run?


@dataclass
class ResidualTensionMap:
    """Complete tension picture of the landscape after a run."""
    residuals: List[ResidualTension]    # all edges, sorted by s_eff desc
    hotspots: List[ResidualTension]     # unvisited edges with high s_eff
    resolved: List[Edge]                # edges whose tension decreased
    amplified: List[Edge]               # edges whose tension increased
    iteration: int                      # which iteration produced this map
    max_residual: float                 # highest s_eff in map
    mean_residual: float                # average s_eff across all edges


@dataclass
class IterationVerdict:
    """Decision on whether to continue iterating."""
    should_continue: bool
    reason: str                         # "tension_active" | "equilibrium" | "stagnation" | "budget"
    should_reflect: bool                # inject reflection before next run?
    residual_map: ResidualTensionMap
    iteration: int


# ──────────────────────────────────────────────
# 2. Thresholds
# ──────────────────────────────────────────────

_HOTSPOT_THRESHOLD = 0.5       # S_eff > this to count as hotspot
_EQUILIBRIUM_THRESHOLD = 0.1   # max actionable residual < this → equilibrium
_STAGNATION_DELTA = 0.02       # |Δ mean_residual| < this between iterations → stagnation
_HOTSPOT_TOP_N = 5             # how many top hotspots to report


# ──────────────────────────────────────────────
# 3. Compute residual map
# ──────────────────────────────────────────────

def _snapshot_tensions(landscape: Landscape) -> Dict[Edge, float]:
    """Capture S_eff for every edge in the landscape."""
    tensions = {}
    for edge in landscape.edges:
        tensions[edge] = landscape.effective_tension(edge.source, edge.target)
    return tensions


def compute_residual_map(
    landscape: Landscape,
    trace: RunTrace,
    pre_tensions: Dict[Edge, float],
    iteration: int = 1,
) -> ResidualTensionMap:
    """Build a ResidualTensionMap from a completed run.

    Parameters
    ----------
    landscape : Landscape
        The landscape *after* the run (historization applied).
    trace : RunTrace
        The trace from the completed run.
    pre_tensions : dict
        S_eff snapshot taken *before* the run (from snapshot_tensions).
    iteration : int
        Current iteration number.
    """
    # Edges visited during the run
    visited_edges: Set[Edge] = set()
    for step in trace.steps:
        visited_edges.add(Edge(step.source, step.target))

    residuals: List[ResidualTension] = []
    resolved: List[Edge] = []
    amplified: List[Edge] = []

    for edge in landscape.edges:
        s_now = landscape.effective_tension(edge.source, edge.target)
        s_before = pre_tensions.get(edge, s_now)
        delta_s = s_now - s_before
        f_trace = landscape.historization.failure_trace(edge)

        residuals.append(ResidualTension(
            edge=edge,
            s_eff=s_now,
            delta_s=delta_s,
            f_trace=f_trace,
            visited=edge in visited_edges,
        ))

        if delta_s < -1e-6:
            resolved.append(edge)
        elif delta_s > 1e-6:
            amplified.append(edge)

    # Sort by tension descending
    residuals.sort(key=lambda r: r.s_eff, reverse=True)

    # Hotspots: high-tension edges that were NOT visited
    hotspots = [
        r for r in residuals
        if not r.visited and r.s_eff > _HOTSPOT_THRESHOLD
    ][:_HOTSPOT_TOP_N]

    finite_tensions = [r.s_eff for r in residuals if not math.isinf(r.s_eff)]
    max_res = max(finite_tensions) if finite_tensions else 0.0
    mean_res = sum(finite_tensions) / len(finite_tensions) if finite_tensions else 0.0

    return ResidualTensionMap(
        residuals=residuals,
        hotspots=hotspots,
        resolved=resolved,
        amplified=amplified,
        iteration=iteration,
        max_residual=max_res,
        mean_residual=mean_res,
    )


def snapshot_tensions(landscape: Landscape) -> Dict[Edge, float]:
    """Public API: capture pre-run tension snapshot."""
    return _snapshot_tensions(landscape)


# ──────────────────────────────────────────────
# 4. Should continue?
# ──────────────────────────────────────────────

def should_continue(
    residual_map: ResidualTensionMap,
    prev_map: Optional[ResidualTensionMap] = None,
    iteration: int = 1,
    max_iterations: int = 10,
    tension_threshold: float = _EQUILIBRIUM_THRESHOLD,
    stagnation_threshold: float = _STAGNATION_DELTA,
) -> IterationVerdict:
    """Decide whether to iterate again — Axiom A₀ at the iteration level.

    Stopping conditions (checked in order):
    1. Budget exhausted (max_iterations reached)
    2. Tension equilibrium (no actionable hotspot above threshold)
    3. Stagnation (mean tension didn't change between iterations)

    If none triggers → continue.  Reflection is recommended when
    hotspots exist but tension is trending upward (amplification).

    Parameters
    ----------
    residual_map : ResidualTensionMap
        Current iteration's tension picture.
    prev_map : ResidualTensionMap, optional
        Previous iteration's map (for stagnation detection).
    iteration : int
        Current iteration number.
    max_iterations : int
        Hard budget limit.
    tension_threshold : float
        Below this, residual tension is considered resolved.
    stagnation_threshold : float
        If |Δ mean_residual| < this between iterations, stagnation.
    """
    # 1. Budget
    if iteration >= max_iterations:
        return IterationVerdict(
            should_continue=False,
            reason="budget",
            should_reflect=False,
            residual_map=residual_map,
            iteration=iteration,
        )

    # Actionable hotspots: unvisited high-tension edges with admissible paths
    actionable = [h for h in residual_map.hotspots if h.s_eff > tension_threshold]

    # 2. Equilibrium — no actionable tension remaining
    if not actionable:
        return IterationVerdict(
            should_continue=False,
            reason="equilibrium",
            should_reflect=False,
            residual_map=residual_map,
            iteration=iteration,
        )

    # 3. Stagnation — tension landscape didn't change meaningfully
    if prev_map is not None:
        delta_mean = abs(residual_map.mean_residual - prev_map.mean_residual)
        if delta_mean < stagnation_threshold:
            return IterationVerdict(
                should_continue=False,
                reason="stagnation",
                should_reflect=True,   # stagnation warrants reflection
                residual_map=residual_map,
                iteration=iteration,
            )

    # Continue — tension is active and changing
    # Recommend reflection if tension is amplifying (getting worse)
    amplifying = len(residual_map.amplified) > len(residual_map.resolved)
    return IterationVerdict(
        should_continue=True,
        reason="tension_active",
        should_reflect=amplifying,
        residual_map=residual_map,
        iteration=iteration,
    )


# ──────────────────────────────────────────────
# 5. Formatting
# ──────────────────────────────────────────────

def format_residual_map(rmap: ResidualTensionMap) -> str:
    """Human-readable summary of a ResidualTensionMap."""
    lines = [
        f"ResidualTensionMap (iteration {rmap.iteration})",
        f"  Edges: {len(rmap.residuals)}",
        f"  Max S_eff: {rmap.max_residual:.4f}",
        f"  Mean S_eff: {rmap.mean_residual:.4f}",
        f"  Resolved: {len(rmap.resolved)} edges (tension decreased)",
        f"  Amplified: {len(rmap.amplified)} edges (tension increased)",
    ]
    if rmap.hotspots:
        lines.append(f"  Hotspots ({len(rmap.hotspots)}):")
        for h in rmap.hotspots:
            lines.append(
                f"    {h.edge.source}→{h.edge.target}: "
                f"S_eff={h.s_eff:.4f}, ΔS={h.delta_s:+.4f}, "
                f"F_trace={h.f_trace:.2f}"
            )
    else:
        lines.append("  Hotspots: none (equilibrium)")
    return "\n".join(lines)
