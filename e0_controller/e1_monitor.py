"""
E₀ E1Monitor (C288)
====================
DifferenzPort implementation for LLM-proposed structure (E1 layer).

Extracted from interactive_session.py (ARC-D: C285–C287) and formalized
as a proper DifferenzPort. The E1Monitor tracks which landscape nodes were
proposed by E1 functions (propose_domain_graph, deepen_domain_graph, etc.)
and historizes their structural impact via (community_idx × function) edges.

Design decisions (locked in ARC-D):
  - "Impact not Quality": E₀ historizes structural consequence, not judgment.
    Whether a node helped navigation (coverage_delta > 0) is the signal.
  - Domain × E1-Function as Edge key: captures per-domain, per-function
    contribution independently.
  - execute_transition excluded: would be circular (E1 produces the Outcome).
  - Analog dampening: inertia_factor, never binary block.
  - Domain key = str(community_of(node, communities)): community index as str.

This module is purely E₀ domain logic — no REPL, no UI, no session coupling.
interactive_session.py delegates to this class.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set

from .differenz_port import DifferenzPort
from .historization import Historization
from .primitives import Edge, Outcome


class E1Monitor(DifferenzPort):
    """Tracks structural impact of E1-proposed landscape nodes.

    Lifecycle:
        1. register_node(node_id, e1_function)   — when E1 proposes a node
        2. record_round(path, outcome, communities) — after each nav round
        3. dampening_factor()                    — used by plan() to scale steps
        4. impact_profile()                      — exposed by cmd_diagnose

    Edge key in Historization: Edge(str(community_idx), e1_function_name)
    This means: "how did function X perform in community Y?"
    """

    def __init__(self) -> None:
        self._proposed_states: Set[str] = set()
        # node_id → e1_function_name that proposed it
        self._proposed_functions: Dict[str, str] = {}
        self._hist: Historization = Historization()

    # ── DifferenzPort: identity ──────────────────────────────────────

    def port_name(self) -> str:
        return "E1"

    # ── Node registration ────────────────────────────────────────────

    def register_node(self, node_id: str, e1_function: str) -> None:
        """Mark a landscape node as E1-proposed.

        Called by _inject_spec_into_landscape (session layer) when nodes
        from an LLM proposal are added to the landscape.

        node_id must match the prefixed id in the landscape
        (e.g. 'T:NODE_A', not 'NODE_A').
        """
        self._proposed_states.add(node_id)
        self._proposed_functions[node_id] = e1_function

    def proposed_nodes(self) -> Set[str]:
        """Return the set of all E1-proposed node ids."""
        return set(self._proposed_states)

    def function_for(self, node_id: str) -> Optional[str]:
        """Return the E1 function name that proposed node_id, or None."""
        return self._proposed_functions.get(node_id)

    # ── Outcome recording ─────────────────────────────────────────────

    def record_round(
        self,
        path: List[str],
        outcome: Outcome,
        communities: List,
    ) -> None:
        """Update impact history for E1-proposed nodes visited in path.

        For each unique (community_idx, e1_function) pair among E1-proposed
        nodes in the path, records the round outcome. Deduplicates per call
        so one confused community doesn't skew the signal by repetition.

        Nodes not found in any community (community_of == -1) are skipped.
        """
        if not (self._proposed_states and communities and path):
            return
        from .explore_learning_cycle_multidomain import community_of
        seen_pairs: Set[tuple] = set()
        for node in path:
            if node not in self._proposed_states:
                continue
            domain_idx = community_of(node, communities)
            if domain_idx == -1:
                continue
            fn = self._proposed_functions.get(node, "propose_domain_graph")
            pair = (domain_idx, fn)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            self._hist.update(Edge(str(domain_idx), fn), outcome)

    def record_outcome(self, outcome: Outcome) -> None:
        """DifferenzPort ABC: single-outcome recording (no path/communities).

        For use when only an aggregate outcome is available, without
        path detail. Records against the synthetic edge ('E1', 'aggregate').
        Prefer record_round() when path data is available.
        """
        self._hist.update(Edge("E1", "aggregate"), outcome)

    # ── Impact reporting ─────────────────────────────────────────────

    def impact_quality(self) -> float:
        """Mean trace_quality over all known (community × function) edges.

        Returns 0.0 when no history is available.
        """
        all_edges = set(self._hist._U.keys()) | set(self._hist._F.keys())
        if not all_edges:
            return 0.0
        qualities = [self._hist.trace_quality(e) for e in all_edges]
        return sum(qualities) / len(qualities)

    def dampening_factor(self) -> float:
        """Mean inertia_factor over all known edges.

        Returns 1.0 when no data — neutral, no overhead on planning.
        """
        all_edges = set(self._hist._U.keys()) | set(self._hist._F.keys())
        if not all_edges:
            return 1.0
        factors = [self._hist.inertia_factor(e) for e in all_edges]
        return sum(factors) / len(factors)

    def impact_profile(self) -> List[dict]:
        """Return per-edge impact data for diagnostics (cmd_diagnose).

        Each entry: {edge, load, quality, inertia, warn}
        warn=True when quality < -0.3 (confused domain × function pair).
        Sorted by community index, then function name.
        """
        all_edges = sorted(
            set(self._hist._U.keys()) | set(self._hist._F.keys()),
            key=lambda e: (e.source, e.target),
        )
        profile = []
        for edge in all_edges:
            q = self._hist.trace_quality(edge)
            profile.append({
                "edge": edge,
                "load": self._hist.trace_load(edge),
                "quality": q,
                "inertia": self._hist.inertia_factor(edge),
                "warn": q < -0.3,
            })
        return profile

    def has_data(self) -> bool:
        """Return True if any outcomes have been recorded."""
        return self._hist._tau > 0

    # ── Serialization ─────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dict."""
        def ek(e: Edge) -> str:
            return f"{e.source}→{e.target}"
        return {
            "proposed_states": list(self._proposed_states),
            "proposed_functions": dict(self._proposed_functions),
            "hist": {
                "U": {ek(e): v for e, v in self._hist._U.items()},
                "F": {ek(e): v for e, v in self._hist._F.items()},
                "tau": self._hist._tau,
                "tau_last": {ek(e): t for e, t in self._hist._tau_last.items()},
            },
        }

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "E1Monitor":
        """Restore from a serialized dict. None → fresh instance (backward compat)."""
        monitor = cls()
        if not data:
            return monitor
        monitor._proposed_states = set(data.get("proposed_states", []))
        monitor._proposed_functions = dict(data.get("proposed_functions", {}))
        hist_data = data.get("hist") or {}
        h = monitor._hist
        for key, v in hist_data.get("U", {}).items():
            parts = key.split("→", 1)
            if len(parts) == 2:
                h._U[Edge(parts[0], parts[1])] = float(v)
        for key, v in hist_data.get("F", {}).items():
            parts = key.split("→", 1)
            if len(parts) == 2:
                h._F[Edge(parts[0], parts[1])] = float(v)
        h._tau = hist_data.get("tau", 0)
        for key, t in hist_data.get("tau_last", {}).items():
            parts = key.split("→", 1)
            if len(parts) == 2:
                h._tau_last[Edge(parts[0], parts[1])] = int(t)
        return monitor
