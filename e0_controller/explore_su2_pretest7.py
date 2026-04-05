"""
Pretest 7 — Q3: Can axis_fn be meaningfully parameterized?

On simple topologies (Pretests 1–4), all axis choices (ẑ, x̂, ŷ, mixed)
produced identical rankings.  Pretest 5 showed that SU(2) with default ẑ
produces 6.3% reversal rate on 5-node graphs.

This pretest asks: does the CHOICE of rotation axis matter?

Five axis strategies on 5000 random 5-node topologies:
  1. ẑ = [0,0,1]  — default (minimal embedding, reduces to U(1) half-phase)
  2. x̂ = [1,0,0]  — σ_x generator
  3. ŷ = [0,1,0]  — σ_y generator
  4. ω-derived    — axis derived from the edge's phase angle ω(x,y)
  5. random       — deterministic pseudo-random per edge

Measurements:
  A. Reversal rate vs U(1) for each axis
  B. Inter-axis disagreement: do different axes produce different rankings?
  C. Near-degenerate performance: which axis breaks degeneracy most?
"""

import math
import random
import numpy as np
from collections import Counter
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller
from e0_controller.primitives import Outcome
from e0_controller.amplitude_overlay import analyze_controller_state
from e0_controller.spinor_connection import omega

exec_fn = lambda s, t: Outcome.SUCCESS
rng = random.Random(42)

# ── Axis functions ────────────────────────────────────────

def axis_z(L, x, y):
    return np.array([0.0, 0.0, 1.0])

def axis_x(L, x, y):
    return np.array([1.0, 0.0, 0.0])

def axis_y(L, x, y):
    return np.array([0.0, 1.0, 0.0])

def axis_omega(L, x, y):
    """Derive axis from phase angle ω(x,y) — rotated in xz-plane."""
    w = omega(L, x, y)
    if abs(w) > 1e-10:
        return np.array([math.cos(w), 0.0, math.sin(w)])
    return np.array([0.0, 0.0, 1.0])

_edge_rng = random.Random(123)
_edge_cache = {}

def axis_random(L, x, y):
    """Deterministic pseudo-random axis per edge (cached)."""
    key = (x, y)
    if key not in _edge_cache:
        # Random point on unit sphere via Marsaglia method
        while True:
            u = _edge_rng.uniform(-1, 1)
            v = _edge_rng.uniform(-1, 1)
            s = u*u + v*v
            if s < 1.0:
                break
        factor = 2 * math.sqrt(1 - s)
        _edge_cache[key] = np.array([u * factor, v * factor, 1 - 2*s])
    return _edge_cache[key]

AXES = {
    "ẑ": axis_z,
    "x̂": axis_x,
    "ŷ": axis_y,
    "ω-derived": axis_omega,
    "random": axis_random,
}

# ── Landscape generator ──────────────────────────────────

def make_random_landscape(nodes, density=0.6):
    L = Landscape()
    for i, x in enumerate(nodes):
        for j, y in enumerate(nodes):
            if i != j and rng.random() < density:
                d = 10 ** rng.uniform(-2, 2)
                r = 10 ** rng.uniform(-2, 2)
                L.add_edge(x, y, delta=d, resistance=r)
    return L


# ── Phase 1: Reversal rate per axis vs U(1) ──────────────

print("=" * 70)
print("Q3 PRETEST 7 — Axis Function Parameterization")
print("=" * 70)
print()

N_TRIALS = 5000
nodes = ["S", "A", "B", "C", "D"]

# Pre-generate landscapes (same for all axes)
landscapes = []
for trial in range(N_TRIALS):
    L = make_random_landscape(nodes)
    adm = L.admissible_neighbors("S")
    if len(adm) >= 2:
        landscapes.append(L)

print(f"Valid topologies: {len(landscapes)} / {N_TRIALS}")
print()

# Compute U(1) rankings once
u1_rankings = []
for L in landscapes:
    ctrl = E0Controller(L, exec_fn)
    try:
        r = analyze_controller_state(ctrl, "S", horizon_edges=3, use_su2=False)
        u1_rankings.append(tuple(a.action for a in r.action_infos))
    except Exception:
        u1_rankings.append(None)

# Compute SU(2) rankings per axis
axis_rankings = {}
for name, afn in AXES.items():
    rankings = []
    for L in landscapes:
        ctrl = E0Controller(L, exec_fn)
        try:
            r = analyze_controller_state(ctrl, "S", horizon_edges=3,
                                          use_su2=True, axis_fn=afn)
            rankings.append(tuple(a.action for a in r.action_infos))
        except Exception:
            rankings.append(None)
    axis_rankings[name] = rankings

# Also compute geometric (no axis_fn)
geo_rankings = []
for L in landscapes:
    ctrl = E0Controller(L, exec_fn)
    try:
        r = analyze_controller_state(ctrl, "S", horizon_edges=3, use_su2="geometric")
        geo_rankings.append(tuple(a.action for a in r.action_infos))
    except Exception:
        geo_rankings.append(None)
axis_rankings["geometric"] = geo_rankings

# ── Phase 1 Results: reversal rate vs U(1) ────────────────

print("PHASE 1: Reversal rate vs U(1) per axis")
print("-" * 50)

for name in list(AXES.keys()) + ["geometric"]:
    reversals = 0
    valid = 0
    for u1, su2 in zip(u1_rankings, axis_rankings[name]):
        if u1 is not None and su2 is not None:
            valid += 1
            if u1 != su2:
                reversals += 1
    rate = reversals / valid * 100 if valid else 0
    print(f"  {name:12s}  {reversals:4d} / {valid:4d}  = {rate:5.1f}%")

# ── Phase 2: Inter-axis disagreement ─────────────────────

print()
print("PHASE 2: Inter-axis disagreement (axis A vs axis B)")
print("-" * 50)

all_names = list(AXES.keys()) + ["geometric"]
for i, a in enumerate(all_names):
    for b in all_names[i+1:]:
        disagree = 0
        valid = 0
        for ra, rb in zip(axis_rankings[a], axis_rankings[b]):
            if ra is not None and rb is not None:
                valid += 1
                if ra != rb:
                    disagree += 1
        rate = disagree / valid * 100 if valid else 0
        print(f"  {a:12s} vs {b:12s}  {disagree:4d} / {valid:4d}  = {rate:5.1f}%")

# ── Phase 3: Near-degenerate landscapes ──────────────────

print()
print("PHASE 3: Near-degenerate U(1) landscapes (I₂/I₁ > 0.8)")
print("-" * 50)

for name in all_names:
    reversals = 0
    total_degen = 0
    for idx, (L, u1) in enumerate(zip(landscapes, u1_rankings)):
        su2 = axis_rankings[name][idx]
        if u1 is None or su2 is None:
            continue
        # Check U(1) near-degeneracy
        ctrl = E0Controller(L, exec_fn)
        try:
            r = analyze_controller_state(ctrl, "S", horizon_edges=3, use_su2=False)
            intensities = sorted([a.intensity for a in r.action_infos], reverse=True)
            if len(intensities) >= 2 and intensities[0] > 1e-12:
                ratio = intensities[1] / intensities[0]
                if ratio > 0.8:
                    total_degen += 1
                    if u1 != su2:
                        reversals += 1
        except Exception:
            continue
    rate = reversals / total_degen * 100 if total_degen else 0
    print(f"  {name:12s}  {reversals:4d} / {total_degen:4d}  = {rate:5.1f}%")

# ── Phase 4: Axis uniqueness summary ─────────────────────

print()
print("PHASE 4: Unique ranking profiles per topology")
print("-" * 50)

unique_counts = Counter()
for idx in range(len(landscapes)):
    rankings = set()
    for name in all_names:
        r = axis_rankings[name][idx]
        if r is not None:
            rankings.add(r)
    unique_counts[len(rankings)] += 1

for k in sorted(unique_counts):
    pct = unique_counts[k] / len(landscapes) * 100
    print(f"  {k} distinct rankings: {unique_counts[k]:4d}  ({pct:5.1f}%)")

print()
print("=" * 70)
print("CONCLUSION")
print("=" * 70)
