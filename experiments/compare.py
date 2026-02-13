"""
E₀ Cross-Condition Comparison
===============================
Loads multiple experiment results and generates publication-ready
comparison tables and statistical tests.

Usage:
    py -m experiments.compare \
        --e0 experiments/results/qm_derivation_e0/experiment_*.json \
        --null experiments/results/qm_derivation_null/experiment_*.json \
        --placebo experiments/results/qm_derivation_placebo/experiment_*.json \
        --inverted experiments/results/qm_derivation_inverted/experiment_*.json
"""

from __future__ import annotations

import json
import sys
import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from experiments.stats import (
    mean, std, bootstrap_ci, cohens_d, effect_size_label,
    permutation_test, monotonicity_score, kendall_tau,
    analyze_experiment, compare_conditions, test_context_length_hypothesis,
)


# ─────────────────────────────────────────────────────
# Simple object reconstruction from JSON
# ─────────────────────────────────────────────────────

class Obj:
    """Reconstruct nested objects from a JSON dict."""

    def __init__(self, d: dict):
        for k, v in d.items():
            if isinstance(v, dict):
                setattr(self, k, Obj(v))
            elif isinstance(v, list) and v and isinstance(v[0], dict):
                setattr(self, k, [Obj(item) for item in v])
            else:
                setattr(self, k, v)


def load_experiment(path: str) -> Obj:
    """Load an experiment JSON into an Obj."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Obj(data)


# ─────────────────────────────────────────────────────
# Publication-Ready Table
# ─────────────────────────────────────────────────────

def publication_table(experiments: Dict[str, Obj]) -> str:
    """
    Generate a Markdown table comparing all conditions.

    | Condition | Turn | R̄ [95% CI] | H̄ [95% CI] | Φ [95% CI] | v̄ [95% CI] |
    """
    lines = [
        "## Cross-Condition Comparison Table",
        "",
        "| Condition | Turn | R̄ [95% CI] | H̄ [95% CI] | Φ [95% CI] | v̄ [95% CI] |",
        "|-----------|------|-------------|-------------|------------|-------------|",
    ]

    for label, exp in experiments.items():
        runs = exp.runs
        if not runs:
            continue
        n_turns = len(runs[0].turns)

        for t in range(n_turns):
            R_vals = [r.turns[t].R_mean for r in runs if t < len(r.turns)]
            H_vals = [r.turns[t].H_mean for r in runs if t < len(r.turns)]
            Phi_vals = [float(r.turns[t].Phi) for r in runs if t < len(r.turns)]
            v_vals = [r.turns[t].v_mean for r in runs if t < len(r.turns)]

            R = bootstrap_ci(R_vals) if R_vals else (0, 0, 0)
            H = bootstrap_ci(H_vals) if H_vals else (0, 0, 0)
            Phi = bootstrap_ci(Phi_vals) if Phi_vals else (0, 0, 0)
            v = bootstrap_ci(v_vals) if v_vals else (0, 0, 0)

            lines.append(
                f"| {label} | {t+1} | "
                f"{R[0]:.4f} [{R[1]:.4f}, {R[2]:.4f}] | "
                f"{H[0]:.4f} [{H[1]:.4f}, {H[2]:.4f}] | "
                f"{Phi[0]:.0f} [{Phi[1]:.0f}, {Phi[2]:.0f}] | "
                f"{v[0]:.1f} [{v[1]:.1f}, {v[2]:.1f}] |"
            )

    lines.append("")
    return "\n".join(lines)


def pairwise_comparison_table(exp_e0: Obj, controls: Dict[str, Obj]) -> str:
    """
    Pairwise statistical comparison: E₀ vs each control.

    | Control | Turn | ΔR̄ | Cohen's d | p-value | Sig |
    """
    lines = [
        "## Pairwise Statistical Comparisons (E₀ vs Controls)",
        "",
        "| Comparison | Turn | R̄(E₀) | R̄(Control) | Cohen's d | Effect | p-value | Sig |",
        "|------------|------|--------|-------------|-----------|--------|---------|-----|",
    ]

    for ctrl_name, ctrl in controls.items():
        runs_e = exp_e0.runs
        runs_c = ctrl.runs
        n_turns = min(
            len(runs_e[0].turns) if runs_e else 0,
            len(runs_c[0].turns) if runs_c else 0,
        )

        for t in range(n_turns):
            R_e = [r.turns[t].R_mean for r in runs_e if t < len(r.turns)]
            R_c = [r.turns[t].R_mean for r in runs_c if t < len(r.turns)]

            m_e = mean(R_e)
            m_c = mean(R_c)
            d = cohens_d(R_e, R_c)
            p = permutation_test(R_e, R_c)
            sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"

            lines.append(
                f"| E₀ vs {ctrl_name} | {t+1} | "
                f"{m_e:.4f} | {m_c:.4f} | "
                f"{d:+.3f} | {effect_size_label(d)} | "
                f"{p:.4f} | {sig} |"
            )

    lines.append("")
    lines.append("Significance: *** p<0.001, ** p<0.01, * p<0.05, ns = not significant")
    lines.append("")
    return "\n".join(lines)


def trend_comparison_table(experiments: Dict[str, Obj]) -> str:
    """Compare R̄ trajectory trends across conditions."""
    lines = [
        "## R̄ Trajectory Trend Analysis",
        "",
        "| Condition | R̄ Trajectory | Mono | Kendall τ | Interpretation |",
        "|-----------|--------------|------|-----------|----------------|",
    ]

    for label, exp in experiments.items():
        runs = exp.runs
        if not runs:
            continue
        n_turns = len(runs[0].turns)

        R_traj = []
        for t in range(n_turns):
            vals = [r.turns[t].R_mean for r in runs if t < len(r.turns)]
            R_traj.append(mean(vals))

        mono = monotonicity_score(R_traj, "decreasing")
        tau = kendall_tau(R_traj)

        traj_str = " → ".join(f"{r:.4f}" for r in R_traj)

        if mono == 1.0 and tau < -0.8:
            interp = "Strong entailment cascade"
        elif mono > 0.5 and tau < -0.3:
            interp = "Partial cascade with breaks"
        elif abs(tau) < 0.3:
            interp = "No clear trend"
        else:
            interp = "Increasing (anti-entailment)"

        lines.append(
            f"| {label} | {traj_str} | {mono:.2f} | {tau:+.3f} | {interp} |"
        )

    lines.append("")
    return "\n".join(lines)


def full_report(experiments: Dict[str, Obj]) -> str:
    """Generate the complete cross-condition report."""
    parts = [
        "=" * 70,
        "  E₀ EXPERIMENT — CROSS-CONDITION ANALYSIS",
        "=" * 70,
        "",
    ]

    # Per-condition analysis
    for label, exp in experiments.items():
        parts.append(analyze_experiment(exp))

    # H₀ test per condition
    parts.append("## H₀ Tests: Context Length Effect")
    parts.append("")
    for label, exp in experiments.items():
        parts.append(f"### {label}")
        parts.append(test_context_length_hypothesis(exp))
        parts.append("")

    # Publication tables
    parts.append(publication_table(experiments))

    # Pairwise comparisons if E₀ condition exists
    if "E₀" in experiments:
        controls = {k: v for k, v in experiments.items() if k != "E₀"}
        parts.append(pairwise_comparison_table(experiments["E₀"], controls))

    # Trend analysis
    parts.append(trend_comparison_table(experiments))

    return "\n".join(parts)


# ─────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="E₀ Cross-Condition Comparison",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--e0", help="Path to E₀-initialized experiment JSON")
    parser.add_argument("--null", help="Path to null control experiment JSON")
    parser.add_argument("--placebo", help="Path to placebo control experiment JSON")
    parser.add_argument("--inverted", help="Path to inverted control experiment JSON")
    parser.add_argument("--output", default=None, help="Save report to file")

    args = parser.parse_args()

    experiments = {}
    if args.e0:
        experiments["E₀"] = load_experiment(args.e0)
    if args.null:
        experiments["Null"] = load_experiment(args.null)
    if args.placebo:
        experiments["Placebo"] = load_experiment(args.placebo)
    if args.inverted:
        experiments["Inverted"] = load_experiment(args.inverted)

    if not experiments:
        print("Error: Provide at least one experiment result with --e0, --null, --placebo, or --inverted")
        sys.exit(1)

    report = full_report(experiments)
    print(report)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\nReport saved to: {args.output}")


if __name__ == "__main__":
    main()
