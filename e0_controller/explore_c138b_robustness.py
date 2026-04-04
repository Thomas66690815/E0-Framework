#!/usr/bin/env python3
"""
E₀ C138b — Robustness: Score Noise + Topology Perturbation
=============================================================

Two stress axes on the C137 pipeline (Hungarian + WL depth=2):

Axis 1 — Score perturbation:
  Add Gaussian noise to LLM scores before bootstrapping.
  σ = [0, 1, 2, 3] (scores clamped to 0–10)
  Tests: how robust is matching against noisy/inconsistent teaching?

Axis 2 — Topology perturbation:
  Break perfect isomorphism by adding asymmetric edges:
  N = [0, 5, 10, 20] edges added to DE only (not in EN).
  Tests: how strongly does 44/44 depend on perfect topology match?

Base config: noise=100, depth=2, Hungarian (minimal 100% from C138a).
LLM scores collected ONCE, then perturbed offline → fast iteration.
"""

import copy
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
# Matching + Scoring (reused from C138a)
# ══════════════════════════════════════════════

def match_hungarian(
    en_L: Landscape, de_L: Landscape, depth: int = 2,
) -> List[Tuple[str, str]]:
    node_eqs = find_wl_node_equivalences_hungarian(
        en_L, de_L, domain_a="EN", domain_b="DE", depth=depth,
    )
    return [(eq.fp_a.node, eq.fp_b.node) for eq in node_eqs]


def score_pairs(pairs: List[Tuple[str, str]]) -> Tuple[int, int]:
    correct = wrong = 0
    for en, de in pairs:
        expected = GROUND_TRUTH.get(en)
        if expected == de:
            correct += 1
        elif expected is not None:
            wrong += 1
    return correct, wrong


# ══════════════════════════════════════════════
# Score perturbation
# ══════════════════════════════════════════════

def perturb_scores(
    scores: Dict[Tuple[str, str], int],
    sigma: float,
    rng: random.Random,
) -> Dict[Tuple[str, str], int]:
    """Add Gaussian noise to scores, clamped to 0–10."""
    if sigma == 0:
        return dict(scores)
    result = {}
    for key, s in scores.items():
        noisy = s + rng.gauss(0, sigma)
        result[key] = max(0, min(10, round(noisy)))
    return result


# ══════════════════════════════════════════════
# Topology perturbation
# ══════════════════════════════════════════════

def add_asymmetric_edges(
    de_spec: dict,
    n_extra: int,
    rng: random.Random,
) -> dict:
    """Add edges to DE that have NO counterpart in EN.

    Breaks perfect isomorphism by inserting random DE-only edges.
    """
    if n_extra == 0:
        return de_spec

    de_spec = copy.deepcopy(de_spec)
    de_nodes = [n if isinstance(n, str) else n["id"] for n in de_spec["nodes"]]
    de_existing = {(e["from"], e["to"]) for e in de_spec["edges"]}

    all_possible = [
        (a, b) for a in de_nodes for b in de_nodes
        if a != b and (a, b) not in de_existing
    ]
    rng.shuffle(all_possible)

    added = 0
    for src, tgt in all_possible:
        if added >= n_extra:
            break
        de_spec["edges"].append({
            "from": src,
            "to": tgt,
            "delta": 0.3,
            "resistance": 0.3,
            "initial_U": 0,
            "initial_F": 0,
        })
        de_existing.add((src, tgt))
        added += 1

    return de_spec


# ══════════════════════════════════════════════
# Build landscape from spec + scores
# ══════════════════════════════════════════════

def build_from_scores(
    spec: dict, scores: Dict[Tuple[str, str], int], language: str,
) -> Landscape:
    """Inject scores into spec copy and bootstrap landscape."""
    spec = copy.deepcopy(spec)
    spec = inject_scores_into_spec(spec, scores)
    return build_landscape(spec, language)


# ══════════════════════════════════════════════
# Main experiment
# ══════════════════════════════════════════════

def run_experiment():
    """C138b: Score noise + topology perturbation."""
    print("=" * 72)
    print("  E₀ C138b — Robustness: Score Noise + Topology Perturbation")
    print("  Base: noise=100, depth=2, Hungarian")
    print("  Axis 1: score σ = [0, 1, 2, 3]")
    print("  Axis 2: asymmetric DE edges = [0, 5, 10, 20]")
    print("=" * 72)

    eval_config = LLMConfig(temperature=0.0, max_tokens=4096)
    rng = random.Random(42)

    # ── Phase 1: Build base canons + score ONCE ──
    print(f"\n{'─'*72}")
    print("  Phase 1: Load canons, add 100 noise edges, score via LLM...")
    print(f"{'─'*72}")

    en_spec = load_canon_spec("english_basic")
    de_spec_base = load_canon_spec("german_basic")

    en_spec, de_spec_base = build_noise_mapping(
        en_spec, de_spec_base, rng, noise_edges=100,
    )

    en_pairs = [(e["from"], e["to"]) for e in en_spec["edges"]]
    de_pairs_base = [(e["from"], e["to"]) for e in de_spec_base["edges"]]

    en_scores_clean = batch_score_edges(en_pairs, "English", eval_config)
    de_scores_clean = batch_score_edges(de_pairs_base, "German", eval_config)

    print(f"  EN: {len(en_pairs)} edges scored")
    print(f"  DE: {len(de_pairs_base)} edges scored")

    # ── Phase 2a: Score perturbation ──
    sigmas = [0, 1, 2, 3]
    n_gt = len(GROUND_TRUTH)

    print(f"\n{'='*72}")
    print("  AXIS 1: Score Perturbation (Gaussian noise on scores)")
    print(f"{'='*72}")

    score_results: Dict[float, Tuple[int, int]] = {}

    for sigma in sigmas:
        perturb_rng = random.Random(123)  # deterministic perturbation
        en_scores_p = perturb_scores(en_scores_clean, sigma, perturb_rng)
        de_scores_p = perturb_scores(de_scores_clean, sigma, perturb_rng)

        en_L = build_from_scores(en_spec, en_scores_p, "EN")
        de_L = build_from_scores(de_spec_base, de_scores_p, "DE")

        pairs = match_hungarian(en_L, de_L, depth=2)
        c, w = score_pairs(pairs)
        score_results[sigma] = (c, w)

        prec = f"{c/(c+w)*100:.0f}%" if c + w > 0 else "—"
        print(f"  σ={sigma}: {c}/44 correct, {w} wrong, precision={prec}")

    # ── Phase 2b: Topology perturbation ──
    asymmetric_counts = [0, 5, 10, 20]

    print(f"\n{'='*72}")
    print("  AXIS 2: Topology Perturbation (asymmetric DE-only edges)")
    print(f"{'='*72}")

    topo_results: Dict[int, Tuple[int, int]] = {}

    for n_extra in asymmetric_counts:
        perturb_rng = random.Random(456)
        de_spec_pert = add_asymmetric_edges(de_spec_base, n_extra, perturb_rng)

        # Score new DE edges (the asymmetric ones need scores too)
        de_pairs_pert = [(e["from"], e["to"]) for e in de_spec_pert["edges"]]
        new_pairs = [p for p in de_pairs_pert if p not in de_scores_clean]

        de_scores_pert = dict(de_scores_clean)
        if new_pairs:
            new_scores = batch_score_edges(new_pairs, "German", eval_config)
            de_scores_pert.update(new_scores)

        en_L = build_from_scores(en_spec, en_scores_clean, "EN")
        de_L = build_from_scores(de_spec_pert, de_scores_pert, "DE")

        n_en = len(en_L.edges)
        n_de = len(de_L.edges)

        pairs = match_hungarian(en_L, de_L, depth=2)
        c, w = score_pairs(pairs)
        topo_results[n_extra] = (c, w)

        prec = f"{c/(c+w)*100:.0f}%" if c + w > 0 else "—"
        print(f"  +{n_extra:>2} DE-only edges "
              f"(EN={n_en}, DE={n_de}): "
              f"{c}/44 correct, {w} wrong, precision={prec}")

    # ── Phase 2c: Combined stress ──
    print(f"\n{'='*72}")
    print("  COMBINED: Score noise + topology perturbation")
    print(f"{'='*72}")

    combined_results: Dict[Tuple[float, int], Tuple[int, int]] = {}
    combo_sigmas = [1, 2]
    combo_extras = [5, 10]

    for sigma in combo_sigmas:
        for n_extra in combo_extras:
            perturb_rng_s = random.Random(123)
            perturb_rng_t = random.Random(456)

            en_scores_p = perturb_scores(en_scores_clean, sigma, perturb_rng_s)
            de_scores_p = perturb_scores(de_scores_clean, sigma, perturb_rng_s)

            de_spec_pert = add_asymmetric_edges(
                de_spec_base, n_extra, perturb_rng_t,
            )
            de_pairs_pert = [(e["from"], e["to"]) for e in de_spec_pert["edges"]]
            new_pairs = [p for p in de_pairs_pert if p not in de_scores_p]
            if new_pairs:
                # Score new edges with perturbation
                new_raw = batch_score_edges(new_pairs, "German", eval_config)
                new_perturbed = perturb_scores(new_raw, sigma, perturb_rng_s)
                de_scores_p.update(new_perturbed)

            en_L = build_from_scores(en_spec, en_scores_p, "EN")
            de_L = build_from_scores(de_spec_pert, de_scores_p, "DE")

            pairs = match_hungarian(en_L, de_L, depth=2)
            c, w = score_pairs(pairs)
            combined_results[(sigma, n_extra)] = (c, w)

            prec = f"{c/(c+w)*100:.0f}%" if c + w > 0 else "—"
            print(f"  σ={sigma}, +{n_extra} DE-only: "
                  f"{c}/44 correct, {w} wrong, precision={prec}")

    # ── Summary ──
    print(f"\n{'='*72}")
    print("  C138b SUMMARY")
    print(f"{'='*72}")

    print(f"\n  Score Perturbation (topology intact):")
    print(f"  {'σ':>3}  {'Correct':>7}  {'Wrong':>5}  {'Precision':>9}")
    print(f"  {'─'*30}")
    for sigma in sigmas:
        c, w = score_results[sigma]
        prec = f"{c/(c+w)*100:.0f}%" if c + w > 0 else "—"
        print(f"  {sigma:>3}  {c:>7}  {w:>5}  {prec:>9}")

    print(f"\n  Topology Perturbation (scores clean):")
    print(f"  {'Extra':>5}  {'EN edges':>8}  {'DE edges':>8}  "
          f"{'Correct':>7}  {'Wrong':>5}  {'Precision':>9}")
    print(f"  {'─'*50}")
    for n_extra in asymmetric_counts:
        c, w = topo_results[n_extra]
        prec = f"{c/(c+w)*100:.0f}%" if c + w > 0 else "—"
        n_de = len(de_spec_base["edges"]) + n_extra
        print(f"  {n_extra:>5}  {len(en_pairs):>8}  {n_de:>8}  "
              f"{c:>7}  {w:>5}  {prec:>9}")

    print(f"\n  Combined Stress:")
    print(f"  {'σ':>3}  {'Extra':>5}  {'Correct':>7}  {'Wrong':>5}  "
          f"{'Precision':>9}")
    print(f"  {'─'*35}")
    for sigma in combo_sigmas:
        for n_extra in combo_extras:
            c, w = combined_results[(sigma, n_extra)]
            prec = f"{c/(c+w)*100:.0f}%" if c + w > 0 else "—"
            print(f"  {sigma:>3}  {n_extra:>5}  {c:>7}  {w:>5}  "
                  f"{prec:>9}")

    # ── Degradation analysis ──
    print(f"\n  {'='*60}")
    print(f"  DEGRADATION THRESHOLDS")
    print(f"  {'='*60}")

    first_score_drop = None
    for sigma in sigmas:
        c, w = score_results[sigma]
        if c < 44 and first_score_drop is None:
            first_score_drop = sigma
    if first_score_drop:
        print(f"  Score noise: first drop at σ={first_score_drop}")
    else:
        print(f"  Score noise: NO degradation up to σ=3")

    first_topo_drop = None
    for n_extra in asymmetric_counts:
        c, w = topo_results[n_extra]
        if c < 44 and first_topo_drop is None:
            first_topo_drop = n_extra
    if first_topo_drop:
        print(f"  Topology: first drop at +{first_topo_drop} asymmetric edges")
    else:
        print(f"  Topology: NO degradation up to +20 asymmetric edges")

    print(f"\n  {'='*60}")


if __name__ == "__main__":
    run_experiment()
