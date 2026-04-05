"""
E₀ UI-Schema Emitter (C160)
==============================
Maps (CommunicationIntent × PerceptionDomain) → UISpec.

This is Layer 3 of the Human Communication architecture — the bridge
between what E0 wants to say (C159) and what a coding agent can consume.

The emitter consults the perception landscape to decide *how* to
present each intent. If perception primitives have been reinforced
through historization (feedback loop), the strongest perceptions are
preferred. On cold start, heuristic affinities provide reasonable
defaults.

Output: a UISpec — a structured, agent-agnostic description of what
to show, why, and with what perceptual strategy. The UISpec does not
prescribe rendering technology.

See docs/E0_HUMAN_COMMUNICATION_DESIGN_v1.md §2 Layer 3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .communication import CommunicationIntent, IntentReport, IntentType
from .perception import (
    PerceptionDomain,
    PerceptionKind,
    PerceptionSnapshot,
    VISUAL_PRIMITIVES,
    LANGUAGE_PRIMITIVES,
)


# ──────────────────────────────────────────────
# 1. UISpec Dataclasses
# ──────────────────────────────────────────────

@dataclass(frozen=True)
class UIPanel:
    """One panel in the UI specification.

    Describes *what* to show and *why*, not *how* to render it.
    """
    intent: str              # intent type value ("uncertainty", ...)
    perception: str          # chosen perception primitive ("emphasis", ...)
    language_act: str        # chosen language primitive ("assertion", ...)
    data_source: str         # dotted path into E0 state
    suggested_visual: str    # "heatmap", "tree", "timeline", "bar", "text"
    urgency: float           # 0.0 = informational, 1.0 = critical
    label: str               # human-readable title
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UISpec:
    """Complete UI specification emitted by E0.

    A coding agent consumes this to generate a concrete frontend.
    """
    panels: List[UIPanel]
    layout: str              # "dashboard", "narrative", "alert"
    generated_at: str        # ISO timestamp
    context: str             # what E0 was doing when this was generated

    @property
    def panel_count(self) -> int:
        return len(self.panels)

    @property
    def max_urgency(self) -> float:
        if not self.panels:
            return 0.0
        return max(p.urgency for p in self.panels)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict (JSON-compatible)."""
        return {
            "layout": self.layout,
            "generated_at": self.generated_at,
            "context": self.context,
            "panels": [
                {
                    "intent": p.intent,
                    "perception": p.perception,
                    "language_act": p.language_act,
                    "data_source": p.data_source,
                    "suggested_visual": p.suggested_visual,
                    "urgency": p.urgency,
                    "label": p.label,
                    "evidence": p.evidence,
                }
                for p in self.panels
            ],
        }


# ──────────────────────────────────────────────
# 2. Heuristic Affinities (cold-start defaults)
# ──────────────────────────────────────────────

# Which visual perception primitives naturally fit which intent type.
# These are initial heuristics — the perception landscape's learned
# strengths override these once enough feedback is accumulated.

_INTENT_VISUAL_AFFINITY: Dict[IntentType, List[str]] = {
    IntentType.UNCERTAINTY: ["emphasis", "contrast", "label"],
    IntentType.DECISION:    ["contrast", "sequence", "hierarchy"],
    IntentType.PATTERN:     ["sequence", "motion", "grouping"],
    IntentType.REQUEST:     ["emphasis", "label", "absence"],
    IntentType.STATUS:      ["density", "grouping", "hierarchy"],
    IntentType.ANOMALY:     ["emphasis", "contrast", "motion"],
}

_INTENT_LANGUAGE_AFFINITY: Dict[IntentType, str] = {
    IntentType.UNCERTAINTY: "uncertainty",
    IntentType.DECISION:    "assertion",
    IntentType.PATTERN:     "reference",
    IntentType.REQUEST:     "question",
    IntentType.STATUS:      "enumeration",
    IntentType.ANOMALY:     "assertion",
}

_INTENT_VISUAL_SUGGESTION: Dict[IntentType, str] = {
    IntentType.UNCERTAINTY: "heatmap",
    IntentType.DECISION:    "tree",
    IntentType.PATTERN:     "timeline",
    IntentType.REQUEST:     "text",
    IntentType.STATUS:      "dashboard",
    IntentType.ANOMALY:     "highlight",
}

_INTENT_DATA_SOURCE: Dict[IntentType, str] = {
    IntentType.UNCERTAINTY: "self_graph.component_health",
    IntentType.DECISION:    "controller.step_result",
    IntentType.PATTERN:     "landscape.trace_dynamics",
    IntentType.REQUEST:     "self_graph.insufficient_data",
    IntentType.STATUS:      "self_graph.snapshot",
    IntentType.ANOMALY:     "dream_observer.equivalences",
}


# ──────────────────────────────────────────────
# 3. Perception Selection
# ──────────────────────────────────────────────

def _select_visual_perception(
    intent_type: IntentType,
    snapshot: Optional[PerceptionSnapshot],
) -> str:
    """Choose the best visual perception primitive for an intent.

    Strategy:
    1. Get the heuristic affinity list for this intent type.
    2. If a perception snapshot is available, pick the highest-strength
       primitive from the affinity list.
    3. If no snapshot or all strengths are 0, use the first affinity.
    """
    affinities = _INTENT_VISUAL_AFFINITY.get(
        intent_type, ["emphasis", "label"]
    )

    if snapshot is not None:
        best_name = affinities[0]
        best_strength = -1.0
        for name in affinities:
            try:
                p = snapshot.by_name(name)
                if p.strength > best_strength:
                    best_strength = p.strength
                    best_name = name
            except KeyError:
                continue
        return best_name

    return affinities[0]


def _select_language_act(
    intent_type: IntentType,
    snapshot: Optional[PerceptionSnapshot],
) -> str:
    """Choose the language primitive for an intent.

    Uses heuristic affinity, boosted by learned strength if available.
    """
    default = _INTENT_LANGUAGE_AFFINITY.get(intent_type, "assertion")

    if snapshot is None:
        return default

    # Check if the default is strong; if not, check alternatives
    try:
        default_profile = snapshot.by_name(default)
        if default_profile.strength > 0:
            return default
    except KeyError:
        pass

    # Fall back to strongest language primitive
    lang_ranked = snapshot.ranked(PerceptionKind.LANGUAGE)
    if lang_ranked and lang_ranked[0].strength > 0:
        return lang_ranked[0].name

    return default


# ──────────────────────────────────────────────
# 4. Layout Selection
# ──────────────────────────────────────────────

def _select_layout(intents: List[CommunicationIntent]) -> str:
    """Choose the overall layout based on intent composition.

    - alert: any intent with urgency >= 0.8
    - narrative: 1-2 intents (focused story)
    - dashboard: 3+ intents (multi-panel overview)
    """
    if not intents:
        return "dashboard"
    max_urgency = max(i.urgency for i in intents)
    if max_urgency >= 0.8:
        return "alert"
    if len(intents) <= 2:
        return "narrative"
    return "dashboard"


# ──────────────────────────────────────────────
# 5. Panel Building
# ──────────────────────────────────────────────

def _build_panel(
    intent: CommunicationIntent,
    snapshot: Optional[PerceptionSnapshot],
) -> UIPanel:
    """Build a single UIPanel from an intent and perception state."""
    visual = _select_visual_perception(intent.type, snapshot)
    language = _select_language_act(intent.type, snapshot)
    suggested = _INTENT_VISUAL_SUGGESTION.get(intent.type, "text")
    data_source = _INTENT_DATA_SOURCE.get(intent.type, "self_graph")

    return UIPanel(
        intent=intent.type.value,
        perception=visual,
        language_act=language,
        data_source=data_source,
        suggested_visual=suggested,
        urgency=intent.urgency,
        label=intent.summary,
        evidence=dict(intent.evidence),
    )


# ──────────────────────────────────────────────
# 6. Main Emitter
# ──────────────────────────────────────────────

def emit_ui_spec(
    report: IntentReport,
    perception: Optional[PerceptionDomain] = None,
    *,
    context: str = "",
    max_panels: int = 10,
    min_urgency: float = 0.0,
) -> UISpec:
    """Emit a UISpec from an IntentReport and optional PerceptionDomain.

    This is the main entry point for Layer 3.

    Args:
        report: IntentReport from detect_intents() (C159).
        perception: Optional PerceptionDomain (C158). If provided,
            perception strengths influence visual/language selection.
        context: Description of what E0 was doing.
        max_panels: Maximum number of panels to emit.
        min_urgency: Filter out intents below this urgency.

    Returns:
        A UISpec ready for consumption by a coding agent.
    """
    snapshot = perception.snapshot() if perception is not None else None

    # Filter and limit
    intents = report.above_urgency(min_urgency)
    intents = intents[:max_panels]

    # Build panels
    panels = [_build_panel(i, snapshot) for i in intents]

    # Select layout
    layout = _select_layout(intents)

    return UISpec(
        panels=panels,
        layout=layout,
        generated_at=datetime.now(timezone.utc).isoformat(),
        context=context,
    )
