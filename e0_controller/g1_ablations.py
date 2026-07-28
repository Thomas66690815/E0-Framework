"""Five causal E0 ablations for the preregistered Gate G1 protocol.

WP-2.3 implements the development-only method layer.  It deliberately keeps
the causal boundary narrow:

* all variants share empty-start historization and revisit handling;
* B through E share candidates, path family, horizon, cap, and override gate;
* only the aggregation named by ``E0-G1-v1`` changes between B, C, and D;
* E delegates its decision report to ``structural_geometry.influence_map``.

The module cannot construct holdout domains.  Its compatibility outputs are
engineering evidence, not Gate G1 results or a method ranking.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from lean.structural_geometry import (
    NavField,
    enumerate_continuations,
    influence_map,
    phase_regime,
    theta,
)

from .g1_baselines import (
    ActionView,
    BaselineAdapter,
    EpisodeSummary,
    Transition,
    run_episode,
)
from .g1_domains import (
    PROTOCOL_ID,
    G1DomainInstance,
    load_g1_protocol,
    protocol_sha256,
    validate_development_seed,
)
from .historization import Historization
from .landscape import Landscape
from .primitives import Edge, Outcome

CONFIG_PATH = Path(__file__).resolve().parents[1] / "docs" / "E0_G1_ABLATION_CONFIGS_v1.json"

ABLATION_METHODS = (
    "A_HIST",
    "B_INCOHERENT",
    "C_THETA_ZERO",
    "D_U1_PHASE",
    "E_FULL_GEOMETRY",
)
LOOKAHEAD_METHODS = ABLATION_METHODS[1:]
SIMPLER_CONTROL_CANDIDATES = ABLATION_METHODS[:3]

INFORMATION_ACCESS = "static_topology_and_edge_weights_plus_local_actions_and_observed_outcomes"


@dataclass(frozen=True)
class AblationContract:
    """Protocol-facing identity and causal role for one ablation."""

    method_id: str
    lookahead: bool
    aggregation: str
    phase: str
    purpose: str


@dataclass(frozen=True)
class PathFamily:
    """One bounded path enumeration shared by B through E."""

    candidates: Tuple[str, ...]
    paths_by_action: Mapping[str, Tuple[Tuple[str, ...], ...]]
    paths_expanded: int
    truncated: bool
    signature: str


@dataclass(frozen=True)
class DecisionRecord:
    """Causal diagnostics for one adapter decision."""

    method: str
    state: str
    candidates: Tuple[str, ...]
    greedy_action: Optional[str]
    preferred_action: Optional[str]
    selected_action: Optional[str]
    scores: Mapping[str, float]
    probabilities: Mapping[str, float]
    path_counts: Mapping[str, int]
    path_family_signature: Optional[str]
    paths_expanded: int
    path_cap_hit: bool
    confidence: float
    path_imbalance: float
    override: bool
    phase_regime: Optional[str]


@dataclass(frozen=True)
class AblationEpisodeResult:
    """One episode plus the WP-2.3 secondary diagnostics."""

    summary: EpisodeSummary
    status: str
    wall_time_ms: float
    decision_count: int
    paths_expanded: int
    path_cap_hits: int
    override_count: int
    override_success_count: int
    phase_regime_gradient_count: int
    phase_regime_interfering_count: int
    phase_regime_wrapped_count: int

    def to_record(self) -> Dict[str, Any]:
        record = self.summary.to_record()
        record.update(
            {
                "status": self.status,
                "wall_time_ms": self.wall_time_ms,
                "decision_count": self.decision_count,
                "paths_expanded": self.paths_expanded,
                "path_cap_hits": self.path_cap_hits,
                "override_count": self.override_count,
                "override_success_count": self.override_success_count,
                "override_success_rate": (
                    self.override_success_count / self.override_count
                    if self.override_count
                    else None
                ),
                "phase_regime_gradient_count": self.phase_regime_gradient_count,
                "phase_regime_interfering_count": (self.phase_regime_interfering_count),
                "phase_regime_wrapped_count": self.phase_regime_wrapped_count,
            }
        )
        return record


@dataclass
class AblationReplicateResult:
    """All adaptation/evaluation episodes for one ablation and domain."""

    protocol_id: str
    split: str
    method: str
    information_access: str
    domain_family: str
    target_node_count: int
    actual_node_count: int
    generator_seed: int
    outcome_seed: int
    policy_seed: int
    config_sha256: str
    episodes: List[AblationEpisodeResult]

    @property
    def evaluation_episodes(self) -> List[AblationEpisodeResult]:
        return [episode for episode in self.episodes if episode.summary.phase == "evaluation"]

    def to_record(self, *, include_episodes: bool = True) -> Dict[str, Any]:
        evaluation = self.evaluation_episodes
        record: Dict[str, Any] = {
            "protocol_id": self.protocol_id,
            "artifact_kind": "development_ablation_run",
            "not_g1_result": True,
            "holdout_accessed": False,
            "split": self.split,
            "method": self.method,
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
                sum(episode.summary.goal_reached for episode in evaluation) / len(evaluation)
                if evaluation
                else None
            ),
            "evaluation_mean_success_adjusted_efficiency": (
                sum(episode.summary.success_adjusted_efficiency for episode in evaluation)
                / len(evaluation)
                if evaluation
                else None
            ),
            "paths_expanded": sum(episode.paths_expanded for episode in self.episodes),
            "path_cap_hits": sum(episode.path_cap_hits for episode in self.episodes),
            "override_count": sum(episode.override_count for episode in self.episodes),
            "wall_time_ms": sum(episode.wall_time_ms for episode in self.episodes),
        }
        if include_episodes:
            record["episodes"] = [episode.to_record() for episode in self.episodes]
        return record


def load_ablation_configs() -> Dict[str, Any]:
    """Load and verify the frozen WP-2.3 configuration document."""
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if data.get("protocol_id") != PROTOCOL_ID:
        raise ValueError("Ablation config protocol does not match E0-G1-v1")
    if data.get("frozen_before_holdout") is not True:
        raise ValueError("Ablation configs must be frozen before holdout access")
    if data.get("holdout_execution_started") is not False:
        raise ValueError("WP-2.3 requires holdout_execution_started=false")
    if data.get("protocol_sha256") != protocol_sha256():
        raise ValueError("Frozen ablation configs reference a different protocol")
    configured = tuple(data.get("methods", {}).keys())
    if configured != ABLATION_METHODS:
        raise ValueError(f"Ablation config IDs differ from the protocol order: {configured}")
    return data


def ablation_config_sha256() -> str:
    """Return the byte-level digest of the frozen ablation configuration."""
    return hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest()


def protocol_ablation_contracts() -> Dict[str, AblationContract]:
    """Return the exact ordered method registry from E0-G1-v1."""
    items = load_g1_protocol()["e0_ablations"]
    contracts = {
        str(item["id"]): AblationContract(
            method_id=str(item["id"]),
            lookahead=bool(item["lookahead"]),
            aggregation=str(item["aggregation"]),
            phase=str(item["phase"]),
            purpose=str(item["purpose"]),
        )
        for item in items
    }
    if tuple(contracts) != ABLATION_METHODS:
        raise ValueError(f"Ablation registry differs from protocol: {tuple(contracts)}")
    return contracts


def validate_ablation_contract() -> None:
    """Ensure config, protocol constants, and code boundaries remain aligned."""
    protocol = load_g1_protocol()
    config = load_ablation_configs()
    contracts = protocol_ablation_contracts()
    constants = protocol["ablation_constants"]
    shared = config["shared"]
    expected = {
        "path_horizon": int(constants["path_horizon"]),
        "min_confidence": float(constants["min_confidence"]),
        "max_imbalance": float(constants["max_imbalance"]),
        "max_paths_per_decision": int(constants["max_paths_per_decision"]),
    }
    actual = {key: shared[key] for key in expected}
    if actual != expected:
        raise ValueError(f"Frozen shared constants differ: {actual} != {expected}")
    if constants["same_candidates"] is not True:
        raise ValueError("WP-2.3 requires same_candidates=true")
    if constants["same_path_family_for_B_to_E"] is not True:
        raise ValueError("WP-2.3 requires one B-E path family")
    if constants["same_override_rule_for_B_to_E"] is not True:
        raise ValueError("WP-2.3 requires one B-E override rule")
    for method, contract in contracts.items():
        frozen = config["methods"][method]
        if bool(frozen["lookahead"]) != contract.lookahead:
            raise ValueError(f"{method} lookahead differs from protocol")
        if frozen["aggregation"] != contract.aggregation:
            raise ValueError(f"{method} aggregation differs from protocol")
        if frozen["phase"] != contract.phase:
            raise ValueError(f"{method} phase differs from protocol")


def _clone_landscape(domain: G1DomainInstance, config: Mapping[str, Any]) -> Landscape:
    history = config["shared"]["historization"]
    landscape = Landscape(
        historization=Historization(
            rho=float(history["rho"]),
            lambda_s=float(history["lambda_s"]),
            lambda_f=float(history["lambda_f"]),
            delta_max=float(history["delta_max"]),
        )
    )
    for state in sorted(domain.landscape.states):
        landscape.add_state(state)
    for edge in sorted(domain.landscape.edges, key=lambda item: (item.source, item.target)):
        delta = domain.landscape.difference(edge.source, edge.target)
        assert delta is not None
        landscape.add_edge(
            edge.source,
            edge.target,
            delta=delta,
            resistance=domain.landscape.base_resistance(edge.source, edge.target),
            **domain.landscape.edge_meta(edge.source, edge.target),
        )
    return landscape


def _nav_field(landscape: Landscape) -> NavField:
    field = NavField()
    for state in sorted(landscape.states):
        field.add_node(state)
    for edge in sorted(landscape.edges, key=lambda item: (item.source, item.target)):
        delta = landscape.difference(edge.source, edge.target)
        assert delta is not None
        field.add_edge(
            edge.source,
            edge.target,
            cost=landscape.effective_tension(edge.source, edge.target),
            weight=delta,
        )
    return field


def _path_family(
    field: NavField,
    current: str,
    candidates: Sequence[str],
    shared: Mapping[str, Any],
) -> PathFamily:
    paths, truncated = enumerate_continuations(
        field,
        current,
        int(shared["path_horizon"]),
        geometry=str(shared["path_geometry"]),
        max_paths=int(shared["max_paths_per_decision"]),
    )
    by_action: Dict[str, List[Tuple[str, ...]]] = {action: [] for action in candidates}
    for path in paths:
        if len(path) >= 2 and path[1] in by_action:
            by_action[path[1]].append(tuple(path))
    for action in candidates:
        direct = (current, action)
        if direct not in by_action[action]:
            by_action[action].insert(0, direct)
    frozen = {action: tuple(by_action[action]) for action in candidates}
    payload = json.dumps(
        {
            "candidates": list(candidates),
            "paths": {action: [list(path) for path in frozen[action]] for action in candidates},
            "truncated": truncated,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return PathFamily(
        candidates=tuple(candidates),
        paths_by_action=frozen,
        paths_expanded=len(paths),
        truncated=bool(truncated),
        signature=hashlib.sha256(payload).hexdigest(),
    )


def _normalise_scores(
    scores: Mapping[str, float],
) -> Tuple[Dict[str, float], Optional[str], float]:
    if not scores:
        return {}, None, 0.0
    total = sum(scores.values())
    probabilities = {
        action: (score / total if total > 0.0 else 0.0) for action, score in scores.items()
    }
    maximum = max(scores.values())
    preferred = min(action for action, score in scores.items() if score == maximum)
    ordered = sorted(probabilities.values(), reverse=True)
    confidence = ordered[0] - ordered[1] if len(ordered) >= 2 else 0.0
    return probabilities, preferred, confidence


def _path_imbalance(path_counts: Mapping[str, int]) -> float:
    counts = [count for count in path_counts.values() if count > 0]
    return max(counts) / min(counts) if len(counts) >= 2 else 1.0


def _manual_scores(
    method_id: str,
    field: NavField,
    family: PathFamily,
) -> Dict[str, float]:
    scores: Dict[str, float] = {}
    for action in family.candidates:
        paths = family.paths_by_action[action]
        if method_id == "B_INCOHERENT":
            scores[action] = sum(math.exp(-2.0 * field.path_cost(path)) for path in paths)
        elif method_id == "C_THETA_ZERO":
            mass = sum(math.exp(-field.path_cost(path)) for path in paths)
            scores[action] = mass * mass
        elif method_id == "D_U1_PHASE":
            amplitude = sum(
                (
                    math.exp(-field.path_cost(path))
                    * complex(math.cos(theta(field, path)), math.sin(theta(field, path)))
                    for path in paths
                ),
                start=0j,
            )
            scores[action] = abs(amplitude) ** 2
        else:
            raise ValueError(f"{method_id} has no manual path aggregation")
    return scores


class E0AblationAdapter(BaselineAdapter):
    """One of the five E0 causal variants under a shared interaction API."""

    def __init__(
        self,
        method_id: str,
        domain: G1DomainInstance,
        config_document: Mapping[str, Any],
    ):
        super().__init__(
            goal=domain.goal,
            policy_seed=domain.policy_seed,
            config=config_document["methods"][method_id],
        )
        self.method_id = method_id
        self.contract = protocol_ablation_contracts()[method_id]
        self.document = dict(config_document)
        self.shared = dict(config_document["shared"])
        self.landscape = _clone_landscape(domain, config_document)
        self.recent: List[str] = []
        self.decision_records: List[DecisionRecord] = []
        self._episode_records: List[DecisionRecord] = []
        self._last_override = False
        self._override_success_count = 0

    def start_episode(self, episode_index: int, start: str) -> None:
        super().start_episode(episode_index, start)
        self.recent = []
        self._episode_records = []
        self._last_override = False
        self._override_success_count = 0

    def _greedy(self, state: str, actions: Sequence[ActionView]) -> ActionView:
        alpha = float(self.shared["revisit"]["alpha"])
        return min(
            actions,
            key=lambda action: (
                self.landscape.effective_tension(state, action.target)
                * (1.0 + alpha if action.target in self.recent else 1.0),
                action.target,
            ),
        )

    def _lookahead_record(
        self,
        state: str,
        actions: Tuple[ActionView, ...],
        greedy: ActionView,
    ) -> DecisionRecord:
        candidates = tuple(sorted(action.target for action in actions))
        field = _nav_field(self.landscape)
        family = _path_family(field, state, candidates, self.shared)
        if self.method_id == "E_FULL_GEOMETRY":
            report = influence_map(
                field,
                state,
                horizon=int(self.shared["path_horizon"]),
                geometry=str(self.shared["path_geometry"]),
                candidates=candidates,
                max_paths=int(self.shared["max_paths_per_decision"]),
                keep_paths=True,
            )
            report_paths = {
                item.action: tuple(tuple(path) for path in item.paths) for item in report.actions
            }
            if report_paths != family.paths_by_action:
                raise RuntimeError("E_FULL_GEOMETRY path family differs from B-D")
            scores = {item.action: item.intensity for item in report.actions}
            regime = str(
                phase_regime(
                    field,
                    horizon=int(self.shared["path_horizon"]),
                )["regime"]
            )
        else:
            scores = _manual_scores(self.method_id, field, family)
            regime = (
                str(
                    phase_regime(
                        field,
                        horizon=int(self.shared["path_horizon"]),
                    )["regime"]
                )
                if self.method_id == "D_U1_PHASE"
                else None
            )
        probabilities, preferred, confidence = _normalise_scores(scores)
        path_counts = {action: len(family.paths_by_action[action]) for action in candidates}
        imbalance = _path_imbalance(path_counts)
        override = (
            not family.truncated
            and preferred is not None
            and preferred != greedy.target
            and confidence >= float(self.shared["min_confidence"])
            and imbalance <= float(self.shared["max_imbalance"])
        )
        selected = preferred if override else greedy.target
        return DecisionRecord(
            method=self.method_id,
            state=state,
            candidates=candidates,
            greedy_action=greedy.target,
            preferred_action=preferred,
            selected_action=None if family.truncated else selected,
            scores=scores,
            probabilities=probabilities,
            path_counts=path_counts,
            path_family_signature=family.signature,
            paths_expanded=family.paths_expanded,
            path_cap_hit=family.truncated,
            confidence=confidence,
            path_imbalance=imbalance,
            override=override,
            phase_regime=regime,
        )

    def select_action(
        self,
        episode_index: int,
        state: str,
        actions: Tuple[ActionView, ...],
    ) -> Optional[ActionView]:
        if not actions:
            self._last_override = False
            return None
        greedy = self._greedy(state, actions)
        if not self.contract.lookahead:
            record = DecisionRecord(
                method=self.method_id,
                state=state,
                candidates=tuple(sorted(action.target for action in actions)),
                greedy_action=greedy.target,
                preferred_action=None,
                selected_action=greedy.target,
                scores={},
                probabilities={},
                path_counts={},
                path_family_signature=None,
                paths_expanded=0,
                path_cap_hit=False,
                confidence=0.0,
                path_imbalance=1.0,
                override=False,
                phase_regime=None,
            )
        else:
            record = self._lookahead_record(state, actions, greedy)
        self.decision_records.append(record)
        self._episode_records.append(record)
        self._last_override = record.override
        if record.selected_action is None:
            return None
        return next(action for action in actions if action.target == record.selected_action)

    def observe(self, transition: Transition) -> None:
        super().observe(transition)
        edge = Edge(transition.state, transition.action.target)
        r_before = self.landscape.effective_resistance(edge.source, edge.target)
        self.landscape.historization.inscribe(
            edge,
            transition.outcome,
            mode=self.method_id,
            revisit_count=int(transition.action.target in self.recent),
        )
        self.landscape.historization.record(
            edge,
            transition.outcome,
            r_before,
            self.landscape.effective_resistance(edge.source, edge.target),
        )
        if self._last_override and transition.outcome == Outcome.SUCCESS:
            self._override_success_count += 1
        self.recent.append(transition.state)
        recent_k = int(self.shared["revisit"]["recent_k"])
        if len(self.recent) > recent_k:
            self.recent = self.recent[-recent_k:]
        self._last_override = False

    def episode_diagnostics(self) -> Dict[str, Any]:
        regimes = {"gradient": 0, "interfering": 0, "wrapped": 0}
        for record in self._episode_records:
            if record.phase_regime in regimes:
                regimes[record.phase_regime] += 1
        return {
            "decision_count": len(self._episode_records),
            "paths_expanded": sum(record.paths_expanded for record in self._episode_records),
            "path_cap_hits": sum(record.path_cap_hit for record in self._episode_records),
            "override_count": sum(record.override for record in self._episode_records),
            "override_success_count": self._override_success_count,
            "phase_regime_gradient_count": regimes["gradient"],
            "phase_regime_interfering_count": regimes["interfering"],
            "phase_regime_wrapped_count": regimes["wrapped"],
        }


def build_ablation_adapter(
    method_id: str,
    domain: G1DomainInstance,
    *,
    config_document: Optional[Mapping[str, Any]] = None,
) -> E0AblationAdapter:
    """Build one empty-state development adapter."""
    validate_development_seed(domain.generator_seed)
    validate_ablation_contract()
    if method_id not in ABLATION_METHODS:
        raise ValueError(f"Unknown E0 ablation {method_id!r}")
    config = dict(config_document or load_ablation_configs())
    return E0AblationAdapter(method_id, domain, config)


def run_ablation_episode(
    domain: G1DomainInstance,
    adapter: E0AblationAdapter,
    episode_index: int,
    *,
    interaction_budget: Optional[int] = None,
) -> AblationEpisodeResult:
    """Run one fair-budget episode and attach causal diagnostics."""
    started = time.perf_counter()
    summary = run_episode(
        domain,
        adapter,
        episode_index,
        interaction_budget=interaction_budget,
    )
    wall_time_ms = (time.perf_counter() - started) * 1000.0
    diagnostics = adapter.episode_diagnostics()
    timeout_seconds = float(
        load_g1_protocol()["interaction_protocol"]["wall_time_timeout_seconds_per_episode"]
    )
    if diagnostics["path_cap_hits"]:
        status = "path_cap_hit"
    elif wall_time_ms > timeout_seconds * 1000.0:
        status = "algorithm_timeout"
    else:
        status = "completed"
    if status != "completed":
        summary = replace(
            summary,
            goal_reached=False,
            success_adjusted_efficiency=0.0,
            terminal_reason=status,
        )
    return AblationEpisodeResult(
        summary=summary,
        status=status,
        wall_time_ms=round(wall_time_ms, 6),
        **diagnostics,
    )


def run_ablation_replicate(
    domain: G1DomainInstance,
    method_id: str,
    *,
    episode_count: Optional[int] = None,
    interaction_budget: Optional[int] = None,
) -> AblationReplicateResult:
    """Run one development replicate while preserving method learning state."""
    protocol = load_g1_protocol()
    interaction = protocol["interaction_protocol"]
    total = int(interaction["adaptation_episodes"]) + int(interaction["evaluation_episodes"])
    selected_count = total if episode_count is None else int(episode_count)
    if selected_count <= 0 or selected_count > total:
        raise ValueError(f"episode_count must lie in 1..{total}")
    adapter = build_ablation_adapter(method_id, domain)
    episodes = [
        run_ablation_episode(
            domain,
            adapter,
            episode_index,
            interaction_budget=interaction_budget,
        )
        for episode_index in range(selected_count)
    ]
    return AblationReplicateResult(
        protocol_id=PROTOCOL_ID,
        split="development",
        method=method_id,
        information_access=INFORMATION_ACCESS,
        domain_family=domain.family,
        target_node_count=domain.target_node_count,
        actual_node_count=domain.actual_node_count,
        generator_seed=domain.generator_seed,
        outcome_seed=domain.outcome_seed,
        policy_seed=domain.policy_seed,
        config_sha256=ablation_config_sha256(),
        episodes=episodes,
    )


validate_ablation_contract()
