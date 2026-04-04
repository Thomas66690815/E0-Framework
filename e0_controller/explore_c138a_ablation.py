#!/usr/bin/env python3
"""
E₀ C138a — Ablation Matrix
============================

Systematic test of ALL combinations that contributed to C137's 44/44:

  depth      × [0, 1, 2]
  noise      × [100, 200, 300]
  algorithm  × [mutual-best, Hungarian]

= 3 × 3 × 2 = 18 data points per run.

LLM scoring is done once per noise level (the expensive step).
Matching is fast and runs all depth × algorithm combos on the same landscapes.

Goal: identify the minimal configuration for near-perfect performance
and isolate which component contributes most.
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
    find_wl_node_equivalences,
    find_wl_node_equivalences_hungarian,
    wl_node_fingerprints, wl_node_distance,
)
from e0_controller.canon_loader import load_canon_spec
from e0_controller.explore_dict_learning import GROUND_TRUTH, GROUND_TRUTH_REV

from e0_controller.explore_c134_bootstrapper_teacher import (
    build_noise_mapping,
    batch_score_edges,
    inject_scores_into_spec,
    build_landscape,
)


# ══════════════════════════════════════════════
# Matching methods
# ══════════════════════════════════════════════

def match_mutual_best(
    en_L: Landscape, de_L: Landscape, depth: int, quantile: float = 0.15,
) -> List[Tuple[str, str]]:
    """Mutual-best matching (C135/C136 method)."""
    node_eqs = find_wl_node_equivalences(
        en_L, de_L, domain_a="EN", domain_b="DE",
        depth=depth, quantile=quantile,
    )

    best_for_en: Dict[str, Tuple[str, float]] = {}
    for eq in node_eqs:
        en, de, conf = eq.fp_a.node, eq.fp_b.node, eq.confidence
        if en not in best_for_en or conf > best_for_en[en][1]:
            best_for_en[en] = (de, conf)

    best_for_de: Dict[str, Tuple[str, float]] = {}
    for eq in node_eqs:
        en, de, conf = eq.fp_a.node, eq.fp_b.node, eq.confidence
        if de not in best_for_de or conf > best_for_de[de][1]:
            best_for_de[de] = (en, conf)

    results = []
    for en, (de, _) in best_for_en.items():
        if de in best_for_de and best_for_de[de][0] == en:
            results.append((en, de))
    return results


def match_hungarian(
    en_L: Landscape, de_L: Landscape, depth: int,
) -> List[Tuple[str, str]]:
    """Hungarian optimal assignment (C137 method)."""
    node_eqs = find_wl_node_equivalences_hungarian(
        en_L, de_L, domain_a="EN", domain_b="DE", depth=depth,
    )
    return [(eq.fp_a.node, eq.fp_b.node) for eq in node_eqs]


def score_pairs(pairs: List[Tuple[str, str]]) -> Tuple[int, int]:
    """Score against ground truth. Returns (correct, wrong)."""
    correct = wrong = 0
    for en, de in pairs:
        expected = GROUND_TRUTH.get(en)
        if expected == de:
            correct += 1
        elif expected is not None:
            wrong += 1
    return correct, wrong


# ══════════════════════════════════════════════
# Build landscapes for a given noise level
# ══════════════════════════════════════════════

def build_landscapes_for_noise(
    noise_edges: int, eval_config: LLMConfig,
) -> Tuple[Landscape, Landscape]:
    """Load canons, add noise, score via LLM, bootstrap landscapes."""
    rng = random.Random(42)

    en_spec = load_canon_spec("english_basic")
    de_spec = load_canon_spec("german_basic")

    en_spec, de_spec = build_noise_mapping(
        en_spec, de_spec, rng, noise_edges=noise_edges,
    )

    en_pairs = [(e["from"], e["to"]) for e in en_spec["edges"]]
    de_pairs = [(e["from"], e["to"]) for e in de_spec["edges"]]

    en_scores = batch_score_edges(en_pairs, "English", eval_config)
    de_scores = batch_score_edges(de_pairs, "German", eval_config)

    en_spec = inject_scores_into_spec(en_spec, en_scores)
    de_spec = inject_scores_into_spec(de_spec, de_scores)

    en_L = build_landscape(en_spec, "EN")
    de_L = build_landscape(de_spec, "DE")

    return en_L, de_L


# ══════════════════════════════════════════════
# Main ablation matrix
# ══════════════════════════════════════════════

def run_ablation():
    """C138a: Systematic ablation matrix."""
    print("=" * 72)
    print("  E₀ C138a — Ablation Matrix")
    print("  depth × noise × algorithm = 3 × 3 × 2 = 18 data points")
    print("=" * 72)

    eval_config = LLMConfig(temperature=0.0, max_tokens=4096)

    noise_levels = [100, 200, 300]
    depths = [0, 1, 2]
    algorithms = [
        ("MutBest", match_mutual_best),
        ("Hungarian", match_hungarian),
    ]

    # Collect results: (noise, depth, algo_name) → (correct, wrong, n_pairs)
    results: Dict[Tuple[int, int, str], Tuple[int, int, int]] = {}

    for noise in noise_levels:
        print(f"\n{'═'*72}")
        print(f"  Noise = {noise} edges")
        print(f"{'═'*72}")

        en_L, de_L = build_landscapes_for_noise(noise, eval_config)
        n_edges = len(en_L.edges)
        print(f"  Landscapes: {n_edges} edges each, "
              f"avg degree = {2*n_edges/44:.1f}")

        for depth in depths:
            for algo_name, algo_fn in algorithms:
                pairs = algo_fn(en_L, de_L, depth)
                correct, wrong = score_pairs(pairs)
                n = len(pairs)
                results[(noise, depth, algo_name)] = (correct, wrong, n)

    # ── Summary table ──
    n_gt = len(GROUND_TRUTH)

    print(f"\n\n{'='*72}")
    print(f"  C138a ABLATION MATRIX — RESULTS")
    print(f"{'='*72}")

    # Table header
    header = f"  {'Noise':>5}  {'Depth':>5}  {'Algorithm':<10} "
    header += f"{'Correct':>7}  {'Wrong':>5}  {'Pairs':>5}  "
    header += f"{'Prec':>6}  {'Recall':>10}"
    print(header)
    print(f"  {'─'*68}")

    for noise in noise_levels:
        for depth in depths:
            for algo_name, _ in algorithms:
                c, w, n = results[(noise, depth, algo_name)]
                prec = f"{c/(c+w)*100:.0f}%" if c + w > 0 else "—"
                recall = f"{c}/{n_gt} ({c/n_gt*100:.0f}%)"
                print(f"  {noise:>5}  {depth:>5}  {algo_name:<10} "
                      f"{c:>7}  {w:>5}  {n:>5}  {prec:>6}  {recall:>10}")
        print(f"  {'─'*68}")

    # ── Pivot: Algorithm comparison ──
    print(f"\n  PIVOT: Hungarian gain over Mutual-Best")
    print(f"  {'Noise':>5}  {'Depth':>5}  {'MutBest':>10}  "
          f"{'Hungarian':>10}  {'Δ':>6}")
    print(f"  {'─'*45}")

    for noise in noise_levels:
        for depth in depths:
            c_mb = results[(noise, depth, "MutBest")][0]
            c_hu = results[(noise, depth, "Hungarian")][0]
            delta = c_hu - c_mb
            print(f"  {noise:>5}  {depth:>5}  {c_mb:>7}/44  "
                  f"{c_hu:>7}/44  {delta:>+4}")

    # ── Pivot: Depth comparison (Hungarian only) ──
    print(f"\n  PIVOT: Depth comparison (Hungarian)")
    print(f"  {'Noise':>5}  {'D0':>8}  {'D1':>8}  {'D2':>8}")
    print(f"  {'─'*38}")

    for noise in noise_levels:
        vals = []
        for depth in depths:
            c = results[(noise, depth, "Hungarian")][0]
            w = results[(noise, depth, "Hungarian")][1]
            vals.append(f"{c}/{n_gt}" + (f" ({w}✗)" if w else ""))
        print(f"  {noise:>5}  {vals[0]:>8}  {vals[1]:>8}  {vals[2]:>8}")

    # ── Key findings ──
    print(f"\n  {'='*60}")
    print(f"  KEY FINDINGS")
    print(f"  {'='*60}")

    # Best minimal config
    for depth in depths:
        for algo_name, _ in algorithms:
            all_perfect = all(
                results[(n, depth, algo_name)][0] == n_gt
                and results[(n, depth, algo_name)][1] == 0
                for n in noise_levels
            )
            if all_perfect:
                print(f"  ✓ {algo_name} + depth={depth}: "
                      f"44/44 across ALL noise levels")

    # Worst configs
    worst = min(results.items(), key=lambda x: x[1][0])
    k, (c, w, _) = worst
    print(f"  ✗ Worst: noise={k[0]}, depth={k[1]}, {k[2]}: "
          f"{c}/44 correct, {w} wrong")

    # Hungarian dominance
    hu_wins = sum(
        1 for n in noise_levels for d in depths
        if results[(n, d, "Hungarian")][0] > results[(n, d, "MutBest")][0]
    )
    hu_ties = sum(
        1 for n in noise_levels for d in depths
        if results[(n, d, "Hungarian")][0] == results[(n, d, "MutBest")][0]
    )
    print(f"  Hungarian wins: {hu_wins}/9, ties: {hu_ties}/9")

    print(f"\n  {'='*60}")


if __name__ == "__main__":
    run_ablation()
