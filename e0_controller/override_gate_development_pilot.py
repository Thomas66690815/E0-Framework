"""Bounded development-only pilot for override-gate activation and cost.

WP-GATE-0.9 deliberately accepts only G1 development seeds.  It reuses the
frozen calibration candidates as diagnostic policies, but it cannot construct
calibration, verification, or protected-holdout domains and emits no gate
result.  Every case runs in a killable child process behind small hard limits.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

from .g1_domains import build_domain, validate_development_seed
from .override_gate_calibration_engine import (
    InstrumentedEpisodeResult,
    candidate_policy,
    run_instrumented_episode,
)

PILOT_SCHEMA_VERSION = 1
PILOT_FAMILY = "wall_grid"
PILOT_SCALES = (100, 500, 1000)
MAX_INTERACTION_BUDGET = 40
MAX_CASE_TIMEOUT_SECONDS = 120.0
DEFAULT_INTERACTION_BUDGET = 8
DEFAULT_CASE_TIMEOUT_SECONDS = 30.0
DEFAULT_CASES = (
    (100, 0, "gate_disabled", True),
    (100, 0, "margin_000", True),
    (100, 0, "margin_040", True),
    (100, 0, "gate_disabled", False),
    (500, 0, "gate_disabled", True),
    (500, 0, "gate_disabled", False),
    (1000, 0, "gate_disabled", True),
    (1000, 0, "gate_disabled", False),
)


@dataclass(frozen=True)
class DevelopmentPilotCase:
    """One small development-only diagnostic case."""

    scale: int
    seed: int
    policy_id: str
    episode_index: int = 0
    interaction_budget: int = DEFAULT_INTERACTION_BUDGET
    collect_paired_branches: bool = True

    def __post_init__(self) -> None:
        if self.scale not in PILOT_SCALES:
            raise ValueError(f"Pilot scale must be one of {PILOT_SCALES}")
        validate_development_seed(self.seed)
        candidate_policy(self.policy_id)
        if not 0 <= self.episode_index < 30:
            raise ValueError("Pilot episode_index must be in 0..29")
        if not 0 < self.interaction_budget <= MAX_INTERACTION_BUDGET:
            raise ValueError(
                f"Pilot interaction budget must be in 1..{MAX_INTERACTION_BUDGET}"
            )
        if not isinstance(self.collect_paired_branches, bool):
            raise TypeError("collect_paired_branches must be boolean")
        if not self.collect_paired_branches and self.policy_id != "gate_disabled":
            raise ValueError("Parent-only pilot cases must use gate_disabled")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "family": PILOT_FAMILY,
            "scale": self.scale,
            "seed": self.seed,
            "policy_id": self.policy_id,
            "episode_index": self.episode_index,
            "interaction_budget": self.interaction_budget,
            "collect_paired_branches": self.collect_paired_branches,
        }

    @classmethod
    def from_dict(cls, record: Mapping[str, Any]) -> "DevelopmentPilotCase":
        if record.get("family") != PILOT_FAMILY:
            raise ValueError("Override-gate pilot is wall_grid-only")
        collect_paired_branches = record["collect_paired_branches"]
        if not isinstance(collect_paired_branches, bool):
            raise TypeError("collect_paired_branches must be boolean")
        return cls(
            scale=int(record["scale"]),
            seed=int(record["seed"]),
            policy_id=str(record["policy_id"]),
            episode_index=int(record["episode_index"]),
            interaction_budget=int(record["interaction_budget"]),
            collect_paired_branches=collect_paired_branches,
        )


def _base_record(case: DevelopmentPilotCase) -> Dict[str, Any]:
    policy = candidate_policy(case.policy_id)
    return {
        "pilot_schema_version": PILOT_SCHEMA_VERSION,
        "artifact_kind": "override_gate_development_pilot_case",
        "split": "development",
        "family": PILOT_FAMILY,
        "scale": case.scale,
        "generator_seed": case.seed,
        "episode_index": case.episode_index,
        "interaction_budget": case.interaction_budget,
        "paired_branch_collection": case.collect_paired_branches,
        "policy_id": case.policy_id,
        "min_support_margin": policy.min_support_margin,
        "calibration_executed": False,
        "verification_executed": False,
        "protected_holdout_accessed": False,
        "holdout_accessed": False,
        "not_gate_result": True,
    }


def summarize_pilot_episode(
    case: DevelopmentPilotCase,
    episode: InstrumentedEpisodeResult,
    *,
    wall_time_ms: float,
) -> Dict[str, Any]:
    """Expose the complete disagreement funnel and diagnostic branch cost."""
    decisions = episode.decision_records
    paired = episode.paired_decisions
    observed = sum(
        record.preferred_action is not None
        and record.greedy_action is not None
        and record.preferred_action != record.greedy_action
        for record in decisions
    )
    eligible = len(paired)
    overrides = sum(record.override for record in decisions)
    branch_interactions = sum(
        max(0, branch.greedy.interactions_used - branch.interaction_index)
        + max(0, branch.lookahead.interactions_used - branch.interaction_index)
        for branch in paired
    )
    geometry_decisions = len(decisions) + branch_interactions
    if not overrides <= eligible <= observed:
        raise RuntimeError(
            "Pilot counts must satisfy override <= eligible <= observed"
        )
    record = {
        **_base_record(case),
        "worker_status": "completed",
        "wall_time_ms": round(float(wall_time_ms), 6),
        "parent": episode.summary.to_record(),
        "observed_disagreement_count": observed,
        "eligible_disagreement_count": eligible,
        "override_count": overrides,
        "paired_branch_count": eligible,
        "paired_branch_rollout_count": 2 * eligible,
        "paired_branch_interactions": branch_interactions,
        "geometry_decision_count_lower_bound": geometry_decisions,
        "geometry_decision_amplification": (
            geometry_decisions / len(decisions) if decisions else 0.0
        ),
        "eligible_support_margin_min": (
            min(branch.support_margin for branch in paired) if paired else None
        ),
        "eligible_support_margin_max": (
            max(branch.support_margin for branch in paired) if paired else None
        ),
        "beneficial_branch_count": sum(
            branch.delta_utility > 0.01 for branch in paired
        ),
        "harmful_branch_count": sum(
            branch.delta_utility < -0.01 for branch in paired
        ),
        "neutral_branch_count": sum(
            -0.01 <= branch.delta_utility <= 0.01 for branch in paired
        ),
        "paired_branches": [branch.to_record() for branch in paired],
    }
    return record


def execute_pilot_case(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Execute one validated development case inside the child process."""
    case = DevelopmentPilotCase.from_dict(payload)
    domain = build_domain(PILOT_FAMILY, case.scale, case.seed)
    policy = candidate_policy(case.policy_id)
    started = time.perf_counter()
    episode = run_instrumented_episode(
        domain,
        policy,
        case.episode_index,
        interaction_budget=case.interaction_budget,
        collect_paired_branches=case.collect_paired_branches,
    )
    return summarize_pilot_episode(
        case,
        episode,
        wall_time_ms=(time.perf_counter() - started) * 1000.0,
    )


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


def execute_pilot_case_bounded(
    case: DevelopmentPilotCase,
    *,
    timeout_seconds: float = DEFAULT_CASE_TIMEOUT_SECONDS,
    worker: Callable[[Mapping[str, Any]], Dict[str, Any]] = execute_pilot_case,
) -> Dict[str, Any]:
    """Run one development case behind a portable hard process timeout."""
    timeout = float(timeout_seconds)
    if not 0.0 < timeout <= MAX_CASE_TIMEOUT_SECONDS:
        raise ValueError(
            f"Pilot timeout must be in (0, {MAX_CASE_TIMEOUT_SECONDS}] seconds"
        )
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_child_entry, args=(worker, case.to_dict(), sender))
    started = time.perf_counter()
    process.start()
    sender.close()
    try:
        if receiver.poll(timeout):
            message = receiver.recv()
            process.join(timeout=2.0)
            if message["kind"] == "error":
                return {
                    **_base_record(case),
                    "worker_status": "pilot_error",
                    "wall_time_ms": round((time.perf_counter() - started) * 1000.0, 6),
                    "error_type": message["error_type"],
                    "error_message": message["error_message"],
                }
            return dict(message["record"])
        process.terminate()
        process.join(timeout=5.0)
        return {
            **_base_record(case),
            "worker_status": "pilot_timeout",
            "wall_time_ms": round((time.perf_counter() - started) * 1000.0, 6),
        }
    finally:
        receiver.close()
        if process.is_alive():
            process.kill()
            process.join(timeout=2.0)


def default_pilot_cases(
    *, interaction_budget: int = DEFAULT_INTERACTION_BUDGET
) -> List[DevelopmentPilotCase]:
    return [
        DevelopmentPilotCase(
            scale=scale,
            seed=seed,
            policy_id=policy_id,
            interaction_budget=interaction_budget,
            collect_paired_branches=collect_paired_branches,
        )
        for scale, seed, policy_id, collect_paired_branches in DEFAULT_CASES
    ]


def run_development_pilot(
    cases: Sequence[DevelopmentPilotCase],
    *,
    timeout_seconds: float = DEFAULT_CASE_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Run a small stable case list sequentially and summarize its cost."""
    if not cases:
        raise ValueError("Pilot requires at least one case")
    records = [
        execute_pilot_case_bounded(case, timeout_seconds=timeout_seconds)
        for case in cases
    ]
    return {
        "pilot_schema_version": PILOT_SCHEMA_VERSION,
        "artifact_kind": "override_gate_development_pilot",
        "split": "development",
        "case_count": len(records),
        "completed_case_count": sum(
            record["worker_status"] == "completed" for record in records
        ),
        "pilot_timeout_count": sum(
            record["worker_status"] == "pilot_timeout" for record in records
        ),
        "pilot_error_count": sum(
            record["worker_status"] == "pilot_error" for record in records
        ),
        "calibration_executed": False,
        "verification_executed": False,
        "protected_holdout_accessed": False,
        "holdout_accessed": False,
        "not_gate_result": True,
        "cases": records,
    }


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--interaction-budget",
        type=int,
        default=DEFAULT_INTERACTION_BUDGET,
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_CASE_TIMEOUT_SECONDS,
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    result = run_development_pilot(
        default_pilot_cases(interaction_budget=args.interaction_budget),
        timeout_seconds=args.timeout_seconds,
    )
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(text, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
