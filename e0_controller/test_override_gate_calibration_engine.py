"""WP-GATE-0.5 structural and synthetic tests; no calibration outcomes."""

from __future__ import annotations

import copy
from dataclasses import replace

import pytest

from .g1_ablations import load_ablation_configs
from .g1_baselines import _local_actions, run_episode
from .g1_domains import (
    BUILDERS,
    CALIBRATION_SEED_NAMESPACE,
    G1DomainInstance,
    HoldoutAccessError,
    build_domain,
    validate_domain,
)
from .landscape import Landscape
from .override_gate import OverrideGatePolicy
from .override_gate_calibration_engine import (
    CalibrationEFullAdapter,
    build_calibration_domain,
    calibration_domain_record,
    candidate_policy,
    run_instrumented_episode,
)


def _synthetic_domain() -> G1DomainInstance:
    landscape = Landscape()
    landscape.add_edge("S", "A", delta=0.1, resistance=1.0)
    landscape.add_edge("S", "B", delta=0.5, resistance=1.0)
    landscape.add_edge("A", "S", delta=3.0, resistance=1.0)
    landscape.add_edge("A", "G", delta=3.0, resistance=1.0)
    landscape.add_edge("B", "G", delta=0.01, resistance=1.0)
    return G1DomainInstance(
        family="synthetic_test_only",
        target_node_count=4,
        generator_seed=0,
        landscape=landscape,
        start="S",
        goal="G",
        oracle_cost_by_regime={"stationary": 2},
    )


def test_calibration_builder_accepts_only_frozen_population():
    domain = build_calibration_domain("wall_grid", 100, 2000)
    assert domain.generator_seed == 2000
    assert domain.seed_namespace == CALIBRATION_SEED_NAMESPACE
    assert domain.actual_node_count == 100
    assert all(item["passed"] for item in validate_domain(domain))
    assert domain.run_id.startswith("gate-cal-")


@pytest.mark.parametrize("family", tuple(BUILDERS))
@pytest.mark.parametrize("scale", (100, 500, 1000))
def test_calibration_domains_preserve_exact_n_and_invariants(family, scale):
    domain = build_calibration_domain(family, scale, 2001)
    assert domain.actual_node_count == scale
    assert all(item["passed"] for item in validate_domain(domain))


def test_calibration_generation_is_deterministic():
    first = build_calibration_domain("decoy_dag", 100, 2002)
    second = build_calibration_domain("decoy_dag", 100, 2002)
    assert first.topology_sha256() == second.topology_sha256()
    assert first.outcome_seed == second.outcome_seed == 202002
    assert first.policy_seed == second.policy_seed == 302002


def test_calibration_domain_record_cannot_be_mislabeled_as_g1_development():
    domain = build_calibration_domain("wall_grid", 100, 2000)
    with pytest.raises(RuntimeError, match="development-only"):
        domain.to_record()
    record = calibration_domain_record(domain)
    assert record["protocol_id"] == "E0-OVERRIDE-GATE-CAL-v1"
    assert record["split"] == "calibration"
    assert record["holdout_accessed"] is False
    assert record["not_gate_result"] is True
    assert record["domains_instantiated"] == 1
    assert record["outcomes_observed"] == 0


def test_calibration_domain_record_rejects_development_domain():
    with pytest.raises(ValueError, match="not in"):
        calibration_domain_record(build_domain("wall_grid", 100, 0))


@pytest.mark.parametrize("seed", (0, 9, 1000, 1029, 1999, 2020, 3000, 4000))
def test_calibration_builder_rejects_every_noncalibration_seed(seed):
    with pytest.raises((ValueError, HoldoutAccessError)):
        build_calibration_domain("wall_grid", 100, seed)


def test_g1_v1_public_builder_still_rejects_calibration_seed():
    with pytest.raises(ValueError, match="outside development"):
        build_domain("wall_grid", 100, 2000)


def test_protected_namespace_is_not_available():
    with pytest.raises(HoldoutAccessError, match="Unknown or protected"):
        BUILDERS["wall_grid"](100, 3000, seed_namespace="override_gate_verification")
    with pytest.raises(HoldoutAccessError, match="Unknown or protected"):
        BUILDERS["wall_grid"](100, 4000, seed_namespace="override_gate_holdout")


def test_namespace_changes_access_not_generator_semantics(monkeypatch):
    from . import override_gate_calibration

    monkeypatch.setattr(
        override_gate_calibration,
        "seeds_for_split",
        lambda split: (0,),
    )
    development = BUILDERS["wall_grid"](100, 0)
    calibration = BUILDERS["wall_grid"](
        100,
        0,
        seed_namespace=CALIBRATION_SEED_NAMESPACE,
    )
    assert development.topology_sha256() == calibration.topology_sha256()
    assert development.outcome_seed == calibration.outcome_seed


def test_all_frozen_candidate_policies_materialize_exactly():
    expected = {
        "gate_disabled": None,
        "margin_000": 0.0,
        "margin_005": 0.05,
        "margin_010": 0.1,
        "margin_015": 0.15,
        "margin_020": 0.2,
        "margin_025": 0.25,
        "margin_030": 0.3,
        "margin_035": 0.35,
        "margin_040": 0.4,
        "margin_050": 0.5,
        "margin_085": 0.85,
    }
    for policy_id, threshold in expected.items():
        policy = candidate_policy(policy_id)
        assert policy.policy_id == policy_id
        assert policy.min_support_margin == threshold
        assert policy.max_path_imbalance == 3.0
        assert policy.forbid_path_cap_hit is True
        assert policy.provenance["protected_holdout_accessed"] is False


def test_unknown_candidate_is_rejected():
    with pytest.raises(ValueError, match="Unknown frozen candidate"):
        candidate_policy("margin_042")


def test_adapter_is_e_full_geometry_only():
    domain = _synthetic_domain()
    adapter = CalibrationEFullAdapter(domain, candidate_policy("gate_disabled"))
    assert adapter.method_id == "E_FULL_GEOMETRY"
    assert adapter.override_gate_policy.policy_id == "gate_disabled"


def test_adapter_rejects_legacy_policy():
    with pytest.raises(ValueError, match="disabled or fixed"):
        CalibrationEFullAdapter(
            _synthetic_domain(),
            OverrideGatePolicy.legacy_g1_v1(),
        )


def test_adapter_rejects_modified_candidate():
    modified = replace(candidate_policy("margin_020"), min_support_margin=0.21)
    with pytest.raises(ValueError, match="exact frozen candidate"):
        CalibrationEFullAdapter(_synthetic_domain(), modified)


def test_disabled_and_zero_margin_change_only_gate_decision():
    domain = _synthetic_domain()
    actions = _local_actions(domain, "S")
    disabled = CalibrationEFullAdapter(domain, candidate_policy("gate_disabled"))
    zero = CalibrationEFullAdapter(domain, candidate_policy("margin_000"))
    disabled.start_episode(0, "S")
    zero.start_episode(0, "S")

    disabled_action = disabled.select_action(0, "S", actions)
    zero_action = zero.select_action(0, "S", actions)
    disabled_record = disabled.decision_records[-1]
    zero_record = zero.decision_records[-1]

    assert disabled_record.scores == zero_record.scores
    assert disabled_record.probabilities == zero_record.probabilities
    assert disabled_record.path_family_signature == zero_record.path_family_signature
    assert disabled_record.greedy_action == zero_record.greedy_action
    assert disabled_record.preferred_action == zero_record.preferred_action
    assert disabled_record.override is False
    assert zero_record.override is True
    assert disabled_action.target == disabled_record.greedy_action
    assert zero_action.target == zero_record.preferred_action


def test_instrumented_episode_records_paired_disagreement():
    result = run_instrumented_episode(
        _synthetic_domain(),
        candidate_policy("gate_disabled"),
        0,
        interaction_budget=8,
    )
    assert result.paired_decisions
    first = result.paired_decisions[0]
    assert first.greedy_action != first.lookahead_action
    assert len(first.state_hash) == 64
    assert first.random_stream_id == "branch-500000"
    assert first.parent_run_mutated is False
    assert first.delta_utility == (
        first.lookahead.utility - first.greedy.utility
    )
    assert first.to_record()["delta_utility"] == first.delta_utility


def test_branches_do_not_mutate_parent_episode():
    domain = _synthetic_domain()
    policy = candidate_policy("gate_disabled")
    instrumented = run_instrumented_episode(
        domain,
        policy,
        0,
        interaction_budget=8,
    )
    plain_adapter = CalibrationEFullAdapter(domain, policy)
    plain = run_episode(
        domain,
        plain_adapter,
        0,
        interaction_budget=8,
    )
    assert instrumented.summary == plain
    assert instrumented.decision_records == tuple(plain_adapter._episode_records)


def test_branch_evidence_is_deterministic():
    first = run_instrumented_episode(
        _synthetic_domain(),
        candidate_policy("margin_000"),
        0,
        interaction_budget=8,
    )
    second = run_instrumented_episode(
        _synthetic_domain(),
        candidate_policy("margin_000"),
        0,
        interaction_budget=8,
    )
    assert first.summary == second.summary
    assert first.paired_decisions == second.paired_decisions


def test_branch_rollouts_share_the_same_predecision_snapshot():
    result = run_instrumented_episode(
        _synthetic_domain(),
        candidate_policy("gate_disabled"),
        0,
        interaction_budget=8,
    )
    first = result.paired_decisions[0]
    assert first.greedy.interactions_used >= 1
    assert first.lookahead.interactions_used >= 1
    assert first.greedy.path[0] == first.lookahead.path[0] == "S"
    assert first.greedy.first_action == first.greedy_action
    assert first.lookahead.first_action == first.lookahead_action


def test_path_cap_fails_closed_and_emits_no_branch():
    config = copy.deepcopy(load_ablation_configs())
    config["shared"]["max_paths_per_decision"] = 1
    result = run_instrumented_episode(
        _synthetic_domain(),
        candidate_policy("margin_000"),
        0,
        interaction_budget=8,
        config_document=config,
    )
    assert result.path_cap_hits == 1
    assert result.summary.terminal_reason == "path_cap_hit"
    assert result.summary.success_adjusted_efficiency == 0.0
    assert result.paired_decisions == ()


def test_no_verification_or_holdout_builder_is_exported():
    from . import override_gate_calibration_engine as engine

    assert not hasattr(engine, "build_verification_domain")
    assert not hasattr(engine, "build_holdout_domain")
    assert not hasattr(engine, "main")
