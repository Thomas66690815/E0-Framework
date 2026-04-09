# E₀ Test Registry v1

> Central reference for all tests in the E₀ Framework.
> **Last verified:** 2026-03-30 — **2278 tests** (2196 unittest via discover; 41 live LLM in `live_test_llm.py`; 0 failures, 0 warnings)

---

## Overview Table

| # | File | Tests | Runner | Domain | Status |
|---|------|------:|--------|--------|--------|
| 1 | `test_amplitude_overlay.py` | 125 | unittest | Ψ-paths, interference, geometries | ✅ GREEN |
| 2 | `test_llm_adapter.py` | 63 | unittest | LLM parsing, normalization, mocks, domain graph proposal (C45) | ✅ GREEN |
| 3 | `test_gordian_trap.py` | 44 | unittest | Holonomy, Gordian trap, multi-goal | ✅ GREEN |
| 4 | `test_evaluation.py` | 42 | unittest | Run/semantic/scenario evaluation | ✅ GREEN |
| 5 | `test_phase2_minidomain.py` | 38 | unittest | Φ, ω, holonomy, Ψ = e^(−S+iΘ) | ✅ GREEN |
| 6 | `test_reflection.py` | 57 | unittest | Reflection triggers, LLM fallback, structural reflection (C36) | ✅ GREEN |
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
| 27 | `test_minidomain.py` | 21 | standalone | Mini-Domain graph, tension, coherence, historization, K11/K12 | ✅ GREEN |
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
| 41 | `test_residual_tension.py` | 31 | unittest | C37 Residual Tension: snapshot, compute_residual_map, should_continue (4 stopping conditions), Session.iterate(), format, C37b iterate-reflection | ✅ GREEN |
| 42 | `test_resonator_integration.py` | 37 | unittest | C39 Resonator-Controller integration: cycle detection, coherence, resonance map, intensity modifier, controller switch, backward compat | ✅ GREEN |
| 43 | `test_overlap.py` | 43 | unittest | C40 Graduated Overlap: triangle_support, edge_overlap, overlap_map, landscape modulation, falsification domain, backward compat | ✅ GREEN |
| 44 | `test_exploration_policy.py` | 42 | unittest | C41 Stochastic Exploration Policy: PolicyDecision, warmup/fixed/convergence policies, Session.iterate() integration, mode restoration, backward compat | ✅ GREEN |
| 45 | `test_landscape_mutation.py` | 56 | unittest | B4-S1 Landscape Mutation API: remove_edge, adjust_R₀/Δ, has_edge, would_orphan, historization interaction, cache invalidation, undo | ✅ GREEN |
| 46 | `test_structural_mutation.py` | 91 | unittest | B4-S2 Structural Mutation Infrastructure: StructuralMutation, admissibility, apply/revert, propose, MutationHistory oscillation, serialization, end-to-end, Identity Invariant (B4-S4a) | ✅ GREEN |
| 47 | `test_structural_tuning_cycle.py` | 42 | unittest | B4-S3 Structural Tuning Cycle: StructuralTuningCycleResult, cycle no-proposals/dead/loops/revert, MutationHistory integration, Session.iterate() structural hook, IterationResult fields, end-to-end | ✅ GREEN |
| 48 | `test_qualitative_mass.py` | 37 | unittest | C42 4-Layer Model: trace_load, trace_quality, inertia_factor, inertia_modulation, backward-compat aliases | ✅ GREEN |
| 49 | `test_self_graph.py` | 47 | unittest | C43 Self-Graph: topology, self_historize, component quality/load/inertia, snapshot, controller integration | ✅ GREEN |
| 50 | `test_bootstrapper.py` | 41 | unittest | C44 Bootstrapper: validate_spec, bootstrap_landscape, confidence scaling, trace injection, inertia_modulation | ✅ GREEN |
| 51 | `test_mode_controller.py` | 36 | unittest | C46 Mode Controller: OperatingMode, coverage, edge_needs_llm, neighbors_needing_llm, controller integration | ✅ GREEN |
| 52 | `test_dual_reflection.py` | 36 | unittest | C47 Dual Reflection: diagnose_self_graph, component assessment, cross-reference, reflect_dual, meta-control, formatting | ✅ GREEN |
| 53 | `test_canon_loader.py` | 72 | unittest | C48 Canon Loader: canon discovery, JSON loading, node/edge extraction, Bootstrapper conversion, Ontodynamics v1.2 topology, navigation, graph quality | ✅ GREEN |
| 54 | `test_canon_self_bridge.py` | 32 | unittest | C48 Canon ↔ Self-Graph Bridge: process mapping, canon coverage, process status, self-exposition, structural correctness | ✅ GREEN |
| 55 | `test_reflexive_action.py` | 41 | unittest | C49 Reflexive Action: plan/apply, core protection, undo, Session integration, end-to-end with SelfGraph | ✅ GREEN |
| 56 | `test_reflexive_journal.py` | 37 | unittest | C50 Reflexive Journal: record/restore, exposition Section 5, Session integration, end-to-end chain | ✅ GREEN |
| 57 | `test_system_integration.py` | 19 | unittest | C51 System Integration: full pipeline convergence, Selbst-Fundierung, reflexive convergence, direct assembly, edge cases | ✅ GREEN |
| 58 | `test_honest_self_knowledge.py` | 19 | unittest | C52 Honest Self-Knowledge: new mappings justified, coverage correction 58→95%, exposition accuracy, reverse map | ✅ GREEN |
| 59 | `test_domain_invariance.py` | 30 | unittest | C53 Domain-Invariance Benchmark: 10 domains, spec integrity, all goals reached, cross-domain invariance, per-domain behavior, runner infra | ✅ GREEN |

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

### 6. test_reflection.py — 57 tests

**What it tests:** Reflection decision triggers (failure, quality, opportunity, structural), evidence block construction for LLM, result sampling and truncation, JSON parsing of LLM reflection responses, multi-scenario summary formatting. Structural reflection (C36): StructuralDiagnostic (dead states, loop states, chronic issues, plateau, parameter bounds), structural trigger from TuningMemory, rebuild_landscape() prompt integration.

**Key findings:**
- Hard failures trigger "failure" reflection with high priority
- Goal-not-reached triggers only if progress_ratio < 0.5
- Repeated cycles > 3 with loop_penalty > 0.2 trigger reflection
- Opportunity type only when rating ≥ B and coverage high
- LLM reflection has fallback to rule-based on call failure
- Structural trigger fires between quality and opportunity when TuningMemory shows plateau, chronic issues, or parameter bounds
- StructuralDiagnostic identifies dead states, loop states, and chronic dimensions
- rebuild_landscape() passes diagnostic context to LLM for topology restructuring

---

### 7. test_invoice.py — 33 tests

**What it tests:** Invoice domain as realistic end-to-end validation — graph construction, controller run, evaluation, hybrid mode, memory persistence, full pipeline from START to COMPLETED.

**Key findings:**
- Invoice domain (almost-DAG) successfully runs through entire E₀ pipeline
- Happy path shorter than recovery alternatives
- Hybrid mode makes minor overrides in this low-holonomy domain

---

### 8. live_test_llm.py — 41 tests ⚠

**What it tests:** Live LLM integration tests (requires API key, separated from unittest discover). Landscape proposal, transition execution (SUCCESS/FAILURE/PARTIAL), confidence extraction, delta/resistance estimation, full controller run, semantic evaluation, hybrid mode with real LLM, multi-goal handling, provenance chain.

**Key findings:**
- LLM proposes connected graph with ≥ 4 states, goal always reachable
- Graph quality score typically > 0.3
- Confidence clamped to [0, 1]
- Full runs reach goal ≥ 85% with LLM
- Multi-goal runs path to at least one goal

**Note:** Requires `OPENAI_API_KEY`. Separated from unittest discover to avoid CI failures. Run explicitly: `py -3 -m unittest e0_controller.live_test_llm -v`.

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

### 41. test_residual_tension.py — 31 tests

**What it tests:** C37 Residual Tension Map and Iterative Session Control. 6 test classes:
- `TestSnapshotTensions` (3): pre-run snapshot captures all edges, s_eff values, zero initial delta
- `TestComputeResidualMap` (8): visited/unvisited edge tracking, delta_s computation, hotspot identification, resolved count, iteration tracking
- `TestShouldContinue` (9): hotspot → CONTINUE verdict, no hotspot → EQUILIBRIUM, stagnation detection (Δ < 0.02), budget exhaustion (max_iterations), threshold sensitivity, should_reflect on stagnation
- `TestSessionIterate` (5): single-iteration equilibrium, multi-iteration with hotspots, max_iterations budget, tension_threshold parameter, historization carries across iterations
- `TestFormatResidualMap` (3): key info present in output, hotspot display, equilibrium message
- `TestIterateReflection` (5; C37b): reflections list length = iterations, failure reflection on unreachable goal, clean equilibrium no reflection, failure_fn triggers reflection, _inter_iteration_reflect builds evaluation

**Key findings:**
- Iteration count is emergent (not prescribed): burnout live demo produced exactly 2 iterations
- `should_continue()` implements 4 stopping conditions: CONTINUE, EQUILIBRIUM, STAGNATION, BUDGET
- C37b: `_inter_iteration_reflect()` fires between iterations, producing ReflectionReport on failure/quality triggers
- `IterationResult.reflections` list has one entry per iteration (may be None if no trigger)

```bash
# Standard unittest suite (1483 tests, no LLM calls, ~8s)
py -3 -m unittest discover -s e0_controller -p "test_*.py" -t .

# Live LLM tests (requires API key, ~22s)
py -3 -m unittest e0_controller.live_test_llm -v

# Single file
py -3 -m unittest e0_controller.test_gordian_trap -v
```

---

## Maintenance Notes

### 42. test_resonator_integration.py — 37 tests

**What it tests:** C39 — Integration of the resonator kernel (explore_resonator.py) into the controller's amplitude overlay via resonator.py. Seven test classes:
- `TestCycleDetection` (8): detect_cycles() on triangle, diamond, acyclic, two-cycle domains; max_length constraints
- `TestCycleCoherence` (5): cycle_coherence() R_coh values, broken cycle → 0, single-node degenerate, high n_cycles
- `TestResonanceMap` (6): resonance_map() factor computation, acyclic empty, factor ∈ [1, 2], threshold filtering, ResonanceInfo fields
- `TestIntensityModifier` (4): build_resonance_modifier() boosts cyclic action, leaves non-cyclic unchanged, linear scaling
- `TestControllerIntegration` (6): resonator_modulation switch on E0Controller, overlay differs with resonator, full run, hybrid override, _compute_overlay injection
- `TestBackwardCompatibility` (3): resonator_modulation=False preserves behavior, acyclic domain unaffected
- `TestEdgeCases` (5): single edge, self-loop exclusion, probabilities sum to 1, intensities non-negative, Gordian-with-cycle probabilities valid

**Key findings:**
- Cyclic actions (B in A→B→C→A) receive intensity boost factor ∈ [1.0, 2.0]
- Non-cyclic actions (OUT) unchanged — modifier leaves them at raw intensity
- Acyclic domains: resonator_modulation=True has zero effect (no cycles to detect)
- Probabilities still sum to 1.0 and intensities remain non-negative after boost
- Hybrid mode with resonator_modulation=True works end-to-end on Gordian-with-cycle domain

---

### 43. test_overlap.py — 43 tests

**What it tests:** C40 — Graduated overlap functional per Ontodynamics §3.4 ("Overlap is graduated, not binary"). Seven test classes covering the full M_H pipeline from triangle support → edge overlap → overlap map → landscape modulation:
- `TestTriangleSupport` (8): T(x,y) = {z : x→z, z→y ∈ E, z ∉ {x,y}} — directed 2-hop support; linear, cycle, full triangle, nested loop, self-loop exclusion
- `TestEdgeOverlap` (6): overlap(x→y) = Σ_z √(v(x,z)·v(z,y)) — geometric mean of support legs; zero/positive/exact, asymmetric ordering, non-negativity
- `TestOverlapMap` (10): full M_H computation — domain-relative normalization with ε-floor; linear/cycle neutral; supported=1.0, unsupported=floor; floor parameter sensitivity; nested loop single-support
- `TestLandscapeOverlapModulation` (7): overlap_modulation flag on Landscape — default off, on differentiates, v_mod ≤ v_base, linear/cycle no effect
- `TestFalsificationDomain` (3): key falsification: two paths with identical Δ/R/S_eff/ω but different overlap — overlap modulation breaks the tie; v_mod/v_base = M_H verified
- `TestBackwardCompatibility` (4): default off, curvature + overlap independent, empty landscape, single edge
- `TestEdgeCases` (5): self-loop excluded, v=0 support leg → 0 overlap, multiple support nodes additive, floor=0 edge case

**Key findings:**
- >35 of 45 surveyed domains have zero directed triangle support → M_H trivially 1.0 (correct neutral behavior)
- Falsification domain proves M_H is non-redundant: two edges with identical burden/phase differ only in overlap
- Overlap normalization: M_H = (overlap + ε) / (max_overlap + ε), ε = max_overlap · floor / (1−floor)
- If max_overlap = 0 → M_H = 1.0 everywhere (no support structure → no modulation)
- Two independent modulation flags (curvature_modulation, overlap_modulation) coexist without interaction
- Circular dependency resolved: cache built from base v with both modulations temporarily disabled

---

### 44. test_exploration_policy.py — 42 tests

**What it tests:** C41 — Stochastic Exploration Policy. Born warmup → argmax exploit transition via ExplorationPolicy, integrated into Session.iterate(). Ten test classes:
- `TestPolicyDecision` (3): PolicyDecision dataclass fields
- `TestFixedPolicy` (4): warmup=0, always exploit from step 0
- `TestWarmupPolicy` (6): fixed warmup count, Born during warmup, argmax after
- `TestConvergencePolicy` (5): early switch to exploit when tension drops below threshold
- `TestConvenienceConstructors` (3): born_warmup() and fixed() factory functions
- `TestPolicyLabel` (3): human-readable label for each policy type
- `TestSessionPolicyIntegration` (7): iterate() with policy, mode switches, goal reaching
- `TestModeRestoration` (3): original mode preserved after iterate() completes
- `TestExplorationEffect` (4): warmup builds historization that helps exploit phase
- `TestBackwardCompatibility` (4): no policy = existing behavior unchanged

**Key findings:**
- Born warmup broadens historization coverage → exploit phase benefits from richer traces
- Mode restoration ensures Session state is clean after iterate() regardless of policy
- Convergence policy switches early when residual tension drops below threshold
- No policy = zero behavioral change (backward compatible)

---

### 45. test_landscape_mutation.py — 56 tests

**What it tests:** B4-S1 — Landscape Mutation API for Bridge 4 Structural Reflexivity. Primitives for structural self-modification of the Landscape topology. Ten test classes:
- `TestRemoveEdge` (9): removal, delta→None, R₀→∞, tension→∞, neighbors updated, nonexistent raises, states survive, preserves other edges
- `TestAdjustBaseResistance` (8): returns old value, changes R₀, propagates to tension/field, errors for nonexistent/negative, preserves Δ
- `TestAdjustDelta` (7): returns old value, changes Δ, propagates, Δ=0→v=0, errors, preserves R₀
- `TestHasEdge` (5): existing, nonexistent, directed (no reverse implication), after removal, after add
- `TestWouldOrphan` (6): diamond no orphan, leaf orphan, both endpoints, cycle no orphan, nonexistent→empty, chain middle
- `TestHistorizationInteraction` (4): R₀ change preserves δ_H, removal preserves traces, re-add keeps traces, R_eff = new_R₀ + δ_H
- `TestCacheInvalidation` (3): remove clears M_H cache, adjust_R clears overlap cache, adjust_Δ clears both
- `TestMutationErrors` (6): KeyError for nonexistent, ValueError for negative, double remove
- `TestFieldConsistency` (5): field after R↑, R↓, Δ=0, remove→v=0, re-add restores
- `TestUndoSupport` (3): undo R₀, undo Δ, undo remove via re-add

**Key findings:**
- All mutations invalidate modulation caches (_M_H_cache, _overlap_cache, _phi_cache)
- Historization survives mutations — δ_H traces are on Historization object, not Landscape edges
- remove_edge does NOT delete states — states persist for potential re-add
- Undo is manual (caller saves old value, calls adjust again) — sufficient for Stufe 2 infrastructure

---

### 46. test_structural_mutation.py — 66 tests

**What it tests:** B4-S2 — Structural Mutation Infrastructure for Bridge 4. Complete data layer for structural self-modification: typed mutations, admissibility, apply/revert, proposal engine, history with oscillation protection. Ten test classes:
- `TestStructuralMutation` (5): dataclass fields, edge property, describe() for remove/add/adjust_R₀/adjust_Δ
- `TestMutationType` (4): enum values (remove_edge, add_edge, adjust_resistance, adjust_delta)
- `TestAdmissibility` (12): remove existing/nonexistent/orphan, add new/existing/negative/missing, adjust R₀/Δ existing/nonexistent/negative
- `TestApplyMutation` (8): apply adjust_R₀/Δ/remove/add on Landscape, inadmissible raises, stores old values, preserves other edges
- `TestRevertMutation` (6): revert adjust_R₀/Δ, remove→re-add with original values, add→remove, field restoration, idempotent double revert
- `TestProposalLogic` (8): dead_states→Δ boost, loop_states→R₀ increase, empty diagnostic, admissibility filter, bounded per cycle, motivation, oscillation filter, loop dedup
- `TestMutationRecord` (4): delta_quality computed/None, default not accepted, negative delta
- `TestMutationHistory` (10): append, bounded capacity, oscillation detection (same-type + add↔remove), counts, per-edge isolation
- `TestHistorySerialization` (4): empty roundtrip, with records, max_records, add_edge fields
- `TestEndToEnd` (5): propose→apply→accept, propose→apply→revert, loop fix, history tracking, multi-cycle oscillation protection

**Key findings:**
- Admissibility gate blocks orphaning, negative values, nonexistent/duplicate edges
- Oscillation protection: same-type R₀/Δ ping-pong AND cross-type add/remove cycling
- Proposals bounded to 3 per cycle, loop pairs deduplicated
- Full serialization roundtrip for MemOS persistence
- Apply fills old_value for mechanical undo; revert uses stored values

---

### 47. test_structural_tuning_cycle.py — 42 tests

**What it tests:** B4-S3 — Structural Tuning Cycle + Session.iterate() Integration. The complete structural tuning feedback cycle and its hook into the multi-iteration orchestrator. Ten test classes:
- `TestStructuralTuningCycleResult` (4): dataclass defaults, quality, mutation_records, revert fields
- `TestCycleNoProposals` (4): healthy diamond produces no mutations, quality computed, diagnostic populated, no quality_after
- `TestCycleWithDeadStates` (5): dead state D generates ADJUST_DELTA proposals, applied_mutations filled, quality computed, accept/revert outcome
- `TestCycleWithLoops` (4): S↔A loop detected, R₀ proposals generated, quality computed, returns correct type
- `TestCycleRevert` (4): revert restores landscape, reverted flag set, accepted on positive delta, records match applied
- `TestCycleHistoryIntegration` (5): history updated after cycle, None creates fresh, oscillation blocked on repeat, records have quality, accept/revert consistency
- `TestSessionStructuralHook` (6): Session has mutation_history, iterate() returns structural_results, length matches iterations, no trigger gives None, structural trigger invokes cycle, quality trigger skips
- `TestIterationResultFields` (3): default empty, explicit, policy_phases backward compat
- `TestSessionMutationHistory` (3): new session has empty history, attribute exists, mutable
- `TestEndToEndStructural` (4): full loop cycle, multiple cycles accumulate, dead state modifies landscape, no-goal works

**Key findings:**
- Eskalationskette: parametrisch erschöpft → structural trigger in reflection → structural_tuning_cycle
- structural_tuning_cycle: Run → Diagnose → Propose → Apply → Re-run → Verify Q → Accept/Revert
- Session.iterate() Step 6: only fires on reflection_type="structural" AND should_continue
- MutationHistory accumulates across cycles, oscillation guard filters repeats

---

### 48. test_qualitative_mass.py — 37 tests

**What it tests:** C42 — 4-Layer Model (Historization → Inscription → Inertia → Mass). The core functions `trace_load()`, `trace_quality()`, `inertia_factor()` on Historization edges, the `inertia_modulation` flag on Landscape, and backward-compatibility aliases (`mass()`, `quality()`, `mass_modulation_factor()`, `mass_modulation`).

**Key findings:**
- `trace_load()` = effective trace count with ρ-decay
- `trace_quality()` = (U−F)/(U+F), bounded in [−1, +1]
- `inertia_factor()` = 1 − α·(m/(m+μ))·(1−|q|): high load + high quality → low inertia (confident), high load + low quality → high inertia (confused)
- Old names still work as aliases for backward compat

---

### 49. test_self_graph.py — 47 tests

**What it tests:** C43 — Self-Graph (Selbstunterscheidung). E0's structural self-knowledge: 8-node, 8-edge dedicated Landscape representing E0's own operational cycle. ρ=1.0 (cumulative — no decay). `self_historize()` updates traces on edges where both endpoints are active. `component_quality/load/inertia()` aggregate outgoing edge metrics. `snapshot()` for MemOS persistence. Controller integration via `self.self_graph` attribute.

**Key findings:**
- Core components (amplitude, born, realization, historization, inertia, transition_field) always active
- Modulation components (curvature, overlap) active only when their flags are enabled
- Only edges where both source and target are in active set get updated
- Quality converges: all SUCCESS → positive, all FAILURE → negative, mixed → near zero
- Controller `cycle()` hook calls `self_graph.self_historize()` after historization

---

### 50. test_bootstrapper.py — 41 tests

**What it tests:** C44 — Bootstrapper. Converts structured domain specs into initialized Landscapes. `validate_spec()` checks structure (nodes, edges, types, ranges). `bootstrap_landscape()` builds Landscape with topology + injected initial traces. `_apply_confidence()` scales initial traces toward midpoint (low confidence → balanced U/F → low |quality| → E0 is cautious). `_inject_traces()` injects U/F values from spec.

**Key findings:**
- Validates: no empty graph, no negative weights, no self-loops, edges reference known nodes
- Confidence=1.0 preserves exact U/F ratios; confidence=0.0 forces U=F (quality=0)
- Bootstrapped landscapes get `inertia_modulation=True` by default
- Unknown nodes in edges are skipped (lenient parsing for LLM output)

---

### 51. test_mode_controller.py — 36 tests

**What it tests:** C46 — Mode Controller. `OperatingMode` enum (LEARN / EXECUTE / COMBINATION). `ModeController` monitors Landscape edge `trace_load` vs μ threshold. `current_mode()` determines aggregate mode from coverage ratio. `edge_needs_llm()` / `neighbors_needing_llm()` for COMBINATION filtering. Coverage statistics.

**Key findings:**
- Empty landscape → LEARN mode (no data to operate on)
- All edges explored (trace_load ≥ μ) → EXECUTE mode (autonomous)
- Mixture → COMBINATION (call LLM only for unexplored edges)
- Uses same μ threshold as `inertia_factor()` — consistent semantics
- Controller integration via `self.mode_controller` attribute

---

### 52. test_dual_reflection.py — 36 tests

**What it tests:** C47 — Dual Reflection. Combines domain `ReflectionReport` with self-graph `SelfGraphDiagnosis`. `diagnose_self_graph()` classifies each component as healthy/confused/harmful/insufficient_data. Cross-referencing: domain failure layers + self-graph issues → targeted meta-actions. Meta-control: modulation components (curvature, overlap) with negative quality → deactivation candidates. `format_dual_report()` for human-readable combined output.

**Key findings:**
- Fresh self-graph: all components have insufficient_data (no traces yet)
- After 10+ successes: all assessed components healthy
- After failures only: harmful components, modulation → deactivation candidates
- Mixed outcomes: confused status, investigation recommended
- Cross-reference: domain flags "controller" + born is harmful → prioritize born investigation
- Core components never in deactivation_candidates (only modulation can be disabled)

---

### 53. test_canon_loader.py — 72 tests

**What it tests:** C48 — Canon Loader. Discovery of canon JSON files via `list_canons()`. Raw spec loading and error handling. Extraction of `CanonInfo` (nodes, edges, necessary_consequences). Conversion to Bootstrapper-compatible spec. Full `load_canon()` pipeline (JSON → CanonLandscape). Ontodynamics v1.2 topology: derivation levels L0–L8, axiom convergence, reflexivity inputs, negative_notwendigkeit 3-input convergence, happy path length, full reachability. Navigation: controller can traverse differenz→masse and differenz→negative_notwendigkeit. Graph quality: no traps on masse path, no trivial loops, quality to negative_notwendigkeit.

**Test classes:**
- `TestListCanons` (3): discovery logic, returns list, ontodynamics present
- `TestLoadCanonSpec` (4): valid load, missing file, invalid JSON, required fields
- `TestExtractInfo` (12): node count, edge count, consequence count, field presence, derivation levels, confidence values
- `TestToBootstrapperSpec` (6): spec format, node presence, edge mapping, delta/resistance transfer, confidence passthrough, invalid spec
- `TestLoadCanon` (6): returns CanonLandscape, landscape states, info nodes, info summary, error propagation, bootstrapper integration
- `TestOntodynamicsTopology` (17): 19 nodes, 31 edges, primitive levels, derived levels, cycle closure, axiom requires differenz+pfad, reflexivity requires 2 inputs, negative_notwendigkeit requires 3 inputs, happy path ≥5, full journey reachable, blueprint convergence, level distribution
- `TestDerivationOrder` (4): order exists, differenz first, all nodes present, topological consistency
- `TestCanonTraces` (4): U/F values from confidence, high confidence ratio, low confidence near 0.5, trace load
- `TestCanonNavigation` (4): differenz→masse reachable, differenz→negative_notwendigkeit reachable, step results valid, s_eff positive
- `TestFormatCanonSummary` (9): contains canon_id, contains nodes, contains edges, contains consequences, level markers, level labels, description included, edge format, multiline
- `TestCanonGraphQuality` (3): no traps on masse path, no trivial loops, quality to negative_notwendigkeit

**Key findings:**
- Ontodynamics v1.2 has 19 nodes (5 primitives L0–L3, 14 derived L4–L8) and 31 edges
- Cycle closure historisierung→differenz verified
- Full journey differenz→negative_notwendigkeit navigable in ≥5 steps
- Graph quality uses `graph_quality(landscape, start, goal)` — no traps on masse path, quality score positive for full journey
- Canon loads through the same Bootstrapper (C44) pipeline as LLM-proposed domains

---

### 54. test_canon_self_bridge.py — 32 tests

**What it tests:** C48 — Canon ↔ Self-Graph Bridge. Structural mapping between self-graph components and canon concepts. Coverage analysis (which canon nodes have operational counterparts). Canon-aligned process status formatting. Combined self-exposition for LLM context (4 sections). Structural correctness invariants.

**Test classes:**
- `TestCanonProcessMap` (7): all 8 self-graph components present, all values are non-empty lists, all mapped canon nodes exist in PROCESS_CANON_MAP, reverse map completeness, historisierung maps to historization, no duplicate entries, gradueller_overlap shared by curvature+overlap
- `TestCanonCoverage` (9): coverage ratio, instantiated set, not-instantiated set, union equals all nodes, empty canon edge case, full-coverage synthetic canon, ratio bounds, specific frontier nodes, no overlap between sets
- `TestFormatProcessStatus` (3): all 8 components in output, quality/load/inertia fields present, canon concept labels in output
- `TestBuildSelfExposition` (9): 4 sections present (BELIEVE/OPERATE/COVERAGE/INSIGHT), with self-graph includes operational data, without self-graph shows placeholder, epistemic frontier section present, historization quality assessment, key identity statement, coverage percentage, node labels in frontier, section ordering
- `TestStructuralCorrectness` (4): historisierung→historization bidirectional, PROCESS_CANON_MAP consistent with CANON_PROCESS_MAP, gradueller_overlap shared by both modulation components, all v1.2 nodes either instantiated or explicitly frontier

**Key findings:**
- 11/19 canon nodes (58%) have operational self-graph counterparts
- 8 frontier nodes: zeit, zustand, raumzeit, strukturelle_zulaessigkeit, reflexivitaet, strukturelle_ausrichtung, domaeneninvarianz, negative_notwendigkeit
- Central identity: self-graph "historization" = canon "historisierung" — same mechanism, different perspectives
- Coverage gap is a feature (epistemic honesty), not a deficiency

---

### 55. test_reflexive_action.py — 41 tests

**What it tests:** C49 — Reflexive Action. Closes the reflexive loop: C47 Dual Reflection diagnosis → concrete, reversible landscape mutations. Only modulation components (curvature, overlap) can be toggled; core components are structurally protected. Full undo via `ReflexiveActionResult.restore()`. Session.iterate() Step 7 integration.

**Test classes:**
- `TestReflexiveAction` (4): dataclass fields, is_deactivation true/false/noop
- `TestReflexiveActionResult` (7): empty result, any_changes, restore reverses, restore order, summary variants
- `TestPlanReflexiveActions` (8): no candidates, curvature active/inactive, overlap, both, core ignored, unknown ignored, reason has quality
- `TestApplyReflexiveActions` (7): deactivates curvature/overlap/both, skips inactive, mixed, no candidates, undo
- `TestCoreProtection` (3): modulation flags only modulations, contains known modulations, core never applied
- `TestEndToEnd` (4): harmful curvature deactivated via live SelfGraph, healthy stays, confused not deactivated, restore after end-to-end
- `TestSessionIntegration` (5): IterationResult has reflexive_results, Session has self_graph, iterate produces results, results are Optional, backward compat default empty
- `TestEdgeCases` (3): empty diagnosis, repeated apply idempotent, summary format no crash

**Key findings:**
- Only `_MODULATION_FLAGS` (curvature→curvature_modulation, overlap→overlap_modulation) are ever toggled
- Core components (amplitude, born, realization, historization, inertia, transition_field) are structurally protected
- Full reversibility: `restore()` undoes all mutations in reverse order
- Session integration: Step 7 in iterate() — after structural tuning, dual reflection triggers reflexive action
- End-to-end chain verified: SelfGraph → diagnose_self_graph → apply_reflexive_actions → landscape mutation → restore

---

### 56. test_reflexive_journal.py — 37 tests

**What it tests:** C50 — Stufe 4b Representation. Reflexive Journal persistence + Section 5 of self-exposition. After C49 mutates the landscape, C50 ensures those mutations are recorded chronologically and rendered in `build_self_exposition()`. Closes Bridge 4 Stufe 4b.

**Test classes:**
- `TestReflexiveJournalEntry` (3): dataclass fields, restored default false, restored settable
- `TestReflexiveJournal` (16): empty state, record returns count, entries returns copy, active_deactivations filter, mark_restored (single, already restored, wrong iteration), current_state (empty, active, restored), multi_iteration ordering, format (empty, active, mixed), non-deactivation not tracked
- `TestExpositionSection5` (10): without journal, with empty journal, populated journal, active count, current state, restored shown, all 5 sections present, with self_graph, canon L7 reference, empty journal message
- `TestSessionJournal` (3): session has journal attribute, starts empty, survives iterate
- `TestEndToEnd` (3): harmful component appears in exposition, restore reflected in exposition, length grows with entries
- `TestEdgeCases` (3): multiple iterations same component, many entries (100), None journal handled

**Key findings:**
- `ReflexiveJournal` records `ReflexiveJournalEntry` per reflexive action, supports `mark_restored()` for undo tracking
- Section 5 "WHAT I HAVE DONE TO MYSELF" renders: chronological history, active deactivation count, canon L7 reference, current modulation state
- Active vs restored distinction visible: `[active]` vs `[restored]` in format output
- End-to-end chain: SelfGraph failures → diagnose → apply → journal.record → build_self_exposition → Section 5 verifiable
- Session wiring: journal created in `__init__`/`resume`, recorded in Step 7 after reflexive action

---

### 57. test_system_integration.py — 19 tests

**What it tests:** C51 — System-Level Integration (E₀ lernt E₀). Proves that all components from C43–C50 work together as one system. Full pipeline: Session(canon_landscape) → iterate() → controller.cycle() → self_graph.self_historize() → dual_reflect → apply_reflexive_actions → journal.record → build_self_exposition(). Uses the materialized Ontodynamics canon as domain — E₀ operates on its own ontology (Selbst-Fundierung).

**Test classes:**
- `TestPipelineWiring` (5): Session creates all components, iterate returns complete result, self_graph accumulates, exposition has 5 sections, result lists aligned
- `TestSelfFundierung` (5): canon navigable, process map covers core, coverage partial with frontier, self-knowledge accumulates over iterations, full exposition substantial
- `TestReflexiveConvergence` (3): pre-poisoned curvature deactivated in iterate Step 7, journal populated + visible in exposition, flag stays off
- `TestDirectPipelineAssembly` (3): manual walk all 5 steps, component→canon mapping shown, epistemic frontier identified
- `TestEdgeCases` (3): minimal 2-node landscape, all-failure negative quality, fresh vs operated exposition differs

**Key findings:**
- Full pipeline fires end-to-end within Session.iterate() — not just component-by-component
- Step 7 reflexive action fires with pre-poisoned curvature + amplifying tension (mostly-failing execute_fn)
- Canon landscape (19 nodes, 31 edges) is a valid, navigable domain for the controller
- Self-knowledge accumulates significantly across iterations (total_load > 5)
- Exposition grows from ~500 chars (canon only) to ~2000+ chars (fully operated)
- Coverage ratio ~58% — honest epistemic frontier with 8 not-yet-instantiated concepts (corrected to ~95% in C52)

---

### 58. test_honest_self_knowledge.py — 19 tests

**What it tests:** C52 — Honest Self-Knowledge. Proves that the CANON_PROCESS_MAP was inaccurate (58% coverage when 7 concepts were already operationally implemented) and that the corrected map (95%) is justified by actual code. Verifies each new mapping against real infrastructure, checks coverage arithmetic, exposition accuracy, and reverse-map consistency.

**Test classes:**
- `TestNewMappings` (7): each new mapping justified — zeit via historization._tau, zustand via Landscape._states, negative_notwendigkeit via born/A₀, reflexivitaet via reflexive loop, strukturelle_zulaessigkeit via admissibility, strukturelle_ausrichtung via inertia/resistance, domaeneninvarianz via domain-free realization
- `TestCoverageCorrection` (5): coverage > 90%, not_instantiated == {raumzeit}, 18/19 instantiated, instantiated ∪ not_instantiated = all nodes, partition invariant
- `TestExpositionAccuracy` (4): frontier shows only raumzeit, reflexivitaet is operational, zeit mapped to historization, frontier length ≤ 2
- `TestReverseMap` (3): PROCESS_CANON_MAP keys ⊆ canon nodes, every mapped canon node traceable to component, bidirectional consistency

**Key findings:**
- 7 canon concepts were implemented but unmapped — structural lie in self-observation
- Only `raumzeit` (emergent spacetime, L5) is genuinely unimplemented
- coverage: 18/19 = 94.7%
- Each mapping has code-level justification (not just semantic similarity)

---

### 59. test_domain_invariance.py — 30 tests

**What it tests:** C53 — Domain-Invariance Benchmark. Proves E₀’s controller is domain-invariant: 10 structurally diverse domains, identical controller parameters (alpha=2.0, recent_k=3, HybridMode.GREEDY), all goals reached, worst rating B.

**Test classes:**
- `TestDomainSpecIntegrity` (10): 10 domains, unique names, start/goal in states, node/edge counts match, ≥6 topology classes
- `TestAllDomainsReachGoal` (1): all 10 goals reached with default params
- `TestDomainInvariance` (6): no tuning, worst rating ≤C, success rate ≥60%, ≥6 topology classes, scale range, mixed difficulty
- `TestIndividualDomains` (10): per-domain behavioral expectations (optimal paths, trap escape, failure recovery, dead-end escalation)
- `TestBenchmarkRunner` (3): 10 results, dict structure, required fields

**Key findings:**
- 10 topology classes: linear, diamond, gordian, cycle_trap, grid, star, process, cyclic, dag, bottleneck
- Ratings: 6×A, 4×B — no C or F
- Trap domains require FAILURE outcomes for greedy escape (historization reinforces successful loops)
- Domain-specific data (execute_fn outcomes) is NOT controller tuning — it’s the domain’s physics

---

## Maintenance Notes

- When adding a new test file: add a row to the **Overview Table** and a **Per-File Details** section.
- Update `Last verified` date and total count after full regression.
- LLM integration tests (`test_llm_integration`) fail without `OPENAI_API_KEY` — not counted as regression failures.
- `test_minidomain.py` runs standalone (21 tests, not discovered by unittest discover).
- `test_beipackzettel_noncircular.py` uses mock LLM — no API key needed.
