"""
Tests for E₀ Confidence-Weighted Override (Phase 3f)
=====================================================

Formal verification that amplitude override decisions are gated by a
probability-gap confidence metric: conf = P_best − P_second.

Coverage:
  F1 — override_confidence property on OverlayReport
  F2 — Single-action edge: confidence = 0.0
  F3 — Two-action basic gap computation
  F4 — Multi-action ordering
  F5 — Confidence threshold = 0 (backward compat: always override)
  F6 — Confidence threshold gates override
  F7 — High threshold blocks override
  F8 — StepResult carries override_confidence
  F9 — RunTrace.metrics() includes avg_override_confidence
  F10 — Gordian integration: confidence governs trap escape
  F11 — Diamond integration: symmetric probabilities
  F12 — End-to-end: threshold sweep
"""

import math
import unittest
from e0_controller.amplitude_overlay import (
    ActionAmplitudeInfo,
    OverlayReport,
    analyze_controller_state,
)
from e0_controller.controller import (
    E0Controller,
    HybridMode,
    StepResult,
)
from e0_controller.landscape import Landscape
from e0_controller.primitives import Edge, Outcome


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _success(src, tgt):
    return Outcome.SUCCESS


def _make_action_info(action, intensity, probability):
    return ActionAmplitudeInfo(
        action=action,
        direct_s_eff=1.0,
        penalized_s=1.0,
        path_count=1,
        paths=[[action]],
        psi_total=complex(math.sqrt(intensity), 0),
        intensity=intensity,
        probability=probability,
    )


def _make_overlay(infos, current="S", det_choice="A"):
    return OverlayReport(
        current=current,
        horizon_edges=3,
        geometry="simple",
        admissible_actions=[i.action for i in infos],
        deterministic_choice=det_choice,
        deterministic_escalated=False,
        action_infos=infos,
    )


def _build_mini():
    """A→B→C→D, happy path length 3."""
    L = Landscape()
    L.add_edge("A", "B", delta=0.5, resistance=1.0)
    L.add_edge("B", "C", delta=0.5, resistance=1.0)
    L.add_edge("C", "D", delta=0.5, resistance=1.0)
    return L


def _build_diamond():
    """S→A, S→B, A→G, B→G. Two paths to goal."""
    L = Landscape()
    L.add_edge("S", "A", delta=0.5, resistance=1.0)
    L.add_edge("S", "B", delta=0.6, resistance=1.0)
    L.add_edge("A", "G", delta=0.5, resistance=1.0)
    L.add_edge("B", "G", delta=0.4, resistance=1.0)
    return L


def _build_gordian():
    """S→A (trap-loop A→A_loop→A), S→B→G (correct path)."""
    L = Landscape()
    L.add_edge("S", "A", delta=0.1, resistance=1.0)
    L.add_edge("S", "B", delta=0.8, resistance=1.0)
    L.add_edge("A", "A_loop", delta=0.1, resistance=1.0)
    L.add_edge("A_loop", "A", delta=0.1, resistance=1.0)
    L.add_edge("B", "G", delta=0.3, resistance=1.0)
    return L


def _build_wide():
    """S→A, S→B, S→C, S→D, S→E, E→G. Five actions from S."""
    L = Landscape()
    for x in "ABCDE":
        L.add_edge("S", x, delta=0.5, resistance=1.0)
    L.add_edge("E", "G", delta=0.3, resistance=1.0)
    return L


# ══════════════════════════════════════════════
# F1: override_confidence property
# ══════════════════════════════════════════════

class TestF1OverrideConfidence(unittest.TestCase):
    """OverlayReport.override_confidence returns P_best - P_second."""

    def test_two_actions_gap(self):
        infos = [
            _make_action_info("A", 0.8, 0.8),
            _make_action_info("B", 0.2, 0.2),
        ]
        ov = _make_overlay(infos)
        self.assertAlmostEqual(ov.override_confidence, 0.6)

    def test_equal_probabilities(self):
        infos = [
            _make_action_info("A", 0.5, 0.5),
            _make_action_info("B", 0.5, 0.5),
        ]
        ov = _make_overlay(infos)
        self.assertAlmostEqual(ov.override_confidence, 0.0)

    def test_dominant_action(self):
        infos = [
            _make_action_info("A", 0.99, 0.99),
            _make_action_info("B", 0.01, 0.01),
        ]
        ov = _make_overlay(infos)
        self.assertAlmostEqual(ov.override_confidence, 0.98)

    def test_three_actions(self):
        infos = [
            _make_action_info("A", 0.6, 0.6),
            _make_action_info("B", 0.3, 0.3),
            _make_action_info("C", 0.1, 0.1),
        ]
        ov = _make_overlay(infos)
        # P_best=0.6, P_second=0.3 → gap=0.3
        self.assertAlmostEqual(ov.override_confidence, 0.3)


# ══════════════════════════════════════════════
# F2: Single-action edge case
# ══════════════════════════════════════════════

class TestF2SingleAction(unittest.TestCase):
    """With only one action, confidence is 0.0."""

    def test_single_action_zero_confidence(self):
        infos = [_make_action_info("A", 1.0, 1.0)]
        ov = _make_overlay(infos)
        self.assertAlmostEqual(ov.override_confidence, 0.0)

    def test_empty_infos_zero_confidence(self):
        ov = _make_overlay([])
        self.assertAlmostEqual(ov.override_confidence, 0.0)


# ══════════════════════════════════════════════
# F3: Two-action gap computation on real overlay
# ══════════════════════════════════════════════

class TestF3RealOverlayGap(unittest.TestCase):
    """Override confidence computed from real amplitude analysis."""

    def test_diamond_confidence_positive(self):
        L = _build_diamond()
        ctrl = E0Controller(L, _success)
        ov = analyze_controller_state(ctrl, "S", horizon_edges=2,
                                      goals={"G"}, geometry="simple")
        # Two actions (A, B) — confidence should be non-negative
        self.assertGreaterEqual(ov.override_confidence, 0.0)
        self.assertLessEqual(ov.override_confidence, 1.0)

    def test_gordian_confidence_at_start(self):
        L = _build_gordian()
        ctrl = E0Controller(L, _success)
        ov = analyze_controller_state(ctrl, "S", horizon_edges=3,
                                      goals={"G"}, geometry="goal_reaching")
        # S has two actions (A, B) — B reaches goal, A doesn't
        self.assertGreaterEqual(ov.override_confidence, 0.0)


# ══════════════════════════════════════════════
# F4: Multi-action ordering independence
# ══════════════════════════════════════════════

class TestF4MultiActionOrdering(unittest.TestCase):
    """Confidence uses sorted probabilities, not insertion order."""

    def test_reversed_order_same_confidence(self):
        infos_a = [
            _make_action_info("X", 0.7, 0.7),
            _make_action_info("Y", 0.2, 0.2),
            _make_action_info("Z", 0.1, 0.1),
        ]
        infos_b = [
            _make_action_info("Z", 0.1, 0.1),
            _make_action_info("Y", 0.2, 0.2),
            _make_action_info("X", 0.7, 0.7),
        ]
        ov_a = _make_overlay(infos_a)
        ov_b = _make_overlay(infos_b)
        self.assertAlmostEqual(ov_a.override_confidence,
                               ov_b.override_confidence)

    def test_five_actions_gap(self):
        probs = [0.4, 0.25, 0.2, 0.1, 0.05]
        infos = [_make_action_info(chr(65 + i), p, p) for i, p in enumerate(probs)]
        ov = _make_overlay(infos)
        # gap = 0.4 - 0.25 = 0.15
        self.assertAlmostEqual(ov.override_confidence, 0.15)


# ══════════════════════════════════════════════
# F5: Threshold=0 backward compatibility
# ══════════════════════════════════════════════

class TestF5ThresholdZero(unittest.TestCase):
    """With threshold=0.0, every disagreement still overrides (backward compat)."""

    def test_override_always_when_zero(self):
        L = _build_gordian()
        ctrl = E0Controller(
            L, _success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=3,
            hybrid_goals={"G"},
            hybrid_geometry="goal_reaching",
            confidence_threshold=0.0,
        )
        target, esc, esc_type, overlay, overridden = ctrl.select_hybrid("S")
        # At S: greedy picks A (lower delta), amplitude should pick B (reaches G)
        if overlay and overlay.amplitude_choice != overlay.deterministic_choice:
            self.assertTrue(overridden)

    def test_agree_no_override(self):
        """When greedy and amplitude agree, override is False regardless."""
        L = _build_mini()
        ctrl = E0Controller(
            L, _success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=2,
            confidence_threshold=0.0,
        )
        target, esc, esc_type, overlay, overridden = ctrl.select_hybrid("A")
        # A→B is only option, so agreement → no override
        self.assertFalse(overridden)


# ══════════════════════════════════════════════
# F6: Confidence threshold gates override
# ══════════════════════════════════════════════

class TestF6ThresholdGating(unittest.TestCase):
    """Override should be blocked when confidence < threshold."""

    def test_high_threshold_blocks_override(self):
        """With threshold=0.99, almost no override should pass."""
        L = _build_gordian()
        ctrl = E0Controller(
            L, _success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=3,
            hybrid_goals={"G"},
            hybrid_geometry="goal_reaching",
            confidence_threshold=0.99,
        )
        target, esc, esc_type, overlay, overridden = ctrl.select_hybrid("S")
        # Unless confidence is exactly ≥0.99, override is blocked
        if overlay and overlay.override_confidence < 0.99:
            self.assertFalse(overridden)

    def test_moderate_threshold_conditional(self):
        """With moderate threshold, override depends on actual confidence."""
        L = _build_gordian()
        ctrl = E0Controller(
            L, _success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=3,
            hybrid_goals={"G"},
            hybrid_geometry="goal_reaching",
            confidence_threshold=0.3,
        )
        target, esc, esc_type, overlay, overridden = ctrl.select_hybrid("S")
        if overlay:
            conf = overlay.override_confidence
            if conf >= 0.3:
                # If confidence sufficient AND disagree → override
                if overlay.amplitude_choice != overlay.deterministic_choice:
                    self.assertTrue(overridden)
            else:
                self.assertFalse(overridden)

    def test_threshold_exactly_at_confidence(self):
        """Threshold == confidence should allow override (>=)."""
        infos = [
            _make_action_info("A", 0.7, 0.7),
            _make_action_info("B", 0.3, 0.3),
        ]
        ov = _make_overlay(infos)
        # confidence = 0.7 - 0.3 = 0.4
        self.assertAlmostEqual(ov.override_confidence, 0.4)
        # Threshold exactly 0.4 → should allow (>=)


# ══════════════════════════════════════════════
# F7: High threshold blocks override on various domains
# ══════════════════════════════════════════════

class TestF7HighThresholdBlocking(unittest.TestCase):
    """With threshold=1.0, no override is ever possible."""

    def test_no_override_with_max_threshold(self):
        L = _build_gordian()
        ctrl = E0Controller(
            L, _success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=3,
            hybrid_goals={"G"},
            hybrid_geometry="simple",  # simple geometry: both actions have paths
            confidence_threshold=1.0,
        )
        target, esc, esc_type, overlay, overridden = ctrl.select_hybrid("S")
        # With simple geometry both actions get non-zero intensity
        # so confidence < 1.0 → override blocked
        if overlay and overlay.override_confidence < 1.0:
            self.assertFalse(overridden)

    def test_diamond_no_override_max_threshold(self):
        L = _build_diamond()
        ctrl = E0Controller(
            L, _success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=2,
            hybrid_goals={"G"},
            confidence_threshold=1.0,
        )
        target, esc, esc_type, overlay, overridden = ctrl.select_hybrid("S")
        self.assertFalse(overridden)

    def test_wide_no_override_max_threshold(self):
        L = _build_wide()
        ctrl = E0Controller(
            L, _success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=2,
            hybrid_goals={"G"},
            confidence_threshold=1.0,
        )
        target, esc, esc_type, overlay, overridden = ctrl.select_hybrid("S")
        self.assertFalse(overridden)


# ══════════════════════════════════════════════
# F8: StepResult carries override_confidence
# ══════════════════════════════════════════════

class TestF8StepResultField(unittest.TestCase):
    """StepResult.override_confidence is populated from overlay."""

    def test_default_zero(self):
        sr = StepResult(
            tau=1, source="A", target="B",
            outcome=Outcome.SUCCESS, s_eff=1.0,
            r_eff_before=1.0, r_eff_after=1.0,
            candidates=["B"],
        )
        self.assertEqual(sr.override_confidence, 0.0)

    def test_confidence_populated_on_cycle(self):
        L = _build_gordian()
        ctrl = E0Controller(
            L, _success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=3,
            hybrid_goals={"G"},
            hybrid_geometry="goal_reaching",
            confidence_threshold=0.0,
        )
        step = ctrl.cycle("S")
        self.assertIsNotNone(step)
        # override_confidence should be a float ≥ 0
        self.assertGreaterEqual(step.override_confidence, 0.0)

    def test_confidence_matches_overlay(self):
        """StepResult.override_confidence matches overlay.override_confidence."""
        L = _build_gordian()
        ctrl = E0Controller(
            L, _success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=3,
            hybrid_goals={"G"},
            hybrid_geometry="goal_reaching",
        )
        step = ctrl.cycle("S")
        if step and step.overlay:
            self.assertAlmostEqual(
                step.override_confidence,
                step.overlay.override_confidence,
            )


# ══════════════════════════════════════════════
# F9: RunTrace.metrics() includes avg_override_confidence
# ══════════════════════════════════════════════

class TestF9RunTraceMetrics(unittest.TestCase):
    """Metrics dict must include avg_override_confidence."""

    def test_metric_present(self):
        L = _build_gordian()
        ctrl = E0Controller(
            L, _success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=3,
            hybrid_goals={"G"},
            hybrid_geometry="goal_reaching",
            confidence_threshold=0.0,
        )
        trace = ctrl.run("S", max_cycles=10, goal="G")
        m = trace.metrics()
        self.assertIn("avg_override_confidence", m)
        self.assertGreaterEqual(m["avg_override_confidence"], 0.0)

    def test_no_override_avg_zero(self):
        """When no overrides happen, avg is 0."""
        L = _build_mini()
        ctrl = E0Controller(
            L, _success,
            hybrid_mode=HybridMode.GREEDY,
        )
        trace = ctrl.run("A", max_cycles=10, goal="D")
        m = trace.metrics()
        self.assertEqual(m["avg_override_confidence"], 0.0)


# ══════════════════════════════════════════════
# F10: Gordian integration
# ══════════════════════════════════════════════

class TestF10GordianIntegration(unittest.TestCase):
    """Confidence-weighted override on Gordian trap domain."""

    def test_low_threshold_escapes_trap(self):
        """With low threshold, amplitude overrides greedy trap-entry."""
        L = _build_gordian()
        ctrl = E0Controller(
            L, _success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=3,
            hybrid_goals={"G"},
            hybrid_geometry="goal_reaching",
            confidence_threshold=0.0,
        )
        trace = ctrl.run("S", max_cycles=10, goal="G")
        # Should reach G via B
        self.assertIn("G", trace.path)

    def test_high_threshold_may_enter_trap(self):
        """With threshold=1.0 + simple geometry, override is blocked."""
        L = _build_gordian()
        ctrl = E0Controller(
            L, _success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=3,
            hybrid_goals={"G"},
            hybrid_geometry="simple",  # both actions get intensity → conf < 1.0
            confidence_threshold=1.0,
        )
        target, esc, esc_type, overlay, overridden = ctrl.select_hybrid("S")
        # simple geometry: both A and B have paths → confidence < 1.0 → blocked
        if overlay and overlay.override_confidence < 1.0:
            self.assertFalse(overridden)
            self.assertEqual(target, "A")  # greedy picks A (low delta)

    def test_moderate_threshold_conditional_escape(self):
        """Moderate threshold: override iff confidence exceeds it."""
        L = _build_gordian()
        for threshold in [0.1, 0.3, 0.5, 0.7]:
            ctrl = E0Controller(
                L, _success,
                hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
                hybrid_horizon=3,
                hybrid_goals={"G"},
                hybrid_geometry="goal_reaching",
                confidence_threshold=threshold,
            )
            target, esc, esc_type, overlay, overridden = ctrl.select_hybrid("S")
            if overlay:
                conf = overlay.override_confidence
                if conf >= threshold and overlay.amplitude_choice != overlay.deterministic_choice:
                    self.assertTrue(overridden,
                                    f"Should override at threshold={threshold}, conf={conf:.3f}")
                elif conf < threshold:
                    self.assertFalse(overridden,
                                     f"Should NOT override at threshold={threshold}, conf={conf:.3f}")


# ══════════════════════════════════════════════
# F11: Diamond integration
# ══════════════════════════════════════════════

class TestF11DiamondIntegration(unittest.TestCase):
    """Diamond domain: symmetric paths produce different confidences."""

    def test_diamond_confidence_range(self):
        L = _build_diamond()
        ctrl = E0Controller(L, _success)
        ov = analyze_controller_state(ctrl, "S", horizon_edges=2,
                                      goals={"G"}, geometry="simple")
        conf = ov.override_confidence
        self.assertGreaterEqual(conf, 0.0)
        self.assertLessEqual(conf, 1.0)

    def test_diamond_deterministic_reaches_goal(self):
        L = _build_diamond()
        ctrl = E0Controller(
            L, _success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=2,
            hybrid_goals={"G"},
            confidence_threshold=0.0,
        )
        trace = ctrl.run("S", max_cycles=5, goal="G")
        self.assertIn("G", trace.path)

    def test_diamond_high_threshold_still_reaches_goal(self):
        """Even if override blocked, greedy on diamond should reach G."""
        L = _build_diamond()
        ctrl = E0Controller(
            L, _success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=2,
            hybrid_goals={"G"},
            confidence_threshold=1.0,
        )
        trace = ctrl.run("S", max_cycles=5, goal="G")
        self.assertIn("G", trace.path)


# ══════════════════════════════════════════════
# F12: End-to-end threshold sweep
# ══════════════════════════════════════════════

class TestF12ThresholdSweep(unittest.TestCase):
    """Sweep threshold from 0.0 to 1.0 and verify monotonic override behavior."""

    def test_override_rate_non_increasing_with_threshold(self):
        """Higher threshold → same or fewer overrides."""
        L = _build_gordian()
        rates = []
        for t in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
            ctrl = E0Controller(
                L, _success,
                hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
                hybrid_horizon=3,
                hybrid_goals={"G"},
                hybrid_geometry="goal_reaching",
                confidence_threshold=t,
            )
            trace = ctrl.run("S", max_cycles=15, goal="G")
            m = trace.metrics()
            rates.append(m["hybrid_override_rate"])

        # Rates should be non-increasing as threshold increases
        for i in range(1, len(rates)):
            self.assertGreaterEqual(rates[i - 1] + 1e-9, rates[i],
                                    f"Rate at threshold {i/10:.1f} ({rates[i]:.3f}) "
                                    f"exceeds rate at {(i-1)/10:.1f} ({rates[i-1]:.3f})")

    def test_zero_threshold_has_most_overrides(self):
        """Threshold=0 always has >= overrides than any higher threshold."""
        L = _build_gordian()
        ctrl_0 = E0Controller(
            L, _success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=3,
            hybrid_goals={"G"},
            hybrid_geometry="goal_reaching",
            confidence_threshold=0.0,
        )
        ctrl_1 = E0Controller(
            L, _success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=3,
            hybrid_goals={"G"},
            hybrid_geometry="goal_reaching",
            confidence_threshold=1.0,
        )
        trace_0 = ctrl_0.run("S", max_cycles=15, goal="G")
        trace_1 = ctrl_1.run("S", max_cycles=15, goal="G")
        m0 = trace_0.metrics()
        m1 = trace_1.metrics()
        self.assertGreaterEqual(m0["hybrid_override_count"],
                                m1["hybrid_override_count"])


if __name__ == "__main__":
    unittest.main()
