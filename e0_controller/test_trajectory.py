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


# ---------------------------------------------------------------------------
# TestTrajectoryEndToEnd (C279)
# ---------------------------------------------------------------------------

class TestTrajectoryEndToEnd:
    """C279 Stage 1: Integration tests for classify_trajectory_experience().

    Validates that realistic multi-round session patterns produce the
    expected classification using directly-scripted TrajectoryRecord
    inscriptions (no navigate() or run_multidomain_cycle() — fast and
    deterministic).

    Design constraint (C279 analysis): 2-community landscapes produce at
    most 4 distinct signatures {(0,), (1,), (0,1), (1,0)}, so revisits
    accumulate faster than with 4+ communities (birthday paradox with k
    symbols).  Tests that verify the '≥3 events → leaves exploratory'
    boundary use this small signature space explicitly.

    Arithmetic derivations:
      quality = (U-F)/(U+F+1)  (same formula as edge-level Historization)
      productive ↔ coverage_delta > 0 or community_crossings > 0
      surprise ↔ quality predicted the wrong direction
    """

    def test_exploratory_with_single_revisit_event(self):
        """1 revisit event (< 3 threshold) → 'exploratory'."""
        th = TrajectoryHistorization()
        sig = (0, 1)
        th.inscribe(TrajectoryRecord(sig, "explore", 0.05, 2))  # load=1, no event
        th.inscribe(TrajectoryRecord(sig, "explore", 0.05, 2))  # load=2, 1 event
        # total revisit events = 1 < 3 → still exploratory
        assert th.classify_trajectory_experience() == "exploratory"

    def test_leaves_exploratory_after_sufficient_data(self):
        """≥3 revisit events → classification leaves 'exploratory'.

        5 productive inscriptions of the same sig → 4 revisit events (all
        confirmations because quality rises monotonically) → not exploratory.
        """
        th = TrajectoryHistorization()
        sig = (0, 1)
        for _ in range(5):
            th.inscribe(TrajectoryRecord(sig, "explore", 0.05, 2))
        result = th.classify_trajectory_experience()
        assert result != "exploratory"

    def test_stable_session_pattern(self):
        """Consistent productive history → surprise_rate = 0.25 < 0.3 → 'stable'.

        Session: 4 productive inscriptions of same sig, then 1 stagnant.
        Derivation:
          i=1 (p): U=1,F=0, quality=0.5.    No event.
          i=2 (p): quality=0.5→predict p→actual p→CONF.  U=2,F=0.
          i=3 (p): quality=0.667→CONF.  U=3,F=0.
          i=4 (p): quality=0.75→CONF.   U=4,F=0.
          i=5 (s): quality=0.8→predict p→actual s→SURP.  U=4,F=1.
        Events: 3 CONF + 1 SURP = 4 total.  surprise_rate = 1/4 = 0.25 → stable.
        """
        th = TrajectoryHistorization()
        sig = (0, 1)
        for _ in range(4):
            th.inscribe(TrajectoryRecord(sig, "explore", 0.05, 2))  # productive
        th.inscribe(TrajectoryRecord(sig, "explore", 0.0, 0))       # stagnant
        assert th.trajectory_surprise_rate() == pytest.approx(0.25)
        assert th.classify_trajectory_experience() == "stable"

    def test_volatile_session_pattern(self):
        """Alternating productive/stagnant → surprise_rate = 0.75 ≥ 0.3 → 'volatile'.

        Session on sig (0,): p, s, p, s, s.
        Derivation:
          i=1 (p): U=1,F=0, quality=0.5.     No event.
          i=2 (s): quality=0.5→predict p→actual s→SURP.  U=1,F=1, quality=0.
          i=3 (p): quality=0→predict p→actual p→CONF.    U=2,F=1, quality=0.25.
          i=4 (s): quality=0.25→predict p→actual s→SURP. U=2,F=2, quality=0.
          i=5 (s): quality=0→predict p→actual s→SURP.    U=2,F=3.
        Events: 1 CONF + 3 SURP = 4 total.  surprise_rate = 3/4 = 0.75 → volatile.
        """
        th = TrajectoryHistorization()
        sig = (0,)
        th.inscribe(TrajectoryRecord(sig, "explore", 0.05, 1))  # p: load=1
        th.inscribe(TrajectoryRecord(sig, "explore", 0.0,  0))  # s: SURP
        th.inscribe(TrajectoryRecord(sig, "explore", 0.05, 1))  # p: CONF
        th.inscribe(TrajectoryRecord(sig, "explore", 0.0,  0))  # s: SURP
        th.inscribe(TrajectoryRecord(sig, "explore", 0.0,  0))  # s: SURP
        assert th.trajectory_surprise_rate() == pytest.approx(0.75)
        assert th.classify_trajectory_experience() == "volatile"

    def test_two_community_signature_diversity(self):
        """20-round cycling over 4 signatures → sufficient revisits to leave exploratory.

        Design: 2-community landscape → 4 distinct signatures.
        Birthday paradox: 20 rounds / 4 signatures → ~5 visits per sig → ~4 events each.
        Validates the C279 design constraint: 2 communities are the minimum for
        reliable revisit accumulation within typical session lengths.

        The specific pattern (4th inscription stagnant, rest productive) produces
        ~3 CONF + 1 SURP per signature → rate ≈ 0.267 < 0.3 → 'stable'.
        """
        th = TrajectoryHistorization()
        sigs = [(0,), (1,), (0, 1), (1, 0)]
        for i in range(20):
            sig = sigs[i % 4]
            delta = 0.02 if i % 5 != 4 else 0.0
            th.inscribe(TrajectoryRecord(sig, "explore", delta, 1))
        assert th.classify_trajectory_experience() != "exploratory"


# ---------------------------------------------------------------------------
# TestTrajectoryAdaptation (C280)
# ---------------------------------------------------------------------------


class TestTrajectoryAdaptation:
    """C280: adapt_from_trajectory_experience() and adaptive plan() thresholds.

    Mirrors C188 adapt_from_experience() at trajectory level.
    Claims:
      1. adapt_from_trajectory_experience() returns correct dict for each experience type.
      2. plan() uses the adaptive quality_threshold (volatile fires at -0.167, stable does not).
      3. plan() uses the adaptive step_multiplier (volatile → 1.5x, stable → 2.0x).

    Key arithmetic:
      volatile sig (0,) via (p,s,p,s,s): U=2,F=3 → quality=-1/6 ≈ -0.167
        volatile threshold=-0.15 → -0.167 < -0.15 → fires
        stable  threshold=-0.30 → -0.167 > -0.30 → does not fire
      deeply stagnant sig via 5×stagnant: U=0,F=5 → quality=-5/6 ≈ -0.833
        fires both thresholds; differentiates only step_multiplier.
    """

    # --- Helpers ---

    def _make_volatile_session(self) -> TrajectoryHistorization:
        """Builds volatile session: sig (0,) with pattern p,s,p,s,s → rate=0.75."""
        th = TrajectoryHistorization()
        sig = (0,)
        th.inscribe(TrajectoryRecord(sig, "explore", 0.05, 1))  # p: no event
        th.inscribe(TrajectoryRecord(sig, "explore", 0.0,  0))  # s: SURP
        th.inscribe(TrajectoryRecord(sig, "explore", 0.05, 1))  # p: CONF
        th.inscribe(TrajectoryRecord(sig, "explore", 0.0,  0))  # s: SURP
        th.inscribe(TrajectoryRecord(sig, "explore", 0.0,  0))  # s: SURP
        # 1 CONF + 3 SURP → rate=0.75 → volatile; quality=(2-3)/(2+3+1)=-1/6
        return th

    def _add_stable_base(self, th: TrajectoryHistorization, sig: PathSignature,
                         n_productive: int) -> None:
        """Add n_productive inscriptions of sig (all confirmations) to th."""
        for _ in range(n_productive):
            th.inscribe(TrajectoryRecord(sig, "explore", 0.05, 2))

    # --- adapt_from_trajectory_experience() ---

    def test_adapt_exploratory_returns_defaults(self):
        """Fresh hist → exploratory → default thresholds (same as stable)."""
        th = TrajectoryHistorization()
        result = th.adapt_from_trajectory_experience()
        assert result["quality_threshold"] == pytest.approx(-0.3)
        assert result["step_multiplier"] == pytest.approx(2.0)

    def test_adapt_stable_returns_defaults(self):
        """Stable session → quality_threshold=-0.3, step_multiplier=2.0."""
        th = TrajectoryHistorization()
        sig = (0, 1)
        for _ in range(5):
            th.inscribe(TrajectoryRecord(sig, "explore", 0.05, 2))
        # 4 revisit events, all CONF → rate=0.0 → stable
        assert th.classify_trajectory_experience() == "stable"
        result = th.adapt_from_trajectory_experience()
        assert result["quality_threshold"] == pytest.approx(-0.3)
        assert result["step_multiplier"] == pytest.approx(2.0)

    def test_adapt_volatile_returns_sensitive_threshold(self):
        """Volatile session → quality_threshold=-0.15, step_multiplier=1.5."""
        th = self._make_volatile_session()
        assert th.classify_trajectory_experience() == "volatile"
        result = th.adapt_from_trajectory_experience()
        assert result["quality_threshold"] == pytest.approx(-0.15)
        assert result["step_multiplier"] == pytest.approx(1.5)

    # --- plan() threshold sensitivity ---

    def test_plan_volatile_fires_at_intermediate_quality(self):
        """In volatile session, plan() fires for sig with quality ≈ -0.167.

        Derivation: sig (0,) via (p,s,p,s,s) → quality=-1/6 ≈ -0.167.
        volatile threshold=-0.15 → -0.167 < -0.15 → fires.
        Reason string must include 'experience' keyword.
        """
        th = self._make_volatile_session()
        # sig (0,) from the volatile session has quality=-1/6, load=5
        sig = (0,)
        last_round = _make_round_result(
            coverage_delta=0.0,
            trajectory=TrajectoryRecord(sig, "explore", 0.0, 0),
        )
        a = _make_assessment(coverage=0.4, frontier_size=8)
        mode, steps, reason = plan(a, 2, [last_round], max_steps=30,
                                   trajectory_hist=th)
        assert mode == "explore"
        assert "experience" in reason.lower()

    def test_plan_stable_does_not_fire_at_intermediate_quality(self):
        """In stable session, plan() does NOT fire for sig with quality ≈ -0.167.

        Derivation: sig_test (0,) via (p,s,p,s,s) → quality=-1/6 ≈ -0.167.
        stable threshold=-0.30 → -0.167 > -0.30 → does not fire.
        sig_stable (0,1) with 9 productive inscriptions contributes 8 CONF
        to overwhelm the 3 SURP from sig_test: total 9 CONF, 3 SURP → rate=0.25 → stable.
        """
        th = TrajectoryHistorization()
        # Build stable base: 9 productive inscriptions on sig_stable → 8 CONF, 0 SURP
        sig_stable = (0, 1)
        self._add_stable_base(th, sig_stable, n_productive=9)
        # Add intermediate-quality sig_test via (p,s,p,s,s) → 1 CONF, 3 SURP
        sig_test = (0,)
        th.inscribe(TrajectoryRecord(sig_test, "explore", 0.05, 1))  # p: no event
        th.inscribe(TrajectoryRecord(sig_test, "explore", 0.0,  0))  # s: SURP
        th.inscribe(TrajectoryRecord(sig_test, "explore", 0.05, 1))  # p: CONF
        th.inscribe(TrajectoryRecord(sig_test, "explore", 0.0,  0))  # s: SURP
        th.inscribe(TrajectoryRecord(sig_test, "explore", 0.0,  0))  # s: SURP
        # Combined: 9 CONF, 3 SURP → rate=3/12=0.25 < 0.3 → stable
        assert th.classify_trajectory_experience() == "stable"
        # sig_test quality=-1/6 ≈ -0.167 > -0.30 → does NOT fire stable threshold
        last_round = _make_round_result(
            coverage_delta=0.0,
            trajectory=TrajectoryRecord(sig_test, "explore", 0.0, 0),
        )
        a = _make_assessment(coverage=0.4, frontier_size=8)
        mode, steps, reason = plan(a, 2, [last_round], max_steps=30,
                                   trajectory_hist=th)
        # Trajectory check must NOT have fired (no 'experience' in reason)
        assert "experience" not in reason.lower()

    # --- plan() step_multiplier ---

    def test_plan_volatile_uses_1_5x_steps(self):
        """Volatile session + deeply stagnant sig → base_steps × 1.5.

        sig_session (0,): (p,s,p,s,s) → 1 CONF, 3 SURP (volatile base)
        sig_target  (1,): 5×stagnant → 4 CONF (adds to session), quality=-5/6 < -0.15
        Combined: 5 CONF, 3 SURP → rate=3/8=0.375 → volatile.
        plan(max_steps=30) → steps = int(30 × 1.5) = 45.
        """
        th = self._make_volatile_session()           # sig (0,): 1C+3S
        sig_target = (1,)
        for _ in range(5):                           # sig (1,): 4C+0S → rate=5/8=0.375
            th.inscribe(TrajectoryRecord(sig_target, "explore", 0.0, 0))
        assert th.classify_trajectory_experience() == "volatile"
        last_round = _make_round_result(
            coverage_delta=0.0,
            trajectory=TrajectoryRecord(sig_target, "explore", 0.0, 0),
        )
        a = _make_assessment(coverage=0.4, frontier_size=8)
        _, steps, _ = plan(a, 2, [last_round], max_steps=30, trajectory_hist=th)
        assert steps == 45  # int(30 × 1.5)

    def test_plan_stable_uses_2x_steps(self):
        """Stable session + deeply stagnant sig → base_steps × 2.0.

        sig_stable (0,1): 5 productive → 4 CONF; sig_target (1,): 5 stagnant → 4 CONF
        Combined: 8 CONF, 0 SURP → rate=0.0 → stable.
        plan(max_steps=30) → steps = int(30 × 2.0) = 60.
        """
        th = TrajectoryHistorization()
        self._add_stable_base(th, (0, 1), n_productive=5)  # 4 CONF
        sig_target = (1,)
        for _ in range(5):                                  # 4 CONF more
            th.inscribe(TrajectoryRecord(sig_target, "explore", 0.0, 0))
        assert th.classify_trajectory_experience() == "stable"
        last_round = _make_round_result(
            coverage_delta=0.0,
            trajectory=TrajectoryRecord(sig_target, "explore", 0.0, 0),
        )
        a = _make_assessment(coverage=0.4, frontier_size=8)
        _, steps, _ = plan(a, 2, [last_round], max_steps=30, trajectory_hist=th)
        assert steps == 60  # int(30 × 2.0)


# ---------------------------------------------------------------------------
# TestSessionBenchmark (C282)
# ---------------------------------------------------------------------------


class TestSessionBenchmark:
    """C282: SessionBenchmarkResult structure and invariants.

    These tests validate the shape and consistency of benchmark results,
    not specific numeric outcomes (which depend on real landscape topology
    and are non-deterministic).  The benchmark is run with minimal
    parameters (rounds=2, steps=5) to keep tests fast.

    Claims:
      1. run_session_benchmark() returns a SessionBenchmarkResult
      2. rounds_run ≤ requested rounds (saturation may stop early)
      3. unique_signatures ≤ rounds_run (can't have more sigs than rounds)
      4. experience_category is a valid label
      5. adaptation dict has expected keys with valid types
      6. trajectory_surprise_rate is in [0, 1]
      7. If escalation fired, escalation_details is non-empty
      8. signature_diversity is in [0, 1]
      9. collision_rate = 1 - signature_diversity
      10. Per-signature revisit_events sum == total_revisit_events
    """

    @pytest.fixture(scope="class")
    def result(self):
        """Run a minimal benchmark once for all tests in this class."""
        from e0_controller.benchmark_trajectory_session import run_session_benchmark
        return run_session_benchmark(rounds=2, steps_per_round=5)

    def test_returns_session_benchmark_result(self, result):
        from e0_controller.benchmark_trajectory_session import SessionBenchmarkResult
        assert isinstance(result, SessionBenchmarkResult)

    def test_rounds_run_at_most_requested(self, result):
        """Saturation may stop cmd_run early — rounds_run ≤ 2."""
        assert result.rounds_run <= 2

    def test_unique_signatures_at_most_rounds_run(self, result):
        """Can't have more unique signatures than rounds navigated."""
        assert result.unique_signatures <= result.rounds_run

    def test_experience_category_is_valid(self, result):
        assert result.experience_category in ("stable", "volatile", "exploratory")

    def test_adaptation_has_expected_keys(self, result):
        assert "quality_threshold" in result.adaptation
        assert "step_multiplier" in result.adaptation

    def test_adaptation_quality_threshold_is_float(self, result):
        assert isinstance(result.adaptation["quality_threshold"], float)

    def test_adaptation_step_multiplier_positive(self, result):
        assert result.adaptation["step_multiplier"] > 0

    def test_surprise_rate_in_unit_interval(self, result):
        assert 0.0 <= result.trajectory_surprise_rate <= 1.0

    def test_escalation_consistency(self, result):
        """If escalation fired, details must be non-empty and vice versa."""
        if result.trajectory_escalation_fired:
            assert result.escalation_count > 0
            assert len(result.escalation_details) > 0
        else:
            assert result.escalation_count == 0
            assert len(result.escalation_details) == 0

    def test_signature_diversity_in_unit_interval(self, result):
        assert 0.0 <= result.signature_diversity <= 1.0

    def test_collision_rate_complement(self, result):
        assert result.collision_rate == pytest.approx(1.0 - result.signature_diversity)

    def test_revisit_events_consistent(self, result):
        """Sum of per-signature revisit_events == total_revisit_events."""
        computed = sum(sp.revisit_events for sp in result.per_signature)
        assert computed == result.total_revisit_events

    def test_summary_is_string_with_content(self, result):
        s = result.summary()
        assert isinstance(s, str)
        assert "Stage 2" in s
        assert result.experience_category in s

    def test_communities_count_nonnegative(self, result):
        assert result.communities_count >= 0
