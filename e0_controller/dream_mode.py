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


class DreamObserver:
    """Passive observer that watches N domains and detects cross-domain patterns.

    Holds read-only references to domain landscapes. Never mutates them.
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

        For each pair of dream-ready domains:
        1. Extract fingerprints
        2. Find equivalences (quantile-based)
        3. Update (or build) the Dream Landscape incrementally

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

        self._cycle_count += 1

        dl = self._dream_landscape
        return DreamCycleResult(
            domains_observed=ready,
            domains_skipped=skipped,
            equivalences_found=len(all_equivalences),
            equivalences_new=new_count,
            dream_landscape_states=len(dl.states) if dl else 0,
            dream_landscape_edges=len(dl.edges) if dl else 0,
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
