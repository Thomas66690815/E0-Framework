"""Frozen joint Stage-A/Stage-B statistics for override-gate v2."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from statistics import mean
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .override_gate_calibration_v2 import load_calibration_instance_v2

Unit = Tuple[str, int, int]
Stratum = Tuple[str, int]
PAIR_STATUSES = {"completed", "stage_a_unresolved"}


@dataclass(frozen=True)
class _BootstrapResult:
    overall: tuple[float, ...]
    families: Dict[str, tuple[float, ...]]
    harmful_rates: tuple[float, ...]


def _candidate_ids(instance: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(
        str(candidate["policy_id"])
        for candidate in instance["candidate_policies"]
        if candidate["policy_id"] != "gate_disabled"
    )


def _thresholds(instance: Mapping[str, Any]) -> Dict[str, float]:
    return {
        str(candidate["policy_id"]): float(candidate["min_support_margin"])
        for candidate in instance["candidate_policies"]
        if candidate["policy_id"] != "gate_disabled"
    }


def _unit(record: Mapping[str, Any]) -> Unit:
    return (
        str(record["domain_family"]),
        int(record["scale"]),
        int(record["generator_seed"]),
    )


def _finite_number(value: Any, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def _nonnegative_integer(value: Any, label: str) -> int:
    number = _finite_number(value, label)
    if number < 0.0 or int(number) != number:
        raise ValueError(f"{label} must be a nonnegative integer")
    return int(number)


def validate_stage_b_calibration_records(
    records: Sequence[Mapping[str, Any]],
    *,
    instance: Optional[Mapping[str, Any]] = None,
) -> None:
    """Require the exact complete 2,880-record Stage-B matrix."""
    document = load_calibration_instance_v2() if instance is None else instance
    expected_count = int(
        document["planned_counts"]["calibration_stage_b_replicates_total"]
    )
    if len(records) != expected_count:
        raise ValueError(f"Expected {expected_count} Stage-B records")
    policies = {
        str(candidate["policy_id"]) for candidate in document["candidate_policies"]
    }
    families = set(document["domain_manifest"]["families"])
    scales = {int(scale) for scale in document["domain_manifest"]["scales"]}
    seeds = set(document["split_manifests"]["calibration"]["generator_seeds"])
    identities = set()
    for record in records:
        if record.get("split") != "calibration":
            raise ValueError("Stage-B selection accepts calibration records only")
        if record.get("policy_id") not in policies:
            raise ValueError("Unknown Stage-B candidate")
        if record.get("domain_family") not in families:
            raise ValueError("Unknown Stage-B family")
        if int(record.get("scale", -1)) not in scales:
            raise ValueError("Unknown Stage-B scale")
        if int(record.get("generator_seed", -1)) not in seeds:
            raise ValueError("Unknown Stage-B calibration seed")
        if record.get("holdout_accessed") is not False:
            raise ValueError("Stage-B calibration claims holdout access")
        if record.get("not_gate_result") is not True:
            raise ValueError("Stage-B calibration must remain not_gate_result=true")
        if record.get("infrastructure_failure") is not False:
            raise ValueError("Infrastructure-invalid Stage-B cells must be rerun")
        utility = _finite_number(record.get("primary_utility"), "primary_utility")
        if not 0.0 <= utility <= 1.0:
            raise ValueError("Stage-B primary_utility must be in [0,1]")
        counts = {
            field: _nonnegative_integer(record.get(field), field)
            for field in (
                "observed_disagreement_count",
                "guard_eligible_disagreement_count",
                "executed_override_count",
                "algorithm_timeout_count",
                "path_cap_count",
            )
        }
        if counts["executed_override_count"] > counts[
            "guard_eligible_disagreement_count"
        ]:
            raise ValueError("Stage-B override count exceeds guard eligibility")
        if counts["guard_eligible_disagreement_count"] > counts[
            "observed_disagreement_count"
        ]:
            raise ValueError("Stage-B eligible count exceeds observed disagreements")
        identity = (str(record["policy_id"]), *_unit(record))
        if identity in identities:
            raise ValueError(f"Duplicate Stage-B record {identity}")
        identities.add(identity)
    expected_identities = {
        (policy_id, family, scale, seed)
        for policy_id in policies
        for family in families
        for scale in scales
        for seed in seeds
    }
    if identities != expected_identities:
        raise ValueError("Stage-B record identities are incomplete")


def validate_stage_a_calibration_records(
    records: Sequence[Mapping[str, Any]],
    *,
    stage_b_records: Sequence[Mapping[str, Any]],
    instance: Optional[Mapping[str, Any]] = None,
) -> None:
    """Require one bounded Stage-A replicate record per active Stage-B unit."""
    document = load_calibration_instance_v2() if instance is None else instance
    active = set(_candidate_ids(document))
    families = set(document["domain_manifest"]["families"])
    scales = {int(scale) for scale in document["domain_manifest"]["scales"]}
    seeds = set(document["split_manifests"]["calibration"]["generator_seeds"])
    expected_count = len(active) * len(families) * len(scales) * len(seeds)
    if len(records) != expected_count:
        raise ValueError(f"Expected {expected_count} Stage-A records")
    stage_b_by_identity = {
        (str(record["policy_id"]), *_unit(record)): record
        for record in stage_b_records
        if record["policy_id"] in active
    }
    identities = set()
    for record in records:
        if record.get("split") != "calibration":
            raise ValueError("Stage-A selection accepts calibration records only")
        policy_id = str(record.get("policy_id"))
        if policy_id not in active:
            raise ValueError("Stage-A record must use an active candidate")
        identity = (policy_id, *_unit(record))
        if identity not in stage_b_by_identity:
            raise ValueError("Stage-A record lacks its Stage-B parent")
        if identity in identities:
            raise ValueError(f"Duplicate Stage-A record {identity}")
        identities.add(identity)
        if record.get("holdout_accessed") is not False:
            raise ValueError("Stage-A calibration claims holdout access")
        if record.get("not_gate_result") is not True:
            raise ValueError("Stage-A calibration must remain not_gate_result=true")
        if record.get("infrastructure_failure") is not False:
            raise ValueError("Infrastructure-invalid Stage-A cells must be rerun")
        stage_b_parent = stage_b_by_identity[identity]
        skipped = record.get("stage_a_skipped_due_stage_b_valid_negative") is True
        if skipped:
            if int(stage_b_parent.get("algorithm_timeout_count", 0)) != 1:
                raise ValueError("Stage-A skip requires a Stage-B algorithm timeout")
            if record.get("parent_replay_trace_match") is not False:
                raise ValueError("Skipped Stage-A replay cannot claim a trace match")
            if any(
                record.get(field) not in (0, [], None)
                for field in (
                    "sampling_frame_override_count",
                    "sample_count",
                    "paired_decisions",
                    "unresolved_count",
                )
            ):
                raise ValueError("Skipped Stage-A record must contain no samples")
            continue
        if record.get("parent_replay_trace_match") is not True:
            raise ValueError("Stage-A replay must match its Stage-B parent")
        frame = _nonnegative_integer(
            record.get("sampling_frame_override_count"),
            "sampling_frame_override_count",
        )
        if frame != int(stage_b_parent["executed_override_count"]):
            raise ValueError("Stage-A sampling frame differs from Stage-B overrides")
        sample_count = _nonnegative_integer(record.get("sample_count"), "sample_count")
        expected_samples = min(frame, 4)
        if sample_count != expected_samples:
            raise ValueError("Stage-A sample count violates the frozen cap")
        pairs = record.get("paired_decisions")
        if not isinstance(pairs, list) or len(pairs) != sample_count:
            raise ValueError("Stage-A paired decision count is inconsistent")
        priorities = []
        unresolved = 0
        for pair in pairs:
            priority = str(pair.get("sample_priority_sha256"))
            if len(priority) != 64 or any(ch not in "0123456789abcdef" for ch in priority):
                raise ValueError("Stage-A sample priority must be SHA-256")
            priorities.append(priority)
            status = pair.get("status")
            if status not in PAIR_STATUSES:
                raise ValueError("Unknown Stage-A pair status")
            if status == "completed":
                delta = _finite_number(pair.get("delta_utility"), "delta_utility")
                if not -1.0 <= delta <= 1.0:
                    raise ValueError("Stage-A delta_utility must be in [-1,1]")
            else:
                unresolved += 1
                if pair.get("delta_utility") is not None:
                    raise ValueError("Unresolved Stage-A pair cannot have utility")
        if priorities != sorted(priorities) or len(priorities) != len(set(priorities)):
            raise ValueError("Stage-A priorities must be unique and sorted")
        if _nonnegative_integer(record.get("unresolved_count"), "unresolved_count") != unresolved:
            raise ValueError("Stage-A unresolved count is inconsistent")
    if len(identities) != expected_count:
        raise ValueError("Stage-A record identities are incomplete")


def _paired_rows(
    stage_b_records: Sequence[Mapping[str, Any]],
    stage_a_records: Sequence[Mapping[str, Any]],
    policy_id: str,
) -> List[Dict[str, Any]]:
    controls = {
        _unit(record): record
        for record in stage_b_records
        if record["policy_id"] == "gate_disabled"
    }
    stage_a = {
        _unit(record): record
        for record in stage_a_records
        if record["policy_id"] == policy_id
    }
    rows = []
    for record in stage_b_records:
        if record["policy_id"] != policy_id:
            continue
        unit = _unit(record)
        if unit not in controls or unit not in stage_a:
            raise ValueError(f"Candidate unit lacks paired control or Stage A: {unit}")
        pair_record = stage_a[unit]
        completed_deltas = [
            float(pair["delta_utility"])
            for pair in pair_record["paired_decisions"]
            if pair["status"] == "completed"
        ]
        rows.append(
            {
                "family": unit[0],
                "scale": unit[1],
                "seed": unit[2],
                "effect": float(record["primary_utility"])
                - float(controls[unit]["primary_utility"]),
                "observed": int(record["observed_disagreement_count"]),
                "eligible": int(record["guard_eligible_disagreement_count"]),
                "overrides": int(record["executed_override_count"]),
                "algorithm_timeout": int(record["algorithm_timeout_count"]) > 0,
                "path_cap": int(record["path_cap_count"]) > 0,
                "sample_count": int(pair_record["sample_count"]),
                "unresolved": int(pair_record["unresolved_count"]),
                "harmful": sum(delta < -0.01 for delta in completed_deltas),
                "severe": sum(delta <= -0.10 for delta in completed_deltas),
            }
        )
    return rows


def _cell_weighted_effect(rows: Sequence[Mapping[str, Any]]) -> float:
    cells: Dict[Stratum, List[float]] = {}
    for row in rows:
        cells.setdefault((str(row["family"]), int(row["scale"])), []).append(
            float(row["effect"])
        )
    return mean(mean(values) for values in cells.values())


def _family_effects(rows: Sequence[Mapping[str, Any]]) -> Dict[str, float]:
    return {
        family: _cell_weighted_effect(
            [row for row in rows if str(row["family"]) == family]
        )
        for family in sorted({str(row["family"]) for row in rows})
    }


def _harm_rate(rows: Sequence[Mapping[str, Any]]) -> float:
    completed = sum(int(row["sample_count"]) - int(row["unresolved"]) for row in rows)
    if completed == 0:
        return 1.0
    return sum(int(row["harmful"]) for row in rows) / completed


def _bootstrap(
    rows: Sequence[Mapping[str, Any]],
    *,
    resamples: int,
    seed: int,
) -> _BootstrapResult:
    if resamples <= 0:
        raise ValueError("Bootstrap resamples must be positive")
    strata: Dict[Stratum, List[Mapping[str, Any]]] = {}
    for row in rows:
        strata.setdefault((str(row["family"]), int(row["scale"])), []).append(row)
    signature = ("effect", "sample_count", "unresolved", "harmful")
    constant = all(
        len({tuple(row[field] for field in signature) for row in values}) == 1
        for values in strata.values()
    )
    if constant:
        overall = _cell_weighted_effect(rows)
        families = _family_effects(rows)
        harmful = _harm_rate(rows)
        return _BootstrapResult(
            overall=(overall,) * resamples,
            families={key: (value,) * resamples for key, value in families.items()},
            harmful_rates=(harmful,) * resamples,
        )
    rng = random.Random(seed)
    overall_samples: List[float] = []
    family_samples: Dict[str, List[float]] = {
        family: [] for family in sorted({key[0] for key in strata})
    }
    harmful_samples: List[float] = []
    for _ in range(resamples):
        sampled = [
            values[rng.randrange(len(values))]
            for values in strata.values()
            for _ in values
        ]
        overall_samples.append(_cell_weighted_effect(sampled))
        for family, value in _family_effects(sampled).items():
            family_samples[family].append(value)
        harmful_samples.append(_harm_rate(sampled))
    return _BootstrapResult(
        overall=tuple(overall_samples),
        families={key: tuple(value) for key, value in family_samples.items()},
        harmful_rates=tuple(harmful_samples),
    )


def _quantile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError("Quantile requires values")
    position = probability * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _lower_test_p(samples: Sequence[float], observed: float, boundary: float) -> float:
    exceedances = sum((sample - observed + boundary) >= observed for sample in samples)
    return (exceedances + 1) / (len(samples) + 1)


def _upper_test_p(samples: Sequence[float], observed: float, boundary: float) -> float:
    exceedances = sum((sample - observed + boundary) <= observed for sample in samples)
    return (exceedances + 1) / (len(samples) + 1)


def _candidate_report(
    stage_b_records: Sequence[Mapping[str, Any]],
    stage_a_records: Sequence[Mapping[str, Any]],
    policy_id: str,
    *,
    resamples: int,
    seed: int,
    instance: Mapping[str, Any],
) -> Dict[str, Any]:
    rows = _paired_rows(stage_b_records, stage_a_records, policy_id)
    overall = _cell_weighted_effect(rows)
    family_points = _family_effects(rows)
    harmful = _harm_rate(rows)
    bootstrap = _bootstrap(rows, resamples=resamples, seed=seed)
    confidence = float(instance["statistics"]["confidence_level"])
    risk = instance["risk_budget"]
    harm_boundary = float(
        risk["stage_a_harmful_override_rate_upper_confidence_bound_max"]
    )
    constraints: List[Dict[str, Any]] = [
        {
            "id": "stage_a_harmful_override_rate",
            "direction": "upper",
            "boundary": harm_boundary,
            "estimate": harmful,
            "nominal_bound": _quantile(bootstrap.harmful_rates, confidence),
            "raw_p": _upper_test_p(bootstrap.harmful_rates, harmful, harm_boundary),
        }
    ]
    family_boundary = float(
        risk["stage_b_family_primary_effect_lower_confidence_bound_min"]
    )
    family_reports = {}
    for family, point in family_points.items():
        samples = bootstrap.families[family]
        lower = _quantile(samples, 1.0 - confidence)
        family_reports[family] = {
            "mean_effect": point,
            "nominal_lower_bound": lower,
        }
        constraints.append(
            {
                "id": f"stage_b_family_noninferiority:{family}",
                "direction": "lower",
                "boundary": family_boundary,
                "estimate": point,
                "nominal_bound": lower,
                "raw_p": _lower_test_p(samples, point, family_boundary),
            }
        )
    overall_boundary = float(
        risk["stage_b_overall_primary_effect_lower_confidence_bound_min_exclusive"]
    )
    overall_lower = _quantile(bootstrap.overall, 1.0 - confidence)
    constraints.append(
        {
            "id": "stage_b_overall_positive_effect",
            "direction": "lower",
            "boundary": overall_boundary,
            "estimate": overall,
            "nominal_bound": overall_lower,
            "raw_p": _lower_test_p(bootstrap.overall, overall, overall_boundary),
        }
    )
    sample_count = sum(int(row["sample_count"]) for row in rows)
    return {
        "policy_id": policy_id,
        "min_support_margin": _thresholds(instance)[policy_id],
        "replicates": len(rows),
        "mean_stage_b_primary_effect": overall,
        "nominal_overall_lower_bound": overall_lower,
        "family_results": family_reports,
        "stage_a_harmful_override_rate": harmful,
        "stage_a_sample_count": sample_count,
        "stage_a_replicates_with_sample": sum(
            int(row["sample_count"]) > 0 for row in rows
        ),
        "stage_a_severe_harm_count": sum(int(row["severe"]) for row in rows),
        "stage_a_unresolved_count": sum(int(row["unresolved"]) for row in rows),
        "stage_b_override_count": sum(int(row["overrides"]) for row in rows),
        "stage_b_replicates_with_override": sum(
            int(row["overrides"]) > 0 for row in rows
        ),
        "stage_b_observed_disagreement_count": sum(
            int(row["observed"]) for row in rows
        ),
        "stage_b_guard_eligible_disagreement_count": sum(
            int(row["eligible"]) for row in rows
        ),
        "stage_b_algorithm_timeout_rate": sum(
            bool(row["algorithm_timeout"]) for row in rows
        )
        / len(rows),
        "stage_b_path_cap_rate": sum(bool(row["path_cap"]) for row in rows)
        / len(rows),
        "constraints": constraints,
        "bootstrap_resamples": resamples,
        "bootstrap_seed": seed,
    }


def _apply_holm(reports: Sequence[Dict[str, Any]], *, alpha: float) -> None:
    constraints = [
        (report, constraint)
        for report in reports
        for constraint in report["constraints"]
    ]
    ordered = sorted(
        constraints,
        key=lambda item: (
            float(item[1]["raw_p"]),
            str(item[0]["policy_id"]),
            str(item[1]["id"]),
        ),
    )
    running = 0.0
    total = len(ordered)
    for index, (_, constraint) in enumerate(ordered):
        adjusted = min(1.0, (total - index) * float(constraint["raw_p"]))
        running = max(running, adjusted)
        constraint["holm_adjusted_p"] = running
        constraint["holm_pass"] = running <= alpha


def _bound_pass(constraint: Mapping[str, Any]) -> bool:
    if constraint["direction"] == "upper":
        return float(constraint["nominal_bound"]) <= float(constraint["boundary"])
    if constraint["id"] == "stage_b_overall_positive_effect":
        return float(constraint["nominal_bound"]) > float(constraint["boundary"])
    return float(constraint["nominal_bound"]) >= float(constraint["boundary"])


def _mark_eligibility(report: Dict[str, Any], instance: Mapping[str, Any]) -> None:
    support = instance["minimum_activation_support"]
    risk = instance["risk_budget"]
    eligible = report["stage_b_guard_eligible_disagreement_count"]
    checks = {
        "stage_b_override_decisions": report["stage_b_override_count"]
        >= int(support["stage_b_override_decisions_min"]),
        "stage_b_replicates_with_override": report[
            "stage_b_replicates_with_override"
        ]
        >= int(support["stage_b_replicates_with_override_min"]),
        "stage_b_override_fraction": (
            report["stage_b_override_count"] / eligible if eligible else 0.0
        )
        >= float(
            support["stage_b_overridden_fraction_of_guard_eligible_disagreements_min"]
        ),
        "stage_a_sampled_decisions": report["stage_a_sample_count"]
        >= int(support["stage_a_sampled_override_decisions_min"]),
        "stage_a_replicates_with_sample": report["stage_a_replicates_with_sample"]
        >= int(support["stage_a_replicates_with_sample_min"]),
        "stage_a_severe_harm": report["stage_a_severe_harm_count"]
        <= int(risk["stage_a_severe_harmful_override_count_max"]),
        "stage_a_unresolved": report["stage_a_unresolved_count"]
        <= int(risk["stage_a_unresolved_count_max"]),
        "stage_b_algorithm_timeout": report["stage_b_algorithm_timeout_rate"]
        <= float(risk["stage_b_algorithm_timeout_rate_max"]),
        "stage_b_path_cap": report["stage_b_path_cap_rate"]
        <= float(risk["stage_b_path_cap_rate_max"]),
        "all_nominal_bounds": all(_bound_pass(item) for item in report["constraints"]),
        "all_holm_tests": all(item["holm_pass"] for item in report["constraints"]),
    }
    report["eligibility_checks"] = checks
    report["eligible"] = all(checks.values())


def select_v2_calibration_policy(
    stage_b_records: Sequence[Mapping[str, Any]],
    stage_a_records: Sequence[Mapping[str, Any]],
    *,
    bootstrap_resamples: Optional[int] = None,
    test_only_resample_override: bool = False,
) -> Dict[str, Any]:
    """Apply the complete frozen joint selection rule to complete matrices."""
    instance = load_calibration_instance_v2()
    validate_stage_b_calibration_records(stage_b_records, instance=instance)
    validate_stage_a_calibration_records(
        stage_a_records,
        stage_b_records=stage_b_records,
        instance=instance,
    )
    frozen_resamples = int(instance["statistics"]["bootstrap_resamples"])
    resamples = (
        frozen_resamples if bootstrap_resamples is None else int(bootstrap_resamples)
    )
    if resamples != frozen_resamples and not test_only_resample_override:
        raise ValueError("Non-frozen bootstrap count is test-only")
    base_seed = int(instance["statistics"]["calibration_bootstrap_seed"])
    reports = [
        _candidate_report(
            stage_b_records,
            stage_a_records,
            policy_id,
            resamples=resamples,
            seed=base_seed + index,
            instance=instance,
        )
        for index, policy_id in enumerate(_candidate_ids(instance))
    ]
    _apply_holm(
        reports,
        alpha=1.0 - float(instance["statistics"]["confidence_level"]),
    )
    for report in reports:
        _mark_eligibility(report, instance)
    eligible = [report for report in reports if report["eligible"]]
    tie_band = float(instance["selection_rule"]["practical_tie_band"])
    if not eligible:
        selected = "gate_disabled"
        no_eligible = True
        tie_set: List[str] = []
    else:
        best = max(float(report["mean_stage_b_primary_effect"]) for report in eligible)
        tied = [
            report
            for report in eligible
            if best - float(report["mean_stage_b_primary_effect"]) <= tie_band
        ]
        ordered = sorted(
            tied,
            key=lambda report: (
                -float(report["min_support_margin"]),
                str(report["policy_id"]),
            ),
        )
        selected = str(ordered[0]["policy_id"])
        no_eligible = False
        tie_set = [str(report["policy_id"]) for report in ordered]
    return {
        "instance_id": instance["instance_id"],
        "protocol_id": instance["protocol_id"],
        "artifact_kind": "override_gate_v2_calibration_selection_report",
        "split": "calibration",
        "holdout_accessed": False,
        "not_gate_result": True,
        "stage_b_record_count": len(stage_b_records),
        "stage_a_record_count": len(stage_a_records),
        "candidate_reports": reports,
        "holm_family_size": sum(len(report["constraints"]) for report in reports),
        "selected_policy_id": selected,
        "no_eligible_candidate": no_eligible,
        "tie_set_safety_order": tie_set,
        "test_only_resample_override": resamples != frozen_resamples,
        "bootstrap_resamples": resamples,
        "selection_rule": dict(instance["selection_rule"]),
    }
