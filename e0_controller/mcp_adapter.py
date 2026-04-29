"""
E₀ MCP Adapter (C291)
======================
Exposes E₀ as an MCP tool server for OpenClaw and other MCP-compatible agents.

Design principle: Bottom-up.
  The Landscape starts empty. Edges are added on demand as OpenClaw reports
  step sequences. Structure emerges from observed outcomes, not from design.

Three tools:
  e0_observe(port, signal_id, outcome)
      Record the result of a tool-call step.
      outcome: "success" | "failure" | "partial"

  e0_recommend(state, candidates)
      Ask E₀ which next step to take given the current state and a list
      of candidate steps. Returns null on cold start (< MIN_INSCRIPTIONS).

  e0_status()
      Current landscape size, port quality, inscription count.

Architecture:
  _E0AdapterSession holds:
    - Landscape       (auto-grows from observe + recommend calls)
    - ObservationPort (historizes tool-call outcomes per signal_id)
    - E0Controller    (rebuilt from Landscape each call — stateless selector)

  Session is persisted to SESSION_PATH as JSON.

Usage as MCP server (requires `mcp` package):
    py -3 -m e0_controller.mcp_adapter

Usage in tests (no `mcp` needed):
    from e0_controller.mcp_adapter import E0AdapterSession
    session = E0AdapterSession()
    session.observe("search", "success")
    result = session.recommend("search_complete", ["browse", "synthesize"])
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .controller import E0Controller
from .landscape import Landscape
from .observation_port import ObservationPort
from .primitives import Edge, Outcome

# ── Constants ────────────────────────────────────────────────────────────────

SESSION_PATH: Path = Path(
    os.environ.get("E0_MCP_SESSION", Path.home() / ".e0_mcp" / "session.json")
)

# Below this inscription count, recommend() returns None (honest cold-start).
MIN_INSCRIPTIONS: int = 5

# Default edge parameters for auto-created edges (no prior knowledge).
_DEFAULT_DELTA: float = 0.5
_DEFAULT_RESISTANCE: float = 0.3

# ── Session ──────────────────────────────────────────────────────────────────


@dataclass
class RecommendResult:
    """Return type of E0AdapterSession.recommend()."""
    recommended: Optional[str]     # None = cold start, caller decides freely
    reason: str                    # Human-readable explanation
    quality: float                 # trace_quality of the recommended edge (-1..+1)
    inscriptions: int              # Total observations recorded so far


class E0AdapterSession:
    """
    Holds E₀ state for one OpenClaw integration session.

    Thread safety: not thread-safe. OpenClaw's MCP calls are sequential per
    session; if used concurrently, wrap in a lock.
    """

    def __init__(self) -> None:
        self._landscape: Landscape = Landscape()
        self._port: ObservationPort = ObservationPort(name="openclaw")
        self._inscription_count: int = 0

    # ── Core API (pure Python, no MCP dependency) ─────────────────────────

    def observe(
        self,
        signal_id: str,
        outcome_str: str,
    ) -> dict:
        """Record a tool-call outcome.

        Args:
            signal_id: Identifier for the step/tool (e.g. "search", "browse").
            outcome_str: "success", "failure", or "partial".

        Returns dict with acknowledgment and current port quality.
        """
        outcome = _parse_outcome(outcome_str)
        self._port.observe(signal_id, outcome)
        self._inscription_count += 1
        return {
            "ok": True,
            "signal_id": signal_id,
            "outcome": outcome.value,
            "port_quality": round(self._port.impact_quality(), 4),
            "inscriptions": self._inscription_count,
        }

    def observe_edge(
        self,
        source: str,
        target: str,
        outcome_str: str,
    ) -> dict:
        """Record an outcome for a directed step transition.

        This is the richer form of observe(): it records both the outcome
        in the ObservationPort AND inscribes the edge in the Landscape.
        Use this when you know the full (source → target) sequence.

        Args:
            source: State name before the step (e.g. "task_received").
            target: State name after the step (e.g. "search_complete").
            outcome_str: "success", "failure", or "partial".
        """
        outcome = _parse_outcome(outcome_str)
        self._ensure_edge(source, target)
        self._landscape.historization.update(Edge(source, target), outcome)
        self._port.observe(f"{source}→{target}", outcome)
        self._inscription_count += 1
        return {
            "ok": True,
            "edge": f"{source}→{target}",
            "outcome": outcome.value,
            "port_quality": round(self._port.impact_quality(), 4),
            "inscriptions": self._inscription_count,
        }

    def recommend(
        self,
        state: str,
        candidates: List[str],
    ) -> RecommendResult:
        """Ask E₀ which candidate to visit from the current state.

        On cold start (< MIN_INSCRIPTIONS) returns recommended=None — the
        caller should decide freely and later report the outcome via observe().

        Edges from state to each candidate are auto-created if not present.

        Args:
            state: Current node name.
            candidates: List of possible next nodes.

        Returns RecommendResult.
        """
        if not candidates:
            return RecommendResult(
                recommended=None,
                reason="no candidates provided",
                quality=0.0,
                inscriptions=self._inscription_count,
            )

        if self._inscription_count < MIN_INSCRIPTIONS:
            return RecommendResult(
                recommended=None,
                reason=f"cold start ({self._inscription_count}/{MIN_INSCRIPTIONS} inscriptions)",
                quality=0.0,
                inscriptions=self._inscription_count,
            )

        # Ensure all candidate edges exist in landscape
        for target in candidates:
            self._ensure_edge(state, target)

        ctrl = E0Controller(self._landscape, _null_execute)
        chosen, escalated, esc_type = ctrl.select_next(state)

        if chosen is None or chosen not in candidates:
            # Fallback: pick the candidate with best trace_quality
            chosen = max(
                candidates,
                key=lambda t: self._landscape.historization.trace_quality(
                    Edge(state, t)
                ),
            )
            reason = "greedy quality fallback (controller returned no candidate in set)"
        elif escalated:
            reason = f"escalated ({esc_type.name if esc_type else 'unknown'})"
        else:
            reason = "structural selection (lowest burden)"

        q = self._landscape.historization.trace_quality(Edge(state, chosen))
        return RecommendResult(
            recommended=chosen,
            reason=reason,
            quality=round(q, 4),
            inscriptions=self._inscription_count,
        )

    def status(self) -> dict:
        """Return current adapter state summary."""
        ls = self._landscape
        edges = list(ls.edges)
        return {
            "inscriptions": self._inscription_count,
            "landscape_nodes": len(ls.states),
            "landscape_edges": len(edges),
            "port_quality": round(self._port.impact_quality(), 4),
            "port_dampening": round(self._port.dampening_factor(), 4),
            "cold_start": self._inscription_count < MIN_INSCRIPTIONS,
        }

    # ── Persistence ───────────────────────────────────────────────────────

    def save(self, path: Path = SESSION_PATH) -> None:
        """Persist session state to JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "inscription_count": self._inscription_count,
            "port": self._port.to_dict(),
            "landscape": _landscape_to_dict(self._landscape),
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path = SESSION_PATH) -> "E0AdapterSession":
        """Restore session state from JSON. Returns fresh session if file absent."""
        session = cls()
        if not path.exists():
            return session
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return session
        session._inscription_count = data.get("inscription_count", 0)
        session._port = ObservationPort.from_dict(data.get("port"))
        session._landscape = _landscape_from_dict(data.get("landscape", {}))
        return session

    # ── Internal helpers ─────────────────────────────────────────────────

    def _ensure_edge(self, source: str, target: str) -> None:
        """Add edge to landscape if not already present."""
        existing = {(e.source, e.target) for e in self._landscape.edges}
        if (source, target) not in existing:
            self._landscape.add_edge(
                source, target,
                delta=_DEFAULT_DELTA,
                resistance=_DEFAULT_RESISTANCE,
            )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _null_execute(source: str, target: str) -> Outcome:
    """Dummy execute_fn for single-step selection (no actual execution)."""
    return Outcome.SUCCESS


def _parse_outcome(s: str) -> Outcome:
    mapping = {
        "success": Outcome.SUCCESS,
        "failure": Outcome.FAILURE,
        "partial": Outcome.PARTIAL,
    }
    return mapping.get(s.lower(), Outcome.FAILURE)


def _landscape_to_dict(ls: Landscape) -> dict:
    """Minimal serialization: edges with delta/resistance + historization traces."""
    edges_data = []
    for e in ls.edges:
        edges_data.append({
            "source": e.source,
            "target": e.target,
            "delta": ls._delta.get(e, _DEFAULT_DELTA),
            "resistance": ls._R0.get(e, _DEFAULT_RESISTANCE),
        })

    h = ls.historization
    u_data = {f"{e.source}→{e.target}": v for e, v in h._U.items()}
    f_data = {f"{e.source}→{e.target}": v for e, v in h._F.items()}
    tau_last = {f"{e.source}→{e.target}": t for e, t in h._tau_last.items()}

    return {
        "edges": edges_data,
        "hist": {
            "U": u_data,
            "F": f_data,
            "tau": h._tau,
            "tau_last": tau_last,
        },
    }


def _landscape_from_dict(data: dict) -> Landscape:
    """Restore Landscape from dict."""
    ls = Landscape()
    for e in data.get("edges", []):
        ls.add_edge(e["source"], e["target"],
                    delta=e.get("delta", _DEFAULT_DELTA),
                    resistance=e.get("resistance", _DEFAULT_RESISTANCE))

    h = ls.historization
    hist = data.get("hist", {})
    for key, v in hist.get("U", {}).items():
        parts = key.split("→", 1)
        if len(parts) == 2:
            h._U[Edge(parts[0], parts[1])] = float(v)
    for key, v in hist.get("F", {}).items():
        parts = key.split("→", 1)
        if len(parts) == 2:
            h._F[Edge(parts[0], parts[1])] = float(v)
    h._tau = hist.get("tau", 0)
    for key, t in hist.get("tau_last", {}).items():
        parts = key.split("→", 1)
        if len(parts) == 2:
            h._tau_last[Edge(parts[0], parts[1])] = int(t)
    return ls


# ── MCP server (optional — requires `mcp` package) ───────────────────────────

def run_mcp_server(session_path: Path = SESSION_PATH) -> None:
    """Start E₀ as an MCP server on stdio.

    Requires: pip install mcp
    Usage: py -3 -m e0_controller.mcp_adapter
    """
    try:
        from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ImportError(
            "mcp package not installed. Run: pip install mcp"
        ) from exc

    session = E0AdapterSession.load(session_path)
    mcp_server = FastMCP("E₀ Framework")

    @mcp_server.tool()
    def e0_observe(signal_id: str, outcome: str) -> dict:
        """Record the result of a tool-call step.

        Args:
            signal_id: Identifier for the step/tool (e.g. "search", "browse").
            outcome: "success", "failure", or "partial".
        """
        result = session.observe(signal_id, outcome)
        session.save(session_path)
        return result

    @mcp_server.tool()
    def e0_observe_edge(source: str, target: str, outcome: str) -> dict:
        """Record an outcome for a directed step transition (source → target).

        Richer form of e0_observe: inscribes both the ObservationPort and the
        Landscape edge. Use when you know the full transition sequence.

        Args:
            source: State before the step (e.g. "task_received").
            target: State after the step (e.g. "search_complete").
            outcome: "success", "failure", or "partial".
        """
        result = session.observe_edge(source, target, outcome)
        session.save(session_path)
        return result

    @mcp_server.tool()
    def e0_recommend(state: str, candidates: list[str]) -> dict:
        """Ask E₀ which next step to take.

        On cold start returns recommended=null — proceed freely and report
        outcomes via e0_observe_edge to build inscriptions.

        Args:
            state: Current node/state name.
            candidates: Possible next steps to choose from.
        """
        result = session.recommend(state, candidates)
        return {
            "recommended": result.recommended,
            "reason": result.reason,
            "quality": result.quality,
            "inscriptions": result.inscriptions,
        }

    @mcp_server.tool()
    def e0_status() -> dict:
        """Return current E₀ adapter state: inscription count, landscape size, port quality."""
        return session.status()

    mcp_server.run()


if __name__ == "__main__":
    run_mcp_server()
