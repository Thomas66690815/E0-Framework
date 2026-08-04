"""Contract tests for frozen, non-executing override-gate v2."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from .override_gate_calibration_v2 import (
    EXPECTED_CANONICAL_SHA256,
    EXPECTED_FAMILIES,
    EXPECTED_SAMPLE_PRIORITY_FIELDS,
    EXPECTED_SCALES,
    EXPECTED_SEEDS,
    EXPECTED_THRESHOLDS,
    instance_sha256,
    load_calibration_instance_v2,
    seeds_for_split_v2,
    validate_calibration_instance_v2,
)


@pytest.fixture
def instance():
    return load_calibration_instance_v2()


def test_v2_instance_is_frozen_but_not_authorized_or_executed(instance):
    assert instance["status"] == "frozen_not_executed"
    assert instance["runtime_behavior_changed"] is False
    assert instance["calibration_executed"] is False
    assert instance["verification_executed"] is False
    assert instance["protected_holdout_accessed"] is False
    assert instance["holdout_accessed"] is False
    assert instance["not_gate_result"] is True


def test_v2_canonical_digest_is_frozen(instance):
    assert instance_sha256(instance) == EXPECTED_CANONICAL_SHA256
    assert len(EXPECTED_CANONICAL_SHA256) == 64


def test_v2_fresh_seed_manifests_are_exact_and_disjoint(instance):
    actual = {
        split: tuple(seeds_for_split_v2(split, instance))
        for split in EXPECTED_SEEDS
    }
    assert actual == EXPECTED_SEEDS
    fresh = [set(actual[name]) for name in tuple(EXPECTED_SEEDS)[1:]]
    assert fresh[0].isdisjoint(fresh[1])
    assert fresh[0].isdisjoint(fresh[2])
    assert fresh[1].isdisjoint(fresh[2])


def test_v2_fresh_seeds_avoid_every_earlier_reserved_range(instance):
    fresh = set().union(
        *(set(seeds_for_split_v2(name, instance)) for name in tuple(EXPECTED_SEEDS)[1:])
    )
    for start, stop in instance["excluded_seed_ranges"].values():
        assert fresh.isdisjoint(range(start, stop + 1))


def test_v2_domain_and_candidate_population_are_exact(instance):
    domain = instance["domain_manifest"]
    assert tuple(domain["families"]) == EXPECTED_FAMILIES
    assert tuple(domain["scales"]) == EXPECTED_SCALES
    thresholds = tuple(
        candidate["min_support_margin"]
        for candidate in instance["candidate_policies"]
    )
    assert thresholds == EXPECTED_THRESHOLDS


def test_v2_stage_b_is_branch_and_snapshot_free(instance):
    stage_b = instance["stage_b_closed_loop"]
    assert stage_b["runs_before_stage_a"] is True
    assert stage_b["paired_branch_collection"] is False
    assert stage_b["snapshot_cloning_for_branch_evidence"] is False
    assert stage_b["decision_trace_required"] is True


def test_v2_stage_a_sampling_is_bounded_deterministic_and_outcome_blind(instance):
    stage_a = instance["stage_a_paired_evidence"]
    assert stage_a["sample_cap_per_candidate_replicate"] == 4
    assert tuple(stage_a["sample_priority_fields"]) == EXPECTED_SAMPLE_PRIORITY_FIELDS
    assert stage_a["outcome_fields_in_sample_priority"] is False
    assert stage_a["manual_sampling_permitted"] is False
    assert stage_a["parent_replay_trace_digest_must_match_stage_b"] is True


def test_v2_timeout_namespaces_cannot_confound_parent_and_branch(instance):
    timeouts = instance["timeouts"]
    stage_a = instance["stage_a_paired_evidence"]
    assert timeouts["stage_b_episode_seconds"] == 60
    assert timeouts["stage_a_individual_branch_seconds"] == 60
    assert timeouts["stage_a_branch_pair_process_seconds"] == 150
    assert timeouts["branch_time_charged_to_parent"] is False
    assert stage_a["stage_a_unresolved_is_parent_algorithm_timeout"] is False
    assert stage_a["stage_a_unresolved_candidate_action"] == "ineligible"


def test_v2_support_and_risk_fail_closed(instance):
    support = instance["minimum_activation_support"]
    risk = instance["risk_budget"]
    assert support["stage_b_override_decisions_min"] == 200
    assert support["stage_a_sampled_override_decisions_min"] == 400
    assert support["stage_a_replicates_with_sample_min"] == 120
    assert risk["stage_a_severe_harmful_override_count_max"] == 0
    assert risk["stage_a_unresolved_count_max"] == 0
    assert risk["stage_b_algorithm_timeout_rate_max"] == 0.0
    assert instance["selection_rule"]["no_eligible_candidate"] == "gate_disabled"


def test_v2_planned_counts_are_derived_from_the_frozen_population(instance):
    assert instance["planned_counts"] == {
        "domain_family_scale_cells": 12,
        "calibration_replicates_per_candidate": 240,
        "calibration_candidates_including_disabled": 12,
        "calibration_stage_b_replicates_total": 2880,
        "calibration_stage_a_active_candidates": 11,
        "calibration_stage_a_sampled_pairs_max": 10560,
        "verification_stage_b_replicates_selected_policy": 360,
        "verification_stage_a_sampled_pairs_max": 1440,
        "protected_holdout_stage_b_replicates_selected_policy": 360,
        "protected_holdout_stage_a_sampled_pairs_max": 1440,
    }


def test_v2_protocol_is_inert_and_contains_no_authorization():
    path = (
        Path(__file__).resolve().parent.parent
        / "docs"
        / "E0_OVERRIDE_GATE_CALIBRATION_PROTOCOL_v2.json"
    )
    protocol = json.loads(path.read_text(encoding="utf-8"))
    assert protocol["status"] == (
        "frozen_design_authorization_validator_implemented_not_authorized"
    )
    assert protocol["authorization_record_present"] is False
    assert protocol["calibration_execution_authorized"] is False
    assert protocol["verification_execution_authorized"] is False
    assert protocol["protected_holdout_execution_authorized"] is False
    assert protocol["not_gate_result"] is True
    status = protocol["implementation_status"]
    assert status["immutable_instance_validator"] == "implemented"
    assert status["stage_a_sampler"] == "implemented_not_executed"
    assert status["stage_a_branch_runner"] == (
        "development_worker_implemented_production_not_implemented"
    )
    assert status["stage_b_runner"] == (
        "development_worker_implemented_production_not_implemented"
    )
    assert status["v2_statistics"] == "implemented_with_synthetic_records_only"
    assert status["v2_distributed_workflow"] == "planning_only"
    assert status["v2_authorization_gate"] == (
        "validator_implemented_no_operational_record"
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda doc: doc.update(status="executed"), "not frozen"),
        (lambda doc: doc.update(calibration_executed=True), "must be false"),
        (lambda doc: doc.update(source_commit="0" * 40), "Source commit changed"),
        (
            lambda doc: doc["split_manifests"]["calibration"][
                "generator_seeds"
            ].__setitem__(0, 2000),
            "calibration seed manifest changed",
        ),
        (
            lambda doc: doc["candidate_policies"].pop(),
            "Candidate count changed",
        ),
        (
            lambda doc: doc["stage_b_closed_loop"].update(
                paired_branch_collection=True
            ),
            "branch-free",
        ),
        (
            lambda doc: doc["stage_a_paired_evidence"].update(
                sample_cap_per_candidate_replicate=5
            ),
            "sample cap changed",
        ),
        (
            lambda doc: doc["stage_a_paired_evidence"].update(
                outcome_fields_in_sample_priority=True
            ),
            "Outcome-dependent",
        ),
        (
            lambda doc: doc["timeouts"].update(
                branch_time_charged_to_parent=True
            ),
            "Timeout semantics changed",
        ),
        (
            lambda doc: doc["risk_budget"].update(
                stage_a_unresolved_count_max=1
            ),
            "Risk budget changed",
        ),
        (
            lambda doc: doc["selection_rule"].update(
                no_eligible_candidate="margin_000"
            ),
            "fallback must be disabled",
        ),
    ],
)
def test_v2_validator_rejects_semantic_drift(instance, mutation, message):
    changed = copy.deepcopy(instance)
    mutation(changed)
    with pytest.raises(ValueError, match=message):
        validate_calibration_instance_v2(changed)


def test_v2_instance_round_trips_as_json(instance):
    assert json.loads(json.dumps(instance)) == instance


def test_v2_unknown_split_is_rejected(instance):
    with pytest.raises(ValueError, match="Unknown split"):
        seeds_for_split_v2("future", instance)


def test_v2_validator_exports_no_domain_builder():
    from . import override_gate_calibration_v2 as contract

    assert not hasattr(contract, "build_domain")
    assert not hasattr(contract, "build_calibration_domain")
    assert not hasattr(contract, "main")
