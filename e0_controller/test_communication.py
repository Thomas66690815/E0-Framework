"""
Tests for E₀ Communication Intent (C159)
==========================================
Verify intent detection from Self-Graph, StepResult, and DreamObserver.
"""

import pytest
from dataclasses import dataclass, field
from typing import List, Optional

from e0_controller.primitives import Edge, Outcome
from e0_controller.controller import EscalationType
from e0_controller.self_graph import SelfGraph, CORE_COMPONENTS, MODULATION_COMPONENTS
from e0_controller.dual_reflection import diagnose_self_graph
from e0_controller.communication import (
    CommunicationIntent,
    IntentReport,
    IntentType,
    detect_dream_intents,
    detect_intents,
    detect_landscape_intents,
    detect_round_intents,
    detect_self_graph_intents,
    detect_status_intent,
    detect_step_intents,
)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _inject(sg: SelfGraph, outcome: Outcome, n: int = 10):
    """Inject n traces on all core components."""
    for _ in range(n):
        sg.self_historize(CORE_COMPONENTS, outcome)


@dataclass
class MockStepResult:
    """Minimal StepResult mock for intent detection."""
    tau: int = 1
    source: str = "A"
    target: str = "B"
    outcome: Outcome = Outcome.SUCCESS
    s_eff: float = 0.5
    r_eff_before: float = 1.0
    r_eff_after: float = 0.8
    candidates: List[str] = field(default_factory=lambda: ["B"])
    escalated: bool = False
    escalation_type: EscalationType = EscalationType.NONE


class MockDreamObserver:
    """Minimal DreamObserver mock returning configured equivalences."""

    def __init__(self, equivalences: Optional[List[dict]] = None):
        self._eqs = equivalences or []

    def equivalences_for(self, domain: str, **kwargs):
        return self._eqs


# ──────────────────────────────────────────────
# 1. CommunicationIntent Dataclass
# ──────────────────────────────────────────────

class TestCommunicationIntent:

    def test_basic_fields(self):
        i = CommunicationIntent(
            type=IntentType.UNCERTAINTY,
            urgency=0.7,
            subject="amplitude",
            summary="test",
        )
        assert i.type == IntentType.UNCERTAINTY
        assert i.urgency == 0.7
        assert i.subject == "amplitude"
        assert i.evidence == {}

    def test_with_evidence(self):
        i = CommunicationIntent(
            type=IntentType.DECISION,
            urgency=0.4,
            subject="A→B",
            summary="chose B",
            evidence={"key": "value"},
        )
        assert i.evidence["key"] == "value"

    def test_frozen(self):
        i = CommunicationIntent(
            type=IntentType.STATUS,
            urgency=0.1,
            subject="self_graph",
            summary="ok",
        )
        with pytest.raises(AttributeError):
            i.urgency = 0.9


# ──────────────────────────────────────────────
# 2. Self-Graph Intent Detection
# ──────────────────────────────────────────────

class TestSelfGraphIntents:

    def test_fresh_graph_all_request(self):
        sg = SelfGraph()
        intents = detect_self_graph_intents(sg)
        assert len(intents) > 0
        assert all(i.type == IntentType.REQUEST for i in intents)

    def test_healthy_graph_no_uncertainty(self):
        sg = SelfGraph()
        _inject(sg, Outcome.SUCCESS, n=15)
        intents = detect_self_graph_intents(sg)
        # Core components healthy, modulation may still lack data → REQUEST only
        assert all(
            i.type in (IntentType.REQUEST,) for i in intents
        )
        assert not any(i.type == IntentType.UNCERTAINTY for i in intents)

    def test_harmful_produces_uncertainty(self):
        sg = SelfGraph()
        _inject(sg, Outcome.FAILURE, n=15)
        intents = detect_self_graph_intents(sg)
        uncertainty = [i for i in intents if i.type == IntentType.UNCERTAINTY]
        assert len(uncertainty) > 0
        # Harmful = high urgency
        assert all(i.urgency >= 0.7 for i in uncertainty)

    def test_confused_produces_uncertainty(self):
        sg = SelfGraph()
        _inject(sg, Outcome.SUCCESS, n=15)
        _inject(sg, Outcome.FAILURE, n=15)
        intents = detect_self_graph_intents(sg)
        # Some should be confusion-type uncertainty
        uncertainty = [i for i in intents if i.type == IntentType.UNCERTAINTY]
        assert len(uncertainty) > 0

    def test_sorted_by_urgency(self):
        sg = SelfGraph()
        _inject(sg, Outcome.FAILURE, n=15)
        intents = detect_self_graph_intents(sg)
        for i in range(len(intents) - 1):
            assert intents[i].urgency >= intents[i + 1].urgency

    def test_evidence_contains_metrics(self):
        sg = SelfGraph()
        _inject(sg, Outcome.FAILURE, n=15)
        intents = detect_self_graph_intents(sg)
        for i in intents:
            if i.type == IntentType.UNCERTAINTY:
                assert "quality" in i.evidence
                assert "load" in i.evidence

    def test_pre_computed_diagnosis(self):
        sg = SelfGraph()
        _inject(sg, Outcome.FAILURE, n=15)
        diag = diagnose_self_graph(sg)
        intents = detect_self_graph_intents(sg, diagnosis=diag)
        assert len(intents) > 0


# ──────────────────────────────────────────────
# 3. Step Result Intent Detection
# ──────────────────────────────────────────────

class TestStepIntents:

    def test_single_candidate_no_decision(self):
        step = MockStepResult(candidates=["B"])
        intents = detect_step_intents(step)
        decision = [i for i in intents if i.type == IntentType.DECISION]
        assert len(decision) == 0

    def test_multiple_candidates_produces_decision(self):
        step = MockStepResult(candidates=["B", "C", "D"], target="B")
        intents = detect_step_intents(step)
        decision = [i for i in intents if i.type == IntentType.DECISION]
        assert len(decision) == 1
        assert "C" in decision[0].evidence["rejected"]
        assert "D" in decision[0].evidence["rejected"]

    def test_decision_urgency_scales_with_candidates(self):
        step2 = MockStepResult(candidates=["B", "C"], target="B")
        step5 = MockStepResult(candidates=["B", "C", "D", "E", "F"], target="B")
        intents2 = detect_step_intents(step2)
        intents5 = detect_step_intents(step5)
        d2 = [i for i in intents2 if i.type == IntentType.DECISION][0]
        d5 = [i for i in intents5 if i.type == IntentType.DECISION][0]
        assert d5.urgency > d2.urgency

    def test_escalation_produces_uncertainty(self):
        step = MockStepResult(
            escalated=True,
            escalation_type=EscalationType.DEAD_END,
        )
        intents = detect_step_intents(step)
        esc = [i for i in intents if i.type == IntentType.UNCERTAINTY]
        assert len(esc) == 1
        assert esc[0].urgency >= 0.7

    def test_exhausted_escalation_high_urgency(self):
        step = MockStepResult(
            escalated=True,
            escalation_type=EscalationType.EXHAUSTED,
        )
        intents = detect_step_intents(step)
        esc = [i for i in intents if i.type == IntentType.UNCERTAINTY]
        assert esc[0].urgency >= 0.7

    def test_filtered_escalation_moderate_urgency(self):
        step = MockStepResult(
            escalated=True,
            escalation_type=EscalationType.FILTERED,
        )
        intents = detect_step_intents(step)
        esc = [i for i in intents if i.type == IntentType.UNCERTAINTY]
        assert esc[0].urgency == 0.5

    def test_resistance_drop_produces_pattern(self):
        step = MockStepResult(r_eff_before=2.0, r_eff_after=1.0)
        intents = detect_step_intents(step)
        pattern = [i for i in intents if i.type == IntentType.PATTERN]
        assert len(pattern) == 1
        assert "stabilizing" in pattern[0].summary

    def test_small_resistance_drop_no_pattern(self):
        step = MockStepResult(r_eff_before=2.0, r_eff_after=1.8)
        intents = detect_step_intents(step)
        pattern = [i for i in intents if i.type == IntentType.PATTERN]
        assert len(pattern) == 0

    def test_no_escalation_no_uncertainty(self):
        step = MockStepResult(candidates=["B"])
        intents = detect_step_intents(step)
        assert all(i.type != IntentType.UNCERTAINTY for i in intents)


# ──────────────────────────────────────────────
# 4. Dream Intent Detection
# ──────────────────────────────────────────────

class TestDreamIntents:

    def test_no_equivalences_no_intents(self):
        obs = MockDreamObserver([])
        intents = detect_dream_intents(obs, "test")
        assert len(intents) == 0

    def test_negative_quality_produces_anomaly(self):
        obs = MockDreamObserver([{
            "own_state": "test:A→B",
            "partner_state": "other:X→Y",
            "trace_quality": -0.6,
            "trace_load": 5.0,
            "r_eff": 1.2,
        }])
        intents = detect_dream_intents(obs, "test")
        anomaly = [i for i in intents if i.type == IntentType.ANOMALY]
        assert len(anomaly) == 1

    def test_strong_positive_produces_pattern(self):
        obs = MockDreamObserver([{
            "own_state": "test:A→B",
            "partner_state": "other:X→Y",
            "trace_quality": 0.8,
            "trace_load": 10.0,
            "r_eff": 0.5,
        }])
        intents = detect_dream_intents(obs, "test")
        pattern = [i for i in intents if i.type == IntentType.PATTERN]
        assert len(pattern) == 1

    def test_middling_quality_no_intent(self):
        obs = MockDreamObserver([{
            "own_state": "test:A→B",
            "partner_state": "other:X→Y",
            "trace_quality": 0.2,
            "trace_load": 5.0,
            "r_eff": 1.0,
        }])
        intents = detect_dream_intents(obs, "test")
        assert len(intents) == 0

    def test_custom_anomaly_threshold(self):
        obs = MockDreamObserver([{
            "own_state": "test:A→B",
            "partner_state": "other:X→Y",
            "trace_quality": -0.1,
            "trace_load": 5.0,
            "r_eff": 1.0,
        }])
        # Default threshold -0.3 → not an anomaly
        assert len(detect_dream_intents(obs, "test")) == 0
        # Looser threshold -0.05 → anomaly
        assert len(detect_dream_intents(obs, "test", anomaly_threshold=-0.05)) == 1

    def test_anomaly_urgency_scales_with_quality(self):
        obs = MockDreamObserver([
            {"own_state": "t:A→B", "partner_state": "o:X→Y",
             "trace_quality": -0.4, "trace_load": 5.0, "r_eff": 1.0},
            {"own_state": "t:C→D", "partner_state": "o:W→Z",
             "trace_quality": -0.9, "trace_load": 5.0, "r_eff": 1.0},
        ])
        intents = detect_dream_intents(obs, "test")
        assert len(intents) == 2
        # More negative → higher urgency
        urgencies = sorted([i.urgency for i in intents], reverse=True)
        assert urgencies[0] > urgencies[1]


# ──────────────────────────────────────────────
# 5. Status Intent
# ──────────────────────────────────────────────

class TestStatusIntent:

    def test_fresh_graph_status(self):
        sg = SelfGraph()
        status = detect_status_intent(sg)
        assert status.type == IntentType.STATUS
        assert "insufficient data" in status.summary

    def test_healthy_graph_low_urgency(self):
        sg = SelfGraph()
        _inject(sg, Outcome.SUCCESS, n=15)
        status = detect_status_intent(sg)
        assert status.urgency <= 0.3

    def test_harmful_components_raise_urgency(self):
        sg = SelfGraph()
        _inject(sg, Outcome.FAILURE, n=15)
        status = detect_status_intent(sg)
        assert status.urgency >= 0.5

    def test_evidence_contains_lists(self):
        sg = SelfGraph()
        _inject(sg, Outcome.SUCCESS, n=15)
        status = detect_status_intent(sg)
        assert "healthy" in status.evidence
        assert isinstance(status.evidence["healthy"], list)


# ──────────────────────────────────────────────
# 6. IntentReport
# ──────────────────────────────────────────────

class TestIntentReport:

    def test_empty_report(self):
        r = IntentReport()
        assert r.count == 0
        assert r.max_urgency == 0.0
        assert "No communication" in r.summary()

    def test_by_type(self):
        r = IntentReport(intents=[
            CommunicationIntent(IntentType.UNCERTAINTY, 0.8, "x", "uncertain"),
            CommunicationIntent(IntentType.DECISION, 0.4, "y", "decided"),
            CommunicationIntent(IntentType.UNCERTAINTY, 0.6, "z", "confused"),
        ])
        assert len(r.by_type(IntentType.UNCERTAINTY)) == 2
        assert len(r.by_type(IntentType.DECISION)) == 1
        assert len(r.by_type(IntentType.STATUS)) == 0

    def test_above_urgency(self):
        r = IntentReport(intents=[
            CommunicationIntent(IntentType.UNCERTAINTY, 0.9, "a", "high"),
            CommunicationIntent(IntentType.DECISION, 0.3, "b", "low"),
        ])
        above = r.above_urgency(0.5)
        assert len(above) == 1
        assert above[0].urgency == 0.9

    def test_max_urgency(self):
        r = IntentReport(intents=[
            CommunicationIntent(IntentType.UNCERTAINTY, 0.3, "a", "low"),
            CommunicationIntent(IntentType.ANOMALY, 0.9, "b", "high"),
        ])
        assert r.max_urgency == 0.9

    def test_summary_format(self):
        r = IntentReport(intents=[
            CommunicationIntent(IntentType.UNCERTAINTY, 0.8, "x", "x"),
            CommunicationIntent(IntentType.DECISION, 0.4, "y", "y"),
        ])
        s = r.summary()
        assert "2 intents" in s
        assert "uncertainty" in s
        assert "decision" in s


# ──────────────────────────────────────────────
# 7. Unified detect_intents
# ──────────────────────────────────────────────

class TestDetectIntents:

    def test_self_graph_only(self):
        sg = SelfGraph()
        _inject(sg, Outcome.FAILURE, n=15)
        report = detect_intents(self_graph=sg)
        assert report.count > 0
        # Should include status
        assert len(report.by_type(IntentType.STATUS)) == 1

    def test_step_result_only(self):
        step = MockStepResult(candidates=["B", "C"], target="B")
        report = detect_intents(step_result=step)
        assert len(report.by_type(IntentType.DECISION)) == 1

    def test_dream_only(self):
        obs = MockDreamObserver([{
            "own_state": "d:A→B",
            "partner_state": "o:X→Y",
            "trace_quality": -0.7,
            "trace_load": 5.0,
            "r_eff": 1.0,
        }])
        report = detect_intents(dream_observer=obs, dream_domain="d")
        assert len(report.by_type(IntentType.ANOMALY)) == 1

    def test_all_sources_combined(self):
        sg = SelfGraph()
        _inject(sg, Outcome.FAILURE, n=15)
        step = MockStepResult(candidates=["B", "C"], target="B")
        obs = MockDreamObserver([{
            "own_state": "d:A→B",
            "partner_state": "o:X→Y",
            "trace_quality": -0.5,
            "trace_load": 5.0,
            "r_eff": 1.0,
        }])
        report = detect_intents(
            self_graph=sg,
            step_result=step,
            dream_observer=obs,
            dream_domain="d",
        )
        types = {i.type for i in report.intents}
        assert IntentType.UNCERTAINTY in types
        assert IntentType.DECISION in types
        assert IntentType.ANOMALY in types
        assert IntentType.STATUS in types

    def test_sorted_by_urgency(self):
        sg = SelfGraph()
        _inject(sg, Outcome.FAILURE, n=15)
        step = MockStepResult(candidates=["B", "C", "D"], target="B")
        report = detect_intents(self_graph=sg, step_result=step)
        for i in range(report.count - 1):
            assert report.intents[i].urgency >= report.intents[i + 1].urgency

    def test_no_status_when_disabled(self):
        sg = SelfGraph()
        report = detect_intents(self_graph=sg, include_status=False)
        assert len(report.by_type(IntentType.STATUS)) == 0

    def test_empty_when_no_sources(self):
        report = detect_intents()
        assert report.count == 0

    def test_dream_without_domain_ignored(self):
        obs = MockDreamObserver([{
            "own_state": "d:A→B",
            "partner_state": "o:X→Y",
            "trace_quality": -0.7,
            "trace_load": 5.0,
            "r_eff": 1.0,
        }])
        report = detect_intents(dream_observer=obs)
        assert report.count == 0


# ──────────────────────────────────────────────
# Landscape Intent Tests (C166)
# ──────────────────────────────────────────────

from e0_controller import Landscape
from e0_controller.controller import RunTrace, StepResult


def _make_task_landscape():
    """A→B→C→D linear landscape."""
    L = Landscape()
    L.add_edge("A", "B", delta=0.3, resistance=0.5)
    L.add_edge("B", "C", delta=0.5, resistance=1.0)
    L.add_edge("C", "D", delta=0.2, resistance=0.3)
    return L


def _make_trace(*steps_spec):
    """Build a RunTrace from (source, target, s_eff, outcome) tuples."""
    steps = []
    for i, (src, tgt, s_eff, outcome) in enumerate(steps_spec):
        steps.append(StepResult(
            tau=i, source=src, target=tgt,
            outcome=outcome, s_eff=s_eff,
            r_eff_before=1.0, r_eff_after=0.9,
            candidates=[tgt],
        ))
    return RunTrace(steps=steps)


class TestLandscapeIntents:
    """C166: Task-landscape-aware intent detection."""

    def test_task_status_intent_with_path(self):
        """Landscape intents include a STATUS with task overview."""
        L = _make_task_landscape()
        trace = _make_trace(
            ("A", "B", 0.15, Outcome.SUCCESS),
            ("B", "C", 0.50, Outcome.SUCCESS),
            ("C", "D", 0.06, Outcome.SUCCESS),
        )
        intents = detect_landscape_intents(
            L, trace=trace, goal="D",
            task_description="Test task",
        )
        status = [i for i in intents if i.subject == "task_landscape"]
        assert len(status) == 1
        s = status[0]
        assert s.type == IntentType.STATUS
        assert "Goal REACHED" in s.summary
        assert "A → B → C → D" in s.summary
        assert s.evidence["goal_reached"] is True
        assert s.evidence["path"] == ["A", "B", "C", "D"]
        assert s.evidence["states"] == ["A", "B", "C", "D"]
        assert s.evidence["edge_count"] == 3

    def test_task_status_goal_pending(self):
        """When goal is not reached, status says 'pending'."""
        L = _make_task_landscape()
        trace = _make_trace(
            ("A", "B", 0.15, Outcome.SUCCESS),
        )
        intents = detect_landscape_intents(L, trace=trace, goal="D")
        status = [i for i in intents if i.subject == "task_landscape"][0]
        assert "Goal pending" in status.summary
        assert status.evidence["goal_reached"] is False

    def test_high_tension_edge_produces_decision(self):
        """Steps with S_eff > 0.5 produce DECISION intents."""
        L = _make_task_landscape()
        trace = _make_trace(
            ("A", "B", 0.15, Outcome.SUCCESS),
            ("B", "C", 0.80, Outcome.SUCCESS),
        )
        intents = detect_landscape_intents(L, trace=trace, goal="D")
        decisions = [i for i in intents if i.type == IntentType.DECISION]
        assert len(decisions) == 1
        d = decisions[0]
        assert d.subject == "B→C"
        assert "High tension" in d.summary
        assert d.evidence["s_eff"] == 0.80

    def test_low_tension_no_decision(self):
        """Steps with S_eff <= 0.5 don't produce DECISION intents."""
        L = _make_task_landscape()
        trace = _make_trace(
            ("A", "B", 0.15, Outcome.SUCCESS),
            ("B", "C", 0.30, Outcome.SUCCESS),
        )
        intents = detect_landscape_intents(L, trace=trace, goal="D")
        decisions = [i for i in intents if i.type == IntentType.DECISION]
        assert len(decisions) == 0

    def test_negative_quality_produces_uncertainty(self):
        """Edges with negative quality + sufficient load → UNCERTAINTY."""
        L = _make_task_landscape()
        edge = Edge("A", "B")
        for _ in range(5):
            L.historization.update(edge, Outcome.FAILURE)
        trace = _make_trace(
            ("A", "B", 0.20, Outcome.FAILURE),
        )
        intents = detect_landscape_intents(L, trace=trace, goal="D")
        uncertainties = [i for i in intents
                         if i.type == IntentType.UNCERTAINTY]
        assert len(uncertainties) >= 1
        u = uncertainties[0]
        assert "Struggling" in u.summary
        assert u.evidence["quality"] < 0

    def test_stabilizing_edge_produces_pattern(self):
        """Edges with positive quality + high load → PATTERN."""
        L = _make_task_landscape()
        edge = Edge("A", "B")
        for _ in range(10):
            L.historization.update(edge, Outcome.SUCCESS)
        trace = _make_trace(
            ("A", "B", 0.15, Outcome.SUCCESS),
        )
        intents = detect_landscape_intents(L, trace=trace, goal="D")
        patterns = [i for i in intents if i.type == IntentType.PATTERN]
        assert len(patterns) >= 1
        p = patterns[0]
        assert "stable" in p.summary
        assert p.evidence["quality"] > 0

    def test_dead_end_produces_request(self):
        """When current state has no admissible neighbors → REQUEST."""
        L = Landscape()
        L.add_edge("A", "B", delta=0.3, resistance=0.5)
        trace = _make_trace(
            ("A", "B", 0.15, Outcome.SUCCESS),
        )
        intents = detect_landscape_intents(L, trace=trace, goal="C")
        requests = [i for i in intents if i.type == IntentType.REQUEST]
        assert len(requests) == 1
        r = requests[0]
        assert r.subject == "B"
        assert "Dead end" in r.summary
        assert r.urgency >= 0.8

    def test_no_dead_end_when_goal_reached(self):
        """No REQUEST when goal is reached even if no outgoing edges."""
        L = Landscape()
        L.add_edge("A", "B", delta=0.3, resistance=0.5)
        trace = _make_trace(
            ("A", "B", 0.15, Outcome.SUCCESS),
        )
        intents = detect_landscape_intents(L, trace=trace, goal="B")
        requests = [i for i in intents if i.type == IntentType.REQUEST]
        assert len(requests) == 0

    def test_empty_trace_gives_status_only(self):
        """Without trace, only status intent is produced."""
        L = _make_task_landscape()
        intents = detect_landscape_intents(L, goal="D")
        assert len(intents) == 1
        assert intents[0].type == IntentType.STATUS
        assert intents[0].evidence["path"] == []

    def test_evidence_includes_task_description(self):
        """Task description flows into evidence."""
        L = _make_task_landscape()
        trace = _make_trace(("A", "B", 0.15, Outcome.SUCCESS))
        intents = detect_landscape_intents(
            L, trace=trace, task_description="Build a spaceship",
        )
        status = [i for i in intents if i.subject == "task_landscape"][0]
        assert status.evidence["task"] == "Build a spaceship"
        assert "Build a spaceship" in status.summary


class TestUnifiedWithLandscape:
    """detect_intents() passes landscape data through."""

    def test_landscape_intents_in_unified_report(self):
        """Landscape intents appear in the unified report."""
        L = _make_task_landscape()
        trace = _make_trace(
            ("A", "B", 0.15, Outcome.SUCCESS),
            ("B", "C", 0.80, Outcome.SUCCESS),
            ("C", "D", 0.06, Outcome.SUCCESS),
        )
        report = detect_intents(
            landscape=L, trace=trace, goal="D",
            task_description="Test unified",
        )
        # Should have task status + high-tension decision
        types = [i.type for i in report.intents]
        assert IntentType.STATUS in types
        assert IntentType.DECISION in types

    def test_landscape_and_selfgraph_combined(self):
        """Landscape and self-graph intents can coexist."""
        L = _make_task_landscape()
        trace = _make_trace(("A", "B", 0.15, Outcome.SUCCESS))
        sg = SelfGraph()
        report = detect_intents(
            self_graph=sg,
            landscape=L,
            trace=trace,
            goal="D",
            include_status=True,
        )
        # Should have both self-graph status and task status
        status_intents = report.by_type(IntentType.STATUS)
        subjects = {s.subject for s in status_intents}
        assert "self_graph" in subjects
        assert "task_landscape" in subjects


# ──────────────────────────────────────────────
# Round Intents (C212)
# ──────────────────────────────────────────────


def _round_kwargs(**overrides):
    """Default kwargs for detect_round_intents."""
    defaults = dict(
        round_num=3,
        mode="explore",
        reason="Frontier of 20 unvisited nodes",
        steps=40,
        coverage_before=0.4,
        coverage_after=0.55,
        coverage_delta=0.15,
        T_s_before=0.3,
        T_s_after=0.25,
        domain_crossings=12,
        crossing_rate=0.3,
        canon_coverage=0.6,
        bootstrap_coverage=0.7,
        en_coverage=0.4,
        new_edges=3,
        total_nodes=148,
        visited_nodes=81,
    )
    defaults.update(overrides)
    return defaults


class TestRoundIntents:
    """detect_round_intents produces well-structured IntentReport."""

    def test_returns_intent_report(self):
        report = detect_round_intents(**_round_kwargs())
        assert isinstance(report, IntentReport)
        assert report.count >= 3  # decision + coverage + balance at minimum

    def test_has_decision_intent(self):
        report = detect_round_intents(**_round_kwargs())
        decisions = report.by_type(IntentType.DECISION)
        assert len(decisions) >= 1
        assert "explore" in decisions[0].summary

    def test_has_coverage_pattern(self):
        report = detect_round_intents(**_round_kwargs())
        patterns = report.by_type(IntentType.PATTERN)
        cov = [p for p in patterns if p.subject == "coverage"]
        assert len(cov) == 1
        assert "40.0%" in cov[0].summary or "55.0%" in cov[0].summary

    def test_coverage_evidence_has_drop_pct(self):
        report = detect_round_intents(**_round_kwargs())
        patterns = report.by_type(IntentType.PATTERN)
        cov = [p for p in patterns if p.subject == "coverage"][0]
        assert "r_eff_before" in cov.evidence
        assert "r_eff_after" in cov.evidence
        assert "drop_pct" in cov.evidence
        # 40% → 55%: r_eff = 0.6 → 0.45, drop_pct ≈ 0.25
        assert 0.2 < cov.evidence["drop_pct"] < 0.3

    def test_has_domain_balance_status(self):
        report = detect_round_intents(**_round_kwargs())
        statuses = report.by_type(IntentType.STATUS)
        balance = [s for s in statuses if s.subject == "domain_balance"]
        assert len(balance) == 1
        assert "Canon" in balance[0].summary

    def test_domain_imbalance_higher_urgency(self):
        # EN far behind → higher urgency
        report = detect_round_intents(**_round_kwargs(
            canon_coverage=0.9, bootstrap_coverage=0.8, en_coverage=0.2,
        ))
        balance = [s for s in report.by_type(IntentType.STATUS)
                   if s.subject == "domain_balance"][0]
        assert balance.urgency > 0.5
        assert "lagging" in balance.summary

    def test_has_crossing_pattern(self):
        report = detect_round_intents(**_round_kwargs())
        patterns = report.by_type(IntentType.PATTERN)
        xing = [p for p in patterns if p.subject == "domain_crossings"]
        assert len(xing) == 1
        assert "12 domain crossings" in xing[0].summary

    def test_high_T_s_produces_uncertainty(self):
        report = detect_round_intents(**_round_kwargs(
            T_s_before=0.8, T_s_after=1.2,
        ))
        uncerts = report.by_type(IntentType.UNCERTAINTY)
        assert len(uncerts) >= 1
        assert "T_s" in uncerts[0].summary

    def test_low_T_s_no_uncertainty(self):
        report = detect_round_intents(**_round_kwargs(
            T_s_before=0.1, T_s_after=0.15,
        ))
        uncerts = report.by_type(IntentType.UNCERTAINTY)
        assert len(uncerts) == 0

    def test_stagnation_produces_request(self):
        report = detect_round_intents(**_round_kwargs(
            stagnation_count=3,
            coverage_delta=0.0,
        ))
        requests = report.by_type(IntentType.REQUEST)
        assert len(requests) == 1
        assert "Stagnation" in requests[0].summary

    def test_no_stagnation_no_request(self):
        report = detect_round_intents(**_round_kwargs(stagnation_count=0))
        requests = report.by_type(IntentType.REQUEST)
        assert len(requests) == 0

    def test_many_new_edges_produces_anomaly(self):
        report = detect_round_intents(**_round_kwargs(new_edges=10))
        anomalies = report.by_type(IntentType.ANOMALY)
        assert len(anomalies) == 1
        assert "10 new shortcut" in anomalies[0].summary

    def test_few_new_edges_no_anomaly(self):
        report = detect_round_intents(**_round_kwargs(new_edges=2))
        anomalies = report.by_type(IntentType.ANOMALY)
        assert len(anomalies) == 0

    def test_sorted_by_urgency_descending(self):
        report = detect_round_intents(**_round_kwargs())
        urgencies = [i.urgency for i in report.intents]
        assert urgencies == sorted(urgencies, reverse=True)

    def test_zero_steps_no_crossing_pattern(self):
        report = detect_round_intents(**_round_kwargs(steps=0))
        patterns = report.by_type(IntentType.PATTERN)
        xing = [p for p in patterns if p.subject == "domain_crossings"]
        assert len(xing) == 0

    def test_full_coverage_goal_reached(self):
        report = detect_round_intents(**_round_kwargs(
            coverage_after=0.95,
        ))
        statuses = report.by_type(IntentType.STATUS)
        balance = [s for s in statuses if s.subject == "domain_balance"][0]
        assert balance.evidence["goal_reached"] is True
