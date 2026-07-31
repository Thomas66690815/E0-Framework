"""Load and validate the frozen override-gate calibration instance.

This module is deliberately non-executing.  It validates preregistration
boundaries without importing or calling a domain generator.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence

INSTANCE_ID = "E0-OVERRIDE-GATE-CAL-INSTANCE-v1"
PROTOCOL_ID = "E0-OVERRIDE-GATE-CAL-v1"
INSTANCE_PATH = (
    Path(__file__).resolve().parent.parent
    / "docs"
    / "E0_OVERRIDE_GATE_CALIBRATION_INSTANCE_v1.json"
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
EXPECTED_CANONICAL_SHA256 = (
    "0ec61ef75d1a80966518a050351b1e5933e9ef0221ab9be4352815722072d597"
)


def load_calibration_instance(path: Path = INSTANCE_PATH) -> Dict[str, Any]:
    """Read and validate the frozen instance without constructing domains."""
    with path.open(encoding="utf-8") as handle:
        document = json.load(handle)
    validate_calibration_instance(document)
    return document


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


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
        seeds = set(_seed_tuple(manifests[name]))
        _require(not seen.intersection(seeds), f"Split {name} overlaps an earlier split")
        seen.update(seeds)
    g1_holdout = _inclusive_seed_set(
        g1_protocol["splits"]["holdout"]["generator_seeds"]
    )
    fresh = set()
    for name in ("calibration", "verification", "protected_holdout"):
        fresh.update(_seed_tuple(manifests[name]))
    _require(not fresh.intersection(g1_holdout), "Fresh seeds overlap G1-v1 holdout")


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
    family_scale_cells = len(EXPECTED_FAMILIES) * len(EXPECTED_SCALES)
    calibration_seeds = len(
        instance["split_manifests"]["calibration"]["generator_seeds"]
    )
    verification_seeds = len(
        instance["split_manifests"]["verification"]["generator_seeds"]
    )
    holdout_seeds = len(
        instance["split_manifests"]["protected_holdout"]["generator_seeds"]
    )
    candidate_count = len(instance["candidate_policies"])
    expected = {
        "domain_family_scale_cells": family_scale_cells,
        "calibration_replicates_per_candidate": family_scale_cells
        * calibration_seeds,
        "calibration_candidates_including_disabled": candidate_count,
        "calibration_closed_loop_replicates_total": family_scale_cells
        * calibration_seeds
        * candidate_count,
        "verification_replicates_selected_policy": family_scale_cells
        * verification_seeds,
        "protected_holdout_replicates_selected_policy": family_scale_cells
        * holdout_seeds,
    }
    _require(instance["planned_counts"] == expected, "Planned counts are inconsistent")


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


def validate_calibration_instance(
    instance: Mapping[str, Any],
    *,
    g1_protocol_path: Path = G1_PROTOCOL_PATH,
) -> None:
    """Reject semantic drift in the frozen, non-executed experiment instance."""
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
            "candidate_policies",
            "paired_decision_stage",
            "closed_loop_stage",
            "risk_budget",
            "minimum_activation_support",
            "statistics",
            "selection_rule",
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
    for flag in (
        "runtime_behavior_changed",
        "calibration_executed",
        "verification_executed",
        "protected_holdout_accessed",
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
    _validate_planned_counts(instance)

    risk = instance["risk_budget"]
    _require(
        0.0 < risk["harmful_override_rate_upper_confidence_bound_max"] < 1.0,
        "Harm budget must be a probability",
    )
    _require(
        0.0 < risk["severe_harmful_override_rate_upper_confidence_bound_max"] < 1.0,
        "Severe-harm budget must be a probability",
    )
    activation = instance["minimum_activation_support"]
    _require(activation["override_decisions_min"] > 0, "Override support must be positive")
    _require(
        activation["replicates_with_override_min"] > 0,
        "Replicate support must be positive",
    )
    _require(
        instance["statistics"]["optional_stopping"] is False,
        "Optional stopping is forbidden",
    )
    _require(
        instance["statistics"]["negative_seed_removal"] is False,
        "Negative-seed removal is forbidden",
    )
    _require(
        instance["selection_rule"]["no_eligible_candidate"] == "gate_disabled",
        "No-candidate fallback must be disabled",
    )
    _require(
        instance["verification_rule"]["retuning_forbidden"] is True,
        "Verification retuning must be forbidden",
    )
    _require(
        _canonical_sha256(instance) == EXPECTED_CANONICAL_SHA256,
        "Frozen instance digest changed; create a new versioned instance",
    )


def seeds_for_split(
    split: str,
    instance: Mapping[str, Any] | None = None,
) -> Sequence[int]:
    """Return a frozen seed tuple; this function never builds a domain."""
    document = load_calibration_instance() if instance is None else instance
    validate_calibration_instance(document)
    if split not in EXPECTED_SPLITS:
        raise ValueError(f"Unknown split: {split}")
    return _seed_tuple(document["split_manifests"][split])
