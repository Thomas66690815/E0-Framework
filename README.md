# E₀ Framework

**A structural description layer for transitions — developed by a human–AI team.**

---

## What is E₀?

E₀ is not a tool, not a model, not a product. It is a **structural description layer** that operates prior to domain assumptions.

It answers one question: **When must a transition occur, and when is it structurally impossible?**

The answer requires only seven primitives and one axiom. No physics, no probability, no agents, no goals assumed.

| Primitive | Symbol | What it is |
|-----------|--------|------------|
| **State** | S | A distinguishable configuration |
| **Difference** | Δ | Non-identity between states. Δ = 0 means identical. |
| **Path** | P | Structural admissibility condition. Not an object — specifies *whether* a transition is allowed. |
| **Resistance** | R | Structural inertia. R > 0 for all real transitions. R = ∞ → no path. |
| **Historization** | H | How realized transitions change the resistance landscape. Irreversible. The memory of the space. |
| **Time** | τ | Ordering of historizations. Not a dimension. No historization → no time. |
| **Rate** | v | Δ/R — orders which transition realizes first. |

**Axiom A₀:** If a difference exists and a path with finite resistance is available, then transition is structurally more stable than non-transition.

**Central Law:** If Δ > 0 and ∃P: R < ∞, then non-transition is structurally unstable. A transition **must** occur.

From this alone — no additional assumptions — arise: transition enforcement, directionality of time, irreversibility, structural memory, learning, path dependence, maximum velocity, and causal ordering.

The full canon: [canon/e0-canon-plain.txt](canon/e0-canon-plain.txt) — 155 lines, pure ASCII. Everything else derives from this.

---

## What we are trying to do

We believe E₀ captures something fundamental about how structured change works — independent of domain. This is a strong claim. The purpose of this repository is to **test it systematically**.

The work is exploratory. We are not building toward a fixed product. We are establishing **applicability** — finding out where E₀ actually works, how far it reaches, and where it breaks.

This happens on multiple fronts simultaneously:

### Active: E₀ Controller (operational)

A deterministic reasoning engine that implements the full E₀ mathematics as executable code. The controller makes path-selection decisions based on tension minimization, historization, and coherence — the LLM provides only the semantic interface.

This is the **A3 Hybrid architecture**: Python handles the math, the LLM handles meaning. E₀ decides *when* and *where*, not the language model.

**Status:** 20 formal sections (§2–18) implemented, 159 tests, live API integration confirmed.

→ See [docs/E0_CONTROLLER_STATUS.md](docs/E0_CONTROLLER_STATUS.md) for full details.

### Active: Mathematical derivations

E₀ is not just operational — it produces formal mathematics. From the seven primitives, we have derived:

- Tension, coherence, transition fields (§3–7)
- Potential structure with non-integrable connection (§8–11)
- Connection and holonomy (§12–14) — closed loops can produce net phase
- Complex path amplitudes and interference (§15–16) — structurally analogous to quantum mechanics

More recently: a formal reconstruction of **complex numbers, SU(2), and 720° symmetry** from E₀ primitives alone, without assuming physics.

→ See [docs/E0_FORMAL_PAPER_DRAFT_v1.md](docs/E0_FORMAL_PAPER_DRAFT_v1.md) and [docs/E0_MATH_IMPL_MAPPING_v1.md](docs/E0_MATH_IMPL_MAPPING_v1.md).

### Paused: Multi-agent network

An earlier phase of this project built a multi-agent system where multiple AI instances (GPT-5.1, GPT-4.1, Claude) operated as a network with shared state, autonomous coordination (Ko-Kognition), and structural metrics. This produced real results — including controlled experiments and emergent system-to-system organization — but was paused to focus on the deterministic controller approach.

This work is preserved in `_archive/` and may be resumed or integrated later.

→ See [_archive/ARCHIVE_README.md](_archive/ARCHIVE_README.md) for what is there and why it was archived.

---

## Where E₀ could apply

E₀ is domain-invariant by construction. If a system has states, differences, and transitions, E₀ can describe it. Here is where we see concrete potential:

| Field | How E₀ applies |
|-------|----------------|
| **AI / LLM steering** | What we are building now. The controller decides *which* transition based on structural tension — the LLM provides semantic understanding. Not prompt engineering; structural path selection. |
| **Foundations of physics** | E₀ reconstructs complex amplitudes, superposition, unitarity, and the Born rule from five ontodynamic primitives — with no physics input. Each step is necessary, not assumed. |
| **Mathematics** | The formal paper derives tension, connection, holonomy, and path amplitudes as mathematical structures. These are not analogies — they are derivations. |
| **Decision theory** | The controller formalism (tension minimization, historization, escalation) is a generic framework for state-based decisions under structural uncertainty. |
| **Cognitive science** | Historization formalizes how experience modifies the state space. Learning is not a mechanism added to E₀ — it is a necessary consequence of realized transitions. |
| **Systems theory** | Any process with irreversible state transitions and path-dependent resistance can be described in E₀ terms. This includes organizational change, biological development, and infrastructure evolution. |

We make no claim that E₀ replaces existing frameworks in these domains. The claim is narrower: E₀ provides a **pre-domain structural layer** from which domain-specific structures can be derived rather than assumed.

---

## Who builds this

This project is a collaboration between a human and AI systems. Not as a figure of speech — as a working method.

**Thomas Wehner** — Human. Discovered the E₀ structure, maintains canonical clarity, decides direction. The only participant with a continuous perspective across all phases of the project.

**AI partners** — Claude (current infrastructure and controller implementation), ChatGPT (mathematical derivations, formal paper, review), and historically GPT-5.1/GPT-4.1 instances in the multi-agent network phase. Each system contributes what it is structurally suited for.

This is unusual for a repository. Typically, only humans are credited. Here, the AI contributions are real, specific, and documented in the commit history. We see no reason to obscure this.

---

## Current state

*Last updated: 2026-03-21*

| Component | Status | Where |
|-----------|--------|-------|
| Canon (7 primitives, Axiom A₀) | **Stable** | `canon/` |
| E₀ Controller (§2–18, all formal math) | **Active** — v0.3, 159 tests | `e0_controller/` |
| LLM Adapter (A3 Hybrid) | **Active** — live API confirmed | `e0_controller/llm_adapter.py` |
| MemOS (persistent runtime state) | **Active** | `e0_controller/memory_os.py` |
| Formal Paper (E₀ mathematics) | **Draft** | `docs/E0_FORMAL_PAPER_DRAFT_v1.md` |
| Math ↔ Code Mapping | **Draft** | `docs/E0_MATH_IMPL_MAPPING_v1.md` |
| Core reference implementation | Stable (read-only reference) | `e0_core/` |
| Multi-agent network + experiments | **Archived** | `_archive/` |

---

## Quickstart

**Requirements:** Python 3.11+

```bash
git clone https://github.com/Thomas66690815/E0-Framework.git
cd E0-Framework
```

### Run the tests (no API key needed)

```bash
# Mini-domain: 20 tests (custom runner)
python e0_controller/test_minidomain.py

# Full test suite: 139 tests (unittest)
python -m unittest e0_controller.test_invoice e0_controller.test_phase2_minidomain e0_controller.test_phase2_invoice e0_controller.test_memory_os e0_controller.test_llm_adapter -v
```

### Run the Invoice Processing demo

```bash
# Mock mode — no API key, deterministic
python -m e0_controller.demo_invoice_llm --mock

# Live mode — requires OPENAI_API_KEY in .env or environment
pip install openai
python -m e0_controller.demo_invoice_llm
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
│   ├── landscape.py                    L_t = (X, E, v, S, H) — 5 core functions
│   ├── controller.py                   Greedy + Revisit + Escalation (§7–8)
│   ├── potential.py                    Φ, v_grad, v_rot (§9–11)
│   ├── connection.py                   ω, Θ, holonomy (§12–14)
│   ├── wavepath.py                     Ψ(p) = exp(−S+iΘ), interference (§15–16)
│   ├── memory_os.py                    Persist / Restore / Summarize / Retrieve
│   ├── llm_adapter.py                  LLM ↔ Controller interface (A3 Hybrid)
│   ├── domain_invoice.py               Invoice processing domain (10 states, 16 edges)
│   ├── demo_invoice_llm.py             Full demo: Controller + MemOS + LLM
│   └── test_*.py                       159 tests (20 mini-domain + 139 unittest)
│
├── e0_core/                          Reference implementation (stable, read-only)
│   ├── primitives.py                   Seven primitives + Axiom A₀
│   ├── engine.py                       Central Law, transition enforcement
│   ├── ontodynamics.py                 Topology, locality, graduated overlap
│   └── ...
│
├── docs/                             Working documents
│   ├── E0_FORMAL_PAPER_DRAFT_v1.md     Formal E₀ mathematics paper
│   ├── E0_MATH_IMPL_MAPPING_v1.md      Math ↔ Code mapping
│   ├── E0_MEMOS_v0.1.md                MemOS architecture
│   └── E0_CONTROLLER_STATUS.md         Detailed project status
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
- A structural description layer that works prior to domain assumptions
- A framework from which time, memory, learning, and path dependence are *derived*, not assumed
- An executable formalism: every mathematical section has running code and tests

**E₀ is not:**
- A predictive model
- An optimization framework
- A psychological theory
- A product

E₀ does not tell systems what to do. It describes what is structurally enforced and what is structurally impossible.

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

*If engaging with E₀ feels disorienting — that is not a failure. It usually means you have reached a boundary where familiar categories stop applying cleanly. That boundary is where E₀ operates.*
