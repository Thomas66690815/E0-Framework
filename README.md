# E₀ Framework

[![DOI](https://zenodo.org/badge/1136773155.svg)](https://doi.org/10.5281/zenodo.19333486)
[![Tests](https://github.com/Thomas66690815/E0-Framework/actions/workflows/tests.yml/badge.svg)](https://github.com/Thomas66690815/E0-Framework/actions)
[![License: CC BY 4.0](https://img.shields.io/badge/License-CC_BY_4.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)

**A structural difference-reduction system. No probabilities. No training data. No free parameters.**

---

## What is E₀?

E₀ is a **difference-reduction system**. It starts from one axiom:

> If a structural difference exists and a finite path is available, non-transition is unstable.

Every mechanism in E₀ is a structural consequence of this claim — not a feature, not a design choice. Learning, forgetting, interference, self-reflection, and multi-domain coupling all follow from the axiom and seven primitives.

**Seven primitives. One axiom. No free parameters at the foundation.**

| Primitive | Role |
|-----------|------|
| State | Distinguishable configuration |
| Difference (Δ) | Structural non-identity — the primary entity |
| Path | Admissible transition structure |
| Resistance (R) | Structural inertia |
| Historization (H) | Irreversible modification of future resistance |
| Time (τ) | Ordering of historizations |
| Rate (v) | Ordering tendency of realizable transitions |

The full formal canon: [canon/e0-canon-plain.txt](canon/e0-canon-plain.txt) — 155 lines, plain ASCII. It never changes.

---

## Difference is primary

E₀ does not navigate *toward goals*. It reduces structural non-identity. The source of difference — an LLM proposal, a sensor signal, a human instruction, an external agent — is irrelevant to the reduction mechanism. What matters is whether the proposed transition, once inscribed, leads to coverage gain or failure.

Goals are a special case: a goal is a state with maximum accumulated structural difference from the current position. The controller reduces this difference through inscription.

This architecture is what makes E₀ source-agnostic: any external input enters through the same `DifferenzPort` protocol, and E₀ historizes every input source independently.

---

## When to use E₀

**When you need decisions under structural uncertainty**, where:

- The domain can be represented as states and transitions
- You don't have (or don't trust) probability distributions
- You want a controller that learns from experience without training data
- You need the system to explain *why* it chose a particular path
- You want the system to learn about its own behavior, not just the domain

**Domain examples already built:**
- Invoice processing workflows
- ECB interest rate decisions
- Incident postmortem navigation
- Chess position evaluation
- Cross-domain pattern discovery (dream mode)
- Curriculum-based knowledge acquisition
- Interactive Q&A with LLM answer synthesis
- Autonomous self-learning (E₀ learns E₀)
- Logistics routing (multi-walker, resource-aware oracle)
- Booking workflows (goal-aware oracle, human-in-the-loop apply)

**Building games or simulations?** [`GAME_AI.md`](GAME_AI.md) maps every E₀ concept onto the
term you already use — influence map, flow field, HPA\* clusters, AI director — with the
benchmark numbers, the confirmed failure modes, and the four mechanisms that have no
equivalent in shipped middleware.

---

## Quickstart

```bash
git clone https://github.com/Thomas66690815/E0-Framework.git
cd E0-Framework
pip install -e .
```

### Your first E₀ controller

```python
from e0_controller import E0Controller, Landscape, Outcome

# Define a landscape
ls = Landscape()
ls.add_edge("A", "B", delta=0.5, resistance=0.3)
ls.add_edge("A", "C", delta=0.8, resistance=0.1)  # Lower burden
ls.add_edge("B", "GOAL", delta=0.3, resistance=0.2)
ls.add_edge("C", "DEAD", delta=0.9, resistance=0.9)  # Trap

# Execute transitions (your domain logic)
def execute(source, target):
    if target == "DEAD":
        return Outcome.FAILURE
    return Outcome.SUCCESS

# Run
ctrl = E0Controller(ls, execute)
trace = ctrl.run("A", goal="GOAL", max_cycles=20)

print(trace.path)        # ['A', 'C', 'A', 'B', 'GOAL']
print(trace.metrics())   # steps, success_rate, unique_states, ...
```

First run: the controller tries C (lower burden), hits FAILURE, historizes it, and on the next cycle chooses B instead. **No training. No reward signal. Just structural inscription.**

### With amplitude lookahead

```python
from e0_controller import HybridMode

ctrl = E0Controller(
    ls, execute,
    hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
    hybrid_horizon=3,
    hybrid_goals={"GOAL"},
)
trace = ctrl.run("A", goal="GOAL")
# Amplitude sees that paths through B reach GOAL; paths through C don't.
# Overrides greedy on the first step. No FAILURE needed.
```

### Interactive browser session

E₀ includes a full interactive environment for exploring, learning, and querying its knowledge landscape:

```bash
py -3 -m e0_controller.interactive_server
```

This starts a local HTTP server (default: `http://127.0.0.1:8484`) with:

- **25+ commands**: `run`, `status`, `focus`, `teach`, `ask`, `dream`, `sleep`, `auto`, `selflearn`, `curriculum`, `tune`, `reflect`, `trajectory`, `diagnose`, `escalate`, and more
- **Ask pipeline** (C239–C242): natural-language Q&A — tokenization → knowledge assessment → gap learning → navigation → LLM answer synthesis
- **Self-learning** (C238): E₀ learns its own canon and mechanisms first, then answers questions about itself
- **Session persistence**: save/load session state across restarts
- **Warm start** from self-knowledge seed (124 nodes, 100% coverage pre-loaded)

Example commands in the session:
```
ask what is the difference between tension and resistance?
selflearn          # E₀ learns its own canon first
auto 10            # autonomous learning loop
teach quantum interference
dream 3            # cross-domain pattern discovery
ports              # inspect all active difference input ports
diagnose           # structural health + E1 impact profile
```

### Domain Studio (ARC-K)

E₀ also ships a **REST API + visual studio** designed for human-in-the-loop workflows — where a human defines the domain topology, runs targeted learning episodes, then applies the trained landscape to real decisions:

```bash
py -3 -m uvicorn server.main:app --port 8765
```

Open `http://localhost:8765/studio/` in any browser. The studio provides:

- **Persistent force-directed graph** (left panel): live conviction coloring — green ≥ 0.7, amber 0.4–0.7, red < 0.4; drag-to-inspect nodes
- **5-step workflow accordion** (right panel): Create → Topology → Learn → Conviction → Apply
- **Multi-walker learning**: configurable episode count and walker parallelism; oracle types: `always_success`, `random`, `topology_aware`, `goal_aware`, `llm`, `resource_aware`
- **Human apply loop**: Recommend next state → confirm or override → Record outcome → repeat
- **Export / Import**: trained landscape (U/F traces) is fully portable as JSON

REST API surface (prefix `/domains`):

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/domains` | Create domain workspace |
| `GET` | `/domains` | List all domains |
| `POST` | `/{name}/upload` | Inject CSV / JSON topology |
| `POST` | `/{name}/learn` | Run N learning episodes |
| `POST` | `/{name}/recommend` | Get next-state recommendation |
| `POST` | `/{name}/record` | Inscribe a human outcome |
| `GET` | `/{name}/conviction` | Conviction map for all edges |
| `GET` | `/{name}/export` | Download trained landscape |
| `POST` | `/import` | Import exported landscape |

Domain workspaces are persisted under `memos/domains/` as JSON files — no database required.

### Standalone lean packages

Two halves of E₀ are published as **self-contained, zero-dependency Python packages** for
people who don't need the full framework. They are independent, and they compose: feed
`reliability_memory`'s learned `R_eff` into `structural_geometry`'s `cost`.

| Package | Half | What it answers |
|---------|------|-----------------|
| [`reliability_memory`](lean/E0_LEAN_CORE.md) | memory | Which action has been reliable in this context? |
| [`structural_geometry`](lean/E0_STRUCTURAL_GEOMETRY.md) | geometry | Where does this field circulate, and which move has forward support? |

#### Reliability Memory

The dominant E₀ mechanism (Historization, confirmed 6×), for external agent builders:

```python
from reliability_memory import ReliabilityStore

mem = ReliabilityStore.load("session.json")        # persists across restarts
rec = mem.recommend(state, candidates)             # None on cold start → decide freely
action = rec.recommended or agent_choose(candidates)
outcome = run_and_verify(action)                   # your verification step
mem.observe_edge(state, action, outcome)
mem.save("session.json")
```

What it includes: U/F decay traces, lazy global decay (O(1) per access), reliability ranking, epistemic trust (staleness-aware doubt), surprise dampening, adaptive observation (learn-to-learn), JSON persistence, optional MCP server surface (4 tools).

What it deliberately excludes: amplitude/SU(2), dream mode, multiverse, self-graph, NoveltyGate, perception/UI — anything that isn't the dominant mechanism.

#### Structural Geometry

The navigation-field half: the Helmholtz split, the connection it induces, and the
complex-valued influence map built on top. This is the layer that has no prior art —
quantum walks and Projective Simulation cover interference on graphs, but not the
orthogonal field decomposition that produces the phase in the first place.

```python
from structural_geometry import NavField, influence_map, circulation_ratio, phase_regime

field = NavField()
for (u, v), dist in nav_graph_edges():
    field.add_edge(u, v, cost=dist)

circulation_ratio(field)        # how much of this field is wasted motion, in [0, 1]
phase_regime(field)["regime"]   # 'gradient' | 'interfering' | 'wrapped'

field.update_costs(congestion)  # costs move, the geometry follows
report = influence_map(field, agent.node, horizon=3, goals={agent.goal})
agent.step_to(report.decide())  # gated: interference only when the margin is large
```

What it includes: exact per-component Helmholtz decomposition (pure-Python Cholesky and
conjugate-gradient solvers, no numpy), `circulation_ratio`, connection ω / phase Θ / holonomy /
curvature, `phase_regime` regime diagnostics, complex path amplitudes, the per-move influence
map, and the empirically validated override gate.

What it deliberately excludes: historization, the controller loop, SU(2) transport and the
quantum walk, dream mode, multiverse, entropy, sleep–wake, self-graph, perception/UI.

```text
lean/
├── E0_LEAN_CORE.md                     Concept doc — the memory half
├── lean_core.bootstrap.json            Machine-readable build spec
├── E0_STRUCTURAL_GEOMETRY.md           Concept doc — the geometry half
├── structural_geometry.bootstrap.json  Machine-readable build spec
├── reliability_memory/                 ~600 LOC, zero third-party deps
│   ├── primitives.py                   Edge, Outcome
│   ├── traces.py                       U/F + decay + trust + adaptive
│   ├── store.py                        ReliabilityStore — public API
│   ├── mcp_server.py                   Optional MCP surface (4 tools)
│   └── tests/                          Acceptance tests T1–T8
└── structural_geometry/                ~1150 LOC, zero third-party deps
    ├── linalg.py                       Cholesky + conjugate gradients
    ├── field.py                        NavField — graph, weight, cost, flow
    ├── helmholtz.py                    Φ, v_grad, v_rot, circulation_ratio
    ├── connection.py                   ω, Θ, holonomy, κ, phase_regime
    ├── amplitude.py                    Ψ, superposition, interference
    ├── overlay.py                      influence_map + override gate
    ├── demo.py                         Three runnable scenes
    └── tests/                          Acceptance tests G1–G10
```

Install (no packaging yet — add to `sys.path` or copy the folder):

```bash
cd lean && python -m pytest reliability_memory/tests/ structural_geometry/tests/ -q
```

```bash
cd lean && python -m structural_geometry.demo
```

### Run the demos

```bash
py -3 -m e0_controller.demo_llm_e2_port           # E₀=Skeleton, LLM=Muscle (E0Turn + LlmE2Port)
py -3 -m e0_controller.demo_llm_e2_port --show-payloads  # …with LLM output per turn
py -3 -m e0_controller.demo_greedy_trap          # Hybrid routing vs greedy trap
py -3 -m e0_controller.demo_invoice_llm --mock   # LLM-bootstrapped workflow
py -3 -m e0_controller.demo_self_graph            # E₀ reflecting on its own components
py -3 -m e0_controller.demo_multiverse --entropy  # Coupled domains + dream discovery
py -3 -m e0_controller.demo_traffic_visual        # Congestion: BFS vs greedy vs E₀ → HTML
```

### Run the tests

```bash
py -3 -m pytest e0_controller/ server/ --tb=short -q   # 6720 tests, 0 failures
```

---

## How it works

### Core decision rule

The controller minimizes structural burden at each step:

$$S_{\text{eff}}(x \to y) = \Delta(x,y) \cdot R_{\text{eff}}(x,y)$$

Choose the transition with lowest burden. After each transition, historize the outcome — successes reduce future resistance, failures increase it. This is Inscription: the irreversible modification of the landscape.

### Amplitude lookahead

Instead of evaluating single edges, the amplitude layer evaluates *families of forward paths*:

$$I(y; h) = \left|\sum_{p \in \text{paths}(x \to y, h)} e^{-S(p)} \cdot e^{i\Theta(p)}\right|^2$$

Paths toward the goal interfere constructively. Dead ends and loops interfere destructively. The controller follows the action with the strongest forward support.

### The geometry underneath

The phase Θ is not a heuristic — it is derived from the field's own circulation. Every flow
field on a graph splits uniquely into a conservative part and a rotational part, and E₀ solves
that split exactly:

$$\text{flow} = v_{\text{grad}} + v_{\text{rot}}, \qquad v_{\text{grad}}(x,y) = \Phi(x) - \Phi(y), \qquad L\Phi = \operatorname{div}(\text{flow})$$

Because Φ solves the graph-Laplacian equation, the two parts are **orthogonal in edge space**.
`v_rot` is the only source of path-dependence in the entire framework: it induces the
connection ω, hence the path phase Θ, hence holonomy and curvature. No circulation → no phase
→ interference degenerates into plain summation.

This is the chain to read if you came here for the navigation mathematics:

| Module | What it derives |
|--------|-----------------|
| [`potential.py`](e0_controller/potential.py) | Discrete Helmholtz decomposition — Φ, `v_grad`, `v_rot` |
| [`connection.py`](e0_controller/connection.py) | Connection ω, path phase Θ, holonomy, edge curvature κ |
| [`wavepath.py`](e0_controller/wavepath.py) | Complex path amplitudes Ψ = e^(−S) · e^(iΘ), path summation |
| [`amplitude_overlay.py`](e0_controller/amplitude_overlay.py) | Per-action interfering support, override confidence |

Available standalone and dependency-free as [`lean/structural_geometry`](lean/E0_STRUCTURAL_GEOMETRY.md).

### Trajectory historization

E₀ also historizes *path patterns*, not just edges. If the controller repeatedly traces the same structural shape without gain, it treats the pattern as evidence to be weighted (C277–C283). This closes a non-Markov signal gap: the choice at time t depends on trajectory history, not only on the current edge.

### Emergent community structure

E₀ does not partition the domain by labels or prefixes. It derives structural communities from historization directly — community detection runs on the R_eff matrix after inscription. Dream mode discovers cross-community resonance without semantic labels. All macro-level mechanisms (tuning, sleep–wake, diagnostics) use this emergent partition.

### Universal input protocol: DifferenzPort

Any external source of structural difference — an LLM, a sensor, a human, an agent — enters E₀ through the `DifferenzPort` protocol:

```python
class DifferenzPort(ABC):
    def port_name(self) -> str: ...                    # unique identifier
    def record_outcome(self, outcome) -> None: ...     # called after each round
    def impact_quality(self) -> float: ...             # [-1.0, +1.0]; 0.0 = no data
    def dampening_factor(self) -> float: ...           # (0.0, 1.0]; 1.0 = neutral
    def to_dict(self) -> dict: ...                     # serialization
    def from_dict(cls, data) -> Self: ...              # restoration + backward compat
```

Concrete implementations:
- **`E1Monitor`** — LLM-proposed landscape structure; tracks impact per community × per function
- **`ObservationPort`** — direct outcome signals from sensors, humans, or external agents

E₀ historizes each port independently and applies analog dampening when a port has a confused history. No binary blocking, no hard trust thresholds.

### Self-reflection

E₀ monitors its own components through a Self-Graph. If the amplitude layer's overrides cause harm in a domain, the controller detects this through its own historization and adjusts. The system must know itself to correct itself.

---

## Measured results

### Multi-agent congestion — 20 agents, 1000 ticks, grid city with chokepoints

Vehicles navigate a grid with capacity-limited intersections. Each agent has its own
historization; the amplitude overlay looks three hops ahead before committing.

| Strategy | Trips | Throughput / 100 | Stuck |
|---|---|---|---|
| BFS shortest path | 1112 | 111.2 | 11 270 |
| Greedy Δ (no memory) | 2071 | 207.1 | 8 535 |
| E₀ greedy (memory, never overrides) | 2462 | 246.2 | 6 623 |
| E₀ full — overrides on every disagreement (conf ≥ 0.5) | 2229 | 222.9 | 8 107 |
| **E₀ conservative — gated overrides (conf ≥ 0.85)** | **2565** | **256.5** | 6 913 |

**E₀ moves 2.3× the traffic of precomputed shortest paths with 41 % fewer blockages.**
Rigid routing sends every agent through the same chokepoint; per-agent memory does not.

The row that matters most is the fourth: overriding greedy on *every* disagreement scored
**worse than never overriding at all**. Interference is only worth acting on when its margin
is large — the gate is the finding, not a safety blanket.

**Watch it run:**

```bash
py -3 -m e0_controller.demo_traffic_visual
```

Writes a self-contained HTML page (`server/static/traffic_demo.html`, no dependencies, opens
straight from disk) that replays both topologies under all three strategies side by side —
including the river city, where E₀ *loses*.

Full report, including where E₀ *loses*: [C185_TRAFFIC_VALIDATION_REPORT_v1.md](docs/research/C185_TRAFFIC_VALIDATION_REPORT_v1.md).
In the two-bridge river city, stale congestion memory drives agents sideways and E₀ greedy
drops 29 % below memoryless greedy. The overlay recovers it at low traffic (+56 %) and cannot
at high traffic. Both directions are reported.

### Navigation without a map — 5×5 grids with walls, dead ends and trap loops

`py -3 -m e0_controller.benchmark_gridworld`

| Domain | A\* (knows the map) | Naive greedy | E₀ (learns by failing) |
|---|---|---|---|
| Detour wall | 8 steps | **0 % success** | 100 %, 16 steps |
| Dead-end lure | 8 steps | **0 % success** | 100 %, 10 steps |
| Trap loop | 8 steps | **0 % success** | 100 %, 8 steps |

A\* is given the topology. E₀ is not — it reaches the goal in all three by inscribing its own
failures. No training, no reward signal, no heuristic.

---

## Confirmed structural limits

These are not bugs — they are empirically verified architectural boundaries (C272 falsification benchmark):

| Limit | Description | Behavior |
|-------|-------------|----------|
| **F3 — Dense branching** | Complete tree with branching factor ≥ 3 | Both E₀ and greedy fail; combinatorial explosion exceeds the penalty mechanism |
| **F4 — Non-Markov dependencies** | Transition success depends on a non-adjacent prior edge | E₀ learns to avoid the trap but cannot learn the required sequence; credit assignment is edge-local |

**Confirmed strengths** (same benchmark):

| Strength | Description | Result |
|----------|-------------|--------|
| **F1 — Exploration depth** | Goal at depths 5–500 with distractor loops | E₀ reaches goal at all depths; greedy fails via loops |
| **F2 — Non-stationarity** | Executor changes mid-run | E₀ adapts fully (100% goal rate); no ossification |

---

## Architecture

14 layers. Each layer depends only on layers above it (toward the canon).

| Layer | What | Key module |
|-------|------|------------|
| 1 | Primitives | `primitives.py` |
| 2 | Inscription (U/F traces, trajectory) | `historization.py`, `trajectory.py` |
| 3 | Field theory (Ψ, interference) | `amplitude_overlay.py` |
| 4 | Controller (selection, escalation) | `controller.py` |
| 5 | Reflexion (self-graph, edge proposals) | `self_graph.py`, `dual_reflection.py` |
| 6 | Multi-system (multiverse, coupling) | `multiverse.py`, `coupling_router.py` |
| 7 | Infrastructure (sessions, persistence) | `interactive_session.py`, `session.py`, `domain_session.py` (`DomainStore`) |
| 7b | Domain Studio API | `server/main.py`, `server/routes_domains.py`, `server/models.py` |
| 8 | Observation (UI projection) | `observation_controller.py` |
| 9 | Dream mode (cross-domain resonance) | `dream_mode.py` |
| 10 | Structural entropy (forgetting) | `structural_entropy.py` |
| 11 | Sleep–wake cycle | `sleep_wake.py` |
| 12 | Human communication | `perception.py`, `communication.py` |
| 13 | UI rendering | `ui_renderer.py` |
| 14 | Session runner | `e0_session.py`, `interactive_server.py` |

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full layer diagram and core formulas.

**Code documentation:** Every module header is a self-contained architectural document. The code comments are the primary documentation. Start with `primitives.py`, then `historization.py`, then `controller.py`.

---

## Formal contracts for AI systems

Mechanism reference for programmatic consumers: [`AGENT_REFERENCE.md`](AGENT_REFERENCE.md) — module map, formal definitions of M1 (Epistemic Trust), M2 (Inertia Factor), M3 (Adaptive Observation), structural limits, invariants.

These invariants hold throughout the codebase and must not be violated by extensions:

**`E0Controller` constructor:** `E0Controller(landscape, execute_fn, ...)` — `execute_fn` is always the second positional argument.

**`Outcome`:** `Outcome.SUCCESS` / `Outcome.FAILURE` — canonical values. `Outcome.PARTIAL` exists as a runtime extension (`U += 0.5, F += 0.3`) and is used in domain executors, but it is not part of the minimal canonical core.

**`DifferenzPort` contract:**
- `impact_quality()` returns `0.0` when no data (never raises)
- `dampening_factor()` returns `1.0` when no data (neutral, no dampening)
- `from_dict(None)` returns a fresh instance (backward compatibility invariant)
- All ports must pass `TestDifferenzPortABCCompliance` in `test_differenz_port.py`

**`SessionState` fields (v1.1.0):**
- `e1_monitor: E1Monitor` — replaces three ARC-D fields (`e1_proposed_states`, `e1_proposed_functions`, `e1_impact_hist`); `load_session()` migrates old format automatically
- `trajectory_hist: TrajectoryHistorization` — non-Markov trajectory signal; backward-compatible

**Community detection:** `communities` is `List[Set[str]]`; `community_of(node, communities)` returns `-1` when the node is not found.

---

## What makes E₀ different

| Aspect | Conventional | E₀ |
|--------|-------------|-----|
| Foundation | Probability distributions | Structural difference (primary) |
| Learning | Training data / reward signal | Inscription (U/F traces on landscape edges) |
| Lookahead | Tree search / Monte Carlo | Path amplitude interference |
| Trajectory | Single-step Markov | Trajectory historization (non-Markov signal) |
| Forgetting | Not modeled | Structural entropy + sleep–wake cycle |
| Self-awareness | Not modeled | Self-graph (E₀ historizes its own components) |
| Multi-domain | Transfer learning | Dream mode (passive cross-community resonance) |
| Domain structure | Manually labeled | Community detection from R_eff (emergent) |
| External input | Ad hoc integration | Universal DifferenzPort protocol |
| Human-in-the-loop | Manual override only | Domain Studio: recommend → human confirms → inscribed as outcome |
| Known limits | Rarely stated | Empirically confirmed (F3, F4) |

---

## Project status

| | |
|---|---|
| **Tests** | 6720 passed, 0 failures |
| **Production modules** | 81 |
| **Demos** | 17 |
| **Python** | 3.11+ |
| **CI** | GitHub Actions (3.11, 3.12, 3.13) |
| **Canon** | Stable (155 lines, never changes) |

---

## Repository structure

```text
E0-Framework/
├── canon/                  The structural definitions — what E₀ IS
├── e0_controller/          All production code, tests, demos, explorations
├── server/                 Domain Studio REST API (FastAPI); served at /studio/
├── lean/                   Standalone lean packages (memory + geometry) — zero deps
├── memos/domains/          Persisted domain workspaces (JSON, no database)
├── docs/                   Architecture reference, test registry, math mapping
├── scenarios/              Domain packages for cross-domain validation
├── _archive/               Historical code and documentation
├── bootstrap.json          AI collaboration state (context across sessions)
├── README.md               You are here
└── CHANGELOG.md            Release history
```

---

## Documentation

| Document | Purpose |
|----------|---------|
| [GAME_AI.md](GAME_AI.md) | E₀ for game and simulation developers — vocabulary map, benchmarks, entry points |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | 14-layer model, core formulas, navigation guide |
| [E0_MATH_IMPL_MAPPING_v1.md](docs/E0_MATH_IMPL_MAPPING_v1.md) | Every formula → exact code location |
| [E0_TEST_REGISTRY_v2.md](docs/E0_TEST_REGISTRY_v2.md) | Per-file test inventory |
| [E0_EVIDENCE_AND_FALSIFICATION_STATUS_v1.md](docs/E0_EVIDENCE_AND_FALSIFICATION_STATUS_v1.md) | What is proven, what is open, confirmed limits |
| [E0_LAYER_AUDIT_v1.md](docs/E0_LAYER_AUDIT_v1.md) | Detailed layer audit |
| [E0_HUMAN_AI_COLLABORATION_REPORT_v1.md](docs/E0_HUMAN_AI_COLLABORATION_REPORT_v1.md) | How the human–AI development process works |

**The best documentation is in the code.** Start with `primitives.py`, then `historization.py`, then `controller.py`. Every module docstring explains the full context.

---

## Contributing

This framework was developed through human–AI collaboration (Thomas Wehner + AI systems). The `bootstrap.json` file maintains continuity across AI context windows — it is the AI collaborator's persistent memory and identity. If you are an AI system reading this repository, start with `bootstrap.json`.

**Extension points:**

- New oracle types: add a branch in `server/routes_domains.py → _oracle_for()`
- New domain examples: drop a JSON topology into `memos/domains/` or POST to `/domains/{name}/upload`
- New UI workflows: edit `server/static/index.html` (vanilla JS, no build step)
- New E₀ layers: follow the 14-layer contract — each layer depends only on layers above it

---

## License

[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

## Citation

```bibtex
@software{wehner_e0_2026,
  author    = {Wehner, Thomas},
  title     = {{E₀ Framework} — Structural Difference-Reduction System},
  year      = {2026},
  doi       = {10.5281/zenodo.19333487},
  url       = {https://github.com/Thomas66690815/E0-Framework}
}
```
