"""
C180 — N-Domain Mesh Exploration (N=5)

Extended mesh experiment: EN + DE + ONTO (canon, curriculum-trained)
plus COOK + PROJ (bootstrapped, hand-crafted workflow topologies).

Research questions:
  1. Do COOK↔PROJ form a second cluster (both 10 nodes / 13 edges)?  → YES (0.27)
  2. Does EN↔DE cluster persist in a 5-domain mesh?                  → YES (0.37)
  3. Which cross-family pairs (canon ↔ bootstrapped) become compatible?
     → ONTO↔COOK and ONTO↔PROJ cross boundary post-navigation (Δ > 1.0)
  4. Does coupling weight self-organization emerge with more domains? → Not yet (all 1.0)

Emergent finding: ONTO acts as bridge node between clusters.
  Pre-nav: 2 clusters + 1 isolate ({EN,DE}, {COOK,PROJ}, ONTO)
  Post-nav: ONTO bridges {COOK,PROJ} to {EN} via compatibility shift.
  DE remains the actual isolate (DE↔COOK, DE↔PROJ > 0.6).

Protocol:
  Phase 1: Domain preparation (curriculum + bootstrap)
  Phase 2: Pairwise compatibility matrix (10 pairs)
  Phase 3: Mesh assembly (DreamObserver + CouplingRouter)
  Phase 4: Run episodes, collect per-episode metrics
  Phase 5: Post-navigation compatibility (WL fingerprint shift)
  Phase 6: Cluster analysis and verdict

Reference: docs/E0_STRATEGIC_ROADMAP_v1.md Priority 3
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from itertools import combinations
from typing import Dict, List

from e0_controller.bootstrapper import bootstrap_landscape
from e0_controller.canon_loader import load_canon
from e0_controller.controller import E0Controller, HybridMode
from e0_controller.coupling_router import (
    CouplingRouter,
    Universe,
    update_weights_from_dream,
)
from e0_controller.curriculum import CurriculumRunner
from e0_controller.dream_mode import (
    DreamObserver,
    dream_compatibility,
)
from e0_controller.primitives import Outcome
from e0_controller.structural_entropy import (
    dream_pressure,
    structural_temperature,
)


# ── Configuration ────────────────────────────────────────────────────

EXEC_FN = lambda s, t: Outcome.SUCCESS

# Canon domains (curriculum-trained)
CANON_DOMAINS = [
    ("EN",   "english_basic_enriched",  "thing",      "self"),
    ("DE",   "german_basic_enriched",   "ding",       "selbst"),
    ("ONTO", "ontodynamics",            "difference", "negative_necessity"),
]

# Bootstrapped domains (hand-crafted specs)
BOOTSTRAP_DOMAINS = [
    ("COOK", "PLANNING", "SERVING"),
    ("PROJ", "PLANNING", "DEPLOYMENT"),
]

ALL_LABELS = [c[0] for c in CANON_DOMAINS] + [b[0] for b in BOOTSTRAP_DOMAINS]

N_EPISODES = 8
MAX_CYCLES_PER_RUN = 40
COMPATIBILITY_THRESHOLD = 0.6


# ── Landscape Builders ──────────────────────────────────────────────

def build_cooking_landscape():
    """Hand-crafted cooking workflow: 10 nodes, 13 edges."""
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


def build_project_landscape():
    """Hand-crafted project management workflow: 10 nodes, 13 edges."""
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


# ── Data Collection ──────────────────────────────────────────────────

@dataclass
class EpisodeMetrics:
    episode: int
    weights: Dict[str, float]
    dream_eq_counts: Dict[str, int]
    compat_skipped: List[str]
    sleep_occurred: bool


# ── Phases ───────────────────────────────────────────────────────────

def phase_domain_prep() -> Dict[str, dict]:
    """Phase 1: Prepare all 5 domains (curriculum + bootstrap)."""
    print("── Phase 1: Domain Preparation ─────────────────────────")
    trained = {}

    # Canon domains: curriculum training
    for label, canon_name, start, goal in CANON_DOMAINS:
        t0 = time.time()
        runner = CurriculumRunner(
            canon_name, EXEC_FN,
            equilibrium_threshold=2.0,
            equilibrium_patience=3,
            max_episodes_per_turn=15,
            max_cycles_per_episode=40,
        )
        turn_results = runner.run()
        L = runner.final_landscape
        dt = time.time() - t0

        T_s = structural_temperature(L.historization)
        dp = dream_pressure(L.historization)
        total_steps = sum(r.total_steps for r in turn_results)
        n_nodes = len(L.states)
        n_edges = len(L.edges)

        print(f"  {label:6s}: curriculum, {len(turn_results)} turns, "
              f"{total_steps:4d} steps, {n_nodes}n/{n_edges}e, "
              f"T_s={T_s:.3f}, dp={dp:.3f}  ({dt:.1f}s)")
        trained[label] = {
            "landscape": L, "start": start, "goal": goal,
            "source": "curriculum",
        }

    # Bootstrapped domains
    builders = [
        ("COOK", build_cooking_landscape, "PLANNING", "SERVING"),
        ("PROJ", build_project_landscape, "PLANNING", "DEPLOYMENT"),
    ]
    for label, builder_fn, start, goal in builders:
        t0 = time.time()
        L = builder_fn()
        dt = time.time() - t0
        n_nodes = len(L.states)
        n_edges = len(L.edges)
        T_s = structural_temperature(L.historization)
        dp = dream_pressure(L.historization)

        print(f"  {label:6s}: bootstrap, {n_nodes}n/{n_edges}e, "
              f"T_s={T_s:.3f}, dp={dp:.3f}  ({dt:.1f}s)")
        trained[label] = {
            "landscape": L, "start": start, "goal": goal,
            "source": "bootstrap",
        }

    print()
    return trained


def phase_compatibility(trained: Dict, phase_label: str = "2") -> Dict[str, float]:
    """Show pairwise dream compatibility for all C(5,2) = 10 pairs."""
    print(f"── Phase {phase_label}: Dream Compatibility Matrix "
          f"({len(trained)} domains) ──")
    scores = {}
    labels = list(trained.keys())
    for a, b in combinations(labels, 2):
        score = dream_compatibility(
            trained[a]["landscape"], trained[b]["landscape"])
        verdict = "PASS" if score < COMPATIBILITY_THRESHOLD else "SKIP"
        scores[f"{a}↔{b}"] = score
        print(f"  {a:4s}↔{b:4s}: {score:.4f}  [{verdict}]")

    # Summary
    compatible = [k for k, v in scores.items() if v < COMPATIBILITY_THRESHOLD]
    incompatible = [k for k, v in scores.items() if v >= COMPATIBILITY_THRESHOLD]
    print(f"\n  Compatible ({len(compatible)}): {compatible}")
    print(f"  Incompatible ({len(incompatible)}): {incompatible}")
    print()
    return scores


def phase_mesh_assembly(trained: Dict):
    """Phase 3: Assemble DreamObserver + CouplingRouter + Controllers."""
    print("── Phase 3: Mesh Assembly ──────────────────────────────")

    observer = DreamObserver(
        readiness_threshold=0.0,
        node_equivalence_method="hungarian",
        compatibility_threshold=COMPATIBILITY_THRESHOLD,
    )

    universes = []
    controllers = {}
    for label in ALL_LABELS:
        info = trained[label]
        L = info["landscape"]
        observer.register(label, L)
        ctrl = E0Controller(L, EXEC_FN, hybrid_mode=HybridMode.GREEDY)
        controllers[label] = ctrl
        universes.append(Universe(
            name=label, landscape=L,
            execute_fn=EXEC_FN, start=info["start"], goal=info["goal"],
        ))

    router = CouplingRouter(universes)

    print(f"  DreamObserver: {len(observer._domains)} domains, "
          f"threshold={COMPATIBILITY_THRESHOLD}")
    print(f"  CouplingRouter: {len(universes)} universes")
    print(f"  Controllers: {list(controllers.keys())}")
    print()

    return observer, router, controllers


def phase_episodes(observer, router, controllers, trained) -> List[EpisodeMetrics]:
    """Phase 4: Run N episodes, collecting metrics."""
    print(f"── Phase 4: Running {N_EPISODES} Episodes ──────────────────────")
    all_metrics = []

    for ep in range(1, N_EPISODES + 1):
        # ── Wake: run each controller ────────────────────────
        for label in ALL_LABELS:
            info = trained[label]
            ctrl = controllers[label]
            ctrl.run(info["start"], max_cycles=MAX_CYCLES_PER_RUN, goal=info["goal"])

        # ── Sleep: dream cycle ───────────────────────────────
        dream_result = observer.dream_cycle()
        sleep_occurred = dream_result.equivalences_found > 0

        # ── Update coupling weights from dream ───────────────
        update_weights_from_dream(router, observer)

        # ── Collect metrics ──────────────────────────────────
        weights = {label: router.get_weight(label) for label in ALL_LABELS}

        eq_counts = {}
        for a, b in combinations(ALL_LABELS, 2):
            eqs_a = observer.equivalences_for(a)
            count = sum(1 for eq in eqs_a
                        if eq["partner_state"].startswith(f"{b}:"))
            eq_counts[f"{a}↔{b}"] = count

        skipped = [f"{a}↔{b}" for a, b in dream_result.compatibility_skipped]

        metrics = EpisodeMetrics(
            episode=ep,
            weights=weights,
            dream_eq_counts=eq_counts,
            compat_skipped=skipped,
            sleep_occurred=sleep_occurred,
        )
        all_metrics.append(metrics)

        # Print per-episode summary
        w_str = "  ".join(f"{l}={w:.2f}" for l, w in weights.items())
        active_eq = {k: v for k, v in eq_counts.items() if v > 0}
        eq_str = "  ".join(f"{k}={v}" for k, v in active_eq.items()) or "(none)"
        print(f"  Ep {ep:2d}: W=[{w_str}]  EQ=[{eq_str}]  "
              f"skip={len(skipped)}")

    print()
    return all_metrics


def phase_analysis(metrics: List[EpisodeMetrics],
                   pre_scores: Dict[str, float],
                   post_scores: Dict[str, float]) -> dict:
    """Phase 6: Cluster analysis and verdict."""
    print("── Phase 6: Cluster Analysis ───────────────────────────")
    final = metrics[-1]
    results = {}

    # ── 1. Known cluster: EN↔DE
    en_de_eqs = final.dream_eq_counts.get("EN↔DE", 0)
    en_de_cluster = en_de_eqs > 0
    print(f"\n  [Cluster 1] EN↔DE equivalences: {en_de_eqs}"
          f"  {'← cluster' if en_de_cluster else '← NO cluster'}")
    results["en_de_cluster"] = en_de_cluster

    # ── 2. Hypothesis: COOK↔PROJ cluster (same topology)
    cook_proj_eqs = final.dream_eq_counts.get("COOK↔PROJ", 0)
    cook_proj_cluster = cook_proj_eqs > 0
    print(f"  [Cluster 2] COOK↔PROJ equivalences: {cook_proj_eqs}"
          f"  {'← cluster' if cook_proj_cluster else '← NO cluster'}")
    results["cook_proj_cluster"] = cook_proj_cluster

    # ── 3. Cross-family pairs
    print("\n  Cross-family (canon ↔ bootstrapped):")
    cross_pairs = [
        "EN↔COOK", "EN↔PROJ", "DE↔COOK", "DE↔PROJ",
        "ONTO↔COOK", "ONTO↔PROJ",
    ]
    for pair in cross_pairs:
        eqs = final.dream_eq_counts.get(pair, 0)
        pre = pre_scores.get(pair, float("nan"))
        post = post_scores.get(pair, float("nan"))
        shift = post - pre
        print(f"    {pair:12s}: eq={eqs:4d}  "
              f"compat {pre:.3f}→{post:.3f} (Δ={shift:+.3f})")

    # ── 4. ONTO as bridge node
    #    ONTO becomes compatible with COOK/PROJ post-navigation
    #    (WL fingerprints shift drastically, Δ > 1.0).
    #    DE stays isolated: DE↔ONTO, DE↔COOK, DE↔PROJ all > 0.6.
    onto_cook_eq = final.dream_eq_counts.get("ONTO↔COOK", 0)
    onto_proj_eq = final.dream_eq_counts.get("ONTO↔PROJ", 0)
    onto_bridges = onto_cook_eq > 0 and onto_proj_eq > 0
    print(f"\n  ONTO↔COOK eq: {onto_cook_eq}  ONTO↔PROJ eq: {onto_proj_eq}"
          f"  {'← ONTO bridges clusters' if onto_bridges else '← no bridging'}")
    results["onto_bridges"] = onto_bridges

    # DE isolation (actual isolate in N=5)
    de_cross = ["DE↔COOK", "DE↔PROJ"]
    de_cross_eq = sum(final.dream_eq_counts.get(p, 0) for p in de_cross)
    de_isolated = de_cross_eq == 0
    print(f"  DE cross-bootstrapped eq: {de_cross_eq}"
          f"  {'← DE isolated from bootstrapped' if de_isolated else '← DE connected'}")
    results["de_isolated_from_bootstrapped"] = de_isolated

    # ── 5. Weight differentiation
    print("\n  Final coupling weights:")
    for label in ALL_LABELS:
        w = final.weights[label]
        print(f"    {label:6s}: {w:.4f}")
    results["final_weights"] = dict(final.weights)

    # ── 6. Compatibility shift summary
    print("\n  Compatibility shifts (pre → post navigation):")
    shifted_pairs = []
    for pair in sorted(pre_scores):
        pre = pre_scores[pair]
        post = post_scores[pair]
        delta = post - pre
        crossed = (pre >= COMPATIBILITY_THRESHOLD) != (post >= COMPATIBILITY_THRESHOLD)
        marker = "  ◆ BOUNDARY CROSSED" if crossed else ""
        print(f"    {pair:12s}: {pre:.4f} → {post:.4f}  (Δ={delta:+.4f}){marker}")
        if crossed:
            shifted_pairs.append(pair)
    results["boundary_crossed"] = shifted_pairs

    # ── 7. Equivalence accumulation table
    print("\n  Equivalence accumulation (non-zero pairs):")
    active_pairs = set()
    for m in metrics:
        for k, v in m.dream_eq_counts.items():
            if v > 0:
                active_pairs.add(k)
    active_pairs = sorted(active_pairs)
    if active_pairs:
        header = "    Ep  " + "  ".join(f"{p:>10s}" for p in active_pairs)
        print(header)
        for m in metrics:
            vals = "  ".join(
                f"{m.dream_eq_counts.get(p, 0):10d}" for p in active_pairs)
            print(f"    {m.episode:2d}  {vals}")
    else:
        print("    (no equivalences found)")

    # ── 8. Weight evolution
    print("\n  Weight evolution:")
    w_header = "    Ep  " + "  ".join(f"{l:>7s}" for l in ALL_LABELS)
    print(w_header)
    for m in metrics:
        wvals = "  ".join(f"{m.weights[l]:7.3f}" for l in ALL_LABELS)
        print(f"    {m.episode:2d}  {wvals}")

    print()
    return results


def phase_verdict(results: dict) -> None:
    """Final verdict."""
    print("=" * 70)
    checks = [
        ("EN↔DE cluster formed (dream equivalences > 0)",
         results["en_de_cluster"]),
        ("COOK↔PROJ cluster formed (same-size topology)",
         results["cook_proj_cluster"]),
        ("ONTO bridges clusters (ONTO↔COOK + ONTO↔PROJ > 0)",
         results["onto_bridges"]),
        ("DE isolated from bootstrapped (DE↔COOK + DE↔PROJ = 0)",
         results["de_isolated_from_bootstrapped"]),
    ]
    all_pass = True
    for desc, ok in checks:
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        print(f"  [{status}] {desc}")

    # Info-only (not pass/fail):
    if results["boundary_crossed"]:
        print(f"\n  INFO: Compatibility boundary crossed: "
              f"{results['boundary_crossed']}")
    else:
        print(f"\n  INFO: No compatibility boundaries crossed")

    print("\n" + ("  ◆ ALL CHECKS PASSED" if all_pass
                  else "  ◆ SOME CHECKS FAILED — see analysis above"))
    print("=" * 70)


# ── Main ─────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("C180 — N-Domain Mesh Exploration (N=5: EN + DE + ONTO + COOK + PROJ)")
    print("=" * 70)
    print()

    trained = phase_domain_prep()
    pre_scores = phase_compatibility(trained, phase_label="2a")
    observer, router, controllers = phase_mesh_assembly(trained)
    metrics = phase_episodes(observer, router, controllers, trained)
    post_scores = phase_compatibility(trained, phase_label="5")
    results = phase_analysis(metrics, pre_scores, post_scores)
    phase_verdict(results)


if __name__ == "__main__":
    main()
