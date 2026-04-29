"""
E₀ ObservationPort (C290)
==========================
DifferenzPort for direct outcome signals — sensor, human, external agent.

Design:
    ObservationPort covers the case where a signal arrives without LLM
    mediation: a sensor reports 'temperature check failed', a human marks
    a transition as wrong, or an external agent reports an outcome.

    Each signal is identified by a string (signal_id). E₀ historizes
    outcomes per (port_name × signal_id) edge — exactly as E1Monitor uses
    (community_idx × function) edges.

    This proves DifferenzPort generalizes: the Historization layer does not
    care whether the difference came from an LLM, a sensor, or a human.
    E₀ treats every port as a hypothesis source and learns to trust or
    dampen it purely through outcome traces.

Edge key: Edge(port_name(), signal_id)
    → "how did signal X perform on port Y?"

Usage:
    port = ObservationPort(name="sensor_A")
    port.observe("temperature_check", Outcome.SUCCESS)
    port.observe("pressure_check", Outcome.FAILURE)
    factor = port.dampening_factor()   # 0.0 < factor <= 1.0
"""

from __future__ import annotations

from typing import List, Optional

from .differenz_port import DifferenzPort
from .historization import Historization
from .primitives import Edge, Outcome


class ObservationPort(DifferenzPort):
    """DifferenzPort for direct outcome signals (sensor / human / agent).

    Lifecycle:
        1. observe(signal_id, outcome)  — when a signal is received
        2. record_outcome(outcome)      — ABC fallback (aggregate signal)
        3. dampening_factor()           — used by plan() to scale steps
        4. has_data()                   — check before reading impact

    Edge key in Historization: Edge(port_name(), signal_id)
    This means: "how did signal X perform on this port?"
    """

    def __init__(self, name: str = "observation") -> None:
        self._name = name
        self._hist: Historization = Historization()

    # ── DifferenzPort: identity ──────────────────────────────────────

    def port_name(self) -> str:
        return self._name

    # ── Signal recording ─────────────────────────────────────────────

    def observe(self, signal_id: str, outcome: Outcome) -> None:
        """Record an outcome for a named signal.

        Edge key: Edge(self._name, signal_id).
        Multiple calls with the same signal_id accumulate traces on that edge.
        Different signal_ids create separate edges — tracked independently.
        """
        self._hist.update(Edge(self._name, signal_id), outcome)

    def record_outcome(self, outcome: Outcome) -> None:
        """DifferenzPort ABC: aggregate-level outcome recording.

        For use when only a single outcome is available without a signal_id.
        Records against the synthetic edge (port_name, 'aggregate').
        Prefer observe() when signal_id is available.
        """
        self._hist.update(Edge(self._name, "aggregate"), outcome)

    # ── Introspection ────────────────────────────────────────────────

    def observed_signals(self) -> List[str]:
        """Return sorted list of all observed signal_ids (incl. 'aggregate')."""
        all_edges = set(self._hist._U.keys()) | set(self._hist._F.keys())
        return sorted({e.target for e in all_edges})

    def has_data(self) -> bool:
        """Return True if any outcomes have been recorded."""
        return self._hist._tau > 0

    # ── Impact reporting ─────────────────────────────────────────────

    def impact_quality(self) -> float:
        """Mean trace_quality over all known (port × signal) edges.

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

    # ── Serialization ─────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dict."""
        def ek(e: Edge) -> str:
            return f"{e.source}→{e.target}"
        return {
            "name": self._name,
            "hist": {
                "U": {ek(e): v for e, v in self._hist._U.items()},
                "F": {ek(e): v for e, v in self._hist._F.items()},
                "tau": self._hist._tau,
                "tau_last": {ek(e): t for e, t in self._hist._tau_last.items()},
            },
        }

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "ObservationPort":
        """Restore from a serialized dict. None → fresh instance (backward compat)."""
        if not data:
            return cls()
        port = cls(name=data.get("name", "observation"))
        hist_data = data.get("hist") or {}
        h = port._hist
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
        return port
