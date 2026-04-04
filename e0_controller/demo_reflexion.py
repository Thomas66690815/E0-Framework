"""E₀ Demo — Reflexion: Reactive vs. Proactive vs. Integrated (C144)
====================================================================
Demonstrates the three reflexion modes on a domain with structural
gaps (frontiers where the goal is unreachable without new edges):

  Phase 1: Build a domain with dead-ends and a hidden forward path
  Phase 2: Standard controller — stagnates, never reaches goal
  Phase 3: Reactive reflexion (C56) — proposes after 8 stagnation cycles
  Phase 4: Proactive reflexion (C57) — proposes at first frontier arrival
  Phase 5: Integrated reflexion (C59) — proactive + SelfGraph diagnosis
  Phase 6: Comparison table

Key insight: "Reflexion ist kein Spezialfall — sie ist der Normalfall
für alles Neue." Proactive reflexion proposes BEFORE the controller
gets stuck, not after.

Usage:
    py -3 -m e0_controller.demo_reflexion
    py -3 -m e0_controller.demo_reflexion --entropy
"""

from __future__ import annotations

import copy
import sys

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller, RunTrace
from e0_controller.evaluation import evaluate_run
from e0_controller.reflexive_edge_proposal import (
    ProposedEdge,
    run_with_reflexion,
    run_with_proactive_reflexion,
    is_frontier,
)
from e0_controller.integrated_reflexion import (
    run_with_integrated_reflexion,
    IntegratedReflexionResult,
)
from e0_controller.reflexive_action import ReflexiveJournal
from e0_controller.structural_entropy import structural_temperature
from e0_controller.sleep_wake import SleepWakeCycle
from e0_controller.dream_mode import DreamObserver


# ── Domain: "Research Pipeline" with structural gaps ─────────────

def _execute_research(source: str, target: str) -> Outcome:
    """Execution function with one unreliable edge."""
    # The shortcut DRAFT→REVIEW sometimes fails (reviewer rejects)
    if source == "DRAFT" and target == "REVIEW":
        return Outcome.FAILURE
    return Outcome.SUCCESS


def build_research_domain() -> Landscape:
    """Build a research pipeline domain with structural gaps.

    Topology:
        START → COLLECT → ANALYZE → DRAFT → (gap) → REVIEW → PUBLISH
                                  ↘ NOTES → COLLECT  (dead-end loop)

    The gap between DRAFT and REVIEW forces reflexion to propose
    a hypothesis edge.  Without reflexion, the controller loops
    in the DRAFT → NOTES → COLLECT → ANALYZE → DRAFT cycle.

    A second gap hides a shortcut: ANALYZE → REVIEW (direct).
    Proactive reflexion discovers this; reactive may not.
    """
    L = Landscape()

    # Forward path (connected up to DRAFT)
    L.add_edge("START", "COLLECT", delta=0.5, resistance=0.3)
    L.add_edge("COLLECT", "ANALYZE", delta=0.4, resistance=0.4)
    L.add_edge("ANALYZE", "DRAFT", delta=0.3, resistance=0.5)

    # Dead-end loop from DRAFT
    L.add_edge("DRAFT", "NOTES", delta=0.2, resistance=0.3)
    L.add_edge("NOTES", "COLLECT", delta=0.3, resistance=0.4)

    # ── GAP ──  No edge DRAFT→REVIEW exists.
    # Reflexion must propose it.

    # Post-gap path (isolated from START side)
    L.add_edge("REVIEW", "PUBLISH", delta=0.2, resistance=0.3)

    # Also no edge ANALYZE→REVIEW — a second gap for proactive
    # reflexion to potentially discover.

    return L


# ── Phase runners ────────────────────────────────────────────────

MAX_CYCLES = 40


def _run_standard(L: Landscape) -> dict:
    """Phase 2: Standard controller, no reflexion."""
    ctrl = E0Controller(L, _execute_research, alpha=2.0, recent_k=3)
    trace = ctrl.run("START", max_cycles=MAX_CYCLES, goal="PUBLISH")
    reached = "PUBLISH" in trace.path
    return {
        "trace": trace,
        "reached": reached,
        "steps": len(trace.steps),
        "proposals": 0,
    }


def _run_reactive(L: Landscape) -> dict:
    """Phase 3: Reactive reflexion (C56)."""
    trace, proposals = run_with_reflexion(
        L, _execute_research, "START", "PUBLISH",
        max_cycles=MAX_CYCLES,
        proposal_trigger=8,
        stuckness_window=8,
    )
    reached = "PUBLISH" in trace.path
    return {
        "trace": trace,
        "reached": reached,
        "steps": len(trace.steps),
        "proposals": len(proposals),
        "proposal_list": proposals,
    }


def _run_proactive(L: Landscape) -> dict:
    """Phase 4: Proactive reflexion (C57)."""
    trace, proposals = run_with_proactive_reflexion(
        L, _execute_research, "START", "PUBLISH",
        max_cycles=MAX_CYCLES,
    )
    reached = "PUBLISH" in trace.path
    return {
        "trace": trace,
        "reached": reached,
        "steps": len(trace.steps),
        "proposals": len(proposals),
        "proposal_list": proposals,
    }


def _run_integrated(L: Landscape) -> dict:
    """Phase 5: Integrated reflexion (C59)."""
    trace, result, journal = run_with_integrated_reflexion(
        L, _execute_research, "START", "PUBLISH",
        max_cycles=MAX_CYCLES,
        diagnosis_interval=10,
    )
    reached = "PUBLISH" in trace.path
    return {
        "trace": trace,
        "reached": reached,
        "steps": len(trace.steps),
        "proposals": len(result.edge_proposals),
        "proposal_list": result.edge_proposals,
        "flags_changed": result.flags_changed,
        "scopes": result.scopes,
        "journal": journal,
        "integrated_result": result,
    }


# ── Demo runner ──────────────────────────────────────────────────

def run_demo(use_entropy: bool = False) -> dict:
    """Run the reflexion demo. Returns results dict."""
    print("=" * 64)
    print("E₀ — Reflexion Demo (C144)")
    print("     Reactive vs. Proactive vs. Integrated")
    if use_entropy:
        print("     + Structural Entropy / Sleep-Wake")
    print("=" * 64)

    # ── Phase 1: Domain ──────────────────────────────────────────
    print("\n── Phase 1: Research Pipeline Domain ──")
    L_base = build_research_domain()
    print(f"   States:    {sorted(L_base.states)}")
    print(f"   Edges:     {L_base.edge_count()}")
    print(f"   Start:     START")
    print(f"   Goal:      PUBLISH")
    print(f"   Gaps:      DRAFT→REVIEW (missing), ANALYZE→REVIEW (missing)")
    print(f"   Dead-end:  DRAFT→NOTES→COLLECT (loop)")
    frontier = is_frontier(L_base, "START", "PUBLISH")
    print(f"   Frontier:  {'yes' if frontier else 'no'} (PUBLISH unreachable from START)")

    # ── Phase 2: Standard ────────────────────────────────────────
    print("\n── Phase 2: Standard Controller (no reflexion) ──")
    L2 = build_research_domain()
    r_std = _run_standard(L2)
    print(f"   Reached:   {'✓' if r_std['reached'] else '✗ FAILED'}")
    print(f"   Steps:     {r_std['steps']}/{MAX_CYCLES}")
    if not r_std["reached"]:
        path_short = r_std["trace"].path[:10]
        if len(r_std["trace"].path) > 10:
            path_short.append("...")
        print(f"   Path:      {' → '.join(path_short)}")
        print(f"   Diagnosis: Controller loops — no path to PUBLISH exists")

    # ── Phase 3: Reactive ────────────────────────────────────────
    print("\n── Phase 3: Reactive Reflexion (C56) ──")
    L3 = build_research_domain()
    r_react = _run_reactive(L3)
    print(f"   Reached:   {'✓' if r_react['reached'] else '✗ FAILED'}")
    print(f"   Steps:     {r_react['steps']}/{MAX_CYCLES}")
    print(f"   Proposals: {r_react['proposals']}")
    for p in r_react.get("proposal_list", []):
        print(f"     → {p.source}→{p.target}  "
              f"(Δ={p.delta:.2f}, R₀={p.resistance:.2f}, "
              f"conf={p.confidence:.2f})")
    if r_react["reached"]:
        print(f"   Diagnosis: Waited {min(8, r_react['steps'])} cycles "
              f"before proposing (stuckness detection)")
    else:
        print(f"   Diagnosis: Stuckness window may not trigger "
              f"if cycling pattern is too varied")

    # ── Phase 4: Proactive ───────────────────────────────────────
    print("\n── Phase 4: Proactive Reflexion (C57) ──")
    L4 = build_research_domain()
    r_pro = _run_proactive(L4)
    print(f"   Reached:   {'✓' if r_pro['reached'] else '✗ FAILED'}")
    print(f"   Steps:     {r_pro['steps']}/{MAX_CYCLES}")
    print(f"   Proposals: {r_pro['proposals']}")
    for p in r_pro.get("proposal_list", []):
        print(f"     → {p.source}→{p.target}  "
              f"(Δ={p.delta:.2f}, R₀={p.resistance:.2f}, "
              f"conf={p.confidence:.2f})")
    if r_pro["reached"]:
        print(f"   Diagnosis: Proposed at first frontier — no stagnation needed")

    # ── Phase 5: Integrated ──────────────────────────────────────
    print("\n── Phase 5: Integrated Reflexion (C59) ──")
    L5 = build_research_domain()
    r_int = _run_integrated(L5)
    print(f"   Reached:   {'✓' if r_int['reached'] else '✗ FAILED'}")
    print(f"   Steps:     {r_int['steps']}/{MAX_CYCLES}")
    print(f"   Proposals: {r_int['proposals']}")
    for p in r_int.get("proposal_list", []):
        print(f"     → {p.source}→{p.target}  "
              f"(Δ={p.delta:.2f}, R₀={p.resistance:.2f}, "
              f"conf={p.confidence:.2f})")
    print(f"   Flags:     {'changed' if r_int['flags_changed'] else 'unchanged'}")
    if r_int.get("journal"):
        j = r_int["journal"]
        print(f"   Journal:   {j.total_actions} actions, "
              f"{j.active_count} active")

    # ── Phase 6 (optional): Sleep-Wake ───────────────────────────
    entropy_result = None
    if use_entropy and r_int["reached"]:
        print("\n── Phase 6: Sleep-Wake on Integrated Landscape ──")
        L_ent = L5  # reuse the integrated landscape (already has proposals)
        T_s = structural_temperature(L_ent.historization)
        print(f"   Initial T_s: {T_s:.3f}")

        obs = DreamObserver(
            readiness_threshold=0.0,
            decay_enabled=True,
            theta_base=0.5,
            protected_fn=lambda domain: {"START", "PUBLISH"},
        )
        obs.register("research", L_ent)

        ctrl_ent = E0Controller(
            L_ent, _execute_research, inscription_threshold=True,
        )
        swc = SleepWakeCycle(obs, mu=5.0, max_dream_cycles=3)
        swc.register("research", ctrl_ent, "START", "PUBLISH")

        episodes = swc.run(n_episodes=3, max_cycles_per_run=15)

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

        pr = swc.pressure_report()
        entropy_result = {
            "episodes": len(episodes),
            "sleep_phases": sleep_count,
            "dream_cycles": dream_count,
            "pressure_report": pr,
        }

    # ── Comparison ───────────────────────────────────────────────
    print(f"\n{'=' * 64}")
    print("Comparison")
    print(f"{'=' * 64}")
    print(f"  {'Mode':<20} {'Goal?':>6} {'Steps':>6} {'Proposals':>10}")
    print(f"  {'-'*20} {'-'*6} {'-'*6} {'-'*10}")

    rows = [
        ("Standard", r_std),
        ("Reactive (C56)", r_react),
        ("Proactive (C57)", r_pro),
        ("Integrated (C59)", r_int),
    ]
    for name, r in rows:
        ok = "✓" if r["reached"] else "✗"
        print(f"  {name:<20} {ok:>6} {r['steps']:>6} {r['proposals']:>10}")

    print()
    print(f"  Key insight: Proactive reflexion proposes at the FIRST frontier")
    print(f"  arrival — the controller never stagnates.  Reactive reflexion")
    print(f"  waits for stuckness, which may come too late or not at all.")
    print(f"{'=' * 64}")

    res = {
        "domain_edges": L_base.edge_count(),
        "domain_states": len(L_base.states),
        "standard": r_std,
        "reactive": r_react,
        "proactive": r_pro,
        "integrated": r_int,
    }
    if entropy_result:
        res["entropy"] = entropy_result
    return res


# ── CLI ───────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    use_entropy = "--entropy" in args

    if "--help" in args or "-h" in args:
        print(__doc__)
        return

    run_demo(use_entropy=use_entropy)


if __name__ == "__main__":
    main()
