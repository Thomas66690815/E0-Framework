"""
C184b: Real-World Validation — BPI Challenge 2017 (Loan Application Workflow)

Second real-world domain for E₀: business process workflow with genuine
structural traps (rework loops, rejection dead-ends).

Data: 31,509 loan applications, 1.2M events (van Dongen, 4TU.ResearchData 2017).

Key question: Can E₀'s interference detect the rework loop trap that greedy
(most-frequent-transition) falls into?

Domain properties vs Wikispeedia:
  - 24 unique activities (compact graph, no subgraph extraction needed)
  - Moderate degree (3-8 outgoing transitions per activity)
  - Genuine structural trap: A_Validating → O_Returned → A_Incomplete → loop
  - Irreversible dead-ends: A_Cancelled (33%), A_Denied (12%)
  - Clear success terminal: A_Pending (55%)

Δ mapping:  1 - success_rate(target)  — distance from success
R₀ mapping: failure_rate(target) + 1/sqrt(out-degree)  — navigability risk
"""

from __future__ import annotations

import gzip
import math
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from collections import Counter, defaultdict
import xml.etree.ElementTree as ET

from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller, HybridMode
from e0_controller.primitives import Outcome


# ─────────────────────── Data paths ───────────────────────

DATA_DIR = Path(__file__).parent.parent / "data" / "bpi2017"
XES_FILE = DATA_DIR / "BPI_Challenge_2017.xes.gz"


# ─────────────────────── Data structures ───────────────────────

@dataclass
class ProcessGraph:
    """Aggregate transition graph from BPI 2017 event log."""
    activities: list[str]                          # unique activity names
    activity_set: frozenset[str] = field(repr=False, default=frozenset())
    transitions: Dict[Tuple[str, str], int] = field(default_factory=dict)  # (from, to) → count
    out_edges: Dict[str, list[str]] = field(default_factory=dict)  # activity → [targets]
    in_edges: Dict[str, list[str]] = field(default_factory=dict)   # activity → [sources]

    # Per-activity statistics (computed from cases)
    success_rate: Dict[str, float] = field(default_factory=dict)    # fraction reaching A_Pending
    cancel_rate: Dict[str, float] = field(default_factory=dict)     # fraction reaching A_Cancelled
    denial_rate: Dict[str, float] = field(default_factory=dict)     # fraction reaching A_Denied
    avg_remaining: Dict[str, float] = field(default_factory=dict)   # avg steps to case end

    # Case data
    case_sequences: list[list[str]] = field(default_factory=list, repr=False)
    case_outcomes: list[str] = field(default_factory=list, repr=False)

    def out_degree(self, act: str) -> int:
        return len(self.out_edges.get(act, []))

    def in_degree(self, act: str) -> int:
        return len(self.in_edges.get(act, []))

    def transition_count(self, src: str, tgt: str) -> int:
        return self.transitions.get((src, tgt), 0)

    def most_frequent_next(self, act: str) -> Optional[str]:
        """Return the most frequent outgoing transition (greedy choice)."""
        neighbors = self.out_edges.get(act, [])
        if not neighbors:
            return None
        return max(neighbors, key=lambda n: self.transitions.get((act, n), 0))


@dataclass
class CaseTrace:
    """A single loan application case."""
    case_id: str
    sequence: list[str]         # activity sequence (complete events only)
    outcome: str                # last A_ state (A_Pending, A_Cancelled, A_Denied)
    rework_count: int           # number of A_Incomplete visits
    num_offers: int             # number of O_Create Offer events


# ─────────────────────── XES parsing ───────────────────────

def parse_xes(max_cases: int = 32000) -> ProcessGraph:
    """Parse BPI Challenge 2017 XES file into a ProcessGraph.

    Extracts only 'complete' lifecycle events to build the activity
    transition graph. Computes per-activity success/failure rates.
    """
    # Phase 1: Extract case sequences
    transition_counts: Dict[Tuple[str, str], int] = Counter()
    activity_visits: Dict[str, int] = Counter()
    activity_to_pending: Dict[str, int] = Counter()
    activity_to_cancelled: Dict[str, int] = Counter()
    activity_to_denied: Dict[str, int] = Counter()
    activity_remaining: Dict[str, list] = defaultdict(list)

    case_sequences: list[list[str]] = []
    case_outcomes: list[str] = []
    case_count = 0

    with gzip.open(str(XES_FILE), 'rb') as f:
        context = ET.iterparse(f, events=('end',))
        current_events: list[tuple] = []

        for event, elem in context:
            tag = elem.tag.replace('{http://www.xes-standard.org/}', '')

            if tag == 'trace':
                case_count += 1
                complete = [(n, o) for n, lc, o in current_events if lc == 'complete']
                seq = [n for n, o in complete]

                if seq:
                    # Determine outcome
                    a_states = [n for n, o in complete if o == 'Application']
                    outcome = a_states[-1] if a_states else 'UNKNOWN'

                    case_sequences.append(seq)
                    case_outcomes.append(outcome)

                    # Build transitions
                    for i in range(len(seq) - 1):
                        transition_counts[(seq[i], seq[i + 1])] += 1

                    # Per-activity statistics
                    visited = set(seq)
                    for act in visited:
                        activity_visits[act] += 1
                        if outcome == 'A_Pending':
                            activity_to_pending[act] += 1
                        elif outcome == 'A_Cancelled':
                            activity_to_cancelled[act] += 1
                        elif outcome == 'A_Denied':
                            activity_to_denied[act] += 1

                    # Remaining steps from each occurrence
                    for pos, act in enumerate(seq):
                        activity_remaining[act].append(len(seq) - 1 - pos)

                current_events = []
                elem.clear()

            elif tag == 'event':
                name = lc = origin = None
                for child in elem:
                    k = child.get('key', '')
                    v = child.get('value', '')
                    if k == 'concept:name':
                        name = v
                    elif k == 'lifecycle:transition':
                        lc = v
                    elif k == 'EventOrigin':
                        origin = v
                if name:
                    current_events.append((name, lc, origin))

            if case_count >= max_cases:
                break

    # Phase 2: Build graph structure
    all_activities = sorted(set(a for pair in transition_counts for a in pair))
    out_edges: Dict[str, list[str]] = defaultdict(list)
    in_edges: Dict[str, list[str]] = defaultdict(list)

    for (src, tgt) in transition_counts:
        if tgt not in out_edges[src]:
            out_edges[src].append(tgt)
        if src not in in_edges[tgt]:
            in_edges[tgt].append(src)

    # Phase 3: Compute rates
    success_rate = {}
    cancel_rate = {}
    denial_rate = {}
    avg_remaining = {}

    for act in all_activities:
        visits = activity_visits.get(act, 0)
        if visits > 0:
            success_rate[act] = activity_to_pending.get(act, 0) / visits
            cancel_rate[act] = activity_to_cancelled.get(act, 0) / visits
            denial_rate[act] = activity_to_denied.get(act, 0) / visits
        else:
            success_rate[act] = 0.0
            cancel_rate[act] = 0.0
            denial_rate[act] = 0.0

        remaining = activity_remaining.get(act, [0])
        avg_remaining[act] = sum(remaining) / len(remaining)

    return ProcessGraph(
        activities=all_activities,
        activity_set=frozenset(all_activities),
        transitions=dict(transition_counts),
        out_edges=dict(out_edges),
        in_edges=dict(in_edges),
        success_rate=success_rate,
        cancel_rate=cancel_rate,
        denial_rate=denial_rate,
        avg_remaining=avg_remaining,
        case_sequences=case_sequences,
        case_outcomes=case_outcomes,
    )


# ─────────────────────── Δ and R₀ mapping ───────────────────────

# Terminal states
GOAL = "A_Pending"
TERMINALS_BAD = {"A_Cancelled", "A_Denied"}
TERMINALS_ALL = {GOAL} | TERMINALS_BAD


def compute_bfs_distance(graph: ProcessGraph, goal: str) -> Dict[str, int]:
    """BFS shortest path distance from each activity to goal (reverse edges)."""
    from collections import deque
    dist = {goal: 0}
    queue = deque([goal])

    while queue:
        node = queue.popleft()
        d = dist[node]
        # Traverse INCOMING edges (reverse BFS)
        for src in graph.in_edges.get(node, []):
            if src not in dist:
                dist[src] = d + 1
                queue.append(src)

    return dist


def compute_delta(
    graph: ProcessGraph,
    source: str,
    target: str,
    dist_to_goal: Dict[str, int],
    d_max: int = 12,
) -> float:
    """Compute Δ for edge source→target.

    Dual signal:
    - BFS distance to A_Pending (structural position)
    - Empirical failure rate (historical outcome)

    Δ = α * d(target, goal)/d_max + (1-α) * (1 - success_rate(target))
    with α = 0.5 (equal weight to structure and history).
    """
    # Structural component
    d = dist_to_goal.get(target, d_max)
    structural = d / d_max

    # Empirical component: failure rate
    success = graph.success_rate.get(target, 0.5)
    empirical = 1.0 - success

    # Blend
    delta = 0.5 * structural + 0.5 * empirical
    return max(0.05, min(1.0, delta))


def compute_resistance(
    graph: ProcessGraph,
    target: str,
) -> float:
    """Compute R₀ for edge pointing to target activity.

    R₀ combines:
    - Navigability: 1/sqrt(out_degree) — fewer exits = harder to recover
    - Risk: failure rate from target activity

    Terminal bad states get maximum resistance.
    """
    if target in TERMINALS_BAD:
        return 5.0

    deg = graph.out_degree(target)
    if deg == 0:
        return 5.0  # dead-end

    navigability = 1.0 / math.sqrt(deg)
    failure = 1.0 - graph.success_rate.get(target, 0.5)

    # Weight: 40% navigability + 60% failure risk
    r = 0.4 * navigability + 0.6 * failure
    return max(0.1, r * 3.0)  # scale to E₀ typical range


# ─────────────────────── Landscape construction ───────────────────────

def build_landscape(
    graph: ProcessGraph,
    min_edge_fraction: float = 0.01,
) -> Landscape:
    """Build E₀ Landscape from the BPI 2017 process graph.

    The full graph is small enough (24 nodes) — no subgraph extraction needed.

    min_edge_fraction: minimum fraction of outgoing transitions from source
        to include an edge. Filters rare outlier transitions that don't
        represent real routing options. Default 0.01 = at least 1%.
    """
    dist_to_goal = compute_bfs_distance(graph, GOAL)
    d_max = max(dist_to_goal.values()) if dist_to_goal else 12

    L = Landscape()
    for act in graph.activities:
        L.add_state(act)

    # Compute total outgoing per node for filtering
    total_out: Dict[str, int] = {}
    for src in graph.activities:
        total_out[src] = sum(
            graph.transitions.get((src, tgt), 0)
            for tgt in graph.out_edges.get(src, [])
        )

    edges_added = 0
    edges_filtered = 0
    for (src, tgt), count in graph.transitions.items():
        # Filter rare edges
        if total_out.get(src, 0) > 0:
            fraction = count / total_out[src]
            if fraction < min_edge_fraction:
                edges_filtered += 1
                continue

        delta = compute_delta(graph, src, tgt, dist_to_goal, d_max)
        resistance = compute_resistance(graph, tgt)
        L.add_edge(src, tgt, delta=delta, resistance=resistance)
        edges_added += 1

    return L, edges_added, edges_filtered


# ─────────────────────── Greedy baseline ───────────────────────

def run_greedy_frequent(
    graph: ProcessGraph,
    start: str,
    goal: str,
    max_steps: int = 50,
) -> Tuple[list[str], bool]:
    """Greedy baseline: always follow the most frequent transition."""
    path = [start]
    current = start
    visited_count: Dict[str, int] = defaultdict(int)
    visited_count[start] = 1

    for _ in range(max_steps):
        if current == goal:
            return path, True
        if current in TERMINALS_BAD:
            return path, False

        next_act = graph.most_frequent_next(current)
        if next_act is None:
            return path, False

        current = next_act
        path.append(current)
        visited_count[current] += 1

        # Detect infinite loop
        if visited_count[current] > 5:
            return path, False

    return path, current == goal


def run_greedy_success_rate(
    graph: ProcessGraph,
    start: str,
    goal: str,
    max_steps: int = 50,
) -> Tuple[list[str], bool]:
    """Smarter greedy: follow the neighbor with highest success rate."""
    path = [start]
    current = start
    visited_count: Dict[str, int] = defaultdict(int)
    visited_count[start] = 1

    for _ in range(max_steps):
        if current == goal:
            return path, True
        if current in TERMINALS_BAD:
            return path, False

        neighbors = graph.out_edges.get(current, [])
        if not neighbors:
            return path, False

        # Pick neighbor with highest success rate, break ties by fewer visits
        best = max(
            neighbors,
            key=lambda n: (
                graph.success_rate.get(n, 0),
                -visited_count.get(n, 0),
            ),
        )

        current = best
        path.append(current)
        visited_count[current] += 1

        if visited_count[current] > 5:
            return path, False

    return path, current == goal


# ─────────────────────── E₀ runner ───────────────────────

def run_e0(
    graph: ProcessGraph,
    start: str,
    goal: str,
    max_cycles: int = 50,
    hybrid_horizon: int = 3,
    confidence_threshold: float = 0.3,
) -> Tuple[list[str], bool, int, list[str]]:
    """Run E₀ controller on the process graph.

    Returns (path, reached_goal, num_overrides, trap_detections).
    """
    landscape, _, _ = build_landscape(graph)

    def execute_fn(source: str, target: str) -> Outcome:
        if target in graph.out_edges.get(source, []):
            return Outcome.SUCCESS
        return Outcome.FAILURE

    controller = E0Controller(
        landscape=landscape,
        execute_fn=execute_fn,
        alpha=2.0,
        recent_k=3,
        hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
        hybrid_horizon=hybrid_horizon,
        hybrid_goals={goal},
        hybrid_geometry="goal_reaching",
        confidence_threshold=confidence_threshold,
    )

    trace = controller.run(
        start=start,
        max_cycles=max_cycles,
        goal=goal,
        overlay_horizon=hybrid_horizon,
    )

    e0_path = trace.path
    reached = e0_path[-1] == goal if e0_path else False

    # Count overrides and trap detections
    overrides = 0
    traps = []
    for step in trace.steps:
        if step.overlay:
            ov = step.overlay
            if (ov.deterministic_choice and ov.amplitude_choice
                    and ov.deterministic_choice != ov.amplitude_choice):
                overrides += 1
            for ai in ov.action_infos:
                if ai.intensity < 0.05 and ai.path_count >= 2:
                    if ai.action not in traps:
                        traps.append(ai.action)

    return e0_path, reached, overrides, traps


# ─────────────────────── Human baseline from cases ───────────────────────

def compute_human_baselines(graph: ProcessGraph) -> dict:
    """Compute human (actual) process statistics for comparison."""
    success_cases = [
        seq for seq, out in zip(graph.case_sequences, graph.case_outcomes)
        if out == 'A_Pending'
    ]
    cancel_cases = [
        seq for seq, out in zip(graph.case_sequences, graph.case_outcomes)
        if out == 'A_Cancelled'
    ]
    denied_cases = [
        seq for seq, out in zip(graph.case_sequences, graph.case_outcomes)
        if out == 'A_Denied'
    ]

    total = len(graph.case_sequences)
    avg_success_len = sum(len(s) for s in success_cases) / len(success_cases) if success_cases else 0
    avg_cancel_len = sum(len(s) for s in cancel_cases) / len(cancel_cases) if cancel_cases else 0
    avg_denied_len = sum(len(s) for s in denied_cases) / len(denied_cases) if denied_cases else 0

    # Rework cycles in successful cases
    rework_in_success = [
        sum(1 for a in seq if a == 'A_Incomplete')
        for seq in success_cases
    ]
    avg_rework_success = sum(rework_in_success) / len(rework_in_success) if rework_in_success else 0

    return {
        'total_cases': total,
        'success_count': len(success_cases),
        'success_rate': len(success_cases) / total if total else 0,
        'cancel_count': len(cancel_cases),
        'denied_count': len(denied_cases),
        'avg_success_steps': avg_success_len,
        'avg_cancel_steps': avg_cancel_len,
        'avg_denied_steps': avg_denied_len,
        'avg_rework_in_success': avg_rework_success,
    }


# ─────────────────────── Main exploration ───────────────────────

def run_exploration():
    """Run the full BPI 2017 exploration."""

    print("=" * 70)
    print("C184b: Real-World Validation — BPI Challenge 2017")
    print("=" * 70)

    # Phase 1: Parse event log
    print("\n--- Phase 1: Parsing BPI 2017 event log ---")
    graph = parse_xes()
    print(f"  Cases:       {len(graph.case_sequences)}")
    print(f"  Activities:  {len(graph.activities)}")
    print(f"  Transitions: {len(graph.transitions)}")
    print(f"  Outcomes:    A_Pending={graph.case_outcomes.count('A_Pending')}, "
          f"A_Cancelled={graph.case_outcomes.count('A_Cancelled')}, "
          f"A_Denied={graph.case_outcomes.count('A_Denied')}")

    # Phase 2: Graph structure
    print("\n--- Phase 2: Process graph structure ---")
    dist_to_goal = compute_bfs_distance(graph, GOAL)

    # Build filtered landscape to show edge stats
    _, edges_added, edges_filtered = build_landscape(graph)
    print(f"  Landscape edges: {edges_added} (filtered {edges_filtered} rare transitions < 1%)")

    print(f"  BFS distance to {GOAL}:")
    for act in sorted(dist_to_goal.keys(), key=lambda a: dist_to_goal[a]):
        d = dist_to_goal[act]
        sr = graph.success_rate.get(act, 0)
        deg = graph.out_degree(act)
        print(f"    d={d}  sr={sr:.1%}  deg={deg:2d}  {act}")
    unreachable = [a for a in graph.activities if a not in dist_to_goal]
    if unreachable:
        print(f"  Unreachable from {GOAL}: {unreachable}")

    # Phase 3: Identify trap structure
    print("\n--- Phase 3: Trap structure analysis ---")
    # The rework loop
    loop_acts = ['A_Validating', 'O_Returned', 'A_Incomplete']
    print("  Rework loop: A_Validating → O_Returned → A_Incomplete → A_Validating")
    for act in loop_acts:
        print(f"    {act}: sr={graph.success_rate.get(act, 0):.1%}, "
              f"out-degree={graph.out_degree(act)}, "
              f"most_frequent_next={graph.most_frequent_next(act)}")

    # Show greedy path
    print("\n  Greedy (most-frequent) path prediction:")
    greedy_pred = []
    current = 'A_Create Application'
    for i in range(20):
        greedy_pred.append(current)
        if current == GOAL or current in TERMINALS_BAD:
            break
        nxt = graph.most_frequent_next(current)
        if nxt is None:
            break
        freq = graph.transition_count(current, nxt)
        total_out = sum(graph.transition_count(current, t) for t in graph.out_edges.get(current, []))
        print(f"    {i:2d}. {current:35s} → {nxt} ({freq}/{total_out} = {freq/total_out:.0%})")
        current = nxt
        if current in [a for a in greedy_pred[:-1]] and greedy_pred.count(current) >= 3:
            print(f"    ** LOOP DETECTED at {current} **")
            break
    print(f"    Greedy terminated at: {current} (steps: {len(greedy_pred)})")

    # Phase 4: Run baselines
    print("\n--- Phase 4: Running baselines ---")

    # Greedy (frequency)
    greedy_freq_path, greedy_freq_ok = run_greedy_frequent(
        graph, 'A_Create Application', GOAL, max_steps=50
    )
    print(f"  Greedy (frequency):     {'✓' if greedy_freq_ok else '✗'}  "
          f"steps={len(greedy_freq_path)-1}  "
          f"ended_at={greedy_freq_path[-1]}")
    if not greedy_freq_ok:
        # Show where it looped
        loop_visits = Counter(greedy_freq_path)
        loops = {a: c for a, c in loop_visits.items() if c > 1}
        print(f"    Loop visits: {loops}")

    # Greedy (success rate)
    greedy_sr_path, greedy_sr_ok = run_greedy_success_rate(
        graph, 'A_Create Application', GOAL, max_steps=50
    )
    print(f"  Greedy (success-rate):  {'✓' if greedy_sr_ok else '✗'}  "
          f"steps={len(greedy_sr_path)-1}  "
          f"ended_at={greedy_sr_path[-1]}")

    # Phase 5: Run E₀
    print("\n--- Phase 5: Running E₀ controller ---")
    for conf_thresh in [0.2, 0.3, 0.5]:
        for horizon in [3, 4]:
            e0_path, e0_ok, overrides, traps = run_e0(
                graph, 'A_Create Application', GOAL,
                max_cycles=50, hybrid_horizon=horizon,
                confidence_threshold=conf_thresh,
            )
            print(f"  E₀ (ct={conf_thresh}, h={horizon}):  "
                  f"{'✓' if e0_ok else '✗'}  "
                  f"steps={len(e0_path)-1:2d}  "
                  f"overrides={overrides:2d}  "
                  f"traps={traps}  "
                  f"ended_at={e0_path[-1]}")
            if e0_ok or conf_thresh == 0.3:
                # Print the path for the primary config
                if conf_thresh == 0.3 and horizon == 3:
                    print(f"    Path: {' → '.join(e0_path)}")

    # Phase 6: Human baseline
    print("\n--- Phase 6: Human (actual) process statistics ---")
    human = compute_human_baselines(graph)
    print(f"  Total cases:         {human['total_cases']}")
    print(f"  Success rate:        {human['success_rate']:.1%}")
    print(f"  Avg steps (success): {human['avg_success_steps']:.1f}")
    print(f"  Avg steps (cancel):  {human['avg_cancel_steps']:.1f}")
    print(f"  Avg steps (denied):  {human['avg_denied_steps']:.1f}")
    print(f"  Avg rework cycles (in successful cases): {human['avg_rework_in_success']:.2f}")

    # Phase 7: Comparison
    print("\n--- Phase 7: Comparison ---")
    # Find best E₀ config
    e0_path_best, e0_ok_best, overrides_best, traps_best = run_e0(
        graph, 'A_Create Application', GOAL,
        max_cycles=50, hybrid_horizon=3, confidence_threshold=0.3,
    )

    print(f"  {'Method':<30s}  {'Success':>7s}  {'Steps':>5s}  Notes")
    print(f"  {'-'*30}  {'-'*7}  {'-'*5}  {'-'*30}")
    print(f"  {'Greedy (frequency)':<30s}  {'✓' if greedy_freq_ok else '✗':>7s}  "
          f"{len(greedy_freq_path)-1:5d}  "
          f"{'LOOP in rework cycle' if not greedy_freq_ok else ''}")
    print(f"  {'Greedy (success-rate)':<30s}  {'✓' if greedy_sr_ok else '✗':>7s}  "
          f"{len(greedy_sr_path)-1:5d}  "
          f"{'Oracle: uses outcome knowledge' if greedy_sr_ok else ''}")
    print(f"  {'E₀ (ct=0.3, h=3)':<30s}  {'✓' if e0_ok_best else '✗':>7s}  "
          f"{len(e0_path_best)-1:5d}  "
          f"{overrides_best} overrides, traps: {traps_best}")
    print(f"  {'Human average (success)':<30s}  {'✓':>7s}  "
          f"{human['avg_success_steps']:5.1f}  "
          f"Only successful cases ({human['success_count']})")
    print(f"  {'Human average (all)':<30s}  "
          f"{human['success_rate']:6.1%}  "
          f"{sum(len(s) for s in graph.case_sequences)/len(graph.case_sequences):5.1f}  "
          f"Including failures")

    # Shortest possible path (BFS)
    from collections import deque
    bfs_path = bfs_shortest_path(graph, 'A_Create Application', GOAL)
    if bfs_path:
        print(f"  {'BFS optimal':<30s}  {'✓':>7s}  {len(bfs_path)-1:5d}  "
              f"Theoretical minimum")
        print(f"    Optimal path: {' → '.join(bfs_path)}")

    # Phase 8: Critical decision-point tests
    print("\n--- Phase 8: Decision-point tests ---")
    print("  The real test: can E₀ avoid the rework loop at A_Validating?")
    print()

    # Test starting from A_Validating (the trap entry point)
    decision_points = [
        ('A_Validating', 'Rework loop entry'),
        ('A_Complete', 'Before validation/cancellation'),
        ('O_Sent (mail and online)', 'Mid-process routing'),
    ]

    for start, description in decision_points:
        print(f"  Decision point: {start} — {description}")

        # Greedy (frequency)
        gf_path, gf_ok = run_greedy_frequent(graph, start, GOAL, max_steps=30)
        # Greedy (success-rate)
        gs_path, gs_ok = run_greedy_success_rate(graph, start, GOAL, max_steps=30)
        # E₀
        e0_dp_path, e0_dp_ok, e0_dp_ov, e0_dp_traps = run_e0(
            graph, start, GOAL, max_cycles=30, hybrid_horizon=3,
            confidence_threshold=0.3,
        )

        print(f"    Greedy(freq):   {'✓' if gf_ok else '✗'}  steps={len(gf_path)-1:2d}  "
              f"path={' → '.join(gf_path[:8])}{'...' if len(gf_path) > 8 else ''}")
        print(f"    Greedy(sr):     {'✓' if gs_ok else '✗'}  steps={len(gs_path)-1:2d}  "
              f"path={' → '.join(gs_path[:8])}")
        print(f"    E₀:             {'✓' if e0_dp_ok else '✗'}  steps={len(e0_dp_path)-1:2d}  "
              f"overrides={e0_dp_ov}  path={' → '.join(e0_dp_path[:8])}")
        print()

    print("\n" + "=" * 70)
    print("C184b exploration complete.")


def bfs_shortest_path(
    graph: ProcessGraph,
    start: str,
    goal: str,
) -> Optional[list[str]]:
    """Find shortest path from start to goal in the process graph."""
    from collections import deque
    parent = {start: None}
    queue = deque([start])

    while queue:
        node = queue.popleft()
        if node == goal:
            # Reconstruct path
            path = []
            current = goal
            while current is not None:
                path.append(current)
                current = parent[current]
            return list(reversed(path))
        for nb in graph.out_edges.get(node, []):
            if nb not in parent:
                parent[nb] = node
                queue.append(nb)

    return None


if __name__ == "__main__":
    run_exploration()
