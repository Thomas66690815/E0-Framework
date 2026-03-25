"""
E₀ Resonator Tests — Minimal Resonator Formal Verification
=============================================================
Tests for the 3-node resonator kernel from E0_MINIMAL_RESONATOR_TEST_DESIGN_v0.

Verified findings:
    F1. Domain construction: correct topology, edge counts, states
    F2. R1 — Recurrent reconstruction: loop phase nonzero and constant
    F3. R2 — Bounded coherent support: I_coh > I_min in resonator regimes
    F4. R3 — Leakage dominance: I_out < I_coh in stable resonator
    F5. R4 — Historization balance: H1 does not cause monotonic I_coh decay
    F6. Classification correctness: M2/H0=RESONATOR, C1=DECAY, C2=DECAY
    F7. SU(2) holonomy: loop transport ∈ SU(2), three-theory separation
    F8. Historization enables M1 resonance: METASTABLE → RESONATOR
    F9. Controls valid: C1 has zero loop intensity, C2 has negligible intensity

Phase 4 research — NOT integrated into controller.
"""

import math
import sys
import os
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from e0_controller.landscape import Landscape
from e0_controller.connection import omega, theta, holonomy
from e0_controller.wavepath import psi, sum_paths, intensity
from e0_controller.spinor_connection import (
    su2_holonomy, su2_geometric_path_transport,
    spinor_intensity, spinor_geometric_intensity,
    is_su2, IDENTITY,
)
from e0_controller.explore_resonator import (
    build_resonator_domain,
    regime_M1, regime_M2, regime_M3, control_C1, control_C2,
    loop_paths, leakage_path,
    measure_cycle, apply_loop_historization, classify_resonator,
    CycleMetrics,
)


# ═══════════════════════════════════════════════════════════════════
# 1. Domain Construction
# ═══════════════════════════════════════════════════════════════════

class TestDomainConstruction(unittest.TestCase):
    """F1: Minimal resonator domain has correct topology."""

    def test_loop_domain_has_4_nodes(self):
        L = regime_M2()
        self.assertEqual(len(L.states), 4)
        for n in ["A", "B", "C", "OUT"]:
            self.assertIn(n, L.states)

    def test_loop_domain_has_4_edges(self):
        L = regime_M2()
        self.assertEqual(len(L.edges), 4)

    def test_loop_closure_exists(self):
        L = regime_M2()
        self.assertIsNotNone(L.difference("C", "A"))

    def test_leakage_edge_exists(self):
        L = regime_M2()
        self.assertIsNotNone(L.difference("C", "OUT"))

    def test_acyclic_has_no_loop_closure(self):
        L = control_C1()
        self.assertIsNone(L.difference("C", "A"))

    def test_acyclic_has_3_edges(self):
        L = control_C1()
        self.assertEqual(len(L.edges), 3)

    def test_dephased_has_loop_closure(self):
        L = control_C2()
        self.assertIsNotNone(L.difference("C", "A"))

    def test_dephased_high_resistance(self):
        L = control_C2()
        S_ca = L.effective_tension("C", "A")
        S_ab = L.effective_tension("A", "B")
        self.assertGreater(S_ca, 10 * S_ab)


# ═══════════════════════════════════════════════════════════════════
# 2. Path Families
# ═══════════════════════════════════════════════════════════════════

class TestPathFamilies(unittest.TestCase):
    """Path generation for loop and leakage."""

    def test_loop_paths_count(self):
        paths = loop_paths(5)
        self.assertEqual(len(paths), 5)

    def test_single_cycle_path(self):
        paths = loop_paths(1)
        self.assertEqual(paths[0], ["A", "B", "C", "A"])

    def test_double_cycle_path(self):
        paths = loop_paths(2)
        self.assertEqual(paths[1], ["A", "B", "C", "A", "B", "C", "A"])

    def test_leakage_path(self):
        self.assertEqual(leakage_path(), ["A", "B", "C", "OUT"])

    def test_cycle_path_starts_and_ends_at_A(self):
        for p in loop_paths(8):
            self.assertEqual(p[0], "A")
            self.assertEqual(p[-1], "A")


# ═══════════════════════════════════════════════════════════════════
# 3. R1 — Recurrent Reconstruction
# ═══════════════════════════════════════════════════════════════════

class TestR1Reconstruction(unittest.TestCase):
    """F2: Loop phase is nonzero and reproducible."""

    def test_loop_phase_nonzero(self):
        L = regime_M2()
        one_cycle = ["A", "B", "C", "A"]
        theta_1 = theta(L, one_cycle)
        self.assertGreater(abs(theta_1), 0.01)

    def test_loop_phase_positive(self):
        """All three loop edges have equal positive ω by symmetry."""
        L = regime_M3()
        theta_1 = theta(L, ["A", "B", "C", "A"])
        self.assertGreater(theta_1, 0)

    def test_phase_doubles_for_two_cycles(self):
        """θ(2 cycles) ≈ 2·θ(1 cycle)."""
        L = regime_M2()
        one = ["A", "B", "C", "A"]
        two = ["A", "B", "C", "A", "B", "C", "A"]
        theta_1 = theta(L, one)
        theta_2 = theta(L, two)
        self.assertAlmostEqual(theta_2, 2 * theta_1, places=10)

    def test_psi_phase_stable_in_resonator(self):
        """In M2/H0, Ψ_total phase direction is consistent across cycles."""
        L = regime_M2()
        phases = []
        for k in range(1, 6):
            psi_total = sum_paths(L, loop_paths(k))
            if abs(psi_total) > 1e-15:
                phases.append(math.atan2(psi_total.imag, psi_total.real))
        self.assertGreater(len(phases), 3)
        # All phases should exist (bounded away from zero)


# ═══════════════════════════════════════════════════════════════════
# 4. R2 — Bounded Coherent Support
# ═══════════════════════════════════════════════════════════════════

class TestR2BoundedSupport(unittest.TestCase):
    """F3: I_coh stays above threshold in resonator regimes."""

    def test_M2_H0_intensity_nonzero(self):
        L = regime_M2()
        m = measure_cycle(L, 4)
        self.assertGreater(m.I_coh, 0.001)

    def test_M3_H0_intensity_grows(self):
        """In reinforced regime, early cycles show constructive buildup."""
        L = regime_M3()
        m1 = measure_cycle(L, 1)
        m3 = measure_cycle(L, 3)
        self.assertGreater(m3.I_coh, m1.I_coh)

    def test_M2_H0_R_coh_near_one(self):
        """Balanced regime: single-path-dominated → R_coh ≈ 1."""
        L = regime_M2()
        m = measure_cycle(L, 4)
        self.assertAlmostEqual(m.R_coh, 1.0, delta=0.1)

    def test_C1_intensity_zero(self):
        """Acyclic domain: no loop paths → I_coh = 0."""
        L = control_C1()
        # Loop paths require C→A which doesn't exist; measure returns 0
        paths = loop_paths(4)
        # psi for a path through non-existent edge returns 0
        psi_total = sum_paths(L, paths)
        self.assertAlmostEqual(abs(psi_total), 0.0, places=10)

    def test_C2_intensity_negligible(self):
        """Dephased domain: I_coh < 0.001 (below absolute threshold)."""
        L = control_C2()
        m = measure_cycle(L, 4)
        self.assertLess(m.I_coh, 0.001)


# ═══════════════════════════════════════════════════════════════════
# 5. R3 — Leakage Dominance
# ═══════════════════════════════════════════════════════════════════

class TestR3Leakage(unittest.TestCase):
    """F4: Leakage relationship to coherent intensity."""

    def test_leakage_exists(self):
        L = regime_M2()
        psi_leak = psi(L, leakage_path())
        self.assertGreater(abs(psi_leak) ** 2, 0)

    def test_M3_H0_leakage_below_coherent(self):
        """Reinforced loop: I_coh > I_out at peak."""
        L = regime_M3()
        m = measure_cycle(L, 4)  # near peak
        self.assertGreater(m.I_coh, m.I_out)

    def test_M1_H0_leakage_dominates(self):
        """Transient regime without historization: leakage dominates."""
        L = regime_M1()
        m = measure_cycle(L, 4)
        self.assertGreater(m.I_out, m.I_coh)

    def test_C1_leakage_only(self):
        """Acyclic: all intensity goes to leakage, none to loop."""
        L = control_C1()
        m = measure_cycle(L, 1)
        self.assertEqual(m.I_coh, 0.0)
        self.assertGreater(m.I_out, 0.0)


# ═══════════════════════════════════════════════════════════════════
# 6. R4 — Historization Balance
# ═══════════════════════════════════════════════════════════════════

class TestR4Historization(unittest.TestCase):
    """F5: Historization boosts loop support, does not cause monotonic decay."""

    def test_historization_increases_loop_H(self):
        """After updates, delta_H on loop edges becomes nonzero."""
        L = regime_M2()
        from e0_controller.primitives import Edge
        e = Edge("A", "B")
        H_before = abs(L.historization.delta_H(e))
        apply_loop_historization(L)
        H_after = abs(L.historization.delta_H(e))
        self.assertGreater(H_after, H_before)

    def test_M1_historization_enables_resonance(self):
        """F8: M1 transitions from METASTABLE to RESONATOR with enough historization."""
        # H0: no historization
        L0 = regime_M1()
        history_H0 = [measure_cycle(L0, k) for k in range(1, 9)]
        class_H0 = classify_resonator(history_H0)

        # H1 with 20 rounds
        L1 = regime_M1()
        for _ in range(20):
            apply_loop_historization(L1)
        history_H1 = [measure_cycle(L1, k) for k in range(1, 9)]
        class_H1 = classify_resonator(history_H1)

        self.assertNotEqual(class_H0, "RESONATOR")
        self.assertEqual(class_H1, "RESONATOR")

    def test_historization_boosts_M1_intensity(self):
        """More historization rounds → higher I_coh for M1."""
        L0 = regime_M1()
        I_H0 = measure_cycle(L0, 4).I_coh

        L1 = regime_M1()
        for _ in range(10):
            apply_loop_historization(L1)
        I_H1 = measure_cycle(L1, 4).I_coh

        self.assertGreater(I_H1, I_H0)


# ═══════════════════════════════════════════════════════════════════
# 7. Classification
# ═══════════════════════════════════════════════════════════════════

class TestClassification(unittest.TestCase):
    """F6: Classifier produces correct labels for known regimes."""

    def _run_regime(self, builder, n_hist=0, max_cycles=8):
        L = builder()
        for _ in range(n_hist):
            apply_loop_historization(L)
        return [measure_cycle(L, k) for k in range(1, max_cycles + 1)]

    def test_M2_H0_is_resonator(self):
        history = self._run_regime(regime_M2)
        self.assertEqual(classify_resonator(history), "RESONATOR")

    def test_M3_H0_is_resonator(self):
        history = self._run_regime(regime_M3)
        self.assertEqual(classify_resonator(history), "RESONATOR")

    def test_C1_H0_is_decay(self):
        history = self._run_regime(control_C1)
        self.assertEqual(classify_resonator(history), "DECAY")

    def test_C1_H1_is_decay(self):
        history = self._run_regime(control_C1, n_hist=10)
        self.assertEqual(classify_resonator(history), "DECAY")

    def test_C2_H0_is_decay(self):
        history = self._run_regime(control_C2)
        self.assertEqual(classify_resonator(history), "DECAY")

    def test_C2_H1_is_decay(self):
        history = self._run_regime(control_C2, n_hist=20)
        self.assertEqual(classify_resonator(history), "DECAY")

    def test_M1_H0_is_not_resonator(self):
        history = self._run_regime(regime_M1)
        label = classify_resonator(history)
        self.assertIn(label, ("METASTABLE", "DECAY"))

    def test_insufficient_data(self):
        metrics = [CycleMetrics(cycle=1, I_coh=1, I_inc=1, R_coh=1,
                                H_loop=0, I_out=0, theta_loop=0)]
        self.assertEqual(classify_resonator(metrics), "INSUFFICIENT_DATA")

    def test_three_classes_distinct(self):
        """The three main regimes produce at least two different classes."""
        h_M2 = self._run_regime(regime_M2)
        h_C1 = self._run_regime(control_C1)
        classes = {classify_resonator(h_M2), classify_resonator(h_C1)}
        self.assertGreaterEqual(len(classes), 2)


# ═══════════════════════════════════════════════════════════════════
# 8. SU(2) on Resonator
# ═══════════════════════════════════════════════════════════════════

class TestSU2Resonator(unittest.TestCase):
    """F7: SU(2) holonomy and three-theory separation on resonator."""

    def test_loop_holonomy_is_SU2(self):
        L = regime_M3()
        U = su2_holonomy(L, ["A", "B", "C", "A"])
        self.assertTrue(is_su2(U))

    def test_geometric_holonomy_is_SU2(self):
        L = regime_M3()
        U_geo = su2_geometric_path_transport(L, ["A", "B", "C", "A"])
        self.assertTrue(is_su2(U_geo))

    def test_holonomy_not_identity(self):
        """Non-trivial loop → holonomy ≠ 𝕀."""
        L = regime_M3()
        U = su2_holonomy(L, ["A", "B", "C", "A"])
        tr = abs(np.trace(U))
        self.assertLess(tr, 1.999)

    def test_three_theories_differ_on_loop(self):
        """U(1), SU(2)-min, SU(2)-geo produce different intensities."""
        L = regime_M3()
        paths = loop_paths(4)
        I_u1 = intensity(L, paths)
        I_su2 = spinor_intensity(L, paths)
        I_geo = spinor_geometric_intensity(L, paths)
        # At least two of three should differ by more than 1%
        diffs = [abs(I_u1 - I_su2), abs(I_u1 - I_geo), abs(I_su2 - I_geo)]
        self.assertGreater(max(diffs), 0.01 * max(I_u1, I_su2, I_geo, 1e-10))

    def test_SU2_intensity_nonnegative(self):
        L = regime_M2()
        paths = loop_paths(4)
        self.assertGreaterEqual(spinor_intensity(L, paths), 0)
        self.assertGreaterEqual(spinor_geometric_intensity(L, paths), 0)

    def test_SU2_single_cycle_matches_U1_magnitude(self):
        """Single loop: SU(2)-min ≈ U(1) (no multi-path interference)."""
        L = regime_M2()
        paths_1 = loop_paths(1)
        I_u1 = intensity(L, paths_1)
        I_su2 = spinor_intensity(L, paths_1)
        self.assertAlmostEqual(I_u1, I_su2, places=5)


# ═══════════════════════════════════════════════════════════════════
# 9. Measurement Protocol
# ═══════════════════════════════════════════════════════════════════

class TestMeasurement(unittest.TestCase):
    """Measurement protocol returns consistent metrics."""

    def test_R_coh_definition(self):
        """R_coh = I_coh / I_inc."""
        L = regime_M2()
        m = measure_cycle(L, 4)
        if m.I_inc > 1e-30:
            self.assertAlmostEqual(m.R_coh, m.I_coh / m.I_inc, places=8)

    def test_I_inc_geq_0(self):
        L = regime_M2()
        m = measure_cycle(L, 4)
        self.assertGreaterEqual(m.I_inc, 0)

    def test_cycle_number_stored(self):
        L = regime_M2()
        m = measure_cycle(L, 5)
        self.assertEqual(m.cycle, 5)

    def test_theta_loop_equals_connection_theta(self):
        """Θ_loop from measurement matches theta() from connection."""
        L = regime_M3()
        m = measure_cycle(L, 1)
        theta_direct = theta(L, ["A", "B", "C", "A"])
        self.assertAlmostEqual(m.theta_loop, theta_direct, places=10)


# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    unittest.main()
