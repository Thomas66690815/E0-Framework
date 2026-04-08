# E₀ Architecture Overview v5

**Status:** Canonical reference  
**Date:** 2026-04-07  
**Supersedes:** E0_ARCHITECTURE_OVERVIEW_v4.md (2026-04-06)  
**Scope:** 76 production modules, 10 benchmarks, 17 demos, 62 explorations, 121 test files — ~31,000 production lines, 4265 tests
**Latest:** C183 (E2E Multiverse — full capability exercise across all 14 layers, 15-phase pipeline)
**Papers:** P1 (Structural Interference), P2 (Spinor/Born), P3 (Non-Abelian), P4 (Reflexivity), P5 (Emergent Locality), P6 (Dream Mode)

---

## 1. Structural Layer Model

E₀ is organized in fourteen layers. Each layer depends only on layers above it.

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1 — PRIMITIVES                                   │
│  Edge, Outcome, Tension, Coherence, TransportRegime     │
├─────────────────────────────────────────────────────────┤
│  Layer 2 — STRUCTURAL INSCRIPTION                       │
│  Historization (U/F traces, δ_H, trace_load/quality)    │
│  Landscape (states, edges, Δ, R₀, modulation flags)     │
├─────────────────────────────────────────────────────────┤
│  Layer 3 — FIELD THEORY                                 │
│  Potential (Φ, v_grad, v_rot), Connection (ω, Θ),       │
│  Wave Path (Ψ, intensity), Overlap (M_H), Resonator     │
├─────────────────────────────────────────────────────────┤
│  Layer 4 — CONTROLLER                                   │
│  Selection (argmin S_eff / M_H·I), Escalation (4 types), │
│  Hybrid Modes, Amplitude Overlay, Dynamic Horizon        │
├─────────────────────────────────────────────────────────┤
│  Layer 5 — REFLEXION                                    │
│  Self-Graph, Dual Reflection, Reflexive Edge Proposal,   │
│  Reflexive Action, Integrated Reflexion, Struct Mutation, │
│  Scoped Reflexion (emergent locality),                    │
│  SU(2) Perspective Diagnostic                             │
├─────────────────────────────────────────────────────────┤
│  Layer 6 — MULTI-SYSTEM                                 │
│  Multiverse (Novelty Gate, Coupling), Cross-Reflexion,   │
│  Overload Escalation (peer_fn), Raumzeit Coupling,       │
│  Coupling Router (N>2 dynamic partner selection)         │
├─────────────────────────────────────────────────────────┤
│  Layer 7 — INFRASTRUCTURE                               │
│  Session, MemOS, LLM Adapter, Bootstrapper, Provenance,  │
│  Canon Loader/Bridge, Evaluation, Exploration Policy,     │
│  Config, Curriculum, Parameter Sensitivity                │
├─────────────────────────────────────────────────────────┤
│  Layer 8 — OBSERVATION                                  │
│  O-Landscape, Observation Controller, Rendering Adapter, │
│  Service Layer, Input Pipeline, Snapshot Codec            │
├─────────────────────────────────────────────────────────┤
│  Layer 9 — DREAM MODE                                   │
│  EdgeFingerprint, Equivalence Detection, DreamObserver,  │
│  WLNodeFingerprint, Node Equivalences, Bridge Hypothesis │
├─────────────────────────────────────────────────────────┤
│  Layer 10 — STRUCTURAL ENTROPY                          │
│  Inscription Threshold (Type 1), Anchor Analysis,        │
│  Structural Decay (Type 2), Structural Temperature       │
├─────────────────────────────────────────────────────────┤
│  Layer 11 — SLEEP–WAKE CYCLE                            │
│  Dream Pressure, SleepWakeCycle Orchestrator             │
├─────────────────────────────────────────────────────────┤
│  Layer 12 — HUMAN COMMUNICATION                         │
│  Perception Ontology, Communication Intent,              │
│  UI-Schema Emitter, Human Feedback Loop                  │
├─────────────────────────────────────────────────────────┤
│  Layer 13 — UI RENDERING + PRETRAINING                   │
│  UI Renderer (UISpec → HTML), Visual Pretraining,        │
│  LLM Rendering Selection, Memo Persistence               │
├─────────────────────────────────────────────────────────┤
│  Layer 14 — SESSION RUNNER                               │
│  Unified Pipeline: task → LLM endpoints → Controller     │
│  → Perception → Intent → UISpec → HTML                  │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Complete Module Inventory

### Layer 1 — Primitives (2 modules, 76 lines)

| Module | Lines | Purpose | Paper |
|--------|------:|---------|-------|
| `primitives.py` | 31 | `Edge`, `Outcome`, `TransportRegime` | P1–P4 |
| `tension.py` | 45 | `tension()`, `path_tension()`, `coherence()` — S = Δ · R_eff | P1–P4 |

### Layer 2 — Structural Inscription (2 modules, 584 lines)

| Module | Lines | Purpose | Paper |
|--------|------:|---------|-------|
| `historization.py` | 252 | U/F traces, δ_H, trace_load, trace_quality, inertia_factor | P1 |
| `landscape.py` | 332 | States, edges, Δ, R₀, admissible_neighbors, modulation flags | P1–P4 |

### Layer 3 — Field Theory (6 modules, 1,109 lines)

| Module | Lines | Purpose | Paper |
|--------|------:|---------|-------|
| `potential.py` | 194 | Φ, v_grad, v_rot — discrete Helmholtz decomposition | P1 |
| `connection.py` | 142 | ω, Θ, holonomy — gauge connection on edges | P1–P3 |
| `wavepath.py` | 138 | Ψ(p) = exp(−S+iΘ), sum_paths, intensity | P1 |
| `overlap.py` | 106 | Graduated M_H — triangle support, edge overlap (C40, C98) | P4, P5 |
| `resonator.py` | 222 | Loop detection, cycle coherence, resonance_map (C39) | — |
| `spinor_connection.py` | 349 | SU(2) lift: su2_edge_transport, spinor_psi, compare_u1_su2 | P2, P3 |

### Layer 4 — Controller (4 modules, 1,107 lines)

| Module | Lines | Purpose | Paper |
|--------|------:|---------|-------|
| `controller.py` | 621 | Core loop: select → execute → historize. 4 escalation types (DEAD_END, FILTERED, EXHAUSTED, OVERLOADED). 3 hybrid modes (GREEDY, AMPLITUDE_ON_DISAGREE, BORN_SAMPLING). peer_fn callback (C63). Greedy selection: argmin S_eff/(M_H·I) with overlap modulation (C98) and inertia dampening (C99) | P1, P4, P5 |
| `amplitude_overlay.py` | 257 | Bounded-horizon amplitude analysis, non-invasive overlay | P1 |
| `dynamic_horizon.py` | 129 | Pluggable horizon strategies: fixed, topology_adaptive, capped | — |
| `exploration_policy.py` | 100 | Born warmup → exploit switch, convergence threshold (C41) | — |

### Layer 5 — Reflexion (11 modules, ~5,000 lines)

| Module | Lines | Purpose | Paper |
|--------|------:|---------|-------|
| `self_graph.py` | 200 | Structural self-knowledge — component quality historization (C43) | P4 |
| `dual_reflection.py` | 331 | Domain + self-graph dual diagnosis (C47) | P4 |
| `reflexive_edge_proposal.py` | 322 | Hypothesis edges at frontier — reactive (C56) + proactive (C57) | P4 |
| `reflexive_action.py` | 232 | Diagnosis → concrete landscape mutation (C49) | P4 |
| `integrated_reflexion.py` | 245 | Unified C49 + C57 reflexion pipeline (C59). Scoped mode (C102): scoped=True delegates to scoped_propose_edges | P4, P5 |
| `scoped_reflexion.py` | 445 | Locality-driven scope: ℓ = m̄/(m̄+μ), radius = max(1,⌈(1-ℓ)·D⌉). μ = |E|/|V| auto-derived (C105). Corridor mode follows inscription (C106). Fresh → global, historized → local (C101) | P5 |
| `emergent_locality.py` | 406 | Emergence proof tooling: track locality evolution, phase transition, regional profile, convergence (C104) | P5 |
| `reflection.py` | 791 | Reflection layer — bounded self-reference, 4 triggers (Phase 3g) | P4 |
| `structural_mutation.py` | 693 | Bridge 4 — propose/apply/verify/revert topology (Stufe 2) | — |
| `self_tuning.py` | 1,164 | Meta-landscape over parameters, tuning memory (B4) | — |
| `perspective_diagnostic.py` | 171 | SU(2) perspective check: U(1) vs SU(2) ranking comparison, PerspectiveReport, fragile action detection. Controller + DualReflectionReport integration (C153) | P2, P3 |

### Layer 6 — Multi-System (5 modules, 1,720 lines)

| Module | Lines | Purpose | Paper |
|--------|------:|---------|-------|
| `multiverse.py` | 363 | Coupled systems: NoveltyGate, divergence pressure, coupling landscape (C60) | — |
| `cross_reflexion.py` | 284 | Cross-universe reflexive edge discovery: blend_patterns, cross_propose (C62) | — |
| `raumzeit_coupling.py` | 244 | Coupling necessity theorem proof (C54) | — |
| `coupling_router.py` | 545 | N>2 dynamic partner selection, coupling metrics, partner scoring (C66/C67) | — |
| `peer_bridge.py` | 133 | Peer function bridge: adapter between multiverse coupling and controller peer_fn | — |
| C63 in `controller.py` | ~30 | OVERLOADED escalation, peer_fn, overload_index | — |

### Layer 7 — Infrastructure (17 modules, 4,499+ lines)

| Module | Lines | Purpose | Paper |
|--------|------:|---------|-------|
| `session.py` | 491 | Lifecycle: load → run → iterate → save. ExplorationPolicy (C41) | P4 |
| `memory_os.py` | 568 | Persistent substrate: snapshots, hybrid traces, geometry | P1 |
| `llm_adapter.py` | 869 | Structured LLM interface: extract_delta, propose_states, execute_transition | — |
| `bootstrapper.py` | 230 | Structured spec → Landscape (C44). Monolingual teacher role (C134): LLM score 0–10 → initial_U/F → continuous quality spectrum via _apply_confidence | — |
| `evaluation.py` | 454 | Run quality: A–F rating, hard failure gates, semantic assessment | P1, P4 |
| `reflection.py` | *(see L5)* | *(also infrastructure — trigger + diagnostic)* | P4 |
| `residual_tension.py` | 234 | Iteration control: residual map, should_continue (C37) | — |
| `provenance.py` | 287 | Full evidence chain: input → LLM call → output logging | — |
| `canon_loader.py` | 204 | JSON canon → materialized Landscape (C48) | — |
| `canon_self_bridge.py` | 255 | Canon ↔ Self-Graph alignment: coverage, exposition | — |
| `graph_validation.py` | 278 | Pre-run structural checks: reachable, traps, happy_path (Phase 3c) | — |
| `scenario_loader.py` | 102 | JSON scenario packets for LLM context | P1 |
| `mode_controller.py` | 146 | Learn/Execute/Combination auto-switch (C46) | — |
| `envelope.py` | 154 | Typed, frozen controller config: E0Envelope | — |
| `domain_invoice.py` | 197 | Invoice processing domain model (Phase 1b) | — |
| `config.py` | 172 | E0Config central parameter registry: 45+ fields, frozen dataclass, DEFAULTS singleton. Single source of truth for all numerical defaults (C148) | — |
| `curriculum.py` | 341 | Curriculum Navigator: hierarchical learning, CurriculumStrategy, EquilibriumDetector, build_scoped_landscape, transfer_historization, CurriculumRunner. DreamObserver integration (C156) | — |
| `parameter_sensitivity.py` | 438 | Parameter sensitivity + auto-tuning: run_trial, sensitivity_analysis, suggest_perturbations, auto_tune, apply_config. Closed-loop parameter optimization (C150/C155) | — |

### Benchmarks (10 modules, ~3,600 lines)

| Module | Lines | Purpose | Paper |
|--------|------:|---------|-------|
| `benchmark_domain_invariance.py` | 451 | 10 domains × zero tuning — proves universality (C53) | — |
| `benchmark_amplitude.py` | 302 | 10 domains × 3 controller modes (C55) | — |
| `benchmark_gridworld.py` | 359 | E₀ vs Naive-Greedy vs A* | P1 |
| `benchmark_reflexion.py` | 179 | 10 domains × 3 reflexion regimes (C58) | P4 |
| `benchmark_multiverse.py` | 223 | 5 cross-domain pairings (C61) | — |
| `benchmark_overloaded.py` | 271 | Peer consultation × 10 domains (C70) | — |
| `benchmark_cross_reflexion.py` | 184 | Cross-universe edge discovery (C69) | — |
| `benchmark_modulation.py` | 387 | 14 domains × 3 modes: BASELINE/OVERLAP/FULL (C100) | P5 |
| `benchmark_scoped_reflexion.py` | 212 | 10 domains × GLOBAL vs SCOPED (C103) | P5 |
| `validate_cross_domain.py` | 295 | Systematic demo comparison (Phase 3d) | — |

### Demos (17) and Explorations (60)

Not listed individually — these are experimental tooling for interactive analysis.
Demos: `demo_beipackzettel`, `demo_ezb_zinsentscheidung`, `demo_burnout_*`, `demo_invoice_llm`, `demo_greedy_trap`, `demo_open_domain`, `demo_research_brief`, `demo_incident_postmortem`, `demo_session_persist`, `demo_canon_exposition`, `demo_bootstrap_domain` (C140, `--entropy` C141), `demo_multiverse` (C142), `demo_curriculum` (C143, `--entropy`), `demo_reflexion` (C144, `--entropy`), `demo_self_graph`, `demo_human_communication` (C162).
Explorations (62): Not listed individually. Covers Gordian analysis, amplitude/resonator/spinor/topology scans, G5 edge cases, attractor dynamics, dream mode, focus narrowing, structural entropy, language learning (C124–C138), adversarial stability (C172–C174), causal binding (C175–C178), compatibility calibration (C169), partial matching (C170), asymmetric teaching (C171), N-domain mesh (C179–C180), dream transitivity (C181), saturation point (C182), E2E multiverse (C183), and SU(2) pretests.

### Layer 8 — Observation & Service (6 modules, 1,387 lines)

| Module | Lines | Purpose | Paper |
|--------|------:|---------|-------|
| `observation.py` | 214 | O-Landscape: observation as E₀ domain (scope×depth states) (C94) | — |
| `observation_controller.py` | 310 | Navigation (focus/defocus/move/deepen/retreat) + domain projection (C95) | — |
| `rendering_adapter.py` | 178 | Observation → wire format: edge data at each depth level (C96) | — |
| `service.py` | 437 | FastAPI service layer: REST + WebSocket endpoints (C83/C84) | — |
| `input_pipeline.py` | 67 | Input processing pipeline (C83) | — |
| `snapshot_codec.py` | 181 | Snapshot encoding/decoding for persistence and wire format (C83) | — |

### Layer 9 — Dream Mode (1 module, 1320 lines)

| Module | Lines | Purpose | Paper |
|--------|------:|---------|-------|
| `dream_mode.py` | 1320 | Cross-domain pattern recognition: EdgeFingerprint, fingerprint_distance, find_equivalences, DreamObserver (register/unregister/dream_cycle/feedback), BridgeHypothesis, propose_bridges, make_dream_peer_fn (C109–C111). Decay integration: decay_enabled, DreamCycleResult.decay_reports (C119). **Node-level matching (C134b):** NodeFingerprint, node_fingerprints, node_fingerprint_distance, find_node_equivalences. **WL recursive neighborhood (C135–C136):** WLNodeFingerprint, wl_node_fingerprints (9-dim Round-0: mean/std/degree/pos_frac/min/max/median quality + trace_load mean/std), wl_node_distance, find_wl_node_equivalences. **Hungarian optimal assignment (C137):** find_wl_node_equivalences_hungarian — scipy.optimize.linear_sum_assignment on full WL distance matrix, globally optimal 1:1 node pairing → **44/44 = 100%**. **C139 Runtime Integration:** DreamObserver.dream_cycle() now invokes node-level equivalences (hungarian or wl method) alongside edge-EQ. `_update_dream_landscape_nodes()` creates "domain:node" states. `_node_equivalence_state()` helper. DreamCycleResult extended with `node_equivalences_found`/`node_equivalences_new`. **C168 Compatibility Gating:** `dream_compatibility()` (mean WL distance under Hungarian assignment), `is_dream_compatible()` (threshold check). DreamObserver pre-filters domain pairs — incompatible pairs skipped. DreamCycleResult extended with `compatibility_skipped`/`compatibility_scores`. Config: `dream_compatibility_threshold = 0.6`. Empirical: EN↔DE=0.375✓, EN↔ONTO=0.870✗, DE↔ONTO=1.014✗. **C169 Threshold Calibration:** 36 domain pairs (9 domains), gap=0.410 between compatible (max 0.190) and incompatible (min 0.600). Any threshold in [0.4, 0.7] gives identical results. **C170 Partial Matching (NEGATIVE):** Full NxM WL distance matrices for incompatible pairs show 0% overlap with compatible best-5 distances — WL fingerprints are too specific for subgraph matching. **C171 Asymmetric Teaching:** EN_heavy (5400 steps) vs EN_light (300 steps) produce identical fingerprints (variance ratio=1.000). All cross-domain differences are topology-driven (EN/DE ratio=0.692). Asymmetric teaching scoped to LLM-bootstrapped domains only. | P6 |

### Layer 10 — Structural Entropy (1 module, ~600 lines)

| Module | Lines | Purpose | Paper |
|--------|------:|---------|-------|
| `structural_entropy.py` | ~600 | Forgetting as structural necessity. Type 1: structural_temperature (T_s = m̄/q̄), novelty, inscription_threshold, should_inscribe. Type 2: anchor_score, state_dormancy, find_decay_candidates, find_anchors. Execution: DecayTrace, DecayReport, apply_decay (3-phase). Dream trigger: dream_pressure, should_dream (C115–C121) | — |

### Layer 11 — Sleep–Wake Cycle (1 module, ~240 lines)

| Module | Lines | Purpose | Paper |
|--------|------:|---------|-------|
| `sleep_wake.py` | ~240 | Automatic rhythm between wake (controller.run) and sleep (dream_cycle). dream_pressure = T_s/(T_s+μ) triggers dreaming when T_s > μ. SleepWakeCycle orchestrates Controller + DreamObserver. Parameter-free trigger (C121) | — |

### Layer 12 — Human Communication (4 modules, ~1,150 lines)

| Module | Lines | Purpose | Paper |
|--------|------:|---------|-------|
| `perception.py` | ~290 | Perception Ontology: 10 visual + 5 language Gestalt primitives as landscape domain, 20 sparse edges (C158) | — |
| `communication.py` | ~400 | Communication Intent: 6 intent types (uncertainty/decision/pattern/request/status/anomaly), `detect_intents()` from SelfGraph + StepResult + DreamObserver (C159) | — |
| `ui_emitter.py` | ~300 | UI-Schema Emitter: (Intent × Perception) → UISpec with heuristic affinities + learned perception override, `emit_ui_spec()` (C160) | — |
| `feedback.py` | ~160 | Human Feedback Loop: 6 HumanActions → Outcome, perception edge historization closes the learning cycle (C161) | — |

### Layer 13 — UI Rendering + Pretraining (2 modules, ~850 lines)

| Module | Lines | Purpose | Paper |
|--------|------:|---------|-------|
| `ui_renderer.py` | ~350 | Stateless UISpec → standalone HTML document. Component templates (table, alert, list, metric, text, chart). CSS generation. (C163) | — |
| `visual_pretraining.py` | ~500 | LLM evaluates rendering options per perception primitive. Memo persistence for learned preferences. Learnable rendering selection. (C164) | — |

### Layer 14 — Session Runner (1 module, ~400 lines)

| Module | Lines | Purpose | Paper |
|--------|------:|---------|-------|
| `e0_session.py` | ~400 | Unified end-to-end pipeline: task → LLM-derived endpoints → Controller navigation → Perception → Intent → UISpec → HTML. CLI interface. Mock mode. (C165–C166b) | — |

### Applications (3 modules, 1,047 lines)

| Module | Lines | Purpose | Paper |
|--------|------:|---------|-------|
| `chess_e0.py` | 399 | E₀ Chess Engine: strategic dimension navigation via landscape (C72) | — |
| `chess_team.py` | 348 | E₀ Team Chess: multiverse team play with coupling (C74) | — |
| `llm_cocognition.py` | 300 | LLM Co-Cognition: 2 LLMs coupled via multiverse peer protocol (C71) | — |

---

## 3. Escalation Architecture (Controller)

The controller's `select_next()` differentiates four failure modes, each with a distinct recovery strategy:

```
select_next(current)
  │
  ├─ neighbors exist?
  │    ├─ YES, OI > threshold + peer_fn → OVERLOADED  (C63: consult peer)
  │    ├─ YES, all recent              → EXHAUSTED    (least-recently-visited)
  │    └─ YES, clear                   → NONE         (argmin S_penalized)
  │
  └─ no neighbors?
       ├─ raw edges exist but fail K11 → FILTERED     (lower threshold)
       └─ no edges at all              → DEAD_END     (field-based global jump)
```

**Overload Index** (C63): OI = N_admissible × (1 − mean|trace_quality|)  
Many paths × little experience = overwhelmed. When OI > threshold, `peer_fn(landscape, current, neighbors)` is called — an external system (another E₀, an LLM, a human) helps prioritize.

---

## 4. Reflexion Architecture (Layer 5)

Three stages of self-modification, corresponding to increasing structural depth:

```
                    ┌───────────────────────────────┐
  Stufe 1 (C43)    │  Self-Graph — observe which    │
  "I see what I    │  components contribute to      │
   am doing"       │  success/failure               │
                    └──────────┬────────────────────┘
                               │
                    ┌──────────▼────────────────────┐
  Stufe 1R (C47)   │  Dual Reflection — diagnose    │
  "I understand    │  domain + self simultaneously  │
   why"            │  → assessment + recommendations│
                    └──────────┬────────────────────┘
                               │
                    ┌──────────▼────────────────────┐
  Stufe 2 (C49/    │  Reflexive Action — mutate     │
  C56/C57/C59)     │  landscape topology based on   │
  "I change my     │  reflexive diagnosis            │
   own structure"  │  (reactive, proactive, integ.) │
                    └──────────┬────────────────────┘
                               │
                    ┌──────────▼────────────────────┐
  Stufe 3 (C62/    │  Cross-Reflexion — foreign     │
  C63)             │  experience informs own         │
  "The other's     │  hypotheses (multiverse)       │
   experience      │                                │
   informs mine"   └───────────┬───────────────────────────┘
                               │
                    ┌──────────▼────────────────────┐
  Stufe 4 (C109–   │  Dream Mode — passive cross-   │
  C112)            │  domain pattern recognition     │
  "I dream of      │  via EdgeFingerprints,           │
   structural      │  equivalences, and bridge        │
   bridges"        │  hypothesis generation           │
                    └───────────────────────────────┘
```

### Self-Graph Attribution Mechanism (C43/C147)

The Self-Graph applies \*the same historization\* that E₀ uses on domains to its own
operational structure. After each controller step, `self_historize(active_components, outcome)`
records the step's outcome on all edges whose endpoints are both in the active set.

**Differential Sampling:** Core components (6) are always active. Modulation components
(curvature, overlap) are only active when their flag is True. This creates asymmetric
quality accumulation:

```
  Period A: core=ON, overlap=OFF  → 20 × SUCCESS
  Period B: core=ON, overlap=ON   → 10 × FAILURE
  Period C: core=ON, overlap=OFF  → 10 × SUCCESS

  Result:
    q(core)    = (30 - 10) / (30 + 10) = +0.500  (diluted but healthy)
    q(overlap) = ( 0 - 10) / ( 0 + 10) = -1.000  (pure failure)
```

**Bulk Attribution:** All active components receive the same outcome simultaneously.
No per-component measurement exists. Attribution arises from *which components were
active during which periods* — correlation, not causation.

**Meta-Control:** `diagnose_self_graph()` classifies components by quality threshold
(harmful < -0.2, confused |q| < 0.1, healthy otherwise). Only modulation components
can be deactivated — core components are structurally protected. Deactivation is a
flag toggle (reversible in O(1)), making correlation-based decisions safe.

---

## 5. Multiverse Architecture (Layer 6)

```
  Universe A ←──→ Coupling Landscape ←──→ Universe B
  (own L, H)      (bidirectional edges,    (own L, H)
                    NoveltyGate outcomes)

  Turn N:
    1. Snapshot before (state_count, edge_count, total_delta)
    2. Turn function: navigate active, interact with passive
    3. Snapshot after
    4. NoveltyGate: new_states, new_edges, delta_growth → SUCCESS/FAILURE
    5. Historize coupling edge with outcome
    6. If convergence detected → apply_divergence_pressure()

  Divergence pressure:
    - New coupling mode (mode_N) with fresh low-R edges
    - Exploration edges in each universe (least-connected pair)
    - Applied DURING next turn (between snapshots) so NoveltyGate sees it

  Cross-Reflexion (C62):
    - At frontier: blend own + donor experience patterns
    - coupling_discount (0–1) controls trust in foreign experience
    - Proposes NEW edges that existed in neither universe
```

---

## 6. Hybrid Selection Modes

| Mode | Selection Rule | When to Use |
|------|----------------|-------------|
| `GREEDY` | argmin S_penalized | Baseline deterministic |
| `AMPLITUDE_ON_DISAGREE` | Override greedy when amplitude disagrees + confidence ≥ threshold | Default — trap avoidance |
| `BORN_SAMPLING` | Sample from P ∝ I (Born rule) | Exploration, multi-goal, distributional |

All three share the same controller core. They differ only in the final action selection step.

---

## 7. Key Equations

| Symbol | Formula | Module |
|--------|---------|--------|
| S(e) | Δ(e) · R_eff(e) | `tension.py` |
| R_eff(e) | R₀(e) + δ_H(e) | `historization.py` |
| C(e) | exp(−S(e)) | `tension.py` |
| Ψ(p) | exp(−S(p)) · exp(iΘ(p)) | `wavepath.py` |
| I(a) | \|Σ_p Ψ(p)\|² | `wavepath.py` |
| Θ(p) | Σ_{e∈p} ω(e) | `connection.py` |
| M_H | triangle_support · edge_overlap | `overlap.py` |
| I(e) | 1 − α · m/(m+μ) · (1−\|q\|) | `historization.py` (C42/C99) |
| S_pen | S_eff / (M_H · I) · (1 + α·𝟙[revisit]) | `controller.py` (C98/C99) |
| ℓ | m̄ / (m̄ + μ), μ = |E|/|V| | `scoped_reflexion.py` (C101, C105) |
| r | max(1, ⌈(1−ℓ)·D⌉) | `scoped_reflexion.py` (C101) |
| OI(x) | N_admissible × (1 − mean\|q\|) | `controller.py` (C63) |

---

## 8. Test Infrastructure

**4265 tests**, 0 failures (2026-04-08) across **121 test files**.

**Recent explorations (C169–C183):** Compatibility calibration (C169), partial matching — negative (C170), asymmetric teaching — topology dominates (C171), adversarial stability (C172–C174), causal binding — emergent (C175–C178), N-domain mesh N=3 (C179), N=5 (C180), dream transitivity (C181), saturation point (C182), E2E multiverse (C183).

| Category | Test Files | Tests |
|----------|-----------|-------|
| Core (L1–L4) | ~25 files | ~1400 |
| Reflexion (L5) | ~13 files | ~530 |
| Multi-System (L6) | 3 files (multiverse, cross_reflexion, overload) | 69 |
| Benchmarks | 10 files | ~400 |
| Infrastructure (L7) | ~15 files | ~600 |
| Observation (L8) | 4 files | ~160 |
| Modulation & Locality (C98–C108) | 5 files | ~140 |
| Dream Mode (L9, C109–C112, C134b–C139) | 2 files | ~130 |
| Human Communication (L12, C158–C162) | 5 files | 164 |
| UI Rendering + Pretraining (L13, C163–C164) | 2 files | 68 |
| Session Runner (L14, C165–C166b) | 1 file | 36 |
| Causal + Mesh + Transitivity (C176–C181) | 4 files | ~80 |
| Saturation + E2E (C182–C183) | 2 files | 69 |

---

## 9. Runtime Configuration

| Component | Description |
|-----------|-------------|
| `E0Envelope` | Typed, frozen controller config: mode, geometry, thresholds, transport |
| `ExplorationPolicy` | Per-iteration mode switching: Born warmup → exploit, convergence threshold |
| `TransportRegime` | Interference algebra: U1 (ℂ¹), SU2_MINIMAL, SU2_GEOMETRIC (ℂ²) |
| `HorizonStrategy` | Dynamic overlay depth: fixed, topology_adaptive, capped_adaptive |

---

## 10. Paper Coverage Matrix

| Layer | Covered in Papers | Gaps |
|-------|-------------------|------|
| L1 Primitives | P1–P4 | — |
| L2 Inscription | P1 | — |
| L3 Field Theory | P1–P3 | resonator (only ARCH) |
| L4 Controller | P1, P4 | dynamic_horizon, exploration_policy (only ARCH) |
| L5 Reflexion | P4 | structural_mutation, self_tuning (only ARCH) |
| L5 Reflexion (Scoped) | P5 | — |
| L6 Multi-System | — | Multiverse coupling (paper candidate) |
| L7 Infrastructure | Partial | bootstrapper, provenance, canon_*, residual_tension |
| L8 Observation | — | O-Landscape, controller, rendering (architectural doc exists) |
| L9 Dream Mode | P6 | — |
| Applications | — | Chess, LLM Co-Cognition (architectural docs exist) |
| Benchmarks | P1, P4, P5 | C53, C61 uncovered |

---

## 11. Dependency Graph (imports)

```
primitives ← tension ← landscape ← historization
                            ↑
              connection ←──┤
              potential  ←──┤
              wavepath   ←──┤
              overlap    ←──┘
                            │
              controller ←──┘ ← amplitude_overlay ← dynamic_horizon
                   ↑
    self_graph ←───┤
    dual_reflection ←──┤
    reflexive_edge_proposal ←──┤
    reflexive_action ←──┤
    integrated_reflexion ←──┤
                   │
    multiverse ←───┤ ← cross_reflexion
                   │
    session ←──────┤ ← memory_os ← evaluation ← reflection
                   │
    llm_adapter ←──┘ ← bootstrapper ← canon_loader
                       ← provenance
                       ← graph_validation
                   │
    dream_mode ←───┤ ← cross_reflexion (equivalences, bridges)
                   │
    chess_e0 ←─────┤ ← landscape, controller
    chess_team ←───┘ ← multiverse
```

---

## 12. Documentation Pointers

| Topic | Document |
|-------|----------|
| Formal theory | `canon/e0-canonical-reference.txt` |
| Math ↔ Code mapping | `docs/E0_MATH_IMPL_MAPPING_v1.md` |
| Paper 1 (Interference) | `docs/papers/PAPER1_MANUSCRIPT_v1.md` |
| Paper 2 (Spinor/Born) | `docs/papers/PAPER2_MANUSCRIPT_v1.md` |
| Paper 3 (Non-Abelian) | `docs/papers/E0_PAPER3_NON_ABELIAN_STRUCTURE_v1.md` |
| Paper 4 (Reflexivity) | `docs/papers/PAPER4_MANUSCRIPT_v1.md` |
| Paper 5 (Emergent Locality) | `docs/papers/PAPER5_MANUSCRIPT_v1.md` |
| Paper 6 (Dream Mode) | `docs/papers/PAPER6_MANUSCRIPT_v1.md` |
| Multiverse Design | `docs/E0_MULTIVERSE_DESIGN_v1.md` |
| Observation UI Architecture | `docs/E0_OBSERVATION_UI_ARCHITECTURE_v1.md` |
| Observation Onboarding | `docs/E0_OBSERVATION_ONBOARDING_v1.md` |
| Dream Mode Concept | `docs/E0_DREAM_MODE_CONCEPT_v1.md` |
| Structural Entropy Design | `docs/E0_STRUCTURAL_ENTROPY_DESIGN_v1.md` |
| Ontodynamics Canon Analysis | `docs/E0_ONTODYNAMICS_CANON_ANALYSIS_v1.md` |
| Test Registry | `docs/E0_TEST_REGISTRY_v2.md` |
| Empirical Insights | `docs/E0_EMPIRICAL_INSIGHTS_v1.md` |
| Canon Alignment | `docs/E0_CANON_ALIGNMENT_v1.md` |
| Human Communication Design | `docs/E0_HUMAN_COMMUNICATION_DESIGN_v1.md` |

---

## 13. C122 — Ontodynamics Canon v2.0 and Epistemic Corrections

### C122: Canon Renewal (51 nodes, 93 edges)

The ontodynamics JSON canon was rebuilt from scratch:
- **v1.2** (19 nodes, 31 edges, German IDs) → **v2.0** (51 nodes, 93 edges, English IDs)
- 18 derivation levels (0-8 canonical, 9-17 implementation)
- Edge types: canonical (31), border (13), implementation (42), feedback (7)
- Goal states: `negative_necessity`, `sleep_wake_cycle`

### C122b: German ID Cleanup

All navigation code updated from German to English state identifiers.

### C122c: Dead-End Repair

7 implementation nodes were topological sinks (0 outgoing edges). Added 7 feedback edges to close them. Only goal states remain as sinks.

### C122d: Epistemic Liveness ("Zweifel zuzulassen")

**Problem discovered:** 50/93 edges had `s_eff = 0` (epistemically dead). Root cause: initial U=8-10 with F=0 produced `δ_H ≈ -1.5`, driving R_eff to floor. No historization possible — greedy permanently trapped in implementation layer.

**Key insight:** Without difference there is no historization, without historization no learning. The threshold `F/U < λ_s/λ_f = 0.75` determines whether unvisited edges amplify (correct: unused knowledge atrophies) or spontaneously heal (incorrect).

**Fix:** Uniform `U=2, F=1` for all 93 edges. No edge claims certainty E₀ hasn't earned. Result: all edges have `s_eff > 0` (min: 0.030), correct decay direction, reflexive action gate operational.

---

## 14. C123 — Curriculum Navigator

### Problem

A 51-node landscape cannot be learned in a single `run()` — greedy covers ~12% of edges per path. Two deeper questions:

1. **Goals are not endpoints.** The real stopping condition is *equilibrium* — when T_s stabilizes below threshold, the system has exhausted internal difference and waits for external difference.
2. **Derivation order matters.** You can't understand `resistance` without `difference`. The canon's derivation hierarchy implies a natural learning sequence.

### Solution

`curriculum.py` implements hierarchical curriculum learning:

| Component | Purpose |
|---|---|
| `CurriculumStrategy` | Generates cumulative turns from derivation levels (auto-splits into thirds) |
| `EquilibriumDetector` | Monitors T_s — equilibrium when below threshold for `patience` consecutive episodes |
| `build_scoped_landscape` | Creates sub-landscapes per turn scope |
| `transfer_historization` | Carries learned U/F traces across turns |
| `CurriculumRunner` | Orchestrates: scope → navigate → equilibrium? → next turn |

Ontodynamics default: 3 turns (levels 0–5 canonical, 0–11 border, 0–17 full). Historization persists across turns. Goal selection: highest-level goal_state within each turn's scope. Start: lowest derivation level node.

35 tests in `test_curriculum.py`.

---

## 15. C124–C128 — Language Learning via Cross-Domain Fingerprint Matching

### Problem

Can E₀ learn unknown word translations from known ones?  The system has two vocabulary graphs (EN, DE) with parallel structure.  Dream Mode compares edge fingerprints across domains — but without heterogeneous SUCCESS/FAILURE signals, all fingerprints converge identically (C124: 614 equivalences at q=0.000).

### Solution

**Partial dictionaries as reality barrier**: Known translation pairs provide the SUCCESS/FAILURE signal that creates fingerprint differentiation.  Starting from 11 known pairs (Config B), the system bootstraps new translations through iterative rounds: learn → dream → discover → expand.

**Three validation levels** (progressively stronger):

| Level | Mechanism | Effect |
|---|---|---|
| L1: Target known? | SUCCESS if target ∈ known | Bootstrap start, but causes distance collapse |
| L2: Pair-based | p(SUCCESS) = w(source) × w(target) | Prevents distance collapse, preserves diversity |
| L3: Neighborhood | w = base_w × context_score | Rejects structural false matches |

**Context score** (C128): Bidirectional neighborhood consistency.  For candidate en↔de, translate en's neighbors → check if they are de's neighbors (and vice versa).  Validates relational identity, not just isolated fingerprint similarity.

### Key Files

| File | Purpose |
|---|---|
| `canons/english_basic.json` | EN vocabulary canon (44 nodes, 64 edges) |
| `canons/german_basic.json` | DE vocabulary canon (44 nodes, 64 edges) |
| `explore_dict_learning.py` | C125: PartialDictionary, GROUND_TRUTH, config_a/b |
| `explore_bootstrap_learning.py` | C126/b: Iterative bootstrap, bijective matching |
| `explore_weighted_learning.py` | C126c: 3-tier graduation (canonical/tentative/confirmed) |
| `explore_level2_learning.py` | C127: Level-2 multiplicative validation |
| `explore_level2_cumulative.py` | C127b: Cumulative votes (falsified) |
| `explore_level3_learning.py` | C128: Level-3 neighborhood consistency |

### Results

| Experiment | Confirmed accuracy | Distance diversity | Key finding |
|---|---|---|---|
| C126 ungated L1 | 40% | collapse | Contamination cascade |
| C126c weighted L1 | 100% (4/4) | **collapse R2** | L1 floods SUCCESS |
| C127 weighted L2 | 100% (1/1) | preserved | Oscillation |
| C127b cumul L2 | **50%** (2/4) | preserved | **False matches amplified** |
| **C128 context L3** | **100%** (4/4) | preserved | Structural validation works |

Detailed results: `docs/E0_LANGUAGE_LEARNING_RESULTS_v1.md`.

## 16. C129–C137 — Monolingual Teaching + Seedless Structural Matching

### Problem

C124–C128 rely on seed dictionaries (known translation pairs) to bootstrap. Can E₀ learn translations **without any seed** — Zero-Shot?

### Architecture: Two-Phase Teaching + Playground

**Phase 1 — Monolingual Teaching (with LLM, per language, NO translation):**

Each language gets its own "teacher" that evaluates edges monolingually. The LLM never sees both languages simultaneously — no cross-language leakage.

- C133: Binary YES/NO evaluation → `historization.update(edge, outcome)`
- C134: Score 0–10 → `bootstrap_landscape(initial_U=score, initial_F=10-score)` → continuous quality spectrum via the Bootstrapper's native `_apply_confidence` mechanism

**Phase 2 — Playground (NO LLM, NO seed):**

The two children "meet" and discover translation correspondences through structural matching alone. Shared topology (isomorphic graphs) provides the "common world" — this is necessary, not cheating, because without structural correspondence the graphs are "aliens" to each other.

### Key Insight: The Correct Comparison Unit

| Approach | Compares | Best Result | Limitation |
|---|---|---|---|
| `find_equivalences` (C109) | Individual edge fingerprints (q, m, I) | 1/44 (2%) | Same-quality pairs swamp quantile |
| `find_node_equivalences` (C134b) | Sorted quality profiles per node | 9/44 (20%) | Sorting loses edge-position info |
| `find_wl_node_equivalences` (C135) | Recursive neighborhood profiles | 33/44 (75%) | 100% precision, mutual-best blocks 6 correct |
| **`find_wl_node_equivalences_hungarian` (C137)** | **WL + Hungarian optimal assignment** | **44/44 (100%)** | **100% precision, globally optimal** |
| Position-based matching (C133) | Quality at corresponding edge positions | 44/44 (100%) | Requires known topology positions (oracle) |

**"Not Edge, but Node plus recursive neighborhood"** is the right comparison unit for cross-domain structural identification.

### WL Recursive Fingerprints (C135–C136)

Weisfeiler-Leman-style iterative refinement:

- **Round 0 (C136):** Node features = 9 floats: mean_q, std_q, degree, pos_fraction, min_q, max_q, median_q, **trace_load_mean**, **trace_load_std**
- **Round k:** Aggregate (mean, std) of each neighbor feature dimension from round k−1 → append to own features
- **Depth 2:** 81-dimensional feature vector capturing 2-hop structural context

trace_load (U+F) is independent from quality (U−F)/(U+F+ε) — two edges with identical quality can have vastly different trace loads depending on bootstrapper confidence, providing a new differentiation axis.

The D0→D1 jump (25%→70%) shows that **1-hop neighborhood context is the decisive signal**. D2 refines further and eliminates false matches.

### Hungarian Optimal Assignment (C137)

C136 diagnosis: 6/10 unmatched nodes had the correct partner CLOSER in WL distance, but greedy mutual-best matching blocked them (another node "stole" the partner). The remaining 4 had genuine semantic confusions (see↔eye, take↔go).

Fix: Replace greedy mutual-best with **Hungarian algorithm** (`scipy.optimize.linear_sum_assignment`) — globally optimal 1:1 assignment minimizing total WL distance across all 44×44 pairs.

Result: **ALL 44/44 correct**, including the 4 "genuine confusions" — because global optimization avoids cascading assignment errors.

### Key Files

| File | Purpose |
|---|---|
| `explore_c133_playground.py` | LLM monolingual teaching + seedless playground (binary YES/NO) |
| `explore_c134_bootstrapper_teacher.py` | Bootstrapper as teacher (score 0–10), node-eq + WL methods |
| `explore_c135_wl_matching.py` | WL recursive neighborhood matching at depth 0/1/2 |
| `explore_c136_feature_engineering.py` | 9-dim features + unmatched diagnostics |
| `explore_c137_hungarian.py` | Hungarian optimal assignment — the breakthrough |
| `dream_mode.py` (extended) | NodeFingerprint, WLNodeFingerprint, find_wl_node_equivalences, find_wl_node_equivalences_hungarian |

### Results

| Experiment | Matching | Correct/44 | Wrong | Precision | Key finding |
|---|---|---|---|---|---|
| C131b (seed=11) | Dream edge-eq | 13 | — | — | Seed-based baseline (30%) |
| C132b (seed=8, LLM) | Bilingual validator | 20 | — | — | Wrong architecture (bilingual) |
| C133 (seedless) | Position-based | **44** | 0 | 100% | Oracle-level, needs shared positions |
| C134b (seedless) | Node sorted profile | 9 | 13 | 41% | First framework-native attempt |
| C135 D2 (seedless) | WL depth=2 (4-dim) | 33 | 0 | 100% | Framework-native, mutual-best |
| C136 D2 (seedless) | WL depth=2 (9-dim) | 34 | 0 | 100% | +trace_load features |
| **C137 (seedless)** | **WL d=2 + Hungarian** | **44** | **0** | **100%** | **BREAKTHROUGH — matches oracle** |

### Robustness Suite (C138a–c)

Systematic validation that the C137 pipeline is not a lucky configuration:

**C138a — Ablation Matrix** (18 configurations: depth × noise × algorithm):
- Hungarian+D2 = 44/44 at ALL noise levels (100/200/300)
- Hungarian wins 9/9 over mutual-best across all configurations
- More noise even helps at lower depths (richer neighborhood signal)

**C138b — Stress Test** (score noise + topology perturbation):

| Axis | Parameter | Correct/44 | Key finding |
|---|---|---|---|
| Score noise σ=0 | Gaussian on LLM scores | 44 (100%) | Baseline |
| Score noise σ=1 | | 44 (100%) | Fully robust |
| Score noise σ=2 | | 44 (100%) | WL averages absorb noise |
| Score noise σ=3 | | 42 (95%) | First drop, graceful |
| Topology +5 DE-only | Asymmetric edges | 41 (93%) | Breaks isomorphism |
| Topology +10 | | 40 (91%) | Linear degradation |
| Topology +20 | | 35 (80%) | Still no cliff-edge |
| Combined σ=2, +10 | Both axes | 38 (86%) | Graceful under dual stress |

**C138c — Scaling** (synthetic isomorphic pairs, correlated scores, +100 noise):

| Nodes | Accuracy | Wall-clock | Key finding |
|---|---|---|---|
| 50 | 100.0% | 0.5s | Perfect |
| 100 | 100.0% | 0.1s | Perfect |
| 200 | 99.3% | 0.9s | 198–200/200 |
| 500 | 99.3% | 7.8s | 494–498/500 |

- Empirical scaling: O(n^1.17) — sub-cubic, practical
- **Critical assumption:** score correlation (same edge → similar LLM score in both languages). Without correlation, accuracy drops to ~45%. With correlation: >99% at 500 nodes.

### Key Files (C138)

| File | Purpose |
|---|---|
| `explore_c138a_ablation.py` | Ablation matrix: depth × noise × algorithm (18 configs) |
| `explore_c138b_robustness.py` | Score noise + topology perturbation stress test |
| `explore_c138c_scaling.py` | Scaling to 50–500 nodes with synthetic graphs |
