# E₀ Runtime Code Analysis — 2026‑03‑25

**Status:** Read-only review (no code changes)  
**Purpose:** Update the 2026-03-24 analysis to reflect the substantial additions made in the past ~24 hours.  
**Scope:** New geometries, Gordian trap, SU(2) spinor layer, topology classification, G5 edge-case suite, multigoal formalization, waypoint domain, scaling tests, and resolved follow-up items from the previous analysis.

---

## 1. What changed since 2026-03-24

The table below maps the open follow-up items from the previous analysis to their current status.

| Follow-up (2026-03-24) | Status today |
|---|---|
| Geometry selection hardcoded in `_compute_overlay`, no config switch | ✅ **Resolved** — `hybrid_geometry` param added to `E0Controller.__init__` |
| No G5 goal-reaching geometry implemented | ✅ **Resolved** — `"goal_reaching"` added as 4th geometry in `amplitude_overlay.py` |
| Reflection layer ignores hybrid metrics | ⚪ Open (no change) |
| Automated trap benchmarks / geometry stress tests not coded | ✅ **Largely resolved** — Gordian trap, topology classification, G5 suite, scaling tests added |
| MemOS geometry field missing | ⚪ Open (no change) |
| No regression tests for phase perturbations | ✅ **Partially resolved** — Holonomy + phase tests in `test_gordian_trap.py` and `test_topology_classification.py` |
| Per-domain horizons / dynamic horizon hooks | ⚪ Open (no change) |

**Test count:** ~148 → **613 (581 passed, 32 skipped)** in 17 s — a 4× increase.

---

## 2. New Fourth Geometry: `goal_reaching` (G5)

**Files:** `e0_controller/amplitude_overlay.py`, `docs/E0_G5_MULTIGOAL_FORMALIZATION_v1.md`

Key properties:
- Only paths whose terminal state is in `goals` contribute to the amplitude sum.
- Intermediate non-goal paths are excluded entirely (contrast with `first_arrival`, which includes non-goal prefixes).
- Aligned with the Born criterion: only "complete" realizations (paths that actually reach a goal) contribute to interference.
- Requires a non-empty `goals` set; raises `ValueError` otherwise.
- Multi-goal extension: `goals = {g1, g2, ...}` — all goal-reaching paths summed into a single composite amplitude per action.

The `analyze_controller_state` and `_enumerate_continuations` functions are unchanged in signature; `geometry="goal_reaching"` is now a valid argument alongside the three geometries from Phase 3h.

`HybridMode.AMPLITUDE_ON_DISAGREE` can now use G5 end-to-end by setting `hybrid_geometry="goal_reaching"` on the controller — closing the config-switch gap identified on 2026-03-24.

---

## 3. Gordian Trap Domain

**Files:** `e0_controller/explore_gordian.py`, `e0_controller/test_gordian_trap.py`,
`e0_controller/explore_historization_gordian.py`, `docs/E0_GORDIAN_TRAP_DESIGN_v1.md`

The Gordian Trap is the first purpose-built landscape where greedy selection is structurally wrong due to destructive interference, not due to a greedy horizon limitation.

### Topology

```
START → A1 → A2 → GOAL          (A-short: low δ → small Θ)
START → A1 → L1 → L2 → L3 → GOAL  (A-loop: high δ → large Θ)
START → B1 → B2 → GOAL          (Detour B: coherent, no phase split)
```

Greedy picks `A1` (cheapest first step). Within the A-family, A-short and A-loop accumulate phases near π apart, producing destructive interference. B remains coherent.

### Holonomy formula (key insight)

```
ΔΘ = ½ · [Σ v(A-loop edges) − Σ v(A-short edges)]
```

Back-edges are irrelevant: Φ cancels in the holonomy. This makes Gordian trap topology minimally designable.

### Test hierarchy (5 tests in `test_gordian_trap.py`)
1. Holonomy formula matches analytical prediction
2. A-family destructive interference factor < 0.1
3. G5 overlay picks `B1` at h ≥ 5
4. Hybrid controller overrides greedy `A1 → B1`
5. Both greedy and hybrid reach GOAL (reachability sanity)

### Historization stability (`explore_historization_gordian.py`)
Exploration (not formal test) shows ΔΘ is preserved under multi-pass historization: `cos(ΔΘ) < −0.9` survives both B-path traversals and greedy A-traversals in tested scenarios.

---

## 4. Greedy Trap Walkthrough Demo

**Files:** `e0_controller/demo_greedy_trap.py`, `e0_controller/test_greedy_trap.py`

A simpler, README-level demonstration:

```
A → C → A   (cheap loop)
A → B → E → G → GOAL  (slightly costlier first hop, but forward)
```

- Greedy: bounces in A↔C loop, never reaches GOAL in 10 cycles.
- Hybrid (h=4, `goal_reaching`, goals={"GOAL"}): overrides A→C with A→B at step 1, reaches GOAL in exactly 4 steps.

Three formal tests confirm: (1) greedy trapped, (2) hybrid reaches GOAL, (3) override fires at step 1.

---

## 5. Topology Scan & Classification Tests

**Files:** `e0_controller/explore_topology_scan.py`, `e0_controller/test_topology_classification.py`

### Topology scan tool
`explore_topology_scan.py` generates random directed graphs and classifies which structural features produce G5 override decisions. Key findings encoded as tests:

1. **Triangle topology** (single action family, all via one intermediate): G5 NEVER overrides — single family means no competing phase branches.
2. **Diamond topology** (two independent families to goal): CAN override — produces ≥2 families, enabling phase competition.
3. **Gordian-lite topology** (diamond + designed phase split): high override rate.
4. **G5 is unique**: `prefix ≡ first_arrival` (both include non-goal prefixes); `simple ≈ prefix` (differences < 3%). G5 is qualitatively distinct.
5. **Override requires ≥2 path families** from START — single-family graphs are immune.
6. **Phase opposition is the strongest predictor** of override occurrence.
7. **Geometry stress**: prefix/simple/first_arrival agree ≥ 97% — confirming the geometry-invariance claim from Phase 3h.

---

## 6. G5 Edge-Case Suite (Families A–E)

**Files:** `e0_controller/explore_g5_edge_cases.py`, `e0_controller/test_g5_edge_cases.py`,
`docs/E0_G5_EDGE_CASE_SUITE_v1.md`

Five test families covering G5 robustness under adversarial goal sets:

| Family | Question | Key result |
|---|---|---|
| A — Goal-count growth | Winner stability as \|G\| increases | Winner stable for small growth; dilution at large \|G\| |
| B — Irrelevant-goal injection | Unreachable / weak goals distort ordering? | Unreachable goals safe; reachable-but-weak goals shift probabilities |
| C — Competing-goal conflict | Different goals favor different actions | Generalist action (reaches multiple goals) wins |
| D — Rescue threshold | Minimum strength to rescue a suppressed action | Low-δ path sufficient if coherent to alternative goal |
| E — Ranking sharpness | Entropy / top-gap as \|G\| grows | Selectivity preserved: entropy ↓, gap ↑ as goals increase |

---

## 7. Multigoal Formalization

**Files:** `e0_controller/explore_multigoal.py`, `docs/E0_G5_MULTIGOAL_FORMALIZATION_v1.md`

Multi-goal G5 is formally defined as:

```
Ψ(a, G) = Σ_{g ∈ G} Σ_{p ∈ Paths_g(a)} Ψ(p)
I(a, G) = |Ψ(a, G)|²
a* = argmax_a I(a, G)
```

`analyze_controller_state(..., goals={g1, g2, ...})` already implements this by summing all goal-reaching paths across all goals in the set. No new API is needed; the implementation generalizes correctly.

---

## 8. Waypoint Domain (Phase 3p, Closes H4)

**Files:** `e0_controller/test_waypoint.py`

The waypoint domain has a goal state `G` with outgoing edges (non-terminal goal).  
This is the decisive test for `first_arrival` vs `prefix`:

- `prefix`: follows post-goal loop `G → Y1 → G`, inflating path counts.
- `first_arrival`: stops at `G`, immune to post-goal inflation.
- `simple`: allows `G → Y1 → Y2 → ...` but not `G → Y1 → G` (revisit filter).

The geometry-divergence claim from `E0_SUMMATION_GEOMETRY_COMPARISON_v1.md` (hypothesis H4) is now confirmed with a formal test.

---

## 9. SU(2) Spinor Layer (Phase 4)

**Files:** `e0_controller/spinor_connection.py`, `e0_controller/test_spinor.py`,
`docs/E0_SPINOR_EXPLORATION_v0.md`, `docs/E0_INTERNAL_DIFFERENCE_TO_SPINOR_BRIDGE_v0.md`

The SU(2) extension lifts the scalar U(1) connection ω to 2×2 SU(2) matrix transport:

```
U(x,y) = exp(−i · ω(x,y) / 2 · n̂ · σ⃗)   ∈ SU(2)
Ψ_spinor(p) = exp(−S(p)) · U(p) · |ref⟩     ∈ ℂ²
I_spinor     = ‖Σ_p Ψ_spinor(p)‖²
```

Seven findings verified in `test_spinor.py`:

| # | Finding |
|---|---|
| F1 | SU(2) primitives correct (Pauli algebra, det=1, unitarity) |
| F2 | Single-path magnitudes match U(1) — no spurious intensity change |
| F3 | Phase halving Θ → Θ/2 alters interference patterns (double cover) |
| F4 | 720° periodicity: exp(−iπσ) = −𝕀, exp(−i2πσ) = +𝕀 (algebraic) |
| F5 | Non-commutativity: multi-axis SU(2) produces [σᵢ, σⱼ] ≠ 0 |
| F6 | All transport matrices are valid SU(2) members |
| F7 | Holonomy is well-defined on graph loops |

**Status:** Phase 4 research module — NOT integrated into controller decisions. The U(1) layer remains the operational foundation. The current implementation uses the minimal single-axis embedding (n̂ = ẑ = σ_z), which reduces exactly to U(1). Multi-axis SU(2) is possible via the optional `axis_fn` argument in `su2_path_transport` / `spinor_psi`, but no graph domain with multiple independent loop orientations has been designed yet.

---

## 10. Graph Validation Extension

**File:** `e0_controller/graph_validation.py`

`graph_quality_multigoal(L, start, goals)` added alongside the existing single-goal `graph_quality()`:
- Finds the closest reachable goal for happy-path analysis.
- Checks reachability to ALL goals.
- Excludes all goals (not just one) from trap detection.

---

## 11. Scaling Tests (Phase 3q)

**File:** `e0_controller/test_scaling.py`

Formal tests at n = 50 / 100 / 500 states:
- Landscape construction < 1 s at n = 500.
- Greedy run (full chain) completes in time.
- `analyze_controller_state` with `horizon_edges=3` completes < 2 s at n = 500.
- Path count behavior is bounded (no exponential blow-up with small horizon).

---

## 12. Updated Module & Test Map

| Module | Phase | Tests | Status |
|---|---|---|---|
| `primitives.py` | Phase 1 | `test_phase2_minidomain.py` (partial) | ✅ Stable |
| `landscape.py` | Phase 1 | `test_phase2_minidomain.py`, `test_phase2_invoice.py` | ✅ Stable |
| `tension.py` / `historization.py` | Phase 1–2 | `test_phase2_minidomain.py` | ✅ Stable |
| `potential.py` / `connection.py` / `wavepath.py` | Phase 2a | `test_phase2_minidomain.py`, `test_amplitude_overlay.py` | ✅ Stable |
| `controller.py` | Phase 1–3l | `test_minidomain.py`, `test_phase2_minidomain.py`, `test_gordian_trap.py`, `test_greedy_trap.py`, `test_topology_classification.py` | ✅ Stable |
| `amplitude_overlay.py` | Phase 3h–3q | `test_amplitude_overlay.py`, `test_gordian_trap.py`, `test_topology_classification.py`, `test_g5_edge_cases.py`, `test_waypoint.py` | ✅ Stable |
| `graph_validation.py` | Phase 3c | `test_graph_validation.py`, `test_scaling.py` | ✅ Stable |
| `memory_os.py` | Phase 2c | `test_memory_os.py` | ✅ Stable |
| `llm_adapter.py` | Phase 3a | `test_llm_adapter.py`, `test_llm_integration.py` | ✅ Stable |
| `evaluation.py` | Phase 3f | `test_evaluation.py` | ✅ Stable |
| `reflection.py` | Phase 3g | `test_reflection.py` | ✅ Stable |
| `spinor_connection.py` | Phase 4 | `test_spinor.py` | ✅ Stable (research, not operational) |
| `scenario_loader.py` | Phase 3e | `test_minidomain.py` | ✅ Stable |

---

## 13. Open Points & Follow-ups

| Area | Status | Note |
|---|---|---|
| Reflection layer hybrid metrics | ⚪ Open | Reflection still ignores `hybrid_override_rate`. Hooks needed. |
| MemOS explicit geometry field | ⚪ Open | Geometry stored only implicitly via overlay snapshots. |
| Born criterion operational integration | ⚪ Research | `E0_BORN_CRITERION_ANALYSIS_v1.md` establishes that P(z) = I(z)/ΣI is the structurally natural candidate inside a bounded realization regime, but it is not yet enforced by the controller. |
| Historization × Gordian trap formal tests | ⚪ Exploration only | `explore_historization_gordian.py` shows stability but no formal tests yet. |
| Multi-axis SU(2) topology | ⚪ Phase 4 | Current spinor layer uses σ_z-only (minimal embedding). Multi-axis support exists via `axis_fn` API but requires designing graph domains with multiple independent loop orientations. |
| Dynamic horizon / per-domain horizons | ⚪ Open | Single global `hybrid_horizon` still. |
| Partial hybrid override (confidence-weighted) | ⚪ Open | Override is still binary; no confidence score channel. |

---

This document intentionally records **observations only**. No code was changed during this analysis.
