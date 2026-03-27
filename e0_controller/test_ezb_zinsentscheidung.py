"""Tests for the EZB-Zinsentscheidung real-world landscape (Domäne 2).

Verifies that E₀ structural primitives correctly model macroeconomic
monetary policy relationships and that the controller exhibits the
expected behaviour across three structurally distinct scenarios:

  C35-EZB — EZB Real-World Claim:
    1. Inflation path reaches Preisstabilität under goal_reaching
    2. Multi-goal correctly navigates competing ECB mandates
    3. Stagflation produces Gordian-trap topology (high resistance on all exits)
    4. Cycles: Wachstum → Inflation → Zinserhöhung → Rezession is traversable
    5. Geometry difference persists with LLM-generated parameters (non-circular)

Domain contrast vs. Beipackzettel (Domäne 1):
    - Cycles (boom-bust feedback loops)
    - Multi-goal (Preisstabilität + Wachstum)
    - Gordian topology (Stagflation trap)
    - Higher connectivity (~18 edges, 11 states)
"""

from __future__ import annotations

import json
import math
import os
import shutil
import unittest

from e0_controller import HybridMode, Landscape, Outcome
from e0_controller.controller import E0Controller, RunTrace
from e0_controller.primitives import Edge
from e0_controller.demo_ezb_zinsentscheidung import (
    EZB_EDGES,
    build_ezb_landscape,
    run_scenario,
)


class TestEZBLandscapeStructure(unittest.TestCase):
    """Structural tests for the EZB landscape."""

    def setUp(self):
        self.L = build_ezb_landscape()

    def test_all_edges_have_finite_positive_tension(self):
        """Every EZB edge produces 0 < S_eff < ∞."""
        for (src, tgt) in EZB_EDGES:
            s_eff = self.L.effective_tension(src, tgt)
            self.assertGreater(s_eff, 0.0, f"S_eff({src}→{tgt}) must be > 0")
            self.assertFalse(math.isinf(s_eff), f"S_eff({src}→{tgt}) must be finite")

    def test_state_count(self):
        """Landscape has 11 macroeconomic states."""
        expected = set()
        for (s, t) in EZB_EDGES:
            expected.add(s)
            expected.add(t)
        self.assertEqual(self.L.states, expected)
        self.assertEqual(len(expected), 11)

    def test_edge_count(self):
        """All 16 edges registered."""
        count = sum(len(self.L.admissible_neighbors(s)) for s in self.L.states)
        self.assertEqual(count, len(EZB_EDGES))

    def test_cycle_exists(self):
        """Boom-bust cycle is traversable."""
        cycle = [
            ("WACHSTUM", "INFLATION_HOCH"),
            ("INFLATION_HOCH", "ZINS_ERHOEHUNG"),
            ("ZINS_ERHOEHUNG", "REZESSION"),
            ("REZESSION", "ZINS_SENKUNG"),
            ("ZINS_SENKUNG", "KREDIT_EXPANSION"),
            ("KREDIT_EXPANSION", "WACHSTUM"),
        ]
        for src, tgt in cycle:
            self.assertIn(tgt, self.L.admissible_neighbors(src),
                          f"Cycle edge {src}→{tgt} must exist")

    def test_inflation_hoch_single_exit(self):
        """INFLATION_HOCH has only one policy option: ZINS_ERHOEHUNG."""
        neighbors = self.L.admissible_neighbors("INFLATION_HOCH")
        self.assertEqual(set(neighbors), {"ZINS_ERHOEHUNG"})

    def test_zins_senkung_single_transit(self):
        """ZINS_SENKUNG exits only via KREDIT_EXPANSION (credit channel)."""
        neighbors = self.L.admissible_neighbors("ZINS_SENKUNG")
        self.assertEqual(set(neighbors), {"KREDIT_EXPANSION"})


class TestStagflationGordianTrap(unittest.TestCase):
    """Stagflation should exhibit Gordian-trap characteristics."""

    def setUp(self):
        self.L = build_ezb_landscape()

    def test_stagflation_has_three_exits(self):
        """STAGFLATION has exactly 3 neighbors."""
        neighbors = self.L.admissible_neighbors("STAGFLATION")
        self.assertEqual(len(neighbors), 3)
        self.assertEqual(set(neighbors),
                         {"ZINS_ERHOEHUNG", "ZINS_SENKUNG", "STRUKTURREFORM"})

    def test_stagflation_is_isolated_trap(self):
        """STAGFLATION has no incoming edges — it's an external starting condition."""
        for (src, tgt) in EZB_EDGES:
            self.assertNotEqual(tgt, "STAGFLATION",
                                f"{src} should not lead to STAGFLATION")

    def test_all_stagflation_exits_high_resistance(self):
        """All exits from STAGFLATION have R₀ ≥ 0.70."""
        for (src, tgt), (_, r, _) in EZB_EDGES.items():
            if src == "STAGFLATION":
                self.assertGreaterEqual(r, 0.70,
                                        f"STAGFLATION→{tgt} should have high resistance")

    def test_stagflation_higher_burden_than_normal_policy(self):
        """S_eff from STAGFLATION→ZINS_ERHOEHUNG > INFLATION_HOCH→ZINS_ERHOEHUNG."""
        s_stag_hike = self.L.effective_tension("STAGFLATION", "ZINS_ERHOEHUNG")
        s_normal_hike = self.L.effective_tension("INFLATION_HOCH", "ZINS_ERHOEHUNG")
        self.assertGreater(s_stag_hike, s_normal_hike)

    def test_stagflation_zins_senkung_highest_resistance(self):
        """Rate cut during stagflation has the highest resistance."""
        r_cut = EZB_EDGES[("STAGFLATION", "ZINS_SENKUNG")][1]
        r_hike = EZB_EDGES[("STAGFLATION", "ZINS_ERHOEHUNG")][1]
        r_reform = EZB_EDGES[("STAGFLATION", "STRUKTURREFORM")][1]
        self.assertGreater(r_cut, r_hike)
        self.assertGreater(r_cut, r_reform)


class TestInflationScenario(unittest.TestCase):
    """Szenario 1: Inflationsbekämpfung → Preisstabilität."""

    def test_goal_reaching_finds_preisstabilitaet(self):
        """goal_reaching geometry reaches PREISSTABILITAET from INFLATION_HOCH."""
        L = build_ezb_landscape()
        r = run_scenario("test_inflation", L,
                         start="INFLATION_HOCH", goal="PREISSTABILITAET",
                         hybrid_geometry="goal_reaching")
        self.assertIn("PREISSTABILITAET", r["goals_reached"])

    def test_inflation_path_includes_zins_erhoehung(self):
        """Controller must go through ZINS_ERHOEHUNG."""
        L = build_ezb_landscape()
        r = run_scenario("test_inflation_path", L,
                         start="INFLATION_HOCH", goal="PREISSTABILITAET",
                         hybrid_geometry="goal_reaching")
        self.assertIn("ZINS_ERHOEHUNG", r["path"])

    def test_inflation_path_avoids_stagflation(self):
        """Controller avoids STAGFLATION from INFLATION_HOCH."""
        L = build_ezb_landscape()
        r = run_scenario("test_inflation_avoid_stag", L,
                         start="INFLATION_HOCH", goal="PREISSTABILITAET",
                         hybrid_geometry="goal_reaching")
        self.assertFalse(r["visited_stagflation"])

    def test_therapeutic_path_short(self):
        """Direct inflation path ≤ 4 steps."""
        L = build_ezb_landscape()
        r = run_scenario("test_inflation_short", L,
                         start="INFLATION_HOCH", goal="PREISSTABILITAET",
                         hybrid_geometry="goal_reaching")
        self.assertLessEqual(r["steps"], 4)


class TestRezessionMultiGoal(unittest.TestCase):
    """Szenario 2: Rezession → Multi-Goal (Wachstum + Preisstabilität)."""

    def test_multi_goal_reaches_wachstum(self):
        """Controller reaches WACHSTUM from REZESSION."""
        L = build_ezb_landscape()
        r = run_scenario("test_rezession_multi", L,
                         start="REZESSION",
                         goals={"WACHSTUM", "PREISSTABILITAET"},
                         goal="WACHSTUM",
                         hybrid_geometry="goal_reaching")
        self.assertIn("WACHSTUM", r["goals_reached"])

    def test_rezession_avoids_stagflation(self):
        """With goal_reaching, controller prefers recovery over STAGFLATION."""
        L = build_ezb_landscape()
        r = run_scenario("test_rezession_avoid_stag", L,
                         start="REZESSION",
                         goals={"WACHSTUM", "PREISSTABILITAET"},
                         goal="WACHSTUM",
                         hybrid_geometry="goal_reaching")
        self.assertFalse(r["visited_stagflation"])

    def test_rezession_recovery_path(self):
        """First step from REZESSION should be ZINS_SENKUNG (recovery)."""
        L = build_ezb_landscape()
        r = run_scenario("test_rezession_recovery", L,
                         start="REZESSION",
                         goals={"WACHSTUM"},
                         goal="WACHSTUM",
                         hybrid_geometry="goal_reaching")
        self.assertEqual(r["path"][1], "ZINS_SENKUNG")


class TestStagflationScenario(unittest.TestCase):
    """Szenario 3: Stagflation (Gordian Trap) — already inside the trap."""

    def test_stagflation_eventually_escapes(self):
        """Controller can escape STAGFLATION and reach PREISSTABILITAET."""
        L = build_ezb_landscape()
        r = run_scenario("test_stagflation_escape", L,
                         start="STAGFLATION", goal="PREISSTABILITAET",
                         hybrid_geometry="goal_reaching", max_cycles=25)
        self.assertIn("PREISSTABILITAET", r["goals_reached"])

    def test_stagflation_harder_burden_than_inflation(self):
        """Stagflation escape accumulates higher total burden."""
        L = build_ezb_landscape()
        r_inflation = run_scenario("test_steps_i", L,
                                   start="INFLATION_HOCH",
                                   goal="PREISSTABILITAET",
                                   hybrid_geometry="goal_reaching")
        L2 = build_ezb_landscape()
        r_stagflation = run_scenario("test_steps_s", L2,
                                     start="STAGFLATION",
                                     goal="PREISSTABILITAET",
                                     hybrid_geometry="goal_reaching",
                                     max_cycles=25)
        self.assertGreaterEqual(r_stagflation["steps"], r_inflation["steps"])
        self.assertGreater(r_stagflation["total_tension"],
                           r_inflation["total_tension"])

    def test_stagflation_total_burden_higher(self):
        """Total burden from STAGFLATION exceeds from INFLATION_HOCH."""
        L = build_ezb_landscape()
        r_inflation = run_scenario("test_burden_i", L,
                                   start="INFLATION_HOCH",
                                   goal="PREISSTABILITAET",
                                   hybrid_geometry="goal_reaching")
        L2 = build_ezb_landscape()
        r_stagflation = run_scenario("test_burden_s", L2,
                                     start="STAGFLATION",
                                     goal="PREISSTABILITAET",
                                     hybrid_geometry="goal_reaching",
                                     max_cycles=25)
        self.assertGreater(r_stagflation["total_tension"],
                           r_inflation["total_tension"])


class TestGeometryDifference(unittest.TestCase):
    """After amplitude mass trap removal, geometries should agree on the
    optimal path — the locally cheapest edge is also globally best."""

    def test_both_geometries_reach_goal_from_rezession(self):
        """simple and goal_reaching both reach WACHSTUM from REZESSION."""
        L1 = build_ezb_landscape()
        r_simple = run_scenario("test_geom_simple", L1,
                                start="REZESSION", goal="WACHSTUM",
                                hybrid_geometry="simple")
        L2 = build_ezb_landscape()
        r_goal = run_scenario("test_geom_goal", L2,
                              start="REZESSION", goal="WACHSTUM",
                              hybrid_geometry="goal_reaching")
        self.assertIn("WACHSTUM", r_simple["goals_reached"])
        self.assertIn("WACHSTUM", r_goal["goals_reached"])


class TestCycleDetection(unittest.TestCase):
    """Verify that E₀ handles economic cycles correctly."""

    def _execute(self, source: str, target: str) -> Outcome:
        return Outcome.SUCCESS

    def test_no_infinite_loop_in_cycle(self):
        """Controller terminates even when cycles exist (max_cycles bound)."""
        L = build_ezb_landscape()
        ctrl = E0Controller(
            L, self._execute,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=5,
            hybrid_goals={"PREISSTABILITAET"},
            hybrid_geometry="goal_reaching",
        )
        trace = ctrl.run("WACHSTUM", goal="PREISSTABILITAET", max_cycles=15)
        self.assertLessEqual(len(trace.steps), 15)

    def test_historization_shifts_tension(self):
        """Visiting an edge changes its effective tension via historization."""
        L = build_ezb_landscape()
        edge = Edge("INFLATION_HOCH", "ZINS_ERHOEHUNG")
        s1 = L.effective_tension(edge.source, edge.target)
        # Simulate one traversal
        L.historization.update(edge, Outcome.SUCCESS)
        s2 = L.effective_tension(edge.source, edge.target)
        self.assertNotEqual(s1, s2, "Historization should shift tension after visit")


# ── Non-circular validation (Mock-LLM) ──────────────────────────────────

EZB_QUELLTEXT = """
Pressekonferenz der EZB zum geldpolitischen Beschluss, Frankfurt am Main.

Die Inflation im Euroraum liegt bei 4,2 % und damit deutlich über dem
Zielwert von 2 %. Der EZB-Rat hat beschlossen, die Leitzinsen um 25
Basispunkte anzuheben. Das Ziel ist die Rückkehr zur Preisstabilität.

Gleichzeitig verlangsamt sich das Wirtschaftswachstum. Das BIP-Wachstum
liegt bei 0,3 % im Quartal. Die Arbeitslosenquote steigt leicht auf 6,8 %.
Einige Mitglieder des Rats sehen Rezessionsrisiken.

Die EZB verfolgt ein duales Mandat: Preisstabilität als Primärziel und,
soweit damit vereinbar, Unterstützung der allgemeinen Wirtschaftspolitik
einschließlich Wachstum und Beschäftigung.

Risikoszenario Stagflation: Sollten Energiepreisschocks anhalten und
gleichzeitig die Nachfrage einbrechen, entstünde eine Situation, in der
weder Zinserhöhung noch Zinssenkung wirksam wäre. Strukturreformen
wären dann der einzig gangbare Weg, erfordern aber politischen Konsens
und wirken erst langfristig.

Transmissionsmechanismus: Zinserhöhungen wirken über höhere Kreditkosten
auf die Investitionsnachfrage. Die Wirkung tritt mit Verzögerung ein
(6-18 Monate). Bei Zinssenkungen stimuliert günstigerer Kredit die
Kreditexpansion, was über den Multiplikatoreffekt das BIP steigert.
"""


def _mock_llm_ezb(system: str, user: str, config) -> str:
    """Simulate an LLM reading the EZB press conference and producing a landscape.

    This mock intentionally keeps INFLATION_HOCH → STAGFLATION (a plausible LLM
    interpretation of the press text) to demonstrate the amplitude mass trap:
    the 3 exit families from STAGFLATION overwhelm the direct policy path via
    constructive interference.  The hand-tuned demo landscape removes this edge.
    """
    return json.dumps({
        "states": [
            "INFLATION_HOCH", "ZINS_ERHOEHUNG", "INFLATION_SINKT",
            "PREISSTABILITAET", "REZESSION", "ARBEITSLOSIGKEIT",
            "ZINS_SENKUNG", "KREDIT_EXPANSION", "WACHSTUM",
            "STAGFLATION", "STRUKTURREFORM",
        ],
        "edges": [
            {"source": "INFLATION_HOCH", "target": "ZINS_ERHOEHUNG",
             "delta": 0.75, "resistance": 0.25,
             "description": "Leitzinsanhebung bei 4,2% Inflation"},
            {"source": "INFLATION_HOCH", "target": "STAGFLATION",
             "delta": 0.45, "resistance": 0.60,
             "description": "Angebotsschock + schwache Nachfrage"},
            {"source": "ZINS_ERHOEHUNG", "target": "INFLATION_SINKT",
             "delta": 0.65, "resistance": 0.45,
             "description": "Transmissionsmechanismus wirkt verzögert (6-18 Mon.)"},
            {"source": "INFLATION_SINKT", "target": "PREISSTABILITAET",
             "delta": 0.55, "resistance": 0.20,
             "description": "Inflation erreicht Zielband 2%"},

            {"source": "ZINS_ERHOEHUNG", "target": "REZESSION",
             "delta": 0.55, "resistance": 0.50,
             "description": "Übermäßige Straffung bei 0,3% Quartalswachstum"},
            {"source": "REZESSION", "target": "ARBEITSLOSIGKEIT",
             "delta": 0.65, "resistance": 0.35,
             "description": "Konjunktureinbruch → AL-Quote steigt über 6,8%"},
            {"source": "ARBEITSLOSIGKEIT", "target": "ZINS_SENKUNG",
             "delta": 0.70, "resistance": 0.25,
             "description": "Politischer Druck zur geldpol. Lockerung"},

            {"source": "REZESSION", "target": "ZINS_SENKUNG",
             "delta": 0.65, "resistance": 0.30,
             "description": "EZB senkt Leitzins zur Konjunkturstützung"},
            {"source": "ZINS_SENKUNG", "target": "KREDIT_EXPANSION",
             "delta": 0.55, "resistance": 0.40,
             "description": "Günstigere Kreditkonditionen"},
            {"source": "KREDIT_EXPANSION", "target": "WACHSTUM",
             "delta": 0.45, "resistance": 0.35,
             "description": "Multiplikatoreffekt → BIP-Wachstum"},
            {"source": "ZINS_SENKUNG", "target": "WACHSTUM",
             "delta": 0.40, "resistance": 0.45,
             "description": "Direkte Konjunkturwirkung"},

            {"source": "WACHSTUM", "target": "INFLATION_HOCH",
             "delta": 0.35, "resistance": 0.55,
             "description": "Nachfrageüberhang → erneuter Preisdruck"},
            {"source": "WACHSTUM", "target": "PREISSTABILITAET",
             "delta": 0.30, "resistance": 0.30,
             "description": "Moderates Wachstum bei stabilen Preisen"},
            {"source": "PREISSTABILITAET", "target": "WACHSTUM",
             "delta": 0.35, "resistance": 0.25,
             "description": "Stable Preise fördern Investition"},

            {"source": "REZESSION", "target": "STAGFLATION",
             "delta": 0.40, "resistance": 0.55,
             "description": "Rezession + importierte Inflation"},
            {"source": "STAGFLATION", "target": "ZINS_ERHOEHUNG",
             "delta": 0.55, "resistance": 0.75,
             "description": "Zinserhöhung in Stagflation: politisch extrem schwierig"},
            {"source": "STAGFLATION", "target": "ZINS_SENKUNG",
             "delta": 0.45, "resistance": 0.80,
             "description": "Zinssenkung würde Inflation weiter anheizen"},
            {"source": "STAGFLATION", "target": "STRUKTURREFORM",
             "delta": 0.65, "resistance": 0.70,
             "description": "Angebotsseitige Reformen brauchen polit. Konsens"},
            {"source": "STRUKTURREFORM", "target": "WACHSTUM",
             "delta": 0.55, "resistance": 0.60,
             "description": "Strukturmaßnahmen wirken langfristig nachhaltig"},
        ],
    })


class TestNonCircularEZBLandscape(unittest.TestCase):
    """Non-circular validation: LLM-generated EZB landscape.

    The mock LLM intentionally includes INFLATION_HOCH → STAGFLATION
    (19 edges vs 18 in the hand-tuned demo) to demonstrate the amplitude
    mass trap as a cross-domain structural phenomenon.
    """

    def setUp(self):
        from e0_controller.llm_adapter import (
            E0LLMAdapter, materialize_landscape,
        )
        adapter = E0LLMAdapter(call_fn=_mock_llm_ezb)
        self.proposal = adapter.build_landscape(
            task=EZB_QUELLTEXT,
            start="INFLATION_HOCH",
            goal="PREISSTABILITAET",
        )
        self.L = materialize_landscape(self.proposal)

    def test_landscape_correct_size(self):
        """LLM-generated landscape has 11 states."""
        self.assertEqual(len(self.L.states), 11)

    def test_all_edges_finite(self):
        """Every edge has finite positive S_eff."""
        for e in self.proposal.edges:
            s_eff = self.L.effective_tension(e["source"], e["target"])
            self.assertGreater(s_eff, 0.0)
            self.assertFalse(math.isinf(s_eff))

    def test_stagflation_gordian_structure(self):
        """STAGFLATION exits all have R₀ ≥ 0.70 in LLM-generated landscape."""
        stagflation_edges = [e for e in self.proposal.edges
                             if e["source"] == "STAGFLATION"]
        self.assertEqual(len(stagflation_edges), 3)
        for e in stagflation_edges:
            self.assertGreaterEqual(e["resistance"], 0.70,
                                    f"Stagflation→{e['target']} should have high R₀")

    def test_cycle_exists_in_llm_landscape(self):
        """Boom-bust cycle traversable in LLM-generated landscape."""
        self.assertIn("INFLATION_HOCH",
                      self.L.admissible_neighbors("WACHSTUM"))
        self.assertIn("ZINS_ERHOEHUNG",
                      self.L.admissible_neighbors("INFLATION_HOCH"))

    def test_inflation_hoch_has_two_exits(self):
        """Mock LLM gives INFLATION_HOCH two exits (incl. STAGFLATION)."""
        neighbors = self.L.admissible_neighbors("INFLATION_HOCH")
        self.assertEqual(set(neighbors), {"ZINS_ERHOEHUNG", "STAGFLATION"})


class TestNonCircularAmplitudeMassTrap(unittest.TestCase):
    """Prove the amplitude mass trap is a cross-domain structural phenomenon.

    The mock LLM includes INFLATION_HOCH → STAGFLATION.  STAGFLATION's 3 exit
    families produce constructive interference that overwhelms the single direct
    policy path (ZINS_ERH → INFL_SINKT → PREISSTAB).  The controller gets
    trapped in a cycle: IH → STAG → ZS → W → IH → …

    This is the SAME structural phenomenon observed in the Beipackzettel
    domain — confirming that the amplitude mass trap is domain-invariant.

    Resolution requires a path_family_imbalance detector in the amplitude
    overlay + self-tuning coupling (see MEMO_AMPLITUDE_MASS_TRAP.md).
    """

    def _execute(self, source: str, target: str) -> Outcome:
        return Outcome.SUCCESS

    def _build_landscape(self) -> Landscape:
        from e0_controller.llm_adapter import E0LLMAdapter, materialize_landscape
        adapter = E0LLMAdapter(call_fn=_mock_llm_ezb)
        proposal = adapter.build_landscape(EZB_QUELLTEXT,
                                           "INFLATION_HOCH", "PREISSTABILITAET")
        return materialize_landscape(proposal)

    def test_mass_trap_prevents_goal_from_inflation_hoch(self):
        """Controller cycles without reaching goal due to amplitude mass trap."""
        L = self._build_landscape()
        ctrl = E0Controller(
            L, self._execute,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=5,
            hybrid_goals={"PREISSTABILITAET"},
            hybrid_geometry="goal_reaching",
        )
        trace = ctrl.run("INFLATION_HOCH", goal="PREISSTABILITAET", max_cycles=20)
        # Mass trap: controller cycles, NEVER reaches goal
        self.assertNotIn("PREISSTABILITAET", trace.path,
                         "With mass trap active, controller should NOT reach goal")
        # It visits STAGFLATION repeatedly
        stag_visits = trace.path.count("STAGFLATION")
        self.assertGreater(stag_visits, 1,
                           "Controller should visit STAGFLATION multiple times")

    def test_mass_trap_from_stagflation_also_cycles(self):
        """Starting inside STAGFLATION, controller also cycles."""
        L = self._build_landscape()
        ctrl = E0Controller(
            L, self._execute,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=5,
            hybrid_goals={"PREISSTABILITAET"},
            hybrid_geometry="goal_reaching",
        )
        trace = ctrl.run("STAGFLATION", goal="PREISSTABILITAET", max_cycles=25)
        self.assertNotIn("PREISSTABILITAET", trace.path,
                         "Mass trap propagates: even from STAGFLATION, no escape")

    def test_greedy_escapes_mass_trap(self):
        """Pure GREEDY (no amplitude overlay) reaches goal from INFLATION_HOCH.

        This proves the trap is caused by the amplitude overlay, not the graph."""
        L = self._build_landscape()
        ctrl = E0Controller(
            L, self._execute,
            hybrid_mode=HybridMode.GREEDY,
        )
        trace = ctrl.run("INFLATION_HOCH", goal="PREISSTABILITAET", max_cycles=20)
        self.assertIn("PREISSTABILITAET", trace.path,
                      "Greedy must reach goal — the graph IS navigable")
        self.assertNotIn("STAGFLATION", trace.path,
                         "Greedy avoids STAGFLATION (higher S_eff)")

    def test_demo_landscape_avoids_trap(self):
        """Hand-tuned demo landscape (no IH→STAG edge) avoids mass trap."""
        L = build_ezb_landscape()
        ctrl = E0Controller(
            L, self._execute,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=5,
            hybrid_goals={"PREISSTABILITAET"},
            hybrid_geometry="goal_reaching",
        )
        trace = ctrl.run("INFLATION_HOCH", goal="PREISSTABILITAET", max_cycles=20)
        self.assertIn("PREISSTABILITAET", trace.path,
                      "Demo landscape must reach goal (trap removed)")


if __name__ == "__main__":
    unittest.main()
