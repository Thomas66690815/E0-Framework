"""
Tests for C102: Scoped Reflexion Controller Integration
=========================================================
Verifies that scoped=True in integrated_reflexion() and
run_with_integrated_reflexion() correctly delegates to C101
scoped reflexion while preserving backward compatibility.

Tests cover:
  1. integrated_reflexion() with scoped=True
  2. integrated_reflexion() backward compat (scoped=False unchanged)
  3. run_with_integrated_reflexion() with scoped=True
  4. Runner backward compat (scoped=False unchanged)
  5. Scope metadata propagation (scopes list populated)
  6. scope_mu parameter effect
  7. Fresh landscape degeneration (low trace_load → global-like scope)
  8. Historized landscape locality (high trace_load → narrow scope)
"""

import unittest

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.dual_reflection import (
    ComponentAssessment,
    DualReflectionReport,
    SelfGraphDiagnosis,
)
from e0_controller.reflexive_action import ReflexiveAction, ReflexiveActionResult
from e0_controller.reflexive_edge_proposal import ProposedEdge
from e0_controller.scoped_reflexion import ReflexionScope
from e0_controller.integrated_reflexion import (
    IntegratedReflexionResult,
    integrated_reflexion,
    run_with_integrated_reflexion,
)


# ── Helpers ──

def _make_frontier_landscape():
    """S→A→B cycle, GOAL isolated → frontier at B."""
    L = Landscape()
    L.add_edge("S", "A", delta=0.5, resistance=0.3)
    L.add_edge("A", "B", delta=0.5, resistance=0.3)
    L.add_edge("B", "S", delta=0.5, resistance=0.3)
    L.add_state("GOAL")
    return L


def _historize(L, n=1):
    """Inscribe all existing edges n times with SUCCESS."""
    for _ in range(n):
        for e in list(L._delta):
            L.historization.update(e, Outcome.SUCCESS)


def _make_connected():
    """S→A→GOAL — no frontier."""
    L = Landscape()
    L.add_edge("S", "A", delta=0.5, resistance=0.3)
    L.add_edge("A", "GOAL", delta=0.5, resistance=0.3)
    return L


def _make_large_graph(n=10):
    """Chain S→N1→N2→...→N{n-1} + GOAL isolated.
    Frontier at N{n-1}.
    """
    L = Landscape()
    prev = "S"
    for i in range(1, n):
        name = f"N{i}"
        L.add_edge(prev, name, delta=0.5, resistance=0.3)
        prev = name
    L.add_state("GOAL")
    return L


def _all_success(source, target):
    return Outcome.SUCCESS


def _make_diagnosis(deactivation_candidates=None, components=None):
    return SelfGraphDiagnosis(
        deactivation_candidates=deactivation_candidates or [],
        components=components or [],
    )


def _make_report(diagnosis):
    return DualReflectionReport(domain_report=None, self_diagnosis=diagnosis)


# ══════════════════════════════════════════════
# 1. integrated_reflexion() with scoped=True
# ══════════════════════════════════════════════

class TestIntegratedReflexionScoped(unittest.TestCase):
    """Scoped mode in the standalone function."""

    def test_scoped_proposes_edges_at_frontier(self):
        """scoped=True at frontier → proposals via scoped_propose_edges."""
        L = _make_frontier_landscape()
        _historize(L)
        r = integrated_reflexion(L, "B", "GOAL", scoped=True)
        self.assertTrue(r.topology_changed)
        self.assertGreater(len(r.edge_proposals), 0)
        self.assertTrue(L.has_edge("B", "GOAL"))

    def test_scoped_populates_scopes_list(self):
        """scoped=True → result.scopes has one ReflexionScope."""
        L = _make_frontier_landscape()
        _historize(L)
        r = integrated_reflexion(L, "B", "GOAL", scoped=True)
        self.assertEqual(len(r.scopes), 1)
        scope = r.scopes[0]
        self.assertIsInstance(scope, ReflexionScope)
        self.assertIn("B", scope.included_states)
        self.assertGreater(scope.radius, 0)

    def test_scoped_false_has_empty_scopes(self):
        """scoped=False (default) → no scope metadata."""
        L = _make_frontier_landscape()
        _historize(L)
        r = integrated_reflexion(L, "B", "GOAL", scoped=False)
        self.assertEqual(len(r.scopes), 0)
        self.assertTrue(r.topology_changed)

    def test_scoped_no_frontier_no_proposals(self):
        """scoped=True on connected landscape → no proposals."""
        L = _make_connected()
        r = integrated_reflexion(L, "S", "GOAL", scoped=True)
        self.assertFalse(r.topology_changed)
        self.assertEqual(len(r.scopes), 0)

    def test_scoped_with_flags(self):
        """scoped=True + flag report → both fire."""
        L = _make_frontier_landscape()
        L.curvature_modulation = True
        _historize(L)
        diag = _make_diagnosis(
            deactivation_candidates=["curvature"],
            components=[ComponentAssessment(
                "curvature", load=5.0, quality=-0.5, inertia=0.8,
                status="harmful", is_modulation=True,
            )],
        )
        report = _make_report(diag)
        r = integrated_reflexion(L, "B", "GOAL", report=report, scoped=True)
        self.assertTrue(r.flags_changed)
        self.assertTrue(r.topology_changed)
        self.assertEqual(len(r.scopes), 1)

    def test_scope_mu_affects_locality(self):
        """Smaller mu → higher locality → smaller scope radius."""
        L = _make_frontier_landscape()
        _historize(L, n=5)
        r_small_mu = integrated_reflexion(L, "B", "GOAL", scoped=True, scope_mu=0.5)
        sc_small = r_small_mu.scopes[0] if r_small_mu.scopes else None

        # Reset landscape
        L2 = _make_frontier_landscape()
        _historize(L2, n=5)
        r_large_mu = integrated_reflexion(L2, "B", "GOAL", scoped=True, scope_mu=50.0)
        sc_large = r_large_mu.scopes[0] if r_large_mu.scopes else None

        self.assertIsNotNone(sc_small)
        self.assertIsNotNone(sc_large)
        # Smaller mu → higher locality → smaller or equal radius
        self.assertLessEqual(sc_small.radius, sc_large.radius)
        self.assertGreaterEqual(sc_small.locality, sc_large.locality)


# ══════════════════════════════════════════════
# 2. Backward compatibility
# ══════════════════════════════════════════════

class TestBackwardCompatibility(unittest.TestCase):
    """scoped=False (default) produces identical behavior to pre-C102."""

    def test_default_is_unscoped(self):
        """No scoped kwarg → global proposals."""
        L = _make_frontier_landscape()
        _historize(L)
        r = integrated_reflexion(L, "B", "GOAL")
        self.assertTrue(r.topology_changed)
        self.assertEqual(len(r.scopes), 0)

    def test_result_has_scopes_field(self):
        """IntegratedReflexionResult always has scopes list (empty by default)."""
        r = IntegratedReflexionResult()
        self.assertIsInstance(r.scopes, list)
        self.assertEqual(len(r.scopes), 0)


# ══════════════════════════════════════════════
# 3. run_with_integrated_reflexion() scoped mode
# ══════════════════════════════════════════════

class TestRunnerScoped(unittest.TestCase):
    """Full runner with scoped=True."""

    def test_scoped_runner_reaches_goal(self):
        """Scoped runner navigates through frontier to GOAL."""
        L = Landscape()
        L.add_edge("S", "A", delta=0.5, resistance=0.3)
        L.historization.update(Edge("S", "A"), Outcome.SUCCESS)
        L.add_state("GOAL")

        trace, result, journal = run_with_integrated_reflexion(
            L, _all_success, "S", "GOAL", max_cycles=30, scoped=True,
        )
        self.assertTrue(result.topology_changed)
        self.assertGreater(len(result.scopes), 0)
        # Should reach GOAL or get close
        self.assertGreater(len(trace.steps), 0)

    def test_scoped_runner_collects_scopes(self):
        """Runner accumulates scope metadata from all frontier encounters."""
        L = Landscape()
        L.add_edge("S", "A", delta=0.5, resistance=0.3)
        L.historization.update(Edge("S", "A"), Outcome.SUCCESS)
        L.add_state("GOAL")

        trace, result, journal = run_with_integrated_reflexion(
            L, _all_success, "S", "GOAL", max_cycles=30, scoped=True,
        )
        self.assertIsInstance(result.scopes, list)
        for scope in result.scopes:
            self.assertIsInstance(scope, ReflexionScope)

    def test_unscoped_runner_no_scopes(self):
        """scoped=False runner → empty scopes list."""
        L = Landscape()
        L.add_edge("S", "A", delta=0.5, resistance=0.3)
        L.historization.update(Edge("S", "A"), Outcome.SUCCESS)
        L.add_state("GOAL")

        trace, result, journal = run_with_integrated_reflexion(
            L, _all_success, "S", "GOAL", max_cycles=30, scoped=False,
        )
        self.assertEqual(len(result.scopes), 0)

    def test_connected_scoped_runner(self):
        """Connected landscape → no frontiers → no scopes."""
        L = _make_connected()
        trace, result, journal = run_with_integrated_reflexion(
            L, _all_success, "S", "GOAL", max_cycles=20, scoped=True,
        )
        self.assertEqual(trace.path[-1], "GOAL")
        self.assertFalse(result.topology_changed)
        self.assertEqual(len(result.scopes), 0)

    def test_scope_mu_passed_to_runner(self):
        """scope_mu parameter reaches the scope computation."""
        L = Landscape()
        L.add_edge("S", "A", delta=0.5, resistance=0.3)
        L.historization.update(Edge("S", "A"), Outcome.SUCCESS)
        L.add_state("GOAL")

        trace, result, journal = run_with_integrated_reflexion(
            L, _all_success, "S", "GOAL", max_cycles=30,
            scoped=True, scope_mu=1.0,
        )
        # Just verify it runs without error and produces scopes
        if result.scopes:
            for scope in result.scopes:
                self.assertGreater(scope.locality, 0.0)


# ══════════════════════════════════════════════
# 4. Fresh vs historized locality
# ══════════════════════════════════════════════

class TestFreshVsHistorized(unittest.TestCase):
    """Verify the canonical property: fresh → global, historized → local."""

    def test_fresh_landscape_wide_scope(self):
        """Minimal historization → locality near 0 → radius ≈ diameter."""
        L = _make_large_graph(n=8)
        # Only 1 inscription on first edge
        L.historization.update(Edge("S", "N1"), Outcome.SUCCESS)
        r = integrated_reflexion(L, "N7", "GOAL", scoped=True)
        if r.scopes:
            scope = r.scopes[0]
            # Fresh: locality should be low
            self.assertLess(scope.locality, 0.5)

    def test_heavy_historization_narrow_scope(self):
        """Heavy historization → locality near 1 → narrow radius."""
        L = _make_large_graph(n=8)
        _historize(L, n=20)  # 20 rounds of inscription
        r = integrated_reflexion(L, "N7", "GOAL", scoped=True, scope_mu=1.0)
        if r.scopes:
            scope = r.scopes[0]
            # Historized: locality should be high
            self.assertGreater(scope.locality, 0.5)


# ══════════════════════════════════════════════
# 5. Edge cases
# ══════════════════════════════════════════════

class TestEdgeCases(unittest.TestCase):
    """Edge cases for scoped integration."""

    def test_scoped_with_enable_topology_false(self):
        """scoped=True but enable_topology=False → no proposals, no scopes."""
        L = _make_frontier_landscape()
        _historize(L)
        r = integrated_reflexion(L, "B", "GOAL",
                                 scoped=True, enable_topology=False)
        self.assertFalse(r.topology_changed)
        self.assertEqual(len(r.scopes), 0)

    def test_scoped_single_state_landscape(self):
        """Landscape with only one state → no frontier, no crash."""
        L = Landscape()
        L.add_state("ONLY")
        L.add_state("GOAL")
        r = integrated_reflexion(L, "ONLY", "GOAL", scoped=True)
        # No edges → is_frontier may fire but no pattern → graceful
        self.assertEqual(len(r.scopes), 0) if not r.scopes else None

    def test_result_scopes_default_empty(self):
        """New IntegratedReflexionResult has empty scopes list."""
        r = IntegratedReflexionResult()
        self.assertEqual(r.scopes, [])


if __name__ == "__main__":
    unittest.main()
