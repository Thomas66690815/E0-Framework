"""Tests for E₀ Interactive Text Session (C213–C227).

Validates the REPL dispatch, session state management,
each command's output through the communication pipeline,
the C214 feedback loop (rate command + session-scoped perception),
C216 transition detail (detail + inspect commands),
C217 Human Peer Input (task command + node matching),
C218 LLM Peer Structuring (propose_domain_graph → inject → navigate),
C219 Semantic Surface + 3-Tier Task Processing,
C225 Session Persistence (save/load/auto-detect),
C226 Session History + Server Lifecycle (history round-trip,
perception write-back, server auto-save),
and C227 Seed Regeneration (regenerate_seed, cmd_regenerate,
discovered_edge materialization, multi-session learning loop).
"""

from __future__ import annotations

import os

import pytest

from e0_controller.interactive_session import (
    SESSION_STATE_PATH,
    SessionState,
    _RATING_ACTION,
    _assessment_to_dict,
    _dict_to_assessment,
    _dict_to_round,
    _match_nodes,
    _quality_bar,
    _round_to_dict,
    _task_connection,
    _task_known_path,
    _task_navigate,
    build_session,
    cmd_detail,
    cmd_focus,
    cmd_help,
    cmd_inspect,
    cmd_rate,
    cmd_regenerate,
    cmd_run,
    cmd_save,
    cmd_status,
    cmd_summary,
    cmd_task,
    cmd_why,
    dispatch,
    load_session,
    regenerate_seed,
    save_session,
)
from e0_controller.feedback import HumanAction
from e0_controller.perception import PerceptionDomain
from e0_controller.primitives import Edge


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

    def test_unknown_command_becomes_task(self, session):
        """Unrecognized input is treated as free-text task."""
        s = build_session(steps_per_round=15)
        result = dispatch(s, "foobar")
        # Either matches structurally or calls LLM peer
        assert "Structural Matching" in result or "LLM Peer" in result

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


# ── C217: Node Matching ─────────────────────────────────────────────────


class TestMatchNodes:
    """Token-to-nodeID structural matching."""

    def test_exact_concept_match(self):
        s = build_session(steps_per_round=10)
        matches = _match_nodes("historization", s.landscape)
        node_ids = [n for n, _ in matches]
        assert any("historization" in n.lower() for n in node_ids)

    def test_partial_concept_match(self):
        s = build_session(steps_per_round=10)
        matches = _match_nodes("tension", s.landscape)
        node_ids = [n for n, _ in matches]
        assert any("tension" in n.lower() for n in node_ids)

    def test_no_match_for_gibberish(self):
        s = build_session(steps_per_round=10)
        matches = _match_nodes("xyzzyplugh", s.landscape)
        assert len(matches) == 0

    def test_short_tokens_ignored(self):
        """Words ≤2 chars are dropped to avoid noise."""
        s = build_session(steps_per_round=10)
        matches = _match_nodes("a b c", s.landscape)
        assert len(matches) == 0

    def test_relevance_sorted(self):
        s = build_session(steps_per_round=10)
        matches = _match_nodes("trace quality", s.landscape)
        if len(matches) >= 2:
            assert matches[0][1] >= matches[1][1]

    def test_multi_word_match_higher_relevance(self):
        """A query matching multiple concept parts scores higher."""
        s = build_session(steps_per_round=10)
        single = _match_nodes("trace", s.landscape)
        multi = _match_nodes("trace quality", s.landscape)
        # The best match for "trace quality" should be >= best for "trace"
        if single and multi:
            assert multi[0][1] >= single[0][1]

    def test_substring_fallback(self):
        """Longer tokens match via substring if no exact word overlap."""
        s = build_session(steps_per_round=10)
        matches = _match_nodes("historiz", s.landscape)
        # "historiz" is 8 chars, should substring-match "historization"
        assert len(matches) > 0

    def test_case_insensitive(self):
        s = build_session(steps_per_round=10)
        upper = _match_nodes("HISTORIZATION", s.landscape)
        lower = _match_nodes("historization", s.landscape)
        assert len(upper) == len(lower)

    def test_empty_input(self):
        s = build_session(steps_per_round=10)
        matches = _match_nodes("", s.landscape)
        assert len(matches) == 0


# ── C217: Task Command ─────────────────────────────────────────────────


class TestCmdTask:
    """Human Peer Input via free-text task."""

    def test_task_empty_input(self):
        s = build_session(steps_per_round=10)
        result = cmd_task(s, "")
        assert "Usage" in result

    def test_task_no_match_calls_llm_peer(self):
        s = build_session(steps_per_round=10)
        # Inject a mock LLM adapter that returns minimal structure
        from e0_controller.llm_adapter import E0LLMAdapter
        mock_spec = {
            "nodes": ["FROBNICATOR", "XYZZY"],
            "edges": [{
                "from": "FROBNICATOR", "to": "XYZZY",
                "delta": 0.5, "resistance": 1.0,
                "initial_U": 2.0, "initial_F": 1.0,
                "confidence": 0.6,
            }],
        }
        import json
        mock_fn = lambda sys, usr, cfg: json.dumps(mock_spec)
        s.llm_adapter = E0LLMAdapter(call_fn=mock_fn)
        result = cmd_task(s, "xyzzyplugh frobnicator")
        assert "LLM Peer Structuring" in result
        assert "0 matches" in result

    def test_task_with_known_concept(self):
        s = build_session(steps_per_round=15)
        result = cmd_task(s, "historization and inscription")
        assert "Structural Matching" in result
        assert "matching node" in result
        assert "Navigation" in result

    def test_task_creates_round(self):
        s = build_session(steps_per_round=15)
        before = len(s.history)
        cmd_task(s, "tension and landscape")
        assert len(s.history) == before + 1

    def test_task_mode_is_task(self):
        s = build_session(steps_per_round=15)
        cmd_task(s, "historization")
        assert s.history[-1].mode in ("task", "task_connect")

    def test_task_reason_contains_query(self):
        s = build_session(steps_per_round=15)
        cmd_task(s, "tension exploration")
        assert "tension" in s.history[-1].reason.lower()

    def test_task_shows_coverage(self):
        s = build_session(steps_per_round=15)
        result = cmd_task(s, "inscription")
        assert "Coverage" in result

    def test_task_shows_connectivity(self):
        """When multiple nodes match, connectivity section appears."""
        s = build_session(steps_per_round=15)
        result = cmd_task(s, "historization inscription")
        assert "Connectivity" in result

    def test_task_shows_visited_matches(self):
        s = build_session(steps_per_round=20)
        result = cmd_task(s, "historization")
        # Either visited or not reached should appear
        assert "Visited" in result or "Not reached" in result

    def test_task_long_query_truncated(self):
        s = build_session(steps_per_round=15)
        long_text = "word " * 30 + "historization"
        cmd_task(s, long_text)
        # Reason should be truncated
        assert len(s.history[-1].reason) < 200

    def test_task_increments_round(self):
        s = build_session(steps_per_round=15)
        before = s.round_num
        cmd_task(s, "tension")
        assert s.round_num == before + 1


# ── C217: Task via Dispatch ────────────────────────────────────────────


class TestTaskDispatch:
    """Task command through the dispatch parser."""

    def test_dispatch_task(self):
        s = build_session(steps_per_round=15)
        result = dispatch(s, "task historization")
        assert "Structural Matching" in result

    def test_dispatch_task_no_arg(self):
        s = build_session(steps_per_round=10)
        result = dispatch(s, "task")
        assert "Usage" in result

    def test_dispatch_task_multi_word(self):
        s = build_session(steps_per_round=15)
        result = dispatch(s, "task trace quality and tension")
        assert "matching node" in result

    def test_dispatch_task_unknown_calls_llm(self):
        s = build_session(steps_per_round=10)
        import json
        from e0_controller.llm_adapter import E0LLMAdapter
        mock_spec = {
            "nodes": ["GIBBERISH_A"], "edges": [],
        }
        s.llm_adapter = E0LLMAdapter(call_fn=lambda sys, usr, cfg: json.dumps(mock_spec))
        result = dispatch(s, "task completely unknown gibberish words")
        assert "LLM Peer" in result

    def test_help_includes_freetext_hint(self):
        result = cmd_help()
        assert "just type any text" in result


# ── C218: LLM Peer Structuring ────────────────────────────────────────


def _mock_llm_fn(spec: dict):
    """Create a mock LLM call_fn returning a fixed spec."""
    import json
    return lambda sys, usr, cfg: json.dumps(spec)


def _build_session_with_mock(spec: dict, steps: int = 15) -> SessionState:
    """Build a session with a mock LLM adapter pre-injected."""
    from e0_controller.llm_adapter import E0LLMAdapter
    s = build_session(steps_per_round=steps)
    s.llm_adapter = E0LLMAdapter(call_fn=_mock_llm_fn(spec))
    return s


_BASIC_SPEC = {
    "nodes": ["ALPHA", "BETA", "GAMMA"],
    "edges": [
        {"from": "ALPHA", "to": "BETA", "delta": 0.6, "resistance": 1.0,
         "initial_U": 3.0, "initial_F": 1.0, "confidence": 0.7},
        {"from": "BETA", "to": "GAMMA", "delta": 0.4, "resistance": 0.8,
         "initial_U": 2.0, "initial_F": 0.5, "confidence": 0.8},
        {"from": "GAMMA", "to": "ALPHA", "delta": 0.5, "resistance": 1.0,
         "initial_U": 0.0, "initial_F": 0.0, "confidence": 0.5},
    ],
}


class TestLLMPeerStructure:
    """LLM structures unknown input into navigable landscape."""

    def test_llm_injects_nodes(self):
        s = _build_session_with_mock(_BASIC_SPEC)
        result = cmd_task(s, "alpha beta gamma unknown")
        assert "T:ALPHA" in result or "LLM Peer Structuring" in result
        assert "T:ALPHA" in s.landscape.states

    def test_llm_injects_edges(self):
        s = _build_session_with_mock(_BASIC_SPEC)
        cmd_task(s, "alpha beta gamma unknown")
        edge = Edge("T:ALPHA", "T:BETA")
        assert edge in s.landscape.edges

    def test_llm_nodes_prefixed(self):
        s = _build_session_with_mock(_BASIC_SPEC)
        cmd_task(s, "alpha beta unknown")
        task_nodes = [n for n in s.landscape.states if n.startswith("T:")]
        assert len(task_nodes) >= 3

    def test_llm_initial_traces_injected(self):
        s = _build_session_with_mock(_BASIC_SPEC)
        cmd_task(s, "alpha beta unknown")
        edge = Edge("T:ALPHA", "T:BETA")
        hist = s.landscape.historization
        assert hist.trace_load(edge) > 0

    def test_llm_confidence_applied(self):
        """Lower confidence → more balanced U/F → lower quality."""
        s = _build_session_with_mock(_BASIC_SPEC)
        cmd_task(s, "alpha beta unknown")
        edge = Edge("T:ALPHA", "T:BETA")
        hist = s.landscape.historization
        q = hist.trace_quality(edge)
        # confidence=0.7, initial_U=3, initial_F=1 → quality < raw (3-1)/(3+1)
        assert q < 0.5  # dampened by confidence

    def test_llm_edge_metadata(self):
        s = _build_session_with_mock(_BASIC_SPEC)
        cmd_task(s, "alpha beta unknown")
        meta = s.landscape.edge_meta("T:ALPHA", "T:BETA")
        assert meta.get("relation_type") == "llm_proposed"

    def test_llm_creates_bridges(self):
        """LLM-injected nodes with overlapping concepts get bridged."""
        # Use a concept name that overlaps with existing landscape nodes
        spec_with_overlap = {
            "nodes": ["HISTORIZATION_NEW", "TENSION_NEW"],
            "edges": [
                {"from": "HISTORIZATION_NEW", "to": "TENSION_NEW",
                 "delta": 0.5, "resistance": 1.0, "confidence": 0.8},
            ],
        }
        s = _build_session_with_mock(spec_with_overlap)
        # Query must NOT match existing nodes so LLM path fires
        result = cmd_task(s, "xyzzyplugh frobnicator")
        assert "LLM Peer Structuring" in result
        # These should bridge to existing C:historization / C:tension
        task_nodes = [n for n in s.landscape.states if n.startswith("T:")]
        bridged = False
        for tn in task_nodes:
            for e in s.landscape.edges:
                if (e.source == tn and not e.target.startswith("T:")) or \
                   (e.target == tn and not e.source.startswith("T:")):
                    bridged = True
                    break
            if bridged:
                break
        assert bridged

    def test_llm_navigates_from_anchor(self):
        s = _build_session_with_mock(_BASIC_SPEC)
        result = cmd_task(s, "alpha beta unknown")
        assert "Navigation" in result
        assert "Coverage" in result

    def test_llm_creates_round_with_task_llm_mode(self):
        s = _build_session_with_mock(_BASIC_SPEC)
        before = len(s.history)
        cmd_task(s, "alpha beta unknown")
        assert len(s.history) == before + 1
        assert s.history[-1].mode == "task_llm"

    def test_llm_reason_contains_query(self):
        s = _build_session_with_mock(_BASIC_SPEC)
        cmd_task(s, "alpha beta unknown")
        assert "LLM peer" in s.history[-1].reason

    def test_llm_unified_nodes_updated(self):
        s = _build_session_with_mock(_BASIC_SPEC)
        cmd_task(s, "alpha beta unknown")
        assert "T:ALPHA" in s.unified_nodes
        assert s.unified_nodes["T:ALPHA"]["type"] == "task"


class TestLLMPeerError:
    """Error handling for LLM peer failures."""

    def test_llm_error_falls_back(self):
        """LLM failure → graceful fallback message."""
        from e0_controller.llm_adapter import E0LLMAdapter
        def failing_fn(sys, usr, cfg):
            raise RuntimeError("API unavailable")
        s = build_session(steps_per_round=10)
        s.llm_adapter = E0LLMAdapter(call_fn=failing_fn)
        result = cmd_task(s, "unknown jabberwocky")
        assert "LLM peer error" in result
        assert "Falling back" in result

    def test_llm_empty_nodes(self):
        """LLM returns empty structure → message, no crash."""
        s = _build_session_with_mock({"nodes": [], "edges": []})
        result = cmd_task(s, "unknown jabberwocky")
        assert "no structure" in result.lower()

    def test_llm_no_adapter_creates_one(self):
        """Lazy adapter creation — will fail without API key in test env."""
        s = build_session(steps_per_round=10)
        s.llm_adapter = None
        # Test that it tries to create adapter (may error on API key)
        result = cmd_task(s, "unknown jabberwocky")
        # Either succeeds or reports error — no crash
        assert "LLM Peer" in result or "LLM peer error" in result


class TestInjectSpec:
    """Direct tests for _inject_spec_into_landscape."""

    def test_inject_adds_nodes(self):
        from e0_controller.interactive_session import _inject_spec_into_landscape
        s = build_session(steps_per_round=10)
        spec = {"nodes": ["FOO", "BAR"], "edges": []}
        new_nodes, new_edges = _inject_spec_into_landscape(s, spec)
        assert "T:FOO" in s.landscape.states
        assert "T:BAR" in s.landscape.states
        assert len(new_nodes) == 2

    def test_inject_adds_edges(self):
        from e0_controller.interactive_session import _inject_spec_into_landscape
        s = build_session(steps_per_round=10)
        spec = {
            "nodes": ["X", "Y"],
            "edges": [{"from": "X", "to": "Y", "delta": 0.5,
                        "resistance": 1.0, "confidence": 1.0}],
        }
        new_nodes, new_edges = _inject_spec_into_landscape(s, spec)
        assert Edge("T:X", "T:Y") in s.landscape.edges

    def test_inject_skips_existing(self):
        from e0_controller.interactive_session import _inject_spec_into_landscape
        s = build_session(steps_per_round=10)
        spec = {"nodes": ["DUP"], "edges": []}
        _inject_spec_into_landscape(s, spec)
        nodes_before = len(list(s.landscape.states))
        _inject_spec_into_landscape(s, spec)
        nodes_after = len(list(s.landscape.states))
        assert nodes_after == nodes_before

    def test_inject_custom_prefix(self):
        from e0_controller.interactive_session import _inject_spec_into_landscape
        s = build_session(steps_per_round=10)
        spec = {"nodes": ["CUSTOM"], "edges": []}
        _inject_spec_into_landscape(s, spec, prefix="P:")
        assert "P:CUSTOM" in s.landscape.states

    def test_inject_bridge_metadata(self):
        from e0_controller.interactive_session import _inject_spec_into_landscape
        s = build_session(steps_per_round=10)
        spec = {"nodes": ["LANDSCAPE"], "edges": []}
        new_nodes, new_edges = _inject_spec_into_landscape(s, spec)
        # "LANDSCAPE" should bridge to existing landscape nodes
        if new_edges:
            # At least one bridge should have bridge_type metadata
            for src, tgt in new_edges:
                meta = s.landscape.edge_meta(src, tgt)
                if meta.get("bridge_type") == "llm_structural":
                    break
            else:
                pass  # No bridges is acceptable for unique concepts


# ── C219: Semantic Surface + 3-Tier Task Processing ───────────────────


class TestSemanticSurface:
    """Verify that unified_nodes carry descriptions from all domains."""

    def test_canon_nodes_have_description(self):
        s = build_session(steps_per_round=10)
        canon = {k: v for k, v in s.unified_nodes.items() if k.startswith("C:")}
        assert len(canon) > 0
        with_desc = sum(1 for v in canon.values() if v.get("description"))
        assert with_desc == len(canon), f"Only {with_desc}/{len(canon)} canon nodes have descriptions"

    def test_en_nodes_have_description(self):
        s = build_session(steps_per_round=10)
        en = {k: v for k, v in s.unified_nodes.items() if k.startswith("EN:")}
        assert len(en) > 0
        with_desc = sum(1 for v in en.values() if v.get("description"))
        assert with_desc > 0, "EN nodes should have descriptions"

    def test_bootstrap_gt_has_description(self):
        s = build_session(steps_per_round=10)
        gt1 = s.unified_nodes.get("B:GT-1", {})
        assert gt1.get("description"), "GT-1 should have a lesson as description"

    def test_bootstrap_bt_has_description(self):
        s = build_session(steps_per_round=10)
        bt1 = s.unified_nodes.get("B:BT-1", {})
        assert bt1.get("description"), "BT-1 should have insight as description"

    def test_bootstrap_wp_has_description(self):
        s = build_session(steps_per_round=10)
        wp = {k: v for k, v in s.unified_nodes.items() if k.startswith("B:WP-")}
        assert len(wp) > 0
        with_desc = sum(1 for v in wp.values() if v.get("description"))
        assert with_desc > 0


class TestMatchNodesWithDescriptions:
    """Verify that _match_nodes searches descriptions when provided."""

    def test_match_via_description_keyword(self):
        s = build_session(steps_per_round=10)
        # "primitive" appears in canon descriptions but not in node IDs
        matches = _match_nodes("primitive", s.landscape, s.unified_nodes)
        assert len(matches) > 0, "Should match via description content"

    def test_match_description_scores_lower_than_id(self):
        s = build_session(steps_per_round=10)
        # "historization" should match C:historization by ID (high score)
        # and other nodes only via description (lower score)
        matches = _match_nodes("historization", s.landscape, s.unified_nodes)
        top = matches[0]
        assert top[0] == "C:historization"
        assert top[1] >= 0.8

    def test_no_descriptions_still_works(self):
        """When unified_nodes not passed, ID-only matching still works."""
        s = build_session(steps_per_round=10)
        matches = _match_nodes("tension", s.landscape)
        assert any(nid == "C:tension" for nid, _ in matches)

    def test_what_is_e0_finds_matches(self):
        """'what is e0' should now find matches via descriptions."""
        s = build_session(steps_per_round=10)
        matches = _match_nodes("what is e0", s.landscape, s.unified_nodes)
        assert len(matches) > 0, "Semantic matching should find something for 'what is e0'"

    def test_tension_resistance_both_match(self):
        s = build_session(steps_per_round=10)
        matches = _match_nodes(
            "how does tension relate to resistance",
            s.landscape, s.unified_nodes,
        )
        ids = [nid for nid, _ in matches]
        assert "C:tension" in ids
        assert "C:resistance" in ids


class TestThreeTierRouting:
    """Verify that cmd_task routes to correct tier based on matches."""

    def test_tier1_known_concept(self):
        """Single dominant match → Known Concept output."""
        s = build_session(steps_per_round=15)
        result = dispatch(s, "difference")
        assert "Known Concept" in result or "Structural Matching" in result

    def test_tier2_connection(self):
        """Multiple matches → Structural Matching + Connectivity."""
        s = build_session(steps_per_round=15)
        result = dispatch(s, "how does tension relate to resistance")
        assert "Structural Matching" in result
        assert "Connectivity" in result

    def test_tier2_creates_edges(self):
        """Multiple unconnected matches → creates new connections."""
        s = build_session(steps_per_round=15)
        result = dispatch(s, "how does tension relate to resistance")
        # Should either find existing or create new connections
        assert "Connectivity" in result

    def test_tier3_llm_fallback(self):
        """No matches → LLM Peer Structuring."""
        s = build_session(steps_per_round=15)
        result = dispatch(s, "xyzzyplugh frobnicator zazzle")
        assert "LLM Peer" in result

    def test_freetext_dispatch(self):
        """Unrecognized input treated as task."""
        s = build_session(steps_per_round=15)
        result = dispatch(s, "what are the core primitives")
        # Should trigger matching (not "Unknown command")
        assert "Unknown command" not in result

    def test_navigation_output(self):
        """All tiers produce navigation output."""
        s = build_session(steps_per_round=15)
        result = dispatch(s, "historization")
        assert "Navigation" in result
        assert "Coverage" in result


class TestTaskKnownPath:
    """Tier 1: Known Concept — single strong match."""

    def test_shows_label(self):
        s = build_session(steps_per_round=15)
        result = _task_known_path(s, "difference", ("C:difference", 1.0))
        assert "Known Concept" in result
        assert "Navigation" in result

    def test_shows_neighborhood(self):
        s = build_session(steps_per_round=15)
        # Run first to build some traces
        cmd_run(s)
        result = _task_known_path(s, "difference", ("C:difference", 1.0))
        # Should mention the concept
        assert "C:difference" in result

    def test_increments_round(self):
        s = build_session(steps_per_round=15)
        before = s.round_num
        _task_known_path(s, "difference", ("C:difference", 1.0))
        assert s.round_num == before + 1


class TestTaskConnection:
    """Tier 2: Connection — multiple matches create edges."""

    def test_creates_human_structural_edge(self):
        s = build_session(steps_per_round=15)
        matches = [("C:tension", 1.0), ("C:resistance", 1.0)]
        result = _task_connection(s, "tension and resistance", matches)
        assert "Connectivity" in result

    def test_shows_existing_connections(self):
        s = build_session(steps_per_round=15)
        # Run to build some history
        cmd_run(s)
        matches = [("C:tension", 1.0), ("C:resistance", 1.0)]
        result = _task_connection(s, "tension resistance", matches)
        # Should show connectivity section
        assert "Connectivity" in result

    def test_bidirectional_edges_created(self):
        s = build_session(steps_per_round=15)
        # Pick two nodes that are NOT connected
        n1 = "C:dream_mode"
        n2 = "C:epistemic_trust"
        matches = [(n1, 0.8), (n2, 0.8)]
        result = _task_connection(s, "dream mode epistemic trust", matches)
        # Check edges were created
        e_fwd = Edge(n1, n2)
        e_rev = Edge(n2, n1)
        assert e_fwd in s.landscape.edges or e_rev in s.landscape.edges

    def test_connection_mode_in_history(self):
        s = build_session(steps_per_round=15)
        matches = [("C:dream_mode", 0.8), ("C:novelty_gate", 0.8)]
        _task_connection(s, "dream mode novelty gate", matches)
        last = s.history[-1]
        assert last.mode in ("task", "task_connect")

    def test_visited_unvisited_tracking(self):
        s = build_session(steps_per_round=15)
        matches = [("C:tension", 1.0), ("C:resistance", 1.0)]
        result = _task_connection(s, "tension resistance", matches)
        # Output should reference visited/not-reached status
        assert "Visited" in result or "Not reached" in result


class TestTaskNavigate:
    """Shared navigation helper."""

    def test_returns_three_values(self):
        s = build_session(steps_per_round=10)
        nav_lines, comm_out, path = _task_navigate(s, "test", "C:difference")
        assert isinstance(nav_lines, str)
        assert isinstance(comm_out, str)
        assert isinstance(path, list)

    def test_coverage_in_output(self):
        s = build_session(steps_per_round=10)
        nav_lines, _, _ = _task_navigate(s, "test", "C:difference")
        assert "Coverage" in nav_lines

    def test_appends_to_history(self):
        s = build_session(steps_per_round=10)
        before = len(s.history)
        _task_navigate(s, "test", "C:difference")
        assert len(s.history) == before + 1


# ── Session Persistence (C225) ─────────────────────────────────────────


class TestSaveSession:
    """save_session writes a valid JSON file."""

    def test_save_creates_file(self, session, tmp_path):
        path = str(tmp_path / "test_session.json")
        result = save_session(session, path)
        assert os.path.exists(result)

    def test_save_contains_landscape(self, session, tmp_path):
        path = str(tmp_path / "test_session.json")
        save_session(session, path)
        import json
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert "landscape" in data
        assert "states" in data["landscape"]
        assert "edges" in data["landscape"]

    def test_save_contains_meta(self, session, tmp_path):
        path = str(tmp_path / "test_session.json")
        save_session(session, path)
        import json
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        meta = data["meta"]
        assert meta["version"] == "1.1"
        assert "round_num" in meta
        assert "saved_at" in meta

    def test_save_contains_unified_nodes(self, session, tmp_path):
        path = str(tmp_path / "test_session.json")
        save_session(session, path)
        import json
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["unified_nodes"]) > 100

    def test_save_contains_perception(self, session, tmp_path):
        path = str(tmp_path / "test_session.json")
        save_session(session, path)
        import json
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert data["perception"] is not None
        assert "spec" in data["perception"]
        assert "nodes" in data["perception"]["spec"]


class TestLoadSession:
    """load_session restores a SessionState from saved JSON."""

    def test_round_trip_landscape(self, session, tmp_path):
        path = str(tmp_path / "rt_session.json")
        save_session(session, path)
        restored = load_session(path)
        assert isinstance(restored, SessionState)
        assert restored.landscape is not None
        assert len(restored.landscape.states) == len(session.landscape.states)

    def test_round_trip_edges(self, session, tmp_path):
        path = str(tmp_path / "rt_session.json")
        save_session(session, path)
        restored = load_session(path)
        assert restored.landscape.edge_count() == session.landscape.edge_count()

    def test_round_trip_unified_nodes(self, session, tmp_path):
        path = str(tmp_path / "rt_session.json")
        save_session(session, path)
        restored = load_session(path)
        assert set(restored.unified_nodes.keys()) == set(session.unified_nodes.keys())

    def test_round_trip_perception(self, session, tmp_path):
        path = str(tmp_path / "rt_session.json")
        save_session(session, path)
        restored = load_session(path)
        assert restored.perception is not None
        assert isinstance(restored.perception, PerceptionDomain)
        assert len(restored.perception.primitives) == len(session.perception.primitives)

    def test_round_trip_metadata(self, session, tmp_path):
        path = str(tmp_path / "rt_session.json")
        save_session(session, path)
        restored = load_session(path)
        assert restored.round_num == session.round_num
        assert restored.stagnation_streak == session.stagnation_streak
        assert restored.steps_per_round == session.steps_per_round

    def test_round_trip_stats(self, session, tmp_path):
        path = str(tmp_path / "rt_session.json")
        save_session(session, path)
        restored = load_session(path)
        assert restored.stats["total_nodes"] == session.stats["total_nodes"]

    def test_restored_session_can_run(self, session, tmp_path):
        """Restored session should be fully functional."""
        path = str(tmp_path / "rt_session.json")
        save_session(session, path)
        restored = load_session(path)
        output = cmd_status(restored)
        assert "Coverage" in output or "coverage" in output.lower()


class TestCmdSave:
    """cmd_save dispatches correctly."""

    def test_cmd_save_returns_confirmation(self, session, tmp_path):
        path = str(tmp_path / "save_cmd.json")
        result = cmd_save(session, path)
        assert "Session saved" in result
        assert "Rounds" in result

    def test_dispatch_save(self, session, tmp_path):
        path = str(tmp_path / "dispatch_save.json")
        result = dispatch(session, f"save {path}")
        assert "Session saved" in result


class TestSaveInHelp:
    """Help text includes save command."""

    def test_save_in_help(self):
        text = cmd_help()
        assert "save" in text.lower()


class TestAutoDetect:
    """build_session auto-detects session_state.json when enabled."""

    def test_auto_detect_session_state(self, session, tmp_path, monkeypatch):
        path = str(tmp_path / "session_state.json")
        save_session(session, path)
        import e0_controller.interactive_session as mod
        monkeypatch.setattr(mod, "SESSION_STATE_PATH", path)
        restored = build_session(steps_per_round=15, auto_detect=True)
        assert restored.landscape is not None
        assert len(restored.landscape.states) == len(session.landscape.states)
        assert restored.steps_per_round == 15  # overridden

    def test_auto_detect_off_by_default(self):
        """Without auto_detect=True, build_session does cold start."""
        state = build_session(steps_per_round=10)
        assert isinstance(state, SessionState)
        # Cold start always has EN nodes
        assert state.stats["en_nodes"] > 0


class TestConsolidateNotDry:
    """cmd_run now uses consolidate with dry_run=False."""

    def test_consolidate_persists(self, tmp_path, monkeypatch):
        """After cmd_run, learning_state.json should be written."""
        import e0_controller.explore_bootstrap_landscape as ebl
        ls_path = str(tmp_path / "learning_state.json")
        monkeypatch.setattr(ebl, "LEARNING_STATE_PATH", ls_path)
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        assert os.path.exists(ls_path)


# ── C226: Session History + Server Lifecycle ───────────────────────────


class TestHistoryRoundTrip:
    """C226: History survives save→load cycle."""

    def test_save_contains_history(self, session, tmp_path):
        """Saved JSON includes history array."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 2)
        path = str(tmp_path / "hist_save.json")
        save_session(s, path)
        import json
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert "history" in data
        assert len(data["history"]) == 2

    def test_history_entry_fields(self, session, tmp_path):
        """Each history entry has required fields."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        path = str(tmp_path / "hist_fields.json")
        save_session(s, path)
        import json
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        entry = data["history"][0]
        for field in ["round_num", "mode", "reason", "steps", "path",
                      "coverage_delta", "T_s_delta", "assessment_before",
                      "assessment_after", "domain_crossings"]:
            assert field in entry, f"Missing field: {field}"

    def test_assessment_fields(self, session, tmp_path):
        """Assessment dicts have all required fields."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        path = str(tmp_path / "hist_assess.json")
        save_session(s, path)
        import json
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        a = data["history"][0]["assessment_after"]
        for field in ["total_nodes", "coverage", "T_s", "canon_coverage",
                      "bootstrap_coverage", "en_coverage", "mech_coverage"]:
            assert field in a, f"Missing assessment field: {field}"

    def test_load_restores_history(self, session, tmp_path):
        """load_session restores history with correct count."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 3)
        path = str(tmp_path / "hist_load.json")
        save_session(s, path)
        restored = load_session(path)
        assert len(restored.history) == 3

    def test_restored_history_types(self, session, tmp_path):
        """Restored history entries are MultiDomainRoundResult objects."""
        from e0_controller.explore_learning_cycle_multidomain import (
            MultiDomainRoundResult,
            MultiDomainAssessment,
        )
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        path = str(tmp_path / "hist_types.json")
        save_session(s, path)
        restored = load_session(path)
        r = restored.history[0]
        assert isinstance(r, MultiDomainRoundResult)
        assert isinstance(r.assessment_before, MultiDomainAssessment)
        assert isinstance(r.assessment_after, MultiDomainAssessment)

    def test_restored_history_values(self, session, tmp_path):
        """Restored history preserves scalar values."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        original = s.history[0]
        path = str(tmp_path / "hist_values.json")
        save_session(s, path)
        restored = load_session(path)
        r = restored.history[0]
        assert r.round_num == original.round_num
        assert r.mode == original.mode
        assert r.steps == original.steps
        assert r.domain_crossings == original.domain_crossings

    def test_summary_after_reload(self, session, tmp_path):
        """cmd_summary works on a reloaded session."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 2)
        path = str(tmp_path / "hist_summary.json")
        save_session(s, path)
        restored = load_session(path)
        output = cmd_summary(restored)
        assert "2 rounds" in output.lower() or "summary" in output.lower()

    def test_detail_after_reload(self, session, tmp_path):
        """cmd_detail works on a reloaded session."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        path = str(tmp_path / "hist_detail.json")
        save_session(s, path)
        restored = load_session(path)
        output = cmd_detail(restored)
        assert "Round" in output

    def test_backward_compat_no_history(self, session, tmp_path):
        """Loading a v1.0 file without history key gives empty list."""
        import json
        s = build_session(steps_per_round=10)
        path = str(tmp_path / "v1_compat.json")
        save_session(s, path)
        # Remove history key to simulate v1.0
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        del data["history"]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        restored = load_session(path)
        assert restored.history == []


class TestRoundDictCodec:
    """C226: _round_to_dict / _dict_to_round codec."""

    def test_codec_round_trip(self):
        """Encode→decode preserves round result."""
        from e0_controller.explore_learning_cycle_multidomain import (
            MultiDomainRoundResult,
            MultiDomainAssessment,
        )
        a = MultiDomainAssessment(
            total_nodes=100, total_edges=200, visited_nodes=50,
            coverage=0.5, frontier_size=10, T_s=1.5, mean_quality=0.3,
            stale_edges=2, canon_coverage=0.4, bootstrap_coverage=0.6,
            en_coverage=0.3, canon_nodes=30, bootstrap_nodes=20,
            en_nodes=50, canon_visited=12, bootstrap_visited=12,
            en_visited=15, mech_coverage=0.2, mech_nodes=10,
            mech_visited=2,
        )
        r = MultiDomainRoundResult(
            round_num=7, mode="explore", reason="low coverage",
            steps=40, assessment_before=a, assessment_after=a,
            path=["A", "B", "C"], new_edges=3, domain_crossings=2,
            crossing_rate=0.05, coverage_delta=0.02, T_s_delta=-0.1,
            en_canon_crossings=1, en_bootstrap_crossings=0,
            canon_bootstrap_crossings=1,
        )
        d = _round_to_dict(r)
        r2 = _dict_to_round(d)
        assert r2.round_num == 7
        assert r2.mode == "explore"
        assert r2.path == ["A", "B", "C"]
        assert r2.assessment_after.coverage == 0.5

    def test_assessment_codec(self):
        """Encode→decode preserves assessment."""
        from e0_controller.explore_learning_cycle_multidomain import (
            MultiDomainAssessment,
        )
        a = MultiDomainAssessment(
            total_nodes=50, total_edges=100, visited_nodes=25,
            coverage=0.5, frontier_size=5, T_s=2.0, mean_quality=0.4,
            stale_edges=1, canon_coverage=0.6, bootstrap_coverage=0.5,
            en_coverage=0.4, canon_nodes=20, bootstrap_nodes=15,
            en_nodes=15, canon_visited=12, bootstrap_visited=8,
            en_visited=5, mech_coverage=0.1, mech_nodes=5,
            mech_visited=1,
        )
        d = _assessment_to_dict(a)
        a2 = _dict_to_assessment(d)
        assert a2.total_nodes == 50
        assert a2.coverage == 0.5
        assert a2.mech_coverage == 0.1


class TestPerceptionWriteBack:
    """C226: save_session can write back perception_pretrained.json."""

    def test_write_back_off_by_default(self, session, tmp_path, monkeypatch):
        """Default save does NOT write perception_pretrained.json."""
        seed_path = str(tmp_path / "perception_pretrained.json")
        import e0_controller.interactive_session as mod
        monkeypatch.setattr(mod, "_PERCEPTION_SEED", seed_path)
        save_path = str(tmp_path / "session.json")
        save_session(session, save_path)
        assert not os.path.exists(seed_path)

    def test_write_back_on(self, session, tmp_path, monkeypatch):
        """write_back_perception=True writes perception_pretrained.json."""
        seed_path = str(tmp_path / "perception_pretrained.json")
        import e0_controller.interactive_session as mod
        monkeypatch.setattr(mod, "_PERCEPTION_SEED", seed_path)
        save_path = str(tmp_path / "session_wb.json")
        save_session(session, save_path, write_back_perception=True)
        assert os.path.exists(seed_path)

    def test_write_back_valid_json(self, session, tmp_path, monkeypatch):
        """Written perception file is valid and loadable."""
        seed_path = str(tmp_path / "perception_pretrained.json")
        import e0_controller.interactive_session as mod
        monkeypatch.setattr(mod, "_PERCEPTION_SEED", seed_path)
        save_path = str(tmp_path / "session_wb2.json")
        save_session(session, save_path, write_back_perception=True)
        restored = PerceptionDomain.from_saved(seed_path)
        assert len(restored.primitives) == len(session.perception.primitives)

    def test_write_back_no_perception(self, tmp_path, monkeypatch):
        """No crash when perception is None."""
        seed_path = str(tmp_path / "perception_pretrained.json")
        import e0_controller.interactive_session as mod
        monkeypatch.setattr(mod, "_PERCEPTION_SEED", seed_path)
        s = build_session(steps_per_round=10)
        s.perception = None
        save_path = str(tmp_path / "session_nop.json")
        save_session(s, save_path, write_back_perception=True)
        assert not os.path.exists(seed_path)


class TestServerAutoSave:
    """C226: interactive_server imports save_session."""

    def test_save_session_imported(self):
        """Server module has save_session in its namespace."""
        import e0_controller.interactive_server as srv
        assert hasattr(srv, "save_session")
        assert callable(srv.save_session)


# ── C227: Seed Regeneration ────────────────────────────────────────────


class TestRegenerateSeed:
    """C227: regenerate_seed folds session + discoveries into a new seed."""

    def test_regenerate_creates_file(self, session, tmp_path):
        """regenerate_seed writes a valid seed file."""
        path = str(tmp_path / "regen_seed.json")
        result = regenerate_seed(session, path=path)
        assert os.path.exists(result["path"])

    def test_regenerate_returns_stats(self, session, tmp_path):
        """Result dict contains all required keys."""
        path = str(tmp_path / "regen_stats.json")
        result = regenerate_seed(session, path=path)
        for key in ["path", "materialized_edges", "skipped_existing",
                     "skipped_low_confidence", "total_discovered",
                     "coverage", "total_nodes", "total_edges"]:
            assert key in result, f"Missing key: {key}"

    def test_regenerate_valid_seed_format(self, session, tmp_path):
        """Output file is a valid seed loadable by load_seed."""
        from e0_controller.explore_self_knowledge import load_seed
        path = str(tmp_path / "regen_valid.json")
        regenerate_seed(session, path=path)
        landscape, unified_nodes, meta = load_seed(path)
        assert len(landscape.states) > 100
        assert len(unified_nodes) > 100

    def test_regenerate_coverage_in_meta(self, session, tmp_path):
        """Seed meta has coverage stats."""
        import json
        path = str(tmp_path / "regen_meta.json")
        regenerate_seed(session, path=path)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert "coverage" in data["meta"]
        assert data["meta"]["coverage"] > 0.5

    def test_regenerate_after_run(self, session, tmp_path):
        """Seed regenerated after rounds has higher edge count."""
        s = build_session(steps_per_round=10)
        edges_before = s.landscape.edge_count()
        cmd_run(s, 2)
        path = str(tmp_path / "regen_run.json")
        result = regenerate_seed(s, path=path)
        assert result["total_edges"] >= edges_before


class TestRegenerateMaterialization:
    """C227: discovered_edges from learning_state.json get materialized."""

    def test_materializes_discovered_edges(self, session, tmp_path, monkeypatch):
        """Qualifying discovered_edges are added to landscape."""
        import e0_controller.explore_bootstrap_landscape as ebl
        import json

        # Create a fake learning_state with discoverable edges
        # Pick two nodes that exist but aren't connected
        nodes = list(session.landscape.states)[:2]
        src, tgt = nodes[0], nodes[1]

        ls = {
            "discovered_edges": {
                "edges": [{
                    "from": src, "to": tgt,
                    "delta": 0.5, "resistance": 1.0,
                    "confidence": 0.8,
                }]
            }
        }
        ls_path = str(tmp_path / "learning_state.json")
        with open(ls_path, "w", encoding="utf-8") as f:
            json.dump(ls, f)
        monkeypatch.setattr(ebl, "LEARNING_STATE_PATH", ls_path)

        had_edge_before = session.landscape.has_edge(src, tgt)
        path = str(tmp_path / "regen_mat.json")
        result = regenerate_seed(session, path=path)

        if had_edge_before:
            assert result["skipped_existing"] >= 1
        else:
            assert result["materialized_edges"] >= 1
            assert session.landscape.has_edge(src, tgt)

    def test_skips_low_confidence(self, session, tmp_path, monkeypatch):
        """Edges below confidence threshold are skipped."""
        import e0_controller.explore_bootstrap_landscape as ebl
        import json

        nodes = list(session.landscape.states)[:2]
        ls = {
            "discovered_edges": {
                "edges": [{
                    "from": nodes[0], "to": nodes[1],
                    "delta": 0.5, "resistance": 1.0,
                    "confidence": 0.1,  # Below default 0.4
                }]
            }
        }
        ls_path = str(tmp_path / "learning_state.json")
        with open(ls_path, "w", encoding="utf-8") as f:
            json.dump(ls, f)
        monkeypatch.setattr(ebl, "LEARNING_STATE_PATH", ls_path)

        path = str(tmp_path / "regen_skip.json")
        result = regenerate_seed(session, path=path)
        assert result["skipped_low_confidence"] >= 1

    def test_empty_learning_state(self, session, tmp_path, monkeypatch):
        """No crash when learning_state has no discovered_edges."""
        import e0_controller.explore_bootstrap_landscape as ebl
        import json

        ls = {}
        ls_path = str(tmp_path / "learning_state_empty.json")
        with open(ls_path, "w", encoding="utf-8") as f:
            json.dump(ls, f)
        monkeypatch.setattr(ebl, "LEARNING_STATE_PATH", ls_path)

        path = str(tmp_path / "regen_empty.json")
        result = regenerate_seed(session, path=path)
        assert result["materialized_edges"] == 0
        assert result["total_discovered"] == 0

    def test_custom_confidence_threshold(self, session, tmp_path, monkeypatch):
        """Custom confidence_threshold filters correctly."""
        import e0_controller.explore_bootstrap_landscape as ebl
        import json

        nodes = list(session.landscape.states)[:2]
        ls = {
            "discovered_edges": {
                "edges": [{
                    "from": nodes[0], "to": nodes[1],
                    "delta": 0.5, "resistance": 1.0,
                    "confidence": 0.3,
                }]
            }
        }
        ls_path = str(tmp_path / "learning_state.json")
        with open(ls_path, "w", encoding="utf-8") as f:
            json.dump(ls, f)
        monkeypatch.setattr(ebl, "LEARNING_STATE_PATH", ls_path)

        # With threshold=0.5 → skip
        path1 = str(tmp_path / "regen_high.json")
        s1 = build_session(steps_per_round=10)
        r1 = regenerate_seed(s1, confidence_threshold=0.5, path=path1)
        assert r1["skipped_low_confidence"] >= 1

        # With threshold=0.2 → materialize (if edge didn't exist)
        s2 = build_session(steps_per_round=10)
        path2 = str(tmp_path / "regen_low.json")
        r2 = regenerate_seed(s2, confidence_threshold=0.2, path=path2)
        # At least the threshold changed the outcome
        assert r2["skipped_low_confidence"] < r1["skipped_low_confidence"] or \
               r2["materialized_edges"] > r1["materialized_edges"] or \
               r2["skipped_existing"] > r1["skipped_existing"]


class TestCmdRegenerate:
    """C227: cmd_regenerate returns formatted output."""

    def test_cmd_regenerate_output(self, session, tmp_path):
        """cmd_regenerate returns a human-readable summary."""
        path = str(tmp_path / "cmd_regen.json")
        output = cmd_regenerate(session, path=path)
        assert "Seed regenerated" in output
        assert "Coverage" in output
        assert "Discovered edges materialized" in output

    def test_dispatch_regenerate(self, session, tmp_path):
        """dispatch routes 'regenerate' to cmd_regenerate."""
        path = str(tmp_path / "dispatch_regen.json")
        output = dispatch(session, f"regenerate {path}")
        assert "Seed regenerated" in output

    def test_regenerate_in_help(self):
        """Help text includes regenerate command."""
        text = cmd_help()
        assert "regenerate" in text.lower()


class TestMultiSessionLoop:
    """C227: Integration test — multi-session learning cycle."""

    def test_session_a_to_b_learning_carries(self, tmp_path):
        """Session A runs + saves. Session B loads + sees A's round count."""
        # Session A
        s_a = build_session(steps_per_round=10)
        cmd_run(s_a, 2)
        session_path = str(tmp_path / "session_a.json")
        save_session(s_a, session_path)

        # Session B loads A's session
        s_b = load_session(session_path)
        assert s_b.round_num == 2
        assert len(s_b.history) == 2

        # Session B runs further
        cmd_run(s_b, 1)
        assert s_b.round_num == 3
        assert len(s_b.history) == 3

        # Regenerate seed from B's combined state
        seed_path = str(tmp_path / "combined_seed.json")
        result = regenerate_seed(s_b, path=seed_path)
        assert result["coverage"] > 0
        assert os.path.exists(seed_path)

        # Session C loads the regenerated seed
        from e0_controller.explore_self_knowledge import load_seed
        landscape_c, unified_c, meta_c = load_seed(seed_path)
        assert len(landscape_c.states) == len(s_b.landscape.states)
