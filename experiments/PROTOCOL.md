# E₀ Experiment Protocol
## Token-Level Structural Analysis of Guided Axiomatic Derivation in LLMs

**Version:** 1.0  
**Date:** 2026-02-13  
**Authors:** Thomas / Copilot (Human-Synthetic Partnership)  
**Status:** First reproducible experimental framework — no prior work exists

---

## 1. What This Is (and Is Not)

This protocol describes **how to measure and reproduce behavioral patterns** in large
language models when guided through axiomatic derivation sequences.

**This is NOT:**
- A claim that E₀ is physics
- A claim that LLMs "understand" axioms
- A claim that token probabilities reveal consciousness

**This IS:**
- An empirical observation protocol
- A set of reproducible measurements
- Material for independent verification

**Core question:** When an LLM is primed with a minimal axiomatic system (E₀) and
then asked to perform stepwise derivations, does its token-level behavior show
patterns that differ from unprimed or differently-primed models — and if so, are
those patterns consistent, reproducible, and distinguishable from pure
context-length effects?

---

## 2. Measured Quantities

All measurements are derived from the model's own logprob output. No external
labels or human judgments are involved.

| Symbol | Name | Formula | What It Captures |
|--------|------|---------|------------------|
| R | Resistance | R = -log(p) for selected token | Structural inertia of a token choice |
| R̄ | Mean Resistance | average of R across all tokens | Overall "difficulty" of a response |
| H | Entropy | H = -Σ pᵢ log(pᵢ) over top-k logprobs | Uncertainty at each position |
| H̄ | Mean Entropy | average of H | Overall uncertainty |
| Φ | Reconfiguration Count | # sign changes in ΔH | Structural oscillation in the response |
| v | Velocity | v = 1/R | Inverse resistance — "flow rate" |
| v̄ | Mean Velocity | average of v | Overall flow |

**All metrics are computed from the same raw data: per-token logprobs returned by
the API.** No interpretation layer is added. The numbers are what the model reports.

---

## 3. Experimental Conditions

### 3.1 Main Condition: E₀-Initialized (qm_derivation_e0)

```
System Prompt → E₀ structural primer
Init Phase    → E₀ Canon + Ontodynamics text (NOT measured)
Test Phase    → 4 stepwise QM derivation prompts (MEASURED)
```

### 3.2 Null Control (qm_derivation_null)

```
System Prompt → none
Init Phase    → none
Test Phase    → identical 4 QM derivation prompts (MEASURED)
```

### 3.3 Placebo Control (qm_derivation_placebo)

```
System Prompt → ZFC set theory primer (same structural position)
Init Phase    → ZFC axioms + math structures (same # tokens, different content)
Test Phase    → identical 4 QM derivation prompts (MEASURED)
```

### 3.4 Inverted Control (qm_derivation_inverted)

```
System Prompt → E₀ structural primer (identical to main)
Init Phase    → E₀ Canon + Ontodynamics (identical to main)
Test Phase    → 4 THERMODYNAMICS prompts instead of QM (MEASURED)
```

**Logic of controls:**
- Null tests: "Is R̄ decrease just context-length?"
- Placebo tests: "Is R̄ decrease just any-axioms-help?"
- Inverted tests: "Is R̄ decrease specific to coherent E₀→QM path?"

---

## 4. What Would a Purely Probabilistic System Show?

This is the critical scientific question. If the model is "just predicting tokens"
with no structural integration of the axiomatic content, we would expect:

### 4.1 The Null Hypothesis (H₀)

**H₀: All observed R̄ patterns are caused by context-window effects, not by
structural integration of E₀ content.**

Specifically, H₀ predicts:

| Prediction | Reasoning |
|------------|-----------|
| R̄ decreases monotonically in ALL conditions | Longer context → more priming → lower R̄ always |
| R̄ trajectory shape is IDENTICAL across conditions | Content doesn't matter, only token count |
| Null control R̄ ≈ E₀ R̄ at same token position | No privileged initialization |
| Placebo R̄ ≈ E₀ R̄ | Any axioms work equally well |
| Inverted R̄ ≈ Main R̄ | E₀ priming helps regardless of test content |
| Φ (reconfigurations) is CONSTANT across steps | No structural learning |
| No identifiable "derivation hotspots" in token trace | Flow is uniform |

### 4.2 Expected Probabilistic Baseline Behavior

For a purely probabilistic token predictor, we expect:

**R̄ as a function of context position:**

```
R̄(n) ≈ R₀ · f(n)

where:
  R₀  = base resistance (model-dependent, ~0.1–0.2 for Llama 70B)
  n   = cumulative token position in context window
  f(n) = monotonically decreasing function of n
```

The function f(n) decreases because:
1. **Attention saturation:** More context → more relevant tokens to attend to → 
   higher confidence → lower R
2. **Vocabulary narrowing:** Each response constrains the semantic field → 
   subsequent responses have fewer "surprising" tokens
3. **Repetition priming:** Technical terms introduced early become low-R in 
   later responses (pure statistical effect)
4. **KV-cache accumulation:** The model literally has more "memory" as context 
   grows, leading to more predictable outputs

**This is a real, measurable, well-understood effect.** It is NOT evidence of
structural integration. Any multi-turn conversation will show R̄ decrease.

### 4.3 What Would Distinguish Structural Integration from Context Effects?

If E₀ produces genuine structural effects beyond pure statistics, we should see:

| Observable | Probabilistic (H₀) | Structural (H₁) |
|------------|--------------------|--------------------|
| R̄(E₀) vs R̄(Null) | Same trajectory, shifted by init tokens | Different SHAPE, not just offset |
| R̄(E₀) vs R̄(Placebo) | Same (any axioms help equally) | E₀ lower (specific content matters) |
| R̄(Inverted) | Same as Main (priming helps regardless) | Higher (wrong test content breaks coherence) |
| Φ across steps | Constant or random | Decreasing (structural consolidation) |
| Token-level hotspots | Random distribution | Clustered at derivation-critical transitions |
| R̄ step-to-step variance | Constant | Decreasing (convergence) |

### 4.4 The Critical Test

**The one test that would falsify H₀ definitively:**

> If R̄(E₀) < R̄(Placebo) at the SAME context position, with the SAME number 
> of initialization tokens, then content matters — not just context length.

This is why the placebo control is designed to have approximately the same number
of initialization tokens as the E₀ condition, but with ZFC content instead.

---

## 5. First Results (N=10, E₀ condition)

### 5.1 R̄ Trajectory (10 runs, temp=0)

| Step | Content | R̄ | 95% CI | Φ | 95% CI |
|------|---------|------|--------|-----|--------|
| 1 | Complex States (ℂ) | 0.1013 | [0.0941, 0.1091] | 498 | [470, 528] |
| 2 | Superposition | 0.0698 | [0.0629, 0.0755] | 503 | [471, 533] |
| 3 | Born Rule | 0.0600 | [0.0536, 0.0659] | 447 | [426, 470] |
| 4 | Unitarity | 0.0460 | [0.0420, 0.0505] | 412 | [396, 429] |

**Monotonicity: 1.00 (all 10 runs show R̄ strictly decreasing)**  
**Kendall's τ: -1.000**

### 5.2 Comparison with Null Control (N=1)

| Step | E₀ (N=10) | Null (N=1) | Ratio |
|------|-----------|------------|-------|
| 1 | 0.1013 | 0.1913 | 0.53x |
| 2 | 0.0698 | 0.0837 | 0.83x |
| 3 | 0.0600 | 0.0716 | 0.84x |
| 4 | 0.0460 | 0.0540 | 0.85x |

**Key observation:** E₀ initialization produces 47% lower R̄ at Step 1, but the
advantage narrows to 15% by Step 4. The NULL control also shows perfectly 
monotonic R̄ decrease (τ = -1.0). This is CONSISTENT with H₀ — context length
alone produces the same qualitative pattern.

### 5.3 What Remains To Be Tested

- [ ] Null control with N=10 (currently N=1)
- [ ] Placebo control (ZFC) — THE critical discriminator
- [ ] Inverted control — coherence test
- [ ] Cross-model replication (different LLM families)
- [ ] Temperature sweep (0, 0.3, 0.7, 1.0)
- [ ] Order permutation (Steps in different sequence)

---

## 6. How To Reproduce

### 6.1 Prerequisites

```
Python >= 3.10
pip install openai
API key for Together AI (or any OpenAI-compatible endpoint)
```

### 6.2 Run the Main Experiment

```bash
# E₀-initialized QM derivation (10 runs, ~15 min)
py -m experiments.runner \
    --config experiments/configs/qm_derivation_e0.json \
    --runs 10 \
    --api-key YOUR_KEY \
    --analyze

# Null control
py -m experiments.runner \
    --config experiments/configs/qm_derivation_null.json \
    --runs 10 \
    --api-key YOUR_KEY \
    --analyze

# Placebo control (ZFC)
py -m experiments.runner \
    --config experiments/configs/qm_derivation_placebo.json \
    --runs 10 \
    --api-key YOUR_KEY \
    --analyze

# Inverted control (E₀ + thermodynamics)
py -m experiments.runner \
    --config experiments/configs/qm_derivation_inverted.json \
    --runs 10 \
    --api-key YOUR_KEY \
    --analyze
```

### 6.3 Compare Conditions

```bash
py -m experiments.compare \
    --e0 experiments/results/qm_derivation_e0/experiment_*.json \
    --null experiments/results/qm_derivation_null/experiment_*.json \
    --placebo experiments/results/qm_derivation_placebo/experiment_*.json \
    --inverted experiments/results/qm_derivation_inverted/experiment_*.json \
    --output experiments/results/comparison_report.txt
```

### 6.4 Output Files

Each experiment produces:
- `run_NNN_turns.csv` — per-turn metrics for each run
- `run_NNN_tokens.csv` — per-token trace for each run
- `summary.csv` — all runs aggregated
- `experiment_HASH.json` — full results including response texts

---

## 7. For Independent Researchers

### 7.1 What We Provide

1. **Complete experiment configs** — exact prompts, exact model settings
2. **Runner code** — automated execution with metric capture
3. **Statistics code** — bootstrap CIs, effect sizes, permutation tests
4. **Comparison tools** — cross-condition analysis
5. **Our raw results** — for validation

### 7.2 What We Ask

1. Run the full protocol (all 4 conditions, N≥10 each)
2. Report your raw numbers alongside ours
3. If your results differ, report that — negative results are valuable
4. Try different models (GPT-4, Claude, Mixtral, etc.)
5. Try the order-permutation variant (Steps in 3→1→4→2 order)

### 7.3 Minimum Viable Replication

If you can only run one test, run this:

```bash
# E₀ condition
py -m experiments.runner --config experiments/configs/qm_derivation_e0.json --runs 3 --api-key YOUR_KEY

# Null control  
py -m experiments.runner --config experiments/configs/qm_derivation_null.json --runs 3 --api-key YOUR_KEY
```

Then compare the R̄ trajectories. If E₀ shows consistently lower R̄ at Step 1,
the E₀ initialization effect is real. If the trajectories are identical,
it's a context-length artifact.

---

## 8. Intellectual Honesty Checklist

Before claiming any result, verify:

- [ ] Is the pattern present in ALL runs, not just cherry-picked ones?
- [ ] Does the NULL control show the SAME pattern? (If yes → context artifact)
- [ ] Does the PLACEBO control show the SAME pattern? (If yes → any-axioms effect)
- [ ] Is the effect size (Cohen's d) at least "medium" (|d| ≥ 0.5)?
- [ ] Is the permutation test p-value < 0.05?
- [ ] Have you checked for order effects by permuting the test sequence?
- [ ] Have you tried a different model to rule out model-specific artifacts?

**If any of these fail, the result is inconclusive.** Report it anyway.

---

## 9. File Structure

```
experiments/
├── configs/                    # Experiment definitions
│   ├── qm_derivation_e0.json       # Main condition
│   ├── qm_derivation_null.json     # Null control
│   ├── qm_derivation_placebo.json  # Placebo (ZFC)
│   ├── qm_derivation_inverted.json # Inverted (E₀ + thermo)
│   └── gravity_derivation_e0.json  # Extension: gravity
├── runner.py                   # Experiment execution
├── stats.py                    # Statistical analysis
├── compare.py                  # Cross-condition comparison
├── validate.py                 # Module validation
├── analyze_results.py          # Quick results analysis
└── results/                    # Output (gitignored, regenerable)
    ├── qm_derivation_e0/
    ├── qm_derivation_null/
    └── ...
```

---

## 10. Version History

| Date | Change |
|------|--------|
| 2026-02-13 | v1.0 — Initial protocol, 4 conditions, N=10 E₀ results |
