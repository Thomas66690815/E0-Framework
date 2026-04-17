"""
Scaling Benchmark (SC-11 — Phase B)
====================================
Tests whether E₀'s structural advantage survives at scale.

Falsifiable prediction: E₀ outperforms memoryless greedy at N=100, 500.

SC-11 concern: E₀'s interference depends on full path structure.
Holonomy Independence Theorem (P1 Theorem 1) proves phase differences
are path-local — cannot be computed from state summaries. If S_eff
discrimination collapses at scale, that is a terminal structural
limitation, not an engineering problem.

Design principle: Each topology family embeds a structural challenge
that REQUIRES memory to solve. On topologies where greedy is optimal,
we learn nothing about E₀'s advantage.

Topology families:
  WALL_GRID   — NxN grid with wall forcing detour against gradient
  TRAP_GRID   — Grid with siren traps ON the forward path
  DECOY_DAG   — Parallel paths, some fail (requires learning)
  SHORTCUT    — Long backbone + rare shortcuts (memory finds shortcuts)

Scale levels:
  L0 (baseline)  — N ~  25
  L1             — N ~  50
  L2             — N ~ 100
  L3             — N ~ 225
  L4 (stretch)   — N ~ 500

Methods:
  E₀         — Full controller with historization + revisit penalty
  Greedy     — argmin Δ·R₀, no memory
  Random     — Uniform random neighbor selection

Usage:
  py -3 -m e0_controller.benchmark_scaling              # run all
  py -3 -m e0_controller.benchmark_scaling --level L2    # single level
  py -3 -m e0_controller.benchmark_scaling --json        # machine-readable
"""

from __future__ import annotations

import json
import math
import random as rng
import sys
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller, HybridMode


# ══════════════════════════════════════════════
# Data types
# ══════════════════════════════════════════════

@dataclass
class ScaleDomain:
    """One benchmark domain at a specific scale."""
    name: str
    family: str           # GRID, DAG, TRAP_GRID, RANDOM
    landscape: Landscape
    start: str
    goal: str
    execute_fn: Callable[[str, str], Outcome]
    node_count: int
    edge_count: int
    optimal_path_length: int


@dataclass
class MethodResult:
    """Result of one method on one domain."""
    method: str
    goal_reached: bool
    steps: int
    wall_time_ms: float
    unique_states: int
    revisits: int


@dataclass
class ScaleResult:
    """Result of all methods on one domain."""
    domain: str
    family: str
    node_count: int
    edge_count: int
    optimal_path: int
    results: Dict[str, MethodResult]


# ══════════════════════════════════════════════
# Landscape Generators
# ══════════════════════════════════════════════

def _all_success(source: str, target: str) -> Outcome:
    return Outcome.SUCCESS


def _cell(r: int, c: int) -> str:
    return f"R{r}C{c}"


# ── WALL_GRID: NxN grid with wall forcing detour against gradient ──

def build_wall_grid(rows: int, cols: int) -> ScaleDomain:
    """NxN grid with a wall blocking the direct path.

    Wall spans column cols//2, rows 1..rows-1 (gap only at row 0).
    Greedy must go AGAINST the gradient (up toward row 0) to pass.
    At small scale this is trivial; at N=225+ it requires sustained
    anti-gradient navigation. Memory tracks the failed attempts.
    """
    L = Landscape()
    gr, gc = rows - 1, cols - 1
    max_dist = rows + cols
    wall_col = cols // 2
    walls = {(r, wall_col) for r in range(1, rows)}

    for r in range(rows):
        for c in range(cols):
            if (r, c) in walls:
                continue
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols and (nr, nc) not in walls:
                    dist = abs(nr - gr) + abs(nc - gc)
                    delta = 0.1 + 0.5 * (dist / max_dist)
                    L.add_edge(_cell(r, c), _cell(nr, nc),
                               delta=round(delta, 4),
                               resistance=0.5)

    n_wall = len(walls)
    n_nodes = rows * cols - n_wall
    n_edges = sum(1 for e in L.edges)
    return ScaleDomain(
        name=f"WALL_GRID_{rows}x{cols}",
        family="WALL_GRID",
        landscape=L,
        start=_cell(0, 0),
        goal=_cell(gr, gc),
        execute_fn=_all_success,
        node_count=n_nodes,
        edge_count=n_edges,
        optimal_path_length=rows + cols - 2 + 2,  # detour costs ~2 extra
    )


# ── TRAP_GRID: Siren traps ON the forward path ──

def build_trap_grid(rows: int, cols: int, n_traps: int, seed: int = 42) -> ScaleDomain:
    """Grid with n_traps siren cycles placed ON the forward diagonal.

    Traps are 2-cell bidirectional cycles with delta much lower than
    the surrounding edges. Memoryless greedy enters and oscillates.
    E₀'s revisit penalty (α=2.0) should escape after 1-2 cycles.

    Key: traps are placed on the optimal path diagonal (r+c near midpoints),
    so the controller MUST pass through trap territory.
    """
    L = Landscape()
    gr, gc = rows - 1, cols - 1
    max_dist = rows + cols

    # Normal grid edges
    for r in range(rows):
        for c in range(cols):
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    dist = abs(nr - gr) + abs(nc - gc)
                    delta = 0.15 + 0.5 * (dist / max_dist)
                    L.add_edge(_cell(r, c), _cell(nr, nc),
                               delta=round(delta, 4),
                               resistance=0.5)

    # Place traps on the forward diagonal
    gen = rng.Random(seed)
    diagonal_cells = []
    for r in range(1, rows - 1):
        for c in range(1, cols - 1):
            # On or near the diagonal (forward path)
            diag_dist = abs(r / rows - c / cols)
            if diag_dist < 0.3:
                diagonal_cells.append((r, c))

    gen.shuffle(diagonal_cells)
    trap_positions = set()
    for r, c in diagonal_cells[:n_traps]:
        trap_positions.add((r, c))
        # Make edges between (r,c) and (r,c+1) very attractive (siren)
        nc = c + 1
        if nc < cols:
            trap_delta = 0.02  # Much lower than normal (~0.15-0.65)
            for e in L.edges:
                if e.source == _cell(r, c) and e.target == _cell(r, nc):
                    L._delta[e] = trap_delta
                if e.source == _cell(r, nc) and e.target == _cell(r, c):
                    L._delta[e] = trap_delta

    n_edges = sum(1 for _ in L.edges)
    return ScaleDomain(
        name=f"TRAP_GRID_{rows}x{cols}_t{len(trap_positions)}",
        family="TRAP_GRID",
        landscape=L,
        start=_cell(0, 0),
        goal=_cell(gr, gc),
        execute_fn=_all_success,
        node_count=rows * cols,
        edge_count=n_edges,
        optimal_path_length=rows + cols - 2,
    )


# ── DECOY_DAG: Parallel paths, some fail ──

def build_decoy_dag(paths: int, depth: int, fail_fraction: float = 0.4,
                    seed: int = 42) -> ScaleDomain:
    """K parallel paths, fraction of them FAIL at random depth.

    Decoy paths have MUCH lower delta (very attractive) but execute_fn
    returns FAILURE deep in the path. Greedy enters the decoy, walks
    most of the depth, then fails — and re-enters because the delta
    is still lowest. E₀ learns from FAILURE (R_eff increases) and
    routes to non-failing paths.
    """
    gen = rng.Random(seed)
    n_fail = max(1, int(paths * fail_fraction))
    fail_paths = set(gen.sample(range(paths), n_fail))
    fail_depths: Dict[int, int] = {}
    for p in fail_paths:
        # Fail LATE — 70-90% through the path (maximum wasted steps)
        fail_depths[p] = gen.randint(int(depth * 0.7), max(int(depth * 0.9), int(depth * 0.7) + 1))

    L = Landscape()
    for p in range(paths):
        is_decoy = p in fail_paths
        # Decoys: delta=0.08 (S_eff=0.08*0.3=0.024) vs good: delta=0.30 (S_eff=0.30*0.5=0.15)
        base_delta = 0.08 if is_decoy else 0.30
        base_r = 0.30 if is_decoy else 0.50
        prev = "S"
        for d in range(depth):
            node = f"P{p}_D{d}"
            L.add_edge(prev, node, delta=base_delta, resistance=base_r)
            prev = node
        L.add_edge(prev, "GOAL", delta=base_delta, resistance=base_r)

    # Cross-links for recovery after failure
    for d in range(depth):
        for p in range(paths - 1):
            src = f"P{p}_D{d}"
            dst = f"P{p+1}_D{d}"
            L.add_edge(src, dst, delta=0.5, resistance=0.8)
            L.add_edge(dst, src, delta=0.5, resistance=0.8)

    # Back-edges from fail points to S (expensive but reachable)
    for p, fail_d in fail_depths.items():
        fail_node = f"P{p}_D{fail_d}"
        L.add_edge(fail_node, "S", delta=0.6, resistance=1.0)

    def execute_fn(source: str, target: str) -> Outcome:
        for p, fail_d in fail_depths.items():
            fail_node = f"P{p}_D{fail_d}"
            next_node = f"P{p}_D{fail_d + 1}" if fail_d + 1 < depth else "GOAL"
            if source == fail_node and target == next_node:
                return Outcome.FAILURE
        return Outcome.SUCCESS

    n_nodes = 2 + paths * depth
    n_edges = paths * (depth + 1) + 2 * (paths - 1) * depth
    return ScaleDomain(
        name=f"DECOY_DAG_{paths}p_{depth}d_f{n_fail}",
        family="DECOY_DAG",
        landscape=L,
        start="S",
        goal="GOAL",
        execute_fn=execute_fn,
        node_count=n_nodes,
        edge_count=n_edges,
        optimal_path_length=depth + 1,
    )


# ── SHORTCUT: Long path + rare shortcuts (finds them via memory) ──

def build_shortcut_graph(n: int, n_shortcuts: int, seed: int = 42) -> ScaleDomain:
    """Ring of N nodes with goal at N//2 (opposite side of ring).

    Going around the ring takes N//2 steps. A few shortcut edges
    cut across the ring (delta=0.05, very attractive). Greedy finds
    shortcuts on first encounter, but the *sequence* of shortcuts
    matters: some lead to dead-end spurs. E₀'s historization tracks
    which shortcuts actually lead to progress.

    Dead-end shortcuts: 40% of shortcuts lead to spur nodes (2 hops
    off the ring, then dead end). Greedy enters and gets stuck cycling.
    E₀ learns to avoid them.
    """
    L = Landscape()
    gen = rng.Random(seed)
    ring = [f"N{i}" for i in range(n)]
    goal_idx = n // 2

    # Bidirectional ring — forward edges (toward goal) have lower delta
    # so both greedy and E₀ naturally progress toward goal.
    # Backward edges are more expensive (delta=0.4).
    for i in range(n):
        j = (i + 1) % n
        # Forward direction: toward goal (shortest arc)
        i_to_goal = min(abs(goal_idx - i), n - abs(goal_idx - i))
        j_to_goal = min(abs(goal_idx - j), n - abs(goal_idx - j))
        if j_to_goal <= i_to_goal:
            fwd_src, fwd_dst = ring[i], ring[j]
            bwd_src, bwd_dst = ring[j], ring[i]
        else:
            fwd_src, fwd_dst = ring[j], ring[i]
            bwd_src, bwd_dst = ring[i], ring[j]
        L.add_edge(fwd_src, fwd_dst, delta=0.20, resistance=0.50)
        L.add_edge(bwd_src, bwd_dst, delta=0.40, resistance=0.50)

    extra_nodes = 0
    n_dead_shortcuts = max(1, int(n_shortcuts * 0.4))
    n_good_shortcuts = n_shortcuts - n_dead_shortcuts

    # Good shortcuts: jump forward along shortest path to goal
    good_sources = gen.sample(range(1, goal_idx), min(n_good_shortcuts, goal_idx - 1))
    for src_idx in good_sources:
        dst_idx = min(src_idx + n // 6, goal_idx)  # jump ~1/6 of ring forward
        L.add_edge(ring[src_idx], ring[dst_idx], delta=0.05, resistance=0.3)

    # Dead-end shortcuts: lead to spur (2 nodes off ring, then dead end)
    # Economics tuned for α=2.0 revisit penalty:
    #   Entry S_eff = 0.06 < ring 0.15 → greedy enters
    #   With penalty: 0.06 × 3 = 0.18 > 0.15 → E₀ avoids after first visit
    #   Spur exit S_eff = 0.10, spur internal w/ penalty = 0.135 > 0.10 → E₀ exits
    dead_sources = gen.sample(
        [i for i in range(1, n) if i != goal_idx and i not in good_sources],
        min(n_dead_shortcuts, n - 2 - len(good_sources)))
    fail_edges: Set[Tuple[str, str]] = set()
    for i, src_idx in enumerate(dead_sources):
        spur1 = f"SPUR{i}_1"
        spur2 = f"SPUR{i}_2"
        # Entry: attractive but penalty-escapable
        L.add_edge(ring[src_idx], spur1, delta=0.20, resistance=0.30)
        L.add_edge(spur1, spur2, delta=0.15, resistance=0.30)
        # Return FAILS — historization increases R permanently
        L.add_edge(spur2, spur1, delta=0.30, resistance=0.50)
        fail_edges.add((spur2, spur1))
        # Exit: moderate cost, cheaper than penalized spur
        L.add_edge(spur1, ring[src_idx], delta=0.25, resistance=0.40)
        extra_nodes += 2

    def execute_fn(source: str, target: str) -> Outcome:
        if (source, target) in fail_edges:
            return Outcome.FAILURE
        return Outcome.SUCCESS

    return ScaleDomain(
        name=f"SHORTCUT_N{n}_s{n_shortcuts}",
        family="SHORTCUT",
        landscape=L,
        start=ring[0],
        goal=ring[goal_idx],
        execute_fn=execute_fn,
        node_count=n + extra_nodes,
        edge_count=sum(1 for _ in L.edges),
        optimal_path_length=goal_idx,
    )


# ══════════════════════════════════════════════
# Scale Levels
# ══════════════════════════════════════════════

SCALE_LEVELS = {
    "L0": {
        "label": "Baseline (N~25)",
        "domains": [
            lambda: build_wall_grid(5, 5),
            lambda: build_trap_grid(5, 5, 2),
            lambda: build_decoy_dag(5, 4, 0.4),
            lambda: build_shortcut_graph(25, 4),
        ],
        "max_cycles": 200,
    },
    "L1": {
        "label": "Medium (N~50)",
        "domains": [
            lambda: build_wall_grid(7, 7),
            lambda: build_trap_grid(7, 7, 4),
            lambda: build_decoy_dag(7, 7, 0.4),
            lambda: build_shortcut_graph(50, 6),
        ],
        "max_cycles": 400,
    },
    "L2": {
        "label": "Large (N~100)",
        "domains": [
            lambda: build_wall_grid(10, 10),
            lambda: build_trap_grid(10, 10, 8),
            lambda: build_decoy_dag(10, 10, 0.4),
            lambda: build_shortcut_graph(100, 10),
        ],
        "max_cycles": 800,
    },
    "L3": {
        "label": "XL (N~225)",
        "domains": [
            lambda: build_wall_grid(15, 15),
            lambda: build_trap_grid(15, 15, 15),
            lambda: build_decoy_dag(15, 15, 0.4),
            lambda: build_shortcut_graph(225, 15),
        ],
        "max_cycles": 1500,
    },
    "L4": {
        "label": "Stretch (N~500)",
        "domains": [
            lambda: build_wall_grid(22, 22),
            lambda: build_trap_grid(22, 22, 30),
            lambda: build_decoy_dag(20, 25, 0.4),
            lambda: build_shortcut_graph(500, 25),
        ],
        "max_cycles": 3000,
    },
}


# ══════════════════════════════════════════════
# Methods (E₀, Greedy, Random)
# ══════════════════════════════════════════════

def run_e0(domain: ScaleDomain, max_cycles: int) -> MethodResult:
    """E₀ controller — full historization + revisit penalty."""
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

    return MethodResult(
        method="E0",
        goal_reached=goal_reached,
        steps=len(trace.steps),
        wall_time_ms=round(elapsed, 1),
        unique_states=int(metrics["unique_states"]),
        revisits=int(metrics["revisit_count"]),
    )


def run_greedy(domain: ScaleDomain, max_cycles: int) -> MethodResult:
    """Memoryless greedy — argmin Δ·R₀ among neighbors, with failure fallback.

    Each step: try neighbors in ascending S_eff order, execute via execute_fn.
    First SUCCESS transition is taken. Between steps, all failures are forgotten
    (greedy has no memory). This models "immediate feedback without learning."
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
        # Try in S_eff order; take first that succeeds
        moved = False
        for target, _ in neighbors:
            outcome = execute_fn(current, target)
            steps += 1
            if outcome == Outcome.SUCCESS:
                current = target
                path.append(current)
                visited_count[current] = visited_count.get(current, 0) + 1
                moved = True
                break
            if steps >= max_cycles:
                break
        if not moved:
            break  # all neighbors fail — stuck
    elapsed = (time.perf_counter() - t0) * 1000

    revisits = sum(v - 1 for v in visited_count.values() if v > 1)
    return MethodResult(
        method="GREEDY",
        goal_reached=current == domain.goal,
        steps=steps,
        wall_time_ms=round(elapsed, 1),
        unique_states=len(visited_count),
        revisits=revisits,
    )


def run_random(domain: ScaleDomain, max_cycles: int, seed: int = 99) -> MethodResult:
    """Random walk — uniform random neighbor selection."""
    L = domain.landscape
    current = domain.start
    gen = rng.Random(seed)
    visited_count: Dict[str, int] = {current: 1}
    steps = 0

    t0 = time.perf_counter()
    while steps < max_cycles and current != domain.goal:
        neighbors = [e.target for e in L.edges if e.source == current]
        if not neighbors:
            break
        current = gen.choice(neighbors)
        visited_count[current] = visited_count.get(current, 0) + 1
        steps += 1
    elapsed = (time.perf_counter() - t0) * 1000

    revisits = sum(v - 1 for v in visited_count.values() if v > 1)
    return MethodResult(
        method="RANDOM",
        goal_reached=current == domain.goal,
        steps=steps,
        wall_time_ms=round(elapsed, 1),
        unique_states=len(visited_count),
        revisits=revisits,
    )


# ══════════════════════════════════════════════
# Benchmark Runner
# ══════════════════════════════════════════════

METHODS = [
    ("E0", run_e0),
    ("GREEDY", run_greedy),
    ("RANDOM", run_random),
]


def run_level(level: str) -> List[ScaleResult]:
    """Run all domains at one scale level."""
    spec = SCALE_LEVELS[level]
    max_cycles = spec["max_cycles"]
    results = []

    for builder in spec["domains"]:
        domain = builder()
        method_results = {}
        for name, runner in METHODS:
            result = runner(domain, max_cycles)
            method_results[name] = result

        results.append(ScaleResult(
            domain=domain.name,
            family=domain.family,
            node_count=domain.node_count,
            edge_count=domain.edge_count,
            optimal_path=domain.optimal_path_length,
            results=method_results,
        ))

    return results


def run_all_levels(levels: Optional[List[str]] = None) -> Dict[str, List[ScaleResult]]:
    """Run all requested scale levels."""
    if levels is None:
        levels = list(SCALE_LEVELS.keys())
    return {level: run_level(level) for level in levels}


# ══════════════════════════════════════════════
# Output
# ══════════════════════════════════════════════

def print_level(level: str, results: List[ScaleResult]) -> None:
    """Pretty-print one scale level."""
    spec = SCALE_LEVELS[level]
    print(f"\n{'═' * 100}")
    print(f"  {level}: {spec['label']}  (max_cycles={spec['max_cycles']})")
    print(f"{'═' * 100}")

    header = (
        f"{'Domain':<30} {'|V|':>4} {'|E|':>5} {'Opt':>3} │ "
        f"{'Method':<7} {'Goal':>4} {'Steps':>6} {'Time':>8} {'Unique':>6} {'Revis':>5}"
    )
    print(header)
    print("─" * 100)

    for sr in results:
        first = True
        for method in ["E0", "GREEDY", "RANDOM"]:
            mr = sr.results[method]
            goal_str = "✓" if mr.goal_reached else "✗"
            if first:
                print(
                    f"{sr.domain:<30} {sr.node_count:>4} {sr.edge_count:>5} {sr.optimal_path:>3} │ "
                    f"{mr.method:<7} {goal_str:>4} {mr.steps:>6} {mr.wall_time_ms:>7.1f}ms "
                    f"{mr.unique_states:>6} {mr.revisits:>5}"
                )
                first = False
            else:
                print(
                    f"{'':30} {'':>4} {'':>5} {'':>3} │ "
                    f"{mr.method:<7} {goal_str:>4} {mr.steps:>6} {mr.wall_time_ms:>7.1f}ms "
                    f"{mr.unique_states:>6} {mr.revisits:>5}"
                )
        print("─" * 100)


def print_summary(all_results: Dict[str, List[ScaleResult]]) -> None:
    """Print cross-level summary: does E₀'s advantage survive?"""
    print(f"\n{'═' * 80}")
    print("  SC-11 SCALING VERDICT")
    print(f"{'═' * 80}")

    print(f"\n{'Level':<8} {'Domain':<30} {'E0':>6} {'Greedy':>8} {'Random':>8} │ {'E0 wins':>7}")
    print("─" * 80)

    e0_wins_total = 0
    comparisons_total = 0

    for level, results in all_results.items():
        for sr in results:
            e0 = sr.results["E0"]
            greedy = sr.results["GREEDY"]
            rand = sr.results["RANDOM"]

            # E₀ wins if it reaches goal AND (greedy doesn't, or E₀ uses fewer steps)
            e0_better_than_greedy = (
                (e0.goal_reached and not greedy.goal_reached) or
                (e0.goal_reached and greedy.goal_reached and e0.steps < greedy.steps)
            )
            e0_better_than_random = (
                (e0.goal_reached and not rand.goal_reached) or
                (e0.goal_reached and rand.goal_reached and e0.steps < rand.steps)
            )
            wins = e0_better_than_greedy or e0_better_than_random
            comparisons_total += 1
            if wins:
                e0_wins_total += 1

            e0_str = f"{'✓' if e0.goal_reached else '✗'}/{e0.steps}"
            g_str = f"{'✓' if greedy.goal_reached else '✗'}/{greedy.steps}"
            r_str = f"{'✓' if rand.goal_reached else '✗'}/{rand.steps}"
            win_str = "YES" if wins else "no"

            print(f"{level:<8} {sr.domain:<30} {e0_str:>6} {g_str:>8} {r_str:>8} │ {win_str:>7}")

    print("─" * 80)

    win_rate = e0_wins_total / comparisons_total if comparisons_total else 0
    print(f"\n  E₀ advantage rate: {e0_wins_total}/{comparisons_total} = {win_rate:.0%}")

    # SC-11 verdict
    if win_rate >= 0.75:
        verdict = "CONFIRMED — E₀'s structural advantage survives at scale"
    elif win_rate >= 0.5:
        verdict = "PARTIAL — E₀ helps on some topologies but not universally"
    else:
        verdict = "FALSIFIED — E₀'s advantage does NOT survive at scale"

    print(f"  SC-11 verdict:     {verdict}")
    print()


def results_to_dict(all_results: Dict[str, List[ScaleResult]]) -> Dict:
    """Convert to serializable dict."""
    out = {"benchmark": "scaling_sc11_v1", "levels": {}}
    for level, results in all_results.items():
        out["levels"][level] = {
            "label": SCALE_LEVELS[level]["label"],
            "max_cycles": SCALE_LEVELS[level]["max_cycles"],
            "domains": [
                {
                    "name": sr.domain,
                    "family": sr.family,
                    "node_count": sr.node_count,
                    "edge_count": sr.edge_count,
                    "optimal_path": sr.optimal_path,
                    "methods": {
                        name: {
                            "goal_reached": mr.goal_reached,
                            "steps": mr.steps,
                            "wall_time_ms": mr.wall_time_ms,
                            "unique_states": mr.unique_states,
                            "revisits": mr.revisits,
                        }
                        for name, mr in sr.results.items()
                    },
                }
                for sr in results
            ],
        }
    return out


# ══════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════

if __name__ == "__main__":
    levels_to_run = None
    json_mode = "--json" in sys.argv

    if "--level" in sys.argv:
        idx = sys.argv.index("--level")
        if idx + 1 < len(sys.argv):
            requested = sys.argv[idx + 1].upper()
            if requested in SCALE_LEVELS:
                levels_to_run = [requested]
            else:
                print(f"Unknown level: {requested}. Available: {list(SCALE_LEVELS.keys())}")
                sys.exit(1)

    all_results = run_all_levels(levels_to_run)

    if json_mode:
        print(json.dumps(results_to_dict(all_results), indent=2))
    else:
        for level in sorted(all_results.keys()):
            print_level(level, all_results[level])
        print_summary(all_results)
