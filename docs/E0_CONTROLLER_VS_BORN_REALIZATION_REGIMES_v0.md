# E₀ — Controller vs Born Realization Regimes

**Status:** Architecture Decision Record (ADR)  
**Date:** 2026-03-25  
**Decision ID:** ADR-0007  

---

## 1. Context

The E₀ system has reached a stage where amplitude-based support is fully implemented:

- Ψ(p) = exp(−S + iΘ)
- I = |ΣΨ|²
- P = I / ΣI

This raises a key architectural question:

> Should the controller select actions via deterministic argmax(I), or via probabilistic sampling from P (Born rule)?

---

## 2. The Two Regimes

### 2.1 Controller Regime (Structural Control)

- Purpose: decision-making, planning, navigation
- Semantics: select most coherent structure
- Rule:

argmax(I)

- Properties:
  - deterministic
  - reproducible
  - stable under evaluation

---

### 2.2 Born Realization Regime (Episodic Realization)

- Purpose: realization under bounded exclusive alternatives
- Semantics: sample according to support
- Rule:

P(y) = I(y) / Σ I(w)

sample(P)

- Properties:
  - stochastic
  - distributional outcomes
  - aligns with quantum-like realization

---

## 3. Decision

The E₀ Controller SHALL remain deterministic.

- Core selection rule: argmax(I)
- Born sampling is NOT used in the core controller loop

---

## 4. Rationale

### 4.1 Stability

Deterministic selection enables:
- reproducible results
- clear regression testing
- controlled evaluation

### 4.2 Debuggability

Sampling introduces variance that obscures:
- structural effects
- causal attribution

### 4.3 Current System Role

The controller is a:

> structural decision engine

not a realization process.

---

## 5. Position of Born Sampling

Born sampling is treated as:

> a separate realization regime

It may be used in:
- analysis tools
- simulation layers
- future physical interpretation modules

But not in:
- core control logic

---

## 6. Architectural Implication

The system is explicitly split into two layers:

### Layer A — Structural Control
- deterministic
- uses argmax(I)

### Layer B — Realization / Sampling
- stochastic
- uses sample(P)

---

## 7. Future Work

- Implement sampling as optional mode
- Compare argmax vs sample behavior
- Identify domains where Born regime is required

---

## 8. Summary

> The controller selects the most coherent structure.
> The Born regime realizes one possibility.

These are not the same operation and must not be conflated.

---

_End of document._