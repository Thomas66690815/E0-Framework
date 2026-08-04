"""Domain-free v2 cell planning and artifact contracts.

This module deliberately exposes no outcome-producing command.  It plans the
separate Stage-B and Stage-A matrices, validates result shapes, and emits a
sealed no-outcome manifest for review before an execution layer exists.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .override_gate_calibration_v2 import (
    instance_sha256,
    load_calibration_instance_v2,
    seeds_for_split_v2,
)

CELL_SCHEMA_VERSION = 1
DRY_RUN_SCHEMA_VERSION = 1
UNFROZEN_EXECUTION_COMMIT = "UNFROZEN"
SELECTED_POLICY_PLACEHOLDER = "__selected_policy__"
STAGE_A = "stage_a_paired_evidence"
STAGE_B = "stage_b_closed_loop_parent"
MAX_GITHUB_MATRIX_JOBS = 256

STAGE_B_REPLICATE_REQUIRED_FIELDS = (
    "instance_id",
    "instance_sha256",
    "source_commit",
    "execution_commit",
    "split",
    "stage",
    "domain_family",
    "scale",
    "generator_seed",
    "policy_id",
    "primary_utility",
    "observed_disagreement_count",
    "guard_eligible_disagreement_count",
    "executed_override_count",
    "algorithm_timeout_count",
    "path_cap_count",
    "infrastructure_failure",
    "parent_wall_time_ms",
    "holdout_accessed",
    "not_gate_result",
)

STAGE_A_REPLICATE_REQUIRED_FIELDS = (
    "instance_id",
    "instance_sha256",
    "source_commit",
    "execution_commit",
    "split",
    "stage",
    "domain_family",
    "scale",
    "generator_seed",
    "policy_id",
    "sample_manifest_sha256",
    "sampling_frame_override_count",
    "sample_count",
    "parent_replay_trace_match",
    "paired_decisions",
    "unresolved_count",
    "infrastructure_failure",
    "instrumentation_wall_time_ms",
    "holdout_accessed",
    "not_gate_result",
)

SELECTION_REQUIRED_FIELDS = (
    "instance_id",
    "instance_sha256",
    "source_commit",
    "execution_commit",
    "split",
    "stage_a_record_count",
    "stage_b_record_count",
    "candidate_reports",
    "selected_policy_id",
    "no_eligible_candidate",
    "statistics",
    "artifact_hashes",
    "holdout_accessed",
    "not_gate_result",
)


class V2ExecutionProhibited(PermissionError):
    """Raised until an independently reviewed v2 execution layer exists."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _full_commit(value: Any) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{40}", str(value)))


def _candidate_ids(instance: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(str(item["policy_id"]) for item in instance["candidate_policies"])


def _active_candidate_ids(instance: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(
        policy_id
        for policy_id in _candidate_ids(instance)
        if policy_id != "gate_disabled"
    )


@dataclass(frozen=True)
class V2CellTask:
    """One stage × policy × family × scale cell containing all split seeds."""

    instance_id: str
    instance_sha256: str
    source_commit: str
    execution_commit: str
    split: str
    stage: str
    family: str
    scale: int
    policy_id: str
    seeds: tuple[int, ...]

    @property
    def cell_id(self) -> str:
        stage_token = "stage-a" if self.stage == STAGE_A else "stage-b"
        return (
            f"gate-v2-{self.split}-{stage_token}-{self.family}-"
            f"N{self.scale}-{self.policy_id}"
        )

    @property
    def artifact_name(self) -> str:
        return self.cell_id + ".json"

    @property
    def replicate_count(self) -> int:
        return len(self.seeds)

    @property
    def sampled_pairs_max(self) -> int:
        if self.stage != STAGE_A:
            return 0
        return self.replicate_count * 4

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cell_schema_version": CELL_SCHEMA_VERSION,
            "instance_id": self.instance_id,
            "instance_sha256": self.instance_sha256,
            "source_commit": self.source_commit,
            "execution_commit": self.execution_commit,
            "split": self.split,
            "stage": self.stage,
            "family": self.family,
            "scale": self.scale,
            "policy_id": self.policy_id,
            "seeds": list(self.seeds),
            "replicate_count": self.replicate_count,
            "sampled_pairs_max": self.sampled_pairs_max,
            "cell_id": self.cell_id,
            "artifact_name": self.artifact_name,
        }


def build_cell_plan(
    split: str,
    stage: str,
    *,
    execution_commit: str = UNFROZEN_EXECUTION_COMMIT,
    selected_policy_id: Optional[str] = None,
    planning_only: bool = True,
    instance: Optional[Mapping[str, Any]] = None,
) -> List[V2CellTask]:
    """Build exact cell identities without importing or building a domain."""
    if not planning_only:
        raise V2ExecutionProhibited(
            "WP-GATE-0.12 exposes planning only; v2 outcome execution is prohibited"
        )
    document = load_calibration_instance_v2() if instance is None else instance
    if split == "exploration":
        raise V2ExecutionProhibited("Historical exploration may not be executed")
    if split not in {"calibration", "verification", "protected_holdout"}:
        raise ValueError(f"Unknown executable split: {split}")
    if stage not in {STAGE_A, STAGE_B}:
        raise ValueError(f"Unknown v2 stage: {stage}")
    if selected_policy_id is not None:
        raise V2ExecutionProhibited(
            "Planning cannot bind a selected policy before calibration"
        )

    if split == "calibration":
        policy_ids = (
            _active_candidate_ids(document)
            if stage == STAGE_A
            else _candidate_ids(document)
        )
    else:
        policy_ids = (SELECTED_POLICY_PLACEHOLDER,)
    seeds = tuple(seeds_for_split_v2(split, document))
    digest = instance_sha256(document)
    tasks = [
        V2CellTask(
            instance_id=document["instance_id"],
            instance_sha256=digest,
            source_commit=document["source_commit"],
            execution_commit=execution_commit,
            split=split,
            stage=stage,
            family=str(family),
            scale=int(scale),
            policy_id=policy_id,
            seeds=seeds,
        )
        for policy_id in policy_ids
        for family in document["domain_manifest"]["families"]
        for scale in document["domain_manifest"]["scales"]
    ]
    validate_cell_plan(tasks, split=split, stage=stage, instance=document)
    return tasks


def validate_cell_plan(
    tasks: Sequence[V2CellTask],
    *,
    split: str,
    stage: str,
    instance: Optional[Mapping[str, Any]] = None,
) -> None:
    """Validate ordering-independent identity, population, and matrix limits."""
    document = load_calibration_instance_v2() if instance is None else instance
    if not tasks:
        raise ValueError("V2 cell plan must not be empty")
    identities = [task.cell_id for task in tasks]
    if len(identities) != len(set(identities)):
        raise ValueError("V2 cell IDs must be unique")
    artifacts = [task.artifact_name for task in tasks]
    if len(artifacts) != len(set(artifacts)):
        raise ValueError("V2 cell artifact names must be unique")
    expected_seeds = tuple(seeds_for_split_v2(split, document))
    if any(task.seeds != expected_seeds for task in tasks):
        raise ValueError("V2 cell seed manifest changed")
    if any(task.split != split or task.stage != stage for task in tasks):
        raise ValueError("V2 cell stage or split mismatch")
    if len(tasks) > MAX_GITHUB_MATRIX_JOBS:
        raise ValueError("V2 stage matrix exceeds GitHub's matrix-job limit")
    if split == "calibration":
        expected = 132 if stage == STAGE_A else 144
    else:
        expected = 12
    if len(tasks) != expected:
        raise ValueError(f"Expected {expected} {split} {stage} cells")
    if stage == STAGE_A and any(task.policy_id == "gate_disabled" for task in tasks):
        raise ValueError("Stage A must exclude the disabled control")


def matrix_plan(
    *,
    split: str = "calibration",
    stage: str,
    execution_commit: str = UNFROZEN_EXECUTION_COMMIT,
) -> Dict[str, Any]:
    """Return one explicit, separately dispatchable stage matrix."""
    tasks = build_cell_plan(
        split,
        stage,
        execution_commit=execution_commit,
        planning_only=True,
    )
    return {
        "execution_prohibited": True,
        "split": split,
        "stage": stage,
        "cell_count": len(tasks),
        "replicate_count": sum(task.replicate_count for task in tasks),
        "sampled_pairs_max": sum(task.sampled_pairs_max for task in tasks),
        "include": [
            {
                "cell_index": index,
                **task.to_dict(),
                "cell_sha256": _sha256(task.to_dict()),
            }
            for index, task in enumerate(tasks)
        ],
    }


def artifact_contract() -> Dict[str, Any]:
    """Return v2 record shapes without producing result-shaped evidence."""
    return {
        "stage_b_replicate_record": {
            "required_fields": list(STAGE_B_REPLICATE_REQUIRED_FIELDS),
            "branch_time_charged_to_parent_must_be": False,
        },
        "stage_a_replicate_record": {
            "required_fields": list(STAGE_A_REPLICATE_REQUIRED_FIELDS),
            "parent_replay_trace_match_must_be": True,
            "sample_count_max": 4,
        },
        "selection_record": {
            "required_fields": list(SELECTION_REQUIRED_FIELDS),
            "split_must_be": "calibration",
            "both_stages_required": True,
        },
        "global_invariants": {
            "instance_sha256": instance_sha256(),
            "source_commit_must_match_instance": True,
            "execution_commit_must_be_full_sha": True,
            "highest_attempt_only": True,
            "fallback_to_earlier_attempt": False,
            "stage_a_time_is_parent_performance": False,
            "stage_a_unresolved_is_parent_algorithm_timeout": False,
            "authorization_required_for_any_outcome_command": True,
        },
    }


def validate_artifact_record(kind: str, record: Mapping[str, Any]) -> None:
    """Validate common provenance and stage-specific non-confounding fields."""
    required_by_kind = {
        "stage_b_replicate_record": STAGE_B_REPLICATE_REQUIRED_FIELDS,
        "stage_a_replicate_record": STAGE_A_REPLICATE_REQUIRED_FIELDS,
        "selection_record": SELECTION_REQUIRED_FIELDS,
    }
    if kind not in required_by_kind:
        raise ValueError(f"Unknown v2 artifact kind: {kind}")
    missing = set(required_by_kind[kind]).difference(record)
    if missing:
        raise ValueError(f"{kind} missing fields: {sorted(missing)}")
    instance = load_calibration_instance_v2()
    if record["instance_id"] != instance["instance_id"]:
        raise ValueError("V2 artifact references another instance")
    if record["instance_sha256"] != instance_sha256(instance):
        raise ValueError("V2 artifact instance digest changed")
    if record["source_commit"] != instance["source_commit"]:
        raise ValueError("V2 artifact source commit changed")
    if not _full_commit(record["execution_commit"]):
        raise ValueError("V2 artifact execution commit must be a full SHA")
    split = str(record["split"])
    if split not in {"calibration", "verification", "protected_holdout"}:
        raise ValueError("V2 artifact split is invalid")
    if record["holdout_accessed"] is not (split == "protected_holdout"):
        raise ValueError("V2 artifact holdout flag contradicts its split")
    if record["not_gate_result"] is not True:
        raise ValueError("V2 pre-verification artifacts must be not_gate_result=true")
    if kind == "stage_b_replicate_record":
        if record["stage"] != STAGE_B:
            raise ValueError("Stage-B artifact has wrong stage")
        if record.get("branch_time_charged_to_parent") is not False:
            raise ValueError("Stage-B parent time cannot contain branch time")
    elif kind == "stage_a_replicate_record":
        if record["stage"] != STAGE_A:
            raise ValueError("Stage-A artifact has wrong stage")
        if int(record["sample_count"]) > 4:
            raise ValueError("Stage-A sample cap exceeded")
        skipped = record.get("stage_a_skipped_due_stage_b_valid_negative") is True
        if not skipped and record["parent_replay_trace_match"] is not True:
            raise ValueError("Stage-A parent replay must match Stage B")
        if skipped and record["parent_replay_trace_match"] is not False:
            raise ValueError("Skipped Stage-A replay cannot claim a trace match")
        if record.get("instrumentation_time_is_parent_performance") is not False:
            raise ValueError("Stage-A time cannot be parent performance")
    elif split != "calibration":
        raise ValueError("V2 selection is calibration-only")


def dry_run_manifest(
    *,
    execution_commit: str = UNFROZEN_EXECUTION_COMMIT,
) -> Dict[str, Any]:
    """Seal every future matrix identity while proving no domain was built."""
    instance = load_calibration_instance_v2()
    splits: Dict[str, Any] = {}
    for split in ("calibration", "verification", "protected_holdout"):
        stages = {}
        for stage in (STAGE_B, STAGE_A):
            matrix = matrix_plan(
                split=split,
                stage=stage,
                execution_commit=execution_commit,
            )
            stages[stage] = {
                "cell_count": matrix["cell_count"],
                "replicate_count": matrix["replicate_count"],
                "sampled_pairs_max": matrix["sampled_pairs_max"],
                "matrix_sha256": _sha256(matrix["include"]),
                "first_cell_id": matrix["include"][0]["cell_id"],
                "last_cell_id": matrix["include"][-1]["cell_id"],
            }
        splits[split] = {
            "generator_seeds": list(seeds_for_split_v2(split, instance)),
            "stages": stages,
        }
    manifest = {
        "dry_run_schema_version": DRY_RUN_SCHEMA_VERSION,
        "artifact_kind": "override_gate_v2_planning_dry_run",
        "instance_id": instance["instance_id"],
        "instance_sha256": instance_sha256(instance),
        "source_commit": instance["source_commit"],
        "execution_commit": execution_commit,
        "execution_commit_frozen": _full_commit(execution_commit),
        "execution_prohibited": True,
        "outcome_commands_exposed": False,
        "domains_instantiated": 0,
        "outcomes_observed": 0,
        "calibration_executed": False,
        "verification_executed": False,
        "protected_holdout_accessed": False,
        "holdout_accessed": False,
        "not_gate_result": True,
        "splits": splits,
        "artifact_contract": artifact_contract(),
    }
    manifest["dry_run_sha256"] = _sha256(manifest)
    validate_dry_run_manifest(manifest)
    return manifest


def validate_dry_run_manifest(manifest: Mapping[str, Any]) -> None:
    """Reject result-shaped or count-drifted planning evidence."""
    if manifest.get("execution_prohibited") is not True:
        raise ValueError("V2 dry run must prohibit execution")
    if manifest.get("outcome_commands_exposed") is not False:
        raise ValueError("V2 dry run cannot expose outcome commands")
    for field in ("domains_instantiated", "outcomes_observed"):
        if manifest.get(field) != 0:
            raise ValueError(f"V2 dry-run {field} must be zero")
    for field in (
        "calibration_executed",
        "verification_executed",
        "protected_holdout_accessed",
        "holdout_accessed",
    ):
        if manifest.get(field) is not False:
            raise ValueError(f"V2 dry-run {field} must be false")
    expected = {
        "calibration": {STAGE_B: (144, 2880, 0), STAGE_A: (132, 2640, 10560)},
        "verification": {STAGE_B: (12, 360, 0), STAGE_A: (12, 360, 1440)},
        "protected_holdout": {
            STAGE_B: (12, 360, 0),
            STAGE_A: (12, 360, 1440),
        },
    }
    for split, stages in expected.items():
        for stage, values in stages.items():
            actual = manifest["splits"][split]["stages"][stage]
            if (
                actual["cell_count"],
                actual["replicate_count"],
                actual["sampled_pairs_max"],
            ) != values:
                raise ValueError(f"V2 dry-run counts changed for {split} {stage}")
    payload = dict(manifest)
    recorded = payload.pop("dry_run_sha256", None)
    if recorded != _sha256(payload):
        raise ValueError("V2 dry-run manifest digest changed")


def _write_atomic_json(path: Path, document: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True).encode(
            "utf-8"
        )
        + b"\n"
    )
    os.replace(temporary, path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    dry = subparsers.add_parser("dry-run")
    dry.add_argument("--execution-commit", default=UNFROZEN_EXECUTION_COMMIT)
    dry.add_argument("--output", type=Path)
    matrix = subparsers.add_parser("matrix")
    matrix.add_argument(
        "--split",
        choices=("calibration", "verification", "protected_holdout"),
        default="calibration",
    )
    matrix.add_argument("--stage", choices=(STAGE_B, STAGE_A), required=True)
    matrix.add_argument("--execution-commit", default=UNFROZEN_EXECUTION_COMMIT)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "matrix":
            result = matrix_plan(
                split=args.split,
                stage=args.stage,
                execution_commit=args.execution_commit,
            )
        else:
            result = dry_run_manifest(execution_commit=args.execution_commit)
            if args.output is not None:
                _write_atomic_json(args.output, result)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, V2ExecutionProhibited, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
