# E₀ Internal Difference → Spinor Bridge v0

**Status:** Exploratory formalization (critical bridge)  
**Date:** 2026-03-24  
**Purpose:** Formalize the missing step connecting E₀ internal difference to the necessity of a spinor (ℂ²) carrier and thus to SU(2) structure.

---

## 1. Why this document exists

Current state:

- Amplitude formulation exists (Ψ = exp(-S)·exp(iΘ))
- SU(2) identified as minimal stable structure with internal difference (Chapter 4)
- 720° periodicity follows if SU(2) carrier is established

**Open gap:**

> Why does internal difference in E₀ require a two-component complex carrier (ℂ²) instead of a scalar phase (ℂ)?

This document isolates that bridge.

---

## 2. Definitions (working)

### 2.1 Internal Difference

A system exhibits **internal difference** if:

- it contains at least two non-reducible components
- their relation cannot be represented by a single scalar phase
- their relative orientation carries information

Formally (working definition):

```text
A system has internal difference if there exist states (ψ₁, ψ₂) such that:

ψ₁ ≠ e^{iθ} ψ₂  for all θ
```

---

### 2.2 Scalar Carrier (U(1))

```text
ψ ∈ ℂ
ψ → e^{iθ} ψ
```

Properties:

- single degree of freedom (phase)
- no internal relational structure
- all transformations act globally

---

### 2.3 Vector Carrier (candidate)

```text
ψ = (ψ₁, ψ₂, ...)
ψ ∈ ℂⁿ
```

Allows:

- internal relations between components
- nontrivial mixing under transformation

---

## 3. Negative Result: ℂ is insufficient

We claim:

> A scalar complex carrier cannot represent irreducible internal difference.

### Argument:

1. In ℂ, all states differ only by magnitude and phase
2. Phase transformations are global: ψ → e^{iθ}ψ
3. Any two states are related by scaling + phase (modulo normalization)

Therefore:

- no invariant notion of "relative orientation" exists
- no internal degrees of freedom can be preserved under transformation

Conclusion:

```text
ℂ cannot encode irreducible internal difference
```

---

## 4. Minimality Argument: Why ℂ²

We now ask:

> What is the smallest space that can encode irreducible internal difference?

Requirements:

1. At least two independent components
2. Complex structure (phase-sensitive)
3. Ability to represent relations invariant under transformation

Minimal solution:

```text
ψ = (ψ₁, ψ₂) ∈ ℂ²
```

ℂ² is the smallest complex vector space where:

- two components exist
- their relative phase is meaningful
- transformations can mix components

---

## 5. Rotational Consistency Requirement

E₀ systems exist in spatial context → transformations include rotations.

We require:

> Internal difference must be preserved under rotation.

This imposes constraints:

- transformation must be linear
- must preserve norm (unitarity)
- must act consistently on both components

Thus:

```text
ψ → U ψ,   U ∈ U(2)
```

---

## 6. Reduction to SU(2)

We further require:

- no global phase redundancy
- determinant = 1 (pure internal transformation)

Thus:

```text
U ∈ SU(2)
```

This is the minimal group acting on ℂ² that:

- preserves norm
- preserves internal relations
- allows nontrivial mixing

---

## 7. Connection to Spatial Rotations

Known result:

```text
SU(2) → SO(3)  (double cover)
```

Implication:

- transformations in SU(2) correspond to rotations in 3D space
- but require double traversal for identity

---

## 8. Emergence of 720°

From topology:

```text
π₁(SO(3)) = ℤ₂
```

Therefore:

- 360° rotation → nontrivial loop
- 720° rotation → contractible → identity

Since system transforms via SU(2):

```text
360° → ψ → -ψ
720° → ψ → ψ
```

---

## 9. Bridge Summary

The full chain becomes:

```text
E₀ internal difference
    ↓ (requires non-scalar representation)
ℂ insufficient
    ↓ (minimal extension)
ℂ²
    ↓ (unitary, relational preservation)
SU(2)
    ↓ (topology)
720° periodicity
```

---

## 10. Status of the argument

### Strong

- ℂ insufficiency argument
- ℂ² minimality (plausible)
- SU(2) → 720° (proven mathematics)

### Still open

- formal definition of "internal difference"
- proof that ℂ² is not just sufficient but necessary
- derivation of Θ → rotational structure

---

## 11. Interpretation

The key shift is:

> Spinor behavior is not an added structure — it is a consequence of requiring internal difference to be preserved under transformation.

---

## 12. Next steps

To complete the bridge:

1. Formalize internal difference in E₀ primitives
2. Derive Θ from v_rot
3. Show loop-dependent phase accumulation
4. Test emergence of sign inversion in controlled domains

---

## 13. Conclusion

The 720° spinor behavior is not yet fully derived, but:

- the structural path is clear
- the minimal carrier argument is strong
- the remaining gap is well-localized

This makes the spinor hypothesis a **targeted formal problem**, not a speculative idea.

---

## End of Document
