"""Killable development workers and immutable attempts for gate v2.

WP-GATE-0.13 exercises the distribution boundary only.  It accepts exclusively
the development seed namespace, never constructs a frozen experimental split,
and every artifact remains ``not_gate_result=true``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

from .g1_domains import build_domain, validate_development_seed
from .override_gate_calibration_engine import (
    candidate_policy,
    run_instrumented_episode,
)
from .override_gate_calibration_v2 import instance_sha256, load_calibration_instance_v2
from .override_gate_calibration_v2_sampler import (
    build_stage_a_sample_manifest,
    validate_stage_a_sample_manifest,
    validate_stage_b_trace,
)

WORKER_SCHEMA_VERSION = 1
ATTEMPT_SCHEMA_VERSION = 1
MAX_DEVELOPMENT_EPISODES = 4
MAX_INTERACTION_BUDGET = 40
MAX_TIMEOUT_SECONDS = 120.0
DEFAULT_TIMEOUT_SECONDS = 30.0
_CELL_ID = re.compile(r"^[A-Za-z0-9_.-]+$")
_ATTEMPT_NAME = re.compile(
    r"^(?P<cell>[A-Za-z0-9_.-]+)\.attempt-(?P<attempt>[1-9][0-9]*)\.json$"
)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


@dataclass(frozen=True)
class DevelopmentReplicateCase:
    """Small active-candidate replicate used only to prove worker mechanics."""

    scale: int = 100
    seed: int = 0
    policy_id: str = "margin_000"
    first_episode_index: int = 10
    episode_count: int = 1
    interaction_budget: int = 40

    def __post_init__(self) -> None:
        if self.scale not in {100, 500, 1000}:
            raise ValueError("Development worker scale must be 100, 500, or 1000")
        validate_development_seed(self.seed)
        policy = candidate_policy(self.policy_id)
        if policy.policy_id == "gate_disabled":
            raise ValueError("Stage-B trace worker requires an active candidate")
        if not 10 <= self.first_episode_index < 30:
            raise ValueError("Development replay must start in evaluation episodes")
        if not 0 < self.episode_count <= MAX_DEVELOPMENT_EPISODES:
            raise ValueError("Development episode_count is out of bounds")
        if self.first_episode_index + self.episode_count > 30:
            raise ValueError("Development episodes exceed the frozen episode range")
        if not 0 < self.interaction_budget <= MAX_INTERACTION_BUDGET:
            raise ValueError("Development interaction budget is out of bounds")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scale": self.scale,
            "seed": self.seed,
            "policy_id": self.policy_id,
            "first_episode_index": self.first_episode_index,
            "episode_count": self.episode_count,
            "interaction_budget": self.interaction_budget,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DevelopmentReplicateCase":
        return cls(**{key: int(item) if key != "policy_id" else str(item) for key, item in value.items()})

    @property
    def cell_id(self) -> str:
        return (
            f"dev.wall_grid.n{self.scale}.s{self.seed}.{self.policy_id}."
            f"e{self.first_episode_index}-{self.episode_count}"
        )


def _safety_fields() -> Dict[str, Any]:
    return {
        "split": "development",
        "calibration_executed": False,
        "verification_executed": False,
        "protected_holdout_accessed": False,
        "holdout_accessed": False,
        "not_gate_result": True,
    }


def _decision_record(record: Any, episode_index: int, interaction_index: int) -> Dict[str, Any]:
    return {
        "phase": "evaluation",
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


def execute_stage_b_trace(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Run one complete bounded development trace without any branch snapshot."""
    case = DevelopmentReplicateCase.from_dict(payload)
    domain = build_domain("wall_grid", case.scale, case.seed)
    policy = candidate_policy(case.policy_id)
    decisions: List[Dict[str, Any]] = []
    episodes: List[Dict[str, Any]] = []
    started = time.perf_counter()
    for episode_index in range(
        case.first_episode_index,
        case.first_episode_index + case.episode_count,
    ):
        result = run_instrumented_episode(
            domain,
            policy,
            episode_index,
            interaction_budget=case.interaction_budget,
            collect_paired_branches=False,
        )
        if result.paired_decisions:
            raise RuntimeError("Stage B produced forbidden paired evidence")
        episodes.append(result.summary.to_record())
        decisions.extend(
            _decision_record(record, episode_index, interaction_index)
            for interaction_index, record in enumerate(result.decision_records)
        )
    instance = load_calibration_instance_v2()
    trace = {
        "worker_schema_version": WORKER_SCHEMA_VERSION,
        "trace_schema_version": 1,
        "artifact_kind": "override_gate_v2_stage_b_decision_trace",
        "instance_id": instance["instance_id"],
        "instance_sha256": instance_sha256(instance),
        **_safety_fields(),
        "cell_id": case.cell_id,
        "policy_id": case.policy_id,
        "domain_family": "wall_grid",
        "scale": case.scale,
        "generator_seed": case.seed,
        "first_episode_index": case.first_episode_index,
        "episode_count": case.episode_count,
        "interaction_budget": case.interaction_budget,
        "trace_complete": True,
        "parent_decision_trace_sha256": _trace_digest(decisions),
        "decision_records": decisions,
        "episode_summaries": episodes,
        "parent_wall_time_ms": round((time.perf_counter() - started) * 1000.0, 6),
        "paired_branch_count": 0,
    }
    validate_stage_b_trace(trace, split="development", instance=instance)
    return trace


def _child_entry(
    worker: Callable[[Mapping[str, Any]], Dict[str, Any]],
    payload: Mapping[str, Any],
    sender: Any,
) -> None:
    try:
        sender.send({"kind": "result", "record": worker(payload)})
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


def _execute_bounded(
    worker: Callable[[Mapping[str, Any]], Dict[str, Any]],
    payload: Mapping[str, Any],
    *,
    timeout_seconds: float,
) -> Dict[str, Any]:
    timeout = float(timeout_seconds)
    if not 0.0 < timeout <= MAX_TIMEOUT_SECONDS:
        raise ValueError("Development worker timeout is out of bounds")
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_child_entry, args=(worker, payload, sender))
    started = time.perf_counter()
    process.start()
    sender.close()
    try:
        if receiver.poll(timeout):
            message = receiver.recv()
            process.join(timeout=2.0)
            return {
                **message,
                "worker_wall_time_ms": round(
                    (time.perf_counter() - started) * 1000.0, 6
                ),
            }
        process.terminate()
        process.join(timeout=5.0)
        return {
            "kind": "timeout",
            "worker_wall_time_ms": round(
                (time.perf_counter() - started) * 1000.0, 6
            ),
        }
    finally:
        receiver.close()
        if process.is_alive():
            process.kill()
            process.join(timeout=2.0)


def execute_stage_b_bounded(
    case: DevelopmentReplicateCase,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    worker: Callable[[Mapping[str, Any]], Dict[str, Any]] = execute_stage_b_trace,
) -> Dict[str, Any]:
    """Kill one Stage-B replicate cleanly and classify timeout vs worker error."""
    message = _execute_bounded(worker, case.to_dict(), timeout_seconds=timeout_seconds)
    if message["kind"] == "result":
        return {
            "worker_status": "completed",
            "worker_wall_time_ms": message["worker_wall_time_ms"],
            "trace": message["record"],
            **_safety_fields(),
        }
    result = {
        "worker_status": (
            "algorithm_timeout" if message["kind"] == "timeout" else "infrastructure_error"
        ),
        "cell_id": case.cell_id,
        "worker_wall_time_ms": message["worker_wall_time_ms"],
        **_safety_fields(),
    }
    if message["kind"] == "error":
        result.update(
            error_type=message["error_type"], error_message=message["error_message"]
        )
    return result


def _pair_worker(payload: Mapping[str, Any]) -> Dict[str, Any]:
    case = DevelopmentReplicateCase.from_dict(payload["case"])
    selected = dict(payload["selected_decision"])
    episode_index = int(selected["episode_index"])
    interaction_index = int(selected["interaction_index"])
    domain = build_domain("wall_grid", case.scale, case.seed)
    result = run_instrumented_episode(
        domain,
        candidate_policy(case.policy_id),
        episode_index,
        interaction_budget=case.interaction_budget,
        collect_paired_branches=True,
        paired_branch_decision_keys={(episode_index, interaction_index)},
    )
    actual = _decision_record(
        result.decision_records[interaction_index], episode_index, interaction_index
    )
    for field in ("state", "greedy_action", "preferred_action"):
        if actual[field] != selected[field]:
            raise RuntimeError(f"Stage-A replay decision mismatch: {field}")
    if len(result.paired_decisions) != 1:
        raise RuntimeError("Stage-A selected decision did not yield exactly one pair")
    return {
        "sample_priority_sha256": selected["sample_priority_sha256"],
        "episode_index": episode_index,
        "interaction_index": interaction_index,
        "decision_replay_equal": True,
        "paired_evidence": result.paired_decisions[0].to_record(),
    }


def execute_stage_a_replay(
    case: DevelopmentReplicateCase,
    source_trace: Mapping[str, Any],
    *,
    parent_timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    pair_timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    pair_worker: Callable[[Mapping[str, Any]], Dict[str, Any]] = _pair_worker,
) -> Dict[str, Any]:
    """Replay the parent exactly, then run each frozen pair in its own process."""
    validate_stage_b_trace(source_trace, split="development")
    if source_trace["cell_id"] != case.cell_id:
        raise ValueError("Stage-A source trace belongs to another cell")
    manifest = build_stage_a_sample_manifest(source_trace, split="development")
    validate_stage_a_sample_manifest(manifest, split="development")
    parent_replay = execute_stage_b_bounded(
        case, timeout_seconds=parent_timeout_seconds
    )
    result = {
        "worker_schema_version": WORKER_SCHEMA_VERSION,
        "artifact_kind": "override_gate_v2_stage_a_development_replay",
        "cell_id": case.cell_id,
        "source_parent_decision_trace_sha256": source_trace[
            "parent_decision_trace_sha256"
        ],
        "sample_manifest": manifest,
        "parent_replay_status": parent_replay["worker_status"],
        "parent_replay_equal": False,
        "pairs": [],
        **_safety_fields(),
    }
    if parent_replay["worker_status"] != "completed":
        result["worker_status"] = "stage_a_unresolved"
        return result
    result["parent_replay_equal"] = (
        parent_replay["trace"]["parent_decision_trace_sha256"]
        == source_trace["parent_decision_trace_sha256"]
    )
    if not result["parent_replay_equal"]:
        result["worker_status"] = "infrastructure_error"
        result["error_message"] = "Stage-A parent trace differs from Stage B"
        return result
    for selected in manifest["selected_decisions"]:
        message = _execute_bounded(
            pair_worker,
            {"case": case.to_dict(), "selected_decision": selected},
            timeout_seconds=pair_timeout_seconds,
        )
        pair = {
            "sample_priority_sha256": selected["sample_priority_sha256"],
            "episode_index": selected["episode_index"],
            "interaction_index": selected["interaction_index"],
            "pair_wall_time_ms": message["worker_wall_time_ms"],
        }
        if message["kind"] == "result":
            pair.update(pair_status="completed", **message["record"])
        elif message["kind"] == "timeout":
            pair["pair_status"] = "stage_a_unresolved"
        else:
            pair.update(
                pair_status="infrastructure_error",
                error_type=message["error_type"],
                error_message=message["error_message"],
            )
        result["pairs"].append(pair)
    statuses = {pair["pair_status"] for pair in result["pairs"]}
    if "infrastructure_error" in statuses:
        result["worker_status"] = "infrastructure_error"
    elif "stage_a_unresolved" in statuses:
        result["worker_status"] = "stage_a_unresolved"
    else:
        result["worker_status"] = "completed"
    result["sampled_pair_count"] = len(result["pairs"])
    result["completed_pair_count"] = sum(
        pair["pair_status"] == "completed" for pair in result["pairs"]
    )
    return result


def build_attempt_envelope(
    cell_id: str,
    stage: str,
    run_attempt: int,
    record: Mapping[str, Any],
) -> Dict[str, Any]:
    if not _CELL_ID.fullmatch(cell_id):
        raise ValueError("Unsafe attempt cell_id")
    if stage not in {"stage_a", "stage_b"}:
        raise ValueError("Unknown attempt stage")
    if isinstance(run_attempt, bool) or not isinstance(run_attempt, int) or run_attempt < 1:
        raise ValueError("run_attempt must be a positive integer")
    payload = {**dict(record), **_safety_fields()}
    return {
        "attempt_schema_version": ATTEMPT_SCHEMA_VERSION,
        "artifact_kind": "override_gate_v2_immutable_attempt",
        "cell_id": cell_id,
        "stage": stage,
        "run_attempt": run_attempt,
        "record_sha256": _sha256(payload),
        "record": payload,
        **_safety_fields(),
    }


def validate_attempt_envelope(envelope: Mapping[str, Any]) -> None:
    required = {
        "attempt_schema_version", "artifact_kind", "cell_id", "stage",
        "run_attempt", "record_sha256", "record", "calibration_executed",
        "verification_executed", "protected_holdout_accessed",
        "holdout_accessed", "not_gate_result",
    }
    missing = required.difference(envelope)
    if missing:
        raise ValueError(f"Attempt envelope missing fields: {sorted(missing)}")
    if envelope["attempt_schema_version"] != ATTEMPT_SCHEMA_VERSION:
        raise ValueError("Unknown attempt schema")
    if envelope["artifact_kind"] != "override_gate_v2_immutable_attempt":
        raise ValueError("Wrong attempt artifact kind")
    if not _CELL_ID.fullmatch(str(envelope["cell_id"])):
        raise ValueError("Unsafe attempt cell_id")
    if envelope["stage"] not in {"stage_a", "stage_b"}:
        raise ValueError("Unknown attempt stage")
    attempt = envelope["run_attempt"]
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        raise ValueError("Invalid run_attempt")
    if envelope["record_sha256"] != _sha256(envelope["record"]):
        raise ValueError("Attempt record digest changed")
    safety = _safety_fields()
    if any(envelope.get(field) != value for field, value in safety.items()):
        raise ValueError("Development attempt safety envelope changed")
    if any(envelope["record"].get(field) != value for field, value in safety.items()):
        raise ValueError("Development attempt record safety flags changed")


def write_attempt_atomic(
    directory: Path,
    envelope: Mapping[str, Any],
) -> Path:
    """Write once via same-directory replace; never overwrite an attempt."""
    validate_attempt_envelope(envelope)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (
        f"{envelope['cell_id']}.attempt-{envelope['run_attempt']}.json"
    )
    if target.exists():
        raise FileExistsError(f"Immutable attempt already exists: {target.name}")
    temporary = directory / f".{target.name}.{os.getpid()}.tmp"
    text = json.dumps(envelope, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, target)
        except FileExistsError as error:
            raise FileExistsError(
                f"Immutable attempt already exists: {target.name}"
            ) from error
    finally:
        if temporary.exists():
            temporary.unlink()
    return target


def consolidate_latest_attempts(
    paths: Sequence[Path],
    expected_cell_ids: Sequence[str],
) -> Dict[str, Any]:
    """Select each newest named attempt first, then fail closed if it is bad."""
    expected = list(expected_cell_ids)
    if len(expected) != len(set(expected)) or any(
        not _CELL_ID.fullmatch(cell) for cell in expected
    ):
        raise ValueError("Expected cell IDs must be unique and safe")
    grouped: Dict[str, List[tuple[int, Path]]] = {cell: [] for cell in expected}
    for path in paths:
        match = _ATTEMPT_NAME.fullmatch(path.name)
        if match is None:
            raise ValueError(f"Invalid attempt filename: {path.name}")
        cell = match.group("cell")
        if cell not in grouped:
            raise ValueError(f"Unexpected attempt cell: {cell}")
        grouped[cell].append((int(match.group("attempt")), path))
    missing = [cell for cell, attempts in grouped.items() if not attempts]
    if missing:
        raise ValueError(f"Missing attempt cells: {missing}")
    selected: List[Dict[str, Any]] = []
    for cell in expected:
        attempt, path = max(grouped[cell], key=lambda item: item[0])
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"Newest attempt is unreadable for {cell}") from error
        validate_attempt_envelope(envelope)
        if envelope["cell_id"] != cell or envelope["run_attempt"] != attempt:
            raise ValueError(f"Newest attempt identity mismatch for {cell}")
        selected.append(envelope)
    return {
        "artifact_kind": "override_gate_v2_development_attempt_consolidation",
        "expected_cell_count": len(expected),
        "selected_attempt_count": len(selected),
        "selected_latest_attempts_without_fallback": True,
        "selected_attempts": selected,
        **_safety_fields(),
    }


def run_development_distribution_pilot(
    case: DevelopmentReplicateCase,
    *,
    attempt_directory: Optional[Path] = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Exercise Stage B, exact Stage A, and latest-attempt consolidation."""
    stage_b = execute_stage_b_bounded(case, timeout_seconds=timeout_seconds)
    if stage_b["worker_status"] == "completed":
        stage_a = execute_stage_a_replay(
            case,
            stage_b["trace"],
            parent_timeout_seconds=timeout_seconds,
            pair_timeout_seconds=timeout_seconds,
        )
    else:
        stage_a = {
            "artifact_kind": "override_gate_v2_stage_a_development_replay",
            "cell_id": case.cell_id,
            "worker_status": "blocked_by_stage_b",
            **_safety_fields(),
        }
    stage_b_cell = f"{case.cell_id}.stage_b"
    stage_a_cell = f"{case.cell_id}.stage_a"
    consolidation = None
    attempt_paths: List[Path] = []
    if attempt_directory is not None:
        attempt_paths.append(
            write_attempt_atomic(
                attempt_directory,
                build_attempt_envelope(stage_b_cell, "stage_b", 1, stage_b),
            )
        )
        attempt_paths.append(
            write_attempt_atomic(
                attempt_directory,
                build_attempt_envelope(stage_a_cell, "stage_a", 1, stage_a),
            )
        )
        consolidation = consolidate_latest_attempts(
            attempt_paths, [stage_b_cell, stage_a_cell]
        )
    return {
        "worker_schema_version": WORKER_SCHEMA_VERSION,
        "artifact_kind": "override_gate_v2_development_distribution_pilot",
        "work_package": "WP-GATE-0.13",
        "case": case.to_dict(),
        "stage_b": stage_b,
        "stage_a": stage_a,
        "consolidation": consolidation,
        "stage_b_branch_free": bool(
            stage_b.get("worker_status") == "completed"
            and stage_b["trace"]["paired_branch_count"] == 0
        ),
        "stage_a_exact_parent_replay": bool(stage_a.get("parent_replay_equal")),
        "latest_attempts_selected_without_fallback": bool(
            consolidation
            and consolidation["selected_latest_attempts_without_fallback"]
        ),
        **_safety_fields(),
    }


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--attempt-directory", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    result = run_development_distribution_pilot(
        DevelopmentReplicateCase(),
        attempt_directory=args.attempt_directory,
        timeout_seconds=args.timeout_seconds,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    temporary = args.output.with_name(f".{args.output.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, args.output)
    finally:
        if temporary.exists():
            temporary.unlink()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
