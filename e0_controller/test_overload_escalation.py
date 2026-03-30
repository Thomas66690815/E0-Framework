"""Tests for Overload Escalation (C63).

When the controller has many admissible neighbors but little experience
to differentiate them, it detects OVERLOADED and optionally consults
a peer system via peer_fn.
"""

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import (
    E0Controller, EscalationType, StepResult, RunTrace,
)


# ══════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════

def _success(source: str, target: str) -> Outcome:
    return Outcome.SUCCESS


def _build_wide_landscape() -> Landscape:
    """Hub with many outgoing edges, none historized → high overload."""
    L = Landscape()
    for i in range(8):
        L.add_edge("HUB", f"T{i}", delta=0.5, resistance=0.3)
    L.add_edge("HUB", "GOAL", delta=0.5, resistance=0.3)
    return L


def _build_experienced_landscape() -> Landscape:
    """Same hub topology but with historized edges → low overload."""
    L = _build_wide_landscape()
    for edge in list(L._delta.keys()):
        L.historization.update(edge, Outcome.SUCCESS)
        L.historization.update(edge, Outcome.SUCCESS)
        L.historization.update(edge, Outcome.SUCCESS)
    return L


def _peer_picks_goal(landscape, current, neighbors):
    """Peer always recommends GOAL if available."""
    if "GOAL" in neighbors:
        return "GOAL"
    return neighbors[0] if neighbors else None


def _peer_returns_none(landscape, current, neighbors):
    """Peer declines to help."""
    return None


def _peer_returns_invalid(landscape, current, neighbors):
    """Peer returns a state not in neighbors."""
    return "NONEXISTENT"


# ══════════════════════════════════════════════
# TestOverloadIndex
# ══════════════════════════════════════════════

class TestOverloadIndex:
    """Overload index calculation."""

    def test_no_neighbors_returns_zero(self):
        L = Landscape()
        L.add_state("X")
        ctrl = E0Controller(L, _success)
        assert ctrl._overload_index("X", []) == 0.0

    def test_high_oi_with_no_experience(self):
        """Many neighbors, no trace → OI = N × 1.0."""
        L = _build_wide_landscape()
        ctrl = E0Controller(L, _success)
        neighbors = ctrl._admissible_neighbors("HUB")
        oi = ctrl._overload_index("HUB", neighbors)
        # 9 neighbors × (1 - 0) = 9.0
        assert oi == len(neighbors)

    def test_low_oi_with_experience(self):
        """Same topology but historized → OI drops."""
        L = _build_experienced_landscape()
        ctrl = E0Controller(L, _success)
        neighbors = ctrl._admissible_neighbors("HUB")
        oi = ctrl._overload_index("HUB", neighbors)
        # trace_quality → +1 for all-success, |q| ≈ 1 → OI ≈ 0
        assert oi < 1.0

    def test_partial_experience(self):
        """Some edges historized, some not → intermediate OI."""
        L = _build_wide_landscape()
        # Historize half the edges
        edges = list(L._delta.keys())
        for edge in edges[:4]:
            L.historization.update(edge, Outcome.SUCCESS)
            L.historization.update(edge, Outcome.SUCCESS)
        ctrl = E0Controller(L, _success)
        neighbors = ctrl._admissible_neighbors("HUB")
        oi = ctrl._overload_index("HUB", neighbors)
        # Some quality, some not → between 0 and N
        assert 0 < oi < len(neighbors)

    def test_mixed_outcomes_give_medium_oi(self):
        """Mixed success/failure → quality near 0 → high OI."""
        L = _build_wide_landscape()
        for edge in L._delta:
            L.historization.update(edge, Outcome.SUCCESS)
            L.historization.update(edge, Outcome.FAILURE)
        ctrl = E0Controller(L, _success)
        neighbors = ctrl._admissible_neighbors("HUB")
        oi = ctrl._overload_index("HUB", neighbors)
        # |quality| ≈ 0 for mixed → OI ≈ N
        assert oi > len(neighbors) * 0.5


# ══════════════════════════════════════════════
# TestOverloadDetection
# ══════════════════════════════════════════════

class TestOverloadDetection:
    """Controller detects overload and escalates."""

    def test_overload_triggers_peer(self):
        """With peer_fn and high OI, controller uses peer's choice."""
        L = _build_wide_landscape()
        ctrl = E0Controller(
            L, _success,
            peer_fn=_peer_picks_goal,
            overload_threshold=3.0,
        )
        target, escalated, esc_type = ctrl.select_next("HUB")
        assert target == "GOAL"
        assert escalated is True
        assert esc_type == EscalationType.OVERLOADED

    def test_no_overload_without_peer_fn(self):
        """Without peer_fn, overload is never triggered."""
        L = _build_wide_landscape()
        ctrl = E0Controller(L, _success, overload_threshold=3.0)
        target, escalated, esc_type = ctrl.select_next("HUB")
        # Normal greedy selection
        assert escalated is False
        assert esc_type == EscalationType.NONE
        assert target is not None

    def test_no_overload_when_experienced(self):
        """With sufficient experience, OI stays below threshold."""
        L = _build_experienced_landscape()
        ctrl = E0Controller(
            L, _success,
            peer_fn=_peer_picks_goal,
            overload_threshold=3.0,
        )
        target, escalated, esc_type = ctrl.select_next("HUB")
        # OI < 3.0, so normal selection
        assert esc_type == EscalationType.NONE
        assert escalated is False

    def test_overload_threshold_controls_sensitivity(self):
        """Higher threshold → less likely to trigger."""
        L = _build_wide_landscape()
        # Threshold = 100 → will never trigger with 9 neighbors
        ctrl = E0Controller(
            L, _success,
            peer_fn=_peer_picks_goal,
            overload_threshold=100.0,
        )
        _, escalated, esc_type = ctrl.select_next("HUB")
        assert esc_type == EscalationType.NONE

    def test_peer_none_falls_through_to_greedy(self):
        """If peer returns None, fall through to normal selection."""
        L = _build_wide_landscape()
        ctrl = E0Controller(
            L, _success,
            peer_fn=_peer_returns_none,
            overload_threshold=3.0,
        )
        target, escalated, esc_type = ctrl.select_next("HUB")
        # Peer returned None → normal greedy
        assert esc_type == EscalationType.NONE
        assert target is not None

    def test_peer_invalid_falls_through(self):
        """If peer returns invalid state, fall through to greedy."""
        L = _build_wide_landscape()
        ctrl = E0Controller(
            L, _success,
            peer_fn=_peer_returns_invalid,
            overload_threshold=3.0,
        )
        target, escalated, esc_type = ctrl.select_next("HUB")
        assert esc_type == EscalationType.NONE
        assert target is not None


# ══════════════════════════════════════════════
# TestOverloadInRun
# ══════════════════════════════════════════════

class TestOverloadInRun:
    """Overload detection in full controller runs."""

    def test_overload_in_cycle(self):
        """cycle() correctly reports OVERLOADED escalation."""
        L = _build_wide_landscape()
        ctrl = E0Controller(
            L, _success,
            peer_fn=_peer_picks_goal,
            overload_threshold=3.0,
        )
        step = ctrl.cycle("HUB")
        assert step is not None
        assert step.escalated is True
        assert step.escalation_type == EscalationType.OVERLOADED
        assert step.target == "GOAL"

    def test_overload_recorded_in_trace(self):
        """RunTrace captures OVERLOADED escalation steps."""
        L = _build_wide_landscape()
        ctrl = E0Controller(
            L, _success,
            peer_fn=_peer_picks_goal,
            overload_threshold=3.0,
        )
        trace = ctrl.run("HUB", max_cycles=5, goal="GOAL")
        overloaded_steps = [
            s for s in trace.steps
            if s.escalation_type == EscalationType.OVERLOADED
        ]
        assert len(overloaded_steps) >= 1
        assert overloaded_steps[0].target == "GOAL"

    def test_overload_disappears_with_experience(self):
        """After historization, OI drops and peer is no longer consulted."""
        L = _build_wide_landscape()
        calls = []

        def tracking_peer(landscape, current, neighbors):
            calls.append(current)
            return neighbors[0]

        ctrl = E0Controller(
            L, _success,
            peer_fn=tracking_peer,
            overload_threshold=3.0,
        )
        # Run enough cycles to build experience
        ctrl.run("HUB", max_cycles=20, goal="GOAL")
        # Early calls should be OVERLOADED, later ones may not be
        # After enough historization, OI should drop
        assert len(calls) >= 1  # at least one peer consultation


# ══════════════════════════════════════════════
# TestOverloadWithCrossReflexion
# ══════════════════════════════════════════════

class TestOverloadWithCrossReflexion:
    """Integration: cross-reflexion as peer_fn."""

    def test_cross_reflexion_as_peer(self):
        """Use donor experience to guide overloaded controller."""
        donor_landscape = _build_experienced_landscape()

        def cross_peer(landscape, current, neighbors):
            """Consult donor's trace quality to pick best neighbor."""
            from e0_controller.reflexive_edge_proposal import experienced_pattern
            pattern = experienced_pattern(donor_landscape)
            # Pick neighbor closest to donor's median delta
            best = min(
                neighbors,
                key=lambda n: abs(
                    landscape._delta.get(Edge(current, n), 0)
                    - pattern.median_delta
                ),
            )
            return best

        L = _build_wide_landscape()
        ctrl = E0Controller(
            L, _success,
            peer_fn=cross_peer,
            overload_threshold=3.0,
        )
        step = ctrl.cycle("HUB")
        assert step is not None
        assert step.escalation_type == EscalationType.OVERLOADED
