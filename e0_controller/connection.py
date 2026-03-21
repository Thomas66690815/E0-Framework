"""
E₀ Controller — Connection & Phase
=====================================
Antisymmetrische Connection und Pfad-Phase auf diskretem gerichtetem Graphen.

Spec coverage: §12 (Connection ω), §13 (Path Phase Θ), §14 (Holonomy).

Core equations:
    ω(x, y) = ½ · (v_rot(x, y) − v_rot(y, x))    — §12 Connection
    Θ(p)    = Σ_{e ∈ p} ω(e)                        — §13 Path Phase
    Θ(γ)    = Θ(cycle) for closed paths              — §14 Holonomy

Konvention für gerichtete Kanten:
    Auf einem gerichteten Graphen existiert Kante x→y möglicherweise,
    aber y→x nicht. Für ω(x,y) brauchen wir v_rot in beide Richtungen.

    Regel: Wenn Kante y→x nicht existiert:
        v_rot(y, x) = 0.0

    Begründung: Keine Rückkante = keine Transitionskapazität in Gegenrichtung.
    Dann wird ω(x, y) = ½ · v_rot(x, y), was sinnvoll ist:
    Einseitige Transitionen tragen halbe Connection.

    Diese Konvention ist explizit und dokumentiert (K3/Phase-2-Pflicht).

Antisymmetrie:
    ω(x, y) = −ω(y, x) gilt konstruktionsbedingt:
    ω(y, x) = ½ · (v_rot(y,x) − v_rot(x,y)) = −ω(x, y)

    Dies gilt auch wenn eine Richtung fehlt (v_rot = 0 für fehlende Kante),
    weil die Formel symmetrisch in der Subtraktion ist.
"""

from __future__ import annotations

import warnings
from typing import Dict, List, Optional

from .landscape import Landscape
from .primitives import Edge
from .potential import v_rot


def _safe_v_rot(L: Landscape, x: str, y: str) -> float:
    """
    v_rot(x, y) mit Konvention für fehlende Kanten:
    Fehlende Kante → 0.0 (keine Transitionskapazität in diese Richtung).
    """
    val = v_rot(L, x, y)
    if val is None:
        return 0.0
    return val


def omega(L: Landscape, x: str, y: str) -> float:
    """
    §12: Connection.

    ω(x, y) = ½ · (v_rot(x, y) − v_rot(y, x))

    Antisymmetric: ω(x, y) = −ω(y, x).

    Interpretations:
        ω = 0:  Transition carries no phase (pure gradient).
        ω ≠ 0:  Transition has rotational structure —
                 traversing it accumulates phase.
        ω > 0:  Positive phase accumulation in direction x→y.
        ω < 0:  Negative phase accumulation in direction x→y.
    """
    vr_xy = _safe_v_rot(L, x, y)
    vr_yx = _safe_v_rot(L, y, x)
    return 0.5 * (vr_xy - vr_yx)


def theta(L: Landscape, path: List[str]) -> float:
    """
    §13: Path Phase.

    Θ(p) = Σ_{i} ω(x_i, x_{i+1})

    Total phase accumulated along a path.
    Path is given as list of state names: [x₀, x₁, x₂, ...].

    A path with 0 or 1 states has Θ = 0.
    """
    if len(path) < 2:
        return 0.0
    total = 0.0
    for i in range(len(path) - 1):
        total += omega(L, path[i], path[i + 1])
    return total


def holonomy(L: Landscape, cycle: List[str]) -> float:
    """
    §14: Holonomy.

    Θ(γ) = Θ(cycle) where cycle is a closed path (first = last).

    For a truly closed path, holonomy measures the net phase
    accumulated over one full traversal. If holonomy ≠ 0,
    the landscape has non-integrable structure.

    If the path is not closed (first ≠ last), a warning is issued
    and the path phase is still computed — but it is not a holonomy
    in the strict mathematical sense.
    """
    if len(cycle) >= 2 and not is_closed(cycle):
        warnings.warn(
            f"holonomy() called with non-closed path "
            f"(first={cycle[0]!r}, last={cycle[-1]!r}). "
            f"Result is path phase Θ, not true holonomy.",
            stacklevel=2,
        )
    return theta(L, cycle)


def is_closed(path: List[str]) -> bool:
    """Check if a path forms a cycle (first state = last state)."""
    return len(path) >= 2 and path[0] == path[-1]


def omega_map(L: Landscape) -> Dict[str, float]:
    """
    ω for all edges in the landscape.
    Returns dict with 'x→y' keys.
    """
    result = {}
    for edge in L.edges:
        w = omega(L, edge.source, edge.target)
        result[str(edge)] = w
    return result


def connection_info(L: Landscape, x: str, y: str) -> Dict:
    """Full connection info for a pair of states."""
    vr_xy = _safe_v_rot(L, x, y)
    vr_yx = _safe_v_rot(L, y, x)
    w = omega(L, x, y)
    return {
        "edge": f"{x}→{y}",
        "v_rot_xy": vr_xy,
        "v_rot_yx": vr_yx,
        "omega": w,
        "has_forward": L.difference(x, y) is not None,
        "has_reverse": L.difference(y, x) is not None,
    }
