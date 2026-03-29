"""
E₀ Self-Graph — Structural Self-Knowledge (C43)
=================================================
E0 learns its own operational structure.

Canon basis: Ontodynamics begins with Selbstunterscheidung — a process
that distinguishes itself from itself before distinguishing from anything
else. The Self-Graph implements this: E0's first domain is E0.

Architecture (from E0_LLM_BOOTSTRAP_ARCHITECTURE_v1.md §6):
  Level 1 — Structural self-image: graph of own components
  Level 2 — Operational reflection: which component helped/hurt
  Level 3 — Meta-control: deactivate components with low quality

The Self-Graph is a dedicated Landscape instance with fixed topology
representing E0's operational cycle:

    amplitude → born → realization → historization → inertia
         ↑                                              │
         └──────────── transition_field ←───────────────┘
                            ↑
                    curvature, overlap (optional modulations)

Each node = an E0 component. Each edge = operational dependency.
After every controller decision, self_historize() records which
components contributed and whether the outcome was good.

Over time, trace_quality on self-graph edges reveals which components
are effective (high |q|) and which are confused (q ≈ 0).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from .primitives import Edge, Outcome
from .landscape import Landscape


# ──────────────────────────────────────────────
# 1. Component Definitions
# ──────────────────────────────────────────────

# Core cycle: always active
CORE_COMPONENTS = [
    "amplitude", "born", "realization", "historization",
    "inertia", "transition_field",
]

# Optional modulations: may or may not be active
MODULATION_COMPONENTS = ["curvature", "overlap"]

ALL_COMPONENTS = CORE_COMPONENTS + MODULATION_COMPONENTS

# Core cycle edges (tight coupling: low Δ, low R₀)
CORE_EDGES = [
    ("amplitude", "born"),
    ("born", "realization"),
    ("realization", "historization"),
    ("historization", "inertia"),
    ("inertia", "transition_field"),
    ("transition_field", "amplitude"),
]

# Modulation edges (looser coupling: higher Δ, higher R₀)
MODULATION_EDGES = [
    ("curvature", "transition_field"),
    ("overlap", "transition_field"),
]

# Default parameters for edge initialization
CORE_DELTA = 0.5
CORE_R0 = 0.3
MODULATION_DELTA = 1.0
MODULATION_R0 = 1.0


# ──────────────────────────────────────────────
# 2. Component Attribution
# ──────────────────────────────────────────────

def active_components(
    *,
    curvature_active: bool = False,
    overlap_active: bool = False,
    inertia_active: bool = False,
) -> List[str]:
    """Return the list of components active in this decision cycle.

    Core components (amplitude, born, realization, historization,
    transition_field) are always active. Modulation components are
    active only when their flags are enabled.

    The `inertia` component is always in the graph (it's part of the
    core cycle) but only *modulates* when inertia_modulation is True.
    When inactive, its edge still exists but gets neutral outcomes.
    """
    result = list(CORE_COMPONENTS)
    if curvature_active:
        result.append("curvature")
    if overlap_active:
        result.append("overlap")
    return result


# ──────────────────────────────────────────────
# 3. SelfGraph
# ──────────────────────────────────────────────

class SelfGraph:
    """E0's structural self-knowledge.

    Wraps a Landscape instance representing E0's own operational cycle.
    Provides targeted APIs for self-historization and component quality
    queries.

    Usage:
        sg = SelfGraph()
        # After each controller step:
        sg.self_historize(["amplitude", "born", "realization", ...], Outcome.SUCCESS)
        # Query which components are effective:
        q = sg.component_quality("curvature")  # → trace_quality
    """

    def __init__(self) -> None:
        self._landscape = Landscape()
        # Self-graph uses ρ=1.0: E0's self-knowledge is cumulative,
        # not decaying. Unlike domain edges that may become stale,
        # E0's operational cycle is fixed — what it learns about its
        # own components is persistent structural knowledge.
        self._landscape.historization.rho = 1.0
        self._build_topology()

    def _build_topology(self) -> None:
        """Initialize the self-graph with E0's operational structure."""
        for src, tgt in CORE_EDGES:
            self._landscape.add_edge(src, tgt, CORE_DELTA, CORE_R0)
        for src, tgt in MODULATION_EDGES:
            self._landscape.add_edge(src, tgt, MODULATION_DELTA, MODULATION_R0)

    @property
    def landscape(self) -> Landscape:
        """Access the underlying Landscape (for inspection/testing)."""
        return self._landscape

    # --- Self-Historization ---

    def self_historize(self, components: List[str], outcome: Outcome) -> None:
        """Record the outcome on all edges involving the given components.

        After a controller decision, call this with the list of components
        that were active in that cycle and the decision outcome.

        Updates traces on every edge where *both* source and target
        are in the active component set. This ensures that only
        edges that actually participated get historized.
        """
        component_set = set(components)
        all_edges = CORE_EDGES + MODULATION_EDGES
        for src, tgt in all_edges:
            if src in component_set and tgt in component_set:
                edge = Edge(src, tgt)
                self._landscape.historization.update(edge, outcome)

    # --- Component Quality Queries ---

    def component_quality(self, component: str) -> float:
        """Aggregate trace_quality for a component.

        Returns the average trace_quality across all edges where
        `component` is the source. This answers: "How good are the
        transitions *from* this component?"

        Returns 0.0 if the component has no outgoing edges in the graph.
        """
        all_edges = CORE_EDGES + MODULATION_EDGES
        outgoing = [Edge(s, t) for s, t in all_edges if s == component]
        if not outgoing:
            return 0.0
        total = sum(self._landscape.historization.trace_quality(e) for e in outgoing)
        return total / len(outgoing)

    def component_load(self, component: str) -> float:
        """Aggregate trace_load for a component.

        Returns the average trace_load across all edges where
        `component` is the source.

        Returns 0.0 if the component has no outgoing edges.
        """
        all_edges = CORE_EDGES + MODULATION_EDGES
        outgoing = [Edge(s, t) for s, t in all_edges if s == component]
        if not outgoing:
            return 0.0
        total = sum(self._landscape.historization.trace_load(e) for e in outgoing)
        return total / len(outgoing)

    def component_inertia(self, component: str,
                          alpha: float = 0.5,
                          mu: float = 5.0) -> float:
        """Aggregate inertia_factor for a component.

        Returns the average inertia_factor across all outgoing edges.
        Low values mean the component has high load but contradictory
        outcomes — a signal that it may be hurting more than helping.

        Returns 1.0 if no outgoing edges (neutral — no information).
        """
        all_edges = CORE_EDGES + MODULATION_EDGES
        outgoing = [Edge(s, t) for s, t in all_edges if s == component]
        if not outgoing:
            return 1.0
        total = sum(
            self._landscape.historization.inertia_factor(e, alpha, mu)
            for e in outgoing
        )
        return total / len(outgoing)

    # --- Snapshot (for MemOS / persistence) ---

    def snapshot(self) -> Dict[str, Dict[str, float]]:
        """Export self-graph state as component → metrics dict.

        Returns a dict mapping each component to its current
        load, quality, and inertia values.
        """
        result = {}
        for comp in ALL_COMPONENTS:
            result[comp] = {
                "load": self.component_load(comp),
                "quality": self.component_quality(comp),
                "inertia": self.component_inertia(comp),
            }
        return result

    def summary(self) -> str:
        """Human-readable self-graph status."""
        lines = ["SelfGraph Status:"]
        snap = self.snapshot()
        for comp in ALL_COMPONENTS:
            m = snap[comp]
            lines.append(
                f"  {comp:20s}  load={m['load']:.2f}  "
                f"quality={m['quality']:+.3f}  "
                f"inertia={m['inertia']:.3f}"
            )
        return "\n".join(lines)
