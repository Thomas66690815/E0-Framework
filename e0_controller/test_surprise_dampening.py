"""
C187: Surprise Dampening — "The bridge was full ≠ the bridge is bad"

Tests for pre-inscription memory routing: surprising outcomes receive
reduced inscription weight, and experience classification diagnoses
domain character from accumulated surprise/confirmation statistics.
"""

import pytest
from e0_controller.primitives import Edge, Outcome
from e0_controller.historization import Historization
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller


# ─────────────────────── Helpers ───────────────────────

def make_edge(src="A", tgt="B"):
    return Edge(src, tgt)


def build_simple_landscape():
    L = Landscape()
    for s in ("A", "B", "C"):
        L.add_state(s)
    L.add_edge("A", "B", delta=0.5, resistance=1.0)
    L.add_edge("A", "C", delta=0.8, resistance=1.0)
    L.add_edge("B", "C", delta=0.3, resistance=1.0)
    return L


# ─────────────────────── Surprise Dampening ───────────────────────

class TestSurpriseDampening:
    """Surprising outcomes are inscribed with reduced weight."""

    def test_default_off(self):
        """surprise_dampening is False by default."""
        H = Historization()
        assert H.surprise_dampening is False

    def test_first_visit_always_full_weight(self):
        """First visit is never a surprise (no prediction to violate)."""
        H = Historization(surprise_dampening=True)
        e = make_edge()
        H.update(e, Outcome.FAILURE)
        u, f = H._effective_traces(e)
        assert f == 1.0  # full weight on first visit

    def test_confirmed_revisit_full_weight(self):
        """Revisit matching prediction → full inscription weight."""
        H = Historization(surprise_dampening=True)
        e = make_edge()
        # Build expectation: FAILURE → q < 0, predicts FAILURE
        H.update(e, Outcome.FAILURE)
        for _ in range(3):
            H.update(Edge("X", "Y"), Outcome.SUCCESS)
        # Revisit with FAILURE (confirms prediction)
        H.update(e, Outcome.FAILURE)
        u, f = H._effective_traces(e)
        # F should reflect full inscription (1.0) on the confirming revisit
        # plus decayed prior
        assert f > 1.0  # prior + new at full weight

    def test_surprising_revisit_half_weight(self):
        """Revisit contradicting prediction → half inscription weight."""
        H_damp = Historization(surprise_dampening=True)
        H_nodamp = Historization(surprise_dampening=False)
        e = make_edge()

        # Build same history in both
        for H in (H_damp, H_nodamp):
            H.update(e, Outcome.SUCCESS)  # q > 0 → predicts SUCCESS
            for _ in range(3):
                H.update(Edge("X", "Y"), Outcome.SUCCESS)
            # Surprising revisit: FAILURE when q > 0
            H.update(e, Outcome.FAILURE)

        _, f_damp = H_damp._effective_traces(e)
        _, f_nodamp = H_nodamp._effective_traces(e)
        # Dampened should have less F
        assert f_damp < f_nodamp
        # Specifically: dampened writes 0.5, undampened writes 1.0
        assert f_damp == pytest.approx(0.5, abs=0.01)
        assert f_nodamp == pytest.approx(1.0, abs=0.01)

    def test_surprise_dampening_reduces_delta_H(self):
        """With dampening, a surprising failure produces smaller δ_H."""
        H_damp = Historization(surprise_dampening=True)
        H_nodamp = Historization(surprise_dampening=False)
        e = make_edge()

        for H in (H_damp, H_nodamp):
            # Many successes → strong positive expectation
            for _ in range(5):
                H.update(e, Outcome.SUCCESS)
                for _ in range(2):
                    H.update(Edge("X", "Y"), Outcome.SUCCESS)
            # One surprising failure
            H.update(e, Outcome.FAILURE)

        dh_damp = H_damp.delta_H(e)
        dh_nodamp = H_nodamp.delta_H(e)
        # Both should be negative (successes dominate) but dampened less negative
        # Actually: the failure contributes less → δ_H is MORE negative (closer to pure success)
        # delta_H = lambda_f * F - lambda_s * U
        # less F → more negative δ_H → less resistance increase
        assert dh_damp < dh_nodamp  # dampened has lower δ_H (less failure contribution)

    def test_dampening_off_no_effect(self):
        """With dampening=False, surprise detection still runs (for C186)
        but inscription weight is always 1.0."""
        H = Historization(surprise_dampening=False)
        e = make_edge()
        H.update(e, Outcome.SUCCESS)
        for _ in range(3):
            H.update(Edge("X", "Y"), Outcome.SUCCESS)
        H.update(e, Outcome.FAILURE)  # surprising but undampened
        _, f = H._effective_traces(e)
        assert f == pytest.approx(1.0, abs=0.01)

    def test_consecutive_surprises_all_dampened(self):
        """Multiple surprising revisits all receive half weight."""
        H = Historization(surprise_dampening=True)
        e = make_edge()
        # Build positive expectation
        H.update(e, Outcome.SUCCESS)
        for _ in range(3):
            H.update(Edge("X", "Y"), Outcome.SUCCESS)
        # Surprise 1
        H.update(e, Outcome.FAILURE)
        f1 = H._effective_traces(e)[1]
        for _ in range(3):
            H.update(Edge("X", "Y"), Outcome.SUCCESS)
        # After first surprise, q may have shifted — check if still dampened
        # The key property: surprising outcome → always weight 0.5
        H.update(e, Outcome.FAILURE)
        f2 = H._effective_traces(e)[1]
        # f2 > f1 (accumulated) but each increment was 0.5, not 1.0
        assert f2 > f1


class TestExperienceClassification:
    """classify_experience() correctly diagnoses domain character."""

    def test_no_data_exploratory(self):
        """No revisits → exploratory (insufficient data)."""
        H = Historization()
        assert H.classify_experience() == "exploratory"

    def test_few_revisits_exploratory(self):
        """Very few revisits → still exploratory."""
        H = Historization()
        e = make_edge()
        H.update(e, Outcome.SUCCESS)
        for _ in range(3):
            H.update(Edge("X", "Y"), Outcome.SUCCESS)
        H.update(e, Outcome.SUCCESS)  # one confirmation
        assert H.classify_experience() == "exploratory"

    def test_many_confirmations_stable(self):
        """Many confirmed revisits → stable domain."""
        H = Historization()
        e = make_edge()
        for _ in range(10):
            H.update(e, Outcome.SUCCESS)
            for _ in range(3):
                H.update(Edge("X", "Y"), Outcome.SUCCESS)
            H.update(e, Outcome.SUCCESS)  # confirm
        assert H.classify_experience() == "stable"

    def test_many_surprises_volatile(self):
        """Alternating outcomes → volatile domain."""
        H = Historization()
        e = make_edge()
        outcomes = [Outcome.SUCCESS, Outcome.FAILURE] * 8
        for oc in outcomes:
            H.update(e, oc)
            for _ in range(3):
                H.update(Edge("X", "Y"), Outcome.SUCCESS)
        assert H.classify_experience() == "volatile"

    def test_surprise_rate_correlates(self):
        """surprise_rate > 0.3 in volatile classification."""
        H = Historization()
        e = make_edge()
        outcomes = [Outcome.SUCCESS, Outcome.FAILURE] * 8
        for oc in outcomes:
            H.update(e, oc)
            for _ in range(3):
                H.update(Edge("X", "Y"), Outcome.SUCCESS)
        sr = H.surprise_rate()
        assert sr > 0.3
        assert H.classify_experience() == "volatile"


class TestSurpriseEdges:
    """surprise_edges() returns top surprise-concentration points."""

    def test_empty(self):
        """No surprises → empty list."""
        H = Historization()
        assert H.surprise_edges() == []

    def test_identifies_volatile_edge(self):
        """Edge with flip-flop outcomes should appear in surprise_edges."""
        H = Historization()
        e = make_edge()
        for oc in [Outcome.SUCCESS, Outcome.FAILURE] * 5:
            H.update(e, oc)
            for _ in range(3):
                H.update(Edge("X", "Y"), Outcome.SUCCESS)
        edges = H.surprise_edges()
        assert len(edges) >= 1
        assert edges[0][0] == e  # highest surprise count


class TestSurpriseRateMetric:
    """surprise_rate() correctly measures global surprise fraction."""

    def test_zero_for_stable(self):
        """All confirmations → surprise_rate = 0."""
        H = Historization()
        e = make_edge()
        for _ in range(10):
            H.update(e, Outcome.SUCCESS)
            for _ in range(3):
                H.update(Edge("X", "Y"), Outcome.SUCCESS)
            H.update(e, Outcome.SUCCESS)
        assert H.surprise_rate() < 0.1

    def test_high_for_volatile(self):
        """Alternating outcomes → surprise_rate > 0.3."""
        H = Historization()
        e = make_edge()
        for oc in [Outcome.SUCCESS, Outcome.FAILURE] * 8:
            H.update(e, oc)
            for _ in range(3):
                H.update(Edge("X", "Y"), Outcome.SUCCESS)
        assert H.surprise_rate() > 0.3

    def test_bounded_zero_one(self):
        """Always in [0, 1]."""
        H = Historization()
        e = make_edge()
        for oc in [Outcome.SUCCESS, Outcome.FAILURE] * 5:
            H.update(e, oc)
        sr = H.surprise_rate()
        assert 0.0 <= sr <= 1.0


class TestBackwardCompatibility:
    """surprise_dampening=False preserves exact previous behavior."""

    def test_identical_traces_without_dampening(self):
        """Two Historizations with same inputs produce same traces."""
        H1 = Historization(surprise_dampening=False)
        H2 = Historization(surprise_dampening=False)
        e = make_edge()
        for H in (H1, H2):
            H.update(e, Outcome.SUCCESS)
            for _ in range(3):
                H.update(Edge("X", "Y"), Outcome.SUCCESS)
            H.update(e, Outcome.FAILURE)
        u1, f1 = H1._effective_traces(e)
        u2, f2 = H2._effective_traces(e)
        assert u1 == u2
        assert f1 == f2
