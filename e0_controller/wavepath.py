"""
E₀ Controller — Wave Path (Ψ)
================================
Komplexe Pfad-Darstellung und Pfad-Summation.

Spec coverage: §15 (Ψ(p)), §16 (Pfad-Summation).

Core equations:
    Ψ(p)    = exp(−S(p)) · exp(iΘ(p))     — §15 Komplexe Pfadadresse
    Ψ(z)    = Σ_{p→z} Ψ(p)                 — §16 Pfad-Summation
    I(z)    = |Ψ(z)|²                       — Intensität (Ankunftswahreinlichkeit)

Design decisions:
    - Pfade werden als explizite Listen übergeben (bounded, nicht global).
    - Keine automatische Pfad-Enumeration — das bleibt dem Caller.
    - Komplexe Zahlen via Python built-in `complex`.
    - Phase Θ(p) kommt aus connection.theta().
    - Tension S(p) kommt aus Landscape.effective_tension().

    Dies implementiert die Theorie-Schicht. Der Controller bleibt lokal-greedy
    und wird NICHT durch Pfadintegral ersetzt (Phase-2-Leitplanke).
"""

from __future__ import annotations

import cmath
import math
from typing import Dict, List

from .landscape import Landscape
from .connection import theta


def path_tension(L: Landscape, path: List[str]) -> float:
    """
    §5: S(p) = Σ S_eff(x_i → x_{i+1})

    Total tension along a path.
    Returns ∞ if any edge is inadmissible.
    """
    if len(path) < 2:
        return 0.0
    total = 0.0
    for i in range(len(path) - 1):
        s = L.effective_tension(path[i], path[i + 1])
        if math.isinf(s):
            return math.inf
        total += s
    return total


def psi(L: Landscape, path: List[str]) -> complex:
    """
    §15: Komplexe Pfad-Darstellung.

    Ψ(p) = exp(−S(p)) · exp(iΘ(p))
         = exp(−S(p) + iΘ(p))

    Returns a complex number encoding both magnitude and phase.

    Magnitude |Ψ| = exp(-S) = coherence of the path.
    Phase arg(Ψ) = Θ = accumulated connection phase.

    Special cases:
        S = ∞  → Ψ = 0 (inadmissible path contributes nothing)
        S = 0  → |Ψ| = 1 (zero-tension path, maximal coherence)
        Θ = 0  → Ψ is real positive (no rotational structure)
    """
    s = path_tension(L, path)
    if math.isinf(s):
        return complex(0.0, 0.0)
    t = theta(L, path)
    return cmath.exp(complex(-s, t))


def path_intensity(L: Landscape, path: List[str]) -> float:
    """
    |Ψ(p)|² = exp(−2S(p))

    Intensity of a single path.
    Note: for a single path, phase doesn't affect intensity.
    Phase only matters in superposition (sum_paths).
    """
    p = psi(L, path)
    return abs(p) ** 2


def sum_paths(L: Landscape, paths: List[List[str]]) -> complex:
    """
    §16: Pfad-Summation.

    Ψ(z) = Σ_{p → z} Ψ(p)

    Superposition of all paths reaching a target.
    Interference happens here:
        - Same phase → constructive (|Ψ_total| > individual)
        - Opposite phase → destructive (|Ψ_total| < individual)

    Caller provides the explicit path list — no automatic enumeration.
    This is the bounded discrete version (Phase-2-Leitplanke).
    """
    total = complex(0.0, 0.0)
    for path in paths:
        total += psi(L, path)
    return total


def intensity(L: Landscape, paths: List[List[str]]) -> float:
    """
    I(z) = |Ψ(z)|² = |Σ Ψ(p)|²

    Total intensity at a target from superposition of all paths.
    This is where interference becomes observable.
    """
    return abs(sum_paths(L, paths)) ** 2


def path_analysis(L: Landscape, path: List[str]) -> Dict:
    """
    Complete analysis of a single path.

    Returns:
        path:      state sequence
        length:    number of edges
        tension:   S(p)
        phase:     Θ(p) in radians
        psi:       complex Ψ(p)
        magnitude: |Ψ(p)|
        intensity: |Ψ(p)|²
        phase_deg: Θ(p) in degrees
    """
    s = path_tension(L, path)
    t = theta(L, path)
    p = psi(L, path)
    return {
        "path": " → ".join(path),
        "length": max(0, len(path) - 1),
        "tension": s,
        "phase": t,
        "psi": p,
        "magnitude": abs(p),
        "intensity": abs(p) ** 2,
        "phase_deg": math.degrees(t),
    }


def interference_analysis(L: Landscape, paths: List[List[str]]) -> Dict:
    """
    Analysis of interference between multiple paths.

    Returns:
        paths:               list of individual path analyses
        sum_psi:             Ψ_total = Σ Ψ(p)
        total_intensity:     |Ψ_total|²
        sum_intensities:     Σ |Ψ(p)|² (what intensity would be without interference)
        interference_factor: total_intensity / sum_intensities
            > 1: constructive interference
            < 1: destructive interference
            = 1: no interference (orthogonal phases)
    """
    analyses = [path_analysis(L, p) for p in paths]
    psi_total = sum_paths(L, paths)
    total_int = abs(psi_total) ** 2
    sum_int = sum(a["intensity"] for a in analyses)

    return {
        "paths": analyses,
        "sum_psi": psi_total,
        "total_intensity": total_int,
        "sum_intensities": sum_int,
        "interference_factor": total_int / sum_int if sum_int > 0 else 0.0,
    }
