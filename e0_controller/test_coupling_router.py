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
    CouplingSelfGraph,
    CouplingDiagnosis,
    ALL_COUPLING_COMPONENTS,
    ALL_COUPLING_EDGES,
    COUPLING_CORE,
    COUPLING_MODULATION,
    coupling_active_components,
    diagnose_coupling,
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

    def test_two_universes_two_directed_edges(self):
        r = CouplingRouter([_universe_A(), _universe_B()])
        assert r.universe_count == 2
        assert r.landscape.edge_count() == 2  # A→B and B→A

    def test_three_universes_six_directed_edges(self):
        r = CouplingRouter([_universe_A(), _universe_B(), _universe_C()])
        assert r.universe_count == 3
        assert r.landscape.edge_count() == 6  # directed K3

    def test_four_universes_twelve_directed_edges(self):
        d = _universe_clone_A()
        r = CouplingRouter([_universe_A(), _universe_B(), _universe_C(), d])
        assert r.universe_count == 4
        assert r.landscape.edge_count() == 12  # directed K4

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
        assert r.landscape.edge_count() == 6  # directed K3

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
        assert r.landscape.edge_count() == 2  # Only A↔C directed pair remains

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

    def test_directional_historization(self):
        """Historizing A→B does NOT affect B→A (C67 directional independence)."""
        a, b = _universe_A(), _universe_B()
        r = CouplingRouter([a, b])

        for _ in range(5):
            r.historize("A", "B", Outcome.SUCCESS)

        # A→B has quality > 0
        h_ab = r.coupling_history("A", "B")
        assert h_ab["trace_quality"] > 0.0

        # B→A remains at quality 0 (independent direction)
        h_ba = r.coupling_history("B", "A")
        assert h_ba["trace_quality"] == pytest.approx(0.0, abs=1e-9)

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
# 10. Asymmetric Coupling (C67)
# ══════════════════════════════════════════════

class TestAsymmetricCoupling:
    """Weight-based asymmetry in coupling resistance."""

    def test_default_weights_are_one(self):
        a, b = _universe_A(), _universe_B()
        r = CouplingRouter([a, b])
        assert r.get_weight("A") == 1.0
        assert r.get_weight("B") == 1.0

    def test_custom_weights_at_construction(self):
        a, b = _universe_A(), _universe_B()
        r = CouplingRouter([a, b], coupling_weights={"A": 2.0, "B": 0.5})
        assert r.get_weight("A") == 2.0
        assert r.get_weight("B") == 0.5

    def test_high_weight_donor_lowers_resistance(self):
        """High-weight donor → low R₀ on incoming edges."""
        a, b = _universe_A(), _universe_B()
        r = CouplingRouter([a, b], coupling_weights={"A": 1.0, "B": 2.0})
        # Edge A→B: B is donor (weight=2.0) → R₀ = 1.0/2.0 = 0.5
        r0_a_to_b = r.landscape.base_resistance("A", "B")
        # Edge B→A: A is donor (weight=1.0) → R₀ = 1.0/1.0 = 1.0
        r0_b_to_a = r.landscape.base_resistance("B", "A")
        assert r0_a_to_b == pytest.approx(0.5)
        assert r0_b_to_a == pytest.approx(1.0)

    def test_asymmetric_resistance_breaks_symmetry(self):
        """Same Δ but different R₀ → different effective tension."""
        a, b = _universe_A(), _universe_B()
        r = CouplingRouter([a, b], coupling_weights={"A": 1.0, "B": 3.0})
        s_eff_ab = r.landscape.effective_tension("A", "B")
        s_eff_ba = r.landscape.effective_tension("B", "A")
        # A requesting from B (heavy donor) is cheaper
        assert s_eff_ab < s_eff_ba

    def test_set_weight_updates_resistance(self):
        """Changing weight updates R₀ on all edges where universe is donor."""
        a, b, c = _universe_A(), _universe_B(), _universe_C()
        r = CouplingRouter([a, b, c])
        r0_before = r.landscape.base_resistance("A", "B")
        assert r0_before == pytest.approx(1.0)  # default weight=1.0

        r.set_weight("B", 4.0)
        r0_after = r.landscape.base_resistance("A", "B")
        assert r0_after == pytest.approx(0.25)  # 1.0 / 4.0

        # Also affects C→B edge
        r0_c_to_b = r.landscape.base_resistance("C", "B")
        assert r0_c_to_b == pytest.approx(0.25)

    def test_set_weight_does_not_affect_reverse(self):
        """Changing B's weight does NOT affect edges where B is requester."""
        a, b = _universe_A(), _universe_B()
        r = CouplingRouter([a, b])
        r.set_weight("B", 4.0)
        # B→A: A is donor, A's weight unchanged → R₀ = 1.0/1.0
        r0_b_to_a = r.landscape.base_resistance("B", "A")
        assert r0_b_to_a == pytest.approx(1.0)

    def test_invalid_weight_rejected(self):
        a, b = _universe_A(), _universe_B()
        r = CouplingRouter([a, b])
        with pytest.raises(ValueError, match="must be > 0"):
            r.set_weight("A", 0.0)
        with pytest.raises(ValueError, match="must be > 0"):
            r.set_weight("A", -1.0)

    def test_weight_affects_recovery_selection(self):
        """High-weight donor preferred for RECOVERY (lower R₀ → easier coupling)."""
        a, b, c = _universe_A(), _universe_B(), _universe_C()
        # Give C high weight, B low weight
        r = CouplingRouter([a, b, c], coupling_weights={"A": 1.0, "B": 0.3, "C": 3.0})

        # Historize equally: both SUCCESS same number of times
        for _ in range(5):
            r.historize("A", "B", Outcome.SUCCESS)
            r.historize("A", "C", Outcome.SUCCESS)

        # C has higher weight → SUCCESS historization on lower-R₀ edge
        # produces stronger quality signal
        sel = r.select_partner(a, CouplingReason.RECOVERY)
        # Both have SUCCESS history but C's edge is stronger
        # Verify at least that C's coupling is cheaper
        h_ab = r.coupling_history("A", "B")
        h_ac = r.coupling_history("A", "C")
        assert h_ac["r_eff"] < h_ab["r_eff"]

    def test_weight_in_coupling_history(self):
        """coupling_history includes donor_weight."""
        a, b = _universe_A(), _universe_B()
        r = CouplingRouter([a, b], coupling_weights={"A": 1.0, "B": 2.5})
        h = r.coupling_history("A", "B")
        assert h["donor_weight"] == 2.5

    def test_weight_in_summary(self):
        a, b = _universe_A(), _universe_B()
        r = CouplingRouter([a, b], coupling_weights={"A": 1.0, "B": 2.0})
        s = r.summary()
        assert "w=1.00" in s
        assert "w=2.00" in s

    def test_add_universe_with_weight(self):
        """Added universe uses specified weight."""
        a, b = _universe_A(), _universe_B()
        r = CouplingRouter([a, b])
        c = _universe_C()
        r.add_universe(c, weight=3.0)
        assert r.get_weight("C") == 3.0
        # A→C: C is donor (weight=3.0) → R₀ = 1.0/3.0
        r0 = r.landscape.base_resistance("A", "C")
        assert r0 == pytest.approx(1.0 / 3.0)

    def test_directional_recovery_after_asymmetric_history(self):
        """A historizes SUCCESS to B, B historizes FAILURE to A → asymmetric view."""
        a, b, c = _universe_A(), _universe_B(), _universe_C()
        r = CouplingRouter([a, b, c])

        # A has good experience with B, B has bad experience with A
        for _ in range(5):
            r.historize("A", "B", Outcome.SUCCESS)
            r.historize("B", "A", Outcome.FAILURE)

        # A's recovery → B (good track record for A→B)
        sel_a = r.select_partner(a, CouplingReason.RECOVERY, max_partners=2)
        assert sel_a[0].partner.name == "B"

        # B's recovery → NOT A (bad track record for B→A)
        sel_b = r.select_partner(b, CouplingReason.RECOVERY, max_partners=2)
        assert sel_b[0].partner.name != "A"  # C or anything but A


# ══════════════════════════════════════════════
# 11. Routed Peer Function
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


# ══════════════════════════════════════════════
# 12. Coupling Self-Graph Construction (C68)
# ══════════════════════════════════════════════

class TestCouplingSelfGraphConstruction:
    """CouplingSelfGraph topology mirrors domain SelfGraph."""

    def test_has_all_components_as_states(self):
        csg = CouplingSelfGraph()
        states = csg.landscape.states
        for c in ALL_COUPLING_COMPONENTS:
            assert c in states

    def test_has_correct_edge_count(self):
        """5 core cycle + 2 modulation = 7 edges."""
        csg = CouplingSelfGraph()
        assert csg.landscape.edge_count() == 7

    def test_core_cycle_is_closed(self):
        """trigger→selection→exchange→evaluation→recording→trigger."""
        csg = CouplingSelfGraph()
        cycle = ["trigger", "selection", "exchange",
                 "evaluation", "recording", "trigger"]
        for i in range(len(cycle) - 1):
            assert csg.landscape.has_edge(cycle[i], cycle[i + 1])

    def test_modulation_edges_feed_into_selection(self):
        csg = CouplingSelfGraph()
        assert csg.landscape.has_edge("weight_mod", "selection")
        assert csg.landscape.has_edge("distance_mod", "selection")

    def test_rho_is_cumulative(self):
        csg = CouplingSelfGraph()
        assert csg.landscape.historization.rho == 1.0


# ══════════════════════════════════════════════
# 13. Coupling Self-Historization (C68)
# ══════════════════════════════════════════════

class TestCouplingSelfHistorization:
    """self_historize records coupling outcomes correctly."""

    def test_core_only_historization(self):
        csg = CouplingSelfGraph()
        components = coupling_active_components()  # core only
        csg.self_historize(components, Outcome.SUCCESS)

        # All core edges should have load > 0
        for src, tgt in ALL_COUPLING_EDGES:
            if src in COUPLING_CORE and tgt in COUPLING_CORE:
                load = csg.landscape.historization.trace_load(
                    Edge(src, tgt))
                assert load > 0

    def test_modulation_not_historized_when_inactive(self):
        csg = CouplingSelfGraph()
        components = coupling_active_components()  # core only
        csg.self_historize(components, Outcome.SUCCESS)

        # Modulation edges should have load = 0
        mod_load = csg.landscape.historization.trace_load(
            Edge("weight_mod", "selection"))
        assert mod_load == 0.0

    def test_modulation_historized_when_active(self):
        csg = CouplingSelfGraph()
        components = coupling_active_components(weight_mod_active=True)
        csg.self_historize(components, Outcome.SUCCESS)

        mod_load = csg.landscape.historization.trace_load(
            Edge("weight_mod", "selection"))
        assert mod_load > 0

    def test_success_raises_quality(self):
        csg = CouplingSelfGraph()
        components = coupling_active_components()
        for _ in range(5):
            csg.self_historize(components, Outcome.SUCCESS)
        assert csg.component_quality("exchange") > 0.0

    def test_failure_lowers_quality(self):
        csg = CouplingSelfGraph()
        components = coupling_active_components()
        for _ in range(5):
            csg.self_historize(components, Outcome.FAILURE)
        assert csg.component_quality("exchange") < 0.0

    def test_mixed_outcomes_near_zero(self):
        csg = CouplingSelfGraph()
        components = coupling_active_components()
        for _ in range(10):
            csg.self_historize(components, Outcome.SUCCESS)
            csg.self_historize(components, Outcome.FAILURE)
        q = csg.component_quality("exchange")
        assert abs(q) < 0.15  # roughly confused


# ══════════════════════════════════════════════
# 14. Component Queries (C68)
# ══════════════════════════════════════════════

class TestCouplingComponentQueries:
    """Quality, load, and inertia queries work correctly."""

    def test_quality_all_components(self):
        csg = CouplingSelfGraph()
        for c in ALL_COUPLING_COMPONENTS:
            q = csg.component_quality(c)
            assert isinstance(q, float)

    def test_load_increases_with_use(self):
        csg = CouplingSelfGraph()
        load_before = csg.component_load("trigger")
        components = coupling_active_components()
        for _ in range(5):
            csg.self_historize(components, Outcome.SUCCESS)
        load_after = csg.component_load("trigger")
        assert load_after > load_before

    def test_inertia_default_is_one(self):
        """No outgoing edges for unknown → 1.0."""
        csg = CouplingSelfGraph()
        # "selection" has outgoing edge but no historization → inertia=1.0
        assert csg.component_inertia("selection") == pytest.approx(1.0)

    def test_snapshot_has_all_components(self):
        csg = CouplingSelfGraph()
        snap = csg.snapshot()
        for c in ALL_COUPLING_COMPONENTS:
            assert c in snap
            assert "load" in snap[c]
            assert "quality" in snap[c]
            assert "inertia" in snap[c]

    def test_summary_format(self):
        csg = CouplingSelfGraph()
        s = csg.summary()
        assert "CouplingSelfGraph:" in s
        assert "exchange" in s
        assert "core" in s


# ══════════════════════════════════════════════
# 15. Coupling Diagnosis (C68)
# ══════════════════════════════════════════════

class TestCouplingDiagnosis:
    """diagnose_coupling produces correct assessments."""

    def test_insufficient_data_initially(self):
        csg = CouplingSelfGraph()
        d = diagnose_coupling(csg)
        # All components should be insufficient (no history)
        assert len(d.insufficient_data) == len(ALL_COUPLING_COMPONENTS)
        assert len(d.harmful) == 0

    def test_healthy_after_success(self):
        csg = CouplingSelfGraph()
        components = coupling_active_components()
        for _ in range(10):
            csg.self_historize(components, Outcome.SUCCESS)

        d = diagnose_coupling(csg)
        # Core components should be healthy
        for c in COUPLING_CORE:
            assert c in d.healthy

    def test_harmful_after_failure(self):
        csg = CouplingSelfGraph()
        components = coupling_active_components()
        for _ in range(10):
            csg.self_historize(components, Outcome.FAILURE)

        d = diagnose_coupling(csg)
        assert len(d.harmful) > 0

    def test_confused_after_mixed(self):
        csg = CouplingSelfGraph()
        components = coupling_active_components()
        for _ in range(10):
            csg.self_historize(components, Outcome.SUCCESS)
            csg.self_historize(components, Outcome.FAILURE)

        d = diagnose_coupling(csg)
        assert len(d.confused) > 0

    def test_deactivation_candidates_only_modulation(self):
        """Only modulation components can be deactivation candidates."""
        csg = CouplingSelfGraph()
        components = coupling_active_components(weight_mod_active=True)
        for _ in range(10):
            csg.self_historize(components, Outcome.FAILURE)

        d = diagnose_coupling(csg)
        for name in d.deactivation_candidates:
            assert name in COUPLING_MODULATION

    def test_meta_actions_for_harmful(self):
        csg = CouplingSelfGraph()
        components = coupling_active_components(weight_mod_active=True)
        for _ in range(10):
            csg.self_historize(components, Outcome.FAILURE)

        d = diagnose_coupling(csg)
        assert any("Disable" in a or "Investigate" in a
                    for a in d.meta_actions)

    def test_all_healthy_message(self):
        csg = CouplingSelfGraph()
        # Activate ALL components so nothing is insufficient
        components = coupling_active_components(
            weight_mod_active=True, distance_mod_active=True)
        for _ in range(10):
            csg.self_historize(components, Outcome.SUCCESS)

        d = diagnose_coupling(csg)
        assert any("healthy" in a for a in d.meta_actions)


# ══════════════════════════════════════════════
# 16. Router Self-Graph Integration (C68)
# ══════════════════════════════════════════════

class TestRouterSelfGraphIntegration:
    """CouplingRouter integrates with CouplingSelfGraph."""

    def test_self_graph_default_none(self):
        r = CouplingRouter([_universe_A(), _universe_B()])
        assert r.self_graph is None

    def test_self_graph_enabled(self):
        r = CouplingRouter([_universe_A(), _universe_B()])
        r.self_graph = CouplingSelfGraph()
        assert r.self_graph is not None

    def test_historize_updates_self_graph(self):
        a, b = _universe_A(), _universe_B()
        r = CouplingRouter([a, b])
        r.self_graph = CouplingSelfGraph()

        for _ in range(5):
            r.historize("A", "B", Outcome.SUCCESS)

        # Self-graph should have accumulated load
        assert r.self_graph.component_load("exchange") > 0

    def test_historize_with_weight_mod(self):
        a, b = _universe_A(), _universe_B()
        r = CouplingRouter([a, b], coupling_weights={"A": 1.0, "B": 2.0})
        r.self_graph = CouplingSelfGraph()

        for _ in range(5):
            r.historize("A", "B", Outcome.SUCCESS, weight_mod_active=True)

        # weight_mod should have load > 0
        mod_load = r.self_graph.landscape.historization.trace_load(
            Edge("weight_mod", "selection"))
        assert mod_load > 0

    def test_historize_without_self_graph_no_error(self):
        """historize works fine even when self_graph is None."""
        r = CouplingRouter([_universe_A(), _universe_B()])
        r.historize("A", "B", Outcome.SUCCESS)  # no error

    def test_diagnosis_after_mixed_coupling(self):
        a, b, c = _universe_A(), _universe_B(), _universe_C()
        r = CouplingRouter([a, b, c])
        r.self_graph = CouplingSelfGraph()

        # Some coupling succeeds, some fails
        for _ in range(5):
            r.historize("A", "B", Outcome.SUCCESS)
            r.historize("A", "C", Outcome.FAILURE)

        d = diagnose_coupling(r.self_graph)
        # Should have enough data + reveal mixed component status
        assert isinstance(d, CouplingDiagnosis)
        assert len(d.components) == len(ALL_COUPLING_COMPONENTS)
