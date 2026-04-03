# E₀ Hybrid Controller Specification v1

**Status:** Draft (operational)  
**Date:** 2026-03-25  
**Purpose:** Define the behavior, guarantees, limits, and metrics of the E₀ hybrid controller.

---

## 1. Overview

The E₀ controller operates in three modes:

- **GREEDY_ONLY** — selects the action with minimal local structural burden
- **AMPLITUDE_ON_DISAGREE** — compares greedy choice with amplitude-based path-family support and may override (default)
- **BORN_SAMPLING** — samples from P ∝ I instead of argmax (opt-in, ADR-0007-v1)

The hybrid controller does **not** replace the greedy controller.  
It augments it with additional evaluation regimes.

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

   - if mode is `BORN_SAMPLING` → sample from P (see §2.1)
   - if `a_greedy == a_amp` → select `a_greedy` (AGREE)
   - if `a_greedy != a_amp` → apply hybrid policy (see §3)

### 2.1 Born sampling sub-pipeline

When `hybrid_mode == BORN_SAMPLING`:

1. Compute overlay as above (same Ψ, I, P)
2. Sample action: `a = random.choices(actions, weights=P, k=1)[0]`
3. Mark as overridden (`override = True`)
4. Escalated steps bypass sampling and fall back to greedy

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

### Confidence gating (Path F)

Overrides are gated by `override_confidence` from the amplitude overlay:

- if `override_confidence < confidence_threshold` → fall back to greedy
- default `confidence_threshold = 0.0` (no gating)

`override_confidence` is computed as `1 − 2·min(P, 1−P)` where P is the
probability of the greedy action. Ranges from 0 (50/50 split) to 1 (dominant action).

This applies to AMPLITUDE_ON_DISAGREE mode. BORN_SAMPLING always samples.

---

## 4. Metrics

The following runtime metrics must be tracked:

- `hybrid_override_count`
- `hybrid_override_rate`
- `agreement_rate`
- `avg_horizon`
- `avg_override_confidence` (Path F)

Born-specific metrics (optional):

- `sample_variance` — variance across repeated Born runs
- `ensemble_success_rate` — fraction of Born trials reaching goal
- `goal_coverage` — number of distinct goals reached (multi-goal domains)

---

## 5. Summation geometry

The amplitude layer depends on summation geometry.

Currently supported:

- `prefix`
- `simple` (default)
- `first_arrival`
- `goal_reaching` — filters to only goal-reaching paths (Path A/D1)

### Current status

- `simple` is empirically most stable for general use
- `goal_reaching` is best for trap-escape domains (Gordian)
- `prefix` overcounts recursive paths
- `first_arrival` requires further validation
- Geometry is persisted via MemOS (Path G)

---

## 6. Known limitations

- Path enumeration is exponential in horizon (`O(k^h)`)
- Phase `Θ` is not fully derived from rotational field
- Summation geometry is empirically selected, not fully derived

---

## 7. Guarantees (current)

The hybrid controller:

- preserves deterministic structure in GREEDY_ONLY and AMPLITUDE_ON_DISAGREE modes
- provides stochastic exploration in BORN_SAMPLING mode
- can override greedy traps in bounded domains
- remains stable under historization
- persists geometry and confidence settings across sessions (MemOS)

---

## 8. Non-guarantees

The hybrid controller does **not** yet guarantee:

- global optimality
- scalability to large branching factors
- full phase-consistent field derivation
- that Born sampling outperforms argmax (empirically, argmax dominates with correct geometry)

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
> + optional probabilistic realization (Born sampling)

It is not probabilistic planning.  
It is not heuristic search.  
It is a structural decision system with three evaluation regimes.

Key empirical finding (Path H, ADR-0007-v1):
> Geometry choice dominates over decision rule choice.

---

## End of Spec
