"""
E₀ Statistical Analysis — Confidence Intervals, Effect Sizes, Tests
=====================================================================
Analyzes experiment results for scientific rigor:
  - Confidence intervals for all metrics (bootstrap)
  - Cohen's d effect sizes between conditions
  - Permutation tests for significance
  - Trend analysis (R̄ monotonicity across derivation steps)
  - Summary tables for publication

Usage:
    from experiments.stats import analyze_experiment, compare_conditions

    # Single experiment analysis
    analysis = analyze_experiment(experiment_result)

    # Compare two conditions
    comparison = compare_conditions(e0_result, null_result)
"""

from __future__ import annotations

import json
import math
import os
import sys
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ─────────────────────────────────────────────────────
# Core Statistical Functions
# ─────────────────────────────────────────────────────

def mean(values: List[float]) -> float:
    """Arithmetic mean."""
    if not values:
        return 0.0
    return sum(values) / len(values)


def std(values: List[float], ddof: int = 1) -> float:
    """Standard deviation with Bessel's correction."""
    if len(values) < 2:
        return 0.0
    m = mean(values)
    ss = sum((x - m) ** 2 for x in values)
    return math.sqrt(ss / (len(values) - ddof))


def median(values: List[float]) -> float:
    """Median."""
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    if n % 2 == 1:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2


def percentile(values: List[float], p: float) -> float:
    """p-th percentile (0-100)."""
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * p / 100.0
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[int(f)] * (c - k) + s[int(c)] * (k - f)


# ─────────────────────────────────────────────────────
# Bootstrap Confidence Intervals
# ─────────────────────────────────────────────────────

def bootstrap_ci(
    values: List[float],
    n_bootstrap: int = 10000,
    ci: float = 95.0,
    statistic=mean,
    seed: int = 42,
) -> Tuple[float, float, float]:
    """
    Bootstrap confidence interval.

    Returns: (point_estimate, ci_lower, ci_upper)
    """
    if len(values) < 2:
        v = values[0] if values else 0.0
        return (v, v, v)

    rng = random.Random(seed)
    n = len(values)
    point = statistic(values)

    # Bootstrap resampling
    boot_stats = []
    for _ in range(n_bootstrap):
        sample = [rng.choice(values) for _ in range(n)]
        boot_stats.append(statistic(sample))

    boot_stats.sort()
    alpha = (100.0 - ci) / 2.0
    lower = percentile(boot_stats, alpha)
    upper = percentile(boot_stats, 100.0 - alpha)

    return (round(point, 6), round(lower, 6), round(upper, 6))


# ─────────────────────────────────────────────────────
# Effect Size
# ─────────────────────────────────────────────────────

def cohens_d(group1: List[float], group2: List[float]) -> float:
    """
    Cohen's d effect size.

    |d| < 0.2: negligible
    0.2 ≤ |d| < 0.5: small
    0.5 ≤ |d| < 0.8: medium
    |d| ≥ 0.8: large
    """
    if len(group1) < 2 or len(group2) < 2:
        return 0.0

    m1, m2 = mean(group1), mean(group2)
    s1, s2 = std(group1), std(group2)
    n1, n2 = len(group1), len(group2)

    # Pooled standard deviation
    pooled = math.sqrt(
        ((n1 - 1) * s1 ** 2 + (n2 - 1) * s2 ** 2) / (n1 + n2 - 2)
    )

    if pooled < 1e-10:
        return 0.0

    return (m1 - m2) / pooled


def effect_size_label(d: float) -> str:
    """Human-readable effect size label."""
    ad = abs(d)
    if ad < 0.2:
        return "negligible"
    elif ad < 0.5:
        return "small"
    elif ad < 0.8:
        return "medium"
    else:
        return "large"


# ─────────────────────────────────────────────────────
# Permutation Test
# ─────────────────────────────────────────────────────

def permutation_test(
    group1: List[float],
    group2: List[float],
    n_permutations: int = 10000,
    seed: int = 42,
) -> float:
    """
    Two-sided permutation test for difference in means.

    Returns: p-value
    """
    if not group1 or not group2:
        return 1.0

    rng = random.Random(seed)
    observed_diff = abs(mean(group1) - mean(group2))
    combined = group1 + group2
    n1 = len(group1)

    count_extreme = 0
    for _ in range(n_permutations):
        rng.shuffle(combined)
        perm_diff = abs(mean(combined[:n1]) - mean(combined[n1:]))
        if perm_diff >= observed_diff:
            count_extreme += 1

    return count_extreme / n_permutations


# ─────────────────────────────────────────────────────
# Trend Analysis (Monotonicity)
# ─────────────────────────────────────────────────────

def monotonicity_score(values: List[float], direction: str = "decreasing") -> float:
    """
    Fraction of consecutive pairs that follow the expected direction.

    1.0 = perfectly monotonic
    0.0 = perfectly anti-monotonic
    0.5 = no trend

    For R̄ across QM steps: we expect decreasing (cumulative entailment).
    """
    if len(values) < 2:
        return 1.0

    correct = 0
    total = len(values) - 1

    for i in range(total):
        if direction == "decreasing":
            if values[i + 1] <= values[i]:
                correct += 1
        else:  # increasing
            if values[i + 1] >= values[i]:
                correct += 1

    return correct / total


def kendall_tau(values: List[float]) -> float:
    """
    Kendall's tau rank correlation with position index.

    -1 = perfectly decreasing
    +1 = perfectly increasing
     0 = no trend
    """
    n = len(values)
    if n < 2:
        return 0.0

    concordant = 0
    discordant = 0
    for i in range(n):
        for j in range(i + 1, n):
            # We compare with index order (i < j always)
            if values[j] < values[i]:
                concordant += 1  # decreasing trend
            elif values[j] > values[i]:
                discordant += 1

    total_pairs = n * (n - 1) / 2
    if total_pairs == 0:
        return 0.0

    # Negative tau = decreasing trend (what we expect for R̄)
    return (discordant - concordant) / total_pairs


# ─────────────────────────────────────────────────────
# Experiment Analysis
# ─────────────────────────────────────────────────────

@dataclass
class TurnStats:
    """Statistical summary for one turn across all runs."""
    turn_index: int
    prompt: str
    n: int
    R_mean: Tuple[float, float, float]   # (point, ci_lo, ci_hi)
    H_mean: Tuple[float, float, float]
    Phi: Tuple[float, float, float]
    v_mean: Tuple[float, float, float]
    R_values: List[float]                 # raw values for comparison


@dataclass
class ExperimentAnalysis:
    """Full statistical analysis of one experiment."""
    experiment_id: str
    condition: str
    n_runs: int
    turn_stats: List[TurnStats]
    R_trajectory: List[float]             # R̄ means across turns
    R_monotonicity: float                 # monotonicity score
    R_kendall: float                      # Kendall's tau


def analyze_experiment(experiment) -> str:
    """
    Produce a statistical analysis report from an ExperimentResult.

    Returns formatted text report.
    """
    exp_id = experiment.experiment_id
    condition = experiment.condition
    runs = experiment.runs
    n_runs = len(runs)

    if n_runs == 0:
        return f"No runs in experiment {exp_id}."

    # Determine number of turns from first run
    n_turns = len(runs[0].turns)

    # Collect per-turn metrics across runs
    turn_analyses: List[TurnStats] = []
    R_trajectory = []

    for t in range(n_turns):
        R_values = [r.turns[t].R_mean for r in runs if t < len(r.turns)]
        H_values = [r.turns[t].H_mean for r in runs if t < len(r.turns)]
        Phi_values = [float(r.turns[t].Phi) for r in runs if t < len(r.turns)]
        v_values = [r.turns[t].v_mean for r in runs if t < len(r.turns)]

        prompt = runs[0].turns[t].prompt if t < len(runs[0].turns) else "?"

        ts = TurnStats(
            turn_index=t,
            prompt=prompt[:80],
            n=len(R_values),
            R_mean=bootstrap_ci(R_values) if R_values else (0, 0, 0),
            H_mean=bootstrap_ci(H_values) if H_values else (0, 0, 0),
            Phi=bootstrap_ci(Phi_values) if Phi_values else (0, 0, 0),
            v_mean=bootstrap_ci(v_values) if v_values else (0, 0, 0),
            R_values=R_values,
        )
        turn_analyses.append(ts)
        R_trajectory.append(ts.R_mean[0])

    R_mono = monotonicity_score(R_trajectory, "decreasing")
    R_tau = kendall_tau(R_trajectory)

    # Build report
    lines = [
        f"{'═' * 70}",
        f"  STATISTICAL ANALYSIS: {exp_id}",
        f"  Condition: {condition}",
        f"  Runs: {n_runs}",
        f"{'═' * 70}",
        "",
        "  Per-Turn Metrics (point estimate [95% CI]):",
        f"  {'Turn':<5} {'R̄':>22} {'H̄':>22} {'Φ':>18} {'v̄':>22}",
        f"  {'─' * 5} {'─' * 22} {'─' * 22} {'─' * 18} {'─' * 22}",
    ]

    for ts in turn_analyses:
        r = ts.R_mean
        h = ts.H_mean
        p = ts.Phi
        v = ts.v_mean
        lines.append(
            f"  {ts.turn_index:<5} "
            f"{r[0]:.4f} [{r[1]:.4f}, {r[2]:.4f}]  "
            f"{h[0]:.4f} [{h[1]:.4f}, {h[2]:.4f}]  "
            f"{p[0]:.0f} [{p[1]:.0f}, {p[2]:.0f}]  "
            f"{v[0]:.1f} [{v[1]:.1f}, {v[2]:.1f}]"
        )

    lines += [
        "",
        "  Trend Analysis (R̄ across derivation steps):",
        f"    R̄ trajectory:    {' → '.join(f'{r:.4f}' for r in R_trajectory)}",
        f"    Monotonicity:     {R_mono:.2f} (1.0 = perfectly decreasing)",
        f"    Kendall's τ:      {R_tau:.3f} (negative = decreasing trend)",
        "",
    ]

    return "\n".join(lines)


# ─────────────────────────────────────────────────────
# Condition Comparison
# ─────────────────────────────────────────────────────

def compare_conditions(
    exp_a,  # ExperimentResult (e.g., E₀-initialized)
    exp_b,  # ExperimentResult (e.g., null control)
    label_a: str = "E₀",
    label_b: str = "Control",
) -> str:
    """
    Statistical comparison of two experimental conditions.

    For each turn, compares:
      - Mean R̄ with confidence intervals
      - Cohen's d effect size
      - Permutation test p-value
    """
    runs_a = exp_a.runs
    runs_b = exp_b.runs
    n_turns = min(
        len(runs_a[0].turns) if runs_a else 0,
        len(runs_b[0].turns) if runs_b else 0,
    )

    lines = [
        f"{'═' * 70}",
        f"  CONDITION COMPARISON: {label_a} vs {label_b}",
        f"  Runs: {len(runs_a)} vs {len(runs_b)}",
        f"{'═' * 70}",
        "",
        f"  {'Turn':<5} {'R̄(' + label_a + ')':>12} {'R̄(' + label_b + ')':>12} "
        f"{'Cohen d':>10} {'Effect':>12} {'p-value':>10}",
        f"  {'─' * 5} {'─' * 12} {'─' * 12} {'─' * 10} {'─' * 12} {'─' * 10}",
    ]

    for t in range(n_turns):
        R_a = [r.turns[t].R_mean for r in runs_a if t < len(r.turns)]
        R_b = [r.turns[t].R_mean for r in runs_b if t < len(r.turns)]

        m_a = mean(R_a)
        m_b = mean(R_b)
        d = cohens_d(R_a, R_b)
        label = effect_size_label(d)
        p = permutation_test(R_a, R_b)

        sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"

        lines.append(
            f"  {t:<5} {m_a:>12.4f} {m_b:>12.4f} "
            f"{d:>+10.3f} {label:>12} {p:>8.4f} {sig}"
        )

    # Overall comparison (pooled across all turns)
    all_R_a = [r.turns[t].R_mean for r in runs_a for t in range(min(n_turns, len(r.turns)))]
    all_R_b = [r.turns[t].R_mean for r in runs_b for t in range(min(n_turns, len(r.turns)))]

    if all_R_a and all_R_b:
        d_overall = cohens_d(all_R_a, all_R_b)
        p_overall = permutation_test(all_R_a, all_R_b)
        lines += [
            "",
            f"  Overall (pooled):",
            f"    {label_a} R̄ = {mean(all_R_a):.4f} ± {std(all_R_a):.4f}",
            f"    {label_b} R̄ = {mean(all_R_b):.4f} ± {std(all_R_b):.4f}",
            f"    Cohen's d = {d_overall:+.3f} ({effect_size_label(d_overall)})",
            f"    p-value   = {p_overall:.4f}",
        ]

    lines.append("")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────
# Null Hypothesis Test
# ─────────────────────────────────────────────────────

def test_context_length_hypothesis(experiment) -> str:
    """
    Test H₀: R̄ decreases only because context window grows.

    If H₀ is true, R̄ should decrease monotonically regardless of
    prompt content. We test this by checking whether the CONTROL
    condition also shows the same R̄ decrease pattern.

    This function analyzes a single experiment and reports whether
    the R̄ trajectory is consistent with a pure context-length effect.
    """
    runs = experiment.runs
    if not runs:
        return "No data."

    n_turns = len(runs[0].turns)

    # Get R̄ per turn
    R_per_turn = []
    for t in range(n_turns):
        values = [r.turns[t].R_mean for r in runs if t < len(r.turns)]
        R_per_turn.append(mean(values))

    # Token counts per turn (proxy for context growth)
    tokens_per_turn = []
    for t in range(n_turns):
        values = [float(r.turns[t].token_count) for r in runs if t < len(r.turns)]
        tokens_per_turn.append(mean(values))

    mono = monotonicity_score(R_per_turn, "decreasing")
    tau = kendall_tau(R_per_turn)

    lines = [
        f"  H₀ Analysis: Context Length Effect",
        f"  ────────────────────────────────────",
        f"  R̄ trajectory:  {' → '.join(f'{r:.4f}' for r in R_per_turn)}",
        f"  Monotonicity:   {mono:.2f}",
        f"  Kendall's τ:    {tau:.3f}",
        f"  Tokens/turn:    {' → '.join(f'{t:.0f}' for t in tokens_per_turn)}",
        f"",
        f"  Interpretation:",
    ]

    if mono == 1.0 and tau < -0.8:
        lines.append(
            f"    R̄ is perfectly monotonically decreasing. This is CONSISTENT\n"
            f"    with H₀ (context length effect). Compare with control condition\n"
            f"    to distinguish structural entailment from mere context growth."
        )
    elif mono > 0.5:
        lines.append(
            f"    R̄ shows a decreasing trend but with breaks. The non-monotonic\n"
            f"    steps may indicate genuine structural effects beyond context length."
        )
    else:
        lines.append(
            f"    R̄ does not show a clear decreasing trend. H₀ is unlikely."
        )

    return "\n".join(lines)


# ─────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────

def main():
    """Analyze results from a completed experiment."""
    import argparse

    parser = argparse.ArgumentParser(description="E₀ Statistical Analysis")
    parser.add_argument("--results", required=True, help="Path to experiment JSON")
    parser.add_argument("--compare", default=None, help="Path to second experiment JSON for comparison")
    args = parser.parse_args()

    # Load experiment
    with open(args.results, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Reconstruct minimal objects for analysis
    class SimpleObj:
        def __init__(self, d):
            for k, v in d.items():
                if isinstance(v, dict):
                    setattr(self, k, SimpleObj(v))
                elif isinstance(v, list) and v and isinstance(v[0], dict):
                    setattr(self, k, [SimpleObj(item) for item in v])
                else:
                    setattr(self, k, v)

    exp = SimpleObj(data)
    print(analyze_experiment(exp))
    print(test_context_length_hypothesis(exp))

    if args.compare:
        with open(args.compare, "r", encoding="utf-8") as f:
            data2 = json.load(f)
        exp2 = SimpleObj(data2)
        print(compare_conditions(exp, exp2))


if __name__ == "__main__":
    main()
