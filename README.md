# E₀ Framework

**A structural transition framework with an executable hybrid controller — developed through human–AI collaboration.**

E₀ begins as a pre-domain structural theory of transitions.
This repository now goes further: it contains the first operational E₀ controller, including a hybrid mode that can override locally greedy choices when bounded path-family amplitude support indicates a stronger forward structure.

In practical terms, this means the repository is no longer only about a deterministic transition law. It now also contains:

- a historized structural controller,
- a phase/amplitude path layer,
- empirically tested summation geometries,
- a hybrid correction mode,
- persistent runtime support via MemOS,
- and live integration into multiple LLM-driven demos.

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

This repository currently contains five connected layers.

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

### 5. Hybrid controller mode

The controller can run in a hybrid mode:

- **GREEDY** — pure local structural selection
- **AMPLITUDE_ON_DISAGREE** — follow the amplitude layer when it disagrees with greedy local choice and indicates a stronger forward-support structure

This hybrid mode is integrated into MemOS and into all major LLM demos in the repository.

### 6. Interference-based routing (Gordian Trap)

The framework now includes a constructive proof that the amplitude layer can route through structurally deceptive topologies:

- A **Gordian Trap** topology offers a greedy-attractive short path and a loop-laden alternative to the same goal.
- The holonomy (accumulated phase difference) between the two path families is controlled by the transition field `v` on forward edges.
- With `goal_reaching` geometry and sufficient horizon, the amplitude layer correctly identifies the coherent path and overrides the greedy choice.

Key theoretical result: the holonomy ΔΘ between two paths is **independent of back-edges** — the Helmholtz potential Φ cancels exactly. Only raw `v` values on forward edges contribute:

    ΔΘ = ½ [Σ v(loop edges) − Σ v(short edges)]

See `e0_controller/test_gordian_trap.py` for 17 formal tests and `docs/E0_PHASE3Q_INTERFERENCE_REPORT_v1.md` for the full scientific report.

---

## Documentation quick links

- [Architecture overview](docs/E0_ARCHITECTURE_OVERVIEW_v1.md) — how the layers connect end-to-end
- [Hybrid controller spec](docs/E0_HYBRID_CONTROLLER_SPEC_v1.md) — exact runtime behaviour and metrics
- [Derived / Empirical / Heuristic map](docs/E0_DERIVED_EMPIRICAL_HEURISTIC_MAP_v1.md) — classification of each subsystem
- [Evidence & falsification status](docs/E0_EVIDENCE_AND_FALSIFICATION_STATUS_v1.md) — what is demonstrated vs open
- [External validation / handoff note](docs/E0_EXTERNAL_VALIDATION_AND_HANDOFF_NOTE_v1.md) — package for reviewers or AI systems
- [Phase 3q interference report](docs/E0_PHASE3Q_INTERFERENCE_REPORT_v1.md) — holonomy formula, goal_reaching geometry, Gordian Trap

---

## What is new here

Many systems can rank local actions.
What is unusual here is the combination of:

- historized structural burden,
- non-probabilistic transition enforcement,
- path-phase structure,
- bounded amplitude superposition,
- empirically tested summation geometry,
- and hybrid correction of local greedy decisions.

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

*Last updated: 2026-03-24 — v0.10.11*

| Component | Status | Where |
|-----------|--------|-------|
| Canon (7 primitives, Axiom A₀) | **Stable** | `canon/` |
| Deterministic controller (§2–18) | **Active** | `e0_controller/controller.py` |
| Amplitude overlay | **Active** (4 geometries) | `e0_controller/amplitude_overlay.py` |
| Summation geometry comparison | **Completed** (empirical + G5) | `docs/E0_SUMMATION_GEOMETRY_COMPARISON_v1.md` |
| Hybrid controller mode | **Active** (`hybrid_geometry` param) | `e0_controller/controller.py` |
| Interference routing | **Demonstrated** (Gordian Trap) | `e0_controller/test_gordian_trap.py` |
| MemOS (hybrid-aware persistence) | **Active** | `e0_controller/memory_os.py` |
| LLM Adapter (A3 Hybrid) | **Active** — live API confirmed | `e0_controller/llm_adapter.py` |
| LLM demo hybrid integration | **Active** (4 demos) | `e0_controller/demo_*.py` |
| LLM integration tests | **Active** (24 tests) | `e0_controller/test_llm_integration.py` |
| Scaling tests | **Active** (14 tests, n≤500) | `e0_controller/test_scaling.py` |
| Evaluation layer (hybrid-extended) | **Active** | `e0_controller/evaluation.py` |
| Reflection layer | **Active** | `e0_controller/reflection.py` |
| Cross-domain validation | **Active** (3 domains, hybrid) | `e0_controller/validate_cross_domain.py` |
| Graph validation | **Active** | `e0_controller/graph_validation.py` |
| Scenario packets | **Active** (3 domains) | `scenarios/` |
| Formal Paper (E₀ mathematics) | **Draft** | `docs/E0_FORMAL_PAPER_DRAFT_v1.md` |
| Core reference implementation | Stable (read-only) | `e0_core/` |
| Multi-agent network + experiments | **Archived** | `_archive/` |

**Tests:** 416 total (395 unittest + 21 mini-domain), all green.

---

## Quickstart

**Requirements:** Python 3.11+

```bash
git clone https://github.com/Thomas66690815/E0-Framework.git
cd E0-Framework
```

### Run the tests (no API key needed)

```bash
# Mini-domain: 21 tests (custom runner)
python e0_controller/test_minidomain.py

# Full test suite: 391 tests (unittest)
python -m unittest e0_controller.test_amplitude_overlay e0_controller.test_invoice e0_controller.test_phase2_minidomain e0_controller.test_phase2_invoice e0_controller.test_memory_os e0_controller.test_llm_adapter e0_controller.test_graph_validation e0_controller.test_evaluation e0_controller.test_reflection -v
```

### Run a standard demo (mock mode — no API key)

```bash
python -m e0_controller.demo_greedy_trap
python -m e0_controller.demo_invoice_llm --mock
python -m e0_controller.demo_open_domain --mock
python -m e0_controller.demo_research_brief --mock
python -m e0_controller.demo_incident_postmortem --mock
```

### Run a hybrid demo

```bash
python -m e0_controller.demo_invoice_llm --mock --hybrid
python -m e0_controller.demo_open_domain --mock --hybrid
python -m e0_controller.demo_research_brief --mock --hybrid
python -m e0_controller.demo_incident_postmortem --mock --hybrid
```

### Run cross-domain validation

```bash
python -m e0_controller.validate_cross_domain
python -m e0_controller.validate_cross_domain --hybrid
```

### Read the canon

[canon/e0-canon-plain.txt](canon/e0-canon-plain.txt) — 155 lines. This is where E₀ begins.

### See E₀ without any AI

```bash
python -m e0_core.demo
```

Transitions select themselves through tension minimization. No language model involved.

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
│   ├── connection.py                   ω, Θ, holonomy (§12–14)
│   ├── wavepath.py                     Ψ(p) = exp(−S+iΘ), interference (§15–16)
│   ├── amplitude_overlay.py            Path-family intensity, summation geometries
│   ├── memory_os.py                    Persist / Restore / Summarize / Retrieve (hybrid-aware)
│   ├── llm_adapter.py                  LLM ↔ Controller interface (A3 Hybrid)
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
│   ├── explore_amplitude.py            Amplitude exploration tool
│   └── test_*.py                       416 tests (21 mini-domain + 395 unittest)
│
├── e0_core/                          Reference implementation (stable, read-only)
│   ├── primitives.py                   Seven primitives + Axiom A₀
│   ├── engine.py                       Central Law, transition enforcement
│   ├── ontodynamics.py                 Topology, locality, graduated overlap
│   └── ...
│
├── scenarios/                        Scenario Packets for grounded LLM demos
│   ├── competitor_brief/               Domain-specific scenario data
│   ├── incident_postmortem/            Domain-specific scenario data
│   └── research_brief/                 Domain-specific scenario data
│
├── docs/                             Working documents and analysis
│   ├── E0_FORMAL_PAPER_DRAFT_v1.md     Formal E₀ mathematics paper
│   ├── E0_MATH_IMPL_MAPPING_v1.md      Math ↔ Code mapping
│   ├── E0_SUMMATION_GEOMETRY_COMPARISON_v1.md  Geometry comparison results
│   ├── E0_EXTERNAL_VALIDATION_AND_HANDOFF_NOTE_v1.md  Handoff strategy
│   ├── E0_CONTROLLER_STATUS.md         Detailed project status
│   └── ...                             Additional analysis and derivation notes
│
├── _archive/                         Preserved earlier work
│   ├── ARCHIVE_README.md                What is here and why
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
4. Run a hybrid demo: `python -m e0_controller.demo_invoice_llm --mock --hybrid`
5. Read the analysis notes in `docs/`

For a structured handoff to independent reviewers or AI systems, see [docs/E0_EXTERNAL_VALIDATION_AND_HANDOFF_NOTE_v1.md](docs/E0_EXTERNAL_VALIDATION_AND_HANDOFF_NOTE_v1.md).

---

*If engaging with E₀ feels disorienting — that is not a failure. It usually means you have reached a boundary where familiar categories stop applying cleanly. That boundary is where E₀ operates.*
