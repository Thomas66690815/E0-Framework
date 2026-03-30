"""
Tests for Raumzeit Coupling Experiment (C54)
==============================================
Tests the structural finding: deep traps require coupling (FAILURE signals)
for escape, while shallow traps can be escaped via revisit penalty alone.

Theorem (Coupling Necessity for Trap Escape):
  A closed E₀ system (all outcomes SUCCESS) reinforces traversed edges
  through historization and cannot escape deep traps. Only coupling — an
  environment delivering FAILURE outcomes — creates the resistance
  asymmetry necessary for trap escape.
"""

import pytest
from e0_controller.primitives import Outcome
from e0_controller.raumzeit_coupling import (
    run_coupling_experiment,
    run_domain_closed,
    _has_failure_edges,
    _rebuild_landscape,
    CouplingResult,
)
from e0_controller.benchmark_domain_invariance import (
    ALL_DOMAINS,
    build_d1_linear_chain,
    build_d2_diamond,
    build_d3_gordian_trap,
    build_d4_greedy_trap,
    build_d5_grid_detour,
    build_d6_multigoal_star,
    build_d7_invoice,
    build_d8_nested_cycles,
    build_d9_wide_dag,
    build_d10_bottleneck,
    _all_success,
    run_domain,
)


# ══════════════════════════════════════════════
# Full experiment — cached fixture
# ══════════════════════════════════════════════

@pytest.fixture(scope="module")
def coupling_result() -> CouplingResult:
    return run_coupling_experiment(max_cycles=50)


# ══════════════════════════════════════════════
# Central theorem tests
# ══════════════════════════════════════════════

class TestCouplingTheorem:
    """The central structural claim."""

    def test_coupled_system_all_goals(self, coupling_result: CouplingResult):
        """Coupled system reaches all 10 goals."""
        assert coupling_result.coupled_goals_reached == 10

    def test_closed_system_misses_goals(self, coupling_result: CouplingResult):
        """Closed system fails to reach at least one goal."""
        assert coupling_result.closed_goals_reached < 10

    def test_coupling_necessary_for_some(self, coupling_result: CouplingResult):
        """At least one domain requires coupling for goal-reaching."""
        assert coupling_result.coupling_necessary_count > 0

    def test_theorem_holds(self, coupling_result: CouplingResult):
        """Every domain that needs coupling has failure edges."""
        assert coupling_result.theorem_holds

    def test_deep_traps_exist(self, coupling_result: CouplingResult):
        """There are domains classified as deep traps."""
        deep = [c for c in coupling_result.comparisons if c.trap_class == "deep"]
        assert len(deep) >= 2


# ══════════════════════════════════════════════
# Deep trap tests — coupling is necessary
# ══════════════════════════════════════════════

class TestDeepTraps:
    """Domains where closed system cannot reach the goal."""

    def test_d3_closed_fails(self):
        """D3 Gordian trap: closed system loops forever."""
        spec = build_d3_gordian_trap()
        result = run_domain_closed(spec, max_cycles=50)
        assert not result.goal_reached
        assert result.steps == 50  # hit step limit

    def test_d3_coupled_escapes(self):
        """D3 Gordian trap: coupled system escapes via failure signal."""
        spec = build_d3_gordian_trap()
        result = run_domain(spec, max_cycles=50)
        assert result.goal_reached
        assert result.steps <= 10

    def test_d6_closed_fails(self):
        """D6 multi-goal star: closed system can't reach G1."""
        spec = build_d6_multigoal_star()
        result = run_domain_closed(spec, max_cycles=50)
        assert not result.goal_reached

    def test_d6_coupled_escapes(self):
        """D6 multi-goal star: failure on B→G2 forces rerouting."""
        spec = build_d6_multigoal_star()
        result = run_domain(spec, max_cycles=50)
        assert result.goal_reached

    def test_d10_closed_fails(self):
        """D10 bottleneck: closed system hits dead end forever."""
        spec = build_d10_bottleneck()
        result = run_domain_closed(spec, max_cycles=50)
        assert not result.goal_reached

    def test_d10_coupled_escapes(self):
        """D10 bottleneck: failure on S→X teaches avoidance."""
        spec = build_d10_bottleneck()
        result = run_domain(spec, max_cycles=50)
        assert result.goal_reached


# ══════════════════════════════════════════════
# Shallow trap tests — coupling not necessary
# ══════════════════════════════════════════════

class TestShallowTraps:
    """Domains where revisit penalty alone is sufficient."""

    def test_d4_closed_still_escapes(self):
        """D4 greedy trap: revisit penalty breaks 2-cycle."""
        spec = build_d4_greedy_trap()
        result = run_domain_closed(spec, max_cycles=50)
        assert result.goal_reached

    def test_d7_closed_still_reaches_goal(self):
        """D7 invoice: closed system navigates process graph."""
        spec = build_d7_invoice()
        result = run_domain_closed(spec, max_cycles=50)
        assert result.goal_reached

    def test_d8_closed_still_reaches_goal(self):
        """D8 nested cycles: closed system finds exit."""
        spec = build_d8_nested_cycles()
        result = run_domain_closed(spec, max_cycles=50)
        assert result.goal_reached


# ══════════════════════════════════════════════
# No-trap domains — coupling irrelevant
# ══════════════════════════════════════════════

class TestNoTraps:
    """Domains without traps — closed = coupled."""

    @pytest.mark.parametrize("builder,name", [
        (build_d1_linear_chain, "D1"),
        (build_d2_diamond, "D2"),
        (build_d5_grid_detour, "D5"),
        (build_d9_wide_dag, "D9"),
    ])
    def test_closed_equals_coupled(self, builder, name):
        """No-trap domains reach goal with same step count."""
        spec_closed = builder()
        spec_coupled = builder()
        r_closed = run_domain_closed(spec_closed, max_cycles=50)
        r_coupled = run_domain(spec_coupled, max_cycles=50)
        assert r_closed.goal_reached
        assert r_coupled.goal_reached
        assert r_closed.steps == r_coupled.steps


# ══════════════════════════════════════════════
# Structural property tests
# ══════════════════════════════════════════════

class TestStructuralProperties:
    """Invariants about the coupling experiment."""

    def test_failure_edge_detection(self):
        """Failure edges are correctly detected."""
        assert not _has_failure_edges(build_d1_linear_chain())
        assert not _has_failure_edges(build_d4_greedy_trap())
        assert _has_failure_edges(build_d3_gordian_trap())
        assert _has_failure_edges(build_d10_bottleneck())

    def test_rebuild_preserves_topology(self):
        """Rebuilt landscape has same topology as original."""
        spec = build_d3_gordian_trap()
        rebuilt = _rebuild_landscape(spec)
        assert rebuilt._states == spec.landscape._states
        assert set(rebuilt._delta.keys()) == set(spec.landscape._delta.keys())
        for e in spec.landscape._delta:
            assert rebuilt._delta[e] == spec.landscape._delta[e]

    def test_closed_system_reinforces_loops(self):
        """In a closed system, historization makes traversed edges cheaper."""
        spec = build_d3_gordian_trap()
        from e0_controller.controller import E0Controller
        ctrl = E0Controller(spec.landscape, _all_success, alpha=2.0, recent_k=3)

        # Get initial R_eff for S→A
        r_before = ctrl._effective_resistance("S", "A")

        # Execute S→A with SUCCESS
        from e0_controller.primitives import Edge
        spec.landscape.historization.update(Edge("S", "A"), Outcome.SUCCESS)

        r_after = ctrl._effective_resistance("S", "A")
        # SUCCESS should decrease effective resistance
        assert r_after < r_before

    def test_failure_increases_resistance(self):
        """FAILURE outcome increases effective resistance."""
        spec = build_d3_gordian_trap()
        from e0_controller.controller import E0Controller
        ctrl = E0Controller(spec.landscape, _all_success, alpha=2.0, recent_k=3)

        r_before = ctrl._effective_resistance("S", "A")

        from e0_controller.primitives import Edge
        spec.landscape.historization.update(Edge("S", "A"), Outcome.FAILURE)

        r_after = ctrl._effective_resistance("S", "A")
        # FAILURE should increase effective resistance
        assert r_after > r_before

    def test_historization_asymmetry(self):
        """After equal SUCCESS and FAILURE, net effect is positive δ_H.

        This is the caution principle: λ_f > λ_s.
        """
        spec = build_d3_gordian_trap()
        from e0_controller.primitives import Edge
        edge = Edge("S", "A")

        # One success, one failure
        spec.landscape.historization.update(edge, Outcome.SUCCESS)
        spec.landscape.historization.update(edge, Outcome.FAILURE)

        dh = spec.landscape.historization.delta_H(edge)
        # λ_f (0.20) > λ_s (0.15) → net positive → resistance increases
        assert dh > 0
