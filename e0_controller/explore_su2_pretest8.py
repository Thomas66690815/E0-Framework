"""
Pretest 8 — Q4: What about the 720° periodicity?

SU(2) has a unique topological property: a 360° rotation gives U = −𝕀
(spinor sign flip), not U = +𝕀. Only at 720° does the spinor return
to its original state. This is the "plate trick" / Dirac belt trick.

For E₀, the question is: can actual graph topologies accumulate enough
phase around closed loops to reach the 360° regime where sign flips
occur? And does this sign flip produce observable ranking reversals?

Measurement strategy:
  1. Sweep graph sizes 5–15 nodes with high edge density
  2. For each topology, find the cycle with maximum holonomy angle
  3. Report distribution: how often do we reach 180°, 270°, 360°, 540°?
  4. When holonomy > 360°: does the ranking reversal rate increase?
  5. Compare: do sign-flip topologies show stronger SU(2) effects?
"""

import math
import random
import numpy as np
from collections import Counter
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller
from e0_controller.primitives import Outcome
from e0_controller.amplitude_overlay import analyze_controller_state
from e0_controller.spinor_connection import (
    su2_holonomy, omega, IDENTITY,
)

exec_fn = lambda s, t: Outcome.SUCCESS
rng = random.Random(42)


def holonomy_angle(U: np.ndarray) -> float:
    """Extract rotation angle from SU(2) matrix.

    U = cos(φ/2)·I − i·sin(φ/2)·(n̂·σ⃗)
    Tr(U) = 2·cos(φ/2)
    φ = 2·arccos(Tr(U).real / 2)

    Returns angle in degrees [0, 360].
    """
    tr = np.trace(U)
    cos_half = tr.real / 2.0
    cos_half = max(-1.0, min(1.0, cos_half))
    return math.degrees(2 * math.acos(cos_half))


def find_cycles(L: Landscape, max_length: int = 6) -> list:
    """Find all simple cycles up to max_length via DFS."""
    nodes = sorted(L._states)
    cycles = []

    for start in nodes:
        # DFS stack: (current_node, path_so_far, visited_set)
        stack = [(start, [start], {start})]
        while stack:
            curr, path, visited = stack.pop()
            if len(path) > max_length:
                continue
            neighbors = L.admissible_neighbors(curr)
            for nb in neighbors:
                if nb == start and len(path) >= 3:
                    # Found a cycle — store with closing edge back to start
                    cycles.append(path + [start])
                elif nb not in visited and len(path) < max_length:
                    stack.append((nb, path + [nb], visited | {nb}))

    # Deduplicate: normalize cycle representation
    unique = {}
    for c in cycles:
        # Canonical form: minimum rotation of the node sequence (excl. closing node)
        body = c[:-1]
        rotations = [tuple(body[i:] + body[:i]) for i in range(len(body))]
        canon = min(rotations)
        unique[canon] = c

    return list(unique.values())


def total_phase_around_cycle(L: Landscape, cycle: list) -> float:
    """Sum of |ω(x,y)| around the cycle, in degrees."""
    total = 0.0
    for i in range(len(cycle) - 1):
        total += abs(omega(L, cycle[i], cycle[i+1]))
    return math.degrees(total)


def make_random_landscape(nodes, density=0.7):
    L = Landscape()
    for i, x in enumerate(nodes):
        for j, y in enumerate(nodes):
            if i != j and rng.random() < density:
                d = 10 ** rng.uniform(-2, 2)
                r = 10 ** rng.uniform(-2, 2)
                L.add_edge(x, y, delta=d, resistance=r)
    return L


# ══════════════════════════════════════════════════════════
# Phase 1: Holonomy angle distribution across graph sizes
# ══════════════════════════════════════════════════════════

print("=" * 70)
print("Q4 PRETEST 8 — 720° Periodicity")
print("=" * 70)
print()

NODE_CONFIGS = [
    (5,  0.7, 500, 5),   # (nodes, density, trials, max_cycle_len)
    (7,  0.7, 300, 5),
    (8,  0.7, 300, 5),
]

BINS = [0, 45, 90, 135, 180, 270, 360, 540, 720]

print("PHASE 1: Maximum holonomy angle distribution")
print("-" * 60)
print(f"{'Nodes':>5}  {'Trials':>6}  {'Max°':>6}  {'Mean°':>6}  ", end="")
print("  ".join(f">{b}°" for b in [90, 180, 270, 360]))
print()

all_results = []  # (n_nodes, max_angle, L, cycles) for Phase 2

for n_nodes, density, n_trials, max_cyc_len in NODE_CONFIGS:
    nodes = ["S"] + [chr(65 + i) for i in range(n_nodes - 1)]
    max_angles = []
    results_for_size = []

    for trial in range(n_trials):
        L = make_random_landscape(nodes, density)
        adm = L.admissible_neighbors("S")
        if len(adm) < 2:
            continue

        # Find cycles and measure holonomy
        cycles = find_cycles(L, max_length=max_cyc_len)
        if not cycles:
            continue

        best_angle = 0.0
        best_cycle = None
        for c in cycles:
            U = su2_holonomy(L, c)
            angle = holonomy_angle(U)
            if angle > best_angle:
                best_angle = angle
                best_cycle = c

        max_angles.append(best_angle)
        results_for_size.append((best_angle, L))

    if not max_angles:
        print(f"{n_nodes:>5}  {n_trials:>6}  no valid topologies")
        continue

    max_a = max(max_angles)
    mean_a = sum(max_angles) / len(max_angles)
    counts = {b: sum(1 for a in max_angles if a > b) for b in [90, 180, 270, 360]}

    n_valid = len(max_angles)
    print(f"{n_nodes:>5}  {n_valid:>6}  {max_a:>6.1f}  {mean_a:>6.1f}  ", end="")
    print("  ".join(f"{counts[b]:>4}" for b in [90, 180, 270, 360]))

    all_results.extend([(n_nodes, a, L) for a, L in results_for_size])


# ══════════════════════════════════════════════════════════
# Phase 2: Reversal rate conditioned on holonomy angle
# ══════════════════════════════════════════════════════════

print()
print("PHASE 2: Reversal rate conditioned on max holonomy angle")
print("-" * 60)

angle_bins = [(0, 90), (90, 180), (180, 270), (270, 361)]
bin_stats = {b: {"total": 0, "reversals_su2": 0} for b in angle_bins}

for n_nodes, max_angle, L in all_results:
    adm = L.admissible_neighbors("S")
    if len(adm) < 2:
        continue

    ctrl = E0Controller(L, exec_fn)
    try:
        r_u1 = analyze_controller_state(ctrl, "S", horizon_edges=3, use_su2=False)
        r_su2 = analyze_controller_state(ctrl, "S", horizon_edges=3, use_su2=True)
    except Exception:
        continue

    order_u1 = tuple(a.action for a in r_u1.action_infos)
    order_su2 = tuple(a.action for a in r_su2.action_infos)

    for (lo, hi) in angle_bins:
        if lo <= max_angle < hi:
            bin_stats[(lo, hi)]["total"] += 1
            if order_u1 != order_su2:
                bin_stats[(lo, hi)]["reversals_su2"] += 1
            break
            if order_u1 != order_su2:
                bin_stats[(270, 360)]["reversals_su2"] += 1
            if order_u1 != order_geo:
                bin_stats[(270, 360)]["reversals_geo"] += 1

print(f"{'Holonomy':>12}  {'Total':>6}  {'SU(2) rev':>10}")
for (lo, hi) in angle_bins:
    s = bin_stats[(lo, hi)]
    t = s["total"]
    r_su2 = s["reversals_su2"]
    pct_su2 = r_su2 / t * 100 if t > 0 else 0
    label = f"{lo}°–{hi}°"
    print(f"{label:>12}  {t:>6}  {r_su2:>4} ({pct_su2:5.1f}%)")


# ══════════════════════════════════════════════════════════
# Phase 3: Sign flip detection — U ≈ −I
# ══════════════════════════════════════════════════════════

print()
print("PHASE 3: Sign flip detection (holonomy ≈ −I)")
print("-" * 60)

# A sign flip means U ≈ −I, i.e. holonomy_angle ≈ 360°
# Threshold: |angle - 360°| < 30°
SIGN_FLIP_RANGE = (330, 390)  # degrees

sign_flips = 0
sign_flip_reversals_su2 = 0

for n_nodes, max_angle, L in all_results:
    if not (SIGN_FLIP_RANGE[0] <= max_angle <= SIGN_FLIP_RANGE[1]):
        continue

    adm = L.admissible_neighbors("S")
    if len(adm) < 2:
        continue

    ctrl = E0Controller(L, exec_fn)
    try:
        r_u1 = analyze_controller_state(ctrl, "S", horizon_edges=3, use_su2=False)
        r_su2 = analyze_controller_state(ctrl, "S", horizon_edges=3, use_su2=True)
    except Exception:
        continue

    sign_flips += 1
    order_u1 = tuple(a.action for a in r_u1.action_infos)
    order_su2 = tuple(a.action for a in r_su2.action_infos)

    if order_u1 != order_su2:
        sign_flip_reversals_su2 += 1

if sign_flips > 0:
    print(f"  Topologies with holonomy near 360° (±30°): {sign_flips}")
    print(f"  SU(2) reversals: {sign_flip_reversals_su2} ({sign_flip_reversals_su2/sign_flips*100:.1f}%)")
else:
    print("  No topologies reached the sign-flip regime (330°–390°)")

print()
print("=" * 70)
print("SUMMARY")
print("=" * 70)
