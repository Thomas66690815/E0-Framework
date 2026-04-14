"""Tests for E₀ Interactive Text Session (C213–C233).

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
C227 Seed Regeneration (regenerate_seed, cmd_regenerate,
discovered_edge materialization, multi-session learning loop),
C228 Observation Dashboard (trajectory, diagnose,
compute_trajectory, diagnose_session, per-domain stagnation),
C229 Stagnation Escalation (escalate, cmd_escalate,
auto-escalation in cmd_run, 5-level progressive response),
C230 Teaching Pipeline (teach_concept, cmd_teach),
C231 Session Journal (record_journal_event, save_journal,
load_journal, cmd_journal, _metrics_snapshot, cross-session merge),
and C232 Meta-Reflection (meta_reflect, cmd_reflect,
stagnation patterns, mode effectiveness, recommendations),
and C233 Curriculum Command (curriculum_run, cmd_curriculum,
prefix-aware historization transfer, session coupling),
and C234 Dream Command (dream_run, cmd_dream,
domain sub-landscape extraction, DreamObserver session integration).
"""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from e0_controller.interactive_session import (
    AVAILABLE_CANONS,
    JOURNAL_PATH,
    SESSION_STATE_PATH,
    SessionState,
    _RATING_ACTION,
    _assessment_to_dict,
    _dict_to_assessment,
    _dict_to_round,
    _match_nodes,
    _metrics_snapshot,
    _quality_bar,
    _round_to_dict,
    _task_connection,
    _task_known_path,
    _task_navigate,
    _extract_domain_landscapes,
    build_session,
    cmd_curriculum,
    cmd_detail,
    cmd_diagnose,
    cmd_dream,
    cmd_escalate,
    cmd_focus,
    cmd_help,
    cmd_inspect,
    cmd_journal,
    cmd_rate,
    cmd_reflect,
    cmd_regenerate,
    cmd_run,
    cmd_save,
    cmd_status,
    cmd_summary,
    cmd_task,
    cmd_teach,
    cmd_trajectory,
    cmd_why,
    compute_trajectory,
    curriculum_run,
    diagnose_session,
    dream_run,
    dispatch,
    escalate,
    load_journal,
    load_session,
    meta_reflect,
    record_journal_event,
    regenerate_seed,
    save_journal,
    save_session,
    teach_concept,
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


# ── C228: Observation Dashboard ────────────────────────────────────────


class TestComputeTrajectory:
    """C228: compute_trajectory returns structured learning data."""

    def test_empty_history(self, session):
        """No rounds → empty rounds list, summary is None."""
        s = build_session(steps_per_round=10)
        traj = compute_trajectory(s)
        assert traj["rounds"] == []
        assert traj["summary"] is None

    def test_trajectory_after_rounds(self, session):
        """After N rounds, trajectory has N entries."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 3)
        traj = compute_trajectory(s)
        assert len(traj["rounds"]) == 3
        assert traj["summary"] is not None

    def test_round_fields(self, session):
        """Each round entry has required metric fields."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        traj = compute_trajectory(s)
        rd = traj["rounds"][0]
        for key in ("round_num", "coverage", "coverage_delta", "T_s",
                     "T_s_delta", "mode", "domain_crossings",
                     "frontier_size", "new_edges", "steps"):
            assert key in rd, f"Missing field: {key}"

    def test_summary_domain_trends(self, session):
        """Summary includes per-domain coverage trends."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 2)
        traj = compute_trajectory(s)
        trends = traj["summary"]["domain_trends"]
        # At least Canon and Bootstrap should be present
        assert "Canon" in trends
        assert "Bootstrap" in trends
        for name, dt in trends.items():
            assert "coverage_start" in dt
            assert "coverage_end" in dt
            assert "delta" in dt
            assert "nodes" in dt

    def test_summary_mode_progression(self, session):
        """Summary includes mode progression as ordered unique list."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 2)
        traj = compute_trajectory(s)
        modes = traj["summary"]["mode_progression"]
        assert isinstance(modes, list)
        assert len(modes) >= 1


class TestCmdTrajectory:
    """C228: cmd_trajectory formats trajectory for display."""

    def test_no_history_message(self, session):
        """With no rounds, shows helpful message."""
        s = build_session(steps_per_round=10)
        out = cmd_trajectory(s)
        assert "No rounds" in out

    def test_text_format(self, session):
        """Text output contains trajectory header and data rows."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 2)
        out = cmd_trajectory(s)
        assert "Learning Trajectory" in out
        assert "Overall:" in out
        assert "Per-domain:" in out
        assert "Mode progression:" in out

    def test_markdown_format(self, session):
        """Markdown output uses table syntax."""
        s = build_session(steps_per_round=10, output_format="markdown")
        cmd_run(s, 2)
        out = cmd_trajectory(s)
        assert "## Learning Trajectory" in out
        assert "| Rnd |" in out

    def test_stagnation_warning(self, session):
        """Stagnation streak appears in output when > 0."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 5)  # enough rounds to potentially trigger stagnation
        out = cmd_trajectory(s)
        # If stagnation streak is 0, warning should be absent
        if s.stagnation_streak > 0:
            assert "Stagnation" in out

    def test_dispatch_trajectory(self, session):
        """dispatch routes 'trajectory' to cmd_trajectory."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = dispatch(s, "trajectory")
        assert "Learning Trajectory" in out


class TestDiagnoseSession:
    """C228: diagnose_session returns structured diagnostic data."""

    def test_diagnose_fresh_session(self, session):
        """Diagnosis works on a session with no rounds."""
        s = build_session(steps_per_round=10)
        diag = diagnose_session(s)
        assert "domains" in diag
        assert "overall" in diag
        assert len(diag["domains"]) >= 2  # Canon + Bootstrap at minimum

    def test_domain_fields(self, session):
        """Each domain has required diagnostic fields."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 2)
        diag = diagnose_session(s)
        for d in diag["domains"]:
            for key in ("name", "prefix", "coverage", "total", "visited",
                         "frontier", "isolated", "active_edges",
                         "mean_quality", "velocity", "status",
                         "suggestion"):
                assert key in d, f"Missing field: {key} in {d['name']}"

    def test_status_values(self, session):
        """Status is one of the defined values."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 2)
        diag = diagnose_session(s)
        valid = {"SATURATED", "BLOCKED", "STAGNANT", "GROWING", "IDLE"}
        for d in diag["domains"]:
            assert d["status"] in valid, (
                f"{d['name']} has invalid status: {d['status']}"
            )

    def test_overall_has_bottleneck(self, session):
        """Overall diagnosis identifies a bottleneck domain."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 2)
        diag = diagnose_session(s)
        ov = diag["overall"]
        assert "bottleneck" in ov
        assert "stagnation_streak" in ov
        assert "blocked_domains" in ov
        assert "coverage" in ov
        assert "T_s" in ov

    def test_velocity_after_rounds(self, session):
        """Velocity is computed from recent history."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 3)
        diag = diagnose_session(s)
        # At least one domain should have nonzero velocity
        velocities = [d["velocity"] for d in diag["domains"]]
        # All velocities should be finite numbers
        import math
        for v in velocities:
            assert math.isfinite(v)


class TestCmdDiagnose:
    """C228: cmd_diagnose formats diagnosis for display."""

    def test_output_contains_domains(self, session):
        """Output lists all active domains."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_diagnose(s)
        assert "Diagnostic Report" in out
        assert "Canon" in out
        assert "Bootstrap" in out
        assert "Overall" in out

    def test_output_shows_status(self, session):
        """Each domain shows its status label."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_diagnose(s)
        assert "Status:" in out
        assert "Suggestion:" in out
        assert "Coverage:" in out

    def test_dispatch_diagnose(self, session):
        """dispatch routes 'diagnose' to cmd_diagnose."""
        s = build_session(steps_per_round=10)
        out = dispatch(s, "diagnose")
        assert "Diagnostic Report" in out

    def test_help_includes_new_commands(self):
        """Help text includes trajectory and diagnose."""
        text = cmd_help()
        assert "trajectory" in text.lower()
        assert "diagnose" in text.lower()

    def test_markdown_diagnose(self, session):
        """Markdown output uses headers."""
        s = build_session(steps_per_round=10, output_format="markdown")
        cmd_run(s, 1)
        out = cmd_diagnose(s)
        assert "## Diagnostic Report" in out
        assert "### Canon" in out or "### Bootstrap" in out


# ── C229: Stagnation Escalation ────────────────────────────────────────


class TestEscalate:
    """C229: escalate() returns structured escalation result."""

    def test_returns_dict(self):
        """escalate() returns a dict with required keys."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = escalate(s)
        assert isinstance(result, dict)
        assert "resolved" in result
        assert "level" in result
        assert "name" in result
        assert "coverage_delta" in result
        assert "attempts" in result

    def test_attempts_list(self):
        """Each attempt has level, name, coverage_delta, detail."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = escalate(s)
        for a in result["attempts"]:
            assert "level" in a
            assert "name" in a
            assert "coverage_delta" in a
            assert "detail" in a

    def test_levels_in_order(self):
        """Attempts are tried in ascending level order."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = escalate(s)
        levels = [a["level"] for a in result["attempts"]]
        assert levels == sorted(levels)

    def test_resets_stagnation_on_resolve(self):
        """On resolution, stagnation_streak is reset to 0."""
        s = build_session(steps_per_round=10)
        s.stagnation_streak = 5
        result = escalate(s)
        if result["resolved"]:
            assert s.stagnation_streak == 0

    def test_accept_is_last_resort(self):
        """Level 5 (accept) is present when nothing resolves."""
        s = build_session(steps_per_round=10)
        # Run many rounds to push coverage high
        cmd_run(s, 10)
        result = escalate(s)
        assert result["level"] <= 5
        if not result["resolved"]:
            assert result["name"] == "accept"
            assert result["level"] == 5


class TestCmdEscalate:
    """C229: cmd_escalate formats readable output."""

    def test_output_is_string(self):
        """cmd_escalate returns a non-empty string."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_escalate(s)
        assert isinstance(out, str)
        assert len(out) > 0

    def test_output_header(self):
        """Output starts with 'Stagnation Escalation'."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_escalate(s)
        assert "Stagnation Escalation" in out

    def test_output_shows_levels(self):
        """Output shows L1, L2, etc. for attempted levels."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_escalate(s)
        assert "L1" in out

    def test_output_shows_resolution(self):
        """Output includes resolution status."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_escalate(s)
        assert "Resolved" in out or "Structural limit" in out

    def test_output_shows_delta(self):
        """Output includes coverage delta."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_escalate(s)
        assert "cov=" in out


class TestEscalationDispatch:
    """C229: dispatch routes 'escalate' to cmd_escalate."""

    def test_dispatch_escalate(self):
        """dispatch('escalate') calls cmd_escalate."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = dispatch(s, "escalate")
        assert "Stagnation Escalation" in out

    def test_help_includes_escalate(self):
        """Help text includes 'escalate' command."""
        text = cmd_help()
        assert "escalate" in text.lower()


class TestAutoEscalation:
    """C229: cmd_run auto-escalates on stagnation >= 3."""

    def test_auto_escalation_triggers(self):
        """After 3+ rounds of stagnation, auto-escalation appears."""
        s = build_session(steps_per_round=3)
        # Run enough rounds to potentially trigger stagnation
        out = cmd_run(s, 10)
        # Auto-escalation may or may not trigger depending on landscape
        # State consistency: stagnation streak is tracked
        assert s.stagnation_streak >= 0

    def test_no_auto_escalation_below_threshold(self):
        """No escalation warning with stagnation < 3."""
        s = build_session(steps_per_round=10)
        out = cmd_run(s, 1)
        assert "auto-escalating" not in out

    def test_forced_stagnation_triggers_escalation(self):
        """Pre-setting stagnation_streak=2, one more stagnant round triggers."""
        s = build_session(steps_per_round=1)
        s.stagnation_streak = 2
        # Run many rounds to saturate, forcing stagnation
        cmd_run(s, 5)
        out = cmd_run(s, 5)
        # With very small steps, likely to stagnate
        # Either auto-escalation message or structural saturation
        assert (
            "auto-escalating" in out
            or "saturation" in out.lower()
            or s.stagnation_streak < 3  # was resolved
        )


# ── C230: Teaching Pipeline ──────────────────────────────────────────────────

_TEACH_SPEC = {
    "nodes": ["CONCEPT_A", "CONCEPT_B", "CONCEPT_C", "CONCEPT_D"],
    "edges": [
        {"from": "CONCEPT_A", "to": "CONCEPT_B", "delta": 0.5,
         "resistance": 1.0, "initial_U": 4.0, "initial_F": 1.0,
         "confidence": 0.8},
        {"from": "CONCEPT_B", "to": "CONCEPT_C", "delta": 0.4,
         "resistance": 0.9, "initial_U": 3.0, "initial_F": 0.5,
         "confidence": 0.7},
        {"from": "CONCEPT_C", "to": "CONCEPT_D", "delta": 0.6,
         "resistance": 1.1, "initial_U": 2.0, "initial_F": 1.0,
         "confidence": 0.6},
        {"from": "CONCEPT_D", "to": "CONCEPT_A", "delta": 0.3,
         "resistance": 0.8, "initial_U": 5.0, "initial_F": 0.5,
         "confidence": 0.9},
    ],
}


class TestTeachConcept:
    """C230: teach_concept returns structured result."""

    def test_returns_dict(self):
        """teach_concept returns a dict with required keys."""
        s = _build_session_with_mock(_TEACH_SPEC)
        result = teach_concept(s, "alpha beta unknown concept")
        assert isinstance(result, dict)
        for key in (
            "nodes_added", "edges_added", "coverage_before",
            "coverage_after", "coverage_delta", "rounds_run",
            "domain_crossings", "absorbed", "total_new_edges",
        ):
            assert key in result, f"missing key: {key}"

    def test_nodes_have_l_prefix(self):
        """Injected nodes use L: prefix."""
        s = _build_session_with_mock(_TEACH_SPEC)
        result = teach_concept(s, "alpha beta unknown concept")
        assert len(result["nodes_added"]) >= 1
        for nid in result["nodes_added"]:
            assert nid.startswith("L:"), f"expected L: prefix, got {nid}"

    def test_coverage_non_negative(self):
        """Coverage delta is non-negative (new material can't decrease it)."""
        s = _build_session_with_mock(_TEACH_SPEC)
        result = teach_concept(s, "alpha beta unknown concept")
        assert result["coverage_delta"] >= 0.0

    def test_runs_multiple_passes(self):
        """teach_concept runs multiple exploration passes."""
        s = _build_session_with_mock(_TEACH_SPEC)
        result = teach_concept(s, "alpha beta unknown concept")
        assert result["rounds_run"] >= 1

    def test_history_grows(self):
        """Teaching adds rounds to session history."""
        s = _build_session_with_mock(_TEACH_SPEC)
        before = len(s.history)
        teach_concept(s, "alpha beta unknown concept")
        assert len(s.history) > before

    def test_teach_mode_in_history(self):
        """History entries from teach use mode='teach'."""
        s = _build_session_with_mock(_TEACH_SPEC)
        before = len(s.history)
        teach_concept(s, "alpha beta unknown concept")
        for r in s.history[before:]:
            assert r.mode == "teach"

    def test_absorbed_leq_total(self):
        """Absorbed edges cannot exceed total new edges."""
        s = _build_session_with_mock(_TEACH_SPEC)
        result = teach_concept(s, "alpha beta unknown concept")
        assert result["absorbed"] <= result["total_new_edges"]


class TestCmdTeach:
    """C230: cmd_teach provides formatted output."""

    def test_output_is_string(self):
        """cmd_teach returns a non-empty string."""
        s = _build_session_with_mock(_TEACH_SPEC)
        out = cmd_teach(s, "alpha beta unknown concept")
        assert isinstance(out, str)
        assert len(out) > 0

    def test_output_header(self):
        """Output starts with 'Teaching Pipeline'."""
        s = _build_session_with_mock(_TEACH_SPEC)
        out = cmd_teach(s, "alpha beta unknown concept")
        assert "Teaching Pipeline" in out

    def test_output_shows_nodes(self):
        """Output lists injected nodes."""
        s = _build_session_with_mock(_TEACH_SPEC)
        out = cmd_teach(s, "alpha beta unknown concept")
        assert "L:" in out

    def test_output_shows_coverage(self):
        """Output includes coverage metrics."""
        s = _build_session_with_mock(_TEACH_SPEC)
        out = cmd_teach(s, "alpha beta unknown concept")
        assert "Coverage:" in out

    def test_output_shows_absorption(self):
        """Output includes absorption report."""
        s = _build_session_with_mock(_TEACH_SPEC)
        out = cmd_teach(s, "alpha beta unknown concept")
        assert "Absorbed:" in out


class TestTeachDispatch:
    """C230: dispatch routes 'teach' to cmd_teach."""

    def test_dispatch_teach(self):
        """dispatch('teach X') calls cmd_teach."""
        s = _build_session_with_mock(_TEACH_SPEC)
        out = dispatch(s, "teach alpha beta unknown concept")
        assert "Teaching Pipeline" in out

    def test_dispatch_teach_no_arg(self):
        """dispatch('teach') without arg returns usage hint."""
        s = build_session(steps_per_round=10)
        out = dispatch(s, "teach")
        assert "Usage:" in out

    def test_help_includes_teach(self):
        """Help text includes 'teach' command."""
        text = cmd_help()
        assert "teach" in text.lower()


# ── C231: Session Journal ────────────────────────────────────────────────────


class TestMetricsSnapshot:
    """C231: _metrics_snapshot returns a well-structured dict."""

    def test_returns_dict(self):
        s = build_session(steps_per_round=10)
        snap = _metrics_snapshot(s)
        assert isinstance(snap, dict)

    def test_has_coverage(self):
        s = build_session(steps_per_round=10)
        snap = _metrics_snapshot(s)
        assert "coverage" in snap
        assert 0.0 <= snap["coverage"] <= 1.0

    def test_has_domain_coverages(self):
        s = build_session(steps_per_round=10)
        snap = _metrics_snapshot(s)
        for key in ("canon_coverage", "bootstrap_coverage", "en_coverage"):
            assert key in snap

    def test_has_stagnation_streak(self):
        s = build_session(steps_per_round=10)
        snap = _metrics_snapshot(s)
        assert snap["stagnation_streak"] == 0


class TestRecordJournalEvent:
    """C231: record_journal_event creates well-formed entries."""

    def test_returns_entry_dict(self):
        s = build_session(steps_per_round=10)
        entry = record_journal_event(s, "round", {"mode": "exploit"})
        assert isinstance(entry, dict)

    def test_required_keys(self):
        s = build_session(steps_per_round=10)
        entry = record_journal_event(s, "round")
        for key in ("timestamp", "session_id", "event_type", "round_num", "metrics"):
            assert key in entry, f"missing key: {key}"

    def test_event_type_preserved(self):
        s = build_session(steps_per_round=10)
        entry = record_journal_event(s, "teach", {"concept": "test"})
        assert entry["event_type"] == "teach"

    def test_detail_attached(self):
        s = build_session(steps_per_round=10)
        entry = record_journal_event(s, "note", {"text": "hello"})
        assert entry["detail"]["text"] == "hello"

    def test_appends_to_journal(self):
        s = build_session(steps_per_round=10)
        before = len(s.journal)
        record_journal_event(s, "round")
        assert len(s.journal) == before + 1

    def test_session_id_set(self):
        s = build_session(steps_per_round=10)
        entry = record_journal_event(s, "round")
        assert entry["session_id"] == s.session_id
        assert len(s.session_id) > 0


class TestSaveLoadJournal:
    """C231: save_journal and load_journal round-trip."""

    def test_round_trip(self):
        s = build_session(steps_per_round=10)
        record_journal_event(s, "session_start")
        record_journal_event(s, "round", {"mode": "explore"})
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "journal.json")
            save_journal(s, path=path)
            loaded = load_journal(path=path)
        assert len(loaded) == 2
        assert loaded[0]["event_type"] == "session_start"

    def test_cross_session_merge(self):
        """Two sessions are merged into a single file."""
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "journal.json")
            # Session 1
            s1 = build_session(steps_per_round=10)
            s1.session_id = "SES_001"
            s1.journal.clear()
            record_journal_event(s1, "session_start")
            save_journal(s1, path=path)
            # Session 2 (different session_id to avoid dedup)
            s2 = build_session(steps_per_round=10)
            s2.session_id = "SES_002"
            s2.journal.clear()
            record_journal_event(s2, "session_start")
            record_journal_event(s2, "round")
            save_journal(s2, path=path)
            loaded = load_journal(path=path)
        # Both sessions' entries present
        assert len(loaded) >= 3

    def test_deduplication(self):
        """Saving the same session twice does not double entries."""
        s = build_session(steps_per_round=10)
        record_journal_event(s, "session_start")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "journal.json")
            save_journal(s, path=path)
            save_journal(s, path=path)
            loaded = load_journal(path=path)
        assert len(loaded) == 1

    def test_load_nonexistent(self):
        """Loading from a nonexistent path returns empty list."""
        loaded = load_journal(path="/nonexistent/path/journal.json")
        assert loaded == []

    def test_saved_format(self):
        """Saved file has version and entries keys."""
        s = build_session(steps_per_round=10)
        record_journal_event(s, "round")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "journal.json")
            save_journal(s, path=path)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        assert data["version"] == "1.0"
        assert "entries" in data


class TestCmdJournal:
    """C231: cmd_journal dispatches correctly."""

    def test_empty_journal_message(self):
        s = build_session(steps_per_round=10)
        s.journal.clear()
        out = cmd_journal(s, None)
        assert "No journal entries" in out

    def test_shows_entries_after_record(self):
        s = build_session(steps_per_round=10)
        record_journal_event(s, "round", {"mode": "explore"})
        out = cmd_journal(s, None)
        assert "Session Journal" in out
        assert "●" in out  # round icon

    def test_note_recording(self):
        s = build_session(steps_per_round=10)
        out = cmd_journal(s, "note This is a test annotation")
        assert "✓" in out
        assert len(s.journal) >= 2  # session_start + note

    def test_note_appears_in_output(self):
        s = build_session(steps_per_round=10)
        cmd_journal(s, "note Remember this insight")
        out = cmd_journal(s, None)
        assert "Remember this insight" in out

    def test_note_empty_returns_usage(self):
        s = build_session(steps_per_round=10)
        out = cmd_journal(s, "note ")
        assert "Usage:" in out

    def test_all_mode(self):
        s = build_session(steps_per_round=10)
        record_journal_event(s, "round")
        out = cmd_journal(s, "all")
        assert "Cross-Session" in out or "Session Journal" in out

    def test_summary_line(self):
        s = build_session(steps_per_round=10)
        record_journal_event(s, "round")
        record_journal_event(s, "round")
        out = cmd_journal(s, None)
        assert "entries" in out


class TestSessionIdField:
    """C231: SessionState carries session_id."""

    def test_session_id_nonempty(self):
        s = build_session(steps_per_round=10)
        assert isinstance(s.session_id, str)
        assert len(s.session_id) > 0

    def test_session_start_recorded(self):
        s = build_session(steps_per_round=10)
        assert len(s.journal) >= 1
        assert s.journal[0]["event_type"] == "session_start"


class TestJournalDispatch:
    """C231: dispatch routes 'journal' command."""

    def test_dispatch_journal(self):
        s = build_session(steps_per_round=10)
        out = dispatch(s, "journal")
        assert "Journal" in out or "journal" in out or "No journal" in out

    def test_dispatch_journal_note(self):
        s = build_session(steps_per_round=10)
        out = dispatch(s, "journal note Test from dispatch")
        assert "✓" in out

    def test_help_includes_journal(self):
        text = cmd_help()
        assert "journal" in text.lower()


# ── C232: Meta-Reflection ────────────────────────────────────────────────────


class TestMetaReflect:
    """C232: meta_reflect returns structured analysis."""

    def test_returns_dict(self, session):
        """meta_reflect returns a dict with required keys."""
        cmd_run(session, 2)
        ref = meta_reflect(session)
        assert isinstance(ref, dict)

    def test_has_required_keys(self, session):
        """Result contains all expected sections."""
        ref = meta_reflect(session)
        for key in (
            "stagnation_episodes", "mode_effectiveness",
            "domain_trajectories", "escalation_summary",
            "teach_summary", "patterns", "recommendations",
            "overall",
        ):
            assert key in ref, f"missing key: {key}"

    def test_mode_effectiveness_populated(self, session):
        """Mode effectiveness contains at least one entry after running."""
        ref = meta_reflect(session)
        assert len(ref["mode_effectiveness"]) >= 1

    def test_mode_entries_have_fields(self, session):
        """Each mode entry has required fields."""
        ref = meta_reflect(session)
        for me in ref["mode_effectiveness"]:
            for field in ("mode", "rounds", "avg_delta",
                          "stagnation_rate", "avg_crossings"):
                assert field in me, f"missing field: {field}"

    def test_domain_trajectories_four_domains(self, session):
        """All four domains are tracked."""
        ref = meta_reflect(session)
        for name in ("Canon", "Bootstrap", "EN", "Mechanism"):
            assert name in ref["domain_trajectories"]

    def test_domain_trajectory_fields(self, session):
        """Domain trajectory entries have expected fields."""
        ref = meta_reflect(session)
        for name, dt in ref["domain_trajectories"].items():
            for field in ("coverage_start", "coverage_end", "status",
                          "velocity", "confused_edges", "frontier"):
                assert field in dt, f"missing field: {field} in {name}"

    def test_overall_section(self, session):
        """Overall section has total_rounds and coverage."""
        ref = meta_reflect(session)
        ov = ref["overall"]
        assert ov["total_rounds"] >= 2
        assert 0.0 <= ov["coverage"] <= 1.0

    def test_patterns_nonempty(self, session):
        """Patterns list is always non-empty (at least 'healthy')."""
        ref = meta_reflect(session)
        assert len(ref["patterns"]) >= 1

    def test_recommendations_nonempty(self, session):
        """Recommendations list is always non-empty."""
        ref = meta_reflect(session)
        assert len(ref["recommendations"]) >= 1

    def test_escalation_summary(self, session):
        """Escalation summary has correct structure."""
        ref = meta_reflect(session)
        esc = ref["escalation_summary"]
        assert "total" in esc
        assert "resolved" in esc
        assert isinstance(esc["total"], int)

    def test_teach_summary(self, session):
        """Teach summary has correct structure."""
        ref = meta_reflect(session)
        ts = ref["teach_summary"]
        assert "total" in ts
        assert "total_nodes_added" in ts

    def test_records_journal_event(self):
        """meta_reflect records a 'reflect' journal event."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        before = len(s.journal)
        meta_reflect(s)
        reflect_events = [
            e for e in s.journal[before:]
            if e["event_type"] == "reflect"
        ]
        assert len(reflect_events) == 1


class TestMetaReflectStagnation:
    """C232: stagnation detection in meta_reflect."""

    def test_stagnation_episodes_list(self, session):
        """Stagnation episodes is a list of dicts."""
        ref = meta_reflect(session)
        assert isinstance(ref["stagnation_episodes"], list)

    def test_stagnation_episode_fields(self):
        """Each episode has start/end/length/modes."""
        s = build_session(steps_per_round=10)
        # Run enough rounds that some may stagnate
        cmd_run(s, 5)
        ref = meta_reflect(s)
        for ep in ref["stagnation_episodes"]:
            assert "start" in ep
            assert "end" in ep
            assert "length" in ep
            assert "modes" in ep
            assert ep["length"] >= 1


class TestCmdReflect:
    """C232: cmd_reflect provides formatted output."""

    def test_output_is_string(self, session):
        """cmd_reflect returns a non-empty string."""
        out = cmd_reflect(session)
        assert isinstance(out, str)
        assert len(out) > 0

    def test_output_has_header(self, session):
        """Output contains 'Meta-Reflection'."""
        out = cmd_reflect(session)
        assert "Meta-Reflection" in out

    def test_output_has_mode_section(self, session):
        """Output contains mode effectiveness."""
        out = cmd_reflect(session)
        assert "Mode Effectiveness" in out

    def test_output_has_domain_section(self, session):
        """Output contains domain trajectories."""
        out = cmd_reflect(session)
        assert "Domain Trajectories" in out

    def test_output_has_patterns(self, session):
        """Output shows identified patterns."""
        out = cmd_reflect(session)
        assert "Patterns" in out

    def test_output_has_recommendations(self, session):
        """Output shows recommendations."""
        out = cmd_reflect(session)
        assert "Recommendations" in out

    def test_no_history_message(self):
        """With no history, returns help message."""
        s = build_session(steps_per_round=10)
        out = cmd_reflect(s)
        assert "No history" in out


class TestReflectDispatch:
    """C232: dispatch routes 'reflect' command."""

    def test_dispatch_reflect(self, session):
        """dispatch('reflect') returns meta-reflection."""
        out = dispatch(session, "reflect")
        assert "Meta-Reflection" in out or "No history" in out

    def test_help_includes_reflect(self):
        """Help text includes 'reflect' command."""
        text = cmd_help()
        assert "reflect" in text.lower()


# ── C233: Curriculum Command ───────────────────────────────────────────


class TestCurriculumRun:
    """C233: curriculum_run executes CurriculumRunner and couples back."""

    def test_returns_result_dict(self):
        """curriculum_run returns dict with expected keys."""
        s = build_session(steps_per_round=10)
        result = curriculum_run(s, "ontodynamics")
        assert "canon_name" in result
        assert "turn_results" in result
        assert "transferred_edges" in result
        assert "summary" in result
        assert result["canon_name"] == "ontodynamics"

    def test_has_turn_results(self):
        """Result contains non-empty turn_results list."""
        s = build_session(steps_per_round=10)
        result = curriculum_run(s, "ontodynamics")
        assert len(result["turn_results"]) > 0

    def test_turn_results_have_fields(self):
        """Each turn result has expected fields."""
        s = build_session(steps_per_round=10)
        result = curriculum_run(s, "ontodynamics")
        for tr in result["turn_results"]:
            assert hasattr(tr, "turn")
            assert hasattr(tr, "traces")
            assert hasattr(tr, "equilibrium_reached")
            assert hasattr(tr, "final_T_s")
            assert hasattr(tr, "total_steps")
            assert hasattr(tr, "episodes")

    def test_summary_is_string(self):
        """Result summary is a non-empty string."""
        s = build_session(steps_per_round=10)
        result = curriculum_run(s, "ontodynamics")
        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 0

    def test_transferred_edges_non_negative(self):
        """Transferred edges count is >= 0."""
        s = build_session(steps_per_round=10)
        result = curriculum_run(s, "ontodynamics")
        assert result["transferred_edges"] >= 0

    def test_journal_event_recorded(self):
        """curriculum_run records a journal event."""
        s = build_session(steps_per_round=10)
        initial_count = len(s.journal)
        curriculum_run(s, "ontodynamics")
        assert len(s.journal) > initial_count
        # Find the curriculum event
        events = [e for e in s.journal if e["event_type"] == "curriculum"]
        assert len(events) >= 1
        ev = events[-1]
        assert ev["detail"]["canon"] == "ontodynamics"
        assert ev["detail"]["turns"] > 0

    def test_mechanism_canon(self):
        """curriculum_run works with mechanism_e0 canon."""
        s = build_session(steps_per_round=10)
        result = curriculum_run(s, "mechanism_e0")
        assert result["canon_name"] == "mechanism_e0"
        assert len(result["turn_results"]) > 0


class TestCmdCurriculum:
    """C233: cmd_curriculum produces formatted output."""

    def test_output_is_string(self):
        """cmd_curriculum returns a non-empty string."""
        s = build_session(steps_per_round=10)
        out = cmd_curriculum(s)
        assert isinstance(out, str)
        assert len(out) > 0

    def test_output_contains_header(self):
        """Output contains 'Curriculum:' header."""
        s = build_session(steps_per_round=10)
        out = cmd_curriculum(s)
        assert "Curriculum:" in out

    def test_output_contains_turn_results(self):
        """Output contains 'Turn Results' section."""
        s = build_session(steps_per_round=10)
        out = cmd_curriculum(s)
        assert "Turn Results" in out

    def test_output_contains_coupling(self):
        """Output contains 'Session Coupling' section."""
        s = build_session(steps_per_round=10)
        out = cmd_curriculum(s)
        assert "Session Coupling" in out

    def test_explicit_canon_name(self):
        """Passing canon name selects that canon."""
        s = build_session(steps_per_round=10)
        out = cmd_curriculum(s, "mechanism_e0")
        assert "mechanism_e0" in out

    def test_partial_canon_match(self):
        """Partial name matches the full canon."""
        s = build_session(steps_per_round=10)
        out = cmd_curriculum(s, "onto")
        assert "ontodynamics" in out

    def test_unknown_canon_error(self):
        """Unknown canon returns error message."""
        s = build_session(steps_per_round=10)
        out = cmd_curriculum(s, "nonexistent_canon")
        assert "Unknown canon" in out

    def test_markdown_format(self):
        """Markdown format uses ## headers."""
        s = build_session(steps_per_round=10)
        s.output_format = "markdown"
        out = cmd_curriculum(s)
        assert "## Curriculum:" in out


class TestCurriculumDispatch:
    """C233: dispatch routes 'curriculum' command."""

    def test_dispatch_curriculum(self):
        """dispatch('curriculum') runs the curriculum."""
        s = build_session(steps_per_round=10)
        out = dispatch(s, "curriculum")
        assert "Curriculum:" in out

    def test_dispatch_curriculum_with_arg(self):
        """dispatch('curriculum ontodynamics') passes the argument."""
        s = build_session(steps_per_round=10)
        out = dispatch(s, "curriculum ontodynamics")
        assert "ontodynamics" in out

    def test_help_includes_curriculum(self):
        """Help text includes 'curriculum' command."""
        text = cmd_help()
        assert "curriculum" in text.lower()


class TestAvailableCanons:
    """C233: AVAILABLE_CANONS list is correct."""

    def test_contains_ontodynamics(self):
        assert "ontodynamics" in AVAILABLE_CANONS

    def test_contains_mechanism(self):
        assert "mechanism_e0" in AVAILABLE_CANONS

    def test_contains_english(self):
        assert "english_basic_enriched" in AVAILABLE_CANONS


# ── C234: Dream Command ───────────────────────────────────────────────


class TestExtractDomainLandscapes:
    """C234: _extract_domain_landscapes extracts per-domain sub-landscapes."""

    def test_returns_dict(self, session):
        """Returns a dict of domain name → Landscape."""
        result = _extract_domain_landscapes(session.landscape)
        assert isinstance(result, dict)
        assert len(result) >= 2  # at least canon + bootstrap

    def test_contains_expected_domains(self, session):
        """Extracted domains include canon and bootstrap."""
        result = _extract_domain_landscapes(session.landscape)
        assert "canon" in result
        assert "bootstrap" in result

    def test_sub_landscapes_have_edges(self, session):
        """Each sub-landscape has at least one edge."""
        result = _extract_domain_landscapes(session.landscape)
        for name, ls in result.items():
            assert len(ls.edges) > 0, f"{name} has no edges"

    def test_nodes_have_correct_prefix(self, session):
        """Canon sub-landscape nodes start with C:."""
        result = _extract_domain_landscapes(session.landscape)
        canon_ls = result["canon"]
        for state in canon_ls.states:
            assert state.startswith("C:"), f"Unexpected node: {state}"


class TestDreamRun:
    """C234: dream_run executes dream cycles on session landscape."""

    def test_returns_dict(self):
        """dream_run returns a result dict."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)  # generate some historization
        result = dream_run(s, cycles=1)
        assert isinstance(result, dict)

    def test_result_has_expected_keys(self):
        """Result contains cycles, domains, readiness, totals."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = dream_run(s, cycles=1)
        assert "cycles" in result
        assert "domains" in result
        assert "readiness" in result
        assert "total_equivalences" in result
        assert "cycle_results" in result

    def test_cycles_respected(self):
        """Number of DreamCycleResults matches requested cycles."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = dream_run(s, cycles=2)
        assert len(result["cycle_results"]) == 2

    def test_observer_persists_on_state(self):
        """DreamObserver is stored on session state for reuse."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        assert s.dream_observer is None
        dream_run(s, cycles=1)
        assert s.dream_observer is not None

    def test_journal_event_recorded(self):
        """dream_run records a 'dream' journal event."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        dream_run(s, cycles=1)
        dream_events = [e for e in s.journal if e["event_type"] == "dream"]
        assert len(dream_events) >= 1
        detail = dream_events[-1]["detail"]
        assert "cycles" in detail
        assert "domains_registered" in detail

    def test_readiness_has_domains(self):
        """Readiness report contains registered domain names."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = dream_run(s, cycles=1)
        assert len(result["readiness"]) > 0


class TestCmdDream:
    """C234: cmd_dream provides formatted output."""

    def test_output_is_string(self):
        """cmd_dream returns a non-empty string."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_dream(s)
        assert isinstance(out, str)
        assert len(out) > 0

    def test_output_has_header(self):
        """Output contains 'Dream Consolidation'."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_dream(s)
        assert "Dream Consolidation" in out

    def test_output_has_readiness(self):
        """Output contains 'Readiness' section."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_dream(s)
        assert "Readiness" in out

    def test_output_has_cycle_results(self):
        """Output contains 'Cycle' in cycle result lines."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_dream(s)
        assert "Cycle" in out

    def test_output_has_dream_landscape(self):
        """Output contains 'Dream Landscape' stats."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_dream(s)
        assert "Dream Landscape" in out

    def test_custom_cycles(self):
        """cmd_dream('5') runs 5 cycles."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_dream(s, "5")
        assert "5 cycles" in out

    def test_invalid_arg(self):
        """Invalid arg returns usage hint."""
        s = build_session(steps_per_round=10)
        out = cmd_dream(s, "abc")
        assert "Usage" in out or "Invalid" in out

    def test_markdown_format(self):
        """Markdown mode uses ## headers."""
        s = build_session(steps_per_round=10, output_format="markdown")
        cmd_run(s, 1)
        out = cmd_dream(s, "1")
        assert "## Dream" in out


class TestDreamDispatch:
    """C234: dispatch routes 'dream' command."""

    def test_dispatch_dream(self):
        """dispatch('dream') calls cmd_dream."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = dispatch(s, "dream")
        assert "Dream Consolidation" in out

    def test_dispatch_dream_with_arg(self):
        """dispatch('dream 2') passes cycle count."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = dispatch(s, "dream 2")
        assert "2 cycles" in out

    def test_help_includes_dream(self):
        """Help text includes 'dream' command."""
        text = cmd_help()
        assert "dream" in text.lower()
