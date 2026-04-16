"""Dream Mode — Cross-domain pattern recognition through passive observation.

Detects functional equivalences across domains by comparing edge fingerprints
(trace_quality, trace_load, inertia_factor). Equivalences are stored in a
Dream Landscape that historizes itself — productive analogies strengthen,
bad analogies die through the same mechanism as any E₀ edge.

Key constraint: Dream Mode never mutates any domain landscape.

C109: Fingerprint extraction, distance metric, equivalence detection,
      dream_readiness trigger.
C110: DreamObserver class, dream_cycle, incremental updates,
      feedback historization.
C111: Bridge hypothesis generation — dream equivalences → cross-reflexion
      proposals. Integration via propose_bridges() and make_dream_peer_fn().
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from e0_controller.landscape import Landscape
from e0_controller.primitives import Edge, Outcome
from e0_controller.config import DEFAULTS


# ---------------------------------------------------------------------------
# Edge fingerprint
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EdgeFingerprint:
    """Historization profile of a single edge: (q, m, I, cs)."""
    domain: str
    edge: Edge
    quality: float      # trace_quality ∈ (-1, +1)
    load: float         # trace_load ∈ [0, ∞)
    inertia: float      # inertia_factor ∈ (1-α, 1]
    context_sensitivity: float = 0.0  # C178: ∈ [0, 2]


def edge_fingerprint(
    edge: Edge,
    landscape: Landscape,
    domain: str = "",
    *,
    alpha: float = DEFAULTS.inertia_alpha,
    mu: float = DEFAULTS.mu,
) -> EdgeFingerprint:
    """Extract the historization fingerprint of an edge."""
    h = landscape.historization
    return EdgeFingerprint(
        domain=domain,
        edge=edge,
        quality=h.trace_quality(edge),
        load=h.trace_load(edge),
        inertia=h.inertia_factor(edge, alpha=alpha, mu=mu),
        context_sensitivity=h.context_sensitivity(edge),
    )


def domain_fingerprints(
    landscape: Landscape,
    domain: str = "",
    *,
    alpha: float = DEFAULTS.inertia_alpha,
    mu: float = DEFAULTS.mu,
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
    mu: float = DEFAULTS.mu,
) -> float:
    """Normalized distance between two edge fingerprints.

    Uses the m/(m+μ) sigmoid for trace_load normalization, ensuring
    scale-invariance across domains with different activity levels.

    C178: Includes context_sensitivity as 4th dimension. Edges with
    different context sensitivity are farther apart — confounded edges
    won't match causal ones even if quality/load/inertia coincide.
    """
    dq = a.quality - b.quality
    # Normalize load via sigmoid (same as inertia_factor uses)
    norm_a = a.load / (a.load + mu)
    norm_b = b.load / (b.load + mu)
    dm = norm_a - norm_b
    di = a.inertia - b.inertia
    dcs = a.context_sensitivity - b.context_sensitivity
    return math.sqrt(dq * dq + dm * dm + di * di + dcs * dcs)


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
    mu: float = DEFAULTS.mu,
    alpha: float = DEFAULTS.inertia_alpha,
    quantile: float = DEFAULTS.dream_quantile,
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
# Node fingerprints  (C134b)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NodeFingerprint:
    """Historization profile of a node: sorted quality vector of its edges."""
    domain: str
    node: str
    qualities: tuple  # sorted tuple of edge qualities, ascending
    degree: int       # number of edges (= len(qualities))


def node_fingerprint(
    node: str,
    landscape: Landscape,
    domain: str = "",
) -> NodeFingerprint:
    """Extract quality profile for a single node.

    The profile is the sorted vector of trace_quality values for all
    edges incident to this node (both as source and target).
    Sorting makes the profile invariant to edge ordering.
    """
    h = landscape.historization
    qualities = []
    for edge in landscape.edges:
        if edge.source == node or edge.target == node:
            qualities.append(h.trace_quality(edge))
    qualities.sort()
    return NodeFingerprint(
        domain=domain,
        node=node,
        qualities=tuple(qualities),
        degree=len(qualities),
    )


def node_fingerprints(
    landscape: Landscape,
    domain: str = "",
) -> List[NodeFingerprint]:
    """Extract fingerprints for all nodes in a landscape."""
    return [
        node_fingerprint(n, landscape, domain)
        for n in sorted(landscape.states)
    ]


def node_fingerprint_distance(a: NodeFingerprint, b: NodeFingerprint) -> float:
    """Distance between two node profiles.

    Compares sorted quality vectors element-wise. If degrees differ,
    pads the shorter vector with 0.0 (neutral quality). Distance is
    the RMS of element-wise differences, normalized by max degree.

    Returns value in [0, 2.0] (since quality ∈ (-1, +1)).
    """
    qa = list(a.qualities)
    qb = list(b.qualities)
    max_len = max(len(qa), len(qb))
    if max_len == 0:
        return 0.0

    # Pad shorter vector with 0.0
    while len(qa) < max_len:
        qa.append(0.0)
    while len(qb) < max_len:
        qb.append(0.0)

    sum_sq = sum((x - y) ** 2 for x, y in zip(qa, qb))
    return math.sqrt(sum_sq / max_len)


@dataclass(frozen=True)
class NodeEquivalence:
    """A detected equivalence between two nodes in different domains."""
    fp_a: NodeFingerprint
    fp_b: NodeFingerprint
    distance: float

    @property
    def node_a(self) -> str:
        return self.fp_a.node

    @property
    def node_b(self) -> str:
        return self.fp_b.node

    @property
    def confidence(self) -> float:
        return max(0.0, 1.0 - self.distance)


def find_node_equivalences(
    landscape_a: Landscape,
    landscape_b: Landscape,
    *,
    domain_a: str = "A",
    domain_b: str = "B",
    quantile: float = 0.1,
    max_results: Optional[int] = None,
) -> List[NodeEquivalence]:
    """Find functional equivalences between nodes in two domains.

    Compares node fingerprints (sorted quality profiles) instead of
    individual edge fingerprints. This captures the structural role
    of each node — how it participates across all its relationships.

    Args:
        landscape_a, landscape_b: The two domain landscapes (read-only).
        domain_a, domain_b: Names for reporting.
        quantile: Fraction of pairwise distances to keep (bottom %).
        max_results: Optional cap on returned equivalences.

    Returns:
        List of NodeEquivalence objects, sorted by distance (ascending).
    """
    nfps_a = node_fingerprints(landscape_a, domain_a)
    nfps_b = node_fingerprints(landscape_b, domain_b)

    if not nfps_a or not nfps_b:
        return []

    # Compute all pairwise distances
    pairs: List[NodeEquivalence] = []
    for na in nfps_a:
        for nb in nfps_b:
            d = node_fingerprint_distance(na, nb)
            pairs.append(NodeEquivalence(fp_a=na, fp_b=nb, distance=d))

    pairs.sort(key=lambda eq: eq.distance)

    # Apply quantile threshold
    cutoff_idx = max(1, int(len(pairs) * quantile))
    result = pairs[:cutoff_idx]

    if max_results is not None:
        result = result[:max_results]

    return result


# ---------------------------------------------------------------------------
# WL node fingerprints  (C135)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WLNodeFingerprint:
    """Weisfeiler-Leman-style recursive neighborhood fingerprint.

    Features encode not just the node's own edge qualities, but also
    the aggregated features of its neighbors — recursively to `depth` rounds.
    This captures structural role without knowing edge positions.
    """
    domain: str
    node: str
    features: tuple   # fixed-size feature vector (floats)
    depth: int        # number of WL refinement rounds applied


def _edge_quality_stats(
    node: str,
    landscape: Landscape,
) -> List[float]:
    """Round-0 features: statistics of a node's edge qualities and trace loads.

    Returns 9 floats:
      [mean_q, std_q, degree, pos_fraction,
       min_q, max_q, median_q,
       trace_load_mean, trace_load_std]

    trace_load (U+F) is an independent dimension from quality (U-F)/(U+F).
    Two edges with identical quality can have vastly different trace loads
    depending on bootstrapper confidence, providing additional differentiation.
    """
    h = landscape.historization
    qualities = []
    loads = []
    for edge in landscape.edges:
        if edge.source == node or edge.target == node:
            qualities.append(h.trace_quality(edge))
            loads.append(h.trace_load(edge))

    if not qualities:
        return [0.0] * 9

    n = len(qualities)
    mean_q = sum(qualities) / n
    std_q = (sum((q - mean_q) ** 2 for q in qualities) / n) ** 0.5
    pos_frac = sum(1 for q in qualities if q > 0.0) / n
    min_q = min(qualities)
    max_q = max(qualities)
    sorted_q = sorted(qualities)
    median_q = (sorted_q[n // 2] if n % 2 == 1
                else (sorted_q[n // 2 - 1] + sorted_q[n // 2]) / 2.0)
    load_mean = sum(loads) / n
    load_std = (sum((l - load_mean) ** 2 for l in loads) / n) ** 0.5
    return [mean_q, std_q, float(n), pos_frac,
            min_q, max_q, median_q, load_mean, load_std]


def wl_node_fingerprints(
    landscape: Landscape,
    domain: str = "",
    depth: int = 2,
) -> List[WLNodeFingerprint]:
    """Compute WL-style recursive node fingerprints.

    Round 0: each node gets 9 features:
      [mean_q, std_q, degree, pos_fraction,
       min_q, max_q, median_q, trace_load_mean, trace_load_std]
    Round k: each node's feature vector is extended by (mean, std)
    of each dimension of its neighbors' features from round k-1.

    Feature vector size: 9 at depth 0, grows by 3× per round
    (self + 2×prev_size neighbor aggregation).
    Depth 1 → 27 floats, depth 2 → 81 floats.
    """
    nodes = sorted(landscape.states)

    # Build adjacency map
    neighbors: Dict[str, List[str]] = {n: [] for n in nodes}
    for edge in landscape.edges:
        neighbors[edge.source].append(edge.target)
        neighbors[edge.target].append(edge.source)

    # Round 0: edge quality statistics
    features: Dict[str, List[float]] = {}
    for node in nodes:
        features[node] = _edge_quality_stats(node, landscape)

    # Refinement rounds
    for _ in range(depth):
        new_features: Dict[str, List[float]] = {}
        for node in nodes:
            self_f = features[node]
            neighbor_fs = [features[nb] for nb in neighbors[node]]

            if neighbor_fs:
                n_dims = len(self_f)
                agg: List[float] = []
                for dim in range(n_dims):
                    vals = [f[dim] for f in neighbor_fs]
                    m = sum(vals) / len(vals)
                    s = (sum((v - m) ** 2 for v in vals) / len(vals)) ** 0.5
                    agg.extend([m, s])
                new_features[node] = self_f + agg
            else:
                new_features[node] = self_f + [0.0] * (2 * len(self_f))
        features = new_features

    return [
        WLNodeFingerprint(
            domain=domain,
            node=node,
            features=tuple(features[node]),
            depth=depth,
        )
        for node in nodes
    ]


def wl_node_distance(a: WLNodeFingerprint, b: WLNodeFingerprint) -> float:
    """Euclidean distance between WL feature vectors, normalized by dimension."""
    fa, fb = a.features, b.features
    n = max(len(fa), len(fb))
    if n == 0:
        return 0.0

    # Pad if needed (should not happen with same depth, but safe)
    fa_list = list(fa) + [0.0] * (n - len(fa))
    fb_list = list(fb) + [0.0] * (n - len(fb))

    sum_sq = sum((x - y) ** 2 for x, y in zip(fa_list, fb_list))
    return math.sqrt(sum_sq / n)


def find_wl_node_equivalences(
    landscape_a: Landscape,
    landscape_b: Landscape,
    *,
    domain_a: str = "A",
    domain_b: str = "B",
    depth: int = 2,
    quantile: float = 0.1,
    max_results: Optional[int] = None,
) -> List[NodeEquivalence]:
    """Find node equivalences using WL-style recursive fingerprints.

    Like find_node_equivalences but with neighborhood-aware profiles
    instead of simple sorted quality vectors. Returns NodeEquivalence
    objects (reusing the existing dataclass with WLNodeFingerprint
    as fp_a/fp_b).
    """
    wl_a = wl_node_fingerprints(landscape_a, domain_a, depth=depth)
    wl_b = wl_node_fingerprints(landscape_b, domain_b, depth=depth)

    if not wl_a or not wl_b:
        return []

    pairs: List[NodeEquivalence] = []
    for na in wl_a:
        for nb in wl_b:
            d = wl_node_distance(na, nb)
            pairs.append(NodeEquivalence(fp_a=na, fp_b=nb, distance=d))

    pairs.sort(key=lambda eq: eq.distance)

    cutoff_idx = max(1, int(len(pairs) * quantile))
    result = pairs[:cutoff_idx]

    if max_results is not None:
        result = result[:max_results]

    return result


def find_wl_node_equivalences_hungarian(
    landscape_a: Landscape,
    landscape_b: Landscape,
    *,
    domain_a: str = "A",
    domain_b: str = "B",
    depth: int = 2,
) -> List[NodeEquivalence]:
    """Find node equivalences using Hungarian algorithm on WL distances.

    Unlike find_wl_node_equivalences (quantile + mutual best), this computes
    the globally optimal 1:1 assignment that minimizes total WL distance
    across all node pairs. Uses scipy.optimize.linear_sum_assignment.

    Returns one NodeEquivalence per node in the smaller landscape,
    sorted by distance (best matches first).
    """
    from scipy.optimize import linear_sum_assignment

    wl_a = wl_node_fingerprints(landscape_a, domain_a, depth=depth)
    wl_b = wl_node_fingerprints(landscape_b, domain_b, depth=depth)

    if not wl_a or not wl_b:
        return []

    # Build full cost matrix
    cost = []
    for na in wl_a:
        row = [wl_node_distance(na, nb) for nb in wl_b]
        cost.append(row)

    row_ind, col_ind = linear_sum_assignment(cost)

    result = []
    for r, c in zip(row_ind, col_ind):
        result.append(NodeEquivalence(
            fp_a=wl_a[r],
            fp_b=wl_b[c],
            distance=cost[r][c],
        ))

    result.sort(key=lambda eq: eq.distance)
    return result


# ---------------------------------------------------------------------------
# Dream readiness
# ---------------------------------------------------------------------------

def dream_readiness(landscape: Landscape, alpha: float = DEFAULTS.inertia_alpha, mu: float = DEFAULTS.mu) -> float:
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
    threshold: float = DEFAULTS.dream_readiness,
    alpha: float = DEFAULTS.inertia_alpha,
    mu: float = DEFAULTS.mu,
) -> bool:
    """Whether a domain's fingerprints are stable enough for dreaming."""
    return dream_readiness(landscape, alpha=alpha, mu=mu) >= threshold


# ---------------------------------------------------------------------------
# Dream compatibility (C168)
# ---------------------------------------------------------------------------

def dream_compatibility(
    landscape_a: Landscape,
    landscape_b: Landscape,
    *,
    depth: int = 2,
) -> float:
    """Structural compatibility score between two domains.

    Delegates to find_structural_resonance() (C260) and returns the
    compatibility field (mean WL distance under Hungarian assignment).
    Lower values indicate higher compatibility — domains whose nodes occupy
    similar structural roles with similar quality distributions.

    Returns a float ≥ 0.  Empirically:
      - < 0.5  → structurally compatible (near-isomorphic topology)
      - 0.5–0.7 → borderline
      - > 0.7  → structurally incompatible (dream matching is noise)

    Returns float('inf') if either landscape has no states.
    """
    return find_structural_resonance(
        landscape_a, landscape_b, depth=depth,
    ).compatibility


def is_dream_compatible(
    landscape_a: Landscape,
    landscape_b: Landscape,
    *,
    threshold: float = DEFAULTS.dream_compatibility_threshold,
    depth: int = 2,
) -> bool:
    """Whether two domains are structurally compatible for cross-domain dreaming."""
    return dream_compatibility(landscape_a, landscape_b, depth=depth) <= threshold


# ---------------------------------------------------------------------------
# Unified Structural Resonance (C260)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StructuralResonance:
    """Result of unified structural resonance analysis between two landscapes.

    Works on arbitrary landscape subsets: community sub-landscapes (intra),
    full landscapes (inter-universe), or any Landscape pair.

    Dream uses this intra-landscape (community ↔ community).
    Coupling uses this inter-landscape (universe ↔ universe).
    Same algorithm, different scale.
    """
    node_equivalences: Tuple  # Tuple[NodeEquivalence, ...]
    compatibility: float      # mean WL distance (lower = more compatible)
    structural_distance: float  # Jaccard state distance (0=identical, 1=disjoint)
    resonance_score: float    # combined score (higher = more resonant)
    nodes_a: int              # node count in landscape_a
    nodes_b: int              # node count in landscape_b
    matched_nodes: int        # number of matched pairs

    @property
    def is_compatible(self) -> bool:
        """Whether the two landscapes are structurally compatible (<0.5)."""
        return self.compatibility < 0.5

    @property
    def top_matches(self) -> Tuple:
        """Top 5 best node matches by distance."""
        return self.node_equivalences[:5]


def find_structural_resonance(
    landscape_a: Landscape,
    landscape_b: Landscape,
    *,
    domain_a: str = "A",
    domain_b: str = "B",
    depth: int = 2,
) -> StructuralResonance:
    """Unified structural resonance between two arbitrary landscapes.

    Combines WL-Hungarian node matching (proven C137) with Jaccard
    structural distance into a single resonance score.

    This is the canonical way to compare any two landscape subsets:
    - Dream: community_0.landscape ↔ community_1.landscape (intra)
    - Coupling: universe_a.landscape ↔ universe_b.landscape (inter)
    - Validation: known-isomorphic graphs should score high

    Parameters
    ----------
    landscape_a, landscape_b : Landscape
        Arbitrary landscape subsets to compare.
    domain_a, domain_b : str
        Labels for the two landscapes (used in fingerprints).
    depth : int
        WL recursion depth (default 2).

    Returns
    -------
    StructuralResonance
        Combined analysis with node equivalences, compatibility,
        structural distance, and resonance score.
    """
    states_a = landscape_a.states
    states_b = landscape_b.states
    n_a = len(states_a)
    n_b = len(states_b)

    # Edge case: empty landscapes
    if n_a == 0 or n_b == 0:
        return StructuralResonance(
            node_equivalences=(),
            compatibility=float("inf"),
            structural_distance=1.0,
            resonance_score=0.0,
            nodes_a=n_a,
            nodes_b=n_b,
            matched_nodes=0,
        )

    # 1. WL-Hungarian node matching (proven C137)
    eqs = find_wl_node_equivalences_hungarian(
        landscape_a, landscape_b,
        domain_a=domain_a, domain_b=domain_b,
        depth=depth,
    )

    # 2. Compatibility = mean WL distance under optimal assignment
    if eqs:
        compatibility = sum(eq.distance for eq in eqs) / len(eqs)
    else:
        compatibility = float("inf")

    # 3. Jaccard structural distance on state sets
    union = states_a | states_b
    if union:
        jaccard_dist = 1.0 - len(states_a & states_b) / len(union)
    else:
        jaccard_dist = 1.0

    # 4. Combined resonance score
    # High resonance = low compatibility distance + structural overlap
    # Score ∈ [0, 1]: 1 = perfect resonance, 0 = no resonance
    if compatibility == float("inf"):
        resonance_score = 0.0
    else:
        # compatibility_score: 1.0 at distance=0, 0.0 at distance≥1.0
        compat_score = max(0.0, 1.0 - compatibility)
        # overlap_score: 1.0 for identical states, 0.0 for disjoint
        overlap_score = 1.0 - jaccard_dist
        # Weighted combination: topology (WL) matters more than naming overlap
        # 70% topology, 30% state overlap
        resonance_score = 0.7 * compat_score + 0.3 * overlap_score

    return StructuralResonance(
        node_equivalences=tuple(eqs),
        compatibility=compatibility,
        structural_distance=jaccard_dist,
        resonance_score=resonance_score,
        nodes_a=n_a,
        nodes_b=n_b,
        matched_nodes=len(eqs),
    )


# ---------------------------------------------------------------------------
# Dream Landscape construction
# ---------------------------------------------------------------------------

def _equivalence_state(fp: EdgeFingerprint) -> str:
    """Encode a fingerprinted edge as a Dream Landscape state."""
    return f"{fp.domain}:{fp.edge.source}→{fp.edge.target}"


def _node_equivalence_state(fp) -> str:
    """Encode a node fingerprint as a Dream Landscape state (C139).

    Uses 'domain:node' format for NodeFingerprint and WLNodeFingerprint.
    """
    return f"{fp.domain}:{fp.node}"


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


# ---------------------------------------------------------------------------
# DreamObserver — passive multi-domain watcher (C110)
# ---------------------------------------------------------------------------

@dataclass
class DreamCycleResult:
    """Outcome of a single dream cycle."""
    domains_observed: List[str]
    domains_skipped: List[str]      # not dream-ready
    equivalences_found: int
    equivalences_new: int           # not previously in Dream Landscape
    dream_landscape_states: int
    dream_landscape_edges: int
    # C119: Structural decay during dream consolidation
    decay_reports: Dict[str, Any] = field(default_factory=dict)  # domain → DecayReport
    # C139: Node-level equivalences via WL + Hungarian
    node_equivalences_found: int = 0
    node_equivalences_new: int = 0
    # C168: Compatibility-gated dreaming
    compatibility_skipped: List[Tuple[str, str]] = field(default_factory=list)
    compatibility_scores: Dict[Tuple[str, str], float] = field(default_factory=dict)


class DreamObserver:
    """Passive observer that watches N domains and detects cross-domain patterns.

    Holds references to domain landscapes. Equivalence detection is
    read-only.  Structural decay (C119) consolidates domain landscapes
    during dream — pruning dormant, low-anchor states.  This mirrors
    biological sleep consolidation: patterns are extracted first, then
    the graph is compressed.

    Maintains a Dream Landscape that historizes equivalences — productive
    analogies strengthen, bad ones decay.

    Usage:
        observer = DreamObserver()
        observer.register("chess", chess_landscape)
        observer.register("invoice", invoice_landscape)

        # Run when domains are stable enough:
        result = observer.dream_cycle()

        # Query equivalences:
        eqs = observer.equivalences_for("chess")

        # Provide feedback (after cross-reflexion used a bridge hypothesis):
        observer.feedback("chess:A→B", "invoice:X→Y", Outcome.SUCCESS)
    """

    def __init__(
        self,
        *,
        readiness_threshold: float = DEFAULTS.dream_readiness,
        quantile: float = DEFAULTS.dream_quantile,
        mu: float = DEFAULTS.mu,
        alpha: float = DEFAULTS.inertia_alpha,
        base_resistance: float = DEFAULTS.dream_base_resistance,
        decay_enabled: bool = False,
        theta_base: float = DEFAULTS.theta_base,
        protected_fn: Optional[Any] = None,
        node_equivalence_method: Optional[str] = None,
        wl_depth: int = DEFAULTS.wl_depth,
        compatibility_threshold: Optional[float] = None,
    ):
        self._domains: Dict[str, Landscape] = {}
        self._dream_landscape: Optional[Landscape] = None
        self._known_edges: set = set()  # track (state_a, state_b) already in DL
        self._cycle_count: int = 0
        self._readiness_threshold = readiness_threshold
        self._quantile = quantile
        self._mu = mu
        self._alpha = alpha
        self._base_resistance = base_resistance
        self.decay_enabled = decay_enabled          # C119
        self._theta_base = theta_base               # C119
        self._protected_fn = protected_fn           # C119: domain → Set[str]
        # C139: Node-level equivalence detection
        if node_equivalence_method is not None and node_equivalence_method not in ("hungarian", "wl"):
            raise ValueError(f"node_equivalence_method must be None, 'hungarian', or 'wl', got {node_equivalence_method!r}")
        self._node_eq_method = node_equivalence_method
        self._wl_depth = wl_depth
        # C168: Compatibility-gated dreaming
        self._compatibility_threshold = compatibility_threshold

    # -- Domain management --------------------------------------------------

    def register(self, name: str, landscape: Landscape) -> None:
        """Register a domain for passive observation. Read-only reference."""
        self._domains[name] = landscape

    def unregister(self, name: str) -> Optional[Landscape]:
        """Remove a domain from observation."""
        return self._domains.pop(name, None)

    @property
    def domain_names(self) -> List[str]:
        return list(self._domains.keys())

    @property
    def dream_landscape(self) -> Optional[Landscape]:
        return self._dream_landscape

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    # -- Dream cycle --------------------------------------------------------

    def dream_cycle(
        self,
        compatibility_threshold: Optional[float] = None,
    ) -> DreamCycleResult:
        """Run one dream observation pass across all domain pairs.

        Steps:
        1. Partition domains by readiness
        2. (C168) Check pairwise compatibility — skip incompatible pairs
        3. Extract edge fingerprints + find equivalences (quantile-based)
        4. (C139) If node_equivalence_method set: find node-level equivalences
           via WL + Hungarian or WL + mutual-best
        5. Update (or build) the Dream Landscape incrementally
        6. If decay_enabled: consolidate each domain landscape (C119)
           — patterns are extracted BEFORE decay, then graphs are compressed

        Domains that are not dream-ready are skipped.
        Domain pairs that are not structurally compatible are skipped (C168).

        *compatibility_threshold* overrides the instance default for this cycle.
        Pass ``None`` (default) to use the observer's configured threshold.

        Returns a DreamCycleResult summarizing the cycle.
        """
        threshold = (
            compatibility_threshold
            if compatibility_threshold is not None
            else self._compatibility_threshold
        )

        # Partition domains by readiness
        ready: List[str] = []
        skipped: List[str] = []
        for name, landscape in self._domains.items():
            if is_dream_ready(landscape, self._readiness_threshold,
                              self._alpha, self._mu):
                ready.append(name)
            else:
                skipped.append(name)

        # C168: Build compatible pairs (skip structurally incompatible)
        compatible_pairs: List[Tuple[str, str]] = []
        compatibility_skipped: List[Tuple[str, str]] = []
        compatibility_scores: Dict[Tuple[str, str], float] = {}
        for i, name_a in enumerate(ready):
            for name_b in ready[i + 1:]:
                if threshold is not None:
                    score = dream_compatibility(
                        self._domains[name_a],
                        self._domains[name_b],
                        depth=self._wl_depth,
                    )
                    compatibility_scores[(name_a, name_b)] = score
                    if score > threshold:
                        compatibility_skipped.append((name_a, name_b))
                        continue
                compatible_pairs.append((name_a, name_b))

        # Collect edge equivalences across compatible domain pairs
        all_equivalences: List[Equivalence] = []
        for name_a, name_b in compatible_pairs:
            eqs = find_equivalences(
                self._domains[name_a],
                self._domains[name_b],
                domain_a=name_a,
                domain_b=name_b,
                mu=self._mu,
                alpha=self._alpha,
                quantile=self._quantile,
            )
            all_equivalences.extend(eqs)

        # Incremental update of Dream Landscape (edge equivalences)
        new_count = self._update_dream_landscape(all_equivalences)

        # C139: Node-level equivalences via WL fingerprints
        all_node_eqs: List[NodeEquivalence] = []
        if self._node_eq_method is not None and len(compatible_pairs) >= 1:
            for name_a, name_b in compatible_pairs:
                if self._node_eq_method == "hungarian":
                    node_eqs = find_wl_node_equivalences_hungarian(
                        self._domains[name_a],
                        self._domains[name_b],
                        domain_a=name_a,
                        domain_b=name_b,
                        depth=self._wl_depth,
                    )
                else:  # "wl" — mutual-best
                    node_eqs = find_wl_node_equivalences(
                        self._domains[name_a],
                        self._domains[name_b],
                        domain_a=name_a,
                        domain_b=name_b,
                        depth=self._wl_depth,
                        quantile=self._quantile,
                    )
                all_node_eqs.extend(node_eqs)

        node_new_count = self._update_dream_landscape_nodes(all_node_eqs)

        # C119: Structural decay — consolidation during dream
        decay_reports: Dict[str, Any] = {}
        if self.decay_enabled:
            from .structural_entropy import (
                find_decay_candidates, apply_decay,
            )
            for name in ready:
                landscape = self._domains[name]
                protected = set()
                if self._protected_fn is not None:
                    protected = self._protected_fn(name)
                candidates = find_decay_candidates(
                    landscape.states,
                    landscape.historization,
                    landscape.edges,
                    theta_base=self._theta_base,
                    protected=protected,
                )
                if candidates:
                    report = apply_decay(landscape, candidates)
                    decay_reports[name] = report

        self._cycle_count += 1

        dl = self._dream_landscape
        return DreamCycleResult(
            domains_observed=ready,
            domains_skipped=skipped,
            equivalences_found=len(all_equivalences),
            equivalences_new=new_count,
            dream_landscape_states=len(dl.states) if dl else 0,
            dream_landscape_edges=len(dl.edges) if dl else 0,
            decay_reports=decay_reports,
            node_equivalences_found=len(all_node_eqs),
            node_equivalences_new=node_new_count,
            compatibility_skipped=compatibility_skipped,
            compatibility_scores=compatibility_scores,
        )

    def _update_dream_landscape(self, equivalences: List[Equivalence]) -> int:
        """Incrementally add new equivalences to the Dream Landscape.

        Existing equivalences are not re-added — their historization
        persists from previous cycles. Returns count of newly added edges.
        """
        if self._dream_landscape is None:
            self._dream_landscape = Landscape()

        dl = self._dream_landscape
        new_count = 0

        for eq in equivalences:
            sa = _equivalence_state(eq.fp_a)
            sb = _equivalence_state(eq.fp_b)
            key_fwd = (sa, sb)
            key_rev = (sb, sa)

            if key_fwd in self._known_edges:
                continue  # already exists, historization persists

            # Add states if new
            if sa not in dl.states:
                dl.add_state(sa)
            if sb not in dl.states:
                dl.add_state(sb)

            # Add bidirectional edges
            conf = max(eq.confidence, 0.01)
            r0 = self._base_resistance / conf
            delta = eq.distance

            dl.add_edge(sa, sb, delta=delta, resistance=r0)
            dl.add_edge(sb, sa, delta=delta, resistance=r0)

            self._known_edges.add(key_fwd)
            self._known_edges.add(key_rev)
            new_count += 1

        return new_count

    def _update_dream_landscape_nodes(
        self, node_eqs: List[NodeEquivalence],
    ) -> int:
        """Incrementally add node-level equivalences to the Dream Landscape (C139).

        Node equivalences are represented as "domain:node" states connected
        by bidirectional edges. Uses the same _known_edges deduplication as
        edge equivalences — both coexist in the same Dream Landscape.

        Returns count of newly added node equivalence edges.
        """
        if not node_eqs:
            return 0

        if self._dream_landscape is None:
            self._dream_landscape = Landscape()

        dl = self._dream_landscape
        new_count = 0

        for neq in node_eqs:
            sa = _node_equivalence_state(neq.fp_a)
            sb = _node_equivalence_state(neq.fp_b)
            key_fwd = (sa, sb)
            key_rev = (sb, sa)

            if key_fwd in self._known_edges:
                continue

            if sa not in dl.states:
                dl.add_state(sa)
            if sb not in dl.states:
                dl.add_state(sb)

            conf = max(neq.confidence, 0.01)
            r0 = self._base_resistance / conf
            delta = neq.distance

            dl.add_edge(sa, sb, delta=delta, resistance=r0)
            dl.add_edge(sb, sa, delta=delta, resistance=r0)

            self._known_edges.add(key_fwd)
            self._known_edges.add(key_rev)
            new_count += 1

        return new_count

    # -- Feedback -----------------------------------------------------------

    def feedback(self, state_a: str, state_b: str, outcome: Outcome) -> bool:
        """Provide feedback on an equivalence after it was used.

        When cross-reflexion uses a bridge hypothesis derived from
        an equivalence, the result (SUCCESS/FAILURE) feeds back into
        the Dream Landscape's historization. This is how bad analogies
        die and good ones strengthen.

        Args:
            state_a: Dream Landscape state (e.g., "chess:A→B")
            state_b: Dream Landscape state (e.g., "invoice:X→Y")
            outcome: Whether the bridge hypothesis was productive.

        Returns:
            True if feedback was recorded, False if edge not found.
        """
        if self._dream_landscape is None:
            return False

        edge = Edge(state_a, state_b)
        if edge not in self._dream_landscape._R0:
            return False

        self._dream_landscape.historization.update(edge, outcome)
        # Also update reverse direction
        rev = Edge(state_b, state_a)
        if rev in self._dream_landscape._R0:
            self._dream_landscape.historization.update(rev, outcome)

        return True

    # -- Query --------------------------------------------------------------

    def equivalences_for(
        self,
        domain: str,
        *,
        min_quality: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """List equivalences involving a specific domain.

        Returns dicts with: partner_domain, partner_edge, own_edge,
        trace_quality, trace_load, confidence (from Dream Landscape).

        Args:
            domain: Name of the domain to query.
            min_quality: If set, only return equivalences with
                trace_quality >= this value on the Dream Landscape edge.
        """
        if self._dream_landscape is None:
            return []

        dl = self._dream_landscape
        prefix = f"{domain}:"
        results: List[Dict[str, Any]] = []

        for edge in dl.edges:
            if not edge.source.startswith(prefix):
                continue

            # Skip node equivalence states (no →); those are handled
            # by node_equivalences_for() (C154).
            if "\u2192" not in edge.source:
                continue

            tq = dl.historization.trace_quality(edge)
            if min_quality is not None and tq < min_quality:
                continue

            r0 = dl._R0.get(edge, 0.0)
            delta_h = dl.historization.delta_H(edge)
            results.append({
                "own_state": edge.source,
                "partner_state": edge.target,
                "trace_quality": tq,
                "trace_load": dl.historization.trace_load(edge),
                "r_eff": r0 + delta_h,
            })

        # Sort by trace_quality descending (best analogies first)
        results.sort(key=lambda r: r["trace_quality"], reverse=True)
        return results

    def node_equivalences_for(
        self,
        domain: str,
        node: Optional[str] = None,
        *,
        min_quality: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """List node-level equivalences involving a specific domain (C154).

        Returns dicts with: own_node, partner_domain, partner_node,
        trace_quality, trace_load.

        Node states in the Dream Landscape use "domain:node" format
        (no → arrow). Edge equivalences use "domain:src→tgt".

        Args:
            domain: Name of the domain to query.
            node: If set, only return equivalences for this specific node.
            min_quality: If set, only return equivalences with
                trace_quality >= this value.
        """
        if self._dream_landscape is None:
            return []

        dl = self._dream_landscape
        prefix = f"{domain}:"
        results: List[Dict[str, Any]] = []

        for edge in dl.edges:
            src = edge.source
            tgt = edge.target

            # Skip edge-level equivalences (contain →)
            if "\u2192" in src or "\u2192" in tgt:
                continue

            if not src.startswith(prefix):
                continue

            # Parse "domain:node"
            own_node = src[len(prefix):]
            colon_idx = tgt.find(":")
            if colon_idx < 0:
                continue
            partner_domain = tgt[:colon_idx]
            partner_node = tgt[colon_idx + 1:]

            if node is not None and own_node != node:
                continue

            tq = dl.historization.trace_quality(edge)
            if min_quality is not None and tq < min_quality:
                continue

            results.append({
                "own_node": own_node,
                "partner_domain": partner_domain,
                "partner_node": partner_node,
                "trace_quality": tq,
                "trace_load": dl.historization.trace_load(edge),
            })

        results.sort(key=lambda r: r["trace_quality"], reverse=True)
        return results

    def readiness_report(self) -> Dict[str, float]:
        """Dream readiness for each registered domain."""
        return {
            name: dream_readiness(landscape, self._alpha, self._mu)
            for name, landscape in self._domains.items()
        }

    def summary(self) -> str:
        """Human-readable status report."""
        lines = [f"DreamObserver — {len(self._domains)} domains, "
                 f"{self._cycle_count} cycles"]

        for name, landscape in self._domains.items():
            r = dream_readiness(landscape, self._alpha, self._mu)
            lines.append(f"  {name}: {len(landscape.edges)} edges, "
                         f"readiness={r:.3f}")

        if self._compatibility_threshold is not None:
            lines.append(f"  Compatibility threshold: {self._compatibility_threshold}")

        if self._dream_landscape:
            dl = self._dream_landscape
            lines.append(f"  Dream Landscape: {len(dl.states)} states, "
                         f"{len(dl.edges)} edges")
        else:
            lines.append("  Dream Landscape: not yet built")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Bridge hypothesis generation (C111)
# ---------------------------------------------------------------------------

@dataclass
class BridgeHypothesis:
    """A concrete cross-reflexion proposal derived from a dream equivalence.

    Wraps a CrossReflexionResult with the dream context that motivated it.
    """
    partner_domain: str
    equivalence_quality: float   # trace_quality of the dream edge
    coupling_discount: float     # derived from equivalence quality
    cross_result: Any            # CrossReflexionResult (avoid circular import)
    edges_added: int


@dataclass
class DreamBridgeResult:
    """Outcome of propose_bridges(): all bridge hypotheses for a target domain."""
    target_domain: str
    bridges: List[BridgeHypothesis]
    total_proposals: int
    total_edges_added: int
    domains_consulted: int
    equivalences_used: int


def dream_coupling_discount(
    equivalence_quality: float,
    base_discount: float = 0.5,
) -> float:
    """Derive coupling discount from dream equivalence quality.

    High-quality equivalences (trace_quality -> 1.0) get closer to
    base_discount (full trust). Low-quality or negative equivalences
    get scaled down toward 0.

    Formula: discount = base * max(0, quality)
    This means:
      - quality=1.0 -> discount=base (full weight)
      - quality=0.5 -> discount=base*0.5 (half weight)
      - quality<=0   -> discount=0 (no trust -- bad analogy)
    """
    return base_discount * max(0.0, equivalence_quality)


def _parse_dream_state(state: str) -> Tuple[str, str, str]:
    """Parse 'domain:src->tgt' into (domain, src, tgt)."""
    colon = state.index(":")
    domain = state[:colon]
    arrow = state.index("\u2192", colon)
    src = state[colon + 1:arrow]
    tgt = state[arrow + 1:]
    return domain, src, tgt


def propose_bridges(
    observer: DreamObserver,
    target_domain: str,
    current: str,
    goal: str,
    *,
    max_bridges: int = 3,
    min_quality: float = 0.0,
    base_discount: float = 0.5,
    max_proposals_per_bridge: int = 5,
) -> DreamBridgeResult:
    """Generate bridge hypotheses from dream equivalences.

    For each high-quality equivalence involving the target domain:
    1. Identify the partner domain
    2. Compute coupling_discount from equivalence quality
    3. Call cross_propose_edges(target, partner, current, goal)
    4. Wrap in BridgeHypothesis

    This is the key C111 integration: dream observation feeds into
    cross-reflexion. The Dream Landscape's historization (via feedback())
    determines which partner domains are trusted -- P3 self-correction.

    Args:
        observer: DreamObserver with registered domains and dream_landscape.
        target_domain: Domain that needs bridge hypotheses (e.g., "invoice").
        current: Current state in target domain.
        goal: Goal state in target domain.
        max_bridges: Maximum number of partner domains to consult.
        min_quality: Minimum equivalence quality to consider.
        base_discount: Base coupling discount (scaled by quality).
        max_proposals_per_bridge: Max proposals per partner domain.

    Returns:
        DreamBridgeResult with all bridge hypotheses.
    """
    from e0_controller.cross_reflexion import cross_propose_edges

    target_landscape = observer._domains.get(target_domain)
    if target_landscape is None:
        return DreamBridgeResult(
            target_domain=target_domain,
            bridges=[],
            total_proposals=0,
            total_edges_added=0,
            domains_consulted=0,
            equivalences_used=0,
        )

    # Get dream equivalences for target domain, filtered by quality
    eqs = observer.equivalences_for(target_domain, min_quality=min_quality)
    if not eqs:
        return DreamBridgeResult(
            target_domain=target_domain,
            bridges=[],
            total_proposals=0,
            total_edges_added=0,
            domains_consulted=0,
            equivalences_used=0,
        )

    # Group by partner domain, take best quality per partner
    partner_best: Dict[str, Dict[str, Any]] = {}
    for eq in eqs:
        partner_state = eq["partner_state"]
        partner_domain, _, _ = _parse_dream_state(partner_state)
        if partner_domain not in partner_best:
            partner_best[partner_domain] = eq
        # eqs are already sorted by quality desc, so first is best

    # Limit to max_bridges partners (already sorted by quality)
    partners = list(partner_best.items())[:max_bridges]

    bridges: List[BridgeHypothesis] = []
    total_proposals = 0
    total_edges_added = 0

    for partner_name, best_eq in partners:
        partner_landscape = observer._domains.get(partner_name)
        if partner_landscape is None:
            continue

        eq_quality = best_eq["trace_quality"]
        discount = dream_coupling_discount(eq_quality, base_discount)

        if discount <= 0.0:
            continue  # negative quality -- don't trust this partner

        cross_result = cross_propose_edges(
            target_landscape,
            partner_landscape,
            current,
            goal,
            max_proposals=max_proposals_per_bridge,
            coupling_discount=discount,
            donor_name=f"dream:{partner_name}",
        )

        bridges.append(BridgeHypothesis(
            partner_domain=partner_name,
            equivalence_quality=eq_quality,
            coupling_discount=discount,
            cross_result=cross_result,
            edges_added=cross_result.edges_added,
        ))

        total_proposals += len(cross_result.proposals)
        total_edges_added += cross_result.edges_added

    return DreamBridgeResult(
        target_domain=target_domain,
        bridges=bridges,
        total_proposals=total_proposals,
        total_edges_added=total_edges_added,
        domains_consulted=len(bridges),
        equivalences_used=len(eqs),
    )


# ---------------------------------------------------------------------------
# Node-level bridge hypothesis generation (C154)
# ---------------------------------------------------------------------------

@dataclass
class NodeBridgeProposal:
    """A single edge proposal derived from node-level equivalence transfer."""
    source: str
    target: str
    delta: float
    resistance: float
    confidence: float
    donor_domain: str
    donor_source: str
    donor_target: str


@dataclass
class NodeBridgeResult:
    """Outcome of propose_node_bridges(): edge proposals from node mapping."""
    target_domain: str
    proposals: List[NodeBridgeProposal]
    edges_added: int
    node_mappings_used: int
    donor_edges_checked: int


def propose_node_bridges(
    observer: DreamObserver,
    target_domain: str,
    current: str,
    goal: Optional[str] = None,
    *,
    base_discount: float = 0.5,
    min_quality: float = 0.0,
    max_proposals: int = 5,
    confidence_floor: float = 0.1,
) -> NodeBridgeResult:
    """Propose edges using node-level equivalences from Hungarian matching (C154).

    Algorithm:
    1. Find which donor nodes match `current` (via Dream Landscape)
    2. For each donor match: list donor's successful outgoing edges
    3. For each donor edge target: check if it maps back to target domain
    4. Propose edge current → mapped_target with discounted parameters

    This is structural transfer: the donor's navigation pattern around
    its equivalent node is proposed as a hypothesis for the target domain.

    Args:
        observer: DreamObserver with node equivalences in Dream Landscape.
        target_domain: Domain that needs proposals.
        current: Current state in target domain.
        goal: Goal state (for proximity sorting).
        base_discount: Base coupling discount for donor parameters.
        min_quality: Minimum equivalence quality on Dream Landscape edge.
        max_proposals: Maximum proposals to return.
        confidence_floor: Minimum confidence for node equivalences.
            Node equivalences from structural matching (Hungarian) start
            with trace_quality=0 in the Dream Landscape. The floor
            breaks the chicken-and-egg: without it, no proposals would
            be generated until historization confirms them — but
            historization requires proposals to exist first.

    Returns:
        NodeBridgeResult with proposed edges and statistics.
    """
    target_landscape = observer._domains.get(target_domain)
    if target_landscape is None:
        return NodeBridgeResult(
            target_domain=target_domain, proposals=[],
            edges_added=0, node_mappings_used=0, donor_edges_checked=0,
        )

    # 1. Find donor nodes matching current
    current_matches = observer.node_equivalences_for(
        target_domain, current, min_quality=min_quality,
    )
    if not current_matches:
        return NodeBridgeResult(
            target_domain=target_domain, proposals=[],
            edges_added=0, node_mappings_used=0, donor_edges_checked=0,
        )

    proposals: List[NodeBridgeProposal] = []
    mappings_used = 0
    edges_checked = 0

    for match in current_matches:
        donor_domain = match["partner_domain"]
        donor_node = match["partner_node"]
        match_quality = match["trace_quality"]

        donor_landscape = observer._domains.get(donor_domain)
        if donor_landscape is None:
            continue

        # 2. List donor's outgoing edges from the matched node
        donor_neighbors = donor_landscape.admissible_neighbors(donor_node)
        if not donor_neighbors:
            continue

        mappings_used += 1

        # Get all node equivalences from donor → target for reverse mapping
        donor_to_target = observer.node_equivalences_for(
            donor_domain, min_quality=min_quality,
        )
        reverse_map: Dict[str, str] = {}
        for eq in donor_to_target:
            if eq["partner_domain"] == target_domain:
                reverse_map[eq["own_node"]] = eq["partner_node"]

        for donor_target in donor_neighbors:
            edges_checked += 1
            mapped_target = reverse_map.get(donor_target)
            if mapped_target is None:
                continue

            # Don't propose self-loops or edges back to current
            if mapped_target == current:
                continue

            # Don't propose edges that already exist
            edge = Edge(current, mapped_target)
            if edge in target_landscape._R0:
                continue

            # Get donor edge parameters
            donor_edge = Edge(donor_node, donor_target)
            donor_delta = 1.0
            donor_r0 = 1.0

            # Use donor landscape parameters with discount
            if donor_edge in donor_landscape._delta:
                donor_delta = donor_landscape._delta[donor_edge]
            if donor_edge in donor_landscape._R0:
                donor_r0 = donor_landscape._R0[donor_edge]

            discount = dream_coupling_discount(
                max(match_quality, confidence_floor), base_discount,
            )
            if discount <= 0.0:
                continue

            # Inflate resistance by inverse discount (more uncertainty)
            proposed_r0 = donor_r0 / max(discount, 0.1)

            proposals.append(NodeBridgeProposal(
                source=current,
                target=mapped_target,
                delta=donor_delta,
                resistance=round(proposed_r0, 4),
                confidence=round(discount, 3),
                donor_domain=donor_domain,
                donor_source=donor_node,
                donor_target=donor_target,
            ))

    # Sort by goal proximity if goal is set, else by confidence
    if goal is not None and target_landscape is not None:
        from e0_controller.reflexive_edge_proposal import _goal_proximity
        proposals.sort(key=lambda p: _goal_proximity(
            target_landscape, p.target, goal,
        ))
    else:
        proposals.sort(key=lambda p: p.confidence, reverse=True)

    proposals = proposals[:max_proposals]

    # Apply proposals to target landscape
    edges_added = 0
    for p in proposals:
        edge = Edge(p.source, p.target)
        if edge not in target_landscape._R0:
            target_landscape.add_edge(
                p.source, p.target, delta=p.delta, resistance=p.resistance,
            )
            edges_added += 1

    return NodeBridgeResult(
        target_domain=target_domain,
        proposals=proposals,
        edges_added=edges_added,
        node_mappings_used=mappings_used,
        donor_edges_checked=edges_checked,
    )


def make_dream_peer_fn(
    observer: DreamObserver,
    domain_name: str,
    goal: str,
    *,
    min_quality: float = 0.0,
    base_discount: float = 0.5,
):
    """Create a peer_fn for E0Controller that consults dream equivalences.

    Returns a callable with signature (landscape, current, neighbors) -> Optional[str]
    compatible with E0Controller.peer_fn.

    When the controller is overloaded, it calls peer_fn. This implementation:
    1. Calls propose_bridges() using current dream state
    2. If any proposals were generated, returns the best proposal target
    3. If no proposals, returns None (controller handles normally)

    This is a non-invasive integration: the controller doesn't know
    it's consulting dream equivalences. It just gets a peer suggestion.
    """
    def _dream_peer(landscape, current, neighbors):
        # 1. Try edge-level bridges first (original path)
        result = propose_bridges(
            observer,
            domain_name,
            current,
            goal,
            min_quality=min_quality,
            base_discount=base_discount,
            max_bridges=1,          # fast: only best partner
            max_proposals_per_bridge=1,
        )

        if result.bridges:
            bridge = result.bridges[0]
            proposals = bridge.cross_result.proposals
            if proposals:
                best_target = proposals[0].target
                if best_target in neighbors:
                    return best_target

        # 2. Fallback: try node-level bridges (C154)
        node_result = propose_node_bridges(
            observer,
            domain_name,
            current,
            goal,
            min_quality=min_quality,
            base_discount=base_discount,
            max_proposals=1,
        )
        if node_result.proposals:
            best_target = node_result.proposals[0].target
            if best_target in neighbors:
                return best_target

        return None

    return _dream_peer
