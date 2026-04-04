"""Pretest 4: Does 87-degree omega produce different SU(2) rankings?"""

import math
import numpy as np
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller
from e0_controller.primitives import Outcome
from e0_controller.amplitude_overlay import analyze_controller_state
from e0_controller.connection import omega
from e0_controller.spinor_connection import su2_holonomy

exec_fn = lambda s, t: Outcome.SUCCESS


def show(name, L, start, horizon=3):
    ctrl = E0Controller(L, exec_fn)
    print(f"=== {name} ===")
    print(f"  Admissible: {L.admissible_neighbors(start)}")
    print(f"  Omega magnitudes:")
    for e in L.edges:
        w = omega(L, e.source, e.target)
        if abs(w) > 0.01:
            print(f"    {e.source}->{e.target}: {math.degrees(w):+.1f} deg")

    results = {}
    for mode_name, use_su2 in [("U(1)", False), ("SU(2)", True), ("Geometric", "geometric")]:
        report = analyze_controller_state(ctrl, start, horizon_edges=horizon, use_su2=use_su2)
        ranking = [(a.action, round(a.intensity, 6), round(a.probability, 4)) for a in report.action_infos]
        order = [a.action for a in report.action_infos]
        results[mode_name] = order
        print(f"  {mode_name:12s}: {ranking}")

    if all(o == list(results.values())[0] for o in results.values()):
        print("  --> IDENTICAL rankings")
    else:
        print("  --> *** DIFFERENT RANKINGS DETECTED ***")
        for n1, o1 in results.items():
            for n2, o2 in results.items():
                if n1 < n2 and o1 != o2:
                    print(f"      {n1} = {o1}  vs  {n2} = {o2}")
    print()


# ─── High-omega topology: extreme directional asymmetry ───
# S→A: huge forward flow, tiny backward
# S→B: tiny forward, huge backward
# This creates omega ~ 87 deg per edge = ~174 deg for 2-edge path

L1 = Landscape()
L1.add_edge("S", "A", delta=10.0, resistance=0.1)
L1.add_edge("A", "S", delta=0.01, resistance=10.0)
L1.add_edge("S", "B", delta=0.01, resistance=10.0)
L1.add_edge("B", "S", delta=10.0, resistance=0.1)
L1.add_edge("A", "B", delta=5.0, resistance=0.2)
L1.add_edge("B", "A", delta=0.1, resistance=5.0)

show("High-omega triangle (87 deg edges)", L1, "S", horizon=3)


# ─── Even more extreme: push omega toward 180 deg ───
L2 = Landscape()
L2.add_edge("S", "A", delta=50.0, resistance=0.01)
L2.add_edge("A", "S", delta=0.001, resistance=100.0)
L2.add_edge("S", "B", delta=0.001, resistance=100.0)
L2.add_edge("B", "S", delta=50.0, resistance=0.01)
L2.add_edge("A", "B", delta=25.0, resistance=0.02)
L2.add_edge("B", "A", delta=0.01, resistance=50.0)
L2.add_edge("A", "G", delta=1.0, resistance=1.0)
L2.add_edge("B", "G", delta=1.0, resistance=1.0)
L2.add_edge("G", "S", delta=1.0, resistance=1.0)

print("Omega on extreme L2:")
for e in L2.edges:
    w = omega(L2, e.source, e.target)
    if abs(w) > 0.01:
        print(f"  {e.source}->{e.target}: {math.degrees(w):+.1f} deg")
print()
show("Extreme-omega with goal node (4 nodes)", L2, "S", horizon=4)


# ─── Custom axis_fn on high-omega topology ───
print("=== axis_fn comparison on high-omega L1 ===")
ctrl = E0Controller(L1, exec_fn)

for ax_name, ax_fn in [
    ("z-axis", lambda L, x, y: np.array([0, 0, 1.0])),
    ("x-axis", lambda L, x, y: np.array([1.0, 0, 0])),
    ("y-axis", lambda L, x, y: np.array([0, 1.0, 0])),
    ("xy-diag", lambda L, x, y: np.array([1, 1, 0]) / math.sqrt(2)),
]:
    report = analyze_controller_state(ctrl, "S", horizon_edges=3, use_su2=True, axis_fn=ax_fn)
    ranking = [(a.action, round(a.intensity, 6), round(a.probability, 4)) for a in report.action_infos]
    order = [a.action for a in report.action_infos]
    print(f"  {ax_name:10s}: {ranking}  order={order}")

# U(1) baseline
report_u1 = analyze_controller_state(ctrl, "S", horizon_edges=3, use_su2=False)
ranking_u1 = [(a.action, round(a.intensity, 6), round(a.probability, 4)) for a in report_u1.action_infos]
print(f"  {'U(1)':10s}: {ranking_u1}  order={[a.action for a in report_u1.action_infos]}")

# Holonomy check
try:
    H = su2_holonomy(L1, ["S", "A", "B", "S"])
    angle = 2 * np.arccos(min(1.0, max(-1.0, abs(np.trace(H)) / 2)))
    print(f"\n  Holonomy S->A->B->S: angle={math.degrees(angle):.1f} deg")
    H2 = su2_holonomy(L2, ["S", "A", "B", "S"])
    angle2 = 2 * np.arccos(min(1.0, max(-1.0, abs(np.trace(H2)) / 2)))
    print(f"  Holonomy S->A->B->S (extreme): angle={math.degrees(angle2):.1f} deg")
except Exception as ex:
    print(f"  Holonomy error: {ex}")
