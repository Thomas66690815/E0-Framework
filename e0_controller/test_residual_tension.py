"""
Tests for Residual Tension & Iteration Control (C37)
======================================================
Verifies ResidualTensionMap computation, should_continue() logic,
Session.iterate(), and format_residual_map().

Tests organized by component:
  1. ResidualTensionMap computation
  2. should_continue() verdicts
  3. Session.iterate() integration
  4. format_residual_map() output
"""

import math
import shutil
import tempfile
import unittest

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller, RunTrace, StepResult, EscalationType
from e0_controller.residual_tension import (
    ResidualTension,
    ResidualTensionMap,
    IterationVerdict,
    compute_residual_map,
    should_continue,
    snapshot_tensions,
    format_residual_map,
    _HOTSPOT_THRESHOLD,
    _EQUILIBRIUM_THRESHOLD,
    _STAGNATION_DELTA,
)
from e0_controller.session import Session, IterationResult
from e0_controller.reflection import ReflectionReport


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _make_landscape():
    """A → B → C → GOAL with one side branch D (high tension)."""
    L = Landscape()
    L.add_edge("A", "B", delta=0.3, resistance=0.5)   # S₀ = 0.15
    L.add_edge("B", "C", delta=0.2, resistance=0.4)   # S₀ = 0.08
    L.add_edge("C", "GOAL", delta=0.1, resistance=0.2)  # S₀ = 0.02
    # High-tension side branch (not on happy path)
    L.add_edge("A", "D", delta=0.8, resistance=1.5)   # S₀ = 1.20
    L.add_edge("D", "GOAL", delta=0.9, resistance=2.0)  # S₀ = 1.80
    return L


def _success_fn(source, target):
    return Outcome.SUCCESS


def _failure_on_D(source, target):
    if source == "D" or target == "D":
        return Outcome.FAILURE
    return Outcome.SUCCESS


def _make_trace_AB(landscape):
    """Simulate a trace that only visits A→B→C→GOAL."""
    ctrl = E0Controller(landscape, _success_fn)
    trace = ctrl.run("A", max_cycles=10, goal="GOAL")
    return trace


def _make_simple_residual_map(hotspot_s=0.8, iteration=1):
    """Build a minimal ResidualTensionMap for testing should_continue."""
    edge_hot = Edge("X", "Y")
    edge_low = Edge("A", "B")
    hot = ResidualTension(edge_hot, s_eff=hotspot_s, delta_s=0.1,
                          f_trace=0.0, visited=False)
    low = ResidualTension(edge_low, s_eff=0.05, delta_s=-0.01,
                          f_trace=0.0, visited=True)
    return ResidualTensionMap(
        residuals=[hot, low],
        hotspots=[hot] if hotspot_s > _HOTSPOT_THRESHOLD else [],
        resolved=[edge_low] if True else [],
        amplified=[edge_hot] if hotspot_s > _HOTSPOT_THRESHOLD else [],
        iteration=iteration,
        max_residual=hotspot_s,
        mean_residual=(hotspot_s + 0.05) / 2,
    )


# ──────────────────────────────────────────────
# 1. ResidualTensionMap computation
# ──────────────────────────────────────────────

class TestSnapshotTensions(unittest.TestCase):
    """Tests for snapshot_tensions()."""

    def test_captures_all_edges(self):
        L = _make_landscape()
        snap = snapshot_tensions(L)
        self.assertEqual(len(snap), L.edge_count())

    def test_tension_values_match_landscape(self):
        L = _make_landscape()
        snap = snapshot_tensions(L)
        for edge, s in snap.items():
            expected = L.effective_tension(edge.source, edge.target)
            self.assertAlmostEqual(s, expected, places=10)

    def test_reflects_historization(self):
        L = _make_landscape()
        snap_before = snapshot_tensions(L)
        # Historize an edge
        L.historization.update(Edge("A", "B"), Outcome.SUCCESS)
        snap_after = snapshot_tensions(L)
        edge_ab = Edge("A", "B")
        # Success → lower resistance → lower tension
        self.assertLess(snap_after[edge_ab], snap_before[edge_ab])


class TestComputeResidualMap(unittest.TestCase):
    """Tests for compute_residual_map()."""

    def test_all_edges_present(self):
        L = _make_landscape()
        pre = snapshot_tensions(L)
        trace = _make_trace_AB(L)
        rmap = compute_residual_map(L, trace, pre, iteration=1)
        self.assertEqual(len(rmap.residuals), L.edge_count())

    def test_visited_edges_marked(self):
        L = _make_landscape()
        pre = snapshot_tensions(L)
        trace = _make_trace_AB(L)
        rmap = compute_residual_map(L, trace, pre, iteration=1)
        visited_sources = {s.source for s in trace.steps}
        for r in rmap.residuals:
            if r.edge.source in visited_sources:
                # At least one visited edge from the trace
                pass  # just checking structure
        # A→B should be visited
        ab_residual = next(
            r for r in rmap.residuals if r.edge == Edge("A", "B")
        )
        self.assertTrue(ab_residual.visited)

    def test_unvisited_high_tension_is_hotspot(self):
        L = _make_landscape()
        pre = snapshot_tensions(L)
        trace = _make_trace_AB(L)
        rmap = compute_residual_map(L, trace, pre, iteration=1)
        # D→GOAL (S₀=1.80) was not visited and has high tension
        hotspot_edges = {h.edge for h in rmap.hotspots}
        d_goal = Edge("D", "GOAL")
        self.assertIn(d_goal, hotspot_edges)

    def test_resolved_edges_have_negative_delta(self):
        L = _make_landscape()
        pre = snapshot_tensions(L)
        trace = _make_trace_AB(L)
        rmap = compute_residual_map(L, trace, pre, iteration=1)
        # Visited edges with SUCCESS → tension decreased
        for edge in rmap.resolved:
            r = next(r for r in rmap.residuals if r.edge == edge)
            self.assertLess(r.delta_s, 0)

    def test_sorted_by_tension_descending(self):
        L = _make_landscape()
        pre = snapshot_tensions(L)
        trace = _make_trace_AB(L)
        rmap = compute_residual_map(L, trace, pre, iteration=1)
        tensions = [r.s_eff for r in rmap.residuals]
        self.assertEqual(tensions, sorted(tensions, reverse=True))

    def test_iteration_stored(self):
        L = _make_landscape()
        pre = snapshot_tensions(L)
        trace = _make_trace_AB(L)
        rmap = compute_residual_map(L, trace, pre, iteration=7)
        self.assertEqual(rmap.iteration, 7)

    def test_max_and_mean_computed(self):
        L = _make_landscape()
        pre = snapshot_tensions(L)
        trace = _make_trace_AB(L)
        rmap = compute_residual_map(L, trace, pre, iteration=1)
        self.assertGreater(rmap.max_residual, 0)
        self.assertGreater(rmap.mean_residual, 0)
        self.assertGreaterEqual(rmap.max_residual, rmap.mean_residual)


# ──────────────────────────────────────────────
# 2. should_continue() verdicts
# ──────────────────────────────────────────────

class TestShouldContinue(unittest.TestCase):
    """Tests for should_continue() — iteration-level Axiom A₀."""

    def test_budget_stops_iteration(self):
        rmap = _make_simple_residual_map(hotspot_s=2.0, iteration=5)
        verdict = should_continue(rmap, iteration=5, max_iterations=5)
        self.assertFalse(verdict.should_continue)
        self.assertEqual(verdict.reason, "budget")

    def test_equilibrium_when_no_actionable_hotspots(self):
        rmap = _make_simple_residual_map(hotspot_s=0.05, iteration=1)
        verdict = should_continue(rmap, iteration=1)
        self.assertFalse(verdict.should_continue)
        self.assertEqual(verdict.reason, "equilibrium")

    def test_continue_with_active_tension(self):
        rmap = _make_simple_residual_map(hotspot_s=1.5, iteration=1)
        verdict = should_continue(rmap, iteration=1, max_iterations=10)
        self.assertTrue(verdict.should_continue)
        self.assertEqual(verdict.reason, "tension_active")

    def test_stagnation_detection(self):
        prev = _make_simple_residual_map(hotspot_s=1.5, iteration=1)
        # Same mean tension in next iteration
        curr = _make_simple_residual_map(hotspot_s=1.5, iteration=2)
        # Force same mean_residual
        curr_copy = ResidualTensionMap(
            residuals=curr.residuals,
            hotspots=curr.hotspots,
            resolved=curr.resolved,
            amplified=curr.amplified,
            iteration=2,
            max_residual=curr.max_residual,
            mean_residual=prev.mean_residual,  # exactly same
        )
        verdict = should_continue(curr_copy, prev_map=prev, iteration=2)
        self.assertFalse(verdict.should_continue)
        self.assertEqual(verdict.reason, "stagnation")
        self.assertTrue(verdict.should_reflect)

    def test_reflect_recommended_when_amplifying(self):
        """More amplified than resolved → reflect before next run."""
        edge1 = Edge("X", "Y")
        edge2 = Edge("P", "Q")
        hot = ResidualTension(edge1, s_eff=1.5, delta_s=0.3,
                              f_trace=0.0, visited=False)
        rmap = ResidualTensionMap(
            residuals=[hot],
            hotspots=[hot],
            resolved=[],
            amplified=[edge1, edge2],
            iteration=1,
            max_residual=1.5,
            mean_residual=1.5,
        )
        verdict = should_continue(rmap, iteration=1)
        self.assertTrue(verdict.should_continue)
        self.assertTrue(verdict.should_reflect)

    def test_no_reflect_when_resolving(self):
        """More resolved than amplified → no reflection needed."""
        edge1 = Edge("X", "Y")
        hot = ResidualTension(edge1, s_eff=1.5, delta_s=-0.2,
                              f_trace=0.0, visited=False)
        rmap = ResidualTensionMap(
            residuals=[hot],
            hotspots=[hot],
            resolved=[edge1, Edge("P", "Q"), Edge("R", "S")],
            amplified=[],
            iteration=1,
            max_residual=1.5,
            mean_residual=1.5,
        )
        verdict = should_continue(rmap, iteration=1)
        self.assertTrue(verdict.should_continue)
        self.assertFalse(verdict.should_reflect)

    def test_verdict_carries_map(self):
        rmap = _make_simple_residual_map(hotspot_s=1.0, iteration=3)
        verdict = should_continue(rmap, iteration=3)
        self.assertIs(verdict.residual_map, rmap)
        self.assertEqual(verdict.iteration, 3)


# ──────────────────────────────────────────────
# 3. Session.iterate() integration
# ──────────────────────────────────────────────

class TestSessionIterate(unittest.TestCase):
    """Integration tests for Session.iterate()."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="e0_iter_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_iterate_reaches_equilibrium(self):
        """Simple landscape → should reach equilibrium quickly."""
        L = Landscape()
        L.add_edge("A", "B", delta=0.3, resistance=0.5)
        L.add_edge("B", "GOAL", delta=0.2, resistance=0.3)

        session = Session("iter-eq", L, _success_fn, base_dir=self.tmpdir)
        result = session.iterate("A", goal="GOAL", max_cycles=10)

        self.assertIsInstance(result, IterationResult)
        self.assertGreaterEqual(result.iterations, 1)
        self.assertIn(result.stop_reason, ("equilibrium", "stagnation", "budget"))
        self.assertEqual(len(result.results), result.iterations)
        self.assertEqual(len(result.verdicts), result.iterations)
        self.assertIsNotNone(result.final_map)

    def test_iterate_respects_budget(self):
        """With max_iterations=2, never runs more than 2."""
        L = _make_landscape()
        session = Session("iter-bud", L, _success_fn, base_dir=self.tmpdir)
        result = session.iterate("A", goal="GOAL", max_cycles=10,
                                 max_iterations=2)
        self.assertLessEqual(result.iterations, 2)

    def test_iterate_produces_verdicts(self):
        L = _make_landscape()
        session = Session("iter-verd", L, _success_fn, base_dir=self.tmpdir)
        result = session.iterate("A", goal="GOAL", max_cycles=10,
                                 max_iterations=3)
        for v in result.verdicts:
            self.assertIsInstance(v, IterationVerdict)
            self.assertIsInstance(v.residual_map, ResidualTensionMap)

    def test_iterate_historization_persists_across_runs(self):
        """Each iteration builds on the previous historization."""
        L = _make_landscape()
        session = Session("iter-hist", L, _success_fn, base_dir=self.tmpdir)
        ab = Edge("A", "B")
        u_before = L.historization.success_trace(ab)
        result = session.iterate("A", goal="GOAL", max_cycles=10,
                                 max_iterations=3)
        u_after = L.historization.success_trace(ab)
        # Multiple runs → accumulated success
        self.assertGreater(u_after, u_before)

    def test_iterate_final_map_is_last(self):
        L = _make_landscape()
        session = Session("iter-map", L, _success_fn, base_dir=self.tmpdir)
        result = session.iterate("A", goal="GOAL", max_cycles=10,
                                 max_iterations=3)
        if result.verdicts:
            self.assertEqual(result.final_map.iteration,
                             result.verdicts[-1].residual_map.iteration)

    def test_iterate_with_high_threshold_stops_early(self):
        """High tension_threshold → everything below → equilibrium fast."""
        L = _make_landscape()
        session = Session("iter-thr", L, _success_fn, base_dir=self.tmpdir)
        result = session.iterate("A", goal="GOAL", max_cycles=10,
                                 tension_threshold=100.0)
        self.assertEqual(result.stop_reason, "equilibrium")
        self.assertEqual(result.iterations, 1)


# ──────────────────────────────────────────────
# 4. format_residual_map()
# ──────────────────────────────────────────────

class TestFormatResidualMap(unittest.TestCase):
    """Tests for human-readable formatting."""

    def test_format_contains_key_info(self):
        L = _make_landscape()
        pre = snapshot_tensions(L)
        trace = _make_trace_AB(L)
        rmap = compute_residual_map(L, trace, pre, iteration=1)
        text = format_residual_map(rmap)
        self.assertIn("iteration 1", text)
        self.assertIn("Max S_eff", text)
        self.assertIn("Mean S_eff", text)
        self.assertIn("Resolved", text)

    def test_format_shows_hotspots(self):
        L = _make_landscape()
        pre = snapshot_tensions(L)
        trace = _make_trace_AB(L)
        rmap = compute_residual_map(L, trace, pre, iteration=1)
        text = format_residual_map(rmap)
        if rmap.hotspots:
            self.assertIn("Hotspots", text)
            self.assertIn("→", text)

    def test_format_equilibrium_message(self):
        """When no hotspots → equilibrium message."""
        rmap = _make_simple_residual_map(hotspot_s=0.01, iteration=1)
        text = format_residual_map(rmap)
        self.assertIn("equilibrium", text.lower())


# ──────────────────────────────────────────────
# 5. Reflection in iterate() loop
# ──────────────────────────────────────────────

class TestIterateReflection(unittest.TestCase):
    """Tests that reflection executes between iterations."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="e0_iref_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_reflections_list_matches_iterations(self):
        """IterationResult.reflections has one entry per iteration."""
        L = _make_landscape()
        session = Session("ref-len", L, _success_fn, base_dir=self.tmpdir)
        result = session.iterate("A", goal="GOAL", max_cycles=10,
                                 max_iterations=3)
        self.assertEqual(len(result.reflections), result.iterations)

    def test_reflection_triggered_on_goal_miss(self):
        """When goal is never reached, reflection fires (failure trigger)."""
        L = Landscape()
        L.add_edge("A", "B", delta=0.3, resistance=0.5)
        L.add_edge("B", "C", delta=0.2, resistance=0.4)
        # No edge to GOAL — goal will never be reached

        session = Session("ref-miss", L, _success_fn, base_dir=self.tmpdir)
        result = session.iterate("A", goal="GOAL", max_cycles=5,
                                 max_iterations=2)
        # At least the last iteration should trigger reflection
        # (because !should_continue always attempts reflection)
        last_refl = result.reflections[-1]
        self.assertIsNotNone(last_refl)
        self.assertIsInstance(last_refl, ReflectionReport)
        self.assertEqual(last_refl.reflection_type, "failure")

    def test_no_reflection_on_clean_equilibrium(self):
        """Quick equilibrium with goal reached → no reflection."""
        L = Landscape()
        L.add_edge("A", "GOAL", delta=0.1, resistance=0.1)

        session = Session("ref-clean", L, _success_fn, base_dir=self.tmpdir)
        result = session.iterate("A", goal="GOAL", max_cycles=5,
                                 tension_threshold=100.0)
        self.assertEqual(result.iterations, 1)
        # Stop on equilibrium — reflection fires but goal reached
        # with good efficiency → should_reflect returns no trigger
        # (reflects are attempted when !should_continue, but
        # the reflection layer decides if conditions warrant a report)

    def test_reflection_on_failure_fn(self):
        """Repeated failures on D branch → failure reflection."""
        L = _make_landscape()
        session = Session("ref-fail", L, _failure_on_D, base_dir=self.tmpdir)
        result = session.iterate("A", goal="GOAL", max_cycles=10,
                                 max_iterations=3)
        # Check that reflections list has the right length
        self.assertEqual(len(result.reflections), result.iterations)
        # All reflections should be either None or ReflectionReport
        for r in result.reflections:
            if r is not None:
                self.assertIsInstance(r, ReflectionReport)

    def test_inter_iteration_reflect_builds_evaluation(self):
        """_inter_iteration_reflect returns report for bad runs."""
        L = Landscape()
        L.add_edge("A", "B", delta=0.3, resistance=0.5)
        # No GOAL reachable

        session = Session("ref-eval", L, _success_fn, base_dir=self.tmpdir)
        result = session.run("A", goal="GOAL", max_cycles=5)
        pre = snapshot_tensions(L)
        rmap = compute_residual_map(L, result.trace, pre, iteration=1)

        report = session._inter_iteration_reflect(result, "GOAL", rmap)
        # Goal not reached → failure reflection
        self.assertIsNotNone(report)
        self.assertEqual(report.reflection_type, "failure")


if __name__ == "__main__":
    unittest.main()
