"""
E₀ Human Feedback Loop (C161)
================================
Closes the communication loop: human interaction with rendered UI
generates outcome signals that flow back into the perception landscape.

When E0 emits a UISpec (C160), each panel maps an intent to a
perception primitive. When the human interacts with the rendered UI,
the interaction is classified as a HumanAction. Each action maps to
an E0 Outcome (SUCCESS / FAILURE / PARTIAL), which historizes the
perception edges that were used — reinforcing what worked, weakening
what didn't.

This is standard E0 online learning: outcome → historization →
trace_load update → behavior change. No special mechanism required —
the perception landscape is a normal E0 Landscape.

See docs/E0_HUMAN_COMMUNICATION_DESIGN_v1.md §2 (The Feedback Loop).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from .perception import PerceptionDomain, RENDERING_PRIMITIVES
from .primitives import Edge, Outcome
from .ui_emitter import UIPanel, UISpec


# ──────────────────────────────────────────────
# 1. Human Actions
# ──────────────────────────────────────────────

class HumanAction(Enum):
    """Observable human interactions with a rendered UI panel."""
    CLICK = "click"              # engaged with the panel
    IGNORE = "ignore"            # panel was shown but not interacted with
    FOLLOWUP = "followup"        # asked a follow-up question
    CONFUSION = "confusion"      # expressed confusion or misunderstanding
    DISMISS = "dismiss"          # explicitly closed / rejected panel
    ACKNOWLEDGE = "acknowledge"  # saw and confirmed (low engagement)


# Mapping: HumanAction → E0 Outcome
_ACTION_OUTCOME: Dict[HumanAction, Outcome] = {
    HumanAction.CLICK:        Outcome.SUCCESS,
    HumanAction.IGNORE:       Outcome.FAILURE,
    HumanAction.FOLLOWUP:     Outcome.SUCCESS,
    HumanAction.CONFUSION:    Outcome.FAILURE,
    HumanAction.DISMISS:      Outcome.FAILURE,
    HumanAction.ACKNOWLEDGE:  Outcome.SUCCESS,
}


def action_to_outcome(action: HumanAction) -> Outcome:
    """Map a human action to an E0 Outcome."""
    return _ACTION_OUTCOME[action]


# ──────────────────────────────────────────────
# 2. Feedback Events
# ──────────────────────────────────────────────

@dataclass(frozen=True)
class FeedbackEvent:
    """A single feedback event: human acted on a panel.

    Attributes:
        panel: the UIPanel that was acted upon.
        action: the observed human action.
        outcome: the derived E0 Outcome.
    """
    panel: UIPanel
    action: HumanAction
    outcome: Outcome


@dataclass(frozen=True)
class FeedbackResult:
    """Summary of feedback ingestion for a UISpec.

    Attributes:
        events: all feedback events processed.
        edges_updated: number of perception edges historized.
        panels_without_feedback: panel indices that had no feedback.
    """
    events: List[FeedbackEvent]
    edges_updated: int
    panels_without_feedback: List[int]

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def success_count(self) -> int:
        return sum(1 for e in self.events if e.outcome == Outcome.SUCCESS)

    @property
    def failure_count(self) -> int:
        return sum(1 for e in self.events if e.outcome == Outcome.FAILURE)


# ──────────────────────────────────────────────
# 3. Feedback Ingestion
# ──────────────────────────────────────────────

def _find_perception_edges(
    domain: PerceptionDomain,
    primitive_name: str,
) -> List[Edge]:
    """Find all edges in the perception landscape touching a primitive.

    Returns edges where the primitive is either source or target,
    so that reinforcement propagates through the perception graph.
    """
    return [
        e for e in domain.landscape.edges
        if e.source == primitive_name or e.target == primitive_name
    ]


def ingest_panel_feedback(
    domain: PerceptionDomain,
    panel: UIPanel,
    action: HumanAction,
) -> FeedbackEvent:
    """Ingest feedback for a single panel.

    Historizes all perception edges touching the panel's perception
    primitive with the outcome derived from the human action.

    C164: Additionally historizes the specific perception→rendering
    edge that was used (e.g., emphasis→heatmap). This gives the
    chosen rendering widget a stronger learning signal than
    alternatives, enabling E0 to learn which widget works best.

    Returns the FeedbackEvent for audit.
    """
    outcome = action_to_outcome(action)
    edges = _find_perception_edges(domain, panel.perception)

    hist = domain.landscape.historization
    for edge in edges:
        hist.update(edge, outcome)

    # C164: targeted rendering edge update
    rendering_edge = Edge(panel.perception, panel.suggested_visual)
    if (panel.suggested_visual in RENDERING_PRIMITIVES
            and domain.landscape.has_edge(
                panel.perception, panel.suggested_visual)):
        hist.update(rendering_edge, outcome)

    return FeedbackEvent(panel=panel, action=action, outcome=outcome)


def ingest_feedback(
    domain: PerceptionDomain,
    spec: UISpec,
    actions: Dict[int, HumanAction],
) -> FeedbackResult:
    """Ingest feedback for an entire UISpec.

    Args:
        domain: The perception domain whose landscape is historized.
        spec: The UISpec that was rendered for the human.
        actions: Mapping of panel index → human action.
            Panels not in this dict receive no feedback (they are
            tracked in panels_without_feedback).

    Returns:
        FeedbackResult summarizing what was historized.
    """
    events: List[FeedbackEvent] = []
    edges_updated = 0
    panels_without = []

    for idx, panel in enumerate(spec.panels):
        if idx not in actions:
            panels_without.append(idx)
            continue
        action = actions[idx]
        edge_count = len(_find_perception_edges(domain, panel.perception))
        event = ingest_panel_feedback(domain, panel, action)
        events.append(event)
        edges_updated += edge_count

    return FeedbackResult(
        events=events,
        edges_updated=edges_updated,
        panels_without_feedback=panels_without,
    )
