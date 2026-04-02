# E₀ Architecture Overview v3

**Status:** Canonical reference  
**Date:** 2026-04-02  
**Supersedes:** E0_ARCHITECTURE_OVERVIEW_v2.md (2026-03-30)  
**Scope:** All 75+ production modules, ~21,000 lines of code, 3200 tests  
**Papers:** P1 (Structural Interference), P2 (Spinor/Born), P3 (Non-Abelian), P4 (Reflexivity), P5 (Emergent Locality)

---

## 1. Structural Layer Model

E₀ is organized in seven layers. Each layer depends only on layers above it.

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
│  Scoped Reflexion (emergent locality)                    │
├─────────────────────────────────────────────────────────┤
│  Layer 6 — MULTI-SYSTEM                                 │
│  Multiverse (Novelty Gate, Coupling), Cross-Reflexion,   │
│  Overload Escalation (peer_fn), Raumzeit Coupling        │
├─────────────────────────────────────────────────────────┤
│  Layer 7 — INFRASTRUCTURE                               │
│  Session, MemOS, LLM Adapter, Bootstrapper, Provenance,  │
│  Canon Loader/Bridge, Evaluation, Exploration Policy      │
├─────────────────────────────────────────────────────────┤
│  Layer 8 — OBSERVATION                                  │
│  O-Landscape, Observation Controller, Rendering Adapter, │
│  Service Layer, Input Pipeline                           │
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

### Layer 5 — Reflexion (8 modules, 3,978 lines)

| Module | Lines | Purpose | Paper |
|--------|------:|---------|-------|
| `self_graph.py` | 200 | Structural self-knowledge — component quality historization (C43) | P4 |
| `dual_reflection.py` | 331 | Domain + self-graph dual diagnosis (C47) | P4 |
| `reflexive_edge_proposal.py` | 322 | Hypothesis edges at frontier — reactive (C56) + proactive (C57) | P4 |
| `reflexive_action.py` | 232 | Diagnosis → concrete landscape mutation (C49) | P4 |
| `integrated_reflexion.py` | 245 | Unified C49 + C57 reflexion pipeline (C59). Scoped mode (C102): scoped=True delegates to scoped_propose_edges | P4, P5 |
| `scoped_reflexion.py` | ~250 | Locality-driven scope: ℓ = m̄/(m̄+μ), radius = max(1,⌈(1-ℓ)·D⌉). μ = |E|/|V| auto-derived (C105). Corridor mode follows inscription (C106). Fresh → global, historized → local (C101) | P5 |
| `emergent_locality.py` | ~200 | Emergence proof tooling: track locality evolution, phase transition, regional profile, convergence (C104) | P5 |
| `reflection.py` | 791 | Reflection layer — bounded self-reference, 4 triggers (Phase 3g) | P4 |
| `structural_mutation.py` | 693 | Bridge 4 — propose/apply/verify/revert topology (Stufe 2) | — |
| `self_tuning.py` | 1,164 | Meta-landscape over parameters, tuning memory (B4) | — |

### Layer 6 — Multi-System (4 modules, 891+ lines)

| Module | Lines | Purpose | Paper |
|--------|------:|---------|-------|
| `multiverse.py` | 363 | Coupled systems: NoveltyGate, divergence pressure, coupling landscape (C60) | — |
| `cross_reflexion.py` | 284 | Cross-universe reflexive edge discovery: blend_patterns, cross_propose (C62) | — |
| `raumzeit_coupling.py` | 244 | Coupling necessity theorem proof (C54) | — |
| `coupling_router.py` | ~100 | N>2 dynamic partner selection (C66/C67) | — |
| C63 in `controller.py` | ~30 | OVERLOADED escalation, peer_fn, overload_index | — |

### Layer 7 — Infrastructure (14 modules, 3,548+ lines)

| Module | Lines | Purpose | Paper |
|--------|------:|---------|-------|
| `session.py` | 491 | Lifecycle: load → run → iterate → save. ExplorationPolicy (C41) | P4 |
| `memory_os.py` | 568 | Persistent substrate: snapshots, hybrid traces, geometry | P1 |
| `llm_adapter.py` | 869 | Structured LLM interface: extract_delta, propose_states, execute_transition | — |
| `bootstrapper.py` | 182 | Structured spec → Landscape (C44) | — |
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

### Benchmarks (6 modules, 1,809 lines)

| Module | Lines | Purpose | Paper |
|--------|------:|---------|-------|
| `benchmark_domain_invariance.py` | 451 | 10 domains × zero tuning — proves universality (C53) | — |
| `benchmark_amplitude.py` | 302 | 10 domains × 3 controller modes (C55) | — |
| `benchmark_gridworld.py` | 359 | E₀ vs Naive-Greedy vs A* | P1 |
| `benchmark_reflexion.py` | 179 | 10 domains × 3 reflexion regimes (C58) | P4 |
| `benchmark_multiverse.py` | 223 | 5 cross-domain pairings (C61) | — |
| `benchmark_overloaded.py` | — | Peer consultation × 10 domains (C70) | — |
| `benchmark_cross_reflexion.py` | — | Cross-universe edge discovery (C69) | — |
| `benchmark_modulation.py` | ~220 | 14 domains × 3 modes: BASELINE/OVERLAP/FULL (C100) | P5 |
| `benchmark_scoped_reflexion.py` | ~180 | 10 domains × GLOBAL vs SCOPED (C103) | P5 |
| `validate_cross_domain.py` | 295 | Systematic demo comparison (Phase 3d) | — |

### Demos (11) and Explorations (9): 6,237 lines

Not listed individually — these are experimental tooling for interactive analysis.
Demos: `demo_beipackzettel`, `demo_ezb_zinsentscheidung`, `demo_burnout_*`, `demo_invoice_llm`, `demo_greedy_trap`, `demo_open_domain`, `demo_research_brief`, `demo_incident_postmortem`, `demo_session_persist`, `demo_canon_exposition`.
Explorations: `explore_gordian`, `explore_amplitude`, `explore_resonator`, `explore_spinor`, `explore_topology_scan`, `explore_omega_uniqueness`, `explore_g5_edge_cases`, `explore_multigoal`, `explore_historization_gordian`.

### Layer 8 — Observation (5 modules, ~700 lines)

| Module | Lines | Purpose | Paper |
|--------|------:|---------|-------|
| `observation.py` | ~160 | O-Landscape: observation as E₀ domain (scope×depth states) (C94) | — |
| `observation_controller.py` | ~200 | Navigation (focus/defocus/move/deepen/retreat) + domain projection (C95) | — |
| `rendering_adapter.py` | ~120 | Observation → wire format: edge data at each depth level (C96) | — |
| `service.py` | ~200 | FastAPI service layer: 13 REST + WebSocket endpoints (C83/C84) | — |
| `input_pipeline.py` | ~100 | Input processing, snapshot codec (C83) | — |

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
   informs mine"   └───────────────────────────────┘
```

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

**3200 tests**, 0 failures (2026-04-02) across **92 test files**.

| Category | Test Files | Tests |
|----------|-----------|-------|
| Core (L1–L4) | ~25 files | ~1400 |
| Reflexion (L5) | ~12 files | ~500 |
| Multi-System (L6) | 3 files (multiverse, cross_reflexion, overload) | 69 |
| Benchmarks | 8 files | ~350 |
| Infrastructure (L7) | ~12 files | ~550 |
| Observation (L8) | 4 files | ~160 |
| Modulation & Locality (C98–C104) | 5 files | ~140 |

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
```

---

## 12. Documentation Pointers

| Topic | Document |
|-------|----------|
| Formal theory | `canon/e0-canonical-reference.txt` |
| Math ↔ Code mapping | `docs/E0_MATH_IMPL_MAPPING_v1.md` |
| Paper 1 (Interference) | `docs/PAPER1_MANUSCRIPT_v1.md` |
| Paper 2 (Spinor/Born) | `docs/PAPER2_MANUSCRIPT_v1.md` |
| Paper 3 (Non-Abelian) | `docs/E0_PAPER3_NON_ABELIAN_STRUCTURE_v1.md` |
| Paper 4 (Reflexivity) | `docs/PAPER4_MANUSCRIPT_v1.md` |
| Paper 5 (Emergent Locality) | `docs/papers/PAPER5_MANUSCRIPT_v1.md` |
| Multiverse Design | `docs/E0_MULTIVERSE_DESIGN_v1.md` |
| Observation UI Architecture | `docs/E0_OBSERVATION_UI_ARCHITECTURE_v1.md` |
| Controller Status | `docs/E0_CONTROLLER_STATUS.md` |
| Test Registry | `docs/E0_TEST_REGISTRY_v2.md` |
| Hybrid Spec | `docs/E0_HYBRID_CONTROLLER_SPEC_v1.md` |
