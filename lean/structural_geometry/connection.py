"""
structural_geometry.connection — phase, holonomy and curvature.
================================================================

Once the field is split (see ``helmholtz``), the circulating part ``v_rot``
induces a **connection** on the graph:

    ω(u→v) = ½ · ( v_rot(u→v) − v_rot(v→u) )          antisymmetric by construction
    Θ(path) = Σ_{e ∈ path} ω(e)                        phase accumulated along a path
    Hol(γ)  = Θ(γ) for a closed path                    holonomy: net phase per lap
    κ(u→v)  = mean |Hol| over triangles through u→v     local curvature

Antisymmetry ``ω(u→v) = −ω(v→u)`` holds even when only one direction of the
edge exists: a missing edge contributes ``v_rot = 0``, so a one-way street
carries exactly half the connection of a two-way one.  That is the intended
reading — no reverse capacity, half the circulation.

What these are good for
-----------------------
``Θ`` is the phase that makes path amplitudes interfere (see ``amplitude``).
Without a non-zero connection every path has phase 0, all amplitudes are
real and positive, and interference degenerates into plain summation.

``Hol(γ) ≠ 0`` means the field is **non-integrable**: walking a loop does
not return you to where you started, in the field's own accounting.  A
navigation graph with large holonomy around a region is one where agents
systematically drift when circling it.

``κ`` measures how tightly the field curls near a single edge.  The derived
``damping(u→v) = 1/(1+κ)`` is a ready-made multiplier for suppressing
traversal through high-curl regions: flat → 1.0 (untouched), strongly
curled → toward 0.

# e0-structural-geometry-twehner
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, List, Sequence

from .field import Edge, NavField
from .helmholtz import v_grad

__all__ = [
    "omega",
    "omega_map",
    "theta",
    "holonomy",
    "is_closed",
    "edge_curvature",
    "curvature_map",
    "damping",
    "connection_info",
    "phase_regime",
]

_CACHE_KEY = "connection.omega"


def _raw_v_rot(field: NavField, u: str, v: str) -> float:
    """``v_rot`` with the missing-edge convention: absent edge → 0.0."""
    if not field.has_edge(u, v):
        return 0.0
    return field.flow(u, v) - v_grad(field, u, v)


def _omega_table(field: NavField) -> Dict[Edge, float]:
    """All ω values, cached per field revision."""
    cached = field.cache_get(_CACHE_KEY)
    if cached is not None:
        token, value = cached  # type: ignore[misc]
        if token == field.token:
            return value  # type: ignore[return-value]

    table: Dict[Edge, float] = {}
    for e in field.edges:
        table[e] = 0.5 * (
            _raw_v_rot(field, e.source, e.target)
            - _raw_v_rot(field, e.target, e.source)
        )
    field.cache_put(_CACHE_KEY, (field.token, table))
    return table


def omega(field: NavField, source: str, target: str) -> float:
    """``ω(u→v)`` — connection on one edge.

    ``0.0``  the transition carries no phase (pure gradient there)
    ``> 0``  positive phase accumulates in the direction ``u→v``
    ``< 0``  negative phase accumulates

    Returns ``0.0`` for a non-existent edge.
    """
    table = _omega_table(field)
    e = Edge(source, target)
    if e in table:
        return table[e]
    rev = Edge(target, source)
    if rev in table:
        return -table[rev]
    return 0.0


def omega_map(field: NavField) -> Dict[str, float]:
    """``ω`` for every edge, keyed ``'u→v'``."""
    return {str(e): w for e, w in sorted(_omega_table(field).items())}


def theta(field: NavField, path: Sequence[str]) -> float:
    """``Θ(p) = Σ ω`` — total phase along a node sequence.

    A path of fewer than two nodes has ``Θ = 0``.
    """
    nodes = list(path)
    if len(nodes) < 2:
        return 0.0
    return sum(omega(field, nodes[i], nodes[i + 1]) for i in range(len(nodes) - 1))


def is_closed(path: Sequence[str]) -> bool:
    """True when the path returns to its starting node."""
    nodes = list(path)
    return len(nodes) >= 2 and nodes[0] == nodes[-1]


def holonomy(field: NavField, cycle: Sequence[str]) -> float:
    """Net phase accumulated over one full lap of a closed path.

    Raises ``ValueError`` if the path is not closed — unlike the parent
    framework, which warns and returns the open-path phase.  A silent
    "almost holonomy" is a bug waiting to happen; if you want the phase of
    an open path, call :func:`theta` and mean it.
    """
    if not is_closed(cycle):
        nodes = list(cycle)
        first = nodes[0] if nodes else None
        last = nodes[-1] if nodes else None
        raise ValueError(
            f"holonomy() requires a closed path (first={first!r}, last={last!r}); "
            f"use theta() for open paths"
        )
    return theta(field, cycle)


def edge_curvature(field: NavField, source: str, target: str) -> float:
    """``κ(u→v)`` — mean ``|holonomy|`` over directed triangles through the edge.

    A triangle is ``u→v→z→u``.  With no such triangle the edge is flat and
    ``κ = 0``.  Curvature is unsigned: it measures how much the field curls
    nearby, not which way.
    """
    v_targets = set(field.neighbors(target))
    z_closing = set(field.predecessors(source))
    triangles = (v_targets & z_closing) - {source, target}
    if not triangles:
        return 0.0
    w_uv = omega(field, source, target)
    hols = [
        abs(w_uv + omega(field, target, z) + omega(field, z, source))
        for z in sorted(triangles)
    ]
    return sum(hols) / len(hols)


def curvature_map(field: NavField) -> Dict[str, float]:
    """``κ`` for every edge, keyed ``'u→v'``."""
    return {
        str(e): edge_curvature(field, e.source, e.target)
        for e in sorted(field.edges, key=lambda x: (x.source, x.target))
    }


def damping(field: NavField, source: str, target: str) -> float:
    """``1 / (1 + κ)`` ∈ (0, 1] — traversal multiplier for a curled region.

    Flat edge → ``1.0`` (no effect).  Strongly curled → toward ``0``.
    Multiply into ``flow`` (or into a movement speed) to make agents
    avoid regions where the field turns sharply.
    """
    return 1.0 / (1.0 + edge_curvature(field, source, target))


def phase_regime(field: NavField, *, horizon: int = 3) -> Dict[str, object]:
    """Tell the caller whether phase can do anything in this field.

    Interference cancels when two routes to the same place differ in phase
    by an appreciable fraction of ``π``.  What matters is therefore the
    phase *gap between alternative routes*, not the absolute phase along
    any one of them — a large phase that every route shares rotates the
    whole superposition and changes nothing.

    That gap is exactly a holonomy: two routes joining the same endpoints
    form a loop, and the loop's holonomy is their phase difference.  The
    estimate here uses the mean edge curvature ``κ``, which is the mean
    ``|holonomy|`` over the shortest loops in the field.  Where the graph
    has no triangles, it falls back to ``mean|ω| · horizon`` and says so
    via ``basis``.

    ``Θ`` scales linearly with ``ω``, hence with ``flow``, hence with
    ``weight``.  **The regime is therefore a modelling choice you control.**

    ``regime``:

    ``"gradient"``      gap < 0.1·π.  Phase is a rounding correction and
                        ranking is effectively ``exp(−cost)``.  Perfectly
                        usable — just do not claim cancellation.
    ``"interfering"``   gap within [0.1·π, 2π].  Cancellation is reachable;
                        this is the intended operating range.
    ``"wrapped"``       gap > 2π.  Route phases alias around the circle, so
                        the ranking becomes erratic in ``weight``: two
                        nearly identical fields can rank moves differently.
                        Scale ``weight`` down.
    """
    table = _omega_table(field)
    if not table:
        return {
            "mean_abs_omega": 0.0,
            "max_abs_omega": 0.0,
            "phase_gap": 0.0,
            "basis": "empty",
            "horizon": horizon,
            "regime": "gradient",
        }

    mags = [abs(w) for w in table.values()]
    mean_abs = sum(mags) / len(mags)

    curvatures = [
        edge_curvature(field, e.source, e.target) for e in field.edges
    ]
    curved = [k for k in curvatures if k > 0.0]
    if curved:
        gap = sum(curved) / len(curved)
        basis = "curvature"
    else:
        gap = mean_abs * horizon
        basis = "omega"

    if gap > 2.0 * math.pi:
        regime = "wrapped"
    elif gap >= 0.1 * math.pi:
        regime = "interfering"
    else:
        regime = "gradient"

    return {
        "mean_abs_omega": mean_abs,
        "max_abs_omega": max(mags),
        "phase_gap": gap,
        "basis": basis,
        "horizon": horizon,
        "regime": regime,
    }


def connection_info(field: NavField, source: str, target: str) -> Dict[str, object]:
    """Everything the connection layer knows about one edge."""
    return {
        "edge": f"{source}→{target}",
        "v_rot_forward": _raw_v_rot(field, source, target),
        "v_rot_reverse": _raw_v_rot(field, target, source),
        "omega": omega(field, source, target),
        "curvature": edge_curvature(field, source, target),
        "damping": damping(field, source, target),
        "has_forward": field.has_edge(source, target),
        "has_reverse": field.has_edge(target, source),
    }
