"""Tests for E₀ Human Feedback Loop (C161)."""

import pytest

from e0_controller.feedback import (
    HumanAction,
    FeedbackEvent,
    FeedbackResult,
    action_to_outcome,
    ingest_panel_feedback,
    ingest_feedback,
    _find_perception_edges,
)
from e0_controller.perception import (
    PerceptionDomain,
    build_perception_domain,
    VISUAL_PRIMITIVES,
    LANGUAGE_PRIMITIVES,
)
from e0_controller.primitives import Outcome
from e0_controller.ui_emitter import UIPanel, UISpec


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _make_panel(perception: str = "emphasis", intent: str = "uncertainty",
                urgency: float = 0.5) -> UIPanel:
    return UIPanel(
        intent=intent,
        perception=perception,
        language_act="assertion",
        data_source="self_graph.component_health",
        suggested_visual="heatmap",
        urgency=urgency,
        label="Test panel",
    )


def _make_spec(panels: list, layout: str = "dashboard") -> UISpec:
    return UISpec(
        panels=panels,
        layout=layout,
        generated_at="2026-04-05T00:00:00+00:00",
        context="test",
    )


# ──────────────────────────────────────────────
# 1. Action → Outcome Mapping
# ──────────────────────────────────────────────

class TestActionOutcome:
    def test_click_is_success(self):
        assert action_to_outcome(HumanAction.CLICK) == Outcome.SUCCESS

    def test_ignore_is_failure(self):
        assert action_to_outcome(HumanAction.IGNORE) == Outcome.FAILURE

    def test_followup_is_success(self):
        assert action_to_outcome(HumanAction.FOLLOWUP) == Outcome.SUCCESS

    def test_confusion_is_failure(self):
        assert action_to_outcome(HumanAction.CONFUSION) == Outcome.FAILURE

    def test_dismiss_is_failure(self):
        assert action_to_outcome(HumanAction.DISMISS) == Outcome.FAILURE

    def test_acknowledge_is_success(self):
        assert action_to_outcome(HumanAction.ACKNOWLEDGE) == Outcome.SUCCESS

    def test_all_actions_mapped(self):
        """Every HumanAction has a defined outcome."""
        for action in HumanAction:
            assert action_to_outcome(action) in (
                Outcome.SUCCESS, Outcome.FAILURE
            )


# ──────────────────────────────────────────────
# 2. Edge Finding
# ──────────────────────────────────────────────

class TestFindEdges:
    def test_emphasis_has_edges(self):
        domain = build_perception_domain()
        edges = _find_perception_edges(domain, "emphasis")
        assert len(edges) > 0

    def test_edges_touch_primitive(self):
        domain = build_perception_domain()
        edges = _find_perception_edges(domain, "contrast")
        for e in edges:
            assert e.source == "contrast" or e.target == "contrast"

    def test_unknown_primitive_returns_empty(self):
        domain = build_perception_domain()
        edges = _find_perception_edges(domain, "nonexistent")
        assert edges == []

    def test_all_visual_primitives_have_edges(self):
        domain = build_perception_domain()
        for prim in VISUAL_PRIMITIVES:
            edges = _find_perception_edges(domain, prim)
            assert len(edges) > 0, f"{prim} has no edges"


# ──────────────────────────────────────────────
# 3. Single Panel Feedback
# ──────────────────────────────────────────────

class TestPanelFeedback:
    def test_click_reinforces(self):
        domain = build_perception_domain()
        panel = _make_panel("emphasis")
        before = domain.profile("emphasis")
        event = ingest_panel_feedback(domain, panel, HumanAction.CLICK)
        after = domain.profile("emphasis")
        assert event.outcome == Outcome.SUCCESS
        # SUCCESS adds U-trace → quality improves (more success-leaning)
        assert after.quality > before.quality

    def test_ignore_weakens_quality(self):
        domain = build_perception_domain()
        panel = _make_panel("emphasis")
        # First establish some success baseline
        for _ in range(10):
            ingest_panel_feedback(domain, panel, HumanAction.CLICK)
        q_after_success = domain.profile("emphasis").quality
        # Now failures
        for _ in range(20):
            ingest_panel_feedback(domain, panel, HumanAction.IGNORE)
        q_after_failure = domain.profile("emphasis").quality
        assert q_after_failure < q_after_success

    def test_confusion_records_failure(self):
        domain = build_perception_domain()
        panel = _make_panel("contrast")
        event = ingest_panel_feedback(domain, panel, HumanAction.CONFUSION)
        assert event.outcome == Outcome.FAILURE
        assert event.action == HumanAction.CONFUSION

    def test_followup_is_success(self):
        domain = build_perception_domain()
        panel = _make_panel("sequence")
        event = ingest_panel_feedback(domain, panel, HumanAction.FOLLOWUP)
        assert event.outcome == Outcome.SUCCESS

    def test_event_records_panel(self):
        domain = build_perception_domain()
        panel = _make_panel("hierarchy")
        event = ingest_panel_feedback(domain, panel, HumanAction.CLICK)
        assert event.panel is panel


# ──────────────────────────────────────────────
# 4. Full Spec Feedback
# ──────────────────────────────────────────────

class TestSpecFeedback:
    def test_all_panels_with_feedback(self):
        domain = build_perception_domain()
        spec = _make_spec([
            _make_panel("emphasis"),
            _make_panel("contrast"),
            _make_panel("sequence"),
        ])
        actions = {0: HumanAction.CLICK, 1: HumanAction.IGNORE, 2: HumanAction.FOLLOWUP}
        result = ingest_feedback(domain, spec, actions)
        assert result.event_count == 3
        assert result.panels_without_feedback == []

    def test_partial_feedback(self):
        domain = build_perception_domain()
        spec = _make_spec([
            _make_panel("emphasis"),
            _make_panel("contrast"),
            _make_panel("sequence"),
        ])
        actions = {0: HumanAction.CLICK}  # only panel 0
        result = ingest_feedback(domain, spec, actions)
        assert result.event_count == 1
        assert result.panels_without_feedback == [1, 2]

    def test_no_feedback(self):
        domain = build_perception_domain()
        spec = _make_spec([_make_panel("emphasis")])
        result = ingest_feedback(domain, spec, {})
        assert result.event_count == 0
        assert result.panels_without_feedback == [0]
        assert result.edges_updated == 0

    def test_success_failure_counts(self):
        domain = build_perception_domain()
        spec = _make_spec([
            _make_panel("emphasis"),
            _make_panel("contrast"),
            _make_panel("sequence"),
        ])
        actions = {
            0: HumanAction.CLICK,       # success
            1: HumanAction.CONFUSION,    # failure
            2: HumanAction.DISMISS,      # failure
        }
        result = ingest_feedback(domain, spec, actions)
        assert result.success_count == 1
        assert result.failure_count == 2

    def test_edges_updated_counted(self):
        domain = build_perception_domain()
        spec = _make_spec([_make_panel("emphasis")])
        actions = {0: HumanAction.CLICK}
        result = ingest_feedback(domain, spec, actions)
        assert result.edges_updated > 0

    def test_empty_spec(self):
        domain = build_perception_domain()
        spec = _make_spec([])
        result = ingest_feedback(domain, spec, {})
        assert result.event_count == 0
        assert result.panels_without_feedback == []


# ──────────────────────────────────────────────
# 5. Learning Effect (closed loop)
# ──────────────────────────────────────────────

class TestLearningEffect:
    def test_repeated_success_increases_strength(self):
        """Consistent positive feedback on a perception raises its strength."""
        domain = build_perception_domain()
        panel = _make_panel("grouping")

        # Let initial traces decay, then build up from success
        for _ in range(100):
            ingest_panel_feedback(domain, panel, HumanAction.CLICK)

        after = domain.profile("grouping")
        # After 100 successes, quality should be strongly positive
        assert after.quality > 0.5
        assert after.strength > 0

    def test_repeated_failure_kills_strength(self):
        """Consistent negative feedback drives strength toward 0."""
        domain = build_perception_domain()
        panel = _make_panel("density")

        # Build some success first
        for _ in range(10):
            ingest_panel_feedback(domain, panel, HumanAction.CLICK)
        mid = domain.profile("density").strength
        assert mid > 0

        # Now overwhelm with failure
        for _ in range(50):
            ingest_panel_feedback(domain, panel, HumanAction.IGNORE)
        after = domain.profile("density").strength
        assert after < mid

    def test_feedback_shifts_preferred_perception(self):
        """After feedback, the perception snapshot ranking changes.

        Reinforce 'absence' heavily.  The snapshot should then show
        improved quality for 'absence' compared to baseline.
        """
        domain = build_perception_domain()

        # Baseline
        quality_before = domain.profile("absence").quality

        # Heavily reinforce absence
        panel_abs = _make_panel("absence")
        for _ in range(50):
            ingest_panel_feedback(domain, panel_abs, HumanAction.CLICK)

        quality_after = domain.profile("absence").quality

        # Quality should have improved after consistent positive feedback
        assert quality_after > quality_before

    def test_multiple_panels_compound(self):
        """Feedback on two panels produces more effect than one."""
        # Domain A: one panel feedback
        domain_a = build_perception_domain()
        spec_a = _make_spec([_make_panel("emphasis")])
        ingest_feedback(domain_a, spec_a, {0: HumanAction.CLICK})
        quality_a = domain_a.profile("emphasis").quality

        # Domain B: two panels feedback (same primitive)
        domain_b = build_perception_domain()
        spec_b = _make_spec([
            _make_panel("emphasis"),
            _make_panel("emphasis"),
        ])
        ingest_feedback(domain_b, spec_b, {0: HumanAction.CLICK, 1: HumanAction.CLICK})
        quality_b = domain_b.profile("emphasis").quality

        # Two panels = more success signal → higher quality
        assert quality_b > quality_a


# ──────────────────────────────────────────────
# 6. FeedbackResult properties
# ──────────────────────────────────────────────

class TestFeedbackResult:
    def test_result_properties(self):
        events = [
            FeedbackEvent(
                panel=_make_panel("emphasis"),
                action=HumanAction.CLICK,
                outcome=Outcome.SUCCESS,
            ),
            FeedbackEvent(
                panel=_make_panel("contrast"),
                action=HumanAction.IGNORE,
                outcome=Outcome.FAILURE,
            ),
        ]
        result = FeedbackResult(
            events=events, edges_updated=5, panels_without_feedback=[2]
        )
        assert result.event_count == 2
        assert result.success_count == 1
        assert result.failure_count == 1

    def test_empty_result(self):
        result = FeedbackResult(events=[], edges_updated=0, panels_without_feedback=[])
        assert result.event_count == 0
        assert result.success_count == 0
        assert result.failure_count == 0


# ──────────────────────────────────────────────
# 7. HumanAction enum coverage
# ──────────────────────────────────────────────

class TestHumanAction:
    def test_six_actions(self):
        assert len(HumanAction) == 6

    def test_values(self):
        expected = {"click", "ignore", "followup", "confusion", "dismiss", "acknowledge"}
        assert {a.value for a in HumanAction} == expected
