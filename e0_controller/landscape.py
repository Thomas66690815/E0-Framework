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
        §2.4: v_x(y) = Δ(x,y) · exp(-S_eff(x→y))

        Spec-aligned simplified runtime form (M_H = 1 for v0.1).
        The full generalized form (M_H derived from curvature/topology)
        is not yet implemented.

        Higher v = more structurally open transition.
        Returns 0.0 if edge does not exist (no transition capacity).
        """
        delta = self.difference(x, y)
        if delta is None:
            return 0.0
        s_eff = self.effective_tension(x, y)
        return delta * coherence(s_eff)

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
