"""
Convergence Speed Experiment
==============================
Open Question #1: How many interactions until the strategy profile stabilizes?

Method:
  After each controller episode (start → goal navigation), snapshot the
  strategy_profile and compute two convergence metrics:
    1. Quality drift: mean |Δq(e)| across all observed edges
    2. Rank stability: Kendall tau correlation of edge quality ordering

  Tested across:
    (a) Deterministic C53 domains (D3, D7, D8, D10)
    (b) Stochastic corridor (C77)
    (c) ρ sensitivity: compare ρ ∈ {0.8, 0.9, 0.95, 0.99}

  Theoretical baseline: For a single edge visited every step with
  constant outcome, trace reaches 95% of steady state at:
      t_95 = log(0.05) / log(ρ)
      ρ=0.9 → t_95 ≈ 28 visits

Usage:
  py -3 -m e0_controller.explore_convergence_speed
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller
from e0_controller.historization import Historization
from e0_controller.benchmark_domain_invariance import (
    DomainSpec,
    build_d3_gordian_trap,
    build_d7_invoice,
    build_d8_nested_cycles,
    build_d10_bottleneck,
)


# ══════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════

N_EPISODES = 60


# ══════════════════════════════════════════════
# Convergence Metrics
# ══════════════════════════════════════════════

@dataclass
class ProfileSnapshot:
    """Strategy profile at a point in time."""
    episode: int
    tau: int                     # global time
    qualities: Dict[Edge, float] # edge → trace_quality
    loads: Dict[Edge, float]     # edge → trace_load
    rank_order: List[Edge]       # edges sorted by quality desc


@dataclass
class EpisodeMetrics:
    """Convergence metrics for one episode transition."""
    episode: int
    tau: int
    steps: int
    goal_reached: bool
    quality_drift: float       # mean |Δq(e)| vs previous
    max_drift: float           # max |Δq(e)| for any edge
    rank_kendall: float        # rank correlation with previous (1.0 = identical)
    active_edges: int          # edges with load > 0
    total_load: float          # sum of all trace loads


def snapshot_profile(hist: Historization, episode: int) -> ProfileSnapshot:
    """Take a snapshot of the current strategy profile."""
    profile = hist.strategy_profile()
    qualities = {e: q for e, q, _l in profile}
    loads = {e: l for e, _q, l in profile}
    rank_order = [e for e, _q, _l in profile]
    return ProfileSnapshot(
        episode=episode,
        tau=hist.tau,
        qualities=qualities,
        loads=loads,
        rank_order=rank_order,
    )


def compute_metrics(
    prev: ProfileSnapshot,
    curr: ProfileSnapshot,
    steps: int,
    goal_reached: bool,
) -> EpisodeMetrics:
    """Compute convergence metrics between two consecutive snapshots."""
    # All edges observed in either snapshot
    all_edges = set(prev.qualities.keys()) | set(curr.qualities.keys())

    if not all_edges:
        return EpisodeMetrics(
            episode=curr.episode, tau=curr.tau, steps=steps,
            goal_reached=goal_reached,
            quality_drift=0.0, max_drift=0.0, rank_kendall=1.0,
            active_edges=0, total_load=0.0,
        )

    # Quality drift
    drifts = []
    for e in all_edges:
        q_prev = prev.qualities.get(e, 0.0)
        q_curr = curr.qualities.get(e, 0.0)
        drifts.append(abs(q_curr - q_prev))

    quality_drift = sum(drifts) / len(drifts)
    max_drift = max(drifts)

    # Rank stability (simplified Kendall tau via concordant pairs)
    rank_kendall = _kendall_rank_correlation(prev.rank_order, curr.rank_order)

    return EpisodeMetrics(
        episode=curr.episode,
        tau=curr.tau,
        steps=steps,
        goal_reached=goal_reached,
        quality_drift=quality_drift,
        max_drift=max_drift,
        rank_kendall=rank_kendall,
        active_edges=len(curr.qualities),
        total_load=sum(curr.loads.values()),
    )


def _kendall_rank_correlation(order_a: List[Edge], order_b: List[Edge]) -> float:
    """Simplified rank correlation: fraction of pairwise comparisons that agree.

    Returns 1.0 if rankings are identical, 0.0 if completely reversed.
    Handles different edge sets by using the intersection.
    """
    common = [e for e in order_a if e in set(order_b)]
    if len(common) < 2:
        return 1.0

    # Position maps
    pos_a = {e: i for i, e in enumerate(order_a)}
    pos_b = {e: i for i, e in enumerate(order_b)}

    concordant = 0
    total = 0
    for i in range(len(common)):
        for j in range(i + 1, len(common)):
            e1, e2 = common[i], common[j]
            da = pos_a[e1] - pos_a[e2]
            db = pos_b[e1] - pos_b[e2]
            if da * db > 0:
                concordant += 1
            total += 1

    return concordant / total if total > 0 else 1.0


# ══════════════════════════════════════════════
# Core Runner
# ══════════════════════════════════════════════

def run_convergence_analysis(
    spec: DomainSpec,
    n_episodes: int = N_EPISODES,
    rho_override: Optional[float] = None,
) -> List[EpisodeMetrics]:
    """Run episodes and track convergence metrics."""
    if rho_override is not None:
        spec.landscape.historization.rho = rho_override

    ctrl = E0Controller(spec.landscape, spec.execute_fn)
    hist = ctrl.landscape.historization

    # Initial snapshot (empty)
    prev_snap = snapshot_profile(hist, -1)
    metrics = []

    for ep in range(n_episodes):
        trace = ctrl.run(spec.start, goal=spec.goal, max_cycles=80)
        steps = len(trace.steps)
        reached = (trace.steps and trace.steps[-1].target == spec.goal) if trace.steps else False

        curr_snap = snapshot_profile(hist, ep)
        m = compute_metrics(prev_snap, curr_snap, steps, reached)
        metrics.append(m)
        prev_snap = curr_snap

    return metrics


def find_stabilization_episode(
    metrics: List[EpisodeMetrics],
    drift_threshold: float = 0.01,
    window: int = 5,
) -> int:
    """Find first episode where quality_drift < threshold for `window` consecutive episodes.

    Returns episode index, or -1 if never stabilizes.
    """
    count = 0
    for m in metrics:
        if m.quality_drift < drift_threshold:
            count += 1
            if count >= window:
                return m.episode - window + 1
        else:
            count = 0
    return -1


# ══════════════════════════════════════════════
# Part 1: Deterministic C53 Domains
# ══════════════════════════════════════════════

def run_part1():
    print("=" * 95)
    print("PART 1: CONVERGENCE IN DETERMINISTIC C53 DOMAINS")
    print(f"Config: N_EPISODES={N_EPISODES}")
    print("=" * 95)

    builders = [
        ("D3_gordian", build_d3_gordian_trap),
        ("D7_invoice", build_d7_invoice),
        ("D8_cycles", build_d8_nested_cycles),
        ("D10_bottleneck", build_d10_bottleneck),
    ]

    for name, builder in builders:
        spec = builder()
        metrics = run_convergence_analysis(spec)

        stab_strict = find_stabilization_episode(metrics, drift_threshold=0.01)
        stab_loose = find_stabilization_episode(metrics, drift_threshold=0.05)

        print(f"\n─── {name} ({spec.node_count} nodes, {spec.edge_count} edges, "
              f"happy path: {spec.happy_path_length}) ───")
        print(f"    {'Ep':>3}  {'τ':>5}  {'Steps':>5}  {'Drift':>7}  "
              f"{'MaxΔq':>7}  {'Kendall':>7}  {'Edges':>5}  {'Load':>7}")
        print(f"    {'---':>3}  {'---':>5}  {'-----':>5}  {'------':>7}  "
              f"{'------':>7}  {'-------':>7}  {'-----':>5}  {'------':>7}")

        for m in metrics:
            marker = ""
            if m.quality_drift < 0.01:
                marker = " ●"  # stable
            elif m.quality_drift < 0.05:
                marker = " ○"  # near-stable
            print(f"    {m.episode:>3}  {m.tau:>5}  {m.steps:>5}  "
                  f"{m.quality_drift:>7.4f}  {m.max_drift:>7.4f}  "
                  f"{m.rank_kendall:>7.3f}  {m.active_edges:>5}  "
                  f"{m.total_load:>7.2f}{marker}")

        stab_s = str(stab_strict) if stab_strict >= 0 else "never"
        stab_l = str(stab_loose) if stab_loose >= 0 else "never"
        print(f"    Stabilization (drift<0.01): episode {stab_s}")
        print(f"    Stabilization (drift<0.05): episode {stab_l}")


# ══════════════════════════════════════════════
# Part 2: Stochastic Corridor
# ══════════════════════════════════════════════

def build_stochastic_corridor(
    n_levels: int = 8,
    n_dead_ends: int = 3,
    p_correct: float = 0.85,
    p_wrong: float = 0.30,
    rng: Optional[random.Random] = None,
) -> DomainSpec:
    """Same as C77 branching corridor."""
    if rng is None:
        rng = random.Random(42)

    ls = Landscape()
    correct_edges = set()
    path_nodes = [f"N{i}" for i in range(n_levels)] + ["GOAL"]

    all_edges = []
    for i in range(len(path_nodes) - 1):
        all_edges.append((path_nodes[i], path_nodes[i + 1], True))
        correct_edges.add((path_nodes[i], path_nodes[i + 1]))
    for i in range(n_levels):
        for d in range(n_dead_ends):
            dead = f"D{i}_{d}"
            all_edges.append((path_nodes[i], dead, False))

    rng.shuffle(all_edges)
    for src, tgt, _ in all_edges:
        ls.add_edge(src, tgt, delta=0.5, resistance=1.0)

    exec_rng = random.Random(rng.random())

    def execute_fn(source: str, target: str) -> Outcome:
        if (source, target) in correct_edges:
            return Outcome.SUCCESS if exec_rng.random() < p_correct else Outcome.FAILURE
        elif target.startswith("D"):
            return Outcome.SUCCESS if exec_rng.random() < p_wrong else Outcome.FAILURE
        return Outcome.SUCCESS

    total_nodes = n_levels + 1 + n_levels * n_dead_ends
    total_edges = n_levels + n_levels * n_dead_ends

    return DomainSpec(
        name=f"Stochastic_{n_levels}L_{n_dead_ends}D",
        description=f"Stochastic {n_levels}-level corridor",
        landscape=ls,
        start="N0",
        goal="GOAL",
        execute_fn=execute_fn,
        happy_path_length=n_levels,
        topology_class="tree",
        node_count=total_nodes,
        edge_count=total_edges,
    )


def run_part2():
    N_TRIALS = 10

    print("\n\n" + "=" * 95)
    print("PART 2: CONVERGENCE IN STOCHASTIC CORRIDOR (8L×3D)")
    print(f"Config: N_EPISODES={N_EPISODES}, N_TRIALS={N_TRIALS}")
    print("=" * 95)

    # Collect per-episode averages across trials
    all_drifts = [[] for _ in range(N_EPISODES)]
    all_ranks = [[] for _ in range(N_EPISODES)]
    all_steps = [[] for _ in range(N_EPISODES)]

    for trial in range(N_TRIALS):
        spec = build_stochastic_corridor(rng=random.Random(7000 + trial))
        metrics = run_convergence_analysis(spec)
        for m in metrics:
            all_drifts[m.episode].append(m.quality_drift)
            all_ranks[m.episode].append(m.rank_kendall)
            all_steps[m.episode].append(m.steps)

    print(f"\n    {'Ep':>3}  {'Steps μ':>7}  {'Drift μ':>7}  {'Kendall μ':>9}")
    print(f"    {'---':>3}  {'------':>7}  {'------':>7}  {'---------':>9}")

    for ep in range(N_EPISODES):
        avg_drift = sum(all_drifts[ep]) / len(all_drifts[ep])
        avg_rank = sum(all_ranks[ep]) / len(all_ranks[ep])
        avg_steps = sum(all_steps[ep]) / len(all_steps[ep])
        marker = ""
        if avg_drift < 0.01:
            marker = " ●"
        elif avg_drift < 0.05:
            marker = " ○"
        print(f"    {ep:>3}  {avg_steps:>7.1f}  {avg_drift:>7.4f}  "
              f"{avg_rank:>9.3f}{marker}")

    # Summary
    early_drift = sum(sum(all_drifts[ep]) / len(all_drifts[ep]) for ep in range(5)) / 5
    late_drift = sum(sum(all_drifts[ep]) / len(all_drifts[ep]) for ep in range(N_EPISODES-5, N_EPISODES)) / 5
    print(f"\n    Mean drift (first 5 eps): {early_drift:.4f}")
    print(f"    Mean drift (last 5 eps):  {late_drift:.4f}")
    print(f"    Drift reduction ratio:    {early_drift/late_drift:.2f}×" if late_drift > 0 else "")


# ══════════════════════════════════════════════
# Part 3: ρ Sensitivity Analysis
# ══════════════════════════════════════════════

def run_part3():
    print("\n\n" + "=" * 95)
    print("PART 3: ρ SENSITIVITY — DECAY RATE vs CONVERGENCE SPEED")
    print(f"Config: N_EPISODES={N_EPISODES}, Domain: D7_invoice")
    print("=" * 95)

    rho_values = [0.80, 0.90, 0.95, 0.99]

    # Theoretical bounds
    print("\n    Theoretical t_95 (single edge, constant outcome):")
    for rho in rho_values:
        t95 = math.log(0.05) / math.log(rho)
        print(f"      ρ={rho:.2f} → t_95 = {t95:.1f} visits per edge")

    print()

    header = f"    {'ρ':>4}  {'Stab@0.01':>9}  {'Stab@0.05':>9}  {'Drift@5':>8}  {'Drift@50':>8}  {'Load@60':>8}"
    print(header)
    print("    " + "-" * (len(header) - 4))

    for rho in rho_values:
        spec = build_d7_invoice()
        metrics = run_convergence_analysis(spec, rho_override=rho)

        stab_strict = find_stabilization_episode(metrics, drift_threshold=0.01)
        stab_loose = find_stabilization_episode(metrics, drift_threshold=0.05)

        drift_5 = metrics[4].quality_drift if len(metrics) > 4 else 0
        drift_50 = metrics[49].quality_drift if len(metrics) > 49 else 0
        load_60 = metrics[-1].total_load

        stab_s = str(stab_strict) if stab_strict >= 0 else "never"
        stab_l = str(stab_loose) if stab_loose >= 0 else "never"
        print(f"    {rho:.2f}  {stab_s:>9}  {stab_l:>9}  "
              f"{drift_5:>8.4f}  {drift_50:>8.4f}  {load_60:>8.2f}")

    # Part 3b: ρ sensitivity in stochastic domain
    print(f"\n    ρ sensitivity in stochastic corridor (8L×3D, 5 trials each):")
    print(f"    {'ρ':>4}  {'Drift@5':>8}  {'Drift@50':>8}  {'Converges':>9}")
    print("    " + "-" * 35)

    for rho in rho_values:
        drifts_5 = []
        drifts_50 = []
        for trial in range(5):
            spec = build_stochastic_corridor(rng=random.Random(8000 + trial))
            metrics = run_convergence_analysis(spec, rho_override=rho)
            drifts_5.append(metrics[4].quality_drift if len(metrics) > 4 else 0)
            drifts_50.append(metrics[49].quality_drift if len(metrics) > 49 else 0)
        avg_d5 = sum(drifts_5) / len(drifts_5)
        avg_d50 = sum(drifts_50) / len(drifts_50)
        converges = "yes" if avg_d50 < 0.01 else "partial" if avg_d50 < 0.05 else "no"
        print(f"    {rho:.2f}  {avg_d5:>8.4f}  {avg_d50:>8.4f}  {converges:>9}")


# ══════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════

def main():
    run_part1()
    run_part2()
    run_part3()


if __name__ == "__main__":
    main()
