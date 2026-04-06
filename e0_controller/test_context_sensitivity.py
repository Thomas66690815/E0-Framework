"""
C176 — Context Sensitivity Tests

Tests for predecessor tracking in TraceRecord and context_sensitivity metric.
"""

import pytest

from e0_controller.controller import E0Controller
from e0_controller.historization import Historization, TraceRecord
from e0_controller.landscape import Landscape
from e0_controller.primitives import Edge, Outcome


# ── TraceRecord predecessor field ────────────────────────────────────

class TestTraceRecordPredecessor:
    """TraceRecord stores optional predecessor edge."""

    def test_default_none(self):
        rec = TraceRecord(tau=0, edge=Edge("A", "B"), outcome=Outcome.SUCCESS,
                          r_eff_before=1.0, r_eff_after=0.8)
        assert rec.predecessor is None

    def test_explicit_predecessor(self):
        pred = Edge("X", "A")
        rec = TraceRecord(tau=0, edge=Edge("A", "B"), outcome=Outcome.SUCCESS,
                          r_eff_before=1.0, r_eff_after=0.8,
                          predecessor=pred)
        assert rec.predecessor == pred
        assert rec.predecessor.source == "X"
        assert rec.predecessor.target == "A"


# ── context_quality ──────────────────────────────────────────────────

class TestContextQuality:
    """context_quality computes per-predecessor quality from audit log."""

    def _build_historization_with_log(self, events):
        """Helper: create Historization and populate log directly."""
        h = Historization()
        for edge, outcome, predecessor in events:
            h.update(edge, outcome)
            h.record(edge, outcome, 1.0, 1.0, predecessor=predecessor)
        return h

    def test_single_predecessor(self):
        e = Edge("B", "GOAL")
        pred = Edge("A", "B")
        h = self._build_historization_with_log([
            (e, Outcome.SUCCESS, pred),
            (e, Outcome.SUCCESS, pred),
        ])
        cq = h.context_quality(e)
        assert len(cq) == 1
        assert pred in cq
        q, count = cq[pred]
        assert q > 0.99  # all success → q ≈ +1.0
        assert count == 2.0

    def test_two_predecessors_diverging(self):
        """B→GOAL succeeds from A, fails from C."""
        e = Edge("B", "GOAL")
        pred_a = Edge("A", "B")
        pred_c = Edge("C", "B")
        h = self._build_historization_with_log([
            (e, Outcome.SUCCESS, pred_a),
            (e, Outcome.SUCCESS, pred_a),
            (e, Outcome.FAILURE, pred_c),
            (e, Outcome.FAILURE, pred_c),
        ])
        cq = h.context_quality(e)
        assert len(cq) == 2
        q_a, _ = cq[pred_a]
        q_c, _ = cq[pred_c]
        assert q_a > 0.99   # all success
        assert q_c < -0.99  # all failure

    def test_no_predecessor(self):
        """First step in a run has predecessor=None."""
        e = Edge("START", "A")
        h = self._build_historization_with_log([
            (e, Outcome.SUCCESS, None),
        ])
        cq = h.context_quality(e)
        assert None in cq
        q, count = cq[None]
        assert q > 0.99

    def test_empty_log(self):
        h = Historization()
        cq = h.context_quality(Edge("X", "Y"))
        assert cq == {}

    def test_mixed_outcomes_same_predecessor(self):
        e = Edge("A", "B")
        pred = Edge("START", "A")
        h = self._build_historization_with_log([
            (e, Outcome.SUCCESS, pred),
            (e, Outcome.FAILURE, pred),
        ])
        cq = h.context_quality(e)
        q, count = cq[pred]
        assert -0.1 < q < 0.1  # ~ 0 (balanced)
        assert count == 2.0


# ── context_sensitivity ─────────────────────────────────────────────

class TestContextSensitivity:
    """context_sensitivity measures quality variance across predecessors."""

    def _build_historization_with_log(self, events):
        h = Historization()
        for edge, outcome, predecessor in events:
            h.update(edge, outcome)
            h.record(edge, outcome, 1.0, 1.0, predecessor=predecessor)
        return h

    def test_single_predecessor_zero(self):
        """Only one predecessor → sensitivity = 0."""
        e = Edge("B", "GOAL")
        pred = Edge("A", "B")
        h = self._build_historization_with_log([
            (e, Outcome.SUCCESS, pred),
            (e, Outcome.SUCCESS, pred),
        ])
        assert h.context_sensitivity(e) == 0.0

    def test_identical_quality_zero(self):
        """Two predecessors, same quality → sensitivity = 0."""
        e = Edge("B", "GOAL")
        h = self._build_historization_with_log([
            (e, Outcome.SUCCESS, Edge("A", "B")),
            (e, Outcome.SUCCESS, Edge("C", "B")),
        ])
        assert h.context_sensitivity(e) == 0.0

    def test_maximum_divergence(self):
        """One predecessor all SUCCESS, another all FAILURE → sensitivity ≈ 2.0."""
        e = Edge("B", "GOAL")
        pred_a = Edge("A", "B")
        pred_c = Edge("C", "B")
        h = self._build_historization_with_log([
            (e, Outcome.SUCCESS, pred_a),
            (e, Outcome.SUCCESS, pred_a),
            (e, Outcome.FAILURE, pred_c),
            (e, Outcome.FAILURE, pred_c),
        ])
        cs = h.context_sensitivity(e)
        assert cs > 1.9  # close to 2.0

    def test_moderate_divergence(self):
        """Mixed → intermediate sensitivity."""
        e = Edge("B", "GOAL")
        pred_a = Edge("A", "B")
        pred_c = Edge("C", "B")
        h = self._build_historization_with_log([
            (e, Outcome.SUCCESS, pred_a),
            (e, Outcome.SUCCESS, pred_a),
            (e, Outcome.SUCCESS, pred_c),
            (e, Outcome.FAILURE, pred_c),
        ])
        cs = h.context_sensitivity(e)
        assert 0.3 < cs < 1.5

    def test_no_log_entries(self):
        h = Historization()
        assert h.context_sensitivity(Edge("X", "Y")) == 0.0

    def test_causal_domain_zero(self):
        """CAUSAL domain: B→GOAL works from both A and C → sensitivity ≈ 0."""
        e = Edge("B", "GOAL")
        h = self._build_historization_with_log([
            (e, Outcome.SUCCESS, Edge("A", "B")),
            (e, Outcome.SUCCESS, Edge("A", "B")),
            (e, Outcome.SUCCESS, Edge("C", "B")),
            (e, Outcome.SUCCESS, Edge("C", "B")),
        ])
        assert h.context_sensitivity(e) == 0.0

    def test_confounded_domain_high(self):
        """CONFOUNDED domain: B→GOAL works from A, fails from C → sensitivity ≈ 2."""
        e = Edge("B", "GOAL")
        h = self._build_historization_with_log([
            (e, Outcome.SUCCESS, Edge("A", "B")),
            (e, Outcome.SUCCESS, Edge("A", "B")),
            (e, Outcome.FAILURE, Edge("C", "B")),
            (e, Outcome.FAILURE, Edge("C", "B")),
        ])
        assert h.context_sensitivity(e) > 1.9


# ── Controller predecessor wiring ───────────────────────────────────

class TestControllerPredecessorTracking:
    """Controller.run() passes predecessor edges to historization.record()."""

    def _build_chain(self):
        """A→B→C chain."""
        L = Landscape()
        for s in ["A", "B", "C"]:
            L.add_state(s)
        L.add_edge("A", "B", delta=1.0, resistance=0.3)
        L.add_edge("B", "C", delta=1.0, resistance=0.3)
        return L

    def test_first_step_has_no_predecessor(self):
        L = self._build_chain()
        ctrl = E0Controller(L, lambda s, t: Outcome.SUCCESS)
        ctrl.run(start="A", goal="C", max_cycles=5)

        log = L.historization.log
        assert len(log) >= 2
        # First step A→B has no predecessor
        first = log[0]
        assert first.edge == Edge("A", "B")
        assert first.predecessor is None

    def test_second_step_has_predecessor(self):
        L = self._build_chain()
        ctrl = E0Controller(L, lambda s, t: Outcome.SUCCESS)
        ctrl.run(start="A", goal="C", max_cycles=5)

        log = L.historization.log
        # Second step B→C has predecessor A→B
        second = log[1]
        assert second.edge == Edge("B", "C")
        assert second.predecessor == Edge("A", "B")

    def test_separate_runs_reset_predecessor(self):
        """Each run starts with predecessor=None."""
        L = self._build_chain()
        ctrl = E0Controller(L, lambda s, t: Outcome.SUCCESS)
        ctrl.run(start="A", goal="C", max_cycles=5)
        ctrl.run(start="A", goal="C", max_cycles=5)

        log = L.historization.log
        # Run 2, first step should have predecessor=None
        run2_start = log[2]
        assert run2_start.edge == Edge("A", "B")
        assert run2_start.predecessor is None

    def test_context_sensitivity_via_controller(self):
        """End-to-end: controller run produces data for context_sensitivity."""
        L = Landscape()
        for s in ["START", "A", "B", "C", "GOAL"]:
            L.add_state(s)
        L.add_edge("START", "A", delta=1.0, resistance=0.3)
        L.add_edge("START", "C", delta=1.0, resistance=0.3)
        L.add_edge("A", "B", delta=1.0, resistance=0.3)
        L.add_edge("C", "B", delta=1.0, resistance=0.3)
        L.add_edge("B", "GOAL", delta=1.0, resistance=0.3)

        # B→GOAL always succeeds (causal)
        ctrl = E0Controller(L, lambda s, t: Outcome.SUCCESS)

        for _ in range(6):
            ctrl.run(start="START", goal="GOAL", max_cycles=10)

        # B→GOAL should have low context sensitivity (works from both A and C)
        cs = L.historization.context_sensitivity(Edge("B", "GOAL"))
        assert cs == 0.0
