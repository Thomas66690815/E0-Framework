"""No-outcome tests for the frozen v2 Stage-A sampler."""

from __future__ import annotations

import copy

import pytest

from .override_gate_calibration_v2 import instance_sha256
from .override_gate_calibration_v2_sampler import (
    build_sample_manifests,
    build_stage_a_sample_manifest,
    sample_priority,
    validate_stage_a_sample_manifest,
    validate_stage_b_trace,
)


def _decision(index: int, *, phase: str = "evaluation", override: bool = True):
    return {
        "phase": phase,
        "episode_index": 10 + index // 3,
        "interaction_index": index,
        "state": f"S{index}",
        "greedy_action": f"G{index}",
        "preferred_action": f"P{index}",
        "selected_action": f"P{index}" if override else f"G{index}",
        "override": override,
        "outcome": "ignored-by-sampler",
        "utility": 999.0,
    }


def _trace(*, decisions=None, policy_id="margin_000", seed=5000):
    return {
        "trace_schema_version": 1,
        "artifact_kind": "override_gate_v2_stage_b_decision_trace",
        "instance_id": "E0-OVERRIDE-GATE-CAL-INSTANCE-v2",
        "instance_sha256": instance_sha256(),
        "split": "calibration",
        "policy_id": policy_id,
        "domain_family": "wall_grid",
        "scale": 100,
        "generator_seed": seed,
        "trace_complete": True,
        "parent_decision_trace_sha256": "a" * 64,
        "decision_records": list(decisions or [_decision(i) for i in range(8)]),
        "holdout_accessed": False,
        "not_gate_result": True,
    }


def test_v2_sampler_selects_four_lowest_frozen_priorities():
    trace = _trace()
    manifest = build_stage_a_sample_manifest(trace)
    expected = sorted(
        (sample_priority(trace, decision), decision["interaction_index"])
        for decision in trace["decision_records"]
    )[:4]
    assert manifest["sampling_frame_override_count"] == 8
    assert manifest["sample_cap"] == 4
    assert manifest["sample_count"] == 4
    assert [
        (item["sample_priority_sha256"], item["interaction_index"])
        for item in manifest["selected_decisions"]
    ] == expected
    validate_stage_a_sample_manifest(manifest)


def test_v2_sampler_ignores_outcomes_and_input_order():
    first_trace = _trace()
    changed_trace = copy.deepcopy(first_trace)
    changed_trace["decision_records"].reverse()
    for item in changed_trace["decision_records"]:
        item["outcome"] = "changed"
        item["utility"] = -123.0
    first = build_stage_a_sample_manifest(first_trace)
    changed = build_stage_a_sample_manifest(changed_trace)
    assert first == changed


def test_v2_sampler_uses_evaluation_overrides_only():
    decisions = [
        _decision(0, phase="adaptation"),
        _decision(1, override=False),
        _decision(2),
    ]
    manifest = build_stage_a_sample_manifest(_trace(decisions=decisions))
    assert manifest["sampling_frame_override_count"] == 1
    assert manifest["sample_count"] == 1
    assert manifest["selected_decisions"][0]["interaction_index"] == 2


def test_v2_sampler_emits_valid_empty_manifest_for_zero_overrides():
    trace = _trace(decisions=[_decision(0, override=False)])
    manifest = build_stage_a_sample_manifest(trace)
    assert manifest["sampling_frame_override_count"] == 0
    assert manifest["sample_count"] == 0
    assert manifest["selected_decisions"] == []


def test_v2_sampler_rejects_disabled_policy_and_incomplete_trace():
    with pytest.raises(ValueError, match="active candidates only"):
        validate_stage_b_trace(_trace(policy_id="gate_disabled"))
    incomplete = _trace()
    incomplete["trace_complete"] = False
    with pytest.raises(ValueError, match="complete Stage-B trace"):
        validate_stage_b_trace(incomplete)


def test_v2_sampler_rejects_seed_outside_frozen_split():
    with pytest.raises(ValueError, match="outside its frozen split"):
        validate_stage_b_trace(_trace(seed=2000))


def test_v2_sampler_rejects_mutated_manifest_digest_and_order():
    manifest = build_stage_a_sample_manifest(_trace())
    changed = copy.deepcopy(manifest)
    changed["selected_decisions"].reverse()
    with pytest.raises(ValueError, match="ascending priorities"):
        validate_stage_a_sample_manifest(changed)
    changed = copy.deepcopy(manifest)
    changed["sampling_frame_override_count"] += 1
    with pytest.raises(ValueError, match="digest changed"):
        validate_stage_a_sample_manifest(changed)


def test_v2_sampler_rejects_duplicate_replicate_trace():
    trace = _trace()
    with pytest.raises(ValueError, match="Duplicate"):
        build_sample_manifests([trace, trace])


def test_v2_sampler_does_not_construct_fresh_split_domains(monkeypatch):
    from . import g1_domains

    def forbidden(*args, **kwargs):
        raise AssertionError("domain builder was called")

    monkeypatch.setattr(g1_domains, "build_domain", forbidden)
    manifest = build_stage_a_sample_manifest(_trace())
    assert manifest["sample_count"] == 4
