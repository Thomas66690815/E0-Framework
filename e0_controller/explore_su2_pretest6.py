"""
Pretest 6: Minimum graph complexity for SU(2) ranking relevance.

Sweeps node count from 3 to 10 and edge density from 30% to 80%.
For each (node_count, density) pair: generate 500 random asymmetric
topologies, measure SU(2) and Geometric reversal rates vs U(1).

Goal: find the activation threshold — the minimum graph size where
SU(2) perspective produces operationally different rankings.
"""

import math
import random
from collections import defaultdict
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller
from e0_controller.primitives import Outcome
from e0_controller.amplitude_overlay import analyze_controller_state

exec_fn = lambda s, t: Outcome.SUCCESS
rng = random.Random(42)

NODE_LABELS = list("SABCDEFGHIJ")
TRIALS_PER_CELL = 500
NODE_COUNTS = [3, 4, 5, 6, 7, 8, 9, 10]
DENSITIES = [0.3, 0.5, 0.7]
HORIZON = 3


def make_random_landscape(n_nodes, density):
    """Random asymmetric directed graph with log-uniform weights."""
    L = Landscape()
    nodes = NODE_LABELS[:n_nodes]
    for i, x in enumerate(nodes):
        for j, y in enumerate(nodes):
            if i != j and rng.random() < density:
                d = 10 ** rng.uniform(-2, 2)
                r = 10 ** rng.uniform(-2, 2)
                L.add_edge(x, y, delta=d, resistance=r)
    return L, nodes[0]


def check_reversal(L, start):
    """Returns (valid, su2_reversed, geo_reversed, near_degenerate, su2_rev_degen, geo_rev_degen)."""
    adm = L.admissible_neighbors(start)
    if len(adm) < 2:
        return False, False, False, False, False, False

    ctrl = E0Controller(L, exec_fn)
    try:
        r_u1 = analyze_controller_state(ctrl, start, horizon_edges=HORIZON, use_su2=False)
        r_su2 = analyze_controller_state(ctrl, start, horizon_edges=HORIZON, use_su2=True)
        r_geo = analyze_controller_state(ctrl, start, horizon_edges=HORIZON, use_su2="geometric")
    except Exception:
        return False, False, False, False, False, False

    order_u1 = [a.action for a in r_u1.action_infos]
    order_su2 = [a.action for a in r_su2.action_infos]
    order_geo = [a.action for a in r_geo.action_infos]

    su2_rev = order_u1 != order_su2
    geo_rev = order_u1 != order_geo

    # Check near-degeneracy
    near_degen = False
    su2_rev_d = False
    geo_rev_d = False
    if len(r_u1.action_infos) >= 2:
        i1 = r_u1.action_infos[0].intensity
        i2 = r_u1.action_infos[1].intensity
        if i1 > 0 and i2 / i1 > 0.8:
            near_degen = True
            su2_rev_d = su2_rev
            geo_rev_d = geo_rev

    return True, su2_rev, geo_rev, near_degen, su2_rev_d, geo_rev_d


# ─── Main sweep ───

print(f"{'Nodes':>5} {'Dens':>5} {'Valid':>6} {'SU2%':>7} {'Geo%':>7} "
      f"{'Degen':>6} {'SU2d%':>7} {'Geod%':>7}")
print("-" * 62)

results = {}

for n_nodes in NODE_COUNTS:
    for density in DENSITIES:
        valid = 0
        su2_rev = 0
        geo_rev = 0
        degen = 0
        su2_rev_d = 0
        geo_rev_d = 0

        for _ in range(TRIALS_PER_CELL):
            L, start = make_random_landscape(n_nodes, density)
            v, sr, gr, nd, srd, grd = check_reversal(L, start)
            if v:
                valid += 1
                su2_rev += sr
                geo_rev += gr
                if nd:
                    degen += 1
                    su2_rev_d += srd
                    geo_rev_d += grd

        su2_pct = 100 * su2_rev / valid if valid else 0
        geo_pct = 100 * geo_rev / valid if valid else 0
        su2d_pct = 100 * su2_rev_d / degen if degen else 0
        geod_pct = 100 * geo_rev_d / degen if degen else 0

        results[(n_nodes, density)] = {
            "valid": valid, "su2_pct": su2_pct, "geo_pct": geo_pct,
            "degen": degen, "su2d_pct": su2d_pct, "geod_pct": geod_pct,
        }

        print(f"{n_nodes:>5} {density:>5.1f} {valid:>6} {su2_pct:>6.1f}% {geo_pct:>6.1f}% "
              f"{degen:>6} {su2d_pct:>6.1f}% {geod_pct:>6.1f}%")

# ─── Summary ───

print()
print("=" * 62)
print("SUMMARY: SU(2) reversal rate by node count (averaged over densities)")
print("=" * 62)

for n in NODE_COUNTS:
    cells = [results[(n, d)] for d in DENSITIES if results[(n, d)]["valid"] > 0]
    if not cells:
        continue
    total_valid = sum(c["valid"] for c in cells)
    avg_su2 = sum(c["su2_pct"] * c["valid"] for c in cells) / total_valid
    avg_geo = sum(c["geo_pct"] * c["valid"] for c in cells) / total_valid
    total_degen = sum(c["degen"] for c in cells)
    avg_su2d = sum(c["su2d_pct"] * c["degen"] for c in cells) / total_degen if total_degen else 0
    avg_geod = sum(c["geod_pct"] * c["degen"] for c in cells) / total_degen if total_degen else 0
    bar_su2 = "█" * int(avg_su2 * 2)
    bar_degen = "█" * int(avg_su2d)
    print(f"  {n:>2} nodes: SU2={avg_su2:5.1f}% {bar_su2:<30s}  "
          f"Degen: {avg_su2d:5.1f}% {bar_degen}")

# ─── Threshold detection ───
print()
print("THRESHOLD ANALYSIS:")
for n in NODE_COUNTS:
    cells = [results[(n, d)] for d in DENSITIES if results[(n, d)]["valid"] > 0]
    if not cells:
        continue
    total_valid = sum(c["valid"] for c in cells)
    total_su2 = sum(c["su2_pct"] * c["valid"] / 100 for c in cells)
    rate = total_su2 / total_valid if total_valid else 0
    if rate > 0.001:
        print(f"  First non-trivial SU(2) effect at {n} nodes (rate={rate*100:.2f}%)")
        break
else:
    print("  No SU(2) effect detected in tested range")

for n in NODE_COUNTS:
    cells = [results[(n, d)] for d in DENSITIES if results[(n, d)]["valid"] > 0]
    if not cells:
        continue
    total_valid = sum(c["valid"] for c in cells)
    total_su2 = sum(c["su2_pct"] * c["valid"] / 100 for c in cells)
    rate = total_su2 / total_valid if total_valid else 0
    if rate > 0.05:
        print(f"  SU(2) operationally significant (>5%) at {n} nodes (rate={rate*100:.2f}%)")
        break

# Self-Graph relevance
print()
print("SELF-GRAPH RELEVANCE:")
print("  Self-Graph has 8 component nodes (6 core + 2 modulation)")
print("  with ~20 edges (dense connectivity)")
sg_cells = [results[(n, d)] for n in [7, 8, 9, 10] for d in DENSITIES 
            if (n, d) in results and results[(n, d)]["valid"] > 0]
if sg_cells:
    total = sum(c["valid"] for c in sg_cells)
    avg = sum(c["su2_pct"] * c["valid"] for c in sg_cells) / total
    print(f"  Avg SU(2) reversal rate at 7-10 nodes: {avg:.1f}%")
    total_d = sum(c["degen"] for c in sg_cells)
    avg_d = sum(c["su2d_pct"] * c["degen"] for c in sg_cells) / total_d if total_d else 0
    print(f"  Avg SU(2) reversal rate at 7-10 nodes (near-degenerate): {avg_d:.1f}%")
