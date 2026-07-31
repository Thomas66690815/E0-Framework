"""No-outcome tests for calibration worker, shard, resume, and authorization."""

from __future__ import annotations

import copy
import json
import time
from pathlib import Path

import pytest

from .g1_baselines import EpisodeSummary
from .override_gate import OverrideGateMode
from .override_gate_calibration import load_calibration_instance
from .override_gate_calibration_engine import InstrumentedEpisodeResult
from .override_gate_calibration_pipeline import (
    AUTHORIZATION_SCHEMA_VERSION,
    CALIBRATION_SHARD_VERSION,
    _classify_branches,
    _execution_cells,
    _sha256_value,
    _task_from_payload,
    _write_failure_artifact,
    algorithm_timeout_shard,
    build_completed_shard,
    consolidate_calibration,
    execute_calibration_task_bounded,
    execute_task_set,
    load_calibration_shard,
    validate_calibration_shard,
    validate_execution_authorization,
)
from .override_gate_calibration_runner import build_task_plan, instance_sha256

EXECUTION_COMMIT = "a" * 40


def _task(policy_id: str = "gate_disabled"):
    return next(
        task
        for task in build_task_plan(
            "calibration",
            execution_commit=EXECUTION_COMMIT,
            planning_only=False,
        )
        if task.policy_id == policy_id
    )


def _authorization():
    instance = load_calibration_instance()
    return {
        "authorization_schema_version": AUTHORIZATION_SCHEMA_VERSION,
        "instance_id": instance["instance_id"],
        "instance_sha256": instance_sha256(instance),
        "execution_commit": EXECUTION_COMMIT,
        "authorized_split": "calibration",
        "calibration_execution_authorized": True,
        "verification_execution_authorized": False,
        "protected_holdout_execution_authorized": False,
        "retuning_after_authorization": False,
        "authorized_by": "synthetic-test",
        "authorized_on": "2026-07-31",
    }


def _episode(index: int, *, override: bool = False):
    summary = EpisodeSummary(
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
    )
    return InstrumentedEpisodeResult(
        summary=summary,
        policy_id="gate_disabled",
        decision_records=(),
        paired_decisions=(),
        path_cap_hits=0,
    )


def _sleep_worker(payload):
    time.sleep(5)
    raise AssertionError("worker should have been terminated")


def test_canonical_task_round_trip():
    task = _task()
    assert _task_from_payload(task.to_dict()) == task


@pytest.mark.parametrize(
    "mutation",
    [
        lambda record: record.update(split="verification"),
        lambda record: record.update(execution_commit="short"),
        lambda record: record.update(seed=3000),
        lambda record: record.update(policy_id="margin_042"),
        lambda record: record.update(run_id="tampered"),
    ],
)
def test_task_payload_rejects_scope_or_identity_drift(mutation):
    record = _task().to_dict()
    mutation(record)
    with pytest.raises(ValueError):
        _task_from_payload(record)


def test_authorization_is_calibration_only_and_commit_bound():
    validate_execution_authorization(
        _authorization(),
        execution_commit=EXECUTION_COMMIT,
    )
    for key, value in (
        ("calibration_execution_authorized", False),
        ("verification_execution_authorized", True),
        ("protected_holdout_execution_authorized", True),
        ("execution_commit", "b" * 40),
    ):
        changed = _authorization()
        changed[key] = value
        with pytest.raises(PermissionError):
            validate_execution_authorization(
                changed,
                execution_commit=EXECUTION_COMMIT,
            )


def test_task_set_rejects_authorization_before_creating_output(tmp_path):
    changed = _authorization()
    changed["calibration_execution_authorized"] = False
    output = tmp_path / "must-not-exist"
    with pytest.raises(PermissionError):
        execute_task_set(
            [_task()],
            output,
            authorization=changed,
            workers=1,
        )
    assert not output.exists()


def test_execution_subsets_must_be_complete_cells():
    task = _task()
    with pytest.raises(ValueError, match="complete candidate-family-scale"):
        _execution_cells([task])
    cell = [
        candidate
        for candidate in build_task_plan(
            "calibration",
            execution_commit=EXECUTION_COMMIT,
            planning_only=False,
        )
        if (
            candidate.policy_id,
            candidate.family,
            candidate.scale,
        )
        == (task.policy_id, task.family, task.scale)
    ]
    assert len(cell) == 20
    assert list(_execution_cells(cell).values()) == [cell]


def test_completed_disabled_shard_has_exact_contract():
    task = _task()
    shard = build_completed_shard(
        task,
        [_episode(index) for index in range(30)],
        wall_time_ms=12.5,
        peak_rss_bytes=1234,
    )
    assert shard["calibration_shard_version"] == CALIBRATION_SHARD_VERSION
    assert shard["raw_run"]["primary_utility"] == 1.0
    assert shard["raw_run"]["primary_effect_vs_disabled"] == 0.0
    assert shard["raw_run"]["override_count"] == 0
    assert shard["raw_run"]["holdout_accessed"] is False
    assert len(shard["episodes"]) == 30
    validate_calibration_shard(shard, task)


def test_completed_shard_requires_all_episodes():
    with pytest.raises(ValueError, match="requires 30"):
        build_completed_shard(
            _task(),
            [_episode(index) for index in range(29)],
            wall_time_ms=1.0,
            peak_rss_bytes=1,
        )


def test_timeout_shard_retains_completed_episode_evidence():
    task = _task()
    shard = algorithm_timeout_shard(
        task,
        wall_time_ms=100.0,
        completed_episodes=[_episode(0), _episode(1)],
    )
    assert shard["raw_run"]["status"] == "algorithm_timeout"
    assert shard["raw_run"]["primary_utility"] == 0.0
    assert shard["raw_run"]["episode_count_completed"] == 2
    assert len(shard["episodes"]) == 2
    validate_calibration_shard(shard, task)


def test_hard_process_timeout_does_not_execute_calibration_worker():
    task = _task()
    shard = execute_calibration_task_bounded(
        task.to_dict(),
        timeout_seconds=0.05,
        worker=_sleep_worker,
    )
    assert shard["raw_run"]["status"] == "algorithm_timeout"
    assert shard["raw_run"]["primary_utility"] == 0.0
    assert shard["raw_run"]["episode_count_completed"] == 0


def test_atomic_shard_load_and_resume_validation(tmp_path):
    task = _task()
    shard = build_completed_shard(
        task,
        [_episode(index) for index in range(30)],
        wall_time_ms=1.0,
        peak_rss_bytes=1,
    )
    path = tmp_path / task.shard_name
    path.write_text(json.dumps(shard), encoding="utf-8")
    assert load_calibration_shard(path, task) == shard

    tampered = copy.deepcopy(shard)
    tampered["raw_run"]["primary_utility"] = 0.0
    path.write_text(json.dumps(tampered), encoding="utf-8")
    assert load_calibration_shard(path, task) is None


def test_infrastructure_failure_is_retained_and_not_resumable(tmp_path):
    task = _task()
    failure = {
        "calibration_shard_version": CALIBRATION_SHARD_VERSION,
        "task": task.to_dict(),
        "infrastructure_error": {"type": "Synthetic", "message": "test"},
    }
    first = _write_failure_artifact(tmp_path, task, failure)
    second = _write_failure_artifact(tmp_path, task, failure)
    assert first.is_file()
    assert second.is_file()
    assert first != second
    assert load_calibration_shard(first, task) is None


def test_shard_rejects_task_identity_drift():
    task = _task()
    shard = build_completed_shard(
        task,
        [_episode(index) for index in range(30)],
        wall_time_ms=1.0,
        peak_rss_bytes=1,
    )
    changed = copy.deepcopy(shard)
    changed["task"]["seed"] = 2001
    with pytest.raises(ValueError, match="identity"):
        validate_calibration_shard(changed, task)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda shard: shard["episodes"][0].update(split="verification"),
        lambda shard: shard["episodes"][0].update(holdout_accessed=True),
        lambda shard: shard["episodes"][0].update(episode_index=2),
        lambda shard: shard["raw_run"].update(policy_id="margin_020"),
        lambda shard: shard["raw_run"].update(infrastructure_failure=True),
    ],
)
def test_shard_rejects_rehashed_leakage_or_nested_identity_drift(mutation):
    task = _task()
    shard = build_completed_shard(
        task,
        [_episode(index) for index in range(30)],
        wall_time_ms=1.0,
        peak_rss_bytes=1,
    )
    mutation(shard)
    payload = copy.deepcopy(shard)
    payload.pop("shard_sha256")
    shard["shard_sha256"] = _sha256_value(payload)
    with pytest.raises(ValueError):
        validate_calibration_shard(shard, task)


def test_branch_classification_uses_threshold_and_marks_unresolved():
    records = [
        {
            "support_margin": 0.10,
            "delta_utility": 0.20,
            "greedy_branch": {"terminal_reason": "goal_reached"},
            "lookahead_branch": {"terminal_reason": "goal_reached"},
        },
        {
            "support_margin": 0.20,
            "delta_utility": -0.20,
            "greedy_branch": {"terminal_reason": "goal_reached"},
            "lookahead_branch": {"terminal_reason": "goal_reached"},
        },
        {
            "support_margin": 0.30,
            "delta_utility": 0.50,
            "greedy_branch": {"terminal_reason": "path_cap_hit"},
            "lookahead_branch": {"terminal_reason": "goal_reached"},
        },
    ]
    classified = _classify_branches(
        OverrideGateMode.FIXED,
        0.20,
        records,
    )
    assert classified == {
        "attributed_override_count": 2,
        "beneficial_overrides": 0,
        "neutral_overrides": 0,
        "harmful_overrides": 1,
        "severe_harmful_overrides": 1,
        "unresolved_overrides": 1,
        "paired_utility_difference": pytest.approx(-0.20),
    }


def test_github_workflow_is_planning_only():
    workflow = (
        Path(__file__).parents[1]
        / ".github"
        / "workflows"
        / "override-gate-calibration-plan.yml"
    ).read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert 'python -m pip install -e ".[science]" pytest' in workflow
    assert "override_gate_calibration_runner dry-run" in workflow
    assert "python -m e0_controller.override_gate_calibration_pipeline" not in workflow
    assert "run-batch" not in workflow
    assert "consolidate" not in workflow
    assert "verification" not in workflow
    assert "protected_holdout" not in workflow


def test_consolidation_refuses_incomplete_calibration(tmp_path):
    with pytest.raises(RuntimeError, match="0/2880 valid shards"):
        consolidate_calibration(
            tmp_path,
            execution_commit=EXECUTION_COMMIT,
        )
    assert not (tmp_path / "selection_report.json").exists()
