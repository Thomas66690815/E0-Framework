# E₀ Test Registry v2

> Central validation registry for the E₀ Framework.
> **Purpose:** connect claims, tests, evidence, and status in one place.

**Last updated:** 2026-03-25  
**Scope:** Deterministic controller, phase/amplitude layer, G5 geometries, hybrid arbitration, historization, multi-goal behavior, topology scans, and active edge-case work.

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
- `e0_controller/test_historization_gordian.py` — 36 dedicated tests across 10 classes
- `docs/E0_EVIDENCE_AND_FALSIFICATION_STATUS_v1.md`

**Result**  
Across tested scenarios, `cos(ΔΘ)` remains destructive (< 0), B-path dominance survives, and hybrid routing remains stable. Extended verification covers: parametric resilience (δ_max, ρ, λ_s, λ_f), FAILURE outcomes, K2 lazy decay recovery, clipping saturation, alternating adversarial, recovery from adversarial, holonomy formula invariance under historization, multi-goal × historization, extreme stress (100+ passes), and hybrid multi-cycle.

**Status**  
✅ Confirmed

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

### C10 — G5 remains selective under tested edge cases up to |G| = 5

**Claim**  
Multi-goal G5 does not automatically collapse into flat, noisy, or arbitrary rankings as goal sets grow.

**Evidence**  
- `e0_controller/test_g5_edge_cases.py`
- `docs/E0_G5_EDGE_CASE_SUITE_v1.md`

**Result**  
No failure signatures F1–F4 triggered in the tested suite. Entropy decreases and top-1 gap increases in the reported scenarios; anti-saturation behavior observed.

**Status**  
✅ Confirmed *(within tested range)*

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
Scalar Θ has been lifted to an SU(2) generator with matrix-valued propagation. Phase 4b: rotation axis n̂ derived from local Helmholtz vorticity (geometric coupling).

**Evidence**  
- `e0_controller/test_spinor.py` — 52 tests across 8 classes
- `e0_controller/spinor_connection.py` — Phase 4a (minimal σ_z) + Phase 4b (geometric A⃗)
- `e0_controller/explore_spinor.py` — 6 domain explorations

**Result**  
SU(2) primitives verified (Pauli algebra, det=1, unitarity). Single-path magnitudes match U(1). Phase halving Θ→Θ/2 changes interference (double cover). 720° periodicity confirmed. **Geometric coupling** derives 3-component connection A⃗ = (A₁, A₂, A₃) from Helmholtz decomposition: A₁ = vorticity gradient, A₂ = face holonomy, A₃ = ω. Three-theory separation (U(1), SU(2)-min, SU(2)-geo) observed: up to 55.3% divergence on Gordian. Winner flips between U(1) and SU(2) on Gordian Trap.

**Status**  
✅ Confirmed

---

### C16 — Stable resonators / proto-persistent structures emerge in E₀

**Claim**  
Closed interference structures plus historization can form self-sustaining localized entities.

**Evidence**  
- `e0_controller/test_resonator.py` — 48 tests across 9 classes
- `e0_controller/explore_resonator.py` — 5 regimes (M1/M2/M3/C1/C2), 4 historization modes
- `docs/E0_RESONATOR_STABILITY_CRITERION_v0.md`, `docs/E0_MINIMAL_RESONATOR_TEST_DESIGN_v0.md`

**Result**  
3-node resonator kernel (A→B→C→A + leakage C→OUT) tested across 5 regimes. M2/H0 and M3/H0 are genuine RESONATOR: R_coh > 0.3, leakage non-dominant. M1 transitions METASTABLE→RESONATOR with ≥10 historization rounds (memory enables resonance). C1 (acyclic) = DECAY, C2 (dephased) = DECAY — both negative controls pass. Historization can enable resonance (M1) or destabilize it via over-amplification (M2/M3). Loop holonomy ∈ SU(2) confirmed, three-theory separation on resonator domain.

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

## 4. Test-file → claim map

| Test file | Primary claims covered |
|-----------|------------------------|
| `test_amplitude_overlay.py` | C2, C3, C7 |
| `test_phase2_minidomain.py` | C2, C14 |
| `test_waypoint.py` | C3, C4 |
| `test_gordian_trap.py` | C4, C5, C6, C7, C8, C9 |
| `test_g5_edge_cases.py` | C9, C10 |
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
| `test_spinor.py` | C15 |
| `test_resonator.py` | C16 |
| `test_omega_uniqueness.py` | C14 |
| `test_historization_gordian.py` | C8, C9 |
| `test_born_regime.py` | C17 |
| `test_minidomain.py` | base mechanics, historization, K11/K12 |

---

## 5. Open claims with recommended next tests

### O1 — Extreme historization stress

**Target claim**  
C8 under much stronger clipping / distortion regimes.

**Status:** ✅ Largely addressed by `test_historization_gordian.py` — covers δ_max=0.5/10.0, ρ=0.5/1.0, λ variations, 100 adversarial passes, 50 alternating cycles, FAILURE outcomes, K2 decay recovery, and clipping saturation.

**Remaining gap:** Cross-domain generalization (non-Gordian topologies with historization stress).

---

### O2 — Large-goal-set G5 stability

**Target claim**  
C10 beyond |G| = 5.

**Recommended test**  
Extend edge-case suite with larger goal sets and weighted/irrelevant/noisy goals.

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

**Recommended test**  
Swap U(1) intensity for SU(2) intensity in amplitude overlay and compare override decisions.

---

### O5 — Resonator scaling and multi-loop structures

**Target claim**  
C16 extended — resonator behavior in larger topologies with multiple loops.

**Recommended test**  
Extend 3-node kernel to 4+ node loops, nested loops, and multi-resonator coupling.

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