"""
Tests for C210: Session Text Mode.

run_session() gains output_format param ("html"|"text"|"markdown").
E0SessionResult carries output_format, output_path, text_output.
Evidence interpretation wired into text/markdown output.
CLI --format flag.

Test structure:
    TestE0SessionResultFormat    — dataclass format fields
    TestRunSessionTextFormat     — run_session(output_format="text")
    TestRunSessionMarkdownFormat — run_session(output_format="markdown")
    TestRunSessionHtmlDefault    — backward compatibility
    TestFormatDispatch           — rendering dispatch logic
    TestCLIFormatArg             — --format argument parsing
    TestInterpretationWiring     — evidence interpretation in output
"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch

from e0_controller.e0_session import (
    run_session,
    E0SessionResult,
    DEFAULT_TASK,
    DEFAULT_START,
    DEFAULT_GOAL,
)
from e0_controller.communication import IntentReport
from e0_controller.ui_emitter import UISpec, UIPanel


def _make_result(**overrides) -> E0SessionResult:
    """Factory for test results."""
    defaults = dict(
        session_id="test-session",
        task="test task",
        iterations=3,
        stop_reason="converged",
        goal_reached=True,
        intent_report=IntentReport(intents=[]),
        ui_spec=UISpec(
            panels=[],
            layout="dashboard",
            generated_at="2026-04-10T12:00:00Z",
            context="test",
        ),
        output_path=Path("test.html"),
        output_format="html",
        perception_saved=Path("memos/perception_pretrained.json"),
        resumed=False,
        text_output=None,
    )
    defaults.update(overrides)
    return E0SessionResult(**defaults)


# ── E0SessionResult Format Fields ──────────────────────────────────────


class TestE0SessionResultFormat:
    """Dataclass format fields."""

    def test_output_format_in_result(self):
        r = _make_result(output_format="text")
        assert r.output_format == "text"

    def test_output_path_in_result(self):
        r = _make_result(output_path=Path("out.txt"))
        assert r.output_path == Path("out.txt")

    def test_text_output_in_result(self):
        r = _make_result(text_output="Hello E₀", output_format="text")
        assert r.text_output == "Hello E₀"

    def test_html_path_compat_html(self):
        """html_path property returns output_path for html format."""
        r = _make_result(output_format="html", output_path=Path("x.html"))
        assert r.html_path == Path("x.html")

    def test_html_path_compat_text(self):
        """html_path property returns None for non-html formats."""
        r = _make_result(output_format="text", output_path=Path("x.txt"))
        assert r.html_path is None

    def test_summary_includes_format(self):
        r = _make_result(output_format="markdown")
        s = r.summary()
        assert "Format: markdown" in s

    def test_summary_includes_output(self):
        r = _make_result(output_path=Path("out.md"))
        s = r.summary()
        assert "Output:" in s


# ── Run Session: Text Format ──────────────────────────────────────────


class TestRunSessionTextFormat:
    """run_session(output_format='text')."""

    def test_text_format_produces_txt_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = run_session(
            task=DEFAULT_TASK,
            start=DEFAULT_START,
            goal=DEFAULT_GOAL,
            session_id="test-text",
            use_mock=True,
            open_browser=False,
            max_iterations=1,
            output_format="text",
        )
        assert result.output_format == "text"
        assert result.output_path is not None
        assert result.output_path.exists()
        assert str(result.output_path).endswith(".txt")

    def test_text_format_has_text_output(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = run_session(
            task=DEFAULT_TASK,
            start=DEFAULT_START,
            goal=DEFAULT_GOAL,
            session_id="test-text2",
            use_mock=True,
            open_browser=False,
            max_iterations=1,
            output_format="text",
        )
        assert result.text_output is not None
        assert len(result.text_output) > 50
        assert "═" in result.text_output

    def test_text_format_contains_interpretation(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = run_session(
            task=DEFAULT_TASK,
            start=DEFAULT_START,
            goal=DEFAULT_GOAL,
            session_id="test-text3",
            use_mock=True,
            open_browser=False,
            max_iterations=1,
            output_format="text",
        )
        # Interpretation section appended
        assert "Interpretations" in result.text_output


# ── Run Session: Markdown Format ──────────────────────────────────────


class TestRunSessionMarkdownFormat:
    """run_session(output_format='markdown')."""

    def test_markdown_format_produces_md_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = run_session(
            task=DEFAULT_TASK,
            start=DEFAULT_START,
            goal=DEFAULT_GOAL,
            session_id="test-md",
            use_mock=True,
            open_browser=False,
            max_iterations=1,
            output_format="markdown",
        )
        assert result.output_format == "markdown"
        assert result.output_path is not None
        assert result.output_path.exists()
        assert str(result.output_path).endswith(".md")

    def test_markdown_has_text_output(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = run_session(
            task=DEFAULT_TASK,
            start=DEFAULT_START,
            goal=DEFAULT_GOAL,
            session_id="test-md2",
            use_mock=True,
            open_browser=False,
            max_iterations=1,
            output_format="markdown",
        )
        assert result.text_output is not None
        assert "# " in result.text_output

    def test_markdown_contains_interpretations(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = run_session(
            task=DEFAULT_TASK,
            start=DEFAULT_START,
            goal=DEFAULT_GOAL,
            session_id="test-md3",
            use_mock=True,
            open_browser=False,
            max_iterations=1,
            output_format="markdown",
        )
        assert "## Interpretations" in result.text_output


# ── Run Session: HTML Default ─────────────────────────────────────────


class TestRunSessionHtmlDefault:
    """Backward compatibility: default format is html."""

    def test_default_format_is_html(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = run_session(
            task=DEFAULT_TASK,
            start=DEFAULT_START,
            goal=DEFAULT_GOAL,
            session_id="test-html",
            use_mock=True,
            open_browser=False,
            max_iterations=1,
        )
        assert result.output_format == "html"
        assert result.output_path is not None
        assert str(result.output_path).endswith(".html")

    def test_html_no_text_output(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = run_session(
            task=DEFAULT_TASK,
            start=DEFAULT_START,
            goal=DEFAULT_GOAL,
            session_id="test-html2",
            use_mock=True,
            open_browser=False,
            max_iterations=1,
            output_format="html",
        )
        assert result.text_output is None

    def test_html_path_compat(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = run_session(
            task=DEFAULT_TASK,
            start=DEFAULT_START,
            goal=DEFAULT_GOAL,
            session_id="test-html3",
            use_mock=True,
            open_browser=False,
            max_iterations=1,
        )
        assert result.html_path == result.output_path


# ── Format Dispatch ───────────────────────────────────────────────────


class TestFormatDispatch:
    """Correct renderer is called for each format."""

    def test_text_does_not_open_browser(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        opened = []
        with patch("e0_controller.e0_session.render_and_open",
                    side_effect=lambda *a, **kw: opened.append(True)):
            run_session(
                task=DEFAULT_TASK,
                start=DEFAULT_START,
                goal=DEFAULT_GOAL,
                session_id="test-no-browser",
                use_mock=True,
                open_browser=True,  # would trigger browser for html
                max_iterations=1,
                output_format="text",
            )
        assert not opened

    def test_all_three_formats_work(self, tmp_path, monkeypatch):
        """Each format produces a result without error."""
        monkeypatch.chdir(tmp_path)
        for fmt in ("html", "text", "markdown"):
            result = run_session(
                task=DEFAULT_TASK,
                start=DEFAULT_START,
                goal=DEFAULT_GOAL,
                session_id=f"test-{fmt}",
                use_mock=True,
                open_browser=False,
                max_iterations=1,
                output_format=fmt,
            )
            assert result.output_path is not None
            assert result.output_path.exists()
            assert result.output_format == fmt


# ── CLI --format Argument ─────────────────────────────────────────────


class TestCLIFormatArg:
    """--format argument parsing in main()."""

    def test_cli_parses_format_text(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        calls = []
        original_run = run_session

        def capture_run(**kwargs):
            calls.append(kwargs)
            return original_run(**kwargs)

        monkeypatch.setattr("e0_controller.e0_session.run_session", capture_run)
        import sys
        monkeypatch.setattr(sys, "argv",
                            ["e0_session", "--mock", "--no-browser", "--format", "text"])

        from e0_controller.e0_session import main
        main()

        assert len(calls) == 1
        assert calls[0]["output_format"] == "text"

    def test_cli_parses_format_md(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        calls = []
        original_run = run_session

        def capture_run(**kwargs):
            calls.append(kwargs)
            return original_run(**kwargs)

        monkeypatch.setattr("e0_controller.e0_session.run_session", capture_run)
        import sys
        monkeypatch.setattr(sys, "argv",
                            ["e0_session", "--mock", "--no-browser", "--format", "md"])

        from e0_controller.e0_session import main
        main()

        assert len(calls) == 1
        assert calls[0]["output_format"] == "markdown"

    def test_cli_default_format_html(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        calls = []
        original_run = run_session

        def capture_run(**kwargs):
            calls.append(kwargs)
            return original_run(**kwargs)

        monkeypatch.setattr("e0_controller.e0_session.run_session", capture_run)
        import sys
        monkeypatch.setattr(sys, "argv", ["e0_session", "--mock", "--no-browser"])

        from e0_controller.e0_session import main
        main()

        assert len(calls) == 1
        assert calls[0]["output_format"] == "html"


# ── Interpretation Wiring ─────────────────────────────────────────────


class TestInterpretationWiring:
    """Evidence interpretation appears in text/markdown output."""

    def test_text_has_per_panel_interpretation(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = run_session(
            task=DEFAULT_TASK,
            start=DEFAULT_START,
            goal=DEFAULT_GOAL,
            session_id="test-interp",
            use_mock=True,
            open_browser=False,
            max_iterations=1,
            output_format="text",
        )
        # Each panel should generate some interpretation prose
        assert result.text_output is not None
        # At least one intent/perception tag should appear
        assert any(
            tag in result.text_output
            for tag in ["Intent:", "urgency", "perception"]
        )

    def test_markdown_has_interpretation_section(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = run_session(
            task=DEFAULT_TASK,
            start=DEFAULT_START,
            goal=DEFAULT_GOAL,
            session_id="test-interp-md",
            use_mock=True,
            open_browser=False,
            max_iterations=1,
            output_format="markdown",
        )
        assert "## Interpretations" in result.text_output
        # Should have per-panel H3 headers
        assert "### " in result.text_output
