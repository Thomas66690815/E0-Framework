# E₀ — Agent Reference

Machine-readable orientation document. Covers mechanisms, file locations, formal contracts, and known limits. No prose beyond what is structurally necessary.

Full formal canon: [`canon/e0-canon-plain.txt`](canon/e0-canon-plain.txt) — 155 lines, ASCII, invariant.

---

## Module Map

| Module | File | Primary class |
|--------|------|---------------|
| Primitives | `e0_controller/primitives.py` | `Edge`, `Outcome`, `TransportRegime` |
| Historization | `e0_controller/historization.py` | `Historization` |
| Landscape | `e0_controller/landscape.py` | `Landscape` |
| Controller | `e0_controller/controller.py` | `E0Controller` |
| Amplitude | `e0_controller/amplitude_overlay.py` | `AmplitudeOverlay` |
| Reflexion | `e0_controller/self_graph.py` | `SelfGraph` |
| Multiverse | `e0_controller/multiverse.py` | `MultiverseController` |
| Dream | `e0_controller/dream_mode.py` | `DreamObserver` |
| Trajectory | `e0_controller/trajectory.py` | `TrajectoryHistorization` |
| Input protocol | `e0_controller/observation_port.py` | `DifferenzPort` (ABC) |
| Session runner | `e0_controller/e0_session.py` | `run_session()` |
| MCP adapter | `e0_controller/mcp_adapter.py` | `MCPAdapter` |

---

## Three Mechanisms Not Present in Standard Agent Frameworks

### M1 — Epistemic Trust

**File:** `e0_controller/historization.py` → `Historization.trust()`, `Historization.delta_H_trusted()`  
**Spec:** §C186

**Problem:** Fixed-rate memory decay treats stable and volatile edges identically. A learned resistance that was accurate last month may be wrong today; a virgin edge has no basis for doubt.

**Formal definition:**

```
trust(e) = exp( -staleness(e) / τ_doubt(e) )

where:
  staleness(e)  = τ_current - τ_last(e)
  stability(e)  = confirmations(e) / (confirmations(e) + surprises(e) + 1)
  τ_doubt(e)    = τ_base / (1 - stability(e) + ε)
  τ_base        = median inter-visit interval (self-calibrating, no external parameter)
```

**Behavior:**
- Virgin edge (no traces): `trust = 1.0`
- Just visited: `trust = 1.0`
- Stable edge (outcomes consistently confirm predictions): `τ_doubt` large → slow trust decay
- Volatile edge (outcomes frequently contradict predictions): `τ_doubt` small → fast trust decay
- Stale + volatile: trust approaches 0 → historization correction suppressed → edge returns to base resistance

**Applied as:** `R_eff(e) = R₀(e) + δ_H(e) · trust(e)`

**What this replaces:** Fixed `ρ`-decay (same rate regardless of edge history). E₀ self-calibrates doubt from its own revisit statistics.

---

### M2 — Inertia Factor (Layer 3 inscription)

**File:** `e0_controller/historization.py` → `Historization.inertia_factor()`  
**Spec:** §C99, layer model §4 (Ontodynamics)

**Problem:** Scalar `δ_H` conflates magnitude with direction. When `U ≈ F`, `δ_H ≈ 0` — a conventional system treats this as "no experience." It is not: it is contradictory experience, a distinct structural signal.

**Formal definition:**

```
I(e) = 1 - α · (m / (m + μ)) · (1 - |q|)

where:
  m = trace_load(e)  = U(e) + F(e)          [magnitude of inscription]
  q = trace_quality(e) = (U - F) / (U + F + ε)  [direction of inscription]
  α = dampening strength (default 0.5)
  μ = half-load reference (default 5.0)
```

**Behavior:**
- No inscription (`m ≈ 0`): `I = 1.0` (neutral)
- Clear quality (`|q| → 1`): `I → 1.0` (no dampening — system knows this edge)
- Contradictory inscription (`q ≈ 0`, `m >> 0`): `I` approaches `1 - α` (maximum dampening)

**Applied as:** `S_eff(e) = Δ(e) · R_eff(e) / (M_H(e) · I(e))`

**What this replaces:** Loss of the `(m, q)` decomposition when collapsing to scalar `δ_H`. Two edges with identical `δ_H ≈ 0` are now distinguishable: one is virgin, one is contested.

---

### M3 — Adaptive Observation (self-calibrating inscription weight)

**File:** `e0_controller/historization.py` → `Historization.classify_experience()`, `Historization.adapt_from_experience()`  
**Spec:** §C187, §C188

**Problem:** Static inscription weight. A surprising outcome in a volatile domain (traffic jam on usually-clear road) should not permanently overwrite stable knowledge. In a stable domain, full-weight inscription is correct.

**Formal definition:**

```
surprise_rate = Σ_edges surprises(e) / (Σ_edges confirmations(e) + surprises(e))

classify_experience():
  surprise_rate < 0.3 and total_events ≥ 3  →  'stable'
  surprise_rate ≥ 0.3 and total_events ≥ 3  →  'volatile'
  total_events < 3                           →  'exploratory'

adapt_from_experience():
  'volatile'    →  surprise_dampening = True   (w = 0.5 on surprising outcomes)
  'stable'      →  surprise_dampening = False  (w = 1.0, full inscription)
  'exploratory' →  no change
```

**Feedback loop:** `Historization → classify_experience() → adapt_from_experience() → inscription weight → Historization`

The system observes its own surprise statistics and changes how it inscribes. No external signal, no tuned threshold beyond `0.3` (derived from empirical observation that `> 30%` surprises indicates structural instability).

**What this replaces:** Fixed inscription weight. E₀ learns *how to learn* from the character of the domain it is navigating.

---

## Structural Limits (empirically confirmed)

These are not design choices — they are verified boundaries of the current architecture.

| Limit | ID | Description |
|-------|----|-------------|
| Branching boundary | F3 | At branching factor `b ≥ 3`, differentiation degrades. Hierarchical revisit penalty partially addresses this. |
| Non-Markov boundary | F4 | Edge-level credit assignment across non-adjacent edges is not supported. `TrajectoryHistorization` partially closes this at the trajectory level. |
| PARTIAL residual | GT-8 | `Outcome.PARTIAL` does not create a residual difference object — the unresolved remainder is not carried forward. Known gap, no resolution yet. |

Full falsification status: [`docs/E0_EVIDENCE_AND_FALSIFICATION_STATUS_v1.md`](docs/E0_EVIDENCE_AND_FALSIFICATION_STATUS_v1.md) — 8/8 targets resolved as of 2026-03-31.

---

## Invariants

These must hold in any extension or fork:

- `E0Controller(landscape, execute_fn, ...)` — `execute_fn` always second positional argument
- `Outcome.SUCCESS` / `Outcome.FAILURE` — canonical. `Outcome.PARTIAL` is a runtime extension, not in the minimal core.
- `DifferenzPort.impact_quality()` returns `0.0` when no data (never raises)
- `DifferenzPort.dampening_factor()` returns `1.0` when no data (neutral)
- `DifferenzPort.from_dict(None)` returns fresh instance
- All ports must pass `TestDifferenzPortABCCompliance` in `e0_controller/test_differenz_port.py`
- Domain partitioning must emerge from `R_eff` (community detection), not from string labels

---

## Citation

```bibtex
@software{e0_framework,
  author  = {Wehner, Thomas},
  title   = {E₀ Framework},
  year    = {2026},
  doi     = {10.5281/zenodo.19333487},
  license = {CC BY 4.0},
  url     = {https://github.com/Thomas66690815/E0-Framework}
}
```
