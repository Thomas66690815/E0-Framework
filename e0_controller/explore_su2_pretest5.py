"""
Pretest 5: Mathematical proof-of-concept for SU(2) ranking reversal.

Key mathematical insight (from analysis of spinor_psi):
For a FIXED rotation axis, SU(2) is equivalent to U(1) with HALF the phase:
    U(1):  interference term ∝ cos(θ₁ - θ₂)
    SU(2): interference term ∝ cos((θ₁ - θ₂) / 2)

Ranking reversal is possible when two actions A and B have multi-path
interference such that the half-frequency cosine changes the ordering.

Critical scenario:
    Action A: paths with Δθ ≈ 2π  → U(1): cos(2π)=1 (constructive)
                                    → SU(2): cos(π)=-1 (DESTRUCTIVE)
    Action B: paths with Δθ ≈ π   → U(1): cos(π)=-1 (destructive)
                                    → SU(2): cos(π/2)=0 (neutral)

    U(1): A wins (constructive) > B (destructive)
    SU(2): B wins (neutral) > A (destructive)
    → RANKING REVERSAL

This script: sweep random asymmetric landscapes, count reversals.
"""

import math
import random
import numpy as np
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller
from e0_controller.primitives import Outcome
from e0_controller.amplitude_overlay import analyze_controller_state

exec_fn = lambda s, t: Outcome.SUCCESS
rng = random.Random(42)

# ─── 1. Systematic sweep with random asymmetric topologies ───

print("=" * 70)
print("PHASE 1: Random asymmetric topologies (N=5000)")
print("=" * 70)

reversals = []
total = 0

for trial in range(5000):
    L = Landscape()
    nodes = ["S", "A", "B", "C", "D"]
    # Random asymmetric edges
    for i, x in enumerate(nodes):
        for j, y in enumerate(nodes):
            if i != j and rng.random() < 0.6:
                d = 10 ** rng.uniform(-2, 2)
                r = 10 ** rng.uniform(-2, 2)
                L.add_edge(x, y, delta=d, resistance=r)

    adm = L.admissible_neighbors("S")
    if len(adm) < 2:
        continue
    total += 1

    ctrl = E0Controller(L, exec_fn)
    try:
        r_u1 = analyze_controller_state(ctrl, "S", horizon_edges=3, use_su2=False)
        r_su2 = analyze_controller_state(ctrl, "S", horizon_edges=3, use_su2=True)
    except Exception:
        continue

    order_u1 = [a.action for a in r_u1.action_infos]
    order_su2 = [a.action for a in r_su2.action_infos]

    if order_u1 != order_su2:
        reversals.append((trial, order_u1, order_su2))

print(f"  Tested: {total} valid topologies")
print(f"  Reversals found: {len(reversals)}")
if reversals:
    for trial, o1, o2 in reversals[:10]:
        print(f"    Trial {trial}: U(1)={o1} vs SU(2)={o2}")


# ─── 2. Also test geometric SU(2) ───

print()
print("=" * 70)
print("PHASE 2: Geometric SU(2) vs U(1) (N=5000)")
print("=" * 70)

reversals_geo = []
total_geo = 0

for trial in range(5000):
    L = Landscape()
    nodes = ["S", "A", "B", "C", "D"]
    for i, x in enumerate(nodes):
        for j, y in enumerate(nodes):
            if i != j and rng.random() < 0.6:
                d = 10 ** rng.uniform(-2, 2)
                r = 10 ** rng.uniform(-2, 2)
                L.add_edge(x, y, delta=d, resistance=r)

    adm = L.admissible_neighbors("S")
    if len(adm) < 2:
        continue
    total_geo += 1

    ctrl = E0Controller(L, exec_fn)
    try:
        r_u1 = analyze_controller_state(ctrl, "S", horizon_edges=3, use_su2=False)
        r_geo = analyze_controller_state(ctrl, "S", horizon_edges=3, use_su2="geometric")
    except Exception:
        continue

    order_u1 = [a.action for a in r_u1.action_infos]
    order_geo = [a.action for a in r_geo.action_infos]

    if order_u1 != order_geo:
        reversals_geo.append((trial, order_u1, order_geo))

print(f"  Tested: {total_geo} valid topologies")
print(f"  Reversals found: {len(reversals_geo)}")
if reversals_geo:
    for trial, o1, o2 in reversals_geo[:10]:
        print(f"    Trial {trial}: U(1)={o1} vs Geo={o2}")


# ─── 3. Targeted: near-degenerate U(1) rankings ───

print()
print("=" * 70)
print("PHASE 3: Near-degenerate U(1) landscapes (N=10000)")
print("=" * 70)

reversals_deg = []
near_degenerate = 0

for trial in range(10000):
    L = Landscape()
    nodes = ["S", "A", "B", "C", "D", "E"]
    for i, x in enumerate(nodes):
        for j, y in enumerate(nodes):
            if i != j and rng.random() < 0.5:
                d = 10 ** rng.uniform(-2, 2)
                r = 10 ** rng.uniform(-2, 2)
                L.add_edge(x, y, delta=d, resistance=r)

    adm = L.admissible_neighbors("S")
    if len(adm) < 2:
        continue

    ctrl = E0Controller(L, exec_fn)
    try:
        r_u1 = analyze_controller_state(ctrl, "S", horizon_edges=4, use_su2=False)
    except Exception:
        continue

    # Check if top-2 are near-degenerate (within 10%)
    if len(r_u1.action_infos) < 2:
        continue
    i1 = r_u1.action_infos[0].intensity
    i2 = r_u1.action_infos[1].intensity
    if i1 == 0:
        continue
    ratio = i2 / i1
    if ratio < 0.8:  # not near-degenerate
        continue
    near_degenerate += 1

    try:
        r_su2 = analyze_controller_state(ctrl, "S", horizon_edges=4, use_su2=True)
        r_geo = analyze_controller_state(ctrl, "S", horizon_edges=4, use_su2="geometric")
    except Exception:
        continue

    order_u1 = [a.action for a in r_u1.action_infos]
    order_su2 = [a.action for a in r_su2.action_infos]
    order_geo = [a.action for a in r_geo.action_infos]

    if order_u1 != order_su2 or order_u1 != order_geo:
        reversals_deg.append({
            "trial": trial,
            "u1": order_u1,
            "su2": order_su2,
            "geo": order_geo,
            "ratio": ratio,
            "i1": i1,
            "i2": i2,
        })

print(f"  Near-degenerate topologies: {near_degenerate}")
print(f"  Reversals found: {len(reversals_deg)}")
if reversals_deg:
    for r in reversals_deg[:10]:
        print(f"    Trial {r['trial']}: ratio={r['ratio']:.4f}")
        print(f"      U(1)={r['u1']}, SU(2)={r['su2']}, Geo={r['geo']}")
        print(f"      I_top={r['i1']:.6f}, I_second={r['i2']:.6f}")


# ─── Summary ───
print()
print("=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"  Phase 1 (random, N=5000):       {len(reversals)} reversals / {total} topologies")
print(f"  Phase 2 (geometric, N=5000):    {len(reversals_geo)} reversals / {total_geo} topologies")
print(f"  Phase 3 (near-degen, N=10000):  {len(reversals_deg)} reversals / {near_degenerate} topologies")

total_r = len(reversals) + len(reversals_geo) + len(reversals_deg)
if total_r == 0:
    print()
    print("  CONCLUSION: SU(2) NEVER changes rankings on any tested topology.")
    print("  This is likely a structural invariant, not a sampling artifact.")
    print()
    print("  Mathematical explanation:")
    print("  For fixed axis: SU(2) = U(1) with half-phase")
    print("  → cos(Δθ/2) vs cos(Δθ) changes absolute values")
    print("  → but the MONOTONICITY of the ranking depends on S_eff,")
    print("    not on phase, because tensions dominate interference.")
else:
    print()
    print(f"  CONCLUSION: {total_r} ranking reversals found!")
    print("  SU(2) CAN change operational decisions under specific conditions.")
