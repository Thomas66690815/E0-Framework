"""
Historization × Gordian Trap — Stability Exploration
====================================================
Key question: Does interference-based routing survive when
R_eff changes through historization?

Scenarios:
  A) Multi-pass hybrid: controller repeatedly runs B-path (with overrides)
  B) Greedy pre-traversal: greedy runs first (takes A-short), then check ΔΘ
  C) Mixed: multiple greedy passes through A, then hybrid check
  D) Adversarial: force many A-loop traversals, then check

For each scenario, track:
  - ΔΘ(A-loop − A-short) over time
  - cos(ΔΘ) — must stay < -0.9 for good interference
  - I(A1) vs I(B1) under goal_reaching geometry
  - Whether hybrid still overrides to B1
"""
import math
import sys

from e0_controller.landscape import Landscape
from e0_controller.connection import theta, omega
from e0_controller.wavepath import psi, intensity
from e0_controller.controller import E0Controller, HybridMode
from e0_controller.primitives import Outcome, Edge
from e0_controller.amplitude_overlay import analyze_controller_state


def build_gordian_trap() -> Landscape:
    """Gordian Trap v3 (same as test_gordian_trap.py)."""
    L = Landscape()
    L.add_edge("START", "A1", delta=0.3, resistance=0.3)
    L.add_edge("A1", "A2", delta=0.4, resistance=0.3)
    L.add_edge("A2", "GOAL", delta=0.4, resistance=0.3)
    L.add_edge("A1", "L1", delta=2.0, resistance=0.05)
    L.add_edge("L1", "L2", delta=2.0, resistance=0.05)
    L.add_edge("L2", "L3", delta=2.0, resistance=0.05)
    L.add_edge("L3", "GOAL", delta=2.0, resistance=0.05)
    L.add_edge("START", "B1", delta=0.5, resistance=0.4)
    L.add_edge("B1", "B2", delta=0.3, resistance=0.35)
    L.add_edge("B2", "GOAL", delta=0.3, resistance=0.3)
    return L


def always_success(source, target):
    return Outcome.SUCCESS


A_SHORT = ["START", "A1", "A2", "GOAL"]
A_LOOP  = ["START", "A1", "L1", "L2", "L3", "GOAL"]
B_PATH  = ["START", "B1", "B2", "GOAL"]


def measure_state(L, label=""):
    """Measure all key quantities on current landscape state."""
    # v values on key edges
    v_a_short = [L.transition_field("A1", "A2"), L.transition_field("A2", "GOAL")]
    v_a_loop  = [L.transition_field("A1", "L1"), L.transition_field("L1", "L2"),
                 L.transition_field("L2", "L3"), L.transition_field("L3", "GOAL")]
    v_b = [L.transition_field("B1", "B2"), L.transition_field("B2", "GOAL")]

    # Holonomy formula
    dt_predicted = 0.5 * (sum(v_a_loop) - sum(v_a_short))

    # Actual theta
    dt_actual = theta(L, A_LOOP) - theta(L, A_SHORT)

    # Interference factor
    psi_short = psi(L, A_SHORT)
    psi_loop = psi(L, A_LOOP)
    I_coherent = abs(psi_short + psi_loop) ** 2
    I_incoherent = abs(psi_short) ** 2 + abs(psi_loop) ** 2
    factor = I_coherent / I_incoherent if I_incoherent > 0 else float('inf')

    # Born intensities
    I_A = abs(psi_short + psi_loop) ** 2
    I_B = abs(psi(L, B_PATH)) ** 2

    # R_eff values
    r_eff = {}
    for x, y in [("START","A1"),("A1","A2"),("A2","GOAL"),
                  ("A1","L1"),("L1","L2"),("L2","L3"),("L3","GOAL"),
                  ("START","B1"),("B1","B2"),("B2","GOAL")]:
        r_eff[f"{x}→{y}"] = L.effective_resistance(x, y)

    return {
        "label": label,
        "v_a_short": v_a_short,
        "v_a_loop": v_a_loop,
        "v_b": v_b,
        "dt_predicted": dt_predicted,
        "dt_actual": dt_actual,
        "cos_dt": math.cos(dt_actual),
        "factor": factor,
        "I_A": I_A,
        "I_B": I_B,
        "B_wins": I_B > I_A,
        "r_eff": r_eff,
    }


def print_state(s):
    print(f"\n{'='*60}")
    print(f"  {s['label']}")
    print(f"{'='*60}")
    print(f"  ΔΘ predicted: {s['dt_predicted']:.4f}")
    print(f"  ΔΘ actual:    {s['dt_actual']:.4f}")
    print(f"  cos(ΔΘ):      {s['cos_dt']:.4f}  {'✓ GOOD' if s['cos_dt'] < -0.9 else '⚠ WEAK' if s['cos_dt'] < -0.5 else '✗ BROKEN'}")
    print(f"  Factor:        {s['factor']:.4f}  (0=perfect cancellation)")
    print(f"  I(A):          {s['I_A']:.4f}")
    print(f"  I(B):          {s['I_B']:.4f}")
    print(f"  B wins:        {'YES' if s['B_wins'] else 'NO'}")
    print(f"  Σv(loop):      {sum(s['v_a_loop']):.4f}")
    print(f"  Σv(short):     {sum(s['v_a_short']):.4f}")

    # Show changed R_eff values
    changed = [(k, v) for k, v in s['r_eff'].items()]
    print(f"  R_eff:")
    for k, v in changed:
        print(f"    {k}: {v:.4f}")


def simulate_traversal(L, path):
    """Manually historize edges along a path with SUCCESS outcomes."""
    for i in range(len(path) - 1):
        edge = Edge(path[i], path[i + 1])
        L.historization.update(edge, Outcome.SUCCESS)


def overlay_check(L, label=""):
    """Run full overlay analysis at START with goal_reaching h=5."""
    ctrl = E0Controller(L, always_success)
    report = analyze_controller_state(
        ctrl, "START", horizon_edges=5,
        geometry="goal_reaching", goals={"GOAL"},
    )
    amp_choice = report.amplitude_choice
    for ai in report.action_infos:
        print(f"    {ai.action}: I={ai.intensity:.4f}, P={ai.probability:.3f}, paths={ai.path_count}")
    print(f"    Amplitude choice: {amp_choice}")
    return amp_choice


# ── Scenario A: Multi-pass hybrid ─────────────────────────

def scenario_A():
    print("\n" + "█"*60)
    print("  SCENARIO A: Multi-pass hybrid (B-path repeated)")
    print("█"*60)

    L = build_gordian_trap()
    s0 = measure_state(L, "Initial (pristine)")
    print_state(s0)

    for run in range(1, 6):
        simulate_traversal(L, B_PATH)
        s = measure_state(L, f"After {run}x B-path traversal")
        print_state(s)
        print(f"  Overlay:")
        overlay_check(L)


# ── Scenario B: Greedy pre-traversal (A-short) ───────────

def scenario_B():
    print("\n" + "█"*60)
    print("  SCENARIO B: Greedy pre-traversal (A-short path)")
    print("█"*60)

    L = build_gordian_trap()
    s0 = measure_state(L, "Initial (pristine)")
    print_state(s0)

    for run in range(1, 8):
        simulate_traversal(L, A_SHORT)
        s = measure_state(L, f"After {run}x A-short traversal")
        print_state(s)
        if run in [1, 3, 5, 7]:
            print(f"  Overlay:")
            overlay_check(L)


# ── Scenario C: Greedy pre-traversal (A-loop) ────────────

def scenario_C():
    print("\n" + "█"*60)
    print("  SCENARIO C: Greedy pre-traversal (A-loop path)")
    print("█"*60)

    L = build_gordian_trap()
    s0 = measure_state(L, "Initial (pristine)")
    print_state(s0)

    for run in range(1, 8):
        simulate_traversal(L, A_LOOP)
        s = measure_state(L, f"After {run}x A-loop traversal")
        print_state(s)
        if run in [1, 3, 5, 7]:
            print(f"  Overlay:")
            overlay_check(L)


# ── Scenario D: Mixed — greedy A, then check hybrid ──────

def scenario_D():
    print("\n" + "█"*60)
    print("  SCENARIO D: Mixed greedy-then-hybrid")
    print("█"*60)

    L = build_gordian_trap()
    s0 = measure_state(L, "Initial (pristine)")
    print_state(s0)

    # 3 greedy runs through A-short
    for run in range(1, 4):
        simulate_traversal(L, A_SHORT)
    s1 = measure_state(L, "After 3x A-short (greedy)")
    print_state(s1)
    print(f"  Overlay after greedy:")
    overlay_check(L)

    # Now 2 hybrid runs through B
    for run in range(1, 3):
        simulate_traversal(L, B_PATH)
    s2 = measure_state(L, "After 3x A-short + 2x B-path")
    print_state(s2)
    print(f"  Overlay after mixed:")
    overlay_check(L)


# ── Scenario E: Adversarial — many A-short to weaken ΔΘ ──

def scenario_E():
    print("\n" + "█"*60)
    print("  SCENARIO E: Adversarial — many A-short traversals")
    print("█"*60)

    L = build_gordian_trap()

    results = []
    for run in range(20):
        s = measure_state(L, f"Pass {run}")
        results.append(s)
        simulate_traversal(L, A_SHORT)

    # Summary table
    print(f"\n  {'Pass':>4} | {'ΔΘ':>8} | {'cos(ΔΘ)':>8} | {'Factor':>8} | {'I(A)':>8} | {'I(B)':>8} | {'B wins':>7}")
    print(f"  {'-'*4}-+-{'-'*8}-+-{'-'*8}-+-{'-'*8}-+-{'-'*8}-+-{'-'*8}-+-{'-'*7}")
    for s in results:
        print(f"  {s['label'].split()[-1]:>4} | {s['dt_actual']:8.4f} | {s['cos_dt']:8.4f} | {s['factor']:8.4f} | {s['I_A']:8.4f} | {s['I_B']:8.4f} | {'YES' if s['B_wins'] else 'NO':>7}")

    # At which pass does B stop winning?
    for i, s in enumerate(results):
        if not s['B_wins']:
            print(f"\n  ⚠ B stops winning at pass {i}")
            break
    else:
        print(f"\n  ✓ B wins throughout all 20 passes!")


if __name__ == "__main__":
    scenarios = {
        'A': scenario_A,
        'B': scenario_B,
        'C': scenario_C,
        'D': scenario_D,
        'E': scenario_E,
    }

    if len(sys.argv) > 1:
        for name in sys.argv[1:]:
            if name.upper() in scenarios:
                scenarios[name.upper()]()
    else:
        # Run all
        for fn in scenarios.values():
            fn()
