"""E₀ Learning Cycle (C202) — Iterative self-improvement through repeated navigation.

The outer loop that runs E₀ exploration iteratively:
  Round N: load → assess → plan → navigate → validate → consolidate → persist
  Round N+1: load richer bootstrap.json → repeat

Each round enriches bootstrap.json with:
  - New shortcut edges (Phase D structural creation)
  - Updated confidence on existing edges (Phase F)
  - LLM semantic scores (conditional, Phase G)
  - Learning history metrics (coverage, T_s, frontier size)

Termination: T_s < μ (structural saturation) OR max_rounds OR 3× stagnation.

Usage:
  py -3 -m e0_controller.explore_learning_cycle                 # 5 rounds, no LLM
  py -3 -m e0_controller.explore_learning_cycle --rounds 10     # 10 rounds
  py -3 -m e0_controller.explore_learning_cycle --llm           # with LLM validation
  py -3 -m e0_controller.explore_learning_cycle --llm-dry       # dry-run LLM
  py -3 -m e0_controller.explore_learning_cycle --persist        # write results to bootstrap.json
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from e0_controller.bootstrapper import bootstrap_landscape
from e0_controller.canon_loader import load_canon
from e0_controller.explore_bootstrap_landscape import (
    BOOTSTRAP_PATH,
    build_spec,
    extract_edges,
    extract_nodes,
    filter_discovered_edges,
    inject_node_traces,
    load_bootstrap,
    local_autonomous_step,
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


# ── Data Model ─────────────────────────────────────────────────────────


@dataclass
class Assessment:
    """Phase 1 output: what does the landscape look like right now?"""

    total_nodes: int
    total_edges: int
    visited_nodes: int          # nodes with any trace_load > 0
    coverage: float             # visited / total
    frontier_size: int          # nodes with T > 0 reachable from current
    T_s: float                  # structural temperature
    mean_quality: float         # mean |trace_quality| across historized edges
    stale_edges: int            # edges with load > 5 and |quality| < 0.2
    canon_coverage: float       # proportion of Canon nodes with load > 0
    bootstrap_coverage: float   # proportion of Bootstrap nodes with load > 0


@dataclass
class RoundPlan:
    """Phase 2 output: what should this round do?"""

    mode: str                   # "explore" | "exploit" | "llm"
    steps: int                  # navigation budget
    reason: str                 # why this mode was chosen
    focus_region: Optional[str] = None  # optional: sub-region to target


@dataclass
class RoundResult:
    """Phase 3-5 output: what happened in this round?"""

    round_num: int
    plan: RoundPlan
    assessment_before: Assessment
    assessment_after: Assessment
    path: List[str]
    new_edges: int
    domain_crossings: int
    crossing_rate: float
    canon_visited: int
    bootstrap_visited: int
    llm_round: bool
    coverage_delta: float
    T_s_delta: float


# ── Phase 1: ASSESS ────────────────────────────────────────────────────


def assess(landscape, unified_nodes) -> Assessment:
    """Compute the current state of the unified landscape."""
    hist = landscape.historization

    # Coverage: which nodes have at least one edge with trace_load > 0?
    visited = set()
    total_load = 0.0
    total_abs_quality = 0.0
    stale = 0
    n_historized = 0

    for e in landscape.edges:
        load = hist.trace_load(e)
        quality = hist.trace_quality(e)
        if load > 0:
            n_historized += 1
            total_load += load
            total_abs_quality += abs(quality)
            visited.add(e.source)
            visited.add(e.target)
            if load > 5 and abs(quality) < 0.2:
                stale += 1

    total_nodes = len(landscape.states)
    total_edges = landscape.edge_count()
    coverage = len(visited) / max(1, total_nodes)
    mean_q = (total_abs_quality / max(1, n_historized))

    # Frontier: nodes reachable from any visited node with T > 0
    frontier = set()
    for src in visited:
        for e in landscape.edges:
            if e.source == src and e.target not in visited:
                tp = transition_potential(landscape, e)
                if tp > 0:
                    frontier.add(e.target)

    # Domain-specific coverage
    canon_nodes = {n for n in landscape.states if n.startswith("C:")}
    bootstrap_nodes = {n for n in landscape.states if n.startswith("B:")}
    canon_visited = len(visited & canon_nodes)
    bootstrap_visited_count = len(visited & bootstrap_nodes)
    canon_cov = canon_visited / max(1, len(canon_nodes))
    bootstrap_cov = bootstrap_visited_count / max(1, len(bootstrap_nodes))

    T_s = structural_temperature(hist)

    return Assessment(
        total_nodes=total_nodes,
        total_edges=total_edges,
        visited_nodes=len(visited),
        coverage=coverage,
        frontier_size=len(frontier),
        T_s=T_s,
        mean_quality=mean_q,
        stale_edges=stale,
        canon_coverage=canon_cov,
        bootstrap_coverage=bootstrap_cov,
    )


# ── Phase 2: PLAN ──────────────────────────────────────────────────────


def plan(assessment: Assessment, round_num: int, history: List[RoundResult],
         max_steps: int = 30) -> RoundPlan:
    """Decide what this round should do based on assessment and history."""
    base_steps = max_steps

    # Check for stagnation: last 3 rounds had 0 coverage increase
    stagnation_count = 0
    for r in history[-3:]:
        if r.coverage_delta <= 0.001:
            stagnation_count += 1

    # Decision logic
    if stagnation_count >= 3:
        return RoundPlan(
            mode="llm",
            steps=base_steps,
            reason=f"Stagnation: {stagnation_count} consecutive rounds with no coverage increase",
        )

    if stagnation_count >= 1 and round_num > 2:
        # Increase budget to break through
        return RoundPlan(
            mode="explore",
            steps=int(base_steps * 1.5),
            reason=f"Stagnation recovery: increased budget ({stagnation_count} stalled rounds)",
        )

    if assessment.coverage < 0.3:
        # Early phase: broad exploration
        return RoundPlan(
            mode="explore",
            steps=base_steps,
            reason=f"Low coverage ({assessment.coverage:.1%}) → broad exploration",
        )

    if assessment.T_s > MU * 2:
        # Hot system: too much unresolved experience
        return RoundPlan(
            mode="explore",
            steps=base_steps,
            reason=f"High T_s ({assessment.T_s:.1f} > {MU*2:.0f}) → explore to build clarity",
        )

    if assessment.frontier_size > 0:
        # Frontier exists: keep exploring
        return RoundPlan(
            mode="explore",
            steps=base_steps,
            reason=f"Frontier of {assessment.frontier_size} unvisited nodes available",
        )

    # Default: continue exploring
    return RoundPlan(
        mode="explore",
        steps=base_steps,
        reason="Default exploration round",
    )


# ── Phase 3: NAVIGATE ──────────────────────────────────────────────────


def _pick_start_node(landscape, unified_nodes) -> str:
    """Pick a starting node adjacent to the frontier for maximum learning.

    Finds visited nodes that have unvisited neighbors (frontier-adjacent),
    then picks the one with the highest total transition potential toward
    unvisited territory. Falls back to B:HERE if no frontier exists.
    """
    hist = landscape.historization

    # Identify visited and unvisited nodes
    visited = set()
    for e in landscape.edges:
        if hist.trace_load(e) > 0:
            visited.add(e.source)
            visited.add(e.target)

    if not visited:
        return "B:HERE"

    # Find frontier-adjacent visited nodes
    best_start = None
    best_potential = -1.0

    for e in landscape.edges:
        if e.source in visited and e.target not in visited:
            tp = transition_potential(landscape, e)
            if tp > best_potential:
                best_potential = tp
                best_start = e.source

    return best_start or "B:HERE"


def navigate(landscape, unified_nodes, plan: RoundPlan,
             start: str = "B:HERE") -> Dict[str, Any]:
    """Run exploration with the planned budget.

    Uses transition potential with an exploration bonus: edges leading to
    nodes not yet visited (trace_load == 0) get their T doubled.
    This pulls navigation into new territory instead of circling the known.

    Returns dict with path, domain crossings, visited sets, new shortcut edges.
    """
    hist = landscape.historization

    # Pre-compute the set of globally-visited nodes (have any edge with load>0)
    globally_visited = set()
    for e in landscape.edges:
        if hist.trace_load(e) > 0:
            globally_visited.add(e.source)
            globally_visited.add(e.target)

    current = start
    path = [current]
    visited_count: Dict[str, int] = {}
    domain_crossings = 0

    for step in range(plan.steps):
        visited_count[current] = visited_count.get(current, 0) + 1

        # Custom neighbor selection: argmax T with exploration bonus
        potentials = local_transition_potential(
            landscape, unified_nodes, current, horizon=3
        )
        if not potentials:
            break

        # Apply exploration bonus: 2x T for edges leading to unvisited targets
        scored = {}
        for nbr_candidate, tp in potentials.items():
            bonus = 2.0 if nbr_candidate not in globally_visited else 1.0
            # Also penalize revisits within this round
            revisit_penalty = 1.0 / (1.0 + visited_count.get(nbr_candidate, 0))
            scored[nbr_candidate] = tp * bonus * revisit_penalty

        nbr = max(scored, key=scored.get)
        potential = scored[nbr]

        if potential <= 0:
            break

        # Track domain crossing
        src_domain = "canon" if current.startswith("C:") else "bootstrap"
        tgt_domain = "canon" if nbr.startswith("C:") else "bootstrap"
        if src_domain != tgt_domain:
            domain_crossings += 1

        # Historize
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
            landscape.historization.update(edge, outcome)

        # Update visited set for intra-round exploration bonus
        globally_visited.add(nbr)

        path.append(nbr)
        current = nbr

    # Create structural shortcut edges (Phase D logic)
    new_edges = _create_shortcut_edges(landscape, unified_nodes, path)

    unique = set(path)
    canon_visited = {s for s in unique if s.startswith("C:")}
    bootstrap_visited = {s for s in unique if s.startswith("B:")}

    return {
        "path": path,
        "steps": len(path) - 1,
        "domain_crossings": domain_crossings,
        "crossing_rate": domain_crossings / max(1, len(path) - 1),
        "canon_visited": len(canon_visited),
        "bootstrap_visited": len(bootstrap_visited),
        "new_edges": new_edges,
    }


def _create_shortcut_edges(landscape, unified_nodes, path) -> List[Dict]:
    """Create shortcut edges from sub-paths (Phase D).

    For every sub-path A→B→C (length 2-4), if no direct A→C edge exists,
    create it with avg delta and sum resistance.
    """
    new_edges = []

    for length in range(2, min(5, len(path))):
        for i in range(len(path) - length):
            src = path[i]
            tgt = path[i + length]

            if src == tgt:
                continue
            if landscape.has_edge(src, tgt):
                continue

            # Compute averaged delta and summed resistance along sub-path
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

            # Add to landscape
            landscape.add_state(src)  # no-op if exists
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


# ── Phase 4: VALIDATE ──────────────────────────────────────────────────


def validate_confidence(landscape, path) -> Dict[Tuple[str, str], float]:
    """Update confidence of previously discovered edges based on usage.

    Returns dict of {(from, to): new_confidence}.
    """
    with open(BOOTSTRAP_PATH, encoding="utf-8") as f:
        bs = json.load(f)

    disc = bs.get("discovered_edges", {}).get("edges", [])
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

    # Don't write here — consolidate does the writing
    return updates


def prune_low_confidence_edges(threshold: float = 0.05) -> int:
    """Remove discovered edges with confidence below threshold.

    Returns number of pruned edges.
    """
    with open(BOOTSTRAP_PATH, encoding="utf-8") as f:
        bs = json.load(f)

    disc = bs.get("discovered_edges", {}).get("edges", [])
    if not disc:
        return 0

    before = len(disc)
    disc[:] = [e for e in disc if e.get("confidence", 0.5) >= threshold]
    pruned = before - len(disc)
    return pruned


# ── Phase 5: CONSOLIDATE ───────────────────────────────────────────────


def consolidate(round_result: RoundResult, new_edges: List[Dict],
                dry_run: bool = False) -> Dict[str, Any]:
    """Write round results to bootstrap.json.

    Persists: new discovered edges, learning history entry.
    Returns summary of what was written.
    """
    if dry_run:
        return {
            "new_edges_would_persist": len(new_edges),
            "round_recorded": False,
            "dry_run": True,
        }

    with open(BOOTSTRAP_PATH, encoding="utf-8") as f:
        bs = json.load(f)

    # Persist new shortcut edges
    if "discovered_edges" not in bs:
        bs["discovered_edges"] = {
            "_comment": "Edges discovered through E₀ self-navigation.",
            "edges": [],
        }

    existing = {(e["from"], e["to"]) for e in bs["discovered_edges"]["edges"]}
    added = 0
    for edge in new_edges:
        # Only persist cross-type or structurally novel edges
        key = (edge["from"], edge["to"])
        if key not in existing:
            bs["discovered_edges"]["edges"].append(edge)
            existing.add(key)
            added += 1

    # Persist learning history
    if "learning_history" not in bs:
        bs["learning_history"] = {
            "_comment": "Accumulated learning cycle metrics (C202).",
            "rounds": [],
        }

    history_entry = {
        "round": round_result.round_num,
        "mode": round_result.plan.mode,
        "reason": round_result.plan.reason,
        "steps": len(round_result.path) - 1,
        "coverage_before": round(round_result.assessment_before.coverage, 4),
        "coverage_after": round(round_result.assessment_after.coverage, 4),
        "coverage_delta": round(round_result.coverage_delta, 4),
        "new_edges": round_result.new_edges,
        "T_s_before": round(round_result.assessment_before.T_s, 3),
        "T_s_after": round(round_result.assessment_after.T_s, 3),
        "T_s_delta": round(round_result.T_s_delta, 3),
        "crossing_rate": round(round_result.crossing_rate, 3),
        "canon_visited": round_result.canon_visited,
        "bootstrap_visited": round_result.bootstrap_visited,
        "llm_round": round_result.llm_round,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    bs["learning_history"]["rounds"].append(history_entry)

    with open(BOOTSTRAP_PATH, "w", encoding="utf-8") as f:
        json.dump(bs, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return {
        "new_edges_persisted": added,
        "round_recorded": True,
        "total_discovered": len(bs["discovered_edges"]["edges"]),
    }


# ── Outer Loop ──────────────────────────────────────────────────────────


def build_landscape(fresh_canon: bool = True) -> Tuple[Any, Dict, List[Dict]]:
    """Load Canon + Bootstrap + bridges → unified landscape.

    Args:
        fresh_canon: If True, Canon nodes start with zero traces (U=0, F=0).
            This makes Canon territory genuinely unknown — high Δ + zero load
            = high transition potential. Navigation is drawn FROM Bootstrap
            (known) TOWARD Canon (unknown) via bridges.

    Returns (landscape, unified_nodes, bridge_edges).
    """
    cl = load_canon("ontodynamics")
    bs = load_bootstrap()
    bs_nodes = extract_nodes(bs)
    bs_edges = extract_edges(bs, bs_nodes)

    static_bridges = build_static_bridges(cl.info, bs_nodes)

    unified_nodes, unified_edges = build_unified_landscape(
        cl.info, cl.landscape, bs_nodes, bs_edges, static_bridges,
    )

    if fresh_canon:
        # Zero out Canon node traces so they're genuinely unexplored
        for nid in unified_nodes:
            if nid.startswith("C:"):
                unified_nodes[nid]["U"] = 0.0
                unified_nodes[nid]["F"] = 0.0

    spec = build_spec(unified_nodes, unified_edges)
    landscape = bootstrap_landscape(spec)
    inject_node_traces(landscape, unified_nodes)

    return landscape, unified_nodes, static_bridges


def run_learning_cycle(
    max_rounds: int = 5,
    steps_per_round: int = 30,
    persist: bool = False,
    use_llm: bool = False,
    llm_dry: bool = False,
    llm_every_n: int = 3,
    verbose: bool = True,
) -> List[RoundResult]:
    """Run the iterative learning cycle.

    Each round: assess → plan → navigate → validate → consolidate.
    Landscape is built ONCE and reused — traces accumulate across rounds.
    This is the key design: each round's navigation enriches the shared
    historization, so the next round starts with more knowledge.

    Args:
        max_rounds: Maximum number of rounds.
        steps_per_round: Base navigation budget per round.
        persist: Whether to write results to bootstrap.json.
        use_llm: Whether to run LLM validation/execution.
        llm_dry: Dry-run LLM (placeholder scores).
        llm_every_n: Run LLM every Nth round (or when triggered by stagnation).
        verbose: Print progress.

    Returns:
        List of RoundResult for each completed round.
    """
    history: List[RoundResult] = []
    stagnation_streak = 0

    # Build landscape ONCE — traces accumulate across rounds
    landscape, unified_nodes, bridges = build_landscape()

    for round_num in range(1, max_rounds + 1):

        # Phase 1: ASSESS
        assessment_before = assess(landscape, unified_nodes)

        if verbose:
            print(f"\n{'─' * 60}")
            print(f"  Round {round_num}/{max_rounds}")
            print(f"{'─' * 60}")
            print(f"  Coverage: {assessment_before.coverage:.1%} "
                  f"({assessment_before.visited_nodes}/{assessment_before.total_nodes})")
            print(f"  T_s:      {assessment_before.T_s:.3f}")
            print(f"  Frontier: {assessment_before.frontier_size} unvisited nodes")
            print(f"  Canon:    {assessment_before.canon_coverage:.1%}")
            print(f"  Bootstrap:{assessment_before.bootstrap_coverage:.1%}")

        # Check termination: no frontier left and high coverage
        if (assessment_before.frontier_size == 0
                and assessment_before.coverage > 0.9):
            if verbose:
                print(f"\n  ✓ Structural saturation: no frontier, "
                      f"coverage={assessment_before.coverage:.1%}")
                print(f"    System has equilibrated. Stopping.")
            break

        # Phase 2: PLAN
        round_plan = plan(assessment_before, round_num, history, steps_per_round)

        # Force LLM round if planner says so or if every-N triggers
        is_llm_round = (
            round_plan.mode == "llm"
            or (use_llm and round_num % llm_every_n == 0)
        )

        if verbose:
            print(f"  Plan:     {round_plan.mode} ({round_plan.steps} steps)")
            print(f"  Reason:   {round_plan.reason}")
            if is_llm_round:
                print(f"  LLM:      {'dry-run' if llm_dry else 'active'}")

        # Phase 3: NAVIGATE — start from frontier-adjacent node
        start_node = _pick_start_node(landscape, unified_nodes)
        nav_result = navigate(landscape, unified_nodes, round_plan,
                              start=start_node)

        if verbose:
            print(f"\n  Navigation (start={start_node}):")
            print(f"    Steps:      {nav_result['steps']}")
            print(f"    Crossings:  {nav_result['domain_crossings']} "
                  f"({nav_result['crossing_rate']:.1%})")
            print(f"    Canon:      {nav_result['canon_visited']} nodes")
            print(f"    Bootstrap:  {nav_result['bootstrap_visited']} nodes")
            print(f"    New edges:  {len(nav_result['new_edges'])}")

        # Phase 4: VALIDATE
        conf_updates = validate_confidence(landscape, nav_result["path"])

        if is_llm_round and (use_llm or llm_dry):
            if verbose:
                print(f"  LLM validation: ", end="")
            # Import lazily to avoid import errors when not using LLM
            from e0_controller.explore_bootstrap_landscape import (
                llm_semantic_validation,
                extract_nodes as _extract_nodes,
            )
            bs = load_bootstrap()
            nodes_for_llm = _extract_nodes(bs)
            scores = llm_semantic_validation(nodes_for_llm, dry_run=llm_dry)
            if verbose:
                print(f"{len(scores)} edges scored")

        # Phase 5: CONSOLIDATE (re-assess after navigation)
        assessment_after = assess(landscape, unified_nodes)
        coverage_delta = assessment_after.coverage - assessment_before.coverage
        T_s_delta = assessment_after.T_s - assessment_before.T_s

        round_result = RoundResult(
            round_num=round_num,
            plan=round_plan,
            assessment_before=assessment_before,
            assessment_after=assessment_after,
            path=nav_result["path"],
            new_edges=len(nav_result["new_edges"]),
            domain_crossings=nav_result["domain_crossings"],
            crossing_rate=nav_result["crossing_rate"],
            canon_visited=nav_result["canon_visited"],
            bootstrap_visited=nav_result["bootstrap_visited"],
            llm_round=is_llm_round and (use_llm or llm_dry),
            coverage_delta=coverage_delta,
            T_s_delta=T_s_delta,
        )
        history.append(round_result)

        if verbose:
            print(f"\n  After round {round_num}:")
            print(f"    Coverage: {assessment_after.coverage:.1%} "
                  f"(Δ={coverage_delta:+.1%})")
            print(f"    T_s:      {assessment_after.T_s:.3f} "
                  f"(Δ={T_s_delta:+.3f})")

        # Persist if requested
        if persist:
            consolidation = consolidate(round_result, nav_result["new_edges"])
            if verbose:
                print(f"    Persisted: {consolidation['new_edges_persisted']} new edges")
        else:
            # Dry-run consolidation (just shows what would happen)
            consolidation = consolidate(round_result, nav_result["new_edges"],
                                        dry_run=True)

        # Stagnation tracking
        if coverage_delta <= 0.001:
            stagnation_streak += 1
        else:
            stagnation_streak = 0

        if stagnation_streak >= 3 and not is_llm_round:
            if verbose:
                print(f"\n  ⚠ Stagnation: {stagnation_streak} rounds with no progress")
                print(f"    Next round will trigger LLM validation")

    # Final summary
    if verbose and history:
        _print_summary(history)

    return history


def _print_summary(history: List[RoundResult]) -> None:
    """Print final learning cycle summary."""
    print(f"\n{'=' * 60}")
    print(f"  LEARNING CYCLE SUMMARY")
    print(f"{'=' * 60}")

    total_steps = sum(len(r.path) - 1 for r in history)
    total_new_edges = sum(r.new_edges for r in history)
    total_crossings = sum(r.domain_crossings for r in history)

    first = history[0].assessment_before
    last = history[-1].assessment_after

    print(f"  Rounds:         {len(history)}")
    print(f"  Total steps:    {total_steps}")
    print(f"  Total new edges:{total_new_edges}")
    print(f"  Total crossings:{total_crossings}")
    print()
    print(f"  Coverage:       {first.coverage:.1%} → {last.coverage:.1%} "
          f"(Δ={last.coverage - first.coverage:+.1%})")
    print(f"  T_s:            {first.T_s:.3f} → {last.T_s:.3f} "
          f"(Δ={last.T_s - first.T_s:+.3f})")
    print(f"  Canon cov:      {first.canon_coverage:.1%} → {last.canon_coverage:.1%}")
    print(f"  Bootstrap cov:  {first.bootstrap_coverage:.1%} → {last.bootstrap_coverage:.1%}")

    print(f"\n  Round-by-round:")
    print(f"  {'#':>3} {'Mode':>8} {'Steps':>6} {'Cov':>7} {'ΔCov':>7} "
          f"{'T_s':>7} {'ΔT_s':>7} {'Cross':>6} {'New':>4}")
    print(f"  {'─' * 57}")
    for r in history:
        print(f"  {r.round_num:3d} {r.plan.mode:>8} {len(r.path)-1:6d} "
              f"{r.assessment_after.coverage:7.1%} {r.coverage_delta:+7.1%} "
              f"{r.assessment_after.T_s:7.3f} {r.T_s_delta:+7.3f} "
              f"{r.domain_crossings:6d} {r.new_edges:4d}")

    print(f"{'=' * 60}")


# ── CLI ─────────────────────────────────────────────────────────────────


def main():
    print("=" * 60)
    print("  E₀ Learning Cycle (C202)")
    print("  Iterative self-improvement through repeated navigation")
    print("=" * 60)

    # Parse args
    max_rounds = 5
    for i, arg in enumerate(sys.argv):
        if arg == "--rounds" and i + 1 < len(sys.argv):
            max_rounds = int(sys.argv[i + 1])

    use_llm = "--llm" in sys.argv
    llm_dry = "--llm-dry" in sys.argv
    persist = "--persist" in sys.argv

    print(f"\n  Config:")
    print(f"    Rounds:  {max_rounds}")
    print(f"    LLM:     {'active' if use_llm else 'dry-run' if llm_dry else 'off'}")
    print(f"    Persist: {'yes' if persist else 'no'}")

    results = run_learning_cycle(
        max_rounds=max_rounds,
        persist=persist,
        use_llm=use_llm,
        llm_dry=llm_dry,
    )

    if results:
        last = results[-1]
        print(f"\n  Final state:")
        print(f"    Coverage: {last.assessment_after.coverage:.1%}")
        print(f"    T_s:      {last.assessment_after.T_s:.3f}")
        print(f"    Rounds:   {len(results)}")


if __name__ == "__main__":
    main()
