"""
SOTA Comparison Benchmark (Phase D — S2)
=========================================
Positions E₀ relative to standard decision-making baselines on the
10 canonical domains from the Domain-Invariance Benchmark (C53).

Methods:
  E₀         — Full controller with Historization, revisit penalty, escalation
  Greedy     — Memoryless argmin(Δ·R₀), always advance, no learning
  ε-Greedy   — 20% random exploration, 80% greedy, no memory
  Q-Learning — Tabular Q-learning (α=0.3, γ=0.9, ε=0.2→0.05 decay)
  Random     — Uniform random neighbor selection

All methods use the same interface:
  - Current state → choose edge → execute → receive Outcome → advance
  - Same max_cycles budget per domain
  - Goal: reach the goal state

This is NOT a claim that E₀ is "better than RL". The comparison isolates
what E₀'s edge-level Historization provides vs. standard approaches on
E₀'s own domain types (traps, cycles, dead-ends, stochastic outcomes).

Honest framing:
  - These are tiny domains (4–22 nodes). SOTA RL shines on large MDPs.
  - E₀ has structural advantages here: edge-level memory, revisit penalty.
  - The question is: does Historization add value over standard methods
    on domains with uncertainty and traps?

Usage:
  python -m e0_controller.benchmark_sota              # run all
  python -m e0_controller.benchmark_sota --json       # machine-readable
"""

from __future__ import annotations

import json
import math
import random
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Set, Tuple

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller
from e0_controller.benchmark_domain_invariance import (
    DomainSpec,
    ALL_DOMAINS,
    build_all_domains,
)


# ══════════════════════════════════════════════
# Result types
# ══════════════════════════════════════════════

@dataclass
class MethodResult:
    """Result of one method on one domain."""
    method: str
    goal_reached: bool
    steps: int
    unique_states: int
    revisits: int
    wall_time_ms: float


@dataclass
class DomainComparison:
    """All methods compared on one domain."""
    domain: str
    topology: str
    nodes: int
    results: Dict[str, MethodResult]


# ══════════════════════════════════════════════
# Shared utilities
# ══════════════════════════════════════════════

def _get_neighbors(L: Landscape, state: str) -> List[Tuple[str, float]]:
    """Return [(target, S_eff)] for all edges from state."""
    return [
        (e.target, L._delta[e] * L._R0[e])
        for e in L.edges if e.source == state
    ]


# ══════════════════════════════════════════════
# Method 1: E₀ (full controller)
# ══════════════════════════════════════════════

def run_e0(spec: DomainSpec, max_cycles: int) -> MethodResult:
    """E₀ controller with default parameters."""
    ctrl = E0Controller(
        spec.landscape, spec.execute_fn,
        alpha=2.0, recent_k=3,
    )
    t0 = time.perf_counter()
    trace = ctrl.run(spec.start, max_cycles=max_cycles, goal=spec.goal)
    elapsed = (time.perf_counter() - t0) * 1000

    m = trace.metrics()
    return MethodResult(
        method="E0",
        goal_reached=spec.goal in trace.path,
        steps=len(trace.steps),
        unique_states=int(m["unique_states"]),
        revisits=int(m["revisit_count"]),
        wall_time_ms=round(elapsed, 2),
    )


# ══════════════════════════════════════════════
# Method 2: Memoryless Greedy
# ══════════════════════════════════════════════

def run_greedy(spec: DomainSpec, max_cycles: int) -> MethodResult:
    """Argmin S_eff, always advance, no memory."""
    L = spec.landscape
    current = spec.start
    visited: Dict[str, int] = {current: 1}
    steps = 0

    t0 = time.perf_counter()
    while steps < max_cycles and current != spec.goal:
        neighbors = _get_neighbors(L, current)
        if not neighbors:
            break
        neighbors.sort(key=lambda x: x[1])
        target = neighbors[0][0]
        spec.execute_fn(current, target)
        steps += 1
        current = target
        visited[current] = visited.get(current, 0) + 1
    elapsed = (time.perf_counter() - t0) * 1000

    return MethodResult(
        method="GREEDY",
        goal_reached=current == spec.goal,
        steps=steps,
        unique_states=len(visited),
        revisits=sum(v - 1 for v in visited.values() if v > 1),
        wall_time_ms=round(elapsed, 2),
    )


# ══════════════════════════════════════════════
# Method 3: ε-Greedy (exploration)
# ══════════════════════════════════════════════

def run_epsilon_greedy(spec: DomainSpec, max_cycles: int,
                       epsilon: float = 0.2, seed: int = 42) -> MethodResult:
    """ε-greedy: explore random (ε) or exploit argmin S_eff (1-ε)."""
    rng = random.Random(seed)
    L = spec.landscape
    current = spec.start
    visited: Dict[str, int] = {current: 1}
    steps = 0

    t0 = time.perf_counter()
    while steps < max_cycles and current != spec.goal:
        neighbors = _get_neighbors(L, current)
        if not neighbors:
            break
        if rng.random() < epsilon:
            target = rng.choice(neighbors)[0]
        else:
            neighbors.sort(key=lambda x: x[1])
            target = neighbors[0][0]
        spec.execute_fn(current, target)
        steps += 1
        current = target
        visited[current] = visited.get(current, 0) + 1
    elapsed = (time.perf_counter() - t0) * 1000

    return MethodResult(
        method="EPS_GREEDY",
        goal_reached=current == spec.goal,
        steps=steps,
        unique_states=len(visited),
        revisits=sum(v - 1 for v in visited.values() if v > 1),
        wall_time_ms=round(elapsed, 2),
    )


# ══════════════════════════════════════════════
# Method 4: Tabular Q-Learning
# ══════════════════════════════════════════════

def run_q_learning(spec: DomainSpec, max_cycles: int,
                   lr: float = 0.3, gamma: float = 0.9,
                   eps_start: float = 0.2, eps_end: float = 0.05,
                   seed: int = 42) -> MethodResult:
    """Tabular Q-learning over (state, target) pairs.

    Reward: +10 for reaching goal, -1 for FAILURE outcome, 0 otherwise.
    ε decays linearly from eps_start to eps_end over max_cycles.
    """
    rng = random.Random(seed)
    L = spec.landscape
    Q: Dict[Tuple[str, str], float] = defaultdict(float)
    current = spec.start
    visited: Dict[str, int] = {current: 1}
    steps = 0

    t0 = time.perf_counter()
    while steps < max_cycles and current != spec.goal:
        neighbors = _get_neighbors(L, current)
        if not neighbors:
            break

        # ε-greedy with decay
        eps = eps_start - (eps_start - eps_end) * min(steps / max(max_cycles - 1, 1), 1.0)
        if rng.random() < eps:
            target = rng.choice(neighbors)[0]
        else:
            target = max(neighbors, key=lambda x: Q[(current, x[0])])[0]

        outcome = spec.execute_fn(current, target)
        steps += 1

        # Reward signal
        if target == spec.goal:
            reward = 10.0
        elif outcome == Outcome.FAILURE:
            reward = -1.0
        else:
            reward = 0.0

        # Q-update: Q(s,a) ← Q(s,a) + α[r + γ·max_a'Q(s',a') - Q(s,a)]
        next_neighbors = _get_neighbors(L, target)
        if next_neighbors:
            max_q_next = max(Q[(target, n[0])] for n in next_neighbors)
        else:
            max_q_next = 0.0

        Q[(current, target)] += lr * (
            reward + gamma * max_q_next - Q[(current, target)]
        )

        current = target
        visited[current] = visited.get(current, 0) + 1
    elapsed = (time.perf_counter() - t0) * 1000

    return MethodResult(
        method="Q_LEARN",
        goal_reached=current == spec.goal,
        steps=steps,
        unique_states=len(visited),
        revisits=sum(v - 1 for v in visited.values() if v > 1),
        wall_time_ms=round(elapsed, 2),
    )


# ══════════════════════════════════════════════
# Method 5: Random Walk
# ══════════════════════════════════════════════

def run_random(spec: DomainSpec, max_cycles: int,
               seed: int = 42) -> MethodResult:
    """Uniform random neighbor selection."""
    rng = random.Random(seed)
    L = spec.landscape
    current = spec.start
    visited: Dict[str, int] = {current: 1}
    steps = 0

    t0 = time.perf_counter()
    while steps < max_cycles and current != spec.goal:
        neighbors = _get_neighbors(L, current)
        if not neighbors:
            break
        target = rng.choice(neighbors)[0]
        spec.execute_fn(current, target)
        steps += 1
        current = target
        visited[current] = visited.get(current, 0) + 1
    elapsed = (time.perf_counter() - t0) * 1000

    return MethodResult(
        method="RANDOM",
        goal_reached=current == spec.goal,
        steps=steps,
        unique_states=len(visited),
        revisits=sum(v - 1 for v in visited.values() if v > 1),
        wall_time_ms=round(elapsed, 2),
    )


# ══════════════════════════════════════════════
# Multi-run averaging (for stochastic methods)
# ══════════════════════════════════════════════

def _avg_results(results: List[MethodResult]) -> MethodResult:
    """Average over multiple runs of the same method."""
    n = len(results)
    return MethodResult(
        method=results[0].method,
        goal_reached=sum(r.goal_reached for r in results) > n / 2,
        steps=round(sum(r.steps for r in results) / n),
        unique_states=round(sum(r.unique_states for r in results) / n),
        revisits=round(sum(r.revisits for r in results) / n),
        wall_time_ms=round(sum(r.wall_time_ms for r in results) / n, 2),
    )


def _goal_rate(results: List[MethodResult]) -> float:
    """Fraction of runs that reached goal."""
    return sum(r.goal_reached for r in results) / len(results)


# ══════════════════════════════════════════════
# Benchmark Runner
# ══════════════════════════════════════════════

METHODS = ["E0", "GREEDY", "EPS_GREEDY", "Q_LEARN", "RANDOM"]
N_STOCHASTIC_RUNS = 10  # repeat stochastic methods for robustness


def run_comparison(spec: DomainSpec, max_cycles: int = 50) -> DomainComparison:
    """Run all 5 methods on one domain.

    Deterministic methods (E₀, Greedy) run once.
    Stochastic methods (ε-greedy, Q-learning, Random) run N times
    with different seeds and report majority vote + averaged metrics.
    """
    results: Dict[str, MethodResult] = {}

    # Deterministic
    results["E0"] = run_e0(spec, max_cycles)
    results["GREEDY"] = run_greedy(spec, max_cycles)

    # Stochastic — multi-run
    for method_name, runner in [
        ("EPS_GREEDY", run_epsilon_greedy),
        ("Q_LEARN", run_q_learning),
        ("RANDOM", run_random),
    ]:
        runs = [runner(spec, max_cycles, seed=seed)
                for seed in range(N_STOCHASTIC_RUNS)]
        results[method_name] = _avg_results(runs)
        results[method_name + "_goal_rate"] = MethodResult(
            method=method_name,
            goal_reached=True,
            steps=0,
            unique_states=0,
            revisits=0,
            wall_time_ms=_goal_rate(runs),  # abuse field for rate
        )

    return DomainComparison(
        domain=spec.name,
        topology=spec.topology_class,
        nodes=spec.node_count,
        results=results,
    )


def run_benchmark(max_cycles: int = 50) -> List[DomainComparison]:
    """Run all 10 domains × 5 methods."""
    domains = build_all_domains()
    return [run_comparison(spec, max_cycles) for spec in domains]


# ══════════════════════════════════════════════
# Output
# ══════════════════════════════════════════════

def _goal_sym(r: MethodResult) -> str:
    return "✓" if r.goal_reached else "✗"


def print_results(comparisons: List[DomainComparison]) -> None:
    """Pretty-print comparison table."""
    print()
    print("=" * 100)
    print("  SOTA Comparison — 10 Domains × 5 Methods")
    print("  (stochastic methods: avg over 10 seeds)")
    print("=" * 100)

    header = (
        f"{'Domain':<24} "
        f"{'E₀':>8} {'Grdy':>8} {'εGrdy':>8} "
        f"{'Q-Lrn':>8} {'Rand':>8}"
    )
    print(header)
    print("-" * 100)

    e0_wins = 0
    total = 0

    for c in comparisons:
        total += 1
        cells = []
        e0_steps = c.results["E0"].steps
        e0_reached = c.results["E0"].goal_reached

        for m in METHODS:
            r = c.results[m]
            sym = _goal_sym(r)
            cells.append(f"{sym}{r.steps:>3}")

        if e0_reached:
            # Check if E₀ is best or tied
            others_reach = [
                c.results[m].goal_reached for m in METHODS if m != "E0"
            ]
            others_steps = [
                c.results[m].steps for m in METHODS
                if m != "E0" and c.results[m].goal_reached
            ]
            if not others_steps or e0_steps <= min(others_steps):
                e0_wins += 1

        print(f"{c.domain:<24} {'  '.join(cells)}")

    print("-" * 100)

    # Summary
    print()
    print("Goal-reach summary:")
    for m in METHODS:
        reached = sum(1 for c in comparisons if c.results[m].goal_reached)
        label = {"E0": "E₀", "GREEDY": "Greedy", "EPS_GREEDY": "ε-Greedy",
                 "Q_LEARN": "Q-Learn", "RANDOM": "Random"}[m]
        print(f"  {label:<12} {reached:>2}/10 domains")

    print(f"\n  E₀ best-or-tied: {e0_wins}/10 domains")

    # Per-method step comparison (only where goal reached by all)
    all_reach = [
        c for c in comparisons
        if all(c.results[m].goal_reached for m in METHODS)
    ]
    if all_reach:
        print(f"\n  On {len(all_reach)} domains where ALL methods reach goal:")
        for m in METHODS:
            total_steps = sum(c.results[m].steps for c in all_reach)
            label = {"E0": "E₀", "GREEDY": "Greedy", "EPS_GREEDY": "ε-Greedy",
                     "Q_LEARN": "Q-Learn", "RANDOM": "Random"}[m]
            print(f"    {label:<12} total steps: {total_steps}")
    print()


def results_to_dict(comparisons: List[DomainComparison]) -> Dict:
    """Serialize for JSON output."""
    return {
        "benchmark": "sota_comparison_v1",
        "domains": len(comparisons),
        "methods": METHODS,
        "stochastic_runs": N_STOCHASTIC_RUNS,
        "comparisons": [
            {
                "domain": c.domain,
                "topology": c.topology,
                "nodes": c.nodes,
                "results": {
                    m: {
                        "goal_reached": c.results[m].goal_reached,
                        "steps": c.results[m].steps,
                        "unique_states": c.results[m].unique_states,
                        "revisits": c.results[m].revisits,
                    }
                    for m in METHODS
                },
            }
            for c in comparisons
        ],
    }


# ══════════════════════════════════════════════
# Main entry
# ══════════════════════════════════════════════

if __name__ == "__main__":
    json_mode = "--json" in sys.argv
    comparisons = run_benchmark()
    if json_mode:
        print(json.dumps(results_to_dict(comparisons), indent=2))
    else:
        print_results(comparisons)
