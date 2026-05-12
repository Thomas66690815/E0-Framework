"""
E₀ Domain Session (C306)
=========================
Named, persistent domain workspace — the Learn/Apply core for ARC-K.

Architecture
------------
DomainSession = a named Landscape + mode label + FileSensor + episode counter.
DomainStore   = filesystem persistence (memos/domains/{name}.json).

Mode semantics:
    LEARN  — Historization build-up phase. `learn()` is the primary operation.
             `recommend()` returns None during cold-start (< MIN_INSCRIPTIONS).
    APPLY  — Deployment phase. `recommend()` uses full E0Controller judgment.
             `record()` still accepted (online learning / error correction).
    HYBRID — APPLY with continuous recording after each recommend+execute cycle.
             Semantically identical to APPLY — callers can use this label to
             signal intent; the server layer enforces the auto-record loop.

Two-phase pattern (the logistics use-case)
------------------------------------------
1. Build topology:
       session.inject("ORDER_RECEIVED,PICKING,success\\n...", hint="csv")
2. Learn from data:
       session.learn(oracle, n_episodes=50, start="ORDER_RECEIVED", goal="DELIVERED")
3. Persist:
       store.save(session)
4. Later: load & apply:
       session = store.load("logistics")
       session.set_mode(DomainMode.APPLY)
       result  = session.recommend("ORDER_RECEIVED", ["PICKING", "BACKORDER"])

FileSensor is the E2-boundary read layer (C305).
E0Controller + HistorizedQuantumWalk are the navigation layer.
DomainStore is the persistence layer.
"""

from __future__ import annotations

import datetime
import json
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .controller import E0Controller
from .file_sensor import FileSensor, InjectionReport, parse_outcome_str
from .landscape import Landscape
from .primitives import Edge, Outcome
from .quantum_walk_historized import HistorizedQuantumWalk, conviction


# ──────────────────────────────────────────────────────────────────────────────
# 1. Constants
# ──────────────────────────────────────────────────────────────────────────────

_DEFAULT_DELTA: float = 1.0
_DEFAULT_RESISTANCE: float = 0.3
_MIN_INSCRIPTIONS: int = 5   # below this → cold-start in recommend()
_STORE_DIR: str = os.path.join("memos", "domains")


# ──────────────────────────────────────────────────────────────────────────────
# 2. Enums & Return Types
# ──────────────────────────────────────────────────────────────────────────────

class DomainMode(Enum):
    LEARN = "learn"
    APPLY = "apply"
    HYBRID = "hybrid"


@dataclass
class LearnReport:
    """Summary of a learning run (one call to DomainSession.learn())."""
    episodes: int = 0
    total_steps: int = 0
    success_count: int = 0
    failure_count: int = 0
    partial_count: int = 0
    edges_explored: int = 0
    warnings: List[str] = field(default_factory=list)

    @property
    def goal_rate(self) -> float:
        """Fraction of episodes that reached the goal (total_steps > 0 heuristic)."""
        return self.success_count / max(self.episodes, 1)

    def __repr__(self) -> str:
        return (
            f"LearnReport(episodes={self.episodes}, steps={self.total_steps}, "
            f"S={self.success_count}, F={self.failure_count}, "
            f"edges_explored={self.edges_explored})"
        )


@dataclass
class RecommendResult:
    """Result of DomainSession.recommend()."""
    recommended: Optional[str]
    reason: str
    quality: float
    conviction_score: float
    candidates: List[str] = field(default_factory=list)

    @property
    def cold_start(self) -> bool:
        return self.recommended is None


# ──────────────────────────────────────────────────────────────────────────────
# 3. Landscape codec (self-contained, no external private dependencies)
# ──────────────────────────────────────────────────────────────────────────────

def _landscape_to_dict(ls: Landscape) -> dict:
    """Minimal serialization: topology + U/F/tau Historization traces."""
    edges_data = []
    for e in ls.edges:
        edges_data.append({
            "source": e.source,
            "target": e.target,
            "delta": ls._delta.get(e, _DEFAULT_DELTA),
            "resistance": ls._R0.get(e, _DEFAULT_RESISTANCE),
        })
    h = ls.historization
    return {
        "edges": edges_data,
        "hist": {
            "U": {f"{e.source}\u2192{e.target}": v for e, v in h._U.items()},
            "F": {f"{e.source}\u2192{e.target}": v for e, v in h._F.items()},
            "tau": h._tau,
            "tau_last": {
                f"{e.source}\u2192{e.target}": t for e, t in h._tau_last.items()
            },
        },
    }


def _landscape_from_dict(data: dict) -> Landscape:
    """Restore Landscape from the dict produced by _landscape_to_dict."""
    ls = Landscape()
    for e in data.get("edges", []):
        ls.add_edge(
            e["source"], e["target"],
            delta=e.get("delta", _DEFAULT_DELTA),
            resistance=e.get("resistance", _DEFAULT_RESISTANCE),
        )
    h = ls.historization
    hist = data.get("hist", {})
    for key, v in hist.get("U", {}).items():
        parts = key.split("\u2192", 1)
        if len(parts) == 2:
            h._U[Edge(parts[0], parts[1])] = float(v)
    for key, v in hist.get("F", {}).items():
        parts = key.split("\u2192", 1)
        if len(parts) == 2:
            h._F[Edge(parts[0], parts[1])] = float(v)
    h._tau = hist.get("tau", 0)
    for key, t in hist.get("tau_last", {}).items():
        parts = key.split("\u2192", 1)
        if len(parts) == 2:
            h._tau_last[Edge(parts[0], parts[1])] = int(t)
    return ls


# ──────────────────────────────────────────────────────────────────────────────
# 4. DomainSession
# ──────────────────────────────────────────────────────────────────────────────

class DomainSession:
    """
    A named, stateful E₀ workspace for one domain.

    Owns:
        - landscape        — the E₀ Landscape (topology + Historization)
        - mode             — LEARN / APPLY / HYBRID
        - _sensor          — FileSensor (delegates inject calls)
        - _episode_count   — number of learn() episodes run in total

    Thread safety: not thread-safe. Each session is single-user.
    """

    def __init__(
        self,
        name: str,
        description: str = "",
        topic: str = "",
        landscape: Optional[Landscape] = None,
        mode: DomainMode = DomainMode.LEARN,
        created_at: Optional[str] = None,
        episode_count: int = 0,
    ) -> None:
        self.name = name
        self.description = description
        self.topic = topic
        self.landscape = landscape if landscape is not None else Landscape()
        self.mode = mode
        self._sensor = FileSensor(self.landscape)
        self._episode_count = episode_count
        self._created_at = (
            created_at
            or datetime.datetime.now(datetime.timezone.utc).isoformat()
        )

    # ── File injection ─────────────────────────────────────────────────────

    def inject(
        self,
        content: Any,
        hint: Optional[str] = None,
        call_fn: Optional[Callable[..., Any]] = None,
    ) -> InjectionReport:
        """
        Inject file content into the Landscape via FileSensor.

        hint: "csv" | "json" | "text" | None (auto-detect)
        call_fn: LLM callable — required only for text format
        """
        return self._sensor.inject(content, hint=hint, call_fn=call_fn)

    # ── Learning phase ─────────────────────────────────────────────────────

    def learn(
        self,
        oracle_fn: Callable[[str, str], Outcome],
        n_episodes: int = 10,
        start: Optional[str] = None,
        goal: Optional[str] = None,
        max_steps: int = 50,
        coin_mode: str = "geometric",
        mu: float = 5.0,
    ) -> LearnReport:
        """
        Run N episodes of HistorizedQuantumWalk on the current Landscape.

        oracle_fn(source, target) → Outcome
            — the ground-truth signal (simulation, historical data rule, etc.)

        start: initial state for each episode. If None, uses the first state
               (alphabetically) in the landscape.
        goal:  terminal state. If None, each episode runs exactly max_steps.

        Returns LearnReport with episode counts and edge coverage.
        """
        report = LearnReport()

        edges = list(self.landscape.edges)
        if not edges:
            report.warnings.append(
                "Landscape has no edges — inject topology first."
            )
            return report

        states = sorted(self.landscape.states)
        if not states:
            report.warnings.append("Landscape has no states.")
            return report

        start_state = start if start is not None else states[0]
        if start_state not in self.landscape.states:
            report.warnings.append(
                f"Start state '{start_state}' not in landscape. "
                f"Using '{states[0]}' instead."
            )
            start_state = states[0]

        edges_seen: set = set()

        for _ in range(n_episodes):
            walk = HistorizedQuantumWalk(
                landscape=self.landscape,
                initial_state=start_state,
                coin_mode=coin_mode,
                mu=mu,
            )
            episode_results = walk.run_with_outcomes(
                oracle_fn, goal=goal, max_steps=max_steps
            )
            report.episodes += 1
            self._episode_count += 1

            for step, outcome in episode_results:
                report.total_steps += 1
                if outcome == Outcome.SUCCESS:
                    report.success_count += 1
                elif outcome == Outcome.FAILURE:
                    report.failure_count += 1
                else:
                    report.partial_count += 1
                if not step.escalated:
                    edges_seen.add((step.state_before, step.state_after))

        report.edges_explored = len(edges_seen)
        return report

    # ── Application phase ──────────────────────────────────────────────────

    def recommend(
        self,
        state: str,
        candidates: List[str],
    ) -> RecommendResult:
        """
        Ask E₀ which candidate to navigate to from the current state.

        Cold-start (< _MIN_INSCRIPTIONS total) → returns recommended=None.
        Candidate edges are auto-created if absent.

        Returns RecommendResult.
        """
        if not candidates:
            return RecommendResult(
                recommended=None,
                reason="no candidates provided",
                quality=0.0,
                conviction_score=0.0,
                candidates=[],
            )

        # Auto-create missing edges
        for tgt in candidates:
            self._sensor._ensure_edge(state, tgt)

        total_inscriptions = self._sensor.landscape_summary()
        if self._inscription_events() < _MIN_INSCRIPTIONS:
            return RecommendResult(
                recommended=None,
                reason=f"cold start ({self._inscription_events()}/{_MIN_INSCRIPTIONS} inscriptions)",
                quality=0.0,
                conviction_score=0.0,
                candidates=candidates,
            )

        ctrl = E0Controller(self.landscape, _null_execute)
        chosen, escalated, esc_type = ctrl.select_next(state)

        if chosen is None or chosen not in candidates:
            chosen = max(
                candidates,
                key=lambda t: self.landscape.historization.trace_quality(
                    Edge(state, t)
                ),
            )
            reason = "quality fallback (controller chose outside candidate set)"
        elif escalated:
            reason = f"escalated ({esc_type.name if esc_type else 'unknown'})"
        else:
            reason = "structural selection"

        edge = Edge(state, chosen)
        q = self.landscape.historization.trace_quality(edge)
        c = conviction(self.landscape, edge)

        return RecommendResult(
            recommended=chosen,
            reason=reason,
            quality=round(q, 4),
            conviction_score=round(c, 4),
            candidates=candidates,
        )

    def record(
        self,
        source: str,
        target: str,
        outcome_str: str,
    ) -> bool:
        """
        Manually record a transition outcome (online learning / correction).

        outcome_str: "success" | "failure" | "partial"
        Returns True on success, False if outcome_str is unrecognised.
        """
        outcome = parse_outcome_str(outcome_str)
        if outcome is None:
            return False
        self._sensor._ensure_edge(source, target)
        self.landscape.historization.update(Edge(source, target), outcome)
        return True

    # ── Mode control ───────────────────────────────────────────────────────

    def set_mode(self, mode: DomainMode) -> None:
        """Switch the operating mode."""
        self.mode = mode

    # ── Introspection ──────────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        """Summary of current domain state."""
        summary = self._sensor.landscape_summary()
        total_insc = summary["total_inscriptions"]
        cold = self._inscription_events() < _MIN_INSCRIPTIONS

        return {
            "name": self.name,
            "description": self.description,
            "topic": self.topic,
            "mode": self.mode.value,
            "episode_count": self._episode_count,
            "states": summary["states"],
            "edges": summary["edges"],
            "total_inscriptions": round(total_insc, 4),
            "cold_start": cold,
            "created_at": self._created_at,
        }

    def conviction_map(self) -> Dict[str, float]:
        """
        Conviction score for every edge in the Landscape.

        conviction(e) = (m/(m+μ)) * |q(e)|  in [0, 1)
        Virgin/conflicted edges → near 0 (full quantum).
        Confirmed edges → approaches 1 (classical).
        """
        result: Dict[str, float] = {}
        for edge in self.landscape.edges:
            key = f"{edge.source}\u2192{edge.target}"
            result[key] = round(conviction(self.landscape, edge), 4)
        return result

    # ── Internal helpers ───────────────────────────────────────────────────

    def _inscription_events(self) -> int:
        """Total update() calls (historization._tau) — not rho-decayed."""
        return self.landscape.historization._tau

    def _total_inscriptions(self) -> float:
        """Sum of all U+F traces across the Landscape (float, rho-decayed)."""
        h = self.landscape.historization
        return sum(
            h._U.get(e, 0.0) + h._F.get(e, 0.0)
            for e in self.landscape.edges
        )


# ──────────────────────────────────────────────────────────────────────────────
# 5. DomainStore
# ──────────────────────────────────────────────────────────────────────────────

class DomainStore:
    """
    Filesystem persistence for DomainSessions.

    Storage: {store_dir}/{name}.json
    Default store_dir: memos/domains/ (relative to CWD)

    Format (domain_store_v1):
        {
            "_schema": "domain_store_v1",
            "meta": { name, description, topic, mode, created_at,
                      episode_count },
            "landscape": { edges: [...], hist: {U, F, tau, tau_last} }
        }
    """

    SCHEMA = "domain_store_v1"

    def __init__(self, store_dir: Optional[str] = None) -> None:
        self._dir = Path(store_dir or _STORE_DIR)

    def _path(self, name: str) -> Path:
        return self._dir / f"{name}.json"

    # ── Save ──────────────────────────────────────────────────────────────

    def save(self, session: DomainSession) -> Path:
        """
        Persist a DomainSession to disk.

        Creates the store directory if it doesn't exist.
        Returns the path written.
        """
        self._dir.mkdir(parents=True, exist_ok=True)
        data = {
            "_schema": self.SCHEMA,
            "meta": {
                "name": session.name,
                "description": session.description,
                "topic": session.topic,
                "mode": session.mode.value,
                "created_at": session._created_at,
                "episode_count": session._episode_count,
            },
            "landscape": _landscape_to_dict(session.landscape),
        }
        path = self._path(session.name)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return path

    # ── Load ──────────────────────────────────────────────────────────────

    def load(self, name: str) -> Optional[DomainSession]:
        """
        Restore a DomainSession by name.

        Returns None if the domain does not exist or the file is corrupt.
        """
        path = self._path(name)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

        meta = data.get("meta", {})
        landscape = _landscape_from_dict(data.get("landscape", {}))

        mode_str = meta.get("mode", "learn")
        try:
            mode = DomainMode(mode_str)
        except ValueError:
            mode = DomainMode.LEARN

        return DomainSession(
            name=meta.get("name", name),
            description=meta.get("description", ""),
            topic=meta.get("topic", ""),
            landscape=landscape,
            mode=mode,
            created_at=meta.get("created_at"),
            episode_count=meta.get("episode_count", 0),
        )

    # ── List & Delete ─────────────────────────────────────────────────────

    def list_domains(self) -> List[str]:
        """Return a sorted list of domain names currently stored."""
        if not self._dir.exists():
            return []
        return sorted(
            p.stem for p in self._dir.iterdir()
            if p.suffix == ".json"
        )

    def delete(self, name: str) -> bool:
        """
        Delete a domain by name.

        Returns True if deleted, False if not found.
        """
        path = self._path(name)
        if path.exists():
            path.unlink()
            return True
        return False

    def exists(self, name: str) -> bool:
        """True if a domain with this name is stored."""
        return self._path(name).exists()


# ──────────────────────────────────────────────────────────────────────────────
# 6. Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _null_execute(source: str, target: str) -> Outcome:
    """Dummy execute_fn for single-step selection (no actual execution)."""
    return Outcome.SUCCESS
