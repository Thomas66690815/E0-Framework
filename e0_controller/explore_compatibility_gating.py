#!/usr/bin/env python3
"""
E₀ C168 — Compatibility-Gated Dreaming Exploration
=====================================================

Empirical validation of dream_compatibility() and compatibility-gated
DreamObserver. Three domains with different structural properties:

  - EN (english_basic_enriched) — 44 nodes, 127 edges, avg_deg 5.8
  - DE (german_basic_enriched)  — 44 nodes, 135 edges, avg_deg 6.1
  - ONTO (ontodynamics)         — 51 nodes,  93 edges, avg_deg 3.6

Expected behavior:
  - EN↔DE: structurally compatible (near-isomorphic) → low distance → PASS
  - EN↔ONTO, DE↔ONTO: structurally incompatible → high distance → SKIP

Phases:
  1. Canon loading + structural survey
  2. Curriculum training (all three domains)
  3. Pairwise compatibility matrix
  4. Ungated dream cycle (baseline — all pairs matched)
  5. Gated dream cycle (compatibility_threshold=0.6)
  6. Comparison: gated vs ungated
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from e0_controller.canon_loader import load_canon
from e0_controller.curriculum import CurriculumRunner
from e0_controller.primitives import Outcome
from e0_controller.structural_entropy import structural_temperature, dream_pressure
from e0_controller.dream_mode import (
    DreamObserver,
    dream_compatibility,
    is_dream_compatible,
    dream_readiness,
)

EXEC_FN = lambda s, t: Outcome.SUCCESS  # noqa: E731

CANONS = [
    ("EN", "english_basic_enriched"),
    ("DE", "german_basic_enriched"),
    ("ONTO", "ontodynamics"),
]


# ──────────────────────────────────────────────
# Phase 1: Canon Loading + Structural Survey
# ──────────────────────────────────────────────

def phase_canons():
    print("=" * 72)
    print("  E₀ C168 — Compatibility-Gated Dreaming Exploration")
    print("=" * 72)
    print()
    print("── Phase 1: Canon Loading ──────────────────────────────")
    for label, name in CANONS:
        cl = load_canon(name)
        ls = cl.landscape
        n_nodes = len(ls.states)
        n_edges = len(ls.edges)
        avg_deg = 2 * n_edges / n_nodes if n_nodes > 0 else 0
        print(f"  {label:6s} ({name}): "
              f"{n_nodes} nodes, {n_edges} edges, avg_deg={avg_deg:.1f}")
    print()


# ──────────────────────────────────────────────
# Phase 2: Curriculum Training
# ──────────────────────────────────────────────

def phase_training():
    print("── Phase 2: Curriculum Training ────────────────────────")
    landscapes = {}
    for label, name in CANONS:
        t0 = time.time()
        runner = CurriculumRunner(
            name, EXEC_FN,
            equilibrium_threshold=2.0,
            equilibrium_patience=3,
            max_episodes_per_turn=15,
            max_cycles_per_episode=40,
        )
        results = runner.run()
        L = runner.final_landscape
        dt = time.time() - t0

        T_s = structural_temperature(L.historization)
        dp = dream_pressure(L.historization)
        dr = dream_readiness(L)

        total_steps = sum(r.total_steps for r in results)
        print(f"  {label:6s}: {len(results)} turns, {total_steps} steps, "
              f"T_s={T_s:.3f}, dp={dp:.3f}, readiness={dr:.3f}  ({dt:.1f}s)")
        landscapes[label] = L

    print()
    return landscapes


# ──────────────────────────────────────────────
# Phase 3: Pairwise Compatibility Matrix
# ──────────────────────────────────────────────

def phase_compatibility_matrix(landscapes):
    print("── Phase 3: Compatibility Matrix ───────────────────────")
    labels = list(landscapes.keys())
    n = len(labels)

    # Header
    print(f"  {'':8s}", end="")
    for lb in labels:
        print(f"  {lb:>8s}", end="")
    print()

    for i, la in enumerate(labels):
        print(f"  {la:8s}", end="")
        for j, lb in enumerate(labels):
            if i == j:
                print(f"  {'—':>8s}", end="")
            elif j > i:
                score = dream_compatibility(
                    landscapes[la], landscapes[lb], depth=2,
                )
                compat = "✓" if score <= 0.6 else "✗"
                print(f"  {score:>6.3f}{compat}", end="")
            else:
                print(f"  {'':>8s}", end="")
        print()

    print()

    # Detailed pairwise report
    print("  Pairwise detail:")
    for i, la in enumerate(labels):
        for lb in labels[i + 1:]:
            score = dream_compatibility(
                landscapes[la], landscapes[lb], depth=2,
            )
            compat = is_dream_compatible(
                landscapes[la], landscapes[lb], threshold=0.6,
            )
            status = "COMPATIBLE" if compat else "INCOMPATIBLE"
            print(f"    {la}↔{lb}: score={score:.4f} → {status}")
    print()


# ──────────────────────────────────────────────
# Phase 4: Ungated Dream Cycle (baseline)
# ──────────────────────────────────────────────

def phase_ungated(landscapes):
    print("── Phase 4: Ungated Dream Cycle (baseline) ─────────────")
    obs = DreamObserver(
        readiness_threshold=0.0,
        node_equivalence_method="hungarian",
    )
    for label in landscapes:
        obs.register(label, landscapes[label])

    result = obs.dream_cycle()
    print(f"  Domains observed:   {result.domains_observed}")
    print(f"  Domains skipped:    {result.domains_skipped}")
    print(f"  Edge equivalences:  {result.equivalences_found} found, "
          f"{result.equivalences_new} new")
    print(f"  Node equivalences:  {result.node_equivalences_found} found, "
          f"{result.node_equivalences_new} new")
    print(f"  Dream Landscape:    {result.dream_landscape_states} states, "
          f"{result.dream_landscape_edges} edges")
    print(f"  Compat skipped:     {result.compatibility_skipped}")
    print()
    return result


# ──────────────────────────────────────────────
# Phase 5: Gated Dream Cycle (C168)
# ──────────────────────────────────────────────

def phase_gated(landscapes, threshold=0.6):
    print(f"── Phase 5: Gated Dream Cycle (threshold={threshold}) ──")
    obs = DreamObserver(
        readiness_threshold=0.0,
        node_equivalence_method="hungarian",
        compatibility_threshold=threshold,
    )
    for label in landscapes:
        obs.register(label, landscapes[label])

    result = obs.dream_cycle()
    print(f"  Domains observed:   {result.domains_observed}")
    print(f"  Domains skipped:    {result.domains_skipped}")
    print(f"  Edge equivalences:  {result.equivalences_found} found, "
          f"{result.equivalences_new} new")
    print(f"  Node equivalences:  {result.node_equivalences_found} found, "
          f"{result.node_equivalences_new} new")
    print(f"  Dream Landscape:    {result.dream_landscape_states} states, "
          f"{result.dream_landscape_edges} edges")
    print(f"  Compat skipped:     {result.compatibility_skipped}")
    print(f"  Compat scores:      ", end="")
    for (a, b), score in sorted(result.compatibility_scores.items()):
        status = "✓" if score <= threshold else "✗"
        print(f"{a}↔{b}={score:.3f}{status}  ", end="")
    print()
    print()
    return result


# ──────────────────────────────────────────────
# Phase 6: Comparison
# ──────────────────────────────────────────────

def phase_comparison(ungated, gated):
    print("── Phase 6: Comparison ─────────────────────────────────")
    print(f"  {'Metric':<30s} {'Ungated':>10s} {'Gated':>10s} {'Diff':>10s}")
    print(f"  {'─' * 60}")

    metrics = [
        ("Edge equivalences", ungated.equivalences_found, gated.equivalences_found),
        ("Edge EQ (new)", ungated.equivalences_new, gated.equivalences_new),
        ("Node equivalences", ungated.node_equivalences_found, gated.node_equivalences_found),
        ("Node EQ (new)", ungated.node_equivalences_new, gated.node_equivalences_new),
        ("Dream states", ungated.dream_landscape_states, gated.dream_landscape_states),
        ("Dream edges", ungated.dream_landscape_edges, gated.dream_landscape_edges),
        ("Pairs skipped", len(ungated.compatibility_skipped), len(gated.compatibility_skipped)),
    ]

    for name, u, g in metrics:
        diff = g - u
        sign = "+" if diff > 0 else ""
        print(f"  {name:<30s} {u:>10d} {g:>10d} {sign + str(diff):>10s}")

    print()

    # Noise reduction ratio
    if ungated.equivalences_found > 0:
        edge_noise = ungated.equivalences_found - gated.equivalences_found
        print(f"  Edge noise filtered:  {edge_noise} "
              f"({edge_noise / ungated.equivalences_found:.0%} of ungated)")
    if ungated.node_equivalences_found > 0:
        node_noise = ungated.node_equivalences_found - gated.node_equivalences_found
        print(f"  Node noise filtered:  {node_noise} "
              f"({node_noise / ungated.node_equivalences_found:.0%} of ungated)")

    print()
    print("  Verdict: ", end="")
    if len(gated.compatibility_skipped) > 0:
        skipped_str = ", ".join(f"{a}↔{b}" for a, b in gated.compatibility_skipped)
        print(f"Gating active — {len(gated.compatibility_skipped)} "
              f"incompatible pair(s) skipped: {skipped_str}")
    else:
        print("All pairs compatible — no gating applied")
    print()


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main():
    phase_canons()
    landscapes = phase_training()
    phase_compatibility_matrix(landscapes)
    ungated = phase_ungated(landscapes)
    gated = phase_gated(landscapes, threshold=0.6)
    phase_comparison(ungated, gated)

    print("=" * 72)
    print("  C168 Exploration complete.")
    print("=" * 72)


if __name__ == "__main__":
    main()
