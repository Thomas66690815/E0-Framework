"""
Multi-Goal G5 Exploration
=========================
Extends the Gordian Trap with a second goal (GOAL2) to investigate
how goal_reaching geometry distributes amplitude across competing goals.

Landscape (Multi-Goal Gordian):

  Decoy A (destructive interference toward GOAL, coherent toward GOAL2):
    A-short:  START → A1 → A2 → GOAL       (low v → small Θ)
    A-loop:   START → A1 → L1 → L2 → L3 → GOAL  (high v → large Θ)
    A-alt:    START → A1 → D1 → GOAL2       (moderate, single coherent path)

  Detour B (coherent to GOAL):
    B-path:   START → B1 → B2 → GOAL

  Direct C (coherent to GOAL2):
    C-path:   START → C1 → C2 → GOAL2

Key questions:
  Q1: Single-goal {GOAL} — identical to original Gordian? (regression)
  Q2: Single-goal {GOAL2} — who wins between A1(→D1→GOAL2) and C1(→C2→GOAL2)?
  Q3: Multi-goal {GOAL, GOAL2} — does A1 recover from destructive interference
      because of the GOAL2 path? Or does B1+C1 dominate?
  Q4: Does the multi-goal set disturb the GOAL-specific interference?
"""
import math

from e0_controller.landscape import Landscape
from e0_controller.connection import theta
from e0_controller.wavepath import psi
from e0_controller.controller import E0Controller, HybridMode
from e0_controller.primitives import Outcome
from e0_controller.amplitude_overlay import analyze_controller_state


def build_multigoal_gordian() -> Landscape:
    """
    Multi-Goal Gordian: original trap + A-alt path to GOAL2 + C-path to GOAL2.
    """
    L = Landscape()

    # ── Original Gordian Trap edges ──
    # Decoy A (cheap greedy entry)
    L.add_edge("START", "A1", delta=0.3, resistance=0.3)

    # A-short: low δ → low v → small Θ
    L.add_edge("A1", "A2", delta=0.4, resistance=0.3)
    L.add_edge("A2", "GOAL", delta=0.4, resistance=0.3)

    # A-loop: high δ, low R → high v → large Θ
    L.add_edge("A1", "L1", delta=2.0, resistance=0.05)
    L.add_edge("L1", "L2", delta=2.0, resistance=0.05)
    L.add_edge("L2", "L3", delta=2.0, resistance=0.05)
    L.add_edge("L3", "GOAL", delta=2.0, resistance=0.05)

    # Detour B (expensive start, coherent to GOAL)
    L.add_edge("START", "B1", delta=0.5, resistance=0.4)
    L.add_edge("B1", "B2", delta=0.3, resistance=0.35)
    L.add_edge("B2", "GOAL", delta=0.3, resistance=0.3)

    # ── New Multi-Goal edges ──
    # A-alt: A1 can also reach GOAL2 (moderate path)
    L.add_edge("A1", "D1", delta=0.5, resistance=0.3)
    L.add_edge("D1", "GOAL2", delta=0.4, resistance=0.3)

    # C-path: direct route to GOAL2 (moderate-expensive)
    L.add_edge("START", "C1", delta=0.6, resistance=0.4)
    L.add_edge("C1", "C2", delta=0.4, resistance=0.3)
    L.add_edge("C2", "GOAL2", delta=0.3, resistance=0.3)

    return L


def always_success(source, target):
    return Outcome.SUCCESS


# Named paths
A_SHORT = ["START", "A1", "A2", "GOAL"]
A_LOOP  = ["START", "A1", "L1", "L2", "L3", "GOAL"]
A_ALT   = ["START", "A1", "D1", "GOAL2"]
B_PATH  = ["START", "B1", "B2", "GOAL"]
C_PATH  = ["START", "C1", "C2", "GOAL2"]


def separator(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def main():
    L = build_multigoal_gordian()
    ctrl = E0Controller(L, always_success)

    # ── Path-level analysis ──
    separator("Path-Level Ψ Values")

    for name, path in [("A-short", A_SHORT), ("A-loop", A_LOOP),
                       ("A-alt→GOAL2", A_ALT), ("B→GOAL", B_PATH),
                       ("C→GOAL2", C_PATH)]:
        p = psi(L, path)
        t = theta(L, path)
        print(f"  {name:20s}  Ψ={p:.6f}  |Ψ|²={abs(p)**2:.6f}  Θ={t:.4f}")

    # ── A-family interference ──
    separator("A-Family Interference (GOAL paths only)")
    psi_short = psi(L, A_SHORT)
    psi_loop = psi(L, A_LOOP)
    psi_A_goal = psi_short + psi_loop
    I_coherent = abs(psi_A_goal) ** 2
    I_incoherent = abs(psi_short) ** 2 + abs(psi_loop) ** 2
    factor = I_coherent / I_incoherent if I_incoherent > 0 else float('inf')
    dt = theta(L, A_LOOP) - theta(L, A_SHORT)
    print(f"  Ψ(A-short) + Ψ(A-loop) = {psi_A_goal:.6f}")
    print(f"  I_coherent   = {I_coherent:.6f}")
    print(f"  I_incoherent = {I_incoherent:.6f}")
    print(f"  factor       = {factor:.4f}  (< 0.1 = destructive)")
    print(f"  ΔΘ           = {dt:.4f}  (≈π={math.pi:.4f})")
    print(f"  cos(ΔΘ)      = {math.cos(dt):.4f}")

    # ── A1 total with GOAL2 path ──
    separator("A1 Total Amplitude (GOAL + GOAL2 paths)")
    psi_A_alt = psi(L, A_ALT)
    psi_A1_total = psi_A_goal + psi_A_alt  # all goal-reaching paths through A1
    print(f"  Ψ(A→GOAL)  = {psi_A_goal:.6f}  (destructive remnant)")
    print(f"  Ψ(A→GOAL2) = {psi_A_alt:.6f}  (single coherent path)")
    print(f"  Ψ(A1 total)= {psi_A1_total:.6f}")
    print(f"  I(A1 total) = {abs(psi_A1_total)**2:.6f}")
    print(f"  I(B1)       = {abs(psi(L, B_PATH))**2:.6f}")
    print(f"  I(C1)       = {abs(psi(L, C_PATH))**2:.6f}")

    # ── Scenario 1: Single goal {GOAL} — regression ──
    separator("Scenario 1: Single Goal {GOAL} (h=5)")
    report = analyze_controller_state(
        ctrl, "START", horizon_edges=5,
        geometry="goal_reaching", goals={"GOAL"},
    )
    for ai in report.action_infos:
        print(f"  {ai.action:4s}  I={ai.intensity:.6f}  P={ai.probability:.4f}  paths={ai.path_count}")
    print(f"  → amplitude_choice = {report.amplitude_choice}")
    print(f"  → deterministic    = {report.deterministic_choice}")

    # ── Scenario 2: Single goal {GOAL2} ──
    separator("Scenario 2: Single Goal {GOAL2} (h=5)")
    report2 = analyze_controller_state(
        ctrl, "START", horizon_edges=5,
        geometry="goal_reaching", goals={"GOAL2"},
    )
    for ai in report2.action_infos:
        print(f"  {ai.action:4s}  I={ai.intensity:.6f}  P={ai.probability:.4f}  paths={ai.path_count}")
    print(f"  → amplitude_choice = {report2.amplitude_choice}")

    # ── Scenario 3: Multi-goal {GOAL, GOAL2} ──
    separator("Scenario 3: Multi-Goal {GOAL, GOAL2} (h=5)")
    report3 = analyze_controller_state(
        ctrl, "START", horizon_edges=5,
        geometry="goal_reaching", goals={"GOAL", "GOAL2"},
    )
    for ai in report3.action_infos:
        print(f"  {ai.action:4s}  I={ai.intensity:.6f}  P={ai.probability:.4f}  paths={ai.path_count}")
    print(f"  → amplitude_choice = {report3.amplitude_choice}")

    # ── Scenario 4: Multi-goal at different horizons ──
    separator("Scenario 4: Multi-Goal at varying horizons")
    for h in [3, 4, 5, 6, 7]:
        rpt = analyze_controller_state(
            ctrl, "START", horizon_edges=h,
            geometry="goal_reaching", goals={"GOAL", "GOAL2"},
        )
        choices = {ai.action: f"P={ai.probability:.3f}" for ai in rpt.action_infos}
        print(f"  h={h}: choice={rpt.amplitude_choice}  {choices}")

    # ── Scenario 5: Hybrid run with multi-goal ──
    separator("Scenario 5: Hybrid Run (multi-goal)")
    ctrl_hybrid = E0Controller(
        L, always_success,
        hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
        hybrid_horizon=5,
        hybrid_goals={"GOAL", "GOAL2"},
        hybrid_geometry="goal_reaching",
    )
    trace = ctrl_hybrid.run(start="START", max_cycles=20)
    print(f"  Path: {' → '.join(trace.path)}")
    print(f"  Final state: {trace.path[-1]}")
    for step in trace.steps:
        ovr = "OVERRIDE" if step.hybrid_overridden else "agree"
        print(f"    {step.source} → {step.target} [{ovr}]")

    # ── Scenario 6: Which GOAL does it reach? ──
    separator("Scenario 6: Does hybrid reach GOAL or GOAL2?")
    final = trace.path[-1]
    if final in ("GOAL", "GOAL2"):
        print(f"  ✓ Reached {final}")
    else:
        print(f"  ✗ Did NOT reach a goal. Stuck at {final}")

    # ── Scenario 7: Separate hybrid runs for each goal ──
    separator("Scenario 7: Separate hybrid runs for each single goal")
    for g in ["GOAL", "GOAL2"]:
        ctrl_g = E0Controller(
            build_multigoal_gordian(), always_success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=5,
            hybrid_goals={g},
            hybrid_geometry="goal_reaching",
        )
        tr = ctrl_g.run(start="START", goal=g, max_cycles=20)
        print(f"  goal={g:6s}  path={' → '.join(tr.path)}  reached={tr.path[-1]==g}")


if __name__ == "__main__":
    main()
