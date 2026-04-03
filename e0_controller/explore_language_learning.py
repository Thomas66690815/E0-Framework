#!/usr/bin/env python3
"""
E₀ Language Learning Exploration (C124)
=========================================
Full-stack demonstration: English ↔ German vocabulary learning
exercising all 12 architectural layers.

Phases:
    1. Canon Loading      — load english_basic + german_basic
    2. Curriculum EN      — hierarchical learning (primitives → body → food → actions → …)
    3. Curriculum DE      — same structure, German vocabulary
    4. Mode Assessment    — ModeController coverage on both learned landscapes
    5. Structural Entropy — T_s and dream pressure after curriculum
    6. Dream Discovery    — DreamObserver finds cross-language equivalences (cognates!)
    7. Multiverse         — EN↔DE coupling with novelty detection
    8. Sleep-Wake         — automatic wake/dream rhythm across both domains
    9. Activity Summary   — which module was active when, what was discovered

Expected discovery: cognate pairs (hand↔Hand, finger↔Finger, arm↔Arm,
salt↔Salz, milch↔Milk, apfel↔Apple) should emerge as low-distance
dream equivalences because their topological positions and historization
fingerprints match across languages.
"""

import sys
import os
from dataclasses import dataclass, field
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from e0_controller.canon_loader import load_canon, format_canon_summary
from e0_controller.curriculum import CurriculumRunner
from e0_controller.controller import E0Controller
from e0_controller.primitives import Outcome
from e0_controller.structural_entropy import (
    structural_temperature, dream_pressure,
)
from e0_controller.mode_controller import ModeController
from e0_controller.dream_mode import DreamObserver
from e0_controller.multiverse import MultiverseController, Universe
from e0_controller.sleep_wake import SleepWakeCycle


# ──────────────────────────────────────────────
# Activity Log
# ──────────────────────────────────────────────

@dataclass
class Activity:
    phase: int
    module: str
    action: str
    detail: str


LOG: List[Activity] = []


def log(phase: int, module: str, action: str, detail: str = "") -> None:
    LOG.append(Activity(phase, module, action, detail))


EXEC_FN = lambda s, t: Outcome.SUCCESS  # noqa: E731


# ──────────────────────────────────────────────
# Banner
# ──────────────────────────────────────────────

def banner() -> None:
    print("=" * 72)
    print("  E₀ Language Learning — Full 12-Layer Exploration (C124)")
    print("=" * 72)
    print()


# ──────────────────────────────────────────────
# Phase 1: Canon Loading
# ──────────────────────────────────────────────

def phase_canons() -> None:
    print("── Phase 1: Canon Loading ──────────────────────────────")
    for name in ("english_basic", "german_basic"):
        cl = load_canon(name)
        info = cl.info
        n_edges = len(list(cl.landscape.edges))
        print(f"  {info.name} v{info.version}: "
              f"{len(info.nodes)} nodes, {n_edges} edges, "
              f"goals={info.goal_states}")
        log(1, "canon_loader", "load_canon", f"{name}: {len(info.nodes)}N {n_edges}E")
    print()


# ──────────────────────────────────────────────
# Phase 2 & 3: Curriculum Learning
# ──────────────────────────────────────────────

def phase_curriculum(canon_name: str, label: str, phase_nr: int) -> CurriculumRunner:
    print(f"── Phase {phase_nr}: Curriculum ({label}) ───────────────────────")
    runner = CurriculumRunner(
        canon_name,
        EXEC_FN,
        equilibrium_threshold=2.0,
        equilibrium_patience=3,
        max_episodes_per_turn=15,
        max_cycles_per_episode=40,
    )
    log(phase_nr, "CurriculumRunner", "init", f"{canon_name}")

    results = runner.run()
    log(phase_nr, "CurriculumRunner", "run", f"{len(results)} turns")

    for r in results:
        eq = "✓ eq" if r.equilibrium_reached else "✗ max"
        print(f"  Turn '{r.turn.scope}' (≤L{r.turn.level_max}): "
              f"{r.episodes} ep, {r.total_steps} steps, "
              f"T_s={r.final_T_s:.2f} [{eq}]")
        log(phase_nr, "EquilibriumDetector", "observe",
            f"{r.turn.scope}: T_s={r.final_T_s:.2f}")

    L = runner.final_landscape
    if L is not None:
        T_s = structural_temperature(L.historization)
        print(f"  Final T_s = {T_s:.3f}")
        log(phase_nr, "structural_entropy", "T_s", f"{T_s:.3f}")
    print()
    return runner


# ──────────────────────────────────────────────
# Phase 4: Mode Assessment
# ──────────────────────────────────────────────

def phase_mode(en_L, de_L) -> None:
    print("── Phase 4: Mode Assessment ────────────────────────────")
    for label, L in [("EN", en_L), ("DE", de_L)]:
        mc = ModeController(L)
        mode = mc.current_mode()
        cov = mc.coverage()
        print(f"  {label}: mode={mode.value}, "
              f"coverage={cov['ratio']:.1%} "
              f"({cov['explored']}/{cov['total']} edges explored)")
        log(4, "ModeController", "current_mode",
            f"{label}: {mode.value} ({cov['ratio']:.1%})")
    print()


# ──────────────────────────────────────────────
# Phase 5: Structural Entropy
# ──────────────────────────────────────────────

def phase_temperature(en_L, de_L) -> None:
    print("── Phase 5: Structural Entropy ─────────────────────────")
    for label, L in [("EN", en_L), ("DE", de_L)]:
        T_s = structural_temperature(L.historization)
        dp = dream_pressure(L.historization)
        print(f"  {label}: T_s={T_s:.3f}, dream_pressure={dp:.3f}")
        log(5, "structural_entropy", "measure",
            f"{label}: T_s={T_s:.3f} dp={dp:.3f}")
    print()


# ──────────────────────────────────────────────
# Phase 6: Dream Discovery
# ──────────────────────────────────────────────

def phase_dream(en_L, de_L) -> DreamObserver:
    print("── Phase 6: Dream Discovery ────────────────────────────")
    obs = DreamObserver(readiness_threshold=0.3, quantile=0.15)
    obs.register("EN", en_L)
    obs.register("DE", de_L)
    log(6, "DreamObserver", "register", "EN + DE")

    # Readiness check
    rr = obs.readiness_report()
    for name, val in rr.items():
        print(f"  Dream readiness {name}: {val:.3f}")
    log(6, "DreamObserver", "readiness", str(rr))

    # Run dream cycles
    n_cycles = 3
    for i in range(n_cycles):
        result = obs.dream_cycle()
        print(f"  Dream cycle {i+1}: "
              f"{result.equivalences_found} equivalences found, "
              f"{result.equivalences_new} new, "
              f"{result.dream_landscape_edges} dream edges")
        log(6, "DreamObserver", "dream_cycle",
            f"cycle {i+1}: {result.equivalences_found} eq")

    # Show top equivalences (cross-language bridges)
    en_eq = obs.equivalences_for("EN")
    if en_eq:
        print(f"\n  Top cross-language equivalences ({len(en_eq)} total):")
        for eq in en_eq[:10]:
            own = eq["own_state"]
            partner = eq["partner_state"]
            tq = eq["trace_quality"]
            print(f"    {own:30s} ↔ {partner:30s}  q={tq:+.3f}")
            log(6, "DreamObserver", "equivalence",
                f"{own} ↔ {partner}")
    print()
    return obs


# ──────────────────────────────────────────────
# Phase 7: Multiverse Coupling
# ──────────────────────────────────────────────

def phase_multiverse(en_L, de_L) -> None:
    print("── Phase 7: Multiverse EN↔DE ───────────────────────────")
    # Pick start/goal from each landscape
    en_states = list(en_L.states)
    de_states = list(de_L.states)
    en_start = "thing" if "thing" in en_states else en_states[0]
    en_goal = "self" if "self" in en_states else en_states[-1]
    de_start = "ding" if "ding" in de_states else de_states[0]
    de_goal = "selbst" if "selbst" in de_states else de_states[-1]

    uni_en = Universe(
        name="EN", landscape=en_L, execute_fn=EXEC_FN,
        start=en_start, goal=en_goal,
    )
    uni_de = Universe(
        name="DE", landscape=de_L, execute_fn=EXEC_FN,
        start=de_start, goal=de_goal,
    )
    log(7, "MultiverseController", "init", "EN + DE")

    mc = MultiverseController(
        uni_en, uni_de,
        convergence_window=3,
        max_steps_per_turn=10,
        coupling_delta=0.8,
        coupling_resistance=0.5,
    )
    result = mc.run(max_turns=12)
    log(7, "MultiverseController", "run", result.summary())

    print(f"  Turns: {result.total_turns}, "
          f"novelty: {result.total_novelty}/{result.total_turns} "
          f"({result.novelty_rate:.0%})")
    print(f"  Convergence: {'turn ' + str(result.convergence_turn) if result.converged else 'none'}")
    print(f"  Divergence pressure applied: {result.divergence_count}x")
    print(f"  Novelty edges added: {result.novelty_edges_added}")
    print()


# ──────────────────────────────────────────────
# Phase 8: Sleep-Wake Consolidation
# ──────────────────────────────────────────────

def phase_sleep_wake(en_L, de_L, obs: DreamObserver) -> None:
    print("── Phase 8: Sleep-Wake Consolidation ───────────────────")

    # Create fresh controllers on the (already-learned) landscapes
    en_states = list(en_L.states)
    de_states = list(de_L.states)
    en_start = "thing" if "thing" in en_states else en_states[0]
    en_goal = "self" if "self" in en_states else en_states[-1]
    de_start = "ding" if "ding" in de_states else de_states[0]
    de_goal = "selbst" if "selbst" in de_states else de_states[-1]

    ctrl_en = E0Controller(en_L, EXEC_FN, inscription_threshold=True)
    ctrl_de = E0Controller(de_L, EXEC_FN, inscription_threshold=True)

    swc = SleepWakeCycle(obs, mu=5.0, max_dream_cycles=5)
    swc.register("EN", ctrl_en, en_start, en_goal)
    swc.register("DE", ctrl_de, de_start, de_goal)
    log(8, "SleepWakeCycle", "register", "EN + DE")

    episodes = swc.run(n_episodes=4, max_cycles_per_run=30)
    log(8, "SleepWakeCycle", "run", f"{len(episodes)} episodes")

    for ep in episodes:
        wake = ep.wake
        status = "wake"
        detail = (f"domain={wake.domain}, "
                  f"steps={len(wake.trace.steps)}, "
                  f"T_s={wake.T_s_after:.3f}")
        if ep.slept and ep.sleep is not None:
            status = "wake+sleep"
            detail += (f" → dream×{len(ep.sleep.dream_results)}, "
                       f"T_s_after={ep.sleep.T_s_after:.3f}")
        print(f"  Episode {ep.episode}: [{status}] {detail}")
        log(8, "SleepWakeCycle", status,
            f"ep{ep.episode}: {detail}")
    print()


# ──────────────────────────────────────────────
# Phase 9: Activity Summary
# ──────────────────────────────────────────────

def phase_summary() -> None:
    print("── Phase 9: Activity Summary ───────────────────────────")
    print(f"  Total module activations: {len(LOG)}")
    print()

    # Module frequency table
    modules: dict[str, int] = {}
    for a in LOG:
        modules[a.module] = modules.get(a.module, 0) + 1
    print("  Module Activity:")
    for mod, count in sorted(modules.items(), key=lambda x: -x[1]):
        print(f"    {mod:30s} {count:3d} activations")
    print()

    # Phase timeline
    print("  Timeline:")
    for a in LOG:
        print(f"    [P{a.phase}] {a.module:25s} {a.action:15s} {a.detail}")
    print()
    print("=" * 72)
    print("  Done — all 12 layers exercised.")
    print("=" * 72)


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main() -> None:
    banner()

    # Phase 1: Load canons
    phase_canons()

    # Phase 2 & 3: Curriculum learning
    en_runner = phase_curriculum("english_basic", "EN", phase_nr=2)
    de_runner = phase_curriculum("german_basic", "DE", phase_nr=3)

    en_L = en_runner.final_landscape
    de_L = de_runner.final_landscape
    assert en_L is not None, "EN curriculum produced no landscape"
    assert de_L is not None, "DE curriculum produced no landscape"

    # Phase 4: Mode assessment
    phase_mode(en_L, de_L)

    # Phase 5: Structural entropy
    phase_temperature(en_L, de_L)

    # Phase 6: Dream discovery
    obs = phase_dream(en_L, de_L)

    # Phase 7: Multiverse coupling
    phase_multiverse(en_L, de_L)

    # Phase 8: Sleep-wake consolidation
    phase_sleep_wake(en_L, de_L, obs)

    # Phase 9: Summary
    phase_summary()


if __name__ == "__main__":
    main()
