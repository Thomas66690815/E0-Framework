"""Fair baseline adapters for the preregistered Gate G1 protocol.

WP-2.2 deliberately does not reuse the historical ``benchmark_sota`` runners:
those runners are single-episode demonstrations and do not share one consistent
FAILURE transition rule.  This module provides a fresh protocol-facing contract
with three hard boundaries:

* every method receives the same environment-interaction budget;
* FAILURE consumes one interaction and leaves the agent at the source state;
* only A* and D* Lite receive a full topology map.

The adapters are development-only because :class:`G1DomainInstance` rejects all
non-development seeds.  Holdout execution needs a separate, deliberate runner.
"""

from __future__ import annotations

import hashlib
import heapq
import json
import math
import random
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .g1_domains import (
    PROTOCOL_ID,
    G1DomainInstance,
    edge_id,
    load_g1_protocol,
    protocol_sha256,
    validate_development_seed,
)
from .primitives import Outcome

CONFIG_PATH = Path(__file__).resolve().parents[1] / "docs" / "E0_G1_BASELINE_CONFIGS_v1.json"

COMPETITIVE_METHODS = (
    "Q_LEARNING",
    "UCB1_EDGE",
    "RANDOM_RESTART_GREEDY",
)
DIAGNOSTIC_METHODS = (
    "MEMORYLESS_GREEDY",
    "EPSILON_GREEDY",
    "UNIFORM_RANDOM",
)
MAP_REFERENCE_METHODS = (
    "A_STAR",
    "D_STAR_LITE",
)
ALL_BASELINE_METHODS = (
    *COMPETITIVE_METHODS,
    *DIAGNOSTIC_METHODS,
    *MAP_REFERENCE_METHODS,
)


@dataclass(frozen=True)
class MethodContract:
    """Information and reporting contract for one preregistered method."""

    method_id: str
    category: str
    information_access: str
    comparator_eligible: bool
    stochastic: bool
    implementation_status: str = "implemented"

    @property
    def receives_full_map(self) -> bool:
        return self.information_access == "full_static_topology"


METHOD_CONTRACTS: Dict[str, MethodContract] = {
    "Q_LEARNING": MethodContract(
        "Q_LEARNING",
        "competitive_G1_B",
        "local_outgoing_edges_and_observed_outcomes",
        True,
        True,
    ),
    "UCB1_EDGE": MethodContract(
        "UCB1_EDGE",
        "competitive_G1_B",
        "local_outgoing_edges_and_observed_outcomes",
        True,
        True,
    ),
    "RANDOM_RESTART_GREEDY": MethodContract(
        "RANDOM_RESTART_GREEDY",
        "competitive_G1_B",
        "local_outgoing_edges_and_observed_outcomes",
        True,
        True,
    ),
    "MEMORYLESS_GREEDY": MethodContract(
        "MEMORYLESS_GREEDY",
        "diagnostic",
        "local_outgoing_edges_only",
        False,
        False,
    ),
    "EPSILON_GREEDY": MethodContract(
        "EPSILON_GREEDY",
        "diagnostic",
        "local_outgoing_edges_only",
        False,
        True,
    ),
    "UNIFORM_RANDOM": MethodContract(
        "UNIFORM_RANDOM",
        "diagnostic",
        "local_outgoing_edges_only",
        False,
        True,
    ),
    "A_STAR": MethodContract(
        "A_STAR",
        "map_informed_upper_references",
        "full_static_topology",
        False,
        False,
    ),
    "D_STAR_LITE": MethodContract(
        "D_STAR_LITE",
        "map_informed_upper_references",
        "full_static_topology",
        False,
        False,
    ),
}


@dataclass(frozen=True)
class ActionView:
    """The local information visible for one outgoing action."""

    source: str
    target: str
    delta: float
    resistance: float

    @property
    def base_cost(self) -> float:
        return self.delta * self.resistance

    @property
    def identifier(self) -> str:
        return edge_id(self.source, self.target)


@dataclass(frozen=True)
class Transition:
    """One observed environment interaction."""

    episode_index: int
    interaction_index: int
    state: str
    action: ActionView
    outcome: Outcome
    next_state: str
    next_actions: Tuple[ActionView, ...]
    goal: str

    @property
    def goal_reached(self) -> bool:
        return self.next_state == self.goal


@dataclass(frozen=True)
class EpisodeSummary:
    """Protocol-facing episode result."""

    episode_index: int
    phase: str
    goal_reached: bool
    interactions_used: int
    interaction_budget: int
    total_cost: float
    oracle_cost: int
    success_adjusted_efficiency: float
    revisits: int
    failure_count: int
    terminal_reason: str
    final_state: str
    path: Tuple[str, ...]

    def to_record(self) -> Dict[str, Any]:
        return {
            "episode_index": self.episode_index,
            "phase": self.phase,
            "goal_reached": self.goal_reached,
            "interactions_used": self.interactions_used,
            "interaction_budget": self.interaction_budget,
            "total_cost": self.total_cost,
            "oracle_cost": self.oracle_cost,
            "success_adjusted_efficiency": self.success_adjusted_efficiency,
            "revisits": self.revisits,
            "failure_count": self.failure_count,
            "terminal_reason": self.terminal_reason,
            "final_state": self.final_state,
            "path": list(self.path),
        }


@dataclass
class ReplicateResult:
    """All adaptation and evaluation episodes for one method/instance."""

    protocol_id: str
    split: str
    method: str
    method_category: str
    comparator_eligible: bool
    information_access: str
    domain_family: str
    target_node_count: int
    actual_node_count: int
    generator_seed: int
    outcome_seed: int
    policy_seed: int
    config_sha256: str
    episodes: List[EpisodeSummary]

    @property
    def evaluation_episodes(self) -> List[EpisodeSummary]:
        return [episode for episode in self.episodes if episode.phase == "evaluation"]

    def to_record(self, *, include_episodes: bool = True) -> Dict[str, Any]:
        evaluation = self.evaluation_episodes
        record: Dict[str, Any] = {
            "protocol_id": self.protocol_id,
            "artifact_kind": "development_baseline_run",
            "not_g1_result": True,
            "holdout_accessed": False,
            "split": self.split,
            "method": self.method,
            "method_category": self.method_category,
            "comparator_eligible": self.comparator_eligible,
            "information_access": self.information_access,
            "domain_family": self.domain_family,
            "target_node_count": self.target_node_count,
            "actual_node_count": self.actual_node_count,
            "generator_seed": self.generator_seed,
            "outcome_seed": self.outcome_seed,
            "policy_seed": self.policy_seed,
            "config_sha256": self.config_sha256,
            "episode_count": len(self.episodes),
            "evaluation_episode_count": len(evaluation),
            "evaluation_goal_rate": (
                sum(episode.goal_reached for episode in evaluation) / len(evaluation)
                if evaluation
                else None
            ),
            "evaluation_mean_success_adjusted_efficiency": (
                sum(episode.success_adjusted_efficiency for episode in evaluation) / len(evaluation)
                if evaluation
                else None
            ),
        }
        if include_episodes:
            record["episodes"] = [episode.to_record() for episode in self.episodes]
        return record


@dataclass(frozen=True)
class MapView:
    """Immutable full-topology view reserved for map-informed references."""

    states: Tuple[str, ...]
    goal: str
    actions_by_state: Mapping[str, Tuple[ActionView, ...]]
    predecessors_by_state: Mapping[str, Tuple[str, ...]]

    @classmethod
    def from_domain(cls, domain: G1DomainInstance) -> "MapView":
        actions = {
            state: _local_actions(domain, state) for state in sorted(domain.landscape.states)
        }
        predecessors: Dict[str, List[str]] = {state: [] for state in domain.landscape.states}
        for source, outgoing in actions.items():
            for action in outgoing:
                predecessors[action.target].append(source)
        return cls(
            states=tuple(sorted(domain.landscape.states)),
            goal=domain.goal,
            actions_by_state=actions,
            predecessors_by_state={
                state: tuple(sorted(values)) for state, values in predecessors.items()
            },
        )

    def actions(self, state: str) -> Tuple[ActionView, ...]:
        return self.actions_by_state.get(state, ())

    def predecessors(self, state: str) -> Tuple[str, ...]:
        return self.predecessors_by_state.get(state, ())


def load_baseline_configs() -> Dict[str, Any]:
    """Load and verify the frozen WP-2.2 configuration document."""
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if data.get("protocol_id") != PROTOCOL_ID:
        raise ValueError("Baseline config protocol does not match E0-G1-v1")
    if data.get("frozen_before_holdout") is not True:
        raise ValueError("Baseline configs must be frozen before holdout access")
    if data.get("holdout_execution_started") is not False:
        raise ValueError("WP-2.2 requires holdout_execution_started=false")
    if data.get("protocol_sha256") != protocol_sha256():
        raise ValueError("Frozen baseline configs reference a different protocol")
    configured = tuple(data.get("methods", {}).keys())
    if set(configured) != set(ALL_BASELINE_METHODS):
        raise ValueError(
            f"Baseline config method IDs differ from the preregistered registry: {configured}"
        )
    return data


def baseline_config_sha256() -> str:
    """Return the byte-level digest of the frozen baseline configuration."""
    return hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest()


def validate_method_registry() -> None:
    """Ensure code categories exactly match the frozen protocol."""
    protocol_baselines = load_g1_protocol()["baselines"]
    expected = {
        "competitive_G1_B": tuple(protocol_baselines["competitive_G1_B"]),
        "diagnostic": tuple(protocol_baselines["diagnostic"]),
        "map_informed_upper_references": tuple(protocol_baselines["map_informed_upper_references"]),
    }
    actual = {
        "competitive_G1_B": COMPETITIVE_METHODS,
        "diagnostic": DIAGNOSTIC_METHODS,
        "map_informed_upper_references": MAP_REFERENCE_METHODS,
    }
    if actual != expected:
        raise ValueError(f"Method registry differs from protocol: {actual} != {expected}")
    if set(METHOD_CONTRACTS) != set(ALL_BASELINE_METHODS):
        raise ValueError("Every baseline method needs exactly one contract")


def _local_actions(domain: G1DomainInstance, state: str) -> Tuple[ActionView, ...]:
    actions = []
    for target in sorted(domain.landscape.admissible_neighbors(state)):
        delta = domain.landscape.difference(state, target)
        assert delta is not None
        actions.append(
            ActionView(
                source=state,
                target=target,
                delta=delta,
                resistance=domain.landscape.base_resistance(state, target),
            )
        )
    return tuple(actions)


def _minimum_base_cost(actions: Sequence[ActionView]) -> ActionView:
    return min(actions, key=lambda action: (action.base_cost, action.target))


def bfs_shortest_path(
    map_view: MapView,
    start: str,
    *,
    blocked_edges: Iterable[Tuple[str, str]] = (),
) -> Optional[List[str]]:
    """Return the unit-cost BFS path used only as a map-oracle cross-check."""
    blocked = set(blocked_edges)
    queue: List[List[str]] = [[start]]
    cursor = 0
    visited = {start}
    while cursor < len(queue):
        path = queue[cursor]
        cursor += 1
        current = path[-1]
        if current == map_view.goal:
            return path
        for action in map_view.actions(current):
            pair = (action.source, action.target)
            if pair in blocked or action.target in visited:
                continue
            visited.add(action.target)
            queue.append([*path, action.target])
    return None


def astar_shortest_path(
    map_view: MapView,
    start: str,
    *,
    blocked_edges: Iterable[Tuple[str, str]] = (),
) -> Optional[List[str]]:
    """A* with a globally admissible zero heuristic and unit interaction cost."""
    blocked = set(blocked_edges)
    frontier: List[Tuple[float, int, str]] = [(0.0, 0, start)]
    parent: Dict[str, Optional[str]] = {start: None}
    best_g: Dict[str, float] = {start: 0.0}
    counter = 0
    while frontier:
        _, _, current = heapq.heappop(frontier)
        if current == map_view.goal:
            path: List[str] = []
            node: Optional[str] = current
            while node is not None:
                path.append(node)
                node = parent[node]
            return list(reversed(path))
        current_g = best_g[current]
        for action in map_view.actions(current):
            if (action.source, action.target) in blocked:
                continue
            tentative = current_g + 1.0
            if tentative >= best_g.get(action.target, math.inf):
                continue
            best_g[action.target] = tentative
            parent[action.target] = current
            counter += 1
            heapq.heappush(frontier, (tentative, counter, action.target))
    return None


class BaselineAdapter:
    """Local-observation method contract shared by all baselines."""

    method_id = ""

    def __init__(
        self,
        *,
        goal: str,
        policy_seed: int,
        config: Mapping[str, Any],
        map_view: Optional[MapView] = None,
    ):
        self.goal = goal
        self.policy_seed = policy_seed
        self.config = dict(config)
        self.rng = random.Random(policy_seed)
        self.map_view = map_view
        self.episodes_started = 0
        self.observations_received = 0

    def start_episode(self, episode_index: int, start: str) -> None:
        self.episodes_started += 1

    def select_action(
        self,
        episode_index: int,
        state: str,
        actions: Tuple[ActionView, ...],
    ) -> Optional[ActionView]:
        raise NotImplementedError

    def observe(self, transition: Transition) -> None:
        self.observations_received += 1

    def end_episode(self, summary: EpisodeSummary) -> None:
        return None


class MemorylessGreedyAdapter(BaselineAdapter):
    method_id = "MEMORYLESS_GREEDY"

    def select_action(
        self,
        episode_index: int,
        state: str,
        actions: Tuple[ActionView, ...],
    ) -> Optional[ActionView]:
        return _minimum_base_cost(actions) if actions else None


class EpsilonGreedyAdapter(BaselineAdapter):
    method_id = "EPSILON_GREEDY"

    def select_action(
        self,
        episode_index: int,
        state: str,
        actions: Tuple[ActionView, ...],
    ) -> Optional[ActionView]:
        if not actions:
            return None
        if self.rng.random() < float(self.config["epsilon"]):
            return self.rng.choice(actions)
        return _minimum_base_cost(actions)


class UniformRandomAdapter(BaselineAdapter):
    method_id = "UNIFORM_RANDOM"

    def select_action(
        self,
        episode_index: int,
        state: str,
        actions: Tuple[ActionView, ...],
    ) -> Optional[ActionView]:
        return self.rng.choice(actions) if actions else None


class QLearningAdapter(BaselineAdapter):
    method_id = "Q_LEARNING"

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self.q_values: Dict[Tuple[str, str], float] = defaultdict(float)

    def _epsilon(self, episode_index: int) -> float:
        start = float(self.config["epsilon_start"])
        end = float(self.config["epsilon_end"])
        protocol = load_g1_protocol()["interaction_protocol"]
        total = int(protocol["adaptation_episodes"]) + int(protocol["evaluation_episodes"])
        fraction = min(episode_index / max(total - 1, 1), 1.0)
        return start + fraction * (end - start)

    def select_action(
        self,
        episode_index: int,
        state: str,
        actions: Tuple[ActionView, ...],
    ) -> Optional[ActionView]:
        if not actions:
            return None
        if self.rng.random() < self._epsilon(episode_index):
            return self.rng.choice(actions)
        maximum = max(self.q_values[(state, action.target)] for action in actions)
        best = [action for action in actions if self.q_values[(state, action.target)] == maximum]
        return self.rng.choice(best)

    def observe(self, transition: Transition) -> None:
        super().observe(transition)
        if transition.outcome == Outcome.FAILURE:
            reward = float(self.config["reward_failure"])
        elif transition.goal_reached:
            reward = float(self.config["reward_goal"])
        else:
            reward = float(self.config["reward_step"])
        next_max = (
            max(
                self.q_values[(transition.next_state, action.target)]
                for action in transition.next_actions
            )
            if transition.next_actions and not transition.goal_reached
            else 0.0
        )
        key = (transition.state, transition.action.target)
        learning_rate = float(self.config["learning_rate"])
        target = reward + float(self.config["discount_factor"]) * next_max
        self.q_values[key] += learning_rate * (target - self.q_values[key])


class UCB1EdgeAdapter(BaselineAdapter):
    method_id = "UCB1_EDGE"

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self.counts: Dict[Tuple[str, str], int] = defaultdict(int)
        self.reward_sums: Dict[Tuple[str, str], float] = defaultdict(float)
        self.state_visits: Dict[str, int] = defaultdict(int)
        self._episode_edges: List[Tuple[str, str]] = []

    def start_episode(self, episode_index: int, start: str) -> None:
        super().start_episode(episode_index, start)
        self._episode_edges = []

    def select_action(
        self,
        episode_index: int,
        state: str,
        actions: Tuple[ActionView, ...],
    ) -> Optional[ActionView]:
        if not actions:
            return None
        untried = [action for action in actions if self.counts[(state, action.target)] == 0]
        if untried:
            return self.rng.choice(untried)
        total = max(1, self.state_visits[state])
        coefficient = float(self.config["exploration_coefficient"])

        def score(action: ActionView) -> Tuple[float, str]:
            key = (state, action.target)
            mean = self.reward_sums[key] / self.counts[key]
            bonus = coefficient * math.sqrt(math.log(total) / self.counts[key])
            return mean + bonus, action.target

        maximum = max(score(action)[0] for action in actions)
        best = [action for action in actions if score(action)[0] == maximum]
        return self.rng.choice(best)

    def observe(self, transition: Transition) -> None:
        super().observe(transition)
        self.state_visits[transition.state] += 1
        self._episode_edges.append((transition.state, transition.action.target))

    def end_episode(self, summary: EpisodeSummary) -> None:
        reward = 1.0 if summary.goal_reached else 0.0
        for key in self._episode_edges:
            self.counts[key] += 1
            self.reward_sums[key] += reward


class RandomRestartGreedyAdapter(BaselineAdapter):
    """Greedy with randomized episode restarts and persistent failure penalties.

    E0-G1-v1 resets position only between episodes, so this adapter never
    teleports within an episode.  Each protocol episode is one restart: ties and
    configured exploration are randomized, while failure evidence persists.
    """

    method_id = "RANDOM_RESTART_GREEDY"

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self.penalties: Dict[Tuple[str, str], float] = defaultdict(float)
        self._episode_edges: List[Tuple[str, str]] = []

    def start_episode(self, episode_index: int, start: str) -> None:
        super().start_episode(episode_index, start)
        self._episode_edges = []

    def select_action(
        self,
        episode_index: int,
        state: str,
        actions: Tuple[ActionView, ...],
    ) -> Optional[ActionView]:
        if not actions:
            return None
        if self.rng.random() < float(self.config["restart_exploration_probability"]):
            return self.rng.choice(actions)
        return min(
            actions,
            key=lambda action: (
                action.base_cost + self.penalties[(action.source, action.target)],
                action.target,
            ),
        )

    def observe(self, transition: Transition) -> None:
        super().observe(transition)
        key = (transition.state, transition.action.target)
        self._episode_edges.append(key)
        if transition.outcome == Outcome.FAILURE:
            self.penalties[key] += float(self.config["immediate_failure_penalty"])

    def end_episode(self, summary: EpisodeSummary) -> None:
        if summary.goal_reached:
            decay = float(self.config["success_penalty_decay"])
            for key in set(self._episode_edges):
                self.penalties[key] *= decay
            return
        increment = float(self.config["failed_episode_credit_penalty"])
        for key in set(self._episode_edges):
            self.penalties[key] += increment


class AStarAdapter(BaselineAdapter):
    method_id = "A_STAR"

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        if self.map_view is None:
            raise ValueError("A_STAR requires a full MapView")
        self.blocked_edges: set[Tuple[str, str]] = set()
        self._planned_path: List[str] = []

    def start_episode(self, episode_index: int, start: str) -> None:
        super().start_episode(episode_index, start)
        self.blocked_edges = set()
        self._planned_path = []

    def select_action(
        self,
        episode_index: int,
        state: str,
        actions: Tuple[ActionView, ...],
    ) -> Optional[ActionView]:
        assert self.map_view is not None
        if not self._planned_path or self._planned_path[0] != state:
            path = astar_shortest_path(
                self.map_view,
                state,
                blocked_edges=self.blocked_edges,
            )
            self._planned_path = path or []
        if len(self._planned_path) < 2:
            return None
        target = self._planned_path[1]
        return next((action for action in actions if action.target == target), None)

    def observe(self, transition: Transition) -> None:
        super().observe(transition)
        if transition.outcome == Outcome.FAILURE:
            self.blocked_edges.add((transition.state, transition.action.target))
            self._planned_path = []
        elif self._planned_path and self._planned_path[0] == transition.state:
            self._planned_path = self._planned_path[1:]


class DStarLitePlanner:
    """D* Lite with unit edge costs and an admissible zero heuristic."""

    def __init__(self, map_view: MapView, start: str):
        self.map_view = map_view
        self.start = start
        self.goal = map_view.goal
        self.last = start
        self.km = 0.0
        self.blocked_edges: set[Tuple[str, str]] = set()
        self.g: Dict[str, float] = defaultdict(lambda: math.inf)
        self.rhs: Dict[str, float] = defaultdict(lambda: math.inf)
        self.rhs[self.goal] = 0.0
        self._queue: List[Tuple[float, float, int, str]] = []
        self._counter = 0
        self._push(self.goal)
        self.compute_shortest_path()

    def _heuristic(self, first: str, second: str) -> float:
        return 0.0

    def _key(self, state: str) -> Tuple[float, float]:
        minimum = min(self.g[state], self.rhs[state])
        return minimum + self._heuristic(self.start, state) + self.km, minimum

    def _push(self, state: str) -> None:
        key = self._key(state)
        self._counter += 1
        heapq.heappush(self._queue, (key[0], key[1], self._counter, state))

    def _cost(self, source: str, target: str) -> float:
        return math.inf if (source, target) in self.blocked_edges else 1.0

    def _successors(self, state: str) -> Tuple[ActionView, ...]:
        return self.map_view.actions(state)

    def _update_vertex(self, state: str) -> None:
        if state != self.goal:
            self.rhs[state] = min(
                (
                    self._cost(state, action.target) + self.g[action.target]
                    for action in self._successors(state)
                ),
                default=math.inf,
            )
        if self.g[state] != self.rhs[state]:
            self._push(state)

    def _top_key(self) -> Tuple[float, float]:
        while self._queue:
            first, second, _, state = self._queue[0]
            if self.g[state] == self.rhs[state]:
                heapq.heappop(self._queue)
                continue
            if (first, second) != self._key(state):
                heapq.heappop(self._queue)
                self._push(state)
                continue
            return first, second
        return math.inf, math.inf

    def compute_shortest_path(self) -> None:
        while self._top_key() < self._key(self.start) or (
            self.rhs[self.start] != self.g[self.start]
        ):
            if not self._queue:
                break
            old_first, old_second, _, state = heapq.heappop(self._queue)
            old_key = (old_first, old_second)
            new_key = self._key(state)
            if self.g[state] == self.rhs[state]:
                continue
            if old_key < new_key:
                self._push(state)
            elif self.g[state] > self.rhs[state]:
                self.g[state] = self.rhs[state]
                for predecessor in self.map_view.predecessors(state):
                    self._update_vertex(predecessor)
            else:
                self.g[state] = math.inf
                self._update_vertex(state)
                for predecessor in self.map_view.predecessors(state):
                    self._update_vertex(predecessor)

    def move_start(self, new_start: str) -> None:
        self.km += self._heuristic(self.last, new_start)
        self.start = new_start
        self.last = new_start
        self.compute_shortest_path()

    def block_edge(self, source: str, target: str) -> None:
        self.blocked_edges.add((source, target))
        self._update_vertex(source)
        self.compute_shortest_path()

    def next_target(self) -> Optional[str]:
        candidates = [
            (
                self._cost(self.start, action.target) + self.g[action.target],
                action.target,
            )
            for action in self._successors(self.start)
            if not math.isinf(self._cost(self.start, action.target))
        ]
        if not candidates:
            return None
        value, target = min(candidates)
        return None if math.isinf(value) else target


class DStarLiteAdapter(BaselineAdapter):
    method_id = "D_STAR_LITE"

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        if self.map_view is None:
            raise ValueError("D_STAR_LITE requires a full MapView")
        self.planner: Optional[DStarLitePlanner] = None

    def start_episode(self, episode_index: int, start: str) -> None:
        super().start_episode(episode_index, start)
        assert self.map_view is not None
        self.planner = DStarLitePlanner(self.map_view, start)

    def select_action(
        self,
        episode_index: int,
        state: str,
        actions: Tuple[ActionView, ...],
    ) -> Optional[ActionView]:
        assert self.planner is not None
        target = self.planner.next_target()
        return next((action for action in actions if action.target == target), None)

    def observe(self, transition: Transition) -> None:
        super().observe(transition)
        assert self.planner is not None
        if transition.outcome == Outcome.FAILURE:
            self.planner.block_edge(transition.state, transition.action.target)
        else:
            self.planner.move_start(transition.next_state)


ADAPTER_TYPES = {
    "Q_LEARNING": QLearningAdapter,
    "UCB1_EDGE": UCB1EdgeAdapter,
    "RANDOM_RESTART_GREEDY": RandomRestartGreedyAdapter,
    "MEMORYLESS_GREEDY": MemorylessGreedyAdapter,
    "EPSILON_GREEDY": EpsilonGreedyAdapter,
    "UNIFORM_RANDOM": UniformRandomAdapter,
    "A_STAR": AStarAdapter,
    "D_STAR_LITE": DStarLiteAdapter,
}


def build_adapter(
    method_id: str,
    domain: G1DomainInstance,
    *,
    config_document: Optional[Mapping[str, Any]] = None,
) -> BaselineAdapter:
    """Build one empty-state adapter under the frozen information contract."""
    validate_method_registry()
    validate_development_seed(domain.generator_seed)
    if method_id not in ADAPTER_TYPES:
        raise ValueError(f"Unknown baseline method {method_id!r}")
    configs = dict(config_document or load_baseline_configs())
    method_config = configs["methods"][method_id]["parameters"]
    contract = METHOD_CONTRACTS[method_id]
    map_view = MapView.from_domain(domain) if contract.receives_full_map else None
    return ADAPTER_TYPES[method_id](
        goal=domain.goal,
        policy_seed=domain.policy_seed,
        config=method_config,
        map_view=map_view,
    )


def _oracle_cost(domain: G1DomainInstance, episode_index: int) -> int:
    if "stationary" in domain.oracle_cost_by_regime:
        return int(domain.oracle_cost_by_regime["stationary"])
    switch = int(domain.metadata["switch_absolute_episode_index"])
    key = "pre_switch" if episode_index < switch else "post_switch"
    return int(domain.oracle_cost_by_regime[key])


def _episode_phase(episode_index: int) -> str:
    adaptation = int(load_g1_protocol()["interaction_protocol"]["adaptation_episodes"])
    return "adaptation" if episode_index < adaptation else "evaluation"


def run_episode(
    domain: G1DomainInstance,
    adapter: BaselineAdapter,
    episode_index: int,
    *,
    interaction_budget: Optional[int] = None,
) -> EpisodeSummary:
    """Run one episode with FAILURE-as-no-transition semantics."""
    validate_development_seed(domain.generator_seed)
    budget = (
        int(interaction_budget) if interaction_budget is not None else 4 * domain.actual_node_count
    )
    if budget <= 0:
        raise ValueError("interaction_budget must be positive")
    timeout_seconds = float(
        load_g1_protocol()["interaction_protocol"]["wall_time_timeout_seconds_per_episode"]
    )
    deadline = time.perf_counter() + timeout_seconds

    executor = domain.executor(episode_index)
    state = domain.start
    path = [state]
    visit_counts: Dict[str, int] = {state: 1}
    interactions = 0
    total_cost = 0.0
    failures = 0
    terminal_reason = "interaction_budget_exhausted"
    adapter.start_episode(episode_index, state)

    while interactions < budget and state != domain.goal:
        actions = _local_actions(domain, state)
        if time.perf_counter() >= deadline:
            terminal_reason = "algorithm_timeout"
            break
        action = adapter.select_action(episode_index, state, actions)
        if time.perf_counter() >= deadline:
            terminal_reason = "algorithm_timeout"
            break
        if action is None:
            terminal_reason = "no_action"
            break
        if action not in actions:
            raise RuntimeError(
                f"{adapter.method_id} selected unavailable action {action.identifier}"
            )
        outcome = executor(action.source, action.target)
        interactions += 1
        total_cost += action.base_cost
        next_state = action.target if outcome == Outcome.SUCCESS else state
        if outcome == Outcome.FAILURE:
            failures += 1
        else:
            path.append(next_state)
            visit_counts[next_state] = visit_counts.get(next_state, 0) + 1
        next_actions = _local_actions(domain, next_state)
        adapter.observe(
            Transition(
                episode_index=episode_index,
                interaction_index=interactions - 1,
                state=state,
                action=action,
                outcome=outcome,
                next_state=next_state,
                next_actions=next_actions,
                goal=domain.goal,
            )
        )
        state = next_state

    goal_reached = state == domain.goal
    if goal_reached and terminal_reason != "algorithm_timeout":
        terminal_reason = "goal_reached"
    oracle = _oracle_cost(domain, episode_index)
    score = (
        oracle / max(interactions, oracle)
        if goal_reached and terminal_reason != "algorithm_timeout"
        else 0.0
    )
    summary = EpisodeSummary(
        episode_index=episode_index,
        phase=_episode_phase(episode_index),
        goal_reached=goal_reached and terminal_reason != "algorithm_timeout",
        interactions_used=interactions,
        interaction_budget=budget,
        total_cost=round(total_cost, 9),
        oracle_cost=oracle,
        success_adjusted_efficiency=score,
        revisits=sum(count - 1 for count in visit_counts.values() if count > 1),
        failure_count=failures,
        terminal_reason=terminal_reason,
        final_state=state,
        path=tuple(path),
    )
    adapter.end_episode(summary)
    return summary


def run_replicate(
    domain: G1DomainInstance,
    method_id: str,
    *,
    episode_count: Optional[int] = None,
    interaction_budget: Optional[int] = None,
) -> ReplicateResult:
    """Run one baseline replicate with learning state preserved across episodes."""
    protocol = load_g1_protocol()
    interaction_protocol = protocol["interaction_protocol"]
    total_episodes = int(interaction_protocol["adaptation_episodes"]) + int(
        interaction_protocol["evaluation_episodes"]
    )
    selected_count = total_episodes if episode_count is None else int(episode_count)
    if selected_count <= 0 or selected_count > total_episodes:
        raise ValueError(f"episode_count must lie in 1..{total_episodes}")
    adapter = build_adapter(method_id, domain)
    episodes = [
        run_episode(
            domain,
            adapter,
            episode_index,
            interaction_budget=interaction_budget,
        )
        for episode_index in range(selected_count)
    ]
    contract = METHOD_CONTRACTS[method_id]
    return ReplicateResult(
        protocol_id=PROTOCOL_ID,
        split="development",
        method=method_id,
        method_category=contract.category,
        comparator_eligible=contract.comparator_eligible,
        information_access=contract.information_access,
        domain_family=domain.family,
        target_node_count=domain.target_node_count,
        actual_node_count=domain.actual_node_count,
        generator_seed=domain.generator_seed,
        outcome_seed=domain.outcome_seed,
        policy_seed=domain.policy_seed,
        config_sha256=baseline_config_sha256(),
        episodes=episodes,
    )


validate_method_registry()
