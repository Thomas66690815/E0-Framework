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
