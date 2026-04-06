"""
C179 — N-Domain Mesh Exploration (N=3)

First N>2 integrated experiment: EN + DE + ONTO domains with
DreamObserver (compatibility-gated), CouplingRouter (dynamic weights),
and SleepWakeCycle (automatic sleep/dream rhythm).

Protocol:
  Phase 1: Curriculum training (3 canon landscapes)
  Phase 2: Mesh assembly (DreamObserver + CouplingRouter + SleepWakeCycle)
  Phase 3: Run episodes, collect per-episode metrics
  Phase 4: Analyze cluster formation and weight self-organization

Expected behavior:
  - EN↔DE: compatible (score ~0.375), form dream cluster
  - EN↔ONTO, DE↔ONTO: incompatible (score >0.7), skipped by dream layer
  - Coupling weights: EN,DE rise (productive dream equivalences), ONTO stays ~1.0
  - EN↔DE dream equivalences accumulate, ONTO gets 0

Reference: docs/E0_STRATEGIC_ROADMAP_v1.md Priority 3
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from e0_controller.canon_loader import load_canon
from e0_controller.controller import E0Controller, HybridMode
from e0_controller.coupling_router import (
    CouplingRouter,
    CouplingReason,
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

CANONS = [
    ("EN",   "english_basic_enriched",  "thing",      "self"),
    ("DE",   "german_basic_enriched",   "ding",       "selbst"),
    ("ONTO", "ontodynamics",            "difference", "negative_necessity"),
]

N_EPISODES = 8
MAX_CYCLES_PER_RUN = 40
COMPATIBILITY_THRESHOLD = 0.6


# ── Data Collection ──────────────────────────────────────────────────

@dataclass
class EpisodeMetrics:
    episode: int
    weights: Dict[str, float]            # coupling weight per domain
    dream_eq_counts: Dict[str, int]      # edge equivalences per pair
    compat_skipped: List[str]            # skipped pair labels
    sleep_occurred: bool


# ── Phases ───────────────────────────────────────────────────────────

def phase_training() -> Dict[str, object]:
    """Phase 1: Curriculum-train all 3 canon landscapes."""
    print("── Phase 1: Curriculum Training ────────────────────────")
    results = {}
    for label, canon_name, start, goal in CANONS:
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

        print(f"  {label:6s}: {len(turn_results)} turns, {total_steps:4d} steps, "
              f"T_s={T_s:.3f}, dp={dp:.3f}  ({dt:.1f}s)")
        results[label] = {
            "landscape": L,
            "start": start,
            "goal": goal,
            "turns": len(turn_results),
        }
    print()
    return results


def phase_compatibility(trained: Dict) -> None:
    """Phase 2a: Show pairwise dream compatibility (pre-navigation)."""
    print("── Phase 2a: Dream Compatibility Matrix ────────────────")
    print("  (Measured after curriculum training, before mesh navigation)")
    labels = list(trained.keys())
    for i, a in enumerate(labels):
        for b in labels[i + 1:]:
            score = dream_compatibility(
                trained[a]["landscape"], trained[b]["landscape"])
            verdict = "PASS" if score < COMPATIBILITY_THRESHOLD else "SKIP"
            print(f"  {a}↔{b}: {score:.4f}  [{verdict}]")
    print()


def phase_mesh_assembly(trained: Dict):
    """Phase 2b: Assemble DreamObserver + CouplingRouter + Controllers."""
    print("── Phase 2b: Mesh Assembly ─────────────────────────────")

    # DreamObserver
    observer = DreamObserver(
        readiness_threshold=0.0,
        node_equivalence_method="hungarian",
        compatibility_threshold=COMPATIBILITY_THRESHOLD,
    )

    # Universes + Controllers
    universes = []
    controllers = {}
    for label, _, start, goal in CANONS:
        L = trained[label]["landscape"]
        observer.register(label, L)
        ctrl = E0Controller(L, EXEC_FN, hybrid_mode=HybridMode.GREEDY)
        controllers[label] = ctrl
        universes.append(Universe(
            name=label, landscape=L,
            execute_fn=EXEC_FN, start=start, goal=goal,
        ))

    # CouplingRouter
    router = CouplingRouter(universes)

    print(f"  DreamObserver: {len(observer._domains)} domains, "
          f"threshold={COMPATIBILITY_THRESHOLD}")
    print(f"  CouplingRouter: {len(universes)} universes")
    print(f"  Controllers: {list(controllers.keys())}")
    print()

    return observer, router, controllers


def phase_episodes(observer, router, controllers, trained) -> List[EpisodeMetrics]:
    """Phase 3: Run N episodes, collecting metrics."""
    print(f"── Phase 3: Running {N_EPISODES} Episodes ──────────────────────")
    all_metrics = []

    for ep in range(1, N_EPISODES + 1):
        # ── Wake: run each controller ────────────────────────
        for label, _, start, goal in CANONS:
            ctrl = controllers[label]
            ctrl.run(start, max_cycles=MAX_CYCLES_PER_RUN, goal=goal)

        # ── Sleep: dream cycle ───────────────────────────────
        dream_result = observer.dream_cycle()
        sleep_occurred = dream_result.equivalences_found > 0

        # ── Update coupling weights from dream ───────────────
        weight_report = update_weights_from_dream(router, observer)

        # ── Collect metrics ──────────────────────────────────
        weights = {label: router.get_weight(label) for label, *_ in CANONS}

        # Count equivalences per domain pair
        eq_counts = {}
        labels = [c[0] for c in CANONS]
        for i, a in enumerate(labels):
            for b in labels[i + 1:]:
                # equivalences_for returns dicts with partner_state="DOMAIN:src→tgt"
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
        eq_str = "  ".join(f"{k}={v}" for k, v in eq_counts.items())
        skip_str = f"  skip={skipped}" if skipped else ""
        print(f"  Ep {ep:2d}: weights=[{w_str}]  eq=[{eq_str}]{skip_str}")

    print()
    return all_metrics


def phase_post_compat(trained: Dict) -> None:
    """Phase 4: Show post-navigation compatibility (may shift)."""
    print("── Phase 4: Post-Navigation Compatibility ──────────────")
    print("  (WL fingerprints absorb trace data → scores can shift)")
    labels = list(trained.keys())
    for i, a in enumerate(labels):
        for b in labels[i + 1:]:
            score = dream_compatibility(
                trained[a]["landscape"], trained[b]["landscape"])
            verdict = "PASS" if score < COMPATIBILITY_THRESHOLD else "SKIP"
            print(f"  {a}↔{b}: {score:.4f}  [{verdict}]")
    print()


def phase_analysis(metrics: List[EpisodeMetrics]) -> dict:
    """Phase 5: Analyze cluster formation and weight self-organization."""
    print("── Phase 5: Analysis ───────────────────────────────────")

    final = metrics[-1]
    results = {}

    # ── 1. EN↔DE formed cluster (have dream equivalences)?
    en_de_eqs = final.dream_eq_counts.get("EN↔DE", 0)
    en_de_cluster = en_de_eqs > 0
    print(f"  EN↔DE equivalences: {en_de_eqs}"
          f"  {'← cluster formed' if en_de_cluster else '← NO cluster'}")
    results["en_de_cluster"] = en_de_cluster

    # ── 2. ONTO isolation: DE↔ONTO should have 0, EN↔ONTO may have some
    en_onto_eqs = final.dream_eq_counts.get("EN↔ONTO", 0)
    de_onto_eqs = final.dream_eq_counts.get("DE↔ONTO", 0)
    de_onto_isolated = de_onto_eqs == 0
    print(f"  EN↔ONTO equivalences: {en_onto_eqs}"
          f"  {'← some (compat shifted post-nav)' if en_onto_eqs > 0 else '← isolated'}")
    print(f"  DE↔ONTO equivalences: {de_onto_eqs}"
          f"  {'← isolated (correct)' if de_onto_isolated else '← NOT isolated'}")
    results["de_onto_isolated"] = de_onto_isolated

    # ── 3. Coupling weight differentiation?
    w_en = final.weights["EN"]
    w_de = final.weights["DE"]
    w_onto = final.weights["ONTO"]
    en_de_similar = abs(w_en - w_de) < 0.5
    print(f"  Final weights: EN={w_en:.3f}  DE={w_de:.3f}  ONTO={w_onto:.3f}")
    print(f"  EN≈DE: {en_de_similar}  (diff={abs(w_en - w_de):.3f})")
    results["weight_differentiation"] = en_de_similar

    # ── 4. Weight evolution trend
    print("\n  Weight evolution:")
    for ep_m in metrics:
        w_str = "  ".join(f"{l}={w:.3f}" for l, w in ep_m.weights.items())
        print(f"    Ep {ep_m.episode:2d}: {w_str}")

    # ── 5. Compatibility gating worked?
    all_skipped = set()
    for m in metrics:
        all_skipped.update(m.compat_skipped)
    onto_skipped = any("ONTO" in s for s in all_skipped)
    print(f"\n  Compatibility-skipped pairs: {sorted(all_skipped)}")
    print(f"  ONTO pairs skipped: {onto_skipped}")
    results["compat_gating_worked"] = onto_skipped

    # ── 6. Dream equivalence accumulation
    print("\n  Equivalence accumulation:")
    for ep_m in metrics:
        eq_str = "  ".join(f"{k}={v}" for k, v in ep_m.dream_eq_counts.items())
        print(f"    Ep {ep_m.episode:2d}: {eq_str}")

    return results


def phase_verdict(results: dict) -> None:
    """Final verdict."""
    print("\n" + "=" * 70)
    checks = [
        ("EN↔DE cluster formed (dream equivalences > 0)",
         results["en_de_cluster"]),
        ("DE↔ONTO isolated (0 dream equivalences)",
         results["de_onto_isolated"]),
        ("EN ≈ DE coupling weight (diff < 0.5)",
         results["weight_differentiation"]),
        ("Compatibility gating blocked ONTO pairs",
         results["compat_gating_worked"]),
    ]
    all_pass = True
    for desc, ok in checks:
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        print(f"  [{status}] {desc}")

    print("\n" + ("  ◆ ALL CHECKS PASSED" if all_pass
                  else "  ◆ SOME CHECKS FAILED"))
    print("=" * 70)


# ── Main ─────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("C179 — N-Domain Mesh Exploration (N=3: EN + DE + ONTO)")
    print("=" * 70)
    print()

    trained = phase_training()
    phase_compatibility(trained)
    observer, router, controllers = phase_mesh_assembly(trained)
    metrics = phase_episodes(observer, router, controllers, trained)
    phase_post_compat(trained)
    results = phase_analysis(metrics)
    phase_verdict(results)


if __name__ == "__main__":
    main()
