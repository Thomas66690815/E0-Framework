"""Tests for E₀ Interactive Text Session (C213 + C214 + C216).

Validates the REPL dispatch, session state management,
each command's output through the communication pipeline,
the C214 feedback loop (rate command + session-scoped perception),
and C216 transition detail (detail + inspect commands).
"""

from __future__ import annotations

import pytest

from e0_controller.interactive_session import (
    SessionState,
    _RATING_ACTION,
    _quality_bar,
    build_session,
    cmd_detail,
    cmd_focus,
    cmd_help,
    cmd_inspect,
    cmd_rate,
    cmd_run,
    cmd_status,
    cmd_summary,
    cmd_why,
    dispatch,
)
from e0_controller.feedback import HumanAction
from e0_controller.perception import PerceptionDomain


# ── Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def session():
    """Build a session once for all tests (landscape is expensive)."""
    return build_session(steps_per_round=20, output_format="text")


# ── Build Session ──────────────────────────────────────────────────────


class TestBuildSession:
    """Session construction."""

    def test_builds_session(self, session):
        assert isinstance(session, SessionState)
        assert session.round_num == 0
        assert session.stagnation_streak == 0
        assert len(session.history) == 0

    def test_has_landscape(self, session):
        assert session.landscape is not None
        assert session.stats["total_nodes"] > 100

    def test_has_three_domains(self, session):
        assert session.stats["canon_nodes"] > 0
        assert session.stats["bootstrap_nodes"] > 0
        assert session.stats["en_nodes"] > 0

    def test_default_format(self, session):
        assert session.output_format == "text"


# ── Dispatch ───────────────────────────────────────────────────────────


class TestDispatch:
    """Command parsing and routing."""

    def test_empty_input(self, session):
        assert dispatch(session, "") == ""
        assert dispatch(session, "   ") == ""

    def test_quit(self, session):
        s = build_session(steps_per_round=10)
        assert dispatch(s, "quit") is None
        assert dispatch(s, "exit") is None
        assert dispatch(s, "q") is None

    def test_help(self, session):
        result = dispatch(session, "help")
        assert "run" in result
        assert "status" in result
        assert "focus" in result

    def test_help_alias(self, session):
        result = dispatch(session, "?")
        assert "run" in result

    def test_unknown_command(self, session):
        result = dispatch(session, "foobar")
        assert "Unknown command" in result

    def test_run_invalid_count(self, session):
        s = build_session(steps_per_round=10)
        result = dispatch(s, "run abc")
        assert "Invalid count" in result

    def test_focus_no_arg(self, session):
        result = dispatch(session, "focus")
        assert "Usage" in result

    def test_focus_unknown_domain(self, session):
        result = dispatch(session, "focus xyz")
        assert "Unknown domain" in result


# ── Run Command ────────────────────────────────────────────────────────


class TestCmdRun:
    """Round execution."""

    def test_run_one_round(self):
        s = build_session(steps_per_round=15)
        result = cmd_run(s, 1)
        assert s.round_num == 1
        assert len(s.history) == 1
        assert "Round 1" in result
        assert "Interpretations" in result

    def test_run_multiple_rounds(self):
        s = build_session(steps_per_round=15)
        result = cmd_run(s, 3)
        assert s.round_num == 3
        assert len(s.history) == 3

    def test_run_accumulates(self):
        s = build_session(steps_per_round=15)
        cmd_run(s, 1)
        cmd_run(s, 2)
        assert s.round_num == 3
        assert len(s.history) == 3

    def test_coverage_increases(self):
        s = build_session(steps_per_round=20)
        cmd_run(s, 2)
        cov = s.history[-1].assessment_after.coverage
        assert cov > 0.0


# ── Status Command ─────────────────────────────────────────────────────


class TestCmdStatus:
    """Status overview."""

    def test_status_before_run(self):
        s = build_session(steps_per_round=10)
        result = cmd_status(s)
        assert "Status" in result or "E₀" in result
        assert "Interpretations" in result

    def test_status_after_run(self):
        s = build_session(steps_per_round=15)
        cmd_run(s, 1)
        result = cmd_status(s)
        assert "Round 1" in result or "%" in result

    def test_status_shows_domain_balance(self):
        s = build_session(steps_per_round=15)
        cmd_run(s, 1)
        result = cmd_status(s)
        assert "Canon" in result or "Bootstrap" in result or "EN" in result


# ── Focus Command ──────────────────────────────────────────────────────


class TestCmdFocus:
    """Domain zoom."""

    def test_focus_canon(self):
        s = build_session(steps_per_round=15)
        cmd_run(s, 1)
        result = cmd_focus(s, "canon")
        assert "Canon" in result
        assert "Interpretations" in result

    def test_focus_bootstrap(self):
        s = build_session(steps_per_round=15)
        cmd_run(s, 1)
        result = cmd_focus(s, "bootstrap")
        assert "Bootstrap" in result

    def test_focus_en(self):
        s = build_session(steps_per_round=15)
        cmd_run(s, 1)
        result = cmd_focus(s, "en")
        assert "EN" in result

    def test_focus_aliases(self):
        s = build_session(steps_per_round=15)
        cmd_run(s, 1)
        assert "Canon" in cmd_focus(s, "c")
        assert "Bootstrap" in cmd_focus(s, "boot")
        assert "EN" in cmd_focus(s, "english")

    def test_focus_case_insensitive(self):
        s = build_session(steps_per_round=15)
        cmd_run(s, 1)
        assert "Canon" in cmd_focus(s, "CANON")
        assert "EN" in cmd_focus(s, "En")

    def test_focus_unknown(self):
        s = build_session(steps_per_round=10)
        result = cmd_focus(s, "xyz")
        assert "Unknown domain" in result

    def test_focus_shows_unvisited(self):
        s = build_session(steps_per_round=10)
        # Before any run, all are unvisited
        result = cmd_focus(s, "canon")
        assert "unvisited" in result.lower() or "0/" in result


# ── Why Command ────────────────────────────────────────────────────────


class TestCmdWhy:
    """Decision explanation."""

    def test_why_no_history(self):
        s = build_session(steps_per_round=10)
        result = cmd_why(s)
        assert "No rounds" in result

    def test_why_after_run(self):
        s = build_session(steps_per_round=15)
        cmd_run(s, 1)
        result = cmd_why(s)
        assert "Round 1" in result
        assert "Mode:" in result
        assert "Reason:" in result
        assert "Coverage:" in result

    def test_why_shows_path(self):
        s = build_session(steps_per_round=15)
        cmd_run(s, 1)
        result = cmd_why(s)
        assert "Path:" in result

    def test_why_shows_next(self):
        s = build_session(steps_per_round=15)
        cmd_run(s, 1)
        result = cmd_why(s)
        assert "Next round" in result


# ── Summary Command ────────────────────────────────────────────────────


class TestCmdSummary:
    """Cycle summary."""

    def test_summary_no_history(self):
        s = build_session(steps_per_round=10)
        result = cmd_summary(s)
        assert "No rounds" in result

    def test_summary_after_rounds(self):
        s = build_session(steps_per_round=15)
        cmd_run(s, 2)
        result = cmd_summary(s)
        assert "Summary" in result
        assert "Interpretations" in result


# ── Help Command ───────────────────────────────────────────────────────


class TestCmdHelp:
    """Help text."""

    def test_help_lists_commands(self):
        result = cmd_help()
        for cmd in ("run", "status", "focus", "why", "detail", "inspect",
                     "rate", "summary", "help", "quit"):
            assert cmd in result


# ── Markdown Format ────────────────────────────────────────────────────


class TestMarkdownFormat:
    """Commands work with markdown output format."""

    def test_run_markdown(self):
        s = build_session(steps_per_round=15, output_format="markdown")
        result = cmd_run(s, 1)
        assert "# E₀" in result
        assert "## Interpretations" in result

    def test_status_markdown(self):
        s = build_session(steps_per_round=15, output_format="markdown")
        cmd_run(s, 1)
        result = cmd_status(s)
        assert "# E₀" in result

    def test_focus_markdown(self):
        s = build_session(steps_per_round=15, output_format="markdown")
        cmd_run(s, 1)
        result = cmd_focus(s, "canon")
        assert "# E₀ Focus" in result


# ── C214: Perception in Session ────────────────────────────────────────


class TestSessionPerception:
    """Session-scoped perception domain."""

    def test_session_has_perception(self):
        s = build_session(steps_per_round=10)
        assert s.perception is not None
        assert isinstance(s.perception, PerceptionDomain)

    def test_perception_has_primitives(self):
        s = build_session(steps_per_round=10)
        assert len(s.perception.primitives) >= 20

    def test_perception_is_session_scoped(self):
        """Two sessions get independent perception domains."""
        s1 = build_session(steps_per_round=10)
        s2 = build_session(steps_per_round=10)
        assert s1.perception is not s2.perception
        assert s1.perception.landscape is not s2.perception.landscape

    def test_last_spec_initially_none(self):
        s = build_session(steps_per_round=10)
        assert s.last_spec is None

    def test_status_sets_last_spec(self):
        s = build_session(steps_per_round=10)
        cmd_status(s)
        assert s.last_spec is not None
        assert len(s.last_spec.panels) > 0

    def test_focus_sets_last_spec(self):
        s = build_session(steps_per_round=15)
        cmd_run(s, 1)
        cmd_focus(s, "canon")
        assert s.last_spec is not None


# ── C214: Rate Command ─────────────────────────────────────────────────


class TestCmdRate:
    """Panel feedback via rate command."""

    def test_rate_no_output(self):
        s = build_session(steps_per_round=10)
        result = cmd_rate(s, 0, "helpful")
        assert "No output to rate" in result

    def test_rate_helpful(self):
        s = build_session(steps_per_round=10)
        cmd_status(s)
        result = cmd_rate(s, 0, "helpful")
        assert "Rated panel 0" in result
        assert "click" in result
        assert "success" in result

    def test_rate_not_helpful(self):
        s = build_session(steps_per_round=10)
        cmd_status(s)
        result = cmd_rate(s, 0, "not")
        assert "Rated panel 0" in result
        assert "dismiss" in result
        assert "failure" in result

    def test_rate_confused(self):
        s = build_session(steps_per_round=10)
        cmd_status(s)
        result = cmd_rate(s, 0, "confused")
        assert "confusion" in result
        assert "failure" in result

    def test_rate_shorthand_plus(self):
        s = build_session(steps_per_round=10)
        cmd_status(s)
        result = cmd_rate(s, 0, "+")
        assert "click" in result

    def test_rate_shorthand_minus(self):
        s = build_session(steps_per_round=10)
        cmd_status(s)
        result = cmd_rate(s, 0, "-")
        assert "dismiss" in result

    def test_rate_out_of_range(self):
        s = build_session(steps_per_round=10)
        cmd_status(s)
        result = cmd_rate(s, 999, "helpful")
        assert "out of range" in result

    def test_rate_negative_index(self):
        s = build_session(steps_per_round=10)
        cmd_status(s)
        result = cmd_rate(s, -1, "helpful")
        assert "out of range" in result

    def test_rate_unknown_rating(self):
        s = build_session(steps_per_round=10)
        cmd_status(s)
        result = cmd_rate(s, 0, "xyz")
        assert "Unknown rating" in result

    def test_rate_shows_perception_profile(self):
        s = build_session(steps_per_round=10)
        cmd_status(s)
        result = cmd_rate(s, 0, "helpful")
        assert "load=" in result
        assert "quality=" in result


# ── C214: Perception Learns from Feedback ──────────────────────────────


class TestPerceptionLearning:
    """Feedback changes perception trace_load and quality."""

    def test_helpful_increases_quality(self):
        s = build_session(steps_per_round=10)
        cmd_status(s)
        panel = s.last_spec.panels[0]
        prim = panel.perception
        profile_before = s.perception.profile(prim)

        cmd_rate(s, 0, "helpful")
        profile_after = s.perception.profile(prim)

        # Quality should increase or stay same (SUCCESS inscribed)
        assert profile_after.quality >= profile_before.quality

    def test_not_helpful_decreases_quality(self):
        s = build_session(steps_per_round=10)
        cmd_status(s)
        panel = s.last_spec.panels[0]
        prim = panel.perception
        profile_before = s.perception.profile(prim)

        cmd_rate(s, 0, "not")
        profile_after = s.perception.profile(prim)

        # quality should decrease or stay same (FAILURE inscribed)
        assert profile_after.quality <= profile_before.quality

    def test_repeated_feedback_accumulates(self):
        s = build_session(steps_per_round=10)
        cmd_status(s)
        panel = s.last_spec.panels[0]
        prim = panel.perception
        q_before = s.perception.profile(prim).quality

        for _ in range(3):
            cmd_rate(s, 0, "helpful")

        q_after = s.perception.profile(prim).quality
        assert q_after >= q_before

    def test_feedback_does_not_affect_other_session(self):
        """Perception is session-scoped — other sessions not affected."""
        s1 = build_session(steps_per_round=10)
        s2 = build_session(steps_per_round=10)

        cmd_status(s1)
        panel = s1.last_spec.panels[0]
        prim = panel.perception

        q2_before = s2.perception.profile(prim).quality
        cmd_rate(s1, 0, "helpful")
        cmd_rate(s1, 0, "helpful")
        cmd_rate(s1, 0, "helpful")

        q2_after = s2.perception.profile(prim).quality
        assert q2_before == q2_after


# ── C214: Rate via Dispatch ────────────────────────────────────────────


class TestRateDispatch:
    """Rate command through dispatch parser."""

    def test_dispatch_rate(self):
        s = build_session(steps_per_round=10)
        cmd_status(s)
        result = dispatch(s, "rate 0 helpful")
        assert "Rated panel 0" in result

    def test_dispatch_rate_no_args(self):
        s = build_session(steps_per_round=10)
        result = dispatch(s, "rate")
        assert "Usage" in result

    def test_dispatch_rate_missing_rating(self):
        s = build_session(steps_per_round=10)
        result = dispatch(s, "rate 0")
        assert "Usage" in result

    def test_dispatch_rate_invalid_index(self):
        s = build_session(steps_per_round=10)
        result = dispatch(s, "rate abc helpful")
        assert "Invalid panel index" in result

    def test_dispatch_rate_after_focus(self):
        s = build_session(steps_per_round=15)
        cmd_run(s, 1)
        dispatch(s, "focus canon")
        result = dispatch(s, "rate 0 +")
        assert "Rated" in result


# ── C214: Rating Map Coverage ──────────────────────────────────────────


class TestRatingMap:
    """All rating aliases map to the correct HumanAction."""

    def test_helpful_aliases(self):
        for alias in ("helpful", "yes", "good", "+"):
            assert _RATING_ACTION[alias] == HumanAction.CLICK

    def test_not_helpful_aliases(self):
        for alias in ("not", "no", "bad", "-"):
            assert _RATING_ACTION[alias] == HumanAction.DISMISS

    def test_confused_aliases(self):
        for alias in ("confused", "?"):
            assert _RATING_ACTION[alias] == HumanAction.CONFUSION


# ── C216: Quality Bar ──────────────────────────────────────────────────


class TestQualityBar:
    """ASCII quality indicator."""

    def test_positive_quality(self):
        bar = _quality_bar(1.0)
        assert "██████████" in bar

    def test_negative_quality(self):
        bar = _quality_bar(-1.0)
        assert "░░░░░░░░░░" in bar

    def test_zero_quality(self):
        bar = _quality_bar(0.0)
        assert "█████" in bar  # half filled
        assert "░░░░░" in bar

    def test_bar_has_brackets(self):
        bar = _quality_bar(0.5)
        assert bar.startswith("[")
        assert bar.endswith("]")


# ── C216: Detail Command ──────────────────────────────────────────────


class TestCmdDetail:
    """Transition-level detail view."""

    def test_detail_no_history(self):
        s = build_session(steps_per_round=10)
        result = cmd_detail(s)
        assert "No rounds" in result

    def test_detail_after_run(self):
        s = build_session(steps_per_round=15)
        cmd_run(s, 1)
        result = cmd_detail(s)
        assert "Round 1" in result
        assert "Transition Detail" in result
        assert "→" in result

    def test_detail_shows_quality(self):
        s = build_session(steps_per_round=15)
        cmd_run(s, 1)
        result = cmd_detail(s)
        assert "q=" in result

    def test_detail_shows_load(self):
        s = build_session(steps_per_round=15)
        cmd_run(s, 1)
        result = cmd_detail(s)
        assert "m=" in result

    def test_detail_shows_inertia(self):
        s = build_session(steps_per_round=15)
        cmd_run(s, 1)
        result = cmd_detail(s)
        assert "I=" in result

    def test_detail_shows_crossings(self):
        s = build_session(steps_per_round=15)
        cmd_run(s, 1)
        result = cmd_detail(s)
        assert "transitions" in result

    def test_detail_specific_round(self):
        s = build_session(steps_per_round=15)
        cmd_run(s, 3)
        result = cmd_detail(s, round_num=1)
        assert "Round 1" in result

    def test_detail_invalid_round(self):
        s = build_session(steps_per_round=15)
        cmd_run(s, 1)
        result = cmd_detail(s, round_num=99)
        assert "not found" in result

    def test_detail_quality_bar(self):
        s = build_session(steps_per_round=15)
        cmd_run(s, 1)
        result = cmd_detail(s)
        assert "[" in result  # quality bar brackets

    def test_detail_markdown(self):
        s = build_session(steps_per_round=15, output_format="markdown")
        cmd_run(s, 1)
        result = cmd_detail(s)
        assert "| #" in result  # markdown table header
        assert "Transition" in result


# ── C216: Inspect Command ─────────────────────────────────────────────


class TestCmdInspect:
    """Deep edge inspection."""

    def test_inspect_no_inscriptions(self):
        s = build_session(steps_per_round=10)
        result = cmd_inspect(s, "NONEXISTENT_A", "NONEXISTENT_B")
        assert "no inscriptions" in result

    def test_inspect_after_run(self):
        s = build_session(steps_per_round=15)
        cmd_run(s, 1)
        # Inspect first edge from path
        path = s.history[-1].path
        result = cmd_inspect(s, path[0], path[1])
        assert "Edge:" in result
        assert "trace_load" in result
        assert "quality" in result

    def test_inspect_shows_inertia(self):
        s = build_session(steps_per_round=15)
        cmd_run(s, 1)
        path = s.history[-1].path
        result = cmd_inspect(s, path[0], path[1])
        assert "inertia" in result

    def test_inspect_shows_domains(self):
        s = build_session(steps_per_round=15)
        cmd_run(s, 1)
        path = s.history[-1].path
        result = cmd_inspect(s, path[0], path[1])
        assert "Domains:" in result or "Domain" in result

    def test_inspect_shows_inscriptions(self):
        s = build_session(steps_per_round=15)
        cmd_run(s, 1)
        path = s.history[-1].path
        result = cmd_inspect(s, path[0], path[1])
        assert "Inscriptions:" in result

    def test_inspect_suggests_reverse(self):
        """When edge has no inscriptions but reverse does."""
        s = build_session(steps_per_round=15)
        cmd_run(s, 2)
        # Find an edge from path
        path = s.history[-1].path
        src, tgt = path[0], path[1]
        # Try reversed
        result = cmd_inspect(s, tgt, src)
        # Should either show data or suggest reverse
        assert "Edge:" in result or "Did you mean" in result

    def test_inspect_shows_recent_inscriptions(self):
        s = build_session(steps_per_round=20)
        cmd_run(s, 2)
        path = s.history[-1].path
        result = cmd_inspect(s, path[0], path[1])
        # Should show τ= entries if there are inscriptions
        if "Recent" in result:
            assert "τ=" in result


# ── C216: Detail + Inspect via Dispatch ────────────────────────────────


class TestDetailInspectDispatch:
    """Commands through dispatch parser."""

    def test_dispatch_detail(self):
        s = build_session(steps_per_round=15)
        cmd_run(s, 1)
        result = dispatch(s, "detail")
        assert "Round 1" in result

    def test_dispatch_detail_with_round(self):
        s = build_session(steps_per_round=15)
        cmd_run(s, 2)
        result = dispatch(s, "detail 1")
        assert "Round 1" in result

    def test_dispatch_detail_invalid(self):
        s = build_session(steps_per_round=15)
        cmd_run(s, 1)
        result = dispatch(s, "detail abc")
        assert "Invalid round number" in result

    def test_dispatch_inspect(self):
        s = build_session(steps_per_round=15)
        cmd_run(s, 1)
        path = s.history[-1].path
        result = dispatch(s, f"inspect {path[0]} {path[1]}")
        assert "Edge:" in result or "no inscriptions" in result

    def test_dispatch_inspect_no_args(self):
        s = build_session(steps_per_round=10)
        result = dispatch(s, "inspect")
        assert "Usage" in result

    def test_dispatch_inspect_one_arg(self):
        s = build_session(steps_per_round=10)
        result = dispatch(s, "inspect C:only_one")
        assert "Usage" in result
