"""
E₀ Scaling Tests (Phase 3q)
============================
Verify that core E₀ operations scale gracefully with graph size.

Tests synthetic landscapes of 50, 100, and 500 states, measuring:
  - Landscape construction time
  - Controller run time (greedy mode)
  - Amplitude overlay computation time (single-state analysis)
  - Path enumeration / path count behavior
  - No exponential blowup in bounded-horizon analysis

All tests are deterministic (no LLM, no API).

Run:
    python -m unittest e0_controller.test_scaling -v
"""

from __future__ import annotations

import math
import random
import time
import unittest

from e0_controller.landscape import Landscape
from e0_controller.primitives import Outcome
from e0_controller.controller import E0Controller, HybridMode
from e0_controller.amplitude_overlay import analyze_controller_state
from e0_controller.graph_validation import graph_quality


# ──────────────────────────────────────────────
# Synthetic Landscape Builder
# ──────────────────────────────────────────────

def build_chain_landscape(n: int, seed: int = 42) -> Landscape:
    """
    Build a linear-chain landscape with ``n`` states and random shortcuts.

    Structure:
        S_0 → S_1 → ... → S_{n-1}   (backbone: chain edges)
        + ~n/3 random forward shortcuts (S_i → S_j where j > i+1)
        + ~n/10 backward edges (S_j → S_i where j > i) for loops

    The first state is START, the last is GOAL.
    """
    rng = random.Random(seed)
    L = Landscape()

    states = [f"S_{i}" for i in range(n)]
    states[0] = "START"
    states[-1] = "GOAL"

    for s in states:
        L.add_state(s)

    # Backbone edges
    for i in range(n - 1):
        delta = round(rng.uniform(0.2, 0.7), 3)
        resistance = round(rng.uniform(0.3, 1.5), 3)
        L.add_edge(states[i], states[i + 1], delta, resistance)

    # Forward shortcuts (~n/3)
    for _ in range(n // 3):
        i = rng.randint(0, n - 3)
        j = rng.randint(i + 2, n - 1)
        delta = round(rng.uniform(0.3, 0.8), 3)
        resistance = round(rng.uniform(0.5, 2.0), 3)
        L.add_edge(states[i], states[j], delta, resistance)

    # Backward edges (~n/20) — E0-canonical: Δ proportional to hop distance.
    # Going backward S_j → S_i means undoing (j-i) forward transitions,
    # so Δ ≈ hop_distance × avg_forward_delta. This makes backward edges
    # naturally expensive — which is structurally correct. A cheap backward
    # edge would violate the canon (low Δ = low difference, but going
    # backward INCREASES structural distance to GOAL).
    for _ in range(n // 20):
        j = rng.randint(n // 2, n - 1)          # only from second half
        i = rng.randint(max(0, j - 5), j - 1)   # short backward hop
        hop = j - i
        delta = round(hop * rng.uniform(0.3, 0.5), 3)  # E0: Δ ~ hop distance
        resistance = round(rng.uniform(1.5, 3.0), 3)
        L.add_edge(states[j], states[i], delta, resistance)

    return L


def always_success(source: str, target: str) -> Outcome:
    return Outcome.SUCCESS


def make_structural_evaluate(n: int):
    """
    Pure-E0 structural evaluation for chain graphs.

    SUCCESS iff the transition moves toward GOAL (higher index).
    FAILURE iff it regresses (lower index).

    This is canonical E0: historization receives both signals,
    forward paths get reinforced, backward paths get penalized.
    Without this, always_success turns historization into blind
    reinforcement — which is not E0.
    """
    def _index(state: str) -> int:
        if state == "START":
            return 0
        if state == "GOAL":
            return n - 1
        return int(state.split("_")[1])

    def evaluate(source: str, target: str) -> Outcome:
        return Outcome.SUCCESS if _index(target) > _index(source) else Outcome.FAILURE

    return evaluate


# ──────────────────────────────────────────────
# Test Class 1: Construction & Graph Quality
# ──────────────────────────────────────────────

class TestScalingConstruction(unittest.TestCase):
    """Landscape construction and graph quality at scale."""

    SIZES = [50, 100, 500]

    def test_construction_completes(self):
        """All landscape sizes build without error."""
        for n in self.SIZES:
            with self.subTest(n=n):
                L = build_chain_landscape(n)
                self.assertEqual(len(L.states), n)
                self.assertGreater(L.edge_count(), n - 1)

    def test_goal_reachable_at_all_sizes(self):
        """Goal is reachable from START for every size."""
        for n in self.SIZES:
            with self.subTest(n=n):
                L = build_chain_landscape(n)
                gq = graph_quality(L, "START", "GOAL")
                self.assertTrue(gq.reachable, f"Goal not reachable at n={n}")

    def test_happy_path_exists(self):
        """A happy path exists at every size."""
        for n in self.SIZES:
            with self.subTest(n=n):
                L = build_chain_landscape(n)
                gq = graph_quality(L, "START", "GOAL")
                self.assertIsNotNone(gq.happy_path)

    def test_happy_path_shorter_than_chain(self):
        """Happy path is shorter than the full chain (shortcuts exist)."""
        for n in self.SIZES:
            with self.subTest(n=n):
                L = build_chain_landscape(n)
                gq = graph_quality(L, "START", "GOAL")
                # Backbone is n-1 edges; shortcuts should reduce this
                self.assertLess(gq.happy_path_length, n - 1)


# ──────────────────────────────────────────────
# Test Class 2: Controller Run Scaling
# ──────────────────────────────────────────────

class TestScalingControllerRun(unittest.TestCase):
    """Controller run behavior at different graph sizes."""

    SIZES = [50, 100, 500]

    def test_greedy_reaches_goal(self):
        """Greedy controller reaches GOAL at every size (pure E0 evaluation)."""
        for n in self.SIZES:
            with self.subTest(n=n):
                L = build_chain_landscape(n)
                evaluate = make_structural_evaluate(n)
                ctrl = E0Controller(L, evaluate)
                trace = ctrl.run(start="START", goal="GOAL", max_cycles=n * 3)
                self.assertEqual(trace.path[-1], "GOAL",
                                 f"Did not reach GOAL at n={n}. "
                                 f"Ended at {trace.path[-1]}")

    def test_run_time_subquadratic(self):
        """Run time grows sub-quadratically (no combinatorial explosion)."""
        times = {}
        for n in self.SIZES:
            L = build_chain_landscape(n)
            evaluate = make_structural_evaluate(n)
            ctrl = E0Controller(L, evaluate)
            t0 = time.perf_counter()
            ctrl.run(start="START", goal="GOAL", max_cycles=n * 3)
            times[n] = time.perf_counter() - t0

        # Heuristic: time for n=500 should be < 50× time for n=50
        # (quadratic would be 100×, linear would be 10×)
        if times[50] > 0:
            ratio = times[500] / times[50]
            self.assertLess(ratio, 50,
                            f"500/50 time ratio = {ratio:.1f}× — "
                            f"suggests super-linear blowup")

    def test_step_count_bounded(self):
        """Step count stays within O(n) for chain graphs."""
        for n in self.SIZES:
            with self.subTest(n=n):
                L = build_chain_landscape(n)
                evaluate = make_structural_evaluate(n)
                ctrl = E0Controller(L, evaluate)
                trace = ctrl.run(start="START", goal="GOAL", max_cycles=n * 3)
                metrics = trace.metrics()
                steps = int(metrics["steps"])
                # Steps should be proportional to n, not n²
                self.assertLess(steps, n * 3,
                                f"Steps={steps} at n={n} — excessive")


# ──────────────────────────────────────────────
# Test Class 3: Amplitude Overlay Scaling
# ──────────────────────────────────────────────

class TestScalingAmplitudeOverlay(unittest.TestCase):
    """Amplitude overlay computation stays bounded at scale."""

    def _build_controller(self, n: int) -> E0Controller:
        L = build_chain_landscape(n)
        return E0Controller(L, always_success)

    def test_overlay_at_start_bounded(self):
        """analyze_controller_state with small horizon is fast even at n=500."""
        for n in [50, 100, 500]:
            with self.subTest(n=n):
                ctrl = self._build_controller(n)
                t0 = time.perf_counter()
                report = analyze_controller_state(
                    ctrl, "START", horizon_edges=3, geometry="simple"
                )
                elapsed = time.perf_counter() - t0
                # Should complete in < 5 seconds even on slow machines
                self.assertLess(elapsed, 5.0,
                                f"Overlay took {elapsed:.2f}s at n={n}")
                # Sanity: at least 1 action analyzed
                self.assertGreater(len(report.action_infos), 0)

    def test_path_count_bounded_by_horizon(self):
        """Path count does not explode with graph size at fixed horizon."""
        counts = {}
        for n in [50, 100, 500]:
            ctrl = self._build_controller(n)
            report = analyze_controller_state(
                ctrl, "START", horizon_edges=3, geometry="simple"
            )
            total_paths = sum(a.path_count for a in report.action_infos)
            counts[n] = total_paths

        # With bounded horizon + simple geometry (no revisits),
        # path count is bounded by branching factor, not graph size.
        # At horizon=3, should be < 200 paths regardless of n.
        for n, count in counts.items():
            self.assertLess(count, 200,
                            f"Path explosion at n={n}: {count} paths at h=3")

    def test_prefix_has_more_paths_than_simple(self):
        """Prefix geometry has at least as many paths as simple geometry."""
        ctrl = self._build_controller(100)
        prefix = analyze_controller_state(
            ctrl, "START", horizon_edges=3, geometry="prefix"
        )
        simple = analyze_controller_state(
            ctrl, "START", horizon_edges=3, geometry="simple"
        )
        p_paths = sum(a.path_count for a in prefix.action_infos)
        s_paths = sum(a.path_count for a in simple.action_infos)
        self.assertGreaterEqual(p_paths, s_paths)

    def test_overlay_at_mid_graph(self):
        """Overlay at a mid-chain node also completes quickly."""
        ctrl = self._build_controller(500)
        # Run a few steps to get to a mid-point
        trace = ctrl.run(start="START", goal="GOAL", max_cycles=10)
        mid_state = trace.path[min(5, len(trace.path) - 1)]
        t0 = time.perf_counter()
        report = analyze_controller_state(
            ctrl, mid_state, horizon_edges=3, geometry="simple"
        )
        elapsed = time.perf_counter() - t0
        self.assertLess(elapsed, 5.0,
                        f"Mid-graph overlay took {elapsed:.2f}s")


# ──────────────────────────────────────────────
# Test Class 4: Hybrid Mode at Scale
# ──────────────────────────────────────────────

class TestScalingHybrid(unittest.TestCase):
    """Hybrid controller works correctly at larger scales."""

    def test_hybrid_reaches_goal_at_100(self):
        """Hybrid controller reaches GOAL on 100-state graph (pure E0)."""
        L = build_chain_landscape(100)
        ctrl = E0Controller(
            L, make_structural_evaluate(100),
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=3,
            hybrid_goals={"GOAL"},
        )
        trace = ctrl.run(start="START", goal="GOAL", max_cycles=300)
        self.assertEqual(trace.path[-1], "GOAL")

    def test_hybrid_has_overlay_data_at_scale(self):
        """Hybrid produces overlay data on 100-state graph."""
        L = build_chain_landscape(100)
        ctrl = E0Controller(
            L, make_structural_evaluate(100),
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=3,
            hybrid_goals={"GOAL"},
        )
        trace = ctrl.run(start="START", goal="GOAL", max_cycles=300)
        overlay_count = sum(1 for s in trace.steps if s.overlay is not None)
        self.assertGreater(overlay_count, 0)

    def test_hybrid_runtime_reasonable(self):
        """Hybrid on 100-state graph completes in < 60 seconds."""
        L = build_chain_landscape(100)
        ctrl = E0Controller(
            L, make_structural_evaluate(100),
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=3,
            hybrid_goals={"GOAL"},
        )
        t0 = time.perf_counter()
        trace = ctrl.run(start="START", goal="GOAL", max_cycles=300)
        elapsed = time.perf_counter() - t0
        self.assertLess(elapsed, 60.0,
                        f"Hybrid run took {elapsed:.1f}s on n=100")


if __name__ == "__main__":
    unittest.main()
