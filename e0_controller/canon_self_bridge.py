"""
E₀ Canon ↔ Self-Graph Bridge
==============================
Connects the canon landscape (what E0 believes) with the self-graph
(how E0 operates) — making explicit that the operational cycle IS
the canon, seen from the process side.

Canon basis (from E0_LLM_BOOTSTRAP_ARCHITECTURE_v1.md):
    Level 1 — Structural self-image: self-graph topology
    Level 2 — Operational reflection: component quality
    Level 3 — Canon alignment: do my operations match my ontology?

Usage:
    from e0_controller.canon_self_bridge import (
        build_self_exposition, CANON_PROCESS_MAP,
    )
    from e0_controller.self_graph import SelfGraph
    from e0_controller.canon_loader import load_canon

    sg = SelfGraph()
    cl = load_canon("ontodynamics")
    exposition = build_self_exposition(cl, sg)
    print(exposition)
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set

from .canon_loader import CanonLandscape, format_canon_summary
from .self_graph import SelfGraph, ALL_COMPONENTS
from .reflexive_action import ReflexiveJournal


# ──────────────────────────────────────────────
# 1. Canon ↔ Process Mapping
# ──────────────────────────────────────────────

# Each self-graph component → the canon concept(s) it instantiates.
# This is the structural claim: E0's operation IS the canon in action.
CANON_PROCESS_MAP: Dict[str, List[str]] = {
    # Δ-detection: the amplitude module finds differences
    "amplitude": ["differenz"],
    # State selection via A0 + realizability rate
    "born": ["axiom_a0", "rate"],
    # Execution: local realization along structurally admissible paths
    "realization": ["lokale_realisierung", "pfad"],
    # THE central connection — operational historization IS the canon primitive
    "historization": ["historisierung"],
    # Resistance from accumulated structure + topological inertia
    "inertia": ["widerstand", "masse"],
    # The transition field: connecting differences via the operational cycle
    "transition_field": ["verbindung", "operationaler_zyklus"],
    # Curvature modulation → degree of overlap (topological quality)
    "curvature": ["gradueller_overlap"],
    # Overlap modulation → also degree-based
    "overlap": ["gradueller_overlap"],
}

# Reverse map: canon node → which self-graph component(s) instantiate it
def _build_reverse_map() -> Dict[str, List[str]]:
    rev: Dict[str, List[str]] = {}
    for comp, canon_nodes in CANON_PROCESS_MAP.items():
        for node in canon_nodes:
            rev.setdefault(node, []).append(comp)
    return rev

PROCESS_CANON_MAP: Dict[str, List[str]] = _build_reverse_map()


# ──────────────────────────────────────────────
# 2. Canon Coverage Analysis
# ──────────────────────────────────────────────

def canon_coverage(cl: CanonLandscape) -> Dict[str, object]:
    """Analyze which canon concepts are operationally instantiated.

    Returns a dict with:
      - instantiated: set of canon node IDs that map to self-graph components
      - not_instantiated: set of canon node IDs with no operational counterpart
      - coverage_ratio: float in [0, 1]
    """
    all_canon_nodes = {n.id for n in cl.info.nodes}
    instantiated = set(PROCESS_CANON_MAP.keys()) & all_canon_nodes
    not_instantiated = all_canon_nodes - instantiated
    ratio = len(instantiated) / len(all_canon_nodes) if all_canon_nodes else 0.0
    return {
        "instantiated": instantiated,
        "not_instantiated": not_instantiated,
        "coverage_ratio": ratio,
    }


# ──────────────────────────────────────────────
# 3. Combined Self-Exposition
# ──────────────────────────────────────────────

def format_process_status(sg: SelfGraph) -> str:
    """Format the self-graph as canon-aligned operational status."""
    snap = sg.snapshot()
    lines = []
    for comp in ALL_COMPONENTS:
        m = snap[comp]
        canon_nodes = CANON_PROCESS_MAP.get(comp, [])
        canon_str = ", ".join(canon_nodes) if canon_nodes else "(no canon mapping)"
        lines.append(
            f"  {comp:20s} → {canon_str:40s}  "
            f"quality={m['quality']:+.3f}  load={m['load']:.1f}  "
            f"inertia={m['inertia']:.3f}"
        )
    return "\n".join(lines)


def build_self_exposition(
    cl: CanonLandscape,
    sg: Optional[SelfGraph] = None,
    reflexive_journal: Optional[ReflexiveJournal] = None,
) -> str:
    """Build a complete self-exposition for LLM context.

    Combines:
      1. Canon summary (what E0 believes about reality)
      2. Process status (how well E0's components are performing)
      3. Canon coverage (which beliefs are operationally active)
      4. Structural insight (what the mapping reveals)
      5. Reflexive history (what E0 has done to itself) — Stufe 4b

    If sg is None, sections 2 and 4 are marked as "no operational data".
    If reflexive_journal is None or empty, section 5 notes no actions taken.
    """
    sections = []

    # Section 1: Canon knowledge
    sections.append("=== WHAT I BELIEVE (Canon Landscape) ===")
    sections.append(format_canon_summary(cl.info))

    # Section 2: Operational status
    sections.append("")
    sections.append("=== HOW I OPERATE (Self-Graph ↔ Canon) ===")
    if sg is not None:
        sections.append(format_process_status(sg))
    else:
        sections.append("  (no operational data — self-graph not attached)")

    # Section 3: Coverage analysis
    sections.append("")
    sections.append("=== CANON COVERAGE ===")
    cov = canon_coverage(cl)
    inst = sorted(cov["instantiated"])
    not_inst = sorted(cov["not_instantiated"])
    ratio = cov["coverage_ratio"]
    sections.append(f"  Coverage: {ratio:.0%} ({len(inst)}/{len(inst) + len(not_inst)})")
    sections.append(f"  Instantiated:     {', '.join(inst)}")
    sections.append(f"  Not yet operational: {', '.join(not_inst)}")

    # Section 4: Structural insight
    sections.append("")
    sections.append("=== STRUCTURAL INSIGHT ===")
    sections.append(
        "  The self-graph's operational cycle (amplitude → born → realization →"
    )
    sections.append(
        "  historization → inertia → transition_field → amplitude) IS the canon's"
    )
    sections.append(
        "  'operationaler_zyklus' (L6) — not a separate implementation, but the"
    )
    sections.append(
        "  same structure seen from the process side."
    )
    sections.append("")
    sections.append(
        "  Key identity: self-graph 'historization' component = canon 'historisierung'"
    )
    sections.append(
        "  primitive. When the self-graph historizes its own outcomes, it performs"
    )
    sections.append(
        "  exactly what the canon describes: realized connections leave irreversible"
    )
    sections.append(
        "  structural trace."
    )

    if sg is not None:
        q = sg.component_quality("historization")
        load = sg.component_load("historization")
        sections.append("")
        sections.append(f"  Current historization quality: {q:+.3f} (load={load:.1f})")
        if q > 0.5:
            sections.append("  → The canon's central mechanism is working well.")
        elif q < -0.2:
            sections.append("  → WARNING: The canon's central mechanism is struggling.")
        elif load < 1.0:
            sections.append("  → Insufficient data to assess canon alignment.")
        else:
            sections.append("  → Mixed results — historization quality is uncertain.")

        # Not-instantiated concepts = the framework's epistemic frontier
        if not_inst:
            sections.append("")
            sections.append("  EPISTEMIC FRONTIER:")
            sections.append(
                "  The following canon concepts exist in my knowledge but have no"
            )
            sections.append(
                "  direct operational counterpart yet. They represent what I"
            )
            sections.append(
                "  understand theoretically but cannot yet verify through experience:"
            )
            for node_id in not_inst:
                node = next((n for n in cl.info.nodes if n.id == node_id), None)
                if node:
                    sections.append(f"    - {node.label} (L{node.derivation_level})")

    # Section 5: Reflexive action history (Stufe 4b)
    sections.append("")
    sections.append("=== WHAT I HAVE DONE TO MYSELF (Reflexive History) ===")
    if reflexive_journal is not None and reflexive_journal.total_actions > 0:
        sections.append(reflexive_journal.format())
        active = reflexive_journal.active_deactivations
        if active:
            components = sorted({e.action.component for e in active})
            sections.append("")
            sections.append(
                f"  Currently {len(active)} modulation(s) deactivated "
                f"by self-diagnosis: {', '.join(components)}"
            )
            sections.append(
                "  This demonstrates operational reflexivity (canon L7): I have"
            )
            sections.append(
                "  modified my own transition structure based on self-assessment"
            )
            sections.append(
                "  of component health. These changes are reversible."
            )
        else:
            sections.append("")
            sections.append(
                "  All prior reflexive actions have been restored."
            )
            sections.append(
                "  Self-modification occurred but was subsequently reverted."
            )
        # Current modulation state
        state = reflexive_journal.current_state()
        if state:
            sections.append("")
            sections.append("  Current modulation state (from self-diagnosis):")
            for comp, is_active in state:
                status = "ACTIVE" if is_active else "DEACTIVATED"
                sections.append(f"    {comp}: {status}")
    else:
        sections.append(
            "  No reflexive self-modifications taken. All modulation"
        )
        sections.append(
            "  components operate at their initial configuration."
        )

    return "\n".join(sections)
