"""
Multi-Attractor Dynamics Experiment
====================================
Open Question #7: In larger landscapes, do multiple attractors
compete?  Does that correspond to galaxy formation?

C75 established: attractor formation requires (1) topological choice
and (2) differential feedback.  This experiment tests what happens
when the landscape is large enough for MULTIPLE attractor basins.

Setup:
  - 25 states in 5 clusters (A1-A5, B1-B5, C1-C5, D1-D5, E1-E5)
  - Fully connected (600 directed edges), uniform Δ=0.5, R₀=1.0
  - Differential execute_fn: intra-cluster = SUCCESS,
    inter-cluster = FAILURE with probability P_FAIL
  - No goal — free navigation for N_STEPS cycles
  - Measure: per-cluster load concentration, attractor count

Variations:
  V1: P_FAIL = 0.7 (strong cluster boundaries)
  V2: P_FAIL = 0.3 (weak cluster boundaries)
  V3: P_FAIL = 1.0 (impermeable walls)
  V4: Asymmetric — cluster A has P_FAIL=0.3, rest P_FAIL=0.9
      (one dominant vs four subordinate clusters)

Usage:
  py -3 -m e0_controller.explore_multi_attractor
"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Set, Tuple

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller


# ══════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════

CLUSTERS = ["A", "B", "C", "D", "E"]
CLUSTER_SIZE = 5
N_RUNS = 30            # repeated navigations
MAX_CYCLES = 50        # per run
SEED = 42


# ══════════════════════════════════════════════
# Cluster-based execute_fn factory
# ══════════════════════════════════════════════

def _cluster_of(state: str) -> str:
    """Extract cluster letter from state name (e.g., 'A3' → 'A')."""
    return state[0]


def make_cluster_execute_fn(
    p_fail_inter: float = 0.7,
    asymmetric: Dict[str, float] | None = None,
    rng: random.Random | None = None,
) -> Callable[[str, str], Outcome]:
    """Create an execute_fn with cluster-based differential feedback.

    Intra-cluster transitions always succeed.
    Inter-cluster transitions fail with probability p_fail_inter
    (or per-cluster override from asymmetric dict).
    """
    _rng = rng or random.Random(SEED)

    def execute(source: str, target: str) -> Outcome:
        src_cluster = _cluster_of(source)
        tgt_cluster = _cluster_of(target)
        if src_cluster == tgt_cluster:
            return Outcome.SUCCESS
        # Inter-cluster: check asymmetric override
        p = p_fail_inter
        if asymmetric and src_cluster in asymmetric:
            p = asymmetric[src_cluster]
        if _rng.random() < p:
            return Outcome.FAILURE
        return Outcome.SUCCESS

    return execute


# ══════════════════════════════════════════════
# Cluster Metrics
# ══════════════════════════════════════════════

@dataclass
class ClusterMetrics:
    """Aggregate metrics for one cluster."""
    cluster: str
    total_incoming_load: float = 0.0
    total_outgoing_load: float = 0.0
    mean_incoming_quality: float = 0.0
    total_visits: int = 0
    top_state: str = ""
    top_state_load: float = 0.0


@dataclass
class MultiAttractorResult:
    """Result of one multi-attractor experiment variant."""
    variant: str
    description: str
    n_states: int
    n_edges: int
    total_steps: int
    cluster_metrics: List[ClusterMetrics]
    # Per-state detail
    state_loads: Dict[str, float] = field(default_factory=dict)
    state_visits: Dict[str, int] = field(default_factory=dict)
    # Derived
    n_attractors: int = 0             # clusters with ratio > 1.5× per-cluster baseline
    dominant_cluster: str = ""
    gini_coefficient: float = 0.0     # inequality of load across clusters


def build_cluster_landscape() -> Tuple[Landscape, List[str]]:
    """Build a 25-state landscape with 5 clusters.

    Intra-cluster: fully connected (5×4=20 edges per cluster, 100 total)
    Inter-cluster: 1 bridge between adjacent clusters
    (A↔B, B↔C, C↔D, D↔E, E↔A) = 10 directed bridge edges

    Total: 110 edges.  Topology provides partial isolation.
    """
    states = []
    for c in CLUSTERS:
        for i in range(1, CLUSTER_SIZE + 1):
            states.append(f"{c}{i}")
    L = Landscape()
    for s in states:
        L.add_state(s)

    # Intra-cluster: fully connected
    for c in CLUSTERS:
        c_states = [f"{c}{i}" for i in range(1, CLUSTER_SIZE + 1)]
        for a in c_states:
            for b in c_states:
                if a != b:
                    L.add_edge(a, b, delta=0.5, resistance=1.0)

    # Inter-cluster bridges: adjacent clusters connected via state 1
    bridges = [("A", "B"), ("B", "C"), ("C", "D"), ("D", "E"), ("E", "A")]
    for c1, c2 in bridges:
        L.add_edge(f"{c1}1", f"{c2}1", delta=0.3, resistance=2.0)
        L.add_edge(f"{c2}1", f"{c1}1", delta=0.3, resistance=2.0)

    return L, states


def compute_gini(values: List[float]) -> float:
    """Compute Gini coefficient for a list of non-negative values."""
    if not values or sum(values) < 1e-12:
        return 0.0
    n = len(values)
    sorted_v = sorted(values)
    total = sum(sorted_v)
    cum = 0.0
    area = 0.0
    for v in sorted_v:
        cum += v
        area += cum
    # Gini = 1 - 2 * (area under Lorenz) / (n * total)
    return 1.0 - 2.0 * area / (n * total) + 1.0 / n


def run_variant(
    variant: str,
    description: str,
    execute_fn: Callable[[str, str], Outcome],
) -> MultiAttractorResult:
    """Run one experiment variant."""
    L, states = build_cluster_landscape()
    ctrl = E0Controller(L, execute_fn)
    H = L.historization

    total_steps = 0
    visit_counts: Dict[str, int] = defaultdict(int)

    # Rotate starting position through clusters:
    # Each cluster gets N_RUNS/5 starts from its first state.
    # This ensures all clusters get explored with SHARED historization.
    start_rotation = [f"{c}1" for c in CLUSTERS]
    for run_idx in range(N_RUNS):
        start = start_rotation[run_idx % len(start_rotation)]
        trace = ctrl.run(start, max_cycles=MAX_CYCLES)
        total_steps += len(trace.steps)
        visit_counts[start] += 1
        for step in trace.steps:
            visit_counts[step.target] += 1

    # Compute per-state loads
    state_loads: Dict[str, float] = {}
    for s in states:
        incoming = sum(
            H.trace_load(Edge(other, s))
            for other in states if other != s
        )
        state_loads[s] = incoming

    # Aggregate per cluster
    cluster_metrics: Dict[str, ClusterMetrics] = {}
    for c in CLUSTERS:
        cm = ClusterMetrics(cluster=c)
        c_states = [s for s in states if _cluster_of(s) == c]
        loads = [(s, state_loads.get(s, 0.0)) for s in c_states]
        cm.total_incoming_load = sum(l for _, l in loads)
        cm.total_visits = sum(visit_counts.get(s, 0) for s in c_states)

        # Mean incoming quality (load-weighted)
        total_q_w = 0.0
        total_w = 0.0
        for s in c_states:
            for other in states:
                if other != s:
                    edge = Edge(other, s)
                    load = H.trace_load(edge)
                    if load > 1e-12:
                        total_q_w += H.trace_quality(edge) * load
                        total_w += load
        cm.mean_incoming_quality = total_q_w / total_w if total_w > 1e-12 else 0.0

        # Outgoing load
        for s in c_states:
            for other in states:
                if other != s:
                    cm.total_outgoing_load += H.trace_load(Edge(s, other))

        # Top state in cluster
        if loads:
            top = max(loads, key=lambda x: x[1])
            cm.top_state = top[0]
            cm.top_state_load = top[1]

        cluster_metrics[c] = cm

    cm_list = sorted(cluster_metrics.values(),
                     key=lambda x: x.total_incoming_load, reverse=True)

    # Count attractors: cluster load > 1.5× uniform per-cluster baseline
    total_load = sum(cm.total_incoming_load for cm in cm_list)
    per_cluster_baseline = total_load / len(CLUSTERS) if total_load > 1e-12 else 0.0
    n_attractors = 0
    for cm in cm_list:
        if per_cluster_baseline > 1e-12:
            if cm.total_incoming_load / per_cluster_baseline > 1.5:
                n_attractors += 1

    # Gini of cluster loads
    cluster_loads = [cm.total_incoming_load for cm in cm_list]
    gini = compute_gini(cluster_loads)

    return MultiAttractorResult(
        variant=variant,
        description=description,
        n_states=len(states),
        n_edges=L.edge_count(),
        total_steps=total_steps,
        cluster_metrics=cm_list,
        state_loads=state_loads,
        state_visits=dict(visit_counts),
        n_attractors=n_attractors,
        dominant_cluster=cm_list[0].cluster if cm_list else "",
        gini_coefficient=gini,
    )


# ══════════════════════════════════════════════
# Experiment Variants
# ══════════════════════════════════════════════

def run_independent_variant(
    execute_fn_factory: Callable[[], Callable[[str, str], Outcome]],
) -> MultiAttractorResult:
    """V5: 5 independent controllers, one per cluster, each with own Landscape.

    Each controller starts in its cluster's first state and navigates freely.
    All 5 use the same topology and execute_fn, but separate Historization.
    After all runs, we merge the state metrics to see if 5 independent
    attractors coexist.
    """
    all_states: List[str] = []
    for c in CLUSTERS:
        for i in range(1, CLUSTER_SIZE + 1):
            all_states.append(f"{c}{i}")

    total_steps = 0
    visit_counts: Dict[str, int] = defaultdict(int)
    # Per-state incoming load from each independent controller
    combined_state_loads: Dict[str, float] = defaultdict(float)
    # Per-cluster metrics: track individually
    cluster_loads: Dict[str, float] = defaultdict(float)
    cluster_visits: Dict[str, int] = defaultdict(int)
    cluster_top: Dict[str, Tuple[str, float]] = {}
    cluster_quality: Dict[str, Tuple[float, float]] = {}  # (sum_q*w, sum_w)

    for c in CLUSTERS:
        # Each controller gets its own landscape + historization
        execute_fn = execute_fn_factory()
        L, states = build_cluster_landscape()
        ctrl = E0Controller(L, execute_fn)
        H = L.historization

        start = f"{c}1"
        runs_per_cluster = N_RUNS // len(CLUSTERS)
        for _ in range(runs_per_cluster):
            trace = ctrl.run(start, max_cycles=MAX_CYCLES)
            total_steps += len(trace.steps)
            visit_counts[start] += 1
            for step in trace.steps:
                visit_counts[step.target] += 1

        # Measure this controller's state loads
        for s in states:
            incoming = sum(
                H.trace_load(Edge(other, s))
                for other in states if other != s
            )
            combined_state_loads[s] += incoming

        # Aggregate per cluster from this controller
        for cc in CLUSTERS:
            c_states = [s for s in states if _cluster_of(s) == cc]
            c_load = sum(combined_state_loads.get(s, 0) for s in c_states)
            # Only count this controller's contribution meaningfully
            # for the cluster it explored

    # Now build final cluster metrics from combined state loads
    cm_list = []
    total_all = sum(combined_state_loads.values())
    for c in CLUSTERS:
        c_states = [s for s in all_states if _cluster_of(s) == c]
        cm = ClusterMetrics(cluster=c)
        cm.total_incoming_load = sum(combined_state_loads.get(s, 0) for s in c_states)
        cm.total_visits = sum(visit_counts.get(s, 0) for s in c_states)
        # Top state
        top_s, top_l = "", 0.0
        for s in c_states:
            l = combined_state_loads.get(s, 0)
            if l > top_l:
                top_s, top_l = s, l
        cm.top_state = top_s
        cm.top_state_load = top_l
        cm_list.append(cm)

    cm_list.sort(key=lambda x: x.total_incoming_load, reverse=True)

    # Count attractors
    per_cluster_baseline = total_all / len(CLUSTERS) if total_all > 1e-12 else 0.0
    n_attractors = 0
    for cm in cm_list:
        if per_cluster_baseline > 1e-12:
            if cm.total_incoming_load / per_cluster_baseline > 0.5:
                n_attractors += 1

    cluster_load_vals = [cm.total_incoming_load for cm in cm_list]
    gini = compute_gini(cluster_load_vals)

    return MultiAttractorResult(
        variant="V5",
        description="Independent controllers (1 per cluster, separate Historization)",
        n_states=len(all_states),
        n_edges=600,
        total_steps=total_steps,
        cluster_metrics=cm_list,
        state_loads=dict(combined_state_loads),
        state_visits=dict(visit_counts),
        n_attractors=n_attractors,
        dominant_cluster=cm_list[0].cluster if cm_list else "",
        gini_coefficient=gini,
    )


def run_all_variants() -> List[MultiAttractorResult]:
    results = []

    # V1: Strong cluster boundaries
    results.append(run_variant(
        "V1", "Strong boundaries (P_fail=0.7)",
        make_cluster_execute_fn(p_fail_inter=0.7, rng=random.Random(SEED)),
    ))

    # V2: Weak cluster boundaries
    results.append(run_variant(
        "V2", "Weak boundaries (P_fail=0.3)",
        make_cluster_execute_fn(p_fail_inter=0.3, rng=random.Random(SEED)),
    ))

    # V3: Impermeable walls
    results.append(run_variant(
        "V3", "Impermeable walls (P_fail=1.0)",
        make_cluster_execute_fn(p_fail_inter=1.0, rng=random.Random(SEED)),
    ))

    # V4: Asymmetric — cluster A permeable, rest hard
    results.append(run_variant(
        "V4", "Asymmetric (A: P=0.3, rest: P=0.9)",
        make_cluster_execute_fn(
            p_fail_inter=0.9,
            asymmetric={"A": 0.3},
            rng=random.Random(SEED),
        ),
    ))

    # V5: Independent controllers — one per cluster with own Historization
    results.append(run_independent_variant(
        lambda: make_cluster_execute_fn(p_fail_inter=0.7, rng=random.Random(SEED)),
    ))

    return results


# ══════════════════════════════════════════════
# Printing
# ══════════════════════════════════════════════

def print_results(results: List[MultiAttractorResult]) -> None:
    print("=" * 90)
    print("MULTI-ATTRACTOR DYNAMICS EXPERIMENT")
    print(f"Config: {len(CLUSTERS)} clusters × {CLUSTER_SIZE} states = "
          f"{len(CLUSTERS) * CLUSTER_SIZE} states, clustered topology "
          f"(intra-FC + bridges), "
          f"N_RUNS={N_RUNS}, MAX_CYCLES={MAX_CYCLES}")
    print("=" * 90)

    for r in results:
        print()
        print(f"━━━ {r.variant}: {r.description} ━━━")
        print(f"    Steps: {r.total_steps}, Attractors: {r.n_attractors}, "
              f"Gini: {r.gini_coefficient:.3f}, Dominant: {r.dominant_cluster}")
        print()
        header = (f"    {'Cluster':<8} {'In-Load':>10} {'Out-Load':>10} "
                  f"{'In-Qual':>8} {'Visits':>8} {'Top State':<8} {'Top Load':>10}")
        print(header)
        print("    " + "-" * (len(header) - 4))
        total_load = sum(cm.total_incoming_load for cm in r.cluster_metrics)
        for cm in r.cluster_metrics:
            pct = (100 * cm.total_incoming_load / total_load
                   if total_load > 1e-12 else 0)
            print(f"    {cm.cluster:<8} {cm.total_incoming_load:>10.2f} "
                  f"{cm.total_outgoing_load:>10.2f} {cm.mean_incoming_quality:>+8.3f} "
                  f"{cm.total_visits:>8} {cm.top_state:<8} {cm.top_state_load:>10.2f}"
                  f"  ({pct:4.1f}%)")

    # ── Cross-variant comparison ──
    print()
    print("━" * 90)
    print("CROSS-VARIANT COMPARISON")
    print("━" * 90)
    header = (f"{'Variant':<6} {'Description':<38} {'Attractors':>10} "
              f"{'Gini':>6} {'Dominant':>8} {'Dom%':>6}")
    print(header)
    print("-" * len(header))
    for r in results:
        total_load = sum(cm.total_incoming_load for cm in r.cluster_metrics)
        dom_load = r.cluster_metrics[0].total_incoming_load if r.cluster_metrics else 0
        dom_pct = 100 * dom_load / total_load if total_load > 1e-12 else 0
        print(f"{r.variant:<6} {r.description:<38} {r.n_attractors:>10} "
              f"{r.gini_coefficient:>6.3f} {r.dominant_cluster:>8} {dom_pct:>5.1f}%")

    # ── Key insight ──
    print()
    multi_count = sum(1 for r in results if r.n_attractors > 1)
    single_count = sum(1 for r in results if r.n_attractors == 1)
    zero_count = sum(1 for r in results if r.n_attractors == 0)
    print(f"Multi-attractor: {multi_count}/{len(results)} variants")
    print(f"Single attractor: {single_count}/{len(results)} variants")
    print(f"No attractor: {zero_count}/{len(results)} variants")

    if multi_count > 0:
        print("\nRESULT: Multiple attractors CAN coexist — galaxy formation confirmed.")
    else:
        print("\nRESULT: No multi-attractor dynamics observed in this configuration.")


def main():
    results = run_all_variants()
    print_results(results)


if __name__ == "__main__":
    main()
