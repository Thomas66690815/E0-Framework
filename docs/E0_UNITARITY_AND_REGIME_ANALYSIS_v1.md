# E₀ Unitarity and Regime Analysis
## Does amplitude transport require a unitarity-like condition, and how stable is the Born-Criterion Regime?

**Status:** Research note / structural analysis  
**Date:** 2026-03-23  
**Language:** English  
**Purpose:** Examine two questions before applying the amplitude layer to the operational controller:  
(1) whether the E₀ amplitude structure implies a unitarity-like conservation principle, and  
(2) whether the Born-Criterion Regime is a rare special case or a structurally stable attractor.

---

## 1. Why this step matters

We now have a strong chain:

```text
Δ, R, H → S → Θ → Ψ → I = |Ψ|² → normalized I (conditional)
```

This is already enough to make the route look physics-like.
But before using it inside the controller, two foundational checks are necessary:

1. **Unitarity check**  
   If amplitudes are transported or composed through a landscape, is some norm-like quantity preserved, or can intensity arbitrarily inflate / deflate?

2. **Regime check**  
   The Born-like rule was derived only in an exclusive bounded-alternative regime. Is that regime exceptional, or does it arise naturally from structurally constrained transition episodes?

These questions determine whether the amplitude layer is:

- decorative,
- local-only,
- or deep enough to support a general interpretation.

---

## 2. First distinction: E₀ is not quantum mechanics

We must state the boundary clearly.

The current E₀ path object:

```text
Ψ(p) = exp(-S(p)) exp(iΘ(p))
```

contains **exponential damping** through `exp(-S)`.
That already differs from standard unitary quantum evolution, where norm-preserving phase transport is primary and suppression is not encoded as literal path damping in the same way.

So if a unitarity-like principle exists in E₀, it will not be the naive statement:

```text
|Ψ| is always preserved.
```

That is false in general, because tension accumulation suppresses magnitude.

Therefore the right question is subtler:

> Is there a **conditional or renormalized conservation law** at the level of amplitude transport, endpoint support, or alternative realization weights?

---

## 3. Three distinct notions of “unitary”

The term must be separated into three possible meanings.

### 3.1 Pathwise magnitude preservation

This would require:

```text
|Ψ(p ∘ q)| = |Ψ(p)|
```

or equivalent pathwise norm conservation.

This is incompatible with E₀ because:

```text
|Ψ(p)| = exp(-S(p))
```

and `S` is additive and typically increases along path concatenation.

So strict pathwise unitarity is **not** the right notion.

### 3.2 Transport-level conservation after normalization

One might instead ask whether, after comparing a bounded set of alternatives at a fixed transition episode, the normalized support satisfies:

```text
Σ_z P(z) = 1
```

This is true by construction once normalization is applied.

But that is not yet deep enough; it is merely probabilistic closure, not structural conservation.

### 3.3 Relative coherence preservation under phase transport

A more promising notion is that the **orientational part** of the amplitude is norm-preserving, while the **magnitude part** encodes structural loss / resistance.

In that reading:

- `exp(iΘ)` is unitary-like,
- `exp(-S)` is dissipative / selective.

This suggests that E₀ amplitudes are not purely unitary objects but **mixed transport objects**:

```text
coherent phase transport × resistance-induced attenuation
```

This is likely the correct structural interpretation.

---

## 4. The strongest defensible unitarity claim today

The current strongest safe claim is:

> E₀ does not imply global unitarity of amplitude magnitude.  
> It does imply a unitary-like transport law for the orientational factor, with non-unitary attenuation carried by tension.

This can be written schematically as:

```text
Ψ(p) = M(p) U(p)
```

where:

```text
M(p) = exp(-S(p))     positive attenuation factor
U(p) = exp(iΘ(p))     unit-modulus orientation factor
```

Then concatenation gives:

```text
M(p ∘ q) = M(p)M(q)
U(p ∘ q) = U(p)U(q)
```

So the phase sector is exactly unitary in the elementary sense of unit modulus, while the magnitude sector is not.

That means the natural E₀ analogue is not “unitary evolution” but rather:

> **attenuated unitary transport**

or, more descriptively:

> **historized coherent transport under structural loss**.

---

## 5. Why this is actually reasonable inside E₀

This mixed structure fits E₀ unusually well.

E₀ was never a lossless theory.
From the start it encoded:

- resistance,
- path burden,
- historization,
- irreversibility,
- and asymmetry between available alternatives.

So a purely unitary theory would have been surprising.

Instead, the current amplitude form says:

- orientation is transported coherently,
- but realizability decays with accumulated burden.

This is not a defect. It is a direct expression of E₀’s original commitments.

---

## 6. Is there any deeper conserved quantity?

A serious question remains.

Although `|Ψ|` is not conserved pathwise, perhaps some other quantity is conserved under bounded closed evolution.
Possible candidates:

1. total normalized endpoint support,
2. a renormalized partition-like quantity,
3. a local continuity equation on the landscape,
4. or a conserved holonomy class under closed loops.

At present none of these is proved.

### 6.1 Closed-loop clue

For a closed cycle `γ`:

```text
Ψ(γ) = exp(-S(γ)) exp(iΘ(γ))
```

Even when the system returns to the same state, the path amplitude is not generally 1 because:

- `S(γ)` may be positive,
- `Θ(γ)` may encode nontrivial holonomy.

So closed return is not identity. It leaves residue.

This strongly suggests that the natural conserved objects, if any, will not be raw amplitudes but **equivalence classes after historization and renormalization**.

That remains open.

---

## 7. Interim conclusion on unitarity

The clean conclusion is:

> E₀ does not support global magnitude-preserving unitarity.  
> It supports a unit-modulus phase transport factor coupled to a dissipative tension factor.  
> Any deeper conservation principle, if it exists, must be renormalized, conditional, or formulated at the level of support flow rather than raw path amplitude.

This is already a useful answer because it prevents the wrong analogy.

---

## 8. Now the regime question

We now turn to the Born-Criterion Regime.

Recall the regime conditions:

1. bounded alternative endpoint set,
2. exactly one endpoint realized,
3. endpoint support fully represented by `Ψ(z)`,
4. no extra endpoint-distorting rule allowed.

The question is:

> Is this regime rare and artificial, or is it a structurally stable attractor for many transition episodes?

---

## 9. Why the regime is unlikely to be rare

There are strong reasons to suspect the regime is common.

### 9.1 Real decision points are typically bounded

In most operational settings, a transition episode is not evaluated against an infinite open world at once.
It is evaluated against a bounded admissible set generated by:

- current state,
- reachable next states,
- path constraints,
- time budget,
- or controller horizon.

So boundedness is not exotic. It is often operationally natural.

### 9.2 Many episodes are effectively exclusive

At a given decision point, a system often takes one next transition, not several simultaneously.
This is true for:

- controller action selection,
- branching computations,
- many biological actions,
- and many measured physical outcomes.

So exclusivity is also common.

### 9.3 Canonical support pressure

Once a canonical amplitude support quantity exists, adding extra arbitrary weighting layers becomes structurally costly.
Systems that operate cleanly will tend to reuse the canonical scalar already available.

This means the no-extra-structure principle is not merely aesthetic; it is operationally economical.

---

## 10. Why the regime may still fail sometimes

We should not overstate it.

The regime can fail in at least four kinds of situations.

### 10.1 Multi-realization episodes

Some systems do not choose one endpoint; they distribute realization across several simultaneously.
Then normalized exclusive weights are the wrong semantics.

### 10.2 Open-ended endpoint growth

Some landscapes have no stable bounded alternative set at the relevant scale.
Then normalization is unstable or context-dependent.

### 10.3 Ongoing flow rather than episode closure

Sometimes there is no single decision episode at all, only continuous transition flow.
Then one may need densities or currents rather than endpoint probabilities.

### 10.4 Enriched carriers

If later E₀ extensions require more than the current complex carrier, the support scalar itself may be generalized.

So the regime is not universal by default.

---

## 11. Structural judgment: attractor, not axiom

The best current judgment is:

> The Born-Criterion Regime is not an axiom of all E₀ systems.  
> It is a **structurally stable attractor regime** for bounded exclusive transition episodes.

That is stronger than “special case,” but weaker than “universal law.”

This is probably the right level of commitment today.

It means:

- when a system localizes into a finite exclusive choice point, Born-like normalization becomes hard to avoid,
- but E₀ as a whole remains broader than that regime.

---

## 12. Why that is a strong result, not a weak one

This might sound modest, but it is actually powerful.

If E₀ is more general than a Born-governed theory, then:

- quantum-like exclusive realization becomes one domain of E₀,
- controller decisions may instantiate the regime locally,
- continuous or multi-realization processes may fall outside it,
- and the formalism remains flexible rather than overcommitted.

That is preferable to forcing everything into one semantics too early.

---

## 13. A useful taxonomy of E₀ regimes

The current picture suggests at least three regime types.

### Regime A — Exclusive bounded episode

- finite endpoint set,
- one realization,
- canonical support scalar.

This is the Born-Criterion Regime.

### Regime B — Continuous / flow regime

- endpoint set not discretely bounded,
- realization as current or density rather than one-shot choice.

This likely needs transport equations rather than simple normalization.

### Regime C — Multi-realization / branching regime

- several endpoints may be jointly realized,
- normalized exclusivity is not appropriate.

This likely needs measure over realized subsets or branching support.

This taxonomy is not final, but it is already clarifying.

---

## 14. Immediate implication for the controller question

Before checking the controller directly, we can already say what to look for.

The controller will instantiate the Born-Criterion Regime only if, at a given evaluation step:

1. it produces a bounded candidate action set,
2. exactly one action is chosen,
3. the amplitude-derived support is taken as canonical,
4. no extra hand-coded action distortion overrides that support.

That gives us a precise diagnostic later.

---

## 15. Final conclusions

### On unitarity

> E₀ is not globally unitary in amplitude magnitude.  
> It exhibits a unit-modulus phase sector plus a dissipative tension sector.  
> The correct picture is attenuated coherent transport, not pure norm-preserving evolution.

### On regime status

> The Born-Criterion Regime is not universal across all E₀ systems, but it is not marginal either.  
> It is best understood as a stable attractor regime for bounded exclusive transition episodes.

These two conclusions fit together.

Because E₀ is dissipative in magnitude, one should not expect universal unitary dynamics.  
Because E₀ often localizes into bounded exclusive episodes, one should expect frequent emergence of Born-like normalized support rules.

That is a coherent picture.

---

## 16. Next tasks

1. Formalize attenuated coherent transport as a theorem-style proposition.
2. Formalize the three-regime taxonomy.
3. Test whether controller decision points instantiate Regime A locally.
4. Explore whether Regime B admits a continuity-equation analogue.
5. Explore whether Regime C admits a branching support law.

---

## End of Note
