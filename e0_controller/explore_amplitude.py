"""
E₀ Controller — Amplitude Overlay Exploration
==============================================
Runs the amplitude overlay on the mini-domain at every decision point
along a full controller run, showing:
  - deterministic choice vs amplitude choice
  - per-action intensity I, probability P, path count
  - whether interference effects are visible

Usage:
    python e0_controller/explore_amplitude.py
"""

from __future__ import annotations
import sys, os, cmath
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from e0_controller.primitives import Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller
from e0_controller.amplitude_overlay import analyze_controller_state
from e0_controller.wavepath import psi as path_psi


# ── Mini-Domain Builder (same as test_minidomain) ──

def build_mini_landscape() -> Landscape:
    L = Landscape()
    L.add_edge("A", "B", delta=0.5, resistance=1.0)
    L.add_edge("A", "C", delta=0.4, resistance=0.8)
    L.add_edge("C", "A", delta=0.4, resistance=0.8)
    L.add_edge("C", "D", delta=0.7, resistance=3.0)
    L.add_edge("B", "E", delta=0.3, resistance=0.8)
    L.add_edge("B", "D", delta=0.6, resistance=1.5)
    L.add_state("D")
    L.add_edge("E", "F", delta=0.4, resistance=1.2)
    L.add_edge("E", "G", delta=0.2, resistance=0.5)
    L.add_edge("F", "G", delta=0.3, resistance=1.0)
    L.add_edge("G", "GOAL", delta=0.1, resistance=0.3)
    return L


def all_success(source: str, target: str) -> Outcome:
    return Outcome.SUCCESS


def failure_on_EF(source: str, target: str) -> Outcome:
    if source == "E" and target == "F":
        return Outcome.FAILURE
    return Outcome.SUCCESS


def sep(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ── Scenario 1: Fresh landscape, all success ──

def scenario_fresh():
    sep("Scenario 1: Fresh landscape, all_success")
    L = build_mini_landscape()
    ctrl = E0Controller(L, all_success, alpha=2.0, recent_k=3)

    print("\nAmplitude overlay at every state (horizon=3):\n")
    for state in ["A", "B", "C", "E", "F", "G"]:
        neighbors = ctrl._admissible_neighbors(state)
        if not neighbors:
            print(f"  {state}: no admissible neighbors (dead-end or goal sink)\n")
            continue
        report = analyze_controller_state(ctrl, state, horizon_edges=3)
        print(report.summary())
        match = "✓ AGREE" if report.deterministic_choice == report.amplitude_choice else "✗ DISAGREE"
        print(f"  → {match}")
        print()


# ── Scenario 2: Walk with overlay at each step ──

def scenario_walk_with_overlay():
    sep("Scenario 2: Full walk A→GOAL with overlay at each step")
    L = build_mini_landscape()
    ctrl = E0Controller(L, all_success, alpha=2.0, recent_k=3)

    current = "A"
    step = 0
    visited = []

    while current != "GOAL" and step < 15:
        step += 1
        neighbors = ctrl._admissible_neighbors(current)
        if not neighbors:
            print(f"  Step {step}: {current} → STUCK (no neighbors)")
            break

        report = analyze_controller_state(ctrl, current, horizon_edges=3)

        # Execute the deterministic cycle
        result = ctrl.cycle(current)
        if result is None:
            print(f"  Step {step}: {current} → STUCK (cycle returned None)")
            break
        next_state = result.target
        visited.append(current)

        match = "✓" if report.deterministic_choice == report.amplitude_choice else "✗"
        print(f"  Step {step}: {current} → {next_state}  "
              f"[det={report.deterministic_choice}, amp={report.amplitude_choice}] {match}")

        # Show probabilities
        for info in report.action_infos:
            marker = "←" if info.action == next_state else "  "
            print(f"      {info.action}: P={info.probability:.4f}, "
                  f"I={info.intensity:.6f}, paths={info.path_count} {marker}")

        current = next_state

    print(f"\n  Path: {' → '.join(visited + [current])}")


# ── Scenario 3: After learning (failure on E→F) ──

def scenario_post_learning():
    sep("Scenario 3: After E→F failures, overlay comparison")
    L = build_mini_landscape()
    ctrl = E0Controller(L, failure_on_EF, alpha=2.0, recent_k=3)

    # Run a few steps to trigger learning on E→F
    trace = ctrl.run("A", goal="GOAL", max_cycles=20)
    print(f"  Run completed in {len(trace.steps)} steps: {trace.path}")
    print(f"  Escalations: {sum(1 for s in trace.steps if s.escalated)}")

    # Now examine E with learned resistances
    print(f"\n  After learning, overlay at E (horizon=3):")
    report = analyze_controller_state(ctrl, "E", horizon_edges=3)
    print(report.summary())
    match = "✓ AGREE" if report.deterministic_choice == report.amplitude_choice else "✗ DISAGREE"
    print(f"  → {match}")


# ── Scenario 4: Horizon sensitivity ──

def scenario_horizon_sensitivity():
    sep("Scenario 4: Horizon sensitivity at state A")
    L = build_mini_landscape()
    ctrl = E0Controller(L, all_success, alpha=2.0, recent_k=3)

    for h in [1, 2, 3, 4]:
        report = analyze_controller_state(ctrl, "A", horizon_edges=h)
        print(f"\n  Horizon h={h}:")
        for info in report.action_infos:
            print(f"    {info.action}: P={info.probability:.4f}, "
                  f"I={info.intensity:.6f}, Ψ={info.psi_total:.6f}, "
                  f"paths={info.path_count}")
        match = "✓" if report.deterministic_choice == report.amplitude_choice else "✗"
        print(f"    det={report.deterministic_choice}, amp={report.amplitude_choice} {match}")


# ── Scenario 5: Interference check ──

def scenario_interference():
    sep("Scenario 5: Interference at G (two paths converge)")
    print("  G receives flow from E→G (direct) and E→F→G (via F)")
    print("  If Θ differs, we should see constructive/destructive interference\n")

    L = build_mini_landscape()
    ctrl = E0Controller(L, all_success, alpha=2.0, recent_k=3)

    # Check at E with horizon 2 — paths [E,G] and [E,F,G] both end at G
    report = analyze_controller_state(ctrl, "E", horizon_edges=2)
    print(report.summary())

    print("\n  Detailed Ψ per action:")
    for info in report.action_infos:
        print(f"    {info.action}: Ψ = {info.psi_total}")
        print(f"      |Ψ| = {abs(info.psi_total):.6f}")
        for p in info.paths:
            pv = path_psi(L, p)
            print(f"      path {'→'.join(p)}: Ψ={pv:.6f}, |Ψ|={abs(pv):.6f}")


# ══════════════════════════════════════════════
# Diamond Domain Scenarios (interference-rich)
# ══════════════════════════════════════════════

from e0_controller.test_amplitude_overlay import build_diamond_landscape
from e0_controller.connection import omega, theta


def scenario_diamond_overview():
    sep("Scenario 6: Diamond Domain — Overview at every state")
    L = build_diamond_landscape()
    ctrl = E0Controller(L, all_success, alpha=2.0, recent_k=3)

    print("\n  Domain: S→{A,B,C}, A→M→Z, B→N→Z, M→N cross-link")
    print("  Back-edges: A→S (heavy), B→S (medium)")
    print("  C = dead-end trap (greedy picks it)\n")

    for state in ["S", "A", "B", "M", "N"]:
        neighbors = ctrl._admissible_neighbors(state)
        if not neighbors:
            continue
        report = analyze_controller_state(ctrl, state, horizon_edges=3)
        print(report.summary())
        match = "✓ AGREE" if report.deterministic_choice == report.amplitude_choice else "✗ DISAGREE"
        print(f"  → {match}")
        print()

    # Show the phase structure
    print("  Phase analysis:")
    theta_upper = theta(L, ["S", "A", "M", "Z"])
    theta_lower = theta(L, ["S", "B", "N", "Z"])
    theta_cross = theta(L, ["S", "A", "M", "N", "Z"])
    print(f"    Θ(S→A→M→Z)   = {theta_upper:.6f}")
    print(f"    Θ(S→B→N→Z)   = {theta_lower:.6f}")
    print(f"    Θ(S→A→M→N→Z) = {theta_cross:.6f}")
    print(f"    ΔΘ(upper-lower) = {theta_upper - theta_lower:.6f}")
    print()
    print("  Connection values:")
    for x, y in [("S","A"), ("S","B"), ("S","C"), ("A","M"), ("B","N"), ("M","Z"), ("N","Z"), ("M","N")]:
        w = omega(L, x, y)
        print(f"    ω({x},{y}) = {w:+.6f}")


def scenario_diamond_walk():
    sep("Scenario 7: Diamond Domain — Full walk S→Z")
    L = build_diamond_landscape()
    ctrl = E0Controller(L, all_success, alpha=2.0, recent_k=3)

    current = "S"
    step = 0
    visited = []

    while current != "Z" and step < 15:
        step += 1
        neighbors = ctrl._admissible_neighbors(current)
        if not neighbors:
            print(f"  Step {step}: {current} → STUCK")
            break

        report = analyze_controller_state(ctrl, current, horizon_edges=3)
        result = ctrl.cycle(current)
        if result is None:
            print(f"  Step {step}: {current} → STUCK (cycle returned None)")
            break
        next_state = result.target
        visited.append(current)

        match = "✓" if report.deterministic_choice == report.amplitude_choice else "✗"
        print(f"  Step {step}: {current} → {next_state}  "
              f"[det={report.deterministic_choice}, amp={report.amplitude_choice}] {match}")
        for info in report.action_infos:
            marker = "←" if info.action == next_state else "  "
            print(f"      {info.action}: P={info.probability:.4f}, "
                  f"I={info.intensity:.6f}, paths={info.path_count} {marker}")

        current = next_state

    print(f"\n  Path: {' → '.join(visited + [current])}")


def scenario_diamond_interference_detail():
    sep("Scenario 8: Diamond Domain — Interference detail at S")
    L = build_diamond_landscape()
    ctrl = E0Controller(L, all_success, alpha=2.0, recent_k=3)

    print("\n  Comparing coherent vs incoherent intensity per action:")
    print("  Coherent:   I = |Σ Ψ(p)|²        (phases matter)")
    print("  Incoherent: I = Σ |Ψ(p)|²        (phases ignored)\n")

    for h in [2, 3]:
        report = analyze_controller_state(ctrl, "S", horizon_edges=h)
        print(f"  Horizon h={h}:")
        for info in report.action_infos:
            coherent = info.intensity
            incoherent = sum(abs(path_psi(L, p)) ** 2 for p in info.paths)
            diff = coherent - incoherent
            kind = "constructive" if diff > 1e-10 else ("destructive" if diff < -1e-10 else "none")
            print(f"    {info.action}: coherent={coherent:.6f}, incoherent={incoherent:.6f}, "
                  f"Δ={diff:+.6f} ({kind}), paths={info.path_count}")

            # Show individual path Ψ
            for p in info.paths:
                pv = path_psi(L, p)
                print(f"       {'→'.join(p)}: Ψ={pv:.6f}, |Ψ|²={abs(pv)**2:.6f}, "
                      f"arg={cmath.phase(pv):.4f} rad")
        print()


# ══════════════════════════════════════════════
# Current-Loop Domain (destructive interference)
# ══════════════════════════════════════════════

from e0_controller.test_amplitude_overlay import build_current_loop_landscape


def scenario_current_loop_overview():
    sep("Scenario 9: Current-Loop Domain — Destructive Interference")
    L = build_current_loop_landscape()
    ctrl = E0Controller(L, all_success, alpha=2.0, recent_k=3)

    print("\n  Domain: START→A1→A2→A3→A4→END (upper, 5 hops)")
    print("          START→B1→END (lower, 2 hops)")
    print("          Strong back-edges: A4→A3→A2→A1→START + END→A4")
    print("          (creates large unidirectional circulation)\n")

    print("  Phase analysis:")
    theta_upper = theta(L, ["START","A1","A2","A3","A4","END"])
    theta_lower = theta(L, ["START","B1","END"])
    print(f"    Θ(upper) = {theta_upper:.6f}")
    print(f"    Θ(lower) = {theta_lower:.6f}")
    print(f"    ΔΘ       = {theta_upper - theta_lower:.6f}")
    print(f"    cos(ΔΘ)  = {__import__('math').cos(theta_upper - theta_lower):.6f}")

    psi_u = path_psi(L, ["START","A1","A2","A3","A4","END"])
    psi_l = path_psi(L, ["START","B1","END"])
    coherent = abs(psi_u + psi_l) ** 2
    incoherent = abs(psi_u)**2 + abs(psi_l)**2

    print(f"\n  Two-path interference at END:")
    print(f"    Ψ(upper): |Ψ|={abs(psi_u):.6f}, arg={cmath.phase(psi_u):.4f}")
    print(f"    Ψ(lower): |Ψ|={abs(psi_l):.6f}, arg={cmath.phase(psi_l):.4f}")
    print(f"    Incoherent Σ|Ψ|² = {incoherent:.6f}")
    print(f"    Coherent |Σ Ψ|²  = {coherent:.6f}")
    diff = coherent - incoherent
    print(f"    Δ = {diff:+.6f} → {'DESTRUCTIVE' if diff < -1e-10 else 'constructive'}")
    print(f"    Ratio coherent/incoherent = {coherent/incoherent:.2%}")


def scenario_current_loop_overlay():
    sep("Scenario 10: Current-Loop — Overlay at START (varying horizon)")
    L = build_current_loop_landscape()
    ctrl = E0Controller(L, all_success, alpha=2.0, recent_k=3)

    for h in [1, 2, 3, 5]:
        report = analyze_controller_state(ctrl, "START", horizon_edges=h)
        print(f"\n  Horizon h={h}:")
        for info in report.action_infos:
            coherent = info.intensity
            incoherent = sum(abs(path_psi(L, p))**2 for p in info.paths)
            diff = coherent - incoherent
            kind = "DESTR" if diff < -1e-10 else ("constr" if diff > 1e-10 else "none")
            print(f"    {info.action}: P={info.probability:.4f}, "
                  f"coh={coherent:.6f}, incoh={incoherent:.6f}, "
                  f"Δ={diff:+.6f} ({kind}), paths={info.path_count}")
        match = "✓" if report.deterministic_choice == report.amplitude_choice else "✗"
        print(f"    det={report.deterministic_choice}, amp={report.amplitude_choice} {match}")


if __name__ == "__main__":
    scenario_fresh()
    scenario_walk_with_overlay()
    scenario_post_learning()
    scenario_horizon_sensitivity()
    scenario_interference()
    scenario_diamond_overview()
    scenario_diamond_walk()
    scenario_diamond_interference_detail()
    scenario_current_loop_overview()
    scenario_current_loop_overlay()
    print(f"\n{'='*60}")
    print("  Exploration complete.")
    print(f"{'='*60}")
