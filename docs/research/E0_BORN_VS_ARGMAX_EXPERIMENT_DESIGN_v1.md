# E₀ — Argmax vs Born Sampling Experiment Design

**Status:** Experimental Protocol — **Executed (Path H, commit `b3ac2c3`)**  
**Date:** 2026-03-25  
**Purpose:** Empirically evaluate deterministic vs stochastic realization regimes

> **Note (2026-03-25):** This experiment has been implemented and executed as
> Path H. Results: 27 tests in `test_born_sampling.py`, Claim C22 in
> `E0_TEST_REGISTRY_v2.md`. Key finding: geometry choice dominates over
> decision rule choice. See ADR-0007-v1 for the updated architecture decision.

---

## 1. Objective

Compare two decision rules on identical domains:

- Deterministic: argmax(I)
- Stochastic: sample(P), with P ∝ I

The goal is NOT to replace the controller, but to understand:

> When does sampling add value — and when does it degrade structure?

---

## 2. Experimental Setup

### Shared Components

- Same Landscape
- Same Ψ(p) definition
- Same Θ and ω
- Same horizon
- Same historization state

Only difference:

Decision rule

---

## 3. Decision Modes

### Mode A — Deterministic

select(y) = argmax I(y)

---

### Mode B — Born Sampling

P(y) = I(y) / Σ I
select(y) ~ P

Run multiple trials per state.

---

## 4. Domains

Run experiments on:

### 4.1 Gordian Trap
- Measure trap avoidance rate

### 4.2 Multi-Goal (G5)
- Measure goal distribution
- Rescue stability

### 4.3 Resonator Domain
- Measure classification outcome stability

### 4.4 Random Topology Scan
- Compare override frequency

---

## 5. Metrics

### 5.1 Success Rate
- % reaching correct outcome

### 5.2 Stability
- variance of outcomes

### 5.3 Coherence Loss
- cases where sampling selects low-support branch

### 5.4 Efficiency
- steps to goal

### 5.5 Distribution Shape
- entropy of P

---

## 6. Expected Outcomes

Hypothesis:

- argmax → stable, high performance
- sampling → higher variance
- sampling may help in flat distributions

---

## 7. Analysis Plan

For each domain:

- run N=100–1000 trials (sampling)
- compare with deterministic baseline
- compute metrics

---

## 8. Interpretation

Possible results:

### Case 1 — argmax dominates
→ keep deterministic controller

### Case 2 — sampling beneficial in specific regimes
→ activate selectively

### Case 3 — sampling degrades performance
→ restrict to analysis only

---

## 9. Key Question

> Is Born sampling a control improvement, or only a realization description?

---

## 10. Output

- tables per domain
- variance plots
- success comparisons

---

_End of document._