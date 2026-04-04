"""
E₀ Mode Controller (C46)
==========================
Automatic switching between Learn/Execute/Combination operating modes
based on the structural inscription (trace_load) of landscape edges.

Core insight (from E0_LLM_BOOTSTRAP_ARCHITECTURE_v1.md §4):
  - LLM = Muscle (generation/exploration)
  - E0  = Skeleton (structure/judgment/memory)
  - Neither is complete alone — the Mode Controller decides when
    E0 needs LLM assistance based on accumulated experience.

Three modes:
  - LEARN:       All or most edges lack sufficient inscription →
                 every decision needs LLM guidance.
  - EXECUTE:     All edges have sufficient inscription →
                 E0 operates autonomously, no LLM calls.
  - COMBINATION: Some edges have inscription, some don't →
                 LLM is called only for under-explored edges.

The trigger threshold μ is the same parameter used in inertia_factor:
  I(e) = 1 − α · (m/(m+μ)) · (1−|q|)
When trace_load < μ, the edge is "under half-load" — not enough
experience to trust the inscription direction.

See docs/E0_LLM_BOOTSTRAP_ARCHITECTURE_v1.md §4 and §9.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional, Tuple

from .primitives import Edge
from .landscape import Landscape
from .config import DEFAULTS


# ──────────────────────────────────────────────
# 1. Operating Mode Enum
# ──────────────────────────────────────────────

class OperatingMode(Enum):
    """E0 operating mode based on structural inscription coverage."""
    LEARN = "learn"
    EXECUTE = "execute"
    COMBINATION = "combination"


# ──────────────────────────────────────────────
# 2. Mode Controller
# ──────────────────────────────────────────────

class ModeController:
    """
    Monitors a Landscape's edge inscription and determines operating mode.

    The controller inspects trace_load on each edge to decide whether
    E0 has enough experience to operate autonomously (EXECUTE), needs
    full LLM guidance (LEARN), or a selective mix (COMBINATION).

    Parameters
    ----------
    landscape : Landscape
        The landscape to monitor.
    mu : float
        Half-load threshold (same μ as in inertia_factor).
        Edges with trace_load < mu are considered under-explored.
        Default 5.0 matches inertia_factor's default.
    learn_ratio : float
        Fraction of edges that must be under-explored to trigger
        full LEARN mode. Default 0.8 (≥80% under-explored → LEARN).
    """

    def __init__(
        self,
        landscape: Landscape,
        mu: float = DEFAULTS.mu,
        learn_ratio: float = DEFAULTS.learn_ratio,
    ):
        self.landscape = landscape
        self.mu = mu
        self.learn_ratio = learn_ratio

    # ── Edge-level assessment ──

    def edge_load(self, edge: Edge) -> float:
        """Return trace_load for an edge."""
        return self.landscape.historization.trace_load(edge)

    def edge_explored(self, edge: Edge) -> bool:
        """Return True if edge has sufficient inscription (trace_load ≥ μ)."""
        return self.edge_load(edge) >= self.mu

    def edge_needs_llm(self, edge: Edge) -> bool:
        """Return True if edge needs LLM assistance (trace_load < μ)."""
        return not self.edge_explored(edge)

    # ── Landscape-level assessment ──

    def _all_edges(self) -> List[Edge]:
        """Return all edges in the landscape."""
        return list(self.landscape._R0.keys())

    def coverage(self) -> Dict[str, object]:
        """Return inscription coverage statistics.

        Returns dict with:
            total: total number of edges
            explored: edges with trace_load ≥ μ
            unexplored: edges with trace_load < μ
            ratio: fraction of explored edges (0.0–1.0)
        """
        edges = self._all_edges()
        total = len(edges)
        if total == 0:
            return {"total": 0, "explored": 0, "unexplored": 0, "ratio": 0.0}

        explored = sum(1 for e in edges if self.edge_explored(e))
        return {
            "total": total,
            "explored": explored,
            "unexplored": total - explored,
            "ratio": explored / total,
        }

    def current_mode(self) -> OperatingMode:
        """Determine the current operating mode from edge coverage.

        Logic:
          - All edges explored → EXECUTE
          - ≥ learn_ratio fraction unexplored → LEARN
          - Otherwise → COMBINATION
        """
        cov = self.coverage()
        if cov["total"] == 0:
            return OperatingMode.LEARN  # empty landscape → need LLM

        ratio_explored = cov["ratio"]
        if ratio_explored >= 1.0:
            return OperatingMode.EXECUTE
        if ratio_explored <= (1.0 - self.learn_ratio):
            return OperatingMode.LEARN
        return OperatingMode.COMBINATION

    def unexplored_edges(self) -> List[Edge]:
        """Return list of edges that need LLM attention."""
        return [e for e in self._all_edges() if self.edge_needs_llm(e)]

    def explored_edges(self) -> List[Edge]:
        """Return list of edges with sufficient inscription."""
        return [e for e in self._all_edges() if self.edge_explored(e)]

    # ── Neighbor-level filtering ──

    def neighbors_needing_llm(self, state: str) -> List[str]:
        """Return neighbors of state whose edges need LLM assistance."""
        result = []
        for edge in self._all_edges():
            if edge.source == state and self.edge_needs_llm(edge):
                result.append(edge.target)
        return result

    def neighbors_autonomous(self, state: str) -> List[str]:
        """Return neighbors of state whose edges are well-explored."""
        result = []
        for edge in self._all_edges():
            if edge.source == state and self.edge_explored(edge):
                result.append(edge.target)
        return result

    # ── Summary ──

    def summary(self) -> Dict[str, object]:
        """Return a diagnostic summary of mode state."""
        cov = self.coverage()
        return {
            "mode": self.current_mode().value,
            "mu": self.mu,
            "learn_ratio": self.learn_ratio,
            **cov,
        }
