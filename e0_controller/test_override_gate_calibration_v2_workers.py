"""Distribution-boundary tests for WP-GATE-0.13."""

from __future__ import annotations

import copy
import json
import time

import pytest

from .g1_domains import build_domain
from .override_gate_calibration_engine import (
    build_calibration_domain,
    candidate_policy,
    run_instrumented_episode,
)
from .override_gate_calibration_v2_sampler import build_stage_a_sample_manifest
from .override_gate_calibration_v2_workers import (
    DevelopmentReplicateCase,
    build_attempt_envelope,
    consolidate_latest_attempts,
    execute_stage_a_replay,
    execute_stage_b_bounded,
    execute_stage_b_trace,
    validate_attempt_envelope,
    write_attempt_atomic,
)


def _sleep_worker(payload):
    time.sleep(5)
    raise AssertionError("bounded worker should have been terminated")


def _error_worker(payload):
    raise RuntimeError("synthetic child failure")


def test_worker_case_rejects_control_and_non_development_seed():
    with pytest.raises(ValueError, match="active candidate"):
        DevelopmentReplicateCase(policy_id="gate_disabled")
    with pytest.raises(ValueError):
        DevelopmentReplicateCase(seed=5000)


def test_exact_branch_keys_are_development_only():
    domain = build_calibration_domain("wall_grid", 100, 2000)
    with pytest.raises(PermissionError, match="development-diagnostic"):
        run_instrumented_episode(
            domain,
            candidate_policy("margin_000"),
            10,
            interaction_budget=10,
            paired_branch_decision_keys={(10, 0)},
        )


def test_exact_branch_key_collects_only_selected_decision():
    domain = build_domain("wall_grid", 100, 0)
    policy = candidate_policy("margin_000")
    parent = run_instrumented_episode(
        domain,
        policy,
        10,
        interaction_budget=40,
        collect_paired_branches=False,
    )
    selected = next(
        index for index, decision in enumerate(parent.decision_records) if decision.override
    )
    replay = run_instrumented_episode(
        domain,
        policy,
        10,
        interaction_budget=40,
        paired_branch_decision_keys={(10, selected)},
    )
    assert len(replay.paired_decisions) == 1
    assert replay.paired_decisions[0].interaction_index == selected
    assert replay.summary == parent.summary
    assert replay.decision_records == parent.decision_records


def test_stage_b_trace_is_complete_branch_free_and_sampleable():
    case = DevelopmentReplicateCase()
    trace = execute_stage_b_trace(case.to_dict())
    manifest = build_stage_a_sample_manifest(trace, split="development")
    assert trace["trace_complete"] is True
    assert trace["paired_branch_count"] == 0
    assert trace["generator_seed"] == 0
    assert trace["holdout_accessed"] is False
    assert trace["not_gate_result"] is True
    assert 0 < manifest["sample_count"] <= 4


def test_stage_b_timeout_is_algorithm_timeout_not_infrastructure_error():
    result = execute_stage_b_bounded(
        DevelopmentReplicateCase(), timeout_seconds=0.05, worker=_sleep_worker
    )
    assert result["worker_status"] == "algorithm_timeout"
    assert result["holdout_accessed"] is False
    assert result["not_gate_result"] is True


def test_stage_b_child_exception_is_infrastructure_error():
    result = execute_stage_b_bounded(
        DevelopmentReplicateCase(), timeout_seconds=1.0, worker=_error_worker
    )
    assert result["worker_status"] == "infrastructure_error"
    assert result["error_type"] == "RuntimeError"


def test_stage_a_replays_exact_trace_and_selected_pairs():
    case = DevelopmentReplicateCase()
    trace = execute_stage_b_trace(case.to_dict())
    result = execute_stage_a_replay(case, trace)
    assert result["worker_status"] == "completed"
    assert result["parent_replay_equal"] is True
    assert result["completed_pair_count"] == result["sample_manifest"]["sample_count"]
    assert all(pair["decision_replay_equal"] for pair in result["pairs"])
    assert result["protected_holdout_accessed"] is False
    assert result["not_gate_result"] is True


def test_stage_a_classifies_each_pair_timeout_as_unresolved():
    case = DevelopmentReplicateCase()
    trace = execute_stage_b_trace(case.to_dict())
    result = execute_stage_a_replay(
        case,
        trace,
        pair_timeout_seconds=0.05,
        pair_worker=_sleep_worker,
    )
    assert result["worker_status"] == "stage_a_unresolved"
    assert result["parent_replay_equal"] is True
    assert result["completed_pair_count"] == 0
    assert len(result["pairs"]) == result["sample_manifest"]["sample_count"]
    assert all(pair["pair_status"] == "stage_a_unresolved" for pair in result["pairs"])


def test_attempt_digest_rejects_record_mutation():
    envelope = build_attempt_envelope("cell.a", "stage_b", 1, {"status": "ok"})
    validate_attempt_envelope(envelope)
    changed = copy.deepcopy(envelope)
    changed["record"]["status"] = "changed"
    with pytest.raises(ValueError, match="digest changed"):
        validate_attempt_envelope(changed)


def test_atomic_attempt_is_write_once(tmp_path):
    envelope = build_attempt_envelope("cell.a", "stage_b", 1, {"status": "ok"})
    path = write_attempt_atomic(tmp_path, envelope)
    assert json.loads(path.read_text(encoding="utf-8")) == envelope
    with pytest.raises(FileExistsError, match="already exists"):
        write_attempt_atomic(tmp_path, envelope)


def test_consolidation_selects_latest_attempt_without_fallback(tmp_path):
    first = build_attempt_envelope("cell.a", "stage_b", 1, {"status": "old"})
    latest = build_attempt_envelope("cell.a", "stage_b", 2, {"status": "new"})
    paths = [write_attempt_atomic(tmp_path, first), write_attempt_atomic(tmp_path, latest)]
    result = consolidate_latest_attempts(paths, ["cell.a"])
    assert result["selected_latest_attempts_without_fallback"] is True
    assert result["selected_attempts"][0]["run_attempt"] == 2
    assert result["selected_attempts"][0]["record"]["status"] == "new"


def test_consolidation_rejects_corrupt_latest_instead_of_using_valid_old(tmp_path):
    first = build_attempt_envelope("cell.a", "stage_b", 1, {"status": "old"})
    old_path = write_attempt_atomic(tmp_path, first)
    corrupt_path = tmp_path / "cell.a.attempt-2.json"
    corrupt_path.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError, match="Newest attempt is unreadable"):
        consolidate_latest_attempts([old_path, corrupt_path], ["cell.a"])


def test_consolidation_rejects_missing_or_unexpected_cells(tmp_path):
    envelope = build_attempt_envelope("cell.a", "stage_a", 1, {"status": "ok"})
    path = write_attempt_atomic(tmp_path, envelope)
    with pytest.raises(ValueError, match="Missing attempt cells"):
        consolidate_latest_attempts([path], ["cell.a", "cell.b"])
    with pytest.raises(ValueError, match="Unexpected attempt cell"):
        consolidate_latest_attempts([path], ["cell.b"])
