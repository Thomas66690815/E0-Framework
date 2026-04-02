"""
Dream Mode — End-to-End Exploration (C112)
==========================================
Demonstrates the full Dream Mode pipeline across multiple domain types:

  1. Register N domains (from benchmark_domain_invariance)
  2. Run each domain for several episodes (inscription phase)
  3. Run dream cycles (passive cross-domain observation)
  4. Use dream bridges to help a stuck domain
  5. Measure: equivalence count, bridge proposals, acceleration

Metrics measured:
  - Equivalence precision: do similar domains pair more than dissimilar?
  - Transfer acceleration: does a stuck domain benefit from dream bridges?
  - Self-correction: does FAILURE feedback reduce bad bridges?
  - Dream Landscape convergence: does the DL stabilize after N cycles?

Usage:
  py -3 -m e0_controller.explore_dream_mode
"""

from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

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
    build_d8_nested_cycles,
)
from e0_controller.dream_mode import (
    DreamObserver,
    DreamCycleResult,
    DreamBridgeResult,
    dream_readiness,
    propose_bridges,
    make_dream_peer_fn,
)


# ══════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════

N_INSCRIPTION_RUNS = 15     # runs per domain to build historization
N_DREAM_CYCLES = 5          # passive observation cycles
READINESS_THRESHOLD = 0.5   # lower than default for exploration


# ══════════════════════════════════════════════
# Results
# ══════════════════════════════════════════════

@dataclass
class DomainInscriptionResult:
    """Inscription results for one domain."""
    name: str
    runs: int
    final_readiness: float
    edges: int
    goal_reached_count: int


@dataclass
class DreamCycleSummary:
    """Summary of one dream cycle."""
    cycle: int
    domains_observed: int
    domains_skipped: int
    equivalences_found: int
    equivalences_new: int
    dl_states: int
    dl_edges: int


@dataclass
class BridgeExperiment:
    """Result of bridge hypothesis experiment."""
    target_domain: str
    partner_domains: List[str]
    equivalences_used: int
    proposals: int
    edges_added: int
    goal_reached_before: bool
    goal_reached_after: bool


@dataclass
class SelfCorrectionExperiment:
    """Result of self-correction experiment (P3)."""
    domain: str
    bridges_before_failure: int
    bridges_after_failure: int
    quality_before: float
    quality_after: float


# ══════════════════════════════════════════════
# Phase 1: Domain inscription
# ══════════════════════════════════════════════

def inscribe_domain(spec: DomainSpec, n_runs: int) -> DomainInscriptionResult:
    """Run a domain N times to build historization."""
    goal_count = 0
    for _ in range(n_runs):
        ctrl = E0Controller(spec.landscape, spec.execute_fn)
        trace = ctrl.run(spec.start, goal=spec.goal)
        if trace.path[-1] == spec.goal:
            goal_count += 1

    readiness = dream_readiness(spec.landscape)
    return DomainInscriptionResult(
        name=spec.name,
        runs=n_runs,
        final_readiness=readiness,
        edges=len(spec.landscape.edges),
        goal_reached_count=goal_count,
    )


# ══════════════════════════════════════════════
# Phase 2: Dream cycles
# ══════════════════════════════════════════════

def run_dream_cycles(
    observer: DreamObserver,
    n_cycles: int,
) -> List[DreamCycleSummary]:
    """Run N dream cycles and collect summaries."""
    summaries = []
    for i in range(n_cycles):
        result = observer.dream_cycle()
        summaries.append(DreamCycleSummary(
            cycle=i + 1,
            domains_observed=len(result.domains_observed),
            domains_skipped=len(result.domains_skipped),
            equivalences_found=result.equivalences_found,
            equivalences_new=result.equivalences_new,
            dl_states=result.dream_landscape_states,
            dl_edges=result.dream_landscape_edges,
        ))
    return summaries


# ══════════════════════════════════════════════
# Phase 3: Bridge experiment
# ══════════════════════════════════════════════

def run_bridge_experiment(
    observer: DreamObserver,
    target_name: str,
    target_spec: DomainSpec,
) -> BridgeExperiment:
    """Test whether dream bridges help a domain stuck at frontier."""
    # Check if goal reachable before bridges
    ctrl_before = E0Controller(target_spec.landscape, target_spec.execute_fn)
    trace_before = ctrl_before.run(target_spec.start, goal=target_spec.goal)
    goal_before = trace_before.path[-1] == target_spec.goal

    # Provide SUCCESS feedback on all dream edges to simulate validated eqs
    dl = observer.dream_landscape
    if dl:
        for e in dl.edges:
            for _ in range(3):
                observer.feedback(e.source, e.target, Outcome.SUCCESS)

    # Propose bridges
    result = propose_bridges(
        observer,
        target_name,
        target_spec.start,
        target_spec.goal,
        max_bridges=3,
    )

    # Check if goal reachable after bridges
    ctrl_after = E0Controller(target_spec.landscape, target_spec.execute_fn)
    trace_after = ctrl_after.run(target_spec.start, goal=target_spec.goal)
    goal_after = trace_after.path[-1] == target_spec.goal

    return BridgeExperiment(
        target_domain=target_name,
        partner_domains=[b.partner_domain for b in result.bridges],
        equivalences_used=result.equivalences_used,
        proposals=result.total_proposals,
        edges_added=result.total_edges_added,
        goal_reached_before=goal_before,
        goal_reached_after=goal_after,
    )


# ══════════════════════════════════════════════
# Phase 4: Self-correction experiment (P3)
# ══════════════════════════════════════════════

def run_self_correction(
    observer: DreamObserver,
    target_name: str,
    target_spec: DomainSpec,
) -> SelfCorrectionExperiment:
    """Test P3: FAILURE feedback reduces bridges."""
    # Bridges before failure
    result_before = propose_bridges(
        observer, target_name, target_spec.start, target_spec.goal,
        min_quality=0.0,
    )

    eqs_before = observer.equivalences_for(target_name)
    q_before = eqs_before[0]["trace_quality"] if eqs_before else 0.0

    # Heavy FAILURE feedback
    dl = observer.dream_landscape
    if dl:
        for e in dl.edges:
            for _ in range(20):
                observer.feedback(e.source, e.target, Outcome.FAILURE)

    eqs_after = observer.equivalences_for(target_name)
    q_after = eqs_after[0]["trace_quality"] if eqs_after else 0.0

    result_after = propose_bridges(
        observer, target_name, target_spec.start, target_spec.goal,
        min_quality=0.0,
    )

    return SelfCorrectionExperiment(
        domain=target_name,
        bridges_before_failure=result_before.domains_consulted,
        bridges_after_failure=result_after.domains_consulted,
        quality_before=q_before,
        quality_after=q_after,
    )


# ══════════════════════════════════════════════
# Phase 5: Equivalence precision analysis
# ══════════════════════════════════════════════

def analyze_equivalence_precision(observer: DreamObserver) -> Dict[str, any]:
    """Analyze whether similar domains pair more than dissimilar ones."""
    dl = observer.dream_landscape
    if not dl:
        return {"total_edges": 0, "pairs": {}}

    pair_counts: Dict[str, int] = defaultdict(int)
    for e in dl.edges:
        src_domain = e.source.split(":")[0]
        tgt_domain = e.target.split(":")[0]
        key = f"{min(src_domain, tgt_domain)}<>{max(src_domain, tgt_domain)}"
        pair_counts[key] += 1

    return {
        "total_edges": len(dl.edges),
        "total_states": len(dl.states),
        "pairs": dict(pair_counts),
    }


# ══════════════════════════════════════════════
# Main exploration
# ══════════════════════════════════════════════

def main():
    print("=" * 70)
    print("Dream Mode — End-to-End Exploration (C112)")
    print("=" * 70)

    # Build domains
    domains = {
        "D1_chain": build_d1_linear_chain(),
        "D2_diamond": build_d2_diamond(),
        "D3_gordian": build_d3_gordian_trap(),
        "D4_greedy": build_d4_greedy_trap(),
        "D5_grid": build_d5_grid_detour(),
        "D8_cycles": build_d8_nested_cycles(),
    }

    # ── Phase 1: Inscription ──────────────────────────────────────
    print(f"\n{'─' * 70}")
    print("Phase 1: Domain Inscription")
    print(f"{'─' * 70}")
    print(f"Running {N_INSCRIPTION_RUNS} episodes per domain...\n")

    inscription_results = {}
    for name, spec in domains.items():
        result = inscribe_domain(spec, N_INSCRIPTION_RUNS)
        inscription_results[name] = result
        print(f"  {name:15s}  edges={result.edges:3d}  "
              f"readiness={result.final_readiness:.3f}  "
              f"goal={result.goal_reached_count}/{result.runs}")

    # ── Phase 2: Dream Cycles ─────────────────────────────────────
    print(f"\n{'─' * 70}")
    print("Phase 2: Dream Cycles (passive observation)")
    print(f"{'─' * 70}")

    observer = DreamObserver(readiness_threshold=READINESS_THRESHOLD)
    for name, spec in domains.items():
        observer.register(name, spec.landscape)

    summaries = run_dream_cycles(observer, N_DREAM_CYCLES)

    print(f"\n  {'Cycle':>5s}  {'Obs':>4s}  {'Skip':>4s}  "
          f"{'Found':>6s}  {'New':>5s}  {'DL_S':>5s}  {'DL_E':>5s}")
    for s in summaries:
        print(f"  {s.cycle:5d}  {s.domains_observed:4d}  "
              f"{s.domains_skipped:4d}  {s.equivalences_found:6d}  "
              f"{s.equivalences_new:5d}  {s.dl_states:5d}  {s.dl_edges:5d}")

    # ── Phase 3: Equivalence Precision ────────────────────────────
    print(f"\n{'─' * 70}")
    print("Phase 3: Equivalence Precision")
    print(f"{'─' * 70}")

    precision = analyze_equivalence_precision(observer)
    print(f"\n  Dream Landscape: {precision['total_states']} states, "
          f"{precision['total_edges']} edges")
    print(f"  Domain pair distribution:")
    for pair, count in sorted(precision["pairs"].items(),
                               key=lambda x: -x[1]):
        print(f"    {pair:35s}  {count:4d} edges")

    # ── Phase 4: Bridge Experiment ────────────────────────────────
    print(f"\n{'─' * 70}")
    print("Phase 4: Bridge Hypothesis Experiment")
    print(f"{'─' * 70}")

    # Pick D3 (gordian trap) as target — it's the hardest for isolated E₀
    target_name = "D3_gordian"
    bridge_result = run_bridge_experiment(
        observer, target_name, domains[target_name],
    )
    print(f"\n  Target: {bridge_result.target_domain}")
    print(f"  Partners consulted: {bridge_result.partner_domains}")
    print(f"  Equivalences used: {bridge_result.equivalences_used}")
    print(f"  Proposals generated: {bridge_result.proposals}")
    print(f"  Edges added: {bridge_result.edges_added}")
    print(f"  Goal reached before: {bridge_result.goal_reached_before}")
    print(f"  Goal reached after:  {bridge_result.goal_reached_after}")

    # ── Phase 5: Self-Correction (P3) ─────────────────────────────
    print(f"\n{'─' * 70}")
    print("Phase 5: Self-Correction (P3)")
    print(f"{'─' * 70}")

    # Use a fresh observer for clean self-correction test
    observer2 = DreamObserver(readiness_threshold=READINESS_THRESHOLD)
    for name, spec in domains.items():
        observer2.register(name, spec.landscape)
    run_dream_cycles(observer2, 2)

    # Positive feedback first
    dl2 = observer2.dream_landscape
    if dl2:
        for e in dl2.edges:
            for _ in range(3):
                observer2.feedback(e.source, e.target, Outcome.SUCCESS)

    correction = run_self_correction(
        observer2, "D4_greedy", domains["D4_greedy"],
    )
    print(f"\n  Domain: {correction.domain}")
    print(f"  Quality before FAILURE: {correction.quality_before:+.3f}")
    print(f"  Quality after FAILURE:  {correction.quality_after:+.3f}")
    print(f"  Bridges before: {correction.bridges_before_failure}")
    print(f"  Bridges after:  {correction.bridges_after_failure}")
    if correction.quality_after < correction.quality_before:
        print("  → P3 confirmed: FAILURE feedback reduces trust")
    else:
        print("  → P3 inconclusive (quality did not decrease)")

    # ── Phase 6: Dream Peer Integration ───────────────────────────
    print(f"\n{'─' * 70}")
    print("Phase 6: Dream Peer Integration (E0Controller)")
    print(f"{'─' * 70}")

    # Fresh observer with clean feedback
    observer3 = DreamObserver(readiness_threshold=READINESS_THRESHOLD)
    for name, spec in domains.items():
        observer3.register(name, spec.landscape)
    run_dream_cycles(observer3, 3)

    # Positive feedback for peer experiment
    dl3 = observer3.dream_landscape
    if dl3:
        for e in dl3.edges:
            for _ in range(3):
                observer3.feedback(e.source, e.target, Outcome.SUCCESS)

    # Run D2 with dream peer_fn
    d2 = domains["D2_diamond"]
    peer_fn = make_dream_peer_fn(observer3, "D2_diamond", d2.goal)
    ctrl_with_peer = E0Controller(
        d2.landscape, d2.execute_fn, peer_fn=peer_fn,
    )
    trace_peer = ctrl_with_peer.run(d2.start, goal=d2.goal)
    print(f"\n  D2 with dream peer_fn:")
    print(f"    Path: {' → '.join(trace_peer.path)}")
    print(f"    Steps: {len(trace_peer.steps)}")
    print(f"    Goal reached: {trace_peer.path[-1] == d2.goal}")

    # ── Summary ───────────────────────────────────────────────────
    print(f"\n{'═' * 70}")
    print("Summary")
    print(f"{'═' * 70}")

    dl_final = observer.dream_landscape
    print(f"\n  Domains registered:     {len(domains)}")
    print(f"  Inscription runs/domain: {N_INSCRIPTION_RUNS}")
    print(f"  Dream cycles:           {N_DREAM_CYCLES}")
    if dl_final:
        print(f"  Dream Landscape states: {len(dl_final.states)}")
        print(f"  Dream Landscape edges:  {len(dl_final.edges)}")
    print(f"  Domain pairs found:     {len(precision['pairs'])}")
    print(f"  Bridge proposals:       {bridge_result.proposals}")
    print(f"  P3 self-correction:     "
          f"{'confirmed' if correction.quality_after < correction.quality_before else 'inconclusive'}")

    # Convergence check: do new equivalences decrease over cycles?
    if len(summaries) >= 2:
        first_new = summaries[0].equivalences_new
        last_new = summaries[-1].equivalences_new
        print(f"  DL convergence:         new_eq cycle1={first_new}, "
              f"cycle{len(summaries)}={last_new} "
              f"({'converging' if last_new <= first_new else 'growing'})")

    print(f"\n{'═' * 70}")
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
