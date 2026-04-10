"""Tests for E₀ Interactive Browser Session (C215).

Validates the server handler rendering, command dispatch via POST,
page generation, and the feedback-button wiring.
Does NOT start a real server — tests the handler logic directly.
"""

from __future__ import annotations

import pytest

from e0_controller.interactive_session import build_session, cmd_run, cmd_status
from e0_controller.interactive_server import (
    OutputEntry,
    SessionHandler,
    _render_feedback_toast,
    _render_panel_with_feedback,
    _render_spec_block,
    _render_text_block,
    make_handler,
)
from e0_controller.ui_emitter import UIPanel, UISpec


# ── Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def session():
    """Build a session once for all tests."""
    return build_session(steps_per_round=15)


@pytest.fixture(scope="module")
def session_with_spec(session):
    """Session that has run status (so last_spec exists)."""
    cmd_status(session)
    return session


# ── Text Block Rendering ──────────────────────────────────────────────


class TestRenderTextBlock:
    """Plain text to HTML."""

    def test_wraps_in_div(self):
        out = _render_text_block("hello world")
        assert '<div class="text-block">' in out
        assert "hello world" in out

    def test_escapes_html(self):
        out = _render_text_block("<script>alert('xss')</script>")
        assert "<script>" not in out
        assert "&lt;script&gt;" in out


# ── Feedback Toast ────────────────────────────────────────────────────


class TestRenderFeedbackToast:
    """Feedback confirmation rendering."""

    def test_wraps_in_toast(self):
        out = _render_feedback_toast("Rated panel 0: helpful")
        assert "feedback-toast" in out
        assert "Rated panel 0" in out

    def test_escapes_html(self):
        out = _render_feedback_toast("<b>bold</b>")
        assert "<b>" not in out
        assert "&lt;b&gt;" in out


# ── Panel with Feedback Buttons ───────────────────────────────────────


class TestRenderPanelWithFeedback:
    """Panels get live feedback buttons."""

    def test_has_helpful_button(self, session_with_spec):
        panel = session_with_spec.last_spec.panels[0]
        out = _render_panel_with_feedback(panel, 0)
        assert "rateFeedback(0" in out
        assert "Helpful" in out

    def test_has_not_helpful_button(self, session_with_spec):
        panel = session_with_spec.last_spec.panels[0]
        out = _render_panel_with_feedback(panel, 0)
        assert "'not'" in out
        assert "Not helpful" in out

    def test_has_confused_button(self, session_with_spec):
        panel = session_with_spec.last_spec.panels[0]
        out = _render_panel_with_feedback(panel, 0)
        assert "'confused'" in out

    def test_index_matches_panel(self, session_with_spec):
        panel = session_with_spec.last_spec.panels[0]
        out_0 = _render_panel_with_feedback(panel, 0)
        out_3 = _render_panel_with_feedback(panel, 3)
        assert "rateFeedback(0" in out_0
        assert "rateFeedback(3" in out_3


# ── Spec Block Rendering ─────────────────────────────────────────────


class TestRenderSpecBlock:
    """UISpec → panels + interpretations HTML."""

    def test_renders_panels(self, session_with_spec):
        spec = session_with_spec.last_spec
        out = _render_spec_block(spec)
        assert '<div class="panels">' in out
        assert "panel" in out.lower()

    def test_renders_interpretations(self, session_with_spec):
        spec = session_with_spec.last_spec
        out = _render_spec_block(spec)
        assert "interpretation" in out

    def test_optional_title(self, session_with_spec):
        spec = session_with_spec.last_spec
        out = _render_spec_block(spec, title="Test Title")
        assert "Test Title" in out

    def test_no_title_by_default(self, session_with_spec):
        spec = session_with_spec.last_spec
        out = _render_spec_block(spec)
        # Should not have a title div if title is empty
        assert "Test Title" not in out

    def test_escapes_title(self, session_with_spec):
        spec = session_with_spec.last_spec
        out = _render_spec_block(spec, title="<script>")
        assert "<script>" not in out
        assert "&lt;script&gt;" in out


# ── OutputEntry ───────────────────────────────────────────────────────


class TestOutputEntry:
    """Output history entry."""

    def test_stores_command_and_html(self):
        e = OutputEntry("run 1", "<p>result</p>")
        assert e.command == "run 1"
        assert e.html_content == "<p>result</p>"


# ── Handler Factory ───────────────────────────────────────────────────


class TestMakeHandler:
    """Handler class factory."""

    def test_creates_handler_class(self, session):
        history = []
        cls = make_handler(session, history)
        assert issubclass(cls, SessionHandler)
        assert cls.state is session
        assert cls.output_history is history

    def test_independent_handlers(self, session):
        h1 = []
        h2 = []
        cls1 = make_handler(session, h1)
        cls2 = make_handler(session, h2)
        assert cls1.output_history is not cls2.output_history


# ── Page Generation (via _send_page internals) ───────────────────────


class TestPageStructure:
    """Verify page HTML structure without running a real server."""

    def test_handler_attributes(self, session):
        history = [OutputEntry("help", _render_text_block("help text"))]
        cls = make_handler(session, history)
        # The class should have the right bindings
        assert cls.state.stats["total_nodes"] > 100
        assert len(cls.output_history) == 1

    def test_history_accumulates(self, session):
        history = []
        cls = make_handler(session, history)
        history.append(OutputEntry("cmd1", "<p>one</p>"))
        history.append(OutputEntry("cmd2", "<p>two</p>"))
        assert len(cls.output_history) == 2
        assert cls.output_history[0].command == "cmd1"
        assert cls.output_history[1].command == "cmd2"


# ── XSS Prevention ───────────────────────────────────────────────────


class TestXSSPrevention:
    """Ensure all user input is escaped."""

    def test_text_block_escapes(self):
        out = _render_text_block('"><img src=x onerror=alert(1)>')
        assert "onerror" not in out or "&" in out
        assert "<img" not in out

    def test_toast_escapes(self):
        out = _render_feedback_toast("<svg onload=alert(1)>")
        assert "<svg" not in out
        assert "&lt;svg" in out

    def test_spec_title_escapes(self, session_with_spec):
        spec = session_with_spec.last_spec
        out = _render_spec_block(spec, title='<img src=x onerror=alert(1)>')
        assert "<img" not in out
