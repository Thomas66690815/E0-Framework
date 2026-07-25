"""
structural_geometry — the geometry layer of the E₀ Framework, standalone.
==========================================================================

Zero third-party dependencies. Pure Python. ~900 LOC.

Four ideas, in dependency order:

1. ``field``      — a directed graph whose edges carry ``weight`` and ``cost``,
                    yielding ``flow = weight · exp(−cost)``.
2. ``helmholtz``  — split ``flow`` into an orthogonal conservative part
                    (``v_grad``, real progress) and a circulating part
                    (``v_rot``, swirl). Solved exactly, per component.
3. ``connection`` — the circulation induces a phase ``ω`` per edge, a phase
                    ``Θ`` per path, holonomy per loop, curvature per edge.
4. ``amplitude`` /
   ``overlay``    — paths become complex amplitudes ``exp(−cost + iΘ)`` that
                    superpose. Loops and dead ends cancel themselves out.
                    ``influence_map`` turns that into a per-move score.

Quick start
-----------
    from structural_geometry import NavField, influence_map, circulation_ratio

    f = NavField()
    f.add_edge("A", "B", cost=0.4)
    f.add_edge("B", "GOAL", cost=0.3)
    f.add_edge("A", "C", cost=0.2)        # cheaper, but...
    f.add_edge("C", "A", cost=0.2)        # ...it just loops back

    report = influence_map(f, "A", horizon=3)
    report.greedy          # 'C'  — cheapest single edge
    report.best            # 'B'  — strongest forward support
    report.decide()        # gated choice; see should_override()

    circulation_ratio(f)   # how much of the field is wasted motion

Vocabulary
----------
This package uses navigation vocabulary. The E₀ canon terms map as:

    cost        S_eff = Δ · R_eff        weight      Δ
    flow        transition field v        v_grad      §10 gradient component
    v_rot       §11 rotation component    ω           §12 connection
    Θ           §13 path phase            Hol         §14 holonomy
    Ψ           §15 complex path address  I           §16 path summation

Source: https://github.com/Thomas66690815/E0-Framework
Author: Thomas Wehner · License: CC BY 4.0
# e0-structural-geometry-twehner
"""

from __future__ import annotations

from .amplitude import (
    interference_analysis,
    intensity,
    path_analysis,
    path_intensity,
    psi,
    sum_paths,
)
from .connection import (
    connection_info,
    curvature_map,
    damping,
    edge_curvature,
    holonomy,
    is_closed,
    omega,
    omega_map,
    phase_regime,
    theta,
)
from .field import Edge, NavField
from .helmholtz import (
    circulation_ratio,
    decompose,
    decomposition_table,
    divergence,
    divergence_map,
    orthogonality_residual,
    potential,
    potential_map,
    v_grad,
    v_rot,
)
from .overlay import (
    GEOMETRIES,
    ActionSupport,
    InfluenceReport,
    enumerate_continuations,
    influence_map,
)

__author__ = "Thomas Wehner"
__license__ = "CC BY 4.0"
__source__ = "https://github.com/Thomas66690815/E0-Framework"
__version__ = "0.1.0"

__all__ = [
    # field
    "NavField",
    "Edge",
    # helmholtz
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
    # connection
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
    # amplitude
    "psi",
    "path_intensity",
    "sum_paths",
    "intensity",
    "path_analysis",
    "interference_analysis",
    # overlay
    "influence_map",
    "enumerate_continuations",
    "InfluenceReport",
    "ActionSupport",
    "GEOMETRIES",
    # meta
    "__author__",
    "__license__",
    "__source__",
    "__version__",
]
