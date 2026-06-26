"""
Traces — the reliability-memory engine.

Holds per-edge U/F decay traces with:
  - lazy global decay (K2): O(1) per access, identical to per-step global decay
  - epistemic trust (C186): trust = exp(-staleness / τ_doubt), self-calibrated τ_base
  - surprise dampening (C187): w = 0.5 for surprising revisits
  - adaptive observation (C188): auto-toggles dampening from domain volatility

Formulas:
    U(e) ← ρ·U(e) + w·1[success]        (w = 0.5 on dampened surprise, else 1.0)
    F(e) ← ρ·F(e) + w·1[failure]
    q(e) = (U - F) / (U + F + ε)        reliability ∈ (−1, +1)
    m(e) = U + F                         evidence ∈ [0, ∞)
    penalty(e) = clip(λ_f·F − λ_s·U, ±δ_max)
    trust(e) = exp(−staleness / τ_doubt)
    τ_doubt = τ_base / (1 − stability + trust_ε)
    stability = confirmations / (confirmations + surprises + 1)
"""
from __future__ import annotations

import math
import statistics
from typing import Callable, Dict, List, Optional, Tuple

from .primitives import Edge, Outcome

_RHO = 0.9
_LAMBDA_S = 0.15
_LAMBDA_F = 0.20
_DELTA_MAX = 3.0
_EPSILON = 1e-12
_TRUST_EPSILON = 0.01
_TAU_BASE_FALLBACK = 10.0
_INTER_VISIT_WINDOW = 200
_INTER_VISIT_TRIM = 100


class Traces:
    """Per-edge U/F traces with lazy decay, epistemic trust, and adaptive dampening."""

    def __init__(
        self,
        rho: float = _RHO,
        lambda_s: float = _LAMBDA_S,
        lambda_f: float = _LAMBDA_F,
        delta_max: float = _DELTA_MAX,
        epsilon: float = _EPSILON,
        trust_epsilon: float = _TRUST_EPSILON,
        inter_visit_window: int = _INTER_VISIT_WINDOW,
        surprise_dampening: bool = False,
    ) -> None:
        self.rho = rho
        self.lambda_s = lambda_s
        self.lambda_f = lambda_f
        self.delta_max = delta_max
        self.epsilon = epsilon
        self.trust_epsilon = trust_epsilon
        self.inter_visit_window = inter_visit_window
        self.surprise_dampening = surprise_dampening

        self._U: Dict[Edge, float] = {}
        self._F: Dict[Edge, float] = {}
        self._tau: int = 0
        self._tau_last: Dict[Edge, int] = {}
        self._confirmations: Dict[Edge, float] = {}
        self._surprises: Dict[Edge, float] = {}
        self._inter_visit_intervals: List[int] = []

    # ── core access ───────────────────────────────────────────────────────────

    def _effective_traces(self, edge: Edge) -> Tuple[float, float]:
        """(U, F) after lazy decay ρ^(τ − τ_last); (0, 0) for virgin edges."""
        if edge not in self._tau_last:
            return 0.0, 0.0
        gap = self._tau - self._tau_last[edge]
        decay = self.rho ** gap
        return self._U.get(edge, 0.0) * decay, self._F.get(edge, 0.0) * decay

    def update(self, edge: Edge, outcome: Outcome) -> None:
        """Record an outcome; apply catch-up decay, record surprise/confirmation, inscribe."""
        is_surprise = False

        if edge in self._tau_last:
            gap = self._tau - self._tau_last[edge]
            if gap > 0:
                decay = self.rho ** gap
                # Catch-up: write decayed values back so the update formula sees them
                self._U[edge] = self._U.get(edge, 0.0) * decay
                self._F[edge] = self._F.get(edge, 0.0) * decay

                if gap > 1:
                    # Decay confirmations/surprises alongside U/F
                    self._confirmations[edge] = self._confirmations.get(edge, 0.0) * decay
                    self._surprises[edge] = self._surprises.get(edge, 0.0) * decay

                    # Surprise = predicted direction (q ≥ 0 → success) ≠ actual
                    u, f = self._U[edge], self._F[edge]
                    q = (u - f) / (u + f + self.epsilon)
                    predicted_success = (q >= 0)
                    actual_success = (outcome != Outcome.FAILURE)
                    is_surprise = (predicted_success != actual_success)

                    if is_surprise:
                        self._surprises[edge] = self._surprises.get(edge, 0.0) + 1.0
                    else:
                        self._confirmations[edge] = self._confirmations.get(edge, 0.0) + 1.0

                    # Track inter-visit interval; trim when window exceeded
                    self._inter_visit_intervals.append(gap)
                    if len(self._inter_visit_intervals) > self.inter_visit_window:
                        self._inter_visit_intervals = self._inter_visit_intervals[-_INTER_VISIT_TRIM:]

        # Inscription weight: halved for a surprising revisit when dampening is on
        w = 0.5 if (is_surprise and self.surprise_dampening) else 1.0

        rho = self.rho
        if outcome == Outcome.SUCCESS:
            self._U[edge] = rho * self._U.get(edge, 0.0) + w
            self._F[edge] = rho * self._F.get(edge, 0.0)
        elif outcome == Outcome.FAILURE:
            self._U[edge] = rho * self._U.get(edge, 0.0)
            self._F[edge] = rho * self._F.get(edge, 0.0) + w
        else:  # PARTIAL — non-canonical; residual (0.2) silently dropped
            self._U[edge] = rho * self._U.get(edge, 0.0) + 0.5 * w
            self._F[edge] = rho * self._F.get(edge, 0.0) + 0.3 * w

        self._tau += 1
        self._tau_last[edge] = self._tau

    # ── scalar metrics ────────────────────────────────────────────────────────

    def trace_quality(self, edge: Edge) -> float:
        """q = (U − F) / (U + F + ε)  ∈ (−1, +1).  Alias: quality."""
        u, f = self._effective_traces(edge)
        return (u - f) / (u + f + self.epsilon)

    quality = trace_quality

    def trace_load(self, edge: Edge) -> float:
        """m = U + F  ∈ [0, ∞).  Alias: mass."""
        u, f = self._effective_traces(edge)
        return u + f

    mass = trace_load

    def penalty(self, edge: Edge) -> float:
        """δ_H = clip(λ_f·F − λ_s·U, ±δ_max)."""
        u, f = self._effective_traces(edge)
        raw = self.lambda_f * f - self.lambda_s * u
        return max(-self.delta_max, min(self.delta_max, raw))

    # ── epistemic trust ───────────────────────────────────────────────────────

    def stability(self, edge: Edge) -> float:
        """confirmations / (confirmations + surprises + 1)  ∈ [0, 1)."""
        if edge not in self._tau_last:
            return 0.0
        gap = self._tau - self._tau_last[edge]
        decay = self.rho ** gap
        conf = self._confirmations.get(edge, 0.0) * decay
        surp = self._surprises.get(edge, 0.0) * decay
        return conf / (conf + surp + 1.0)

    def _tau_base(self) -> float:
        """Median inter-visit interval; fallback 10.0 when none."""
        if not self._inter_visit_intervals:
            return _TAU_BASE_FALLBACK
        return statistics.median(self._inter_visit_intervals)

    def trust(self, edge: Edge) -> float:
        """exp(−staleness / τ_doubt); 1.0 for virgin or just-visited edges."""
        if edge not in self._tau_last:
            return 1.0
        staleness = self._tau - self._tau_last[edge]
        if staleness == 0:
            return 1.0
        stab = self.stability(edge)
        tau_doubt = self._tau_base() / (1.0 - stab + self.trust_epsilon)
        return math.exp(-staleness / tau_doubt)

    def penalty_trusted(self, edge: Edge) -> float:
        """δ_H_trusted = penalty(edge) · trust(edge)."""
        return self.penalty(edge) * self.trust(edge)

    # ── adaptive observation ──────────────────────────────────────────────────

    def surprise_rate(self) -> float:
        """Global Σsurprises / (Σconf + Σsurp); 0.0 if no revisit events."""
        total_surp = sum(self._surprises.values())
        total_conf = sum(self._confirmations.values())
        total = total_conf + total_surp
        return 0.0 if total == 0 else total_surp / total

    def classify_experience(self) -> str:
        """'stable' | 'volatile' | 'exploratory'."""
        total_surp = sum(self._surprises.values())
        total_conf = sum(self._confirmations.values())
        total = total_conf + total_surp
        if total < 3:
            return "exploratory"
        return "volatile" if (total_surp / total) >= 0.3 else "stable"

    def adapt_from_experience(self) -> bool:
        """Toggle surprise_dampening from classify_experience(); returns True if changed."""
        cls = self.classify_experience()
        if cls == "volatile" and not self.surprise_dampening:
            self.surprise_dampening = True
            return True
        if cls == "stable" and self.surprise_dampening:
            self.surprise_dampening = False
            return True
        return False

    # ── persistence ───────────────────────────────────────────────────────────

    def to_snapshot_dict(self) -> dict:
        """Serialize to a JSON-compatible dict.  Key format: 'source\\x1ftarget'."""
        def _key(e: Edge) -> str:
            return f"{e.source}\x1f{e.target}"

        return {
            "tau": self._tau,
            "tau_last": {_key(e): v for e, v in self._tau_last.items()},
            "U": {_key(e): v for e, v in self._U.items()},
            "F": {_key(e): v for e, v in self._F.items()},
            "confirmations": {_key(e): v for e, v in self._confirmations.items()},
            "surprises": {_key(e): v for e, v in self._surprises.items()},
            "inter_visit_intervals": list(self._inter_visit_intervals),
            "params": {
                "rho": self.rho,
                "lambda_s": self.lambda_s,
                "lambda_f": self.lambda_f,
                "delta_max": self.delta_max,
                "surprise_dampening": self.surprise_dampening,
                "inter_visit_window": self.inter_visit_window,
            },
        }

    @classmethod
    def from_snapshot_dict(
        cls,
        d: dict,
        edge_parser: Optional[Callable[[str], Edge]] = None,
    ) -> "Traces":
        """Restore from snapshot; missing keys fall back to defaults."""
        if edge_parser is None:
            def edge_parser(key: str) -> Edge:
                src, tgt = key.split("\x1f", 1)
                return Edge(src, tgt)

        params = d.get("params", {})
        obj = cls(
            rho=params.get("rho", _RHO),
            lambda_s=params.get("lambda_s", _LAMBDA_S),
            lambda_f=params.get("lambda_f", _LAMBDA_F),
            delta_max=params.get("delta_max", _DELTA_MAX),
            surprise_dampening=params.get("surprise_dampening", False),
            inter_visit_window=params.get("inter_visit_window", _INTER_VISIT_WINDOW),
        )
        obj._tau = d.get("tau", 0)
        obj._tau_last = {edge_parser(k): v for k, v in d.get("tau_last", {}).items()}
        obj._U = {edge_parser(k): v for k, v in d.get("U", {}).items()}
        obj._F = {edge_parser(k): v for k, v in d.get("F", {}).items()}
        obj._confirmations = {edge_parser(k): v for k, v in d.get("confirmations", {}).items()}
        obj._surprises = {edge_parser(k): v for k, v in d.get("surprises", {}).items()}
        obj._inter_visit_intervals = list(d.get("inter_visit_intervals", []))
        return obj
