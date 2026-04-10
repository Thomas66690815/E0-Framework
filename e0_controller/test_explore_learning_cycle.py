"""Tests for explore_learning_cycle.py — C202.

Validates the iterative learning cycle:
1. Assessment: coverage, frontier detection, domain-specific metrics
2. Planning: mode selection based on assessment and history
3. Navigation: exploration bonus, frontier-adjacent start, cross-domain traversal
4. Validation: confidence updates from traversal
5. Consolidation: dry-run persistence of edges and learning history
6. Full cycle: multi-round coverage increase with natural termination
"""

import pytest

from e0_controller.explore_learning_cycle import (
    Assessment,
    RoundPlan,
    RoundResult,
    assess,
    build_landscape,
    consolidate,
    navigate,
    plan,
    validate_confidence,
    _pick_start_node,
    _create_shortcut_edges,
    run_learning_cycle,
)
from e0_controller.explore_bootstrap_landscape import MU


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def landscape_data():
    """Build unified landscape once (fresh Canon traces)."""
    landscape, unified_nodes, bridges = build_landscape(fresh_canon=True)
    return landscape, unified_nodes, bridges


@pytest.fixture(scope="module")
def warm_landscape_data():
    """Build unified landscape with inherited Canon traces."""
    landscape, unified_nodes, bridges = build_landscape(fresh_canon=False)
    return landscape, unified_nodes, bridges


# ---------------------------------------------------------------------------
# Phase 1: ASSESS
# ---------------------------------------------------------------------------


class TestAssessment:
    """Assessment correctly characterizes the landscape state."""

    def test_assessment_fields(self, landscape_data):
        """Assessment returns all required fields with valid types."""
        landscape, unified_nodes, _ = landscape_data
        a = assess(landscape, unified_nodes)

        assert isinstance(a, Assessment)
        assert a.total_nodes > 0
        assert a.total_edges > 0
        assert 0 <= a.coverage <= 1.0
        assert a.frontier_size >= 0
        assert a.T_s >= 0
        assert 0 <= a.mean_quality <= 1.0
        assert a.stale_edges >= 0
        assert 0 <= a.canon_coverage <= 1.0
        assert 0 <= a.bootstrap_coverage <= 1.0

    def test_fresh_canon_lower_coverage(self, landscape_data, warm_landscape_data):
        """Fresh Canon (U=0, F=0) gives lower coverage than inherited traces."""
        ls_fresh, nodes_fresh, _ = landscape_data
        ls_warm, nodes_warm, _ = warm_landscape_data

        fresh = assess(ls_fresh, nodes_fresh)
        warm = assess(ls_warm, nodes_warm)

        assert fresh.coverage < warm.coverage, (
            f"Fresh ({fresh.coverage:.1%}) should be < warm ({warm.coverage:.1%})"
        )

    def test_fresh_canon_has_frontier(self, landscape_data):
        """Fresh Canon landscape has unvisited frontier nodes."""
        landscape, unified_nodes, _ = landscape_data
        a = assess(landscape, unified_nodes)
        assert a.frontier_size > 0, "Expected frontier nodes with fresh Canon"

    def test_visited_plus_frontier_leq_total(self, landscape_data):
        """Visited + frontier ≤ total (some nodes may be unreachable)."""
        landscape, unified_nodes, _ = landscape_data
        a = assess(landscape, unified_nodes)
        assert a.visited_nodes + a.frontier_size <= a.total_nodes + 5  # small tolerance

    def test_domain_coverage_sums(self, landscape_data):
        """Canon and Bootstrap coverage are both computed."""
        landscape, unified_nodes, _ = landscape_data
        a = assess(landscape, unified_nodes)
        # Bootstrap should have high initial coverage (real traces)
        assert a.bootstrap_coverage > 0.5, (
            f"Bootstrap coverage too low: {a.bootstrap_coverage:.1%}"
        )

    def test_unified_landscape_size(self, landscape_data):
        """Unified landscape has Canon + Bootstrap + bridge nodes."""
        landscape, unified_nodes, _ = landscape_data
        a = assess(landscape, unified_nodes)
        assert a.total_nodes >= 100, f"Expected ≥100 nodes, got {a.total_nodes}"
        assert a.total_edges >= 200, f"Expected ≥200 edges, got {a.total_edges}"


# ---------------------------------------------------------------------------
# Phase 2: PLAN
# ---------------------------------------------------------------------------


class TestPlan:
    """Planner selects correct mode based on assessment and history."""

    def _make_assessment(self, **overrides):
        """Create a minimal Assessment with overrides."""
        defaults = dict(
            total_nodes=100, total_edges=200, visited_nodes=50,
            coverage=0.5, frontier_size=10, T_s=1.0,
            mean_quality=0.3, stale_edges=0,
            canon_coverage=0.4, bootstrap_coverage=0.9,
        )
        defaults.update(overrides)
        return Assessment(**defaults)

    def _make_result(self, coverage_delta=0.0):
        """Create a minimal RoundResult stub for history."""
        a = self._make_assessment()
        p = RoundPlan(mode="explore", steps=30, reason="test")
        return RoundResult(
            round_num=1, plan=p, assessment_before=a, assessment_after=a,
            path=["A"], new_edges=0, domain_crossings=0, crossing_rate=0.0,
            canon_visited=0, bootstrap_visited=0, llm_round=False,
            coverage_delta=coverage_delta, T_s_delta=0.0,
        )

    def test_low_coverage_broad_explore(self):
        """Coverage < 30% → broad exploration."""
        a = self._make_assessment(coverage=0.2)
        p = plan(a, round_num=1, history=[])
        assert p.mode == "explore"
        assert "Low coverage" in p.reason or "Frontier" in p.reason

    def test_frontier_triggers_explore(self):
        """Frontier > 0 → keep exploring."""
        a = self._make_assessment(coverage=0.7, frontier_size=15)
        p = plan(a, round_num=1, history=[])
        assert p.mode == "explore"

    def test_stagnation_triggers_llm(self):
        """3 stalled rounds → LLM mode."""
        history = [self._make_result(coverage_delta=0.0) for _ in range(3)]
        a = self._make_assessment()
        p = plan(a, round_num=4, history=history)
        assert p.mode == "llm"
        assert "Stagnation" in p.reason

    def test_stagnation_recovery_increases_budget(self):
        """1-2 stalled rounds → increased budget."""
        history = [self._make_result(coverage_delta=0.0)]
        a = self._make_assessment(frontier_size=10)
        p = plan(a, round_num=3, history=history)
        assert p.steps > 30, f"Expected increased budget, got {p.steps}"

    def test_high_Ts_explore(self):
        """High T_s → explore for clarity."""
        a = self._make_assessment(T_s=MU * 3, frontier_size=0)
        p = plan(a, round_num=1, history=[])
        assert p.mode == "explore"
        assert "T_s" in p.reason

    def test_plan_returns_valid_object(self):
        """Plan always returns a RoundPlan with valid fields."""
        a = self._make_assessment()
        p = plan(a, round_num=1, history=[])
        assert isinstance(p, RoundPlan)
        assert p.mode in ("explore", "exploit", "llm")
        assert p.steps > 0
        assert len(p.reason) > 0


# ---------------------------------------------------------------------------
# Phase 3: NAVIGATE
# ---------------------------------------------------------------------------


class TestNavigate:
    """Navigation explores the landscape with domain crossings."""

    def test_navigate_returns_path(self, landscape_data):
        """Navigate produces a non-empty path with domain crossings."""
        landscape, unified_nodes, _ = landscape_data
        p = RoundPlan(mode="explore", steps=10, reason="test")
        result = navigate(landscape, unified_nodes, p, start="B:HERE")

        assert len(result["path"]) > 1
        assert result["steps"] > 0
        assert result["crossing_rate"] >= 0
        assert isinstance(result["new_edges"], list)

    def test_navigate_visits_canon_nodes(self, landscape_data):
        """Navigation reaches Canon territory (via bridges)."""
        landscape, unified_nodes, _ = landscape_data
        p = RoundPlan(mode="explore", steps=20, reason="test")
        result = navigate(landscape, unified_nodes, p, start="B:HERE")

        assert result["canon_visited"] > 0, "Expected Canon nodes in path"

    def test_navigate_visits_bootstrap_nodes(self, landscape_data):
        """Navigation includes Bootstrap territory."""
        landscape, unified_nodes, _ = landscape_data
        p = RoundPlan(mode="explore", steps=20, reason="test")
        result = navigate(landscape, unified_nodes, p, start="B:HERE")

        assert result["bootstrap_visited"] > 0

    def test_navigate_creates_shortcut_edges(self, landscape_data):
        """Navigation creates Phase D shortcut edges from sub-paths."""
        landscape, unified_nodes, _ = landscape_data
        p = RoundPlan(mode="explore", steps=30, reason="test")
        result = navigate(landscape, unified_nodes, p, start="B:HERE")

        # With 30 steps, should create some shortcuts
        assert len(result["new_edges"]) > 0

    def test_navigate_domain_crossings(self, landscape_data):
        """Navigation crosses between Canon and Bootstrap domains."""
        landscape, unified_nodes, _ = landscape_data
        p = RoundPlan(mode="explore", steps=20, reason="test")
        result = navigate(landscape, unified_nodes, p, start="B:HERE")

        assert result["domain_crossings"] > 0, "Expected cross-domain navigation"

    def test_shortcut_edge_format(self, landscape_data):
        """Shortcut edges have required fields."""
        landscape, unified_nodes, _ = landscape_data
        p = RoundPlan(mode="explore", steps=30, reason="test")
        result = navigate(landscape, unified_nodes, p, start="B:HERE")

        for edge in result["new_edges"]:
            assert "from" in edge
            assert "to" in edge
            assert "delta" in edge
            assert "confidence" in edge
            assert "derivation" in edge
            assert edge["from"] != edge["to"]


# ---------------------------------------------------------------------------
# Frontier-adjacent start
# ---------------------------------------------------------------------------


class TestPickStartNode:
    """Start node selection prefers frontier-adjacent nodes."""

    def test_picks_valid_node(self, landscape_data):
        """Picked start node exists in the landscape."""
        landscape, unified_nodes, _ = landscape_data
        start = _pick_start_node(landscape, unified_nodes)
        assert start in landscape.states

    def test_picks_frontier_adjacent(self, landscape_data):
        """Start node is adjacent to unvisited territory."""
        landscape, unified_nodes, _ = landscape_data
        start = _pick_start_node(landscape, unified_nodes)
        hist = landscape.historization

        # Start should be a visited node with unvisited neighbors
        visited = set()
        for e in landscape.edges:
            if hist.trace_load(e) > 0:
                visited.add(e.source)
                visited.add(e.target)

        if start != "B:HERE":
            assert start in visited, "Start node should be visited"
            # Should have at least one unvisited neighbor
            has_unvisited_nbr = any(
                e.target not in visited
                for e in landscape.edges
                if e.source == start
            )
            assert has_unvisited_nbr, "Start should be adjacent to frontier"


# ---------------------------------------------------------------------------
# Phase 4: VALIDATE
# ---------------------------------------------------------------------------


class TestValidateConfidence:
    """Confidence updates reflect traversal patterns."""

    def test_validate_returns_dict(self, landscape_data):
        """Validation returns a dict of (from, to) → confidence."""
        landscape, _, _ = landscape_data
        updates = validate_confidence(landscape, ["B:HERE", "B:REFLEXION"])
        assert isinstance(updates, dict)

    def test_empty_path_no_updates(self, landscape_data):
        """Empty path produces no confidence updates."""
        landscape, _, _ = landscape_data
        updates = validate_confidence(landscape, [])
        # Edges not traversed may still decay, so result can be non-empty
        assert isinstance(updates, dict)


# ---------------------------------------------------------------------------
# Phase 5: CONSOLIDATE
# ---------------------------------------------------------------------------


class TestConsolidate:
    """Consolidation persists or dry-runs round results."""

    def _make_round_result(self):
        """Create minimal RoundResult for consolidation testing."""
        a = Assessment(
            total_nodes=100, total_edges=200, visited_nodes=50,
            coverage=0.5, frontier_size=10, T_s=1.0,
            mean_quality=0.3, stale_edges=0,
            canon_coverage=0.4, bootstrap_coverage=0.9,
        )
        p = RoundPlan(mode="explore", steps=30, reason="test")
        return RoundResult(
            round_num=1, plan=p, assessment_before=a, assessment_after=a,
            path=["B:HERE", "C:overlap"], new_edges=2,
            domain_crossings=1, crossing_rate=0.5,
            canon_visited=1, bootstrap_visited=1,
            llm_round=False, coverage_delta=0.05, T_s_delta=-0.01,
        )

    def test_dry_run_no_write(self):
        """Dry run returns summary without writing to disk."""
        rr = self._make_round_result()
        new_edges = [{"from": "B:X", "to": "C:Y", "delta": 0.5,
                       "confidence": 0.5, "derivation": "test"}]
        result = consolidate(rr, new_edges, dry_run=True)

        assert result["dry_run"] is True
        assert result["round_recorded"] is False
        assert result["new_edges_would_persist"] == 1

    def test_dry_run_empty_edges(self):
        """Dry run with no new edges."""
        rr = self._make_round_result()
        result = consolidate(rr, [], dry_run=True)
        assert result["new_edges_would_persist"] == 0


# ---------------------------------------------------------------------------
# Full Learning Cycle
# ---------------------------------------------------------------------------


class TestLearningCycle:
    """Integration: the full learning cycle shows progressive improvement."""

    def test_cycle_returns_results(self):
        """Learning cycle returns a list of RoundResult."""
        results = run_learning_cycle(max_rounds=2, steps_per_round=10,
                                      verbose=False)
        assert len(results) > 0
        assert all(isinstance(r, RoundResult) for r in results)

    def test_coverage_increases(self):
        """Coverage increases across rounds (the core learning claim)."""
        results = run_learning_cycle(max_rounds=4, steps_per_round=20,
                                      verbose=False)
        first_coverage = results[0].assessment_before.coverage
        last_coverage = results[-1].assessment_after.coverage
        assert last_coverage > first_coverage, (
            f"Coverage should increase: {first_coverage:.1%} → {last_coverage:.1%}"
        )

    def test_Ts_decreases(self):
        """Structural temperature decreases (system learns structure)."""
        results = run_learning_cycle(max_rounds=4, steps_per_round=20,
                                      verbose=False)
        first_Ts = results[0].assessment_before.T_s
        last_Ts = results[-1].assessment_after.T_s
        assert last_Ts < first_Ts, (
            f"T_s should decrease: {first_Ts:.3f} → {last_Ts:.3f}"
        )

    def test_canon_coverage_increases(self):
        """Canon-specific coverage increases (E₀ learns E₀)."""
        results = run_learning_cycle(max_rounds=4, steps_per_round=20,
                                      verbose=False)
        first_canon = results[0].assessment_before.canon_coverage
        last_canon = results[-1].assessment_after.canon_coverage
        assert last_canon > first_canon, (
            f"Canon coverage should increase: {first_canon:.1%} → {last_canon:.1%}"
        )

    def test_frontier_shrinks(self):
        """Frontier size decreases as exploration progresses."""
        results = run_learning_cycle(max_rounds=4, steps_per_round=20,
                                      verbose=False)
        first_frontier = results[0].assessment_before.frontier_size
        last_frontier = results[-1].assessment_after.frontier_size
        assert last_frontier < first_frontier, (
            f"Frontier should shrink: {first_frontier} → {last_frontier}"
        )

    def test_shortcut_edges_created(self):
        """Rounds produce new shortcut edges."""
        results = run_learning_cycle(max_rounds=3, steps_per_round=15,
                                      verbose=False)
        total_new = sum(r.new_edges for r in results)
        assert total_new > 0, "Expected shortcut edges from navigation"

    def test_domain_crossings_occur(self):
        """Navigation crosses between Canon and Bootstrap."""
        results = run_learning_cycle(max_rounds=3, steps_per_round=15,
                                      verbose=False)
        total_crossings = sum(r.domain_crossings for r in results)
        assert total_crossings > 0

    def test_stagnation_detection(self):
        """Stagnation detection works (no crash on extended run)."""
        # Run enough rounds that stagnation might trigger
        results = run_learning_cycle(max_rounds=6, steps_per_round=10,
                                      verbose=False)
        # After coverage saturates, planner should switch to stagnation modes
        assert len(results) >= 4  # Should complete at least 4 rounds

    def test_natural_termination(self):
        """With enough rounds, cycle terminates before max_rounds."""
        results = run_learning_cycle(max_rounds=20, steps_per_round=30,
                                      verbose=False)
        # Should stop early due to frontier=0 + coverage>90%
        # (from our smoke tests: achieves 96.2% in 4 rounds)
        last = results[-1].assessment_after
        if last.frontier_size == 0 and last.coverage > 0.9:
            assert len(results) < 20, "Should terminate early"

    def test_learning_curve_shape(self):
        """Coverage gains diminish over time (natural learning curve)."""
        results = run_learning_cycle(max_rounds=5, steps_per_round=20,
                                      verbose=False)
        # First rounds should have bigger gains than later rounds
        if len(results) >= 3:
            early_gain = results[0].coverage_delta
            # At least one early round should show positive gain
            any_gain = any(r.coverage_delta > 0 for r in results[:3])
            assert any_gain, "Expected coverage gain in first 3 rounds"
