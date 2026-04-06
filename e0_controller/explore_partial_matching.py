#!/usr/bin/env python3
"""
E₀ C170 — Partial Structure Matching
======================================

Open Question Q3 from Multi-Domain Dream Analysis (§6):
  "Can partial structure matching work? Instead of matching the full graph,
   match subgraphs (clusters) across domains. A 5-node chain in EN might
   genuinely correspond to a 5-node chain in Onto if they share local
   quality patterns."

Core idea: dream_compatibility() gates entire domain pairs as all-or-nothing.
EN↔ONTO=0.870 → SKIP. But within those 44/51 matched nodes, maybe 5-10
pairs have distance <0.3 — real local matches, discarded by the global gate.

Phases:
  1. Landscape construction + curriculum training (reuse C169 setup)
  2. Full NxM distance matrices for all pairs
  3. Per-pair distance distributions (incompatible pairs: are there outliers?)
  4. Partial match extraction: best-k pairs at various k
  5. Quality characterization: do partial matches share structural coherence?
  6. Compatible vs. incompatible: distribution shape comparison
  7. Design verdict: is partial matching worth implementing?
"""

import sys
import os
import time
import random
import math
import statistics
from itertools import combinations
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from e0_controller.canon_loader import load_canon
from e0_controller.curriculum import CurriculumRunner
from e0_controller.bootstrapper import bootstrap_landscape
from e0_controller.landscape import Landscape
from e0_controller.primitives import Outcome
from e0_controller.dream_mode import (
    dream_compatibility,
    wl_node_fingerprints,
    wl_node_distance,
    WLNodeFingerprint,
)

EXEC_FN = lambda s, t: Outcome.SUCCESS  # noqa: E731

COMPAT_THRESHOLD = 0.6  # from C168/C169


# ──────────────────────────────────────────────
# Landscape builders (from C169)
# ──────────────────────────────────────────────

def build_random_landscape(n_nodes: int, density: float, seed: int = 42) -> Landscape:
    """Random directed graph with varied delta/resistance."""
    rng = random.Random(seed)
    nodes = [f"N{i}" for i in range(n_nodes)]
    spec = {"nodes": nodes, "edges": []}
    for i, src in enumerate(nodes):
        for j, tgt in enumerate(nodes):
            if i != j and rng.random() < density:
                spec["edges"].append({
                    "from": src, "to": tgt,
                    "delta": round(rng.uniform(0.1, 0.9), 2),
                    "resistance": round(rng.uniform(0.3, 2.0), 2),
                    "initial_U": round(rng.uniform(0, 5), 1),
                    "initial_F": round(rng.uniform(0, 5), 1),
                    "confidence": round(rng.uniform(0.3, 1.0), 2),
                })
    return bootstrap_landscape(spec)


def build_llm_cooking_landscape() -> Landscape:
    """Hand-crafted LLM-style domain: cooking workflow."""
    spec = {
        "nodes": [
            "RECIPE_SELECTION", "INGREDIENT_PREP", "COOKING_TECHNIQUE",
            "FLAVOR_BALANCE", "PLATING", "TASTING", "ADJUSTMENT",
            "SERVING", "CLEANUP", "PLANNING",
        ],
        "edges": [
            {"from": "RECIPE_SELECTION", "to": "INGREDIENT_PREP", "delta": 0.7, "resistance": 0.3, "initial_U": 8, "initial_F": 1, "confidence": 0.9},
            {"from": "INGREDIENT_PREP", "to": "COOKING_TECHNIQUE", "delta": 0.6, "resistance": 0.5, "initial_U": 7, "initial_F": 2, "confidence": 0.8},
            {"from": "COOKING_TECHNIQUE", "to": "FLAVOR_BALANCE", "delta": 0.5, "resistance": 0.6, "initial_U": 5, "initial_F": 3, "confidence": 0.7},
            {"from": "FLAVOR_BALANCE", "to": "TASTING", "delta": 0.4, "resistance": 0.4, "initial_U": 6, "initial_F": 2, "confidence": 0.8},
            {"from": "TASTING", "to": "ADJUSTMENT", "delta": 0.3, "resistance": 0.3, "initial_U": 4, "initial_F": 4, "confidence": 0.5},
            {"from": "ADJUSTMENT", "to": "COOKING_TECHNIQUE", "delta": 0.5, "resistance": 0.7, "initial_U": 3, "initial_F": 3, "confidence": 0.5},
            {"from": "FLAVOR_BALANCE", "to": "PLATING", "delta": 0.6, "resistance": 0.4, "initial_U": 7, "initial_F": 1, "confidence": 0.9},
            {"from": "PLATING", "to": "SERVING", "delta": 0.8, "resistance": 0.2, "initial_U": 9, "initial_F": 0, "confidence": 0.95},
            {"from": "SERVING", "to": "CLEANUP", "delta": 0.3, "resistance": 0.5, "initial_U": 5, "initial_F": 2, "confidence": 0.7},
            {"from": "PLANNING", "to": "RECIPE_SELECTION", "delta": 0.6, "resistance": 0.4, "initial_U": 6, "initial_F": 1, "confidence": 0.8},
            {"from": "CLEANUP", "to": "PLANNING", "delta": 0.2, "resistance": 0.6, "initial_U": 3, "initial_F": 1, "confidence": 0.6},
            {"from": "TASTING", "to": "PLATING", "delta": 0.5, "resistance": 0.3, "initial_U": 6, "initial_F": 2, "confidence": 0.7},
            {"from": "RECIPE_SELECTION", "to": "PLANNING", "delta": 0.3, "resistance": 0.5, "initial_U": 4, "initial_F": 2, "confidence": 0.6},
        ],
    }
    return bootstrap_landscape(spec)


def build_llm_project_landscape() -> Landscape:
    """Hand-crafted LLM-style domain: project management."""
    spec = {
        "nodes": [
            "REQUIREMENTS", "DESIGN", "IMPLEMENTATION", "TESTING",
            "REVIEW", "DEPLOYMENT", "MONITORING", "FEEDBACK",
            "PLANNING", "DOCUMENTATION",
        ],
        "edges": [
            {"from": "REQUIREMENTS", "to": "DESIGN", "delta": 0.7, "resistance": 0.4, "initial_U": 7, "initial_F": 2, "confidence": 0.8},
            {"from": "DESIGN", "to": "IMPLEMENTATION", "delta": 0.6, "resistance": 0.5, "initial_U": 6, "initial_F": 3, "confidence": 0.7},
            {"from": "IMPLEMENTATION", "to": "TESTING", "delta": 0.5, "resistance": 0.4, "initial_U": 5, "initial_F": 3, "confidence": 0.7},
            {"from": "TESTING", "to": "REVIEW", "delta": 0.4, "resistance": 0.3, "initial_U": 6, "initial_F": 2, "confidence": 0.8},
            {"from": "REVIEW", "to": "DEPLOYMENT", "delta": 0.5, "resistance": 0.5, "initial_U": 5, "initial_F": 3, "confidence": 0.6},
            {"from": "DEPLOYMENT", "to": "MONITORING", "delta": 0.3, "resistance": 0.4, "initial_U": 4, "initial_F": 2, "confidence": 0.7},
            {"from": "MONITORING", "to": "FEEDBACK", "delta": 0.4, "resistance": 0.3, "initial_U": 5, "initial_F": 3, "confidence": 0.6},
            {"from": "FEEDBACK", "to": "REQUIREMENTS", "delta": 0.5, "resistance": 0.6, "initial_U": 3, "initial_F": 4, "confidence": 0.5},
            {"from": "PLANNING", "to": "REQUIREMENTS", "delta": 0.6, "resistance": 0.3, "initial_U": 7, "initial_F": 1, "confidence": 0.9},
            {"from": "REVIEW", "to": "IMPLEMENTATION", "delta": 0.3, "resistance": 0.7, "initial_U": 2, "initial_F": 5, "confidence": 0.4},
            {"from": "DOCUMENTATION", "to": "DEPLOYMENT", "delta": 0.4, "resistance": 0.4, "initial_U": 5, "initial_F": 2, "confidence": 0.7},
            {"from": "IMPLEMENTATION", "to": "DOCUMENTATION", "delta": 0.3, "resistance": 0.5, "initial_U": 4, "initial_F": 2, "confidence": 0.6},
            {"from": "TESTING", "to": "DOCUMENTATION", "delta": 0.2, "resistance": 0.4, "initial_U": 3, "initial_F": 1, "confidence": 0.5},
        ],
    }
    return bootstrap_landscape(spec)


# ──────────────────────────────────────────────
# Analysis helpers
# ──────────────────────────────────────────────

def compute_full_distance_matrix(
    landscape_a: Landscape,
    landscape_b: Landscape,
    domain_a: str,
    domain_b: str,
    depth: int = 2,
):
    """Compute NxM WL distance matrix + fingerprint lists.

    Returns (wl_a, wl_b, cost_matrix) where cost_matrix[i][j] = distance
    between node i of A and node j of B.
    """
    wl_a = wl_node_fingerprints(landscape_a, domain_a, depth=depth)
    wl_b = wl_node_fingerprints(landscape_b, domain_b, depth=depth)
    cost = []
    for na in wl_a:
        row = [wl_node_distance(na, nb) for nb in wl_b]
        cost.append(row)
    return wl_a, wl_b, cost


def best_k_distances(cost_matrix, k):
    """Extract the k smallest distances from the full NxM matrix (no 1:1 constraint)."""
    all_dists = []
    for i, row in enumerate(cost_matrix):
        for j, d in enumerate(row):
            all_dists.append((d, i, j))
    all_dists.sort()
    return all_dists[:k]


def best_k_hungarian(cost_matrix, k):
    """Extract the k best 1:1-matched pairs (Hungarian on full, take top-k)."""
    from scipy.optimize import linear_sum_assignment
    import numpy as np
    arr = np.array(cost_matrix)
    row_ind, col_ind = linear_sum_assignment(arr)
    pairs = [(arr[r, c], r, c) for r, c in zip(row_ind, col_ind)]
    pairs.sort()
    return pairs[:k]


def quantile_stats(values):
    """Compute distribution stats for a list of floats."""
    if not values:
        return {}
    s = sorted(values)
    n = len(s)
    return {
        "min": s[0],
        "p10": s[max(0, int(n * 0.1))],
        "p25": s[max(0, int(n * 0.25))],
        "median": statistics.median(s),
        "p75": s[min(n - 1, int(n * 0.75))],
        "p90": s[min(n - 1, int(n * 0.90))],
        "max": s[-1],
        "mean": statistics.mean(s),
        "std": statistics.stdev(s) if n > 1 else 0.0,
        "n": n,
    }


def fraction_below(values, threshold):
    """What fraction of values falls below threshold."""
    if not values:
        return 0.0
    return sum(1 for v in values if v < threshold) / len(values)


# ═══════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════

def main():
    t0 = time.time()

    # ── Phase 1: Construct landscapes ──────────────────────────
    print("=" * 70)
    print("PHASE 1: Landscape Construction")
    print("=" * 70)

    landscapes = {}

    # Canon-based
    for label, name in [("EN", "english_basic_enriched"),
                        ("DE", "german_basic_enriched"),
                        ("ONTO", "ontodynamics")]:
        cl = load_canon(name)
        landscapes[label] = cl.landscape
        ls = cl.landscape
        print(f"  {label:>8}: {len(ls.states)} nodes, {len(ls.edges)} edges")

    # LLM-style hand-crafted
    landscapes["COOK"] = build_llm_cooking_landscape()
    landscapes["PROJ"] = build_llm_project_landscape()
    for name in ("COOK", "PROJ"):
        ls = landscapes[name]
        print(f"  {name:>8}: {len(ls.states)} nodes, {len(ls.edges)} edges")

    # Random
    landscapes["RND"] = build_random_landscape(12, 0.25, seed=44)
    ls = landscapes["RND"]
    print(f"  {'RND':>8}: {len(ls.states)} nodes, {len(ls.edges)} edges")

    print(f"\n  Total: {len(landscapes)} landscapes\n")

    # ── Phase 2: Curriculum training ──────────────────────────
    print("=" * 70)
    print("PHASE 2: Curriculum Training (canons only)")
    print("=" * 70)

    canon_map = {"EN": "english_basic_enriched", "DE": "german_basic_enriched", "ONTO": "ontodynamics"}
    for label in ("EN", "DE", "ONTO"):
        runner = CurriculumRunner(
            canon_map[label], EXEC_FN,
            equilibrium_threshold=2.0,
            equilibrium_patience=3,
            max_episodes_per_turn=15,
            max_cycles_per_episode=40,
        )
        results = runner.run()
        landscapes[label] = runner.final_landscape
        total_steps = sum(r.total_steps for r in results)
        print(f"  {label}: {len(results)} turns, {total_steps} steps")

    # ── Phase 3: Full NxM distance matrices ──────────────────
    print("\n" + "=" * 70)
    print("PHASE 3: Full Distance Matrices")
    print("=" * 70)

    names = sorted(landscapes.keys())
    pair_data = {}  # (A, B) -> {wl_a, wl_b, cost, compat, all_dists, hungarian_dists}

    for a, b in combinations(names, 2):
        la, lb = landscapes[a], landscapes[b]
        wl_a, wl_b, cost = compute_full_distance_matrix(la, lb, a, b)
        compat = dream_compatibility(la, lb)

        # All pairwise distances
        all_dists = [cost[i][j] for i in range(len(cost)) for j in range(len(cost[0]))]

        # Hungarian assignments
        hung = best_k_hungarian(cost, min(len(wl_a), len(wl_b)))
        hung_dists = [d for d, _, _ in hung]

        pair_data[(a, b)] = {
            "wl_a": wl_a, "wl_b": wl_b, "cost": cost,
            "compat": compat,
            "all_dists": all_dists,
            "hungarian_dists": hung_dists,
            "hungarian_pairs": hung,
            "n_a": len(wl_a), "n_b": len(wl_b),
        }

        status = "PASS" if compat <= COMPAT_THRESHOLD else "SKIP"
        print(f"  {a:>4}↔{b:<4}: compat={compat:.3f} [{status}]  "
              f"({len(wl_a)}×{len(wl_b)}={len(all_dists)} distances)")

    # ── Phase 4: Distribution analysis ──────────────────────
    print("\n" + "=" * 70)
    print("PHASE 4: Per-Pair Distance Distributions")
    print("=" * 70)

    # Split into compatible and incompatible
    compatible_pairs = [(a, b) for (a, b) in pair_data
                        if pair_data[(a, b)]["compat"] <= COMPAT_THRESHOLD]
    incompatible_pairs = [(a, b) for (a, b) in pair_data
                          if pair_data[(a, b)]["compat"] > COMPAT_THRESHOLD]

    print(f"\n  Compatible pairs ({len(compatible_pairs)}):")
    print(f"  {'Pair':>12} {'compat':>7} {'min':>6} {'p10':>6} {'p25':>6} "
          f"{'med':>6} {'p75':>6} {'max':>6} {'<0.3':>5} {'<0.5':>5}")
    print("  " + "-" * 80)
    for a, b in sorted(compatible_pairs, key=lambda p: pair_data[p]["compat"]):
        d = pair_data[(a, b)]
        stats = quantile_stats(d["all_dists"])
        f03 = fraction_below(d["all_dists"], 0.3)
        f05 = fraction_below(d["all_dists"], 0.5)
        print(f"  {a+'↔'+b:>12} {d['compat']:7.3f} {stats['min']:6.3f} "
              f"{stats['p10']:6.3f} {stats['p25']:6.3f} {stats['median']:6.3f} "
              f"{stats['p75']:6.3f} {stats['max']:6.3f} {f03:5.1%} {f05:5.1%}")

    print(f"\n  Incompatible pairs ({len(incompatible_pairs)}):")
    print(f"  {'Pair':>12} {'compat':>7} {'min':>6} {'p10':>6} {'p25':>6} "
          f"{'med':>6} {'p75':>6} {'max':>6} {'<0.3':>5} {'<0.5':>5}")
    print("  " + "-" * 80)
    for a, b in sorted(incompatible_pairs, key=lambda p: pair_data[p]["compat"]):
        d = pair_data[(a, b)]
        stats = quantile_stats(d["all_dists"])
        f03 = fraction_below(d["all_dists"], 0.3)
        f05 = fraction_below(d["all_dists"], 0.5)
        print(f"  {a+'↔'+b:>12} {d['compat']:7.3f} {stats['min']:6.3f} "
              f"{stats['p10']:6.3f} {stats['p25']:6.3f} {stats['median']:6.3f} "
              f"{stats['p75']:6.3f} {stats['max']:6.3f} {f03:5.1%} {f05:5.1%}")

    # ── Phase 5: Partial match extraction ─────────────────────
    print("\n" + "=" * 70)
    print("PHASE 5: Partial Match Extraction (Incompatible Pairs)")
    print("=" * 70)
    print("\n  For each INCOMPATIBLE pair: best-k Hungarian matches at k=3,5,10")
    print(f"  {'Pair':>12} {'compat':>7} | {'k=3 mean':>9} {'k=5 mean':>9} {'k=10 mean':>10} | "
          f"{'best':>6} {'worst-of-10':>11}")
    print("  " + "-" * 82)

    partial_candidates = []
    for a, b in sorted(incompatible_pairs, key=lambda p: pair_data[p]["compat"]):
        d = pair_data[(a, b)]
        hung = d["hungarian_pairs"]  # sorted by distance, ascending
        n_hung = len(hung)

        k3 = statistics.mean([h[0] for h in hung[:3]]) if n_hung >= 3 else float("inf")
        k5 = statistics.mean([h[0] for h in hung[:5]]) if n_hung >= 5 else float("inf")
        k10 = statistics.mean([h[0] for h in hung[:10]]) if n_hung >= 10 else float("inf")
        best = hung[0][0] if hung else float("inf")
        worst10 = hung[min(9, n_hung - 1)][0] if hung else float("inf")

        print(f"  {a+'↔'+b:>12} {d['compat']:7.3f} | {k3:9.4f} {k5:9.4f} {k10:10.4f} | "
              f"{best:6.4f} {worst10:11.4f}")

        # Mark as partial candidate if best-5 mean is below compatible threshold
        if k5 < COMPAT_THRESHOLD:
            partial_candidates.append((a, b, k5))

    if partial_candidates:
        print(f"\n  *** PARTIAL CANDIDATES (best-5 < {COMPAT_THRESHOLD}):")
        for a, b, k5 in partial_candidates:
            print(f"      {a}↔{b}: best-5 mean = {k5:.4f}")
    else:
        print(f"\n  No incompatible pairs have best-5 < {COMPAT_THRESHOLD}")

    # ── Phase 6: Characterize best partial matches ────────────
    print("\n" + "=" * 70)
    print("PHASE 6: Best Partial Matches — Structural Detail")
    print("=" * 70)

    # For each incompatible pair, show the top-5 Hungarian matches with node names
    for a, b in sorted(incompatible_pairs, key=lambda p: pair_data[p]["compat"]):
        d = pair_data[(a, b)]
        hung = d["hungarian_pairs"]
        if not hung:
            continue
        print(f"\n  {a}↔{b} (compat={d['compat']:.3f}, {d['n_a']}×{d['n_b']})")
        print(f"    Top-5 matches:")
        for rank, (dist, ri, ci) in enumerate(hung[:5], 1):
            na = d["wl_a"][ri]
            nb = d["wl_b"][ci]
            # Show degree (feature index 2) and mean_q (feature index 0) from base features
            deg_a = na.features[2] if len(na.features) > 2 else "?"
            deg_b = nb.features[2] if len(nb.features) > 2 else "?"
            mq_a = na.features[0] if len(na.features) > 0 else "?"
            mq_b = nb.features[0] if len(nb.features) > 0 else "?"
            print(f"    {rank}. d={dist:.4f}  {na.node:>30} ↔ {nb.node:<30}  "
                  f"deg=({deg_a:.0f},{deg_b:.0f})  mean_q=({mq_a:.3f},{mq_b:.3f})")

        # Also show the bottom-3 (worst matches)
        if len(hung) > 5:
            print(f"    Bottom-3 matches:")
            for dist, ri, ci in hung[-3:]:
                na = d["wl_a"][ri]
                nb = d["wl_b"][ci]
                print(f"       d={dist:.4f}  {na.node:>30} ↔ {nb.node:<30}")

    # ── Phase 7: Compatible pair comparison ──────────────────
    print("\n" + "=" * 70)
    print("PHASE 7: Compatible Pairs — Reference Distribution")
    print("=" * 70)
    print("\n  How uniform are compatible pairs? (all Hungarian distances)")

    for a, b in sorted(compatible_pairs, key=lambda p: pair_data[p]["compat"]):
        d = pair_data[(a, b)]
        hung = d["hungarian_pairs"]
        if not hung:
            continue
        dists = [h[0] for h in hung]
        stats = quantile_stats(dists)
        below_03 = sum(1 for h in hung if h[0] < 0.3)
        below_05 = sum(1 for h in hung if h[0] < 0.5)
        print(f"\n  {a}↔{b} (compat={d['compat']:.3f})")
        print(f"    Hungarian dist: min={stats['min']:.4f} p25={stats['p25']:.4f} "
              f"med={stats['median']:.4f} p75={stats['p75']:.4f} max={stats['max']:.4f}")
        print(f"    <0.3: {below_03}/{stats['n']}  <0.5: {below_05}/{stats['n']}")

    # ── Phase 8: Partial vs. Full — Signal quality ────────────
    print("\n" + "=" * 70)
    print("PHASE 8: Signal Quality — Partial vs. Full Matching")
    print("=" * 70)

    # Key question: In compatible pairs, what % of nodes have distance < 0.5?
    # In incompatible pairs, what % of BEST nodes have distance < 0.5?
    # If incompatible best-k looks similar to compatible full → partial matching has signal.

    print("\n  Compatible pairs — Hungarian distance profile:")
    all_compat_dists = []
    for a, b in compatible_pairs:
        d = pair_data[(a, b)]
        for h in d["hungarian_pairs"]:
            all_compat_dists.append(h[0])
    if all_compat_dists:
        cs = quantile_stats(all_compat_dists)
        print(f"    N={cs['n']}  mean={cs['mean']:.4f}  std={cs['std']:.4f}  "
              f"median={cs['median']:.4f}  max={cs['max']:.4f}")
        print(f"    <0.3: {fraction_below(all_compat_dists, 0.3):.1%}  "
              f"<0.5: {fraction_below(all_compat_dists, 0.5):.1%}  "
              f"<0.6: {fraction_below(all_compat_dists, 0.6):.1%}")

    print("\n  Incompatible pairs — best-5 Hungarian distances pooled:")
    best5_incompat_dists = []
    for a, b in incompatible_pairs:
        d = pair_data[(a, b)]
        for h in d["hungarian_pairs"][:5]:
            best5_incompat_dists.append(h[0])
    if best5_incompat_dists:
        bs = quantile_stats(best5_incompat_dists)
        print(f"    N={bs['n']}  mean={bs['mean']:.4f}  std={bs['std']:.4f}  "
              f"median={bs['median']:.4f}  max={bs['max']:.4f}")
        print(f"    <0.3: {fraction_below(best5_incompat_dists, 0.3):.1%}  "
              f"<0.5: {fraction_below(best5_incompat_dists, 0.5):.1%}  "
              f"<0.6: {fraction_below(best5_incompat_dists, 0.6):.1%}")

    # Overlap analysis
    if all_compat_dists and best5_incompat_dists:
        compat_p75 = sorted(all_compat_dists)[int(len(all_compat_dists) * 0.75)]
        incompat_below = fraction_below(best5_incompat_dists, compat_p75)
        print(f"\n  Overlap: compatible p75={compat_p75:.4f}")
        print(f"  Fraction of incompat best-5 below compatible p75: {incompat_below:.1%}")
        if incompat_below > 0.3:
            print("  → SIGNIFICANT overlap: partial matches resemble compatible matches.")
            print("  → Partial structure matching has signal!")
        else:
            print("  → LOW overlap: even best-5 from incompat pairs are far from compatible.")
            print("  → Partial matching value is limited.")

    # ── Phase 9: Summary + Design Verdict ─────────────────────
    print("\n" + "=" * 70)
    print("PHASE 9: Summary + Design Verdict")
    print("=" * 70)

    print(f"\n  Landscapes:     {len(landscapes)}")
    print(f"  Pairs analyzed: {len(pair_data)}")
    print(f"  Compatible:     {len(compatible_pairs)}")
    print(f"  Incompatible:   {len(incompatible_pairs)}")

    if partial_candidates:
        print(f"\n  PARTIAL MATCH CANDIDATES: {len(partial_candidates)}")
        for a, b, k5 in partial_candidates:
            print(f"    {a}↔{b}: best-5 mean = {k5:.4f}")
        print("\n  VERDICT: Partial matching shows promise.")
        print("  Implementation suggestion: extract best-k pairs from incompatible")
        print("  domains and use them for targeted cross-domain transfer.")
    else:
        print("\n  No partial match candidates found (best-5 < 0.6 in any incompat pair).")

    # Additional thresholds for partial candidates
    for partial_thresh in (0.3, 0.4, 0.5):
        cands = [(a, b) for a, b in incompatible_pairs
                 if len(pair_data[(a, b)]["hungarian_pairs"]) >= 5
                 and statistics.mean([h[0] for h in pair_data[(a, b)]["hungarian_pairs"][:5]]) < partial_thresh]
        if cands:
            print(f"\n  At partial threshold {partial_thresh}: "
                  f"{len(cands)} pairs with best-5 < {partial_thresh}")

    t_total = time.time() - t0
    print(f"\n  Total runtime: {t_total:.1f}s")
    print("=" * 70)


if __name__ == "__main__":
    main()
