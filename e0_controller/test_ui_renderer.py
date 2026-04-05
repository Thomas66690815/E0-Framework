"""Tests for E₀ UI Renderer (C163)."""

import json
import pathlib
import pytest

from e0_controller.ui_emitter import UIPanel, UISpec
from e0_controller.ui_renderer import (
    urgency_color,
    urgency_text_color,
    render_html,
    render_to_file,
    _render_panel,
    _render_evidence,
    _render_visual,
    _layout_css,
)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _make_panel(
    intent: str = "uncertainty",
    perception: str = "emphasis",
    suggested_visual: str = "heatmap",
    urgency: float = 0.5,
    label: str = "Test panel",
    evidence: dict | None = None,
) -> UIPanel:
    return UIPanel(
        intent=intent,
        perception=perception,
        language_act="assertion",
        data_source="self_graph.component_health",
        suggested_visual=suggested_visual,
        urgency=urgency,
        label=label,
        evidence=evidence or {},
    )


def _make_spec(
    panels: list | None = None,
    layout: str = "dashboard",
    context: str = "test context",
) -> UISpec:
    if panels is None:
        panels = [_make_panel()]
    return UISpec(
        panels=panels,
        layout=layout,
        generated_at="2026-04-05T12:00:00+00:00",
        context=context,
    )


# ──────────────────────────────────────────────
# 1. Color Mapping
# ──────────────────────────────────────────────

class TestUrgencyColor:
    def test_zero_is_green(self):
        c = urgency_color(0.0)
        assert c == "rgb(76,175,80)"

    def test_half_is_yellow(self):
        c = urgency_color(0.5)
        assert c == "rgb(255,235,59)"

    def test_one_is_red(self):
        c = urgency_color(1.0)
        assert c == "rgb(244,67,54)"

    def test_clamp_below_zero(self):
        c = urgency_color(-0.5)
        assert c == urgency_color(0.0)

    def test_clamp_above_one(self):
        c = urgency_color(1.5)
        assert c == urgency_color(1.0)

    def test_quarter(self):
        c = urgency_color(0.25)
        # Should be between green and yellow
        assert c.startswith("rgb(")

    def test_text_color_low(self):
        assert urgency_text_color(0.3) == "#222"

    def test_text_color_high(self):
        assert urgency_text_color(0.8) == "#fff"


# ──────────────────────────────────────────────
# 2. Visual Renderers
# ──────────────────────────────────────────────

class TestVisualRenderers:
    def test_heatmap(self):
        panel = _make_panel(suggested_visual="heatmap", urgency=0.9)
        html_out = _render_visual(panel)
        assert "visual-heatmap" in html_out
        assert "0.90" in html_out

    def test_tree(self):
        panel = _make_panel(
            suggested_visual="tree",
            evidence={"status": "harmful", "quality": -0.4},
        )
        html_out = _render_visual(panel)
        assert "visual-tree" in html_out
        assert "status" in html_out
        assert "harmful" in html_out

    def test_timeline(self):
        panel = _make_panel(
            suggested_visual="timeline",
            evidence={"step_1": "init", "step_2": "run"},
        )
        html_out = _render_visual(panel)
        assert "visual-timeline" in html_out
        assert "step_1" in html_out

    def test_bar(self):
        panel = _make_panel(suggested_visual="bar", urgency=0.7)
        html_out = _render_visual(panel)
        assert "visual-bar" in html_out
        assert "70%" in html_out

    def test_text(self):
        panel = _make_panel(suggested_visual="text")
        html_out = _render_visual(panel)
        assert "visual-text" in html_out

    def test_highlight(self):
        panel = _make_panel(suggested_visual="highlight")
        html_out = _render_visual(panel)
        assert "visual-highlight" in html_out

    def test_dashboard_visual(self):
        panel = _make_panel(
            suggested_visual="dashboard",
            evidence={"healthy": 5, "confused": 1},
        )
        html_out = _render_visual(panel)
        assert "visual-dashboard" in html_out
        assert "healthy" in html_out

    def test_unknown_visual_falls_back_to_text(self):
        panel = _make_panel(suggested_visual="unknown_widget")
        html_out = _render_visual(panel)
        assert "visual-text" in html_out


# ──────────────────────────────────────────────
# 3. Evidence Rendering
# ──────────────────────────────────────────────

class TestEvidence:
    def test_empty_evidence(self):
        assert _render_evidence({}) == ""

    def test_with_evidence(self):
        html_out = _render_evidence({"key": "value"})
        assert "<details" in html_out
        assert "Evidence" in html_out
        assert "key" in html_out

    def test_xss_escaped(self):
        html_out = _render_evidence({"<script>": "alert(1)"})
        assert "<script>" not in html_out
        assert "&lt;script&gt;" in html_out


# ──────────────────────────────────────────────
# 4. Panel Card
# ──────────────────────────────────────────────

class TestPanelCard:
    def test_contains_label(self):
        panel = _make_panel(label="My Label")
        html_out = _render_panel(panel, 0)
        assert "My Label" in html_out

    def test_contains_intent_tag(self):
        panel = _make_panel(intent="decision")
        html_out = _render_panel(panel, 0)
        assert "decision" in html_out

    def test_contains_feedback_buttons(self):
        panel = _make_panel()
        html_out = _render_panel(panel, 0)
        assert "Engage" in html_out
        assert "Acknowledge" in html_out
        assert "Confused" in html_out
        assert "Dismiss" in html_out

    def test_data_index(self):
        panel = _make_panel()
        html_out = _render_panel(panel, 3)
        assert 'data-index="3"' in html_out
        assert "feedback(3," in html_out

    def test_xss_in_label(self):
        panel = _make_panel(label="<img onerror=alert(1)>")
        html_out = _render_panel(panel, 0)
        assert "<img onerror" not in html_out
        assert "&lt;img" in html_out


# ──────────────────────────────────────────────
# 5. Layout CSS
# ──────────────────────────────────────────────

class TestLayoutCSS:
    def test_alert_layout(self):
        css = _layout_css("alert")
        assert "flex-direction:column" in css
        assert "f44336" in css  # red border

    def test_narrative_layout(self):
        css = _layout_css("narrative")
        assert "flex-direction:column" in css
        assert "700px" in css

    def test_dashboard_layout(self):
        css = _layout_css("dashboard")
        assert "grid" in css

    def test_unknown_defaults_to_dashboard(self):
        css = _layout_css("something_else")
        assert "grid" in css


# ──────────────────────────────────────────────
# 6. Full HTML Render
# ──────────────────────────────────────────────

class TestRenderHTML:
    def test_valid_html(self):
        spec = _make_spec()
        result = render_html(spec)
        assert "<!DOCTYPE html>" in result
        assert "</html>" in result

    def test_contains_panels(self):
        spec = _make_spec([
            _make_panel(label="Panel A"),
            _make_panel(label="Panel B"),
        ])
        result = render_html(spec)
        assert "Panel A" in result
        assert "Panel B" in result

    def test_contains_feedback_section(self):
        spec = _make_spec()
        result = render_html(spec)
        assert "feedback-json" in result
        assert "feedbackLog" in result

    def test_contains_context(self):
        spec = _make_spec(context="my test context")
        result = render_html(spec)
        assert "my test context" in result

    def test_empty_spec(self):
        spec = _make_spec(panels=[])
        result = render_html(spec)
        assert "<!DOCTYPE html>" in result
        assert "Panels: 0" in result

    def test_custom_title(self):
        spec = _make_spec()
        result = render_html(spec, title="Custom Title")
        assert "Custom Title" in result

    def test_alert_layout_applied(self):
        spec = _make_spec(layout="alert")
        result = render_html(spec)
        assert "f44336" in result  # red styling


# ──────────────────────────────────────────────
# 7. File Output
# ──────────────────────────────────────────────

class TestRenderToFile:
    def test_writes_file(self, tmp_path):
        spec = _make_spec()
        out = tmp_path / "test.html"
        result = render_to_file(spec, out)
        assert result.exists()
        content = result.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content

    def test_returns_resolved_path(self, tmp_path):
        spec = _make_spec()
        out = tmp_path / "test.html"
        result = render_to_file(spec, out)
        assert result.is_absolute()


# ──────────────────────────────────────────────
# 8. Integration: emit → render
# ──────────────────────────────────────────────

class TestEmitAndRender:
    def test_full_pipeline(self):
        """UISpec from real emit_ui_spec → render_html."""
        from e0_controller.communication import detect_intents
        from e0_controller.perception import build_perception_domain
        from e0_controller.self_graph import SelfGraph, active_components
        from e0_controller.primitives import Outcome
        from e0_controller.ui_emitter import emit_ui_spec

        sg = SelfGraph()
        core = active_components(overlap_active=False)
        for _ in range(10):
            sg.self_historize(core, Outcome.SUCCESS)

        domain = build_perception_domain()
        report = detect_intents(self_graph=sg, include_status=True)
        spec = emit_ui_spec(report, domain, context="integration test")

        html_out = render_html(spec, title="Integration Test")
        assert "<!DOCTYPE html>" in html_out
        assert spec.layout in html_out
        for panel in spec.panels:
            assert panel.label in html_out or panel.intent in html_out
