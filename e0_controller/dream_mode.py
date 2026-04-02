"""Dream Mode — Cross-domain pattern recognition through passive observation.

Detects functional equivalences across domains by comparing edge fingerprints
(trace_quality, trace_load, inertia_factor). Equivalences are stored in a
Dream Landscape that historizes itself — productive analogies strengthen,
bad analogies die through the same mechanism as any E₀ edge.

Key constraint: Dream Mode never mutates any domain landscape.

C109: Fingerprint extraction, distance metric, equivalence detection,
      dream_readiness trigger.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from e0_controller.landscape import Landscape
from e0_controller.primitives import Edge


# ---------------------------------------------------------------------------
# Edge fingerprint
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EdgeFingerprint:
    """Historization profile of a single edge: (q, m, I)."""
    domain: str
    edge: Edge
    quality: float      # trace_quality ∈ (-1, +1)
    load: float         # trace_load ∈ [0, ∞)
    inertia: float      # inertia_factor ∈ (1-α, 1]


def edge_fingerprint(
    edge: Edge,
    landscape: Landscape,
    domain: str = "",
    *,
    alpha: float = 0.5,
    mu: float = 5.0,
) -> EdgeFingerprint:
    """Extract the historization fingerprint of an edge."""
    h = landscape.historization
    return EdgeFingerprint(
        domain=domain,
        edge=edge,
        quality=h.trace_quality(edge),
        load=h.trace_load(edge),
        inertia=h.inertia_factor(edge, alpha=alpha, mu=mu),
    )


def domain_fingerprints(
    landscape: Landscape,
    domain: str = "",
    *,
    alpha: float = 0.5,
    mu: float = 5.0,
) -> List[EdgeFingerprint]:
    """Extract fingerprints for all edges in a landscape."""
    return [
        edge_fingerprint(e, landscape, domain, alpha=alpha, mu=mu)
        for e in landscape.edges
    ]


# ---------------------------------------------------------------------------
# Fingerprint distance
# ---------------------------------------------------------------------------

def fingerprint_distance(
    a: EdgeFingerprint,
    b: EdgeFingerprint,
    mu: float = 5.0,
) -> float:
    """Normalized distance between two edge fingerprints.

    Uses the m/(m+μ) sigmoid for trace_load normalization, ensuring
    scale-invariance across domains with different activity levels.
    """
    dq = a.quality - b.quality
    # Normalize load via sigmoid (same as inertia_factor uses)
    norm_a = a.load / (a.load + mu)
    norm_b = b.load / (b.load + mu)
    dm = norm_a - norm_b
    di = a.inertia - b.inertia
    return math.sqrt(dq * dq + dm * dm + di * di)


# ---------------------------------------------------------------------------
# Functional equivalence
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Equivalence:
    """A detected functional equivalence between two edges in different domains."""
    fp_a: EdgeFingerprint
    fp_b: EdgeFingerprint
    distance: float

    @property
    def edge_a(self) -> Edge:
        return self.fp_a.edge

    @property
    def edge_b(self) -> Edge:
        return self.fp_b.edge

    @property
    def domain_a(self) -> str:
        return self.fp_a.domain

    @property
    def domain_b(self) -> str:
        return self.fp_b.domain

    @property
    def confidence(self) -> float:
        """Higher confidence for closer fingerprints. Range [0, 1]."""
        # max possible distance is sqrt(4 + 1 + α²) ≈ 2.3 for α=0.5
        # but practically distances > 2.0 are very far
        return max(0.0, 1.0 - self.distance)


def find_equivalences(
    landscape_a: Landscape,
    landscape_b: Landscape,
    *,
    domain_a: str = "A",
    domain_b: str = "B",
    mu: float = 5.0,
    alpha: float = 0.5,
    quantile: float = 0.1,
    max_results: Optional[int] = None,
) -> List[Equivalence]:
    """Find functional equivalences between edges in two domains.

    Computes all pairwise fingerprint distances and returns those in the
    bottom quantile (closest matches). The threshold is data-driven, not
    fixed — adapts to each domain pair.

    Args:
        landscape_a, landscape_b: The two domain landscapes (read-only).
        domain_a, domain_b: Names for reporting.
        mu: Half-load parameter for fingerprint normalization.
        alpha: Dampening strength for inertia_factor.
        quantile: Fraction of pairwise distances to keep (default: bottom 10%).
        max_results: Optional cap on returned equivalences.

    Returns:
        List of Equivalence objects, sorted by distance (ascending).
    """
    fps_a = domain_fingerprints(landscape_a, domain_a, alpha=alpha, mu=mu)
    fps_b = domain_fingerprints(landscape_b, domain_b, alpha=alpha, mu=mu)

    if not fps_a or not fps_b:
        return []

    # Compute all pairwise distances
    pairs: List[Equivalence] = []
    for fa in fps_a:
        for fb in fps_b:
            d = fingerprint_distance(fa, fb, mu=mu)
            pairs.append(Equivalence(fp_a=fa, fp_b=fb, distance=d))

    if not pairs:
        return []

    # Sort by distance
    pairs.sort(key=lambda eq: eq.distance)

    # Apply quantile threshold
    cutoff_idx = max(1, int(len(pairs) * quantile))
    result = pairs[:cutoff_idx]

    if max_results is not None:
        result = result[:max_results]

    return result


# ---------------------------------------------------------------------------
# Dream readiness
# ---------------------------------------------------------------------------

def dream_readiness(landscape: Landscape, alpha: float = 0.5, mu: float = 5.0) -> float:
    """How ready a domain is for dream observation.

    Returns the mean inertia_factor across all edges. High values (→1.0)
    indicate stable fingerprints — the domain has consolidated its experience.
    Low values indicate the domain is still actively learning.

    A domain with no edges returns 0.0 (not ready).
    """
    edges = landscape.edges
    if not edges:
        return 0.0
    h = landscape.historization
    total = sum(h.inertia_factor(e, alpha=alpha, mu=mu) for e in edges)
    return total / len(edges)


def is_dream_ready(
    landscape: Landscape,
    threshold: float = 0.8,
    alpha: float = 0.5,
    mu: float = 5.0,
) -> bool:
    """Whether a domain's fingerprints are stable enough for dreaming."""
    return dream_readiness(landscape, alpha=alpha, mu=mu) >= threshold


# ---------------------------------------------------------------------------
# Dream Landscape construction
# ---------------------------------------------------------------------------

def _equivalence_state(fp: EdgeFingerprint) -> str:
    """Encode a fingerprinted edge as a Dream Landscape state."""
    return f"{fp.domain}:{fp.edge.source}→{fp.edge.target}"


def build_dream_landscape(
    equivalences: List[Equivalence],
    *,
    base_resistance: float = 0.5,
) -> Landscape:
    """Build a Dream Landscape from detected equivalences.

    States = domain-qualified edges ("A:src→tgt").
    Edges = functional equivalences between domain edges.
    Δ = fingerprint distance (low = high similarity = high relevance).
    R₀ = base_resistance / confidence (speculative hypotheses are expensive).

    The resulting landscape is a valid E₀ Landscape that can be navigated,
    historized, and inspected like any other.
    """
    landscape = Landscape()

    # Collect all states
    states_seen: set = set()
    for eq in equivalences:
        sa = _equivalence_state(eq.fp_a)
        sb = _equivalence_state(eq.fp_b)
        if sa not in states_seen:
            landscape.add_state(sa)
            states_seen.add(sa)
        if sb not in states_seen:
            landscape.add_state(sb)
            states_seen.add(sb)

    # Add equivalence edges (bidirectional)
    for eq in equivalences:
        sa = _equivalence_state(eq.fp_a)
        sb = _equivalence_state(eq.fp_b)
        conf = max(eq.confidence, 0.01)  # avoid division by zero
        r0 = base_resistance / conf
        delta = eq.distance

        landscape.add_edge(sa, sb, delta=delta, resistance=r0)
        landscape.add_edge(sb, sa, delta=delta, resistance=r0)

    return landscape
