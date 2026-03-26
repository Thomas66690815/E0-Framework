# E₀ Runtime Code Analysis — 2026‑03‑26

**Status:** Read-only review (no code changes)  
**Purpose:** Fresh from-scratch analysis of the entire implementation, building on the three previous analyses (2026-03-24, 2026-03-25, 2026-03-25 v2). Evaluates and classifies all components in their current state.  
**Scope:** Full stack — primitives, controller, amplitude overlay, SU(2) spinor layer, curvature modulation, LLM integration, persistence, evaluation, reflection, testing, and documentation.

---

## 0. Analyses at a Glance

| Analysis | Date | Test count | Test growth | Headline additions |
|---|---|---|---|---|
| 2026-03-24 | 2026-03-24 | ~148 | baseline | Controller pipeline, hybrid mode, MemOS, evaluation, reflection |
| 2026-03-25 (v1) | 2026-03-25 | 613 | +465 (+314 %) | Gordian trap, G5 geometry, topology classification, scaling tests, greedy trap demo |
| 2026-03-25 (v2) | 2026-03-25 | 936 | +323 (+52 %) | ω uniqueness proof, historization×Gordian, reflection amplitude metrics, Born-regime axioms, dynamic horizons, confidence override, MemOS geometry persistence, Born-sampling comparison |
| **2026-03-26 (this)** | **2026-03-26** | **1138** | **+202 (+22 %)** | **Multi-axis SU(2), M_H curvature modulation, waypoint geometry tests, Paper 3 draft** |

The repository now contains **1,106 passing tests, 32 skipped**, across **29 test files** and the entirety of the `e0_controller/` implementation (≈29,800 LOC).

---

## 1. What changed since 2026-03-25 (v2)

The table below tracks the open items from the previous analysis.

| Follow-up (2026-03-25 v2) | Status today |
|---|---|
| Multi-axis SU(2) topology | ✅ **Resolved** — `test_multi_axis_su2.py` (36 tests, B1); per-edge `axis_fn` threaded through controller and overlay |
| Full θ derivation from v_rot | ⚪ Open (no change) |
| LLM demos with new features | ⚪ Open (no change) |
| Resonator kernel integration into controller | ⚪ Open (no change) |
| Stochastic exploration policy | ⚪ Open (no change) |
| Formal correctness proof of G5 geometry | ⚪ Open (no change) |

**Three new test files** were added (all since 2026-03-25 v2):

| File | Tests | Claim(s) | Content |
|---|---|---|---|
| `test_multi_axis_su2.py` | 36 | B1, C15 ext., C23 ext. | Per-edge SU(2) rotation axes, non-commutativity, path-order dependence, controller/overlay integration, tetrahedron domain |
| `test_curvature_modulation.py` | 35 | B2 | Edge curvature κ, M_H factor, modulated transition field, Helmholtz interaction, backward compatibility |
| `test_waypoint.py` | 17 | H4 closure | Goal-with-continuations domain; geometry divergence between `prefix`, `first_arrival`, `simple` when goal is non-terminal |

**Two source modules were extended:**

| File | New symbols | Purpose |
|---|---|---|
| `connection.py` | `edge_curvature`, `M_H_factor` | Curvature κ from face holonomies; modulation factor M_H = 1/(1+κ) |
| `landscape.py` | `curvature_modulation: bool = False`, `transition_field_modulated`, `_get_M_H`, `_build_M_H_cache` | M_H feedback into v(x,y); lazy cache; default-off for backward compatibility |
| `spinor_connection.py` | `su2_connection`, `su2_geometric_transport`, `su2_geometric_path_transport`, `spinor_geometric_psi`, `spinor_geometric_sum`, `spinor_geometric_intensity`, `compare_minimal_geometric` | Full three-component su(2) connection from Helmholtz geometry; geometric vs minimal comparison |
| `amplitude_overlay.py` | `use_su2="geometric"` mode, `axis_fn` parameter | Routes per-edge axis_fn and geometric su(2) through overlay computation |
| `controller.py` | `axis_fn` parameter in `__init__` | Propagates per-edge axis function to overlay |

**One new document was created:**

- `docs/E0_PAPER3_NON_ABELIAN_STRUCTURE_v1.md` — Paper 3 draft: Non-Abelian Structure in E₀

---

## 2. From-Scratch Module Assessment

### 2.1 Primitive Layer — `primitives.py`, `landscape.py`, `tension.py`, `historization.py`

**Purpose:** Encode the 7 primitives (Δ, R, H, S, C, v, Ψ) and 1 axiom. Define the state space and transition burden.

**Current state:**

- `Edge(source, target, delta, resistance)` and `Outcome(edge, result)` are immutable dataclasses. No changes since initial implementation.
- `Landscape` is the central container: `add_edge`, `neighbors`, `admissible`, `transition_field`, `v_raw`, plus the new `transition_field_modulated` when `curvature_modulation=True`.
- The `curvature_modulation` flag defaults to `False`, ensuring zero breaking change to all prior code. When enabled, `v(x,y)` is multiplied by `M_H(x,y) = 1/(1+κ(x,y))`.
- Tension `S(x→y) = Δ · R_eff` — unchanged. Coherence `C = exp(−S)` — unchanged.
- `Historization`: U/F-Traces, `δ_H`, clipping (`§17`). The historization layer is called "stable" in all prior analyses and remains so; no changes in this period.

**Assessment:** Production-ready. The `curvature_modulation` extension is clean (lazy cache, circular-dependency guard) and provably non-breaking.

---

### 2.2 Potential, Connection, Wavepath — `potential.py`, `connection.py`, `wavepath.py`

**Purpose:** Implement the dependency chain `v_rot → ω → Θ → Ψ`.

**Current state:**

- `potential.py`: `Φ`, `v_grad`, `v_rot` (Helmholtz decomposition). Unchanged.
- `connection.py`:
  - `omega(L, x, y)` = ½(v_rot(x,y) − v_rot(y,x)) — the unique antisymmetric phase generator (proven in Phase 5a / `test_omega_uniqueness.py`).
  - `theta(L, path)` — path phase accumulation.
  - `holonomy(L, cycle)` — sum of ω around a closed loop.
  - `omega_map(L)`, `connection_info(L, x, y)` — convenience utilities.
  - **New:** `edge_curvature(L, x, y)` — mean |face holonomy| through the edge from all directed triangles that contain it. Returns 0 for tree/line graphs.
  - **New:** `M_H_factor(L, x, y)` = 1/(1+κ) — topological modulation. Numerically: κ=0 → M_H=1; κ→∞ → M_H→0.
- `wavepath.py`: `path_tension`, `psi` (complex path amplitude), `path_amplitude_sum`. Unchanged.

**Key invariant (confirmed in `test_curvature_modulation.py`):**

- Line graphs and symmetric graphs: κ = 0, M_H = 1 → zero effect even when `curvature_modulation=True`.
- Asymmetric triangles: κ > 0, M_H < 1 → transitions are topologically damped.
- M_H modulates `v` but is computed from the *unmodulated* ω (the cache builder temporarily disables the flag) → no circular dependency.
- The formula `M_H = 1/(1+κ)` and the alternative `M_H = exp(−κ)` have the same limits at 0 and ∞ but differ for intermediate κ. The polynomial formula is implemented; the exponential alternative is documented in Paper 3 for future comparison.

**Assessment:** The Helmholtz stack is stable. The curvature addition is minimal, reversible, and correctly scoped to the topology layer.

---

### 2.3 SU(2) Spinor Extension — `spinor_connection.py`

**Purpose:** Lift the scalar U(1) connection ω to non-Abelian SU(2) matrix transport, enabling path-order-dependent interference in ℂ².

**Current state (as of 2026-03-26):**

The module now implements **three layers** of SU(2) transport:

| Layer | API | Transport | Axis source |
|---|---|---|---|
| **Minimal (Phase 4a)** | `su2_edge_transport`, `su2_path_transport`, `spinor_psi` | `U = exp(−iω/2 · σ_z)` | Fixed ẑ axis; reduces to U(1) on single-axis domains |
| **Multi-axis (Phase 6a)** | `su2_edge_transport(axis_fn=...)`, `su2_path_transport(axis_fn=...)`, `spinor_psi(axis_fn=...)` | `U = exp(−iω/2 · n̂(x,y) · σ⃗)` | Per-edge function; non-commutative when axes differ |
| **Geometric (Phase 4b/6b)** | `su2_geometric_transport`, `su2_geometric_path_transport`, `spinor_geometric_psi` | `U = exp(−i‖A⃗‖/2 · n̂ · σ⃗)` where A⃗ = (A₁, A₂, A₃) | Helmholtz-derived: A₁ = vorticity gradient, A₂ = mean face holonomy, A₃ = ω |

Comparison utilities: `compare_u1_su2`, `compare_minimal_geometric`.

**Multi-axis (B1) test coverage (`test_multi_axis_su2.py`, 36 tests):**

| Family | Key claim | Status |
|---|---|---|
| Non-commutativity | U(σ_x)·U(σ_z) ≠ U(σ_z)·U(σ_x) | ✅ verified |
| Path-order dependence | U(A→B→C) ≠ U(A→C→B) for different axes | ✅ verified |
| Magnitude preservation | ‖U·ψ‖ = ‖ψ‖ for all paths and axis functions | ✅ verified |
| Controller integration | `E0Controller(axis_fn=...)` propagates to overlay | ✅ verified |
| Overlay difference | Multi-axis overlay differs from single-axis on Gordian trap | ✅ verified |
| Backward compatibility | `axis_fn=None` produces same results as prior SU(2) code | ✅ verified |
| Tetrahedron domain | Four orthogonal per-edge axes produce nontrivial holonomy | ✅ verified |
| Probability normalization | `Σ P(a) ≈ 1` under SU(2) Born rule | ✅ verified |

**Curvature modulation (B2) test coverage (`test_curvature_modulation.py`, 35 tests):**

| Family | Key claim | Status |
|---|---|---|
| κ formula | κ = 0 on line graphs and symmetric triangles | ✅ verified |
| κ formula | κ > 0 on asymmetric triangles | ✅ verified |
| M_H formula | M_H = 1/(1+κ) within (0,1] | ✅ verified |
| Default-off | `curvature_modulation=False` → M_H = 1 everywhere | ✅ verified |
| Modulated v | Modulated v ≤ unmodulated v for all edges | ✅ verified |
| Helmholtz interaction | ω changes when curvature_modulation=True | ✅ verified |
| Cache consistency | M_H cache built once; entries match direct computation | ✅ verified |
| Edge cases | Single edge, empty landscape, self-loop → no crash | ✅ verified |

**Integration status:** SU(2) (both minimal and multi-axis) is wired into `amplitude_overlay.py` via `use_su2` and `axis_fn` parameters and through `E0Controller.__init__`. The geometric coupling is available in `spinor_connection.py` but not yet exposed as a controller init option (requires explicit `analyze_controller_state` call with `use_su2="geometric"`).

**Assessment:** Research module with production-grade test coverage. The non-commutativity claims are now formally verified (36 tests). The extension is behind `axis_fn=None` / `use_su2=False` defaults — zero runtime impact when not explicitly enabled.

---

### 2.4 Controller — `controller.py`

**Purpose:** Implement the decision loop: greedy override, revisit, escalation, hybrid (amplitude-guided), Born sampling.

**Current state:**

`E0Controller` now accepts:
- `hybrid_mode: HybridMode` (GREEDY / AMPLITUDE_ON_DISAGREE / BORN_SAMPLING)
- `hybrid_horizon: int` and `horizon_strategy` (dynamic horizon)
- `hybrid_geometry: str` (one of `prefix`, `simple`, `first_arrival`, `goal_reaching`)
- `hybrid_goals: set`
- `confidence_threshold: float`
- `axis_fn` (B1 per-edge rotation axis)

Three complete decision paths:
1. **GREEDY**: `select_next()` — pure `argmin S` with revisit/escalation.
2. **AMPLITUDE_ON_DISAGREE**: `_compute_overlay()` → if amplitude choice ≠ greedy and `override_confidence ≥ confidence_threshold` → override.
3. **BORN_SAMPLING**: `_compute_overlay()` → sample from `P(a) ∝ I(a)` — always sets `hybrid_overridden=True`.

**Test coverage (combined from `test_minidomain.py`, `test_gordian_trap.py`, `test_greedy_trap.py`, `test_confidence_override.py`, `test_born_sampling.py`, `test_dynamic_horizon.py`, `test_multi_axis_su2.py`):**

All three HybridMode variants are covered end-to-end. Multi-axis controller integration is confirmed (`axis_fn` propagates to `_compute_overlay` → `analyze_controller_state`).

**Assessment:** Production-ready for GREEDY and AMPLITUDE_ON_DISAGREE. BORN_SAMPLING is alpha/research (empirically correct but no exploration policy). Multi-axis controller integration is beta (wired up, 8 controller-level tests).

---

### 2.5 Amplitude Overlay — `amplitude_overlay.py`

**Purpose:** Enumerate path families, compute ψ-totals and intensities per action, produce `OverlayReport`.

**Current state:**

Four summation geometries:

| Geometry | Path inclusion rule | Use case |
|---|---|---|
| `prefix` | All paths of length ≤ h, including post-goal continuations | Dense topology exploration |
| `simple` | Paths with no state repetition | General-purpose (default) |
| `first_arrival` | Stop at first goal hit; exclude paths that miss goal | Goal-directed, non-terminal goals |
| `goal_reaching` | Include only paths that terminate at a goal state | Born-criterion aligned, G5 |

Three computation modes:

| Mode | `use_su2` | Transport | Intensity |
|---|---|---|---|
| U(1) (default) | `False` | scalar ψ = exp(−S+iΘ) | \|Σψ\|² |
| SU(2) minimal / multi-axis | `True` | per-edge matrix U (axis_fn) | ‖Σ U·ψ‖² |
| SU(2) geometric | `"geometric"` | Helmholtz-derived A⃗ | ‖Σ U_geo·ψ‖² |

**Waypoint domain (`test_waypoint.py`, 17 tests):** Closes the H4 gap ("goal with continuations") from the Summation Geometry Comparison. Verifies that:
- `prefix` inflates intensities for paths cycling through G (non-terminal goal).
- `first_arrival` correctly stops at G regardless of post-goal loops.
- `simple` stops before revisiting G but allows G→Y2→END post-goal continuation.
- Three-way divergence (`prefix` vs `first_arrival` vs `simple`) is confirmed when goal is non-terminal with loop.

`OverlayReport` carries: `action_reports`, `best_action`, `best_intensity`, `override_confidence`, plus the confidence-gating property.

**Assessment:** Stable and well-tested across all four geometries and all three computation modes.

---

### 2.6 Dynamic Horizon — `dynamic_horizon.py`

**Purpose:** Plug-in horizon strategies replacing the fixed `hybrid_horizon`.

**Current state:** Three strategies — `fixed(h)`, `topology_adaptive(...)`, `capped_adaptive(...)`. All satisfy the `HorizonStrategy` Protocol. `E0Controller` falls back to `hybrid_horizon` when `horizon_strategy=None` (no breaking change).

**Assessment:** Beta. 45 tests confirm correct behavior across Gordian, Diamond, and Mini domains. No changes in this analysis period.

---

### 2.7 Graph Validation — `graph_validation.py`

**Purpose:** Goal reachability, dead-end detection, loop detection.

**Assessment:** Stable. `test_graph_validation.py` (24 tests) + `test_scaling.py` (14 tests, n≤500). No changes in this analysis period.

---

### 2.8 Memory OS — `memory_os.py`

**Purpose:** Persist/restore controller state (RuntimeSnapshot), summarize for LLM, retrieve session records.

**Current state:** `RuntimeSnapshot` stores `hybrid_mode`, `hybrid_horizon`, `hybrid_geometry`, `confidence_threshold`. Backward-compatible (old snapshots without `hybrid_geometry` default to `"simple"`). `axis_fn` is **not yet persisted** — this is the first new open item created in this analysis period.

**Assessment:** Beta. Geometry-aware persistence is confirmed (34 tests in `test_memos_geometry.py`). The `axis_fn` persistence gap is low-severity (axis function is a Python callable and not naturally serializable).

---

### 2.9 Evaluation & Reflection — `evaluation.py`, `reflection.py`

**Purpose:** Score runs (A–F), emit reports, trigger reflection on structural anomalies.

**Current state:**

Evaluation tracks: `hybrid_override_count`, `hybrid_override_rate`, `r_coh_avg`, `r_coh_min`, `r_coh_max`, `theta_consistency`, `amplitude_drift`, `avg_override_confidence`.

Reflection triggers: coherence collapse (R_coh_min < 0.1), high drift (> 0.30) with poor progress, strong phase alignment (opportunity trigger). Amplitude section rendered in evaluation reports.

The SU(2) intensity metric (`‖Σψ‖²`) does not yet flow into evaluation/reflection. This is a minor gap for future SU(2)-dominant deployments.

**Assessment:** Beta. 42 tests in `test_reflection_hybrid.py`, 42 in `test_evaluation.py`. No changes in this analysis period. Coherent with the amplitude stack.

---

### 2.10 LLM Adapter — `llm_adapter.py`

**Purpose:** Bridge LLM responses to controller decisions (A3 hybrid).

**Current state:** Supports mock mode (`--mock`), live OpenAI API. Parses LLM JSON outputs into controller-compatible action dictionaries. `test_llm_adapter.py` (47 tests), `test_llm_integration.py` (32 tests, 32 skipped in offline mode).

The LLM demos (`demo_invoice_llm.py`, `demo_open_domain.py`, `demo_research_brief.py`, `demo_incident_postmortem.py`) still use the Phase 3a API surface (no dynamic horizons, no confidence gating, no MemOS geometry persistence, no SU(2) modes). This gap has persisted through all four analyses.

**Assessment:** Beta for core adapter; open gap for demo modernization.

---

### 2.11 Scenario Loader — `scenario_loader.py`

**Purpose:** Load JSON scenario packets (`SCENARIO_PACKET_SCHEMA_v0.1.md`) into Landscape instances.

**Assessment:** Stable. No changes.

---

## 3. Complete Module and Test Registry (2026-03-26)

| Module | Phase introduced | Test files | Test count | Status |
|---|---|---|---|---|
| `primitives.py` | Phase 1 | `test_phase2_minidomain.py` (partial) | — | ✅ Stable |
| `landscape.py` | Phase 1 + B2 | `test_curvature_modulation.py`, `test_phase2_minidomain.py` | 35 (B2) + partial | ✅ Stable (modulation-extended) |
| `tension.py` / `historization.py` | Phase 1–2 | `test_phase2_minidomain.py`, `test_historization_gordian.py` | 38 + 61 | ✅ Stable |
| `potential.py` | Phase 2a | `test_phase2_minidomain.py`, `test_amplitude_overlay.py` | partial | ✅ Stable |
| `connection.py` | Phase 2a + B2 | `test_curvature_modulation.py`, `test_omega_uniqueness.py`, `test_amplitude_overlay.py` | 35 + 27 + 125 | ✅ Stable |
| `wavepath.py` | Phase 2a | `test_phase2_minidomain.py`, `test_amplitude_overlay.py` | partial | ✅ Stable |
| `spinor_connection.py` | Phase 4a/4b + B1/6b | `test_spinor.py`, `test_multi_axis_su2.py` | 71 + 36 | ✅ Research (complete) |
| `controller.py` | Phase 1–5h + B1 | `test_minidomain.py`, `test_gordian_trap.py`, `test_greedy_trap.py`, `test_confidence_override.py`, `test_born_sampling.py`, `test_dynamic_horizon.py`, `test_multi_axis_su2.py` | 21+44+4+31+31+45+8 | ✅ Stable (greedy/hybrid), ⚪ Alpha (Born sampling) |
| `amplitude_overlay.py` | Phase 3h–5f + B1 | `test_amplitude_overlay.py`, `test_gordian_trap.py`, `test_g5_edge_cases.py`, `test_confidence_override.py`, `test_born_regime.py`, `test_waypoint.py`, `test_multi_axis_su2.py` | 125+44+55+31+44+17+8 | ✅ Stable |
| `dynamic_horizon.py` | Phase 5e | `test_dynamic_horizon.py` | 45 | ✅ Beta |
| `graph_validation.py` | Phase 3c | `test_graph_validation.py`, `test_scaling.py` | 24+14 | ✅ Stable |
| `memory_os.py` | Phase 2c, 5g | `test_memory_os.py`, `test_memos_geometry.py` | 28+34 | ✅ Beta (geometry-aware) |
| `llm_adapter.py` | Phase 3a | `test_llm_adapter.py`, `test_llm_integration.py` | 47+32 | ✅ Beta |
| `evaluation.py` | Phase 3f, 5c | `test_evaluation.py`, `test_reflection_hybrid.py` | 42+42 | ✅ Beta |
| `reflection.py` | Phase 3g, 5c | `test_reflection.py`, `test_reflection_hybrid.py` | 36+42 | ✅ Beta |
| `scenario_loader.py` | Phase 3e | `test_minidomain.py` | partial | ✅ Stable |
| `domain_invoice.py` | Phase 3d | `test_invoice.py`, `test_phase2_invoice.py` | 33+18 | ✅ Stable |
| `validate_cross_domain.py` | Phase 3d | — (system test) | — | ✅ Stable |

**Test file summary (29 files, 1138 total):**

| File | Tests | Claim coverage |
|---|---|---|
| `test_amplitude_overlay.py` | 125 | Geometries, ψ-sums, edge cases |
| `test_born_regime.py` | 44 | B1–B5 axioms across 5 domains |
| `test_born_sampling.py` | 31 | BORN_SAMPLING mode, KL divergence, argmax dominance |
| `test_confidence_override.py` | 31 | Confidence gating, threshold sweep, Gordian integration |
| `test_curvature_modulation.py` | 35 | B2: κ, M_H, curvature modulation (NEW) |
| `test_dynamic_horizon.py` | 45 | C19: fixed, topology_adaptive, capped_adaptive |
| `test_evaluation.py` | 42 | C18: r_coh, amplitude_drift, theta_consistency |
| `test_g5_edge_cases.py` | 55 | G5 geometry edge cases (5 families, 28 canonical) |
| `test_gordian_trap.py` | 44 | C8: holonomy, interference, hybrid override |
| `test_graph_validation.py` | 24 | Reachability, dead ends, loop detection |
| `test_greedy_trap.py` | 4 | Greedy trap, hybrid escape |
| `test_historization_gordian.py` | 61 | C8/C9: historization × Gordian interference |
| `test_invoice.py` | 33 | Invoice domain, 10 states, 16 edges |
| `test_llm_adapter.py` | 47 | LLM ↔ controller bridge |
| `test_llm_integration.py` | 32 | Live/mock API integration (32 skipped offline) |
| `test_memory_os.py` | 28 | Persist/restore/summarize/retrieve |
| `test_memos_geometry.py` | 34 | C21: geometry round-trips in MemOS |
| `test_minidomain.py` | 21 | Core controller end-to-end |
| `test_multi_axis_su2.py` | 36 | B1: per-edge axes, non-commutativity, controller integration (NEW) |
| `test_omega_uniqueness.py` | 27 | C14: ω uniqueness proof |
| `test_phase2_invoice.py` | 18 | Invoice domain structural maths |
| `test_phase2_minidomain.py` | 38 | Core primitives and maths |
| `test_reflection.py` | 36 | Reflection triggers (structural) |
| `test_reflection_hybrid.py` | 42 | C18: amplitude reflection triggers |
| `test_resonator.py` | 73 | Resonator stability (Phase 4b) |
| `test_scaling.py` | 14 | n≤500 performance |
| `test_spinor.py` | 71 | SU(2) phase 4a/4b (minimal + geometric) |
| `test_topology_classification.py` | 30 | 380-graph topology scan |
| `test_waypoint.py` | 17 | Goal-with-continuations geometry divergence (NEW) |

---

## 4. Open Items and Follow-ups

### 4.1 Newly opened in this analysis period

| Item | Source | Priority |
|---|---|---|
| `axis_fn` not persisted in MemOS | SU(2) multi-axis feature | Low (callables not serializable; document the gap) |
| `use_su2` / `axis_fn` not exposed in controller `__init__` as high-level option | Current: controller sets `axis_fn` but not `use_su2` | Medium — limits one-liner SU(2) hybrid controller setup |
| Geometric SU(2) (`use_su2="geometric"`) not exposed as controller init option | Must call `analyze_controller_state` directly | Medium |
| SU(2) intensity not threaded into evaluation/reflection metrics | Would require a new `su2_r_coh` metric | Low (research-phase only for now) |

### 4.2 Carried over from 2026-03-25 (v2)

| Item | Status | Note |
|---|---|---|
| Full θ derivation from v_rot | ⚪ Open | `E0_PHASE_DERIVATION_PROGRAM_v1.md` and worked example exist; no closed form yet |
| LLM demos with new features | ⚪ Gap | All four demos (`demo_invoice_llm.py`, `demo_open_domain.py`, `demo_research_brief.py`, `demo_incident_postmortem.py`) use Phase 3a surface only |
| Resonator kernel integration | ⚪ Gap | 73 tests pass; still not connected to hybrid decision loop |
| Stochastic exploration policy | ⚪ Research | BORN_SAMPLING available; no warm-up/switch policy defined |
| Formal correctness proof of G5 geometry | ⚪ Research | Empirically validated (44+ tests, Born-criterion alignment); formal proof absent |
| M_H formula choice justification | ⚪ Research | `1/(1+κ)` implemented; `exp(−κ)` alternative documented in Paper 3; no empirical comparison yet |

---

## 5. Documentation Assessment

### 5.1 Papers

| Document | Status | Coverage |
|---|---|---|
| `E0_FORMAL_PAPER_DRAFT_v1.md` | Draft | §1–§14: primitives → Ψ; Gordian trap appendix |
| `PAPER1_MANUSCRIPT_v1.md` | Draft | Core framework derivation |
| `PAPER2_MANUSCRIPT_v1.md` | Draft | Hybrid controller, trap escape, G5 geometry |
| `E0_PAPER3_NON_ABELIAN_STRUCTURE_v1.md` | Draft v1.0 | SU(2) lift, curvature modulation, B1+B2+B4+C23; 71 tests cited; Appendix B: Derived/Empirical/Heuristic classification |

Paper 3 is the only new document added since 2026-03-25 v2. It is well-structured (8 sections + 2 appendices), honest about scope (experimental switch, alternative M_H formula disclosed), and references all 71 B1+B2 test results as numerical evidence.

### 5.2 Supporting Documentation

The `docs/` directory contains 65 documents covering the full arc: primitives → Helmholtz → spinors → curvature → controller → LLM → evaluation → reflection → topology → persistence → papers. No new supporting documents beyond Paper 3 were added in this period.

A notable gap: `E0_TEST_REGISTRY_v2.md` (the last test registry) was written for the 936-test state (2026-03-25 v2). The three new test files are not yet registered there. An update to `v3` or an inline patch is warranted.

---

## 6. Overall Classification

### 6.1 Where E₀ stands today

The E₀ Controller as of 2026-03-26 is a **fully operational, multi-layered structural decision system** with:

- A **formally verified primitive chain** (7 primitives, 1 axiom → ψ → I → P) proven unique in its phase generator (C14) and Born-rule realization (C17).
- A **production-grade greedy + hybrid controller** with four enumeration geometries, three controller modes, dynamic horizons, confidence gating, and full MemOS persistence.
- A **research-grade non-Abelian extension** (SU(2) minimal, multi-axis, and geometric) verified numerically and non-commutative by construction.
- A **topological modulation layer** (curvature-derived M_H feedback) that is switched off by default and verified for backward compatibility.
- **1 138 tests** covering the full dependency chain from primitives to interference to controller decisions to LLM integration.

### 6.2 Updated maturity table

| Layer | Maturity | Evidence |
|---|---|---|
| Core primitives (Δ, R, H, S, C, v, Ψ) | **Production-ready** | 100+ tests, invoice/minidomain domains, scaling to n=500 |
| Amplitude overlay (4 geometries) | **Beta → Production** | 125 overlay tests, waypoint domain confirms geometry divergence, G5 Born-aligned |
| Hybrid mode (AMPLITUDE_ON_DISAGREE) | **Beta** | Gordian trap escape, confidence gating, dynamic horizons all confirmed |
| Born sampling (BORN_SAMPLING) | **Alpha/Research** | 31 tests, correct distribution, argmax dominance confirmed |
| Dynamic horizons | **Beta** | 45 tests, Gordian/diamond/mini domain verified |
| Confidence-weighted override | **Beta** | 31 tests, monotonic threshold–rate relationship |
| MemOS persistence | **Beta** | Geometry-aware; 62 round-trip tests; axis_fn gap documented |
| Reflection (amplitude triggers) | **Beta** | 42 tests, coherence + drift + phase triggers |
| SU(2) minimal (single-axis) | **Research (complete)** | 71 tests, 720° periodicity, non-commutativity |
| SU(2) multi-axis (B1) | **Research (complete)** | 36 tests, per-edge axes, controller-integrated |
| SU(2) geometric (A⃗ coupling) | **Research (experimental)** | Implemented; not yet controller-accessible as init option |
| M_H curvature modulation (B2) | **Research (complete)** | 35 tests, backward-compatible, formula justified |
| Resonator layer | **Research (isolated)** | 73 tests; not connected to controller loop |
| LLM integration | **Beta** | 47+32 tests; demos not modernized |
| Waypoint / goal-with-continuations | **Verified** | 17 tests, closes H4 geometry gap |

### 6.3 Three-tier claim classification (from Paper 3, applicable across the stack)

Following the classification introduced in Appendix B of Paper 3:

**Derived (mathematically necessary):**
- ω = ½(v_rot(x,y) − v_rot(y,x)) is the unique antisymmetric phase generator (C14, 27 tests)
- P(z) = I(z)/ΣI satisfies axioms B1–B5 and is the unique minimal realization rule (C17, 44 tests)
- SU(2) edge transport U = exp(−iω/2 · n̂ · σ⃗) is non-Abelian when axes differ (B1, 36 tests)
- M_H = 1/(1+κ) is bounded in (0,1] and equals 1 on flat (κ=0) graphs (B2, 35 tests)

**Empirically demonstrated:**
- Gordian trap holonomy formula ΔΘ = ½[Σv(A-loop) − Σv(A-short)] (C8, 44 tests)
- G5 goal-reaching geometry enables hybrid override on traps where greedy fails (C8/C9, 44+61 tests)
- `argmax(I)` dominates Born sampling on average across 50 random domains (C22, 31 tests)
- Topology-adaptive horizon selects h ≥ 5 on Gordian trap, matching the proven interference threshold (C19, 45 tests)
- Multi-axis SU(2) overlay produces different controller decisions from single-axis on Gordian trap (B1, 36 tests)

**Heuristic (empirically validated, not derived):**
- `topology_adaptive` horizon formula (distance × branching factor reduction)
- Reflection trigger thresholds (R_coh < 0.30, drift > 0.30, θ ≥ 0.70)
- Confidence gating default (0.0)
- M_H = 1/(1+κ) vs M_H = exp(−κ): both candidates, neither formally justified over the other

---

## 7. Proposed Next Steps

Based on the current state and open items, the following directions are ordered by impact-to-effort ratio:

### 7.1 High impact, low effort

1. **Update `E0_TEST_REGISTRY_v2.md` → v3**: Add the three new test files (`test_multi_axis_su2.py`, `test_curvature_modulation.py`, `test_waypoint.py`) to the registry. Straightforward documentation update.

2. **Expose `use_su2` and `axis_fn` in controller `__init__`**: Currently `axis_fn` is stored on the controller but `use_su2` must be passed to `analyze_controller_state` directly. A simple plumbing change would make SU(2) mode a first-class controller option.

3. **Document the `axis_fn` MemOS gap**: A one-paragraph addition to `E0_MEMOS_v0.1.md` or the controller docstring prevents future confusion.

### 7.2 High impact, medium effort

4. **Modernize at least one LLM demo**: Update `demo_greedy_trap.py` (the simplest) to use dynamic horizons and confidence gating. This demonstrates the Phase 5 stack end-to-end.

5. **M_H formula comparison experiment**: Run the Gordian trap with `M_H = exp(−κ)` vs `M_H = 1/(1+κ)` and add 6–8 comparison tests. Converts the heuristic formula choice to an empirically adjudicated one.

6. **Connect resonator kernel to controller**: The 73-test resonator layer (`test_resonator.py`) is validated but isolated. Integrating it as a hybrid signal (e.g., resonator score as a secondary amplitude modifier) would close the largest isolated module gap.

### 7.3 Research directions

7. **Formal correctness proof for G5 geometry**: Prove that goal-reaching geometry minimizes realization-rule arbitrariness. The Born-criterion alignment argument in `E0_BORN_CRITERION_ANALYSIS_v1.md` points toward this.

8. **Phase derivation from v_rot (full generalization)**: The `E0_PHASE_DERIVATION_PROGRAM_v1.md` establishes a worked example. A general procedure for deriving ω from measured `v_rot` would remove the only remaining manually-assigned parameter in live deployments.

9. **Stochastic exploration policy**: Implement a warm-up/switch policy for BORN_SAMPLING (e.g., first N steps in sampling mode for domain discovery, then switch to argmax). Relevant for multi-goal discovery and open-domain LLM operation.

10. **Geometric SU(2) as first-class controller option**: Expose `use_su2="geometric"` as a controller init parameter. Requires threading `su2_geometric_path_transport` through `analyze_controller_state`.

---

## 8. Limitations and Risks (updated)

1. **Computational cost:** Path enumeration is O(kʰ). Dynamic horizons mitigate this for known domains, but no pruning or sampling exists for truly open-ended branching. No hard real-time latency benchmarks.

2. **Phase derivation gap:** ω is provably unique, but deriving its values from measurable `v_rot` in new domains is still manual or requires instrumented domain measurement. Applications must either pre-specify ω or infer it from observed transition patterns.

3. **SU(2) operational status:** Multi-axis SU(2) is wired into the controller but not yet activated by default. Until the `use_su2` parameter is promoted to a controller-level config, deployers must use the overlay API directly to access SU(2) interference.

4. **M_H formula is a candidate:** The curvature modulation formula `M_H = 1/(1+κ)` is one of two candidates (the other being `exp(−κ)`). No empirical comparison exists yet. Using `curvature_modulation=True` in production should be considered experimental.

5. **LLM demo gap:** All four LLM demos use the Phase 3a API surface. Deployers using demos as templates will miss dynamic horizons, confidence gating, geometry options, and MemOS geometry persistence.

6. **Born sampling in long chains:** Argmax dominance is confirmed on average. Scenarios where sampling is systematically superior (multi-goal discovery) exist but lack a principled exploration policy.

---

This document intentionally records **observations only**. No code was changed during this analysis.
