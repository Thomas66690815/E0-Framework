"""
Falsification Benchmark (Phase C — S4)
=======================================
Constructs domains designed to expose E₀'s structural limits.
Each target tests a specific falsifiable prediction from the
Structural Contradictions analysis (docs/E0_STRUCTURAL_CONTRADICTIONS_v1.md §6.1).

Targets:
  F1 — Exploration Depth Limit (SC-5)
        Linear gauntlet of high-tension edges. No side branches.
        Greedy ALWAYS reaches goal (delta gradient favors forward).
        E₀ must push through rising R_eff from repeated failures.
        Falsifiable: at what depth does E₀ fail to reach the goal?

  F2 — Ossification Under Non-Stationarity (SC-6 / SC-8)
        Phase 1: warm up on path A (500 steps). Path A becomes low-R_eff.
        Phase 2: path A blocked (execute_fn returns FAILURE). Path B opens.
        Falsifiable: does E₀ adapt to the environmental change?
        Compares: with vs. without structural decay.

  F3 — Dense Branching Interference (SC-11)
        Tree of branching factor b, depth d. Single goal leaf.
        Path enumeration grows as O(b^d). Tests whether E₀'s
        advantage degrades as branching factor increases.
        Falsifiable: at what branching factor does E₀ lose advantage?

  F4 — History-Dependent Fork (SC-1 / SC-3)
        State G has two exits. execute_fn returns SUCCESS on G→WIN only
        if the traversal immediately before G was a specific "key" edge.
        Memoryless greedy cannot learn the contingency; E₀'s historization
        should learn which entry path succeeds.
        Falsifiable: does E₀ learn the history-dependent rule?

Usage:
  py -3 -m e0_controller.benchmark_falsification          # run all
  py -3 -m e0_controller.benchmark_falsification --target F1  # single
  py -3 -m e0_controller.benchmark_falsification --json    # machine output
"""

from __future__ import annotations

import copy
import math
import random as rng
import sys
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller


# ══════════════════════════════════════════════
# Data types (same pattern as benchmark_scaling)
# ══════════════════════════════════════════════

@dataclass
class FalsificationDomain:
    """One falsification domain."""
    name: str
    target: str           # F1, F2, F3, F4
    landscape: Landscape
    start: str
    goal: str
    execute_fn: Callable[[str, str], Outcome]
    node_count: int
    edge_count: int
    description: str


@dataclass
class FalsificationResult:
    """Result of one method on one falsification domain."""
    method: str
    goal_reached: bool
    steps: int
    wall_time_ms: float
    unique_states: int
    revisits: int
    extra: Dict = field(default_factory=dict)


# ══════════════════════════════════════════════
# F1 — Exploration Depth Limit (SC-5)
# ══════════════════════════════════════════════

def build_exploration_gauntlet(depth: int) -> FalsificationDomain:
    """Linear chain with SUCCESS-returning loop distractors at every node.

    Topology at each node N_i:
        N_i → N_{i+1}  (forward, delta=0.15, higher tension)
        N_i → D_i       (distractor, delta=0.08, lower tension)
        D_i → N_i       (return, only exit from D_i)

    All edges succeed. Greedy always picks distractor (S_eff = 0.04 vs
    forward S_eff = 0.075). Without memory, greedy enters D_i, returns,
    picks D_i again → infinite loop.

    E₀ with revisit penalty (α=2.0, recent_k=3):
    After visiting D_i, it's in recent. Penalized S_eff(D_i) = 0.04 × 3 = 0.12.
    Forward S_eff = 0.075. Now forward wins (0.075 < 0.12). E₀ learns to push
    through. Cost: ~4 extra steps per distractor node (visit, return, visit,
    return, then forward).

    Falsifiable claim: E₀ reaches GOAL through distractor chain.
    Boundary question: at what depth does step cost exceed budget?
    """
    L = Landscape()

    prev = "S"
    for i in range(depth):
        node = f"N{i}"
        dist = f"D{i}"
        # Forward edge: higher tension but leads to progress
        L.add_edge(prev, node, delta=0.15, resistance=0.5)
        L.add_edge(node, prev, delta=0.9, resistance=0.5)
        # Distractor: lower tension, dead-end loop
        L.add_edge(node, dist, delta=0.08, resistance=0.5)
        L.add_edge(dist, node, delta=0.5, resistance=0.5)
        prev = node
    L.add_edge(prev, "GOAL", delta=0.05, resistance=0.5)
    L.add_edge("GOAL", prev, delta=0.9, resistance=0.5)

    return FalsificationDomain(
        name=f"GAUNTLET_d{depth}",
        target="F1",
        landscape=L,
        start="S",
        goal="GOAL",
        execute_fn=lambda s, t: Outcome.SUCCESS,
        node_count=depth * 2 + 2,
        edge_count=(depth + 1) * 2 + depth * 2,
        description=f"Linear chain depth={depth} with loop distractors",
    )


# ══════════════════════════════════════════════
# F2 — Ossification Under Non-Stationarity (SC-6/SC-8)
# ══════════════════════════════════════════════

class NonStationaryExecutor:
    """Execute function that changes behavior after N steps.

    Phase 1 (steps 0..switch_at-1): path_a edges succeed, path_b edges fail.
    Phase 2 (steps switch_at..):    path_a edges FAIL, path_b edges succeed.
    """

    def __init__(self, path_a_edges: Set[Tuple[str, str]],
                 path_b_edges: Set[Tuple[str, str]],
                 switch_at: int):
        self._path_a = path_a_edges
        self._path_b = path_b_edges
        self._switch_at = switch_at
        self.step_count = 0
        self.switch_happened = False

    def __call__(self, source: str, target: str) -> Outcome:
        self.step_count += 1
        key = (source, target)
        if self.step_count <= self._switch_at:
            # Phase 1: path A works
            if key in self._path_a:
                return Outcome.SUCCESS
            if key in self._path_b:
                return Outcome.FAILURE
            return Outcome.SUCCESS
        else:
            # Phase 2: path A blocked, path B works
            self.switch_happened = True
            if key in self._path_a:
                return Outcome.FAILURE
            if key in self._path_b:
                return Outcome.SUCCESS
            return Outcome.SUCCESS

    def reset(self):
        self.step_count = 0
        self.switch_happened = False


def build_ossification_domain(switch_at: int = 200) -> FalsificationDomain:
    """Two parallel paths from S to GOAL. Path A works first, then fails.

    Path A: S → A1 → A2 → A3 → GOAL  (delta=0.2, low tension)
    Path B: S → B1 → B2 → B3 → GOAL  (delta=0.3, slightly higher)

    Phase 1 (steps 0..switch_at): Path A succeeds, Path B fails.
    After switch_at steps: Path A FAILS, Path B succeeds.

    E₀ must:
    1. Learn path A in phase 1 (easy — lower delta)
    2. Detect path A failures in phase 2
    3. Switch to path B despite accumulated SUCCESS history on path A

    The ossification risk: after many steps on path A, trace quality
    q(A_edges) ≈ 1.0, inertia_factor → 1.0. The system might keep
    trying path A because historization "believes" it's reliable.
    """
    L = Landscape()

    # Path A (initially working)
    path_a_edges = set()
    for src, tgt in [("S", "A1"), ("A1", "A2"), ("A2", "A3"), ("A3", "GOAL")]:
        L.add_edge(src, tgt, delta=0.2, resistance=0.5)
        L.add_edge(tgt, src, delta=0.8, resistance=0.5)
        path_a_edges.add((src, tgt))

    # Path B (initially failing, later working)
    path_b_edges = set()
    for src, tgt in [("S", "B1"), ("B1", "B2"), ("B2", "B3"), ("B3", "GOAL")]:
        L.add_edge(src, tgt, delta=0.3, resistance=0.5)
        L.add_edge(tgt, src, delta=0.7, resistance=0.5)
        path_b_edges.add((src, tgt))

    executor = NonStationaryExecutor(path_a_edges, path_b_edges, switch_at)

    return FalsificationDomain(
        name=f"OSSIFICATION_switch{switch_at}",
        target="F2",
        landscape=L,
        start="S",
        goal="GOAL",
        execute_fn=executor,
        node_count=8,
        edge_count=16,
        description=f"Two parallel paths, path A blocked after step {switch_at}",
    )


def run_f2_multi_episode(switch_at: int, warmup_episodes: int,
                         test_episodes: int,
                         max_cycles: int = 50) -> Dict:
    """Run F2 with multi-episode design.

    Phase 1: warmup_episodes runs on the landscape (PATH A works).
    Phase 2: environment switches, run test_episodes more.
    Measures whether E₀ adapts to the change.
    """
    domain = build_ossification_domain(switch_at=999999)  # no switch yet
    executor = domain.execute_fn

    ctrl = E0Controller(
        domain.landscape,
        domain.execute_fn,
        alpha=2.0,
        recent_k=3,
    )

    # Phase 1: warm up — accumulate history on path A
    phase1_goals = 0
    for _ in range(warmup_episodes):
        trace = ctrl.run("S", max_cycles=max_cycles, goal="GOAL")
        if "GOAL" in trace.path:
            phase1_goals += 1

    # Capture historization state after warmup
    hist = domain.landscape.historization
    warmup_path_a_quality = []
    for src, tgt in [("S", "A1"), ("A1", "A2"), ("A2", "A3"), ("A3", "GOAL")]:
        e = Edge(src, tgt)
        warmup_path_a_quality.append(hist.trace_quality(e))
    mean_a_quality = sum(warmup_path_a_quality) / len(warmup_path_a_quality)

    # Phase 2: switch environment — path A now fails
    executor._switch_at = 0  # switch immediately
    executor.switch_happened = True

    phase2_goals = 0
    for _ in range(test_episodes):
        trace = ctrl.run("S", max_cycles=max_cycles, goal="GOAL")
        if "GOAL" in trace.path:
            phase2_goals += 1

    return {
        "warmup_episodes": warmup_episodes,
        "test_episodes": test_episodes,
        "phase1_goal_rate": phase1_goals / warmup_episodes,
        "phase2_goal_rate": phase2_goals / test_episodes,
        "adapted": phase2_goals > 0,
        "mean_path_a_quality_after_warmup": round(mean_a_quality, 4),
    }


# ══════════════════════════════════════════════
# F3 — Dense Branching Interference (SC-11)
# ══════════════════════════════════════════════

def build_dense_tree(branching: int, depth: int, seed: int = 42) -> FalsificationDomain:
    """Complete tree with branching factor b and depth d.

    Single goal leaf (randomly chosen). All other leaves are dead-ends
    that return FAILURE when traversed outward.

    N = (b^(d+1) - 1) / (b - 1) for b > 1
    At b=3, d=4: N = 121 nodes
    At b=5, d=3: N = 156 nodes
    At b=10, d=2: N = 111 nodes

    Greedy: follows lowest delta, typically wrong (1/b chance per level).
    E₀: learns from failures, should converge on correct branch.
    Question: does E₀'s advantage hold as branching factor increases?
    """
    gen = rng.Random(seed)
    L = Landscape()

    # Build tree level by level
    levels: List[List[str]] = [["ROOT"]]
    for d_level in range(depth):
        next_level = []
        for parent in levels[d_level]:
            for b_idx in range(branching):
                child = f"L{d_level + 1}_B{b_idx}_{parent}"
                # Delta decreases slightly with depth (gradient toward leaves)
                delta = 0.5 - 0.1 * (d_level / depth)
                L.add_edge(parent, child, delta=round(delta, 4), resistance=0.5)
                L.add_edge(child, parent, delta=round(1.0 - delta, 4), resistance=0.5)
                next_level.append(child)
        levels.append(next_level)

    leaves = levels[-1]
    goal_leaf = gen.choice(leaves)

    # Dead-end detection: leaves that are NOT the goal return FAILURE
    # when you try to move forward (no children). The execute_fn
    # penalizes entering dead-end leaves by making the edge TO them fail.
    dead_leaves = set(leaves) - {goal_leaf}

    def execute_fn(source: str, target: str) -> Outcome:
        if target in dead_leaves:
            return Outcome.FAILURE
        return Outcome.SUCCESS

    n_nodes = sum(len(lev) for lev in levels)
    n_edges = sum(1 for _ in L.edges)

    return FalsificationDomain(
        name=f"DENSE_TREE_b{branching}_d{depth}",
        target="F3",
        landscape=L,
        start="ROOT",
        goal=goal_leaf,
        execute_fn=execute_fn,
        node_count=n_nodes,
        edge_count=n_edges,
        description=f"Complete tree b={branching} d={depth}, single goal leaf, N={n_nodes}",
    )


# ══════════════════════════════════════════════
# F4 — History-Dependent Fork (SC-1 / SC-3)
# ══════════════════════════════════════════════

class HistoryDependentExecutor:
    """Execute function where outcome at GATE→TRY depends on entry path.

    GATE→TRY succeeds ONLY if the previous edge was KEY_EDGE.
    All other edges always succeed.

    Used to test SC-1 (value on edges, not states) and SC-3 (non-Markov).
    """

    def __init__(self, key_edge: Tuple[str, str],
                 guarded_source: str = "GATE", guarded_target: str = "TRY"):
        self._key_edge = key_edge
        self._guarded = (guarded_source, guarded_target)
        self._last_edge: Optional[Tuple[str, str]] = None
        self.try_attempts = 0
        self.try_successes = 0

    def __call__(self, source: str, target: str) -> Outcome:
        if (source, target) == self._guarded:
            self.try_attempts += 1
            if self._last_edge == self._key_edge:
                self.try_successes += 1
                result = Outcome.SUCCESS
            else:
                result = Outcome.FAILURE
            self._last_edge = (source, target)
            return result
        self._last_edge = (source, target)
        return Outcome.SUCCESS

    def reset(self):
        self._last_edge = None
        self.try_attempts = 0
        self.try_successes = 0


def build_history_fork() -> FalsificationDomain:
    """Loop domain testing non-Markov path-dependent outcomes.

    Topology (loop, no terminal goal):
        S ──→ KEY ──→ GATE ──→ TRY ──→ S
        S ──→ ALT ──→ GATE ──→ TRY ──→ S
                              └──→ S  (direct return)

    GATE→TRY succeeds ONLY if prior edge was KEY→GATE.
    GATE→TRY fails    if prior edge was ALT→GATE.

    KEY path is costly (S→KEY delta=0.3), ALT path is cheap (delta=0.1).
    Both methods naturally pick ALT → all TRY attempts fail.

    STRUCTURAL LIMIT: E₀'s historization is edge-local. S→ALT always
    succeeds (U++ regardless of later GATE→TRY outcome), so nothing
    penalizes S→ALT at the decision point. E₀ may learn to AVOID TRY
    (failure inscription), but cannot learn to switch from ALT to KEY.

    This is a confirmed falsification for SC-1 and SC-3: the current
    architecture cannot learn non-Markov path dependencies.
    """
    L = Landscape()

    # Two paths from S to GATE — ALT is cheaper (lower S_eff)
    L.add_edge("S", "KEY", delta=0.3, resistance=0.5)    # costly, correct
    L.add_edge("S", "ALT", delta=0.1, resistance=0.5)    # cheap, wrong
    L.add_edge("KEY", "GATE", delta=0.15, resistance=0.5)
    L.add_edge("ALT", "GATE", delta=0.15, resistance=0.5)

    # History-dependent attempt
    L.add_edge("GATE", "TRY", delta=0.1, resistance=0.5)

    # Return from TRY (loop back for next episode)
    L.add_edge("TRY", "S", delta=0.2, resistance=0.5)

    # Skip TRY — direct retreat from GATE
    L.add_edge("GATE", "S", delta=0.5, resistance=0.5)

    executor = HistoryDependentExecutor(key_edge=("KEY", "GATE"))

    return FalsificationDomain(
        name="HISTORY_FORK",
        target="F4",
        landscape=L,
        start="S",
        goal="_UNREACHABLE_",  # loop domain — no terminal goal
        execute_fn=executor,
        node_count=5,
        edge_count=7,
        description="GATE→TRY succeeds only via KEY path (non-Markov)",
    )


# ══════════════════════════════════════════════
# Runners (same pattern as benchmark_scaling)
# ══════════════════════════════════════════════

def run_e0(domain: FalsificationDomain, max_cycles: int) -> FalsificationResult:
    """E₀ controller with full historization."""
    ctrl = E0Controller(
        domain.landscape,
        domain.execute_fn,
        alpha=2.0,
        recent_k=3,
    )

    t0 = time.perf_counter()
    trace = ctrl.run(domain.start, max_cycles=max_cycles, goal=domain.goal)
    elapsed = (time.perf_counter() - t0) * 1000

    metrics = trace.metrics()
    goal_reached = domain.goal in trace.path

    return FalsificationResult(
        method="E0",
        goal_reached=goal_reached,
        steps=len(trace.steps),
        wall_time_ms=round(elapsed, 1),
        unique_states=int(metrics["unique_states"]),
        revisits=int(metrics["revisit_count"]),
    )


def run_greedy(domain: FalsificationDomain, max_cycles: int) -> FalsificationResult:
    """Memoryless greedy — argmin Δ·R₀, always advance (same as E₀).

    Same movement rule as E₀ (always advance to target regardless of
    outcome). The ONLY difference: greedy has no historization, no
    revisit penalty, no memory. This isolates the effect of memory.
    """
    L = domain.landscape
    execute_fn = domain.execute_fn
    current = domain.start
    path = [current]
    visited_count: Dict[str, int] = {current: 1}
    steps = 0

    t0 = time.perf_counter()
    while steps < max_cycles and current != domain.goal:
        neighbors = sorted(
            [(e.target, L._delta[e] * L._R0[e])
             for e in L.edges if e.source == current],
            key=lambda x: x[1],
        )
        if not neighbors:
            break
        target = neighbors[0][0]  # always pick best, always advance
        execute_fn(current, target)  # execute but ignore outcome
        steps += 1
        current = target
        path.append(current)
        visited_count[current] = visited_count.get(current, 0) + 1
    elapsed = (time.perf_counter() - t0) * 1000

    revisits = sum(v - 1 for v in visited_count.values() if v > 1)
    return FalsificationResult(
        method="GREEDY",
        goal_reached=current == domain.goal,
        steps=steps,
        wall_time_ms=round(elapsed, 1),
        unique_states=len(visited_count),
        revisits=revisits,
    )


# ══════════════════════════════════════════════
# Parametric sweeps
# ══════════════════════════════════════════════

def sweep_f1(depths: Optional[List[int]] = None) -> List[Dict]:
    """Sweep exploration gauntlet at increasing depths."""
    if depths is None:
        depths = [5, 10, 20, 50, 100, 200, 500]
    results = []
    for d in depths:
        domain = build_exploration_gauntlet(d)
        max_steps = d * 4  # generous budget
        e0 = run_e0(domain, max_steps)
        greedy = run_greedy(domain, max_steps)
        results.append({
            "depth": d,
            "nodes": domain.node_count,
            "e0_reached": e0.goal_reached,
            "e0_steps": e0.steps,
            "greedy_reached": greedy.goal_reached,
            "greedy_steps": greedy.steps,
        })
        status = "✓" if e0.goal_reached else "✗"
        print(f"  F1 depth={d:4d}: E₀ {status} ({e0.steps} steps), "
              f"Greedy {'✓' if greedy.goal_reached else '✗'} ({greedy.steps} steps)")
    return results


def sweep_f2(warmup_configs: Optional[List[int]] = None,
             test_episodes: int = 10) -> List[Dict]:
    """Sweep ossification with different warm-up lengths."""
    if warmup_configs is None:
        warmup_configs = [5, 20, 50, 100, 200]
    results = []
    for n_warmup in warmup_configs:
        result = run_f2_multi_episode(
            switch_at=999999,
            warmup_episodes=n_warmup,
            test_episodes=test_episodes,
        )
        results.append(result)
        status = "ADAPTED" if result["adapted"] else "OSSIFIED"
        print(f"  F2 warmup={n_warmup:4d}: {status} "
              f"(phase1={result['phase1_goal_rate']:.0%}, "
              f"phase2={result['phase2_goal_rate']:.0%}, "
              f"q_A={result['mean_path_a_quality_after_warmup']:.3f})")
    return results


def sweep_f3(configs: Optional[List[Tuple[int, int]]] = None) -> List[Dict]:
    """Sweep dense tree at increasing branching factors."""
    if configs is None:
        configs = [(2, 4), (3, 3), (5, 3), (8, 2), (10, 2), (15, 2), (20, 2)]
    results = []
    for b, d in configs:
        domain = build_dense_tree(b, d)
        max_steps = domain.node_count * 6  # generous for deep backtracking
        e0 = run_e0(domain, max_steps)
        greedy = run_greedy(domain, max_steps)
        results.append({
            "branching": b,
            "depth": d,
            "nodes": domain.node_count,
            "e0_reached": e0.goal_reached,
            "e0_steps": e0.steps,
            "e0_time_ms": e0.wall_time_ms,
            "greedy_reached": greedy.goal_reached,
            "greedy_steps": greedy.steps,
        })
        e0s = "✓" if e0.goal_reached else "✗"
        gs = "✓" if greedy.goal_reached else "✗"
        print(f"  F3 b={b:2d} d={d}: N={domain.node_count:4d}  "
              f"E₀ {e0s} ({e0.steps}/{max_steps} steps, {e0.wall_time_ms:.0f}ms)  "
              f"Greedy {gs} ({greedy.steps} steps)")
    return results


def sweep_f4(max_cycles: int = 200) -> Dict:
    """Run history-dependent loop domain — count TRY success rates.

    Since the goal is unreachable, both methods loop for max_cycles.
    We measure how many GATE→TRY executions succeed (correct path).

    Also runs an "oracle" that always picks KEY to prove the path matters.
    """
    # --- E₀ run ---
    domain_e0 = build_history_fork()
    ctrl = E0Controller(domain_e0.landscape, domain_e0.execute_fn,
                        alpha=2.0, recent_k=3)
    trace_e0 = ctrl.run(domain_e0.start, max_cycles=max_cycles,
                        goal="_UNREACHABLE_")
    e0_exec = domain_e0.execute_fn
    e0_attempts = e0_exec.try_attempts
    e0_successes = e0_exec.try_successes
    e0_rate = e0_successes / e0_attempts if e0_attempts else 0.0

    # --- Greedy run (memoryless, always argmin S_eff) ---
    domain_gr = build_history_fork()
    L = domain_gr.landscape
    current = domain_gr.start
    for _ in range(max_cycles):
        neighbors = sorted(
            [(e.target, L._delta[e] * L._R0[e])
             for e in L.edges if e.source == current],
            key=lambda x: x[1],
        )
        if not neighbors:
            break
        target = neighbors[0][0]
        domain_gr.execute_fn(current, target)
        current = target
    gr_exec = domain_gr.execute_fn
    gr_attempts = gr_exec.try_attempts
    gr_successes = gr_exec.try_successes
    gr_rate = gr_successes / gr_attempts if gr_attempts else 0.0

    # --- Oracle run (always picks KEY at S, TRY at GATE) ---
    domain_or = build_history_fork()
    current = domain_or.start
    oracle_path = {"S": "KEY", "KEY": "GATE", "GATE": "TRY",
                   "TRY": "S", "ALT": "GATE"}
    for _ in range(max_cycles):
        target = oracle_path.get(current)
        if target is None:
            break
        domain_or.execute_fn(current, target)
        current = target
    or_exec = domain_or.execute_fn
    or_attempts = or_exec.try_attempts
    or_successes = or_exec.try_successes
    or_rate = or_successes / or_attempts if or_attempts else 0.0

    result = {
        "max_cycles": max_cycles,
        "e0_attempts": e0_attempts, "e0_successes": e0_successes,
        "e0_rate": e0_rate,
        "greedy_attempts": gr_attempts, "greedy_successes": gr_successes,
        "greedy_rate": gr_rate,
        "oracle_attempts": or_attempts, "oracle_successes": or_successes,
        "oracle_rate": or_rate,
    }

    print(f"  F4 ({max_cycles} cycles):")
    print(f"    Oracle (KEY forced):  {or_successes}/{or_attempts} TRY successes "
          f"({or_rate:.0%})")
    print(f"    E₀ (historization):   {e0_successes}/{e0_attempts} TRY successes "
          f"({e0_rate:.0%})")
    print(f"    Greedy (memoryless):  {gr_successes}/{gr_attempts} TRY successes "
          f"({gr_rate:.0%})")

    # Document structural limit
    if e0_rate == 0.0 and or_rate > 0.0:
        print("  → CONFIRMED LIMIT: E₀ cannot learn non-Markov "
              "path dependencies (SC-1/SC-3)")
    elif e0_rate > gr_rate:
        print(f"  → UNEXPECTED: E₀ shows path learning (rate={e0_rate:.0%})")

    return result


# ══════════════════════════════════════════════
# Main entry
# ══════════════════════════════════════════════

def run_all() -> Dict:
    """Run all falsification targets."""
    all_results = {}

    print("=" * 60)
    print("F1 — Exploration Depth Limit (SC-5)")
    print("=" * 60)
    all_results["F1"] = sweep_f1()

    print()
    print("=" * 60)
    print("F2 — Ossification Under Non-Stationarity (SC-6/SC-8)")
    print("=" * 60)
    all_results["F2"] = sweep_f2()

    print()
    print("=" * 60)
    print("F3 — Dense Branching Interference (SC-11)")
    print("=" * 60)
    all_results["F3"] = sweep_f3()

    print()
    print("=" * 60)
    print("F4 — History-Dependent Fork (SC-1/SC-3)")
    print("=" * 60)
    all_results["F4"] = sweep_f4()

    return all_results


if __name__ == "__main__":
    import json as _json

    target = None
    json_mode = False
    for arg in sys.argv[1:]:
        if arg == "--json":
            json_mode = True
        elif arg.startswith("--target"):
            target = arg.split("=")[1] if "=" in arg else sys.argv[sys.argv.index(arg) + 1]

    if target:
        results = {}
        if target == "F1":
            print("F1 — Exploration Depth Limit (SC-5)")
            results["F1"] = sweep_f1()
        elif target == "F2":
            print("F2 — Ossification Under Non-Stationarity (SC-6/SC-8)")
            results["F2"] = sweep_f2()
        elif target == "F3":
            print("F3 — Dense Branching Interference (SC-11)")
            results["F3"] = sweep_f3()
        elif target == "F4":
            print("F4 — History-Dependent Fork (SC-1/SC-3)")
            results["F4"] = sweep_f4()
        else:
            print(f"Unknown target: {target}")
            sys.exit(1)
    else:
        results = run_all()

    if json_mode:
        print(_json.dumps(results, indent=2))
