# E₀ Architecture Overview v1

**Status:** Working reference  
**Date:** 2026-03-25  
**Purpose:** Provide a single-page overview of the current E₀ stack so new readers understand how the canonical theory, runtime layers, and demos connect.  
**Scope:** Descriptive; see the referenced specs for details and proofs.

---

## 1. Layered stack (top-down)

```
Canon (Δ, P, R, H, τ, v)
  ↓
Deterministic Controller (greedy burden minimisation)
  ↓
Amplitude Overlay (bounded path family Ψ, |ΣΨ|²)
  ↓
Summation Geometry (prefix / simple / first_arrival / goal_reaching)
  ↓
Hybrid Arbitration (3 modes: GREEDY_ONLY / AMPLITUDE_ON_DISAGREE / BORN_SAMPLING)
  ↓
Confidence Gating (override_confidence threshold)
  ↓
MemOS Persistence (snapshots, hybrid traces, geometry + threshold)
  ↓
Evaluation + Reflection + Demos
```

Each arrow represents a dependency:

- the amplitude layer consumes controller traces and the canonical equations for `S`, `C`, `Θ`, `Ψ`;
- summation geometry determines how the amplitude layer aggregates path families;
- the hybrid controller uses both greedy and amplitude outcomes;
- MemOS stores both controller and hybrid artefacts;
- evaluation/reflection consume all runtime data and feed back into documentation/tests.

---

## 2. Key artefacts per layer

| Layer | Primary files | Notes |
|-------|---------------|-------|
| Canon | `canon/`, `docs/E0_FORMAL_PAPER_DRAFT_v1.md` | Seven primitives + Axiom A₀ |
| Deterministic controller | `e0_controller/controller.py`, `e0_controller/landscape.py` | Greedy burden minimisation, historisation, escalation |
| Amplitude overlay | `e0_controller/amplitude_overlay.py`, `docs/E0_PHASE_DERIVATION_PROGRAM_v1.md` | Implements bounded path amplitudes `Ψ = exp(-S) exp(iΘ)` |
| Summation geometry | `docs/E0_SUMMATION_GEOMETRY_COMPARISON_v1.md`, `docs/E0_SUMMATION_GEOMETRY_RESULTS_v1.txt` | Empirical comparison of `prefix`, `simple`, `first_arrival` |
| Hybrid arbitration | `docs/E0_HYBRID_CONTROLLER_SPEC_v1.md`, `e0_controller/controller.py` | GREEDY_ONLY / AMPLITUDE_ON_DISAGREE / BORN_SAMPLING |
| Persistence | `e0_controller/memory_os.py` | Stores landscapes, historisation, hybrid overrides |
| Evaluation | `e0_controller/evaluation.py`, `docs/E0_EVALUATION_LAYER_v0.2.md` | Run/Scenario scoring, hybrid metrics |
| Reflection | `e0_controller/reflection.py`, `docs/E0_REFLECTION_LAYER_v0.1.md` | Structured self-observation |
| External interface | `e0_controller/llm_adapter.py`, `docs/E0_EXTERNAL_VALIDATION_AND_HANDOFF_NOTE_v1.md` | Bounded LLM context, handoff strategy |

---

## 3. Runtime modes

| Mode | Description | When to use |
|------|-------------|-------------|
| `GREEDY_ONLY` | Pure local structural burden minimisation | Baseline deterministic runs |
| `AMPLITUDE_ON_DISAGREE` | Override greedy when amplitude disagrees (argmax I) | Default — avoid traps, compare geometries |
| `BORN_SAMPLING` | Sample from P ∝ I instead of argmax | Exploration, multi-goal coverage, distributional analysis |

All three modes share the same controller core and amplitude overlay. They differ only in the final action selection step. BORN_SAMPLING is opt-in (ADR-0007-v1). Additional configuration:

- `confidence_threshold` — gates overrides on `override_confidence` (Path F)
- `hybrid_geometry` — selectable summation geometry persisted via MemOS (Path G)

---

## 4. Metrics that define the architecture

- `S = Δ · R_eff` — local structural burden (derived)
- `Ψ(p) = exp(-S(p)) exp(iΘ(p))` — complex path carrier
- `I(a) = |Σ_{p∈Paths(a)} Ψ(p)|²` — path-family intensity
- `hybrid_override_count/rate` — how often amplitude overrides greedy
- `geometry = {prefix, simple, first_arrival, goal_reaching}` — summation regime in use
- `trap_escape_events` — empirical evidence that hybrid avoids loops

These metrics are logged in MemOS snapshots and reported by the evaluation layer.

---

## 5. Documentation pointers

For deeper detail:

- ADR-0007 (Born regime decision) — `docs/E0_CONTROLLER_VS_BORN_REALIZATION_REGIMES_v1.md`
- Hybrid spec — `docs/E0_HYBRID_CONTROLLER_SPEC_v1.md`
- Derived/Empirical/Heuristic classification — `docs/E0_DERIVED_EMPIRICAL_HEURISTIC_MAP_v1.md`
- Summation geometry evidence — `docs/E0_SUMMATION_GEOMETRY_COMPARISON_v1.md`
- Reflection and inline corrections — `docs/CLAUDE_THREAD_REFLECTION_NOTES_v1.md`
- External validation package — `docs/E0_EXTERNAL_VALIDATION_AND_HANDOFF_NOTE_v1.md`

---

## 6. Open questions

1. Full derivation of `Θ` from the rotational field (`v_rot`)  
2. Proof-level justification for the `simple` summation geometry default  
3. Scalable amplitude aggregation without explicit enumeration  
4. Formal link between inline Verdichtungssnapshots and MemOS snapshots  
5. Adaptive mode selection (auto-switch between argmax/Born per domain)  
6. SU(2) intensities in operational controller decisions (O4)

These open points connect the current operational system back to the mathematical research agenda.

---

_End of document._
