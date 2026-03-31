# E₀ Θ from v_rot — Worked Example
## Explicit path residue on equal-tension paths

**Status:** Working note  
**Date:** 2026-03-23  
**Language:** English  
**Purpose:** Show concretely, on the previously constructed equal-tension counterexample, how an orientational residue `Θ` can distinguish paths that scalar tension `S` cannot.

---

## 1. Goal

We already constructed two paths with equal total scalar tension:

```text
p1 = A → B → D
p2 = A → C → B → C → D
```

with:

```text
S(p1) = S(p2) = 4
```

The present task is to define an explicit connection-like residue from the rotational part of the transition field and show:

```text
Θ(p1) ≠ Θ(p2)
```

This is the concrete bridge from the equal-tension counterexample to the phase-derivation program.

---

## 2. Reminder: where Θ comes from in E₀

The current E₀ formal paper defines:

```text
v = v_grad + v_rot
ω(x,y) = 1/2 · (v_rot(x,y) - v_rot(y,x))
Θ(p) = Σ ω(e)
```

So the plan is simple:

1. assign a local rotational residue `v_rot` on relevant directed edges,
2. compute `ω` by antisymmetrization,
3. sum `ω` along each path.

If a loop carries rotational residue, then `Θ` should detect it even when scalar tension does not.

---

## 3. The graph

We use the same directed edges:

```text
A → B
B → D
A → C
C → B
B → C
C → D
```

To compute `ω`, it is enough to specify values of `v_rot` on the directed edges we traverse and on their reverse partners when present. Missing reverse edges are treated as `0`, exactly as allowed in the current E₀ formal paper.

---

## 4. A minimal rotational assignment

We choose the simplest nontrivial assignment.

### Non-cyclic edges carry no rotational residue

```text
v_rot(A,B) = 0
v_rot(B,A) = 0

v_rot(B,D) = 0
v_rot(D,B) = 0

v_rot(A,C) = 0
v_rot(C,A) = 0

v_rot(C,D) = 0
v_rot(D,C) = 0
```

### The embedded cycle carries rotational asymmetry

Let:

```text
v_rot(C,B) = +1
v_rot(B,C) = -1
```

This is the smallest clean choice that encodes a directed orientational bias on the internal loop fragment.

---

## 5. Compute ω edge by edge

Using:

```text
ω(x,y) = 1/2 · (v_rot(x,y) - v_rot(y,x))
```

we obtain:

### Direct path edges

```text
ω(A,B) = 1/2 · (0 - 0) = 0
ω(B,D) = 1/2 · (0 - 0) = 0
ω(A,C) = 1/2 · (0 - 0) = 0
ω(C,D) = 1/2 · (0 - 0) = 0
```

### Cycle edges

```text
ω(C,B) = 1/2 · (1 - (-1)) = 1
ω(B,C) = 1/2 · (-1 - 1) = -1
```

At first glance this seems to cancel on the two-edge loop `C → B → C`, and that is exactly the place where we need to be careful.

---

## 6. Why naive antisymmetry alone is not enough

If we sum the antisymmetric edge residues directly on the loop fragment, we get:

```text
Θ(C→B→C) = ω(C,B) + ω(B,C) = 1 + (-1) = 0
```

So with this perfectly antisymmetric two-edge assignment, the loop leaves no net residue.

This is not a failure of the general idea.
It shows something subtler:

> a two-edge back-and-forth loop with perfectly mirrored local residue is too symmetric to serve as a nontrivial holonomy example.

That means the previous equal-tension counterexample was sufficient to show that `S` is incomplete, but not yet rich enough to exhibit nonzero `Θ` under the current antisymmetric connection rule.

So we now strengthen the example in the minimal possible way.

---

## 7. Strengthened graph with a genuine 3-cycle

Replace the loop fragment with a directed 3-cycle.

Use states:

```text
A, B, C, E, D
```

and edges:

```text
A → B
B → D
A → C
C → E
E → B
B → C
C → D
```

Now define:

### Path 1

```text
p1 = A → B → D
```

### Path 2

```text
p2 = A → C → E → B → D
```

Choose tensions:

| Edge | Tension |
|------|---------|
| A → B | 1 |
| B → D | 3 |
| A → C | 1 |
| C → E | 1 |
| E → B | 1 |
| B → D | 1 |
|

To avoid duplicating `B→D` with two different values, fix the paths instead as:

```text
p1 = A → B → F → D
p2 = A → C → E → B → D
```

This is becoming messy in notation, so we reset cleanly in the next section.

---

## 8. Clean final worked example

Use six states:

```text
A, B, C, E, F, D
```

Directed edges:

```text
A → B
B → F
F → D

A → C
C → E
E → B
B → D
```

And an additional edge to close a local 3-cycle around the detour region:

```text
C → E
E → B
B → C
```

Now define:

### Path 1

```text
p1 = A → B → F → D
```

### Path 2

```text
p2 = A → C → E → B → D
```

Choose tensions:

| Edge | Tension |
|------|---------|
| A → B | 1 |
| B → F | 1 |
| F → D | 2 |
| A → C | 1 |
| C → E | 1 |
| E → B | 1 |
| B → D | 1 |
|

Then:

```text
S(p1) = 1 + 1 + 2 = 4
S(p2) = 1 + 1 + 1 + 1 = 4
```

So again:

```text
S(p1) = S(p2) = 4
```

---

## 9. Rotational structure on the detour region

Now assign a genuine oriented rotational residue on the local 3-cycle:

```text
B → C → E → B
```

Choose:

```text
v_rot(B,C) = +1
v_rot(C,E) = +1
v_rot(E,B) = +1
```

and all reverse directions absent or treated as `0`.

All other traversed edges carry zero rotational residue:

```text
v_rot(A,B) = 0
v_rot(B,F) = 0
v_rot(F,D) = 0
v_rot(A,C) = 0
v_rot(B,D) = 0
```

Since reverse partners are zero, antisymmetrization gives:

```text
ω(B,C) = 1/2 · (1 - 0) = 1/2
ω(C,E) = 1/2 · (1 - 0) = 1/2
ω(E,B) = 1/2 · (1 - 0) = 1/2
```

All non-cycle edges have:

```text
ω = 0
```

---

## 10. Compute Θ for the relevant paths

### Path 1

```text
p1 = A → B → F → D
```

All edges on `p1` have zero connection residue, so:

```text
Θ(p1) = 0
```

### Path 2 as written

```text
p2 = A → C → E → B → D
```

This path includes:

- `C → E` with `ω = 1/2`
- `E → B` with `ω = 1/2`

but not `B → C`.

Hence:

```text
Θ(p2) = 0 + 1/2 + 1/2 + 0 = 1
```

Therefore:

```text
S(p1) = S(p2) = 4
but
Θ(p1) = 0
Θ(p2) = 1
```

This is the worked distinction we wanted.

---

## 11. What exactly this shows

This example is already enough to prove a crucial claim:

> Equal scalar tension does not imply equal ordered path residue.

One path reaches the same endpoint with the same total burden while passing through a region of nontrivial rotational structure.
The scalar quantity `S` cannot represent that distinction.
The additive residue `Θ` can.

This is the first concrete demonstration that the path descriptor must be at least two-component:

- burden-like magnitude,
- orientational residue.

---

## 12. Why this is the right bridge to Ψ

Now the logic becomes much tighter.

### We already have additive scalar burden

```text
S(p ∘ q) = S(p) + S(q)
```

### We now have additive ordered residue

By construction:

```text
Θ(p ∘ q) = Θ(p) + Θ(q)
```

provided `Θ` is defined as a path sum of local connection terms.

Therefore the natural joint representation is:

```text
Ψ(p) = exp(-S(p)) exp(iΘ(p))
```

because then path concatenation becomes multiplication:

```text
Ψ(p ∘ q) = Ψ(p) Ψ(q)
```

This is no longer just pretty notation.
It is the minimal compact carrier that preserves both additive structures at once.

---

## 13. Important honesty note

This worked example does **not** yet prove that:

- the exact connection choice is unique,
- the complex exponential is uniquely forced,
- or every nontrivial loop must generate nonzero holonomy.

What it does prove is narrower and still significant:

> once E₀ admits a rotational residue layer, equal-tension paths can differ by a second additive path quantity, and the magnitude-phase representation becomes structurally motivated.

---

## 14. Next step

The next theorem-sized task is now precise:

> show that among candidate carriers of two additive path quantities, the complex magnitude-phase form is minimal and compositionally closed.

That is the point where phase stops being merely plausible and starts becoming necessary.

---

## 15. Final summary

The worked example can be compressed to one line:

```text
S(p1) = S(p2) = 4
Θ(p1) = 0
Θ(p2) = 1
```

Same burden. Different orientational residue.

That is the exact doorway through which E₀ must pass if it wants a complete path language.

---

## End of Note
