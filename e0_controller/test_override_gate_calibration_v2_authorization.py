"""Fail-closed authorization tests for WP-GATE-0.14."""

from __future__ import annotations

import copy
import json

import pytest

from .override_gate_calibration_v2 import instance_sha256, load_calibration_instance_v2
from .override_gate_calibration_v2_authorization import (
    AUTHORIZATION_CONFIRMATION,
    AUTHORIZATION_SCHEMA_VERSION,
    EXECUTION_MANIFEST_SCHEMA_VERSION,
    EXPECTED_CALIBRATION_SEEDS,
    EXPECTED_STAGE_A_CELL_COUNT,
    EXPECTED_STAGE_B_CELL_COUNT,
    WP_GATE_0_13_EVIDENCE_SHA256,
    authorization_sha256,
    build_no_outcome_review,
    build_review_template,
    load_and_validate_authorization,
    main,
    protocol_file_sha256,
    sha256_file,
    validate_authorization_record,
    validate_execution_manifest,
)

EXECUTION_COMMIT = "a" * 40


def _bundle(tmp_path):
    instance = load_calibration_instance_v2()
    workflow = tmp_path / "execute.yml"
    workflow.write_text("name: exact future outcome workflow\n", encoding="utf-8")
    workflow_digest = sha256_file(workflow)
    manifest = {
        "execution_manifest_schema_version": EXECUTION_MANIFEST_SCHEMA_VERSION,
        "artifact_kind": "override_gate_v2_execution_manifest",
        "instance_id": instance["instance_id"],
        "instance_sha256": instance_sha256(instance),
        "protocol_id": instance["protocol_id"],
        "protocol_file_sha256": protocol_file_sha256(),
        "source_commit": instance["source_commit"],
        "execution_commit": EXECUTION_COMMIT,
        "outcome_workflow_sha256": workflow_digest,
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
    manifest_path = tmp_path / "execution-manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    record = {
        "authorization_schema_version": AUTHORIZATION_SCHEMA_VERSION,
        "artifact_kind": "override_gate_v2_external_calibration_authorization",
        "instance_id": instance["instance_id"],
        "instance_sha256": instance_sha256(instance),
        "protocol_id": instance["protocol_id"],
        "protocol_file_sha256": protocol_file_sha256(),
        "source_commit": instance["source_commit"],
        "execution_commit": EXECUTION_COMMIT,
        "execution_manifest_sha256": sha256_file(manifest_path),
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
        "authorized_by": "external-reviewer",
        "authorized_on": "2026-08-04",
        "authorization_reason": "Reviewed the frozen calibration-only bundle.",
        "human_confirmation": AUTHORIZATION_CONFIRMATION,
        "not_gate_result": True,
    }
    return record, manifest, manifest_path, workflow


def _validate(record, manifest_path, workflow, **changes):
    arguments = {
        "expected_sha256": authorization_sha256(record),
        "execution_commit": EXECUTION_COMMIT,
        "execution_manifest_path": manifest_path,
        "outcome_workflow_path": workflow,
        "confirmation": AUTHORIZATION_CONFIRMATION,
    }
    arguments.update(changes)
    validate_authorization_record(record, **arguments)


def test_review_template_is_deliberately_non_operational():
    template = build_review_template()
    assert template["operational_authorization_record"] is False
    assert template["template_fields"]["execution_commit"].startswith("__")
    assert template["calibration_executed"] is False
    assert template["protected_holdout_accessed"] is False
    assert template["not_gate_result"] is True


def test_no_outcome_review_records_current_boundary():
    review = build_no_outcome_review()
    assert review["authorization_validator_implemented"] is True
    assert review["authorization_request_ready"] is False
    assert review["execution_manifest_present"] is False
    assert review["outcome_workflow_present"] is False
    assert review["domains_instantiated"] == 0
    assert review["outcomes_observed"] == 0


def test_complete_external_bundle_validates(tmp_path):
    record, _, manifest_path, workflow = _bundle(tmp_path)
    _validate(record, manifest_path, workflow)


def test_authorization_digest_is_format_independent_but_content_bound(tmp_path):
    record, _, manifest_path, workflow = _bundle(tmp_path)
    path = tmp_path / "authorization.json"
    path.write_text(json.dumps(record, indent=4), encoding="utf-8")
    loaded = load_and_validate_authorization(
        path,
        expected_sha256=authorization_sha256(record),
        execution_commit=EXECUTION_COMMIT,
        execution_manifest_path=manifest_path,
        outcome_workflow_path=workflow,
        confirmation=AUTHORIZATION_CONFIRMATION,
    )
    assert loaded == record
    changed = copy.deepcopy(record)
    changed["authorization_reason"] += " changed"
    with pytest.raises(PermissionError, match="SHA-256 mismatch"):
        validate_authorization_record(
            changed,
            expected_sha256=authorization_sha256(record),
            execution_commit=EXECUTION_COMMIT,
            execution_manifest_path=manifest_path,
            outcome_workflow_path=workflow,
            confirmation=AUTHORIZATION_CONFIRMATION,
        )


def test_confirmation_is_required_in_both_channels(tmp_path):
    record, _, manifest_path, workflow = _bundle(tmp_path)
    with pytest.raises(PermissionError, match="Exact v2"):
        _validate(record, manifest_path, workflow, confirmation="yes")
    record["human_confirmation"] = "yes"
    with pytest.raises(PermissionError, match="human_confirmation"):
        _validate(record, manifest_path, workflow)


def test_execution_commit_is_exactly_bound(tmp_path):
    record, _, manifest_path, workflow = _bundle(tmp_path)
    with pytest.raises(PermissionError, match="execution_commit"):
        _validate(record, manifest_path, workflow, execution_commit="b" * 40)
    with pytest.raises(PermissionError, match="full execution commit"):
        _validate(record, manifest_path, workflow, execution_commit="short")


def test_changed_workflow_invalidates_manifest_and_authorization(tmp_path):
    record, _, manifest_path, workflow = _bundle(tmp_path)
    workflow.write_text("name: modified workflow\n", encoding="utf-8")
    with pytest.raises(PermissionError, match="outcome_workflow_sha256"):
        _validate(record, manifest_path, workflow)


def test_changed_execution_manifest_digest_is_rejected(tmp_path):
    record, manifest, manifest_path, workflow = _bundle(tmp_path)
    manifest["tests_passed"] = False
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(PermissionError, match="tests_passed|manifest_sha256"):
        _validate(record, manifest_path, workflow)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("verification_execution_authorized", True),
        ("protected_holdout_execution_authorized", True),
        ("protected_holdout_accessed", True),
        ("retuning_after_authorization", True),
        ("candidate_removal_after_authorization", True),
        ("latest_attempt_only", False),
        ("fallback_to_earlier_attempt", True),
    ],
)
def test_dangerous_authorization_flags_fail_closed(tmp_path, field, value):
    record, _, manifest_path, workflow = _bundle(tmp_path)
    record[field] = value
    with pytest.raises(PermissionError, match=field):
        _validate(record, manifest_path, workflow)


def test_unknown_or_missing_authorization_fields_are_rejected(tmp_path):
    record, _, manifest_path, workflow = _bundle(tmp_path)
    record["unexpected"] = True
    with pytest.raises(PermissionError, match="fields differ"):
        _validate(record, manifest_path, workflow)
    del record["unexpected"]
    del record["authorized_by"]
    with pytest.raises(PermissionError, match="fields differ"):
        _validate(record, manifest_path, workflow)


@pytest.mark.parametrize("field", ["authorized_by", "authorization_reason"])
def test_external_review_metadata_cannot_be_empty_or_placeholder(tmp_path, field):
    record, _, manifest_path, workflow = _bundle(tmp_path)
    record[field] = "  "
    with pytest.raises(PermissionError, match=field):
        _validate(record, manifest_path, workflow)
    record[field] = "__PLACEHOLDER__"
    with pytest.raises(PermissionError, match="placeholder"):
        _validate(record, manifest_path, workflow)


def test_authorization_date_requires_iso_calendar_date(tmp_path):
    record, _, manifest_path, workflow = _bundle(tmp_path)
    record["authorized_on"] = "04.08.2026"
    with pytest.raises(PermissionError, match="ISO calendar date"):
        _validate(record, manifest_path, workflow)


def test_manifest_rejects_seed_or_scope_drift(tmp_path):
    _, manifest, _, workflow = _bundle(tmp_path)
    manifest["calibration_generator_seeds"] = list(range(5001, 5021))
    with pytest.raises(PermissionError, match="calibration_generator_seeds"):
        validate_execution_manifest(
            manifest,
            execution_commit=EXECUTION_COMMIT,
            outcome_workflow_sha256=sha256_file(workflow),
        )
    manifest["calibration_generator_seeds"] = list(EXPECTED_CALIBRATION_SEEDS)
    manifest["protected_holdout_execution_enabled"] = True
    with pytest.raises(PermissionError, match="protected_holdout"):
        validate_execution_manifest(
            manifest,
            execution_commit=EXECUTION_COMMIT,
            outcome_workflow_sha256=sha256_file(workflow),
        )


def test_unreadable_or_non_object_authorization_is_rejected(tmp_path):
    _, _, manifest_path, workflow = _bundle(tmp_path)
    arguments = {
        "expected_sha256": "a" * 64,
        "execution_commit": EXECUTION_COMMIT,
        "execution_manifest_path": manifest_path,
        "outcome_workflow_path": workflow,
        "confirmation": AUTHORIZATION_CONFIRMATION,
    }
    with pytest.raises(PermissionError, match="unreadable"):
        load_and_validate_authorization(tmp_path / "missing.json", **arguments)
    path = tmp_path / "list.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(PermissionError, match="JSON object"):
        load_and_validate_authorization(path, **arguments)


def test_template_and_validator_never_construct_domains(monkeypatch, tmp_path):
    from . import g1_domains

    def forbidden(*args, **kwargs):
        raise AssertionError("authorization boundary constructed a domain")

    monkeypatch.setattr(g1_domains, "build_domain", forbidden)
    record, _, manifest_path, workflow = _bundle(tmp_path)
    build_review_template()
    build_no_outcome_review()
    _validate(record, manifest_path, workflow)


def test_cli_emits_template_and_no_outcome_dry_run(tmp_path):
    template_path = tmp_path / "template.json"
    review_path = tmp_path / "review.json"
    assert main(["review-template", "--output", str(template_path)]) == 0
    assert main(["dry-run", "--output", str(review_path)]) == 0
    template = json.loads(template_path.read_text(encoding="utf-8"))
    review = json.loads(review_path.read_text(encoding="utf-8"))
    assert template["operational_authorization_record"] is False
    assert review["authorization_request_ready"] is False


def test_protocol_and_review_evidence_digests_are_frozen():
    assert protocol_file_sha256() == (
        "8cf978f6df7390e11297a4b00715dd2ce3c75ca4a542299dc53e5c1a917fe76d"
    )
    assert WP_GATE_0_13_EVIDENCE_SHA256 == (
        "467de7f261a9b8feaac2a212fbce9acec68c8a36cc09654c0d2f2cfcf0293ba2"
    )
