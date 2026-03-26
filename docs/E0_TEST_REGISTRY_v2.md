# E₀ Test Registry v2

> Central validation registry for the E₀ Framework.
> **Purpose:** connect claims, tests, evidence, and status in one place.

**Last updated:** 2026-03-26  
**Scope:** Deterministic controller, phase/amplitude layer, G5 geometries, hybrid arbitration, historization, multi-goal behavior, topology scans, Born sampling comparison, multi-axis SU(2), and active edge-case work.

---

## 1. Why v2 exists

`E0_TEST_REGISTRY_v1.md` provides a strong inventory of test files, counts, domains, and key findings.

This v2 document adds the missing scientific layer:

> **Claim → Test → Result → Status**

That makes the registry usable not only as engineering documentation, but as a research validation map.

---

## 2. Status vocabulary

| Status | Meaning |
|--------|---------|
| ✅ Confirmed | Reproduced by dedicated tests and/or reports |
| ⚠ Partial | Supported, but not yet closed or generalized |
| 🔄 In progress | Active work exists, but no final conclusion yet |
| ❌ Falsified | Counterexample or failed target found |
| ❓ Untested | Not yet operationalized into tests |

---

## 3. Claims & evidence map

### C1 — Greedy traps exist in bounded domains

**Claim**  
Pure local burden minimization can select structurally inferior paths (loops, dead ends, or deceptive entries).

**Evidence**  
- `e0_controller/test_phase2_minidomain.py`
- `e0_controller/test_greedy_trap.py` *(source exists; import issue remains)*
- `e0_controller/demo_greedy_trap.py`

**Result**  
Greedy repeatedly prefers locally cheaper but globally worse routes in trap domains.

**Status**  
✅ Confirmed

---

### C2 — Amplitude overlay reproduces constructive and destructive interference

**Claim**  
Bounded path-family summation using

```text
Ψ(p) = exp(−S(p)) · exp(iΘ(p))
I(a) = |ΣΨ|²
```

produces operational constructive/destructive interference effects.

**Evidence**  
- `e0_controller/test_amplitude_overlay.py`
- `e0_controller/test_phase2_minidomain.py`
- `docs/E0_SUMMATION_GEOMETRY_COMPARISON_v1.md`

**Result**  
Interference effects are visible across Mini-Domain, Diamond, Waypoint, and Gordian-style structures. Probability normalization and intensity identities hold.

**Status**  
✅ Confirmed

---

### C3 — Simple geometry reduces path inflation relative to prefix

**Claim**  
`simple` summation suppresses loop/path-family inflation that appears under `prefix`, while preserving useful amplitude structure for exploration.

**Evidence**  
- `e0_controller/test_amplitude_overlay.py`
- `e0_controller/test_waypoint.py`
- `docs/E0_SUMMATION_GEOMETRY_COMPARISON_v1.md`

**Result**  
`simple` remains the strongest default exploration geometry; `prefix` overcounts recursive support in continuation-heavy domains.

**Status**  
✅ Confirmed

---

### C4 — Goal-reaching geometry (G5) resolves prefix inflation for endpoint questions

**Claim**  
If the question is goal-oriented, only goal-reaching paths should contribute to the amplitude superposition.

**Evidence**  
- `e0_controller/test_gordian_trap.py`
- `docs/E0_PHASE3Q_INTERFERENCE_REPORT_v1.md`
- `docs/E0_G5_MULTIGOAL_FORMALIZATION_v1.md`

**Result**  
Under Gordian, `goal_reaching` selects the coherent detour where `simple` still prefers the decoy due to prefix dominance.

**Status**  
✅ Confirmed

---

### C5 — Holonomy difference ΔΘ depends only on forward-edge transition field values

**Claim**  
For competing paths sharing endpoints,

```text
ΔΘ = ½ [Σ v(path_1) − Σ v(path_2)]
```

and is independent of back-edges because the Helmholtz potential cancels in the difference.

**Evidence**  
- `e0_controller/test_gordian_trap.py::TestHolonomyFormula`
- `docs/E0_PHASE3Q_INTERFERENCE_REPORT_v1.md`

**Result**  
Predicted and actual ΔΘ match to 6 decimal places in the Gordian domain; back-edge variations do not alter the holonomy difference.

**Status**  
✅ Confirmed

---

### C6 — Interference can override a greedy-preferred action (Gordian Trap)

**Claim**  
A locally attractive action family can be suppressed by destructive interference, allowing a structurally coherent detour to dominate.

**Evidence**  
- `e0_controller/test_gordian_trap.py::TestPathLevelInterference`
- `e0_controller/test_gordian_trap.py::TestOverlayGoalReaching`
- `docs/E0_PHASE3Q_INTERFERENCE_REPORT_v1.md`

**Result**  
In Gordian, A-family interference factor falls below 0.1; `goal_reaching` shifts support to B1; hybrid overrides greedy A1 → B1.

**Status**  
✅ Confirmed

---

### C7 — Hybrid arbitration is operationally meaningful

**Claim**  
`AMPLITUDE_ON_DISAGREE` is not decorative; it changes behavior when greedy and amplitude disagree.

**Evidence**  
- `e0_controller/test_gordian_trap.py::TestHybridOverride`
- `e0_controller/test_amplitude_overlay.py`
- hybrid metrics in `e0_controller/evaluation.py`

**Result**  
Hybrid overrides are real, measurable, and improve behavior in trap-style domains.

**Status**  
✅ Confirmed

---

### C8 — Historization does not destroy Gordian interference routing under tested regimes

**Claim**  
Interference-based routing in Gordian remains structurally stable under repeated, adversarial, and mixed historization scenarios.

**Evidence**  
- historization scenarios integrated into `e0_controller/test_gordian_trap.py`
- `e0_controller/test_historization_gordian.py` — 61 dedicated tests across 14 classes
- `docs/E0_EVIDENCE_AND_FALSIFICATION_STATUS_v1.md`

**Result**  
Across tested scenarios, `cos(ΔΘ)` remains destructive (< 0), B-path dominance survives, and hybrid routing remains stable. Extended verification covers: parametric resilience (δ_max, ρ, λ_s, λ_f), FAILURE outcomes, K2 lazy decay recovery, clipping saturation, alternating adversarial, recovery from adversarial, holonomy formula invariance under historization, multi-goal × historization, extreme stress (100+ passes), hybrid multi-cycle, **and non-Gordian topologies (Triangle, Diamond, Gordian-lite) under U(1) and SU(2)**.

**Status**  
✅ Confirmed *(Gordian + Triangle + Diamond + Gordian-lite)*

---

### C9 — Coherence is relative to a goal set, not absolute

**Claim**  
A path family suppressed relative to one goal may remain coherent relative to another goal in the same goal set.

**Evidence**  
- multi-goal sections in `e0_controller/test_gordian_trap.py`
- `e0_controller/explore_multigoal.py`
- `docs/E0_G5_MULTIGOAL_FORMALIZATION_v1.md`
- `docs/E0_EVIDENCE_AND_FALSIFICATION_STATUS_v1.md`

**Result**  
Alternative-goal support rescues A1 from single-goal destructive suppression; goal-set changes alter the action ordering in principled ways.

**Status**  
✅ Confirmed

---

### C10 — G5 remains selective under tested edge cases up to |G| = 32

**Claim**  
Multi-goal G5 does not automatically collapse into flat, noisy, or arbitrary rankings as goal sets grow.

**Evidence**  
- `e0_controller/test_g5_edge_cases.py` — 12 classes / 55 tests
- `docs/E0_G5_EDGE_CASE_SUITE_v1.md`

**Result**  
No failure signatures F1–F4 triggered up to |G| = 32. Entropy decreases and top-1 gap increases; anti-saturation confirmed. P(A) converges to ≈ 0.74 at LCM-6 multiples. 64 truly unreachable goals produce zero probability drift (< 1e-14). SU(2) preserves all properties at |G| = 32.

**Status**  
✅ Confirmed *(tested to |G| = 32, U(1) and SU(2))*

---

### C11 — Topology strongly predicts override likelihood

**Claim**  
Override behavior is not random; it depends on path-family count and phase opposition.

**Evidence**  
- `e0_controller/test_topology_classification.py`

**Result**  
Triangle: 0% overrides; Diamond: ~37%; Gordian-lite: ~93%. Phase opposition is the strongest predictor. G5 produces uniquely different decisions in a substantial fraction of graphs.

**Status**  
✅ Confirmed

---

### C12 — Bounded-horizon overlay scales beyond toy domains

**Claim**  
The bounded-horizon overlay remains computationally manageable on larger graphs.

**Evidence**  
- `e0_controller/test_scaling.py`

**Result**  
At n ≤ 500 with bounded horizon, runtime remains controlled and path count depends on horizon more than graph size.

**Status**  
⚠ Partial

**Why partial?**  
Scaling is demonstrated for current bounded settings, but not yet for large branching factors or wider amplitude horizons.

---

### C13 — LLM integration works with the E₀ controller stack

**Claim**  
The LLM adapter can build usable landscapes and support controller execution, including hybrid and multi-goal scenarios.

**Evidence**  
- `e0_controller/test_llm_adapter.py`
- `e0_controller/test_llm_integration.py`
- `e0_controller/test_invoice.py`

**Result**  
Live API tests and mocked tests show viable graph construction, controller runs, and multi-goal handling.

**Status**  
⚠ Partial

**Why partial?**  
Live LLM tests are conditional and non-deterministic; integration is operationally strong but not yet benchmarked as a stable scientific layer.

---

### C14 — Phase derivation from v_rot is fully closed

**Claim**  
Θ is fully derived from E₀ primitives without operational gaps. ω = ½(v_rot(x,y) − v_rot(y,x)) is the unique admissible phase generator (up to scale).

**Evidence**  
- `e0_controller/test_omega_uniqueness.py` — 27 tests, 8 classes
- `e0_controller/explore_omega_uniqueness.py` — 5 alternatives tested on 4 domains
- `docs/E0_THETA_ANTISYMMETRY_DERIVATION_v0.md` — theoretical derivation with axioms A1–A4

**Result**  
Five alternative phase generators (ω_sym, ω_full, ω_v, ω_grad, ω_nonlin) each violate at least one axiom. Only ω_true satisfies all: A1 (antisymmetry), A3 (gauge invariance), A4 (reciprocity neutrality), P1 (non-degeneracy). Helmholtz orthogonality v_grad ⊥ v_rot verified. Gradient always path-independent (telescopes). The derivation chain v → v_rot → ω → Θ → SU(2) is now justified at every link.

**Status**  
✅ Confirmed

---

### C15 — SU(2) / spinor lift is operationally realized

**Claim**  
Scalar Θ has been lifted to an SU(2) generator with matrix-valued propagation. Phase 4b: rotation axis n̂ derived from local Helmholtz vorticity (geometric coupling). SU(2) is now wired into the controller's amplitude overlay as an operational switch (`use_su2=True` for SU(2)-minimal, `use_su2="geometric"` for SU(2)-geometric with Helmholtz A⃗).

**Evidence**  
- `e0_controller/test_spinor.py` — 76 tests across 12 classes:
  - `TestSU2ControllerOverlay` — 5 integration tests
  - `TestThreeTheoryNaturalDomains` — 11 natural domain tests (Diamond, Leaf, Triangle-Dense, Gordian-lite)
  - `TestPerformanceScaling` — 3 performance overhead tests (10-node mesh, 36 edges)
- `e0_controller/spinor_connection.py` — Phase 4a (minimal σ_z) + Phase 4b (geometric A⃗)
- `e0_controller/explore_spinor.py` — 6 domain explorations
- `e0_controller/amplitude_overlay.py` — `use_su2` parameter: `False` (U(1)), `True` (SU(2)-min), `"geometric"` (SU(2)-geo)
- `e0_controller/controller.py` — `use_su2` parameter threaded through `E0Controller.__init__()` → `_compute_overlay()`

**Result**  
SU(2) primitives verified (Pauli algebra, det=1, unitarity). Single-path magnitudes match U(1). Phase halving Θ→Θ/2 changes interference (double cover). 720° periodicity confirmed. **Geometric coupling** derives 3-component connection A⃗ = (A₁, A₂, A₃) from Helmholtz decomposition: A₁ = vorticity gradient, A₂ = face holonomy, A₃ = ω. Three-theory separation (U(1), SU(2)-min, SU(2)-geo) observed: up to 55.3% divergence on Gordian. Winner flips between U(1) and SU(2) on Gordian Trap.

**Operational integration verified:**
- Gordian trap: U(1) I(A1)=9.41, SU(2) I(A1)=18.06 (47.9% divergence on multi-path A-family)
- Single-path B1: U(1) ≈ SU(2) (2.1% divergence — confirming single-path equivalence)
- SU(2) sharpens probability discrimination: P(A1)=0.79 vs U(1) P(A1)=0.66
- Hybrid mode with `use_su2=True` and `use_su2="geometric"` both reach GOAL correctly

**Three-theory natural domain validation:**
- Diamond / Leaf: all three theories produce identical results (single-path families — no multi-path interference)
- Triangle-Dense: winner agrees across all theories; intensity difference < 2%
- Gordian-lite: U(1)→B winner, SU(2)-min→A (I=1.028), SU(2)-geo→A (I=0.556) — geo intensity lies between U(1) and min
- SU(2)-geo hybrid controller reaches goal correctly on Gordian

**Performance overhead (10-node mesh, 36 edges, horizon=4):**
- U(1): ~800 µs/call
- SU(2)-min: ~1344 µs/call (1.7×)
- SU(2)-geo: ~3941 µs/call (4.9×)
- Overhead bounded by generous ceilings (10× for min, 20× for geo) to avoid CI flakiness

**Status**  
✅ Confirmed

---

### C16 — Stable resonators / proto-persistent structures emerge in E₀

**Claim**  
Closed interference structures plus historization can form self-sustaining localized entities.

**Evidence**  
- `e0_controller/test_resonator.py` — 73 tests across 13 classes (9 original + 4 multi-loop)
- `e0_controller/explore_resonator.py` — 5 regimes (M1/M2/M3/C1/C2), 4 historization modes, 3 multi-loop builders
- `docs/E0_RESONATOR_STABILITY_CRITERION_v0.md`, `docs/E0_MINIMAL_RESONATOR_TEST_DESIGN_v0.md`

**Result**  
3-node resonator kernel (A→B→C→A + leakage C→OUT) tested across 5 regimes. M2/H0 and M3/H0 are genuine RESONATOR: R_coh > 0.3, leakage non-dominant. M1 transitions METASTABLE→RESONATOR with ≥10 historization rounds (memory enables resonance). C1 (acyclic) = DECAY, C2 (dephased) = DECAY — both negative controls pass. Historization can enable resonance (M1) or destabilize it via over-amplification (M2/M3). Loop holonomy ∈ SU(2) confirmed, three-theory separation on resonator domain.

**Multi-loop extension (O5):**
- **4-node ring** (A→B→C→D→A + leak): RESONATOR, longer phase accumulation survives, SU(2)-min I > U(1) I (phase halving constructive), three-theory separation confirmed
- **Nested loops** (outer A→B→C→A, inner B→X→C): constructive interference factor ~2.0 between outer and inner families, phase difference Δθ=0.14, SU(2) differs from U(1) on mixed paths
- **Coupled resonators** (K1: A-B-C, K2: P-Q-R, bridge C→P): both kernels independently RESONATOR, K1-historization isolated from K2, bridge historization increases cross-kernel coupling, identical holonomies for identical parameters

**Status**  
✅ Confirmed

### C17 — Born-regime axioms are satisfied on E₀ domains

**Claim**  
The 5 Born-Criterion axioms (bounded alternatives, mutual exclusivity, representation invariance, monotonicity, coarse-graining consistency) hold on concrete E₀ domains, and P(z) = I(z)/ΣI is the unique minimal realization rule.

**Evidence**  
- `e0_controller/test_born_regime.py` — 44 tests across 10 classes
- `docs/E0_BORN_CRITERION_ANALYSIS_v1.md` — theoretical derivation of 5 axioms
- `docs/E0_INTENSITY_AND_BORN_PROGRAM_v1.md` — structural analysis of |Ψ|²

**Result**  
All 5 axioms verified numerically on 5 domains (MiniDomain, Diamond, Gordian, Multi-goal, Current-loop):
- B1: Finite bounded Ω confirmed (2–3 actions per domain)
- B2: Unique amplitude winner on every domain (no ties)
- B3: I = |Ψ|² phase-invariant to 10 decimals under 5 different global rotations
- B4: P ordering matches I ordering on all domains and geometries
- B5: Partition additivity ΣP = 1.0 ± 1e-10 on all domains

Uniqueness verified:
- U1: √I, I², log(1+I) distortions all change the distribution (not faithful)
- U2: |Ψ| shows weaker interference suppression than |Ψ|² (squared norm privileged)
- U3: ΣP = 1.0 across all 4 geometries (prefix, simple, first_arrival, goal_reaching)

**Status**  
✅ Confirmed (conditional: inside bounded-exclusive regime)

---

### C18 — Reflection layer incorporates amplitude-hybrid metrics

**Claim**  
The reflection layer triggers on amplitude-derived metrics (R_coh, Θ-consistency, amplitude drift) and produces structured observations, layer attributions, and recommendations based on coherence anomalies.

**Evidence**  
- `e0_controller/test_reflection_hybrid.py` — 42 tests across 12 classes (H1–H12)
- `e0_controller/evaluation.py` — RunEvaluation extended with r_coh_avg/min/max, theta_consistency, amplitude_drift
- `e0_controller/reflection.py` — should_reflect() extended with amplitude quality/opportunity triggers

**Result**  
- RunEvaluation carries 5 amplitude fields (r_coh_avg, r_coh_min, r_coh_max, theta_consistency, amplitude_drift)
- evaluate_run() / evaluate_scenario() accept, round, and store all fields
- Warnings fire on low R_coh (< 0.3) and high drift (> 30%)
- should_reflect() triggers quality on drift > 0.3 or R_coh < 0.3
- should_reflect() triggers opportunity on R_coh > 0.8 or Θ > 0.9
- Rule-based reflection (_reflect_failure/quality/opportunity) surfaces amplitude patterns
- Evidence block includes amplitude section for LLM reflection
- No false triggers when amplitude data is absent (R_coh=0)

**Status**  
✅ Confirmed

---

### C19 — Dynamic horizons adapt to graph topology

**Claim**  
Amplitude overlay horizon h can be dynamically adapted per state based on topology (branching factor, goal distance, graph diameter) instead of using a fixed constant, and controller behavior remains correct under all strategies.

**Evidence**  
- `e0_controller/test_dynamic_horizon.py` — 45 tests across 15 classes (D1–D15)
- `e0_controller/dynamic_horizon.py` — fixed, topology_adaptive, capped_adaptive strategies
- `e0_controller/controller.py` — horizon_strategy parameter in E0Controller

**Result**  
- fixed(h) returns constant h, validates h ≥ 1
- branching_factor correctly reports 0–5 neighbors across domains
- goal_distance returns BFS shortest-path or None (unreachable/no goals)
- topology_adaptive: h = max(h_min, distance) - branching_reduction, clamped to [h_min, h_max]
- Branching reduction activates at threshold (default 3), caps at 2
- No-goal fallback returns h_max
- capped_adaptive: wraps topology_adaptive with explicit cap
- Controller accepts horizon_strategy, calls it per-state in select_hybrid()
- None strategy falls back to fixed hybrid_horizon
- All strategies produce valid overlay reports on Mini, Diamond, Gordian domains
- Full runs in HYBRID/GREEDY modes with all strategies: no crashes, correct traces

**Status**  
✅ Confirmed

---

### C20 — Confidence-weighted override gating

**Claim**  
Amplitude overlay override can be gated by a confidence threshold (P_best − P_second ≥ θ), so low-confidence overlays fall back to greedy instead of overriding. With θ = 0 all prior behavior is preserved (backward-compatible).

**Evidence**  
- `e0_controller/test_confidence_override.py` — 31 tests across 12 classes (F1–F12)
- `e0_controller/amplitude_overlay.py` — `override_confidence` property on `OverlayReport`
- `e0_controller/controller.py` — `confidence_threshold` parameter, gating in `select_hybrid()`

**Result**  
- Confidence gap = P_best − P_second, correctly computed for 2–5 actions
- Single action → confidence 0 (no second action to compare)
- Equal probabilities → gap ≈ 0
- Threshold=0.0 matches pre-existing behavior exactly (no regressions in 875-test suite)
- High threshold blocks override on Diamond, Wide, and simple-geometry Gordian
- On Gordian with goal_reaching: one action has 0 goal paths → confidence = 1.0 (correct edge case)
- StepResult.override_confidence populated from overlay each cycle
- RunTrace.metrics()['avg_override_confidence'] averages across overridden steps
- Threshold sweep: higher θ → monotonically ≤ overrides (verified)

**Status**  
✅ Confirmed

---

### C21 — MemOS geometry persistence round-trip

**Claim**  
MemOS correctly persists, restores, and summarizes the amplitude overlay geometry (hybrid_geometry) and confidence threshold (confidence_threshold) across save/load cycles. All four geometry types survive JSON round-trip. Old sessions without the geometry field default gracefully to "simple".

**Evidence**  
- `e0_controller/test_memos_geometry.py` — 34 tests across 10 classes (G1–G10)
- `e0_controller/memory_os.py` — hybrid_geometry + confidence_threshold in RuntimeSnapshot, restore_controller, and _build_overlay_summary

**Result**  
- RuntimeSnapshot.controller_params now includes hybrid_geometry and confidence_threshold
- All 4 geometries (prefix, simple, first_arrival, goal_reaching) survive save→load→restore
- restore_controller passes hybrid_geometry and confidence_threshold to E0Controller.__init__
- _build_overlay_summary passes controller.hybrid_geometry to analyze_controller_state
- Old persisted data (no geometry/threshold fields) defaults to "simple" / 0.0 gracefully
- Geometry stable across two save/restore cycles; independent across sessions
- Diamond + Gordian domain integration verified with restored controllers

**Status**  
✅ Confirmed

---

### C22 — Born sampling as alternative realization regime (ADR-0007)

**Claim**  
Born sampling (P ∝ I, choosing actions probabilistically from the amplitude-derived distribution) is a valid alternative realization regime alongside deterministic argmax. With goal_reaching geometry, argmax dominates or matches Born sampling on success rate. Born sampling enables stochastic exploration: it reaches all G5 goals and can randomly escape traps where argmax gets stuck due to greedy–amplitude agreement. The BORN_SAMPLING mode integrates cleanly with existing infrastructure (MemOS persistence, StepResult, escalation handling).

**Evidence**  
- `e0_controller/test_born_sampling.py` — 27 tests across 10 classes (H1–H10)
- `e0_controller/controller.py` — HybridMode.BORN_SAMPLING + `_born_sample()` method

**Result**  
- H1: All Born-sampled transitions are valid on Diamond, Gordian, G5
- H2: Sampling frequencies converge to P(a) = I(a) / Σ I over repeated trials
- H3: With goal_reaching geometry, argmax ≥ born; with simple geometry, both struggle on Gordian (geometry choice matters more than decision rule)
- H4: Diamond efficiency identical for both modes (no traps, 2-step paths)
- H5: Born sampling reaches all 3 G5 goals across trials; argmax always picks same 1
- H6: Argmax avg steps ≤ Born avg steps (deterministic always optimal or tied)
- H7: Argmax variance = 0 (deterministic); Born variance > 0 on multi-path domains
- H8: Born sampling sometimes picks trap on Gordian with simple geometry (coherence cost of stochastic exploration)
- H9: BORN_SAMPLING mode survives MemOS save → load → restore round-trip
- H10: StepResult correctly marks Born-chosen actions as overridden

**Status**  
✅ Confirmed

---

## 4. Test-file → claim map

| Test file | Primary claims covered |
|-----------|------------------------|
| `test_amplitude_overlay.py` | C2, C3, C7 |
| `test_phase2_minidomain.py` | C2, C14 |
| `test_waypoint.py` | C3, C4 |
| `test_gordian_trap.py` | C4, C5, C6, C7, C8, C9 |
| `test_g5_edge_cases.py` | C9, C10 (families A–E + O2 large-|G|) |
| `test_topology_classification.py` | C11 |
| `test_scaling.py` | C12 |
| `test_llm_adapter.py` | C13 |
| `test_llm_integration.py` | C13 |
| `test_invoice.py` | C7, C13 |
| `test_memory_os.py` | persistence support for hybrid workflows |
| `test_graph_validation.py` | graph-quality support layer |
| `test_evaluation.py` | evaluation/rating support layer |
| `test_reflection.py` | reflection support layer |
| `test_reflection_hybrid.py` | C18 |
| `test_dynamic_horizon.py` | C19 |
| `test_confidence_override.py` | C20 |
| `test_memos_geometry.py` | C21 |
| `test_born_sampling.py` | C22 |
| `test_spinor.py` | C15, C23, C12 |
| `test_resonator.py` | C16, C24 |
| `test_omega_uniqueness.py` | C14 |
| `test_historization_gordian.py` | C8, C9 (Gordian + O1 non-Gordian) |
| `test_born_regime.py` | C17 |
| `test_minidomain.py` | base mechanics, historization, K11/K12 |
| `test_g5_edge_cases.py` | C10, C23 (SU(2) classes) |
| `test_topology_classification.py` | C11, C23 (SU(2) classes) |
| `test_born_sampling.py` | C22, C23 (H11 class) |
| `test_multi_axis_su2.py` | C15, C23, C25 |

---

### C23 — SU(2) reclassifies topology: Gordian override rate 90% → 0%

**Claim**  
SU(2) phase halving (Θ→Θ/2) weakens destructive interference on multi-path families, fundamentally changing the topology-to-override mapping. Gordian-lite graphs that produce ~90% override rate under U(1) produce ~0% under SU(2) because the halved phases no longer reach destructive opposition.

**Evidence**  
- `e0_controller/test_topology_classification.py` — `TestSU2TriangleStillNeverOverrides` (1 test), `TestSU2DiamondOverrideShift` (2 tests), `TestSU2GordianLiteOverrides` (2 tests), `TestSU2PhaseHalvingEffect` (2 tests)
- `e0_controller/test_g5_edge_cases.py` — `TestG5UnderSU2_WinnerStability` (5 tests), `TestG5UnderSU2_StructuralInvariants` (4 tests), `TestG5UnderSU2_Selectivity` (3 tests)
- `e0_controller/test_born_sampling.py` — `TestH11BornSamplingUnderSU2` (4 tests)

**Result**  
- **Triangle**: 0% overrides under both U(1) and SU(2) (single family → no interference)
- **Diamond**: Override rate identical under U(1) and SU(2) — each family has exactly 1 path, so phase halving has no multi-path effect
- **Gordian-lite**: Override rate drops from ~90% (U(1)) to ~0% (SU(2)) — phase halving eliminates destructive interference on A-family's two paths
- **G5 Winner Flip**: Family D single-goal: U(1) selects B (A destructive, I=0.024), SU(2) selects A (halved phase restores coherence, I=1.028) — 43× intensity increase
- **G5 structural invariants preserved**: probabilities sum to 1, intensities non-negative, unreachable goals have zero effect, entropy decreases with |G|
- **Born sampling**: SU(2) shifts sampling distribution toward A on Gordian multi-path domains
- **Single-path equivalence confirmed**: Diamond/B1 intensities identical under U(1) and SU(2)

**Status**  
✅ Confirmed

---

### C24 — Resonator behavior scales to multi-loop and coupled topologies

**Claim**  
Resonance (R1–R4 criteria) is not limited to the minimal 3-node kernel. Larger rings (4-node), nested loops (two interfering loop families), and coupled resonator pairs all exhibit measurable resonance, constructive interference, and SU(2) structure.

**Evidence**  
- `e0_controller/test_resonator.py` — `TestFourNodeLoop` (6 tests), `TestNestedLoop` (6 tests), `TestCoupledResonators` (7 tests), `TestMultiLoopSU2` (6 tests)
- `e0_controller/explore_resonator.py` — `build_4node_loop()`, `build_nested_loop()`, `build_coupled_resonators()`, `generic_loop_paths()`, `measure_generic_loop()`

**Result**  
- **4-node ring**: Classifies as RESONATOR; I_coh positive across 8 cycles; leakage non-dominant; θ ≠ 0; acyclic control has no loop closure; SU(2) holonomy nontrivial (tr=1.78); three-theory separation: U(1)=1.78, SU(2)-min=4.67, SU(2)-geo=3.72; SU(2)-min > U(1) (phase halving constructive)
- **Nested loop**: Outer loop independently RESONATOR; inner path B→X→C has measurable intensity; **constructive interference factor ≈ 2.0** between outer and inner loop families (nearly pure constructive); phase difference Δθ=0.14 rad; SU(2) shows three-theory separation on mixed paths
- **Coupled resonators**: Both kernels independently RESONATOR; K1-historization completely isolated from K2 (I_coh unchanged to 6 decimals); cross-kernel path A→B→C→P→Q→R→P has measurable intensity; bridge historization increases coupling intensity; identical parameters produce identical holonomies; both holonomies ∈ SU(2); single cross-kernel path shows U(1)≡SU(2) (expected: single path)

**Status**  
✅ Confirmed

---

### C25 — Per-edge SU(2) rotation axes produce non-trivial multi-axis structure (B1)

**Claim**  
The SU(2) spinor transport can be extended from a single global axis (σ_z) to per-edge rotation axes via `axis_fn(L, x, y) → n̂ ∈ ℝ³`. When edges carry orthogonal axes (σ_x, σ_y, σ_z), transport matrices no longer commute across different edges, holonomy becomes axis-assignment-dependent, and multi-path interference patterns diverge from both single-axis SU(2) and U(1). The `axis_fn` parameter is threaded through the full stack: `E0Controller.__init__()` → `_compute_overlay()` → `analyze_controller_state()` → `spinor_psi()`. Backward compatibility is preserved: `axis_fn=None` produces identical results to the existing single-axis (σ_z) behavior.

**Evidence**  
- `e0_controller/test_multi_axis_su2.py` — 36 tests across 11 classes:
  - `TestPauliNonCommutativity` (4 tests): σ_x/σ_y/σ_z non-commutativity, same-axis commutativity, SU(2) closure
  - `TestTetrahedronDomain` (3 tests): 12-edge tetrahedron with orthogonal per-edge axes, every triangle uses all 3 axes
  - `TestEdgeTransportMultiAxis` (3 tests): per-edge transport differs from default σ_z, SU(2) preservation, inverse transport
  - `TestPathTransportMultiAxis` (4 tests): A→B→C ≠ A→C→B with multi-axis, SU(2) preservation, magnitude = exp(−S)
  - `TestMultiAxisHolonomy` (4 tests): nontrivial holonomy, different triangles differ, orientation dependence, single-axis diagonal
  - `TestMultiAxisInterference` (4 tests): multi-axis ≠ single-axis intensity, single-path axis-independence, three-way U(1)/σ_z/multi separation, tetrahedron multi-path interference
  - `TestMultiAxisSpinorProperties` (4 tests): probability normalization, non-negativity, magnitude preservation, reference-spinor properties
  - `TestControllerAxisFn` (5 tests): constructor accepts axis_fn, overlay produces results, overlay differs from single-axis (fan graph), cycle completes, axis_fn=None backward-compatible
  - `TestPathOrderDependence` (3 tests): different routes produce different spinors, three routes give distinct directions, path reversal changes transport
  - `TestFourTheoryComparison` (1 test): U(1), SU(2)-σ_z, SU(2)-geometric, SU(2)-multi-axis all differ
  - `TestDiamondAxisInsensitivity` (1 test): single-path families are axis-independent (control)
- `e0_controller/spinor_connection.py` — `axis_fn` parameter already threaded through `su2_path_transport`, `spinor_psi`, `spinor_sum_paths`, `spinor_intensity` (unchanged)
- `e0_controller/controller.py` — `axis_fn=None` parameter added to `E0Controller.__init__()`
- `e0_controller/amplitude_overlay.py` — `axis_fn=None` parameter added to `analyze_controller_state()`

**Result**  
- **Non-commutativity**: max|AB−BA| > 0.1 for all Pauli pairs; same-axis products commute (< 1e-12)
- **Edge transport**: σ_x transport differs from σ_z by 0.44 on tetrahedron edges with ω ≈ 0.9
- **Path non-commutativity**: A→B→C vs A→C→B differ by 1.29 under multi-axis (0.06 single-axis)
- **Holonomy**: Triangle A→B→C→A has dist_to_I = 0.92 (multi-axis) vs 0.05 (single-axis); different triangles differ by 1.19; reversed orientation differs
- **Interference**: Multi-axis intensity 1.043 vs single-axis 0.817 (diff 0.23) on tetrahedron 3-path family
- **Single-path invariance**: Diamond single-path families identical under any axis assignment (10 decimal places)
- **Controller integration**: Fan graph (action M has 2 paths) shows overlay intensity diff = 0.015 between single-axis and multi-axis
- **Four theories all differ**: U(1), σ_z, geometric, multi-axis produce distinct intensities on tetrahedron
- **Backward compatibility**: axis_fn=None intensities identical to old behavior (10 decimal places)

**Test domain design note:**  
Strongly asymmetric edge parameters (forward: δ=5.0, r=0.1; reverse: δ=0.1, r=0.9) are required to produce non-zero ω. Symmetric edges give ω=0 via the Helmholtz decomposition (v_rot(x,y) = v_rot(y,x)), which makes axis choice irrelevant.

**Status**  
✅ Confirmed

---

## 5. Open claims with recommended next tests

### O1 — Extreme historization stress

**Target claim**  
C8 under much stronger clipping / distortion regimes.

**Status:** ✅ Resolved

**What was done:**
- Extended `test_historization_gordian.py` with 4 new classes (25 tests):
  - `TestTriangleHistorization` (6): single-family topology immune to historization — P(A)=1.0 under all regimes, SU(2) included
  - `TestDiamondHistorization` (6): two-family winner shifts (expected intensity reweighting) with structural invariants preserved
  - `TestGordianLiteHistorization` (10): cos(ΔΘ) < 0 under all 6 regimes (pristine, short-success, loop-success, alternating, failure, mixed-100×); SU(2) A-wins preserved
  - `TestCrossTopologyHistorizationInvariants` (3): normalization + non-negativity + SU(2) normalization across all topologies
- File total: 61 tests / 14 classes (was 36/10)
- Key finding: Historization modifies resistance but cannot create or destroy interference patterns — topology determines interference possibility

---

### O2 — Large-goal-set G5 stability

**Target claim**  
C10 beyond |G| = 5.

**Status:** ✅ Resolved

**What was done:**
- Extended Family E tests to |G| = 16, 32 — A wins at all sizes, P(A) ∈ [0.70, 0.80], path count scales linearly
- Overall entropy trend H(32) < H(1) confirmed; periodicity convergence at LCM-6 multiples (spread < 0.001)
- Unreachable-goal stress: 64 isolated goals produce zero probability drift (< 1e-14)
- SU(2): winner stability, entropy trend, and anti-saturation all confirmed at |G| = 32
- 15 new tests in 3 classes: `TestFamilyE_LargeGoalSets` (8), `TestUnreachableGoalStress` (3), `TestLargeGoalSetsUnderSU2` (4)

---

### O3 — Weighted G5 necessity

**Target claim**  
Whether plain multi-goal summation remains sufficient.

**Recommended test**  
Introduce weighted goal sets only if edge-case failures emerge.

---

### O4 — SU(2) operational integration

**Target claim**  
C15 extended — use SU(2) intensities in actual controller decisions (currently research-only).

**Status:** ✅ Resolved in commit `e87d70a` and subsequent work.

**What was done:**
- `amplitude_overlay.py`: added `use_su2` parameter; when True, sums ℂ² spinor amplitudes and computes ‖Ψ‖² via `np.vdot`
- `controller.py`: added `use_su2` parameter to `E0Controller.__init__()`, threaded through `_compute_overlay()`
- `test_spinor.py`: 5 integration tests (`TestSU2ControllerOverlay`) verify divergence, single-path match, probability sharpening, hybrid goal-reaching, flag consistency
- `test_g5_edge_cases.py`: 12 tests (`TestG5UnderSU2_*`) verify G5 structural properties preserved under SU(2), including winner-flip on Family D
- `test_topology_classification.py`: 7 tests (`TestSU2*`) reclassify 380-graph topologies; Gordian override rate drops from 90% to 0% under SU(2)
- `test_born_sampling.py`: 4 tests (`TestH11BornSamplingUnderSU2`) verify Born sampling distribution shift under SU(2)

---

### O5 — Resonator scaling and multi-loop structures

**Target claim**  
C16 extended — resonator behavior in larger topologies with multiple loops.

**Status:** ✅ Resolved — see C24.

**What was done:**
- `explore_resonator.py`: 3 new builders (`build_4node_loop`, `build_nested_loop`, `build_coupled_resonators`), generalized measurement (`generic_loop_paths`, `measure_generic_loop`, `apply_generic_historization`)
- `test_resonator.py`: 25 tests across 4 new classes — 4-node ring, nested interference, coupled kernel isolation/coupling, multi-loop SU(2)
- Key finding: constructive interference factor ≈ 2.0 on nested loops; coupled kernels show isolation + bridge-mediated coupling

---

### P3 — Paper 3: Multi-Axis SU(2) and Non-Abelian Structure in E₀

**Target**  
Dedicated publication exploring per-edge SU(2) rotation axes as non-abelian gauge structure. Extends the SU(2) lift (C15) from global σ_z to per-edge axis assignment. Key results: non-commutativity, axis-dependent holonomy, interference divergence from U(1) and single-axis SU(2), four-theory comparison, and backward compatibility.

**Foundation**  
- B1 implementation complete (C25): 36 tests, full stack integration
- Canon Alignment §9 Bridge B1: per-edge rotation axes
- Builds on Paper 2 (SU(2) lift) by adding the non-abelian dimension

**Open questions for Paper 3**  
- How does axis assignment relate to physical geometry (embedding dimension)?
- Can axis_fn be derived from topology rather than assigned?
- What is the relationship between multi-axis holonomy and M_H topological invariant (B2)?
- Does multi-axis SU(2) predict new topology reclassifications beyond C23?

**Status:** 🔄 In progress (B1 engineering complete; paper draft pending)

---

## 6. Maintenance rule

When a new test family is added, update both:

1. the inventory-level registry (`E0_TEST_REGISTRY_v1.md`)
2. this claim-level registry (`E0_TEST_REGISTRY_v2.md`)

The v1 file answers:
> *What tests exist?*

The v2 file answers:
> *What do those tests establish?*

---

_End of document._