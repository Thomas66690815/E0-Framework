"""Load and validate the frozen, non-executing override-gate v2 instance."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence

INSTANCE_ID = "E0-OVERRIDE-GATE-CAL-INSTANCE-v2"
PROTOCOL_ID = "E0-OVERRIDE-GATE-CAL-v2"
SOURCE_COMMIT = "91c1f63cbfda3891be851acafa3beee3b6f9baa7"
INSTANCE_PATH = (
    Path(__file__).resolve().parent.parent
    / "docs"
    / "E0_OVERRIDE_GATE_CALIBRATION_INSTANCE_v2.json"
)
G1_PROTOCOL_PATH = (
    Path(__file__).resolve().parent.parent / "docs" / "E0_G1_PROTOCOL_v1.json"
)
EXPECTED_SPLITS = ("exploration", "calibration", "verification", "protected_holdout")
EXPECTED_FAMILIES = (
    "wall_grid",
    "trap_grid_v2",
    "decoy_dag",
    "nonstationary_parallel",
)
EXPECTED_SCALES = (100, 500, 1000)
EXPECTED_THRESHOLDS = (
    None,
    0.0,
    0.05,
    0.1,
    0.15,
    0.2,
    0.25,
    0.3,
    0.35,
    0.4,
    0.5,
    0.85,
)
EXPECTED_SEEDS = {
    "exploration": tuple(range(0, 10)),
    "calibration": tuple(range(5000, 5020)),
    "verification": tuple(range(6000, 6030)),
    "protected_holdout": tuple(range(7000, 7030)),
}
EXPECTED_SAMPLE_PRIORITY_FIELDS = (
    "instance_id",
    "policy_id",
    "domain_family",
    "scale",
    "generator_seed",
    "episode_index",
    "interaction_index",
    "state",
    "greedy_action",
    "preferred_action",
)
EXPECTED_CANONICAL_SHA256 = (
    "0210d41d5e76c7c6fd8be8da79040a3e99f55906d62393007356d8aa86678692"
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _require_keys(record: Mapping[str, Any], keys: Iterable[str], label: str) -> None:
    missing = set(keys).difference(record)
    _require(not missing, f"{label} missing keys: {sorted(missing)}")


def _canonical_sha256(instance: Mapping[str, Any]) -> str:
    payload = json.dumps(
        instance,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def instance_sha256(instance: Mapping[str, Any] | None = None) -> str:
    """Return the canonical digest of the exact v2 instance."""
    document = load_calibration_instance_v2() if instance is None else instance
    return _canonical_sha256(document)


def _seed_tuple(split: Mapping[str, Any]) -> tuple[int, ...]:
    seeds = split.get("generator_seeds")
    _require(isinstance(seeds, list) and bool(seeds), "Every split needs seeds")
    _require(
        all(isinstance(seed, int) and not isinstance(seed, bool) for seed in seeds),
        "Seeds must be integers",
    )
    result = tuple(seeds)
    _require(len(result) == len(set(result)), "Seeds must be unique within a split")
    _require(tuple(sorted(result)) == result, "Seeds must be sorted")
    return result


def _inclusive_seed_set(specification: Mapping[str, Any]) -> set[int]:
    return set(
        range(
            int(specification["start"]),
            int(specification["stop_inclusive"]) + 1,
        )
    )


def _validate_seed_boundaries(
    instance: Mapping[str, Any],
    g1_protocol: Mapping[str, Any],
) -> None:
    manifests = instance["split_manifests"]
    _require(tuple(manifests) == EXPECTED_SPLITS, "Unexpected split order or names")
    seen: set[int] = set()
    for name in EXPECTED_SPLITS:
        seeds = _seed_tuple(manifests[name])
        _require(seeds == EXPECTED_SEEDS[name], f"{name} seed manifest changed")
        _require(not seen.intersection(seeds), f"Split {name} overlaps an earlier split")
        seen.update(seeds)

    fresh = set().union(
        *(set(EXPECTED_SEEDS[name]) for name in EXPECTED_SPLITS[1:])
    )
    g1_holdout = _inclusive_seed_set(
        g1_protocol["splits"]["holdout"]["generator_seeds"]
    )
    _require(not fresh.intersection(g1_holdout), "Fresh seeds overlap G1-v1 holdout")

    excluded = instance["excluded_seed_ranges"]
    expected_excluded = {
        "g1_v1_holdout": [1000, 1029],
        "observed_v1_calibration": [2000, 2019],
        "reserved_unopened_v1_verification": [3000, 3029],
        "reserved_unopened_v1_holdout": [4000, 4029],
    }
    _require(excluded == expected_excluded, "Excluded seed ranges changed")
    for start, stop in excluded.values():
        _require(
            not fresh.intersection(range(start, stop + 1)),
            "Fresh seeds overlap an excluded earlier range",
        )


def _validate_candidates(instance: Mapping[str, Any]) -> None:
    candidates = instance["candidate_policies"]
    _require(len(candidates) == len(EXPECTED_THRESHOLDS), "Candidate count changed")
    ids = [candidate["policy_id"] for candidate in candidates]
    _require(len(ids) == len(set(ids)), "Candidate policy IDs must be unique")
    thresholds = tuple(candidate["min_support_margin"] for candidate in candidates)
    _require(thresholds == EXPECTED_THRESHOLDS, "Candidate threshold grid changed")
    _require(candidates[0]["mode"] == "disabled", "First candidate must be disabled")
    _require(
        all(candidate["mode"] == "fixed" for candidate in candidates[1:]),
        "Non-control candidates must be fixed policies",
    )


def _validate_planned_counts(instance: Mapping[str, Any]) -> None:
    cells = len(EXPECTED_FAMILIES) * len(EXPECTED_SCALES)
    calibration_replicates = cells * len(EXPECTED_SEEDS["calibration"])
    verification_replicates = cells * len(EXPECTED_SEEDS["verification"])
    holdout_replicates = cells * len(EXPECTED_SEEDS["protected_holdout"])
    candidates = len(EXPECTED_THRESHOLDS)
    active_candidates = candidates - 1
    sample_cap = int(
        instance["stage_a_paired_evidence"]["sample_cap_per_candidate_replicate"]
    )
    expected = {
        "domain_family_scale_cells": cells,
        "calibration_replicates_per_candidate": calibration_replicates,
        "calibration_candidates_including_disabled": candidates,
        "calibration_stage_b_replicates_total": calibration_replicates * candidates,
        "calibration_stage_a_active_candidates": active_candidates,
        "calibration_stage_a_sampled_pairs_max": (
            calibration_replicates * active_candidates * sample_cap
        ),
        "verification_stage_b_replicates_selected_policy": verification_replicates,
        "verification_stage_a_sampled_pairs_max": (
            verification_replicates * sample_cap
        ),
        "protected_holdout_stage_b_replicates_selected_policy": holdout_replicates,
        "protected_holdout_stage_a_sampled_pairs_max": (
            holdout_replicates * sample_cap
        ),
    }
    _require(instance["planned_counts"] == expected, "Planned counts are inconsistent")


def _validate_stage_separation(instance: Mapping[str, Any]) -> None:
    stage_b = instance["stage_b_closed_loop"]
    _require(stage_b["runs_before_stage_a"] is True, "Stage B must run first")
    _require(stage_b["paired_branch_collection"] is False, "Stage B must be branch-free")
    _require(
        stage_b["snapshot_cloning_for_branch_evidence"] is False,
        "Stage B must not clone branch snapshots",
    )
    _require(
        tuple(stage_b["required_decision_counts"])
        == (
            "observed_disagreement_count",
            "guard_eligible_disagreement_count",
            "executed_override_count",
        ),
        "Stage-B disagreement funnel changed",
    )

    stage_a = instance["stage_a_paired_evidence"]
    _require(
        stage_a["sample_cap_per_candidate_replicate"] == 4,
        "Stage-A sample cap changed",
    )
    _require(
        tuple(stage_a["sample_priority_fields"])
        == EXPECTED_SAMPLE_PRIORITY_FIELDS,
        "Stage-A sample priority changed",
    )
    _require(
        stage_a["outcome_fields_in_sample_priority"] is False,
        "Outcome-dependent sampling is forbidden",
    )
    _require(
        stage_a["manual_sampling_permitted"] is False,
        "Manual sampling is forbidden",
    )
    _require(
        stage_a["parent_replay_trace_digest_must_match_stage_b"] is True,
        "Stage-A replay must match Stage B",
    )
    _require(
        stage_a["parent_replay_time_is_parent_performance"] is False,
        "Stage-A replay time cannot be parent performance",
    )
    _require(
        stage_a["stage_a_unresolved_is_parent_algorithm_timeout"] is False,
        "Stage-A unresolved work cannot relabel the parent",
    )
    _require(
        stage_a["stage_a_unresolved_candidate_action"] == "ineligible",
        "Unresolved Stage-A evidence must fail closed",
    )

    timeouts = instance["timeouts"]
    expected_timeouts = {
        "stage_b_episode_seconds": 60,
        "stage_b_replicate_seconds": 1800,
        "stage_a_parent_replay_episode_seconds": 60,
        "stage_a_individual_branch_seconds": 60,
        "stage_a_branch_pair_process_seconds": 150,
        "stage_a_cell_seconds": 3600,
        "infrastructure_retry": "Whole cell, identical inputs, immutable attempt artifacts, highest attempt only, no fallback to earlier attempts.",
        "branch_time_charged_to_parent": False,
    }
    _require(timeouts == expected_timeouts, "Timeout semantics changed")


def _validate_statistics_and_selection(instance: Mapping[str, Any]) -> None:
    risk = instance["risk_budget"]
    expected_risk = {
        "stage_a_harmful_override_rate_upper_confidence_bound_max": 0.10,
        "stage_a_severe_harmful_override_count_max": 0,
        "stage_a_unresolved_count_max": 0,
        "stage_b_family_primary_effect_lower_confidence_bound_min": -0.02,
        "stage_b_overall_primary_effect_lower_confidence_bound_min_exclusive": 0.0,
        "stage_b_algorithm_timeout_rate_max": 0.0,
        "stage_b_path_cap_rate_max": 0.0,
        "infrastructure_invalid_cell_fraction_max": 0.0,
    }
    _require(risk == expected_risk, "Risk budget changed")

    support = instance["minimum_activation_support"]
    _require(support["stage_b_override_decisions_min"] == 200, "Stage-B support changed")
    _require(
        support["stage_b_replicates_with_override_min"] == 24,
        "Stage-B replicate support changed",
    )
    _require(
        support["stage_a_sampled_override_decisions_min"] == 400,
        "Stage-A decision support changed",
    )
    _require(
        support["stage_a_replicates_with_sample_min"] == 120,
        "Stage-A replicate support changed",
    )

    statistics = instance["statistics"]
    _require(statistics["bootstrap_resamples"] == 20000, "Bootstrap count changed")
    _require(statistics["optional_stopping"] is False, "Optional stopping is forbidden")
    _require(
        statistics["negative_seed_removal"] is False,
        "Negative-seed removal is forbidden",
    )
    _require(
        statistics["post_authorization_candidate_removal"] is False,
        "Candidate removal after authorization is forbidden",
    )
    _require(
        "Holm-Bonferroni" in statistics["multiplicity"],
        "Multiplicity method changed",
    )

    selection = instance["selection_rule"]
    _require(
        selection["no_eligible_candidate"] == "gate_disabled",
        "No-candidate fallback must be disabled",
    )
    _require(selection["practical_tie_band"] == 0.005, "Tie band changed")
    _require(
        instance["verification_rule"]["retuning_forbidden"] is True,
        "Verification retuning must be forbidden",
    )


def validate_calibration_instance_v2(
    instance: Mapping[str, Any],
    *,
    g1_protocol_path: Path = G1_PROTOCOL_PATH,
) -> None:
    """Reject semantic drift without constructing any fresh-split domain."""
    _require_keys(
        instance,
        (
            "instance_id",
            "protocol_id",
            "status",
            "source_commit",
            "scope",
            "domain_manifest",
            "split_manifests",
            "excluded_seed_ranges",
            "candidate_policies",
            "stage_b_closed_loop",
            "stage_a_paired_evidence",
            "timeouts",
            "risk_budget",
            "minimum_activation_support",
            "statistics",
            "selection_rule",
            "missingness_and_retry",
            "verification_rule",
            "planned_counts",
        ),
        "instance",
    )
    _require(instance["instance_id"] == INSTANCE_ID, "Wrong instance ID")
    _require(instance["protocol_id"] == PROTOCOL_ID, "Wrong protocol ID")
    _require(instance["status"] == "frozen_not_executed", "Instance is not frozen")
    _require(
        bool(re.fullmatch(r"[0-9a-f]{40}", str(instance["source_commit"]))),
        "source_commit must be a full SHA-1",
    )
    _require(instance["source_commit"] == SOURCE_COMMIT, "Source commit changed")
    for flag in (
        "runtime_behavior_changed",
        "calibration_executed",
        "verification_executed",
        "protected_holdout_accessed",
        "holdout_accessed",
    ):
        _require(instance.get(flag) is False, f"{flag} must be false")
    _require(instance.get("not_gate_result") is True, "not_gate_result must be true")

    domain = instance["domain_manifest"]
    _require(tuple(domain["families"]) == EXPECTED_FAMILIES, "Domain families changed")
    _require(tuple(domain["scales"]) == EXPECTED_SCALES, "Domain scales changed")
    _require(
        domain["g1_v1_split_validator_reused"] is False,
        "G1-v1 split validator must not be weakened or reused",
    )

    with g1_protocol_path.open(encoding="utf-8") as handle:
        g1_protocol = json.load(handle)
    _validate_seed_boundaries(instance, g1_protocol)
    _validate_candidates(instance)
    _validate_stage_separation(instance)
    _validate_statistics_and_selection(instance)
    _validate_planned_counts(instance)
    _require(
        _canonical_sha256(instance) == EXPECTED_CANONICAL_SHA256,
        "Frozen v2 instance digest changed; create a new versioned instance",
    )


def load_calibration_instance_v2(path: Path = INSTANCE_PATH) -> Dict[str, Any]:
    """Read and validate v2 without importing or calling a domain generator."""
    with path.open(encoding="utf-8") as handle:
        document = json.load(handle)
    validate_calibration_instance_v2(document)
    return document


def seeds_for_split_v2(
    split: str,
    instance: Mapping[str, Any] | None = None,
) -> Sequence[int]:
    """Return an immutable manifest tuple; never construct a domain."""
    document = load_calibration_instance_v2() if instance is None else instance
    validate_calibration_instance_v2(document)
    if split not in EXPECTED_SPLITS:
        raise ValueError(f"Unknown split: {split}")
    return _seed_tuple(document["split_manifests"][split])
