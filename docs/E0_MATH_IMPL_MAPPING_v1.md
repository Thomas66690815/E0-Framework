# E₀ — Mathematics ↔ Implementation Mapping v1.0

**Status:** Draft (post Phase 3a)  
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

The controller selects the minimal admissible transition:

```text
p* = argmin S_eff
```

Operationally, in the current runtime, this is implemented as local edge selection.

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

## 27. Structural Summary

The current implementation realizes the following derived chain:

```text
Δ → R₀ → H → δ_H → R_eff → S → C → Φ → v_grad / v_rot → ω → Θ → Ψ
```

with controller-level realization through:

```text
argmin S_eff
```

and persistence/semantic extension through:

```text
MemOS + LLM Adapter
```

---

## 28. Scope Note

This document maps the current runtime and mathematical structure as implemented after Phase 3a.

It does **not** claim:

- full graph-theoretic Helmholtz decomposition,
- complete continuous-limit formalization,
- finished phase-3b/open-domain validation,
- completion of the spin-1/2 derivation program.

It is an exact mapping document for the current implemented system.

---

## End of Document
