# E₀ G5 Edge Case Suite v1

**Status:** Experimental design (post multi-goal formalization)  
**Date:** 2026-03-25  
**Purpose:** Define a disciplined edge-case suite for evaluating the robustness, selectivity, and limits of goal-reaching geometry G5 under increasingly complex goal sets.

---

## 1. Motivation

Phase 3q established:

- single-goal G5 resolves prefix inflation and enables interference-based routing
- multi-goal G5 confirms that coherence is relative to a goal set `G`
- alternative-goal support can rescue an action that is destructively suppressed relative to one goal

This raises the next critical question:

> How robust is G5 when the goal set becomes larger, noisier, weaker, or internally contradictory?

This suite is designed to answer that.

---

## 2. Core evaluation questions

The edge-case suite should test five distinct questions.

### Q1 — Goal-set growth

What happens as `|G|` increases from 1 to many?

### Q2 — Irrelevant goals

Does adding weak or unreachable goals distort the action ordering?

### Q3 — Conflicting goals

What happens when different goals support different competing actions?

### Q4 — Rescue vs dilution

When does alternative-goal support usefully rescue a path, and when does it merely wash out selectivity?

### Q5 — Stability of ranking

Does G5 still produce clear action orderings, or does the distribution flatten as the goal set expands?

---

## 3. Formal object under test

Recall the multi-goal G5 definition:

```text
Ψ(a, G) = Σ_{g ∈ G} Σ_{p ∈ Paths_g(a)} Ψ(p)
I(a, G) = |Ψ(a, G)|²
a* = argmax_a I(a, G)
```

The suite tests how the mapping

```text
G ↦ ordering over actions
```

behaves under edge conditions.

---

## 4. Test families

### 4.1 Family A — Goal-count expansion

Construct a domain with:

- one action strongly coherent toward one goal
- one action moderately coherent toward several goals
- one action weakly coherent toward many goals

Test with:

- `G = {g1}`
- `G = {g1, g2}`
- `G = {g1, g2, g3}`
- ... up to a small fixed number (e.g. 5)

**Question:** does one action dominate through meaningful support, or do many weak goals flatten the ranking?

---

### 4.2 Family B — Irrelevant-goal injection

Add goal states that are:

- unreachable
n- reachable only through negligible amplitude
- reachable only through highly incoherent paths

Compare:

- base goal set `G_base`
- `G_base ∪ G_irrelevant`

**Desired result:** irrelevant goals should not significantly perturb the ordering.

---

### 4.3 Family C — Competing-goal conflict

Construct a topology where:

- action A is best for `g1`
- action B is best for `g2`
- action C is locally cheapest but globally incoherent

Test:

- `G = {g1}`
- `G = {g2}`
- `G = {g1, g2}`

**Question:** how does G5 combine genuinely conflicting goal support?

---

### 4.4 Family D — Rescue threshold

Use a Gordian-style topology where:

- A is suppressed toward `g1`
- A has coherent support toward `g2`
- B is coherent toward `g1`

Gradually vary the strength of A→`g2` support.

**Question:** at what threshold does alternative-goal support rescue A from suppression?

---

### 4.5 Family E — Ranking sharpness

Measure not only the winner but the shape of the distribution.

Track:

- top-1 probability
- top-2 gap
- entropy over action probabilities

**Question:** does selectivity remain sharp as G grows, or does G5 become too permissive?

---

## 5. Required metrics

For each scenario, record at minimum:

### 5.1 Action metrics

- `I(a, G)` for each action
- `P(a, G)` for each action
- winner `argmax_a I(a, G)`

### 5.2 Ranking metrics

- top-1 minus top-2 probability gap
- entropy of action distribution
- stability of rank ordering across changes in `G`

### 5.3 Goal contribution diagnostics

For each action `a`, decompose:

```text
Ψ(a, G) = Σ_g Ψ(a, g)
```

and record:

- which goals contribute positively
- which goals are suppressed by interference
- whether rescue occurs through a small number of strong goals or many weak ones

---

## 6. Success criteria

A robust G5 implementation should satisfy all of the following.

### S1 — Stability under irrelevant goals

Adding irrelevant goals should not substantially change the ranking.

### S2 — Controlled rescue

Alternative-goal rescue should occur when coherent support is structurally real, not from negligible noise paths.

### S3 — Preserved selectivity

Even under multi-goal aggregation, the action ranking should remain meaningfully ordered.

### S4 — Context sensitivity without collapse

Different goal sets may legitimately change the winner, but not in an erratic or arbitrary way.

---

## 7. Failure signatures

### F1 — Goal-set saturation

As goals are added, all actions approach similar probabilities.

Interpretation:

- G5 loses selectivity
- multi-goal aggregation may need weighting or normalization

### F2 — Irrelevant-goal drift

Weak or unreachable goals change the winner.

Interpretation:

- G5 is too sensitive to low-value support

### F3 — Rescue by noise

An action is “rescued” by many tiny, incoherent goal contributions.

Interpretation:

- aggregation is too permissive

### F4 — Ranking instability

Tiny changes in `G` produce large, discontinuous ranking flips.

Interpretation:

- coherence over goal sets may need structure beyond plain summation

---

## 8. Optional extension: weighted G5

If the suite reveals selectivity loss, test a weighted extension:

```text
Ψ(a, G, w) = Σ_{g ∈ G} w_g · Ψ(a, g)
```

with weights `w_g ≥ 0`.

This is not part of core G5 yet, but should be considered if large-goal-set robustness fails.

---

## 9. Deliverables for the coding agent

The coding agent should eventually produce:

1. one or more synthetic domain builders for Families A–E
2. a dedicated test module (e.g. `e0_controller/test_g5_edge_cases.py`)
3. an exploration script that prints ranking changes as `G` varies
4. a short report summarizing where G5 remains sharp and where it degrades

---

## 10. Strategic significance

This suite determines whether G5 is:

- merely correct for small, clean target sets,
- or a scalable coherence operator for structured goal landscapes.

That distinction is critical for future work on:

- landscape evaluation
- contextual decision systems
- and later resonator / structure-emergence hypotheses

---

## 11. Conclusion

The G5 Edge Case Suite is the correct next stress test because it asks the question opened by the multi-goal result:

> If coherence is relative to a goal set, how far can that principle be pushed before it loses selectivity or stability?

Answering that is necessary before G5 can be treated as a mature general operator.

---

_End of document._