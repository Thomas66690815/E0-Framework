# E₀ Internal Difference — Formalization v1

**Status:** Formal refinement (critical definition layer)  
**Date:** 2026-03-24  
**Purpose:** Provide a precise, minimal, and testable definition of *internal difference* that supports (but does not assume) the emergence of a spinorial carrier.

---

## 1. Why this document exists

Previous result:

- ℂ is insufficient to encode internal difference
- ℂ² is a plausible minimal carrier
- SU(2) follows if such a carrier must transform under rotations

**Open problem:**

> What exactly is *internal difference* in E₀ terms such that ℂ becomes insufficient *by necessity*, not by intuition?

---

## 2. Core intuition (non-formal)

Internal difference is not:

- "having two states"
- "having two values"

It is:

> **a relational degree of freedom that cannot be reduced to a single global phase or scalar quantity**

---

## 3. Formal working definition

A system exhibits **internal difference** iff:

```text
There exists a representation space V and two non-zero elements ψ₁, ψ₂ ∈ V such that:

1. ψ₁ and ψ₂ are not related by any global phase:
   ∄ θ ∈ ℝ : ψ₁ = e^{iθ} ψ₂

2. There exists at least one transformation T in the admissible transformation set such that:
   T(ψ₁) ≠ λ T(ψ₂)  for all λ ∈ ℂ

3. The relation between ψ₁ and ψ₂ is invariantly meaningful under admissible transformations
```

---

## 4. Admissible transformations

We define admissible transformations as those that:

- are continuous
- preserve total intensity (norm)
- preserve structural relations

Thus:

```text
T ∈ U(n)
```

---

## 5. Negative theorem (ℂ insufficiency)

**Claim:** ℂ cannot satisfy the definition above.

### Sketch:

- Any ψ ∈ ℂ is fully described by magnitude + phase
- All transformations are global: ψ → e^{iθ}ψ
- Therefore:

```text
∀ ψ₁, ψ₂ ∈ ℂ  ⇒  ψ₁ ~ ψ₂ (up to scaling and phase)
```

No invariant relational structure exists.

---

## 6. Minimal representation requirement

We require a space V such that:

- dim(V) ≥ 2
- supports complex structure
- supports nontrivial unitary transformations

Minimal candidate:

```text
V = ℂ²
```

---

## 7. Relational invariant

In ℂ², the relative phase and orientation between components define a nontrivial invariant structure.

Example invariant:

```text
R(ψ) = ψ₁* ψ₂
```

This quantity is:

- not reducible to a single global phase
- transformation-sensitive
- relational

---

## 8. Transformation constraint

We now require:

> Transformations must preserve relational structure

Thus:

- linear
- norm-preserving

⇒ unitary group

---

## 9. Reduction to SU(2)

Further constraint:

- global phase should not carry physical meaning

Thus we factor out U(1):

```text
U(2) / U(1) ≈ SU(2)
```

---

## 10. Connection to rotations

To embed into spatial transitions:

- transformations must correspond to 3D rotations

Only consistent mapping:

```text
SU(2) → SO(3)
```

(double cover)

---

## 11. Consequence: spinorial behavior

Once SU(2) is required:

- representation is spinorial
- 360° → sign inversion
- 720° → identity

---

## 12. Critical clarification

This document does NOT prove:

- that all E₀ systems are spinorial

It shows:

> If a system exhibits irreducible internal difference AND must preserve it under rotation,
> then the minimal consistent representation is spinorial.

---

## 13. Relation to SU2_SPEC_v0.2 (Gemini)

Gemini correctly identifies:

- U(1) collapses orientation
- SU(2) preserves internal structure

However, we refine:

- ℂ² is not introduced because "two states exist"
- but because **scalar representation fails to preserve relational invariants**

---

## 14. Testable implications

A system has internal difference iff:

1. There exist observables depending on relative component structure
2. These observables are invariant under allowed transformations
3. Scalar projection destroys these observables

---

## 15. Next steps

1. Connect relational invariant to Θ
2. Derive rotational generator from v_rot
3. Construct loop tests for sign inversion
4. Integrate with Gordian Trap phase behavior

---

## 16. Final statement

Internal difference is not multiplicity.

It is:

> **irreducible relational structure preserved under transformation**

This is the true driver behind the emergence of spinorial representation.

---

## End of Document
