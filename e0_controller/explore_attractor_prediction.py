"""
Attractor Prediction Experiment (C80)
=======================================
Open Question #6: Can we predict WHICH state will become the attractor
from domain structure alone, before historization runs?

C75 showed that attractor formation requires (1) topological choice and
(2) differential feedback. But it did not address prediction: given a
domain, which state will concentrate inscription?

Approach: compute structural predictors per state, run historization,
measure which predictor best correlates with actual attractor identity.

Structural predictors (computed before any navigation):
  1. In-degree: number of incoming edges
  2. Out-degree: number of outgoing edges
  3. Goal-distance: shortest path distance to goal (BFS)
  4. Start-distance: shortest path distance from start (BFS)
  5. PageRank: stationary distribution of random walk (damping=0.85)
  6. Betweenness: fraction of shortest paths through this state
  7. Harmonic closeness: sum of 1/d(v, s) for all other states s

Part 1: Original topology + uniform init + original execute_fn
Part 2: Fully connected topology + original execute_fn
Part 3: Synthetic domains designed to stress-test predictors

Usage:
  py -3 -m e0_controller.explore_attractor_prediction
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Set, Tuple

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller
from e0_controller.explore_attractor_universality import (
    analyze_domain,
    DomainAttractorResult,
    StateMetrics,
    N_RUNS,
    UNIFORM_DELTA,
    UNIFORM_R0,
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
# Structural Predictors (computed before navigation)
# ══════════════════════════════════════════════

def _build_adjacency(landscape: Landscape) -> Dict[str, Set[str]]:
    """Forward adjacency: state → set of reachable targets."""
    adj: Dict[str, Set[str]] = defaultdict(set)
    for e in landscape.edges:
        adj[e.source].add(e.target)
    return adj


def _build_reverse_adjacency(landscape: Landscape) -> Dict[str, Set[str]]:
    """Reverse adjacency: state → set of sources that reach it."""
    rev: Dict[str, Set[str]] = defaultdict(set)
    for e in landscape.edges:
        rev[e.target].add(e.source)
    return rev


def compute_degrees(landscape: Landscape) -> Tuple[Dict[str, int], Dict[str, int]]:
    """Return (in_degree, out_degree) per state."""
    in_deg: Dict[str, int] = defaultdict(int)
    out_deg: Dict[str, int] = defaultdict(int)
    for e in landscape.edges:
        out_deg[e.source] += 1
        in_deg[e.target] += 1
    # Ensure all states appear
    for s in landscape.states:
        in_deg.setdefault(s, 0)
        out_deg.setdefault(s, 0)
    return dict(in_deg), dict(out_deg)


def bfs_distances(landscape: Landscape, start: str) -> Dict[str, int]:
    """BFS shortest path distances from start. Unreachable → -1."""
    adj = _build_adjacency(landscape)
    dist: Dict[str, int] = {s: -1 for s in landscape.states}
    dist[start] = 0
    queue = deque([start])
    while queue:
        u = queue.popleft()
        for v in adj[u]:
            if dist[v] == -1:
                dist[v] = dist[u] + 1
                queue.append(v)
    return dist


def reverse_bfs_distances(landscape: Landscape, target: str) -> Dict[str, int]:
    """BFS shortest path distances TO target (reverse edges). Unreachable → -1."""
    rev = _build_reverse_adjacency(landscape)
    dist: Dict[str, int] = {s: -1 for s in landscape.states}
    dist[target] = 0
    queue = deque([target])
    while queue:
        u = queue.popleft()
        for v in rev[u]:
            if dist[v] == -1:
                dist[v] = dist[u] + 1
                queue.append(v)
    return dist


def compute_pagerank(landscape: Landscape, damping: float = 0.85,
                     iterations: int = 100) -> Dict[str, float]:
    """Simple PageRank on the directed graph."""
    states = sorted(landscape.states)
    n = len(states)
    if n == 0:
        return {}
    adj = _build_adjacency(landscape)
    out_deg = {s: len(adj[s]) for s in states}

    pr = {s: 1.0 / n for s in states}
    for _ in range(iterations):
        new_pr = {s: (1.0 - damping) / n for s in states}
        for s in states:
            if out_deg[s] > 0:
                share = damping * pr[s] / out_deg[s]
                for t in adj[s]:
                    new_pr[t] += share
            else:
                # Dangling node: distribute evenly
                share = damping * pr[s] / n
                for t in states:
                    new_pr[t] += share
        pr = new_pr
    return pr


def compute_betweenness(landscape: Landscape) -> Dict[str, float]:
    """Betweenness centrality (fraction of shortest paths through each node)."""
    states = sorted(landscape.states)
    adj = _build_adjacency(landscape)
    betweenness = {s: 0.0 for s in states}

    for source in states:
        # BFS from source
        dist: Dict[str, int] = {source: 0}
        sigma: Dict[str, int] = {source: 1}  # number of shortest paths
        pred: Dict[str, List[str]] = {s: [] for s in states}
        queue = deque([source])
        visited_order = []

        while queue:
            u = queue.popleft()
            visited_order.append(u)
            for v in adj.get(u, set()):
                if v not in dist:
                    dist[v] = dist[u] + 1
                    queue.append(v)
                if v in dist and dist[v] == dist[u] + 1:
                    sigma[v] = sigma.get(v, 0) + sigma[u]
                    pred[v].append(u)

        # Back-propagation
        delta = {s: 0.0 for s in states}
        while visited_order:
            w = visited_order.pop()
            for v in pred[w]:
                if sigma.get(w, 0) > 0:
                    delta[v] += (sigma[v] / sigma[w]) * (1.0 + delta[w])
            if w != source:
                betweenness[w] += delta[w]

    # Normalize
    n = len(states)
    if n > 2:
        norm = (n - 1) * (n - 2)
        betweenness = {s: v / norm for s, v in betweenness.items()}
    return betweenness


def compute_harmonic_closeness(landscape: Landscape) -> Dict[str, float]:
    """Harmonic closeness centrality: sum of 1/d(v, s) for all s reachable from v.
    Higher = more central. Uses outgoing distances (how easily you reach others).
    """
    states = sorted(landscape.states)
    closeness = {}
    for s in states:
        dists = bfs_distances(landscape, s)
        total = sum(1.0 / d for d in dists.values() if d > 0)
        closeness[s] = total
    return closeness


@dataclass
class StatePredictor:
    """Structural predictors for one state."""
    state: str
    in_degree: int = 0
    out_degree: int = 0
    goal_distance: int = -1     # BFS hops to goal (-1 = unreachable)
    start_distance: int = -1    # BFS hops from start (-1 = unreachable)
    pagerank: float = 0.0
    betweenness: float = 0.0
    closeness: float = 0.0


def compute_all_predictors(
    landscape: Landscape, start: str, goal: str,
) -> Dict[str, StatePredictor]:
    """Compute all structural predictors before any navigation."""
    in_deg, out_deg = compute_degrees(landscape)
    start_dist = bfs_distances(landscape, start)
    goal_dist = reverse_bfs_distances(landscape, goal)
    pr = compute_pagerank(landscape)
    bt = compute_betweenness(landscape)
    cl = compute_harmonic_closeness(landscape)

    result = {}
    for s in sorted(landscape.states):
        result[s] = StatePredictor(
            state=s,
            in_degree=in_deg.get(s, 0),
            out_degree=out_deg.get(s, 0),
            goal_distance=goal_dist.get(s, -1),
            start_distance=start_dist.get(s, -1),
            pagerank=pr.get(s, 0.0),
            betweenness=bt.get(s, 0.0),
            closeness=cl.get(s, 0.0),
        )
    return result


# ══════════════════════════════════════════════
# Prediction Evaluation
# ══════════════════════════════════════════════

@dataclass
class PredictionResult:
    """Prediction accuracy for one domain."""
    domain: str
    n_states: int
    actual_attractor: str
    actual_ratio: float
    has_attractor: bool
    # Which predictor's top-ranked state matches actual attractor
    predictions: Dict[str, str]       # predictor_name → predicted state
    correct: Dict[str, bool]          # predictor_name → correct?
    predictor_values: Dict[str, Dict[str, float]]  # predictor → {state: value}
    feedback_type: str  # "differential" or "all_success"


PREDICTOR_NAMES = [
    "in_degree", "out_degree", "goal_distance",
    "start_distance", "pagerank", "betweenness", "closeness",
]

# For goal_distance: LOWER is better (closer to goal = more attractive)
# For start_distance: depends — on-path states are moderate distance
# For all others: HIGHER is better

LOWER_IS_BETTER = {"goal_distance", "start_distance"}


def predict_attractor(
    predictors: Dict[str, StatePredictor],
    predictor_name: str,
) -> str:
    """Return the state with the highest (or lowest for distance) predictor value."""
    lower = predictor_name in LOWER_IS_BETTER
    items = [
        (sp.state, getattr(sp, predictor_name))
        for sp in predictors.values()
        if getattr(sp, predictor_name) >= 0  # skip unreachable (-1)
    ]
    if not items:
        return "(none)"
    if lower:
        items.sort(key=lambda x: x[1])
    else:
        items.sort(key=lambda x: x[1], reverse=True)
    return items[0][0]


def evaluate_domain(
    builder: Callable[[], DomainSpec],
    mode: str = "original",
    feedback_type: str = "unknown",
) -> PredictionResult:
    """Compute predictors, run navigation, compare prediction vs actual."""
    spec = builder()
    start, goal = spec.start, spec.goal

    # Compute predictors on the raw landscape
    if mode == "fully_connected":
        states = sorted(spec.landscape.states)
        spec.landscape = Landscape.fully_connected(
            states, delta=UNIFORM_DELTA, resistance=UNIFORM_R0,
        )
    else:
        # Uniformize for fair comparison
        from e0_controller.explore_attractor_universality import uniformize_landscape
        uniformize_landscape(spec)

    predictors = compute_all_predictors(spec.landscape, start, goal)

    # Run navigation to find actual attractor
    result = analyze_domain(spec, mode=mode)

    # Predict for each predictor
    predictions = {}
    correct = {}
    pred_values: Dict[str, Dict[str, float]] = {}
    for pname in PREDICTOR_NAMES:
        predicted = predict_attractor(predictors, pname)
        predictions[pname] = predicted
        correct[pname] = (predicted == result.top_attractor)
        pred_values[pname] = {
            sp.state: getattr(sp, pname)
            for sp in predictors.values()
        }

    return PredictionResult(
        domain=spec.name,
        n_states=result.n_states,
        actual_attractor=result.top_attractor,
        actual_ratio=result.attractor_ratio,
        has_attractor=result.has_attractor,
        predictions=predictions,
        correct=correct,
        predictor_values=pred_values,
        feedback_type=feedback_type,
    )


# ══════════════════════════════════════════════
# Synthetic Domains (stress-test predictors)
# ══════════════════════════════════════════════

def build_hub_spoke() -> DomainSpec:
    """Hub-and-spoke: central hub connects to 6 spokes + goal.
    Hub has highest betweenness but differential feedback makes
    one spoke the funnel to goal.
    """
    ls = Landscape()
    spokes = [f"S{i}" for i in range(6)]
    # Hub connects to all spokes and goal
    for s in spokes:
        ls.add_edge("HUB", s, delta=0.5, resistance=1.0)
        ls.add_edge(s, "HUB", delta=0.5, resistance=1.0)
    ls.add_edge("HUB", "GOAL", delta=0.5, resistance=1.0)
    # START connects to hub
    ls.add_edge("START", "HUB", delta=0.5, resistance=1.0)
    # One spoke also connects to goal
    ls.add_edge("S0", "GOAL", delta=0.5, resistance=1.0)

    failing_edges = {("HUB", "S1"), ("HUB", "S2"), ("HUB", "S3"),
                     ("HUB", "S4"), ("HUB", "S5")}

    def execute_fn(source: str, target: str) -> Outcome:
        if (source, target) in failing_edges:
            return Outcome.FAILURE
        return Outcome.SUCCESS

    return DomainSpec(
        name="Hub-Spoke",
        description="Central hub with differential spoke feedback",
        landscape=ls,
        start="START",
        goal="GOAL",
        execute_fn=execute_fn,
        happy_path_length=2,
        topology_class="star",
        node_count=9,
        edge_count=15,
    )


def build_diamond_chain() -> DomainSpec:
    """Chain of 3 diamonds — attractor should form at the bottleneck
    between diamonds, not at highest degree node.
    """
    ls = Landscape()
    # Diamond 1: S → A1, B1 → M1
    ls.add_edge("START", "A1", delta=0.5, resistance=1.0)
    ls.add_edge("START", "B1", delta=0.5, resistance=1.0)
    ls.add_edge("A1", "M1", delta=0.5, resistance=1.0)
    ls.add_edge("B1", "M1", delta=0.5, resistance=1.0)
    # Diamond 2: M1 → A2, B2 → M2
    ls.add_edge("M1", "A2", delta=0.5, resistance=1.0)
    ls.add_edge("M1", "B2", delta=0.5, resistance=1.0)
    ls.add_edge("A2", "M2", delta=0.5, resistance=1.0)
    ls.add_edge("B2", "M2", delta=0.5, resistance=1.0)
    # Diamond 3: M2 → A3, B3 → GOAL
    ls.add_edge("M2", "A3", delta=0.5, resistance=1.0)
    ls.add_edge("M2", "B3", delta=0.5, resistance=1.0)
    ls.add_edge("A3", "GOAL", delta=0.5, resistance=1.0)
    ls.add_edge("B3", "GOAL", delta=0.5, resistance=1.0)

    # Differential: B-paths always fail
    failing = {("START", "B1"), ("M1", "B2"), ("M2", "B3")}

    def execute_fn(source: str, target: str) -> Outcome:
        if (source, target) in failing:
            return Outcome.FAILURE
        return Outcome.SUCCESS

    return DomainSpec(
        name="Diamond-Chain",
        description="3 diamonds in series, B-paths fail",
        landscape=ls,
        start="START",
        goal="GOAL",
        execute_fn=execute_fn,
        happy_path_length=6,
        topology_class="series_parallel",
        node_count=10,
        edge_count=12,
    )


def build_bypass_trap() -> DomainSpec:
    """High-degree trap node vs low-degree bypass to goal.
    Tests whether degree-based predictors get fooled.
    """
    ls = Landscape()
    # TRAP node has many connections
    ls.add_edge("START", "TRAP", delta=0.5, resistance=1.0)
    for i in range(5):
        ls.add_edge("TRAP", f"DEAD{i}", delta=0.5, resistance=1.0)
    ls.add_edge("TRAP", "START", delta=0.5, resistance=1.0)  # cycle back

    # Bypass: low-degree path to goal
    ls.add_edge("START", "BYPASS", delta=0.5, resistance=1.0)
    ls.add_edge("BYPASS", "GOAL", delta=0.5, resistance=1.0)

    # Differential: TRAP→DEAD always fails, TRAP→START fails too
    failing = {("TRAP", f"DEAD{i}") for i in range(5)} | {("TRAP", "START")}

    def execute_fn(source: str, target: str) -> Outcome:
        if (source, target) in failing:
            return Outcome.FAILURE
        return Outcome.SUCCESS

    return DomainSpec(
        name="Bypass-Trap",
        description="High-degree trap vs low-degree correct path",
        landscape=ls,
        start="START",
        goal="GOAL",
        execute_fn=execute_fn,
        happy_path_length=2,
        topology_class="tree",
        node_count=9,
        edge_count=8,
    )


SYNTHETIC_BUILDERS = [
    (build_hub_spoke, "differential"),
    (build_diamond_chain, "differential"),
    (build_bypass_trap, "differential"),
]


# ══════════════════════════════════════════════
# Combined Predictor (composite score)
# ══════════════════════════════════════════════

def rank_normalize(values: Dict[str, float], lower_is_better: bool = False) -> Dict[str, float]:
    """Normalize values to [0, 1] range. Highest original = 1.0."""
    if not values:
        return {}
    vals = list(values.values())
    vmin, vmax = min(vals), max(vals)
    if vmax - vmin < 1e-12:
        return {s: 0.5 for s in values}
    if lower_is_better:
        return {s: (vmax - v) / (vmax - vmin) for s, v in values.items()}
    return {s: (v - vmin) / (vmax - vmin) for s, v in values.items()}


# ══════════════════════════════════════════════
# Output
# ══════════════════════════════════════════════

ALL_BUILDERS = [
    (build_d1_linear_chain, "all_success"),
    (build_d2_diamond, "all_success"),
    (build_d3_gordian_trap, "differential"),
    (build_d4_greedy_trap, "all_success"),
    (build_d5_grid_detour, "all_success"),
    (build_d6_multigoal_star, "differential"),
    (build_d7_invoice, "differential"),
    (build_d8_nested_cycles, "differential"),
    (build_d9_wide_dag, "all_success"),
    (build_d10_bottleneck, "differential"),
]


def print_prediction_table(
    results: List[PredictionResult],
    title: str,
) -> None:
    print("=" * 110)
    print(title)
    print("=" * 110)

    # Table: domain, actual attractor, each predictor's prediction, match
    short_names = {
        "in_degree": "InDeg",
        "out_degree": "OutDeg",
        "goal_distance": "GoalD",
        "start_distance": "StartD",
        "pagerank": "PgRank",
        "betweenness": "Btwn",
        "closeness": "Close",
    }

    header = f"{'Domain':<22} {'Actual':<12} {'Ratio':>5} {'FB':>5}"
    for pname in PREDICTOR_NAMES:
        header += f"  {short_names[pname]:>6}"
    print(header)
    print("-" * len(header))

    for r in results:
        line = f"{r.domain:<22} {r.actual_attractor:<12} {r.actual_ratio:>5.1f} "
        line += f"{'diff' if r.feedback_type == 'differential' else 'all':>5}"
        for pname in PREDICTOR_NAMES:
            pred = r.predictions[pname]
            mark = "✓" if r.correct[pname] else "✗"
            # Truncate state name
            short_pred = pred[:5] if len(pred) > 5 else pred
            line += f"  {short_pred:>5}{mark}"
        print(line)

    # Accuracy per predictor
    print()
    total = len(results)
    attractor_only = [r for r in results if r.has_attractor]
    n_attr = len(attractor_only)

    print(f"  Predictor accuracy (all {total} domains / {n_attr} with attractor):")
    for pname in PREDICTOR_NAMES:
        all_correct = sum(1 for r in results if r.correct[pname])
        attr_correct = sum(1 for r in attractor_only if r.correct[pname])
        print(f"    {short_names[pname]:>6}: {all_correct:>2}/{total}  "
              f"({attr_correct}/{n_attr} with-attractor)")


def print_detail(results: List[PredictionResult]) -> None:
    """Print per-domain predictor values for top 3 states."""
    for r in results:
        if not r.has_attractor:
            continue
        print(f"\n─── {r.domain} (attractor: {r.actual_attractor}, "
              f"ratio: {r.actual_ratio:.1f}×) ───")
        # Sort states by in_degree descending
        states = sorted(r.predictor_values["in_degree"].keys())
        # Show predictor values for top states (by pagerank)
        by_pr = sorted(states,
                       key=lambda s: r.predictor_values["pagerank"].get(s, 0),
                       reverse=True)[:5]
        header = f"    {'State':<12}"
        short = {"in_degree": "InD", "out_degree": "OutD", "goal_distance": "GoalD",
                 "start_distance": "SrtD", "pagerank": "PR", "betweenness": "Btw",
                 "closeness": "Cls"}
        for pname in PREDICTOR_NAMES:
            header += f" {short[pname]:>6}"
        print(header)
        for s in by_pr:
            line = f"    {s:<12}"
            for pname in PREDICTOR_NAMES:
                v = r.predictor_values[pname].get(s, 0)
                if pname in ("pagerank",):
                    line += f" {v:>6.3f}"
                elif pname in ("betweenness", "closeness"):
                    line += f" {v:>6.2f}"
                else:
                    line += f" {v:>6.0f}"
            marker = " ◀ ATTRACTOR" if s == r.actual_attractor else ""
            print(line + marker)


def main():
    # ════════════════════════════
    # Part 1: Original topology
    # ════════════════════════════
    print()
    results1 = []
    for builder, fb in ALL_BUILDERS:
        r = evaluate_domain(builder, mode="original", feedback_type=fb)
        results1.append(r)
    print_prediction_table(results1, "PART 1: ORIGINAL TOPOLOGY — PREDICTOR vs ACTUAL ATTRACTOR")
    print_detail(results1)

    # ════════════════════════════
    # Part 2: Fully connected
    # ════════════════════════════
    print("\n")
    results2 = []
    for builder, fb in ALL_BUILDERS:
        r = evaluate_domain(builder, mode="fully_connected", feedback_type=fb)
        results2.append(r)
    print_prediction_table(results2, "PART 2: FULLY CONNECTED — PREDICTOR vs ACTUAL ATTRACTOR")
    print_detail(results2)

    # ════════════════════════════
    # Part 3: Synthetic domains
    # ════════════════════════════
    print("\n")
    results3 = []
    for builder, fb in SYNTHETIC_BUILDERS:
        r = evaluate_domain(builder, mode="original", feedback_type=fb)
        results3.append(r)
    print_prediction_table(results3, "PART 3: SYNTHETIC DOMAINS — STRESS-TEST PREDICTORS")
    print_detail(results3)

    # ════════════════════════════
    # Overall Summary
    # ════════════════════════════
    print("\n" + "=" * 110)
    print("OVERALL SUMMARY")
    print("=" * 110)

    all_results = results1 + results2 + results3
    all_with_attr = [r for r in all_results if r.has_attractor]

    short_names = {
        "in_degree": "InDeg", "out_degree": "OutDeg",
        "goal_distance": "GoalD", "start_distance": "StartD",
        "pagerank": "PgRank", "betweenness": "Btwn", "closeness": "Close",
    }

    print(f"\nTotal domains: {len(all_results)}, with attractor: {len(all_with_attr)}")
    print(f"\nPredictor accuracy (attractor-only domains):")
    print(f"  {'Predictor':<10} {'Correct':>7} {'Total':>5} {'Accuracy':>8}")
    print(f"  {'─'*10} {'─'*7:>7} {'─'*5:>5} {'─'*8:>8}")

    best_name = ""
    best_acc = -1
    for pname in PREDICTOR_NAMES:
        correct = sum(1 for r in all_with_attr if r.correct[pname])
        total = len(all_with_attr)
        acc = correct / total if total > 0 else 0
        print(f"  {short_names[pname]:<10} {correct:>7} {total:>5} {acc:>7.0%}")
        if acc > best_acc:
            best_acc = acc
            best_name = short_names[pname]

    print(f"\n  Best predictor: {best_name} ({best_acc:.0%})")

    # Split by feedback type
    diff_attr = [r for r in all_with_attr if r.feedback_type == "differential"]
    succ_attr = [r for r in all_with_attr if r.feedback_type == "all_success"]
    if diff_attr:
        print(f"\n  Differential feedback domains ({len(diff_attr)} with attractor):")
        for pname in PREDICTOR_NAMES:
            correct = sum(1 for r in diff_attr if r.correct[pname])
            acc = correct / len(diff_attr) if diff_attr else 0
            print(f"    {short_names[pname]:<10} {correct}/{len(diff_attr)} ({acc:.0%})")
    if succ_attr:
        print(f"\n  All-success domains ({len(succ_attr)} with attractor):")
        for pname in PREDICTOR_NAMES:
            correct = sum(1 for r in succ_attr if r.correct[pname])
            acc = correct / len(succ_attr) if succ_attr else 0
            print(f"    {short_names[pname]:<10} {correct}/{len(succ_attr)} ({acc:.0%})")


if __name__ == "__main__":
    main()
