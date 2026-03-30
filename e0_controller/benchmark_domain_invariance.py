"""
Domain-Invariance Benchmark (C53)
===================================
10 structurally diverse domains, one controller, zero domain-specific tuning.

Claim: E₀'s controller is domain-invariant — the same algorithm with
identical parameters navigates any well-formed landscape.

Domains:
  D1  Linear Chain      — no branching, pure forward progression
  D2  Diamond           — 2-family interference discrimination
  D3  Gordian Trap      — decoy path with phase-cancelling loop
  D4  Greedy Trap       — 2-cycle oscillation trap (historization-dependent)
  D5  Grid Detour       — 5×5 spatial grid, wall forces detour
  D6  Multi-Goal Star   — fan-out to 3 goals, 1 path fails
  D7  Invoice Process   — 10-state real-world business process
  D8  Nested Cycles     — overlapping cycles + exit to goal
  D9  Wide DAG          — 5 parallel paths converging, no cycles
  D10 Bottleneck Funnel — decoy dead-ends + high-resistance chokepoint

Usage:
  python -m e0_controller.benchmark_domain_invariance          # run all
  python -m e0_controller.benchmark_domain_invariance --json   # machine-readable
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller, HybridMode, RunTrace
from e0_controller.evaluation import evaluate_run, RunEvaluation


# ══════════════════════════════════════════════
# Domain Spec
# ══════════════════════════════════════════════

@dataclass
class DomainSpec:
    """One benchmark domain."""
    name: str
    description: str
    landscape: Landscape
    start: str
    goal: str
    execute_fn: Callable[[str, str], Outcome]
    happy_path_length: int
    topology_class: str       # e.g. "linear", "diamond", "grid", "DAG"
    node_count: int
    edge_count: int


@dataclass
class DomainResult:
    """Result of running one domain."""
    domain: str
    goal_reached: bool
    steps: int
    rating: str
    success_rate: float
    escalations: int
    revisits: int
    efficiency: float
    avg_tension: float
    unique_states: int
    evaluation: RunEvaluation


# ══════════════════════════════════════════════
# 10 Domain Builders
# ══════════════════════════════════════════════

def _all_success(source: str, target: str) -> Outcome:
    return Outcome.SUCCESS


# ── D1: Linear Chain ──

def build_d1_linear_chain() -> DomainSpec:
    """8-node linear chain. No branching, no traps."""
    L = Landscape()
    nodes = ["S", "A", "B", "C", "D", "E", "F", "GOAL"]
    for i in range(len(nodes) - 1):
        L.add_edge(nodes[i], nodes[i + 1],
                   delta=0.3, resistance=0.5)
    return DomainSpec(
        name="D1_linear_chain",
        description="8-node linear chain — pure forward progression",
        landscape=L, start="S", goal="GOAL",
        execute_fn=_all_success,
        happy_path_length=7,
        topology_class="linear",
        node_count=8, edge_count=7,
    )


# ── D2: Diamond ──

def build_d2_diamond() -> DomainSpec:
    """S→A→G, S→B→G. Path B has lower total tension."""
    L = Landscape()
    L.add_edge("S", "A", delta=0.3, resistance=0.4)   # looks easy
    L.add_edge("A", "G", delta=0.5, resistance=2.0)   # but hard finish
    L.add_edge("S", "B", delta=0.5, resistance=0.6)   # higher delta
    L.add_edge("B", "G", delta=0.2, resistance=0.3)   # easy finish
    return DomainSpec(
        name="D2_diamond",
        description="Diamond — 2-family interference discrimination",
        landscape=L, start="S", goal="G",
        execute_fn=_all_success,
        happy_path_length=2,
        topology_class="diamond",
        node_count=4, edge_count=4,
    )


# ── D3: Gordian Trap ──

def _d3_execute(source: str, target: str) -> Outcome:
    """Trap entrance S→A fails — the decoy doesn’t deliver."""
    if source == "S" and target == "A":
        return Outcome.FAILURE
    return Outcome.SUCCESS


def build_d3_gordian_trap() -> DomainSpec:
    """Decoy path S→A→X loops back to S, detour S→B→C→GOAL.

    S→A has lower initial tension but FAILS. After one cycle,
    historization (+0.1 on R) plus revisit penalty makes S→B win.
    """
    L = Landscape()
    # Decoy: low tension but FAILS
    L.add_edge("S", "A", delta=0.2, resistance=0.3)    # 0.06
    L.add_edge("A", "X", delta=0.2, resistance=0.4)    # 0.08
    L.add_edge("X", "S", delta=0.3, resistance=0.5)    # 0.15 — return
    # Forward: higher initial tension, succeeds
    L.add_edge("S", "B", delta=0.3, resistance=0.5)    # 0.15
    L.add_edge("B", "C", delta=0.3, resistance=0.5)    # 0.15
    L.add_edge("C", "GOAL", delta=0.2, resistance=0.3) # 0.06
    return DomainSpec(
        name="D3_gordian_trap",
        description="Gordian trap — failing decoy loop + coherent detour",
        landscape=L, start="S", goal="GOAL",
        execute_fn=_d3_execute,
        happy_path_length=3,
        topology_class="gordian",
        node_count=6, edge_count=6,
    )


# ── D4: Greedy Trap (2-cycle) ──

def build_d4_greedy_trap() -> DomainSpec:
    """A↔C cycle has lower tension than forward; after one cycle
    the revisit penalty on C (0.08×3 = 0.24 > 0.15) makes A→B win.
    """
    L = Landscape()
    L.add_edge("S", "A", delta=0.3, resistance=0.4)    # 0.12
    # Forward path
    L.add_edge("A", "B", delta=0.3, resistance=0.5)    # 0.15
    L.add_edge("B", "D", delta=0.3, resistance=0.5)    # 0.15
    L.add_edge("D", "GOAL", delta=0.2, resistance=0.3) # 0.06
    # Trap: lower tension but penalizable
    L.add_edge("A", "C", delta=0.2, resistance=0.4)    # 0.08
    L.add_edge("C", "A", delta=0.2, resistance=0.4)    # 0.08
    return DomainSpec(
        name="D4_greedy_trap",
        description="Greedy trap — 2-cycle oscillation + forward path",
        landscape=L, start="S", goal="GOAL",
        execute_fn=_all_success,
        happy_path_length=4,
        topology_class="cycle_trap",
        node_count=6, edge_count=6,
    )


# ── D5: Grid Detour (5×5 with wall) ──

def build_d5_grid_detour() -> DomainSpec:
    """5×5 grid with wall forcing detour. Reuses grid logic."""
    L = Landscape()
    size = 5
    walls = {(1, 2), (2, 2), (3, 2)}  # vertical wall in column 2

    def cell(r: int, c: int) -> str:
        return f"R{r}C{c}"

    for r in range(size):
        for c in range(size):
            if (r, c) in walls:
                continue
            # Right
            if c + 1 < size and (r, c + 1) not in walls:
                d = abs(r - 4) + abs(c + 1 - 4)
                L.add_edge(cell(r, c), cell(r, c + 1),
                           delta=0.1 + d * 0.05, resistance=0.3)
            # Down
            if r + 1 < size and (r + 1, c) not in walls:
                d = abs(r + 1 - 4) + abs(c - 4)
                L.add_edge(cell(r, c), cell(r + 1, c),
                           delta=0.1 + d * 0.05, resistance=0.3)
            # Left
            if c - 1 >= 0 and (r, c - 1) not in walls:
                d = abs(r - 4) + abs(c - 1 - 4)
                L.add_edge(cell(r, c), cell(r, c - 1),
                           delta=0.1 + d * 0.05, resistance=0.3)
            # Up
            if r - 1 >= 0 and (r - 1, c) not in walls:
                d = abs(r - 1 - 4) + abs(c - 4)
                L.add_edge(cell(r, c), cell(r - 1, c),
                           delta=0.1 + d * 0.05, resistance=0.3)

    return DomainSpec(
        name="D5_grid_detour",
        description="5×5 grid with wall — spatial detour navigation",
        landscape=L, start="R0C0", goal="R4C4",
        execute_fn=_all_success,
        happy_path_length=8,
        topology_class="grid",
        node_count=len(L._states), edge_count=len(L._delta),
    )


# ── D6: Multi-Goal Star ──

def _d6_execute(source: str, target: str) -> Outcome:
    """B→G2 always fails — forces re-routing."""
    if source == "B" and target == "G2":
        return Outcome.FAILURE
    return Outcome.SUCCESS


def build_d6_multigoal_star() -> DomainSpec:
    """Fan-out to 3 goals. Path B→G2 fails, others succeed."""
    L = Landscape()
    L.add_edge("S", "A", delta=0.3, resistance=0.5)
    L.add_edge("S", "B", delta=0.2, resistance=0.4)   # cheapest, but fails
    L.add_edge("S", "C", delta=0.4, resistance=0.6)
    L.add_edge("A", "G1", delta=0.3, resistance=0.4)
    L.add_edge("B", "G2", delta=0.2, resistance=0.3)  # FAILURE edge
    L.add_edge("C", "G3", delta=0.3, resistance=0.5)
    # Cross-links for recovery after B→G2 fails
    L.add_edge("B", "A", delta=0.4, resistance=0.7)
    L.add_edge("B", "C", delta=0.4, resistance=0.7)
    return DomainSpec(
        name="D6_multigoal_star",
        description="Multi-goal star — 3 goals, 1 failing path",
        landscape=L, start="S", goal="G1",
        execute_fn=_d6_execute,
        happy_path_length=2,
        topology_class="star",
        node_count=7, edge_count=8,
    )


# ── D7: Invoice Process ──

def _d7_execute(source: str, target: str) -> Outcome:
    """Realistic invoice outcomes: customer lookup fails, policy partial."""
    if source == "DATA_EXTRACTED" and target == "CUSTOMER_FOUND":
        return Outcome.FAILURE
    if source == "CONTRACT_MATCH" and target == "POLICY_OK":
        return Outcome.PARTIAL
    return Outcome.SUCCESS


def build_d7_invoice() -> DomainSpec:
    """Real-world invoice processing (10 states, 17 edges)."""
    from e0_controller.domain_invoice import build_invoice_landscape
    L = build_invoice_landscape()
    return DomainSpec(
        name="D7_invoice_process",
        description="Invoice processing — real-world business domain",
        landscape=L, start="RECEIVED", goal="APPROVED",
        execute_fn=_d7_execute,
        happy_path_length=7,
        topology_class="process",
        node_count=10, edge_count=16,
    )


# ── D8: Nested Cycles ──

def _d8_execute(source: str, target: str) -> Outcome:
    """Cycle edge B→S fails — forces exit through B→GOAL."""
    if source == "B" and target == "S":
        return Outcome.FAILURE
    return Outcome.SUCCESS


def build_d8_nested_cycles() -> DomainSpec:
    """Two overlapping cycles with exit via B→GOAL.

    B→S FAILS, so historization increases B→S resistance.
    After one cycle, revisit penalty + increased R makes B→GOAL win.
    """
    L = Landscape()
    # Inner cycle: S→A→B→S
    L.add_edge("S", "A", delta=0.2, resistance=0.4)    # 0.08
    L.add_edge("A", "B", delta=0.2, resistance=0.4)    # 0.08
    L.add_edge("B", "S", delta=0.15, resistance=0.3)   # 0.045 — FAILS
    # Outer cycle: A→C→D→A (more expensive)
    L.add_edge("A", "C", delta=0.5, resistance=0.7)    # 0.35
    L.add_edge("C", "D", delta=0.3, resistance=0.5)    # 0.15
    L.add_edge("D", "A", delta=0.4, resistance=0.6)    # 0.24
    # Exit: B→GOAL
    L.add_edge("B", "GOAL", delta=0.15, resistance=0.4) # 0.06
    return DomainSpec(
        name="D8_nested_cycles",
        description="Nested cycles — failing cycle edge + exit to goal",
        landscape=L, start="S", goal="GOAL",
        execute_fn=_d8_execute,
        happy_path_length=3,
        topology_class="cyclic",
        node_count=6, edge_count=7,
    )


# ── D9: Wide DAG ──

def build_d9_wide_dag() -> DomainSpec:
    """5 parallel paths S→Ai→M→GOAL. Pure DAG, no cycles."""
    L = Landscape()
    for i in range(1, 6):
        d = 0.2 + i * 0.05
        r = 0.3 + i * 0.1
        L.add_edge("S", f"A{i}", delta=d, resistance=r)
        L.add_edge(f"A{i}", "M", delta=d, resistance=r)
    L.add_edge("M", "GOAL", delta=0.1, resistance=0.2)
    return DomainSpec(
        name="D9_wide_dag",
        description="Wide DAG — 5 parallel paths converging to goal",
        landscape=L, start="S", goal="GOAL",
        execute_fn=_all_success,
        happy_path_length=3,
        topology_class="dag",
        node_count=8, edge_count=11,
    )


# ── D10: Bottleneck Funnel ──

def _d10_execute(source: str, target: str) -> Outcome:
    """Dead-end edge S→X fails — forces controller to learn."""
    if source == "S" and target == "X":
        return Outcome.FAILURE
    return Outcome.SUCCESS


def build_d10_bottleneck() -> DomainSpec:
    """Single decoy dead-end + bottleneck forward path.

    S→X (0.06) is cheapest but dead-end AND FAILS.
    After DEAD_END escalation + failure-increased R,
    revisit penalty makes S→A (0.12) win.
    """
    L = Landscape()
    # Decoy: attractive but dead, and FAILS
    L.add_edge("S", "X", delta=0.2, resistance=0.3)    # 0.06
    L.add_state("X")  # dead end
    # Forward: through bottleneck
    L.add_edge("S", "A", delta=0.3, resistance=0.4)    # 0.12
    L.add_edge("A", "B", delta=0.3, resistance=0.8)    # 0.24 — bottleneck
    L.add_edge("B", "C", delta=0.2, resistance=0.3)    # 0.06
    L.add_edge("C", "GOAL", delta=0.1, resistance=0.2) # 0.02
    return DomainSpec(
        name="D10_bottleneck_funnel",
        description="Bottleneck funnel — failing dead-end + chokepoint",
        landscape=L, start="S", goal="GOAL",
        execute_fn=_d10_execute,
        happy_path_length=4,
        topology_class="bottleneck",
        node_count=6, edge_count=5,
    )


# ══════════════════════════════════════════════
# All Domains
# ══════════════════════════════════════════════

ALL_DOMAINS = [
    build_d1_linear_chain,
    build_d2_diamond,
    build_d3_gordian_trap,
    build_d4_greedy_trap,
    build_d5_grid_detour,
    build_d6_multigoal_star,
    build_d7_invoice,
    build_d8_nested_cycles,
    build_d9_wide_dag,
    build_d10_bottleneck,
]


def build_all_domains() -> List[DomainSpec]:
    """Build all 10 benchmark domains."""
    return [builder() for builder in ALL_DOMAINS]


# ══════════════════════════════════════════════
# Benchmark Runner
# ══════════════════════════════════════════════

def run_domain(
    spec: DomainSpec,
    max_cycles: int = 50,
) -> DomainResult:
    """Run E₀ controller on one domain with default parameters.

    Key invariant: NO domain-specific tuning.
    Same alpha, same recent_k, same mode — for all 10 domains.
    """
    ctrl = E0Controller(
        spec.landscape,
        spec.execute_fn,
        alpha=2.0,
        recent_k=3,
    )
    trace = ctrl.run(spec.start, max_cycles=max_cycles, goal=spec.goal)
    metrics = trace.metrics()

    goal_reached = spec.goal in trace.path

    ev = evaluate_run(
        path=trace.path,
        steps=len(trace.steps),
        escalation_count=int(metrics["escalation_count"]),
        revisit_count=int(metrics["revisit_count"]),
        success_rate=metrics["success_rate"],
        avg_tension=metrics["avg_tension"],
        total_tension=float(trace.total_tension),
        reached_goal=goal_reached,
        happy_path_length=spec.happy_path_length,
    )

    return DomainResult(
        domain=spec.name,
        goal_reached=goal_reached,
        steps=len(trace.steps),
        rating=ev.rating,
        success_rate=round(metrics["success_rate"], 3),
        escalations=int(metrics["escalation_count"]),
        revisits=int(metrics["revisit_count"]),
        efficiency=ev.goal_reach_efficiency,
        avg_tension=round(metrics["avg_tension"], 4),
        unique_states=int(metrics["unique_states"]),
        evaluation=ev,
    )


def run_benchmark(max_cycles: int = 50) -> List[DomainResult]:
    """Run all 10 domains and collect results."""
    domains = build_all_domains()
    return [run_domain(spec, max_cycles=max_cycles) for spec in domains]


# ══════════════════════════════════════════════
# Output
# ══════════════════════════════════════════════

def print_results(results: List[DomainResult]) -> None:
    """Pretty-print benchmark results table."""
    print("\n" + "=" * 90)
    print("  E₀ Domain-Invariance Benchmark — 10 Domains, 1 Controller")
    print("=" * 90)
    header = (
        f"{'Domain':<28} {'Goal':>4} {'Steps':>5} {'Rate':>5} "
        f"{'Esc':>3} {'Rev':>3} {'Eff':>5} {'Tens':>6} {'Rate':>4}"
    )
    print(header)
    print("-" * 90)
    for r in results:
        goal_str = "✓" if r.goal_reached else "✗"
        print(
            f"{r.domain:<28} {goal_str:>4} {r.steps:>5} "
            f"{r.success_rate:>5.1%} {r.escalations:>3} {r.revisits:>3} "
            f"{r.efficiency:>5.2f} {r.avg_tension:>6.3f}  {r.rating:>2}"
        )
    print("-" * 90)

    # Summary
    all_reached = all(r.goal_reached for r in results)
    ratings = [r.rating for r in results]
    worst = max(ratings, key=lambda x: "ABCDF".index(x))
    print(f"\n  All goals reached: {'YES' if all_reached else 'NO'}")
    print(f"  Worst rating:      {worst}")
    print(f"  Domain-invariant:  {'YES' if all_reached and worst <= 'C' else 'NO'}")
    print()


def results_to_dict(results: List[DomainResult]) -> Dict:
    """Convert results to serializable dict."""
    return {
        "benchmark": "domain_invariance_v1",
        "domains": len(results),
        "all_goals_reached": all(r.goal_reached for r in results),
        "worst_rating": max(
            (r.rating for r in results),
            key=lambda x: "ABCDF".index(x),
        ),
        "results": [
            {
                "domain": r.domain,
                "goal_reached": r.goal_reached,
                "steps": r.steps,
                "rating": r.rating,
                "success_rate": r.success_rate,
                "escalations": r.escalations,
                "revisits": r.revisits,
                "efficiency": r.efficiency,
                "avg_tension": r.avg_tension,
                "unique_states": r.unique_states,
            }
            for r in results
        ],
    }


# ══════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════

if __name__ == "__main__":
    results = run_benchmark()
    if "--json" in sys.argv:
        print(json.dumps(results_to_dict(results), indent=2))
    else:
        print_results(results)
