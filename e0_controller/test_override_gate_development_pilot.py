"""Development-only safety and accounting tests for WP-GATE-0.9."""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from .override_gate_calibration_engine import BranchOutcome
from .override_gate_development_pilot import (
    DevelopmentPilotCase,
    default_pilot_cases,
    execute_pilot_case_bounded,
    run_development_pilot,
    summarize_pilot_episode,
)


def _sleep_worker(payload):
    time.sleep(5)
    raise AssertionError("worker should have been terminated")


def _record(*, disagreement: bool, override: bool = False):
    return SimpleNamespace(
        preferred_action="B" if disagreement else "A",
        greedy_action="A",
        override=override,
    )


def _branch(*, margin: float = 0.2, delta: float = -1.0):
    greedy = BranchOutcome(
        first_action="A",
        first_outcome="success",
        utility=1.0,
        goal_reached=True,
        interactions_used=3,
        terminal_reason="goal_reached",
        final_state="G",
        path=("S", "A", "G"),
    )
    lookahead = BranchOutcome(
        first_action="B",
        first_outcome="success",
        utility=1.0 + delta,
        goal_reached=False,
        interactions_used=8,
        terminal_reason="interaction_budget_exhausted",
        final_state="B",
        path=("S", "B"),
    )
    return SimpleNamespace(
        greedy=greedy,
        lookahead=lookahead,
        interaction_index=1,
        support_margin=margin,
        delta_utility=delta,
        to_record=lambda: {"support_margin": margin, "delta_utility": delta},
    )


def test_case_rejects_non_development_seed():
    with pytest.raises(ValueError):
        DevelopmentPilotCase(scale=100, seed=2000, policy_id="gate_disabled")


@pytest.mark.parametrize("budget", [0, 41])
def test_case_rejects_unbounded_interaction_budget(budget):
    with pytest.raises(ValueError, match="interaction budget"):
        DevelopmentPilotCase(
            scale=100,
            seed=0,
            policy_id="gate_disabled",
            interaction_budget=budget,
        )


def test_default_cases_are_small_development_only_matrix():
    cases = default_pilot_cases()
    assert len(cases) == 8
    assert {case.seed for case in cases} == {0}
    assert {case.scale for case in cases} == {100, 500, 1000}
    assert all(case.interaction_budget == 8 for case in cases)
    assert sum(case.collect_paired_branches for case in cases) == 5
    assert all(
        case.policy_id == "gate_disabled"
        for case in cases
        if not case.collect_paired_branches
    )


def test_parent_only_case_rejects_active_policy():
    with pytest.raises(ValueError, match="gate_disabled"):
        DevelopmentPilotCase(
            scale=100,
            seed=0,
            policy_id="margin_000",
            collect_paired_branches=False,
        )


def test_summary_separates_funnel_and_branch_amplification():
    case = DevelopmentPilotCase(scale=100, seed=0, policy_id="margin_000")
    summary = SimpleNamespace(to_record=lambda: {"interactions_used": 8})
    episode = SimpleNamespace(
        summary=summary,
        decision_records=(
            _record(disagreement=True, override=True),
            _record(disagreement=True),
            _record(disagreement=False),
        ),
        paired_decisions=(_branch(),),
    )
    result = summarize_pilot_episode(case, episode, wall_time_ms=12.5)
    assert result["observed_disagreement_count"] == 2
    assert result["eligible_disagreement_count"] == 1
    assert result["override_count"] == 1
    assert result["paired_branch_interactions"] == 9
    assert result["geometry_decision_count_lower_bound"] == 12
    assert result["geometry_decision_amplification"] == 4.0
    assert result["harmful_branch_count"] == 1
    assert result["split"] == "development"
    assert result["calibration_executed"] is False
    assert result["protected_holdout_accessed"] is False


def test_bounded_case_terminates_sleeping_worker():
    case = DevelopmentPilotCase(scale=100, seed=0, policy_id="gate_disabled")
    result = execute_pilot_case_bounded(
        case,
        timeout_seconds=0.05,
        worker=_sleep_worker,
    )
    assert result["worker_status"] == "pilot_timeout"
    assert result["split"] == "development"
    assert result["not_gate_result"] is True


def test_pilot_rejects_empty_case_list():
    with pytest.raises(ValueError, match="at least one"):
        run_development_pilot([])
