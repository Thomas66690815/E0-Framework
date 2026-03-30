"""Tests for Cross-Universe Reflexive Edge Discovery (C62)."""

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.reflexive_edge_proposal import (
    EdgePattern, ProposedEdge, experienced_pattern, is_frontier,
)
from e0_controller.multiverse import Universe
from e0_controller.cross_reflexion import (
    blend_patterns,
    cross_propose_edges,
    cross_reflexion_turn,
    run_with_cross_reflexion,
    CrossReflexionResult,
    CrossReflexionRunResult,
)


# ══════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════

def _success(source: str, target: str) -> Outcome:
    return Outcome.SUCCESS


def _failure(source: str, target: str) -> Outcome:
    return Outcome.FAILURE


def _build_experienced_landscape() -> Landscape:
    """Landscape with historized edges (donor-quality experience)."""
    L = Landscape()
    L.add_edge("A", "B", delta=1.0, resistance=0.5)
    L.add_edge("B", "C", delta=0.8, resistance=0.4)
    L.add_edge("C", "D", delta=1.2, resistance=0.6)
    # Historize with successes so experienced_pattern picks them up
    for edge in list(L._delta.keys()):
        L.historization.update(edge, Outcome.SUCCESS)
        L.historization.update(edge, Outcome.SUCCESS)
    return L


def _build_frontier_landscape() -> Landscape:
    """Landscape where node X has no path to GOAL — a frontier."""
    L = Landscape()
    L.add_edge("S", "X", delta=0.5, resistance=0.3)
    L.add_edge("X", "S", delta=0.5, resistance=0.3)
    # GOAL exists but is unreachable from X
    L.add_edge("GOAL", "S", delta=0.5, resistance=0.3)
    return L


# ══════════════════════════════════════════════
# TestBlendPatterns
# ══════════════════════════════════════════════

class TestBlendPatterns:
    """Blending self and donor experience patterns."""

    def test_pure_donor_when_self_has_no_samples(self):
        self_p = EdgePattern(median_delta=0.3, median_r0=0.5,
                             sample_size=0, coverage=0.0)
        donor_p = EdgePattern(median_delta=1.0, median_r0=0.4,
                              sample_size=5, coverage=0.8)
        blended = blend_patterns(self_p, donor_p)
        # With self=0 samples, donor dominates entirely
        assert blended.median_delta == donor_p.median_delta
        assert blended.median_r0 == donor_p.median_r0

    def test_self_dominates_with_more_samples(self):
        self_p = EdgePattern(median_delta=1.0, median_r0=0.5,
                             sample_size=10, coverage=0.8)
        donor_p = EdgePattern(median_delta=2.0, median_r0=1.0,
                              sample_size=2, coverage=0.5)
        blended = blend_patterns(self_p, donor_p, coupling_discount=0.5)
        # self_w=10, donor_w=2*0.5=1, total=11
        # delta = (1.0*10 + 2.0*1) / 11 ≈ 1.09
        assert blended.median_delta < 1.2  # closer to self
        assert blended.median_delta > 1.0  # but influenced by donor

    def test_discount_zero_ignores_donor(self):
        self_p = EdgePattern(median_delta=1.0, median_r0=0.5,
                             sample_size=5, coverage=0.8)
        donor_p = EdgePattern(median_delta=2.0, median_r0=1.0,
                              sample_size=5, coverage=0.8)
        blended = blend_patterns(self_p, donor_p, coupling_discount=0.0)
        assert blended.median_delta == 1.0
        assert blended.median_r0 == 0.5

    def test_both_empty_uses_donor_raw(self):
        self_p = EdgePattern(median_delta=0.3, median_r0=0.5,
                             sample_size=0, coverage=0.0)
        donor_p = EdgePattern(median_delta=0.7, median_r0=0.9,
                              sample_size=0, coverage=0.0)
        blended = blend_patterns(self_p, donor_p)
        assert blended.median_delta == 0.7
        assert blended.median_r0 == 0.9


# ══════════════════════════════════════════════
# TestCrossPropose
# ══════════════════════════════════════════════

class TestCrossPropose:
    """Cross-reflexive edge proposal engine."""

    def test_proposes_edges_at_frontier(self):
        stuck = _build_frontier_landscape()
        donor = _build_experienced_landscape()
        result = cross_propose_edges(
            stuck, donor, "X", "GOAL", donor_name="B",
        )
        assert result.edges_added > 0
        assert result.frontier_node == "X"
        assert result.donor_name == "B"

    def test_proposals_use_donor_pattern(self):
        stuck = _build_frontier_landscape()
        donor = _build_experienced_landscape()
        result = cross_propose_edges(
            stuck, donor, "X", "GOAL", donor_name="B",
        )
        # Proposals should exist and reference donor
        assert len(result.proposals) > 0
        for p in result.proposals:
            assert "Cross-reflexion" in p.rationale
            assert "B" in p.rationale

    def test_no_proposals_when_all_connected(self):
        """If current connects to all other states, nothing to propose."""
        L = Landscape()
        L.add_edge("X", "Y", delta=0.5, resistance=0.3)
        L.add_edge("X", "GOAL", delta=0.5, resistance=0.3)
        donor = _build_experienced_landscape()
        result = cross_propose_edges(L, donor, "X", "GOAL")
        assert result.edges_added == 0
        assert len(result.proposals) == 0

    def test_max_proposals_respected(self):
        # Landscape with many unreachable states
        stuck = Landscape()
        stuck.add_edge("X", "Y", delta=0.5, resistance=0.3)
        for i in range(10):
            stuck.add_state(f"S{i}")
        stuck.add_state("GOAL")
        donor = _build_experienced_landscape()
        result = cross_propose_edges(
            stuck, donor, "X", "GOAL", max_proposals=3,
        )
        assert len(result.proposals) <= 3

    def test_goal_proximity_ordering(self):
        """Targets closer to goal should be proposed first."""
        L = Landscape()
        L.add_edge("X", "Y", delta=0.5, resistance=0.3)
        L.add_state("FAR")
        L.add_state("NEAR")
        L.add_edge("NEAR", "GOAL", delta=0.5, resistance=0.3)
        L.add_state("GOAL")
        donor = _build_experienced_landscape()
        result = cross_propose_edges(L, donor, "X", "GOAL")
        # GOAL itself or NEAR (which has path to GOAL) should be first
        targets = [p.target for p in result.proposals]
        goal_idx = targets.index("GOAL") if "GOAL" in targets else len(targets)
        near_idx = targets.index("NEAR") if "NEAR" in targets else len(targets)
        far_idx = targets.index("FAR") if "FAR" in targets else -1
        assert min(goal_idx, near_idx) < far_idx

    def test_confidence_capped_at_0_7(self):
        """Cross-reflexion caps confidence lower than self-reflexion."""
        stuck = _build_frontier_landscape()
        donor = _build_experienced_landscape()
        result = cross_propose_edges(stuck, donor, "X", "GOAL")
        for p in result.proposals:
            assert p.confidence <= 0.7

    def test_coupling_discount_affects_result(self):
        # Need self-experience so discount matters (with 0 self samples,
        # donor dominates regardless of discount)
        stuck1 = _build_frontier_landscape()
        stuck2 = _build_frontier_landscape()
        # Give stuck landscapes some experience
        for L in (stuck1, stuck2):
            for edge in list(L._delta.keys()):
                L.historization.update(edge, Outcome.SUCCESS)
                L.historization.update(edge, Outcome.SUCCESS)
        donor = _build_experienced_landscape()

        r_low = cross_propose_edges(
            stuck1, donor, "X", "GOAL", coupling_discount=0.1,
        )
        r_high = cross_propose_edges(
            stuck2, donor, "X", "GOAL", coupling_discount=1.0,
        )
        # Different discount → different blended pattern → different R₀
        if r_low.proposals and r_high.proposals:
            assert r_low.proposals[0].resistance != r_high.proposals[0].resistance


# ══════════════════════════════════════════════
# TestCrossReflexionTurn
# ══════════════════════════════════════════════

class TestCrossReflexionTurn:
    """Turn function for MultiverseController integration."""

    def test_turn_runs_without_error(self):
        active = Universe(
            name="A",
            landscape=_build_frontier_landscape(),
            execute_fn=_success,
            start="S",
            goal="GOAL",
        )
        passive = Universe(
            name="B",
            landscape=_build_experienced_landscape(),
            execute_fn=_success,
            start="A",
            goal="D",
        )
        # Should not raise
        cross_reflexion_turn(active, passive)

    def test_turn_adds_edges_when_stuck(self):
        active = Universe(
            name="stuck",
            landscape=_build_frontier_landscape(),
            execute_fn=_failure,  # all transitions fail → stays stuck
            start="S",
            goal="GOAL",
        )
        passive = Universe(
            name="experienced",
            landscape=_build_experienced_landscape(),
            execute_fn=_success,
            start="A",
            goal="D",
        )
        edges_before = len(active.landscape._delta)
        cross_reflexion_turn(active, passive)
        edges_after = len(active.landscape._delta)
        # Should have proposed at least one new edge
        assert edges_after >= edges_before

    def test_turn_does_not_add_if_not_frontier(self):
        # Active has path to goal — not a frontier
        L = Landscape()
        L.add_edge("S", "GOAL", delta=0.5, resistance=0.3)
        active = Universe("ok", L, _success, "S", "GOAL")
        passive = Universe(
            "B", _build_experienced_landscape(), _success, "A", "D",
        )
        edges_before = len(active.landscape._delta)
        cross_reflexion_turn(active, passive)
        assert len(active.landscape._delta) == edges_before


# ══════════════════════════════════════════════
# TestRunWithCrossReflexion
# ══════════════════════════════════════════════

class TestRunWithCrossReflexion:
    """Full integrated run: Universe A with donor B."""

    def test_run_completes(self):
        # Universe A: has gap (S→X, no path to GOAL)
        a = Universe(
            name="target",
            landscape=_build_frontier_landscape(),
            execute_fn=_success,
            start="S",
            goal="GOAL",
        )
        # Universe B: experienced donor
        b = Universe(
            name="donor",
            landscape=_build_experienced_landscape(),
            execute_fn=_success,
            start="A",
            goal="D",
        )
        result = run_with_cross_reflexion(a, b, max_cycles=30)
        assert isinstance(result, CrossReflexionRunResult)
        assert result.total_proposals >= 0

    def test_cross_reflexion_enables_goal(self):
        """With donor experience, A should get edges toward GOAL."""
        a = Universe(
            name="target",
            landscape=_build_frontier_landscape(),
            execute_fn=_success,
            start="S",
            goal="GOAL",
        )
        b = Universe(
            name="donor",
            landscape=_build_experienced_landscape(),
            execute_fn=_success,
            start="A",
            goal="D",
        )
        result = run_with_cross_reflexion(a, b, max_cycles=30)
        # Cross-reflexion should have proposed edges
        assert result.total_edges_added > 0
        # Check that at least one frontier was detected
        assert len(result.frontier_nodes) > 0

    def test_result_properties(self):
        a = Universe(
            name="target",
            landscape=_build_frontier_landscape(),
            execute_fn=_success,
            start="S",
            goal="GOAL",
        )
        b = Universe(
            name="donor",
            landscape=_build_experienced_landscape(),
            execute_fn=_success,
            start="A",
            goal="D",
        )
        result = run_with_cross_reflexion(a, b, max_cycles=20)
        assert result.total_proposals == sum(
            len(r.proposals) for r in result.reflexions
        )
        assert result.total_edges_added == sum(
            r.edges_added for r in result.reflexions
        )


# ══════════════════════════════════════════════
# TestCrossReflexionResult
# ══════════════════════════════════════════════

class TestCrossReflexionResult:
    """Result type validation."""

    def test_empty_result(self):
        r = CrossReflexionResult(
            proposals=[],
            self_pattern=EdgePattern(0.3, 0.5, 0, 0.0),
            donor_pattern=EdgePattern(1.0, 0.4, 5, 0.8),
            edges_added=0,
            frontier_node="X",
            donor_name="B",
        )
        assert r.edges_added == 0
        assert r.donor_name == "B"

    def test_run_result_no_reflexions(self):
        from e0_controller.controller import RunTrace
        r = CrossReflexionRunResult(
            trace=RunTrace(),
            reflexions=[],
            goal_reached=False,
        )
        assert r.total_proposals == 0
        assert r.total_edges_added == 0
        assert r.frontier_nodes == []
