"""
Probabilistic Baseline Model
==============================
Computes what a PURELY probabilistic system (H₀) would predict,
and compares those predictions against actual experiment data.

The null model: R̄(step) = R₀ · exp(-λ · cumulative_tokens)

If actual data matches this exponential decay, the E₀ effect is
indistinguishable from a context-length artifact.

If actual data deviates from this model significantly, something
beyond context length is at work.
"""

from __future__ import annotations

import csv
import math
import sys
from pathlib import Path
from typing import List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from experiments.stats import mean, std, bootstrap_ci


def fit_exponential_decay(
    cumulative_tokens: List[float],
    R_values: List[float],
) -> Tuple[float, float]:
    """
    Fit R̄ = R₀ · exp(-λ · n) to the data.
    Uses log-linear regression: log(R̄) = log(R₀) - λ·n

    Returns: (R₀, λ)
    """
    if not R_values or not cumulative_tokens:
        return (0.1, 0.0)

    # Filter out zeros
    valid = [(n, r) for n, r in zip(cumulative_tokens, R_values) if r > 0]
    if len(valid) < 2:
        return (0.1, 0.0)

    ns = [v[0] for v in valid]
    log_rs = [math.log(v[1]) for v in valid]

    # Simple linear regression on log(R) = a + b·n
    n_mean = mean(ns)
    lr_mean = mean(log_rs)
    numerator = sum((n - n_mean) * (lr - lr_mean) for n, lr in zip(ns, log_rs))
    denominator = sum((n - n_mean) ** 2 for n in ns)

    if abs(denominator) < 1e-12:
        return (math.exp(lr_mean), 0.0)

    b = numerator / denominator  # slope = -λ
    a = lr_mean - b * n_mean     # intercept = log(R₀)

    R0 = math.exp(a)
    lam = -b  # positive λ means decay

    return (R0, lam)


def predict_R(R0: float, lam: float, n: float) -> float:
    """Predict R̄ at cumulative token position n."""
    return R0 * math.exp(-lam * n)


def load_experiment_data(summary_path: str):
    """Load per-run, per-turn data from summary CSV."""
    turns = {}  # {(run_id, turn_index): {R, tokens, ...}}
    with open(summary_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = (int(row["run_id"]), int(row["turn_index"]))
            turns[key] = {
                "R": float(row["R_mean"]),
                "H": float(row["H_mean"]),
                "Phi": int(row["Phi"]),
                "tokens": int(row["token_count"]),
            }
    return turns


def analyze_baseline(summary_path: str, label: str = "Experiment"):
    """
    Compare actual R̄ trajectory against exponential decay baseline.
    """
    turns = load_experiment_data(summary_path)

    # Get unique runs and steps
    runs = sorted(set(k[0] for k in turns.keys()))
    steps = sorted(set(k[1] for k in turns.keys()))

    print(f"\n{'=' * 60}")
    print(f"  PROBABILISTIC BASELINE ANALYSIS: {label}")
    print(f"  Runs: {len(runs)}, Steps: {len(steps)}")
    print(f"{'=' * 60}")

    # Per-run analysis
    all_residuals = []

    for run_id in runs:
        # Compute cumulative tokens
        cum_tokens = []
        R_values = []
        running_total = 0

        for step in steps:
            key = (run_id, step)
            if key not in turns:
                continue
            running_total += turns[key]["tokens"]
            cum_tokens.append(running_total)
            R_values.append(turns[key]["R"])

        # Fit exponential decay to this run
        R0, lam = fit_exponential_decay(
            [float(x) for x in cum_tokens], R_values
        )

        # Compute predictions and residuals
        residuals = []
        for n, actual in zip(cum_tokens, R_values):
            predicted = predict_R(R0, lam, float(n))
            residual = actual - predicted
            residuals.append(residual)

        all_residuals.append(residuals)

        if run_id == 0:  # Print detailed for first run
            print(f"\n  Run 0 (example):")
            print(f"  Fitted: R₀={R0:.4f}, λ={lam:.6f}")
            print(f"  {'Step':>5} {'Tokens':>7} {'Actual':>8} {'Predicted':>10} {'Residual':>10}")
            for i, (n, actual) in enumerate(zip(cum_tokens, R_values)):
                pred = predict_R(R0, lam, float(n))
                res = actual - pred
                print(f"  {i+1:>5} {n:>7} {actual:>8.4f} {pred:>10.4f} {res:>+10.4f}")

    # Aggregate residuals across runs
    print(f"\n  Residuals (Actual - Predicted) across all runs:")
    print(f"  {'Step':>5} {'Mean Res':>10} {'Std Res':>10} {'Interpretation':>30}")

    for step_idx in range(len(steps)):
        step_residuals = [
            all_residuals[r][step_idx]
            for r in range(len(runs))
            if step_idx < len(all_residuals[r])
        ]
        m = mean(step_residuals)
        s = std(step_residuals) if len(step_residuals) > 1 else 0

        if abs(m) < s * 0.5:
            interp = "~ baseline (H₀ consistent)"
        elif m < 0:
            interp = "BELOW baseline (structurally easier)"
        else:
            interp = "ABOVE baseline (structurally harder)"

        print(f"  {step_idx+1:>5} {m:>+10.4f} {s:>10.4f} {interp:>30}")

    # Overall fit quality
    all_flat = [r for run in all_residuals for r in run]
    rmse = math.sqrt(mean([r**2 for r in all_flat]))
    mean_R = mean([turns[k]["R"] for k in turns])

    print(f"\n  Overall RMSE:       {rmse:.4f}")
    print(f"  Mean R̄:             {mean_R:.4f}")
    print(f"  RMSE / Mean R̄:     {rmse/mean_R:.2%}")
    print(f"  (If < 10%: exponential decay fits well → H₀ plausible)")
    print(f"  (If > 20%: significant deviations → structural effects likely)")

    # Fit across all runs combined
    all_cum = []
    all_R = []
    for run_id in runs:
        running = 0
        for step in steps:
            key = (run_id, step)
            if key in turns:
                running += turns[key]["tokens"]
                all_cum.append(float(running))
                all_R.append(turns[key]["R"])

    R0_global, lam_global = fit_exponential_decay(all_cum, all_R)
    print(f"\n  Global fit: R̄ = {R0_global:.4f} · exp(-{lam_global:.6f} · n)")
    print(f"  This predicts R̄ decreases by {(1 - math.exp(-lam_global * 700)):.1%} per ~700 tokens")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Probabilistic Baseline Analysis")
    parser.add_argument("--data", required=True, help="Path to summary.csv")
    parser.add_argument("--label", default="Experiment", help="Label for this condition")
    args = parser.parse_args()

    analyze_baseline(args.data, args.label)


if __name__ == "__main__":
    main()
