# M_H Adjudication — Research Note v1

**Date:** 2026-03-28
**Status:** Conceptual analysis complete. No code changes yet.
**Prior state:** M_H = 1/(1+κ) implemented, `curvature_modulation=True` available but experimental.

---

## 1. Problem Statement

The transition field formula is:

    v(x,y) = Δ(x,y) · M_H(x,y) · exp(−S_eff(x→y))

The current implementation sets `M_H(x,y) = 1/(1+κ)` where `κ = mean |Θ(face)|` over directed triangles containing edge x→y. An alternative `M_H = exp(−κ)` was documented but never implemented. The question was: which formula is correct?

**This turns out to be the wrong question.**

Both formulas take holonomy-derived curvature as input. The deeper problem is that this input is structurally redundant with information already carried by ω and Θ.

---

## 2. The Redundancy Diagnosis

The current κ is:

    κ(x,y) = mean |ω(x,y) + ω(y,z) + ω(z,x)|   over all triangle-closing z

This is literally `mean |Θ(face)| ` — the absolute face holonomy averaged over local triangles. It takes the same information that ω and Θ already encode, strips the phase (via |·|), and squeezes it through a damping function.

**Consequence:** The current M_H converts phase information into a scalar penalty. This is not new information — it is information loss.

---

## 3. What M_H Should Be — Canon Analysis

### 3.1 What the Canon Says

Neither `e0-canon-plain.txt` nor `e0-canonical-reference.txt` mention M_H. The Paper Draft (§5.1) introduces it as a "historization modulation term" and immediately simplifies to M_H = 1.

In `ontodynamics.txt`, the relevant primitives are:

- **§3.2 Local Realization:** "Difference can be realized partially, not only globally. Realization is necessarily local with respect to scale."
- **§3.3 Connection:** "Connection means: multiple difference components are realized together."
- **§3.4 Gradual Overlap:** "Connections possess degree. Overlap is graduated, not binary. Stability requires non-zero overlap."

### 3.2 The Key Insight from §3.4

"Overlap is graduated" is a statement about the **relationship of a connection to other connections** — not about the connection itself. This points toward M_H as a measure of how a given edge relates to its structural neighborhood.

### 3.3 The Label Was Wrong

"Topological invariant" was introduced in the Canon Alignment report (§9.3), not in the Canon itself. This label wrongly suggests a global, homotopy-type quantity. What the Canon actually demands (if anything) is a **local overlap functional**.

---

## 4. Six Readings of "Local Realization" — Evaluated

| Reading | Description | Status after Canon analysis |
|---------|-------------|---------------------------|
| A: Structural Redundancy | Many common neighbors = well-realized | Canon does NOT say "many neighbors = better" |
| B: Functional Necessity | Only path = maximally real | Inverts overlap semantics |
| C: Loop Embedding | Part of coherent cycles | Redundant with Θ |
| D: Directed Support | Surrounding flow supports this edge | Close, but mis-formulated |
| E: Perturbation Stability | Small change doesn't affect v | Derived, not primitive |
| F: Historical Confirmation | Frequently used = strongly realized | Redundant with R_eff |
| **G: Graduated Overlap** | Co-realization strength with neighborhood | **Directly from §3.4** |

**Reading G survives as the only non-redundant, canon-aligned interpretation.**

---

## 5. New Working Definition

> **M_H(x,y) = graduated overlap of the connection x→y with its co-realized neighborhood**

Not:
- a second damping on S_eff (redundant with R/S)
- a masked holonomy magnitude (redundant with Θ)
- an imported curvature penalty (no canon basis)
- a topological invariant (wrong label)

But rather:
- How strongly is the transition x→y **structurally supported** by the realized transitions around it?
- Measured through the **strength of co-realized connections** (the v-values of supporting edges), not through their count or phase.

---

## 6. Formal Sketch

    overlap(x→y) = Σ_{z ∈ T(x,y)} f(v(x,z), v(z,y))

where:
- T(x,y) = set of nodes forming triangles with edge x→y
- f = aggregation function over supporting edge strengths
- v(·,·) = transition field values of the supporting edges

This measures: **How well is x→y embedded in other strong transitions?**

### Why This Is New Information

| Existing quantity | Sees overlap? |
|---|---|
| Δ(x,y) | No — property of the edge itself |
| R(x,y), S_eff | No — property of the edge itself |
| ω(x,y) | No — compares x→y with y→x, not with neighborhood |
| Θ(γ) | Partially — but path-global, not edge-local |
| ψ (path amplitude) | Yes, but at path level, not edge level |

**M_H as overlap functional would be the edge-local equivalent of what ψ does globally.**

---

## 7. Open Questions Before Code

### Q1: Neighborhood Convention for Directed Graphs

What is T(x,y)? Options:
- z such that edges x→z and z→y both exist (forward triangles)
- z such that edges y→z and z→x both exist (reverse triangles)
- Both directions
- All z reachable from {x,y} within distance 1

### Q2: What Is the Aggregation Function f?

- f(a,b) = min(a,b) — bottleneck: weakest link determines support
- f(a,b) = a·b — multiplicative: both supporting edges must be strong
- f(a,b) = (a+b)/2 — average
- f(a,b) = √(a·b) — geometric mean

Then the overlap is normalized (e.g., by the number of triangles or by v(x,y) itself).

### Q3: Mapping to M_H ∈ (0, 1]

How does the raw overlap value map to M_H?
- Canon §3.4: "Stability requires non-zero overlap" → M_H = 0 must not occur
- M_H = 1 when overlap is "typical" or "sufficient" → neutral condition
- M_H < 1 when overlap is weak (bridge edge, poorly embedded)
- Could M_H > 1? (Edge with unusually strong support boosted above baseline)

### Q4: Falsification Domain

Which E₀ domain demonstrates a path-choice problem that Δ, R, S_eff, ω, Θ together cannot solve, but a local overlap factor would solve?

If no such domain exists, M_H = 1 is correct and final.

---

## 8. Candidate Family (for future implementation)

### 8.1 Jaccard / Neighborhood Overlap

    M_H^J(x,y) = |N(x) ∩ N(y)| / |N(x) ∪ N(y)|

- Simplest possible existence test
- Purely structural (ignores edge weights)
- Canon connection: "graduated overlap" (§3.4) — but unweighted

### 8.2 Forman-Ricci Curvature

    Ric_F(x→y) based on parallel transport structure

- Directly edge-based, discrete, weight-aware
- Positive = well-embedded (cluster), negative = bridge
- Better structural proxy for overlap degree

### 8.3 Ollivier-Ricci Curvature

    κ_OR(x,y) = 1 − W₁(μ_x, μ_y) / d(x,y)

- Conceptually strongest: measures neighborhood convergence
- Computationally expensive (optimal transport)
- Not a first candidate for implementation

### Priority

Jaccard as existence test → Forman as operational candidate → Ollivier as theoretical target.

---

## 9. Relation to Existing Code

| File | Current state | Implication |
|------|--------------|------------|
| `connection.py` | `edge_curvature()` and `M_H_factor()` exist | Will need rethinking — κ from holonomy is wrong input |
| `landscape.py` | `curvature_modulation` flag, `_M_H_cache` | Infrastructure is reusable, content changes |
| `test_curvature_modulation.py` | 35 tests for holonomy-based M_H | Tests encode wrong semantics if M_H changes |
| Paper 3 §5 | Documents current M_H | Needs update |
| Canon Alignment §9.3 | Labels M_H as "topological invariant" | Label must change |

**No code changes are proposed in this note.** This is a conceptual prerequisite.

---

## 10. Decision Record

| Date | Decision |
|------|----------|
| 2026-03-26 | M_H = 1/(1+κ) implemented, alternative exp(−κ) documented |
| 2026-03-28 | Both formulas identified as wrong question — input (holonomy-κ) is redundant with Θ |
| 2026-03-28 | New working definition: M_H as graduated overlap functional (from Ontodynamics §3.4) |
| 2026-03-28 | "Topological invariant" label retired |
| pending | Q1–Q4 resolution before any code changes |
| pending | Existence test on falsification domain |
