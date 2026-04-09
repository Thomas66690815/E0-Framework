# E₀ Framework

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19333487.svg)](https://doi.org/10.5281/zenodo.19333487)
[![Tests](https://github.com/Thomas66690815/E0-Framework/actions/workflows/tests.yml/badge.svg)](https://github.com/Thomas66690815/E0-Framework/actions)
[![License: CC BY 4.0](https://img.shields.io/badge/License-CC_BY_4.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)

**A structural decision framework that navigates uncertainty without probabilities.**

---

## What is E₀?

E₀ is a transition framework. It doesn't start with goals, rewards, or probability distributions. It starts with one claim:

> If a structural difference exists and a finite path is available, non-transition is unstable.

From this, everything else follows: learning, forgetting, interference, self-reflection — not as added features, but as structural consequences.

**Seven primitives. One axiom. No free parameters at the foundation.**

| Primitive | Role |
|-----------|------|
| State | Distinguishable configuration |
| Difference (Δ) | Structural non-identity |
| Path | Admissible transition structure |
| Resistance (R) | Structural inertia |
| Historization (H) | Irreversible modification of future resistance |
| Time (τ) | Ordering of historizations |
| Rate (v) | Ordering tendency of realizable transitions |

The full canon: [canon/e0-canon-plain.txt](canon/e0-canon-plain.txt) — 155 lines, plain ASCII.

---

## When would you use E₀?

**When you need decisions under structural uncertainty**, where:

- The domain can be represented as states and transitions
- You don't have (or don't trust) probability distributions
- You want a controller that learns from experience without training data
- You need the system to explain *why* it chose a particular path

**Examples already built:**
- Invoice processing workflows
- ECB interest rate decisions
- Incident postmortem navigation
- Chess position evaluation
- Cross-domain pattern discovery (dreaming)
- Curriculum-based knowledge acquisition

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

### Run the demos

```bash
py -3 -m e0_controller.demo_greedy_trap          # Hybrid routing vs greedy trap
py -3 -m e0_controller.demo_invoice_llm --mock   # LLM-bootstrapped workflow
py -3 -m e0_controller.demo_self_graph            # E₀ reflecting on its own components
py -3 -m e0_controller.demo_multiverse --entropy  # Coupled domains + dream discovery
```

### Run the tests

```bash
py -3 -m pytest e0_controller/ server/ --tb=short -q   # 4369 tests, 0 failures
```

---

## How it works

The controller's core decision at each step:

$$S_{\text{eff}}(x \to y) = \Delta(x,y) \cdot R_{\text{eff}}(x,y)$$

Choose the transition with lowest structural burden. After each transition, historize the outcome — successes reduce future resistance, failures increase it.

**The amplitude layer** goes further. Instead of evaluating single edges, it evaluates *families of forward paths*:

$$I(y; h) = \left|\sum_{p \in \text{paths}(x \to y, h)} e^{-S(p)} \cdot e^{i\Theta(p)}\right|^2$$

Paths that reach the goal *interfere constructively*. Dead ends and loops *interfere destructively*. The controller follows the action with strongest forward support.

**Self-reflection** (Self-Graph): E₀ monitors its own components. If the amplitude layer's overrides cause harm (e.g., loop traps), the controller detects this through its own historization and disables the harmful mechanism. The system must know itself to correct itself.

---

## Architecture

14 layers, bottom-up. Each layer depends only on layers above it.

| Layer | What | Key module |
|-------|------|------------|
| 1 | Primitives | `primitives.py` |
| 2 | Inscription (U/F traces, learning) | `historization.py` |
| 3 | Field theory (Ψ, interference) | `amplitude_overlay.py` |
| 4 | Controller (selection, escalation) | `controller.py` |
| 5 | Reflexion (self-graph, edge proposals) | `self_graph.py`, `dual_reflection.py` |
| 6 | Multi-system (multiverse, coupling) | `multiverse.py`, `coupling_router.py` |
| 7 | Infrastructure (sessions, persistence) | `session.py`, `memory_os.py` |
| 8 | Observation (UI projection) | `observation_controller.py` |
| 9 | Dream mode (cross-domain patterns) | `dream_mode.py` |
| 10 | Structural entropy (forgetting) | `structural_entropy.py` |
| 11 | Sleep–wake cycle | `sleep_wake.py` |
| 12 | Human communication | `perception.py`, `communication.py` |
| 13 | UI rendering | `ui_renderer.py` |
| 14 | Session runner (full pipeline) | `e0_session.py` |

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full layer diagram and core formulas.

**Code documentation:** Every module header is a self-contained architectural document explaining what, why, and which axiom. The code comments are the primary documentation.

---

## What makes E₀ different

| Aspect | Conventional | E₀ |
|--------|-------------|-----|
| Foundation | Probability distributions | Structural difference |
| Learning | Training data / reward | Historization (U/F traces) |
| Lookahead | Tree search / Monte Carlo | Path amplitude interference |
| Forgetting | Not modeled | Structural entropy + sleep–wake |
| Self-awareness | Not modeled | Self-graph (E₀ monitors E₀) |
| Multi-domain | Transfer learning | Dream mode (passive cross-domain observation) |

---

## Project status

| | |
|---|---|
| **Tests** | 4369 passed, 0 failures |
| **Production modules** | 76 |
| **Demos** | 17 |
| **Python** | 3.11+ |
| **CI** | GitHub Actions, 3 Python versions |
| **Canon** | Stable (155 lines, never changes) |

---

## Repository structure

```
E0-Framework/
├── canon/                  The structural definitions — what E₀ IS
├── e0_controller/          All production code, tests, demos, explorations
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
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | 14-layer model, core formulas, navigation guide |
| [E0_MATH_IMPL_MAPPING_v1.md](docs/E0_MATH_IMPL_MAPPING_v1.md) | Every formula → exact code location |
| [E0_TEST_REGISTRY_v2.md](docs/E0_TEST_REGISTRY_v2.md) | Per-file test inventory |
| [E0_EVIDENCE_AND_FALSIFICATION_STATUS_v1.md](docs/E0_EVIDENCE_AND_FALSIFICATION_STATUS_v1.md) | What is proven, what is open |
| [AUDIT_REPORT_v1.md](docs/AUDIT_REPORT_v1.md) | External code audit |
| [PERSONAL_ASSESSMENT_v1.md](docs/PERSONAL_ASSESSMENT_v1.md) | Honest critical assessment |

**The best documentation is in the code.** Start with `primitives.py`, then `historization.py`, then `controller.py`. Every module docstring explains the full context.

---

## Contributing

This framework was developed through human–AI collaboration (Thomas Wehner + AI systems). The `bootstrap.json` file maintains continuity across AI context windows — it is the AI collaborator's persistent memory.

---

## License

[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

## Citation

```bibtex
@software{wehner_e0_2026,
  author    = {Wehner, Thomas},
  title     = {{E₀ Framework} — Structural Transition Controller},
  year      = {2026},
  doi       = {10.5281/zenodo.19333487},
  url       = {https://github.com/Thomas66690815/E0-Framework}
}
```
