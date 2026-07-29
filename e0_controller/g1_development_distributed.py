"""Bounded distributed execution for the E0-G1-v1 development matrix.

WP-2.4 replicates are partitioned deterministically across GitHub Actions
matrix jobs.  Every replicate runs in a dedicated child process so the
preregistered 1,800-second replicate timeout is an enforced resource boundary,
not merely a label applied after an unbounded computation returns.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import sys
import time
from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

from .g1_ablations import ABLATION_METHODS, ablation_config_sha256
from .g1_baselines import baseline_config_sha256
from .g1_development_report import (
    DEFAULT_OUTPUT,
    SHARD_VERSION,
    DevelopmentTask,
    _git_value,
    _json_bytes,
    _load_shard,
    _task_grid,
    _write_atomic,
    execute_development_task,
    run_full_development,
)
from .g1_domains import PROTOCOL_ID, build_domain, load_g1_protocol, protocol_sha256

DEFAULT_BATCH_COUNT = 240
MAX_GITHUB_MATRIX_JOBS = 256


def partition_tasks(
    tasks: Sequence[DevelopmentTask],
    batch_count: int,
) -> List[List[DevelopmentTask]]:
    """Return stable, balanced strided batches without duplicating tasks."""
    if batch_count <= 0:
        raise ValueError("batch_count must be positive")
    if batch_count > MAX_GITHUB_MATRIX_JOBS:
        raise ValueError(f"batch_count exceeds GitHub's {MAX_GITHUB_MATRIX_JOBS}-job matrix limit")
    if batch_count > len(tasks):
        raise ValueError("batch_count must not exceed task count")
    return [list(tasks[index::batch_count]) for index in range(batch_count)]


def github_matrix(batch_count: int = DEFAULT_BATCH_COUNT) -> Dict[str, Any]:
    """Build the JSON matrix consumed by ``strategy.matrix``."""
    tasks = _task_grid("matrix-plan")
    batches = partition_tasks(tasks, batch_count)
    return {
        "include": [
            {
                "batch_index": index,
                "task_count": len(batch),
            }
            for index, batch in enumerate(batches)
        ]
    }


def _oracle_cost(family: str, scale: int, seed: int, episode_index: int) -> int:
    domain = build_domain(family, scale, seed)
    if "stationary" in domain.oracle_cost_by_regime:
        return int(domain.oracle_cost_by_regime["stationary"])
    switch = int(domain.metadata["switch_absolute_episode_index"])
    regime = "pre_switch" if episode_index < switch else "post_switch"
    return int(domain.oracle_cost_by_regime[regime])


def _timeout_episode(
    task: DevelopmentTask,
    episode_index: int,
) -> Dict[str, Any]:
    protocol = load_g1_protocol()
    adaptation = int(protocol["interaction_protocol"]["adaptation_episodes"])
    budget = 4 * task.scale
    domain = build_domain(task.family, task.scale, task.seed)
    return {
        "protocol_id": PROTOCOL_ID,
        "artifact_kind": "development_evaluation_episode",
        "not_g1_result": True,
        "holdout_accessed": False,
        "split": "development",
        "commit": task.source_commit,
        "run_id": task.run_id,
        "domain_family": task.family,
        "target_node_count": task.scale,
        "generator_seed": task.seed,
        "method": task.method,
        "episode_index": episode_index,
        "phase": "adaptation" if episode_index < adaptation else "evaluation",
        "goal_reached": False,
        "interactions_used": 0,
        "interaction_budget": budget,
        "total_cost": 0.0,
        "oracle_cost": _oracle_cost(
            task.family,
            task.scale,
            task.seed,
            episode_index,
        ),
        "success_adjusted_efficiency": 0.0,
        "revisits": 0,
        "failure_count": 0,
        "terminal_reason": "algorithm_timeout",
        "final_state": domain.start,
        "path": [domain.start],
        "status": "algorithm_timeout",
        "wall_time_ms": 0.0,
        "decision_count": 0,
        "paths_expanded": 0,
        "path_cap_hits": 0,
        "override_count": 0,
        "override_success_count": 0,
        "override_success_rate": None,
        "phase_regime_gradient_count": 0,
        "phase_regime_interfering_count": 0,
        "phase_regime_wrapped_count": 0,
        "executed": False,
        "measurement_censored": True,
    }


def timeout_shard(
    task_payload: Mapping[str, Any],
    wall_time_ms: float,
) -> Dict[str, Any]:
    """Create a protocol-valid negative shard after hard process termination."""
    task = DevelopmentTask(
        family=str(task_payload["family"]),
        scale=int(task_payload["scale"]),
        seed=int(task_payload["seed"]),
        method=str(task_payload["method"]),
        source_commit=str(task_payload["source_commit"]),
    )
    protocol = load_g1_protocol()
    adaptation = int(protocol["interaction_protocol"]["adaptation_episodes"])
    evaluation = int(protocol["interaction_protocol"]["evaluation_episodes"])
    total = adaptation + evaluation
    domain = build_domain(task.family, task.scale, task.seed)
    episodes = [_timeout_episode(task, index) for index in range(total)]
    evaluation_episodes = [item for item in episodes if item["phase"] == "evaluation"]
    config_hash = (
        ablation_config_sha256() if task.method in ABLATION_METHODS else baseline_config_sha256()
    )
    return {
        "shard_version": SHARD_VERSION,
        "task": task.to_dict(),
        "hard_timeout_enforced": True,
        "raw_run": {
            "protocol_id": PROTOCOL_ID,
            "protocol_sha256": protocol_sha256(),
            "artifact_kind": "development_full_run",
            "not_g1_result": True,
            "holdout_accessed": False,
            "split": "development",
            "commit": task.source_commit,
            "run_id": task.run_id,
            "domain_family": task.family,
            "target_node_count": task.scale,
            "actual_node_count": domain.actual_node_count,
            "generator_seed": task.seed,
            "outcome_seed": domain.outcome_seed,
            "policy_seed": domain.policy_seed,
            "method": task.method,
            "method_category": ("e0_ablation" if task.method in ABLATION_METHODS else "baseline"),
            "config_hash": config_hash,
            "interaction_budget": 4 * domain.actual_node_count,
            "episode_count": total,
            "evaluation_episode_count": evaluation,
            "interactions_used": 0,
            "evaluation_interactions_used": 0,
            "success_adjusted_efficiency": 0.0,
            "goal_rate": 0.0,
            "mean_steps": 0.0,
            "mean_total_cost": 0.0,
            "mean_oracle_cost": (
                sum(float(item["oracle_cost"]) for item in evaluation_episodes)
                / len(evaluation_episodes)
            ),
            "mean_oracle_regret": 0.0,
            "revisits": 0,
            "failure_count": 0,
            "post_switch_recovery_episodes": (
                evaluation if task.family == "nonstationary_parallel" else None
            ),
            "wall_time_ms": round(wall_time_ms, 6),
            "peak_rss_bytes": 0,
            "paths_expanded": 0,
            "path_cap_hits": 0,
            "override_count": 0,
            "override_success_rate": None,
            "phase_regime_gradient_count": 0,
            "phase_regime_interfering_count": 0,
            "phase_regime_wrapped_count": 0,
            "status": "algorithm_timeout",
            "hard_timeout_enforced": True,
            "measurement_censored": True,
        },
        "evaluation_episodes": evaluation_episodes,
    }


def _child_entry(
    task_payload: Mapping[str, Any],
    sender: Any,
) -> None:
    try:
        sender.send(execute_development_task(task_payload))
    except BaseException as error:
        sender.send(
            {
                "shard_version": SHARD_VERSION,
                "task": dict(task_payload),
                "infrastructure_error": {
                    "type": type(error).__name__,
                    "message": str(error),
                },
            }
        )
    finally:
        sender.close()


def execute_development_task_bounded(
    task_payload: Mapping[str, Any],
    *,
    timeout_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    """Run one replicate in a killable child process."""
    configured = float(
        load_g1_protocol()["interaction_protocol"]["wall_time_timeout_seconds_per_replicate"]
    )
    limit = configured if timeout_seconds is None else float(timeout_seconds)
    if limit <= 0:
        raise ValueError("timeout_seconds must be positive")
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(
        target=_child_entry,
        args=(dict(task_payload), sender),
    )
    started = time.perf_counter()
    process.start()
    sender.close()
    deadline = started + limit
    try:
        while True:
            remaining = deadline - time.perf_counter()
            if receiver.poll(max(0.0, min(remaining, 0.25))):
                result = receiver.recv()
                process.join(timeout=5.0)
                return result
            if not process.is_alive():
                process.join(timeout=1.0)
                if receiver.poll():
                    return receiver.recv()
                return {
                    "shard_version": SHARD_VERSION,
                    "task": dict(task_payload),
                    "infrastructure_error": {
                        "type": "WorkerExitError",
                        "message": f"child exited with code {process.exitcode} without a result",
                    },
                }
            if remaining <= 0.0:
                process.terminate()
                process.join(timeout=5.0)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=5.0)
                wall_ms = (time.perf_counter() - started) * 1000.0
                return timeout_shard(task_payload, wall_ms)
    finally:
        receiver.close()
        if process.is_alive():
            process.terminate()
            process.join(timeout=5.0)


def execute_task_set(
    tasks: Sequence[DevelopmentTask],
    output_dir: Path,
    *,
    workers: int,
    progress: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, int]:
    """Execute a bounded set and persist each result atomically."""
    if workers <= 0:
        raise ValueError("workers must be positive")
    output = Path(output_dir)
    shards_dir = output / "shards"
    shards_dir.mkdir(parents=True, exist_ok=True)
    completed = 0
    resumed = 0
    pending: List[DevelopmentTask] = []
    for task in tasks:
        shard = _load_shard(shards_dir / task.shard_name, task)
        if shard is not None and "raw_run" in shard:
            completed += 1
            resumed += 1
        else:
            pending.append(task)
    if progress is not None:
        progress(
            {
                "event": "batch_start",
                "planned": len(tasks),
                "resumed": resumed,
                "pending": len(pending),
            }
        )
    failures = 0
    if pending:
        executor_kwargs: Dict[str, Any] = {"max_workers": workers}
        if sys.version_info >= (3, 11):
            executor_kwargs["max_tasks_per_child"] = 1
        with ProcessPoolExecutor(**executor_kwargs) as executor:
            futures: Dict[Future, DevelopmentTask] = {
                executor.submit(execute_development_task_bounded, task.to_dict()): task
                for task in pending
            }
            for future in as_completed(futures):
                task = futures[future]
                try:
                    shard = future.result()
                except BaseException as error:
                    shard = {
                        "shard_version": SHARD_VERSION,
                        "task": task.to_dict(),
                        "infrastructure_error": {
                            "type": type(error).__name__,
                            "message": str(error),
                        },
                    }
                _write_atomic(shards_dir / task.shard_name, _json_bytes(shard))
                if "raw_run" in shard:
                    completed += 1
                else:
                    failures += 1
                if progress is not None:
                    progress(
                        {
                            "event": "replicate",
                            "completed": completed,
                            "planned": len(tasks),
                            "run_id": task.run_id,
                            "status": (
                                shard.get("raw_run", {}).get("status") or "infrastructure_failure"
                            ),
                        }
                    )
    return {
        "planned": len(tasks),
        "completed": completed,
        "resumed": resumed,
        "infrastructure_failures": failures,
    }


def run_batch(
    output_dir: Path,
    *,
    batch_index: int,
    batch_count: int = DEFAULT_BATCH_COUNT,
    workers: int = 4,
    progress: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, int]:
    """Execute one deterministic GitHub matrix batch."""
    source_commit = _git_value("rev-parse", "HEAD") or "unknown"
    tasks = _task_grid(source_commit)
    batches = partition_tasks(tasks, batch_count)
    if batch_index < 0 or batch_index >= len(batches):
        raise ValueError(f"batch_index must lie in 0..{len(batches) - 1}")
    return execute_task_set(
        batches[batch_index],
        output_dir,
        workers=workers,
        progress=progress,
    )


def consolidate_distributed(
    output_dir: Path,
    *,
    report: Path,
) -> Dict[str, Any]:
    """Validate the complete shard set before invoking normal consolidation."""
    output = Path(output_dir)
    source_commit = _git_value("rev-parse", "HEAD") or "unknown"
    tasks = _task_grid(source_commit)
    missing = [
        task.run_id
        for task in tasks
        if _load_shard(output / "shards" / task.shard_name, task) is None
    ]
    if missing:
        raise RuntimeError(
            f"Cannot consolidate incomplete distributed matrix: "
            f"{len(tasks) - len(missing)}/{len(tasks)} valid shards"
        )
    manifest = run_full_development(output, workers=1, resume=True)
    from .g1_development_report import render_development_report

    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    _write_atomic(report, (render_development_report(summary) + "\n").encode("utf-8"))
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    matrix_parser = subparsers.add_parser("matrix")
    matrix_parser.add_argument("--batch-count", type=int, default=DEFAULT_BATCH_COUNT)

    batch_parser = subparsers.add_parser("run-batch")
    batch_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    batch_parser.add_argument("--batch-index", type=int, required=True)
    batch_parser.add_argument("--batch-count", type=int, default=DEFAULT_BATCH_COUNT)
    batch_parser.add_argument(
        "--workers",
        type=int,
        default=max(1, min(4, os.cpu_count() or 1)),
    )

    consolidate_parser = subparsers.add_parser("consolidate")
    consolidate_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    consolidate_parser.add_argument(
        "--report",
        type=Path,
        default=Path("docs/research/E0_DECISION_BENCHMARK_v1.md"),
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "matrix":
        print(json.dumps(github_matrix(args.batch_count), separators=(",", ":")))
        return 0

    def emit(event: Dict[str, Any]) -> None:
        print(json.dumps(event, sort_keys=True), flush=True)

    try:
        if args.command == "run-batch":
            result = run_batch(
                args.output,
                batch_index=args.batch_index,
                batch_count=args.batch_count,
                workers=args.workers,
                progress=emit,
            )
            emit({"event": "batch_complete", **result})
            return 0 if result["infrastructure_failures"] == 0 else 2
        manifest = consolidate_distributed(args.output, report=args.report)
        emit(
            {
                "event": "consolidation_complete",
                "completed": manifest["counts"]["completed_replicates"],
                "selected_control": manifest["primary_control_selected"],
                "not_g1_result": manifest["not_g1_result"],
            }
        )
        return 0
    except (FileExistsError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
