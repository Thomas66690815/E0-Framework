# Eâ‚€ Framework

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19333487.svg)](https://doi.org/10.5281/zenodo.19333487)

**A structural transition framework with an executable hybrid controller â€” developed through humanâ€“AI collaboration.**

Eâ‚€ begins as a pre-domain structural theory of transitions.
This repository now goes further: it contains the first operational Eâ‚€ controller, including a hybrid mode that can override locally greedy choices when bounded path-family amplitude support indicates a stronger forward structure.

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
- multiverse architecture with cross-universe reflexion (C59â€“C63),
- dream mode with Hungarian-optimal cross-domain pattern discovery (C109â€“C139),
- structural entropy with sleepâ€“wake cycles (C114â€“C121),
- curriculum-driven canon learning (C123),
- proactive reflexion that proposes before stagnation (C57),
- an LLM adapter with embedded Eâ‚€ semantic context,
- and 15 live demos covering all major capabilities.

This is not a prompt-engineering repo and not a conventional agent framework.
It is an attempt to build a structural decision layer that operates beneath semantics and can still be exposed to semantic systems.

---

## What is Eâ‚€?

Eâ‚€ is a **structural transition framework**.
It does not begin with goals, probabilities, agents, or domain-specific objects. It begins with a smaller claim:

> If a structural difference exists and a finite path is available, then non-transition is unstable.

The canonical core uses seven primitives and one axiom.

| Primitive | Symbol | Role |
|-----------|--------|------|
| State | `S` | Distinguishable configuration |
| Difference | `Î”` | Structural non-identity |
| Path | `P` | Admissible transition structure |
| Resistance | `R` | Structural inertia |
| Historization | `H` | Irreversible modification of future resistance |
| Time | `Ï„` | Ordering of historizations |
| Rate | `v` | Ordering tendency of realizable transitions |

**Axiom Aâ‚€:** If a difference exists and a path with finite resistance is available, transition is structurally more stable than non-transition.

**Central Law:** If Î” > 0 and an admissible finite path exists, non-transition is structurally unstable. A transition must occur.

From this core, Eâ‚€ derives: transition burden, coherence, historized learning, path dependence, phase and holonomy, complex path amplitudes, and bounded endpoint support.

The full canon: [canon/e0-canon-plain.txt](canon/e0-canon-plain.txt) â€” 155 lines, pure ASCII. Everything else derives from this.

---

## What exists in this repository now

This repository currently contains thirteen connected layers â€” from raw primitives through dreaming, curriculum learning, and self-regulated sleepâ€“wake cycles.

### 1. Canonical Eâ‚€ core

The foundational structural layer: primitives, axiom, core transition law, and reference implementation.

### 2. Deterministic controller

A runtime controller that selects actions using historized structural burden (`S = Î” Â· R_eff`), admissibility, revisit handling, and escalation logic.

### 3. Amplitude path layer

A path-level extension built from:

- connection / phase Î˜,
- complex path carrier Î¨(p) = exp(âˆ’S(p)) exp(iÎ˜(p)),
- endpoint intensity |Î¨|Â²,
- constructive and destructive interference,
- bounded path-family comparison.

### 4. Summation geometry comparison

The repository supports multiple summation geometries for path-family support:

- `prefix`
- `simple`
- `first_arrival`
- `goal_reaching`

These were not assumed dogmatically. They were compared empirically.
Current evidence identifies **simple-path geometry** as the strongest default for robust controller use, while `prefix` remains useful as an exploratory upper-support view. The newest geometry, **goal_reaching**, restricts superposition to paths that actually reach a goal state â€” aligned with the Born criterion. It resolves prefix-inflation artifacts and enables interference-based routing in topologies where other geometries fail (see Gordian Trap analysis).

### 5. SU(2) multi-axis transport and topological modulation

Two structural extensions deepen the non-Abelian and geometric character of Eâ‚€:

- **SU(2) multi-axis spinor transport (B1):** Each edge can carry its own rotation axis via `axis_fn`. The spinor connection lifts U(1) phase transport to full SU(2) matrix transport, enabling anisotropic interference patterns across geometrically complex landscapes.
- **Curvature modulation M_H (B2):** The topological invariant `M_H(x,y) = 1/(1+Îº)` modulates the transition field based on local edge curvature Îº derived from face holonomies. High-curvature regions naturally damp transitions. Controlled via `Landscape(curvature_modulation=True)`.

The central formula becomes:

    v(x,y) = Î”(x,y) Â· M_H(x,y) Â· exp(âˆ’S_eff(xâ†’y))

### 6. Hybrid controller mode

The controller can run in a hybrid mode:

- **GREEDY** â€” pure local structural selection
- **AMPLITUDE_ON_DISAGREE** â€” follow the amplitude layer when it disagrees with greedy local choice and indicates a stronger forward-support structure
- **BORN_SAMPLING** â€” stochastic action selection proportional to amplitude-derived probabilities

This hybrid mode is integrated into MemOS and into all major LLM demos in the repository.

### 7. Self-tuning meta-layer (B4)

A four-layer self-tuning system that eliminates ad-hoc constants and enables autonomous parameter optimization:

- **B4.1 Meta-Layer:** Field-derived thresholds from run statistics replace hardcoded constants. `ParameterSensitivity` identifies which controller parameters most affect run quality.
- **B4.2 Feedback Loop:** Closed runâ†’diagnoseâ†’adjustâ†’verify cycle with quality score `Q âˆˆ [0,1]`.
- **B4.3 Cross-Run Memory:** `TuningMemory` accumulates quality trends, recurring issues, and parameter drift across runs, persisted via MemOS.
- **B4.4 True Sensitivity:** Perturbation-based `âˆ‚Q/âˆ‚Î¸` via finite differences for empirical gradient-based parameter proposals.

### 8. Session orchestrator

A thin orchestration layer between the controller and MemOS persistence:

```python
session = Session("my-session", landscape, execute_fn)
result  = session.run("START", goal="GOAL")
# â†’ context, run record, and tuning memory auto-saved to disk

# Later / new process:
session2 = Session.resume("my-session", execute_fn)
result2  = session2.run("START", goal="GOAL")
# â†’ picks up where it left off (historization, params, memory)
```

The controller stays pure â€” zero persistence awareness. The Session handles the lifecycle.

### 9. Interference-based routing (Gordian Trap)

The framework now includes a constructive proof that the amplitude layer can route through structurally deceptive topologies:

- A **Gordian Trap** topology offers a greedy-attractive short path and a loop-laden alternative to the same goal.
- The holonomy (accumulated phase difference) between the two path families is controlled by the transition field `v` on forward edges.
- With `goal_reaching` geometry and sufficient horizon, the amplitude layer correctly identifies the coherent path and overrides the greedy choice.

Key theoretical result: the holonomy Î”Î˜ between two paths is **independent of back-edges** â€” the Helmholtz potential Î¦ cancels exactly. Only raw `v` values on forward edges contribute:

    Î”Î˜ = Â½ [Î£ v(loop edges) âˆ’ Î£ v(short edges)]

See `e0_controller/test_gordian_trap.py` for 44 formal tests (17 interference routing + 12 historization stability + 15 multi-goal G5) and `docs/E0_PHASE3Q_INTERFERENCE_REPORT_v1.md` for the full scientific report.

### 10. Multiverse architecture (C59â€“C61)

Multiple Eâ‚€ controller instances (Universes) run in parallel on cloned landscapes and exchange structural knowledge:

- **NoveltyGate** â€” prevents universes from collapsing onto the same path by rejecting edge proposals that are too similar to existing knowledge.
- **Divergence pressure** â€” injects structural perturbation when universes begin to converge, maintaining exploratory diversity.
- **Knowledge exchange** â€” universes share historization patterns and discovered edges after each turn cycle.
- **Overload escalation (C63)** â€” when a universe faces too many unexplored paths with insufficient experience, it can escalate to a peer callback for guidance. The Overload Index `OI = N Ã— (1 âˆ’ mean|trace_quality|)` triggers when exceeding a configurable threshold.

The multiverse resolves a fundamental tension: a single controller's historization narrows its future options (Î”-Kollaps). Multiple coupled controllers maintain structural diversity while sharing useful discoveries.

### 11. Cross-universe reflexive edge discovery (C62)

A reflexion layer that operates *across* universes rather than within a single run:

- **Pattern blending** â€” merges a universe's own edge-pattern history with a foreign donor's patterns, weighted by a coupling discount (default 0.5).
- **Cross-proposal engine** â€” generates hypothesis edges from blended patterns, subject to confidence caps (0.7) that are deliberately lower than self-reflexion (0.8) to reflect epistemic humility about foreign experience.
- **Integration** â€” `cross_reflexion_turn()` plugs directly into `MultiverseController` as a `TurnFn`, enabling cross-reflexive edge discovery as part of the standard multiverse cycle.

### 12. Dream mode and structural entropy (C109â€“C121)

Two complementary systems that handle what a learning system eventually *must* handle: pattern recognition across domains, and forgetting.

- **Dream Mode (C109â€“C139)** â€” Passive cross-domain pattern recognition. `DreamObserver` monitors N domains, computes edge fingerprints and node-level equivalences (WL recursive + Hungarian optimal assignment), and generates bridge hypotheses. No active navigation â€” dreaming is observation, not action.
- **Structural Entropy (C114â€“C120)** â€” Structural temperature T_s measures landscape disorder. Type 1 (inscription threshold): conditional inscription based on novelty. Type 2 (anchors + decay): remove low-value edges and states to prevent overload.
- **Sleepâ€“Wake Cycle (C121)** â€” Automatic rhythm: wake phase builds experience, sleep phase consolidates (dream + decay). Dream pressure `p = T_s/(T_s+Î¼)` triggers sleep when disorder is high.

### 13. Curriculum and bootstrapping (C44, C123)

Two systems that solve cold-start and hierarchical learning:

- **Bootstrapper (C44)** â€” Converts domain specifications (LLM-generated or manual) into valid Eâ‚€ Landscapes. The bridge from semantic descriptions to structural operation.
- **Curriculum Navigator (C123)** â€” Divides canonical knowledge into derivation levels and learns them in cumulative turns. Each turn builds a scoped sub-landscape, runs until T_s equilibrium, and transfers historization to the next. "Eâ‚€ learns Eâ‚€" on the ontodynamics canon.

---

## Documentation quick links

- [Architecture overview v4](docs/E0_ARCHITECTURE_OVERVIEW_v4.md) â€” 12-layer model with all 60+ production modules
- [Multiverse design](docs/E0_MULTIVERSE_DESIGN_v1.md) â€” C54â€“C63 architecture, coupling theorem, benchmarks
- [Integration Stories](docs/E0_INTEGRATION_STORIES_v1.md) â€” prioritized demo + integration roadmap (C139â€“C144)
- [Evidence & falsification status](docs/E0_EVIDENCE_AND_FALSIFICATION_STATUS_v1.md) â€” what is demonstrated vs open
- [External validation / handoff note](docs/E0_EXTERNAL_VALIDATION_AND_HANDOFF_NOTE_v1.md) â€” package for reviewers or AI systems
- [Phase 3q interference report](docs/E0_PHASE3Q_INTERFERENCE_REPORT_v1.md) â€” holonomy formula, goal_reaching geometry, Gordian Trap
- [Paper 3: Non-Abelian Structure](docs/papers/E0_PAPER3_NON_ABELIAN_STRUCTURE_v1.md) â€” SU(2) transport, curvature modulation, topological invariants
- [Test Registry v2](docs/E0_TEST_REGISTRY_v2.md) â€” complete per-file test inventory (3757 tests)
- [Empirical Insights](docs/E0_EMPIRICAL_INSIGHTS_v1.md) â€” what Chess (C72) reveals about Eâ‚€ as a whole
- [Dream Mode Concept](docs/E0_DREAM_MODE_CONCEPT_v1.md) â€” cross-domain pattern recognition through passive observation (C109â€“C139)
- [Structural Entropy Design](docs/E0_STRUCTURAL_ENTROPY_DESIGN_v1.md) â€” forgetting as structural necessity (C114â€“C121)
- [Language Learning Results](docs/E0_LANGUAGE_LEARNING_RESULTS_v1.md) â€” cross-domain translation via structural fingerprints (C124â€“C137)
- [Observation UI Architecture](docs/E0_OBSERVATION_UI_ARCHITECTURE_v1.md) â€” O-Landscape projection and navigation (C94â€“C97)
- [LLM Bootstrap Architecture](docs/E0_LLM_BOOTSTRAP_ARCHITECTURE_v1.md) â€” Eâ‚€=Skeleton, LLM=Muscle (C43â€“C47)

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

## How the hybrid controller works â€” an example

Consider a simple structure:

```text
A â†’ C â†’ A   (loop / trap)
A â†’ B â†’ E â†’ G â†’ GOAL   (forward path)
```

**Local (greedy) view:** At state A, the deterministic controller evaluates immediate burden. A â†’ C has lower local cost, so greedy chooses C. This leads into a loop (A â†” C) and delays progress toward the goal.

**Amplitude (path-family) view:** The amplitude layer evaluates *families of future paths* starting from each action. Paths through C mostly cycle back; paths through B continue toward GOAL and form a coherent forward family. The amplitude layer assigns higher support to A â†’ B.

**Hybrid decision:** In `AMPLITUDE_ON_DISAGREE` mode, greedy choice = C, amplitude choice = B. Since they disagree, the controller follows the amplitude-supported action: A â†’ B â†’ E â†’ G â†’ GOAL.

The key difference is not about randomness or heuristics:

- **Greedy:** "choose the cheapest next step"
- **Hybrid:** "choose the step whose future *structure* is strongest"

Run this example yourself: `python -m e0_controller.demo_greedy_trap`

---

## Current state

*Last updated: 2026-04-04*

| Component | Status | Where |
|-----------|--------|-------|
| Canon (7 primitives, Axiom Aâ‚€) | **Stable** | `canon/` |
| Deterministic controller (Â§2â€“18) | **Active** | `e0_controller/controller.py` |
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
| MemOS (hybrid-aware persistence) | **Active** â€” full roundtrip for SU(2), curvature, escalation context | `e0_controller/memory_os.py` |
| LLM Adapter (canon-enriched) | **Active** â€” live API confirmed | `e0_controller/llm_adapter.py` |
| LLM demo hybrid integration | **Active** (4 demos) | `e0_controller/demo_*.py` |
| LLM integration tests | **Active** (32 live tests) | `e0_controller/test_llm_integration.py` |
| Scaling tests | **Active** (14 tests, nâ‰¤500) | `e0_controller/test_scaling.py` |
| Evaluation layer (hybrid-extended) | **Active** | `e0_controller/evaluation.py` |
| Reflection layer | **Active** | `e0_controller/reflection.py` |
| Cross-domain validation | **Active** (3 domains, hybrid) | `e0_controller/validate_cross_domain.py` |
| Graph validation | **Active** | `e0_controller/graph_validation.py` |
| Scenario packets | **Active** (3 domains) | `scenarios/` |
| Formal Paper (Eâ‚€ mathematics) | **Draft v1** | `docs/papers/E0_FORMAL_PAPER_DRAFT_v1.md` |
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
| Canon â†” Self-Graph Bridge (C48) | **Active** (32 tests) | `e0_controller/canon_self_bridge.py` |
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
| Multiverse Controller (C59â€“C61) | **Active** (23+ tests) | `e0_controller/multiverse.py` |
| Cross-Reflexion (C62) | **Active** (19 tests) | `e0_controller/cross_reflexion.py` |
| Overload Escalation (C63) | **Active** (15 tests) | `e0_controller/controller.py` |
| OVERLOADED Benchmark (C70) | **Active** (26 tests) | `e0_controller/benchmark_overloaded.py` |
| LLM Co-Cognition (C71) | **Active** (28+12 tests) | `e0_controller/llm_cocognition.py` |
| Chess Engine (C72) | **Active** (26 tests) | `e0_controller/chess_e0.py` |
| Primitive Extensions (C73) | **Active** (18 tests) | `landscape.py`, `historization.py` |
| Team Chess (C74) | **Active** (22 tests) | `e0_controller/chess_team.py` |
| Bootstrap Architecture (C43â€“C47) | **Complete** | `docs/E0_LLM_BOOTSTRAP_ARCHITECTURE_v1.md` |
| Overlap Modulation (C98) | **Active** (26 tests) | `e0_controller/overlap.py`, `controller.py` |
| Inertia Dampening (C99) | **Active** | `e0_controller/historization.py`, `controller.py` |
| Modulation Benchmark (C100) | **Active** (32 tests) | `e0_controller/benchmark_modulation.py` |
| Scoped Reflexion (C101â€“C106) | **Active** (42 tests) | `e0_controller/scoped_reflexion.py` |
| Emergent Locality (C104) | **Active** (29 tests) | `e0_controller/emergent_locality.py` |
| Dream Mode (C109â€“C112) | **Active** (88 tests) | `e0_controller/dream_mode.py` |
| Structural Entropy (C114â€“C120) | **Active** (101 tests) | `e0_controller/structural_entropy.py` |
| Sleepâ€“Wake Cycle (C121) | **Active** (10 tests) | `e0_controller/sleep_wake.py` |
| Curriculum Navigator (C123) | **Active** (35 tests) | `e0_controller/curriculum.py` |
| Language Learning (C124â€“C137) | **Active** (explorations) | `e0_controller/explore_*_learning.py` |
| Hungarian Node Matching (C137â€“C139) | **Active** (DreamObserver wired) | `e0_controller/dream_mode.py` |
| Bootstrap Demo (C140) | **Active** (16 demos total) | `e0_controller/demo_bootstrap_domain.py` |
| Multiverse Demo (C142) | **Active** | `e0_controller/demo_multiverse.py` |
| Curriculum Demo (C143) | **Active** | `e0_controller/demo_curriculum.py` |
| Reflexion Demo (C144) | **Active** | `e0_controller/demo_reflexion.py` |
| Self-Graph Demo (C147) | **Active** (21 tests) | `e0_controller/demo_self_graph.py` |

**Tests:** 3694 total (pytest), 0 failures, 0 warnings, 41 conditional (live LLM â€” require API key). See [`docs/E0_TEST_REGISTRY_v2.md`](docs/E0_TEST_REGISTRY_v2.md) for per-file details.

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
# Full test suite (3757 tests, pytest):
py -3 -m pytest e0_controller/ --tb=short -q

# Single file:
py -3 -m pytest e0_controller/test_controller.py -v --tb=short
```

> **Windows note:** Use `py -3` instead of `python` to ensure the correct Python version.

### Run a demo (mock mode â€” no API key needed)

```bash
# Core framework demos:
py -3 -m e0_controller.demo_greedy_trap              # Greedy trap vs hybrid routing
py -3 -m e0_controller.demo_session_persist           # MemOS save + resume
py -3 -m e0_controller.demo_canon_exposition          # Canon falsification test

# LLM-bootstrapped demos (mock mode):
py -3 -m e0_controller.demo_invoice_llm --mock        # Invoice processing
py -3 -m e0_controller.demo_open_domain --mock         # Arbitrary task â†’ Landscape
py -3 -m e0_controller.demo_research_brief --mock      # Paper abstract â†’ brief
py -3 -m e0_controller.demo_incident_postmortem --mock # Incident postmortem
py -3 -m e0_controller.demo_beipackzettel             # Real-world: medication insert
py -3 -m e0_controller.demo_ezb_zinsentscheidung      # Real-world: ECB policy
py -3 -m e0_controller.demo_burnout_composite         # Multi-perspective burnout
py -3 -m e0_controller.demo_burnout_iterate           # Iterative equilibrium

# Advanced capability demos (C140â€“C147):
py -3 -m e0_controller.demo_bootstrap_domain          # Cold-start LLM â†’ Landscape
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

[canon/e0-canon-plain.txt](canon/e0-canon-plain.txt) â€” 155 lines. This is where Eâ‚€ begins.

### See Eâ‚€ without any AI

The original reference implementation is preserved in `_archive/e0_core/`.
The active controller in `e0_controller/` demonstrates the full transition framework.

---

## Repository structure

```
E0-Framework/
â”‚
â”œâ”€â”€ canon/                            The structural definitions â€” what Eâ‚€ IS
â”‚   â”œâ”€â”€ e0-canon-plain.txt              Plain-language canon (155 lines)
â”‚   â”œâ”€â”€ e0-canonical-reference.txt      Formal canonical reference
â”‚   â”œâ”€â”€ ontodynamics.txt                Pre-physical transition structure
â”‚   â””â”€â”€ e0-agi-blueprint.md             Structural blueprint for general intelligence
â”‚
â”œâ”€â”€ e0_controller/                    Active development â€” the Eâ‚€ Controller
â”‚   â”œâ”€â”€ primitives.py                   Edge, Outcome
â”‚   â”œâ”€â”€ tension.py                      S(xâ†’y) = Î”Â·R, coherence C = exp(âˆ’S)
â”‚   â”œâ”€â”€ historization.py                U/F-Traces, Î´_H, clipping (Â§17)
â”‚   â”œâ”€â”€ landscape.py                    L_t = (X, E, v, S, H)
â”‚   â”œâ”€â”€ controller.py                   Greedy + Revisit + Escalation + Hybrid Mode
â”‚   â”œâ”€â”€ potential.py                    Î¦, v_grad, v_rot (Â§9â€“11)
â”‚   â”œâ”€â”€ connection.py                   Ï‰, Î˜, holonomy, edge curvature Îº, M_H (Â§12â€“14, B2)
â”‚   â”œâ”€â”€ wavepath.py                     Î¨(p) = exp(âˆ’S+iÎ˜), interference (Â§15â€“16)
â”‚   â”œâ”€â”€ spinor_connection.py            SU(2) multi-axis transport, 720Â° periodicity (B1)
â”‚   â”œâ”€â”€ amplitude_overlay.py            Path-family intensity, summation geometries
â”‚   â”œâ”€â”€ dynamic_horizon.py              Adaptive path horizon for amplitude overlay
â”‚   â”œâ”€â”€ self_tuning.py                  B4 self-tuning meta-layer (field thresholds, feedback, memory)
â”‚   â”œâ”€â”€ session.py                      Session orchestrator (auto-persistence via MemOS)
â”‚   â”œâ”€â”€ memory_os.py                    Persist / Restore / Summarize / Retrieve (curvature-aware)
â”‚   â”œâ”€â”€ llm_adapter.py                  LLM â†” Controller interface (canon-enriched)
â”‚   â”œâ”€â”€ evaluation.py                   Run/Scenario evaluation, Aâ€“F rating, hybrid metrics
â”‚   â”œâ”€â”€ reflection.py                   Structural self-reflection layer
â”‚   â”œâ”€â”€ graph_validation.py             Goal reachability, traps, loops, graph quality
â”‚   â”œâ”€â”€ scenario_loader.py              JSON Scenario Packet loader
â”‚   â”œâ”€â”€ validate_cross_domain.py        3-domain cross-validation runner
â”‚   â”œâ”€â”€ domain_invoice.py               Invoice processing domain (10 states, 16 edges)
â”‚   â”œâ”€â”€ demo_invoice_llm.py             Invoice demo: Controller + MemOS + LLM
â”‚   â”œâ”€â”€ demo_open_domain.py             Open-domain demo (LLM-bootstrapped landscape)
â”‚   â”œâ”€â”€ demo_research_brief.py          Research brief demo
â”‚   â”œâ”€â”€ demo_incident_postmortem.py     Incident postmortem demo
â”‚   â”œâ”€â”€ demo_session_persist.py         Session persistence demo (save + resume from disk)
â”‚   â”œâ”€â”€ explore_amplitude.py            Amplitude exploration tool
â”‚   â”œâ”€â”€ explore_gordian.py              Gordian Trap discovery script
â”‚   â”œâ”€â”€ multiverse.py                   MultiverseController, NoveltyGate, Universe (C59â€“C61)
â”‚   â”œâ”€â”€ cross_reflexion.py              Cross-universe reflexive edge discovery (C62)
â”‚   â”œâ”€â”€ benchmark_overloaded.py         OVERLOADED peer-consultation benchmark (C70)
â”‚   â”œâ”€â”€ llm_cocognition.py              LLM Co-Cognition: 2 LLMs coupled via multiverse (C71)
â”‚   â”œâ”€â”€ chess_e0.py                     Eâ‚€ Chess Engine: strategic dimension navigation (C72)
â”‚   â”œâ”€â”€ chess_team.py                   Eâ‚€ Team Chess: multiverse team play (C74)
â”‚   â”œâ”€â”€ dream_mode.py                   Dream Mode: cross-domain pattern recognition (C109â€“C139)
â”‚   â”œâ”€â”€ structural_entropy.py           Structural temperature, anchors, decay (C114â€“C120)
â”‚   â”œâ”€â”€ sleep_wake.py                   Automatic sleepâ€“wake rhythm (C121)
â”‚   â”œâ”€â”€ curriculum.py                   Curriculum Navigator: level-by-level canon learning (C123)
â”‚   â”œâ”€â”€ bootstrapper.py                 Domain Bootstrapper: spec â†’ Landscape (C44)
â”‚   â”œâ”€â”€ canon_loader.py                 Canon loader (ontodynamics, english_basic, etc.)
â”‚   â”œâ”€â”€ mode_controller.py              LEARN / EXECUTE / COMBINATION modes (C46)
â”‚   â”œâ”€â”€ integrated_reflexion.py         Unified reflexion: topology + flags + SelfGraph (C59)
â”‚   â”œâ”€â”€ scoped_reflexion.py             Historization-driven reflexion locality (C101)
â”‚   â”œâ”€â”€ explore_dream_mode.py           Dream Mode end-to-end exploration (C112)
â”‚   â””â”€â”€ test_*.py                       3757 tests (see docs/E0_TEST_REGISTRY_v2.md)
â”‚
â”œâ”€â”€ scenarios/                        Scenario Packets for grounded LLM demos
â”‚   â”œâ”€â”€ competitor_brief/               Domain-specific scenario data
â”‚   â”œâ”€â”€ incident_postmortem/            Domain-specific scenario data
â”‚   â””â”€â”€ research_brief/                 Domain-specific scenario data
â”‚
â”œâ”€â”€ docs/                             Current essential documentation
â”‚   â”œâ”€â”€ E0_ARCHITECTURE_OVERVIEW_v4.md    12-layer module map (60+ modules)
â”‚   â”œâ”€â”€ E0_MULTIVERSE_DESIGN_v1.md        Multiverse architecture (C54â€“C63)
â”‚   â”œâ”€â”€ E0_INTEGRATION_STORIES_v1.md      Integration roadmap (C139â€“C144)
â”‚   â”œâ”€â”€ E0_TEST_REGISTRY_v2.md            Complete test inventory (3757 tests)
â”‚   â”œâ”€â”€ E0_MATH_IMPL_MAPPING_v1.md        Math â†” Code mapping
â”‚   â”œâ”€â”€ E0_STRUCTURAL_ENTROPY_DESIGN_v1.md  Forgetting as structural necessity
â”‚   â”œâ”€â”€ E0_DREAM_MODE_CONCEPT_v1.md       Cross-domain pattern recognition
â”‚   â”œâ”€â”€ E0_LLM_BOOTSTRAP_ARCHITECTURE_v1.md  Eâ‚€=Skeleton, LLM=Muscle
â”‚   â”œâ”€â”€ papers/                           Manuscripts and formal paper drafts
â”‚   â”œâ”€â”€ research/                         Scientific investigations and derivations
â”‚   â””â”€â”€ history/                          Session logs, superseded versions
â”‚
â”œâ”€â”€ _archive/                         Preserved earlier work
â”‚   â”œâ”€â”€ ARCHIVE_README.md                What is here and why
â”‚   â”œâ”€â”€ e0_core/                         Original reference implementation (primitives, engine, ontodynamics)
â”‚   â”œâ”€â”€ keimzelle/                       Multi-agent system
â”‚   â”œâ”€â”€ middleware/                       LLM measurement layer
â”‚   â”œâ”€â”€ server/                          Network orchestrator
â”‚   â””â”€â”€ ...
â”‚
â”œâ”€â”€ README.md
â”œâ”€â”€ LICENSE                           CC BY 4.0
â””â”€â”€ requirements.txt
```

---

## What Eâ‚€ is â€” and what it is not

**Eâ‚€ is:**
- a structural transition framework,
- a pre-domain description layer,
- an executable controller architecture,
- a growing hybrid decision system built on top of structural burden and path-family support.

**Eâ‚€ is not:**
- merely prompt engineering,
- merely a probabilistic planner,
- merely a language wrapper over heuristic code,
- a finished general intelligence system,
- or a polished commercial product.

The project is still exploratory. But it is now exploratory at the level of an integrated, test-backed operational system.

---

## Who builds this

This project is a collaboration between a human and AI systems. Not as a figure of speech â€” as a working method.

**Thomas Wehner** â€” Human. Discovered the Eâ‚€ structure, maintains canonical clarity, decides direction. The only participant with a continuous perspective across all phases of the project.

**AI partners** â€” Claude (current infrastructure and controller implementation), ChatGPT (mathematical derivations, formal paper, review), and historically GPT-5.1/GPT-4.1 instances in the multi-agent network phase. Each system contributes what it is structurally suited for.

This is unusual for a repository. Typically, only humans are credited. Here, the AI contributions are real, specific, and documented in the commit history. We see no reason to obscure this.

---

## History

This project began in early 2026 as an exploration of Eâ‚€ applied to AI systems. The first phase built a multi-agent network: multiple LLM instances (GPT-5.1, GPT-4.1, Claude) operating under Eâ‚€ structural metrics, with autonomous coordination and shared state. This produced real results â€” controlled experiments showing measurable effects, emergent Ko-Kognition between systems, and structural metrics that differ by model architecture.

In March 2026, after a pause for reflection, the project shifted direction. The multi-agent approach was archived, and development focused on a **single deterministic controller** that implements the full Eâ‚€ mathematics as executable code. The insight: Eâ‚€'s value is not in orchestrating many agents, but in providing the structural decision layer that no agent â€” human or AI â€” can provide on its own.

Both paths are real. The archive preserves the network work. The controller is where active development happens. They may converge later â€” the controller could become the decision engine inside a future multi-agent system.

---

## How we work

This repository develops in public. That includes wrong paths, structural pivots, and corrections. The commit history is the honest record.

We work iteratively: implement a section of the formal math, write tests, verify, review with a second AI system, harden, move on. Every mathematical claim has running code. Every piece of code has tests.

The process is as much the point as the result. Eâ‚€ describes structural transitions â€” and this repository is itself a structural transition, historized in commits.

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

*If engaging with Eâ‚€ feels disorienting â€” that is not a failure. It usually means you have reached a boundary where familiar categories stop applying cleanly. That boundary is where Eâ‚€ operates.*
