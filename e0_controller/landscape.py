"""
E₀ Controller — Landscape
===========================
The complete transition structure at time t.

Spec coverage: §7 (Landscape L_t), §2.4 (Transition Field v_x(y)).

L_t = (X_t, E_t, v_t, S_t, H_t) where:
    X_t  — reachable states
    E_t  — admissible edges (transitions)
    v_t  — transition field
    S_t  — tension structure
    H_t  — historization

Core functions implemented here:
    1. difference(x, y)          — Δ from stored matrix
    2. base_resistance(x, y)     — R₀ from stored matrix
    3. effective_resistance(x, y) — R₀ + δ_H(U,F)
    4. effective_tension(x, y)   — S_eff = Δ · R_eff
    5. admissible_neighbors(x)   — all y with S_eff < ∞
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from .primitives import Edge, Outcome
from .historization import Historization
from .tension import tension, coherence


@dataclass
class Landscape:
    """
    The current structure of possibilities.

    Build by adding states and edges with their Δ and R₀.
    The landscape evolves through historization — R_eff changes
    as transitions succeed or fail.
    """

    # Static structure
    _states: Set[str] = field(default_factory=set)
    _delta: Dict[Edge, float] = field(default_factory=dict)   # Δ(x→y)
    _R0: Dict[Edge, float] = field(default_factory=dict)      # R₀(x→y)

    # Dynamic structure
    historization: Historization = field(default_factory=Historization)

    # Experimental: curvature modulation (B2)
    curvature_modulation: bool = False

    # Experimental: overlap modulation (C40, Ontodynamics §3.4)
    overlap_modulation: bool = False

    # Experimental: inertia modulation (C42, Ontodynamics §4, Layer 3)
    inertia_modulation: bool = False

    @property
    def mass_modulation(self) -> bool:
        """Backward-compatible alias for inertia_modulation."""
        return self.inertia_modulation

    @mass_modulation.setter
    def mass_modulation(self, value: bool) -> None:
        self.inertia_modulation = value

    # --- Construction ---

    def add_state(self, name: str) -> None:
        """Add a state to the landscape."""
        self._states.add(name)

    def add_edge(self, source: str, target: str,
                 delta: float, resistance: float) -> None:
        """
        Add a directed transition with its Δ and R₀.

        Both states are auto-registered if not already present.
        """
        if delta < 0:
            raise ValueError(f"Δ must be ≥ 0, got {delta}")
        if resistance < 0:
            raise ValueError(f"R₀ must be ≥ 0, got {resistance}")
        self._states.add(source)
        self._states.add(target)
        edge = Edge(source, target)
        self._delta[edge] = delta
        self._R0[edge] = resistance

    # --- Structural Mutation (Bridge 4, Stufe 1) ---

    def remove_edge(self, source: str, target: str) -> None:
        """Remove a directed transition from the landscape.

        Raises KeyError if the edge does not exist.
        Does NOT remove orphaned states — they remain in the state set
        (a state without edges is isolated, not deleted).
        """
        edge = Edge(source, target)
        if edge not in self._R0:
            raise KeyError(f"Edge {source}→{target} does not exist")
        del self._delta[edge]
        del self._R0[edge]
        # Invalidate modulation caches
        self._invalidate_caches()

    def adjust_base_resistance(self, source: str, target: str,
                               new_R0: float) -> float:
        """Change the base resistance R₀ of an existing edge.

        Returns the old R₀ value (for undo support).
        Raises KeyError if edge does not exist.
        Raises ValueError if new_R0 < 0.
        """
        edge = Edge(source, target)
        if edge not in self._R0:
            raise KeyError(f"Edge {source}→{target} does not exist")
        if new_R0 < 0:
            raise ValueError(f"R₀ must be ≥ 0, got {new_R0}")
        old = self._R0[edge]
        self._R0[edge] = new_R0
        self._invalidate_caches()
        return old

    def adjust_delta(self, source: str, target: str,
                     new_delta: float) -> float:
        """Change the difference measure Δ of an existing edge.

        Returns the old Δ value (for undo support).
        Raises KeyError if edge does not exist.
        Raises ValueError if new_delta < 0.
        """
        edge = Edge(source, target)
        if edge not in self._delta:
            raise KeyError(f"Edge {source}→{target} does not exist")
        if new_delta < 0:
            raise ValueError(f"Δ must be ≥ 0, got {new_delta}")
        old = self._delta[edge]
        self._delta[edge] = new_delta
        self._invalidate_caches()
        return old

    def has_edge(self, source: str, target: str) -> bool:
        """Check whether a directed edge exists."""
        return Edge(source, target) in self._R0

    def would_orphan(self, source: str, target: str) -> Set[str]:
        """Return states that would become unreachable if edge is removed.

        A state is 'orphaned' if removing this edge leaves it with
        no incoming AND no outgoing edges.  Returns the empty set
        if no states would be orphaned.
        """
        edge = Edge(source, target)
        if edge not in self._R0:
            return set()
        orphans: Set[str] = set()
        for state in (source, target):
            remaining = [e for e in self._R0
                         if e != edge and (e.source == state or e.target == state)]
            if not remaining:
                orphans.add(state)
        return orphans

    def _invalidate_caches(self) -> None:
        """Clear cached modulation data after structural mutation."""
        if hasattr(self, '_M_H_cache'):
            del self._M_H_cache
        if hasattr(self, '_overlap_cache'):
            del self._overlap_cache
        self._phi_cache = None

    # --- Core Functions (§2–6) ---

    def difference(self, x: str, y: str) -> Optional[float]:
        """
        Function 1: Δ(x, y)

        Returns the difference measure for edge x→y.
        If no edge exists, returns None — meaning "no defined transition",
        NOT "zero difference" (K3 fix).

        Semantics:
            None  → edge does not exist (inadmissible)
            0.0   → edge exists but states are identical
            > 0   → edge exists with structural difference
        """
        edge = Edge(x, y)
        if edge in self._delta:
            return self._delta[edge]
        return None

    def base_resistance(self, x: str, y: str) -> float:
        """
        Function 2: R₀(x→y)

        Returns the base resistance for edge x→y.
        If no edge exists, returns ∞ (inadmissible).
        """
        edge = Edge(x, y)
        if edge not in self._R0:
            return math.inf
        return self._R0[edge]

    def effective_resistance(self, x: str, y: str) -> float:
        """
        Function 3: R_eff(x→y) = R₀(x→y) + δ_H(x→y)

        Base resistance modified by historization.
        Successes lower it, failures raise it.
        Always ≥ ε (never zero, never negative).
        """
        r0 = self.base_resistance(x, y)
        if math.isinf(r0):
            return math.inf
        dh = self.historization.delta_H(Edge(x, y))
        r_eff = r0 + dh
        return max(r_eff, 1e-10)  # structural floor: R > 0 always

    def effective_tension(self, x: str, y: str) -> float:
        """
        Function 4: S_eff(x→y) = Δ(x,y) · R_eff(x→y)

        Effective integration effort for a transition.
        Returns ∞ if edge does not exist (Δ is None) — K3.
        """
        delta = self.difference(x, y)
        if delta is None:
            return math.inf
        r_eff = self.effective_resistance(x, y)
        return tension(delta, r_eff)

    def admissible_neighbors(self, x: str) -> List[str]:
        """
        Function 5: all y where S_eff(x→y) < ∞

        Raw landscape admissibility — returns all neighbors with finite
        tension.  This is the base layer; the Controller applies additional
        K11 thresholds (s_max, c_min) on top of this.  See
        E0Controller._admissible_neighbors() for the full filter.
        """
        neighbors = []
        for edge in self._R0:
            if edge.source == x:
                if not math.isinf(self.effective_tension(x, edge.target)):
                    neighbors.append(edge.target)
        return neighbors

    def transition_field(self, x: str, y: str) -> float:
        """
        §2.4: v_x(y) = Δ(x,y) · M_H(x,y) · exp(-S_eff(x→y))

        When curvature_modulation is False (default), M_H = 1 — the
        current runtime form.

        When curvature_modulation is True, M_H is derived from local
        face holonomy (curvature). High curvature → damped transition.
        M_H is cached and computed from the base (unmodulated) ω to
        avoid circular dependency.

        When inertia_modulation is True, edges with high accumulated
        inscription but contradictory outcomes (low trace quality)
        are dampened. Ontodynamics §4, Layer 3: structural inertia
        from accumulated inscription.

        Higher v = more structurally open transition.
        Returns 0.0 if edge does not exist (no transition capacity).
        """
        delta = self.difference(x, y)
        if delta is None:
            return 0.0
        s_eff = self.effective_tension(x, y)
        v = delta * coherence(s_eff)
        if self.curvature_modulation:
            v *= self._get_M_H(x, y)
        if self.overlap_modulation:
            v *= self._get_overlap_M_H(x, y)
        if self.inertia_modulation:
            v *= self.historization.inertia_factor(Edge(x, y))
        return v

    def _get_M_H(self, x: str, y: str) -> float:
        """Return cached M_H(x,y). Build cache on first call."""
        cache = getattr(self, '_M_H_cache', None)
        if cache is None:
            self._build_M_H_cache()
        return self._M_H_cache.get((x, y), 1.0)

    def _build_M_H_cache(self) -> None:
        """
        Pre-compute M_H for all edges from base (unmodulated) ω.

        Temporarily disables curvature_modulation to break the
        circular dependency: transition_field → M_H → κ → ω →
        v_rot → v_raw → transition_field.

        The base ω reflects the pure geometric structure.
        M_H then modulates it — a one-way dependency, not circular.
        """
        from .connection import M_H_factor

        # Temporarily disable to compute base ω without M_H
        self.curvature_modulation = False
        saved_inertia = self.inertia_modulation
        self.inertia_modulation = False
        # Invalidate Helmholtz cache so base v is used
        self._phi_cache = None
        try:
            cache = {}
            for edge in self._R0:
                cache[(edge.source, edge.target)] = M_H_factor(
                    self, edge.source, edge.target
                )
        finally:
            self.curvature_modulation = True
            self.inertia_modulation = saved_inertia
            # Invalidate again so downstream sees modulated v
            self._phi_cache = None
        self._M_H_cache = cache

    # --- Overlap modulation (C40) ---

    def _get_overlap_M_H(self, x: str, y: str) -> float:
        """Return cached overlap-based M_H. Build cache on first call."""
        cache = getattr(self, '_overlap_cache', None)
        if cache is None:
            self._build_overlap_cache()
        key = (x, y)
        if key in self._overlap_cache:
            return self._overlap_cache[key].m_h
        return 1.0

    def _build_overlap_cache(self) -> None:
        """
        Pre-compute overlap M_H for all edges.

        Uses base (unmodulated) v to avoid circular dependency:
        transition_field → overlap → v of supporting edges → transition_field.
        """
        from .overlap import overlap_map

        # Temporarily disable all modulations for base v
        saved_curv = self.curvature_modulation
        saved_over = self.overlap_modulation
        saved_inertia = self.inertia_modulation
        self.curvature_modulation = False
        self.overlap_modulation = False
        self.inertia_modulation = False
        self._phi_cache = None
        try:
            self._overlap_cache = overlap_map(self)
        finally:
            self.curvature_modulation = saved_curv
            self.overlap_modulation = saved_over
            self.inertia_modulation = saved_inertia
            self._phi_cache = None

    # --- Inspection ---

    @property
    def states(self) -> Set[str]:
        return set(self._states)

    @property
    def edges(self) -> List[Edge]:
        return list(self._R0.keys())

    def edge_count(self) -> int:
        return len(self._R0)

    def info(self, x: str, y: str) -> Dict:
        """Full info for a single edge."""
        edge = Edge(x, y)
        r0 = self.base_resistance(x, y)
        r_eff = self.effective_resistance(x, y)
        s_eff = self.effective_tension(x, y)
        return {
            "edge": str(edge),
            "delta": self.difference(x, y),  # None if edge missing
            "R0": r0,
            "R_eff": r_eff,
            "delta_H": self.historization.delta_H(edge),
            "S_eff": s_eff,
            "coherence": coherence(s_eff),
            "v": self.transition_field(x, y),
            "U": self.historization.success_trace(edge),
            "F": self.historization.failure_trace(edge),
        }

    def __repr__(self) -> str:
        return (f"Landscape(states={len(self._states)}, "
                f"edges={len(self._R0)}, "
                f"τ={self.historization.tau})")
