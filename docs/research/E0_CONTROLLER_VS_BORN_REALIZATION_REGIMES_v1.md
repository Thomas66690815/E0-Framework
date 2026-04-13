# E₀ — Controller vs Born Realization Regimes

**Status:** Architecture Decision Record (ADR) — **Active**  
**Date:** 2026-03-25  
**Decision ID:** ADR-0007-v1  
**Supersedes:** ADR-0007-v0  

---

## 1. Context

The E₀ system has a fully implemented amplitude overlay:

- Ψ(p) = exp(−S + iΘ)
- I = |ΣΨ|²
- P = I / ΣI

ADR-0007-v0 decided that the controller SHALL remain deterministic (argmax).
It listed "implement sampling as optional mode" as future work.

**Path H (commit `b3ac2c3`)** has now completed that future work:
Born sampling is implemented as `HybridMode.BORN_SAMPLING`, an opt-in
alternative realization mode alongside the deterministic default.

This v1 update reflects the implemented architecture.

---

## 2. The Three Modes

### 2.1 GREEDY_ONLY — Baseline

- Rule: pick the action with lowest δ (greedy tension)
- No amplitude overlay computation
- Deterministic, fastest

### 2.2 AMPLITUDE_ON_DISAGREE — Structural Control (Default)

- Rule: compute I(a) for all actions; if argmax(I) ≠ greedy, override
- Semantics: select the most coherent structure
- Properties:
  - deterministic
  - reproducible
  - overrides greedy only when amplitude disagrees

### 2.3 BORN_SAMPLING — Realization Regime (Opt-In)

- Rule: compute I(a) for all actions; sample from P(a) = I(a) / Σ I
- Semantics: realize one possibility according to support
- Properties:
  - stochastic
  - distributional outcomes
  - explores all actions with nonzero intensity

---

## 3. Decision (Updated)

The E₀ Controller SHALL support three hybrid modes:

1. **GREEDY_ONLY** — no overlay
2. **AMPLITUDE_ON_DISAGREE** — deterministic override (default)
3. **BORN_SAMPLING** — probabilistic realization (opt-in)

The **default** remains deterministic (AMPLITUDE_ON_DISAGREE).
Born sampling is available for use cases that require exploration
or distributional analysis.

---

## 4. Rationale

### 4.1 Original Rationale Preserved

The v0 rationale for deterministic default still holds:
- Reproducibility for regression testing
- Clear causal attribution
- Stable evaluation metrics

### 4.2 Why Born Sampling Was Added

Path H demonstrated that Born sampling provides value in specific regimes:

1. **Multi-goal exploration:** On G5 (3 goals), argmax deterministically
   picks the same goal every time. Born sampling reaches all 3 goals
   across trials — essential for exploration and coverage analysis.

2. **Geometry-failure resilience:** On Gordian with `simple` geometry,
   argmax and greedy AGREE on the trap action (A). Born sampling
   sometimes picks B randomly, escaping the trap. This shows sampling
   can help when geometry is insufficient.

3. **Distributional analysis:** Born sampling generates outcome
   distributions that can be compared against theoretical predictions
   (P ∝ I convergence verified in H2 tests).

### 4.3 Key Finding: Geometry > Decision Rule

The most important result from Path H:

> The choice of geometry (simple vs goal_reaching) has more impact
> on controller success than the choice of decision rule (argmax vs sampling).

With `goal_reaching` geometry, argmax dominates or matches Born sampling
on all domains. With `simple` geometry on Gordian, both modes fail —
but sampling has a random chance of escaping.

**Implication:** Invest in geometry before switching decision rules.

---

## 5. Architecture

The two-layer separation from v0 is preserved, but both layers
are now accessible within the same controller:

```
┌──────────────────────────────────────────────┐
│  E0Controller                                │
│                                              │
│  hybrid_mode = GREEDY_ONLY                   │
│             | AMPLITUDE_ON_DISAGREE  (default)│
│             | BORN_SAMPLING                   │
│                                              │
│  ┌────────────────────┐                      │
│  │  Amplitude Overlay  │  (shared by both)   │
│  │  I = |ΣΨ|²         │                      │
│  └────────┬───────────┘                      │
│           │                                  │
│     ┌─────┴─────┐                            │
│     │           │                            │
│  argmax(I)   sample(P)                       │
│  Layer A     Layer B                         │
│  structural  realization                     │
│  (default)   (opt-in)                        │
│                                              │
└──────────────────────────────────────────────┘
```

Both layers compute the same overlay. They differ only in the
final selection step: argmax vs sample.

---

## 6. Implementation

### 6.1 Controller (`controller.py`)

```python
class HybridMode(str, Enum):
    GREEDY_ONLY = "greedy_only"
    AMPLITUDE_ON_DISAGREE = "amplitude_on_disagree"
    BORN_SAMPLING = "born_sampling"
```

Born sampling branch in `select_hybrid()`:
```python
if self.hybrid_mode == HybridMode.BORN_SAMPLING:
    return self._born_sample(overlay, escalated, esc_type)
```

`_born_sample()` method:
```python
def _born_sample(self, overlay, escalated, esc_type):
    actions = [ai.action for ai in overlay.action_infos]
    probs = [ai.probability for ai in overlay.action_infos]
    chosen = random.choices(actions, weights=probs, k=1)[0]
    return (chosen, escalated, esc_type, overlay, True)
```

### 6.2 Persistence (`memory_os.py`)

`BORN_SAMPLING` survives MemOS save → load → restore cycle.
The `hybrid_mode` string value `"born_sampling"` is stored in
`RuntimeSnapshot.controller_params` and reconstructed via
`HybridMode(value)` in `restore_controller()`.

---

## 7. Evidence (Path H — 27 Tests, C22)

| Family | Tests | Result |
|--------|------:|--------|
| H1 Valid transitions | 3 | All Born-sampled actions are valid |
| H2 Distribution | 3 | Frequencies converge to P ∝ I |
| H3 Gordian comparison | 4 | Geometry matters more than decision rule |
| H4 Diamond efficiency | 3 | Both modes reach G in 2 steps |
| H5 G5 multi-goal | 3 | Born reaches all 3 goals; argmax picks 1 |
| H6 Argmax dominance | 3 | argmax steps ≤ Born steps (goal_reaching) |
| H7 Variance | 2 | argmax = 0, Born > 0 on multi-path |
| H8 Coherence loss | 2 | Born sometimes picks trap (cost of exploration) |
| H9 MemOS round-trip | 2 | Mode survives persistence cycle |
| H10 StepResult | 2 | Born actions marked as overridden |

Full details in `E0_TEST_REGISTRY_v2.md`, Claim C22.

---

## 8. Relationship to ADR-0007-v0

v0 stated:
> "Born sampling is NOT used in the core controller loop."

v1 updates this to:
> "Born sampling is available as an opt-in alternative mode.
>  The default core loop remains deterministic (argmax)."

The original two-layer architecture is preserved. The change is
that Layer B (realization) is now accessible within the controller
as `HybridMode.BORN_SAMPLING`, rather than being deferred to
external analysis tools.

---

## 9. Future Work

- Compare Born sampling on larger domains (O2: G5 with |G| > 5)
- Investigate adaptive mode selection (switch between argmax/Born
  based on domain topology or confidence metrics)
- Evaluate Born sampling for SU(2) intensity distributions (O4)

---

## 10. Summary

> The controller selects the most coherent structure (argmax, default).
> Born sampling realizes one possibility according to support (opt-in).
> Geometry choice dominates over decision rule choice.

These are distinct operations. Both are now available.

---

_End of document._
