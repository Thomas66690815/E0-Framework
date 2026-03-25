"""
E₀ Omega Uniqueness Tests — Phase Generator Falsification
============================================================
Numerical verification of the Uniqueness Conjecture from
E0_THETA_ANTISYMMETRY_DERIVATION_v0:

    Among linear phase generators satisfying axioms A1–A4,
    ω(x,y) = ½(v_rot(x,y) − v_rot(y,x)) is unique (up to scale).

Five alternative candidates are tested. Each violates at least one axiom
or structural requirement, while the true ω satisfies all.

Axioms:
    A1 — Orientation:      ω(x,y) = −ω(y,x)
    A3 — Gauge invariance: ω depends only on v_rot (gradient-independent)
    A4 — Reciprocity:      v_rot(x,y) = v_rot(y,x) ⟹ ω(x,y) = 0

Structural requirements:
    P1 — Non-degeneracy:   Nonzero holonomy on loops with asymmetric v_rot
    P2 — Correct interference: R_coh matches the true theory

Elimination:
    ω_sym   → ✗ A1, ✗ A4
    ω_full  → ✗ A1
    ω_v     → ✗ A1
    ω_grad  → ✗ P1 (always zero holonomy — degenerate)
    ω_nonlin → ✗ P2 (wrong interference — not a linear 1-form)
    ω_true  → ✓ all
"""

import math
import sys
import os
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from e0_controller.landscape import Landscape
from e0_controller.connection import omega, theta, holonomy
from e0_controller.potential import v_rot, v_grad, v_raw, phi_map, decomposition_table
from e0_controller.wavepath import psi, sum_paths, intensity
from e0_controller.explore_omega_uniqueness import (
    omega_true, omega_sym, omega_full, omega_v, omega_grad, omega_nonlin,
    build_diamond, build_triangle, build_asymmetric_triangle, build_gordian,
    path_phase, interference_with_candidate, _safe_vrot,
)


# ── Helpers ────────────────────────────────────────────────────────

def all_edge_pairs(L: Landscape):
    """Yield (source, target) for all edges."""
    for e in L.edges:
        yield e.source, e.target


def bidirectional_pairs(L: Landscape):
    """Yield (x, y) for edges where both x→y and y→x exist."""
    for e in L.edges:
        x, y = e.source, e.target
        if L.difference(y, x) is not None:
            yield x, y


# ═══════════════════════════════════════════════════════════════════
# 1. True ω Satisfies All Axioms
# ═══════════════════════════════════════════════════════════════════

class TestTrueOmegaAxioms(unittest.TestCase):
    """The true ω = ½(v_rot(x,y) − v_rot(y,x)) satisfies A1, A3, A4."""

    def test_A1_orientation_diamond(self):
        """ω(x,y) = −ω(y,x) on Diamond domain."""
        L = build_diamond()
        for x, y in all_edge_pairs(L):
            self.assertAlmostEqual(
                omega_true(L, x, y), -omega_true(L, y, x), places=12,
                msg=f"A1 failed on {x}→{y}")

    def test_A1_orientation_asymmetric_triangle(self):
        L = build_asymmetric_triangle()
        for x, y in all_edge_pairs(L):
            self.assertAlmostEqual(
                omega_true(L, x, y), -omega_true(L, y, x), places=12)

    def test_A1_orientation_gordian(self):
        L = build_gordian()
        for x, y in all_edge_pairs(L):
            self.assertAlmostEqual(
                omega_true(L, x, y), -omega_true(L, y, x), places=12)

    def test_A4_reciprocity_symmetric_triangle(self):
        """On symmetric triangle: v_rot(x,y) = v_rot(y,x) → ω = 0."""
        L = build_triangle()
        for x, y in bidirectional_pairs(L):
            vr_xy = _safe_vrot(L, x, y)
            vr_yx = _safe_vrot(L, y, x)
            self.assertAlmostEqual(vr_xy, vr_yx, places=10,
                                   msg=f"v_rot not symmetric on {x}↔{y}")
            self.assertAlmostEqual(omega_true(L, x, y), 0.0, places=12,
                                   msg=f"A4 failed: ω≠0 on symmetric {x}→{y}")

    def test_A3_matches_standard_omega(self):
        """omega_true produces same values as connection.omega."""
        for builder in [build_diamond, build_asymmetric_triangle, build_gordian]:
            L = builder()
            for x, y in all_edge_pairs(L):
                self.assertAlmostEqual(
                    omega_true(L, x, y), omega(L, x, y), places=12,
                    msg=f"omega_true ≠ omega on {x}→{y}")

    def test_P1_nonzero_holonomy_on_asymmetric_loop(self):
        """Asymmetric triangle: ω_true produces nonzero loop holonomy."""
        L = build_asymmetric_triangle()
        hol = abs(path_phase(L, ["A", "B", "C", "A"], omega_true))
        self.assertGreater(hol, 0.01)


# ═══════════════════════════════════════════════════════════════════
# 2. ω_sym Violates A1 and A4
# ═══════════════════════════════════════════════════════════════════

class TestOmegaSymElimination(unittest.TestCase):
    """ω_sym = ½(v_rot(x,y) + v_rot(y,x)) fails orientation and reciprocity."""

    def test_A1_violation_on_diamond(self):
        """ω_sym(x,y) ≠ −ω_sym(y,x) on asymmetric edges."""
        L = build_diamond()
        max_viol = 0.0
        for x, y in bidirectional_pairs(L):
            viol = abs(omega_sym(L, x, y) + omega_sym(L, y, x))
            max_viol = max(max_viol, viol)
        self.assertGreater(max_viol, 0.1, "Expected A1 violation for ω_sym")

    def test_A4_violation_on_symmetric_triangle(self):
        """Symmetric v_rot → ω_sym ≠ 0."""
        L = build_triangle()
        for x, y in bidirectional_pairs(L):
            vr_xy = _safe_vrot(L, x, y)
            vr_yx = _safe_vrot(L, y, x)
            if abs(vr_xy - vr_yx) < 1e-10:
                self.assertGreater(
                    abs(omega_sym(L, x, y)), 0.1,
                    f"Expected A4 violation: ω_sym≠0 on symmetric {x}→{y}")
                return
        self.fail("No symmetric v_rot pair found")


# ═══════════════════════════════════════════════════════════════════
# 3. ω_full Violates A1
# ═══════════════════════════════════════════════════════════════════

class TestOmegaFullElimination(unittest.TestCase):
    """ω_full = v_rot(x,y) is not antisymmetric."""

    def test_A1_violation(self):
        L = build_diamond()
        max_viol = 0.0
        for x, y in bidirectional_pairs(L):
            viol = abs(omega_full(L, x, y) + omega_full(L, y, x))
            max_viol = max(max_viol, viol)
        self.assertGreater(max_viol, 0.1, "Expected A1 violation for ω_full")

    def test_not_equal_to_true_omega(self):
        """ω_full ≠ ω_true on asymmetric edges."""
        L = build_diamond()
        diffs = [abs(omega_full(L, x, y) - omega_true(L, x, y))
                 for x, y in all_edge_pairs(L)]
        self.assertGreater(max(diffs), 0.01)


# ═══════════════════════════════════════════════════════════════════
# 4. ω_v Violates A1
# ═══════════════════════════════════════════════════════════════════

class TestOmegaVElimination(unittest.TestCase):
    """ω_v = v(x,y) — full field, no Helmholtz — fails orientation."""

    def test_A1_violation(self):
        L = build_diamond()
        max_viol = 0.0
        for x, y in bidirectional_pairs(L):
            viol = abs(omega_v(L, x, y) + omega_v(L, y, x))
            max_viol = max(max_viol, viol)
        self.assertGreater(max_viol, 0.1, "Expected A1 violation for ω_v")

    def test_includes_gradient_contamination(self):
        """ω_v includes v_grad, so it's NOT gauge-invariant."""
        L = build_diamond()
        for x, y in all_edge_pairs(L):
            vg = v_grad(L, x, y)
            if abs(vg) > 0.01:
                # v(x,y) = v_grad + v_rot → v(x,y) ≠ v_rot
                self.assertNotAlmostEqual(
                    omega_v(L, x, y), omega_full(L, x, y), places=2,
                    msg="Expected gradient contamination")
                return
        self.fail("No edge with significant v_grad found")


# ═══════════════════════════════════════════════════════════════════
# 5. ω_grad Is Degenerate (Zero Holonomy)
# ═══════════════════════════════════════════════════════════════════

class TestOmegaGradElimination(unittest.TestCase):
    """ω_grad = v_grad(x,y) = Φ(x)−Φ(y) telescopes → zero holonomy."""

    def test_A1_satisfied(self):
        """v_grad IS antisymmetric: Φ(x)−Φ(y) = −(Φ(y)−Φ(x))."""
        L = build_diamond()
        for x, y in all_edge_pairs(L):
            self.assertAlmostEqual(
                omega_grad(L, x, y), -omega_grad(L, y, x), places=12)

    def test_P1_zero_holonomy_symmetric_triangle(self):
        """Holonomy = 0 on symmetric triangle."""
        L = build_triangle()
        hol = path_phase(L, ["A", "B", "C", "A"], omega_grad)
        self.assertAlmostEqual(hol, 0.0, places=10)

    def test_P1_zero_holonomy_asymmetric_triangle(self):
        """Holonomy = 0 on asymmetric triangle — gradient always telescopes."""
        L = build_asymmetric_triangle()
        hol = path_phase(L, ["A", "B", "C", "A"], omega_grad)
        self.assertAlmostEqual(hol, 0.0, places=10)

    def test_gradient_telescopes_on_any_path(self):
        """Σ v_grad along any path = Φ(start) − Φ(end)."""
        L = build_gordian()
        pm = phi_map(L)
        for path in [["START", "A1", "A2", "GOAL"],
                     ["START", "A1", "L1", "L2", "L3", "GOAL"],
                     ["START", "B1", "B2", "GOAL"]]:
            theta_grad = path_phase(L, path, omega_grad)
            phi_diff = pm[path[0]] - pm[path[-1]]
            self.assertAlmostEqual(theta_grad, phi_diff, places=10,
                                   msg=f"Telescope failed on {path}")

    def test_all_paths_same_phase(self):
        """All paths from START→GOAL have identical ω_grad phase → no interference."""
        L = build_gordian()
        paths = [
            ["START", "A1", "A2", "GOAL"],
            ["START", "A1", "L1", "L2", "L3", "GOAL"],
            ["START", "B1", "B2", "GOAL"],
        ]
        phases = [path_phase(L, p, omega_grad) for p in paths]
        for p in phases[1:]:
            self.assertAlmostEqual(p, phases[0], places=10,
                                   msg="Gradient phase should be path-independent")


# ═══════════════════════════════════════════════════════════════════
# 6. ω_nonlin Produces Wrong Interference
# ═══════════════════════════════════════════════════════════════════

class TestOmegaNonlinElimination(unittest.TestCase):
    """ω_nonlin = sign(d)·d² where d=v_rot(x,y)−v_rot(y,x).
    Antisymmetric but nonlinear → different interference predictions."""

    def test_A1_satisfied(self):
        """Nonlinear candidate IS antisymmetric."""
        L = build_asymmetric_triangle()
        for x, y in all_edge_pairs(L):
            self.assertAlmostEqual(
                omega_nonlin(L, x, y), -omega_nonlin(L, y, x), places=12)

    def test_A4_satisfied(self):
        """On symmetric edges, d=0 → ω_nonlin=0."""
        L = build_triangle()
        for x, y in bidirectional_pairs(L):
            vr_xy = _safe_vrot(L, x, y)
            vr_yx = _safe_vrot(L, y, x)
            if abs(vr_xy - vr_yx) < 1e-10:
                self.assertAlmostEqual(omega_nonlin(L, x, y), 0.0, places=12)

    def test_P2_wrong_interference_on_gordian(self):
        """ω_nonlin produces significantly different R_coh than ω_true."""
        L = build_gordian()
        paths = [
            ["START", "A1", "A2", "GOAL"],
            ["START", "A1", "L1", "L2", "L3", "GOAL"],
            ["START", "B1", "B2", "GOAL"],
        ]
        I_true, _, R_true = interference_with_candidate(L, paths, omega_true)
        I_nonlin, _, R_nonlin = interference_with_candidate(L, paths, omega_nonlin)
        # R_coh should differ significantly
        self.assertGreater(abs(R_true - R_nonlin) / max(R_true, 0.01), 0.3,
                           f"Expected >30% R_coh divergence: true={R_true:.3f}, "
                           f"nonlin={R_nonlin:.3f}")

    def test_nonlin_disagrees_with_standard_theory(self):
        """ω_nonlin ≠ ω_true on Gordian edges (different per-edge values)."""
        L = build_gordian()
        diffs = [abs(omega_nonlin(L, x, y) - omega_true(L, x, y))
                 for x, y in all_edge_pairs(L)]
        self.assertGreater(max(diffs), 0.01)


# ═══════════════════════════════════════════════════════════════════
# 7. Helmholtz Orthogonality
# ═══════════════════════════════════════════════════════════════════

class TestHelmholtzOrthogonality(unittest.TestCase):
    """v_grad ⊥ v_rot in the edge inner product space."""

    def test_orthogonality_diamond(self):
        """⟨v_grad, v_rot⟩_E = Σ_e v_grad(e)·v_rot(e) ≈ 0."""
        L = build_diamond()
        dot = 0.0
        for e in L.edges:
            vg = v_grad(L, e.source, e.target)
            vr = v_rot(L, e.source, e.target)
            if vr is not None:
                dot += vg * vr
        self.assertAlmostEqual(dot, 0.0, places=8,
                               msg=f"Orthogonality failed: dot={dot}")

    def test_orthogonality_asymmetric_triangle(self):
        L = build_asymmetric_triangle()
        dot = 0.0
        for e in L.edges:
            vg = v_grad(L, e.source, e.target)
            vr = v_rot(L, e.source, e.target)
            if vr is not None:
                dot += vg * vr
        self.assertAlmostEqual(dot, 0.0, places=8)

    def test_orthogonality_gordian(self):
        L = build_gordian()
        dot = 0.0
        for e in L.edges:
            vg = v_grad(L, e.source, e.target)
            vr = v_rot(L, e.source, e.target)
            if vr is not None:
                dot += vg * vr
        self.assertAlmostEqual(dot, 0.0, places=8)


# ═══════════════════════════════════════════════════════════════════
# 8. Uniqueness Synthesis
# ═══════════════════════════════════════════════════════════════════

class TestUniquenessSynthesis(unittest.TestCase):
    """Cross-domain elimination: only ω_true survives all axioms."""

    def test_only_true_omega_passes_all_on_asymmetric(self):
        """On asymmetric triangle (loop + asymmetric v_rot):
        ω_true is the only linear candidate satisfying A1 + A4 + P1."""
        L = build_asymmetric_triangle()
        loop = ["A", "B", "C", "A"]

        # ω_true: A1 ✓, A4 ✓, P1 ✓
        for x, y in all_edge_pairs(L):
            self.assertAlmostEqual(
                omega_true(L, x, y), -omega_true(L, y, x), places=12)
        hol_true = abs(path_phase(L, loop, omega_true))
        self.assertGreater(hol_true, 0.01)

        # ω_sym: A1 ✗
        max_viol = max(abs(omega_sym(L, x, y) + omega_sym(L, y, x))
                       for x, y in all_edge_pairs(L))
        self.assertGreater(max_viol, 0.1)

        # ω_full: A1 ✗
        max_viol = max(abs(omega_full(L, x, y) + omega_full(L, y, x))
                       for x, y in all_edge_pairs(L))
        self.assertGreater(max_viol, 0.1)

        # ω_grad: P1 ✗
        hol_grad = abs(path_phase(L, loop, omega_grad))
        self.assertAlmostEqual(hol_grad, 0.0, places=10)

    def test_true_omega_correct_interference_on_gordian(self):
        """ω_true matches the standard wavepath intensity on Gordian."""
        L = build_gordian()
        paths = [
            ["START", "A1", "A2", "GOAL"],
            ["START", "A1", "L1", "L2", "L3", "GOAL"],
            ["START", "B1", "B2", "GOAL"],
        ]
        I_standard = intensity(L, paths)
        I_true, _, _ = interference_with_candidate(L, paths, omega_true)
        self.assertAlmostEqual(I_true, I_standard, places=6,
                               msg="ω_true must reproduce standard theory")

    def test_gradient_only_removes_all_interference(self):
        """Using ω_grad: all paths have same phase → R_coh maximal (no cancellation)."""
        L = build_gordian()
        paths = [
            ["START", "A1", "A2", "GOAL"],
            ["START", "A1", "L1", "L2", "L3", "GOAL"],
            ["START", "B1", "B2", "GOAL"],
        ]
        _, _, R_grad = interference_with_candidate(L, paths, omega_grad)
        _, _, R_true = interference_with_candidate(L, paths, omega_true)
        # Gradient: all phases equal → constructive, R_coh high
        # True: phase differences → destructive, R_coh lower
        self.assertGreater(R_grad, R_true,
                           "Gradient-only should be more 'constructive' "
                           "(no phase distinction → no destructive interference)")


# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    unittest.main()
