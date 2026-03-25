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
- `docs/E0_EVIDENCE_AND_FALSIFICATION_STATUS_v1.md`

**Result**  
Across tested scenarios, `cos(ΔΘ)` remains destructive (< 0), B-path dominance survives, and hybrid routing remains stable.

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
| `test_spinor.py` | C15 |
| `test_resonator.py` | C16 |
| `test_omega_uniqueness.py` | C14 |
| `test_minidomain.py` | base mechanics, historization, K11/K12 |

---

## 5. Open claims with recommended next tests

### O1 — Extreme historization stress

**Target claim**  
C8 under much stronger clipping / distortion regimes.

**Recommended test**  
Stress `δ_max ≫ R₀` and long adversarial replay sequences.

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