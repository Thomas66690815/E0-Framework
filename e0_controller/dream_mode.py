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
        readiness_threshold: float = 0.8,
        quantile: float = 0.1,
        mu: float = 5.0,
        alpha: float = 0.5,
        base_resistance: float = 0.5,
        decay_enabled: bool = False,
        theta_base: float = 0.5,
        protected_fn: Optional[Any] = None,
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

    def dream_cycle(self) -> DreamCycleResult:
        """Run one dream observation pass across all domain pairs.

        Steps:
        1. Partition domains by readiness
        2. Extract fingerprints + find equivalences (quantile-based)
        3. Update (or build) the Dream Landscape incrementally
        4. If decay_enabled: consolidate each domain landscape (C119)
           — patterns are extracted BEFORE decay, then graphs are compressed

        Domains that are not dream-ready are skipped.

        Returns a DreamCycleResult summarizing the cycle.
        """
        # Partition domains by readiness
        ready: List[str] = []
        skipped: List[str] = []
        for name, landscape in self._domains.items():
            if is_dream_ready(landscape, self._readiness_threshold,
                              self._alpha, self._mu):
                ready.append(name)
            else:
                skipped.append(name)

        # Collect equivalences across all ready domain pairs
        all_equivalences: List[Equivalence] = []
        for i, name_a in enumerate(ready):
            for name_b in ready[i + 1:]:
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

        # Incremental update of Dream Landscape
        new_count = self._update_dream_landscape(all_equivalences)

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

        if not result.bridges:
            return None

        bridge = result.bridges[0]
        proposals = bridge.cross_result.proposals
        if not proposals:
            return None

        # Return best proposal's target if it's in neighbors
        best_target = proposals[0].target
        if best_target in neighbors:
            return best_target

        return None

    return _dream_peer
