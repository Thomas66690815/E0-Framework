"""
Focus Narrowing Experiment (C81)
=====================================
Core hypothesis: "An Komplexität scheitert man nur, wenn man nicht
bereit ist zu simplifizieren — also auf E0 zurückzuführen."

E0 works perfectly at N=10 (OI=2.3, 100% goal).
At N=50 (OI=37, 0% goal) and N=100 (OI=87, 0% goal) it drowns
in option overload: N*(N-1) edges with signal ratio 1/(N-1).

The fix is NOT more information (peer oracle) but LESS OPTIONS:
when OI is too high, narrow the candidate set to k << N before
selecting.  This reduces the effective graph back to E0-territory.

Focus strategies tested:
  1. Top-k by trace_quality (known good paths)
  2. Top-k by trace_load (most experienced paths)
  3. Top-k by penalized_tension (existing scoring, just fewer)
  4. Random-k (baseline — is focusing better than random pruning?)

The experiment patches E0Controller._admissible_neighbors() to
return at most k candidates when OI exceeds a focus threshold,
WITHOUT modifying the controller source code.

Part 1: solo scaling recap (N=10,25,50,100, no focus) — baseline
Part 2: focus narrowing (k=8, oi_trigger=5.0) on N=50,100
Part 3: sweep k ∈ {5,8,12,20} on N=100 — find sweet spot
Part 4: peer integration on focused graph — does peer PLUS focus help?

Usage:
  py -3 -m e0_controller.explore_focus_narrowing
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller, EscalationType
from e0_controller.benchmark_domain_invariance import DomainSpec


# ══════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════

N_EPISODES = 30
N_TRIALS = 3
MAX_CYCLES_CAP = 200   # happy path N=100 is 99 steps; 2× overhead


# ══════════════════════════════════════════════
# Domain Builder (same as explore_landscape_scaling)
# ══════════════════════════════════════════════

def build_scalable_domain(
    n_states: int,
    p_correct: float = 0.85,
    p_wrong: float = 0.30,
    rng: Optional[random.Random] = None,
) -> DomainSpec:
    """N-state fully-connected with differential feedback.

    Happy path: S0 → S1 → ... → GOAL (length N-1).
    Signal ratio: (N-1)/(N*(N-1)) = 1/N.
    """
    if rng is None:
        rng = random.Random(42)

    states = [f"S{i}" for i in range(n_states - 1)] + ["GOAL"]
    ls = Landscape.fully_connected(states, delta=0.5, resistance=1.0)

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
        description=f"{n_states}-state FC with differential feedback",
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
# Focus Narrowing: Monkey-patch _admissible_neighbors
# ══════════════════════════════════════════════

def patch_focus_narrowing(
    ctrl: E0Controller,
    k: int = 8,
    oi_trigger: float = 5.0,
    strategy: str = "quality",
) -> None:
    """Patch controller to narrow candidates when OI exceeds trigger.

    Strategies:
      "quality"  — keep top-k by trace_quality (prefer known-good)
      "load"     — keep top-k by trace_load (prefer well-explored)
      "tension"  — keep top-k by penalized_tension (existing score)
      "random"   — keep random k (baseline: is ANY pruning helpful?)
    """
    original_admissible = ctrl._admissible_neighbors.__func__
    rng = random.Random(42)

    def focused_admissible(self, current: str) -> List[str]:
        neighbors = original_admissible(self, current)

        if len(neighbors) <= k:
            return neighbors

        # Check if we should focus
        oi = self._overload_index(current, neighbors)
        if oi <= oi_trigger:
            return neighbors

        # FOCUS: narrow to k candidates
        hist = self.landscape.historization

        if strategy == "quality":
            # Top-k by trace_quality — prefer known-good edges
            def score(nb):
                edge = Edge(current, nb)
                load = hist.trace_load(edge)
                if load > 0:
                    return hist.trace_quality(edge)
                return 0.0  # unknown = neutral
            neighbors.sort(key=score, reverse=True)
            return neighbors[:k]

        elif strategy == "load":
            # Top-k by trace_load — prefer most-experienced
            def score(nb):
                edge = Edge(current, nb)
                return hist.trace_load(edge)
            neighbors.sort(key=score, reverse=True)
            return neighbors[:k]

        elif strategy == "tension":
            # Top-k by penalized_tension — use existing scoring
            neighbors.sort(key=lambda nb: self._penalized_tension(current, nb))
            return neighbors[:k]

        elif strategy == "random":
            # Random k — baseline
            rng.shuffle(neighbors)
            return neighbors[:k]

        return neighbors

    import types
    ctrl._admissible_neighbors = types.MethodType(focused_admissible, ctrl)


# ══════════════════════════════════════════════
# Metrics
# ══════════════════════════════════════════════

@dataclass
class FocusResult:
    n_states: int
    condition: str
    strategy: str
    k: int
    goal_reached: int
    total_episodes: int
    mean_steps: float
    mean_steps_reached: float
    mean_oi_raw: float       # OI before focus (all neighbors)
    mean_oi_focused: float   # OI after focus (k neighbors)
    peer_calls: int = 0
    learning_curve: List[float] = field(default_factory=list)


def run_trial(
    spec: DomainSpec,
    n_episodes: int = N_EPISODES,
    focus_k: int = 0,
    focus_strategy: str = "none",
    oi_trigger: float = 5.0,
    peer_fn: Optional[Callable] = None,
    overload_threshold: float = 3.0,
) -> FocusResult:
    """Run one trial with optional focus narrowing."""
    max_cycles = min(MAX_CYCLES_CAP, max(150, spec.happy_path_length * 5))
    ctrl = E0Controller(
        spec.landscape, spec.execute_fn,
        peer_fn=peer_fn,
        overload_threshold=overload_threshold,
    )

    if focus_k > 0:
        patch_focus_narrowing(ctrl, k=focus_k, oi_trigger=oi_trigger,
                              strategy=focus_strategy)

    goal_reached = 0
    total_steps = 0
    steps_reached = []
    oi_raw_samples = []
    oi_focused_samples = []
    peer_calls = 0
    per_ep = []

    for ep in range(n_episodes):
        trace = ctrl.run(spec.start, goal=spec.goal, max_cycles=max_cycles)
        steps = len(trace.steps)
        per_ep.append(steps)
        total_steps += steps

        reached = (trace.steps and trace.steps[-1].target == spec.goal) if trace.steps else False
        if reached:
            goal_reached += 1
            steps_reached.append(steps)

        for step in trace.steps:
            if step.escalation_type == EscalationType.OVERLOADED:
                peer_calls += 1

        # Sample raw OI (before focus)
        raw_neighbors = spec.landscape.admissible_neighbors(spec.start)
        if raw_neighbors:
            oi_raw = len(raw_neighbors)  # simplified: just N_neighbors
            oi_raw_samples.append(oi_raw)
            oi_focused = min(focus_k, len(raw_neighbors)) if focus_k > 0 else len(raw_neighbors)
            oi_focused_samples.append(oi_focused)

    mean_s = total_steps / n_episodes if n_episodes > 0 else 0
    mean_r = sum(steps_reached) / len(steps_reached) if steps_reached else float('inf')
    mean_oi_r = sum(oi_raw_samples) / len(oi_raw_samples) if oi_raw_samples else 0
    mean_oi_f = sum(oi_focused_samples) / len(oi_focused_samples) if oi_focused_samples else 0

    return FocusResult(
        n_states=spec.node_count,
        condition="focused" if focus_k > 0 else "solo",
        strategy=focus_strategy if focus_k > 0 else "none",
        k=focus_k if focus_k > 0 else spec.node_count - 1,
        goal_reached=goal_reached,
        total_episodes=n_episodes,
        mean_steps=mean_s,
        mean_steps_reached=mean_r,
        mean_oi_raw=mean_oi_r,
        mean_oi_focused=mean_oi_f,
        peer_calls=peer_calls,
        learning_curve=per_ep,
    )


# ══════════════════════════════════════════════
# Part 1: Baseline (solo, no focus)
# ══════════════════════════════════════════════

SCALE_SIZES = [10, 25, 50, 100]


def run_baseline():
    """Baseline: solo agent, no focus narrowing."""
    print("=" * 100)
    print("PART 1: BASELINE — SOLO AGENT, NO FOCUS NARROWING")
    print(f"Config: N_TRIALS={N_TRIALS}, N_EPISODES={N_EPISODES}")
    print("=" * 100)

    results: Dict[int, List[FocusResult]] = {}
    for n in SCALE_SIZES:
        trial_results = []
        for trial in range(N_TRIALS):
            spec = build_scalable_domain(n, rng=random.Random(1000 + trial))
            r = run_trial(spec)
            trial_results.append(r)
        results[n] = trial_results

    _print_table("Baseline", results, SCALE_SIZES)
    return results


# ══════════════════════════════════════════════
# Part 2: Focus Narrowing — all strategies on N=50, N=100
# ══════════════════════════════════════════════

STRATEGIES = ["quality", "load", "tension", "random"]


def run_focus_strategies():
    """Compare focus strategies on N=50 and N=100 with k=8."""
    print("\n\n" + "=" * 100)
    print("PART 2: FOCUS NARROWING — k=8, oi_trigger=5.0")
    print(f"Strategies: {STRATEGIES}")
    print(f"Config: N_TRIALS={N_TRIALS}, N_EPISODES={N_EPISODES}")
    print("=" * 100)

    test_sizes = [50, 100]
    all_results: Dict[str, Dict[int, List[FocusResult]]] = {}

    for strategy in STRATEGIES:
        strat_results: Dict[int, List[FocusResult]] = {}
        for n in test_sizes:
            trial_results = []
            for trial in range(N_TRIALS):
                spec = build_scalable_domain(n, rng=random.Random(1000 + trial))
                r = run_trial(spec, focus_k=8, focus_strategy=strategy)
                trial_results.append(r)
            strat_results[n] = trial_results
        all_results[strategy] = strat_results

    # Summary table
    print(f"\n    {'Strategy':<12} {'N':>5}  {'Goal%':>6}  {'Mean Steps':>10}  "
          f"{'Steps|Goal':>10}  {'EffectiveK':>10}")
    print(f"    {'─'*12} {'─'*5}  {'─'*6}  {'─'*10}  {'─'*10}  {'─'*10}")

    for strategy in STRATEGIES:
        for n in test_sizes:
            results = all_results[strategy][n]
            goal_pct = sum(r.goal_reached for r in results) / sum(r.total_episodes for r in results)
            mean_s = sum(r.mean_steps for r in results) / len(results)
            mean_r = sum(r.mean_steps_reached for r in results) / len(results)
            reached_str = f"{mean_r:.1f}" if mean_r < float('inf') else "∞"
            eff_k = sum(r.mean_oi_focused for r in results) / len(results)
            print(f"    {strategy:<12} {n:>5}  {goal_pct:>5.0%}  {mean_s:>10.1f}  "
                  f"{reached_str:>10}  {eff_k:>10.0f}")

    return all_results


# ══════════════════════════════════════════════
# Part 3: Sweep k on N=100 with best strategy
# ══════════════════════════════════════════════

K_VALUES = [5, 8, 12, 20]


def run_k_sweep(best_strategy: str = "quality"):
    """Sweep k values on N=100 with the best strategy from Part 2."""
    print("\n\n" + "=" * 100)
    print(f"PART 3: k-SWEEP ON N=100 — strategy='{best_strategy}'")
    print(f"k values: {K_VALUES}")
    print(f"Config: N_TRIALS={N_TRIALS}, N_EPISODES={N_EPISODES}")
    print("=" * 100)

    results: Dict[int, List[FocusResult]] = {}
    for k in K_VALUES:
        trial_results = []
        for trial in range(N_TRIALS):
            spec = build_scalable_domain(100, rng=random.Random(1000 + trial))
            r = run_trial(spec, focus_k=k, focus_strategy=best_strategy)
            trial_results.append(r)
        results[k] = trial_results

    # Summary table
    print(f"\n    {'k':>5}  {'Goal%':>6}  {'Mean Steps':>10}  {'Steps|Goal':>10}  "
          f"{'Signal':>7}  {'OI_eff':>7}")
    print(f"    {'─'*5}  {'─'*6}  {'─'*10}  {'─'*10}  {'─'*7}  {'─'*7}")

    for k in K_VALUES:
        kr = results[k]
        goal_pct = sum(r.goal_reached for r in kr) / sum(r.total_episodes for r in kr)
        mean_s = sum(r.mean_steps for r in kr) / len(kr)
        mean_r = sum(r.mean_steps_reached for r in kr) / len(kr)
        reached_str = f"{mean_r:.1f}" if mean_r < float('inf') else "∞"
        # Effective signal: happy_path_edges_in_view / k
        # At best 1 of the k is on the happy path
        signal = 1.0 / k
        oi_eff = k * 0.8  # rough: mostly unknown at start
        print(f"    {k:>5}  {goal_pct:>5.0%}  {mean_s:>10.1f}  {reached_str:>10}  "
              f"{signal:>6.1%}  {oi_eff:>7.1f}")

    # Learning curves for best and worst k
    for k in [K_VALUES[0], K_VALUES[-1]]:
        kr = results[k]
        avg_curve = [sum(r.learning_curve[ep] for r in kr) / len(kr) for ep in range(N_EPISODES)]
        print(f"\n    Learning curve k={k}:")
        for ep in range(0, N_EPISODES, 5):
            vals = avg_curve[ep:ep+5]
            line = f"      ep {ep:>2}-{ep+4:>2}: " + "  ".join(f"{v:>6.1f}" for v in vals)
            print(line)

    return results


# ══════════════════════════════════════════════
# Part 4: Focus + Peer (Zentrale-Modell)
# ══════════════════════════════════════════════

def build_perfect_oracle_peer_fn(n_states: int) -> Callable:
    """Perfect oracle: knows the happy path, always recommends correct next."""
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


def run_focus_plus_peer():
    """Focus narrowing + perfect peer on N=100.

    The "Zentrale" model: focus down to manageable set, then
    integrate peer advice if still overloaded.
    """
    print("\n\n" + "=" * 100)
    print("PART 4: FOCUS + PEER INTEGRATION (N=100)")
    print("  Conditions: solo | focus-only(k=8) | peer-only | focus+peer")
    print(f"Config: N_TRIALS={N_TRIALS}, N_EPISODES={N_EPISODES}")
    print("=" * 100)

    conditions = [
        ("solo",         0,  "none",    None),
        ("focus(k=8)",   8,  "quality", None),
        ("peer-only",    0,  "none",    "perfect"),
        ("focus+peer",   8,  "quality", "perfect"),
    ]

    all_results: Dict[str, List[FocusResult]] = {}

    for label, focus_k, strategy, peer_type in conditions:
        trial_results = []
        for trial in range(N_TRIALS):
            spec = build_scalable_domain(100, rng=random.Random(1000 + trial))
            pfn = build_perfect_oracle_peer_fn(100) if peer_type else None
            r = run_trial(
                spec,
                focus_k=focus_k,
                focus_strategy=strategy,
                peer_fn=pfn,
                overload_threshold=3.0 if pfn else 999.0,
            )
            r.condition = label
            trial_results.append(r)
        all_results[label] = trial_results

    # Summary
    print(f"\n    {'Condition':<18} {'Goal%':>6}  {'Mean Steps':>10}  "
          f"{'Steps|Goal':>10}  {'Peer Calls':>10}")
    print(f"    {'─'*18} {'─'*6}  {'─'*10}  {'─'*10}  {'─'*10}")

    for label, _, _, _ in conditions:
        results = all_results[label]
        goal_pct = sum(r.goal_reached for r in results) / sum(r.total_episodes for r in results)
        mean_s = sum(r.mean_steps for r in results) / len(results)
        mean_r = sum(r.mean_steps_reached for r in results) / len(results)
        reached_str = f"{mean_r:.1f}" if mean_r < float('inf') else "∞"
        peer_c = sum(r.peer_calls for r in results) / len(results)
        print(f"    {label:<18} {goal_pct:>5.0%}  {mean_s:>10.1f}  "
              f"{reached_str:>10}  {peer_c:>10.0f}")

    # Learning curves
    for label, _, _, _ in conditions:
        results = all_results[label]
        avg_curve = [sum(r.learning_curve[ep] for r in results) / len(results)
                     for ep in range(N_EPISODES)]
        print(f"\n    Learning curve {label}:")
        for ep in range(0, N_EPISODES, 5):
            vals = avg_curve[ep:ep+5]
            line = f"      ep {ep:>2}-{ep+4:>2}: " + "  ".join(f"{v:>6.1f}" for v in vals)
            print(line)


# ══════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════

def _print_table(label: str, results: Dict[int, List[FocusResult]], sizes: List[int]):
    """Print a standard summary table."""
    print(f"\n    {'N':>5}  {'Edges':>6}  {'Signal':>7}  {'Goal%':>6}  "
          f"{'Mean Steps':>10}  {'Steps|Goal':>10}")
    print(f"    {'─'*5}  {'─'*6}  {'─'*7}  {'─'*6}  "
          f"{'─'*10}  {'─'*10}")
    for n in sizes:
        rr = results[n]
        edges = n * (n - 1)
        signal = (n - 1) / edges
        goal_pct = sum(r.goal_reached for r in rr) / sum(r.total_episodes for r in rr)
        mean_s = sum(r.mean_steps for r in rr) / len(rr)
        mean_r = sum(r.mean_steps_reached for r in rr) / len(rr)
        reached_str = f"{mean_r:.1f}" if mean_r < float('inf') else "∞"
        print(f"    {n:>5}  {edges:>6}  {signal:>6.1%}  {goal_pct:>5.0%}  "
              f"{mean_s:>10.1f}  {reached_str:>10}")


# ══════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════

def main():
    run_baseline()

    focus_results = run_focus_strategies()

    # Find best strategy from Part 2
    best_strat = "quality"
    best_goal = -1
    for strategy, strat_data in focus_results.items():
        # Check N=100 performance
        if 100 in strat_data:
            g = sum(r.goal_reached for r in strat_data[100]) / sum(r.total_episodes for r in strat_data[100])
            if g > best_goal:
                best_goal = g
                best_strat = strategy
    print(f"\n    >>> Best strategy for N=100: '{best_strat}' ({best_goal:.0%} goal)")

    run_k_sweep(best_strategy=best_strat)
    run_focus_plus_peer()


if __name__ == "__main__":
    main()
