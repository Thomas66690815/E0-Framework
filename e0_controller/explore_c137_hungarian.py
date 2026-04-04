#!/usr/bin/env python3
"""
E₀ C137 — Hungarian Optimal Assignment for WL Node Matching
=============================================================

C136 diagnosis: 6/10 unmatched nodes have correct pair CLOSER,
but mutual-best-match blocks them (another EN node "steals" the
DE partner). 4/10 have genuine semantic confusion.

Fix: Replace greedy mutual-best with Hungarian algorithm
(scipy.optimize.linear_sum_assignment) — globally optimal 1:1
assignment minimizing total WL distance.

Expected: ~40/44 (recover 6 from Group 1, 4 in Group 2 remain).
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
    find_wl_node_equivalences_hungarian,
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
# Method E: Hungarian optimal assignment
# ══════════════════════════════════════════════

def match_by_hungarian(
    en_L: Landscape,
    de_L: Landscape,
    depth: int = 2,
) -> List[Tuple[str, str, float, int]]:
    """Match via Hungarian algorithm on WL distance matrix."""
    node_eqs = find_wl_node_equivalences_hungarian(
        en_L, de_L,
        domain_a="EN", domain_b="DE",
        depth=depth,
    )

    print(f"  Assignments: {len(node_eqs)}")
    if node_eqs:
        dists = [eq.distance for eq in node_eqs]
        print(f"  Distance range: {min(dists):.4f} — {max(dists):.4f}")
        print(f"  Total cost: {sum(dists):.4f}")
        print(f"  Mean dist:  {sum(dists)/len(dists):.4f}")

    results = []
    for eq in node_eqs:
        results.append((eq.fp_a.node, eq.fp_b.node, eq.confidence, 1))

    results.sort(key=lambda x: -x[2])
    return results


# ══════════════════════════════════════════════
# Method D: Mutual-best (C136 baseline for comparison)
# ══════════════════════════════════════════════

def match_by_wl_mutual_best(
    en_L: Landscape,
    de_L: Landscape,
    depth: int = 2,
    quantile: float = 0.15,
) -> List[Tuple[str, str, float, int]]:
    """Match via mutual best (C136 method for comparison)."""
    node_eqs = find_wl_node_equivalences(
        en_L, de_L,
        domain_a="EN", domain_b="DE",
        depth=depth,
        quantile=quantile,
    )

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
              f"{'Conf':>7}  Verdict")
        print(f"  {'─'*60}")

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
                  f"{conf:>7.1f}  {verdict}")

    n_gt = len(GROUND_TRUTH)
    prec = (f"{correct/(correct+wrong)*100:.0f}%"
            if correct + wrong > 0 else "—")

    if verbose:
        print(f"  → Correct={correct}, Wrong={wrong}, "
              f"Precision={prec}, Recall={correct}/{n_gt} "
              f"({correct/n_gt*100:.0f}%)")

    return correct, wrong


# ══════════════════════════════════════════════
# Diagnostic: show wrong assignments
# ══════════════════════════════════════════════

def show_wrong_assignments(
    correspondences: List[Tuple[str, str, float, int]],
    en_L: Landscape,
    de_L: Landscape,
    depth: int = 2,
):
    """Show details for wrongly assigned nodes."""
    wl_en = {fp.node: fp for fp in wl_node_fingerprints(en_L, "EN", depth=depth)}
    wl_de = {fp.node: fp for fp in wl_node_fingerprints(de_L, "DE", depth=depth)}

    wrongs = []
    for en, de, conf, _ in correspondences:
        expected = GROUND_TRUTH.get(en, None)
        if expected and expected != de:
            wrongs.append((en, de, expected, conf))

    if not wrongs:
        print("\n  No wrong assignments!")
        return

    def node_degree(landscape, node):
        return sum(1 for e in landscape.edges
                   if e.source == node or e.target == node)

    print(f"\n  {'─'*60}")
    print(f"  WRONG ASSIGNMENTS: {len(wrongs)}")
    print(f"  {'─'*60}")
    for en, de_got, de_expected, conf in wrongs:
        fp_en = wl_en[en]
        fp_de_got = wl_de[de_got]
        fp_de_exp = wl_de[de_expected]
        d_got = wl_node_distance(fp_en, fp_de_got)
        d_exp = wl_node_distance(fp_en, fp_de_exp)
        en_deg = node_degree(en_L, en)
        print(f"  {en:<12} → got {de_got:<12} (d={d_got:.4f})  "
              f"expected {de_expected:<12} (d={d_exp:.4f})  "
              f"deg={en_deg}  Δ={d_exp - d_got:+.4f}")


# ══════════════════════════════════════════════
# Main experiment
# ══════════════════════════════════════════════

def run_experiment(noise_edges: int = 100):
    """C137: Hungarian optimal assignment for WL matching."""
    print("=" * 72)
    print("  E₀ C137 — Hungarian Optimal Assignment")
    print(f"  WL depth=2, 9-dim Round-0 features")
    print(f"  Shared topology + {noise_edges} noise edges")
    print(f"  Hungarian (global optimal) vs Mutual-Best (greedy)")
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

    # ── Phase 1b: LLM scores ──
    print(f"\n{'─'*72}")
    print("  Phase 1b: LLM scoring — monolingual relatedness 0-10...")
    print(f"{'─'*72}")

    en_pairs = [(e["from"], e["to"]) for e in en_spec["edges"]]
    de_pairs = [(e["from"], e["to"]) for e in de_spec["edges"]]

    en_scores = batch_score_edges(en_pairs, "English", eval_config)
    de_scores = batch_score_edges(de_pairs, "German", eval_config)

    # ── Phase 1c: Inject + bootstrap ──
    print(f"\n{'─'*72}")
    print("  Phase 1c: Bootstrapping landscapes...")
    print(f"{'─'*72}")

    en_spec = inject_scores_into_spec(en_spec, en_scores)
    de_spec = inject_scores_into_spec(de_spec, de_scores)

    en_L = build_landscape(en_spec, "EN")
    de_L = build_landscape(de_spec, "DE")

    analyze_fingerprints(en_L, "EN")
    analyze_fingerprints(de_L, "DE")

    # ── Phase 2: Playground ──
    print(f"\n{'='*72}")
    print("  Phase 2: Playground — structural matching WITHOUT LLM")
    print(f"{'='*72}")

    # Method A: Position baseline
    print(f"\n  Method A: Edge-position matching (oracle baseline)...")
    corr_A = match_by_edge_position(en_L, de_L, en_pairs, de_pairs)

    # Method D: Mutual-best (C136)
    print(f"\n  Method D: WL depth=2 + mutual-best (C136 baseline)...")
    corr_D = match_by_wl_mutual_best(en_L, de_L, depth=2)
    print(f"  Correspondences: {len(corr_D)}")

    # Method E: Hungarian
    print(f"\n  Method E: WL depth=2 + Hungarian (C137)...")
    corr_E = match_by_hungarian(en_L, de_L, depth=2)

    # Also test Hungarian at depth 0, 1
    corr_E_depths = {}
    for depth in [0, 1, 2]:
        print(f"\n  Method E{depth}: Hungarian depth={depth}...")
        corr_E_depths[depth] = match_by_hungarian(en_L, de_L, depth=depth)

    # ── Scoring ──
    print(f"\n{'='*72}")
    print("  Results")
    print(f"{'='*72}")

    c_A, w_A = score_correspondences(corr_A, "A (position)", verbose=False)
    c_D, w_D = score_correspondences(corr_D, "D (mutual-best)", verbose=False)

    # Full table for Hungarian depth=2
    c_E, w_E = score_correspondences(corr_E, "E (Hungarian d=2)", verbose=True)

    # Diagnostic for wrong assignments
    show_wrong_assignments(corr_E, en_L, de_L, depth=2)

    # Hungarian at all depths
    results_E = {}
    for depth in [0, 1, 2]:
        c, w = score_correspondences(
            corr_E_depths[depth],
            f"E{depth} (Hungarian d={depth})",
            verbose=False,
        )
        results_E[depth] = (c, w)

    # Summary
    n_gt = len(GROUND_TRUTH)
    print(f"\n  {'='*60}")
    print(f"  C137 SUMMARY")
    print(f"  {'='*60}")
    print(f"  {'Method':<32} {'Correct':>7} {'Wrong':>6} {'Prec':>6} {'Recall':>10}")
    print(f"  {'─'*65}")
    print(f"  {'A (position, oracle)':<32} {c_A:>7} {w_A:>6} {'100%':>6} "
          f"{c_A}/{n_gt} ({c_A/n_gt*100:.0f}%)")
    print(f"  {'D (mutual-best, C136)':<32} {c_D:>7} {w_D:>6} "
          f"{'100%' if w_D == 0 else f'{c_D/(c_D+w_D)*100:.0f}%':>6} "
          f"{c_D}/{n_gt} ({c_D/n_gt*100:.0f}%)")

    for depth in [0, 1, 2]:
        c, w = results_E[depth]
        label = f"E{depth} (Hungarian d={depth})"
        prec = f"{c/(c+w)*100:.0f}%" if c + w > 0 else "—"
        marker = " ← KEY" if depth == 2 else ""
        print(f"  {label:<32} {c:>7} {w:>6} {prec:>6} "
              f"{c}/{n_gt} ({c/n_gt*100:.0f}%){marker}")

    # Comparison table
    c136_results = {0: (15, 9), 1: (29, 4), 2: (34, 0)}
    print(f"\n  COMPARISON — Mutual-Best vs Hungarian:")
    print(f"  {'Depth':<10} {'Mutual-Best':>14} {'Hungarian':>14} {'Δ correct':>12}")
    print(f"  {'─'*52}")
    for depth in [0, 1, 2]:
        c_old, w_old = c136_results[depth]
        c_new, w_new = results_E[depth]
        print(f"  {'D'+str(depth):<10} {c_old:>7}/{n_gt}      "
              f"{c_new:>7}/{n_gt}      {c_new - c_old:>+6}")

    print(f"\n  Signal: Score 0–10, 9-dim, WL depth=2, seedless, no LLM in matching")
    print(f"  {'='*60}")


if __name__ == "__main__":
    noise = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    run_experiment(noise_edges=noise)
