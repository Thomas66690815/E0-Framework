"""
E₀ Canon Loader (C48)
======================
Loads canonical landscape specifications from JSON files and
materializes them via the Bootstrapper (C44).

Canon JSON files live in e0_controller/canons/ and follow the
Bootstrapper spec format (nodes + edges) extended with:

  - Metadata: name, version, source, description
  - Node metadata: derivation_level, is_primitive, label, description
  - Edge metadata: derivation (human-readable derivation reason)
  - goal_states: list of final/emergent concepts
  - necessary_consequences: canon-derived consequences

The loader strips metadata for the Bootstrapper and preserves it
as a CanonInfo object for reflection and LLM context.

Design principle: the Canon's derivation order IS the topology.
Delta values rise with derivation level — they are the integration
costs between concepts, exactly as Ontodynamics defines resistance.

See E0_LLM_BOOTSTRAP_ARCHITECTURE_v1.md §6, §7.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .bootstrapper import bootstrap_landscape, BootstrapError
from .landscape import Landscape

# ──────────────────────────────────────────────
# Canon directory (relative to this file)
# ──────────────────────────────────────────────

CANON_DIR = Path(__file__).parent / "canons"


# ──────────────────────────────────────────────
# 1. Metadata Dataclasses
# ──────────────────────────────────────────────

@dataclass
class NodeInfo:
    """Metadata about a canonical concept."""
    id: str
    label: str
    derivation_level: int
    is_primitive: bool
    description: str


@dataclass
class EdgeInfo:
    """Metadata about a canonical derivation relationship."""
    source: str
    target: str
    derivation: str


@dataclass
class CanonInfo:
    """Full metadata about a loaded canon."""
    name: str
    version: str
    source: str
    description: str
    nodes: List[NodeInfo]
    edges: List[EdgeInfo]
    goal_states: List[str]
    necessary_consequences: List[str]


@dataclass
class CanonLandscape:
    """A materialized canon: Landscape + metadata."""
    landscape: Landscape
    info: CanonInfo


# ──────────────────────────────────────────────
# 2. Directory Listing
# ──────────────────────────────────────────────

def list_canons() -> List[str]:
    """List available canon names (JSON files in canons directory)."""
    if not CANON_DIR.is_dir():
        return []
    return sorted(p.stem for p in CANON_DIR.glob("*.json"))


# ──────────────────────────────────────────────
# 3. Raw Loading
# ──────────────────────────────────────────────

def load_canon_spec(name: str) -> Dict[str, Any]:
    """Load a raw canon JSON spec by name.

    Raises FileNotFoundError if the canon doesn't exist.
    """
    path = CANON_DIR / f"{name}.json"
    if not path.is_file():
        available = list_canons()
        raise FileNotFoundError(
            f"Canon '{name}' not found. Available: {available}"
        )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ──────────────────────────────────────────────
# 4. Metadata Extraction
# ──────────────────────────────────────────────

def _extract_info(spec: Dict[str, Any]) -> CanonInfo:
    """Extract metadata from canon spec."""
    nodes = []
    for n in spec.get("nodes", []):
        if isinstance(n, dict):
            nodes.append(NodeInfo(
                id=n["id"],
                label=n.get("label", n["id"]),
                derivation_level=n.get("derivation_level", 0),
                is_primitive=n.get("is_primitive", False),
                description=n.get("description", ""),
            ))

    edges = []
    for e in spec.get("edges", []):
        if isinstance(e, dict):
            edges.append(EdgeInfo(
                source=e.get("from", ""),
                target=e.get("to", ""),
                derivation=e.get("derivation", ""),
            ))

    return CanonInfo(
        name=spec.get("name", "unknown"),
        version=spec.get("version", "0"),
        source=spec.get("source", ""),
        description=spec.get("description", ""),
        nodes=nodes,
        edges=edges,
        goal_states=spec.get("goal_states", []),
        necessary_consequences=spec.get("necessary_consequences", []),
    )


# ──────────────────────────────────────────────
# 5. Spec Conversion
# ──────────────────────────────────────────────

def _to_bootstrapper_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Convert canon spec to bootstrapper-compatible format.

    Strips metadata, converts node dicts to plain strings.
    """
    raw_nodes = spec.get("nodes", [])
    nodes = []
    for n in raw_nodes:
        if isinstance(n, dict):
            nodes.append(n["id"])
        else:
            nodes.append(str(n))

    edges = []
    for e in spec.get("edges", []):
        edge: Dict[str, Any] = {
            "from": e["from"],
            "to": e["to"],
            "delta": e.get("delta", 0.5),
            "resistance": e.get("resistance", 0.3),
        }
        if "initial_U" in e:
            edge["initial_U"] = e["initial_U"]
        if "initial_F" in e:
            edge["initial_F"] = e["initial_F"]
        if "confidence" in e:
            edge["confidence"] = e["confidence"]
        edges.append(edge)

    return {"nodes": nodes, "edges": edges}


# ──────────────────────────────────────────────
# 5b. Edge Metadata Injection (C205)
# ──────────────────────────────────────────────

def _inject_edge_metadata(landscape: Landscape, spec: dict) -> None:
    """Inject relation type and derivation from canon spec into landscape.

    Called after bootstrap_landscape() to enrich edges with the semantic
    information that the bootstrapper doesn't carry.
    """
    for e in spec.get("edges", []):
        src = e.get("from", "")
        tgt = e.get("to", "")
        if not landscape.has_edge(src, tgt):
            continue
        meta = {}
        if "type" in e:
            meta["relation_type"] = e["type"]
        if "derivation" in e:
            meta["derivation"] = e["derivation"]
        if "confidence" in e:
            meta["confidence"] = e["confidence"]
        if meta:
            landscape.set_edge_meta(src, tgt, **meta)


# ──────────────────────────────────────────────
# 6. Main Loader
# ──────────────────────────────────────────────

def load_canon(name: str) -> CanonLandscape:
    """Load and materialize a canon landscape.

    Steps:
    1. Load JSON spec from canons directory
    2. Extract metadata as CanonInfo
    3. Convert to bootstrapper format
    4. Materialize via bootstrap_landscape()

    Returns CanonLandscape with both the live Landscape
    and the canonical metadata.

    Raises FileNotFoundError if canon not found.
    Raises BootstrapError if spec is invalid.
    """
    spec = load_canon_spec(name)
    info = _extract_info(spec)
    bs_spec = _to_bootstrapper_spec(spec)
    landscape = bootstrap_landscape(bs_spec)

    # Inject canon edge metadata (C205: relation type, derivation, confidence)
    _inject_edge_metadata(landscape, spec)

    return CanonLandscape(landscape=landscape, info=info)


# ──────────────────────────────────────────────
# 7. Summary Formatting (for LLM context)
# ──────────────────────────────────────────────

def format_canon_summary(info: CanonInfo) -> str:
    """Format a human-readable summary of a canon for LLM context."""
    lines = [
        f"Canon: {info.name} (v{info.version})",
        f"Source: {info.source}",
        f"Description: {info.description}",
        "",
        "Concepts:",
    ]

    # Group by derivation level
    by_level: Dict[int, List[NodeInfo]] = {}
    for n in info.nodes:
        by_level.setdefault(n.derivation_level, []).append(n)

    for level in sorted(by_level):
        all_primitive = all(n.is_primitive for n in by_level[level])
        tier = "Primitive" if all_primitive else "Derived"
        lines.append(f"  Level {level} ({tier}):")
        for n in by_level[level]:
            lines.append(f"    - {n.label}: {n.description}")
        lines.append("")

    lines.append("Derivation relationships:")
    for e in info.edges:
        lines.append(f"  {e.source} -> {e.target}: {e.derivation}")

    if info.goal_states:
        lines.append("")
        lines.append(f"Goal states: {', '.join(info.goal_states)}")

    if info.necessary_consequences:
        lines.append("")
        lines.append("Necessary consequences:")
        for c in info.necessary_consequences:
            lines.append(f"  - {c}")

    return "\n".join(lines)
