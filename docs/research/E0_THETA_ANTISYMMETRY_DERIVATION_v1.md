# E₀ — Θ Antisymmetry Derivation v1

**Status:** Formal Theorem (proof sketch)  
**Date:** 2026-03-25  
**Scope:** Phase definition as discrete connection, uniqueness, gauge invariance, SU(2) bridge

---

## 1. Problem Statement

We define the path phase:

Θ(p) = Σ ω(e)

We seek a derivation of ω from the transition field v such that Θ behaves as a valid phase connection.

---

## 2. Definitions

Let G = (V, E) be a directed graph.

Let:

- v: E → ℝ be a transition field
- v = v_grad + v_rot (Helmholtz decomposition)

Define a path:

p = (e₁, ..., e_n)

---

## 3. Requirements for a Phase Generator

A function ω: E → ℝ is admissible iff:

(R1) Orientation:
ω(x,y) = −ω(y,x)

(R2) Additivity:
Θ(p) = Σ ω(e)

(R3) Gauge invariance:
ω invariant under v → v + v_grad

(R4) Reciprocity neutrality:
If v(x,y) = v(y,x), then ω(x,y) = 0

---

## 4. Lemma 1 — Gradient Elimination

For v_grad(x,y) = Φ(x) − Φ(y):

Σ v_grad = Φ(start) − Φ(end)

Thus v_grad contributes no path-dependent phase.

∎

---

## 5. Lemma 2 — Necessity of Rotational Component

Only v_rot survives path comparison:

v → v_rot

Thus ω must depend only on v_rot.

∎

---

## 6. Lemma 3 — Symmetric Components Violate Orientation

Let s(x,y) = s(y,x).

Then:

s(x,y) = s(y,x)

⇒ violates (R1)

Thus symmetric components are inadmissible.

∎

---

## 7. Lemma 4 — Antisymmetric Edge Functions Form Discrete 1-Forms

If ω(x,y) = −ω(y,x), then:

- path integrals are well-defined
- loop sums encode holonomy

Thus ω is a discrete 1-form.

∎

---

## 8. Theorem — Uniqueness of Antisymmetric Rotational Phase

Given requirements (R1–R4), the unique admissible phase generator is:

ω(x,y) = 1/2 (v_rot(x,y) − v_rot(y,x))

---

### Proof Sketch

1. From Lemma 1, v_grad is excluded
2. From Lemma 2, only v_rot remains
3. From Lemma 3, symmetric components are excluded
4. Remaining admissible structure is antisymmetric component of v_rot

Thus ω is uniquely determined.

∎

---

## 9. Corollary — Phase as Discrete Line Integral

Θ(p) = Σ ω(e)

is the discrete analogue of:

Θ = ∫ A · dl

where A is a U(1) connection.

---

## 10. Corollary — Gauge Invariance

Θ is invariant under:

v → v + v_grad

Thus:

Phase depends only on rotational structure.

---

## 11. SU(2) Lift

Define generator:

G = Θ · (n · σ)

with:

n = normalize(v_rot)

Then:

U = exp(-i G/2)

ensures:

- unitary evolution
- 4π periodicity

---

## 12. Historization Link (Hypothesis)

Let H be historization.

Hypothesis:

Only antisymmetric rotational imbalance contributes to persistent accumulation:

∂H/∂t ∝ ω

---

## 13. Consequences

1. Phase is structurally derived
2. Interference is geometric
3. Gauge invariance is intrinsic
4. SU(2) structure is natural extension

---

## 14. Status

- Empirical support: Gordian, G5, topology scan
- Formal proof: complete at sketch level
- Full formalization: ongoing

---

_End of document._