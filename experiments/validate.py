"""Quick validation of experiments module."""
import json
from pathlib import Path

# Test imports
from experiments.runner import (
    ExperimentRunner, compute_turn_metrics,
    TurnMetrics, RunResult, ExperimentResult,
)
print("runner.py imports: OK")

from experiments.stats import (
    bootstrap_ci, cohens_d, permutation_test, effect_size_label,
    monotonicity_score, kendall_tau, analyze_experiment, compare_conditions,
)
print("stats.py imports: OK")

# Bootstrap CI
vals = [0.050, 0.036, 0.018, 0.041]
m, lo, hi = bootstrap_ci(vals)
print(f"Bootstrap CI for QM R trajectory: {m:.4f} [{lo:.4f}, {hi:.4f}]")

# Monotonicity
print(f"Monotonicity (decreasing): {monotonicity_score(vals, 'decreasing'):.2f}")
print(f"Kendall tau: {kendall_tau(vals):.3f}")

# Cohen's d
g1 = [0.050, 0.036, 0.018, 0.041]  # E0-primed
g2 = [0.092, 0.088, 0.082, 0.081]  # hypothetical control
d = cohens_d(g1, g2)
print(f"Cohen d (E0 vs Control example): {d:+.3f} ({effect_size_label(d)})")

# Permutation test
p = permutation_test(g1, g2)
print(f"Permutation test p-value: {p:.4f}")

# Config loading
configs_dir = Path("experiments/configs")
for cfg_file in sorted(configs_dir.glob("*.json")):
    with open(cfg_file, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    sp = "yes" if cfg.get("system_prompt") else "null"
    ni = len(cfg.get("initialization_prompts", []))
    nt = len(cfg.get("test_prompts", []))
    print(f"  {cfg_file.name}: condition={cfg['condition']}, sys={sp}, init={ni}, test={nt}")

print("\nAll validations passed.")
