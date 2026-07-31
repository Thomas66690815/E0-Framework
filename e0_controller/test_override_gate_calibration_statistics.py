"""Synthetic-only tests for frozen calibration statistics and selection."""

from __future__ import annotations

import copy

import pytest

from .override_gate_calibration import load_calibration_instance
from .override_gate_calibration_statistics import (
    select_calibration_policy,
    validate_calibration_records,
)


def _synthetic_records(*, beneficial_policy: str | None = "margin_020"):
    instance = load_calibration_instance()
    records = []
    for family in instance["domain_manifest"]["families"]:
        for scale in instance["domain_manifest"]["scales"]:
            for seed in instance["split_manifests"]["calibration"]["generator_seeds"]:
                for candidate in instance["candidate_policies"]:
                    policy_id = candidate["policy_id"]
                    beneficial = policy_id == beneficial_policy
                    records.append(
                        {
                            "split": "calibration",
                            "holdout_accessed": False,
                            "not_gate_result": True,
                            "policy_id": policy_id,
                            "domain_family": family,
                            "scale": scale,
                            "generator_seed": seed,
                            "primary_utility": 0.60 if beneficial else 0.50,
                            "override_count": 1 if beneficial else 0,
                            "eligible_disagreement_count": 10,
                            "harmful_overrides": 0,
                            "severe_harmful_overrides": 0,
                            "path_cap_hits": 0,
                            "infrastructure_failure": False,
                        }
                    )
    return records


def test_exact_complete_synthetic_matrix_is_valid():
    records = _synthetic_records()
    validate_calibration_records(records)
    assert len(records) == 2880


@pytest.mark.parametrize(
    "mutation",
    [
        lambda records: records.pop(),
        lambda records: records[0].update(split="verification"),
        lambda records: records[0].update(holdout_accessed=True),
        lambda records: records[0].update(not_gate_result=False),
        lambda records: records[0].update(policy_id="margin_042"),
        lambda records: records[0].update(generator_seed=3000),
        lambda records: records[0].update(infrastructure_failure=True),
        lambda records: records[0].update(primary_utility=float("nan")),
        lambda records: records[0].update(primary_utility=1.01),
        lambda records: records[0].update(override_count=11),
        lambda records: records[0].update(harmful_overrides=2, override_count=1),
        lambda records: records[0].update(
            severe_harmful_overrides=2,
            harmful_overrides=1,
            override_count=2,
        ),
        lambda records: records.append(copy.deepcopy(records[0])),
    ],
)
def test_record_validation_rejects_incomplete_or_leaking_matrix(mutation):
    records = _synthetic_records()
    mutation(records)
    with pytest.raises(ValueError):
        validate_calibration_records(records)


def test_synthetic_beneficial_policy_passes_all_constraints():
    report = select_calibration_policy(
        _synthetic_records(),
        bootstrap_resamples=1999,
        test_only_resample_override=True,
    )
    assert report["holm_family_size"] == 77
    assert report["selected_policy_id"] == "margin_020"
    assert report["no_eligible_candidate"] is False
    selected = next(
        item
        for item in report["candidate_reports"]
        if item["policy_id"] == "margin_020"
    )
    assert selected["eligible"] is True
    assert selected["mean_primary_effect"] == pytest.approx(0.1)
    assert selected["override_count"] == 240
    assert selected["replicates_with_override"] == 240
    assert selected["harmful_override_rate"] == 0.0
    assert selected["severe_harmful_override_rate"] == 0.0
    assert all(selected["eligibility_checks"].values())
    assert all(item["holm_pass"] for item in selected["constraints"])


def test_no_effect_or_activation_falls_back_to_disabled():
    report = select_calibration_policy(
        _synthetic_records(beneficial_policy=None),
        bootstrap_resamples=99,
        test_only_resample_override=True,
    )
    assert report["selected_policy_id"] == "gate_disabled"
    assert report["no_eligible_candidate"] is True
    assert not any(item["eligible"] for item in report["candidate_reports"])


def test_path_cap_disqualifies_otherwise_beneficial_policy():
    records = _synthetic_records()
    for row in records:
        if row["policy_id"] == "margin_020":
            row["path_cap_hits"] = 1
    report = select_calibration_policy(
        records,
        bootstrap_resamples=1999,
        test_only_resample_override=True,
    )
    candidate = next(
        item
        for item in report["candidate_reports"]
        if item["policy_id"] == "margin_020"
    )
    assert candidate["eligibility_checks"]["path_cap_rate"] is False
    assert candidate["eligible"] is False
    assert report["selected_policy_id"] == "gate_disabled"


def test_harm_budget_disqualifies_otherwise_beneficial_policy():
    records = _synthetic_records()
    for row in records:
        if row["policy_id"] == "margin_020":
            row["harmful_overrides"] = 1
            row["severe_harmful_overrides"] = 1
    report = select_calibration_policy(
        records,
        bootstrap_resamples=1999,
        test_only_resample_override=True,
    )
    candidate = next(
        item
        for item in report["candidate_reports"]
        if item["policy_id"] == "margin_020"
    )
    assert candidate["harmful_override_rate"] == 1.0
    assert candidate["eligibility_checks"]["all_nominal_bounds"] is False
    assert candidate["eligible"] is False


def test_nonfrozen_resample_count_requires_explicit_test_marker():
    with pytest.raises(ValueError, match="test-only"):
        select_calibration_policy(
            _synthetic_records(),
            bootstrap_resamples=99,
        )


def test_statistics_are_deterministic():
    records = _synthetic_records()
    first = select_calibration_policy(
        records,
        bootstrap_resamples=1999,
        test_only_resample_override=True,
    )
    second = select_calibration_policy(
        records,
        bootstrap_resamples=1999,
        test_only_resample_override=True,
    )
    assert first == second


def test_frozen_default_resample_count_is_used():
    report = select_calibration_policy(_synthetic_records())
    assert report["bootstrap_resamples"] == 20000
    assert report["test_only_resample_override"] is False
