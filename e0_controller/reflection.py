"""
E₀ Reflection Layer (Phase 3g)
=================================
Bounded self-reference over persisted system behavior.

Reflection consumes evaluation evidence and produces structured
improvement-oriented observations.  It is meta-diagnostic and
action-oriented — not free introspection.

Three trigger classes:
  1. Failure   — hard failures, goal not reached, structural collapse
  2. Quality   — suboptimal success, low efficiency, weak semantics
  3. Opportunity — unusually strong runs worth preserving

See E0_REFLECTION_LAYER_v0.1.md for architecture.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .evaluation import ScenarioEvaluation, RunEvaluation, SemanticEvaluation
from .graph_validation import GraphQuality
from .llm_adapter import LLMConfig, LLMResponseError, TransitionResult


# ──────────────────────────────────────────────
# 1. Reflection Decision
# ──────────────────────────────────────────────

@dataclass
class ReflectionDecision:
    """Whether and why to trigger reflection."""
    reflect: bool
    reason: str
    priority: str           # "low" | "medium" | "high"
    reflection_type: str    # "failure" | "quality" | "opportunity"


# ──────────────────────────────────────────────
# 2. Reflection Report
# ──────────────────────────────────────────────

@dataclass
class ReflectionReport:
    """Structured output of a reflection pass."""
    reflection_type: str                    # "failure" | "quality" | "opportunity"
    observed_patterns: List[str] = field(default_factory=list)
    likely_layers: List[str] = field(default_factory=list)   # plural: multi-layer attribution
    evidence: List[str] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)
    preservations: List[str] = field(default_factory=list)   # patterns worth keeping


# ──────────────────────────────────────────────
# 3. Trigger Thresholds
# ──────────────────────────────────────────────

# Failure triggers (hard — always reflect)
_FAILURE_EFFICIENCY_FLOOR = 0.0     # goal not reached

# Quality triggers (soft — reflect on suboptimal success)
_QUALITY_EFFICIENCY_CEIL = 0.5      # low efficiency despite goal
_QUALITY_LOOP_PENALTY_CEIL = 0.15   # non-trivial looping
_QUALITY_SEMANTIC_CEIL = 0.6        # weak semantic coverage
_QUALITY_ESCALATION_RATIO = 0.3     # high escalation rate
_QUALITY_PROGRESS_FLOOR = 0.5       # low progress ratio

# Opportunity triggers (positive — reflect to preserve)
_OPPORTUNITY_RATING = "A"
_OPPORTUNITY_EFFICIENCY_FLOOR = 0.8
_OPPORTUNITY_GRAPH_SCORE_FLOOR = 0.9

# Amplitude hybrid triggers (Phase 3h)
_AMPLITUDE_DRIFT_THRESHOLD = 0.3       # > 30% greedy-vs-amplitude mismatch
_COHERENCE_QUALITY_FLOOR = 0.3         # R_coh < 30% triggers quality
_COHERENCE_OPPORTUNITY_FLOOR = 0.8     # R_coh > 80% is opportunity
_THETA_OPPORTUNITY_FLOOR = 0.9         # Θ > 90% is opportunity


# ──────────────────────────────────────────────
# 4. Should Reflect?
# ──────────────────────────────────────────────

def should_reflect(ev: ScenarioEvaluation) -> ReflectionDecision:
    """Determine whether reflection should be triggered for this evaluation.

    Checks failure triggers first (highest priority), then quality,
    then opportunity.  Returns the first matching trigger class.
    """
    run = ev.run_evaluation

    # ── Failure triggers (hard) ──
    if ev.hard_failure:
        return ReflectionDecision(
            reflect=True,
            reason=f"Hard failure: {ev.hard_failure}",
            priority="high",
            reflection_type="failure",
        )
    if not run.goal_reached:
        return ReflectionDecision(
            reflect=True,
            reason="Goal not reached",
            priority="high",
            reflection_type="failure",
        )
    if run.repeated_cycles > 0 and run.loop_penalty > 0.3:
        return ReflectionDecision(
            reflect=True,
            reason=f"Severe loop penalty ({run.loop_penalty:.2f})",
            priority="high",
            reflection_type="failure",
        )

    # ── Quality triggers (soft) ──
    quality_reasons: List[str] = []

    if run.goal_reach_efficiency < _QUALITY_EFFICIENCY_CEIL:
        quality_reasons.append(
            f"low efficiency ({run.goal_reach_efficiency:.2f})")
    if run.loop_penalty > _QUALITY_LOOP_PENALTY_CEIL:
        quality_reasons.append(
            f"non-trivial looping (penalty {run.loop_penalty:.2f})")
    if run.steps > 0 and run.escalations / run.steps > _QUALITY_ESCALATION_RATIO:
        quality_reasons.append(
            f"high escalation rate ({run.escalations}/{run.steps})")
    if run.progress_ratio < _QUALITY_PROGRESS_FLOOR:
        quality_reasons.append(
            f"low progress ({run.progress_ratio:.2f})")
    if ev.semantic_evaluation:
        sem = ev.semantic_evaluation
        if sem.required_outputs_covered < _QUALITY_SEMANTIC_CEIL:
            quality_reasons.append(
                f"weak semantic coverage ({sem.required_outputs_covered:.0%})")

    # Amplitude hybrid (Phase 3h)
    if run.amplitude_drift > _AMPLITUDE_DRIFT_THRESHOLD:
        quality_reasons.append(
            f"amplitude drift ({run.amplitude_drift:.0%} disagreement)")
    if run.r_coh_avg > 0 and run.r_coh_avg < _COHERENCE_QUALITY_FLOOR:
        quality_reasons.append(
            f"low coherence ratio (R_coh={run.r_coh_avg:.2f})")

    if quality_reasons:
        return ReflectionDecision(
            reflect=True,
            reason="; ".join(quality_reasons),
            priority="medium",
            reflection_type="quality",
        )

    # ── Opportunity triggers (positive) ──
    opportunity_reasons: List[str] = []

    if run.rating == _OPPORTUNITY_RATING:
        opportunity_reasons.append("A-rated run")
    if run.goal_reach_efficiency >= _OPPORTUNITY_EFFICIENCY_FLOOR:
        opportunity_reasons.append(
            f"high efficiency ({run.goal_reach_efficiency:.2f})")
    if ev.graph_score >= _OPPORTUNITY_GRAPH_SCORE_FLOOR:
        opportunity_reasons.append(
            f"strong graph ({ev.graph_score:.2f})")

    # Amplitude hybrid (Phase 3h)
    if run.r_coh_avg >= _COHERENCE_OPPORTUNITY_FLOOR:
        opportunity_reasons.append(
            f"high coherence (R_coh={run.r_coh_avg:.2f})")
    if run.theta_consistency >= _THETA_OPPORTUNITY_FLOOR and run.r_coh_avg > 0:
        opportunity_reasons.append(
            f"strong phase alignment (Θ={run.theta_consistency:.2f})")

    if opportunity_reasons:
        return ReflectionDecision(
            reflect=True,
            reason="; ".join(opportunity_reasons),
            priority="low",
            reflection_type="opportunity",
        )

    # ── No trigger ──
    return ReflectionDecision(
        reflect=False,
        reason="No reflection trigger matched",
        priority="low",
        reflection_type="quality",
    )


# ──────────────────────────────────────────────
# 5. Reflection Logic
# ──────────────────────────────────────────────

def _reflect_failure(ev: ScenarioEvaluation) -> ReflectionReport:
    """Reflect on a failed or structurally collapsed run."""
    run = ev.run_evaluation
    patterns: List[str] = []
    layers: List[str] = []
    evidence: List[str] = []
    actions: List[str] = []

    # Hard failure analysis
    if ev.hard_failure:
        patterns.append(f"Hard failure: {ev.hard_failure}")
        evidence.append(f"hard_failure={ev.hard_failure}")

    # Goal analysis
    if not run.goal_reached:
        patterns.append("Run did not reach goal state")
        evidence.append(f"goal_reached=False, steps={run.steps}")
        if run.progress_ratio < 0.3:
            patterns.append("Minimal structural progress")
            layers.append("controller")
            actions.append("Investigate controller selection logic for this graph topology")

    # Loop analysis
    if run.repeated_cycles > 0:
        patterns.append(f"{run.repeated_cycles} repeated 2-cycle(s)")
        evidence.append(f"loop_penalty={run.loop_penalty:.2f}")
        layers.append("graph_design")
        layers.append("controller")
        actions.append("Add controller-level trivial-loop breaker (detect 2-cycle, force alternative)")
        actions.append("Review graph for bidirectional low-resistance edges that invite oscillation")

    # Graph quality
    if ev.graph_score < 0.5:
        patterns.append(f"Weak graph structure (score={ev.graph_score:.2f})")
        layers.append("graph_design")
        actions.append("Improve LLM landscape prompt to produce better graph topology")

    # Semantic gaps
    if ev.semantic_evaluation and ev.semantic_evaluation.required_outputs_covered < 0.5:
        sem = ev.semantic_evaluation
        patterns.append(f"Severe semantic gap ({sem.required_outputs_covered:.0%} coverage)")
        layers.append("semantic")
        if sem.missing_outputs:
            evidence.append(f"missing: {', '.join(sem.missing_outputs)}")
        actions.append("Check scenario packet required_outputs alignment with graph states")

    # Amplitude coherence collapse (Phase 3h)
    if run.r_coh_avg > 0 and run.r_coh_min < 0.1:
        patterns.append(f"Coherence collapse detected (R_coh_min={run.r_coh_min:.3f})")
        evidence.append(f"r_coh_avg={run.r_coh_avg:.3f}, r_coh_min={run.r_coh_min:.3f}")
        layers.append("controller")
        actions.append("Investigate destructive phase cancellation in graph topology")

    # Deduplicate layers
    layers = list(dict.fromkeys(layers))

    return ReflectionReport(
        reflection_type="failure",
        observed_patterns=patterns,
        likely_layers=layers,
        evidence=evidence,
        recommended_actions=actions,
    )


def _reflect_quality(ev: ScenarioEvaluation) -> ReflectionReport:
    """Reflect on a suboptimally successful run."""
    run = ev.run_evaluation
    patterns: List[str] = []
    layers: List[str] = []
    evidence: List[str] = []
    actions: List[str] = []

    # Efficiency
    if run.goal_reach_efficiency < _QUALITY_EFFICIENCY_CEIL:
        patterns.append(f"Low path efficiency ({run.goal_reach_efficiency:.2f})")
        evidence.append(f"efficiency={run.goal_reach_efficiency:.2f}, steps={run.steps}")
        layers.append("graph_design")
        actions.append("Check for unnecessary detour states in graph")

    # Looping
    if run.loop_penalty > _QUALITY_LOOP_PENALTY_CEIL:
        patterns.append(f"Non-trivial loop activity (penalty={run.loop_penalty:.2f})")
        evidence.append(f"repeated_cycles={run.repeated_cycles}")
        layers.append("controller")
        actions.append("Increase revisit penalty alpha or add cycle-breaking logic")

    # Escalations
    if run.steps > 0 and run.escalations / run.steps > _QUALITY_ESCALATION_RATIO:
        patterns.append(f"High escalation rate ({run.escalations}/{run.steps})")
        layers.append("graph_design")
        layers.append("controller")
        actions.append("Review graph connectivity — frequent escalation suggests poor edge structure")

    # Progress ratio
    if run.progress_ratio < _QUALITY_PROGRESS_FLOOR:
        patterns.append(f"Low progress ratio ({run.progress_ratio:.2f})")
        evidence.append(f"unique_states relative to steps is low")
        layers.append("controller")

    # Semantic
    if ev.semantic_evaluation:
        sem = ev.semantic_evaluation
        if sem.required_outputs_covered < _QUALITY_SEMANTIC_CEIL:
            patterns.append(f"Incomplete semantic output ({sem.required_outputs_covered:.0%})")
            if sem.missing_outputs:
                evidence.append(f"missing: {', '.join(sem.missing_outputs)}")
            layers.append("semantic")
            actions.append("Ensure transition tasks explicitly address required outputs")
        if sem.grounding_warnings > 0:
            patterns.append(f"{sem.grounding_warnings} grounding warning(s)")
            layers.append("semantic")
            actions.append("Review LLM outputs for unsupported claims")

    # Amplitude hybrid (Phase 3h)
    if run.amplitude_drift > _AMPLITUDE_DRIFT_THRESHOLD:
        patterns.append(f"Amplitude drift: {run.amplitude_drift:.0%} greedy-vs-amplitude disagreement")
        evidence.append(f"amplitude_drift={run.amplitude_drift:.2f}, overlay_agree_rate={run.overlay_agree_rate:.2f}")
        layers.append("controller")
        actions.append("Review penalized tension weights — amplitude suggests alternative pathways")
    if run.r_coh_avg > 0 and run.r_coh_avg < _COHERENCE_QUALITY_FLOOR:
        patterns.append(f"Low coherence ratio (R_coh_avg={run.r_coh_avg:.2f})")
        evidence.append(f"r_coh_min={run.r_coh_min:.3f}, r_coh_max={run.r_coh_max:.3f}")
        layers.append("graph_design")
        actions.append("Graph phases cause cancellation — consider simplifying parallel branches")

    layers = list(dict.fromkeys(layers))

    return ReflectionReport(
        reflection_type="quality",
        observed_patterns=patterns,
        likely_layers=layers,
        evidence=evidence,
        recommended_actions=actions,
    )


def _reflect_opportunity(ev: ScenarioEvaluation) -> ReflectionReport:
    """Reflect on an unusually strong run to identify patterns worth preserving."""
    run = ev.run_evaluation
    patterns: List[str] = []
    layers: List[str] = []
    evidence: List[str] = []
    preservations: List[str] = []

    if run.rating == "A":
        patterns.append("A-rated run — structurally and semantically strong")
        evidence.append(f"rating=A, efficiency={run.goal_reach_efficiency:.2f}")

    if run.goal_reach_efficiency >= _OPPORTUNITY_EFFICIENCY_FLOOR:
        patterns.append(f"High path efficiency ({run.goal_reach_efficiency:.2f})")
        preservations.append("Graph topology produced efficient path — preserve graph design pattern")

    if run.escalations == 0:
        patterns.append("Zero escalations — clean deterministic traversal")
        preservations.append("Controller selected correct path without escalation")

    if run.repeated_cycles == 0 and run.steps > 2:
        patterns.append("No repeated cycles")
        preservations.append("Graph has no degenerate bidirectional low-resistance edges")

    if ev.graph_score >= _OPPORTUNITY_GRAPH_SCORE_FLOOR:
        patterns.append(f"Strong graph quality ({ev.graph_score:.2f})")
        layers.append("graph_design")
        preservations.append("LLM produced well-structured landscape — note prompt pattern")

    if ev.semantic_evaluation:
        sem = ev.semantic_evaluation
        if sem.required_outputs_covered >= 0.9:
            patterns.append(f"High semantic coverage ({sem.required_outputs_covered:.0%})")
            layers.append("semantic")
            preservations.append("Scenario packet + prompt produced near-complete deliverable")
        if sem.grounding_warnings == 0 and sem.uncertainty_marks > 0:
            patterns.append("Good epistemic discipline (uncertainty marked, no unsupported claims)")
            preservations.append("LLM exhibited appropriate epistemic caution")

    # Amplitude hybrid (Phase 3h)
    if run.r_coh_avg >= _COHERENCE_OPPORTUNITY_FLOOR:
        patterns.append(f"High coherence ratio (R_coh_avg={run.r_coh_avg:.2f})")
        evidence.append(f"r_coh_avg={run.r_coh_avg:.2f}, r_coh_min={run.r_coh_min:.2f}")
        preservations.append("Graph phase structure supports constructive interference — preserve topology")
    if run.theta_consistency >= _THETA_OPPORTUNITY_FLOOR and run.r_coh_avg > 0:
        patterns.append(f"Strong phase alignment (Θ={run.theta_consistency:.2f})")
        preservations.append("Path phases are well-aligned — graph has coherent forward flow")
    if run.amplitude_drift == 0.0 and run.overlay_count > 0:
        patterns.append("Perfect greedy-amplitude agreement")
        preservations.append("Deterministic controller and amplitude view fully agree — ideal structure")

    layers = list(dict.fromkeys(layers))

    return ReflectionReport(
        reflection_type="opportunity",
        observed_patterns=patterns,
        likely_layers=layers,
        evidence=evidence,
        preservations=preservations,
    )


# ──────────────────────────────────────────────
# 6. LLM-Backed Reflection
# ──────────────────────────────────────────────

REFLECTION_SYSTEM_PROMPT = """You are the E₀ Reflection Layer.
You analyse structured evaluation evidence from an E₀ controller run.
You identify patterns, attribute causes to system layers, and propose concrete improvements.
You do NOT produce free narrative or self-mythology.
You respond ONLY with the requested JSON structure."""

REFLECTION_PROMPT = """\
Reflect on the following E₀ run evaluation.

Reflection type: {reflection_type}
Trigger reason: {trigger_reason}

--- Evaluation Evidence ---
{evidence_block}

--- Transition Output Samples ---
{result_samples}

Analyse the evidence. Identify:
1. observed_patterns — structural or semantic patterns you see in this run
2. likely_layers — which system layers are most responsible (from: graph_design, controller, semantic, scenario, llm_prompt)
3. evidence — specific metrics or facts supporting your analysis
4. recommended_actions — concrete improvements to make (be specific)
5. preservations — patterns worth keeping for future runs (especially for opportunity reflections)

Respond with exactly this JSON (no other text):
{{
  "observed_patterns": ["..."],
  "likely_layers": ["..."],
  "evidence": ["..."],
  "recommended_actions": ["..."],
  "preservations": ["..."]
}}"""

# Type for pluggable LLM backends (same as llm_adapter)
ReflectionCallFn = Callable[[str, str, LLMConfig], str]


def _build_evidence_block(ev: ScenarioEvaluation) -> str:
    """Build a structured text block of evaluation evidence for the LLM."""
    lines: List[str] = []
    run = ev.run_evaluation

    lines.append(f"Domain: {ev.domain}")
    lines.append(f"Scenario: {ev.scenario_id}")
    lines.append(f"Graph Score: {ev.graph_score:.2f}")
    lines.append(f"Hard Failure: {ev.hard_failure or 'none'}")
    lines.append(f"Overall Score: {ev.overall_score}")
    lines.append("")
    lines.append("Run Dynamics:")
    lines.append(f"  Rating: {run.rating}")
    lines.append(f"  Goal Reached: {run.goal_reached}")
    lines.append(f"  Steps: {run.steps}")
    lines.append(f"  Efficiency: {run.goal_reach_efficiency:.2f}")
    lines.append(f"  Progress Ratio: {run.progress_ratio:.2f}")
    lines.append(f"  Loop Penalty: {run.loop_penalty:.2f}")
    lines.append(f"  Repeated Cycles: {run.repeated_cycles}")
    lines.append(f"  Escalations: {run.escalations}")
    lines.append(f"  Revisits: {run.revisits}")
    lines.append(f"  Step Success Rate: {run.step_success_rate:.0%}")
    lines.append(f"  Avg Tension: {run.avg_tension:.4f}")
    if run.warnings:
        lines.append(f"  Warnings: {'; '.join(run.warnings)}")

    # Amplitude hybrid metrics (Phase 3h)
    if run.r_coh_avg > 0 or run.amplitude_drift > 0:
        lines.append("")
        lines.append("Amplitude Hybrid Metrics:")
        lines.append(f"  R_coh (avg/min/max): {run.r_coh_avg:.3f} / {run.r_coh_min:.3f} / {run.r_coh_max:.3f}")
        lines.append(f"  Θ Consistency: {run.theta_consistency:.3f}")
        lines.append(f"  Amplitude Drift: {run.amplitude_drift:.2f}")
        if hasattr(run, 'override_count') and run.override_count > 0:
            lines.append(f"  Overrides: {run.override_count} (amplitude disagreed with greedy)")

    if ev.semantic_evaluation:
        sem = ev.semantic_evaluation
        lines.append("")
        lines.append("Semantic Evaluation:")
        lines.append(f"  Coverage: {sem.required_outputs_covered:.0%}")
        lines.append(f"  Completeness: {sem.completeness_score:.2f}")
        lines.append(f"  Missing: {', '.join(sem.missing_outputs) if sem.missing_outputs else 'none'}")
        lines.append(f"  Uncertainty Marks: {sem.uncertainty_marks}")
        lines.append(f"  Grounding Warnings: {sem.grounding_warnings}")

    return "\n".join(lines)


def _build_result_samples(
    result_log: Optional[List[TransitionResult]],
    max_samples: int = 5,
) -> str:
    """Format a few transition output samples for the LLM to inspect."""
    if not result_log:
        return "(no transition outputs available)"

    samples = result_log[:max_samples]
    lines: List[str] = []
    for i, r in enumerate(samples, 1):
        text = r.result[:200] + "..." if len(r.result) > 200 else r.result
        lines.append(f"  [{i}] {r.outcome.name} (conf={r.confidence:.2f}): {text}")

    if len(result_log) > max_samples:
        lines.append(f"  ... ({len(result_log) - max_samples} more transitions)")

    return "\n".join(lines)


def _parse_reflection_response(raw: str, reflection_type: str) -> ReflectionReport:
    """Parse LLM JSON response into a ReflectionReport."""
    text = raw.strip()
    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        raise LLMResponseError(
            f"Reflection LLM returned invalid JSON: {exc}",
            raw_response=raw,
        ) from exc

    if not isinstance(data, dict):
        raise LLMResponseError(
            f"Expected JSON object, got {type(data).__name__}",
            raw_response=raw,
        )

    return ReflectionReport(
        reflection_type=reflection_type,
        observed_patterns=data.get("observed_patterns", []),
        likely_layers=data.get("likely_layers", []),
        evidence=data.get("evidence", []),
        recommended_actions=data.get("recommended_actions", []),
        preservations=data.get("preservations", []),
    )


def reflect_with_llm(
    ev: ScenarioEvaluation,
    decision: ReflectionDecision,
    call_fn: ReflectionCallFn,
    config: LLMConfig,
    result_log: Optional[List[TransitionResult]] = None,
) -> ReflectionReport:
    """Run LLM-backed reflection on a scenario evaluation.

    Uses the LLM to analyse evaluation evidence and produce a structured
    reflection report with patterns, layer attribution, and actions.
    """
    evidence_block = _build_evidence_block(ev)
    result_samples = _build_result_samples(result_log)

    prompt = REFLECTION_PROMPT.format(
        reflection_type=decision.reflection_type,
        trigger_reason=decision.reason,
        evidence_block=evidence_block,
        result_samples=result_samples,
    )

    raw = call_fn(REFLECTION_SYSTEM_PROMPT, prompt, config)
    return _parse_reflection_response(raw, decision.reflection_type)


# ──────────────────────────────────────────────
# 7. Main Reflection Entry Point
# ──────────────────────────────────────────────

def reflect(
    ev: ScenarioEvaluation,
    call_fn: Optional[ReflectionCallFn] = None,
    config: Optional[LLMConfig] = None,
    result_log: Optional[List[TransitionResult]] = None,
) -> Optional[ReflectionReport]:
    """Run reflection on a scenario evaluation if triggered.

    If call_fn and config are provided, uses LLM-backed reflection.
    Otherwise falls back to rule-based reflection.
    Returns a ReflectionReport if reflection was warranted, or None.
    """
    decision = should_reflect(ev)
    if not decision.reflect:
        return None

    # LLM path: structured reflection with real reasoning
    if call_fn is not None and config is not None:
        try:
            return reflect_with_llm(ev, decision, call_fn, config, result_log)
        except (LLMResponseError, Exception):
            # Fall through to rule-based on LLM failure
            pass

    # Rule-based fallback
    if decision.reflection_type == "failure":
        return _reflect_failure(ev)
    elif decision.reflection_type == "quality":
        return _reflect_quality(ev)
    elif decision.reflection_type == "opportunity":
        return _reflect_opportunity(ev)
    return None


# ──────────────────────────────────────────────
# 8. Report Formatting
# ──────────────────────────────────────────────

def format_reflection_report(reports: List[ReflectionReport], domains: Optional[List[str]] = None) -> str:
    """Format reflection reports as a structured console report."""
    lines: List[str] = []
    lines.append("")
    lines.append("=" * 78)
    lines.append("E₀ Reflection Layer Report (Phase 3g)")
    lines.append("=" * 78)

    for i, report in enumerate(reports):
        domain_label = domains[i] if domains and i < len(domains) else f"Run {i+1}"
        type_icon = {"failure": "██", "quality": "▓▓", "opportunity": "░░"}.get(
            report.reflection_type, "  ")

        lines.append("")
        lines.append(f"┌─ {domain_label} [{report.reflection_type.upper()}] {type_icon}")
        lines.append(f"│")

        if report.observed_patterns:
            lines.append(f"│  Observed Patterns:")
            for p in report.observed_patterns:
                lines.append(f"│    • {p}")

        if report.likely_layers:
            lines.append(f"│")
            lines.append(f"│  Likely Responsible Layers:")
            for layer in report.likely_layers:
                lines.append(f"│    → {layer}")

        if report.evidence:
            lines.append(f"│")
            lines.append(f"│  Evidence:")
            for e in report.evidence:
                lines.append(f"│    [{e}]")

        if report.recommended_actions:
            lines.append(f"│")
            lines.append(f"│  Recommended Actions:")
            for a in report.recommended_actions:
                lines.append(f"│    ▸ {a}")

        if report.preservations:
            lines.append(f"│")
            lines.append(f"│  Patterns Worth Preserving:")
            for p in report.preservations:
                lines.append(f"│    ★ {p}")

        lines.append(f"└{'─' * 77}")

    # Summary
    if len(reports) > 1:
        lines.append("")
        lines.append("─" * 78)
        type_counts = {}
        for r in reports:
            type_counts[r.reflection_type] = type_counts.get(r.reflection_type, 0) + 1
        total_actions = sum(len(r.recommended_actions) for r in reports)
        total_preservations = sum(len(r.preservations) for r in reports)

        lines.append("Reflection Summary:")
        for t, c in sorted(type_counts.items()):
            lines.append(f"  {t}: {c} domain(s)")
        lines.append(f"  Total actions proposed: {total_actions}")
        lines.append(f"  Total patterns to preserve: {total_preservations}")

    lines.append("=" * 78)
    return "\n".join(lines)
