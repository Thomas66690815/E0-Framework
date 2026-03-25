"""
Tests for E₀ Reflection-Layer Hybrid Metrics (Phase 3h)
==========================================================

Formal verification of amplitude-aware metrics (R_coh, Θ-consistency,
amplitude drift) integrated into RunEvaluation and the Reflection Layer.

Coverage:
  H1 — RunEvaluation carries amplitude fields
  H2 — evaluate_run() accepts and rounds amplitude fields
  H3 — evaluate_scenario() threads amplitude fields
  H4 — Warnings fire on low R_coh / high drift
  H5 — should_reflect() quality triggers on amplitude drift / low R_coh
  H6 — should_reflect() opportunity triggers on high R_coh / Θ
  H7 — _reflect_failure() detects coherence collapse
  H8 — _reflect_quality() detects drift and low coherence
  H9 — _reflect_opportunity() detects high coherence & phase alignment
  H10 — _build_evidence_block() includes amplitude metrics
  H11 — format_evaluation_report() shows amplitude section
  H12 — End-to-end: amplitude triggers reflection pipeline
"""

import unittest
from e0_controller.evaluation import (
    RunEvaluation,
    ScenarioEvaluation,
    SemanticEvaluation,
    evaluate_run,
    evaluate_scenario,
    format_evaluation_report,
)
from e0_controller.graph_validation import GraphQuality
from e0_controller.reflection import (
    ReflectionDecision,
    ReflectionReport,
    should_reflect,
    reflect,
    _reflect_failure,
    _reflect_quality,
    _reflect_opportunity,
    _build_evidence_block,
    format_reflection_report,
    _AMPLITUDE_DRIFT_THRESHOLD,
    _COHERENCE_QUALITY_FLOOR,
    _COHERENCE_OPPORTUNITY_FLOOR,
    _THETA_OPPORTUNITY_FLOOR,
)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _run_eval(
    goal_reached=True, steps=5, escalations=0, revisits=0,
    repeated_cycles=0, progress_ratio=0.8, avg_tension=0.5,
    total_tension=2.5, efficiency=0.8, loop_penalty=0.0,
    success_rate=1.0, rating="A",
    r_coh_avg=0.0, r_coh_min=0.0, r_coh_max=1.0,
    theta_consistency=1.0, amplitude_drift=0.0,
    overlay_agree_rate=1.0, overlay_count=0,
    hybrid_override_count=0, hybrid_override_rate=0.0,
):
    return RunEvaluation(
        goal_reached=goal_reached,
        steps=steps,
        escalations=escalations,
        revisits=revisits,
        repeated_cycles=repeated_cycles,
        progress_ratio=progress_ratio,
        avg_tension=avg_tension,
        total_tension=total_tension,
        goal_reach_efficiency=efficiency,
        loop_penalty=loop_penalty,
        step_success_rate=success_rate,
        rating=rating,
        r_coh_avg=r_coh_avg,
        r_coh_min=r_coh_min,
        r_coh_max=r_coh_max,
        theta_consistency=theta_consistency,
        amplitude_drift=amplitude_drift,
        overlay_agree_rate=overlay_agree_rate,
        overlay_count=overlay_count,
        hybrid_override_count=hybrid_override_count,
        hybrid_override_rate=hybrid_override_rate,
    )


def _scenario_eval(
    run_eval=None, hard_failure=None, graph_score=0.85,
    overall_score=0.80, sem_eval=None,
):
    if run_eval is None:
        run_eval = _run_eval()
    return ScenarioEvaluation(
        scenario_id="test_hybrid",
        domain="hybrid_domain",
        graph_score=graph_score,
        run_evaluation=run_eval,
        semantic_evaluation=sem_eval,
        hard_failure=hard_failure,
        overall_score=overall_score,
    )


def _make_gq(
    reachable=True, happy_path_length=3, score=0.85,
):
    return GraphQuality(
        reachable=reachable,
        happy_path=["A", "B", "C", "D"],
        happy_path_length=happy_path_length,
        recovery_edges=[],
        recovery_count=0,
        traps=[],
        trivial_loops=[],
        state_count=5,
        edge_count=8,
        score=score,
    )


# ══════════════════════════════════════════════
# H1: RunEvaluation carries amplitude fields
# ══════════════════════════════════════════════

class TestH1RunEvaluationFields(unittest.TestCase):
    """RunEvaluation must carry all five amplitude-hybrid fields."""

    def test_default_values(self):
        r = RunEvaluation(
            goal_reached=True, steps=5, escalations=0, revisits=0,
            repeated_cycles=0, progress_ratio=0.8, avg_tension=0.5,
            total_tension=2.5, goal_reach_efficiency=0.8,
            loop_penalty=0.0, step_success_rate=1.0, rating="A",
        )
        self.assertEqual(r.r_coh_avg, 0.0)
        self.assertEqual(r.r_coh_min, 0.0)
        self.assertEqual(r.r_coh_max, 1.0)
        self.assertEqual(r.theta_consistency, 1.0)
        self.assertEqual(r.amplitude_drift, 0.0)

    def test_custom_values(self):
        r = _run_eval(r_coh_avg=0.72, r_coh_min=0.3, r_coh_max=0.95,
                       theta_consistency=0.88, amplitude_drift=0.12)
        self.assertAlmostEqual(r.r_coh_avg, 0.72)
        self.assertAlmostEqual(r.r_coh_min, 0.3)
        self.assertAlmostEqual(r.r_coh_max, 0.95)
        self.assertAlmostEqual(r.theta_consistency, 0.88)
        self.assertAlmostEqual(r.amplitude_drift, 0.12)

    def test_extreme_coherence(self):
        """R_coh can exceed 1.0 (constructive amplification)."""
        r = _run_eval(r_coh_avg=2.5, r_coh_max=4.0)
        self.assertGreater(r.r_coh_avg, 1.0)
        self.assertGreater(r.r_coh_max, 1.0)


# ══════════════════════════════════════════════
# H2: evaluate_run() accepts and rounds amplitude fields
# ══════════════════════════════════════════════

class TestH2EvaluateRunAmplitude(unittest.TestCase):
    """evaluate_run() must accept, round, and store hybrid metrics."""

    def test_amplitude_fields_passed(self):
        r = evaluate_run(
            path=["A", "B", "C", "D"],
            steps=3,
            escalation_count=0,
            revisit_count=0,
            success_rate=1.0,
            avg_tension=0.5,
            total_tension=1.5,
            reached_goal=True,
            happy_path_length=3,
            r_coh_avg=0.654321,
            r_coh_min=0.123456,
            r_coh_max=0.987654,
            theta_consistency=0.876543,
            amplitude_drift=0.234567,
        )
        self.assertAlmostEqual(r.r_coh_avg, 0.6543, places=4)
        self.assertAlmostEqual(r.r_coh_min, 0.1235, places=4)
        self.assertAlmostEqual(r.r_coh_max, 0.9877, places=4)
        self.assertAlmostEqual(r.theta_consistency, 0.8765, places=4)
        self.assertAlmostEqual(r.amplitude_drift, 0.2346, places=4)

    def test_defaults_zero_when_not_provided(self):
        r = evaluate_run(
            path=["A", "B"],
            steps=1,
            escalation_count=0,
            revisit_count=0,
            success_rate=1.0,
            avg_tension=0.5,
            total_tension=0.5,
            reached_goal=True,
            happy_path_length=1,
        )
        self.assertEqual(r.r_coh_avg, 0.0)
        self.assertEqual(r.amplitude_drift, 0.0)
        self.assertEqual(r.theta_consistency, 1.0)


# ══════════════════════════════════════════════
# H3: evaluate_scenario() threads amplitude fields
# ══════════════════════════════════════════════

class TestH3EvaluateScenarioAmplitude(unittest.TestCase):
    """evaluate_scenario() must pass amplitude fields to RunEvaluation."""

    def test_amplitude_threaded_to_run(self):
        gq = _make_gq()
        ev = evaluate_scenario(
            scenario_id="h3",
            domain="test",
            gq=gq,
            path=["A", "B", "C", "D"],
            steps=3,
            escalation_count=0,
            revisit_count=0,
            success_rate=1.0,
            avg_tension=0.5,
            total_tension=1.5,
            reached_goal=True,
            result_log=[],
            r_coh_avg=0.75,
            r_coh_min=0.40,
            r_coh_max=0.95,
            theta_consistency=0.92,
            amplitude_drift=0.08,
        )
        r = ev.run_evaluation
        self.assertAlmostEqual(r.r_coh_avg, 0.75)
        self.assertAlmostEqual(r.r_coh_min, 0.40)
        self.assertAlmostEqual(r.theta_consistency, 0.92)
        self.assertAlmostEqual(r.amplitude_drift, 0.08)


# ══════════════════════════════════════════════
# H4: Warnings fire on low R_coh / high drift
# ══════════════════════════════════════════════

class TestH4AmplitudeWarnings(unittest.TestCase):
    """RunEvaluation warnings must fire for amplitude anomalies."""

    def test_low_coherence_warning(self):
        r = evaluate_run(
            path=["A", "B", "C"],
            steps=2,
            escalation_count=0,
            revisit_count=0,
            success_rate=1.0,
            avg_tension=0.5,
            total_tension=1.0,
            reached_goal=True,
            happy_path_length=2,
            r_coh_avg=0.15,
        )
        self.assertTrue(any("R_coh" in w for w in r.warnings))

    def test_high_drift_warning(self):
        r = evaluate_run(
            path=["A", "B", "C"],
            steps=2,
            escalation_count=0,
            revisit_count=0,
            success_rate=1.0,
            avg_tension=0.5,
            total_tension=1.0,
            reached_goal=True,
            happy_path_length=2,
            amplitude_drift=0.45,
        )
        self.assertTrue(any("drift" in w.lower() for w in r.warnings))

    def test_no_warning_when_coherence_zero(self):
        """R_coh=0 (no overlay) should not produce warning."""
        r = evaluate_run(
            path=["A", "B", "C"],
            steps=2,
            escalation_count=0,
            revisit_count=0,
            success_rate=1.0,
            avg_tension=0.5,
            total_tension=1.0,
            reached_goal=True,
            happy_path_length=2,
            r_coh_avg=0.0,
        )
        self.assertFalse(any("R_coh" in w for w in r.warnings))

    def test_no_drift_warning_below_threshold(self):
        r = evaluate_run(
            path=["A", "B", "C"],
            steps=2,
            escalation_count=0,
            revisit_count=0,
            success_rate=1.0,
            avg_tension=0.5,
            total_tension=1.0,
            reached_goal=True,
            happy_path_length=2,
            amplitude_drift=0.2,
        )
        self.assertFalse(any("drift" in w.lower() for w in r.warnings))


# ══════════════════════════════════════════════
# H5: should_reflect() quality triggers
# ══════════════════════════════════════════════

class TestH5QualityTriggers(unittest.TestCase):
    """Amplitude drift and low R_coh must trigger quality reflection."""

    def test_amplitude_drift_triggers_quality(self):
        run = _run_eval(amplitude_drift=0.5, rating="B", efficiency=0.7)
        ev = _scenario_eval(run_eval=run)
        dec = should_reflect(ev)
        self.assertTrue(dec.reflect)
        self.assertEqual(dec.reflection_type, "quality")
        self.assertIn("drift", dec.reason.lower())

    def test_low_coherence_triggers_quality(self):
        run = _run_eval(r_coh_avg=0.15, rating="B", efficiency=0.7)
        ev = _scenario_eval(run_eval=run)
        dec = should_reflect(ev)
        self.assertTrue(dec.reflect)
        self.assertEqual(dec.reflection_type, "quality")
        self.assertIn("coherence", dec.reason.lower())

    def test_drift_below_threshold_no_trigger(self):
        run = _run_eval(amplitude_drift=0.2, rating="B", efficiency=0.7)
        ev = _scenario_eval(run_eval=run)
        dec = should_reflect(ev)
        # May still trigger on other quality reasons, but drift should not appear
        if dec.reflect and dec.reflection_type == "quality":
            self.assertNotIn("drift", dec.reason.lower())

    def test_zero_rcoh_no_trigger(self):
        """R_coh=0 means no overlay data — should not trigger coherence."""
        run = _run_eval(r_coh_avg=0.0, rating="B", efficiency=0.7)
        ev = _scenario_eval(run_eval=run)
        dec = should_reflect(ev)
        if dec.reflect and dec.reflection_type == "quality":
            self.assertNotIn("coherence", dec.reason.lower())

    def test_threshold_constants_sane(self):
        self.assertGreater(_AMPLITUDE_DRIFT_THRESHOLD, 0.0)
        self.assertLess(_AMPLITUDE_DRIFT_THRESHOLD, 1.0)
        self.assertGreater(_COHERENCE_QUALITY_FLOOR, 0.0)
        self.assertLess(_COHERENCE_QUALITY_FLOOR, 1.0)


# ══════════════════════════════════════════════
# H6: should_reflect() opportunity triggers
# ══════════════════════════════════════════════

class TestH6OpportunityTriggers(unittest.TestCase):
    """High R_coh and Θ-consistency must trigger opportunity reflection."""

    def test_high_coherence_triggers_opportunity(self):
        run = _run_eval(r_coh_avg=0.9, rating="A", efficiency=0.85)
        ev = _scenario_eval(run_eval=run)
        dec = should_reflect(ev)
        self.assertTrue(dec.reflect)
        self.assertEqual(dec.reflection_type, "opportunity")
        self.assertIn("coherence", dec.reason.lower())

    def test_high_theta_triggers_opportunity(self):
        run = _run_eval(theta_consistency=0.95, r_coh_avg=0.5,
                        rating="A", efficiency=0.85)
        ev = _scenario_eval(run_eval=run)
        dec = should_reflect(ev)
        self.assertTrue(dec.reflect)
        self.assertEqual(dec.reflection_type, "opportunity")
        self.assertIn("phase", dec.reason.lower())

    def test_theta_without_rcoh_no_trigger(self):
        """Θ alone should not trigger if R_coh is zero (no data)."""
        run = _run_eval(theta_consistency=0.99, r_coh_avg=0.0,
                        rating="A", efficiency=0.85)
        ev = _scenario_eval(run_eval=run)
        dec = should_reflect(ev)
        # Should still trigger on other opportunity reasons (A-rated, high eff)
        # but phase alignment specifically should not appear
        if dec.reflect and dec.reflection_type == "opportunity":
            self.assertNotIn("phase alignment", dec.reason)

    def test_moderate_coherence_no_opportunity(self):
        """R_coh below threshold should not add coherence opportunity."""
        run = _run_eval(r_coh_avg=0.5, rating="C", efficiency=0.4)
        ev = _scenario_eval(run_eval=run)
        dec = should_reflect(ev)
        if dec.reflect:
            self.assertNotIn("coherence", dec.reason.lower())

    def test_opportunity_thresholds_sane(self):
        self.assertGreater(_COHERENCE_OPPORTUNITY_FLOOR, _COHERENCE_QUALITY_FLOOR)
        self.assertGreater(_THETA_OPPORTUNITY_FLOOR, 0.5)


# ══════════════════════════════════════════════
# H7: _reflect_failure() detects coherence collapse
# ══════════════════════════════════════════════

class TestH7ReflectFailureAmplitude(unittest.TestCase):
    """Failure reflection must detect R_coh_min collapse."""

    def test_coherence_collapse_in_failure(self):
        run = _run_eval(goal_reached=False, rating="F",
                        r_coh_avg=0.2, r_coh_min=0.05)
        ev = _scenario_eval(run_eval=run, hard_failure="Goal not reached")
        report = _reflect_failure(ev)
        self.assertTrue(any("collapse" in p.lower() or "coherence" in p.lower()
                            for p in report.observed_patterns))
        self.assertTrue(any("r_coh" in e.lower() for e in report.evidence))

    def test_no_collapse_when_min_ok(self):
        run = _run_eval(goal_reached=False, rating="F",
                        r_coh_avg=0.5, r_coh_min=0.3)
        ev = _scenario_eval(run_eval=run, hard_failure="Goal not reached")
        report = _reflect_failure(ev)
        self.assertFalse(any("collapse" in p.lower()
                             for p in report.observed_patterns))

    def test_no_amplitude_patterns_when_no_data(self):
        run = _run_eval(goal_reached=False, rating="F",
                        r_coh_avg=0.0, r_coh_min=0.0)
        ev = _scenario_eval(run_eval=run, hard_failure="Goal not reached")
        report = _reflect_failure(ev)
        self.assertFalse(any("r_coh" in e.lower() for e in report.evidence))


# ══════════════════════════════════════════════
# H8: _reflect_quality() detects drift and low coherence
# ══════════════════════════════════════════════

class TestH8ReflectQualityAmplitude(unittest.TestCase):
    """Quality reflection must surface amplitude drift and low R_coh."""

    def test_drift_produces_pattern_and_action(self):
        run = _run_eval(amplitude_drift=0.5, overlay_agree_rate=0.5,
                        efficiency=0.4, rating="C")
        ev = _scenario_eval(run_eval=run)
        report = _reflect_quality(ev)
        self.assertTrue(any("drift" in p.lower() for p in report.observed_patterns))
        self.assertTrue(any("controller" in l for l in report.likely_layers))
        self.assertTrue(any("amplitude" in a.lower() or "tension" in a.lower()
                            for a in report.recommended_actions))

    def test_low_rcoh_produces_pattern(self):
        run = _run_eval(r_coh_avg=0.15, efficiency=0.4, rating="C")
        ev = _scenario_eval(run_eval=run)
        report = _reflect_quality(ev)
        self.assertTrue(any("coherence" in p.lower() for p in report.observed_patterns))
        self.assertIn("graph_design", report.likely_layers)

    def test_both_drift_and_low_coherence(self):
        run = _run_eval(amplitude_drift=0.6, r_coh_avg=0.15,
                        efficiency=0.3, rating="C")
        ev = _scenario_eval(run_eval=run)
        report = _reflect_quality(ev)
        patterns_text = " ".join(report.observed_patterns).lower()
        self.assertIn("drift", patterns_text)
        self.assertIn("coherence", patterns_text)

    def test_no_amplitude_quality_when_clean(self):
        run = _run_eval(amplitude_drift=0.05, r_coh_avg=0.7,
                        efficiency=0.4, rating="C")
        ev = _scenario_eval(run_eval=run)
        report = _reflect_quality(ev)
        patterns_text = " ".join(report.observed_patterns).lower()
        self.assertNotIn("drift", patterns_text)
        self.assertNotIn("coherence", patterns_text)


# ══════════════════════════════════════════════
# H9: _reflect_opportunity() detects high coherence & phase
# ══════════════════════════════════════════════

class TestH9ReflectOpportunityAmplitude(unittest.TestCase):
    """Opportunity reflection must detect high coherence and Θ."""

    def test_high_coherence_preserved(self):
        run = _run_eval(r_coh_avg=0.9, r_coh_min=0.7, rating="A", efficiency=0.85)
        ev = _scenario_eval(run_eval=run)
        report = _reflect_opportunity(ev)
        self.assertTrue(any("coherence" in p.lower() for p in report.observed_patterns))
        self.assertTrue(any("interference" in pr.lower() or "topology" in pr.lower()
                            for pr in report.preservations))

    def test_theta_alignment_preserved(self):
        run = _run_eval(theta_consistency=0.95, r_coh_avg=0.5,
                        rating="A", efficiency=0.85)
        ev = _scenario_eval(run_eval=run)
        report = _reflect_opportunity(ev)
        self.assertTrue(any("phase" in p.lower() for p in report.observed_patterns))
        self.assertTrue(any("phase" in pr.lower() for pr in report.preservations))

    def test_perfect_agreement_preserved(self):
        run = _run_eval(amplitude_drift=0.0, overlay_count=10,
                        rating="A", efficiency=0.85)
        ev = _scenario_eval(run_eval=run)
        report = _reflect_opportunity(ev)
        self.assertTrue(any("agreement" in p.lower() for p in report.observed_patterns))

    def test_no_amplitude_opportunity_when_low(self):
        run = _run_eval(r_coh_avg=0.3, theta_consistency=0.5,
                        rating="A", efficiency=0.85)
        ev = _scenario_eval(run_eval=run)
        report = _reflect_opportunity(ev)
        self.assertFalse(any("coherence ratio" in p.lower() for p in report.observed_patterns))
        self.assertFalse(any("phase alignment" in p.lower() for p in report.observed_patterns))


# ══════════════════════════════════════════════
# H10: _build_evidence_block() includes amplitude metrics
# ══════════════════════════════════════════════

class TestH10EvidenceBlock(unittest.TestCase):
    """Evidence block for LLM must include amplitude metrics when present."""

    def test_amplitude_section_present(self):
        run = _run_eval(r_coh_avg=0.75, r_coh_min=0.3, r_coh_max=0.95,
                        theta_consistency=0.88, amplitude_drift=0.12)
        ev = _scenario_eval(run_eval=run)
        block = _build_evidence_block(ev)
        self.assertIn("R_coh", block)
        self.assertIn("Θ Consistency", block)
        self.assertIn("Amplitude Drift", block)
        self.assertIn("0.750", block)  # avg rounded
        self.assertIn("0.880", block)  # theta

    def test_no_amplitude_section_when_zero(self):
        run = _run_eval(r_coh_avg=0.0, amplitude_drift=0.0)
        ev = _scenario_eval(run_eval=run)
        block = _build_evidence_block(ev)
        self.assertNotIn("Amplitude Hybrid", block)

    def test_drift_only_shows_section(self):
        run = _run_eval(r_coh_avg=0.0, amplitude_drift=0.15)
        ev = _scenario_eval(run_eval=run)
        block = _build_evidence_block(ev)
        self.assertIn("Amplitude Hybrid", block)
        self.assertIn("Amplitude Drift", block)


# ══════════════════════════════════════════════
# H11: format_evaluation_report() shows amplitude section
# ══════════════════════════════════════════════

class TestH11FormatReport(unittest.TestCase):
    """Console report must display amplitude metrics when present."""

    def test_amplitude_section_in_report(self):
        run = _run_eval(r_coh_avg=0.65, amplitude_drift=0.1)
        ev = _scenario_eval(run_eval=run)
        report = format_evaluation_report([ev])
        self.assertIn("R_coh", report)
        self.assertIn("Θ Consistency", report)
        self.assertIn("Amplitude Drift", report)

    def test_no_amplitude_section_if_zero(self):
        run = _run_eval()
        ev = _scenario_eval(run_eval=run)
        report = format_evaluation_report([ev])
        self.assertNotIn("R_coh", report)
        self.assertNotIn("Θ Consistency", report)


# ══════════════════════════════════════════════
# H12: End-to-end — amplitude triggers reflection pipeline
# ══════════════════════════════════════════════

class TestH12EndToEnd(unittest.TestCase):
    """Full pipeline: amplitude metrics → trigger → rule reflection."""

    def test_drift_triggers_reflect(self):
        """High drift on a goal-reached run triggers quality reflection."""
        run = _run_eval(amplitude_drift=0.5, efficiency=0.7, rating="B")
        ev = _scenario_eval(run_eval=run)
        report = reflect(ev)
        self.assertIsNotNone(report)
        self.assertEqual(report.reflection_type, "quality")
        self.assertTrue(any("drift" in p.lower() for p in report.observed_patterns))

    def test_low_coherence_triggers_reflect(self):
        """Low R_coh on a B-rated run triggers quality reflection."""
        run = _run_eval(r_coh_avg=0.15, efficiency=0.6, rating="B")
        ev = _scenario_eval(run_eval=run)
        report = reflect(ev)
        self.assertIsNotNone(report)
        self.assertEqual(report.reflection_type, "quality")

    def test_high_coherence_triggers_opportunity_reflect(self):
        """High R_coh on an A-rated run triggers opportunity reflection."""
        run = _run_eval(r_coh_avg=0.9, rating="A", efficiency=0.85)
        ev = _scenario_eval(run_eval=run)
        report = reflect(ev)
        self.assertIsNotNone(report)
        self.assertEqual(report.reflection_type, "opportunity")
        self.assertTrue(any("coherence" in p.lower() for p in report.observed_patterns))

    def test_failure_with_collapse(self):
        """Failure + coherence collapse surfaces amplitude patterns."""
        run = _run_eval(goal_reached=False, rating="F",
                        r_coh_avg=0.2, r_coh_min=0.05)
        ev = _scenario_eval(run_eval=run)
        report = reflect(ev)
        self.assertIsNotNone(report)
        self.assertEqual(report.reflection_type, "failure")
        self.assertTrue(any("collapse" in p.lower() or "coherence" in p.lower()
                            for p in report.observed_patterns))

    def test_clean_run_no_amplitude_noise(self):
        """Perfect run with moderate coherence — no amplitude clutter."""
        run = _run_eval(r_coh_avg=0.5, theta_consistency=0.7,
                        amplitude_drift=0.0, overlay_count=5,
                        rating="A", efficiency=0.85)
        ev = _scenario_eval(run_eval=run)
        report = reflect(ev)
        # opportunity reflection, but without amplitude-specific patterns
        if report is not None:
            self.assertFalse(any("drift" in p.lower() for p in report.observed_patterns))

    def test_format_reflection_report_with_amplitude(self):
        """Reflection report formatted with amplitude observations."""
        report = ReflectionReport(
            reflection_type="quality",
            observed_patterns=["Amplitude drift: 45% disagreement",
                               "Low coherence ratio (R_coh_avg=0.20)"],
            likely_layers=["controller", "graph_design"],
            evidence=["amplitude_drift=0.45", "r_coh_min=0.10"],
            recommended_actions=["Review tension weights"],
        )
        text = format_reflection_report([report], domains=["test_domain"])
        self.assertIn("Amplitude drift", text)
        self.assertIn("R_coh", text)
        self.assertIn("controller", text)


if __name__ == "__main__":
    unittest.main()
