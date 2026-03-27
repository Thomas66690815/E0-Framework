"""Tests for the Ibuprofen-Beipackzettel real-world landscape.

Verifies that E₀ structural primitives correctly model pharmacological
relationships from a medication package insert and that the controller
exhibits the expected behaviour:

  C31-BPZ — Beipackzettel Real-World Claim:
    1. Therapeutic path (lowest burden) reaches GESUND
    2. Amplitude overlay avoids risk states the greedy controller might visit
    3. ASS interaction produces convergent burden on BLUTUNGSRISIKO
    4. All Beipackzettel edges produce finite, positive S_eff
"""

from __future__ import annotations

import math
import os
import shutil
import unittest

from e0_controller import Landscape, HybridMode, Outcome
from e0_controller.controller import E0Controller, RunTrace
from e0_controller.demo_beipackzettel import (
    IBUPROFEN_EDGES,
    build_ibuprofen_landscape,
    run_scenario,
)


class TestBeipackzettelLandscape(unittest.TestCase):
    """Structural tests for the Beipackzettel landscape."""

    def setUp(self):
        self.L = build_ibuprofen_landscape(include_interaction=True)

    def test_all_edges_have_finite_positive_tension(self):
        """Every Beipackzettel edge produces 0 < S_eff < ∞."""
        for (src, tgt), (delta, resistance, label) in IBUPROFEN_EDGES.items():
            s_eff = self.L.effective_tension(src, tgt)
            self.assertGreater(s_eff, 0.0,
                               f"S_eff({src}→{tgt}) must be > 0")
            self.assertFalse(math.isinf(s_eff),
                             f"S_eff({src}→{tgt}) must be finite")

    def test_therapeutic_path_lower_burden_than_risk(self):
        """Therapeutic edges have lower S_eff than side-effect edges."""
        s_therapeutic = self.L.effective_tension("IBU_400", "BESSERUNG")
        s_magen = self.L.effective_tension("IBU_400", "MAGEN_REIZUNG")
        self.assertLess(s_therapeutic, s_magen,
                        "Therapeutic path should have lower burden than GI side effect")

    def test_high_dose_increases_side_effect_burden(self):
        """IBU_800 → MAGEN_REIZUNG has lower resistance (= more likely) than IBU_400."""
        r_400 = IBUPROFEN_EDGES[("IBU_400", "MAGEN_REIZUNG")][1]
        r_800 = IBUPROFEN_EDGES[("IBU_800", "MAGEN_REIZUNG")][1]
        self.assertLess(r_800, r_400,
                        "Higher dose should make side effect more likely (lower R₀)")

    def test_state_counts(self):
        """Landscape has expected number of states."""
        states = self.L.states
        # All unique nodes from IBUPROFEN_EDGES
        expected = set()
        for (s, t) in IBUPROFEN_EDGES:
            expected.add(s)
            expected.add(t)
        self.assertEqual(states, expected)

    def test_edge_count(self):
        """All edges registered."""
        count = 0
        for s in self.L.states:
            count += len(self.L.admissible_neighbors(s))
        self.assertEqual(count, len(IBUPROFEN_EDGES))

    def test_landscape_without_interaction(self):
        """Without interaction flag, ASS edges are excluded."""
        L_no_ass = build_ibuprofen_landscape(include_interaction=False)
        self.assertNotIn("ASS_PARALLEL", L_no_ass.states)

    def test_ass_convergence_on_bleeding_risk(self):
        """Both ASS_PARALLEL and IBU_400 have edges to BLUTUNGSRISIKO → convergent burden."""
        s_ass = self.L.effective_tension("ASS_PARALLEL", "BLUTUNGSRISIKO")
        s_ibu = self.L.effective_tension("IBU_400", "BLUTUNGSRISIKO")
        self.assertFalse(math.isinf(s_ass))
        self.assertFalse(math.isinf(s_ibu))
        # ASS path has lower resistance = higher pharmacological risk
        self.assertLess(s_ass, s_ibu,
                        "ASS → BLUTUNGSRISIKO should be easier (lower burden) "
                        "because ASS irreversibly inhibits COX-1")


class TestBeipackzettelController(unittest.TestCase):
    """Behavioural tests: controller navigation through Beipackzettel landscape."""

    @classmethod
    def setUpClass(cls):
        cls._memo_dir = "memos/_bpz_test"

    def tearDown(self):
        if os.path.exists(self._memo_dir):
            shutil.rmtree(self._memo_dir)

    def _execute(self, source: str, target: str) -> Outcome:
        return Outcome.SUCCESS

    def test_therapeutic_path_reaches_goal(self):
        """Amplitude-on-disagree with goal_reaching geometry finds GESUND."""
        L = build_ibuprofen_landscape(include_interaction=False)
        ctrl = E0Controller(
            L, self._execute,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=4,
            hybrid_goals={"GESUND"},
            hybrid_geometry="goal_reaching",
            alpha=0.5, recent_k=2,
        )
        trace = ctrl.run("KOPFSCHMERZ", goal="GESUND", max_cycles=20)
        self.assertIn("GESUND", trace.path,
                      f"Controller must reach GESUND. Path: {trace.path}")

    def test_greedy_takes_dose_escalation_path(self):
        """Greedy finds GESUND but through the longer dose-escalation route.

        S_eff(KEINE_WIRKUNG)=0.15 < S_eff(BESSERUNG)=0.18, so greedy detours
        through IBU_800 before finding BESSERUNG from there.
        """
        L = build_ibuprofen_landscape(include_interaction=False)
        ctrl = E0Controller(
            L, self._execute,
            hybrid_mode=HybridMode.GREEDY,
            alpha=0.5, recent_k=2,
        )
        trace = ctrl.run("KOPFSCHMERZ", goal="GESUND", max_cycles=20)
        self.assertIn("GESUND", trace.path)
        self.assertIn("KEINE_WIRKUNG", trace.path,
                      "Greedy should detour through KEINE_WIRKUNG")
        self.assertIn("IBU_800", trace.path,
                      "Greedy should pass through dose escalation")
        # Path is longer than optimal (3 steps)
        self.assertGreater(len(trace.steps), 3)

    def test_simple_geometry_trapped_by_amplitude(self):
        """simple geometry + amplitude override gets trapped in side-effect loop.

        Without goal awareness, amplitude prefers MAGEN_REIZUNG (more outgoing
        paths → more amplitude mass) over BESSERUNG → controller loops.
        """
        L = build_ibuprofen_landscape(include_interaction=False)
        ctrl = E0Controller(
            L, self._execute,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=4,
            hybrid_goals={"GESUND"},
            hybrid_geometry="simple",
            alpha=0.5, recent_k=2,
        )
        trace = ctrl.run("KOPFSCHMERZ", goal="GESUND", max_cycles=20)
        self.assertNotIn("GESUND", trace.path,
                         "simple geometry should get trapped (no goal bias)")

    def test_therapeutic_path_avoids_severe_risks(self):
        """Amplitude mode should not visit MAGENULKUS or NOTFALL."""
        L = build_ibuprofen_landscape(include_interaction=False)
        ctrl = E0Controller(
            L, self._execute,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=4,
            hybrid_goals={"GESUND"},
            hybrid_geometry="goal_reaching",
            alpha=0.5, recent_k=2,
        )
        trace = ctrl.run("KOPFSCHMERZ", goal="GESUND", max_cycles=15)
        severe = {"MAGENULKUS", "NOTFALL", "NIERE_STRESS", "HERZ_RISIKO"}
        visited_severe = severe & set(trace.path)
        self.assertEqual(visited_severe, set(),
                         f"Should not visit severe risk states: {visited_severe}")

    def test_total_tension_bounded(self):
        """Total path tension for therapeutic route should be moderate."""
        L = build_ibuprofen_landscape(include_interaction=False)
        ctrl = E0Controller(
            L, self._execute,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=4,
            hybrid_goals={"GESUND"},
            hybrid_geometry="goal_reaching",
            alpha=0.5, recent_k=2,
        )
        trace = ctrl.run("KOPFSCHMERZ", goal="GESUND", max_cycles=15)
        if "GESUND" in trace.path:
            self.assertLess(trace.total_tension, 2.0,
                            "Therapeutic path tension should be low")

    def test_interaction_landscape_has_more_risk(self):
        """With ASS interaction, more risk-adjacent edges are reachable."""
        L = build_ibuprofen_landscape(include_interaction=True)
        bleeding_neighbors = L.admissible_neighbors("BLUTUNGSRISIKO")
        self.assertIn("NOTFALL", bleeding_neighbors,
                      "BLUTUNGSRISIKO → NOTFALL must exist")

    def test_dose_escalation_trap_structure(self):
        """Verify the trap cycle exists: IBU_400 → KEINE_WIRKUNG → IBU_800 → side effects → ABSETZEN → KOPFSCHMERZ."""
        L = build_ibuprofen_landscape(include_interaction=False)
        # Forward path exists
        self.assertIn("KEINE_WIRKUNG", L.admissible_neighbors("IBU_400"))
        self.assertIn("IBU_800", L.admissible_neighbors("KEINE_WIRKUNG"))
        self.assertIn("MAGEN_REIZUNG", L.admissible_neighbors("IBU_800"))
        self.assertIn("ABSETZEN", L.admissible_neighbors("MAGEN_REIZUNG"))
        self.assertIn("KOPFSCHMERZ", L.admissible_neighbors("ABSETZEN"))

    def test_scenario_runner_returns_expected_keys(self):
        """run_scenario returns a dict with all expected fields."""
        L = build_ibuprofen_landscape(include_interaction=False)
        r = run_scenario("test", L, "KOPFSCHMERZ", "GESUND", max_cycles=10)
        for key in ("name", "path", "steps", "total_tension",
                     "goal_reached", "visited_risks", "hybrid_overrides",
                     "override_details", "trace"):
            self.assertIn(key, r)


class TestBeipackzettelEdgeSemantics(unittest.TestCase):
    """Semantic integrity: edge parameters encode medical knowledge correctly."""

    def test_all_delta_in_range(self):
        """All Δ values between 0 and 1."""
        for (src, tgt), (delta, _r, _label) in IBUPROFEN_EDGES.items():
            self.assertGreater(delta, 0.0, f"Δ({src}→{tgt}) must be > 0")
            self.assertLessEqual(delta, 1.0, f"Δ({src}→{tgt}) must be ≤ 1")

    def test_all_resistance_positive(self):
        """All R₀ values are positive."""
        for (src, tgt), (_d, resistance, _label) in IBUPROFEN_EDGES.items():
            self.assertGreater(resistance, 0.0,
                               f"R₀({src}→{tgt}) must be > 0")

    def test_all_edges_labelled(self):
        """Every edge has a non-empty German label."""
        for (src, tgt), (_d, _r, label) in IBUPROFEN_EDGES.items():
            self.assertTrue(len(label) > 0,
                            f"Edge ({src}→{tgt}) needs a label")

    def test_therapeutic_edges_low_resistance(self):
        """Direct therapeutic edges should have R₀ < 0.3."""
        therapeutic = [
            ("KOPFSCHMERZ", "IBU_400"),
            ("IBU_400", "BESSERUNG"),
            ("BESSERUNG", "GESUND"),
        ]
        for src, tgt in therapeutic:
            r = IBUPROFEN_EDGES[(src, tgt)][1]
            self.assertLess(r, 0.3,
                            f"Therapeutic edge ({src}→{tgt}) should have low R₀")

    def test_severe_side_effects_high_resistance(self):
        """Severe complications should have R₀ ≥ 0.4."""
        severe = [
            ("IBU_800", "NIERE_STRESS"),
            ("IBU_800", "HERZ_RISIKO"),
            ("PARACETAMOL", "LEBER_STRESS"),
        ]
        for src, tgt in severe:
            r = IBUPROFEN_EDGES[(src, tgt)][1]
            self.assertGreaterEqual(r, 0.4,
                                    f"Severe edge ({src}→{tgt}) should have high R₀")


if __name__ == "__main__":
    unittest.main()
