"""Bounded, resumable calibration pipeline with no execution CLI.

WP-GATE-0.6 implements the worker, shard, resume, and consolidation contracts.
Outcome execution requires a separate explicit authorization record that does
not exist in this work package.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import multiprocessing
import os
import platform
import re
import signal
import sys
import time
from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from contextlib import contextmanager
from pathlib import Path
from statistics import mean
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence

from .g1_domains import load_g1_protocol
from .override_gate import OverrideGateMode
from .override_gate_calibration import load_calibration_instance
from .override_gate_calibration_engine import (
    InstrumentedEpisodeResult,
    build_calibration_domain,
    candidate_policy,
    run_instrumented_episode,
)
from .override_gate_calibration_runner import (
    CalibrationTask,
    build_task_plan,
    instance_sha256,
    validate_artifact_record,
)
from .override_gate_calibration_statistics import select_calibration_policy

CALIBRATION_SHARD_VERSION = 2
AUTHORIZATION_SCHEMA_VERSION = 1
DEFAULT_OUTPUT = Path(
    "artifacts/override_gate/E0-OVERRIDE-GATE-CAL-INSTANCE-v1/calibration"
)
ARTIFACT_FILES = (
    "raw_runs.jsonl",
    "paired_branches.jsonl.gz",
    "selection_report.json",
    "policy_record.json",
    "environment.json",
    "manifest.json",
)


class EpisodeTimeoutError(TimeoutError):
    """Raised by the POSIX per-episode hard alarm."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _json_bytes(value: Any, *, indent: Optional[int] = 2) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=indent,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _sha256_value(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def _write_jsonl_atomic(path: Path, records: Iterable[Mapping[str, Any]]) -> None:
    _write_atomic(
        path,
        b"".join(_json_bytes(record, indent=None) for record in records),
    )


def _write_gzip_jsonl_atomic(
    path: Path,
    records: Iterable[Mapping[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as raw:
        with gzip.GzipFile(
            filename="",
            mode="wb",
            fileobj=raw,
            compresslevel=9,
            mtime=0,
        ) as compressed:
            for record in records:
                compressed.write(_json_bytes(record, indent=None))
    os.replace(temporary, path)


def _task_from_payload(payload: Mapping[str, Any]) -> CalibrationTask:
    instance = load_calibration_instance()
    required = {
        "task_schema_version",
        "instance_id",
        "instance_sha256",
        "source_commit",
        "execution_commit",
        "split",
        "family",
        "scale",
        "seed",
        "policy_id",
        "control_policy_id",
        "control_run_id",
        "control_mode",
        "run_id",
        "shard_name",
    }
    missing = required.difference(payload)
    if missing:
        raise ValueError(f"Task payload missing fields: {sorted(missing)}")
    task = CalibrationTask(
        instance_id=str(payload["instance_id"]),
        instance_sha256=str(payload["instance_sha256"]),
        source_commit=str(payload["source_commit"]),
        execution_commit=str(payload["execution_commit"]),
        split=str(payload["split"]),
        family=str(payload["family"]),
        scale=int(payload["scale"]),
        seed=int(payload["seed"]),
        policy_id=str(payload["policy_id"]),
    )
    if task.to_dict() != dict(payload):
        raise ValueError("Task payload differs from its canonical identity")
    if task.instance_id != instance["instance_id"]:
        raise ValueError("Task references another calibration instance")
    if task.instance_sha256 != instance_sha256(instance):
        raise ValueError("Task instance digest differs from the frozen instance")
    if task.source_commit != instance["source_commit"]:
        raise ValueError("Task source commit differs from the frozen instance")
    if task.split != "calibration":
        raise ValueError("WP-GATE-0.6 executes calibration tasks only")
    if not re.fullmatch(r"[0-9a-f]{40}", task.execution_commit):
        raise ValueError("Task execution commit must be a full SHA")
    if task.family not in instance["domain_manifest"]["families"]:
        raise ValueError("Task family is outside the frozen instance")
    if task.scale not in instance["domain_manifest"]["scales"]:
        raise ValueError("Task scale is outside the frozen instance")
    if task.seed not in instance["split_manifests"]["calibration"]["generator_seeds"]:
        raise ValueError("Task seed is outside calibration")
    policy_ids = {
        str(candidate["policy_id"]) for candidate in instance["candidate_policies"]
    }
    if task.policy_id not in policy_ids:
        raise ValueError("Task policy is outside the frozen candidate set")
    return task


def validate_execution_authorization(
    authorization: Mapping[str, Any],
    *,
    execution_commit: str,
) -> None:
    """Require a separately created calibration-only authorization record."""
    instance = load_calibration_instance()
    expected = {
        "authorization_schema_version": AUTHORIZATION_SCHEMA_VERSION,
        "instance_id": instance["instance_id"],
        "instance_sha256": instance_sha256(instance),
        "execution_commit": execution_commit,
        "authorized_split": "calibration",
        "calibration_execution_authorized": True,
        "verification_execution_authorized": False,
        "protected_holdout_execution_authorized": False,
        "retuning_after_authorization": False,
    }
    for key, value in expected.items():
        if authorization.get(key) != value:
            raise PermissionError(f"Invalid calibration authorization field {key}")
    if not re.fullmatch(r"[0-9a-f]{40}", execution_commit):
        raise PermissionError("Authorization requires a full execution commit")
    if not isinstance(authorization.get("authorized_by"), str) or not str(
        authorization["authorized_by"]
    ).strip():
        raise PermissionError("Authorization requires authorized_by")
    if not isinstance(authorization.get("authorized_on"), str) or not str(
        authorization["authorized_on"]
    ).strip():
        raise PermissionError("Authorization requires authorized_on")


@contextmanager
def _episode_deadline(seconds: float):
    """Interrupt Python work at the deadline on POSIX worker processes."""
    if seconds <= 0:
        raise ValueError("Episode timeout must be positive")
    if not hasattr(signal, "SIGALRM") or not hasattr(signal, "setitimer"):
        yield
        return

    def alarm_handler(signum, frame):
        raise EpisodeTimeoutError(f"Episode exceeded {seconds} seconds")

    previous = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, alarm_handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, previous)


def _peak_rss_bytes() -> int:
    try:
        import resource

        peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        return peak if sys.platform == "darwin" else peak * 1024
    except (ImportError, OSError, ValueError):
        return 0


def _enrich_branch_record(
    task: CalibrationTask,
    record: Mapping[str, Any],
) -> Dict[str, Any]:
    enriched = {
        "instance_id": task.instance_id,
        "instance_sha256": task.instance_sha256,
        "source_commit": task.source_commit,
        "execution_commit": task.execution_commit,
        "split": task.split,
        "run_id": task.run_id,
        "holdout_accessed": False,
        "not_gate_result": True,
        **dict(record),
    }
    validate_artifact_record("paired_branch_record", enriched)
    return enriched


def _classify_branches(
    policy_mode: OverrideGateMode,
    min_support_margin: Optional[float],
    paired_records: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    if policy_mode is OverrideGateMode.DISABLED:
        attributed: List[Mapping[str, Any]] = []
    else:
        assert min_support_margin is not None
        attributed = [
            record
            for record in paired_records
            if float(record["support_margin"]) >= float(min_support_margin)
        ]
    beneficial = 0
    neutral = 0
    harmful = 0
    severe = 0
    unresolved = 0
    resolved_deltas = []
    for record in attributed:
        branch_reasons = {
            str(record["greedy_branch"]["terminal_reason"]),
            str(record["lookahead_branch"]["terminal_reason"]),
        }
        if branch_reasons.intersection(
            {"algorithm_timeout", "path_cap_hit", "method_out_of_memory"}
        ):
            unresolved += 1
            continue
        delta = float(record["delta_utility"])
        resolved_deltas.append(delta)
        if delta < -0.01:
            harmful += 1
            if delta <= -0.10:
                severe += 1
        elif delta > 0.01:
            beneficial += 1
        else:
            neutral += 1
    return {
        "attributed_override_count": len(attributed),
        "beneficial_overrides": beneficial,
        "neutral_overrides": neutral,
        "harmful_overrides": harmful,
        "severe_harmful_overrides": severe,
        "unresolved_overrides": unresolved,
        "paired_utility_difference": (
            mean(resolved_deltas) if resolved_deltas else None
        ),
    }


def build_completed_shard(
    task: CalibrationTask,
    episodes: Sequence[InstrumentedEpisodeResult],
    *,
    wall_time_ms: float,
    peak_rss_bytes: int,
    forced_status: Optional[str] = None,
) -> Dict[str, Any]:
    """Build one complete or valid-negative task shard."""
    instance = load_calibration_instance()
    adaptation = int(instance["domain_manifest"]["adaptation_episodes"])
    expected_episodes = adaptation + int(
        instance["domain_manifest"]["evaluation_episodes"]
    )
    if forced_status is None and len(episodes) != expected_episodes:
        raise ValueError(
            f"Completed shard requires {expected_episodes} episodes, got {len(episodes)}"
        )
    policy = candidate_policy(task.policy_id)
    evaluation = [
        episode for episode in episodes if episode.summary.episode_index >= adaptation
    ]
    branch_records = [
        _enrich_branch_record(task, paired.to_record())
        for episode in episodes
        if episode.summary.episode_index >= adaptation
        for paired in episode.paired_decisions
    ]
    parent_path_cap_hits = sum(episode.path_cap_hits for episode in evaluation)
    branch_path_cap_hits = sum(
        record["path_cap_hit"]
        or record["greedy_branch"]["terminal_reason"] == "path_cap_hit"
        or record["lookahead_branch"]["terminal_reason"] == "path_cap_hit"
        for record in branch_records
    )
    path_cap_hits = parent_path_cap_hits + branch_path_cap_hits
    status = forced_status or ("path_cap_hit" if path_cap_hits else "completed")
    primary_utility = (
        mean(
            episode.summary.success_adjusted_efficiency
            for episode in evaluation
        )
        if status == "completed" and evaluation
        else 0.0
    )
    decision_records = [
        record
        for episode in episodes
        if episode.summary.episode_index >= adaptation
        for record in episode.decision_records
    ]
    observed_disagreement_count = sum(
        record.preferred_action is not None
        and record.greedy_action is not None
        and record.preferred_action != record.greedy_action
        for record in decision_records
    )
    classified = _classify_branches(
        policy.mode,
        policy.min_support_margin,
        branch_records,
    )
    raw = {
        "instance_id": task.instance_id,
        "instance_sha256": task.instance_sha256,
        "source_commit": task.source_commit,
        "execution_commit": task.execution_commit,
        "split": "calibration",
        "run_id": task.run_id,
        "domain_family": task.family,
        "scale": task.scale,
        "generator_seed": task.seed,
        "outcome_seed": 200000 + task.seed,
        "policy_seed": 300000 + task.seed,
        "policy_id": task.policy_id,
        "control_policy_id": task.control_policy_id,
        "control_run_id": task.control_run_id,
        "primary_utility": primary_utility,
        "primary_effect_vs_disabled": (
            0.0 if task.policy_id == "gate_disabled" else None
        ),
        "override_count": sum(record.override for record in decision_records),
        # Every preferred/greedy disagreement observed on the parent trajectory,
        # before the common path guards or candidate confidence threshold.
        "observed_disagreement_count": observed_disagreement_count,
        # Disagreements that pass the common non-confidence guards and therefore
        # receive paired branch evidence.  The threshold may still reject them.
        "eligible_disagreement_count": len(branch_records),
        **classified,
        "path_cap_hits": path_cap_hits,
        "infrastructure_failure": False,
        "status": status,
        "episode_count_completed": len(episodes),
        "evaluation_episode_count_completed": len(evaluation),
        "wall_time_ms": round(float(wall_time_ms), 6),
        "peak_rss_bytes": int(peak_rss_bytes),
        "holdout_accessed": False,
        "not_gate_result": True,
    }
    if raw["override_count"] != raw["attributed_override_count"]:
        raise RuntimeError(
            "Parent override count differs from attributed paired decisions"
        )
    if raw["eligible_disagreement_count"] > raw["observed_disagreement_count"]:
        raise RuntimeError(
            "Guard-eligible disagreements exceed observed disagreements"
        )
    validate_artifact_record("closed_loop_replicate_record", raw)
    episode_records = [
        {
            "instance_id": task.instance_id,
            "instance_sha256": task.instance_sha256,
            "source_commit": task.source_commit,
            "execution_commit": task.execution_commit,
            "split": "calibration",
            "run_id": task.run_id,
            "policy_id": task.policy_id,
            "holdout_accessed": False,
            "not_gate_result": True,
            **episode.summary.to_record(),
            "path_cap_hits": episode.path_cap_hits,
        }
        for episode in episodes
    ]
    shard = {
        "calibration_shard_version": CALIBRATION_SHARD_VERSION,
        "artifact_kind": "calibration_task_shard",
        "task": task.to_dict(),
        "raw_run": raw,
        "episodes": episode_records,
        "paired_branch_records": branch_records,
    }
    shard["shard_sha256"] = _sha256_value(shard)
    return shard


def algorithm_timeout_shard(
    task: CalibrationTask,
    *,
    wall_time_ms: float,
    completed_episodes: Sequence[InstrumentedEpisodeResult] = (),
) -> Dict[str, Any]:
    """Retain completed episode evidence while scoring the replicate zero."""
    return build_completed_shard(
        task,
        completed_episodes,
        wall_time_ms=wall_time_ms,
        peak_rss_bytes=_peak_rss_bytes(),
        forced_status="algorithm_timeout",
    )


def execute_calibration_task(
    task_payload: Mapping[str, Any],
    *,
    checkpoint: Optional[Callable[[InstrumentedEpisodeResult], None]] = None,
) -> Dict[str, Any]:
    """Execute one authorized-by-caller task inside its fresh child process."""
    task = _task_from_payload(task_payload)
    domain = build_calibration_domain(task.family, task.scale, task.seed)
    policy = candidate_policy(task.policy_id)
    instance = load_calibration_instance()
    episode_count = int(instance["domain_manifest"]["adaptation_episodes"]) + int(
        instance["domain_manifest"]["evaluation_episodes"]
    )
    timeout_seconds = float(
        load_g1_protocol()["interaction_protocol"][
            "wall_time_timeout_seconds_per_episode"
        ]
    )
    started = time.perf_counter()
    episodes: List[InstrumentedEpisodeResult] = []
    try:
        for episode_index in range(episode_count):
            with _episode_deadline(timeout_seconds):
                episode = run_instrumented_episode(
                    domain,
                    policy,
                    episode_index,
                )
                episodes.append(episode)
                if checkpoint is not None:
                    checkpoint(episode)
        return build_completed_shard(
            task,
            episodes,
            wall_time_ms=(time.perf_counter() - started) * 1000.0,
            peak_rss_bytes=_peak_rss_bytes(),
        )
    except EpisodeTimeoutError:
        return algorithm_timeout_shard(
            task,
            wall_time_ms=(time.perf_counter() - started) * 1000.0,
            completed_episodes=episodes,
        )
    except MemoryError:
        return build_completed_shard(
            task,
            episodes,
            wall_time_ms=(time.perf_counter() - started) * 1000.0,
            peak_rss_bytes=_peak_rss_bytes(),
            forced_status="method_out_of_memory",
        )


def _child_entry(
    worker: Callable[[Mapping[str, Any]], Dict[str, Any]],
    task_payload: Mapping[str, Any],
    sender: Any,
) -> None:
    try:
        if worker is execute_calibration_task:
            result = execute_calibration_task(
                task_payload,
                checkpoint=lambda episode: sender.send(
                    {
                        "message_kind": "episode_checkpoint",
                        "episode": episode,
                    }
                ),
            )
        else:
            result = worker(task_payload)
        sender.send({"message_kind": "result", "result": result})
    except BaseException as error:
        sender.send(
            {
                "message_kind": "result",
                "result": {
                    "calibration_shard_version": CALIBRATION_SHARD_VERSION,
                    "artifact_kind": "calibration_infrastructure_failure",
                    "task": dict(task_payload),
                    "infrastructure_error": {
                        "type": type(error).__name__,
                        "message": str(error),
                    },
                },
            }
        )
    finally:
        sender.close()


def execute_calibration_task_bounded(
    task_payload: Mapping[str, Any],
    *,
    timeout_seconds: Optional[float] = None,
    worker: Callable[
        [Mapping[str, Any]],
        Dict[str, Any],
    ] = execute_calibration_task,
) -> Dict[str, Any]:
    """Run one task in a killable fresh process with a hard replicate limit."""
    task = _task_from_payload(task_payload)
    configured = float(
        load_g1_protocol()["interaction_protocol"][
            "wall_time_timeout_seconds_per_replicate"
        ]
    )
    limit = configured if timeout_seconds is None else float(timeout_seconds)
    if limit <= 0:
        raise ValueError("Replicate timeout must be positive")
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(
        target=_child_entry,
        args=(worker, task.to_dict(), sender),
    )
    started = time.perf_counter()
    process.start()
    sender.close()
    deadline = started + limit
    completed_episodes: List[InstrumentedEpisodeResult] = []
    try:
        while True:
            remaining = deadline - time.perf_counter()
            if receiver.poll(max(0.0, min(remaining, 0.25))):
                message = receiver.recv()
                if message.get("message_kind") == "episode_checkpoint":
                    completed_episodes.append(message["episode"])
                    continue
                if message.get("message_kind") != "result":
                    raise RuntimeError("Child returned an unknown message")
                process.join(timeout=5.0)
                return message["result"]
            if not process.is_alive():
                process.join(timeout=1.0)
                if receiver.poll():
                    return receiver.recv()
                return {
                    "calibration_shard_version": CALIBRATION_SHARD_VERSION,
                    "artifact_kind": "calibration_infrastructure_failure",
                    "task": task.to_dict(),
                    "infrastructure_error": {
                        "type": "WorkerExitError",
                        "message": (
                            f"child exited with code {process.exitcode} "
                            "without a result"
                        ),
                    },
                }
            if remaining <= 0.0:
                process.terminate()
                process.join(timeout=5.0)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=5.0)
                return algorithm_timeout_shard(
                    task,
                    wall_time_ms=(time.perf_counter() - started) * 1000.0,
                    completed_episodes=completed_episodes,
                )
    finally:
        receiver.close()
        if process.is_alive():
            process.terminate()
            process.join(timeout=5.0)


def validate_calibration_shard(
    shard: Mapping[str, Any],
    task: CalibrationTask,
) -> None:
    """Reject corrupt, stale, leaking, or incomplete resume shards."""
    if shard.get("calibration_shard_version") != CALIBRATION_SHARD_VERSION:
        raise ValueError("Calibration shard version mismatch")
    if shard.get("task") != task.to_dict():
        raise ValueError("Calibration shard task identity mismatch")
    payload = dict(shard)
    recorded_digest = payload.pop("shard_sha256", None)
    if recorded_digest != _sha256_value(payload):
        raise ValueError("Calibration shard digest mismatch")
    if "raw_run" not in shard:
        raise ValueError("Infrastructure failures are not resumable result shards")
    raw = shard["raw_run"]
    validate_artifact_record("closed_loop_replicate_record", raw)
    raw_identity = {
        "run_id": task.run_id,
        "domain_family": task.family,
        "scale": task.scale,
        "generator_seed": task.seed,
        "policy_id": task.policy_id,
        "control_policy_id": task.control_policy_id,
        "control_run_id": task.control_run_id,
    }
    for field, expected in raw_identity.items():
        if raw.get(field) != expected:
            raise ValueError(f"Raw run {field} differs from task")
    if raw.get("status") not in {
        "completed",
        "algorithm_timeout",
        "path_cap_hit",
        "method_out_of_memory",
    }:
        raise ValueError("Raw run has an invalid algorithmic status")
    if raw.get("infrastructure_failure") is not False:
        raise ValueError("Infrastructure failures cannot be result shards")

    instance = load_calibration_instance()
    adaptation = int(instance["domain_manifest"]["adaptation_episodes"])
    evaluation = int(instance["domain_manifest"]["evaluation_episodes"])
    expected = adaptation + evaluation
    episodes = shard.get("episodes", [])
    if not isinstance(episodes, list):
        raise ValueError("Shard episodes must be a list")
    if len(episodes) > expected:
        raise ValueError("Shard contains too many episodes")
    if raw.get("episode_count_completed") != len(episodes):
        raise ValueError("Raw episode count differs from retained episodes")
    indices = [record.get("episode_index") for record in episodes]
    if indices != list(range(len(episodes))):
        raise ValueError("Retained episodes are not a contiguous prefix")
    for record in episodes:
        episode_index = int(record["episode_index"])
        episode_identity = {
            "instance_id": task.instance_id,
            "instance_sha256": task.instance_sha256,
            "source_commit": task.source_commit,
            "execution_commit": task.execution_commit,
            "split": "calibration",
            "run_id": task.run_id,
            "policy_id": task.policy_id,
            "holdout_accessed": False,
            "not_gate_result": True,
            "phase": "adaptation" if episode_index < adaptation else "evaluation",
        }
        for field, expected_value in episode_identity.items():
            if record.get(field) != expected_value:
                raise ValueError(f"Episode {field} differs from task")

    paired_records = shard.get("paired_branch_records", [])
    if not isinstance(paired_records, list):
        raise ValueError("Shard paired branches must be a list")
    if raw.get("eligible_disagreement_count") != len(paired_records):
        raise ValueError("Raw disagreement count differs from paired branches")
    if not (
        int(raw.get("override_count", -1))
        <= int(raw.get("eligible_disagreement_count", -1))
        <= int(raw.get("observed_disagreement_count", -1))
    ):
        raise ValueError(
            "Disagreement counts must satisfy override <= eligible <= observed"
        )
    for record in shard.get("paired_branch_records", []):
        validate_artifact_record("paired_branch_record", record)
        branch_identity = {
            "run_id": task.run_id,
            "domain_family": task.family,
            "scale": task.scale,
            "generator_seed": task.seed,
        }
        for field, expected_value in branch_identity.items():
            if record.get(field) != expected_value:
                raise ValueError(f"Paired branch {field} differs from task")
        if not adaptation <= int(record["episode_index"]) < expected:
            raise ValueError("Paired branch lies outside evaluation episodes")
    if raw["status"] == "completed":
        if len(episodes) != expected:
            raise ValueError("Completed shard has incomplete episodes")
        if raw.get("evaluation_episode_count_completed") != evaluation:
            raise ValueError("Completed shard has incomplete evaluation episodes")
    elif float(raw.get("primary_utility", math.nan)) != 0.0:
        raise ValueError("Valid-negative algorithmic status must score zero")


def load_calibration_shard(
    path: Path,
    task: CalibrationTask,
) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        shard = json.loads(path.read_text(encoding="utf-8"))
        validate_calibration_shard(shard, task)
        return shard
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def _write_failure_artifact(
    failures_dir: Path,
    task: CalibrationTask,
    shard: Mapping[str, Any],
) -> Path:
    failures_dir.mkdir(parents=True, exist_ok=True)
    index = 1
    while True:
        path = failures_dir / f"{task.shard_name}.attempt-{index:03d}.json"
        if not path.exists():
            _write_atomic(path, _json_bytes(shard))
            return path
        index += 1


def _execution_cells(
    tasks: Sequence[CalibrationTask],
) -> Dict[tuple[str, str, int], List[CalibrationTask]]:
    """Require complete candidate-family-scale cells for unbiased retries."""
    instance = load_calibration_instance()
    expected_seeds = set(
        instance["split_manifests"]["calibration"]["generator_seeds"]
    )
    cells: Dict[tuple[str, str, int], List[CalibrationTask]] = {}
    seen = set()
    for task in tasks:
        canonical = _task_from_payload(task.to_dict())
        if canonical != task:
            raise ValueError("Execution task differs from canonical calibration task")
        if task.run_id in seen:
            raise ValueError(f"Duplicate execution task {task.run_id}")
        seen.add(task.run_id)
        cells.setdefault(
            (task.policy_id, task.family, task.scale),
            [],
        ).append(task)
    for cell, cell_tasks in cells.items():
        seeds = {task.seed for task in cell_tasks}
        if seeds != expected_seeds or len(cell_tasks) != len(expected_seeds):
            raise ValueError(
                "Execution subsets must contain complete candidate-family-scale "
                f"cells; incomplete cell {cell}"
            )
    return cells


def execute_task_set(
    tasks: Sequence[CalibrationTask],
    output_dir: Path,
    *,
    authorization: Mapping[str, Any],
    workers: int,
    bounded_executor: Callable[
        [Mapping[str, Any]],
        Dict[str, Any],
    ] = execute_calibration_task_bounded,
    progress: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, int]:
    """Execute/resume authorized calibration tasks and persist atomic shards."""
    if workers <= 0:
        raise ValueError("workers must be positive")
    if not tasks:
        raise ValueError("Task set must not be empty")
    commits = {task.execution_commit for task in tasks}
    if len(commits) != 1:
        raise ValueError("Task set mixes execution commits")
    execution_commit = next(iter(commits))
    validate_execution_authorization(
        authorization,
        execution_commit=execution_commit,
    )
    cells = _execution_cells(tasks)
    output = Path(output_dir)
    shards_dir = output / "shards"
    failures_dir = output / "failures"
    shards_dir.mkdir(parents=True, exist_ok=True)
    pending = []
    completed = 0
    resumed = 0
    for cell_tasks in cells.values():
        existing = [
            load_calibration_shard(shards_dir / task.shard_name, task)
            for task in cell_tasks
        ]
        if all(shard is not None for shard in existing):
            completed += len(cell_tasks)
            resumed += len(cell_tasks)
        else:
            # One infrastructure failure invalidates the entire frozen cell.
            # Existing successful shards are overwritten by the full-cell retry;
            # the failure artifact itself remains immutable under failures/.
            pending.extend(cell_tasks)
    infrastructure_failures = 0
    if progress is not None:
        progress(
            {
                "event": "batch_start",
                "planned": len(tasks),
                "resumed": resumed,
                "pending": len(pending),
            }
        )
    if pending:
        executor_kwargs: Dict[str, Any] = {"max_workers": workers}
        if sys.version_info >= (3, 11):
            executor_kwargs["max_tasks_per_child"] = 1
        with ProcessPoolExecutor(**executor_kwargs) as executor:
            futures: Dict[Future, CalibrationTask] = {
                executor.submit(bounded_executor, task.to_dict()): task
                for task in pending
            }
            for future in as_completed(futures):
                task = futures[future]
                try:
                    shard = future.result()
                except BaseException as error:
                    shard = {
                        "calibration_shard_version": CALIBRATION_SHARD_VERSION,
                        "artifact_kind": "calibration_infrastructure_failure",
                        "task": task.to_dict(),
                        "infrastructure_error": {
                            "type": type(error).__name__,
                            "message": str(error),
                        },
                    }
                try:
                    validate_calibration_shard(shard, task)
                except (KeyError, TypeError, ValueError):
                    _write_failure_artifact(failures_dir, task, shard)
                    infrastructure_failures += 1
                    status = "infrastructure_failure"
                else:
                    _write_atomic(
                        shards_dir / task.shard_name,
                        _json_bytes(shard),
                    )
                    completed += 1
                    status = str(shard["raw_run"]["status"])
                if progress is not None:
                    progress(
                        {
                            "event": "replicate",
                            "planned": len(tasks),
                            "completed": completed,
                            "run_id": task.run_id,
                            "status": status,
                        }
                    )
    return {
        "planned": len(tasks),
        "completed": completed,
        "resumed": resumed,
        "infrastructure_failures": infrastructure_failures,
    }


def calibration_environment(execution_commit: str) -> Dict[str, Any]:
    return {
        "artifact_kind": "calibration_environment",
        "python": sys.version,
        "platform": platform.platform(),
        "executable": sys.executable,
        "source_commit": load_calibration_instance()["source_commit"],
        "execution_commit": execution_commit,
        "instance_sha256": instance_sha256(),
        "posix_episode_alarm_available": (
            hasattr(signal, "SIGALRM") and hasattr(signal, "setitimer")
        ),
        "holdout_accessed": False,
        "not_gate_result": True,
    }


def consolidate_calibration(
    output_dir: Path,
    *,
    execution_commit: str,
) -> Dict[str, Any]:
    """Require all 2,880 valid shards and emit immutable calibration evidence."""
    output = Path(output_dir)
    tasks = build_task_plan(
        "calibration",
        execution_commit=execution_commit,
        planning_only=False,
    )
    shards = []
    missing = []
    for task in tasks:
        shard = load_calibration_shard(output / "shards" / task.shard_name, task)
        if shard is None:
            missing.append(task.run_id)
        else:
            shards.append(shard)
    if missing:
        raise RuntimeError(
            "Cannot consolidate incomplete calibration: "
            f"{len(tasks) - len(missing)}/{len(tasks)} valid shards"
        )
    records = [dict(shard["raw_run"]) for shard in shards]
    controls = {
        (
            row["domain_family"],
            int(row["scale"]),
            int(row["generator_seed"]),
        ): float(row["primary_utility"])
        for row in records
        if row["policy_id"] == "gate_disabled"
    }
    for row in records:
        unit = (
            row["domain_family"],
            int(row["scale"]),
            int(row["generator_seed"]),
        )
        row["primary_effect_vs_disabled"] = (
            float(row["primary_utility"]) - controls[unit]
        )
    paired = [
        record
        for shard in shards
        for record in shard.get("paired_branch_records", [])
    ]
    raw_path = output / "raw_runs.jsonl"
    paired_path = output / "paired_branches.jsonl.gz"
    _write_jsonl_atomic(raw_path, records)
    _write_gzip_jsonl_atomic(paired_path, paired)

    selection = select_calibration_policy(records)
    selection.update(
        {
            "instance_sha256": instance_sha256(),
            "source_commit": load_calibration_instance()["source_commit"],
            "execution_commit": execution_commit,
            "statistics": dict(load_calibration_instance()["statistics"]),
            "artifact_hashes": {
                "raw_runs.jsonl": _sha256_file(raw_path),
                "paired_branches.jsonl.gz": _sha256_file(paired_path),
            },
        }
    )
    validate_artifact_record("selection_record", selection)
    selection_path = output / "selection_report.json"
    _write_atomic(selection_path, _json_bytes(selection))

    selected = candidate_policy(str(selection["selected_policy_id"]))
    policy_record = selected.to_dict()
    policy_record["selection_artifact"] = "selection_report.json"
    policy_record["selection_artifact_sha256"] = _sha256_file(selection_path)
    policy_record["execution_commit"] = execution_commit
    policy_record["holdout_accessed"] = False
    policy_record["not_gate_result"] = True
    policy_path = output / "policy_record.json"
    _write_atomic(policy_path, _json_bytes(policy_record))

    environment_path = output / "environment.json"
    _write_atomic(
        environment_path,
        _json_bytes(calibration_environment(execution_commit)),
    )
    checksums = {
        name: _sha256_file(output / name)
        for name in ARTIFACT_FILES
        if name != "manifest.json" and (output / name).exists()
    }
    manifest = {
        "instance_id": load_calibration_instance()["instance_id"],
        "instance_sha256": instance_sha256(),
        "source_commit": load_calibration_instance()["source_commit"],
        "execution_commit": execution_commit,
        "artifact_kind": "calibration_manifest",
        "split": "calibration",
        "holdout_accessed": False,
        "not_gate_result": True,
        "calibration_executed": True,
        "verification_executed": False,
        "protected_holdout_accessed": False,
        "counts": {
            "task_shards": len(shards),
            "closed_loop_records": len(records),
            "paired_branch_records": len(paired),
            "algorithm_timeouts": sum(
                row["status"] == "algorithm_timeout" for row in records
            ),
            "path_cap_hits": sum(int(row["path_cap_hits"]) for row in records),
            "infrastructure_failures": 0,
        },
        "selected_policy_id": selection["selected_policy_id"],
        "no_eligible_candidate": selection["no_eligible_candidate"],
        "files": checksums,
    }
    manifest["manifest_sha256"] = _sha256_value(manifest)
    _write_atomic(output / "manifest.json", _json_bytes(manifest))
    return manifest
