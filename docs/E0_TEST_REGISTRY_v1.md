# E₀ Test Registry v1

> Central reference for all tests in the E₀ Framework.
> **Last verified:** 2026-03-28 — **1431 tests** (1431 unittest via discover; 41 live LLM in `live_test_llm.py`; 0 failures)

---

## Overview Table

| # | File | Tests | Runner | Domain | Status |
|---|------|------:|--------|--------|--------|
| 1 | `test_amplitude_overlay.py` | 125 | unittest | Ψ-paths, interference, geometries | ✅ GREEN |
| 2 | `test_llm_adapter.py` | 47 | unittest | LLM parsing, normalization, mocks | ✅ GREEN |
| 3 | `test_gordian_trap.py` | 44 | unittest | Holonomy, Gordian trap, multi-goal | ✅ GREEN |
| 4 | `test_evaluation.py` | 42 | unittest | Run/semantic/scenario evaluation | ✅ GREEN |
| 5 | `test_phase2_minidomain.py` | 38 | unittest | Φ, ω, holonomy, Ψ = e^(−S+iΘ) | ✅ GREEN |
| 6 | `test_reflection.py` | 36 | unittest | Reflection triggers, LLM fallback | ✅ GREEN |
| 7 | `test_invoice.py` | 33 | unittest | Invoice domain end-to-end | ✅ GREEN |
| 8 | `live_test_llm.py` | 41 | explicit | Live LLM + Provenance (requires API key, separated from discover) | ⚠ LIVE |
| 9 | `test_g5_edge_cases.py` | 55 | unittest | G5 robustness, 5 families A–E, SU(2) | ✅ GREEN |
| 10 | `test_memory_os.py` | 38 | unittest | Persistence, save/load round-trip, SU(2)/curvature/escalation | ✅ GREEN |
| 11 | `test_graph_validation.py` | 24 | unittest | Reachability, traps, quality score | ✅ GREEN |
| 12 | `test_topology_classification.py` | 30 | unittest | 380-graph scan, override prediction, SU(2) | ✅ GREEN |
| 13 | `test_phase2_invoice.py` | 18 | unittest | Invoice phase-layer validation | ✅ GREEN |
| 14 | `test_waypoint.py` | 17 | unittest | Goal-with-continuations, H4 | ✅ GREEN |
| 15 | `test_scaling.py` | 14 | unittest | O(n) complexity, n ≤ 500 | ✅ GREEN |
| 16 | `test_spinor.py` | 71 | unittest | SU(2) lift, geometric coupling, 720° | ✅ GREEN |
| 17 | `test_greedy_trap.py` | 4 | unittest | Greedy-trap walkthrough | ✅ GREEN |
| 18 | `test_resonator.py` | 73 | unittest | Resonator kernel, R1-R4, multi-loop, coupled | ✅ GREEN |
| 19 | `test_omega_uniqueness.py` | 27 | unittest | ω uniqueness, 5 alternatives falsified | ✅ GREEN |
| 20 | `test_historization_gordian.py` | 61 | unittest | Historization × Gordian, non-Gordian topologies | ✅ GREEN |
| 21 | `test_born_regime.py` | 44 | unittest | Born regime B1-B5, uniqueness U1-U3 | ✅ GREEN |
| 22 | `test_reflection_hybrid.py` | 42 | unittest | Reflection hybrid metrics R_coh, Θ, drift | ✅ GREEN |
| 23 | `test_dynamic_horizon.py` | 45 | unittest | Dynamic horizons, topology_adaptive, capped | ✅ GREEN |
| 24 | `test_confidence_override.py` | 31 | unittest | Confidence-weighted override gating F1-F12 | ✅ GREEN |
| 25 | `test_memos_geometry.py` | 34 | unittest | MemOS geometry persistence G1-G10 | ✅ GREEN |
| 26 | `test_born_sampling.py` | 31 | unittest | Born sampling vs argmax, ADR-0007 H1-H11 | ✅ GREEN |
| 27 | `test_minidomain.py` | — | — | (empty — tests migrated to test_phase2_minidomain) | — |
| 28 | `test_multi_axis_su2.py` | 36 | unittest | Per-edge SU(2) axes, non-commutativity, multi-axis interference, controller integration | ✅ GREEN |
| 29 | `test_curvature_modulation.py` | 35 | unittest | M_H topological invariant, edge curvature, curvature modulation switch, downstream effects | ✅ GREEN |
| 30 | `test_llm_context.py` | 23 | unittest | LLM canon essence, summary enrichment, overlay fields | ✅ GREEN |
| 31 | `test_k5_escalation.py` | 9 | unittest | K5 field-based escalation, dead-end/filtered/exhausted strategies | ✅ GREEN |
| 32 | `test_self_tuning.py` | 87 | unittest | B4 self-tuning: field summary, derived thresholds, quality score, tuning cycle, tuning memory, perturbation sensitivity | ✅ GREEN |
| 33 | `test_session.py` | 13 | unittest | Session orchestrator lifecycle, resume, tuning memory persistence | ✅ GREEN |
| 34 | `test_beipackzettel.py` | 20 | unittest | Real-world Beipackzettel landscape, amplitude mass trap, goal_reaching vs simple | ✅ GREEN |
| 35 | `test_beipackzettel_noncircular.py` | 11 | unittest | Non-circular LLM validation, geometry warning, structural amplitude trap | ✅ GREEN |
| 36 | `test_provenance.py` | 28 | unittest | ProvenanceLog 6-stage evidence chain, serialization, adapter/session integration | ✅ GREEN |
| 37 | `test_ezb_zinsentscheidung.py` | 33 | unittest | EZB-Zinsentscheidung real-world domain, Gordian trap, amplitude mass trap, non-circular mock LLM | ✅ GREEN |
| 38 | `test_mass_trap_detector.py` | 25 | unittest | Mass trap detection: path_count_imbalance, reflection trigger, self-tuning horizon inversion | ✅ GREEN |
| 39 | `test_envelope.py` | 48 | unittest | E0Envelope + TransportRegime: typed config, serialization, bridge, controller integration | ✅ GREEN |
| 40 | `test_burnout_composite.py` | 39 | unittest | Burnout Domäne 3: fragments, mock landscape, envelope presets, full demo run (greedy + hybrid), topology | ✅ GREEN |

---

## Per-File Details

### 1. test_amplitude_overlay.py — 125 tests

**What it tests:** Path enumeration with bounded horizons, Ψ-summation and intensity I = |Ψ|², probability normalization, deterministic vs. amplitude choice, dead-end and single-neighbor edge cases, destructive/constructive interference, multiple domain topologies (Mini-Domain, Diamond, Waypoint), all four geometry variants (simple, prefix, first_arrival, goal_reaching), hybrid controller override behavior.

**Key findings:**
- Probabilities always sum to ≈ 1.0 across all domains and geometries
- I(a) = |Ψ(a)|² holds precisely
- Amplitude choice avoids dead-end traps that greedy selects
- Destructive interference at START in diamond domain suppresses certain paths
- All geometries preserve admissibility constraints

---

### 2. test_llm_adapter.py — 47 tests

**What it tests:** JSON parsing from LLM output (plain, markdown-fenced, whitespace-tolerant), state name normalization (UPPER_SNAKE_CASE), delta/resistance extraction with clamping, state proposal generation, transition result parsing, landscape materialization from proposals, task map generation, snapshot comparison.

**Key findings:**
- Markdown fence stripping works with/without language tag
- Normalization: hyphens → underscores, multi-underscores → single
- Delta/resistance clamped to [0, 1]
- Duplicate state names (post-normalization) deduplicated
- LLMResponseError raised with raw_response on parse failure

---

### 3. test_gordian_trap.py — 44 tests

**What it tests:** Holonomy formula ΔΘ = ½[Σv_loop − Σv_short], destructive interference between A-family paths, B-path dominance at path level, greedy behavior (picks A1), goal-reaching geometry (picks B1 at h ≥ 5), hybrid override A1 → B1, simple geometry preference, historization stability, multi-goal coherence.

**Key findings:**
- ΔΘ_predicted matches ΔΘ_actual to 6 decimals
- cos(ΔΘ) < −0.9 (near-π phase opposition)
- Interference factor < 0.1 (strong destructive)
- h = 3: A1 wins (loop invisible); h = 5: B1 wins (loop visible → destructive)
- P(B1) > 0.9 at h = 5 with goal_reaching geometry
- Multi-goal {G1, G2, G3}: A1 always wins (most coverage)

---

### 4. test_evaluation.py — 42 tests

**What it tests:** Repeated cycle counting, rating assignment (A–F), run evaluation metrics (efficiency, goal reach, loop penalty), semantic coverage scoring, hard failure detection (graph quality, goal reachability, semantic gaps), scenario evaluation composition, hybrid mode metrics (override rate, agreement rate), multi-scenario summary generation.

**Key findings:**
- Ratings correlate with efficiency and cycle patterns
- Hard failures (F) override all other metrics
- Semantic coverage correctly identifies missing outputs
- Zero-step paths handled gracefully

---

### 5. test_phase2_minidomain.py — 38 tests

**What it tests:** Potential Φ(x) computation, Helmholtz decomposition v = v_grad + v_rot, ω antisymmetry ω(x,y) = −ω(y,x), holonomy on closed cycles, path phase Θ accumulation, Ψ = exp(−S + iΘ) formula verification.

**Key findings:**
- Φ correctly captures sink vs. source hierarchy
- v_grad ⊥ v_rot (dot product ≈ 0)
- ω antisymmetric for ALL state pairs, not just edges
- 2-edge cycles: trivial holonomy (exact cancellation); 3+ edges: may be nonzero
- |Ψ| = exp(−S) and arg(Ψ) = Θ to 10+ decimal places

---

### 6. test_reflection.py — 36 tests

**What it tests:** Reflection decision triggers (failure, quality, opportunity), evidence block construction for LLM, result sampling and truncation, JSON parsing of LLM reflection responses, multi-scenario summary formatting.

**Key findings:**
- Hard failures trigger "failure" reflection with high priority
- Goal-not-reached triggers only if progress_ratio < 0.5
- Repeated cycles > 3 with loop_penalty > 0.2 trigger reflection
- Opportunity type only when rating ≥ B and coverage high
- LLM reflection has fallback to rule-based on call failure

---

### 7. test_invoice.py — 33 tests

**What it tests:** Invoice domain as realistic end-to-end validation — graph construction, controller run, evaluation, hybrid mode, memory persistence, full pipeline from START to COMPLETED.

**Key findings:**
- Invoice domain (almost-DAG) successfully runs through entire E₀ pipeline
- Happy path shorter than recovery alternatives
- Hybrid mode makes minor overrides in this low-holonomy domain

---

### 8. test_llm_integration.py — 32 tests ⚠

**What it tests:** Live LLM landscape proposal, transition execution (SUCCESS/FAILURE/PARTIAL), confidence extraction, delta/resistance estimation, full controller run, semantic evaluation, hybrid mode with real LLM, multi-goal handling.

**Key findings:**
- LLM proposes connected graph with ≥ 4 states, goal always reachable
- Graph quality score typically > 0.3
- Confidence clamped to [0, 1]
- Full runs reach goal ≥ 85% with LLM
- Multi-goal runs path to at least one goal

**Note:** Skipped when `OPENAI_API_KEY` not set. Results may vary due to LLM non-determinism.

---

### 9. test_g5_edge_cases.py — 55 tests

**What it tests:** G5 multi-goal robustness across 5 stress families (A–E), large goal sets (|G| = 16, 32), unreachable goal stress, SU(2) winner stability/structural invariants/selectivity:
- **Family A** — Winner stability as |G| grows from 1 → 5
- **Family B** — Unreachable, weak, and noisy goal injection
- **Family C** — Competing goals (generalist vs. specialist actions)
- **Family D** — Low-δ rescue path threshold crossover
- **Family E** — Selectivity (entropy, top-1 gap) vs. goal count

**Key findings:**
- A: Winner A stable across all |G|, selectivity peaks at |G| = 2–3
- B: Unreachable goals = safe; weak/noisy goals with coherent paths correctly shift winner
- C: Single-goal → specialists win; multi-goal → generalist C wins (P = 0.665)
- D: Rescue from δ = 0.01 (low S = Δ·R → high amplitude); crossover at δ ∈ [0.8, 1.5]
- E: Entropy ↓, gap ↑ with more goals — anti-saturation (no F1 triggered)
- **No failure signatures F1–F4 triggered**

---

### 10. test_memory_os.py — 38 tests

**What it tests:** Edge serialization, context save/load round-trip, landscape/controller restoration from snapshot, E0MemoryOS summarize_for_llm, historization persistence across sessions, behavior change from restored memory, hybrid controller snapshots, session listing, use_su2 roundtrip, curvature_modulation roundtrip, escalation edge created_by persistence.

**Key findings:**
- Edge key format: "SOURCE→TARGET"
- Round-trip: save → load → content identical
- Restored landscape passes integrity checks
- Historization U/F traces survive persistence exactly
- Avoided edge (high F-trace) skipped in restored runs
- Overlay attached in snapshots when hybrid

---

### 11. test_graph_validation.py — 24 tests

**What it tests:** Goal reachability (BFS), shortest path (happy path), recovery edge identification, trap detection (dead-end non-goal), trivial loop detection (2-cycles, self-loops), composite graph quality score.

**Key findings:**
- Quality score = reachable (0.5) + path_length (0.2) + coverage (0.15) + traps (0.1) + loops (0.05)
- Traps correctly identified (no outgoing edges, not goal)
- 2-cycle B↔D detected in trivial_loops
- Recovery edges are out-of-happy-path but contribute to reachability

---

### 12. test_topology_classification.py — 30 tests

**What it tests:** 380-graph parametric scan across triangle/diamond/gordian-lite topologies — override rate prediction from path family count and phase opposition. SU(2) phase halving effect on topology classification.

**Key findings:**
- Triangle (1 family) → 0% overrides
- Diamond (2 families) → ~37% overrides
- Gordian-lite (2 families + phase opposition) → ~93% overrides
- Prefix = first_arrival (100% agreement)
- Simple ≈ prefix (97.6% agreement)
- G5 exclusive disagreements in ~30% of graphs
- Phase opposition (ΔΘ > π/4) is strong predictor of override

---

### 13. test_phase2_invoice.py — 18 tests

**What it tests:** Invoice domain as secondary validation of Phase 2 layer — Φ computations, ω antisymmetry, holonomy over HUMAN_REVIEW cycle, happy path vs. recovery path interference, phase consistency.

**Key findings:**
- Invoice domain mostly DAG → weak holonomy overall
- Happy path has stronger Ψ than recovery path
- Two-edge cycles verify holonomy = 0
- All edges have finite, non-NaN ω and v_rot

---

### 14. test_waypoint.py — 17 tests

**What it tests:** Goal-with-continuations domain (goal G has outgoing edges), post-goal loop G→Y1→G, path enumeration across geometries, interference when goal is not terminal.

**Key findings:**
- Prefix geometry includes post-goal paths → more paths than first_arrival
- First_arrival stops at goal; prefix/simple continue
- Intensity values genuinely differ between geometries (> 0.1% deviation)
- Post-goal loop effects visible at horizon ≥ 4
- Validates H4 from summation geometry program

---

### 15. test_scaling.py — 14 tests

**What it tests:** Landscape construction at n = 50, 100, 500. Goal reachability, controller run time complexity (greedy), step count growth, amplitude overlay bounded computation, hybrid mode scalability.

**Key findings:**
- Run time subquadratic (500/50 ratio < 50×)
- Step count stays O(n) (< 3n for chains)
- Overlay with h = 3 completes in < 2 seconds at n = 500
- Path count bounded by horizon, not graph size
- No exponential blowup in bounded-horizon analysis

---

### 16. test_spinor.py — 71 tests

**What it tests:** SU(2) lift of the scalar U(1) phase layer — Pauli algebra (anticommutation, hermiticity, tracelessness), 720° periodicity (exp(−iπσ)=−𝕀, exp(−i2πσ)=+𝕀), single-path magnitude consistency (‖Ψ_SU2‖ = |Ψ_U1|), phase halving effect (Θ→Θ/2), winner divergence (U(1) vs SU(2) on Gordian Trap), non-commutativity (multi-axis transport), graph holonomy (loop transport, size dependence), structural invariants (empty paths, inadmissible paths, reference spinor independence), **geometric coupling** (Phase 4b: vorticity-derived axis from Helmholtz decomposition), three-theory natural domain validation (Diamond, Leaf, Triangle-Dense, Gordian-lite), performance scaling.

**Key findings:**
- **Phase halving:** SU(2) uses exp(−iΘ/2·σ_z)|↑⟩, not exp(iΘ). Relative phase ΔΘ/2 ≈ π/2 (orthogonal) vs ΔΘ ≈ π (destructive in U(1))
- **Winner flips on Gordian Trap:** U(1) I(A1) = 0.018 (B1 wins), SU(2) I(A1) = 0.838 (A1 wins)
- **Geometric coupling (Phase 4b):** su(2) connection vector A⃗ = (A₁, A₂, A₃) from local Helmholtz geometry. A₁ = vorticity gradient (≤92.9% off-axis on Gordian), A₂ = face holonomy (non-zero on triangles). Geometric SU(2) intensity sits between U(1) and minimal SU(2). Gordian A+loop: 55.3% divergence geo vs min. Triangle domain: 16.7% divergence.
- 720° periodicity: exact for all axes, including arbitrary unit vectors
- Non-commutativity: ‖[U(σ_z), U(σ_x)]‖ > 0 on multi-axis domain
- All transport matrices verified SU(2): det = 1, U†U = 𝕀
- Antisymmetry A⃗(y,x) = −A⃗(x,y) and transport reversal U(y,x) = U(x,y)† verified

---

### 18. test_resonator.py — 73 tests

**What it tests:** Minimal 3-node resonator kernel (A→B→C→A + leakage C→OUT), R1–R4 stability criteria, classification (DECAY/METASTABLE/RESONATOR), loop path families, measurement protocol, historization-driven regime transitions, SU(2) holonomy on loop, three-theory separation. **Multi-loop extension:** 4-node ring, nested loops (constructive interference factor ≈2.0), coupled resonators (kernel isolation + bridge coupling), multi-loop SU(2).

**Key findings:**
- M2 (balanced)/H0 and M3 (reinforced)/H0: genuine RESONATOR (R_coh > 0.3, leakage non-dominant)
- M1 (transient): METASTABLE→RESONATOR transition via historization (≥10 rounds)
- C1 (acyclic): DECAY — no loop = no resonance
- C2 (dephased): DECAY — high R kills coherence (I_coh < 0.001)
- Loop holonomy ∈ SU(2), three-theory intensities diverge on multi-cycle paths
- Phase doubles linearly: θ(2 cycles) = 2·θ(1 cycle)
- R_coh = I_coh/I_inc verified, measurement protocol self-consistent
- Historization boosts M1 I_coh by 20× but can destabilize M2/M3 (over-amplification)

---

### 19. test_omega_uniqueness.py — 27 tests

**What it tests:** Numerical falsification of the Uniqueness Conjecture from E0_THETA_ANTISYMMETRY_DERIVATION_v0. Five alternative ω candidates tested against axioms A1 (orientation), A3 (gauge invariance), A4 (reciprocity), P1 (non-degeneracy), P2 (correct interference). Helmholtz orthogonality. Gradient telescoping.

**Key findings:**
- ω_sym = ½(v_rot(x,y) + v_rot(y,x)): fails A1 (orientation) and A4 (reciprocity)
- ω_full = v_rot(x,y): fails A1 (not antisymmetric)
- ω_v = v(x,y): fails A1 (gradient contamination)
- ω_grad = Φ(x)−Φ(y): fails P1 (zero holonomy — degenerate, telescopes on all paths)
- ω_nonlin = sign(d)·d²: fails P2 (R_coh = 1.73 vs 0.35 — wrong interference)
- **Only ω_true = ½(v_rot(x,y) − v_rot(y,x)) survives all axioms**
- Helmholtz orthogonality ⟨v_grad, v_rot⟩_E = 0 verified on Diamond, Asymmetric Triangle, Gordian
- Gradient always path-independent: Σ v_grad = Φ(start) − Φ(end)
- ω_true exactly matches standard connection.omega and reproduces standard wavepath intensity

---

### 20. test_historization_gordian.py — 61 tests

**What it tests:** Formal verification of historization × Gordian trap interaction across 14 test classes: parametric resilience (δ_max, ρ, λ_s, λ_f), FAILURE outcomes (R_eff raise, v reduction), K2 lazy decay recovery (trace decay, R_eff recovery, ΔΘ recovery), clipping saturation (δ_H bounds, R_eff floor), alternating adversarial (A-short/A-loop interleave), recovery from adversarial, holonomy formula invariance under historization (holds for success, failure, mixed, loop), multi-goal × historization, extreme stress (100 A-short, 50 alternating), hybrid multi-cycle (greedy pollution, alternating greedy/hybrid), **non-Gordian topologies** (Triangle, Diamond, Gordian-lite under U(1) and SU(2)), cross-topology invariants.

**Key findings:**
- Interference routing (B1 wins) survives under all tested parameter regimes
- cos(ΔΘ) remains destructive (< 0) even under 100+ adversarial passes
- Holonomy formula ΔΘ = ½[Σv_loop − Σv_short] holds precisely after all historization patterns
- K2 lazy decay recovers R_eff and ΔΘ toward pristine values
- δ_H saturates at ±δ_max, R_eff never reaches zero (structural floor)
- Hybrid controller overrides correctly even after greedy pollution

---

### 21. test_greedy_trap.py — 4 tests

**What it tests:** Greedy-trap walkthrough demonstrating local-burden minimization pitfalls.

**Status:** ✅ GREEN

---

### 30. test_llm_context.py — 23 tests

**What it tests:** LLM SYSTEM_PROMPT canon essence (all 11 E₀ symbols: Δ, R, H, S, C, v, ω, Θ, Ψ, I, M_H), summarize_for_llm curvature_modulation exposure, overlay summary fields (override_confidence, psi_phase), reflection evidence block override count.

**Key findings:**
- Canon essence covers all 11 primitives with semantic descriptions
- Curvature modulation flag conditionally exposed (token-efficient)
- Override confidence and psi_phase present when overlay active
- Evidence block includes override count when overrides occurred

---

### 31. test_k5_escalation.py — 9 tests

**What it tests:** K5 field-based DEAD_END escalation (y* = argmax_y Σ_z v(y→z)), FILTERED and EXHAUSTED strategies unchanged, curvature_modulation effect on escalation target selection.

**Key findings:**
- DEAD_END target = state with strongest total transition field outflow
- Replaces prior max-connectivity heuristic with E₀-native field computation
- Equal-field tiebreak is deterministic
- Curvature modulation changes escalation targets by damping high-curvature edges
- FILTERED (cheapest raw neighbor) and EXHAUSTED (least-recently-visited) unchanged

---

### 32. test_self_tuning.py — 87 tests

**What it tests:** Full B4 self-tuning meta-layer across 25 classes. Covers four sub-layers:
- **B4.1 Meta-Layer:** RunFieldSummary, field_summary_from_run, DerivedThresholds, ParameterSensitivity, propose_tuning, apply_tuning, H_meta oscillation protection
- **B4.2 Feedback Loop:** quality_score Q ∈ [0,1], tuning_cycle (run→diagnose→adjust→verify), tune() multi-cycle with improvement tracking, landscape reset between cycles
- **B4.3 Cross-Run Memory:** TuningSnapshot, TuningMemory (trend, recurring_issues, drift, suggest), serialization round-trip, MemOS persistence bridge (save/load), tune_with_memory integration
- **B4.4 True Sensitivity:** perturbation_sensitivity (∂Q/∂θ via finite differences), propose_tuning_empirical

**Test classes (25):**
- `TestRunFieldSummary` — field summary from landscape metrics
- `TestFieldSummaryFromRun` — field summary from controller trace
- `TestDerivedThresholds` — field-derived vs ad-hoc threshold comparison
- `TestParameterSensitivity` — Q → θ sensitivity analysis
- `TestOscillationProtection` — H_meta oscillation guard
- `TestTuningProposals` — propose_tuning rule-based suggestions
- `TestApplyTuning` — apply proposed changes to controller
- `TestReflectionWithFieldThresholds` — field thresholds in reflection
- `TestQualityScore` — Q formula with weights
- `TestLandscapeReset` — landscape restoration between tuning cycles
- `TestTuningCycle` — single run→diagnose→adjust→verify cycle
- `TestMultiCycleTuning` — multi-cycle tune() convergence
- `TestTuningImprovement` — improvement detected across cycles
- `TestTuningSnapshot` — snapshot dataclass
- `TestTuningMemoryCore` — memory record/retrieve
- `TestQualityTrend` — trend calculation from history
- `TestRecurringIssues` — repeated issue detection
- `TestParameterDrift` — drift measurement
- `TestEffectiveProposals` — drift-aware proposal filtering
- `TestSuggestFromHistory` — suggest() combining all signals
- `TestTuningMemorySerialization` — JSON round-trip
- `TestTuningMemoryPersistence` — save/load to disk
- `TestTuneWithMemory` — tune_with_memory integration
- `TestPerturbationSensitivity` — ∂Q/∂θ finite differences
- `TestProposeTuningEmpirical` — empirical gradient-based proposals

**Key findings:**
- Q = 0.4·goal + 0.25·τ_eff + 0.15·progress − 0.1·loop − 0.1·esc ∈ [0,1]
- DerivedThresholds from field summary eliminate ad-hoc constants
- Multi-cycle tuning converges: Q improves or stabilizes within 5 cycles
- TuningMemory tracks trend, recurring issues, and parameter drift across runs
- Perturbation ∂Q/∂θ correctly identifies sensitive parameters (alpha, recent_k)
- propose_tuning_empirical selects adjustments aligned with gradient sign
- Serialization round-trip preserves all fields exactly

---

### 33. test_session.py — 13 tests

**What it tests:** Session orchestrator lifecycle across 3 classes:
- `TestSessionLifecycle` (7): session creation, run returns SessionResult, context saved, run record saved, canon refs persisted, controller kwargs forwarded, multiple runs append
- `TestSessionResume` (4): resume from disk restores controller, historization survives, run accumulation, nonexistent session raises FileNotFoundError
- `TestSessionTuningMemory` (2): tuning memory saved to disk, tuning memory survives resume

**Key findings:**
- Session wraps controller + MemOS with zero persistence in the controller itself
- Auto-saves context, run record, and tuning memory after each run
- Resume restores landscape, historization, controller params, and tuning memory
- Multiple runs within a session and across resumed sessions accumulate correctly
- Uses tempfile for test isolation — no disk pollution

---

### 23. test_confidence_override.py — 31 tests

**What it tests:** `OverlayReport.override_confidence` (P_best − P_second gap), confidence threshold gating in `select_hybrid()`, `StepResult.override_confidence` field, `RunTrace.metrics()['avg_override_confidence']`, edge cases (single action, equal probabilities, dominant action, 3+ actions), backward compatibility with threshold=0.0, high-threshold blocking across topologies (Gordian, Diamond, Wide), end-to-end threshold sweep monotonicity.

**Key findings:**
- Confidence gap correctly computed as P_best − P_second
- Threshold=0.0 preserves 100% backward compatibility (all prior behavior unchanged)
- On Gordian with goal_reaching geometry, confidence reaches 1.0 (one action has 0 goal-reaching paths)
- Higher threshold → monotonically fewer overrides (sweep verified)
- Diamond topology always reaches goal even when override is blocked

---

### 24. test_memos_geometry.py — 34 tests

**What it tests:** MemOS persistence of hybrid_geometry and confidence_threshold across save/load/restore cycles. All 4 geometry types (prefix, simple, first_arrival, goal_reaching) round-trip correctly. Overlay summary uses correct geometry from controller. Backward compatibility (old sessions without geometry field default to "simple"). Multi-run geometry stability. Diamond and Gordian domain integration.

**Key findings:**
- hybrid_geometry + confidence_threshold now explicitly stored in RuntimeSnapshot.controller_params
- All 4 geometries survive JSON round-trip (save → load → restore)
- summarize_for_llm overlay now passes controller.hybrid_geometry to analyze_controller_state
- Old persisted data (no geometry field) gracefully defaults to "simple" / 0.0
- Geometry stays stable across two save/restore cycles
- Different sessions maintain independent geometry configurations

---

### 26. test_born_sampling.py — 31 tests

**What it tests:** Born sampling (P ∝ I) as alternative realization regime alongside deterministic argmax. Validates ADR-0007 architecture decision: argmax stays default, Born sampling is opt-in. Compares success rates on Gordian, Diamond, and G5 domains across both geometry types. Covers distribution convergence, variance, coherence loss, multi-goal coverage, MemOS round-trip, and StepResult integration.

**Key findings:**
- With goal_reaching geometry, argmax dominates or equals Born sampling on all domains
- With simple geometry on Gordian, both modes struggle; sampling can randomly escape trap
- Born sampling reaches all 3 G5 goals (exploration), argmax deterministically picks 1
- BORN_SAMPLING mode survives MemOS save → load → restore cycle
- Born sampling variance > 0 on multi-path domains (G5), argmax variance = 0

---

### 27. test_minidomain.py — 21 standalone tests

**Runner:** `python e0_controller/test_minidomain.py` (not unittest-based)

**What it tests:** Mini-Domain graph structure, tension formula S = Δ·R, coherence C = exp(−S), historization U/F traces with decay ρ, K2 lazy global decay, 7 landscape core functions, oscillation breaking via revisit penalty α, dead-end escalation, failure/success learning, full runs reaching GOAL, K11 tension filtering (s_max, c_min), K12 escalation type detection.

**Key findings:**
- Oscillation A↔C broken when α = 2.0 (revisit cost crosses threshold)
- Dead-end D produces escalation (no neighbors)
- E→F fails: R rises from 0.5 → 2.0+ (hits δ_max = 3.0)
- E→G succeeds: R falls from 0.5 → 0.35
- Lazy decay: u_eff = ρ^gap × u_last
- All 7 core functions verified correct
- K12 escalation types: DEAD_END, FILTERED, EXHAUSTED, REVISIT

---

### 28. test_multi_axis_su2.py — 36 tests

**Runner:** `python -m unittest e0_controller.test_multi_axis_su2 -v`

**What it tests:** Per-edge SU(2) rotation axes (B1 from Canon Alignment §9). Extends the SU(2) spinor transport from global σ_z to per-edge axis assignment via `axis_fn(L, x, y) → n̂`. Tests across 11 classes: Pauli non-commutativity, tetrahedron domain with orthogonal per-edge axes, edge/path transport with custom axis_fn, holonomy orientation dependence, multi-axis interference vs single-axis, spinor structural invariants, controller/overlay integration (fan graph with multi-path actions), path-order dependence, four-theory comparison (U(1)/σ_z/geometric/multi-axis), and single-path axis-insensitivity control.

**Key findings:**
- Non-commutativity: max|AB−BA| > 0.1 for all Pauli pairs; same-axis commutes (< 1e-12)
- Strongly asymmetric edge parameters needed for non-zero ω (symmetric edges give ω=0 via Helmholtz)
- Multi-axis holonomy dist_to_I = 0.92 vs single-axis 0.05 on tetrahedron triangle
- Multi-axis interference intensity 1.04 vs single-axis 0.82 (diff 0.23) on 3-path family
- Single-path families axis-independent (magnitude-only, 10 decimal places)
- Overlay intensity diff = 0.015 on fan graph with multi-path action
- Four theories all produce distinct intensities on tetrahedron
- axis_fn=None backward-compatible (identical to single-axis, 10 decimal places)

---

### 29. test_curvature_modulation.py — 35 tests

**Runner:** `python -m unittest e0_controller.test_curvature_modulation -v`

**What it tests:** M_H topological invariant (B2 from Canon Alignment §9). Edge curvature κ(x,y) from face holonomies, modulation factor M_H = 1/(1+κ), experimental curvature_modulation switch on Landscape, forward/backward compatibility, cache consistency, downstream effects on Helmholtz/ω/holonomy, and quantitative behavior. Tests across 10 classes with 4 graph topologies (triangle, line, diamond, tetrahedron).

**Key findings:**
- Line graph (no triangles): κ = 0, M_H = 1, v unchanged — correct flat behavior
- Symmetric triangle: ω = 0 → κ = 0 → M_H = 1 → no modulation effect
- Asymmetric triangle: κ > 0, M_H < 1, v_mod < v_base — curvature damps transitions
- v_mod / v_base = M_H holds to 8 decimal places
- curvature_modulation=False (default): zero change from existing behavior (1082 tests unaffected)
- Downstream chain verified: v → Helmholtz → Φ → v_rot → ω → holonomy all change with modulation
- Admissible neighbors unchanged — M_H only scales v, never removes edges
- M_H cache built lazily, used for all subsequent calls
- Circular dependency (transition_field → M_H → κ → ω → v_rot → transition_field) resolved via temporary flag disable during cache build

---

### 34. test_beipackzettel.py — 20 tests

**What it tests:** Real-world Beipackzettel (package insert) landscape for Ibuprofen, mapped to E₀ states and edges. 23 edges, 16 states. Three scenarios: (1) goal_reaching finds GESUND in 3 steps, (2) simple geometry gets trapped in amplitude mass trap through MAGEN_REIZUNG loop, (3) ASS interaction scenario with goal_reaching finds safe path. Tests validate landscape structure, path outcomes, and geometry-dependent behavior.

**Key findings:**
- Amplitude mass trap confirmed: states with more outgoing edges accumulate more Ψ-terms under simple geometry → I(a) biased toward high-branching states
- goal_reaching geometry reliably finds GESUND; simple geometry loops through side-effect states
- Greedy takes dose escalation path (IBU_400→KEINE_WIRKUNG→IBU_800→BESSERUNG→GESUND) — not trapped, but via longer pharmacological route
- Real-world domain validates E₀ geometry distinction beyond synthetic benchmarks

---

### 35. test_beipackzettel_noncircular.py — 11 tests

**What it tests:** Non-circular validation of the amplitude mass trap. Uses mock LLM function that generates pharmacologically plausible Δ/R₀ values from Beipackzettel text without knowledge of what parameter values "work". Three test classes:
- `TestNonCircularLandscapeBuild` (4): landscape size, edges, delta/resistance ranges from LLM-derived values
- `TestNonCircularGeometryDifference` (4): goal_reaching finds goal, simple geometry does not, greedy succeeds (via longer path), hybrid override count ≥ 1
- `TestSessionGeometryWarning` (3): Session.run() emits UserWarning when goal set but geometry≠goal_reaching, no warning when geometry matches, no warning when no goal

**Key findings:**
- Amplitude mass trap is structural (topology-dependent), not parameter-dependent — persists with LLM-derived values
- Validates that the Session geometry warning fires correctly
- Breaks circularity: parameters come from text analysis, not from knowing which values produce the desired demo outcome

---

### 36. test_provenance.py — 28 tests

**What it tests:** Full 6-stage ProvenanceLog evidence chain (Input → LLM Call → Proposal → Landscape → Run → Evaluation). 11 test classes:
- `TestInputRecord` (4): SHA-256 hashing, metadata storage, format validation
- `TestLLMCallRecord` (4): prompt/response/model/timing capture, call recording
- `TestProposalRecord` (1): state/edge proposal extraction
- `TestLandscapeRecord` (2): S_eff matrix, reachability flags
- `TestRunRecord` (2): path/override/controller-config recording
- `TestEvaluationRecord` (1): findings dict capture
- `TestSerialization` (3): JSON round-trip, save/load file I/O, empty log
- `TestChainCompleteness` (4): chain_complete() logic, chain_summary() formatting
- `TestAdapterProvenance` (3): transparent call wrapping in E0LLMAdapter
- `TestSessionProvenance` (2): automatic run recording in Session
- `TestEndToEndProvenance` (2): full pipeline mock, chain completeness verification

**Key findings:**
- ProvenanceLog provides lückenlose (gapless) evidence chain from raw input to evaluation
- All stages independently testable and JSON-serializable
- `wrap_call_fn()` intercepts LLM calls transparently — no adapter code changes needed
- Session auto-records controller config (goal, geometry, hybrid_mode, alpha, etc.)

---

## How to Run

```bash
# Standard unittest suite (1286 tests, no LLM calls, ~10s)
py -3 -m unittest discover -s e0_controller -p "test_*.py" -t .

# Live LLM tests (requires API key, ~22s)
py -3 -m unittest e0_controller.live_test_llm -v

# Single file
py -3 -m unittest e0_controller.test_gordian_trap -v
```

---

## Maintenance Notes

- When adding a new test file: add a row to the **Overview Table** and a **Per-File Details** section.
- Update `Last verified` date and total count after full regression.
- LLM integration tests (`test_llm_integration`) fail without `OPENAI_API_KEY` — not counted as regression failures.
- `test_minidomain.py` runs standalone (21 tests, not discovered by unittest discover).
- `test_beipackzettel_noncircular.py` uses mock LLM — no API key needed.
