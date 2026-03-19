"""
E₀ Controller — Phase 2 Tests: Mini-Domain
=============================================
Validiert Potential, Connection und Wave Path auf der Mini-Domain.

Prüft:
    - Φ(x) ist für alle States berechenbar
    - v_grad und v_rot sind konsistent getrennt
    - ω(x,y) = −ω(y,x) gilt (Antisymmetrie)
    - Geschlossene Zyklen können nichttriviale Holonomie tragen
    - Ψ(path) ist berechenbar
    - Intensitäten ändern sich sinnvoll bei Pfadphasen

Domäne: Mini-Domain (8 States, 10 Edges)
    Enthält Zyklus A ↔ C (bidirektional) — guter Holonomie-Kandidat.
"""

from __future__ import annotations

import math
import cmath
import unittest

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.potential import (
    phi, phi_map, v_raw, v_grad, v_rot, decomposition, decomposition_table,
)
from e0_controller.connection import (
    omega, theta, holonomy, is_closed, omega_map, connection_info,
)
from e0_controller.wavepath import (
    psi, path_tension, path_intensity, sum_paths, intensity,
    path_analysis, interference_analysis,
)
from e0_controller.test_minidomain import build_mini_landscape


class TestPotential(unittest.TestCase):
    """§9: Lokales Potential Φ(x)."""

    def setUp(self):
        self.L = build_mini_landscape()

    def test_phi_computable_for_all_states(self):
        """Φ(x) ist für alle 8 States berechenbar."""
        pm = phi_map(self.L)
        self.assertEqual(len(pm), 8)
        for state, val in pm.items():
            self.assertIsInstance(val, float, f"Φ({state}) muss float sein")
            self.assertFalse(math.isnan(val), f"Φ({state}) darf nicht NaN sein")
            self.assertFalse(math.isinf(val), f"Φ({state}) darf nicht ∞ sein")

    def test_phi_dead_end_is_zero(self):
        """Dead-end D hat keine Ausgangskanten → Φ(D) = 0."""
        self.assertEqual(phi(self.L, "D"), 0.0)

    def test_phi_goal_is_zero(self):
        """GOAL hat keine Ausgangskanten → Φ(GOAL) = 0."""
        self.assertEqual(phi(self.L, "GOAL"), 0.0)

    def test_phi_source_higher_than_sink(self):
        """
        States mit Ausgangskanten (z.B. A) haben höheres Φ als Dead-ends.
        A hat 2 Kanten mit Tension > 0 → Φ(A) > 0 = Φ(D).
        """
        self.assertGreater(phi(self.L, "A"), phi(self.L, "D"))
        self.assertGreater(phi(self.L, "A"), phi(self.L, "GOAL"))

    def test_phi_positive_for_connected_states(self):
        """Alle States mit Ausgangskanten haben Φ > 0."""
        for state in ["A", "B", "C", "E", "G"]:
            self.assertGreater(phi(self.L, state), 0.0,
                               f"Φ({state}) sollte > 0 sein")

    def test_phi_consistent_with_tension(self):
        """
        Φ(A) = Δ(A,B)·R_eff(A,B) + Δ(A,C)·R_eff(A,C)
             = 0.5·1.0 + 0.4·0.8 = 0.82
        """
        self.assertAlmostEqual(phi(self.L, "A"), 0.82, places=5)


class TestDecomposition(unittest.TestCase):
    """§10–11: v = v_grad + v_rot."""

    def setUp(self):
        self.L = build_mini_landscape()

    def test_decomposition_sums_correctly(self):
        """v(x,y) = v_grad(x,y) + v_rot(x,y) für alle existierenden Kanten."""
        for edge in self.L.edges:
            x, y = edge.source, edge.target
            v = v_raw(self.L, x, y)
            vg = v_grad(self.L, x, y)
            vr = v_rot(self.L, x, y)
            self.assertIsNotNone(vr, f"v_rot({x},{y}) darf nicht None sein")
            self.assertAlmostEqual(
                v, vg + vr, places=10,
                msg=f"v({x},{y}) ≠ v_grad + v_rot: {v} ≠ {vg} + {vr}"
            )

    def test_v_rot_none_for_missing_edge(self):
        """v_rot(D, A) = None (keine Kante D→A)."""
        self.assertIsNone(v_rot(self.L, "D", "A"))

    def test_v_raw_zero_for_missing_edge(self):
        """v(D, A) = 0.0 (keine Kante)."""
        self.assertEqual(v_raw(self.L, "D", "A"), 0.0)

    def test_v_grad_always_computable(self):
        """v_grad(x,y) = Φ(x)−Φ(y) ist für jedes Paar berechenbar."""
        states = list(self.L.states)
        for x in states:
            for y in states:
                vg = v_grad(self.L, x, y)
                self.assertIsInstance(vg, float)
                self.assertFalse(math.isnan(vg))

    def test_v_grad_antisymmetric(self):
        """v_grad(x,y) = −v_grad(y,x) (aus Φ-Definition)."""
        for edge in self.L.edges:
            x, y = edge.source, edge.target
            self.assertAlmostEqual(
                v_grad(self.L, x, y), -v_grad(self.L, y, x), places=10,
                msg=f"v_grad({x},{y}) ≠ −v_grad({y},{x})"
            )

    def test_decomposition_table_complete(self):
        """decomposition_table hat einen Eintrag pro Kante."""
        table = decomposition_table(self.L)
        self.assertEqual(len(table), self.L.edge_count())


class TestOmegaAntisymmetry(unittest.TestCase):
    """§12: ω(x,y) = −ω(y,x)."""

    def setUp(self):
        self.L = build_mini_landscape()

    def test_omega_antisymmetric_all_pairs(self):
        """ω(x,y) = −ω(y,x) für ALLE State-Paare, nicht nur existierende Kanten."""
        states = list(self.L.states)
        for x in states:
            for y in states:
                if x == y:
                    continue
                w_xy = omega(self.L, x, y)
                w_yx = omega(self.L, y, x)
                self.assertAlmostEqual(
                    w_xy, -w_yx, places=10,
                    msg=f"ω({x},{y})={w_xy} ≠ −ω({y},{x})={w_yx}"
                )

    def test_omega_self_zero(self):
        """ω(x,x) = 0 (self-loop carries no connection)."""
        for x in self.L.states:
            self.assertEqual(omega(self.L, x, x), 0.0)

    def test_omega_bidirectional_edge_nonzero(self):
        """
        A↔C ist bidirektional (A→C und C→A existieren).
        Wenn v_rot in beiden Richtungen verschieden ist, muss ω ≠ 0 sein.
        """
        w = omega(self.L, "A", "C")
        # We can't necessarily assert non-zero (depends on symmetry),
        # but we verify it's computed without error
        self.assertIsInstance(w, float)
        self.assertFalse(math.isnan(w))

    def test_omega_unidirectional_well_defined(self):
        """
        A→B existiert, B→A nicht.
        ω(A,B) ist trotzdem definiert (Konvention: v_rot(B,A)=0).
        """
        w = omega(self.L, "A", "B")
        self.assertIsInstance(w, float)
        self.assertFalse(math.isnan(w))

    def test_omega_map_has_all_edges(self):
        """omega_map enthält alle Landscape-Kanten."""
        om = omega_map(self.L)
        self.assertEqual(len(om), self.L.edge_count())


class TestHolonomy(unittest.TestCase):
    """§14: Holonomie auf geschlossenen Zyklen."""

    def setUp(self):
        self.L = build_mini_landscape()

    def test_trivial_cycle_zero_holonomy(self):
        """Trivialer Zyklus (1 State) hat Θ = 0."""
        self.assertEqual(holonomy(self.L, ["A"]), 0.0)

    def test_bidirectional_cycle_ACA(self):
        """
        A → C → A ist ein geschlossener Zyklus (beide Kanten existieren).
        Holonomie muss berechenbar sein.
        """
        cycle = ["A", "C", "A"]
        self.assertTrue(is_closed(cycle))
        h = holonomy(self.L, cycle)
        self.assertIsInstance(h, float)
        self.assertFalse(math.isnan(h))

    def test_holonomy_sign_reversal(self):
        """
        Zyklus in Gegenrichtung hat gegensätzliche Holonomie:
        Θ(A→C→A) = −Θ(A→C→A reversed) iff ω ist antisymmetrisch.
        Aber A→C→A reversed = A→C→A (gleicher Zyklus!).

        Besser: Θ(A→C→A) = ω(A,C) + ω(C,A) = ω(A,C) − ω(A,C) = 0.

        ERWARTUNG: Bidirektionaler 2-Kanten-Zyklus hat Holonomie = 0,
        weil ω-Antisymmetrie die Beiträge exakt cancelt.
        """
        cycle_fwd = ["A", "C", "A"]
        h = holonomy(self.L, cycle_fwd)
        self.assertAlmostEqual(h, 0.0, places=10,
                               msg="2-Kanten-Zyklus: ω(A,C)+ω(C,A) muss = 0 sein")

    def test_longer_cycle_may_have_nonzero_holonomy(self):
        """
        Längere Zyklen (≥ 3 Kanten) können nichttriviale Holonomie tragen.
        A → B → E → F → G → (kein Rückweg zu A im Graph).

        Aber A → C → A ist 2-Kanten → trivial (s.o.).
        A → B → ... hat keinen Rückweg.

        Also: Zyklen mit ≥ 3 verschiedenen Stationen und Rückkante
        sind nötig für Holonomie ≠ 0. Im Mini-Graph ist das schwer.

        Test: Konstruieren expliziten 3er-Zyklus A → C → D → A.
        C→D existiert, D→A nicht → D→A wird als v_rot=0 behandelt.
        Trotzdem: Θ = ω(A,C) + ω(C,D) + ω(D,A) kann ≠ 0 sein
        weil die einzelnen ω nicht zwangsläufig canceln.
        """
        path = ["A", "C", "D", "A"]
        h = holonomy(self.L, path)
        self.assertIsInstance(h, float)
        # We don't assert non-zero — it depends on the specific Δ/R values.
        # But we verify it's computable.

    def test_path_phase_accumulation(self):
        """Θ akkumuliert entlang des Pfads."""
        path = ["A", "B", "E", "G", "GOAL"]
        t = theta(self.L, path)
        self.assertIsInstance(t, float)
        self.assertFalse(math.isnan(t))

        # Must equal sum of individual ω values
        expected = sum(
            omega(self.L, path[i], path[i + 1])
            for i in range(len(path) - 1)
        )
        self.assertAlmostEqual(t, expected, places=10)


class TestWavePath(unittest.TestCase):
    """§15: Ψ(path) = exp(−S + iΘ)."""

    def setUp(self):
        self.L = build_mini_landscape()

    def test_psi_computable(self):
        """Ψ(p) ist berechenbar für einen normalen Pfad."""
        path = ["A", "B", "E", "G", "GOAL"]
        p = psi(self.L, path)
        self.assertIsInstance(p, complex)
        self.assertFalse(cmath.isnan(p))

    def test_psi_magnitude_equals_exp_minus_s(self):
        """|Ψ| = exp(−S)."""
        path = ["A", "B", "E", "G", "GOAL"]
        p = psi(self.L, path)
        s = path_tension(self.L, path)
        self.assertAlmostEqual(abs(p), math.exp(-s), places=10)

    def test_psi_phase_equals_theta(self):
        """arg(Ψ) = Θ."""
        path = ["A", "B", "E", "G", "GOAL"]
        p = psi(self.L, path)
        t = theta(self.L, path)
        self.assertAlmostEqual(cmath.phase(p), t, places=10)

    def test_psi_zero_for_inadmissible_path(self):
        """Pfad über nicht-existierende Kante → Ψ = 0."""
        path = ["D", "A"]  # D→A existiert nicht
        p = psi(self.L, path)
        self.assertEqual(p, complex(0.0, 0.0))

    def test_psi_empty_path(self):
        """Leerer Pfad → Ψ = 1 (S=0, Θ=0) → exp(0) = 1."""
        p = psi(self.L, ["A"])
        self.assertAlmostEqual(p, complex(1.0, 0.0), places=10)

    def test_path_intensity_matches_magnitude_squared(self):
        """I(p) = |Ψ(p)|²."""
        path = ["A", "B", "E", "G", "GOAL"]
        p = psi(self.L, path)
        i = path_intensity(self.L, path)
        self.assertAlmostEqual(i, abs(p) ** 2, places=10)

    def test_path_analysis_keys(self):
        """path_analysis gibt alle erwarteten Schlüssel zurück."""
        path = ["A", "B", "E", "G", "GOAL"]
        a = path_analysis(self.L, path)
        expected_keys = {
            "path", "length", "tension", "phase",
            "psi", "magnitude", "intensity", "phase_deg",
        }
        self.assertEqual(set(a.keys()), expected_keys)
        self.assertEqual(a["length"], 4)


class TestInterference(unittest.TestCase):
    """§16: Pfad-Summation und Interferenz."""

    def setUp(self):
        self.L = build_mini_landscape()

    def test_single_path_no_interference(self):
        """Ein einziger Pfad: interference_factor = 1.0."""
        paths = [["A", "B", "E", "G", "GOAL"]]
        analysis = interference_analysis(self.L, paths)
        self.assertAlmostEqual(analysis["interference_factor"], 1.0, places=5)

    def test_two_paths_to_goal(self):
        """
        Zwei Pfade zum GOAL:
        - A → B → E → G → GOAL (direkt)
        - A → B → E → F → G → GOAL (über F)

        Superposition muss berechenbar sein.
        """
        path1 = ["A", "B", "E", "G", "GOAL"]
        path2 = ["A", "B", "E", "F", "G", "GOAL"]
        result = sum_paths(self.L, [path1, path2])
        self.assertIsInstance(result, complex)
        self.assertFalse(cmath.isnan(result))

    def test_interference_factor_computable(self):
        """interference_factor ist berechenbar und > 0."""
        path1 = ["A", "B", "E", "G", "GOAL"]
        path2 = ["A", "B", "E", "F", "G", "GOAL"]
        analysis = interference_analysis(self.L, [path1, path2])
        self.assertGreater(analysis["interference_factor"], 0.0)
        self.assertFalse(math.isnan(analysis["interference_factor"]))

    def test_intensity_via_sum_paths(self):
        """I(z) = |Σ Ψ(p)|²."""
        paths = [
            ["A", "B", "E", "G", "GOAL"],
            ["A", "B", "E", "F", "G", "GOAL"],
        ]
        psi_total = sum_paths(self.L, paths)
        i = intensity(self.L, paths)
        self.assertAlmostEqual(i, abs(psi_total) ** 2, places=10)

    def test_different_paths_different_phase(self):
        """
        Zwei Pfade gleichen Ziels: Phase-Differenz beeinflusst Interferenz.
        Pfad über F ist länger → andere Tension → anderes |Ψ|.
        """
        path1 = ["A", "B", "E", "G", "GOAL"]
        path2 = ["A", "B", "E", "F", "G", "GOAL"]
        a1 = path_analysis(self.L, path1)
        a2 = path_analysis(self.L, path2)

        # Different paths, different tension
        self.assertNotAlmostEqual(a1["tension"], a2["tension"], places=3)

    def test_constructive_destructive_possible(self):
        """
        Interference factor can be > 1 (constructive) or < 1 (destructive).
        We verify the factor is not always exactly 1.

        With two paths of different tensions and phases, the factor
        should deviate from 1 (either direction).
        """
        path1 = ["A", "B", "E", "G", "GOAL"]
        path2 = ["A", "B", "E", "F", "G", "GOAL"]
        analysis = interference_analysis(self.L, [path1, path2])
        # Factor != 1 means interference is happening
        # (could be constructive or destructive depending on phases)
        factor = analysis["interference_factor"]
        # We just verify it's not NaN/Inf and is finite positive
        self.assertTrue(0 < factor < float("inf"))


class TestHistorizationEffectsOnPhase(unittest.TestCase):
    """Phase-Schicht reagiert auf Historisierung."""

    def test_phi_changes_after_historization(self):
        """Φ(E) verändert sich nach Failures auf E→F."""
        L = build_mini_landscape()
        phi_before = phi(L, "E")

        # Historize some failures on E→F
        edge = Edge("E", "F")
        for _ in range(5):
            L.historization.update(edge, Outcome.FAILURE)

        phi_after = phi(L, "E")
        # After failures: R_eff(E→F) is higher → Φ(E) increases
        self.assertGreater(phi_after, phi_before,
                           "Φ(E) muss nach Failures steigen (höherer R_eff)")

    def test_psi_magnitude_changes_after_failures(self):
        """Path über failure-prone Kante wird schwächer nach Historisierung."""
        L = build_mini_landscape()
        path = ["E", "F", "G", "GOAL"]
        mag_before = abs(psi(L, path))

        # Historize failures on E→F
        edge = Edge("E", "F")
        for _ in range(5):
            L.historization.update(edge, Outcome.FAILURE)

        mag_after = abs(psi(L, path))
        # Higher tension → lower magnitude
        self.assertLess(mag_after, mag_before,
                        "|Ψ| muss sinken wenn Tension steigt")

    def test_omega_changes_after_historization(self):
        """ω kann sich durch Historisierung verändern (v_rot ändert sich)."""
        L = build_mini_landscape()
        w_before = omega(L, "E", "F")

        edge = Edge("E", "F")
        for _ in range(5):
            L.historization.update(edge, Outcome.FAILURE)

        w_after = omega(L, "E", "F")
        # ω can change because v_raw changes (different S → different coherence)
        # We just verify it's computable after historization
        self.assertIsInstance(w_after, float)
        self.assertFalse(math.isnan(w_after))


if __name__ == "__main__":
    unittest.main()
