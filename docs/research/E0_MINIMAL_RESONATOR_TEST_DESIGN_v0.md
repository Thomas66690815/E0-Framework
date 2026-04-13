# E₀ Minimal Resonator Test Design v0

**Status:** Experimental design (post-stability criterion)  
**Date:** 2026-03-24  
**Purpose:** Define the smallest controlled experiment that can distinguish a transient loop from a self-sustaining resonator in the E₀ framework.

---

## 1. Why this test exists

We now have a working stability hypothesis:

- structural reproduction
- coherence preservation
- historization balance against dissipation

But this remains conceptual until tested.

The next step is therefore not a full “mass module”, but the smallest experiment that asks:

> Can a closed interference structure in E₀ persist across repeated cycles instead of simply decaying away?

This is the Minimal Resonator Test.

---

## 2. Test objective

The test should separate two cases:

### Case A — transient loop

A loop exists, but its coherent support decays over repeated cycles.
No stable local structure forms.

### Case B — resonator

A loop exists and repeatedly reconstructs its internal structure.
Coherent local support remains bounded away from zero over time.

---

## 3. Minimal domain shape

The smallest useful topology should contain:

1. **one closed loop family**
2. **one leakage path** out of the loop region
3. **one observation node** where local support is measured

Suggested skeleton:

```text
        L1
      /    \
START       L2
      \    /
        L3 ---- OUT
```

Alternative explicit version:

```text
START → A → B → C → A   (closed loop)
                 \
                  OUT
```

The loop provides potential resonance.
The `OUT` edge provides a dissipative escape route.

---

## 4. Required measurements

For repeated traversals or repeated evaluation cycles, record:

### 4.1 Local coherent intensity

At a designated loop-support class:

```text
I_coh(t) = |Σ Ψ_loop_family(t)|²
```

### 4.2 Incoherent reference

```text
I_inc(t) = Σ |Ψ_loop_family(t)|²
```

### 4.3 Coherence ratio

```text
R_coh(t) = I_coh(t) / I_inc(t)
```

### 4.4 Local historization density

A loop-local quantity such as:

```text
H_loop(t) = Σ |δ_H(e)|   over loop edges
```

### 4.5 Leakage intensity

Support escaping via `OUT`:

```text
I_out(t)
```

---

## 5. Minimal success criterion

A candidate resonator should satisfy all of the following for a nontrivial time window:

### R1 — recurrent reconstruction

The loop family reproduces a comparable amplitude pattern after each cycle:

```text
Ψ_loop(t + T) ≈ Ψ_loop(t)
```

up to phase/sign symmetry.

### R2 — bounded coherent support

```text
I_coh(t) ≥ I_min > 0
```

for repeated cycles, rather than monotone collapse to zero.

### R3 — non-dominant leakage

```text
I_out(t) < I_coh(t)
```

for the stable regime.

### R4 — historization balance

Historization must not destroy the loop faster than the loop reconstructs itself.
Operationally:

```text
ΔI_coh / Δt  not strongly negative
```

while local `H_loop(t)` remains bounded or stabilizing.

---

## 6. Parameter regimes to compare

The experiment should not use one setting only.
It should scan at least three regimes.

### Regime M1 — low loop support

- moderate burden on loop edges
- strong leakage to `OUT`
- expectation: transient loop, no resonance

### Regime M2 — balanced loop

- loop edges low enough burden to preserve support
- leakage moderate
- expectation: borderline persistence

### Regime M3 — reinforced loop

- loop edges support constructive recurrence
- leakage weak
- expectation: strongest resonator candidate

---

## 7. Role of phase

The test should explicitly compare:

- same topology with low phase accumulation
- same topology with nontrivial holonomy

This checks whether persistence is merely a burden effect or truly an interference-supported structure.

---

## 8. Role of historization

Historization must be tested in two modes.

### H0 — frozen historization

No updates to `δ_H`.
This gives the pure wave/interference baseline.

### H1 — live historization

Normal `δ_H` updates applied.
This tests whether historization stabilizes or destroys the loop.

This comparison is essential.
Without it, one cannot tell whether persistence is caused by geometry alone or by memory-like reinforcement.

---

## 9. Suggested experimental protocol

### Step 1

Construct minimal loop domain with one leakage edge.

### Step 2

Measure amplitude behavior with historization frozen.

### Step 3

Enable historization and rerun over repeated cycles.

### Step 4

Compare:

- intensity persistence
- coherence ratio
- leakage growth
- loop-local `H`

### Step 5

Classify outcome:

- decaying loop
- metastable loop
- candidate resonator

---

## 10. Negative controls

At least two negative controls should be included.

### C1 — acyclic control

Remove the closing edge of the loop.
Expectation: no resonance possible.

### C2 — dephased control

Keep topology but alter parameters so phase coherence collapses.
Expectation: loop exists topologically but not resonantly.

---

## 11. Connection to later hypotheses

A successful minimal resonator would not yet prove mass.
But it would establish the missing prerequisite:

> persistent localized interference structure

That is the necessary bridge toward later hypotheses about:

- topological inertia
- proto-particle behavior
- SU(2)-stabilized resonant knots

---

## 12. Deliverables

The coding agent should eventually produce:

1. `build_minimal_resonator_domain()` fixture
2. `e0_controller/test_resonator.py`
3. an exploration script for repeated-cycle metrics
4. a short report documenting whether stability appears

---

## 13. Conclusion

The Minimal Resonator Test is the correct next experiment because it asks the smallest possible version of the deepest open question:

> Can E₀ generate persistent local structure from closed interference plus historization?

If yes, later mass/inertia hypotheses become much more serious.
If no, the stability criterion must be revised before any stronger physical interpretation is attempted.

---

## End of Document
