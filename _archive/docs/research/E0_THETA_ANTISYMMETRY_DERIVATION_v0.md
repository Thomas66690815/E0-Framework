# E₀ — Θ Antisymmetry Derivation v0

**Status:** Structural derivation (closing phase-definition gap)  
**Date:** 2026-03-25  
**Purpose:** Derive why the phase increment ω must be the antisymmetric component of the rotational field and why Θ = Σ ω is the unique admissible path phase.

---

## 1. Problem Statement

We currently define:

```text
Θ(p) = Σ ω(e)
```

with ω derived from v_rot.

Open question:

> Why must ω be the antisymmetric component of v_rot, and why does this yield the correct notion of phase?

---

## 2. Required Properties of a Phase Connection

A valid phase increment ω must satisfy:

1. **Orientation sensitivity**  
   ω(x,y) = −ω(y,x)

2. **Path additivity**  
   Θ(p) = Σ ω(e)

3. **Conservative invariance (gauge invariance)**  
   Contributions from gradient fields must cancel on any path difference.

4. **Zero under local reciprocity**  
   If transitions are symmetric, no oriented phase remains.

---

## 3. Elimination of v_grad

The gradient component:

```text
v_grad(x,y) = Φ(x) − Φ(y)
```

Telescopes along paths:

```text
Σ v_grad = Φ(start) − Φ(end)
```

Thus:

- path-independent
- cancels in path comparison

→ cannot generate interference structure

---

## 4. Need for a Rotational Component

Only the non-conservative component can distinguish paths:

```text
v = v_grad + v_rot
```

Thus:

- phase must depend on v_rot
- this encodes geometric (Berry-like) phase

---

## 5. Antisymmetry as Necessity

We define:

```text
ω(x,y) = ½ (v_rot(x,y) − v_rot(y,x))
```

### 5.1 Orientation

Ensures:

```text
ω(y,x) = −ω(x,y)
```

Required for a directed phase.

---

### 5.2 Reciprocity Cancellation

If:

```text
v_rot(x,y) = v_rot(y,x)
```

then:

```text
ω = 0
```

→ no artificial phase from symmetric structure

---

### 5.3 Path Structure

Antisymmetric edge functions behave as discrete 1-forms:

- additive along paths
- sign-sensitive
- define loop integrals

Thus:

```text
Θ = Σ ω
```

is a discrete line integral.

---

## 6. Interpretation as Discrete Gauge Connection

ω is the graph analogue of a U(1) connection A:

```text
Θ = ∫ A · dl
```

Properties:

- gauge-invariant under Φ shifts
- depends only on curvature (rotational component)
- defines holonomy

---

## 7. Relation to Holonomy

For two paths p₁, p₂:

```text
ΔΘ = Θ(p₁) − Θ(p₂)
```

All gradient contributions cancel.

Thus:

```text
ΔΘ depends only on rotational antisymmetric structure
```

---

## 8. The 1/2 Factor

The factor ½ arises from two constraints:

1. extracting the antisymmetric component
2. matching SU(2) normalization

When lifted:

```text
U = exp(-i Θ/2 · (n · σ))
```

ensures correct 4π periodicity.

---

## 9. Bridge to SU(2)

Scalar phase:

```text
exp(iΘ)
```

is insufficient for internal difference.

Lift:

```text
Θ → G = Θ · (n · σ)
```

where:

```text
n = normalize(v_rot)
```

Thus:

- ω → magnitude accumulation
- v_rot direction → rotation axis

---

## 10. Connection to Historization (MemOS)

Key hypothesis:

- antisymmetric ω encodes directional memory
- only antisymmetric contributions can accumulate without cancellation

Thus:

```text
dH/dt couples to rotational imbalance
```

→ enables stable memory without drift from symmetric noise

---

## 11. Uniqueness Statement (Conjecture)

Given requirements:

- orientation sensitivity
- path additivity
- conservative invariance
- reciprocity neutrality

Then:

> The antisymmetric component of the rotational field is the unique admissible phase generator.

---

## 12. Consequences

1. Phase is not arbitrary — it is structurally forced
2. Interference arises from geometry, not heuristics
3. Gauge invariance is built-in
4. SU(2) lift is natural, not imposed

---

## 13. Conclusion

Θ is the line integral of the unique antisymmetric rotational 1-form on the graph.

This closes the conceptual gap:

```text
v → v_rot → ω → Θ → SU(2)
```

---

_End of document._