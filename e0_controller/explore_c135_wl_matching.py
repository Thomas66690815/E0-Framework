#!/usr/bin/env python3
"""
E₀ C135 — WL-style Recursive Neighborhood Matching
=====================================================

Builds on C134b's confirmed architecture:
  - Bootstrapper as monolingual teacher (score 0-10)
  - Shared topology (44 nodes, 64 + noise edges)

Changes ONLY the matching method:
  - Method C (C134b): sorted quality profile → 9-13/44
  - Method D (C135):  WL recursive neighborhood → ???

WL refinement at depth k captures k-hop neighborhood structure.
Each round aggregates (mean, std) of neighbor features, building
increasingly distinctive node signatures.

Hypothesis: Depth-2 WL fingerprints should disambiguate nodes that
have similar quality distributions but different neighborhood contexts.
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
    domain_fingerprints, find_equivalences,
    find_node_equivalences, node_fingerprints,
    find_wl_node_equivalences, wl_node_fingerprints,
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
    match_by_find_equivalences,
    match_by_node_equivalences,
    extract_node_correspondences,
)


# ══════════════════════════════════════════════
# Method D: WL-style node matching
# ══════════════════════════════════════════════

def match_by_wl_nodes(
    en_L: Landscape,
    de_L: Landscape,
    depth: int = 2,
) -> List[Tuple[str, str, float, int]]:
    """Match via WL recursive neighborhood fingerprints."""
    node_eqs = find_wl_node_equivalences(
        en_L, de_L,
        domain_a="EN", domain_b="DE",
        depth=depth,
        quantile=0.15,
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
# Scoring helper
# ══════════════════════════════════════════════

def score_correspondences(
    correspondences: List[Tuple[str, str, float, int]],
    method_name: str,
    verbose: bool = True,
) -> Tuple[int, int]:
    """Score and optionally print correspondences against GROUND_TRUTH."""
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
# Main experiment
# ══════════════════════════════════════════════

def run_experiment(noise_edges: int = 100):
    """C135: WL recursive neighborhood matching."""
    print("=" * 72)
    print("  E₀ C135 — WL Recursive Neighborhood Matching")
    print(f"  Shared topology + {noise_edges} noise edges")
    print(f"  Score 0–10 → bootstrap_landscape()")
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

    # ── Phase 2: Playground ──
    print(f"\n{'='*72}")
    print("  Phase 2: Playground — structural matching WITHOUT LLM")
    print(f"{'='*72}")

    # Method A: Position-based (Oracle baseline)
    print(f"\n  Method A: Edge-position matching (baseline)...")
    corr_A = match_by_edge_position(en_L, de_L, en_pairs, de_pairs)
    print(f"  Correspondences: {len(corr_A)}")

    # Method C: Sorted profile (C134b baseline)
    print(f"\n  Method C: Node-eq sorted profile (C134b)...")
    corr_C = match_by_node_equivalences(en_L, de_L)
    print(f"  Correspondences: {len(corr_C)}")

    # Method D: WL at depth 0, 1, 2
    corr_D = {}
    for depth in [0, 1, 2]:
        print(f"\n  Method D{depth}: WL depth={depth}...")
        corr_D[depth] = match_by_wl_nodes(en_L, de_L, depth=depth)
        print(f"  Correspondences: {len(corr_D[depth])}")

    # ── Scoring ──
    print(f"\n{'='*72}")
    print("  Results")
    print(f"{'='*72}")

    c_A, w_A = score_correspondences(corr_A, "A (position)", verbose=False)
    c_C, w_C = score_correspondences(corr_C, "C (sorted profile)", verbose=False)

    results_D = {}
    for depth in [0, 1, 2]:
        verbose = (depth == 2)  # Full table only for best depth
        c, w = score_correspondences(
            corr_D[depth], f"D{depth} (WL depth={depth})", verbose=verbose,
        )
        results_D[depth] = (c, w)

    # Summary table
    n_gt = len(GROUND_TRUTH)
    print(f"\n  {'='*60}")
    print(f"  C135 SUMMARY")
    print(f"  {'='*60}")
    print(f"  {'Method':<28} {'Correct':>7} {'Wrong':>6} {'Recall':>10}")
    print(f"  {'─'*55}")
    print(f"  {'A (position, oracle)':<28} {c_A:>7} {w_A:>6} "
          f"{c_A}/{n_gt} ({c_A/n_gt*100:.0f}%)")
    print(f"  {'C (sorted profile)':<28} {c_C:>7} {w_C:>6} "
          f"{c_C}/{n_gt} ({c_C/n_gt*100:.0f}%)")
    for depth in [0, 1, 2]:
        c, w = results_D[depth]
        label = f"D{depth} (WL depth={depth})"
        marker = " ← KEY" if depth == 2 else ""
        print(f"  {label:<28} {c:>7} {w:>6} "
              f"{c}/{n_gt} ({c/n_gt*100:.0f}%){marker}")

    print(f"\n  Signal: Score 0–10, pure bootstrap, seedless, no LLM in matching")
    print(f"  {'='*60}")

    print(f"\n  HISTORICAL COMPARISON:")
    print(f"  C131b (seed=11, binary):       13/44 (30%)")
    print(f"  C132b (seed=8, LLM teach):     20/44 (45%)")
    print(f"  C133  (binary+pos):            44/44 (100%)")
    print(f"  C134b (sorted profile):         9/44 (20%)")
    c2, _ = results_D[2]
    print(f"  C135  (WL depth=2):           {c2:>3}/44 ({c2/44*100:.0f}%)")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    run_experiment(noise_edges=n)
