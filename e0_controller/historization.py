"""
E₀ Controller — Historization
==============================
Success/Failure trace management with separated learning rates.

Spec coverage: §17.1 (U/F Traces), §17.2 (δ_H correction), §17.3 (Clipping).

Core equations:
    U_t(e) = ρ · U_{t-1}(e) + 𝟙_success
    F_t(e) = ρ · F_{t-1}(e) + 𝟙_failure
    δ_H(e) = λ_f · F_t(e) − λ_s · U_t(e)
    δ_H_clipped = clip(δ_H, -δ_max, δ_max)
    R_eff(e) = R₀(e) + δ_H_clipped(e)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .primitives import Edge, Outcome


@dataclass
class TraceRecord:
    """Single historization event for audit trail."""
    tau: int
    edge: Edge
    outcome: Outcome
    r_eff_before: float
    r_eff_after: float


@dataclass
class Historization:
    """
    Separated Success/Failure trace management.

    Successes lower effective resistance (path reinforcement).
    Failures raise effective resistance (path avoidance).
    Decay (ρ < 1) prevents permanent lock-in.
    Clipping (δ_max) ensures bounded dynamics.
    """

    # Learning parameters
    rho: float = 0.9          # decay rate (forgetting)
    lambda_s: float = 0.15    # success learning rate
    lambda_f: float = 0.20    # failure learning rate
    delta_max: float = 3.0    # resistance clipping bound

    # Internal state
    _U: Dict[Edge, float] = field(default_factory=dict)  # success traces
    _F: Dict[Edge, float] = field(default_factory=dict)  # failure traces
    _tau: int = 0
    _log: List[TraceRecord] = field(default_factory=list)

    # --- Public API ---

    def update(self, edge: Edge, outcome: Outcome) -> None:
        """
        Update traces after executing a transition.

        §17.1: U_t(e) = ρ · U_{t-1}(e) + 𝟙_success
               F_t(e) = ρ · F_{t-1}(e) + 𝟙_failure
        """
        # Decay existing traces for this edge
        u_prev = self._U.get(edge, 0.0)
        f_prev = self._F.get(edge, 0.0)

        if outcome == Outcome.SUCCESS:
            self._U[edge] = self.rho * u_prev + 1.0
            self._F[edge] = self.rho * f_prev
        elif outcome == Outcome.FAILURE:
            self._U[edge] = self.rho * u_prev
            self._F[edge] = self.rho * f_prev + 1.0
        else:  # PARTIAL
            self._U[edge] = self.rho * u_prev + 0.5
            self._F[edge] = self.rho * f_prev + 0.3

        self._tau += 1

    def delta_H(self, edge: Edge) -> float:
        """
        Historization correction for an edge.

        §17.2: δ_H(e) = λ_f · F_t(e) − λ_s · U_t(e)
        §17.3: clipped to [-δ_max, +δ_max]

        Positive δ_H → resistance increases (failures dominate).
        Negative δ_H → resistance decreases (successes dominate).
        """
        u = self._U.get(edge, 0.0)
        f = self._F.get(edge, 0.0)
        raw = self.lambda_f * f - self.lambda_s * u
        return max(-self.delta_max, min(raw, self.delta_max))

    def record(self, edge: Edge, outcome: Outcome,
               r_eff_before: float, r_eff_after: float) -> None:
        """Append to audit trail."""
        self._log.append(TraceRecord(
            tau=self._tau, edge=edge, outcome=outcome,
            r_eff_before=r_eff_before, r_eff_after=r_eff_after,
        ))

    # --- Inspection ---

    @property
    def tau(self) -> int:
        """Current time = number of historization events."""
        return self._tau

    @property
    def log(self) -> List[TraceRecord]:
        return list(self._log)

    def success_trace(self, edge: Edge) -> float:
        return self._U.get(edge, 0.0)

    def failure_trace(self, edge: Edge) -> float:
        return self._F.get(edge, 0.0)

    # --- Snapshot export/import (for MemOS) ---

    def to_snapshot_dict(self) -> dict:
        """Export internal state as plain dict for serialization."""
        return {
            "tau": self._tau,
            "rho": self.rho,
            "lambda_s": self.lambda_s,
            "lambda_f": self.lambda_f,
            "delta_max": self.delta_max,
            "U": {e: v for e, v in self._U.items()},
            "F": {e: v for e, v in self._F.items()},
        }

    @classmethod
    def from_snapshot_dict(cls, d: dict, edge_parser) -> Historization:
        """Reconstruct from a snapshot dict.

        edge_parser: callable that converts a dict key back to an Edge.
        """
        H = cls(
            rho=d["rho"],
            lambda_s=d["lambda_s"],
            lambda_f=d["lambda_f"],
            delta_max=d["delta_max"],
        )
        H._tau = d["tau"]
        H._U = {edge_parser(k): v for k, v in d["U"].items()}
        H._F = {edge_parser(k): v for k, v in d["F"].items()}
        return H

    def summary(self) -> Dict[str, float]:
        """Quick overview of historization state."""
        all_edges = set(self._U.keys()) | set(self._F.keys())
        return {
            "tau": self._tau,
            "edges_touched": len(all_edges),
            "total_U": sum(self._U.values()),
            "total_F": sum(self._F.values()),
        }
