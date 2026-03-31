"""
Transfer Learning Experiment
==============================
Open Question #3: Can a strategy_profile from one domain seed a new
landscape for faster convergence?

Part 1: C53 benchmark domains (deterministic) — baseline test.
Part 2: Stochastic grid domain (20+ states, probabilistic failures) —
         the real test, because stochastic outcomes create a learning
         curve that transfer can actually accelerate.

Key metric: "episodes to convergence" (first episode where steps ≤
happy_path_length and stays there for all remaining episodes).

Usage:
  py -3 -m e0_controller.explore_transfer_learning
"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller
from e0_controller.benchmark_domain_invariance import (
    DomainSpec,
    build_d3_gordian_trap,
    build_d4_greedy_trap,
    build_d6_multigoal_star,
    build_d7_invoice,
    build_d8_nested_cycles,
    build_d10_bottleneck,
)


# ══════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════

N_EPISODES = 20       # learning episodes per condition
SOURCE_EPISODES = 10  # episodes to build source experience
SEED_STRENGTH = 3.0   # how many "virtual successes" to inject per edge


# ══════════════════════════════════════════════
# Transfer Result
# ══════════════════════════════════════════════

@dataclass
class EpisodeRecord:
    """One navigation episode."""
    episode: int
    steps: int
    goal_reached: bool


@dataclass
class TransferResult:
    """Result for one domain, cold vs warm."""
    domain: str
    happy_path: int
    cold_episodes: List[EpisodeRecord]
    warm_episodes: List[EpisodeRecord]
    transferred_edges: int
    # Derived
    cold_convergence: int = -1    # episode where steps == happy_path (-1 = never)
    warm_convergence: int = -1
    cold_mean_steps: float = 0.0
    warm_mean_steps: float = 0.0
    speedup: float = 0.0         # cold_mean / warm_mean


# ══════════════════════════════════════════════
# Core Logic
# ══════════════════════════════════════════════

def run_episodes(
    spec: DomainSpec,
    n_episodes: int,
) -> Tuple[List[EpisodeRecord], E0Controller]:
    """Run n_episodes of navigation and return learning curve + controller."""
    ctrl = E0Controller(spec.landscape, spec.execute_fn)
    records = []
    for ep in range(n_episodes):
        trace = ctrl.run(spec.start, goal=spec.goal, max_cycles=50)
        steps = len(trace.steps)
        reached = (trace.steps and trace.steps[-1].target == spec.goal) if trace.steps else False
        records.append(EpisodeRecord(episode=ep, steps=steps, goal_reached=reached))
    return records, ctrl


def inject_strategy(
    target_hist,
    strategy: List[Tuple[Edge, float, float]],
    strength: float = SEED_STRENGTH,
) -> int:
    """Inject strategy_profile into a fresh Historization.

    For each edge in the profile with positive quality, add 'strength'
    virtual successes.  For negative quality, add 'strength' virtual failures.
    This biases the Historization without running actual episodes.

    Returns: number of edges injected.
    """
    count = 0
    for edge, quality, load in strategy:
        if quality > 0.1:
            # Inject successes
            for _ in range(int(strength)):
                target_hist.update(edge, Outcome.SUCCESS)
            count += 1
        elif quality < -0.1:
            # Inject failures (teach avoidance)
            for _ in range(int(strength)):
                target_hist.update(edge, Outcome.FAILURE)
            count += 1
    return count


def find_convergence(
    episodes: List[EpisodeRecord],
    target_steps: int,
) -> int:
    """Find first episode where steps <= target_steps and stays there.

    Returns episode index, or -1 if never converges.
    """
    for i, ep in enumerate(episodes):
        if ep.steps <= target_steps and ep.goal_reached:
            # Check if it stays converged for remaining episodes
            remaining = episodes[i:]
            if all(r.steps <= target_steps + 1 and r.goal_reached for r in remaining):
                return i
    return -1


def run_transfer_experiment(
    builder: Callable[[], DomainSpec],
) -> TransferResult:
    """Run cold vs warm comparison for one domain."""

    # ── Phase 1: COLD run (learning from scratch) ──
    cold_spec = builder()
    cold_episodes, cold_ctrl = run_episodes(cold_spec, N_EPISODES)

    # ── Phase 2: Build source experience (separate run) ──
    source_spec = builder()
    _, source_ctrl = run_episodes(source_spec, SOURCE_EPISODES)
    strategy = source_ctrl.landscape.historization.strategy_profile()

    # ── Phase 3: WARM run (with transferred knowledge) ──
    warm_spec = builder()
    transferred = inject_strategy(
        warm_spec.landscape.historization,
        strategy,
        strength=SEED_STRENGTH,
    )
    warm_episodes, warm_ctrl = run_episodes(warm_spec, N_EPISODES)

    # ── Analyze ──
    happy = cold_spec.happy_path_length
    cold_conv = find_convergence(cold_episodes, happy)
    warm_conv = find_convergence(warm_episodes, happy)

    cold_mean = sum(e.steps for e in cold_episodes) / len(cold_episodes)
    warm_mean = sum(e.steps for e in warm_episodes) / len(warm_episodes)
    speedup = cold_mean / warm_mean if warm_mean > 0 else 0.0

    return TransferResult(
        domain=cold_spec.name,
        happy_path=happy,
        cold_episodes=cold_episodes,
        warm_episodes=warm_episodes,
        transferred_edges=transferred,
        cold_convergence=cold_conv,
        warm_convergence=warm_conv,
        cold_mean_steps=cold_mean,
        warm_mean_steps=warm_mean,
        speedup=speedup,
    )


# ══════════════════════════════════════════════
# Domains
# ══════════════════════════════════════════════

DOMAIN_BUILDERS = [
    build_d3_gordian_trap,
    build_d4_greedy_trap,
    build_d6_multigoal_star,
    build_d7_invoice,
    build_d8_nested_cycles,
    build_d10_bottleneck,
]


# ══════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════

def print_results(results: List[TransferResult], title: str = "TRANSFER LEARNING EXPERIMENT") -> None:
    print("=" * 95)
    print(title)
    print(f"Config: N_EPISODES={N_EPISODES}, SOURCE_EPISODES={SOURCE_EPISODES}, "
          f"SEED_STRENGTH={SEED_STRENGTH}")
    print("=" * 95)
    print()

    # Summary table
    header = (f"{'Domain':<22} {'Happy':>5} {'Xfer':>4} "
              f"{'Cold μ':>7} {'Warm μ':>7} {'Speedup':>7} "
              f"{'Cold Conv':>9} {'Warm Conv':>9}")
    print(header)
    print("-" * len(header))

    for r in results:
        cold_c = str(r.cold_convergence) if r.cold_convergence >= 0 else "never"
        warm_c = str(r.warm_convergence) if r.warm_convergence >= 0 else "never"
        print(f"{r.domain:<22} {r.happy_path:>5} {r.transferred_edges:>4} "
              f"{r.cold_mean_steps:>7.1f} {r.warm_mean_steps:>7.1f} "
              f"{r.speedup:>6.2f}× "
              f"{cold_c:>9} {warm_c:>9}")

    # Per-domain learning curves
    print()
    for r in results:
        print(f"─── {r.domain} (happy path: {r.happy_path}, "
              f"transferred: {r.transferred_edges} edges) ───")
        print(f"    {'Ep':>3}  {'Cold':>5} {'C-Goal':>6}  {'Warm':>5} {'W-Goal':>6}")
        for i in range(len(r.cold_episodes)):
            ce = r.cold_episodes[i]
            we = r.warm_episodes[i]
            c_g = "✓" if ce.goal_reached else "✗"
            w_g = "✓" if we.goal_reached else "✗"
            marker = ""
            if we.steps < ce.steps:
                marker = " ◀ warm faster"
            elif ce.steps < we.steps:
                marker = " ◀ cold faster"
            print(f"    {i:>3}  {ce.steps:>5} {c_g:>6}  {we.steps:>5} {w_g:>6}{marker}")
        print()

    # Verdict
    improved = sum(1 for r in results if r.speedup > 1.05)
    hurt = sum(1 for r in results if r.speedup < 0.95)
    neutral = len(results) - improved - hurt
    print(f"Transfer improved: {improved}/{len(results)} domains")
    print(f"Transfer neutral:  {neutral}/{len(results)} domains")
    print(f"Transfer hurt:     {hurt}/{len(results)} domains")

    faster_conv = sum(1 for r in results
                      if r.warm_convergence >= 0
                      and (r.cold_convergence < 0 or r.warm_convergence < r.cold_convergence))
    print(f"Faster convergence: {faster_conv}/{len(results)} domains")


def main():
    # ════════════════════════════
    # Part 1: Deterministic C53 domains
    # ════════════════════════════
    results_det = []
    for builder in DOMAIN_BUILDERS:
        result = run_transfer_experiment(builder)
        results_det.append(result)
    print_results(results_det, title="PART 1: DETERMINISTIC C53 DOMAINS")

    # ════════════════════════════
    # Part 2: Stochastic grid domain
    # ════════════════════════════
    print()
    print()
    run_stochastic_experiment()


# ══════════════════════════════════════════════
# Part 2: Branching Corridor (dead ends create real step-count cost)
# ══════════════════════════════════════════════

def build_branching_corridor(
    n_levels: int = 5,
    n_dead_ends: int = 4,
    p_correct: float = 0.85,
    p_wrong: float = 0.30,
    rng: Optional[random.Random] = None,
) -> DomainSpec:
    """Build a corridor with dead-end branches at each level.

    Structure (n_levels=5, n_dead_ends=4):
        N0 → N1 → N2 → N3 → N4 → GOAL   (correct path: 5 steps)
        N0 → D0_0, D0_1, D0_2, D0_3      (dead ends at level 0)
        N1 → D1_0, D1_1, D1_2, D1_3      (dead ends at level 1)
        ...

    Dead-end exploration costs: each wrong choice = move to dead end
    (1 step) + DEAD_END escalation jump back (1 step) = 2 extra steps.

    Stochastic execute_fn:
      – Correct-path edges: P(SUCCESS) = p_correct (e.g. 0.85)
      – Dead-end edges:     P(SUCCESS) = p_wrong   (e.g. 0.30)
      – Escalation jumps:   always SUCCESS (free)

    With stochastic outcomes, the controller needs multiple episodes to
    build reliable trace quality for edge discrimination.  Transfer of
    "which edges are correct" accelerates convergence.
    """
    if rng is None:
        rng = random.Random(42)

    ls = Landscape()
    correct_edges = set()
    path_nodes = [f"N{i}" for i in range(n_levels)] + ["GOAL"]

    # Collect all edges, then shuffle to avoid insertion-order tiebreak bias
    all_edges = []

    # Correct path
    for i in range(len(path_nodes) - 1):
        all_edges.append((path_nodes[i], path_nodes[i + 1], True))
        correct_edges.add((path_nodes[i], path_nodes[i + 1]))

    # Dead-end branches at each level
    for i in range(n_levels):
        for d in range(n_dead_ends):
            dead = f"D{i}_{d}"
            all_edges.append((path_nodes[i], dead, False))

    # Shuffle so that min() tiebreak is random, not insertion-order biased
    rng.shuffle(all_edges)
    for src, tgt, _is_correct in all_edges:
        ls.add_edge(src, tgt, delta=0.5, resistance=1.0)

    exec_rng = random.Random(rng.random())

    def execute_fn(source: str, target: str) -> Outcome:
        if (source, target) in correct_edges:
            return Outcome.SUCCESS if exec_rng.random() < p_correct else Outcome.FAILURE
        elif target.startswith("D"):
            return Outcome.SUCCESS if exec_rng.random() < p_wrong else Outcome.FAILURE
        else:
            # Escalation jumps, unexpected edges — always succeed
            return Outcome.SUCCESS

    total_nodes = n_levels + 1 + n_levels * n_dead_ends  # path + GOAL + dead ends
    total_edges = n_levels + n_levels * n_dead_ends       # correct + dead-end

    return DomainSpec(
        name=f"Corridor_{n_levels}L_{n_dead_ends}D",
        description=f"{n_levels}-level corridor with {n_dead_ends} dead ends per level",
        landscape=ls,
        start=path_nodes[0],
        goal="GOAL",
        execute_fn=execute_fn,
        happy_path_length=n_levels,
        topology_class="tree",
        node_count=total_nodes,
        edge_count=total_edges,
    )


def run_stochastic_experiment():
    """Part 2: Branching corridor with stochastic outcomes.

    Dead-end branches create genuine step-count variation:
    each wrong choice costs 2+ steps (dead end + escalation jump).

    Stochastic execute_fn ensures learning takes multiple episodes:
    correct edges sometimes fail, wrong edges sometimes succeed.
    Transfer injects edge-quality knowledge, skipping the exploration.
    """
    N_TRIALS = 30
    N_EPS = 30
    N_SOURCE_EPS = 15

    # Corridor configs: (n_levels, n_dead_ends, label)
    configs = [
        (5, 4, "5L×4D"),
        (8, 3, "8L×3D"),
    ]

    print("=" * 95)
    print("PART 2: BRANCHING CORRIDOR (dead ends + stochastic outcomes)")
    print(f"Config: N_TRIALS={N_TRIALS}, EPISODES={N_EPS}, "
          f"SOURCE_EPS={N_SOURCE_EPS}, SEED_STRENGTH={SEED_STRENGTH}")
    print("=" * 95)

    for n_levels, n_dead_ends, label in configs:
        print(f"\n─── Corridor {label} (happy path: {n_levels} steps, "
              f"{n_dead_ends} dead ends/level, "
              f"{n_levels + n_levels * n_dead_ends} edges) ───\n")

        cold_curves = []
        warm_curves = []
        cold_failures_curves = []
        warm_failures_curves = []

        for trial in range(N_TRIALS):
            # COLD
            cold_spec = build_branching_corridor(
                n_levels, n_dead_ends, rng=random.Random(2000 + trial))
            cold_eps, cold_ctrl = run_stochastic_episodes(
                cold_spec, N_EPS, random.Random(3000 + trial))
            cold_curves.append([e.steps for e in cold_eps])
            cold_failures_curves.append([
                sum(1 for s in _get_trace_outcomes(cold_ctrl, cold_spec, ep_idx)
                    if s == Outcome.FAILURE)
                for ep_idx in range(N_EPS)
            ] if False else [0] * N_EPS)  # placeholder — we use steps

            # SOURCE (train)
            source_spec = build_branching_corridor(
                n_levels, n_dead_ends, rng=random.Random(2000 + trial))
            source_eps, source_ctrl = run_stochastic_episodes(
                source_spec, N_SOURCE_EPS, random.Random(4000 + trial))
            strategy = source_ctrl.landscape.historization.strategy_profile()

            # WARM (with transfer)
            warm_spec = build_branching_corridor(
                n_levels, n_dead_ends, rng=random.Random(2000 + trial))
            transferred = inject_strategy(
                warm_spec.landscape.historization, strategy, strength=SEED_STRENGTH)
            warm_eps, warm_ctrl = run_stochastic_episodes(
                warm_spec, N_EPS, random.Random(5000 + trial))
            warm_curves.append([e.steps for e in warm_eps])

        # Average curves
        avg_cold = [sum(cold_curves[t][ep] for t in range(N_TRIALS)) / N_TRIALS
                    for ep in range(N_EPS)]
        avg_warm = [sum(warm_curves[t][ep] for t in range(N_TRIALS)) / N_TRIALS
                    for ep in range(N_EPS)]

        # Print learning curves
        print(f"    {'Ep':>3}  {'Cold μ':>7}  {'Warm μ':>7}  {'Δ':>7}  {'Note'}")
        print(f"    {'---':>3}  {'------':>7}  {'------':>7}  {'-----':>7}")
        for ep in range(N_EPS):
            delta = avg_cold[ep] - avg_warm[ep]
            note = ""
            if delta > 1.0:
                note = "◀ warm faster"
            elif delta < -1.0:
                note = "◀ cold faster"
            print(f"    {ep:>3}  {avg_cold[ep]:>7.1f}  {avg_warm[ep]:>7.1f}  "
                  f"{delta:>+7.1f}  {note}")

        # Summary stats
        cold_mean = sum(avg_cold) / len(avg_cold)
        warm_mean = sum(avg_warm) / len(avg_warm)
        speedup = cold_mean / warm_mean if warm_mean > 0 else 0.0

        cold_first5 = sum(avg_cold[:5]) / 5
        warm_first5 = sum(avg_warm[:5]) / 5
        cold_last5 = sum(avg_cold[-5:]) / 5
        warm_last5 = sum(avg_warm[-5:]) / 5

        print(f"\n    Overall:      cold={cold_mean:.1f}  warm={warm_mean:.1f}  "
              f"speedup={speedup:.2f}×")
        print(f"    First 5 eps:  cold={cold_first5:.1f}  warm={warm_first5:.1f}  "
              f"speedup={cold_first5/warm_first5:.2f}×" if warm_first5 > 0 else "")
        print(f"    Last 5 eps:   cold={cold_last5:.1f}   warm={warm_last5:.1f}   "
              f"speedup={cold_last5/warm_last5:.2f}×" if warm_last5 > 0 else "")

        # Win/loss/draw per episode
        cold_wins = sum(1 for ep in range(N_EPS) if avg_cold[ep] < avg_warm[ep] - 0.5)
        warm_wins = sum(1 for ep in range(N_EPS) if avg_warm[ep] < avg_cold[ep] - 0.5)
        draws = N_EPS - cold_wins - warm_wins
        print(f"    Episodes:     warm wins {warm_wins}, cold wins {cold_wins}, "
              f"draws {draws} (of {N_EPS})")


def run_stochastic_episodes(
    spec: DomainSpec,
    n_episodes: int,
    rng: random.Random,
) -> Tuple[List[EpisodeRecord], E0Controller]:
    """Run episodes on a stochastic domain."""
    ctrl = E0Controller(spec.landscape, spec.execute_fn)
    records = []
    for ep in range(n_episodes):
        trace = ctrl.run(spec.start, goal=spec.goal, max_cycles=80)
        steps = len(trace.steps)
        reached = (trace.steps and trace.steps[-1].target == spec.goal) if trace.steps else False
        records.append(EpisodeRecord(episode=ep, steps=steps, goal_reached=reached))
    return records, ctrl


if __name__ == "__main__":
    main()
