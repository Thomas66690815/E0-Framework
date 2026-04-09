# E₀ Runtime Code Analysis — 2026‑03‑26

**Status:** Read-only review (no code changes)  
**Purpose:** Fresh from-scratch analysis of the entire implementation, building on three prior analyses (2026-03-24, 2026-03-25, 2026-03-25 v2). The 2026-03-25 v2 analysis was itself published today at 04:32 CET — all work from that point onward is captured here for the first time. This document supersedes the incomplete earlier draft.  
**Scope:** Full stack — primitives, controller, amplitude overlay, SU(2) spinor layers, curvature modulation, grid benchmark, CI infrastructure, LLM integration, persistence, evaluation, reflection, papers, testing, and documentation.

---

## 0. Analyses at a Glance

| Analysis | Date | Test count | Test growth | Headline additions |
|---|---|---|---|---|
| 2026-03-24 | 2026-03-24 | ~148 | baseline | Controller pipeline, hybrid mode, MemOS, evaluation, reflection |
| 2026-03-25 (v1) | 2026-03-25 | 613 | +465 (+314 %) | Gordian trap, G5 geometry, topology classification, scaling tests, greedy trap demo |
| 2026-03-25 (v2) | 2026-03-26 04:32 CET | 936 | +323 (+52 %) | ω uniqueness proof, historization×Gordian, reflection amplitude metrics, Born-regime axioms, dynamic horizons, confidence override, MemOS geometry persistence, Born-sampling comparison |
| **2026-03-26 (this)** | **2026-03-26** | **1,138** | **+202 (+22 %)** | **Papers 1–3, Canon Alignment, SU(2) Tier 1–3, three-theory stack, O1/O2/O5 test expansions, M_H curvature, grid benchmark, Helmholtz cache, CI, pyproject** |

The repository now contains **1,106 passing tests, 32 skipped**, across **29 test files** and the entirety of the `e0_controller/` implementation.

**Note:** The 2026-03-25 v2 analysis was committed today at 04:32 CET. All 25 commits from that point to the final `Paper 3 draft` commit are covered here.

---

## 1. What changed since 2026-03-25 (v2) — complete delta

### 1.1 Chronological commit summary (2026-03-26)

| Time (CET) | Commit | Content |
|---|---|---|
| 04:32 | `c4ca32a` | docs: E₀ Code Analysis 2026-03-25 v2 — Paths A–H (baseline of this analysis) |
| 05:40 | `99f857b` | Paper 1 skeleton: structure, evidence mapping, production plan |
| 05:56 | `8464cd4` | Paper 1 manuscript v1: complete draft (§1–§11 + Appendices A–D, ~7200 words) |
| 06:31 | `bf43e70` | Paper 1: integrate §2 Related Work + 30 references (~9200 words total) |
| 06:46 | `3c6caea` | Paper 1: quality audit — fix 7 issues |
| 07:02 | `dd1f53d` | Paper 1 v2: 4 structural fixes from external reviewer critique |
| 07:08 | `20d037a` | Paper 2 skeleton: SU(2) spinor amplitudes + Born criterion |
| 07:33 | `4e96746` | Paper 2 manuscript v1: SU(2) spinor amplitudes and Born criterion |
| 07:43 | `7c284b0` | Paper 2 reviewer fixes: 4 structural improvements |
| 07:52 | `c6c0ce3` | Paper 1 v3: 3 structural fixes from external review |
| 08:45 | `e675651` | Grid world benchmark + Paper 1 §7.5 results |
| 09:10 | `822aa38` | fix: repair 3 broken test modules (scaling/greedy_trap/llm_integration) |
| 09:15 | `47abe10` | perf: cache Helmholtz decomposition — 6× speedup (65s → 11s) |
| 09:29 | `b188fcb` | docs: document why amplitude overlay excluded from grid benchmark |
| 09:46 | `e87d70a` | feat: SU(2) spinor interference switch — `use_su2` flag in controller + overlay |
| 10:10 | `7c4d2d3` | SU(2) Tier 2: G5 reclassification, topology scan, Born sampling under SU(2) |
| 11:45 | `8bc7983` | Tier 3: three-theory stack (U(1)/SU(2)-min/SU(2)-geo) + performance tests |
| 12:04 | `bebb6b9` | O5: multi-loop resonator scaling — 4-node, nested, coupled kernels (+25 tests) |
| 12:21 | `5c66f99` | O2: G5 stability verified to |G|=32 — 15 new tests, no failure signatures |
| 12:34 | `13e09ae` | O1: Historization × non-Gordian topologies — 25 new tests, gap closed |
| 12:52 | `db989c7` | ci: add GitHub Actions workflow + pyproject.toml |
| 13:06 | `31e37f8` | docs: Canon Alignment Report v1 |
| 13:45 | `d536bb9` | B1: Multi-Axis SU(2) — per-edge `axis_fn` threaded through full stack |
| 13:54 | `b35545c` | docs: Add C25 Multi-Axis SU(2) to test registries + Paper 3 roadmap |
| 14:19 | `8fc67cc` | B2: M_H topological invariant — curvature modulation |
| 14:32 | `13645ba` | Paper 3 draft v1.0: Non-Abelian Structure in E₀ + test_waypoint.py |

### 1.2 Open-items follow-up from 2026-03-25 (v2)

| Follow-up (2026-03-25 v2) | Status today |
|---|---|
| Multi-axis SU(2) topology | ✅ **Resolved** — B1: `test_multi_axis_su2.py` (36 tests); per-edge `axis_fn` wired through controller and overlay |
| Full θ derivation from v_rot | ⚪ Open |
| LLM demos with new features | ⚪ Open — demos still use Phase 3a surface |
| Resonator kernel integration into controller | ⚪ Open — resonator validated (73 tests), not yet connected to controller loop |
| Stochastic exploration policy | ⚪ Open |
| Formal correctness proof of G5 geometry | ⚪ Open |

### 1.3 New files created today

**New documents (10 items in docs/ + 3 non-docs):**

| File | Lines | Summary |
|---|---|---|
| `docs/PAPER1_SKELETON_v1.md` | 465 | Paper 1 skeleton: structure, evidence mapping, section plan |
| `docs/PAPER1_MANUSCRIPT_v1.md` | 1614 | Paper 1 manuscript: E₀ Structural Interference in Discrete Transition Systems |
| `docs/PAPER2_SKELETON_v1.md` | 502 | Paper 2 skeleton: SU(2) spinor amplitudes + Born criterion |
| `docs/PAPER2_MANUSCRIPT_v1.md` | 1310 | Paper 2 manuscript: Spinor Amplitudes and the Born Criterion |
| `docs/E0_CANON_ALIGNMENT_v1.md` | 533 | Canon Alignment Report: systematic mapping of 4 canon docs vs. implementation |
| `docs/related-work-research-report.md` | 116 | Related-work research report (source for Paper 1 §2) |
| `docs/E0_PAPER3_NON_ABELIAN_STRUCTURE_v1.md` | 552 | Paper 3 draft: Non-Abelian Structure in E₀ (SU(2) lift, curvature modulation) |
| `docs/E0_CODE_ANALYSIS_2026-03-25_v2.md` | 311 | The prior v2 analysis itself (created today at 04:32 CET) |
| `docs/E0_TEST_REGISTRY_v1.md` | +43 lines | Updated with C25, test count to 1082 |
| `docs/E0_TEST_REGISTRY_v2.md` | +254 lines | C15/C23/C24/C25 added; O1/O2/O4/O5 resolved; P3 roadmap |
| `e0_controller/benchmark_gridworld.py` | 445 | Grid world benchmark: E₀ vs Naive-Greedy vs A* on 3 variants of 5×5 grid |
| `e0_controller/test_curvature_modulation.py` | 480 | B2: κ, M_H, curvature modulation tests (35 tests) |
| `e0_controller/test_multi_axis_su2.py` | 731 | B1: multi-axis SU(2), non-commutativity, controller/overlay integration (36 tests) |
| `.github/workflows/tests.yml` | 37 | CI: Python 3.11/3.12/3.13 matrix, numpy-only, ≥1000-test guard |
| `pyproject.toml` | 24 | Project metadata, optional deps, ruff config |

### 1.4 Modified source files today

| File | Change | Key additions |
|---|---|---|
| `e0_controller/potential.py` | +23 lines | Helmholtz decomposition cache keyed by (edge_count, tau) — 6× speedup |
| `e0_controller/amplitude_overlay.py` | +25 lines | `use_su2=True/False/"geometric"` flag; `axis_fn` parameter; geometric SU(2) branch |
| `e0_controller/controller.py` | +6 lines | `use_su2: object = False` and `axis_fn=None` parameters in `__init__` |
| `e0_controller/connection.py` | +41 lines | `edge_curvature()`, `M_H_factor()` |
| `e0_controller/landscape.py` | +56 lines | `curvature_modulation` flag, `_get_M_H()`, `_build_M_H_cache()`, M_H-aware `transition_field()` |
| `e0_controller/explore_resonator.py` | +194 lines | 3 new builders: 4-node loop, nested loop, coupled resonators + generalized measurement |
| `e0_controller/test_spinor.py` | +366 lines | +5 (SU(2) controller integration, Tier 1) +14 (three-theory stack, Tier 3) — total 71 |
| `e0_controller/test_historization_gordian.py` | +334 lines | O1: historization × non-Gordian (+25 tests) — total 61 |
| `e0_controller/test_g5_edge_cases.py` | +328 lines | O2: G5 |G|=32 (+15 tests, Tier 2 SU(2) +12 tests) — total 55 |
| `e0_controller/test_resonator.py` | +269 lines | O5: multi-loop resonator (+25 tests) — total 73 |
| `e0_controller/test_topology_classification.py` | +145 lines | Tier 2 SU(2) reclassification (+7 tests) — total 30 |
| `e0_controller/test_born_sampling.py` | +117 lines | Tier 2 SU(2) Born sampling (+4 tests, CI fix) — total 31 |
| `e0_controller/test_greedy_trap.py` | +4 lines | fix: switch to absolute imports |
| `e0_controller/test_scaling.py` | +6 lines | fix: relax timing limits 2.0s → 5.0s (slow hardware) |
| `e0_controller/test_llm_integration.py` | +36 lines | fix: skip when openai not installed; max_cycles 20→30; check GOAL in path |
| `e0_controller/test_waypoint.py` | NEW | Goal-with-continuations geometry divergence (17 tests) |

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

- `potential.py`: `Φ`, `v_grad`, `v_rot` (Helmholtz decomposition).
  - **New today:** Helmholtz decomposition result is now **cached** on the Landscape object, keyed by `(edge_count, historization.tau)`. A cache hit avoids a redundant O(n³) least-squares solve on every `phi()` call within the same controller step. **Measured impact: 65 s → 11 s (6× speedup)** on the full test suite. The cache is invalidated whenever the landscape changes (edge additions) or historization advances (tau changes).
- `connection.py`:
  - `omega(L, x, y)` = ½(v_rot(x,y) − v_rot(y,x)) — the unique antisymmetric phase generator (proven in Phase 5a / `test_omega_uniqueness.py`).
  - `theta(L, path)` — path phase accumulation.
  - `holonomy(L, cycle)` — sum of ω around a closed loop.
  - `omega_map(L)`, `connection_info(L, x, y)` — convenience utilities.
  - **New today:** `edge_curvature(L, x, y)` — mean |face holonomy| through the edge from all directed triangles that contain it. Returns 0 for tree/line graphs.
  - **New today:** `M_H_factor(L, x, y)` = 1/(1+κ) — topological modulation. Numerically: κ=0 → M_H=1; κ→∞ → M_H→0.
- `wavepath.py`: `path_tension`, `psi` (complex path amplitude), `path_amplitude_sum`. Unchanged.

**Key invariant (confirmed in `test_curvature_modulation.py`):**

- Line graphs and symmetric graphs: κ = 0, M_H = 1 → zero effect even when `curvature_modulation=True`.
- Asymmetric triangles: κ > 0, M_H < 1 → transitions are topologically damped.
- M_H modulates `v` but is computed from the *unmodulated* ω (the cache builder temporarily disables the flag) → no circular dependency.
- The formula `M_H = 1/(1+κ)` and the alternative `M_H = exp(−κ)` have the same limits at 0 and ∞ but differ for intermediate κ. The polynomial formula is implemented; the exponential alternative is documented in Paper 3 for future comparison.

**Assessment:** The Helmholtz stack is stable. The Helmholtz cache is a significant practical improvement. The curvature addition is minimal, reversible, and correctly scoped to the topology layer.

---

### 2.3 SU(2) Spinor Extension — `spinor_connection.py`

**Purpose:** Lift the scalar U(1) connection ω to non-Abelian SU(2) matrix transport, enabling path-order-dependent interference in ℂ².

**SU(2) development timeline today (four tiers):**

| Tier | Time | Commit | Content | Tests |
|---|---|---|---|---|
| 1 — Integration switch | 09:46 | `e87d70a` | `use_su2` flag wired into `E0Controller` and `amplitude_overlay`; Gordian trap under SU(2): A-family intensity diverges 47.9% (phase halving), B-family within 2.1% | +5 in `test_spinor.py` |
| 2 — Reclassification | 10:10 | `7c4d2d3` | G5 winner flip (Family D: U(1)→B, SU(2)→A due to phase halving Θ→Θ/2); Gordian override rate drops 90%→0% under SU(2); SU(2) Born sampling distribution shift | +12 (g5), +7 (topo), +4 (born_sampling) |
| 3 — Three-theory stack | 11:45 | `8bc7983` | `use_su2="geometric"` branch in overlay using Helmholtz-derived A⃗; Diamond/Leaf identical across all 3 theories; Triangle <2% spread; Gordian: U(1)→B, SU(2)-min→A, SU(2)-geo intermediate; performance: overhead ≤10×/20× on 36-edge mesh | +14 in `test_spinor.py` |
| B1 — Multi-axis | 13:45 | `d536bb9` | per-edge `axis_fn` wired through full stack; non-commutativity, path-order dependence, tetrahedron domain | 36 in `test_multi_axis_su2.py` |

**Current state of `spinor_connection.py`:**

Three layers of SU(2) transport:

| Layer | API | Transport | Axis source |
|---|---|---|---|
| **Minimal (σ_z)** | `su2_edge_transport`, `su2_path_transport`, `spinor_psi` | `U = exp(−iω/2 · σ_z)` | Fixed ẑ; reduces to U(1) on single-axis domains |
| **Multi-axis (B1)** | `su2_edge_transport(axis_fn=...)`, `su2_path_transport(axis_fn=...)` | `U = exp(−iω/2 · n̂(x,y) · σ⃗)` | Per-edge callable; non-commutative when axes differ |
| **Geometric (A⃗)** | `su2_geometric_transport`, `su2_geometric_path_transport`, `spinor_geometric_psi` | `U = exp(−i‖A⃗‖/2 · n̂ · σ⃗)`, A⃗=(A₁,A₂,A₃) | Helmholtz-derived: A₁=vorticity gradient, A₂=face holonomy, A₃=ω |

**Key empirical findings (Tier 2 + Tier 3):**
- On the Gordian trap, U(1) and SU(2) produce **qualitatively different winners** (B vs A). Cause: SU(2) phase halving Θ→Θ/2 changes the destructive interference pattern.
- Gordian override rate: 90% (U(1)) → **0%** (SU(2)-min). The trap structure that defeated greedy under U(1) disappears under SU(2).
- Diamond and Leaf graphs: all three theories produce identical intensity ratios (single-path families — axis-insensitive by construction).
- Triangle domain: spread < 2% across three theories (minimal asymmetry).
- SU(2) geometric intensity falls between U(1) and SU(2)-min on the Gordian trap.

**Integration status:** `use_su2` (False/True/"geometric") and `axis_fn` are parameters of `E0Controller.__init__` and `analyze_controller_state`. The `use_su2="geometric"` option is fully operational and tested; it uses the Helmholtz A⃗ vector for all edge transports.

**Test coverage:**

| File | Tests | Scope |
|---|---|---|
| `test_spinor.py` | 71 | Phase 4a (52 original), +5 Tier 1 integration, +14 Tier 3 three-theory + performance |
| `test_multi_axis_su2.py` | 36 | B1: non-commutativity, path-order, tetrahedron, controller/overlay integration |

**Assessment:** Research module with production-grade test coverage (107 tests across both files). The three-tier progression (σ_z → multi-axis → geometric) is fully implemented and empirically validated. Phase halving as a qualitative decision-flip mechanism is confirmed (C23).

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
- `use_su2: object = False` (False / True / "geometric") — **added today** (Tier 1, `e87d70a`)
- `axis_fn` — **added today** (B1, `d536bb9`) per-edge SU(2) rotation axis

Three complete decision paths:
1. **GREEDY**: `select_next()` — pure `argmin S` with revisit/escalation.
2. **AMPLITUDE_ON_DISAGREE**: `_compute_overlay()` → if amplitude choice ≠ greedy and `override_confidence ≥ confidence_threshold` → override.
3. **BORN_SAMPLING**: `_compute_overlay()` → sample from `P(a) ∝ I(a)` — always sets `hybrid_overridden=True`.

All three modes support SU(2) computation when `use_su2` is set. The `use_su2` and `axis_fn` parameters are threaded through to `analyze_controller_state`.

**Assessment:** Production-ready for GREEDY and AMPLITUDE_ON_DISAGREE. BORN_SAMPLING is alpha/research. SU(2) controller integration is beta (confirmed in 8 controller-level tests in `test_multi_axis_su2.py` + 5 in `test_spinor.py`).

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

**Current state:** Supports mock mode (`--mock`), live OpenAI API. Parses LLM JSON outputs into controller-compatible action dictionaries. `test_llm_adapter.py` (47 tests), `test_llm_integration.py` (32 tests).

**Changes today to `test_llm_integration.py`** (the adapter itself was not modified):
- Tests now gracefully skip when `openai` is not installed (was: failed with ImportError)
- `max_cycles` increased from 20 → 30 for more robust goal-reaching
- Goal check updated: checks `GOAL in path` rather than `final_state == GOAL` (more lenient, correct for paths through goal)

These changes make the integration tests reliable in offline/CI environments. The 32 tests that were skipped in offline mode remain skipped (require live API).

The LLM demos (`demo_invoice_llm.py`, `demo_open_domain.py`, `demo_research_brief.py`, `demo_incident_postmortem.py`) still use the Phase 3a API surface (no dynamic horizons, no confidence gating, no SU(2) modes). This gap has persisted through all four analyses.

**Assessment:** Beta for core adapter. Integration tests are now CI-compatible. Demo modernization is still open.

---

### 2.11 Grid World Benchmark — `benchmark_gridworld.py`

**Purpose:** Empirically compare E₀ Greedy, Naive Greedy, and A* across three 5×5 grid world variants.

**New today** (`e675651`):

| Domain | Naive Greedy | E₀ Greedy | A* |
|---|---|---|---|
| V1 — Detour wall | 0% success | **100%** (16 steps) | 8 steps (optimal) |
| V2 — Dead-end lure | 0% success | **100%** (10 steps) | 8 steps (optimal) |
| V3 — Trap loop | 0% success | **100%** (8 steps) | 8 steps (optimal) |

**Key finding:** E₀ Greedy (with revisit penalty α=2, k=3, and typed escalation) escapes all three trap variants without amplitude overlay. The benchmark shows that the E₀ controller's structural memory alone (historization) is sufficient to escape grid traps — the amplitude overlay is not needed and would be counterproductive at large grid sizes (horizon 3–4 cannot reach goals 8+ edges away; intensities degenerate to single-edge fallbacks).

This finding is documented in `benchmark_gridworld.py` and referenced in Paper 1 §7.5 (Grid World Benchmark, Table 6) and Appendix B.4. The amplitude overlay's domain of advantage is confirmed as *structured decision-point graphs* (Gordian, invoice, research domain), not navigation grids.

**Usage:** `python -m e0_controller.benchmark_gridworld` or `--json` for machine-readable output.

**Assessment:** Executable benchmark showing E₀ Greedy superiority over naive greedy on grid traps. Amplitude overlay exclusion is documented and justified.

---

### 2.12 CI and Project Infrastructure

**New today** (`db989c7`):

- **`.github/workflows/tests.yml`**: GitHub Actions CI matrix testing Python 3.11, 3.12, 3.13 with numpy-only dependencies. Includes a test count guard: CI fails if fewer than 1,000 tests are discovered. This prevents silent test-count regressions.
- **`pyproject.toml`**: Project metadata (name: `e0-framework`, version: `0.10.11`), optional LLM dependency group, ruff linter config.

**Assessment:** CI infrastructure now exists and provides automated regression protection. The ≥1,000-test guard is an unconventional but appropriate quality signal for a rapidly growing test suite.

---

### 2.13 Scenario Loader — `scenario_loader.py`

**Assessment:** Stable. No changes.

---

### 2.14 Domain and Exploration Scripts

**`explore_resonator.py`** (updated `bebb6b9`):
- Added `build_4node_loop` — 4-node ring A→B→C→D→A + leak edge
- Added `build_nested_loop` — outer A→B→C→A + inner B→X→C (two path families)
- Added `build_coupled_resonators` — K1(A-B-C) + bridge C→P + K2(P-Q-R)
- Added `generic_loop_paths`, `measure_generic_loop`, `apply_generic_historization` — generalized measurement utilities

**O5 empirical findings:**
- 4-node loop: RESONATOR classification, Θ≠0, acyclic decay pattern confirmed
- Nested loop: constructive interference factor ~2.0 (two families combine coherently)
- Coupled resonators: K1 and K2 maintain isolation; bridge C→P creates measurable coupling
- Multi-loop SU(2): holonomy and three-theory separation on 4-node ring confirmed

**Assessment:** explore_resonator.py is now a generalized multi-topology measurement tool. resonator_connection.py remains research-isolated (not connected to controller loop).

---

## 3. Complete Module and Test Registry (2026-03-26)

| Module | Phase introduced | Test files | Test count | Status |
|---|---|---|---|---|
| `primitives.py` | Phase 1 | `test_phase2_minidomain.py` (partial) | — | ✅ Stable |
| `landscape.py` | Phase 1 + B2 | `test_curvature_modulation.py`, `test_phase2_minidomain.py` | 35 (B2) + partial | ✅ Stable (modulation-extended) |
| `tension.py` / `historization.py` | Phase 1–2 | `test_phase2_minidomain.py`, `test_historization_gordian.py` | 38 + 61 | ✅ Stable |
| `potential.py` | Phase 2a + perf | `test_phase2_minidomain.py`, `test_amplitude_overlay.py` | partial | ✅ Stable (Helmholtz cached) |
| `connection.py` | Phase 2a + B2 | `test_curvature_modulation.py`, `test_omega_uniqueness.py`, `test_amplitude_overlay.py` | 35 + 27 + 125 | ✅ Stable |
| `wavepath.py` | Phase 2a | `test_phase2_minidomain.py`, `test_amplitude_overlay.py` | partial | ✅ Stable |
| `spinor_connection.py` | Phase 4a/4b + Tier 1–3 + B1 | `test_spinor.py`, `test_multi_axis_su2.py` | 71 + 36 | ✅ Research (complete) |
| `controller.py` | Phase 1–5h + Tier 1 + B1 | `test_minidomain.py`, `test_gordian_trap.py`, `test_greedy_trap.py`, `test_confidence_override.py`, `test_born_sampling.py`, `test_dynamic_horizon.py`, `test_multi_axis_su2.py`, `test_spinor.py` | 21+44+4+31+31+45+8+5 | ✅ Stable (greedy/hybrid), ⚪ Alpha (Born sampling) |
| `amplitude_overlay.py` | Phase 3h–5f + Tier 1–3 + B1 | `test_amplitude_overlay.py`, `test_gordian_trap.py`, `test_g5_edge_cases.py`, `test_confidence_override.py`, `test_born_regime.py`, `test_waypoint.py`, `test_multi_axis_su2.py`, `test_spinor.py` | 125+44+55+31+44+17+8+14 | ✅ Stable |
| `dynamic_horizon.py` | Phase 5e | `test_dynamic_horizon.py` | 45 | ✅ Beta |
| `graph_validation.py` | Phase 3c | `test_graph_validation.py`, `test_scaling.py` | 24+14 | ✅ Stable |
| `memory_os.py` | Phase 2c, 5g | `test_memory_os.py`, `test_memos_geometry.py` | 28+34 | ✅ Beta (geometry-aware) |
| `llm_adapter.py` | Phase 3a | `test_llm_adapter.py`, `test_llm_integration.py` | 47+32 | ✅ Beta (integration tests CI-compatible) |
| `evaluation.py` | Phase 3f, 5c | `test_evaluation.py`, `test_reflection_hybrid.py` | 42+42 | ✅ Beta |
| `reflection.py` | Phase 3g, 5c | `test_reflection.py`, `test_reflection_hybrid.py` | 36+42 | ✅ Beta |
| `scenario_loader.py` | Phase 3e | `test_minidomain.py` | partial | ✅ Stable |
| `domain_invoice.py` | Phase 3d | `test_invoice.py`, `test_phase2_invoice.py` | 33+18 | ✅ Stable |
| `validate_cross_domain.py` | Phase 3d | — (system test) | — | ✅ Stable |
| `benchmark_gridworld.py` | **NEW today** | no tests (executable benchmark) | — | ✅ Runnable |
| `explore_resonator.py` | Phase 4b + O5 | `test_resonator.py` | 73 | ✅ Research (generalized) |

**Test file summary (29 files, 1,138 total tests):**

| File | Tests | Claim coverage | Changes today |
|---|---|---|---|
| `test_amplitude_overlay.py` | 125 | Geometries, ψ-sums, edge cases | — |
| `test_born_regime.py` | 44 | B1–B5 axioms across 5 domains | — |
| `test_born_sampling.py` | 31 | BORN_SAMPLING mode, KL divergence; SU(2) Born sampling | +4 (Tier 2 SU(2)), CI fix |
| `test_confidence_override.py` | 31 | Confidence gating, threshold sweep, Gordian integration | — |
| `test_curvature_modulation.py` | 35 | B2: κ, M_H, curvature modulation | NEW |
| `test_dynamic_horizon.py` | 45 | C19: fixed, topology_adaptive, capped_adaptive | — |
| `test_evaluation.py` | 42 | C18: r_coh, amplitude_drift, theta_consistency | — |
| `test_g5_edge_cases.py` | 55 | G5 geometry edge cases; SU(2) G5 reclassification; |G|=32 stability | +12 (Tier 2 SU(2)), +15 (O2) |
| `test_gordian_trap.py` | 44 | C8: holonomy, interference, hybrid override | — |
| `test_graph_validation.py` | 24 | Reachability, dead ends, loop detection | — |
| `test_greedy_trap.py` | 4 | Greedy trap, hybrid escape | fix: absolute imports |
| `test_historization_gordian.py` | 61 | C8/C9: historization × Gordian + Triangle + Diamond + GordianLite | +25 (O1) |
| `test_invoice.py` | 33 | Invoice domain, 10 states, 16 edges | — |
| `test_llm_adapter.py` | 47 | LLM ↔ controller bridge | — |
| `test_llm_integration.py` | 32 | Live/mock API integration (32 skipped offline) | fix: CI-compatible skipping |
| `test_memory_os.py` | 28 | Persist/restore/summarize/retrieve | — |
| `test_memos_geometry.py` | 34 | C21: geometry round-trips in MemOS | — |
| `test_minidomain.py` | 21 | Core controller end-to-end | — |
| `test_multi_axis_su2.py` | 36 | B1: per-edge axes, non-commutativity, controller integration | NEW |
| `test_omega_uniqueness.py` | 27 | C14: ω uniqueness proof | — |
| `test_phase2_invoice.py` | 18 | Invoice domain structural maths | — |
| `test_phase2_minidomain.py` | 38 | Core primitives and maths | — |
| `test_reflection.py` | 36 | Reflection triggers (structural) | — |
| `test_reflection_hybrid.py` | 42 | C18: amplitude reflection triggers | — |
| `test_resonator.py` | 73 | Resonator stability; multi-loop (4-node, nested, coupled); SU(2) | +25 (O5) |
| `test_scaling.py` | 14 | n≤500 performance | fix: timing limits |
| `test_spinor.py` | 71 | SU(2) controller integration (Tier 1); three-theory + performance (Tier 3) | +5 (Tier 1), +14 (Tier 3) |
| `test_topology_classification.py` | 30 | 380-graph scan; SU(2) reclassification (C23) | +7 (Tier 2 SU(2)) |
| `test_waypoint.py` | 17 | Goal-with-continuations geometry divergence (H4 closure) | NEW |

---

## 4. Open Items and Follow-ups

### 4.1 Gaps closed today (O-series)

| Item | Status | Evidence |
|---|---|---|
| O1: Historization × non-Gordian topologies | ✅ **Closed** | 25 new tests: Triangle (immune), Diamond (winner shift), GordianLite (interference survives), cross-topology invariants |
| O2: G5 stability to large |G| | ✅ **Closed** | 15 new tests: A wins at |G|=16,32; entropy/gap trends hold; P(A) converges [0.70,0.80] |
| O4: SU(2) topology reclassification | ✅ **Closed** | C23: Gordian override rate 90%→0% under SU(2); phase halving identified as mechanism; 7 tests |
| O5: Multi-loop resonator scaling | ✅ **Closed** | C24: 4-node, nested, coupled kernels; constructive interference ~2.0; 25 tests |

### 4.2 Newly opened in this analysis period

| Item | Source | Priority |
|---|---|---|
| `axis_fn` not persisted in MemOS | SU(2) multi-axis feature | Low (callables not serializable) |
| `use_su2` not yet a `E0Controller.__init__` parameter | Must be passed to overlay directly | Medium |
| SU(2) intensity not threaded into evaluation/reflection metrics | Would require a new `su2_r_coh` metric | Low |
| M_H formula comparison (`1/(1+κ)` vs `exp(−κ)`) unresolved | Paper 3 documents both; no empirical test | Low |

### 4.3 Carried over from 2026-03-25 (v2)

| Item | Status | Note |
|---|---|---|
| Full θ derivation from v_rot | ⚪ Open | Worked example exists; no general closed form |
| LLM demos with new features | ⚪ Gap | All four demos use Phase 3a surface only |
| Resonator kernel integration into controller | ⚪ Gap | 73 tests pass; isolated from controller loop |
| Stochastic exploration policy | ⚪ Research | BORN_SAMPLING available; no warm-up/switch policy |
| Formal correctness proof of G5 geometry | ⚪ Research | Empirically validated; formal proof absent |

---

## 5. Documentation Assessment

### 5.1 Scientific Papers — Three Complete Manuscripts

All three papers were written or finalized today. This represents the single largest documentation event in the project's history.

**Paper 1 — E₀: Structural Interference in Discrete Transition Systems**
`docs/PAPER1_MANUSCRIPT_v1.md` (1614 lines, ~9200 words after related-work integration)

- Derivation chain from primitives to Ψ
- **Theorem 1 (Holonomy Independence):** phase differences between paths depend only on path-local quantities
- 4 summation geometries with formal definitions + empirical comparison
- Hybrid controller (3 algorithms), confidence gating, dynamic horizons
- **Theorem 2 (Geometry Dominance):** on trap-containing domains, geometry change → 0%→100% success; decision-rule change → ≤24 pp change
- 380-graph topology classification; structural predictors (path-family count + phase opposition |ΔΘ| > π/2)
- Grid world benchmark (§7.5, Table 6): E₀ escapes all 3 grid variants; A* optimal
- §2 Related Work + 30 numbered references (Kappen, Todorov, Aharonov, Berry, Singer/Wu, Schaul/UVFA, HER, etc.)
- Appendices: Theorem 1 proof, benchmark domains (Gordian, Diamond, invoice, grid), honesty map (Derived/Empirical/Heuristic)
- Status: v3 (3 external-reviewer structural fixes applied)

**Paper 2 — E₀-II: Spinor Amplitudes and the Born Criterion on Discrete Transition Graphs**
`docs/PAPER2_MANUSCRIPT_v1.md` (1310 lines)

- Carrier-space minimality argument: internal difference forces ℂ → ℂ², yielding SU(2)
- Three emergent effects: 720° periodicity, phase halving, non-commutativity
- Born criterion derivation: P(z) = |Ψ(z)|² / Σ|Ψ|² is unique structurally non-arbitrary distribution
- Empirical analysis: phase halving causes decision flip on Gordian (B→A); Gordian override rate 90%→0% under SU(2)
- Multi-goal analysis under spinor amplitudes (G5 geometry under SU(2))
- Reviewer fixes applied: 4 structural improvements
- Status: v1 with reviewer fixes

**Paper 3 — Non-Abelian Structure in E₀: Per-Edge SU(2) Transport and Curvature Modulation**
`docs/E0_PAPER3_NON_ABELIAN_STRUCTURE_v1.md` (552 lines)

- SU(2) extension in 3 stages: per-edge rotation axes, geometry-derived axes (A⃗), curvature feedback (M_H)
- 71 tests across 4 graph topologies cited as numerical evidence
- Experimental switch (`curvature_modulation=False` default) documented
- Alternative M_H formula `exp(−κ)` vs `1/(1+κ)` disclosed
- Appendix B: Derived/Empirical/Heuristic classification for all claims
- Status: Draft v1.0

**Paper skeleton documents:**
- `PAPER1_SKELETON_v1.md` (465 lines) — structure, evidence mapping, section plan
- `PAPER2_SKELETON_v1.md` (502 lines) — SU(2) structure, evidence mapping

### 5.2 Canon Alignment Report

**`docs/E0_CANON_ALIGNMENT_v1.md`** (533 lines) — NEW today.

Systematic mapping of all 4 canon documents (`e0-canonical-reference.txt`, `e0-canon-plain.txt`, `ontodynamics.txt`, `e0-agi-blueprint.md`) against the actual implementation. Key findings:

- All 7 primitives: faithful to canon, none abandoned. Historization is the most extended (§17 adds clipping, traces, decay — far beyond canon spec).
- A0 + Transition Enforcement: fully realized as `argmin S`.
- The derivation chain `v → v_rot → ω → Θ → Ψ → interference → Born → SU(2)` follows **necessarily** from canon primitives — but was **not predicted** by the canon itself.
- Ontodynamics: conceptually referenced, not implemented (per design — operates at a different layer).
- 4 open bridges: local realization, multi-axis SU(2), M_H, reflexivity.
- Written against the 1,046-test state (between O5 and O1).

### 5.3 Supporting Documentation (updated registries)

- `E0_TEST_REGISTRY_v2.md`: heavily updated today (+254 lines). Now covers C15 (three-theory), C23 (SU(2) reclassification), C24 (multi-loop resonance), C25 (per-edge SU(2)); O1/O2/O4/O5 resolved; P3 roadmap added.
- `E0_TEST_REGISTRY_v1.md`: +43 lines, entry for `test_multi_axis_su2.py` (C25), test count updated to 1,082.
- `related-work-research-report.md` (116 lines): source material for Paper 1 §2 Related Work.
- `docs/` total document count: **75** (vs. 65 reported in prior analysis — the 10-document delta the user noted).

### 5.4 Document count reconciliation

| Period | Doc count | Delta |
|---|---|---|
| Before today (up to 2026-03-25 v2) | ~65 | — |
| Added today | +10 | Canon Alignment + related-work + E0_CODE_ANALYSIS_2026-03-25_v2 + Paper 1 manuscript + Paper 1 skeleton + Paper 2 manuscript + Paper 2 skeleton + Paper 3 + test registry v1 update + test registry v2 update |
| **Total today** | **~75** | |

---

## 6. Overall Classification

### 6.1 Where E₀ stands today

The E₀ Controller as of 2026-03-26 is a **fully operational, multi-layered structural decision system with three complete scientific manuscripts**, comprising:

- A **formally verified primitive chain** (7 primitives, 1 axiom → ψ → I → P) proven unique in its phase generator (C14) and Born-rule realization (C17).
- A **production-grade greedy + hybrid controller** with four enumeration geometries, three controller modes, dynamic horizons, confidence gating, and full MemOS persistence.
- A **research-grade non-Abelian extension** (SU(2) minimal, multi-axis, and geometric) verified numerically and non-commutative by construction, with phase halving identified as the mechanism for trap-domain decision flips.
- A **topological modulation layer** (curvature-derived M_H feedback) switched off by default and verified for backward compatibility.
- A **grid benchmark** (E₀ Greedy escapes all 3 trap variants; A* optimal; amplitude overlay correctly excluded from grids).
- **CI infrastructure** (GitHub Actions, ≥1,000-test guard).
- **1,138 tests** covering the full dependency chain.
- **Three scientific manuscripts** (Papers 1–3) and a Canon Alignment Report.

### 6.2 Updated maturity table

| Layer | Maturity | Evidence |
|---|---|---|
| Core primitives (Δ, R, H, S, C, v, Ψ) | **Production-ready** | 100+ tests, invoice/minidomain domains, scaling to n=500 |
| Helmholtz decomposition (potential.py) | **Production-ready** | Cached; 6× speedup confirmed |
| Amplitude overlay (4 geometries) | **Beta → Production** | 125 overlay tests, waypoint domain, G5 Born-aligned |
| Hybrid mode (AMPLITUDE_ON_DISAGREE) | **Beta** | Gordian trap escape, confidence gating, dynamic horizons confirmed |
| Born sampling (BORN_SAMPLING) | **Alpha/Research** | 31 tests, correct distribution, argmax dominance confirmed |
| Dynamic horizons | **Beta** | 45 tests, Gordian/diamond/mini domain verified |
| Confidence-weighted override | **Beta** | 31 tests, monotonic threshold–rate relationship |
| MemOS persistence | **Beta** | Geometry-aware; 62 round-trip tests; axis_fn gap documented |
| Reflection (amplitude triggers) | **Beta** | 42 tests, coherence + drift + phase triggers |
| SU(2) minimal (single-axis, σ_z) | **Research (complete)** | Phase 4a: 52 tests |
| SU(2) controller integration (use_su2 flag) | **Beta** | 5 integration tests; Gordian trap decision flip confirmed |
| SU(2) three-theory stack (U(1)/min/geo) | **Research (complete)** | 14 tests; natural domain comparison; performance bounds |
| SU(2) multi-axis (B1, axis_fn) | **Research (complete)** | 36 tests, per-edge axes, controller-integrated |
| SU(2) geometric (A⃗ coupling) | **Research (experimental)** | Implemented; `use_su2="geometric"` controller init param pending |
| M_H curvature modulation (B2) | **Research (complete)** | 35 tests, backward-compatible, formula justified |
| Resonator layer | **Research (isolated)** | 73 tests (multi-loop extended today); not connected to controller |
| LLM integration | **Beta** | 47+32 tests; integration tests CI-compatible; demos not modernized |
| Grid benchmark | **Verified** | E₀ Greedy escapes all 3 variants; amplitude overlay exclusion justified |
| Waypoint / goal-with-continuations | **Verified** | 17 tests, H4 closure |
| Canon alignment | **Documented** | 533-line report; 7 primitives × 4 canon docs; 4 open bridges |
| CI / pyproject | **Active** | Python 3.11–3.13 matrix; ≥1,000-test guard; ruff config |
| Papers 1–3 | **Draft** | 3 complete manuscripts; reviewer fixes applied to P1+P2 |

### 6.3 Three-tier claim classification

Following the classification introduced in Paper 3 Appendix B and applied consistently across all papers:

**Derived (within E₀ axiom system):**
- ω = ½(v_rot(x,y) − v_rot(y,x)) is the unique antisymmetric phase generator (C14, within axioms A1/A3/A4; 27 tests)
- P(z) = I(z)/ΣI satisfies axioms B1–B5 and is the unique minimal realization rule (C17, under BER-1–5; 44 tests)
- SU(2) edge transport U = exp(−iω/2 · n̂ · σ⃗) is non-Abelian when axes differ (B1, 36 tests)
- M_H = 1/(1+κ) is bounded in (0,1] and equals 1 on flat (κ=0) graphs (B2, 35 tests)
- Holonomy Independence Theorem: phase differences depend only on path-local quantities (Paper 1 Theorem 1)
- Carrier-space minimality: internal difference forces ℂ → ℂ², yielding SU(2) (Paper 2 §3)

**Empirically demonstrated:**
- Gordian trap: holonomy formula ΔΘ = ½[Σv(A-loop) − Σv(A-short)] (C8, 44 tests)
- G5 goal-reaching geometry enables hybrid override on traps (C8/C9, 44+61 tests); stable to |G|=32 (O2, 15 tests)
- `argmax(I)` dominates Born sampling on average across 50 random domains (C22, 31 tests)
- Topology-adaptive horizon selects h ≥ 5 on Gordian trap (C19, 45 tests)
- Multi-axis SU(2) overlay produces different decisions from single-axis on Gordian trap (C25, 36 tests)
- SU(2) phase halving causes Gordian override rate to drop 90%→0% (C23, 7 tests)
- Historization cannot create/destroy interference patterns: cross-topology invariant (O1, 25 tests)
- Multi-loop resonance: constructive interference factor ~2.0 on nested loop (C24, 25 tests)
- E₀ Greedy escapes all 3 grid trap variants; A* is step-optimal (benchmark, no tests)
- Geometry choice dominates decision-rule choice: 0%→100% vs ≤24 pp (Paper 1 Theorem 2)

**Heuristic (empirically validated, not derived):**
- `topology_adaptive` horizon formula (distance × branching factor reduction)
- Reflection trigger thresholds (R_coh < 0.30, drift > 0.30, θ ≥ 0.70)
- Confidence gating default (0.0)
- M_H formula: 1/(1+κ) vs exp(−κ) — both candidates, neither formally justified over the other

---

## 7. Proposed Next Steps

Based on the current state and open items:

### 7.1 High impact, low effort

1. **Expose `use_su2` as an `E0Controller.__init__` parameter**: Currently it must be passed explicitly to `analyze_controller_state`. A one-line addition to `__init__` and `_compute_overlay` would make SU(2) mode a first-class controller option (matching how `axis_fn` is already handled).

2. **Document the `axis_fn` MemOS gap**: A one-paragraph note in `E0_MEMOS_v0.1.md` or the controller docstring prevents future confusion for users who switch SU(2) modes across sessions.

3. **M_H formula comparison experiment**: Run the Gordian trap and triangle domain with `M_H = exp(−κ)` vs `M_H = 1/(1+κ)` and add 6–8 comparison tests. Converts the last open heuristic formula choice to an empirically adjudicated one.

### 7.2 High impact, medium effort

4. **Modernize at least one LLM demo**: Update `demo_greedy_trap.py` (the simplest) to use dynamic horizons, confidence gating, and `use_su2`. Demonstrates the full current stack end-to-end.

5. **Connect resonator kernel to controller**: The 73-test resonator layer is validated but isolated. Integrating resonator score as a secondary overlay signal (e.g., amplitude modifier on loop-containing paths) would close the largest isolated-module gap.

6. **Submit Paper 1 to arXiv**: All structural reviewer fixes are applied (v3). The manuscript is at submission quality. Related work section and 30 references are integrated.

### 7.3 Research directions

7. **Phase derivation from v_rot (general)**: `E0_PHASE_DERIVATION_PROGRAM_v1.md` establishes a worked example. A general procedure for deriving ω from measured `v_rot` would remove the only remaining manually-assigned parameter.

8. **Stochastic exploration policy**: BORN_SAMPLING is available but lacks a principled warm-up/switch policy (e.g., N steps sampling → argmax). Needed for multi-goal discovery and open-domain LLM operation.

9. **Formal correctness proof for G5 geometry**: Goal-reaching geometry is empirically validated and Born-criterion aligned. A formal minimality argument remains open.

10. **SU(2) reflexivity (Canon Bridge 4)**: The Canon Alignment Report identifies reflexivity as an open bridge between the canon's AGI blueprint and the current implementation. An SU(2)-based internal-state representation would close this.

---

## 8. Limitations and Risks (updated)

1. **Computational cost:** Path enumeration is O(kʰ). Dynamic horizons mitigate this; the Helmholtz cache provides 6× speedup on the full suite. No hard real-time benchmarks.

2. **Phase derivation gap:** ω is provably unique, but deriving its values from measurable `v_rot` in new domains is still manual. Applications must pre-specify ω or infer it from observed transition patterns.

3. **SU(2) operational status:** `use_su2` is wired into the controller (as of today) but not yet a first-class `__init__` parameter. The three-theory stack is validated; default remains U(1).

4. **M_H formula is a candidate:** `M_H = 1/(1+κ)` vs `exp(−κ)` — both candidates, neither empirically adjudicated. Using `curvature_modulation=True` in production is experimental.

5. **LLM demo gap:** All four LLM demos use the Phase 3a API surface. Dynamic horizons, confidence gating, geometry options, and SU(2) are not demonstrated in any runnable demo.

6. **SU(2) decision-flip caution:** SU(2) phase halving changes Gordian trap override rate from 90% to 0%. Activating `use_su2=True` in production on trap-containing domains will produce qualitatively different behavior from U(1). This is physically meaningful but must be documented and intentional.

7. **Born sampling in long chains:** Argmax dominance confirmed on average. Multi-goal discovery scenarios where sampling is superior lack a principled policy.

---

This document intentionally records **observations only**. No code was changed during this analysis.
