"""Pretest 2: Extreme delta contrast — designed to maximize SU(2) divergence."""

import numpy as np
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller
from e0_controller.primitives import Outcome, Edge
from e0_controller.amplitude_overlay import analyze_controller_state
from e0_controller.spinor_connection import (
    compare_u1_su2, compare_minimal_geometric,
    spinor_psi, spinor_intensity, su2_holonomy, omega,
)
from e0_controller.wavepath import intensity as u1_intensity

exec_fn = lambda s, t: Outcome.SUCCESS


def show_overlay(name, L, start, horizon=4):
    ctrl = E0Controller(L, exec_fn)
    print(f"=== {name} ===")
    print(f"  Admissible from {start}: {L.admissible_neighbors(start)}")
    for mode_name, use_su2 in [
        ("U(1)", False),
        ("SU(2) minimal", True),
        ("SU(2) geometric", "geometric"),
    ]:
        report = analyze_controller_state(
            ctrl, start, horizon_edges=horizon, use_su2=use_su2
        )
        ranking = [
            (a.action, round(a.intensity, 6), round(a.probability, 4))
            for a in report.action_infos
        ]
        print(f"  {mode_name:18s}: {ranking}")

    orders = {}
    for mode_name, use_su2 in [("U(1)", False), ("SU(2) minimal", True), ("SU(2) geometric", "geometric")]:
        report = analyze_controller_state(ctrl, start, horizon_edges=horizon, use_su2=use_su2)
        orders[mode_name] = [a.action for a in report.action_infos]
    if all(o == list(orders.values())[0] for o in orders.values()):
        print("  --> IDENTICAL rankings")
    else:
        print("  --> DIFFERENT rankings!")
    print()


# ─── Test 1: Extreme delta contrast ───
L1 = Landscape()
L1.add_edge("S", "A", delta=0.1, resistance=0.5)
L1.add_edge("A", "G", delta=0.1, resistance=0.5)
L1.add_edge("S", "B", delta=5.0, resistance=0.3)
L1.add_edge("B", "C", delta=5.0, resistance=0.3)
L1.add_edge("C", "G", delta=5.0, resistance=0.3)
L1.add_edge("S", "G", delta=3.0, resistance=1.0)
L1.add_edge("G", "S", delta=1.0, resistance=1.0)

show_overlay("Test 1: Extreme delta contrast", L1, "S")

# Raw path comparison
print("Per-path inspection (Test 1):")
for name, paths in [
    ("via A", [["S", "A", "G"]]),
    ("via B", [["S", "B", "C", "G"]]),
    ("direct", [["S", "G"]]),
]:
    u1_I = u1_intensity(L1, paths)
    su2_I = spinor_intensity(L1, paths)
    print(f"  {name:8s}: U(1)={u1_I:.6f}  SU(2)={su2_I:.6f}  ratio={su2_I / max(u1_I, 1e-30):.4f}")

all_paths = [["S", "A", "G"], ["S", "B", "C", "G"], ["S", "G"]]
result = compare_u1_su2(L1, all_paths)
print(f"  Combined: U(1)={result['u1_intensity']:.6f}  SU(2)={result['su2_intensity']:.6f}  dev={result['deviation_pct']:.2f}%")
result2 = compare_minimal_geometric(L1, all_paths)
print(f"  Minimal={result2['minimal_intensity']:.6f}  Geometric={result2['geometric_intensity']:.6f}  geo_vs_min={result2['geo_vs_min_pct']:.2f}%")
print()


# ─── Test 2: Understand omega ───
print("Phase angles (omega) on key edges:")
for s, t in [("S", "A"), ("A", "G"), ("S", "B"), ("B", "C"), ("C", "G"), ("S", "G")]:
    w = omega(L1, s, t)
    print(f"  omega({s}->{t}) = {w:.4f}")
print()


# ─── Test 3: Triangle with high vorticity ───
# Vorticity = omega(A,B) + omega(B,C) + omega(C,A) mod 2pi
# High vorticity => face holonomy => geometric SU(2) differs from minimal
L3 = Landscape()
L3.add_edge("S", "A", delta=1.0, resistance=0.5)
L3.add_edge("S", "B", delta=2.0, resistance=0.5)
L3.add_edge("A", "B", delta=3.0, resistance=0.5)
L3.add_edge("B", "A", delta=0.5, resistance=0.5)
L3.add_edge("A", "S", delta=1.0, resistance=0.5)
L3.add_edge("B", "S", delta=1.0, resistance=0.5)

show_overlay("Test 3: Triangle with high vorticity", L3, "S", horizon=3)

# Holonomy of cycle S->A->B->S
try:
    H = su2_holonomy(L3, ["S", "A", "B", "S"])
    print(f"  Holonomy S->A->B->S:")
    print(f"  {H}")
    w_total = np.arccos(min(1.0, max(-1.0, abs(np.trace(H)) / 2)))
    print(f"  Holonomy angle: {w_total:.4f} rad ({np.degrees(w_total):.1f} deg)")
except Exception as e:
    print(f"  Holonomy error: {e}")
print()


# ─── Test 4: With custom axis_fn — perspective rotation ───
print("=== Test 4: Custom axis_fn (perspective rotation) ===")
L4 = Landscape()
for s in ("S", "A", "B", "C"):
    for t in ("S", "A", "B", "C"):
        if s != t:
            L4.add_edge(s, t, delta=0.5 + 0.3 * abs(ord(s) - ord(t)), resistance=1.0)

ctrl4 = E0Controller(L4, exec_fn)

import math


def axis_z(L, x, y):
    return np.array([0, 0, 1.0])


def axis_x(L, x, y):
    return np.array([1.0, 0, 0])


def axis_y(L, x, y):
    return np.array([0, 1.0, 0])


def axis_mixed(L, x, y):
    w = omega(L, x, y)
    return np.array([math.cos(w), math.sin(w), 0]) if abs(w) > 1e-10 else np.array([0, 0, 1.0])


for ax_name, ax_fn in [("axis_z", axis_z), ("axis_x", axis_x), ("axis_y", axis_y), ("axis_mixed", axis_mixed)]:
    report = analyze_controller_state(
        ctrl4, "S", horizon_edges=3, use_su2=True, axis_fn=ax_fn
    )
    ranking = [(a.action, round(a.intensity, 6), round(a.probability, 4)) for a in report.action_infos]
    order = [a.action for a in report.action_infos]
    print(f"  {ax_name:12s}: {ranking}  order={order}")

# Also U(1) baseline
report_u1 = analyze_controller_state(ctrl4, "S", horizon_edges=3, use_su2=False)
ranking_u1 = [(a.action, round(a.intensity, 6), round(a.probability, 4)) for a in report_u1.action_infos]
print(f"  {'U(1)':12s}: {ranking_u1}  order={[a.action for a in report_u1.action_infos]}")
print()


# ─── Test 5: Near-degenerate landscape (intentionally close intensities) ───
print("=== Test 5: Near-degenerate intensities ===")
L5 = Landscape()
L5.add_edge("S", "A", delta=1.00, resistance=1.0)
L5.add_edge("S", "B", delta=1.01, resistance=1.0)
L5.add_edge("A", "C", delta=1.0, resistance=1.0)
L5.add_edge("B", "C", delta=1.0, resistance=1.0)
L5.add_edge("C", "S", delta=1.0, resistance=1.0)
L5.add_edge("A", "B", delta=2.0, resistance=1.0)
L5.add_edge("B", "A", delta=0.5, resistance=1.0)

for mode_name, use_su2 in [("U(1)", False), ("SU(2) minimal", True), ("SU(2) geometric", "geometric")]:
    ctrl5 = E0Controller(L5, exec_fn)
    report = analyze_controller_state(ctrl5, "S", horizon_edges=3, use_su2=use_su2)
    ranking = [(a.action, round(a.intensity, 8), round(a.probability, 6)) for a in report.action_infos]
    print(f"  {mode_name:18s}: {ranking}")

print()
print("=" * 60)
print("KEY QUESTION: Do any topologies show ranking differences?")
print("If axis_fn changes produce different orders, perspective")
print("rotation has operational effect.")
