#!/usr/bin/env python3
"""
E₀ C136 — Feature Engineering for WL Node Matching
====================================================

Builds on C135's WL recursive neighborhood matching (33/44 = 75%).

Changes ONLY the Round-0 feature vector:
  - C135: [mean_q, std_q, degree, pos_fraction] → 4 features
  - C136: [mean_q, std_q, degree, pos_fraction,
           min_q, max_q, median_q,
           trace_load_mean, trace_load_std] → 9 features

Key insight: trace_load (U+F) is independent from quality (U-F)/(U+F).
Two edges with identical quality can have vastly different trace loads
depending on bootstrapper confidence. This provides a new differentiation axis.

Feature vector sizes at each depth:
  Depth 0: 9  (was 4)
  Depth 1: 27 (was 12)
  Depth 2: 63 (was 36)

Hypothesis: Richer Round-0 features → better differentiation of
low-degree nodes that were unmatched at C135.
"""

import json
import math
import os
import random
import sys
from collections import defaultdict
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.bootstrapper import bootstrap_landscape
from e0_controller.llm_adapter import LLMConfig, openai_call
from e0_controller.dream_mode import (
    NodeEquivalence,
    find_wl_node_equivalences, wl_node_fingerprints,
    wl_node_distance,
)
from e0_controller.canon_loader import load_canon_spec
from e0_controller.explore_dict_learning import GROUND_TRUTH, GROUND_TRUTH_REV

# Reuse building blocks from C134
from e0_controller.explore_c134_bootstrapper_teacher import (
    build_noise_mapping,
    batch_score_edges,
    inject_scores_into_spec,
    build_landscape,
    analyze_fingerprints,
    match_by_edge_position,
)


# ══════════════════════════════════════════════
# WL matching (same logic as C135, now with 9-dim features)
# ══════════════════════════════════════════════

def match_by_wl_nodes(
    en_L: Landscape,
    de_L: Landscape,
    depth: int = 2,
    quantile: float = 0.15,
) -> List[Tuple[str, str, float, int]]:
    """Match via WL recursive neighborhood fingerprints."""
    node_eqs = find_wl_node_equivalences(
        en_L, de_L,
        domain_a="EN", domain_b="DE",
        depth=depth,
        quantile=quantile,
    )

    print(f"  Node equivalences found: {len(node_eqs)}")
    if node_eqs:
        dists = [eq.distance for eq in node_eqs]
        print(f"  Distance range: {min(dists):.4f} — {max(dists):.4f}")

    # Mutual best match
    best_for_en: Dict[str, Tuple[str, float]] = {}
    vote_counts: Dict[Tuple[str, str], int] = defaultdict(int)

    for eq in node_eqs:
        en_node = eq.fp_a.node
        de_node = eq.fp_b.node
        conf = eq.confidence
        vote_counts[(en_node, de_node)] += 1
        if en_node not in best_for_en or conf > best_for_en[en_node][1]:
            best_for_en[en_node] = (de_node, conf)

    best_for_de: Dict[str, Tuple[str, float]] = {}
    for eq in node_eqs:
        en_node = eq.fp_a.node
        de_node = eq.fp_b.node
        conf = eq.confidence
        if de_node not in best_for_de or conf > best_for_de[de_node][1]:
            best_for_de[de_node] = (en_node, conf)

    results = []
    for en, (de, conf) in best_for_en.items():
        if de in best_for_de and best_for_de[de][0] == en:
            results.append((en, de, conf, vote_counts[(en, de)]))

    results.sort(key=lambda x: -x[2])
    return results


# ══════════════════════════════════════════════
# Scoring
# ══════════════════════════════════════════════

def score_correspondences(
    correspondences: List[Tuple[str, str, float, int]],
    method_name: str,
    verbose: bool = True,
) -> Tuple[int, int]:
    """Score correspondences against GROUND_TRUTH."""
    correct = 0
    wrong = 0

    if verbose:
        print(f"\n  {'─'*60}")
        print(f"  Method {method_name}: {len(correspondences)} pairs")
        print(f"  {'EN':<14} {'DE matched':<14} {'Expected':<14} "
              f"{'Conf':>7} {'Votes':>5}  Verdict")
        print(f"  {'─'*70}")

    for en, de, conf, votes in correspondences:
        expected = GROUND_TRUTH.get(en, "—")
        if expected == de:
            verdict = "✓"
            correct += 1
        elif expected == "—":
            verdict = "?"
        else:
            verdict = f"✗ (→{expected})"
            wrong += 1

        if verbose:
            print(f"  {en:<14} {de:<14} {expected:<14} "
                  f"{conf:>7.1f} {votes:>5}  {verdict}")

    n_gt = len(GROUND_TRUTH)
    prec = (f"{correct/(correct+wrong)*100:.0f}%"
            if correct + wrong > 0 else "—")

    if verbose:
        print(f"  → Correct={correct}, Wrong={wrong}, "
              f"Precision={prec}, Recall={correct}/{n_gt} "
              f"({correct/n_gt*100:.0f}%)")

    return correct, wrong


# ══════════════════════════════════════════════
# Diagnostic: show unmatched nodes
# ══════════════════════════════════════════════

def show_unmatched(
    correspondences: List[Tuple[str, str, float, int]],
    en_L: Landscape,
    de_L: Landscape,
    depth: int = 2,
):
    """Show details for nodes that were NOT matched."""
    matched_en = {en for en, de, _, _ in correspondences}
    unmatched = [en for en in sorted(GROUND_TRUTH) if en not in matched_en]

    if not unmatched:
        print("\n  All 44 nodes matched!")
        return

    print(f"\n  {'─'*60}")
    print(f"  UNMATCHED NODES: {len(unmatched)}")
    print(f"  {'─'*60}")

    # Compute fingerprints for analysis
    wl_en = {fp.node: fp for fp in wl_node_fingerprints(en_L, "EN", depth=depth)}
    wl_de = {fp.node: fp for fp in wl_node_fingerprints(de_L, "DE", depth=depth)}

    # Build adjacency for degree info
    def node_degree(landscape, node):
        return sum(1 for e in landscape.edges
                   if e.source == node or e.target == node)

    for en in unmatched:
        de_expected = GROUND_TRUTH[en]
        en_deg = node_degree(en_L, en)
        de_deg = node_degree(de_L, de_expected)

        fp_en = wl_en.get(en)
        fp_de = wl_de.get(de_expected)
        if fp_en and fp_de:
            dist = wl_node_distance(fp_en, fp_de)
            # Find closest wrong match
            best_wrong_dist = float('inf')
            best_wrong_node = "?"
            for de_node, fp in wl_de.items():
                if de_node != de_expected:
                    d = wl_node_distance(fp_en, fp)
                    if d < best_wrong_dist:
                        best_wrong_dist = d
                        best_wrong_node = de_node
            print(f"  {en:<14} → {de_expected:<14}  deg={en_deg}/{de_deg}  "
                  f"true_dist={dist:.4f}  "
                  f"closest_wrong={best_wrong_node} ({best_wrong_dist:.4f})  "
                  f"margin={dist - best_wrong_dist:+.4f}")
        else:
            print(f"  {en:<14} → {de_expected:<14}  deg={en_deg}/{de_deg}  "
                  f"NO FINGERPRINT")


# ══════════════════════════════════════════════
# Main experiment
# ══════════════════════════════════════════════

def run_experiment(noise_edges: int = 100):
    """C136: Feature Engineering for WL Node Matching."""
    print("=" * 72)
    print("  E₀ C136 — Feature Engineering for WL Node Matching")
    print(f"  Round-0: 9 features (was 4)")
    print(f"  [mean_q, std_q, degree, pos_frac, min_q, max_q, median_q,")
    print(f"   trace_load_mean, trace_load_std]")
    print(f"  Shared topology + {noise_edges} noise edges")
    print("=" * 72)

    eval_config = LLMConfig(temperature=0.0, max_tokens=4096)
    rng = random.Random(42)

    # ── Phase 1a: Load and augment canons ──
    print(f"\n{'─'*72}")
    print("  Phase 1a: Loading shared-topology canons + adding noise edges...")
    print(f"{'─'*72}")

    en_spec = load_canon_spec("english_basic")
    de_spec = load_canon_spec("german_basic")

    n_en_orig = len(en_spec["edges"])
    en_spec, de_spec = build_noise_mapping(
        en_spec, de_spec, rng, noise_edges=noise_edges,
    )
    n_en_total = len(en_spec["edges"])

    print(f"  EN: {n_en_orig} → {n_en_total} edges "
          f"(+{n_en_total - n_en_orig} noise)")
    print(f"  Avg degree: {2 * n_en_total / 44:.1f}")

    # ── Phase 1b: LLM scores edges (monolingual, 0-10) ──
    print(f"\n{'─'*72}")
    print("  Phase 1b: LLM scoring — monolingual relatedness 0-10...")
    print(f"{'─'*72}")

    en_pairs = [(e["from"], e["to"]) for e in en_spec["edges"]]
    de_pairs = [(e["from"], e["to"]) for e in de_spec["edges"]]

    en_scores = batch_score_edges(en_pairs, "English", eval_config)
    de_scores = batch_score_edges(de_pairs, "German", eval_config)

    # ── Phase 1c: Inject scores + bootstrap ──
    print(f"\n{'─'*72}")
    print("  Phase 1c: Bootstrapping landscapes with scored traces...")
    print(f"{'─'*72}")

    en_spec = inject_scores_into_spec(en_spec, en_scores)
    de_spec = inject_scores_into_spec(de_spec, de_scores)

    en_L = build_landscape(en_spec, "EN")
    de_L = build_landscape(de_spec, "DE")

    analyze_fingerprints(en_L, "EN")
    analyze_fingerprints(de_L, "DE")

    # Show feature vector info
    wl_en_d0 = wl_node_fingerprints(en_L, "EN", depth=0)
    wl_en_d1 = wl_node_fingerprints(en_L, "EN", depth=1)
    wl_en_d2 = wl_node_fingerprints(en_L, "EN", depth=2)
    print(f"\n  Feature vector sizes: D0={len(wl_en_d0[0].features)}, "
          f"D1={len(wl_en_d1[0].features)}, D2={len(wl_en_d2[0].features)}")

    # ── Phase 2: Playground ──
    print(f"\n{'='*72}")
    print("  Phase 2: Playground — structural matching WITHOUT LLM")
    print(f"{'='*72}")

    # Method A: Position-based (Oracle baseline)
    print(f"\n  Method A: Edge-position matching (baseline)...")
    corr_A = match_by_edge_position(en_L, de_L, en_pairs, de_pairs)
    print(f"  Correspondences: {len(corr_A)}")

    # Method D: WL at depth 0, 1, 2
    corr_D = {}
    for depth in [0, 1, 2]:
        print(f"\n  Method D{depth}: WL depth={depth} (9-dim Round-0)...")
        corr_D[depth] = match_by_wl_nodes(en_L, de_L, depth=depth)
        print(f"  Correspondences: {len(corr_D[depth])}")

    # ── Scoring ──
    print(f"\n{'='*72}")
    print("  Results")
    print(f"{'='*72}")

    c_A, w_A = score_correspondences(corr_A, "A (position)", verbose=False)

    results_D = {}
    for depth in [0, 1, 2]:
        verbose = (depth == 2)
        c, w = score_correspondences(
            corr_D[depth], f"D{depth} (WL depth={depth}, 9-dim)", verbose=verbose,
        )
        results_D[depth] = (c, w)

    # Unmatched analysis for best depth
    best_depth = max(results_D, key=lambda d: results_D[d][0])
    show_unmatched(corr_D[best_depth], en_L, de_L, depth=best_depth)

    # Summary table
    n_gt = len(GROUND_TRUTH)
    print(f"\n  {'='*60}")
    print(f"  C136 SUMMARY")
    print(f"  {'='*60}")
    print(f"  {'Method':<32} {'Correct':>7} {'Wrong':>6} {'Recall':>10}")
    print(f"  {'─'*58}")
    print(f"  {'A (position, oracle)':<32} {c_A:>7} {w_A:>6} "
          f"{c_A}/{n_gt} ({c_A/n_gt*100:.0f}%)")
    for depth in [0, 1, 2]:
        c, w = results_D[depth]
        label = f"D{depth} (WL d={depth}, 9-dim)"
        marker = " ←" if depth == best_depth else ""
        print(f"  {label:<32} {c:>7} {w:>6} "
              f"{c}/{n_gt} ({c/n_gt*100:.0f}%){marker}")

    print(f"\n  COMPARISON vs C135 (4-dim):")
    print(f"  {'Method':<24} {'C135 (4-dim)':>14} {'C136 (9-dim)':>14} {'Δ':>6}")
    print(f"  {'─'*60}")
    c135_results = {0: (11, 10), 1: (31, 1), 2: (33, 0)}
    for depth in [0, 1, 2]:
        c_old, w_old = c135_results[depth]
        c_new, w_new = results_D[depth]
        delta = c_new - c_old
        print(f"  {'D'+str(depth):<24} {c_old:>7}/{n_gt}      "
              f"{c_new:>7}/{n_gt}      {delta:>+4}")

    print(f"\n  Signal: Score 0–10, 9-dim features, seedless, no LLM in matching")
    print(f"  {'='*60}")


if __name__ == "__main__":
    noise = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    run_experiment(noise_edges=noise)
