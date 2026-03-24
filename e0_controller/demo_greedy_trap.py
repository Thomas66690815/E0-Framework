"""
E₀ Walkthrough Demo — Greedy Trap vs Hybrid Correction
========================================================
Executable version of the README walkthrough example.

Scenario:
    A → C → A   (loop / trap — low local cost)
    A → B → E → G → GOAL   (forward path — slightly higher first step)

In GREEDY mode the controller picks A→C (cheapest), gets trapped in a loop,
and hits max_steps without reaching GOAL.

In AMPLITUDE_ON_DISAGREE mode the amplitude layer evaluates path families,
detects that A→B leads to GOAL while A→C cycles, and overrides the greedy
choice.  The controller reaches GOAL in 4 steps.

Usage:
    python -m e0_controller.demo_greedy_trap
"""

from __future__ import annotations

import sys

from .controller import E0Controller, HybridMode, RunTrace
from .landscape import Landscape
from .primitives import Outcome


def build_trap_landscape() -> Landscape:
    """
    Build the greedy-trap landscape from the README walkthrough.

    Structure:
        A → C  (Δ=1.0, R=0.3)  — cheap, but C only goes back to A
        C → A  (Δ=1.0, R=0.3)  — completes the loop
        A → B  (Δ=1.0, R=0.8)  — more expensive first step, but leads forward
        B → E  (Δ=1.0, R=0.5)
        E → G  (Δ=1.0, R=0.5)
        G → GOAL (Δ=1.0, R=0.3)
    """
    L = Landscape()
    # Trap loop: A ↔ C (low cost)
    L.add_edge("A", "C", delta=1.0, resistance=0.3)
    L.add_edge("C", "A", delta=1.0, resistance=0.3)
    # Forward path: A → B → E → G → GOAL (first step costlier)
    L.add_edge("A", "B", delta=1.0, resistance=0.8)
    L.add_edge("B", "E", delta=1.0, resistance=0.5)
    L.add_edge("E", "G", delta=1.0, resistance=0.5)
    L.add_edge("G", "GOAL", delta=1.0, resistance=0.3)
    return L


def always_success(source: str, target: str) -> Outcome:
    """Simple execute function — every transition succeeds."""
    return Outcome.SUCCESS


def run_demo() -> None:
    max_cycles = 10

    # --- GREEDY run ---
    print("=" * 60)
    print("E₀ Walkthrough: Greedy Trap vs Hybrid Correction")
    print("=" * 60)
    print()
    print("Landscape:")
    print("  A → C → A   (loop, low cost: S=0.30)")
    print("  A → B → E → G → GOAL   (forward, first step S=0.80)")
    print()

    L_greedy = build_trap_landscape()
    ctrl_greedy = E0Controller(
        landscape=L_greedy,
        execute_fn=always_success,
        hybrid_mode=HybridMode.GREEDY,
        alpha=0.5,      # moderate revisit penalty
        recent_k=2,     # short memory so trap persists longer
    )
    trace_greedy = ctrl_greedy.run("A", goal="GOAL", max_cycles=max_cycles)

    greedy_reached = trace_greedy.path[-1] == "GOAL" if trace_greedy.path else False

    print(f"[GREEDY]  mode = pure local burden minimization")
    print(f"  Path:    {' → '.join(trace_greedy.path)}")
    print(f"  Steps:   {len(trace_greedy.steps)}")
    print(f"  Reached GOAL: {'YES' if greedy_reached else 'NO — trapped in loop'}")
    print()

    # --- HYBRID run ---
    L_hybrid = build_trap_landscape()
    ctrl_hybrid = E0Controller(
        landscape=L_hybrid,
        execute_fn=always_success,
        hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
        hybrid_horizon=4,
        hybrid_goals={"GOAL"},
        alpha=0.5,
        recent_k=2,
    )
    trace_hybrid = ctrl_hybrid.run("A", goal="GOAL", max_cycles=max_cycles)

    hybrid_reached = trace_hybrid.path[-1] == "GOAL" if trace_hybrid.path else False
    overrides = sum(1 for s in trace_hybrid.steps if s.hybrid_overridden)

    print(f"[HYBRID]  mode = AMPLITUDE_ON_DISAGREE (horizon=4)")
    print(f"  Path:    {' → '.join(trace_hybrid.path)}")
    print(f"  Steps:   {len(trace_hybrid.steps)}")
    print(f"  Reached GOAL: {'YES' if hybrid_reached else 'NO'}")
    print(f"  Amplitude overrides: {overrides}")
    print()

    # --- Overlay detail for first step ---
    if trace_hybrid.steps and trace_hybrid.steps[0].overlay:
        ov = trace_hybrid.steps[0].overlay
        det = ov.deterministic_choice
        amp = ov.amplitude_choice
        # Find intensity for amplitude choice
        amp_info = next((a for a in ov.action_infos if a.action == amp), None)
        det_info = next((a for a in ov.action_infos if a.action == det), None)
        print("Step 1 amplitude overlay detail:")
        if det_info:
            print(f"  Greedy choice:    {det}  (S_eff={det_info.direct_s_eff:.2f})")
        else:
            print(f"  Greedy choice:    {det}")
        if amp_info:
            print(f"  Amplitude choice: {amp}  (intensity={amp_info.intensity:.4f})")
        else:
            print(f"  Amplitude choice: {amp}")
        agree = det == amp
        print(f"  Agreement:        {'AGREE' if agree else 'DISAGREE'}")
        if trace_hybrid.steps[0].hybrid_overridden:
            print(f"  → Controller followed amplitude (override)")
        print()

    # --- Summary ---
    print("-" * 60)
    print("Summary")
    print("-" * 60)
    if not greedy_reached and hybrid_reached:
        print("  Greedy got trapped in the A↔C loop.")
        print("  Hybrid detected stronger forward support through B")
        print("  and reached GOAL in fewer steps.")
        print()
        print("  This is the core E₀ hybrid capability:")
        print("  decisions are evaluated both locally (burden)")
        print("  and globally (coherent future support),")
        print("  and resolved when they disagree.")
    elif greedy_reached and hybrid_reached:
        g_steps = len(trace_greedy.steps)
        h_steps = len(trace_hybrid.steps)
        print(f"  Both reached GOAL (greedy: {g_steps} steps, hybrid: {h_steps} steps).")
        if h_steps < g_steps:
            print("  Hybrid was more efficient.")
    print()


if __name__ == "__main__":
    run_demo()
