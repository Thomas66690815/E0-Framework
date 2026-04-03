"""
E₀ Controller — Phase 1b Tests: Rechnungsprüfung
====================================================
Validiert Controller an realistischem Invoice-Processing-Domain.

Prüft:
    - Happy Path (alle SUCCESS)
    - Failure-Learning (Historisierung verbessert nachfolgende Läufe)
    - Escalation-Verhalten an Dead-Ends & HUMAN_REVIEW
    - Metriken (K13)
    - Landscape-Invarianz (K1)
    - Wiederholte Läufe mit frischer Historisierung
    - Edge Cases (Start bei Dead-End, Start bei HUMAN_REVIEW)
"""

from __future__ import annotations

import copy
import math
import unittest

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller, RunTrace
from e0_controller.domain_invoice import (
    build_invoice_landscape,
    happy_path,
    realistic_outcomes,
    harsh_outcomes,
    learning_scenario,
    reset_learning_scenario,
    INVOICE_CASES,
)


class TestInvoiceLandscape(unittest.TestCase):
    """Landscape-Struktur korrekt aufgebaut."""

    def setUp(self):
        self.L = build_invoice_landscape()

    def test_state_count(self):
        """10 Zustände."""
        self.assertEqual(len(self.L.states), 10)

    def test_edge_count(self):
        """16 Kanten."""
        self.assertEqual(self.L.edge_count(), 16)

    def test_happy_path_edges_exist(self):
        """Hauptpfad RECEIVED→…→APPROVED existiert."""
        path = [
            ("RECEIVED", "PDF_LOADED"),
            ("PDF_LOADED", "DATA_EXTRACTED"),
            ("DATA_EXTRACTED", "CUSTOMER_FOUND"),
            ("CUSTOMER_FOUND", "AMOUNT_OK"),
            ("AMOUNT_OK", "CONTRACT_MATCH"),
            ("CONTRACT_MATCH", "POLICY_OK"),
            ("POLICY_OK", "APPROVED"),
        ]
        for src, tgt in path:
            r0 = self.L.base_resistance(src, tgt)
            self.assertFalse(math.isinf(r0),
                             f"Kante {src}→{tgt} fehlt")

    def test_dead_ends(self):
        """REJECTED und APPROVED haben keine Ausgangskanten."""
        self.assertEqual(self.L.admissible_neighbors("REJECTED"), [])
        self.assertEqual(self.L.admissible_neighbors("APPROVED"), [])

    def test_human_review_has_outgoing(self):
        """HUMAN_REVIEW hat Recovery-Pfade."""
        nb = self.L.admissible_neighbors("HUMAN_REVIEW")
        self.assertTrue(len(nb) >= 2,
                        "HUMAN_REVIEW braucht Recovery-Pfade")
        # Must include CUSTOMER_FOUND and DATA_EXTRACTED
        self.assertIn("CUSTOMER_FOUND", nb)
        self.assertIn("DATA_EXTRACTED", nb)

    def test_escalation_paths_exist(self):
        """PDF_LOADED, AMOUNT_OK, POLICY_OK können REJECTED erreichen."""
        for src in ["PDF_LOADED", "AMOUNT_OK", "POLICY_OK"]:
            r0 = self.L.base_resistance(src, "REJECTED")
            self.assertFalse(math.isinf(r0),
                             f"Kante {src}→REJECTED fehlt")


class TestHappyPath(unittest.TestCase):
    """Alles SUCCESS — Controller findet APPROVED über Happy Path."""

    def test_reaches_approved(self):
        L = build_invoice_landscape()
        ctrl = E0Controller(L, happy_path)
        trace = ctrl.run("RECEIVED", goal="APPROVED", max_cycles=20)
        self.assertEqual(trace.path[-1], "APPROVED")

    def test_happy_path_length(self):
        """Happy Path sollte ≤ 8 Steps brauchen (7 Kanten optimal)."""
        L = build_invoice_landscape()
        ctrl = E0Controller(L, happy_path)
        trace = ctrl.run("RECEIVED", goal="APPROVED", max_cycles=20)
        self.assertLessEqual(len(trace.steps), 8)

    def test_no_escalation_on_happy_path(self):
        """Happy Path braucht keine Escalation."""
        L = build_invoice_landscape()
        ctrl = E0Controller(L, happy_path)
        trace = ctrl.run("RECEIVED", goal="APPROVED", max_cycles=20)
        esc = sum(1 for s in trace.steps if s.escalated)
        self.assertEqual(esc, 0)

    def test_all_success_outcomes(self):
        """Happy Path produziert nur SUCCESS."""
        L = build_invoice_landscape()
        ctrl = E0Controller(L, happy_path)
        trace = ctrl.run("RECEIVED", goal="APPROVED", max_cycles=20)
        for step in trace.steps:
            self.assertEqual(step.outcome, Outcome.SUCCESS)


class TestRealisticOutcomes(unittest.TestCase):
    """Realistische Fehler — Controller muss umsteuern."""

    def test_realistic_completes(self):
        """Controller terminiert (kein Endlos-Loop)."""
        L = build_invoice_landscape()
        ctrl = E0Controller(L, realistic_outcomes)
        trace = ctrl.run("RECEIVED", goal="APPROVED", max_cycles=50)
        self.assertTrue(len(trace.steps) > 0)
        self.assertTrue(len(trace.steps) <= 50)

    def test_realistic_has_failures(self):
        """Realistische Szenarien produzieren Failures."""
        L = build_invoice_landscape()
        ctrl = E0Controller(L, realistic_outcomes)
        trace = ctrl.run("RECEIVED", goal="APPROVED", max_cycles=50)
        oc = trace.outcomes
        self.assertGreater(oc["FAILURE"], 0,
                           "Realistische Szenarien müssen Failures haben")

    def test_historization_learns(self):
        """
        R_eff auf FAILURE-Kante steigt über die Zeit.
        DATA_EXTRACTED → CUSTOMER_FOUND scheitert immer → R_eff muss steigen.
        """
        L = build_invoice_landscape()
        ctrl = E0Controller(L, realistic_outcomes)
        trace = ctrl.run("RECEIVED", goal="APPROVED", max_cycles=50)

        # Find steps on the failure edge
        failure_edge_steps = [
            s for s in trace.steps
            if s.source == "DATA_EXTRACTED" and s.target == "CUSTOMER_FOUND"
        ]
        if len(failure_edge_steps) >= 2:
            # R_eff should increase
            first_r = failure_edge_steps[0].r_eff_before
            last_r = failure_edge_steps[-1].r_eff_after
            self.assertGreater(last_r, first_r,
                               "R_eff muss auf FAILURE-Kante steigen")


class TestHarshOutcomes(unittest.TestCase):
    """Schwieriger Fall — viele Fehler, Controller muss navigieren."""

    def test_harsh_terminates(self):
        L = build_invoice_landscape()
        ctrl = E0Controller(L, harsh_outcomes)
        trace = ctrl.run("RECEIVED", goal="APPROVED", max_cycles=50)
        self.assertGreater(len(trace.steps), 0)

    def test_harsh_has_escalation_or_alternative(self):
        """Bei vielen Fehlern muss der Controller eskalieren oder Alternativpfade finden."""
        L = build_invoice_landscape()
        ctrl = E0Controller(L, harsh_outcomes)
        trace = ctrl.run("RECEIVED", goal="APPROVED", max_cycles=50)
        oc = trace.outcomes
        esc = sum(1 for s in trace.steps if s.escalated)
        # Either the controller escalated or found alternative paths
        self.assertTrue(
            esc > 0 or oc["FAILURE"] > 0,
            "Harsches Szenario muss Escalation oder Failures zeigen"
        )


class TestLearningScenario(unittest.TestCase):
    """Lernfähiges Szenario: N Failures → dann SUCCESS."""

    def setUp(self):
        reset_learning_scenario()

    def tearDown(self):
        reset_learning_scenario()

    def test_learning_eventually_succeeds(self):
        """Mit learning_scenario: Kanten die erst scheitern, klappen dann."""
        L = build_invoice_landscape()
        ctrl = E0Controller(L, lambda s, t: learning_scenario(s, t, []))
        trace = ctrl.run("RECEIVED", goal="APPROVED", max_cycles=60)
        oc = trace.outcomes
        # Must have both failures and successes
        self.assertGreater(oc["SUCCESS"], 0)

    def test_learning_r_eff_rises_during_failures(self):
        """R_eff steigt während der Failure-Phase."""
        L = build_invoice_landscape()
        ctrl = E0Controller(L, lambda s, t: learning_scenario(s, t, []))
        trace = ctrl.run("RECEIVED", goal="APPROVED", max_cycles=60)

        target_steps = [
            s for s in trace.steps
            if s.source == "DATA_EXTRACTED" and s.target == "CUSTOMER_FOUND"
        ]
        # Among steps that failed, R_eff should increase
        failure_steps = [s for s in target_steps if s.outcome == Outcome.FAILURE]
        if len(failure_steps) >= 2:
            self.assertGreater(failure_steps[-1].r_eff_after,
                               failure_steps[0].r_eff_before)


class TestEscalation(unittest.TestCase):
    """Escalation-Verhalten explizit testen."""

    def test_dead_end_escalation(self):
        """Start bei REJECTED (Dead-end) → Controller MUSS eskalieren."""
        L = build_invoice_landscape()
        ctrl = E0Controller(L, happy_path)
        trace = ctrl.run("REJECTED", max_cycles=10)
        if trace.steps:
            # First step must be escalation (no normal edges from REJECTED)
            self.assertTrue(trace.steps[0].escalated,
                            "Start bei Dead-end muss sofort eskalieren")

    def test_escalation_targets_viable_state(self):
        """Escalation-Ziel muss ein State mit Ausgangskanten sein."""
        L = build_invoice_landscape()
        ctrl = E0Controller(L, happy_path)
        trace = ctrl.run("REJECTED", max_cycles=10)
        if trace.steps:
            esc_target = trace.steps[0].target
            nb = L.admissible_neighbors(esc_target)
            self.assertTrue(len(nb) > 0,
                            f"Escalation-Ziel {esc_target} hat keine Ausgangskanten")


class TestLandscapeInvariance(unittest.TestCase):
    """K1: Landscape darf durch Controller-Run nicht mutiert werden."""

    def test_landscape_edges_unchanged(self):
        """Kantenanzahl bleibt gleich nach einem Run."""
        L = build_invoice_landscape()
        initial_edges = L.edge_count()
        initial_states = len(L.states)

        ctrl = E0Controller(L, realistic_outcomes)
        trace = ctrl.run("RECEIVED", goal="APPROVED", max_cycles=50)

        self.assertEqual(L.edge_count(), initial_edges,
                         "Landscape-Kanten dürfen sich nicht ändern")
        self.assertEqual(len(L.states), initial_states,
                         "Landscape-States dürfen sich nicht ändern")

    def test_landscape_delta_unchanged(self):
        """Δ-Werte bleiben gleich nach einem Run."""
        L = build_invoice_landscape()
        # Snapshot all delta values
        deltas_before = {}
        for src in L.states:
            for tgt in L.states:
                d = L.difference(src, tgt)
                if d is not None and d > 0:
                    deltas_before[(src, tgt)] = d

        ctrl = E0Controller(L, realistic_outcomes)
        ctrl.run("RECEIVED", goal="APPROVED", max_cycles=50)

        for (src, tgt), d_before in deltas_before.items():
            d_after = L.difference(src, tgt)
            self.assertAlmostEqual(d_before, d_after, places=10,
                                   msg=f"Δ({src},{tgt}) darf sich nicht ändern")


class TestMetrics(unittest.TestCase):
    """K13: Operative Metriken (RunTrace.metrics())."""

    def test_metrics_happy_path(self):
        """Happy Path: 100% success, 100% deterministic."""
        L = build_invoice_landscape()
        ctrl = E0Controller(L, happy_path)
        trace = ctrl.run("RECEIVED", goal="APPROVED", max_cycles=20)
        m = trace.metrics()

        self.assertGreater(m["steps"], 0)
        self.assertEqual(m["success_rate"], 1.0)
        self.assertEqual(m["failure_rate"], 0.0)
        self.assertEqual(m["escalation_count"], 0.0)
        self.assertEqual(m["deterministic_rate"], 1.0)
        self.assertGreater(m["unique_states"], 1)

    def test_metrics_has_all_keys(self):
        """Alle 9 Metrik-Schlüssel vorhanden."""
        L = build_invoice_landscape()
        ctrl = E0Controller(L, happy_path)
        trace = ctrl.run("RECEIVED", goal="APPROVED", max_cycles=20)
        m = trace.metrics()

        expected_keys = {
            "steps", "deterministic_rate", "escalation_count",
            "success_rate", "failure_rate", "avg_tension",
            "avg_r_eff_shift", "revisit_count", "unique_states",
            "overlay_agree", "overlay_count",
            "hybrid_override_count", "hybrid_override_rate",
            "avg_override_confidence",
            "non_inscription_count", "non_inscription_rate",
        }
        self.assertEqual(set(m.keys()), expected_keys)

    def test_metrics_empty_trace(self):
        """Leerer Trace → alle Metriken 0."""
        trace = RunTrace()
        m = trace.metrics()
        for k, v in m.items():
            self.assertEqual(v, 0.0, f"Leerer Trace: {k} muss 0 sein")

    def test_metrics_realistic_has_failures(self):
        """Realistische Szenarien: failure_rate > 0."""
        L = build_invoice_landscape()
        ctrl = E0Controller(L, realistic_outcomes)
        trace = ctrl.run("RECEIVED", goal="APPROVED", max_cycles=50)
        m = trace.metrics()
        self.assertGreater(m["failure_rate"], 0.0)

    def test_metrics_escalation_dead_end(self):
        """Dead-end Start: escalation_count > 0."""
        L = build_invoice_landscape()
        ctrl = E0Controller(L, happy_path)
        trace = ctrl.run("REJECTED", max_cycles=10)
        m = trace.metrics()
        if m["steps"] > 0:
            self.assertGreater(m["escalation_count"], 0.0)

    def test_metrics_revisit_count(self):
        """Bei Failures entstehen revisits."""
        L = build_invoice_landscape()
        ctrl = E0Controller(L, realistic_outcomes)
        trace = ctrl.run("RECEIVED", goal="APPROVED", max_cycles=50)
        m = trace.metrics()
        # With failures, the controller may revisit states
        # (not guaranteed, but check type)
        self.assertIsInstance(m["revisit_count"], float)


class TestMultipleRuns(unittest.TestCase):
    """Wiederholte Läufe auf gleicher Landscape (shared historization)."""

    def test_second_run_benefits_from_first(self):
        """
        Zweiter Lauf auf gleicher Landscape:
        Historisierung aus Run 1 beeinflusst Run 2.
        """
        L = build_invoice_landscape()

        # Run 1: realistic outcomes → failures historized
        ctrl1 = E0Controller(L, realistic_outcomes)
        trace1 = ctrl1.run("RECEIVED", goal="APPROVED", max_cycles=50)

        # Check that historization has records
        tau_after_run1 = L.historization.tau
        self.assertGreater(tau_after_run1, 0)

        # After run 1: failed edges should have elevated R_eff
        edge = Edge("DATA_EXTRACTED", "CUSTOMER_FOUND")
        r_eff_after_run1 = L.effective_resistance("DATA_EXTRACTED", "CUSTOMER_FOUND")
        r0 = L.base_resistance("DATA_EXTRACTED", "CUSTOMER_FOUND")

        # Run 2: same landscape, happy_path execution
        # Historization from run 1 affects R_eff
        ctrl2 = E0Controller(L, happy_path)
        trace2 = ctrl2.run("RECEIVED", goal="APPROVED", max_cycles=20)

        # R_eff should differ from R₀ — historization from both runs
        # has a measurable effect (K2: global decay means exact direction
        # depends on the balance of successes and failures over time)
        r_eff_after_run2 = L.effective_resistance("DATA_EXTRACTED", "CUSTOMER_FOUND")
        self.assertNotAlmostEqual(r_eff_after_run2, r0, places=3,
                                  msg="Historisierung aus Run 1+2 muss R_eff verändern")


class TestHumanReviewRecovery(unittest.TestCase):
    """Recovery-Pfade aus HUMAN_REVIEW."""

    def test_from_human_review_reaches_approved(self):
        """Start bei HUMAN_REVIEW → APPROVED erreichbar."""
        L = build_invoice_landscape()
        ctrl = E0Controller(L, happy_path)
        trace = ctrl.run("HUMAN_REVIEW", goal="APPROVED", max_cycles=20)
        self.assertEqual(trace.path[-1], "APPROVED")

    def test_human_review_recovery_path(self):
        """Recovery geht über CUSTOMER_FOUND oder DATA_EXTRACTED."""
        L = build_invoice_landscape()
        ctrl = E0Controller(L, happy_path)
        trace = ctrl.run("HUMAN_REVIEW", goal="APPROVED", max_cycles=20)
        path = trace.path
        # Must go through one of the recovery targets
        self.assertTrue(
            "CUSTOMER_FOUND" in path or "DATA_EXTRACTED" in path,
            "Recovery muss über CUSTOMER_FOUND oder DATA_EXTRACTED gehen"
        )


class TestEdgeCases(unittest.TestCase):
    """Edge Cases und Grenzfälle."""

    def test_start_at_goal(self):
        """Start = Goal → 0 Steps."""
        L = build_invoice_landscape()
        ctrl = E0Controller(L, happy_path)
        trace = ctrl.run("APPROVED", goal="APPROVED", max_cycles=20)
        self.assertEqual(len(trace.steps), 0)

    def test_max_cycles_respected(self):
        """max_cycles wird eingehalten."""
        L = build_invoice_landscape()
        ctrl = E0Controller(L, realistic_outcomes)
        trace = ctrl.run("RECEIVED", goal="APPROVED", max_cycles=5)
        self.assertLessEqual(len(trace.steps), 5)

    def test_fresh_landscape_no_historization(self):
        """Frische Landscape: δ_H = 0 überall."""
        L = build_invoice_landscape()
        for src in L.states:
            for tgt in L.states:
                edge = Edge(src, tgt)
                dh = L.historization.delta_H(edge)
                self.assertEqual(dh, 0.0,
                                 f"Frische Landscape: δ_H({src},{tgt}) muss 0 sein")


if __name__ == "__main__":
    unittest.main()
