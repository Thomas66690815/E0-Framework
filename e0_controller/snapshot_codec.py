"""SnapshotCodec — wire-format serialization for E₀ structures.

Provides JSON-safe encoding/decoding for Landscape, Historization,
StepResult, and strategy profiles. Used by API Gateway (Layer C)
and any consumer needing E₀ state over the wire.

Part of Layer B (Service Layer).  C83.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from e0_controller.primitives import Edge, Outcome
from e0_controller.controller import (
    EscalationType,
    HybridMode,
    StepResult,
    RunTrace,
)
from e0_controller.historization import Historization
from e0_controller.landscape import Landscape
from e0_controller.tension import coherence
from e0_controller.mode_controller import ModeController, OperatingMode


def _edge_key(edge: Edge) -> str:
    return f"{edge.source}→{edge.target}"


def _parse_edge(key: str) -> Edge:
    parts = key.split("→")
    if len(parts) != 2:
        raise ValueError(f"Invalid edge key: {key!r}")
    return Edge(parts[0], parts[1])


def _encode_historization_dict(hist: dict) -> dict:
    """Convert Edge-keyed dicts inside historization snapshot to string keys."""
    result = {}
    for k, v in hist.items():
        if k in ("U", "F", "tau_last") and isinstance(v, dict):
            result[k] = {
                _edge_key(e) if isinstance(e, tuple) else str(e): val
                for e, val in v.items()
            }
        else:
            result[k] = v
    return result


# ── Landscape ────────────────────────────────────────────

def encode_landscape(landscape: Landscape) -> dict:
    """Encode a Landscape to a JSON-safe dict."""
    edges = {}
    for e in landscape.edges:
        info = landscape.info(e.source, e.target)
        edges[_edge_key(e)] = {
            "source": e.source,
            "target": e.target,
            "delta": info["delta"],
            "R0": info["R0"],
            "R_eff": info["R_eff"],
            "delta_H": info["delta_H"],
            "S_eff": info["S_eff"],
            "coherence": info["coherence"],
            "v": info["v"],
            "U": info["U"],
            "F": info["F"],
            "trace_quality": landscape.historization.trace_quality(e),
            "trace_load": landscape.historization.trace_load(e),
        }
    return {
        "states": sorted(landscape.states),
        "edges": edges,
        "modulation": {
            "curvature": landscape.curvature_modulation,
            "overlap": landscape.overlap_modulation,
            "inertia": landscape.inertia_modulation,
        },
        "historization": _encode_historization_dict(
            landscape.historization.to_snapshot_dict()
        ),
        "summary": landscape.historization.summary(),
    }


def decode_landscape(data: dict) -> Landscape:
    """Reconstruct a Landscape from an encoded dict."""
    L = Landscape()
    L.curvature_modulation = data["modulation"]["curvature"]
    L.overlap_modulation = data["modulation"]["overlap"]
    L.inertia_modulation = data["modulation"]["inertia"]

    for s in data["states"]:
        L.add_state(s)

    for _key, edata in data["edges"].items():
        L.add_edge(
            edata["source"], edata["target"],
            delta=edata["delta"],
            resistance=edata["R0"],
        )

    # Restore historization from embedded snapshot
    hist_data = data["historization"]
    # Convert edge keys: they use Edge NamedTuples as keys in to_snapshot_dict
    # but we serialized them — need to handle both Edge objects and string keys
    L.historization = Historization.from_snapshot_dict(
        hist_data, _coerce_edge_key
    )
    return L


def _coerce_edge_key(key) -> Edge:
    """Parse edge key from snapshot — handles Edge tuples and string keys."""
    if isinstance(key, Edge):
        return key
    if isinstance(key, (list, tuple)) and len(key) == 2:
        return Edge(key[0], key[1])
    if isinstance(key, str) and "→" in key:
        return _parse_edge(key)
    raise ValueError(f"Cannot parse edge key: {key!r}")


# ── StepResult ───────────────────────────────────────────

def encode_step(step: StepResult) -> dict:
    """Encode a StepResult to a JSON-safe dict."""
    d: Dict[str, Any] = {
        "tau": step.tau,
        "source": step.source,
        "target": step.target,
        "outcome": step.outcome.value,
        "s_eff": step.s_eff,
        "r_eff_before": step.r_eff_before,
        "r_eff_after": step.r_eff_after,
        "candidates": step.candidates,
        "escalated": step.escalated,
        "escalation_type": step.escalation_type.value,
        "hybrid_overridden": step.hybrid_overridden,
        "override_confidence": step.override_confidence,
    }
    if step.overlay is not None:
        d["overlay"] = {
            "horizon": step.overlay.horizon,
            "action_infos": [
                {
                    "action": ai.action,
                    "probability": ai.probability,
                    "greedy_rank": ai.greedy_rank,
                }
                for ai in step.overlay.action_infos
            ],
        }
    return d


# ── RunTrace ─────────────────────────────────────────────

def encode_run_trace(trace: RunTrace) -> dict:
    """Encode a complete RunTrace to a JSON-safe dict."""
    return {
        "steps": [encode_step(s) for s in trace.steps],
        "path": trace.path,
        "total_tension": trace.total_tension,
        "outcomes": trace.outcomes,
        "metrics": trace.metrics(),
    }


# ── Strategy Profile ─────────────────────────────────────

def encode_strategy_profile(
    historization: Historization,
    edges: Optional[List[Edge]] = None,
    top_n: int = 0,
) -> List[dict]:
    """Encode strategy_profile() output to JSON-safe list."""
    profile = historization.strategy_profile(edges, top_n=top_n)
    return [
        {
            "edge": _edge_key(edge),
            "source": edge.source,
            "target": edge.target,
            "trace_quality": q,
            "trace_load": m,
        }
        for edge, q, m in profile
    ]


# ── Edge Info (for peer dialog) ──────────────────────────

def encode_edge_info(landscape: Landscape, source: str, targets: List[str]) -> Dict[str, dict]:
    """Encode edge info for a set of candidate targets from a given source."""
    result = {}
    for t in targets:
        info = landscape.info(source, t)
        edge = Edge(source, t)
        result[t] = {
            "delta": info["delta"],
            "S_eff": info["S_eff"],
            "R_eff": info["R_eff"],
            "delta_H": info["delta_H"],
            "coherence": info["coherence"],
            "trace_quality": landscape.historization.trace_quality(edge),
            "trace_load": landscape.historization.trace_load(edge),
            "U": info["U"],
            "F": info["F"],
        }
    return result
