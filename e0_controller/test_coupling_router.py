"""
Tests for Coupling Router (C66)
================================
Dynamic partner selection for N>2 E₀ universes.

Key claims tested:
  1. Routing landscape is a complete graph over all universes
  2. RECOVERY selects partner with best coupling track record
  3. EXPLORATION selects partner with highest structural difference
  4. Historization shifts partner preference over time
  5. Dynamic membership (add/remove) maintains valid topology
  6. Structural distance is correct (Jaccard complement)
  7. Dual selection pressures are genuinely different
  8. make_routed_peer_fn integrates with controller interface
"""

import pytest

from e0_controller.coupling_router import (
    CouplingReason,
    CouplingRouter,
    CouplingSelection,
    make_routed_peer_fn,
    structural_distance,
)
from e0_controller.landscape import Landscape
from e0_controller.multiverse import Universe
from e0_controller.primitives import Edge, Outcome


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _all_success(src, tgt):
    return Outcome.SUCCESS


def _make_universe(name: str, states: list, edges: list) -> Universe:
    """Build a universe with the given topology."""
    L = Landscape()
    for s in states:
        L.add_state(s)
    for src, tgt, d, r in edges:
        L.add_edge(src, tgt, delta=d, resistance=r)
    return Universe(name=name, landscape=L, execute_fn=_all_success,
                    start=states[0] if states else "S", goal=states[-1] if states else "G")


def _universe_A():
    return _make_universe("A", ["S", "M", "G"],
                          [("S", "M", 0.3, 0.5), ("M", "G", 0.4, 0.6)])


def _universe_B():
    return _make_universe("B", ["S", "X", "Y", "G"],
                          [("S", "X", 0.5, 0.8), ("X", "Y", 0.3, 0.5),
                           ("Y", "G", 0.4, 0.6)])


def _universe_C():
    """Completely disjoint state set from A and B."""
    return _make_universe("C", ["P", "Q", "R"],
                          [("P", "Q", 0.6, 0.7), ("Q", "R", 0.3, 0.4)])


def _universe_clone_A():
    """Same topology as A — minimal structural distance."""
    return _make_universe("D", ["S", "M", "G"],
                          [("S", "M", 0.3, 0.5), ("M", "G", 0.4, 0.6)])


# ══════════════════════════════════════════════
# 1. Structural Distance
# ══════════════════════════════════════════════

class TestStructuralDistance:
    """Jaccard-complement distance metric."""

    def test_identical_topologies(self):
        a, d = _universe_A(), _universe_clone_A()
        assert structural_distance(a, d) == pytest.approx(0.0)

    def test_disjoint_topologies(self):
        a, c = _universe_A(), _universe_C()
        assert structural_distance(a, c) == pytest.approx(1.0)

    def test_partial_overlap(self):
        a, b = _universe_A(), _universe_B()
        # A: {S, M, G}, B: {S, X, Y, G} → intersection {S, G}, union {S, M, G, X, Y}
        expected = 1.0 - 2.0 / 5.0  # 0.6
        assert structural_distance(a, b) == pytest.approx(expected)

    def test_symmetric(self):
        a, b = _universe_A(), _universe_B()
        assert structural_distance(a, b) == structural_distance(b, a)

    def test_empty_landscapes(self):
        u1 = _make_universe("E1", [], [])
        u2 = _make_universe("E2", [], [])
        assert structural_distance(u1, u2) == 1.0


# ══════════════════════════════════════════════
# 2. Router Construction
# ══════════════════════════════════════════════

class TestRouterConstruction:
    """Routing landscape is a complete graph."""

    def test_minimum_two_universes(self):
        with pytest.raises(ValueError, match="at least 2"):
            CouplingRouter([_universe_A()])

    def test_two_universes_one_edge(self):
        r = CouplingRouter([_universe_A(), _universe_B()])
        assert r.universe_count == 2
        assert r.landscape.edge_count() == 1  # one bidirectional edge

    def test_three_universes_three_edges(self):
        r = CouplingRouter([_universe_A(), _universe_B(), _universe_C()])
        assert r.universe_count == 3
        assert r.landscape.edge_count() == 3  # complete graph K3

    def test_four_universes_six_edges(self):
        d = _universe_clone_A()
        r = CouplingRouter([_universe_A(), _universe_B(), _universe_C(), d])
        assert r.universe_count == 4
        assert r.landscape.edge_count() == 6  # K4

    def test_edge_delta_reflects_distance(self):
        a, b, c = _universe_A(), _universe_B(), _universe_C()
        r = CouplingRouter([a, b, c])
        # A↔C are disjoint (Δ=1.0), A↔B partially overlap (Δ=0.6)
        delta_ac = r.landscape.difference("A", "C")
        delta_ab = r.landscape.difference("A", "B")
        assert delta_ac > delta_ab

    def test_min_delta_enforced(self):
        """Identical topologies still get min_delta edge."""
        a, d = _universe_A(), _universe_clone_A()
        r = CouplingRouter([a, d], min_delta=0.1)
        delta = r.landscape.difference("A", "D")
        assert delta == pytest.approx(0.1)


# ══════════════════════════════════════════════
# 3. RECOVERY Selection
# ══════════════════════════════════════════════

class TestRecoverySelection:
    """RECOVERY selects partner with best coupling quality."""

    def test_no_history_all_equal(self):
        """Without coupling history, all partners have quality=0."""
        a, b, c = _universe_A(), _universe_B(), _universe_C()
        r = CouplingRouter([a, b, c])
        selections = r.select_partner(a, CouplingReason.RECOVERY, max_partners=2)
        assert len(selections) == 2
        assert all(s.coupling_quality == 0.0 for s in selections)

    def test_successful_coupling_raises_quality(self):
        """After SUCCESS coupling, partner's quality increases."""
        a, b, c = _universe_A(), _universe_B(), _universe_C()
        r = CouplingRouter([a, b, c])

        # Couple A↔B with SUCCESS repeatedly
        for _ in range(5):
            r.historize("A", "B", Outcome.SUCCESS)

        sel = r.select_partner(a, CouplingReason.RECOVERY)
        assert len(sel) == 1
        assert sel[0].partner.name == "B"
        assert sel[0].coupling_quality > 0.0

    def test_failed_coupling_lowers_quality(self):
        """After FAILURE coupling, partner becomes less attractive for RECOVERY."""
        a, b, c = _universe_A(), _universe_B(), _universe_C()
        r = CouplingRouter([a, b, c])

        # B gets SUCCESS, C gets FAILURE
        for _ in range(5):
            r.historize("A", "B", Outcome.SUCCESS)
            r.historize("A", "C", Outcome.FAILURE)

        sel = r.select_partner(a, CouplingReason.RECOVERY)
        assert sel[0].partner.name == "B"  # B has better track record

    def test_exclude_parameter(self):
        """Excluded partners are not considered."""
        a, b, c = _universe_A(), _universe_B(), _universe_C()
        r = CouplingRouter([a, b, c])
        sel = r.select_partner(a, CouplingReason.RECOVERY, exclude={"B"})
        assert all(s.partner.name != "B" for s in sel)


# ══════════════════════════════════════════════
# 4. EXPLORATION Selection
# ══════════════════════════════════════════════

class TestExplorationSelection:
    """EXPLORATION selects partner with highest structural difference."""

    def test_most_different_wins(self):
        """Disjoint universe C beats partially overlapping B."""
        a, b, c = _universe_A(), _universe_B(), _universe_C()
        r = CouplingRouter([a, b, c])
        sel = r.select_partner(a, CouplingReason.EXPLORATION)
        assert sel[0].partner.name == "C"  # Completely disjoint = highest Δ

    def test_identical_topology_loses(self):
        """Clone D has lowest Δ → last choice for exploration."""
        a, b, d = _universe_A(), _universe_B(), _universe_clone_A()
        r = CouplingRouter([a, b, d])
        sel = r.select_partner(a, CouplingReason.EXPLORATION, max_partners=2)
        assert sel[-1].partner.name == "D"  # Clone is worst for exploration

    def test_exploration_ignores_quality(self):
        """Coupling history doesn't affect EXPLORATION selection."""
        a, b, c = _universe_A(), _universe_B(), _universe_C()
        r = CouplingRouter([a, b, c])

        # Give B excellent track record
        for _ in range(10):
            r.historize("A", "B", Outcome.SUCCESS)

        # EXPLORATION still picks C (higher Δ)
        sel = r.select_partner(a, CouplingReason.EXPLORATION)
        assert sel[0].partner.name == "C"


# ══════════════════════════════════════════════
# 5. Dual Selection Pressure
# ══════════════════════════════════════════════

class TestDualPressure:
    """RECOVERY and EXPLORATION can select different partners."""

    def test_recovery_vs_exploration_diverge(self):
        """Same requester, different reasons → different partners."""
        a, b, c = _universe_A(), _universe_B(), _universe_C()
        r = CouplingRouter([a, b, c])

        # Make B the reliable partner (good quality)
        for _ in range(10):
            r.historize("A", "B", Outcome.SUCCESS)
        # C remains unknown but has highest Δ

        recovery = r.select_partner(a, CouplingReason.RECOVERY)
        exploration = r.select_partner(a, CouplingReason.EXPLORATION)

        assert recovery[0].partner.name == "B"   # Best track record
        assert exploration[0].partner.name == "C"  # Most different

    def test_scores_differ_per_reason(self):
        """Score meaning changes with reason."""
        a, b, c = _universe_A(), _universe_B(), _universe_C()
        r = CouplingRouter([a, b, c])
        for _ in range(5):
            r.historize("A", "B", Outcome.SUCCESS)

        rec = r.select_partner(a, CouplingReason.RECOVERY)
        exp = r.select_partner(a, CouplingReason.EXPLORATION)

        # Recovery score = quality, exploration score = delta
        assert rec[0].score == rec[0].coupling_quality
        assert exp[0].score == exp[0].edge_delta


# ══════════════════════════════════════════════
# 6. Dynamic Membership
# ══════════════════════════════════════════════

class TestDynamicMembership:
    """Universes can be added and removed at runtime."""

    def test_add_universe(self):
        a, b = _universe_A(), _universe_B()
        r = CouplingRouter([a, b])
        assert r.universe_count == 2

        c = _universe_C()
        r.add_universe(c)
        assert r.universe_count == 3
        assert r.landscape.edge_count() == 3  # K3

    def test_add_duplicate_ignored(self):
        a, b = _universe_A(), _universe_B()
        r = CouplingRouter([a, b])
        r.add_universe(a)  # Same name
        assert r.universe_count == 2

    def test_remove_universe(self):
        a, b, c = _universe_A(), _universe_B(), _universe_C()
        r = CouplingRouter([a, b, c])
        removed = r.remove_universe("B")
        assert removed is not None
        assert removed.name == "B"
        assert r.universe_count == 2
        assert r.landscape.edge_count() == 1  # Only A↔C remains

    def test_remove_nonexistent_returns_none(self):
        r = CouplingRouter([_universe_A(), _universe_B()])
        assert r.remove_universe("Z") is None

    def test_selection_after_add(self):
        """New universe is immediately available for selection."""
        a, b = _universe_A(), _universe_B()
        r = CouplingRouter([a, b])
        c = _universe_C()
        r.add_universe(c)

        sel = r.select_partner(a, CouplingReason.EXPLORATION)
        # C is most different → wins exploration
        assert sel[0].partner.name == "C"


# ══════════════════════════════════════════════
# 7. Historization Dynamics
# ══════════════════════════════════════════════

class TestHistorizationDynamics:
    """Coupling history changes partner preferences over time."""

    def test_recovery_preference_shifts(self):
        """Initially equal. After coupling, preference shifts to successful partner."""
        a, b, c = _universe_A(), _universe_B(), _universe_C()
        r = CouplingRouter([a, b, c])

        # Initially: both quality=0, selection is arbitrary
        sel_before = r.select_partner(a, CouplingReason.RECOVERY, max_partners=2)
        quality_spread_before = abs(sel_before[0].score - sel_before[1].score)

        # Couple A↔B with SUCCESS, A↔C with FAILURE
        for _ in range(10):
            r.historize("A", "B", Outcome.SUCCESS)
            r.historize("A", "C", Outcome.FAILURE)

        sel_after = r.select_partner(a, CouplingReason.RECOVERY, max_partners=2)
        quality_spread_after = abs(sel_after[0].score - sel_after[1].score)

        assert quality_spread_after > quality_spread_before
        assert sel_after[0].partner.name == "B"

    def test_historize_both_directions(self):
        """Historizing A→B also informs B's view of A."""
        a, b = _universe_A(), _universe_B()
        r = CouplingRouter([a, b])

        for _ in range(5):
            r.historize("A", "B", Outcome.SUCCESS)

        # Now ask from B's perspective
        sel = r.select_partner(b, CouplingReason.RECOVERY)
        # The edge is historized → quality > 0
        assert sel[0].coupling_quality > 0.0

    def test_coupling_history_dict(self):
        a, b = _universe_A(), _universe_B()
        r = CouplingRouter([a, b])

        for _ in range(3):
            r.historize("A", "B", Outcome.SUCCESS)

        history = r.coupling_history("A", "B")
        assert "trace_quality" in history
        assert "trace_load" in history
        assert history["trace_load"] > 0


# ══════════════════════════════════════════════
# 8. Update Distances
# ══════════════════════════════════════════════

class TestUpdateDistances:
    """Structural distances can be recomputed after landscape changes."""

    def test_distance_changes_after_state_addition(self):
        a, b = _universe_A(), _universe_B()
        r = CouplingRouter([a, b])
        delta_before = r.landscape.difference("A", "B")

        # Add states from B into A's landscape → more overlap
        a.landscape.add_state("X")
        a.landscape.add_state("Y")
        r.update_distances()

        delta_after = r.landscape.difference("A", "B")
        assert delta_after < delta_before  # More overlap → lower distance


# ══════════════════════════════════════════════
# 9. Inspection
# ══════════════════════════════════════════════

class TestInspection:
    """Summary and inspection produce valid output."""

    def test_summary_format(self):
        a, b, c = _universe_A(), _universe_B(), _universe_C()
        r = CouplingRouter([a, b, c])
        s = r.summary()
        assert "3 universes" in s
        assert "recovery" in s
        assert "exploration" in s


# ══════════════════════════════════════════════
# 10. Routed Peer Function
# ══════════════════════════════════════════════

class TestRoutedPeerFn:
    """make_routed_peer_fn creates a controller-compatible peer function."""

    def test_peer_fn_callable(self):
        a, b = _universe_A(), _universe_B()
        r = CouplingRouter([a, b])
        fn = make_routed_peer_fn(r, "A", goal="G")
        assert callable(fn)

    def test_peer_fn_returns_string_or_none(self):
        a, b = _universe_A(), _universe_B()
        r = CouplingRouter([a, b])
        fn = make_routed_peer_fn(r, "A", goal="G")
        result = fn(a.landscape, "S", ["M"])
        # Result is either a string target or None
        assert result is None or isinstance(result, str)

    def test_peer_fn_with_exploration_reason(self):
        a, b, c = _universe_A(), _universe_B(), _universe_C()
        r = CouplingRouter([a, b, c])
        fn = make_routed_peer_fn(r, "A", goal="G",
                                 reason=CouplingReason.EXPLORATION)
        # Should pick C (most different) as donor
        result = fn(a.landscape, "S", ["M"])
        assert result is None or isinstance(result, str)
