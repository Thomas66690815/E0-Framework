"""Contract tests for the frozen, non-executing gate calibration instance."""

from __future__ import annotations

import copy
import json

import pytest

from .override_gate_calibration import (
    EXPECTED_FAMILIES,
    EXPECTED_SCALES,
    EXPECTED_THRESHOLDS,
    load_calibration_instance,
    seeds_for_split,
    validate_calibration_instance,
)


@pytest.fixture
def instance():
    return load_calibration_instance()


def test_instance_is_frozen_but_not_executed(instance):
    assert instance["status"] == "frozen_not_executed"
    assert instance["runtime_behavior_changed"] is False
    assert instance["calibration_executed"] is False
    assert instance["verification_executed"] is False
    assert instance["protected_holdout_accessed"] is False
    assert instance["not_gate_result"] is True


def test_scope_is_narrow_and_nonportable(instance):
    assert instance["scope"]["treatment"].startswith("E_FULL_GEOMETRY")
    assert instance["scope"]["control"].startswith("E_FULL_GEOMETRY")
    assert instance["scope"]["portable"] is False
    assert "a universal E0 confidence threshold" in instance["scope"]["out_of_scope"]


def test_domain_population_is_exact(instance):
    domain = instance["domain_manifest"]
    assert tuple(domain["families"]) == EXPECTED_FAMILIES
    assert tuple(domain["scales"]) == EXPECTED_SCALES
    assert domain["g1_v1_split_validator_reused"] is False


def test_fresh_splits_are_mutually_disjoint(instance):
    calibration = set(seeds_for_split("calibration", instance))
    verification = set(seeds_for_split("verification", instance))
    holdout = set(seeds_for_split("protected_holdout", instance))
    assert calibration.isdisjoint(verification)
    assert calibration.isdisjoint(holdout)
    assert verification.isdisjoint(holdout)


def test_fresh_splits_do_not_touch_g1_v1_holdout(instance):
    fresh = set()
    for split in ("calibration", "verification", "protected_holdout"):
        fresh.update(seeds_for_split(split, instance))
    assert fresh.isdisjoint(range(1000, 1030))


def test_split_sizes_are_frozen(instance):
    assert len(seeds_for_split("calibration", instance)) == 20
    assert len(seeds_for_split("verification", instance)) == 30
    assert len(seeds_for_split("protected_holdout", instance)) == 30


def test_candidate_grid_is_exact(instance):
    thresholds = tuple(
        candidate["min_support_margin"]
        for candidate in instance["candidate_policies"]
    )
    assert thresholds == EXPECTED_THRESHOLDS


def test_disabled_is_control_and_fallback(instance):
    assert instance["candidate_policies"][0] == {
        "policy_id": "gate_disabled",
        "mode": "disabled",
        "min_support_margin": None,
    }
    assert instance["selection_rule"]["no_eligible_candidate"] == "gate_disabled"


def test_common_gate_guards_are_frozen(instance):
    guards = instance["candidate_common_guards"]
    assert guards == {
        "disagreement_required": True,
        "max_path_imbalance": 3.0,
        "forbid_path_cap_hit": True,
        "missing_or_nonfinite_measurement": "fail_closed",
    }


def test_planned_counts_are_exact(instance):
    assert instance["planned_counts"] == {
        "domain_family_scale_cells": 12,
        "calibration_replicates_per_candidate": 240,
        "calibration_candidates_including_disabled": 12,
        "calibration_closed_loop_replicates_total": 2880,
        "verification_replicates_selected_policy": 360,
        "protected_holdout_replicates_selected_policy": 360,
    }


def test_statistics_forbid_optional_stopping_and_seed_removal(instance):
    statistics = instance["statistics"]
    assert statistics["bootstrap_resamples"] == 20000
    assert statistics["optional_stopping"] is False
    assert statistics["negative_seed_removal"] is False
    assert "Holm-Bonferroni" in statistics["multiplicity"]


def test_risk_and_activation_are_numeric_and_positive(instance):
    risk = instance["risk_budget"]
    activation = instance["minimum_activation_support"]
    assert risk["harmful_override_rate_upper_confidence_bound_max"] == 0.10
    assert risk["severe_harmful_override_rate_upper_confidence_bound_max"] == 0.02
    assert activation["override_decisions_min"] == 200
    assert activation["replicates_with_override_min"] == 24


def test_verification_cannot_retune(instance):
    rule = instance["verification_rule"]
    assert rule["policy_frozen_before_access"] is True
    assert rule["retuning_forbidden"] is True
    assert "do not open protected_holdout" in rule["failure_action"]


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda doc: doc.update(status="executed"), "not frozen"),
        (lambda doc: doc.update(calibration_executed=True), "must be false"),
        (
            lambda doc: doc["split_manifests"]["verification"][
                "generator_seeds"
            ].__setitem__(0, 2000),
            "overlaps",
        ),
        (
            lambda doc: doc["split_manifests"]["calibration"][
                "generator_seeds"
            ].__setitem__(0, 1000),
            "G1-v1 holdout",
        ),
        (
            lambda doc: doc["candidate_policies"].pop(),
            "Candidate count changed",
        ),
        (
            lambda doc: doc["risk_budget"].update(
                harmful_override_rate_upper_confidence_bound_max=0.20
            ),
            "digest changed",
        ),
        (
            lambda doc: doc["domain_manifest"].update(
                g1_v1_split_validator_reused=True
            ),
            "must not be weakened",
        ),
        (
            lambda doc: doc["selection_rule"].update(
                no_eligible_candidate="margin_000"
            ),
            "fallback must be disabled",
        ),
    ],
)
def test_validator_rejects_semantic_drift(instance, mutation, message):
    changed = copy.deepcopy(instance)
    mutation(changed)
    with pytest.raises(ValueError, match=message):
        validate_calibration_instance(changed)


def test_instance_round_trips_as_json(instance):
    assert json.loads(json.dumps(instance)) == instance


def test_unknown_split_is_rejected(instance):
    with pytest.raises(ValueError, match="Unknown split"):
        seeds_for_split("future", instance)
