# E₀ Controller Born-Regime Check
## Does the current controller instantiate the Born-Criterion Regime?

**Status:** Structural audit note — **Updated 2026-03-25**  
**Date:** 2026-03-23 (original), 2026-03-25 (update)  
**Language:** English  
**Purpose:** Check the current operational controller against the previously derived amplitude regime criteria before any direct implementation changes.

> **Update (2026-03-25):** The original audit (§1–§12) was written before the
> amplitude overlay existed. Since then, Paths D1–H have implemented all three
> options proposed in §10. See **§13 (Post-Implementation Re-Audit)** at the
> end of this document for the current assessment.

---

## 1. Audit question

We want to test the current controller against four criteria for local instantiation of the Born-Criterion Regime:

1. bounded alternative set,
2. exclusive realization,
3. canonical support scalar,
4. no overriding distortion rule.

The question is not whether the controller already computes `Ψ` explicitly.
The question is whether its current logic is structurally equivalent to that regime, partially equivalent, or not yet there.

---

## 2. Result in one sentence

> The current controller **does instantiate a bounded exclusive episode structure**, but it **does not yet instantiate the Born-Criterion Regime**, because selection is performed by deterministic argmin over penalized tension rather than by amplitude-derived endpoint support.

So the regime is **nearby**, but not yet realized.

---

## 3. Criterion 1 — bounded alternatives

This criterion is clearly satisfied locally.

In `select_next(current)`, the controller constructs a finite candidate set via:

- `_admissible_neighbors(current)` under controller-level admissibility,
- with fallbacks through escalation if needed.

This means that at any decision step, the effective choice set is a bounded set of outgoing neighbors, not an open world.

So the controller strongly matches the bounded-alternative requirement.

---

## 4. Criterion 2 — exclusive realization

This criterion is also clearly satisfied.

The controller selects exactly one next state:

```text
best = min(neighbors, key=lambda y: self._penalized_tension(current, y))
```

and returns one target for execution.

So the controller is locally an exclusive single-transition episode machine.

This is exactly the kind of operational structure in which Born-like normalization could potentially appear.

---

## 5. Criterion 3 — canonical support scalar

This criterion is **not** satisfied in amplitude form.

The controller currently uses:

```text
S_eff = Δ · R_eff
```

and selects the next state by deterministic minimization of penalized tension.

The support object is therefore not:

```text
Ψ(y) = Σ_p exp(-S(p)) exp(iΘ(p))
```

nor even:

```text
I(y) = |Ψ(y)|²
```

Instead, the controller uses a scalar ordering functional:

```text
argmin S_penalized(x→y)
```

This means the controller currently realizes **winner-take-lowest-burden**, not **normalized coherent support**.

So the amplitude layer is absent operationally.

---

## 6. Criterion 4 — no overriding distortion rule

This criterion is only partially satisfied.

On the one hand, the controller is internally consistent: it does not insert arbitrary scoring layers unrelated to its formalism.

On the other hand, it does apply a revisit-penalty:

```text
S_revisit(x→y) = S_eff(x→y) · (1 + α · 1[y in recent])
```

This is a deliberate distortion of raw local tension for operational reasons.

That does not make the controller incoherent.
But it means the final choice rule is not purely canonical even relative to its own local scalar support.

The escalation heuristics reinforce this point: dead-end and exhausted recovery are operational overlays, not yet fully derived from the deeper phase/potential formalism.

So criterion 4 is not cleanly satisfied at the present stage.

---

## 7. Structural classification of the current controller

The current controller is best described as:

> **Regime-A-shaped, but pre-amplitude.**

Meaning:

- it already has the right episode geometry (bounded, exclusive, local alternatives),
- but it still resolves that episode with deterministic lowest-tension selection,
- rather than with amplitude aggregation and normalized intensity.

This is a very important result.

It means the controller is not alien to the Born-Criterion Regime.  
It is a near-neighbor architecture that could be extended into it.

---

## 8. What is already amplitude-compatible

Even without explicit `Ψ`, several controller features are compatible with the amplitude route.

### 8.1 Additive burden structure

Single-edge tension is already defined as:

```text
S(x→y) = Δ · R_eff
```

and path tension is additive.

This is exactly the magnitude-side prerequisite for:

```text
exp(-S(p))
```

### 8.2 Bounded local branching

The controller already evaluates finite candidate branches. This is precisely where endpoint amplitude comparison would live.

### 8.3 Historization

Historization changes future resistance, which means future path amplitudes would also change naturally over time.

So the controller’s learning mechanism is fully compatible with an amplitude interpretation.

---

## 9. What is still missing for true regime instantiation

Three things are missing.

### 9.1 Path aggregation

The controller currently compares only local outgoing edges, not multi-path families to the same target horizon.

A true amplitude regime needs at least bounded path-family aggregation:

```text
Ψ(y) = Σ_{p:x→...→y} exp(-S(p)) exp(iΘ(p))
```

within some horizon.

### 9.2 Orientational residue

The controller currently has no implemented `Θ` layer in action selection.
So equal-burden but differently oriented path families remain invisible.

### 9.3 Support-based choice rule

Even if amplitude were computed, the controller would still need to decide whether to:

- choose `argmax I(y)` deterministically,
- or sample from normalized support `P(y) ∝ I(y)`,
- or reserve Born-like semantics only for specific sub-regimes.

That decision is not yet implemented.

---

## 10. Immediate design options

The audit suggests three possible controller evolutions.

### Option 1 — Deterministic amplitude controller

Compute bounded-horizon endpoint intensities:

```text
I(y) = |Ψ(y)|²
```

but still choose:

```text
argmax I(y)
```

This keeps determinism while upgrading support from scalar tension to coherent path support.

### Option 2 — Born-regime controller

In explicit exclusive bounded episodes, normalize:

```text
P(y) = I(y) / Σ I(w)
```

and sample one realization.

This would instantiate the Born-Criterion Regime operationally.

### Option 3 — Hybrid semantic split

Use deterministic argmin/argmax in ordinary operational control, but activate normalized support only in subdomains where the semantics are genuinely exclusive and uncertainty-like.

This may fit E₀’s regime taxonomy best.

---

## 11. Best current conclusion

The strongest defensible conclusion is:

> The current controller already satisfies the **geometry** of the Born-Criterion Regime (bounded local alternatives + exclusive realization), but not its **support semantics**.  
> It therefore does not yet implement Born-like behavior, though it is structurally very close to the regime in which such behavior would become natural.

That is a highly informative result.

It means the controller is neither a contradiction to the derivation nor a proof of it.  
It is the right place to test the derivation next.

---

## 12. Recommended next move

Before modifying the controller core, the cleanest next experiment would be:

1. keep the current controller unchanged,
2. add an **analysis-only prototype** that computes bounded-horizon `Ψ`, `I`, and normalized `P` for the current candidate set,
3. compare its ranking against deterministic `argmin S_penalized` on the same landscapes.

That would reveal whether the amplitude regime merely reformulates the existing controller or genuinely changes decisions.

---

## End of Original Audit (2026-03-23)

---

## 13. Post-Implementation Re-Audit (2026-03-25)

Since the original audit, the E₀ controller has been extended through
Paths D1–H. All three options from §10 are now implemented:

| Option | §10 Proposal | Implementation | Mode |
|--------|-------------|----------------|------|
| 1 | Deterministic amplitude controller | `AMPLITUDE_ON_DISAGREE` | Default |
| 2 | Born-regime controller | `BORN_SAMPLING` | Opt-in |
| 3 | Hybrid semantic split | Confidence gating + geometry selection | Configurable |

### 13.1 Re-evaluation of the four criteria

**Criterion 1 — Bounded alternatives:** ✅ Still satisfied.
The amplitude overlay enumerates paths within a bounded horizon
and computes I(a) for each admissible action.

**Criterion 2 — Exclusive realization:** ✅ Still satisfied.
Both argmax and Born sampling select exactly one action per step.

**Criterion 3 — Canonical support scalar:** ✅ **Now satisfied.**
The amplitude overlay computes:
```
Ψ(a) = Σ_p exp(−S(p)) · exp(iΘ(p))
I(a) = |Ψ(a)|²
P(a) = I(a) / Σ I
```
This is exactly the canonical support scalar that was missing in v1.
Implemented in `amplitude_overlay.py`, used by both AMPLITUDE_ON_DISAGREE
and BORN_SAMPLING modes.

**Criterion 4 — No overriding distortion rule:** ⚠️ Partially satisfied.
The revisit-penalty and escalation heuristics remain as operational overlays
in the greedy layer. However, BORN_SAMPLING mode delegates directly to
`_born_sample()` which uses only the amplitude-derived P(a) — no distortion.
Escalated steps fall back to greedy (operational necessity, not distortion
of the Born rule itself).

### 13.2 Updated structural classification

The controller is now best described as:

> **Multi-regime: deterministic structural control (default) with
>  opt-in Born realization (BORN_SAMPLING).**

The original audit's conclusion — "right geometry, wrong support semantics" —
has been resolved. The support semantics are now amplitude-derived.

### 13.3 What §9 identified as missing — status

| Gap from §9 | Status |
|-------------|--------|
| 9.1 Path aggregation | ✅ Implemented — bounded-horizon Ψ(a) aggregation in `amplitude_overlay.py` |
| 9.2 Orientational residue (Θ) | ✅ Implemented — phase Θ(p) computed per path, interference is real |
| 9.3 Support-based choice rule | ✅ Implemented — argmax(I) in AMPLITUDE_ON_DISAGREE, sample(P) in BORN_SAMPLING |

### 13.4 Key empirical finding (Path H)

> Geometry choice (simple vs goal_reaching) has more impact on controller
> success than decision rule choice (argmax vs sampling).

With `goal_reaching` geometry, argmax dominates. With `simple` geometry
on Gordian, both modes struggle because greedy and amplitude agree on
the trap action. This validates the original audit's emphasis on
structural geometry as the foundation.

### 13.5 Conclusion

The Born-Criterion Regime is now **operationally instantiated** in the
E₀ controller as `HybridMode.BORN_SAMPLING`. All four criteria are
satisfied (Criterion 4 with the caveat that escalated steps bypass
the Born rule for operational safety).

The original audit's prediction — that the controller was "the right place
to test the derivation" — has been confirmed.

---

_End of document._
