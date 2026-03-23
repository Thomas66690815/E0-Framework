"""
Tests for E₀ Evaluation Layer (Phase 3f)
==========================================
Unit tests for RunEvaluation, SemanticEvaluation, ScenarioEvaluation,
hard failure detection, and rating assignment.
"""

import unittest
from e0_controller.evaluation import (
    RunEvaluation,
    SemanticEvaluation,
    ScenarioEvaluation,
    evaluate_run,
    evaluate_semantics,
    evaluate_scenario,
    detect_hard_failure,
    format_evaluation_report,
    _count_repeated_cycles,
    _assign_rating,
)
from e0_controller.graph_validation import GraphQuality
from e0_controller.llm_adapter import TransitionResult
from e0_controller.primitives import Outcome, Edge
from e0_controller.scenario_loader import ScenarioPacket


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _make_gq(
    reachable=True, happy_path="DEFAULT", happy_path_length=3,
    score=0.85, traps=None, loops=None,
):
    """Create a minimal GraphQuality for testing."""
    if happy_path == "DEFAULT":
        happy_path = ["A", "B", "C", "D"]
    return GraphQuality(
        reachable=reachable,
        happy_path=happy_path,
        happy_path_length=happy_path_length,
        recovery_edges=[],
        recovery_count=0,
        traps=traps or [],
        trivial_loops=loops or [],
        state_count=5,
        edge_count=8,
        score=score,
    )


def _make_scenario():
    return ScenarioPacket(
        scenario_id="test_001",
        domain="test_domain",
        title="Test Scenario",
        source_text="A competitor announced a new platform with capabilities.",
        objective="Produce a briefing",
        required_outputs=[
            "announcement_summary",
            "capabilities",
            "risks",
            "recommended_actions",
        ],
    )


def _make_result(text="", outcome=Outcome.SUCCESS, confidence=0.8):
    return TransitionResult(outcome=outcome, result=text, confidence=confidence)


# ──────────────────────────────────────────────
# Test: Repeated Cycle Counting
# ──────────────────────────────────────────────

class TestRepeatedCycles(unittest.TestCase):

    def test_no_cycles(self):
        self.assertEqual(_count_repeated_cycles(["A", "B", "C", "D"]), 0)

    def test_single_oscillation_not_counted(self):
        # A→B→A is one 2-cycle, first occurrence — not "repeated"
        self.assertEqual(_count_repeated_cycles(["A", "B", "A"]), 0)

    def test_repeated_oscillation(self):
        # A→B→A→B→A — two A↔B cycles, one repeated
        self.assertEqual(_count_repeated_cycles(["A", "B", "A", "B", "A"]), 1)

    def test_many_repeats(self):
        path = ["A", "B"] * 10 + ["A"]  # 10 A↔B cycles
        self.assertEqual(_count_repeated_cycles(path), 9)

    def test_empty_path(self):
        self.assertEqual(_count_repeated_cycles([]), 0)

    def test_short_path(self):
        self.assertEqual(_count_repeated_cycles(["A"]), 0)
        self.assertEqual(_count_repeated_cycles(["A", "B"]), 0)

    def test_different_cycles(self):
        # A→B→A (1st A↔B) then C→D→C (1st C↔D) — no repeats
        path = ["A", "B", "A", "C", "D", "C"]
        self.assertEqual(_count_repeated_cycles(path), 0)


# ──────────────────────────────────────────────
# Test: Rating Assignment
# ──────────────────────────────────────────────

class TestRating(unittest.TestCase):

    def test_hard_failure_is_F(self):
        self.assertEqual(
            _assign_rating(True, 1.0, 1.0, 0.0, 1.0, "some failure"), "F")

    def test_goal_not_reached_no_progress_is_F(self):
        self.assertEqual(
            _assign_rating(False, 0.0, 0.3, 0.0, None, None), "F")

    def test_goal_not_reached_with_progress_is_D(self):
        self.assertEqual(
            _assign_rating(False, 0.0, 0.6, 0.0, None, None), "D")

    def test_perfect_run_is_A(self):
        self.assertEqual(
            _assign_rating(True, 1.0, 1.0, 0.0, 1.0, None), "A")

    def test_moderate_efficiency_is_B(self):
        self.assertEqual(
            _assign_rating(True, 0.5, 0.8, 0.1, 0.7, None), "B")

    def test_weak_run_is_C(self):
        self.assertEqual(
            _assign_rating(True, 0.2, 0.5, 0.3, 0.4, None), "C")


# ──────────────────────────────────────────────
# Test: Run Evaluation
# ──────────────────────────────────────────────

class TestRunEvaluation(unittest.TestCase):

    def test_perfect_run(self):
        path = ["A", "B", "C", "D"]  # 3 steps, matches happy path of 3
        ev = evaluate_run(
            path=path, steps=3, escalation_count=0, revisit_count=0,
            success_rate=1.0, avg_tension=0.5, total_tension=1.5,
            reached_goal=True, happy_path_length=3,
        )
        self.assertTrue(ev.goal_reached)
        self.assertEqual(ev.steps, 3)
        self.assertEqual(ev.rating, "A")
        self.assertAlmostEqual(ev.goal_reach_efficiency, 1.0)
        self.assertEqual(ev.repeated_cycles, 0)
        self.assertAlmostEqual(ev.loop_penalty, 0.0)
        self.assertEqual(ev.warnings, [])

    def test_loopy_run(self):
        # 3-step happy but took 10 with oscillations
        path = ["A", "B", "A", "B", "A", "B", "A", "C", "B", "C", "D"]
        ev = evaluate_run(
            path=path, steps=10, escalation_count=1, revisit_count=6,
            success_rate=0.8, avg_tension=0.6, total_tension=6.0,
            reached_goal=True, happy_path_length=3,
        )
        self.assertTrue(ev.goal_reached)
        self.assertGreater(ev.repeated_cycles, 0)
        self.assertGreater(ev.loop_penalty, 0)
        self.assertLessEqual(ev.goal_reach_efficiency, 0.5)
        self.assertIn(ev.rating, ("B", "C"))

    def test_failed_run(self):
        path = ["A", "B", "A", "B", "A"]
        ev = evaluate_run(
            path=path, steps=4, escalation_count=2, revisit_count=2,
            success_rate=0.5, avg_tension=0.8, total_tension=3.2,
            reached_goal=False, happy_path_length=3,
        )
        self.assertFalse(ev.goal_reached)
        self.assertIn(ev.rating, ("D", "F"))
        self.assertIn("Goal not reached", ev.warnings)

    def test_zero_steps(self):
        ev = evaluate_run(
            path=[], steps=0, escalation_count=0, revisit_count=0,
            success_rate=0.0, avg_tension=0.0, total_tension=0.0,
            reached_goal=False, happy_path_length=0,
        )
        self.assertFalse(ev.goal_reached)
        self.assertEqual(ev.steps, 0)
        self.assertAlmostEqual(ev.progress_ratio, 0.0)


# ──────────────────────────────────────────────
# Test: Semantic Evaluation
# ──────────────────────────────────────────────

class TestSemanticEvaluation(unittest.TestCase):

    def test_full_coverage(self):
        scenario = _make_scenario()
        results = [
            _make_result("Announcement summary of the new capabilities"),
            _make_result("Analysis of risks and recommended actions"),
        ]
        ev = evaluate_semantics(results, scenario)
        self.assertAlmostEqual(ev.required_outputs_covered, 1.0)
        self.assertEqual(ev.missing_outputs, [])

    def test_partial_coverage(self):
        scenario = _make_scenario()
        results = [
            _make_result("Here is the announcement summary"),
        ]
        ev = evaluate_semantics(results, scenario)
        self.assertGreater(ev.required_outputs_covered, 0.0)
        self.assertLess(ev.required_outputs_covered, 1.0)
        self.assertTrue(len(ev.missing_outputs) > 0)

    def test_no_coverage(self):
        scenario = _make_scenario()
        results = [_make_result("Nothing relevant here")]
        ev = evaluate_semantics(results, scenario)
        self.assertLess(ev.required_outputs_covered, 0.5)

    def test_uncertainty_markers(self):
        scenario = _make_scenario()
        results = [
            _make_result(
                "Announcement summary of capabilities. Risks include "
                "uncertainty and potentially unclear outcomes. "
                "Recommended actions needed."
            ),
        ]
        ev = evaluate_semantics(results, scenario)
        self.assertGreater(ev.uncertainty_marks, 0)

    def test_grounding_warnings(self):
        scenario = _make_scenario()
        results = [
            _make_result(
                "It is well known that this announcement summary shows "
                "capabilities. Obviously the risks are guaranteed. "
                "Recommended actions."
            ),
        ]
        ev = evaluate_semantics(results, scenario)
        self.assertGreater(ev.grounding_warnings, 0)

    def test_empty_results(self):
        scenario = _make_scenario()
        ev = evaluate_semantics([], scenario)
        self.assertAlmostEqual(ev.required_outputs_covered, 0.0)
        self.assertAlmostEqual(ev.completeness_score, 0.0)


# ──────────────────────────────────────────────
# Test: Hard Failure Detection
# ──────────────────────────────────────────────

class TestHardFailure(unittest.TestCase):

    def test_unreachable_graph(self):
        gq = _make_gq(reachable=False, happy_path=None, score=0.0)
        result = detect_hard_failure(gq, False, 0, 5)
        self.assertIsNotNone(result)
        self.assertIn("not reachable", result)

    def test_no_happy_path(self):
        gq = _make_gq(reachable=True, happy_path=None, score=0.3)
        result = detect_hard_failure(gq, True, 0, 5)
        self.assertIsNotNone(result)
        self.assertIn("no happy path", result)

    def test_goal_not_reached(self):
        gq = _make_gq()
        result = detect_hard_failure(gq, False, 0, 5)
        self.assertIsNotNone(result)
        self.assertIn("Goal not reached", result)

    def test_trivial_loop_dominance(self):
        gq = _make_gq()
        result = detect_hard_failure(gq, True, 8, 10)
        self.assertIsNotNone(result)
        self.assertIn("Trivial loop", result)

    def test_critical_semantic_gap(self):
        gq = _make_gq()
        result = detect_hard_failure(gq, True, 0, 5, semantic_coverage=0.1)
        self.assertIsNotNone(result)
        self.assertIn("semantic gap", result)

    def test_no_failure(self):
        gq = _make_gq()
        result = detect_hard_failure(gq, True, 0, 5, semantic_coverage=0.8)
        self.assertIsNone(result)


# ──────────────────────────────────────────────
# Test: Scenario Evaluation
# ──────────────────────────────────────────────

class TestScenarioEvaluation(unittest.TestCase):

    def test_successful_scenario(self):
        gq = _make_gq()
        scenario = _make_scenario()
        results = [
            _make_result("Announcement summary of new capabilities."),
            _make_result("Assessment of risks and recommended actions."),
        ]
        ev = evaluate_scenario(
            scenario_id="test_001", domain="test",
            gq=gq, path=["A", "B", "C", "D"],
            steps=3, escalation_count=0, revisit_count=0,
            success_rate=1.0, avg_tension=0.5, total_tension=1.5,
            reached_goal=True, result_log=results, scenario=scenario,
        )
        self.assertIsNone(ev.hard_failure)
        self.assertIsNotNone(ev.overall_score)
        self.assertEqual(ev.run_evaluation.rating, "A")
        self.assertIsNotNone(ev.semantic_evaluation)

    def test_hard_failure_nullifies_overall(self):
        gq = _make_gq(reachable=False, happy_path=None, score=0.0)
        ev = evaluate_scenario(
            scenario_id="fail_001", domain="test",
            gq=gq, path=["A"],
            steps=1, escalation_count=0, revisit_count=0,
            success_rate=0.0, avg_tension=0.0, total_tension=0.0,
            reached_goal=False, result_log=[],
        )
        self.assertIsNotNone(ev.hard_failure)
        self.assertIsNone(ev.overall_score)
        self.assertEqual(ev.run_evaluation.rating, "F")

    def test_without_scenario_no_semantic_eval(self):
        gq = _make_gq()
        ev = evaluate_scenario(
            scenario_id="no_sc", domain="test",
            gq=gq, path=["A", "B", "C", "D"],
            steps=3, escalation_count=0, revisit_count=0,
            success_rate=1.0, avg_tension=0.5, total_tension=1.5,
            reached_goal=True, result_log=[],
        )
        self.assertIsNone(ev.semantic_evaluation)
        # Still gets overall score (semantic defaults to 0.5)
        self.assertIsNotNone(ev.overall_score)


# ──────────────────────────────────────────────
# Test: Report Formatting
# ──────────────────────────────────────────────

class TestReportFormatting(unittest.TestCase):

    def test_report_renders(self):
        gq = _make_gq()
        scenario = _make_scenario()
        results = [
            _make_result("Announcement summary, capabilities, risks, actions"),
        ]
        ev = evaluate_scenario(
            scenario_id="test_001", domain="test",
            gq=gq, path=["A", "B", "C", "D"],
            steps=3, escalation_count=0, revisit_count=0,
            success_rate=1.0, avg_tension=0.5, total_tension=1.5,
            reached_goal=True, result_log=results, scenario=scenario,
        )
        report = format_evaluation_report([ev])
        self.assertIn("Evaluation Layer Report", report)
        self.assertIn("test_001", report)
        self.assertIn("Rating:", report)

    def test_cross_domain_summary_in_report(self):
        gq = _make_gq()
        ev1 = evaluate_scenario(
            "s1", "domain_a", gq, ["A", "B", "C"], 2, 0, 0,
            1.0, 0.5, 1.0, True, [],
        )
        ev2 = evaluate_scenario(
            "s2", "domain_b", gq, ["A", "B", "C", "D"], 3, 1, 0,
            0.8, 0.6, 1.8, True, [],
        )
        report = format_evaluation_report([ev1, ev2])
        self.assertIn("Cross-Domain Summary", report)
        self.assertIn("Mean Overall", report)


# ──────────────────────────────────────────────
# Test: Hybrid / Overlay Evaluation (Phase 3o)
# ──────────────────────────────────────────────

class TestHybridEvaluation(unittest.TestCase):
    """Tests for hybrid/overlay fields in RunEvaluation."""

    def test_default_hybrid_fields(self):
        """evaluate_run without hybrid params has safe defaults."""
        ev = evaluate_run(
            path=["A", "B", "C"], steps=2, escalation_count=0,
            revisit_count=0, success_rate=1.0, avg_tension=0.3,
            total_tension=0.6, reached_goal=True, happy_path_length=2,
        )
        self.assertEqual(ev.hybrid_override_count, 0)
        self.assertAlmostEqual(ev.hybrid_override_rate, 0.0)
        self.assertAlmostEqual(ev.overlay_agree_rate, 1.0)
        self.assertEqual(ev.overlay_count, 0)

    def test_hybrid_fields_passed_through(self):
        """Hybrid metrics are stored correctly in RunEvaluation."""
        ev = evaluate_run(
            path=["A", "B", "C", "D"], steps=3, escalation_count=0,
            revisit_count=0, success_rate=1.0, avg_tension=0.3,
            total_tension=0.9, reached_goal=True, happy_path_length=3,
            hybrid_override_count=2, hybrid_override_rate=0.667,
            overlay_agree_rate=0.333, overlay_count=3,
        )
        self.assertEqual(ev.hybrid_override_count, 2)
        self.assertAlmostEqual(ev.hybrid_override_rate, 0.667, places=3)
        self.assertAlmostEqual(ev.overlay_agree_rate, 0.333, places=3)
        self.assertEqual(ev.overlay_count, 3)

    def test_high_override_warning(self):
        """Override rate > 50% triggers a warning."""
        ev = evaluate_run(
            path=["A", "B", "C", "D"], steps=3, escalation_count=0,
            revisit_count=0, success_rate=1.0, avg_tension=0.3,
            total_tension=0.9, reached_goal=True, happy_path_length=3,
            hybrid_override_count=2, hybrid_override_rate=0.667,
            overlay_agree_rate=0.333, overlay_count=3,
        )
        override_warnings = [w for w in ev.warnings if "override" in w.lower()]
        self.assertEqual(len(override_warnings), 1)

    def test_low_agree_warning(self):
        """Overlay agree rate < 50% triggers a warning."""
        ev = evaluate_run(
            path=["A", "B", "C", "D", "E"], steps=4, escalation_count=0,
            revisit_count=0, success_rate=1.0, avg_tension=0.3,
            total_tension=1.2, reached_goal=True, happy_path_length=4,
            hybrid_override_count=0, hybrid_override_rate=0.0,
            overlay_agree_rate=0.25, overlay_count=4,
        )
        agree_warnings = [w for w in ev.warnings if "disagree" in w.lower()]
        self.assertEqual(len(agree_warnings), 1)

    def test_no_warning_when_rates_ok(self):
        """No hybrid warnings when override and agree rates are healthy."""
        ev = evaluate_run(
            path=["A", "B", "C", "D"], steps=3, escalation_count=0,
            revisit_count=0, success_rate=1.0, avg_tension=0.3,
            total_tension=0.9, reached_goal=True, happy_path_length=3,
            hybrid_override_count=1, hybrid_override_rate=0.333,
            overlay_agree_rate=0.667, overlay_count=3,
        )
        hybrid_warnings = [w for w in ev.warnings
                           if "override" in w.lower() or "disagree" in w.lower()]
        self.assertEqual(len(hybrid_warnings), 0)


class TestHybridScenarioEvaluation(unittest.TestCase):
    """Tests for hybrid passthrough in evaluate_scenario."""

    def test_hybrid_metrics_in_scenario(self):
        gq = _make_gq()
        ev = evaluate_scenario(
            scenario_id="hybrid_001", domain="test",
            gq=gq, path=["A", "B", "C", "D"],
            steps=3, escalation_count=0, revisit_count=0,
            success_rate=1.0, avg_tension=0.3, total_tension=0.9,
            reached_goal=True, result_log=[],
            hybrid_override_count=1, hybrid_override_rate=0.333,
            overlay_agree_rate=0.667, overlay_count=3,
        )
        self.assertEqual(ev.run_evaluation.hybrid_override_count, 1)
        self.assertAlmostEqual(ev.run_evaluation.hybrid_override_rate, 0.333, places=3)
        self.assertEqual(ev.run_evaluation.overlay_count, 3)

    def test_hybrid_report_section(self):
        """format_evaluation_report includes hybrid section when data present."""
        gq = _make_gq()
        ev = evaluate_scenario(
            scenario_id="hybrid_rpt", domain="test",
            gq=gq, path=["A", "B", "C", "D"],
            steps=3, escalation_count=0, revisit_count=0,
            success_rate=1.0, avg_tension=0.3, total_tension=0.9,
            reached_goal=True, result_log=[],
            hybrid_override_count=2, hybrid_override_rate=0.5,
            overlay_agree_rate=0.5, overlay_count=4,
        )
        report = format_evaluation_report([ev])
        self.assertIn("Overlay Steps", report)
        self.assertIn("Hybrid Overrides", report)
        self.assertIn("Override Rate", report)

    def test_no_hybrid_section_when_zero(self):
        """format_evaluation_report omits hybrid section when no overlay data."""
        gq = _make_gq()
        ev = evaluate_scenario(
            scenario_id="greedy_001", domain="test",
            gq=gq, path=["A", "B", "C", "D"],
            steps=3, escalation_count=0, revisit_count=0,
            success_rate=1.0, avg_tension=0.3, total_tension=0.9,
            reached_goal=True, result_log=[],
        )
        report = format_evaluation_report([ev])
        self.assertNotIn("Overlay Steps", report)
        self.assertNotIn("Hybrid Overrides", report)


if __name__ == "__main__":
    unittest.main()
