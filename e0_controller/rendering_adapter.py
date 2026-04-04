"""
E₀ Rendering Adapter (C96)
============================
Pure projection: observation data → wire-format snapshot.

Canon basis:
  "Domain specificity enters only through embedding, not through
   mechanism." (AGI Blueprint §7)

The rendering adapter is a pure function — no state, no mutation.
It translates ObservationController.project() output into the same
wire-format that the UI already consumes (snapshot_codec format).

This closes the 3-step observation pipeline:
  C94: observation.py        — O-Landscape (domain definition)
  C95: observation_controller — navigation + project()
  C96: rendering_adapter      — project() → UI snapshot

The adapter adds observation-specific metadata:
  - obs_scope, obs_depth, obs_state for UI to display observation context
  - observation_options for navigation controls
  - observation_history for trajectory display

Usage:
    from e0_controller.rendering_adapter import render_observation

    ctrl = ObservationController(domain_landscape)
    ctrl.focus("node_A")
    ctrl.deepen()

    snapshot = render_observation(ctrl)
    # → JSON-safe dict in encode_landscape format + observation metadata
    # → send to UI via WebSocket / REST
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .observation import DEPTH_INDEX
from .observation_controller import ObservationController
from .primitives import Edge
from .tension import coherence


def render_observation(ctrl: ObservationController) -> Dict[str, Any]:
    """Render the current observation state as a wire-format snapshot.

    Returns a dict compatible with encode_landscape() format, plus
    observation-specific metadata under the "observation" key.

    The snapshot contains only what the observer can currently see —
    scope and depth determine visibility.
    """
    proj = ctrl.project()
    return _projection_to_snapshot(proj, ctrl)


def _projection_to_snapshot(
    proj: Dict[str, Any],
    ctrl: ObservationController,
) -> Dict[str, Any]:
    """Convert project() output to snapshot_codec wire format."""

    nodes: List[str] = proj["nodes"]
    raw_edges: List[Dict[str, str]] = proj["edges"]
    field_data: Dict[str, Dict] = proj.get("field", {})
    dyn_data: Dict[str, Dict] = proj.get("dynamics", {})

    # ── Build edge map in snapshot_codec format ──
    edges: Dict[str, Dict[str, Any]] = {}
    for e in raw_edges:
        src, tgt = e["source"], e["target"]
        key = f"{src}→{tgt}"

        edge_info: Dict[str, Any] = {
            "source": src,
            "target": tgt,
        }

        # Field layer (depth >= 1)
        if key in field_data:
            f = field_data[key]
            edge_info["delta"] = f["delta"]
            edge_info["R0"] = f["R0"]
            edge_info["R_eff"] = f["R_eff"]
            edge_info["S_eff"] = f["S_eff"]
            edge_info["coherence"] = coherence(f["S_eff"])
            edge_info["delta_H"] = f["R_eff"] - f["R0"]
            edge_info["v"] = f["delta"] / f["R_eff"] if f["R_eff"] > 0 else 0.0
        else:
            # Topo-only: structure visible, no values
            edge_info["delta"] = 0.0
            edge_info["R0"] = 0.0
            edge_info["R_eff"] = 0.0
            edge_info["S_eff"] = 0.0
            edge_info["coherence"] = 1.0
            edge_info["delta_H"] = 0.0
            edge_info["v"] = 0.0

        # Dynamics layer (depth >= 2)
        if key in dyn_data:
            d = dyn_data[key]
            edge_info["U"] = d["success_trace"]
            edge_info["F"] = d["failure_trace"]
            edge_info["trace_load"] = d["trace_load"]
            edge_info["trace_quality"] = d["trace_quality"]
        else:
            edge_info["U"] = 0.0
            edge_info["F"] = 0.0
            edge_info["trace_load"] = 0.0
            edge_info["trace_quality"] = 0.0

        # Inertia (depth >= 2, derived)
        tl = edge_info["trace_load"]
        tq = edge_info["trace_quality"]
        if tl > 0:
            from .config import DEFAULTS
            alpha, mu = DEFAULTS.inertia_alpha, DEFAULTS.mu
            edge_info["inertia"] = 1.0 - alpha * (tl / (tl + mu)) * (1.0 - abs(tq))
        else:
            edge_info["inertia"] = 1.0

        edges[key] = edge_info

    # ── Observation metadata ──
    options = ctrl.options()
    obs_meta = {
        "state": ctrl.current,
        "scope": ctrl.scope,
        "depth": ctrl.depth,
        "depth_index": ctrl.depth_index,
        "focused_node": ctrl.focused_node,
        "history": ctrl.history,
        "info": ctrl.info(),
        "options": [
            {
                "target": o["target"],
                "scope_change": o["scope_change"],
                "depth_change": o["depth_change"],
                "r_eff": round(o["r_eff"], 4),
                "s_eff": round(o["s_eff"], 4),
            }
            for o in options
        ],
    }

    # ── Assemble snapshot ──
    snapshot: Dict[str, Any] = {
        "states": nodes,
        "edges": edges,
        "modulation": {
            "curvature": False,
            "overlap": False,
            "inertia": False,
        },
        "observation": obs_meta,
    }

    return snapshot


def render_observation_landscape(ctrl: ObservationController) -> Dict[str, Any]:
    """Render the O-Landscape itself as a snapshot (meta-observation).

    This shows the observation state space — useful for debugging
    or for a "map of what the observer can see" overlay.
    """
    o = ctrl.o_landscape
    states = sorted(o._states)

    edges: Dict[str, Dict[str, Any]] = {}
    for e in o.edges:
        key = f"{e.source}→{e.target}"
        r_eff = o.effective_resistance(e.source, e.target)
        s_eff = o.effective_tension(e.source, e.target)
        edges[key] = {
            "source": e.source,
            "target": e.target,
            "delta": o.difference(e.source, e.target),
            "R0": o.base_resistance(e.source, e.target),
            "R_eff": r_eff,
            "S_eff": s_eff,
            "coherence": coherence(s_eff),
            "delta_H": r_eff - o.base_resistance(e.source, e.target),
            "v": o.transition_field(e.source, e.target),
            "U": o.historization.success_trace(e),
            "F": o.historization.failure_trace(e),
            "trace_quality": o.historization.trace_quality(e),
            "trace_load": o.historization.trace_load(e),
            "inertia": o.historization.inertia_factor(e),
        }

    return {
        "states": states,
        "edges": edges,
        "modulation": {
            "curvature": False,
            "overlap": False,
            "inertia": False,
        },
        "observation": {
            "state": ctrl.current,
            "scope": ctrl.scope,
            "depth": ctrl.depth,
            "depth_index": ctrl.depth_index,
            "focused_node": ctrl.focused_node,
            "is_meta": True,
        },
    }
