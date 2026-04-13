# E₀ Summation Geometry Program
## How bounded path families should be selected, weighted, and compared

**Status:** Research note / design program  
**Date:** 2026-03-23  
**Language:** English  
**Purpose:** Define the next research step after the successful amplitude-overlay experiments: determine the correct summation geometry for path-family amplitudes so that coherent support is structurally meaningful without being distorted by uncontrolled loop proliferation.

---

## 1. Why this is now the main question

The amplitude overlay has now shown three important things:

1. it can correct local greedy trap choices,
2. it can strongly amplify coherent forward-support families,
3. it can exhibit genuine destructive interference when phase separation is large enough.

This means the overlay is no longer merely a technical curiosity.
It is now an active candidate for a richer E₀ decision layer.

That shifts the center of gravity.

The main question is no longer:

> “Does amplitude matter?”

That has already been answered positively.

The main question is now:

> **Which path families are legitimately allowed to contribute to an action amplitude?**

This is the summation geometry problem.

---

## 2. The observed warning sign

In the current-loop experiments, larger horizons can strongly amplify one action because many recursively related prefix paths contribute coherently.

This is not automatically wrong.
It may reflect real structural reinforcement.

But it creates a serious ambiguity:

- are we measuring genuine future support,
- or are we rewarding path-family multiplicity that arises only because the summation policy is too permissive?

So the next task is not to reject the overlay, but to discipline it.

---

## 3. The core principle

A path should contribute to an action amplitude only if its inclusion corresponds to a structurally meaningful alternative continuation of that action.

This means the summation set cannot be chosen ad hoc.
It must satisfy explicit criteria.

The right way forward is not to guess the final geometry immediately.
It is to define candidate geometries and evaluate them systematically.

---

## 4. Candidate summation geometries

We should treat the following as competing models.

### Geometry G1 — Prefix geometry (current overlay)

For current state `x` and first action `y`, include all admissible prefix paths:

```text
x → y → ...
```

with length up to `horizon_edges`.

This is the current implementation.

#### Strengths

- simple,
- exhaustive within the bound,
- captures rich coherent future support,
- already produced meaningful trap corrections.

#### Risks

- may overcount recursive revisitation families,
- may favor branches with many looping prefixes,
- horizon sensitivity can become dominated by proliferation rather than genuine structural direction.

---

### Geometry G2 — Leaf-only geometry

For current state `x` and first action `y`, include only paths of exactly length `horizon_edges` (or paths ending earlier only if no continuation exists).

#### Strengths

- suppresses prefix overcounting,
- forces comparison at a common forward depth,
- easier to interpret as “support at horizon h”.

#### Risks

- may throw away important early termination structure,
- may treat dead-end and ongoing paths awkwardly,
- can become brittle when horizons are small.

---

### Geometry G3 — First-arrival geometry

For each candidate target family, include only paths that reach a designated endpoint class for the first time.

Examples:

- first arrival at GOAL,
- first arrival at a frontier set,
- first arrival at a phase-comparison boundary.

#### Strengths

- avoids repeated loop contributions after effective arrival,
- closest to endpoint-support semantics,
- likely best for Born-like or realization-style regimes.

#### Risks

- requires defining target/frontier sets,
- less natural for open-ended exploratory control,
- may hide useful pre-arrival support structure.

---

### Geometry G4 — Simple-path geometry

Include only paths with no repeated states.

#### Strengths

- brutally suppresses loop inflation,
- easy to interpret,
- strong baseline for comparison.

#### Risks

- may be too restrictive for domains where revisitation is genuinely meaningful,
- may exclude real structural strategies,
- not obviously compatible with historized landscapes where revisits matter.

---

### Geometry G5 — Discounted revisit geometry

Allow repeated states, but multiply each path by a revisit penalty or loop-discount factor.

Schematic:

```text
Ψ'(p) = Ψ(p) · D_loop(p)
```

where `0 < D_loop(p) ≤ 1` decreases with repeated-state structure.

#### Strengths

- preserves revisitation as a real possibility,
- prevents uncontrolled loop-family domination,
- likely closest to controller intuition.

#### Risks

- introduces a new weighting rule,
- must be derived or at least justified,
- can become arbitrary if added too early.

---

### Geometry G6 — Coherence-cutoff geometry

Keep paths only while their magnitude coherence remains above a threshold:

```text
exp(-S(p)) ≥ C_min_path
```

or until incremental contribution falls below a support floor.

#### Strengths

- naturally suppresses very low-support long paths,
- compatible with E₀ burden/coherence logic,
- can reduce horizon arbitrariness.

#### Risks

- threshold choice matters,
- may still overcount medium-coherence loops,
- requires careful tolerance design.

---

## 5. The three geometries to test first

Not all candidates should be explored at once.

The best first comparison set is:

### Primary comparison trio

1. **G1 Prefix geometry** — current baseline
2. **G4 Simple-path geometry** — strict anti-loop baseline
3. **G3 First-arrival geometry** — endpoint-support baseline

This trio is strong because it spans:

- permissive support,
- restrictive support,
- and realization-oriented support.

If the same qualitative trap-correction results survive across all three, the overlay result becomes much more robust.

---

## 6. What to measure for each geometry

For each candidate geometry, the same diagnostics should be collected.

### 6.1 Agreement profile

At each state:

- deterministic choice,
- amplitude choice,
- agreement/disagreement.

### 6.2 Support concentration

For the candidate set:

- max `P(action)`,
- entropy or concentration measure over action support,
- size of gap between top two actions.

### 6.3 Path-family size

For each action:

- number of contributing paths,
- repeated-state frequency,
- average path length.

### 6.4 Coherent vs incoherent ratio

For each action:

```text
R_coh = |Σ Ψ(p)|² / Σ |Ψ(p)|²
```

This helps separate:

- support driven by mere multiplicity,
- support driven by genuine coherence.

### 6.5 Horizon sensitivity

Track how rankings change as `h` increases.

This is crucial for deciding whether a geometry is stable or pathological.

---

## 7. The decision criterion for a good geometry

A good summation geometry should satisfy as many of the following as possible.

### Criterion S1 — preserves known trap corrections

It should still detect the important non-greedy cases already found.

### Criterion S2 — reduces spurious loop inflation

Support should not explode merely because many recursive prefixes are available.

### Criterion S3 — remains phase-sensitive

Constructive and destructive interference should still be visible where structurally present.

### Criterion S4 — is interpretable

One should be able to say what a contributing path means.

### Criterion S5 — does not require arbitrary extra weighting too early

Geometries that work without introducing too many new parameters should be preferred initially.

---

## 8. My current expectation

Before running the comparison, my best structural guess is:

- **G1 Prefix geometry** is too permissive in loop-rich domains, but valuable as an exploratory upper-support view.
- **G4 Simple-path geometry** is probably too strict for final use, but excellent as a control baseline.
- **G3 First-arrival geometry** is likely the best candidate whenever the semantics are endpoint-oriented or realization-like.

So I do **not** expect one geometry to replace all others.
I expect a regime picture.

---

## 9. Likely regime split

The geometry may depend on what the controller is trying to do.

### Regime SG-A — exploratory support view

Use a permissive geometry such as G1 or G6 when the goal is to estimate broad future support.

### Regime SG-B — realization / endpoint selection view

Use a stricter geometry such as G3 when the semantics are “which endpoint-support family should count?”

### Regime SG-C — robustness / sanity baseline

Use G4 to test whether a result depends entirely on loops.

This is analogous to the earlier regime taxonomy: not one geometry for everything, but structurally matched geometries.

---

## 10. Immediate implementation advice

The cleanest next implementation step is **not** to replace the overlay.
It is to extend it so the geometry is selectable.

Suggested interface direction:

```python
analyze_controller_state(..., geometry="prefix")
```

with possible values:

- `"prefix"`
- `"simple"`
- `"first_arrival"`

This keeps the experiment controlled and lets the same fixtures compare multiple geometries.

---

## 11. Minimal development order

### Step 1

Implement **simple-path geometry** as the easiest contrast case.

Why first?
Because it requires no new semantic target definition and immediately tests whether current results depend on loops.

### Step 2

Implement **first-arrival geometry** for goal/frontier domains.

Why second?
Because it is the most likely candidate for endpoint-support semantics.

### Step 3

Compare all three (`prefix`, `simple`, `first_arrival`) on:

- trap domain,
- diamond domain,
- current-loop domain.

That will already answer most of the hard question.

---

## 12. What success would look like

The strongest positive outcome would be:

1. trap-correction survives under both prefix and simple-path geometries,
2. first-arrival geometry gives the clearest endpoint semantics,
3. destructive interference remains visible in the loop-current scenario,
4. loop inflation weakens significantly under simple-path or first-arrival restrictions.

If that happens, then the overlay is not only real — it becomes structurally disciplined.

---

## 13. What failure would look like

A concerning outcome would be:

- all important disagreements vanish once loops are restricted,
- support rankings become random across horizons,
- or destructive interference depends entirely on pathological path-family proliferation.

If that happens, then the current overlay would still be interesting, but not yet decision-ready.

---

## 14. Recommended next concrete deliverable

The next deliverable should be:

> a **Summation Geometry Comparison Note**

covering the three primary geometries (`prefix`, `simple`, `first_arrival`) across the three known domains.

That note should explicitly answer:

- which results are geometry-stable,
- which are geometry-sensitive,
- and which geometry best matches each controller regime.

---

## 15. Final conclusion

The right way to approach summation geometry is not to search immediately for one final formula.
It is to compare a small set of disciplined geometries against the phenomena already found.

The immediate next move is therefore:

> **treat summation geometry as a controlled model-comparison problem**.

That is the cleanest path from strong experiment to stable theory.

---

## End of Note
