"""E₀ Demo — Self-Graph: E0 Learns E0 (C147)
===============================================
Demonstrates E0's structural self-knowledge — the Self-Graph that
records which of its own components are helping or hurting decisions.

The Self-Graph is E0's first domain: 8 nodes representing E0's own
operational cycle (amplitude → born → realization → historization →
inertia → transition_field → amplitude, plus curvature and overlap
as optional modulations).

Six phases:

  Phase 1: Structure — the Self-Graph as a Landscape
  Phase 2: Mechanism — direct self_historize calls showing differential
           quality for core vs modulation components
  Phase 3: Diagnosis — Dual Reflection classifies + recommends
  Phase 4: End-to-end — controller run with Self-Graph attached
  Phase 5: Convergence — quality stabilization over 30 runs
  Phase 6: Summary — what the Self-Graph teaches us

Key insight: The Self-Graph records CORRELATION, not causation.
Components that are active during failure-heavy periods get worse
quality. This is sufficient for meta-control because the system
can deactivate harmful modulations and observe improvement.

Canon basis: Ontodynamics §1 — Selbstunterscheidung. E0's first
structural operation is distinguishing itself from itself.

Usage:
    py -3 -m e0_controller.demo_self_graph
    py -3 -m e0_controller.demo_self_graph --entropy
"""

from __future__ import annotations

import sys

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller
from e0_controller.self_graph import (
    SelfGraph, active_components, ALL_COMPONENTS,
    CORE_COMPONENTS, MODULATION_COMPONENTS,
    CORE_EDGES, MODULATION_EDGES,
)
from e0_controller.dual_reflection import (
    diagnose_self_graph,
    DualReflectionReport,
)
from e0_controller.reflexive_action import (
    apply_reflexive_actions,
)
from e0_controller.structural_entropy import structural_temperature


# ── Domain for end-to-end phase ──────────────────────────────────

def _execute_approval(source: str, target: str) -> Outcome:
    """All transitions succeed (clean domain for end-to-end test)."""
    return Outcome.SUCCESS


def build_approval_domain() -> Landscape:
    """Simple approval pipeline for end-to-end self-graph demo.

    Topology: SUBMIT → REVIEW → EVALUATE → RECOMMEND → APPROVED → DONE
    """
    L = Landscape()
    L.add_edge("SUBMIT", "REVIEW", delta=0.5, resistance=0.3)
    L.add_edge("REVIEW", "EVALUATE", delta=0.4, resistance=0.4)
    L.add_edge("EVALUATE", "RECOMMEND", delta=0.4, resistance=0.3)
    L.add_edge("RECOMMEND", "APPROVED", delta=0.3, resistance=0.3)
    L.add_edge("APPROVED", "DONE", delta=0.2, resistance=0.2)
    L.inertia_modulation = True
    return L


# ── Helpers ──────────────────────────────────────────────────────

def _print_sg_table(sg: SelfGraph) -> None:
    """Print self-graph component table."""
    diag = diagnose_self_graph(sg)
    for ca in diag.components:
        icon = {"healthy": "✓", "confused": "?", "harmful": "✗",
                "insufficient_data": "·"}.get(ca.status, " ")
        tag = " [mod]" if ca.is_modulation else ""
        print(f"     {icon} {ca.name:20s}  load={ca.load:5.1f}  "
              f"quality={ca.quality:+.3f}  "
              f"inertia={ca.inertia:.3f}  [{ca.status}]{tag}")


# ── Demo runner ──────────────────────────────────────────────────

def run_demo(use_entropy: bool = False) -> dict:
    """Run the Self-Graph demo. Returns results dict."""
    print("=" * 68)
    print("E₀ — Self-Graph Demo (C147)")
    print("     E0 Learns Its Own Components")
    if use_entropy:
        print("     + Structural Entropy")
    print("=" * 68)

    # ── Phase 1: Structure ───────────────────────────────────────
    print("\n── Phase 1: Self-Graph Structure ──")
    print(f"   Components: {len(ALL_COMPONENTS)}")
    print(f"     Core:       {CORE_COMPONENTS}")
    print(f"     Modulation: {MODULATION_COMPONENTS}")
    print(f"   Edges:      {len(CORE_EDGES)} core (cycle) "
          f"+ {len(MODULATION_EDGES)} modulation")
    print(f"   Core cycle:   amplitude → born → realization → "
          f"historization → inertia → transition_field → amplitude")
    print(f"   Modulation:   curvature → transition_field, "
          f"overlap → transition_field")
    print(f"   ρ = 1.0:      Self-knowledge is cumulative (no decay)")
    print()
    print("   Principle: after every controller step, self_historize()")
    print("   records the outcome on ALL edges where both endpoints")
    print("   are in the active component set.")
    print("   → Core edges: always traced (6 components always active)")
    print("   → Modulation edges: only traced when that modulation is ON")
    print("   This creates DIFFERENTIAL SAMPLING: components that are")
    print("   only active during bad periods accumulate worse quality.")

    # ── Phase 2: Mechanism ───────────────────────────────────────
    print("\n── Phase 2: Mechanism — Differential Quality ──")
    sg = SelfGraph()

    # Step 2a: 20 successes with core only (overlap OFF)
    print("\n   Step 2a: 20 × SUCCESS, overlap OFF")
    print("   → Core edges traced, overlap edge not.")
    core_comps = active_components(overlap_active=False)
    for _ in range(20):
        sg.self_historize(core_comps, Outcome.SUCCESS)
    _print_sg_table(sg)

    # Step 2b: 10 failures with core + overlap (overlap ON)
    print("\n   Step 2b: 10 × FAILURE, overlap ON")
    print("   → Core + overlap edges traced. Core diluted, overlap pure F.")
    overlap_comps = active_components(overlap_active=True)
    for _ in range(10):
        sg.self_historize(overlap_comps, Outcome.FAILURE)
    _print_sg_table(sg)

    # Step 2c: 10 more successes with core only (overlap OFF)
    print("\n   Step 2c: 10 × SUCCESS, overlap OFF")
    print("   → Core quality recovers, overlap quality unchanged.")
    for _ in range(10):
        sg.self_historize(core_comps, Outcome.SUCCESS)
    _print_sg_table(sg)

    # ── Phase 3: Diagnosis ───────────────────────────────────────
    print("\n── Phase 3: Dual Reflection Diagnosis ──")
    diag = diagnose_self_graph(sg)
    print(f"   Healthy:       {diag.healthy or '—'}")
    print(f"   Confused:      {diag.confused or '—'}")
    print(f"   Harmful:       {diag.harmful or '—'}")
    print(f"   Insufficient:  {diag.insufficient_data or '—'}")
    if diag.deactivation_candidates:
        print(f"   Deactivate:    {diag.deactivation_candidates}")
    if diag.meta_actions:
        print("   Meta-actions:")
        for a in diag.meta_actions:
            print(f"     ► {a}")

    # Show the key insight
    mech_core_q = sg.component_quality("amplitude")
    mech_overlap_q = sg.component_quality("overlap")
    print(f"\n   Core quality:     {mech_core_q:+.3f}  "
          f"(30 U + 10 F = quality {mech_core_q:+.3f})")
    print(f"   Overlap quality:  {mech_overlap_q:+.3f}  "
          f"(0 U + 10 F = quality {mech_overlap_q:+.3f})")
    print(f"   Why? Overlap was only active during the failure phase.")
    print(f"   The Self-Graph sees correlation → recommends deactivation.")

    # Apply deactivation
    has_deactivation = len(diag.deactivation_candidates) > 0
    if has_deactivation:
        L_demo = build_approval_domain()
        L_demo.overlap_modulation = True  # currently ON
        report = DualReflectionReport(
            domain_report=None,
            self_diagnosis=diag,
            meta_actions=list(diag.meta_actions),
        )
        action_result = apply_reflexive_actions(report, L_demo)
        if action_result.any_changes:
            print(f"\n   Reflexive action:")
            print(f"     {action_result.summary()}")
            print(f"     Overlap: ON → OFF (reversible)")

    # ── Phase 4: End-to-end ──────────────────────────────────────
    print(f"\n── Phase 4: End-to-End — Controller with Self-Graph ──")
    sg_e2e = SelfGraph()
    L_e2e = build_approval_domain()
    L_e2e.overlap_modulation = True
    if use_entropy:
        T_s = structural_temperature(L_e2e)
        print(f"   T_s:          {T_s:.4f}")

    print(f"   Running 10 controller cycles (overlap ON, all succeed)...")
    for i in range(10):
        ctrl = E0Controller(L_e2e, _execute_approval, alpha=2.0, recent_k=3)
        ctrl.self_graph = sg_e2e
        trace = ctrl.run("SUBMIT", max_cycles=20, goal="DONE")
        if i == 0:
            print(f"   Sample path:  {' → '.join(trace.path)}")

    _print_sg_table(sg_e2e)

    snap = sg_e2e.snapshot()
    print(f"\n   Key observation:")
    print(f"     All components healthy (all outcomes = SUCCESS)")
    print(f"     Core load:    {snap['amplitude']['load']:.0f}  "
          f"(10 runs × 5 steps = 50 traces per edge)")
    print(f"     Overlap load: {snap['overlap']['load']:.0f}  "
          f"(same — overlap was active in all runs)")
    print(f"     Quality:      {snap['amplitude']['quality']:+.3f}  "
          f"(all +1.0 — no failures)")
    print(f"\n   If failures had occurred, overlap would accumulate")
    print(f"   worse quality unless it also had a pre-existing positive")
    print(f"   base (as shown in Phase 2).")

    # ── Phase 5: Convergence ─────────────────────────────────────
    print("\n── Phase 5: Convergence Analysis ──")
    sg_conv = SelfGraph()
    L_conv = build_approval_domain()
    history = []
    for i in range(30):
        ctrl = E0Controller(L_conv, _execute_approval, alpha=2.0, recent_k=3)
        ctrl.self_graph = sg_conv
        ctrl.run("SUBMIT", max_cycles=20, goal="DONE")
        snap = sg_conv.snapshot()
        core_q = sum(snap[c]["quality"] for c in CORE_COMPONENTS) / len(CORE_COMPONENTS)
        core_load = sum(snap[c]["load"] for c in CORE_COMPONENTS) / len(CORE_COMPONENTS)
        core_inertia = sum(snap[c]["inertia"] for c in CORE_COMPONENTS) / len(CORE_COMPONENTS)
        history.append({
            "run": i + 1, "core_q": core_q,
            "core_load": core_load, "core_inertia": core_inertia,
        })

    print(f"   30 runs (all succeed, overlap OFF):")
    print(f"   {'Run':>4s}  {'Core Quality':>13s}  {'Core Load':>10s}  "
          f"{'Core Inertia':>13s}")
    for h in history:
        if h["run"] <= 3 or h["run"] >= 28 or h["run"] == 15:
            print(f"   {h['run']:4d}  {h['core_q']:+13.6f}  "
                  f"{h['core_load']:10.2f}  {h['core_inertia']:13.6f}")
        elif h["run"] == 4:
            print(f"   {'...':>4s}")

    q_final = history[-1]["core_q"]
    print(f"\n   Converges to quality {q_final:+.4f} immediately (all-success domain)")
    print(f"   Inertia stays at 1.000 (|q|=1.0 → no dampening)")

    # ── Phase 6: Summary ─────────────────────────────────────────
    print("\n── Phase 6: Summary ──")
    print(f"   Three levels of self-knowledge (Architecture §6):")
    print(f"     Level 1 — Structure:   8-node graph of own operational cycle")
    print(f"     Level 2 — Operational: self_historize() attributes outcomes")
    print(f"                            to active components per cycle")
    print(f"     Level 3 — Meta-control: diagnose_self_graph() classifies")
    print(f"                             components → deactivation of harmful")
    print(f"                             modulations (reversible)")
    print()
    print(f"   Key property: DIFFERENTIAL SAMPLING")
    print(f"     Core components are always active → quality averages all periods")
    print(f"     Modulation components toggle → quality reflects only ON periods")
    print(f"     If overlap is ON only during failures → overlap gets blamed")
    print(f"     This is correlation, not causation — but sufficient for")
    print(f"     meta-control because deactivation is reversible.")
    print()

    overlap_harmful = "overlap" in diag.harmful
    print("=" * 68)
    if overlap_harmful:
        print(f"Phase 2 demonstrated: overlap harmful ({mech_overlap_q:+.3f}), "
              f"core healthy ({mech_core_q:+.3f})")
        print("Phase 3 prescribed: deactivate overlap modulation")
    print(f"Convergence: quality {q_final:+.4f} in all-success domain")
    print("Canon: Selbstunterscheidung — E0's first domain is E0.")
    print("=" * 68)

    return {
        "diag": diag,
        "overlap_harmful": overlap_harmful,
        "core_quality": mech_core_q,
        "overlap_quality": mech_overlap_q,
        "has_deactivation": has_deactivation,
        "convergence": history,
        "sg_mechanism": sg,
        "sg_e2e": sg_e2e,
    }


# ── CLI ──────────────────────────────────────────────────────────

def main():
    use_entropy = "--entropy" in sys.argv
    run_demo(use_entropy=use_entropy)


if __name__ == "__main__":
    main()
