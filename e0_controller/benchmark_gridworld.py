"""
Grid World Benchmark: E₀ vs Naive-Greedy vs A*

Three 5×5 grid variants with obstacles, dead-ends, and trap loops.
Compares success rate and steps-to-goal across decision strategies.

Methods:
  Naive Greedy — picks lowest-delta neighbor, no memory, no E₀
  E₀ Greedy   — E₀ controller with revisit penalty + escalation
  A*          — optimal path with Manhattan heuristic

Domains:
  V1 — Detour wall: wall forces detour, naive greedy oscillates
  V2 — Dead-end attractor: moderate-delta dead-end lures naive greedy
  V3 — Trap loop: cycle with low delta traps memoryless agents

Usage:
  python -m e0_controller.benchmark_gridworld          # run all
  python -m e0_controller.benchmark_gridworld --json    # machine-readable
"""

import heapq
import json
import sys
from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller, HybridMode
from e0_controller.primitives import Outcome

GRID_SIZE = 5


# ──────────────────────────────────────────────
# Grid World Construction
# ──────────────────────────────────────────────

def _cell(r: int, c: int) -> str:
    return f"R{r}C{c}"


def _manhattan(r1: int, c1: int, r2: int, c2: int) -> int:
    return abs(r1 - r2) + abs(c1 - c2)


def _parse_cell(name: str) -> Tuple[int, int]:
    """Parse 'R3C7' → (3, 7)."""
    parts = name.split("C")
    return int(parts[0][1:]), int(parts[1])


def _build_grid(
    rows: int,
    cols: int,
    walls: FrozenSet[Tuple[int, int]],
    goal: Tuple[int, int],
    base_delta: float = 0.3,
    base_resistance: float = 1.0,
    delta_overrides: Optional[Dict[Tuple[Tuple[int,int],Tuple[int,int]], float]] = None,
) -> Landscape:
    """
    Build a 4-connected grid landscape.
    Delta is proportional to Manhattan distance to goal (farther = higher Δ).
    delta_overrides: {((r1,c1),(r2,c2)): delta} for specific edges.
    """
    L = Landscape()
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    gr, gc = goal
    max_dist = rows + cols

    for r in range(rows):
        for c in range(cols):
            if (r, c) in walls:
                continue
            for dr, dc in directions:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols and (nr, nc) not in walls:
                    key = ((r, c), (nr, nc))
                    if delta_overrides and key in delta_overrides:
                        delta = delta_overrides[key]
                    else:
                        dist = _manhattan(nr, nc, gr, gc)
                        delta = base_delta + 0.5 * (dist / max_dist)
                    L.add_edge(_cell(r, c), _cell(nr, nc),
                               delta=round(delta, 4),
                               resistance=base_resistance)
    return L


# ──────────────────────────────────────────────
# Three Grid Variants
# ──────────────────────────────────────────────

def build_v1_detour_wall() -> Tuple[Landscape, str, str, Set[str]]:
    """
    V1 — Detour wall (5×5).

    Wall at col 2, rows 1-4. Gap ONLY at row 0.
    Greedy from (0,0) to (4,4) heads right+down, hits wall,
    then must go UP to row 0 (against the delta gradient) to pass.

        0 1 2 3 4
    0   S . . . .   ← only gap
    1   . . # . .
    2   . . # . .
    3   . . # . .
    4   . . # . G
    """
    walls = frozenset((r, 2) for r in range(1, 5))
    L = _build_grid(GRID_SIZE, GRID_SIZE, walls, goal=(4, 4))
    return L, _cell(0, 0), _cell(4, 4), {_cell(4, 4)}


def build_v2_deadend_lure() -> Tuple[Landscape, str, str, Set[str]]:
    """
    V2 — Dead-end attractor (5×5).

    Moderate-delta dead-end at bottom-left lures greedy.
    Wall blocks escape from dead-end toward goal.

        0 1 2 3 4
    0   S . . . .
    1   . . . . .
    2   . # # . .
    3   L L . . .
    4   L # . . G

    L = lure (Δ=0.20, moderate). # = wall.
    Naive greedy goes into lure and cycles (no exit past (4,1) wall).
    E₀ revisit penalty: 0.20 × 3.0 = 0.60 > 0.45 exit tension → escape.
    """
    walls: Set[Tuple[int, int]] = set()
    walls.add((2, 1))
    walls.add((2, 2))
    walls.add((4, 1))

    overrides: Dict[Tuple[Tuple[int,int],Tuple[int,int]], float] = {}
    lure_edges = [
        ((1, 0), (2, 0)), ((2, 0), (3, 0)), ((3, 0), (4, 0)),
        ((3, 0), (3, 1)), ((3, 1), (3, 0)), ((4, 0), (3, 0)),
        ((3, 1), (4, 1)),  # toward wall (doesn't exist, harmless)
    ]
    for src, dst in lure_edges:
        overrides[(src, dst)] = 0.20

    L = _build_grid(GRID_SIZE, GRID_SIZE, frozenset(walls), goal=(4, 4),
                    delta_overrides=overrides)
    return L, _cell(0, 0), _cell(4, 4), {_cell(4, 4)}


def build_v3_trap_loop() -> Tuple[Landscape, str, str, Set[str]]:
    """
    V3 — Trap loop (5×5).

    A moderate-delta 3-cell cycle on the direct path traps naive agents.
    E₀ historization should escape via escalation.

        0 1 2 3 4
    0   S . . . .
    1   . T T . .
    2   . T # . .
    3   . . . . .
    4   . . . . G

    T = trap cells (Δ=0.18), # = wall.
    Trap cycle: (1,1)↔(1,2) and (1,1)↔(2,1) with Δ=0.18.
    Naive greedy enters trap and cycles forever (no historization).
    E₀ historization: 0.18 × (1+3) = 0.72 > ~0.55 exit → escapable.
    """
    walls: Set[Tuple[int, int]] = set()
    walls.add((2, 2))

    overrides: Dict[Tuple[Tuple[int,int],Tuple[int,int]], float] = {}
    trap_cells = [(1, 1), (1, 2), (2, 1)]
    for (r1, c1) in trap_cells:
        for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
            r2, c2 = r1+dr, c1+dc
            if (r2, c2) in trap_cells:
                overrides[((r1,c1),(r2,c2))] = 0.18
            elif 0 <= r2 < GRID_SIZE and 0 <= c2 < GRID_SIZE and (r2,c2) not in walls:
                overrides[((r2,c2),(r1,c1))] = 0.20  # entry moderately attractive

    L = _build_grid(GRID_SIZE, GRID_SIZE, frozenset(walls), goal=(4, 4),
                    delta_overrides=overrides)
    return L, _cell(0, 0), _cell(4, 4), {_cell(4, 4)}


VARIANTS = {
    "V1_detour_wall": build_v1_detour_wall,
    "V2_deadend_lure": build_v2_deadend_lure,
    "V3_trap_loop": build_v3_trap_loop,
}


# ──────────────────────────────────────────────
# A* Baseline
# ──────────────────────────────────────────────

def astar(landscape: Landscape, start: str, goal: str) -> Optional[List[str]]:
    """A* search with Manhattan heuristic. Returns path or None."""
    gr, gc = _parse_cell(goal)

    def h(state: str) -> float:
        r, c = _parse_cell(state)
        return float(_manhattan(r, c, gr, gc))

    adj: Dict[str, List[str]] = {}
    for edge in landscape.edges:
        if edge.source not in adj:
            adj[edge.source] = []
        adj[edge.source].append(edge.target)

    open_set: List[Tuple[float, int, str]] = [(h(start), 0, start)]
    g_score: Dict[str, float] = {start: 0.0}
    came_from: Dict[str, str] = {}
    counter = 0
    closed: Set[str] = set()

    while open_set:
        _, _, current = heapq.heappop(open_set)
        if current in closed:
            continue
        closed.add(current)

        if current == goal:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            return list(reversed(path))

        for neighbor in adj.get(current, []):
            if neighbor in closed:
                continue
            tentative = g_score[current] + 1.0
            if tentative < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_score[neighbor] = tentative
                counter += 1
                heapq.heappush(open_set,
                               (tentative + h(neighbor), counter, neighbor))

    return None


# ──────────────────────────────────────────────
# Naive Greedy (no E₀, no memory)
# ──────────────────────────────────────────────

def naive_greedy_run(
    landscape: Landscape,
    start: str,
    goal: str,
    max_steps: int = 200,
) -> Tuple[bool, int, List[str]]:
    """
    Naive greedy: pick neighbor with lowest delta. No memory, no E₀.
    Gets trapped in cycles easily.
    """
    adj: Dict[str, List[Tuple[str, float]]] = {}
    for edge in landscape.edges:
        d = landscape.difference(edge.source, edge.target)
        if d is None:
            d = 1.0
        if edge.source not in adj:
            adj[edge.source] = []
        adj[edge.source].append((edge.target, d))

    path = [start]
    current = start
    for step in range(max_steps):
        if current == goal:
            return True, step, path
        neighbors = adj.get(current, [])
        if not neighbors:
            return False, step, path
        # Pick lowest delta
        best = min(neighbors, key=lambda x: x[1])
        current = best[0]
        path.append(current)
    return current == goal, max_steps, path


# ──────────────────────────────────────────────
# E₀ Runners
# ──────────────────────────────────────────────

def _success_fn(s: str, t: str) -> Outcome:
    return Outcome.SUCCESS


def e0_greedy_run(
    landscape: Landscape,
    start: str,
    goal: str,
    max_steps: int = 200,
) -> Tuple[bool, int, List[str]]:
    """E₀ greedy: historization + revisit penalty + escalation."""
    ctrl = E0Controller(
        landscape, _success_fn,
        hybrid_mode=HybridMode.GREEDY,
        hybrid_horizon=0,
    )
    trace = ctrl.run(start, max_cycles=max_steps, goal=goal)
    reached = goal in trace.path
    return reached, len(trace.steps), trace.path


# ──────────────────────────────────────────────
# Benchmark Runner
# ──────────────────────────────────────────────

@dataclass
class BenchmarkResult:
    variant: str
    method: str
    trials: int
    successes: int
    avg_steps: float
    min_steps: int
    max_steps: int

    @property
    def success_rate(self) -> float:
        return self.successes / self.trials if self.trials > 0 else 0.0


def _collect(results_list: List[Tuple[bool, int, List[str]]],
             variant: str, method: str) -> BenchmarkResult:
    """Aggregate trial results into a BenchmarkResult."""
    n = len(results_list)
    succ = [s for reached, s, _ in results_list if reached]
    return BenchmarkResult(
        variant, method, n, len(succ),
        (sum(succ) / len(succ)) if succ else 0.0,
        min(succ) if succ else 0,
        max(succ) if succ else 0,
    )


def run_benchmark(
    variant_name: str,
    n_trials: int = 10,
    max_steps: int = 50,
) -> List[BenchmarkResult]:
    """Run all methods on one grid variant."""
    build_fn = VARIANTS[variant_name]
    results: List[BenchmarkResult] = []

    # ── A* (deterministic, single run) ──
    L, start, goal, goal_set = build_fn()
    astar_path = astar(L, start, goal)
    if astar_path is not None:
        steps = len(astar_path) - 1
        results.append(BenchmarkResult(
            variant_name, "A*", 1, 1, float(steps), steps, steps))
    else:
        results.append(BenchmarkResult(variant_name, "A*", 1, 0, 0, 0, 0))

    # ── Naive Greedy ──
    naive_results = []
    for _ in range(n_trials):
        L, start, goal, goal_set = build_fn()
        naive_results.append(naive_greedy_run(L, start, goal, max_steps))
    results.append(_collect(naive_results, variant_name, "Naive_Greedy"))

    # ── E₀ Greedy ──
    e0g_results = []
    for _ in range(n_trials):
        L, start, goal, goal_set = build_fn()
        e0g_results.append(e0_greedy_run(L, start, goal, max_steps))
    results.append(_collect(e0g_results, variant_name, "E0_Greedy"))

    return results


# ──────────────────────────────────────────────
# Display
# ──────────────────────────────────────────────

def print_results(all_results: List[BenchmarkResult]) -> None:
    print("\n" + "=" * 75)
    print("GRID WORLD BENCHMARK — E₀ vs Naive Greedy vs A*")
    print("=" * 75)

    current_variant = None
    for r in all_results:
        if r.variant != current_variant:
            current_variant = r.variant
            print(f"\n--- {r.variant} (5×5 grid) ---")
            print(f"  {'Method':<16} {'Success':>8} {'Avg Steps':>10} "
                  f"{'Min':>5} {'Max':>5}")
            print(f"  {'-'*16} {'-'*8} {'-'*10} {'-'*5} {'-'*5}")

        rate_str = f"{r.success_rate:.0%}" if r.trials > 1 else (
            "YES" if r.successes > 0 else "NO")
        avg_str = f"{r.avg_steps:.1f}" if r.successes > 0 else "—"
        min_str = str(r.min_steps) if r.successes > 0 else "—"
        max_str = str(r.max_steps) if r.successes > 0 else "—"
        print(f"  {r.method:<16} {rate_str:>8} {avg_str:>10} "
              f"{min_str:>5} {max_str:>5}")

    print("\n" + "=" * 75)


def results_to_json(all_results: List[BenchmarkResult]) -> str:
    return json.dumps([{
        "variant": r.variant, "method": r.method,
        "trials": r.trials, "success_rate": round(r.success_rate, 4),
        "avg_steps": round(r.avg_steps, 2),
        "min_steps": r.min_steps, "max_steps": r.max_steps,
    } for r in all_results], indent=2)


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main():
    json_mode = "--json" in sys.argv
    n_trials = 10

    all_results: List[BenchmarkResult] = []
    for name in VARIANTS:
        print(f"Running {name}...", file=sys.stderr)
        all_results.extend(run_benchmark(name, n_trials=n_trials))

    if json_mode:
        print(results_to_json(all_results))
    else:
        print_results(all_results)


if __name__ == "__main__":
    main()
