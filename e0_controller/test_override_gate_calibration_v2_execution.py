"""No-outcome execution-layer tests for WP-GATE-0.15."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from .g1_domains import (
    V2_CALIBRATION_SEED_NAMESPACE,
    HoldoutAccessError,
    _validate_seed_namespace,
    build_domain,
)
from .override_gate_calibration_engine import candidate_policy, run_instrumented_episode
from .override_gate_calibration_v2_authorization import (
    AUTHORIZATION_CONFIRMATION,
    authorization_sha256,
    build_review_template,
    sha256_file,
)
from .override_gate_calibration_v2_execution import (
    STAGE_A,
    STAGE_B,
    WORKFLOW_PATH,
    _attempt_document,
    _sha256,
    _task_for_cell,
    _validate_attempt,
    _write_once,
    authorize_calibration_context,
    authorized_matrix,
    build_calibration_domain_v2,
    build_execution_manifest,
    build_no_outcome_execution_review,
    consolidate_stage,
    main,
    validate_stage_consolidation,
)
from .override_gate_calibration_v2_statistics import (
    validate_stage_a_calibration_records,
)
from .test_override_gate_calibration_v2_statistics import (
    _complete_synthetic_records,
)

EXECUTION_COMMIT = "c" * 40


def _authorized_bundle(tmp_path):
    manifest = build_execution_manifest(EXECUTION_COMMIT)
    manifest_path = tmp_path / "execution-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest_digest = sha256_file(manifest_path)
    record = copy.deepcopy(build_review_template()["template_fields"])
    record.update(
        execution_commit=EXECUTION_COMMIT,
        execution_manifest_sha256=manifest_digest,
        outcome_workflow_sha256=sha256_file(WORKFLOW_PATH),
        authorized_by="external-reviewer",
        authorized_on="2026-08-04",
        authorization_reason="Reviewed the exact execution package.",
    )
    authorization_path = tmp_path / "authorization.json"
    authorization_path.write_text(json.dumps(record), encoding="utf-8")
    context = authorize_calibration_context(
        authorization_path=authorization_path,
        authorization_digest=authorization_sha256(record),
        execution_commit=EXECUTION_COMMIT,
        execution_manifest_path=manifest_path,
        execution_manifest_digest=manifest_digest,
        outcome_workflow_path=WORKFLOW_PATH,
        confirmation=AUTHORIZATION_CONFIRMATION,
    )
    return context, record, authorization_path, manifest, manifest_path


def _timeout_stage_b_record(task, seed):
    return {
        "instance_id": task.instance_id,
        "instance_sha256": task.instance_sha256,
        "source_commit": __import__(
            "e0_controller.override_gate_calibration_v2",
            fromlist=["load_calibration_instance_v2"],
        ).load_calibration_instance_v2()["source_commit"],
        "execution_commit": task.execution_commit,
        "split": "calibration",
        "stage": STAGE_B,
        "domain_family": task.family,
        "scale": task.scale,
        "generator_seed": seed,
        "policy_id": task.policy_id,
        "primary_utility": 0.0,
        "observed_disagreement_count": 0,
        "guard_eligible_disagreement_count": 0,
        "executed_override_count": 0,
        "algorithm_timeout_count": 1,
        "path_cap_count": 0,
        "infrastructure_failure": False,
        "parent_wall_time_ms": 1800000.0,
        "branch_time_charged_to_parent": False,
        "holdout_accessed": False,
        "not_gate_result": True,
    }


def _incomplete_trace(record):
    identity = {
        key: record[key]
        for key in (
            "instance_id",
            "instance_sha256",
            "source_commit",
            "execution_commit",
            "split",
            "domain_family",
            "scale",
            "generator_seed",
            "policy_id",
            "holdout_accessed",
            "not_gate_result",
        )
    }
    return {
        "trace_schema_version": 1,
        "artifact_kind": "override_gate_v2_stage_b_decision_trace",
        **identity,
        "trace_complete": False,
        "parent_decision_trace_sha256": _sha256([]),
        "decision_records": [],
        "episode_summaries": [],
    }


def test_execution_manifest_is_complete_and_domain_free(monkeypatch):
    from . import g1_domains

    def forbidden(*args, **kwargs):
        raise AssertionError("manifest constructed a domain")

    monkeypatch.setattr(g1_domains, "build_domain", forbidden)
    manifest = build_execution_manifest(EXECUTION_COMMIT)
    assert manifest["stage_b_cell_count"] == 144
    assert manifest["stage_a_cell_count"] == 132
    assert manifest["calibration_generator_seeds"] == list(range(5000, 5020))
    assert manifest["verification_execution_enabled"] is False
    assert manifest["protected_holdout_execution_enabled"] is False


def test_no_outcome_review_seals_locked_executable_state():
    review = build_no_outcome_execution_review()
    assert review["execution_layer_implemented"] is True
    assert review["authorization_required_before_domain"] is True
    assert review["outcome_commands_exposed_but_locked"] is True
    assert review["operational_authorization_record_present"] is False
    assert review["execution_commit_frozen"] is False
    assert review["domains_instantiated"] == 0
    assert review["outcomes_observed"] == 0


def test_external_bundle_creates_authorized_context(tmp_path):
    context, record, _, _, _ = _authorized_bundle(tmp_path)
    assert context.execution_commit == EXECUTION_COMMIT
    assert context.authorization_sha256 == authorization_sha256(record)


def test_context_rejects_changed_manifest_bytes(tmp_path):
    _, record, authorization_path, manifest, manifest_path = _authorized_bundle(tmp_path)
    manifest["tests_passed"] = False
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(PermissionError, match="manifest SHA-256 mismatch"):
        authorize_calibration_context(
            authorization_path=authorization_path,
            authorization_digest=authorization_sha256(record),
            execution_commit=EXECUTION_COMMIT,
            execution_manifest_path=manifest_path,
            execution_manifest_digest=record["execution_manifest_sha256"],
            outcome_workflow_path=WORKFLOW_PATH,
            confirmation=AUTHORIZATION_CONFIRMATION,
        )


def test_authorized_matrices_are_exact_and_domain_free(tmp_path, monkeypatch):
    context, *_ = _authorized_bundle(tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("matrix constructed a domain")

    monkeypatch.setitem(
        __import__(
            "e0_controller.override_gate_calibration_v2_execution",
            fromlist=["BUILDERS"],
        ).BUILDERS,
        "wall_grid",
        forbidden,
    )
    assert len(authorized_matrix(context, STAGE_B)["include"]) == 144
    assert len(authorized_matrix(context, STAGE_A)["include"]) == 132


def test_domain_builder_requires_context_and_calibration_seed(tmp_path):
    context, *_ = _authorized_bundle(tmp_path)
    with pytest.raises(PermissionError, match="context required"):
        build_calibration_domain_v2(object(), "wall_grid", 100, 5000)
    with pytest.raises(PermissionError, match="outside v2 calibration"):
        build_calibration_domain_v2(context, "wall_grid", 100, 7000)


def test_v2_namespace_accepts_only_frozen_calibration_seeds():
    _validate_seed_namespace(5000, V2_CALIBRATION_SEED_NAMESPACE)
    with pytest.raises(HoldoutAccessError):
        _validate_seed_namespace(7000, V2_CALIBRATION_SEED_NAMESPACE)


def test_unauthorized_outcome_command_fails_before_domain_builder(monkeypatch, tmp_path):
    from . import override_gate_calibration_v2_execution as execution

    def forbidden(*args, **kwargs):
        raise AssertionError("unauthorized path reached a domain builder")

    for family in tuple(execution.BUILDERS):
        monkeypatch.setitem(execution.BUILDERS, family, forbidden)
    result = main(
        [
            "run-stage-b-cell",
            "--authorization", str(tmp_path / "missing-auth.json"),
            "--authorization-sha256", "a" * 64,
            "--execution-commit", EXECUTION_COMMIT,
            "--execution-manifest", str(tmp_path / "missing-manifest.json"),
            "--execution-manifest-sha256", "b" * 64,
            "--outcome-workflow", str(WORKFLOW_PATH),
            "--confirmation", AUTHORIZATION_CONFIRMATION,
            "--cell-index", "0",
            "--run-attempt", "1",
            "--output", str(tmp_path / "out"),
        ]
    )
    assert result == 2


def test_independent_branch_deadline_is_not_available_in_development():
    domain = build_domain("wall_grid", 100, 0)
    with pytest.raises(PermissionError, match="v2 calibration-only"):
        run_instrumented_episode(
            domain,
            candidate_policy("margin_000"),
            10,
            interaction_budget=10,
            paired_branch_decision_keys={(10, 0)},
            paired_branch_timeout_seconds=1.0,
        )


def test_complete_timeout_cell_attempt_validates(tmp_path):
    context, *_ = _authorized_bundle(tmp_path)
    task = _task_for_cell(context, STAGE_B, 0)
    records = [_timeout_stage_b_record(task, seed) for seed in task.seeds]
    traces = [_incomplete_trace(record) for record in records]
    attempt = _attempt_document(context, task, 1, records, traces, ())
    _validate_attempt(attempt, context, task)
    assert attempt["cell_complete"] is True
    assert attempt["record_count"] == 20


def test_attempt_is_write_once_and_digest_bound(tmp_path):
    context, *_ = _authorized_bundle(tmp_path)
    task = _task_for_cell(context, STAGE_B, 0)
    records = [_timeout_stage_b_record(task, seed) for seed in task.seeds]
    traces = [_incomplete_trace(record) for record in records]
    attempt = _attempt_document(context, task, 1, records, traces, ())
    path = tmp_path / f"{task.cell_id}.attempt-1.json"
    _write_once(path, attempt)
    with pytest.raises(FileExistsError):
        _write_once(path, attempt)
    changed = copy.deepcopy(attempt)
    changed["records"][0]["primary_utility"] = 1.0
    with pytest.raises(ValueError, match="digest changed"):
        _validate_attempt(changed, context, task)


def test_consolidation_never_falls_back_from_corrupt_latest(tmp_path):
    context, *_ = _authorized_bundle(tmp_path)
    task = _task_for_cell(context, STAGE_B, 0)
    records = [_timeout_stage_b_record(task, seed) for seed in task.seeds]
    traces = [_incomplete_trace(record) for record in records]
    attempt = _attempt_document(context, task, 1, records, traces, ())
    _write_once(tmp_path / f"{task.cell_id}.attempt-1.json", attempt)
    (tmp_path / f"{task.cell_id}.attempt-2.json").write_text("{broken", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        consolidate_stage(context, STAGE_B, tmp_path)
    with pytest.raises(ValueError, match="consolidation digest changed"):
        validate_stage_consolidation({}, context, STAGE_B)


def test_skipped_stage_a_record_is_valid_only_for_stage_b_timeout():
    stage_b, stage_a = _complete_synthetic_records()
    parent = next(item for item in stage_b if item["policy_id"] == "margin_000")
    child = next(
        item
        for item in stage_a
        if item["policy_id"] == "margin_000"
        and item["domain_family"] == parent["domain_family"]
        and item["scale"] == parent["scale"]
        and item["generator_seed"] == parent["generator_seed"]
    )
    parent.update(algorithm_timeout_count=1, executed_override_count=0)
    child.update(
        stage_a_skipped_due_stage_b_valid_negative=True,
        parent_replay_trace_match=False,
        sampling_frame_override_count=0,
        sample_count=0,
        paired_decisions=[],
        unresolved_count=0,
    )
    validate_stage_a_calibration_records(stage_a, stage_b_records=stage_b)
    parent["algorithm_timeout_count"] = 0
    with pytest.raises(ValueError, match="requires a Stage-B algorithm timeout"):
        validate_stage_a_calibration_records(stage_a, stage_b_records=stage_b)


def test_workflow_is_manual_calibration_only_and_stage_separated():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert "schedule:" not in workflow
    assert "push:" not in workflow
    assert "run-stage-b-cell" in workflow
    assert "consolidate_stage_b:" in workflow
    assert "run-stage-a-cell" in workflow
    assert "needs: [authorize, consolidate_stage_b]" in workflow
    assert "protected_holdout" not in workflow
    assert AUTHORIZATION_CONFIRMATION in workflow


def test_workflow_revalidates_boundary_for_every_mutating_command():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    commands = (
        "run-stage-b-cell",
        "run-stage-a-cell",
        "consolidate",
        "select",
    )
    for command in commands:
        section = workflow.split(command, 1)[1]
        assert "--authorization " in section
        assert "--execution-manifest " in section
        assert "--outcome-workflow " in section
        assert "--confirmation " in section


def test_current_repository_contains_no_operational_authorization_or_manifest():
    root = Path(__file__).resolve().parent.parent
    assert not (root / "artifacts/override_gate/v2-boundary/authorization.json").exists()
    assert not (root / "artifacts/override_gate/v2-boundary/execution-manifest.json").exists()


def test_cli_execution_manifest_is_no_outcome(tmp_path):
    output = tmp_path / "manifest.json"
    assert main(
        [
            "execution-manifest",
            "--execution-commit", EXECUTION_COMMIT,
            "--outcome-workflow", str(WORKFLOW_PATH),
            "--output", str(output),
        ]
    ) == 0
    manifest = json.loads(output.read_text(encoding="utf-8"))
    assert manifest["not_gate_result"] is True
    assert manifest["protected_holdout_accessed"] is False
    assert "authorization_sha256" not in manifest
