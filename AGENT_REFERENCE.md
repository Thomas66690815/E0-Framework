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
| Structural entropy | `e0_controller/structural_entropy.py` | `structural_temperature()` |
| Input protocol | `e0_controller/observation_port.py` | `DifferenzPort` (ABC) |
| Session runner | `e0_controller/e0_session.py` | `run_session()` |
| MCP adapter | `e0_controller/mcp_adapter.py` | `MCPAdapter` |

---

## Mechanisms Not Present in Standard Agent Frameworks

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
- Stale + volatile: trust → 0 → historization correction suppressed → edge returns to base resistance

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
  m = trace_load(e)      = U(e) + F(e)              [magnitude of inscription]
  q = trace_quality(e)   = (U - F) / (U + F + ε)   [direction of inscription]
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

**Problem:** Static inscription weight. A surprising outcome in a volatile domain should not permanently overwrite stable knowledge. In a stable domain, full-weight inscription is correct.

**Formal definition:**

```
surprise_rate = Σ surprises(e) / (Σ confirmations(e) + Σ surprises(e))

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

**What this replaces:** Fixed inscription weight. E₀ learns *how to learn* from the character of the domain it is navigating.

---

### M4 — Self-Graph (metacognitive loop as navigable landscape)

**File:** `e0_controller/self_graph.py` → `SelfGraph`
**Spec:** §C43, §C151, §C193

**Problem:** Agent monitoring layers observe but do not feed back into navigation. A component that consistently produces bad outcomes continues to be used identically.

**Architecture:**

E₀ maintains a dedicated `Landscape` instance whose nodes are E₀'s own operational components:

```
amplitude → born → realization → historization → inertia → transition_field → (loop)
                                                                    ↑
                                                      curvature, overlap (optional)
```

After every controller decision, `self_historize(active_components, outcome)` inscribes `Outcome.SUCCESS` or `Outcome.FAILURE` on edges originating from each active component. The same `Historization` mechanism used for domain edges now runs on the system's own structure.

**Three levels:**

| Level | Mechanism | What it enables |
|-------|-----------|-----------------|
| 1 | Structural self-image — fixed topology of own components | Knowing what parts exist |
| 2 | Operational reflection — `component_quality(c)` = mean `trace_quality` on outgoing edges | Knowing which parts help |
| 3 | Meta-control — components with `quality < threshold` can be deactivated | Changing own behavior |

**Key design decisions:**

- `rho = 1.0` for the self-graph: E₀'s operational cycle is fixed — self-knowledge is cumulative, not stale.
- **Honest Activation (C151):** `amplitude` and `born` excluded in GREEDY mode. Marking them active when they had zero influence causes all 6 core components to share identical quality (degeneracy).
- **Override self-loop (C193):** `Edge("amplitude", "amplitude")` inscribed only on override events. `trace_quality` of this edge = net override effectiveness. Negative quality → override gate blocks future overrides.

**Queries:**

```python
sg = SelfGraph()
sg.component_quality("curvature")   # is curvature helping?
sg.component_load("amplitude")      # how often was amplitude active?
sg.component_inertia("born")        # contradictory signal about born?
```

**What this replaces:** External monitoring dashboards that observe but don't close the loop. E₀'s self-graph feeds directly into navigation — the controller is a domain like any other.

---

### M5 — Structural Temperature + Dream Pressure (self-calibrating forgetting)

**File:** `e0_controller/structural_entropy.py` → `structural_temperature()`, `dream_pressure()`
**Spec:** §C114–C121

**Problem:** Fixed forgetting schedules require external tuning and ignore the actual knowledge state. A system that "runs hot" — much experience, little clarity — needs consolidation; a cold system needs to keep learning.

**Structural Temperature:**

```
T_s = m̄ / q̄

where:
  m̄ = mean(trace_load(e))       over all historized edges
  q̄ = mean(|trace_quality(e)|)  over all historized edges + ε
```

| T_s | Interpretation |
|-----|----------------|
| ≈ 0 | Virgin system — no experience |
| Low | Clear judgments, low load — "cold", keep inscribing |
| High | Much experience, contradictory outcomes — "hot", consolidate |

**Dream Pressure (sleep–wake trigger):**

```
dream_pressure = T_s / (T_s + μ)   ∈ [0, 1)
```

Uses the same `μ` as `inertia_factor`. No new parameter. When `T_s = μ`, pressure = 0.5 (tipping point).

**Two forgetting types:**

*Type 1 — Inscription Threshold:*
```
novelty(e, outcome) = |signal(outcome) − trace_quality(e)|
inscription gate:   novelty > ε(e)
ε(e) = ε₀(T_s) · (1 − exp(−trace_load(e)/μ))
```
Routine transitions that match expectation are not inscribed. Only surprises write new structure.

*Type 2 — Anchor-Based Pruning:*
```
anchor_score(s) = |q̄_s| · m_max(s) · log(1 + degree(s))
decay_candidate: anchor_score < θ_decay AND dormant > τ_dormant
```

**What this replaces:** Fixed TTL, fixed buffer size, fixed replay schedules. All thresholds derived from existing ρ, μ, and landscape statistics. No new tuning parameters for Type 1.

---

### M6 — PathSignature (domain-invariant non-Markov trajectory signal)

**File:** `e0_controller/trajectory.py` → `PathSignature`, `TrajectoryHistorization`, `compute_path_signature()`
**Spec:** §C277–C283, BT-5

**Problem:** Edge-level historization is Markov. Stagnation patterns (looping through the same community structure repeatedly) are invisible until coverage stops growing.

**PathSignature:**

```python
path = ["C:omega", "C:zeta", "B:HERE", "B:L4", "C:omega"]
communities = [{"C:omega", "C:zeta"}, {"B:HERE", "B:L4"}]
→ compute_path_signature(path, communities) = (0, 1, 0)
```

Node IDs are discarded. Only community boundary crossings are retained, consecutive duplicates removed.

**Properties:**

| Property | Description |
|----------|-------------|
| Domain-invariant | Same boundary pattern in different domains → same signature |
| Instance-independent | Specific node IDs irrelevant — structure is what counts |
| Historizable | `TrajectoryHistorization` accumulates U/F traces on signatures across rounds |
| Non-Markov | `plan()` consults history of trajectory *shapes*, not current state alone |

**TrajectoryHistorization:**

```python
th = TrajectoryHistorization()
th.record(signature, Outcome.SUCCESS)   # this shape was productive
th.record(signature, Outcome.FAILURE)   # this shape led nowhere
th.quality(signature)                   # → trace_quality ∈ (-1, +1)
th.should_escape(signature)             # → True when shape has negative quality
```

**Relationship to BT-3 / BT-5:**

> BT-3: `F=0` traps the system at the edge level — allowing doubt is structurally necessary.
> BT-5: A fixed trajectory *shape* traps at the round level — trajectory historization is structurally necessary for pattern-level escape.

**What this replaces:** Coverage-delta as the only stagnation signal (reactive). PathSignature enables proactive escape before stagnation is measured.

---

### M7 — Dream Mode (cross-domain structural equivalence via fingerprint matching)

**File:** `e0_controller/dream_mode.py` → `EdgeFingerprint`, `DreamObserver`, `fingerprint_distance()`
**Spec:** §C109–C111, §C135–C139, §C154, §C168, §C178

**Problem:** Knowledge accumulated in one domain is invisible to a controller navigating another. Structurally equivalent edges in different domains carry independent but redundant evidence.

**EdgeFingerprint — 4D descriptor:**

```python
@dataclass(frozen=True)
class EdgeFingerprint:
    domain: str
    edge: Edge
    quality: float             # trace_quality ∈ (-1, +1)
    load: float                # trace_load ∈ [0, ∞)
    inertia: float             # inertia_factor ∈ (1-α, 1]
    context_sensitivity: float # ∈ [0, 2] — C178: causal vs. confounded
```

`context_sensitivity` (C178) prevents false equivalences: an edge whose quality depends on predecessor (high `cs`) will not match a context-free edge with identical `(q, m, I)`.

**Fingerprint distance:**

```
d(a, b) = weighted_euclidean(dq, dm_normalized, dI, dcs)
dm normalized via sigmoid: load / (load + μ)   (scale-invariant across domains)
```

**Dream cycle (read-only constraint):**

`DreamObserver` holds N domain landscapes. `dream_cycle()`:
1. Extracts fingerprints from all edges in all domains
2. Skips incompatible domain pairs (`dream_compatibility() < threshold`) — C168
3. Hungarian optimal assignment finds best-matching edge pairs — C137
4. Equivalent edges → bridge hypothesis stored in Dream Landscape

**Dream Landscape self-historization:**

The Dream Landscape is itself a `Landscape` with `Historization`. When a proposed bridge leads to a successful cross-domain transition → `SUCCESS`. When it fails → `FAILURE`. Good bridges strengthen; bad bridges die — through the same mechanism as any E₀ edge.

**Hard constraint:** `dream_cycle()` never mutates any domain landscape. All writes go to the Dream Landscape only.

**What this replaces:** Manual knowledge transfer, hand-coded analogies, retraining on combined data. E₀ discovers structural equivalences passively from accumulated historization profiles — no labels required.

---

## Structural Limits (empirically confirmed)

These are not design choices — they are verified boundaries of the current architecture.

| Limit | ID | Description |
|-------|----|-------------|
| Branching boundary | F3 | At branching factor `b ≥ 3`, differentiation degrades. Hierarchical revisit penalty partially addresses this. |
| Non-Markov boundary | F4 | Edge-level credit assignment across non-adjacent edges is not supported. `TrajectoryHistorization` partially closes this at trajectory level. |
| PARTIAL residual | GT-8 | `Outcome.PARTIAL` does not create a residual difference object — unresolved remainder is not carried forward. Known gap, no resolution yet. |

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
