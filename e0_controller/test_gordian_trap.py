"""
E₀ Gordian Trap — Interference Routing Tests
=============================================
Proves that amplitude-overlay interference can redirect routing
decisions away from a locally optimal (greedy-preferred) decoy
toward a structurally sound detour.

Domain topology (Gordian Trap v3):

  Decoy A (cheap entry, internal phase cancellation):
    A-short:  START → A1 → A2 → GOAL   (low v → small Θ)
    A-loop:   START → A1 → L1 → L2 → L3 → GOAL  (high v → large Θ)
    ΔΘ(A-loop − A-short) ≈ π  →  destructive interference

  Detour B (expensive entry, coherent):
    START → B1 → B2 → GOAL

Key insight (holonomy formula):
    ΔΘ = ½ · [Σ v(A-loop edges) − Σ v(A-short edges)]
    Back-edges are irrelevant: Φ cancels in the holonomy.
    High v on loop edges (high δ, low R) + low v on short edges → ΔΘ ≈ π.

Test hierarchy:
    1. Holonomy formula verification
    2. Path-level destructive interference (factor < 0.1)
    3. Overlay-level: goal_reaching geometry picks B1 at h ≥ 5
    4. Hybrid controller overrides greedy A1 → B1
    5. Both greedy and hybrid reach GOAL

Run:
    python -m pytest e0_controller/test_gordian_trap.py -v
"""
import math
import unittest

from e0_controller.landscape import Landscape
from e0_controller.connection import theta, omega
from e0_controller.wavepath import psi, intensity, sum_paths
from e0_controller.controller import E0Controller, HybridMode
from e0_controller.primitives import Outcome
from e0_controller.amplitude_overlay import analyze_controller_state


# ── Domain builder ────────────────────────────────────────────

def build_gordian_trap() -> Landscape:
    """
    Gordian Trap v3: holonomy-tuned interference domain.

    Parameters derived from exploration:
      n_loop=3, loop_delta=2.0, loop_R=0.05, short_delta=0.4, short_R=0.3
      ΔΘ_pred ≈ +3.26 (close to π), factor ≈ 0.02
    """
    L = Landscape()

    # Decoy A (cheap greedy entry)
    L.add_edge("START", "A1", delta=0.3, resistance=0.3)         # S≈0.09

    # A-short: low δ → low v → small Θ
    L.add_edge("A1", "A2", delta=0.4, resistance=0.3)            # S≈0.12
    L.add_edge("A2", "GOAL", delta=0.4, resistance=0.3)

    # A-loop: high δ, low R → high v → large Θ
    L.add_edge("A1", "L1", delta=2.0, resistance=0.05)           # S=0.10
    L.add_edge("L1", "L2", delta=2.0, resistance=0.05)
    L.add_edge("L2", "L3", delta=2.0, resistance=0.05)
    L.add_edge("L3", "GOAL", delta=2.0, resistance=0.05)

    # Detour B (expensive start, coherent)
    L.add_edge("START", "B1", delta=0.5, resistance=0.4)         # S≈0.20
    L.add_edge("B1", "B2", delta=0.3, resistance=0.35)
    L.add_edge("B2", "GOAL", delta=0.3, resistance=0.3)

    return L


def always_success(source, target):
    return Outcome.SUCCESS


# ── Paths ─────────────────────────────────────────────────────

A_SHORT = ["START", "A1", "A2", "GOAL"]
A_LOOP  = ["START", "A1", "L1", "L2", "L3", "GOAL"]
B_PATH  = ["START", "B1", "B2", "GOAL"]


# ── Test classes ──────────────────────────────────────────────

class TestHolonomyFormula(unittest.TestCase):
    """Verify the holonomy-based ΔΘ prediction."""

    def setUp(self):
        self.L = build_gordian_trap()

    def test_delta_theta_formula(self):
        """ΔΘ = ½ · [Σ v_loop − Σ v_short] matches actual theta difference."""
        v_loop_edges = [
            self.L.transition_field("A1", "L1"),
            self.L.transition_field("L1", "L2"),
            self.L.transition_field("L2", "L3"),
            self.L.transition_field("L3", "GOAL"),
        ]
        v_short_edges = [
            self.L.transition_field("A1", "A2"),
            self.L.transition_field("A2", "GOAL"),
        ]
        dt_predicted = 0.5 * (sum(v_loop_edges) - sum(v_short_edges))
        dt_actual = theta(self.L, A_LOOP) - theta(self.L, A_SHORT)
        self.assertAlmostEqual(dt_predicted, dt_actual, places=6,
                               msg="Holonomy formula must match actual ΔΘ")

    def test_delta_theta_near_pi(self):
        """ΔΘ should be close to π for near-total cancellation."""
        dt = theta(self.L, A_LOOP) - theta(self.L, A_SHORT)
        # cos(ΔΘ) should be strongly negative
        self.assertLess(math.cos(dt), -0.9,
                        msg=f"cos(ΔΘ)={math.cos(dt):.4f} should be < -0.9")


class TestPathLevelInterference(unittest.TestCase):
    """Verify destructive interference between A-short and A-loop."""

    def setUp(self):
        self.L = build_gordian_trap()

    def test_a_paths_destructive(self):
        """A-family coherent intensity < incoherent intensity (factor < 0.5)."""
        psi_short = psi(self.L, A_SHORT)
        psi_loop = psi(self.L, A_LOOP)
        I_coherent = abs(psi_short + psi_loop) ** 2
        I_incoherent = abs(psi_short) ** 2 + abs(psi_loop) ** 2
        factor = I_coherent / I_incoherent
        self.assertLess(factor, 0.1,
                        msg=f"Interference factor {factor:.4f} should be < 0.1")

    def test_b_beats_a_at_path_level(self):
        """I(B) > I(A) at the path level (only GOAL-reaching paths)."""
        psi_A = psi(self.L, A_SHORT) + psi(self.L, A_LOOP)
        psi_B = psi(self.L, B_PATH)
        self.assertGreater(abs(psi_B) ** 2, abs(psi_A) ** 2)

    def test_b_path_is_coherent(self):
        """B has no internal phase splitting → intensity = |Ψ|²."""
        p = psi(self.L, B_PATH)
        self.assertGreater(abs(p), 0.5,
                           msg="B-path should have significant coherence")


class TestGreedyBehavior(unittest.TestCase):
    """Verify greedy prefers A1 (the decoy)."""

    def setUp(self):
        self.L = build_gordian_trap()

    def test_greedy_picks_a1(self):
        """S_eff(START→A1) < S_eff(START→B1) → greedy prefers A1."""
        s_a = self.L.effective_tension("START", "A1")
        s_b = self.L.effective_tension("START", "B1")
        self.assertLess(s_a, s_b)

    def test_greedy_reaches_goal(self):
        """Greedy run from START reaches GOAL."""
        ctrl = E0Controller(self.L, always_success)
        trace = ctrl.run(start="START", goal="GOAL", max_cycles=20)
        self.assertEqual(trace.path[-1], "GOAL")


class TestOverlayGoalReaching(unittest.TestCase):
    """Test goal_reaching geometry: only GOAL-reaching paths count."""

    def setUp(self):
        self.L = build_gordian_trap()
        self.ctrl = E0Controller(self.L, always_success)

    def test_h3_a1_wins(self):
        """At h=3, only A-short reaches GOAL → A1 wins (no loop visible yet)."""
        report = analyze_controller_state(
            self.ctrl, "START", horizon_edges=3,
            geometry="goal_reaching", goals={"GOAL"},
        )
        self.assertEqual(report.amplitude_choice, "A1")

    def test_h5_b1_wins(self):
        """At h=5, A-loop becomes visible → destructive interference → B1 wins."""
        report = analyze_controller_state(
            self.ctrl, "START", horizon_edges=5,
            geometry="goal_reaching", goals={"GOAL"},
        )
        self.assertEqual(report.amplitude_choice, "B1",
                         msg="Amplitude should pick B1 due to A-family interference")

    def test_h5_a1_intensity_suppressed(self):
        """At h=5, A1's intensity should be < 5% of total."""
        report = analyze_controller_state(
            self.ctrl, "START", horizon_edges=5,
            geometry="goal_reaching", goals={"GOAL"},
        )
        a1_info = next(ai for ai in report.action_infos if ai.action == "A1")
        self.assertLess(a1_info.probability, 0.05,
                        msg=f"P(A1)={a1_info.probability:.3f} should be < 0.05")

    def test_b1_probability_dominant(self):
        """At h=5 with goal_reaching, P(B1) > 0.9."""
        report = analyze_controller_state(
            self.ctrl, "START", horizon_edges=5,
            geometry="goal_reaching", goals={"GOAL"},
        )
        b1_info = next(ai for ai in report.action_infos if ai.action == "B1")
        self.assertGreater(b1_info.probability, 0.9)

    def test_goal_reaching_path_counts(self):
        """At h=5: A1 has 2 GOAL-reaching paths, B1 has 1."""
        report = analyze_controller_state(
            self.ctrl, "START", horizon_edges=5,
            geometry="goal_reaching", goals={"GOAL"},
        )
        a1_info = next(ai for ai in report.action_infos if ai.action == "A1")
        b1_info = next(ai for ai in report.action_infos if ai.action == "B1")
        self.assertEqual(a1_info.path_count, 2)
        self.assertEqual(b1_info.path_count, 1)


class TestHybridOverride(unittest.TestCase):
    """Test that hybrid controller overrides greedy A1 → B1."""

    def setUp(self):
        self.L = build_gordian_trap()

    def test_hybrid_overrides_to_b1(self):
        """Hybrid with goal_reaching geometry at h=5 should override to B1."""
        ctrl = E0Controller(
            self.L, always_success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=5,
            hybrid_goals={"GOAL"},
            hybrid_geometry="goal_reaching",
        )
        trace = ctrl.run(start="START", goal="GOAL", max_cycles=20)
        # First step should be overridden: greedy A1 → amplitude B1
        self.assertTrue(trace.steps[0].hybrid_overridden,
                        msg="First step should be hybrid-overridden")
        self.assertEqual(trace.steps[0].target, "B1",
                         msg="Override should redirect to B1")

    def test_hybrid_reaches_goal(self):
        """Hybrid run reaches GOAL via B-path."""
        ctrl = E0Controller(
            self.L, always_success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=5,
            hybrid_goals={"GOAL"},
            hybrid_geometry="goal_reaching",
        )
        trace = ctrl.run(start="START", goal="GOAL", max_cycles=20)
        self.assertEqual(trace.path[-1], "GOAL")

    def test_hybrid_path_is_b_detour(self):
        """Hybrid path should be START → B1 → B2 → GOAL."""
        ctrl = E0Controller(
            self.L, always_success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=5,
            hybrid_goals={"GOAL"},
            hybrid_geometry="goal_reaching",
        )
        trace = ctrl.run(start="START", goal="GOAL", max_cycles=20)
        self.assertEqual(trace.path, ["START", "B1", "B2", "GOAL"])

    def test_no_override_at_low_horizon(self):
        """At h=3, A-loop not visible → no override (greedy A1 stands)."""
        ctrl = E0Controller(
            self.L, always_success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=3,
            hybrid_goals={"GOAL"},
            hybrid_geometry="goal_reaching",
        )
        trace = ctrl.run(start="START", goal="GOAL", max_cycles=20)
        # At h=3, A1 still wins in goal_reaching → no override at START
        self.assertFalse(trace.steps[0].hybrid_overridden,
                         msg="At h=3 no override expected (A-loop not visible)")


class TestSimpleGeometryNoOverride(unittest.TestCase):
    """With simple geometry, prefix paths dominate → no override."""

    def test_simple_geometry_a1_wins(self):
        """Simple geometry: prefix paths give A1 higher intensity → no override."""
        L = build_gordian_trap()
        report = analyze_controller_state(
            E0Controller(L, always_success), "START",
            horizon_edges=5, geometry="simple",
        )
        self.assertEqual(report.amplitude_choice, "A1",
                         msg="Simple geometry should favor A1 (prefix dominance)")


if __name__ == "__main__":
    unittest.main()
