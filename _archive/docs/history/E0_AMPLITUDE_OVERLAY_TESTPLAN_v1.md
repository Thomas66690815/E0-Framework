# E₀ Amplitude Overlay Test Plan
## Validation strategy for `e0_controller/amplitude_overlay.py`

**Status:** Test plan  
**Date:** 2026-03-23  
**Language:** English  
**Purpose:** Define a rigorous test strategy for the analysis-only amplitude overlay layer, with special attention to correctness, normalization, horizon behavior, and controller-comparison semantics.

---

## 1. Why this plan is needed

The amplitude overlay has now produced the first nontrivial divergences from the current deterministic controller in exactly the structurally interesting cases:

- local traps,
- bounded-horizon forward support,
- coherent multi-path amplification.

That makes the module too important to remain untested.

The goal of this plan is therefore **not** to test the whole E₀ mathematics again.  
The goal is narrower:

> verify that `amplitude_overlay.py` correctly builds bounded continuation families, aggregates path amplitudes by first action, produces valid intensities and normalized support, and compares these results consistently against the controller’s current local decision rule.

---

## 2. Scope of what should be tested

The following units and behaviors should be covered.

### 2.1 Path enumeration behavior

- bounded depth respected,
- admissibility respected,
- path prefixes included correctly,
- no missing direct one-edge path,
- filtering by first action works correctly.

### 2.2 Amplitude aggregation behavior

- `psi_total` per action equals the sum of the constituent path amplitudes,
- intensity equals `abs(psi_total) ** 2`,
- probabilities normalize to 1 when total intensity is positive,
- sort order is descending by intensity.

### 2.3 Controller-comparison behavior

- deterministic choice is taken from the current controller without mutating controller state,
- admissible action list matches controller admissibility,
- overlay can disagree without causing side effects,
- escalation cases are handled without crashing.

### 2.4 Horizon sensitivity behavior

- `horizon_edges=1` reduces to first-hop paths only,
- larger horizons add continuation families,
- path count grows in the expected bounded way,
- amplitude choice may change with horizon without violating invariants.

---

## 3. Proposed test structure

Recommended structure:

```text
e0_controller/test_amplitude_overlay.py
```

with four sections:

1. **Enumeration tests**
2. **Aggregation and normalization tests**
3. **Controller consistency tests**
4. **Known-phenomenon regression tests**

This keeps the module independent and easy to expand.

---

## 4. Test fixtures to prepare

At minimum, define three reusable test landscapes.

### Fixture A — Minimal chain

```text
A → B → C
```

Use this for:

- horizon basics,
- one-action cases,
- direct-path inclusion,
- trivial normalization.

### Fixture B — Simple branch

```text
A → B
A → C
```

with no further continuation.

Use this for:

- horizon=1 behavior,
- admissible action listing,
- probability normalization,
- deterministic/amplitude agreement in a simple local case.

### Fixture C — Trap / forward-support domain

Use the already observed mini-domain where:

- `A` branches to `B` and `C`,
- `C` is locally cheaper but leads into a loop/trap,
- `B` carries richer coherent forward support.

Use this for:

- disagreement regression,
- horizon sensitivity,
- no-mutation guarantee under repeated overlay analysis.

### Fixture D — Diamond domain

Use the domain where:

- `S` branches to `A`, `B`, `C`,
- `C` is the local greedy trap,
- `A` and `B` lead to rich forward structure,
- constructive interference already appears clearly.

Use this for:

- multi-path coherent amplification,
- regression on known disagreement at `S`,
- path-family aggregation checks.

---

## 5. Core invariants to assert in every relevant test

These should appear repeatedly across the suite.

### Invariant 1 — Probabilities are valid

If total intensity is positive:

```text
Σ P(action) = 1
```

up to floating-point tolerance.

Also:

```text
0 ≤ P(action) ≤ 1
```

for every action.

### Invariant 2 — Intensity is nonnegative

```text
I(action) ≥ 0
```

for every action.

### Invariant 3 — Path counts are coherent

Every `ActionAmplitudeInfo.path_count` must equal `len(paths)`.

### Invariant 4 — Admissible actions match controller filter

The overlay’s `admissible_actions` must match:

```python
controller._admissible_neighbors(current)
```

exactly, modulo ordering if sorting differs.

### Invariant 5 — Direct path is always present

For every admissible action `y`, the path:

```text
[current, y]
```

must appear in the action path family.

---

## 6. Enumeration tests

### Test E1 — `horizon_edges=1` returns only direct one-edge paths

Fixture: simple branch.

Expected:

- one path per admissible action,
- each path is exactly `[current, action]`,
- no longer paths included.

### Test E2 — bounded expansion at `horizon_edges=2`

Fixture: minimal chain or branch with continuation.

Expected:

- direct path included,
- one-step continuation paths included,
- no paths longer than 2 edges.

### Test E3 — first-action filtering works

Fixture: branching domain.

Expected:

- `_filter_paths_by_first_action(paths, "B")` returns only paths whose second state is `B`,
- same for `C`,
- no cross-contamination.

### Test E4 — inadmissible edges never appear

Fixture: graph with one infinite-resistance or absent branch.

Expected:

- no path includes an inadmissible transition,
- admissible list excludes it.

---

## 7. Aggregation and normalization tests

### Test A1 — one-action case gives `P=1`

Fixture: minimal chain at a state with only one outgoing admissible edge.

Expected:

- exactly one `ActionAmplitudeInfo`,
- probability is 1.0,
- amplitude choice equals deterministic choice.

### Test A2 — `psi_total` equals explicit sum of path amplitudes

Fixture: small branching fixture with two or three known paths.

Expected:

- recompute `sum(path_psi(...))` explicitly,
- compare to stored `psi_total`.

### Test A3 — intensity equals `abs(psi_total)**2`

Expected exactly up to floating tolerance.

### Test A4 — zero total intensity does not crash

This is defensive.

It may be hard to generate with current bounded admissible paths, but if a synthetic case is available where all amplitudes are zero, the overlay should:

- not divide by zero,
- leave probabilities at 0.0.

If such a case is awkward to construct, this test can be deferred but the code path should be documented.

---

## 8. Controller consistency tests

### Test C1 — overlay does not mutate controller recent state

This is very important.

Procedure:

- snapshot `controller._recent`,
- call `analyze_controller_state(...)`,
- assert `_recent` unchanged.

### Test C2 — overlay does not increment historization

Procedure:

- snapshot `controller.landscape.historization.tau`,
- run overlay,
- assert `tau` unchanged.

### Test C3 — deterministic choice reported by overlay matches `select_next`

Procedure:

- call overlay,
- call `controller.select_next(current)` separately,
- compare choices and escalated flag.

### Test C4 — escalation state does not crash analysis

Fixture: dead-end or filtered state.

Expected:

- overlay returns a report cleanly,
- admissible list may be empty,
- deterministic choice may be escalation-derived or `None`,
- no exception.

---

## 9. Known-phenomenon regression tests

These are the most scientifically valuable tests.

### Test R1 — trap disagreement at `A`

Fixture: the existing trap domain.

Expected:

- deterministic choice is the locally cheaper trap branch,
- amplitude choice is the forward-support branch,
- this disagreement is stable for the selected horizon.

This should be pinned to the horizon where it was observed, not asserted for all horizons.

### Test R2 — diamond-domain disagreement at `S`

Fixture: diamond domain.

Expected:

- deterministic choice = local greedy trap `C`,
- amplitude choice = `A` (or whichever branch remains the known coherent winner),
- `C` has clearly lower probability than the coherent branches.

### Test R3 — coherent amplification exceeds incoherent sum expectation in the diamond domain

Use the interference-rich fixture.

Expected:

- coherent intensity differs from the naive single-path ranking,
- constructive amplification is visible for the rich branches.

This can be asserted more conservatively as:

```text
I(action) > max individual path intensity
```

for at least one known action.

### Test R4 — horizon sensitivity is stable, not random

Fixture: trap domain at `A`.

Expected:

- overlay returns deterministic, reproducible values for fixed horizons,
- the known choice changes across at least one horizon boundary,
- but core invariants stay intact.

This test should **not** overfit exact floating values unless necessary.  
It should assert the pattern, not every decimal.

---

## 10. Assertions that should avoid overfitting

Some results are scientifically meaningful but numerically fragile.
To keep the suite robust, avoid asserting:

- exact full `psi_total` complex values unless the fixture is extremely small,
- exact full probability decimals beyond reasonable tolerance,
- exact path-ordering if two actions are almost tied.

Prefer asserting:

- sign / ordering relationships,
- normalization,
- agreement/disagreement status,
- monotonicity or threshold gaps,
- and explicit horizon-conditioned patterns.

---

## 11. Tolerance policy

Use `assertAlmostEqual` or equivalent tolerances for:

- probabilities,
- intensities,
- complex real/imaginary parts,
- normalization sums.

Recommended starting tolerance:

```text
1e-9 for simple fixtures
1e-6 for larger aggregate comparisons
```

depending on path-count growth.

---

## 12. Suggested implementation order

Implement tests in this order.

### Phase 1 — Safety and invariants

- E1
- A1
- A2
- A3
- C1
- C2
- C3

These give fast confidence that the module is mechanically sound.

### Phase 2 — Behavioral coverage

- E2
- E3
- E4
- C4

These extend coverage to boundaries and edge cases.

### Phase 3 — Scientific regression cases

- R1
- R2
- R3
- R4

These lock in the actual discoveries.

This order keeps the suite stable while preserving the novel phenomena.

---

## 13. Deliverables

The minimum deliverable for the first test pass should be:

1. `e0_controller/test_amplitude_overlay.py`
2. at least one small helper fixture builder module or local fixture functions
3. documented comments in the tests indicating which scenarios are:
   - invariant checks,
   - regression checks,
   - or exploratory checks.

---

## 14. Recommended next test plan after this one

Once the overlay tests are green, the next plan should be:

> a deliberately destructive-interference domain

with:

- converging path families,
- larger `Θ` separation,
- and at least one case where coherent intensity is **lower** than incoherent accumulation.

That will test the true phase power of the overlay beyond constructive reinforcement.

---

## 15. Final summary

The immediate mission is simple:

> prove that the amplitude overlay is mechanically correct, state-safe, normalization-correct, and regression-stable exactly where the new structural phenomena were observed.

That will turn the current findings from strong exploration into durable evidence.

---

## End of Note
