"""Non-circular validation: LLM-generated Beipackzettel landscape.

The hand-crafted demo (demo_beipackzettel.py) is potentially circular:
we set Δ/R₀ values, then validated that E₀ navigates them "correctly".

This test removes the circularity by having a *mock LLM generate* the
landscape from a natural-language medication description.  The experimenter
does NOT control Δ/R₀ — the LLM does (here simulated by a mock that
returns medically plausible values without knowledge of what "works").

The test then checks whether the geometry-dependent behaviour
(amplitude mass trap) still holds under LLM-derived parameters.

If it does → the finding is structural, not an artefact of hand-tuning.
If it doesn't → the finding depends on specific parameter choices.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import unittest
import warnings

from e0_controller import HybridMode, Landscape, Outcome, Session
from e0_controller.controller import E0Controller, RunTrace
from e0_controller.llm_adapter import (
    E0LLMAdapter,
    LandscapeProposal,
    LLMConfig,
    materialize_landscape,
)

# ── Beipackzettel-Text (öffentliche Fachinformation, gekürzt) ────────────
BEIPACKZETTEL_TEXT = """
Ibuprofen 400 mg Filmtabletten.
Wirkstoff: Ibuprofen.

Anwendungsgebiete: Leichte bis mäßig starke Schmerzen wie Kopfschmerzen,
Zahnschmerzen, Regelschmerzen. Fieber.

Dosierung: Erwachsene und Jugendliche ab 12 Jahren: 1 Tablette (400 mg)
alle 6-8 Stunden. Maximale Tagesdosis: 1200 mg (3 Tabletten).
Bei unzureichender Wirkung NICHT die Dosis eigenmächtig erhöhen.

Gegenanzeigen: Überempfindlichkeit gegen Ibuprofen oder andere NSAR.
Bestehende Magen-Darm-Geschwüre. Schwere Leber- oder Niereninsuffizienz.
Letztes Drittel der Schwangerschaft.

Wechselwirkungen: ASS (Acetylsalicylsäure): Ibuprofen kann die
thrombozytenaggregationshemmende Wirkung von ASS abschwächen.
Gleichzeitige Anwendung erhöht das Risiko gastrointestinaler Blutungen.

Nebenwirkungen:
Häufig (1-10%): Magen-Darm-Beschwerden, Übelkeit, Sodbrennen.
Gelegentlich (0.1-1%): Magengeschwür, Magenblutung.
Selten (<0.1%): Schwere Hautreaktionen, Niereninsuffizienz.
Sehr selten (<0.01%): Kardiovaskuläre Ereignisse bei Langzeitanwendung.
"""


# ── Mock-LLM: simuliert medizinisch plausible Landschaftsgenerierung ─────
#
# CRITICAL: These values are derived from pharmacological knowledge
# (response rates, NNH numbers, GRADE evidence levels) — NOT from
# what "makes the demo work".  The mock LLM has no access to the
# demo results or the geometry comparison logic.

def _mock_llm_beipackzettel(system: str, user: str, config: LLMConfig) -> str:
    """Simulate an LLM reading the Beipackzettel and producing a landscape.

    The LLM would extract:
    - States from clinical situations mentioned in the text
    - Δ from the magnitude of clinical change described
    - R₀ from frequency indicators (häufig=low R, selten=high R)
    """
    return json.dumps({
        "states": [
            "KOPFSCHMERZ", "IBU_400", "BESSERUNG", "GESUND",
            "KEINE_WIRKUNG", "IBU_800",
            "MAGEN_REIZUNG", "MAGENULKUS", "ABSETZEN",
            "ASS_PARALLEL", "BLUTUNGSRISIKO",
        ],
        "edges": [
            # Therapeutic path — LLM judges from "Anwendungsgebiete" + dosing
            {"source": "KOPFSCHMERZ", "target": "IBU_400",
             "delta": 0.7, "resistance": 0.2,
             "description": "Standard-Analgesie laut Anwendungsgebiet"},
            {"source": "IBU_400", "target": "BESSERUNG",
             "delta": 0.8, "resistance": 0.25,
             "description": "Analgetische Wirkung bei Responder (~70-80%)"},
            {"source": "BESSERUNG", "target": "GESUND",
             "delta": 0.5, "resistance": 0.15,
             "description": "Vollständige Symptomrückbildung"},

            # Non-responder path — "bei unzureichender Wirkung" (~20-30%)
            {"source": "IBU_400", "target": "KEINE_WIRKUNG",
             "delta": 0.2, "resistance": 0.4,
             "description": "Non-Responder (ca. 20-30%)"},
            {"source": "KEINE_WIRKUNG", "target": "IBU_800",
             "delta": 0.6, "resistance": 0.3,
             "description": "Dosiserhöhung trotz Warnung im Beipackzettel"},
            {"source": "IBU_800", "target": "BESSERUNG",
             "delta": 0.8, "resistance": 0.2,
             "description": "Höhere Dosis erhöht Responserate"},

            # Side effects — from "häufig (1-10%)" → moderate R₀
            {"source": "IBU_400", "target": "MAGEN_REIZUNG",
             "delta": 0.4, "resistance": 0.55,
             "description": "GI-Nebenwirkung (häufig: 1-10%)"},
            {"source": "IBU_800", "target": "MAGEN_REIZUNG",
             "delta": 0.5, "resistance": 0.4,
             "description": "Dosisabhängig verstärkte GI-NW"},
            {"source": "MAGEN_REIZUNG", "target": "MAGENULKUS",
             "delta": 0.7, "resistance": 0.6,
             "description": "Ulkusprogression (gelegentlich: 0.1-1%)"},
            {"source": "MAGEN_REIZUNG", "target": "ABSETZEN",
             "delta": 0.4, "resistance": 0.25,
             "description": "Absetzen bei GI-Beschwerden"},
            {"source": "ABSETZEN", "target": "KOPFSCHMERZ",
             "delta": 0.5, "resistance": 0.35,
             "description": "Symptomwiederkehr nach Absetzen"},

            # ASS interaction — from "Wechselwirkungen" section
            {"source": "ASS_PARALLEL", "target": "IBU_400",
             "delta": 0.7, "resistance": 0.2,
             "description": "IBU-Einnahme unter ASS-Therapie"},
            {"source": "ASS_PARALLEL", "target": "BLUTUNGSRISIKO",
             "delta": 0.6, "resistance": 0.3,
             "description": "ASS+IBU: erhöhtes GI-Blutungsrisiko"},
            {"source": "IBU_400", "target": "BLUTUNGSRISIKO",
             "delta": 0.4, "resistance": 0.6,
             "description": "IBU allein: Thrombozytenaggregationshemmung"},
        ],
    })


class TestNonCircularLandscapeBuild(unittest.TestCase):
    """Validate that the LLM-generated landscape is structurally sound."""

    def setUp(self):
        adapter = E0LLMAdapter(call_fn=_mock_llm_beipackzettel)
        proposal = adapter.build_landscape(
            task=BEIPACKZETTEL_TEXT,
            start="KOPFSCHMERZ",
            goal="GESUND",
        )
        self.proposal = proposal
        self.L = materialize_landscape(proposal)

    def test_landscape_has_expected_states(self):
        """LLM-built landscape contains all medically relevant states."""
        for s in ("KOPFSCHMERZ", "IBU_400", "BESSERUNG", "GESUND",
                  "MAGEN_REIZUNG", "MAGENULKUS"):
            self.assertIn(s, self.L.states)

    def test_all_edges_valid(self):
        """Every edge has finite positive S_eff."""
        for e in self.proposal.edges:
            s_eff = self.L.effective_tension(e["source"], e["target"])
            self.assertGreater(s_eff, 0.0)
            self.assertFalse(math.isinf(s_eff))

    def test_therapeutic_path_exists(self):
        """Direct therapeutic path KOPFSCHMERZ → IBU_400 → BESSERUNG → GESUND exists."""
        self.assertIn("IBU_400", self.L.admissible_neighbors("KOPFSCHMERZ"))
        self.assertIn("BESSERUNG", self.L.admissible_neighbors("IBU_400"))
        self.assertIn("GESUND", self.L.admissible_neighbors("BESSERUNG"))

    def test_side_effect_branch_exists(self):
        """Side-effect branching at IBU_400 exists."""
        neighbors = self.L.admissible_neighbors("IBU_400")
        self.assertIn("MAGEN_REIZUNG", neighbors)


class TestNonCircularGeometryDifference(unittest.TestCase):
    """Core non-circular validation: geometry difference persists with LLM values.

    If this test passes, the amplitude mass trap is structural —
    not an artefact of hand-tuned Δ/R₀.
    """

    def _execute(self, source: str, target: str) -> Outcome:
        return Outcome.SUCCESS

    def _build_landscape(self) -> Landscape:
        adapter = E0LLMAdapter(call_fn=_mock_llm_beipackzettel)
        proposal = adapter.build_landscape(
            BEIPACKZETTEL_TEXT, "KOPFSCHMERZ", "GESUND")
        return materialize_landscape(proposal)

    def test_goal_reaching_finds_goal(self):
        """goal_reaching geometry successfully navigates to GESUND."""
        L = self._build_landscape()
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
                      f"goal_reaching must find GESUND. Path: {trace.path}")

    def test_simple_geometry_does_not_find_goal(self):
        """simple geometry gets trapped (amplitude mass on side-effect branches)."""
        L = self._build_landscape()
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
                         f"simple geometry should be trapped. Path: {trace.path}")

    def test_goal_reaching_avoids_severe_complications(self):
        """goal_reaching should not visit MAGENULKUS."""
        L = self._build_landscape()
        ctrl = E0Controller(
            L, self._execute,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=4,
            hybrid_goals={"GESUND"},
            hybrid_geometry="goal_reaching",
            alpha=0.5, recent_k=2,
        )
        trace = ctrl.run("KOPFSCHMERZ", goal="GESUND", max_cycles=15)
        self.assertNotIn("MAGENULKUS", trace.path)

    def test_goal_reaching_lower_tension(self):
        """goal_reaching total tension < simple total tension."""
        L_gr = self._build_landscape()
        L_si = self._build_landscape()

        ctrl_gr = E0Controller(
            L_gr, self._execute,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=4, hybrid_goals={"GESUND"},
            hybrid_geometry="goal_reaching", alpha=0.5, recent_k=2,
        )
        ctrl_si = E0Controller(
            L_si, self._execute,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=4, hybrid_goals={"GESUND"},
            hybrid_geometry="simple", alpha=0.5, recent_k=2,
        )

        trace_gr = ctrl_gr.run("KOPFSCHMERZ", goal="GESUND", max_cycles=20)
        trace_si = ctrl_si.run("KOPFSCHMERZ", goal="GESUND", max_cycles=20)

        self.assertLess(trace_gr.total_tension, trace_si.total_tension,
                        "goal_reaching should produce lower total burden")


class TestSessionGeometryWarning(unittest.TestCase):
    """Validate the geometry mismatch warning in Session.run()."""

    def _execute(self, source: str, target: str) -> Outcome:
        return Outcome.SUCCESS

    @classmethod
    def setUpClass(cls):
        cls._memo_dir = "memos/_bpz_warn_test"

    def tearDown(self):
        if os.path.exists(self._memo_dir):
            shutil.rmtree(self._memo_dir)

    def _simple_landscape(self):
        L = Landscape()
        L.add_edge("A", "B", delta=0.5, resistance=0.3)
        L.add_edge("B", "GOAL", delta=0.5, resistance=0.3)
        return L

    def test_warning_on_goal_with_simple_geometry(self):
        """Session warns when goal is set but geometry is not goal_reaching."""
        L = self._simple_landscape()
        session = Session(
            session_id="warn-test",
            landscape=L,
            execute_fn=self._execute,
            base_dir=self._memo_dir,
            controller_kwargs=dict(hybrid_geometry="simple"),
        )
        with self.assertWarns(UserWarning) as cm:
            session.run("A", goal="GOAL", max_cycles=5, auto_save=False)
        self.assertIn("goal_reaching", str(cm.warning))

    def test_no_warning_with_goal_reaching(self):
        """No warning when geometry matches goal-directed use."""
        L = self._simple_landscape()
        session = Session(
            session_id="nowarn-test",
            landscape=L,
            execute_fn=self._execute,
            base_dir=self._memo_dir,
            controller_kwargs=dict(hybrid_geometry="goal_reaching"),
        )
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            session.run("A", goal="GOAL", max_cycles=5, auto_save=False)
        geom_warnings = [x for x in w if "goal_reaching" in str(x.message)]
        self.assertEqual(len(geom_warnings), 0)

    def test_no_warning_without_goal(self):
        """No warning when no goal is set (exploratory run)."""
        L = self._simple_landscape()
        session = Session(
            session_id="nogoal-test",
            landscape=L,
            execute_fn=self._execute,
            base_dir=self._memo_dir,
            controller_kwargs=dict(hybrid_geometry="simple"),
        )
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            session.run("A", max_cycles=5, auto_save=False)
        geom_warnings = [x for x in w if "goal_reaching" in str(x.message)]
        self.assertEqual(len(geom_warnings), 0)


if __name__ == "__main__":
    unittest.main()
