"""Safety, separation, and accounting tests for WP-GATE-0.10."""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from .override_gate_v2_development import (
    STAGE_A,
    STAGE_B,
    V2DevelopmentCase,
    compare_control_replays,
    decision_trace_sha256,
    default_v2_cases,
    execute_v2_case_bounded,
    run_v2_development_pilot,
    summarize_v2_episode,
)


def _sleep_worker(payload):
    time.sleep(5)
    raise AssertionError("worker should have been terminated")


def _decision(*, disagreement: bool = True, override: bool = False):
    return SimpleNamespace(
        state="S",
        greedy_action="A",
        preferred_action="B" if disagreement else "A",
        selected_action="B" if override else "A",
        path_family_signature="abc",
        path_cap_hit=False,
        confidence=0.2,
        path_imbalance=1.0,
        override=override,
        phase_regime="gradient",
    )


def _episode(*, paired=(), decisions=None):
    return SimpleNamespace(
        summary=SimpleNamespace(
            to_record=lambda: {
                "goal_reached": True,
                "interactions_used": 2,
                "terminal_reason": "goal_reached",
            }
        ),
        decision_records=tuple(decisions or (_decision(),)),
        paired_decisions=tuple(paired),
    )


def _branch():
    return SimpleNamespace(to_record=lambda: {"delta_utility": -1.0})


def test_v2_case_rejects_non_development_seed():
    with pytest.raises(ValueError):
        V2DevelopmentCase(
            stage=STAGE_A,
            scale=100,
            seed=2000,
            policy_id="gate_disabled",
            max_paired_branches=1,
        )


def test_v2_stage_contracts_reject_cross_contamination():
    with pytest.raises(ValueError, match="gate_disabled"):
        V2DevelopmentCase(
            stage=STAGE_A,
            scale=100,
            seed=0,
            policy_id="margin_000",
            max_paired_branches=1,
        )
    with pytest.raises(ValueError, match="cannot collect"):
        V2DevelopmentCase(
            stage=STAGE_B,
            scale=100,
            seed=0,
            policy_id="gate_disabled",
            max_paired_branches=1,
        )


def test_default_v2_cases_are_small_and_stage_separated():
    cases = default_v2_cases()
    assert len(cases) == 8
    assert {case.seed for case in cases} == {0}
    assert {case.scale for case in cases} == {100, 500, 1000}
    assert sum(case.stage == STAGE_A for case in cases) == 3
    assert sum(case.stage == STAGE_B for case in cases) == 5
    assert all(
        case.max_paired_branches == 1
        for case in cases
        if case.stage == STAGE_A
    )
    assert all(
        case.max_paired_branches is None
        for case in cases
        if case.stage == STAGE_B
    )


def test_stage_summaries_keep_parent_and_instrumentation_timing_distinct():
    stage_a = V2DevelopmentCase(
        stage=STAGE_A,
        scale=100,
        seed=0,
        policy_id="gate_disabled",
        max_paired_branches=1,
    )
    stage_b = V2DevelopmentCase(
        stage=STAGE_B,
        scale=100,
        seed=0,
        policy_id="margin_000",
    )
    a_record = summarize_v2_episode(
        stage_a,
        _episode(paired=(_branch(),)),
        wall_time_ms=12.5,
    )
    b_record = summarize_v2_episode(
        stage_b,
        _episode(decisions=(_decision(override=True),)),
        wall_time_ms=2.5,
    )
    assert a_record["instrumentation_wall_time_ms"] == 12.5
    assert a_record["parent_wall_time_ms"] is None
    assert a_record["sampled_paired_branch_count"] == 1
    assert b_record["instrumentation_wall_time_ms"] is None
    assert b_record["parent_wall_time_ms"] == 2.5
    assert b_record["sampled_paired_branch_count"] == 0
    assert b_record["executed_override_count"] == 1
    assert b_record["protected_holdout_accessed"] is False


def test_parent_trace_digest_is_deterministic_and_action_sensitive():
    first = decision_trace_sha256((_decision(),))
    second = decision_trace_sha256((_decision(),))
    changed = decision_trace_sha256((_decision(override=True),))
    assert first == second
    assert first != changed
    assert len(first) == 64


def test_control_replay_comparison_requires_summary_and_trace_equality():
    records = []
    for scale in (100, 500, 1000):
        common = {
            "scale": scale,
            "policy_id": "gate_disabled",
            "worker_status": "completed",
            "parent": {"goal_reached": True},
            "parent_decision_trace_sha256": "a" * 64,
        }
        records.append({**common, "stage": STAGE_A})
        records.append({**common, "stage": STAGE_B})
    comparisons = compare_control_replays(records)
    assert len(comparisons) == 3
    assert all(item["parent_invariance_pass"] for item in comparisons)
    records[-1]["parent_decision_trace_sha256"] = "b" * 64
    assert compare_control_replays(records)[-1]["parent_invariance_pass"] is False


def test_v2_bounded_case_terminates_sleeping_worker():
    case = V2DevelopmentCase(
        stage=STAGE_B,
        scale=100,
        seed=0,
        policy_id="gate_disabled",
    )
    result = execute_v2_case_bounded(
        case,
        timeout_seconds=0.05,
        worker=_sleep_worker,
    )
    assert result["worker_status"] == "prototype_timeout"
    assert result["stage"] == STAGE_B
    assert result["not_gate_result"] is True


def test_v2_pilot_rejects_empty_case_list():
    with pytest.raises(ValueError, match="at least one"):
        run_v2_development_pilot([])
