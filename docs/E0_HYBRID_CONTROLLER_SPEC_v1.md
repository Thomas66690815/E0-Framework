# E₀ Hybrid Controller Specification v1

**Status:** Draft (operational)  
**Date:** 2026-03-24  
**Purpose:** Define the behavior, guarantees, limits, and metrics of the E₀ hybrid controller.

---

## 1. Overview

The E₀ controller operates in two modes:

- **GREEDY** — selects the action with minimal local structural burden
- **AMPLITUDE_ON_DISAGREE** — compares greedy choice with amplitude-based path-family support and may override

The hybrid controller does **not** replace the greedy controller.  
It augments it with a second evaluation regime.

---

## 2. Core decision pipeline

At each decision step:

1. Enumerate admissible actions `A = {a1, a2, ...}`
2. Compute local burden for each action:

   `S(a) = Δ(a) · R_eff(a)`

3. Select greedy action:

   `a_greedy = argmin_a S(a)`

4. Compute amplitude support for each action over bounded horizon `h`:

   `Ψ(p) = exp(-S(p)) · exp(i Θ(p))`

   `I(a) = | Σ_{p ∈ Paths(a, h)} Ψ(p) |²`

   `P(a) = I(a) / Σ I(a')`

5. Select amplitude action:

   `a_amp = argmax_a P(a)`

6. Arbitration:

   - if `a_greedy == a_amp` → select `a_greedy`
   - if `a_greedy != a_amp` → apply hybrid policy

---

## 3. Hybrid arbitration policy

### Mode: AMPLITUDE_ON_DISAGREE

If `a_greedy != a_amp`:

- select `a_amp`
- record override event

### Safety conditions

The hybrid layer must **not override** when:

- action leads to escalation state
- no admissible continuation exists
- amplitude computation is invalid or incomplete

---

## 4. Metrics

The following runtime metrics must be tracked:

- `hybrid_override_count`
- `hybrid_override_rate`
- `agreement_rate`
- `avg_horizon`

Optional (future):

- `avg_intensity_gap`
- `trap_escape_events`

---

## 5. Summation geometry

The amplitude layer depends on summation geometry.

Currently supported:

- `prefix`
- `simple` (default)
- `first_arrival` (experimental)

### Current status

- `simple` is empirically most stable
- `prefix` overcounts recursive paths
- `first_arrival` requires further validation

---

## 6. Known limitations

- Path enumeration is exponential in horizon (`O(k^h)`)
- Phase `Θ` is not fully derived from rotational field
- Summation geometry is empirically selected, not fully derived

---

## 7. Guarantees (current)

The hybrid controller:

- preserves deterministic structure (no randomness)
- can override greedy traps in bounded domains
- remains stable under historization

---

## 8. Non-guarantees

The hybrid controller does **not** yet guarantee:

- global optimality
- scalability to large branching factors
- full phase-consistent field derivation

---

## 9. Falsification conditions

The hybrid approach would be challenged if:

- amplitude fails to outperform greedy in trap scenarios
- geometry choice leads to inconsistent decisions
- phase variation does not influence outcomes

---

## 10. Interpretation

The hybrid controller implements:

> local structural minimization + bounded future coherence comparison

It is not probabilistic planning.  
It is not heuristic search.  
It is a structural decision system with dual evaluation regimes.

---

## End of Spec
