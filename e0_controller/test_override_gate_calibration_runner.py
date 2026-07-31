"""Tests for the fail-closed, domain-free calibration execution scaffold."""

from __future__ import annotations

import json

import pytest

from .override_gate_calibration import load_calibration_instance
from .override_gate_calibration_runner import (
    CLOSED_LOOP_REQUIRED_FIELDS,
    PAIRED_BRANCH_REQUIRED_FIELDS,
    SELECTED_POLICY_PLACEHOLDER,
    CalibrationTask,
    SplitAuthorizationError,
    artifact_contract,
    build_task_plan,
    dry_run_manifest,
    instance_sha256,
    main,
    matrix_plan,
    partition_tasks,
    validate_artifact_record,
    validate_dry_run_manifest,
    validate_task_plan,
)

EXECUTION_COMMIT = "1" * 40
ARTIFACT_SHA = "2" * 64


def _authorization(split: str, policy_id: str = "margin_020"):
    record = {
        "instance_id": "E0-OVERRIDE-GATE-CAL-INSTANCE-v1",
        "selected_policy_id": policy_id,
        "artifact_sha256": ARTIFACT_SHA,
        "retuning_after_artifact": False,
    }
    if split == "verification":
        record["calibration_status"] = "selected"
    else:
        record["verification_status"] = "passed"
        record["protected_holdout_accessed"] = False
    return record


def _artifact_record(kind: str, split: str = "calibration"):
    required = {
        "paired_branch_record": PAIRED_BRANCH_REQUIRED_FIELDS,
        "closed_loop_replicate_record": CLOSED_LOOP_REQUIRED_FIELDS,
        "selection_record": artifact_contract()["selection_record"][
            "required_fields"
        ],
    }[kind]
    record = {field: 0 for field in required}
    record.update(
        {
            "instance_id": "E0-OVERRIDE-GATE-CAL-INSTANCE-v1",
            "instance_sha256": instance_sha256(),
            "source_commit": load_calibration_instance()["source_commit"],
            "execution_commit": EXECUTION_COMMIT,
            "split": split,
            "holdout_accessed": split == "protected_holdout",
            "not_gate_result": True,
        }
    )
    if kind == "paired_branch_record":
        record["parent_run_mutated"] = False
    return record


def test_calibration_plan_has_all_frozen_tasks():
    tasks = build_task_plan("calibration")
    assert len(tasks) == 2880
    assert len({task.run_id for task in tasks}) == 2880
    assert len({task.shard_name for task in tasks}) == 2880
    assert {task.policy_id for task in tasks} == {
        "gate_disabled",
        "margin_000",
        "margin_005",
        "margin_010",
        "margin_015",
        "margin_020",
        "margin_025",
        "margin_030",
        "margin_035",
        "margin_040",
        "margin_050",
        "margin_085",
    }
    assert {
        task.control_mode for task in tasks
    } == {"self", "shared_calibration_task"}


@pytest.mark.parametrize(
    ("split", "expected"),
    [("verification", 360), ("protected_holdout", 360)],
)
def test_protected_planning_uses_visible_placeholder(split, expected):
    tasks = build_task_plan(split)
    assert len(tasks) == expected
    assert {task.policy_id for task in tasks} == {SELECTED_POLICY_PLACEHOLDER}
    assert all(task.execution_commit == "UNFROZEN" for task in tasks)
    assert {task.control_mode for task in tasks} == {"coexecuted_in_task"}


def test_planning_does_not_call_g1_domain_builder(monkeypatch):
    from . import g1_domains

    def forbidden(*args, **kwargs):
        raise AssertionError("domain builder was called")

    monkeypatch.setattr(g1_domains, "build_domain", forbidden)
    assert len(build_task_plan("calibration")) == 2880
    assert dry_run_manifest()["domains_instantiated"] == 0


def test_exploration_cannot_be_planned_for_execution():
    with pytest.raises(SplitAuthorizationError, match="may not be executed"):
        build_task_plan("exploration")


def test_nonplanning_calibration_requires_frozen_commit():
    with pytest.raises(SplitAuthorizationError, match="frozen 40-character"):
        build_task_plan("calibration", planning_only=False)


def test_nonplanning_calibration_rejects_selected_policy():
    with pytest.raises(SplitAuthorizationError, match="complete frozen candidate"):
        build_task_plan(
            "calibration",
            execution_commit=EXECUTION_COMMIT,
            selected_policy_id="margin_020",
            planning_only=False,
        )


def test_verification_requires_calibration_selection():
    with pytest.raises(SplitAuthorizationError, match="authorization"):
        build_task_plan(
            "verification",
            execution_commit=EXECUTION_COMMIT,
            selected_policy_id="margin_020",
            planning_only=False,
        )
    tasks = build_task_plan(
        "verification",
        execution_commit=EXECUTION_COMMIT,
        selected_policy_id="margin_020",
        authorization=_authorization("verification"),
        planning_only=False,
    )
    assert len(tasks) == 360
    assert {task.policy_id for task in tasks} == {"margin_020"}


def test_holdout_requires_passed_verification():
    bad = _authorization("protected_holdout")
    bad["verification_status"] = "failed"
    with pytest.raises(SplitAuthorizationError, match="verification_status=passed"):
        build_task_plan(
            "protected_holdout",
            execution_commit=EXECUTION_COMMIT,
            selected_policy_id="margin_020",
            authorization=bad,
            planning_only=False,
        )


def test_holdout_rejects_prior_access():
    authorization = _authorization("protected_holdout")
    authorization["protected_holdout_accessed"] = True
    with pytest.raises(SplitAuthorizationError, match="already marked accessed"):
        build_task_plan(
            "protected_holdout",
            execution_commit=EXECUTION_COMMIT,
            selected_policy_id="margin_020",
            authorization=authorization,
            planning_only=False,
        )


def test_partition_is_complete_unique_and_balanced():
    tasks = build_task_plan("calibration")
    batches = partition_tasks(tasks, 240)
    flattened = [task.run_id for batch in batches for task in batch]
    assert len(batches) == 240
    assert {len(batch) for batch in batches} == {12}
    assert len(flattened) == len(set(flattened)) == 2880
    assert set(flattened) == {task.run_id for task in tasks}


@pytest.mark.parametrize("batch_count", [0, 257, 2881])
def test_partition_rejects_invalid_batch_count(batch_count):
    tasks = build_task_plan("calibration")
    with pytest.raises(ValueError):
        partition_tasks(tasks, batch_count)


def test_matrix_is_explicitly_nonexecuting():
    matrix = matrix_plan()
    assert matrix["execution_prohibited"] is True
    assert matrix["task_count"] == 2880
    assert matrix["batch_count"] == 240
    assert len(matrix["include"]) == 240
    assert sum(item["task_count"] for item in matrix["include"]) == 2880


def test_dry_run_manifest_is_complete_and_result_free():
    manifest = dry_run_manifest()
    assert manifest["execution_prohibited"] is True
    assert manifest["domains_instantiated"] == 0
    assert manifest["outcomes_observed"] == 0
    assert manifest["calibration_executed"] is False
    assert manifest["verification_executed"] is False
    assert manifest["protected_holdout_accessed"] is False
    assert manifest["not_gate_result"] is True
    assert manifest["splits"]["calibration"]["task_count"] == 2880
    assert manifest["splits"]["verification"]["task_count"] == 360
    assert manifest["splits"]["protected_holdout"]["task_count"] == 360
    assert manifest["splits"]["verification"]["control_modes"] == [
        "coexecuted_in_task"
    ]
    assert len(manifest["dry_run_sha256"]) == 64
    validate_dry_run_manifest(manifest)


def test_dry_run_is_deterministic():
    assert dry_run_manifest() == dry_run_manifest()


def test_dry_run_digest_rejects_mutation():
    manifest = dry_run_manifest()
    manifest["outcomes_observed"] = 1
    with pytest.raises(ValueError, match="must be zero"):
        validate_dry_run_manifest(manifest)


def test_task_plan_hash_changes_with_execution_commit():
    first = dry_run_manifest(execution_commit="UNFROZEN")
    second = dry_run_manifest(execution_commit=EXECUTION_COMMIT)
    assert (
        first["splits"]["calibration"]["task_plan_sha256"]
        != second["splits"]["calibration"]["task_plan_sha256"]
    )
    assert second["execution_commit_frozen"] is True


def test_artifact_contract_exposes_required_boundaries():
    contract = artifact_contract()
    assert "delta_utility" in contract["paired_branch_record"]["required_fields"]
    assert "primary_effect_vs_disabled" in contract[
        "closed_loop_replicate_record"
    ]["required_fields"]
    assert contract["selection_record"]["split_must_be"] == "calibration"
    assert contract["global_invariants"][
        "protected_holdout_requires_verification_pass"
    ] is True
    assert contract["global_invariants"][
        "verification_and_holdout_control_mode"
    ] == "coexecuted_in_task"


@pytest.mark.parametrize(
    "kind",
    [
        "paired_branch_record",
        "closed_loop_replicate_record",
        "selection_record",
    ],
)
def test_valid_artifact_record_shapes(kind):
    validate_artifact_record(kind, _artifact_record(kind))


def test_artifact_record_rejects_missing_field():
    record = _artifact_record("paired_branch_record")
    del record["delta_utility"]
    with pytest.raises(ValueError, match="missing fields"):
        validate_artifact_record("paired_branch_record", record)


def test_artifact_record_rejects_parent_mutation():
    record = _artifact_record("paired_branch_record")
    record["parent_run_mutated"] = True
    with pytest.raises(ValueError, match="must not mutate"):
        validate_artifact_record("paired_branch_record", record)


def test_selection_is_calibration_only():
    record = _artifact_record("selection_record", split="verification")
    with pytest.raises(ValueError, match="calibration-only"):
        validate_artifact_record("selection_record", record)


def test_holdout_flag_must_match_split():
    record = _artifact_record("closed_loop_replicate_record")
    record["holdout_accessed"] = True
    with pytest.raises(ValueError, match="contradicts"):
        validate_artifact_record("closed_loop_replicate_record", record)


def test_validate_task_plan_detects_duplicate_identity():
    tasks = build_task_plan("verification")
    changed = list(tasks)
    changed[-1] = changed[0]
    with pytest.raises(ValueError, match="run IDs"):
        validate_task_plan(
            changed,
            split="verification",
            planning_only=True,
        )


def test_task_record_is_json_round_trippable():
    task = build_task_plan("calibration")[0]
    assert json.loads(json.dumps(task.to_dict())) == task.to_dict()
    assert CalibrationTask(**{
        key: value
        for key, value in task.to_dict().items()
        if key
        not in {
            "task_schema_version",
            "control_policy_id",
            "control_run_id",
            "control_mode",
            "run_id",
            "shard_name",
        }
    }) == task


def test_cli_dry_run_writes_atomic_manifest(tmp_path, capsys):
    output = tmp_path / "dry-run.json"
    assert main(["dry-run", "--output", str(output)]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    written = json.loads(output.read_text(encoding="utf-8"))
    assert written == json.loads(captured.out)
    assert written["execution_prohibited"] is True


def test_cli_has_no_run_command():
    with pytest.raises(SystemExit):
        main(["run-batch"])
