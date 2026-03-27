# E₀ Runtime Code Analysis — 2026‑03‑27

**Status:** Read-only review (no code changes)
**Purpose:** Incremental analysis of all developments since 2026-03-26. Builds on four prior analyses (2026-03-24, 2026-03-25, 2026-03-25 v2, 2026-03-26). Canon understood and applied as the foundational reference throughout.
**Scope:** Full stack delta — C37 Continuum (residual tension + iteration control), E0Envelope (typed configuration), Session orchestrator, TransportRegime primitive, LLM context enrichment tests, and the iterative burnout demo.

---

## 0. Analyses at a Glance

| Analysis | Date | Test count | Test growth | Headline additions |
|---|---|---|---|---|
| 2026-03-24 | 2026-03-24 | ~148 | baseline | Controller pipeline, hybrid mode, MemOS, evaluation, reflection |
| 2026-03-25 (v1) | 2026-03-25 | 613 | +465 (+314 %) | Gordian trap, G5 geometry, topology classification, scaling tests, greedy trap demo |
| 2026-03-25 (v2) | 2026-03-26 04:32 CET | 936 | +323 (+52 %) | ω uniqueness proof, historization×Gordian, reflection amplitude metrics, Born-regime axioms, dynamic horizons, confidence override, MemOS geometry persistence, Born-sampling comparison |
| 2026-03-26 | 2026-03-26 | 1,138 | +202 (+22 %) | Papers 1–3, Canon Alignment, SU(2) Tier 1–3, three-theory stack, O1/O2/O5 test expansions, M_H curvature, grid benchmark, Helmholtz cache, CI, pyproject |
| **2026-03-27 (this)** | **2026-03-27** | **1,499** | **+361 (+32 %)** | **C37 Continuum (residual tension + Session.iterate()), E0Envelope + TransportRegime, Session orchestrator, LLM context enrichment tests, iterative burnout demo** |

The repository now contains **1,499 passing tests, 0 skipped**, across **40 test files**.

**Test count accounting:** The prior analysis recorded 1,138 total tests (1,106 passing + 32 skipped). The current suite has 1,499 passing and 0 skipped — a net increase of **+361 in total count** (+32 %) and **+393 in passing tests** (+36 % relative to the 1,106 previously passing). The 32 previously-skipped tests in `test_llm_integration.py` (offline LLM integration tests) have been superseded by `test_llm_context.py` (23 tests, all runnable offline), which focuses on unit-level contract verification. Since skipped tests did not count as passing before, they do not affect the passing-test delta; the 393 net-new passing tests break down as: 110 in the 4 new test files (test_session: 13, test_residual_tension: 26, test_envelope: 48, test_llm_context: 23) plus 283 added to existing files.

---

## 1. What Changed since 2026-03-26 — Complete Delta

### 1.1 New Source Modules

| Module | Lines | Summary |
|---|---|---|
| `e0_controller/residual_tension.py` | ~280 | C37: ResidualTensionMap, IterationVerdict, compute_residual_map(), should_continue(), format_residual_map() |
| `e0_controller/envelope.py` | ~180 | E0Envelope frozen dataclass; transport_to_use_su2/use_su2_to_transport bridge; to_controller_kwargs/to_dict/from_dict/from_controller/summary |
| `e0_controller/session.py` | ~335 | Session orchestrator: run/resume/iterate/recent_runs; SessionResult + IterationResult dataclasses; persistence via MemOS + TuningMemory |

### 1.2 New Test Files

| File | Tests | Coverage |
|---|---|---|
| `test_session.py` | 13 | Session lifecycle, auto-save, resume, historization carry-over, tuning memory |
| `test_residual_tension.py` | 26 | snapshot_tensions, compute_residual_map, should_continue (all 4 stopping conditions), Session.iterate() integration, format_residual_map |
| `test_envelope.py` | 48 | TransportRegime identity, transport↔use_su2 bridge, E0Envelope defaults/construction, to_controller_kwargs backward compat, to_dict/from_dict round-trips, from_controller extraction, controller.transport property, immutability, summary, Session integration |
| `test_llm_context.py` | 23 | Canon-essence in SYSTEM_PROMPT (12 concepts), curvature-aware MemOS summary, override confidence and psi_phase in overlay summary, evidence-block override count |

### 1.3 New Demo File

| File | Summary |
|---|---|
| `demo_burnout_iterate.py` | C37 Continuum demo: LLM-bootstrapped burnout landscape → Session.iterate() → per-iteration ResidualTensionMap → automatic stop on stagnation. Live test: 2 iterations emerged; hotspots: ERROR_STATE path + AUTOFICTIONAL_ANALYSIS (both unvisited — structural tension correctly identified). |

### 1.4 Modified Source Files

| File | Change |
|---|---|
| `e0_controller/primitives.py` | `TransportRegime` enum added: `U1 = "u1"`, `SU2_MINIMAL = "su2_minimal"`, `SU2_GEOMETRIC = "su2_geometric"`. Replaces the polymorphic `use_su2` flag (False/True/"geometric") with a typed, canon-aligned primitive. |
| `e0_controller/__init__.py` | New exports: `TransportRegime`, `Session`, `SessionResult`, `IterationResult`, `format_residual_map`, `E0Envelope`, `transport_to_use_su2`, `use_su2_to_transport`. |

### 1.5 Removed / Superseded Files

| File | Status |
|---|---|
| `test_llm_integration.py` | Superseded by `test_llm_context.py`. The 32 skipped live-API tests are replaced by 23 offline unit tests verifying prompt contract (SYSTEM_PROMPT content, MemOS summary fields, overlay summary fields). |

### 1.6 Open-Item Follow-up from 2026-03-26

| Open Item (2026-03-26) | Status |
|---|---|
| Expose `use_su2` as a typed `E0Controller` parameter | ✅ **Resolved via E0Envelope + TransportRegime** — clean typed abstraction; bridge functions ensure backward compatibility |
| LLM demos not modernized | ✅ **Partially resolved** — `demo_burnout_iterate.py` uses the full current stack (Session.iterate, E0Envelope, ResidualTensionMap, C37); the 4 original LLM demos remain on Phase 3a surface |
| `axis_fn` not persisted in MemOS | ⚪ Carried over |
| SU(2) intensity not in evaluation/reflection metrics | ⚪ Carried over |
| M_H formula comparison (1/(1+κ) vs exp(−κ)) | ⚪ Carried over |
| Full θ derivation from v_rot (general) | ⚪ Carried over |
| Resonator kernel integration into controller | ⚪ Carried over |
| Stochastic exploration policy | ⚪ Carried over |
| Formal correctness proof of G5 geometry | ⚪ Carried over |

---

## 2. New Module Assessment

### 2.1 `residual_tension.py` — C37: Residual Tension & Iteration Control

**Canon alignment:**
C37 is a direct application of Axiom A₀ ("if Δ > 0 and a path with finite R exists, non-transition is structurally unstable") *at the iteration level*: if high residual tension with admissible paths remains after a controller run, "stopping now" is structurally unstable — the system must iterate. This is one of the cleanest canon-to-code mappings in the repository.

**Key data structures:**

```
ResidualTension       — per-edge snapshot: s_eff, delta_s, f_trace, visited
ResidualTensionMap    — landscape tension picture: residuals, hotspots, resolved, amplified,
                        iteration, max_residual, mean_residual
IterationVerdict      — should_continue, reason, should_reflect, residual_map, iteration
```

**Key functions:**

| Function | Behaviour |
|---|---|
| `snapshot_tensions(landscape)` | Captures S_eff for every edge before a run |
| `compute_residual_map(landscape, trace, pre_tensions, iteration)` | Builds full tension picture after a run; identifies hotspots (unvisited high-tension edges); classifies resolved/amplified |
| `should_continue(residual_map, prev_map, iteration, max_iterations, tension_threshold)` | Applies A₀ at iteration level; checks budget → equilibrium → stagnation in order; recommends reflection when amplifying |
| `format_residual_map(rmap)` | Human-readable summary string |

**Stopping conditions** (in priority order):
1. **Budget** — `iteration >= max_iterations` → stop unconditionally
2. **Equilibrium** — no actionable hotspot above `tension_threshold` → resolved
3. **Stagnation** — `|Δ mean_residual|` < 0.02 between iterations → stuck; recommend reflection

**Hotspot detection:** Edges with `s_eff > 0.5` that were **not visited** in the run. These represent unresolved structural tensions that the controller failed to reach — the most structurally significant finding from an E₀ perspective.

**Assessment:** Correct canon derivation. The module cleanly separates concerns (snapshot → compute → decide → format). Thresholds (0.5 hotspot, 0.1 equilibrium, 0.02 stagnation) are empirical heuristics, not derived values — appropriately flagged as such in the code.

**Tests:** 26 tests across 5 test classes. All 4 stopping conditions individually verified. Session.iterate() integration verified (equilibrium, budget, historization carry-over, final-map identity). `format_residual_map` string output verified.

---

### 2.2 `envelope.py` — E0Envelope: Typed Controller Configuration

**Motivation:** The 2026-03-26 analysis flagged "use_su2 not yet a typed E0Controller parameter" as a medium-priority open item. E0Envelope resolves this architecturally: rather than adding yet another init parameter to E0Controller, it introduces a **frozen configuration object** that holds all controller settings in a type-safe, serializable form.

**TransportRegime enum** (in `primitives.py`):
```python
class TransportRegime(Enum):
    U1 = "u1"                      # scalar phase (ℂ¹)
    SU2_MINIMAL = "su2_minimal"    # minimal spinor (ℂ²)
    SU2_GEOMETRIC = "su2_geometric"  # geometric spinor with curvature
```

This replaces the informal `use_su2 ∈ {False, True, "geometric"}` with a proper typed primitive — correct placement in `primitives.py` given the canon's definition of primitives as "irreducible domain concepts."

**E0Envelope fields:**
| Field | Type | Default | Description |
|---|---|---|---|
| `mode` | `HybridMode` | `GREEDY` | Controller mode |
| `geometry` | `str` | `"simple"` | Enumeration geometry |
| `horizon` | `int` | 3 | Lookahead depth |
| `transport` | `TransportRegime` | `U1` | Phase interference regime |
| `goals` | `FrozenSet[str]` | None | Target states |
| `alpha` | `float` | 2.0 | Tension exponent |
| `s_max` | `float` | ∞ | Tension saturation cap |
| `c_min` | `float` | 0.0 | Minimum coherence |
| `confidence_threshold` | `float` | 0.0 | Hybrid override gate |

**Key methods:**
- `to_controller_kwargs()` — backward-compatible; calls `transport_to_use_su2()` bridge
- `to_dict()` / `from_dict()` — JSON-serializable (inf → null for s_max)
- `from_controller(ctrl)` — extract envelope from a running controller
- `summary()` — one-line human-readable representation

**Backward compatibility:** The bridge functions `transport_to_use_su2()` and `use_su2_to_transport()` ensure that existing code using the old bool/string `use_su2` convention continues to work unchanged. The `to_controller_kwargs()` method always produces the legacy format.

**Assessment:** Clean design. Frozen dataclass prevents mutation after construction. The `from_controller()` extractor enables round-trip consistency (controller → envelope → kwargs → equivalent controller). JSON serialization handles the `inf`/`null` edge case correctly. One minor limitation: `axis_fn` is not captured (callables are not serializable — documented in the 2026-03-26 analysis and carried forward).

**Tests:** 48 tests across 10 test classes. Covers all API surfaces including backward compat, serialization round-trips, and Session integration.

---

### 2.3 `session.py` — Session Orchestrator

**Purpose:** Thin orchestration layer between the E₀ controller (which remains stateless) and MemOS persistence. All persistence awareness is concentrated here; the controller has no knowledge of disk state.

**Architecture:**
```
Session.run()       → delegate to controller.run() → persist (MemOS + TuningMemory)
Session.iterate()   → loop: snapshot → run() → compute_residual_map → should_continue
Session.resume()    → classmethod: load landscape + controller state from MemOS
```

**SessionResult dataclass:**
```python
@dataclass
class SessionResult:
    trace: RunTrace
    context: MemOSContext
    tuning_memory: TuningMemory
    session_id: str
    resumed: bool
```

**IterationResult dataclass:**
```python
@dataclass
class IterationResult:
    results: List[SessionResult]      # one per iteration
    verdicts: List[IterationVerdict]  # one per iteration
    final_map: Optional[ResidualTensionMap]
    iterations: int
    stop_reason: str                  # "equilibrium" | "stagnation" | "budget"
```

**`Session.iterate()` loop:**
1. Snapshot pre-run tensions
2. `self.run()` — controller run with full persistence
3. `compute_residual_map()` — tension picture after run
4. `should_continue()` — Axiom A₀ applied to iteration level
5. If `should_continue → False`: stop
6. Historization accumulates across iterations (correctly — the same landscape object persists)

**Design correctness:** Historization accumulates because each `run()` call uses the same `self.landscape` and `self.controller` object. This means each iteration starts from the structurally-informed state left by the previous one — exactly what E₀ historization requires. Time in E₀ is the ordering of historizations; Session.iterate() makes this explicit.

**Goal-geometry warning:** `session.run()` emits a `UserWarning` when `goal` is set but `hybrid_geometry != "goal_reaching"`. This is appropriate and canon-correct: a stated goal without goal-reaching geometry may not produce goal-directed traversal.

**Tests:** 13 tests. Lifecycle, auto-save, resume, historization carry-over, tuning memory persistence verified.

---

### 2.4 `test_llm_context.py` — LLM Context Enrichment Tests

This file verifies the **contract between the E₀ system and the LLM adapter's context generation** — a previously untested area. The 32 previously-skipped `test_llm_integration.py` tests required a live API key and were skipped in CI. `test_llm_context.py` provides offline unit tests at the contract level.

**Test groups:**
1. **Canon-essence in SYSTEM_PROMPT (P1):** Verifies SYSTEM_PROMPT contains 12 key concepts: Δ, Tension S, Coherence C = exp(−S), transition_field, connection ω, path phase Θ, amplitude Ψ, intensity I, M_H, curvature_modulation, historization, resistance. This ensures any LLM asked to process E₀ states receives the correct conceptual vocabulary.

2. **Curvature-aware MemOS summary (P2):** Verifies that when `curvature_modulation=True` is set in a landscape, the MemOS runtime summary includes M_H data. When curvature modulation is off (default), M_H is absent from the summary (no noise injection).

3. **Override confidence and psi_phase in overlay summary (P3):** Verifies amplitude overlay summary includes `override_confidence` and `psi_phase` fields in the context passed to LLM.

4. **Evidence block override count (P3b):** Verifies the override count is included in the evidence block when non-zero, and absent when zero (no false context injection for non-hybrid runs).

**Assessment:** These tests close a previously identified gap: LLM context quality was tested only via live API calls. The new tests verify the *content* of what gets sent, independently of whether the LLM is reachable. This is strictly better for CI stability and for verifying canon-alignment of LLM prompts.

---

### 2.5 `demo_burnout_iterate.py` — C37 Continuum Live Demo

The first demo where the number of iterations is **not prescribed** — it emerges from the landscape's tension structure.

**Key design points:**
- Uses the same 5-fragment burnout domain as `demo_burnout_composite.py`
- E0Envelope properly configured: `mode=AMPLITUDE_ON_DISAGREE, geometry="goal_reaching", h=4, transport=U1`
- `Session.iterate()` called with `max_iterations=5, tension_threshold=0.15`
- Per-iteration ResidualTensionMap printed: max/mean S_eff, resolved/amplified edges, hotspots

**Live test result (from commit message):**
- 2 iterations emerged (stopped on stagnation, not budget)
- Hotspots correctly identified: `ERROR_STATE` path and `AUTOFICTIONAL_ANALYSIS` — both unvisited
- This is a meaningful structural observation: the controller finds the "happy path" in iterations 1–2 but the tension-laden emotional states remain unresolved. Exactly the kind of structural insight E₀ is designed to surface.

**Canon alignment:** The demo explicitly names the iteration count as "not prescribed — it emerges from the landscape's tension structure." This is a correct formulation of Axiom A₀ applied to the iteration level.

---

## 3. Complete Module and Test Registry (2026-03-27)

### 3.1 Source modules

| Module | Phase | Test coverage | Tests | Status |
|---|---|---|---|---|
| `primitives.py` | Phase 1 | `test_envelope.py` (TransportRegime), `test_phase2_minidomain.py` | 48 (partial) | ✅ Stable (TransportRegime added) |
| `tension.py` | Phase 1 | `test_phase2_minidomain.py`, `test_historization_gordian.py` | 38+61 | ✅ Stable |
| `historization.py` | Phase 1 | `test_phase2_minidomain.py`, `test_historization_gordian.py` | 38+61 | ✅ Stable |
| `landscape.py` | Phase 1 + B2 | `test_curvature_modulation.py`, `test_phase2_minidomain.py` | 35+ | ✅ Stable (curvature-modulation-extended) |
| `potential.py` | Phase 2a + perf | `test_phase2_minidomain.py`, `test_amplitude_overlay.py` | partial | ✅ Stable (Helmholtz cached) |
| `connection.py` | Phase 2a + B2 | `test_curvature_modulation.py`, `test_omega_uniqueness.py`, `test_amplitude_overlay.py` | 35+27+125 | ✅ Stable |
| `wavepath.py` | Phase 2a | `test_phase2_minidomain.py`, `test_amplitude_overlay.py` | partial | ✅ Stable |
| `spinor_connection.py` | Phase 4a/4b + Tier 1–3 + B1 | `test_spinor.py`, `test_multi_axis_su2.py` | 71+36 | ✅ Research (complete) |
| `controller.py` | Phase 1–5h + Tier 1 + B1 | (many test files) | — | ✅ Stable (greedy/hybrid); ⚪ Alpha (Born sampling) |
| `amplitude_overlay.py` | Phase 3h–5f + Tier 1–3 + B1 | (many test files) | — | ✅ Stable |
| `dynamic_horizon.py` | Phase 5e | `test_dynamic_horizon.py` | 45 | ✅ Beta |
| `graph_validation.py` | Phase 3c | `test_graph_validation.py`, `test_scaling.py` | 24+14 | ✅ Stable |
| `memory_os.py` | Phase 2c, 5g | `test_memory_os.py`, `test_memos_geometry.py` | 28+34 | ✅ Beta (geometry-aware) |
| `evaluation.py` | Phase 3f, 5c | `test_evaluation.py`, `test_reflection_hybrid.py` | 42+42 | ✅ Beta |
| `reflection.py` | Phase 3g, 5c | `test_reflection.py`, `test_reflection_hybrid.py` | 36+42 | ✅ Beta |
| `llm_adapter.py` | Phase 3a | `test_llm_adapter.py`, `test_llm_context.py` | 47+23 | ✅ Beta (contract-tested offline) |
| `self_tuning.py` | Phase 5i | `test_self_tuning.py` | — | ✅ Beta |
| `provenance.py` | Phase 5j | `test_provenance.py` | — | ✅ Beta |
| `scenario_loader.py` | Phase 3e | `test_minidomain.py` (partial) | — | ✅ Stable |
| `domain_invoice.py` | Phase 3d | `test_invoice.py`, `test_phase2_invoice.py` | 33+18 | ✅ Stable |
| `validate_cross_domain.py` | Phase 3d | — (system test) | — | ✅ Stable |
| `benchmark_gridworld.py` | Phase 5k | no tests (executable benchmark) | — | ✅ Runnable |
| `explore_resonator.py` | Phase 4b + O5 | `test_resonator.py` | 73 | ✅ Research (generalized) |
| **`residual_tension.py`** | **C37 (NEW)** | **`test_residual_tension.py`** | **26** | **✅ Stable** |
| **`envelope.py`** | **C38 (NEW)** | **`test_envelope.py`** | **48** | **✅ Stable** |
| **`session.py`** | **C36/C37 (NEW)** | **`test_session.py`**, `test_residual_tension.py` | **13+6** | **✅ Beta** |

### 3.2 Test files summary

| File | Tests | New since 2026-03-26 |
|---|---|---|
| `test_amplitude_overlay.py` | 125 | — |
| `test_beipackzettel.py` | ~19 | — |
| `test_beipackzettel_noncircular.py` | — | — |
| `test_born_regime.py` | 44 | — |
| `test_born_sampling.py` | 31 | — |
| `test_burnout_composite.py` | — | — |
| `test_confidence_override.py` | 31 | — |
| `test_curvature_modulation.py` | 35 | — |
| `test_dynamic_horizon.py` | 45 | — |
| **`test_envelope.py`** | **48** | **✅ NEW** |
| `test_evaluation.py` | 42 | — |
| `test_ezb_zinsentscheidung.py` | — | — |
| `test_g5_edge_cases.py` | 55 | — |
| `test_gordian_trap.py` | 44 | — |
| `test_graph_validation.py` | 24 | — |
| `test_greedy_trap.py` | 4 | — |
| `test_historization_gordian.py` | 61 | — |
| `test_invoice.py` | 33 | — |
| `test_k5_escalation.py` | — | — |
| `test_llm_adapter.py` | 47 | — |
| **`test_llm_context.py`** | **23** | **✅ NEW (replaces skipped test_llm_integration.py)** |
| `test_mass_trap_detector.py` | — | — |
| `test_memory_os.py` | 28 | — |
| `test_memos_geometry.py` | 34 | — |
| `test_minidomain.py` | 21 | — |
| `test_multi_axis_su2.py` | 36 | — |
| `test_omega_uniqueness.py` | 27 | — |
| `test_phase2_invoice.py` | 18 | — |
| `test_phase2_minidomain.py` | — | — |
| `test_provenance.py` | — | — |
| `test_reflection.py` | 36 | — |
| `test_reflection_hybrid.py` | 42 | — |
| **`test_residual_tension.py`** | **26** | **✅ NEW** |
| `test_resonator.py` | 73 | — |
| `test_scaling.py` | 14 | — |
| `test_self_tuning.py` | — | — |
| **`test_session.py`** | **13** | **✅ NEW** |
| `test_spinor.py` | 71 | — |
| `test_topology_classification.py` | 30 | — |
| `test_waypoint.py` | 17 | — |
| **Total** | **1,499** | **+393 net passing; +361 total (incl. removal of 32 skipped); +110 in new files** |

---

## 4. Open Items and Follow-ups

### 4.1 Closed since 2026-03-26

| Item | Evidence |
|---|---|
| Expose `use_su2` as a typed controller parameter | ✅ `TransportRegime` enum + `E0Envelope` + bridge functions (`test_envelope.py`, 48 tests) |
| Modernize at least one LLM demo | ✅ `demo_burnout_iterate.py` uses Session.iterate(), E0Envelope, ResidualTensionMap, C37 |
| LLM context contract untestable offline | ✅ `test_llm_context.py` (23 tests) verifies SYSTEM_PROMPT content and MemOS summary fields without API key |

### 4.2 Carried Over from 2026-03-26

| Item | Priority | Note |
|---|---|---|
| `axis_fn` not persisted in MemOS | Low | Callables not serializable; document in controller docstring |
| SU(2) intensity not in evaluation/reflection metrics | Low | Would require new `su2_r_coh` metric |
| M_H formula comparison (1/(1+κ) vs exp(−κ)) | Low | Both documented in Paper 3; no empirical adjudication yet |
| Full θ derivation from v_rot (general) | Medium | Worked example exists; no general closed form |
| Resonator kernel integration into controller | Medium | 73 tests pass; kernel remains isolated from controller loop |
| Stochastic exploration policy | Research | BORN_SAMPLING available; no warm-up/switch policy |
| Formal correctness proof of G5 geometry | Research | Empirically validated to |G|=32; formal proof absent |

### 4.3 Newly Identified in This Analysis Period

| Item | Source | Priority |
|---|---|---|
| `Session.iterate()` reflection path not tested end-to-end | `should_reflect=True` verdict exists but no test verifies reflection injection | Low |
| Remaining 4 LLM demos still use Phase 3a surface | `demo_burnout_composite.py`, `demo_ezb_zinsentscheidung.py`, `demo_research_brief.py`, `demo_incident_postmortem.py` do not use Session/E0Envelope | Medium |
| `E0Envelope.from_dict` transport field fallback uses `"u1"` string literal | Minor: if a serialized envelope has an unknown transport value, the error is not explicit | Low |
| Session.iterate() does not pass `tension_threshold` to `should_continue` explicitly | `tension_threshold` param propagated correctly; confirmed by test — no actual bug | Note only |

---

## 5. Documentation Assessment

### 5.1 New Documents (none in this period)

No new documentation files were added in this analysis period. All additions are code files.

### 5.2 Documentation Status

The documentation corpus remains at the 2026-03-26 state:
- **`E0_CANON_ALIGNMENT_v1.md`** — Canon Alignment Report: 4 canon documents × 7 primitives; 4 open bridges (reflexivity, stochastic process, full θ derivation, SU(2) time-directionality)
- **`PAPER1_MANUSCRIPT_v1.md`** — Complete; reviewer fixes applied (v3); ready for arXiv submission
- **`PAPER2_MANUSCRIPT_v1.md`** — Complete; reviewer fixes applied
- **`E0_PAPER3_NON_ABELIAN_STRUCTURE_v1.md`** — Draft; roadmap targets 4 experiments
- **`E0_TEST_REGISTRY_v2.md`** — Last updated for 2026-03-26; not yet updated to reflect C37/C38

**Observation:** The test registry (`E0_TEST_REGISTRY_v2.md`) should be updated to include the C37 (residual tension + iteration) and C38 (E0Envelope) capabilities, as well as the Session orchestrator and TransportRegime primitive.

---

## 6. Overall Classification

### 6.1 Where E₀ Stands Today (2026-03-27)

The E₀ Controller as of 2026-03-27 is a **fully operational, multi-layered structural decision system with three complete scientific manuscripts and a self-organizing iteration loop**, comprising:

- A **formally verified primitive chain** (7 primitives, 1 axiom → ψ → I → P) proven unique in its phase generator (C14) and Born-rule realization (C17), now with **TransportRegime as a typed primitive** (U1 / SU2_MINIMAL / SU2_GEOMETRIC).
- A **production-grade greedy + hybrid controller** with four enumeration geometries, three controller modes, dynamic horizons, confidence gating, full MemOS persistence, and a **typed configuration envelope (E0Envelope)**.
- A **self-organizing iteration layer (C37)**: the controller can now be run in a loop where the number of iterations is not prescribed but emerges from the landscape's residual tension structure — a direct, running implementation of Axiom A₀ at the iteration level.
- A **research-grade non-Abelian extension** (SU(2) minimal, multi-axis, and geometric) verified numerically and non-commutative by construction.
- A **topological modulation layer** (curvature-derived M_H feedback).
- A **grid benchmark** (E₀ Greedy escapes all 3 trap variants; A* optimal).
- **CI infrastructure** (GitHub Actions, ≥1,000-test guard).
- **1,499 tests** covering the full dependency chain.
- **Three scientific manuscripts** (Papers 1–3) and a Canon Alignment Report.

### 6.2 Updated Maturity Table

| Layer | Maturity | Evidence |
|---|---|---|
| Core primitives (Δ, R, H, S, C, v, Ψ) | **Production-ready** | 100+ tests; stable across 5 analysis cycles |
| TransportRegime enum | **Production-ready (NEW)** | `test_envelope.py` (identity, bridge, round-trip) |
| Helmholtz decomposition (potential.py) | **Production-ready** | Cached; 6× speedup confirmed |
| Amplitude overlay (4 geometries) | **Beta → Production** | 125 overlay tests, G5 Born-aligned |
| Hybrid mode (AMPLITUDE_ON_DISAGREE) | **Beta** | Gordian trap escape, confidence gating confirmed |
| Born sampling (BORN_SAMPLING) | **Alpha/Research** | 31 tests, argmax dominance confirmed |
| Dynamic horizons | **Beta** | 45 tests, cross-domain verified |
| Confidence-weighted override | **Beta** | 31 tests, monotonic threshold-rate relationship |
| MemOS persistence | **Beta** | Geometry-aware; 62 round-trip tests; axis_fn gap documented |
| Reflection (amplitude triggers) | **Beta** | 42 tests, coherence + drift + phase triggers |
| **Session orchestrator (NEW)** | **Beta** | 13 tests; run/resume/iterate lifecycle verified |
| **E0Envelope (NEW)** | **Stable** | 48 tests; full API coverage; backward compat confirmed |
| **C37 Residual Tension (NEW)** | **Stable** | 26 tests; all 4 stopping conditions; Session.iterate() verified |
| SU(2) minimal (single-axis, σ_z) | **Research (complete)** | Phase 4a: 52 tests |
| SU(2) three-theory stack | **Research (complete)** | 14 tests; U(1)/min/geo comparison |
| SU(2) multi-axis (B1, axis_fn) | **Research (complete)** | 36 tests, per-edge axes, controller-integrated |
| SU(2) geometric (A⃗ coupling) | **Research (experimental)** | Implemented; `use_su2="geometric"` backend |
| M_H curvature modulation (B2) | **Research (complete)** | 35 tests, backward-compatible |
| Resonator layer | **Research (isolated)** | 73 tests; not connected to controller |
| LLM integration (contract-tested) | **Beta** | 47+23 tests; context contract verified offline |
| Grid benchmark | **Verified** | E₀ Greedy escapes all 3 variants |
| Waypoint / goal-with-continuations | **Verified** | 17 tests, H4 closure |
| Canon alignment | **Documented** | 533-line report; 7 primitives × 4 canon docs; 4 open bridges |
| CI / pyproject | **Active** | Python 3.11–3.13 matrix; ≥1,000-test guard; ruff config |
| Papers 1–3 | **Draft** | 3 complete manuscripts; P1 ready for arXiv |

### 6.3 Three-Tier Claim Classification (updated)

**Derived (mathematically necessary):**
- ω = ½(v_rot(x,y) − v_rot(y,x)) is the unique antisymmetric phase generator (C14)
- P(z) = I(z)/ΣI satisfies axioms B1–B5 and is the unique minimal realization rule (C17)
- SU(2) edge transport U = exp(−iω/2 · n̂ · σ⃗) is non-Abelian when axes differ (B1)
- M_H = 1/(1+κ) is bounded in (0,1] and equals 1 on flat (κ=0) graphs (B2)
- If Δ > 0 and a path with finite R exists, non-transition is structurally unstable (Axiom A₀) — **now implemented at both the edge level (controller) and the iteration level (C37)**

**Empirically demonstrated:**
- Gordian trap holonomy formula ΔΘ = ½[Σv(A-loop) − Σv(A-short)] (C8, 44 tests)
- G5 goal-reaching geometry enables hybrid override on traps (stable to |G|=32)
- `argmax(I)` dominates Born sampling on average across 50 random domains (C22)
- Topology-adaptive horizon selects h ≥ 5 on Gordian trap (C19)
- Multi-axis SU(2) overlay produces different decisions from single-axis on Gordian trap (C25)
- SU(2) phase halving causes Gordian override rate to drop 90%→0% (C23)
- Historization cannot create/destroy interference patterns: cross-topology invariant (O1)
- Multi-loop resonance: constructive interference factor ~2.0 on nested loop (C24)
- **Burnout iterative demo: 2 iterations emerged; hotspots (ERROR_STATE, AUTOFICTIONAL_ANALYSIS) correctly identified as unvisited high-tension edges (C37 live test)**

**Heuristic (empirically validated, not derived):**
- `topology_adaptive` horizon formula
- Reflection trigger thresholds (R_coh < 0.30, drift > 0.30, θ ≥ 0.70)
- Confidence gating default (0.0)
- M_H formula: 1/(1+κ) vs exp(−κ) — both candidates, neither formally justified
- C37 thresholds: hotspot (0.5), equilibrium (0.1), stagnation Δ (0.02) — empirically chosen

---

## 7. Proposed Next Steps

### 7.1 High Impact, Low Effort

1. **Update `E0_TEST_REGISTRY_v2.md`**: Add C37 (Residual Tension), C38 (E0Envelope), Session orchestrator (C36-related), and TransportRegime. The registry is currently the most outdated documentation artifact.

2. **Document `Session.iterate()` in `E0_ARCHITECTURE_OVERVIEW_v1.md`**: The iterative layer is a structurally significant addition (Axiom A₀ at iteration level). The architecture overview document should be updated to include C37 as a distinct architectural layer.

3. **Add `should_reflect` path test to `test_residual_tension.py`**: `IterationVerdict.should_reflect = True` is computed correctly but there is no test verifying that Session.iterate() acts on this recommendation (it currently logs but does not automatically inject reflection). Either document the gap or add the behavior.

### 7.2 High Impact, Medium Effort

4. **Modernize remaining 4 LLM demos**: `demo_burnout_composite.py` is the natural next candidate — it uses the same domain as `demo_burnout_iterate.py` and could be updated to use E0Envelope and optionally switch to `Session.run()`.

5. **Submit Paper 1 to arXiv**: P1 is at v3 (all reviewer fixes applied, 30 references integrated, ~9200 words). The only blocker is a submission decision.

6. **Connect resonator kernel to controller**: 73-test resonator layer is validated but isolated. Integration as a secondary amplitude modifier would close the largest isolated-module gap.

### 7.3 Research Directions

7. **M_H formula adjudication**: Run Gordian trap and triangle domain with both `M_H = 1/(1+κ)` and `M_H = exp(−κ)`. Add 6–8 comparison tests. This would convert the last open heuristic formula to an empirically adjudicated one.

8. **C37 stagnation handling**: Currently, `should_reflect=True` is set on stagnation but Session.iterate() does not automatically trigger `reflect_with_llm()`. Wiring this would close the C37 loop for LLM-backed domains.

9. **Stochastic exploration policy**: BORN_SAMPLING is available but lacks a principled warm-up/switch policy. Needed for multi-goal discovery and open-domain LLM operation.

10. **SU(2) reflexivity (Canon Bridge 4)**: The Canon Alignment Report identifies reflexivity as an open bridge. An SU(2)-based internal-state representation would close this.

---

## 8. Limitations and Risks (updated)

| Risk | Status | Mitigation |
|---|---|---|
| LLM landscape quality determines iteration behavior | Active | Graph quality check (`graph_quality()`) before iterate; demo confirms correct hotspot identification |
| C37 thresholds are heuristic | Active | Documented; flagged in three-tier classification |
| Session.iterate() reflection recommendation not yet acted upon | Active | Documented as open item 4.3 |
| axis_fn not serializable to MemOS | Active | Documented; low priority given experimental status of SU(2) multi-axis |
| Paper 1 not yet submitted | Active | Manuscript is at submission quality; action required externally |
| Resonator kernel isolated from controller | Active | 73 tests pass; integration design needed |

---

*This document intentionally records observations only. No code was changed during this analysis.*
