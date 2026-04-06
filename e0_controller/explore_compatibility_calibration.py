#!/usr/bin/env python3
"""
E₀ C169 — Compatibility Threshold Calibration
================================================

Empirical calibration of dream_compatibility() across diverse landscape
types, answering two open questions from the Multi-Domain Dream Analysis:

  Q1: Does dream_compatibility() work on LLM-scored landscapes
      (not just curriculum-trained canons)?
  Q2: What is the right threshold? (0.6 was based on only 3 pairs)

Landscape pool (8 domains, 28 pairs):
  - 3 canon-based (curriculum-trained): EN, DE, ONTO
  - 2 LLM-proposed (bootstrapped):     LLM_COOKING, LLM_PROJECT
  - 2 random (bootstrapped):           RND_44, RND_51
  - 1 canon raw (no training):         EN_RAW

Expected structure:
  - EN↔DE: compatible (near-isomorphic, same node count, similar topology)
  - EN↔EN_RAW: same topology, different historization → measures H effect
  - LLM domains: unknown structure → empirical discovery
  - RND domains: random topology → likely incompatible with everything

Phases:
  1. Landscape construction (canons + LLM + random)
  2. Curriculum training (canon domains only)
  3. Full compatibility matrix (all 28 pairs)
  4. Threshold analysis (gap detection, ROC-style)
  5. Cross-check: does training change compatibility?
  6. Summary + recommendation
"""

import sys
import os
import time
import random
import math
from itertools import combinations

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from e0_controller.canon_loader import load_canon
from e0_controller.curriculum import CurriculumRunner
from e0_controller.bootstrapper import bootstrap_landscape
from e0_controller.landscape import Landscape
from e0_controller.primitives import Outcome
from e0_controller.dream_mode import (
    dream_compatibility,
    is_dream_compatible,
    dream_readiness,
    wl_node_fingerprints,
)

EXEC_FN = lambda s, t: Outcome.SUCCESS  # noqa: E731


# ──────────────────────────────────────────────
# Landscape builders
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
            {"from": "REVIEW", "to": "DEPLOYMENT", "delta": 0.7, "resistance": 0.3, "initial_U": 8, "initial_F": 1, "confidence": 0.9},
            {"from": "DEPLOYMENT", "to": "MONITORING", "delta": 0.3, "resistance": 0.5, "initial_U": 5, "initial_F": 2, "confidence": 0.7},
            {"from": "MONITORING", "to": "FEEDBACK", "delta": 0.4, "resistance": 0.4, "initial_U": 4, "initial_F": 3, "confidence": 0.6},
            {"from": "FEEDBACK", "to": "REQUIREMENTS", "delta": 0.5, "resistance": 0.6, "initial_U": 3, "initial_F": 3, "confidence": 0.5},
            {"from": "PLANNING", "to": "REQUIREMENTS", "delta": 0.6, "resistance": 0.3, "initial_U": 7, "initial_F": 1, "confidence": 0.85},
            {"from": "TESTING", "to": "IMPLEMENTATION", "delta": 0.4, "resistance": 0.7, "initial_U": 2, "initial_F": 4, "confidence": 0.5},
            {"from": "REVIEW", "to": "DESIGN", "delta": 0.3, "resistance": 0.6, "initial_U": 2, "initial_F": 3, "confidence": 0.5},
            {"from": "IMPLEMENTATION", "to": "DOCUMENTATION", "delta": 0.4, "resistance": 0.4, "initial_U": 5, "initial_F": 2, "confidence": 0.7},
            {"from": "DOCUMENTATION", "to": "DEPLOYMENT", "delta": 0.3, "resistance": 0.3, "initial_U": 6, "initial_F": 1, "confidence": 0.8},
        ],
    }
    return bootstrap_landscape(spec)


# ──────────────────────────────────────────────
# Phase 1: Landscape Construction
# ──────────────────────────────────────────────

def phase_construction():
    """Build all 8 landscapes."""
    print("=" * 72)
    print("  E₀ C169 — Compatibility Threshold Calibration")
    print("=" * 72)
    print()
    print("── Phase 1: Landscape Construction ─────────────────────")

    landscapes = {}

    # Canon-based (raw, to be trained in phase 2)
    for label, name in [("EN", "english_basic_enriched"),
                        ("DE", "german_basic_enriched"),
                        ("ONTO", "ontodynamics")]:
        cl = load_canon(name)
        landscapes[label] = cl.landscape

    # EN_RAW: same topology as EN, but no training
    cl_raw = load_canon("english_basic_enriched")
    landscapes["EN_RAW"] = cl_raw.landscape

    # LLM-style bootstrapped domains
    landscapes["LLM_COOK"] = build_llm_cooking_landscape()
    landscapes["LLM_PROJ"] = build_llm_project_landscape()

    # Random domains
    landscapes["RND_44"] = build_random_landscape(44, 0.07, seed=42)  # ~130 edges
    landscapes["RND_51"] = build_random_landscape(51, 0.05, seed=99)  # ~130 edges

    for label, ls in landscapes.items():
        n = len(ls.states)
        e = len(ls.edges)
        avg = 2 * e / n if n > 0 else 0
        print(f"  {label:10s}: {n:3d} nodes, {e:3d} edges, avg_deg={avg:.1f}")

    print()
    return landscapes


# ──────────────────────────────────────────────
# Phase 2: Curriculum Training (canon domains)
# ──────────────────────────────────────────────

def phase_training(landscapes):
    """Train EN, DE, ONTO via curriculum. Others keep bootstrap historization."""
    print("── Phase 2: Curriculum Training (canon domains) ────────")

    for label, name in [("EN", "english_basic_enriched"),
                        ("DE", "german_basic_enriched"),
                        ("ONTO", "ontodynamics")]:
        t0 = time.time()
        runner = CurriculumRunner(
            name, EXEC_FN,
            equilibrium_threshold=2.0,
            equilibrium_patience=3,
            max_episodes_per_turn=15,
            max_cycles_per_episode=40,
        )
        results = runner.run()
        landscapes[label] = runner.final_landscape
        dt = time.time() - t0
        total_steps = sum(r.total_steps for r in results)
        print(f"  {label:6s}: {len(results)} turns, {total_steps} steps, "
              f"readiness={dream_readiness(landscapes[label]):.3f}, "
              f"{dt:.1f}s")

    print()
    return landscapes


# ──────────────────────────────────────────────
# Phase 3: Full Compatibility Matrix
# ──────────────────────────────────────────────

def phase_compatibility_matrix(landscapes):
    """Compute dream_compatibility() for all pairs."""
    print("── Phase 3: Full Compatibility Matrix ──────────────────")

    labels = list(landscapes.keys())
    n = len(labels)
    scores = {}

    # Header
    hdr = f"{'':12s}" + "".join(f"{l:>10s}" for l in labels)
    print(hdr)
    print("-" * len(hdr))

    for i, la in enumerate(labels):
        row = f"{la:12s}"
        for j, lb in enumerate(labels):
            if i == j:
                row += f"{'---':>10s}"
            elif (la, lb) in scores:
                row += f"{scores[(la, lb)]:>10.3f}"
            else:
                s = dream_compatibility(landscapes[la], landscapes[lb], depth=2)
                scores[(la, lb)] = s
                scores[(lb, la)] = s  # symmetric
                row += f"{s:>10.3f}"
        print(row)

    print()
    return scores


# ──────────────────────────────────────────────
# Phase 4: Threshold Analysis
# ──────────────────────────────────────────────

def phase_threshold_analysis(scores, landscapes):
    """Analyze score distribution and find natural threshold."""
    print("── Phase 4: Threshold Analysis ─────────────────────────")

    # Unique pairs only
    all_pairs = []
    seen = set()
    for (a, b), s in scores.items():
        key = tuple(sorted([a, b]))
        if key not in seen:
            seen.add(key)
            all_pairs.append((a, b, s))
    all_pairs.sort(key=lambda x: x[2])

    print(f"  Total unique pairs: {len(all_pairs)}")
    print()

    # Distribution
    vals = [s for _, _, s in all_pairs]
    print(f"  min={min(vals):.3f}  max={max(vals):.3f}  "
          f"mean={sum(vals)/len(vals):.3f}  "
          f"median={sorted(vals)[len(vals)//2]:.3f}")
    print()

    # Sorted list
    print(f"  {'Rank':>4s}  {'Pair':30s}  {'Score':>7s}  {'@0.6':>5s}  {'@0.5':>5s}  {'@0.7':>5s}")
    print("  " + "-" * 80)
    for rank, (a, b, s) in enumerate(all_pairs, 1):
        pair = f"{a}↔{b}"
        t06 = "PASS" if s <= 0.6 else "SKIP"
        t05 = "PASS" if s <= 0.5 else "SKIP"
        t07 = "PASS" if s <= 0.7 else "SKIP"
        print(f"  {rank:4d}  {pair:30s}  {s:7.3f}  {t06:>5s}  {t05:>5s}  {t07:>5s}")

    # Gap analysis: find the largest gap between consecutive scores
    print()
    print("  Gap analysis (largest jumps between consecutive scores):")
    gaps = []
    for i in range(len(vals) - 1):
        gap = vals[i + 1] - vals[i]
        gaps.append((gap, vals[i], vals[i + 1], i + 1))
    gaps.sort(reverse=True)
    for gap, lo, hi, pos in gaps[:5]:
        mid = (lo + hi) / 2
        print(f"    gap={gap:.3f} between score {lo:.3f} and {hi:.3f} "
              f"(natural threshold ≈ {mid:.3f}, position {pos}/{len(vals)})")

    # Category analysis
    print()
    print("  Category breakdown:")

    # Define expected categories
    categories = {
        "canon-same-type (EN↔DE)": [],
        "canon-raw (EN↔EN_RAW)": [],
        "canon-different (EN/DE↔ONTO)": [],
        "llm-pair (COOK↔PROJ)": [],
        "llm-vs-canon": [],
        "random-vs-any": [],
    }

    canon_trained = {"EN", "DE"}
    canon_all = {"EN", "DE", "ONTO", "EN_RAW"}
    llm_domains = {"LLM_COOK", "LLM_PROJ"}
    rnd_domains = {"RND_44", "RND_51"}

    for a, b, s in all_pairs:
        pair = {a, b}
        if pair == {"EN", "DE"}:
            categories["canon-same-type (EN↔DE)"].append(s)
        elif pair == {"EN", "EN_RAW"}:
            categories["canon-raw (EN↔EN_RAW)"].append(s)
        elif pair <= canon_all and "ONTO" in pair:
            categories["canon-different (EN/DE↔ONTO)"].append(s)
        elif pair <= llm_domains:
            categories["llm-pair (COOK↔PROJ)"].append(s)
        elif pair & llm_domains and pair & canon_all:
            categories["llm-vs-canon"].append(s)
        elif pair & rnd_domains:
            categories["random-vs-any"].append(s)

    for cat, vals_cat in categories.items():
        if vals_cat:
            avg = sum(vals_cat) / len(vals_cat)
            print(f"    {cat:35s}: n={len(vals_cat):2d}, "
                  f"mean={avg:.3f}, range=[{min(vals_cat):.3f}, {max(vals_cat):.3f}]")
        else:
            print(f"    {cat:35s}: n= 0")

    print()
    return all_pairs


# ──────────────────────────────────────────────
# Phase 5: Training Effect on Compatibility
# ──────────────────────────────────────────────

def phase_training_effect(landscapes):
    """Compare EN (trained) vs EN_RAW (untrained) compatibility to others."""
    print("── Phase 5: Training Effect on Compatibility ───────────")

    en_trained = landscapes["EN"]
    en_raw = landscapes["EN_RAW"]
    de_trained = landscapes["DE"]
    onto_trained = landscapes["ONTO"]

    # EN_trained vs EN_raw → how much does training change WL fingerprints?
    d_self = dream_compatibility(en_trained, en_raw, depth=2)
    print(f"  EN_trained ↔ EN_RAW    = {d_self:.3f}  (same topology, different H)")

    # Both vs DE
    d_en_de = dream_compatibility(en_trained, de_trained, depth=2)
    d_raw_de = dream_compatibility(en_raw, de_trained, depth=2)
    print(f"  EN_trained ↔ DE_trained = {d_en_de:.3f}")
    print(f"  EN_RAW     ↔ DE_trained = {d_raw_de:.3f}")
    print(f"  → Training shifts EN↔DE by {abs(d_en_de - d_raw_de):.3f}")

    # Both vs ONTO
    d_en_onto = dream_compatibility(en_trained, onto_trained, depth=2)
    d_raw_onto = dream_compatibility(en_raw, onto_trained, depth=2)
    print(f"  EN_trained ↔ ONTO       = {d_en_onto:.3f}")
    print(f"  EN_RAW     ↔ ONTO       = {d_raw_onto:.3f}")
    print(f"  → Training shifts EN↔ONTO by {abs(d_en_onto - d_raw_onto):.3f}")

    # WL fingerprint stats for trained vs raw
    fp_trained = wl_node_fingerprints(en_trained, depth=2)
    fp_raw = wl_node_fingerprints(en_raw, depth=2)

    def mean_feature_magnitude(fps):
        if not fps:
            return 0.0
        return sum(sum(abs(f) for f in fp.features) / len(fp.features)
                   for fp in fps) / len(fps)

    mag_trained = mean_feature_magnitude(fp_trained)
    mag_raw = mean_feature_magnitude(fp_raw)
    print(f"\n  Mean feature magnitude: trained={mag_trained:.3f}, raw={mag_raw:.3f}")
    print(f"  Ratio: {mag_trained / mag_raw:.2f}x" if mag_raw > 0
          else "  (raw has zero magnitude)")

    print()


# ──────────────────────────────────────────────
# Phase 6: LLM-Proposed Domain Test
# ──────────────────────────────────────────────

def phase_llm_test(landscapes):
    """Use actual LLM to propose a domain and test compatibility."""
    print("── Phase 6: Live LLM Domain Proposal ───────────────────")

    try:
        from e0_controller.llm_adapter import E0LLMAdapter

        adapter = E0LLMAdapter()

        # Two LLM-proposed domains with retry
        llm_domains = [
            ("LLM_ML", "A machine learning pipeline with 8-10 states: "
             "data collection, feature engineering, model training, "
             "evaluation, deployment, monitoring, and retraining."),
            ("LLM_MED", "A medical diagnosis workflow with 6-8 states: "
             "patient intake, symptom assessment, differential diagnosis, "
             "testing, treatment planning, follow-up."),
        ]

        for llm_label, llm_desc in llm_domains:
            for attempt in range(3):
                try:
                    t0 = time.time()
                    print(f"  Proposing {llm_label}... (attempt {attempt + 1})")
                    llm_landscape = adapter.propose_and_bootstrap(llm_desc)
                    dt = time.time() - t0
                    n = len(llm_landscape.states)
                    e = len(llm_landscape.edges)
                    print(f"    → {n} nodes, {e} edges ({dt:.1f}s)")
                    landscapes[llm_label] = llm_landscape
                    break
                except Exception as ex:
                    print(f"    attempt {attempt + 1} failed: {ex}")
                    if attempt == 2:
                        print(f"    SKIPPED {llm_label} after 3 attempts")
                    time.sleep(1)

        # Compatibility of new LLM domains with all existing
        llm_added = [l for l in ["LLM_ML", "LLM_MED"] if l in landscapes]
        if llm_added:
            print()
            print(f"  {'Domain':15s}", end="")
            for ll in llm_added:
                print(f"  {ll:>10s}", end="")
            print()
            print("  " + "-" * (15 + 12 * len(llm_added)))

            for label in list(landscapes.keys()):
                if label in llm_added:
                    continue
                row = f"  {label:15s}"
                for ll in llm_added:
                    s = dream_compatibility(landscapes[ll], landscapes[label], depth=2)
                    row += f"  {s:10.3f}"
                print(row)

            # LLM vs LLM
            if len(llm_added) == 2:
                s = dream_compatibility(landscapes[llm_added[0]],
                                        landscapes[llm_added[1]], depth=2)
                print(f"  {llm_added[0]+' ↔ '+llm_added[1]:15s}  {s:10.3f}")

        print()
        return len(llm_added) > 0

    except Exception as ex:
        print(f"  SKIPPED: {ex}")
        print("  (LLM phase requires OPENAI_API_KEY in .env)")
        print()
        return False


# ──────────────────────────────────────────────
# Phase 7: Summary + Recommendation
# ──────────────────────────────────────────────

def phase_summary(all_pairs, llm_available):
    """Final analysis and threshold recommendation."""
    print("── Phase 7: Summary + Recommendation ───────────────────")

    vals = sorted([s for _, _, s in all_pairs])

    # Find the largest gap
    best_gap = 0
    best_threshold = 0.6
    for i in range(len(vals) - 1):
        gap = vals[i + 1] - vals[i]
        if gap > best_gap:
            best_gap = gap
            best_threshold = (vals[i] + vals[i + 1]) / 2

    # Count pass/skip at different thresholds
    thresholds = [0.4, 0.5, best_threshold, 0.6, 0.7, 0.8]
    thresholds = sorted(set(thresholds))

    print(f"  Threshold sensitivity analysis:")
    print(f"  {'Threshold':>10s}  {'PASS':>5s}  {'SKIP':>5s}  {'PASS%':>6s}")
    print("  " + "-" * 30)
    for t in thresholds:
        n_pass = sum(1 for s in vals if s <= t)
        n_skip = len(vals) - n_pass
        pct = 100 * n_pass / len(vals)
        marker = " ← gap" if abs(t - best_threshold) < 0.001 else ""
        print(f"  {t:10.3f}  {n_pass:5d}  {n_skip:5d}  {pct:5.1f}%{marker}")

    print()
    print(f"  Largest natural gap: {best_gap:.3f}")
    print(f"  Recommended threshold: {best_threshold:.3f}")
    print(f"  Current threshold: 0.6")

    if abs(best_threshold - 0.6) < 0.05:
        print(f"  → Current threshold is well-calibrated (within ±0.05)")
    elif best_threshold < 0.6:
        print(f"  → Consider lowering threshold to {best_threshold:.2f}")
    else:
        print(f"  → Consider raising threshold to {best_threshold:.2f}")

    print()
    print(f"  Q1 answer: dream_compatibility() {'works' if llm_available else 'untested'} "
          f"on LLM-scored landscapes")
    print(f"  Q2 answer: optimal threshold ≈ {best_threshold:.3f} "
          f"(gap={best_gap:.3f}, {len(vals)} pairs tested)")
    print()


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main():
    t_start = time.time()

    landscapes = phase_construction()
    landscapes = phase_training(landscapes)
    scores = phase_compatibility_matrix(landscapes)
    all_pairs = phase_threshold_analysis(scores, landscapes)
    phase_training_effect(landscapes)
    llm_ok = phase_llm_test(landscapes)

    # If LLM added domains, add their pairs to all_pairs
    if llm_ok:
        for llm_label in ["LLM_ML", "LLM_MED"]:
            if llm_label not in landscapes:
                continue
            for label, ls in landscapes.items():
                if label == llm_label:
                    continue
                # Skip if already in all_pairs
                key = tuple(sorted([llm_label, label]))
                if any(tuple(sorted([a, b])) == key for a, b, _ in all_pairs):
                    continue
                s = dream_compatibility(landscapes[llm_label], ls, depth=2)
                all_pairs.append((llm_label, label, s))

    phase_summary(all_pairs, llm_ok)

    dt = time.time() - t_start
    print(f"  Total runtime: {dt:.1f}s")
    print()


if __name__ == "__main__":
    main()
