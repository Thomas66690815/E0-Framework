"""
C185: E₀ Traffic Simulation

Living multi-agent system: vehicles navigate grid cities with congestion
bottlenecks.  Each vehicle is an independent E₀ agent with shared road
topology but individual historization (personal jam memory).

Phase 1 — Uniform Grid (5×4):
    20 intersections, 62 directed road segments.
    Central bottleneck: r2_c1 and r2_c2 (capacity 1).
    Finding: conservative interference (conf=0.85) wins by 4–6%.

Phase 2 — River City (6×8):
    42 intersections, river at row 3, two bridges at columns 2 and 5.
    All north→south traffic forced through bridges (capacity 1).
    Finding: interference wins by 10–28% (structural smoking gun).
    Key insight: historization ALONE hurts in bridge topology — it raises
    R_eff on bridge edges after failure, causing vehicles to detour
    sideways (never crosses river).  The overlay corrects this by seeing
    at depth 3 that the OTHER bridge is free.

Strategies compared:
    RANDOM          — pick a random neighbor each tick
    GREEDY_DELTA    — always step toward goal (lowest Manhattan distance)
    BFS_SHORTEST    — follow precomputed shortest path
    E0_GREEDY       — E₀ with historization, no amplitude overlay
    E0_FULL         — E₀ with amplitude overlay (confidence=0.5)
    E0_CONSERVATIVE — E₀ with amplitude overlay (confidence=0.85)

Δ mapping:   manhattan_distance(edge_target, vehicle_goal) / d_max
R₀ mapping:  1.0 (uniform)
"""

from __future__ import annotations

import math
import random
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Set, Tuple

from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller, HybridMode
from e0_controller.primitives import Outcome, Edge


# ─────────────────────── Grid city ───────────────────────

ROWS = 5
COLS = 4
BOTTLENECK_NODES = {"r2_c1", "r2_c2"}
DEFAULT_CAPACITY = 3
BOTTLENECK_CAPACITY = 1


def node_name(r: int, c: int) -> str:
    return f"r{r}_c{c}"


def parse_node(name: str) -> Tuple[int, int]:
    parts = name.split("_")
    return int(parts[0][1:]), int(parts[1][1:])


def manhattan(a: str, b: str) -> int:
    r1, c1 = parse_node(a)
    r2, c2 = parse_node(b)
    return abs(r1 - r2) + abs(c1 - c2)


@dataclass
class CityGrid:
    rows: int
    cols: int
    nodes: List[str]
    edges: List[Tuple[str, str]]              # directed (src, tgt)
    neighbors: Dict[str, List[str]]           # node → [neighbor, …]
    capacity: Dict[str, int]                  # node → max vehicles
    d_max: int                                # max Manhattan distance

    @classmethod
    def build(
        cls,
        rows: int = ROWS,
        cols: int = COLS,
        bottleneck_nodes: Optional[Set[str]] = None,
    ) -> "CityGrid":
        if bottleneck_nodes is None:
            bottleneck_nodes = BOTTLENECK_NODES
        nodes = [node_name(r, c) for r in range(rows) for c in range(cols)]
        edges: List[Tuple[str, str]] = []
        nbrs: Dict[str, List[str]] = defaultdict(list)
        for r in range(rows):
            for c in range(cols):
                n = node_name(r, c)
                for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < cols:
                        m = node_name(nr, nc)
                        edges.append((n, m))
                        nbrs[n].append(m)
        cap = {
            n: (BOTTLENECK_CAPACITY if n in bottleneck_nodes else DEFAULT_CAPACITY)
            for n in nodes
        }
        d_max = (rows - 1) + (cols - 1)
        return cls(
            rows=rows, cols=cols, nodes=nodes, edges=edges,
            neighbors=dict(nbrs), capacity=cap, d_max=d_max,
        )

    @classmethod
    def build_river_city(
        cls,
        rows: int = 6,
        cols: int = 8,
        river_row: int = 3,
        bridge_cols: Optional[Set[int]] = None,
    ) -> "CityGrid":
        """Build a city with a river and two bridges.

        The river runs horizontally at river_row.  Only bridge columns
        have nodes at the river row, creating forced chokepoints.
        Bridge nodes have capacity 1; all others have DEFAULT_CAPACITY.

        This topology is designed to expose the overlay advantage:
        historization alone punishes bridge edges after failure and
        diverts vehicles sideways (never crossing the river), while
        the amplitude overlay sees at depth 3 that the OTHER bridge
        is free and routes there instead.
        """
        if bridge_cols is None:
            bridge_cols = {2, 5}
        nodes: List[str] = []
        edges: List[Tuple[str, str]] = []
        nbrs: Dict[str, List[str]] = defaultdict(list)
        cap: Dict[str, int] = {}
        for r in range(rows):
            for c in range(cols):
                if r == river_row and c not in bridge_cols:
                    continue  # river — no node here
                n = node_name(r, c)
                nodes.append(n)
                cap[n] = BOTTLENECK_CAPACITY if r == river_row else DEFAULT_CAPACITY
        node_set = set(nodes)
        for r in range(rows):
            for c in range(cols):
                n = node_name(r, c)
                if n not in node_set:
                    continue
                for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                    m = node_name(r + dr, c + dc)
                    if m in node_set:
                        edges.append((n, m))
                        nbrs[n].append(m)
        d_max = (rows - 1) + (cols - 1)
        return cls(
            rows=rows, cols=cols, nodes=nodes, edges=edges,
            neighbors=dict(nbrs), capacity=cap, d_max=d_max,
        )


# ─────────────────────── BFS all-pairs ───────────────────────

def bfs_next_hop(city: CityGrid) -> Dict[Tuple[str, str], str]:
    """Precompute next-hop for shortest path between all node pairs.

    Returns dict[(source, goal)] → next_node_on_shortest_path.
    Ties broken by lowest node name for determinism.
    """
    table: Dict[Tuple[str, str], str] = {}
    for goal in city.nodes:
        # Reverse BFS from goal
        parent: Dict[str, Optional[str]] = {goal: None}
        queue: deque[str] = deque([goal])
        while queue:
            node = queue.popleft()
            for prev in city.neighbors.get(node, []):
                if prev not in parent:
                    parent[prev] = node
                    queue.append(prev)
        # Extract next-hop
        for src in city.nodes:
            if src == goal:
                continue
            if src in parent:
                table[(src, goal)] = parent[src]
    return table


# ─────────────────────── Landscape per vehicle ───────────────────────

def build_vehicle_landscape(city: CityGrid, goal: str) -> Landscape:
    """Build a Landscape for one vehicle targeting goal.

    All vehicles share the same topology but each gets its own
    Historization (created automatically by Landscape()).
    """
    L = Landscape()
    for n in city.nodes:
        L.add_state(n)
    d_max = city.d_max or 1
    for src, tgt in city.edges:
        delta = manhattan(tgt, goal) / d_max
        delta = max(0.05, min(1.0, delta))
        L.add_edge(src, tgt, delta=delta, resistance=1.0)
    return L


def update_landscape_goal(landscape: Landscape, city: CityGrid, goal: str) -> None:
    """Recompute Δ for all edges to point toward a new goal.

    Preserves historization (personal jam memory carries over).
    """
    d_max = city.d_max or 1
    for src, tgt in city.edges:
        new_delta = manhattan(tgt, goal) / d_max
        new_delta = max(0.05, min(1.0, new_delta))
        landscape.adjust_delta(src, tgt, new_delta)


# ─────────────────────── Strategy enum ───────────────────────

class Strategy(Enum):
    RANDOM = "random"
    GREEDY_DELTA = "greedy_delta"
    BFS_SHORTEST = "bfs_shortest"
    E0_GREEDY = "e0_greedy"
    E0_FULL = "e0_full"
    E0_CONSERVATIVE = "e0_conservative"  # high confidence threshold


# ─────────────────────── Vehicle ───────────────────────

@dataclass
class Vehicle:
    name: str
    position: str
    goal: str
    strategy: Strategy
    trip_start_tick: int = 0
    trips_completed: int = 0
    trip_times: List[int] = field(default_factory=list)
    total_stuck: int = 0
    trip_stuck: int = 0                # stuck events for current trip
    consecutive_stuck: int = 0         # consecutive ticks stuck (for escape)
    overrides: int = 0

    # E₀ internals (only for E0_GREEDY / E0_FULL)
    landscape: Optional[Landscape] = field(default=None, repr=False)
    controller: Optional[E0Controller] = field(default=None, repr=False)


# ─────────────────────── Congestion model ───────────────────────

def count_at(positions: Dict[str, str], node: str, exclude: str = "") -> int:
    """Count vehicles at a node, optionally excluding one vehicle."""
    return sum(1 for v, pos in positions.items() if pos == node and v != exclude)


def make_execute_fn(
    vehicle_name: str,
    positions: Dict[str, str],
    capacity: Dict[str, int],
) -> Callable[[str, str], Outcome]:
    """Create execute_fn that checks global congestion state."""
    def execute_fn(source: str, target: str) -> Outcome:
        current_count = count_at(positions, target, exclude=vehicle_name)
        if current_count >= capacity.get(target, DEFAULT_CAPACITY):
            return Outcome.FAILURE
        return Outcome.SUCCESS
    return execute_fn


# ─────────────────────── Congestion-aware R₀ update ───────────────────

IMPATIENCE_THRESHOLD = 3   # stuck this many ticks → try random neighbor
CONGESTION_PENALTY = 3.0   # R₀ penalty scaling for congested nodes


def update_congestion_r0(
    vehicles: List[Vehicle],
    positions: Dict[str, str],
    city: CityGrid,
) -> None:
    """Update R₀ for all edges entering congested intersections.

    This gives every E₀ agent a real-time 'traffic report':
    edges pointing at busy intersections get higher base resistance.
    The amplitude overlay can then detect congested paths at depth
    and route around them — the look-ahead advantage over greedy.
    """
    congestion: Dict[str, float] = {}
    for node in city.nodes:
        count = count_at(positions, node)
        cap = city.capacity.get(node, DEFAULT_CAPACITY)
        congestion[node] = count / cap   # 0.0 … 1.0+

    for v in vehicles:
        if v.landscape is None:
            continue
        for src, tgt in city.edges:
            penalty = congestion.get(tgt, 0.0) * CONGESTION_PENALTY
            v.landscape.adjust_base_resistance(src, tgt, 1.0 + penalty)


# ─────────────────────── Simple routing (non-E₀ baselines) ───────────

def pick_random(position: str, city: CityGrid) -> Optional[str]:
    nbrs = city.neighbors.get(position, [])
    return random.choice(nbrs) if nbrs else None


def pick_greedy(position: str, goal: str, city: CityGrid) -> Optional[str]:
    """Pick neighbor closest to goal (Manhattan). Ties broken randomly."""
    nbrs = city.neighbors.get(position, [])
    if not nbrs:
        return None
    best_dist = min(manhattan(n, goal) for n in nbrs)
    candidates = [n for n in nbrs if manhattan(n, goal) == best_dist]
    return random.choice(candidates)


# ─────────────────────── Simulation core ───────────────────────

@dataclass
class TripRecord:
    vehicle: str
    start_pos: str
    goal: str
    ticks: int
    stuck_events: int


@dataclass
class TickSnapshot:
    tick: int
    positions: Dict[str, str]
    congested: List[str]          # nodes at capacity
    trips_so_far: int


@dataclass
class SimResult:
    strategy: Strategy
    total_ticks: int
    trips: List[TripRecord]
    snapshots: List[TickSnapshot]
    total_stuck: int
    total_overrides: int

    @property
    def trips_completed(self) -> int:
        return len(self.trips)

    @property
    def avg_trip_time(self) -> float:
        if not self.trips:
            return float("inf")
        return sum(t.ticks for t in self.trips) / len(self.trips)

    @property
    def throughput_per_100(self) -> float:
        if self.total_ticks == 0:
            return 0.0
        return self.trips_completed / self.total_ticks * 100


def spawn_vehicles(
    city: CityGrid,
    n: int,
    strategy: Strategy,
    positions: Dict[str, str],
    bfs_table: Dict[Tuple[str, str], str],
    epistemic_trust: bool = False,
) -> List[Vehicle]:
    """Create n vehicles at random positions with random goals."""
    vehicles = []
    for i in range(n):
        pos = random.choice(city.nodes)
        goal = random.choice([nd for nd in city.nodes if nd != pos])
        v = Vehicle(name=f"v{i}", position=pos, goal=goal, strategy=strategy)

        # Register in global positions (for congestion checks)
        positions[v.name] = v.position

        # Build E₀ internals if needed
        if strategy in (Strategy.E0_GREEDY, Strategy.E0_FULL, Strategy.E0_CONSERVATIVE):
            v.landscape = build_vehicle_landscape(city, goal)
            if strategy == Strategy.E0_GREEDY:
                mode = HybridMode.GREEDY
                horizon = 0
                conf = 1.0
            elif strategy == Strategy.E0_FULL:
                mode = HybridMode.AMPLITUDE_ON_DISAGREE
                horizon = 3
                conf = 0.5
            else:  # E0_CONSERVATIVE
                mode = HybridMode.AMPLITUDE_ON_DISAGREE
                horizon = 3
                conf = 0.85
            v.controller = E0Controller(
                landscape=v.landscape,
                execute_fn=make_execute_fn(v.name, positions, city.capacity),
                alpha=2.0,
                recent_k=3,
                hybrid_mode=mode,
                hybrid_horizon=horizon,
                hybrid_goals={goal},
                hybrid_geometry="goal_reaching",
                confidence_threshold=conf,
                epistemic_trust=epistemic_trust,
            )

        vehicles.append(v)
    return vehicles


def recycle_vehicle(
    v: Vehicle,
    city: CityGrid,
    tick: int,
    positions: Dict[str, str],
) -> TripRecord:
    """Record completed trip and assign new goal."""
    trip = TripRecord(
        vehicle=v.name,
        start_pos=v.position,  # == old goal
        goal=v.goal,
        ticks=tick - v.trip_start_tick,
        stuck_events=v.trip_stuck,
    )
    v.trips_completed += 1
    v.trip_times.append(trip.ticks)
    v.trip_stuck = 0
    v.consecutive_stuck = 0

    # New goal
    new_goal = random.choice([nd for nd in city.nodes if nd != v.position])
    v.goal = new_goal
    v.trip_start_tick = tick

    # Update E₀ internals
    if v.landscape is not None:
        update_landscape_goal(v.landscape, city, new_goal)
    if v.controller is not None:
        v.controller.hybrid_goals = {new_goal}

    return trip


def run_simulation(
    city: CityGrid,
    n_vehicles: int = 10,
    n_ticks: int = 500,
    strategy: Strategy = Strategy.E0_FULL,
    bfs_table: Optional[Dict[Tuple[str, str], str]] = None,
    snapshot_interval: int = 50,
    epistemic_trust: bool = False,
) -> SimResult:
    """Run tick-based traffic simulation."""
    if bfs_table is None:
        bfs_table = bfs_next_hop(city)

    positions: Dict[str, str] = {}
    vehicles = spawn_vehicles(city, n_vehicles, strategy, positions, bfs_table,
                              epistemic_trust=epistemic_trust)

    all_trips: List[TripRecord] = []
    snapshots: List[TickSnapshot] = []
    total_stuck = 0
    total_overrides = 0

    for tick in range(n_ticks):
        order = list(vehicles)
        random.shuffle(order)

        for v in order:
            # Check if already at goal
            if v.position == v.goal:
                trip = recycle_vehicle(v, city, tick, positions)
                all_trips.append(trip)
                continue

            # === Choose and execute move ===
            if v.strategy == Strategy.RANDOM:
                target = pick_random(v.position, city)
                if target is None:
                    continue
                if count_at(positions, target, v.name) >= city.capacity.get(target, DEFAULT_CAPACITY):
                    v.total_stuck += 1
                    v.trip_stuck += 1
                    v.consecutive_stuck += 1
                    total_stuck += 1
                else:
                    v.position = target
                    positions[v.name] = target
                    v.consecutive_stuck = 0

            elif v.strategy == Strategy.GREEDY_DELTA:
                # Impatient driver: if stuck too long, try random detour
                if v.consecutive_stuck >= IMPATIENCE_THRESHOLD:
                    target = pick_random(v.position, city)
                else:
                    target = pick_greedy(v.position, v.goal, city)
                if target is None:
                    continue
                if count_at(positions, target, v.name) >= city.capacity.get(target, DEFAULT_CAPACITY):
                    v.total_stuck += 1
                    v.trip_stuck += 1
                    v.consecutive_stuck += 1
                    total_stuck += 1
                else:
                    v.position = target
                    positions[v.name] = target
                    v.consecutive_stuck = 0

            elif v.strategy == Strategy.BFS_SHORTEST:
                key = (v.position, v.goal)
                if v.consecutive_stuck >= IMPATIENCE_THRESHOLD:
                    target = pick_random(v.position, city)
                else:
                    target = bfs_table.get(key)
                if target is None:
                    continue
                if count_at(positions, target, v.name) >= city.capacity.get(target, DEFAULT_CAPACITY):
                    v.total_stuck += 1
                    v.trip_stuck += 1
                    v.consecutive_stuck += 1
                    total_stuck += 1
                else:
                    v.position = target
                    positions[v.name] = target
                    v.consecutive_stuck = 0

            elif v.strategy in (Strategy.E0_GREEDY, Strategy.E0_FULL, Strategy.E0_CONSERVATIVE):
                assert v.controller is not None

                # Anti-gridlock: if stuck too long, bypass overlay
                if v.consecutive_stuck >= IMPATIENCE_THRESHOLD:
                    target = pick_random(v.position, city)
                    if target and count_at(positions, target, v.name) < city.capacity.get(target, DEFAULT_CAPACITY):
                        old_pos = v.position
                        v.position = target
                        positions[v.name] = target
                        v.consecutive_stuck = 0
                        # Historize escape so the vehicle learns this route exists
                        v.landscape.historization.update(
                            Edge(old_pos, target), Outcome.SUCCESS,
                        )
                    else:
                        v.total_stuck += 1
                        v.trip_stuck += 1
                        v.consecutive_stuck += 1
                        total_stuck += 1
                    continue

                step = v.controller.cycle(
                    v.position,
                    overlay_horizon=(3 if v.strategy in (Strategy.E0_FULL, Strategy.E0_CONSERVATIVE) else 0),
                    overlay_goals={v.goal},
                )
                if step is None:
                    continue

                if step.outcome == Outcome.SUCCESS:
                    v.position = step.target
                    positions[v.name] = step.target
                    v.consecutive_stuck = 0
                else:
                    v.total_stuck += 1
                    v.trip_stuck += 1
                    v.consecutive_stuck += 1
                    total_stuck += 1

                # Track overrides
                if step.overlay and step.hybrid_overridden:
                    v.overrides += 1
                    total_overrides += 1

        # Periodic snapshot
        if tick % snapshot_interval == 0:
            congested = [
                n for n in city.nodes
                if count_at(positions, n) >= city.capacity.get(n, DEFAULT_CAPACITY)
            ]
            snapshots.append(TickSnapshot(
                tick=tick,
                positions=dict(positions),
                congested=congested,
                trips_so_far=len(all_trips),
            ))

    return SimResult(
        strategy=strategy,
        total_ticks=n_ticks,
        trips=all_trips,
        snapshots=snapshots,
        total_stuck=total_stuck,
        total_overrides=total_overrides,
    )


# ─────────────────────── Analysis ───────────────────────

def print_comparison(results: Dict[Strategy, SimResult]) -> None:
    """Print comparison table of all strategies."""
    print("\n" + "=" * 78)
    print("C185: Traffic Simulation — Phase 1 Results")
    print("=" * 78)
    print(f"{'Strategy':<20} {'Trips':>6} {'Avg Time':>9} {'Thru/100':>9} "
          f"{'Stuck':>7} {'Overrides':>10}")
    print("-" * 78)
    for strat in Strategy:
        r = results.get(strat)
        if r is None:
            continue
        print(f"{strat.value:<20} {r.trips_completed:>6} "
              f"{r.avg_trip_time:>9.1f} {r.throughput_per_100:>9.1f} "
              f"{r.total_stuck:>7} {r.total_overrides:>10}")
    print("=" * 78)


def print_congestion_timeline(results: Dict[Strategy, SimResult]) -> None:
    """Show congestion over time for each strategy."""
    print("\n--- Congestion Timeline ---")
    for strat in Strategy:
        r = results.get(strat)
        if r is None:
            continue
        print(f"\n  {strat.value}:")
        for snap in r.snapshots:
            bar = "█" * len(snap.congested) + "·" * (5 - len(snap.congested))
            print(f"    tick {snap.tick:>4}  congested: {len(snap.congested):>2}  "
                  f"trips: {snap.trips_so_far:>4}  {bar}")


def print_interference_analysis(results: Dict[Strategy, SimResult]) -> None:
    """Analyze whether interference provides measurable advantage."""
    e0_g = results.get(Strategy.E0_GREEDY)
    e0_f = results.get(Strategy.E0_FULL)
    e0_c = results.get(Strategy.E0_CONSERVATIVE)
    greedy = results.get(Strategy.GREEDY_DELTA)

    if not (e0_g and e0_f and greedy):
        print("\n  (insufficient data for interference analysis)")
        return

    print("\n--- Interference Evidence ---")
    for label, e0_variant in [("E₀ full (conf=0.5)", e0_f),
                               ("E₀ conservative (conf=0.85)", e0_c)]:
        if e0_variant is None:
            continue
        print(f"\n  {label} vs E₀ greedy:")
        if e0_g.trips_completed > 0 and e0_variant.trips_completed > 0:
            speedup = e0_g.avg_trip_time / e0_variant.avg_trip_time
            print(f"    Trips:            {e0_variant.trips_completed} vs {e0_g.trips_completed}")
            print(f"    Avg trip time:    {e0_variant.avg_trip_time:.1f} vs {e0_g.avg_trip_time:.1f} "
                  f"({speedup:.2f}×)")
            print(f"    Overrides:        {e0_variant.total_overrides}")
            print(f"    Stuck events:     {e0_variant.total_stuck} vs {e0_g.total_stuck}")
        else:
            print("    No completed trips for comparison.")

    # Verdict
    print("\n  Verdict:")
    best_e0 = None
    best_label = ""
    for label, variant in [("E₀ full (conf=0.5)", e0_f),
                            ("E₀ conservative (conf=0.85)", e0_c)]:
        if variant and variant.trips_completed > e0_g.trips_completed:
            if best_e0 is None or variant.trips_completed > best_e0.trips_completed:
                best_e0 = variant
                best_label = label

    if best_e0:
        speedup = e0_g.avg_trip_time / best_e0.avg_trip_time
        print(f"    ✓ Interference helps when gated conservatively.")
        print(f"      {best_label}: {best_e0.trips_completed} trips vs "
              f"{e0_g.trips_completed} (E₀ greedy), {speedup:.2f}× faster")
        print(f"      {best_e0.total_overrides} targeted overrides (quality > quantity)")
        if e0_f and e0_f.trips_completed < e0_g.trips_completed:
            print(f"    ⚠ Low-confidence overrides hurt: E₀ full "
                  f"({e0_f.trips_completed} trips, {e0_f.total_overrides} overrides)")
    elif e0_f and e0_f.total_overrides > 0:
        print("    ✗ Interference overrides hurt at all tested thresholds.")
    else:
        print("    ✗ No interference advantage detected.")


# ─────────────────────── Main ───────────────────────

def spawn_commute_vehicles(
    city: CityGrid,
    n: int,
    strategy: Strategy,
    positions: Dict[str, str],
    bfs_table: Dict[Tuple[str, str], str],
    river_row: int = 3,
    epistemic_trust: bool = False,
) -> List[Vehicle]:
    """Create n vehicles that commute north → south (forced river crossing).

    Origin: random node in rows 0..river_row-1
    Goal:   random node in rows river_row+1..rows-1
    """
    north = [nd for nd in city.nodes if parse_node(nd)[0] < river_row]
    south = [nd for nd in city.nodes if parse_node(nd)[0] > river_row]
    vehicles = []
    for i in range(n):
        pos = random.choice(north)
        goal = random.choice(south)
        v = Vehicle(name=f"v{i}", position=pos, goal=goal, strategy=strategy)
        positions[v.name] = v.position
        if strategy in (Strategy.E0_GREEDY, Strategy.E0_FULL, Strategy.E0_CONSERVATIVE):
            v.landscape = build_vehicle_landscape(city, goal)
            if strategy == Strategy.E0_GREEDY:
                mode = HybridMode.GREEDY
                horizon = 0
                conf = 1.0
            elif strategy == Strategy.E0_FULL:
                mode = HybridMode.AMPLITUDE_ON_DISAGREE
                horizon = 3
                conf = 0.5
            else:
                mode = HybridMode.AMPLITUDE_ON_DISAGREE
                horizon = 3
                conf = 0.85
            v.controller = E0Controller(
                landscape=v.landscape,
                execute_fn=make_execute_fn(v.name, positions, city.capacity),
                alpha=2.0,
                recent_k=3,
                hybrid_mode=mode,
                hybrid_horizon=horizon,
                hybrid_goals={goal},
                hybrid_geometry="goal_reaching",
                confidence_threshold=conf,
                epistemic_trust=epistemic_trust,
            )
        vehicles.append(v)
    return vehicles


def recycle_commute_vehicle(
    v: Vehicle,
    city: CityGrid,
    tick: int,
    positions: Dict[str, str],
    river_row: int = 3,
) -> TripRecord:
    """Record completed trip and assign new north→south commute."""
    trip = TripRecord(
        vehicle=v.name,
        start_pos=v.position,
        goal=v.goal,
        ticks=tick - v.trip_start_tick,
        stuck_events=v.trip_stuck,
    )
    v.trips_completed += 1
    v.trip_times.append(trip.ticks)
    v.trip_stuck = 0
    v.consecutive_stuck = 0

    north = [nd for nd in city.nodes if parse_node(nd)[0] < river_row]
    south = [nd for nd in city.nodes if parse_node(nd)[0] > river_row]
    new_pos = random.choice(north)
    new_goal = random.choice(south)
    v.position = new_pos
    v.goal = new_goal
    v.trip_start_tick = tick
    positions[v.name] = new_pos

    if v.landscape is not None:
        update_landscape_goal(v.landscape, city, new_goal)
    if v.controller is not None:
        v.controller.hybrid_goals = {new_goal}

    return trip


def run_commute_simulation(
    city: CityGrid,
    n_vehicles: int = 10,
    n_ticks: int = 1000,
    strategy: Strategy = Strategy.E0_CONSERVATIVE,
    bfs_table: Optional[Dict[Tuple[str, str], str]] = None,
    river_row: int = 3,
) -> SimResult:
    """Run simulation where all vehicles commute north→south across the river."""
    if bfs_table is None:
        bfs_table = bfs_next_hop(city)

    positions: Dict[str, str] = {}
    vehicles = spawn_commute_vehicles(
        city, n_vehicles, strategy, positions, bfs_table, river_row,
    )

    all_trips: List[TripRecord] = []
    snapshots: List[TickSnapshot] = []
    total_stuck = 0
    total_overrides = 0

    for tick in range(n_ticks):
        order = list(vehicles)
        random.shuffle(order)

        for v in order:
            if v.position == v.goal:
                trip = recycle_commute_vehicle(v, city, tick, positions, river_row)
                all_trips.append(trip)
                continue

            # Reuse the same move logic as run_simulation
            if v.strategy == Strategy.RANDOM:
                target = pick_random(v.position, city)
                if target is None:
                    continue
                if count_at(positions, target, v.name) >= city.capacity.get(target, DEFAULT_CAPACITY):
                    v.total_stuck += 1; v.trip_stuck += 1
                    v.consecutive_stuck += 1; total_stuck += 1
                else:
                    v.position = target; positions[v.name] = target
                    v.consecutive_stuck = 0

            elif v.strategy == Strategy.GREEDY_DELTA:
                if v.consecutive_stuck >= IMPATIENCE_THRESHOLD:
                    target = pick_random(v.position, city)
                else:
                    target = pick_greedy(v.position, v.goal, city)
                if target is None:
                    continue
                if count_at(positions, target, v.name) >= city.capacity.get(target, DEFAULT_CAPACITY):
                    v.total_stuck += 1; v.trip_stuck += 1
                    v.consecutive_stuck += 1; total_stuck += 1
                else:
                    v.position = target; positions[v.name] = target
                    v.consecutive_stuck = 0

            elif v.strategy == Strategy.BFS_SHORTEST:
                if v.consecutive_stuck >= IMPATIENCE_THRESHOLD:
                    target = pick_random(v.position, city)
                else:
                    target = bfs_table.get((v.position, v.goal))
                if target is None:
                    continue
                if count_at(positions, target, v.name) >= city.capacity.get(target, DEFAULT_CAPACITY):
                    v.total_stuck += 1; v.trip_stuck += 1
                    v.consecutive_stuck += 1; total_stuck += 1
                else:
                    v.position = target; positions[v.name] = target
                    v.consecutive_stuck = 0

            elif v.strategy in (Strategy.E0_GREEDY, Strategy.E0_FULL, Strategy.E0_CONSERVATIVE):
                assert v.controller is not None
                if v.consecutive_stuck >= IMPATIENCE_THRESHOLD:
                    target = pick_random(v.position, city)
                    if target and count_at(positions, target, v.name) < city.capacity.get(target, DEFAULT_CAPACITY):
                        old_pos = v.position
                        v.position = target; positions[v.name] = target
                        v.consecutive_stuck = 0
                        v.landscape.historization.update(
                            Edge(old_pos, target), Outcome.SUCCESS,
                        )
                    else:
                        v.total_stuck += 1; v.trip_stuck += 1
                        v.consecutive_stuck += 1; total_stuck += 1
                    continue

                step = v.controller.cycle(
                    v.position,
                    overlay_horizon=(3 if v.strategy in (Strategy.E0_FULL, Strategy.E0_CONSERVATIVE) else 0),
                    overlay_goals={v.goal},
                )
                if step is None:
                    continue
                if step.outcome == Outcome.SUCCESS:
                    v.position = step.target; positions[v.name] = step.target
                    v.consecutive_stuck = 0
                else:
                    v.total_stuck += 1; v.trip_stuck += 1
                    v.consecutive_stuck += 1; total_stuck += 1
                if step.overlay and step.hybrid_overridden:
                    v.overrides += 1; total_overrides += 1

    return SimResult(
        strategy=strategy,
        total_ticks=n_ticks,
        trips=all_trips,
        snapshots=snapshots,
        total_stuck=total_stuck,
        total_overrides=total_overrides,
    )


# ─────────────────────── Main ───────────────────────

def main():
    city = CityGrid.build()
    bfs_table = bfs_next_hop(city)

    print(f"City: {city.rows}×{city.cols} grid, {len(city.nodes)} intersections, "
          f"{len(city.edges)} directed roads")
    print(f"Bottlenecks: {BOTTLENECK_NODES} (capacity {BOTTLENECK_CAPACITY})")
    print(f"Default capacity: {DEFAULT_CAPACITY}")
    print(f"Impatience threshold: {IMPATIENCE_THRESHOLD} ticks\n")

    for n_veh in (10, 20):
        print(f"\n{'='*78}")
        print(f"  {n_veh} vehicles, 1000 ticks")
        print(f"{'='*78}")

        strategies = list(Strategy)
        results: Dict[Strategy, SimResult] = {}

        for strat in strategies:
            random.seed(42)
            print(f"  Running {strat.value}...", end="", flush=True)
            result = run_simulation(
                city, n_vehicles=n_veh, n_ticks=1000, strategy=strat,
                bfs_table=bfs_table, snapshot_interval=200,
            )
            results[strat] = result
            print(f" done ({result.trips_completed} trips)")

        print_comparison(results)
        print_interference_analysis(results)


def main_river_city():
    """Run river city simulation — the structural smoking gun.

    Uses standard simulation (random origin/goal) on river city topology.
    The river forces bridge crossings for any north↔south trip, creating
    natural chokepoints where the overlay advantage is maximized.
    """
    city = CityGrid.build_river_city()
    bfs_table = bfs_next_hop(city)
    bridges = [n for n in city.nodes if parse_node(n)[0] == 3]

    print(f"=== River City (Two Bridges) ===")
    print(f"{len(city.nodes)} nodes, {len(city.edges)} edges, "
          f"Bridges: {bridges}")
    print(f"Seed-averaged results (5 seeds)\n")

    seeds = [42, 123, 2024, 7777, 31415]
    strategies = [
        ("Greedy", Strategy.GREEDY_DELTA, False),
        ("E0_greedy", Strategy.E0_GREEDY, False),
        ("E0_greedy+trust", Strategy.E0_GREEDY, True),
        ("E0_conserv.", Strategy.E0_CONSERVATIVE, False),
        ("E0_cons.+trust", Strategy.E0_CONSERVATIVE, True),
    ]
    for n_veh in (10, 15, 20):
        print(f"--- {n_veh} vehicles, 1000 ticks ---")
        totals: Dict[str, List[int]] = {s[0]: [] for s in strategies}
        for seed in seeds:
            for label, strat, trust in strategies:
                random.seed(seed)
                r = run_simulation(
                    city, n_vehicles=n_veh, n_ticks=1000,
                    strategy=strat, bfs_table=bfs_table,
                    epistemic_trust=trust,
                )
                totals[label].append(r.trips_completed)
        avgs = {k: sum(v) / len(v) for k, v in totals.items()}
        for label, _, _ in strategies:
            print(f"  {label:20s} {avgs[label]:6.0f} trips (avg)")
        # Trust gain for greedy
        g_base = avgs["E0_greedy"]
        g_trust = avgs["E0_greedy+trust"]
        gain_g = (g_trust - g_base) / max(g_base, 1) * 100
        print(f"  → Trust gain (greedy):     {gain_g:+.0f}%")
        # Trust gain for conservative
        c_base = avgs["E0_conserv."]
        c_trust = avgs["E0_cons.+trust"]
        gain_c = (c_trust - c_base) / max(c_base, 1) * 100
        print(f"  → Trust gain (conserv.):   {gain_c:+.0f}%")
    print()
    print("C186 validation: Does epistemic trust recover greedy from bridge trap?")


if __name__ == "__main__":
    import sys
    if "--river" in sys.argv:
        main_river_city()
    else:
        main()
