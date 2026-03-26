"""
E₀ MemOS v0.1 — Persistent Runtime Substrate
==============================================
Persistence and retrieval layer between the E₀ controller stack
and the LLM-facing semantic interface.

MemOS is NOT the controller. NOT the canon. NOT the LLM.
It is the substrate that keeps these layers coherent across runs.

Core responsibilities:
    1. Persist  — save E₀ runtime state to disk
    2. Restore  — reconstruct controller context from persisted data
    3. Summarize — produce bounded, token-efficient state packages for LLM
    4. Retrieve  — return structurally relevant prior traces and histories

See E0_MEMOS_v0.1.md for architecture reference.
"""

from __future__ import annotations

import json
import hashlib
import math
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .primitives import Edge, Outcome
from .historization import Historization
from .landscape import Landscape
from .controller import E0Controller, EscalationType, HybridMode, RunTrace
from .tension import coherence


# ──────────────────────────────────────────────
# Edge key convention (K-MemOS-1)
# ──────────────────────────────────────────────

def edge_to_key(edge: Edge) -> str:
    """Canonical string key for an Edge: 'source→target'."""
    return f"{edge.source}→{edge.target}"


def key_to_edge(key: str) -> Edge:
    """Parse 'source→target' back to an Edge."""
    parts = key.split("→")
    if len(parts) != 2:
        raise ValueError(f"Invalid edge key: {key!r}")
    return Edge(parts[0], parts[1])


# ──────────────────────────────────────────────
# Snapshot Dataclasses
# ──────────────────────────────────────────────

@dataclass
class CanonRef:
    """Reference to a canonical text."""
    name: str
    version: str
    path: str
    sha: Optional[str] = None


@dataclass
class LandscapeSnapshot:
    """Serializable capture of a Landscape."""
    states: List[str]
    edges: List[Dict[str, Any]]  # [{source, target, delta, r0}, ...]
    curvature_modulation: bool = False

    @staticmethod
    def from_landscape(L: Landscape) -> LandscapeSnapshot:
        states = sorted(L.states)
        edges = []
        for e in L.edges:
            delta = L.difference(e.source, e.target)
            r0 = L.base_resistance(e.source, e.target)
            edges.append({
                "source": e.source,
                "target": e.target,
                "delta": delta,
                "r0": r0,
            })
        return LandscapeSnapshot(
            states=states, edges=edges,
            curvature_modulation=L.curvature_modulation,
        )

    def to_landscape(self, historization: Optional[Historization] = None) -> Landscape:
        """Reconstruct a Landscape from this snapshot."""
        L = Landscape()
        L.curvature_modulation = self.curvature_modulation
        if historization is not None:
            L.historization = historization
        for s in self.states:
            L.add_state(s)
        for e in self.edges:
            L.add_edge(e["source"], e["target"],
                       delta=e["delta"], resistance=e["r0"])
        return L


@dataclass
class HistorizationSnapshot:
    """Serializable capture of Historization state."""
    tau: int
    rho: float
    lambda_s: float
    lambda_f: float
    delta_max: float
    success_traces: Dict[str, float]   # edge_key → U value
    failure_traces: Dict[str, float]   # edge_key → F value
    tau_last: Dict[str, int] = field(default_factory=dict)  # K2: edge_key → last-update time

    @staticmethod
    def from_historization(H: Historization) -> HistorizationSnapshot:
        snap = H.to_snapshot_dict()
        u_traces = {edge_to_key(e): v for e, v in snap["U"].items()}
        f_traces = {edge_to_key(e): v for e, v in snap["F"].items()}
        tau_last = {edge_to_key(e): v for e, v in snap.get("tau_last", {}).items()}
        return HistorizationSnapshot(
            tau=snap["tau"],
            rho=snap["rho"],
            lambda_s=snap["lambda_s"],
            lambda_f=snap["lambda_f"],
            delta_max=snap["delta_max"],
            success_traces=u_traces,
            failure_traces=f_traces,
            tau_last=tau_last,
        )

    def to_historization(self) -> Historization:
        """Reconstruct a Historization from this snapshot."""
        d = {
            "tau": self.tau,
            "rho": self.rho,
            "lambda_s": self.lambda_s,
            "lambda_f": self.lambda_f,
            "delta_max": self.delta_max,
            "U": {k: v for k, v in self.success_traces.items()},
            "F": {k: v for k, v in self.failure_traces.items()},
            "tau_last": {k: v for k, v in self.tau_last.items()},
        }
        return Historization.from_snapshot_dict(d, key_to_edge)


@dataclass
class RuntimeSnapshot:
    """Serializable capture of E0Controller runtime state (K-MemOS-2)."""
    recent_states: List[str]
    escalation_edges: List[Dict[str, Any]]  # [{source, target, delta, r0}]
    last_escalation_type: str               # K-MemOS-2: EscalationType value
    metrics: Dict[str, float]
    controller_params: Dict[str, float]     # alpha, recent_k, s_max, c_min, ...

    @staticmethod
    def from_controller(ctrl: E0Controller,
                        trace: Optional[RunTrace] = None) -> RuntimeSnapshot:
        esc_edges = []
        for e, (delta, r0, *rest) in ctrl._escalation_edges.items():
            esc_edges.append({
                "source": e.source, "target": e.target,
                "delta": delta, "r0": r0,
                "created_by": rest[0] if rest else "unknown",
            })

        # K-MemOS-2: last escalation type from trace
        last_esc = EscalationType.NONE.value
        if trace and trace.steps:
            for step in reversed(trace.steps):
                if step.escalated:
                    last_esc = step.escalation_type.value
                    break

        metrics = trace.metrics() if trace else {}

        return RuntimeSnapshot(
            recent_states=list(ctrl._recent),
            escalation_edges=esc_edges,
            last_escalation_type=last_esc,
            metrics=metrics,
            controller_params={
                "alpha": ctrl.alpha,
                "recent_k": ctrl.recent_k,
                "max_escalation_R": ctrl.max_escalation_R,
                "s_max": ctrl.s_max if not math.isinf(ctrl.s_max) else -1.0,
                "c_min": ctrl.c_min,
                "hybrid_mode": ctrl.hybrid_mode.value,
                "hybrid_horizon": ctrl.hybrid_horizon,
                "hybrid_goals": sorted(ctrl.hybrid_goals) if ctrl.hybrid_goals else [],
                "hybrid_geometry": ctrl.hybrid_geometry,
                "confidence_threshold": ctrl.confidence_threshold,
                "use_su2": bool(ctrl.use_su2),
            },
        )


@dataclass
class RunRecord:
    """Serializable summary of one completed run."""
    run_id: str
    timestamp: str
    start_state: str
    final_state: str
    steps: int
    reached_goal: bool
    metrics: Dict[str, float]
    path: List[str]
    escalation_types: Dict[str, int]  # K-MemOS-2: breakdown by type


@dataclass
class MemOSContext:
    """Complete persisted E₀ state for a session."""
    session_id: str
    created: str
    updated: str
    canon_refs: List[Dict[str, Any]]
    landscape: Dict[str, Any]
    historization: Dict[str, Any]
    runtime: Dict[str, Any]
    runs: List[Dict[str, Any]] = field(default_factory=list)
    notes: Dict[str, Any] = field(default_factory=dict)


# ──────────────────────────────────────────────
# E0MemoryOS — Core Class
# ──────────────────────────────────────────────

class E0MemoryOS:
    """
    Persistent runtime substrate for the E₀ controller stack.

    Manages session state on disk as JSON files.
    Provides bounded summaries for LLM integration.
    """

    def __init__(self, base_dir: str = "memos"):
        self.base_dir = Path(base_dir)
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """Create directory structure if needed."""
        for sub in ["canon", "sessions", "runs", "indices"]:
            (self.base_dir / sub).mkdir(parents=True, exist_ok=True)

    def _session_path(self, session_id: str) -> Path:
        return self.base_dir / "sessions" / f"{session_id}.json"

    def _runs_dir(self, session_id: str) -> Path:
        d = self.base_dir / "runs" / session_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ── 6.1 Persist ──

    def snapshot_from_runtime(
        self,
        session_id: str,
        landscape: Landscape,
        controller: E0Controller,
        trace: Optional[RunTrace] = None,
        canon_refs: Optional[List[CanonRef]] = None,
    ) -> MemOSContext:
        """Capture live runtime objects into a serializable context."""
        now = datetime.now(timezone.utc).isoformat()

        ls = LandscapeSnapshot.from_landscape(landscape)
        hs = HistorizationSnapshot.from_historization(landscape.historization)
        rs = RuntimeSnapshot.from_controller(controller, trace)

        cr = [{"name": c.name, "version": c.version,
               "path": c.path, "sha": c.sha}
              for c in (canon_refs or [])]

        return MemOSContext(
            session_id=session_id,
            created=now,
            updated=now,
            canon_refs=cr,
            landscape=asdict(ls),
            historization=asdict(hs),
            runtime=asdict(rs),
        )

    def save_context(self, context: MemOSContext) -> Path:
        """Persist a MemOSContext to disk as JSON."""
        context.updated = datetime.now(timezone.utc).isoformat()
        path = self._session_path(context.session_id)
        data = asdict(context)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                        encoding="utf-8")
        return path

    def load_context(self, session_id: str) -> MemOSContext:
        """Load a persisted MemOSContext from disk."""
        path = self._session_path(session_id)
        if not path.exists():
            raise FileNotFoundError(f"No session found: {session_id}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return MemOSContext(**data)

    def save_run(self, session_id: str, trace: RunTrace,
                 goal: Optional[str] = None) -> RunRecord:
        """Save a completed run trace as a run record."""
        runs_dir = self._runs_dir(session_id)
        existing = sorted(runs_dir.glob("run_*.json"))
        run_num = len(existing) + 1
        run_id = f"run_{run_num:04d}"

        path_states = trace.path
        final = path_states[-1] if path_states else ""
        start = path_states[0] if path_states else ""

        # K-MemOS-2: escalation type breakdown
        esc_counts: Dict[str, int] = {}
        for step in trace.steps:
            if step.escalated:
                t = step.escalation_type.value
                esc_counts[t] = esc_counts.get(t, 0) + 1

        record = RunRecord(
            run_id=run_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            start_state=start,
            final_state=final,
            steps=len(trace.steps),
            reached_goal=(goal is not None and final == goal),
            metrics=trace.metrics(),
            path=path_states,
            escalation_types=esc_counts,
        )

        run_path = runs_dir / f"{run_id}.json"
        run_path.write_text(
            json.dumps(asdict(record), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return record

    # ── 6.2 Restore ──

    def restore_landscape(self, context: MemOSContext) -> Landscape:
        """Reconstruct a Landscape + Historization from a persisted context."""
        hs = HistorizationSnapshot(**context.historization)
        H = hs.to_historization()
        ls = LandscapeSnapshot(**context.landscape)
        return ls.to_landscape(historization=H)

    def restore_controller(
        self,
        context: MemOSContext,
        landscape: Landscape,
        execute_fn,
    ) -> E0Controller:
        """Reconstruct an E0Controller with persisted runtime state."""
        params = context.runtime.get("controller_params", {})
        s_max_raw = params.get("s_max", -1.0)
        s_max = math.inf if s_max_raw == -1.0 else s_max_raw

        # Hybrid mode params (3l)
        hybrid_mode_str = params.get("hybrid_mode", "greedy")
        try:
            hybrid_mode = HybridMode(hybrid_mode_str)
        except ValueError:
            hybrid_mode = HybridMode.GREEDY
        hybrid_goals_raw = params.get("hybrid_goals", [])
        hybrid_goals = set(hybrid_goals_raw) if hybrid_goals_raw else None

        ctrl = E0Controller(
            landscape=landscape,
            execute_fn=execute_fn,
            alpha=params.get("alpha", 2.0),
            recent_k=int(params.get("recent_k", 3)),
            max_escalation_R=params.get("max_escalation_R", 5.0),
            s_max=s_max,
            c_min=params.get("c_min", 0.0),
            hybrid_mode=hybrid_mode,
            hybrid_horizon=int(params.get("hybrid_horizon", 3)),
            hybrid_goals=hybrid_goals,
            hybrid_geometry=params.get("hybrid_geometry", "simple"),
            confidence_threshold=params.get("confidence_threshold", 0.0),
            use_su2=params.get("use_su2", False),
        )

        # Restore mutable runtime state
        ctrl._recent = list(context.runtime.get("recent_states", []))

        for ee in context.runtime.get("escalation_edges", []):
            edge = Edge(ee["source"], ee["target"])
            ctrl._escalation_edges[edge] = (
                ee["delta"], ee["r0"],
                ee.get("created_by", "unknown"),
            )

        return ctrl

    # ── 6.3 Summarize (K-MemOS-4) ──

    def summarize_for_llm(
        self,
        context: MemOSContext,
        current_state: str,
        landscape: Optional[Landscape] = None,
        controller: Optional[E0Controller] = None,
    ) -> Dict[str, Any]:
        """
        Produce a bounded, token-efficient state package for the LLM.

        Priority order (K-MemOS-4):
            1. Current state + admissible neighbors
            2. Edge historization for current neighborhood
            3. Recent path / runtime context
            4. Canon references
            5. Amplitude overlay (3m) — if controller in hybrid mode or provided
        """
        # Reconstruct landscape if not provided
        if landscape is None:
            landscape = self.restore_landscape(context)

        # 1. Admissible neighbors with tension info
        neighbors = landscape.admissible_neighbors(current_state)
        neighbor_info = {}
        for n in neighbors:
            s_eff = landscape.effective_tension(current_state, n)
            edge = Edge(current_state, n)
            info = {
                "s_eff": round(s_eff, 4),
                "coherence": round(coherence(s_eff), 4),
                "v": round(landscape.transition_field(current_state, n), 4),
            }
            if landscape.curvature_modulation:
                info["M_H"] = round(landscape._get_M_H(current_state, n), 4)
            neighbor_info[n] = info

        # 2. Edge history for current neighborhood
        edge_history = {}
        for n in neighbors:
            edge = Edge(current_state, n)
            ek = edge_to_key(edge)
            u = context.historization["success_traces"].get(ek, 0.0)
            f = context.historization["failure_traces"].get(ek, 0.0)
            edge_history[ek] = {
                "U": round(u, 4),
                "F": round(f, 4),
                "delta_H": round(landscape.historization.delta_H(edge), 4),
            }

        # 3. Runtime context
        params = context.runtime.get("controller_params", {})
        hybrid_mode = params.get("hybrid_mode", "greedy")
        runtime = {
            "recent_states": context.runtime.get("recent_states", []),
            "escalation_type": context.runtime.get("last_escalation_type", "none"),
            "tau": context.historization.get("tau", 0),
            "hybrid_mode": hybrid_mode,
        }

        # Curvature modulation (B2)
        if landscape.curvature_modulation:
            runtime["curvature_modulation"] = True

        # SU(2) spinor interference (Paper 2 / B1)
        if params.get("use_su2"):
            runtime["use_su2"] = True

        # 4. Canon refs
        canon = [ref["name"] + "@" + ref["version"]
                 for ref in context.canon_refs]

        result: Dict[str, Any] = {
            "canon_refs": canon,
            "current_state": current_state,
            "admissible_neighbors": neighbor_info,
            "edge_history": edge_history,
            "runtime": runtime,
        }

        # 5. Amplitude overlay (3m)
        if controller is not None and neighbors:
            overlay_info = self._build_overlay_summary(
                controller, current_state,
            )
            if overlay_info:
                result["amplitude_overlay"] = overlay_info

        return result

    def _build_overlay_summary(
        self,
        controller: E0Controller,
        current_state: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Compute amplitude overlay and produce a bounded LLM-friendly summary.

        Returns None if overlay computation is not possible (e.g., no neighbors).
        """
        from .amplitude_overlay import analyze_controller_state

        try:
            report = analyze_controller_state(
                controller, current_state,
                horizon_edges=controller.hybrid_horizon,
                geometry=controller.hybrid_geometry,
                goals=controller.hybrid_goals,
            )
        except (ValueError, KeyError):
            return None

        if not report.action_infos:
            return None

        actions = {}
        for info in report.action_infos:
            entry: Dict[str, Any] = {
                "probability": round(info.probability, 4),
                "intensity": round(info.intensity, 6),
                "path_count": info.path_count,
            }
            if info.path_count > 1 and abs(info.psi_total) > 1e-15:
                import cmath
                entry["psi_phase"] = round(cmath.phase(info.psi_total), 4)
            actions[info.action] = entry

        greedy_choice = report.deterministic_choice
        amp_choice = report.amplitude_choice
        agree = (greedy_choice == amp_choice)

        return {
            "geometry": report.geometry,
            "horizon": report.horizon_edges,
            "greedy_choice": greedy_choice,
            "amplitude_choice": amp_choice,
            "agree": agree,
            "override_confidence": round(report.override_confidence, 4),
            "actions": actions,
        }

    # ── 6.4 Retrieve ──

    def retrieve_recent_runs(self, session_id: str,
                             limit: int = 5) -> List[Dict[str, Any]]:
        """Return the most recent run records for a session."""
        runs_dir = self.base_dir / "runs" / session_id
        if not runs_dir.exists():
            return []
        files = sorted(runs_dir.glob("run_*.json"), reverse=True)
        results = []
        for f in files[:limit]:
            data = json.loads(f.read_text(encoding="utf-8"))
            results.append(data)
        return results

    def retrieve_edge_history(
        self,
        session_id: str,
        edge_key: str,
    ) -> Dict[str, Any]:
        """
        Return historization data for a specific edge across runs.

        Args:
            session_id: Session to query.
            edge_key: Edge in canonical form "source→target".

        Retrieval priority (§9 of MemOS spec):
            1. Current session historization
            2. Appearances in recent runs
        """
        edge = key_to_edge(edge_key)
        source, target = edge.source, edge.target
        result: Dict[str, Any] = {"edge": edge_key, "runs": []}

        # Current session data
        try:
            ctx = self.load_context(session_id)
            u = ctx.historization["success_traces"].get(edge_key, 0.0)
            f = ctx.historization["failure_traces"].get(edge_key, 0.0)
            result["current"] = {"U": u, "F": f, "tau": ctx.historization["tau"]}
        except FileNotFoundError:
            result["current"] = None

        # Scan recent runs for this edge
        runs = self.retrieve_recent_runs(session_id, limit=10)
        for run in runs:
            path = run.get("path", [])
            # Check if this edge appears in the run's path
            for i in range(len(path) - 1):
                if path[i] == source and path[i + 1] == target:
                    result["runs"].append({
                        "run_id": run["run_id"],
                        "timestamp": run["timestamp"],
                        "step_index": i,
                    })
                    break

        return result

    # ── Utility ──

    def session_exists(self, session_id: str) -> bool:
        return self._session_path(session_id).exists()

    def list_sessions(self) -> List[str]:
        """List all saved session IDs."""
        sessions_dir = self.base_dir / "sessions"
        return [f.stem for f in sorted(sessions_dir.glob("*.json"))]

    def compare_runs(
        self,
        session_id_a: str,
        session_id_b: str,
        limit: int = 1,
    ) -> Dict[str, Any]:
        """
        Compare the most recent runs from two sessions.

        Useful for Mock vs. Live comparison or cross-domain analysis.

        Returns dict with:
            a, b:       individual run summaries
            comparison: structural metrics delta
        """
        runs_a = self.retrieve_recent_runs(session_id_a, limit=limit)
        runs_b = self.retrieve_recent_runs(session_id_b, limit=limit)

        def _summarize(runs: List[Dict]) -> Dict[str, Any]:
            if not runs:
                return {"steps": 0, "path": [], "outcomes": {}}
            r = runs[0]  # most recent
            return {
                "run_id": r.get("run_id", "?"),
                "steps": r.get("steps", 0),
                "path": r.get("path", []),
                "outcomes": r.get("outcomes", {}),
                "total_tension": r.get("total_tension", 0.0),
                "metrics": r.get("metrics", {}),
            }

        sa = _summarize(runs_a)
        sb = _summarize(runs_b)

        # Structural comparison
        path_match = sa["path"] == sb["path"]
        step_diff = sa["steps"] - sb["steps"]
        tension_diff = sa.get("total_tension", 0) - sb.get("total_tension", 0)
        overlap = set(sa["path"]) & set(sb["path"])
        union = set(sa["path"]) | set(sb["path"])
        jaccard = len(overlap) / len(union) if union else 1.0

        return {
            "a": sa,
            "b": sb,
            "comparison": {
                "path_identical": path_match,
                "step_difference": step_diff,
                "tension_difference": round(tension_diff, 4),
                "path_jaccard": round(jaccard, 4),
                "shared_states": sorted(overlap),
            },
        }
