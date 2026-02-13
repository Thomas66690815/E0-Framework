"""Analyze the 10-run E0 experiment results vs null control."""
import csv
from experiments.stats import (
    mean, std, bootstrap_ci, cohens_d, permutation_test,
    effect_size_label, monotonicity_score, kendall_tau,
)

def load_summary(path):
    data = {0: {"R": [], "H": [], "Phi": [], "v": []},
            1: {"R": [], "H": [], "Phi": [], "v": []},
            2: {"R": [], "H": [], "Phi": [], "v": []},
            3: {"R": [], "H": [], "Phi": [], "v": []}}
    with open(path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            t = int(row["turn_index"])
            data[t]["R"].append(float(row["R_mean"]))
            data[t]["H"].append(float(row["H_mean"]))
            data[t]["Phi"].append(int(row["Phi"]))
            data[t]["v"].append(float(row["v_mean"]))
    return data

e0 = load_summary("experiments/results/qm_derivation_e0/summary.csv")
null = load_summary("experiments/results/qm_derivation_null/summary.csv")

steps = ["Complex States", "Superposition", "Born Rule", "Unitarity"]

print("=" * 70)
print("  E0 EXPERIMENT (N=10) — QM Derivation")
print("=" * 70)
R_traj = []
for t in range(4):
    vals = e0[t]["R"]
    m, lo, hi = bootstrap_ci(vals)
    s = std(vals)
    R_traj.append(m)
    phi_m, phi_lo, phi_hi = bootstrap_ci([float(x) for x in e0[t]["Phi"]])
    print(f"  Step {t+1} ({steps[t]:16s}): "
          f"R = {m:.4f} [{lo:.4f}, {hi:.4f}]  "
          f"Phi = {phi_m:.0f} [{phi_lo:.0f}, {phi_hi:.0f}]")

print(f"\n  R trajectory:   {' -> '.join(f'{r:.4f}' for r in R_traj)}")
print(f"  Monotonicity:   {monotonicity_score(R_traj, 'decreasing'):.2f}")
print(f"  Kendall tau:    {kendall_tau(R_traj):.3f}")

print(f"\n{'=' * 70}")
print(f"  NULL CONTROL (N=1)")
print(f"{'=' * 70}")
N_traj = []
for t in range(4):
    m = mean(null[t]["R"])
    N_traj.append(m)
    print(f"  Step {t+1} ({steps[t]:16s}): R = {m:.4f}  Phi = {mean([float(x) for x in null[t]['Phi']]):.0f}")

print(f"\n  R trajectory:   {' -> '.join(f'{r:.4f}' for r in N_traj)}")
print(f"  Monotonicity:   {monotonicity_score(N_traj, 'decreasing'):.2f}")
print(f"  Kendall tau:    {kendall_tau(N_traj):.3f}")

print(f"\n{'=' * 70}")
print(f"  COMPARISON: E0 vs NULL")
print(f"{'=' * 70}")
print(f"  {'Step':<22s} {'E0':>8s} {'NULL':>8s} {'Diff':>8s} {'Ratio':>8s}")
print(f"  {'-'*22} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")
for t in range(4):
    e = mean(e0[t]["R"])
    n = mean(null[t]["R"])
    print(f"  {steps[t]:<22s} {e:>8.4f} {n:>8.4f} {e-n:>+8.4f} {e/n:>8.2f}x")

# Per-step detailed view
print(f"\n{'=' * 70}")
print(f"  ALL 10 RUNS — R values per step")
print(f"{'=' * 70}")
for t in range(4):
    vals = sorted(e0[t]["R"])
    print(f"  Step {t+1}: {', '.join(f'{v:.4f}' for v in vals)}")
    print(f"         min={min(vals):.4f}  max={max(vals):.4f}  range={max(vals)-min(vals):.4f}")
