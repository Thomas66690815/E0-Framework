"""No-outcome tests for WP-GATE-0.7 cell-aligned distribution."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from . import override_gate_calibration_distributed as distributed
from .g1_baselines import EpisodeSummary
from .override_gate_calibration import load_calibration_instance
from .override_gate_calibration_distributed import (
    CALIBRATION_AUTHORIZATION_CONFIRMATION,
    EXPECTED_CELL_COUNT,
    EXPECTED_TASKS_PER_CELL,
    _cell_manifest,
    _sha256_value,
    authorization_sha256,
    build_authorization_record,
    build_cell_plan,
    cell_matrix,
    load_and_validate_authorization,
    merge_cell_artifacts,
    run_cell,
    select_latest_cell_attempts,
    tasks_for_cell,
    validate_cell_manifest,
)
from .override_gate_calibration_engine import InstrumentedEpisodeResult
from .override_gate_calibration_pipeline import build_completed_shard
from .override_gate_calibration_runner import build_task_plan

EXECUTION_COMMIT = "b" * 40
CELLS = build_cell_plan(EXECUTION_COMMIT)


def _authorization():
    return build_authorization_record(
        execution_commit=EXECUTION_COMMIT,
        authorized_by="synthetic-test",
        authorized_on="2026-07-31",
        confirmation=CALIBRATION_AUTHORIZATION_CONFIRMATION,
    )


def _episode(index: int):
    return InstrumentedEpisodeResult(
        summary=EpisodeSummary(
            episode_index=index,
            phase="adaptation" if index < 10 else "evaluation",
            goal_reached=True,
            interactions_used=2,
            interaction_budget=400,
            total_cost=2.0,
            oracle_cost=2,
            success_adjusted_efficiency=1.0,
            revisits=0,
            failure_count=0,
            terminal_reason="goal_reached",
            final_state="G",
            path=("S", "A", "G"),
        ),
        policy_id="gate_disabled",
        decision_records=(),
        paired_decisions=(),
        path_cap_hits=0,
    )


def _manifest(cell_index: int, attempt: int, *, status: str = "complete"):
    cell = CELLS[cell_index]
    authorization = _authorization()
    manifest = {
        "cell_artifact_schema_version": 1,
        "artifact_kind": "override_gate_calibration_cell",
        **cell,
        "run_attempt": attempt,
        "instance_sha256": authorization["instance_sha256"],
        "source_commit": load_calibration_instance()["source_commit"],
        "execution_commit": EXECUTION_COMMIT,
        "authorization_sha256": authorization_sha256(authorization),
        "status": status,
        "summary": {
            "planned": 20,
            "completed": 20 if status == "complete" else 19,
            "resumed": 0,
            "infrastructure_failures": 0 if status == "complete" else 1,
        },
        "shard_files": {
            f"synthetic-{index:02d}.json": "0" * 64
            for index in range(20 if status == "complete" else 19)
        },
        "failure_files": (
            {} if status == "complete" else {"failure.json": "1" * 64}
        ),
        "holdout_accessed": False,
        "not_gate_result": True,
    }
    manifest["cell_manifest_sha256"] = _sha256_value(manifest)
    return manifest


def test_cell_plan_is_exact_complete_144_by_20_partition():
    cells = CELLS
    assert len(cells) == EXPECTED_CELL_COUNT
    assert {cell["task_count"] for cell in cells} == {EXPECTED_TASKS_PER_CELL}
    assert len({cell["cell_id"] for cell in cells}) == EXPECTED_CELL_COUNT
    tasks = build_task_plan(
        "calibration",
        execution_commit=EXECUTION_COMMIT,
        planning_only=False,
    )
    assert len(tasks) == 2880
    assert len({task.run_id for task in tasks}) == 2880
    assert len(tasks_for_cell(EXECUTION_COMMIT, 0)) == 20
    assert len(tasks_for_cell(EXECUTION_COMMIT, 143)) == 20


def test_cell_matrix_is_deterministic_and_no_outcome():
    first = cell_matrix(EXECUTION_COMMIT)
    second = cell_matrix(EXECUTION_COMMIT)
    assert first == second
    assert len(first["include"]) == 144
    assert sum(cell["task_count"] for cell in first["include"]) == 2880
    assert set(first) == {"include"}


@pytest.mark.parametrize("index", [-1, 144])
def test_cell_index_is_bounded(index):
    with pytest.raises(ValueError, match="Cell index"):
        tasks_for_cell(EXECUTION_COMMIT, index)


def test_authorization_template_requires_exact_confirmation():
    with pytest.raises(PermissionError, match="confirmation"):
        build_authorization_record(
            execution_commit=EXECUTION_COMMIT,
            authorized_by="synthetic-test",
            authorized_on="2026-07-31",
            confirmation="yes",
        )


def test_authorization_file_is_digest_and_commit_bound(tmp_path):
    authorization = _authorization()
    digest = authorization_sha256(authorization)
    path = tmp_path / "authorization.json"
    path.write_text(json.dumps(authorization), encoding="utf-8")
    assert load_and_validate_authorization(
        path,
        expected_sha256=digest,
        execution_commit=EXECUTION_COMMIT,
        confirmation=CALIBRATION_AUTHORIZATION_CONFIRMATION,
    ) == authorization

    changed = copy.deepcopy(authorization)
    changed["verification_execution_authorized"] = True
    path.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(PermissionError, match="SHA-256"):
        load_and_validate_authorization(
            path,
            expected_sha256=digest,
            execution_commit=EXECUTION_COMMIT,
            confirmation=CALIBRATION_AUTHORIZATION_CONFIRMATION,
        )


def test_run_cell_rejects_before_domain_or_output(tmp_path):
    with pytest.raises(PermissionError, match="confirmation"):
        run_cell(
            output_dir=tmp_path / "must-not-exist",
            cell_index=0,
            execution_commit=EXECUTION_COMMIT,
            authorization=_authorization(),
            authorization_digest=authorization_sha256(_authorization()),
            confirmation="not-authorized",
            workers=1,
            run_attempt=1,
        )
    assert not (tmp_path / "must-not-exist").exists()


def test_latest_attempt_never_falls_back_to_prior_success():
    manifests = [_manifest(index, 1) for index in range(EXPECTED_CELL_COUNT)]
    manifests.append(_manifest(7, 2, status="infrastructure_failure"))
    selected = select_latest_cell_attempts(manifests)
    assert selected[7]["run_attempt"] == 2
    assert selected[7]["status"] == "infrastructure_failure"


def test_latest_attempt_selection_rejects_missing_or_duplicate():
    manifests = [_manifest(index, 1) for index in range(EXPECTED_CELL_COUNT)]
    with pytest.raises(ValueError, match="Expected latest attempts"):
        select_latest_cell_attempts(manifests[:-1])
    with pytest.raises(ValueError, match="Duplicate cell attempt"):
        select_latest_cell_attempts([*manifests, copy.deepcopy(manifests[0])])


def test_merge_validates_and_copies_complete_synthetic_cell(tmp_path, monkeypatch):
    cell = dict(CELLS[0])
    cell["execution_commit"] = EXECUTION_COMMIT
    tasks = tasks_for_cell(EXECUTION_COMMIT, 0)
    artifact = tmp_path / "downloads" / "cell-0-attempt-1"
    shards = artifact / "shards"
    shards.mkdir(parents=True)
    for task in tasks:
        shard = build_completed_shard(
            task,
            [_episode(index) for index in range(30)],
            wall_time_ms=1.0,
            peak_rss_bytes=1,
        )
        (shards / task.shard_name).write_text(
            json.dumps(shard),
            encoding="utf-8",
        )
    authorization = _authorization()
    digest = authorization_sha256(authorization)
    manifest = _cell_manifest(
        cell=cell,
        run_attempt=1,
        authorization_digest=digest,
        output_dir=artifact,
        summary={
            "planned": 20,
            "completed": 20,
            "resumed": 0,
            "infrastructure_failures": 0,
        },
    )
    (artifact / "cell_manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )
    monkeypatch.setattr(distributed, "build_cell_plan", lambda commit: [CELLS[0]])
    monkeypatch.setattr(
        distributed,
        "tasks_for_cell",
        lambda commit, cell_index: tasks,
    )
    merged = merge_cell_artifacts(
        input_dir=tmp_path / "downloads",
        output_dir=tmp_path / "merged",
        execution_commit=EXECUTION_COMMIT,
        authorization_digest=digest,
    )
    assert merged["cell_count"] == 1
    assert merged["task_shard_count"] == 20
    assert merged["selected_attempts"] == {"0": 1}
    assert len(list((tmp_path / "merged" / "shards").glob("*.json"))) == 20


def test_cell_manifest_is_commit_authorization_and_digest_bound():
    manifest = _manifest(0, 1)
    cell = CELLS[0]
    validate_cell_manifest(
        manifest,
        expected_cell=cell,
        execution_commit=EXECUTION_COMMIT,
        authorization_digest=authorization_sha256(_authorization()),
    )
    changed = copy.deepcopy(manifest)
    changed["execution_commit"] = "c" * 40
    payload = copy.deepcopy(changed)
    payload.pop("cell_manifest_sha256")
    changed["cell_manifest_sha256"] = _sha256_value(payload)
    with pytest.raises(ValueError, match="execution_commit"):
        validate_cell_manifest(
            changed,
            expected_cell=cell,
            execution_commit=EXECUTION_COMMIT,
            authorization_digest=authorization_sha256(_authorization()),
        )


def test_execution_workflow_is_manual_authorized_and_cell_aligned():
    workflow = (
        Path(__file__).parents[1]
        / ".github"
        / "workflows"
        / "override-gate-calibration-execute.yml"
    ).read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert "AUTHORIZE_FROZEN_CALIBRATION_ONLY" in workflow
    assert "authorization_sha256:" in workflow
    assert "authorization_record:" in workflow
    assert "Emit 144 complete 20-seed cells" in workflow
    assert "run-cell" in workflow
    assert "fail-fast: false" in workflow
    assert "max-parallel: 20" in workflow
    assert "run-attempt" in workflow
    assert "consolidate" in workflow
    assert "schedule:" not in workflow
    assert "push:" not in workflow


def test_planning_workflow_cannot_execute_distribution_cli():
    workflow = (
        Path(__file__).parents[1]
        / ".github"
        / "workflows"
        / "override-gate-calibration-plan.yml"
    ).read_text(encoding="utf-8")
    assert "override_gate_calibration_distributed" not in workflow
    assert "run-cell" not in workflow
