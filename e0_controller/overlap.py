"""
Graduated Overlap Functional — M_H as overlap degree (C40)
==========================================================

Implements M_H as a local overlap functional per Ontodynamics §3.4:
"Connections possess degree. Overlap is graduated, not binary.
Stability requires non-zero overlap."

M_H(x,y) measures how strongly the connection x→y is structurally
supported by co-realized transitions in its immediate neighborhood.

This is NOT curvature, NOT holonomy, and NOT a "topological invariant."
It is the edge-local analog of what path amplitude ψ does globally:
aggregating structural support from the surrounding graph.

Key concepts:
- T(x,y) = forward-directed 2-hop support set:
  {z : x→z ∈ E and z→y ∈ E, z ∉ {x,y}}
- overlap(x→y) = Σ_{z ∈ T} √(v(x,z) · v(z,y))
- M_H = domain-relative normalization of overlap → [floor, 1.0]

See: docs/research/E0_MH_ADJUDICATION_RESEARCH_NOTE_v1.md
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, Set, Tuple

if TYPE_CHECKING:
    from .landscape import Landscape

from .config import DEFAULTS


# ─────────────────────────────────────────────
# Core functions
# ─────────────────────────────────────────────

def triangle_support(L: Landscape, x: str, y: str) -> Set[str]:
    """
    Forward-directed 2-hop support set T(x,y).

    T(x,y) = {z : x→z ∈ E and z→y ∈ E, z ∉ {x,y}}

    These are nodes that provide a bypass path x→z→y,
    structurally supporting the direct edge x→y.
    """
    out_x = {e.target for e in L.edges if e.source == x and e.target not in (x, y)}
    into_y = {e.source for e in L.edges if e.target == y and e.source not in (x, y)}
    return out_x & into_y


def edge_overlap(L: Landscape, x: str, y: str) -> float:
    """
    Graduated overlap of edge x→y with its co-realized neighborhood.

    overlap(x→y) = Σ_{z ∈ T(x,y)} √(v(x,z) · v(z,y))

    Uses geometric mean of supporting leg strengths:
    - symmetric in both legs
    - zero if either leg is blocked
    - same units as v (transition field)
    """
    T = triangle_support(L, x, y)
    if not T:
        return 0.0
    total = 0.0
    for z in T:
        vxz = L.transition_field(x, z)
        vzy = L.transition_field(z, y)
        total += math.sqrt(vxz * vzy)
    return total


@dataclass(frozen=True)
class OverlapInfo:
    """Per-edge overlap information."""
    edge: Tuple[str, str]
    overlap: float
    m_h: float
    support_set: frozenset


def overlap_map(L: Landscape, floor: float = DEFAULTS.overlap_floor) -> Dict[Tuple[str, str], OverlapInfo]:
    """
    Compute overlap and M_H for all edges in the landscape.

    Returns a dict mapping (source, target) → OverlapInfo.

    M_H normalization:
    - If max_overlap = 0 across all edges → M_H = 1.0 everywhere
      (simple domain, no bypass structure, completely neutral)
    - Otherwise: M_H = (overlap + ε) / (max_overlap + ε)
      where ε = max_overlap * floor / (1 - floor)
      This gives M_H = floor for zero-overlap edges and M_H = 1.0
      for the best-supported edge.

    Parameters
    ----------
    L : Landscape
    floor : float
        Minimum M_H for unsupported edges in a domain with overlap.
        Default 0.2. Canon §3.4: stability requires non-zero overlap,
        so M_H > 0 always.
    """
    # Phase 1: compute raw overlaps
    raw: Dict[Tuple[str, str], Tuple[float, frozenset]] = {}
    for edge in L.edges:
        x, y = edge.source, edge.target
        T = triangle_support(L, x, y)
        ov = edge_overlap(L, x, y)
        raw[(x, y)] = (ov, frozenset(T))

    # Phase 2: normalize
    max_ov = max((ov for ov, _ in raw.values()), default=0.0)

    result = {}
    if max_ov == 0.0:
        # No overlap anywhere → M_H = 1.0 (neutral, simple domain)
        for (x, y), (ov, T) in raw.items():
            result[(x, y)] = OverlapInfo(
                edge=(x, y), overlap=0.0, m_h=1.0, support_set=T
            )
    else:
        # ε chosen so that overlap=0 → M_H=floor, overlap=max → M_H=1.0
        eps = max_ov * floor / (1.0 - floor)
        for (x, y), (ov, T) in raw.items():
            m_h = (ov + eps) / (max_ov + eps)
            result[(x, y)] = OverlapInfo(
                edge=(x, y), overlap=ov, m_h=m_h, support_set=T
            )

    return result
