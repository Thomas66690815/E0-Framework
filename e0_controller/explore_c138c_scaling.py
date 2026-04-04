#!/usr/bin/env python3
"""
E₀ C138c — Scaling: How does Hungarian+WL-D2 behave on larger graphs?
=======================================================================

Real canons: 44 nodes, 64 edges. Does the approach scale?

Approach:
  - Generate synthetic isomorphic graph pairs at N = 50, 100, 200, 500
  - Planted ground truth: A_i ↔ B_i
  - Edge density ~1.5 edges/node (matches real canons)
  - Simulated scores (no LLM — already validated in C138a/b)
  - Add 100 shared noise edges (same protocol as real pipeline)
  - WL depth=2, Hungarian matching
  - Also include real 44-node pair as reference (with LLM scores)

Measures:
  - Accuracy: correct / total
  - Wall-clock time: WL fingerprinting + Hungarian
  - Breakdown: which nodes fail first under ambiguity?
"""

import copy
import json
import math
import os
import random
import sys
import time
from collections import defaultdict
from typing import Any, Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.bootstrapper import bootstrap_landscape
from e0_controller.dream_mode import (
    find_wl_node_equivalences_hungarian,
    wl_node_fingerprints,
    wl_node_distance,
)


# ══════════════════════════════════════════════
# Synthetic graph generation
# ══════════════════════════════════════════════

def generate_isomorphic_pair(
    n_nodes: int,
    edge_density: float,
    rng: random.Random,
) -> Tuple[dict, dict, Dict[str, str]]:
    """Generate two isomorphic graph specs with planted correspondence.

    Returns (spec_a, spec_b, ground_truth) where ground_truth maps
    A node names → B node names.
    """
    nodes_a = [f"a_{i}" for i in range(n_nodes)]
    nodes_b = [f"b_{i}" for i in range(n_nodes)]
    ground_truth = {f"a_{i}": f"b_{i}" for i in range(n_nodes)}

    # Generate random directed edges for graph A
    n_edges = int(n_nodes * edge_density)
    all_possible = [
        (a, b) for a in nodes_a for b in nodes_a if a != b
    ]
    rng.shuffle(all_possible)
    edges_a = all_possible[:n_edges]

    # Mirror edges in graph B (using ground truth mapping)
    edges_b = [(ground_truth[src], ground_truth[tgt]) for src, tgt in edges_a]

    # Generate simulated scores (mimics real LLM distribution)
    # Real distribution: ~60% low (0-2), ~25% mid (3-5), ~15% high (7-10)
    # Key: corresponding edges get CORRELATED scores (same semantic
    # relationship → similar LLM score in both languages), with small
    # noise to model inter-language variance.
    def sim_score(rng):
        r = rng.random()
        if r < 0.60:
            return rng.choice([0, 0, 0, 1, 1, 2])
        elif r < 0.85:
            return rng.choice([3, 3, 5])
        else:
            return rng.choice([7, 7, 8, 10, 10])

    # Generate base scores per edge pair, then perturb independently
    base_scores = [sim_score(rng) for _ in edges_a]

    def perturb(base, rng, sigma=1.0):
        return max(0, min(10, round(base + rng.gauss(0, sigma))))

    edges_a_specs = []
    edges_b_specs = []
    for i, ((src_a, tgt_a), (src_b, tgt_b)) in enumerate(
        zip(edges_a, edges_b)
    ):
        base = base_scores[i]
        s_a = perturb(base, rng)
        s_b = perturb(base, rng)
        edges_a_specs.append({
            "from": src_a, "to": tgt_a,
            "delta": 0.5, "resistance": 0.3,
            "initial_U": s_a, "initial_F": 10 - s_a,
            "confidence": 1.0,
        })
        edges_b_specs.append({
            "from": src_b, "to": tgt_b,
            "delta": 0.5, "resistance": 0.3,
            "initial_U": s_b, "initial_F": 10 - s_b,
            "confidence": 1.0,
        })

    spec_a = {"nodes": nodes_a, "edges": edges_a_specs}
    spec_b = {"nodes": nodes_b, "edges": edges_b_specs}

    return spec_a, spec_b, ground_truth


def add_noise_edges(
    spec_a: dict, spec_b: dict,
    ground_truth: Dict[str, str],
    n_noise: int,
    rng: random.Random,
) -> Tuple[dict, dict]:
    """Add shared noise edges to both specs (same topology, different scores).

    Mirrors the real pipeline: noise edges appear in both graphs at
    corresponding positions (via ground truth), with independent scores.
    """
    spec_a = copy.deepcopy(spec_a)
    spec_b = copy.deepcopy(spec_b)

    existing_a = {(e["from"], e["to"]) for e in spec_a["edges"]}
    nodes_a = spec_a["nodes"]

    all_possible = [
        (a, b) for a in nodes_a for b in nodes_a
        if a != b and (a, b) not in existing_a
    ]
    rng.shuffle(all_possible)

    def noise_score(rng):
        return rng.choice([0, 0, 0, 0, 1, 1, 2])

    added = 0
    for src_a, tgt_a in all_possible:
        if added >= n_noise:
            break
        src_b = ground_truth[src_a]
        tgt_b = ground_truth[tgt_a]

        s_a = noise_score(rng)
        s_b = noise_score(rng)

        spec_a["edges"].append({
            "from": src_a, "to": tgt_a,
            "delta": 0.3, "resistance": 0.3,
            "initial_U": s_a, "initial_F": 10 - s_a,
            "confidence": 1.0,
        })
        spec_b["edges"].append({
            "from": src_b, "to": tgt_b,
            "delta": 0.3, "resistance": 0.3,
            "initial_U": s_b, "initial_F": 10 - s_b,
            "confidence": 1.0,
        })
        added += 1

    return spec_a, spec_b


# ══════════════════════════════════════════════
# Matching + scoring
# ══════════════════════════════════════════════

def match_and_score(
    L_a: Landscape,
    L_b: Landscape,
    ground_truth: Dict[str, str],
    depth: int = 2,
) -> Tuple[int, int, int, float]:
    """Run Hungarian matching and score against ground truth.

    Returns (correct, wrong, total_matched, elapsed_seconds).
    """
    t0 = time.perf_counter()
    node_eqs = find_wl_node_equivalences_hungarian(
        L_a, L_b, domain_a="A", domain_b="B", depth=depth,
    )
    elapsed = time.perf_counter() - t0

    correct = wrong = 0
    for eq in node_eqs:
        expected = ground_truth.get(eq.fp_a.node)
        if expected == eq.fp_b.node:
            correct += 1
        elif expected is not None:
            wrong += 1

    return correct, wrong, len(node_eqs), elapsed


# ══════════════════════════════════════════════
# Main experiment
# ══════════════════════════════════════════════

def run_experiment():
    print("=" * 72)
    print("  E₀ C138c — Scaling: Hungarian+WL-D2 on larger graphs")
    print("  Synthetic isomorphic pairs with planted ground truth")
    print("  Edge density ~1.5/node, +100 noise edges, simulated scores")
    print("=" * 72)

    sizes = [50, 100, 200, 500]
    edge_density = 1.5
    noise_edges = 100
    depth = 2
    n_trials = 3  # multiple trials per size for variance

    results: Dict[int, List[Tuple[int, int, float]]] = defaultdict(list)

    for n in sizes:
        print(f"\n{'─'*72}")
        print(f"  N = {n} nodes, ~{int(n*edge_density)} base edges "
              f"+ {noise_edges} noise, depth={depth}")
        print(f"{'─'*72}")

        for trial in range(n_trials):
            rng = random.Random(42 + trial * 1000)

            spec_a, spec_b, gt = generate_isomorphic_pair(
                n, edge_density, rng,
            )
            spec_a, spec_b = add_noise_edges(
                spec_a, spec_b, gt, noise_edges, rng,
            )

            L_a = bootstrap_landscape(spec_a)
            L_b = bootstrap_landscape(spec_b)

            correct, wrong, matched, elapsed = match_and_score(
                L_a, L_b, gt, depth=depth,
            )

            results[n].append((correct, wrong, elapsed))
            prec = f"{correct/(correct+wrong)*100:.0f}%" if correct+wrong > 0 else "—"
            print(f"  Trial {trial+1}: {correct}/{n} correct, "
                  f"{wrong} wrong, precision={prec}, "
                  f"time={elapsed:.2f}s")

    # ── Summary table ──
    print(f"\n{'='*72}")
    print("  C138c SCALING SUMMARY")
    print(f"{'='*72}")

    print(f"\n  {'N':>5}  {'Avg Correct':>11}  {'Avg Wrong':>9}  "
          f"{'Accuracy':>8}  {'Avg Time':>8}")
    print(f"  {'─'*50}")

    for n in sizes:
        trials = results[n]
        avg_c = sum(t[0] for t in trials) / len(trials)
        avg_w = sum(t[1] for t in trials) / len(trials)
        avg_t = sum(t[2] for t in trials) / len(trials)
        acc = f"{avg_c/n*100:.1f}%"
        print(f"  {n:>5}  {avg_c:>11.1f}  {avg_w:>9.1f}  "
              f"{acc:>8}  {avg_t:>7.2f}s")

    # ── Scaling analysis ──
    print(f"\n  {'='*60}")
    print(f"  SCALING BEHAVIOR")
    print(f"  {'='*60}")

    times = [(n, sum(t[2] for t in results[n])/len(results[n])) for n in sizes]
    if len(times) >= 2:
        n1, t1 = times[0]
        n2, t2 = times[-1]
        if t1 > 0:
            ratio_n = n2 / n1
            ratio_t = t2 / t1
            exponent = math.log(ratio_t) / math.log(ratio_n)
            print(f"  Time ratio: {n2}/{n1} nodes → "
                  f"{ratio_t:.1f}x slower")
            print(f"  Empirical scaling exponent: O(n^{exponent:.2f})")
            if exponent < 2.5:
                print(f"  → Sub-cubic: practical for moderate graphs")
            elif exponent < 3.5:
                print(f"  → Roughly cubic (Hungarian-dominated)")
            else:
                print(f"  → Super-cubic: may need optimization for large N")

    # ── Per-size accuracy stability ──
    print(f"\n  {'='*60}")
    print(f"  ACCURACY STABILITY (variance across trials)")
    print(f"  {'='*60}")
    for n in sizes:
        trials = results[n]
        accs = [t[0]/n*100 for t in trials]
        avg = sum(accs) / len(accs)
        std = (sum((a - avg)**2 for a in accs) / len(accs)) ** 0.5
        min_a = min(accs)
        max_a = max(accs)
        print(f"  N={n:>4}: avg={avg:.1f}% std={std:.1f}% "
              f"range=[{min_a:.0f}%–{max_a:.0f}%]")

    print(f"\n{'='*72}")


if __name__ == "__main__":
    run_experiment()
