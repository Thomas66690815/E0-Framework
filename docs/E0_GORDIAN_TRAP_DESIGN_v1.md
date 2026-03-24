# E₀ Gordian Trap Design v1

**Status:** Test design / falsification note  
**Date:** 2026-03-24  
**Purpose:** Define a purpose-built stress test that distinguishes local greedy selection from phase-sensitive amplitude evaluation under controlled destructive interference.

---

## 1. Why this test exists

The project has now established:

- greedy trap-correction in bounded domains,
- summation-geometry differentiation,
- constructive and destructive interference,
- and distinct exploration vs realization regimes.

The next decisive test should therefore not merely check whether the overlay works again.
It should test the strongest open claim:

> Can the E₀ amplitude layer correctly reject a locally attractive path whose endpoint support is structurally annihilated by destructive interference, while preferring a worse-looking path that builds coherent forward support?

This is the Gordian Trap.

---

## 2. Core idea

Construct two action families from a common start state.

### Path family A — the decoy

- lower local burden
- apparently attractive to greedy selection
- near the target, splits into multiple phase-opposed continuations
- net endpoint support collapses by destructive interference

### Path family B — the detour

- higher local burden
- unattractive to greedy selection
- supports several coherent continuations
- net endpoint support remains high or is amplified constructively

The desired result is:

```text
greedy   → chooses A
amplitude → chooses B
hybrid    → overrides greedy and chooses B
```

---

## 3. What this test is meant to falsify

The Gordian Trap is not just another demo.
It directly challenges three possibilities.

### F1 — "The amplitude layer is only longer lookahead"

If the amplitude layer wins only because it sees farther, but not because phase matters, then the trap is weaker than claimed.

### F2 — "Interference is cosmetic"

If phase cancellation does not actually change the decision under designed destructive conditions, then phase is not yet operationally meaningful.

### F3 — "Hybrid improvement is just geometry bias"

If the hybrid only prefers B because of path counting inflation rather than controlled interference, then the current interpretation is too strong.

A well-designed Gordian Trap addresses all three.

---

## 4. Required design features

The domain must satisfy all of the following.

### 4.1 Shared start, competing first actions

There must be a common source state:

```text
START → A1
START → B1
```

with `A1` locally cheaper than `B1`.

### 4.2 Comparable endpoint semantics

Both path families must aim toward the same endpoint class, not totally different goals.  
Otherwise the test becomes a semantic mismatch rather than an interference test.

### 4.3 Intrinsic phase opposition on the decoy family

The decoy family must contain continuations whose phases differ enough to drive cancellation at the comparison point.

The target condition is:

```text
cos(ΔΘ_A) < 0
```

for the dominant subpaths of family A.

### 4.4 Constructive support on the detour family

The detour family should contain subpaths whose phase relation is aligned or near-aligned:

```text
cos(ΔΘ_B) > 0
```

### 4.5 Controlled geometry evaluation

The test should be run under at least:

- `simple` geometry
- `first_arrival` geometry

and optionally `prefix` for contrast.

This ensures the result is not a pure path-proliferation artifact.

---

## 5. Recommended domain shape

A good first design is a two-channel target domain.

### Skeleton

```text
START → A1 → A2 → T_left
                  ↘
                   GOAL
                  ↗
START → A1'→ A2'→ T_right

START → B1 → B2 → B3 → GOAL
```

But this should be upgraded so that the A-family has at least two competing branches to the same endpoint support class with opposite phase tendency.

A more explicit structure:

```text
START
 ├─ A1 ─ A2 ─ X ─ GOAL
 │          └─ Y ─ GOAL
 └─ B1 ─ B2 ─ B3 ─ GOAL
```

with:

- `S(A1)` lower than `S(B1)`
- total family A endpoint amplitude reduced by phase opposition between `X→GOAL` and `Y→GOAL`
- total family B endpoint amplitude reinforced by near-aligned continuations

---

## 6. Phase design principle

The crucial design variable is not only burden.
It is the accumulated phase.

The domain should therefore be built so that the decoy branches satisfy approximately:

```text
Θ(A-path-1) - Θ(A-path-2) ≈ π
```

which implies near-maximal destructive interference.

Meanwhile the detour family should satisfy:

```text
Θ(B-path-i) - Θ(B-path-j) ≈ 0
```

for its dominant paths.

The exact target need not be perfect `π`. Even strong negative cosine is enough.

---

## 7. First implementation strategy

Use the current controller infrastructure rather than inventing a special solver.

### Step 1 — Build explicit landscape

Define the graph directly in a mini-domain test fixture.

### Step 2 — Assign local burdens

Ensure:

```text
S_eff(START→A1) < S_eff(START→B1)
```

so greedy reliably selects A.

### Step 3 — Shape rotational structure

Use connection / phase settings so that:

- A-family subpaths oppose one another
- B-family subpaths remain aligned

### Step 4 — Compare four modes

For the same domain, evaluate:

1. greedy
2. overlay with `simple`
3. overlay with `first_arrival`
4. hybrid controller

### Step 5 — Record full evidence

For each mode, capture:

- winner
- intensities
- probabilities
- path counts
- coherent vs incoherent totals
- phase differences on dominant subpaths

---

## 8. Expected success signature

A successful Gordian Trap should look like this.

### Greedy

```text
chooses A
```

because local burden is lower.

### Amplitude (simple / first_arrival)

```text
chooses B
```

because the A family collapses under destructive interference.

### Hybrid

```text
overrides A → B
```

### Diagnostics

- A-family coherent intensity much lower than incoherent sum
- B-family coherent intensity comparable to or greater than incoherent sum
- phase opposition visible in the dominant A subpaths

---

## 9. Failure signatures and interpretation

### Failure type 1 — Greedy and amplitude both choose A

Interpretation:

- interference is too weak,
- or phase construction is not yet strong enough,
- or geometry still includes stabilizing support for A.

### Failure type 2 — Amplitude chooses B only under prefix

Interpretation:

- likely path-family inflation artifact,
- not yet a robust interference result.

### Failure type 3 — first_arrival and simple disagree wildly

Interpretation:

- the domain is mixing exploration semantics and realization semantics unclearly,
- or endpoint class is underspecified.

### Failure type 4 — Hybrid does not improve outcome

Interpretation:

- the override criterion is insufficient,
- or the domain does not isolate the structural effect cleanly.

---

## 10. Minimal code deliverables

The coding agent should produce:

1. a dedicated mini-domain fixture (e.g. `build_gordian_trap_domain()`)
2. a test module (e.g. `e0_controller/test_gordian_trap.py`)
3. an exploration script or section in `explore_amplitude.py`
4. a compact results note in `docs/`

Suggested minimum tests:

- greedy selects decoy path
- amplitude under `simple` selects detour path
- amplitude under `first_arrival` selects detour path
- coherent intensity on decoy family < incoherent sum by large factor
- hybrid reaches goal where greedy degrades or stalls

---

## 11. Relationship to current research threads

This test connects directly to three live questions.

### Summation geometry

It tests whether the amplitude result survives under disciplined geometries.

### Phase derivation

It pressures the current `Θ` implementation to prove that phase is operationally real.

### Born-like realization

It provides a bridge between:

- field-like exploration support,
- and endpoint-support / realization semantics.

That makes it more important than a normal trap test.

---

## 12. Recommended operational stance

The Gordian Trap should be treated as a **falsification-grade domain**, not merely as a showcase.

That means:

- explicit target behavior should be declared before running it,
- competing interpretations should be listed in advance,
- and any failure should be treated as informative rather than embarrassing.

---

## 13. Final conclusion

The Gordian Trap is the right next test because it isolates the strongest remaining question:

> Is the E₀ amplitude layer genuinely sensitive to destructive interference in a way that can override locally attractive but structurally doomed paths?

If the answer is yes under disciplined geometries, the amplitude layer moves from promising extension to serious structural mechanism.

---

## End of Document
