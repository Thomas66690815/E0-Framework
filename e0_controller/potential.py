"""
E₀ Controller — Potential & Helmholtz Decomposition
=====================================================
Diskrete Helmholtz-Zerlegung des Transitionsfelds v in orthogonale
Gradient- und Rotationskomponenten.

Spec coverage: §9 (Lokales Potential Φ), §10 (v_grad), §11 (v_rot).

Core equations (true discrete Helmholtz):
    div(v)(x) = Σ_y v(x→y) − Σ_y v(y→x)              — Divergenz
    L · Φ = div(v)                                      — Graph-Laplacian-Gleichung
    v_grad(x, y) = Φ(x) − Φ(y)                         — §10 Gradient-Komponente
    v_rot(x, y)  = v(x, y) − v_grad(x, y)              — §11 Rotations-Komponente

Mathematische Garantie:
    Diese Zerlegung löst die Graph-Laplacian-Gleichung L·Φ = div(v).
    Dadurch wird Φ so bestimmt, dass v_grad und v_rot orthogonal im
    Kantenraum sind: ⟨v_grad, v_rot⟩_E = 0.

    Konsequenz: Holonomie Hol(γ) = Σ_γ v_rot ist wohldefiniert und
    repräsentiert exakt den nicht-konservativen Anteil des Feldes.

    Vorherige Implementierung (bis v0.9.1) benutzte Φ(x) = Σ Δ·R_eff
    als Heuristik. Das war spec-aligned, aber nicht orthogonal.

Konvention für gerichtete Kanten:
    - v(x, y) ist nur definiert, wenn Kante x→y existiert.
    - v_grad(x, y) = Φ(x) − Φ(y) ist für jedes Paar berechenbar.
    - v_rot(x, y) ist nur sinnvoll für existierende Kanten.
    - Fehlende Kante → v(x, y) = 0.0 (keine Transitionskapazität).

Requires: numpy (for graph Laplacian least-squares solve).
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional

import numpy as np

from .landscape import Landscape


# ──────────────────────────────────────────────
# 1. Divergence and Graph Laplacian
# ──────────────────────────────────────────────

def div_v(L: Landscape, x: str) -> float:
    """
    Divergence of the transition field at node x.

    div(v)(x) = Σ_y v(x→y) − Σ_y v(y→x)

    Positive: net outflow (source-like node).
    Negative: net inflow (sink-like node).
    Zero: balanced flow.
    """
    outflow = 0.0
    inflow = 0.0
    for edge in L.edges:
        if edge.source == x:
            outflow += L.transition_field(x, edge.target)
        if edge.target == x:
            inflow += L.transition_field(edge.source, x)
    return outflow - inflow


def graph_laplacian(L: Landscape) -> tuple:
    """
    Build the graph Laplacian L = D − A for the underlying undirected
    weighted graph derived from the directed edge set.

    For the Helmholtz decomposition on edge space, we use the
    *combinatorial* Laplacian of the undirected graph where edge
    weight w(x,y) = number of directed edges between x and y.

    Returns:
        (laplacian, state_list):
            laplacian — n×n numpy array (symmetric, positive semi-definite)
            state_list — ordered list of state names (index mapping)
    """
    states = sorted(L.states)
    n = len(states)
    idx = {s: i for i, s in enumerate(states)}

    lap = np.zeros((n, n), dtype=np.float64)

    for edge in L.edges:
        i = idx[edge.source]
        j = idx[edge.target]
        # Undirected weight: each directed edge contributes 1
        lap[i, j] -= 1.0
        lap[j, i] -= 1.0
        lap[i, i] += 1.0
        lap[j, j] += 1.0

    return lap, states


def _solve_helmholtz(L: Landscape) -> Dict[str, float]:
    """
    Solve L · Φ = div(v) for the potential Φ.

    The graph Laplacian L is singular (rank n-1 for connected graph),
    so we pin the first node to Φ = 0 and solve the reduced system.

    Uses a per-Landscape cache keyed on (edge_count, τ) to avoid
    redundant O(n³) solves within a single controller step.

    Returns dict mapping state name → Φ value.
    """
    cache_key = (L.edge_count(), L.historization.tau)
    cached = getattr(L, '_phi_cache', None)
    if cached is not None and getattr(L, '_phi_cache_key', None) == cache_key:
        return cached

    lap, states = graph_laplacian(L)
    n = len(states)

    if n == 0:
        result: Dict[str, float] = {}
        L._phi_cache = result
        L._phi_cache_key = cache_key
        return result
    if n == 1:
        result = {states[0]: 0.0}
        L._phi_cache = result
        L._phi_cache_key = cache_key
        return result

    # Build divergence vector
    div_vec = np.array([div_v(L, s) for s in states], dtype=np.float64)

    # Pin node 0 to Φ = 0: remove row/col 0, solve reduced system
    L_reduced = lap[1:, 1:]
    b_reduced = div_vec[1:]

    # Solve via least-squares (handles rank deficiency gracefully)
    phi_reduced, _, _, _ = np.linalg.lstsq(L_reduced, b_reduced, rcond=None)

    # Reconstruct full Φ vector with pinned node
    phi_full = np.zeros(n, dtype=np.float64)
    phi_full[1:] = phi_reduced

    result = {states[i]: float(phi_full[i]) for i in range(n)}
    L._phi_cache = result
    L._phi_cache_key = cache_key
    return result


# ──────────────────────────────────────────────
# 2. Public API — Potential Functions
# ──────────────────────────────────────────────

def phi(L: Landscape, x: str) -> float:
    """
    §9: Potential via true discrete Helmholtz decomposition.

    Φ(x) is determined by solving L · Φ = div(v), where L is the
    graph Laplacian and div(v) is the divergence of the transition field.

    This ensures v_grad ⊥ v_rot in the edge inner product space.

    Interpretation: Φ(x) measures the "structural pressure" at node x.
    High Φ = strong net outflow drive. Low Φ = sink-like.
    Relative differences Φ(x) − Φ(y) drive gradient flow.
    """
    pm = _solve_helmholtz(L)
    return pm.get(x, 0.0)


def phi_map(L: Landscape) -> Dict[str, float]:
    """Φ(x) for all states. Convenience wrapper."""
    return _solve_helmholtz(L)


def v_raw(L: Landscape, x: str, y: str) -> float:
    """
    §2.4: Transition field v(x, y) = Δ(x,y) · exp(-S_eff(x→y))

    Wraps Landscape.transition_field().
    Returns 0.0 if edge does not exist (no transition capacity).
    """
    return L.transition_field(x, y)


def v_grad(L: Landscape, x: str, y: str) -> float:
    """
    §10: Gradient-Komponente des Transitionsfelds.

    v_grad(x, y) = Φ(x) − Φ(y)

    The conservative part — derivable from the Helmholtz potential.
    Can be computed for any pair of states, even without a direct edge.
    Orthogonal to v_rot by construction.
    """
    return phi(L, x) - phi(L, y)


def v_rot(L: Landscape, x: str, y: str) -> Optional[float]:
    """
    §11: Rotations-Komponente des Transitionsfelds.

    v_rot(x, y) = v(x, y) − v_grad(x, y)

    The non-conservative remainder — orthogonal to v_grad by
    construction of the Helmholtz potential Φ.

    This is what creates holonomy: Hol(γ) = Σ_γ v_rot.
    Only defined for edges that actually exist in the landscape.

    Returns None if edge x→y does not exist (v_rot is undefined there).
    """
    delta = L.difference(x, y)
    if delta is None:
        return None  # Edge does not exist
    v = v_raw(L, x, y)
    vg = v_grad(L, x, y)
    return v - vg


def decomposition(L: Landscape, x: str, y: str) -> Dict[str, Optional[float]]:
    """
    Full v-decomposition for an edge.

    Returns:
        v_raw:  transition field value (0.0 if no edge)
        v_grad: gradient component (always computable)
        v_rot:  rotation component (None if no edge)
        phi_x:  potential at source
        phi_y:  potential at target
    """
    return {
        "v_raw": v_raw(L, x, y),
        "v_grad": v_grad(L, x, y),
        "v_rot": v_rot(L, x, y),
        "phi_x": phi(L, x),
        "phi_y": phi(L, y),
    }


def decomposition_table(L: Landscape) -> list:
    """
    Full decomposition for all edges in the landscape.
    Returns list of dicts, one per edge.
    """
    rows = []
    for edge in L.edges:
        d = decomposition(L, edge.source, edge.target)
        d["edge"] = str(edge)
        d["source"] = edge.source
        d["target"] = edge.target
        rows.append(d)
    return rows
