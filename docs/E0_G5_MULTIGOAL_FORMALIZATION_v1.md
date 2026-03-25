# E₀ G5 Multi-Goal Formalization v1

**Status:** Derived from Phase 3q empirical results  
**Date:** 2026-03-25  
**Scope:** Formal definition of goal-reaching geometry (G5) extended to multi-goal sets

---

## 1. Motivation

Phase 3q established that goal-reaching geometry (G5) resolves prefix inflation and enables interference-based routing.

Subsequent multi-goal experiments demonstrate a new effect:

> A path suppressed by destructive interference relative to one goal may remain coherent relative to another goal.

This requires extending G5 from a single-goal formulation to a **goal-set formulation**.

---

## 2. Definition

Let:

- G = {g₁, g₂, ..., gₙ} be a set of goal states
- Paths(p) be all admissible paths from current state

### 2.1 Path contribution

Each path contributes amplitude:

Ψ(p) = exp(−S(p)) · exp(iΘ(p))

---

### 2.2 Goal-filtered path families

For each goal g ∈ G:

Paths_g = { p ∈ Paths | p terminates at g }

---

### 2.3 Multi-goal amplitude aggregation

Total amplitude per action a:

Ψ(a, G) = Σ_{g ∈ G} Σ_{p ∈ Paths_g(a)} Ψ(p)

---

### 2.4 Intensity (Born-style)

I(a, G) = |Ψ(a, G)|²

---

### 2.5 Decision rule

Select action:

a* = argmax_a I(a, G)

---

## 3. Key Property: Relative Interference

Destructive interference is not absolute.

For a path family P:

- Interference may cancel contributions toward g₁
- while remaining constructive toward g₂

Therefore:

> Interference is defined relative to the goal set G.

---

## 4. Rescue Effect

Let:

- P₁ = paths to g₁ (destructively interfering)
- P₂ = paths to g₂ (constructive)

Then:

Ψ_total = Ψ(P₁) + Ψ(P₂)

If Ψ(P₁) ≈ 0 but Ψ(P₂) ≠ 0:

> The action is "rescued" by alternative goal support.

---

## 5. Empirical Evidence (Phase 3q)

Observed in multi-goal Gordian domain:

- Single-goal (G = {GOAL}): A1 suppressed
- Multi-goal (G = {GOAL, GOAL2}): A1 dominant

Ordering:

A1 > B1 > C1

Single-goal behavior remains intact (regression preserved).

---

## 6. Interpretation

G5 is not a goal selector.

It is a **coherence evaluator over a goal set**.

This implies:

- Paths are not intrinsically "good" or "bad"
- They are coherent relative to a chosen G

---

## 7. Consequences

### 7.1 Context dependence

Changing G changes:

- interference structure
- action ordering
- system behavior

---

### 7.2 Structural stability

Multi-goal aggregation reduces over-elimination of path families.

---

### 7.3 Generalisation

G5(G) defines a family of evaluation operators parameterised by goal set G.

---

## 8. Open Questions

1. How large can G be before selectivity degrades?
2. How should irrelevant or weak goals be handled?
3. Does coherence converge as |G| → large?

---

## 9. Relation to Phase 3q

- G5 (single goal) → routing correctness
- G5 (multi-goal) → structural coherence evaluation

---

## 10. Conclusion

Multi-goal G5 establishes:

> Coherence is not absolute but relative to a goal set.

This extends E₀ from goal-directed decision-making

to a system capable of evaluating structured landscapes of possibilities.

---

_End of document._