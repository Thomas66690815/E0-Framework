#!/usr/bin/env python3
"""Full 4-condition comparison: E₀ vs Placebo vs Inverted vs Null."""

import csv
import numpy as np

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

def cohens_d(a, b):
    na, nb = len(a), len(b)
    pooled = np.sqrt(((na-1)*np.std(a,ddof=1)**2 + (nb-1)*np.std(b,ddof=1)**2) / (na+nb-2))
    return (np.mean(a) - np.mean(b)) / pooled if pooled > 0 else 0

# Load all conditions
e0 = group_by_step(load('experiments/results/qm_derivation_e0/summary.csv'))
placebo = group_by_step(load('experiments/results/qm_derivation_placebo/summary.csv'))
inverted = group_by_step(load('experiments/results/qm_derivation_inverted/summary.csv'))
null = group_by_step(load('experiments/results/qm_derivation_null/summary.csv'))

step_names = ['Step 1 (initial)', 'Step 2', 'Step 3', 'Step 4 (final)']

print("=" * 80)
print("FULL 4-CONDITION COMPARISON — ALL N=10")
print("=" * 80)

# Per-step table
print(f"\n  {'Step':<16} {'E₀':>8} {'Placebo':>8} {'Inverted':>8} {'Null':>8}")
print(f"  {'─'*16} {'─'*8} {'─'*8} {'─'*8} {'─'*8}")

for s in range(4):
    e = np.mean(e0[s])
    p = np.mean(placebo[s])
    i = np.mean(inverted[s])
    n = np.mean(null[s])
    print(f"  {step_names[s]:<16} {e:>8.4f} {p:>8.4f} {i:>8.4f} {n:>8.4f}")

# Overall means
e_all = np.mean([np.mean(e0[s]) for s in range(4)])
p_all = np.mean([np.mean(placebo[s]) for s in range(4)])
i_all = np.mean([np.mean(inverted[s]) for s in range(4)])
n_all = np.mean([np.mean(null[s]) for s in range(4)])
print(f"  {'OVERALL':<16} {e_all:>8.4f} {p_all:>8.4f} {i_all:>8.4f} {n_all:>8.4f}")

# Trajectories
print(f"\n  E₀:       {' → '.join(f'{np.mean(e0[s]):.4f}' for s in range(4))}")
print(f"  Placebo:   {' → '.join(f'{np.mean(placebo[s]):.4f}' for s in range(4))}")
print(f"  Inverted:  {' → '.join(f'{np.mean(inverted[s]):.4f}' for s in range(4))}")
print(f"  Null:      {' → '.join(f'{np.mean(null[s]):.4f}' for s in range(4))}")

# Monotonicity
def monotonicity(traj):
    decreases = sum(1 for i in range(len(traj)-1) if traj[i] > traj[i+1])
    return decreases / (len(traj) - 1)

e_traj = [np.mean(e0[s]) for s in range(4)]
p_traj = [np.mean(placebo[s]) for s in range(4)]
i_traj = [np.mean(inverted[s]) for s in range(4)]
n_traj = [np.mean(null[s]) for s in range(4)]

print(f"\n  Monotonicity: E\u2080={monotonicity(e_traj):.2f}  Placebo={monotonicity(p_traj):.2f}  Inverted={monotonicity(i_traj):.2f}  Null={monotonicity(n_traj):.2f}")

# KEY: Inverted vs E₀ comparison (coherence test)
print("\n" + "=" * 80)
print("COHERENCE TEST: E₀ (QM task) vs INVERTED (Thermo task)")
print("  Same E₀ priming, different task domain")
print("=" * 80)

for s in range(4):
    e = np.mean(e0[s])
    i = np.mean(inverted[s])
    d = cohens_d(e0[s], inverted[s])
    print(f"  {step_names[s]:<16} E₀={e:.4f}  Inv={i:.4f}  Δ={i-e:+.4f}  d={d:+.3f}")

print(f"\n  E₀ overall:      {e_all:.4f}")
print(f"  Inverted overall: {i_all:.4f}")
print(f"  Ratio Inv/E₀:    {i_all/e_all:.2f}x")

# Step 1 detailed
d_step1 = cohens_d(e0[0], inverted[0])
print(f"\n  Step 1 Cohen's d (Inv vs E₀): {d_step1:+.3f}", end="")
if abs(d_step1) < 0.2: print(" (negligible)")
elif abs(d_step1) < 0.5: print(" (small)")
elif abs(d_step1) < 0.8: print(" (medium)")
else: print(" (large)")

# Ordering
print("\n" + "=" * 80)
print("RANKING (R̄ overall, lower = less resistance)")
print("=" * 80)
results = [
    ("E₀ (QM)", e_all),
    ("Inverted (Thermo)", i_all),
    ("Placebo (ZFC)", p_all),
    ("Null (nothing)", n_all),
]
for rank, (name, val) in enumerate(sorted(results, key=lambda x: x[1]), 1):
    print(f"  {rank}. {name:<22} R̄ = {val:.4f}")

# Interpretation
print("\n" + "=" * 80)
print("INTERPRETATION")
print("=" * 80)

if i_all < p_all and i_all < n_all:
    if abs(i_all - e_all) / e_all < 0.15:
        print("""
  INVERTED ≈ E₀ — E₀ priming helps ANY derivation, not just QM.
  → The E₀ effect is a GENERAL priming effect, not coherence-specific.
  → E₀ creates a low-resistance state for structured derivation regardless of domain.
""")
    else:
        print("""
  INVERTED < PLACEBO/NULL but INVERTED > E₀ — partial coherence effect.
  → E₀ helps thermodynamics too (more than ZFC does)
  → But helps QM even more → some coherence specificity
""")
elif i_all > p_all:
    print("""
  INVERTED > PLACEBO — E₀ priming with WRONG domain is WORSE than generic priming.
  → Strong coherence effect: E₀ only helps when task matches framework.
""")

print("\n  * Null is now N=10. All conditions complete.")
