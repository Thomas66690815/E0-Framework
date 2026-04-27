"""Tests for C277/C278: Trajectory-level historization and experience classification.

Claims validated:
  1. PathSignature is a compressed community-index tuple (domain-invariant)
  2. TrajectoryHistorization accumulates U/F correctly (same formula as Historization)
  3. plan() reacts to low-quality trajectory signals (non-Markov behavior)
  4. C278: trajectory_surprise_rate() and classify_trajectory_experience() mirror
     the edge-level C186/C188 mechanism for self-calibrating experience awareness
"""

from __future__ import annotations

from typing import List, Set

import pytest

from e0_controller.trajectory import (
    PathSignature,
    TrajectoryHistorization,
    TrajectoryRecord,
    compute_path_signature,
)
from e0_controller.explore_learning_cycle_multidomain import (
    MultiDomainAssessment,
    MultiDomainRoundResult,
    plan,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_assessment(
    coverage: float = 0.5,
    frontier_size: int = 10,
    T_s: float = 0.5,
    canon_coverage: float = 0.5,
    bootstrap_coverage: float = 0.5,
    en_coverage: float = 0.5,
    en_nodes: int = 0,
) -> MultiDomainAssessment:
    return MultiDomainAssessment(
        total_nodes=100,
        total_edges=200,
        visited_nodes=int(coverage * 100),
        coverage=coverage,
        frontier_size=frontier_size,
        T_s=T_s,
        mean_quality=0.6,
        stale_edges=0,
        canon_coverage=canon_coverage,
        bootstrap_coverage=bootstrap_coverage,
        en_coverage=en_coverage,
        canon_nodes=40,
        bootstrap_nodes=40,
        en_nodes=en_nodes,
        canon_visited=int(canon_coverage * 40),
        bootstrap_visited=int(bootstrap_coverage * 40),
        en_visited=int(en_coverage * max(1, en_nodes)),
    )


def _make_round_result(
    round_num: int = 1,
    coverage_delta: float = 0.05,
    trajectory: "TrajectoryRecord | None" = None,
) -> MultiDomainRoundResult:
    a = _make_assessment()
    return MultiDomainRoundResult(
        round_num=round_num,
        mode="explore",
        reason="test",
        steps=20,
        assessment_before=a,
        assessment_after=a,
        path=[],
        new_edges=0,
        domain_crossings=0,
        crossing_rate=0.0,
        coverage_delta=coverage_delta,
        T_s_delta=0.0,
        en_canon_crossings=0,
        en_bootstrap_crossings=0,
        canon_bootstrap_crossings=0,
        trajectory=trajectory,
    )


# ---------------------------------------------------------------------------
# TestPathSignature
# ---------------------------------------------------------------------------


class TestPathSignature:
    """compute_path_signature converts node-ID paths to community tuples."""

    def test_single_community_no_crossings(self):
        communities: List[Set[str]] = [{"A", "B", "C"}]
        path = ["A", "B", "C", "B"]
        sig = compute_path_signature(path, communities)
        # All in community 0 → compressed to (0,)
        assert sig == (0,)

    def test_two_communities_one_crossing(self):
        communities = [{"A", "B"}, {"X", "Y"}]
        path = ["A", "B", "X", "Y"]
        sig = compute_path_signature(path, communities)
        # 0 → 0 → 1 → 1, compressed: (0, 1)
        assert sig == (0, 1)

    def test_round_trip_crossing(self):
        communities = [{"C:omega", "C:zeta"}, {"B:HERE", "B:L4"}]
        path = ["C:omega", "C:zeta", "B:HERE", "B:L4", "C:omega"]
        sig = compute_path_signature(path, communities)
        # 0 0 1 1 0, compressed: (0, 1, 0)
        assert sig == (0, 1, 0)

    def test_unknown_nodes_map_to_minus_one(self):
        communities = [{"A"}]
        path = ["A", "UNKNOWN", "A"]
        sig = compute_path_signature(path, communities)
        # 0 -1 0, compressed: (0, -1, 0)
        assert sig == (0, -1, 0)

    def test_empty_path_returns_empty_tuple(self):
        communities = [{"A", "B"}]
        sig = compute_path_signature([], communities)
        assert sig == ()

    def test_empty_communities_returns_empty_tuple(self):
        sig = compute_path_signature(["A", "B", "C"], [])
        assert sig == ()

    def test_signature_is_domain_invariant(self):
        """Same crossing pattern → same signature regardless of node names."""
        communities_1 = [{"C:alpha", "C:beta"}, {"B:x", "B:y"}]
        communities_2 = [{"EN:word", "EN:verb"}, {"M:engine", "M:greedy"}]
        path_1 = ["C:alpha", "B:x", "C:beta"]
        path_2 = ["EN:word", "M:engine", "EN:verb"]
        sig_1 = compute_path_signature(path_1, communities_1)
        sig_2 = compute_path_signature(path_2, communities_2)
        # Both: 0 → 1 → 0
        assert sig_1 == sig_2 == (0, 1, 0)

    def test_consecutive_deduplication(self):
        """Staying in the same community for many steps compresses to one entry."""
        communities = [{"A", "B", "C"}, {"X"}]
        path = ["A", "A", "B", "C", "X", "X"]
        sig = compute_path_signature(path, communities)
        assert sig == (0, 1)


# ---------------------------------------------------------------------------
# TestTrajectoryHistorization
# ---------------------------------------------------------------------------


class TestTrajectoryHistorization:
    """U/F traces accumulate on PathSignatures; quality formula matches Historization."""

    def test_fresh_hist_load_zero(self):
        th = TrajectoryHistorization()
        assert th.trace_load((0, 1)) == 0

    def test_fresh_hist_quality_zero(self):
        th = TrajectoryHistorization()
        # No evidence → (0-0)/(0+0+1) = 0.0
        assert th.trace_quality((0, 1)) == pytest.approx(0.0)

    def test_inscribe_productive_increments_u(self):
        th = TrajectoryHistorization()
        rec = TrajectoryRecord(signature=(0, 1), mode="explore",
                               coverage_delta=0.05, community_crossings=2)
        assert rec.outcome == "productive"
        th.inscribe(rec)
        assert th.trace_load((0, 1)) == 1
        # quality = (1-0)/(1+0+1) = 0.5
        assert th.trace_quality((0, 1)) == pytest.approx(0.5)

    def test_inscribe_stagnant_increments_f(self):
        th = TrajectoryHistorization()
        rec = TrajectoryRecord(signature=(0,), mode="explore",
                               coverage_delta=0.0, community_crossings=0)
        assert rec.outcome == "stagnant"
        th.inscribe(rec)
        assert th.trace_load((0,)) == 1
        # quality = (0-1)/(0+1+1) = -0.5
        assert th.trace_quality((0,)) == pytest.approx(-0.5)

    def test_inscribe_improving(self):
        th = TrajectoryHistorization()
        rec = TrajectoryRecord(signature=(0, 1, 0), mode="explore",
                               coverage_delta=0.005, community_crossings=2)
        assert rec.outcome == "improving"
        th.inscribe(rec)
        # improving counts as U
        assert th.trace_quality((0, 1, 0)) == pytest.approx(0.5)

    def test_quality_converges_to_negative_with_repeated_stagnation(self):
        th = TrajectoryHistorization()
        sig = (0,)
        for _ in range(5):
            th.inscribe(TrajectoryRecord(sig, "explore", 0.0, 0))
        q = th.trace_quality(sig)
        # (0-5)/(0+5+1) = -5/6 ≈ -0.833
        assert q == pytest.approx(-5 / 6)

    def test_quality_formula_matches_historization(self):
        """(U - F) / (U + F + 1) — same as E₀ Historization."""
        th = TrajectoryHistorization()
        sig = (0, 1)
        # 3 productive, 1 stagnant
        for _ in range(3):
            th.inscribe(TrajectoryRecord(sig, "explore", 0.05, 2))
        th.inscribe(TrajectoryRecord(sig, "explore", 0.0, 0))
        assert th.trace_load(sig) == 4
        # (3-1)/(3+1+1) = 2/5 = 0.4
        assert th.trace_quality(sig) == pytest.approx(2 / 5)

    def test_known_signatures_grows(self):
        th = TrajectoryHistorization()
        assert th.known_signatures() == []
        th.inscribe(TrajectoryRecord((0,), "explore", 0.05, 0))
        th.inscribe(TrajectoryRecord((0, 1), "explore", 0.0, 1))
        assert set(th.known_signatures()) == {(0,), (0, 1)}

    def test_low_quality_warning_triggers(self):
        th = TrajectoryHistorization()
        sig = (0,)
        # 3 stagnant observations
        for _ in range(3):
            th.inscribe(TrajectoryRecord(sig, "explore", 0.0, 0))
        # quality = -3/4 = -0.75 < -0.3, load = 3 >= 2 → True
        assert th.low_quality_warning(sig) is True

    def test_low_quality_warning_suppressed_by_min_load(self):
        th = TrajectoryHistorization()
        sig = (0,)
        # Only 1 stagnant → load = 1 < min_load = 2
        th.inscribe(TrajectoryRecord(sig, "explore", 0.0, 0))
        assert th.low_quality_warning(sig) is False

    def test_low_quality_warning_not_triggered_for_good_signature(self):
        th = TrajectoryHistorization()
        sig = (0, 1)
        for _ in range(3):
            th.inscribe(TrajectoryRecord(sig, "explore", 0.05, 2))
        # quality = (3-0)/(3+0+1) = 0.75 > -0.3 → False
        assert th.low_quality_warning(sig) is False

    def test_different_signatures_independent(self):
        th = TrajectoryHistorization()
        sig_a = (0, 1)
        sig_b = (0,)
        for _ in range(3):
            th.inscribe(TrajectoryRecord(sig_a, "explore", 0.05, 2))
        th.inscribe(TrajectoryRecord(sig_b, "explore", 0.0, 0))
        assert th.trace_load(sig_a) == 3
        assert th.trace_load(sig_b) == 1


# ---------------------------------------------------------------------------
# TestTrajectoryOutcome
# ---------------------------------------------------------------------------


class TestTrajectoryOutcome:
    """TrajectoryRecord.outcome is derived correctly from coverage_delta."""

    def test_productive(self):
        r = TrajectoryRecord((0,), "explore", 0.02, 1)
        assert r.outcome == "productive"

    def test_productive_boundary(self):
        r = TrajectoryRecord((0,), "explore", 0.01, 0)
        assert r.outcome == "productive"

    def test_improving(self):
        r = TrajectoryRecord((0,), "explore", 0.005, 0)
        assert r.outcome == "improving"

    def test_improving_boundary(self):
        r = TrajectoryRecord((0,), "explore", 0.001, 0)
        assert r.outcome == "improving"

    def test_stagnant(self):
        r = TrajectoryRecord((0,), "explore", 0.0, 0)
        assert r.outcome == "stagnant"

    def test_stagnant_near_zero(self):
        r = TrajectoryRecord((0,), "explore", 0.0009, 0)
        assert r.outcome == "stagnant"


# ---------------------------------------------------------------------------
# TestPlanWithTrajectory
# ---------------------------------------------------------------------------


class TestPlanWithTrajectory:
    """plan() uses trajectory_hist for proactive mode switching (C277 non-Markov)."""

    def _make_stagnant_hist(self, sig: PathSignature, n: int = 3) -> TrajectoryHistorization:
        th = TrajectoryHistorization()
        for _ in range(n):
            th.inscribe(TrajectoryRecord(sig, "explore", 0.0, 0))
        return th

    def test_no_trajectory_hist_behaves_as_before(self):
        """Without trajectory_hist, plan() is unchanged."""
        a = _make_assessment(coverage=0.3, frontier_size=5)
        mode, steps, reason = plan(a, 1, [], trajectory_hist=None)
        assert mode == "explore"

    def test_low_quality_signature_triggers_escalation(self):
        """plan() doubles steps when last signature is historically stagnant."""
        sig = (0,)
        th = self._make_stagnant_hist(sig, n=3)
        # Last round had this stagnant signature
        last_round = _make_round_result(
            coverage_delta=0.0,
            trajectory=TrajectoryRecord(sig, "explore", 0.0, 0),
        )
        a = _make_assessment(coverage=0.4, frontier_size=8)
        mode, steps, reason = plan(a, 2, [last_round], max_steps=30,
                                   trajectory_hist=th)
        # Should escalate: 2× base_steps = 60
        assert steps == 60
        assert "trajectory" in reason.lower() or "stagnant" in reason.lower()

    def test_good_signature_does_not_trigger_escalation(self):
        """plan() does NOT escalate when trajectory quality is positive."""
        sig = (0, 1)
        th = TrajectoryHistorization()
        for _ in range(3):
            th.inscribe(TrajectoryRecord(sig, "explore", 0.05, 2))
        last_round = _make_round_result(
            coverage_delta=0.05,
            trajectory=TrajectoryRecord(sig, "explore", 0.05, 2),
        )
        a = _make_assessment(coverage=0.4, frontier_size=8)
        mode, steps, reason = plan(a, 2, [last_round], max_steps=30,
                                   trajectory_hist=th)
        # No escalation — steps should be standard or stagnation-based
        assert steps < 60

    def test_no_trajectory_on_last_round_does_not_crash(self):
        """plan() handles last round with trajectory=None gracefully."""
        sig = (0,)
        th = self._make_stagnant_hist(sig, n=3)
        # Last round has no trajectory attached
        last_round = _make_round_result(coverage_delta=0.0, trajectory=None)
        a = _make_assessment(coverage=0.4, frontier_size=8)
        mode, steps, reason = plan(a, 2, [last_round], max_steps=30,
                                   trajectory_hist=th)
        # No crash — behaves normally
        assert isinstance(mode, str)

    def test_insufficient_load_does_not_trigger(self):
        """With only 1 observation, low_quality_warning suppresses the signal."""
        sig = (0,)
        th = TrajectoryHistorization()
        # Only 1 stagnant → load=1 < min_load=2
        th.inscribe(TrajectoryRecord(sig, "explore", 0.0, 0))
        last_round = _make_round_result(
            coverage_delta=0.0,
            trajectory=TrajectoryRecord(sig, "explore", 0.0, 0),
        )
        a = _make_assessment(coverage=0.4, frontier_size=8)
        mode, steps, reason = plan(a, 2, [last_round], max_steps=30,
                                   trajectory_hist=th)
        # No escalation — steps should be ≤ 45 (stagnation recovery max)
        assert steps <= 45


# ---------------------------------------------------------------------------
# TestTrajectoryExperience (C278)
# ---------------------------------------------------------------------------


class TestTrajectoryExperience:
    """C278: trajectory_surprise_rate() and classify_trajectory_experience().

    Mirrors TestAdaptiveObservation at edge level (test_adaptive_observation.py).
    Structural claim: trajectory-level experience classification uses the same
    three-state vocabulary (stable / volatile / exploratory) as edge-level,
    and the surprise_rate formula is identical in structure.
    """

    # --- trajectory_surprise_rate ---

    def test_surprise_rate_zero_with_no_data(self):
        """Fresh TrajectoryHistorization has no revisit events → rate = 0.0."""
        th = TrajectoryHistorization()
        assert th.trajectory_surprise_rate() == pytest.approx(0.0)

    def test_first_inscription_not_tracked(self):
        """First inscription of a signature has no prior → no conf/surp event."""
        th = TrajectoryHistorization()
        th.inscribe(TrajectoryRecord((0,), "explore", 0.0, 0))
        # No revisit data yet — rate stays 0.0
        assert th.trajectory_surprise_rate() == pytest.approx(0.0)

    def test_confirmation_when_quality_positive_and_productive(self):
        """quality > 0 → predict productive → actual productive → confirmation."""
        th = TrajectoryHistorization()
        sig = (0, 1)
        # First inscription: U=1, F=0 → quality = 0.5 → predicts productive
        th.inscribe(TrajectoryRecord(sig, "explore", 0.05, 2))
        # Second inscription: same signature, actual productive → confirmation
        th.inscribe(TrajectoryRecord(sig, "explore", 0.05, 2))
        assert th.trajectory_surprise_rate() == pytest.approx(0.0)  # all confirmations

    def test_surprise_when_quality_positive_but_stagnant(self):
        """quality > 0 → predict productive → actual stagnant → surprise."""
        th = TrajectoryHistorization()
        sig = (0, 1)
        # First inscription: productive → quality = 0.5
        th.inscribe(TrajectoryRecord(sig, "explore", 0.05, 2))
        # Second inscription: stagnant → contradicts prediction → surprise
        th.inscribe(TrajectoryRecord(sig, "explore", 0.0, 0))
        assert th.trajectory_surprise_rate() == pytest.approx(1.0)  # 1 surp / 1 total

    def test_surprise_when_quality_negative_but_productive(self):
        """quality < 0 → predict stagnant → actual productive → surprise."""
        th = TrajectoryHistorization()
        sig = (0,)
        # First: stagnant → load=1, no revisit event yet.  quality = -0.5
        th.inscribe(TrajectoryRecord(sig, "explore", 0.0, 0))
        # Second: productive → quality = -0.5 < 0 → predict stagnant
        # → actual productive → contradiction → surprise (1 surp, 0 conf)
        th.inscribe(TrajectoryRecord(sig, "explore", 0.05, 1))
        assert th.trajectory_surprise_rate() == pytest.approx(1.0)

    def test_confirmation_when_quality_negative_and_stagnant(self):
        """quality < 0 → predict stagnant → actual stagnant → confirmation."""
        th = TrajectoryHistorization()
        sig = (0,)
        th.inscribe(TrajectoryRecord(sig, "explore", 0.0, 0))  # load=1
        th.inscribe(TrajectoryRecord(sig, "explore", 0.0, 0))  # revisit → conf
        assert th.trajectory_surprise_rate() == pytest.approx(0.0)

    def test_surprise_rate_formula_mixed(self):
        """2 confirmations, 1 surprise → rate = 1/3."""
        th = TrajectoryHistorization()
        sig = (0, 1)
        # First inscription: productive, quality → 0.5 (no event)
        th.inscribe(TrajectoryRecord(sig, "explore", 0.05, 2))
        # Second: productive again → confirmation (1)
        th.inscribe(TrajectoryRecord(sig, "explore", 0.05, 2))
        # Third: quality still > 0; actual stagnant → surprise (1)
        th.inscribe(TrajectoryRecord(sig, "explore", 0.0, 0))
        # Fourth: quality still > 0 at that moment; actual productive → confirmation (2)
        # quality after U=2,F=1: (2-1)/(2+1+1) = 0.25 > 0 → predict productive
        th.inscribe(TrajectoryRecord(sig, "explore", 0.05, 2))
        # total events = 3 (inscriptions 2,3,4); 2 conf + 1 surp → rate = 1/3
        assert th.trajectory_surprise_rate() == pytest.approx(1 / 3)

    def test_independent_signatures_aggregate(self):
        """Confirmations and surprises from different signatures aggregate globally."""
        th = TrajectoryHistorization()
        sig_a = (0, 1)
        sig_b = (1, 0)
        # sig_a: first productive, second productive → 1 confirmation
        th.inscribe(TrajectoryRecord(sig_a, "explore", 0.05, 2))
        th.inscribe(TrajectoryRecord(sig_a, "explore", 0.05, 2))
        # sig_b: first stagnant, second productive (quality < 0 → surprise)
        th.inscribe(TrajectoryRecord(sig_b, "explore", 0.0, 0))
        th.inscribe(TrajectoryRecord(sig_b, "explore", 0.05, 1))
        # total: 1 conf (sig_a) + 1 surp (sig_b) → rate = 0.5
        assert th.trajectory_surprise_rate() == pytest.approx(0.5)

    # --- classify_trajectory_experience ---

    def test_classify_exploratory_when_no_data(self):
        """No revisit events → 'exploratory'."""
        th = TrajectoryHistorization()
        assert th.classify_trajectory_experience() == "exploratory"

    def test_classify_exploratory_below_threshold(self):
        """Fewer than 3 revisit events → 'exploratory', regardless of surprise rate."""
        th = TrajectoryHistorization()
        sig = (0,)
        # 2 inscriptions → 1 revisit event (1 conf or surp), below threshold of 3
        th.inscribe(TrajectoryRecord(sig, "explore", 0.0, 0))
        th.inscribe(TrajectoryRecord(sig, "explore", 0.0, 0))
        # Only 1 total revisit event → still exploratory
        assert th.classify_trajectory_experience() == "exploratory"

    def test_classify_stable_with_all_confirmations(self):
        """All confirmations (0% surprise rate) → 'stable'."""
        th = TrajectoryHistorization()
        sig = (0, 1)
        # Build up 3+ revisit events: all productive (quality > 0 → predict → confirm)
        for _ in range(5):
            th.inscribe(TrajectoryRecord(sig, "explore", 0.05, 2))
        # 4 revisit events, 0 surprises → rate = 0.0 → stable
        assert th.classify_trajectory_experience() == "stable"

    def test_classify_volatile_with_high_surprise_rate(self):
        """Surprise rate ≥ 0.3 → 'volatile'."""
        th = TrajectoryHistorization()
        sig = (0,)
        # First: stagnant → quality = -0.5
        th.inscribe(TrajectoryRecord(sig, "explore", 0.0, 0))
        # Second: stagnant → quality < 0 → predict stagnant → actual stagnant → conf
        th.inscribe(TrajectoryRecord(sig, "explore", 0.0, 0))
        # Third: productive → quality < 0 → predict stagnant → actual productive → surp
        th.inscribe(TrajectoryRecord(sig, "explore", 0.05, 1))
        # Fourth: productive → quality still ≤ 0 at that point → predict stagnant → surp
        # quality after U=1,F=2: (1-2)/(1+2+1) = -0.25 < 0 → predict stagnant
        th.inscribe(TrajectoryRecord(sig, "explore", 0.05, 1))
        # 3 revisit events: 1 conf + 2 surp → rate = 2/3 ≥ 0.3 → volatile
        assert th.classify_trajectory_experience() == "volatile"

    def test_classify_stable_boundary_at_30_percent(self):
        """Surprise rate just below 0.3 → 'stable'."""
        th = TrajectoryHistorization()
        # Construct: 7 confirmations, 2 surprises → rate = 2/9 ≈ 0.222 < 0.3
        sig_c = (0, 1)
        # Prime with productive history so quality stays positive
        th.inscribe(TrajectoryRecord(sig_c, "explore", 0.05, 2))  # load=1, no event
        # 7 more productive → 7 confirmations
        for _ in range(7):
            th.inscribe(TrajectoryRecord(sig_c, "explore", 0.05, 2))
        # Now inject 2 surprises with a different sig that starts stagnant
        sig_s = (1, 0)
        th.inscribe(TrajectoryRecord(sig_s, "explore", 0.0, 0))   # load=1, no event
        th.inscribe(TrajectoryRecord(sig_s, "explore", 0.05, 1))  # surp
        th.inscribe(TrajectoryRecord(sig_s, "explore", 0.05, 1))  # surp
        # 9 total events: 7 conf + 2 surp → 2/9 < 0.3
        assert th.classify_trajectory_experience() == "stable"
