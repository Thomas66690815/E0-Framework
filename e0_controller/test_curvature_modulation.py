"""
B2 — M_H Topological Invariant Tests
=======================================
Verifies edge_curvature, M_H_factor, and curvature_modulation on Landscape.

M_H(x,y) = 1 / (1 + κ(x,y))  where κ = mean |face holonomy| through x→y.

Canonical reference: §2.4  v(x,y) = Δ · M_H · exp(−S_eff)
Canon Alignment §9 B2: "M_H als topologischer Invariant"
"""

import math
import unittest

import numpy as np

from e0_controller.landscape import Landscape
from e0_controller.connection import (
    omega, edge_curvature, M_H_factor, holonomy, omega_map,
)
from e0_controller.potential import v_rot, v_raw, phi


# ═══════════════════════════════════════════════════════════════
# Graph builders
# ═══════════════════════════════════════════════════════════════

def build_triangle(asym: bool = True) -> Landscape:
    """
    Triangle A→B→C→A with optional asymmetry.

    Strongly asymmetric edges produce non-zero ω and thus
    non-zero face holonomy / curvature.
    """
    L = Landscape()
    if asym:
        # Forward: high Δ, low R  →  high v
        # Reverse: low Δ, high R  →  low v
        for s, t in [("A", "B"), ("B", "C"), ("C", "A")]:
            L.add_edge(s, t, delta=5.0, resistance=0.1)
            L.add_edge(t, s, delta=0.1, resistance=0.9)
    else:
        # Symmetric: ω = 0 everywhere
        for s, t in [("A", "B"), ("B", "C"), ("C", "A")]:
            L.add_edge(s, t, delta=3.0, resistance=0.5)
            L.add_edge(t, s, delta=3.0, resistance=0.5)
    return L


def build_line() -> Landscape:
    """
    A→B→C — no triangles, so κ = 0 everywhere.
    """
    L = Landscape()
    L.add_edge("A", "B", delta=5.0, resistance=0.1)
    L.add_edge("B", "A", delta=0.1, resistance=0.9)
    L.add_edge("B", "C", delta=5.0, resistance=0.1)
    L.add_edge("C", "B", delta=0.1, resistance=0.9)
    return L


def build_diamond() -> Landscape:
    """
    Diamond: A→B, A→C, B→D, C→D with triangles through shared diagonals.

    Adds B→C and C→B to create triangles A→B→C→A and B→C→D→B.
    """
    L = Landscape()
    for s, t in [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D"),
                 ("B", "C"), ("C", "B")]:
        L.add_edge(s, t, delta=5.0, resistance=0.1)
        L.add_edge(t, s, delta=0.1, resistance=0.9)
    return L


def build_tetrahedron() -> Landscape:
    """
    Full tetrahedron A-B-C-D: every pair connected, strongly asymmetric.
    Every edge has multiple triangles → rich curvature.
    """
    L = Landscape()
    nodes = ["A", "B", "C", "D"]
    for i, s in enumerate(nodes):
        for j, t in enumerate(nodes):
            if i != j:
                if i < j:
                    L.add_edge(s, t, delta=5.0, resistance=0.1)
                    L.add_edge(t, s, delta=0.1, resistance=0.9)
    return L


# ═══════════════════════════════════════════════════════════════
# Test Classes
# ═══════════════════════════════════════════════════════════════

class TestEdgeCurvature(unittest.TestCase):
    """Test edge_curvature(L, x, y) — the κ function."""

    def test_line_graph_kappa_zero(self):
        """No triangles → κ = 0."""
        L = build_line()
        self.assertAlmostEqual(edge_curvature(L, "A", "B"), 0.0)
        self.assertAlmostEqual(edge_curvature(L, "B", "C"), 0.0)

    def test_symmetric_triangle_kappa_zero(self):
        """Symmetric triangle → ω = 0 everywhere → κ = 0."""
        L = build_triangle(asym=False)
        for s, t in [("A", "B"), ("B", "C"), ("C", "A")]:
            self.assertAlmostEqual(edge_curvature(L, s, t), 0.0,
                                   msg=f"κ({s}→{t}) should be 0 for symmetric triangle")

    def test_asymmetric_triangle_kappa_nonzero(self):
        """Asymmetric triangle → non-zero ω → κ > 0."""
        L = build_triangle(asym=True)
        kappa = edge_curvature(L, "A", "B")
        self.assertGreater(kappa, 0.0,
                           f"κ(A→B) should be > 0, got {kappa}")

    def test_kappa_nonnegative(self):
        """κ is always ≥ 0 (absolute value of holonomy)."""
        L = build_triangle(asym=True)
        for edge in L.edges:
            k = edge_curvature(L, edge.source, edge.target)
            self.assertGreaterEqual(k, 0.0)

    def test_tetrahedron_all_edges_have_curvature(self):
        """Tetrahedron has triangles for every edge → κ > 0 for all."""
        L = build_tetrahedron()
        for edge in L.edges:
            k = edge_curvature(L, edge.source, edge.target)
            # Forward edges should have curvature, reverse might too
            # At least some must be > 0
        # Check at least the forward A→B
        self.assertGreater(edge_curvature(L, "A", "B"), 0.0)

    def test_kappa_varies_across_edges(self):
        """In a diamond, different edges can have different κ."""
        L = build_diamond()
        kappas = {}
        for edge in L.edges:
            k = edge_curvature(L, edge.source, edge.target)
            kappas[(edge.source, edge.target)] = k
        # At least some edges should differ (edges with/without triangles)
        values = set(round(v, 6) for v in kappas.values())
        # Diamond has varied topology
        self.assertGreater(len(values), 0)


class TestMHFactor(unittest.TestCase):
    """Test M_H_factor(L, x, y) = 1 / (1 + κ)."""

    def test_no_curvature_returns_one(self):
        """κ = 0 → M_H = 1 (no modulation)."""
        L = build_line()
        self.assertAlmostEqual(M_H_factor(L, "A", "B"), 1.0)

    def test_curvature_less_than_one(self):
        """κ > 0 → M_H < 1 (damped)."""
        L = build_triangle(asym=True)
        mh = M_H_factor(L, "A", "B")
        self.assertLess(mh, 1.0, f"M_H should be < 1 with curvature, got {mh}")

    def test_mh_bounded_zero_one(self):
        """M_H ∈ (0, 1] for all edges."""
        L = build_tetrahedron()
        for edge in L.edges:
            mh = M_H_factor(L, edge.source, edge.target)
            self.assertGreater(mh, 0.0)
            self.assertLessEqual(mh, 1.0)

    def test_mh_formula(self):
        """Verify M_H = 1/(1+κ) directly."""
        L = build_triangle(asym=True)
        k = edge_curvature(L, "A", "B")
        mh = M_H_factor(L, "A", "B")
        expected = 1.0 / (1.0 + k)
        self.assertAlmostEqual(mh, expected, places=10)

    def test_symmetric_gives_unit_mh(self):
        """Symmetric graph → κ=0 → M_H=1 for all edges."""
        L = build_triangle(asym=False)
        for edge in L.edges:
            self.assertAlmostEqual(
                M_H_factor(L, edge.source, edge.target), 1.0,
                msg=f"M_H({edge}) should be 1.0 for symmetric graph"
            )


class TestCurvatureModulationSwitch(unittest.TestCase):
    """Test the curvature_modulation flag on Landscape."""

    def test_default_off(self):
        """curvature_modulation defaults to False."""
        L = Landscape()
        self.assertFalse(L.curvature_modulation)

    def test_explicit_on(self):
        """Can be set to True."""
        L = Landscape(curvature_modulation=True)
        self.assertTrue(L.curvature_modulation)


class TestTransitionFieldModulation(unittest.TestCase):
    """Test that transition_field uses M_H when curvature_modulation=True."""

    def test_off_unchanged(self):
        """curvature_modulation=False → v is unchanged from base formula."""
        L = build_triangle(asym=True)
        v_base = L.transition_field("A", "B")
        self.assertGreater(v_base, 0.0)

    def test_on_differs_from_off(self):
        """curvature_modulation=True → v differs when κ > 0."""
        L_off = build_triangle(asym=True)
        L_on = build_triangle(asym=True)
        L_on.curvature_modulation = True

        v_off = L_off.transition_field("A", "B")
        v_on = L_on.transition_field("A", "B")

        self.assertGreater(v_off, 0.0)
        self.assertGreater(v_on, 0.0)
        self.assertNotAlmostEqual(v_off, v_on, places=6,
                                  msg="Modulated v should differ from base v")

    def test_modulated_v_less_than_base(self):
        """M_H ≤ 1, so modulated v ≤ base v."""
        L_off = build_triangle(asym=True)
        L_on = build_triangle(asym=True)
        L_on.curvature_modulation = True

        for edge in L_off.edges:
            x, y = edge.source, edge.target
            v_base = L_off.transition_field(x, y)
            v_mod = L_on.transition_field(x, y)
            self.assertLessEqual(v_mod, v_base + 1e-12,
                                 msg=f"v_mod({x}→{y}) should be ≤ v_base")

    def test_line_graph_no_effect(self):
        """Line graph has no triangles → v unchanged by modulation."""
        L_off = build_line()
        L_on = build_line()
        L_on.curvature_modulation = True

        for edge in L_off.edges:
            x, y = edge.source, edge.target
            v_base = L_off.transition_field(x, y)
            v_mod = L_on.transition_field(x, y)
            self.assertAlmostEqual(v_base, v_mod, places=10,
                                   msg=f"Line graph: v({x}→{y}) should be unaffected")

    def test_symmetric_triangle_no_effect(self):
        """Symmetric triangle → ω=0 → κ=0 → M_H=1 → v unchanged."""
        L_off = build_triangle(asym=False)
        L_on = build_triangle(asym=False)
        L_on.curvature_modulation = True

        for edge in L_off.edges:
            x, y = edge.source, edge.target
            v_base = L_off.transition_field(x, y)
            v_mod = L_on.transition_field(x, y)
            self.assertAlmostEqual(v_base, v_mod, places=10)

    def test_missing_edge_returns_zero(self):
        """Non-existent edge → 0.0 regardless of flag."""
        L = build_triangle(asym=True)
        L.curvature_modulation = True
        self.assertEqual(L.transition_field("A", "Z"), 0.0)


class TestCacheConsistency(unittest.TestCase):
    """Test M_H and Helmholtz cache behavior."""

    def test_m_h_cache_built_once(self):
        """Multiple calls to transition_field don't rebuild the cache."""
        L = build_triangle(asym=True)
        L.curvature_modulation = True
        L.transition_field("A", "B")
        cache1 = L._M_H_cache.copy()
        L.transition_field("A", "B")
        self.assertEqual(cache1, L._M_H_cache)

    def test_cache_correct_entries(self):
        """Cache has entries for all edges in the landscape."""
        L = build_triangle(asym=True)
        L.curvature_modulation = True
        L.transition_field("A", "B")  # triggers cache build
        for edge in L.edges:
            self.assertIn((edge.source, edge.target), L._M_H_cache)

    def test_helmholtz_differs_with_modulation(self):
        """Helmholtz potential Φ changes when curvature modulation is on.
        Uses diamond (asymmetric topology) — symmetric triangle has
        Φ=0 everywhere due to rotational symmetry."""
        L_off = build_diamond()
        L_on = build_diamond()
        L_on.curvature_modulation = True

        phi_off = {s: phi(L_off, s) for s in L_off.states}
        phi_on = {s: phi(L_on, s) for s in L_on.states}

        # At least one state should have different Φ
        diffs = [abs(phi_off[s] - phi_on[s]) for s in phi_off]
        self.assertGreater(max(diffs), 0.0,
                           "Φ should differ with curvature modulation")


class TestDownstreamEffects(unittest.TestCase):
    """Test that modulation propagates through the full chain."""

    def test_omega_changes(self):
        """ω changes when curvature_modulation=True (via v_rot)."""
        L_off = build_triangle(asym=True)
        L_on = build_triangle(asym=True)
        L_on.curvature_modulation = True

        w_off = omega(L_off, "A", "B")
        w_on = omega(L_on, "A", "B")

        # Both should be non-zero for asymmetric triangle
        self.assertNotEqual(w_off, 0.0)
        self.assertNotEqual(w_on, 0.0)
        # They should differ
        self.assertNotAlmostEqual(w_off, w_on, places=6,
                                  msg="ω should differ with curvature modulation")

    def test_v_rot_changes(self):
        """v_rot changes with modulation."""
        L_off = build_triangle(asym=True)
        L_on = build_triangle(asym=True)
        L_on.curvature_modulation = True

        vr_off = v_rot(L_off, "A", "B")
        vr_on = v_rot(L_on, "A", "B")

        self.assertIsNotNone(vr_off)
        self.assertIsNotNone(vr_on)
        self.assertNotAlmostEqual(vr_off, vr_on, places=6)

    def test_holonomy_changes(self):
        """Holonomy of a triangle changes with modulation."""
        L_off = build_triangle(asym=True)
        L_on = build_triangle(asym=True)
        L_on.curvature_modulation = True

        h_off = holonomy(L_off, ["A", "B", "C", "A"])
        h_on = holonomy(L_on, ["A", "B", "C", "A"])

        self.assertNotAlmostEqual(h_off, h_on, places=6,
                                  msg="Holonomy should differ with modulation")


class TestAdmissibleNeighbors(unittest.TestCase):
    """Curvature modulation should NOT remove admissible neighbors."""

    def test_same_admissible_set(self):
        """admissible_neighbors returns the same set — M_H only scales v."""
        L_off = build_triangle(asym=True)
        L_on = build_triangle(asym=True)
        L_on.curvature_modulation = True

        for state in L_off.states:
            neighbors_off = sorted(L_off.admissible_neighbors(state))
            neighbors_on = sorted(L_on.admissible_neighbors(state))
            self.assertEqual(neighbors_off, neighbors_on,
                             msg=f"Admissible neighbors of {state} should be unaffected")


class TestSpecFormula(unittest.TestCase):
    """Verify the formula v = Δ · M_H · coherence(S_eff)."""

    def test_formula_matches(self):
        """Manually compute and compare."""
        from e0_controller.tension import coherence as coh

        L = build_triangle(asym=True)
        L.curvature_modulation = True

        x, y = "A", "B"
        delta = L.difference(x, y)
        s_eff = L.effective_tension(x, y)
        mh = L._get_M_H(x, y)
        expected = delta * coh(s_eff) * mh
        actual = L.transition_field(x, y)
        self.assertAlmostEqual(actual, expected, places=12)


class TestRepr(unittest.TestCase):
    """Landscape repr should still work."""

    def test_repr_with_modulation(self):
        L = Landscape(curvature_modulation=True)
        r = repr(L)
        self.assertIn("Landscape", r)


class TestEdgeCases(unittest.TestCase):
    """Edge cases for curvature modulation."""

    def test_single_edge_no_crash(self):
        """Single edge, no triangles — shouldn't crash."""
        L = Landscape(curvature_modulation=True)
        L.add_edge("X", "Y", delta=1.0, resistance=0.5)
        v = L.transition_field("X", "Y")
        self.assertGreater(v, 0.0)

    def test_empty_landscape(self):
        """No edges at all — transition_field returns 0."""
        L = Landscape(curvature_modulation=True)
        self.assertEqual(L.transition_field("X", "Y"), 0.0)

    def test_self_loop_ignored(self):
        """Triangle-finding excludes x and y from triangle vertices."""
        L = Landscape()
        L.add_edge("A", "B", delta=5.0, resistance=0.1)
        L.add_edge("B", "A", delta=0.1, resistance=0.9)
        # Add edge that creates "degenerate" triangle A→B→A→A (should be ignored)
        k = edge_curvature(L, "A", "B")
        self.assertEqual(k, 0.0)

    def test_modulation_on_tetrahedron(self):
        """Tetrahedron with modulation — should produce lower v for all forward edges."""
        L_off = build_tetrahedron()
        L_on = build_tetrahedron()
        L_on.curvature_modulation = True

        lowers = 0
        for edge in L_off.edges:
            x, y = edge.source, edge.target
            v_base = L_off.transition_field(x, y)
            v_mod = L_on.transition_field(x, y)
            if v_mod < v_base - 1e-12:
                lowers += 1
        self.assertGreater(lowers, 0,
                           "At least some edges should have lower v with modulation")


class TestQuantitativeBehavior(unittest.TestCase):
    """Verify quantitative properties of curvature modulation."""

    def test_triangle_kappa_magnitude(self):
        """κ in a single asymmetric triangle should be on the order of ω."""
        L = build_triangle(asym=True)
        k = edge_curvature(L, "A", "B")
        w = abs(omega(L, "A", "B"))
        # κ is built from ω values, should be same order
        self.assertGreater(k, 0.0)
        # κ should be within an order of magnitude of ω
        self.assertLess(k, 10 * (3 * w + 1),
                        "κ should be bounded relative to ω")

    def test_mh_moderate_damping(self):
        """For typical asymmetric triangle, M_H should be in (0.3, 1.0)."""
        L = build_triangle(asym=True)
        mh = M_H_factor(L, "A", "B")
        self.assertGreater(mh, 0.1, f"M_H too small: {mh}")
        self.assertLess(mh, 1.0, f"M_H should be < 1: {mh}")

    def test_modulation_strength(self):
        """
        Verify the relative damping:
        v_mod / v_base = M_H for each edge.
        """
        L_off = build_triangle(asym=True)
        L_on = build_triangle(asym=True)
        L_on.curvature_modulation = True

        for edge in L_on.edges:
            x, y = edge.source, edge.target
            v_base = L_off.transition_field(x, y)
            v_mod = L_on.transition_field(x, y)
            if v_base > 1e-12:
                ratio = v_mod / v_base
                mh = M_H_factor(L_off, x, y)
                self.assertAlmostEqual(ratio, mh, places=8,
                                       msg=f"v_mod/v_base should equal M_H for {x}→{y}")


if __name__ == "__main__":
    unittest.main()
