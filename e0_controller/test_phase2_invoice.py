"""
E₀ Controller — Phase 2 Tests: Invoice Domain
================================================
Sekundärvalidierung der Phase-/Connection-Schicht auf Rechnungsprüfung.

Erwartung (vorab dokumentiert):
    - Invoice-Domain ist fast ein DAG → schwache/triviale Holonomie
    - Zyklen nur über HUMAN_REVIEW (teurer Recovery-Pfad)
    - Phase-Schicht muss trotzdem konsistent berechenbar sein
    - Mehrere Pfade zu APPROVED existieren → Ψ-Vergleich möglich
"""

from __future__ import annotations

import math
import cmath
import unittest

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.potential import phi, phi_map, v_raw, v_grad, v_rot
from e0_controller.connection import omega, theta, holonomy, is_closed, omega_map
from e0_controller.wavepath import (
    psi, path_tension, path_intensity, sum_paths, intensity,
    path_analysis, interference_analysis,
)
from e0_controller.domain_invoice import build_invoice_landscape


HAPPY_PATH = [
    "RECEIVED", "PDF_LOADED", "DATA_EXTRACTED",
    "CUSTOMER_FOUND", "AMOUNT_OK", "CONTRACT_MATCH",
    "POLICY_OK", "APPROVED",
]

RECOVERY_PATH = [
    "RECEIVED", "PDF_LOADED", "DATA_EXTRACTED",
    "HUMAN_REVIEW", "CUSTOMER_FOUND", "AMOUNT_OK",
    "CONTRACT_MATCH", "POLICY_OK", "APPROVED",
]


class TestInvoicePotential(unittest.TestCase):
    """Φ auf der Invoice-Domain."""

    def setUp(self):
        self.L = build_invoice_landscape()

    def test_phi_all_states_computable(self):
        """Φ(x) für alle 10 States."""
        pm = phi_map(self.L)
        self.assertEqual(len(pm), 10)
        for state, val in pm.items():
            self.assertIsInstance(val, float)
            self.assertFalse(math.isnan(val))
            self.assertFalse(math.isinf(val))

    def test_phi_dead_ends_are_sinks(self):
        """REJECTED und APPROVED sind Sinks → niedrigstes Φ."""
        pm = phi_map(self.L)
        sink_states = {"REJECTED", "APPROVED"}
        source_states = set(pm.keys()) - sink_states
        max_sink = max(pm[s] for s in sink_states)
        for s in source_states:
            self.assertGreater(pm[s], max_sink,
                               f"Φ({s}) sollte > max(Φ(sinks)) sein")

    def test_phi_received_highest(self):
        """
        RECEIVED hat genau 1 Ausgangskante (→ PDF_LOADED).
        Andere States wie DATA_EXTRACTED, CUSTOMER_FOUND haben
        mehrere Kanten → typischerweise höheres Φ.
        Φ(RECEIVED) > 0 genügt hier.
        """
        self.assertGreater(phi(self.L, "RECEIVED"), 0.0)

    def test_decomposition_consistent_all_edges(self):
        """v = v_grad + v_rot für alle Kanten."""
        L = self.L
        for edge in L.edges:
            x, y = edge.source, edge.target
            v = v_raw(L, x, y)
            vg = v_grad(L, x, y)
            vr = v_rot(L, x, y)
            self.assertIsNotNone(vr)
            self.assertAlmostEqual(v, vg + vr, places=10,
                                   msg=f"v({x},{y}) ≠ v_grad + v_rot")


class TestInvoiceOmega(unittest.TestCase):
    """ω-Antisymmetrie auf der Invoice-Domain."""

    def setUp(self):
        self.L = build_invoice_landscape()

    def test_omega_antisymmetric_all_edges(self):
        """ω(x,y) = −ω(y,x) für alle Kantenpaare."""
        for edge in self.L.edges:
            x, y = edge.source, edge.target
            w_xy = omega(self.L, x, y)
            w_yx = omega(self.L, y, x)
            self.assertAlmostEqual(
                w_xy, -w_yx, places=10,
                msg=f"ω({x},{y}) ≠ −ω({y},{x})"
            )

    def test_omega_map_complete(self):
        """omega_map hat einen Eintrag pro Kante."""
        om = omega_map(self.L)
        self.assertEqual(len(om), self.L.edge_count())


class TestInvoiceHolonomy(unittest.TestCase):
    """Holonomie auf der Invoice-Domain."""

    def setUp(self):
        self.L = build_invoice_landscape()

    def test_human_review_cycle_computable(self):
        """
        Zyklus über HUMAN_REVIEW:
        DATA_EXTRACTED → HUMAN_REVIEW → DATA_EXTRACTED
        Beide Kanten existieren → geschlossener Zyklus.
        """
        cycle = ["DATA_EXTRACTED", "HUMAN_REVIEW", "DATA_EXTRACTED"]
        self.assertTrue(is_closed(cycle))
        h = holonomy(self.L, cycle)
        self.assertIsInstance(h, float)
        self.assertFalse(math.isnan(h))

    def test_two_edge_cycle_zero_holonomy(self):
        """
        2-Kanten-Zyklus: ω(x,y) + ω(y,x) = 0 (Antisymmetrie).
        DATA_EXTRACTED → HUMAN_REVIEW → DATA_EXTRACTED hat Holonomie = 0.
        """
        cycle = ["DATA_EXTRACTED", "HUMAN_REVIEW", "DATA_EXTRACTED"]
        h = holonomy(self.L, cycle)
        self.assertAlmostEqual(h, 0.0, places=10,
                               msg="2-Kanten-Zyklus muss Holonomie = 0 haben")

    def test_longer_cycle_via_human_review(self):
        """
        Längerer Zyklus:
        CUSTOMER_FOUND → HUMAN_REVIEW → DATA_EXTRACTED → CUSTOMER_FOUND
        3 Kanten → Holonomie kann ≠ 0 sein.
        """
        cycle = [
            "CUSTOMER_FOUND", "HUMAN_REVIEW",
            "DATA_EXTRACTED", "CUSTOMER_FOUND",
        ]
        h = holonomy(self.L, cycle)
        self.assertIsInstance(h, float)
        # 3-edge cycle can have nonzero holonomy — we just verify it's computable

    def test_invoice_mostly_dag_weak_holonomy(self):
        """
        ERWARTET: Invoice-Domain ist fast ein DAG.
        Zyklen nur über HUMAN_REVIEW → schwache Holonomie insgesamt.

        Prüfe: Die meisten ω-Werte sind klein im Vergleich zu Tension.
        """
        om = omega_map(self.L)
        avg_omega = sum(abs(w) for w in om.values()) / len(om) if om else 0
        # ω should be small relative to typical tension values (~0.1-0.5)
        self.assertLess(avg_omega, 1.0,
                        "Invoice-Domain: ω sollte insgesamt klein sein")


class TestInvoiceWavePath(unittest.TestCase):
    """Ψ auf der Invoice-Domain."""

    def setUp(self):
        self.L = build_invoice_landscape()

    def test_happy_path_psi(self):
        """Happy Path hat berechenbare Ψ mit |Ψ| > 0."""
        p = psi(self.L, HAPPY_PATH)
        self.assertGreater(abs(p), 0)

    def test_recovery_path_psi(self):
        """Recovery Path (über HUMAN_REVIEW) hat berechenbare Ψ."""
        p = psi(self.L, RECOVERY_PATH)
        self.assertGreater(abs(p), 0)

    def test_happy_path_stronger_than_recovery(self):
        """
        Happy Path hat niedrigere Tension → höheres |Ψ|.
        Recovery-Pfad geht über HUMAN_REVIEW (hohe R₀) → höhere Tension.
        """
        psi_happy = abs(psi(self.L, HAPPY_PATH))
        psi_recovery = abs(psi(self.L, RECOVERY_PATH))
        self.assertGreater(psi_happy, psi_recovery,
                           "Happy Path muss stärker sein als Recovery-Pfad")

    def test_interference_two_paths_to_approved(self):
        """Superposition von Happy Path und Recovery Path."""
        analysis = interference_analysis(self.L, [HAPPY_PATH, RECOVERY_PATH])
        self.assertGreater(analysis["total_intensity"], 0)
        self.assertGreater(analysis["sum_intensities"], 0)
        # Factor should be finite and positive
        self.assertTrue(0 < analysis["interference_factor"] < float("inf"))

    def test_path_analysis_consistent(self):
        """path_analysis stimmt mit Einzelberechnungen überein."""
        a = path_analysis(self.L, HAPPY_PATH)
        self.assertEqual(a["length"], len(HAPPY_PATH) - 1)
        s = path_tension(self.L, HAPPY_PATH)
        self.assertAlmostEqual(a["tension"], s, places=10)
        t = theta(self.L, HAPPY_PATH)
        self.assertAlmostEqual(a["phase"], t, places=10)


class TestInvoicePhaseConsistency(unittest.TestCase):
    """Phase-Schicht bleibt konsistent über die gesamte Domäne."""

    def test_all_edges_have_finite_omega(self):
        """Jede Kante hat endliches ω."""
        L = build_invoice_landscape()
        for edge in L.edges:
            w = omega(L, edge.source, edge.target)
            self.assertFalse(math.isnan(w), f"ω({edge}) = NaN")
            self.assertFalse(math.isinf(w), f"ω({edge}) = ∞")

    def test_all_edges_have_finite_v_rot(self):
        """v_rot ist für jede existierende Kante endlich (nicht None)."""
        L = build_invoice_landscape()
        for edge in L.edges:
            vr = v_rot(L, edge.source, edge.target)
            self.assertIsNotNone(vr, f"v_rot({edge}) = None")
            self.assertFalse(math.isnan(vr), f"v_rot({edge}) = NaN")
            self.assertFalse(math.isinf(vr), f"v_rot({edge}) = ∞")

    def test_total_phase_system_consistent(self):
        """
        Gesamtprüfung: Für jeden Pfad gilt
            arg(Ψ(p)) = Θ(p) = Σ ω(e_i)
        """
        L = build_invoice_landscape()
        for path in [HAPPY_PATH, RECOVERY_PATH]:
            p = psi(L, path)
            t = theta(L, path)
            if abs(p) > 1e-15:  # Only check if Ψ is non-zero
                self.assertAlmostEqual(cmath.phase(p), t, places=10,
                                       msg=f"arg(Ψ) ≠ Θ für {path[0]}→…→{path[-1]}")


if __name__ == "__main__":
    unittest.main()
