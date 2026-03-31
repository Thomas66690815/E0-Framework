"""
C66 — Coupling Router: Dynamic Partner Selection for N>2 Universes
===================================================================

When a universe needs help, the CouplingRouter selects the best partner
based on the coupling reason:

  RECOVERY    → partner with best coupling track record (highest quality)
  EXPLORATION → partner with highest structural difference (highest Δ)

The routing landscape is a standard E₀ landscape where each state is a
universe.  Edges encode structural distance (Δ = 1 − Jaccard similarity
of state sets) and coupling cost (R₀).  Coupling outcomes are historized:
SUCCESS reinforces the edge, FAILURE raises effective resistance.

Key insight (from Ontodynamics §3.4): partner selection IS landscape
navigation.  The same primitives that navigate domains also navigate
the space of possible coupling partners.

The selection pressure depends on the coupling reason:
  ┌──────────────┬──────────────────────────────────────────────────────┐
  │ RECOVERY     │ I'm stuck.  I need a partner who has helped before. │
  │              │ → argmax(trace_quality) on coupling edges            │
  ├──────────────┼──────────────────────────────────────────────────────┤
  │ EXPLORATION  │ I need novelty.  I need the most different partner. │
  │              │ → argmax(Δ) on coupling edges                       │
  └──────────────┴──────────────────────────────────────────────────────┘

These are dual selection pressures: RECOVERY exploits coupling history,
EXPLORATION exploits structural diversity.  They are the coupling-level
analogues of GREEDY (low-R_eff) vs AMPLITUDE (high-Δ override).

C67 — Asymmetric Coupling
--------------------------
Each universe carries a coupling_weight (default 1.0).  Edges are now
fully directed: Edge(A→B) and Edge(B→A) have DIFFERENT base resistances:

  R₀(requester → donor) = base_resistance / donor.weight

High-weight donor → low R₀ → cheap to receive from (domain expert).
Low-weight donor  → high R₀ → expensive (generalist / weak partner).

Historization is directional: SUCCESS on Edge(A→B) does NOT affect
Edge(B→A).  Each coupling direction has its own track record.

The donor's weight also modulates the coupling_discount passed to
cross_propose_edges:  discount = min(0.5 · donor_weight, 1.0).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set

from e0_controller.landscape import Landscape
from e0_controller.multiverse import Universe
from e0_controller.primitives import Edge, Outcome


# ──────────────────────────────────────────────
# Types
# ──────────────────────────────────────────────

class CouplingReason(Enum):
    """Why is a universe requesting a coupling partner?"""
    RECOVERY = "recovery"        # Stuck — need experienced partner
    EXPLORATION = "exploration"  # Need novelty — want different partner


@dataclass
class CouplingSelection:
    """Result of partner selection."""
    partner: Universe
    reason: CouplingReason
    score: float
    edge_delta: float
    coupling_quality: float


# ──────────────────────────────────────────────
# Structural Distance
# ──────────────────────────────────────────────

def structural_distance(a: Universe, b: Universe) -> float:
    """1 − Jaccard similarity of state sets.

    Returns 0.0 for identical topologies, 1.0 for completely disjoint.
    Empty landscapes are treated as maximally uncertain (distance 1.0).
    """
    states_a = a.landscape.states
    states_b = b.landscape.states
    union = states_a | states_b
    if not union:
        return 1.0
    return 1.0 - len(states_a & states_b) / len(union)


# ──────────────────────────────────────────────
# CouplingRouter
# ──────────────────────────────────────────────

class CouplingRouter:
    """Dynamic partner selection for N ≥ 2 E₀ universes.

    Maintains a routing landscape (complete graph over all universes)
    and historizes coupling outcomes.  Partner selection navigates this
    meta-landscape using E₀'s standard primitives.
    """

    def __init__(
        self,
        universes: List[Universe],
        base_resistance: float = 1.0,
        min_delta: float = 0.1,
        coupling_weights: Optional[Dict[str, float]] = None,
    ):
        if len(universes) < 2:
            raise ValueError("CouplingRouter requires at least 2 universes")
        self.universes: Dict[str, Universe] = {u.name: u for u in universes}
        self.base_resistance = base_resistance
        self.min_delta = min_delta
        self._weights: Dict[str, float] = {
            u.name: (coupling_weights or {}).get(u.name, 1.0)
            for u in universes
        }
        self.landscape = self._build_routing_landscape(universes)

    # ── Construction ──

    def _donor_resistance(self, donor_name: str) -> float:
        """R₀ for edges where donor_name is the donor (target of request)."""
        return self.base_resistance / self._weights[donor_name]

    def _build_routing_landscape(self, universes: List[Universe]) -> Landscape:
        """Build directed complete graph: every pair gets TWO directed edges.

        Edge(A→B): A requests from B.  R₀ = base_resistance / weight(B).
        Edge(B→A): B requests from A.  R₀ = base_resistance / weight(A).
        """
        L = Landscape()
        for i, ua in enumerate(universes):
            for ub in universes[i + 1:]:
                delta = max(structural_distance(ua, ub), self.min_delta)
                # A→B: B is donor
                L.add_edge(ua.name, ub.name, delta=delta,
                           resistance=self._donor_resistance(ub.name))
                # B→A: A is donor
                L.add_edge(ub.name, ua.name, delta=delta,
                           resistance=self._donor_resistance(ua.name))
        return L

    # ── Partner Selection ──

    def select_partner(
        self,
        requester: Universe,
        reason: CouplingReason,
        max_partners: int = 1,
        exclude: Optional[Set[str]] = None,
    ) -> List[CouplingSelection]:
        """Select best partner(s) for the given coupling reason.

        Returns up to max_partners selections, sorted by score descending.
        """
        exclude = exclude or set()
        candidates = [
            u for name, u in self.universes.items()
            if name != requester.name and name not in exclude
        ]
        if not candidates:
            return []

        scored: List[CouplingSelection] = []
        for c in candidates:
            delta, quality = self._edge_metrics(requester.name, c.name)
            if delta is None:
                continue

            if reason == CouplingReason.RECOVERY:
                score = quality  # Best track record wins
            else:
                score = delta    # Most different wins

            scored.append(CouplingSelection(
                partner=c,
                reason=reason,
                score=score,
                edge_delta=delta,
                coupling_quality=quality,
            ))

        scored.sort(key=lambda s: s.score, reverse=True)
        return scored[:max_partners]

    def _edge_metrics(self, requester: str, candidate: str) -> tuple:
        """Get (delta, trace_quality) for the directed Edge(requester→candidate)."""
        delta = self.landscape.difference(requester, candidate)
        if delta is not None:
            quality = self.landscape.historization.trace_quality(
                Edge(requester, candidate))
            return delta, quality
        return None, 0.0

    # ── Historization ──

    def historize(self, source: str, target: str, outcome: Outcome) -> None:
        """Record the outcome of a directed coupling: source requested from target.

        Only Edge(source→target) is updated.  The reverse direction has
        its own independent history (C67 asymmetric coupling).
        """
        if self.landscape.has_edge(source, target):
            self.landscape.historization.update(
                Edge(source, target), outcome)

    # ── Weight Management (C67) ──

    def get_weight(self, name: str) -> float:
        """Get the coupling weight of a universe."""
        return self._weights[name]

    def set_weight(self, name: str, weight: float) -> None:
        """Set the coupling weight of a universe.

        Updates R₀ on all edges where this universe is the donor:
          R₀(x→name) = base_resistance / weight   for all x.
        """
        if weight <= 0:
            raise ValueError(f"Coupling weight must be > 0, got {weight}")
        self._weights[name] = weight
        new_r0 = self.base_resistance / weight
        for other in self.universes:
            if other != name and self.landscape.has_edge(other, name):
                self.landscape.adjust_base_resistance(other, name, new_r0)

    # ── Dynamic Membership ──

    def add_universe(self, universe: Universe, weight: float = 1.0) -> None:
        """Add a new universe and connect it to all existing ones."""
        if universe.name in self.universes:
            return
        self.universes[universe.name] = universe
        self._weights[universe.name] = weight
        for name, u in self.universes.items():
            if name != universe.name:
                delta = max(structural_distance(universe, u), self.min_delta)
                # new→existing: existing is donor
                if not self.landscape.has_edge(universe.name, name):
                    self.landscape.add_edge(
                        universe.name, name,
                        delta=delta,
                        resistance=self._donor_resistance(name),
                    )
                # existing→new: new universe is donor
                if not self.landscape.has_edge(name, universe.name):
                    self.landscape.add_edge(
                        name, universe.name,
                        delta=delta,
                        resistance=self._donor_resistance(universe.name),
                    )

    def remove_universe(self, name: str) -> Optional[Universe]:
        """Remove a universe.  Returns the removed Universe, or None."""
        if name not in self.universes:
            return None
        removed = self.universes.pop(name)
        # Remove all edges involving this universe
        edges_to_remove = [
            (e.source, e.target) for e in self.landscape.edges
            if e.source == name or e.target == name
        ]
        for src, tgt in edges_to_remove:
            self.landscape.remove_edge(src, tgt)
        return removed

    # ── Inspection ──

    def update_distances(self) -> None:
        """Recompute structural distances after landscapes have changed."""
        names = list(self.universes.keys())
        for i, a_name in enumerate(names):
            for b_name in names[i + 1:]:
                new_delta = max(
                    structural_distance(self.universes[a_name], self.universes[b_name]),
                    self.min_delta,
                )
                for src, tgt in [(a_name, b_name), (b_name, a_name)]:
                    if self.landscape.has_edge(src, tgt):
                        self.landscape.adjust_delta(src, tgt, new_delta)

    @property
    def universe_count(self) -> int:
        return len(self.universes)

    def coupling_history(self, requester: str, donor: str) -> dict:
        """Get directed coupling history: requester's experience with donor."""
        if not self.landscape.has_edge(requester, donor):
            return {}
        edge = Edge(requester, donor)
        return {
            "delta": self.landscape.difference(requester, donor),
            "r_eff": self.landscape.effective_resistance(requester, donor),
            "trace_quality": self.landscape.historization.trace_quality(edge),
            "trace_load": self.landscape.historization.trace_load(edge),
            "donor_weight": self._weights.get(donor, 1.0),
        }

    def summary(self) -> str:
        """Human-readable routing status."""
        lines = [f"CouplingRouter: {len(self.universes)} universes"]
        for name in sorted(self.universes):
            u = self.universes[name]
            w = self._weights[name]
            rec = self.select_partner(u, CouplingReason.RECOVERY)
            exp = self.select_partner(u, CouplingReason.EXPLORATION)
            rec_str = rec[0].partner.name if rec else "—"
            exp_str = exp[0].partner.name if exp else "—"
            lines.append(
                f"  {name} (w={w:.2f}): recovery→{rec_str}, "
                f"exploration→{exp_str}")
        return "\n".join(lines)


# ──────────────────────────────────────────────
# Peer function factory
# ──────────────────────────────────────────────

def make_routed_peer_fn(
    router: CouplingRouter,
    requester_name: str,
    goal: str,
    reason: CouplingReason = CouplingReason.RECOVERY,
):
    """Create a peer_fn for E0Controller that uses the CouplingRouter.

    Returns a callable compatible with controller's peer_fn interface:
        (landscape, current, neighbors) → Optional[str]

    The peer_fn dynamically selects the best partner based on coupling
    reason, then uses cross_propose_edges if available, or returns the
    partner's goal-closest neighbor.
    """
    from e0_controller.cross_reflexion import cross_propose_edges

    def routed_peer_fn(landscape, current, neighbors):
        selections = router.select_partner(
            router.universes[requester_name], reason)
        if not selections:
            return None

        partner = selections[0].partner
        donor_weight = router.get_weight(partner.name)
        discount = min(0.5 * donor_weight, 1.0)
        result = cross_propose_edges(
            landscape, partner.landscape, current, goal,
            donor_name=partner.name,
            coupling_discount=discount,
        )
        if result.proposals:
            # Historize the successful coupling
            router.historize(requester_name, partner.name, Outcome.SUCCESS)
            return result.proposals[0].target

        # No proposals → coupling didn't help
        router.historize(requester_name, partner.name, Outcome.FAILURE)
        return None

    return routed_peer_fn
