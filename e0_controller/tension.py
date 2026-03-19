"""
E₀ Controller — Tension & Coherence
=====================================
Computes structural integration effort and path stability.

Spec coverage: §3 (Tension), §5 (Path Tension), §6 (Coherence).

Core equations:
    S(x→y) = Δ(x,y) · R(x→y)          — single-edge tension
    S(p)   = Σ S(eᵢ)                   — path tension (additive)
    C(p)   = exp(-S(p))                 — coherence (0,1]
"""

from __future__ import annotations

import math
from typing import List


def tension(delta: float, resistance: float) -> float:
    """
    §3: S(x→y) = Δ(x,y) · R(x→y)

    Tension = integration effort for a single transition.
    If resistance is infinite, tension is infinite (inadmissible).
    """
    if math.isinf(resistance):
        return math.inf
    return delta * resistance


def path_tension(edge_tensions: List[float]) -> float:
    """
    §5: S(p) = Σ S(eᵢ)

    Total integration effort along a path.
    One infinite edge makes the whole path infinite.
    """
    total = 0.0
    for s in edge_tensions:
        if math.isinf(s):
            return math.inf
        total += s
    return total


def coherence(s: float) -> float:
    """
    §6: C(p) = exp(-S(p))

    Coherence measures structural stability of a path.
    - S = 0   → C = 1.0  (perfect coherence, no effort)
    - S → ∞   → C → 0.0  (path disintegrates)
    - S > 0   → 0 < C < 1
    """
    if math.isinf(s):
        return 0.0
    return math.exp(-s)
