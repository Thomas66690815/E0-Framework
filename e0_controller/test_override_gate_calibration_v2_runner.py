"""Domain-free planning and artifact tests for override-gate v2."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .override_gate_calibration_v2 import (
    instance_sha256,
    load_calibration_instance_v2,
)
from .override_gate_calibration_v2_runner import (
    SELECTED_POLICY_PLACEHOLDER,
    STAGE_A,
    STAGE_A_REPLICATE_REQUIRED_FIELDS,
    STAGE_B,
    STAGE_B_REPLICATE_REQUIRED_FIELDS,
    V2ExecutionProhibited,
    artifact_contract,
    build_cell_plan,
    dry_run_manifest,
    main,
    matrix_plan,
    validate_artifact_record,
    validate_cell_plan,
    validate_dry_run_manifest,
)

EXECUTION_COMMIT = "b" * 40


def _artifact_record(kind: str, split: str = "calibration"):
    required = {
        "stage_b_replicate_record": STAGE_B_REPLICATE_REQUIRED_FIELDS,
        "stage_a_replicate_record": STAGE_A_REPLICATE_REQUIRED_FIELDS,
        "selection_record": artifact_contract()["selection_record"][
            "required_fields"
        ],
    }[kind]
    record = {field: 0 for field in required}
    instance = load_calibration_instance_v2()
    record.update(
        {
            "instance_id": instance["instance_id"],
            "instance_sha256": instance_sha256(instance),
            "source_commit": instance["source_commit"],
            "execution_commit": EXECUTION_COMMIT,
            "split": split,
            "holdout_accessed": split == "protected_holdout",
            "not_gate_result": True,
        }
    )
    if kind == "stage_b_replicate_record":
        record.update(
            stage=STAGE_B,
            branch_time_charged_to_parent=False,
        )
    elif kind == "stage_a_replicate_record":
        record.update(
            stage=STAGE_A,
            sample_count=4,
            parent_replay_trace_match=True,
            instrumentation_time_is_parent_performance=False,
        )
    return record


def test_v2_calibration_cell_plans_have_exact_separate_matrices():
    stage_b = build_cell_plan("calibration", STAGE_B)
    stage_a = build_cell_plan("calibration", STAGE_A)
    assert len(stage_b) == 144
    assert len(stage_a) == 132
    assert len({task.cell_id for task in stage_b}) == 144
    assert len({task.cell_id for task in stage_a}) == 132
    assert {task.replicate_count for task in stage_b + stage_a} == {20}
    assert sum(task.sampled_pairs_max for task in stage_a) == 10560
    assert all(task.policy_id != "gate_disabled" for task in stage_a)


@pytest.mark.parametrize("split", ["verification", "protected_holdout"])
def test_v2_protected_plans_use_visible_placeholder(split):
    for stage in (STAGE_B, STAGE_A):
        tasks = build_cell_plan(split, stage)
        assert len(tasks) == 12
        assert {task.policy_id for task in tasks} == {SELECTED_POLICY_PLACEHOLDER}
        assert {task.replicate_count for task in tasks} == {30}


def test_v2_planning_never_constructs_a_domain(monkeypatch):
    from . import g1_domains

    def forbidden(*args, **kwargs):
        raise AssertionError("domain builder was called")

    monkeypatch.setattr(g1_domains, "build_domain", forbidden)
    assert len(build_cell_plan("calibration", STAGE_B)) == 144
    assert dry_run_manifest()["domains_instantiated"] == 0


def test_v2_nonplanning_execution_is_unconditionally_prohibited():
    with pytest.raises(V2ExecutionProhibited, match="execution is prohibited"):
        build_cell_plan(
            "calibration",
            STAGE_B,
            execution_commit=EXECUTION_COMMIT,
            planning_only=False,
        )


def test_v2_planning_cannot_bind_a_selected_policy():
    with pytest.raises(V2ExecutionProhibited, match="cannot bind"):
        build_cell_plan(
            "verification",
            STAGE_B,
            selected_policy_id="margin_020",
        )


def test_v2_stage_matrices_fit_github_limit_independently():
    stage_b = matrix_plan(split="calibration", stage=STAGE_B)
    stage_a = matrix_plan(split="calibration", stage=STAGE_A)
    assert stage_b["execution_prohibited"] is True
    assert stage_b["cell_count"] == 144
    assert stage_b["replicate_count"] == 2880
    assert stage_a["cell_count"] == 132
    assert stage_a["replicate_count"] == 2640
    assert stage_a["sampled_pairs_max"] == 10560


def test_v2_dry_run_is_complete_deterministic_and_result_free():
    first = dry_run_manifest()
    second = dry_run_manifest()
    assert first == second
    assert first["execution_prohibited"] is True
    assert first["outcome_commands_exposed"] is False
    assert first["domains_instantiated"] == 0
    assert first["outcomes_observed"] == 0
    assert first["calibration_executed"] is False
    assert first["protected_holdout_accessed"] is False
    assert first["not_gate_result"] is True
    assert len(first["dry_run_sha256"]) == 64
    validate_dry_run_manifest(first)


def test_v2_dry_run_digest_rejects_mutation():
    manifest = dry_run_manifest()
    manifest["outcomes_observed"] = 1
    with pytest.raises(ValueError, match="must be zero"):
        validate_dry_run_manifest(manifest)


@pytest.mark.parametrize(
    "kind",
    ["stage_b_replicate_record", "stage_a_replicate_record", "selection_record"],
)
def test_v2_artifact_shapes_validate(kind):
    validate_artifact_record(kind, _artifact_record(kind))


def test_v2_artifact_contract_exposes_nonconfounding_boundaries():
    contract = artifact_contract()
    assert contract["stage_b_replicate_record"][
        "branch_time_charged_to_parent_must_be"
    ] is False
    assert contract["stage_a_replicate_record"]["sample_count_max"] == 4
    assert contract["selection_record"]["both_stages_required"] is True
    assert contract["global_invariants"]["fallback_to_earlier_attempt"] is False


def test_v2_artifacts_reject_cross_stage_timing_and_replay_drift():
    stage_b = _artifact_record("stage_b_replicate_record")
    stage_b["branch_time_charged_to_parent"] = True
    with pytest.raises(ValueError, match="cannot contain branch time"):
        validate_artifact_record("stage_b_replicate_record", stage_b)
    stage_a = _artifact_record("stage_a_replicate_record")
    stage_a["parent_replay_trace_match"] = False
    with pytest.raises(ValueError, match="must match"):
        validate_artifact_record("stage_a_replicate_record", stage_a)


def test_v2_cell_plan_validator_rejects_duplicate_cell():
    tasks = build_cell_plan("calibration", STAGE_B)
    changed = list(tasks)
    changed[-1] = changed[0]
    with pytest.raises(ValueError, match="cell IDs"):
        validate_cell_plan(changed, split="calibration", stage=STAGE_B)


def test_v2_cli_writes_atomic_dry_run_and_has_no_run_command(tmp_path, capsys):
    output = tmp_path / "v2-dry-run.json"
    assert main(["dry-run", "--output", str(output)]) == 0
    written = json.loads(output.read_text(encoding="utf-8"))
    captured = capsys.readouterr()
    assert captured.err == ""
    assert written == json.loads(captured.out)
    assert written["execution_prohibited"] is True
    with pytest.raises(SystemExit):
        main(["run-cell"])


def test_v2_github_workflow_is_manual_and_planning_only():
    workflow = (
        Path(__file__).resolve().parent.parent
        / ".github"
        / "workflows"
        / "override-gate-calibration-v2-plan.yml"
    ).read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert "push:" not in workflow
    assert "schedule:" not in workflow
    assert "run-cell" not in workflow
    assert "stage_b_closed_loop_parent" in workflow
    assert "stage_a_paired_evidence" in workflow
    assert "planning evidence only" in workflow
