"""Synthetic complete-matrix tests for frozen v2 joint statistics."""

from __future__ import annotations

import copy

import pytest

from .override_gate_calibration_v2 import load_calibration_instance_v2
from .override_gate_calibration_v2_statistics import (
    select_v2_calibration_policy,
    validate_stage_a_calibration_records,
    validate_stage_b_calibration_records,
)


def _complete_synthetic_records():
    instance = load_calibration_instance_v2()
    policies = [item["policy_id"] for item in instance["candidate_policies"]]
    active = policies[1:]
    families = instance["domain_manifest"]["families"]
    scales = instance["domain_manifest"]["scales"]
    seeds = instance["split_manifests"]["calibration"]["generator_seeds"]
    stage_b = []
    stage_a = []
    for policy_id in policies:
        for family in families:
            for scale in scales:
                for seed in seeds:
                    is_active = policy_id != "gate_disabled"
                    stage_b.append(
                        {
                            "split": "calibration",
                            "policy_id": policy_id,
                            "domain_family": family,
                            "scale": scale,
                            "generator_seed": seed,
                            "primary_utility": 0.6 if is_active else 0.5,
                            "observed_disagreement_count": 2 if is_active else 10,
                            "guard_eligible_disagreement_count": (
                                2 if is_active else 10
                            ),
                            "executed_override_count": 2 if is_active else 0,
                            "algorithm_timeout_count": 0,
                            "path_cap_count": 0,
                            "infrastructure_failure": False,
                            "holdout_accessed": False,
                            "not_gate_result": True,
                        }
                    )
                    if policy_id in active:
                        stage_a.append(
                            {
                                "split": "calibration",
                                "policy_id": policy_id,
                                "domain_family": family,
                                "scale": scale,
                                "generator_seed": seed,
                                "sampling_frame_override_count": 2,
                                "sample_count": 2,
                                "parent_replay_trace_match": True,
                                "paired_decisions": [
                                    {
                                        "sample_priority_sha256": f"{index:064x}",
                                        "status": "completed",
                                        "delta_utility": 0.1,
                                    }
                                    for index in (1, 2)
                                ],
                                "unresolved_count": 0,
                                "infrastructure_failure": False,
                                "holdout_accessed": False,
                                "not_gate_result": True,
                            }
                        )
    return stage_b, stage_a


@pytest.fixture(scope="module")
def synthetic_records():
    return _complete_synthetic_records()


def _find(records, policy_id):
    return next(record for record in records if record["policy_id"] == policy_id)


def test_v2_statistics_accept_complete_synthetic_stage_matrices(synthetic_records):
    stage_b, stage_a = synthetic_records
    validate_stage_b_calibration_records(stage_b)
    validate_stage_a_calibration_records(stage_a, stage_b_records=stage_b)
    assert len(stage_b) == 2880
    assert len(stage_a) == 2640


def test_v2_joint_selection_uses_conservative_tie_breaker(synthetic_records):
    stage_b, stage_a = synthetic_records
    report = select_v2_calibration_policy(
        stage_b,
        stage_a,
        bootstrap_resamples=2000,
        test_only_resample_override=True,
    )
    assert report["selected_policy_id"] == "margin_085"
    assert report["no_eligible_candidate"] is False
    assert report["holm_family_size"] == 66
    assert len(report["candidate_reports"]) == 11
    assert all(item["eligible"] for item in report["candidate_reports"])


def test_v2_severe_harm_fails_closed_before_optimization(synthetic_records):
    stage_b, original_stage_a = synthetic_records
    stage_a = copy.deepcopy(original_stage_a)
    record = _find(stage_a, "margin_085")
    record["paired_decisions"][0]["delta_utility"] = -0.2
    report = select_v2_calibration_policy(
        stage_b,
        stage_a,
        bootstrap_resamples=2000,
        test_only_resample_override=True,
    )
    margin_085 = _find(report["candidate_reports"], "margin_085")
    assert margin_085["stage_a_severe_harm_count"] == 1
    assert margin_085["eligibility_checks"]["stage_a_severe_harm"] is False
    assert margin_085["eligible"] is False
    assert report["selected_policy_id"] == "margin_050"


def test_v2_unresolved_branch_cannot_be_imputed(synthetic_records):
    stage_b, original_stage_a = synthetic_records
    stage_a = copy.deepcopy(original_stage_a)
    record = _find(stage_a, "margin_085")
    record["paired_decisions"][0].update(
        status="stage_a_unresolved",
        delta_utility=None,
    )
    record["unresolved_count"] = 1
    report = select_v2_calibration_policy(
        stage_b,
        stage_a,
        bootstrap_resamples=2000,
        test_only_resample_override=True,
    )
    margin_085 = _find(report["candidate_reports"], "margin_085")
    assert margin_085["stage_a_unresolved_count"] == 1
    assert margin_085["eligibility_checks"]["stage_a_unresolved"] is False
    assert report["selected_policy_id"] == "margin_050"


def test_v2_clean_parent_timeout_is_valid_but_ineligible(synthetic_records):
    original_stage_b, stage_a = synthetic_records
    stage_b = copy.deepcopy(original_stage_b)
    _find(stage_b, "margin_085")["algorithm_timeout_count"] = 1
    report = select_v2_calibration_policy(
        stage_b,
        stage_a,
        bootstrap_resamples=2000,
        test_only_resample_override=True,
    )
    margin_085 = _find(report["candidate_reports"], "margin_085")
    assert margin_085["stage_b_algorithm_timeout_rate"] > 0.0
    assert margin_085["eligibility_checks"]["stage_b_algorithm_timeout"] is False
    assert report["selected_policy_id"] == "margin_050"


def test_v2_statistics_reject_incomplete_stage_b_matrix(synthetic_records):
    stage_b, _ = synthetic_records
    with pytest.raises(ValueError, match="Expected 2880"):
        validate_stage_b_calibration_records(stage_b[:-1])


def test_v2_statistics_reject_disagreement_funnel_drift(synthetic_records):
    original_stage_b, _ = synthetic_records
    stage_b = copy.deepcopy(original_stage_b)
    stage_b[0]["guard_eligible_disagreement_count"] = 11
    with pytest.raises(ValueError, match="exceeds observed"):
        validate_stage_b_calibration_records(stage_b)


def test_v2_statistics_reject_stage_a_frame_or_cap_drift(synthetic_records):
    stage_b, original_stage_a = synthetic_records
    stage_a = copy.deepcopy(original_stage_a)
    stage_a[0]["sampling_frame_override_count"] = 3
    with pytest.raises(ValueError, match="differs from Stage-B"):
        validate_stage_a_calibration_records(stage_a, stage_b_records=stage_b)
    stage_a = copy.deepcopy(original_stage_a)
    stage_a[0]["sample_count"] = 3
    with pytest.raises(ValueError, match="frozen cap"):
        validate_stage_a_calibration_records(stage_a, stage_b_records=stage_b)


def test_v2_nonfrozen_bootstrap_count_is_test_only(synthetic_records):
    stage_b, stage_a = synthetic_records
    with pytest.raises(ValueError, match="test-only"):
        select_v2_calibration_policy(
            stage_b,
            stage_a,
            bootstrap_resamples=2000,
        )
