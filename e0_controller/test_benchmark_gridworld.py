"""
Tests for Grid World Benchmark (C64)
======================================
Formalizes the baseline comparison: E₀ vs Naive-Greedy vs A*.

The gridworld benchmark is the first formal comparison of E₀ against
established baselines (A* optimal, memoryless greedy) on identical
topologies. Three 5×5 grid variants with walls, dead-ends, and trap
loops systematically test whether historization-based navigation
outperforms memoryless local selection.

Key structural claims tested:
  1. A* finds optimal paths in all variants (sanity check)
  2. Naive greedy fails ALL trap/detour/dead-end variants (0% success)
  3. E₀ greedy reaches goal in ALL variants (100% success)
  4. E₀ matches A* optimal in V3 (trap loop — historization breaks cycle)
  5. E₀ step counts are bounded (≤ 2× A* optimal)
  6. Grid construction produces valid E₀ landscapes
  7. Benchmark runner produces consistent, reproducible results
"""

import pytest

from e0_controller.benchmark_gridworld import (
    VARIANTS,
    BenchmarkResult,
    astar,
    build_v1_detour_wall,
    build_v2_deadend_lure,
    build_v3_trap_loop,
    e0_greedy_run,
    naive_greedy_run,
    run_benchmark,
    _build_grid,
    _cell,
    _manhattan,
    _parse_cell,
)
from e0_controller.primitives import Edge


# ══════════════════════════════════════════════
# 1. Grid Construction Tests
# ══════════════════════════════════════════════

class TestGridConstruction:
    """Grid landscapes are structurally valid E₀ landscapes."""

    def test_cell_naming(self):
        assert _cell(0, 0) == "R0C0"
        assert _cell(4, 4) == "R4C4"

    def test_parse_cell_roundtrip(self):
        for r in range(5):
            for c in range(5):
                assert _parse_cell(_cell(r, c)) == (r, c)

    def test_manhattan_distance(self):
        assert _manhattan(0, 0, 4, 4) == 8
        assert _manhattan(2, 3, 2, 3) == 0
        assert _manhattan(0, 0, 0, 4) == 4

    def test_v1_has_wall_gap(self):
        L, start, goal, goals = build_v1_detour_wall()
        # Wall at col 2, rows 1-4. Gap only at row 0.
        assert L.has_edge(_cell(0, 1), _cell(0, 2)), "Gap at row 0 must exist"
        for r in range(1, 5):
            assert not L.has_edge(_cell(r, 1), _cell(r, 2)), (
                f"Wall at ({r},2) must block edge from ({r},1)")

    def test_v2_has_walls(self):
        L, start, goal, goals = build_v2_deadend_lure()
        assert not L.has_edge(_cell(2, 0), _cell(2, 1)), "Wall at (2,1)"
        assert not L.has_edge(_cell(3, 1), _cell(4, 1)), "Wall at (4,1)"

    def test_v3_has_wall(self):
        L, start, goal, goals = build_v3_trap_loop()
        assert not L.has_edge(_cell(2, 1), _cell(2, 2)), "Wall at (2,2)"
        assert not L.has_edge(_cell(1, 2), _cell(2, 2)), "Wall at (2,2)"

    def test_all_variants_start_goal_valid(self):
        for name, build_fn in VARIANTS.items():
            L, start, goal, goals = build_fn()
            assert start == "R0C0", f"{name}: start must be R0C0"
            assert goal == "R4C4", f"{name}: goal must be R4C4"
            assert goal in goals, f"{name}: goal must be in goal set"

    def test_grid_has_bidirectional_edges(self):
        """Grid cells have edges in both directions (4-connected)."""
        L, _, _, _ = build_v3_trap_loop()
        # Check a non-wall cell pair
        assert L.has_edge(_cell(0, 0), _cell(0, 1))
        assert L.has_edge(_cell(0, 1), _cell(0, 0))

    def test_v2_lure_has_low_delta(self):
        """Dead-end lure cells have lower delta to attract naive greedy."""
        L, _, _, _ = build_v2_deadend_lure()
        # Lure edges should have delta = 0.20
        d = L.difference(_cell(1, 0), _cell(2, 0))
        assert d is not None
        assert d == pytest.approx(0.20, abs=0.01)

    def test_v3_trap_has_low_delta(self):
        """Trap cells have lower delta to attract greedy agents."""
        L, _, _, _ = build_v3_trap_loop()
        d = L.difference(_cell(1, 1), _cell(1, 2))
        assert d is not None
        assert d == pytest.approx(0.18, abs=0.01)


# ══════════════════════════════════════════════
# 2. A* Optimality Tests
# ══════════════════════════════════════════════

class TestAStarBaseline:
    """A* finds optimal paths — the gold standard for comparison."""

    def test_v1_astar_finds_path(self):
        L, start, goal, _ = build_v1_detour_wall()
        path = astar(L, start, goal)
        assert path is not None
        assert path[0] == start
        assert path[-1] == goal

    def test_v1_astar_optimal_length(self):
        L, start, goal, _ = build_v1_detour_wall()
        path = astar(L, start, goal)
        assert len(path) - 1 == 8  # Optimal: 8 steps

    def test_v2_astar_finds_path(self):
        L, start, goal, _ = build_v2_deadend_lure()
        path = astar(L, start, goal)
        assert path is not None
        assert path[-1] == goal

    def test_v2_astar_optimal_length(self):
        L, start, goal, _ = build_v2_deadend_lure()
        path = astar(L, start, goal)
        assert len(path) - 1 == 8

    def test_v3_astar_finds_path(self):
        L, start, goal, _ = build_v3_trap_loop()
        path = astar(L, start, goal)
        assert path is not None
        assert path[-1] == goal

    def test_v3_astar_optimal_length(self):
        L, start, goal, _ = build_v3_trap_loop()
        path = astar(L, start, goal)
        assert len(path) - 1 == 8

    def test_astar_no_path_returns_none(self):
        """A* returns None on disconnected graph."""
        from e0_controller.landscape import Landscape
        L = Landscape()
        L.add_edge("R0C0", "R0C1", delta=1.0, resistance=1.0)
        L.add_edge("R4C3", "R4C4", delta=1.0, resistance=1.0)
        assert astar(L, "R0C0", "R4C4") is None


# ══════════════════════════════════════════════
# 3. Naive Greedy Failure Tests
# ══════════════════════════════════════════════

class TestNaiveGreedyFailure:
    """Naive greedy (no memory) fails on trap topologies."""

    @pytest.fixture(params=["V1_detour_wall", "V2_deadend_lure", "V3_trap_loop"])
    def variant(self, request):
        return request.param

    def test_naive_greedy_fails(self, variant):
        """Memoryless greedy cannot escape traps/detours."""
        L, start, goal, _ = VARIANTS[variant]()
        reached, steps, path = naive_greedy_run(L, start, goal, max_steps=50)
        assert not reached, (
            f"Naive greedy should NOT reach goal in {variant}")

    def test_naive_greedy_gets_stuck(self, variant):
        """Naive greedy uses all available steps (oscillates or cycles)."""
        max_s = 50
        L, start, goal, _ = VARIANTS[variant]()
        reached, steps, path = naive_greedy_run(L, start, goal, max_steps=max_s)
        assert not reached
        assert len(path) == max_s + 1  # start + max_steps moves

    def test_naive_greedy_revisits_states(self, variant):
        """Naive greedy visits the same state more than once (cycling)."""
        L, start, goal, _ = VARIANTS[variant]()
        _, _, path = naive_greedy_run(L, start, goal, max_steps=50)
        assert len(path) > len(set(path)), (
            f"Naive greedy should revisit states in {variant}")


# ══════════════════════════════════════════════
# 4. E₀ Success Tests
# ══════════════════════════════════════════════

class TestE0Success:
    """E₀ controller reaches goal in all trap variants."""

    def test_v1_e0_reaches_goal(self):
        L, start, goal, _ = build_v1_detour_wall()
        reached, steps, path = e0_greedy_run(L, start, goal, max_steps=50)
        assert reached, "E₀ must reach goal in V1 (detour wall)"

    def test_v2_e0_reaches_goal(self):
        L, start, goal, _ = build_v2_deadend_lure()
        reached, steps, path = e0_greedy_run(L, start, goal, max_steps=50)
        assert reached, "E₀ must reach goal in V2 (dead-end lure)"

    def test_v3_e0_reaches_goal(self):
        L, start, goal, _ = build_v3_trap_loop()
        reached, steps, path = e0_greedy_run(L, start, goal, max_steps=50)
        assert reached, "E₀ must reach goal in V3 (trap loop)"

    def test_v1_e0_step_bound(self):
        """E₀ reaches V1 goal within 2× A* optimal."""
        L, start, goal, _ = build_v1_detour_wall()
        _, steps, _ = e0_greedy_run(L, start, goal, max_steps=50)
        assert steps <= 16, f"V1: E₀ took {steps} steps, expected ≤16"

    def test_v2_e0_step_bound(self):
        """E₀ reaches V2 goal within 2× A* optimal."""
        L, start, goal, _ = build_v2_deadend_lure()
        _, steps, _ = e0_greedy_run(L, start, goal, max_steps=50)
        assert steps <= 16, f"V2: E₀ took {steps} steps, expected ≤16"

    def test_v3_e0_matches_astar(self):
        """E₀ matches A* optimal in V3 — historization breaks cycle immediately."""
        L, start, goal, _ = build_v3_trap_loop()
        _, steps, _ = e0_greedy_run(L, start, goal, max_steps=50)
        assert steps == 8, f"V3: E₀ took {steps} steps, expected 8 (A* optimal)"


# ══════════════════════════════════════════════
# 5. Comparative Invariant Tests
# ══════════════════════════════════════════════

class TestComparativeInvariants:
    """Structural invariants across methods."""

    @pytest.fixture(params=list(VARIANTS.keys()))
    def variant_result(self, request):
        name = request.param
        return name, run_benchmark(name, n_trials=5, max_steps=50)

    def test_astar_always_succeeds(self, variant_result):
        name, results = variant_result
        astar_r = [r for r in results if r.method == "A*"][0]
        assert astar_r.success_rate == 1.0

    def test_naive_always_fails(self, variant_result):
        name, results = variant_result
        naive_r = [r for r in results if r.method == "Naive_Greedy"][0]
        assert naive_r.success_rate == 0.0

    def test_e0_always_succeeds(self, variant_result):
        name, results = variant_result
        e0_r = [r for r in results if r.method == "E0_Greedy"][0]
        assert e0_r.success_rate == 1.0

    def test_e0_within_2x_optimal(self, variant_result):
        """E₀ step count is bounded by 2× A* optimal."""
        name, results = variant_result
        astar_r = [r for r in results if r.method == "A*"][0]
        e0_r = [r for r in results if r.method == "E0_Greedy"][0]
        assert e0_r.max_steps <= 2 * astar_r.avg_steps, (
            f"{name}: E₀ max {e0_r.max_steps} > 2×A* {2*astar_r.avg_steps}")


# ══════════════════════════════════════════════
# 6. Benchmark Runner Tests
# ══════════════════════════════════════════════

class TestBenchmarkRunner:
    """The benchmark runner produces valid, complete results."""

    def test_run_benchmark_returns_three_methods(self):
        results = run_benchmark("V1_detour_wall", n_trials=3, max_steps=30)
        methods = {r.method for r in results}
        assert methods == {"A*", "Naive_Greedy", "E0_Greedy"}

    def test_all_variants_registered(self):
        assert set(VARIANTS.keys()) == {
            "V1_detour_wall", "V2_deadend_lure", "V3_trap_loop"}

    def test_benchmark_result_dataclass(self):
        r = BenchmarkResult("test", "method", 10, 8, 5.0, 3, 7)
        assert r.success_rate == 0.8
        assert r.variant == "test"

    def test_benchmark_result_zero_trials(self):
        r = BenchmarkResult("test", "method", 0, 0, 0.0, 0, 0)
        assert r.success_rate == 0.0

    def test_e0_deterministic_across_trials(self):
        """E₀ greedy is deterministic — same result every trial."""
        results = run_benchmark("V3_trap_loop", n_trials=5, max_steps=50)
        e0_r = [r for r in results if r.method == "E0_Greedy"][0]
        assert e0_r.min_steps == e0_r.max_steps, (
            "E₀ greedy should be deterministic (same steps every trial)")
