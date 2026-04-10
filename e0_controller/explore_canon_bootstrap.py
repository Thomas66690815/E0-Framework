"""Explore: Canon × Bootstrap Multiverse — C200.

Two landscapes describing the SAME system from different perspectives:
1. Canon: Ontodynamics theory (51 nodes, 93 edges) — what E₀ IS
2. Bootstrap: Project memory (41 nodes, 76 edges) — what E₀ DOES

They share the same subject but have disjoint node sets.
Standard cross-reflexion (C62) uses topological frontier detection.
Here the bridge is SEMANTIC: the LLM identifies which Canon concepts
relate to which Bootstrap nodes.

The interference hypothesis: Canon knowledge should improve Bootstrap
navigation because theoretical understanding provides structural
shortcuts that pure exploration cannot discover.
"""

import json
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from e0_controller.bootstrapper import bootstrap_landscape
from e0_controller.canon_loader import load_canon
from e0_controller.explore_bootstrap_landscape import (
    load_bootstrap,
    extract_nodes,
    extract_edges,
    build_spec,
    inject_node_traces,
    load_learning_state,
    save_learning_state,
    local_transition_potential,
    local_autonomous_step,
    transition_potential,
    MU,
    BOOTSTRAP_PATH,
)
from e0_controller.primitives import Outcome


# ---------------------------------------------------------------------------
# Phase 1: Static bridge — structural mapping Canon ↔ Bootstrap
# ---------------------------------------------------------------------------

# Maps Canon concept regions to Bootstrap node types/IDs.
# This is hand-curated: the canon's derivation hierarchy maps onto
# the bootstrap's operational structure.
CANON_BOOTSTRAP_BRIDGE = {
    # Canon primitives → Bootstrap architecture layers
    "difference": ["L1"],           # primitives layer implements Δ
    "local_realization": ["L3"],    # controller executes transitions
    "connection": ["L2"],           # landscape IS the connection topology
    "overlap": ["L4"],              # phase/amplitude uses overlap
    "historization": ["L1", "L2"],  # primitives + landscape store traces

    # Canon derived concepts → Bootstrap layers
    "tension": ["L3"],              # controller computes S_eff
    "resistance": ["L1"],           # primitives define R₀/R_eff
    "axiom_a0": ["WP-2"],          # "historization dominant" = A₀
    "reflexivity": ["L5"],          # reflexion layer
    "domain_invariance": ["WP-1"], # skeleton/muscle principle
    "structural_alignment": ["WP-4"],  # quality > quantity
    "negative_necessity": ["WP-7"],    # doubt is structural

    # Canon high-level → Bootstrap specific
    "multiverse": ["L6"],
    "cross_reflexion": ["L6"],
    "dream_mode": ["L9"],
    "structural_temperature": ["L10"],  # structural entropy
    "sleep_wake_cycle": ["L11"],
    "observation": ["L8"],
    "greedy_navigation": ["L3"],
    "amplitude_override": ["L4"],
    "exploration_policy": ["L4"],

    # Canon → Bootstrap traps & breakthroughs
    "mass": ["GT-4"],              # distance collapse = mass-related trap
    "operational_cycle": ["BT-4"],  # dual nature IS operational duality
    "self_graph": ["BT-4", "GT-5"],  # self-graph resolves override trap

    # Canon → Bootstrap open threads
    "coupling_router": ["OPEN-1"],    # orchestrator pattern
    "asymmetric_coupling": ["OPEN-2"],  # adversarial stability
    "scoped_reflexion": ["OPEN-3"],   # longer loops need scoped reflexion

    # v3.0: New Canon concepts (post-C122)
    "transition_potential": ["L3"],     # T(e) drives controller exploration
    "epistemic_trust": ["L1", "L3"],   # trust modulates primitives + controller
    "auto_tuning": ["L5", "BT-4"],     # reflexion self-optimization, dual nature
    "shared_historization": ["L6", "BT-3"],  # multiverse cooperation, cooperation BT
    "bootstrap_landscape": ["L2", "HERE"],   # landscape init, project state
    "perception_ontology": ["L8"],      # observation → perception
    "communication_intent": ["L8"],     # observation → expression
    "compatibility_gating": ["L9"],     # dream gating
    "wl_node_fingerprint": ["L9", "BT-1"],  # dream matching, Hungarian BT
    "curriculum_navigator": ["L11"],    # macro-orchestration ≈ sleep-wake
    "n_domain_mesh": ["L6"],            # multiverse at scale
    "canon_bootstrap_multiverse": ["HERE"],  # THIS exploration
}


def build_static_bridges(canon_info, bootstrap_nodes):
    """Build directed edges from Canon → Bootstrap using static mapping.

    Returns list of edge dicts compatible with bootstrapper spec.
    """
    bridges = []
    canon_ids = {n.id for n in canon_info.nodes}

    for canon_id, bs_ids in CANON_BOOTSTRAP_BRIDGE.items():
        if canon_id not in canon_ids:
            continue
        for bs_id in bs_ids:
            if bs_id not in bootstrap_nodes:
                continue
            # Bidirectional: theory informs practice AND practice grounds theory
            bridges.append({
                "from": f"C:{canon_id}",
                "to": f"B:{bs_id}",
                "delta": 0.6,
                "resistance": 0.5,
                "confidence": 0.7,
                "derivation": f"static bridge: {canon_id} → {bs_id}",
                "bridge_type": "static",
            })
            bridges.append({
                "from": f"B:{bs_id}",
                "to": f"C:{canon_id}",
                "delta": 0.6,
                "resistance": 0.5,
                "confidence": 0.7,
                "derivation": f"static bridge: {bs_id} → {canon_id}",
                "bridge_type": "static",
            })

    return bridges


# ---------------------------------------------------------------------------
# Phase 2: LLM semantic bridge — discover connections the map misses
# ---------------------------------------------------------------------------


def llm_discover_bridges(canon_info, bootstrap_nodes, dry_run=False):
    """Ask LLM to discover semantic connections between Canon and Bootstrap.

    The LLM sees both node sets and identifies cross-domain edges
    that the static mapping misses.

    Returns list of bridge edge dicts.
    """
    # Build Canon summary
    canon_lines = ["Canon nodes (Ontodynamics theory):"]
    for n in sorted(canon_info.nodes, key=lambda x: x.derivation_level):
        canon_lines.append(
            f"  L{n.derivation_level:2d} {n.id:30s}  {n.description[:60]}"
        )

    # Build Bootstrap summary
    bs_lines = ["Bootstrap nodes (project memory):"]
    for nid in sorted(bootstrap_nodes.keys()):
        node = bootstrap_nodes[nid]
        bs_lines.append(
            f"  {nid:8s} [{node['type']:20s}]  {node['label'][:60]}"
        )

    canon_text = "\n".join(canon_lines)
    bs_text = "\n".join(bs_lines)

    system = (
        "You are analyzing the E₀ framework from two perspectives. "
        "The Canon (Ontodynamics) describes E₀'s theoretical foundation — formal concepts "
        "derived from primitives. The Bootstrap describes E₀'s project reality — architecture "
        "layers, resolved mistakes, breakthroughs, open problems. "
        "Your task: find meaningful connections between these two descriptions. "
        "A connection is meaningful if a theoretical concept EXPLAINS, PREDICTS, or RESOLVES "
        "something in the project reality, or vice versa."
    )

    user = (
        f"Find the 10 most meaningful connections between Canon and Bootstrap nodes.\n\n"
        f"{canon_text}\n\n{bs_text}\n\n"
        f"For each connection, specify:\n"
        f"- canon_id: the Canon node ID (exact)\n"
        f"- bootstrap_id: the Bootstrap node ID (exact)\n"
        f"- direction: 'canon_to_bootstrap' or 'bootstrap_to_canon'\n"
        f"- delta: structural difference 0.1-0.9 (high = different perspectives)\n"
        f"- reason: one sentence explaining the connection\n\n"
        f"Focus on connections NOT obvious from the layer names. "
        f"We're looking for insights like:\n"
        f"- A theoretical concept that could resolve an open thread\n"
        f"- A breakthrough that confirms a theoretical prediction\n"
        f"- A trap that CONTRADICTS a theoretical assumption\n"
        f"- A perspective check that operationalizes a formal concept\n\n"
        f"Respond with ONLY a JSON array:\n"
        f'[{{"canon_id": "...", "bootstrap_id": "...", "direction": "...", '
        f'"delta": 0.5, "reason": "..."}}]\n'
        f"No other text."
    )

    if dry_run:
        return [
            {"from": "C:negative_necessity", "to": "B:OPEN-2",
             "delta": 0.7, "resistance": 0.5, "confidence": 0.6,
             "derivation": "LLM bridge: dry_run placeholder",
             "bridge_type": "llm_discovered"},
        ]

    try:
        from e0_controller.llm_adapter import LLMConfig, openai_call

        config = LLMConfig(
            model="gpt-4.1-mini",
            temperature=0.2,
            max_tokens=2048,
        )
        response = openai_call(system, user, config)

        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        results = json.loads(text)

        # Validate and convert to bridge edges
        canon_ids = {n.id for n in canon_info.nodes}
        bridges = []
        for r in results:
            cid = r.get("canon_id", "")
            bid = r.get("bootstrap_id", "")
            if cid not in canon_ids or bid not in bootstrap_nodes:
                continue

            direction = r.get("direction", "canon_to_bootstrap")
            if direction == "canon_to_bootstrap":
                src, tgt = f"C:{cid}", f"B:{bid}"
            else:
                src, tgt = f"B:{bid}", f"C:{cid}"

            bridges.append({
                "from": src,
                "to": tgt,
                "delta": max(0.1, min(0.9, float(r.get("delta", 0.5)))),
                "resistance": 0.5,
                "confidence": 0.6,
                "derivation": f"LLM bridge: {r.get('reason', '?')[:80]}",
                "bridge_type": "llm_discovered",
            })

        return bridges

    except Exception as exc:
        print(f"  LLM bridge discovery failed: {exc}")
        return []


# ---------------------------------------------------------------------------
# Phase 3: Unified Landscape — Canon + Bootstrap + Bridges
# ---------------------------------------------------------------------------


def build_unified_landscape(canon_info, canon_landscape, bootstrap_nodes,
                            bootstrap_edges, bridges):
    """Build a single landscape containing Canon + Bootstrap + bridge edges.

    Node naming: Canon nodes get "C:" prefix, Bootstrap nodes get "B:" prefix.
    This prevents ID collisions and makes cross-domain edges visible.
    """
    # Canon nodes
    all_nodes = {}
    for n in canon_info.nodes:
        nid = f"C:{n.id}"
        all_nodes[nid] = {
            "type": "canon_concept",
            "label": n.description[:60] if n.description else n.id,
            "derivation_level": n.derivation_level,
            "is_primitive": n.is_primitive,
            "domain": "canon",
            "U": 1.0 if n.is_primitive else 0.5,
            "F": 0.0,
        }

    # Bootstrap nodes
    for nid, node in bootstrap_nodes.items():
        uid = f"B:{nid}"
        all_nodes[uid] = {
            **node,
            "domain": "bootstrap",
        }

    # Canon edges (prefixed)
    all_edges = []
    for edge_info in canon_info.edges:
        all_edges.append({
            "from": f"C:{edge_info.source}",
            "to": f"C:{edge_info.target}",
            "delta": 0.3,  # intra-canon: moderate difference
            "resistance": 0.2,
            "confidence": 0.9,
            "derivation": f"canon: {edge_info.derivation}",
        })

    # Bootstrap edges (prefixed)
    for edge in bootstrap_edges:
        all_edges.append({
            "from": f"B:{edge['from']}",
            "to": f"B:{edge['to']}",
            "delta": edge["delta"],
            "resistance": edge["resistance"],
            "confidence": edge.get("confidence", 0.8),
            "derivation": edge.get("derivation", "bootstrap edge"),
        })

    # Bridge edges (already prefixed)
    for bridge in bridges:
        all_edges.append({
            "from": bridge["from"],
            "to": bridge["to"],
            "delta": bridge["delta"],
            "resistance": bridge["resistance"],
            "confidence": bridge.get("confidence", 0.6),
            "derivation": bridge.get("derivation", "bridge edge"),
        })

    return all_nodes, all_edges


def measure_interference(landscape, unified_nodes, bootstrap_nodes):
    """Measure how Canon knowledge affects Bootstrap navigation.

    Computes: (1) which Canon nodes are reachable from B:HERE via BFS,
    (2) how many Bootstrap nodes gain Canon bridges, (3) local T-potential
    shift from the bridge edges.

    Returns dict with metrics.
    """
    # BFS reachability from B:HERE (3 hops)
    visited = set()
    frontier = {"B:HERE"}
    for depth in range(3):
        next_frontier = set()
        for src in frontier:
            for e in landscape.edges:
                if e.source == src and e.target not in visited:
                    next_frontier.add(e.target)
        visited |= frontier
        frontier = next_frontier - visited
    visited |= frontier

    canon_reachable = {s for s in visited if s.startswith("C:")}
    bootstrap_reachable = {s for s in visited if s.startswith("B:")}

    # Local T-potential from B:HERE (direct neighbors)
    local = local_transition_potential(
        landscape, unified_nodes, "B:HERE", horizon=3
    )

    # Which Bootstrap targets have Canon bridges?
    bridge_targets = set()
    for e in landscape.edges:
        if e.source.startswith("C:") and e.target.startswith("B:"):
            bridge_targets.add(e.target)
        elif e.source.startswith("B:") and e.target.startswith("C:"):
            bridge_targets.add(e.source)

    return {
        "total_targets": len(local),
        "canon_targets": len(canon_reachable),
        "bootstrap_targets": len(bootstrap_reachable),
        "bridge_connected": len(bridge_targets),
        "top_local": sorted(local.items(), key=lambda x: -x[1])[:5],
    }


# ---------------------------------------------------------------------------
# Phase 4: Exploration — navigate the unified landscape
# ---------------------------------------------------------------------------


def run_unified_exploration(landscape, unified_nodes, max_steps=30):
    """Explore the unified Canon × Bootstrap landscape.

    Tracks: domain crossings (how often exploration crosses the bridge),
    which Canon concepts inform Bootstrap decisions, and vice versa.
    """
    from e0_controller.landscape import Edge as _Edge

    current = "B:HERE"
    path = [current]
    visited_count = {}
    domain_crossings = 0

    for step in range(1, max_steps + 1):
        visited_count[current] = visited_count.get(current, 0) + 1

        nbr, potential = local_autonomous_step(
            landscape, unified_nodes, current, horizon=3
        )

        if nbr is None:
            break

        # Track domain crossing
        src_domain = "canon" if current.startswith("C:") else "bootstrap"
        tgt_domain = "canon" if nbr.startswith("C:") else "bootstrap"
        if src_domain != tgt_domain:
            domain_crossings += 1

        # Historize
        edge = _Edge(current, nbr)
        if landscape.has_edge(current, nbr):
            node_info = unified_nodes.get(nbr, {})
            node_type = node_info.get("type", "")
            if node_type == "open_thread":
                outcome = Outcome.FAILURE
            elif visited_count.get(nbr, 0) > 0 and node_type != "open_thread":
                outcome = Outcome.FAILURE
            else:
                outcome = Outcome.SUCCESS
            landscape.historization.update(edge, outcome)

        path.append(nbr)
        current = nbr

    # Analysis
    unique = set(path)
    canon_visited = {s for s in unique if s.startswith("C:")}
    bootstrap_visited = {s for s in unique if s.startswith("B:")}
    open_reached = {s for s in unique
                    if unified_nodes.get(s, {}).get("type") == "open_thread"}

    return {
        "path": path,
        "steps": len(path) - 1,
        "unique_states": len(unique),
        "canon_visited": len(canon_visited),
        "bootstrap_visited": len(bootstrap_visited),
        "domain_crossings": domain_crossings,
        "open_threads_reached": len(open_reached),
        "open_thread_names": sorted(open_reached),
        "canon_states": sorted(canon_visited),
        "crossing_rate": domain_crossings / max(1, len(path) - 1),
    }


# ---------------------------------------------------------------------------
# Phase 5: Persist cross-domain discoveries
# ---------------------------------------------------------------------------


def persist_cross_domain_edges(bridges, dry_run=False):
    """Persist cross-domain bridge edges to learning_state.json.

    Stored under cross_domain_bridges section.
    """
    if not bridges or dry_run:
        return len(bridges)

    ls = load_learning_state()

    if "cross_domain_bridges" not in ls:
        ls["cross_domain_bridges"] = {
            "_comment": "Edges connecting Canon (theory) and Bootstrap (practice).",
            "bridges": [],
        }

    existing = {(b["from"], b["to"])
                for b in ls["cross_domain_bridges"]["bridges"]}
    added = 0
    for bridge in bridges:
        key = (bridge["from"], bridge["to"])
        if key not in existing:
            ls["cross_domain_bridges"]["bridges"].append(bridge)
            existing.add(key)
            added += 1

    if added > 0:
        save_learning_state(ls)

    return added


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    print("=" * 70)
    print("  Canon × Bootstrap Multiverse")
    print("  Theory meets Practice — E₀ navigates both at once")
    print("=" * 70)

    # Phase 1: Load both landscapes
    print("\n  Phase 1: Loading landscapes...")
    cl = load_canon("ontodynamics")
    canon_ls = cl.landscape
    canon_info = cl.info
    print(f"    Canon: {len(canon_info.nodes)} nodes, {len(canon_info.edges)} edges")

    bs = load_bootstrap()
    bs_nodes = extract_nodes(bs)
    bs_edges = extract_edges(bs, bs_nodes)
    print(f"    Bootstrap: {len(bs_nodes)} nodes, {len(bs_edges)} edges")

    # Phase 2: Static bridge
    print("\n  Phase 2: Static bridge (hand-curated mapping)...")
    static_bridges = build_static_bridges(canon_info, bs_nodes)
    print(f"    Static bridges: {len(static_bridges)}")
    for b in static_bridges[:10]:
        print(f"      {b['from']:30s} → {b['to']:10s}  {b['derivation'][:50]}")
    if len(static_bridges) > 10:
        print(f"      ... and {len(static_bridges) - 10} more")

    # Phase 3: LLM semantic bridge
    if "--llm" in sys.argv:
        print("\n  Phase 3: LLM semantic bridge (discovering hidden connections)...")
        llm_bridges = llm_discover_bridges(canon_info, bs_nodes)
        print(f"    LLM bridges: {len(llm_bridges)}")
        for b in llm_bridges:
            print(f"      {b['from']:30s} → {b['to']:10s}  {b['derivation'][:60]}")
        all_bridges = static_bridges + llm_bridges
    elif "--llm-dry" in sys.argv:
        print("\n  Phase 3: LLM semantic bridge (DRY RUN)")
        llm_bridges = llm_discover_bridges(canon_info, bs_nodes, dry_run=True)
        print(f"    Would discover {len(llm_bridges)} bridge(s)")
        all_bridges = static_bridges
    else:
        print("\n  Phase 3: Skipped (use --llm for LLM bridge discovery)")
        all_bridges = static_bridges

    # Phase 4: Build unified landscape
    print("\n  Phase 4: Building unified landscape...")
    unified_nodes, unified_edges = build_unified_landscape(
        canon_info, canon_ls, bs_nodes, bs_edges, all_bridges
    )
    print(f"    Unified: {len(unified_nodes)} nodes, {len(unified_edges)} edges")
    print(f"      Canon: {sum(1 for n in unified_nodes if n.startswith('C:'))} nodes")
    print(f"      Bootstrap: {sum(1 for n in unified_nodes if n.startswith('B:'))} nodes")
    print(f"      Bridges: {len(all_bridges)} cross-domain edges")

    spec = build_spec(unified_nodes, unified_edges)
    landscape = bootstrap_landscape(spec)
    inject_node_traces(landscape, unified_nodes)

    # Phase 5: Interference measurement
    print("\n  Phase 5: Interference measurement...")
    interference = measure_interference(landscape, unified_nodes, bs_nodes)
    print(f"    From B:HERE reachable (3 hops): {interference['canon_targets'] + interference['bootstrap_targets']} nodes")
    print(f"      Canon reachable: {interference['canon_targets']}")
    print(f"      Bootstrap reachable: {interference['bootstrap_targets']}")
    print(f"      Bridge-connected: {interference['bridge_connected']}")
    print(f"      Direct neighbors: {interference['total_targets']}")
    print(f"\n    Top local neighbors by T-potential:")
    for tgt, tp in interference["top_local"]:
        label = unified_nodes.get(tgt, {}).get("label", "?")[:45]
        print(f"      {tgt:30s}  T={tp:.4f}  {label}")

    # Phase 6: Unified exploration
    print("\n  Phase 6: Unified exploration (30 steps)...")
    print("  " + "─" * 60)
    result = run_unified_exploration(landscape, unified_nodes, max_steps=30)

    for i in range(len(result["path"]) - 1):
        src = result["path"][i]
        tgt = result["path"][i + 1]
        src_d = "C" if src.startswith("C:") else "B"
        tgt_d = "C" if tgt.startswith("C:") else "B"
        crossing = "⟷" if src_d != tgt_d else " "
        tgt_label = unified_nodes.get(tgt, {}).get("label", "?")[:40]
        tgt_type = unified_nodes.get(tgt, {}).get("type", "?")
        from e0_controller.landscape import Edge as _E2
        edge = _E2(src, tgt)
        tp = transition_potential(landscape, edge) if landscape.has_edge(src, tgt) else 0
        print(f"  Step {i+1:2d}: {src:30s} → {tgt:30s} {crossing} T={tp:.3f} [{tgt_type}]")

    print(f"\n  " + "─" * 60)
    print(f"  Exploration summary:")
    print(f"    Steps:            {result['steps']}")
    print(f"    Unique states:    {result['unique_states']} / {len(unified_nodes)}")
    print(f"    Canon visited:    {result['canon_visited']}")
    print(f"    Bootstrap visited: {result['bootstrap_visited']}")
    print(f"    Domain crossings: {result['domain_crossings']}")
    print(f"    Crossing rate:    {result['crossing_rate']:.1%}")
    print(f"    Open threads:     {result['open_threads_reached']} / 3")
    if result["open_thread_names"]:
        for s in result["open_thread_names"]:
            label = unified_nodes.get(s, {}).get("label", "?")[:50]
            print(f"      ✓ {s}: {label}")

    # Phase 7: Persist
    if "--persist" in sys.argv and all_bridges:
        print("\n  Phase 7: Persisting cross-domain bridges...")
        added = persist_cross_domain_edges(all_bridges)
        print(f"    Persisted: {added} bridges to bootstrap.json")
    else:
        print(f"\n  Phase 7: Skipped (use --persist to save bridges)")

    # Summary
    print(f"\n  {'=' * 70}")
    print(f"  SUMMARY: Canon × Bootstrap Multiverse")
    print(f"  {'=' * 70}")
    print(f"""
  Canon (Ontodynamics) provides {len(canon_info.nodes)} theoretical concepts.
  Bootstrap (Project) provides {len(bs_nodes)} operational nodes.
  {len(all_bridges)} bridge edges connect theory to practice.

  Crossing rate: {result['crossing_rate']:.1%} of steps cross the domain boundary.
  This is the INTERFERENCE SIGNAL — theory informing practice and vice versa.

  The unified landscape IS E₀ seeing itself from both sides at once:
  - "What am I in theory?" (Canon)
  - "What am I in practice?" (Bootstrap)
  - "Where do they agree/disagree?" (Bridges)
""")


if __name__ == "__main__":
    main()
