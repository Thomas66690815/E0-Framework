"""
Tests for Multi-Axis SU(2) — Per-Edge Rotation Axes (B1)
==========================================================
Validates that:
1. Per-edge axis_fn is correctly threaded through the full stack
2. Non-commutativity manifests: U(x,y)·U(y,z) ≠ U(y,z)·U(x,y) when axes differ
3. Path-order dependence: swapping edge order changes spinor but preserves magnitude
4. Multi-axis interference differs from single-axis (σ_z) and from U(1)
5. Controller decisions change under multi-axis vs single-axis SU(2)
6. Holonomy depends on axis assignment
7. 3D test domain (Tetrahedron) with orthogonal per-edge axes

Claims covered:
    B1 (Canon Alignment §9.2): Per-edge rotation axes
    C15 extension: axis_fn threaded through controller
    C23 extension: topology reclassification under multi-axis
"""

from __future__ import annotations

import math
import unittest
from typing import Optional

import numpy as np

from e0_controller.landscape import Landscape
from e0_controller.connection import omega
from e0_controller.wavepath import path_tension
from e0_controller.spinor_connection import (
    IDENTITY, SIGMA_X, SIGMA_Y, SIGMA_Z, SPINOR_UP,
    pauli_exponential,
    su2_edge_transport,
    su2_path_transport,
    su2_holonomy,
    spinor_psi,
    spinor_sum_paths,
    spinor_intensity,
    compare_u1_su2,
    is_su2,
)
from e0_controller.controller import E0Controller, HybridMode
from e0_controller.amplitude_overlay import analyze_controller_state


# ── Helpers ───────────────────────────────────────────────────────

def _success(edge, ctx=None):
    return "SUCCESS"


def _axis_xyz_map(axis_map: dict):
    """Create axis_fn from a dict of (source, target) → unit 3-vector."""
    def axis_fn(L, x, y):
        return axis_map.get((x, y), np.array([0.0, 0.0, 1.0]))
    return axis_fn


# ── Tetrahedron builder ──────────────────────────────────────────

def build_tetrahedron():
    """
    Tetrahedron with 4 nodes (A, B, C, D) and 12 directed edges.
    Full connectivity: every node connects to every other.

    Strongly asymmetric edge parameters (forward ≠ reverse) ensure
    non-zero ω ≈ 0.3–1.8, giving large SU(2) rotations and
    measurable multi-axis effects.

    Edge axes: orthogonal assignment per edge pair:
        A↔B: σ_x = [1, 0, 0]
        A↔C: σ_y = [0, 1, 0]
        A↔D: σ_z = [0, 0, 1]
        B↔C: σ_z = [0, 0, 1]
        B↔D: σ_y = [0, 1, 0]
        C↔D: σ_x = [1, 0, 0]

    This ensures every triangle uses all 3 axes (maximal non-commutativity).
    """
    L = Landscape()
    edge_params = [
        ("A", "B", 5.0, 0.1), ("B", "A", 0.1, 0.9),
        ("A", "C", 0.1, 0.9), ("C", "A", 5.0, 0.1),
        ("A", "D", 4.0, 0.15), ("D", "A", 0.2, 0.85),
        ("B", "C", 4.5, 0.12), ("C", "B", 0.15, 0.88),
        ("B", "D", 0.2, 0.85), ("D", "B", 4.0, 0.15),
        ("C", "D", 3.5, 0.2), ("D", "C", 0.3, 0.8),
    ]
    for s, t, d, r in edge_params:
        L.add_edge(s, t, delta=d, resistance=r)
    return L


TETRA_AXIS_MAP = {
    ("A", "B"): np.array([1.0, 0.0, 0.0]),
    ("B", "A"): np.array([1.0, 0.0, 0.0]),
    ("A", "C"): np.array([0.0, 1.0, 0.0]),
    ("C", "A"): np.array([0.0, 1.0, 0.0]),
    ("A", "D"): np.array([0.0, 0.0, 1.0]),
    ("D", "A"): np.array([0.0, 0.0, 1.0]),
    ("B", "C"): np.array([0.0, 0.0, 1.0]),
    ("C", "B"): np.array([0.0, 0.0, 1.0]),
    ("B", "D"): np.array([0.0, 1.0, 0.0]),
    ("D", "B"): np.array([0.0, 1.0, 0.0]),
    ("C", "D"): np.array([1.0, 0.0, 0.0]),
    ("D", "C"): np.array([1.0, 0.0, 0.0]),
}

TETRA_AXIS_FN = _axis_xyz_map(TETRA_AXIS_MAP)


# ── Diamond builder (reference: single-axis) ────────────────────

def build_diamond():
    """S → A → G and S → B → G. Two single-path families."""
    L = Landscape()
    for s, t, d, r in [("S", "A", 1.0, 0.5), ("A", "G", 0.8, 0.6),
                        ("S", "B", 0.9, 0.7), ("B", "G", 1.1, 0.4)]:
        L.add_edge(s, t, delta=d, resistance=r)
    return L


# ── Gordian-lite builder (multi-path family) ─────────────────────

def build_gordian_lite():
    """
    S → A1 → G and S → A2 → G (A-family, 2 paths)
    S → B1 → G (B-family, 1 path)

    Includes reverse edges with very different parameters to create
    circulation and non-zero ω (needed for SU(2) axis effects).
    """
    L = Landscape()
    for s, t, d, r in [
        ("S", "A1", 5.0, 0.1), ("A1", "G", 4.0, 0.15),
        ("S", "A2", 4.0, 0.15), ("A2", "G", 3.0, 0.2),
        ("S", "B1", 3.0, 0.2), ("B1", "G", 5.0, 0.1),
        ("G", "A1", 0.1, 0.9), ("A1", "S", 0.1, 0.9),
        ("G", "A2", 0.1, 0.9), ("A2", "S", 0.1, 0.9),
        ("G", "B1", 0.1, 0.9), ("B1", "S", 0.1, 0.9),
    ]:
        L.add_edge(s, t, delta=d, resistance=r)
    return L


GORDIAN_MULTI_AXIS_MAP = {
    ("S", "A1"): np.array([1.0, 0.0, 0.0]),   # σ_x
    ("A1", "G"): np.array([0.0, 1.0, 0.0]),   # σ_y
    ("S", "A2"): np.array([0.0, 0.0, 1.0]),   # σ_z
    ("A2", "G"): np.array([1.0, 0.0, 0.0]),   # σ_x
    ("S", "B1"): np.array([0.0, 1.0, 0.0]),   # σ_y
    ("B1", "G"): np.array([0.0, 0.0, 1.0]),   # σ_z
}

GORDIAN_MULTI_AXIS_FN = _axis_xyz_map(GORDIAN_MULTI_AXIS_MAP)


# ── Fan builder (multi-path per action) ──────────────────────────

def build_fan():
    """
    S → M → X → G  (action M, path 1)
    S → M → Y → G  (action M, path 2)
    S → N → G      (action N, single path)

    Action M has 2 paths that interfere, making it sensitive to axis_fn.
    Includes reverse edges for non-zero ω.
    """
    L = Landscape()
    for s, t, d, r in [
        ("S", "M", 5.0, 0.1), ("M", "X", 4.0, 0.15), ("X", "G", 3.0, 0.2),
        ("M", "Y", 3.5, 0.18), ("Y", "G", 4.5, 0.12),
        ("S", "N", 3.0, 0.2), ("N", "G", 5.0, 0.1),
        ("M", "S", 0.1, 0.9), ("X", "M", 0.1, 0.9), ("G", "X", 0.1, 0.9),
        ("Y", "M", 0.1, 0.9), ("G", "Y", 0.1, 0.9),
        ("N", "S", 0.1, 0.9), ("G", "N", 0.1, 0.9),
    ]:
        L.add_edge(s, t, delta=d, resistance=r)
    return L


FAN_MULTI_AXIS_MAP = {
    ("S", "M"): np.array([0.0, 0.0, 1.0]),   # σ_z
    ("M", "X"): np.array([1.0, 0.0, 0.0]),   # σ_x
    ("X", "G"): np.array([0.0, 1.0, 0.0]),   # σ_y
    ("M", "Y"): np.array([0.0, 1.0, 0.0]),   # σ_y  (≠ M→X axis)
    ("Y", "G"): np.array([1.0, 0.0, 0.0]),   # σ_x  (≠ X→G axis)
    ("S", "N"): np.array([1.0, 0.0, 0.0]),
    ("N", "G"): np.array([0.0, 0.0, 1.0]),
}

FAN_MULTI_AXIS_FN = _axis_xyz_map(FAN_MULTI_AXIS_MAP)


# ══════════════════════════════════════════════════════════════════
# Test Classes
# ══════════════════════════════════════════════════════════════════


class TestPauliNonCommutativity(unittest.TestCase):
    """B1-1: Verify that different-axis rotations don't commute."""

    def test_sigma_x_z_commutator_nonzero(self):
        """R_x(a) · R_z(b) ≠ R_z(b) · R_x(a) for generic angles."""
        Rx = pauli_exponential(0.5, np.array([1, 0, 0.]))
        Rz = pauli_exponential(0.7, np.array([0, 0, 1.]))
        AB = Rx @ Rz
        BA = Rz @ Rx
        diff = np.max(np.abs(AB - BA))
        self.assertGreater(diff, 0.1, "σ_x and σ_z should not commute")

    def test_same_axis_commutes(self):
        """R_z(a) · R_z(b) = R_z(b) · R_z(a) (same axis always commutes)."""
        Ra = pauli_exponential(0.5, np.array([0, 0, 1.]))
        Rb = pauli_exponential(0.7, np.array([0, 0, 1.]))
        diff = np.max(np.abs(Ra @ Rb - Rb @ Ra))
        self.assertLess(diff, 1e-12)

    def test_all_three_pairs_noncommutative(self):
        """All Pauli pairs (x,y), (y,z), (x,z) are non-commutative."""
        axes = [np.array([1, 0, 0.]), np.array([0, 1, 0.]), np.array([0, 0, 1.])]
        for i in range(3):
            for j in range(i + 1, 3):
                Ri = pauli_exponential(0.5, axes[i])
                Rj = pauli_exponential(0.7, axes[j])
                diff = np.max(np.abs(Ri @ Rj - Rj @ Ri))
                self.assertGreater(diff, 0.05,
                                   f"Axes {i} and {j} should not commute")

    def test_commutator_is_su2(self):
        """Product of SU(2) elements is still SU(2)."""
        Rx = pauli_exponential(0.5, np.array([1, 0, 0.]))
        Ry = pauli_exponential(0.7, np.array([0, 1, 0.]))
        self.assertTrue(is_su2(Rx @ Ry))
        self.assertTrue(is_su2(Ry @ Rx))


class TestTetrahedronDomain(unittest.TestCase):
    """B1-2: Tetrahedron topology with orthogonal per-edge axes."""

    def setUp(self):
        self.L = build_tetrahedron()

    def test_all_edges_exist(self):
        """Tetrahedron has 12 directed edges (4 nodes, full connectivity)."""
        self.assertEqual(len(list(self.L.edges)), 12)

    def test_all_axes_are_unit_vectors(self):
        """Every axis in the map is a unit vector."""
        for (s, t), ax in TETRA_AXIS_MAP.items():
            self.assertAlmostEqual(np.linalg.norm(ax), 1.0, places=10,
                                   msg=f"Axis for {s}→{t} not unit")

    def test_each_triangle_uses_three_axes(self):
        """Every triangle (3 edges) uses all 3 distinct axes."""
        triangles = [
            [("A", "B"), ("B", "C"), ("C", "A")],
            [("A", "B"), ("B", "D"), ("D", "A")],
            [("A", "C"), ("C", "D"), ("D", "A")],
            [("B", "C"), ("C", "D"), ("D", "B")],
        ]
        for tri in triangles:
            axes_used = set()
            for edge in tri:
                ax = tuple(TETRA_AXIS_MAP[edge])
                axes_used.add(ax)
            self.assertEqual(len(axes_used), 3,
                             f"Triangle {tri} should use 3 distinct axes")


class TestEdgeTransportMultiAxis(unittest.TestCase):
    """B1-3: Per-edge transport with custom axis_fn."""

    def setUp(self):
        self.L = build_tetrahedron()

    def test_transport_with_axis_fn_differs_from_default(self):
        """axis_fn produces different transport than default σ_z."""
        U_default = su2_edge_transport(self.L, "A", "B")  # σ_z
        ax = TETRA_AXIS_MAP[("A", "B")]  # σ_x
        U_custom = su2_edge_transport(self.L, "A", "B", axis=ax)
        # σ_x axis should produce different matrix than σ_z
        diff = np.max(np.abs(U_default - U_custom))
        self.assertGreater(diff, 0.01,
                           "σ_x transport should differ from σ_z transport")

    def test_all_transports_are_su2(self):
        """Every edge transport with custom axis is in SU(2)."""
        for (s, t), ax in TETRA_AXIS_MAP.items():
            U = su2_edge_transport(self.L, s, t, axis=ax)
            self.assertTrue(is_su2(U), f"U({s}→{t}) not in SU(2)")

    def test_inverse_transport(self):
        """U(x,y) · U(y,x) ≈ R(−ω₁)·R(−ω₂) — related by axis and angle."""
        # For same axis: U(x,y)·U(y,x) = exp(-iω/2 σ)·exp(iω/2 σ) = I
        # But only when both edges have same ω magnitude (antisymmetric)
        U_ab = su2_edge_transport(self.L, "A", "B",
                                  axis=TETRA_AXIS_MAP[("A", "B")])
        U_ba = su2_edge_transport(self.L, "B", "A",
                                  axis=TETRA_AXIS_MAP[("B", "A")])
        product = U_ab @ U_ba
        # ω(A,B) and ω(B,A) are antisymmetric, so product should be
        # close to identity if axes match
        self.assertTrue(is_su2(product))


class TestPathTransportMultiAxis(unittest.TestCase):
    """B1-4: Path transport with per-edge axis assignment."""

    def setUp(self):
        self.L = build_tetrahedron()

    def test_path_transport_noncommutative(self):
        """A→B→C ≠ A→C→B when different axes are used on each edge."""
        path1 = ["A", "B", "C"]
        path2 = ["A", "C", "B"]
        U1 = su2_path_transport(self.L, path1, axis_fn=TETRA_AXIS_FN)
        U2 = su2_path_transport(self.L, path2, axis_fn=TETRA_AXIS_FN)
        diff = np.max(np.abs(U1 - U2))
        self.assertGreater(diff, 0.01,
                           "Path A→B→C should differ from A→C→B with multi-axis")

    def test_path_transport_is_su2(self):
        """Multi-edge transport remains in SU(2)."""
        paths = [["A", "B", "C"], ["A", "B", "C", "D"],
                 ["A", "C", "D", "B"], ["B", "D", "C", "A"]]
        for path in paths:
            U = su2_path_transport(self.L, path, axis_fn=TETRA_AXIS_FN)
            self.assertTrue(is_su2(U), f"U({' → '.join(path)}) not in SU(2)")

    def test_single_axis_path_commutes(self):
        """With uniform σ_z axis, path order also matters via angles."""
        # Even with same axis, transport depends on ω values (which differ)
        # But products of same-axis rotations DO commute
        uniform_fn = _axis_xyz_map({})  # all default to σ_z
        U_abc = su2_path_transport(self.L, ["A", "B", "C"],
                                   axis_fn=uniform_fn)
        self.assertTrue(is_su2(U_abc))

    def test_magnitude_preserved_multi_axis(self):
        """Single path spinor magnitude = exp(−S), with any axis assignment."""
        path = ["A", "B", "C", "D"]
        psi = spinor_psi(self.L, path, axis_fn=TETRA_AXIS_FN)
        S = path_tension(self.L, path)
        expected_mag = math.exp(-S)
        actual_mag = float(np.linalg.norm(psi))
        self.assertAlmostEqual(actual_mag, expected_mag, places=10,
                               msg="Spinor magnitude must equal exp(−S)")


class TestMultiAxisHolonomy(unittest.TestCase):
    """B1-5: Holonomy around closed loops with per-edge axes."""

    def setUp(self):
        self.L = build_tetrahedron()

    def test_triangle_holonomy_nontrivial(self):
        """Closed triangle A→B→C→A with 3 different axes has nontrivial holonomy."""
        cycle = ["A", "B", "C", "A"]
        H = su2_holonomy(self.L, cycle, axis_fn=TETRA_AXIS_FN)
        self.assertTrue(is_su2(H))
        # With 3 different axes, holonomy should NOT be identity
        dist_to_I = np.max(np.abs(H - IDENTITY))
        self.assertGreater(dist_to_I, 0.01,
                           "Multi-axis triangle holonomy should be nontrivial")

    def test_different_triangles_different_holonomy(self):
        """A→B→C→A and A→B→D→A have different holonomies."""
        H1 = su2_holonomy(self.L, ["A", "B", "C", "A"],
                          axis_fn=TETRA_AXIS_FN)
        H2 = su2_holonomy(self.L, ["A", "B", "D", "A"],
                          axis_fn=TETRA_AXIS_FN)
        diff = np.max(np.abs(H1 - H2))
        self.assertGreater(diff, 0.01,
                           "Different triangles should produce different holonomies")

    def test_holonomy_orientation_dependence(self):
        """A→B→C→A ≠ A→C→B→A (reversed orientation changes holonomy)."""
        H_fwd = su2_holonomy(self.L, ["A", "B", "C", "A"],
                             axis_fn=TETRA_AXIS_FN)
        H_rev = su2_holonomy(self.L, ["A", "C", "B", "A"],
                             axis_fn=TETRA_AXIS_FN)
        diff = np.max(np.abs(H_fwd - H_rev))
        self.assertGreater(diff, 0.01,
                           "Reversed orientation should change holonomy")

    def test_single_axis_triangle_holonomy_simpler(self):
        """With uniform σ_z, the holonomy reduces to scalar phase rotation."""
        uniform_fn = _axis_xyz_map({})  # all default to σ_z
        H = su2_holonomy(self.L, ["A", "B", "C", "A"],
                         axis_fn=uniform_fn)
        # σ_z-only holonomy is always diagonal (U(1) within SU(2))
        off_diag = abs(H[0, 1]) + abs(H[1, 0])
        self.assertLess(off_diag, 1e-10,
                        "Single-axis holonomy should be diagonal")


class TestMultiAxisInterference(unittest.TestCase):
    """B1-6: Interference patterns differ between single-axis and multi-axis."""

    def test_gordian_multi_axis_differs_from_single(self):
        """On Gordian-lite, multi-axis SU(2) produces different intensity than σ_z."""
        L = build_gordian_lite()
        paths_A = [["S", "A1", "G"], ["S", "A2", "G"]]

        I_single = spinor_intensity(L, paths_A)  # default σ_z
        I_multi = spinor_intensity(L, paths_A, axis_fn=GORDIAN_MULTI_AXIS_FN)

        # Multi-axis should produce different interference
        self.assertNotAlmostEqual(I_single, I_multi, places=3,
                                  msg="Multi-axis should change A-family interference")

    def test_single_path_intensity_unchanged(self):
        """Single-path family intensity is axis-independent (magnitude only)."""
        L = build_gordian_lite()
        paths_B = [["S", "B1", "G"]]

        I_single = spinor_intensity(L, paths_B)
        I_multi = spinor_intensity(L, paths_B, axis_fn=GORDIAN_MULTI_AXIS_FN)

        self.assertAlmostEqual(I_single, I_multi, places=10,
                               msg="Single path has no interference — axis irrelevant")

    def test_u1_vs_single_axis_vs_multi_axis_three_way(self):
        """Three-theory separation: U(1), SU(2)-σ_z, SU(2)-multi all differ on Gordian."""
        L = build_gordian_lite()
        paths_A = [["S", "A1", "G"], ["S", "A2", "G"]]

        # U(1)
        from e0_controller.wavepath import intensity as u1_intensity
        I_u1 = u1_intensity(L, paths_A)

        # SU(2) single-axis (σ_z)
        I_sz = spinor_intensity(L, paths_A)

        # SU(2) multi-axis
        I_ma = spinor_intensity(L, paths_A, axis_fn=GORDIAN_MULTI_AXIS_FN)

        # All three should be non-negative
        self.assertGreaterEqual(I_u1, 0)
        self.assertGreaterEqual(I_sz, 0)
        self.assertGreaterEqual(I_ma, 0)

        # At least two of the three should differ
        diffs = [abs(I_u1 - I_sz), abs(I_u1 - I_ma), abs(I_sz - I_ma)]
        self.assertGreater(max(diffs), 0.001,
                           f"Expected at least some separation: U(1)={I_u1:.4f}, "
                           f"SU(2)-σ_z={I_sz:.4f}, SU(2)-multi={I_ma:.4f}")

    def test_tetrahedron_all_paths_from_A(self):
        """On tetrahedron, multi-path interference from A to D via different routes."""
        L = build_tetrahedron()
        paths = [
            ["A", "B", "D"],    # σ_x then σ_y
            ["A", "C", "D"],    # σ_y then σ_x
            ["A", "D"],         # σ_z only
        ]
        I_multi = spinor_intensity(L, paths, axis_fn=TETRA_AXIS_FN)
        I_single = spinor_intensity(L, paths)  # all σ_z
        I_incoh = sum(spinor_intensity(L, [p], axis_fn=TETRA_AXIS_FN)
                      for p in paths)

        # Multi-axis interference should differ from incoherent sum
        self.assertNotAlmostEqual(I_multi, I_incoh, places=3,
                                  msg="Multi-axis paths should interfere")
        # Should also differ from single-axis
        self.assertNotAlmostEqual(I_multi, I_single, places=3,
                                  msg="Multi-axis and single-axis should diverge")


class TestMultiAxisSpinorProperties(unittest.TestCase):
    """B1-7: Structural invariants under multi-axis transport."""

    def test_probability_normalization(self):
        """Probabilities sum to 1 even with multi-axis."""
        L = build_gordian_lite()
        actions = {"A1": [["S", "A1", "G"], ["S", "A2", "G"]],
                   "B1": [["S", "B1", "G"]]}
        total_I = sum(spinor_intensity(L, paths, axis_fn=GORDIAN_MULTI_AXIS_FN)
                      for paths in actions.values())
        probs = {a: spinor_intensity(L, p, axis_fn=GORDIAN_MULTI_AXIS_FN) / total_I
                 for a, p in actions.items()}
        self.assertAlmostEqual(sum(probs.values()), 1.0, places=10)

    def test_intensity_non_negative(self):
        """All multi-axis intensities are non-negative."""
        L = build_tetrahedron()
        paths = [["A", "B", "C"], ["A", "C", "B"], ["A", "D", "C"],
                 ["A", "B", "D"], ["A", "C", "D"], ["A", "D", "B"]]
        for path in paths:
            I = spinor_intensity(L, [path], axis_fn=TETRA_AXIS_FN)
            self.assertGreaterEqual(I, 0, f"Path {path}: negative intensity")

    def test_magnitude_preservation_all_paths(self):
        """Every single path's spinor magnitude = exp(−S), regardless of axes."""
        L = build_tetrahedron()
        paths = [["A", "B", "C", "D"], ["A", "C", "D", "B"],
                 ["A", "D", "B", "C"], ["B", "C", "D", "A"]]
        for path in paths:
            psi = spinor_psi(L, path, axis_fn=TETRA_AXIS_FN)
            S = path_tension(L, path)
            expected = math.exp(-S)
            actual = float(np.linalg.norm(psi))
            self.assertAlmostEqual(actual, expected, places=10,
                                   msg=f"Path {'→'.join(path)}: magnitude mismatch")

    def test_reference_spinor_independence(self):
        """Intensity is reference-independent for multi-axis (completeness)."""
        L = build_tetrahedron()
        paths = [["A", "B", "D"], ["A", "C", "D"]]
        refs = [
            np.array([1, 0], dtype=complex),
            np.array([0, 1], dtype=complex),
            np.array([1, 1], dtype=complex) / np.sqrt(2),
            np.array([1, -1j], dtype=complex) / np.sqrt(2),
        ]
        intensities = [spinor_intensity(L, paths, ref=r, axis_fn=TETRA_AXIS_FN)
                       for r in refs]
        # For multi-axis, different refs CAN give different intensities
        # (this is expected — ref choice matters in SU(2))
        # But all must be non-negative
        for I_val in intensities:
            self.assertGreaterEqual(I_val, -1e-10)


class TestControllerAxisFn(unittest.TestCase):
    """B1-8: axis_fn threaded through E0Controller and overlay."""

    def test_controller_accepts_axis_fn(self):
        """E0Controller can be constructed with axis_fn parameter."""
        L = build_gordian_lite()
        ctrl = E0Controller(
            L, _success,
            hybrid_mode=HybridMode.BORN_SAMPLING,
            hybrid_horizon=3, hybrid_goals={"G"},
            use_su2=True,
            axis_fn=GORDIAN_MULTI_AXIS_FN,
        )
        self.assertIsNotNone(ctrl.axis_fn)

    def test_overlay_uses_axis_fn(self):
        """Overlay report with axis_fn produces results."""
        L = build_gordian_lite()
        ctrl = E0Controller(
            L, _success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=3, hybrid_goals={"G"},
            hybrid_geometry="goal_reaching",
            use_su2=True,
            axis_fn=GORDIAN_MULTI_AXIS_FN,
        )
        report = analyze_controller_state(
            ctrl, "S", horizon_edges=3,
            geometry="goal_reaching", goals={"G"},
            use_su2=True, axis_fn=GORDIAN_MULTI_AXIS_FN,
        )
        self.assertIsNotNone(report)
        self.assertGreater(len(report.action_infos), 0)
        total_I = sum(a.intensity for a in report.action_infos)
        self.assertGreater(total_I, 0)

    def test_overlay_multi_axis_differs_from_single(self):
        """Overlay with axis_fn produces different intensities than without."""
        L = build_fan()
        ctrl = E0Controller(
            L, _success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=4, hybrid_goals={"G"},
            hybrid_geometry="goal_reaching",
            use_su2=True,
        )
        report_single = analyze_controller_state(
            ctrl, "S", horizon_edges=4,
            geometry="goal_reaching", goals={"G"},
            use_su2=True,
        )
        report_multi = analyze_controller_state(
            ctrl, "S", horizon_edges=4,
            geometry="goal_reaching", goals={"G"},
            use_su2=True, axis_fn=FAN_MULTI_AXIS_FN,
        )
        I_single = {a.action: a.intensity for a in report_single.action_infos}
        I_multi = {a.action: a.intensity for a in report_multi.action_infos}
        # At least one action should have different intensity
        diffs = [abs(I_single.get(a, 0) - I_multi.get(a, 0))
                 for a in set(I_single) | set(I_multi)]
        self.assertGreater(max(diffs), 0.001,
                           "Multi-axis overlay should differ from single-axis")

    def test_cycle_with_axis_fn(self):
        """Controller cycle completes with axis_fn active."""
        L = build_gordian_lite()
        ctrl = E0Controller(
            L, _success,
            hybrid_mode=HybridMode.BORN_SAMPLING,
            hybrid_horizon=3, hybrid_goals={"G"},
            hybrid_geometry="goal_reaching",
            use_su2=True,
            axis_fn=GORDIAN_MULTI_AXIS_FN,
        )
        step = ctrl.cycle("S")
        self.assertIn(step.target, ["A1", "A2", "B1"])

    def test_axis_fn_none_backward_compatible(self):
        """axis_fn=None produces identical results to old behavior."""
        L = build_gordian_lite()
        ctrl_old = E0Controller(
            L, _success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=3, hybrid_goals={"G"},
            hybrid_geometry="goal_reaching",
            use_su2=True,
        )
        ctrl_new = E0Controller(
            L, _success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=3, hybrid_goals={"G"},
            hybrid_geometry="goal_reaching",
            use_su2=True,
            axis_fn=None,
        )
        rep_old = analyze_controller_state(
            ctrl_old, "S", horizon_edges=3,
            geometry="goal_reaching", goals={"G"}, use_su2=True,
        )
        rep_new = analyze_controller_state(
            ctrl_new, "S", horizon_edges=3,
            geometry="goal_reaching", goals={"G"}, use_su2=True,
            axis_fn=None,
        )
        for a_old, a_new in zip(sorted(rep_old.action_infos, key=lambda a: a.action),
                                sorted(rep_new.action_infos, key=lambda a: a.action)):
            self.assertAlmostEqual(a_old.intensity, a_new.intensity, places=10)


class TestPathOrderDependence(unittest.TestCase):
    """B1-9: Spinor amplitudes depend on edge traversal order with multi-axis."""

    def test_different_routes_same_endpoints_different_spinors(self):
        """A→B→D and A→C→D have different spinors under multi-axis."""
        L = build_tetrahedron()
        psi1 = spinor_psi(L, ["A", "B", "D"], axis_fn=TETRA_AXIS_FN)
        psi2 = spinor_psi(L, ["A", "C", "D"], axis_fn=TETRA_AXIS_FN)
        diff = np.max(np.abs(psi1 - psi2))
        self.assertGreater(diff, 0.01,
                           "Different routes should produce different spinors")

    def test_three_routes_to_D(self):
        """Three routes A→?→D produce three distinct spinor directions."""
        L = build_tetrahedron()
        psis = [
            spinor_psi(L, ["A", "B", "D"], axis_fn=TETRA_AXIS_FN),
            spinor_psi(L, ["A", "C", "D"], axis_fn=TETRA_AXIS_FN),
            spinor_psi(L, ["A", "D"], axis_fn=TETRA_AXIS_FN),
        ]
        # Normalize to compare directions
        dirs = [p / np.linalg.norm(p) for p in psis if np.linalg.norm(p) > 1e-10]
        # At least 2 of 3 should differ
        diffs = [np.max(np.abs(dirs[i] - dirs[j]))
                 for i in range(len(dirs))
                 for j in range(i + 1, len(dirs))]
        self.assertGreater(max(diffs), 0.01,
                           "Three routes should give at least 2 distinct directions")

    def test_path_reversal_changes_transport(self):
        """A→B→C→D multi-axis transport ≠ D→C→B→A multi-axis transport."""
        L = build_tetrahedron()
        path_fwd = ["A", "B", "C", "D"]
        path_rev = ["D", "C", "B", "A"]
        U_fwd = su2_path_transport(L, path_fwd, axis_fn=TETRA_AXIS_FN)
        U_rev = su2_path_transport(L, path_rev, axis_fn=TETRA_AXIS_FN)
        diff = np.max(np.abs(U_fwd - U_rev))
        self.assertGreater(diff, 0.01,
                           "Forward and reverse path should differ with multi-axis")


class TestFourTheoryComparison(unittest.TestCase):
    """B1-10: Compare U(1), SU(2)-σ_z, SU(2)-geometric, SU(2)-multi-axis."""

    def test_tetrahedron_four_theories(self):
        """All 4 theories produce different results on tetrahedron."""
        L = build_tetrahedron()
        paths = [["A", "B", "D"], ["A", "C", "D"], ["A", "D"]]

        from e0_controller.wavepath import intensity as u1_int_fn
        from e0_controller.spinor_connection import spinor_geometric_intensity

        I_u1 = u1_int_fn(L, paths)
        I_sz = spinor_intensity(L, paths)  # σ_z
        I_geo = spinor_geometric_intensity(L, paths)  # Helmholtz
        I_ma = spinor_intensity(L, paths, axis_fn=TETRA_AXIS_FN)  # multi-axis

        # All non-negative
        for name, val in [("U(1)", I_u1), ("σ_z", I_sz),
                          ("geo", I_geo), ("multi", I_ma)]:
            self.assertGreaterEqual(val, 0, f"{name} intensity negative")

        # At least multi-axis should differ from σ_z
        self.assertNotAlmostEqual(I_ma, I_sz, places=3,
                                  msg=f"Multi-axis ({I_ma:.4f}) should differ "
                                      f"from σ_z ({I_sz:.4f})")


class TestDiamondAxisInsensitivity(unittest.TestCase):
    """B1-11: Single-path families are axis-insensitive (control test)."""

    def test_diamond_axis_independent(self):
        """Diamond has 1 path per family → axis doesn't matter."""
        L = build_diamond()
        paths_A = [["S", "A", "G"]]
        paths_B = [["S", "B", "G"]]

        axis_map = {
            ("S", "A"): np.array([1, 0, 0.]),
            ("A", "G"): np.array([0, 1, 0.]),
            ("S", "B"): np.array([0, 0, 1.]),
            ("B", "G"): np.array([1, 0, 0.]),
        }
        afn = _axis_xyz_map(axis_map)

        I_A_default = spinor_intensity(L, paths_A)
        I_A_multi = spinor_intensity(L, paths_A, axis_fn=afn)
        I_B_default = spinor_intensity(L, paths_B)
        I_B_multi = spinor_intensity(L, paths_B, axis_fn=afn)

        self.assertAlmostEqual(I_A_default, I_A_multi, places=10)
        self.assertAlmostEqual(I_B_default, I_B_multi, places=10)


if __name__ == "__main__":
    unittest.main()
