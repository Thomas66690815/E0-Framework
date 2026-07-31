"""Gate G1 domain generators and deterministic outcome schedules.

WP-2.1 implements only the preregistered domain and environment layer.  It does
not run G1 methods and it refuses holdout seeds.  Later work packages may build
method adapters on top of :class:`G1DomainInstance`.

The environment random stream is counter based.  An outcome is keyed by
``(generator_seed, episode_index, edge_id, edge_attempt_index)`` instead of
being consumed from one sequential RNG.  Diverging policies therefore observe
the same potential outcome whenever they make the same edge attempt.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections import Counter, deque
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .landscape import Landscape
from .primitives import Edge, Outcome

PROTOCOL_ID = "E0-G1-v1"
GENERATOR_VERSION = "1.0"
PROTOCOL_PATH = Path(__file__).resolve().parents[1] / "docs" / "E0_G1_PROTOCOL_v1.json"
DEVELOPMENT_SEED_NAMESPACE = "g1_v1_development"
CALIBRATION_SEED_NAMESPACE = "override_gate_calibration"


class HoldoutAccessError(ValueError):
    """Raised when WP-2.1 code is asked to access a holdout seed."""


@lru_cache(maxsize=1)
def load_g1_protocol() -> Dict[str, Any]:
    """Load and minimally verify the frozen G1 protocol."""
    data = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    if data.get("protocol_id") != PROTOCOL_ID:
        raise ValueError(f"Expected protocol {PROTOCOL_ID}, got {data.get('protocol_id')!r}")
    if data.get("holdout_execution_started") is not False:
        raise ValueError("WP-2.1 requires holdout_execution_started=false")
    return data


def protocol_sha256() -> str:
    """Return the byte-level SHA-256 of the preregistered protocol."""
    return hashlib.sha256(PROTOCOL_PATH.read_bytes()).hexdigest()


def development_seeds() -> range:
    """Return the inclusive development-seed range from the protocol."""
    split = load_g1_protocol()["splits"]["development"]["generator_seeds"]
    return range(int(split["start"]), int(split["stop_inclusive"]) + 1)


def holdout_seeds() -> range:
    """Return the inclusive holdout range for validation/guarding only."""
    split = load_g1_protocol()["splits"]["holdout"]["generator_seeds"]
    return range(int(split["start"]), int(split["stop_inclusive"]) + 1)


def validate_development_seed(seed: int) -> None:
    """Reject every seed not explicitly assigned to development.

    In particular, WP-2.1 must not instantiate a holdout domain.  The later
    holdout runner needs a deliberate implementation and protocol-state change.
    """
    if seed in holdout_seeds():
        raise HoldoutAccessError(
            f"Seed {seed} is an E0-G1-v1 holdout seed; WP-2.1 is development-only"
        )
    if seed not in development_seeds():
        allowed = development_seeds()
        raise ValueError(
            f"Seed {seed} is outside development range {allowed.start}..{allowed.stop - 1}"
        )


def _validate_seed_namespace(seed: int, namespace: str) -> None:
    """Validate the explicit generator namespace without enabling protected splits."""
    if namespace == DEVELOPMENT_SEED_NAMESPACE:
        validate_development_seed(seed)
        return
    if namespace == CALIBRATION_SEED_NAMESPACE:
        from .override_gate_calibration import seeds_for_split

        if seed not in seeds_for_split("calibration"):
            raise HoldoutAccessError(
                f"Seed {seed} is not in the override-gate calibration split"
            )
        return
    raise HoldoutAccessError(f"Unknown or protected seed namespace {namespace!r}")


def edge_id(source: str, target: str) -> str:
    """Return the stable edge identifier used by the outcome schedule."""
    return f"{source}\u2192{target}"


def keyed_uniform(
    generator_seed: int,
    episode_index: int,
    edge_identifier: str,
    edge_attempt_index: int,
) -> float:
    """Map an outcome key deterministically into ``[0, 1)``.

    BLAKE2b is used as a stable counter-based mixer, not for security.  The
    preregistered outcome seed formula is included as a namespace.
    """
    outcome_seed = 200000 + int(generator_seed)
    payload = "\x1f".join(
        [
            PROTOCOL_ID,
            str(outcome_seed),
            str(generator_seed),
            str(episode_index),
            edge_identifier,
            str(edge_attempt_index),
        ]
    ).encode("utf-8")
    integer = int.from_bytes(hashlib.blake2b(payload, digest_size=8).digest(), "big")
    return integer / float(1 << 64)


@dataclass(frozen=True)
class OutcomeRule:
    """Success probability for one edge before and after an optional switch."""

    source: str
    target: str
    success_probability_pre: float
    success_probability_post: Optional[float] = None
    switch_at_episode_index: Optional[int] = None
    semantic_role: str = ""

    def __post_init__(self) -> None:
        probabilities = [self.success_probability_pre]
        if self.success_probability_post is not None:
            probabilities.append(self.success_probability_post)
        if any(p < 0.0 or p > 1.0 for p in probabilities):
            raise ValueError("Success probabilities must lie in [0, 1]")
        if (self.success_probability_post is None) != (self.switch_at_episode_index is None):
            raise ValueError("Post-switch probability and switch index must be specified together")

    @property
    def identifier(self) -> str:
        return edge_id(self.source, self.target)

    def probability(self, episode_index: int) -> float:
        if (
            self.switch_at_episode_index is not None
            and episode_index >= self.switch_at_episode_index
        ):
            assert self.success_probability_post is not None
            return self.success_probability_post
        return self.success_probability_pre

    def as_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "edge_id": self.identifier,
            "success_probability_pre": self.success_probability_pre,
            "success_probability_post": self.success_probability_post,
            "switch_at_episode_index": self.switch_at_episode_index,
            "semantic_role": self.semantic_role,
        }


@dataclass
class G1DomainInstance:
    """One generated G1 domain instance."""

    family: str
    target_node_count: int
    generator_seed: int
    landscape: Landscape
    start: str
    goal: str
    oracle_cost_by_regime: Dict[str, int]
    outcome_rules: Tuple[OutcomeRule, ...] = ()
    metadata: Dict[str, Any] = field(default_factory=dict)
    generator_version: str = GENERATOR_VERSION
    seed_namespace: str = DEVELOPMENT_SEED_NAMESPACE

    def __post_init__(self) -> None:
        _validate_seed_namespace(self.generator_seed, self.seed_namespace)
        if len(self.landscape.states) != self.target_node_count:
            raise ValueError(
                f"{self.family} generated {len(self.landscape.states)} nodes "
                f"for target {self.target_node_count}"
            )
        if self.start not in self.landscape.states:
            raise ValueError(f"Start state {self.start!r} is missing")
        if self.goal not in self.landscape.states:
            raise ValueError(f"Goal state {self.goal!r} is missing")
        rule_edges = {(r.source, r.target) for r in self.outcome_rules}
        missing = [pair for pair in rule_edges if not self.landscape.has_edge(pair[0], pair[1])]
        if missing:
            raise ValueError(f"Outcome rules reference missing edges: {missing}")

    @property
    def actual_node_count(self) -> int:
        return len(self.landscape.states)

    @property
    def edge_count(self) -> int:
        return self.landscape.edge_count()

    @property
    def outcome_seed(self) -> int:
        return 200000 + self.generator_seed

    @property
    def policy_seed(self) -> int:
        return 300000 + self.generator_seed

    @property
    def run_id(self) -> str:
        if self.seed_namespace == CALIBRATION_SEED_NAMESPACE:
            return (
                f"gate-cal-{self.family}-N{self.target_node_count}-"
                f"s{self.generator_seed:04d}"
            )
        return f"dev-{self.family}-N{self.target_node_count}-s{self.generator_seed:04d}"

    def success_probability(self, source: str, target: str, episode_index: int) -> float:
        for rule in self.outcome_rules:
            if rule.source == source and rule.target == target:
                return rule.probability(episode_index)
        return 1.0

    def executor(self, episode_index: int) -> "G1EpisodeExecutor":
        return G1EpisodeExecutor(self, episode_index)

    def topology_payload(self) -> Dict[str, Any]:
        edges = []
        for edge in sorted(self.landscape.edges, key=lambda e: (e.source, e.target)):
            edges.append(
                {
                    "source": edge.source,
                    "target": edge.target,
                    "delta": self.landscape._delta[edge],
                    "resistance": self.landscape._R0[edge],
                    "metadata": self.landscape.edge_meta(edge.source, edge.target),
                }
            )
        return {
            "family": self.family,
            "states": sorted(self.landscape.states),
            "edges": edges,
            "outcome_rules": [
                rule.as_dict()
                for rule in sorted(self.outcome_rules, key=lambda r: (r.source, r.target))
            ],
        }

    def topology_sha256(self) -> str:
        encoded = json.dumps(
            self.topology_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def to_record(self) -> Dict[str, Any]:
        if self.seed_namespace != DEVELOPMENT_SEED_NAMESPACE:
            raise RuntimeError(
                "G1DomainInstance.to_record is development-only; use the "
                "calibration-specific domain record"
            )
        invariants = validate_domain(self)
        return {
            "protocol_id": PROTOCOL_ID,
            "generator_version": self.generator_version,
            "artifact_kind": "development_domain_validation",
            "not_g1_result": True,
            "split": "development",
            "run_id": self.run_id,
            "domain_family": self.family,
            "target_node_count": self.target_node_count,
            "actual_node_count": self.actual_node_count,
            "edge_count": self.edge_count,
            "generator_seed": self.generator_seed,
            "outcome_seed": self.outcome_seed,
            "policy_seed": self.policy_seed,
            "start": self.start,
            "goal": self.goal,
            "oracle_cost_by_regime": self.oracle_cost_by_regime,
            "topology_sha256": self.topology_sha256(),
            "outcome_rules": [rule.as_dict() for rule in self.outcome_rules],
            "metadata": self.metadata,
            "invariants": invariants,
            "invariant_pass": all(item["passed"] for item in invariants),
            "status": "domain_validated",
        }


class G1EpisodeExecutor:
    """Episode-local adapter implementing the keyed outcome schedule."""

    def __init__(self, domain: G1DomainInstance, episode_index: int):
        if episode_index < 0:
            raise ValueError("episode_index must be non-negative")
        self.domain = domain
        self.episode_index = episode_index
        self._attempts: Counter[str] = Counter()
        self.events: List[Dict[str, Any]] = []

    def __call__(self, source: str, target: str) -> Outcome:
        identifier = edge_id(source, target)
        attempt_index = self._attempts[identifier]
        self._attempts[identifier] += 1
        probability = self.domain.success_probability(source, target, self.episode_index)
        uniform = keyed_uniform(
            self.domain.generator_seed,
            self.episode_index,
            identifier,
            attempt_index,
        )
        outcome = Outcome.SUCCESS if uniform < probability else Outcome.FAILURE
        self.events.append(
            {
                "episode_index": self.episode_index,
                "edge_id": identifier,
                "edge_attempt_index": attempt_index,
                "success_probability": probability,
                "keyed_uniform": uniform,
                "outcome": outcome.value,
            }
        )
        return outcome


def _cell(row: int, col: int) -> str:
    return f"R{row}C{col}"


def _shortest_path(
    landscape: Landscape,
    start: str,
    goal: str,
    allowed_edge: Optional[Any] = None,
) -> Optional[List[str]]:
    queue: deque[List[str]] = deque([[start]])
    visited: Set[str] = set()
    while queue:
        path = queue.popleft()
        current = path[-1]
        if current == goal:
            return path
        if current in visited:
            continue
        visited.add(current)
        for target in sorted(landscape.admissible_neighbors(current)):
            if allowed_edge is not None and not allowed_edge(current, target):
                continue
            if target not in visited:
                queue.append(path + [target])
    return None


def _successful_path(domain: G1DomainInstance, episode_index: int) -> Optional[List[str]]:
    return _shortest_path(
        domain.landscape,
        domain.start,
        domain.goal,
        allowed_edge=lambda source, target: (
            domain.success_probability(source, target, episode_index) > 0.0
        ),
    )


def _is_acyclic(landscape: Landscape) -> bool:
    indegree = {state: 0 for state in landscape.states}
    outgoing: Dict[str, List[str]] = {state: [] for state in landscape.states}
    for edge in landscape.edges:
        indegree[edge.target] += 1
        outgoing[edge.source].append(edge.target)
    queue = deque(sorted(state for state, degree in indegree.items() if degree == 0))
    seen = 0
    while queue:
        source = queue.popleft()
        seen += 1
        for target in outgoing[source]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    return seen == len(landscape.states)


def _edge_cost(landscape: Landscape, source: str, target: str) -> float:
    edge = Edge(source, target)
    return landscape._delta[edge] * landscape._R0[edge]


def build_wall_grid(
    target_node_count: int,
    seed: int,
    *,
    seed_namespace: str = DEVELOPMENT_SEED_NAMESPACE,
) -> G1DomainInstance:
    """Build an exact-N grid whose only wall crossing requires a detour."""
    _validate_seed_namespace(seed, seed_namespace)
    if target_node_count < 16:
        raise ValueError("wall_grid requires at least 16 nodes")

    rows = max(4, int(math.sqrt(target_node_count)))
    cols = math.ceil(target_node_count / rows)
    coordinates = [(index // cols, index % cols) for index in range(target_node_count)]
    coordinate_set = set(coordinates)
    complete_rows = target_node_count // cols
    travel_row = rows - 1 if target_node_count % cols == 0 else max(1, complete_rows - 1)
    wall_col = cols // 2
    gen = random.Random(seed)
    max_gap_row = max(0, travel_row // 3)
    gap_row = gen.randint(0, max_gap_row)

    landscape = Landscape()
    goal_coord = (travel_row, cols - 1)
    for row, col in coordinates:
        landscape.add_state(_cell(row, col))
    for row, col in coordinates:
        for d_row, d_col in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            neighbor = (row + d_row, col + d_col)
            if neighbor not in coordinate_set:
                continue
            crosses_wall = row == neighbor[0] and {col, neighbor[1]} == {wall_col - 1, wall_col}
            if crosses_wall and row != gap_row:
                continue
            distance = abs(neighbor[0] - goal_coord[0]) + abs(neighbor[1] - goal_coord[1])
            delta = round(0.1 + 0.5 * distance / (rows + cols), 6)
            landscape.add_edge(
                _cell(row, col),
                _cell(*neighbor),
                delta=delta,
                resistance=0.5,
                role="grid",
            )

    start = _cell(travel_row, 0)
    goal = _cell(*goal_coord)
    path = _shortest_path(landscape, start, goal)
    assert path is not None
    return G1DomainInstance(
        family="wall_grid",
        target_node_count=target_node_count,
        generator_seed=seed,
        landscape=landscape,
        start=start,
        goal=goal,
        oracle_cost_by_regime={"stationary": len(path) - 1},
        seed_namespace=seed_namespace,
        metadata={
            "rows": rows,
            "cols": cols,
            "travel_row": travel_row,
            "wall_boundary_columns": [wall_col - 1, wall_col],
            "wall_gap_row": gap_row,
            "exact_node_count": True,
        },
    )


def build_trap_grid_v2(
    target_node_count: int,
    seed: int,
    *,
    seed_namespace: str = DEVELOPMENT_SEED_NAMESPACE,
) -> G1DomainInstance:
    """Build an exact-N comb grid with locally attractive terminal traps."""
    _validate_seed_namespace(seed, seed_namespace)
    if target_node_count < 20:
        raise ValueError("trap_grid_v2 requires at least 20 nodes")

    cols = max(4, int(math.sqrt(target_node_count)))
    branch_columns = list(range(1, cols - 1))
    if not branch_columns:
        raise ValueError("trap_grid_v2 needs at least two non-terminal columns")
    gen = random.Random(seed)
    gen.shuffle(branch_columns)

    landscape = Landscape()
    for col in range(cols):
        landscape.add_state(_cell(0, col))
    for col in range(cols - 1):
        landscape.add_edge(
            _cell(0, col),
            _cell(0, col + 1),
            delta=0.30,
            resistance=0.50,
            role="safe_corridor",
        )
        landscape.add_edge(
            _cell(0, col + 1),
            _cell(0, col),
            delta=0.60,
            resistance=0.70,
            role="safe_return",
        )

    remaining = target_node_count - cols
    base_length, extra = divmod(remaining, len(branch_columns))
    branch_lengths = {
        col: base_length + (1 if index < extra else 0) for index, col in enumerate(branch_columns)
    }
    outcome_rules: List[OutcomeRule] = []
    trap_specs: List[Dict[str, Any]] = []
    for col in sorted(branch_lengths):
        length = branch_lengths[col]
        previous = _cell(0, col)
        entry_delta = round(0.015 + 0.005 * gen.random(), 6)
        for depth in range(1, length + 1):
            node = _cell(depth, col)
            delta = entry_delta if depth == 1 else 0.03
            landscape.add_edge(
                previous,
                node,
                delta=delta,
                resistance=0.30,
                role="trap_entry" if depth == 1 else "trap_descent",
            )
            if depth < length:
                landscape.add_edge(
                    node,
                    previous,
                    delta=0.80,
                    resistance=1.00,
                    role="costly_return",
                )
            previous = node
        failure_source = _cell(length - 1, col) if length > 1 else _cell(0, col)
        failure_target = _cell(length, col)
        outcome_rules.append(
            OutcomeRule(
                failure_source,
                failure_target,
                0.0,
                semantic_role="terminal_trap_failure",
            )
        )
        trap_specs.append(
            {
                "junction": _cell(0, col),
                "entry": edge_id(_cell(0, col), _cell(1, col)),
                "depth": length,
                "failure_edge": edge_id(failure_source, failure_target),
                "dead_end": failure_target,
            }
        )

    start = _cell(0, 0)
    goal = _cell(0, cols - 1)
    safe_path = _shortest_path(
        landscape,
        start,
        goal,
        allowed_edge=lambda source, target: not target.startswith("R1C"),
    )
    assert safe_path is not None
    return G1DomainInstance(
        family="trap_grid_v2",
        target_node_count=target_node_count,
        generator_seed=seed,
        landscape=landscape,
        start=start,
        goal=goal,
        oracle_cost_by_regime={"stationary": len(safe_path) - 1},
        outcome_rules=tuple(outcome_rules),
        seed_namespace=seed_namespace,
        metadata={
            "rows": max(branch_lengths.values()) + 1,
            "cols": cols,
            "trap_count": len(trap_specs),
            "traps": trap_specs,
            "exact_node_count": True,
        },
    )


def build_decoy_dag(
    target_node_count: int,
    seed: int,
    *,
    seed_namespace: str = DEVELOPMENT_SEED_NAMESPACE,
) -> G1DomainInstance:
    """Build exact-N parallel paths with 40% attractive late failures."""
    _validate_seed_namespace(seed, seed_namespace)
    if target_node_count < 30:
        raise ValueError("decoy_dag requires at least 30 nodes")

    raw_paths = max(5, min(25, target_node_count // 20))
    path_count = max(5, raw_paths - raw_paths % 5)
    failed_count = int(path_count * 0.4)
    gen = random.Random(seed)
    failed_paths = set(gen.sample(range(path_count), failed_count))
    fractions = {path: gen.uniform(0.7, 0.9) for path in failed_paths}

    def failure_depth(path: int, nominal_depth: int) -> int:
        low = math.ceil(0.7 * nominal_depth)
        high = math.floor(0.9 * nominal_depth)
        return min(
            high,
            max(low, int(round(fractions[path] * nominal_depth))),
        )

    nominal_depth = 3
    while True:
        candidate = nominal_depth + 1
        candidate_nodes = 2
        for path in range(path_count):
            if path in failed_paths:
                candidate_nodes += failure_depth(path, candidate)
            else:
                candidate_nodes += candidate - 1
        if candidate_nodes > target_node_count:
            break
        nominal_depth = candidate

    failed_depths = {path: failure_depth(path, nominal_depth) for path in failed_paths}
    base_nodes = 2 + sum(
        failed_depths[path] if path in failed_paths else nominal_depth - 1
        for path in range(path_count)
    )
    remaining = target_node_count - base_nodes
    good_paths = [path for path in range(path_count) if path not in failed_paths]
    good_extra = {path: 0 for path in good_paths}
    for index in range(remaining):
        good_extra[good_paths[index % len(good_paths)]] += 1

    landscape = Landscape()
    landscape.add_state("S")
    landscape.add_state("GOAL")
    rules: List[OutcomeRule] = []
    specs: List[Dict[str, Any]] = []
    for path in range(path_count):
        previous = "S"
        if path in failed_paths:
            depth = failed_depths[path]
            for step in range(1, depth + 1):
                node = f"P{path}_FAIL" if step == depth else f"P{path}_D{step}"
                landscape.add_edge(
                    previous,
                    node,
                    delta=0.05,
                    resistance=0.30,
                    role="decoy_terminal" if step == depth else "decoy",
                )
                previous = node
            source = "S" if depth == 1 else f"P{path}_D{depth - 1}"
            target = f"P{path}_FAIL"
            rules.append(
                OutcomeRule(
                    source,
                    target,
                    0.0,
                    semantic_role="late_decoy_failure",
                )
            )
            specs.append(
                {
                    "path": path,
                    "failed": True,
                    "nominal_depth": nominal_depth,
                    "failure_depth": depth,
                    "failure_depth_fraction": depth / nominal_depth,
                    "failure_edge": edge_id(source, target),
                }
            )
        else:
            internal_count = nominal_depth - 1 + good_extra[path]
            for step in range(1, internal_count + 1):
                node = f"P{path}_D{step}"
                landscape.add_edge(
                    previous,
                    node,
                    delta=0.30,
                    resistance=0.50,
                    role="successful_path",
                )
                previous = node
            landscape.add_edge(
                previous,
                "GOAL",
                delta=0.30,
                resistance=0.50,
                role="successful_terminal",
            )
            specs.append(
                {
                    "path": path,
                    "failed": False,
                    "path_depth": internal_count + 1,
                }
            )

    temporary = G1DomainInstance(
        family="decoy_dag",
        target_node_count=target_node_count,
        generator_seed=seed,
        landscape=landscape,
        start="S",
        goal="GOAL",
        oracle_cost_by_regime={"stationary": 0},
        outcome_rules=tuple(rules),
        seed_namespace=seed_namespace,
        metadata={
            "path_count": path_count,
            "failed_path_count": failed_count,
            "failed_path_fraction": failed_count / path_count,
            "nominal_depth": nominal_depth,
            "paths": specs,
            "exact_node_count": True,
        },
    )
    path = _successful_path(temporary, 0)
    assert path is not None
    temporary.oracle_cost_by_regime["stationary"] = len(path) - 1
    return temporary


def build_nonstationary_parallel(
    target_node_count: int,
    seed: int,
    *,
    seed_namespace: str = DEVELOPMENT_SEED_NAMESPACE,
) -> G1DomainInstance:
    """Build two fixed corridors whose terminal outcomes reverse at episode 20."""
    _validate_seed_namespace(seed, seed_namespace)
    if target_node_count < 10:
        raise ValueError("nonstationary_parallel requires at least 10 nodes")

    internal_total = target_node_count - 2
    gen = random.Random(seed)
    spread = max(1, internal_total // 10)
    first_length = internal_total // 2 + gen.randint(-spread, spread)
    first_length = min(internal_total - 2, max(2, first_length))
    lengths = [first_length, internal_total - first_length]
    preferred = gen.randrange(2)
    alternate = 1 - preferred
    switch_absolute_episode = 10 + 10  # before 1-based evaluation episode 11

    landscape = Landscape()
    landscape.add_state("S")
    landscape.add_state("GOAL")
    terminal_edges: Dict[int, Tuple[str, str]] = {}
    for corridor in (0, 1):
        previous = "S"
        attractive = corridor == preferred
        delta = 0.08 if attractive else 0.30
        resistance = 0.35 if attractive else 0.50
        for step in range(1, lengths[corridor] + 1):
            node = f"C{corridor}_D{step}"
            landscape.add_edge(
                previous,
                node,
                delta=delta,
                resistance=resistance,
                role="preferred_corridor" if attractive else "alternate_corridor",
            )
            previous = node
        landscape.add_edge(
            previous,
            "GOAL",
            delta=delta,
            resistance=resistance,
            role="corridor_terminal",
        )
        terminal_edges[corridor] = (previous, "GOAL")

    rules = []
    for corridor in (0, 1):
        source, target = terminal_edges[corridor]
        pre = 1.0 if corridor == preferred else 0.0
        post = 0.0 if corridor == preferred else 1.0
        rules.append(
            OutcomeRule(
                source,
                target,
                pre,
                success_probability_post=post,
                switch_at_episode_index=switch_absolute_episode,
                semantic_role="corridor_role_reversal",
            )
        )

    temporary = G1DomainInstance(
        family="nonstationary_parallel",
        target_node_count=target_node_count,
        generator_seed=seed,
        landscape=landscape,
        start="S",
        goal="GOAL",
        oracle_cost_by_regime={"pre_switch": 0, "post_switch": 0},
        outcome_rules=tuple(rules),
        seed_namespace=seed_namespace,
        metadata={
            "corridor_count": 2,
            "corridor_lengths": lengths,
            "pre_switch_successful_corridor": preferred,
            "post_switch_successful_corridor": alternate,
            "switch_before_evaluation_episode": 11,
            "switch_absolute_episode_index": switch_absolute_episode,
            "topology_changes_at_switch": False,
            "exact_node_count": True,
        },
    )
    pre_path = _successful_path(temporary, switch_absolute_episode - 1)
    post_path = _successful_path(temporary, switch_absolute_episode)
    assert pre_path is not None and post_path is not None
    temporary.oracle_cost_by_regime.update(
        {
            "pre_switch": len(pre_path) - 1,
            "post_switch": len(post_path) - 1,
        }
    )
    return temporary


BUILDERS = {
    "wall_grid": build_wall_grid,
    "trap_grid_v2": build_trap_grid_v2,
    "decoy_dag": build_decoy_dag,
    "nonstationary_parallel": build_nonstationary_parallel,
}


def build_domain(family: str, target_node_count: int, generator_seed: int) -> G1DomainInstance:
    """Build one preregistered development instance."""
    protocol = load_g1_protocol()
    configured_families = [item["id"] for item in protocol["domain_families"]]
    if family not in configured_families:
        raise ValueError(f"Unknown G1 family {family!r}")
    if family not in BUILDERS:
        raise NotImplementedError(f"No WP-2.1 builder for {family}")
    if target_node_count not in protocol["scales"]:
        raise ValueError(f"Scale {target_node_count} is not preregistered: {protocol['scales']}")
    validate_development_seed(generator_seed)
    return BUILDERS[family](target_node_count, generator_seed)


def _invariant(identifier: str, passed: bool, detail: str) -> Dict[str, Any]:
    return {"id": identifier, "passed": bool(passed), "detail": detail}


def _validate_wall_grid(domain: G1DomainInstance) -> List[Dict[str, Any]]:
    goal_row = domain.metadata["travel_row"]
    goal_col = domain.metadata["cols"] - 1

    def monotone(source: str, target: str) -> bool:
        def coordinate(state: str) -> Tuple[int, int]:
            row_text, col_text = state[1:].split("C")
            return int(row_text), int(col_text)

        source_row, source_col = coordinate(source)
        target_row, target_col = coordinate(target)
        source_distance = abs(source_row - goal_row) + abs(source_col - goal_col)
        target_distance = abs(target_row - goal_row) + abs(target_col - goal_col)
        return target_distance <= source_distance

    path = _shortest_path(domain.landscape, domain.start, domain.goal)
    monotone_path = _shortest_path(
        domain.landscape, domain.start, domain.goal, allowed_edge=monotone
    )
    return [
        _invariant(
            "start_goal_connected",
            path is not None,
            f"shortest_path_edges={len(path) - 1 if path else None}",
        ),
        _invariant(
            "direct_gradient_route_blocked",
            monotone_path is None,
            "no path reaches the goal without first increasing Manhattan distance",
        ),
        _invariant(
            "oracle_route_exists",
            domain.oracle_cost_by_regime.get("stationary", 0) > 0,
            f"oracle_cost={domain.oracle_cost_by_regime.get('stationary')}",
        ),
        _invariant(
            "actual_node_count_recorded",
            domain.actual_node_count == domain.target_node_count,
            f"actual={domain.actual_node_count}, target={domain.target_node_count}",
        ),
    ]


def _validate_trap_grid(domain: G1DomainInstance) -> List[Dict[str, Any]]:
    traps = domain.metadata["traps"]
    attractive = True
    semantic = True
    for trap in traps:
        source, target = trap["entry"].split("\u2192", 1)
        col = int(source.split("C")[1])
        safe_target = _cell(0, col + 1)
        attractive &= _edge_cost(domain.landscape, source, target) < _edge_cost(
            domain.landscape, source, safe_target
        )
        failure_source, failure_target = trap["failure_edge"].split("\u2192", 1)
        semantic &= domain.success_probability(
            failure_source, failure_target, 0
        ) == 0.0 and not domain.landscape.admissible_neighbors(trap["dead_end"])
    successful = _successful_path(domain, 0)
    return [
        _invariant(
            "locally_attractive_trap_entry",
            attractive and bool(traps),
            f"checked_traps={len(traps)}",
        ),
        _invariant(
            "downstream_failure_dead_end_or_return_cost",
            semantic and bool(traps),
            "each trap ends in a deterministic failed transition into a dead end",
        ),
        _invariant(
            "non_trap_oracle_route_exists",
            successful is not None,
            f"oracle_cost={len(successful) - 1 if successful else None}",
        ),
        _invariant(
            "trap_semantics_tested_automatically",
            attractive and semantic and successful is not None,
            "attraction, terminal failure/dead-end, and safe route all checked",
        ),
    ]


def _validate_decoy_dag(domain: G1DomainInstance) -> List[Dict[str, Any]]:
    specs = domain.metadata["paths"]
    failed = [item for item in specs if item["failed"]]
    good = [item for item in specs if not item["failed"]]
    fractions_ok = all(0.7 <= item["failure_depth_fraction"] <= 0.9 for item in failed)
    decoy_entries = [
        edge
        for edge in domain.landscape.edges
        if edge.source == "S" and domain.landscape.edge_meta(*edge)["role"].startswith("decoy")
    ]
    good_entries = [
        edge
        for edge in domain.landscape.edges
        if edge.source == "S" and domain.landscape.edge_meta(*edge)["role"] == "successful_path"
    ]
    attractive = (
        bool(decoy_entries)
        and bool(good_entries)
        and max(_edge_cost(domain.landscape, edge.source, edge.target) for edge in decoy_entries)
        < min(_edge_cost(domain.landscape, edge.source, edge.target) for edge in good_entries)
    )
    successful = _successful_path(domain, 0)
    return [
        _invariant("acyclic", _is_acyclic(domain.landscape), "Kahn traversal"),
        _invariant(
            "at_least_one_successful_path",
            bool(good) and successful is not None,
            f"successful_paths={len(good)}",
        ),
        _invariant(
            "decoys_locally_attractive",
            attractive,
            f"decoy_paths={len(failed)}, good_paths={len(good)}",
        ),
        _invariant(
            "failure_depth_within_preregistered_range",
            fractions_ok
            and math.isclose(len(failed) / len(specs), 0.4, rel_tol=0.0, abs_tol=1e-12),
            "all failure depths in [0.7,0.9] and failed-path fraction=0.4",
        ),
    ]


def _validate_nonstationary(domain: G1DomainInstance) -> List[Dict[str, Any]]:
    switch = domain.metadata["switch_absolute_episode_index"]
    preferred = domain.metadata["pre_switch_successful_corridor"]
    alternate = domain.metadata["post_switch_successful_corridor"]
    terminal_rules = {int(rule.source.split("_")[0][1:]): rule for rule in domain.outcome_rules}
    preferred_rule = terminal_rules[preferred]
    alternate_rule = terminal_rules[alternate]
    return [
        _invariant(
            "at_least_two_alternative_corridors",
            domain.metadata["corridor_count"] >= 2,
            f"corridors={domain.metadata['corridor_count']}",
        ),
        _invariant(
            "pre_switch_preferred_corridor_becomes_post_switch_failing",
            preferred_rule.probability(switch - 1) == 1.0
            and preferred_rule.probability(switch) == 0.0,
            f"corridor={preferred}",
        ),
        _invariant(
            "previously_failing_corridor_becomes_successful",
            alternate_rule.probability(switch - 1) == 0.0
            and alternate_rule.probability(switch) == 1.0,
            f"corridor={alternate}",
        ),
        _invariant(
            "same_topology_before_and_after_switch",
            domain.metadata["topology_changes_at_switch"] is False,
            "only terminal outcome probabilities change",
        ),
    ]


VALIDATORS = {
    "wall_grid": _validate_wall_grid,
    "trap_grid_v2": _validate_trap_grid,
    "decoy_dag": _validate_decoy_dag,
    "nonstationary_parallel": _validate_nonstationary,
}


def validate_domain(domain: G1DomainInstance) -> List[Dict[str, Any]]:
    """Evaluate all preregistered invariants for an instance."""
    validator = VALIDATORS.get(domain.family)
    if validator is None:
        raise ValueError(f"No invariant validator for {domain.family}")
    results = validator(domain)
    configured = {item["id"] for item in load_g1_protocol()["domain_families"]}
    if domain.family not in configured:
        raise ValueError(f"Family {domain.family} is not in the protocol")
    results.append(
        _invariant(
            "exact_target_node_count",
            domain.actual_node_count == domain.target_node_count,
            f"actual={domain.actual_node_count}, target={domain.target_node_count}",
        )
    )
    return results


def build_development_matrix(
    *,
    families: Optional[Sequence[str]] = None,
    scales: Optional[Sequence[int]] = None,
    seeds: Optional[Sequence[int]] = None,
) -> Iterable[G1DomainInstance]:
    """Yield the requested development-only domain matrix in stable order."""
    protocol = load_g1_protocol()
    configured_families = [item["id"] for item in protocol["domain_families"]]
    selected_families = list(families or configured_families)
    selected_scales = list(scales or protocol["scales"])
    selected_seeds = list(seeds if seeds is not None else development_seeds())

    unknown = [family for family in selected_families if family not in configured_families]
    if unknown:
        raise ValueError(f"Unknown family selection: {unknown}")
    invalid_scales = [scale for scale in selected_scales if scale not in protocol["scales"]]
    if invalid_scales:
        raise ValueError(f"Non-preregistered scales: {invalid_scales}")
    for seed in selected_seeds:
        validate_development_seed(seed)

    for family in selected_families:
        for scale in selected_scales:
            for seed in selected_seeds:
                yield build_domain(family, int(scale), int(seed))
