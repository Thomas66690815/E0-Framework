# E₀ Summation Geometry Comparison
## Prefix vs Simple vs First-Arrival

**Status:** Comparison framework / live analysis note  
**Date:** 2026-03-23  
**Language:** English  
**Purpose:** Provide a disciplined comparison structure for the three currently implemented summation geometries in `e0_controller/amplitude_overlay.py`:

- `prefix`
- `simple`
- `first_arrival`

The goal is to determine which observed amplitude effects are geometry-stable, which are geometry-sensitive, and which are likely artifacts of overly permissive path-family inclusion.

---

## 1. Why this note exists

The project has now reached the point where the key question is no longer whether the amplitude overlay matters at all. That has already been established.

The key question is now:

> Which summation geometry yields structurally meaningful amplitude support without uncontrolled distortion from path-family proliferation?

This note is therefore not a speculative theory paper.  
It is a comparison frame for the next decisive experiment.

---

## 2. The three geometries under comparison

### 2.1 Prefix geometry

Current permissive baseline.

For current state `x` and action `y`, include all admissible prefix continuations:

```text
x → y → ...
```

up to the bounded horizon.

### 2.2 Simple-path geometry

Restrictive anti-loop baseline.

Include only paths with no repeated states.

### 2.3 First-arrival geometry

Endpoint-oriented baseline.

Include only continuations that stop extending once a designated goal/frontier set is first reached.

---

## 3. The decision question

For each state under analysis, compare:

```text
deterministic controller choice     = argmin S_penalized
amplitude choice (prefix)           = argmax I_prefix
amplitude choice (simple)           = argmax I_simple
amplitude choice (first_arrival)    = argmax I_first_arrival
```

The point is not only to identify agreement/disagreement, but to classify the *kind* of effect.

---

## 4. Classification categories

### 4.1 Geometry-stable effect

An amplitude effect is geometry-stable if the qualitative result survives across all three geometries.

Example:

- deterministic picks trap,
- prefix picks escape branch,
- simple picks escape branch,
- first-arrival picks escape branch.

This is the strongest possible result.

### 4.2 Geometry-sensitive effect

An effect is geometry-sensitive if it appears under one or two geometries but not all.

This is not automatically a defect.
It usually means the effect belongs to a particular E₀ regime.

### 4.3 Geometry-pathological effect

An effect is geometry-pathological if it appears only under the most permissive geometry and collapses under even mild restriction.

Such effects should be treated with caution until justified.

---

## 5. Comparison matrix template

Use one row per analytically relevant state.

| Domain | State | Det | Prefix | Simple | First-arrival | Stable? | Interpretation |
|---|---|---|---|---|---|---|---|
| Trap | A |  |  |  |  |  |  |
| Trap | B |  |  |  |  |  |  |
| Diamond | S |  |  |  |  |  |  |
| Diamond | A |  |  |  |  |  |  |
| Diamond | B |  |  |  |  |  |  |
| Diamond | M |  |  |  |  |  |  |
| Current-Loop | START |  |  |  |  |  |  |

This table should be the executive summary.

---

## 6. What to record beyond the choice label

For each geometry and state, record at least:

- winning action,
- probability / support gap between top two actions,
- number of contributing paths,
- coherent vs incoherent support ratio where relevant,
- horizon used,
- whether repeated states were present in the contributing family.

Without these extra diagnostics, the same winner label can hide very different structural reasons.

---

## 7. Domain-by-domain comparison targets

### 7.1 Trap domain

Main question:

> Does the trap correction at the critical branching state survive once loop-heavy prefix proliferation is removed?

Interpretation guide:

- if yes under `simple`, the effect is probably real,
- if yes under `first_arrival`, it is also endpoint-semantically robust,
- if only yes under `prefix`, caution is required.

### 7.2 Diamond domain

Main questions:

1. Does the rejection of the greedy dead-end trap remain under all geometries?
2. Do the `A` and `B` branches keep their support advantage over `C`?
3. Does the `B → S` / `M → N` structure remain meaningful once loops are restricted?

This domain is ideal for separating:

- genuine coherent forward support,
- from recursive support inflation.

### 7.3 Current-loop domain

Main questions:

1. Does destructive interference remain visible under `simple` or `first_arrival`?
2. How much of the large support growth is due to recursive prefix accumulation?
3. Does the ranking of the main actions change when loops are controlled?

This is the key domain for testing the legitimacy of strong phase effects.

---

## 8. Evaluation criteria

A good summation geometry should satisfy as many of these as possible.

### Criterion G1 — preserves trap correction

The geometry should still detect the known failures of purely local greedy selection.

### Criterion G2 — suppresses spurious support inflation

The geometry should not produce massive support growth solely from recursive path-family multiplication.

### Criterion G3 — preserves genuine phase effects

Constructive and destructive interference should remain visible where structurally present.

### Criterion G4 — is semantically interpretable

One should be able to explain why a path belongs to the summed family.

### Criterion G5 — does not require unnecessary extra weighting

A geometry that works without yet introducing loop-discount parameters is preferable at this stage.

---

## 9. Expected role of each geometry

### Prefix

Best read as:

> exploratory upper-support view

It is useful precisely because it is permissive, but it may overcount recursively available support.

### Simple-path

Best read as:

> robustness baseline

If an effect survives here, it is much harder to dismiss as loop artifact.

### First-arrival

Best read as:

> endpoint / realization semantics baseline

If an effect survives here, it is likely relevant for goal-directed or Born-like regimes.

---

## 10. Provisional hypotheses to test

The next comparison should explicitly test these hypotheses.

### H1

The trap-correction effect is geometry-stable.

### H2

The strongest support explosions in loop-rich domains are geometry-sensitive and shrink substantially under `simple` and `first_arrival`.

### H3

Destructive interference remains visible in the current-loop domain even after permissive prefix overcounting is reduced.

### H4

`first_arrival` gives the clearest semantics in goal-oriented domains, while `prefix` remains useful as a broader exploratory-support measure.

---

## 11. How to interpret likely outcomes

### Outcome A — stable trap correction, reduced loop inflation

This is the best-case result.

Interpretation:

- amplitude effect is real,
- current prefix geometry is somewhat too permissive,
- but the core discovery survives restriction.

### Outcome B — trap correction disappears under restriction

Interpretation:

- the current effect may depend too strongly on recursive support counting,
- overlay remains interesting, but not yet controller-ready.

### Outcome C — destructive interference survives under restricted geometries

Interpretation:

- phase effects are robust,
- not just a byproduct of path multiplicity.

### Outcome D — first-arrival gives the cleanest goal semantics

Interpretation:

- the project likely needs a regime split between exploratory support and endpoint realization support.

---

## 12. Recommended deliverable format

The cleanest next evidence artifact should contain three layers.

### Layer 1 — executive table

One matrix summarizing winners and stability class.

### Layer 2 — per-domain notes

A short note for each domain describing what changed under each geometry.

### Layer 3 — interpretation section

A final section answering:

- which effects are geometry-stable,
- which effects are geometry-sensitive,
- which geometry best matches which controller regime.

---

## 13. Immediate next action

Populate this comparison note with actual results from the now-implemented geometry modes in `amplitude_overlay.py`.

The first pass should focus only on:

- the currently known critical states,
- one fixed horizon per domain,
- and qualitative winner stability.

Only after that should more detailed numeric comparisons be expanded.

---

## 14. Provisional conclusion

The summation geometry problem should now be treated as a controlled model-comparison problem.

The core question is not:

> “Which geometry is universally correct?”

but rather:

> “Which phenomena are stable across geometries, and which geometry best matches each E₀ regime?”

That is the correct level of maturity for the project at this stage.

---

## End of Note
