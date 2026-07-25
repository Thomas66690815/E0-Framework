"""
structural_geometry.helmholtz — split a navigation field into its
conservative and its circulating part.
==================================================================

Every flow field on a graph decomposes uniquely into

    flow  =  v_grad  +  v_rot

    v_grad(u→v) = Φ(u) − Φ(v)      the conservative part: pure downhill,
                                     derivable from a scalar potential Φ
    v_rot                            the remainder: circulation, whirl,
                                     the part that goes round in circles

Φ is obtained by solving the graph-Laplacian equation

    L · Φ = div(flow),      div(flow)(x) = Σ_y flow(x→y) − Σ_y flow(y→x)

which makes the two parts **orthogonal in edge space**:

    ⟨v_grad, v_rot⟩_E = ⟨Φ, div v_rot⟩_V = 0        because div v_rot ≡ 0

Why this matters for navigation
-------------------------------
A flow field steering agents toward a goal is normally treated as one
opaque vector field.  It is not one thing.  ``v_grad`` is the part that
actually makes progress.  ``v_rot`` is the part that makes crowds swirl,
units orbit obstacles, and paths loop — and it is measurable, per edge,
before anything moves.

``v_rot`` is also the *only* source of path-dependence: it is what makes
holonomy (see ``connection``) non-zero, and therefore what gives path
amplitudes a phase to interfere with.

Implementation notes
--------------------
The solve is done **per weakly connected component**, pinning one node per
component to ``Φ = 0``.  The reduced Laplacian of a connected component is
symmetric positive definite, so the solve is exact — no least-squares
pseudo-inverse needed, and disconnected graphs are handled correctly rather
than incidentally.

Small components use dense Cholesky; large ones use sparse conjugate
gradients, which never materialises the matrix.  Results are cached on the
field and invalidated automatically whenever a cost or edge changes.

# e0-structural-geometry-twehner
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence

from .field import Edge, NavField
from .linalg import CholeskyError, solve_cg, solve_spd_dense

__all__ = [
    "divergence",
    "divergence_map",
    "potential",
    "potential_map",
    "v_grad",
    "v_rot",
    "decompose",
    "decomposition_table",
    "orthogonality_residual",
    "circulation_ratio",
    "DENSE_THRESHOLD",
]

#: Components with at most this many nodes use exact dense Cholesky;
#: larger components use sparse conjugate gradients.
DENSE_THRESHOLD = 256

_CACHE_KEY = "helmholtz.phi"


# ── divergence ──────────────────────────────────────────────────────

def divergence(field: NavField, node: str) -> float:
    """``div(flow)(x) = Σ_y flow(x→y) − Σ_y flow(y→x)``.

    Positive → net source (more flow leaves than arrives).
    Negative → net sink.
    Zero     → balanced, or purely circulating.
    """
    out = sum(field.flow(node, y) for y in field.neighbors(node))
    inn = sum(field.flow(y, node) for y in field.predecessors(node))
    return out - inn


def divergence_map(field: NavField) -> Dict[str, float]:
    """``div(flow)`` for every node."""
    return {n: divergence(field, n) for n in sorted(field.nodes)}


# ── potential ───────────────────────────────────────────────────────

def _component_laplacian_matvec(
    field: NavField, index: Dict[str, int], pinned: int
):
    """Return a matvec for the component Laplacian with row/col ``pinned`` removed.

    The reduced vector omits the pinned node; it is re-inserted as 0.0
    before applying the operator and dropped again afterwards.
    """
    nodes = [None] * len(index)  # type: List[Optional[str]]
    for name, i in index.items():
        nodes[i] = name
    local_edges = [
        (index[e.source], index[e.target])
        for e in field.edges
        if e.source in index and e.target in index
    ]
    n = len(index)

    def matvec(reduced: Sequence[float]) -> List[float]:
        full = [0.0] * n
        k = 0
        for i in range(n):
            if i == pinned:
                continue
            full[i] = reduced[k]
            k += 1
        out = [0.0] * n
        for i, j in local_edges:
            d = full[i] - full[j]
            out[i] += d
            out[j] -= d
        return [out[i] for i in range(n) if i != pinned]

    return matvec


def _component_laplacian_dense(
    field: NavField, index: Dict[str, int], pinned: int
) -> List[List[float]]:
    """Dense reduced Laplacian for one component (pinned row/col removed)."""
    n = len(index)
    lap = [[0.0] * n for _ in range(n)]
    for e in field.edges:
        if e.source not in index or e.target not in index:
            continue
        i = index[e.source]
        j = index[e.target]
        lap[i][j] -= 1.0
        lap[j][i] -= 1.0
        lap[i][i] += 1.0
        lap[j][j] += 1.0
    keep = [i for i in range(n) if i != pinned]
    return [[lap[i][j] for j in keep] for i in keep]


def _solve_potential(field: NavField) -> Dict[str, float]:
    """Solve ``L Φ = div(flow)`` per component. Cached on the field."""
    cached = field.cache_get(_CACHE_KEY)
    if cached is not None:
        token, value = cached  # type: ignore[misc]
        if token == field.token:
            return value  # type: ignore[return-value]

    phi: Dict[str, float] = {}

    for comp in field.components():
        n = len(comp)
        if n <= 1:
            for name in comp:
                phi[name] = 0.0
            continue

        index = {name: i for i, name in enumerate(comp)}
        pinned = 0  # comp is sorted → deterministic pin
        div_full = [divergence(field, name) for name in comp]
        b = [div_full[i] for i in range(n) if i != pinned]

        solved: Optional[List[float]] = None
        if n <= DENSE_THRESHOLD:
            try:
                solved = solve_spd_dense(
                    _component_laplacian_dense(field, index, pinned), b
                )
            except CholeskyError:
                solved = None
        if solved is None:
            solved = solve_cg(
                _component_laplacian_matvec(field, index, pinned), b
            )

        phi[comp[pinned]] = 0.0
        k = 0
        for i, name in enumerate(comp):
            if i == pinned:
                continue
            phi[name] = solved[k]
            k += 1

    field.cache_put(_CACHE_KEY, (field.token, phi))
    return phi


def potential(field: NavField, node: str) -> float:
    """``Φ(x)`` — structural pressure at a node.

    High Φ means net outflow drive, low Φ means sink-like.  Only
    *differences* of Φ are meaningful; the absolute level is pinned
    arbitrarily (one node per component is set to 0).
    """
    return _solve_potential(field).get(node, 0.0)


def potential_map(field: NavField) -> Dict[str, float]:
    """``Φ`` for every node."""
    return dict(_solve_potential(field))


# ── the decomposition ───────────────────────────────────────────────

def v_grad(field: NavField, source: str, target: str) -> float:
    """Conservative component ``Φ(u) − Φ(v)``.

    Defined for *any* node pair, edge or not — it is a potential difference.
    """
    p = _solve_potential(field)
    return p.get(source, 0.0) - p.get(target, 0.0)


def v_rot(field: NavField, source: str, target: str) -> Optional[float]:
    """Circulating component ``flow − v_grad``.

    Returns ``None`` when the edge does not exist: circulation is a
    property of an edge, and there is nothing to circulate along.
    """
    if not field.has_edge(source, target):
        return None
    return field.flow(source, target) - v_grad(field, source, target)


def decompose(field: NavField, source: str, target: str) -> Dict[str, Optional[float]]:
    """Full per-edge breakdown: ``flow``, ``v_grad``, ``v_rot``, ``Φ`` at both ends."""
    p = _solve_potential(field)
    return {
        "flow": field.flow(source, target),
        "v_grad": p.get(source, 0.0) - p.get(target, 0.0),
        "v_rot": v_rot(field, source, target),
        "phi_source": p.get(source, 0.0),
        "phi_target": p.get(target, 0.0),
    }


def decomposition_table(field: NavField) -> List[Dict[str, object]]:
    """:func:`decompose` for every edge, sorted deterministically."""
    rows: List[Dict[str, object]] = []
    for e in sorted(field.edges, key=lambda x: (x.source, x.target)):
        row: Dict[str, object] = dict(decompose(field, e.source, e.target))
        row["edge"] = str(e)
        row["source"] = e.source
        row["target"] = e.target
        rows.append(row)
    return rows


# ── diagnostics ─────────────────────────────────────────────────────

def orthogonality_residual(field: NavField) -> float:
    """``|⟨v_grad, v_rot⟩_E| / ‖flow‖²`` — should be ~0 up to solver tolerance.

    This is the correctness check for the decomposition.  A value above
    ~1e-6 means the linear solve did not converge; treat it as a bug
    signal, not a property of the graph.

    Normalised by ``‖flow‖²`` rather than by ``‖v_grad‖·‖v_rot‖``: because
    the split is orthogonal, ``‖v_grad‖² + ‖v_rot‖² = ‖flow‖²``, so this is
    a true relative error — and it stays meaningful when one component
    vanishes (on a tree ``v_rot`` is exactly zero, and dividing by its norm
    would turn rounding dust into a spurious residual).
    """
    p = _solve_potential(field)
    dot = 0.0
    scale = 0.0
    for e in field.edges:
        f = field.flow(e.source, e.target)
        g = p.get(e.source, 0.0) - p.get(e.target, 0.0)
        dot += g * (f - g)
        scale += f * f
    if scale <= 0.0:
        return 0.0
    return abs(dot) / scale


def circulation_ratio(field: NavField) -> float:
    """Share of total field energy that is circulation rather than progress.

    ``‖v_rot‖² / (‖v_grad‖² + ‖v_rot‖²)`` ∈ [0, 1].

    - ``0.0`` — the field is a pure gradient: every edge makes progress,
      no swirl anywhere.  Agents following it cannot loop.
    - ``1.0`` — the field is pure circulation: it has no downhill direction
      at all.  Agents following it *only* loop.

    In practice this is the single most useful number the decomposition
    produces: it tells you, before running a single agent, how much of
    your navigation field is wasted motion.
    """
    p = _solve_potential(field)
    ng = 0.0
    nr = 0.0
    for e in field.edges:
        g = p.get(e.source, 0.0) - p.get(e.target, 0.0)
        r = field.flow(e.source, e.target) - g
        ng += g * g
        nr += r * r
    total = ng + nr
    if total <= 0.0:
        return 0.0
    return nr / total
