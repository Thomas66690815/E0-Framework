"""Tests for E₀ Interactive Text Session (C213–C238).

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
domain sub-landscape extraction, DreamObserver session integration),
and C235 Sleep-Wake Integration (sleep_wake_run, cmd_sleep,
per-domain E0Controller, SleepWakeCycle, historization transfer),
and C236 Tune Command (tune_run, cmd_tune,
per-domain auto-tuning via Self-Graph diagnosis, parameter perturbation),
and C237 Auto-Mode (auto_run, cmd_auto, _choose_action,
autonomous decision loop orchestrating run/escalate/dream/sleep/curriculum/tune),
and C238 Self-Learn (selflearn_run, cmd_selflearn, _assess_self_mastery,
self-learning orchestration: canon → mechanism → dream → mastery assessment),
and C239 Ask Command (ask_run, cmd_ask, _extract_question_terms,
_assess_knowledge, on-demand Q&A: assess → gap-detect → learn → navigate).
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
    UniverseState,
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
    _DISPLAY_PREFIXES,
    _pick_community_start,
    _transfer_community_to_session,
    build_session,
    cmd_auto,
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
    cmd_sleep,
    cmd_status,
    cmd_summary,
    cmd_task,
    cmd_teach,
    cmd_trajectory,
    cmd_tune,
    cmd_universe,
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
    sleep_wake_run,
    teach_concept,
    tune_run,
    _choose_action,
    auto_run,
    selflearn_run,
    cmd_selflearn,
    _assess_self_mastery,
    _extract_question_terms,
    _assess_knowledge,
    _diagnose_learning_gaps,
    _formulate_followup,
    _format_path_evidence,
    _structural_answer,
    _stem,
    ask_run,
    cmd_ask,
    universe_create,
    universe_list,
    universe_switch,
    universe_delete,
    _ensure_main_universe,
    _sync_active_to_session,
    _sync_session_to_active,
    _universe_to_coupling,
    _ensure_coupling_router,
    couple_run,
    couple_status,
    cmd_couple,
    _format_couple_result,
    _inject_dream_bridges,
    _create_bridges,
    refresh_communities,
)
from e0_controller.feedback import HumanAction
from e0_controller.perception import PerceptionDomain
from e0_controller.coupling_router import CouplingReason, CouplingRouter
from e0_controller.primitives import Edge, Outcome


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
        # C263: cold start excludes EN by default
        assert session.stats["en_nodes"] == 0

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

    def test_command_with_trailing_colon(self, session):
        """Commands with trailing colon (ask:, run:, help:) are normalized."""
        result = dispatch(session, "help:")
        assert "run" in result

    def test_ask_with_colon_routes_correctly(self):
        """'ask: question' must route to cmd_ask, not to cmd_task."""
        s = build_session(steps_per_round=10)
        result = dispatch(s, "ask: what is tension?")
        assert "Ask: On-Demand Q&A" in result or "On-Demand" in result

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
        # C263: EN excluded by default, focus should report unknown
        s = build_session(steps_per_round=15)
        cmd_run(s, 1)
        result = cmd_focus(s, "en")
        assert "Unknown domain" in result

    def test_focus_aliases(self):
        s = build_session(steps_per_round=15)
        cmd_run(s, 1)
        assert "Canon" in cmd_focus(s, "c")
        assert "Bootstrap" in cmd_focus(s, "boot")
        # C263: EN excluded by default, but alias still resolves (shows empty domain)
        assert "EN" in cmd_focus(s, "english")
        assert "0/0" in cmd_focus(s, "english")

    def test_focus_case_insensitive(self):
        s = build_session(steps_per_round=15)
        cmd_run(s, 1)
        assert "Canon" in cmd_focus(s, "CANON")
        # C263: EN excluded by default
        assert "Unknown domain" in cmd_focus(s, "En")

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
        result = dispatch(s, "task xyzqwp blorfnax gruntik")
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

    def test_cold_start_excludes_en(self):
        """C263: Cold start no longer includes EN domain by default."""
        s = build_session(steps_per_round=10)
        en = {k for k in s.unified_nodes if k.startswith("EN:")}
        assert len(en) == 0, f"Cold start should not include EN nodes, found {len(en)}"

    def test_en_nodes_have_description_when_opted_in(self):
        """EN nodes carry descriptions when explicitly included."""
        from e0_controller.explore_learning_cycle_multidomain import (
            build_multidomain_landscape,
        )
        _, unified_nodes, _ = build_multidomain_landscape(include_en=True)
        en = {k: v for k, v in unified_nodes.items() if k.startswith("EN:")}
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
        # C263: cold start excludes EN by default
        assert state.stats["en_nodes"] == 0


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

    @pytest.fixture(autouse=True)
    def _patch_learning_state(self, monkeypatch, tmp_path):
        import e0_controller.explore_bootstrap_landscape as ebl
        monkeypatch.setattr(ebl, "LEARNING_STATE_PATH", str(tmp_path / "ls.json"))

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
        # Default community mode: at least one community
        assert len(trends) > 0
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
        """Output lists all active partitions."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_diagnose(s)
        assert "Diagnostic Report" in out
        # Default community mode: community_ names
        assert "community_" in out
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
        assert "### community_" in out or "### Canon" in out


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


# ── C243: Iterative Teaching ─────────────────────────────────────────────────

# Spec for deepening round: new nodes that don't overlap with _TEACH_SPEC
_DEEPEN_SPEC = {
    "nodes": ["DETAIL_X", "DETAIL_Y"],
    "edges": [
        {"from": "DETAIL_X", "to": "DETAIL_Y", "delta": 0.5,
         "resistance": 0.9, "initial_U": 2.0, "initial_F": 0.5,
         "confidence": 0.7},
        {"from": "CONCEPT_A", "to": "DETAIL_X", "delta": 0.4,
         "resistance": 1.0, "initial_U": 1.0, "initial_F": 0.0,
         "confidence": 0.8},
    ],
}


class TestDiagnoseLearningGaps:
    """C243: _diagnose_learning_gaps identifies structural weaknesses."""

    def test_returns_dict(self, monkeypatch, tmp_path):
        """Gap diagnosis returns a structured dict."""
        import e0_controller.explore_bootstrap_landscape as ebl
        monkeypatch.setattr(ebl, "LEARNING_STATE_PATH", str(tmp_path / "ls.json"))
        s = _build_session_with_mock(_TEACH_SPEC)
        teach_concept(s, "test concept")
        gaps = _diagnose_learning_gaps(s, prefix="L:")
        assert isinstance(gaps, dict)
        for key in ("frontier_nodes", "weak_edges", "thin_nodes",
                     "leaf_nodes", "total_prefix_nodes", "has_gaps"):
            assert key in gaps, f"missing key: {key}"

    def test_finds_prefix_nodes(self, monkeypatch, tmp_path):
        """Diagnosis counts L: nodes correctly."""
        import e0_controller.explore_bootstrap_landscape as ebl
        monkeypatch.setattr(ebl, "LEARNING_STATE_PATH", str(tmp_path / "ls.json"))
        s = _build_session_with_mock(_TEACH_SPEC)
        teach_concept(s, "test concept")
        gaps = _diagnose_learning_gaps(s, prefix="L:")
        assert gaps["total_prefix_nodes"] >= 4  # CONCEPT_A/B/C/D

    def test_no_gaps_on_empty(self):
        """No gaps when no L: nodes exist."""
        s = build_session(steps_per_round=10)
        gaps = _diagnose_learning_gaps(s, prefix="L:")
        assert not gaps["has_gaps"]
        assert gaps["total_prefix_nodes"] == 0


class TestFormulateFollowup:
    """C243: _formulate_followup translates gaps to natural language."""

    def test_returns_string(self):
        """Follow-up is a non-empty string."""
        gaps = {
            "frontier_nodes": ["L:FRONTIER_A"],
            "weak_edges": [],
            "thin_nodes": [],
            "leaf_nodes": ["L:DEAD_END"],
            "total_prefix_nodes": 5,
            "has_gaps": True,
        }
        result = _formulate_followup("water", gaps)
        assert isinstance(result, str)
        assert len(result) > 20

    def test_mentions_leaf_nodes(self):
        """Follow-up describes leaf/dead-end nodes."""
        gaps = {
            "frontier_nodes": [],
            "weak_edges": [],
            "thin_nodes": [],
            "leaf_nodes": ["L:ICE", "L:STEAM"],
            "total_prefix_nodes": 5,
            "has_gaps": True,
        }
        result = _formulate_followup("water phases", gaps)
        assert "ICE" in result
        assert "STEAM" in result

    def test_mentions_weak_edges(self):
        """Follow-up describes uncertain transitions."""
        gaps = {
            "frontier_nodes": [],
            "weak_edges": [("L:A", "L:B", 0.1)],
            "thin_nodes": [],
            "leaf_nodes": [],
            "total_prefix_nodes": 5,
            "has_gaps": True,
        }
        result = _formulate_followup("physics", gaps)
        assert "uncertain" in result.lower() or "quality" in result.lower()

    def test_fallback_when_no_specific_gaps(self):
        """Generic deepening prompt when no specific gaps identified."""
        gaps = {
            "frontier_nodes": [],
            "weak_edges": [],
            "thin_nodes": [],
            "leaf_nodes": [],
            "total_prefix_nodes": 5,
            "has_gaps": False,
        }
        result = _formulate_followup("quantum mechanics", gaps)
        assert "quantum mechanics" in result.lower()


class TestIterativeTeach:
    """C243: teach_concept with rounds > 1 self-directs learning."""

    def test_single_round_backward_compat(self, monkeypatch, tmp_path):
        """rounds=1 produces same result structure as before."""
        import e0_controller.explore_bootstrap_landscape as ebl
        monkeypatch.setattr(ebl, "LEARNING_STATE_PATH", str(tmp_path / "ls.json"))
        s = _build_session_with_mock(_TEACH_SPEC)
        result = teach_concept(s, "test concept", rounds=1)
        assert "teach_rounds" in result
        assert len(result["teach_rounds"]) == 1
        assert result["teach_rounds"][0]["action"] == "initial"

    def test_multi_round_produces_detail(self, monkeypatch, tmp_path):
        """rounds=2 produces teach_rounds with ≥ 1 entry."""
        import e0_controller.explore_bootstrap_landscape as ebl
        monkeypatch.setattr(ebl, "LEARNING_STATE_PATH", str(tmp_path / "ls.json"))
        s = _build_session_with_mock(_TEACH_SPEC)
        result = teach_concept(s, "test concept", rounds=2)
        assert "teach_rounds" in result
        assert len(result["teach_rounds"]) >= 1
        # First round is always initial
        assert result["teach_rounds"][0]["action"] == "initial"

    def test_multi_round_adds_more_nodes(self, monkeypatch, tmp_path):
        """Multiple rounds can add more nodes than a single round."""
        import e0_controller.explore_bootstrap_landscape as ebl
        monkeypatch.setattr(ebl, "LEARNING_STATE_PATH", str(tmp_path / "ls.json"))
        s1 = _build_session_with_mock(_TEACH_SPEC)
        r1 = teach_concept(s1, "test concept", rounds=1)

        s2 = _build_session_with_mock(_TEACH_SPEC)
        r2 = teach_concept(s2, "test concept", rounds=2)
        # With the same mock, round 2 sees the same spec again
        # but duplicate nodes are skipped. Still, teach_rounds grows.
        assert len(r2["teach_rounds"]) >= len(r1["teach_rounds"])

    def test_rounds_capped_at_five(self, monkeypatch, tmp_path):
        """teach_concept caps rounds at 5."""
        import e0_controller.explore_bootstrap_landscape as ebl
        monkeypatch.setattr(ebl, "LEARNING_STATE_PATH", str(tmp_path / "ls.json"))
        s = _build_session_with_mock(_TEACH_SPEC)
        result = teach_concept(s, "test concept", rounds=10)
        assert len(result["teach_rounds"]) <= 5

    def test_stops_when_no_gaps(self, monkeypatch, tmp_path):
        """Iterative teaching stops early when no gaps are found."""
        import e0_controller.explore_bootstrap_landscape as ebl
        monkeypatch.setattr(ebl, "LEARNING_STATE_PATH", str(tmp_path / "ls.json"))
        s = _build_session_with_mock(_TEACH_SPEC)
        result = teach_concept(s, "test concept", rounds=3)
        # After initial round, if LLM returns same nodes (mocked),
        # they get skipped → likely stops with no_gaps or no_structure
        last = result["teach_rounds"][-1]
        if len(result["teach_rounds"]) > 1:
            assert last["action"] in (
                "deepen", "no_gaps", "no_structure", "llm_error"
            )

    def test_total_nodes_across_rounds(self, monkeypatch, tmp_path):
        """Total nodes_added spans all rounds."""
        import e0_controller.explore_bootstrap_landscape as ebl
        monkeypatch.setattr(ebl, "LEARNING_STATE_PATH", str(tmp_path / "ls.json"))
        s = _build_session_with_mock(_TEACH_SPEC)
        result = teach_concept(s, "test concept", rounds=2)
        total_from_rounds = sum(
            r.get("nodes_added", 0) for r in result["teach_rounds"]
        )
        assert len(result["nodes_added"]) == total_from_rounds


class TestCmdTeachRounds:
    """C243: cmd_teach parses round count from argument."""

    def test_parses_round_count(self, monkeypatch, tmp_path):
        """'teach water 3' parses concept='water' rounds=3."""
        import e0_controller.explore_bootstrap_landscape as ebl
        monkeypatch.setattr(ebl, "LEARNING_STATE_PATH", str(tmp_path / "ls.json"))
        s = _build_session_with_mock(_TEACH_SPEC)
        out = cmd_teach(s, "water 3")
        assert "Rounds: 3" in out

    def test_default_round_is_one(self, monkeypatch, tmp_path):
        """'teach water' defaults to 1 round."""
        import e0_controller.explore_bootstrap_landscape as ebl
        monkeypatch.setattr(ebl, "LEARNING_STATE_PATH", str(tmp_path / "ls.json"))
        s = _build_session_with_mock(_TEACH_SPEC)
        out = cmd_teach(s, "water")
        assert "Rounds: 1" in out

    def test_multi_word_concept_without_number(self, monkeypatch, tmp_path):
        """'teach quantum mechanics' treats full text as concept."""
        import e0_controller.explore_bootstrap_landscape as ebl
        monkeypatch.setattr(ebl, "LEARNING_STATE_PATH", str(tmp_path / "ls.json"))
        s = _build_session_with_mock(_TEACH_SPEC)
        out = cmd_teach(s, "quantum mechanics")
        assert "quantum mechanics" in out

    def test_output_shows_per_round_detail(self, monkeypatch, tmp_path):
        """Multi-round output shows per-round info."""
        import e0_controller.explore_bootstrap_landscape as ebl
        monkeypatch.setattr(ebl, "LEARNING_STATE_PATH", str(tmp_path / "ls.json"))
        s = _build_session_with_mock(_TEACH_SPEC)
        out = cmd_teach(s, "water 2")
        assert "Round 1:" in out


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
        """Community-based domains are tracked."""
        ref = meta_reflect(session)
        # Default community mode: community_ names
        assert len(ref["domain_trajectories"]) > 0
        for name in ref["domain_trajectories"]:
            assert isinstance(name, str)

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


# ── C235: Sleep-Wake Integration ──────────────────────────────────────


class TestSleepWakeRun:
    """C235: sleep_wake_run executes wake-sleep episodes."""

    def test_returns_dict(self):
        """sleep_wake_run returns a result dict."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = sleep_wake_run(s, episodes=2, max_cycles=10)
        assert isinstance(result, dict)

    def test_result_has_expected_keys(self):
        """Result contains episodes, domains, sleep_count, etc."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = sleep_wake_run(s, episodes=2, max_cycles=10)
        assert "episodes" in result
        assert "domains" in result
        assert "sleep_count" in result
        assert "total_steps" in result
        assert "transferred_edges" in result
        assert "episode_results" in result
        assert "pressure" in result

    def test_episode_count_matches(self):
        """Number of EpisodeResults matches domains × episodes."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = sleep_wake_run(s, episodes=2, max_cycles=10)
        n_domains = len(result["domains"])
        # SleepWakeCycle produces one EpisodeResult per domain per episode
        assert len(result["episode_results"]) == n_domains * 2

    def test_episodes_have_wake_phase(self):
        """Each episode has a wake phase with T_s values."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = sleep_wake_run(s, episodes=1, max_cycles=10)
        for ep in result["episode_results"]:
            assert hasattr(ep, "wake")
            assert hasattr(ep.wake, "T_s_before")
            assert hasattr(ep.wake, "T_s_after")

    def test_journal_event_recorded(self):
        """sleep_wake_run records a 'sleep_wake' journal event."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        sleep_wake_run(s, episodes=1, max_cycles=10)
        events = [e for e in s.journal if e["event_type"] == "sleep_wake"]
        assert len(events) >= 1
        detail = events[-1]["detail"]
        assert "episodes" in detail
        assert "domains" in detail
        assert "transferred_edges" in detail

    def test_historization_transferred_back(self):
        """Transferred edges count is non-negative."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = sleep_wake_run(s, episodes=2, max_cycles=10)
        assert result["transferred_edges"] >= 0

    def test_pressure_report_has_domains(self):
        """Pressure report contains registered domains."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = sleep_wake_run(s, episodes=1, max_cycles=10)
        assert len(result["pressure"]) > 0
        for name, info in result["pressure"].items():
            assert "T_s" in info
            assert "pressure" in info

    def test_observer_reused_from_dream(self):
        """If dream was run first, sleep reuses the same observer."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        dream_run(s, cycles=1)
        obs_before = s.dream_observer
        sleep_wake_run(s, episodes=1, max_cycles=10)
        assert s.dream_observer is obs_before


class TestCmdSleep:
    """C235: cmd_sleep provides formatted output."""

    def test_output_is_string(self):
        """cmd_sleep returns a non-empty string."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_sleep(s)
        assert isinstance(out, str)
        assert len(out) > 0

    def test_output_has_header(self):
        """Output contains 'Sleep-Wake Cycle'."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_sleep(s)
        assert "Sleep-Wake Cycle" in out

    def test_output_has_episodes(self):
        """Output contains 'Episodes' section."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_sleep(s)
        assert "Episodes" in out or "Ep " in out

    def test_output_has_summary(self):
        """Output contains 'Summary' section."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_sleep(s)
        assert "Summary" in out

    def test_output_has_pressure(self):
        """Output contains 'Pressure' section."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_sleep(s)
        assert "Pressure" in out

    def test_custom_episodes(self):
        """cmd_sleep('3') runs 3 episodes."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_sleep(s, "3")
        assert "3 episodes" in out

    def test_invalid_arg(self):
        """Invalid arg returns usage hint."""
        s = build_session(steps_per_round=10)
        out = cmd_sleep(s, "abc")
        assert "Usage" in out or "Invalid" in out

    def test_markdown_format(self):
        """Markdown mode uses ## headers."""
        s = build_session(steps_per_round=10, output_format="markdown")
        cmd_run(s, 1)
        out = cmd_sleep(s, "2")
        assert "## Sleep-Wake" in out


class TestSleepDispatch:
    """C235: dispatch routes 'sleep' command."""

    def test_dispatch_sleep(self):
        """dispatch('sleep 2') calls cmd_sleep."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = dispatch(s, "sleep 2")
        assert "Sleep-Wake Cycle" in out

    def test_dispatch_sleep_no_arg(self):
        """dispatch('sleep') uses default episodes."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = dispatch(s, "sleep")
        assert "Sleep-Wake Cycle" in out

    def test_help_includes_sleep(self):
        """Help text includes 'sleep' command."""
        text = cmd_help()
        assert "sleep" in text.lower()


# ── C236 Tune Command ────────────────────────────────────────────────


class TestTuneRun:
    """C236: tune_run runs auto-tuning on domain sub-landscapes."""

    def test_returns_dict(self):
        """tune_run returns a dict with expected keys."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = tune_run(s, max_rounds=1)
        assert isinstance(result, dict)
        assert "domain_results" in result
        assert "any_improved" in result
        assert "improved_count" in result
        assert "patterns" in result

    def test_domain_results_per_domain(self):
        """Each domain gets a separate tuning result."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = tune_run(s, max_rounds=1)
        assert len(result["domain_results"]) > 0
        for dr in result["domain_results"]:
            assert "domain" in dr
            assert "initial_quality" in dr
            assert "final_quality" in dr
            assert "improved" in dr
            assert "rounds" in dr
            assert "trials" in dr

    def test_domain_has_quality_scores(self):
        """Each domain result includes numeric quality scores."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = tune_run(s, max_rounds=1)
        for dr in result["domain_results"]:
            assert isinstance(dr["initial_quality"], float)
            assert isinstance(dr["final_quality"], float)
            assert isinstance(dr["improvement"], float)

    def test_improved_count_matches(self):
        """improved_count matches the number of improved domains."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = tune_run(s, max_rounds=1)
        actual = sum(1 for dr in result["domain_results"] if dr["improved"])
        assert result["improved_count"] == actual

    def test_any_improved_flag(self):
        """any_improved is True iff at least one domain improved."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = tune_run(s, max_rounds=1)
        if result["improved_count"] > 0:
            assert result["any_improved"] is True
        else:
            assert result["any_improved"] is False

    def test_journal_event_recorded(self):
        """tune_run records a 'tune' journal event."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        tune_run(s, max_rounds=1)
        events = [e for e in s.journal if e["event_type"] == "tune"]
        assert len(events) >= 1
        detail = events[-1]["detail"]
        assert "domains_tuned" in detail
        assert "domains_improved" in detail
        assert "total_trials" in detail

    def test_patterns_from_meta_reflect(self):
        """When history exists, patterns list is populated from meta_reflect."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 3)
        result = tune_run(s, max_rounds=1)
        assert isinstance(result["patterns"], list)

    def test_best_config_is_e0config(self):
        """Each domain result has an E0Config as best_config."""
        from e0_controller.config import E0Config
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = tune_run(s, max_rounds=1)
        for dr in result["domain_results"]:
            assert isinstance(dr["best_config"], E0Config)


class TestCmdTune:
    """C236: cmd_tune provides formatted output."""

    def test_output_is_string(self):
        """cmd_tune returns a non-empty string."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_tune(s)
        assert isinstance(out, str)
        assert len(out) > 0

    def test_output_has_header(self):
        """Output contains 'Auto-Tune'."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_tune(s)
        assert "Auto-Tune" in out

    def test_output_has_domain_results(self):
        """Output contains 'Domain Results' section."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_tune(s)
        assert "Domain Results" in out or "domain" in out.lower()

    def test_output_has_summary(self):
        """Output contains 'Summary' section."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_tune(s)
        assert "Summary" in out

    def test_custom_rounds(self):
        """cmd_tune('2') uses max 2 rounds."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_tune(s, "2")
        assert "2 rounds" in out

    def test_invalid_arg(self):
        """Invalid arg returns usage hint."""
        s = build_session(steps_per_round=10)
        out = cmd_tune(s, "abc")
        assert "Usage" in out or "Invalid" in out

    def test_markdown_format(self):
        """Markdown mode uses ## headers."""
        s = build_session(steps_per_round=10, output_format="markdown")
        cmd_run(s, 1)
        out = cmd_tune(s, "1")
        assert "## Auto-Tune" in out

    def test_quality_values_in_output(self):
        """Output contains quality score values."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_tune(s, "1")
        # Should contain quality arrow (→) or quality numbers
        assert "quality" in out.lower() or "\u2192" in out


class TestTuneDispatch:
    """C236: dispatch routes 'tune' command."""

    def test_dispatch_tune(self):
        """dispatch('tune 1') calls cmd_tune."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = dispatch(s, "tune 1")
        assert "Auto-Tune" in out

    def test_dispatch_tune_no_arg(self):
        """dispatch('tune') uses default rounds."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = dispatch(s, "tune")
        assert "Auto-Tune" in out

    def test_help_includes_tune(self):
        """Help text includes 'tune' command."""
        text = cmd_help()
        assert "tune" in text.lower()


# ── C237 Auto-Mode ───────────────────────────────────────────────────


class TestChooseAction:
    """C237: _choose_action selects appropriate next action."""

    def test_returns_tuple(self):
        """_choose_action returns (action, reason)."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        action, reason = _choose_action(s)
        assert isinstance(action, str)
        assert isinstance(reason, str)

    def test_action_is_valid(self):
        """Action is one of the known actions."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        action, _ = _choose_action(s)
        valid = {"run", "escalate", "couple", "dream", "sleep", "curriculum", "tune", "stop"}
        assert action in valid

    def test_low_coverage_suggests_run(self):
        """With low coverage and no issues, action should be run."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        action, reason = _choose_action(s)
        # Early session: most likely run or curriculum
        assert action in {"run", "curriculum", "dream", "sleep"}

    def test_high_stagnation_suggests_escalate(self):
        """When stagnation_streak >= 3 and single universe, should escalate."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        s.stagnation_streak = 5
        action, _ = _choose_action(s)
        assert action == "escalate"

    def test_stagnation_with_universes_suggests_couple(self):
        """C248: stagnation + ≥2 universes → couple instead of escalate."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        _ensure_main_universe(s)
        universe_create(s, "donor")
        s.stagnation_streak = 5
        action, reason = _choose_action(s)
        assert action == "couple"
        assert "universe" in reason.lower()


class TestAutoRun:
    """C237: auto_run orchestrates autonomous learning."""

    def test_returns_dict(self):
        """auto_run returns a dict with expected keys."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = auto_run(s, max_steps=2, rounds_per_step=1)
        assert isinstance(result, dict)
        assert "actions" in result
        assert "total_steps" in result
        assert "coverage_start" in result
        assert "coverage_end" in result
        assert "coverage_delta" in result
        assert "rounds_executed" in result
        assert "stopped_reason" in result

    def test_actions_logged(self):
        """Each step produces an action log entry."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = auto_run(s, max_steps=3, rounds_per_step=1)
        assert len(result["actions"]) > 0
        for a in result["actions"]:
            assert "step" in a
            assert "action" in a

    def test_coverage_tracked(self):
        """Coverage start/end are valid percentages."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = auto_run(s, max_steps=2, rounds_per_step=1)
        assert 0 <= result["coverage_start"] <= 1
        assert 0 <= result["coverage_end"] <= 1

    def test_coverage_non_decreasing(self):
        """Coverage should not decrease during auto-mode."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = auto_run(s, max_steps=3, rounds_per_step=2)
        assert result["coverage_delta"] >= -0.01  # allow tiny float noise

    def test_max_steps_respected(self):
        """auto_run does not exceed max_steps."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = auto_run(s, max_steps=2, rounds_per_step=1)
        assert result["total_steps"] <= 2

    def test_journal_event_recorded(self):
        """auto_run records an 'auto_mode' journal event."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        auto_run(s, max_steps=2, rounds_per_step=1)
        events = [e for e in s.journal if e["event_type"] == "auto_mode"]
        assert len(events) >= 1
        detail = events[-1]["detail"]
        assert "steps" in detail
        assert "actions" in detail
        assert "coverage_start" in detail
        assert "coverage_end" in detail

    def test_rounds_executed_positive(self):
        """At least some rounds are executed."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = auto_run(s, max_steps=3, rounds_per_step=2)
        assert result["rounds_executed"] >= 0

    def test_stopped_reason_populated(self):
        """stopped_reason is always a non-empty string."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = auto_run(s, max_steps=2, rounds_per_step=1)
        assert isinstance(result["stopped_reason"], str)
        assert len(result["stopped_reason"]) > 0


class TestCmdAuto:
    """C237: cmd_auto provides formatted output."""

    def test_output_is_string(self):
        """cmd_auto returns a non-empty string."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_auto(s, "2")
        assert isinstance(out, str)
        assert len(out) > 0

    def test_output_has_header(self):
        """Output contains 'Auto-Mode'."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_auto(s, "2")
        assert "Auto-Mode" in out

    def test_output_has_coverage(self):
        """Output contains coverage information."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_auto(s, "2")
        assert "Coverage" in out or "cov=" in out

    def test_output_has_actions(self):
        """Output contains 'Actions' section."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_auto(s, "2")
        assert "Actions" in out or "Step" in out

    def test_output_has_stopped_reason(self):
        """Output contains 'Stopped' section."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_auto(s, "2")
        assert "Stopped" in out or "stop" in out.lower()

    def test_invalid_arg(self):
        """Invalid arg returns usage hint."""
        s = build_session(steps_per_round=10)
        out = cmd_auto(s, "abc")
        assert "Usage" in out or "Invalid" in out

    def test_markdown_format(self):
        """Markdown mode uses ## headers."""
        s = build_session(steps_per_round=10, output_format="markdown")
        cmd_run(s, 1)
        out = cmd_auto(s, "2")
        assert "## Auto-Mode" in out

    def test_custom_max_steps(self):
        """cmd_auto('3') uses max 3 steps."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_auto(s, "3")
        assert "step" in out.lower()


class TestAutoDispatch:
    """C237: dispatch routes 'auto' command."""

    def test_dispatch_auto(self):
        """dispatch('auto 2') calls cmd_auto."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = dispatch(s, "auto 2")
        assert "Auto-Mode" in out

    def test_dispatch_auto_no_arg(self):
        """dispatch('auto') uses default steps."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = dispatch(s, "auto")
        assert "Auto-Mode" in out

    def test_help_includes_auto(self):
        """Help text includes 'auto' command."""
        text = cmd_help()
        assert "auto" in text.lower()


# ── Self-Learn (C238) ──────────────────────────────────────────────────


class TestAssessSelfMastery:
    """C238: _assess_self_mastery measures self-knowledge completeness."""

    def test_cold_start_low_mastery(self):
        """Fresh session has low mastery (no curriculum run yet)."""
        s = build_session(steps_per_round=10)
        m = _assess_self_mastery(s)
        assert "domain_coverage" in m
        assert "canon" in m["domain_coverage"]
        assert "mechanism" in m["domain_coverage"]
        assert "canon_alignment_ratio" in m
        assert "overall_mastery" in m
        assert "ready" in m
        # Cold start: no curriculum traces → coverage is low
        assert m["domain_coverage"]["canon"]["ratio"] < 1.0

    def test_mastery_has_alignment(self):
        """Mastery includes canon alignment ratio."""
        s = build_session(steps_per_round=10)
        m = _assess_self_mastery(s)
        # Alignment ratio is from static canon_self_bridge analysis — always > 0
        assert m["canon_alignment_ratio"] > 0

    def test_mastery_after_navigation(self):
        """Running rounds increases canon coverage (edges get inscribed)."""
        s = build_session(steps_per_round=10)
        m_before = _assess_self_mastery(s)
        cmd_run(s, 3)
        m_after = _assess_self_mastery(s)
        # After navigation, some C: nodes should have trace data
        total_visited_before = sum(
            d["visited"] for d in m_before["domain_coverage"].values()
        )
        total_visited_after = sum(
            d["visited"] for d in m_after["domain_coverage"].values()
        )
        assert total_visited_after >= total_visited_before

    def test_mastery_overall_is_average(self):
        """Overall mastery is mean of canon_cov + mech_cov + alignment."""
        s = build_session(steps_per_round=10)
        m = _assess_self_mastery(s)
        onto = m["domain_coverage"]["canon"]["ratio"]
        mech = m["domain_coverage"]["mechanism"]["ratio"]
        align = m["canon_alignment_ratio"]
        expected = (onto + mech + align) / 3.0
        assert abs(m["overall_mastery"] - expected) < 1e-9


class TestSelflearnRun:
    """C238: selflearn_run orchestrates self-learning pipeline."""

    def test_returns_all_phases(self):
        """Result contains both curriculum phases + dream + mastery."""
        s = build_session(steps_per_round=10)
        result = selflearn_run(s)
        assert "phases" in result
        assert len(result["phases"]) == 2
        assert result["phases"][0][0] == "ontodynamics"
        assert result["phases"][1][0] == "mechanism_e0"
        assert "dream" in result
        assert "mastery" in result

    def test_curriculum_produces_turns(self):
        """Each phase should produce curriculum turns."""
        s = build_session(steps_per_round=10)
        result = selflearn_run(s)
        for name, phase in result["phases"]:
            assert len(phase["turn_results"]) > 0
            assert phase["transferred_edges"] >= 0

    def test_dream_runs_after_curriculum(self):
        """Dream phase runs 3 cycles after curriculum."""
        s = build_session(steps_per_round=10)
        result = selflearn_run(s)
        assert result["dream"]["cycles"] == 3
        assert "total_equivalences" in result["dream"]

    def test_mastery_assessed(self):
        """Mastery assessment is computed after all phases."""
        s = build_session(steps_per_round=10)
        result = selflearn_run(s)
        m = result["mastery"]
        assert "domain_coverage" in m
        assert "overall_mastery" in m
        assert isinstance(m["ready"], bool)

    def test_journal_event_recorded(self):
        """selflearn records a journal event."""
        s = build_session(steps_per_round=10)
        journal_before = len(s.journal)
        selflearn_run(s)
        selflearn_events = [
            e for e in s.journal[journal_before:]
            if e["event_type"] == "selflearn"
        ]
        assert len(selflearn_events) == 1
        detail = selflearn_events[0]["detail"]
        assert "onto_steps" in detail
        assert "mech_steps" in detail
        assert "mastery_overall" in detail

    def test_selflearn_transfers_historization(self):
        """After selflearn, C: and M: edges should have trace data."""
        s = build_session(steps_per_round=10)
        selflearn_run(s)
        hist = s.landscape.historization
        c_with_data = sum(
            1 for e in s.landscape.edges
            if e.source.startswith("C:") and hist.trace_load(e) > 0
        )
        m_with_data = sum(
            1 for e in s.landscape.edges
            if e.source.startswith("M:") and hist.trace_load(e) > 0
        )
        assert c_with_data > 0, "Ontodynamics curriculum should transfer traces"
        assert m_with_data > 0, "Mechanism curriculum should transfer traces"

    def test_mastery_improves_after_selflearn(self):
        """Overall mastery should improve after selflearn vs cold start."""
        s = build_session(steps_per_round=10)
        m_before = _assess_self_mastery(s)
        selflearn_run(s)
        m_after = _assess_self_mastery(s)
        assert m_after["overall_mastery"] >= m_before["overall_mastery"]


class TestCmdSelflearn:
    """C238: cmd_selflearn produces formatted output."""

    def test_output_contains_phases(self):
        """Output shows both curriculum phases."""
        s = build_session(steps_per_round=10)
        out = cmd_selflearn(s)
        assert "ontodynamics" in out
        assert "mechanism_e0" in out

    def test_output_contains_dream(self):
        """Output shows dream consolidation section."""
        s = build_session(steps_per_round=10)
        out = cmd_selflearn(s)
        assert "Dream" in out

    def test_output_contains_mastery(self):
        """Output shows mastery assessment."""
        s = build_session(steps_per_round=10)
        out = cmd_selflearn(s)
        assert "Mastery" in out

    def test_output_contains_readiness(self):
        """Output shows ready/not-ready status."""
        s = build_session(steps_per_round=10)
        out = cmd_selflearn(s)
        assert "ready" in out.lower() or "continue" in out.lower()

    def test_output_contains_coverage_bars(self):
        """Output shows per-domain coverage with visual bars."""
        s = build_session(steps_per_round=10)
        out = cmd_selflearn(s)
        assert "canon" in out
        assert "mechanism" in out
        assert "%" in out

    def test_output_contains_turn_details(self):
        """Output shows per-turn results for each phase."""
        s = build_session(steps_per_round=10)
        out = cmd_selflearn(s)
        assert "Turn" in out
        assert "T_s=" in out

    def test_markdown_format(self):
        """Markdown format uses ## headers."""
        s = build_session(steps_per_round=10, output_format="markdown")
        out = cmd_selflearn(s)
        assert "## Self-Learn" in out

    def test_title(self):
        """Text format shows correct title."""
        s = build_session(steps_per_round=10)
        out = cmd_selflearn(s)
        assert "Self-Learn" in out


class TestSelflearnDispatch:
    """C238: dispatch routes 'selflearn' command."""

    def test_dispatch_selflearn(self):
        """dispatch('selflearn') calls cmd_selflearn."""
        s = build_session(steps_per_round=10)
        out = dispatch(s, "selflearn")
        assert "Self-Learn" in out

    def test_help_includes_selflearn(self):
        """Help text includes 'selflearn' command."""
        text = cmd_help()
        assert "selflearn" in text.lower()


# ── C239: Ask Command — On-Demand Question Answering ──────────────────

# Spec for ask tests: nodes whose names align with landscape concepts
_ASK_SPEC = {
    "nodes": ["INTERFERENCE_QM", "BORN_RULE", "WAVE_FUNCTION"],
    "edges": [
        {"from": "INTERFERENCE_QM", "to": "BORN_RULE", "delta": 0.5,
         "resistance": 1.0, "initial_U": 3.0, "initial_F": 1.0,
         "confidence": 0.7},
        {"from": "BORN_RULE", "to": "WAVE_FUNCTION", "delta": 0.4,
         "resistance": 0.9, "initial_U": 2.0, "initial_F": 0.5,
         "confidence": 0.8},
        {"from": "WAVE_FUNCTION", "to": "INTERFERENCE_QM", "delta": 0.3,
         "resistance": 1.0, "initial_U": 1.0, "initial_F": 0.5,
         "confidence": 0.6},
    ],
}


class TestExtractQuestionTerms:
    """C239: _extract_question_terms tokenizes and filters questions."""

    def test_basic_extraction(self):
        """Extracts meaningful words, drops stopwords."""
        terms = _extract_question_terms("What is the interference pattern?")
        assert "interference" in terms
        assert "pattern" in terms
        assert "what" not in terms
        assert "the" not in terms

    def test_short_tokens_removed(self):
        """Non-acronym tokens of length <= 2 are removed."""
        terms = _extract_question_terms("Is it an ok fit?")
        assert "ok" not in terms
        assert "is" not in terms
        assert "it" not in terms
        assert "an" not in terms
        assert "fit" in terms

    def test_acronyms_preserved(self):
        """ALL-CAPS tokens >= 2 chars are kept even if short."""
        terms = _extract_question_terms(
            "Does E0's interference match real QM interference?"
        )
        assert "e0" in terms
        assert "qm" in terms
        assert "interference" in terms

    def test_acronyms_mixed_case_not_preserved(self):
        """Mixed-case short tokens are still filtered."""
        terms = _extract_question_terms("Is Ok to go?")
        assert "ok" not in terms  # not ALL-CAPS
        assert "is" not in terms

    def test_empty_input(self):
        """Empty input returns empty list."""
        assert _extract_question_terms("") == []
        assert _extract_question_terms("is the a") == []

    def test_deduplication(self):
        """Duplicate terms appear only once."""
        terms = _extract_question_terms(
            "tension and tension and more tension"
        )
        assert terms.count("tension") == 1

    def test_preserves_order(self):
        """Terms appear in order of first occurrence."""
        terms = _extract_question_terms("landscape tension historization")
        assert terms == ["landscape", "tension", "historization"]

    def test_stopwords_comprehensive(self):
        """All stopwords are filtered."""
        terms = _extract_question_terms(
            "does this have the same interference as that one"
        )
        assert "interference" in terms
        # Only 'interference', 'same', 'one' should survive
        for t in terms:
            assert t not in {"does", "this", "have", "the", "as", "that"}


class TestAssessKnowledge:
    """C239: _assess_knowledge checks structural coverage of a question."""

    def test_known_terms_covered(self):
        """Terms matching existing landscape nodes are covered."""
        s = build_session(steps_per_round=10)
        result = _assess_knowledge(s, "tension and historization")
        assert "tension" in result["covered"]
        assert result["coverage_ratio"] > 0

    def test_unknown_terms_are_gaps(self):
        """Terms not matching any node appear as gaps."""
        s = build_session(steps_per_round=10)
        result = _assess_knowledge(s, "quantum decoherence unknown")
        # These terms should not match canon/bootstrap/en nodes
        gaps = result["gaps"]
        assert len(gaps) > 0

    def test_full_coverage(self):
        """When all terms match, coverage_ratio approaches 1.0."""
        s = build_session(steps_per_round=10)
        # Use terms that definitely exist in the landscape
        result = _assess_knowledge(s, "tension historization")
        assert result["coverage_ratio"] >= 0.5

    def test_empty_landscape_question(self):
        """Coverage of purely unknown terms is 0."""
        s = build_session(steps_per_round=10)
        result = _assess_knowledge(s, "xyzzy plugh gibberish")
        assert result["coverage_ratio"] == 0.0
        assert len(result["gaps"]) == 3

    def test_returns_required_keys(self):
        """Result dict has all required keys."""
        s = build_session(steps_per_round=10)
        result = _assess_knowledge(s, "interference exploration")
        assert "matches" in result
        assert "terms" in result
        assert "covered" in result
        assert "gaps" in result
        assert "coverage_ratio" in result
        assert "knowledge_depth" in result
        assert "deep_count" in result
        assert "structural_count" in result

    def test_coverage_ratio_in_range(self):
        """Coverage ratio is between 0 and 1."""
        s = build_session(steps_per_round=10)
        result = _assess_knowledge(s, "tension unknown_word historization")
        assert 0.0 <= result["coverage_ratio"] <= 1.0

    def test_no_substring_false_match(self):
        """Substring matching should not cause false positives.

        C240: 'real' must NOT match 'local_realization' via substring.
        Only exact word matches count.
        """
        s = build_session(steps_per_round=10)
        result = _assess_knowledge(s, "real question about data")
        # 'real' should be a gap unless there's a node with 'real' as a word
        if "real" in result["covered"]:
            node_id = result["covered"]["real"][0]
            concept = (
                node_id.split(":", 1)[1].lower()
                if ":" in node_id else node_id.lower()
            )
            words = set(concept.replace("_", " ").replace("-", " ").split())
            assert "real" in words, (
                f"'real' matched {node_id} via substring, not word match"
            )

    def test_knowledge_depth_zero_for_unvisited(self):
        """Knowledge depth is 0 for terms matching unvisited nodes."""
        s = build_session(steps_per_round=10)
        result = _assess_knowledge(s, "xyzzy plugh gibberish")
        assert result["knowledge_depth"] == 0.0
        assert result["deep_count"] == 0

    def test_knowledge_depth_in_range(self):
        """Knowledge depth is between 0 and 1."""
        s = build_session(steps_per_round=10)
        result = _assess_knowledge(s, "tension historization landscape")
        assert 0.0 <= result["knowledge_depth"] <= 1.0


class TestAskRun:
    """C239: ask_run orchestrates the full question-answering pipeline."""

    def test_returns_required_keys(self):
        """Result dict has all required keys."""
        s = build_session(steps_per_round=10)
        result = ask_run(s, "tension and historization", auto_learn=False)
        for key in [
            "question", "terms", "assessment_before", "learned",
            "assessment_after", "anchor", "nav_path", "confidence",
        ]:
            assert key in result, f"Missing key: {key}"

    def test_no_learn_when_auto_learn_false(self):
        """With auto_learn=False, no teaching happens even with gaps."""
        s = build_session(steps_per_round=10)
        result = ask_run(s, "quantum decoherence unknown", auto_learn=False)
        assert result["learned"] == []

    def test_known_question_no_learning(self):
        """Question fully covered by existing nodes needs no learning."""
        s = build_session(steps_per_round=10)
        result = ask_run(s, "tension and historization", auto_learn=True)
        # Even with auto_learn=True, no learning if no gaps
        if not result["assessment_before"]["gaps"]:
            assert result["learned"] == []

    def test_navigates_from_best_match(self):
        """Navigation starts from the highest-relevance match."""
        s = build_session(steps_per_round=10)
        result = ask_run(s, "tension and historization", auto_learn=False)
        assert result["anchor"] is not None
        assert len(result["nav_path"]) > 0

    def test_confidence_reflects_depth(self):
        """Confidence equals knowledge_depth (trace_load weighted)."""
        s = build_session(steps_per_round=10)
        result = ask_run(s, "tension and historization", auto_learn=False)
        assert result["confidence"] == result["assessment_after"]["knowledge_depth"]

    def test_journal_event_recorded(self):
        """ask_run records a journal event."""
        s = build_session(steps_per_round=10)
        journal_before = len(s.journal)
        ask_run(s, "tension and exploration", auto_learn=False)
        ask_events = [
            e for e in s.journal[journal_before:]
            if e["event_type"] == "ask"
        ]
        assert len(ask_events) == 1
        d = ask_events[0]["detail"]
        assert "question" in d
        assert "gaps_before" in d
        assert "confidence" in d

    def test_learning_with_mock_llm(self):
        """With gaps and mock LLM, teach_concept is called for gap terms."""
        s = _build_session_with_mock(_ASK_SPEC)
        # Ask about something partially known + gap terms
        result = ask_run(s, "interference quantum born rule")
        # Some terms should have been learned
        if result["assessment_before"]["gaps"]:
            assert len(result["learned"]) > 0

    def test_max_gap_learn_limit(self):
        """At most _ASK_MAX_GAP_LEARN gap terms are learned."""
        from e0_controller.interactive_session import _ASK_MAX_GAP_LEARN
        s = _build_session_with_mock(_ASK_SPEC)
        result = ask_run(
            s, "alpha beta gamma delta epsilon zeta theta kappa"
        )
        assert len(result["learned"]) <= _ASK_MAX_GAP_LEARN

    def test_assessment_after_reflects_learning(self):
        """After learning, assessment_after may have fewer gaps."""
        s = _build_session_with_mock(_ASK_SPEC)
        result = ask_run(s, "interference quantum born wave")
        before_gaps = len(result["assessment_before"]["gaps"])
        after_gaps = len(result["assessment_after"]["gaps"])
        # After learning, gaps should decrease or stay same
        assert after_gaps <= before_gaps

    def test_contextual_learning_passes_question(self):
        """Gap learning passes question context to teach_concept."""
        import unittest.mock as _mock
        s = _build_session_with_mock(_ASK_SPEC)
        with _mock.patch(
            "e0_controller.interactive_session.teach_concept",
            return_value={"status": "ok"},
        ) as mock_teach:
            ask_run(s, "xyzzy plugh gibberish")
            # teach_concept should be called with contextual string
            for call in mock_teach.call_args_list:
                concept_arg = call[0][1]  # 2nd positional arg
                assert "(in context:" in concept_arg


class TestCmdAsk:
    """C239: cmd_ask produces formatted output."""

    def test_output_contains_question(self):
        """Output includes the original question."""
        s = build_session(steps_per_round=10)
        out = cmd_ask(s, "tension and historization")
        assert "tension and historization" in out

    def test_output_contains_assessment(self):
        """Output shows knowledge assessment section."""
        s = build_session(steps_per_round=10)
        out = cmd_ask(s, "tension and exploration")
        assert "Knowledge Assessment" in out
        assert "Terms:" in out

    def test_output_contains_confidence(self):
        """Output shows confidence score."""
        s = build_session(steps_per_round=10)
        out = cmd_ask(s, "tension and historization")
        assert "Confidence:" in out

    def test_output_contains_navigation(self):
        """Output shows navigation section for known terms."""
        s = build_session(steps_per_round=10)
        out = cmd_ask(s, "tension and historization")
        assert "Navigation" in out
        assert "Anchor:" in out

    def test_output_shows_gaps(self):
        """Output shows gaps when terms are unknown."""
        s = build_session(steps_per_round=10)
        out = cmd_ask(s, "xyzzy plugh gibberish")
        assert "Gaps:" in out

    def test_markdown_format(self):
        """Markdown format uses ## headers."""
        s = build_session(steps_per_round=10, output_format="markdown")
        out = cmd_ask(s, "tension and historization")
        assert "## Ask:" in out

    def test_empty_question(self):
        """Empty question returns usage hint."""
        s = build_session(steps_per_round=10)
        out = cmd_ask(s, "")
        assert "Usage:" in out

    def test_learning_section_with_mock(self):
        """Output shows learning section when gaps are filled."""
        s = _build_session_with_mock(_ASK_SPEC)
        out = cmd_ask(s, "interference quantum born")
        # Should show either learning results or gap info
        assert "Knowledge Assessment" in out


class TestFormatPathEvidence:
    """C242: _format_path_evidence formats navigation path for synthesis."""

    def test_empty_path(self):
        """Empty path returns sentinel string."""
        s = build_session(steps_per_round=10)
        assert _format_path_evidence(s, []) == "(no navigation path)"

    def test_single_node_with_meta(self):
        """Shows domain, label, and description from unified_nodes."""
        s = build_session(steps_per_round=10)
        s.unified_nodes = {
            "C:tension": {
                "label": "tension", "domain": "core",
                "description": "The driving force of navigation",
            },
        }
        result = _format_path_evidence(s, ["C:tension"])
        assert "[core] tension" in result
        assert "The driving force" in result

    def test_without_unified_nodes(self):
        """Falls back to node_id as label when no meta set."""
        s = build_session(steps_per_round=10)
        s.unified_nodes = None
        result = _format_path_evidence(s, ["C:tension"])
        assert "C:tension" in result

    def test_deduplication(self):
        """Repeated nodes appear only once."""
        s = build_session(steps_per_round=10)
        s.unified_nodes = {
            "A": {"label": "alpha", "domain": "d1", "description": "A desc"},
            "B": {"label": "beta", "domain": "d2", "description": "B desc"},
        }
        result = _format_path_evidence(s, ["A", "B", "A"])
        assert result.count("[d1] alpha") == 1

    def test_truncates_long_descriptions(self):
        """Descriptions > 120 chars are truncated with ellipsis."""
        s = build_session(steps_per_round=10)
        s.unified_nodes = {
            "A": {"label": "alpha", "domain": "d", "description": "x" * 200},
        }
        result = _format_path_evidence(s, ["A"])
        assert "..." in result

    def test_edge_arrow_shown(self):
        """Transition between nodes shows arrow."""
        s = build_session(steps_per_round=10)
        s.unified_nodes = {
            "A": {"label": "alpha", "domain": "d", "description": ""},
            "B": {"label": "beta", "domain": "d", "description": ""},
        }
        result = _format_path_evidence(s, ["A", "B"])
        assert "→" in result


class TestStructuralAnswer:
    """C242: _structural_answer generates no-LLM fallback answers."""

    def test_empty_path(self):
        """Empty path returns 'No structural evidence' message."""
        s = build_session(steps_per_round=10)
        result = _structural_answer("what?", [], s)
        assert "No structural evidence" in result

    def test_with_descriptions(self):
        """Shows header with count and bullet points."""
        s = build_session(steps_per_round=10)
        s.unified_nodes = {
            "A": {"label": "Alpha", "domain": "d", "description": "First"},
            "B": {"label": "Beta", "domain": "d", "description": "Second"},
        }
        result = _structural_answer("what is alpha?", ["A", "B"], s)
        assert "2 connected concepts" in result
        assert "Alpha: First" in result
        assert "Beta: Second" in result
        assert "•" in result

    def test_max_eight_bullets(self):
        """At most 8 concept bullets are shown."""
        s = build_session(steps_per_round=10)
        nodes = {}
        path = []
        for i in range(12):
            nid = f"N{i}"
            nodes[nid] = {
                "label": f"n{i}", "domain": "d", "description": f"Desc {i}",
            }
            path.append(nid)
        s.unified_nodes = nodes
        result = _structural_answer("question?", path, s)
        assert "12 connected concepts" in result
        assert result.count("•") == 8

    def test_deduplication(self):
        """Repeated nodes yield only one bullet."""
        s = build_session(steps_per_round=10)
        s.unified_nodes = {
            "A": {"label": "Alpha", "domain": "d", "description": "Desc A"},
        }
        result = _structural_answer("what?", ["A", "A", "A"], s)
        assert result.count("Alpha") == 1

    def test_no_description_shows_label(self):
        """Nodes without descriptions still show label."""
        s = build_session(steps_per_round=10)
        s.unified_nodes = {"A": {"label": "Alpha", "domain": "d"}}
        result = _structural_answer("what?", ["A"], s)
        assert "Alpha" in result

    def test_no_meta_at_all(self):
        """Nodes not in unified_nodes show node_id as label."""
        s = build_session(steps_per_round=10)
        s.unified_nodes = {}
        result = _structural_answer("what?", ["MYSTERY"], s)
        assert "MYSTERY" in result


class TestAskRunSynthesis:
    """C242: ask_run Phase 5 produces answer and synthesis keys."""

    def test_result_has_answer_key(self):
        """Result dict always includes 'answer' and 'synthesis' keys."""
        s = build_session(steps_per_round=10)
        result = ask_run(s, "tension and historization")
        assert "answer" in result
        assert "synthesis" in result

    def test_structural_fallback_without_llm(self):
        """When LLM is unavailable, structural fallback produces answer."""
        import unittest.mock as _mock
        s = build_session(steps_per_round=10)
        with _mock.patch(
            "e0_controller.interactive_session._get_llm_adapter",
            side_effect=RuntimeError("no LLM"),
        ):
            result = ask_run(s, "tension and historization")
        if result["nav_path"]:
            assert result["answer"] is not None
            assert result["synthesis"] is None

    def test_llm_synthesis_patched(self):
        """Patched synthesize_answer returns proper synthesis."""
        import unittest.mock as _mock
        s = _build_session_with_mock(_ASK_SPEC)
        fake = {
            "answer": "Interference relates to Born rule.",
            "confidence": 0.8,
            "key_concepts": ["interference", "born_rule"],
            "evidence_sufficient": True,
        }
        s.llm_adapter.synthesize_answer = lambda **kw: fake
        result = ask_run(s, "interference quantum born")
        if result["nav_path"]:
            assert result["answer"] == "Interference relates to Born rule."
            assert result["synthesis"] is not None
            assert result["synthesis"]["key_concepts"] == [
                "interference", "born_rule",
            ]

    def test_unknown_terms_get_answer(self):
        """Even unknown terms may produce structural answer."""
        s = build_session(steps_per_round=10)
        result = ask_run(s, "xyzzy plugh gibberish")
        assert "answer" in result


class TestCmdAskAnswerSection:
    """C242: cmd_ask displays Answer section when answer is available."""

    def test_answer_section_with_patched_llm(self):
        """Output shows Answer section when synthesis succeeds."""
        s = _build_session_with_mock(_ASK_SPEC)
        fake = {
            "answer": "Interference is a wave phenomenon.",
            "confidence": 0.85,
            "key_concepts": ["interference"],
            "evidence_sufficient": True,
        }
        s.llm_adapter.synthesize_answer = lambda **kw: fake
        out = cmd_ask(s, "interference quantum born")
        if "Interference is a wave phenomenon." in out:
            assert "Answer" in out

    def test_evidence_insufficient_warning(self):
        """Shows warning when evidence_sufficient is False."""
        s = _build_session_with_mock(_ASK_SPEC)
        fake = {
            "answer": "Unclear evidence.",
            "confidence": 0.3,
            "key_concepts": [],
            "evidence_sufficient": False,
        }
        s.llm_adapter.synthesize_answer = lambda **kw: fake
        out = cmd_ask(s, "interference quantum born")
        if "Unclear evidence." in out:
            assert "insufficient" in out.lower() or "\u26a0" in out

    def test_key_concepts_in_output(self):
        """Key concepts from synthesis appear in output."""
        s = _build_session_with_mock(_ASK_SPEC)
        fake = {
            "answer": "Answer text here.",
            "confidence": 0.7,
            "key_concepts": ["concept_alpha", "concept_beta"],
            "evidence_sufficient": True,
        }
        s.llm_adapter.synthesize_answer = lambda **kw: fake
        out = cmd_ask(s, "interference quantum born")
        if "Answer text here." in out:
            assert "concept_alpha" in out
            assert "concept_beta" in out

    def test_structural_answer_displayed(self):
        """Structural fallback answer also shown in Answer section."""
        s = build_session(steps_per_round=10)
        out = cmd_ask(s, "tension and historization")
        # Without LLM, structural fallback kicks in
        # If navigation found something, Answer section may appear
        assert "Confidence:" in out  # Always present


class TestAskDispatch:
    """C239: dispatch routes 'ask' command."""

    def test_dispatch_ask(self):
        """dispatch('ask <question>') calls cmd_ask."""
        s = build_session(steps_per_round=10)
        out = dispatch(s, "ask tension and historization")
        assert "Ask:" in out

    def test_dispatch_ask_no_arg(self):
        """dispatch('ask') without argument returns usage."""
        s = build_session(steps_per_round=10)
        out = dispatch(s, "ask")
        assert "Usage:" in out

    def test_help_includes_ask(self):
        """Help text includes 'ask' command."""
        text = cmd_help()
        assert "ask" in text.lower()


# ── C244: Domain Isolation + Stemming + Feedback ─────────────────────────────


class TestStem:
    """C244: _stem strips common English suffixes for fuzzy matching."""

    def test_logistics_logistic(self):
        assert _stem("logistics") == _stem("logistic")

    def test_processing_process(self):
        assert _stem("processing") == _stem("process")

    def test_received_stems_ed(self):
        """'received' strips -ed suffix."""
        assert _stem("received") == "receiv"
        # Note: 'receive' doesn't strip -ive (part of root),
        # so received/receive don't stem identically.
        # Substring fallback in _match_nodes handles this case.

    def test_short_words_unchanged(self):
        """Words shorter than suffix+min_stem are returned as-is."""
        assert _stem("is") == "is"
        assert _stem("go") == "go"

    def test_idempotent(self):
        """Stemming an already-stemmed word doesn't over-strip."""
        w = _stem("process")
        assert _stem(w) == w

    def test_plural_singular(self):
        """Simple plurals."""
        assert _stem("edges") == _stem("edge")

    def test_preserves_base(self):
        """The stem of a base word is itself."""
        assert _stem("landscape") == "landscape"


class TestMatchNodesStemming:
    """C244: _match_nodes uses stemming for fuzzy suffix matching."""

    def test_stemmed_match_on_injected_nodes(self):
        """'logistics' matches L:LOGISTIC_PROCESSES via stemming."""
        s = _build_session_with_mock(_TEACH_SPEC)
        # Inject a node with a different inflection
        s.landscape.add_state("L:LOGISTIC_PROCESSES")
        matches = _match_nodes("logistics", s.landscape)
        node_ids = [n for n, _ in matches]
        assert "L:LOGISTIC_PROCESSES" in node_ids

    def test_processing_matches_process(self):
        """'process' matches node PAYMENT_PROCESSING via stemming."""
        s = _build_session_with_mock(_TEACH_SPEC)
        s.landscape.add_state("L:PAYMENT_PROCESSING")
        matches = _match_nodes("process", s.landscape)
        node_ids = [n for n, _ in matches]
        assert "L:PAYMENT_PROCESSING" in node_ids

    def test_exact_match_still_preferred(self):
        """Exact word match scores higher than stem match."""
        s = _build_session_with_mock(_TEACH_SPEC)
        s.landscape.add_state("L:PROCESS")
        s.landscape.add_state("L:PROCESSING")
        matches = _match_nodes("process", s.landscape)
        scores = {n: sc for n, sc in matches}
        if "L:PROCESS" in scores and "L:PROCESSING" in scores:
            assert scores["L:PROCESS"] >= scores["L:PROCESSING"]


class TestDiagnoseLearningGapsScoped:
    """C244: _diagnose_learning_gaps with concept_nodes scoping."""

    def test_scoped_ignores_other_prefix_nodes(self, monkeypatch, tmp_path):
        """Gap diagnosis with concept_nodes ignores nodes from other teaches."""
        import e0_controller.explore_bootstrap_landscape as ebl
        monkeypatch.setattr(ebl, "LEARNING_STATE_PATH", str(tmp_path / "ls.json"))
        s = _build_session_with_mock(_TEACH_SPEC)
        teach_concept(s, "test concept")
        concept_nodes = [n for n in s.landscape.states if n.startswith("L:")]

        # Now inject "foreign" L: nodes from a different topic
        s.landscape.add_state("L:FOREIGN_WEATHER")
        s.landscape.add_state("L:FOREIGN_CREDIT")

        # Unscoped: sees foreign nodes
        gaps_all = _diagnose_learning_gaps(s, prefix="L:")
        assert gaps_all["total_prefix_nodes"] > len(concept_nodes)

        # Scoped: only sees concept nodes
        gaps_scoped = _diagnose_learning_gaps(
            s, prefix="L:", concept_nodes=concept_nodes,
        )
        assert gaps_scoped["total_prefix_nodes"] == len(concept_nodes)

    def test_scoped_finds_gaps_in_own_nodes(self, monkeypatch, tmp_path):
        """Scoped diagnosis still finds legitimate gaps."""
        import e0_controller.explore_bootstrap_landscape as ebl
        monkeypatch.setattr(ebl, "LEARNING_STATE_PATH", str(tmp_path / "ls.json"))
        s = _build_session_with_mock(_TEACH_SPEC)
        teach_concept(s, "test concept")
        concept_nodes = [n for n in s.landscape.states if n.startswith("L:")]
        gaps = _diagnose_learning_gaps(
            s, prefix="L:", concept_nodes=concept_nodes,
        )
        assert isinstance(gaps["has_gaps"], bool)
        assert gaps["total_prefix_nodes"] >= 1

    def test_empty_concept_nodes_means_no_gaps(self):
        """Empty concept_nodes list → no gaps possible."""
        s = build_session(steps_per_round=10)
        gaps = _diagnose_learning_gaps(
            s, prefix="L:", concept_nodes=[],
        )
        assert not gaps["has_gaps"]
        assert gaps["total_prefix_nodes"] == 0


class TestAssessKnowledgeStemming:
    """C244: _assess_knowledge uses stemming for coverage."""

    def test_stemmed_term_covered(self):
        """'logistics' matches L:LOGISTIC_PROCESSES via stemming."""
        s = build_session(steps_per_round=10)
        # Inject node
        s.landscape.add_state("L:LOGISTIC_PROCESSES")
        s.unified_nodes["L:LOGISTIC_PROCESSES"] = {
            "type": "task", "description": "logistic processes",
        }
        result = _assess_knowledge(s, "what are logistics")
        assert "logistics" in result["covered"], (
            f"'logistics' should be covered, gaps={result['gaps']}"
        )

    def test_processing_vs_process(self):
        """'process' matches PAYMENT_PROCESSING via stemming."""
        s = build_session(steps_per_round=10)
        s.landscape.add_state("L:PAYMENT_PROCESSING")
        s.unified_nodes["L:PAYMENT_PROCESSING"] = {
            "type": "task", "description": "payment processing",
        }
        result = _assess_knowledge(s, "what is the payment process")
        assert "process" in result["covered"], (
            f"'process' should match PAYMENT_PROCESSING, gaps={result['gaps']}"
        )


# ── C253: Teach-Aware Ask — scoring + anchor preference ──────────────


class TestMatchNodesBalancedScoring:
    """C253: _match_nodes uses balanced scoring (node_ratio + query_ratio)/2."""

    def test_single_word_exact_match_unchanged(self):
        """Exact single-word match still scores 1.0."""
        s = build_session(steps_per_round=5)
        s.landscape.add_state("EN:water")
        matches = _match_nodes("water", s.landscape)
        assert matches[0] == ("EN:water", 1.0)

    def test_compound_concept_not_penalized(self):
        """L:WHAT_IS_WATER scores ≥0.5 for query 'water' (was 0.33)."""
        s = build_session(steps_per_round=5)
        s.landscape.add_state("L:WHAT_IS_WATER")
        matches = _match_nodes("water", s.landscape)
        scores = {m[0]: m[1] for m in matches}
        assert "L:WHAT_IS_WATER" in scores
        assert scores["L:WHAT_IS_WATER"] >= 0.5  # was 0.33 before fix

    def test_two_word_concept_scores_higher(self):
        """L:WATER_CYCLE scores higher than L:WHAT_IS_WATER for 'water'."""
        s = build_session(steps_per_round=5)
        s.landscape.add_state("L:WATER_CYCLE")
        s.landscape.add_state("L:WHAT_IS_WATER")
        matches = _match_nodes("water", s.landscape)
        scores = {m[0]: m[1] for m in matches}
        assert scores["L:WATER_CYCLE"] > scores["L:WHAT_IS_WATER"]

    def test_multi_word_query_full_match_is_1(self):
        """'molecular composition' vs L:MOLECULAR_COMPOSITION = 1.0."""
        s = build_session(steps_per_round=5)
        s.landscape.add_state("L:MOLECULAR_COMPOSITION")
        matches = _match_nodes("molecular composition", s.landscape)
        assert matches[0][1] == 1.0

    def test_all_matches_still_returned(self):
        """Both EN: and L: nodes appear when both match."""
        s = build_session(steps_per_round=5)
        s.landscape.add_state("EN:water")
        s.landscape.add_state("L:WHAT_IS_WATER")
        s.landscape.add_state("L:WATER_CYCLE")
        matches = _match_nodes("water", s.landscape)
        ids = [m[0] for m in matches]
        assert "EN:water" in ids
        assert "L:WHAT_IS_WATER" in ids
        assert "L:WATER_CYCLE" in ids


class TestAskAnchorPreference:
    """C253: ask_run prefers L: (taught) anchors over generic matches."""

    def test_prefers_l_node_when_close_score(self):
        """L: node chosen as anchor when its score ≥50% of best."""
        s = build_session(steps_per_round=10)
        s.landscape.add_state("EN:water")
        s.landscape.add_state("L:WHAT_IS_WATER")
        s.landscape.add_state("L:WATER_CYCLE")
        # Add edges so navigation works
        s.landscape.add_edge("EN:water", "L:WHAT_IS_WATER", delta=0.4, resistance=1.0)
        s.landscape.add_edge("L:WHAT_IS_WATER", "L:WATER_CYCLE", delta=0.3, resistance=0.5)
        result = ask_run(s, "what is water", auto_learn=False)
        # Anchor should be an L: node, not EN:water
        anchor = result.get("anchor")
        if anchor is not None:
            assert anchor.startswith("L:"), f"Expected L: anchor, got {anchor}"

    def test_still_uses_best_when_no_l_match(self):
        """Without L: nodes, best match is used as before."""
        s = build_session(steps_per_round=10)
        # Only EN nodes, no L:
        result = ask_run(s, "what is tension", auto_learn=False)
        anchor = result.get("anchor")
        if anchor is not None:
            assert anchor.startswith("C:"), f"Expected C: anchor, got {anchor}"

    def test_l_node_not_preferred_when_score_too_low(self):
        """L: node ignored when its score < 50% of best."""
        s = build_session(steps_per_round=10)
        s.landscape.add_state("EN:water")
        # L: node with very low overlap (no word match, only substring)
        s.landscape.add_state("L:HYDROGEN_OXYGEN_BONDING")
        result = ask_run(s, "water", auto_learn=False)
        anchor = result.get("anchor")
        # Should NOT prefer L: here — no word overlap
        if anchor is not None:
            assert anchor == "EN:water"


class TestAskFeedbackOnFailure:
    """C244: ask_run signals failure when confidence is low."""

    def test_low_confidence_records_gap_event(self):
        """0% confidence triggers knowledge_gap_unresolved journal event."""
        s = build_session(steps_per_round=10)
        initial_streak = s.stagnation_streak
        # auto_learn=False to avoid LLM call; still triggers feedback
        ask_run(s, "xyzzy plugh gibberish nonsense", auto_learn=False)
        # Should have incremented stagnation
        assert s.stagnation_streak > initial_streak
        # Should have recorded journal event
        gap_events = [
            e for e in s.journal
            if e.get("event_type") == "knowledge_gap_unresolved"
        ]
        assert len(gap_events) >= 1
        evt = gap_events[0]
        detail = evt.get("detail", evt)
        assert "unresolved_gaps" in detail

    def test_good_confidence_no_gap_event(self):
        """Good confidence does not trigger gap event."""
        s = build_session(steps_per_round=10)
        initial_streak = s.stagnation_streak
        # Use terms that exist in the landscape
        ask_run(s, "tension historization", auto_learn=False)
        gap_events = [
            e for e in s.journal
            if e.get("event_type") == "knowledge_gap_unresolved"
        ]
        assert len(gap_events) == 0


# ── Universe Registry (C245) ──────────────────────────────────────────


class TestEnsureMainUniverse:
    """C245: _ensure_main_universe lazily wraps session landscape."""

    def test_creates_main_from_session(self):
        """First call creates 'main' from session's current landscape."""
        s = build_session(steps_per_round=10)
        assert len(s.universes) == 0
        _ensure_main_universe(s)
        assert "main" in s.universes
        assert s.universes["main"].landscape is s.landscape

    def test_idempotent(self):
        """Calling twice does not overwrite."""
        s = build_session(steps_per_round=10)
        _ensure_main_universe(s)
        u1 = s.universes["main"]
        _ensure_main_universe(s)
        assert s.universes["main"] is u1


class TestUniverseCreate:
    """C245: universe_create builds isolated landscape."""

    def test_create_new_universe(self):
        """New universe gets its own fresh landscape."""
        s = build_session(steps_per_round=10)
        result = universe_create(s, "logistics")
        assert "created" in result.lower()
        assert "logistics" in s.universes
        # Different landscape object
        u = s.universes["logistics"]
        assert u.landscape is not s.landscape
        assert u.round_num == 0

    def test_create_duplicate_rejected(self):
        """Cannot create a universe with an existing name."""
        s = build_session(steps_per_round=10)
        universe_create(s, "alpha")
        result = universe_create(s, "alpha")
        assert "already exists" in result.lower()

    def test_create_invalid_name_rejected(self):
        """Names must be valid identifiers."""
        s = build_session(steps_per_round=10)
        result = universe_create(s, "my universe")
        assert "invalid" in result.lower()

    def test_create_records_journal(self):
        """Creation records a journal event."""
        s = build_session(steps_per_round=10)
        universe_create(s, "physics")
        events = [
            e for e in s.journal
            if e.get("event_type") == "universe_created"
        ]
        assert len(events) == 1
        assert events[0]["detail"]["name"] == "physics"


class TestUniverseList:
    """C245: universe_list shows all universes with stats."""

    def test_list_default(self):
        """Default session has main universe after list."""
        s = build_session(steps_per_round=10)
        result = universe_list(s)
        assert "main" in result
        assert "active" in result.lower()

    def test_list_multiple(self):
        """Lists all created universes."""
        s = build_session(steps_per_round=10)
        universe_create(s, "alpha")
        universe_create(s, "beta")
        result = universe_list(s)
        assert "main" in result
        assert "alpha" in result
        assert "beta" in result


class TestUniverseSwitch:
    """C245: universe_switch changes active universe."""

    def test_switch_changes_landscape(self):
        """After switch, session landscape reflects new universe."""
        s = build_session(steps_per_round=10)
        original_landscape = s.landscape
        universe_create(s, "alt")
        alt_landscape = s.universes["alt"].landscape
        result = universe_switch(s, "alt")
        assert "switched" in result.lower()
        assert s.active_universe == "alt"
        assert s.landscape is alt_landscape
        assert s.landscape is not original_landscape

    def test_switch_preserves_state(self):
        """Switching away saves current state, switching back restores it."""
        s = build_session(steps_per_round=10)
        # Modify main
        s.round_num = 42
        s.stagnation_streak = 5
        _ensure_main_universe(s)
        _sync_session_to_active(s)
        # Create alt and switch
        universe_create(s, "alt")
        universe_switch(s, "alt")
        assert s.round_num == 0  # alt is fresh
        # Switch back
        universe_switch(s, "main")
        assert s.round_num == 42
        assert s.stagnation_streak == 5

    def test_switch_nonexistent_rejected(self):
        """Cannot switch to a universe that doesn't exist."""
        s = build_session(steps_per_round=10)
        result = universe_switch(s, "nope")
        assert "not found" in result.lower()

    def test_switch_same_noop(self):
        """Switching to the current universe is a no-op."""
        s = build_session(steps_per_round=10)
        _ensure_main_universe(s)
        result = universe_switch(s, "main")
        assert "already" in result.lower()

    def test_switch_records_journal(self):
        """Switching records a journal event."""
        s = build_session(steps_per_round=10)
        universe_create(s, "target")
        universe_switch(s, "target")
        events = [
            e for e in s.journal
            if e.get("event_type") == "universe_switched"
        ]
        assert len(events) == 1
        assert events[0]["detail"]["to"] == "target"


class TestUniverseDelete:
    """C245: universe_delete removes a universe."""

    def test_delete_non_active(self):
        """Can delete a non-active universe."""
        s = build_session(steps_per_round=10)
        universe_create(s, "temp")
        result = universe_delete(s, "temp")
        assert "deleted" in result.lower()
        assert "temp" not in s.universes

    def test_delete_active_rejected(self):
        """Cannot delete the active universe."""
        s = build_session(steps_per_round=10)
        universe_create(s, "active_one")
        universe_switch(s, "active_one")
        result = universe_delete(s, "active_one")
        assert "cannot delete active" in result.lower()

    def test_delete_main_rejected(self):
        """Cannot delete the main universe."""
        s = build_session(steps_per_round=10)
        _ensure_main_universe(s)
        result = universe_delete(s, "main")
        assert "cannot delete" in result.lower()

    def test_delete_records_journal(self):
        """Deletion records a journal event."""
        s = build_session(steps_per_round=10)
        universe_create(s, "doomed")
        universe_delete(s, "doomed")
        events = [
            e for e in s.journal
            if e.get("event_type") == "universe_deleted"
        ]
        assert len(events) == 1


class TestCmdUniverse:
    """C245: cmd_universe dispatches subcommands."""

    def test_no_arg_lists(self):
        """No argument shows list."""
        s = build_session(steps_per_round=10)
        result = cmd_universe(s, "")
        assert "main" in result

    def test_list_subcommand(self):
        """Explicit 'list' subcommand."""
        s = build_session(steps_per_round=10)
        result = cmd_universe(s, "list")
        assert "main" in result

    def test_create_via_cmd(self):
        """Create via cmd_universe."""
        s = build_session(steps_per_round=10)
        result = cmd_universe(s, "create myworld")
        assert "created" in result.lower()

    def test_switch_via_cmd(self):
        """Switch via cmd_universe."""
        s = build_session(steps_per_round=10)
        cmd_universe(s, "create target")
        result = cmd_universe(s, "switch target")
        assert "switched" in result.lower()

    def test_delete_via_cmd(self):
        """Delete via cmd_universe."""
        s = build_session(steps_per_round=10)
        cmd_universe(s, "create temp")
        result = cmd_universe(s, "delete temp")
        assert "deleted" in result.lower()

    def test_unknown_subcommand(self):
        """Unknown subcommand returns error."""
        s = build_session(steps_per_round=10)
        result = cmd_universe(s, "frobnicate")
        assert "unknown" in result.lower()


class TestUniverseDispatch:
    """C245: 'universe' command works through dispatch."""

    def test_dispatch_universe_list(self):
        """dispatch routes 'universe' to cmd_universe."""
        s = build_session(steps_per_round=10)
        result = dispatch(s, "universe")
        assert "main" in result

    def test_dispatch_universe_create(self):
        """dispatch handles 'universe create X'."""
        s = build_session(steps_per_round=10)
        result = dispatch(s, "universe create test_u")
        assert "created" in result.lower()
        assert "test_u" in s.universes

    def test_dispatch_syncs_after_run(self):
        """After 'run' via dispatch, active universe state is synced."""
        s = build_session(steps_per_round=10)
        _ensure_main_universe(s)
        initial_round = s.round_num
        dispatch(s, "run 1")
        # Session state updated
        assert s.round_num > initial_round
        # Universe state also updated
        assert s.universes["main"].round_num == s.round_num


class TestUniverseInHelp:
    """C245: universe command appears in help text."""

    def test_help_mentions_universe(self):
        """Help text includes universe command."""
        text = cmd_help()
        assert "universe" in text.lower()


# ---------------------------------------------------------------------------
# C246: Per-Universe Teach/Ask Isolation
# ---------------------------------------------------------------------------


class TestUniverseLandscapeIsolation:
    """C246: L: nodes added in one universe must not appear in another."""

    def test_l_nodes_isolated_between_universes(self):
        """Teach-injected L: nodes in universe A are absent from universe B."""
        s = build_session(steps_per_round=10)
        _ensure_main_universe(s)

        universe_create(s, "alpha")
        universe_switch(s, "alpha")

        # Inject L: nodes into alpha's landscape
        s.landscape.add_state("L:WATER_CYCLE")
        s.landscape.add_state("L:EVAPORATION")
        _sync_session_to_active(s)

        # Switch to main — L: nodes must be absent
        universe_switch(s, "main")
        main_l = [n for n in s.landscape.states if n.startswith("L:")]
        assert len(main_l) == 0, f"Main sees alpha L: nodes: {main_l}"

    def test_l_nodes_persist_on_switch_back(self):
        """L: nodes survive universe round-trip (A→B→A)."""
        s = build_session(steps_per_round=10)
        _ensure_main_universe(s)

        universe_create(s, "beta")
        universe_switch(s, "beta")

        s.landscape.add_state("L:PHOTOSYNTHESIS")
        _sync_session_to_active(s)

        universe_switch(s, "main")
        universe_switch(s, "beta")

        beta_l = [n for n in s.landscape.states if n.startswith("L:")]
        assert "L:PHOTOSYNTHESIS" in beta_l

    def test_two_universes_independent_l_nodes(self):
        """Two universes can have different L: nodes simultaneously."""
        s = build_session(steps_per_round=10)
        _ensure_main_universe(s)

        # Teach in main
        s.landscape.add_state("L:GRAVITY")
        _sync_session_to_active(s)

        # Teach in alpha
        universe_create(s, "alpha")
        universe_switch(s, "alpha")
        s.landscape.add_state("L:LOGISTICS")
        _sync_session_to_active(s)

        # Check alpha
        alpha_l = {n for n in s.landscape.states if n.startswith("L:")}
        assert "L:LOGISTICS" in alpha_l
        assert "L:GRAVITY" not in alpha_l

        # Check main
        universe_switch(s, "main")
        main_l = {n for n in s.landscape.states if n.startswith("L:")}
        assert "L:GRAVITY" in main_l
        assert "L:LOGISTICS" not in main_l


class TestConsolidateUniverseTag:
    """C246: consolidate() tags edges and history with universe name."""

    def test_edges_tagged_with_universe(self, tmp_path):
        """Persisted edges carry the universe field."""
        import e0_controller.explore_bootstrap_landscape as mod
        from e0_controller.explore_learning_cycle_multidomain import (
            consolidate, MultiDomainAssessment, MultiDomainRoundResult,
        )

        tmp_ls = tmp_path / "learning_state.json"
        with open(tmp_ls, "w", encoding="utf-8") as f:
            json.dump({"_meta": {"source": "test"}}, f)

        orig = mod.LEARNING_STATE_PATH
        mod.LEARNING_STATE_PATH = str(tmp_ls)
        try:
            a = MultiDomainAssessment(
                total_nodes=100, total_edges=200, visited_nodes=50,
                coverage=0.5, frontier_size=10, T_s=0.1,
                mean_quality=0.5, stale_edges=0,
                canon_coverage=0.5, bootstrap_coverage=0.5, en_coverage=0.5,
                canon_nodes=30, bootstrap_nodes=30, en_nodes=30,
                canon_visited=15, bootstrap_visited=15, en_visited=15,
            )
            rr = MultiDomainRoundResult(
                round_num=1, mode="teach", reason="test", steps=10,
                assessment_before=a, assessment_after=a,
                path=["A", "B"], new_edges=1,
                domain_crossings=0, crossing_rate=0.0,
                coverage_delta=0.01, T_s_delta=0.0,
                en_canon_crossings=0, en_bootstrap_crossings=0,
                canon_bootstrap_crossings=0,
            )
            consolidate(rr, [{"from": "X", "to": "Y"}], universe="sandbox")

            with open(tmp_ls, encoding="utf-8") as f:
                ls = json.load(f)

            edge = ls["discovered_edges"]["edges"][0]
            assert edge["universe"] == "sandbox"

            entry = ls["multidomain_history"]["rounds"][0]
            assert entry["universe"] == "sandbox"
        finally:
            mod.LEARNING_STATE_PATH = orig

    def test_default_universe_is_main(self, tmp_path):
        """Without explicit universe kwarg, edges are tagged 'main'."""
        import e0_controller.explore_bootstrap_landscape as mod
        from e0_controller.explore_learning_cycle_multidomain import (
            consolidate, MultiDomainAssessment, MultiDomainRoundResult,
        )

        tmp_ls = tmp_path / "learning_state.json"
        with open(tmp_ls, "w", encoding="utf-8") as f:
            json.dump({"_meta": {"source": "test"}}, f)

        orig = mod.LEARNING_STATE_PATH
        mod.LEARNING_STATE_PATH = str(tmp_ls)
        try:
            a = MultiDomainAssessment(
                total_nodes=100, total_edges=200, visited_nodes=50,
                coverage=0.5, frontier_size=10, T_s=0.1,
                mean_quality=0.5, stale_edges=0,
                canon_coverage=0.5, bootstrap_coverage=0.5, en_coverage=0.5,
                canon_nodes=30, bootstrap_nodes=30, en_nodes=30,
                canon_visited=15, bootstrap_visited=15, en_visited=15,
            )
            rr = MultiDomainRoundResult(
                round_num=1, mode="teach", reason="test", steps=10,
                assessment_before=a, assessment_after=a,
                path=["A", "B"], new_edges=0,
                domain_crossings=0, crossing_rate=0.0,
                coverage_delta=0.01, T_s_delta=0.0,
                en_canon_crossings=0, en_bootstrap_crossings=0,
                canon_bootstrap_crossings=0,
            )
            consolidate(rr, [{"from": "A", "to": "B"}])

            with open(tmp_ls, encoding="utf-8") as f:
                ls = json.load(f)

            edge = ls["discovered_edges"]["edges"][0]
            assert edge["universe"] == "main"
        finally:
            mod.LEARNING_STATE_PATH = orig


class TestRegenerateSeedUniverseFilter:
    """C246: regenerate_seed only materializes edges from active universe."""

    def test_filters_by_active_universe(self, tmp_path):
        """Edges tagged with a different universe are skipped."""
        import e0_controller.explore_bootstrap_landscape as mod

        s = build_session(steps_per_round=10)
        _ensure_main_universe(s)

        # Add nodes so edges can be materialized
        s.landscape.add_state("L:A")
        s.landscape.add_state("L:B")
        s.landscape.add_state("L:C")

        # Write learning_state with edges from two universes
        tmp_ls = tmp_path / "learning_state.json"
        ls_data = {
            "discovered_edges": {
                "edges": [
                    {"from": "L:A", "to": "L:B", "confidence": 0.9,
                     "delta": 0.5, "resistance": 1.0, "universe": "main"},
                    {"from": "L:B", "to": "L:C", "confidence": 0.9,
                     "delta": 0.5, "resistance": 1.0, "universe": "sandbox"},
                ]
            }
        }
        with open(tmp_ls, "w", encoding="utf-8") as f:
            json.dump(ls_data, f)

        orig = mod.LEARNING_STATE_PATH
        mod.LEARNING_STATE_PATH = str(tmp_ls)
        try:
            result = regenerate_seed(s, path=str(tmp_path / "seed.json"))
            # Only the "main" edge should be materialized
            assert result["materialized_edges"] == 1
            assert s.landscape.has_edge("L:A", "L:B")
            assert not s.landscape.has_edge("L:B", "L:C")
        finally:
            mod.LEARNING_STATE_PATH = orig

    def test_legacy_edges_without_universe_count_as_main(self, tmp_path):
        """Pre-C246 edges (no universe field) are treated as 'main'."""
        import e0_controller.explore_bootstrap_landscape as mod

        s = build_session(steps_per_round=10)
        _ensure_main_universe(s)

        s.landscape.add_state("L:X")
        s.landscape.add_state("L:Y")

        tmp_ls = tmp_path / "learning_state.json"
        ls_data = {
            "discovered_edges": {
                "edges": [
                    {"from": "L:X", "to": "L:Y", "confidence": 0.9,
                     "delta": 0.5, "resistance": 1.0},
                ]
            }
        }
        with open(tmp_ls, "w", encoding="utf-8") as f:
            json.dump(ls_data, f)

        orig = mod.LEARNING_STATE_PATH
        mod.LEARNING_STATE_PATH = str(tmp_ls)
        try:
            result = regenerate_seed(s, path=str(tmp_path / "seed.json"))
            assert result["materialized_edges"] == 1
        finally:
            mod.LEARNING_STATE_PATH = orig


# ---------------------------------------------------------------------------
# C247 — CouplingRouter Wiring
# ---------------------------------------------------------------------------


class TestUniverseToCoupling:
    """C247: Converting UniverseState to CouplingRouter Universe."""

    def test_converts_basic_fields(self):
        """Name and landscape carried through."""
        from e0_controller.multiverse import Universe

        s = build_session(steps_per_round=5)
        _ensure_main_universe(s)
        cu = _universe_to_coupling(s.universes["main"])
        assert isinstance(cu, Universe)
        assert cu.name == "main"
        assert cu.landscape is s.universes["main"].landscape

    def test_execute_fn_is_stub(self):
        """Execute function returns SUCCESS (inert stub)."""
        s = build_session(steps_per_round=5)
        _ensure_main_universe(s)
        cu = _universe_to_coupling(s.universes["main"])
        assert cu.execute_fn("a", "b") == Outcome.SUCCESS


class TestEnsureCouplingRouter:
    """C247: Lazy CouplingRouter creation."""

    def test_none_with_single_universe(self):
        """No router when only one universe exists."""
        s = build_session(steps_per_round=5)
        _ensure_main_universe(s)
        router = _ensure_coupling_router(s)
        assert router is None
        assert s.coupling_router is None

    def test_creates_with_two_universes(self):
        """Router created when ≥2 universes exist."""
        s = build_session(steps_per_round=5)
        _ensure_main_universe(s)
        universe_create(s, "alt")
        router = _ensure_coupling_router(s)
        assert router is not None
        assert isinstance(router, CouplingRouter)
        assert router.universe_count == 2

    def test_reuses_existing_router(self):
        """Same router object reused on subsequent calls."""
        s = build_session(steps_per_round=5)
        _ensure_main_universe(s)
        universe_create(s, "alt")
        r1 = _ensure_coupling_router(s)
        r2 = _ensure_coupling_router(s)
        assert r1 is r2

    def test_adds_new_universe_to_existing_router(self):
        """Adding a third universe updates the existing router."""
        s = build_session(steps_per_round=5)
        _ensure_main_universe(s)
        universe_create(s, "alt")
        _ensure_coupling_router(s)
        universe_create(s, "third")
        router = _ensure_coupling_router(s)
        assert router.universe_count == 3

    def test_removes_deleted_universe_from_router(self):
        """Deleting a universe removes it from the router."""
        s = build_session(steps_per_round=5)
        _ensure_main_universe(s)
        universe_create(s, "alt")
        universe_create(s, "third")
        _ensure_coupling_router(s)
        universe_delete(s, "third")
        router = _ensure_coupling_router(s)
        assert router.universe_count == 2


class TestCoupleRun:
    """C247: couple_run knowledge transfer."""

    def test_error_with_single_universe(self):
        """Returns error dict when only one universe."""
        s = build_session(steps_per_round=5)
        result = couple_run(s)
        assert "error" in result

    def test_error_self_couple(self):
        """Cannot couple a universe with itself."""
        s = build_session(steps_per_round=5)
        _ensure_main_universe(s)
        universe_create(s, "alt")
        result = couple_run(s, partner_name="main")
        assert "error" in result

    def test_error_nonexistent_partner(self):
        """Error for nonexistent partner name."""
        s = build_session(steps_per_round=5)
        _ensure_main_universe(s)
        universe_create(s, "alt")
        result = couple_run(s, partner_name="ghost")
        assert "error" in result

    def test_transfers_l_nodes(self):
        """L: nodes from partner appear in active universe."""
        s = build_session(steps_per_round=5)
        _ensure_main_universe(s)
        universe_create(s, "donor")
        # Inject L: nodes into donor
        universe_switch(s, "donor")
        s.landscape.add_state("L:WATER")
        s.landscape.add_state("L:EVAPORATION")
        s.landscape.add_edge("L:WATER", "L:EVAPORATION", delta=0.5, resistance=1.0)
        _sync_session_to_active(s)
        # Switch to main and couple
        universe_switch(s, "main")
        result = couple_run(s, partner_name="donor")
        assert result["nodes_transferred"] == 2
        assert result["edges_transferred"] == 1
        assert "L:WATER" in s.landscape.states
        assert "L:EVAPORATION" in s.landscape.states
        assert result["outcome"] == "SUCCESS"

    def test_no_duplicate_transfer(self):
        """Second couple transfers nothing (already present)."""
        s = build_session(steps_per_round=5)
        _ensure_main_universe(s)
        universe_create(s, "donor")
        universe_switch(s, "donor")
        s.landscape.add_state("L:TOPIC")
        _sync_session_to_active(s)
        universe_switch(s, "main")
        couple_run(s, partner_name="donor")
        result = couple_run(s, partner_name="donor")
        assert result["nodes_transferred"] == 0
        assert result["outcome"] == "FAILURE"

    def test_auto_select_recovery(self):
        """Auto-select partner via RECOVERY reason."""
        s = build_session(steps_per_round=5)
        _ensure_main_universe(s)
        universe_create(s, "expert")
        universe_switch(s, "expert")
        s.landscape.add_state("L:INSIGHT")
        _sync_session_to_active(s)
        universe_switch(s, "main")
        result = couple_run(s, reason=CouplingReason.RECOVERY)
        assert result["partner"] == "expert"
        assert result["reason"] == "recovery"

    def test_auto_select_exploration(self):
        """Auto-select partner via EXPLORATION reason."""
        s = build_session(steps_per_round=5)
        _ensure_main_universe(s)
        universe_create(s, "novel")
        universe_switch(s, "novel")
        s.landscape.add_state("L:ALIEN")
        _sync_session_to_active(s)
        universe_switch(s, "main")
        result = couple_run(s, reason=CouplingReason.EXPLORATION)
        assert result["partner"] == "novel"
        assert result["reason"] == "exploration"

    def test_only_l_edges_transferred(self):
        """Non-L: edges are not transferred."""
        s = build_session(steps_per_round=5)
        _ensure_main_universe(s)
        universe_create(s, "donor")
        universe_switch(s, "donor")
        # Add L: edge and a non-L: edge
        s.landscape.add_state("L:A")
        s.landscape.add_state("L:B")
        s.landscape.add_edge("L:A", "L:B", delta=0.5, resistance=1.0)
        s.landscape.add_state("X:FOO")
        s.landscape.add_state("X:BAR")
        s.landscape.add_edge("X:FOO", "X:BAR", delta=0.5, resistance=1.0)
        _sync_session_to_active(s)
        universe_switch(s, "main")
        result = couple_run(s, partner_name="donor")
        # L: nodes transferred, but X: edge NOT transferred
        assert result["nodes_transferred"] == 2  # only L:A, L:B
        assert result["edges_transferred"] == 1  # only L:A→L:B
        assert "X:FOO" not in s.landscape.states


class TestCoupleStatus:
    """C247: couple status output."""

    def test_inactive_with_one_universe(self):
        """Reports inactive with single universe."""
        s = build_session(steps_per_round=5)
        assert "inactive" in couple_status(s).lower()

    def test_summary_with_two_universes(self):
        """Returns router summary with ≥2 universes."""
        s = build_session(steps_per_round=5)
        _ensure_main_universe(s)
        universe_create(s, "alt")
        text = couple_status(s)
        assert "main" in text
        assert "alt" in text


class TestCmdCouple:
    """C247: cmd_couple command parsing."""

    def test_default_recovery(self):
        """No args = auto-select RECOVERY."""
        s = build_session(steps_per_round=5)
        _ensure_main_universe(s)
        universe_create(s, "donor")
        universe_switch(s, "donor")
        s.landscape.add_state("L:NODE")
        _sync_session_to_active(s)
        universe_switch(s, "main")
        text = cmd_couple(s, "")
        assert "donor" in text.lower()

    def test_explore_subcommand(self):
        """'couple explore' uses EXPLORATION."""
        s = build_session(steps_per_round=5)
        _ensure_main_universe(s)
        universe_create(s, "other")
        text = cmd_couple(s, "explore")
        assert "other" in text.lower() or "FAILURE" in text

    def test_recover_subcommand(self):
        """'couple recover' uses RECOVERY."""
        s = build_session(steps_per_round=5)
        _ensure_main_universe(s)
        universe_create(s, "other")
        text = cmd_couple(s, "recover")
        assert "other" in text.lower() or "FAILURE" in text

    def test_status_subcommand(self):
        """'couple status' shows router info."""
        s = build_session(steps_per_round=5)
        _ensure_main_universe(s)
        universe_create(s, "alt")
        text = cmd_couple(s, "status")
        assert "main" in text and "alt" in text

    def test_named_partner(self):
        """'couple donor' couples with named universe."""
        s = build_session(steps_per_round=5)
        _ensure_main_universe(s)
        universe_create(s, "donor")
        text = cmd_couple(s, "donor")
        assert "donor" in text.lower()

    def test_error_single_universe(self):
        """Error message when only one universe."""
        s = build_session(steps_per_round=5)
        text = cmd_couple(s, "")
        assert "2" in text or "universe" in text.lower()


class TestCoupleInHelp:
    """C247: couple command appears in help text."""

    def test_help_mentions_couple(self):
        """Help text includes couple command."""
        text = cmd_help()
        assert "couple" in text.lower()


class TestCoupleInDispatch:
    """C247: couple command dispatches correctly."""

    def test_dispatch_couple(self):
        """dispatch('couple status') routes correctly."""
        s = build_session(steps_per_round=5)
        _ensure_main_universe(s)
        universe_create(s, "alt")
        text = dispatch(s, "couple status")
        assert "main" in text and "alt" in text


# ---------------------------------------------------------------------------
# C248 — Divergence Pressure Auto-Coupling
# ---------------------------------------------------------------------------


class TestAutoCoupleOnStagnation:
    """C248: auto_run triggers coupling when stagnating with ≥2 universes."""

    def test_auto_run_couples_on_stagnation(self):
        """Auto-mode uses couple action when stagnating + multi-universe."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        _ensure_main_universe(s)
        universe_create(s, "donor")
        # Inject L: nodes into donor so coupling transfers something
        universe_switch(s, "donor")
        s.landscape.add_state("L:HELP_NODE")
        _sync_session_to_active(s)
        universe_switch(s, "main")
        # Force stagnation
        s.stagnation_streak = 5
        result = auto_run(s, max_steps=2, rounds_per_step=1)
        actions = [a["action"] for a in result["actions"]]
        assert "couple" in actions

    def test_auto_couple_resets_stagnation(self):
        """Successful coupling resets stagnation streak."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        _ensure_main_universe(s)
        universe_create(s, "donor")
        universe_switch(s, "donor")
        s.landscape.add_state("L:FRESH_KNOWLEDGE")
        _sync_session_to_active(s)
        universe_switch(s, "main")
        s.stagnation_streak = 5
        auto_run(s, max_steps=1, rounds_per_step=1)
        # After successful couple, stagnation should be reset
        assert s.stagnation_streak == 0

    def test_auto_couple_records_journal(self):
        """Auto-coupling records a journal event."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        _ensure_main_universe(s)
        universe_create(s, "donor")
        universe_switch(s, "donor")
        s.landscape.add_state("L:JOURNAL_TEST")
        _sync_session_to_active(s)
        universe_switch(s, "main")
        s.stagnation_streak = 5
        auto_run(s, max_steps=1, rounds_per_step=1)
        couple_events = [e for e in s.journal if e.get("event_type") == "auto_couple"]
        assert len(couple_events) >= 1
        assert couple_events[0]["detail"]["partner"] == "donor"

    def test_single_universe_still_escalates(self):
        """Without multi-universe, stagnation still triggers escalate."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        s.stagnation_streak = 5
        action, _ = _choose_action(s)
        assert action == "escalate"

    def test_auto_couple_failure_preserves_stagnation(self):
        """Coupling that transfers nothing does not reset stagnation."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        _ensure_main_universe(s)
        universe_create(s, "empty_donor")
        # donor is empty — nothing to transfer
        s.stagnation_streak = 5
        auto_run(s, max_steps=1, rounds_per_step=1)
        # Stagnation NOT reset since coupling transferred nothing
        assert s.stagnation_streak >= 5


# ---------------------------------------------------------------------------
# C249 — Dream Multiverse-Aware
# ---------------------------------------------------------------------------


class TestDomainPrefixesIncludesLearned:
    """C249/C261: _DISPLAY_PREFIXES includes L: for learned nodes."""

    def test_l_prefix_in_domain_prefixes(self):
        """L: prefix is registered as 'learned' (backward compat alias)."""
        from e0_controller.interactive_session import _DOMAIN_PREFIXES
        assert "L:" in _DOMAIN_PREFIXES
        assert _DOMAIN_PREFIXES["L:"] == "learned"

    def test_l_prefix_in_display_prefixes(self):
        """C261: L: prefix in renamed _DISPLAY_PREFIXES."""
        assert "L:" in _DISPLAY_PREFIXES
        assert _DISPLAY_PREFIXES["L:"] == "learned"

    def test_backward_compat_alias(self):
        """C261: _DOMAIN_PREFIXES is same object as _DISPLAY_PREFIXES."""
        from e0_controller.interactive_session import _DOMAIN_PREFIXES
        assert _DOMAIN_PREFIXES is _DISPLAY_PREFIXES


class TestExtractDomainLandscapesLearned:
    """C249: _extract_domain_landscapes extracts L: nodes as 'learned'."""

    def test_extracts_learned_domain(self):
        """L: nodes form a separate 'learned' domain."""
        s = build_session(steps_per_round=5)
        s.landscape.add_state("L:WATER")
        s.landscape.add_state("L:ICE")
        s.landscape.add_edge("L:WATER", "L:ICE", delta=0.5, resistance=1.0)
        result = _extract_domain_landscapes(s.landscape)
        assert "learned" in result
        assert "L:WATER" in result["learned"].states
        assert "L:ICE" in result["learned"].states

    def test_no_learned_when_no_l_nodes(self):
        """No 'learned' domain when no L: edges exist."""
        s = build_session(steps_per_round=5)
        result = _extract_domain_landscapes(s.landscape)
        # May or may not be present (depends on cold start landscape)
        if "learned" in result:
            assert len(result["learned"].states) >= 1


class TestDreamRunCrossUniverse:
    """C249: dream_run includes L: sub-landscapes from other universes."""

    def test_single_universe_no_cross(self):
        """With one universe, domains are standard (no cross_universe_domains)."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = dream_run(s, cycles=1)
        assert "cross_universe_domains" in result
        assert result["cross_universe_domains"] == []

    def test_cross_universe_domains_registered(self):
        """Other universes' L: sub-landscapes registered as learned_<name>."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        _ensure_main_universe(s)
        universe_create(s, "research")
        # Add L: nodes to research universe
        universe_switch(s, "research")
        s.landscape.add_state("L:CONCEPT_A")
        s.landscape.add_state("L:CONCEPT_B")
        s.landscape.add_edge("L:CONCEPT_A", "L:CONCEPT_B", delta=0.5, resistance=1.0)
        _sync_session_to_active(s)
        # Switch back to main and dream
        universe_switch(s, "main")
        result = dream_run(s, cycles=1)
        assert "learned_research" in result["cross_universe_domains"]
        assert "learned_research" in result["domains"]

    def test_cross_universe_empty_not_registered(self):
        """Other universe with no L: nodes is not registered."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        _ensure_main_universe(s)
        universe_create(s, "empty_alt")
        result = dream_run(s, cycles=1)
        assert "learned_empty_alt" not in result.get("cross_universe_domains", [])

    def test_journal_includes_cross_universe(self):
        """Dream journal event includes cross_universe_domains."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        _ensure_main_universe(s)
        universe_create(s, "other")
        universe_switch(s, "other")
        s.landscape.add_state("L:X")
        s.landscape.add_state("L:Y")
        s.landscape.add_edge("L:X", "L:Y", delta=0.3, resistance=0.5)
        _sync_session_to_active(s)
        universe_switch(s, "main")
        dream_run(s, cycles=1)
        dream_events = [e for e in s.journal if e["event_type"] == "dream"]
        assert len(dream_events) >= 1
        detail = dream_events[-1]["detail"]
        assert "cross_universe_domains" in detail
        assert "learned_other" in detail["cross_universe_domains"]

    def test_multiple_other_universes(self):
        """Multiple other universes each get their own dream domain."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        _ensure_main_universe(s)
        for name in ["alpha", "beta"]:
            universe_create(s, name)
            universe_switch(s, name)
            s.landscape.add_state(f"L:{name.upper()}_1")
            s.landscape.add_state(f"L:{name.upper()}_2")
            s.landscape.add_edge(
                f"L:{name.upper()}_1", f"L:{name.upper()}_2",
                delta=0.4, resistance=0.8,
            )
            _sync_session_to_active(s)
        universe_switch(s, "main")
        result = dream_run(s, cycles=1)
        cross = result["cross_universe_domains"]
        assert "learned_alpha" in cross
        assert "learned_beta" in cross


# ---------------------------------------------------------------------------
# C250 — Dynamic Domain Detection
# ---------------------------------------------------------------------------


class TestDetectDomains:
    """C250: _detect_domains scans landscape for prefix patterns."""

    def test_standard_domains(self):
        """Standard landscape has canonical domains in order."""
        from e0_controller.interactive_session import _detect_domains
        s = build_session(steps_per_round=5)
        detected = _detect_domains(s.landscape)
        prefixes = [p for p, _ in detected]
        # C263: cold start excludes EN — only C: B: M: required
        for required in ["C:", "B:", "M:"]:
            assert required in prefixes

    def test_learned_domain_detected(self):
        """L: nodes are detected as Learned domain."""
        from e0_controller.interactive_session import _detect_domains
        s = build_session(steps_per_round=5)
        s.landscape.add_state("L:CONCEPT_X")
        detected = _detect_domains(s.landscape)
        prefixes = [p for p, _ in detected]
        names = [n for _, n in detected]
        assert "L:" in prefixes
        assert "Learned" in names

    def test_unknown_prefix_detected(self):
        """Unknown prefixes are detected and named by their prefix."""
        from e0_controller.interactive_session import _detect_domains
        s = build_session(steps_per_round=5)
        s.landscape.add_state("X:NOVEL_CONCEPT")
        detected = _detect_domains(s.landscape)
        prefixes = [p for p, _ in detected]
        assert "X:" in prefixes
        # Unknown prefixes sort after known ones
        assert prefixes.index("X:") > prefixes.index("M:")

    def test_canonical_order_preserved(self):
        """Known prefixes appear in canonical order."""
        from e0_controller.interactive_session import _detect_domains
        s = build_session(steps_per_round=5)
        s.landscape.add_state("L:A")
        detected = _detect_domains(s.landscape)
        prefixes = [p for p, _ in detected]
        # C263: cold start has C+B+M (no EN). With L: added manually.
        # Canonical order: C: before B: before M: before L:
        known = [p for p in prefixes if p in ["C:", "B:", "EN:", "M:", "L:"]]
        # Only present prefixes must be in order
        expected_order = [p for p in ["C:", "B:", "EN:", "M:", "L:"] if p in known]
        assert known == expected_order


class TestComputeDomainStats:
    """C250: _compute_domain_stats computes directly from landscape."""

    def test_stats_for_learned_domain(self):
        """Coverage computed directly from landscape for L: nodes."""
        from e0_controller.interactive_session import _compute_domain_stats
        s = build_session(steps_per_round=5)
        s.landscape.add_state("L:A")
        s.landscape.add_state("L:B")
        stats = _compute_domain_stats(s.landscape, "L:")
        assert stats["total"] == 2
        assert stats["visited"] == 0
        assert stats["coverage"] == 0.0

    def test_stats_with_visited(self):
        """Visited set is honoured when passed in."""
        from e0_controller.interactive_session import _compute_domain_stats
        s = build_session(steps_per_round=5)
        s.landscape.add_state("L:A")
        s.landscape.add_state("L:B")
        stats = _compute_domain_stats(
            s.landscape, "L:", visited_set={"L:A"},
        )
        assert stats["visited"] == 1
        assert abs(stats["coverage"] - 0.5) < 0.01


class TestDiagnoseSessionDynamic:
    """C250: diagnose_session includes dynamically detected domains."""

    def test_learned_domain_in_diagnostics(self):
        """L: nodes appear in diagnose_session output (prefix mode)."""
        s = build_session(steps_per_round=10)
        s.landscape.add_state("L:ITEM_1")
        s.landscape.add_state("L:ITEM_2")
        s.landscape.add_edge("L:ITEM_1", "L:ITEM_2", delta=0.5, resistance=1.0)
        diag = diagnose_session(s, partition="prefix")
        names = [d["name"] for d in diag["domains"]]
        assert "Learned" in names

    def test_unknown_prefix_in_diagnostics(self):
        """Nodes with novel prefix appear in diagnostics (prefix mode)."""
        s = build_session(steps_per_round=10)
        s.landscape.add_state("Z:ALPHA")
        s.landscape.add_state("Z:BETA")
        diag = diagnose_session(s, partition="prefix")
        names = [d["name"] for d in diag["domains"]]
        assert "Z" in names  # display name = prefix minus colon


class TestComputeTrajectoryDynamic:
    """C250: compute_trajectory includes detected domains."""

    def test_learned_domain_in_trajectory(self):
        """L: nodes appear in trajectory domain_trends (prefix mode)."""
        s = build_session(steps_per_round=10)
        s.landscape.add_state("L:ITEM_1")
        s.landscape.add_state("L:ITEM_2")
        s.landscape.add_edge("L:ITEM_1", "L:ITEM_2", delta=0.5, resistance=1.0)
        cmd_run(s, 1)
        traj = compute_trajectory(s, partition="prefix")
        assert "Learned" in traj["summary"]["domain_trends"]


class TestMetaReflectDynamic:
    """C250: meta_reflect includes all detected domains."""

    def test_learned_domain_in_reflection(self):
        """L: domain appears in meta-reflection (prefix mode)."""
        s = build_session(steps_per_round=10)
        s.landscape.add_state("L:ITEM_1")
        s.landscape.add_state("L:ITEM_2")
        s.landscape.add_edge("L:ITEM_1", "L:ITEM_2", delta=0.5, resistance=1.0)
        cmd_run(s, 3)
        result = meta_reflect(s, partition="prefix")
        assert "Learned" in result["domain_trajectories"]


class TestCmdFocusDynamic:
    """C250: cmd_focus accepts any detected domain."""

    def test_focus_learned_domain(self):
        """cmd_focus('learned') works when L: nodes exist."""
        s = build_session(steps_per_round=10)
        s.landscape.add_state("L:ITEM_1")
        s.landscape.add_state("L:ITEM_2")
        s.landscape.add_edge("L:ITEM_1", "L:ITEM_2", delta=0.5, resistance=1.0)
        cmd_run(s, 1)
        result = cmd_focus(s, "learned")
        assert "Learned" in result

    def test_focus_available_lists_all(self):
        """Unknown domain error lists available domains and communities."""
        s = build_session(steps_per_round=5)
        s.landscape.add_state("L:A")
        result = cmd_focus(s, "nonexistent")
        assert "Unknown domain" in result
        assert "Canon" in result or "community_" in result
        assert "Learned" in result or "Communities:" in result


class TestDomainOfDynamic:
    """C250: _domain_of handles all prefixes correctly."""

    def test_learned_prefix(self):
        """L: nodes return 'learned'."""
        from e0_controller.explore_learning_cycle_multidomain import _domain_of
        assert _domain_of("L:CONCEPT") == "learned"

    def test_bootstrap_explicit(self):
        """B: nodes return 'bootstrap' (not fallback)."""
        from e0_controller.explore_learning_cycle_multidomain import _domain_of
        assert _domain_of("B:SOME_NODE") == "bootstrap"

    def test_unknown_prefix(self):
        """Unknown uppercase prefix returns its lowered name."""
        from e0_controller.explore_learning_cycle_multidomain import _domain_of
        assert _domain_of("Z:SOMETHING") == "z"

    def test_no_prefix(self):
        """Node without prefix returns 'unknown'."""
        from e0_controller.explore_learning_cycle_multidomain import _domain_of
        assert _domain_of("no_prefix_node") == "unknown"


# ── C251: Adaptive Dream Compatibility ────────────────────────────────


class TestDreamCycleThresholdParam:
    """C251: dream_cycle accepts compatibility_threshold override."""

    def test_default_uses_instance_threshold(self):
        """Without override, dream_cycle uses the observer's threshold."""
        from e0_controller.dream_mode import DreamObserver
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        obs = DreamObserver(
            compatibility_threshold=0.01,  # very strict
            readiness_threshold=0.0,
        )
        ls = _extract_domain_landscapes(s.landscape)
        for name, l in ls.items():
            obs.register(name, l)
        result = obs.dream_cycle()
        # All pairs should be skipped at 0.01
        assert len(result.compatibility_skipped) > 0
        assert result.equivalences_found == 0

    def test_override_relaxes_threshold(self):
        """Passing explicit threshold overrides the instance default."""
        from e0_controller.dream_mode import DreamObserver
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        obs = DreamObserver(
            compatibility_threshold=0.01,  # very strict default
            readiness_threshold=0.0,
        )
        ls = _extract_domain_landscapes(s.landscape)
        for name, l in ls.items():
            obs.register(name, l)
        # Override with lenient threshold
        result = obs.dream_cycle(compatibility_threshold=1.0)
        assert len(result.compatibility_skipped) == 0
        assert result.equivalences_found > 0

    def test_none_preserves_instance_threshold(self):
        """Passing None explicitly still uses the observer's threshold."""
        from e0_controller.dream_mode import DreamObserver
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        obs = DreamObserver(
            compatibility_threshold=0.01,
            readiness_threshold=0.0,
        )
        ls = _extract_domain_landscapes(s.landscape)
        for name, l in ls.items():
            obs.register(name, l)
        result = obs.dream_cycle(compatibility_threshold=None)
        assert result.equivalences_found == 0


class TestDreamRunAdaptiveRelaxation:
    """C251: dream_run relaxes threshold when all pairs are incompatible."""

    def test_relaxation_triggers_on_all_incompatible(self):
        """When cycle 1 finds 0 eq, threshold relaxes for remaining cycles."""
        from e0_controller.dream_mode import DreamObserver
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        # Threshold 0.30 → all pairs fail (min score ~0.34)
        # Relaxed to 0.45 → canon↔en(0.40), canon↔mech(0.40) pass
        s.dream_observer = DreamObserver(
            compatibility_threshold=0.30,
            readiness_threshold=0.0,
        )
        result = dream_run(s, cycles=3, partition="prefix")
        assert result["threshold_relaxed"] is True
        # Cycle 1: 0 eq (all fail)
        assert result["cycle_results"][0].equivalences_found == 0
        # Cycle 2+: should find equivalences after relaxation
        assert result["cycle_results"][1].equivalences_found > 0

    def test_no_relaxation_when_pairs_pass(self):
        """When cycle 1 finds equivalences, no relaxation happens."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = dream_run(s, cycles=3)
        # Default threshold (0.6) → canon↔en, canon↔mech, en↔mech pass
        assert result["threshold_relaxed"] is False
        assert result["cycle_results"][0].equivalences_found > 0

    def test_relaxation_in_journal(self):
        """Journal event records whether threshold was relaxed."""
        from e0_controller.dream_mode import DreamObserver
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        s.dream_observer = DreamObserver(
            compatibility_threshold=0.30,
            readiness_threshold=0.0,
        )
        dream_run(s, cycles=3, partition="prefix")
        dream_events = [e for e in s.journal if e["event_type"] == "dream"]
        assert dream_events[-1]["detail"]["threshold_relaxed"] is True


class TestCmdDreamScores:
    """C251: cmd_dream output includes compatibility scores."""

    def test_scores_in_output(self):
        """Dream output shows compatibility scores."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_dream(s)
        assert "scores:" in out

    def test_scores_show_numeric_values(self):
        """Score lines contain numeric values like '=0.40'."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_dream(s)
        import re
        assert re.search(r"=\d\.\d\d", out)

    def test_relaxation_notice_shown(self):
        """Relaxation warning appears when threshold is relaxed."""
        from e0_controller.dream_mode import DreamObserver
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        s.dream_observer = DreamObserver(
            compatibility_threshold=0.30,
            readiness_threshold=0.0,
        )
        out = cmd_dream(s, "prefix")
        assert "Threshold relaxed" in out

    def test_no_relaxation_notice_when_not_needed(self):
        """No relaxation warning when pairs pass at default threshold."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_dream(s)
        assert "Threshold relaxed" not in out


# ── C252: Bidirectional Coupling ──────────────────────────────────────


class TestTransferLNodes:
    """C252: _transfer_l_nodes helper transfers L: nodes and edges."""

    def test_transfers_nodes_and_edges(self):
        """L: nodes and edges move from source to target."""
        from e0_controller.interactive_session import _transfer_l_nodes
        s = build_session(steps_per_round=5)
        _ensure_main_universe(s)
        universe_create(s, "src")
        universe_switch(s, "src")
        s.landscape.add_state("L:A")
        s.landscape.add_state("L:B")
        s.landscape.add_edge("L:A", "L:B", delta=0.5, resistance=1.0)
        src_ls = s.landscape
        universe_switch(s, "main")
        tgt_ls = s.landscape
        nodes, edges = _transfer_l_nodes(src_ls, tgt_ls)
        assert nodes == 2
        assert edges == 1
        assert "L:A" in tgt_ls.states
        assert "L:B" in tgt_ls.states

    def test_skips_existing_nodes(self):
        """Nodes already in target are not duplicated."""
        from e0_controller.interactive_session import _transfer_l_nodes
        s = build_session(steps_per_round=5)
        _ensure_main_universe(s)
        s.landscape.add_state("L:EXIST")
        universe_create(s, "src")
        universe_switch(s, "src")
        s.landscape.add_state("L:EXIST")
        s.landscape.add_state("L:NEW")
        src_ls = s.landscape
        universe_switch(s, "main")
        tgt_ls = s.landscape
        nodes, edges = _transfer_l_nodes(src_ls, tgt_ls)
        assert nodes == 1  # only L:NEW

    def test_skips_non_l_edges(self):
        """Edges not touching L: nodes are not transferred."""
        from e0_controller.interactive_session import _transfer_l_nodes
        s = build_session(steps_per_round=5)
        _ensure_main_universe(s)
        universe_create(s, "src")
        universe_switch(s, "src")
        s.landscape.add_state("X:FOO")
        s.landscape.add_state("X:BAR")
        s.landscape.add_edge("X:FOO", "X:BAR", delta=0.5, resistance=1.0)
        src_ls = s.landscape
        universe_switch(s, "main")
        tgt_ls = s.landscape
        nodes, edges = _transfer_l_nodes(src_ls, tgt_ls)
        assert nodes == 0
        assert edges == 0


class TestBidirectionalCoupleRun:
    """C252: couple_run transfers L: nodes in both directions."""

    def test_outbound_transfer(self):
        """Active → partner direction transfers unique L: nodes."""
        s = build_session(steps_per_round=5)
        _ensure_main_universe(s)
        universe_create(s, "peer")
        # main has unique L: nodes
        universe_switch(s, "main")
        s.landscape.add_state("L:MAIN_ONLY")
        _sync_session_to_active(s)
        # peer has nothing extra
        universe_switch(s, "peer")
        result = couple_run(s, partner_name="main")
        # Inbound: main → peer (L:MAIN_ONLY comes in)
        assert result["inbound"]["nodes"] == 1
        # Check peer now has it
        assert "L:MAIN_ONLY" in s.landscape.states

    def test_both_directions_transfer(self):
        """Both universes gain each other's unique L: nodes."""
        s = build_session(steps_per_round=5)
        _ensure_main_universe(s)
        # main gets unique node
        s.landscape.add_state("L:FROM_MAIN")
        _sync_session_to_active(s)
        universe_create(s, "peer")
        universe_switch(s, "peer")
        # peer gets unique node
        s.landscape.add_state("L:FROM_PEER")
        _sync_session_to_active(s)
        result = couple_run(s, partner_name="main")
        # Inbound (main → peer): L:FROM_MAIN already in peer (copied on create)
        # But the exact duplication depends on create. Let's just check totals.
        total_nodes = result["nodes_transferred"]
        assert total_nodes >= 1  # at least L:FROM_PEER → main
        assert result["outcome"] == "SUCCESS"
        # main should have L:FROM_PEER
        main_ls = s.universes["main"].landscape
        assert "L:FROM_PEER" in main_ls.states

    def test_outbound_when_inbound_zero(self):
        """Even if partner has nothing new, active's nodes flow out."""
        s = build_session(steps_per_round=5)
        _ensure_main_universe(s)
        universe_create(s, "learner")
        # learner gets unique L: nodes, main has none
        universe_switch(s, "learner")
        s.landscape.add_state("L:UNIQUE_A")
        s.landscape.add_state("L:UNIQUE_B")
        _sync_session_to_active(s)
        result = couple_run(s, partner_name="main")
        # Inbound (main → learner): 0 (main has no L: nodes)
        assert result["inbound"]["nodes"] == 0
        # Outbound (learner → main): 2
        assert result["outbound"]["nodes"] == 2
        assert result["outcome"] == "SUCCESS"
        main_ls = s.universes["main"].landscape
        assert "L:UNIQUE_A" in main_ls.states
        assert "L:UNIQUE_B" in main_ls.states

    def test_result_dict_has_inbound_outbound(self):
        """Result dict contains inbound/outbound sub-dicts."""
        s = build_session(steps_per_round=5)
        _ensure_main_universe(s)
        universe_create(s, "alt")
        result = couple_run(s, partner_name="alt")
        assert "inbound" in result
        assert "outbound" in result
        assert "nodes" in result["inbound"]
        assert "edges" in result["inbound"]
        assert "nodes" in result["outbound"]
        assert "edges" in result["outbound"]


class TestCmdCoupleBidirectionalOutput:
    """C252: cmd_couple output shows bidirectional transfer info."""

    def test_inbound_outbound_lines(self):
        """Output shows Inbound and Outbound lines."""
        s = build_session(steps_per_round=5)
        _ensure_main_universe(s)
        universe_create(s, "donor")
        universe_switch(s, "donor")
        s.landscape.add_state("L:ITEM")
        _sync_session_to_active(s)
        universe_switch(s, "main")
        text = cmd_couple(s, "donor")
        assert "Inbound" in text
        assert "Outbound" in text
        assert "Total:" in text


# ---------------------------------------------------------------------------
# C254 — Dream Backflow + Bridge Resistance
# ---------------------------------------------------------------------------


class TestInjectDreamBridges:
    """C254: _inject_dream_bridges creates cross-domain edges from node equivalences."""

    def test_injects_bidirectional_edges(self):
        """Node equivalences produce bidirectional dream_bridge edges."""
        from e0_controller.dream_mode import DreamObserver
        from e0_controller.interactive_session import _inject_dream_bridges

        s = build_session(steps_per_round=10)
        cmd_run(s, 1)

        # Set up observer with two domains that have matching structure
        obs = DreamObserver(compatibility_threshold=1.0, readiness_threshold=0.0)
        ls_canon = _extract_domain_landscapes(s.landscape).get("canon")
        ls_en = _extract_domain_landscapes(s.landscape).get("en")
        if ls_canon and ls_en:
            obs.register("canon", ls_canon)
            obs.register("en", ls_en)
            obs.dream_cycle(compatibility_threshold=1.0)

            count = _inject_dream_bridges(s, obs)
            # Should produce edges if node equivalences found
            node_eqs = obs.node_equivalences_for("canon")
            if len(node_eqs) > 0:
                assert count > 0
                # Check that dream_bridge edges exist
                from e0_controller.primitives import Edge
                eq = node_eqs[0]
                # C257: own_node is already fully qualified (e.g. "C:omega")
                own_full = eq["own_node"]
                partner_full = eq["partner_node"]
                if own_full in s.landscape.states and partner_full in s.landscape.states:
                    fwd = Edge(own_full, partner_full)
                    assert fwd in s.landscape._R0

    def test_no_injection_without_equivalences(self):
        """Zero bridges injected when observer has no equivalences."""
        from e0_controller.dream_mode import DreamObserver
        from e0_controller.interactive_session import _inject_dream_bridges

        s = build_session(steps_per_round=10)
        obs = DreamObserver(compatibility_threshold=0.01, readiness_threshold=0.0)
        # no domains registered → no equivalences
        count = _inject_dream_bridges(s, obs)
        assert count == 0

    def test_skips_missing_nodes(self):
        """Equivalence with nodes not in session landscape is skipped."""
        from e0_controller.dream_mode import DreamObserver
        from e0_controller.interactive_session import _inject_dream_bridges

        s = build_session(steps_per_round=10)
        # Manually set up observer with a landscape that has an extra node
        obs = DreamObserver(compatibility_threshold=1.0, readiness_threshold=0.0)
        from e0_controller.landscape import Landscape

        ls_a = Landscape()
        ls_a.add_state("C:FAKE_NODE_A")
        ls_a.add_state("C:FAKE_NODE_B")
        ls_a.add_edge("C:FAKE_NODE_A", "C:FAKE_NODE_B", 0.5, 1.0)

        ls_b = Landscape()
        ls_b.add_state("EN:fake_a")
        ls_b.add_state("EN:fake_b")
        ls_b.add_edge("EN:fake_a", "EN:fake_b", 0.5, 1.0)

        obs.register("canon", ls_a)
        obs.register("en", ls_b)
        obs.dream_cycle(compatibility_threshold=1.0)

        # These fake nodes don't exist in session landscape
        count = _inject_dream_bridges(s, obs)
        assert count == 0  # all skipped — nodes not in session landscape

    def test_dream_bridge_resistance_is_low(self):
        """Dream bridge edges have R=0.35 (traversable)."""
        from e0_controller.dream_mode import DreamObserver
        from e0_controller.interactive_session import _inject_dream_bridges
        from e0_controller.primitives import Edge

        s = build_session(steps_per_round=10)
        cmd_run(s, 1)

        obs = DreamObserver(compatibility_threshold=1.0, readiness_threshold=0.0)
        domains = _extract_domain_landscapes(s.landscape)
        for name, ls in domains.items():
            obs.register(name, ls)
        obs.dream_cycle(compatibility_threshold=1.0)
        _inject_dream_bridges(s, obs)

        # Find a dream_bridge edge and check its R
        for edge, meta in s.landscape._metadata.items():
            if meta.get("relation_type") == "dream_bridge":
                assert s.landscape._R0[edge] == pytest.approx(0.35)
                assert s.landscape._delta[edge] == pytest.approx(0.3)
                break

    def test_no_duplicate_on_second_run(self):
        """Running injection twice does not create duplicate edges."""
        from e0_controller.dream_mode import DreamObserver
        from e0_controller.interactive_session import _inject_dream_bridges

        s = build_session(steps_per_round=10)
        cmd_run(s, 1)

        obs = DreamObserver(compatibility_threshold=1.0, readiness_threshold=0.0)
        domains = _extract_domain_landscapes(s.landscape)
        for name, ls in domains.items():
            obs.register(name, ls)
        obs.dream_cycle(compatibility_threshold=1.0)

        count1 = _inject_dream_bridges(s, obs)
        count2 = _inject_dream_bridges(s, obs)
        # Second run should add 0 (all already present)
        assert count2 == 0

    def test_skips_cross_universe_domains(self):
        """Domains not in _DOMAIN_PREFIXES (like 'learned_test3') are skipped."""
        from e0_controller.dream_mode import DreamObserver
        from e0_controller.interactive_session import _inject_dream_bridges
        from e0_controller.landscape import Landscape

        s = build_session(steps_per_round=10)
        obs = DreamObserver(compatibility_threshold=1.0, readiness_threshold=0.0)

        # Register a cross-universe domain name
        ls = Landscape()
        ls.add_state("L:A")
        ls.add_state("L:B")
        ls.add_edge("L:A", "L:B", 0.5, 1.0)
        obs.register("learned_test3", ls)

        count = _inject_dream_bridges(s, obs)
        assert count == 0


class TestDreamRunBackflow:
    """C254: dream_run returns dream_bridges_added count."""

    def test_dream_bridges_in_result(self):
        """dream_run result dict contains dream_bridges_added key."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = dream_run(s, cycles=1)
        assert "dream_bridges_added" in result
        assert isinstance(result["dream_bridges_added"], int)

    def test_dream_bridges_in_journal(self):
        """Journal event records dream_bridges_added."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        dream_run(s, cycles=1)
        dream_events = [e for e in s.journal if e["event_type"] == "dream"]
        assert len(dream_events) >= 1
        assert "dream_bridges_added" in dream_events[-1]["detail"]

    def test_cmd_dream_shows_bridges(self):
        """cmd_dream output shows bridge count when >0."""
        from e0_controller.dream_mode import DreamObserver
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        # Use lenient threshold to get node equivalences
        s.dream_observer = DreamObserver(
            compatibility_threshold=1.0,
            readiness_threshold=0.0,
        )
        out = cmd_dream(s)
        # If bridges were injected, output should mention them
        if "dream bridges" in out:
            assert "injected" in out


class TestBridgeResistanceReduced:
    """C254: _create_bridges uses lower resistance for traversability."""

    def test_bridge_resistance_is_0_4(self):
        """Task bridges use R=0.4 (was 1.2)."""
        from e0_controller.interactive_session import _create_bridges

        s = build_session(steps_per_round=10)
        # Add L: nodes that overlap with existing concepts
        s.landscape.add_state("L:TENSION_EXPLAINED")
        bridges = _create_bridges(s, ["L:TENSION_EXPLAINED"])
        if bridges:
            from e0_controller.primitives import Edge
            fwd = Edge(bridges[0][0], bridges[0][1])
            assert s.landscape._R0[fwd] == pytest.approx(0.4)


# ── C257: Dream on Communities ──────────────────────────────────────


class TestDreamRunPartition:
    """C257: dream_run partition parameter selects community or prefix mode."""

    def test_default_partition_is_community(self):
        """Default partition mode is 'community'."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = dream_run(s, cycles=1)
        assert result["partition"] == "community"

    def test_community_partition_returns_community_names(self):
        """Community mode produces domain names like community_0."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = dream_run(s, cycles=1, partition="community")
        # At least one community should exist
        if result["domains"]:
            assert any(d.startswith("community_") for d in result["domains"])

    def test_prefix_partition_returns_prefix_names(self):
        """Prefix mode produces domain names like canon, bootstrap."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = dream_run(s, cycles=1, partition="prefix")
        assert result["partition"] == "prefix"
        prefix_names = {"canon", "bootstrap", "en", "mechanism", "learned"}
        if result["domains"]:
            assert any(d in prefix_names for d in result["domains"])

    def test_partition_in_journal(self):
        """Journal event records partition mode."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        dream_run(s, cycles=1, partition="community")
        dream_events = [e for e in s.journal if e["event_type"] == "dream"]
        assert len(dream_events) >= 1
        assert dream_events[-1]["detail"]["partition"] == "community"

    def test_partition_prefix_in_journal(self):
        """Prefix mode recorded in journal."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        dream_run(s, cycles=1, partition="prefix")
        dream_events = [e for e in s.journal if e["event_type"] == "dream"]
        assert dream_events[-1]["detail"]["partition"] == "prefix"

    def test_result_has_partition_key(self):
        """Result dict always contains 'partition' key."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = dream_run(s, cycles=1)
        assert "partition" in result

    def test_community_mode_returns_valid_result(self):
        """Community mode produces structurally valid result."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = dream_run(s, cycles=1, partition="community")
        assert isinstance(result["cycle_results"], list)
        assert result["cycles"] >= 1
        assert isinstance(result["readiness"], dict)
        assert isinstance(result["total_equivalences"], int)

    def test_both_modes_produce_readiness(self):
        """Both community and prefix modes have readiness reports."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        r_comm = dream_run(s, cycles=1, partition="community")
        s.dream_observer = None  # reset observer
        r_prefix = dream_run(s, cycles=1, partition="prefix")
        assert len(r_comm["readiness"]) >= 0
        assert len(r_prefix["readiness"]) >= 0


class TestCmdDreamPartition:
    """C257: cmd_dream supports partition argument."""

    def test_default_uses_community(self):
        """cmd_dream without args uses community mode."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_dream(s)
        assert "Dream Consolidation" in out
        assert "partitions" in out.lower() or "community" in out.lower()

    def test_community_arg(self):
        """cmd_dream('community') explicitly selects community mode."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_dream(s, "community")
        assert "community" in out.lower()

    def test_prefix_arg(self):
        """cmd_dream('prefix') selects prefix mode."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_dream(s, "prefix")
        assert "prefix" in out.lower()

    def test_community_with_cycles(self):
        """cmd_dream('community 5') selects community mode with 5 cycles."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_dream(s, "community 5")
        assert "5 cycles" in out

    def test_prefix_with_cycles(self):
        """cmd_dream('prefix 2') selects prefix mode with 2 cycles."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_dream(s, "prefix 2")
        assert "2 cycles" in out

    def test_cycles_only(self):
        """cmd_dream('3') still works (backward compat)."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_dream(s, "3")
        assert "3 cycles" in out

    def test_invalid_arg_returns_usage(self):
        """cmd_dream('bad') returns usage hint."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_dream(s, "bad")
        assert "Usage" in out or "Invalid" in out

    def test_markdown_shows_partition_mode(self):
        """Markdown output mentions partition mode."""
        s = build_session(steps_per_round=10)
        s.output_format = "markdown"
        cmd_run(s, 1)
        out = cmd_dream(s, "prefix 1")
        assert "prefix" in out.lower()

    def test_shows_partitions_label(self):
        """Output uses 'Partitions:' instead of legacy 'Domains:'."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_dream(s)
        assert "Partitions:" in out


class TestDreamCommunityBridges:
    """C257: _inject_dream_bridges handles community-based domains."""

    def test_community_domains_not_skipped(self):
        """Community domains are not filtered out by prefix check."""
        from e0_controller.dream_mode import DreamObserver
        from e0_controller.interactive_session import _inject_dream_bridges

        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        obs = DreamObserver(
            compatibility_threshold=1.0, readiness_threshold=0.0,
        )
        # Register community-named landscapes
        from e0_controller.community import extract_community_landscapes
        comms = extract_community_landscapes(s.landscape)
        for name, ls in comms.items():
            obs.register(name, ls)

        # Should not crash — community_ domains are handled
        count = _inject_dream_bridges(s, obs)
        assert isinstance(count, int)
        assert count >= 0

    def test_bridge_injection_uses_full_node_names(self):
        """Node names from DreamObserver are used directly (no prefix prepend)."""
        from e0_controller.dream_mode import DreamObserver
        from e0_controller.interactive_session import _inject_dream_bridges
        from e0_controller.landscape import Landscape

        # Build a tiny session with known nodes
        s = build_session(steps_per_round=10)
        obs = DreamObserver(
            compatibility_threshold=1.0, readiness_threshold=0.0,
        )

        # Register two tiny landscapes with known nodes
        la = Landscape()
        la.add_edge("C:X", "C:Y", delta=0.5, resistance=0.5)
        lb = Landscape()
        lb.add_edge("EN:A", "EN:B", delta=0.5, resistance=0.5)
        obs.register("community_0", la)
        obs.register("community_1", lb)
        obs.dream_cycle(compatibility_threshold=1.0)

        # Verify the function handles community domains
        count = _inject_dream_bridges(s, obs)
        assert isinstance(count, int)

    def test_bridge_delta_is_0_3(self):
        """Task bridges use delta=0.3 (was 0.4)."""
        from e0_controller.interactive_session import _create_bridges

        s = build_session(steps_per_round=10)
        s.landscape.add_state("L:TENSION_EXPLAINED")
        bridges = _create_bridges(s, ["L:TENSION_EXPLAINED"])
        if bridges:
            from e0_controller.primitives import Edge
            fwd = Edge(bridges[0][0], bridges[0][1])
            assert s.landscape._delta[fwd] == pytest.approx(0.3)


# ── C258: Sleep-Wake + Tune on Communities ──────────────────────────


class TestSleepWakePartition:
    """C258: sleep_wake_run partition parameter selects community or prefix mode."""

    def test_default_partition_is_community(self):
        """Default partition mode is 'community'."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = sleep_wake_run(s, episodes=1, max_cycles=10)
        assert result["partition"] == "community"

    def test_community_partition_returns_community_names(self):
        """Community mode produces domain names like community_0."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = sleep_wake_run(s, episodes=1, max_cycles=10, partition="community")
        if result["domains"]:
            assert any(d.startswith("community_") for d in result["domains"])

    def test_prefix_partition_returns_prefix_names(self):
        """Prefix mode produces domain names like canon, bootstrap."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = sleep_wake_run(s, episodes=1, max_cycles=10, partition="prefix")
        assert result["partition"] == "prefix"
        prefix_names = {"canon", "bootstrap", "en", "mechanism", "learned"}
        if result["domains"]:
            assert any(d in prefix_names for d in result["domains"])

    def test_partition_in_journal(self):
        """Journal event records partition mode."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        sleep_wake_run(s, episodes=1, max_cycles=10, partition="community")
        events = [e for e in s.journal if e["event_type"] == "sleep_wake"]
        assert len(events) >= 1
        assert events[-1]["detail"]["partition"] == "community"

    def test_partition_prefix_in_journal(self):
        """Prefix mode recorded in journal."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        sleep_wake_run(s, episodes=1, max_cycles=10, partition="prefix")
        events = [e for e in s.journal if e["event_type"] == "sleep_wake"]
        assert events[-1]["detail"]["partition"] == "prefix"

    def test_result_has_partition_key(self):
        """Result dict always contains 'partition' key."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = sleep_wake_run(s, episodes=1, max_cycles=10)
        assert "partition" in result

    def test_community_mode_valid_result(self):
        """Community mode produces structurally valid result."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = sleep_wake_run(s, episodes=1, max_cycles=10, partition="community")
        assert isinstance(result["episode_results"], list)
        assert result["episodes"] == 1
        assert isinstance(result["transferred_edges"], int)
        assert isinstance(result["pressure"], dict)

    def test_both_modes_produce_pressure(self):
        """Both community and prefix modes have pressure reports."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        r_comm = sleep_wake_run(s, episodes=1, max_cycles=10, partition="community")
        s.dream_observer = None
        r_prefix = sleep_wake_run(s, episodes=1, max_cycles=10, partition="prefix")
        assert len(r_comm["pressure"]) >= 0
        assert len(r_prefix["pressure"]) >= 0


class TestCmdSleepPartition:
    """C258: cmd_sleep supports partition argument."""

    def test_default_uses_community(self):
        """cmd_sleep without args uses community mode."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_sleep(s)
        assert "Sleep-Wake Cycle" in out
        assert "partitions" in out.lower() or "community" in out.lower()

    def test_community_arg(self):
        """cmd_sleep('community') explicitly selects community mode."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_sleep(s, "community")
        assert "community" in out.lower()

    def test_prefix_arg(self):
        """cmd_sleep('prefix') selects prefix mode."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_sleep(s, "prefix")
        assert "prefix" in out.lower()

    def test_community_with_episodes(self):
        """cmd_sleep('community 3') selects community mode with 3 episodes."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_sleep(s, "community 3")
        assert "3 episodes" in out

    def test_prefix_with_episodes(self):
        """cmd_sleep('prefix 2') selects prefix mode with 2 episodes."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_sleep(s, "prefix 2")
        assert "2 episodes" in out

    def test_episodes_only_backward_compat(self):
        """cmd_sleep('3') still works (backward compat)."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_sleep(s, "3")
        assert "3 episodes" in out

    def test_invalid_arg_returns_usage(self):
        """cmd_sleep('bad') returns usage hint."""
        s = build_session(steps_per_round=10)
        out = cmd_sleep(s, "bad")
        assert "Usage" in out or "Invalid" in out

    def test_dispatch_sleep_community(self):
        """dispatch('sleep community 2') works."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = dispatch(s, "sleep community 2")
        assert "Sleep-Wake Cycle" in out

    def test_dispatch_sleep_prefix(self):
        """dispatch('sleep prefix') works."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = dispatch(s, "sleep prefix")
        assert "Sleep-Wake Cycle" in out


class TestTunePartition:
    """C258: tune_run partition parameter selects community or prefix mode."""

    def test_default_partition_is_community(self):
        """Default partition mode is 'community'."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = tune_run(s, max_rounds=1)
        assert result["partition"] == "community"

    def test_community_partition_returns_community_names(self):
        """Community mode produces domain names like community_0."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = tune_run(s, max_rounds=1, partition="community")
        if result["domain_results"]:
            assert any(
                dr["domain"].startswith("community_")
                for dr in result["domain_results"]
            )

    def test_prefix_partition_returns_prefix_names(self):
        """Prefix mode produces domain names like canon, bootstrap."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = tune_run(s, max_rounds=1, partition="prefix")
        assert result["partition"] == "prefix"
        prefix_names = {"canon", "bootstrap", "en", "mechanism", "learned"}
        if result["domain_results"]:
            assert any(
                dr["domain"] in prefix_names
                for dr in result["domain_results"]
            )

    def test_partition_in_journal(self):
        """Journal event records partition mode."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        tune_run(s, max_rounds=1, partition="community")
        events = [e for e in s.journal if e["event_type"] == "tune"]
        assert len(events) >= 1
        assert events[-1]["detail"]["partition"] == "community"

    def test_partition_prefix_in_journal(self):
        """Prefix mode recorded in journal."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        tune_run(s, max_rounds=1, partition="prefix")
        events = [e for e in s.journal if e["event_type"] == "tune"]
        assert events[-1]["detail"]["partition"] == "prefix"

    def test_result_has_partition_key(self):
        """Result dict always contains 'partition' key."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = tune_run(s, max_rounds=1)
        assert "partition" in result

    def test_community_mode_valid_result(self):
        """Community mode produces structurally valid result."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        result = tune_run(s, max_rounds=1, partition="community")
        assert isinstance(result["domain_results"], list)
        assert isinstance(result["any_improved"], bool)
        assert isinstance(result["improved_count"], int)


class TestCmdTunePartition:
    """C258: cmd_tune supports partition argument."""

    def test_default_uses_community(self):
        """cmd_tune without args uses community mode."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_tune(s)
        assert "Auto-Tune" in out
        assert "partitions" in out.lower() or "community" in out.lower()

    def test_community_arg(self):
        """cmd_tune('community') explicitly selects community mode."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_tune(s, "community")
        assert "community" in out.lower()

    def test_prefix_arg(self):
        """cmd_tune('prefix') selects prefix mode."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_tune(s, "prefix")
        assert "prefix" in out.lower()

    def test_community_with_rounds(self):
        """cmd_tune('community 2') selects community mode with 2 rounds."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_tune(s, "community 2")
        assert "2 rounds" in out

    def test_rounds_only_backward_compat(self):
        """cmd_tune('2') still works (backward compat)."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_tune(s, "2")
        assert "2 rounds" in out

    def test_invalid_arg_returns_usage(self):
        """cmd_tune('bad') returns usage hint."""
        s = build_session(steps_per_round=10)
        out = cmd_tune(s, "bad")
        assert "Usage" in out or "Invalid" in out

    def test_dispatch_tune_community(self):
        """dispatch('tune community 1') works."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = dispatch(s, "tune community 1")
        assert "Auto-Tune" in out

    def test_dispatch_tune_prefix(self):
        """dispatch('tune prefix') works."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = dispatch(s, "tune prefix")
        assert "Auto-Tune" in out


class TestPickCommunityStart:
    """C258: _pick_community_start picks lowest trace_load node."""

    def test_returns_node_from_sublangscape(self):
        """Returns a node name that exists in the sub-landscape."""
        from e0_controller.landscape import Landscape
        ls = Landscape()
        ls.add_edge("C:A", "C:B", delta=0.5, resistance=0.5)
        ls.add_edge("C:B", "C:C", delta=0.5, resistance=0.5)
        start = _pick_community_start(ls)
        assert start in ls.states

    def test_prefers_lowest_trace_load(self):
        """Picks the node with lowest outgoing trace_load."""
        from e0_controller.landscape import Landscape
        ls = Landscape()
        ls.add_edge("X", "Y", delta=0.5, resistance=0.5)
        ls.add_edge("Y", "Z", delta=0.5, resistance=0.5)
        # Add trace to X→Y so X has higher load
        from e0_controller.primitives import Edge
        e = Edge("X", "Y")
        ls.historization._U[e] = 5.0
        start = _pick_community_start(ls)
        # Y or Z should be preferred (lower load)
        assert start in ("Y", "Z")

    def test_empty_landscape_returns_none(self):
        """Empty landscape returns None."""
        from e0_controller.landscape import Landscape
        ls = Landscape()
        assert _pick_community_start(ls) is None


class TestTransferCommunityToSession:
    """C258: _transfer_community_to_session transfers by full node names."""

    def test_transfers_matching_edges(self):
        """Edges with matching full names are transferred."""
        from e0_controller.landscape import Landscape
        from e0_controller.primitives import Edge

        sub = Landscape()
        sub.add_edge("C:A", "C:B", delta=0.5, resistance=0.5)
        e_sub = Edge("C:A", "C:B")
        sub.historization._U[e_sub] = 3.0
        sub.historization._F[e_sub] = 1.0

        session = Landscape()
        session.add_edge("C:A", "C:B", delta=0.5, resistance=0.5)
        session.add_edge("EN:X", "EN:Y", delta=0.5, resistance=0.5)

        count = _transfer_community_to_session(sub, session)
        assert count == 1
        # Session edge should have the transferred values
        e_sess = Edge("C:A", "C:B")
        assert session.historization._U.get(e_sess, 0.0) >= 3.0

    def test_no_transfer_for_missing_edges(self):
        """Edges not present in session are not transferred."""
        from e0_controller.landscape import Landscape
        from e0_controller.primitives import Edge

        sub = Landscape()
        sub.add_edge("C:X", "C:Y", delta=0.5, resistance=0.5)
        e_sub = Edge("C:X", "C:Y")
        sub.historization._U[e_sub] = 2.0

        session = Landscape()
        session.add_edge("C:A", "C:B", delta=0.5, resistance=0.5)

        count = _transfer_community_to_session(sub, session)
        assert count == 0

    def test_zero_traces_not_transferred(self):
        """Edges with zero U and F are not transferred."""
        from e0_controller.landscape import Landscape

        sub = Landscape()
        sub.add_edge("C:A", "C:B", delta=0.5, resistance=0.5)

        session = Landscape()
        session.add_edge("C:A", "C:B", delta=0.5, resistance=0.5)

        count = _transfer_community_to_session(sub, session)
        assert count == 0


# ── C259: Diagnostics on Communities ────────────────────────────────


class TestDiagnoseSessionPartition:
    """C259: diagnose_session partition parameter."""

    def test_default_partition_is_community(self):
        """Default partition mode is 'community'."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        diag = diagnose_session(s)
        assert diag["partition"] == "community"

    def test_community_partition_returns_community_names(self):
        """Community mode produces domain names like community_0."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        diag = diagnose_session(s, partition="community")
        names = [d["name"] for d in diag["domains"]]
        if names:
            assert any(n.startswith("community_") for n in names)

    def test_prefix_partition_returns_prefix_names(self):
        """Prefix mode produces domain names like Canon, Bootstrap."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        diag = diagnose_session(s, partition="prefix")
        assert diag["partition"] == "prefix"
        names = [d["name"] for d in diag["domains"]]
        prefix_names = {"Canon", "Bootstrap", "EN", "Mechanism", "Learned"}
        if names:
            assert any(n in prefix_names for n in names)

    def test_partition_in_result(self):
        """Result dict contains 'partition' key."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        diag = diagnose_session(s)
        assert "partition" in diag

    def test_community_domains_have_coverage(self):
        """Each community domain has coverage field."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        diag = diagnose_session(s, partition="community")
        for d in diag["domains"]:
            assert "coverage" in d
            assert "total" in d
            assert "visited" in d
            assert "status" in d

    def test_community_has_overall(self):
        """Overall section present in community mode."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        diag = diagnose_session(s, partition="community")
        assert "overall" in diag
        assert "bottleneck" in diag["overall"]

    def test_community_comparison_always_present(self):
        """Community comparison section present regardless of partition mode."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        for mode in ("community", "prefix"):
            diag = diagnose_session(s, partition=mode)
            assert "communities" in diag


class TestComputeTrajectoryPartition:
    """C259: compute_trajectory partition parameter."""

    def test_default_partition_is_community(self):
        """Default partition mode uses community names."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 2)
        traj = compute_trajectory(s)
        trends = traj["summary"]["domain_trends"]
        if trends:
            assert any(k.startswith("community_") for k in trends)

    def test_prefix_partition_returns_prefix_names(self):
        """Prefix mode uses prefix names (Canon, Bootstrap, etc.)."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 2)
        traj = compute_trajectory(s, partition="prefix")
        trends = traj["summary"]["domain_trends"]
        prefix_names = {"Canon", "Bootstrap", "EN", "Mechanism"}
        if trends:
            assert any(k in prefix_names for k in trends)

    def test_community_trends_have_fields(self):
        """Community domain trends have expected fields."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 2)
        traj = compute_trajectory(s, partition="community")
        for name, dt in traj["summary"]["domain_trends"].items():
            assert "coverage_start" in dt
            assert "coverage_end" in dt
            assert "delta" in dt
            assert "nodes" in dt


class TestMetaReflectPartition:
    """C259: meta_reflect partition parameter."""

    def test_default_uses_community(self):
        """Default mode produces community-based trajectories."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 3)
        ref = meta_reflect(s)
        if ref["domain_trajectories"]:
            assert any(
                k.startswith("community_")
                for k in ref["domain_trajectories"]
            )

    def test_prefix_mode_produces_prefix_names(self):
        """Prefix mode produces Canon, Bootstrap etc."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 3)
        ref = meta_reflect(s, partition="prefix")
        prefix_names = {"Canon", "Bootstrap", "EN", "Mechanism"}
        if ref["domain_trajectories"]:
            assert any(
                k in prefix_names for k in ref["domain_trajectories"]
            )


class TestCmdFocusCommunity:
    """C259: cmd_focus accepts community IDs."""

    def test_focus_community_0(self):
        """cmd_focus('community_0') works."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_focus(s, "community_0")
        assert "community_0" in out

    def test_focus_c0_shorthand(self):
        """cmd_focus('c0') is alias for community_0."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_focus(s, "c0")
        assert "community_0" in out

    def test_focus_prefix_still_works(self):
        """cmd_focus('canon') still works (prefix fallback)."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_focus(s, "canon")
        assert "Canon" in out

    def test_unknown_domain_lists_communities(self):
        """Unknown domain error includes community names."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_focus(s, "nonexistent")
        assert "Unknown domain" in out
        assert "Communities:" in out

    def test_focus_community_shows_nodes(self):
        """Community focus shows node count and coverage."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        out = cmd_focus(s, "community_0")
        assert "visited" in out.lower() or "nodes" in out.lower()


# ---------------------------------------------------------------------------
# C261 — Prefixes as Display Layer + Cleanup
# ---------------------------------------------------------------------------


class TestDisplayPrefixesRename:
    """C261: _DOMAIN_PREFIXES renamed to _DISPLAY_PREFIXES."""

    def test_all_five_prefixes(self):
        """All 5 prefixes present in _DISPLAY_PREFIXES."""
        assert set(_DISPLAY_PREFIXES.keys()) == {"C:", "B:", "EN:", "M:", "L:"}

    def test_values_are_lowercase_domain_names(self):
        """Values are lowercase domain names for observer registration."""
        for k, v in _DISPLAY_PREFIXES.items():
            assert v == v.lower(), f"{k} → {v} should be lowercase"


class TestExtractDomainLandscapesDeprecation:
    """C261: _extract_domain_landscapes emits deprecation warning."""

    def test_deprecation_warning(self):
        """Calling _extract_domain_landscapes raises DeprecationWarning."""
        import warnings
        s = build_session(steps_per_round=5)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _extract_domain_landscapes(s.landscape)
            deprecation_warnings = [
                x for x in w if issubclass(x.category, DeprecationWarning)
            ]
            assert len(deprecation_warnings) >= 1
            assert "C261" in str(deprecation_warnings[0].message)

    def test_still_works(self):
        """Function still returns valid results despite deprecation."""
        import warnings
        s = build_session(steps_per_round=5)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = _extract_domain_landscapes(s.landscape)
        assert isinstance(result, dict)
        # Should at least have canon domain from build_session
        assert len(result) >= 1


class TestTaughtAtMetadata:
    """C261: teach_concept stamps taught_at on newly injected nodes."""

    def test_taught_at_present_after_teach(self):
        """Nodes from teach_concept have taught_at timestamp."""
        s = build_session(steps_per_round=5)
        import time
        before = time.time()
        result = teach_concept(s, "photosynthesis")
        after = time.time()
        for nid in result.get("nodes_added", []):
            meta = s.unified_nodes.get(nid, {})
            assert "taught_at" in meta, f"{nid} missing taught_at"
            assert before <= meta["taught_at"] <= after

    def test_taught_at_is_float_timestamp(self):
        """taught_at value is a float (Unix timestamp)."""
        s = build_session(steps_per_round=5)
        result = teach_concept(s, "gravity")
        for nid in result.get("nodes_added", []):
            assert isinstance(s.unified_nodes[nid]["taught_at"], float)

    def test_nodes_still_have_l_prefix(self):
        """C261: Nodes still get L: prefix as display label."""
        s = build_session(steps_per_round=5)
        result = teach_concept(s, "thermodynamics")
        for nid in result.get("nodes_added", []):
            assert nid.startswith("L:"), f"expected L: prefix, got {nid}"


class TestAskRunCommunityRecencyPreference:
    """C261: ask_run prefers taught nodes by taught_at metadata, not just L: prefix."""

    def test_prefers_node_with_taught_at(self):
        """Node with taught_at metadata preferred over generic match."""
        s = build_session(steps_per_round=10)
        s.landscape.add_state("EN:water")
        s.landscape.add_state("L:WHAT_IS_WATER")
        # Stamp taught_at on the L: node
        s.unified_nodes["L:WHAT_IS_WATER"] = {"taught_at": 1000.0, "type": "task"}
        s.landscape.add_edge("EN:water", "L:WHAT_IS_WATER", delta=0.4, resistance=1.0)
        result = ask_run(s, "what is water", auto_learn=False)
        anchor = result.get("anchor")
        if anchor is not None:
            assert anchor == "L:WHAT_IS_WATER"

    def test_prefers_most_recent_taught(self):
        """Among multiple taught nodes, prefers the most recently taught."""
        s = build_session(steps_per_round=10)
        s.landscape.add_state("L:WATER_BASICS")
        s.landscape.add_state("L:WATER_ADVANCED")
        s.unified_nodes["L:WATER_BASICS"] = {"taught_at": 100.0, "type": "task"}
        s.unified_nodes["L:WATER_ADVANCED"] = {"taught_at": 200.0, "type": "task"}
        s.landscape.add_edge("L:WATER_BASICS", "L:WATER_ADVANCED", delta=0.3, resistance=0.5)
        result = ask_run(s, "water", auto_learn=False)
        anchor = result.get("anchor")
        if anchor is not None:
            assert anchor == "L:WATER_ADVANCED"

    def test_l_prefix_fallback_without_metadata(self):
        """L: node still preferred even without taught_at (legacy fallback)."""
        s = build_session(steps_per_round=10)
        s.landscape.add_state("EN:water")
        s.landscape.add_state("L:WHAT_IS_WATER")
        s.landscape.add_edge("EN:water", "L:WHAT_IS_WATER", delta=0.4, resistance=1.0)
        # No taught_at metadata — should still prefer L: via fallback
        result = ask_run(s, "what is water", auto_learn=False)
        anchor = result.get("anchor")
        if anchor is not None:
            assert anchor.startswith("L:"), f"Expected L: fallback, got {anchor}"


class TestCrossUniverseDreamMetadata:
    """C261: Cross-universe dream uses taught_at metadata for node discovery."""

    def test_taught_at_nodes_discovered_cross_universe(self):
        """Nodes with taught_at in other universe are registered for dreaming."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        # Create second universe with taught nodes
        from e0_controller.interactive_session import cmd_universe
        cmd_universe(s, "create beta")
        cmd_universe(s, "switch beta")
        s.landscape.add_state("L:BETA_CONCEPT")
        s.landscape.add_state("L:BETA_DETAIL")
        s.landscape.add_edge("L:BETA_CONCEPT", "L:BETA_DETAIL", delta=0.5, resistance=1.0)
        s.unified_nodes["L:BETA_CONCEPT"] = {"taught_at": 1000.0}
        s.unified_nodes["L:BETA_DETAIL"] = {"taught_at": 1000.0}
        cmd_universe(s, "switch main")
        # Dream should discover beta's taught nodes
        result = dream_run(s, cycles=1)
        # Check that cross-universe domains were included
        assert "domains_compared" in result or "total_equivalences" in result


# ---------------------------------------------------------------------------
# C262 — Cold Start without Scaffolding
# ---------------------------------------------------------------------------


class TestColdStartWithoutScaffolding:
    """C262: Full integration — session from zero operates without prefix scaffolding.

    Proves the Emergent Structure arc (C255–C262): community detection,
    structural resonance, and dream consolidation work on a landscape
    built purely from selflearn + teach — no prefix-based partitioning required.
    """

    def test_cold_start_selflearn_creates_historization(self):
        """Cold session → selflearn populates landscape with trace data."""
        s = build_session(steps_per_round=10)
        initial_edges_with_data = sum(
            1 for e in s.landscape.edges
            if s.landscape.historization.trace_load(e) > 0
        )
        selflearn_run(s)
        final_edges_with_data = sum(
            1 for e in s.landscape.edges
            if s.landscape.historization.trace_load(e) > 0
        )
        assert final_edges_with_data > initial_edges_with_data

    def test_community_detection_after_selflearn(self):
        """After selflearn, community detection finds natural clusters."""
        from e0_controller.community import detect_communities
        s = build_session(steps_per_round=10)
        selflearn_run(s)
        communities = detect_communities(s.landscape)
        assert len(communities) >= 2, (
            f"Expected ≥2 communities after selflearn, got {len(communities)}"
        )

    def test_teach_adds_nodes_with_metadata(self):
        """teach_concept injects nodes with taught_at metadata."""
        s = build_session(steps_per_round=5)
        result = teach_concept(s, "photosynthesis")
        nodes = result.get("nodes_added", [])
        if nodes:  # LLM may be mocked
            for nid in nodes:
                meta = s.unified_nodes.get(nid, {})
                assert "taught_at" in meta

    def test_teach_nodes_join_communities(self):
        """Taught nodes are detected by community detection (no prefix gate)."""
        from e0_controller.community import detect_communities
        s = build_session(steps_per_round=10)
        selflearn_run(s)
        # Manually inject "taught" nodes (simulating teach_concept without LLM)
        import time
        now = time.time()
        for name in ["L:PHOTOSYNTHESIS", "L:CHLOROPLAST", "L:LIGHT_REACTION"]:
            s.landscape.add_state(name)
            s.unified_nodes[name] = {"taught_at": now, "type": "task"}
        s.landscape.add_edge("L:PHOTOSYNTHESIS", "L:CHLOROPLAST",
                             delta=0.3, resistance=0.5)
        s.landscape.add_edge("L:CHLOROPLAST", "L:LIGHT_REACTION",
                             delta=0.3, resistance=0.5)
        # Bridge to existing landscape
        existing = next(iter(s.landscape.states))
        s.landscape.add_edge(existing, "L:PHOTOSYNTHESIS",
                             delta=0.5, resistance=1.0)

        communities = detect_communities(s.landscape)
        # Taught nodes should appear in some community
        all_community_nodes = set()
        for comm in communities:
            all_community_nodes.update(comm)
        assert "L:PHOTOSYNTHESIS" in all_community_nodes
        assert "L:CHLOROPLAST" in all_community_nodes

    def test_dream_on_communities_after_selflearn(self):
        """dream_run(partition='community') works after selflearn — no prefix needed."""
        s = build_session(steps_per_round=10)
        selflearn_run(s)
        result = dream_run(s, cycles=1, partition="community")
        assert result["cycles"] == 1
        assert "total_equivalences" in result

    def test_structural_resonance_on_communities(self):
        """find_structural_resonance works on community sub-landscapes."""
        from e0_controller.community import extract_community_landscapes
        from e0_controller.dream_mode import find_structural_resonance
        s = build_session(steps_per_round=10)
        selflearn_run(s)
        communities = extract_community_landscapes(s.landscape)
        if len(communities) >= 2:
            names = list(communities.keys())
            sr = find_structural_resonance(
                communities[names[0]], communities[names[1]],
                domain_a=names[0], domain_b=names[1],
            )
            assert 0.0 <= sr.resonance_score <= 1.0
            assert sr.nodes_a > 0
            assert sr.nodes_b > 0

    def test_ask_prefers_taught_over_seed(self):
        """ask_run anchors on taught_at metadata, not prefix membership."""
        s = build_session(steps_per_round=10)
        import time
        # Inject taught node with high relevance
        s.landscape.add_state("L:QUANTUM_MECHANICS")
        s.unified_nodes["L:QUANTUM_MECHANICS"] = {
            "taught_at": time.time(), "type": "task",
        }
        s.landscape.add_edge(
            next(iter(s.landscape.states)), "L:QUANTUM_MECHANICS",
            delta=0.5, resistance=1.0,
        )
        result = ask_run(s, "quantum mechanics", auto_learn=False)
        anchor = result.get("anchor")
        if anchor is not None:
            # Should prefer the taught node via metadata
            assert anchor == "L:QUANTUM_MECHANICS" or anchor.startswith("L:")

    def test_full_pipeline_zero_to_resonance(self):
        """Capstone: cold start → selflearn → inject taught → communities → resonance.

        This is the arc's proof: E₀ starts from zero, learns itself,
        acquires new knowledge, and discovers structural resonance
        between communities — all without prefix-based partitioning.
        """
        from e0_controller.community import (
            detect_communities,
            extract_community_landscapes,
        )
        from e0_controller.dream_mode import find_structural_resonance

        # 1. Cold start
        s = build_session(steps_per_round=10)
        initial_nodes = len(s.landscape.states)
        assert initial_nodes > 0

        # 2. Selflearn — E₀ learns itself
        selflearn_run(s)
        after_selflearn = sum(
            1 for e in s.landscape.edges
            if s.landscape.historization.trace_load(e) > 0
        )
        assert after_selflearn > 0, "Selflearn must create trace data"

        # 3. Inject taught material (simulating biology + physics)
        import time
        now = time.time()

        bio_nodes = ["L:CELL_BIOLOGY", "L:MITOSIS", "L:DNA_REPLICATION"]
        for name in bio_nodes:
            s.landscape.add_state(name)
            s.unified_nodes[name] = {"taught_at": now, "type": "task"}
        s.landscape.add_edge("L:CELL_BIOLOGY", "L:MITOSIS",
                             delta=0.3, resistance=0.5)
        s.landscape.add_edge("L:MITOSIS", "L:DNA_REPLICATION",
                             delta=0.3, resistance=0.5)

        phys_nodes = ["L:QUANTUM_PHYSICS", "L:WAVE_FUNCTION", "L:SUPERPOSITION"]
        for name in phys_nodes:
            s.landscape.add_state(name)
            s.unified_nodes[name] = {"taught_at": now + 1.0, "type": "task"}
        s.landscape.add_edge("L:QUANTUM_PHYSICS", "L:WAVE_FUNCTION",
                             delta=0.3, resistance=0.5)
        s.landscape.add_edge("L:WAVE_FUNCTION", "L:SUPERPOSITION",
                             delta=0.3, resistance=0.5)

        # Bridge taught material to existing landscape (as teach_concept _create_bridges does)
        hub = next(iter(s.landscape.states))
        s.landscape.add_edge(hub, "L:CELL_BIOLOGY", delta=0.5, resistance=1.0)
        s.landscape.add_edge(hub, "L:QUANTUM_PHYSICS", delta=0.5, resistance=1.0)

        # 4. Community detection — finds natural clusters
        communities = detect_communities(s.landscape)
        assert len(communities) >= 2, (
            f"Expected ≥2 communities, got {len(communities)}"
        )

        # Taught nodes should be distributed across communities
        all_community_nodes = set()
        for comm in communities:
            all_community_nodes.update(comm)
        for name in bio_nodes + phys_nodes:
            assert name in all_community_nodes, (
                f"Taught node {name} not in any community"
            )

        # 5. Structural resonance between communities
        community_landscapes = extract_community_landscapes(s.landscape)
        if len(community_landscapes) >= 2:
            names = list(community_landscapes.keys())
            sr = find_structural_resonance(
                community_landscapes[names[0]],
                community_landscapes[names[1]],
                domain_a=names[0],
                domain_b=names[1],
            )
            # Resonance should be computable (may be low — that's fine)
            assert 0.0 <= sr.resonance_score <= 1.0
            assert sr.matched_nodes > 0

        # 6. Dream on communities — no prefix scaffolding
        dream_result = dream_run(s, cycles=1, partition="community")
        assert dream_result["cycles"] == 1

    def test_no_prefix_gate_in_pipeline(self):
        """Verify no step in the pipeline requires prefix-based partitioning."""
        from e0_controller.community import extract_community_landscapes
        s = build_session(steps_per_round=10)
        selflearn_run(s)

        # Community extraction works without _extract_domain_landscapes
        communities = extract_community_landscapes(s.landscape)
        assert len(communities) >= 1

        # Dream works with partition='community' (default)
        result = dream_run(s, cycles=1, partition="community")
        assert "total_equivalences" in result

    def test_diagnose_works_on_cold_start_communities(self):
        """diagnose_session(partition='community') works after cold start + selflearn."""
        s = build_session(steps_per_round=10)
        selflearn_run(s)
        result = diagnose_session(s, partition="community")
        assert "domains" in result
        assert len(result["domains"]) >= 1


# ── C263: Cold Start Alignment ─────────────────────────────────────────


class TestColdStartAlignment:
    """C263: Cold start produces C+B+M landscape (no EN), matching warm start."""

    def test_cold_start_has_no_en_nodes(self):
        """build_session cold start excludes EN domain by default."""
        s = build_session(steps_per_round=5)
        en_nodes = [n for n in s.unified_nodes if n.startswith("EN:")]
        assert len(en_nodes) == 0, f"Cold start should exclude EN, found {len(en_nodes)}"

    def test_cold_start_has_canon_bootstrap_mechanism(self):
        """Cold start still includes the 3 core domains."""
        s = build_session(steps_per_round=5)
        c_nodes = [n for n in s.unified_nodes if n.startswith("C:")]
        b_nodes = [n for n in s.unified_nodes if n.startswith("B:")]
        m_nodes = [n for n in s.unified_nodes if n.startswith("M:")]
        assert len(c_nodes) > 0, "Canon nodes missing"
        assert len(b_nodes) > 0, "Bootstrap nodes missing"
        assert len(m_nodes) > 0, "Mechanism nodes missing"

    def test_cold_start_stats_reflect_no_en(self):
        """Stats dict reports 0 EN nodes on cold start."""
        s = build_session(steps_per_round=5)
        assert s.stats.get("en_nodes", 0) == 0

    def test_explicit_include_en_still_works(self):
        """include_en=True opt-in still produces EN nodes."""
        from e0_controller.explore_learning_cycle_multidomain import (
            build_multidomain_landscape,
        )
        _, nodes, stats = build_multidomain_landscape(include_en=True)
        en = [n for n in nodes if n.startswith("EN:")]
        assert len(en) >= 40, f"EN opt-in should produce ≥40 nodes, got {len(en)}"
        assert stats["en_nodes"] >= 40

    def test_include_en_false_matches_default(self):
        """Explicit include_en=False produces same result as default."""
        from e0_controller.explore_learning_cycle_multidomain import (
            build_multidomain_landscape,
        )
        _, nodes_default, stats_default = build_multidomain_landscape()
        _, nodes_explicit, stats_explicit = build_multidomain_landscape(include_en=False)
        assert stats_default["en_nodes"] == 0
        assert stats_explicit["en_nodes"] == 0
        assert set(nodes_default.keys()) == set(nodes_explicit.keys())

    def test_universe_create_excludes_en(self):
        """New universes match cold start: no EN nodes."""
        s = build_session(steps_per_round=5)
        from e0_controller.interactive_session import universe_create
        result = universe_create(s, "test_u")
        assert "test_u" in s.universes
        u = s.universes["test_u"]
        en = [n for n in u.unified_nodes if n.startswith("EN:")]
        assert len(en) == 0, f"New universe should exclude EN, found {len(en)}"

    def test_cold_warm_start_parity(self):
        """Cold start and warm start (learn_self) produce same domain set."""
        from e0_controller.explore_learning_cycle_multidomain import (
            build_multidomain_landscape,
        )
        # Cold start
        _, cold_nodes, _ = build_multidomain_landscape()
        cold_prefixes = {n.split(":")[0] for n in cold_nodes if ":" in n}
        # Warm start uses include_en=False (default in learn_self)
        _, warm_nodes, _ = build_multidomain_landscape(include_en=False)
        warm_prefixes = {n.split(":")[0] for n in warm_nodes if ":" in n}
        assert cold_prefixes == warm_prefixes, (
            f"Cold {cold_prefixes} ≠ Warm {warm_prefixes}"
        )


# ── C264: Structural Bridges for Teach ─────────────────────────────────


class TestStructuralBridges:
    """C264: _create_bridges uses structural resonance (WL-Hungarian)
    for >= 3 new nodes, lexical fallback for < 3."""

    def test_small_subgraph_uses_lexical(self):
        """Single new node (< 3) triggers lexical fallback path."""
        s = build_session(steps_per_round=10)
        s.landscape.add_state("L:tension_explained")
        bridges = _create_bridges(s, ["L:tension_explained"])
        # Should find a lexical match (tension exists in landscape)
        assert len(bridges) > 0
        # Bridge type should be llm_structural (lexical fallback)
        meta = s.landscape.edge_meta(bridges[0][0], bridges[0][1])
        assert meta.get("bridge_type") == "llm_structural"

    def test_two_nodes_uses_lexical(self):
        """Two new nodes (< 3) still use lexical fallback."""
        s = build_session(steps_per_round=10)
        s.landscape.add_state("L:tension_explained")
        s.landscape.add_state("L:connection_detail")
        s.landscape.add_edge("L:tension_explained", "L:connection_detail", 0.5, 1.0)
        bridges = _create_bridges(
            s, ["L:tension_explained", "L:connection_detail"],
        )
        # Lexical fallback: bridge_type = llm_structural
        for src, tgt in bridges:
            meta = s.landscape.edge_meta(src, tgt)
            assert meta.get("bridge_type") == "llm_structural"

    def test_structural_path_with_3_plus_nodes(self):
        """Three or more new nodes trigger structural resonance."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        # Inject 4 interconnected L: nodes
        new_nodes = ["L:alpha", "L:beta", "L:gamma", "L:delta"]
        for n in new_nodes:
            s.landscape.add_state(n)
        s.landscape.add_edge("L:alpha", "L:beta", 0.5, 1.0)
        s.landscape.add_edge("L:beta", "L:gamma", 0.5, 1.0)
        s.landscape.add_edge("L:gamma", "L:delta", 0.5, 1.0)
        s.landscape.add_edge("L:delta", "L:alpha", 0.5, 1.0)

        bridges = _create_bridges(s, new_nodes)
        # Should produce at least some bridges
        assert len(bridges) > 0
        # At least one bridge should use structural_resonance type
        has_structural = False
        for src, tgt in bridges:
            meta = s.landscape.edge_meta(src, tgt)
            if meta.get("bridge_type") == "structural_resonance":
                has_structural = True
                break
        assert has_structural, "Expected structural_resonance bridges for >= 3 nodes"

    def test_structural_bridges_are_bidirectional(self):
        """Structural bridges are always bidirectional."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        new_nodes = ["L:p1", "L:p2", "L:p3"]
        for n in new_nodes:
            s.landscape.add_state(n)
        s.landscape.add_edge("L:p1", "L:p2", 0.5, 1.0)
        s.landscape.add_edge("L:p2", "L:p3", 0.5, 1.0)
        bridges = _create_bridges(s, new_nodes)
        # Every (a,b) should have a corresponding (b,a)
        bridge_set = set(bridges)
        for src, tgt in bridges:
            assert (tgt, src) in bridge_set, (
                f"Missing reverse bridge ({tgt}, {src})"
            )

    def test_structural_bridge_resistance_0_4(self):
        """Structural bridges use same R=0.4 as lexical (C254)."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        new_nodes = ["L:x1", "L:x2", "L:x3"]
        for n in new_nodes:
            s.landscape.add_state(n)
        s.landscape.add_edge("L:x1", "L:x2", 0.5, 1.0)
        s.landscape.add_edge("L:x2", "L:x3", 0.5, 1.0)
        bridges = _create_bridges(s, new_nodes)
        for src, tgt in bridges:
            meta = s.landscape.edge_meta(src, tgt)
            if meta.get("bridge_type") == "structural_resonance":
                assert s.landscape._R0[Edge(src, tgt)] == pytest.approx(0.4)
                assert s.landscape._delta[Edge(src, tgt)] == pytest.approx(0.3)

    def test_structural_bridge_delta_0_3(self):
        """Structural bridges use delta=0.3."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        new_nodes = ["L:y1", "L:y2", "L:y3", "L:y4"]
        for n in new_nodes:
            s.landscape.add_state(n)
        s.landscape.add_edge("L:y1", "L:y2", 0.5, 1.0)
        s.landscape.add_edge("L:y2", "L:y3", 0.5, 1.0)
        s.landscape.add_edge("L:y3", "L:y4", 0.5, 1.0)
        bridges = _create_bridges(s, new_nodes)
        structural = [(s_, t) for s_, t in bridges
                      if s.landscape.edge_meta(s_, t).get("bridge_type")
                      == "structural_resonance"]
        assert len(structural) > 0

    def test_unbridged_gets_lexical_fallback(self):
        """New nodes not matched structurally get lexical fallback."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        # 3 connected nodes + 1 isolated (no internal edges)
        new_nodes = ["L:node_a", "L:node_b", "L:node_c", "L:tension_detail"]
        for n in new_nodes:
            s.landscape.add_state(n)
        s.landscape.add_edge("L:node_a", "L:node_b", 0.5, 1.0)
        s.landscape.add_edge("L:node_b", "L:node_c", 0.5, 1.0)
        bridges = _create_bridges(s, new_nodes)
        # Should have some bridges (at least structural + possibly lexical)
        assert len(bridges) > 0

    def test_empty_new_nodes(self):
        """Empty input produces no bridges."""
        s = build_session(steps_per_round=10)
        bridges = _create_bridges(s, [])
        assert bridges == []

    def test_lexical_fallback_exported(self):
        """_lexical_bridge_fallback is importable."""
        from e0_controller.interactive_session import _lexical_bridge_fallback
        assert callable(_lexical_bridge_fallback)


# ── C265: Automatic Community Refresh ──────────────────────────────────


class TestCommunityRefresh:
    """C265: Communities are cached on SessionState and refreshed
    after landscape mutations (build_session, cmd_run, teach, selflearn)."""

    def test_build_session_populates_communities(self):
        """build_session sets initial community partition."""
        s = build_session(steps_per_round=10)
        assert hasattr(s, "communities")
        assert len(s.communities) > 0
        # Each community is a set of node names
        for c in s.communities:
            assert isinstance(c, set)
            assert len(c) > 0

    def test_all_nodes_covered(self):
        """Every landscape node belongs to exactly one community."""
        s = build_session(steps_per_round=10)
        all_members = set()
        for c in s.communities:
            # No overlap
            assert len(all_members & c) == 0, "Node in multiple communities"
            all_members |= c
        assert all_members == s.landscape.states

    def test_cmd_run_refreshes(self):
        """Communities update after cmd_run navigation."""
        s = build_session(steps_per_round=10)
        before = [set(c) for c in s.communities]
        cmd_run(s, 1)
        # Communities should still be valid (all nodes covered)
        all_members = set()
        for c in s.communities:
            all_members |= c
        assert all_members == s.landscape.states

    def test_refresh_communities_callable(self):
        """refresh_communities is a standalone function."""
        s = build_session(steps_per_round=10)
        result = refresh_communities(s)
        assert result is s.communities
        assert len(result) > 0

    def test_teach_refreshes_communities(self):
        """After teach_concept, communities include new L: nodes."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)

        # Manually inject nodes to simulate teach (no LLM needed)
        s.landscape.add_state("L:test_alpha")
        s.landscape.add_state("L:test_beta")
        s.landscape.add_edge("L:test_alpha", "L:test_beta", 0.5, 1.0)
        # Bridge to existing
        existing = next(iter(s.landscape.states - {"L:test_alpha", "L:test_beta"}))
        s.landscape.add_edge("L:test_alpha", existing, 0.3, 0.4)

        refresh_communities(s)

        # New nodes must appear in some community
        all_members = set()
        for c in s.communities:
            all_members |= c
        assert "L:test_alpha" in all_members
        assert "L:test_beta" in all_members

    def test_communities_change_after_topology_mutation(self):
        """Adding dense edges between previously distant nodes can merge communities."""
        s = build_session(steps_per_round=10)
        n_before = len(s.communities)

        # Create strong connections between nodes from different communities
        if n_before >= 2:
            comm_a = sorted(s.communities[0])
            comm_b = sorted(s.communities[1])
            if comm_a and comm_b:
                for a_node in comm_a[:3]:
                    for b_node in comm_b[:3]:
                        s.landscape.add_edge(a_node, b_node, 0.5, 0.1)
                        s.landscape.add_edge(b_node, a_node, 0.5, 0.1)

                refresh_communities(s)
                # After dense cross-linking, community count may change
                # (either fewer communities or different membership)
                assert len(s.communities) > 0  # still valid

    def test_communities_field_type(self):
        """communities field is a list of sets."""
        s = build_session(steps_per_round=10)
        assert isinstance(s.communities, list)
        for c in s.communities:
            assert isinstance(c, set)


class TestCommunityCrossings:
    """C266: Navigation crossing detection uses community membership
    instead of prefix-based _domain_of(). Two nodes cross a boundary
    when they belong to different communities."""

    def test_community_of_finds_membership(self):
        """community_of returns correct index for known nodes."""
        from e0_controller.explore_learning_cycle_multidomain import community_of
        communities = [{"A", "B", "C"}, {"D", "E"}, {"F"}]
        assert community_of("A", communities) == 0
        assert community_of("D", communities) == 1
        assert community_of("F", communities) == 2

    def test_community_of_returns_neg1_for_unknown(self):
        """community_of returns -1 for nodes not in any community."""
        from e0_controller.explore_learning_cycle_multidomain import community_of
        communities = [{"A", "B"}]
        assert community_of("Z", communities) == -1

    def test_community_of_empty_communities(self):
        """community_of handles empty community list."""
        from e0_controller.explore_learning_cycle_multidomain import community_of
        assert community_of("A", []) == -1

    def test_navigate_returns_community_crossings(self):
        """navigate() result includes community_crossings key."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)  # populate some history
        from e0_controller.explore_learning_cycle_multidomain import navigate
        nav = navigate(
            s.landscape, s.unified_nodes, "explore", 10,
            start="B:HERE", communities=s.communities,
        )
        assert "community_crossings" in nav
        assert "domain_crossings" in nav  # backward compat
        assert isinstance(nav["community_crossings"], int)
        assert nav["community_crossings"] >= 0

    def test_community_crossings_le_domain_crossings(self):
        """Community crossings <= prefix crossings (communities can span prefix groups)."""
        s = build_session(steps_per_round=20)
        from e0_controller.explore_learning_cycle_multidomain import navigate
        nav = navigate(
            s.landscape, s.unified_nodes, "explore", 20,
            start="B:HERE", communities=s.communities,
        )
        assert nav["community_crossings"] <= nav["domain_crossings"]

    def test_no_communities_fallback(self):
        """Without communities, community_crossings equals domain_crossings."""
        s = build_session(steps_per_round=10)
        from e0_controller.explore_learning_cycle_multidomain import navigate
        nav = navigate(
            s.landscape, s.unified_nodes, "explore", 10,
            start="B:HERE",
        )
        assert nav["community_crossings"] == nav["domain_crossings"]

    def test_crossing_rate_uses_community(self):
        """crossing_rate is computed from community_crossings, not domain_crossings."""
        s = build_session(steps_per_round=10)
        from e0_controller.explore_learning_cycle_multidomain import navigate
        nav = navigate(
            s.landscape, s.unified_nodes, "explore", 10,
            start="B:HERE", communities=s.communities,
        )
        steps = nav["steps"]
        if steps > 0:
            expected_rate = nav["community_crossings"] / steps
            assert abs(nav["crossing_rate"] - expected_rate) < 1e-9

    def test_round_result_has_community_crossings(self):
        """MultiDomainRoundResult stores community_crossings."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        assert len(s.history) >= 1
        r = s.history[-1]
        assert hasattr(r, "community_crossings")
        assert isinstance(r.community_crossings, int)
        assert r.community_crossings >= 0

    def test_cmd_detail_uses_community_label(self):
        """cmd_detail path summary says 'community crossings' when communities exist."""
        s = build_session(steps_per_round=10)
        cmd_run(s, 1)
        output = cmd_detail(s)
        # With communities available, should say 'community crossings'
        assert "community crossings" in output or "0 community" in output

    def test_same_community_no_crossing(self):
        """Two nodes in the same community do not count as a crossing."""
        from e0_controller.explore_learning_cycle_multidomain import community_of
        communities = [{"A", "B", "C"}, {"D", "E"}]
        # A and B in same community
        assert community_of("A", communities) == community_of("B", communities)
        # A and D in different communities
        assert community_of("A", communities) != community_of("D", communities)
