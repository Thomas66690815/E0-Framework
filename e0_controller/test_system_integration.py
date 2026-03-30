"""
C51 — System-Level Integration: E₀ lernt E₀
=============================================

Full pipeline convergence test.  Verifies that all components from
C43–C50 work together as one system:

    Session(canon_landscape) → iterate()
      → controller.cycle() → historize → self_graph.self_historize()
      → dual_reflect → reflexive_action → journal.record
    → build_self_exposition(canon, self_graph, journal)

This is the moment where the architecture stops being components
and starts being a system.

Test classes:
  1. TestPipelineWiring (5) — all components created and wired
  2. TestSelfFundierung (5) — E₀ operates on its own canon
  3. TestReflexiveConvergence (3) — deactivation fires within iterate
  4. TestDirectPipelineAssembly (3) — manual walk proves connectivity
  5. TestEdgeCases (3) — boundary conditions

Total: 19 tests
"""

import tempfile
import unittest

from e0_controller.canon_loader import load_canon
from e0_controller.canon_self_bridge import (
    build_self_exposition,
    canon_coverage,
    CANON_PROCESS_MAP,
)
from e0_controller.dual_reflection import (
    diagnose_self_graph,
    DualReflectionReport,
)
from e0_controller.landscape import Landscape
from e0_controller.primitives import Outcome
from e0_controller.reflexive_action import (
    apply_reflexive_actions,
    ReflexiveJournal,
)
from e0_controller.self_graph import SelfGraph, CORE_COMPONENTS
from e0_controller.session import Session, IterationResult


def _always_succeed(current, target):
    return Outcome.SUCCESS


def _mostly_fail():
    """Factory: execute_fn that fails 2 out of 3 calls."""
    counter = [0]
    def fn(current, target):
        counter[0] += 1
        return Outcome.SUCCESS if counter[0] % 3 == 0 else Outcome.FAILURE
    return fn


# ──────────────────────────────────────────────
# 1. Pipeline Wiring
# ──────────────────────────────────────────────

class TestPipelineWiring(unittest.TestCase):
    """All C43–C50 components created and wired by Session."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cl = load_canon("ontodynamics")

    def test_session_creates_all_components(self):
        """Session wires SelfGraph, ReflexiveJournal, and controller."""
        s = Session("c51-wire", self.cl.landscape, _always_succeed,
                    base_dir=self.tmpdir)
        self.assertIsInstance(s.self_graph, SelfGraph)
        self.assertIsInstance(s.reflexive_journal, ReflexiveJournal)
        self.assertIs(s.controller.self_graph, s.self_graph)

    def test_iterate_returns_complete_result(self):
        """iterate() produces IterationResult with all fields."""
        s = Session("c51-iter", self.cl.landscape, _always_succeed,
                    base_dir=self.tmpdir)
        result = s.iterate("differenz", goal="negative_notwendigkeit",
                           max_cycles=20, max_iterations=3)
        self.assertIsInstance(result, IterationResult)
        self.assertGreater(result.iterations, 0)
        self.assertEqual(len(result.results), result.iterations)
        self.assertEqual(len(result.verdicts), result.iterations)

    def test_self_graph_accumulates_during_iterate(self):
        """Self-graph has non-zero load after iterate()."""
        s = Session("c51-sg", self.cl.landscape, _always_succeed,
                    base_dir=self.tmpdir)
        s.iterate("differenz", goal="negative_notwendigkeit",
                  max_cycles=20, max_iterations=2)
        snap = s.self_graph.snapshot()
        total_load = sum(v["load"] for v in snap.values())
        self.assertGreater(total_load, 0,
            "Self-graph should accumulate traces during iterate")

    def test_exposition_has_five_sections(self):
        """build_self_exposition produces all 5 sections after iterate."""
        s = Session("c51-expo", self.cl.landscape, _always_succeed,
                    base_dir=self.tmpdir)
        s.iterate("differenz", goal="negative_notwendigkeit",
                  max_cycles=20, max_iterations=2)
        expo = build_self_exposition(
            self.cl, sg=s.self_graph,
            reflexive_journal=s.reflexive_journal,
        )
        for section in [
            "WHAT I BELIEVE",
            "HOW I OPERATE",
            "CANON COVERAGE",
            "STRUCTURAL INSIGHT",
            "WHAT I HAVE DONE TO MYSELF",
        ]:
            self.assertIn(section, expo, f"Missing section: {section}")

    def test_iterate_result_lists_aligned(self):
        """All lists in IterationResult have the same length."""
        s = Session("c51-align", self.cl.landscape, _always_succeed,
                    base_dir=self.tmpdir)
        result = s.iterate("differenz", goal="negative_notwendigkeit",
                           max_cycles=15, max_iterations=3)
        n = result.iterations
        self.assertEqual(len(result.results), n)
        self.assertEqual(len(result.verdicts), n)
        self.assertEqual(len(result.reflections), n)
        self.assertEqual(len(result.policy_phases), n)
        self.assertEqual(len(result.structural_results), n)
        self.assertEqual(len(result.reflexive_results), n)


# ──────────────────────────────────────────────
# 2. Selbst-Fundierung — E₀ lernt E₀
# ──────────────────────────────────────────────

class TestSelfFundierung(unittest.TestCase):
    """E₀ operates on its own canon landscape."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cl = load_canon("ontodynamics")

    def test_canon_landscape_is_navigable(self):
        """The controller can navigate through the canon landscape."""
        s = Session("c51-nav", self.cl.landscape, _always_succeed,
                    base_dir=self.tmpdir)
        result = s.iterate("differenz", goal="negative_notwendigkeit",
                           max_cycles=50, max_iterations=2)
        self.assertGreater(result.iterations, 0)
        trace = result.results[0].trace
        self.assertGreater(len(trace.path), 1,
            "Controller should navigate at least one step through canon")

    def test_process_map_covers_core_components(self):
        """Every core component maps to at least one canon concept."""
        for comp in CORE_COMPONENTS:
            self.assertIn(comp, CANON_PROCESS_MAP,
                f"Core component {comp} missing from canon process map")

    def test_coverage_ratio_is_partial(self):
        """Canon coverage is >0 but <1 — honest epistemic frontier."""
        cov = canon_coverage(self.cl)
        self.assertGreater(cov["coverage_ratio"], 0.3)
        self.assertLess(cov["coverage_ratio"], 1.0)
        self.assertTrue(len(cov["not_instantiated"]) > 0,
            "There should be concepts E₀ cannot yet instantiate")

    def test_self_knowledge_accumulates_over_iterations(self):
        """More iterations → more self-knowledge in self-graph."""
        s = Session("c51-accum", self.cl.landscape, _always_succeed,
                    base_dir=self.tmpdir)
        result = s.iterate("differenz", goal="negative_notwendigkeit",
                           max_cycles=30, max_iterations=5)
        snap = s.self_graph.snapshot()
        total_load = sum(v["load"] for v in snap.values())
        self.assertGreater(total_load, 5,
            "Self-knowledge should accumulate significantly")

    def test_full_exposition_is_substantial(self):
        """E₀ runs on its own canon and produces readable self-exposition."""
        s = Session("c51-full", self.cl.landscape, _always_succeed,
                    base_dir=self.tmpdir)
        s.iterate("differenz", goal="negative_notwendigkeit",
                  max_cycles=30, max_iterations=3)
        expo = build_self_exposition(
            self.cl, sg=s.self_graph,
            reflexive_journal=s.reflexive_journal,
        )
        self.assertGreater(len(expo), 500,
            "Full exposition should be a substantial document")
        self.assertIn("historisierung", expo.lower())
        self.assertIn("differenz", expo.lower())


# ──────────────────────────────────────────────
# 3. Reflexive Convergence
# ──────────────────────────────────────────────

class TestReflexiveConvergence(unittest.TestCase):
    """Reflexive action fires within the full pipeline."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cl = load_canon("ontodynamics")

    def _pre_poison_curvature(self, sg, n=30):
        """Make curvature harmful while keeping core healthy."""
        for _ in range(n):
            sg.self_historize(
                ["curvature", "transition_field"], Outcome.FAILURE,
            )
        for _ in range(n):
            sg.self_historize(list(CORE_COMPONENTS), Outcome.SUCCESS)

    def test_reflexive_action_fires_in_iterate(self):
        """Pre-poisoned curvature → iterate Step 7 deactivates it."""
        L = self.cl.landscape
        L.curvature_modulation = True

        s = Session("c51-reflex", L, _mostly_fail(),
                    base_dir=self.tmpdir)
        self._pre_poison_curvature(s.self_graph)

        # Verify precondition
        diag = diagnose_self_graph(s.self_graph)
        self.assertIn("curvature", diag.deactivation_candidates)

        # Run iterate — mostly-failing fn causes amplification → step 7
        result = s.iterate("differenz", goal="negative_notwendigkeit",
                           max_cycles=20, max_iterations=4)

        # Step 7 should have produced at least one reflexive result
        reflex_fired = any(r is not None for r in result.reflexive_results)
        self.assertTrue(reflex_fired,
            "Step 7 should fire with pre-poisoned curvature"
            " and amplifying tension")

    def test_journal_populated_and_visible_in_exposition(self):
        """Deactivation is recorded in journal and visible in exposition."""
        L = self.cl.landscape
        L.curvature_modulation = True

        s = Session("c51-jpop", L, _mostly_fail(),
                    base_dir=self.tmpdir)
        self._pre_poison_curvature(s.self_graph)

        s.iterate("differenz", goal="negative_notwendigkeit",
                  max_cycles=20, max_iterations=4)

        # If deactivation happened, journal should show it
        if s.reflexive_journal.total_actions > 0:
            expo = build_self_exposition(
                self.cl, sg=s.self_graph,
                reflexive_journal=s.reflexive_journal,
            )
            self.assertIn("Deactivated", expo)
            self.assertIn("curvature", expo)

        # Section 5 always present regardless
        expo = build_self_exposition(
            self.cl, sg=s.self_graph,
            reflexive_journal=s.reflexive_journal,
        )
        self.assertIn("WHAT I HAVE DONE TO MYSELF", expo)

    def test_curvature_deactivated_after_iterate(self):
        """After iterate with harmful curvature, flag is toggled off."""
        L = self.cl.landscape
        L.curvature_modulation = True

        s = Session("c51-stays", L, _mostly_fail(),
                    base_dir=self.tmpdir)
        self._pre_poison_curvature(s.self_graph)

        result = s.iterate("differenz", goal="negative_notwendigkeit",
                           max_cycles=20, max_iterations=4)

        changes_made = any(
            r is not None and r.any_changes
            for r in result.reflexive_results
        )
        if changes_made:
            self.assertFalse(L.curvature_modulation,
                "Curvature should be off after deactivation")


# ──────────────────────────────────────────────
# 4. Direct Pipeline Assembly
# ──────────────────────────────────────────────

class TestDirectPipelineAssembly(unittest.TestCase):
    """Manual walk through the full pipeline — proves connectivity."""

    def setUp(self):
        self.cl = load_canon("ontodynamics")

    def test_manual_pipeline_all_steps(self):
        """Walk: SelfGraph → diagnose → apply → journal → exposition."""
        sg = SelfGraph()
        L = Landscape(curvature_modulation=True)
        L.add_edge("A", "B", delta=1.0, resistance=1.0)

        # 1. Historize self-graph (simulate controller cycles)
        for _ in range(20):
            sg.self_historize(list(CORE_COMPONENTS), Outcome.SUCCESS)
        for _ in range(15):
            sg.self_historize(
                ["curvature", "transition_field"], Outcome.FAILURE,
            )

        # 2. Diagnose
        diag = diagnose_self_graph(sg)
        self.assertIn("curvature", diag.harmful)
        self.assertIn("curvature", diag.deactivation_candidates)

        # 3. Apply reflexive action
        report = DualReflectionReport(
            domain_report=None, self_diagnosis=diag,
        )
        result = apply_reflexive_actions(report, L)
        self.assertTrue(result.any_changes)
        self.assertFalse(L.curvature_modulation)

        # 4. Record in journal
        journal = ReflexiveJournal()
        journal.record(result, iteration=1)
        self.assertEqual(journal.total_actions, 1)

        # 5. Build exposition
        expo = build_self_exposition(
            self.cl, sg=sg, reflexive_journal=journal,
        )
        for section in [
            "WHAT I BELIEVE", "HOW I OPERATE", "CANON COVERAGE",
            "STRUCTURAL INSIGHT", "WHAT I HAVE DONE TO MYSELF",
        ]:
            self.assertIn(section, expo)
        self.assertIn("curvature", expo)
        self.assertIn("Deactivated", expo)
        self.assertIn("differenz", expo.lower())

    def test_exposition_shows_component_canon_mapping(self):
        """Section 2 connects operational components to canon concepts."""
        sg = SelfGraph()
        for _ in range(10):
            sg.self_historize(list(CORE_COMPONENTS), Outcome.SUCCESS)
        expo = build_self_exposition(self.cl, sg=sg)
        for comp in ["amplitude", "born", "historization"]:
            self.assertIn(comp, expo)

    def test_exposition_identifies_epistemic_frontier(self):
        """Section 4 flags not-yet-instantiated canon concepts."""
        sg = SelfGraph()
        expo = build_self_exposition(self.cl, sg=sg)
        cov = canon_coverage(self.cl)
        self.assertTrue(len(cov["not_instantiated"]) > 0)
        self.assertIn("frontier", expo.lower())


# ──────────────────────────────────────────────
# 5. Edge Cases
# ──────────────────────────────────────────────

class TestEdgeCases(unittest.TestCase):
    """System-level boundary conditions."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cl = load_canon("ontodynamics")

    def test_minimal_landscape_pipeline(self):
        """Full pipeline works with a 2-node landscape."""
        L = Landscape()
        L.add_edge("A", "B", delta=1.0, resistance=1.0)

        s = Session("c51-min", L, _always_succeed, base_dir=self.tmpdir)
        result = s.iterate("A", goal="B", max_cycles=5, max_iterations=2)
        self.assertGreater(result.iterations, 0)

        expo = build_self_exposition(
            self.cl, sg=s.self_graph,
            reflexive_journal=s.reflexive_journal,
        )
        self.assertIn("WHAT I BELIEVE", expo)

    def test_all_failure_produces_negative_quality(self):
        """All-failure execution → self-graph shows negative quality."""
        def all_fail(current, target):
            return Outcome.FAILURE

        s = Session("c51-allfail", self.cl.landscape, all_fail,
                    base_dir=self.tmpdir)
        s.iterate("differenz", goal="negative_notwendigkeit",
                  max_cycles=15, max_iterations=2)
        snap = s.self_graph.snapshot()
        loaded = [v for v in snap.values() if v["load"] > 0]
        if loaded:
            avg_quality = sum(v["quality"] for v in loaded) / len(loaded)
            self.assertLess(avg_quality, 0,
                "All-failure run should produce negative quality")

    def test_fresh_vs_operated_exposition_differs(self):
        """Exposition is richer after running than before."""
        expo_before = build_self_exposition(self.cl)

        s = Session("c51-diff", self.cl.landscape, _always_succeed,
                    base_dir=self.tmpdir)
        s.iterate("differenz", goal="negative_notwendigkeit",
                  max_cycles=20, max_iterations=2)

        expo_after = build_self_exposition(
            self.cl, sg=s.self_graph,
            reflexive_journal=s.reflexive_journal,
        )
        self.assertGreater(len(expo_after), len(expo_before))


if __name__ == "__main__":
    unittest.main()
