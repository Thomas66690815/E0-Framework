# E₀ Equal-Tension Path Counterexample
## Why scalar tension alone cannot exhaust path structure

**Status:** Working note  
**Date:** 2026-03-23  
**Language:** English  
**Purpose:** Construct an explicit example of two paths with equal total tension but different ordered / cyclic structure, thereby motivating the necessity of an additional path descriptor beyond scalar burden.

---

## 1. Goal

We want an example where:

```text
S(p1) = S(p2)
```

but where `p1` and `p2` are nevertheless structurally non-equivalent.

This is the exact kind of example needed for the phase-derivation program.

If such an example exists, then scalar path burden `S(p)` is not sufficient to characterize all path structure.
A second quantity becomes necessary.

---

## 2. Minimal setup

Consider four states:

```text
A, B, C, D
```

with directed edges:

```text
A → B
B → D
A → C
C → B
B → C
C → D
```

We choose edge tensions directly for the counterexample:

| Edge | Tension S(e) |
|------|--------------|
| A → B | 1 |
| B → D | 3 |
| A → C | 1 |
| C → B | 1 |
| B → C | 1 |
| C → D | 2 |

These values can be realized by many `Δ · R_eff` factorizations, so nothing essential depends on a unique primitive decomposition yet.

---

## 3. Two paths from A to D

Define:

### Path 1

```text
p1 = A → B → D
```

Then:

```text
S(p1) = S(A→B) + S(B→D) = 1 + 3 = 4
```

### Path 2

```text
p2 = A → C → B → C → D
```

Then:

```text
S(p2) = S(A→C) + S(C→B) + S(B→C) + S(C→D)
      = 1 + 1 + 1 + 1
      = 4
```

To make the equality exact, set:

| Edge | Revised Tension S(e) |
|------|----------------------|
| C → D | 1 |

Now we have:

```text
S(p2) = 1 + 1 + 1 + 1 = 4
```

Therefore:

```text
S(p1) = S(p2) = 4
```

---

## 4. Why the paths are not equivalent

Although the total scalar burden is equal, the paths differ in a decisive structural way.

### 4.1 Path 1 is simple

`p1` contains no internal looping behavior.
It is a direct two-step route from `A` to `D`.

### 4.2 Path 2 contains an internal cycle fragment

`p2` includes:

```text
C → B → C
```

This is a closed loop fragment embedded inside the full path.
Even though the path ultimately reaches the same endpoint `D`, it traverses a nontrivial cyclic structure on the way.

### 4.3 Consequence

A scalar sum of tensions cannot tell the difference between:

- a direct route of total burden 4,
- a route of total burden 4 that carries an internal cycle residue.

That means:

> equal tension does not imply equal path structure.

This is the precise opening needed for an additional descriptor.

---

## 5. Why order matters

The difference is not only that `p2` is longer.
The stronger point is that the ordering of edges includes a closed return.

Suppose we collapse all information into total scalar burden.
Then the following would become indistinguishable:

```text
A → B → D
A → C → B → C → D
```

as long as their scalar sums match.

But any framework that tracks:

- loop residue,
- ordered traversal,
- non-integrable local orientation,
- holonomy-like effects,

must distinguish them.

Therefore scalar burden is incomplete.

---

## 6. Reading this in E₀ terms

The present E₀ formalism already contains the structural place where the distinction can live.

If the local transition field decomposes as:

```text
v = v_grad + v_rot
```

then a simple path and a path containing an internal cyclic fragment can accumulate different orientational residue even when their scalar burdens match.

That is, we can have:

```text
S(p1) = S(p2)
```

but:

```text
Θ(p1) ≠ Θ(p2)
```

where `Θ` is the accumulated path residue derived from the connection / rotational structure.

This is exactly the kind of situation for which a phase-like descriptor becomes necessary.

---

## 7. Explicit residue sketch

Suppose the embedded cycle carries nonzero holonomy:

```text
Hol(C→B→C) ≠ 0
```

Then the path residues satisfy schematically:

```text
Θ(p2) = Θ(A→C) + Θ(C→B→C) + Θ(C→D)
```

whereas:

```text
Θ(p1) = Θ(A→B) + Θ(B→D)
```

Even if the scalar tensions happen to sum to the same value, the cyclic contribution changes the orientational class of the path.

Therefore:

- scalar burden class is equal,
- orientational class is not equal.

This is the cleanest reason a second quantity is needed.

---

## 8. Why this is not a triviality about path length

One might object that `p2` is longer, and that alone explains the difference.
But length is not the essential issue.

The essential issue is that we can always redistribute local tensions so that a longer path and a shorter path have the same total burden.
Once that is done, the scalar formalism has spent all its expressive power.
It has nothing left to represent cyclic residue.

The gap is not about number of steps.
It is about **type of ordered structure**.

---

## 9. Stronger variant

The same argument can be sharpened.

Construct two paths with:

- same start,
- same end,
- same number of steps,
- same total tension,

but with one path enclosing a nontrivial cycle in the underlying directed structure and the other not.

Such examples are easy to generate once a non-integrable local field is allowed.

So the counterexample is not an edge case.
It is generic whenever path orientation matters.

---

## 10. The real conclusion

This example proves a limited but crucial claim:

> Scalar path tension is not a complete invariant of path structure.

That does **not** yet prove complex phase uniquely.
But it does prove the need for an additional descriptor whenever E₀ wants to represent:

- loop residue,
- order sensitivity,
- non-integrable traversal structure,
- holonomy-capable path distinctions.

This is exactly the doorway needed for the next derivation step.

---

## 11. Next step

The next task is now sharper:

> Define a path quantity `Θ` that distinguishes `p1` and `p2` in a compositionally stable way.

Then test whether:

```text
Θ(p ∘ q) = Θ(p) + Θ(q)
```

and whether the joint representation:

```text
Ψ(p) = exp(-S(p)) exp(iΘ(p))
```

is the minimal closed carrier of:

- scalar burden,
- orientational residue,
- and interference under path summation.

---

## 12. Provisional summary

The counterexample can be summarized in one sentence:

> Two E₀ paths can carry equal total tension while differing by embedded cyclic residue, so tension alone cannot be the full story.

That is enough to justify moving to the next stage of the derivation.

---

## End of Note
