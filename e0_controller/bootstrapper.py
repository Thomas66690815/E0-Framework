"""
E₀ Domain Bootstrapper (C44)
==============================
Converts structured domain descriptions into initialized Landscapes.

Solves the cold-start problem: E0 needs a populated Landscape with
initial traces before it can make decisions. The Bootstrapper accepts
a domain specification (from an LLM, a human, or a file) and produces
a ready-to-use Landscape with conservative initial historization.

Key design principle: LLM-sourced knowledge is treated as *hypothesis*,
not truth. Initial traces have high trace_load but quality scaled by
confidence — low confidence means balanced U/F, which produces high
inertia_factor dampening. E0 is cautious with unverified knowledge.

Input format (DomainSpec):
    {
        "nodes": ["A", "B", "C"],
        "edges": [
            {
                "from": "A", "to": "B",
                "delta": 1.0, "resistance": 0.5,
                "initial_U": 8.0, "initial_F": 2.0,
                "confidence": 0.7
            },
            ...
        ]
    }

See E0_LLM_BOOTSTRAP_ARCHITECTURE_v1.md §4.1 and §5.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .primitives import Edge, Outcome
from .landscape import Landscape
from .historization import Historization


# ──────────────────────────────────────────────
# 1. Validation Errors
# ──────────────────────────────────────────────

class BootstrapError(Exception):
    """Raised when a domain spec fails validation."""
    pass


# ──────────────────────────────────────────────
# 2. Edge Spec
# ──────────────────────────────────────────────

@dataclass
class EdgeSpec:
    """Validated specification for a single edge."""
    source: str
    target: str
    delta: float
    resistance: float
    initial_U: float = 0.0
    initial_F: float = 0.0
    confidence: float = 1.0


# ──────────────────────────────────────────────
# 3. Validation
# ──────────────────────────────────────────────

def validate_spec(spec: Dict[str, Any]) -> List[EdgeSpec]:
    """Validate a domain spec dict and return parsed EdgeSpecs.

    Raises BootstrapError on any structural problem.
    """
    if not isinstance(spec, dict):
        raise BootstrapError("Spec must be a dict")

    # Nodes
    nodes = spec.get("nodes", [])
    if not isinstance(nodes, list) or len(nodes) == 0:
        raise BootstrapError("Spec must have a non-empty 'nodes' list")
    for n in nodes:
        if not isinstance(n, str) or not n.strip():
            raise BootstrapError(f"Invalid node name: {n!r}")

    # Edges
    raw_edges = spec.get("edges", [])
    if not isinstance(raw_edges, list) or len(raw_edges) == 0:
        raise BootstrapError("Spec must have a non-empty 'edges' list")

    node_set = set(nodes)
    edge_specs: List[EdgeSpec] = []
    seen_edges: Set[tuple] = set()

    for i, e in enumerate(raw_edges):
        if not isinstance(e, dict):
            raise BootstrapError(f"Edge {i}: must be a dict")

        src = e.get("from", "")
        tgt = e.get("to", "")
        if not src or not tgt:
            raise BootstrapError(f"Edge {i}: missing 'from' or 'to'")
        if src not in node_set:
            raise BootstrapError(f"Edge {i}: source '{src}' not in nodes")
        if tgt not in node_set:
            raise BootstrapError(f"Edge {i}: target '{tgt}' not in nodes")
        if src == tgt:
            raise BootstrapError(f"Edge {i}: self-loop '{src}'→'{tgt}'")

        pair = (src, tgt)
        if pair in seen_edges:
            raise BootstrapError(f"Edge {i}: duplicate '{src}'→'{tgt}'")
        seen_edges.add(pair)

        delta = float(e.get("delta", 0.0))
        resistance = float(e.get("resistance", 0.0))
        if delta < 0:
            raise BootstrapError(f"Edge {i}: delta must be ≥ 0, got {delta}")
        if resistance < 0:
            raise BootstrapError(f"Edge {i}: resistance must be ≥ 0, got {resistance}")

        initial_U = float(e.get("initial_U", 0.0))
        initial_F = float(e.get("initial_F", 0.0))
        if initial_U < 0:
            raise BootstrapError(f"Edge {i}: initial_U must be ≥ 0")
        if initial_F < 0:
            raise BootstrapError(f"Edge {i}: initial_F must be ≥ 0")

        confidence = float(e.get("confidence", 1.0))
        if not (0.0 <= confidence <= 1.0):
            raise BootstrapError(
                f"Edge {i}: confidence must be in [0, 1], got {confidence}"
            )

        edge_specs.append(EdgeSpec(
            source=src, target=tgt,
            delta=delta, resistance=resistance,
            initial_U=initial_U, initial_F=initial_F,
            confidence=confidence,
        ))

    return edge_specs


# ──────────────────────────────────────────────
# 4. Trace Initialization
# ──────────────────────────────────────────────

def _apply_confidence(U: float, F: float, confidence: float) -> tuple:
    """Scale initial traces by confidence.

    When confidence < 1.0, the trace magnitudes are preserved but
    the *directional balance* is reduced toward 0.

    At confidence=1.0: return (U, F) as-is.
    At confidence=0.0: return equal split → quality ≈ 0 → maximum caution.

    The formula preserves total trace_load (U+F) while mixing
    toward the midpoint:
        U' = midpoint + confidence * (U - midpoint)
        F' = midpoint + confidence * (F - midpoint)
    """
    if confidence >= 1.0:
        return U, F
    total = U + F
    if total < 1e-12:
        return 0.0, 0.0
    mid = total / 2.0
    U_adj = mid + confidence * (U - mid)
    F_adj = mid + confidence * (F - mid)
    return max(0.0, U_adj), max(0.0, F_adj)


# ──────────────────────────────────────────────
# 5. Bootstrap Builder
# ──────────────────────────────────────────────

def bootstrap_landscape(spec: Dict[str, Any]) -> Landscape:
    """Build and initialize a Landscape from a domain spec.

    Steps:
    1. Validate the spec
    2. Create Landscape with nodes and edges
    3. Inject initial traces (adjusted by confidence)

    Returns a ready-to-use Landscape with conservative initial
    historization. The Landscape has inertia_modulation=True by
    default (since the initial traces exist precisely to be
    modulated by inertia_factor).

    Raises BootstrapError on validation failure.
    """
    edge_specs = validate_spec(spec)

    ls = Landscape()
    ls.inertia_modulation = True

    # Add all nodes explicitly (spec may list nodes without edges)
    for node in spec["nodes"]:
        ls.add_state(node)

    # Add edges
    for es in edge_specs:
        ls.add_edge(es.source, es.target, es.delta, es.resistance,
                     confidence=es.confidence)

    # Inject initial traces
    for es in edge_specs:
        if es.initial_U > 0 or es.initial_F > 0:
            U_adj, F_adj = _apply_confidence(
                es.initial_U, es.initial_F, es.confidence
            )
            edge = Edge(es.source, es.target)
            _inject_traces(ls.historization, edge, U_adj, F_adj)

    return ls


def _inject_traces(hist: Historization, edge: Edge,
                   U: float, F: float) -> None:
    """Directly set initial trace values on an edge.

    This bypasses the normal update() cycle to set starting
    traces from external knowledge. The traces are written
    at the current tau — no decay gap.
    """
    hist._U[edge] = U
    hist._F[edge] = F
    hist._tau_last[edge] = hist._tau
