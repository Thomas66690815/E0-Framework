"""E₀ Multiverse Demo — Coupled Domains with Dream Discovery (C142)
=====================================================================
Demonstrates the complete multiverse pipeline:
  Two bootstrapped domains → MultiverseController with cross-reflexion
  → NoveltyGate breaks convergence → DreamObserver discovers structural
  correspondences via Hungarian+WL node matching (C139).

Two onboarding variants (standard vs accelerated) share structural
similarities but differ in topology.  The multiverse coupling lets them
exchange experience via cross-reflexion, while NoveltyGate prevents
premature consensus.  Post-run, DreamObserver finds which states in
Domain A correspond to states in Domain B.

Usage:
    # Mock mode (no API key needed):
    py -3 -m e0_controller.demo_multiverse

    # With entropy/sleep-wake:
    py -3 -m e0_controller.demo_multiverse --entropy
"""

from __future__ import annotations

import sys

from e0_controller.primitives import Outcome, Edge
from e0_controller.landscape import Landscape
from e0_controller.bootstrapper import bootstrap_landscape
from e0_controller.controller import E0Controller
from e0_controller.multiverse import (
    Universe, MultiverseController, MultiverseResult,
)
from e0_controller.cross_reflexion import scoped_cross_reflexion_turn
from e0_controller.dream_mode import DreamObserver
from e0_controller.mode_controller import ModeController
from e0_controller.structural_entropy import (
    structural_temperature,
    dream_pressure,
    find_anchors,
    find_decay_candidates,
)
from e0_controller.sleep_wake import SleepWakeCycle


# ── Domain specs ──────────────────────────────────────────────────────

DOMAIN_A_SPEC = {
    "nodes": [
        "START", "DOCS_IN", "ACCT_CREATED", "BUDDY_ASSIGNED",
        "ORIENT_SCHED", "ORIENT_DONE", "WEEK1_REVIEW", "DONE",
        "DOCS_INCOMPLETE",
    ],
    "edges": [
        {"from": "START", "to": "DOCS_IN",
         "delta": 0.3, "resistance": 0.4,
         "initial_U": 8, "initial_F": 2, "confidence": 0.8},
        {"from": "DOCS_IN", "to": "ACCT_CREATED",
         "delta": 0.4, "resistance": 0.6,
         "initial_U": 7, "initial_F": 3, "confidence": 0.7},
        {"from": "ACCT_CREATED", "to": "BUDDY_ASSIGNED",
         "delta": 0.2, "resistance": 0.3,
         "initial_U": 9, "initial_F": 1, "confidence": 0.9},
        {"from": "BUDDY_ASSIGNED", "to": "ORIENT_SCHED",
         "delta": 0.3, "resistance": 0.5,
         "initial_U": 8, "initial_F": 2, "confidence": 0.8},
        {"from": "ORIENT_SCHED", "to": "ORIENT_DONE",
         "delta": 0.5, "resistance": 0.8,
         "initial_U": 6, "initial_F": 4, "confidence": 0.6},
        {"from": "ORIENT_DONE", "to": "WEEK1_REVIEW",
         "delta": 0.4, "resistance": 0.7,
         "initial_U": 7, "initial_F": 3, "confidence": 0.7},
        {"from": "WEEK1_REVIEW", "to": "DONE",
         "delta": 0.2, "resistance": 0.3,
         "initial_U": 9, "initial_F": 1, "confidence": 0.9},
        # Error path
        {"from": "START", "to": "DOCS_INCOMPLETE",
         "delta": 0.3, "resistance": 1.5,
         "initial_U": 2, "initial_F": 8, "confidence": 0.8},
        {"from": "DOCS_INCOMPLETE", "to": "DOCS_IN",
         "delta": 0.4, "resistance": 1.0,
         "initial_U": 5, "initial_F": 5, "confidence": 0.6},
        # Shortcut: skip orientation
        {"from": "BUDDY_ASSIGNED", "to": "WEEK1_REVIEW",
         "delta": 0.6, "resistance": 1.2,
         "initial_U": 4, "initial_F": 6, "confidence": 0.5},
    ],
}

DOMAIN_B_SPEC = {
    "nodes": [
        "ARRIVAL", "FAST_DOCS", "SYS_ACCESS", "MENTOR",
        "INTRO_SESSION", "SHADOWING", "CHECKPOINT", "PRODUCTIVE",
        "DOC_ISSUE",
    ],
    "edges": [
        {"from": "ARRIVAL", "to": "FAST_DOCS",
         "delta": 0.5, "resistance": 0.3,
         "initial_U": 10, "initial_F": 0, "confidence": 0.9},
        {"from": "FAST_DOCS", "to": "SYS_ACCESS",
         "delta": 0.4, "resistance": 0.4,
         "initial_U": 8, "initial_F": 2, "confidence": 0.8},
        {"from": "SYS_ACCESS", "to": "MENTOR",
         "delta": 0.4, "resistance": 0.4,
         "initial_U": 8, "initial_F": 2, "confidence": 0.8},
        {"from": "MENTOR", "to": "INTRO_SESSION",
         "delta": 0.3, "resistance": 0.5,
         "initial_U": 7, "initial_F": 3, "confidence": 0.7},
        {"from": "INTRO_SESSION", "to": "SHADOWING",
         "delta": 0.6, "resistance": 0.9,
         "initial_U": 5, "initial_F": 5, "confidence": 0.5},
        {"from": "SHADOWING", "to": "CHECKPOINT",
         "delta": 0.5, "resistance": 0.8,
         "initial_U": 6, "initial_F": 4, "confidence": 0.6},
        {"from": "CHECKPOINT", "to": "PRODUCTIVE",
         "delta": 0.3, "resistance": 0.4,
         "initial_U": 8, "initial_F": 2, "confidence": 0.8},
        # Error path
        {"from": "ARRIVAL", "to": "DOC_ISSUE",
         "delta": 0.4, "resistance": 1.6,
         "initial_U": 1, "initial_F": 9, "confidence": 0.9},
        {"from": "DOC_ISSUE", "to": "FAST_DOCS",
         "delta": 0.5, "resistance": 0.9,
         "initial_U": 4, "initial_F": 6, "confidence": 0.5},
        # Alternative: skip shadowing for experienced hire
        {"from": "MENTOR", "to": "CHECKPOINT",
         "delta": 0.7, "resistance": 1.3,
         "initial_U": 3, "initial_F": 7, "confidence": 0.4},
    ],
}


# ── Demo runner ───────────────────────────────────────────────────────

def run_demo(use_entropy: bool = False) -> dict:
    """Run the multiverse demo. Returns results dict."""
    print("=" * 64)
    print("E₀ — Multiverse Demo (C142)")
    if use_entropy:
        print("     + Structural Entropy / Sleep-Wake")
    print("=" * 64)

    execute_fn = lambda s, t: Outcome.SUCCESS

    # ── Phase 1: Build Landscapes ────────────────────────────────
    print("\n── Phase 1: Landscape Construction ──")

    L_a = bootstrap_landscape(DOMAIN_A_SPEC)
    L_b = bootstrap_landscape(DOMAIN_B_SPEC)

    print(f"   Domain A (Standard):     {len(L_a.states)} states, "
          f"{L_a.edge_count()} edges")
    print(f"   Domain B (Accelerated):  {len(L_b.states)} states, "
          f"{L_b.edge_count()} edges")

    # ── Phase 2: Pre-Coupling Mode Assessment ────────────────────
    print("\n── Phase 2: Pre-Coupling Mode Assessment ──")

    for label, L in [("A", L_a), ("B", L_b)]:
        mc = ModeController(L)
        mode = mc.current_mode()
        cov = mc.coverage()
        T_s = structural_temperature(L.historization)
        print(f"   Domain {label}: mode={mode.value}, "
              f"coverage={cov['explored']}/{cov['total']}, T_s={T_s:.3f}")

    # ── Phase 3: Create Universes + Run Multiverse ───────────────
    print("\n── Phase 3: Multiverse Coupling (20 turns) ──")

    uni_a = Universe(
        name="Domain-A",
        landscape=L_a,
        execute_fn=execute_fn,
        start="START",
        goal="DONE",
    )
    uni_b = Universe(
        name="Domain-B",
        landscape=L_b,
        execute_fn=execute_fn,
        start="ARRIVAL",
        goal="PRODUCTIVE",
    )

    mv_ctrl = MultiverseController(
        uni_a, uni_b,
        convergence_window=3,
        max_steps_per_turn=10,
        coupling_delta=1.0,
        coupling_resistance=0.5,
    )

    result = mv_ctrl.run(max_turns=20, turn_fn=scoped_cross_reflexion_turn)

    print(result.summary())

    # ── Phase 4: Coupling Landscape Metrics ──────────────────────
    print("\n── Phase 4: Coupling Landscape ──")

    for edge in mv_ctrl.coupling.edges:
        tq = mv_ctrl.coupling.historization.trace_quality(edge)
        tl = mv_ctrl.coupling.historization.trace_load(edge)
        print(f"   {edge.source:15s} → {edge.target:15s}  "
              f"q={tq:+.3f}  load={tl:.0f}")

    # ── Phase 5: Dream Discovery ─────────────────────────────────
    print("\n── Phase 5: Dream Discovery (Hungarian + WL) ──")

    obs = DreamObserver(
        readiness_threshold=0.0,
        quantile=0.15,
        node_equivalence_method="hungarian",
        wl_depth=2,
        decay_enabled=False,
    )
    obs.register("Domain-A", L_a)
    obs.register("Domain-B", L_b)

    dream_results = []
    for cycle_i in range(3):
        dr = obs.dream_cycle()
        dream_results.append(dr)
        print(f"   Cycle {cycle_i + 1}: "
              f"edge-EQ {dr.equivalences_found} found / {dr.equivalences_new} new, "
              f"node-EQ {dr.node_equivalences_found} found / {dr.node_equivalences_new} new")

    # ── Phase 6: Cross-Domain Correspondences ────────────────────
    print("\n── Phase 6: Structural Correspondences ──")

    for domain_name in ["Domain-A", "Domain-B"]:
        eqs = obs.equivalences_for(domain_name, min_quality=0.0)
        if eqs:
            print(f"   {domain_name} ({len(eqs)} equivalences):")
            for eq in eqs[:10]:
                print(f"     {eq['own_state']:40s} ↔ {eq['partner_state']:40s}"
                      f"  q={eq['trace_quality']:+.3f}")
        else:
            print(f"   {domain_name}: (no equivalences found)")

    # ── Phase 7 (optional): Sleep-Wake Consolidation ─────────────
    entropy_result = None
    if use_entropy:
        print("\n── Phase 7: Sleep-Wake Consolidation ──")

        obs_sw = DreamObserver(
            readiness_threshold=0.0,
            decay_enabled=True,
            theta_base=0.5,
            protected_fn=lambda domain: (
                {"START", "DONE"} if domain == "Domain-A"
                else {"ARRIVAL", "PRODUCTIVE"}
            ),
        )
        obs_sw.register("Domain-A", L_a)
        obs_sw.register("Domain-B", L_b)

        ctrl_a = E0Controller(L_a, execute_fn, inscription_threshold=True)
        ctrl_b = E0Controller(L_b, execute_fn, inscription_threshold=True)

        swc = SleepWakeCycle(obs_sw, mu=5.0, max_dream_cycles=5)
        swc.register("Domain-A", ctrl_a, "START", "DONE")
        swc.register("Domain-B", ctrl_b, "ARRIVAL", "PRODUCTIVE")

        episodes = swc.run(n_episodes=3, max_cycles_per_run=20)

        sleep_count = sum(1 for ep in episodes if ep.slept)
        dream_count = sum(
            len(ep.sleep.dream_results) for ep in episodes
            if ep.slept and ep.sleep
        )

        for ep in episodes:
            w = ep.wake
            line = (f"   Ep {ep.episode} [{w.domain}]: "
                    f"T_s {w.T_s_before:.3f}→{w.T_s_after:.3f}  "
                    f"p={w.pressure_after:.3f}")
            if ep.slept and ep.sleep:
                line += (f"  → SLEEP (dream×{len(ep.sleep.dream_results)}, "
                         f"T_s→{ep.sleep.T_s_after:.3f})")
            else:
                line += "  → awake"
            print(line)

        pr = swc.pressure_report()
        for name, info in pr.items():
            print(f"   {name}: T_s={info['T_s']:.3f}, "
                  f"pressure={info['pressure']:.3f}")

        entropy_result = {
            "episodes": len(episodes),
            "sleep_phases": sleep_count,
            "dream_cycles": dream_count,
            "pressure_report": pr,
        }

    # ── Summary ──────────────────────────────────────────────────
    print(f"\n{'=' * 64}")
    print("Summary")
    print(f"{'=' * 64}")
    print(f"  Domains:          A ({len(L_a.states)} states) + "
          f"B ({len(L_b.states)} states)")
    print(f"  Multiverse:       {result.total_turns} turns, "
          f"novelty {result.novelty_rate:.0%}")
    if result.converged:
        print(f"  Convergence:      turn {result.convergence_turn}")
    print(f"  Divergence:       {result.divergence_count}x "
          f"({result.novelty_edges_added} edges injected)")
    print(f"  Dream cycles:     {obs.cycle_count}")

    dl = obs.dream_landscape
    if dl:
        print(f"  Dream Landscape:  {len(dl.states)} states, "
              f"{len(dl.edges)} edges")

    total_eqs = sum(
        len(obs.equivalences_for(d, min_quality=0.0))
        for d in obs.domain_names
    )
    print(f"  Equivalences:     {total_eqs} total")

    if use_entropy and entropy_result:
        print(f"  Sleep-Wake:       {entropy_result['sleep_phases']} sleep, "
              f"{entropy_result['dream_cycles']} dream cycles")

    print(f"  Key insight:      NoveltyGate prevents consensus stagnation,")
    print(f"                    Hungarian+WL discovers structural correspondences")
    print(f"                    between independently evolved domains.")
    print(f"{'=' * 64}")

    res = {
        "landscape_a": L_a,
        "landscape_b": L_b,
        "multiverse_result": result,
        "dream_observer": obs,
        "dream_results": dream_results,
        "total_equivalences": total_eqs,
    }
    if entropy_result:
        res["entropy"] = entropy_result
    return res


# ── CLI ───────────────────────────────────────────────────────────────

def main():
    use_entropy = "--entropy" in sys.argv
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return
    run_demo(use_entropy=use_entropy)


if __name__ == "__main__":
    main()
