"""Empirical pretest: Does SU(2) produce different action rankings than U(1)?"""

import numpy as np
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller
from e0_controller.primitives import Outcome
from e0_controller.amplitude_overlay import analyze_controller_state

exec_fn = lambda s, t: Outcome.SUCCESS


def test_topology(name, L, start, horizon=3):
    ctrl = E0Controller(L, exec_fn)
    print(f"=== {name} ===")
    neighbors = L.admissible_neighbors(start)
    print(f"  From {start}, admissible: {neighbors}")

    results = {}
    for mode_name, use_su2 in [("U(1)", False), ("SU(2) minimal", True), ("SU(2) geometric", "geometric")]:
        report = analyze_controller_state(ctrl, start, horizon_edges=horizon, use_su2=use_su2)
        ranking = [(a.action, round(a.intensity, 6), round(a.probability, 4)) for a in report.action_infos]
        order = [a.action for a in report.action_infos]
        results[mode_name] = order
        print(f"  {mode_name:18s}: {ranking}")

    # Check if rankings differ
    orders = list(results.values())
    if all(o == orders[0] for o in orders):
        print("  --> IDENTICAL rankings across all regimes")
    else:
        print("  --> DIFFERENT rankings detected!")
        for i, (n1, o1) in enumerate(results.items()):
            for n2, o2 in list(results.items())[i+1:]:
                if o1 != o2:
                    print(f"      {n1} vs {n2}: {o1} vs {o2}")
    print()


# ── Topology 1: Fully connected 4-node with varied deltas ──
L1 = Landscape()
for s in ("S", "A", "B", "C"):
    for t in ("S", "A", "B", "C"):
        if s != t:
            L1.add_edge(s, t, delta=float(hash((s, t)) % 7 + 1) / 3, resistance=1.0)

test_topology("Topology 1: Fully connected 4-node (varied deltas)", L1, "S")


# ── Topology 2: Diamond with asymmetric deltas ──
L2 = Landscape()
L2.add_edge("S", "A", delta=2.0, resistance=1.0)
L2.add_edge("S", "B", delta=1.0, resistance=1.0)
L2.add_edge("A", "G", delta=3.0, resistance=0.5)
L2.add_edge("B", "G", delta=0.5, resistance=2.0)
L2.add_edge("A", "B", delta=1.5, resistance=1.0)
L2.add_edge("B", "A", delta=1.5, resistance=1.0)
L2.add_edge("G", "S", delta=1.0, resistance=1.0)

test_topology("Topology 2: Diamond (S->A/B->G, asymmetric)", L2, "S")


# ── Topology 3: 6-node ring with shortcuts ──
L3 = Landscape()
nodes = ["S", "A", "B", "C", "D", "E"]
for i in range(6):
    L3.add_edge(nodes[i], nodes[(i + 1) % 6], delta=1.0 + 0.3 * i, resistance=1.0)
    L3.add_edge(nodes[i], nodes[(i + 2) % 6], delta=2.0 - 0.2 * i, resistance=1.5)

test_topology("Topology 3: 6-node ring with shortcuts", L3, "S")


# ── Topology 4: Historized landscape (some edges have U/F history) ──
L4 = Landscape()
for s in ("S", "A", "B", "C"):
    for t in ("S", "A", "B", "C"):
        if s != t:
            L4.add_edge(s, t, delta=1.5, resistance=1.0)

# Build history: S->A succeeds, S->B fails
from e0_controller.primitives import Edge
for _ in range(5):
    L4.historization.update(Edge("S", "A"), Outcome.SUCCESS)
    L4.historization.update(Edge("S", "B"), Outcome.FAILURE)
    L4.historization.update(Edge("A", "C"), Outcome.SUCCESS)
    L4.historization.update(Edge("B", "C"), Outcome.FAILURE)

test_topology("Topology 4: Historized 4-node (differential S->A vs S->B)", L4, "S")


# ── Topology 5: Larger graph (8 nodes, varied structure) ──
L5 = Landscape()
import math
nodes5 = [f"N{i}" for i in range(8)]
for i in range(8):
    for j in range(8):
        if i != j and (abs(i - j) <= 2 or abs(i - j) >= 6):
            d = 1.0 + 0.5 * math.sin(i * j)
            r = 0.5 + 0.5 * abs(math.cos(i + j))
            L5.add_edge(nodes5[i], nodes5[j], delta=d, resistance=r)

test_topology("Topology 5: 8-node graph (trig-derived weights)", L5, "N0", horizon=3)


# ── Summary ──
print("=" * 60)
print("CONCLUSION: Check which topologies show different rankings.")
print("If none differ, SU(2) is inert on these landscapes.")
