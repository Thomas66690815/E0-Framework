# Next Steps — Experiment Execution Plan

**Status:** ✅ ALL 4 CONDITIONS COMPLETE AT N=10. See RESULTS.md for final numbers.  
**Last commit:** 5fb1672 (analyze_all.py updated for Null N=10)  
**Date:** Updated 2025-07-14

---

## 1. Current State

### Completed Experiments

| Condition | N | R̄ trajectory | τ (monotonicity) | Baseline RMSE/R̄ |
|-----------|---|---------------|-------------------|-------------------|
| **E₀** | 10 | 0.1013 → 0.0698 → 0.0600 → 0.0460 | -1.0 (perfect) | 9.94% |
| **Placebo (ZFC)** | 10 | 0.1207 → 0.0798 → 0.0585 → 0.0425 | -1.0 (perfect) | 15.23% |
| **Inverted (Thermo)** | 10 | 0.0893 → 0.0823 → 0.0610 → 0.0558 | -1.0 (perfect) | 10.85% |
| **Null** | 10 | 0.1644 → 0.1039 → 0.0771 → 0.0591 | -1.0 (perfect) | 9.04% |

### Key Findings
- **Ranking:** E₀ (0.069) ≈ Inverted (0.072) < Placebo (0.075) << Null (0.101)
- ~80% of R̄ reduction comes from general axiomatic priming (Placebo achieves most of it)
- ~20% is E₀-specific (Cohen's d=1.4, p=0.006 at Step 1)
- E₀ priming is a **general** effect — helps thermodynamics as much as QM
- **Categorical quality difference** observed but not yet automated: E₀ produces novel derivation paths, Null produces retrieval

---

## 2. Remaining Work — Priority Order

### ✅ Test 1: Placebo Control (ZFC) — COMPLETE
N=10 done. Result: R̄ = 0.0754 (between E₀ and Null, closer to E₀).

### ✅ Test 2: Null Control N=10 — COMPLETE
N=10 done. Result: R̄ = 0.1011.

### ✅ Test 3: Inverted Control N=10 — COMPLETE
N=10 done. Result: R̄ = 0.0721 (≈ E₀, E₀ helps any derivation).

### Next: Quality Scorer — PATH NOVELTY + COHERENCE

R̄ alone cannot distinguish "low resistance from retrieval" from "low resistance
from a genuinely new derivation path." Two quality dimensions need automated scoring:

1. **Pfadneuheit (Path Novelty):** Does the model produce derivation steps not found
   in standard textbook presentations? Semantic distance metric.

2. **Kohärenz (Coherence):** Does Step N+1 operatively use results from Step N?
   Term/concept dependency tracking across steps.

---

## 3. After Quality Scorer — Future Experiments

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

## 4. Decision Tree — RESOLVED

```
ACTUAL OUTCOME:
  R̄(E₀) ≈ R̄(Inverted) < R̄(Placebo) << R̄(Null)
  
→ ✓ R̄(Inverted) ≈ R̄(E₀) — E₀ priming helps ANY derivation generically
→ ✓ R̄(Placebo) between E₀ and Null — any axiomatic priming helps, E₀ adds ~20%
→ The BIGGER story is qualitative: E₀ enables novel derivation paths (not captured by R̄)
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
