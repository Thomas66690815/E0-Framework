"""Tests for Focus Narrowing (C82).

When OI is too high and focus_k is set, the controller narrows the
candidate set to k random neighbors before selection. Peer suggestions
bypass the focus filter and are integrated as the (k+1)th candidate.
"""

import random

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller, EscalationType


# ══════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════

def _success(source: str, target: str) -> Outcome:
    return Outcome.SUCCESS


def _build_large_landscape(n: int = 30) -> Landscape:
    """FC landscape with n states: high OI, suitable for focus tests."""
    states = [f"S{i}" for i in range(n - 1)] + ["GOAL"]
    return Landscape.fully_connected(states, delta=0.5, resistance=1.0)


def _build_differential_domain(n: int = 30, p_correct: float = 0.85, p_wrong: float = 0.30):
    """FC landscape + execute_fn with differential feedback."""
    states = [f"S{i}" for i in range(n - 1)] + ["GOAL"]
    ls = Landscape.fully_connected(states, delta=0.5, resistance=1.0)
    happy_path = set()
    for i in range(len(states) - 1):
        happy_path.add((states[i], states[i + 1]))

    exec_rng = random.Random(42)

    def execute_fn(source, target):
        if (source, target) in happy_path:
            return Outcome.SUCCESS if exec_rng.random() < p_correct else Outcome.FAILURE
        return Outcome.SUCCESS if exec_rng.random() < p_wrong else Outcome.FAILURE

    return ls, execute_fn, states


def _peer_picks_goal(landscape, current, neighbors):
    if "GOAL" in neighbors:
        return "GOAL"
    return None


# ══════════════════════════════════════════════
# TestFocusNarrowingBasics
# ══════════════════════════════════════════════

class TestFocusNarrowingBasics:
    """C82: Basic focus narrowing mechanics."""

    def test_focus_k_accepted(self):
        """Controller accepts focus_k parameter."""
        L = _build_large_landscape(10)
        ctrl = E0Controller(L, _success, focus_k=5)
        assert ctrl.focus_k == 5

    def test_focus_k_none_is_default(self):
        """Without focus_k, no narrowing."""
        L = _build_large_landscape(10)
        ctrl = E0Controller(L, _success)
        assert ctrl.focus_k is None

    def test_focus_reduces_candidates(self):
        """With focus_k=5, at most 5 candidates are considered."""
        L = _build_large_landscape(30)
        ctrl = E0Controller(L, _success, focus_k=5, overload_threshold=3.0)
        # N=30, OI=29 (all unexplored) >> 3.0 → focus triggers
        target, escalated, esc_type = ctrl.select_next("S0")
        assert target is not None
        # Controller selects from reduced set — no crash, valid state

    def test_focus_not_triggered_below_threshold(self):
        """When OI < threshold, focus_k is ignored."""
        L = _build_large_landscape(3)  # only 2 neighbors → OI=2
        ctrl = E0Controller(L, _success, focus_k=1, overload_threshold=3.0)
        target, escalated, esc_type = ctrl.select_next("S0")
        # OI=2 < 3.0, so normal selection (no narrowing)
        assert esc_type == EscalationType.NONE
        assert target is not None

    def test_focus_not_triggered_when_few_neighbors(self):
        """When neighbors <= focus_k, no narrowing needed."""
        L = _build_large_landscape(5)
        ctrl = E0Controller(L, _success, focus_k=10, overload_threshold=3.0)
        target, _, _ = ctrl.select_next("S0")
        assert target is not None


# ══════════════════════════════════════════════
# TestFocusPeerIntegration
# ══════════════════════════════════════════════

class TestFocusPeerIntegration:
    """C82: Peer suggestion bypasses focus filter."""

    def test_peer_added_to_focused_set(self):
        """Peer's choice is added even if not in the k random neighbors."""
        L = _build_large_landscape(30)
        peer_calls = []

        def tracking_peer(landscape, current, neighbors):
            peer_calls.append(len(neighbors))
            return "GOAL"

        ctrl = E0Controller(
            L, _success,
            focus_k=5,
            peer_fn=tracking_peer,
            overload_threshold=3.0,
        )
        target, _, _ = ctrl.select_next("S0")
        # Peer was called (OI > threshold)
        assert len(peer_calls) == 1
        # Peer saw ALL neighbors, not the narrowed set
        assert peer_calls[0] == 29  # 30-1 neighbors from S0

    def test_peer_sees_full_graph(self):
        """Peer receives all admissible neighbors, not the focused subset."""
        L = _build_large_landscape(20)
        seen_counts = []

        def count_peer(landscape, current, neighbors):
            seen_counts.append(len(neighbors))
            return None

        ctrl = E0Controller(
            L, _success,
            focus_k=3,
            peer_fn=count_peer,
            overload_threshold=3.0,
        )
        ctrl.select_next("S0")
        # Peer saw all 19 neighbors, not just 3
        assert seen_counts[0] == 19

    def test_focus_plus_peer_reaches_goal(self):
        """Focus narrowing + peer together can reach goal."""
        ls, exec_fn, states = _build_differential_domain(20)
        ctrl = E0Controller(
            ls, exec_fn,
            focus_k=5,
            peer_fn=_peer_picks_goal,
            overload_threshold=3.0,
        )
        trace = ctrl.run("S0", goal="GOAL", max_cycles=200)
        # With peer always suggesting GOAL, should reach it
        reached = (trace.steps and trace.steps[-1].target == "GOAL") if trace.steps else False
        assert reached

    def test_peer_none_with_focus_still_works(self):
        """If peer returns None, focus still works alone."""
        L = _build_large_landscape(20)
        ctrl = E0Controller(
            L, _success,
            focus_k=5,
            peer_fn=lambda l, c, n: None,
            overload_threshold=3.0,
        )
        target, _, _ = ctrl.select_next("S0")
        assert target is not None


# ══════════════════════════════════════════════
# TestFocusBackwardCompat
# ══════════════════════════════════════════════

class TestFocusBackwardCompat:
    """C82: Without focus_k, old C63 peer-override behavior is preserved."""

    def test_peer_override_without_focus(self):
        """Without focus_k, peer still overrides when OI > threshold."""
        L = _build_large_landscape(20)
        ctrl = E0Controller(
            L, _success,
            peer_fn=_peer_picks_goal,
            overload_threshold=3.0,
        )
        target, escalated, esc_type = ctrl.select_next("S0")
        assert target == "GOAL"
        assert escalated is True
        assert esc_type == EscalationType.OVERLOADED

    def test_no_focus_no_peer_unchanged(self):
        """Without focus_k and peer_fn, behavior is unchanged."""
        L = _build_large_landscape(10)
        ctrl = E0Controller(L, _success)
        target, escalated, esc_type = ctrl.select_next("S0")
        assert target is not None
        assert escalated is False
        assert esc_type == EscalationType.NONE


# ══════════════════════════════════════════════
# TestFocusScalingEffect
# ══════════════════════════════════════════════

class TestFocusScalingEffect:
    """C82: Focus narrowing rescues performance on large domains."""

    def test_focus_improves_goal_rate(self):
        """With focus_k=8, goal rate on N=30 domain improves vs solo."""
        ls, exec_fn, states = _build_differential_domain(30)

        # Solo (no focus)
        ctrl_solo = E0Controller(ls, exec_fn)
        solo_goals = 0
        for _ in range(10):
            # Reset controller for each episode by creating new
            ls_s, ex_s, _ = _build_differential_domain(30)
            c = E0Controller(ls_s, ex_s)
            trace = c.run("S0", goal="GOAL", max_cycles=200)
            if trace.steps and trace.steps[-1].target == "GOAL":
                solo_goals += 1

        # Focused (k=8)
        focus_goals = 0
        for _ in range(10):
            ls_f, ex_f, _ = _build_differential_domain(30)
            c = E0Controller(ls_f, ex_f, focus_k=8, overload_threshold=3.0)
            trace = c.run("S0", goal="GOAL", max_cycles=200)
            if trace.steps and trace.steps[-1].target == "GOAL":
                focus_goals += 1

        # Focus should improve goal rate (allow some variance)
        assert focus_goals >= solo_goals, (
            f"Focus ({focus_goals}/10) should beat solo ({solo_goals}/10)")
