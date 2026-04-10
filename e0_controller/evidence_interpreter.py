"""
E₀ Evidence Interpreter (C209)
================================
Template-based prose generation from structured evidence dicts.

Turns the numeric/categorical data that lives in UIPanel.evidence,
inscription_summary(), inscription_stats(), and trace metrics into
human-readable narratives. No LLM needed — the structure IS the story.

Dispatch strategy: evidence dicts carry signature keys that reveal
their type (e.g. "status" → uncertainty, "source"+"outcome" → decision).
Each type gets a dedicated narrative template.

Public API:
    interpret_evidence(evidence, context)   → prose for any evidence dict
    interpret_inscription_summary(summary)  → edge-level inscription story
    interpret_inscription_stats(stats)      → global inscription overview
    interpret_trace(quality, load, inertia) → trace metric assessment
    interpret_domain_crossings(crossings)   → crossing narrative
    interpret_panel(panel)                  → full panel interpretation
"""

from __future__ import annotations

from typing import Any, Dict, Optional


# ──────────────────────────────────────────────
# 1. Trace metric interpretation
# ──────────────────────────────────────────────

def interpret_trace(quality: float, load: float, inertia: float = 0.0) -> str:
    """Turn trace metrics into a human-readable assessment.

    Args:
        quality: trace_quality value in [-1, 1].
        load: trace_load (number of inscriptions).
        inertia: inertia_factor (optional).

    Returns:
        One-sentence prose assessment.
    """
    # Quality assessment
    if quality > 0.5:
        q_desc = "strongly confirmed"
    elif quality > 0.2:
        q_desc = "mostly confirmed"
    elif quality > -0.2:
        q_desc = "ambiguous — roughly equal successes and failures"
    elif quality > -0.5:
        q_desc = "leaning towards problematic"
    else:
        q_desc = "strongly contradicted"

    # Load assessment
    if load < 2:
        l_desc = "barely visited"
    elif load < 5:
        l_desc = "lightly traversed"
    elif load < 15:
        l_desc = "moderately traversed"
    elif load < 30:
        l_desc = "well-traveled"
    else:
        l_desc = "heavily traversed"

    parts = [f"This pathway is {q_desc} ({l_desc}, load={load:.0f})"]

    # Inertia assessment
    if inertia > 0.0:
        if inertia > 0.8:
            parts.append("High inertia — resistant to change.")
        elif inertia > 0.4:
            parts.append(f"Moderate inertia ({inertia:.2f}).")
        else:
            parts.append("Low inertia — still malleable.")

    return ". ".join(parts)


# ──────────────────────────────────────────────
# 2. Inscription-level interpretation
# ──────────────────────────────────────────────

def interpret_inscription_summary(
    summary: Dict[str, Any],
    edge_label: str = "",
) -> str:
    """Turn inscription_summary() output into a narrative.

    Args:
        summary: Dict from Historization.inscription_summary(edge).
        edge_label: Optional human-readable edge name.

    Returns:
        Multi-sentence narrative about the edge's history.
    """
    count = summary.get("count", 0)
    if count == 0:
        label = f" '{edge_label}'" if edge_label else ""
        return f"Edge{label} has no recorded traversals."

    label = f"'{edge_label}' " if edge_label else "This edge "

    # Dominant mode
    modes = summary.get("modes", {})
    dominant_mode = max(modes, key=modes.get) if modes else "unknown"

    # Dominant role
    roles = summary.get("roles", {})
    role_parts = [f"{r} ({c}×)" for r, c in sorted(roles.items(), key=lambda x: -x[1])]

    # Success rate
    rate = summary.get("success_rate", 0.0)
    if rate > 0.8:
        rate_desc = "high success rate"
    elif rate > 0.5:
        rate_desc = "moderate success rate"
    elif rate > 0.2:
        rate_desc = "low success rate"
    else:
        rate_desc = "very low success rate"

    # Domain pairs
    domain_pairs = summary.get("domain_pairs", {})
    crossing = any("→" in dp for dp in domain_pairs)

    sentences = [
        f"{label}has been traversed {count} time{'s' if count != 1 else ''}, "
        f"primarily in {dominant_mode} mode.",
    ]

    if role_parts:
        sentences.append(f"Roles: {', '.join(role_parts)}.")

    sentences.append(f"Success: {rate:.0%} ({rate_desc}).")

    if crossing:
        pairs = [f"{dp} ({c}×)" for dp, c in domain_pairs.items()]
        sentences.append(f"Domain crossings: {', '.join(pairs)}.")

    return " ".join(sentences)


def interpret_inscription_stats(stats: Dict[str, Any]) -> str:
    """Turn inscription_stats() output into a global overview narrative.

    Args:
        stats: Dict from Historization.inscription_stats().

    Returns:
        Multi-sentence overview of all inscriptions.
    """
    total = stats.get("total_inscriptions", 0)
    edges = stats.get("inscribed_edges", 0)
    crossings = stats.get("domain_crossing_count", 0)
    role_totals = stats.get("role_totals", {})
    mode_totals = stats.get("mode_totals", {})

    if total == 0:
        return "No inscriptions recorded yet."

    # Dominant role
    dom_role = max(role_totals, key=role_totals.get) if role_totals else None
    dom_role_pct = (role_totals[dom_role] / total * 100) if dom_role else 0

    # Dominant mode
    dom_mode = max(mode_totals, key=mode_totals.get) if mode_totals else None

    sentences = [
        f"The system has recorded {total} inscription{'s' if total != 1 else ''} "
        f"across {edges} edge{'s' if edges != 1 else ''}.",
    ]

    if crossings > 0:
        cross_pct = crossings / total * 100
        sentences.append(
            f"{crossings} ({cross_pct:.0f}%) involved domain crossings."
        )

    if dom_role:
        sentences.append(
            f"The dominant role is {dom_role} ({dom_role_pct:.0f}% of traversals)."
        )

    if dom_mode:
        sentences.append(f"Primary operating mode: {dom_mode}.")

    # Secondary roles
    if len(role_totals) > 1:
        secondary = [
            f"{r} ({c}×)"
            for r, c in sorted(role_totals.items(), key=lambda x: -x[1])
            if r != dom_role
        ]
        if secondary:
            sentences.append(f"Other roles: {', '.join(secondary)}.")

    return " ".join(sentences)


# ──────────────────────────────────────────────
# 3. Domain crossing interpretation
# ──────────────────────────────────────────────

def interpret_domain_crossings(
    crossings: Dict[str, int],
    total_steps: int = 0,
) -> str:
    """Turn domain crossing counts into a narrative.

    Args:
        crossings: Dict mapping pair labels to counts,
            e.g. {"EN↔Canon": 104, "EN↔Bootstrap": 55}.
        total_steps: Optional total step count for percentage.

    Returns:
        Prose about cross-domain activity.
    """
    if not crossings:
        return "No domain crossings recorded."

    total_crossings = sum(crossings.values())
    parts = [f"{total_crossings} domain crossing{'s' if total_crossings != 1 else ''}"]

    if total_steps > 0:
        pct = total_crossings / total_steps * 100
        parts[0] += f" ({pct:.0f}% of all steps)"

    parts[0] += ":"

    ranked = sorted(crossings.items(), key=lambda x: -x[1])
    for pair, count in ranked:
        parts.append(f"  {pair}: {count}×")

    dominant = ranked[0]
    if len(ranked) > 1 and dominant[1] > ranked[1][1] * 2:
        parts.append(
            f"The {dominant[0]} axis dominates, suggesting "
            f"strong affinity between these domains."
        )

    return "\n".join(parts)


# ──────────────────────────────────────────────
# 4. Evidence dict interpretation (dispatch)
# ──────────────────────────────────────────────

def _interpret_uncertainty(evidence: Dict[str, Any]) -> str:
    """Uncertainty evidence: status + quality/load."""
    status = evidence.get("status", "unknown")
    quality = evidence.get("quality", 0.0)
    load = evidence.get("load", 0.0)

    if status == "harmful":
        return (
            f"This component is flagged as harmful "
            f"(quality={quality:+.3f}, load={load:.1f}). "
            f"Historically, it has produced more failures than successes."
        )
    elif status == "confused":
        return (
            f"This component shows confusion "
            f"(quality={quality:+.3f}, load={load:.1f}). "
            f"Evidence is mixed — neither clearly helpful nor harmful."
        )
    elif status == "insufficient_data":
        return (
            f"Insufficient data to assess this component "
            f"(load={load:.1f}). More traversals are needed."
        )
    else:
        return f"Uncertainty detected (status={status})."


def _interpret_decision(evidence: Dict[str, Any]) -> str:
    """Decision evidence: source → target with candidates."""
    source = evidence.get("source", "?")
    target = evidence.get("target", "?")
    outcome = evidence.get("outcome", "?")
    s_eff = evidence.get("s_eff", 0.0)
    candidates = evidence.get("candidates", [])
    rejected = evidence.get("rejected", [])

    parts = [f"Navigated {source} → {target} (outcome: {outcome})."]

    if s_eff > 0.5:
        parts.append(f"High effective tension ({s_eff:.3f}) drove this choice.")
    elif s_eff > 0:
        parts.append(f"Moderate tension ({s_eff:.3f}).")

    if rejected:
        parts.append(
            f"Rejected {len(rejected)} alternative{'s' if len(rejected) != 1 else ''}: "
            f"{', '.join(str(r) for r in rejected[:3])}."
        )
    elif len(candidates) > 1:
        parts.append(f"Chose from {len(candidates)} candidates.")

    return " ".join(parts)


def _interpret_pattern(evidence: Dict[str, Any]) -> str:
    """Pattern evidence: resistance drop."""
    before = evidence.get("r_eff_before", 0.0)
    after = evidence.get("r_eff_after", 0.0)
    drop = evidence.get("drop_pct", 0.0)

    if drop > 50:
        impact = "dramatic"
    elif drop > 20:
        impact = "significant"
    elif drop > 5:
        impact = "moderate"
    else:
        impact = "minor"

    return (
        f"Resistance dropped from {before:.3f} to {after:.3f} "
        f"(−{drop:.1f}%, a {impact} reduction)."
    )


def _interpret_status_self_graph(evidence: Dict[str, Any]) -> str:
    """Self-graph status: healthy/confused/harmful breakdown."""
    healthy = evidence.get("healthy", [])
    confused = evidence.get("confused", [])
    harmful = evidence.get("harmful", [])
    insufficient = evidence.get("insufficient_data", [])
    actions = evidence.get("meta_actions", [])

    total = len(healthy) + len(confused) + len(harmful) + len(insufficient)
    parts = [f"Self-graph assessment: {total} component{'s' if total != 1 else ''}."]

    if healthy:
        parts.append(f"Healthy: {len(healthy)} ({', '.join(str(h) for h in healthy[:3])}).")
    if confused:
        parts.append(f"Confused: {len(confused)} ({', '.join(str(c) for c in confused[:3])}).")
    if harmful:
        parts.append(f"Harmful: {len(harmful)} ({', '.join(str(h) for h in harmful[:3])}).")
    if insufficient:
        parts.append(f"Insufficient data: {len(insufficient)}.")
    if actions:
        parts.append(f"Suggested actions: {', '.join(str(a) for a in actions[:3])}.")

    return " ".join(parts)


def _interpret_status_task(evidence: Dict[str, Any]) -> str:
    """Task landscape status: progress and coverage."""
    task = evidence.get("task", "unknown")
    goal_reached = evidence.get("goal_reached", False)
    steps = evidence.get("steps", 0)
    success_rate = evidence.get("success_rate", 0.0)
    avg_tension = evidence.get("avg_tension", 0.0)
    edge_count = evidence.get("edge_count", 0)
    states = evidence.get("states", [])

    result = "Goal reached." if goal_reached else "Goal not yet reached."

    parts = [
        f"Task '{task}': {result}",
        f"{len(states)} states, {edge_count} edges, {steps} steps taken.",
        f"Success rate: {success_rate:.0%}, average tension: {avg_tension:.3f}.",
    ]

    return " ".join(parts)


def _interpret_request_deadend(evidence: Dict[str, Any]) -> str:
    """Dead-end request."""
    state = evidence.get("state", "?")
    goal = evidence.get("goal", "?")
    return (
        f"Dead end at '{state}' — no admissible neighbors. "
        f"Cannot proceed towards goal '{goal}'. "
        f"Structural extension or backtracking required."
    )


def _interpret_dream(evidence: Dict[str, Any]) -> str:
    """Dream equivalence / anomaly."""
    own = evidence.get("own_state", "?")
    partner = evidence.get("partner_state", "?")
    tq = evidence.get("trace_quality", 0.0)

    return (
        f"Dream equivalence detected: '{own}' ↔ '{partner}' "
        f"(trace quality: {tq:+.3f}). "
        f"These states show structural similarity across domains."
    )


def _interpret_generic(evidence: Dict[str, Any]) -> str:
    """Fallback: key-value listing as prose."""
    if not evidence:
        return "No evidence data available."

    parts = []
    for k, v in evidence.items():
        if isinstance(v, float):
            parts.append(f"{k}={v:.3f}")
        elif isinstance(v, list):
            parts.append(f"{k}: {len(v)} items")
        elif isinstance(v, dict):
            parts.append(f"{k}: {len(v)} entries")
        else:
            parts.append(f"{k}={v}")

    return "Evidence: " + ", ".join(parts) + "."


# ── Signature-based dispatch ───────────────────

_EVIDENCE_SIGNATURES = [
    # (required_keys, interpreter)
    ({"status", "quality"}, _interpret_uncertainty),
    ({"status", "load"}, _interpret_uncertainty),
    ({"source", "target", "outcome"}, _interpret_decision),
    ({"r_eff_before", "r_eff_after"}, _interpret_pattern),
    ({"healthy", "confused"}, _interpret_status_self_graph),
    ({"task", "goal_reached"}, _interpret_status_task),
    ({"state", "admissible_neighbors"}, _interpret_request_deadend),
    ({"own_state", "partner_state"}, _interpret_dream),
]


def interpret_evidence(
    evidence: Dict[str, Any],
    context: str = "",
) -> str:
    """Turn a structured evidence dict into prose.

    Dispatches based on the keys present in the dict. Falls back
    to a generic key-value listing for unrecognized structures.

    Args:
        evidence: The evidence dict (from UIPanel, CommunicationIntent, etc.)
        context: Optional context hint (e.g. "self_graph", "navigation").

    Returns:
        Human-readable prose interpretation.
    """
    if not evidence:
        return "No evidence data available."

    keys = set(evidence.keys())

    for required, interpreter in _EVIDENCE_SIGNATURES:
        if required <= keys:
            return interpreter(evidence)

    return _interpret_generic(evidence)


# ──────────────────────────────────────────────
# 5. Panel interpretation
# ──────────────────────────────────────────────

def interpret_panel(panel: "UIPanel") -> str:
    """Full panel interpretation: label + evidence narrative.

    Args:
        panel: A UIPanel instance.

    Returns:
        Multi-line interpretation combining panel metadata and evidence prose.
    """
    from .text_renderer import urgency_label

    label = urgency_label(panel.urgency)

    parts = [
        f"{panel.label} ({label}, urgency {panel.urgency:.2f})",
        f"Intent: {panel.intent} | Perception: {panel.perception} | Act: {panel.language_act}",
    ]

    evidence_prose = interpret_evidence(panel.evidence)
    if evidence_prose != "No evidence data available.":
        parts.append(evidence_prose)

    return "\n".join(parts)
