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

C68 — Coupling Self-Graph
---------------------------
The coupling process has its own self-graph — a meta-landscape that
tracks which coupling components produce good outcomes.  Same pattern
as the domain SelfGraph (C43), but with coupling-specific nodes:

  Core cycle:
    trigger → selection → exchange → evaluation → recording → trigger

  Modulation:
    weight_mod → selection     (asymmetric weights affect partner choice)
    distance_mod → selection   (structural distances affect partner choice)

After each coupling interaction, coupling_self_historize() records
which components participated and the outcome.  Diagnosis reveals:
  - selection "confused" → partner choice inconsistent
  - exchange "harmful"   → cross-reflexion hurting more than helping
  - weight_mod "harmful" → asymmetric weights counterproductive
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
        self.self_graph: Optional[CouplingSelfGraph] = None

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

    def historize(self, source: str, target: str, outcome: Outcome,
                  *, weight_mod_active: bool = False,
                  distance_mod_active: bool = False) -> None:
        """Record the outcome of a directed coupling: source requested from target.

        Only Edge(source→target) is updated.  The reverse direction has
        its own independent history (C67 asymmetric coupling).

        If self_graph is enabled (C68), also self-historizes the coupling
        components that participated.
        """
        if self.landscape.has_edge(source, target):
            self.landscape.historization.update(
                Edge(source, target), outcome)

        if self.self_graph is not None:
            components = coupling_active_components(
                weight_mod_active=weight_mod_active,
                distance_mod_active=distance_mod_active,
            )
            self.self_graph.self_historize(components, outcome)

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
        has_weight_mod = any(w != 1.0 for w in router._weights.values())
        result = cross_propose_edges(
            landscape, partner.landscape, current, goal,
            donor_name=partner.name,
            coupling_discount=discount,
        )
        if result.proposals:
            router.historize(requester_name, partner.name, Outcome.SUCCESS,
                             weight_mod_active=has_weight_mod)
            return result.proposals[0].target

        router.historize(requester_name, partner.name, Outcome.FAILURE,
                         weight_mod_active=has_weight_mod)
        return None

    return routed_peer_fn


# ──────────────────────────────────────────────
# Coupling Self-Graph (C68)
# ──────────────────────────────────────────────

# Core coupling cycle: always active
COUPLING_CORE = [
    "trigger",       # Coupling request (RECOVERY or EXPLORATION)
    "selection",     # Partner choice by CouplingRouter
    "exchange",      # Cross-reflexion / knowledge transfer
    "evaluation",    # Did the coupling produce progress?
    "recording",     # Historize outcome on routing landscape
]

# Optional modulations: active when features are enabled
COUPLING_MODULATION = ["weight_mod", "distance_mod"]

ALL_COUPLING_COMPONENTS = COUPLING_CORE + COUPLING_MODULATION

# Core cycle edges (tight coupling)
COUPLING_CORE_EDGES = [
    ("trigger", "selection"),
    ("selection", "exchange"),
    ("exchange", "evaluation"),
    ("evaluation", "recording"),
    ("recording", "trigger"),
]

# Modulation edges: feed into selection
COUPLING_MOD_EDGES = [
    ("weight_mod", "selection"),
    ("distance_mod", "selection"),
]

ALL_COUPLING_EDGES = COUPLING_CORE_EDGES + COUPLING_MOD_EDGES

# Parameters (same scale as domain SelfGraph)
_COUPLING_CORE_DELTA = 0.5
_COUPLING_CORE_R0 = 0.3
_COUPLING_MOD_DELTA = 1.0
_COUPLING_MOD_R0 = 1.0


def coupling_active_components(
    *,
    weight_mod_active: bool = False,
    distance_mod_active: bool = False,
) -> List[str]:
    """Return components active in a coupling cycle.

    Core components are always active.  Modulations are active
    when asymmetric weights or dynamic distance updates are in use.
    """
    result = list(COUPLING_CORE)
    if weight_mod_active:
        result.append("weight_mod")
    if distance_mod_active:
        result.append("distance_mod")
    return result


class CouplingSelfGraph:
    """Self-knowledge about the coupling process (C68).

    Same architecture as domain SelfGraph (C43) but with coupling-specific
    components.  Tracks which parts of the coupling pipeline produce good
    outcomes (SUCCESS) and which don't (FAILURE).

    Usage:
        csg = CouplingSelfGraph()
        # After each coupling:
        csg.self_historize(
            coupling_active_components(weight_mod_active=True),
            Outcome.SUCCESS)
        # Query:
        q = csg.component_quality("exchange")  # How well does cross-reflexion work?
    """

    def __init__(self) -> None:
        self._landscape = Landscape()
        self._landscape.historization.rho = 1.0  # Cumulative, no decay
        self._build_topology()

    def _build_topology(self) -> None:
        for src, tgt in COUPLING_CORE_EDGES:
            self._landscape.add_edge(
                src, tgt, _COUPLING_CORE_DELTA, _COUPLING_CORE_R0)
        for src, tgt in COUPLING_MOD_EDGES:
            self._landscape.add_edge(
                src, tgt, _COUPLING_MOD_DELTA, _COUPLING_MOD_R0)

    @property
    def landscape(self) -> Landscape:
        return self._landscape

    def self_historize(self, components: List[str],
                       outcome: Outcome) -> None:
        """Record coupling outcome on edges where both endpoints participated."""
        component_set = set(components)
        for src, tgt in ALL_COUPLING_EDGES:
            if src in component_set and tgt in component_set:
                self._landscape.historization.update(
                    Edge(src, tgt), outcome)

    def component_quality(self, component: str) -> float:
        """Average trace_quality across outgoing edges from component."""
        outgoing = [Edge(s, t) for s, t in ALL_COUPLING_EDGES
                    if s == component]
        if not outgoing:
            return 0.0
        return sum(self._landscape.historization.trace_quality(e)
                   for e in outgoing) / len(outgoing)

    def component_load(self, component: str) -> float:
        """Average trace_load across outgoing edges from component."""
        outgoing = [Edge(s, t) for s, t in ALL_COUPLING_EDGES
                    if s == component]
        if not outgoing:
            return 0.0
        return sum(self._landscape.historization.trace_load(e)
                   for e in outgoing) / len(outgoing)

    def component_inertia(self, component: str,
                          alpha: float = 0.5,
                          mu: float = 5.0) -> float:
        """Average inertia_factor across outgoing edges from component."""
        outgoing = [Edge(s, t) for s, t in ALL_COUPLING_EDGES
                    if s == component]
        if not outgoing:
            return 1.0
        return sum(
            self._landscape.historization.inertia_factor(e, alpha, mu)
            for e in outgoing
        ) / len(outgoing)

    def snapshot(self) -> Dict[str, Dict[str, float]]:
        """Export component metrics for persistence."""
        return {
            c: {
                "load": self.component_load(c),
                "quality": self.component_quality(c),
                "inertia": self.component_inertia(c),
            }
            for c in ALL_COUPLING_COMPONENTS
        }

    def summary(self) -> str:
        """Human-readable coupling self-graph status."""
        lines = ["CouplingSelfGraph:"]
        for c in ALL_COUPLING_COMPONENTS:
            q = self.component_quality(c)
            m = self.component_load(c)
            tag = "mod" if c in COUPLING_MODULATION else "core"
            lines.append(f"  {c} ({tag}): quality={q:+.3f}, load={m:.2f}")
        return "\n".join(lines)


# ──────────────────────────────────────────────
# Coupling Diagnosis (C68)
# ──────────────────────────────────────────────

_LOAD_MIN = 3.0
_QUALITY_CONFUSED = 0.1
_QUALITY_HARMFUL = -0.2


@dataclass
class CouplingComponentAssessment:
    """Assessment of one coupling component."""
    name: str
    load: float
    quality: float
    inertia: float
    status: str   # "healthy" | "confused" | "harmful" | "insufficient_data"
    is_modulation: bool


@dataclass
class CouplingDiagnosis:
    """Diagnosis of the entire coupling self-graph."""
    components: List[CouplingComponentAssessment]
    healthy: List[str]
    confused: List[str]
    harmful: List[str]
    insufficient_data: List[str]
    deactivation_candidates: List[str]
    meta_actions: List[str]


def _assess_coupling_component(
    name: str, csg: CouplingSelfGraph,
) -> CouplingComponentAssessment:
    load = csg.component_load(name)
    quality = csg.component_quality(name)
    inertia = csg.component_inertia(name)
    is_mod = name in COUPLING_MODULATION

    if load < _LOAD_MIN:
        status = "insufficient_data"
    elif quality < _QUALITY_HARMFUL:
        status = "harmful"
    elif abs(quality) < _QUALITY_CONFUSED:
        status = "confused"
    else:
        status = "healthy"

    return CouplingComponentAssessment(
        name=name, load=load, quality=quality, inertia=inertia,
        status=status, is_modulation=is_mod)


def diagnose_coupling(csg: CouplingSelfGraph) -> CouplingDiagnosis:
    """Diagnose the coupling self-graph.

    Same algorithm as diagnose_self_graph (C47) but for coupling components.
    Returns component assessments and actionable meta-actions.
    """
    assessments = [_assess_coupling_component(c, csg)
                   for c in ALL_COUPLING_COMPONENTS]

    healthy = [a.name for a in assessments if a.status == "healthy"]
    confused = [a.name for a in assessments if a.status == "confused"]
    harmful = [a.name for a in assessments if a.status == "harmful"]
    insufficient = [a.name for a in assessments
                    if a.status == "insufficient_data"]

    deactivation = [a.name for a in assessments
                    if a.status == "harmful" and a.is_modulation]

    meta_actions: List[str] = []
    for a in assessments:
        if a.status == "harmful" and a.is_modulation:
            meta_actions.append(
                f"Disable {a.name} (quality={a.quality:+.3f}, "
                f"load={a.load:.1f})")
        elif a.status == "harmful":
            meta_actions.append(
                f"Investigate {a.name}: predominantly negative outcomes "
                f"(quality={a.quality:+.3f})")
        elif a.status == "confused":
            meta_actions.append(
                f"Investigate {a.name}: contradictory outcomes "
                f"(quality={a.quality:+.3f}, load={a.load:.1f})")
    if not meta_actions and not insufficient:
        meta_actions.append("All coupling components healthy")

    return CouplingDiagnosis(
        components=assessments,
        healthy=healthy,
        confused=confused,
        harmful=harmful,
        insufficient_data=insufficient,
        deactivation_candidates=deactivation,
        meta_actions=meta_actions,
    )
