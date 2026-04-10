"""
Tests for C208: Text Renderer.

Parallel text dispatcher to HTML renderer (C163).
Same UISpec input, structured text output.

Test structure:
    TestUrgencyUtilities      — prefix, bar, label mapping
    TestEvidenceFormatting     — dict → indented text
    TestTextRenderers          — each of the 7 visual renderers
    TestPanelRendering         — full panel block
    TestRenderText             — full document assembly
    TestRenderMarkdown         — markdown output format
    TestRenderToFile           — file write + format selection
    TestEndToEnd               — UISpec from emitter → text output
"""

import json
import pytest
from e0_controller.ui_emitter import UIPanel, UISpec
from e0_controller.text_renderer import (
    urgency_prefix,
    urgency_bar,
    urgency_label,
    _format_evidence,
    _render_heatmap_text,
    _render_tree_text,
    _render_timeline_text,
    _render_bar_text,
    _render_text_text,
    _render_highlight_text,
    _render_dashboard_text,
    _render_visual_text,
    _render_panel_text,
    render_text,
    render_markdown,
    render_to_text_file,
    _TEXT_RENDERERS,
)


def _make_panel(**overrides) -> UIPanel:
    """Factory for test panels."""
    defaults = dict(
        intent="status",
        perception="emphasis",
        language_act="assertion",
        data_source="self_graph.quality",
        suggested_visual="text",
        urgency=0.5,
        label="Test Panel",
        evidence={"quality": -0.3, "load": 15.2},
    )
    defaults.update(overrides)
    return UIPanel(**defaults)


def _make_spec(panels=None, layout="dashboard", context="test") -> UISpec:
    """Factory for test specs."""
    if panels is None:
        panels = [_make_panel()]
    return UISpec(
        panels=panels,
        layout=layout,
        generated_at="2026-04-10T12:00:00Z",
        context=context,
    )


# ── Urgency Utilities ──────────────────────────────────────────────────


class TestUrgencyUtilities:
    """Urgency mapping functions."""

    def test_prefix_info(self):
        assert urgency_prefix(0.1) == ""

    def test_prefix_notable(self):
        assert urgency_prefix(0.4) == "▸ "

    def test_prefix_warning(self):
        assert urgency_prefix(0.7) == "⚠ "

    def test_prefix_critical(self):
        assert urgency_prefix(0.9) == "‼ "

    def test_prefix_boundary_030(self):
        assert urgency_prefix(0.3) == "▸ "

    def test_prefix_boundary_060(self):
        assert urgency_prefix(0.6) == "⚠ "

    def test_prefix_boundary_080(self):
        assert urgency_prefix(0.8) == "‼ "

    def test_bar_zero(self):
        bar = urgency_bar(0.0, width=10)
        assert "░░░░░░░░░░" in bar
        assert "0.00" in bar

    def test_bar_full(self):
        bar = urgency_bar(1.0, width=10)
        assert "██████████" in bar
        assert "1.00" in bar

    def test_bar_half(self):
        bar = urgency_bar(0.5, width=10)
        assert "█████" in bar
        assert "0.50" in bar

    def test_label_info(self):
        assert urgency_label(0.1) == "info"

    def test_label_notable(self):
        assert urgency_label(0.4) == "notable"

    def test_label_warning(self):
        assert urgency_label(0.7) == "warning"

    def test_label_critical(self):
        assert urgency_label(0.9) == "CRITICAL"


# ── Evidence Formatting ────────────────────────────────────────────────


class TestEvidenceFormatting:
    """Evidence dict → indented text."""

    def test_empty_evidence(self):
        assert _format_evidence({}) == ""

    def test_simple_evidence(self):
        result = _format_evidence({"status": "ok", "count": 5})
        assert "status: ok" in result
        assert "count: 5" in result

    def test_float_formatting(self):
        result = _format_evidence({"quality": -0.3456})
        assert "quality: -0.346" in result

    def test_custom_indent(self):
        result = _format_evidence({"x": 1}, indent=8)
        assert result.startswith("        ")


# ── Text Renderers ─────────────────────────────────────────────────────


class TestTextRenderers:
    """Each of the 7 visual type renderers."""

    def test_heatmap_contains_data_source(self):
        p = _make_panel(suggested_visual="heatmap", urgency=0.7)
        result = _render_heatmap_text(p)
        assert p.data_source in result
        assert "⚠" in result

    def test_heatmap_contains_bar(self):
        p = _make_panel(suggested_visual="heatmap", urgency=0.5)
        result = _render_heatmap_text(p)
        assert "█" in result
        assert "0.50" in result

    def test_tree_renders_evidence(self):
        p = _make_panel(suggested_visual="tree",
                        evidence={"alpha": 1, "beta": 2, "gamma": 3})
        result = _render_tree_text(p)
        assert "├─" in result
        assert "└─" in result
        assert "gamma" in result

    def test_tree_no_evidence(self):
        p = _make_panel(suggested_visual="tree", evidence={})
        result = _render_tree_text(p)
        assert "no data" in result

    def test_timeline_renders_events(self):
        p = _make_panel(suggested_visual="timeline",
                        evidence={"step1": "start", "step2": "navigate"})
        result = _render_timeline_text(p)
        assert "●" in result
        assert "◉" in result
        assert "step1" in result

    def test_timeline_empty(self):
        p = _make_panel(suggested_visual="timeline", evidence={})
        result = _render_timeline_text(p)
        assert "no events" in result

    def test_bar_contains_progress(self):
        p = _make_panel(suggested_visual="bar", urgency=0.6)
        result = _render_bar_text(p)
        assert "█" in result
        assert "0.60" in result

    def test_text_contains_label(self):
        p = _make_panel(suggested_visual="text", label="My Label")
        result = _render_text_text(p)
        assert "My Label" in result
        assert p.data_source in result

    def test_highlight_boxed(self):
        p = _make_panel(suggested_visual="highlight", urgency=0.8,
                        label="Critical Issue")
        result = _render_highlight_text(p)
        assert "┌" in result
        assert "└" in result
        assert "Critical Issue" in result
        assert "‼" in result

    def test_dashboard_renders_metrics(self):
        p = _make_panel(suggested_visual="dashboard",
                        evidence={"q": -0.5, "load": 12.0, "tau": 100})
        result = _render_dashboard_text(p)
        assert "q" in result
        assert "-0.500" in result
        assert "tau" in result

    def test_dashboard_empty(self):
        p = _make_panel(suggested_visual="dashboard", evidence={})
        result = _render_dashboard_text(p)
        assert "no metrics" in result

    def test_dashboard_limits_to_6(self):
        evidence = {f"key{i}": i for i in range(10)}
        p = _make_panel(suggested_visual="dashboard", evidence=evidence)
        result = _render_dashboard_text(p)
        assert "key5" in result
        assert "key6" not in result


# ── Dispatch ───────────────────────────────────────────────────────────


class TestTextDispatch:
    """Visual type dispatching to correct renderer."""

    def test_all_7_renderers_registered(self):
        expected = {"heatmap", "tree", "timeline", "bar",
                    "text", "highlight", "dashboard"}
        assert set(_TEXT_RENDERERS.keys()) == expected

    def test_dispatch_known_type(self):
        p = _make_panel(suggested_visual="heatmap")
        result = _render_visual_text(p)
        assert p.data_source in result

    def test_dispatch_unknown_type_falls_back_to_text(self):
        p = _make_panel(suggested_visual="sparkline", label="Fallback")
        result = _render_visual_text(p)
        assert "Fallback" in result


# ── Panel Rendering ────────────────────────────────────────────────────


class TestPanelRendering:
    """Full panel block rendering."""

    def test_panel_has_index(self):
        p = _make_panel()
        result = _render_panel_text(p, 0)
        assert "[1]" in result

    def test_panel_has_tags(self):
        p = _make_panel(intent="anomaly", perception="contrast")
        result = _render_panel_text(p, 0)
        assert "intent=anomaly" in result
        assert "perception=contrast" in result

    def test_panel_has_urgency_label(self):
        p = _make_panel(urgency=0.9)
        result = _render_panel_text(p, 0)
        assert "CRITICAL" in result

    def test_panel_has_evidence(self):
        p = _make_panel(evidence={"errors": 3})
        result = _render_panel_text(p, 0)
        assert "Evidence:" in result
        assert "errors: 3" in result

    def test_panel_no_evidence(self):
        p = _make_panel(evidence={})
        result = _render_panel_text(p, 0)
        assert "Evidence:" not in result


# ── Full Document: render_text ─────────────────────────────────────────


class TestRenderText:
    """Full text document assembly."""

    def test_has_title(self):
        spec = _make_spec()
        result = render_text(spec, title="My Title")
        assert "My Title" in result

    def test_has_layout_info(self):
        spec = _make_spec(layout="narrative")
        result = render_text(spec)
        assert "narrative" in result

    def test_has_panel_count(self):
        panels = [_make_panel(), _make_panel(label="Second")]
        spec = _make_spec(panels=panels)
        result = render_text(spec)
        assert "Panels: 2" in result

    def test_has_context(self):
        spec = _make_spec(context="Running domain X")
        result = render_text(spec)
        assert "Running domain X" in result

    def test_has_separator(self):
        spec = _make_spec()
        result = render_text(spec)
        assert "═" in result

    def test_multiple_panels(self):
        panels = [
            _make_panel(label="First", urgency=0.2),
            _make_panel(label="Second", urgency=0.7),
            _make_panel(label="Third", urgency=0.95),
        ]
        spec = _make_spec(panels=panels)
        result = render_text(spec)
        assert "[1]" in result
        assert "[2]" in result
        assert "[3]" in result
        assert "First" in result
        assert "Second" in result
        assert "Third" in result

    def test_empty_spec(self):
        spec = _make_spec(panels=[])
        result = render_text(spec)
        assert "Panels: 0" in result


# ── Markdown ───────────────────────────────────────────────────────────


class TestRenderMarkdown:
    """Markdown document output."""

    def test_has_h1_title(self):
        spec = _make_spec()
        result = render_markdown(spec, title="My Report")
        assert "# My Report" in result

    def test_has_h2_panels(self):
        spec = _make_spec(panels=[_make_panel(label="Panel A")])
        result = render_markdown(spec)
        assert "## " in result
        assert "Panel A" in result

    def test_has_code_block(self):
        spec = _make_spec()
        result = render_markdown(spec)
        assert "```" in result

    def test_has_urgency_badge(self):
        spec = _make_spec(panels=[_make_panel(urgency=0.9)])
        result = render_markdown(spec)
        assert "CRITICAL" in result

    def test_evidence_in_details(self):
        spec = _make_spec(panels=[_make_panel(evidence={"x": 1})])
        result = render_markdown(spec)
        assert "<details>" in result
        assert "```json" in result

    def test_no_evidence_no_details(self):
        spec = _make_spec(panels=[_make_panel(evidence={})])
        result = render_markdown(spec)
        assert "<details>" not in result


# ── File Output ────────────────────────────────────────────────────────


class TestRenderToFile:
    """File write + format selection."""

    def test_write_text_file(self, tmp_path):
        spec = _make_spec()
        out = render_to_text_file(spec, tmp_path / "output.txt")
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "E₀ Communication" in content

    def test_write_markdown_file(self, tmp_path):
        spec = _make_spec()
        out = render_to_text_file(spec, tmp_path / "output.md", fmt="markdown")
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "# E₀ Communication" in content

    def test_creates_directory(self, tmp_path):
        spec = _make_spec()
        out = render_to_text_file(spec, tmp_path / "sub" / "out.txt")
        assert out.exists()


# ── End-to-End ─────────────────────────────────────────────────────────


class TestEndToEnd:
    """UISpec from emitter → text output."""

    def test_emitter_to_text(self):
        """Create a realistic UISpec and render to text."""
        from e0_controller.communication import CommunicationIntent, IntentType, IntentReport
        from e0_controller.ui_emitter import emit_ui_spec

        intents = [
            CommunicationIntent(
                type=IntentType.UNCERTAINTY,
                urgency=0.7,
                subject="inscription_policy",
                summary="Inscription policy shows mixed signals",
                evidence={"quality": -0.3, "load": 15.2, "stability": 0.4},
            ),
            CommunicationIntent(
                type=IntentType.STATUS,
                urgency=0.2,
                subject="coverage",
                summary="Navigation coverage at 84.5%",
                evidence={"coverage": 0.845, "rounds": 4, "crossings": 322},
            ),
        ]
        report = IntentReport(intents=intents)
        spec = emit_ui_spec(report, context="C207 post-commit check")

        # Text render
        text = render_text(spec)
        assert "inscription_policy" in text or "Inscription" in text
        assert len(text) > 100

        # Markdown render
        md = render_markdown(spec)
        assert "# " in md
        assert len(md) > 100

    def test_all_visual_types_renderable(self):
        """Every suggested_visual produces output."""
        visuals = ["heatmap", "tree", "timeline", "bar",
                   "text", "highlight", "dashboard"]
        panels = [
            _make_panel(suggested_visual=v, label=f"Panel-{v}")
            for v in visuals
        ]
        spec = _make_spec(panels=panels)
        result = render_text(spec)
        for v in visuals:
            assert f"Panel-{v}" in result

    def test_high_urgency_emphasis(self):
        """Critical panels get emphasis markers."""
        panels = [
            _make_panel(urgency=0.05, label="Low"),
            _make_panel(urgency=0.95, label="High"),
        ]
        spec = _make_spec(panels=panels)
        result = render_text(spec)
        assert "‼" in result
        assert "CRITICAL" in result
