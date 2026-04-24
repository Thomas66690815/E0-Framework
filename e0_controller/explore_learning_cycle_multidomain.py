"""E₀ Multi-Domain Learning Cycle (C204) — EN as third domain.

Extends C202's ASSESS → PLAN → NAVIGATE → VALIDATE → CONSOLIDATE loop
with three domains in one unified landscape:

  Canon (C:)     — Ontodynamics theory (what E₀ IS)
  Bootstrap (B:) — Project memory (what E₀ DOES)
  EN (EN:)       — English vocabulary (what E₀ can LEARN about)

The EN domain proves that E₀'s learning cycle generalizes beyond
its own self-knowledge: it can learn *any* structured domain
through the same mechanisms (Δ, R, T, historization).

Key additions over C202:
  - EN nodes integrated into unified landscape with EN: prefix
  - EN↔Canon semantic bridges (vocabulary concepts ↔ theory)
  - Per-domain coverage tracking (3 domains)
  - Cross-domain bonus biases navigation toward unexplored domains
  - Dream consolidation (optional) finds EN↔Canon equivalences

Usage:
  py -3 -m e0_controller.explore_learning_cycle_multidomain
  py -3 -m e0_controller.explore_learning_cycle_multidomain --rounds 10
  py -3 -m e0_controller.explore_learning_cycle_multidomain --persist
"""

from __future__ import annotations

import json
import os
import sys
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from e0_controller.bootstrapper import bootstrap_landscape
from e0_controller.canon_loader import load_canon, load_canon_spec
from e0_controller.communication import detect_round_intents
from e0_controller.explore_bootstrap_landscape import (
    BOOTSTRAP_PATH,
    build_spec,
    extract_edges,
    extract_nodes,
    filter_discovered_edges,
    inject_edge_metadata,
    inject_node_traces,
    load_bootstrap,
    load_learning_state,
    save_learning_state,
    local_transition_potential,
    transition_potential,
    MU,
)
from e0_controller.explore_canon_bootstrap import (
    build_static_bridges,
    build_unified_landscape,
)
from e0_controller.primitives import Edge, Outcome
from e0_controller.structural_entropy import structural_temperature


# ── EN ↔ Canon Bridges ──────────────────────────────────────────────────

# Semantic mapping: EN vocabulary concepts → Canon/Bootstrap nodes.
# These are hand-curated: the EN primitives map onto Ontodynamics concepts.
EN_CANON_BRIDGE = {
    # EN primitives → Canon primitives (same abstraction level)
    "thing":    ["C:difference"],       # "thing" = something differentiated
    "action":   ["C:local_realization"],  # "action" = local realization
    "quality":  ["C:overlap"],          # "quality" = measure of overlap
    "relation": ["C:connection"],       # "relation" = a connection

    # EN vocabulary → Canon derived concepts
    "see":      ["C:observation"],      # seeing = observing
    "hear":     ["C:observation"],      # hearing = observing
    "hand":     ["C:local_realization"],  # hand = tool for realization
    "foot":     ["C:local_realization"],  # foot = movement/realization
    "food":     ["C:resistance"],       # food = overcoming resistance (need)
    "water":    ["C:resistance"],       # water = basic need/resistance
    "self":     ["C:historization"],    # self = accumulated history
    "name":     ["C:difference"],       # name = differentiation marker
    "good":     ["C:overlap"],          # good = high overlap (desirable)
    "bad":      ["C:tension"],          # bad = high tension (undesirable)
    "big":      ["C:mass"],             # big = accumulated mass
    "small":    ["C:difference"],       # small = minimal difference

    # EN vocabulary → Bootstrap architecture
    "eye":      ["B:L8"],              # eye → observation layer
    "head":     ["B:L5"],              # head → reflexion layer
    "mouth":    ["B:L13"],             # mouth → human communication
}

# EN↔Bootstrap direct: EN learning concepts ↔ bootstrap working concepts
EN_BOOTSTRAP_BRIDGE = {
    "self":     ["B:HERE"],            # EN self ↔ current state
    "action":   ["B:L3"],              # action ↔ controller layer
    "see":      ["B:L8"],              # see ↔ observation
    "name":     ["B:L1"],              # name ↔ primitives (labels)
}


def build_en_bridges(en_info, unified_nodes) -> List[Dict]:
    """Build cross-domain bridges from EN nodes to Canon and Bootstrap.

    Each bridge is bidirectional: EN→target and target→EN.
    Delta is 0.5 (moderate — different perspectives on same concept).
    Resistance is 0.4 (moderate — requires conceptual translation).
    """
    bridges = []

    def _add(src, tgt, delta=0.5, resistance=0.4, derivation=""):
        if src in unified_nodes and tgt in unified_nodes:
            bridges.append({
                "from": src, "to": tgt,
                "delta": delta, "resistance": resistance,
                "confidence": 0.6,
                "derivation": derivation or f"EN bridge: {src} → {tgt}",
                "bridge_type": "en_semantic",
            })
            bridges.append({
                "from": tgt, "to": src,
                "delta": delta, "resistance": resistance,
                "confidence": 0.6,
                "derivation": derivation or f"EN bridge: {tgt} → {src}",
                "bridge_type": "en_semantic",
            })

    # EN→Canon bridges
    for en_concept, canon_targets in EN_CANON_BRIDGE.items():
        en_id = f"EN:{en_concept}"
        for target in canon_targets:
            _add(en_id, target, 0.5, 0.4,
                 f"EN vocabulary '{en_concept}' ↔ Canon concept {target}")

    # EN→Bootstrap bridges
    for en_concept, bs_targets in EN_BOOTSTRAP_BRIDGE.items():
        en_id = f"EN:{en_concept}"
        for target in bs_targets:
            _add(en_id, f"B:{target}" if not target.startswith("B:") else target,
                 0.4, 0.5,
                 f"EN vocabulary '{en_concept}' ↔ Bootstrap {target}")

    return bridges


# ── Data Model ──────────────────────────────────────────────────────────


@dataclass
class MultiDomainAssessment:
    """Assessment with per-domain coverage tracking."""

    total_nodes: int
    total_edges: int
    visited_nodes: int
    coverage: float
    frontier_size: int
    T_s: float
    mean_quality: float
    stale_edges: int
    # Per-domain coverage
    canon_coverage: float
    bootstrap_coverage: float
    en_coverage: float
    # Per-domain counts
    canon_nodes: int
    bootstrap_nodes: int
    en_nodes: int
    canon_visited: int
    bootstrap_visited: int
    en_visited: int
    # M: Mechanism domain (C221)
    mech_coverage: float = 0.0
    mech_nodes: int = 0
    mech_visited: int = 0


@dataclass
class MultiDomainRoundResult:
    """Result of one learning round across 4 domains."""

    round_num: int
    mode: str
    reason: str
    steps: int
    assessment_before: MultiDomainAssessment
    assessment_after: MultiDomainAssessment
    path: List[str]
    new_edges: int
    domain_crossings: int
    crossing_rate: float
    coverage_delta: float
    T_s_delta: float
    # Per-domain crossings
    en_canon_crossings: int
    en_bootstrap_crossings: int
    canon_bootstrap_crossings: int
    # C206: which edge types were traversed
    type_usage: Dict[str, int] = field(default_factory=dict)
    # C221: Mechanism crossings
    mech_canon_crossings: int = 0
    mech_bootstrap_crossings: int = 0
    mech_en_crossings: int = 0
    # C266: Community-based crossing count (≤ domain_crossings)
    community_crossings: int = 0


# ── Phase 1: ASSESS ────────────────────────────────────────────────────


def assess(landscape, unified_nodes) -> MultiDomainAssessment:
    """Compute landscape state with per-domain breakdowns."""
    hist = landscape.historization

    visited = set()
    total_abs_quality = 0.0
    stale = 0
    n_historized = 0

    for e in landscape.edges:
        load = hist.trace_load(e)
        quality = hist.trace_quality(e)
        if load > 0:
            n_historized += 1
            total_abs_quality += abs(quality)
            visited.add(e.source)
            visited.add(e.target)
            if load > 5 and abs(quality) < 0.2:
                stale += 1

    total_nodes = len(landscape.states)
    total_edges = landscape.edge_count()
    coverage = len(visited) / max(1, total_nodes)
    mean_q = total_abs_quality / max(1, n_historized)

    # Frontier
    frontier = set()
    for e in landscape.edges:
        if e.source in visited and e.target not in visited:
            tp = transition_potential(landscape, e)
            if tp > 0:
                frontier.add(e.target)

    # Per-domain coverage
    canon_all = {n for n in landscape.states if n.startswith("C:")}
    bootstrap_all = {n for n in landscape.states if n.startswith("B:")}
    en_all = {n for n in landscape.states if n.startswith("EN:")}
    mech_all = {n for n in landscape.states if n.startswith("M:")}

    canon_vis = len(visited & canon_all)
    bootstrap_vis = len(visited & bootstrap_all)
    en_vis = len(visited & en_all)
    mech_vis = len(visited & mech_all)

    T_s = structural_temperature(hist)

    return MultiDomainAssessment(
        total_nodes=total_nodes,
        total_edges=total_edges,
        visited_nodes=len(visited),
        coverage=coverage,
        frontier_size=len(frontier),
        T_s=T_s,
        mean_quality=mean_q,
        stale_edges=stale,
        canon_coverage=canon_vis / max(1, len(canon_all)),
        bootstrap_coverage=bootstrap_vis / max(1, len(bootstrap_all)),
        en_coverage=en_vis / max(1, len(en_all)),
        canon_nodes=len(canon_all),
        bootstrap_nodes=len(bootstrap_all),
        en_nodes=len(en_all),
        canon_visited=canon_vis,
        bootstrap_visited=bootstrap_vis,
        en_visited=en_vis,
        mech_coverage=mech_vis / max(1, len(mech_all)),
        mech_nodes=len(mech_all),
        mech_visited=mech_vis,
    )


# ── Phase 2: PLAN ──────────────────────────────────────────────────────


def plan(assessment: MultiDomainAssessment, round_num: int,
         history: List[MultiDomainRoundResult],
         max_steps: int = 30) -> Tuple[str, int, str]:
    """Decide round strategy. Returns (mode, steps, reason).

    New logic: if EN is significantly behind other domains, bias
    toward EN territory.
    """
    base_steps = max_steps

    # Stagnation check
    stagnation_count = 0
    for r in history[-3:]:
        if r.coverage_delta <= 0.001:
            stagnation_count += 1

    if stagnation_count >= 3:
        return ("llm", base_steps,
                f"Stagnation: {stagnation_count} consecutive rounds with no coverage increase")

    if stagnation_count >= 1 and round_num > 2:
        return ("explore", int(base_steps * 1.5),
                f"Stagnation recovery: increased budget ({stagnation_count} stalled rounds)")

    # Domain imbalance: EN significantly behind Canon or Bootstrap
    # C276: Only trigger if EN: nodes actually exist in the landscape.
    en_gap = min(assessment.canon_coverage, assessment.bootstrap_coverage) - assessment.en_coverage
    if en_gap > 0.2 and assessment.en_coverage < 0.5 and assessment.en_nodes > 0:
        return ("explore_en", int(base_steps * 1.2),
                f"EN coverage gap ({assessment.en_coverage:.0%} vs "
                f"Canon {assessment.canon_coverage:.0%}, "
                f"Bootstrap {assessment.bootstrap_coverage:.0%})")

    if assessment.coverage < 0.3:
        return ("explore", base_steps,
                f"Low coverage ({assessment.coverage:.1%}) → broad exploration")

    if assessment.T_s > MU * 2:
        return ("explore", base_steps,
                f"High T_s ({assessment.T_s:.1f}) → explore to build clarity")

    if assessment.frontier_size > 0:
        return ("explore", base_steps,
                f"Frontier of {assessment.frontier_size} unvisited nodes available")

    return ("explore", base_steps, "Default exploration round")


# ── Phase 3: NAVIGATE ──────────────────────────────────────────────────

# C206: Relation-type scoring — navigation prefers structurally informative edges.
# These are multiplicative bonuses applied to transition potential.
# Values > 1.0 attract navigation, < 1.0 repel.
RELATION_TYPE_BONUS = {
    "enables":     1.4,   # Opens new capabilities → exploration sweet spot
    "is_a":        1.3,   # Hierarchical climb → structured learning
    "part_of":     1.2,   # Decomposition → understanding structure
    "acts_on":     1.15,  # Active relationship → concrete grounding
    "agent":       1.15,  # Who/what acts → context enrichment
    "instrument":  1.1,   # Tool relationship → practical knowledge
    "co_occurs":   1.0,   # Neutral coexistence
    "located_in":  1.0,   # Spatial — neutral for abstract navigation
    "property_of": 1.0,   # Attribute — neutral
    "opposite_of": 0.85,  # Contrast — informative but risky (tension)
}

BRIDGE_TYPE_BONUS = {
    "en_semantic":  1.25,  # Cross-domain semantic bridge → highly valued
    "static":       1.15,  # Proven structural bridge → moderately valued
}


def _domain_of(node_id: str) -> str:
    """Return domain identifier from node prefix.

    Known prefixes map to canonical names; unknown prefixes use
    the prefix itself (lowercased, colon stripped).  Nodes without
    a recognised ``^[A-Z]+:`` prefix return ``'unknown'``.
    """
    if node_id.startswith("C:"):
        return "canon"
    elif node_id.startswith("B:"):
        return "bootstrap"
    elif node_id.startswith("EN:"):
        return "en"
    elif node_id.startswith("M:"):
        return "mechanism"
    elif node_id.startswith("L:"):
        return "learned"
    else:
        # Generic extraction for future / custom prefixes
        idx = node_id.find(":")
        if idx > 0 and node_id[:idx].isalpha() and node_id[:idx].isupper():
            return node_id[:idx].lower()
        return "unknown"


def community_of(node: str, communities: List[Set[str]]) -> int:
    """Return index of the community containing *node*, or -1 if not found.

    C266: Community-based crossing detection.  Two nodes cross a boundary
    when they belong to different communities (different return values).
    """
    for idx, comm in enumerate(communities):
        if node in comm:
            return idx
    return -1


def _edge_type_bonus(landscape, source: str, target: str) -> float:
    """Compute multiplicative bonus from edge metadata (C206).

    Reads relation_type and bridge_type from edge metadata.
    Returns a multiplier (1.0 = neutral, >1.0 = preferred, <1.0 = avoided).
    """
    meta = landscape.edge_meta(source, target)
    if not meta:
        return 1.0
    bonus = 1.0
    rt = meta.get("relation_type", "")
    if rt:
        bonus *= RELATION_TYPE_BONUS.get(rt, 1.0)
    bt = meta.get("bridge_type", "")
    if bt:
        bonus *= BRIDGE_TYPE_BONUS.get(bt, 1.0)
    return bonus


def _pick_start_node(landscape, unified_nodes, mode: str) -> str:
    """Pick starting node. In explore_en mode, prefer EN-adjacent nodes."""
    hist = landscape.historization

    visited = set()
    for e in landscape.edges:
        if hist.trace_load(e) > 0:
            visited.add(e.source)
            visited.add(e.target)

    if not visited:
        return "B:HERE"

    # Find frontier-adjacent visited nodes
    candidates = []
    for e in landscape.edges:
        if e.source in visited and e.target not in visited:
            tp = transition_potential(landscape, e)
            # In explore_en mode, boost EN targets
            en_bonus = 2.0 if (mode == "explore_en"
                               and e.target.startswith("EN:")) else 1.0
            candidates.append((e.source, tp * en_bonus))

    if not candidates:
        return "B:HERE"

    return max(candidates, key=lambda x: x[1])[0]


def navigate(landscape, unified_nodes, mode: str, steps: int,
             start: str = "B:HERE",
             communities: Optional[List[Set[str]]] = None) -> Dict[str, Any]:
    """Navigate with crossing tracking and exploration bonus.

    C266: When *communities* is provided, crossing detection uses community
    membership instead of prefix-based ``_domain_of()``.  Two nodes cross a
    boundary when ``community_of(src, communities) != community_of(tgt, communities)``.
    Prefix-based pair counts (en_canon, etc.) are only populated when using
    prefix mode (communities is None).
    """
    hist = landscape.historization

    globally_visited = set()
    for e in landscape.edges:
        if hist.trace_load(e) > 0:
            globally_visited.add(e.source)
            globally_visited.add(e.target)

    current = start
    path = [current]
    visited_count: Dict[str, int] = {}
    # C266: use community membership for crossing detection when available
    use_communities = communities is not None and len(communities) > 0

    # C267: warn once if falling back to prefix-based decisions
    if not use_communities:
        warnings.warn(
            "navigate() using prefix-based _domain_of for crossing detection. "
            "Pass communities= for community-based partitioning.",
            DeprecationWarning,
            stacklevel=2,
        )

    crossings = {"en_canon": 0, "en_bootstrap": 0, "canon_bootstrap": 0,
                  "mech_canon": 0, "mech_bootstrap": 0, "mech_en": 0}
    total_crossings = 0
    community_crossings = 0  # C266: community-based crossing count
    type_usage: Dict[str, int] = {}  # C206: track which edge types were chosen

    for step in range(steps):
        visited_count[current] = visited_count.get(current, 0) + 1

        potentials = local_transition_potential(
            landscape, unified_nodes, current, horizon=3
        )
        if not potentials:
            break

        # Apply exploration bonus + type-aware scoring (C206)
        scored = {}
        # C266: cross-boundary bonus uses communities when available
        if use_communities:
            cur_comm = community_of(current, communities)
        else:
            cur_domain = _domain_of(current)
        for nbr, tp in potentials.items():
            # 2× for globally unvisited
            bonus = 2.0 if nbr not in globally_visited else 1.0
            # 1.5× for cross-boundary (encourages bridge usage)
            if use_communities:
                nbr_comm = community_of(nbr, communities)
                is_crossing = cur_comm != nbr_comm
            else:
                nbr_domain = _domain_of(nbr)
                is_crossing = nbr_domain != cur_domain
            if is_crossing:
                bonus *= 1.5
            # In explore_en mode, extra bonus for EN territory (prefix = display label)
            if mode == "explore_en" and nbr.startswith("EN:"):
                bonus *= 1.3
            # C206: relation-type and bridge-type bonus
            bonus *= _edge_type_bonus(landscape, current, nbr)
            # Revisit penalty
            revisit_penalty = 1.0 / (1.0 + visited_count.get(nbr, 0))
            scored[nbr] = tp * bonus * revisit_penalty

        nbr = max(scored, key=scored.get)
        if scored[nbr] <= 0:
            break

        # C206: record which type was chosen
        meta = landscape.edge_meta(current, nbr)
        for key in ("relation_type", "bridge_type"):
            val = meta.get(key, "")
            if val:
                type_usage[val] = type_usage.get(val, 0) + 1

        # Track crossing — C266: community-based when available
        if use_communities:
            src_comm = community_of(current, communities)
            tgt_comm = community_of(nbr, communities)
            is_cross = src_comm != tgt_comm
            if is_cross:
                community_crossings += 1
            # Also track prefix crossings for backward compat reporting
            src_domain = _domain_of(current)
            tgt_domain = _domain_of(nbr)
            if src_domain != tgt_domain:
                total_crossings += 1
                pair = tuple(sorted([src_domain, tgt_domain]))
                if pair == ("canon", "en"):
                    crossings["en_canon"] += 1
                elif pair == ("bootstrap", "en"):
                    crossings["en_bootstrap"] += 1
                elif pair == ("bootstrap", "canon"):
                    crossings["canon_bootstrap"] += 1
                elif pair == ("canon", "mechanism"):
                    crossings["mech_canon"] += 1
                elif pair == ("bootstrap", "mechanism"):
                    crossings["mech_bootstrap"] += 1
                elif pair == ("en", "mechanism"):
                    crossings["mech_en"] += 1
        else:
            src_domain = _domain_of(current)
            tgt_domain = _domain_of(nbr)
            is_cross = src_domain != tgt_domain
            if is_cross:
                total_crossings += 1
                pair = tuple(sorted([src_domain, tgt_domain]))
                if pair == ("canon", "en"):
                    crossings["en_canon"] += 1
                elif pair == ("bootstrap", "en"):
                    crossings["en_bootstrap"] += 1
                elif pair == ("bootstrap", "canon"):
                    crossings["canon_bootstrap"] += 1
                elif pair == ("canon", "mechanism"):
                    crossings["mech_canon"] += 1
                elif pair == ("bootstrap", "mechanism"):
                    crossings["mech_bootstrap"] += 1
                elif pair == ("en", "mechanism"):
                    crossings["mech_en"] += 1
                community_crossings = total_crossings  # no communities → same as prefix

        # Historize with contextual inscription (C207)
        if landscape.has_edge(current, nbr):
            edge = Edge(current, nbr)
            node_info = unified_nodes.get(nbr, {})
            node_type = node_info.get("type", "")
            if node_type == "open_thread":
                outcome = Outcome.FAILURE
            elif visited_count.get(nbr, 0) > 0:
                outcome = Outcome.FAILURE
            else:
                outcome = Outcome.SUCCESS

            # C207/C266: classify traversal role using crossing flag
            rc = visited_count.get(nbr, 0)
            if is_cross:
                role = "bridge"
            elif rc > 0:
                role = "revisit"
            else:
                role = "exploration"

            # source/target domain for inscription (display, always prefix)
            src_domain_log = _domain_of(current)
            tgt_domain_log = _domain_of(nbr)

            landscape.historization.inscribe(
                edge, outcome,
                mode=mode,
                relation_type=meta.get("relation_type", ""),
                bridge_type=meta.get("bridge_type", ""),
                source_domain=src_domain_log,
                target_domain=tgt_domain_log,
                role=role,
                revisit_count=rc,
                step=step,
            )

        globally_visited.add(nbr)
        path.append(nbr)
        current = nbr

    # Shortcut edges
    new_edges = _create_shortcut_edges(landscape, unified_nodes, path)

    return {
        "path": path,
        "steps": len(path) - 1,
        "community_crossings": community_crossings,
        "domain_crossings": total_crossings,  # backward compat (prefix-based)
        "crossing_rate": community_crossings / max(1, len(path) - 1),
        "en_canon_crossings": crossings["en_canon"],
        "en_bootstrap_crossings": crossings["en_bootstrap"],
        "canon_bootstrap_crossings": crossings["canon_bootstrap"],
        "mech_canon_crossings": crossings["mech_canon"],
        "mech_bootstrap_crossings": crossings["mech_bootstrap"],
        "mech_en_crossings": crossings["mech_en"],
        "new_edges": new_edges,
        "type_usage": type_usage,
    }


def _create_shortcut_edges(landscape, unified_nodes, path) -> List[Dict]:
    """Create shortcut edges from sub-paths (same as C202)."""
    new_edges = []

    for length in range(2, min(5, len(path))):
        for i in range(len(path) - length):
            src = path[i]
            tgt = path[i + length]

            if src == tgt:
                continue
            if landscape.has_edge(src, tgt):
                continue

            deltas = []
            resistances = []
            valid = True
            for j in range(i, i + length):
                s, t = path[j], path[j + 1]
                d = landscape.difference(s, t)
                if d is None:
                    valid = False
                    break
                deltas.append(d)
                resistances.append(landscape.base_resistance(s, t))

            if not valid or not deltas:
                continue

            avg_delta = sum(deltas) / len(deltas)
            sum_resistance = sum(resistances)

            if avg_delta < 0.1:
                continue

            landscape.add_state(src)
            landscape.add_state(tgt)
            landscape.add_edge(src, tgt, avg_delta, sum_resistance)

            derivation_path = " → ".join(path[i:i + length + 1])
            new_edges.append({
                "from": src,
                "to": tgt,
                "delta": round(avg_delta, 3),
                "resistance": round(sum_resistance, 3),
                "confidence": 0.5,
                "derivation": f"shortcut ({length}-hop): {derivation_path}",
            })

    return new_edges


# ── Phase 4-5: VALIDATE + CONSOLIDATE ──────────────────────────────────


def validate_confidence(path) -> Dict[Tuple[str, str], float]:
    """Update confidence of discovered edges based on path usage."""
    ls = load_learning_state()

    disc = ls.get("discovered_edges", {}).get("edges", [])
    if not disc:
        return {}

    traversed = set()
    for i in range(len(path) - 1):
        traversed.add((path[i], path[i + 1]))

    updates = {}
    for edge_info in disc:
        key = (edge_info["from"], edge_info["to"])
        old_conf = edge_info.get("confidence", 0.5)
        if key in traversed:
            new_conf = min(1.0, old_conf + 0.1)
        else:
            new_conf = max(0.0, old_conf - 0.02)
        new_conf = round(new_conf, 3)
        if new_conf != old_conf:
            edge_info["confidence"] = new_conf
            updates[key] = new_conf

    return updates


def consolidate(round_result: MultiDomainRoundResult, new_edges: List[Dict],
                dry_run: bool = False,
                universe: str = "main") -> Dict[str, Any]:
    """Write round results to learning_state.json.

    *universe* tags each persisted edge and history entry so that
    multi-universe sessions (C246) can reload without cross-contamination.
    """
    if dry_run:
        return {
            "new_edges_would_persist": len(new_edges),
            "round_recorded": False,
            "dry_run": True,
        }

    ls = load_learning_state()

    # Persist new shortcut edges
    if "discovered_edges" not in ls:
        ls["discovered_edges"] = {
            "_comment": "Edges discovered through E₀ self-navigation.",
            "edges": [],
        }

    existing = {(e["from"], e["to"]) for e in ls["discovered_edges"]["edges"]}
    added = 0
    for edge in new_edges:
        key = (edge["from"], edge["to"])
        if key not in existing:
            tagged = dict(edge, universe=universe)
            ls["discovered_edges"]["edges"].append(tagged)
            existing.add(key)
            added += 1

    # Persist multi-domain learning history
    if "multidomain_history" not in ls:
        ls["multidomain_history"] = {
            "_comment": "Multi-domain learning cycle metrics (C204).",
            "rounds": [],
        }

    a = round_result.assessment_after
    history_entry = {
        "round": round_result.round_num,
        "mode": round_result.mode,
        "reason": round_result.reason,
        "steps": round_result.steps,
        "coverage": round(a.coverage, 4),
        "coverage_delta": round(round_result.coverage_delta, 4),
        "T_s": round(a.T_s, 3),
        "T_s_delta": round(round_result.T_s_delta, 3),
        "new_edges": round_result.new_edges,
        "domain_crossings": round_result.domain_crossings,
        "en_canon_crossings": round_result.en_canon_crossings,
        "en_bootstrap_crossings": round_result.en_bootstrap_crossings,
        "canon_bootstrap_crossings": round_result.canon_bootstrap_crossings,
        "mech_canon_crossings": round_result.mech_canon_crossings,
        "mech_bootstrap_crossings": round_result.mech_bootstrap_crossings,
        "mech_en_crossings": round_result.mech_en_crossings,
        "canon_coverage": round(a.canon_coverage, 4),
        "bootstrap_coverage": round(a.bootstrap_coverage, 4),
        "en_coverage": round(a.en_coverage, 4),
        "mech_coverage": round(a.mech_coverage, 4),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "universe": universe,
    }
    ls["multidomain_history"]["rounds"].append(history_entry)

    save_learning_state(ls)

    return {
        "new_edges_persisted": added,
        "round_recorded": True,
        "total_discovered": len(ls["discovered_edges"]["edges"]),
    }


# ── M: ↔ Canon Bridges ─────────────────────────────────────────────────

# Mechanism nodes → Canon theory concepts they implement.
# Each mechanism IS the implementation of one or more Canon concepts.
MECH_CANON_BRIDGE = {
    "historization_engine":      ["C:historization", "C:trace_quality", "C:trace_load"],
    "greedy_navigation":         ["C:greedy_navigation", "C:tension"],
    "amplitude_overlay":         ["C:amplitude_override", "C:born_sampling"],
    "escalation":                ["C:escalation"],
    "overlap_modulation":        ["C:overlap_modulation"],
    "inertia_modulation":        ["C:inertia_modulation"],
    "reflexive_edge_proposal":   ["C:reflexion_reactive", "C:reflexion_proactive"],
    "self_graph":                ["C:self_graph"],
    "dual_reflection":           ["C:reflexivity"],
    "auto_tuning":               ["C:auto_tuning"],
    "multiverse":                ["C:multiverse", "C:novelty_gate"],
    "coupling_router":           ["C:coupling_router", "C:asymmetric_coupling"],
    "cross_reflexion":           ["C:cross_reflexion", "C:scoped_reflexion"],
    "dream_mode":                ["C:dream_mode", "C:edge_fingerprint",
                                  "C:functional_equivalence", "C:bridge_hypothesis"],
    "structural_entropy":        ["C:structural_temperature", "C:inscription_threshold",
                                  "C:anchor_analysis", "C:structural_decay"],
    "sleep_wake_cycle":          ["C:sleep_wake_cycle", "C:dream_pressure"],
    "perception_ontology":       ["C:perception_ontology"],
    "communication_intent":      ["C:communication_intent"],
    "observation_landscape":     ["C:observation"],
    "curriculum_navigator":      ["C:curriculum_navigator"],
}

# Mechanism nodes → Bootstrap items they relate to.
MECH_BOOTSTRAP_BRIDGE = {
    "historization_engine":      ["B:WP-1"],   # "Historization is dominant"
    "greedy_navigation":         ["B:L4"],     # Controller layer
    "amplitude_overlay":         ["B:GT-5"],   # Amplitude Override Trap
    "escalation":                ["B:L4"],     # Controller layer
    "reflexive_edge_proposal":   ["B:GT-3"],   # Greedy Matching Trap → reflexion solved it
    "self_graph":                ["B:L5"],     # Reflexion layer
    "dual_reflection":           ["B:L5"],     # Reflexion layer
    "auto_tuning":               ["B:L7"],     # Infrastructure layer
    "multiverse":                ["B:GT-1"],   # Isolated Agents Trap
    "coupling_router":           ["B:L6"],     # Multi-System layer
    "cross_reflexion":           ["B:L6"],     # Multi-System layer
    "dream_mode":                ["B:BT-4", "B:L9"],  # Dual Nature breakthrough + Dream layer
    "structural_entropy":        ["B:L10"],    # Structural Entropy layer
    "sleep_wake_cycle":          ["B:L11"],    # Sleep-Wake layer
    "perception_ontology":       ["B:L12"],    # Human Communication layer
    "communication_intent":      ["B:L12"],    # Human Communication layer
    "observation_landscape":     ["B:L8"],     # Observation layer
    "curriculum_navigator":      ["B:L7"],     # Infrastructure layer
}


def build_mech_bridges(mech_info, unified_nodes) -> List[Dict]:
    """Build cross-domain bridges from M: nodes to Canon and Bootstrap.

    Each bridge is bidirectional: M:x → C:y and C:y → M:x.
    """
    bridges = []

    def _add(src, tgt, delta=0.4, resistance=0.3, derivation=""):
        if src in unified_nodes and tgt in unified_nodes:
            bridges.append({
                "from": src, "to": tgt,
                "delta": delta, "resistance": resistance,
                "confidence": 0.7,
                "derivation": derivation or f"Mechanism bridge: {src} → {tgt}",
                "bridge_type": "mech_semantic",
            })
            bridges.append({
                "from": tgt, "to": src,
                "delta": delta, "resistance": resistance,
                "confidence": 0.7,
                "derivation": derivation or f"Mechanism bridge: {tgt} → {src}",
                "bridge_type": "mech_semantic",
            })

    # M: → C: bridges
    for mech_id, canon_targets in MECH_CANON_BRIDGE.items():
        m_id = f"M:{mech_id}"
        for target in canon_targets:
            _add(m_id, target, 0.4, 0.3,
                 f"Mechanism '{mech_id}' implements Canon concept {target}")

    # M: → B: bridges
    for mech_id, bs_targets in MECH_BOOTSTRAP_BRIDGE.items():
        m_id = f"M:{mech_id}"
        for target in bs_targets:
            tgt = target if target.startswith("B:") else f"B:{target}"
            _add(m_id, tgt, 0.5, 0.4,
                 f"Mechanism '{mech_id}' relates to Bootstrap {target}")

    return bridges


# ── Landscape Construction ──────────────────────────────────────────────


def build_multidomain_landscape(fresh_en: bool = True, fresh_canon: bool = True,
                                fresh_mech: bool = True,
                                include_en: bool = False,
                                ) -> Tuple[Any, Dict, Dict[str, int]]:
    """Build unified Canon + Bootstrap + (optional EN) + Mechanism landscape.

    C263: Default changed from include_en=True to include_en=False.
    Cold start now matches warm start (C+B+M only). EN available as opt-in.

    Domains:
    - Canon (C:): Ontodynamics theory — what E₀ IS
    - Bootstrap (B:): Project memory — what E₀ DOES
    - Mechanism (M:): Functional subsystems — HOW E₀ works
    - EN (EN:): English vocabulary — optional, for language tasks

    Returns (landscape, unified_nodes, stats).
    """
    # Load Canon + Bootstrap (same as C202)
    cl = load_canon("ontodynamics")
    bs = load_bootstrap()
    bs_nodes = extract_nodes(bs)
    bs_edges = extract_edges(bs, bs_nodes)

    # Build Canon↔Bootstrap bridges (C200 infrastructure)
    cb_bridges = build_static_bridges(cl.info, bs_nodes)

    # Build Canon+Bootstrap unified base
    unified_nodes, unified_edges = build_unified_landscape(
        cl.info, cl.landscape, bs_nodes, bs_edges, cb_bridges,
    )

    # EN domain — optional (C223: skip for self-knowledge seed)
    en_node_count = 0
    en_bridges: List[Dict] = []
    if include_en:
        en = load_canon("english_basic_enriched")

        # Add EN nodes with EN: prefix
        for n in en.info.nodes:
            nid = f"EN:{n.id}"
            unified_nodes[nid] = {
                "type": "en_vocabulary",
                "label": n.description[:60] if n.description else n.id,
                "description": n.description or "",
                "derivation_level": n.derivation_level,
                "is_primitive": n.is_primitive,
                "domain": "en",
                "U": 0.0 if fresh_en else 1.0,
                "F": 0.0,
            }
            en_node_count += 1

        # Add EN intra-domain edges (with relation type from raw spec)
        en_spec = load_canon_spec("english_basic_enriched")
        en_edge_types = {}
        for e in en_spec.get("edges", []):
            en_edge_types[(e["from"], e["to"])] = e.get("type", "")
        for edge_info in en.info.edges:
            edge_dict = {
                "from": f"EN:{edge_info.source}",
                "to": f"EN:{edge_info.target}",
                "delta": 0.3,
                "resistance": 0.2,
                "confidence": 0.9,
                "derivation": f"EN intra: {edge_info.derivation}",
            }
            rtype = en_edge_types.get((edge_info.source, edge_info.target), "")
            if rtype:
                edge_dict["relation_type"] = rtype
            unified_edges.append(edge_dict)

        # Build EN↔Canon and EN↔Bootstrap bridges
        en_bridges = build_en_bridges(en.info, unified_nodes)
        unified_edges.extend(en_bridges)

    # ── M: Mechanism domain (C221) ──────────────────────────────────────
    mech = load_canon("mechanism_e0")
    mech_node_count = 0
    for n in mech.info.nodes:
        nid = f"M:{n.id}"
        unified_nodes[nid] = {
            "type": "mechanism",
            "label": n.description[:60] if n.description else n.id,
            "description": n.description or "",
            "derivation_level": n.derivation_level,
            "is_primitive": n.is_primitive,
            "domain": "mechanism",
            "U": 0.0 if fresh_mech else 1.0,
            "F": 0.0,
        }
        mech_node_count += 1

    # Mechanism intra-domain edges (with relation type from spec)
    mech_edge_count = 0
    mech_spec = load_canon_spec("mechanism_e0")
    mech_edge_types = {}
    for e in mech_spec.get("edges", []):
        mech_edge_types[(e["from"], e["to"])] = e.get("type", "")
    for edge_info in mech.info.edges:
        edge_dict = {
            "from": f"M:{edge_info.source}",
            "to": f"M:{edge_info.target}",
            "delta": 0.3,
            "resistance": 0.2,
            "confidence": 0.9,
            "derivation": f"M intra: {edge_info.derivation}",
        }
        rtype = mech_edge_types.get((edge_info.source, edge_info.target), "")
        if rtype:
            edge_dict["relation_type"] = rtype
        unified_edges.append(edge_dict)
        mech_edge_count += 1

    # Mechanism↔Canon and Mechanism↔Bootstrap bridges
    mech_bridges = build_mech_bridges(mech.info, unified_nodes)
    unified_edges.extend(mech_bridges)

    # Zero Canon traces for fresh exploration
    if fresh_canon:
        for nid in unified_nodes:
            if nid.startswith("C:"):
                unified_nodes[nid]["U"] = 0.0
                unified_nodes[nid]["F"] = 0.0

    # Build landscape
    spec = build_spec(unified_nodes, unified_edges)
    landscape = bootstrap_landscape(spec)
    inject_node_traces(landscape, unified_nodes)
    inject_edge_metadata(landscape, unified_edges)

    stats = {
        "canon_nodes": sum(1 for n in unified_nodes if n.startswith("C:")),
        "bootstrap_nodes": sum(1 for n in unified_nodes if n.startswith("B:")),
        "en_nodes": en_node_count,
        "mech_nodes": mech_node_count,
        "total_nodes": len(unified_nodes),
        "canon_bootstrap_bridges": len(cb_bridges),
        "en_bridges": len(en_bridges),
        "mech_bridges": len(mech_bridges),
        "total_edges": len(unified_edges),
    }

    return landscape, unified_nodes, stats


# ── Communication (C212) ───────────────────────────────────────────────


def communicate_round(
    result: MultiDomainRoundResult,
    landscape,
    stagnation_count: int = 0,
    output_format: str = "text",
) -> str:
    """Generate communication output for a single learning round.

    Translates round results through the full communication pipeline:
    detect_round_intents → emit_ui_spec → render (text or markdown).

    Returns the rendered output string.
    """
    from e0_controller.ui_emitter import emit_ui_spec
    from e0_controller.text_renderer import render_text, render_markdown
    from e0_controller.evidence_interpreter import interpret_panel

    a_before = result.assessment_before
    a_after = result.assessment_after

    stats = landscape.historization.inscription_stats()

    report = detect_round_intents(
        round_num=result.round_num,
        mode=result.mode,
        reason=result.reason,
        steps=result.steps,
        coverage_before=a_before.coverage,
        coverage_after=a_after.coverage,
        coverage_delta=result.coverage_delta,
        T_s_before=a_before.T_s,
        T_s_after=a_after.T_s,
        domain_crossings=result.domain_crossings,
        crossing_rate=result.crossing_rate,
        canon_coverage=a_after.canon_coverage,
        bootstrap_coverage=a_after.bootstrap_coverage,
        en_coverage=a_after.en_coverage,
        new_edges=result.new_edges,
        total_nodes=a_after.total_nodes,
        visited_nodes=a_after.visited_nodes,
        en_canon_crossings=result.en_canon_crossings,
        en_bootstrap_crossings=result.en_bootstrap_crossings,
        canon_bootstrap_crossings=result.canon_bootstrap_crossings,
        stagnation_count=stagnation_count,
        inscription_stats=stats,
        canon_nodes=a_after.canon_nodes,
        bootstrap_nodes=a_after.bootstrap_nodes,
        en_nodes=a_after.en_nodes,
    )

    spec = emit_ui_spec(
        report,
        context=f"Learning Cycle Round {result.round_num}: {result.mode}",
    )

    title = f"E₀ Learning Cycle — Round {result.round_num}"

    if output_format == "markdown":
        text = render_markdown(spec, title=title)
    else:
        text = render_text(spec, title=title)

    # Append interpretations
    interp_parts = []
    sep = "\n## Interpretations\n" if output_format == "markdown" else "\n--- Interpretations ---"
    interp_parts.append(sep)
    for panel in spec.panels:
        if output_format == "markdown":
            interp_parts.append(f"### {panel.label}\n")
        interp_parts.append(interpret_panel(panel))
    text += "\n".join(interp_parts)

    return text


def communicate_summary(
    history: List[MultiDomainRoundResult],
    landscape,
    output_format: str = "text",
) -> str:
    """Generate communication output for the full learning cycle summary.

    Aggregates all rounds into a single IntentReport and renders it.
    """
    from e0_controller.ui_emitter import emit_ui_spec
    from e0_controller.text_renderer import render_text, render_markdown
    from e0_controller.evidence_interpreter import (
        interpret_panel,
        interpret_inscription_stats,
        interpret_domain_crossings,
    )

    if not history:
        return ""

    first = history[0].assessment_before
    last = history[-1].assessment_after

    # Aggregate crossings
    total_crossings = sum(r.domain_crossings for r in history)
    total_en_canon = sum(r.en_canon_crossings for r in history)
    total_en_bs = sum(r.en_bootstrap_crossings for r in history)
    total_cb = sum(r.canon_bootstrap_crossings for r in history)
    total_steps = sum(r.steps for r in history)
    total_new_edges = sum(r.new_edges for r in history)

    r_before = 1.0 - first.coverage
    r_after = 1.0 - last.coverage
    drop_pct = (r_before - r_after) / r_before if r_before > 0 else 0.0

    report = detect_round_intents(
        round_num=len(history),
        mode="summary",
        reason=f"{len(history)} rounds completed",
        steps=total_steps,
        coverage_before=first.coverage,
        coverage_after=last.coverage,
        coverage_delta=last.coverage - first.coverage,
        T_s_before=first.T_s,
        T_s_after=last.T_s,
        domain_crossings=total_crossings,
        crossing_rate=total_crossings / max(1, total_steps),
        canon_coverage=last.canon_coverage,
        bootstrap_coverage=last.bootstrap_coverage,
        en_coverage=last.en_coverage,
        new_edges=total_new_edges,
        total_nodes=last.total_nodes,
        visited_nodes=last.visited_nodes,
        en_canon_crossings=total_en_canon,
        en_bootstrap_crossings=total_en_bs,
        canon_bootstrap_crossings=total_cb,
        stagnation_count=0,
        canon_nodes=last.canon_nodes,
        bootstrap_nodes=last.bootstrap_nodes,
        en_nodes=last.en_nodes,
    )

    spec = emit_ui_spec(
        report,
        context=f"Learning Cycle Summary — {len(history)} rounds",
    )

    title = f"E₀ Learning Cycle Summary ({len(history)} rounds)"

    if output_format == "markdown":
        text = render_markdown(spec, title=title)
    else:
        text = render_text(spec, title=title)

    # Append interpretations + inscription stats + crossing narrative
    parts = []
    sep = "\n## Interpretations\n" if output_format == "markdown" else "\n--- Interpretations ---"
    parts.append(sep)
    for panel in spec.panels:
        if output_format == "markdown":
            parts.append(f"### {panel.label}\n")
        parts.append(interpret_panel(panel))

    stats = landscape.historization.inscription_stats()
    if stats.get("total_inscriptions", 0) > 0:
        sep2 = "\n## Inscription Analysis\n" if output_format == "markdown" else "\n--- Inscription Analysis ---"
        parts.append(sep2)
        parts.append(interpret_inscription_stats(stats))

    crossings_data = {
        "en_canon": total_en_canon,
        "en_bootstrap": total_en_bs,
        "canon_bootstrap": total_cb,
        "total": total_crossings,
        "steps": total_steps,
    }
    crossing_text = interpret_domain_crossings(crossings_data)
    if crossing_text:
        sep3 = "\n## Domain Crossings\n" if output_format == "markdown" else "\n--- Domain Crossings ---"
        parts.append(sep3)
        parts.append(crossing_text)

    text += "\n".join(parts)
    return text


# ── Outer Loop ──────────────────────────────────────────────────────────


def run_multidomain_cycle(
    max_rounds: int = 8,
    steps_per_round: int = 40,
    persist: bool = False,
    verbose: bool = True,
    output_format: Optional[str] = None,
) -> List[MultiDomainRoundResult]:
    """Run iterative learning across Canon + Bootstrap + EN.

    Landscape is built ONCE — traces accumulate across rounds.
    Each round's navigation enriches the shared historization.
    Cross-domain bridges allow knowledge transfer: Canon insights
    help Bootstrap navigation, EN vocabulary connects to both.

    Args:
        output_format: If "text" or "markdown", each round and the
            summary produce communication output through the full
            pipeline (detect_round_intents → emit_ui_spec → render).
            If None, only verbose print output (legacy behavior).

    Returns list of MultiDomainRoundResult.
    """
    history: List[MultiDomainRoundResult] = []
    stagnation_streak = 0

    # Build landscape ONCE
    landscape, unified_nodes, stats = build_multidomain_landscape(include_en=True)

    if verbose:
        print(f"\n{'=' * 65}")
        print(f"  E₀ MULTI-DOMAIN LEARNING CYCLE (C204)")
        print(f"{'=' * 65}")
        print(f"  Canon:     {stats['canon_nodes']} nodes")
        print(f"  Bootstrap: {stats['bootstrap_nodes']} nodes")
        print(f"  EN:        {stats['en_nodes']} nodes")
        print(f"  Total:     {stats['total_nodes']} nodes, {stats['total_edges']} edges")
        print(f"  Bridges:   {stats['canon_bootstrap_bridges']} Canon↔Bootstrap, "
              f"{stats['en_bridges']} EN↔(Canon+Bootstrap)")

    for round_num in range(1, max_rounds + 1):

        # Phase 1: ASSESS
        a_before = assess(landscape, unified_nodes)

        if verbose:
            print(f"\n{'─' * 65}")
            print(f"  Round {round_num}/{max_rounds}")
            print(f"{'─' * 65}")
            print(f"  Coverage:   {a_before.coverage:.1%} "
                  f"({a_before.visited_nodes}/{a_before.total_nodes})")
            print(f"  T_s:        {a_before.T_s:.3f}")
            print(f"  Frontier:   {a_before.frontier_size} unvisited nodes")
            print(f"  Canon:      {a_before.canon_coverage:.1%} "
                  f"({a_before.canon_visited}/{a_before.canon_nodes})")
            print(f"  Bootstrap:  {a_before.bootstrap_coverage:.1%} "
                  f"({a_before.bootstrap_visited}/{a_before.bootstrap_nodes})")
            print(f"  EN:         {a_before.en_coverage:.1%} "
                  f"({a_before.en_visited}/{a_before.en_nodes})")

        # Termination: no frontier and high coverage
        if a_before.frontier_size == 0 and a_before.coverage > 0.9:
            if verbose:
                print(f"\n  ✓ Structural saturation: no frontier, "
                      f"coverage={a_before.coverage:.1%}")
            break

        # Phase 2: PLAN
        mode, steps, reason = plan(a_before, round_num, history, steps_per_round)

        if verbose:
            print(f"  Plan:       {mode} ({steps} steps)")
            print(f"  Reason:     {reason}")

        # Phase 3: NAVIGATE
        start_node = _pick_start_node(landscape, unified_nodes, mode)
        nav = navigate(landscape, unified_nodes, mode, steps, start=start_node)

        if verbose:
            print(f"\n  Navigation (start={start_node}):")
            print(f"    Steps:        {nav['steps']}")
            print(f"    Crossings:    {nav['domain_crossings']} total "
                  f"({nav['crossing_rate']:.0%})")
            print(f"    EN↔Canon:     {nav['en_canon_crossings']}")
            print(f"    EN↔Bootstrap: {nav['en_bootstrap_crossings']}")
            print(f"    C↔B:          {nav['canon_bootstrap_crossings']}")
            print(f"    M↔Canon:      {nav['mech_canon_crossings']}")
            print(f"    M↔Bootstrap:  {nav['mech_bootstrap_crossings']}")
            print(f"    M↔EN:         {nav['mech_en_crossings']}")
            print(f"    New edges:    {len(nav['new_edges'])}")

        # Phase 4: VALIDATE
        conf_updates = validate_confidence(nav["path"])

        # Phase 5: CONSOLIDATE
        a_after = assess(landscape, unified_nodes)
        coverage_delta = a_after.coverage - a_before.coverage
        T_s_delta = a_after.T_s - a_before.T_s

        result = MultiDomainRoundResult(
            round_num=round_num,
            mode=mode,
            reason=reason,
            steps=nav["steps"],
            assessment_before=a_before,
            assessment_after=a_after,
            path=nav["path"],
            new_edges=len(nav["new_edges"]),
            domain_crossings=nav["domain_crossings"],
            crossing_rate=nav["crossing_rate"],
            coverage_delta=coverage_delta,
            T_s_delta=T_s_delta,
            en_canon_crossings=nav["en_canon_crossings"],
            en_bootstrap_crossings=nav["en_bootstrap_crossings"],
            canon_bootstrap_crossings=nav["canon_bootstrap_crossings"],
            type_usage=nav.get("type_usage", {}),
            mech_canon_crossings=nav.get("mech_canon_crossings", 0),
            mech_bootstrap_crossings=nav.get("mech_bootstrap_crossings", 0),
            mech_en_crossings=nav.get("mech_en_crossings", 0),
        )
        history.append(result)

        if verbose:
            print(f"\n  After round {round_num}:")
            print(f"    Coverage:   {a_after.coverage:.1%} "
                  f"(Δ={coverage_delta:+.1%})")
            print(f"    T_s:        {a_after.T_s:.3f} "
                  f"(Δ={T_s_delta:+.3f})")
            print(f"    Canon:      {a_after.canon_coverage:.1%}")
            print(f"    Bootstrap:  {a_after.bootstrap_coverage:.1%}")
            print(f"    EN:         {a_after.en_coverage:.1%}")

        if persist:
            consolidation = consolidate(result, nav["new_edges"])
            if verbose:
                print(f"    Persisted:  {consolidation['new_edges_persisted']} new edges")
        else:
            consolidate(result, nav["new_edges"], dry_run=True)

        # Stagnation tracking
        if coverage_delta <= 0.001:
            stagnation_streak += 1
        else:
            stagnation_streak = 0

        if stagnation_streak >= 3:
            if verbose:
                print(f"\n  ⚠ Stagnation: {stagnation_streak} rounds with no progress")

        # Communication output per round (C212)
        if output_format in ("text", "markdown"):
            round_text = communicate_round(
                result, landscape,
                stagnation_count=stagnation_streak,
                output_format=output_format,
            )
            print(round_text)

    # Summary
    if verbose and history:
        _print_summary(history, landscape)

    # Communication summary (C212)
    if output_format in ("text", "markdown") and history:
        summary_text = communicate_summary(
            history, landscape, output_format=output_format,
        )
        print(summary_text)

    return history


def _print_summary(history: List[MultiDomainRoundResult],
                   landscape=None) -> None:
    """Print multi-domain learning cycle summary."""
    print(f"\n{'=' * 65}")
    print(f"  MULTI-DOMAIN LEARNING CYCLE SUMMARY")
    print(f"{'=' * 65}")

    total_steps = sum(r.steps for r in history)
    total_new_edges = sum(r.new_edges for r in history)
    total_crossings = sum(r.domain_crossings for r in history)
    total_en_canon = sum(r.en_canon_crossings for r in history)
    total_en_bs = sum(r.en_bootstrap_crossings for r in history)
    total_cb = sum(r.canon_bootstrap_crossings for r in history)
    total_mc = sum(r.mech_canon_crossings for r in history)
    total_mb = sum(r.mech_bootstrap_crossings for r in history)
    total_me = sum(r.mech_en_crossings for r in history)

    first = history[0].assessment_before
    last = history[-1].assessment_after

    print(f"  Rounds:         {len(history)}")
    print(f"  Total steps:    {total_steps}")
    print(f"  Total new edges:{total_new_edges}")
    print(f"  Total crossings:{total_crossings}")
    print(f"    EN↔Canon:     {total_en_canon}")
    print(f"    EN↔Bootstrap: {total_en_bs}")
    print(f"    Canon↔Boot:   {total_cb}")
    print(f"    M↔Canon:      {total_mc}")
    print(f"    M↔Bootstrap:  {total_mb}")
    print(f"    M↔EN:         {total_me}")
    print()
    print(f"  Coverage:       {first.coverage:.1%} → {last.coverage:.1%} "
          f"(Δ={last.coverage - first.coverage:+.1%})")
    print(f"  T_s:            {first.T_s:.3f} → {last.T_s:.3f}")
    print(f"  Canon:          {first.canon_coverage:.1%} → {last.canon_coverage:.1%}")
    print(f"  Bootstrap:      {first.bootstrap_coverage:.1%} → {last.bootstrap_coverage:.1%}")
    print(f"  EN:             {first.en_coverage:.1%} → {last.en_coverage:.1%}")
    print(f"  Mechanism:      {first.mech_coverage:.1%} → {last.mech_coverage:.1%}")

    print(f"\n  Round-by-round:")
    print(f"  {'#':>3} {'Mode':>10} {'Stps':>5} {'Cov':>6} {'ΔCov':>6} "
          f"{'T_s':>6} {'Canon':>6} {'Boot':>6} {'EN':>6} {'X':>4}")
    print(f"  {'─' * 62}")
    for r in history:
        a = r.assessment_after
        print(f"  {r.round_num:3d} {r.mode:>10} {r.steps:5d} "
              f"{a.coverage:6.1%} {r.coverage_delta:+6.1%} "
              f"{a.T_s:6.3f} {a.canon_coverage:6.1%} "
              f"{a.bootstrap_coverage:6.1%} {a.en_coverage:6.1%} "
              f"{r.domain_crossings:4d}")

    # C206: Aggregate type usage across all rounds
    agg_types: Dict[str, int] = {}
    for r in history:
        for t, c in r.type_usage.items():
            agg_types[t] = agg_types.get(t, 0) + c
    if agg_types:
        print(f"\n  Edge types traversed (C206):")
        for t, c in sorted(agg_types.items(), key=lambda x: -x[1]):
            print(f"    {t:20s} {c:4d}")

    # C207: Contextual inscription stats
    if landscape is not None:
        stats = landscape.historization.inscription_stats()
        if stats["total_inscriptions"] > 0:
            print(f"\n  Contextual Inscription (C207):")
            print(f"    Total inscriptions: {stats['total_inscriptions']}")
            print(f"    Inscribed edges:    {stats['inscribed_edges']}")
            print(f"    Domain crossings:   {stats['domain_crossing_count']}")
            if stats["role_totals"]:
                print(f"    Roles:")
                for role, c in sorted(stats["role_totals"].items(), key=lambda x: -x[1]):
                    print(f"      {role:20s} {c:4d}")
            if stats["mode_totals"]:
                print(f"    Modes:")
                for m, c in sorted(stats["mode_totals"].items(), key=lambda x: -x[1]):
                    print(f"      {m:20s} {c:4d}")

    print(f"{'=' * 65}")


# ── CLI ─────────────────────────────────────────────────────────────────


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="E₀ Multi-Domain Learning Cycle (C204)")
    parser.add_argument("--rounds", type=int, default=8,
                        help="Maximum rounds (default: 8)")
    parser.add_argument("--steps", type=int, default=40,
                        help="Steps per round (default: 40)")
    parser.add_argument("--persist", action="store_true",
                        help="Write results to learning_state.json")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress progress output")
    parser.add_argument("--format", dest="fmt", default=None,
                        choices=["text", "markdown", "md"],
                        help="Communication output format (text or markdown)")
    args = parser.parse_args()

    fmt = args.fmt
    if fmt == "md":
        fmt = "markdown"

    run_multidomain_cycle(
        max_rounds=args.rounds,
        steps_per_round=args.steps,
        persist=args.persist,
        verbose=not args.quiet,
        output_format=fmt,
    )


if __name__ == "__main__":
    main()
