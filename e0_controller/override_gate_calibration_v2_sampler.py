"""Outcome-blind deterministic Stage-A sampling for override-gate v2."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Mapping, Sequence

from .g1_domains import validate_development_seed
from .override_gate_calibration_v2 import (
    instance_sha256,
    load_calibration_instance_v2,
    seeds_for_split_v2,
)

STAGE_B_TRACE_SCHEMA_VERSION = 1
STAGE_A_SAMPLE_MANIFEST_SCHEMA_VERSION = 1


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _full_sha256(value: Any) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", str(value)))


def _active_policy_ids(instance: Mapping[str, Any]) -> set[str]:
    return {
        str(candidate["policy_id"])
        for candidate in instance["candidate_policies"]
        if candidate["policy_id"] != "gate_disabled"
    }


def _validate_split_seed(seed: int, split: str, instance: Mapping[str, Any]) -> None:
    """Permit seed 0 only for explicitly labelled no-result diagnostics."""
    if split == "development":
        validate_development_seed(seed)
        return
    if seed not in seeds_for_split_v2(split, instance):
        raise ValueError("Seed lies outside its frozen split")


def _identity_from_trace(trace: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "instance_id": trace["instance_id"],
        "policy_id": trace["policy_id"],
        "domain_family": trace["domain_family"],
        "scale": int(trace["scale"]),
        "generator_seed": int(trace["generator_seed"]),
    }


def validate_stage_b_trace(
    trace: Mapping[str, Any],
    *,
    split: str = "calibration",
    instance: Mapping[str, Any] | None = None,
) -> None:
    """Validate one complete active-candidate Stage-B trace without outcomes."""
    document = load_calibration_instance_v2() if instance is None else instance
    required = {
        "trace_schema_version",
        "artifact_kind",
        "instance_id",
        "instance_sha256",
        "split",
        "policy_id",
        "domain_family",
        "scale",
        "generator_seed",
        "trace_complete",
        "parent_decision_trace_sha256",
        "decision_records",
        "holdout_accessed",
        "not_gate_result",
    }
    missing = required.difference(trace)
    if missing:
        raise ValueError(f"Stage-B trace missing fields: {sorted(missing)}")
    if trace["trace_schema_version"] != STAGE_B_TRACE_SCHEMA_VERSION:
        raise ValueError("Unknown Stage-B trace schema")
    if trace["artifact_kind"] != "override_gate_v2_stage_b_decision_trace":
        raise ValueError("Wrong Stage-B trace artifact kind")
    if trace["instance_id"] != document["instance_id"]:
        raise ValueError("Stage-B trace references another instance")
    if trace["instance_sha256"] != instance_sha256(document):
        raise ValueError("Stage-B trace instance digest changed")
    if trace["split"] != split:
        raise ValueError("Stage-B trace split mismatch")
    if trace["policy_id"] not in _active_policy_ids(document):
        raise ValueError("Stage-A sampling accepts active candidates only")
    if trace["domain_family"] not in document["domain_manifest"]["families"]:
        raise ValueError("Unknown Stage-B domain family")
    if int(trace["scale"]) not in document["domain_manifest"]["scales"]:
        raise ValueError("Unknown Stage-B scale")
    try:
        _validate_split_seed(int(trace["generator_seed"]), split, document)
    except ValueError as error:
        raise ValueError("Stage-B seed lies outside its frozen split") from error
    if trace["trace_complete"] is not True:
        raise ValueError("Stage-A sampling requires a complete Stage-B trace")
    if not _full_sha256(trace["parent_decision_trace_sha256"]):
        raise ValueError("Parent decision trace digest must be a SHA-256")
    expected_holdout = split == "protected_holdout"
    if trace["holdout_accessed"] is not expected_holdout:
        raise ValueError("Stage-B holdout flag contradicts its split")
    if trace["not_gate_result"] is not True:
        raise ValueError("Stage-B trace must remain not_gate_result=true")
    if split == "development":
        for field in (
            "calibration_executed",
            "verification_executed",
            "protected_holdout_accessed",
        ):
            if trace.get(field) is not False:
                raise ValueError(
                    f"Development Stage-B trace requires {field}=false"
                )
    records = trace["decision_records"]
    if not isinstance(records, list):
        raise ValueError("Stage-B decision_records must be a list")
    seen = set()
    for record in records:
        required_decision = {
            "phase",
            "episode_index",
            "interaction_index",
            "state",
            "greedy_action",
            "preferred_action",
            "selected_action",
            "override",
        }
        decision_missing = required_decision.difference(record)
        if decision_missing:
            raise ValueError(
                f"Stage-B decision missing fields: {sorted(decision_missing)}"
            )
        identity = (int(record["episode_index"]), int(record["interaction_index"]))
        if identity in seen:
            raise ValueError("Stage-B decision identity is duplicated")
        seen.add(identity)
        if record["phase"] not in {"adaptation", "evaluation"}:
            raise ValueError("Unknown Stage-B decision phase")
        if not isinstance(record["override"], bool):
            raise ValueError("Stage-B override flag must be boolean")
        if record["override"]:
            if record["phase"] != "evaluation":
                continue
            if record["greedy_action"] is None or record["preferred_action"] is None:
                raise ValueError("Executed override requires both compared actions")
            if record["greedy_action"] == record["preferred_action"]:
                raise ValueError("Executed override requires action disagreement")
            if record["selected_action"] != record["preferred_action"]:
                raise ValueError("Executed override must select the preferred action")


def sample_priority(
    trace: Mapping[str, Any],
    decision: Mapping[str, Any],
    *,
    instance: Mapping[str, Any] | None = None,
) -> str:
    """Hash only the frozen identity fields; no outcome field is accepted."""
    document = load_calibration_instance_v2() if instance is None else instance
    fields = tuple(document["stage_a_paired_evidence"]["sample_priority_fields"])
    values = {
        **_identity_from_trace(trace),
        "episode_index": int(decision["episode_index"]),
        "interaction_index": int(decision["interaction_index"]),
        "state": decision["state"],
        "greedy_action": decision["greedy_action"],
        "preferred_action": decision["preferred_action"],
    }
    if set(values) != set(fields):
        raise RuntimeError("Sampler identity implementation drifted from the instance")
    payload = {
        "salt": document["seed_derivation"]["stage_a_sampler_salt"],
        "identity": {field: values[field] for field in fields},
    }
    return _sha256(payload)


def build_stage_a_sample_manifest(
    trace: Mapping[str, Any],
    *,
    split: str = "calibration",
    instance: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Select the lowest frozen hash priorities from evaluation overrides."""
    document = load_calibration_instance_v2() if instance is None else instance
    validate_stage_b_trace(trace, split=split, instance=document)
    candidates: List[Dict[str, Any]] = []
    for decision in trace["decision_records"]:
        if decision["phase"] != "evaluation" or decision["override"] is not True:
            continue
        candidates.append(
            {
                "sample_priority_sha256": sample_priority(
                    trace,
                    decision,
                    instance=document,
                ),
                "episode_index": int(decision["episode_index"]),
                "interaction_index": int(decision["interaction_index"]),
                "state": decision["state"],
                "greedy_action": decision["greedy_action"],
                "preferred_action": decision["preferred_action"],
            }
        )
    ordered = sorted(
        candidates,
        key=lambda item: (
            item["sample_priority_sha256"],
            item["episode_index"],
            item["interaction_index"],
        ),
    )
    cap = int(
        document["stage_a_paired_evidence"]["sample_cap_per_candidate_replicate"]
    )
    manifest = {
        "sample_manifest_schema_version": STAGE_A_SAMPLE_MANIFEST_SCHEMA_VERSION,
        "artifact_kind": "override_gate_v2_stage_a_sample_manifest",
        "instance_id": document["instance_id"],
        "instance_sha256": instance_sha256(document),
        "split": split,
        **{key: value for key, value in _identity_from_trace(trace).items() if key != "instance_id"},
        "parent_decision_trace_sha256": trace["parent_decision_trace_sha256"],
        "sampling_frame_override_count": len(candidates),
        "sample_cap": cap,
        "sample_count": min(len(candidates), cap),
        "selected_decisions": ordered[:cap],
        "manual_sampling_permitted": False,
        "outcome_fields_in_priority": False,
        "holdout_accessed": split == "protected_holdout",
        "not_gate_result": True,
    }
    payload = dict(manifest)
    manifest["sample_manifest_sha256"] = _sha256(payload)
    validate_stage_a_sample_manifest(manifest, split=split, instance=document)
    return manifest


def validate_stage_a_sample_manifest(
    manifest: Mapping[str, Any],
    *,
    split: str = "calibration",
    instance: Mapping[str, Any] | None = None,
) -> None:
    """Reject any changed ordering, count, provenance, or execution flag."""
    document = load_calibration_instance_v2() if instance is None else instance
    required = {
        "sample_manifest_schema_version",
        "artifact_kind",
        "instance_id",
        "instance_sha256",
        "split",
        "policy_id",
        "domain_family",
        "scale",
        "generator_seed",
        "parent_decision_trace_sha256",
        "sampling_frame_override_count",
        "sample_cap",
        "sample_count",
        "selected_decisions",
        "manual_sampling_permitted",
        "outcome_fields_in_priority",
        "holdout_accessed",
        "not_gate_result",
        "sample_manifest_sha256",
    }
    missing = required.difference(manifest)
    if missing:
        raise ValueError(f"Stage-A sample manifest missing fields: {sorted(missing)}")
    if manifest["sample_manifest_schema_version"] != STAGE_A_SAMPLE_MANIFEST_SCHEMA_VERSION:
        raise ValueError("Unknown Stage-A sample manifest schema")
    if manifest["artifact_kind"] != "override_gate_v2_stage_a_sample_manifest":
        raise ValueError("Wrong Stage-A sample artifact kind")
    if manifest["instance_id"] != document["instance_id"]:
        raise ValueError("Stage-A manifest references another instance")
    if manifest["instance_sha256"] != instance_sha256(document):
        raise ValueError("Stage-A manifest instance digest changed")
    if manifest["split"] != split:
        raise ValueError("Stage-A manifest split mismatch")
    if manifest["policy_id"] not in _active_policy_ids(document):
        raise ValueError("Stage-A manifest policy is not active")
    try:
        _validate_split_seed(int(manifest["generator_seed"]), split, document)
    except ValueError as error:
        raise ValueError("Stage-A manifest seed lies outside its split") from error
    if manifest["manual_sampling_permitted"] is not False:
        raise ValueError("Manual Stage-A sampling is forbidden")
    if manifest["outcome_fields_in_priority"] is not False:
        raise ValueError("Outcome-dependent Stage-A sampling is forbidden")
    cap = int(
        document["stage_a_paired_evidence"]["sample_cap_per_candidate_replicate"]
    )
    if manifest["sample_cap"] != cap:
        raise ValueError("Stage-A sample cap changed")
    selected = manifest["selected_decisions"]
    if not isinstance(selected, list) or len(selected) != manifest["sample_count"]:
        raise ValueError("Stage-A selected decision count is inconsistent")
    expected_count = min(int(manifest["sampling_frame_override_count"]), cap)
    if int(manifest["sample_count"]) != expected_count:
        raise ValueError("Stage-A sample count violates the frozen cap rule")
    priorities = [item["sample_priority_sha256"] for item in selected]
    if any(not _full_sha256(priority) for priority in priorities):
        raise ValueError("Stage-A sample priority must be SHA-256")
    if priorities != sorted(priorities) or len(priorities) != len(set(priorities)):
        raise ValueError("Stage-A samples must have unique ascending priorities")
    expected_holdout = split == "protected_holdout"
    if manifest["holdout_accessed"] is not expected_holdout:
        raise ValueError("Stage-A holdout flag contradicts its split")
    if manifest["not_gate_result"] is not True:
        raise ValueError("Stage-A manifest must remain not_gate_result=true")
    payload = dict(manifest)
    recorded = payload.pop("sample_manifest_sha256")
    if recorded != _sha256(payload):
        raise ValueError("Stage-A sample manifest digest changed")


def build_sample_manifests(
    traces: Sequence[Mapping[str, Any]],
    *,
    split: str = "calibration",
    instance: Mapping[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """Build unique manifests in stable replicate identity order."""
    document = load_calibration_instance_v2() if instance is None else instance
    manifests = [
        build_stage_a_sample_manifest(trace, split=split, instance=document)
        for trace in traces
    ]
    identities = [
        (
            item["policy_id"],
            item["domain_family"],
            int(item["scale"]),
            int(item["generator_seed"]),
        )
        for item in manifests
    ]
    if len(identities) != len(set(identities)):
        raise ValueError("Duplicate Stage-A replicate trace")
    return [
        item
        for _, item in sorted(
            zip(identities, manifests),
            key=lambda pair: pair[0],
        )
    ]
