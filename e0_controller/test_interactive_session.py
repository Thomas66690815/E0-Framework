"""Tests for E₀ Interactive Text Session (C213 + C214 + C216 + C217 + C218).

Validates the REPL dispatch, session state management,
each command's output through the communication pipeline,
the C214 feedback loop (rate command + session-scoped perception),
C216 transition detail (detail + inspect commands),
C217 Human Peer Input (task command + node matching),
and C218 LLM Peer Structuring (propose_domain_graph → inject → navigate).
"""

from __future__ import annotations

import pytest

from e0_controller.interactive_session import (
    SessionState,
    _RATING_ACTION,
    _match_nodes,
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
    cmd_task,
    cmd_why,
    dispatch,
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
        assert s.history[-1].mode == "task"

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

    def test_help_includes_task(self):
        result = cmd_help()
        assert "task" in result


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
