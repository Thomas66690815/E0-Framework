# E₀ Derived / Empirical / Heuristic Map v1

**Status:** Draft (critical clarity layer)  
**Date:** 2026-03-24  
**Purpose:** Explicitly classify all major components and claims of the current E₀ system into:

- Derived (from structural chain)
- Empirical (observed via experiments/tests)
- Heuristic / Operational (working but not yet derived)

---

## 1. Why this document exists

The system has reached a level where multiple layers interact:

- structural theory
- controller logic
- amplitude layer
- summation geometry
- hybrid arbitration

Without explicit classification, it becomes unclear:

- what is proven
- what is observed
- what is assumed

This document prevents that ambiguity.

---

## 2. Classification categories

### Derived

Follows from the E₀ structural chain and internal consistency.

### Empirical

Observed through experiments, simulations, or test results.

### Heuristic / Operational

Used because it works in runtime, but not yet structurally derived.

---

## 3. Core structural layer

| Component | Classification | Notes |
|----------|---------------|------|
| Primitives (S, Δ, P, R, H, τ, v) | Derived | Canonical basis |
| Axiom A₀ | Derived | Structural assumption |
| Central Law (Δ > 0 → transition) | Derived | Core enforcement |
| Burden S = Δ · R_eff | Derived | Direct structural consequence |
| Historization (R updates) | Derived | Irreversibility mechanism |

---

## 4. Deterministic controller

| Component | Classification | Notes |
|----------|---------------|------|
| Greedy selection (min S) | Derived | Direct minimization principle |
| Admissibility constraints | Derived | Path validity |
| Revisit penalty | Heuristic | Stabilization mechanism |
| Escalation logic | Heuristic | Safety / termination |

---

## 5. Amplitude layer

| Component | Classification | Notes |
|----------|---------------|------|
| Path burden S(p) | Derived | Aggregation of local burdens |
| Complex carrier Ψ(p) | Derived (partial) | Structure consistent, phase not fully derived |
| Intensity I = |ΣΨ|² | Derived (conditional) | Supported by Born-style reasoning |
| Phase Θ(p) | Heuristic / Open | Not fully derived from v_rot |
| Holonomy independence (ΔΘ from forward edges only) | **Derived** | Proven: Φ cancels in holonomy. ΔΘ = ½[Σv₁ − Σv₂] |
| Destructive interference (factor < 0.1) | **Empirical (demonstrated)** | Gordian Trap: coherent I_A = 2% of incoherent I_A |

---

## 6. Summation geometry

| Component | Classification | Notes |
|----------|---------------|------|
| Prefix geometry | Empirical (rejected) | Path inflation observed |
| Simple-path geometry | Empirical (preferred) | Stable, reduced inflation; default for exploration |
| First-arrival geometry | Empirical (incomplete) | Needs further testing |
| Goal-reaching geometry (G5) | **Empirical (proven, regime-specific)** | Born-criterion aligned: only goal-ending paths. Resolves prefix-inflation. Demonstrated via Gordian Trap (P(B)=96.2%) |

**Key point:**

Summation geometry is currently not derived — it is selected based on behavior.
However, G5 has a **structural justification** (Born criterion): when the question is endpoint-oriented, only endpoint-reaching paths should contribute. G5 is **not** universally superior — it requires explicit goal specification. `simple` remains the robust default for exploratory analysis.

---

## 7. Hybrid controller

| Component | Classification | Notes |
|----------|---------------|------|
| Dual evaluation (greedy + amplitude) | Structural + Empirical | Motivated by observed disagreement |
| AMPLITUDE_ON_DISAGREE policy | Empirical | Works in tests |
| Override mechanism | Empirical | Validated in scenarios |
| `hybrid_geometry` parameter | Empirical | Allows regime-specific geometry (e.g. G5 for goal-oriented) |
| Safety conditions | Heuristic | Prevent invalid overrides |

---

## 8. MemOS integration

| Component | Classification | Notes |
|----------|---------------|------|
| Trace persistence (U, F) | Derived | Historization extension |
| Runtime snapshots | Empirical | Operational integration |
| Hybrid trace recording | Empirical | New capability |

---

## 9. Key findings (current state)

| Finding | Classification | Notes |
|--------|---------------|------|
| Greedy traps exist | Empirical | Demonstrated in domains |
| Amplitude can correct traps | Empirical | Observed in overlay + hybrid |
| Geometry affects correctness | Empirical | Critical dependency |
| Hybrid improves outcomes | Empirical | Measured via runs |
| **Holonomy independence** | **Derived** | ΔΘ depends only on forward-edge v; Φ cancels. Proven and numerically verified to 6 decimal places |
| **Interference-based routing** | **Empirical (demonstrated)** | Gordian Trap: greedy A1 overridden to B1 via destructive interference at h=5 |
| **G5 is regime-specific** | **Empirical** | G5 wins only under goal semantics; `simple` remains correct for exploration |
| **Prefix-inflation artifact** | **Empirical (identified)** | Non-goal prefixes dominate intensity under `simple`, masking interference |
| **Multi-goal G5 amplitude rescue** | **Empirical (demonstrated)** | Coherent alternative-goal paths rescue actions from single-goal destructive interference; ordering preserved: A1>B1>C1; single-goal regression preserved |
| **Topology classification (G5 override)** | **Empirical (380-graph scan)** | Override requires ≥2 path families; phase opposition |ΔΘ|>π/2 is strongest predictor; triangle=0%, diamond=37%, gordian=93%; G5 uniquely differs (30.3% exclusive) |

---

## 10. Open structural gaps

The following are not yet fully derived:

- Phase Θ from rotational field (v_rot) — partially addressed by holonomy independence theorem
- Formal derivation of summation geometry (why simple? why G5 only for goals?)
- Scalable aggregation of amplitudes without enumeration
- Full necessity proof for Born-style intensity in all regimes
- Stability of interference routing under historization — **RESOLVED** (12 tests, 4 scenarios)
- Multi-goal behavior under G5 — **RESOLVED** (15 tests + 8 LLM tests)
- Spinor extension: whether scalar Θ should be lifted to SU(2) generator (see E0_THETA_TO_SU2_GENERATOR_v0.md)
- Topology classification: which graph structures admit interference-based routing? — **RESOLVED** (23 tests, 380-graph scan)

---

## 11. Interpretation

The system currently consists of:

- a derived structural core
- an empirically validated extension layer
- a set of operational bridges

This is expected at this stage of development.

---

## 12. One-sentence rule

At any point in development, it must be clear whether a component is:

> derived, observed, or assumed.

---

## End of Document
