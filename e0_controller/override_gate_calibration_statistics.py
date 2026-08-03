"""Frozen clustered statistics and policy selection for gate calibration."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from statistics import mean
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .override_gate_calibration import load_calibration_instance

Unit = Tuple[str, int, int]
Stratum = Tuple[str, int]


@dataclass(frozen=True)
class _BootstrapResult:
    overall: Tuple[float, ...]
    families: Mapping[str, Tuple[float, ...]]
    harmful_rates: Tuple[float, ...]
    severe_harmful_rates: Tuple[float, ...]


def _quantile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ValueError("Cannot take a quantile of an empty sample")
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _candidate_ids(instance: Mapping[str, Any]) -> Tuple[str, ...]:
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


def _unit(row: Mapping[str, Any]) -> Unit:
    return (
        str(row["domain_family"]),
        int(row["scale"]),
        int(row["generator_seed"]),
    )


def validate_calibration_records(
    records: Sequence[Mapping[str, Any]],
    *,
    instance: Optional[Mapping[str, Any]] = None,
) -> None:
    """Require the exact complete calibration matrix before selection."""
    document = load_calibration_instance() if instance is None else dict(instance)
    expected_count = int(
        document["planned_counts"]["calibration_closed_loop_replicates_total"]
    )
    if len(records) != expected_count:
        raise ValueError(f"Expected {expected_count} calibration records, got {len(records)}")
    expected_policies = {
        str(candidate["policy_id"]) for candidate in document["candidate_policies"]
    }
    expected_families = set(document["domain_manifest"]["families"])
    expected_scales = {int(scale) for scale in document["domain_manifest"]["scales"]}
    expected_seeds = set(
        document["split_manifests"]["calibration"]["generator_seeds"]
    )
    identities = set()
    for row in records:
        if row.get("split") != "calibration":
            raise ValueError("Selection accepts calibration records only")
        if row.get("holdout_accessed") is not False:
            raise ValueError("Calibration record claims holdout access")
        if row.get("not_gate_result") is not True:
            raise ValueError("Calibration record must remain not_gate_result=true")
        if row.get("policy_id") not in expected_policies:
            raise ValueError(f"Unknown candidate record {row.get('policy_id')!r}")
        if row.get("domain_family") not in expected_families:
            raise ValueError(f"Unknown family {row.get('domain_family')!r}")
        if int(row.get("scale", -1)) not in expected_scales:
            raise ValueError(f"Unknown scale {row.get('scale')!r}")
        if int(row.get("generator_seed", -1)) not in expected_seeds:
            raise ValueError(f"Unknown calibration seed {row.get('generator_seed')!r}")
        if row.get("infrastructure_failure") is not False:
            raise ValueError("Infrastructure-invalid cells must be rerun before selection")
        for field in (
            "primary_utility",
            "override_count",
            "observed_disagreement_count",
            "eligible_disagreement_count",
            "harmful_overrides",
            "severe_harmful_overrides",
            "path_cap_hits",
        ):
            value = row.get(field)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(f"Calibration record {field} must be numeric")
            if not math.isfinite(float(value)) or float(value) < 0.0:
                raise ValueError(f"Calibration record {field} must be finite and nonnegative")
        if float(row["primary_utility"]) > 1.0:
            raise ValueError("Calibration record primary_utility exceeds one")
        for field in (
            "override_count",
            "observed_disagreement_count",
            "eligible_disagreement_count",
            "harmful_overrides",
            "severe_harmful_overrides",
            "path_cap_hits",
        ):
            if int(row[field]) != row[field]:
                raise ValueError(f"Calibration record {field} must be integral")
        if int(row["override_count"]) > int(row["eligible_disagreement_count"]):
            raise ValueError("Override count exceeds eligible disagreements")
        if int(row["eligible_disagreement_count"]) > int(
            row["observed_disagreement_count"]
        ):
            raise ValueError("Eligible disagreements exceed observed disagreements")
        if int(row["harmful_overrides"]) > int(row["override_count"]):
            raise ValueError("Harmful count exceeds overrides")
        if int(row["severe_harmful_overrides"]) > int(row["harmful_overrides"]):
            raise ValueError("Severe-harm count exceeds harmful overrides")
        identity = (
            str(row["policy_id"]),
            str(row["domain_family"]),
            int(row["scale"]),
            int(row["generator_seed"]),
        )
        if identity in identities:
            raise ValueError(f"Duplicate calibration record {identity}")
        identities.add(identity)
    expected_identity_count = (
        len(expected_policies)
        * len(expected_families)
        * len(expected_scales)
        * len(expected_seeds)
    )
    if len(identities) != expected_identity_count:
        raise ValueError("Calibration record identities are incomplete")


def _paired_rows(
    records: Sequence[Mapping[str, Any]],
    policy_id: str,
) -> List[Dict[str, Any]]:
    controls = {
        _unit(row): row for row in records if row["policy_id"] == "gate_disabled"
    }
    rows = []
    for row in records:
        if row["policy_id"] != policy_id:
            continue
        unit = _unit(row)
        if unit not in controls:
            raise ValueError(f"Missing disabled control for {unit}")
        rows.append(
            {
                "family": unit[0],
                "scale": unit[1],
                "seed": unit[2],
                "effect": float(row["primary_utility"])
                - float(controls[unit]["primary_utility"]),
                "override_count": int(row["override_count"]),
                "observed_disagreement_count": int(
                    row["observed_disagreement_count"]
                ),
                "eligible_disagreement_count": int(
                    row["eligible_disagreement_count"]
                ),
                "harmful_overrides": int(row["harmful_overrides"]),
                "severe_harmful_overrides": int(
                    row["severe_harmful_overrides"]
                ),
                "path_cap_hits": int(row["path_cap_hits"]),
                "infrastructure_failure": bool(row["infrastructure_failure"]),
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
    result = {}
    for family in sorted({str(row["family"]) for row in rows}):
        family_rows = [row for row in rows if row["family"] == family]
        result[family] = _cell_weighted_effect(family_rows)
    return result


def _harm_rate(rows: Sequence[Mapping[str, Any]], field: str) -> float:
    overrides = sum(int(row["override_count"]) for row in rows)
    if overrides == 0:
        return 1.0
    return sum(int(row[field]) for row in rows) / overrides


def _cluster_bootstrap(
    rows: Sequence[Mapping[str, Any]],
    *,
    resamples: int,
    seed: int,
) -> _BootstrapResult:
    if resamples <= 0:
        raise ValueError("bootstrap resamples must be positive")
    strata: Dict[Stratum, List[Mapping[str, Any]]] = {}
    for row in rows:
        strata.setdefault((str(row["family"]), int(row["scale"])), []).append(row)
    signature_fields = (
        "effect",
        "override_count",
        "harmful_overrides",
        "severe_harmful_overrides",
    )
    if all(
        len(
            {
                tuple(row[field] for field in signature_fields)
                for row in values
            }
        )
        == 1
        for values in strata.values()
    ):
        overall_point = _cell_weighted_effect(rows)
        family_points = _family_effects(rows)
        harmful_point = _harm_rate(rows, "harmful_overrides")
        severe_point = _harm_rate(rows, "severe_harmful_overrides")
        return _BootstrapResult(
            overall=(overall_point,) * resamples,
            families={
                family: (point,) * resamples
                for family, point in family_points.items()
            },
            harmful_rates=(harmful_point,) * resamples,
            severe_harmful_rates=(severe_point,) * resamples,
        )
    rng = random.Random(seed)
    overall: List[float] = []
    families: Dict[str, List[float]] = {
        family: [] for family in sorted({key[0] for key in strata})
    }
    harmful: List[float] = []
    severe: List[float] = []
    for _ in range(resamples):
        sampled = [
            values[rng.randrange(len(values))]
            for values in strata.values()
            for _ in values
        ]
        overall.append(_cell_weighted_effect(sampled))
        sampled_families = _family_effects(sampled)
        for family, value in sampled_families.items():
            families[family].append(value)
        harmful.append(_harm_rate(sampled, "harmful_overrides"))
        severe.append(_harm_rate(sampled, "severe_harmful_overrides"))
    return _BootstrapResult(
        overall=tuple(overall),
        families={key: tuple(value) for key, value in families.items()},
        harmful_rates=tuple(harmful),
        severe_harmful_rates=tuple(severe),
    )


def _lower_test_p(
    samples: Sequence[float],
    observed: float,
    boundary: float,
) -> float:
    exceedances = sum(
        (sample - observed + boundary) >= observed for sample in samples
    )
    return (exceedances + 1) / (len(samples) + 1)


def _upper_test_p(
    samples: Sequence[float],
    observed: float,
    boundary: float,
) -> float:
    exceedances = sum(
        (sample - observed + boundary) <= observed for sample in samples
    )
    return (exceedances + 1) / (len(samples) + 1)


def _candidate_report(
    records: Sequence[Mapping[str, Any]],
    policy_id: str,
    *,
    resamples: int,
    seed: int,
    instance: Mapping[str, Any],
) -> Dict[str, Any]:
    rows = _paired_rows(records, policy_id)
    overall = _cell_weighted_effect(rows)
    family_points = _family_effects(rows)
    harmful = _harm_rate(rows, "harmful_overrides")
    severe = _harm_rate(rows, "severe_harmful_overrides")
    bootstrap = _cluster_bootstrap(rows, resamples=resamples, seed=seed)
    risk = instance["risk_budget"]
    confidence = float(instance["statistics"]["confidence_level"])
    lower_probability = 1.0 - confidence
    upper_probability = confidence
    override_count = sum(int(row["override_count"]) for row in rows)
    observed_count = sum(
        int(row["observed_disagreement_count"]) for row in rows
    )
    eligible_count = sum(int(row["eligible_disagreement_count"]) for row in rows)
    path_cap_replicates = sum(int(row["path_cap_hits"]) > 0 for row in rows)
    infrastructure_replicates = sum(
        bool(row["infrastructure_failure"]) for row in rows
    )
    constraints: List[Dict[str, Any]] = [
        {
            "id": "harmful_override_rate",
            "direction": "upper",
            "boundary": float(
                risk["harmful_override_rate_upper_confidence_bound_max"]
            ),
            "estimate": harmful,
            "nominal_bound": _quantile(
                bootstrap.harmful_rates,
                upper_probability,
            ),
            "raw_p": _upper_test_p(
                bootstrap.harmful_rates,
                harmful,
                float(risk["harmful_override_rate_upper_confidence_bound_max"]),
            ),
        },
        {
            "id": "severe_harmful_override_rate",
            "direction": "upper",
            "boundary": float(
                risk["severe_harmful_override_rate_upper_confidence_bound_max"]
            ),
            "estimate": severe,
            "nominal_bound": _quantile(
                bootstrap.severe_harmful_rates,
                upper_probability,
            ),
            "raw_p": _upper_test_p(
                bootstrap.severe_harmful_rates,
                severe,
                float(
                    risk["severe_harmful_override_rate_upper_confidence_bound_max"]
                ),
            ),
        },
    ]
    family_reports = {}
    family_boundary = float(
        risk["family_primary_effect_lower_confidence_bound_min"]
    )
    for family, point in family_points.items():
        samples = bootstrap.families[family]
        lower = _quantile(samples, lower_probability)
        family_reports[family] = {
            "mean_effect": point,
            "nominal_lower_bound": lower,
        }
        constraints.append(
            {
                "id": f"family_noninferiority:{family}",
                "direction": "lower",
                "boundary": family_boundary,
                "estimate": point,
                "nominal_bound": lower,
                "raw_p": _lower_test_p(samples, point, family_boundary),
            }
        )
    overall_boundary = float(
        risk["overall_primary_effect_lower_confidence_bound_min_exclusive"]
    )
    overall_lower = _quantile(bootstrap.overall, lower_probability)
    constraints.append(
        {
            "id": "overall_positive_effect",
            "direction": "lower",
            "boundary": overall_boundary,
            "estimate": overall,
            "nominal_bound": overall_lower,
            "raw_p": _lower_test_p(
                bootstrap.overall,
                overall,
                overall_boundary,
            ),
        }
    )
    return {
        "policy_id": policy_id,
        "min_support_margin": _thresholds(instance)[policy_id],
        "replicates": len(rows),
        "mean_primary_effect": overall,
        "nominal_overall_lower_bound": overall_lower,
        "family_results": family_reports,
        "harmful_override_rate": harmful,
        "severe_harmful_override_rate": severe,
        "override_count": override_count,
        "observed_disagreement_count": observed_count,
        "replicates_with_override": sum(
            int(row["override_count"]) > 0 for row in rows
        ),
        "eligible_disagreement_count": eligible_count,
        "overridden_fraction_of_eligible_disagreements": (
            override_count / eligible_count if eligible_count else 0.0
        ),
        "path_cap_rate": path_cap_replicates / len(rows),
        "infrastructure_invalid_fraction": infrastructure_replicates / len(rows),
        "constraints": constraints,
        "bootstrap_resamples": resamples,
        "bootstrap_seed": seed,
    }


def _apply_holm(
    reports: Sequence[Dict[str, Any]],
    *,
    alpha: float,
) -> None:
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


def _constraint_bound_pass(constraint: Mapping[str, Any]) -> bool:
    if constraint["direction"] == "upper":
        return float(constraint["nominal_bound"]) <= float(constraint["boundary"])
    if constraint["id"] == "overall_positive_effect":
        return float(constraint["nominal_bound"]) > float(constraint["boundary"])
    return float(constraint["nominal_bound"]) >= float(constraint["boundary"])


def _mark_eligibility(
    report: Dict[str, Any],
    instance: Mapping[str, Any],
) -> None:
    activation = instance["minimum_activation_support"]
    risk = instance["risk_budget"]
    checks = {
        "override_decisions": report["override_count"]
        >= int(activation["override_decisions_min"]),
        "replicates_with_override": report["replicates_with_override"]
        >= int(activation["replicates_with_override_min"]),
        "override_fraction": (
            report["overridden_fraction_of_eligible_disagreements"]
            >= float(activation["overridden_fraction_of_eligible_disagreements_min"])
        ),
        "path_cap_rate": report["path_cap_rate"]
        <= float(risk["path_cap_rate_max"]),
        "infrastructure_invalid_fraction": report["infrastructure_invalid_fraction"]
        <= float(risk["infrastructure_invalid_cell_fraction_max"]),
        "all_nominal_bounds": all(
            _constraint_bound_pass(constraint)
            for constraint in report["constraints"]
        ),
        "all_holm_tests": all(
            constraint["holm_pass"] for constraint in report["constraints"]
        ),
    }
    report["eligibility_checks"] = checks
    report["eligible"] = all(checks.values())


def select_calibration_policy(
    records: Sequence[Mapping[str, Any]],
    *,
    bootstrap_resamples: Optional[int] = None,
    test_only_resample_override: bool = False,
) -> Dict[str, Any]:
    """Apply the complete frozen calibration selection rule."""
    instance = load_calibration_instance()
    validate_calibration_records(records, instance=instance)
    frozen_resamples = int(instance["statistics"]["bootstrap_resamples"])
    resamples = (
        frozen_resamples if bootstrap_resamples is None else int(bootstrap_resamples)
    )
    if resamples != frozen_resamples and not test_only_resample_override:
        raise ValueError("Non-frozen bootstrap count is test-only")
    base_seed = int(instance["statistics"]["calibration_bootstrap_seed"])
    reports = [
        _candidate_report(
            records,
            policy_id,
            resamples=resamples,
            seed=base_seed + index,
            instance=instance,
        )
        for index, policy_id in enumerate(_candidate_ids(instance))
    ]
    _apply_holm(reports, alpha=1.0 - float(instance["statistics"]["confidence_level"]))
    for report in reports:
        _mark_eligibility(report, instance)

    eligible = [report for report in reports if report["eligible"]]
    tie_band = float(instance["selection_rule"]["practical_tie_band"])
    if not eligible:
        selected = "gate_disabled"
        no_eligible = True
        tie_set: List[str] = []
    else:
        best = max(float(report["mean_primary_effect"]) for report in eligible)
        tied = [
            report
            for report in eligible
            if best - float(report["mean_primary_effect"]) <= tie_band
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
        "artifact_kind": "calibration_selection_report",
        "split": "calibration",
        "holdout_accessed": False,
        "not_gate_result": True,
        "record_count": len(records),
        "candidate_reports": reports,
        "holm_family_size": sum(len(report["constraints"]) for report in reports),
        "selected_policy_id": selected,
        "no_eligible_candidate": no_eligible,
        "tie_set_safety_order": tie_set,
        "test_only_resample_override": resamples != frozen_resamples,
        "bootstrap_resamples": resamples,
        "selection_rule": dict(instance["selection_rule"]),
    }
