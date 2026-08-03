"""Stage-separated development prototype for override-gate v2.

WP-GATE-0.10 is not an experiment instance and cannot emit a gate result.
Stage A samples bounded paired-branch evidence.  Stage B runs closed-loop
parents without branches.  Every case executes in its own killable process.
"""

from __future__ import annotations

import argparse
import hashlib
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

PROTOTYPE_SCHEMA_VERSION = 1
PROTOTYPE_FAMILY = "wall_grid"
PROTOTYPE_SCALES = (100, 500, 1000)
STAGE_A = "stage_a_paired_evidence"
STAGE_B = "stage_b_closed_loop_parent"
MAX_INTERACTION_BUDGET = 40
MAX_STAGE_A_BRANCHES = 4
MAX_CASE_TIMEOUT_SECONDS = 120.0
DEFAULT_INTERACTION_BUDGET = 40
DEFAULT_STAGE_A_BRANCHES = 1
DEFAULT_CASE_TIMEOUT_SECONDS = 30.0
DEFAULT_CASES = (
    (STAGE_A, 100, 0, "gate_disabled"),
    (STAGE_B, 100, 0, "gate_disabled"),
    (STAGE_B, 100, 0, "margin_000"),
    (STAGE_B, 100, 0, "margin_040"),
    (STAGE_A, 500, 0, "gate_disabled"),
    (STAGE_B, 500, 0, "gate_disabled"),
    (STAGE_A, 1000, 0, "gate_disabled"),
    (STAGE_B, 1000, 0, "gate_disabled"),
)


@dataclass(frozen=True)
class V2DevelopmentCase:
    """One bounded case in exactly one prototype stage."""

    stage: str
    scale: int
    seed: int
    policy_id: str
    episode_index: int = 0
    interaction_budget: int = DEFAULT_INTERACTION_BUDGET
    max_paired_branches: Optional[int] = None

    def __post_init__(self) -> None:
        if self.stage not in {STAGE_A, STAGE_B}:
            raise ValueError("Unknown v2 development stage")
        if self.scale not in PROTOTYPE_SCALES:
            raise ValueError(f"Prototype scale must be one of {PROTOTYPE_SCALES}")
        validate_development_seed(self.seed)
        candidate_policy(self.policy_id)
        if not 0 <= self.episode_index < 30:
            raise ValueError("Prototype episode_index must be in 0..29")
        if not 0 < self.interaction_budget <= MAX_INTERACTION_BUDGET:
            raise ValueError(
                "Prototype interaction budget must be in "
                f"1..{MAX_INTERACTION_BUDGET}"
            )
        if self.stage == STAGE_A:
            if self.policy_id != "gate_disabled":
                raise ValueError("Stage A must use the gate_disabled control")
            if (
                isinstance(self.max_paired_branches, bool)
                or not isinstance(self.max_paired_branches, int)
                or not 0 < self.max_paired_branches <= MAX_STAGE_A_BRANCHES
            ):
                raise ValueError(
                    "Stage A max_paired_branches must be in "
                    f"1..{MAX_STAGE_A_BRANCHES}"
                )
        elif self.max_paired_branches is not None:
            raise ValueError("Stage B cannot collect paired branches")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "family": PROTOTYPE_FAMILY,
            "stage": self.stage,
            "scale": self.scale,
            "seed": self.seed,
            "policy_id": self.policy_id,
            "episode_index": self.episode_index,
            "interaction_budget": self.interaction_budget,
            "max_paired_branches": self.max_paired_branches,
        }

    @classmethod
    def from_dict(cls, record: Mapping[str, Any]) -> "V2DevelopmentCase":
        if record.get("family") != PROTOTYPE_FAMILY:
            raise ValueError("Override-gate v2 prototype is wall_grid-only")
        cap = record.get("max_paired_branches")
        return cls(
            stage=str(record["stage"]),
            scale=int(record["scale"]),
            seed=int(record["seed"]),
            policy_id=str(record["policy_id"]),
            episode_index=int(record["episode_index"]),
            interaction_budget=int(record["interaction_budget"]),
            max_paired_branches=None if cap is None else cap,
        )


def _base_record(case: V2DevelopmentCase) -> Dict[str, Any]:
    policy = candidate_policy(case.policy_id)
    return {
        "prototype_schema_version": PROTOTYPE_SCHEMA_VERSION,
        "artifact_kind": (
            "override_gate_v2_stage_a_case"
            if case.stage == STAGE_A
            else "override_gate_v2_stage_b_case"
        ),
        "stage": case.stage,
        "split": "development",
        "family": PROTOTYPE_FAMILY,
        "scale": case.scale,
        "generator_seed": case.seed,
        "episode_index": case.episode_index,
        "interaction_budget": case.interaction_budget,
        "policy_id": case.policy_id,
        "min_support_margin": policy.min_support_margin,
        "max_paired_branches": case.max_paired_branches,
        "calibration_executed": False,
        "verification_executed": False,
        "protected_holdout_accessed": False,
        "holdout_accessed": False,
        "not_gate_result": True,
    }


def _decision_trace_record(record: Any) -> Dict[str, Any]:
    return {
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


def decision_trace_sha256(decision_records: Sequence[Any]) -> str:
    """Hash only parent decisions, excluding instrumentation and wall time."""
    payload = [_decision_trace_record(record) for record in decision_records]
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _is_guard_eligible(record: Any, max_path_imbalance: Optional[float]) -> bool:
    return bool(
        not record.path_cap_hit
        and record.preferred_action is not None
        and record.greedy_action is not None
        and record.preferred_action != record.greedy_action
        and max_path_imbalance is not None
        and record.path_imbalance <= float(max_path_imbalance)
    )


def summarize_v2_episode(
    case: V2DevelopmentCase,
    episode: InstrumentedEpisodeResult,
    *,
    wall_time_ms: float,
) -> Dict[str, Any]:
    """Summarize one stage without reusing instrumentation time as parent time."""
    policy = candidate_policy(case.policy_id)
    decisions = episode.decision_records
    paired = episode.paired_decisions
    observed = sum(
        record.preferred_action is not None
        and record.greedy_action is not None
        and record.preferred_action != record.greedy_action
        for record in decisions
    )
    eligible = sum(
        _is_guard_eligible(record, policy.max_path_imbalance)
        for record in decisions
    )
    overrides = sum(record.override for record in decisions)
    if not overrides <= eligible <= observed:
        raise RuntimeError(
            "Prototype counts must satisfy override <= eligible <= observed"
        )
    if case.stage == STAGE_A and len(paired) > int(case.max_paired_branches or 0):
        raise RuntimeError("Stage A exceeded its paired-branch sample cap")
    if case.stage == STAGE_B and paired:
        raise RuntimeError("Stage B collected forbidden paired branches")

    record = {
        **_base_record(case),
        "worker_status": "completed",
        "parent": episode.summary.to_record(),
        "parent_decision_trace_sha256": decision_trace_sha256(decisions),
        "parent_decision_count": len(decisions),
        "observed_disagreement_count": observed,
        "guard_eligible_disagreement_count": eligible,
        "executed_override_count": overrides,
        "sampled_paired_branch_count": len(paired),
        "paired_branches": [branch.to_record() for branch in paired],
    }
    if case.stage == STAGE_A:
        record["instrumentation_wall_time_ms"] = round(float(wall_time_ms), 6)
        record["parent_wall_time_ms"] = None
        record["timing_interpretation"] = "instrumentation_only"
    else:
        record["instrumentation_wall_time_ms"] = None
        record["parent_wall_time_ms"] = round(float(wall_time_ms), 6)
        record["timing_interpretation"] = "closed_loop_parent_only"
    return record


def execute_v2_case(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Execute one validated stage case inside a child process."""
    case = V2DevelopmentCase.from_dict(payload)
    domain = build_domain(PROTOTYPE_FAMILY, case.scale, case.seed)
    started = time.perf_counter()
    episode = run_instrumented_episode(
        domain,
        candidate_policy(case.policy_id),
        case.episode_index,
        interaction_budget=case.interaction_budget,
        collect_paired_branches=case.stage == STAGE_A,
        max_paired_branches=case.max_paired_branches,
    )
    return summarize_v2_episode(
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


def execute_v2_case_bounded(
    case: V2DevelopmentCase,
    *,
    timeout_seconds: float = DEFAULT_CASE_TIMEOUT_SECONDS,
    worker: Callable[[Mapping[str, Any]], Dict[str, Any]] = execute_v2_case,
) -> Dict[str, Any]:
    """Run exactly one stage case behind a hard process timeout."""
    timeout = float(timeout_seconds)
    if not 0.0 < timeout <= MAX_CASE_TIMEOUT_SECONDS:
        raise ValueError(
            "Prototype timeout must be in "
            f"(0, {MAX_CASE_TIMEOUT_SECONDS}] seconds"
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
                    "worker_status": "prototype_error",
                    "case_wall_time_ms": round(
                        (time.perf_counter() - started) * 1000.0,
                        6,
                    ),
                    "error_type": message["error_type"],
                    "error_message": message["error_message"],
                }
            return dict(message["record"])
        process.terminate()
        process.join(timeout=5.0)
        return {
            **_base_record(case),
            "worker_status": "prototype_timeout",
            "case_wall_time_ms": round(
                (time.perf_counter() - started) * 1000.0,
                6,
            ),
        }
    finally:
        receiver.close()
        if process.is_alive():
            process.kill()
            process.join(timeout=2.0)


def default_v2_cases(
    *,
    interaction_budget: int = DEFAULT_INTERACTION_BUDGET,
    stage_a_branches: int = DEFAULT_STAGE_A_BRANCHES,
) -> List[V2DevelopmentCase]:
    return [
        V2DevelopmentCase(
            stage=stage,
            scale=scale,
            seed=seed,
            policy_id=policy_id,
            interaction_budget=interaction_budget,
            max_paired_branches=(stage_a_branches if stage == STAGE_A else None),
        )
        for stage, scale, seed, policy_id in DEFAULT_CASES
    ]


def compare_control_replays(records: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Compare Stage-A parents with independent Stage-B disabled controls."""
    comparisons: List[Dict[str, Any]] = []
    for scale in PROTOTYPE_SCALES:
        stage_a = next(
            (
                record
                for record in records
                if record.get("stage") == STAGE_A
                and record.get("scale") == scale
                and record.get("policy_id") == "gate_disabled"
            ),
            None,
        )
        stage_b = next(
            (
                record
                for record in records
                if record.get("stage") == STAGE_B
                and record.get("scale") == scale
                and record.get("policy_id") == "gate_disabled"
            ),
            None,
        )
        comparable = bool(
            stage_a
            and stage_b
            and stage_a.get("worker_status") == "completed"
            and stage_b.get("worker_status") == "completed"
        )
        summary_equal = bool(comparable and stage_a["parent"] == stage_b["parent"])
        trace_equal = bool(
            comparable
            and stage_a["parent_decision_trace_sha256"]
            == stage_b["parent_decision_trace_sha256"]
        )
        comparisons.append(
            {
                "scale": scale,
                "comparable": comparable,
                "parent_summary_equal": summary_equal,
                "parent_decision_trace_equal": trace_equal,
                "parent_invariance_pass": bool(
                    comparable and summary_equal and trace_equal
                ),
            }
        )
    return comparisons


def run_v2_development_pilot(
    cases: Sequence[V2DevelopmentCase],
    *,
    stage_a_timeout_seconds: float = DEFAULT_CASE_TIMEOUT_SECONDS,
    stage_b_timeout_seconds: float = DEFAULT_CASE_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Run the stable stage list sequentially and compare control replays."""
    if not cases:
        raise ValueError("V2 development pilot requires at least one case")
    records = [
        execute_v2_case_bounded(
            case,
            timeout_seconds=(
                stage_a_timeout_seconds
                if case.stage == STAGE_A
                else stage_b_timeout_seconds
            ),
        )
        for case in cases
    ]
    comparisons = compare_control_replays(records)
    return {
        "prototype_schema_version": PROTOTYPE_SCHEMA_VERSION,
        "artifact_kind": "override_gate_v2_stage_separation_development_pilot",
        "split": "development",
        "case_count": len(records),
        "stage_a_case_count": sum(record["stage"] == STAGE_A for record in records),
        "stage_b_case_count": sum(record["stage"] == STAGE_B for record in records),
        "completed_case_count": sum(
            record["worker_status"] == "completed" for record in records
        ),
        "prototype_timeout_count": sum(
            record["worker_status"] == "prototype_timeout" for record in records
        ),
        "prototype_error_count": sum(
            record["worker_status"] == "prototype_error" for record in records
        ),
        "control_replay_comparisons": comparisons,
        "all_parent_invariance_checks_pass": all(
            comparison["parent_invariance_pass"] for comparison in comparisons
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
        "--stage-a-branches",
        type=int,
        default=DEFAULT_STAGE_A_BRANCHES,
    )
    parser.add_argument(
        "--stage-a-timeout-seconds",
        type=float,
        default=DEFAULT_CASE_TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--stage-b-timeout-seconds",
        type=float,
        default=DEFAULT_CASE_TIMEOUT_SECONDS,
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    result = run_v2_development_pilot(
        default_v2_cases(
            interaction_budget=args.interaction_budget,
            stage_a_branches=args.stage_a_branches,
        ),
        stage_a_timeout_seconds=args.stage_a_timeout_seconds,
        stage_b_timeout_seconds=args.stage_b_timeout_seconds,
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
