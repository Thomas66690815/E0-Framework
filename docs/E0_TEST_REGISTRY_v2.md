# E₀ Test Registry v2

> Central validation registry for the E₀ Framework.
> **Purpose:** connect claims, tests, evidence, and status in one place.

**Last updated:** 2026-03-29 — **2028 tests** (0 failures, 0 warnings)  
**Scope:** Deterministic controller, phase/amplitude layer, G5 geometries, hybrid arbitration, historization, multi-goal behavior, topology scans, Born sampling comparison, multi-axis SU(2), curvature modulation, LLM context enrichment, K5 field-based escalation, MemOS persistence fidelity, B4 self-tuning meta-layer, Session orchestrator, **C37 residual tension + iterative control (Axiom A₀)**, **C38 E0Envelope + TransportRegime**, **C39 resonator-controller integration**, **C40 graduated overlap functional (M_H from Ontodynamics §3.4)**, **C41 stochastic exploration policy (Born warmup → exploit)**, **B4-S1 Landscape mutation API (Bridge 4 Structural Reflexivity)**, **B4-S2 Structural Mutation Infrastructure**, **B4-S3 Structural Tuning Cycle + Session.iterate() hook**, **B4-S4a Identity Invariant (goal-reachable + A₀-compliant + historization-continuous)**, Beipackzettel real-world validation, non-circular amplitude mass trap, ProvenanceLog evidence chain, live LLM provenance, **C42 4-Layer Model (trace_load/trace_quality/inertia_factor)**, **C43 Self-Graph (Selbstunterscheidung)**, **C44 Bootstrapper (structured spec → Landscape)**, **C45 LLM Adapter v2 (propose_domain_graph)**, **C46 Mode Controller (LEARN/EXECUTE/COMBINATION)**, **C47 Dual Reflection (self-graph diagnosis + meta-control)**, and active edge-case work.

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
- `e0_controller/test_spinor.py` — 71 tests across 11 classes:
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
- `e0_controller/test_born_regime.py` — 44 tests across 9 classes
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
- `e0_controller/test_born_sampling.py` — 31 tests across 11 classes (H1–H11)
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
| `test_greedy_trap.py` | C1 |
| `test_amplitude_overlay.py` | C2, C3, C7 |
| `test_phase2_minidomain.py` | C2, C14 |
| `test_phase2_invoice.py` | C2, C14 |
| `test_waypoint.py` | C3, C4 |
| `test_gordian_trap.py` | C4, C5, C6, C7, C8, C9 |
| `test_g5_edge_cases.py` | C9, C10, C23 (families A–E, O2, SU(2)) |
| `test_topology_classification.py` | C11, C23 (SU(2) classes) |
| `test_scaling.py` | C12 |
| `test_llm_adapter.py` | C13 |
| `live_test_llm.py` | C13 (live, requires API key) |
| `test_invoice.py` | C7, C13 |
| `test_memory_os.py` | persistence support for hybrid workflows, C28 |
| `test_graph_validation.py` | graph-quality support layer |
| `test_evaluation.py` | evaluation/rating support layer |
| `test_reflection.py` | reflection support layer, C36 |
| `test_reflection_hybrid.py` | C18 |
| `test_dynamic_horizon.py` | C19 |
| `test_confidence_override.py` | C20 |
| `test_memos_geometry.py` | C21 |
| `test_born_sampling.py` | C22, C23 (H11 class) |
| `test_spinor.py` | C15, C23, C12 |
| `test_resonator.py` | C16, C24 |
| `test_omega_uniqueness.py` | C14 |
| `test_historization_gordian.py` | C8, C9 (Gordian + O1 non-Gordian) |
| `test_born_regime.py` | C17 |
| `test_minidomain.py` | base mechanics, historization, K11/K12 |
| `test_multi_axis_su2.py` | C15, C23, C25 |
| `test_curvature_modulation.py` | C26 |
| `test_llm_context.py` | C13, C27 |
| `test_k5_escalation.py` | C27 |
| `test_self_tuning.py` | C29 |
| `test_session.py` | C30 |
| `test_beipackzettel.py` | C31 |
| `test_beipackzettel_noncircular.py` | C32 |
| `test_provenance.py` | C33 |
| `test_mass_trap_detector.py` | C34 |
| `test_ezb_zinsentscheidung.py` | C35 |
| `test_residual_tension.py` | C37, C37b |
| `test_envelope.py` | C38 |
| `test_burnout_composite.py` | Domäne 3 composite |
| `test_resonator_integration.py` | C39 |
| `test_overlap.py` | C40 |
| `test_exploration_policy.py` | C41 |
| `test_landscape_mutation.py` | B4-S1 |
| `test_structural_mutation.py` | B4-S2, B4-S4a |
| `test_structural_tuning_cycle.py` | B4-S3 |

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

### C27 — LLM context enrichment and K5 field-based escalation

**Claim**  
The LLM adapter SYSTEM_PROMPT encodes the complete E₀ canon essence (11 symbols: Δ, R, H, S, C, v, ω, Θ, Ψ, I, M_H), giving the LLM semantic grounding for all E₀ primitives. The MemOS summary exposes curvature_modulation and use_su2 when active (token-efficient conditional inclusion). The K5 escalation strategy for DEAD_END uses the E₀-native transition field (y* = argmax_y Σ_z v(y→z)) instead of a connectivity heuristic, making escalation consistent with the core theory.

**Evidence**  
- `e0_controller/test_llm_context.py` — 23 tests across 5 classes:
  - `TestCanonEssence` (14): all 11 symbols present in SYSTEM_PROMPT, structural keywords
  - `TestSummaryCurvatureOff` (2): curvature_modulation absent when off
  - `TestSummaryCurvatureOn` (2): curvature_modulation and M_H present when on
  - `TestOverlaySummaryFields` (2): override_confidence and psi_phase in overlay
  - `TestEvidenceBlockOverrides` (3): override count in reflection evidence
- `e0_controller/test_k5_escalation.py` — 9 tests across 5 classes:
  - `TestK5FieldBasedDeadEnd` (3): field-based target selection, strongest outflow wins
  - `TestK5DeadEndRunCompletion` (2): dead-end runs complete via field escalation
  - `TestK5FilteredAndExhaustedUnchanged` (2): non-DEAD_END strategies unchanged
  - `TestK5EqualFieldTiebreak` (1): deterministic tiebreak on equal fields
  - `TestK5CurvatureModulationAffectsEscalation` (1): curvature changes target selection

**Result**  
- SYSTEM_PROMPT covers all 11 E₀ symbols with semantic explanations (~500 tokens)
- Curvature_modulation and M_H per neighbor conditionally included (token-efficient)
- Override_confidence and psi_phase present in overlay summary when hybrid active
- K5 DEAD_END escalation selects strongest-outflow state (v-weighted, not degree-weighted)
- FILTERED (cheapest tension) and EXHAUSTED (least-recently-visited) strategies preserved

**Status**  
✅ Confirmed

---

### C28 — MemOS persistence fidelity for SU(2), curvature, and escalation context

**Claim**  
All controller state relevant to B1 (SU(2)), B2 (curvature modulation), and K5 (escalation strategy) survives the full MemOS snapshot → save → load → restore cycle. `use_su2` is serialized in RuntimeSnapshot.controller_params, `curvature_modulation` is serialized in LandscapeSnapshot, and escalation edges carry `created_by` (dead_end/filtered/exhausted) through persistence.

**Evidence**  
- `e0_controller/test_memory_os.py` — 10 new tests across 3 classes:
  - `TestUseSu2Roundtrip` (4): use_su2=True persists, use_su2=False default, exposure in LLM summary, absent when false
  - `TestCurvatureModulationRoundtrip` (3): curvature_modulation=True persists, default False, snapshot field reflects landscape
  - `TestEscalationEdgeCreatedBy` (3): dead_end created_by stored, roundtrip persistence, created_by in snapshot JSON
- `e0_controller/memory_os.py` — RuntimeSnapshot.controller_params includes use_su2; LandscapeSnapshot.curvature_modulation field; escalation edges store (Δ, R₀, created_by)
- `e0_controller/controller.py` — _escalation_edges changed to Dict[Edge, Tuple[float, float, str]]

**Result**  
- `use_su2=True` survives snapshot → save → load → restore → controller.use_su2 == True
- `curvature_modulation=True` survives snapshot → save → load → restore → landscape.curvature_modulation == True
- Escalation edge `created_by` survives full roundtrip, defaults to "unknown" for legacy data
- `summarize_for_llm` exposes `use_su2` in runtime section when active (token-efficient)
- Backward compatible: old snapshots without these fields restore gracefully with defaults

**Status**  
✅ Confirmed

---

### C29 — B4 Self-Tuning Meta-Layer (field-derived thresholds, feedback loop, cross-run memory, perturbation sensitivity)

**Claim**  
The E₀ controller can be self-tuned via a four-layer meta-system:
1. **B4.1 Meta-Layer:** Field-derived thresholds replace ad-hoc constants. ParameterSensitivity identifies which controller parameters (alpha, recent_k, etc.) most affect run quality.
2. **B4.2 Feedback Loop:** A closed run→diagnose→adjust→verify cycle with quality score Q ∈ [0,1] drives iterative parameter improvement.
3. **B4.3 Cross-Run Memory:** TuningMemory accumulates quality trends, recurring issues, and parameter drift across runs, with MemOS persistence.
4. **B4.4 True Sensitivity:** Perturbation-based ∂Q/∂θ via finite differences provides empirical gradient for parameter proposals.

**Evidence**  
- `e0_controller/test_self_tuning.py` — 87 tests across 25 classes
- `e0_controller/self_tuning.py` — ~1200 lines, 13 sections covering all four sub-layers
- B4.1: `RunFieldSummary`, `DerivedThresholds`, `ParameterSensitivity`, `propose_tuning`, `apply_tuning`, `H_meta` oscillation protection
- B4.2: `quality_score`, `tuning_cycle`, `tune` (multi-cycle with landscape reset)
- B4.3: `TuningSnapshot`, `TuningMemory`, `save_tuning_memory`, `load_tuning_memory`, `tune_with_memory`
- B4.4: `perturbation_sensitivity`, `propose_tuning_empirical`

**Result**  
- **Q formula verified:** Q = 0.4·goal + 0.25·τ_eff + 0.15·progress − 0.1·loop − 0.1·esc, clamped to [0,1]
- **DerivedThresholds:** Eliminate ad-hoc constants by computing thresholds from RunFieldSummary (mean tension, max R, etc.)
- **ParameterSensitivity:** Correctly ranks parameters by ΔQ/default magnitude
- **Oscillation protection:** H_meta guards against back-and-forth parameter toggling
- **Tuning cycle:** Single run→diagnose→adjust→verify completes; landscape correctly reset between cycles
- **Multi-cycle convergence:** Q improves or stabilizes within 5 cycles; tune() returns best-Q controller
- **TuningMemory:** trend, recurring_issues, parameter_drift computed from snapshot history
- **Serialization:** JSON round-trip preserves all fields; MemOS persistence save/load verified
- **tune_with_memory:** Integrates TuningMemory suggestions into tuning cycle
- **Perturbation ∂Q/∂θ:** Finite differences correctly identify sensitive parameters (alpha, recent_k)
- **propose_tuning_empirical:** Selects adjustments aligned with gradient sign; step size proportional to |gradient|

**Status**  
✅ Confirmed

---

### C30 — Session Orchestrator provides automatic persistence without controller coupling

**Claim**  
A thin Session layer wraps the E₀ controller with automatic MemOS persistence. The controller has zero persistence awareness. Session manages: create → run → save (context + run record + tuning memory). Session.resume() restores landscape, historization, controller params, and tuning memory from disk. Multiple runs accumulate within and across sessions. **Extended in C37:** `Session.iterate()` adds multi-run iterative control with residual tension tracking and inter-iteration reflection (see C37).

**Evidence**  
- `e0_controller/test_session.py` — 13 tests across 3 classes
  - `TestSessionLifecycle` (7): creation, run result, context saved, run record saved, canon refs, controller kwargs, multi-run append
  - `TestSessionResume` (4): resume restores controller, historization persists, runs accumulate, nonexistent raises
  - `TestSessionTuningMemory` (2): tuning memory saved, tuning memory survives resume
- `e0_controller/session.py` — Session class, SessionResult dataclass
- `e0_controller/demo_session_persist.py` — live end-to-end validation (greedy-trap + resume)

**Result**  
- `Session(id, landscape, execute_fn)` creates fresh session, auto-loads tuning memory
- `session.run(start, goal)` delegates to controller, auto-saves context + run record + tuning memory
- `Session.resume(id, execute_fn)` restores full state from disk: landscape, historization, controller params, tuning memory
- `session.recent_runs(limit)` retrieves run history from disk
- Resumed sessions accumulate run records correctly (run_0001, run_0002, …)
- Historization from prior runs persists into resumed session (resistance shifts visible)
- Controller kwargs (alpha, hybrid_mode, hybrid_goals, etc.) survive round-trip
- Canon refs persist through save/resume cycle
- Live demo verified: 3 files on disk (sessions/, runs/, tuning/), resume produces `resumed=True`

**Status**  
✅ Confirmed

---

### C31 — Real-world Beipackzettel landscape validates geometry-dependent amplitude trap

**Claim**  
A real-world pharmacological domain (Ibuprofen package insert) mapped to an E₀ landscape exhibits the same geometry-dependent behavior observed in synthetic benchmarks: `goal_reaching` geometry reliably finds the therapeutic goal state, while `simple` geometry gets trapped in high-branching side-effect states due to amplitude mass accumulation (∑Ψ bias toward states with more outgoing edges).

**Evidence**  
- `e0_controller/test_beipackzettel.py` — 20 tests:
  - Landscape structure validation (16 states, 23 edges, delta/resistance ranges)
  - Goal-reaching geometry finds GESUND in 3 steps
  - Simple geometry loops through MAGEN_REIZUNG (amplitude mass trap)
  - Greedy takes dose escalation path (IBU_400→IBU_800→BESSERUNG→GESUND)
  - ASS interaction scenario with goal_reaching finds safe path
- `e0_controller/demo_beipackzettel.py` — 3-scenario live demonstration
- `docs/MEMO_AMPLITUDE_MASS_TRAP.md` — mechanism documentation

**Result**  
- First real-world data pipeline in E₀: Beipackzettel text → states/edges → landscape → controller → evaluation
- Amplitude mass trap is not a synthetic artifact — it appears in naturally structured domains
- The trap mechanism: states with more outgoing edges contribute more Ψ-terms under simple geometry → higher I(a) → controller is drawn toward high-branching states regardless of goal direction
- goal_reaching geometry suppresses this by weighting paths that reach the goal

**Status**  
✅ Confirmed

---

### C32 — Amplitude mass trap is structural, not parameter-dependent (non-circular validation)

**Claim**  
The amplitude mass trap (C31) persists when landscape parameters (Δ, R₀) are generated by a mock LLM from pharmacological text, without any knowledge of which parameter values produce the desired demonstration outcome. This breaks the circularity concern that hand-tuned parameters trivially produce the observed geometry difference.

**Evidence**  
- `e0_controller/test_beipackzettel_noncircular.py` — 11 tests across 3 classes:
  - `TestNonCircularLandscapeBuild` (4): LLM-derived landscape has correct size, edges, and plausible Δ/R₀ ranges
  - `TestNonCircularGeometryDifference` (4): goal_reaching finds goal, simple does not, greedy succeeds via longer path, hybrid override present
  - `TestSessionGeometryWarning` (3): Session.run() emits UserWarning when goal set with non-goal_reaching geometry
- `e0_controller/session.py` — geometry mismatch warning in `Session.run()`
- `docs/MEMO_AMPLITUDE_MASS_TRAP.md` — circularity caveat and resolution documented

**Result**  
- Mock LLM generates Δ/R₀ from pharmacological plausibility (e.g., side effects get high R₀, therapeutic transitions get low Δ) — no parameter fitting
- The geometry difference persists: goal_reaching finds GESUND, simple does not
- Session.run() now warns when a goal is set but geometry is not `goal_reaching`
- Finding: the amplitude mass trap is a topological property (depends on graph structure, not parameter values)

**Status**  
✅ Confirmed

---

### C33 — ProvenanceLog provides gapless evidence chain from input to evaluation

**Claim**  
A structured 6-stage evidence chain (Input → LLM Call → Proposal → Landscape → Run → Evaluation) records every step from raw text to final assessment, ensuring no link in the inference chain is undocumented or lost.

**Evidence**  
- `e0_controller/provenance.py` — `ProvenanceLog` dataclass with `InputRecord`, `LLMCallRecord`, `ProposalRecord`, `LandscapeRecord`, `RunRecord`, `EvaluationRecord`
- `e0_controller/test_provenance.py` — 28 tests across 11 classes:
  - `TestInputRecord` (4): SHA-256 hashing, metadata, format
  - `TestLLMCallRecord` (4): prompt/response/model/timing capture
  - `TestProposalRecord` (1): state/edge proposal extraction
  - `TestLandscapeRecord` (2): S_eff matrix, reachability
  - `TestRunRecord` (2): path/override/config recording
  - `TestEvaluationRecord` (1): findings dict capture
  - `TestSerialization` (3): JSON round-trip, save/load, empty log
  - `TestChainCompleteness` (4): chain_complete() logic, chain_summary()
  - `TestAdapterProvenance` (3): transparent call wrapping in E0LLMAdapter
  - `TestSessionProvenance` (2): auto run-recording in Session
  - `TestEndToEndProvenance` (2): full pipeline mock, chain verification
- `e0_controller/llm_adapter.py` — auto-wraps `call_fn` via `provenance.wrap_call_fn()`
- `e0_controller/session.py` — auto-records runs with full controller config

**Result**  
- All 6 stages independently testable and JSON-serializable
- `wrap_call_fn()` intercepts LLM calls transparently — no adapter code changes needed
- Session auto-records goal, geometry, hybrid_mode, alpha, confidence_threshold
- `chain_complete()` returns True only when all 6 stages have ≥ 1 record each
- JSON round-trip preserves all fields including SHA-256 hashes and timestamps

**Status**  
✅ Confirmed

---

### C34 — Live LLM provenance validates end-to-end evidence chain with real API

**Claim**  
The ProvenanceLog (C33) captures a complete, verifiable evidence chain when run against a real LLM (gpt-5.4-mini), not just mocks. The resulting provenance log can be serialized, reloaded, and inspected to prove every decision step.

**Evidence**  
- `e0_controller/live_test_llm.py :: TestLiveProvenanceBeipackzettel` — 9 tests:
  - `test_provenance_chain_complete`: all 6 stages populated
  - `test_provenance_input_record`: SHA-256 of raw Beipackzettel text, correct metadata
  - `test_provenance_llm_calls`: ≥ 2 calls (build_landscape + transitions), model/timing recorded
  - `test_provenance_proposal`: correct state/edge counts from LLM-generated landscape
  - `test_provenance_landscape`: S_eff matrix well-formed, goal reachable
  - `test_provenance_runs`: 2 runs (goal_reaching + simple), paths recorded
  - `test_provenance_evaluation`: evaluation findings present
  - `test_provenance_serialization`: JSON save/load round-trip preserves all fields
  - `test_provenance_geometry_difference`: goal_reaching shorter, simple detours via side effects
- `provenance/beipackzettel_live.json` — saved provenance log (gitignored, regenerable)

**Result**  
- 10 real LLM calls recorded (1 build_landscape @ 6.8s, 9 transitions @ ~1.6s each)
- 8 states, 10 edges, all generated by LLM from pharmacological text
- goal_reaching path: 3 steps (KOPFSCHMERZ→IBU_EINNAHME→SCHMERZLINDERUNG→GESUND)
- simple path: 6 steps, 2 overrides (detour: NEBENWIRKUNG→MAGENBESCHWERDEN→DOSIS_ANPASSUNG→ARZT→GESUND)
- Both geometries reach GESUND, but path topology differs significantly
- Full JSON provenance log serializable and reloadable

**Status**  
✅ Confirmed

---

### C35 — EZB-Zinsentscheidung cross-domain validation (Domäne 2)

**Claim**  
The E₀ structural primitives correctly model macroeconomic monetary policy (ECB rate decisions) and the controller exhibits domain-appropriate behavior across three structurally distinct scenarios: inflation control, recession recovery, and stagflation escape.  The amplitude mass trap is confirmed as a cross-domain structural phenomenon.

**Evidence**  
- `e0_controller/demo_ezb_zinsentscheidung.py` — 16 edges, 11 states, 3 scenarios
- `e0_controller/test_ezb_zinsentscheidung.py` — 33 tests across 10 classes:
  - `TestEZBLandscapeStructure` (7): edge/state count, cycle existence, single-exit validation
  - `TestStagflationGordianTrap` (5): 3 exits, isolated trap, R₀ ≥ 0.70, burden comparison, worst-option ordering
  - `TestInflationScenario` (4): goal_reaching reaches PREISSTABILITAET, path includes ZINS_ERHOEHUNG, avoids STAGFLATION, ≤ 4 steps
  - `TestRezessionMultiGoal` (3): reaches WACHSTUM, avoids STAGFLATION, first step = ZINS_SENKUNG
  - `TestStagflationScenario` (3): escapes trap, higher burden + more/equal steps vs inflation
  - `TestGeometryDifference` (1): both geometries reach goal from REZESSION
  - `TestCycleDetection` (2): max_cycles terminates, historization shifts tension
  - `TestNonCircularEZBLandscape` (6): mock LLM landscape with 19 edges (incl. INFL→STAG)
  - `TestNonCircularAmplitudeMassTrap` (4): **proves the trap**: controller cycles with amplitude overlay, GREEDY escapes (graph IS navigable), demo landscape avoids trap
- Domain contrast vs. Beipackzettel (Domäne 1):
  - Cycles (boom-bust feedback loops) — Beipackzettel has none
  - Multi-goal (Preisstabilität + Wachstum) — Beipackzettel has single goal
  - Gordian topology (Stagflation: all 3 exits R₀ ≥ 0.70) — Beipackzettel has mild branching
  - Amplitude mass trap confirmed cross-domain: mock LLM landscape with INFL→STAG triggers same structural phenomenon

**Key finding: Amplitude Mass Trap is domain-invariant**  
When a high-connectivity node (STAGFLATION: 3 exits) is reachable, its path families produce constructive interference that overwhelms the direct shorter path.  The controller cycles: IH→STAG→ZS→W→IH→…  
This is the SAME structural phenomenon observed in Beipackzettel (NEBENWIRKUNG node).  
Resolution: topology surgery (remove the problematic edge) or the `path_count_imbalance` detector (implemented: `OverlayReport.path_count_imbalance`, reflection mass\_trap\_suspect trigger, self-tuning horizon inversion). See `test_mass_trap_detector.py` (25 tests).

**Result**  
- Inflation scenario: INFL→ZE→IS→PS (3 steps, 0 overrides, burden=0.455)
- Rezession scenario: REZ→ZS→KE→W (3 steps, 0 overrides, burden=0.535)
- Stagflation scenario: STAG→ZE→IS→PS (3 steps, 1 override, burden=0.745)
- Override at STAGFLATION: greedy picks ZINS_SENKUNG (lowest S_eff), goal_reaching overrides to ZINS_ERHOEHUNG (Volcker path to PREISSTABILITAET)

**Status**  
✅ Confirmed

---

### C36 — Structural Reflection: landscape-level diagnostics and rebuild

**Claim**  
When parameter tuning reaches a plateau (quality stable despite active tuning), chronic issues persist across runs, or parameters drift to bounds, the system detects this as a structural problem requiring landscape restructuring — not further parameter adjustment. A diagnostic package identifies dead states, loop states, chronic issues, and parameter saturation. The LLM adapter can rebuild the landscape topology using this diagnostic as context.

**Evidence**  
- `e0_controller/test_reflection.py` — 21 new tests across 5 classes:
  - `TestStructuralTriggers` (7): plateau triggers structural, chronic loop triggers structural, param bound triggers structural, no tuning_memory skips structural, too few entries skips, quality takes precedence, failure takes precedence
  - `TestStructuralDiagnostic` (6): dead states detected, loop states detected, chronic issues from memory, plateau evidence, parameter bounds hit, empty diagnostic without context
  - `TestReflectStructural` (4): structural report from reflect(), plateau pattern present, dead states in report, format_reflection_report includes structural icon
  - `TestRebuildLandscape` (4): diagnostic in prompt, state normalization, start/goal ensured, scenario_block inclusion
- `e0_controller/reflection.py` — `StructuralDiagnostic` dataclass, `build_structural_diagnostic()`, `_reflect_structural()`, `"structural"` trigger in `should_reflect()` (between quality and opportunity, priority "high")
- `e0_controller/llm_adapter.py` — `REBUILD_LANDSCAPE_PROMPT`, `E0LLMAdapter.rebuild_landscape()` (takes old proposal + diagnostic → restructured proposal)

**Design**  
Three-part minimal-invasive design:
1. **Trigger**: `should_reflect()` accepts optional `tuning_memory` (TuningMemory). If plateau (|trend| < 0.01 with active tuning) OR chronic issues (>50% of recent runs) OR parameter drift to bounds → `ReflectionDecision(type="structural", priority="high")`
2. **Diagnostic**: `build_structural_diagnostic()` analyzes landscape topology (dead states, bidirectional edges) and TuningMemory (chronic issues, plateau evidence, bounds) → `StructuralDiagnostic`
3. **Rebuild**: `E0LLMAdapter.rebuild_landscape()` sends old topology + diagnostic to LLM with explicit instruction to restructure (not tweak). Returns a new `LandscapeProposal`.

Key insight: `build_landscape()` IS already X→X' (landscape restructuring). The gap was the diagnostic bridge: Controller metrics → structured diagnostic → LLM rebuild instruction.

**Result**  
- Trigger priority: failure > quality > **structural** > opportunity
- Dead state detection: landscape states − visited states
- Loop state detection: bidirectional edges in topology
- Diagnostic flows into rebuild prompt with structured context
- No handcoded merge/split/add operations — LLM generates complete new landscape

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

### P3 — Paper 3: Non-Abelian Structure in E₀ (Multi-Axis SU(2) and Curvature Modulation)

**Target**  
Dedicated publication extending the E₀ phase structure from Abelian U(1) to non-Abelian SU(2). Three-stage extension: per-edge rotation axes (B1), geometry-derived su(2) connection (B4), and curvature modulation M_H (B2). Builds on Papers 1–2.

**Foundation**  
- B1 implementation complete (C25): 36 tests, full stack integration
- B2 implementation complete (C26): 35 tests, experimental curvature_modulation switch
- B4 geometry-derived connection: su2_connection() in spinor_connection.py
- Canon Alignment §9 Bridge Items B1–B2
- SU(2) topology reclassification (C23): Gordian override 90% → 0%
- 144 SU(2)-related tests total across 4 test files

**Draft**  
- `docs/E0_PAPER3_NON_ABELIAN_STRUCTURE_v1.md` — 8 sections + 2 appendices
- Abstract, Introduction, SU(2) Transport, Geometric Connection, Curvature Modulation, Numerical Verification, Discussion, Conclusion
- Appendix A: Implementation reference (11 functions, 4 test suites)
- Appendix B: Derived/Empirical/Heuristic classification

**Status:** 🔄 Draft v1.0 written (review and refinement pending)

---

### C37 — Residual Tension Map and Iterative Session Control (Axiom A₀)

**Claim**  
After a controller run, the per-edge residual tension can be mapped to identify hotspots (high unresolved tension on admissible edges), and the decision whether to iterate emerges from this landscape structure rather than being prescribed. If Δ > 0 and a path with finite R exists, "stop now" is structurally unstable (Axiom A₀ applied at the iteration level). The system iterates until tension equilibrium, stagnation, or budget — the iteration count is not an input but an output of the process. Between iterations, reflection fires when structural problems are detected (C37b).

**Evidence**  
- `e0_controller/residual_tension.py` — `ResidualTension`, `ResidualTensionMap`, `IterationVerdict`, `compute_residual_map()`, `should_continue()`, `snapshot_tensions()`, `format_residual_map()`
- `e0_controller/session.py` — `Session.iterate()`, `IterationResult` dataclass, `_inter_iteration_reflect()`
- `e0_controller/test_residual_tension.py` — 31 tests across 6 classes:
  - `TestSnapshotTensions` (3): pre-run snapshot captures all edges, s_eff values, zero delta
  - `TestComputeResidualMap` (8): visited/unvisited edges, delta computation, hotspot identification, resolved count, iteration tracking
  - `TestShouldContinue` (9): hotspot → CONTINUE, no hotspot → equilibrium STOP, stagnation detection (Δ < 0.02), budget exhaustion (max_iterations), threshold sensitivity, should_reflect on stagnation
  - `TestSessionIterate` (5): single-iteration equilibrium, multi-iteration with hotspots, max_iterations budget, tension_threshold parameter, historization carries across iterations
  - `TestFormatResidualMap` (3): key info present, hotspot display, equilibrium message
  - `TestIterateReflection` (5; C37b): reflections list length = iterations, failure reflection on unreachable goal, clean equilibrium no reflection, failure_fn triggers reflection, _inter_iteration_reflect builds evaluation

**Result**  
- `snapshot_tensions()` captures pre-run baseline; `compute_residual_map()` computes post-run deltas
- Hotspots: edges with s_eff > hotspot_threshold (default 0.5) and admissible (not yet resolved)
- `should_continue()` returns `IterationVerdict` with 4 stopping conditions:
  - `CONTINUE` (hotspots remain)
  - `EQUILIBRIUM` (max_s_eff < tension_threshold, default 0.1)
  - `STAGNATION` (Δ max_s_eff < stagnation_delta, default 0.02)
  - `BUDGET` (iteration ≥ max_iterations)
- `Session.iterate()` loops: run → compute_residual_map → should_continue → (reflect) → repeat
- Iteration count is emergent: burnout live demo produced exactly 2 iterations
- C37b: `_inter_iteration_reflect()` fires between iterations; produces `ReflectionReport` on failure/quality triggers; `IterationResult.reflections` list has one entry per iteration
- `format_residual_map()` produces human-readable hotspot/equilibrium summary

**Status**  
✅ Confirmed

---

### C38 — E0Envelope + TransportRegime: Typed Structural Configuration

**Claim**  
The E₀ controller configuration is captured in a frozen, serializable `E0Envelope` dataclass. The polymorphic `use_su2` parameter (False/True/"geometric") is replaced by a typed `TransportRegime` enum (U1, SU2_MINIMAL, SU2_GEOMETRIC). The envelope provides backward-compatible controller instantiation (`to_controller_kwargs()`), full JSON round-trip (`to_dict()`/`from_dict()`), extraction from a live controller (`from_controller()`), and a typed `controller.transport` property. The envelope is immutable (frozen) and hashable.

**Evidence**  
- `e0_controller/envelope.py` — `E0Envelope` dataclass, `transport_to_use_su2()`, `use_su2_to_transport()` bridge functions
- `e0_controller/primitives.py` — `TransportRegime` enum
- `e0_controller/controller.py` — `Controller.transport` property
- `e0_controller/test_envelope.py` — 48 tests across 10 classes:
  - `TestTransportRegime` (5): enum values, identity, string conversion
  - `TestTransportBridge` (6): transport→use_su2 and use_su2→transport round-trip for all 3 regimes
  - `TestEnvelopeDefaults` (5): default mode, geometry, horizon, transport, goals
  - `TestEnvelopeToKwargs` (8): backward-compatible kwargs for all modes, geometries, and transport values
  - `TestEnvelopeSerialization` (6): to_dict/from_dict round-trip, custom values, frozen goals survive
  - `TestEnvelopeFromController` (5): extraction from live controller, all fields match
  - `TestControllerTransportProperty` (4): typed property returns correct TransportRegime
  - `TestEnvelopeImmutability` (3): frozen, hashable, equal envelopes hash same
  - `TestEnvelopeSummary` (4): human-readable summary, all key fields present
  - `TestEnvelopeIntegration` (2): Session accepts envelope, controller runs correctly with envelope

**Result**  
- `TransportRegime.U1`, `.SU2_MINIMAL`, `.SU2_GEOMETRIC` replace boolean/string `use_su2`
- `to_controller_kwargs()` produces the exact dict `E0Controller.__init__(**kwargs)` expects
- `to_dict()`/`from_dict()` survive JSON serialization (including frozenset goals → sorted list → frozenset)
- `from_controller()` extracts envelope from a live controller instance
- `controller.transport` property returns `TransportRegime` from the internal `use_su2` value
- `E0Envelope` is frozen (`@dataclass(frozen=True)`) and hashable
- Backward compatibility: all 1483 existing tests pass without modification

**Status**  
✅ Confirmed

---

### C39 — Resonator-Controller Integration

**Claim**  
The resonator kernel (cycle detection, coherence measurement, resonance classification from explore_resonator.py) is connected to the controller’s amplitude overlay through a lightweight integration module (resonator.py). A `resonator_modulation` switch on `E0Controller` enables resonance-aware intensity modification: cyclic actions receive a bounded boost factor ∈ [1.0, 2.0] proportional to their cycle coherence R_coh, while acyclic domains and non-cyclic actions are unaffected. Probabilities remain normalized and intensities stay non-negative under the modification.

**Evidence**  
- `e0_controller/resonator.py` — `detect_cycles()`, `cycle_coherence()`, `resonance_map()`, `build_resonance_modifier()`, `ResonanceInfo`
- `e0_controller/controller.py` — `resonator_modulation` parameter, `_compute_overlay()` modifier injection
- `e0_controller/amplitude_overlay.py` — `intensity_modifier` parameter in `analyze_controller_state()`
- `e0_controller/test_resonator_integration.py` — 37 tests across 7 classes:
  - `TestCycleDetection` (8): triangle finds cycle, cycle start/end, acyclic empty, diamond no cycle, two-cycle, max_length constraints (3)
  - `TestCycleCoherence` (5): positive R_coh on triangle, bounded, broken cycle → 0, single node → 0, high n_cycles
  - `TestResonanceMap` (6): cyclic action mapped, non-cyclic excluded, acyclic empty, factor bounded [1,2], info fields, threshold filtering
  - `TestIntensityModifier` (4): boost cyclic, leave non-cyclic unchanged, unknown action unchanged, linear scaling
  - `TestControllerIntegration` (6): accepts flag, default False, overlay differs, full run, hybrid override, _compute_overlay
  - `TestBackwardCompatibility` (3): off = no modifier, identical overlays, acyclic unaffected
  - `TestEdgeCases` (5): single edge, self-loop, probabilities sum to 1, intensities ≥ 0, Gordian probabilities valid

**Result**  
- `detect_cycles()` finds simple cycles of length ≤ max_length through a given state via DFS
- `cycle_coherence()` computes R_coh from multi-pass Ψ accumulation along the cycle
- `resonance_map()` builds action → ResonanceInfo mapping with factor = 1 + min(R_coh, 1) for actions entering cycles (factor ∈ [1.0, 2.0])
- `build_resonance_modifier()` returns a callable `(action, I) → I_modified` for overlay integration
- Controller’s `_compute_overlay()` injects modifier when `resonator_modulation=True`
- On acyclic domains (diamond, linear): zero cycles detected, empty resonance map, modifier is identity — overlay identical to baseline
- Hybrid mode + resonator_modulation: end-to-end run completes correctly on Gordian-with-cycle
- Backward compatible: `resonator_modulation=False` (default) produces identical behavior to pre-C39 code

**Status**  
✅ Confirmed

---

### C40 — Graduated Overlap Functional (M_H from Ontodynamics §3.4)

**Claim**  
The topological modulation parameter M_H is implemented as a graduated overlap functional, derived from the Ontodynamics canon primitive: “Connections possess degree. Overlap is graduated, not binary. Stability requires non-zero overlap.” (§3.4). Unlike the prior holonomy-κ approach (C26, which measures the same geometry as Θ and is therefore redundant), M_H now measures directed 2-hop triangle support — how well each edge is structurally backed by bypass paths. This is a genuinely new observable, non-redundant with Θ, and produces non-trivial modulation only on domains with genuine bypass structure.

The graduated overlap is computed as:
- T(x,y) = {z : x→z ∈ E, z→y ∈ E, z ∉ {x,y}} (forward-directed 2-hop support set)
- overlap(x→y) = Σ_{z ∈ T} √(v(x,z) · v(z,y)) (geometric mean of support leg strengths)
- M_H = (overlap + ε) / (max_overlap + ε), with ε = max_overlap · floor/(1−floor)
- If max_overlap = 0 → M_H = 1.0 everywhere (simple domains, correct neutral behavior)

**Evidence**  
- `e0_controller/overlap.py` — `triangle_support()`, `edge_overlap()`, `overlap_map()`, `OverlapInfo`
- `e0_controller/landscape.py` — `overlap_modulation` flag, `_get_overlap_M_H()`, `_build_overlap_cache()`
- `e0_controller/__init__.py` — exports: `triangle_support`, `edge_overlap`, `overlap_map`, `OverlapInfo`
- `docs/E0_MH_ADJUDICATION_RESEARCH_NOTE_v1.md` — conceptual analysis, Q1–Q4, 45-domain survey
- `e0_controller/test_overlap.py` — 43 tests across 7 classes:
  - `TestTriangleSupport` (8): directed 2-hop support on 6 domain types, self-loop exclusion
  - `TestEdgeOverlap` (6): geometric mean formula, zero/positive, asymmetric ordering, non-negativity
  - `TestOverlapMap` (10): full M_H normalization, ε-floor, linear/cycle neutral, supported=1.0, unsupported=floor, all edges present
  - `TestLandscapeOverlapModulation` (7): flag default, on differentiates, v_mod ≤ v_base, linear/cycle no-op
  - `TestFalsificationDomain` (3): two paths identical in Δ/R/S_eff/ω differ only in overlap — M_H breaks the tie; v_mod/v_base = M_H
  - `TestBackwardCompatibility` (4): default off, curvature+overlap coexist, empty landscape, single edge
  - `TestEdgeCases` (5): self-loop excluded, v=0 support → 0 overlap, multiple supports additive, floor=0 edge case

**Result**  
- **45-domain survey**: >35 domains have zero directed triangle support → M_H trivially 1.0 (correct: overlap modulation is inactive on simple topologies)
- **Falsification domain** (overlap differentiator): edges S→A and S→B have identical Δ, R, S_eff, ω — only structural difference is bypass S→C→B. Without modulation: v(S→A) = v(S→B). With modulation: v(S→B) > v(S→A) — supported edge wins.
- **Non-redundancy**: Overlap measures structural support (bypass paths), not phase geometry (Θ). Domains exist where Θ is identical but overlap differs, and vice versa.
- **Formula verification**: v_mod/v_base = M_H to 8 decimal places for all tested edges
- **Two independent modulations**: `curvature_modulation` (C26, holonomy-κ) and `overlap_modulation` (C40, graduated overlap) can be enabled simultaneously without interaction
- **Circular dependency resolved**: overlap cache built from base v with both modulations temporarily disabled; Helmholtz cache invalidated after cache build
- **Label retirement**: “Topological invariant” label retired in favor of “graduated overlap functional” — the original label came from Canon Alignment, not from the Canon itself

**Status**  
✅ Confirmed

---

### C26 — M_H topological invariant modulates transition field via curvature (B2)

**Claim**  
The topological modulation factor M_H(x,y) = 1/(1 + κ(x,y)), where κ is the mean absolute face holonomy through edge x→y, correctly modulates the transition field v(x,y) = Δ · M_H · exp(−S_eff). When `curvature_modulation=False` (default), M_H = 1 and all existing behavior is preserved. When enabled, high-curvature edges are damped, the full downstream chain (Helmholtz → Φ → v_rot → ω → Θ → holonomy) responds to the modulation, and the circular dependency (transition_field → M_H → κ → ω → v_rot → transition_field) is resolved by computing κ from base (unmodulated) ω.

**Evidence**  
- `e0_controller/test_curvature_modulation.py` — 35 tests across 11 classes:
  - `TestEdgeCurvature` (6 tests): κ=0 for line graph and symmetric triangles; κ>0 for asymmetric triangle; κ non-negative everywhere; tetrahedron all edges curved; diamond shows κ variation
  - `TestMHFactor` (5 tests): no curvature → M_H=1; curvature → M_H<1; M_H ∈ (0,1]; formula 1/(1+κ) verified; symmetric → unit M_H
  - `TestCurvatureModulationSwitch` (2 tests): default False; explicit True
  - `TestTransitionFieldModulation` (6 tests): off unchanged; on differs from off; v_mod ≤ v_base; line graph unaffected; symmetric triangle unaffected; missing edge returns 0
  - `TestCacheConsistency` (3 tests): cache built once; entries for all edges; Helmholtz Φ differs (diamond topology)
  - `TestDownstreamEffects` (3 tests): ω changes; v_rot changes; holonomy changes
  - `TestAdmissibleNeighbors` (1 test): same admissible set with or without modulation
  - `TestSpecFormula` (1 test): v = Δ · M_H · coherence(S_eff) verified to 12 decimal places
  - `TestRepr` (1 test): repr works with modulation enabled
  - `TestEdgeCases` (4 tests): single edge no crash; empty landscape; self-loop ignored; tetrahedron lower v
  - `TestQuantitativeBehavior` (3 tests): κ magnitude vs ω; M_H moderate damping (0.1, 1.0); v_mod/v_base = M_H (8 places)
- `e0_controller/connection.py` — `edge_curvature(L, x, y)` and `M_H_factor(L, x, y)` functions
- `e0_controller/landscape.py` — `curvature_modulation=False` parameter on `Landscape`, `_get_M_H()` and `_build_M_H_cache()` methods, modified `transition_field()`

**Result**  
- **Default off (1082 existing tests unaffected)**: curvature_modulation=False → M_H=1 → zero behavioral change
- **Flat geometry**: Line graphs (no triangles) and symmetric triangles (ω=0) produce κ=0, M_H=1 — modulation is a no-op
- **Curved geometry**: Asymmetric triangle κ > 0, M_H ∈ (0.3, 1.0), v_mod < v_base
- **Downstream propagation**: Helmholtz Φ, v_rot, ω, and holonomy all respond to modulation
- **Admissibility preserved**: M_H only scales v, never removes neighbors
- **Circular dependency resolved**: M_H cache built from base ω (curvature_modulation temporarily disabled during cache build), then re-enabled with stale Helmholtz cache invalidated
- **Helmholtz cache key**: Extended from (edge_count, τ) to (edge_count, τ, curvature_modulation)
- **Formula verified**: v_mod/v_base = M_H to 8 decimal places for all edges
- **Canon Alignment §9 B2**: "M_H als topologischer Invariant" — now implemented with experimental switch

**Design note:**  
Alternative formula M_H = exp(−κ) provides smoother decay but same asymptotic limits. Current choice 1/(1+κ) is algebraically simpler and provides moderate damping for typical curvature values.

**Status**  
✅ Confirmed

---

### C41 — Stochastic Exploration Policy (Born warmup → exploit)

**Claim**  
Born sampling (P ∝ I) provides stochastic exploration that discovers paths argmax misses. An ExplorationPolicy encodes the explore→exploit transition: Born warmup for N steps, then switch to argmax. This is integrated into Session.iterate() as an optional parameter. When no policy is provided, behavior is identical to previous versions.

**Evidence**  
- `e0_controller/exploration_policy.py` — `ExplorationPolicy`, `PolicyDecision`, `born_warmup()`, `fixed()`
- `e0_controller/test_exploration_policy.py` — 42 tests across 10 classes
- `e0_controller/session.py` — `Session.iterate(exploration_policy=...)` integration

**Result**  
- Born warmup builds broader historization traces → exploit phase benefits
- Convergence policy enables early switch when residual tension is low
- Mode restoration ensures Session state is clean after iterate()
- Zero behavioral change without policy (backward compatible)

**Status**  
✅ Confirmed

---

### B4-S1 — Landscape Mutation API (Bridge 4 Structural Reflexivity, Stufe 1)

**Claim**  
The Landscape class supports structural self-modification through safe mutation primitives: `remove_edge`, `adjust_base_resistance`, `adjust_delta`, `has_edge`, and `would_orphan`. These are the mechanical foundation for Bridge 4 (Structural Reflexivity) — the system can modify its own transition structure. Mutations correctly invalidate modulation caches, preserve historization traces, and propagate to tension/transition field computations.

**Evidence**  
- `e0_controller/landscape.py` — 5 new methods + `_invalidate_caches()` helper
- `e0_controller/test_landscape_mutation.py` — 56 tests across 10 classes
- `docs/E0_BRIDGE4_STRUCTURAL_REFLEXIVITY_NOTE_v0.md` — concept note

**Result**  
- `remove_edge` deletes from _delta/_R0, raises KeyError if absent, does NOT delete states
- `adjust_base_resistance`/`adjust_delta` return old value for undo, validate ≥ 0
- `would_orphan` predicts isolation before commit — safety check for structural mutations
- All mutations invalidate _M_H_cache, _overlap_cache, _phi_cache
- Historization survives mutations (traces on Historization object, independent of Landscape edges)
- Undo via caller-saved old values + re-adjust/re-add — no rollback infrastructure needed yet

**Status**  
✅ Confirmed

---

### B4-S2 — Structural Mutation Infrastructure (Bridge 4, Stufe 2)

**Claim**  
The E₀ Framework provides a complete data layer for structural self-modification: typed mutation intents (`StructuralMutation`), an admissibility gate (`is_admissible`), mechanical apply/revert on the Landscape, a proposal engine that translates `StructuralDiagnostic` findings into concrete mutations, and a bounded history log with oscillation protection (`MutationHistory`). This infrastructure makes self-modification one admissible transition among others (AGI Blueprint §5), constrained by locality, topology safety, and historization.

**Evidence**  
- `e0_controller/structural_mutation.py` — full module: `MutationType`, `StructuralMutation`, `MutationRecord`, `MutationHistory`, `is_admissible()`, `apply/revert_structural_mutation()`, `propose_structural_mutations()`
- `e0_controller/test_structural_mutation.py` — 66 tests across 10 classes:
  - `TestStructuralMutation` (5): dataclass fields, edge property, describe() for all 4 types
  - `TestMutationType` (4): enum values match expected strings
  - `TestAdmissibility` (12): remove existing/nonexistent/orphan, add new/existing/negative/missing, adjust R₀/Δ existing/nonexistent/negative
  - `TestApplyMutation` (8): apply adjust_R₀/Δ, remove, add, inadmissible raises, stores old values, preserves other edges
  - `TestRevertMutation` (6): revert adjust_R₀/Δ, remove→re-add, add→remove, field restoration, idempotent re-add
  - `TestProposalLogic` (8): dead→Δ boost, loop→R₀ increase, empty diagnostic, admissibility filter, bounded per cycle, motivation present, oscillation filter, loop dedup
  - `TestMutationRecord` (4): delta_quality computed, None if no after, default not accepted, negative delta
  - `TestMutationHistory` (10): append, bounded capacity, oscillation detection (same-type, add↔remove, remove↔add), counts, per-edge isolation
  - `TestHistorySerialization` (4): empty roundtrip, with records, max_records preserved, add_edge fields preserved
  - `TestEndToEnd` (5): propose→apply→accept, propose→apply→revert, loop fix, history tracking, multi-cycle oscillation protection

**Result**  
- Admissibility gate blocks: orphaning states, negative values, nonexistent edges, duplicate adds
- Oscillation protection covers: same-type ping-pong (R₀ up/down) AND cross-type cycling (add/remove)
- Proposals from `StructuralDiagnostic`: dead states → Δ boost on incoming edges; loop states → R₀ increase on loop-back edges (deduplicated per pair)
- Bounded to 3 mutations per cycle (configurable via `_MAX_MUTATIONS_PER_CYCLE`)
- Full serialization roundtrip for MemOS persistence
- Apply fills `old_value` for undo; revert uses stored values mechanically

**Status**  
✅ Confirmed

---

### B4-S3 — Structural Tuning Cycle + Session.iterate() Hook (Bridge 4, Stufe 3)

**Claim**  
The E₀ Framework integrates structural self-modification into the existing tuning and iteration infrastructure. A `structural_tuning_cycle()` executes the full feedback loop (Run → Diagnose → Propose → Apply → Re-run → Verify → Accept/Revert), and `Session.iterate()` calls it as Step 6 when structural reflection triggers. This completes the escalation chain: parametric tuning exhausted → quality plateau / chronic issues / parameter bounds → structural mutation. The cycle records outcomes in `MutationHistory` for cross-run learning and oscillation protection.

**Evidence**  
- `e0_controller/structural_mutation.py` — added: `StructuralTuningCycleResult` dataclass, `structural_tuning_cycle()` function
- `e0_controller/session.py` — modified: `Session.__init__`/`resume` carry `MutationHistory`, `iterate()` Step 6 structural hook, `IterationResult.structural_results` field
- `e0_controller/test_structural_tuning_cycle.py` — 42 tests across 10 classes:
  - `TestStructuralTuningCycleResult` (4): dataclass defaults, quality, mutation_records, revert
  - `TestCycleNoProposals` (4): healthy landscape → no mutations, quality computed
  - `TestCycleWithDeadStates` (5): dead state D → ADJUST_DELTA proposals generated and applied
  - `TestCycleWithLoops` (4): S↔A 2-cycle → ADJUST_RESISTANCE proposals generated
  - `TestCycleRevert` (4): quality regression → revert restores landscape, flags set correctly
  - `TestCycleHistoryIntegration` (5): MutationHistory updated, oscillation blocked on repeat, records have quality
  - `TestSessionStructuralHook` (6): iterate() fires structural_tuning_cycle on structural reflection, skips on quality reflection
  - `TestIterationResultFields` (3): structural_results default empty, explicit, backward compat
  - `TestSessionMutationHistory` (3): fresh session carries empty history, mutable
  - `TestEndToEndStructural` (4): full loop cycle, multi-cycle accumulation, dead state landscape modification, no-goal

**Result**  
- Escalation chain verified: structural_tuning_cycle only invoked when reflection returns type="structural"
- Quality gating: Q_after < Q_before → all mutations reverted in reverse order
- MutationHistory accumulates across cycles, preventing oscillation (same-type and cross-type)
- Session.iterate() remains backward compatible (structural_results defaults to empty list)
- Test warning cleanup: all 45 `hybrid_geometry='simple'` UserWarnings suppressed via `pyproject.toml` filterwarnings

**Status**  
✅ Confirmed

---

### B4-S4a — Identity Invariant (Bridge 4, Stufe 4a)

**Claim**  
After any structural self-modification, three invariants must hold for the system to remain "the same" E₀ system:

1. **Goal reachability**: If a goal is set, it must remain reachable from the start state. A mutation that severs the goal-path destroys the task-topology identity.
2. **A₀ compliance**: Every state reachable from start (except the goal itself) must have at least one admissible outgoing transition. A mutation creating a reachable dead-end makes Axiom A₀ ("non-transition is structurally unstable") unenforceable at that state.
3. **Historization continuity**: Mutations touch only `_delta` and `_R0`, never historization traces (δ_H, U/F-traces, τ). This is an architectural guarantee, not a runtime check.

These three invariants are checked post-mutation in `structural_tuning_cycle()` (Phase 4b). If any invariant is violated, all applied mutations are reverted before re-running.

**Evidence**
- `e0_controller/structural_mutation.py` — added: `IdentityViolation` enum, `IdentityCheck` dataclass, `_reachable_states()` BFS helper, `check_identity_invariant()` function, `check_identity_after_mutation()` prospective check, integration into `structural_tuning_cycle()` Phase 4b, `identity_check` field in `StructuralTuningCycleResult`
- `e0_controller/test_structural_mutation.py` — 25 tests across 5 classes (11–15):
  - `TestIdentityCheck` (4): dataclass basics, bool semantics, multiple violations
  - `TestReachableStates` (5): BFS from start/middle/end, loop domain, diamond
  - `TestCheckIdentityInvariant` (7): goal reachable/unreachable, dead end, goal-terminal exemption, no-goal, both violations
  - `TestCheckIdentityAfterMutation` (5): safe mutation, landscape restore, inadmissible, goal-severing, dead-end creating
  - `TestIdentityInTuningCycle` (4): clean cycle, loop-fix, no-proposals, field exists

**Result**
- `check_identity_invariant()` correctly identifies goal-unreachable + dead-end violations
- `check_identity_after_mutation()` speculatively applies, checks, and always reverts
- Goal-severing mutations are detected before re-running (avoids wasted controller runs)
- Dead-end-creating mutations are rejected with `IdentityViolation.DEAD_END_CREATED`
- Historization continuity is guaranteed by architecture (mutations never touch δ_H)
- `structural_tuning_cycle()` Phase 4b: reverts mutations and records in history when invariant fails
- `StructuralTuningCycleResult.identity_check` is None when no mutations applied, `IdentityCheck` otherwise

**Canon basis**
- AGI Blueprint §5: "self-modification becomes one admissible transition among others"
- E₀ Canonical Reference A₀: Non-transition is structurally unstable — must remain enforceable throughout reachable subgraph after mutation
- Structural Deep Review v1 §6.1: three-part invariant analysis

**Status**  
✅ Confirmed

---

### C42 — 4-Layer Model (Historization → Inscription → Inertia → Mass)

**Claim**  
Historization accumulates traces that produce measurable quantities at four layers: (1) Historization (raw trace storage), (2) Inscription (`trace_load` = effective count with ρ-decay), (3) Inertia (`inertia_factor` = functional dampening from load + quality), (4) Mass (emergent behavioral weight). The core formula is:

```
I(e) = 1 − α · (m/(m+μ)) · (1−|q|)
```

where m = trace_load, q = trace_quality. High load + high quality → low inertia (confident). High load + contradictory quality → high inertia (confused). This is the first quantitative operationalization of "artificial mass" from Ontodynamics.

**Evidence**  
- `e0_controller/historization.py` — `trace_load()`, `trace_quality()`, `inertia_factor()`
- `e0_controller/landscape.py` — `inertia_modulation` flag
- `e0_controller/test_qualitative_mass.py` — 37 tests
- `docs/E0_HISTORISIERUNG_ALS_MASSE_v1.md` — concept note

**Result**  
- `trace_load` correctly accounts for ρ-decay (ρ=0.9 default)
- `trace_quality` bounded in [−1, +1], converges with dominant outcome
- `inertia_factor` monotonic: I→0 as m→∞ with |q|→1 (confident); I→1 as m→∞ with q→0 (confused)
- Backward-compat aliases preserved: `mass()`, `quality()`, `mass_modulation_factor()`, `mass_modulation`

**Status**  
✅ Confirmed

---

### C43 — Self-Graph (Selbstunterscheidung)

**Claim**  
E0 can learn its own operational structure by maintaining a dedicated Landscape instance representing its decision cycle (amplitude → born → realization → historization → inertia → transition_field → amplitude, plus curvature/overlap modulations). After each controller decision, `self_historize()` records which components contributed and whether the outcome was good. Over time, `component_quality()` reveals which components are effective (high |q|) and which are confused (q ≈ 0).

**Canon basis:** Ontodynamics begins with Selbstunterscheidung — a process that distinguishes itself from itself before distinguishing from anything else. The Self-Graph implements this: E0's first domain is E0.

**Evidence**  
- `e0_controller/self_graph.py` — `SelfGraph`, `active_components()`, topology constants
- `e0_controller/test_self_graph.py` — 47 tests across 9 classes
- `e0_controller/controller.py` — self_graph hook in `cycle()` after historization

**Result**  
- 8 nodes + 8 edges represent E0's complete operational cycle
- ρ=1.0 (cumulative — self-knowledge does not decay, unlike domain edges)
- Only edges where both endpoints are active get updated (attribution precision)
- Core components always active; modulation components conditional on landscape flags
- `snapshot()` exports for MemOS persistence; `summary()` for human diagnosis

**Status**  
✅ Confirmed

---

### C44 — Bootstrapper (structured spec → Landscape)

**Claim**  
A structured domain spec (from LLM or manual input) can be converted into an initialized Landscape with pre-seeded traces. The `confidence` parameter on each edge controls how much E0 trusts the initial estimates: confidence=1.0 preserves exact U/F ratios; confidence=0.0 forces balanced U=F (quality=0, maximum caution). This solves the cold-start problem: E0 gets initial structure from LLM but remains epistemically cautious about unverified edges.

**Evidence**  
- `e0_controller/bootstrapper.py` — `bootstrap_landscape()`, `validate_spec()`, `_apply_confidence()`, `_inject_traces()`
- `e0_controller/test_bootstrapper.py` — 41 tests across 7 classes

**Result**  
- Validates: no empty graph, no negative weights, no self-loops, edges reference known nodes
- Confidence=1.0 preserves exact U/F ratios; confidence=0.0 forces U=F (quality=0)
- Bootstrapped landscapes get `inertia_modulation=True` by default
- Unknown nodes in edges are skipped (lenient parsing for LLM output)
- End-to-end pipeline: spec → validate → bootstrap → controller runs successfully

**Status**  
✅ Confirmed

---

### C45 — LLM Adapter v2 (propose_domain_graph)

**Claim**  
The LLM can be prompted to propose a complete domain graph in bootstrapper-compatible format. `propose_domain_graph(description)` sends a structured prompt that teaches the LLM E0's graph semantics (Δ = structural difference, R₀ = base resistance, confidence per edge) and returns a parsed spec dict. `propose_and_bootstrap(description)` chains proposal + bootstrapping into a ready Landscape.

**Evidence**  
- `e0_controller/llm_adapter.py` — `PROPOSE_DOMAIN_GRAPH_PROMPT`, `propose_domain_graph()`, `propose_and_bootstrap()`
- `e0_controller/test_llm_adapter.py` — 17 new tests (12 propose + 5 pipeline), 63 total

**Result**  
- Prompt teaches LLM: nodes, edges with from/to/delta/resistance/initial_U/initial_F/confidence
- Parser normalizes names (UPPER_SNAKE_CASE), clamps values, skips self-loops and unknown-node edges
- `propose_and_bootstrap()` → fully initialized Landscape in one call
- Error handling: invalid JSON → LLMResponseError with raw_response

**Status**  
✅ Confirmed

---

### C46 — Mode Controller (LEARN / EXECUTE / COMBINATION)

**Claim**  
E0 can automatically determine its operating mode based on accumulated experience. If most edges have insufficient trace data (`trace_load < μ`), E0 is in LEARN mode (needs LLM). If all edges are well-explored, E0 switches to EXECUTE mode (autonomous). In between: COMBINATION mode (call LLM only for unexplored edges). The μ threshold reuses the same parameter from `inertia_factor()` — consistent semantics.

**Evidence**  
- `e0_controller/mode_controller.py` — `OperatingMode`, `ModeController`, `current_mode()`, `edge_needs_llm()`, `neighbors_needing_llm()`, `coverage()`, `summary()`
- `e0_controller/test_mode_controller.py` — 36 tests across 9 classes
- `e0_controller/controller.py` — `self.mode_controller` attribute

**Result**  
- Empty landscape → LEARN (no data)
- All edges explored → EXECUTE (autonomous)
- ≥learn_ratio fraction unexplored → LEARN; else → COMBINATION
- `neighbors_needing_llm(state)` returns successor states that still need LLM exploration
- Coverage ratio correctly tracks total/explored/unexplored edge counts

**Status**  
✅ Confirmed

---

### C47 — Dual Reflection (self-graph diagnosis + meta-control)

**Claim**  
The reflection system can diagnose not only domain-level problems but also E0's own component health. `diagnose_self_graph()` classifies each of E0's 8 components as healthy/confused/harmful/insufficient_data based on self-graph traces. `reflect_dual()` cross-references domain failures with self-graph issues for targeted meta-actions. Modulation components (curvature, overlap) with persistently negative quality become deactivation candidates — core components are flagged but never auto-deactivated.

**Architecture level:** This completes the three-level self-knowledge hierarchy from the Bootstrap Architecture (§6): Level 1 = structural self-image (C43 self-graph topology), Level 2 = operational reflection (C47 component diagnosis), Level 3 = meta-control (C47 deactivation recommendations).

**Evidence**  
- `e0_controller/dual_reflection.py` — `diagnose_self_graph()`, `ComponentAssessment`, `SelfGraphDiagnosis`, `DualReflectionReport`, `reflect_dual()`, `_cross_reference()`, `format_dual_report()`
- `e0_controller/test_dual_reflection.py` — 36 tests across 7 classes

**Result**  
- Fresh self-graph: all components insufficient_data (no traces yet)
- After successes: all assessed components healthy
- After failures only: harmful components, modulation → deactivation candidates
- Mixed outcomes: confused status, investigation meta-actions generated
- Cross-reference: domain flags "controller" + self-graph shows born is harmful → "prioritize born investigation"
- Restructuring recommended + deactivation candidates → "deactivate before restructuring"
- Core components never in deactivation_candidates (only modulation can be disabled)
- `format_dual_report()` produces complete human-readable output with mode info, domain reflection, self-graph diagnosis, and meta-actions

**Status**  
✅ Confirmed

---

### Bootstrap Architecture (C43–C47) — Complete

**Claim**  
The E0+LLM Bootstrap Architecture is fully implemented. The five components work together:
1. **C43 Self-Graph**: E0 learns its own structure (Selbstunterscheidung)
2. **C44 Bootstrapper**: Structured specs → initialized Landscapes with confidence-scaled traces
3. **C45 LLM Adapter v2**: LLM proposes domain graphs in bootstrapper format
4. **C46 Mode Controller**: Automatic LEARN/EXECUTE/COMBINATION switching based on trace coverage
5. **C47 Dual Reflection**: Combined domain + self-graph diagnosis with meta-control

The dependency chain `C43 → C47` and `C44 → C45 → C46 → C47` is fully resolved. E0 can now: receive domain knowledge from an LLM, initialize a cautious Landscape, run autonomously once sufficient experience accumulates, and diagnose both domain problems and its own component health.

**Evidence**  
- 5 modules: `self_graph.py`, `bootstrapper.py`, `llm_adapter.py` (extended), `mode_controller.py`, `dual_reflection.py`
- 5 test files: 197 tests total (47 + 41 + 17 + 36 + 36, plus 16 in llm_adapter existing)
- Architecture doc: `docs/E0_LLM_BOOTSTRAP_ARCHITECTURE_v1.md`

**Status**  
✅ Confirmed

---

When a new test family is added, update both:

1. the inventory-level registry (`E0_TEST_REGISTRY_v1.md`)
2. this claim-level registry (`E0_TEST_REGISTRY_v2.md`)

The v1 file answers:
> *What tests exist?*

The v2 file answers:
> *What do those tests establish?*

---

_End of document._