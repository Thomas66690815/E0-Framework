"""
C61 — Multiverse Benchmark: Cross-Domain Coupling
=====================================================
Couples pairs of structurally different C53 domains and observes:

  1. Do coupled systems converge? (How many turns until stale?)
  2. Does divergence pressure break convergence?
  3. Does the coupling topology grow?
  4. How does novelty rate differ across domain pairings?

The key question: Does structural diversity between coupled systems
delay or prevent convergence?  And when convergence happens, does
divergence pressure successfully restart exploration?

Pairings are chosen to maximize structural contrast:
  P1: Linear (D1) × Gordian Trap (D3)    — simple vs. decoy
  P2: Diamond (D2) × Wide DAG (D9)       — 2-path vs. 5-path
  P3: Grid (D5) × Bottleneck (D10)       — spatial vs. funneled
  P4: Star (D6) × Nested Cycles (D8)     — fan-out vs. loops
  P5: Greedy Trap (D4) × Invoice (D7)    — abstract vs. real-world

Each pairing uses a custom turn function that runs the controller
in the active universe, then transfers discovered topology into
the passive universe as hypothesis edges — simulating structural
knowledge exchange between systems.

Usage:
  from e0_controller.benchmark_multiverse import run_multiverse_benchmark
  result = run_multiverse_benchmark()
  print(result.summary())
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller, RunTrace
from e0_controller.multiverse import (
    MultiverseController,
    MultiverseResult,
    Universe,
)
from e0_controller.benchmark_domain_invariance import (
    DomainSpec,
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
)


# ══════════════════════════════════════════════
# Result types
# ══════════════════════════════════════════════

@dataclass
class PairingResult:
    """Result of one cross-domain pairing."""
    name: str
    domain_a: str
    domain_b: str
    total_turns: int
    total_novelty: int
    novelty_rate: float
    converged: bool
    convergence_turn: Optional[int]
    divergence_count: int
    novelty_edges_added: int
    coupling_edge_count: int


@dataclass
class MultiverseBenchmarkResult:
    """Complete cross-domain benchmark."""
    pairings: List[PairingResult] = field(default_factory=list)

    @property
    def avg_novelty_rate(self) -> float:
        if not self.pairings:
            return 0.0
        return sum(p.novelty_rate for p in self.pairings) / len(self.pairings)

    @property
    def convergence_count(self) -> int:
        return sum(1 for p in self.pairings if p.converged)

    @property
    def divergence_total(self) -> int:
        return sum(p.divergence_count for p in self.pairings)

    def summary(self) -> str:
        lines = [
            "Multiverse Cross-Domain Benchmark",
            "=" * 65,
            f"{'Pairing':<35} {'Nov':>4} {'Rate':>6} "
            f"{'Conv?':>5} {'Div':>4} {'CplEdge':>7}",
            "-" * 65,
        ]
        for p in self.pairings:
            conv = f"T{p.convergence_turn}" if p.converged else "—"
            lines.append(
                f"{p.name:<35} "
                f"{p.total_novelty:>3}/{p.total_turns:<1} "
                f"{p.novelty_rate:>5.0%} "
                f"{conv:>5} "
                f"{p.divergence_count:>4} "
                f"{p.coupling_edge_count:>7}"
            )
        lines.append("-" * 65)
        lines.append(
            f"Avg novelty rate: {self.avg_novelty_rate:.0%}  |  "
            f"Convergences: {self.convergence_count}/{len(self.pairings)}  |  "
            f"Total divergence: {self.divergence_total}"
        )
        return "\n".join(lines)


# ══════════════════════════════════════════════
# Turn function: knowledge exchange
# ══════════════════════════════════════════════

def knowledge_exchange_turn(active: Universe, passive: Universe) -> None:
    """Simulate structural knowledge exchange between two systems.

    1. Run controller in active universe (explore its landscape)
    2. Find edges in active that are absent in passive
    3. Transfer a subset as hypothesis edges (high Δ, moderate R₀)

    This models: "System A navigates its domain, System B learns
    about A's topology and can use those structural patterns."
    """
    # Run active universe
    ctrl = E0Controller(
        active.landscape, active.execute_fn,
        alpha=2.0, recent_k=3,
    )
    ctrl.run(active.start, max_cycles=5, goal=active.goal)

    # Collect edges from active that passive doesn't have
    active_edges = set(active.landscape._delta.keys())
    passive_edges = set(passive.landscape._delta.keys())
    passive_states = passive.landscape._states

    transferable = []
    for edge in active_edges:
        # Only transfer if both states exist in passive, or if target
        # state doesn't exist yet (novel structural insight)
        if edge not in passive_edges:
            transferable.append(edge)

    # Transfer up to 2 edges per turn (limit information flow)
    for edge in transferable[:2]:
        delta = active.landscape._delta[edge]
        r0 = active.landscape._R0[edge]
        # Add missing states first
        if edge.source not in passive_states:
            passive.landscape.add_state(edge.source)
        if edge.target not in passive_states:
            passive.landscape.add_state(edge.target)
        passive.landscape.add_edge(
            edge.source, edge.target,
            delta=delta,
            resistance=r0 * 1.5,  # higher R₀ = treat as hypothesis
        )


# ══════════════════════════════════════════════
# Domain to Universe conversion
# ══════════════════════════════════════════════

def _spec_to_universe(spec: DomainSpec) -> Universe:
    """Convert a DomainSpec into a Universe."""
    return Universe(
        name=spec.name,
        landscape=spec.landscape,
        execute_fn=spec.execute_fn,
        start=spec.start,
        goal=spec.goal,
    )


# ══════════════════════════════════════════════
# Single pairing run
# ══════════════════════════════════════════════

def run_pairing(
    name: str,
    builder_a: Callable,
    builder_b: Callable,
    max_turns: int = 12,
    convergence_window: int = 3,
) -> PairingResult:
    """Run one cross-domain pairing."""
    spec_a = builder_a()
    spec_b = builder_b()
    u_a = _spec_to_universe(spec_a)
    u_b = _spec_to_universe(spec_b)

    ctrl = MultiverseController(
        u_a, u_b,
        convergence_window=convergence_window,
    )
    mv_result = ctrl.run(
        max_turns=max_turns,
        turn_fn=knowledge_exchange_turn,
    )

    return PairingResult(
        name=name,
        domain_a=spec_a.name,
        domain_b=spec_b.name,
        total_turns=mv_result.total_turns,
        total_novelty=mv_result.total_novelty,
        novelty_rate=mv_result.novelty_rate,
        converged=mv_result.converged,
        convergence_turn=mv_result.convergence_turn,
        divergence_count=mv_result.divergence_count,
        novelty_edges_added=mv_result.novelty_edges_added,
        coupling_edge_count=len(ctrl.coupling._delta),
    )


# ══════════════════════════════════════════════
# 5 Pairings
# ══════════════════════════════════════════════

PAIRINGS = [
    ("P1: Linear × Gordian", build_d1_linear_chain, build_d3_gordian_trap),
    ("P2: Diamond × Wide DAG", build_d2_diamond, build_d9_wide_dag),
    ("P3: Grid × Bottleneck", build_d5_grid_detour, build_d10_bottleneck),
    ("P4: Star × Nested Cycles", build_d6_multigoal_star, build_d8_nested_cycles),
    ("P5: Greedy Trap × Invoice", build_d4_greedy_trap, build_d7_invoice),
]


# ══════════════════════════════════════════════
# Full benchmark
# ══════════════════════════════════════════════

def run_multiverse_benchmark(
    max_turns: int = 12,
    convergence_window: int = 3,
) -> MultiverseBenchmarkResult:
    """Run all 5 cross-domain pairings."""
    result = MultiverseBenchmarkResult()
    for name, builder_a, builder_b in PAIRINGS:
        pr = run_pairing(
            name, builder_a, builder_b,
            max_turns=max_turns,
            convergence_window=convergence_window,
        )
        result.pairings.append(pr)
    return result
