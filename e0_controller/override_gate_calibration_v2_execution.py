"""Authorization-gated calibration-only execution layer for gate v2.

The module can plan and seal manifests without outcomes.  Every public command
that can construct a fresh calibration domain first validates the external
authorization, exact execution manifest, and exact workflow bytes.
Verification and protected holdout are intentionally absent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import os
import re
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

from .g1_domains import BUILDERS, V2_CALIBRATION_SEED_NAMESPACE, validate_domain
from .override_gate_calibration_engine import (
    PairedBranchTimeoutError,
    candidate_policy,
    run_instrumented_episode,
)
from .override_gate_calibration_v2 import instance_sha256, load_calibration_instance_v2
from .override_gate_calibration_v2_authorization import (
    EXECUTION_MANIFEST_SCHEMA_VERSION,
    EXPECTED_CALIBRATION_SEEDS,
    EXPECTED_STAGE_A_CELL_COUNT,
    EXPECTED_STAGE_B_CELL_COUNT,
    authorization_sha256,
    load_and_validate_authorization,
    protocol_file_sha256,
    sha256_file,
    validate_execution_manifest,
)
from .override_gate_calibration_v2_runner import (
    STAGE_A,
    STAGE_B,
    V2CellTask,
    build_cell_plan,
    validate_artifact_record,
)
from .override_gate_calibration_v2_sampler import (
    build_stage_a_sample_manifest,
    validate_stage_b_trace,
)
from .override_gate_calibration_v2_statistics import (
    select_v2_calibration_policy,
    validate_stage_b_calibration_records,
)

CELL_ATTEMPT_SCHEMA_VERSION = 1
CONSOLIDATION_SCHEMA_VERSION = 1
DEFAULT_WORKERS = 4
WORKFLOW_PATH = (
    Path(__file__).resolve().parent.parent
    / ".github"
    / "workflows"
    / "override-gate-calibration-v2-execute.yml"
)
_ATTEMPT_NAME = re.compile(r"^(?P<cell>.+)\.attempt-(?P<attempt>[1-9][0-9]*)\.json$")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _full_commit(value: Any) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{40}", str(value)))


def _full_digest(value: Any) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", str(value)))


@dataclass(frozen=True)
class AuthorizedCalibrationContext:
    execution_commit: str
    authorization_sha256: str
    execution_manifest_sha256: str


def build_execution_manifest(
    execution_commit: str,
    *,
    outcome_workflow_path: Path = WORKFLOW_PATH,
) -> Dict[str, Any]:
    """Describe a reviewed execution commit without constructing a domain."""
    if not _full_commit(execution_commit):
        raise ValueError("Execution manifest requires a full commit")
    instance = load_calibration_instance_v2()
    workflow_digest = sha256_file(outcome_workflow_path)
    manifest = {
        "execution_manifest_schema_version": EXECUTION_MANIFEST_SCHEMA_VERSION,
        "artifact_kind": "override_gate_v2_execution_manifest",
        "instance_id": instance["instance_id"],
        "instance_sha256": instance_sha256(instance),
        "protocol_id": instance["protocol_id"],
        "protocol_file_sha256": protocol_file_sha256(),
        "source_commit": instance["source_commit"],
        "execution_commit": execution_commit,
        "outcome_workflow_sha256": workflow_digest,
        "authorized_split": "calibration",
        "stage_b_cell_count": EXPECTED_STAGE_B_CELL_COUNT,
        "stage_a_cell_count": EXPECTED_STAGE_A_CELL_COUNT,
        "calibration_generator_seeds": list(EXPECTED_CALIBRATION_SEEDS),
        "stage_separated": True,
        "branch_time_charged_to_parent": False,
        "latest_attempt_only": True,
        "fallback_to_earlier_attempt": False,
        "implementation_complete": True,
        "tests_passed": True,
        "verification_execution_enabled": False,
        "protected_holdout_execution_enabled": False,
        "protected_holdout_accessed": False,
        "not_gate_result": True,
    }
    validate_execution_manifest(
        manifest,
        execution_commit=execution_commit,
        outcome_workflow_sha256=workflow_digest,
        instance=instance,
    )
    return manifest


def build_no_outcome_execution_review() -> Dict[str, Any]:
    """Seal the executable-but-unauthorized repository state without domains."""
    stage_b = build_cell_plan("calibration", STAGE_B, planning_only=True)
    stage_a = build_cell_plan("calibration", STAGE_A, planning_only=True)
    return {
        "artifact_kind": "override_gate_v2_execution_layer_no_outcome_review",
        "work_package": "WP-GATE-0.15",
        "execution_layer_implemented": True,
        "manual_workflow_present": WORKFLOW_PATH.exists(),
        "outcome_workflow_sha256": sha256_file(WORKFLOW_PATH),
        "stage_b_cell_count": len(stage_b),
        "stage_a_cell_count": len(stage_a),
        "stage_b_replicate_count": sum(task.replicate_count for task in stage_b),
        "stage_a_replicate_count": sum(task.replicate_count for task in stage_a),
        "authorization_required_before_domain": True,
        "operational_authorization_record_present": False,
        "execution_manifest_present": False,
        "execution_commit_frozen": False,
        "authorization_request_ready": False,
        "outcome_commands_exposed_but_locked": True,
        "domains_instantiated": 0,
        "outcomes_observed": 0,
        "calibration_executed": False,
        "verification_executed": False,
        "protected_holdout_accessed": False,
        "holdout_accessed": False,
        "not_gate_result": True,
    }


def authorize_calibration_context(
    *,
    authorization_path: Path,
    authorization_digest: str,
    execution_commit: str,
    execution_manifest_path: Path,
    execution_manifest_digest: str,
    outcome_workflow_path: Path,
    confirmation: str,
) -> AuthorizedCalibrationContext:
    """Validate all external material before returning the only domain capability."""
    if not _full_digest(execution_manifest_digest):
        raise PermissionError("Execution manifest SHA-256 must be full lowercase hex")
    if sha256_file(execution_manifest_path) != execution_manifest_digest:
        raise PermissionError("Execution manifest SHA-256 mismatch")
    record = load_and_validate_authorization(
        authorization_path,
        expected_sha256=authorization_digest,
        execution_commit=execution_commit,
        execution_manifest_path=execution_manifest_path,
        outcome_workflow_path=outcome_workflow_path,
        confirmation=confirmation,
    )
    return AuthorizedCalibrationContext(
        execution_commit=execution_commit,
        authorization_sha256=authorization_sha256(record),
        execution_manifest_sha256=execution_manifest_digest,
    )


def build_calibration_domain_v2(
    context: AuthorizedCalibrationContext,
    family: str,
    scale: int,
    seed: int,
):
    """Construct only a frozen v2 calibration domain behind a validated context."""
    if not isinstance(context, AuthorizedCalibrationContext):
        raise PermissionError("Validated v2 calibration context required")
    instance = load_calibration_instance_v2()
    if family not in instance["domain_manifest"]["families"]:
        raise ValueError("Family lies outside v2 calibration")
    if scale not in instance["domain_manifest"]["scales"]:
        raise ValueError("Scale lies outside v2 calibration")
    if seed not in EXPECTED_CALIBRATION_SEEDS:
        raise PermissionError("Seed lies outside v2 calibration")
    domain = BUILDERS[family](
        scale,
        seed,
        seed_namespace=V2_CALIBRATION_SEED_NAMESPACE,
    )
    invariants = validate_domain(domain)
    if not all(item["passed"] for item in invariants):
        raise RuntimeError(f"V2 calibration domain invariants failed: {invariants}")
    return domain


def authorized_matrix(context: AuthorizedCalibrationContext, stage: str) -> Dict[str, Any]:
    tasks = build_cell_plan(
        "calibration",
        stage,
        execution_commit=context.execution_commit,
        planning_only=True,
    )
    return {
        "include": [
            {
                "cell_index": index,
                **task.to_dict(),
                "cell_sha256": _sha256(task.to_dict()),
            }
            for index, task in enumerate(tasks)
        ]
    }


def _task_for_cell(context: AuthorizedCalibrationContext, stage: str, index: int) -> V2CellTask:
    tasks = build_cell_plan(
        "calibration",
        stage,
        execution_commit=context.execution_commit,
        planning_only=True,
    )
    if not 0 <= index < len(tasks):
        raise ValueError("Cell index is outside the frozen matrix")
    return tasks[index]


@contextmanager
def _deadline(seconds: float):
    if not hasattr(signal, "SIGALRM"):
        yield
        return

    def alarm_handler(signum: int, frame: Any) -> None:
        raise TimeoutError(f"Episode exceeded {seconds} seconds")

    previous = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, alarm_handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, previous)


def _decision_record(record: Any, episode_index: int, interaction_index: int) -> Dict[str, Any]:
    return {
        "phase": "adaptation" if episode_index < 10 else "evaluation",
        "episode_index": episode_index,
        "interaction_index": interaction_index,
        "state": record.state,
        "greedy_action": record.greedy_action,
        "preferred_action": record.preferred_action,
        "selected_action": record.selected_action,
        "path_family_signature": record.path_family_signature,
        "path_cap_hit": record.path_cap_hit,
        "confidence": record.confidence,
        "path_imbalance": record.path_imbalance,
        "override": record.override,
        "phase_regime": record.phase_regime,
    }


def _trace_digest(records: Sequence[Mapping[str, Any]]) -> str:
    return _sha256(list(records))


def _stage_b_payload(task: V2CellTask, seed: int) -> Dict[str, Any]:
    return {
        "task": task.to_dict(),
        "seed": seed,
    }


def _stage_b_replicate(payload: Mapping[str, Any]) -> Dict[str, Any]:
    task = dict(payload["task"])
    seed = int(payload["seed"])
    instance = load_calibration_instance_v2()
    domain = BUILDERS[str(task["family"])](
        int(task["scale"]),
        seed,
        seed_namespace=V2_CALIBRATION_SEED_NAMESPACE,
    )
    policy = candidate_policy(str(task["policy_id"]))
    timeout = float(instance["timeouts"]["stage_b_episode_seconds"])
    decisions: List[Dict[str, Any]] = []
    summaries: List[Dict[str, Any]] = []
    status = "completed"
    started = time.perf_counter()
    for episode_index in range(30):
        try:
            with _deadline(timeout):
                result = run_instrumented_episode(
                    domain,
                    policy,
                    episode_index,
                    collect_paired_branches=False,
                )
        except (MemoryError, TimeoutError) as error:
            status = (
                "method_out_of_memory" if isinstance(error, MemoryError) else "algorithm_timeout"
            )
            break
        summaries.append(result.summary.to_record())
        decisions.extend(
            _decision_record(record, episode_index, interaction_index)
            for interaction_index, record in enumerate(result.decision_records)
        )
    evaluation = [item for item in summaries if int(item["episode_index"]) >= 10]
    evaluation_decisions = [item for item in decisions if item["phase"] == "evaluation"]
    path_caps = sum(bool(item["path_cap_hit"]) for item in evaluation_decisions)
    if status == "completed" and path_caps:
        status = "path_cap_hit"
    primary_utility = (
        mean(float(item["success_adjusted_efficiency"]) for item in evaluation)
        if status == "completed" and len(evaluation) == 20
        else 0.0
    )
    observed = sum(
        item["greedy_action"] is not None
        and item["preferred_action"] is not None
        and item["greedy_action"] != item["preferred_action"]
        for item in evaluation_decisions
    )
    candidate = candidate_policy(str(task["policy_id"]))
    eligible = sum(
        not item["path_cap_hit"]
        and item["greedy_action"] is not None
        and item["preferred_action"] is not None
        and item["greedy_action"] != item["preferred_action"]
        and candidate.max_path_imbalance is not None
        and float(item["path_imbalance"]) <= float(candidate.max_path_imbalance)
        for item in evaluation_decisions
    )
    overrides = sum(bool(item["override"]) for item in evaluation_decisions)
    common = {
        "instance_id": instance["instance_id"],
        "instance_sha256": instance_sha256(instance),
        "source_commit": instance["source_commit"],
        "execution_commit": task["execution_commit"],
        "split": "calibration",
        "domain_family": task["family"],
        "scale": int(task["scale"]),
        "generator_seed": seed,
        "policy_id": task["policy_id"],
        "holdout_accessed": False,
        "not_gate_result": True,
    }
    record = {
        **common,
        "stage": STAGE_B,
        "primary_utility": primary_utility,
        "observed_disagreement_count": observed,
        "guard_eligible_disagreement_count": eligible,
        "executed_override_count": overrides,
        # OOM is retained distinctly but also trips the frozen zero-tolerance
        # parent algorithm-failure sentinel so it can never remain eligible.
        "algorithm_timeout_count": int(
            status in {"algorithm_timeout", "method_out_of_memory"}
        ),
        "method_out_of_memory_count": int(status == "method_out_of_memory"),
        "path_cap_count": path_caps,
        "infrastructure_failure": False,
        "parent_wall_time_ms": round((time.perf_counter() - started) * 1000.0, 6),
        "branch_time_charged_to_parent": False,
        "status": status,
    }
    validate_artifact_record("stage_b_replicate_record", record)
    trace = {
        "trace_schema_version": 1,
        "artifact_kind": "override_gate_v2_stage_b_decision_trace",
        **common,
        "trace_complete": len(summaries) == 30,
        "parent_decision_trace_sha256": _trace_digest(decisions),
        "decision_records": decisions,
        "episode_summaries": summaries,
    }
    if trace["trace_complete"]:
        validate_stage_b_trace(trace, split="calibration", instance=instance)
    return {"record": record, "trace": trace}


def _child_entry(worker: Callable[[Mapping[str, Any]], Dict[str, Any]], payload: Mapping[str, Any], sender: Any) -> None:
    try:
        sender.send({"kind": "result", "value": worker(payload)})
    except BaseException as error:
        sender.send(
            {
                "kind": "error",
                "error_type": type(error).__name__,
                "error_message": str(error),
            }
        )
    finally:
        sender.close()


def _bounded(
    worker: Callable[[Mapping[str, Any]], Dict[str, Any]],
    payload: Mapping[str, Any],
    timeout_seconds: float,
) -> Dict[str, Any]:
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_child_entry, args=(worker, payload, sender))
    process.start()
    sender.close()
    try:
        if receiver.poll(timeout_seconds):
            message = receiver.recv()
            process.join(timeout=2.0)
            return message
        process.terminate()
        process.join(timeout=5.0)
        return {"kind": "timeout"}
    finally:
        receiver.close()
        if process.is_alive():
            process.kill()
            process.join(timeout=2.0)


def _stage_b_bounded(task: V2CellTask, seed: int) -> Dict[str, Any]:
    seconds = float(load_calibration_instance_v2()["timeouts"]["stage_b_replicate_seconds"])
    message = _bounded(_stage_b_replicate, _stage_b_payload(task, seed), seconds)
    if message["kind"] == "result":
        return message["value"]
    if message["kind"] == "error":
        return {"infrastructure_error": message}
    instance = load_calibration_instance_v2()
    common = {
        "instance_id": instance["instance_id"],
        "instance_sha256": instance_sha256(instance),
        "source_commit": instance["source_commit"],
        "execution_commit": task.execution_commit,
        "split": "calibration",
        "domain_family": task.family,
        "scale": task.scale,
        "generator_seed": seed,
        "policy_id": task.policy_id,
        "holdout_accessed": False,
        "not_gate_result": True,
    }
    record = {
        **common,
        "stage": STAGE_B,
        "primary_utility": 0.0,
        "observed_disagreement_count": 0,
        "guard_eligible_disagreement_count": 0,
        "executed_override_count": 0,
        "algorithm_timeout_count": 1,
        "method_out_of_memory_count": 0,
        "path_cap_count": 0,
        "infrastructure_failure": False,
        "parent_wall_time_ms": seconds * 1000.0,
        "branch_time_charged_to_parent": False,
        "status": "algorithm_timeout",
    }
    validate_artifact_record("stage_b_replicate_record", record)
    return {
        "record": record,
        "trace": {
            "trace_schema_version": 1,
            "artifact_kind": "override_gate_v2_stage_b_decision_trace",
            **common,
            "trace_complete": False,
            "parent_decision_trace_sha256": _trace_digest([]),
            "decision_records": [],
            "episode_summaries": [],
        },
    }


def _pair_worker(payload: Mapping[str, Any]) -> Dict[str, Any]:
    task = dict(payload["task"])
    selected = dict(payload["selected"])
    seed = int(payload["seed"])
    domain = BUILDERS[str(task["family"])](
        int(task["scale"]), seed, seed_namespace=V2_CALIBRATION_SEED_NAMESPACE
    )
    episode = int(selected["episode_index"])
    interaction = int(selected["interaction_index"])
    try:
        result = run_instrumented_episode(
            domain,
            candidate_policy(str(task["policy_id"])),
            episode,
            collect_paired_branches=True,
            paired_branch_decision_keys={(episode, interaction)},
            paired_branch_timeout_seconds=float(
                load_calibration_instance_v2()["timeouts"][
                    "stage_a_individual_branch_seconds"
                ]
            ),
        )
    except PairedBranchTimeoutError:
        return {"status": "stage_a_unresolved", "delta_utility": None}
    if len(result.paired_decisions) != 1:
        raise RuntimeError("Selected Stage-A decision did not produce one pair")
    actual = _decision_record(result.decision_records[interaction], episode, interaction)
    for field in ("state", "greedy_action", "preferred_action"):
        if actual[field] != selected[field]:
            raise RuntimeError(f"Stage-A exact replay mismatch: {field}")
    evidence = result.paired_decisions[0].to_record()
    return {
        "status": "completed",
        "delta_utility": evidence["delta_utility"],
        "paired_evidence": evidence,
    }


def _stage_a_replicate(task: V2CellTask, source: Mapping[str, Any]) -> Dict[str, Any]:
    instance = load_calibration_instance_v2()
    source_record = source["record"]
    trace = source["trace"]
    common = {
        "instance_id": instance["instance_id"],
        "instance_sha256": instance_sha256(instance),
        "source_commit": instance["source_commit"],
        "execution_commit": task.execution_commit,
        "split": "calibration",
        "stage": STAGE_A,
        "domain_family": task.family,
        "scale": task.scale,
        "generator_seed": int(source_record["generator_seed"]),
        "policy_id": task.policy_id,
        "holdout_accessed": False,
        "not_gate_result": True,
    }
    if not trace.get("trace_complete"):
        return {
            **common,
            "sample_manifest_sha256": "0" * 64,
            "sampling_frame_override_count": 0,
            "sample_count": 0,
            "parent_replay_trace_match": False,
            "paired_decisions": [],
            "unresolved_count": 0,
            "infrastructure_failure": False,
            "instrumentation_wall_time_ms": 0.0,
            "instrumentation_time_is_parent_performance": False,
            "stage_a_skipped_due_stage_b_valid_negative": True,
        }
    manifest = build_stage_a_sample_manifest(trace, split="calibration", instance=instance)
    started = time.perf_counter()
    replay = _bounded(
        _stage_b_replicate,
        _stage_b_payload(task, int(source_record["generator_seed"])),
        float(instance["timeouts"]["stage_b_replicate_seconds"]),
    )
    if replay["kind"] != "result":
        raise RuntimeError("Stage-A parent replay did not complete")
    replay_equal = (
        replay["value"]["trace"]["parent_decision_trace_sha256"]
        == trace["parent_decision_trace_sha256"]
    )
    if not replay_equal:
        raise RuntimeError("Stage-A parent trace differs from Stage B")
    pairs = []
    for selected in manifest["selected_decisions"]:
        message = _bounded(
            _pair_worker,
            {
                "task": task.to_dict(),
                "seed": int(source_record["generator_seed"]),
                "selected": selected,
            },
            float(instance["timeouts"]["stage_a_branch_pair_process_seconds"]),
        )
        if message["kind"] == "result":
            pair = message["value"]
        elif message["kind"] == "timeout":
            pair = {"status": "stage_a_unresolved", "delta_utility": None}
        else:
            raise RuntimeError("Stage-A pair worker infrastructure failure")
        pairs.append({"sample_priority_sha256": selected["sample_priority_sha256"], **pair})
    record = {
        **common,
        "sample_manifest_sha256": manifest["sample_manifest_sha256"],
        "sampling_frame_override_count": manifest["sampling_frame_override_count"],
        "sample_count": manifest["sample_count"],
        "parent_replay_trace_match": True,
        "paired_decisions": pairs,
        "unresolved_count": sum(pair["status"] == "stage_a_unresolved" for pair in pairs),
        "infrastructure_failure": False,
        "instrumentation_wall_time_ms": round((time.perf_counter() - started) * 1000.0, 6),
        "instrumentation_time_is_parent_performance": False,
        "stage_a_skipped_due_stage_b_valid_negative": False,
    }
    validate_artifact_record("stage_a_replicate_record", record)
    return record


def _attempt_document(
    context: AuthorizedCalibrationContext,
    task: V2CellTask,
    run_attempt: int,
    records: Sequence[Mapping[str, Any]],
    traces: Sequence[Mapping[str, Any]],
    failures: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    complete = len(records) == 20 and not failures
    document = {
        "cell_attempt_schema_version": CELL_ATTEMPT_SCHEMA_VERSION,
        "artifact_kind": "override_gate_v2_calibration_cell_attempt",
        "instance_id": task.instance_id,
        "instance_sha256": task.instance_sha256,
        "source_commit": load_calibration_instance_v2()["source_commit"],
        "execution_commit": context.execution_commit,
        "execution_manifest_sha256": context.execution_manifest_sha256,
        "authorization_sha256": context.authorization_sha256,
        "split": "calibration",
        "stage": task.stage,
        "cell_id": task.cell_id,
        "cell_sha256": _sha256(task.to_dict()),
        "run_attempt": run_attempt,
        "expected_replicate_count": 20,
        "record_count": len(records),
        "trace_count": len(traces),
        "infrastructure_failure_count": len(failures),
        "cell_complete": complete,
        "records": list(records),
        "traces": list(traces),
        "infrastructure_failures": list(failures),
        "latest_attempt_only": True,
        "fallback_to_earlier_attempt": False,
        "holdout_accessed": False,
        "not_gate_result": True,
    }
    document["attempt_sha256"] = _sha256(document)
    return document


def _write_once(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"Immutable attempt exists: {path.name}")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def run_stage_b_cell(
    context: AuthorizedCalibrationContext,
    cell_index: int,
    run_attempt: int,
    output_directory: Path,
    *,
    workers: int = DEFAULT_WORKERS,
) -> Path:
    task = _task_for_cell(context, STAGE_B, cell_index)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda seed: _stage_b_bounded(task, seed), task.seeds))
    records = [item["record"] for item in results if "record" in item]
    traces = [item["trace"] for item in results if "trace" in item]
    failures = [item for item in results if "record" not in item]
    attempt = _attempt_document(context, task, run_attempt, records, traces, failures)
    path = output_directory / f"{task.cell_id}.attempt-{run_attempt}.json"
    _write_once(path, attempt)
    return path


def run_stage_a_cell(
    context: AuthorizedCalibrationContext,
    cell_index: int,
    run_attempt: int,
    stage_b_consolidation_path: Path,
    output_directory: Path,
    *,
    workers: int = DEFAULT_WORKERS,
) -> Path:
    task = _task_for_cell(context, STAGE_A, cell_index)
    consolidated = json.loads(stage_b_consolidation_path.read_text(encoding="utf-8"))
    validate_stage_consolidation(consolidated, context, STAGE_B)
    sources = [
        item
        for item in consolidated["replicates"]
        if item["record"]["policy_id"] == task.policy_id
        and item["record"]["domain_family"] == task.family
        and int(item["record"]["scale"]) == task.scale
    ]
    if len(sources) != 20:
        raise ValueError("Stage-A cell requires exactly 20 Stage-B sources")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        records = list(pool.map(lambda source: _stage_a_replicate(task, source), sources))
    attempt = _attempt_document(context, task, run_attempt, records, (), ())
    path = output_directory / f"{task.cell_id}.attempt-{run_attempt}.json"
    _write_once(path, attempt)
    return path


def _validate_attempt(
    attempt: Mapping[str, Any], context: AuthorizedCalibrationContext, task: V2CellTask
) -> None:
    digest_payload = dict(attempt)
    recorded = digest_payload.pop("attempt_sha256", None)
    if recorded != _sha256(digest_payload):
        raise ValueError("Cell attempt digest changed")
    expected = {
        "cell_attempt_schema_version": CELL_ATTEMPT_SCHEMA_VERSION,
        "artifact_kind": "override_gate_v2_calibration_cell_attempt",
        "execution_commit": context.execution_commit,
        "execution_manifest_sha256": context.execution_manifest_sha256,
        "authorization_sha256": context.authorization_sha256,
        "stage": task.stage,
        "cell_id": task.cell_id,
        "cell_sha256": _sha256(task.to_dict()),
        "expected_replicate_count": 20,
        "cell_complete": True,
        "latest_attempt_only": True,
        "fallback_to_earlier_attempt": False,
        "holdout_accessed": False,
        "not_gate_result": True,
    }
    for field, value in expected.items():
        if attempt.get(field) != value:
            raise ValueError(f"Invalid cell attempt field {field}")
    if int(attempt.get("record_count", -1)) != 20:
        raise ValueError("Complete cell attempt requires 20 records")
    expected_traces = 20 if task.stage == STAGE_B else 0
    if int(attempt.get("trace_count", -1)) != expected_traces:
        raise ValueError("Cell attempt trace count differs from its stage")
    if int(attempt.get("infrastructure_failure_count", -1)) != 0:
        raise ValueError("Latest cell attempt contains infrastructure failures")
    records = attempt.get("records")
    if not isinstance(records, list):
        raise ValueError("Cell attempt records must be a list")
    identities = set()
    for record in records:
        kind = (
            "stage_b_replicate_record"
            if task.stage == STAGE_B
            else "stage_a_replicate_record"
        )
        validate_artifact_record(kind, record)
        identity = (
            record.get("policy_id"),
            record.get("domain_family"),
            int(record.get("scale", -1)),
            int(record.get("generator_seed", -1)),
        )
        expected_identity = (
            task.policy_id,
            task.family,
            task.scale,
            int(record.get("generator_seed", -1)),
        )
        if identity != expected_identity:
            raise ValueError("Cell attempt record belongs to another cell")
        if identity in identities:
            raise ValueError("Cell attempt contains duplicate replicate identity")
        identities.add(identity)
    if {identity[3] for identity in identities} != set(task.seeds):
        raise ValueError("Cell attempt seed manifest is incomplete")
    traces = attempt.get("traces")
    if not isinstance(traces, list):
        raise ValueError("Cell attempt traces must be a list")
    if task.stage == STAGE_B:
        trace_seeds = set()
        by_seed = {int(record["generator_seed"]): record for record in records}
        for trace in traces:
            seed = int(trace.get("generator_seed", -1))
            if seed in trace_seeds:
                raise ValueError("Cell attempt contains duplicate Stage-B trace")
            trace_seeds.add(seed)
            if trace.get("trace_complete") is True:
                validate_stage_b_trace(trace, split="calibration")
            elif int(by_seed[seed].get("algorithm_timeout_count", 0)) != 1:
                raise ValueError("Incomplete Stage-B trace requires algorithm timeout")
        if trace_seeds != set(task.seeds):
            raise ValueError("Cell attempt Stage-B traces are incomplete")


def consolidate_stage(
    context: AuthorizedCalibrationContext,
    stage: str,
    input_directory: Path,
) -> Dict[str, Any]:
    tasks = build_cell_plan(
        "calibration", stage, execution_commit=context.execution_commit, planning_only=True
    )
    by_cell: Dict[str, List[tuple[int, Path]]] = {task.cell_id: [] for task in tasks}
    for path in input_directory.rglob("*.attempt-*.json"):
        match = _ATTEMPT_NAME.fullmatch(path.name)
        if match and match.group("cell") in by_cell:
            by_cell[match.group("cell")].append((int(match.group("attempt")), path))
    selected = []
    records = []
    replicates = []
    for task in tasks:
        if not by_cell[task.cell_id]:
            raise ValueError(f"Missing latest attempt for {task.cell_id}")
        number, path = max(by_cell[task.cell_id], key=lambda item: item[0])
        attempt = json.loads(path.read_text(encoding="utf-8"))
        if int(attempt.get("run_attempt", -1)) != number:
            raise ValueError("Attempt filename and record disagree")
        _validate_attempt(attempt, context, task)
        selected.append({"cell_id": task.cell_id, "run_attempt": number})
        records.extend(attempt["records"])
        if stage == STAGE_B:
            traces = {
                (item["policy_id"], item["domain_family"], int(item["scale"]), int(item["generator_seed"])): item
                for item in attempt["traces"]
            }
            for record in attempt["records"]:
                key = (
                    record["policy_id"], record["domain_family"],
                    int(record["scale"]), int(record["generator_seed"]),
                )
                replicates.append({"record": record, "trace": traces[key]})
    result = {
        "consolidation_schema_version": CONSOLIDATION_SCHEMA_VERSION,
        "artifact_kind": "override_gate_v2_stage_consolidation",
        "execution_commit": context.execution_commit,
        "execution_manifest_sha256": context.execution_manifest_sha256,
        "authorization_sha256": context.authorization_sha256,
        "split": "calibration",
        "stage": stage,
        "selected_latest_attempts_without_fallback": True,
        "selected_attempts": selected,
        "record_count": len(records),
        "records": records,
        "replicates": replicates,
        "holdout_accessed": False,
        "not_gate_result": True,
    }
    result["consolidation_sha256"] = _sha256(result)
    validate_stage_consolidation(result, context, stage)
    return result


def validate_stage_consolidation(
    consolidation: Mapping[str, Any],
    context: AuthorizedCalibrationContext,
    stage: str,
) -> None:
    payload = dict(consolidation)
    recorded = payload.pop("consolidation_sha256", None)
    if recorded != _sha256(payload):
        raise ValueError("Stage consolidation digest changed")
    expected_cells = EXPECTED_STAGE_B_CELL_COUNT if stage == STAGE_B else EXPECTED_STAGE_A_CELL_COUNT
    expected_records = 2880 if stage == STAGE_B else 2640
    expected = {
        "consolidation_schema_version": CONSOLIDATION_SCHEMA_VERSION,
        "artifact_kind": "override_gate_v2_stage_consolidation",
        "execution_commit": context.execution_commit,
        "execution_manifest_sha256": context.execution_manifest_sha256,
        "authorization_sha256": context.authorization_sha256,
        "split": "calibration",
        "stage": stage,
        "selected_latest_attempts_without_fallback": True,
        "record_count": expected_records,
        "holdout_accessed": False,
        "not_gate_result": True,
    }
    for field, value in expected.items():
        if consolidation.get(field) != value:
            raise ValueError(f"Invalid stage consolidation field {field}")
    selected = consolidation.get("selected_attempts")
    if not isinstance(selected, list) or len(selected) != expected_cells:
        raise ValueError("Stage consolidation selected-attempt count changed")
    if len({item.get("cell_id") for item in selected}) != expected_cells:
        raise ValueError("Stage consolidation cell identities are duplicated")
    records = consolidation.get("records")
    if not isinstance(records, list) or len(records) != expected_records:
        raise ValueError("Stage consolidation record population changed")
    if stage == STAGE_B:
        validate_stage_b_calibration_records(records)
        replicates = consolidation.get("replicates")
        if not isinstance(replicates, list) or len(replicates) != expected_records:
            raise ValueError("Stage-B consolidation trace population changed")
        identities = {
            (
                item["record"]["policy_id"],
                item["record"]["domain_family"],
                int(item["record"]["scale"]),
                int(item["record"]["generator_seed"]),
            )
            for item in replicates
        }
        if len(identities) != expected_records:
            raise ValueError("Stage-B consolidation replicates are duplicated")
    elif consolidation.get("replicates") != []:
        raise ValueError("Stage-A consolidation cannot contain Stage-B traces")


def select_from_consolidations(
    context: AuthorizedCalibrationContext,
    stage_b_path: Path,
    stage_a_path: Path,
) -> Dict[str, Any]:
    stage_b = json.loads(stage_b_path.read_text(encoding="utf-8"))
    stage_a = json.loads(stage_a_path.read_text(encoding="utf-8"))
    validate_stage_consolidation(stage_b, context, STAGE_B)
    validate_stage_consolidation(stage_a, context, STAGE_A)
    selection = select_v2_calibration_policy(stage_b["records"], stage_a["records"])
    return {
        "artifact_kind": "override_gate_v2_calibration_selection_evidence",
        "execution_commit": context.execution_commit,
        "execution_manifest_sha256": context.execution_manifest_sha256,
        "authorization_sha256": context.authorization_sha256,
        "stage_b_consolidation_sha256": stage_b["consolidation_sha256"],
        "stage_a_consolidation_sha256": stage_a["consolidation_sha256"],
        "selection": selection,
        "calibration_executed": True,
        "verification_executed": False,
        "protected_holdout_accessed": False,
        "holdout_accessed": False,
        "not_gate_result": True,
    }


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _authorization_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--authorization-sha256", required=True)
    parser.add_argument("--execution-commit", required=True)
    parser.add_argument("--execution-manifest", type=Path, required=True)
    parser.add_argument("--execution-manifest-sha256", required=True)
    parser.add_argument("--outcome-workflow", type=Path, required=True)
    parser.add_argument("--confirmation", required=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    manifest = commands.add_parser("execution-manifest")
    manifest.add_argument("--execution-commit", required=True)
    manifest.add_argument("--outcome-workflow", type=Path, default=WORKFLOW_PATH)
    manifest.add_argument("--output", type=Path, required=True)
    dry_run = commands.add_parser("dry-run")
    dry_run.add_argument("--output", type=Path, required=True)
    validate = commands.add_parser("validate-authorization")
    _authorization_args(validate)
    validate.add_argument("--output", type=Path, required=True)
    matrix = commands.add_parser("matrix")
    _authorization_args(matrix)
    matrix.add_argument("--stage", choices=(STAGE_B, STAGE_A), required=True)
    run_b = commands.add_parser("run-stage-b-cell")
    _authorization_args(run_b)
    run_b.add_argument("--cell-index", type=int, required=True)
    run_b.add_argument("--run-attempt", type=int, required=True)
    run_b.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    run_b.add_argument("--output", type=Path, required=True)
    run_a = commands.add_parser("run-stage-a-cell")
    _authorization_args(run_a)
    run_a.add_argument("--cell-index", type=int, required=True)
    run_a.add_argument("--run-attempt", type=int, required=True)
    run_a.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    run_a.add_argument("--stage-b-consolidation", type=Path, required=True)
    run_a.add_argument("--output", type=Path, required=True)
    consolidate = commands.add_parser("consolidate")
    _authorization_args(consolidate)
    consolidate.add_argument("--stage", choices=(STAGE_B, STAGE_A), required=True)
    consolidate.add_argument("--input", type=Path, required=True)
    consolidate.add_argument("--output", type=Path, required=True)
    select = commands.add_parser("select")
    _authorization_args(select)
    select.add_argument("--stage-b", type=Path, required=True)
    select.add_argument("--stage-a", type=Path, required=True)
    select.add_argument("--output", type=Path, required=True)
    return parser


def _context(args: argparse.Namespace) -> AuthorizedCalibrationContext:
    return authorize_calibration_context(
        authorization_path=args.authorization,
        authorization_digest=args.authorization_sha256,
        execution_commit=args.execution_commit,
        execution_manifest_path=args.execution_manifest,
        execution_manifest_digest=args.execution_manifest_sha256,
        outcome_workflow_path=args.outcome_workflow,
        confirmation=args.confirmation,
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "execution-manifest":
            result = build_execution_manifest(
                args.execution_commit, outcome_workflow_path=args.outcome_workflow
            )
            _write_json(args.output, result)
        elif args.command == "dry-run":
            result = build_no_outcome_execution_review()
            _write_json(args.output, result)
        else:
            context = _context(args)
            if args.command == "validate-authorization":
                result = {
                    "authorization_valid": True,
                    "execution_commit": context.execution_commit,
                    "authorization_sha256": context.authorization_sha256,
                    "execution_manifest_sha256": context.execution_manifest_sha256,
                    "authorized_split": "calibration",
                    "not_gate_result": True,
                }
                _write_json(args.output, result)
            elif args.command == "matrix":
                result = authorized_matrix(context, args.stage)
            elif args.command == "run-stage-b-cell":
                path = run_stage_b_cell(
                    context, args.cell_index, args.run_attempt, args.output,
                    workers=args.workers,
                )
                result = {"attempt_path": str(path)}
            elif args.command == "run-stage-a-cell":
                path = run_stage_a_cell(
                    context, args.cell_index, args.run_attempt,
                    args.stage_b_consolidation, args.output, workers=args.workers,
                )
                result = {"attempt_path": str(path)}
            elif args.command == "consolidate":
                result = consolidate_stage(context, args.stage, args.input)
                _write_json(args.output, result)
            else:
                result = select_from_consolidations(context, args.stage_b, args.stage_a)
                _write_json(args.output, result)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, PermissionError, ValueError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
