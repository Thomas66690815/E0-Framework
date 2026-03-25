"""
E₀ Evaluation Layer (Phase 3f)
================================
Run-quality and semantic-quality assessment for E₀ runs.

Four evaluation layers:
  1. Graph Quality   — structural assessment (delegates to graph_validation)
  2. Run Dynamics    — goal, efficiency, loops, progress
  3. Semantic Output — required output coverage, grounding heuristics
  4. Cross-Run       — stability comparisons (future extension)

See E0_EVALUATION_LAYER_v0.2.md for architecture.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .graph_validation import GraphQuality
from .llm_adapter import TransitionResult
from .scenario_loader import ScenarioPacket


# ──────────────────────────────────────────────
# 1. Run Dynamics Evaluation
# ──────────────────────────────────────────────

@dataclass
class RunEvaluation:
    """Evaluates a complete controller run."""
    goal_reached: bool
    steps: int
    escalations: int
    revisits: int
    repeated_cycles: int
    progress_ratio: float       # unique_states / steps
    avg_tension: float
    total_tension: float
    goal_reach_efficiency: float  # happy_path_length / steps (0 if not reached)
    loop_penalty: float         # repeated_cycles / steps
    step_success_rate: float    # SUCCESS outcomes / steps
    rating: str                 # A–F
    warnings: List[str] = field(default_factory=list)
    # Hybrid / overlay metrics (Phase 3o)
    hybrid_override_count: int = 0
    hybrid_override_rate: float = 0.0
    overlay_agree_rate: float = 1.0   # agree / count (1.0 if no overlay)
    overlay_count: int = 0
    # Amplitude hybrid metrics (Phase 3h)
    r_coh_avg: float = 0.0           # mean coherence ratio across steps
    r_coh_min: float = 0.0           # worst-case coherence (most cancellation)
    r_coh_max: float = 1.0           # best-case coherence
    theta_consistency: float = 1.0   # phase alignment [0–1]
    amplitude_drift: float = 0.0     # 1.0 − overlay_agree_rate


@dataclass
class SemanticEvaluation:
    """Evaluates semantic quality of run outputs against a scenario."""
    required_outputs_covered: float   # 0.0–1.0
    missing_outputs: List[str] = field(default_factory=list)
    uncertainty_marks: int = 0
    grounding_warnings: int = 0
    completeness_score: float = 0.0   # 0.0–1.0
    notes: List[str] = field(default_factory=list)


@dataclass
class ScenarioEvaluation:
    """Combines graph, run, and semantic evaluation for one scenario."""
    scenario_id: str
    domain: str
    graph_score: float
    run_evaluation: RunEvaluation
    semantic_evaluation: Optional[SemanticEvaluation]
    hard_failure: Optional[str]     # None if no hard failure
    overall_score: Optional[float]  # None until all layers computed


# ──────────────────────────────────────────────
# 2. Run Dynamics Evaluator
# ──────────────────────────────────────────────

def _count_repeated_cycles(path: List[str]) -> int:
    """Count repeated 2-cycle oscillations in a path.

    A 2-cycle is A→B→A.  Each occurrence beyond the first counts.
    """
    if len(path) < 3:
        return 0

    cycles: Dict[Tuple[str, str], int] = {}
    for i in range(len(path) - 2):
        a, b, c = path[i], path[i + 1], path[i + 2]
        if a == c and a != b and a <= b:
            key = (a, b)
            cycles[key] = cycles.get(key, 0) + 1

    # Each cycle pair: first occurrence is normal, subsequent are repeated
    return sum(max(0, count - 1) for count in cycles.values())


def _assign_rating(
    goal_reached: bool,
    goal_reach_efficiency: float,
    progress_ratio: float,
    loop_penalty: float,
    semantic_completeness: Optional[float],
    hard_failure: Optional[str],
) -> str:
    """Assign A–F rating based on run quality dimensions."""
    if hard_failure:
        return "F"

    if not goal_reached:
        if progress_ratio > 0.5:
            return "D"
        return "F"

    # Goal reached — judge quality
    sem = semantic_completeness if semantic_completeness is not None else 1.0

    if goal_reach_efficiency >= 0.7 and loop_penalty < 0.1 and sem >= 0.8:
        return "A"
    if goal_reach_efficiency >= 0.4 and loop_penalty < 0.2 and sem >= 0.6:
        return "B"
    return "C"


def evaluate_run(
    path: List[str],
    steps: int,
    escalation_count: int,
    revisit_count: int,
    success_rate: float,
    avg_tension: float,
    total_tension: float,
    reached_goal: bool,
    happy_path_length: int,
    *,
    semantic_completeness: Optional[float] = None,
    hard_failure: Optional[str] = None,
    hybrid_override_count: int = 0,
    hybrid_override_rate: float = 0.0,
    overlay_agree_rate: float = 1.0,
    overlay_count: int = 0,
    r_coh_avg: float = 0.0,
    r_coh_min: float = 0.0,
    r_coh_max: float = 1.0,
    theta_consistency: float = 1.0,
    amplitude_drift: float = 0.0,
) -> RunEvaluation:
    """Build a RunEvaluation from run metrics and graph info."""
    unique_states = len(set(path)) if path else 0
    progress_ratio = unique_states / steps if steps > 0 else 0.0
    repeated = _count_repeated_cycles(path)
    loop_penalty = repeated / steps if steps > 0 else 0.0

    efficiency = 0.0
    if reached_goal and steps > 0 and happy_path_length > 0:
        efficiency = min(1.0, happy_path_length / steps)

    warnings: List[str] = []
    if not reached_goal:
        warnings.append("Goal not reached")
    if repeated > 0:
        warnings.append(f"{repeated} repeated 2-cycle(s) detected")
    if loop_penalty > 0.3:
        warnings.append(f"High loop penalty: {loop_penalty:.2f}")
    if progress_ratio < 0.4 and steps > 3:
        warnings.append(f"Low progress ratio: {progress_ratio:.2f}")
    if escalation_count > steps * 0.3:
        warnings.append(f"High escalation rate: {escalation_count}/{steps}")
    if hybrid_override_count > 0 and hybrid_override_rate > 0.5:
        warnings.append(f"High hybrid override rate: {hybrid_override_rate:.0%} ({hybrid_override_count} overrides)")
    if overlay_count > 0 and overlay_agree_rate < 0.5:
        warnings.append(f"Amplitude frequently disagrees: agree {overlay_agree_rate:.0%} of {overlay_count} steps")
    if r_coh_avg > 0 and r_coh_avg < 0.3:
        warnings.append(f"Low coherence ratio: R_coh_avg={r_coh_avg:.2f}")
    if amplitude_drift > 0.3:
        warnings.append(f"Amplitude drift: {amplitude_drift:.0%} greedy-vs-amplitude disagreement")

    rating = _assign_rating(
        reached_goal, efficiency, progress_ratio,
        loop_penalty, semantic_completeness, hard_failure,
    )

    return RunEvaluation(
        goal_reached=reached_goal,
        steps=steps,
        escalations=escalation_count,
        revisits=revisit_count,
        repeated_cycles=repeated,
        progress_ratio=round(progress_ratio, 4),
        avg_tension=round(avg_tension, 4),
        total_tension=round(total_tension, 4),
        goal_reach_efficiency=round(efficiency, 4),
        loop_penalty=round(loop_penalty, 4),
        step_success_rate=round(success_rate, 4),
        rating=rating,
        warnings=warnings,
        hybrid_override_count=hybrid_override_count,
        hybrid_override_rate=round(hybrid_override_rate, 4),
        overlay_agree_rate=round(overlay_agree_rate, 4),
        overlay_count=overlay_count,
        r_coh_avg=round(r_coh_avg, 4),
        r_coh_min=round(r_coh_min, 4),
        r_coh_max=round(r_coh_max, 4),
        theta_consistency=round(theta_consistency, 4),
        amplitude_drift=round(amplitude_drift, 4),
    )


# ──────────────────────────────────────────────
# 3. Semantic Output Evaluator
# ──────────────────────────────────────────────

_UNCERTAINTY_MARKERS = [
    "uncertain", "unclear", "unknown", "possibly", "potentially",
    "might", "may", "appears to", "seems", "not confirmed",
    "insufficient data", "needs verification", "limited information",
]

_UNSUPPORTED_MARKERS = [
    "obviously", "clearly everyone", "it is well known",
    "without a doubt", "guaranteed", "certainly will",
    "all experts agree", "proven fact",
]


def evaluate_semantics(
    result_log: List[TransitionResult],
    scenario: ScenarioPacket,
) -> SemanticEvaluation:
    """Evaluate semantic quality of run outputs against a scenario packet.

    Uses keyword/section matching for required output coverage and
    heuristic detection of uncertainty markers and unsupported claims.
    """
    # Combine all transition result texts
    combined_text = " ".join(r.result.lower() for r in result_log if r.result)

    # Required output coverage
    required = scenario.required_outputs
    covered = []
    missing = []
    for output_name in required:
        # Normalize: "announcement_summary" → check for "announcement" and "summary"
        keywords = output_name.lower().replace("_", " ").split()
        if all(kw in combined_text for kw in keywords):
            covered.append(output_name)
        else:
            missing.append(output_name)

    coverage = len(covered) / len(required) if required else 1.0

    # Uncertainty marker count
    uncertainty_count = sum(
        1 for marker in _UNCERTAINTY_MARKERS
        if marker in combined_text
    )

    # Grounding warnings: unsupported claim heuristics
    grounding_warns = sum(
        1 for marker in _UNSUPPORTED_MARKERS
        if marker in combined_text
    )

    # Completeness: weighted combo of coverage + confidence
    avg_confidence = (
        sum(r.confidence for r in result_log) / len(result_log)
        if result_log else 0.0
    )
    completeness = 0.6 * coverage + 0.4 * avg_confidence

    notes: List[str] = []
    if missing:
        notes.append(f"Missing outputs: {', '.join(missing)}")
    if grounding_warns > 0:
        notes.append(f"{grounding_warns} possible unsupported claim(s)")
    if uncertainty_count > 0:
        notes.append(f"{uncertainty_count} uncertainty marker(s) found (good)")

    return SemanticEvaluation(
        required_outputs_covered=round(coverage, 4),
        missing_outputs=missing,
        uncertainty_marks=uncertainty_count,
        grounding_warnings=grounding_warns,
        completeness_score=round(completeness, 4),
        notes=notes,
    )


# ──────────────────────────────────────────────
# 4. Hard Failure Detection
# ──────────────────────────────────────────────

def detect_hard_failure(
    gq: GraphQuality,
    reached_goal: bool,
    repeated_cycles: int,
    steps: int,
    semantic_coverage: Optional[float] = None,
) -> Optional[str]:
    """Check for hard failure conditions that gate evaluation.

    Returns a failure reason string, or None if no hard failure.
    """
    # 6.3: Critical graph invalidity
    if not gq.reachable:
        return "Graph: goal not reachable"
    if gq.happy_path is None:
        return "Graph: no happy path exists"

    # 6.1: Goal not reached
    if not reached_goal:
        return "Goal not reached"

    # 6.2: Repeated trivial loop without recovery
    if steps > 0 and repeated_cycles / steps > 0.4:
        return f"Trivial loop dominance: {repeated_cycles} repeated cycles in {steps} steps"

    # 6.4: Semantic deliverable missing required sections
    if semantic_coverage is not None and semantic_coverage < 0.3:
        return f"Critical semantic gap: only {semantic_coverage:.0%} required outputs covered"

    return None


# ──────────────────────────────────────────────
# 5. Combined Scenario Evaluation
# ──────────────────────────────────────────────

def evaluate_scenario(
    scenario_id: str,
    domain: str,
    gq: GraphQuality,
    path: List[str],
    steps: int,
    escalation_count: int,
    revisit_count: int,
    success_rate: float,
    avg_tension: float,
    total_tension: float,
    reached_goal: bool,
    result_log: List[TransitionResult],
    scenario: Optional[ScenarioPacket] = None,
    *,
    hybrid_override_count: int = 0,
    hybrid_override_rate: float = 0.0,
    overlay_agree_rate: float = 1.0,
    overlay_count: int = 0,
    r_coh_avg: float = 0.0,
    r_coh_min: float = 0.0,
    r_coh_max: float = 1.0,
    theta_consistency: float = 1.0,
    amplitude_drift: float = 0.0,
) -> ScenarioEvaluation:
    """Full evaluation pipeline for one scenario run."""
    happy_len = gq.happy_path_length

    # Semantic evaluation (only if scenario exists)
    sem_eval = None
    sem_coverage = None
    if scenario and result_log:
        sem_eval = evaluate_semantics(result_log, scenario)
        sem_coverage = sem_eval.required_outputs_covered

    # Repeated cycles
    repeated = _count_repeated_cycles(path)

    # Hard failure check
    hard = detect_hard_failure(
        gq, reached_goal, repeated, steps, sem_coverage,
    )

    # Run evaluation
    run_eval = evaluate_run(
        path=path,
        steps=steps,
        escalation_count=escalation_count,
        revisit_count=revisit_count,
        success_rate=success_rate,
        avg_tension=avg_tension,
        total_tension=total_tension,
        reached_goal=reached_goal,
        happy_path_length=happy_len,
        semantic_completeness=sem_coverage,
        hard_failure=hard,
        hybrid_override_count=hybrid_override_count,
        hybrid_override_rate=hybrid_override_rate,
        overlay_agree_rate=overlay_agree_rate,
        overlay_count=overlay_count,
        r_coh_avg=r_coh_avg,
        r_coh_min=r_coh_min,
        r_coh_max=r_coh_max,
        theta_consistency=theta_consistency,
        amplitude_drift=amplitude_drift,
    )

    # Overall score (None if hard failure)
    overall = None
    if hard is None:
        graph_w = 0.25
        run_w = 0.40
        sem_w = 0.35
        run_score = run_eval.goal_reach_efficiency * 0.5 + run_eval.progress_ratio * 0.3 + (1.0 - run_eval.loop_penalty) * 0.2
        sem_score = sem_eval.completeness_score if sem_eval else 0.5
        overall = round(
            graph_w * gq.score + run_w * run_score + sem_w * sem_score,
            4,
        )

    return ScenarioEvaluation(
        scenario_id=scenario_id,
        domain=domain,
        graph_score=gq.score,
        run_evaluation=run_eval,
        semantic_evaluation=sem_eval,
        hard_failure=hard,
        overall_score=overall,
    )


# ──────────────────────────────────────────────
# 6. Report Formatting
# ──────────────────────────────────────────────

def format_evaluation_report(evals: List[ScenarioEvaluation]) -> str:
    """Format evaluation results as a structured console report."""
    lines: List[str] = []
    lines.append("")
    lines.append("=" * 78)
    lines.append("E₀ Evaluation Layer Report (Phase 3f)")
    lines.append("=" * 78)

    for ev in evals:
        lines.append("")
        lines.append(f"┌─ {ev.domain} [{ev.scenario_id}]")
        lines.append(f"│")

        # Hard failure gate
        if ev.hard_failure:
            lines.append(f"│  ██ HARD FAILURE: {ev.hard_failure}")
            lines.append(f"│")

        # Graph
        lines.append(f"│  Graph Score:          {ev.graph_score:.2f}")

        # Run dynamics
        r = ev.run_evaluation
        lines.append(f"│  Rating:               {r.rating}")
        lines.append(f"│  Goal Reached:         {'YES' if r.goal_reached else 'NO'}")
        lines.append(f"│  Steps:                {r.steps}")
        lines.append(f"│  Efficiency:           {r.goal_reach_efficiency:.2f}")
        lines.append(f"│  Progress Ratio:       {r.progress_ratio:.2f}")
        lines.append(f"│  Loop Penalty:         {r.loop_penalty:.2f}")
        lines.append(f"│  Escalations:          {r.escalations}")
        lines.append(f"│  Revisits:             {r.revisits}")
        lines.append(f"│  Repeated Cycles:      {r.repeated_cycles}")
        lines.append(f"│  Step Success Rate:    {r.step_success_rate:.0%}")
        lines.append(f"│  Avg Tension:          {r.avg_tension:.4f}")

        # Hybrid / Overlay (Phase 3o)
        if r.overlay_count > 0 or r.hybrid_override_count > 0:
            lines.append(f"│")
            lines.append(f"│  Overlay Steps:        {r.overlay_count}")
            lines.append(f"│  Overlay Agree Rate:   {r.overlay_agree_rate:.0%}")
            lines.append(f"│  Hybrid Overrides:     {r.hybrid_override_count}")
            lines.append(f"│  Override Rate:        {r.hybrid_override_rate:.0%}")

        # Amplitude hybrid metrics (Phase 3h)
        if r.r_coh_avg > 0 or r.amplitude_drift > 0:
            lines.append(f"│")
            lines.append(f"│  R_coh (avg/min/max):  {r.r_coh_avg:.3f} / {r.r_coh_min:.3f} / {r.r_coh_max:.3f}")
            lines.append(f"│  Θ Consistency:        {r.theta_consistency:.3f}")
            lines.append(f"│  Amplitude Drift:      {r.amplitude_drift:.0%}")

        # Semantic
        if ev.semantic_evaluation:
            s = ev.semantic_evaluation
            lines.append(f"│")
            lines.append(f"│  Semantic Coverage:    {s.required_outputs_covered:.0%}")
            lines.append(f"│  Completeness:         {s.completeness_score:.2f}")
            lines.append(f"│  Missing Outputs:      {', '.join(s.missing_outputs) if s.missing_outputs else '(none)'}")
            lines.append(f"│  Uncertainty Marks:    {s.uncertainty_marks}")
            lines.append(f"│  Grounding Warnings:   {s.grounding_warnings}")

        # Overall
        lines.append(f"│")
        if ev.overall_score is not None:
            lines.append(f"│  Overall Score:        {ev.overall_score:.2f}")
        else:
            lines.append(f"│  Overall Score:        N/A (hard failure)")

        # Warnings
        if r.warnings:
            lines.append(f"│")
            for w in r.warnings:
                lines.append(f"│  ⚠ {w}")

        lines.append(f"└{'─' * 77}")

    # Summary across all evaluations
    if len(evals) > 1:
        lines.append("")
        lines.append("─" * 78)
        lines.append("Cross-Domain Summary:")
        ratings = [ev.run_evaluation.rating for ev in evals]
        scores = [ev.overall_score for ev in evals if ev.overall_score is not None]
        hard_fails = [ev for ev in evals if ev.hard_failure]

        lines.append(f"  Ratings:           {', '.join(ratings)}")
        if scores:
            lines.append(f"  Mean Overall:      {sum(scores)/len(scores):.2f}")
            lines.append(f"  Score Spread:      {max(scores)-min(scores):.2f}")
        lines.append(f"  Hard Failures:     {len(hard_fails)}/{len(evals)}")

    lines.append("=" * 78)
    return "\n".join(lines)
