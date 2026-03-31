"""
Attractor Universality Experiment
==================================
Open Question #5: Does every uniformly-initialized landscape develop
a gravitational center?  Or is this specific to domains with inherent
optionality gradients (like chess's central squares)?

Part 1 — Original Topology:
  Keep each domain's edge structure, uniformize Δ/R₀.
  Result: 3/10 attractor, but all are trivial (goal-sink or junction).
  Conclusion: asymmetric topology predetermines the "attractor".

Part 2 — Fully Connected Topology:
  Replace each domain's edges with fully_connected(states).
  Same execute_fn (differential feedback preserved).
  Tests: does differential feedback alone create attractors
  when topology provides zero structural privilege?

Attractor metric:
  concentration = max_incoming_load / total_incoming_load
  uniform_baseline = 1/N_states
  attractor_ratio = concentration / uniform_baseline
  has_attractor iff attractor_ratio > 2.0

Usage:
  py -3 -m e0_controller.explore_attractor_universality
"""

from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Tuple

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller, RunTrace
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
# Configuration
# ══════════════════════════════════════════════

N_RUNS = 20          # repeated navigations per domain
UNIFORM_DELTA = 0.5
UNIFORM_R0 = 1.0


# ══════════════════════════════════════════════
# Attractor Metrics
# ══════════════════════════════════════════════

@dataclass
class StateMetrics:
    """Attractor metrics for a single state."""
    state: str
    incoming_load: float = 0.0
    incoming_quality: float = 0.0   # load-weighted mean quality
    visit_count: int = 0
    outgoing_load: float = 0.0


@dataclass
class DomainAttractorResult:
    """Attractor analysis for one domain."""
    domain: str
    n_states: int
    n_edges: int
    n_runs_completed: int
    total_steps: int
    goal_reached_count: int
    state_metrics: List[StateMetrics]
    # Derived
    top_attractor: str = ""
    concentration: float = 0.0        # max_incoming / total_incoming
    uniform_baseline: float = 0.0     # 1/N (expected if no attractor)
    attractor_ratio: float = 0.0      # concentration / uniform_baseline
    has_attractor: bool = False        # concentration > 2× uniform


def uniformize_landscape(spec: DomainSpec) -> None:
    """Set all edges to uniform Δ and R₀, keeping topology."""
    for edge in spec.landscape.edges:
        spec.landscape.adjust_delta(edge.source, edge.target, UNIFORM_DELTA)
        spec.landscape.adjust_base_resistance(edge.source, edge.target, UNIFORM_R0)


def analyze_domain(spec: DomainSpec, mode: str = "original") -> DomainAttractorResult:
    """Run one domain and compute attractor metrics.

    mode: "original" — keep topology, uniformize Δ/R₀
          "fully_connected" — replace topology with fully_connected
    """

    if mode == "fully_connected":
        states = sorted(spec.landscape.states)
        spec.landscape = Landscape.fully_connected(
            states, delta=UNIFORM_DELTA, resistance=UNIFORM_R0,
        )
    else:
        # 1. Uniformize
        uniformize_landscape(spec)
    L = spec.landscape
    H = L.historization

    # 2. Run N times, accumulating historization
    ctrl = E0Controller(L, spec.execute_fn)
    total_steps = 0
    goal_reached = 0
    visit_counts: Dict[str, int] = defaultdict(int)

    for _ in range(N_RUNS):
        trace = ctrl.run(spec.start, goal=spec.goal, max_cycles=50)
        total_steps += len(trace.steps)
        # Count visits
        visit_counts[spec.start] += 1
        for step in trace.steps:
            visit_counts[step.target] += 1
        # Check if goal reached
        if trace.steps and trace.steps[-1].target == spec.goal:
            goal_reached += 1

    # 3. Compute per-state metrics
    states = sorted(L.states)
    metrics: Dict[str, StateMetrics] = {s: StateMetrics(state=s) for s in states}

    for edge in L.edges:
        load = H.trace_load(edge)
        quality = H.trace_quality(edge)
        if load > 1e-12:
            m = metrics[edge.target]
            m.incoming_load += load
            # Accumulate for weighted mean (will normalize later)
            m.incoming_quality += quality * load
            # Also track outgoing
            metrics[edge.source].outgoing_load += load

    # Normalize incoming_quality to weighted mean
    for m in metrics.values():
        if m.incoming_load > 1e-12:
            m.incoming_quality /= m.incoming_load
        m.visit_count = visit_counts.get(m.state, 0)

    # 4. Compute concentration
    state_list = sorted(metrics.values(), key=lambda m: m.incoming_load, reverse=True)
    total_incoming = sum(m.incoming_load for m in state_list)
    n = len(states)
    uniform_baseline = 1.0 / n if n > 0 else 0.0

    if total_incoming > 1e-12:
        concentration = state_list[0].incoming_load / total_incoming
        top = state_list[0].state
    else:
        concentration = 0.0
        top = "(none)"

    ratio = concentration / uniform_baseline if uniform_baseline > 0 else 0.0

    return DomainAttractorResult(
        domain=spec.domain if hasattr(spec, 'domain') else spec.name,
        n_states=n,
        n_edges=len(L.edges),
        n_runs_completed=N_RUNS,
        total_steps=total_steps,
        goal_reached_count=goal_reached,
        state_metrics=state_list,
        top_attractor=top,
        concentration=concentration,
        uniform_baseline=uniform_baseline,
        attractor_ratio=ratio,
        has_attractor=ratio > 2.0,
    )


# ══════════════════════════════════════════════
# Domain Builders
# ══════════════════════════════════════════════

ALL_BUILDERS = [
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


# ══════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════

def run_experiment(mode: str = "original") -> List[DomainAttractorResult]:
    results = []
    for builder in ALL_BUILDERS:
        spec = builder()
        result = analyze_domain(spec, mode=mode)
        results.append(result)
    return results


def print_summary(results: List[DomainAttractorResult],
                  title: str = "ATTRACTOR UNIVERSALITY EXPERIMENT",
                  mode: str = "original") -> None:
    print("=" * 90)
    print(title)
    print(f"Config: N_RUNS={N_RUNS}, uniform Δ={UNIFORM_DELTA}, R₀={UNIFORM_R0}, mode={mode}")
    print("=" * 90)
    print()

    # Summary table
    header = f"{'Domain':<25} {'States':>6} {'Edges':>6} {'Steps':>6} {'Goal%':>6} {'Top Attractor':<15} {'Conc':>6} {'1/N':>6} {'Ratio':>6} {'Attr?':>5}"
    print(header)
    print("-" * len(header))

    attractor_count = 0
    for r in results:
        goal_pct = f"{100 * r.goal_reached_count / r.n_runs_completed:.0f}%" if r.n_runs_completed > 0 else "n/a"
        flag = "YES" if r.has_attractor else "no"
        if r.has_attractor:
            attractor_count += 1
        print(
            f"{r.domain:<25} {r.n_states:>6} {r.n_edges:>6} {r.total_steps:>6} "
            f"{goal_pct:>6} {r.top_attractor:<15} {r.concentration:>6.3f} "
            f"{r.uniform_baseline:>6.3f} {r.attractor_ratio:>6.1f} {flag:>5}"
        )

    print()
    print(f"Attractor emerged in {attractor_count}/{len(results)} domains "
          f"(threshold: concentration > 2× uniform baseline)")
    print()

    # Detailed per-domain breakdown: top 5 states
    for r in results:
        print(f"─── {r.domain} ({r.n_states} states, {r.n_edges} edges) ───")
        print(f"    Total steps: {r.total_steps}, Goal reached: {r.goal_reached_count}/{r.n_runs_completed}")
        print(f"    {'State':<15} {'In-Load':>8} {'In-Qual':>8} {'Out-Load':>8} {'Visits':>7}")
        for m in r.state_metrics[:5]:
            print(f"    {m.state:<15} {m.incoming_load:>8.3f} {m.incoming_quality:>+8.3f} "
                  f"{m.outgoing_load:>8.3f} {m.visit_count:>7}")
        if len(r.state_metrics) > 5:
            rest = r.state_metrics[5:]
            rest_load = sum(m.incoming_load for m in rest)
            print(f"    {'... (' + str(len(rest)) + ' more)':<15} {rest_load:>8.3f}")
        print()


def _print_verdict(results: List[DomainAttractorResult], label: str) -> None:
    universal = all(r.has_attractor for r in results)
    if universal:
        print(f"{label}: Attractor formation is UNIVERSAL across all 10 domains.")
    else:
        without = [r.domain for r in results if not r.has_attractor]
        with_attr = [r.domain for r in results if r.has_attractor]
        print(f"{label}: Attractor formation is CONDITIONAL.")
        print(f"  With attractor ({len(with_attr)}): {', '.join(with_attr)}")
        print(f"  Without ({len(without)}): {', '.join(without)}")


def main():
    # ── Part 1: Original topology, uniform Δ/R₀ ──
    results1 = run_experiment(mode="original")
    print_summary(results1,
                  title="PART 1 — ORIGINAL TOPOLOGY, UNIFORM INIT",
                  mode="original")
    _print_verdict(results1, "PART 1")

    print("\n" + "━" * 90 + "\n")

    # ── Part 2: Fully connected topology ──
    results2 = run_experiment(mode="fully_connected")
    print_summary(results2,
                  title="PART 2 — FULLY CONNECTED TOPOLOGY",
                  mode="fully_connected")
    _print_verdict(results2, "PART 2")

    # ── Comparison ──
    print("\n" + "━" * 90)
    print("COMPARISON: Original Topology vs Fully Connected")
    print("━" * 90)
    header = f"{'Domain':<25} {'Orig Ratio':>10} {'Orig Top':<12} {'FC Ratio':>10} {'FC Top':<12} {'Feedback':>8}"
    print(header)
    print("-" * len(header))

    # Domains with differential execute_fn
    differential = {"D3_gordian_trap", "D6_multigoal_star", "D7_invoice_process",
                    "D8_nested_cycles", "D10_bottleneck_funnel"}

    for r1, r2 in zip(results1, results2):
        fb = "diff" if r1.domain in differential else "all_ok"
        print(f"{r1.domain:<25} {r1.attractor_ratio:>10.1f} {r1.top_attractor:<12} "
              f"{r2.attractor_ratio:>10.1f} {r2.top_attractor:<12} {fb:>8}")

    print()
    # Key insight
    fc_diff = [(r2, r1) for r1, r2 in zip(results1, results2)
               if r1.domain in differential]
    fc_diff_attr = [r for r, _ in fc_diff if r.has_attractor]
    fc_allok = [(r2, r1) for r1, r2 in zip(results1, results2)
                if r1.domain not in differential]
    fc_allok_attr = [r for r, _ in fc_allok if r.has_attractor]

    print(f"Fully connected + differential feedback: "
          f"{len(fc_diff_attr)}/{len(fc_diff)} with attractor")
    print(f"Fully connected + all_success:           "
          f"{len(fc_allok_attr)}/{len(fc_allok)} with attractor")


if __name__ == "__main__":
    main()
