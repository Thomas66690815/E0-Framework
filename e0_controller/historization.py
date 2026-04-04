"""
E₀ Controller — Historization
==============================
Success/Failure trace management with separated learning rates.

Spec coverage: §17.1 (U/F Traces), §17.2 (δ_H correction), §17.3 (Clipping).

Core equations:
    U_t(e) = ρ_S · U_{t-1}(e) + 𝟙_success
    F_t(e) = ρ_F · F_{t-1}(e) + 𝟙_failure

Asymmetric decay (C79): ρ_S and ρ_F can differ. When ρ_F > ρ_S,
failures are remembered longer than successes — reflecting that errors
are asymmetrically informative (they reveal multiple blocked paths,
not just one). Default: ρ_S = ρ_F = ρ (symmetric, backward-compatible).
    δ_H(e) = λ_f · F_t(e) − λ_s · U_t(e)
    δ_H_clipped = clip(δ_H, -δ_max, δ_max)
    R_eff(e) = R₀(e) + δ_H_clipped(e)

Global decay (K2): All edges decay by ρ at every global time step τ, not
just when touched. Implemented as lazy catch-up: each edge stores τ_last
(when it was last written). On access, the stored traces are multiplied by
ρ^(τ − τ_last) to account for the missed decay steps. This is mathematically
identical to iterating all edges at every step, but O(1) per access.

Note on PARTIAL outcomes: The canonical spec defines only SUCCESS and FAILURE.
PARTIAL (U += 0.5, F += 0.3) is a runtime convenience extension — operationally
useful but not derived from the minimal canonical core.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional

from .primitives import Edge, Outcome
from .config import DEFAULTS


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
    rho: float = DEFAULTS.rho
    lambda_s: float = DEFAULTS.lambda_s
    lambda_f: float = DEFAULTS.lambda_f
    delta_max: float = DEFAULTS.delta_max
    rho_s: Optional[float] = None  # success-trace decay (None → rho)
    rho_f: Optional[float] = None  # failure-trace decay (None → rho)

    # Internal state
    _U: Dict[Edge, float] = field(default_factory=dict)  # success traces
    _F: Dict[Edge, float] = field(default_factory=dict)  # failure traces
    _tau: int = 0
    _tau_last: Dict[Edge, int] = field(default_factory=dict)  # K2: last-update time per edge
    _log: List[TraceRecord] = field(default_factory=list)

    # --- Lazy Global Decay (K2) ---

    def _effective_traces(self, edge: Edge) -> Tuple[float, float]:
        """
        Return (U, F) with lazy global decay applied.

        If an edge was last written at τ_last and current time is τ,
        the effective traces are ρ^(τ − τ_last) · stored values.
        This accounts for decay steps that occurred while the edge
        was not being directly updated.
        """
        u = self._U.get(edge, 0.0)
        f = self._F.get(edge, 0.0)
        if u == 0.0 and f == 0.0:
            return 0.0, 0.0
        tau_last = self._tau_last.get(edge, self._tau)
        gap = self._tau - tau_last
        if gap > 0:
            rs = self.rho_s if self.rho_s is not None else self.rho
            rf = self.rho_f if self.rho_f is not None else self.rho
            u *= rs ** gap
            f *= rf ** gap
        return u, f

    # --- Public API ---

    def update(self, edge: Edge, outcome: Outcome) -> None:
        """
        Update traces after executing a transition.

        §17.1: U_t(e) = ρ · U_{t-1}(e) + 𝟙_success
               F_t(e) = ρ · F_{t-1}(e) + 𝟙_failure

        K2: Lazy catch-up is applied before the standard formula,
        so edges that haven't been touched for k steps first decay
        by ρ^k, then the single-step ρ + signal is applied.
        """
        # Catch up missed decay steps (K2)
        u_prev, f_prev = self._effective_traces(edge)
        rs = self.rho_s if self.rho_s is not None else self.rho
        rf = self.rho_f if self.rho_f is not None else self.rho

        if outcome == Outcome.SUCCESS:
            self._U[edge] = rs * u_prev + 1.0
            self._F[edge] = rf * f_prev
        elif outcome == Outcome.FAILURE:
            self._U[edge] = rs * u_prev
            self._F[edge] = rf * f_prev + 1.0
        else:  # PARTIAL (runtime extension, not canonical)
            self._U[edge] = rs * u_prev + 0.5
            self._F[edge] = rf * f_prev + 0.3

        self._tau += 1
        self._tau_last[edge] = self._tau

    def delta_H(self, edge: Edge) -> float:
        """
        Historization correction for an edge.

        §17.2: δ_H(e) = λ_f · F_t(e) − λ_s · U_t(e)
        §17.3: clipped to [-δ_max, +δ_max]

        Positive δ_H → resistance increases (failures dominate).
        Negative δ_H → resistance decreases (successes dominate).

        K2: Uses effective (lazily decayed) traces.
        """
        u, f = self._effective_traces(edge)
        raw = self.lambda_f * f - self.lambda_s * u
        return max(-self.delta_max, min(raw, self.delta_max))

    def record(self, edge: Edge, outcome: Outcome,
               r_eff_before: float, r_eff_after: float) -> None:
        """Append to audit trail."""
        self._log.append(TraceRecord(
            tau=self._tau, edge=edge, outcome=outcome,
            r_eff_before=r_eff_before, r_eff_after=r_eff_after,
        ))

    def remove_edges(self, edges) -> None:
        """Clean up trace data for removed edges.

        Deletes _U, _F, _tau_last entries. The _log is preserved —
        historical events remain as a record of what happened, even
        after the structure that produced them is gone.

        Does not modify _tau.
        """
        for e in edges:
            self._U.pop(e, None)
            self._F.pop(e, None)
            self._tau_last.pop(e, None)

    # --- Inspection ---

    @property
    def tau(self) -> int:
        """Current time = number of historization events."""
        return self._tau

    @property
    def log(self) -> List[TraceRecord]:
        return list(self._log)

    def success_trace(self, edge: Edge) -> float:
        u, _ = self._effective_traces(edge)
        return u

    def failure_trace(self, edge: Edge) -> float:
        _, f = self._effective_traces(edge)
        return f

    def trace_load(self, edge: Edge) -> float:
        """
        Total accumulated structural inscription on an edge (Layer 2).

        trace_load(e) = U(e) + F(e)

        Layer model (Ontodynamics §4):
          1. Historization — the process (update/decay)
          2. Structural inscription — what remains (trace_load, trace_quality)
          3. Inertia — functional effect (inertia_factor)
          4. Mass — outward appearance (emergent, not computed here)

        trace_load = 0 → no inscription (virgin edge)
        trace_load > 0 → accumulated structural trace

        K2: Uses effective (lazily decayed) traces.
        """
        u, f = self._effective_traces(edge)
        return u + f

    # Backward-compatible alias
    mass = trace_load

    def trace_quality(self, edge: Edge) -> float:
        """
        Directional balance of accumulated structural inscription (Layer 2).

        q(e) = (U(e) − F(e)) / (U(e) + F(e) + ε)    ∈ (−1, +1)

        Not *how much* inscription, but *what kind*:
          q → +1 : pure success (clearly reinforced)
          q → −1 : pure failure (clearly avoided)
          q ≈  0 : mixed signals or no inscription

        Together (trace_load, trace_quality) decompose the structural
        inscription into magnitude and direction — the two dimensions
        that scalar δ_H conflates.

        K2: Uses effective (lazily decayed) traces.
        """
        u, f = self._effective_traces(edge)
        return (u - f) / (u + f + 1e-12)

    # Backward-compatible alias
    quality = trace_quality

    def inertia_factor(self, edge: Edge,
                       alpha: float = 0.5,
                       mu: float = 5.0) -> float:
        """
        Inertia modulation factor from structural inscription (Layer 3).

        I(e) = 1 − α · (m/(m+μ)) · (1 − |q|)

        where m = trace_load(e), q = trace_quality(e).

        Layer model:
          Layer 2 (inscription) → m and q exist
          Layer 3 (inertia) → this function: how inscription resists change
          Layer 4 (mass) → emergent behavior visible from outside

        Dampens edges with high inscription but low clarity (conflicting
        experience). This captures information that the scalar δ_H
        loses: when U ≈ F, δ_H ≈ 0 looks like "no inscription", but
        m >> 0 with q ≈ 0 means "lots of contradictory inscription".

        Parameters
        ----------
        alpha : float
            Maximum dampening strength at full confusion.
            Default 0.5 → conflicted edge damped to 0.5× at saturation.
        mu : float
            Half-load reference. When m = μ, m_norm = 0.5.
            Default 5.0 → ~5 events for half-load.

        Returns
        -------
        float in (1 − alpha, 1.0]:
            1.0 when no inscription or clear quality (|q| → 1).
            Minimum when high inscription and fully contradictory (|q| ≈ 0).

        K2: Uses effective (lazily decayed) traces.
        """
        u, f = self._effective_traces(edge)
        m = u + f
        if m < 1e-12:
            return 1.0  # no inscription → neutral
        m_norm = m / (m + mu)
        q = (u - f) / (m + 1e-12)
        confusion = 1.0 - abs(q)
        return 1.0 - alpha * m_norm * confusion

    # Backward-compatible alias
    mass_modulation_factor = inertia_factor

    # --- Snapshot export/import (for MemOS) ---

    def to_snapshot_dict(self) -> dict:
        """Export internal state as plain dict for serialization."""
        return {
            "tau": self._tau,
            "rho": self.rho,
            "lambda_s": self.lambda_s,
            "lambda_f": self.lambda_f,
            "delta_max": self.delta_max,
            "rho_s": self.rho_s,
            "rho_f": self.rho_f,
            "U": {e: v for e, v in self._U.items()},
            "F": {e: v for e, v in self._F.items()},
            "tau_last": {e: v for e, v in self._tau_last.items()},
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
            rho_s=d.get("rho_s"),
            rho_f=d.get("rho_f"),
        )
        H._tau = d["tau"]
        H._U = {edge_parser(k): v for k, v in d["U"].items()}
        H._F = {edge_parser(k): v for k, v in d["F"].items()}
        # K2: backward compat — old snapshots without tau_last
        if "tau_last" in d:
            H._tau_last = {edge_parser(k): v for k, v in d["tau_last"].items()}
        else:
            # Assume all edges were current at snapshot time
            all_edges = set(H._U.keys()) | set(H._F.keys())
            H._tau_last = {e: H._tau for e in all_edges}
        return H

    def summary(self) -> Dict[str, float]:
        """Quick overview of historization state (with lazy decay applied)."""
        all_edges = set(self._U.keys()) | set(self._F.keys())
        total_u = 0.0
        total_f = 0.0
        for e in all_edges:
            u, f = self._effective_traces(e)
            total_u += u
            total_f += f
        return {
            "tau": self._tau,
            "edges_touched": len(all_edges),
            "total_U": total_u,
            "total_F": total_f,
        }

    def strategy_profile(
        self,
        edges: Optional[List[Edge]] = None,
        *,
        top_n: int = 0,
    ) -> List[Tuple[Edge, float, float]]:
        """Extract learned strategy as ranked (edge, quality, load) triples.

        Returns edges sorted by trace_quality (descending), filtered to
        those with trace_load > 0 (at least one observation).

        This answers: "What did E₀ learn?"

        Parameters
        ----------
        edges : list of Edge, optional
            Edges to inspect.  If None, uses all edges that have
            been touched (non-zero U or F).
        top_n : int
            If > 0, return only the top N entries.  0 = all.

        Returns
        -------
        list of (Edge, trace_quality, trace_load) sorted by quality desc.
        """
        if edges is None:
            edges = list(set(self._U.keys()) | set(self._F.keys()))
        ranked = []
        for e in edges:
            load = self.trace_load(e)
            if load < 1e-12:
                continue
            ranked.append((e, self.trace_quality(e), load))
        ranked.sort(key=lambda x: x[1], reverse=True)
        if top_n > 0:
            ranked = ranked[:top_n]
        return ranked
