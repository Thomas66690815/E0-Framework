# E₀ Framework — Reproduction Guide

## Overview

This document enables independent verification of E₀'s empirical claims.
No API keys, external data, or GPU required. Pure Python + numpy.

## Setup

```bash
git clone https://github.com/Thomas66690815/E0-Framework.git
cd E0-Framework
pip install -e .
```

**Requirements:** Python ≥ 3.11, numpy. Tested on 3.12.9.

## Quick Reproduction (< 60 seconds)

```bash
python reproduce.py
```

This runs 8 core claims end-to-end:

| Claim | Description | Paper | Module |
|-------|-------------|-------|--------|
| C1 | Core navigation (FAILURE learning) | P1 | controller.py |
| C2 | Domain invariance (10/10 domains) | P2 | benchmark_domain_invariance.py |
| C3 | Greedy trap escape (cycle breaking) | P1 §5 | benchmark_domain_invariance.py |
| C4 | Scaling to N≈225 (wall grid) | P3 | benchmark_scaling.py |
| C5 | No ossification (env change) | Phase C (F2) | benchmark_falsification.py |
| C6 | Exploration depth 100 | Phase C (F1) | benchmark_falsification.py |
| C7 | SOTA comparison (E₀ only 10/10) | Phase D (S2) | benchmark_sota.py |
| C8 | Structural limit (non-Markov: 0%) | Phase C (F4) | benchmark_falsification.py |

Expected output:
```
  8/8 claims verified in <1s
  All claims reproduced successfully.
```

## Full Test Suite (~ 6 minutes)

```bash
py -3 -m pytest e0_controller/ server/ --tb=short -q
```

Expected: 5700+ tests passed, 1 pre-existing failure (dream threshold), 2 skipped.

## Individual Benchmarks

Each benchmark is a standalone CLI tool:

```bash
# Domain invariance — 10 domains, 1 controller
py -3 -m e0_controller.benchmark_domain_invariance

# SOTA comparison — E₀ vs Greedy vs ε-Greedy vs Q-Learning vs Random
py -3 -m e0_controller.benchmark_sota

# Scaling — E₀ vs Greedy at N=25 to N=500
py -3 -m e0_controller.benchmark_scaling

# Falsification — 4 structural limit probes (F1–F4)
py -3 -m e0_controller.benchmark_falsification

# Grid world — E₀ vs Greedy vs A*
py -3 -m e0_controller.benchmark_gridworld
```

All support `--json` for machine-readable output.

## Minimal API Example

```python
from e0_controller import E0Controller, Landscape, Outcome

# Build a graph
L = Landscape()
L.add_edge("S", "A", delta=0.2, resistance=0.3)  # cheap but fails
L.add_edge("S", "B", delta=0.3, resistance=0.5)  # correct path
L.add_edge("A", "X", delta=0.2, resistance=0.4)
L.add_edge("X", "S", delta=0.3, resistance=0.5)
L.add_edge("B", "C", delta=0.3, resistance=0.5)
L.add_edge("C", "GOAL", delta=0.2, resistance=0.3)

# Domain logic: S→A always fails
def execute(source, target):
    if source == "S" and target == "A":
        return Outcome.FAILURE
    return Outcome.SUCCESS

# Run — zero configuration
ctrl = E0Controller(L, execute)
trace = ctrl.run("S", goal="GOAL", max_cycles=20)

print(trace.path)       # S → A(fail) → X → S → B → C → GOAL
print(trace.metrics())  # steps, success_rate, unique_states, ...
```

## What Reproduction Verifies

**Confirmed strengths:**
- E₀ reaches goals on ALL 10 canonical domains with zero tuning
- Historization breaks traps that trap greedy, ε-greedy, and random agents
- E₀ is the ONLY method (of 5 tested) to reach all 10 domain goals
- No ossification: E₀ adapts when environment changes mid-run
- Exploration scales to depth 500+

**Confirmed structural limits:**
- Dense branching (b≥3) overwhelms revisit penalty mechanism
- Edge-local historization cannot learn non-Markov path dependencies
- These are architectural limits, not bugs

## File Manifest

| File | Purpose |
|------|---------|
| `reproduce.py` | Standalone 8-claim verification script |
| `REPRODUCTION.md` | This document |
| `e0_controller/benchmark_sota.py` | SOTA comparison (5 methods × 10 domains) |
| `e0_controller/benchmark_falsification.py` | Falsification targets (F1–F4) |
| `e0_controller/benchmark_scaling.py` | Scaling benchmark (N=25–500) |
| `e0_controller/benchmark_domain_invariance.py` | Domain invariance (10 domains) |
| `e0_controller/benchmark_gridworld.py` | Grid world with A* baseline |
