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

This is literally `mean |Θ(face)|` — the absolute face holonomy averaged over local triangles. It takes the same information that ω and Θ already encode, strips the phase (via |·|), and squeezes it through a damping function.

**Consequence:** The current M_H converts phase information into a scalar penalty. This is not new information — it is information loss.

### 2.1 Right Geometry, Wrong Observable

Importantly, the *triangle-finding* in `edge_curvature()` is correct — it identifies
the right local neighborhood structure (directed triangles through x→y). The error is
not in *where* to look, but in *what* to measure there. The current code measures
|Θ(face)| (phase mismatch); it should measure structural support (transition strength
of the bypass edges). The topology search is reusable; only the observable changes.

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

**Why "overlap" and not "realization":** In the Canon, "realization" (§3.2) IS the
transition — that role is already filled by v itself. M_H does not realize; it modulates
v based on the *degree of overlap* with co-realized neighbors. Calling M_H a
"realization factor" would conflate it with Δ/R, which already determine realization
strength. "Overlap degree" is the precise term.

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

This gives M_H a clear architectural role: ψ aggregates interference across all paths
(global); M_H aggregates co-realization across the immediate neighborhood (local).
They operate at different scales but encode the same structural principle —
"how much does the surrounding structure support this transition?"

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

## 8. Answers — Empirically Grounded (2026-03-28)

### Empirical Survey

45 domains across 12 test files were analyzed for directed triangle support:

    T(x,y) = {z : x→z ∈ E and z→y ∈ E, z ∉ {x,y}}

Results:

| Domain | Edges | Edges with T≠∅ | Finding |
|--------|-------|-----------------|---------|
| Gordian Trap | 10 | 0 | No triangles. M_H trivially 1. |
| Coupled Resonators | 8 | 0 | Two 3-cycles but no directed bypass. M_H trivially 1. |
| Nested Loop | 6 | 1 (B→C via X) | First real overlap signal: B→X→C supports B→C. |
| Custom Differentiator | 7 | 2 (S→B via C, C→GOAL via B) | **S→A→GOAL vs S→B→GOAL: identical v, S_eff — only overlap differs.** |

**Key finding:** On most E₀ domains (DAGs, trees, simple cycles), directed triangle support is zero everywhere. M_H is trivially neutral. This is correct behavior — M_H should ONLY activate when the graph has genuine overlapping bypass structure.

### A1: Neighborhood Convention (Q1)

**Decision:** Forward-directed 2-hop support.

    T(x,y) = {z : x→z ∈ E and z→y ∈ E, z ∉ {x,y}}

Rationale:
- E₀ graphs are overwhelmingly unidirectional (30+ of 45 domains)
- In-neighbors and undirected neighbors would fail on most domains
- Forward triangles represent genuine **alternative paths**: if x→y exists
  and x→z→y also exists, the transition x→y is "confirmed" by a bypass
- This is the directed analog of shared neighborhood support
- Empty T → M_H = 1 automatically (correct default for simple domains)

### A2: Aggregation Function (Q2)

**Decision:** Geometric mean of supporting leg strengths.

    overlap(x→y) = Σ_{z ∈ T(x,y)} √(v(x,z) · v(z,y))

Rationale:
- Geometric mean: symmetric in both legs, zero if either leg is blocked
- Uses v (transition field) as the weight — the E₀-native strength measure
- Sum over T: multiple supporting paths contribute additively
- Units: same as v (because √(v·v) = v), so directly comparable

Empirical verification (nested loop):
- B→C: overlap = √(v(B,X) · v(X,C)) = √(0.3767 · 0.3767) = 0.3767
- All other edges: overlap = 0.0000
- This correctly identifies B→C as the only structurally supported edge.

### A3: Mapping to M_H (Q3)

**Decision:** Domain-relative normalization with neutral default.

    If max_overlap = 0 across all edges:  M_H(x,y) = 1  ∀(x,y)
    Otherwise:  M_H(x,y) = (overlap(x,y) + ε) / (max_overlap + ε)

where:
- max_overlap = max over all edges of overlap(x,y)
- ε = max_overlap / 4 (floors M_H at 0.2 for zero-support edges)

Properties:
- M_H ∈ [0.2, 1.0] when overlap structure exists
- M_H = 1.0 for the best-supported edge
- M_H = 0.2 for unsupported edges (in a domain with supported edges)
- M_H = 1.0 everywhere on simple DAGs/trees (no signal → no modulation)
- Canon: M_H > 0 always (§3.4: stability requires non-zero overlap)

Why not boost M_H > 1? The canon says "stability requires non-zero overlap"
— it defines overlap as a stability floor, not a bonus ceiling. Well-supported
edges are the baseline (M_H = 1); poorly-supported edges are below baseline.

Why ε = max_overlap/4? This ensures:
- Minimum M_H = 0.2 (non-zero, moderate penalty, not catastrophic)
- The ratio max_overlap:ε = 4:1 provides clear differentiation
- A bridge edge in a domain with rich overlap gets 0.2× the strength — visible
  in amplitude but doesn't eliminate the transition

### A4: Falsification Domain (Q4)

**Decision: Custom Overlap Differentiator.** Constructed domain:

    S → A → GOAL      (bridge path: no triangle support)
    S → B → GOAL      (supported path: S→C→B supports S→B)
    S → C → B
    C → GOAL           (C→B supports both S→B and creates C→GOAL support via B)

All edges: δ=1.0, R=0.5. Both paths S→A→GOAL and S→B→GOAL have:
- Identical sum_v = 1.2131
- Identical sum_S_eff = 1.0000
- Identical ω = 0 (no reverse edges, no asymmetry)

**The only difference is overlap:**
- S→A: overlap = 0 (no z with S→z and z→A)
- S→B: overlap = 0.6065 (z=C: S→C and C→B both exist)

This makes S→B→GOAL the structurally better-supported path.
With M_H active, the amplitude for S→B→GOAL would be higher.
Without M_H, both paths are indistinguishable.

**This is a genuine falsification domain:** a path-choice problem where
existing quantities (Δ, R, S_eff, ω, Θ) cannot differentiate, but
graduated overlap can.

Additional domains where M_H activates:
- Nested loop (build_nested_loop): B→C is the only supported edge
- Any domain with ≥1 directed triangle (mesh, tetrahedron, diamond)

Domains where M_H is trivially 1 (correct):
- Gordian Trap (Θ/ω solve the problem, not overlap)
- All linear/tree DAGs
- Simple un-bypassed cycles

---

## 9. Relation to Existing Code

| File | Current state | Implication |
|------|--------------|------------|
| `connection.py` | `edge_curvature()` and `M_H_factor()` exist | κ from holonomy is wrong input; overlap logic needed |
| `landscape.py` | `curvature_modulation` flag, `_M_H_cache` | Infrastructure reusable; cache content changes |
| `test_curvature_modulation.py` | 35 tests for holonomy-based M_H | Tests valid as **curvature** tests; new overlap tests needed separately |
| Paper 3 §5 | Documents current M_H | Needs update if overlap-M_H replaces holonomy-M_H |
| Canon Alignment §9.3 | Labels M_H as "topological invariant" | Label → "graduated overlap functional" |

**Existing curvature modulation stays as-is.** The B2 curvature tests validate the
holonomy/face-structure machinery, which has independent value. The new overlap-based
M_H would be a **separate mechanism** — possibly a new flag like `overlap_modulation`
— not a replacement for the curvature infrastructure.

---

## 10. Decision Record

| Date | Decision |
|------|----------|
| 2026-03-26 | M_H = 1/(1+κ) implemented, alternative exp(−κ) documented |
| 2026-03-28 | Both formulas identified as wrong question — input (holonomy-κ) is redundant with Θ |
| 2026-03-28 | New working definition: M_H as graduated overlap functional (from Ontodynamics §3.4) |
| 2026-03-28 | "Topological invariant" label retired |
| 2026-03-28 | Q1 resolved: T(x,y) = forward-directed 2-hop support set |
| 2026-03-28 | Q2 resolved: overlap = Σ √(v(x,z)·v(z,y)) geometric mean |
| 2026-03-28 | Q3 resolved: domain-relative normalization, M_H ∈ [0.2, 1.0], neutral on simple domains |
| 2026-03-28 | Q4 resolved: custom overlap differentiator domain as falsification test |
| 2026-03-28 | 45 domains surveyed — overlap is non-trivial on <10, trivially 1 on >35 |
| pending | Implementation as existence test (Jaccard-level, v-weighted) |
| pending | Empirical validation on falsification domain |
