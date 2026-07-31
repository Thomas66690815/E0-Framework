"""Authorization-gated, cell-aligned calibration distribution.

WP-GATE-0.7 exposes calibration outcome commands only behind a canonical
authorization record, its SHA-256, a full execution commit, and an explicit
confirmation phrase.  It cannot construct verification or holdout tasks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .override_gate_calibration import load_calibration_instance
from .override_gate_calibration_pipeline import (
    AUTHORIZATION_SCHEMA_VERSION,
    DEFAULT_OUTPUT,
    consolidate_calibration,
    execute_task_set,
    load_calibration_shard,
    validate_execution_authorization,
)
from .override_gate_calibration_runner import (
    CalibrationTask,
    build_task_plan,
    instance_sha256,
)

CELL_ARTIFACT_SCHEMA_VERSION = 1
DISTRIBUTED_MERGE_SCHEMA_VERSION = 1
CALIBRATION_AUTHORIZATION_CONFIRMATION = "AUTHORIZE_FROZEN_CALIBRATION_ONLY"
EXPECTED_CELL_COUNT = 144
EXPECTED_TASKS_PER_CELL = 20


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256_value(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_atomic_json(path: Path, document: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _full_commit(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{40}", value))


def _full_digest(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", value))


def authorization_sha256(record: Mapping[str, Any]) -> str:
    """Hash the exact canonical authorization record."""
    return _sha256_value(dict(record))


def build_authorization_record(
    *,
    execution_commit: str,
    authorized_by: str,
    authorized_on: str,
    confirmation: str,
) -> Dict[str, Any]:
    """Materialize, but do not persist, one calibration-only authorization."""
    if confirmation != CALIBRATION_AUTHORIZATION_CONFIRMATION:
        raise PermissionError("Exact calibration authorization confirmation required")
    instance = load_calibration_instance()
    record = {
        "authorization_schema_version": AUTHORIZATION_SCHEMA_VERSION,
        "instance_id": instance["instance_id"],
        "instance_sha256": instance_sha256(instance),
        "execution_commit": execution_commit,
        "authorized_split": "calibration",
        "calibration_execution_authorized": True,
        "verification_execution_authorized": False,
        "protected_holdout_execution_authorized": False,
        "retuning_after_authorization": False,
        "authorized_by": authorized_by,
        "authorized_on": authorized_on,
    }
    validate_execution_authorization(record, execution_commit=execution_commit)
    return record


def load_and_validate_authorization(
    path: Path,
    *,
    expected_sha256: str,
    execution_commit: str,
    confirmation: str,
) -> Dict[str, Any]:
    """Load an immutable external authorization and bind it to this run."""
    if confirmation != CALIBRATION_AUTHORIZATION_CONFIRMATION:
        raise PermissionError("Exact calibration authorization confirmation required")
    if not _full_digest(expected_sha256):
        raise PermissionError("Authorization SHA-256 must be 64 lowercase hex characters")
    try:
        record = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PermissionError("Authorization record is unreadable") from error
    if not isinstance(record, dict):
        raise PermissionError("Authorization record must be a JSON object")
    if authorization_sha256(record) != expected_sha256:
        raise PermissionError("Authorization record SHA-256 mismatch")
    validate_execution_authorization(record, execution_commit=execution_commit)
    return record


def _cell_id(policy_id: str, family: str, scale: int) -> str:
    return f"{policy_id}__{family}__N{scale}"


def build_cell_plan(execution_commit: str) -> List[Dict[str, Any]]:
    """Return the exact 144 complete candidate-family-scale cells."""
    if not _full_commit(execution_commit):
        raise ValueError("Cell planning requires a full execution commit")
    tasks = build_task_plan(
        "calibration",
        execution_commit=execution_commit,
        planning_only=False,
    )
    grouped: Dict[tuple[str, str, int], List[CalibrationTask]] = {}
    for task in tasks:
        grouped.setdefault((task.policy_id, task.family, task.scale), []).append(task)
    cells = []
    for cell_index, ((policy_id, family, scale), cell_tasks) in enumerate(
        grouped.items()
    ):
        task_records = [task.to_dict() for task in cell_tasks]
        cells.append(
            {
                "cell_index": cell_index,
                "cell_id": _cell_id(policy_id, family, scale),
                "policy_id": policy_id,
                "family": family,
                "scale": scale,
                "task_count": len(cell_tasks),
                "first_run_id": cell_tasks[0].run_id,
                "last_run_id": cell_tasks[-1].run_id,
                "task_sha256": _sha256_value(task_records),
            }
        )
    if len(cells) != EXPECTED_CELL_COUNT:
        raise RuntimeError(f"Expected {EXPECTED_CELL_COUNT} cells, got {len(cells)}")
    if any(cell["task_count"] != EXPECTED_TASKS_PER_CELL for cell in cells):
        raise RuntimeError("Every execution cell must contain exactly 20 tasks")
    return cells


def cell_matrix(execution_commit: str) -> Dict[str, Any]:
    """Emit the GitHub matrix without constructing a domain."""
    return {"include": build_cell_plan(execution_commit)}


def tasks_for_cell(execution_commit: str, cell_index: int) -> List[CalibrationTask]:
    cells = build_cell_plan(execution_commit)
    if not 0 <= cell_index < len(cells):
        raise ValueError(f"Cell index must be in [0,{len(cells) - 1}]")
    cell = cells[cell_index]
    tasks = [
        task
        for task in build_task_plan(
            "calibration",
            execution_commit=execution_commit,
            planning_only=False,
        )
        if (
            task.policy_id == cell["policy_id"]
            and task.family == cell["family"]
            and task.scale == cell["scale"]
        )
    ]
    if _sha256_value([task.to_dict() for task in tasks]) != cell["task_sha256"]:
        raise RuntimeError("Cell task digest differs from the frozen matrix")
    return tasks


def _cell_manifest(
    *,
    cell: Mapping[str, Any],
    run_attempt: int,
    authorization_digest: str,
    output_dir: Path,
    summary: Mapping[str, int],
) -> Dict[str, Any]:
    shards_dir = output_dir / "shards"
    failures_dir = output_dir / "failures"
    shard_hashes = {
        path.name: _sha256_file(path)
        for path in sorted(shards_dir.glob("*.json"))
    }
    failure_hashes = {
        path.name: _sha256_file(path)
        for path in sorted(failures_dir.glob("*.json"))
    }
    complete = (
        summary["completed"] == EXPECTED_TASKS_PER_CELL
        and summary["infrastructure_failures"] == 0
        and len(shard_hashes) == EXPECTED_TASKS_PER_CELL
    )
    manifest = {
        "cell_artifact_schema_version": CELL_ARTIFACT_SCHEMA_VERSION,
        "artifact_kind": "override_gate_calibration_cell",
        "cell_index": int(cell["cell_index"]),
        "cell_id": str(cell["cell_id"]),
        "policy_id": str(cell["policy_id"]),
        "family": str(cell["family"]),
        "scale": int(cell["scale"]),
        "task_count": int(cell["task_count"]),
        "task_sha256": str(cell["task_sha256"]),
        "run_attempt": run_attempt,
        "instance_sha256": instance_sha256(),
        "source_commit": load_calibration_instance()["source_commit"],
        "execution_commit": cell.get("execution_commit"),
        "authorization_sha256": authorization_digest,
        "status": "complete" if complete else "infrastructure_failure",
        "summary": dict(summary),
        "shard_files": shard_hashes,
        "failure_files": failure_hashes,
        "holdout_accessed": False,
        "not_gate_result": True,
    }
    manifest["cell_manifest_sha256"] = _sha256_value(manifest)
    return manifest


def run_cell(
    *,
    output_dir: Path,
    cell_index: int,
    execution_commit: str,
    authorization: Mapping[str, Any],
    authorization_digest: str,
    confirmation: str,
    workers: int,
    run_attempt: int,
) -> Dict[str, Any]:
    """Execute exactly one complete authorized calibration cell."""
    if confirmation != CALIBRATION_AUTHORIZATION_CONFIRMATION:
        raise PermissionError("Exact calibration authorization confirmation required")
    if run_attempt <= 0:
        raise ValueError("run_attempt must be positive")
    validate_execution_authorization(authorization, execution_commit=execution_commit)
    if authorization_sha256(authorization) != authorization_digest:
        raise PermissionError("Authorization digest changed before cell execution")
    cells = build_cell_plan(execution_commit)
    if not 0 <= cell_index < len(cells):
        raise ValueError(f"Cell index must be in [0,{len(cells) - 1}]")
    cell = dict(cells[cell_index])
    cell["execution_commit"] = execution_commit
    output = Path(output_dir)
    summary = execute_task_set(
        tasks_for_cell(execution_commit, cell_index),
        output,
        authorization=authorization,
        workers=workers,
    )
    manifest = _cell_manifest(
        cell=cell,
        run_attempt=run_attempt,
        authorization_digest=authorization_digest,
        output_dir=output,
        summary=summary,
    )
    _write_atomic_json(output / "cell_manifest.json", manifest)
    return manifest


def validate_cell_manifest(
    manifest: Mapping[str, Any],
    *,
    expected_cell: Mapping[str, Any],
    execution_commit: str,
    authorization_digest: str,
) -> None:
    payload = dict(manifest)
    recorded = payload.pop("cell_manifest_sha256", None)
    if recorded != _sha256_value(payload):
        raise ValueError("Cell manifest digest mismatch")
    expected = {
        "cell_artifact_schema_version": CELL_ARTIFACT_SCHEMA_VERSION,
        "artifact_kind": "override_gate_calibration_cell",
        "cell_index": expected_cell["cell_index"],
        "cell_id": expected_cell["cell_id"],
        "policy_id": expected_cell["policy_id"],
        "family": expected_cell["family"],
        "scale": expected_cell["scale"],
        "task_count": EXPECTED_TASKS_PER_CELL,
        "task_sha256": expected_cell["task_sha256"],
        "instance_sha256": instance_sha256(),
        "source_commit": load_calibration_instance()["source_commit"],
        "execution_commit": execution_commit,
        "authorization_sha256": authorization_digest,
        "holdout_accessed": False,
        "not_gate_result": True,
    }
    for field, value in expected.items():
        if manifest.get(field) != value:
            raise ValueError(f"Cell manifest {field} mismatch")
    if not isinstance(manifest.get("run_attempt"), int) or manifest["run_attempt"] <= 0:
        raise ValueError("Cell manifest run_attempt must be positive")
    if manifest.get("status") not in {"complete", "infrastructure_failure"}:
        raise ValueError("Cell manifest status is invalid")
    summary = manifest.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("Cell manifest summary must be an object")
    for field in ("planned", "completed", "resumed", "infrastructure_failures"):
        value = summary.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"Cell manifest summary {field} must be nonnegative integer")
    if summary["planned"] != EXPECTED_TASKS_PER_CELL:
        raise ValueError("Cell manifest planned count must be 20")
    if summary["completed"] > EXPECTED_TASKS_PER_CELL:
        raise ValueError("Cell manifest completed count exceeds 20")
    for inventory_name in ("shard_files", "failure_files"):
        inventory = manifest.get(inventory_name)
        if not isinstance(inventory, dict):
            raise ValueError(f"Cell manifest {inventory_name} must be an object")
        for name, digest in inventory.items():
            if Path(name).name != name or not _full_digest(str(digest)):
                raise ValueError(f"Cell manifest {inventory_name} entry is invalid")
    if manifest["status"] == "complete":
        if summary["completed"] != EXPECTED_TASKS_PER_CELL:
            raise ValueError("Complete cell must contain 20 completed tasks")
        if summary["infrastructure_failures"] != 0:
            raise ValueError("Complete cell cannot contain infrastructure failures")
        if len(manifest["shard_files"]) != EXPECTED_TASKS_PER_CELL:
            raise ValueError("Complete cell must inventory 20 shards")
    elif summary["infrastructure_failures"] <= 0:
        raise ValueError("Infrastructure-failure cell must retain a failure count")


def _validate_cell_file_inventory(
    manifest: Mapping[str, Any],
    artifact_dir: Path,
) -> None:
    for inventory_name, directory_name in (
        ("shard_files", "shards"),
        ("failure_files", "failures"),
    ):
        declared = manifest[inventory_name]
        directory = artifact_dir / directory_name
        actual = {
            path.name: _sha256_file(path)
            for path in sorted(directory.glob("*.json"))
        }
        if actual != declared:
            raise ValueError(f"Cell {manifest['cell_index']} {inventory_name} mismatch")


def select_latest_cell_attempts(
    manifests: Sequence[Mapping[str, Any]],
    *,
    expected_cell_count: int = EXPECTED_CELL_COUNT,
) -> Dict[int, Mapping[str, Any]]:
    """Choose the highest run attempt per cell; never fall back after failure."""
    selected: Dict[int, Mapping[str, Any]] = {}
    seen_attempts = set()
    for manifest in manifests:
        cell_index = int(manifest["cell_index"])
        attempt = int(manifest["run_attempt"])
        identity = (cell_index, attempt)
        if identity in seen_attempts:
            raise ValueError(f"Duplicate cell attempt {identity}")
        seen_attempts.add(identity)
        current = selected.get(cell_index)
        if current is None or attempt > int(current["run_attempt"]):
            selected[cell_index] = manifest
    if set(selected) != set(range(expected_cell_count)):
        raise ValueError(
            f"Expected latest attempts for {expected_cell_count} cells, got {len(selected)}"
        )
    return selected


def _load_manifest(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Unreadable cell manifest: {path}") from error
    if not isinstance(value, dict):
        raise ValueError(f"Cell manifest is not an object: {path}")
    value["_artifact_dir"] = str(path.parent)
    return value


def merge_cell_artifacts(
    *,
    input_dir: Path,
    output_dir: Path,
    execution_commit: str,
    authorization_digest: str,
) -> Dict[str, Any]:
    """Select latest attempts and merge only a complete 144-cell matrix."""
    cells = build_cell_plan(execution_commit)
    manifests = [_load_manifest(path) for path in Path(input_dir).rglob("cell_manifest.json")]
    for manifest in manifests:
        cell_index = int(manifest.get("cell_index", -1))
        if not 0 <= cell_index < len(cells):
            raise ValueError(f"Cell manifest index is out of range: {cell_index}")
        clean_manifest = {
            key: value for key, value in manifest.items() if key != "_artifact_dir"
        }
        validate_cell_manifest(
            clean_manifest,
            expected_cell=cells[cell_index],
            execution_commit=execution_commit,
            authorization_digest=authorization_digest,
        )
        _validate_cell_file_inventory(clean_manifest, Path(str(manifest["_artifact_dir"])))
    selected = select_latest_cell_attempts(
        manifests,
        expected_cell_count=len(cells),
    )
    output = Path(output_dir)
    shards_output = output / "shards"
    if shards_output.exists() and any(shards_output.iterdir()):
        raise ValueError("Distributed merge output already contains shards")
    shards_output.mkdir(parents=True, exist_ok=True)
    selected_attempts = {}
    for cell_index, cell in enumerate(cells):
        manifest = selected[cell_index]
        artifact_dir = Path(str(manifest["_artifact_dir"]))
        clean_manifest = {key: value for key, value in manifest.items() if key != "_artifact_dir"}
        validate_cell_manifest(
            clean_manifest,
            expected_cell=cell,
            execution_commit=execution_commit,
            authorization_digest=authorization_digest,
        )
        if clean_manifest["status"] != "complete":
            raise RuntimeError(
                f"Latest attempt for cell {cell_index} is not complete"
            )
        _validate_cell_file_inventory(clean_manifest, artifact_dir)
        tasks = tasks_for_cell(execution_commit, cell_index)
        if len(tasks) != EXPECTED_TASKS_PER_CELL:
            raise RuntimeError(f"Cell {cell_index} does not contain exactly 20 tasks")
        expected_names = {task.shard_name for task in tasks}
        if set(clean_manifest["shard_files"]) != expected_names:
            raise ValueError(f"Cell {cell_index} shard inventory is incomplete")
        for task in tasks:
            source = artifact_dir / "shards" / task.shard_name
            if _sha256_file(source) != clean_manifest["shard_files"][task.shard_name]:
                raise ValueError(f"Cell {cell_index} shard file digest mismatch")
            if load_calibration_shard(source, task) is None:
                raise ValueError(f"Cell {cell_index} contains an invalid shard")
            shutil.copy2(source, shards_output / task.shard_name)
        selected_attempts[str(cell_index)] = int(clean_manifest["run_attempt"])

    for manifest in manifests:
        artifact_dir = Path(str(manifest["_artifact_dir"]))
        cell_index = int(manifest["cell_index"])
        attempt = int(manifest["run_attempt"])
        for failure in (artifact_dir / "failures").glob("*.json"):
            destination = output / "failures" / f"cell-{cell_index:03d}" / f"attempt-{attempt}"
            destination.mkdir(parents=True, exist_ok=True)
            shutil.copy2(failure, destination / failure.name)

    merge_manifest = {
        "distributed_merge_schema_version": DISTRIBUTED_MERGE_SCHEMA_VERSION,
        "artifact_kind": "override_gate_calibration_distributed_merge",
        "instance_sha256": instance_sha256(),
        "source_commit": load_calibration_instance()["source_commit"],
        "execution_commit": execution_commit,
        "authorization_sha256": authorization_digest,
        "cell_count": len(cells),
        "task_shard_count": len(list(shards_output.glob("*.json"))),
        "selected_attempts": selected_attempts,
        "calibration_executed": True,
        "verification_executed": False,
        "protected_holdout_accessed": False,
        "not_gate_result": True,
    }
    if merge_manifest["task_shard_count"] != len(cells) * EXPECTED_TASKS_PER_CELL:
        raise RuntimeError("Merged shard count differs from the complete cell matrix")
    merge_manifest["merge_manifest_sha256"] = _sha256_value(merge_manifest)
    _write_atomic_json(output / "distributed_merge_manifest.json", merge_manifest)
    return merge_manifest


def _authorization_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--authorization-sha256", required=True)
    parser.add_argument("--execution-commit", required=True)
    parser.add_argument("--confirmation", required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    matrix = subparsers.add_parser("matrix")
    matrix.add_argument("--execution-commit", required=True)

    template = subparsers.add_parser("authorization-template")
    template.add_argument("--execution-commit", required=True)
    template.add_argument("--authorized-by", required=True)
    template.add_argument("--authorized-on", required=True)
    template.add_argument("--confirmation", required=True)
    template.add_argument("--output", type=Path)

    validate = subparsers.add_parser("validate-authorization")
    _authorization_arguments(validate)

    run = subparsers.add_parser("run-cell")
    _authorization_arguments(run)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--cell-index", type=int, required=True)
    run.add_argument("--workers", type=int, default=4)
    run.add_argument("--run-attempt", type=int, required=True)

    consolidate = subparsers.add_parser("consolidate")
    _authorization_arguments(consolidate)
    consolidate.add_argument("--input", type=Path, required=True)
    consolidate.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "matrix":
            result = cell_matrix(args.execution_commit)
        elif args.command == "authorization-template":
            record = build_authorization_record(
                execution_commit=args.execution_commit,
                authorized_by=args.authorized_by,
                authorized_on=args.authorized_on,
                confirmation=args.confirmation,
            )
            result = {
                "authorization": record,
                "authorization_sha256": authorization_sha256(record),
            }
            if args.output is not None:
                _write_atomic_json(args.output, record)
        else:
            authorization = load_and_validate_authorization(
                args.authorization,
                expected_sha256=args.authorization_sha256,
                execution_commit=args.execution_commit,
                confirmation=args.confirmation,
            )
            if args.command == "validate-authorization":
                result = {
                    "authorization_valid": True,
                    "authorization_sha256": args.authorization_sha256,
                    "execution_commit": args.execution_commit,
                    "authorized_split": "calibration",
                    "verification_execution_authorized": False,
                    "protected_holdout_execution_authorized": False,
                }
            elif args.command == "run-cell":
                result = run_cell(
                    output_dir=args.output,
                    cell_index=args.cell_index,
                    execution_commit=args.execution_commit,
                    authorization=authorization,
                    authorization_digest=args.authorization_sha256,
                    confirmation=args.confirmation,
                    workers=args.workers,
                    run_attempt=args.run_attempt,
                )
            else:
                merge = merge_cell_artifacts(
                    input_dir=args.input,
                    output_dir=args.output,
                    execution_commit=args.execution_commit,
                    authorization_digest=args.authorization_sha256,
                )
                evidence = consolidate_calibration(
                    args.output,
                    execution_commit=args.execution_commit,
                )
                result = {"merge": merge, "evidence": evidence}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        if result.get("status") == "infrastructure_failure":
            return 3
        return 0
    except (OSError, PermissionError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
