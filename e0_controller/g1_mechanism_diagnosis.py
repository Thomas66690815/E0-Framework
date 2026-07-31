"""Development-only diagnosis of neutralized G1 lookahead mechanisms.

The WP-2.4 aggregate result can show that methods have equal outcomes, but it
does not retain the per-decision evidence needed to locate where their causal
paths collapse.  This module runs a bounded development probe and separates:

* score/probability differences;
* preferred-action differences;
* selected-action differences;
* conservative override-gate blockers; and
* phase-regime activation.

It cannot construct holdout domains and never reports a Gate G1 result.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .g1_ablations import (
    DecisionRecord,
    build_ablation_adapter,
    load_ablation_configs,
    run_ablation_episode,
)
from .g1_domains import (
    PROTOCOL_ID,
    build_development_matrix,
    development_seeds,
    validate_development_seed,
)

LOOKAHEAD_METHODS = (
    "B_INCOHERENT",
    "C_THETA_ZERO",
    "D_U1_PHASE",
    "E_FULL_GEOMETRY",
)
PAIRWISE_COMPARISONS = (
    ("B_INCOHERENT", "C_THETA_ZERO"),
    ("C_THETA_ZERO", "D_U1_PHASE"),
    ("D_U1_PHASE", "E_FULL_GEOMETRY"),
    ("B_INCOHERENT", "E_FULL_GEOMETRY"),
)
PROBABILITY_TOLERANCE = 1e-12
CONFIDENCE_SWEEP = (0.0, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.85)


def _percentile(values: Sequence[float], quantile: float) -> Optional[float]:
    """Return a deterministic linearly interpolated percentile."""
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


@dataclass
class _GateAccumulator:
    decisions: int = 0
    single_candidate_decisions: int = 0
    greedy_preferred_agreements: int = 0
    greedy_preferred_disagreements: int = 0
    preferred_missing: int = 0
    confidence_passes: int = 0
    imbalance_passes: int = 0
    disagreement_confidence_passes: int = 0
    disagreement_imbalance_passes: int = 0
    disagreement_joint_passes: int = 0
    blocked_by_confidence: int = 0
    blocked_by_imbalance: int = 0
    blocked_by_both: int = 0
    path_cap_hits: int = 0
    overrides: int = 0
    phase_regimes: Dict[str, int] = field(
        default_factory=lambda: {"gradient": 0, "interfering": 0, "wrapped": 0}
    )
    confidences: List[float] = field(default_factory=list)
    disagreement_confidences: List[float] = field(default_factory=list)
    disagreement_gate_points: List[Tuple[float, bool, bool]] = field(
        default_factory=list
    )

    def add(
        self,
        record: DecisionRecord,
        *,
        min_confidence: float,
        max_imbalance: float,
    ) -> None:
        self.decisions += 1
        self.confidences.append(record.confidence)
        if len(record.candidates) < 2:
            self.single_candidate_decisions += 1
        if record.path_cap_hit:
            self.path_cap_hits += 1
        if record.override:
            self.overrides += 1
        if record.phase_regime in self.phase_regimes:
            self.phase_regimes[record.phase_regime] += 1

        confidence_pass = record.confidence >= min_confidence
        imbalance_pass = record.path_imbalance <= max_imbalance
        if confidence_pass:
            self.confidence_passes += 1
        if imbalance_pass:
            self.imbalance_passes += 1

        if record.preferred_action is None or record.greedy_action is None:
            self.preferred_missing += 1
            return
        if record.preferred_action == record.greedy_action:
            self.greedy_preferred_agreements += 1
            return

        self.greedy_preferred_disagreements += 1
        self.disagreement_confidences.append(record.confidence)
        self.disagreement_gate_points.append(
            (record.confidence, imbalance_pass, record.path_cap_hit)
        )
        if confidence_pass:
            self.disagreement_confidence_passes += 1
        if imbalance_pass:
            self.disagreement_imbalance_passes += 1
        if confidence_pass and imbalance_pass and not record.path_cap_hit:
            self.disagreement_joint_passes += 1
        if not confidence_pass:
            self.blocked_by_confidence += 1
        if not imbalance_pass:
            self.blocked_by_imbalance += 1
        if not confidence_pass and not imbalance_pass:
            self.blocked_by_both += 1

    def to_record(self) -> Dict[str, Any]:
        return {
            "decisions": self.decisions,
            "single_candidate_decisions": self.single_candidate_decisions,
            "greedy_preferred_agreements": self.greedy_preferred_agreements,
            "greedy_preferred_disagreements": self.greedy_preferred_disagreements,
            "preferred_missing": self.preferred_missing,
            "confidence_passes": self.confidence_passes,
            "imbalance_passes": self.imbalance_passes,
            "disagreement_confidence_passes": self.disagreement_confidence_passes,
            "disagreement_imbalance_passes": self.disagreement_imbalance_passes,
            "disagreement_joint_passes": self.disagreement_joint_passes,
            "blocked_by_confidence": self.blocked_by_confidence,
            "blocked_by_imbalance": self.blocked_by_imbalance,
            "blocked_by_both": self.blocked_by_both,
            "path_cap_hits": self.path_cap_hits,
            "overrides": self.overrides,
            "confidence_mean": (
                sum(self.confidences) / len(self.confidences)
                if self.confidences
                else None
            ),
            "confidence_p95": _percentile(self.confidences, 0.95),
            "confidence_max": max(self.confidences, default=None),
            "disagreement_confidence_p95": _percentile(
                self.disagreement_confidences,
                0.95,
            ),
            "disagreement_confidence_max": max(
                self.disagreement_confidences,
                default=None,
            ),
            "counterfactual_confidence_sweep": {
                f"{threshold:.2f}": sum(
                    confidence >= threshold and imbalance_pass and not path_cap_hit
                    for confidence, imbalance_pass, path_cap_hit in (
                        self.disagreement_gate_points
                    )
                )
                for threshold in CONFIDENCE_SWEEP
            },
            "phase_regimes": dict(self.phase_regimes),
        }


@dataclass
class _PairAccumulator:
    aligned_steps: int = 0
    missing_steps: int = 0
    context_divergences: int = 0
    comparable_decisions: int = 0
    greedy_action_divergences: int = 0
    path_family_divergences: int = 0
    probability_vector_divergences: int = 0
    score_ranking_divergences: int = 0
    preferred_action_divergences: int = 0
    selected_action_divergences: int = 0
    probability_delta_sum: float = 0.0
    probability_delta_max: float = 0.0

    def compare(
        self,
        left: Mapping[Tuple[int, int], DecisionRecord],
        right: Mapping[Tuple[int, int], DecisionRecord],
    ) -> None:
        keys = set(left) | set(right)
        for key in keys:
            if key not in left or key not in right:
                self.missing_steps += 1
                continue
            self.aligned_steps += 1
            left_record = left[key]
            right_record = right[key]
            if (
                left_record.state != right_record.state
                or left_record.candidates != right_record.candidates
            ):
                self.context_divergences += 1
                continue

            self.comparable_decisions += 1
            if left_record.greedy_action != right_record.greedy_action:
                self.greedy_action_divergences += 1
            if (
                left_record.path_family_signature
                != right_record.path_family_signature
            ):
                self.path_family_divergences += 1
            if left_record.preferred_action != right_record.preferred_action:
                self.preferred_action_divergences += 1
            if left_record.selected_action != right_record.selected_action:
                self.selected_action_divergences += 1

            candidates = set(left_record.candidates) | set(right_record.candidates)
            delta = max(
                (
                    abs(
                        left_record.probabilities.get(action, 0.0)
                        - right_record.probabilities.get(action, 0.0)
                    )
                    for action in candidates
                ),
                default=0.0,
            )
            self.probability_delta_sum += delta
            self.probability_delta_max = max(self.probability_delta_max, delta)
            if delta > PROBABILITY_TOLERANCE:
                self.probability_vector_divergences += 1
            if _score_ranking(left_record) != _score_ranking(right_record):
                self.score_ranking_divergences += 1

    def to_record(self) -> Dict[str, Any]:
        return {
            "aligned_steps": self.aligned_steps,
            "missing_steps": self.missing_steps,
            "context_divergences": self.context_divergences,
            "comparable_decisions": self.comparable_decisions,
            "greedy_action_divergences": self.greedy_action_divergences,
            "path_family_divergences": self.path_family_divergences,
            "probability_vector_divergences": self.probability_vector_divergences,
            "score_ranking_divergences": self.score_ranking_divergences,
            "preferred_action_divergences": self.preferred_action_divergences,
            "selected_action_divergences": self.selected_action_divergences,
            "mean_max_probability_delta": (
                self.probability_delta_sum / self.comparable_decisions
                if self.comparable_decisions
                else None
            ),
            "max_probability_delta": self.probability_delta_max,
        }


def _score_ranking(record: DecisionRecord) -> Tuple[str, ...]:
    return tuple(
        sorted(
            record.candidates,
            key=lambda action: (-record.probabilities.get(action, 0.0), action),
        )
    )


def summarize_episode_evidence(records: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    """Aggregate persisted WP-2.4 evaluation-episode mechanism counters."""
    by_method: Dict[str, Dict[str, Any]] = {}
    source_commits = set()
    holdout_violations = 0
    gate_flag_violations = 0
    for record in records:
        method = str(record["method"])
        if method not in LOOKAHEAD_METHODS:
            continue
        if record.get("commit"):
            source_commits.add(str(record["commit"]))
        if record.get("holdout_accessed", False) is not False:
            holdout_violations += 1
        if (
            "not_g1_result" in record
            and record.get("not_g1_result") is not True
        ):
            gate_flag_violations += 1
        summary = by_method.setdefault(
            method,
            {
                "episodes": 0,
                "decisions": 0,
                "overrides": 0,
                "override_successes": 0,
                "path_cap_hits": 0,
                "phase_regimes": {
                    "gradient": 0,
                    "interfering": 0,
                    "wrapped": 0,
                },
            },
        )
        summary["episodes"] += 1
        summary["decisions"] += int(record.get("decision_count", 0))
        summary["overrides"] += int(record.get("override_count", 0))
        summary["override_successes"] += int(
            record.get("override_success_count", 0)
        )
        summary["path_cap_hits"] += int(record.get("path_cap_hits", 0))
        summary["phase_regimes"]["gradient"] += int(
            record.get("phase_regime_gradient_count", 0)
        )
        summary["phase_regimes"]["interfering"] += int(
            record.get("phase_regime_interfering_count", 0)
        )
        summary["phase_regimes"]["wrapped"] += int(
            record.get("phase_regime_wrapped_count", 0)
        )
    return {
        "methods": {method: by_method[method] for method in sorted(by_method)},
        "total_lookahead_decisions": sum(
            item["decisions"] for item in by_method.values()
        ),
        "total_overrides": sum(item["overrides"] for item in by_method.values()),
        "total_path_cap_hits": sum(
            item["path_cap_hits"] for item in by_method.values()
        ),
        "source_commits": sorted(source_commits),
        "holdout_violations": holdout_violations,
        "gate_flag_violations": gate_flag_violations,
    }


def load_episode_evidence(path: Path) -> Dict[str, Any]:
    """Read a compressed WP-2.4 episode JSONL artifact."""
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        records = (json.loads(line) for line in handle if line.strip())
        result = summarize_episode_evidence(records)
    result["source_file"] = {
        "name": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    return result


def diagnose_development_mechanism(
    *,
    families: Optional[Sequence[str]] = None,
    scales: Optional[Sequence[int]] = None,
    seeds: Optional[Sequence[int]] = None,
    episode_count: int = 1,
    interaction_budget: int = 20,
) -> Dict[str, Any]:
    """Probe B-E decisions across a bounded development-only matrix."""
    selected_seeds = list(seeds if seeds is not None else development_seeds())
    for seed in selected_seeds:
        validate_development_seed(int(seed))
    if episode_count <= 0:
        raise ValueError("episode_count must be positive")
    if interaction_budget <= 0:
        raise ValueError("interaction_budget must be positive")

    shared = load_ablation_configs()["shared"]
    min_confidence = float(shared["min_confidence"])
    max_imbalance = float(shared["max_imbalance"])
    domains = list(
        build_development_matrix(
            families=families,
            scales=scales,
            seeds=selected_seeds,
        )
    )
    gates = {method: _GateAccumulator() for method in LOOKAHEAD_METHODS}
    pairs = {
        f"{left}_vs_{right}": _PairAccumulator()
        for left, right in PAIRWISE_COMPARISONS
    }

    for domain in domains:
        traces: Dict[str, Dict[Tuple[int, int], DecisionRecord]] = {}
        for method in LOOKAHEAD_METHODS:
            adapter = build_ablation_adapter(method, domain)
            trace: Dict[Tuple[int, int], DecisionRecord] = {}
            for episode_index in range(episode_count):
                start = len(adapter.decision_records)
                run_ablation_episode(
                    domain,
                    adapter,
                    episode_index,
                    interaction_budget=interaction_budget,
                )
                records = adapter.decision_records[start:]
                for step_index, record in enumerate(records):
                    trace[(episode_index, step_index)] = record
                    gates[method].add(
                        record,
                        min_confidence=min_confidence,
                        max_imbalance=max_imbalance,
                    )
            traces[method] = trace

        for left, right in PAIRWISE_COMPARISONS:
            pairs[f"{left}_vs_{right}"].compare(traces[left], traces[right])

    return {
        "protocol_id": PROTOCOL_ID,
        "artifact_kind": "development_g1_mechanism_diagnosis",
        "split": "development",
        "not_g1_result": True,
        "holdout_accessed": False,
        "probe": {
            "domain_count": len(domains),
            "methods": list(LOOKAHEAD_METHODS),
            "episode_count_per_method_domain": episode_count,
            "interaction_budget_per_episode": interaction_budget,
            "gate": {
                "min_confidence": min_confidence,
                "max_imbalance": max_imbalance,
            },
        },
        "per_method": {
            method: gates[method].to_record() for method in LOOKAHEAD_METHODS
        },
        "pairwise": {name: accumulator.to_record() for name, accumulator in pairs.items()},
    }


def _parse_int_list(value: str) -> List[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def _parse_str_list(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--families", type=_parse_str_list)
    parser.add_argument("--scales", type=_parse_int_list)
    parser.add_argument("--seeds", type=_parse_int_list)
    parser.add_argument("--episode-count", type=int, default=1)
    parser.add_argument("--interaction-budget", type=int, default=20)
    parser.add_argument(
        "--episodes-evidence",
        type=Path,
        help="Optional episodes.jsonl.gz from a completed WP-2.4 bundle.",
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    result = diagnose_development_mechanism(
        families=args.families,
        scales=args.scales,
        seeds=args.seeds,
        episode_count=args.episode_count,
        interaction_budget=args.interaction_budget,
    )
    if args.episodes_evidence is not None:
        result["full_episode_evidence"] = load_episode_evidence(
            args.episodes_evidence
        )
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(text, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
