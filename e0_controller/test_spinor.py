"""
E₀ Spinor Tests — SU(2) Extension Formal Verification
========================================================
Tests for the SU(2) lift of the scalar U(1) phase layer.

Verified findings:
    F1. SU(2) primitives correct (Pauli algebra, det=1, unitarity)
    F2. Single-path magnitudes match U(1) (no intensity change without interference)
    F3. Phase halving Θ → Θ/2 changes interference patterns (Spinor double-cover)
    F4. 720° periodicity: exp(-iπσ) = -𝕀, exp(-i2πσ) = +𝕀  (algebraic)
    F5. Non-commutativity: multi-axis SU(2) produces [σ_i, σ_j] ≠ 0
    F6. All transport matrices are SU(2) members (det=1, U†U=𝕀)
    F7. Holonomy is well-defined on graph loops

Phase 4 research — NOT integrated into controller.
"""

import math
import sys
import os
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from e0_controller.landscape import Landscape
from e0_controller.connection import omega, theta
from e0_controller.wavepath import psi, intensity, path_tension
from e0_controller.spinor_connection import (
    pauli_exponential, su2_edge_transport, su2_path_transport,
    su2_holonomy, spinor_psi, spinor_sum_paths, spinor_intensity,
    compare_u1_su2, spinor_path_analysis,
    is_identity, is_minus_identity, is_su2,
    SIGMA_X, SIGMA_Y, SIGMA_Z, IDENTITY, SPINOR_UP,
    su2_connection, su2_geometric_transport,
    su2_geometric_path_transport, spinor_geometric_psi,
    spinor_geometric_intensity, compare_minimal_geometric,
    connection_analysis,
)


# ── Domain Builders ────────────────────────────────────────────────

def build_gordian_trap() -> Landscape:
    L = Landscape()
    L.add_edge("START", "A1", delta=0.3, resistance=0.3)
    L.add_edge("A1", "A2", delta=0.4, resistance=0.3)
    L.add_edge("A2", "GOAL", delta=0.4, resistance=0.3)
    L.add_edge("A1", "L1", delta=2.0, resistance=0.05)
    L.add_edge("L1", "L2", delta=2.0, resistance=0.05)
    L.add_edge("L2", "L3", delta=2.0, resistance=0.05)
    L.add_edge("L3", "GOAL", delta=2.0, resistance=0.05)
    L.add_edge("START", "B1", delta=0.5, resistance=0.4)
    L.add_edge("B1", "B2", delta=0.3, resistance=0.35)
    L.add_edge("B2", "GOAL", delta=0.3, resistance=0.3)
    return L


def build_multi_axis_domain() -> Landscape:
    L = Landscape()
    L.add_edge("S", "A", delta=0.5, resistance=0.3)
    L.add_edge("A", "B", delta=0.5, resistance=0.3)
    L.add_edge("B", "GOAL", delta=0.3, resistance=0.3)
    L.add_edge("A", "S", delta=1.5, resistance=0.1)
    L.add_edge("B", "A", delta=1.5, resistance=0.1)
    L.add_edge("S", "C", delta=0.4, resistance=0.4)
    L.add_edge("C", "GOAL", delta=0.4, resistance=0.3)
    return L


def build_phase_loop(n_edges: int = 6) -> tuple:
    L = Landscape()
    loop_states = ["S"] + [f"N{i}" for i in range(1, n_edges)] + ["S"]
    for i in range(n_edges):
        src = loop_states[i]
        tgt = loop_states[i + 1] if i < n_edges - 1 else "S"
        L.add_edge(src, tgt, delta=2.5, resistance=0.05)
    L.add_edge(loop_states[n_edges - 1] if n_edges > 1 else "S",
               "GOAL", delta=0.3, resistance=0.3)
    L.add_edge("S", "D", delta=0.3, resistance=0.3)
    L.add_edge("D", "GOAL", delta=0.3, resistance=0.3)
    return L, loop_states


def triangle_axis_fn(L, x, y):
    axis_map = {
        ("S", "A"): np.array([0, 0, 1.0]),
        ("A", "S"): np.array([0, 0, 1.0]),
        ("A", "B"): np.array([1.0, 0, 0]),
        ("B", "A"): np.array([1.0, 0, 0]),
        ("B", "GOAL"): np.array([0, 1.0, 0]),
        ("S", "C"): np.array([0, 0, 1.0]),
        ("C", "GOAL"): np.array([0, 0, 1.0]),
    }
    return axis_map.get((x, y), np.array([0, 0, 1.0]))


# ═══════════════════════════════════════════════════════════════════
# Class 1: Pauli Algebra Fundamentals
# ═══════════════════════════════════════════════════════════════════

class TestPauliAlgebra(unittest.TestCase):
    """F1: Pauli matrices and SU(2) exponential are algebraically correct."""

    def test_pauli_anticommutation(self):
        """σ_i · σ_j + σ_j · σ_i = 2δ_{ij} · 𝕀"""
        sigmas = [SIGMA_X, SIGMA_Y, SIGMA_Z]
        for i in range(3):
            for j in range(3):
                anti = sigmas[i] @ sigmas[j] + sigmas[j] @ sigmas[i]
                expected = 2 * IDENTITY if i == j else np.zeros((2, 2))
                np.testing.assert_allclose(anti, expected, atol=1e-14)

    def test_pauli_hermitian(self):
        """Each σ_i is Hermitian: σ_i† = σ_i."""
        for sigma in [SIGMA_X, SIGMA_Y, SIGMA_Z]:
            np.testing.assert_allclose(sigma.conj().T, sigma, atol=1e-14)

    def test_pauli_traceless(self):
        """tr(σ_i) = 0."""
        for sigma in [SIGMA_X, SIGMA_Y, SIGMA_Z]:
            self.assertAlmostEqual(np.trace(sigma), 0.0, places=14)

    def test_pauli_det_minus_one(self):
        """det(σ_i) = -1."""
        for sigma in [SIGMA_X, SIGMA_Y, SIGMA_Z]:
            self.assertAlmostEqual(np.linalg.det(sigma), -1.0, places=14)

    def test_exponential_identity_at_zero(self):
        """exp(0 · σ) = 𝕀."""
        for axis in [np.array([1, 0, 0.]), np.array([0, 1, 0.]), np.array([0, 0, 1.])]:
            U = pauli_exponential(0.0, axis)
            self.assertTrue(is_identity(U))

    def test_exponential_is_su2(self):
        """exp(-iθ/2 · n̂·σ) ∈ SU(2) for all angles and axes."""
        angles = [0.0, 0.5, math.pi, 2.3, 4 * math.pi, -1.7]
        axes = [np.array([1, 0, 0.]), np.array([0, 1, 0.]),
                np.array([0, 0, 1.]), np.array([1, 1, 0.]) / math.sqrt(2)]
        for angle in angles:
            for axis in axes:
                U = pauli_exponential(angle, axis)
                self.assertTrue(is_su2(U),
                                f"Not SU(2) at θ={angle:.2f}, n̂={axis}")

    def test_determinant_always_one(self):
        """det(U) = 1 for all SU(2) elements."""
        for angle in [0.3, 1.0, math.pi, 3.0]:
            U = pauli_exponential(angle, np.array([0, 0, 1.]))
            self.assertAlmostEqual(abs(np.linalg.det(U)), 1.0, places=12)


# ═══════════════════════════════════════════════════════════════════
# Class 2: 720° Periodicity
# ═══════════════════════════════════════════════════════════════════

class TestPeriodiciy720(unittest.TestCase):
    """F4: SU(2) double cover — 360° gives -𝕀, 720° gives +𝕀."""

    def test_360_gives_minus_identity_z(self):
        """exp(-iπ · σ_z) = -𝕀."""
        U = pauli_exponential(2 * math.pi, np.array([0, 0, 1.]))
        self.assertTrue(is_minus_identity(U))

    def test_720_gives_plus_identity_z(self):
        """exp(-i2π · σ_z) = +𝕀."""
        U = pauli_exponential(4 * math.pi, np.array([0, 0, 1.]))
        self.assertTrue(is_identity(U))

    def test_360_gives_minus_identity_x(self):
        """exp(-iπ · σ_x) = -𝕀."""
        U = pauli_exponential(2 * math.pi, np.array([1., 0, 0]))
        self.assertTrue(is_minus_identity(U))

    def test_720_gives_plus_identity_x(self):
        """exp(-i2π · σ_x) = +𝕀."""
        U = pauli_exponential(4 * math.pi, np.array([1., 0, 0]))
        self.assertTrue(is_identity(U))

    def test_360_gives_minus_identity_arbitrary_axis(self):
        """exp(-iπ · n̂·σ) = -𝕀 for any unit axis n̂."""
        n = np.array([1, 2, 3.])
        n = n / np.linalg.norm(n)
        U = pauli_exponential(2 * math.pi, n)
        self.assertTrue(is_minus_identity(U))

    def test_720_gives_plus_identity_arbitrary_axis(self):
        """exp(-i2π · n̂·σ) = +𝕀 for any unit axis n̂."""
        n = np.array([1, 2, 3.])
        n = n / np.linalg.norm(n)
        U = pauli_exponential(4 * math.pi, n)
        self.assertTrue(is_identity(U))

    def test_spinor_sign_flip_at_2pi(self):
        """A spinor |↑⟩ picks up a -1 sign after 2π rotation."""
        U = pauli_exponential(2 * math.pi, np.array([0, 0, 1.]))
        rotated = U @ SPINOR_UP
        np.testing.assert_allclose(rotated, -SPINOR_UP, atol=1e-14)


# ═══════════════════════════════════════════════════════════════════
# Class 3: Single-Path Magnitude Consistency
# ═══════════════════════════════════════════════════════════════════

class TestSinglePathMagnitude(unittest.TestCase):
    """F2: ‖Ψ_SU2(p)‖ = |Ψ_U1(p)| = exp(-S) for every individual path."""

    def setUp(self):
        self.L = build_gordian_trap()
        self.paths = {
            "A-short": ["START", "A1", "A2", "GOAL"],
            "A-loop": ["START", "A1", "L1", "L2", "L3", "GOAL"],
            "B-path": ["START", "B1", "B2", "GOAL"],
        }

    def test_magnitude_matches_per_path(self):
        """For each path, ‖Ψ_SU2‖ = |Ψ_U1| = exp(-S)."""
        for name, path in self.paths.items():
            u1_mag = abs(psi(self.L, path))
            su2_mag = np.linalg.norm(spinor_psi(self.L, path))
            s = path_tension(self.L, path)
            expected = math.exp(-s)
            self.assertAlmostEqual(u1_mag, expected, places=10, msg=name)
            self.assertAlmostEqual(su2_mag, expected, places=10, msg=name)

    def test_single_path_intensity_matches(self):
        """For a single-path set, I_SU2 = I_U1 (no interference)."""
        for name, path in self.paths.items():
            u1_I = intensity(self.L, [path])
            su2_I = spinor_intensity(self.L, [path])
            self.assertAlmostEqual(su2_I, u1_I, places=10, msg=name)

    def test_transport_matrix_is_su2(self):
        """U(p) ∈ SU(2) for every path."""
        for name, path in self.paths.items():
            U = su2_path_transport(self.L, path)
            self.assertTrue(is_su2(U), f"{name}: U not in SU(2)")


# ═══════════════════════════════════════════════════════════════════
# Class 4: Phase Halving — The Central Finding
# ═══════════════════════════════════════════════════════════════════

class TestPhaseHalving(unittest.TestCase):
    """F3: SU(2) halves the phase angle Θ→Θ/2, changing interference.

    This is the core spinor double-cover effect:
    - U(1): phase = Θ
    - SU(2) σ_z: phase = Θ/2
    - When ΔΘ ≈ π (destructive in U(1)), ΔΘ/2 ≈ π/2 (orthogonal in SU(2))
    """

    def setUp(self):
        self.L = build_gordian_trap()
        self.a_short = ["START", "A1", "A2", "GOAL"]
        self.a_loop = ["START", "A1", "L1", "L2", "L3", "GOAL"]
        self.b_path = ["START", "B1", "B2", "GOAL"]

    def test_u1_a1_destructive_interference(self):
        """U(1): A1 action has strong destructive interference (I < 0.05)."""
        u1_I = intensity(self.L, [self.a_short, self.a_loop])
        self.assertLess(u1_I, 0.05, "A1 should be destructive in U(1)")

    def test_su2_a1_no_destructive_interference(self):
        """SU(2): A1 action does NOT have destructive interference (I > 0.5)."""
        su2_I = spinor_intensity(self.L, [self.a_short, self.a_loop])
        self.assertGreater(su2_I, 0.5, "A1 should NOT be destructive in SU(2)")

    def test_phase_halving_mechanism(self):
        """The SU(2) first component carries exp(-iΘ/2), not exp(iΘ).

        For σ_z axis: U|↑⟩ = exp(-iΘ/2)|↑⟩
        So the first component phase = -Θ/2.
        """
        for path in [self.a_short, self.a_loop, self.b_path]:
            theta_path = theta(self.L, path)
            psi_su2 = spinor_psi(self.L, path)
            # First component carries all the amplitude (σ_z preserves |↑⟩ direction)
            phase_su2 = np.angle(psi_su2[0])
            expected_phase = -theta_path / 2
            # Phases modulo 2π
            diff = (phase_su2 - expected_phase + math.pi) % (2 * math.pi) - math.pi
            self.assertAlmostEqual(diff, 0.0, places=8,
                                   msg=f"Phase halving failed on {path}")

    def test_relative_phase_shift(self):
        """U(1) ΔΘ ≈ π (destructive) → SU(2) ΔΘ/2 ≈ π/2 (orthogonal).

        This IS the spinor double-cover effect on a real E₀ domain.
        """
        theta_short = theta(self.L, self.a_short)
        theta_loop = theta(self.L, self.a_loop)
        delta_theta = theta_loop - theta_short  # U(1) relative phase

        # U(1): ΔΘ should be near π → cos(ΔΘ) ≈ -1 (strong destructive)
        cos_u1 = math.cos(delta_theta)
        self.assertLess(cos_u1, -0.8, "U(1) should be near-destructive")

        # SU(2): ΔΘ/2 should be near π/2 → cos(ΔΘ/2) ≈ 0 (orthogonal)
        cos_su2 = math.cos(delta_theta / 2)
        self.assertLess(abs(cos_su2), 0.2,
                        "SU(2) relative phase should be near-orthogonal")

        # Key: SU(2) has LESS destructive interference (|cos| closer to 0)
        self.assertLess(abs(cos_su2), abs(cos_u1),
                        "SU(2) phase halving should reduce destructive interference")

    def test_winner_changes_u1_vs_su2(self):
        """In U(1), B1 wins over A1 due to destructive interference.
        In SU(2), A1 wins over B1 because interference is not destructive.
        """
        u1_A1 = intensity(self.L, [self.a_short, self.a_loop])
        u1_B1 = intensity(self.L, [self.b_path])
        su2_A1 = spinor_intensity(self.L, [self.a_short, self.a_loop])
        su2_B1 = spinor_intensity(self.L, [self.b_path])

        self.assertGreater(u1_B1, u1_A1, "U(1): B1 should win")
        self.assertGreater(su2_A1, su2_B1, "SU(2): A1 should win")

    def test_b1_identical_both_theories(self):
        """B1 has only one path, so no interference → same in both.
        This confirms the deviation comes from interference, not per-path error.
        """
        u1_B1 = intensity(self.L, [self.b_path])
        su2_B1 = spinor_intensity(self.L, [self.b_path])
        self.assertAlmostEqual(u1_B1, su2_B1, places=10)


# ═══════════════════════════════════════════════════════════════════
# Class 5: Non-Commutativity
# ═══════════════════════════════════════════════════════════════════

class TestNonCommutativity(unittest.TestCase):
    """F5: Multi-axis SU(2) produces genuinely non-commutative transport."""

    def setUp(self):
        self.L = build_multi_axis_domain()

    def test_commutator_nonzero(self):
        """[U(S→A), U(A→B)] ≠ 0 when axes differ (σ_z vs σ_x)."""
        U_SA = su2_edge_transport(self.L, "S", "A", np.array([0, 0, 1.]))
        U_AB = su2_edge_transport(self.L, "A", "B", np.array([1., 0, 0]))
        commutator = U_AB @ U_SA - U_SA @ U_AB
        norm = np.linalg.norm(commutator)
        self.assertGreater(norm, 1e-6, "Should be non-commutative")

    def test_same_axis_commutes(self):
        """[U_1, U_2] = 0 when both use σ_z."""
        U_SA = su2_edge_transport(self.L, "S", "A", np.array([0, 0, 1.]))
        U_AB = su2_edge_transport(self.L, "A", "B", np.array([0, 0, 1.]))
        commutator = U_AB @ U_SA - U_SA @ U_AB
        norm = np.linalg.norm(commutator)
        self.assertLess(norm, 1e-12, "Same-axis should commute")

    def test_multi_axis_spinor_has_second_component(self):
        """Multi-axis transport rotates |↑⟩ into both components of ℂ²."""
        path = ["S", "A", "B", "GOAL"]
        psi_vec = spinor_psi(self.L, path, axis_fn=triangle_axis_fn)
        # With mixed axes, second component should be nonzero
        self.assertGreater(abs(psi_vec[1]), 1e-6,
                           "Multi-axis should populate both spinor components")

    def test_z_axis_spinor_stays_in_first_component(self):
        """σ_z-only transport keeps |↑⟩ in the first component."""
        L = build_gordian_trap()
        for path in [["START", "A1", "A2", "GOAL"],
                     ["START", "B1", "B2", "GOAL"]]:
            psi_vec = spinor_psi(L, path)
            self.assertAlmostEqual(abs(psi_vec[1]), 0.0, places=14,
                                   msg=f"σ_z should keep second component zero")

    def test_multi_axis_preserves_magnitude(self):
        """Multi-axis U is unitary, so ‖Ψ‖ = exp(-S) regardless of axis choice."""
        path = ["S", "A", "B", "GOAL"]
        s = path_tension(self.L, path)
        psi_vec = spinor_psi(self.L, path, axis_fn=triangle_axis_fn)
        self.assertAlmostEqual(np.linalg.norm(psi_vec), math.exp(-s), places=10)


# ═══════════════════════════════════════════════════════════════════
# Class 6: Graph Holonomy
# ═══════════════════════════════════════════════════════════════════

class TestGraphHolonomy(unittest.TestCase):
    """F6/F7: SU(2) holonomy on actual graph loops."""

    def test_trivial_path_is_identity(self):
        """Zero-length path → U = 𝕀."""
        L = build_gordian_trap()
        U = su2_path_transport(L, ["START"])
        self.assertTrue(is_identity(U))

    def test_loop_holonomy_is_su2(self):
        """U(cycle) ∈ SU(2) for graph loops."""
        L, loop_states = build_phase_loop(n_edges=6)
        U = su2_holonomy(L, loop_states)
        self.assertTrue(is_su2(U))

    def test_loop_holonomy_nontrivial(self):
        """Non-trivial loop has U ≠ 𝕀 (nontrivial holonomy)."""
        L, loop_states = build_phase_loop(n_edges=6)
        U = su2_holonomy(L, loop_states)
        self.assertFalse(is_identity(U), "Loop should have nontrivial holonomy")

    def test_holonomy_depends_on_loop_size(self):
        """Different loop sizes produce different holonomy."""
        traces = []
        for n in [3, 5, 8]:
            L, loop_states = build_phase_loop(n_edges=n)
            U = su2_holonomy(L, loop_states)
            traces.append(complex(np.trace(U)))
        # All traces should be different
        for i in range(len(traces)):
            for j in range(i + 1, len(traces)):
                self.assertGreater(abs(traces[i] - traces[j]), 0.01,
                                   f"Loops n={[3,5,8][i]} and n={[3,5,8][j]} "
                                   f"should have different holonomy")

    def test_holonomy_approaches_periodicity(self):
        """Large enough loops approach 2π holonomy → tr(U) approaches -2."""
        # n=6 gives Θ ≈ 379° ≈ 2π + 19°, so tr(U) should be near -2
        L, loop_states = build_phase_loop(n_edges=6)
        U = su2_holonomy(L, loop_states)
        tr = np.trace(U).real
        self.assertLess(tr, -1.5, "6-edge loop should approach tr≈-2 (near 2π)")


# ═══════════════════════════════════════════════════════════════════
# Class 7: Structural Properties
# ═══════════════════════════════════════════════════════════════════

class TestStructuralProperties(unittest.TestCase):
    """Cross-domain structural invariants."""

    def test_compare_returns_correct_fields(self):
        """compare_u1_su2() returns all expected fields."""
        L = build_gordian_trap()
        cmp = compare_u1_su2(L, [["START", "B1", "B2", "GOAL"]])
        for key in ["u1_psi", "u1_intensity", "su2_psi", "su2_intensity",
                     "ratio", "deviation_pct"]:
            self.assertIn(key, cmp)

    def test_empty_path_gives_identity(self):
        """Empty path → U = 𝕀, Ψ = |ref⟩."""
        L = build_gordian_trap()
        U = su2_path_transport(L, [])
        self.assertTrue(is_identity(U))

    def test_single_state_path_gives_identity(self):
        """Single-state path → U = 𝕀."""
        L = build_gordian_trap()
        U = su2_path_transport(L, ["START"])
        self.assertTrue(is_identity(U))

    def test_inadmissible_path_gives_zero_spinor(self):
        """Path with infinite tension → Ψ = [0, 0]."""
        L = Landscape()
        L.add_edge("A", "B", delta=0.5, resistance=0.3)
        # C→D doesn't exist → infinite tension
        psi_vec = spinor_psi(L, ["A", "B", "C"])
        np.testing.assert_allclose(psi_vec, [0, 0], atol=1e-14)

    def test_spinor_intensity_non_negative(self):
        """I = ‖Ψ‖² ≥ 0 always."""
        L = build_gordian_trap()
        paths = [["START", "A1", "A2", "GOAL"],
                 ["START", "A1", "L1", "L2", "L3", "GOAL"],
                 ["START", "B1", "B2", "GOAL"]]
        I = spinor_intensity(L, paths)
        self.assertGreaterEqual(I, 0.0)

    def test_reference_spinor_choice_independence(self):
        """Different reference spinors give same intensity for single paths."""
        L = build_gordian_trap()
        path = ["START", "A1", "A2", "GOAL"]
        I_up = spinor_intensity(L, [path], ref=np.array([1., 0], dtype=complex))
        I_down = spinor_intensity(L, [path], ref=np.array([0., 1], dtype=complex))
        # Both should be exp(-2S) since U is unitary
        s = path_tension(L, path)
        expected = math.exp(-2 * s)
        self.assertAlmostEqual(I_up, expected, places=10)
        self.assertAlmostEqual(I_down, expected, places=10)


# ═══════════════════════════════════════════════════════════════════
# Class 8: Geometric Coupling (Phase 4b)
# ═══════════════════════════════════════════════════════════════════

def build_triangle_domain():
    """Dense 3-node graph with all 6 directed edges — maximizes A₂."""
    L = Landscape()
    L.add_edge("A", "B", delta=3.0, resistance=0.2)
    L.add_edge("B", "C", delta=2.0, resistance=0.3)
    L.add_edge("C", "A", delta=1.5, resistance=0.4)
    L.add_edge("A", "C", delta=1.0, resistance=0.5)
    L.add_edge("B", "A", delta=0.8, resistance=0.3)
    L.add_edge("C", "B", delta=2.5, resistance=0.25)
    return L


class TestGeometricCoupling(unittest.TestCase):
    """Phase 4b: Axis n̂ derived from local Helmholtz vorticity."""

    @classmethod
    def setUpClass(cls):
        cls.L_gordian = build_gordian_trap()
        cls.L_tri = build_triangle_domain()

    # ── Antisymmetry ────────────────────────────────────────────

    def test_connection_antisymmetric(self):
        """A⃗(y,x) = −A⃗(x,y) for all edges."""
        for edge in self.L_gordian.edges:
            x, y = edge.source, edge.target
            A_xy = su2_connection(self.L_gordian, x, y)
            A_yx = su2_connection(self.L_gordian, y, x)
            np.testing.assert_allclose(
                A_xy, -A_yx, atol=1e-12,
                err_msg=f"Antisymmetry violated on {x}→{y}")

    def test_transport_reversal(self):
        """U_geo(y,x) = U_geo(x,y)† for all edges."""
        for edge in self.L_gordian.edges:
            x, y = edge.source, edge.target
            U_xy = su2_geometric_transport(self.L_gordian, x, y)
            U_yx = su2_geometric_transport(self.L_gordian, y, x)
            np.testing.assert_allclose(
                U_yx, U_xy.conj().T, atol=1e-12,
                err_msg=f"Transport reversal violated on {x}→{y}")

    # ── SU(2) membership ──────────────────────────────────────

    def test_geometric_transport_is_su2(self):
        """All geometric transport matrices are SU(2): det=1, U†U=𝕀."""
        for edge in self.L_gordian.edges:
            U = su2_geometric_transport(
                self.L_gordian, edge.source, edge.target)
            self.assertTrue(is_su2(U),
                            f"{edge.source}→{edge.target}: not SU(2)")

    def test_geometric_path_transport_is_su2(self):
        """Path transport is SU(2) even with off-axis components."""
        path = ["START", "A1", "L1", "L2", "L3", "GOAL"]
        U = su2_geometric_path_transport(self.L_gordian, path)
        self.assertTrue(is_su2(U))

    # ── Connection vector structure ────────────────────────────

    def test_A3_equals_omega(self):
        """Third component A₃ = ω(x,y) — the direct connection."""
        for edge in self.L_gordian.edges:
            x, y = edge.source, edge.target
            A = su2_connection(self.L_gordian, x, y)
            w = omega(self.L_gordian, x, y)
            self.assertAlmostEqual(A[2], w, places=12,
                                   msg=f"A₃ ≠ ω on {x}→{y}")

    def test_vorticity_gradient_nonzero(self):
        """A₁ (vorticity gradient) is non-zero on edges with asymmetric neighborhoods."""
        # A1→A2 has neighbors A1:{A2,L1,START→via back}, A2:{GOAL}
        A = su2_connection(self.L_gordian, "A1", "A2")
        self.assertGreater(abs(A[0]), 0.1,
                           "A₁ should be significant on A1→A2")

    def test_face_holonomy_nonzero_on_triangle(self):
        """A₂ (face holonomy) is non-zero on fully connected triangle."""
        A = su2_connection(self.L_tri, "A", "B")
        self.assertGreater(abs(A[1]), 0.1,
                           "A₂ should be non-zero on triangle domain")

    def test_face_holonomy_zero_on_dag(self):
        """A₂ = 0 on Gordian Trap (DAG with no directed triangles)."""
        for edge in self.L_gordian.edges:
            x, y = edge.source, edge.target
            A = su2_connection(self.L_gordian, x, y)
            self.assertAlmostEqual(A[1], 0.0, places=12,
                                   msg=f"A₂ should be 0 on DAG edge {x}→{y}")

    # ── U(1) reduction ───────────────────────────────────────────

    def test_single_path_matches_u1(self):
        """Single-path intensity: U(1) = SU(2)-min = SU(2)-geo."""
        path = ["START", "B1", "B2", "GOAL"]
        cmp = compare_minimal_geometric(self.L_gordian, [path])
        self.assertAlmostEqual(
            cmp["u1_intensity"], cmp["geometric_intensity"], places=10)
        self.assertAlmostEqual(
            cmp["minimal_intensity"], cmp["geometric_intensity"], places=10)

    def test_leaf_edge_matches_minimal(self):
        """Edge to leaf node (no other neighbors) has A₁ = 0 → geo = min."""
        # B2→GOAL: B2 has one outgoing edge (GOAL), GOAL has none
        A = su2_connection(self.L_gordian, "B2", "GOAL")
        self.assertAlmostEqual(A[0], 0.0, places=12, msg="A₁ should be 0")
        self.assertAlmostEqual(A[1], 0.0, places=12, msg="A₂ should be 0")
        # Transport should match minimal
        U_min = su2_edge_transport(self.L_gordian, "B2", "GOAL")
        U_geo = su2_geometric_transport(self.L_gordian, "B2", "GOAL")
        np.testing.assert_allclose(U_geo, U_min, atol=1e-12)

    # ── Divergence ─────────────────────────────────────────────

    def test_geometric_diverges_on_interference(self):
        """Geometric coupling changes interference on Gordian A-short+loop."""
        paths = [["START", "A1", "A2", "GOAL"],
                 ["START", "A1", "L1", "L2", "L3", "GOAL"]]
        cmp = compare_minimal_geometric(self.L_gordian, paths)
        self.assertGreater(cmp["geo_vs_min_pct"], 10.0,
                           "Geometric should diverge >10% from minimal on interference")

    def test_triangle_geometric_diverges(self):
        """Triangle domain: face holonomy drives geo ≠ min."""
        paths = [["A", "B", "C"], ["A", "C"]]
        cmp = compare_minimal_geometric(self.L_tri, paths)
        self.assertGreater(cmp["geo_vs_min_pct"], 10.0,
                           "Triangle domain should show >10% geo vs min divergence")

    def test_geometric_intensity_non_negative(self):
        """Geometric intensity I ≥ 0 on all domains."""
        for L, paths in [
            (self.L_gordian, [["START", "A1", "A2", "GOAL"],
                              ["START", "B1", "B2", "GOAL"]]),
            (self.L_tri, [["A", "B", "C"], ["A", "C"]]),
        ]:
            I = spinor_geometric_intensity(L, paths)
            self.assertGreaterEqual(I, 0.0)


# ═══════════════════════════════════════════════════════════════════
# Class 10: SU(2) Controller Integration (Paper 2 §5.4)
# ═══════════════════════════════════════════════════════════════════

class TestSU2ControllerOverlay(unittest.TestCase):
    """Verify the SU(2) switch in amplitude_overlay produces correct results."""

    @classmethod
    def setUpClass(cls):
        from e0_controller.controller import E0Controller, HybridMode
        from e0_controller.primitives import Outcome

        cls.E0Controller = E0Controller
        cls.HybridMode = HybridMode
        cls.Outcome = Outcome

        cls.L = build_gordian_trap()
        cls.ctrl = E0Controller(cls.L, lambda s, t: Outcome.SUCCESS,
                                hybrid_mode=HybridMode.GREEDY)

    @staticmethod
    def _acs(*args, **kwargs):
        from e0_controller.amplitude_overlay import analyze_controller_state
        return analyze_controller_state(*args, **kwargs)

    def test_su2_intensities_differ_from_u1_on_gordian(self):
        """SU(2) intensity diverges from U(1) on multi-path Gordian A-family."""
        r_u1 = self._acs(self.ctrl, "START", horizon_edges=4,
                         goals={"GOAL"}, use_su2=False)
        r_su2 = self._acs(self.ctrl, "START", horizon_edges=4,
                          goals={"GOAL"}, use_su2=True)
        i_u1_a1 = next(a for a in r_u1.action_infos if a.action == "A1")
        i_su2_a1 = next(a for a in r_su2.action_infos if a.action == "A1")
        # Phase halving increases A1 intensity under SU(2)
        self.assertGreater(i_su2_a1.intensity, i_u1_a1.intensity * 1.3,
                           "SU(2) should boost A1 via phase halving (>30% increase)")

    def test_su2_single_path_matches_u1(self):
        """Single-path B-family intensity: SU(2) ≈ U(1) (no multi-path interference)."""
        r_u1 = self._acs(self.ctrl, "START", horizon_edges=4,
                            goals={"GOAL"}, use_su2=False)
        r_su2 = self._acs(self.ctrl, "START", horizon_edges=4,
                             goals={"GOAL"}, use_su2=True)
        i_u1_b1 = next(a for a in r_u1.action_infos if a.action == "B1")
        i_su2_b1 = next(a for a in r_su2.action_infos if a.action == "B1")
        # B-family has only one path → no interference → U(1) ≈ SU(2)
        self.assertAlmostEqual(i_su2_b1.intensity, i_u1_b1.intensity,
                               delta=i_u1_b1.intensity * 0.05,
                               msg="B1 should be nearly identical (single-path)")

    def test_su2_probability_sharper_on_gordian(self):
        """SU(2) produces sharper probability distribution (higher P for winner)."""
        r_u1 = self._acs(self.ctrl, "START", horizon_edges=4,
                            goals={"GOAL"}, use_su2=False)
        r_su2 = self._acs(self.ctrl, "START", horizon_edges=4,
                             goals={"GOAL"}, use_su2=True)
        p_u1_a1 = next(a for a in r_u1.action_infos if a.action == "A1").probability
        p_su2_a1 = next(a for a in r_su2.action_infos if a.action == "A1").probability
        self.assertGreater(p_su2_a1, p_u1_a1,
                           "SU(2) should give A1 higher P (sharper discrimination)")

    def test_su2_hybrid_reaches_goal(self):
        """E₀ hybrid with SU(2) reaches GOAL on Gordian trap."""
        L = build_gordian_trap()
        ctrl = self.E0Controller(
            L, lambda s, t: self.Outcome.SUCCESS,
            hybrid_mode=self.HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=4, hybrid_goals={"GOAL"}, use_su2=True,
        )
        trace = ctrl.run("START", goal="GOAL", max_cycles=10)
        self.assertIn("GOAL", trace.path)

    def test_su2_flag_false_matches_default(self):
        """use_su2=False should produce identical results to no flag."""
        r_default = self._acs(self.ctrl, "START", horizon_edges=4,
                                 goals={"GOAL"})
        r_explicit = self._acs(self.ctrl, "START", horizon_edges=4,
                                  goals={"GOAL"}, use_su2=False)
        for a_d, a_e in zip(
            sorted(r_default.action_infos, key=lambda a: a.action),
            sorted(r_explicit.action_infos, key=lambda a: a.action),
        ):
            self.assertAlmostEqual(a_d.intensity, a_e.intensity, places=12)


if __name__ == "__main__":
    unittest.main(verbosity=2)
