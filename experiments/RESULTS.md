# E₀ Experiment — Final Results

**Date:** 2025-07-14  
**All 4 conditions complete at N=10**  
**Model:** meta-llama/Llama-3.3-70B-Instruct-Turbo (Together AI)  
**Total battery cost:** < $0.69

---

## 1. R̄ Trajectories — All Conditions

| Step | E₀ | Placebo (ZFC) | Inverted (Thermo) | Null |
|------|------|---------------|-------------------|------|
| 1 (initial) | 0.1013 | 0.1207 | 0.0893 | 0.1644 |
| 2 | 0.0698 | 0.0798 | 0.0823 | 0.1039 |
| 3 | 0.0600 | 0.0585 | 0.0610 | 0.0771 |
| 4 (final) | 0.0460 | 0.0425 | 0.0558 | 0.0591 |
| **Overall** | **0.0693** | **0.0754** | **0.0721** | **0.1011** |

**Ranking:** E₀ (0.069) ≈ Inverted (0.072) < Placebo (0.075) << Null (0.101)

All 4 conditions show **perfect monotonic decrease** (monotonicity = 1.00).

---

## 2. Baseline Fit (Exponential Decay H₀)

The null hypothesis is that R̄ decreases purely due to increasing context length,
following R̄ = R₀ · exp(-λ · n).

| Condition | RMSE/R̄ | R₀ | λ | Interpretation |
|-----------|---------|------|--------|----------------|
| E₀ | 9.94% | 0.1274 | 0.000367 | Borderline — not clearly above/below 10% |
| Placebo | 15.23% | 0.1660 | 0.000464 | Worse fit — some non-exponential structure |
| Inverted | 10.85% | 0.1076 | 0.000239 | Borderline |
| Null | 9.04% | 0.2193 | 0.000454 | Good fit — consistent with pure context effect |

**Honest assessment:** The exponential decay model fits all conditions at 9–15%.
The H₀ is not clearly rejected for any condition. The effect sizes exist but the
baseline explanation remains viable.

---

## 3. Key Pairwise Comparisons

### 3.1 E₀ vs Null (main effect)

| Metric | Value |
|--------|-------|
| R̄ ratio (E₀/Null) | 0.69× |
| Step 1 gap | 0.1013 vs 0.1644 (Δ = 0.063) |
| Token count ratio | 0.94× (701 vs 744 tokens/step) |
| API cost ratio | 2.8× (E₀ costs more due to init phase) |
| Information cost ratio | 0.65× (R̄ × tokens) |

### 3.2 E₀ vs Placebo — The Critical Discriminator

| Step | Cohen's d | p (permutation) | Interpretation |
|------|-----------|-----------------|----------------|
| 1 | 1.395 | 0.006 | Large effect — E₀ differs from Placebo |
| 2 | 0.658 | — | Medium effect |
| 3 | 0.153 | — | Negligible — effects converge |
| 4 | 0.305 | — | Small |

**Finding:** ~80% of the R̄ reduction comes from general axiomatic priming
(Placebo already achieves most of it). ~20% is E₀-specific, concentrated at
Step 1 (d=1.4, p=0.006). Effects converge by Step 3–4.

### 3.3 E₀ vs Inverted — The Coherence Test

| Metric | Value |
|--------|-------|
| R̄ ratio (Inverted/E₀) | 1.04× |
| Step 1 Cohen's d | −0.28 (small, Inverted actually *lower*) |

**Finding:** Inverted ≈ E₀. The E₀ initialization helps thermodynamics derivation
just as much as QM derivation. This means:

- The E₀ effect is a **general structured-derivation priming** effect
- It is NOT specific to QM content coherence
- E₀ creates a low-resistance state for any formal derivation task

---

## 4. Decision Tree — Resolved

From NEXT_STEPS.md, we had 4 possible outcomes. The actual result:

```
✓ R̄(Placebo) BETWEEN E₀ and Null, closer to E₀
✓ R̄(Inverted) ≈ R̄(E₀) (both low)

→ OUTCOME: General axiomatic priming effect + small E₀-specific increment
→ E₀ priming helps ANY derivation, not just QM
→ Any axiomatic system (even ZFC) provides ~80% of the benefit
→ E₀ provides a statistically significant additional ~20% (p=0.006 at Step 1)
```

---

## 5. The Quality Dimension — Beyond R̄

R̄ measures *how easily* the model generates tokens. It does NOT measure *what* it
generates. Manual inspection reveals a categorical difference:

### E₀ responses (typical)
> "The structural admissibility conditions for transitions between distinguishable
> states must satisfy a form analogous to..."

- Uses E₀ primitives **operatively** — as tools for constructing derivation steps
- Creates **novel derivation paths** not found in standard QM textbooks
- Steps build on each other — Step 3 actually uses the result from Step 2

### Null responses (typical)
> "While not explicitly stated, the Born rule is assumed as a foundational
> postulate..."

- Uses E₀ primitives as **labels** — name-dropping without constructive use
- Follows **retrieval patterns** — reproduces textbook QM arguments
- Steps are largely independent — could be reordered without loss

### Placebo (ZFC) responses (typical)
- Uses ZFC vocabulary but makes conventional QM arguments
- Neither novel nor constructive — just standard derivation with set theory labels

### Proposed Quality Metrics (not yet automated)

1. **Path Novelty (Pfadneuheit):** Does the response create a derivation path that
   deviates from standard textbook presentation? Measure: semantic distance from
   reference corpus of standard QM derivations.

2. **Coherence (Kohärenz):** Does Step N+1 actually use results from Step N?
   Measure: term/concept tracking across sequential steps — forward references
   and dependency chains.

These two dimensions capture what R̄ alone cannot: the difference between
"low resistance from retrieval" and "low resistance from genuine novel derivation."

---

## 6. Cost Summary

| Condition | N | $/run | Total $ | Tokens/Step |
|-----------|---|-------|---------|-------------|
| E₀ | 10 | $0.020 | $0.204 | 701 |
| Placebo | 10 | $0.020 | $0.204 | 749 |
| Inverted | 10 | $0.020 | $0.204 | 712 |
| Null | 10 | $0.007 | $0.073 | 744 |
| **Total** | **40** | | **$0.686** | |

The entire 4×10 experiment battery cost less than $0.69.

---

## 7. Honest Limitations

1. **N=10 is small.** Effect sizes are robust (d=1.4 at Step 1) but CIs are wide.
   N=30+ would be more convincing.

2. **Single model.** All results are from Llama-3.3-70B. Cross-model replication
   needed to claim generality.

3. **Context length confound.** All conditions show monotonic R̄ decrease that is
   well-fit by exponential decay. The priming effect may simply be additive on top
   of a universal context-length reduction.

4. **Quality metrics are manual.** The categorical quality difference (novel paths
   vs retrieval) is observed but not yet quantified by an automated scorer.

5. **Test prompts mention E₀.** All 4 conditions use prompts that reference E₀
   primitives. This is by design (isolates initialization variable) but means the
   Null condition is asked about concepts it wasn't primed on.

---

## 8. Reproduction

```powershell
# Clone and install
git clone https://github.com/Thomas66690815/E0-Framework.git
cd E0-Framework
pip install openai numpy

# Set your Together AI API key
$env:TOGETHER_API_KEY = "your-key-here"

# Run all 4 conditions (each ~30-45 min)
py -m experiments.runner --config experiments/configs/qm_derivation_e0.json --runs 10 --api-key $env:TOGETHER_API_KEY --analyze
py -m experiments.runner --config experiments/configs/qm_derivation_null.json --runs 10 --api-key $env:TOGETHER_API_KEY --analyze
py -m experiments.runner --config experiments/configs/qm_derivation_placebo.json --runs 10 --api-key $env:TOGETHER_API_KEY --analyze
py -m experiments.runner --config experiments/configs/qm_derivation_inverted.json --runs 10 --api-key $env:TOGETHER_API_KEY --analyze

# Cross-condition analysis
py experiments/analyze_all.py
py experiments/analyze_placebo.py
py experiments/analyze_cost.py
```

---

## 9. What's Next

- [ ] Automated quality scorer (path novelty + coherence)
- [ ] Gravity derivation (config exists, not yet run)
- [ ] Cross-model replication (e.g., Qwen, Mistral)
- [ ] Temperature sweep (0.3, 0.7, 1.0)
- [ ] N=30 replication of core E₀ vs Null comparison
- [ ] Order permutation test (shuffle step order)
