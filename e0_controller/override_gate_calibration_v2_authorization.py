"""Fail-closed external authorization boundary for override-gate v2.

WP-GATE-0.14 implements review templates and validation only.  It exposes no
domain builder and no outcome command.  A valid record additionally requires a
future execution manifest and the exact outcome-workflow file, so the current
repository state cannot yet be authorized accidentally.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from .override_gate_calibration_v2 import instance_sha256, load_calibration_instance_v2

AUTHORIZATION_SCHEMA_VERSION = 2
EXECUTION_MANIFEST_SCHEMA_VERSION = 1
REVIEW_TEMPLATE_SCHEMA_VERSION = 1
AUTHORIZATION_CONFIRMATION = "AUTHORIZE_E0_OVERRIDE_GATE_V2_CALIBRATION_ONLY"
WP_GATE_0_13_EVIDENCE_SHA256 = (
    "467de7f261a9b8feaac2a212fbce9acec68c8a36cc09654c0d2f2cfcf0293ba2"
)
PROTOCOL_PATH = (
    Path(__file__).resolve().parent.parent
    / "docs"
    / "E0_OVERRIDE_GATE_CALIBRATION_PROTOCOL_v2.json"
)
EXPECTED_STAGE_B_CELL_COUNT = 144
EXPECTED_STAGE_A_CELL_COUNT = 132
EXPECTED_CALIBRATION_SEEDS = tuple(range(5000, 5020))

AUTHORIZATION_FIELDS = frozenset(
    {
        "authorization_schema_version",
        "artifact_kind",
        "instance_id",
        "instance_sha256",
        "protocol_id",
        "protocol_file_sha256",
        "source_commit",
        "execution_commit",
        "execution_manifest_sha256",
        "outcome_workflow_sha256",
        "reviewed_no_outcome_evidence_sha256",
        "authorized_split",
        "stage_a_execution_authorized",
        "stage_b_execution_authorized",
        "calibration_execution_authorized",
        "verification_execution_authorized",
        "protected_holdout_execution_authorized",
        "protected_holdout_accessed",
        "retuning_after_authorization",
        "candidate_removal_after_authorization",
        "latest_attempt_only",
        "fallback_to_earlier_attempt",
        "authorized_by",
        "authorized_on",
        "authorization_reason",
        "human_confirmation",
        "not_gate_result",
    }
)

EXECUTION_MANIFEST_FIELDS = frozenset(
    {
        "execution_manifest_schema_version",
        "artifact_kind",
        "instance_id",
        "instance_sha256",
        "protocol_id",
        "protocol_file_sha256",
        "source_commit",
        "execution_commit",
        "outcome_workflow_sha256",
        "authorized_split",
        "stage_b_cell_count",
        "stage_a_cell_count",
        "calibration_generator_seeds",
        "stage_separated",
        "branch_time_charged_to_parent",
        "latest_attempt_only",
        "fallback_to_earlier_attempt",
        "implementation_complete",
        "tests_passed",
        "verification_execution_enabled",
        "protected_holdout_execution_enabled",
        "protected_holdout_accessed",
        "not_gate_result",
    }
)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _sha256_value(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def protocol_file_sha256() -> str:
    return sha256_file(PROTOCOL_PATH)


def authorization_sha256(record: Mapping[str, Any]) -> str:
    """Hash the exact canonical record; formatting is intentionally irrelevant."""
    return _sha256_value(dict(record))


def _full_commit(value: Any) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{40}", str(value)))


def _full_digest(value: Any) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", str(value)))


def _load_json_object(path: Path, label: str) -> Dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PermissionError(f"{label} is unreadable") from error
    if not isinstance(value, dict):
        raise PermissionError(f"{label} must be a JSON object")
    return value


def validate_execution_manifest(
    manifest: Mapping[str, Any],
    *,
    execution_commit: str,
    outcome_workflow_sha256: str,
    instance: Optional[Mapping[str, Any]] = None,
) -> None:
    """Require a complete calibration-only future execution declaration."""
    document = load_calibration_instance_v2() if instance is None else instance
    if set(manifest) != EXECUTION_MANIFEST_FIELDS:
        missing = sorted(EXECUTION_MANIFEST_FIELDS.difference(manifest))
        extra = sorted(set(manifest).difference(EXECUTION_MANIFEST_FIELDS))
        raise PermissionError(
            f"Execution manifest fields differ; missing={missing}, extra={extra}"
        )
    expected = {
        "execution_manifest_schema_version": EXECUTION_MANIFEST_SCHEMA_VERSION,
        "artifact_kind": "override_gate_v2_execution_manifest",
        "instance_id": document["instance_id"],
        "instance_sha256": instance_sha256(document),
        "protocol_id": document["protocol_id"],
        "protocol_file_sha256": protocol_file_sha256(),
        "source_commit": document["source_commit"],
        "execution_commit": execution_commit,
        "outcome_workflow_sha256": outcome_workflow_sha256,
        "authorized_split": "calibration",
        "stage_b_cell_count": EXPECTED_STAGE_B_CELL_COUNT,
        "stage_a_cell_count": EXPECTED_STAGE_A_CELL_COUNT,
        "calibration_generator_seeds": list(EXPECTED_CALIBRATION_SEEDS),
        "stage_separated": True,
        "branch_time_charged_to_parent": False,
        "latest_attempt_only": True,
        "fallback_to_earlier_attempt": False,
        "implementation_complete": True,
        "tests_passed": True,
        "verification_execution_enabled": False,
        "protected_holdout_execution_enabled": False,
        "protected_holdout_accessed": False,
        "not_gate_result": True,
    }
    for field, value in expected.items():
        if manifest.get(field) != value:
            raise PermissionError(f"Invalid execution manifest field {field}")
    if not _full_commit(execution_commit):
        raise PermissionError("Execution manifest requires a full commit")
    if not _full_digest(outcome_workflow_sha256):
        raise PermissionError("Outcome workflow requires a full SHA-256")


def validate_authorization_record(
    record: Mapping[str, Any],
    *,
    expected_sha256: str,
    execution_commit: str,
    execution_manifest_path: Path,
    outcome_workflow_path: Path,
    confirmation: str,
    instance: Optional[Mapping[str, Any]] = None,
) -> None:
    """Bind an external authorization to exact code, workflow, and manifest."""
    if confirmation != AUTHORIZATION_CONFIRMATION:
        raise PermissionError("Exact v2 calibration confirmation required")
    if not _full_digest(expected_sha256):
        raise PermissionError("Authorization SHA-256 must be lowercase full hex")
    if not _full_commit(execution_commit):
        raise PermissionError("Authorization requires a full execution commit")
    if set(record) != AUTHORIZATION_FIELDS:
        missing = sorted(AUTHORIZATION_FIELDS.difference(record))
        extra = sorted(set(record).difference(AUTHORIZATION_FIELDS))
        raise PermissionError(
            f"Authorization fields differ; missing={missing}, extra={extra}"
        )
    if authorization_sha256(record) != expected_sha256:
        raise PermissionError("Authorization record SHA-256 mismatch")

    document = load_calibration_instance_v2() if instance is None else instance
    workflow_digest = sha256_file(outcome_workflow_path)
    manifest_digest = sha256_file(execution_manifest_path)
    manifest = _load_json_object(execution_manifest_path, "Execution manifest")
    validate_execution_manifest(
        manifest,
        execution_commit=execution_commit,
        outcome_workflow_sha256=workflow_digest,
        instance=document,
    )
    expected = {
        "authorization_schema_version": AUTHORIZATION_SCHEMA_VERSION,
        "artifact_kind": "override_gate_v2_external_calibration_authorization",
        "instance_id": document["instance_id"],
        "instance_sha256": instance_sha256(document),
        "protocol_id": document["protocol_id"],
        "protocol_file_sha256": protocol_file_sha256(),
        "source_commit": document["source_commit"],
        "execution_commit": execution_commit,
        "execution_manifest_sha256": manifest_digest,
        "outcome_workflow_sha256": workflow_digest,
        "reviewed_no_outcome_evidence_sha256": WP_GATE_0_13_EVIDENCE_SHA256,
        "authorized_split": "calibration",
        "stage_a_execution_authorized": True,
        "stage_b_execution_authorized": True,
        "calibration_execution_authorized": True,
        "verification_execution_authorized": False,
        "protected_holdout_execution_authorized": False,
        "protected_holdout_accessed": False,
        "retuning_after_authorization": False,
        "candidate_removal_after_authorization": False,
        "latest_attempt_only": True,
        "fallback_to_earlier_attempt": False,
        "human_confirmation": AUTHORIZATION_CONFIRMATION,
        "not_gate_result": True,
    }
    for field, value in expected.items():
        if record.get(field) != value:
            raise PermissionError(f"Invalid calibration authorization field {field}")
    for field in ("authorized_by", "authorization_reason"):
        if not isinstance(record.get(field), str) or not record[field].strip():
            raise PermissionError(f"Authorization requires non-empty {field}")
        if record[field].startswith("__"):
            raise PermissionError(f"Authorization placeholder remains in {field}")
    try:
        date.fromisoformat(str(record["authorized_on"]))
    except ValueError as error:
        raise PermissionError("authorized_on must be an ISO calendar date") from error


def load_and_validate_authorization(
    path: Path,
    **validation_arguments: Any,
) -> Dict[str, Any]:
    record = _load_json_object(path, "Authorization record")
    validate_authorization_record(record, **validation_arguments)
    return record


def build_review_template() -> Dict[str, Any]:
    """Return a deliberately non-operational external review template."""
    instance = load_calibration_instance_v2()
    fields = {
        "authorization_schema_version": AUTHORIZATION_SCHEMA_VERSION,
        "artifact_kind": "override_gate_v2_external_calibration_authorization",
        "instance_id": instance["instance_id"],
        "instance_sha256": instance_sha256(instance),
        "protocol_id": instance["protocol_id"],
        "protocol_file_sha256": protocol_file_sha256(),
        "source_commit": instance["source_commit"],
        "execution_commit": "__FULL_EXECUTION_COMMIT_REQUIRED__",
        "execution_manifest_sha256": "__EXECUTION_MANIFEST_SHA256_REQUIRED__",
        "outcome_workflow_sha256": "__OUTCOME_WORKFLOW_SHA256_REQUIRED__",
        "reviewed_no_outcome_evidence_sha256": WP_GATE_0_13_EVIDENCE_SHA256,
        "authorized_split": "calibration",
        "stage_a_execution_authorized": True,
        "stage_b_execution_authorized": True,
        "calibration_execution_authorized": True,
        "verification_execution_authorized": False,
        "protected_holdout_execution_authorized": False,
        "protected_holdout_accessed": False,
        "retuning_after_authorization": False,
        "candidate_removal_after_authorization": False,
        "latest_attempt_only": True,
        "fallback_to_earlier_attempt": False,
        "authorized_by": "__EXTERNAL_AUTHORIZER_REQUIRED__",
        "authorized_on": "__YYYY-MM-DD_REQUIRED__",
        "authorization_reason": "__EXTERNAL_REVIEW_REASON_REQUIRED__",
        "human_confirmation": AUTHORIZATION_CONFIRMATION,
        "not_gate_result": True,
    }
    return {
        "review_template_schema_version": REVIEW_TEMPLATE_SCHEMA_VERSION,
        "artifact_kind": "override_gate_v2_authorization_review_template",
        "operational_authorization_record": False,
        "template_fields": fields,
        "canonical_digest_rule": "sha256(canonical-json(record))",
        "required_external_confirmation": AUTHORIZATION_CONFIRMATION,
        "execution_manifest_required": True,
        "outcome_workflow_file_required": True,
        "calibration_executed": False,
        "verification_executed": False,
        "protected_holdout_accessed": False,
        "holdout_accessed": False,
        "not_gate_result": True,
    }


def build_no_outcome_review() -> Dict[str, Any]:
    template = build_review_template()
    return {
        "artifact_kind": "override_gate_v2_authorization_boundary_dry_run",
        "work_package": "WP-GATE-0.14",
        "preauthorization_baseline_commit": (
            "d279f587bb8ad2d4e8a3235a472c4ccb4b802781"
        ),
        "review_template_sha256": _sha256_value(template),
        "authorization_validator_implemented": True,
        "operational_authorization_record_present": False,
        "execution_manifest_present": False,
        "outcome_workflow_present": False,
        "authorization_request_ready": False,
        "fresh_split_builders_exposed": False,
        "outcome_commands_exposed": False,
        "domains_instantiated": 0,
        "outcomes_observed": 0,
        "execution_commit_frozen": False,
        "calibration_executed": False,
        "verification_executed": False,
        "protected_holdout_accessed": False,
        "holdout_accessed": False,
        "not_gate_result": True,
    }


def _write_atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    template = subparsers.add_parser("review-template")
    template.add_argument("--output", type=Path, required=True)
    dry_run = subparsers.add_parser("dry-run")
    dry_run.add_argument("--output", type=Path, required=True)
    validate = subparsers.add_parser("validate-authorization")
    validate.add_argument("--authorization", type=Path, required=True)
    validate.add_argument("--authorization-sha256", required=True)
    validate.add_argument("--execution-commit", required=True)
    validate.add_argument("--execution-manifest", type=Path, required=True)
    validate.add_argument("--outcome-workflow", type=Path, required=True)
    validate.add_argument("--confirmation", required=True)
    validate.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        if args.command == "review-template":
            result = build_review_template()
        elif args.command == "dry-run":
            result = build_no_outcome_review()
        else:
            record = load_and_validate_authorization(
                args.authorization,
                expected_sha256=args.authorization_sha256,
                execution_commit=args.execution_commit,
                execution_manifest_path=args.execution_manifest,
                outcome_workflow_path=args.outcome_workflow,
                confirmation=args.confirmation,
            )
            result = {
                "authorization_valid": True,
                "authorization_sha256": authorization_sha256(record),
                "execution_commit": args.execution_commit,
                "authorized_split": "calibration",
                "verification_execution_authorized": False,
                "protected_holdout_execution_authorized": False,
                "not_gate_result": True,
            }
        _write_atomic_json(args.output, result)
        return 0
    except (OSError, PermissionError, ValueError) as error:
        print(f"ERROR: {error}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
