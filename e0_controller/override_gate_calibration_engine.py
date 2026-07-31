"""Calibration-only domains and deterministic paired decision branches.

WP-GATE-0.5 exposes no CLI and cannot construct verification or protected
holdout domains.  The branch engine is reusable by a later bounded runner, but
this module does not execute the preregistered calibration matrix.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, replace
from typing import Any, Dict, List, Mapping, Optional, Tuple

from .g1_ablations import (
    DecisionRecord,
    E0AblationAdapter,
    load_ablation_configs,
)
from .g1_baselines import (
    ActionView,
    EpisodeSummary,
    Transition,
    _local_actions,
)
from .g1_domains import (
    BUILDERS,
    CALIBRATION_SEED_NAMESPACE,
    G1DomainInstance,
    G1EpisodeExecutor,
    validate_domain,
)
from .override_gate import OverrideGateMode, OverrideGatePolicy
from .override_gate_calibration import load_calibration_instance, seeds_for_split
from .primitives import Edge, Outcome

CALIBRATION_SPLIT = "calibration"
METHOD_ID = "E_FULL_GEOMETRY"


@dataclass
class _EpisodeState:
    state: str
    path: List[str]
    visit_counts: Dict[str, int]
    interactions: int = 0
    total_cost: float = 0.0
    failures: int = 0

    def clone(self) -> "_EpisodeState":
        return _EpisodeState(
            state=self.state,
            path=list(self.path),
            visit_counts=dict(self.visit_counts),
            interactions=self.interactions,
            total_cost=self.total_cost,
            failures=self.failures,
        )


@dataclass(frozen=True)
class BranchOutcome:
    """Terminal utility and diagnostics for one counterfactual branch."""

    first_action: str
    first_outcome: str
    utility: float
    goal_reached: bool
    interactions_used: int
    terminal_reason: str
    final_state: str
    path: Tuple[str, ...]


@dataclass(frozen=True)
class PairedDecisionEvidence:
    """One common-state greedy/lookahead branch comparison."""

    state_hash: str
    random_stream_id: str
    domain_family: str
    scale: int
    generator_seed: int
    episode_index: int
    interaction_index: int
    geometry: str
    horizon: int
    action_count: int
    phase_regime: Optional[str]
    support_margin: float
    path_imbalance: float
    path_cap_hit: bool
    greedy_action: str
    lookahead_action: str
    greedy: BranchOutcome
    lookahead: BranchOutcome
    parent_run_mutated: bool = False

    @property
    def delta_utility(self) -> float:
        return self.lookahead.utility - self.greedy.utility

    def to_record(self) -> Dict[str, Any]:
        return {
            "state_hash": self.state_hash,
            "random_stream_id": self.random_stream_id,
            "domain_family": self.domain_family,
            "scale": self.scale,
            "generator_seed": self.generator_seed,
            "episode_index": self.episode_index,
            "interaction_index": self.interaction_index,
            "geometry": self.geometry,
            "horizon": self.horizon,
            "action_count": self.action_count,
            "phase_regime": self.phase_regime,
            "support_margin": self.support_margin,
            "path_imbalance": self.path_imbalance,
            "path_cap_hit": self.path_cap_hit,
            "greedy_action": self.greedy_action,
            "lookahead_action": self.lookahead_action,
            "greedy_utility": self.greedy.utility,
            "lookahead_utility": self.lookahead.utility,
            "delta_utility": self.delta_utility,
            "greedy_branch": _branch_record(self.greedy),
            "lookahead_branch": _branch_record(self.lookahead),
            "parent_run_mutated": self.parent_run_mutated,
        }


@dataclass(frozen=True)
class InstrumentedEpisodeResult:
    """Parent closed-loop episode plus non-mutating branch evidence."""

    summary: EpisodeSummary
    policy_id: str
    decision_records: Tuple[DecisionRecord, ...]
    paired_decisions: Tuple[PairedDecisionEvidence, ...]
    path_cap_hits: int


class CalibrationEFullAdapter(E0AblationAdapter):
    """E_FULL_GEOMETRY with one explicit frozen candidate gate policy."""

    def __init__(
        self,
        domain: G1DomainInstance,
        policy: OverrideGatePolicy,
        *,
        config_document: Optional[Mapping[str, Any]] = None,
    ):
        if policy.mode not in {OverrideGateMode.DISABLED, OverrideGateMode.FIXED}:
            raise ValueError("Calibration adapter requires disabled or fixed policy")
        expected = candidate_policy(policy.policy_id)
        if policy.to_dict() != expected.to_dict():
            raise ValueError("Calibration adapter requires an exact frozen candidate")
        config = (
            load_ablation_configs()
            if config_document is None
            else dict(config_document)
        )
        super().__init__(METHOD_ID, domain, config)
        self.override_gate_policy = policy

    def _lookahead_record(
        self,
        state: str,
        actions: Tuple[ActionView, ...],
        greedy: ActionView,
    ) -> DecisionRecord:
        record = super()._lookahead_record(state, actions, greedy)
        allowed = self.override_gate_policy.allows_override(
            disagrees=(
                record.preferred_action is not None
                and record.preferred_action != record.greedy_action
            ),
            support_margin=record.confidence,
            path_imbalance=record.path_imbalance,
            path_cap_hit=record.path_cap_hit,
        )
        if record.path_cap_hit:
            selected = None
        elif allowed:
            selected = record.preferred_action
        else:
            selected = record.greedy_action
        return replace(record, selected_action=selected, override=allowed)


def build_calibration_domain(
    family: str,
    scale: int,
    seed: int,
) -> G1DomainInstance:
    """Construct one calibration domain; protected split seeds fail closed."""
    instance = load_calibration_instance()
    if family not in instance["domain_manifest"]["families"]:
        raise ValueError(f"Unknown calibration family {family!r}")
    if scale not in instance["domain_manifest"]["scales"]:
        raise ValueError(f"Scale {scale} is outside the frozen calibration scope")
    if seed not in seeds_for_split(CALIBRATION_SPLIT, instance):
        raise ValueError(f"Seed {seed} is outside the calibration split")
    builder = BUILDERS[family]
    domain = builder(
        scale,
        seed,
        seed_namespace=CALIBRATION_SEED_NAMESPACE,
    )
    invariants = validate_domain(domain)
    if not all(item["passed"] for item in invariants):
        raise RuntimeError(f"Calibration domain invariants failed: {invariants}")
    return domain


def calibration_domain_record(domain: G1DomainInstance) -> Dict[str, Any]:
    """Return a correctly labelled, structure-only calibration-domain record."""
    if domain.seed_namespace != CALIBRATION_SEED_NAMESPACE:
        raise ValueError("Domain is not in the override-gate calibration namespace")
    instance = load_calibration_instance()
    if domain.generator_seed not in seeds_for_split(CALIBRATION_SPLIT, instance):
        raise ValueError("Domain seed is outside the frozen calibration split")
    invariants = validate_domain(domain)
    return {
        "instance_id": instance["instance_id"],
        "protocol_id": instance["protocol_id"],
        "source_commit": instance["source_commit"],
        "artifact_kind": "calibration_domain_validation",
        "not_gate_result": True,
        "holdout_accessed": False,
        "split": CALIBRATION_SPLIT,
        "run_id": domain.run_id,
        "domain_family": domain.family,
        "target_node_count": domain.target_node_count,
        "actual_node_count": domain.actual_node_count,
        "edge_count": domain.edge_count,
        "generator_seed": domain.generator_seed,
        "outcome_seed": domain.outcome_seed,
        "policy_seed": domain.policy_seed,
        "topology_sha256": domain.topology_sha256(),
        "invariants": invariants,
        "invariant_pass": all(item["passed"] for item in invariants),
        "domains_instantiated": 1,
        "outcomes_observed": 0,
    }


def candidate_policy(
    policy_id: str,
    *,
    instance: Optional[Mapping[str, Any]] = None,
) -> OverrideGatePolicy:
    """Materialize one exact candidate from the frozen instance."""
    document = load_calibration_instance() if instance is None else dict(instance)
    candidates = {
        str(record["policy_id"]): record
        for record in document["candidate_policies"]
    }
    if policy_id not in candidates:
        raise ValueError(f"Unknown frozen candidate policy {policy_id!r}")
    record = candidates[policy_id]
    common = document["candidate_common_guards"]
    scope = {
        **document["scope"],
        "domain_families": list(document["domain_manifest"]["families"]),
        "scales": list(document["domain_manifest"]["scales"]),
    }
    provenance = {
        "kind": "preregistered_candidate",
        "protocol_id": document["protocol_id"],
        "instance_id": document["instance_id"],
        "source_commit": document["source_commit"],
        "protected_holdout_accessed": False,
    }
    if record["mode"] == "disabled":
        return OverrideGatePolicy(
            policy_id=policy_id,
            policy_version="1.0",
            mode=OverrideGateMode.DISABLED,
            min_support_margin=None,
            max_path_imbalance=float(common["max_path_imbalance"]),
            forbid_path_cap_hit=bool(common["forbid_path_cap_hit"]),
            revisit_guard="none",
            health_guard="none",
            scope=scope,
            provenance=provenance,
        )
    return OverrideGatePolicy(
        policy_id=policy_id,
        policy_version="1.0",
        mode=OverrideGateMode.FIXED,
        min_support_margin=float(record["min_support_margin"]),
        max_path_imbalance=float(common["max_path_imbalance"]),
        forbid_path_cap_hit=bool(common["forbid_path_cap_hit"]),
        revisit_guard="none",
        health_guard="none",
        scope=scope,
        provenance=provenance,
    )


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _clone_adapter(
    adapter: CalibrationEFullAdapter,
) -> CalibrationEFullAdapter:
    """Deep-copy mutable decision state while sharing the immutable policy."""
    return copy.deepcopy(
        adapter,
        {id(adapter.override_gate_policy): adapter.override_gate_policy},
    )


def _edge_values(values: Mapping[Edge, Any]) -> List[List[Any]]:
    return [
        [edge.source, edge.target, values[edge]]
        for edge in sorted(values, key=lambda item: (item.source, item.target))
    ]


def _state_hash(
    domain: G1DomainInstance,
    adapter: CalibrationEFullAdapter,
    executor: G1EpisodeExecutor,
    episode_index: int,
    episode: _EpisodeState,
) -> str:
    """Hash every state component that can influence the next decision."""
    history = adapter.landscape.historization.to_snapshot_dict()
    field_costs = (
        [
            [edge.source, edge.target, adapter._field._cost[edge]]
            for edge in sorted(
                adapter._field._cost,
                key=lambda item: (item.source, item.target),
            )
        ]
        if adapter._field is not None
        else []
    )
    payload = {
        "domain_topology_sha256": domain.topology_sha256(),
        "generator_seed": domain.generator_seed,
        "episode_index": episode_index,
        "state": episode.state,
        "path": episode.path,
        "visit_counts": sorted(episode.visit_counts.items()),
        "interactions": episode.interactions,
        "total_cost": episode.total_cost,
        "failures": episode.failures,
        "recent": list(adapter.recent),
        "adapter_rng_state": adapter.rng.getstate(),
        "episodes_started": adapter.episodes_started,
        "observations_received": adapter.observations_received,
        "last_override": adapter._last_override,
        "override_success_count": adapter._override_success_count,
        "observed_edges": sorted(
            [[edge.source, edge.target] for edge in adapter._observed_edges]
        ),
        "executor_attempts": sorted(executor._attempts.items()),
        "historization": {
            "tau": history["tau"],
            "rho": history["rho"],
            "lambda_s": history["lambda_s"],
            "lambda_f": history["lambda_f"],
            "delta_max": history["delta_max"],
            "rho_s": history["rho_s"],
            "rho_f": history["rho_f"],
            "U": _edge_values(history["U"]),
            "F": _edge_values(history["F"]),
            "tau_last": _edge_values(history["tau_last"]),
            "confirmations": _edge_values(history["confirmations"]),
            "surprises": _edge_values(history["surprises"]),
            "inter_visit_intervals": list(
                adapter.landscape.historization._inter_visit_intervals
            ),
            "surprise_dampening": (
                adapter.landscape.historization.surprise_dampening
            ),
        },
        "field_costs": field_costs,
    }
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _oracle_cost(domain: G1DomainInstance, episode_index: int) -> int:
    if "stationary" in domain.oracle_cost_by_regime:
        return int(domain.oracle_cost_by_regime["stationary"])
    switch = int(domain.metadata["switch_absolute_episode_index"])
    regime = "pre_switch" if episode_index < switch else "post_switch"
    return int(domain.oracle_cost_by_regime[regime])


def _apply_action(
    domain: G1DomainInstance,
    adapter: CalibrationEFullAdapter,
    executor: G1EpisodeExecutor,
    episode_index: int,
    episode: _EpisodeState,
    action: ActionView,
) -> Outcome:
    outcome = executor(action.source, action.target)
    episode.interactions += 1
    episode.total_cost += action.base_cost
    next_state = action.target if outcome == Outcome.SUCCESS else episode.state
    if outcome == Outcome.FAILURE:
        episode.failures += 1
    else:
        episode.path.append(next_state)
        episode.visit_counts[next_state] = episode.visit_counts.get(next_state, 0) + 1
    next_actions = _local_actions(domain, next_state)
    adapter.observe(
        Transition(
            episode_index=episode_index,
            interaction_index=episode.interactions - 1,
            state=episode.state,
            action=action,
            outcome=outcome,
            next_state=next_state,
            next_actions=next_actions,
            goal=domain.goal,
        )
    )
    episode.state = next_state
    return outcome


def _finish_summary(
    domain: G1DomainInstance,
    episode_index: int,
    episode: _EpisodeState,
    budget: int,
    terminal_reason: str,
) -> EpisodeSummary:
    goal_reached = episode.state == domain.goal
    if goal_reached:
        terminal_reason = "goal_reached"
    oracle = _oracle_cost(domain, episode_index)
    utility = (
        oracle / max(episode.interactions, oracle)
        if goal_reached
        else 0.0
    )
    adaptation = int(
        load_calibration_instance()["domain_manifest"]["adaptation_episodes"]
    )
    return EpisodeSummary(
        episode_index=episode_index,
        phase="adaptation" if episode_index < adaptation else "evaluation",
        goal_reached=goal_reached,
        interactions_used=episode.interactions,
        interaction_budget=budget,
        total_cost=round(episode.total_cost, 9),
        oracle_cost=oracle,
        success_adjusted_efficiency=utility,
        revisits=sum(
            count - 1 for count in episode.visit_counts.values() if count > 1
        ),
        failure_count=episode.failures,
        terminal_reason=terminal_reason,
        final_state=episode.state,
        path=tuple(episode.path),
    )


def _rollout_branch(
    domain: G1DomainInstance,
    adapter_snapshot: CalibrationEFullAdapter,
    executor_snapshot: G1EpisodeExecutor,
    episode_index: int,
    episode_snapshot: _EpisodeState,
    first_action_target: str,
    *,
    first_is_override: bool,
    budget: int,
    disabled_policy: OverrideGatePolicy,
) -> BranchOutcome:
    adapter = _clone_adapter(adapter_snapshot)
    executor = copy.deepcopy(executor_snapshot)
    episode = episode_snapshot.clone()
    adapter.override_gate_policy = disabled_policy

    actions = _local_actions(domain, episode.state)
    adapter.select_action(episode_index, episode.state, actions)
    action = next(
        (candidate for candidate in actions if candidate.target == first_action_target),
        None,
    )
    if action is None:
        raise RuntimeError(f"Branch action {first_action_target!r} is unavailable")
    adapter._last_override = first_is_override
    first_outcome = _apply_action(
        domain,
        adapter,
        executor,
        episode_index,
        episode,
        action,
    )

    terminal_reason = "interaction_budget_exhausted"
    while episode.interactions < budget and episode.state != domain.goal:
        actions = _local_actions(domain, episode.state)
        action = adapter.select_action(episode_index, episode.state, actions)
        if action is None:
            record = adapter.decision_records[-1] if adapter.decision_records else None
            terminal_reason = (
                "path_cap_hit"
                if record is not None and record.path_cap_hit
                else "no_action"
            )
            break
        _apply_action(
            domain,
            adapter,
            executor,
            episode_index,
            episode,
            action,
        )
    summary = _finish_summary(
        domain,
        episode_index,
        episode,
        budget,
        terminal_reason,
    )
    adapter.end_episode(summary)
    return BranchOutcome(
        first_action=first_action_target,
        first_outcome=first_outcome.value,
        utility=summary.success_adjusted_efficiency,
        goal_reached=summary.goal_reached,
        interactions_used=summary.interactions_used,
        terminal_reason=summary.terminal_reason,
        final_state=summary.final_state,
        path=summary.path,
    )


def _branch_record(branch: BranchOutcome) -> Dict[str, Any]:
    return {
        "first_action": branch.first_action,
        "first_outcome": branch.first_outcome,
        "utility": branch.utility,
        "goal_reached": branch.goal_reached,
        "interactions_used": branch.interactions_used,
        "terminal_reason": branch.terminal_reason,
        "final_state": branch.final_state,
        "path": list(branch.path),
    }


def run_instrumented_episode(
    domain: G1DomainInstance,
    policy: OverrideGatePolicy,
    episode_index: int,
    *,
    interaction_budget: Optional[int] = None,
    config_document: Optional[Mapping[str, Any]] = None,
) -> InstrumentedEpisodeResult:
    """Run one parent episode and branch every common-guard disagreement.

    This function has no artifact writer and no matrix loop.  The later
    bounded runner is responsible for process timeouts and persistence.
    """
    budget = (
        int(interaction_budget)
        if interaction_budget is not None
        else 4 * domain.actual_node_count
    )
    if budget <= 0:
        raise ValueError("interaction_budget must be positive")
    adapter = CalibrationEFullAdapter(
        domain,
        policy,
        config_document=config_document,
    )
    executor = domain.executor(episode_index)
    episode = _EpisodeState(
        state=domain.start,
        path=[domain.start],
        visit_counts={domain.start: 1},
    )
    adapter.start_episode(episode_index, domain.start)
    disabled_policy = candidate_policy("gate_disabled")
    paired: List[PairedDecisionEvidence] = []
    terminal_reason = "interaction_budget_exhausted"

    while episode.interactions < budget and episode.state != domain.goal:
        actions = _local_actions(domain, episode.state)
        adapter_snapshot = _clone_adapter(adapter)
        executor_snapshot = copy.deepcopy(executor)
        episode_snapshot = episode.clone()
        state_hash = _state_hash(
            domain,
            adapter_snapshot,
            executor_snapshot,
            episode_index,
            episode_snapshot,
        )
        action = adapter.select_action(episode_index, episode.state, actions)
        record = adapter.decision_records[-1]
        if (
            not record.path_cap_hit
            and record.preferred_action is not None
            and record.greedy_action is not None
            and record.preferred_action != record.greedy_action
            and policy.max_path_imbalance is not None
            and record.path_imbalance <= float(policy.max_path_imbalance)
        ):
            greedy = _rollout_branch(
                domain,
                adapter_snapshot,
                executor_snapshot,
                episode_index,
                episode_snapshot,
                record.greedy_action,
                first_is_override=False,
                budget=budget,
                disabled_policy=disabled_policy,
            )
            lookahead = _rollout_branch(
                domain,
                adapter_snapshot,
                executor_snapshot,
                episode_index,
                episode_snapshot,
                record.preferred_action,
                first_is_override=True,
                budget=budget,
                disabled_policy=disabled_policy,
            )
            paired.append(
                PairedDecisionEvidence(
                    state_hash=state_hash,
                    random_stream_id=f"branch-{500000 + domain.generator_seed}",
                    domain_family=domain.family,
                    scale=domain.target_node_count,
                    generator_seed=domain.generator_seed,
                    episode_index=episode_index,
                    interaction_index=episode.interactions,
                    geometry=str(adapter.shared["path_geometry"]),
                    horizon=int(adapter.shared["path_horizon"]),
                    action_count=len(actions),
                    phase_regime=record.phase_regime,
                    support_margin=record.confidence,
                    path_imbalance=record.path_imbalance,
                    path_cap_hit=record.path_cap_hit,
                    greedy_action=record.greedy_action,
                    lookahead_action=record.preferred_action,
                    greedy=greedy,
                    lookahead=lookahead,
                )
            )
        if action is None:
            terminal_reason = "path_cap_hit" if record.path_cap_hit else "no_action"
            break
        _apply_action(
            domain,
            adapter,
            executor,
            episode_index,
            episode,
            action,
        )

    summary = _finish_summary(
        domain,
        episode_index,
        episode,
        budget,
        terminal_reason,
    )
    adapter.end_episode(summary)
    return InstrumentedEpisodeResult(
        summary=summary,
        policy_id=policy.policy_id,
        decision_records=tuple(adapter._episode_records),
        paired_decisions=tuple(paired),
        path_cap_hits=sum(record.path_cap_hit for record in adapter._episode_records),
    )
