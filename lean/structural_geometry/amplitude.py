"""
structural_geometry.amplitude — complex path amplitudes and interference.
==========================================================================

Each path gets a complex number instead of a scalar score:

    Ψ(p) = exp( −cost(p) ) · exp( i·Θ(p) )
         = exp( −cost(p) + i·Θ(p) )

    |Ψ(p)|  = exp(−cost)   how cheap the path is
    arg Ψ(p) = Θ(p)         which way the field curls along it

Amplitudes of paths reaching the same place **superpose**:

    Ψ(z) = Σ_{p → z} Ψ(p)          I(z) = |Ψ(z)|²

and that is the whole point.  Scalar path scores can only add up.  Complex
amplitudes can *cancel*:

    same phase      → constructive → I > Σ|Ψ(p)|²
    opposite phase  → destructive  → I < Σ|Ψ(p)|²

What phase buys you, and what it does not
-----------------------------------------
A real-valued influence map sums non-negative contributions, so it cannot
represent path-dependence at all: twenty mediocre routes that curl back on
themselves and one genuinely good route both produce a large number.
Complex amplitudes can encode *where the path went*, because ``Θ`` depends
on the whole route rather than on its endpoints.

Be precise about the size of the effect, though — this is a regime, not a
magic trick:

    phase spread ≪ π   amplitudes are near-collinear, interference is
                        essentially constructive, and the ranking is driven
                        by ``exp(−cost)``.  Phase is a small correction.
    phase spread ~ π   contributions genuinely cancel.  This is where
                        loops and dead ends suppress themselves without
                        any loop-detection code.

``Θ`` scales linearly with ``ω``, which scales linearly with ``flow``, which
scales linearly with ``weight``.  **The phase regime is therefore a
modelling choice you control**, not a fixed property of the graph — see
:func:`structural_geometry.connection.phase_regime` to find out which
regime your field is actually in before relying on cancellation.

Two further honest caveats, both surfaced rather than hidden:

``path_imbalance`` (here)
    If one target is reachable by far more enumerated paths than another,
    ``|ΣΨ|²`` is biased by sheer path count regardless of quality.

``InfluenceReport.should_override`` (in ``overlay``)
    Acting on every interference-vs-greedy disagreement measurably *hurts*.
    The gate exists because of that finding.

# e0-structural-geometry-twehner
"""

from __future__ import annotations

import cmath
import math
from typing import Dict, Sequence

from .connection import _omega_table, _theta_from_table, theta
from .field import Edge, NavField

__all__ = [
    "psi",
    "path_intensity",
    "sum_paths",
    "intensity",
    "path_analysis",
    "interference_analysis",
]


def psi(field: NavField, path: Sequence[str]) -> complex:
    """``Ψ(p) = exp(−cost(p) + i·Θ(p))``.

    An impossible path (any missing hop) has ``cost = ∞`` and contributes
    exactly ``0`` — it drops out of every superposition on its own.
    """
    s = field.path_cost(path)
    if math.isinf(s):
        return 0j
    return cmath.exp(complex(-s, theta(field, path)))


def path_intensity(field: NavField, path: Sequence[str]) -> float:
    """``|Ψ(p)|² = exp(−2·cost(p))`` for a single path.

    Phase is invisible here by construction — a lone path cannot interfere
    with anything.  Phase only becomes observable in :func:`intensity`.
    """
    return abs(psi(field, path)) ** 2


def sum_paths(
    field: NavField,
    paths: Sequence[Sequence[str]],
    *,
    _connection_table: Dict[Edge, float] | None = None,
) -> complex:
    """``Ψ(z) = Σ Ψ(p)`` — superposition. This is where interference happens.

    Paths are supplied explicitly; nothing is enumerated for you.  Use
    ``overlay.enumerate_continuations`` when you want the bounded family
    of forward paths from a node.
    """
    table = _connection_table if _connection_table is not None else _omega_table(field)
    total = 0j
    for p in paths:
        cost = field.path_cost(p)
        if math.isinf(cost):
            continue
        total += cmath.exp(complex(-cost, _theta_from_table(table, p)))
    return total


def intensity(field: NavField, paths: Sequence[Sequence[str]]) -> float:
    """``I(z) = |Σ Ψ(p)|²`` — total support from a family of paths."""
    return abs(sum_paths(field, paths)) ** 2


def path_analysis(field: NavField, path: Sequence[str]) -> Dict[str, object]:
    """Full breakdown of one path: cost, phase, amplitude, intensity."""
    nodes = list(path)
    s = field.path_cost(nodes)
    t = theta(field, nodes)
    p = psi(field, nodes)
    return {
        "path": " → ".join(nodes),
        "nodes": nodes,
        "hops": max(0, len(nodes) - 1),
        "cost": s,
        "phase": t,
        "phase_deg": math.degrees(t),
        "psi": p,
        "magnitude": abs(p),
        "intensity": abs(p) ** 2,
    }


def interference_analysis(
    field: NavField, paths: Sequence[Sequence[str]]
) -> Dict[str, object]:
    """Compare the interfering total against the non-interfering sum.

    Returns, among the per-path details:

    ``interference_factor``
        ``|ΣΨ|² / Σ|Ψ|²``.  Greater than 1 → constructive, less than 1 →
        destructive, exactly 1 → phases are orthogonal and interference
        contributes nothing.

    ``path_imbalance``
        Ratio of the largest to the smallest contributing magnitude.  High
        values mean the total is dominated by a few paths — read the
        interference factor with suspicion.

    ``phase_spread``
        ``max Θ − min Θ`` over contributing paths, in radians.  Far below
        ``π`` means the amplitudes are near-collinear and no meaningful
        cancellation is possible, whatever the factor says.
    """
    analyses = [path_analysis(field, p) for p in paths]
    contributing = [a for a in analyses if a["magnitude"] > 0.0]  # type: ignore[operator]

    psi_total = sum_paths(field, paths)
    total_i = abs(psi_total) ** 2
    sum_i = sum(float(a["intensity"]) for a in analyses)

    if len(contributing) >= 2:
        mags = [float(a["magnitude"]) for a in contributing]
        imbalance = max(mags) / min(mags)
        phases = [float(a["phase"]) for a in contributing]
        spread = max(phases) - min(phases)
    else:
        imbalance = 1.0
        spread = 0.0

    return {
        "paths": analyses,
        "path_count": len(analyses),
        "contributing_count": len(contributing),
        "psi_total": psi_total,
        "total_intensity": total_i,
        "sum_intensities": sum_i,
        "interference_factor": (total_i / sum_i) if sum_i > 0.0 else 0.0,
        "path_imbalance": imbalance,
        "phase_spread": spread,
    }
