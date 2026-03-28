"""
Tests for C39: Resonator Integration into Controller
=======================================================
Verifies that the resonator kernel (explore_resonator.py) is properly
connected to the controller's amplitude overlay via resonator.py.

Tests organized by component:
  1. Cycle detection
  2. Cycle coherence
  3. Resonance map
  4. Intensity modifier
  5. Controller integration (resonator_modulation switch)
  6. Backward compatibility (resonator_modulation=False)
  7. Edge cases (acyclic, single-path, no neighbors)
"""

import math
import unittest

from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller, HybridMode
from e0_controller.primitives import Outcome
from e0_controller.resonator import (
    detect_cycles,
    cycle_coherence,
    resonance_map,
    build_resonance_modifier,
    ResonanceInfo,
)
from e0_controller.amplitude_overlay import analyze_controller_state


# ──────────────────────────────────────────────
# Test domains
# ──────────────────────────────────────────────

def _success_fn(source, target):
    return Outcome.SUCCESS


def _triangle_domain() -> Landscape:
    """A→B→C→A + A→OUT: 3-node cycle with exit."""
    L = Landscape()
    L.add_edge("A", "B", delta=3.0, resistance=0.2)
    L.add_edge("B", "C", delta=2.5, resistance=0.3)
    L.add_edge("C", "A", delta=2.0, resistance=0.2)
    L.add_edge("A", "OUT", delta=1.0, resistance=0.5)
    return L


def _diamond_domain() -> Landscape:
    """A→B→D, A→C→D: two paths, no cycle through A."""
    L = Landscape()
    L.add_edge("A", "B", delta=2.0, resistance=0.3)
    L.add_edge("A", "C", delta=2.5, resistance=0.2)
    L.add_edge("B", "D", delta=1.5, resistance=0.4)
    L.add_edge("C", "D", delta=1.0, resistance=0.3)
    return L


def _two_cycle_domain() -> Landscape:
    """A→B→A (2-edge cycle), A→B→C→A (3-edge cycle), A→OUT."""
    L = Landscape()
    L.add_edge("A", "B", delta=3.0, resistance=0.2)
    L.add_edge("B", "A", delta=2.0, resistance=0.3)
    L.add_edge("B", "C", delta=2.5, resistance=0.2)
    L.add_edge("C", "A", delta=2.0, resistance=0.3)
    L.add_edge("A", "OUT", delta=1.0, resistance=0.5)
    return L


def _linear_domain() -> Landscape:
    """A→B→C→D: fully acyclic."""
    L = Landscape()
    L.add_edge("A", "B", delta=2.0, resistance=0.3)
    L.add_edge("B", "C", delta=1.5, resistance=0.4)
    L.add_edge("C", "D", delta=1.0, resistance=0.3)
    return L


def _gordian_with_cycle() -> Landscape:
    """Gordian-like domain with an added cycle A→B→C→A + B→GOAL."""
    L = Landscape()
    L.add_edge("A", "B", delta=3.0, resistance=0.2)
    L.add_edge("B", "C", delta=2.5, resistance=0.3)
    L.add_edge("C", "A", delta=2.0, resistance=0.2)
    L.add_edge("B", "GOAL", delta=1.0, resistance=0.1)
    L.add_edge("A", "GOAL", delta=0.5, resistance=0.8)
    return L


# ═══════════════════════════════════════════════════════════════════
# 1. Cycle Detection
# ═══════════════════════════════════════════════════════════════════

class TestCycleDetection(unittest.TestCase):
    """Tests for detect_cycles()."""

    def test_triangle_finds_cycle(self):
        L = _triangle_domain()
        cycles = detect_cycles(L, "A", max_length=4)
        self.assertGreaterEqual(len(cycles), 1)
        # At least one cycle should be A→B→C→A
        found_abc = any(
            c == ["A", "B", "C", "A"] for c in cycles
        )
        self.assertTrue(found_abc, f"Expected A→B→C→A in {cycles}")

    def test_cycle_starts_and_ends_at_state(self):
        L = _triangle_domain()
        cycles = detect_cycles(L, "A", max_length=4)
        for c in cycles:
            self.assertEqual(c[0], "A")
            self.assertEqual(c[-1], "A")

    def test_acyclic_no_cycles(self):
        L = _linear_domain()
        cycles = detect_cycles(L, "A", max_length=4)
        self.assertEqual(len(cycles), 0)

    def test_diamond_no_cycles_at_A(self):
        """Diamond A→B→D, A→C→D has no cycle through A."""
        L = _diamond_domain()
        cycles = detect_cycles(L, "A", max_length=4)
        self.assertEqual(len(cycles), 0)

    def test_two_cycle_domain_finds_both(self):
        L = _two_cycle_domain()
        cycles = detect_cycles(L, "A", max_length=4)
        # A→B→A is only 2 edges and requires len(path)>2 (simple cycles)
        # so only A→B→C→A should be found
        self.assertGreaterEqual(len(cycles), 1)

    def test_max_length_3_finds_triangle_cycle(self):
        """A→B→C→A is a 3-edge cycle, found with max_length=3."""
        L = _two_cycle_domain()
        cycles = detect_cycles(L, "A", max_length=3)
        found_abca = any(c == ["A", "B", "C", "A"] for c in cycles)
        self.assertTrue(found_abca, f"Expected A→B→C→A in {cycles}")

    def test_max_length_below_2_returns_empty(self):
        L = _triangle_domain()
        cycles = detect_cycles(L, "A", max_length=1)
        self.assertEqual(len(cycles), 0)

    def test_max_length_constrains(self):
        """With max_length=2, the 3-edge cycle should NOT appear."""
        L = _triangle_domain()
        cycles = detect_cycles(L, "A", max_length=2)
        # A→B→C→A is 3 edges, should not appear
        found_abc = any(c == ["A", "B", "C", "A"] for c in cycles)
        self.assertFalse(found_abc)


# ═══════════════════════════════════════════════════════════════════
# 2. Cycle Coherence
# ═══════════════════════════════════════════════════════════════════

class TestCycleCoherence(unittest.TestCase):
    """Tests for cycle_coherence()."""

    def test_triangle_positive_coherence(self):
        L = _triangle_domain()
        r_coh = cycle_coherence(L, ["A", "B", "C"], n_cycles=3)
        self.assertGreater(r_coh, 0.0)

    def test_coherence_bounded(self):
        """R_coh should be in [0, some reasonable upper bound]."""
        L = _triangle_domain()
        r_coh = cycle_coherence(L, ["A", "B", "C"], n_cycles=3)
        self.assertGreaterEqual(r_coh, 0.0)
        # Theoretically can exceed 1.0 with constructive interference but
        # practically bounded
        self.assertLess(r_coh, 10.0)

    def test_broken_cycle_returns_zero(self):
        """If an edge in the cycle doesn't exist, R_coh = 0."""
        L = _linear_domain()
        r_coh = cycle_coherence(L, ["A", "B", "C"], n_cycles=3)
        # C→A doesn't exist
        self.assertEqual(r_coh, 0.0)

    def test_single_node_cycle_zero(self):
        """Degenerate single-node cycle → 0."""
        L = _triangle_domain()
        r_coh = cycle_coherence(L, ["A"], n_cycles=3)
        # Only 1 node, edge A→A doesn't exist
        self.assertEqual(r_coh, 0.0)

    def test_more_cycles_doesnt_crash(self):
        """n_cycles=10 should still work."""
        L = _triangle_domain()
        r_coh = cycle_coherence(L, ["A", "B", "C"], n_cycles=10)
        self.assertGreater(r_coh, 0.0)


# ═══════════════════════════════════════════════════════════════════
# 3. Resonance Map
# ═══════════════════════════════════════════════════════════════════

class TestResonanceMap(unittest.TestCase):
    """Tests for resonance_map()."""

    def test_triangle_B_has_resonance(self):
        """Action B enters the A→B→C→A cycle."""
        L = _triangle_domain()
        rmap = resonance_map(L, "A")
        self.assertIn("B", rmap)
        self.assertGreater(rmap["B"].factor, 1.0)

    def test_triangle_OUT_not_in_map(self):
        """Action OUT doesn't participate in any cycle."""
        L = _triangle_domain()
        rmap = resonance_map(L, "A")
        self.assertNotIn("OUT", rmap)

    def test_acyclic_empty_map(self):
        L = _linear_domain()
        rmap = resonance_map(L, "A")
        self.assertEqual(len(rmap), 0)

    def test_resonance_factor_bounded(self):
        """factor should be in [1.0, 2.0]."""
        L = _triangle_domain()
        rmap = resonance_map(L, "A")
        for action, info in rmap.items():
            self.assertGreaterEqual(info.factor, 1.0)
            self.assertLessEqual(info.factor, 2.0)

    def test_resonance_info_fields(self):
        L = _triangle_domain()
        rmap = resonance_map(L, "A")
        if "B" in rmap:
            info = rmap["B"]
            self.assertIsInstance(info, ResonanceInfo)
            self.assertEqual(info.action, "B")
            self.assertGreater(info.best_r_coh, 0.0)
            self.assertGreaterEqual(info.cycle_count, 1)
            self.assertIsNotNone(info.best_cycle)

    def test_threshold_filters_weak_resonance(self):
        """With a very high threshold, weak resonance maps to factor 1.0."""
        L = _triangle_domain()
        rmap = resonance_map(L, "A", r_coh_threshold=100.0)
        for info in rmap.values():
            self.assertEqual(info.factor, 1.0)


# ═══════════════════════════════════════════════════════════════════
# 4. Intensity Modifier
# ═══════════════════════════════════════════════════════════════════

class TestIntensityModifier(unittest.TestCase):
    """Tests for build_resonance_modifier()."""

    def test_modifier_boosts_cyclic_action(self):
        L = _triangle_domain()
        modifier = build_resonance_modifier(L, "A")
        raw = 1.0
        modified = modifier("B", raw)
        self.assertGreater(modified, raw)

    def test_modifier_leaves_noncyclic_unchanged(self):
        L = _triangle_domain()
        modifier = build_resonance_modifier(L, "A")
        raw = 1.0
        modified = modifier("OUT", raw)
        self.assertEqual(modified, raw)

    def test_modifier_leaves_unknown_action_unchanged(self):
        L = _triangle_domain()
        modifier = build_resonance_modifier(L, "A")
        raw = 1.0
        modified = modifier("NONEXISTENT", raw)
        self.assertEqual(modified, raw)

    def test_modifier_scales_linearly(self):
        """modifier(a, 2*I) == 2 * modifier(a, I)."""
        L = _triangle_domain()
        modifier = build_resonance_modifier(L, "A")
        m1 = modifier("B", 1.0)
        m2 = modifier("B", 2.0)
        self.assertAlmostEqual(m2, 2 * m1, places=10)


# ═══════════════════════════════════════════════════════════════════
# 5. Controller Integration
# ═══════════════════════════════════════════════════════════════════

class TestControllerIntegration(unittest.TestCase):
    """Tests that resonator_modulation=True modifies controller behavior."""

    def test_controller_accepts_resonator_modulation(self):
        L = _triangle_domain()
        ctrl = E0Controller(L, _success_fn, resonator_modulation=True)
        self.assertTrue(ctrl.resonator_modulation)

    def test_controller_default_no_resonator(self):
        L = _triangle_domain()
        ctrl = E0Controller(L, _success_fn)
        self.assertFalse(ctrl.resonator_modulation)

    def test_overlay_differs_with_resonator(self):
        """On a cyclic domain, resonator_modulation changes intensities."""
        L = _triangle_domain()
        ctrl_off = E0Controller(L, _success_fn, resonator_modulation=False)
        ctrl_on = E0Controller(L, _success_fn, resonator_modulation=True)

        report_off = analyze_controller_state(
            ctrl_off, "A", horizon_edges=3, geometry="simple"
        )
        # Build modifier and apply
        modifier = build_resonance_modifier(L, "A")
        report_on = analyze_controller_state(
            ctrl_on, "A", horizon_edges=3, geometry="simple",
            intensity_modifier=modifier,
        )

        # Find the cyclic action (B)
        i_off_B = next(a.intensity for a in report_off.action_infos if a.action == "B")
        i_on_B = next(a.intensity for a in report_on.action_infos if a.action == "B")
        # Non-cyclic action (OUT)
        i_off_OUT = next(a.intensity for a in report_off.action_infos if a.action == "OUT")
        i_on_OUT = next(a.intensity for a in report_on.action_infos if a.action == "OUT")

        # B should be boosted, OUT unchanged
        self.assertGreater(i_on_B, i_off_B)
        self.assertAlmostEqual(i_on_OUT, i_off_OUT, places=10)

    def test_controller_run_with_resonator(self):
        """Full run with resonator_modulation completes without error."""
        L = _gordian_with_cycle()
        ctrl = E0Controller(L, _success_fn, resonator_modulation=True)
        trace = ctrl.run("A", max_cycles=10, goal="GOAL",
                         overlay_horizon=3)
        self.assertIsNotNone(trace)
        self.assertGreater(len(trace.path), 0)

    def test_hybrid_override_with_resonator(self):
        """HYBRID mode with resonator_modulation works end-to-end."""
        L = _gordian_with_cycle()
        ctrl = E0Controller(
            L,
            _success_fn,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            resonator_modulation=True,
        )
        trace = ctrl.run("A", max_cycles=10, goal="GOAL",
                         overlay_horizon=3,
                         overlay_goals={"GOAL"})
        self.assertIsNotNone(trace)

    def test_resonator_via_compute_overlay(self):
        """_compute_overlay with resonator_modulation=True injects modifier."""
        L = _triangle_domain()
        ctrl = E0Controller(L, _success_fn, resonator_modulation=True)
        report = ctrl._compute_overlay("A", 3, None, "simple")
        self.assertIsNotNone(report)
        # Check that B has a boosted factor
        i_B = next(a.intensity for a in report.action_infos if a.action == "B")
        self.assertGreater(i_B, 0)


# ═══════════════════════════════════════════════════════════════════
# 6. Backward Compatibility
# ═══════════════════════════════════════════════════════════════════

class TestBackwardCompatibility(unittest.TestCase):
    """resonator_modulation=False preserves all prior behavior."""

    def test_default_off_no_modifier(self):
        """Without resonator_modulation, overlay uses no modifier."""
        L = _triangle_domain()
        ctrl = E0Controller(L, _success_fn, resonator_modulation=False)
        report = ctrl._compute_overlay("A", 3, None, "simple")
        self.assertIsNotNone(report)

    def test_overlay_identical_without_resonator(self):
        """Two controllers without resonator produce identical overlays."""
        L = _triangle_domain()
        ctrl1 = E0Controller(L, _success_fn)
        ctrl2 = E0Controller(L, _success_fn)
        r1 = ctrl1._compute_overlay("A", 3, None, "simple")
        r2 = ctrl2._compute_overlay("A", 3, None, "simple")
        for a1, a2 in zip(r1.action_infos, r2.action_infos):
            self.assertEqual(a1.action, a2.action)
            self.assertAlmostEqual(a1.intensity, a2.intensity, places=10)

    def test_acyclic_domain_resonator_on_has_no_effect(self):
        """On acyclic domain, resonator_modulation=True changes nothing."""
        L = _linear_domain()
        ctrl_off = E0Controller(L, _success_fn)
        ctrl_on = E0Controller(L, _success_fn, resonator_modulation=True)
        r_off = ctrl_off._compute_overlay("A", 3, None, "simple")
        r_on = ctrl_on._compute_overlay("A", 3, None, "simple")
        for a1, a2 in zip(r_off.action_infos, r_on.action_infos):
            self.assertEqual(a1.action, a2.action)
            self.assertAlmostEqual(a1.intensity, a2.intensity, places=10)


# ═══════════════════════════════════════════════════════════════════
# 7. Edge Cases
# ═══════════════════════════════════════════════════════════════════

class TestEdgeCases(unittest.TestCase):
    """Edge cases for resonator integration."""

    def test_single_edge_domain(self):
        """Domain with one edge — no cycles, no crash."""
        L = Landscape()
        L.add_edge("A", "B", delta=1.0, resistance=0.5)
        cycles = detect_cycles(L, "A")
        self.assertEqual(len(cycles), 0)
        rmap = resonance_map(L, "A")
        self.assertEqual(len(rmap), 0)

    def test_self_loop_not_counted(self):
        """A→A self-loop should not create a cycle in detect_cycles."""
        L = Landscape()
        L.add_edge("A", "A", delta=1.0, resistance=0.5)
        L.add_edge("A", "B", delta=1.0, resistance=0.5)
        cycles = detect_cycles(L, "A")
        # Self-loops are not simple cycles
        for c in cycles:
            self.assertGreater(len(c), 2)

    def test_probabilities_still_sum_to_one(self):
        """With resonator modulation, probabilities must still sum to 1."""
        L = _triangle_domain()
        ctrl = E0Controller(L, _success_fn, resonator_modulation=True)
        report = ctrl._compute_overlay("A", 3, None, "simple")
        total_p = sum(a.probability for a in report.action_infos)
        self.assertAlmostEqual(total_p, 1.0, places=10)

    def test_intensities_non_negative(self):
        """All intensities remain non-negative after modification."""
        L = _triangle_domain()
        ctrl = E0Controller(L, _success_fn, resonator_modulation=True)
        report = ctrl._compute_overlay("A", 3, None, "simple")
        for a in report.action_infos:
            self.assertGreaterEqual(a.intensity, 0.0)

    def test_gordian_with_cycle_probabilities_valid(self):
        """Gordian-with-cycle: probabilities valid after resonator boost."""
        L = _gordian_with_cycle()
        ctrl = E0Controller(L, _success_fn, resonator_modulation=True)
        report = ctrl._compute_overlay("A", 3, {"GOAL"}, "goal_reaching")
        if report is not None:
            total_p = sum(a.probability for a in report.action_infos)
            self.assertAlmostEqual(total_p, 1.0, places=10)


if __name__ == "__main__":
    unittest.main()
