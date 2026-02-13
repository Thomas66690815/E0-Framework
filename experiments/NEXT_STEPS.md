# Next Steps — Experiment Execution Plan

**Status:** Ready to execute. All configs verified, all infrastructure tested.  
**Last commit:** 4e6429d (all analysis tools + PROTOCOL.md committed & pushed)  
**Date:** Created at context window transition point.

---

## 1. Current State

### Completed Experiments

| Condition | N | R̄ trajectory | τ (monotonicity) | Baseline RMSE/R̄ |
|-----------|---|---------------|-------------------|-------------------|
| **E₀** | 10 | 0.1013 → 0.0698 → 0.0600 → 0.0460 | -1.0 (perfect) | 9.94% |
| **Null** | 1 | 0.1913 → 0.0837 → 0.0716 → 0.0540 | -1.0 (perfect) | 17.83% |

### Key Finding So Far
- E₀ has ~50% lower R̄ at Step 1 (0.101 vs 0.191)
- Both show perfectly monotonic decrease
- Exponential decay (context-length H₀) borderline explains E₀ data
- **Cannot yet distinguish content-specific effect from general priming effect**

---

## 2. Execution Plan — Priority Order

### Test 1: Placebo Control (ZFC) — THE Critical Test

```powershell
py -m experiments.runner --config experiments/configs/qm_derivation_placebo.json --runs 10 --api-key tgp_v1_R1XR-G9FNbDCsmsxW1mBKwIzKFCA1wfAta0kE4sXwg0 --analyze
```

**Why first:** This is the single most important remaining test. It discriminates between:
- H₀: "Any axiomatic priming reduces R̄" → R̄(Placebo) ≈ R̄(E₀)
- H₁: "E₀ content specifically helps" → R̄(Placebo) >> R̄(E₀) or R̄(Placebo) ≈ R̄(Null)

**Estimated runtime:** ~30-45 min (10 runs × 6 turns × ~30s/turn)

### Test 2: Null Control N=10

```powershell
py -m experiments.runner --config experiments/configs/qm_derivation_null.json --runs 10 --api-key tgp_v1_R1XR-G9FNbDCsmsxW1mBKwIzKFCA1wfAta0kE4sXwg0 --analyze
```

**Why:** Currently only N=1. Need N=10 for proper confidence intervals and effect size calculations.

**Note:** This will create a NEW results directory. The old N=1 result is in `experiments/results/qm_derivation_null/`. The runner creates timestamped directories, so no conflict.

### Test 3: Inverted Control N=10

```powershell
py -m experiments.runner --config experiments/configs/qm_derivation_inverted.json --runs 10 --api-key tgp_v1_R1XR-G9FNbDCsmsxW1mBKwIzKFCA1wfAta0kE4sXwg0 --analyze
```

**Why:** Tests coherence specificity. E₀ priming + thermodynamics (not QM) test prompts.  
If R̄(Inverted) ≈ R̄(E₀) → E₀ priming helps any derivation (general effect)  
If R̄(Inverted) >> R̄(E₀) → E₀ helps specifically with E₀-coherent tasks

---

## 3. After All 4 Conditions Complete

### Cross-Condition Comparison

```powershell
py -m experiments.compare --e0 experiments/results/qm_derivation_e0/experiment_*.json --null experiments/results/qm_derivation_null/experiment_*.json --placebo experiments/results/qm_derivation_placebo/experiment_*.json --inverted experiments/results/qm_derivation_inverted/experiment_*.json --output experiments/results/comparison_report.txt
```

### Baseline Analysis Per Condition

```powershell
# Find each condition's summary.csv and run baseline
py experiments/baseline.py experiments/results/qm_derivation_placebo/summary.csv
py experiments/baseline.py experiments/results/qm_derivation_null/summary.csv  
py experiments/baseline.py experiments/results/qm_derivation_inverted/summary.csv
```

---

## 4. Decision Tree After Results

```
IF R̄(Placebo) ≈ R̄(Null) >> R̄(E₀):
    → Content-specific effect confirmed
    → E₀ initialization produces measurably different behavior
    → Proceed to: gravity derivation, cross-model replication

IF R̄(Placebo) ≈ R̄(E₀) << R̄(Null):
    → Any axiomatic priming reduces R̄ equally
    → Effect is priming/context, not E₀-specific
    → Report honestly, adjust interpretation

IF R̄(Null) ≈ R̄(E₀) ≈ R̄(Placebo):
    → No detectable effect beyond context length
    → Exponential decay explains everything
    → Report as negative result

IF R̄(Inverted) ≈ R̄(E₀) (both low):
    → E₀ priming helps any derivation generically
    → Not content-specific coherence, just a good prompt

IF R̄(Inverted) >> R̄(E₀):
    → Coherence matters: E₀ helps QM specifically
    → Strongest evidence for content-specific structural effect
```

---

## 5. Future Experiments (After Core Battery)

| Experiment | Config | Purpose |
|------------|--------|---------|
| Gravity derivation | `gravity_derivation_e0.json` | Different derivation domain, same E₀ priming |
| Cross-model | Create new configs with different model IDs | Replication across architectures |
| Temperature sweep | Modify configs with temperature 0.3, 0.7, 1.0 | R̄ sensitivity to sampling |
| Order permutation | Configs with shuffled test_prompts order | Test step-order dependence |

---

## 6. Technical Reference

- **Python:** `py` command → C:/Python312/python.exe (3.12.4)
- **API:** Together AI, key in commands above
- **Model:** meta-llama/Llama-3.3-70B-Instruct-Turbo
- **Results directory:** `experiments/results/` (gitignored)
- **All analysis tools:** `experiments/analyze_results.py`, `experiments/baseline.py`, `experiments/compare.py`, `experiments/stats.py`
- **Protocol:** `experiments/PROTOCOL.md`

---

## 7. Important Design Note

All 4 QM conditions use **identical test prompts** (all reference "E₀ primitives").  
Only the initialization differs (system prompt + init prompts).  
This is intentional — it isolates the initialization variable.

The placebo (ZFC) condition is primed with set theory but asked about E₀ primitives it doesn't have.  
The null condition has no priming at all.  
The difference in how the model handles being asked about E₀ without E₀ context vs. with E₀ context vs. with ZFC context is exactly what we're measuring.
