"""Fail-closed execution planning for override-gate calibration.

WP-GATE-0.4 deliberately implements only the domain-free execution scaffold:
stable tasks, split authorization, matrix partitioning, artifact contracts,
and dry-run manifests.  It does not import a domain generator and exposes no
outcome-producing command.
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

from .override_gate_calibration import (
    load_calibration_instance,
    seeds_for_split,
)

TASK_SCHEMA_VERSION = 1
DRY_RUN_SCHEMA_VERSION = 1
MAX_GITHUB_MATRIX_JOBS = 256
DEFAULT_BATCH_COUNT = 240
UNFROZEN_EXECUTION_COMMIT = "UNFROZEN"
SELECTED_POLICY_PLACEHOLDER = "__selected_policy__"

PAIRED_BRANCH_REQUIRED_FIELDS = (
    "instance_id",
    "instance_sha256",
    "source_commit",
    "execution_commit",
    "split",
    "run_id",
    "state_hash",
    "random_stream_id",
    "domain_family",
    "scale",
    "generator_seed",
    "episode_index",
    "interaction_index",
    "geometry",
    "horizon",
    "action_count",
    "phase_regime",
    "support_margin",
    "path_imbalance",
    "path_cap_hit",
    "greedy_action",
    "lookahead_action",
    "greedy_utility",
    "lookahead_utility",
    "delta_utility",
    "parent_run_mutated",
    "holdout_accessed",
    "not_gate_result",
)

CLOSED_LOOP_REQUIRED_FIELDS = (
    "instance_id",
    "instance_sha256",
    "source_commit",
    "execution_commit",
    "split",
    "run_id",
    "domain_family",
    "scale",
    "generator_seed",
    "outcome_seed",
    "policy_seed",
    "policy_id",
    "control_policy_id",
    "control_run_id",
    "primary_utility",
    "primary_effect_vs_disabled",
    "override_count",
    "observed_disagreement_count",
    "eligible_disagreement_count",
    "beneficial_overrides",
    "neutral_overrides",
    "harmful_overrides",
    "severe_harmful_overrides",
    "unresolved_overrides",
    "path_cap_hits",
    "infrastructure_failure",
    "status",
    "holdout_accessed",
    "not_gate_result",
)

SELECTION_REQUIRED_FIELDS = (
    "instance_id",
    "instance_sha256",
    "source_commit",
    "execution_commit",
    "split",
    "candidate_reports",
    "selected_policy_id",
    "no_eligible_candidate",
    "statistics",
    "artifact_hashes",
    "holdout_accessed",
    "not_gate_result",
)


class SplitAuthorizationError(ValueError):
    """Raised when a protected split is requested without prior evidence."""


@dataclass(frozen=True)
class CalibrationTask:
    """One policy × domain experimental unit, without a constructed domain."""

    instance_id: str
    instance_sha256: str
    source_commit: str
    execution_commit: str
    split: str
    family: str
    scale: int
    seed: int
    policy_id: str

    @property
    def run_id(self) -> str:
        return (
            f"gate-{self.split}-{self.family}-N{self.scale}-"
            f"s{self.seed:04d}-{self.policy_id}"
        )

    @property
    def shard_name(self) -> str:
        return (
            f"{self.split}__{self.family}__N{self.scale}__"
            f"s{self.seed:04d}__{self.policy_id}.json"
        )

    @property
    def control_policy_id(self) -> str:
        return "gate_disabled"

    @property
    def control_run_id(self) -> str:
        return (
            f"gate-{self.split}-{self.family}-N{self.scale}-"
            f"s{self.seed:04d}-gate_disabled"
        )

    @property
    def control_mode(self) -> str:
        if self.policy_id == "gate_disabled":
            return "self"
        if self.split == "calibration":
            return "shared_calibration_task"
        return "coexecuted_in_task"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_schema_version": TASK_SCHEMA_VERSION,
            "instance_id": self.instance_id,
            "instance_sha256": self.instance_sha256,
            "source_commit": self.source_commit,
            "execution_commit": self.execution_commit,
            "split": self.split,
            "family": self.family,
            "scale": self.scale,
            "seed": self.seed,
            "policy_id": self.policy_id,
            "control_policy_id": self.control_policy_id,
            "control_run_id": self.control_run_id,
            "control_mode": self.control_mode,
            "run_id": self.run_id,
            "shard_name": self.shard_name,
        }


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def instance_sha256(instance: Optional[Mapping[str, Any]] = None) -> str:
    """Return the canonical instance digest pinned by the validator."""
    document = load_calibration_instance() if instance is None else instance
    return _sha256(document)


def _full_commit(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{40}", value))


def _full_sha256(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", value))


def _candidate_ids(instance: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(item["policy_id"] for item in instance["candidate_policies"])


def _validate_authorization(
    split: str,
    selected_policy_id: Optional[str],
    authorization: Optional[Mapping[str, Any]],
    instance: Mapping[str, Any],
) -> str:
    candidates = set(_candidate_ids(instance))
    if not selected_policy_id or selected_policy_id not in candidates:
        raise SplitAuthorizationError(
            f"{split} requires one selected policy from the frozen candidate set"
        )
    if authorization is None:
        raise SplitAuthorizationError(f"{split} requires a frozen authorization record")
    required = {
        "instance_id",
        "selected_policy_id",
        "artifact_sha256",
        "retuning_after_artifact",
    }
    missing = required.difference(authorization)
    if missing:
        raise SplitAuthorizationError(
            f"{split} authorization missing fields: {sorted(missing)}"
        )
    if authorization["instance_id"] != instance["instance_id"]:
        raise SplitAuthorizationError("Authorization references another instance")
    if authorization["selected_policy_id"] != selected_policy_id:
        raise SplitAuthorizationError("Authorization policy does not match selection")
    if not _full_sha256(str(authorization["artifact_sha256"])):
        raise SplitAuthorizationError(
            "Authorization artifact_sha256 must be 64 hex characters"
        )
    if authorization["retuning_after_artifact"] is not False:
        raise SplitAuthorizationError("Retuning after authorization is forbidden")
    if split == "verification":
        if authorization.get("calibration_status") != "selected":
            raise SplitAuthorizationError(
                "Verification requires calibration_status=selected"
            )
    elif split == "protected_holdout":
        if authorization.get("verification_status") != "passed":
            raise SplitAuthorizationError(
                "Protected holdout requires verification_status=passed"
            )
        if authorization.get("protected_holdout_accessed") is not False:
            raise SplitAuthorizationError("Protected holdout is already marked accessed")
    return selected_policy_id


def build_task_plan(
    split: str,
    *,
    execution_commit: str = UNFROZEN_EXECUTION_COMMIT,
    selected_policy_id: Optional[str] = None,
    authorization: Optional[Mapping[str, Any]] = None,
    planning_only: bool = True,
    instance: Optional[Mapping[str, Any]] = None,
) -> List[CalibrationTask]:
    """Build stable tasks without importing or constructing any domain.

    Protected split planning may use a visible placeholder.  A non-planning
    request requires a full execution commit and the frozen predecessor
    artifact specified by the lifecycle contract.
    """
    document = load_calibration_instance() if instance is None else dict(instance)
    if split == "exploration":
        raise SplitAuthorizationError("Historical exploration may not be executed")
    if split not in {"calibration", "verification", "protected_holdout"}:
        raise ValueError(f"Unknown executable split: {split}")
    if not planning_only and not _full_commit(execution_commit):
        raise SplitAuthorizationError(
            "Outcome execution requires a frozen 40-character execution commit"
        )

    if split == "calibration":
        policy_ids = _candidate_ids(document)
        if selected_policy_id is not None or authorization is not None:
            raise SplitAuthorizationError(
                "Calibration evaluates the complete frozen candidate set"
            )
    elif planning_only:
        policy_ids = (SELECTED_POLICY_PLACEHOLDER,)
    else:
        policy_ids = (
            _validate_authorization(
                split,
                selected_policy_id,
                authorization,
                document,
            ),
        )

    digest = instance_sha256(document)
    families = tuple(document["domain_manifest"]["families"])
    scales = tuple(document["domain_manifest"]["scales"])
    seeds = tuple(seeds_for_split(split, document))
    tasks = [
        CalibrationTask(
            instance_id=document["instance_id"],
            instance_sha256=digest,
            source_commit=document["source_commit"],
            execution_commit=execution_commit,
            split=split,
            family=family,
            scale=int(scale),
            seed=int(seed),
            policy_id=policy_id,
        )
        for family in families
        for scale in scales
        for seed in seeds
        for policy_id in policy_ids
    ]
    validate_task_plan(tasks, split=split, planning_only=planning_only, instance=document)
    return tasks


def validate_task_plan(
    tasks: Sequence[CalibrationTask],
    *,
    split: str,
    planning_only: bool,
    instance: Optional[Mapping[str, Any]] = None,
) -> None:
    """Validate identity, ordering, counts, and split membership."""
    document = load_calibration_instance() if instance is None else dict(instance)
    if not tasks:
        raise ValueError("Task plan must not be empty")
    records = [task.to_dict() for task in tasks]
    if len({record["run_id"] for record in records}) != len(records):
        raise ValueError("Task run IDs must be unique")
    if len({record["shard_name"] for record in records}) != len(records):
        raise ValueError("Task shard names must be unique")
    allowed_seeds = set(seeds_for_split(split, document))
    if any(task.seed not in allowed_seeds for task in tasks):
        raise ValueError("Task seed lies outside its frozen split")
    if any(task.split != split for task in tasks):
        raise ValueError("Task split does not match the plan")
    if any(task.control_policy_id != "gate_disabled" for task in tasks):
        raise ValueError("Every task must use gate_disabled as its control")
    if split in {"verification", "protected_holdout"} and any(
        task.control_mode != "coexecuted_in_task" for task in tasks
    ):
        raise ValueError(f"{split} must coexecute its disabled control arm")
    expected = document["planned_counts"]
    if split == "calibration":
        count = expected["calibration_closed_loop_replicates_total"]
    elif split == "verification":
        count = expected["verification_replicates_selected_policy"]
    else:
        count = expected["protected_holdout_replicates_selected_policy"]
    if len(tasks) != count:
        raise ValueError(f"Expected {count} {split} tasks, got {len(tasks)}")
    if not planning_only and any(
        not _full_commit(task.execution_commit) for task in tasks
    ):
        raise SplitAuthorizationError("Execution task has an unfrozen commit")


def partition_tasks(
    tasks: Sequence[CalibrationTask],
    batch_count: int,
) -> List[List[CalibrationTask]]:
    """Return stable, balanced, strided batches within GitHub's matrix limit."""
    if batch_count <= 0:
        raise ValueError("batch_count must be positive")
    if batch_count > MAX_GITHUB_MATRIX_JOBS:
        raise ValueError(
            f"batch_count exceeds GitHub's {MAX_GITHUB_MATRIX_JOBS}-job matrix limit"
        )
    if batch_count > len(tasks):
        raise ValueError("batch_count must not exceed task count")
    return [list(tasks[index::batch_count]) for index in range(batch_count)]


def matrix_plan(
    *,
    split: str = "calibration",
    batch_count: int = DEFAULT_BATCH_COUNT,
    execution_commit: str = UNFROZEN_EXECUTION_COMMIT,
) -> Dict[str, Any]:
    """Return a planning-only GitHub matrix; no runner command consumes it yet."""
    tasks = build_task_plan(
        split,
        execution_commit=execution_commit,
        planning_only=True,
    )
    batches = partition_tasks(tasks, batch_count)
    return {
        "execution_prohibited": True,
        "split": split,
        "task_count": len(tasks),
        "batch_count": len(batches),
        "include": [
            {
                "batch_index": index,
                "task_count": len(batch),
                "first_run_id": batch[0].run_id,
                "last_run_id": batch[-1].run_id,
                "task_sha256": _sha256([task.to_dict() for task in batch]),
            }
            for index, batch in enumerate(batches)
        ],
    }


def artifact_contract() -> Dict[str, Any]:
    """Return result-field contracts without creating a result artifact."""
    return {
        "paired_branch_record": {
            "required_fields": list(PAIRED_BRANCH_REQUIRED_FIELDS),
            "parent_run_mutated_must_be": False,
        },
        "closed_loop_replicate_record": {
            "required_fields": list(CLOSED_LOOP_REQUIRED_FIELDS),
        },
        "selection_record": {
            "required_fields": list(SELECTION_REQUIRED_FIELDS),
            "split_must_be": "calibration",
        },
        "global_invariants": {
            "instance_sha256_must_match": instance_sha256(),
            "source_commit_must_match_instance": True,
            "execution_commit_must_be_full_sha": True,
            "verification_retuning_forbidden": True,
            "protected_holdout_requires_verification_pass": True,
            "infrastructure_failure_is_not_algorithmic_failure": True,
            "verification_and_holdout_control_mode": "coexecuted_in_task",
        },
    }


def validate_artifact_record(kind: str, record: Mapping[str, Any]) -> None:
    """Validate common no-leakage fields and kind-specific result shape."""
    required_by_kind = {
        "paired_branch_record": PAIRED_BRANCH_REQUIRED_FIELDS,
        "closed_loop_replicate_record": CLOSED_LOOP_REQUIRED_FIELDS,
        "selection_record": SELECTION_REQUIRED_FIELDS,
    }
    if kind not in required_by_kind:
        raise ValueError(f"Unknown artifact record kind: {kind}")
    missing = set(required_by_kind[kind]).difference(record)
    if missing:
        raise ValueError(f"{kind} missing fields: {sorted(missing)}")
    instance = load_calibration_instance()
    if record["instance_id"] != instance["instance_id"]:
        raise ValueError("Artifact references another instance")
    if record["instance_sha256"] != instance_sha256(instance):
        raise ValueError("Artifact instance digest differs from frozen instance")
    if record["source_commit"] != instance["source_commit"]:
        raise ValueError("Artifact source commit differs from frozen source")
    if not _full_commit(str(record["execution_commit"])):
        raise ValueError("Artifact execution commit must be a full SHA")
    split = str(record["split"])
    if split not in {"calibration", "verification", "protected_holdout"}:
        raise ValueError("Artifact has an invalid split")
    expected_holdout = split == "protected_holdout"
    if record["holdout_accessed"] is not expected_holdout:
        raise ValueError("Artifact holdout_accessed flag contradicts its split")
    if record["not_gate_result"] is not True:
        raise ValueError("Calibration artifacts must remain not_gate_result=true")
    if kind == "paired_branch_record" and record["parent_run_mutated"] is not False:
        raise ValueError("Diagnostic branches must not mutate the parent run")
    if kind == "selection_record" and split != "calibration":
        raise ValueError("Policy selection is calibration-only")


def dry_run_manifest(
    *,
    execution_commit: str = UNFROZEN_EXECUTION_COMMIT,
    batch_count: int = DEFAULT_BATCH_COUNT,
) -> Dict[str, Any]:
    """Build the complete non-executing preflight manifest."""
    instance = load_calibration_instance()
    split_summaries: Dict[str, Any] = {}
    for split in ("calibration", "verification", "protected_holdout"):
        tasks = build_task_plan(
            split,
            execution_commit=execution_commit,
            planning_only=True,
            instance=instance,
        )
        split_summaries[split] = {
            "task_count": len(tasks),
            "task_plan_sha256": _sha256([task.to_dict() for task in tasks]),
            "first_run_id": tasks[0].run_id,
            "last_run_id": tasks[-1].run_id,
            "generator_seeds": list(seeds_for_split(split, instance)),
            "policy_ids": list(dict.fromkeys(task.policy_id for task in tasks)),
            "control_modes": list(dict.fromkeys(task.control_mode for task in tasks)),
        }
        if split == "calibration":
            split_summaries[split]["matrix"] = matrix_plan(
                split=split,
                batch_count=batch_count,
                execution_commit=execution_commit,
            )
    manifest = {
        "dry_run_schema_version": DRY_RUN_SCHEMA_VERSION,
        "artifact_kind": "override_gate_calibration_dry_run",
        "instance_id": instance["instance_id"],
        "instance_sha256": instance_sha256(instance),
        "source_commit": instance["source_commit"],
        "execution_commit": execution_commit,
        "execution_commit_frozen": _full_commit(execution_commit),
        "execution_prohibited": True,
        "domains_instantiated": 0,
        "outcomes_observed": 0,
        "calibration_executed": False,
        "verification_executed": False,
        "protected_holdout_accessed": False,
        "not_gate_result": True,
        "splits": split_summaries,
        "artifact_contract": artifact_contract(),
    }
    manifest["dry_run_sha256"] = _sha256(manifest)
    validate_dry_run_manifest(manifest)
    return manifest


def validate_dry_run_manifest(manifest: Mapping[str, Any]) -> None:
    """Verify the dry-run seal and its non-execution assertions."""
    if manifest.get("execution_prohibited") is not True:
        raise ValueError("Dry run must prohibit execution")
    for field in (
        "domains_instantiated",
        "outcomes_observed",
    ):
        if manifest.get(field) != 0:
            raise ValueError(f"Dry run {field} must be zero")
    for field in (
        "calibration_executed",
        "verification_executed",
        "protected_holdout_accessed",
    ):
        if manifest.get(field) is not False:
            raise ValueError(f"Dry run {field} must be false")
    expected_counts = {
        "calibration": 2880,
        "verification": 360,
        "protected_holdout": 360,
    }
    for split, count in expected_counts.items():
        if manifest.get("splits", {}).get(split, {}).get("task_count") != count:
            raise ValueError(f"Dry-run count changed for {split}")
    payload = dict(manifest)
    recorded = payload.pop("dry_run_sha256", None)
    if recorded != _sha256(payload):
        raise ValueError("Dry-run manifest digest changed")


def _write_atomic_json(path: Path, document: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(
        json.dumps(
            document,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )
    os.replace(temporary, path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    dry = subparsers.add_parser("dry-run")
    dry.add_argument("--execution-commit", default=UNFROZEN_EXECUTION_COMMIT)
    dry.add_argument("--batch-count", type=int, default=DEFAULT_BATCH_COUNT)
    dry.add_argument("--output", type=Path)

    matrix = subparsers.add_parser("matrix")
    matrix.add_argument(
        "--split",
        choices=("calibration", "verification", "protected_holdout"),
        default="calibration",
    )
    matrix.add_argument("--execution-commit", default=UNFROZEN_EXECUTION_COMMIT)
    matrix.add_argument("--batch-count", type=int, default=DEFAULT_BATCH_COUNT)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "matrix":
            result = matrix_plan(
                split=args.split,
                batch_count=args.batch_count,
                execution_commit=args.execution_commit,
            )
        else:
            result = dry_run_manifest(
                execution_commit=args.execution_commit,
                batch_count=args.batch_count,
            )
            if args.output is not None:
                _write_atomic_json(args.output, result)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, SplitAuthorizationError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
