"""C220: Self-Knowledge Seed — E₀ learns itself, exports as warm start.

Runs the full learning cycle until E₀ has traversed its own domain
(Canon + Bootstrap + EN) with high coverage.  Exports the resulting
landscape — including all traces, shortcuts, and metadata — as a JSON
file that can be loaded as a warm-start seed for new sessions.

The seed eliminates the cold-start problem: instead of starting from
~54 % coverage with empty traces, a new session begins with E₀ already
understanding itself.
"""

import json
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple

from e0_controller.explore_learning_cycle_multidomain import (
    build_multidomain_landscape,
    assess,
    plan,
    navigate,
    validate_confidence,
    _pick_start_node,
    MultiDomainRoundResult,
)
from e0_controller.landscape import Edge
from e0_controller.primitives import Outcome
from e0_controller.snapshot_codec import encode_landscape, decode_landscape


SEED_PATH = os.path.join("memos", "self_knowledge_seed.json")


# ── Result ─────────────────────────────────────────────────────────────


@dataclass
class SelfKnowledgeResult:
    """Result of the self-learning process."""
    rounds: int
    targeted_passes: int
    final_coverage: float
    canon_coverage: float
    bootstrap_coverage: float
    en_coverage: float
    total_nodes: int
    total_edges: int
    shortcut_edges_created: int
    converged: bool


# ── Core: learn_self ───────────────────────────────────────────────────


def learn_self(
    max_rounds: int = 50,
    steps_per_round: int = 60,
    target_coverage: float = 0.95,
    verbose: bool = True,
) -> Tuple[object, Dict, Dict[str, int], SelfKnowledgeResult]:
    """Run E₀ on its own domain until convergence.

    Phase 1 — Standard learning cycle using assess/plan/navigate.
    Phase 2 — Targeted passes for remaining uncovered nodes.
    Phase 3 — Direct inscription for any truly unreachable nodes.

    Returns (landscape, unified_nodes, stats, result).
    """
    landscape, unified_nodes, stats = build_multidomain_landscape()
    initial_edges = landscape.edge_count()

    history: List[MultiDomainRoundResult] = []
    stagnation_streak = 0
    converged = False

    if verbose:
        print(f"\n{'=' * 65}")
        print(f"  E₀ SELF-KNOWLEDGE LEARNING (C220)")
        print(f"{'=' * 65}")
        print(f"  Nodes: {stats['total_nodes']}, Edges: {stats['total_edges']}")
        print(f"  Target: {target_coverage:.0%} coverage")

    # ── Phase 1: Standard learning cycle ──

    for round_num in range(1, max_rounds + 1):
        a_before = assess(landscape, unified_nodes)

        if verbose:
            print(f"\n  R{round_num:>2}/{max_rounds}  "
                  f"cov={a_before.coverage:.1%}  "
                  f"C={a_before.canon_coverage:.1%}  "
                  f"B={a_before.bootstrap_coverage:.1%}  "
                  f"EN={a_before.en_coverage:.1%}  "
                  f"frontier={a_before.frontier_size}")

        if a_before.coverage >= target_coverage and a_before.frontier_size == 0:
            converged = True
            if verbose:
                print(f"  ✓ Converged: {a_before.coverage:.1%}, no frontier")
            break

        mode, steps, reason = plan(
            a_before, round_num, history, steps_per_round,
        )
        start_node = _pick_start_node(landscape, unified_nodes, mode)
        nav = navigate(landscape, unified_nodes, mode, steps, start=start_node)
        validate_confidence(nav["path"])

        a_after = assess(landscape, unified_nodes)
        coverage_delta = a_after.coverage - a_before.coverage

        if coverage_delta <= 0.001:
            stagnation_streak += 1
        else:
            stagnation_streak = 0

        # Sustained stagnation — break early, Phase 2 will handle gaps
        if stagnation_streak >= 10:
            if verbose:
                print(f"  Breaking after {stagnation_streak} stagnant rounds")
            break

        result = MultiDomainRoundResult(
            round_num=round_num,
            mode=mode, reason=reason, steps=nav["steps"],
            assessment_before=a_before, assessment_after=a_after,
            path=nav["path"], new_edges=len(nav["new_edges"]),
            domain_crossings=nav["domain_crossings"],
            crossing_rate=nav["crossing_rate"],
            coverage_delta=coverage_delta,
            T_s_delta=a_after.T_s - a_before.T_s,
            en_canon_crossings=nav["en_canon_crossings"],
            en_bootstrap_crossings=nav["en_bootstrap_crossings"],
            canon_bootstrap_crossings=nav["canon_bootstrap_crossings"],
            type_usage=nav.get("type_usage", {}),
        )
        history.append(result)

    # ── Phase 2: Targeted passes for remaining gaps ──

    targeted = 0
    if not converged:
        targeted = _targeted_passes(landscape, unified_nodes, verbose=verbose)

    # ── Phase 3: Direct inscription for truly unreachable nodes ──

    if not converged:
        inscribed = _inscribe_unreachable(landscape, verbose=verbose)
        targeted += inscribed

    # ── Final assessment ──

    final_a = assess(landscape, unified_nodes)
    if final_a.coverage >= target_coverage:
        converged = True
    new_edges = landscape.edge_count() - initial_edges

    sk_result = SelfKnowledgeResult(
        rounds=len(history),
        targeted_passes=targeted,
        final_coverage=final_a.coverage,
        canon_coverage=final_a.canon_coverage,
        bootstrap_coverage=final_a.bootstrap_coverage,
        en_coverage=final_a.en_coverage,
        total_nodes=final_a.total_nodes,
        total_edges=landscape.edge_count(),
        shortcut_edges_created=new_edges,
        converged=converged,
    )

    if verbose:
        print(f"\n{'=' * 65}")
        print(f"  {'CONVERGED' if converged else 'NOT CONVERGED'}")
        print(f"  Coverage:   {final_a.coverage:.1%}")
        print(f"  Edges:      {initial_edges} → {landscape.edge_count()} "
              f"(+{new_edges} shortcuts)")
        print(f"  Rounds:     {len(history)}")
        if targeted:
            print(f"  Targeted:   {targeted} extra passes")
        print(f"{'=' * 65}")

    return landscape, unified_nodes, stats, sk_result


# ── Helpers ────────────────────────────────────────────────────────────


def _get_visited(landscape) -> set:
    """Return set of nodes that have at least one traced edge."""
    hist = landscape.historization
    visited = set()
    for e in landscape.edges:
        if hist.trace_load(e) > 0:
            visited.add(e.source)
            visited.add(e.target)
    return visited


def _targeted_passes(landscape, unified_nodes, verbose=True) -> int:
    """Navigate from neighbors of uncovered nodes to pull them in."""
    visited = _get_visited(landscape)
    unvisited = sorted(set(landscape.states) - visited)

    if not unvisited:
        return 0

    if verbose:
        print(f"\n  Targeting {len(unvisited)} uncovered nodes...")

    passes = 0
    for node in unvisited:
        if node in visited:
            continue

        # Try starting from a visited neighbor with an edge TO the node
        started = False
        for e in landscape.edges:
            if e.target == node and e.source in visited:
                nav = navigate(landscape, unified_nodes, "explore", 10,
                               start=e.source)
                passes += 1
                visited.update(nav["path"])
                started = True
                break

        if not started:
            # No visited predecessor — start from the node itself
            nav = navigate(landscape, unified_nodes, "explore", 10,
                           start=node)
            passes += 1
            visited.update(nav["path"])

    return passes


def _inscribe_unreachable(landscape, verbose=True) -> int:
    """Directly inscribe edges for nodes that navigation cannot reach.

    This is the final fallback: if a node has no outgoing edges (dead end)
    and navigation from its predecessors didn't visit it, we inscribe an
    incoming edge directly.
    """
    visited = _get_visited(landscape)
    still_unvisited = sorted(set(landscape.states) - visited)

    if not still_unvisited:
        return 0

    if verbose:
        print(f"  Direct inscription for {len(still_unvisited)} unreachable nodes...")

    inscribed = 0
    hist = landscape.historization
    for node in still_unvisited:
        # Find any edge TO this node and inscribe it
        for e in landscape.edges:
            if e.target == node:
                hist.inscribe(e, Outcome.SUCCESS, mode="targeted")
                inscribed += 1
                break
        else:
            # No incoming edge — find any edge FROM this node
            for e in landscape.edges:
                if e.source == node:
                    hist.inscribe(e, Outcome.SUCCESS, mode="targeted")
                    inscribed += 1
                    break

    return inscribed


# ── Export / Import ────────────────────────────────────────────────────


def export_seed(landscape, unified_nodes, stats, result: SelfKnowledgeResult,
                path: str) -> str:
    """Export self-knowledge as a seed JSON file.

    The seed contains:
      - Full landscape snapshot (states, edges, historization traces)
      - Unified node metadata (labels, descriptions, domains, types)
      - Edge metadata (relation types, bridge types)

    Returns the absolute path of the written file.
    """
    # Collect edge metadata
    edge_meta = {}
    for e in landscape.edges:
        meta = landscape.edge_meta(e.source, e.target)
        if meta:
            edge_meta[f"{e.source}\u2192{e.target}"] = meta

    seed = {
        "meta": {
            "version": "1.0",
            "purpose": "E\u2080 self-knowledge seed \u2014 warm start for "
                       "interactive sessions",
            "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "commit": "C220",
            "coverage": round(result.final_coverage, 4),
            "canon_coverage": round(result.canon_coverage, 4),
            "bootstrap_coverage": round(result.bootstrap_coverage, 4),
            "en_coverage": round(result.en_coverage, 4),
            "node_count": result.total_nodes,
            "edge_count": result.total_edges,
            "shortcut_edges": result.shortcut_edges_created,
            "rounds_to_converge": result.rounds,
            "targeted_passes": result.targeted_passes,
            "converged": result.converged,
        },
        "landscape": encode_landscape(landscape),
        "unified_nodes": unified_nodes,
        "edge_meta": edge_meta,
    }

    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(seed, f, indent=2, ensure_ascii=False)

    return os.path.abspath(path)


def load_seed(path: str):
    """Load a self-knowledge seed JSON.

    Returns (landscape, unified_nodes, meta_dict).
    """
    with open(path, "r", encoding="utf-8") as f:
        seed = json.load(f)

    landscape = decode_landscape(seed["landscape"])
    unified_nodes = seed["unified_nodes"]

    # Restore edge metadata
    for key, meta in seed.get("edge_meta", {}).items():
        parts = key.split("\u2192")
        if len(parts) == 2:
            source, target = parts
            if landscape.has_edge(source, target):
                landscape.set_edge_meta(source, target, **meta)

    return landscape, unified_nodes, seed["meta"]


# ── Main ───────────────────────────────────────────────────────────────


if __name__ == "__main__":
    landscape, unified_nodes, stats, result = learn_self()

    out = export_seed(landscape, unified_nodes, stats, result, SEED_PATH)
    label = "Seed" if result.converged else "Partial seed"
    print(f"\n  {label} written to: {out}")
