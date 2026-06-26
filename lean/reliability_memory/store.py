"""
ReliabilityStore — public API for reliability memory.

Holds edges (delta, base_cost) and a Traces instance.  Edges are created
bottom-up from observed outcomes — no topology declaration required.

Ranking:  S_eff = Δ · R_eff   where   R_eff = base_cost + penalty_trusted (or penalty)
          recommend() = argmin S_eff over candidates.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Union

from .primitives import Edge, Outcome
from .traces import Traces

_DEFAULT_DELTA = 0.5
_DEFAULT_BASE_COST = 0.3
_MIN_OBSERVATIONS = 5
_COST_FLOOR = 1e-10


@dataclass
class RecommendResult:
    """Return value of ReliabilityStore.recommend()."""
    recommended: Optional[str]
    reason: str
    reliability: float
    observations: int


class ReliabilityStore:
    """Memory sidecar for a long-running agent.

    Usage:
        store = ReliabilityStore.load(path)          # or ReliabilityStore() for fresh
        rec   = store.recommend(state, candidates)   # None on cold start
        action = rec.recommended or agent_choose(candidates)
        outcome = run_and_verify(action)
        store.observe_edge(state, action, outcome)
        store.save(path)
    """

    def __init__(
        self,
        rho: float = 0.9,
        lambda_s: float = 0.15,
        lambda_f: float = 0.20,
        delta_max: float = 3.0,
        default_delta: float = _DEFAULT_DELTA,
        default_base_cost: float = _DEFAULT_BASE_COST,
        min_observations: int = _MIN_OBSERVATIONS,
        epistemic_trust: bool = True,
        adaptive: bool = True,
        surprise_dampening: bool = False,
    ) -> None:
        self._traces = Traces(
            rho=rho,
            lambda_s=lambda_s,
            lambda_f=lambda_f,
            delta_max=delta_max,
            surprise_dampening=surprise_dampening,
        )
        self._delta: Dict[Edge, float] = {}
        self._base_cost: Dict[Edge, float] = {}
        self._count: int = 0
        self.default_delta = default_delta
        self.default_base_cost = default_base_cost
        self.min_observations = min_observations
        self.epistemic_trust = epistemic_trust
        self.adaptive = adaptive

    # ── public API ────────────────────────────────────────────────────────────

    def observe(self, signal_id: str, outcome_str: str) -> dict:
        """Record an aggregate signal outcome on Edge('port', signal_id)."""
        outcome = Outcome(outcome_str)
        self._ensure_edge("port", signal_id)
        edge = Edge("port", signal_id)
        self._traces.update(edge, outcome)
        if self.adaptive:
            self._traces.adapt_from_experience()
        self._count += 1
        return {
            "ok": True,
            "signal_id": signal_id,
            "outcome": outcome_str,
            "reliability": self._traces.trace_quality(edge),
            "observations": self._count,
        }

    def observe_edge(self, source: str, target: str, outcome_str: str) -> dict:
        """Record a directed context→action outcome."""
        outcome = Outcome(outcome_str)
        self._ensure_edge(source, target)
        edge = Edge(source, target)
        self._traces.update(edge, outcome)
        if self.adaptive:
            self._traces.adapt_from_experience()
        self._count += 1
        return {
            "ok": True,
            "source": source,
            "target": target,
            "outcome": outcome_str,
            "observations": self._count,
        }

    def recommend(self, state: str, candidates: List[str]) -> RecommendResult:
        """Return the candidate with lowest S_eff = Δ·R_eff, or None on cold start."""
        if not candidates or self._count < self.min_observations:
            return RecommendResult(
                recommended=None,
                reason=f"cold start ({self._count}/{self.min_observations})",
                reliability=0.0,
                observations=self._count,
            )

        for c in candidates:
            self._ensure_edge(state, c)

        best: Optional[str] = None
        best_score = float("inf")
        best_reliability = 0.0

        for c in candidates:
            edge = Edge(state, c)
            delta = self._delta.get(edge, self.default_delta)
            score = delta * self._effective_cost(state, c)
            if score < best_score:
                best_score = score
                best = c
                best_reliability = self._traces.trace_quality(edge)

        return RecommendResult(
            recommended=best,
            reason="reliability selection (lowest cost)",
            reliability=best_reliability,
            observations=self._count,
        )

    def status(self) -> dict:
        """Observation count, graph size, cold-start flag."""
        nodes: set = set()
        for e in self._delta:
            nodes.add(e.source)
            nodes.add(e.target)
        return {
            "observations": self._count,
            "nodes": len(nodes),
            "edges": len(self._delta),
            "cold_start": self._count < self.min_observations,
        }

    def save(self, path: Union[str, Path]) -> None:
        """Persist store to JSON."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "edges": [
                {
                    "source": e.source,
                    "target": e.target,
                    "delta": self._delta[e],
                    "base_cost": self._base_cost[e],
                }
                for e in self._delta
            ],
            "count": self._count,
            "config": {
                "default_delta": self.default_delta,
                "default_base_cost": self.default_base_cost,
                "min_observations": self.min_observations,
                "epistemic_trust": self.epistemic_trust,
                "adaptive": self.adaptive,
            },
            "traces": self._traces.to_snapshot_dict(),
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Union[str, Path]) -> "ReliabilityStore":
        """Load from JSON; returns a fresh store if file is absent or malformed."""
        try:
            raw = Path(path).read_text(encoding="utf-8")
            data = json.loads(raw)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return cls()

        cfg = data.get("config", {})
        store = cls(
            default_delta=cfg.get("default_delta", _DEFAULT_DELTA),
            default_base_cost=cfg.get("default_base_cost", _DEFAULT_BASE_COST),
            min_observations=cfg.get("min_observations", _MIN_OBSERVATIONS),
            epistemic_trust=cfg.get("epistemic_trust", True),
            adaptive=cfg.get("adaptive", True),
        )
        store._count = data.get("count", 0)
        for e_data in data.get("edges", []):
            edge = Edge(e_data["source"], e_data["target"])
            store._delta[edge] = e_data["delta"]
            store._base_cost[edge] = e_data["base_cost"]
        if "traces" in data:
            store._traces = Traces.from_snapshot_dict(data["traces"])
        return store

    # ── internal helpers ──────────────────────────────────────────────────────

    def _ensure_edge(self, source: str, target: str) -> None:
        edge = Edge(source, target)
        if edge not in self._delta:
            self._delta[edge] = self.default_delta
            self._base_cost[edge] = self.default_base_cost

    def _effective_cost(self, source: str, target: str) -> float:
        """max(base_cost + penalty_trusted (or penalty), 1e-10)."""
        edge = Edge(source, target)
        base = self._base_cost.get(edge, self.default_base_cost)
        pen = (
            self._traces.penalty_trusted(edge)
            if self.epistemic_trust
            else self._traces.penalty(edge)
        )
        return max(base + pen, _COST_FLOOR)
