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
    ):
        if len(universes) < 2:
            raise ValueError("CouplingRouter requires at least 2 universes")
        self.universes: Dict[str, Universe] = {u.name: u for u in universes}
        self.base_resistance = base_resistance
        self.min_delta = min_delta
        self.landscape = self._build_routing_landscape(universes)

    # ── Construction ──

    def _build_routing_landscape(self, universes: List[Universe]) -> Landscape:
        """Build complete graph: every pair of universes gets a bidirectional edge."""
        L = Landscape()
        names = [u.name for u in universes]
        for i, ua in enumerate(universes):
            for ub in universes[i + 1:]:
                delta = max(structural_distance(ua, ub), self.min_delta)
                L.add_edge(ua.name, ub.name, delta=delta, resistance=self.base_resistance)
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

    def _edge_metrics(self, a: str, b: str) -> tuple:
        """Get (delta, trace_quality) for a coupling edge, checking both directions."""
        for src, tgt in [(a, b), (b, a)]:
            delta = self.landscape.difference(src, tgt)
            if delta is not None:
                quality = self.landscape.historization.trace_quality(Edge(src, tgt))
                return delta, quality
        return None, 0.0

    # ── Historization ──

    def historize(self, source: str, target: str, outcome: Outcome) -> None:
        """Record the outcome of a coupling interaction."""
        for src, tgt in [(source, target), (target, source)]:
            if self.landscape.has_edge(src, tgt):
                self.landscape.historization.update(Edge(src, tgt), outcome)
                return

    # ── Dynamic Membership ──

    def add_universe(self, universe: Universe) -> None:
        """Add a new universe and connect it to all existing ones."""
        if universe.name in self.universes:
            return
        self.universes[universe.name] = universe
        for name, u in self.universes.items():
            if name != universe.name:
                delta = max(structural_distance(universe, u), self.min_delta)
                if not self.landscape.has_edge(universe.name, name):
                    self.landscape.add_edge(
                        universe.name, name,
                        delta=delta, resistance=self.base_resistance,
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

    def coupling_history(self, a: str, b: str) -> dict:
        """Get coupling history between two universes."""
        for src, tgt in [(a, b), (b, a)]:
            edge = Edge(src, tgt)
            if self.landscape.has_edge(src, tgt):
                return {
                    "delta": self.landscape.difference(src, tgt),
                    "r_eff": self.landscape.effective_resistance(src, tgt),
                    "trace_quality": self.landscape.historization.trace_quality(edge),
                    "trace_load": self.landscape.historization.trace_load(edge),
                }
        return {}

    def summary(self) -> str:
        """Human-readable routing status."""
        lines = [f"CouplingRouter: {len(self.universes)} universes"]
        for name in sorted(self.universes):
            u = self.universes[name]
            rec = self.select_partner(u, CouplingReason.RECOVERY)
            exp = self.select_partner(u, CouplingReason.EXPLORATION)
            rec_str = rec[0].partner.name if rec else "—"
            exp_str = exp[0].partner.name if exp else "—"
            lines.append(f"  {name}: recovery→{rec_str}, exploration→{exp_str}")
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
        result = cross_propose_edges(
            landscape, partner.landscape, current, goal,
            donor_name=partner.name,
        )
        if result.proposals:
            # Historize the successful coupling
            router.historize(requester_name, partner.name, Outcome.SUCCESS)
            return result.proposals[0].target

        # No proposals → coupling didn't help
        router.historize(requester_name, partner.name, Outcome.FAILURE)
        return None

    return routed_peer_fn
