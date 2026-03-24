# E₀ Summation Geometry Regimes v1

**Status:** Draft (post-H4 milestone)  
**Date:** 2026-03-24  
**Purpose:** Define the conceptual interpretation of different summation geometries as distinct evaluation regimes within the E₀ amplitude system.

---

## 1. Why this document exists

The completion of Hypothesis H4 (Goal-with-Continuations domain) established that different summation geometries do not merely produce numerical differences — they correspond to **qualitatively different evaluation behaviors**.

This requires a shift in interpretation:

> The question is no longer "which geometry is correct?"  
> but "which geometry corresponds to which regime?"

---

## 2. The three geometries (recap)

- **prefix** — includes all admissible continuations up to horizon
- **simple** — includes only non-repeating (loop-free) paths
- **first_arrival** — includes only paths up to first encounter of goal set

---

## 3. Regime interpretation

### 3.1 Exploration regime (G_explore)

Represented by:

- `prefix`
- `simple` (preferred operational variant)

#### Definition

```text
Future = all reachable continuations within bounded horizon
```

#### Properties

- open-ended
- recursive
- loop-sensitive
- accumulates structural support across path families

#### Behavior

- captures forward-support trends
- sensitive to path multiplicity
- can suffer from path inflation (prefix)
- stabilized by loop restriction (simple)

#### Interpretation

> This regime behaves like a **field** over future possibilities.

---

### 3.2 Realization regime (G_realize)

Represented by:

- `first_arrival`

#### Definition

```text
Future = first realization of a designated goal state
```

#### Properties

- endpoint-focused
- non-recursive beyond goal
- horizon-stable (path count bounded by goal structure)
- insensitive to post-goal loops

#### Behavior

- isolates forward structure toward goal
- eliminates post-goal inflation
- can detect correct direction earlier than exploration geometries

#### Interpretation

> This regime behaves like a **measurement or projection** onto goal states.

---

## 4. Empirical evidence (H4)

In the Goal-with-Continuations domain:

- Goal node has outgoing edges and loop-back paths

Observed:

- `prefix` accumulates post-goal loop paths → intensity inflation
- `simple` reduces but does not eliminate this effect
- `first_arrival` stops at goal → stable path count and earlier correct decision

Key result:

> Only `first_arrival` detects the correct forward structure at the smallest horizon.

---

## 5. Relationship to amplitude semantics

The amplitude system defines:

```text
Ψ(p) = exp(-S(p)) · exp(iΘ(p))
I = |ΣΨ|²
```

The geometry determines **which paths are included in the sum**.

Thus:

- geometry defines the **semantic meaning of the amplitude**
- not just its numerical value

---

## 6. Connection to Born-like interpretation

The distinction aligns with two roles:

### Exploration

- evaluates distributed support over path families
- analogous to wave propagation

### Realization

- evaluates support at first endpoint encounter
- analogous to projection / measurement

This suggests that:

> Born-style intensity may correspond specifically to the realization regime.

(This remains a working hypothesis.)

---

## 7. Current operational stance

- `simple` is the best default for **controller operation** (robust exploration)
- `first_arrival` is critical for **goal semantics and validation**
- `prefix` is retained as an **upper-support exploratory baseline**

---

## 8. Open questions

- Can the regime selection be derived rather than chosen?
- What is the formal relationship between exploration and realization regimes?
- Can both regimes be unified in a single expression?
- How does phase Θ behave differently across regimes?

---

## 9. Key conclusion

Summation geometry is not an implementation detail.

> It defines the **interpretation of future structure**.

Different geometries correspond to different regimes:

- exploration (field-like)
- realization (measurement-like)

Understanding when to use each is now a central problem.

---

## End of Document
