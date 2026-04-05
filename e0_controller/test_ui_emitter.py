"""
Tests for E₀ UI-Schema Emitter (C160)
========================================
Verify UISpec emission from IntentReport × PerceptionDomain.
"""

import json
import pytest

from e0_controller.primitives import Outcome, Edge
from e0_controller.perception import (
    PerceptionDomain,
    PerceptionKind,
    build_perception_domain,
    VISUAL_PRIMITIVES,
    LANGUAGE_PRIMITIVES,
)
from e0_controller.communication import (
    CommunicationIntent,
    IntentReport,
    IntentType,
)
from e0_controller.ui_emitter import (
    UIPanel,
    UISpec,
    emit_ui_spec,
    _select_visual_perception,
    _select_language_act,
    _select_layout,
    _build_panel,
    _INTENT_VISUAL_AFFINITY,
    _INTENT_LANGUAGE_AFFINITY,
)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _intent(
    itype: IntentType = IntentType.UNCERTAINTY,
    urgency: float = 0.5,
    subject: str = "test",
    summary: str = "test summary",
    **evidence,
) -> CommunicationIntent:
    return CommunicationIntent(
        type=itype,
        urgency=urgency,
        subject=subject,
        summary=summary,
        evidence=evidence,
    )


def _report(*intents: CommunicationIntent) -> IntentReport:
    return IntentReport(intents=list(intents))


# ──────────────────────────────────────────────
# 1. UIPanel Dataclass
# ──────────────────────────────────────────────

class TestUIPanel:

    def test_basic_fields(self):
        p = UIPanel(
            intent="uncertainty",
            perception="emphasis",
            language_act="assertion",
            data_source="self_graph.component_health",
            suggested_visual="heatmap",
            urgency=0.8,
            label="test",
        )
        assert p.intent == "uncertainty"
        assert p.perception == "emphasis"
        assert p.urgency == 0.8

    def test_frozen(self):
        p = UIPanel("x", "y", "z", "d", "v", 0.5, "l")
        with pytest.raises(AttributeError):
            p.urgency = 0.9


# ──────────────────────────────────────────────
# 2. UISpec Dataclass
# ──────────────────────────────────────────────

class TestUISpec:

    def test_empty_spec(self):
        spec = UISpec(panels=[], layout="dashboard",
                      generated_at="2026-04-05T12:00:00Z", context="test")
        assert spec.panel_count == 0
        assert spec.max_urgency == 0.0

    def test_max_urgency(self):
        panels = [
            UIPanel("a", "b", "c", "d", "v", 0.3, "low"),
            UIPanel("a", "b", "c", "d", "v", 0.9, "high"),
        ]
        spec = UISpec(panels=panels, layout="alert",
                      generated_at="now", context="test")
        assert spec.max_urgency == 0.9
        assert spec.panel_count == 2

    def test_to_dict(self):
        panels = [UIPanel("uncertainty", "emphasis", "assertion",
                          "sg", "heatmap", 0.7, "label")]
        spec = UISpec(panels=panels, layout="narrative",
                      generated_at="2026-04-05", context="ctx")
        d = spec.to_dict()
        assert d["layout"] == "narrative"
        assert len(d["panels"]) == 1
        assert d["panels"][0]["intent"] == "uncertainty"
        assert d["panels"][0]["perception"] == "emphasis"

    def test_to_dict_is_json_serializable(self):
        panels = [UIPanel("status", "density", "enumeration",
                          "sg", "dashboard", 0.2, "Status")]
        spec = UISpec(panels=panels, layout="dashboard",
                      generated_at="2026-04-05", context="ctx")
        text = json.dumps(spec.to_dict())
        assert "status" in text


# ──────────────────────────────────────────────
# 3. Visual Perception Selection
# ──────────────────────────────────────────────

class TestVisualPerceptionSelection:

    def test_no_snapshot_uses_first_affinity(self):
        for itype, affinities in _INTENT_VISUAL_AFFINITY.items():
            result = _select_visual_perception(itype, None)
            assert result == affinities[0]

    def test_snapshot_prefers_strongest(self):
        dom = build_perception_domain()
        hist = dom.landscape.historization
        # Heavily reinforce "contrast" — both outgoing AND incoming
        contrast_edges = [e for e in dom.landscape.edges
                          if e.source == "contrast" or e.target == "contrast"]
        for edge in contrast_edges:
            for _ in range(100):
                hist.update(edge, Outcome.SUCCESS)
        snap = dom.snapshot()
        # For UNCERTAINTY, affinities = [emphasis, contrast, label]
        # contrast should now be strongest after heavy reinforcement
        result = _select_visual_perception(IntentType.UNCERTAINTY, snap)
        assert result == "contrast"

    def test_all_intent_types_valid(self):
        dom = build_perception_domain()
        snap = dom.snapshot()
        for itype in IntentType:
            result = _select_visual_perception(itype, snap)
            assert result in VISUAL_PRIMITIVES


# ──────────────────────────────────────────────
# 4. Language Act Selection
# ──────────────────────────────────────────────

class TestLanguageActSelection:

    def test_no_snapshot_uses_affinity(self):
        for itype, expected in _INTENT_LANGUAGE_AFFINITY.items():
            result = _select_language_act(itype, None)
            assert result == expected

    def test_snapshot_respects_default_if_strong(self):
        dom = build_perception_domain()
        snap = dom.snapshot()
        result = _select_language_act(IntentType.REQUEST, snap)
        assert result in LANGUAGE_PRIMITIVES

    def test_all_intent_types_valid(self):
        dom = build_perception_domain()
        snap = dom.snapshot()
        for itype in IntentType:
            result = _select_language_act(itype, snap)
            assert result in LANGUAGE_PRIMITIVES


# ──────────────────────────────────────────────
# 5. Layout Selection
# ──────────────────────────────────────────────

class TestLayoutSelection:

    def test_empty_intents_dashboard(self):
        assert _select_layout([]) == "dashboard"

    def test_high_urgency_alert(self):
        intents = [_intent(urgency=0.9)]
        assert _select_layout(intents) == "alert"

    def test_one_intent_narrative(self):
        intents = [_intent(urgency=0.4)]
        assert _select_layout(intents) == "narrative"

    def test_two_intents_narrative(self):
        intents = [_intent(urgency=0.3), _intent(urgency=0.4)]
        assert _select_layout(intents) == "narrative"

    def test_three_plus_dashboard(self):
        intents = [_intent(urgency=0.3) for _ in range(4)]
        assert _select_layout(intents) == "dashboard"

    def test_high_urgency_overrides_count(self):
        intents = [_intent(urgency=0.2) for _ in range(5)]
        intents.append(_intent(urgency=0.85))
        assert _select_layout(intents) == "alert"


# ──────────────────────────────────────────────
# 6. Panel Building
# ──────────────────────────────────────────────

class TestBuildPanel:

    def test_basic_panel(self):
        i = _intent(IntentType.DECISION, urgency=0.6,
                    summary="chose B over C")
        panel = _build_panel(i, None)
        assert panel.intent == "decision"
        assert panel.perception in VISUAL_PRIMITIVES
        assert panel.language_act in LANGUAGE_PRIMITIVES
        assert panel.urgency == 0.6
        assert panel.label == "chose B over C"

    def test_panel_with_perception_snapshot(self):
        dom = build_perception_domain()
        snap = dom.snapshot()
        i = _intent(IntentType.STATUS)
        panel = _build_panel(i, snap)
        assert panel.perception in VISUAL_PRIMITIVES
        assert panel.language_act in LANGUAGE_PRIMITIVES

    def test_evidence_copied(self):
        i = _intent(IntentType.ANOMALY, quality=-0.7, load=5.0)
        panel = _build_panel(i, None)
        assert panel.evidence["quality"] == -0.7


# ──────────────────────────────────────────────
# 7. emit_ui_spec — Main Entry Point
# ──────────────────────────────────────────────

class TestEmitUISpec:

    def test_basic_emission(self):
        report = _report(
            _intent(IntentType.UNCERTAINTY, urgency=0.7),
            _intent(IntentType.DECISION, urgency=0.4),
        )
        spec = emit_ui_spec(report, context="test run")
        assert isinstance(spec, UISpec)
        assert spec.panel_count == 2
        assert spec.context == "test run"
        assert spec.generated_at  # not empty

    def test_with_perception_domain(self):
        dom = build_perception_domain()
        report = _report(
            _intent(IntentType.UNCERTAINTY, urgency=0.7),
        )
        spec = emit_ui_spec(report, dom, context="with perception")
        assert spec.panel_count == 1
        assert spec.panels[0].perception in VISUAL_PRIMITIVES

    def test_min_urgency_filter(self):
        report = _report(
            _intent(IntentType.UNCERTAINTY, urgency=0.8),
            _intent(IntentType.STATUS, urgency=0.1),
        )
        spec = emit_ui_spec(report, min_urgency=0.5)
        assert spec.panel_count == 1
        assert spec.panels[0].intent == "uncertainty"

    def test_max_panels_limit(self):
        intents = [_intent(urgency=0.5 + i * 0.01) for i in range(20)]
        report = IntentReport(intents=intents)
        spec = emit_ui_spec(report, max_panels=5)
        assert spec.panel_count == 5

    def test_empty_report(self):
        report = IntentReport()
        spec = emit_ui_spec(report)
        assert spec.panel_count == 0
        assert spec.layout == "dashboard"

    def test_alert_layout_on_high_urgency(self):
        report = _report(_intent(urgency=0.9))
        spec = emit_ui_spec(report)
        assert spec.layout == "alert"

    def test_narrative_layout_on_few_intents(self):
        report = _report(_intent(urgency=0.4))
        spec = emit_ui_spec(report)
        assert spec.layout == "narrative"

    def test_dashboard_layout_on_many_intents(self):
        report = _report(*[_intent(urgency=0.3) for _ in range(5)])
        spec = emit_ui_spec(report)
        assert spec.layout == "dashboard"

    def test_to_dict_roundtrip(self):
        report = _report(
            _intent(IntentType.UNCERTAINTY, urgency=0.7, subject="amp"),
            _intent(IntentType.PATTERN, urgency=0.3),
        )
        spec = emit_ui_spec(report, context="roundtrip test")
        d = spec.to_dict()
        assert len(d["panels"]) == 2
        assert d["context"] == "roundtrip test"
        # Must be JSON-serializable
        text = json.dumps(d)
        parsed = json.loads(text)
        assert parsed["panels"][0]["intent"] == "uncertainty"

    def test_perception_learning_affects_emission(self):
        """After reinforcing a perception, it should be preferred."""
        dom = build_perception_domain()
        hist = dom.landscape.historization
        # Heavily reinforce "sequence" outgoing edges
        seq_edges = [e for e in dom.landscape.edges
                     if e.source == "sequence"]
        for edge in seq_edges:
            for _ in range(50):
                hist.update(edge, Outcome.SUCCESS)

        # For DECISION (affinities: contrast, sequence, hierarchy),
        # sequence should now win
        report = _report(_intent(IntentType.DECISION, urgency=0.5))
        spec = emit_ui_spec(report, dom)
        assert spec.panels[0].perception == "sequence"

    def test_all_intent_types_produce_valid_panels(self):
        dom = build_perception_domain()
        for itype in IntentType:
            report = _report(_intent(itype, urgency=0.5))
            spec = emit_ui_spec(report, dom, context=f"test_{itype.value}")
            assert spec.panel_count == 1
            panel = spec.panels[0]
            assert panel.intent == itype.value
            assert panel.perception in VISUAL_PRIMITIVES
            assert panel.language_act in LANGUAGE_PRIMITIVES
