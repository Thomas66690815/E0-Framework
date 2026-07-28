"""Full development experiment and report pipeline for E0-G1-v1 (WP-2.4).

The runner executes every preregistered E0 ablation and baseline for the full
10-adaptation + 20-evaluation protocol on development seeds only.  Each
replicate is isolated in a fresh worker process and persisted as an atomic
shard, making a long run resumable without changing seeds or method state.

Development output selects and freezes the simpler G1-A control.  It is not a
holdout result and cannot pass or fail Gate G1.
"""

from __future__ import annotations

import argparse
import ctypes
import gzip
import hashlib
import json
import math
import os
import random
import statistics
import subprocess
import sys
import time
from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .g1_ablations import (
    ABLATION_METHODS,
    ablation_config_sha256,
    build_ablation_adapter,
    load_ablation_configs,
    run_ablation_episode,
)
from .g1_baselines import (
    ALL_BASELINE_METHODS,
    COMPETITIVE_METHODS,
    baseline_config_sha256,
    build_adapter,
    load_baseline_configs,
    run_episode,
)
from .g1_domains import (
    GENERATOR_VERSION,
    PROTOCOL_ID,
    build_development_matrix,
    build_domain,
    development_seeds,
    load_g1_protocol,
    protocol_sha256,
    validate_development_seed,
)
from .g1_harness import environment_record

ALL_DEVELOPMENT_METHODS = (*ABLATION_METHODS, *ALL_BASELINE_METHODS)
DEFAULT_OUTPUT = Path("artifacts/g1/E0-G1-v1/development/wp2_4")
ARTIFACT_FILES = (
    "manifest.json",
    "frozen_configs.json",
    "raw_runs.jsonl",
    "episodes.jsonl.gz",
    "summary.json",
    "environment.json",
)
SHARD_VERSION = 1


@dataclass(frozen=True)
class DevelopmentTask:
    """One method × domain experimental unit."""

    family: str
    scale: int
    seed: int
    method: str
    source_commit: str

    @property
    def run_id(self) -> str:
        return f"dev-{self.family}-N{self.scale}-s{self.seed:04d}-{self.method.lower()}"

    @property
    def shard_name(self) -> str:
        safe = self.method.lower().replace("*", "star")
        return f"{self.family}__N{self.scale}__s{self.seed:04d}__{safe}.json"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "family": self.family,
            "scale": self.scale,
            "seed": self.seed,
            "method": self.method,
            "source_commit": self.source_commit,
            "run_id": self.run_id,
        }


def _json_bytes(data: Any, *, indent: Optional[int] = 2) -> bytes:
    text = json.dumps(data, ensure_ascii=False, sort_keys=True, indent=indent)
    return (text + "\n").encode("utf-8")


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def _write_gzip_atomic(path: Path, records: Iterable[Mapping[str, Any]]) -> None:
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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_value(*args: str) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", *args],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def _peak_rss_bytes() -> int:
    """Best available process peak resident-set measurement."""
    if os.name == "nt":

        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        ok = ctypes.windll.psapi.GetProcessMemoryInfo(
            handle,
            ctypes.byref(counters),
            counters.cb,
        )
        return int(counters.PeakWorkingSetSize) if ok else 0
    try:
        import resource

        value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        return value if sys.platform == "darwin" else value * 1024
    except (ImportError, OSError):
        return 0


def _total_memory_bytes() -> int:
    if os.name == "nt":

        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return int(status.ullTotalPhys)
        return 0
    page_size = os.sysconf("SC_PAGE_SIZE")
    pages = os.sysconf("SC_PHYS_PAGES")
    return int(page_size * pages)


def development_environment() -> Dict[str, Any]:
    """Capture reproducibility metadata without paths or secrets."""
    record = environment_record()
    record.update(
        {
            "artifact_kind": "development_full_environment",
            "logical_cpu_count": os.cpu_count(),
            "total_physical_memory_bytes": _total_memory_bytes(),
            "timer": {
                "implementation": "time.perf_counter",
                "resolution_seconds": time.get_clock_info("perf_counter").resolution,
                "monotonic": time.get_clock_info("perf_counter").monotonic,
            },
        }
    )
    return record


def _episode_phase(index: int) -> str:
    adaptation = int(load_g1_protocol()["interaction_protocol"]["adaptation_episodes"])
    return "adaptation" if index < adaptation else "evaluation"


def _timed_baseline_episodes(
    family: str,
    scale: int,
    seed: int,
    method: str,
) -> Tuple[List[Dict[str, Any]], float]:
    domain = build_domain(family, scale, seed)
    adapter = build_adapter(method, domain)
    interaction = load_g1_protocol()["interaction_protocol"]
    episode_timeout = float(interaction["wall_time_timeout_seconds_per_episode"])
    total_episodes = int(interaction["adaptation_episodes"]) + int(
        interaction["evaluation_episodes"]
    )
    records: List[Dict[str, Any]] = []
    started = time.perf_counter()
    for index in range(total_episodes):
        episode_started = time.perf_counter()
        summary = run_episode(domain, adapter, index)
        wall_ms = (time.perf_counter() - episode_started) * 1000.0
        status = "completed"
        if wall_ms > episode_timeout * 1000.0:
            status = "algorithm_timeout"
            summary = replace(
                summary,
                goal_reached=False,
                success_adjusted_efficiency=0.0,
                terminal_reason=status,
            )
        record = summary.to_record()
        record.update(
            {
                "status": status,
                "wall_time_ms": round(wall_ms, 6),
                "paths_expanded": 0,
                "path_cap_hits": 0,
                "override_count": 0,
                "override_success_count": 0,
                "phase_regime_gradient_count": 0,
                "phase_regime_interfering_count": 0,
                "phase_regime_wrapped_count": 0,
            }
        )
        records.append(record)
    return records, (time.perf_counter() - started) * 1000.0


def _timed_ablation_episodes(
    family: str,
    scale: int,
    seed: int,
    method: str,
) -> Tuple[List[Dict[str, Any]], float]:
    domain = build_domain(family, scale, seed)
    adapter = build_ablation_adapter(method, domain)
    interaction = load_g1_protocol()["interaction_protocol"]
    total_episodes = int(interaction["adaptation_episodes"]) + int(
        interaction["evaluation_episodes"]
    )
    records: List[Dict[str, Any]] = []
    started = time.perf_counter()
    for index in range(total_episodes):
        result = run_ablation_episode(domain, adapter, index)
        records.append(result.to_record())
    return records, (time.perf_counter() - started) * 1000.0


def _post_switch_recovery(
    family: str,
    episodes: Sequence[Mapping[str, Any]],
) -> Optional[int]:
    if family != "nonstationary_parallel":
        return None
    evaluation = [item for item in episodes if item["phase"] == "evaluation"]
    for offset, episode in enumerate(evaluation):
        if episode["goal_reached"]:
            return offset
    return len(evaluation)


def _mean(items: Sequence[float]) -> float:
    return sum(items) / len(items) if items else 0.0


def _summarize_replicate(
    task: DevelopmentTask,
    episodes: List[Dict[str, Any]],
    wall_time_ms: float,
    peak_rss_bytes: int,
) -> Dict[str, Any]:
    domain = build_domain(task.family, task.scale, task.seed)
    evaluation = [item for item in episodes if item["phase"] == "evaluation"]
    protocol = load_g1_protocol()
    replicate_timeout_ms = (
        float(protocol["interaction_protocol"]["wall_time_timeout_seconds_per_replicate"]) * 1000.0
    )
    rss_limit = int(protocol["interaction_protocol"]["peak_rss_limit_bytes_per_method_worker"])
    statuses = {str(item["status"]) for item in episodes}
    if wall_time_ms > replicate_timeout_ms:
        status = "algorithm_timeout"
    elif peak_rss_bytes > rss_limit:
        status = "method_out_of_memory"
    elif "path_cap_hit" in statuses:
        status = "path_cap_hit"
    elif "algorithm_timeout" in statuses:
        status = "algorithm_timeout"
    else:
        status = "completed"
    scores = [float(item["success_adjusted_efficiency"]) for item in evaluation]
    if status != "completed":
        scores = [
            0.0 if item["status"] != "completed" else float(item["success_adjusted_efficiency"])
            for item in evaluation
        ]
        if wall_time_ms > replicate_timeout_ms or peak_rss_bytes > rss_limit:
            scores = [0.0 for _ in evaluation]
    goal_rate = _mean([1.0 if item["goal_reached"] else 0.0 for item in evaluation])
    mean_steps = _mean([float(item["interactions_used"]) for item in evaluation])
    mean_oracle = _mean([float(item["oracle_cost"]) for item in evaluation])
    mean_regret = _mean(
        [
            max(float(item["interactions_used"]) - float(item["oracle_cost"]), 0.0)
            for item in evaluation
        ]
    )
    override_count = sum(int(item["override_count"]) for item in evaluation)
    override_success = sum(int(item["override_success_count"]) for item in evaluation)
    config_hash = (
        ablation_config_sha256() if task.method in ABLATION_METHODS else baseline_config_sha256()
    )
    return {
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
        "episode_count": len(episodes),
        "evaluation_episode_count": len(evaluation),
        "interactions_used": sum(int(item["interactions_used"]) for item in episodes),
        "evaluation_interactions_used": sum(int(item["interactions_used"]) for item in evaluation),
        "success_adjusted_efficiency": _mean(scores),
        "goal_rate": goal_rate,
        "mean_steps": mean_steps,
        "mean_total_cost": _mean([float(item["total_cost"]) for item in evaluation]),
        "mean_oracle_cost": mean_oracle,
        "mean_oracle_regret": mean_regret,
        "revisits": sum(int(item["revisits"]) for item in evaluation),
        "failure_count": sum(int(item["failure_count"]) for item in evaluation),
        "post_switch_recovery_episodes": _post_switch_recovery(task.family, episodes),
        "wall_time_ms": round(wall_time_ms, 6),
        "peak_rss_bytes": peak_rss_bytes,
        "paths_expanded": sum(int(item["paths_expanded"]) for item in evaluation),
        "path_cap_hits": sum(int(item["path_cap_hits"]) for item in evaluation),
        "override_count": override_count,
        "override_success_rate": (override_success / override_count if override_count else None),
        "phase_regime_gradient_count": sum(
            int(item["phase_regime_gradient_count"]) for item in evaluation
        ),
        "phase_regime_interfering_count": sum(
            int(item["phase_regime_interfering_count"]) for item in evaluation
        ),
        "phase_regime_wrapped_count": sum(
            int(item["phase_regime_wrapped_count"]) for item in evaluation
        ),
        "status": status,
    }


def execute_development_task(task_payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Fresh-process worker entry point; JSON-compatible input and output."""
    task = DevelopmentTask(
        family=str(task_payload["family"]),
        scale=int(task_payload["scale"]),
        seed=int(task_payload["seed"]),
        method=str(task_payload["method"]),
        source_commit=str(task_payload["source_commit"]),
    )
    validate_development_seed(task.seed)
    try:
        if task.method in ABLATION_METHODS:
            episodes, wall_ms = _timed_ablation_episodes(
                task.family,
                task.scale,
                task.seed,
                task.method,
            )
        elif task.method in ALL_BASELINE_METHODS:
            episodes, wall_ms = _timed_baseline_episodes(
                task.family,
                task.scale,
                task.seed,
                task.method,
            )
        else:
            raise ValueError(f"Unknown development method {task.method!r}")
        peak = _peak_rss_bytes()
        raw = _summarize_replicate(task, episodes, wall_ms, peak)
        evaluation_records = []
        for episode in episodes:
            if episode["phase"] != "evaluation":
                continue
            evaluation_records.append(
                {
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
                    **episode,
                }
            )
        return {
            "shard_version": SHARD_VERSION,
            "task": task.to_dict(),
            "raw_run": raw,
            "evaluation_episodes": evaluation_records,
        }
    except MemoryError:
        return {
            "shard_version": SHARD_VERSION,
            "task": task.to_dict(),
            "infrastructure_error": None,
            "method_failure": "method_out_of_memory",
            "raw_run": {
                "protocol_id": PROTOCOL_ID,
                "artifact_kind": "development_full_run",
                "not_g1_result": True,
                "holdout_accessed": False,
                "split": "development",
                "commit": task.source_commit,
                "run_id": task.run_id,
                "domain_family": task.family,
                "target_node_count": task.scale,
                "actual_node_count": task.scale,
                "generator_seed": task.seed,
                "outcome_seed": 200000 + task.seed,
                "policy_seed": 300000 + task.seed,
                "method": task.method,
                "config_hash": (
                    ablation_config_sha256()
                    if task.method in ABLATION_METHODS
                    else baseline_config_sha256()
                ),
                "interaction_budget": 4 * task.scale,
                "interactions_used": 0,
                "success_adjusted_efficiency": 0.0,
                "goal_rate": 0.0,
                "wall_time_ms": 0.0,
                "peak_rss_bytes": _peak_rss_bytes(),
                "paths_expanded": 0,
                "status": "method_out_of_memory",
            },
            "evaluation_episodes": [],
        }
    except Exception as error:
        return {
            "shard_version": SHARD_VERSION,
            "task": task.to_dict(),
            "infrastructure_error": {
                "type": type(error).__name__,
                "message": str(error),
            },
        }


def _task_grid(
    source_commit: str,
    *,
    families: Optional[Sequence[str]] = None,
    scales: Optional[Sequence[int]] = None,
    seeds: Optional[Sequence[int]] = None,
    methods: Optional[Sequence[str]] = None,
) -> List[DevelopmentTask]:
    selected_methods = list(methods or ALL_DEVELOPMENT_METHODS)
    unknown = sorted(set(selected_methods) - set(ALL_DEVELOPMENT_METHODS))
    if unknown:
        raise ValueError(f"Unknown development methods: {unknown}")
    domains = list(
        build_development_matrix(
            families=families,
            scales=scales,
            seeds=seeds,
        )
    )
    return [
        DevelopmentTask(
            family=domain.family,
            scale=domain.target_node_count,
            seed=domain.generator_seed,
            method=method,
            source_commit=source_commit,
        )
        for domain in domains
        for method in selected_methods
    ]


def _load_shard(path: Path, task: DevelopmentTask) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if data.get("shard_version") != SHARD_VERSION:
        return None
    if data.get("task") != task.to_dict():
        return None
    if "raw_run" not in data and "infrastructure_error" not in data:
        return None
    return data


def _quantile(values: Sequence[float], probability: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _aggregate_records(records: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for method in ALL_DEVELOPMENT_METHODS:
        method_rows = [row for row in records if row["method"] == method]
        if not method_rows:
            continue
        family_rows: Dict[str, Any] = {}
        for family in sorted({str(row["domain_family"]) for row in method_rows}):
            rows = [row for row in method_rows if row["domain_family"] == family]
            cells = {}
            for scale in sorted({int(row["target_node_count"]) for row in rows}):
                cell = [row for row in rows if int(row["target_node_count"]) == scale]
                cells[str(scale)] = {
                    "replicates": len(cell),
                    "mean_success_adjusted_efficiency": _mean(
                        [float(row["success_adjusted_efficiency"]) for row in cell]
                    ),
                    "mean_goal_rate": _mean([float(row["goal_rate"]) for row in cell]),
                    "median_wall_time_ms": statistics.median(
                        float(row["wall_time_ms"]) for row in cell
                    ),
                    "valid_negative_rate": _mean(
                        [1.0 if row["status"] != "completed" else 0.0 for row in cell]
                    ),
                }
            family_rows[family] = {
                "replicates": len(rows),
                "mean_success_adjusted_efficiency": _mean(
                    [float(row["success_adjusted_efficiency"]) for row in rows]
                ),
                "mean_goal_rate": _mean([float(row["goal_rate"]) for row in rows]),
                "cells": cells,
            }
        result[method] = {
            "replicates": len(method_rows),
            "mean_success_adjusted_efficiency": _mean(
                [float(row["success_adjusted_efficiency"]) for row in method_rows]
            ),
            "mean_goal_rate": _mean([float(row["goal_rate"]) for row in method_rows]),
            "median_wall_time_ms": statistics.median(
                float(row["wall_time_ms"]) for row in method_rows
            ),
            "path_cap_hits": sum(int(row.get("path_cap_hits", 0)) for row in method_rows),
            "valid_negative_count": sum(row["status"] != "completed" for row in method_rows),
            "families": family_rows,
        }
    return result


def select_primary_control(
    records: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Apply the preregistered pooled-mean then median-wall-time rule."""
    candidates = tuple(load_g1_protocol()["gate_G1_A"]["control_selection"]["candidates"])
    rows = []
    for method in candidates:
        method_rows = [row for row in records if row["method"] == method]
        if not method_rows:
            raise ValueError(f"Missing development records for {method}")
        rows.append(
            {
                "method": method,
                "pooled_mean_success_adjusted_efficiency": _mean(
                    [float(row["success_adjusted_efficiency"]) for row in method_rows]
                ),
                "median_wall_time_ms": statistics.median(
                    float(row["wall_time_ms"]) for row in method_rows
                ),
                "replicates": len(method_rows),
            }
        )
    ordered = sorted(
        rows,
        key=lambda item: (
            -item["pooled_mean_success_adjusted_efficiency"],
            item["median_wall_time_ms"],
            item["method"],
        ),
    )
    return {
        "selected": ordered[0]["method"],
        "criterion": "highest pooled mean success_adjusted_efficiency",
        "tie_breaker": "lower median wall_time_ms, then lexical ID",
        "data": "development only",
        "holdout_accessed": False,
        "ranking": ordered,
    }


def _paired_values(
    records: Sequence[Mapping[str, Any]],
    treatment: str,
    control: str,
    *,
    comparator: Optional[Callable[[Tuple[str, int, int]], float]] = None,
) -> Dict[Tuple[str, int, int], Tuple[float, float, float, float]]:
    indexed = {
        (
            str(row["method"]),
            str(row["domain_family"]),
            int(row["target_node_count"]),
            int(row["generator_seed"]),
        ): row
        for row in records
    }
    units = sorted(
        {
            (str(row["domain_family"]), int(row["target_node_count"]), int(row["generator_seed"]))
            for row in records
            if row["method"] == treatment
        }
    )
    result = {}
    for unit in units:
        family, scale, seed = unit
        treatment_row = indexed[(treatment, family, scale, seed)]
        if comparator is None:
            control_row = indexed[(control, family, scale, seed)]
            control_score = float(control_row["success_adjusted_efficiency"])
            control_goal = float(control_row["goal_rate"])
        else:
            control_score, control_goal = comparator(unit)
        result[unit] = (
            float(treatment_row["success_adjusted_efficiency"]),
            control_score,
            float(treatment_row["goal_rate"]),
            control_goal,
        )
    return result


def _stratified_bootstrap(
    pairs: Mapping[Tuple[str, int, int], Tuple[float, float, float, float]],
    *,
    resamples: int,
    seed: int,
) -> Dict[str, Any]:
    strata: Dict[Tuple[str, int], List[Tuple[float, float, float, float]]] = {}
    for (family, scale, _), values in pairs.items():
        strata.setdefault((family, scale), []).append(values)
    rng = random.Random(seed)

    def statistic(
        selected: Mapping[Tuple[str, int], Sequence[Tuple[float, float, float, float]]],
    ) -> Tuple[float, float, float, float]:
        cell_diffs = []
        cell_treatment = []
        cell_control = []
        cell_goal_diffs = []
        for values in selected.values():
            cell_diffs.append(_mean([item[0] - item[1] for item in values]))
            cell_treatment.append(_mean([item[0] for item in values]))
            cell_control.append(_mean([item[1] for item in values]))
            cell_goal_diffs.append(_mean([item[2] - item[3] for item in values]))
        return (
            _mean(cell_diffs),
            _mean(cell_treatment),
            _mean(cell_control),
            _mean(cell_goal_diffs),
        )

    point = statistic(strata)
    samples = []
    for _ in range(resamples):
        sampled = {
            key: [values[rng.randrange(len(values))] for _ in values]
            for key, values in strata.items()
        }
        samples.append(statistic(sampled)[0])
    return {
        "paired_units": len(pairs),
        "strata": len(strata),
        "mean_difference": point[0],
        "treatment_mean": point[1],
        "control_mean": point[2],
        "relative_lift": (point[0] / point[2] if abs(point[2]) > 1e-12 else None),
        "goal_rate_difference": point[3],
        "ci95": [_quantile(samples, 0.025), _quantile(samples, 0.975)],
        "bootstrap_resamples": resamples,
        "bootstrap_seed": seed,
    }


def _comparison_summary(
    records: Sequence[Mapping[str, Any]],
    treatment: str,
    control: str,
    *,
    seed_offset: int,
    comparator: Optional[Callable[[Tuple[str, int, int]], Tuple[float, float]]] = None,
) -> Dict[str, Any]:
    protocol = load_g1_protocol()
    resamples = int(protocol["statistics"]["bootstrap_resamples"])
    seed = int(protocol["statistics"]["bootstrap_seed"]) + seed_offset
    pairs = _paired_values(
        records,
        treatment,
        control,
        comparator=comparator,
    )
    families = sorted({unit[0] for unit in pairs})
    family_results = {}
    for index, family in enumerate(families):
        family_pairs = {unit: values for unit, values in pairs.items() if unit[0] == family}
        family_results[family] = _stratified_bootstrap(
            family_pairs,
            resamples=resamples,
            seed=seed + index + 1,
        )
        n1000 = [values for unit, values in family_pairs.items() if unit[1] == 1000]
        family_results[family]["N1000_mean_difference"] = _mean(
            [item[0] - item[1] for item in n1000]
        )
    return {
        "treatment": treatment,
        "control": control,
        "overall": _stratified_bootstrap(
            pairs,
            resamples=resamples,
            seed=seed,
        ),
        "families": family_results,
    }


def summarize_development_records(
    records: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Derive the complete development summary from raw run records only."""
    control = select_primary_control(records)
    indexed = {
        (
            str(row["method"]),
            str(row["domain_family"]),
            int(row["target_node_count"]),
            int(row["generator_seed"]),
        ): row
        for row in records
    }

    def baseline_median(unit: Tuple[str, int, int]) -> Tuple[float, float]:
        family, scale, seed = unit
        rows = [indexed[(method, family, scale, seed)] for method in COMPETITIVE_METHODS]
        return (
            statistics.median(float(row["success_adjusted_efficiency"]) for row in rows),
            statistics.median(float(row["goal_rate"]) for row in rows),
        )

    return {
        "protocol_id": PROTOCOL_ID,
        "protocol_sha256": protocol_sha256(),
        "artifact_kind": "development_full_summary",
        "not_g1_result": True,
        "holdout_accessed": False,
        "split": "development",
        "record_count": len(records),
        "method_aggregates": _aggregate_records(records),
        "primary_control_selection": control,
        "development_diagnostics_not_gate_results": {
            "G1_A_full_geometry_vs_selected_control": _comparison_summary(
                records,
                "E_FULL_GEOMETRY",
                str(control["selected"]),
                seed_offset=0,
            ),
            "phase_attribution_D_vs_C": _comparison_summary(
                records,
                "D_U1_PHASE",
                "C_THETA_ZERO",
                seed_offset=100,
            ),
            "G1_B_A_HIST_vs_competitive_baseline_median": _comparison_summary(
                records,
                "A_HIST",
                "BASELINE_MEDIAN",
                seed_offset=200,
                comparator=baseline_median,
            ),
        },
        "interpretation": (
            "Development-only diagnostics. They select the frozen simpler control "
            "but do not pass or fail Gate G1; holdout remains unread."
        ),
    }


def render_development_report(summary: Mapping[str, Any]) -> str:
    """Render the human-readable WP-2.4 report strictly from summary data."""
    aggregates = summary["method_aggregates"]
    selection = summary["primary_control_selection"]
    diagnostics = summary["development_diagnostics_not_gate_results"]
    lines = [
        "# E₀ Decision Benchmark — Development Report v1",
        "",
        "**Protocol:** `E0-G1-v1`  ",
        "**Split:** development only  ",
        "**Holdout accessed:** no  ",
        "**Gate result:** none",
        "",
        "## Scope",
        "",
        "This report contains the full WP-2.4 development execution. It freezes",
        "the preregistered simpler G1-A control but does not pass or fail Gate G1.",
        "All positive and negative values below are development diagnostics.",
        "",
        "## Method overview",
        "",
        "| Method | Replicates | Mean efficiency | Goal rate | Median wall-time ms | Valid negatives |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for method in ALL_DEVELOPMENT_METHODS:
        if method not in aggregates:
            continue
        item = aggregates[method]
        lines.append(
            f"| `{method}` | {item['replicates']} | "
            f"{item['mean_success_adjusted_efficiency']:.6f} | "
            f"{item['mean_goal_rate']:.6f} | "
            f"{item['median_wall_time_ms']:.3f} | "
            f"{item['valid_negative_count']} |"
        )
    lines.extend(
        [
            "",
            "## Frozen simpler-control selection",
            "",
            f"Selected: **`{selection['selected']}`**.",
            "",
            "| Candidate | Pooled mean efficiency | Median wall-time ms |",
            "|---|---:|---:|",
        ]
    )
    for item in selection["ranking"]:
        lines.append(
            f"| `{item['method']}` | "
            f"{item['pooled_mean_success_adjusted_efficiency']:.6f} | "
            f"{item['median_wall_time_ms']:.3f} |"
        )
    lines.extend(["", "## Paired development diagnostics", ""])
    for title, key in (
        (
            "Full geometry versus selected control",
            "G1_A_full_geometry_vs_selected_control",
        ),
        ("U(1) phase versus Θ=0", "phase_attribution_D_vs_C"),
        (
            "A_HIST versus competitive baseline median",
            "G1_B_A_HIST_vs_competitive_baseline_median",
        ),
    ):
        item = diagnostics[key]
        overall = item["overall"]
        lines.extend(
            [
                f"### {title}",
                "",
                f"Treatment `{item['treatment']}`; control `{item['control']}`.",
                "",
                "| Scope | Mean difference | 95% paired bootstrap CI | Treatment mean | Control mean | Goal-rate difference |",
                "|---|---:|---:|---:|---:|---:|",
                (
                    f"| Overall | {overall['mean_difference']:.6f} | "
                    f"[{overall['ci95'][0]:.6f}, {overall['ci95'][1]:.6f}] | "
                    f"{overall['treatment_mean']:.6f} | "
                    f"{overall['control_mean']:.6f} | "
                    f"{overall['goal_rate_difference']:.6f} |"
                ),
            ]
        )
        for family, family_item in item["families"].items():
            lines.append(
                f"| `{family}` | {family_item['mean_difference']:.6f} | "
                f"[{family_item['ci95'][0]:.6f}, {family_item['ci95'][1]:.6f}] | "
                f"{family_item['treatment_mean']:.6f} | "
                f"{family_item['control_mean']:.6f} | "
                f"{family_item['goal_rate_difference']:.6f} |"
            )
        lines.append("")
    lines.extend(
        [
            "## Interpretation boundary",
            "",
            "- Development seeds are used for implementation checking and control selection.",
            "- No holdout seed was instantiated or read.",
            "- These diagnostics do not constitute Gate G1 evidence.",
            "- `summary.json` is derived solely from `raw_runs.jsonl`; evaluation",
            "  episodes are retained in `episodes.jsonl.gz`.",
            "",
        ]
    )
    return "\n".join(lines)


def _combined_frozen_configs(selection: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "protocol_id": PROTOCOL_ID,
        "protocol_sha256": protocol_sha256(),
        "artifact_kind": "development_frozen_configs",
        "frozen_before_holdout": True,
        "holdout_execution_started": False,
        "baseline_config_sha256": baseline_config_sha256(),
        "ablation_execution_config_sha256": ablation_config_sha256(),
        "baseline_configs": load_baseline_configs(),
        "ablation_configs": load_ablation_configs(),
        "primary_control_selection": dict(selection),
    }


def _ensure_output_available(output: Path, overwrite: bool, resume: bool) -> None:
    existing = [name for name in ARTIFACT_FILES if (output / name).exists()]
    if existing and not overwrite and not resume:
        raise FileExistsError(f"{output} already contains {existing}; use --resume or --overwrite")


def run_full_development(
    output_dir: Path,
    *,
    families: Optional[Sequence[str]] = None,
    scales: Optional[Sequence[int]] = None,
    seeds: Optional[Sequence[int]] = None,
    methods: Optional[Sequence[str]] = None,
    workers: int = 1,
    resume: bool = True,
    overwrite: bool = False,
    progress: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    """Execute/resume full development units and materialize final artifacts."""
    if workers <= 0:
        raise ValueError("workers must be positive")
    protocol = load_g1_protocol()
    if protocol["holdout_execution_started"] is not False:
        raise ValueError("WP-2.4 requires holdout_execution_started=false")
    load_baseline_configs()
    load_ablation_configs()
    output = Path(output_dir)
    _ensure_output_available(output, overwrite, resume)
    source_commit = _git_value("rev-parse", "HEAD") or "unknown"
    source_dirty = bool(_git_value("status", "--porcelain", "--untracked-files=all"))
    tasks = _task_grid(
        source_commit,
        families=families,
        scales=scales,
        seeds=seeds,
        methods=methods,
    )
    shards_dir = output / "shards"
    shards_dir.mkdir(parents=True, exist_ok=True)
    completed: Dict[str, Dict[str, Any]] = {}
    pending = []
    for task in tasks:
        shard = _load_shard(shards_dir / task.shard_name, task) if resume else None
        if shard is not None and "raw_run" in shard:
            completed[task.run_id] = shard
        else:
            pending.append(task)
    if progress is not None:
        progress(
            {
                "event": "start",
                "planned": len(tasks),
                "resumed": len(completed),
                "pending": len(pending),
            }
        )

    infrastructure_failures: List[Dict[str, Any]] = []
    if pending:
        executor_kwargs: Dict[str, Any] = {"max_workers": workers}
        if sys.version_info >= (3, 11):
            executor_kwargs["max_tasks_per_child"] = 1
        with ProcessPoolExecutor(**executor_kwargs) as executor:
            futures: Dict[Future, DevelopmentTask] = {
                executor.submit(execute_development_task, task.to_dict()): task for task in pending
            }
            for future in as_completed(futures):
                task = futures[future]
                try:
                    shard = future.result()
                except Exception as error:
                    shard = {
                        "shard_version": SHARD_VERSION,
                        "task": task.to_dict(),
                        "infrastructure_error": {
                            "type": type(error).__name__,
                            "message": str(error),
                        },
                    }
                _write_atomic(
                    shards_dir / task.shard_name,
                    _json_bytes(shard),
                )
                if "raw_run" in shard:
                    completed[task.run_id] = shard
                else:
                    infrastructure_failures.append(shard)
                if progress is not None:
                    progress(
                        {
                            "event": "replicate",
                            "completed": len(completed),
                            "planned": len(tasks),
                            "run_id": task.run_id,
                            "status": (
                                shard.get("raw_run", {}).get("status") or "infrastructure_failure"
                            ),
                        }
                    )
    if len(completed) != len(tasks):
        raise RuntimeError(
            f"Development matrix incomplete: {len(completed)}/{len(tasks)}; "
            f"infrastructure_failures={len(infrastructure_failures)}"
        )

    ordered_shards = [completed[task.run_id] for task in tasks]
    raw_records = [shard["raw_run"] for shard in ordered_shards]
    episode_records = [
        episode for shard in ordered_shards for episode in shard["evaluation_episodes"]
    ]
    summary = summarize_development_records(raw_records)
    frozen = _combined_frozen_configs(summary["primary_control_selection"])

    raw_path = output / "raw_runs.jsonl"
    episodes_path = output / "episodes.jsonl.gz"
    summary_path = output / "summary.json"
    configs_path = output / "frozen_configs.json"
    environment_path = output / "environment.json"
    manifest_path = output / "manifest.json"
    _write_atomic(
        raw_path,
        b"".join(_json_bytes(record, indent=None) for record in raw_records),
    )
    _write_gzip_atomic(episodes_path, episode_records)
    _write_atomic(summary_path, _json_bytes(summary))
    _write_atomic(configs_path, _json_bytes(frozen))
    _write_atomic(environment_path, _json_bytes(development_environment()))
    manifest = {
        "protocol_id": PROTOCOL_ID,
        "protocol_sha256": protocol_sha256(),
        "generator_version": GENERATOR_VERSION,
        "artifact_kind": "development_full_manifest",
        "not_g1_result": True,
        "holdout_accessed": False,
        "holdout_execution_started": False,
        "split": "development",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": source_commit,
        "source_dirty": source_dirty,
        "selection": {
            "families": sorted({task.family for task in tasks}),
            "scales": sorted({task.scale for task in tasks}),
            "generator_seeds": sorted({task.seed for task in tasks}),
            "methods": list(dict.fromkeys(task.method for task in tasks)),
            "adaptation_episodes": int(protocol["interaction_protocol"]["adaptation_episodes"]),
            "evaluation_episodes": int(protocol["interaction_protocol"]["evaluation_episodes"]),
        },
        "counts": {
            "planned_replicates": len(tasks),
            "completed_replicates": len(raw_records),
            "evaluation_episode_records": len(episode_records),
            "infrastructure_failures": 0,
            "valid_negative_replicates": sum(
                record["status"] != "completed" for record in raw_records
            ),
        },
        "primary_control_selected": summary["primary_control_selection"]["selected"],
        "files": {
            name: {"sha256": _sha256(output / name)}
            for name in ARTIFACT_FILES
            if name != "manifest.json"
        },
        "scope_note": (
            "Full development data and frozen control selection only. "
            "No holdout access and no Gate G1 result."
        ),
    }
    _write_atomic(manifest_path, _json_bytes(manifest))
    return manifest


def _parse_int_selection(value: str) -> List[int]:
    values: List[int] = []
    for part in value.split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            start_text, stop_text = token.split("-", 1)
            start, stop = int(start_text), int(stop_text)
            if stop < start:
                raise argparse.ArgumentTypeError(f"Invalid range {token!r}")
            values.extend(range(start, stop + 1))
        else:
            values.append(int(token))
    if not values:
        raise argparse.ArgumentTypeError("Selection must not be empty")
    return values


def _parse_text_selection(value: str) -> List[str]:
    values = [item.strip() for item in value.split(",") if item.strip()]
    if not values:
        raise argparse.ArgumentTypeError("Selection must not be empty")
    return values


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run/resume the full E0-G1-v1 development experiment. "
            "Holdout seeds are rejected and output is not a Gate result."
        )
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--families", type=_parse_text_selection, default=None)
    parser.add_argument("--scales", type=_parse_int_selection, default=None)
    parser.add_argument(
        "--seeds",
        type=_parse_int_selection,
        default=list(development_seeds()),
    )
    parser.add_argument("--methods", type=_parse_text_selection, default=None)
    parser.add_argument(
        "--workers",
        type=int,
        default=max(1, min(4, os.cpu_count() or 1)),
    )
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("docs/research/E0_DECISION_BENCHMARK_v1.md"),
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    def emit(event: Dict[str, Any]) -> None:
        print(json.dumps(event, ensure_ascii=False, sort_keys=True), flush=True)

    try:
        manifest = run_full_development(
            args.output,
            families=args.families,
            scales=args.scales,
            seeds=args.seeds,
            methods=args.methods,
            workers=args.workers,
            resume=not args.no_resume,
            overwrite=args.overwrite,
            progress=emit,
        )
        summary = json.loads((args.output / "summary.json").read_text(encoding="utf-8"))
        _write_atomic(
            args.report,
            (render_development_report(summary) + "\n").encode("utf-8"),
        )
    except (FileExistsError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr, flush=True)
        return 2
    emit(
        {
            "event": "complete",
            "status": "PASS",
            "protocol_id": manifest["protocol_id"],
            "not_g1_result": manifest["not_g1_result"],
            "holdout_accessed": manifest["holdout_accessed"],
            "completed_replicates": manifest["counts"]["completed_replicates"],
            "selected_control": manifest["primary_control_selected"],
            "output": str(args.output),
            "report": str(args.report),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
