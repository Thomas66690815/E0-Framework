"""
C40 — Graduated Overlap Tests
================================
Tests for overlap.py and overlap_modulation on Landscape.

Verifies the graduated overlap functional from Ontodynamics §3.4:
"Connections possess degree. Overlap is graduated, not binary.
 Stability requires non-zero overlap."

M_H(x,y) = normalized overlap of edge x→y with its co-realized neighborhood.

45 domains surveyed: overlap non-trivial on <10, trivially 1 on >35.
Falsification domain: Custom Overlap Differentiator where two paths
have identical Δ, R, S_eff, ω but different overlap.
"""

import math
import unittest

from e0_controller.landscape import Landscape
from e0_controller.overlap import (
    triangle_support, edge_overlap, overlap_map, OverlapInfo,
)


# ═══════════════════════════════════════════════════════════════
# Domain builders
# ═══════════════════════════════════════════════════════════════

def build_overlap_differentiator() -> Landscape:
    """
    Custom falsification domain:
    Path 1: S → A → GOAL  (bridge, no support)
    Path 2: S → B → GOAL  (supported by C)
    Support: S → C → B, C → GOAL

    All edges: δ=1.0, R=0.5 — identical per-edge properties.
    Only structural difference: S→B has bypass S→C→B.
    """
    L = Landscape()
    for s, t in [("S", "A"), ("A", "GOAL"),
                 ("S", "B"), ("B", "GOAL"),
                 ("S", "C"), ("C", "B"), ("C", "GOAL")]:
        L.add_edge(s, t, delta=1.0, resistance=0.5)
    return L


def build_linear() -> Landscape:
    """A → B → C → D — no triangles anywhere."""
    L = Landscape()
    for s, t in [("A", "B"), ("B", "C"), ("C", "D")]:
        L.add_edge(s, t, delta=1.0, resistance=0.5)
    return L


def build_triangle_cycle() -> Landscape:
    """A → B → C → A — cycle but no directed 2-hop bypass for any edge."""
    L = Landscape()
    for s, t in [("A", "B"), ("B", "C"), ("C", "A")]:
        L.add_edge(s, t, delta=0.5, resistance=0.1)
    return L


def build_full_triangle() -> Landscape:
    """A → B, A → C, B → C — A→C is a direct edge, A→B→C is a bypass."""
    L = Landscape()
    L.add_edge("A", "B", delta=1.0, resistance=0.5)
    L.add_edge("B", "C", delta=1.0, resistance=0.5)
    L.add_edge("A", "C", delta=1.0, resistance=0.5)
    return L


def build_nested_loop() -> Landscape:
    """
    Outer: A → B → C → A
    Inner: B → X → C
    Leak:  C → OUT
    """
    L = Landscape()
    for s, t in [("A", "B"), ("B", "C"), ("C", "A")]:
        L.add_edge(s, t, delta=0.5, resistance=0.1)
    L.add_edge("B", "X", delta=0.4, resistance=0.15)
    L.add_edge("X", "C", delta=0.4, resistance=0.15)
    L.add_edge("C", "OUT", delta=0.3, resistance=1.5)
    return L


def build_asymmetric_support() -> Landscape:
    """
    S → A → G  and  S → B → G
    Support for S→A: S → X → A (weak: δ=0.1, R=2.0)
    Support for S→B: S → Y → B (strong: δ=2.0, R=0.1)
    """
    L = Landscape()
    L.add_edge("S", "A", delta=1.0, resistance=0.5)
    L.add_edge("A", "G", delta=1.0, resistance=0.5)
    L.add_edge("S", "B", delta=1.0, resistance=0.5)
    L.add_edge("B", "G", delta=1.0, resistance=0.5)
    # Weak support for A
    L.add_edge("S", "X", delta=0.1, resistance=2.0)
    L.add_edge("X", "A", delta=0.1, resistance=2.0)
    # Strong support for B
    L.add_edge("S", "Y", delta=2.0, resistance=0.1)
    L.add_edge("Y", "B", delta=2.0, resistance=0.1)
    return L


# ═══════════════════════════════════════════════════════════════
# Test Classes
# ═══════════════════════════════════════════════════════════════

class TestTriangleSupport(unittest.TestCase):
    """Test T(x,y) — the directed 2-hop support set."""

    def test_linear_no_support(self):
        """Linear chain has no triangles."""
        L = build_linear()
        for e in L.edges:
            self.assertEqual(triangle_support(L, e.source, e.target), set())

    def test_cycle_no_bypass(self):
        """3-cycle A→B→C→A: no edge has a forward 2-hop bypass."""
        L = build_triangle_cycle()
        # A→B: need z with A→z and z→B. Only A→B exists from A (z=B excluded).
        self.assertEqual(triangle_support(L, "A", "B"), set())

    def test_full_triangle_has_support(self):
        """A→C has bypass A→B→C, so T(A,C) = {B}."""
        L = build_full_triangle()
        self.assertEqual(triangle_support(L, "A", "C"), {"B"})

    def test_full_triangle_no_support_for_legs(self):
        """A→B and B→C have no 2-hop bypass."""
        L = build_full_triangle()
        self.assertEqual(triangle_support(L, "A", "B"), set())
        self.assertEqual(triangle_support(L, "B", "C"), set())

    def test_differentiator_supported_edge(self):
        """S→B has support via C in the differentiator domain."""
        L = build_overlap_differentiator()
        self.assertEqual(triangle_support(L, "S", "B"), {"C"})

    def test_differentiator_unsupported_edge(self):
        """S→A has no support in the differentiator domain."""
        L = build_overlap_differentiator()
        self.assertEqual(triangle_support(L, "S", "A"), set())

    def test_nested_loop_bc_supported(self):
        """B→C has bypass via X in nested loop."""
        L = build_nested_loop()
        self.assertEqual(triangle_support(L, "B", "C"), {"X"})

    def test_excludes_x_and_y(self):
        """z must not be x or y."""
        L = Landscape()
        L.add_edge("A", "A", delta=1.0, resistance=0.5)  # self-loop
        L.add_edge("A", "B", delta=1.0, resistance=0.5)
        self.assertEqual(triangle_support(L, "A", "B"), set())


class TestEdgeOverlap(unittest.TestCase):
    """Test the overlap(x→y) = Σ √(v(x,z)·v(z,y)) function."""

    def test_no_support_zero(self):
        """Edge with empty T → overlap = 0."""
        L = build_linear()
        self.assertEqual(edge_overlap(L, "A", "B"), 0.0)

    def test_supported_edge_positive(self):
        """Edge with non-empty T → overlap > 0."""
        L = build_full_triangle()
        ov = edge_overlap(L, "A", "C")
        self.assertGreater(ov, 0.0)

    def test_overlap_equals_geometric_mean(self):
        """Verify overlap = √(v(A,B) · v(B,C)) for single support node."""
        L = build_full_triangle()
        ov = edge_overlap(L, "A", "C")
        expected = math.sqrt(
            L.transition_field("A", "B") * L.transition_field("B", "C")
        )
        self.assertAlmostEqual(ov, expected, places=10)

    def test_differentiator_values(self):
        """In the differentiator, S→B overlap = √(v(S,C)·v(C,B))."""
        L = build_overlap_differentiator()
        ov = edge_overlap(L, "S", "B")
        expected = math.sqrt(
            L.transition_field("S", "C") * L.transition_field("C", "B")
        )
        self.assertAlmostEqual(ov, expected, places=10)
        self.assertGreater(ov, 0.0)

    def test_asymmetric_support_differs(self):
        """Weak support (via X) gives less overlap than strong support (via Y)."""
        L = build_asymmetric_support()
        ov_a = edge_overlap(L, "S", "A")  # weak support
        ov_b = edge_overlap(L, "S", "B")  # strong support
        self.assertGreater(ov_b, ov_a)
        self.assertGreater(ov_a, 0.0)  # weak but non-zero

    def test_overlap_nonnegative(self):
        """Overlap is always ≥ 0."""
        L = build_nested_loop()
        for e in L.edges:
            self.assertGreaterEqual(edge_overlap(L, e.source, e.target), 0.0)


class TestOverlapMap(unittest.TestCase):
    """Test overlap_map() — the full M_H computation."""

    def test_linear_all_neutral(self):
        """Linear domain → max_overlap=0 → all M_H=1.0."""
        L = build_linear()
        om = overlap_map(L)
        for info in om.values():
            self.assertAlmostEqual(info.m_h, 1.0)

    def test_cycle_all_neutral(self):
        """Simple 3-cycle → no bypass → all M_H=1.0."""
        L = build_triangle_cycle()
        om = overlap_map(L)
        for info in om.values():
            self.assertAlmostEqual(info.m_h, 1.0)

    def test_differentiator_supported_gets_one(self):
        """Best-supported edge gets M_H=1.0."""
        L = build_overlap_differentiator()
        om = overlap_map(L)
        self.assertAlmostEqual(om[("S", "B")].m_h, 1.0, places=6)

    def test_differentiator_unsupported_gets_floor(self):
        """Unsupported edge in a domain with support gets M_H=floor."""
        L = build_overlap_differentiator()
        om = overlap_map(L, floor=0.2)
        self.assertAlmostEqual(om[("S", "A")].m_h, 0.2, places=6)

    def test_floor_parameter(self):
        """Different floor values produce different M_H for unsupported edges."""
        L = build_overlap_differentiator()
        om_low = overlap_map(L, floor=0.1)
        om_high = overlap_map(L, floor=0.5)
        self.assertAlmostEqual(om_low[("S", "A")].m_h, 0.1, places=6)
        self.assertAlmostEqual(om_high[("S", "A")].m_h, 0.5, places=6)

    def test_m_h_bounded(self):
        """All M_H values are in (0, 1]."""
        L = build_overlap_differentiator()
        om = overlap_map(L)
        for info in om.values():
            self.assertGreater(info.m_h, 0.0)
            self.assertLessEqual(info.m_h, 1.0)

    def test_asymmetric_ordering(self):
        """Strongly supported edge has higher M_H than weakly supported."""
        L = build_asymmetric_support()
        om = overlap_map(L)
        self.assertGreater(om[("S", "B")].m_h, om[("S", "A")].m_h)

    def test_info_fields(self):
        """OverlapInfo has all expected fields."""
        L = build_full_triangle()
        om = overlap_map(L)
        info = om[("A", "C")]
        self.assertEqual(info.edge, ("A", "C"))
        self.assertGreater(info.overlap, 0.0)
        self.assertAlmostEqual(info.m_h, 1.0)
        self.assertEqual(info.support_set, frozenset({"B"}))

    def test_all_edges_present(self):
        """overlap_map returns an entry for every edge in the landscape."""
        L = build_nested_loop()
        om = overlap_map(L)
        for e in L.edges:
            self.assertIn((e.source, e.target), om)

    def test_nested_only_bc_supported(self):
        """In nested loop, only B→C has non-zero overlap."""
        L = build_nested_loop()
        om = overlap_map(L)
        supported = [(k, v) for k, v in om.items() if v.overlap > 0]
        self.assertEqual(len(supported), 1)
        self.assertEqual(supported[0][0], ("B", "C"))


class TestLandscapeOverlapModulation(unittest.TestCase):
    """Test overlap_modulation flag on Landscape."""

    def test_default_off(self):
        """overlap_modulation defaults to False."""
        L = Landscape()
        self.assertFalse(L.overlap_modulation)

    def test_explicit_on(self):
        L = Landscape(overlap_modulation=True)
        self.assertTrue(L.overlap_modulation)

    def test_off_unchanged(self):
        """With modulation off, v is base value."""
        L = build_overlap_differentiator()
        v_a = L.transition_field("S", "A")
        v_b = L.transition_field("S", "B")
        self.assertAlmostEqual(v_a, v_b, places=10)

    def test_on_differentiates(self):
        """With modulation on, supported edge has higher v."""
        L = build_overlap_differentiator()
        L.overlap_modulation = True
        v_a = L.transition_field("S", "A")
        v_b = L.transition_field("S", "B")
        self.assertGreater(v_b, v_a)

    def test_modulated_v_less_or_equal(self):
        """Modulated v ≤ base v (M_H ≤ 1)."""
        L_off = build_overlap_differentiator()
        L_on = build_overlap_differentiator()
        L_on.overlap_modulation = True
        for e in L_off.edges:
            v_base = L_off.transition_field(e.source, e.target)
            v_mod = L_on.transition_field(e.source, e.target)
            self.assertLessEqual(v_mod, v_base + 1e-12)

    def test_linear_no_effect(self):
        """Linear domain: modulation has zero effect."""
        L_off = build_linear()
        L_on = build_linear()
        L_on.overlap_modulation = True
        for e in L_off.edges:
            v_base = L_off.transition_field(e.source, e.target)
            v_mod = L_on.transition_field(e.source, e.target)
            self.assertAlmostEqual(v_base, v_mod, places=10)

    def test_cycle_no_effect(self):
        """Simple 3-cycle: no bypass → modulation has zero effect."""
        L_off = build_triangle_cycle()
        L_on = build_triangle_cycle()
        L_on.overlap_modulation = True
        for e in L_off.edges:
            v_base = L_off.transition_field(e.source, e.target)
            v_mod = L_on.transition_field(e.source, e.target)
            self.assertAlmostEqual(v_base, v_mod, places=10)


class TestFalsificationDomain(unittest.TestCase):
    """
    The overlap differentiator is the key falsification domain:
    two paths with identical Δ, R, S_eff, ω — only overlap differs.
    """

    def test_paths_identical_without_overlap(self):
        """Both paths S→A→GOAL and S→B→GOAL have same sum_v without modulation."""
        L = build_overlap_differentiator()
        path_a = L.transition_field("S", "A") + L.transition_field("A", "GOAL")
        path_b = L.transition_field("S", "B") + L.transition_field("B", "GOAL")
        self.assertAlmostEqual(path_a, path_b, places=10)

    def test_paths_differ_with_overlap(self):
        """With modulation, S→B→GOAL wins over S→A→GOAL."""
        L = build_overlap_differentiator()
        L.overlap_modulation = True
        v_sa = L.transition_field("S", "A")
        v_sb = L.transition_field("S", "B")
        self.assertGreater(v_sb, v_sa,
                          "Supported path S→B should have higher v than bridge S→A")

    def test_ratio_matches_m_h(self):
        """v_mod / v_base = M_H for each edge."""
        L_off = build_overlap_differentiator()
        L_on = build_overlap_differentiator()
        L_on.overlap_modulation = True
        om = overlap_map(L_off)
        for e in L_off.edges:
            x, y = e.source, e.target
            v_base = L_off.transition_field(x, y)
            v_mod = L_on.transition_field(x, y)
            if v_base > 1e-12:
                ratio = v_mod / v_base
                self.assertAlmostEqual(ratio, om[(x, y)].m_h, places=8)


class TestBackwardCompatibility(unittest.TestCase):
    """Overlap modulation must not break existing behavior."""

    def test_default_off(self):
        """Default Landscape has overlap_modulation=False."""
        L = Landscape()
        self.assertFalse(L.overlap_modulation)

    def test_curvature_and_overlap_independent(self):
        """Both modulations can be on simultaneously without crash."""
        L = build_full_triangle()
        # Add reverse edges for curvature (needs bidirectional for ω)
        L.add_edge("B", "A", delta=0.1, resistance=0.9)
        L.add_edge("C", "B", delta=0.1, resistance=0.9)
        L.add_edge("C", "A", delta=0.1, resistance=0.9)
        L.curvature_modulation = True
        L.overlap_modulation = True
        v = L.transition_field("A", "C")
        self.assertGreater(v, 0.0)

    def test_empty_landscape(self):
        """Empty landscape with modulation on: no crash."""
        L = Landscape(overlap_modulation=True)
        self.assertEqual(L.transition_field("X", "Y"), 0.0)

    def test_single_edge(self):
        """Single edge: no support, modulation neutral."""
        L = Landscape(overlap_modulation=True)
        L.add_edge("A", "B", delta=1.0, resistance=0.5)
        v = L.transition_field("A", "B")
        # No support → M_H=1.0 → same as without modulation
        L_off = Landscape()
        L_off.add_edge("A", "B", delta=1.0, resistance=0.5)
        self.assertAlmostEqual(v, L_off.transition_field("A", "B"), places=10)


class TestEdgeCases(unittest.TestCase):
    """Edge cases for overlap computation."""

    def test_self_loop_excluded(self):
        """Self-loop A→A should not appear in T(A,B)."""
        L = Landscape()
        L.add_edge("A", "A", delta=1.0, resistance=0.5)
        L.add_edge("A", "B", delta=1.0, resistance=0.5)
        T = triangle_support(L, "A", "B")
        self.assertNotIn("A", T)

    def test_zero_v_support(self):
        """Support node with v=0 on one leg contributes 0 overlap."""
        L = Landscape()
        L.add_edge("A", "B", delta=1.0, resistance=0.5)
        L.add_edge("A", "Z", delta=0.0, resistance=0.5)  # δ=0 → v=0
        L.add_edge("Z", "B", delta=1.0, resistance=0.5)
        ov = edge_overlap(L, "A", "B")
        self.assertEqual(ov, 0.0)  # √(0 · v) = 0

    def test_multiple_support_nodes(self):
        """Multiple support nodes → overlap is additive."""
        L = Landscape()
        L.add_edge("S", "G", delta=1.0, resistance=0.5)
        L.add_edge("S", "X", delta=1.0, resistance=0.5)
        L.add_edge("X", "G", delta=1.0, resistance=0.5)
        L.add_edge("S", "Y", delta=1.0, resistance=0.5)
        L.add_edge("Y", "G", delta=1.0, resistance=0.5)
        T = triangle_support(L, "S", "G")
        self.assertEqual(T, {"X", "Y"})
        ov = edge_overlap(L, "S", "G")
        v_single = math.sqrt(
            L.transition_field("S", "X") * L.transition_field("X", "G")
        )
        self.assertAlmostEqual(ov, 2 * v_single, places=10)

    def test_overlap_map_floor_zero_not_allowed_by_math(self):
        """Floor=0 means unsupported edges get M_H=0 (edge case)."""
        L = build_overlap_differentiator()
        om = overlap_map(L, floor=0.0)
        # With floor=0: ε = 0, so overlap=0 → M_H = 0/max = 0
        self.assertAlmostEqual(om[("S", "A")].m_h, 0.0, places=10)
        self.assertAlmostEqual(om[("S", "B")].m_h, 1.0, places=10)

    def test_gordian_trap_all_neutral(self):
        """Gordian Trap has no triangles → all M_H=1.0."""
        from e0_controller.test_gordian_trap import build_gordian_trap
        L = build_gordian_trap()
        om = overlap_map(L)
        for info in om.values():
            self.assertAlmostEqual(info.m_h, 1.0,
                                  msg=f"Gordian edge {info.edge} should have M_H=1.0")


if __name__ == "__main__":
    unittest.main()
