"""E₀ Demo — Curriculum-Driven Canon Learning (C143)
=====================================================
Demonstrates level-by-level learning on the ontodynamics canon:
  CurriculumRunner divides 51 nodes (18 derivation levels) into turns,
  builds scoped sub-landscapes per turn, transfers historization between
  turns, and detects equilibrium via structural temperature.

The ontodynamics canon encodes E₀'s own conceptual structure — from
primitive concepts (difference, connection) through derived layers
(state, resistance, mass) to implementation (controller, dream_mode,
sleep_wake_cycle).  "E₀ learns E₀."

Usage:
    # Default (ontodynamics, 3 turns):
    py -3 -m e0_controller.demo_curriculum

    # Custom canon:
    py -3 -m e0_controller.demo_curriculum --canon english_basic

    # Custom boundaries (2 turns: levels 0-8, 0-17):
    py -3 -m e0_controller.demo_curriculum --boundaries 8 17

    # With entropy/sleep-wake:
    py -3 -m e0_controller.demo_curriculum --entropy
"""

from __future__ import annotations

import sys

from e0_controller.primitives import Outcome
from e0_controller.canon_loader import load_canon
from e0_controller.curriculum import (
    CurriculumRunner,
    CurriculumStrategy,
    TurnResult,
)
from e0_controller.structural_entropy import (
    structural_temperature,
    dream_pressure,
    find_anchors,
    find_decay_candidates,
)
from e0_controller.dream_mode import DreamObserver
from e0_controller.sleep_wake import SleepWakeCycle
from e0_controller.controller import E0Controller
from e0_controller.mode_controller import ModeController


# ── Demo runner ───────────────────────────────────────────────────────

def run_demo(
    canon_name: str = "ontodynamics",
    boundaries: list[int] | None = None,
    use_entropy: bool = False,
) -> dict:
    """Run the curriculum demo. Returns results dict.

    Args:
        canon_name: Canon to learn (default: ontodynamics).
        boundaries: Custom derivation level boundaries for turns.
        use_entropy: If True, run SleepWakeCycle after curriculum.
    """
    print("=" * 64)
    print("E₀ — Curriculum Demo (C143)")
    if use_entropy:
        print("     + Structural Entropy / Sleep-Wake")
    print("=" * 64)

    execute_fn = lambda s, t: Outcome.SUCCESS

    # ── Phase 1: Load Canon ──────────────────────────────────────
    print("\n── Phase 1: Canon Loading ──")

    cl = load_canon(canon_name)
    info = cl.info

    print(f"   Canon:   {info.name} v{info.version}")
    print(f"   Nodes:   {len(info.nodes)}")
    print(f"   Edges:   {len(info.edges)}")
    print(f"   Source:  {info.source}")

    # Show level distribution
    level_counts: dict[int, int] = {}
    for node in info.nodes:
        lv = node.derivation_level
        level_counts[lv] = level_counts.get(lv, 0) + 1

    max_level = max(level_counts.keys()) if level_counts else 0
    print(f"   Levels:  0–{max_level} ({len(level_counts)} distinct)")
    for lv in sorted(level_counts):
        print(f"     L{lv:>2}: {level_counts[lv]} nodes")

    if info.goal_states:
        print(f"   Goals:   {', '.join(info.goal_states)}")

    # ── Phase 2: Build Curriculum Strategy ───────────────────────
    print("\n── Phase 2: Curriculum Strategy ──")

    strategy = CurriculumStrategy(info, boundaries=boundaries)
    turns = strategy.turns()

    print(f"   Boundaries: {strategy.boundaries}")
    print(f"   Turns:       {len(turns)}")
    for t in turns:
        print(f"     {t.scope}: {len(t.node_ids)} nodes"
              f"{f', goal={t.goal}' if t.goal else ''}")

    # ── Phase 3: Execute Curriculum ──────────────────────────────
    print("\n── Phase 3: Curriculum Execution ──")

    runner = CurriculumRunner(
        canon_name,
        execute_fn,
        strategy=strategy,
        equilibrium_threshold=2.0,
        equilibrium_patience=3,
        max_episodes_per_turn=15,
        max_cycles_per_episode=40,
    )

    results = runner.run()

    for r in results:
        eq = "✓ equilibrium" if r.equilibrium_reached else "✗ max episodes"
        print(f"   {r.turn.scope}:")
        print(f"     Nodes:     {len(r.turn.node_ids)}")
        print(f"     Episodes:  {r.episodes}")
        print(f"     Steps:     {r.total_steps}")
        print(f"     T_s:       {r.final_T_s:.3f}")
        print(f"     Status:    {eq}")

    # ── Phase 4: Final Landscape Inspection ──────────────────────
    print("\n── Phase 4: Final Landscape ──")

    L = runner.final_landscape
    if L is not None:
        mc = ModeController(L)
        mode = mc.current_mode()
        cov = mc.coverage()
        T_s = structural_temperature(L.historization)

        print(f"   States:   {len(L.states)}")
        print(f"   Edges:    {L.edge_count()}")
        print(f"   Mode:     {mode.value}")
        print(f"   Coverage: {cov['explored']}/{cov['total']} "
              f"({cov['ratio']:.0%})")
        print(f"   T_s:      {T_s:.3f}")
    else:
        print("   (no landscape — curriculum produced no turns)")

    # ── Phase 5 (optional): Sleep-Wake Consolidation ─────────────
    entropy_result = None
    if use_entropy and L is not None:
        print("\n── Phase 5: Sleep-Wake Consolidation ──")

        # Find start/goal for the final landscape
        start_node = sorted(L.states)[0]
        goal_node = None
        if info.goal_states:
            for gs in info.goal_states:
                if gs in L.states:
                    goal_node = gs
                    break

        protected = {start_node}
        if goal_node:
            protected.add(goal_node)

        obs = DreamObserver(
            readiness_threshold=0.0,
            decay_enabled=True,
            theta_base=0.5,
            protected_fn=lambda domain: protected,
        )
        obs.register("canon", L)

        ctrl_e = E0Controller(L, execute_fn, inscription_threshold=True)
        swc = SleepWakeCycle(obs, mu=5.0, max_dream_cycles=5)
        swc.register("canon", ctrl_e, start_node, goal_node)

        episodes = swc.run(n_episodes=3, max_cycles_per_run=20)

        sleep_count = sum(1 for ep in episodes if ep.slept)
        dream_count = sum(
            len(ep.sleep.dream_results) for ep in episodes
            if ep.slept and ep.sleep
        )

        for ep in episodes:
            w = ep.wake
            line = (f"   Ep {ep.episode}: T_s {w.T_s_before:.3f}→"
                    f"{w.T_s_after:.3f}  p={w.pressure_after:.3f}")
            if ep.slept and ep.sleep:
                line += (f"  → SLEEP (dream×{len(ep.sleep.dream_results)}, "
                         f"T_s→{ep.sleep.T_s_after:.3f})")
            else:
                line += "  → awake"
            print(line)

        anchors = find_anchors(L.states, L.historization, list(L.edges),
                               theta_base=0.5)
        candidates = find_decay_candidates(
            L.states, L.historization, list(L.edges),
            theta_base=0.5, protected=protected,
        )

        print(f"\n   Anchors:          {len(anchors)} / {len(L.states)}")
        print(f"   Decay candidates: {len(candidates)}")
        print(f"   Sleep phases:     {sleep_count}")
        print(f"   Dream cycles:     {dream_count}")

        pr = swc.pressure_report()
        for name, pinfo in pr.items():
            print(f"   {name}: T_s={pinfo['T_s']:.3f}, "
                  f"pressure={pinfo['pressure']:.3f}")

        entropy_result = {
            "episodes": len(episodes),
            "sleep_phases": sleep_count,
            "dream_cycles": dream_count,
            "anchor_count": len(anchors),
            "decay_candidate_count": len(candidates),
            "pressure_report": pr,
        }

    # ── Summary ──────────────────────────────────────────────────
    print(f"\n{'=' * 64}")
    print("Summary")
    print(f"{'=' * 64}")
    print(f"  Canon:        {info.name} v{info.version}")
    print(f"  Turns:        {len(results)}")

    total_episodes = sum(r.episodes for r in results)
    total_steps = sum(r.total_steps for r in results)
    eq_count = sum(1 for r in results if r.equilibrium_reached)
    print(f"  Episodes:     {total_episodes}")
    print(f"  Steps:        {total_steps}")
    print(f"  Equilibrium:  {eq_count}/{len(results)} turns")

    if L is not None:
        print(f"  Final T_s:    {structural_temperature(L.historization):.3f}")
        print(f"  Coverage:     {len(L.states)} states, {L.edge_count()} edges")

    if use_entropy and entropy_result:
        print(f"  Anchors:      {entropy_result['anchor_count']}")
        print(f"  Sleep-Wake:   {entropy_result['sleep_phases']} sleep, "
              f"{entropy_result['dream_cycles']} dream")

    print(f"  Key insight:  Curriculum turns build cumulatively — each turn")
    print(f"                inherits historization from the previous, so the")
    print(f"                system never starts from zero.  Equilibrium detection")
    print(f"                (T_s stable below threshold) replaces fixed episode counts.")
    print(f"{'=' * 64}")

    res = {
        "canon_info": info,
        "results": results,
        "final_landscape": L,
        "total_episodes": total_episodes,
        "total_steps": total_steps,
        "equilibrium_count": eq_count,
    }
    if entropy_result:
        res["entropy"] = entropy_result
    return res


# ── CLI ───────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    canon_name = "ontodynamics"
    boundaries = None
    use_entropy = False

    i = 0
    while i < len(args):
        if args[i] == "--canon" and i + 1 < len(args):
            canon_name = args[i + 1]
            i += 1
        elif args[i] == "--boundaries":
            boundaries = []
            i += 1
            while i < len(args) and not args[i].startswith("--"):
                boundaries.append(int(args[i]))
                i += 1
            continue
        elif args[i] == "--entropy":
            use_entropy = True
        elif args[i] in ("--help", "-h"):
            print(__doc__)
            return
        i += 1

    run_demo(
        canon_name=canon_name,
        boundaries=boundaries,
        use_entropy=use_entropy,
    )


if __name__ == "__main__":
    main()
