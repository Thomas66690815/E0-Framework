# E₀ — Mathematics ↔ Implementation Mapping v1.0

**Status:** Draft → v1.1 (updated to C122d, 2026-04-03)  
**Purpose:** Exact correspondence between formal E₀ mathematics and current implementation  
**Scope:** `e0_controller/` package  
**Language:** English

---

## 0. Overview

This document provides a direct mapping between:

- formal E₀ mathematical definitions,
- concrete implementation in code.

Goal:

> Every symbol in the mathematical framework has a clear runtime representation.

This document is not an intuitive introduction. It is a structural reference.

---

## 1. States and Transitions

### Mathematics

Let

```text
X = set of states
E ⊆ X × X
```

where transitions are directed.

A transition exists only if

```text
(x → y) ∈ E
```

### Implementation

In `e0_controller`, states are represented as string identifiers and transitions as directed edges.

- states are stored in `Landscape.states`
- transitions are stored in the adjacency structure of `Landscape`
- each transition is represented by `Edge(source, target)`

Relevant implementation elements:

- `landscape.py` → `Landscape`
- `primitives.py` → `Edge`

---

## 2. Difference Δ(x,y)

### Mathematics

```text
Δ : E → ℝ₊
```

Defined only for existing edges.

Properties:

- `Δ(x,x) = 0` only if such a self-edge is explicitly modeled
- `Δ(x,y) > 0` for structurally distinct reachable states
- undefined if no edge exists

### Implementation

Stored per edge and accessed through:

```python
Landscape.difference(source, target)
```

Behavior:

- returns `float` if the edge exists
- returns `None` if the edge does not exist (K3 fix)

Implementation source:

- `landscape.py`

---

## 3. Base Resistance R₀(x→y)

### Mathematics

```text
R₀ : E → ℝ₊
```

Each edge has a baseline resistance independent of current historization.

### Implementation

Stored per edge and accessed through:

```python
Landscape.base_resistance(source, target)
```

Implementation source:

- `landscape.py`

---

## 4. Historization H(e)

### Mathematics

For each edge `e`:

```text
H(e) = (U(e), F(e))
```

where:

- `U(e)` = success trace
- `F(e)` = failure trace

### Implementation

Implemented in `Historization`.

Official snapshot/export methods exist after MemOS cleanup.

Relevant functions / structure:

- `historization.py` → `Historization`
- success traces
- failure traces
- `to_snapshot_dict()` / `from_snapshot_dict()`

---

## 5. Historization Correction δ_H(e)

### Mathematics

```text
δ_H(e) = λ_f · F(e) − λ_s · U(e)
```

This is the historized correction applied to baseline resistance.

### Implementation

Computed by:

```python
Historization.delta_H(edge)
```

or equivalent edge-based access inside the controller stack.

Parameters are stored in `Historization`:

- `rho`
- `lambda_s`
- `lambda_f`
- `delta_max`

Implementation source:

- `historization.py`

---

## 6. Effective Resistance R_eff(x→y)

### Mathematics

```text
R_eff(e) = R₀(e) + δ_H(e)
```

Subject to a lower structural floor and optional clipping.

### Implementation

Computed via:

```python
Landscape.effective_resistance(source, target)
```

This combines:

- stored baseline resistance,
- historization correction,
- floor / clipping logic.

Implementation source:

- `landscape.py`
- `historization.py`

---

## 7. Edge Tension S(x→y)

### Mathematics

```text
S(x→y) = Δ(x,y) · R_eff(x→y)
```

### Implementation

Computed via:

```python
Landscape.effective_tension(source, target)
```

Behavior:

- if `Δ` is undefined (`None`), returns `inf`
- inadmissible transitions therefore receive infinite tension

Implementation sources:

- `landscape.py`
- `tension.py`

---

## 8. Path Tension S(p)

### Mathematics

For a path

```text
p = (x₀ → x₁ → … → xₙ)
```

```text
S(p) = Σ S(xᵢ → xᵢ₊₁)
```

### Implementation

Computed in the path utilities of the package.

Primary implementation:

- `tension.path_tension(...)`
- reused by `wavepath.py`

Paths are represented as explicit ordered state sequences.

---

## 9. Coherence C(p)

### Mathematics

```text
C(p) = exp(−S(p))
```

Properties:

- `0 < C ≤ 1`
- lower path tension yields higher coherence

### Implementation

Implemented as:

```python
tension.coherence(...)
```

Also reused in controller admissibility and MemOS summaries.

Implementation sources:

- `tension.py`
- `memory_os.py`

---

## 10. Landscape L_t

### Mathematics

```text
L_t = (X_t, E_t, v_t, S_t, H_t)
```

The landscape is the total structured transition state of the system.

### Implementation

Implemented as the central runtime object:

```python
Landscape
```

It contains or derives:

- states,
- edges,
- difference,
- baseline resistance,
- effective resistance,
- effective tension,
- transition field,
- historization.

Implementation source:

- `landscape.py`

---

## 11. Transition Field v_x(y)

### Mathematics

Spec form:

```text
v_x(y) = Δ(x,y) · M_H(x,y) · exp(−S(x→y))
```

For v0.1/v1 runtime, the simplification is:

```text
M_H = 1
```

so that:

```text
v_x(y) = Δ(x,y) · exp(−S(x→y))
```

### Implementation

Implemented via:

```python
Landscape.transition_field(source, target)
```

This is explicitly documented as a simplified runtime form.

Implementation source:

- `landscape.py`

---

## 12. Local Potential Φ(x)

### Mathematics

```text
Φ(x) = Σ Δ(x,y) · R_eff(x→y)
```

summed over outgoing neighbors.

### Implementation

Implemented via:

```python
potential.phi(landscape, x)
```

Notes:

- dead-end states return `0.0`
- this is a local spec-aligned summation, not a full graph-Laplacian Helmholtz solution

Implementation source:

- `potential.py`

---

## 13. Gradient Component v_grad(x,y)

### Mathematics

```text
v_grad(x,y) = Φ(x) − Φ(y)
```

### Implementation

Implemented via:

```python
potential.v_grad(landscape, x, y)
```

Implementation source:

- `potential.py`

---

## 14. Rotational Component v_rot(x,y)

### Mathematics

```text
v_rot(x,y) = v(x,y) − v_grad(x,y)
```

### Implementation

Implemented via:

```python
potential.v_rot(landscape, x, y)
```

Notes:

- defined for existing edges
- missing edges do not automatically imply a reverse structural component
- this is a local decomposition aligned with the current spec/runtime

Implementation source:

- `potential.py`

---

## 15. Connection ω(x,y)

### Mathematics

```text
ω(x,y) = 1/2 · (v_rot(x,y) − v_rot(y,x))
```

### Implementation

Implemented via:

```python
connection.omega(landscape, x, y)
```

Runtime convention:

- if the reverse edge does not exist, its rotational term is treated as `0`

This convention is explicitly documented in the code and tests.

Implementation source:

- `connection.py`

---

## 16. Path Phase Θ(p)

### Mathematics

```text
Θ(p) = Σ ω(e)
```

### Implementation

Implemented via:

```python
connection.theta(landscape, path)
```

Implementation source:

- `connection.py`

---

## 17. Holonomy

### Mathematics

For a closed cycle `γ`:

```text
Hol(γ) = Θ(γ)
```

Interpretation:

- `Hol(γ) = 0` → integrable loop
- `Hol(γ) ≠ 0` → non-integrable structure

### Implementation

Implemented via:

```python
connection.holonomy(landscape, cycle)
```

Implementation source:

- `connection.py`

---

## 18. Complex Path Representation Ψ(p)

### Mathematics

```text
Ψ(p) = exp(−S(p)) · exp(iΘ(p))
```

This is the compact complex representation of path structure.

### Implementation

Implemented via:

```python
wavepath.psi(landscape, path)
```

Returns a Python complex number.

Implementation source:

- `wavepath.py`

---

## 19. Path Summation Ψ(z)

### Mathematics

```text
Ψ(z) = Σ_{p→z} Ψ(p)
```

### Implementation

Implemented via explicit bounded path sets:

```python
wavepath.sum_paths(...)
```

Important runtime constraint:

- no automatic global path enumeration
- paths must be supplied explicitly

Implementation source:

- `wavepath.py`

---

## 20. Intensity |Ψ|²

### Mathematics

```text
I(z) = |Ψ(z)|²
```

### Implementation

Implemented in the wavepath utilities as path/state intensity calculations.

Implementation source:

- `wavepath.py`

---

## 21. Controller Law

### Mathematics

The controller selects the minimal penalized transition:

```text
S_pen(e) = S_eff(e) / (M_H(e) · I(e))
p* = argmin S_pen
```

where M_H is the graduated overlap functional (§30) and I is the inertia factor (§31).

### Implementation

Primary implementation:

```python
E0Controller.select_next(...)
```

The controller:

1. gathers admissible neighbors,
2. computes effective tension,
3. applies revisit penalty,
4. applies admissibility filters,
5. selects the minimal candidate,
6. escalates when necessary.

Implementation source:

- `controller.py`

---

## 22. Admissibility

### Mathematics

Minimal condition:

```text
S_eff < ∞
```

Extended conditions:

```text
S_eff ≤ S_max
C ≥ C_min
```

### Implementation

Implemented in controller-level filtering using:

- `s_max`
- `c_min`

These are part of the K11 fix.

Implementation source:

- `controller.py`

---

## 23. Escalation

### Mathematics

If no admissible transition exists:

```text
ESCALATE
```

### Implementation

Implemented through typed escalation logic.

Current runtime types:

- `NONE`
- `DEAD_END`
- `FILTERED`
- `EXHAUSTED`

This corresponds to the K12 refinement.

Implementation source:

- `controller.py`

---

## 24. Historization Update Dynamics

### Mathematics

Historization is updated after each transition outcome.

Typical abstract form:

- success strengthens `U`
- failure strengthens `F`
- both are subject to decay and clipping

### Implementation

Implemented via:

```python
Historization.update(...)
```

with support for:

- success,
- failure,
- partial outcomes,
- bounded correction.

Implementation source:

- `historization.py`

---

## 25. MemOS Mapping

### Mathematics

MemOS is not part of the core mathematics.
It persists the runtime carriers of:

- landscape,
- historization,
- controller runtime state.

### Implementation

Implemented in:

```python
e0_controller/memory_os.py
```

Key runtime structures:

- `LandscapeSnapshot`
- `HistorizationSnapshot`
- `RuntimeSnapshot`
- `RunRecord`
- `MemOSContext`

This is the persistence substrate for Phase 3.

---

## 26. LLM Interface Mapping

### Mathematics

The LLM is not a primitive of E₀ mathematics.
It belongs to the semantic interface layer.

### Implementation

Implemented in:

```python
e0_controller/llm_adapter.py
```

Core functions:

- `extract_delta()`
- `propose_states()`
- `execute_transition()`
- `as_execute_fn()`

The adapter always receives bounded MemOS summaries rather than raw thread history.

---

## 27. Structural Summary (see §39 for current version)

*(Moved to §39 with updated derivation chain including C42–C122d additions.)*

---

## 28. Scope Note (see §40 for current version)

*(Moved to §40 with expanded scope through C122d.)*

---

## 29. Amplitude Overlay — Bounded Path-Family Support

### Mathematics

For each admissible action `a` from state `x`, within bounded horizon `h`:

```text
Paths(a, h) = { p : x → a → ... | len(p) ≤ h }
I(a) = | Σ_{p ∈ Paths(a,h)} Ψ(p) |²
P(a) = I(a) / Σ_a' I(a')
```

### Implementation

Implemented via:

```python
amplitude_overlay.analyze_controller_state(controller, state, goal_states, geometry, horizon)
```

Returns `OverlayReport` containing:

- `action_infos[].intensity` — I(a)
- `action_infos[].probability` — P(a)
- `action_infos[].psi_total` — Ψ(a) (complex)
- `action_infos[].override_confidence` — 1 − 2·min(P, 1−P)

---

## 30. Graduated Overlap M_H (C40, C98)

### Mathematics

```text
M_H(x→y) = max(ε, Σ_z √(v(x,z) · v(z,y)))
```

Triangle support: shared neighbors with strong transition fields increase edge familiarity.

### Implementation

```python
overlap.graduated_m_h(landscape, source, target)
```

Used in controller greedy loop: `S_pen = S_eff / M_H` — high overlap makes an edge more attractive.

Implementation source: `overlap.py`

---

## 31. Trace Quality q(e) (C42)

### Mathematics

```text
q(e) = (U(e) − F(e)) / (U(e) + F(e) + ε)
```

Range: (−1, +1). Positive = mostly successful, negative = mostly failing, near zero = confused.

### Implementation

```python
Historization.trace_quality(edge)
```

Implementation source: `historization.py`

---

## 32. Trace Load m(e) (C42)

### Mathematics

```text
m(e) = U(e) + F(e)
```

Total accumulated experience on an edge.

### Implementation

```python
Historization.trace_load(edge)
```

Implementation source: `historization.py`

---

## 33. Inertia Factor I(e) (C42, C99)

### Mathematics

```text
I(e) = 1 − α · m/(m + μ) · (1 − |q|)
```

where α = 0.5, μ = |E|/|V|. Heavy-traffic confused edges (high m, low |q|) get penalized. Clear edges (|q| ≈ 1) pass through undamped.

### Implementation

```python
Historization.inertia_factor(edge, alpha, mu)
```

Used in controller greedy loop: `S_pen = S_eff / (M_H · I)`.

Implementation source: `historization.py`

---

## 34. Overload Index OI(x) (C63)

### Mathematics

```text
OI(x) = N_admissible(x) × (1 − mean|q(e)|)
```

Many paths × little experience = overwhelmed. When OI > threshold, peer consultation fires.

### Implementation

Computed inline in `E0Controller.select_next()`. Triggers OVERLOADED escalation with `peer_fn` callback.

Implementation source: `controller.py`

---

## 35. Scoped Reflexion Locality ℓ (C101, C105)

### Mathematics

```text
ℓ = m̄ / (m̄ + μ),    μ = |E|/|V|
r = max(1, ⌈(1 − ℓ) · D⌉)
```

Locality ℓ ∈ [0,1]: fresh landscape (m̄ ≈ 0) → ℓ ≈ 0 → global proposals. Historized landscape → ℓ → 1 → local proposals within radius r.

### Implementation

```python
scoped_reflexion.compute_locality(landscape)
scoped_reflexion.compute_scope_radius(locality, diameter)
```

Implementation source: `scoped_reflexion.py`

---

## 36. Structural Temperature T_s (C115)

### Mathematics

```text
T_s = m̄ / q̄
```

where m̄ = mean trace load, q̄ = mean |trace_quality|. High T_s = much experience but low clarity (hot, noisy). Low T_s = clear knowledge (cold, stable).

### Implementation

```python
structural_entropy.structural_temperature(landscape)
```

Controls inscription threshold and dream pressure.

Implementation source: `structural_entropy.py`

---

## 37. Dream Pressure (C121)

### Mathematics

```text
P_dream = T_s / (T_s + μ)
```

Triggers dreaming when P_dream > 0.5, i.e., when T_s > μ. Parameter-free: uses existing μ from landscape topology.

### Implementation

```python
structural_entropy.dream_pressure(landscape)
structural_entropy.should_dream(landscape)
```

Used by `SleepWakeCycle` to alternate between wake (controller.run) and sleep (dream_cycle).

Implementation source: `structural_entropy.py`, `sleep_wake.py`

---

## 38. Canon Initial Historization (C122d)

### Mathematics

Canon edges carry initial traces (U₀, F₀) that set the prior before any runtime traversal:

```text
δ_H₀(e) = λ_f · F₀ − λ_s · U₀
R_eff₀(e) = R₀(e) + δ_H₀(e)
S_eff₀(e) = Δ(e) · R_eff₀(e)
```

**Epistemic liveness constraint:** S_eff₀ > 0 for all edges (no epistemically dead edges).

**Decay direction constraint:** F₀/U₀ < λ_s/λ_f = 0.75 ensures unvisited edges amplify (unused knowledge atrophies, not spontaneously heals).

### Implementation

Set in `e0_controller/canons/ontodynamics.json` as `initial_U` and `initial_F` per edge. Uniform U=2, F=1 for all 93 edges.

Loaded via `canon_loader.py` → `bootstrapper.py` → `Landscape`.

---

## 39. Structural Summary (updated)

The current implementation realizes the following derived chain:

```text
Δ → R₀ → H(U,F) → δ_H → R_eff → S_eff → C → Φ → v_grad / v_rot → ω → Θ → Ψ
                     ↓
              q, m → I(e) → S_pen = S_eff/(M_H·I)
                     ↓
              T_s → P_dream → SleepWakeCycle
                     ↓
              ℓ → r → Scoped Reflexion
```

with controller-level realization through:

```text
GREEDY:                argmin S_pen = S_eff/(M_H·I)
AMPLITUDE_ON_DISAGREE: argmax I (override on disagree)
BORN_SAMPLING:         sample P ∝ I
```

and persistence/semantic/epistemic extension through:

```text
MemOS (geometry + confidence + snapshots)
LLM Adapter (semantic interface)
Canon (initial Δ, R₀, U₀, F₀ — ontodynamics.json)
```

---

## 40. Scope Note

This document maps the current runtime and mathematical structure as implemented through C122d.

It does **not** claim:

- full graph-theoretic Helmholtz decomposition,
- complete continuous-limit formalization,
- finished phase-3b/open-domain validation,
- completion of the spin-1/2 derivation program.

It is an exact mapping document for the current implemented system.

Implementation source:

- `amplitude_overlay.py`

---

## 30. Summation Geometry

### Mathematics

Four geometry variants determine which paths contribute to Ψ(a):

| Geometry | Filter |
|----------|--------|
| `simple` | All paths up to horizon h |
| `prefix` | All prefixes of all paths |
| `first_arrival` | Only first-visit paths to each intermediate state |
| `goal_reaching` | Only paths that terminate at a goal state |

### Implementation

Geometry is a string parameter passed to `analyze_controller_state()`.
Path filtering happens inside the overlay computation.

Persisted in `RuntimeSnapshot.controller_params["hybrid_geometry"]` (Path G).

Implementation sources:

- `amplitude_overlay.py`
- `memory_os.py`

---

## 31. HybridMode — Three Decision Regimes

### Mathematics

Three selection rules over the same amplitude overlay:

```text
GREEDY_ONLY:            a* = argmin_a S(a)          (no overlay)
AMPLITUDE_ON_DISAGREE:  a* = argmax_a I(a)          (if ≠ greedy)
BORN_SAMPLING:          a* ~ P(a) = I(a) / Σ I     (sample)
```

### Implementation

```python
class HybridMode(str, Enum):
    GREEDY_ONLY = "greedy_only"
    AMPLITUDE_ON_DISAGREE = "amplitude_on_disagree"
    BORN_SAMPLING = "born_sampling"
```

Mode selection in `select_hybrid()`:

- `BORN_SAMPLING` → delegates to `_born_sample(overlay, escalated, esc_type)`
- `AMPLITUDE_ON_DISAGREE` → AGREE/DISAGREE arbitration with optional confidence gating
- `GREEDY_ONLY` → no overlay computation

Implementation source:

- `controller.py`

---

## 32. Born Sampling — _born_sample()

### Mathematics

```text
a ~ P(a) = I(a) / Σ I(a')
```

where sampling uses the intensity-derived probability distribution.

### Implementation

```python
def _born_sample(self, overlay, escalated, esc_type):
    actions = [ai.action for ai in overlay.action_infos]
    probs = [ai.probability for ai in overlay.action_infos]
    chosen = random.choices(actions, weights=probs, k=1)[0]
    return (chosen, escalated, esc_type, overlay, True)
```

Properties:

- Always marks `overridden = True`
- Escalated steps bypass sampling (fall back to greedy)
- Uses Python's `random.choices` with `weights=P`

Implementation source:

- `controller.py` → `_born_sample()`

---

## 33. Confidence Gating (Path F)

### Mathematics

```text
override_confidence = 1 − 2 · min(P_greedy, 1 − P_greedy)
```

Override is applied only if:

```text
override_confidence ≥ confidence_threshold
```

### Implementation

- `OverlayReport.override_confidence` — computed in amplitude overlay
- `E0Controller.confidence_threshold` — configurable parameter (default 0.0)
- Gating check in `select_hybrid()` DISAGREE branch
- `StepResult.override_confidence` — recorded per step
- `avg_override_confidence` — aggregated in run metrics

Implementation sources:

- `amplitude_overlay.py`
- `controller.py`

---

## 34. Structural Summary (Updated)

The current implementation realizes:

```text
Δ → R₀ → H → δ_H → R_eff → S → C → Φ → v_grad / v_rot → ω → Θ → Ψ
                                                                      ↓
                                                              Amplitude Overlay
                                                              I = |ΣΨ|², P = I/ΣI
                                                                      ↓
                                                              ┌───────┴───────┐
                                                              │               │
                                                           argmax(I)      sample(P)
                                                           (default)      (opt-in)
```

with controller-level realization through three modes, persistence through MemOS,
and semantic extension through the LLM Adapter.

---

## End of Document
