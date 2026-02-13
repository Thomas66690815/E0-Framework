#!/usr/bin/env python3
"""Quick comparison: Placebo vs E₀ vs Null — THE critical test."""

import csv
import numpy as np

def kendalltau_simple(x, y):
    """Simple Kendall tau without scipy."""
    n = len(x)
    concordant = discordant = 0
    for i in range(n):
        for j in range(i+1, n):
            if (x[i] - x[j]) * (y[i] - y[j]) > 0:
                concordant += 1
            elif (x[i] - x[j]) * (y[i] - y[j]) < 0:
                discordant += 1
    tau = (concordant - discordant) / (n * (n-1) / 2) if n > 1 else 0
    return tau

def load(path):
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f): rows.append(r)
    return rows

def group_by_step(rows):
    steps = {}
    for r in rows:
        t = int(r['turn_index'])
        if t not in steps: steps[t] = []
        steps[t].append(float(r['R_mean']))
    return steps

def bootstrap_ci(vals, n=10000):
    arr = np.array(vals)
    means = [np.mean(np.random.choice(arr, len(arr), replace=True)) for _ in range(n)]
    return np.percentile(means, [2.5, 97.5])

# Load data  
placebo = group_by_step(load('experiments/results/qm_derivation_placebo/summary.csv'))
e0 = group_by_step(load('experiments/results/qm_derivation_e0/summary.csv'))
null_vals = [0.1913, 0.0837, 0.0716, 0.0540]  # N=1, no CIs

step_names = ['Complex States', 'Superposition', 'Born Rule', 'Unitarity']

print("=" * 72)
print("PLACEBO (ZFC) N=10 — Results")
print("=" * 72)
for step in sorted(placebo.keys()):
    vals = placebo[step]
    m = np.mean(vals)
    lo, hi = bootstrap_ci(vals)
    print(f"  Step {step+1} ({step_names[step]:<16}): R̄ = {m:.4f} [{lo:.4f}, {hi:.4f}]")

pl_traj = [np.mean(placebo[s]) for s in range(4)]
tau = kendalltau_simple(list(range(4)), pl_traj)
print(f"\n  R̄ trajectory:  {' → '.join(f'{v:.4f}' for v in pl_traj)}")
print(f"  Kendall τ:      {tau:.3f}")

print("\n" + "=" * 72)
print("CRITICAL THREE-WAY COMPARISON")
print("=" * 72)
header = f"  {'Step':<18} {'E₀':>8} {'Placebo':>8} {'Null':>8}  {'P/E₀':>6} {'P/Null':>6}"
print(header)
print(f"  {'─'*18} {'─'*8} {'─'*8} {'─'*8}  {'─'*6} {'─'*6}")

for step in range(4):
    e0_m = np.mean(e0[step])
    pl_m = np.mean(placebo[step])
    nu_m = null_vals[step]
    print(f"  {step_names[step]:<18} {e0_m:>8.4f} {pl_m:>8.4f} {nu_m:>8.4f}"
          f"  {pl_m/e0_m:>5.2f}x {pl_m/nu_m:>5.2f}x")

# Overall means
e0_overall = np.mean([np.mean(e0[s]) for s in range(4)])
pl_overall = np.mean(pl_traj)
nu_overall = np.mean(null_vals)

print(f"\n  {'OVERALL':<18} {e0_overall:>8.4f} {pl_overall:>8.4f} {nu_overall:>8.4f}"
      f"  {pl_overall/e0_overall:>5.2f}x {pl_overall/nu_overall:>5.2f}x")

# Step 1 analysis (most diagnostic — before context accumulation)
print("\n" + "=" * 72)
print("STEP 1 ANALYSIS (most diagnostic — minimal context effects)")
print("=" * 72)
e0_step1 = e0[0]
pl_step1 = placebo[0]

e0_m1 = np.mean(e0_step1)
pl_m1 = np.mean(pl_step1)
nu_m1 = null_vals[0]

# Cohen's d between E0 and Placebo at step 1
pooled_std = np.sqrt((np.std(e0_step1, ddof=1)**2 + np.std(pl_step1, ddof=1)**2) / 2)
d = (pl_m1 - e0_m1) / pooled_std if pooled_std > 0 else 0

print(f"  E₀ Step 1:      R̄ = {e0_m1:.4f} [{bootstrap_ci(e0_step1)[0]:.4f}, {bootstrap_ci(e0_step1)[1]:.4f}]")
print(f"  Placebo Step 1:  R̄ = {pl_m1:.4f} [{bootstrap_ci(pl_step1)[0]:.4f}, {bootstrap_ci(pl_step1)[1]:.4f}]")
print(f"  Null Step 1:     R̄ = {nu_m1:.4f} (N=1, no CI)")
print(f"\n  Cohen's d (Placebo - E₀): {d:.3f}", end="")
if abs(d) < 0.2:
    print(" (negligible)")
elif abs(d) < 0.5:
    print(" (small)")  
elif abs(d) < 0.8:
    print(" (medium)")
else:
    print(" (large)")

# Permutation test
combined = list(e0_step1) + list(pl_step1)
observed_diff = pl_m1 - e0_m1
n_perm = 10000
count = 0
for _ in range(n_perm):
    perm = np.random.permutation(combined)
    d_perm = np.mean(perm[:len(e0_step1)]) - np.mean(perm[len(e0_step1):])
    if abs(d_perm) >= abs(observed_diff):
        count += 1
p_perm = count / n_perm
print(f"  Permutation test p-value: {p_perm:.4f}")

# Distance analysis
dist_to_null = abs(pl_m1 - nu_m1)
dist_to_e0 = abs(pl_m1 - e0_m1)
print(f"\n  Distance Placebo→Null:  {dist_to_null:.4f}")
print(f"  Distance Placebo→E₀:   {dist_to_e0:.4f}")

print("\n" + "=" * 72)
print("VERDICT")
print("=" * 72)

if pl_m1 > e0_m1 * 1.1 and pl_m1 < nu_m1 * 0.9:
    print("  Placebo BETWEEN E₀ and Null.")
    print("  → Axiomatic priming helps SOMEWHAT, but E₀ helps MORE.")
    print("  → Partial content-specificity: both priming and content matter.")
elif abs(pl_m1 - nu_m1) < abs(pl_m1 - e0_m1):
    print("  Placebo CLOSER TO NULL than to E₀.")
    print("  → Content-specific effect CONFIRMED.")
    print("  → E₀ priming produces measurably different behavior than ZFC priming.")
elif abs(pl_m1 - e0_m1) < abs(pl_m1 - nu_m1):
    print("  Placebo CLOSER TO E₀ than to Null.")
    print("  → Any axiomatic priming helps similarly.")
    print("  → H₀ survives: effect is priming, not content.")
else:
    print("  Ambiguous — more data needed.")

# Full trajectory comparison
print("\n" + "=" * 72)
print("FULL TRAJECTORIES")
print("=" * 72)
print(f"  E₀:      {' → '.join(f'{np.mean(e0[s]):.4f}' for s in range(4))}")
print(f"  Placebo:  {' → '.join(f'{v:.4f}' for v in pl_traj)}")
print(f"  Null:     {' → '.join(f'{v:.4f}' for v in null_vals)}")

# Per-run Placebo values at each step
print("\n  Placebo per-run R̄ at Step 1:")
for i, v in enumerate(sorted(pl_step1)):
    print(f"    Run {i}: {v:.4f}")
