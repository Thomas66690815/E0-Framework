"""
Landscape Size Scaling Experiment (C81)
========================================
Open Question #2: Does uniform initialization work for 50+ states,
or does the fully-connected edge count (N²) create noise?

Extended question (from cross-cognition with Gemini): E₀ scales not
through larger graphs, but through more cooperating agents with smaller
graphs.  When it gets too complex, ask someone who knows.

Part 1 — Solo scaling: N = 10, 25, 50, 100 states.
  Fully connected + differential feedback.
  Measures: goal-reach rate, mean steps, overload index.
  Expected: performance degrades as N² edges dilute signal.

Part 2 — Peer consultation (OVERLOADED mechanism):
  Same domains, but solo agent gets peer_fn from an experienced agent.
  Expected: peer consultation rescues large domains.

Part 3 — Hierarchical decomposition:
  N=100 split into K partitions with bridge nodes.
  Each partition has its own experienced sub-agent.
  Master agent navigates between partitions.
  Expected: decomposition restores small-graph performance.

Usage:
  py -3 -m e0_controller.explore_landscape_scaling
"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Set, Tuple

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller, EscalationType
from e0_controller.benchmark_domain_invariance import DomainSpec


# ══════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════

N_EPISODES = 30
N_TRIALS = 5


# ══════════════════════════════════════════════
# Domain Builder: Scalable Fully-Connected with Differential Feedback
# ══════════════════════════════════════════════

def build_scalable_domain(
    n_states: int,
    p_correct: float = 0.85,
    p_wrong: float = 0.30,
    rng: Optional[random.Random] = None,
) -> DomainSpec:
    """Build a fully-connected domain with N states and differential feedback.

    Structure:
      - N states labeled S0..S{N-2}, GOAL
      - Happy path: S0 → S1 → S2 → ... → S{N-2} → GOAL (length N-1)
      - Fully connected: N*(N-1) directed edges
      - Differential feedback:
          * Edges on the happy path: P(SUCCESS) = p_correct
          * Edges NOT on happy path: P(SUCCESS) = p_wrong
      - Start: S0, Goal: GOAL

    The happy path is a linear chain through all states.
    The challenge: with N*(N-1) edges, the N-1 correct edges are
    drowned in (N-1)*(N-1) wrong edges.  Signal-to-noise = 1/(N-1).
    """
    if rng is None:
        rng = random.Random(42)

    states = [f"S{i}" for i in range(n_states - 1)] + ["GOAL"]
    ls = Landscape.fully_connected(states, delta=0.5, resistance=1.0)

    # Happy path edges
    happy_path = set()
    for i in range(len(states) - 1):
        happy_path.add((states[i], states[i + 1]))

    exec_rng = random.Random(rng.random())

    def execute_fn(source: str, target: str) -> Outcome:
        if (source, target) in happy_path:
            return Outcome.SUCCESS if exec_rng.random() < p_correct else Outcome.FAILURE
        else:
            return Outcome.SUCCESS if exec_rng.random() < p_wrong else Outcome.FAILURE

    return DomainSpec(
        name=f"Scale_{n_states}",
        description=f"{n_states}-state fully-connected with differential feedback",
        landscape=ls,
        start=states[0],
        goal="GOAL",
        execute_fn=execute_fn,
        happy_path_length=n_states - 1,
        topology_class="fully_connected",
        node_count=n_states,
        edge_count=n_states * (n_states - 1),
    )


# ══════════════════════════════════════════════
# Metrics
# ══════════════════════════════════════════════

@dataclass
class ScalingResult:
    """Result for one scaling condition."""
    n_states: int
    n_edges: int
    condition: str         # "solo", "peer", "partitioned"
    goal_reached: int
    total_episodes: int
    mean_steps: float
    mean_steps_reached: float    # mean steps when goal WAS reached
    mean_overload_index: float   # average OI at first step
    peer_calls: int = 0
    learning_curve: List[float] = None  # mean steps per episode


def run_scaling_trial(
    spec: DomainSpec,
    n_episodes: int = N_EPISODES,
    peer_fn: Optional[Callable] = None,
    overload_threshold: float = 3.0,
) -> ScalingResult:
    """Run one trial and collect scaling metrics."""
    max_cycles = max(150, spec.happy_path_length * 5)
    ctrl = E0Controller(
        spec.landscape, spec.execute_fn,
        peer_fn=peer_fn,
        overload_threshold=overload_threshold,
    )

    goal_reached = 0
    total_steps = 0
    steps_when_reached = []
    oi_samples = []
    peer_calls = 0
    per_episode_steps = []

    for ep in range(n_episodes):
        trace = ctrl.run(spec.start, goal=spec.goal, max_cycles=max_cycles)
        steps = len(trace.steps)
        per_episode_steps.append(steps)
        total_steps += steps

        reached = (trace.steps and trace.steps[-1].target == spec.goal) if trace.steps else False
        if reached:
            goal_reached += 1
            steps_when_reached.append(steps)

        # Count OVERLOADED escalations
        for step in trace.steps:
            if step.escalation_type == EscalationType.OVERLOADED:
                peer_calls += 1

        # Sample OI at start
        neighbors = spec.landscape.admissible_neighbors(spec.start)
        if neighbors:
            oi = ctrl._overload_index(spec.start, neighbors)
            oi_samples.append(oi)

    mean_steps = total_steps / n_episodes if n_episodes > 0 else 0
    mean_reached = (sum(steps_when_reached) / len(steps_when_reached)
                    if steps_when_reached else float('inf'))
    mean_oi = sum(oi_samples) / len(oi_samples) if oi_samples else 0

    return ScalingResult(
        n_states=spec.node_count,
        n_edges=spec.edge_count,
        condition="solo",
        goal_reached=goal_reached,
        total_episodes=n_episodes,
        mean_steps=mean_steps,
        mean_steps_reached=mean_reached,
        mean_overload_index=mean_oi,
        peer_calls=peer_calls,
        learning_curve=per_episode_steps,
    )


# ══════════════════════════════════════════════
# Part 1: Solo Scaling
# ══════════════════════════════════════════════

SCALE_SIZES = [10, 25, 50, 100]


def run_solo_scaling():
    """Part 1: Single agent on increasing domain sizes."""
    print("=" * 100)
    print("PART 1: SOLO AGENT SCALING (fully connected, differential feedback)")
    print(f"Config: N_TRIALS={N_TRIALS}, N_EPISODES={N_EPISODES}, MAX_CYCLES=max(150, N*5)")
    print("=" * 100)

    all_results: Dict[int, List[ScalingResult]] = {}

    for n in SCALE_SIZES:
        trial_results = []
        for trial in range(N_TRIALS):
            spec = build_scalable_domain(n, rng=random.Random(1000 + trial))
            result = run_scaling_trial(spec)
            result.condition = "solo"
            trial_results.append(result)
        all_results[n] = trial_results

    # Summary table
    print(f"\n    {'N':>5}  {'Edges':>6}  {'Signal':>7}  {'Goal%':>6}  "
          f"{'Mean Steps':>10}  {'Steps|Goal':>10}  {'OI':>6}")
    print(f"    {'─'*5}  {'─'*6}  {'─'*7}  {'─'*6}  "
          f"{'─'*10}  {'─'*10}  {'─'*6}")

    for n in SCALE_SIZES:
        results = all_results[n]
        edges = n * (n - 1)
        signal = (n - 1) / edges  # happy-path edges / total edges
        goal_pct = sum(r.goal_reached for r in results) / sum(r.total_episodes for r in results)
        mean_s = sum(r.mean_steps for r in results) / len(results)
        mean_r = sum(r.mean_steps_reached for r in results) / len(results)
        mean_oi = sum(r.mean_overload_index for r in results) / len(results)

        reached_str = f"{mean_r:.1f}" if mean_r < float('inf') else "∞"
        print(f"    {n:>5}  {edges:>6}  {signal:>6.1%}  {goal_pct:>5.0%}  "
              f"{mean_s:>10.1f}  {reached_str:>10}  {mean_oi:>6.1f}")

    # Learning curves for each size
    for n in SCALE_SIZES:
        results = all_results[n]
        avg_curve = []
        for ep in range(N_EPISODES):
            ep_avg = sum(r.learning_curve[ep] for r in results) / len(results)
            avg_curve.append(ep_avg)
        print(f"\n    Learning curve N={n}:")
        for ep in range(0, N_EPISODES, 5):
            vals = avg_curve[ep:ep+5]
            line = f"      ep {ep:>2}-{ep+4:>2}: " + "  ".join(f"{v:>6.1f}" for v in vals)
            print(line)

    return all_results


# ══════════════════════════════════════════════
# Part 2: Peer Consultation (experienced oracle)
# ══════════════════════════════════════════════

def build_oracle_peer_fn(
    n_states: int,
    rng: Optional[random.Random] = None,
) -> Callable:
    """Build a peer_fn from a pre-trained "oracle" agent.

    The oracle runs SOURCE_EPS episodes on the same domain structure,
    then its strategy_profile is used to advise the peer.
    """
    SOURCE_EPS = 50

    # Train the oracle
    oracle_spec = build_scalable_domain(n_states, rng=rng)
    oracle_max = max(150, oracle_spec.happy_path_length * 5)
    oracle_ctrl = E0Controller(oracle_spec.landscape, oracle_spec.execute_fn)
    for _ in range(SOURCE_EPS):
        oracle_ctrl.run(oracle_spec.start, goal=oracle_spec.goal, max_cycles=oracle_max)

    oracle_H = oracle_ctrl.landscape.historization

    def peer_fn(landscape, current: str, neighbors: List[str]) -> Optional[str]:
        """Advise based on oracle's trace quality."""
        best_state = None
        best_quality = -2.0
        for nb in neighbors:
            edge = Edge(current, nb)
            q = oracle_H.trace_quality(edge)
            load = oracle_H.trace_load(edge)
            if load > 0.1 and q > best_quality:
                best_quality = q
                best_state = nb
        return best_state

    return peer_fn


def build_perfect_oracle_peer_fn(n_states: int) -> Callable:
    """Build a peer_fn with perfect happy-path knowledge.

    For N>=50, a trained oracle also fails (0% goal).  This 'perfect'
    oracle short-circuits training: it directly knows the happy path
    (S0->S1->S2->...->GOAL) and always recommends the next correct step.

    If perfect advice STILL can't rescue large domains, the scaling
    limit is structural, not knowledge-related.
    """
    happy_path = {}
    states = [f"S{i}" for i in range(n_states - 1)] + ["GOAL"]
    for i in range(len(states) - 1):
        happy_path[states[i]] = states[i + 1]

    def peer_fn(landscape, current: str, neighbors: List[str]) -> Optional[str]:
        next_state = happy_path.get(current)
        if next_state and next_state in neighbors:
            return next_state
        return None

    return peer_fn


def run_peer_scaling():
    """Part 2: Agent with oracle peer on increasing domain sizes.

    - N=10, 25: trained oracle (can learn these domains)
    - N=50, 100: perfect oracle (trained oracle also fails at 0%)
    """
    print("\n\n" + "=" * 100)
    print("PART 2: PEER CONSULTATION (OVERLOADED trigger)")
    print(f"Config: N_TRIALS={N_TRIALS}, N_EPISODES={N_EPISODES}, "
          f"overload_threshold=3.0")
    print("  N=10,25: trained oracle (50 eps)  |  N=50,100: perfect oracle")
    print("=" * 100)

    all_results: Dict[int, List[ScalingResult]] = {}

    for n in SCALE_SIZES:
        trial_results = []
        for trial in range(N_TRIALS):
            if n <= 25:
                # Trained oracle (can learn these sizes)
                oracle_rng = random.Random(2000 + trial)
                pfn = build_oracle_peer_fn(n, rng=oracle_rng)
            else:
                # Perfect oracle (trained oracle fails at N>=50)
                pfn = build_perfect_oracle_peer_fn(n)

            # Build fresh agent with peer_fn
            spec = build_scalable_domain(n, rng=random.Random(1000 + trial))
            result = run_scaling_trial(spec, peer_fn=pfn, overload_threshold=3.0)
            result.condition = "peer"
            trial_results.append(result)
        all_results[n] = trial_results

    # Summary table
    print(f"\n    {'N':>5}  {'Edges':>6}  {'Goal%':>6}  "
          f"{'Mean Steps':>10}  {'Steps|Goal':>10}  {'OI':>6}  {'Peer Calls':>10}")
    print(f"    {'─'*5}  {'─'*6}  {'─'*6}  "
          f"{'─'*10}  {'─'*10}  {'─'*6}  {'─'*10}")

    for n in SCALE_SIZES:
        results = all_results[n]
        edges = n * (n - 1)
        goal_pct = sum(r.goal_reached for r in results) / sum(r.total_episodes for r in results)
        mean_s = sum(r.mean_steps for r in results) / len(results)
        mean_r = sum(r.mean_steps_reached for r in results) / len(results)
        mean_oi = sum(r.mean_overload_index for r in results) / len(results)
        peer_c = sum(r.peer_calls for r in results) / len(results)

        reached_str = f"{mean_r:.1f}" if mean_r < float('inf') else "∞"
        print(f"    {n:>5}  {edges:>6}  {goal_pct:>5.0%}  "
              f"{mean_s:>10.1f}  {reached_str:>10}  {mean_oi:>6.1f}  {peer_c:>10.0f}")

    return all_results


# ══════════════════════════════════════════════
# Part 3: Hierarchical Decomposition
# ══════════════════════════════════════════════

def build_partitioned_domain(
    n_total: int = 100,
    n_partitions: int = 4,
    p_correct: float = 0.85,
    p_wrong: float = 0.30,
    rng: Optional[random.Random] = None,
) -> Tuple[DomainSpec, List[DomainSpec]]:
    """Build a partitioned domain: K sub-graphs connected by bridge edges.

    Structure:
      - n_total states split into n_partitions groups
      - Each partition is fully connected internally
      - Bridge edges connect last node of partition i to first node of partition i+1
      - Happy path goes through all partitions in order
      - GOAL is in the last partition

    Returns: (full_domain_spec, list_of_partition_specs)
    """
    if rng is None:
        rng = random.Random(42)

    partition_size = n_total // n_partitions
    partitions: List[List[str]] = []
    all_states = []

    for p in range(n_partitions):
        if p < n_partitions - 1:
            states = [f"P{p}_S{i}" for i in range(partition_size)]
        else:
            # Last partition includes GOAL
            states = [f"P{p}_S{i}" for i in range(partition_size - 1)] + ["GOAL"]
        partitions.append(states)
        all_states.extend(states)

    ls = Landscape()

    # Fully connected WITHIN each partition
    for partition_states in partitions:
        for s in partition_states:
            for t in partition_states:
                if s != t:
                    ls.add_edge(s, t, delta=0.5, resistance=1.0)

    # Bridge edges between partitions (bidirectional)
    bridge_edges = set()
    for p in range(n_partitions - 1):
        last = partitions[p][-1]
        first = partitions[p + 1][0]
        ls.add_edge(last, first, delta=0.5, resistance=1.0)
        ls.add_edge(first, last, delta=0.5, resistance=1.0)
        bridge_edges.add((last, first))

    # Happy path: linear through each partition
    happy_path = set()
    for partition_states in partitions:
        for i in range(len(partition_states) - 1):
            happy_path.add((partition_states[i], partition_states[i + 1]))
    # Add bridge edges to happy path
    for p in range(n_partitions - 1):
        happy_path.add((partitions[p][-1], partitions[p + 1][0]))

    exec_rng = random.Random(rng.random())

    def execute_fn(source: str, target: str) -> Outcome:
        if (source, target) in happy_path or (source, target) in bridge_edges:
            return Outcome.SUCCESS if exec_rng.random() < p_correct else Outcome.FAILURE
        else:
            return Outcome.SUCCESS if exec_rng.random() < p_wrong else Outcome.FAILURE

    full_spec = DomainSpec(
        name=f"Partitioned_{n_total}_{n_partitions}P",
        description=f"{n_total} states in {n_partitions} partitions",
        landscape=ls,
        start=all_states[0],
        goal="GOAL",
        execute_fn=execute_fn,
        happy_path_length=n_total - 1,
        topology_class="partitioned",
        node_count=len(all_states),
        edge_count=ls.edge_count(),
    )

    # Build sub-specs for each partition
    sub_specs = []
    for p, partition_states in enumerate(partitions):
        sub_ls = Landscape()
        for s in partition_states:
            for t in partition_states:
                if s != t:
                    sub_ls.add_edge(s, t, delta=0.5, resistance=1.0)
        sub_goal = partition_states[-1]  # last node is exit/goal of partition

        sub_rng = random.Random(rng.random())
        p_happy = set()
        for i in range(len(partition_states) - 1):
            p_happy.add((partition_states[i], partition_states[i + 1]))

        def make_sub_exec(p_happy_set, sub_rng_local):
            def sub_exec(source, target):
                if (source, target) in p_happy_set:
                    return Outcome.SUCCESS if sub_rng_local.random() < p_correct else Outcome.FAILURE
                return Outcome.SUCCESS if sub_rng_local.random() < p_wrong else Outcome.FAILURE
            return sub_exec

        sub_spec = DomainSpec(
            name=f"Partition_{p}",
            description=f"Partition {p} of {n_partitions}",
            landscape=sub_ls,
            start=partition_states[0],
            goal=sub_goal,
            execute_fn=make_sub_exec(p_happy, sub_rng),
            happy_path_length=partition_size - 1,
            topology_class="fully_connected",
            node_count=len(partition_states),
            edge_count=len(partition_states) * (len(partition_states) - 1),
        )
        sub_specs.append(sub_spec)

    return full_spec, sub_specs


def run_partitioned_experiment():
    """Part 3: Compare solo-on-100 vs partitioned-100 (4×25)."""
    print("\n\n" + "=" * 100)
    print("PART 3: HIERARCHICAL DECOMPOSITION (N=100 → 10×10)")
    print(f"Config: N_TRIALS={N_TRIALS}, N_EPISODES={N_EPISODES}")
    print("=" * 100)

    # ── A: Solo on full 100-state domain (already done in Part 1, rerun for comparison) ──
    solo_results = []
    for trial in range(N_TRIALS):
        spec = build_scalable_domain(100, rng=random.Random(1000 + trial))
        result = run_scaling_trial(spec)
        result.condition = "solo_100"
        solo_results.append(result)

    # ── B: Partitioned 100 → 10×10 with trained sub-agents as peer_fns ──
    part_results = []
    for trial in range(N_TRIALS):
        rng = random.Random(3000 + trial)
        full_spec, sub_specs = build_partitioned_domain(100, 10, rng=rng)

        # Train sub-agents on their partitions
        sub_controllers = []
        for sub_spec in sub_specs:
            sub_ctrl = E0Controller(sub_spec.landscape, sub_spec.execute_fn)
            sub_max = max(50, sub_spec.happy_path_length * 5)
            for _ in range(30):
                sub_ctrl.run(sub_spec.start, goal=sub_spec.goal, max_cycles=sub_max)
            sub_controllers.append(sub_ctrl)

        # Build peer_fn that checks partition sub-agents
        def make_partition_peer_fn(sub_ctrls, sub_specs_list):
            def peer_fn(landscape, current, neighbors):
                # Find which partition current belongs to
                for idx, sub_spec in enumerate(sub_specs_list):
                    if current in sub_spec.landscape.states:
                        sub_H = sub_ctrls[idx].landscape.historization
                        best_state = None
                        best_q = -2.0
                        for nb in neighbors:
                            edge = Edge(current, nb)
                            q = sub_H.trace_quality(edge)
                            load = sub_H.trace_load(edge)
                            if load > 0.1 and q > best_q:
                                best_q = q
                                best_state = nb
                        if best_state is not None:
                            return best_state
                        break
                return None
            return peer_fn

        pfn = make_partition_peer_fn(sub_controllers, sub_specs)
        result = run_scaling_trial(full_spec, peer_fn=pfn, overload_threshold=3.0)
        result.condition = "partitioned"
        part_results.append(result)

    # ── C: Solo on partitioned structure (no peer, but partitioned edges) ──
    struct_results = []
    for trial in range(N_TRIALS):
        rng = random.Random(3000 + trial)
        full_spec, _ = build_partitioned_domain(100, 10, rng=rng)
        result = run_scaling_trial(full_spec)
        result.condition = "partitioned_solo"
        struct_results.append(result)

    # Summary
    def summarize(label, results):
        goal_pct = sum(r.goal_reached for r in results) / sum(r.total_episodes for r in results)
        mean_s = sum(r.mean_steps for r in results) / len(results)
        mean_oi = sum(r.mean_overload_index for r in results) / len(results)
        peer_c = sum(r.peer_calls for r in results) / len(results)
        mean_r = sum(r.mean_steps_reached for r in results) / len(results)
        reached = f"{mean_r:.1f}" if mean_r < float('inf') else "∞"
        return label, goal_pct, mean_s, reached, mean_oi, peer_c

    print(f"\n    {'Condition':<25} {'Goal%':>6}  {'Mean Steps':>10}  "
          f"{'Steps|Goal':>10}  {'OI':>6}  {'Peers':>6}")
    print(f"    {'─'*25} {'─'*6}  {'─'*10}  {'─'*10}  {'─'*6}  {'─'*6}")

    for label, results in [
        ("Solo FC-100", solo_results),
        ("Partitioned solo", struct_results),
        ("Partitioned + sub-peers", part_results),
    ]:
        l, g, s, r, oi, pc = summarize(label, results)
        print(f"    {l:<25} {g:>5.0%}  {s:>10.1f}  {r:>10}  {oi:>6.1f}  {pc:>6.0f}")

    # Learning curves
    for label, results in [
        ("Solo FC-100", solo_results),
        ("Part. solo", struct_results),
        ("Part. + peers", part_results),
    ]:
        avg_curve = [sum(r.learning_curve[ep] for r in results) / len(results)
                     for ep in range(N_EPISODES)]
        print(f"\n    Learning curve {label}:")
        for ep in range(0, N_EPISODES, 5):
            vals = avg_curve[ep:ep+5]
            line = f"      ep {ep:>2}-{ep+4:>2}: " + "  ".join(f"{v:>6.1f}" for v in vals)
            print(line)

    # Edge count comparison
    fc_edges = 100 * 99
    part_edges = sum(s.edge_count for s in sub_specs) + 2 * 3  # within + bridges
    print(f"\n    Edge count: FC-100 = {fc_edges}, Partitioned = {part_edges} "
          f"({part_edges/fc_edges:.1%} of FC)")


# ══════════════════════════════════════════════
# Comparison Table
# ══════════════════════════════════════════════

def print_comparison(solo_results, peer_results):
    """Side-by-side Part 1 vs Part 2."""
    print("\n\n" + "=" * 100)
    print("COMPARISON: SOLO vs PEER CONSULTATION")
    print("=" * 100)

    print(f"\n    {'N':>5}  {'─── Solo ───':^22}  {'─── Peer ───':^22}  {'Rescue':>7}")
    print(f"    {'':>5}  {'Goal%':>6} {'Steps':>7} {'OI':>6}  "
          f"{'Goal%':>6} {'Steps':>7} {'Peers':>6}")
    print(f"    {'─'*5}  {'─'*6} {'─'*7} {'─'*6}  {'─'*6} {'─'*7} {'─'*6}  {'─'*7}")

    for n in SCALE_SIZES:
        sr = solo_results[n]
        pr = peer_results[n]

        s_goal = sum(r.goal_reached for r in sr) / sum(r.total_episodes for r in sr)
        s_steps = sum(r.mean_steps for r in sr) / len(sr)
        s_oi = sum(r.mean_overload_index for r in sr) / len(sr)

        p_goal = sum(r.goal_reached for r in pr) / sum(r.total_episodes for r in pr)
        p_steps = sum(r.mean_steps for r in pr) / len(pr)
        p_peers = sum(r.peer_calls for r in pr) / len(pr)

        rescue = p_goal / s_goal if s_goal > 0 else float('inf')
        rescue_str = f"{rescue:.2f}×" if rescue < 100 else "∞"

        print(f"    {n:>5}  {s_goal:>5.0%} {s_steps:>7.1f} {s_oi:>6.1f}  "
              f"{p_goal:>5.0%} {p_steps:>7.1f} {p_peers:>6.0f}  {rescue_str:>7}")


# ══════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════

def main():
    solo_results = run_solo_scaling()
    peer_results = run_peer_scaling()
    print_comparison(solo_results, peer_results)
    run_partitioned_experiment()


if __name__ == "__main__":
    main()
