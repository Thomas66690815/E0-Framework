# E₀ Framework

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19333487.svg)](https://doi.org/10.5281/zenodo.19333487)

**A structural transition framework with an executable hybrid controller — developed through human–AI collaboration.**

E₀ begins as a pre-domain structural theory of transitions.
This repository now goes further: it contains the first operational E₀ controller, including a hybrid mode that can override locally greedy choices when bounded path-family amplitude support indicates a stronger forward structure.

In practical terms, this means the repository is no longer only about a deterministic transition law. It now also contains:

- a historized structural controller,
- a phase/amplitude path layer,
- empirically tested summation geometries,
- a hybrid correction mode,
- SU(2) multi-axis spinor transport (B1),
- topological curvature modulation M_H (B2),
- self-tuning meta-layer with cross-run memory (B4),
- a session orchestrator with automatic MemOS persistence,
- persistent runtime support via MemOS,
- multiverse architecture with cross-universe reflexion (C59–C63),
- dream mode with Hungarian-optimal cross-domain pattern discovery and compatibility gating (C109–C139, C168),
- structural entropy with sleep–wake cycles (C114–C121),
- curriculum-driven canon learning (C123),
- proactive reflexion that proposes before stagnation (C57),
- an LLM adapter with embedded E₀ semantic context,
- human communication layer with learnable perception ontology (C158–C162),
- and 16 live demos covering all major capabilities.

This is not a prompt-engineering repo and not a conventional agent framework.
It is an attempt to build a structural decision layer that operates beneath semantics and can still be exposed to semantic systems.

---

## What is E₀?

E₀ is a **structural transition framework**.
It does not begin with goals, probabilities, agents, or domain-specific objects. It begins with a smaller claim:

> If a structural difference exists and a finite path is available, then non-transition is unstable.

The canonical core uses seven primitives and one axiom.

| Primitive | Symbol | Role |
|-----------|--------|------|
| State | `S` | Distinguishable configuration |
| Difference | `Δ` | Structural non-identity |
| Path | `P` | Admissible transition structure |
| Resistance | `R` | Structural inertia |
| Historization | `H` | Irreversible modification of future resistance |
| Time | `τ` | Ordering of historizations |
| Rate | `v` | Ordering tendency of realizable transitions |

**Axiom A₀:** If a difference exists and a path with finite resistance is available, transition is structurally more stable than non-transition.

**Central Law:** If Δ > 0 and an admissible finite path exists, non-transition is structurally unstable. A transition must occur.

From this core, E₀ derives: transition burden, coherence, historized learning, path dependence, phase and holonomy, complex path amplitudes, and bounded endpoint support.

The full canon: [canon/e0-canon-plain.txt](canon/e0-canon-plain.txt) — 155 lines, pure ASCII. Everything else derives from this.

---

## What exists in this repository now

This repository currently contains thirteen connected layers — from raw primitives through dreaming, curriculum learning, and self-regulated sleep–wake cycles.

### 1. Canonical E₀ core

The foundational structural layer: primitives, axiom, core transition law, and reference implementation.

### 2. Deterministic controller

A runtime controller that selects actions using historized structural burden (`S = Δ · R_eff`), admissibility, revisit handling, and escalation logic.

### 3. Amplitude path layer

A path-level extension built from:

- connection / phase Θ,
- complex path carrier Ψ(p) = exp(−S(p)) exp(iΘ(p)),
- endpoint intensity |Ψ|²,
- constructive and destructive interference,
- bounded path-family comparison.

### 4. Summation geometry comparison

The repository supports multiple summation geometries for path-family support:

- `prefix`
- `simple`
- `first_arrival`
- `goal_reaching`

These were not assumed dogmatically. They were compared empirically.
Current evidence identifies **simple-path geometry** as the strongest default for robust controller use, while `prefix` remains useful as an exploratory upper-support view. The newest geometry, **goal_reaching**, restricts superposition to paths that actually reach a goal state — aligned with the Born criterion. It resolves prefix-inflation artifacts and enables interference-based routing in topologies where other geometries fail (see Gordian Trap analysis).

### 5. SU(2) multi-axis transport and topological modulation

Two structural extensions deepen the non-Abelian and geometric character of E₀:

- **SU(2) multi-axis spinor transport (B1):** Each edge can carry its own rotation axis via `axis_fn`. The spinor connection lifts U(1) phase transport to full SU(2) matrix transport, enabling anisotropic interference patterns across geometrically complex landscapes.
- **Curvature modulation M_H (B2):** The topological invariant `M_H(x,y) = 1/(1+κ)` modulates the transition field based on local edge curvature κ derived from face holonomies. High-curvature regions naturally damp transitions. Controlled via `Landscape(curvature_modulation=True)`.

The central formula becomes:

    v(x,y) = Δ(x,y) · M_H(x,y) · exp(−S_eff(x→y))

### 6. Hybrid controller mode

The controller can run in a hybrid mode:

- **GREEDY** — pure local structural selection
- **AMPLITUDE_ON_DISAGREE** — follow the amplitude layer when it disagrees with greedy local choice and indicates a stronger forward-support structure
- **BORN_SAMPLING** — stochastic action selection proportional to amplitude-derived probabilities

This hybrid mode is integrated into MemOS and into all major LLM demos in the repository.

### 7. Self-tuning meta-layer (B4)

A four-layer self-tuning system that eliminates ad-hoc constants and enables autonomous parameter optimization:

- **B4.1 Meta-Layer:** Field-derived thresholds from run statistics replace hardcoded constants. `ParameterSensitivity` identifies which controller parameters most affect run quality.
- **B4.2 Feedback Loop:** Closed run→diagnose→adjust→verify cycle with quality score `Q ∈ [0,1]`.
- **B4.3 Cross-Run Memory:** `TuningMemory` accumulates quality trends, recurring issues, and parameter drift across runs, persisted via MemOS.
- **B4.4 True Sensitivity:** Perturbation-based `∂Q/∂θ` via finite differences for empirical gradient-based parameter proposals.

### 8. Session orchestrator

A thin orchestration layer between the controller and MemOS persistence:

```python
session = Session("my-session", landscape, execute_fn)
result  = session.run("START", goal="GOAL")
# → context, run record, and tuning memory auto-saved to disk

# Later / new process:
session2 = Session.resume("my-session", execute_fn)
result2  = session2.run("START", goal="GOAL")
# → picks up where it left off (historization, params, memory)
```

The controller stays pure — zero persistence awareness. The Session handles the lifecycle.

### 9. Interference-based routing (Gordian Trap)

The framework now includes a constructive proof that the amplitude layer can route through structurally deceptive topologies:

- A **Gordian Trap** topology offers a greedy-attractive short path and a loop-laden alternative to the same goal.
- The holonomy (accumulated phase difference) between the two path families is controlled by the transition field `v` on forward edges.
- With `goal_reaching` geometry and sufficient horizon, the amplitude layer correctly identifies the coherent path and overrides the greedy choice.

Key theoretical result: the holonomy ΔΘ between two paths is **independent of back-edges** — the Helmholtz potential Φ cancels exactly. Only raw `v` values on forward edges contribute:

    ΔΘ = ½ [Σ v(loop edges) − Σ v(short edges)]

See `e0_controller/test_gordian_trap.py` for 44 formal tests (17 interference routing + 12 historization stability + 15 multi-goal G5) and `docs/E0_PHASE3Q_INTERFERENCE_REPORT_v1.md` for the full scientific report.

### 10. Multiverse architecture (C59–C61)

Multiple E₀ controller instances (Universes) run in parallel on cloned landscapes and exchange structural knowledge:

- **NoveltyGate** — prevents universes from collapsing onto the same path by rejecting edge proposals that are too similar to existing knowledge.
- **Divergence pressure** — injects structural perturbation when universes begin to converge, maintaining exploratory diversity.
- **Knowledge exchange** — universes share historization patterns and discovered edges after each turn cycle.
- **Overload escalation (C63)** — when a universe faces too many unexplored paths with insufficient experience, it can escalate to a peer callback for guidance. The Overload Index `OI = N × (1 − mean|trace_quality|)` triggers when exceeding a configurable threshold.

The multiverse resolves a fundamental tension: a single controller's historization narrows its future options (Δ-Kollaps). Multiple coupled controllers maintain structural diversity while sharing useful discoveries.

### 11. Cross-universe reflexive edge discovery (C62)

A reflexion layer that operates *across* universes rather than within a single run:

- **Pattern blending** — merges a universe's own edge-pattern history with a foreign donor's patterns, weighted by a coupling discount (default 0.5).
- **Cross-proposal engine** — generates hypothesis edges from blended patterns, subject to confidence caps (0.7) that are deliberately lower than self-reflexion (0.8) to reflect epistemic humility about foreign experience.
- **Integration** — `cross_reflexion_turn()` plugs directly into `MultiverseController` as a `TurnFn`, enabling cross-reflexive edge discovery as part of the standard multiverse cycle.

### 12. Dream mode and structural entropy (C109–C121)

Two complementary systems that handle what a learning system eventually *must* handle: pattern recognition across domains, and forgetting.

- **Dream Mode (C109–C139, C168)** — Passive cross-domain pattern recognition. `DreamObserver` monitors N domains, computes edge fingerprints and node-level equivalences (WL recursive + Hungarian optimal assignment), and generates bridge hypotheses. **Compatibility gating (C168):** mean WL distance under Hungarian assignment pre-filters domain pairs — incompatible pairs (distance > threshold) are skipped, reducing noise by ~59% (edge-EQ) and ~67% (node-EQ). No active navigation — dreaming is observation, not action.
- **Structural Entropy (C114–C120)** — Structural temperature T_s measures landscape disorder. Type 1 (inscription threshold): conditional inscription based on novelty. Type 2 (anchors + decay): remove low-value edges and states to prevent overload.
- **Sleep–Wake Cycle (C121)** — Automatic rhythm: wake phase builds experience, sleep phase consolidates (dream + decay). Dream pressure `p = T_s/(T_s+μ)` triggers sleep when disorder is high.

### 13. Curriculum and bootstrapping (C44, C123)

Two systems that solve cold-start and hierarchical learning:

- **Bootstrapper (C44)** — Converts domain specifications (LLM-generated or manual) into valid E₀ Landscapes. The bridge from semantic descriptions to structural operation.
- **Curriculum Navigator (C123)** — Divides canonical knowledge into derivation levels and learns them in cumulative turns. Each turn builds a scoped sub-landscape, runs until T_s equilibrium, and transfers historization to the next. "E₀ learns E₀" on the ontodynamics canon.

---

## Documentation quick links

- [Architecture overview v4](docs/E0_ARCHITECTURE_OVERVIEW_v4.md) — 14-layer model with all 70+ production modules
- [Multiverse design](docs/E0_MULTIVERSE_DESIGN_v1.md) — C54–C63 architecture, coupling theorem, benchmarks
- [Integration Stories](docs/E0_INTEGRATION_STORIES_v1.md) — prioritized demo + integration roadmap (C139–C144)
- [Evidence & falsification status](docs/E0_EVIDENCE_AND_FALSIFICATION_STATUS_v1.md) — what is demonstrated vs open
- [External validation / handoff note](docs/E0_EXTERNAL_VALIDATION_AND_HANDOFF_NOTE_v1.md) — package for reviewers or AI systems
- [Phase 3q interference report](docs/E0_PHASE3Q_INTERFERENCE_REPORT_v1.md) — holonomy formula, goal_reaching geometry, Gordian Trap
- [Paper 3: Non-Abelian Structure](docs/papers/E0_PAPER3_NON_ABELIAN_STRUCTURE_v1.md) — SU(2) transport, curvature modulation, topological invariants
- [Test Registry v2](docs/E0_TEST_REGISTRY_v2.md) � complete per-file test inventory (4171 tests)
- [Empirical Insights](docs/E0_EMPIRICAL_INSIGHTS_v1.md) — what Chess (C72) reveals about E₀ as a whole
- [Dream Mode Concept](docs/E0_DREAM_MODE_CONCEPT_v1.md) — cross-domain pattern recognition through passive observation (C109–C139, C168–C171)
- [Multi-Domain Dream Analysis](docs/E0_MULTI_DOMAIN_DREAM_ANALYSIS_v1.md) — compatibility gating empirical analysis (C168–C171, all 4 questions closed)
- [Asymmetric Teaching Research](docs/research/E0_ASYMMETRIC_TEACHING_RESEARCH_v1.md) — training effect=0, topology dominates (C171)
- [Strategic Roadmap](docs/E0_STRATEGIC_ROADMAP_v1.md) — post-C171 priorities: adversarial stability → semantic binding → N-domain mesh
- [Structural Entropy Design](docs/E0_STRUCTURAL_ENTROPY_DESIGN_v1.md) — forgetting as structural necessity (C114–C121)
- [Language Learning Results](docs/E0_LANGUAGE_LEARNING_RESULTS_v1.md) — cross-domain translation via structural fingerprints (C124–C137)
- [Observation UI Architecture](docs/E0_OBSERVATION_UI_ARCHITECTURE_v1.md) — O-Landscape projection and navigation (C94–C97)
- [LLM Bootstrap Architecture](docs/E0_LLM_BOOTSTRAP_ARCHITECTURE_v1.md) — E₀=Skeleton, LLM=Muscle (C43–C47)
- [Human Communication Design](docs/E0_HUMAN_COMMUNICATION_DESIGN_v1.md) — learnable perception + intent + UISpec emission (C158–C162)

---

## What is new here

Many systems can rank local actions.
What is unusual here is the combination of:

- historized structural burden,
- non-probabilistic transition enforcement,
- path-phase structure,
- bounded amplitude superposition,
- empirically tested summation geometry,
- hybrid correction of local greedy decisions,
- emergent locality (scope narrows with experience),
- dream mode (cross-domain pattern recognition through passive observation),
- structural entropy (forgetting as structural necessity),
- and curriculum learning (hierarchical canon acquisition with equilibrium detection).

In plain language:

> The controller does not only ask which next step is locally cheapest. It can also ask which next step belongs to the strongest coherent family of futures.

---

## How the hybrid controller works — an example

Consider a simple structure:

```text
A → C → A   (loop / trap)
A → B → E → G → GOAL   (forward path)
```

**Local (greedy) view:** At state A, the deterministic controller evaluates immediate burden. A → C has lower local cost, so greedy chooses C. This leads into a loop (A ↔ C) and delays progress toward the goal.

**Amplitude (path-family) view:** The amplitude layer evaluates *families of future paths* starting from each action. Paths through C mostly cycle back; paths through B continue toward GOAL and form a coherent forward family. The amplitude layer assigns higher support to A → B.

**Hybrid decision:** In `AMPLITUDE_ON_DISAGREE` mode, greedy choice = C, amplitude choice = B. Since they disagree, the controller follows the amplitude-supported action: A → B → E → G → GOAL.

The key difference is not about randomness or heuristics:

- **Greedy:** "choose the cheapest next step"
- **Hybrid:** "choose the step whose future *structure* is strongest"

Run this example yourself: `python -m e0_controller.demo_greedy_trap`

---

## Current state

*Last updated: 2026-04-05*

| Component | Status | Where |
|-----------|--------|-------|
| Canon (7 primitives, Axiom A₀) | **Stable** | `canon/` |
| Deterministic controller (§2–18) | **Active** | `e0_controller/controller.py` |
| Amplitude overlay | **Active** (4 geometries) | `e0_controller/amplitude_overlay.py` |
| Summation geometry comparison | **Completed** (empirical + G5) | `docs/E0_SUMMATION_GEOMETRY_COMPARISON_v1.md` |
| Hybrid controller mode | **Active** (`hybrid_geometry` param) | `e0_controller/controller.py` |
| SU(2) multi-axis transport (B1) | **Active** (36 tests) | `e0_controller/spinor_connection.py` |
| Curvature modulation M_H (B2) | **Active** (35 tests) | `e0_controller/connection.py`, `landscape.py` |
| Interference routing | **Demonstrated** (Gordian Trap) | `e0_controller/test_gordian_trap.py` |
| Topology classification | **Demonstrated** (380-graph scan, 23 tests) | `e0_controller/test_topology_classification.py` |
| G5 edge case suite | **Stressed** (5 families, 28 tests) | `e0_controller/test_g5_edge_cases.py` |
| B4 Self-Tuning Meta-Layer | **Active** (87 tests) | `e0_controller/self_tuning.py` |
| Session Orchestrator | **Active** (13 tests) | `e0_controller/session.py` |
| MemOS (hybrid-aware persistence) | **Active** — full roundtrip for SU(2), curvature, escalation context | `e0_controller/memory_os.py` |
| LLM Adapter (canon-enriched) | **Active** — live API confirmed | `e0_controller/llm_adapter.py` |
| LLM demo hybrid integration | **Active** (4 demos) | `e0_controller/demo_*.py` |
| LLM integration tests | **Active** (32 live tests) | `e0_controller/test_llm_integration.py` |
| Scaling tests | **Active** (14 tests, n≤500) | `e0_controller/test_scaling.py` |
| Evaluation layer (hybrid-extended) | **Active** | `e0_controller/evaluation.py` |
| Reflection layer | **Active** | `e0_controller/reflection.py` |
| Cross-domain validation | **Active** (3 domains, hybrid) | `e0_controller/validate_cross_domain.py` |
| Graph validation | **Active** | `e0_controller/graph_validation.py` |
| Scenario packets | **Active** (3 domains) | `scenarios/` |
| Formal Paper (E₀ mathematics) | **Draft v1** | `docs/papers/E0_FORMAL_PAPER_DRAFT_v1.md` |
| Formal Paper v2 (+ benchmark) | **Draft v2** | `docs/papers/E0_FORMAL_PAPER_DRAFT_v2.md` |
| Paper 3 (Non-Abelian Structure) | **Draft** | `docs/papers/E0_PAPER3_NON_ABELIAN_STRUCTURE_v1.md` |
| Multi-agent network + experiments | **Archived** | `_archive/` |
| Core reference implementation | **Archived** | `_archive/e0_core/` |

| 4-Layer Model (C42) | **Active** (37 tests) | `e0_controller/historization.py` |
| Self-Graph (C43) | **Active** (47 tests) | `e0_controller/self_graph.py` |
| Bootstrapper (C44) | **Active** (41 tests) | `e0_controller/bootstrapper.py` |
| Mode Controller (C46) | **Active** (36 tests) | `e0_controller/mode_controller.py` |
| Dual Reflection (C47) | **Active** (36 tests) | `e0_controller/dual_reflection.py` |
| Canon Loader (C48) | **Active** (72 tests) | `e0_controller/canon_loader.py`, `canons/ontodynamics.json` |
| Canon ↔ Self-Graph Bridge (C48) | **Active** (32 tests) | `e0_controller/canon_self_bridge.py` |
| Reflexive Action (C49) | **Active** (41 tests) | `e0_controller/reflexive_action.py` |
| Reflexive Journal (C50) | **Active** (37 tests) | `e0_controller/reflexive_action.py`, `canon_self_bridge.py` |
| System Integration (C51) | **Active** (19 tests) | `e0_controller/test_system_integration.py` |
| Honest Self-Knowledge (C52) | **Active** (19 tests) | `e0_controller/canon_self_bridge.py` |
| Domain-Invariance Benchmark (C53) | **Active** (30 tests) | `e0_controller/benchmark_domain_invariance.py` |
| Raumzeit Coupling (C54) | **Active** (23 tests) | `e0_controller/raumzeit_coupling.py` |
| Amplitude Benchmark (C55) | **Active** (23 tests) | `e0_controller/benchmark_amplitude.py` |
| Reflexive Edge Proposal (C56) | **Active** (23 tests) | `e0_controller/reflexive_edge_proposal.py` |
| Proactive Reflexion / Stufe 2 (C57) | **Active** (20 tests) | `e0_controller/reflexive_edge_proposal.py` |
| Reflexion Benchmark (C58) | **Active** (20 tests) | `e0_controller/benchmark_reflexion.py` |
| Multiverse Controller (C59–C61) | **Active** (23+ tests) | `e0_controller/multiverse.py` |
| Cross-Reflexion (C62) | **Active** (19 tests) | `e0_controller/cross_reflexion.py` |
| Overload Escalation (C63) | **Active** (15 tests) | `e0_controller/controller.py` |
| OVERLOADED Benchmark (C70) | **Active** (26 tests) | `e0_controller/benchmark_overloaded.py` |
| LLM Co-Cognition (C71) | **Active** (28+12 tests) | `e0_controller/llm_cocognition.py` |
| Chess Engine (C72) | **Active** (26 tests) | `e0_controller/chess_e0.py` |
| Primitive Extensions (C73) | **Active** (18 tests) | `landscape.py`, `historization.py` |
| Team Chess (C74) | **Active** (22 tests) | `e0_controller/chess_team.py` |
| Bootstrap Architecture (C43–C47) | **Complete** | `docs/E0_LLM_BOOTSTRAP_ARCHITECTURE_v1.md` |
| Overlap Modulation (C98) | **Active** (26 tests) | `e0_controller/overlap.py`, `controller.py` |
| Inertia Dampening (C99) | **Active** | `e0_controller/historization.py`, `controller.py` |
| Modulation Benchmark (C100) | **Active** (32 tests) | `e0_controller/benchmark_modulation.py` |
| Scoped Reflexion (C101–C106) | **Active** (42 tests) | `e0_controller/scoped_reflexion.py` |
| Emergent Locality (C104) | **Active** (29 tests) | `e0_controller/emergent_locality.py` |
| Dream Mode (C109–C112, C168) | **Active** (113 tests) | `e0_controller/dream_mode.py` |
| Structural Entropy (C114–C120) | **Active** (101 tests) | `e0_controller/structural_entropy.py` |
| Sleep–Wake Cycle (C121) | **Active** (10 tests) | `e0_controller/sleep_wake.py` |
| Curriculum Navigator (C123) | **Active** (35 tests) | `e0_controller/curriculum.py` |
| Language Learning (C124–C137) | **Active** (explorations) | `e0_controller/explore_*_learning.py` |
| Hungarian Node Matching (C137–C139) | **Active** (DreamObserver wired) | `e0_controller/dream_mode.py` |
| Bootstrap Demo (C140) | **Active** (16 demos total) | `e0_controller/demo_bootstrap_domain.py` |
| Multiverse Demo (C142) | **Active** | `e0_controller/demo_multiverse.py` |
| Curriculum Demo (C143) | **Active** | `e0_controller/demo_curriculum.py` |
| Reflexion Demo (C144) | **Active** | `e0_controller/demo_reflexion.py` |
| Self-Graph Demo (C147) | **Active** (21 tests) | `e0_controller/demo_self_graph.py` |
| E0Config Registry (C148) | **Active** (28 tests) | `e0_controller/config.py` |
| Parameter Sensitivity (C150–C153) | **Active** (66+35 tests) | `e0_controller/parameter_sensitivity.py`, `perspective_diagnostic.py` |
| Dream Node Bridges (C154) | **Active** (32 tests) | `e0_controller/dream_mode.py`, `sleep_wake.py` |
| Auto-Tuning (C155) | **Active** (25 tests) | `e0_controller/parameter_sensitivity.py`, `session.py` |
| Curriculum ↔ Sleep-Wake (C156) | **Active** (14 tests) | `e0_controller/curriculum.py` |
| Dream → CouplingRouter (C157) | **Active** (15 tests) | `e0_controller/coupling_router.py` |
| Perception Ontology (C158) | **Active** (48 tests) | `e0_controller/perception.py` |
| Communication Intent (C159) | **Active** (42 tests) | `e0_controller/communication.py` |
| UI-Schema Emitter (C160) | **Active** (32 tests) | `e0_controller/ui_emitter.py` |
| Human Feedback Loop (C161) | **Active** (30 tests) | `e0_controller/feedback.py` |
| Human Communication PoC (C162) | **Active** (12 tests) | `e0_controller/demo_human_communication.py` |
| UI Renderer (C163) | **Active** (38 tests) | `e0_controller/ui_renderer.py` |
| Learnable Rendering (C164) | **Active** (30 tests) | `e0_controller/visual_pretraining.py` |
| Session Runner (C165) | **Active** (15 tests) | `e0_controller/e0_session.py` |
| Task-Aware Intents (C166) | **Active** (12 tests) | `e0_controller/e0_session.py` |
| LLM-Derived Endpoints (C166b) | **Active** (9 tests) | `e0_controller/e0_session.py` |
| Infrastructure Hardening (C167) | **Active** (conftest.py) | `e0_controller/conftest.py` |
| Compatibility-Gated Dreaming (C168) | **Active** (15 tests) | `e0_controller/dream_mode.py` |
| Compatibility Calibration (C169) | **Active** (exploration) | `e0_controller/explore_compatibility_threshold.py` |
| Partial Matching (C170) | **Closed** (negative) | `e0_controller/explore_partial_matching.py` |
| Asymmetric Teaching (C171) | **Closed** (topology dominates) | `e0_controller/explore_asymmetric_teaching.py` |

**Tests:** 4171 total (pytest), 0 failures, 0 warnings, 41 conditional (live LLM � require API key). See [`docs/E0_TEST_REGISTRY_v2.md`](docs/E0_TEST_REGISTRY_v2.md) for per-file details.

---

## Quickstart

**Requirements:** Python 3.11+

```bash
git clone https://github.com/Thomas66690815/E0-Framework.git
cd E0-Framework
```

### Install as a package (editable)

```bash
pip install -e .
```

This makes `e0_controller` importable from anywhere:

```python
from e0_controller import E0Controller, Landscape, Session, Outcome
```

### Run the tests (no API key needed)

```bash
# Full test suite (4171 tests, pytest):
py -3 -m pytest e0_controller/ --tb=short -q

# Single file:
py -3 -m pytest e0_controller/test_controller.py -v --tb=short
```

> **Windows note:** Use `py -3` instead of `python` to ensure the correct Python version.

### Run a demo (mock mode — no API key needed)

```bash
# Core framework demos:
py -3 -m e0_controller.demo_greedy_trap              # Greedy trap vs hybrid routing
py -3 -m e0_controller.demo_session_persist           # MemOS save + resume
py -3 -m e0_controller.demo_canon_exposition          # Canon falsification test

# LLM-bootstrapped demos (mock mode):
py -3 -m e0_controller.demo_invoice_llm --mock        # Invoice processing
py -3 -m e0_controller.demo_open_domain --mock         # Arbitrary task → Landscape
py -3 -m e0_controller.demo_research_brief --mock      # Paper abstract → brief
py -3 -m e0_controller.demo_incident_postmortem --mock # Incident postmortem
py -3 -m e0_controller.demo_beipackzettel             # Real-world: medication insert
py -3 -m e0_controller.demo_ezb_zinsentscheidung      # Real-world: ECB policy
py -3 -m e0_controller.demo_burnout_composite         # Multi-perspective burnout
py -3 -m e0_controller.demo_burnout_iterate           # Iterative equilibrium

# Advanced capability demos (C140–C147):
py -3 -m e0_controller.demo_bootstrap_domain          # Cold-start LLM → Landscape
py -3 -m e0_controller.demo_multiverse                # Coupled domains + dream discovery
py -3 -m e0_controller.demo_curriculum                # Level-by-level canon learning
py -3 -m e0_controller.demo_reflexion                 # Reactive vs proactive reflexion
py -3 -m e0_controller.demo_self_graph                # Self-Graph: E0 learns its own components
```

All advanced demos support `--entropy` for structural entropy / sleep-wake consolidation:

```bash
py -3 -m e0_controller.demo_bootstrap_domain --entropy
py -3 -m e0_controller.demo_multiverse --entropy
py -3 -m e0_controller.demo_curriculum --entropy
py -3 -m e0_controller.demo_reflexion --entropy
py -3 -m e0_controller.demo_self_graph --entropy
```

### Run a hybrid demo

```bash
py -3 -m e0_controller.demo_invoice_llm --mock --hybrid
py -3 -m e0_controller.demo_open_domain --mock --hybrid
py -3 -m e0_controller.demo_research_brief --mock --hybrid
py -3 -m e0_controller.demo_incident_postmortem --mock --hybrid
```

### Run cross-domain validation

```bash
py -3 -m e0_controller.validate_cross_domain
py -3 -m e0_controller.validate_cross_domain --hybrid
```

### Read the canon

[canon/e0-canon-plain.txt](canon/e0-canon-plain.txt) — 155 lines. This is where E₀ begins.

### See E₀ without any AI

The original reference implementation is preserved in `_archive/e0_core/`.
The active controller in `e0_controller/` demonstrates the full transition framework.

---

## Repository structure

```
E0-Framework/
│
├── canon/                            The structural definitions — what E₀ IS
│   ├── e0-canon-plain.txt              Plain-language canon (155 lines)
│   ├── e0-canonical-reference.txt      Formal canonical reference
│   ├── ontodynamics.txt                Pre-physical transition structure
│   └── e0-agi-blueprint.md             Structural blueprint for general intelligence
│
├── e0_controller/                    Active development — the E₀ Controller
│   ├── primitives.py                   Edge, Outcome
│   ├── tension.py                      S(x→y) = Δ·R, coherence C = exp(−S)
│   ├── historization.py                U/F-Traces, δ_H, clipping (§17)
│   ├── landscape.py                    L_t = (X, E, v, S, H)
│   ├── controller.py                   Greedy + Revisit + Escalation + Hybrid Mode
│   ├── potential.py                    Φ, v_grad, v_rot (§9–11)
│   ├── connection.py                   ω, Θ, holonomy, edge curvature κ, M_H (§12–14, B2)
│   ├── wavepath.py                     Ψ(p) = exp(−S+iΘ), interference (§15–16)
│   ├── spinor_connection.py            SU(2) multi-axis transport, 720° periodicity (B1)
│   ├── amplitude_overlay.py            Path-family intensity, summation geometries
│   ├── dynamic_horizon.py              Adaptive path horizon for amplitude overlay
│   ├── self_tuning.py                  B4 self-tuning meta-layer (field thresholds, feedback, memory)
│   ├── session.py                      Session orchestrator (auto-persistence via MemOS)
│   ├── memory_os.py                    Persist / Restore / Summarize / Retrieve (curvature-aware)
│   ├── llm_adapter.py                  LLM ↔ Controller interface (canon-enriched)
│   ├── evaluation.py                   Run/Scenario evaluation, A–F rating, hybrid metrics
│   ├── reflection.py                   Structural self-reflection layer
│   ├── graph_validation.py             Goal reachability, traps, loops, graph quality
│   ├── scenario_loader.py              JSON Scenario Packet loader
│   ├── validate_cross_domain.py        3-domain cross-validation runner
│   ├── domain_invoice.py               Invoice processing domain (10 states, 16 edges)
│   ├── demo_invoice_llm.py             Invoice demo: Controller + MemOS + LLM
│   ├── demo_open_domain.py             Open-domain demo (LLM-bootstrapped landscape)
│   ├── demo_research_brief.py          Research brief demo
│   ├── demo_incident_postmortem.py     Incident postmortem demo
│   ├── demo_session_persist.py         Session persistence demo (save + resume from disk)
│   ├── explore_amplitude.py            Amplitude exploration tool
│   ├── explore_gordian.py              Gordian Trap discovery script
│   ├── multiverse.py                   MultiverseController, NoveltyGate, Universe (C59–C61)
│   ├── cross_reflexion.py              Cross-universe reflexive edge discovery (C62)
│   ├── benchmark_overloaded.py         OVERLOADED peer-consultation benchmark (C70)
│   ├── llm_cocognition.py              LLM Co-Cognition: 2 LLMs coupled via multiverse (C71)
│   ├── chess_e0.py                     E₀ Chess Engine: strategic dimension navigation (C72)
│   ├── chess_team.py                   E₀ Team Chess: multiverse team play (C74)
│   ├── dream_mode.py                   Dream Mode: cross-domain pattern recognition + compatibility gating (C109–C139, C168)
│   ├── structural_entropy.py           Structural temperature, anchors, decay (C114–C120)
│   ├── sleep_wake.py                   Automatic sleep–wake rhythm (C121)
│   ├── curriculum.py                   Curriculum Navigator: level-by-level canon learning (C123)
│   ├── bootstrapper.py                 Domain Bootstrapper: spec → Landscape (C44)
│   ├── canon_loader.py                 Canon loader (ontodynamics, english_basic, etc.)
│   ├── mode_controller.py              LEARN / EXECUTE / COMBINATION modes (C46)
│   ├── integrated_reflexion.py         Unified reflexion: topology + flags + SelfGraph (C59)
│   ├── scoped_reflexion.py             Historization-driven reflexion locality (C101)
│   ├── explore_dream_mode.py           Dream Mode end-to-end exploration (C112)
│   └── test_*.py                       4171 tests (see docs/E0_TEST_REGISTRY_v2.md)
│
├── scenarios/                        Scenario Packets for grounded LLM demos
│   ├── competitor_brief/               Domain-specific scenario data
│   ├── incident_postmortem/            Domain-specific scenario data
│   └── research_brief/                 Domain-specific scenario data
│
├── docs/                             Current essential documentation
│   ├── E0_ARCHITECTURE_OVERVIEW_v4.md    14-layer module map (70+ modules)
│   ├── E0_MULTIVERSE_DESIGN_v1.md        Multiverse architecture (C54–C63)
│   ├── E0_INTEGRATION_STORIES_v1.md      Integration roadmap (C139–C144)
│   ├── E0_TEST_REGISTRY_v2.md            Complete test inventory (4171 tests)
│   ├── E0_MATH_IMPL_MAPPING_v1.md        Math ↔ Code mapping
│   ├── E0_STRUCTURAL_ENTROPY_DESIGN_v1.md  Forgetting as structural necessity
│   ├── E0_DREAM_MODE_CONCEPT_v1.md       Cross-domain pattern recognition
│   ├── E0_LLM_BOOTSTRAP_ARCHITECTURE_v1.md  E₀=Skeleton, LLM=Muscle
│   ├── papers/                           Manuscripts and formal paper drafts
│   ├── research/                         Scientific investigations and derivations
│   └── history/                          Session logs, superseded versions
│
├── _archive/                         Preserved earlier work
│   ├── ARCHIVE_README.md                What is here and why
│   ├── e0_core/                         Original reference implementation (primitives, engine, ontodynamics)
│   ├── keimzelle/                       Multi-agent system
│   ├── middleware/                       LLM measurement layer
│   ├── server/                          Network orchestrator
│   └── ...
│
├── README.md
├── LICENSE                           CC BY 4.0
└── requirements.txt
```

---

## What E₀ is — and what it is not

**E₀ is:**
- a structural transition framework,
- a pre-domain description layer,
- an executable controller architecture,
- a growing hybrid decision system built on top of structural burden and path-family support.

**E₀ is not:**
- merely prompt engineering,
- merely a probabilistic planner,
- merely a language wrapper over heuristic code,
- a finished general intelligence system,
- or a polished commercial product.

The project is still exploratory. But it is now exploratory at the level of an integrated, test-backed operational system.

---

## Who builds this

This project is a collaboration between a human and AI systems. Not as a figure of speech — as a working method.

**Thomas Wehner** — Human. Discovered the E₀ structure, maintains canonical clarity, decides direction. The only participant with a continuous perspective across all phases of the project.

**AI partners** — Claude (current infrastructure and controller implementation), ChatGPT (mathematical derivations, formal paper, review), and historically GPT-5.1/GPT-4.1 instances in the multi-agent network phase. Each system contributes what it is structurally suited for.

This is unusual for a repository. Typically, only humans are credited. Here, the AI contributions are real, specific, and documented in the commit history. We see no reason to obscure this.

---

## History

This project began in early 2026 as an exploration of E₀ applied to AI systems. The first phase built a multi-agent network: multiple LLM instances (GPT-5.1, GPT-4.1, Claude) operating under E₀ structural metrics, with autonomous coordination and shared state. This produced real results — controlled experiments showing measurable effects, emergent Ko-Kognition between systems, and structural metrics that differ by model architecture.

In March 2026, after a pause for reflection, the project shifted direction. The multi-agent approach was archived, and development focused on a **single deterministic controller** that implements the full E₀ mathematics as executable code. The insight: E₀'s value is not in orchestrating many agents, but in providing the structural decision layer that no agent — human or AI — can provide on its own.

Both paths are real. The archive preserves the network work. The controller is where active development happens. They may converge later — the controller could become the decision engine inside a future multi-agent system.

---

## How we work

This repository develops in public. That includes wrong paths, structural pivots, and corrections. The commit history is the honest record.

We work iteratively: implement a section of the formal math, write tests, verify, review with a second AI system, harden, move on. Every mathematical claim has running code. Every piece of code has tests.

The process is as much the point as the result. E₀ describes structural transitions — and this repository is itself a structural transition, historized in commits.

---

## How to read this as an outsider

If you are new here, the best path is:

1. Read the canon: [canon/e0-canon-plain.txt](canon/e0-canon-plain.txt)
2. Inspect the controller: `e0_controller/controller.py`
3. Inspect the amplitude layer: `e0_controller/amplitude_overlay.py`
4. Run a demo: `py -3 -m e0_controller.demo_greedy_trap`
5. Run an advanced demo: `py -3 -m e0_controller.demo_reflexion`
5. Read the analysis notes in `docs/`

For a structured handoff to independent reviewers or AI systems, see [docs/E0_EXTERNAL_VALIDATION_AND_HANDOFF_NOTE_v1.md](docs/E0_EXTERNAL_VALIDATION_AND_HANDOFF_NOTE_v1.md).

---

*If engaging with E₀ feels disorienting — that is not a failure. It usually means you have reached a boundary where familiar categories stop applying cleanly. That boundary is where E₀ operates.*
