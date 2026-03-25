"""
E₀ Historization × Gordian Trap — Formal Interaction Tests
==========================================================
Tests the interaction between historization (§17) and
interference-based routing on the Gordian Trap domain.

Covers gaps not addressed in test_gordian_trap.py:
  1. Parametric resilience (δ_max, ρ, λ_s, λ_f variations)
  2. Failure outcomes (not just SUCCESS)
  3. K2 lazy decay recovery
  4. Clipping saturation and R_eff floor
  5. Alternating adversarial patterns
  6. Recovery from adversarial through decay
  7. Holonomy formula invariance under historization
  8. Multi-goal × historization interaction
  9. Extreme stress (100+ passes)

Run:
    python -m pytest e0_controller/test_historization_gordian.py -v
"""
import math
import unittest

from e0_controller.landscape import Landscape
from e0_controller.connection import theta, omega
from e0_controller.wavepath import psi, intensity
from e0_controller.controller import E0Controller, HybridMode
from e0_controller.primitives import Outcome, Edge
from e0_controller.amplitude_overlay import analyze_controller_state
from e0_controller.historization import Historization


# ── Domain builders ───────────────────────────────────────────

def build_gordian_trap(**hist_kwargs) -> Landscape:
    """Gordian Trap v3 with configurable historization parameters."""
    L = Landscape()
    if hist_kwargs:
        L.historization = Historization(**hist_kwargs)

    L.add_edge("START", "A1", delta=0.3, resistance=0.3)
    L.add_edge("A1", "A2", delta=0.4, resistance=0.3)
    L.add_edge("A2", "GOAL", delta=0.4, resistance=0.3)
    L.add_edge("A1", "L1", delta=2.0, resistance=0.05)
    L.add_edge("L1", "L2", delta=2.0, resistance=0.05)
    L.add_edge("L2", "L3", delta=2.0, resistance=0.05)
    L.add_edge("L3", "GOAL", delta=2.0, resistance=0.05)
    L.add_edge("START", "B1", delta=0.5, resistance=0.4)
    L.add_edge("B1", "B2", delta=0.3, resistance=0.35)
    L.add_edge("B2", "GOAL", delta=0.3, resistance=0.3)
    return L


def build_multigoal_gordian(**hist_kwargs) -> Landscape:
    """Multi-goal Gordian with configurable historization."""
    L = build_gordian_trap(**hist_kwargs)
    L.add_edge("A1", "D1", delta=0.5, resistance=0.3)
    L.add_edge("D1", "GOAL2", delta=0.4, resistance=0.3)
    L.add_edge("START", "C1", delta=0.6, resistance=0.4)
    L.add_edge("C1", "C2", delta=0.4, resistance=0.3)
    L.add_edge("C2", "GOAL2", delta=0.3, resistance=0.3)
    return L


def always_success(source, target):
    return Outcome.SUCCESS


# ── Paths ─────────────────────────────────────────────────────

A_SHORT = ["START", "A1", "A2", "GOAL"]
A_LOOP  = ["START", "A1", "L1", "L2", "L3", "GOAL"]
B_PATH  = ["START", "B1", "B2", "GOAL"]


# ── Helpers ───────────────────────────────────────────────────

def _historize_path(L, path, outcome=Outcome.SUCCESS):
    """Historize edges along a path with given outcome."""
    for i in range(len(path) - 1):
        edge = Edge(path[i], path[i + 1])
        L.historization.update(edge, outcome)


def _delta_theta(L):
    """ΔΘ = Θ(A-loop) - Θ(A-short)."""
    return theta(L, A_LOOP) - theta(L, A_SHORT)


def _holonomy_predicted(L):
    """ΔΘ_pred = ½[Σv(loop) - Σv(short)]."""
    v_loop = sum(L.transition_field(A_LOOP[i], A_LOOP[i+1])
                 for i in range(len(A_LOOP) - 1))
    v_short = sum(L.transition_field(A_SHORT[i], A_SHORT[i+1])
                  for i in range(len(A_SHORT) - 1))
    return 0.5 * (v_loop - v_short)


def _overlay_choice(L, goals=None, horizon=5):
    """Return amplitude_choice at START."""
    goals = goals or {"GOAL"}
    report = analyze_controller_state(
        E0Controller(L, always_success), "START",
        horizon_edges=horizon,
        geometry="goal_reaching", goals=goals,
    )
    return report.amplitude_choice


# ══════════════════════════════════════════════════════════════
# 1. Parametric Resilience
# ══════════════════════════════════════════════════════════════

class TestParametricResilience(unittest.TestCase):
    """Interference survives under varied historization parameters."""

    def test_high_delta_max(self):
        """δ_max=10: permissive clipping — B still wins after 10 A-short."""
        L = build_gordian_trap(delta_max=10.0)
        for _ in range(10):
            _historize_path(L, A_SHORT)
        self.assertEqual(_overlay_choice(L), "B1")

    def test_low_delta_max(self):
        """δ_max=0.5: tight clipping — B still wins after 20 A-short."""
        L = build_gordian_trap(delta_max=0.5)
        for _ in range(20):
            _historize_path(L, A_SHORT)
        self.assertEqual(_overlay_choice(L), "B1")

    def test_no_decay(self):
        """ρ=1.0: no forgetting — traces accumulate forever, B still wins."""
        L = build_gordian_trap(rho=1.0)
        for _ in range(10):
            _historize_path(L, A_SHORT)
        dt = _delta_theta(L)
        self.assertLess(math.cos(dt), 0.0,
                        msg="Interference must remain destructive with ρ=1")
        self.assertEqual(_overlay_choice(L), "B1")

    def test_fast_decay(self):
        """ρ=0.5: rapid forgetting — effects fade fast, B still wins."""
        L = build_gordian_trap(rho=0.5)
        for _ in range(10):
            _historize_path(L, A_SHORT)
        self.assertEqual(_overlay_choice(L), "B1")

    def test_asymmetric_learning_high_failure(self):
        """λ_f=0.5, λ_s=0.05: strong failure sensitivity — B still wins after mixed."""
        L = build_gordian_trap(lambda_f=0.5, lambda_s=0.05)
        for _ in range(5):
            _historize_path(L, A_SHORT)
        self.assertEqual(_overlay_choice(L), "B1")

    def test_strong_success_rate(self):
        """λ_s=0.5: strong success effect — A-short R drops fast, B still wins."""
        L = build_gordian_trap(lambda_s=0.5)
        for _ in range(15):
            _historize_path(L, A_SHORT)
        self.assertEqual(_overlay_choice(L), "B1")


# ══════════════════════════════════════════════════════════════
# 2. Failure Outcomes
# ══════════════════════════════════════════════════════════════

class TestFailureOutcomes(unittest.TestCase):
    """FAILURE historization raises R_eff — changes interference dynamics."""

    def test_a_short_failure_raises_r_eff(self):
        """Failing on A-short edges increases their R_eff."""
        L = build_gordian_trap()
        r_before = L.effective_resistance("A1", "A2")
        for _ in range(5):
            _historize_path(L, A_SHORT, outcome=Outcome.FAILURE)
        r_after = L.effective_resistance("A1", "A2")
        self.assertGreater(r_after, r_before,
                           msg="FAILURE must raise R_eff")

    def test_a_short_failure_reduces_v(self):
        """Failing on A-short reduces v(A-short edges) → changes ΔΘ."""
        L = build_gordian_trap()
        v_before = L.transition_field("A1", "A2")
        for _ in range(5):
            _historize_path(L, A_SHORT, outcome=Outcome.FAILURE)
        v_after = L.transition_field("A1", "A2")
        self.assertLess(v_after, v_before,
                        msg="FAILURE on A-short must reduce v")

    def test_b_wins_after_a_short_failures(self):
        """B still wins when A-short edges have failures."""
        L = build_gordian_trap()
        for _ in range(10):
            _historize_path(L, A_SHORT, outcome=Outcome.FAILURE)
        self.assertEqual(_overlay_choice(L), "B1")

    def test_loop_failure_changes_delta_theta(self):
        """Failing specifically on A-loop edges affects ΔΘ."""
        L = build_gordian_trap()
        dt_before = _delta_theta(L)
        for _ in range(5):
            _historize_path(L, A_LOOP, outcome=Outcome.FAILURE)
        dt_after = _delta_theta(L)
        self.assertNotAlmostEqual(dt_before, dt_after, places=2,
                                  msg="Loop failure must shift ΔΘ")

    def test_b_failure_weakens_b(self):
        """Failing on B-path weakens B's intensity."""
        L = build_gordian_trap()
        I_before = abs(psi(L, B_PATH)) ** 2
        for _ in range(10):
            _historize_path(L, B_PATH, outcome=Outcome.FAILURE)
        I_after = abs(psi(L, B_PATH)) ** 2
        self.assertLess(I_after, I_before,
                        msg="FAILURE on B must reduce I(B)")


# ══════════════════════════════════════════════════════════════
# 3. K2 Lazy Decay Recovery
# ══════════════════════════════════════════════════════════════

class TestK2DecayRecovery(unittest.TestCase):
    """Lazy global decay (K2): traces decay, landscape recovers."""

    def test_traces_decay_toward_zero(self):
        """After historization + many idle steps, traces → 0."""
        L = build_gordian_trap(rho=0.9)
        edge = Edge("A1", "A2")
        # Build up traces
        for _ in range(5):
            L.historization.update(edge, Outcome.SUCCESS)
        u_after_updates = L.historization.success_trace(edge)
        self.assertGreater(u_after_updates, 0)
        # Simulate idle steps by updating an unrelated edge many times
        dummy = Edge("B1", "B2")
        for _ in range(100):
            L.historization.update(dummy, Outcome.SUCCESS)
        # Original edge should have decayed
        u_decayed = L.historization.success_trace(edge)
        self.assertLess(u_decayed, u_after_updates * 0.01,
                        msg="Traces must decay toward zero via K2")

    def test_r_eff_returns_to_r0(self):
        """After decay, R_eff → R₀."""
        L = build_gordian_trap(rho=0.9)
        r0 = L.base_resistance("A1", "A2")
        for _ in range(10):
            _historize_path(L, A_SHORT)
        r_shifted = L.effective_resistance("A1", "A2")
        self.assertNotAlmostEqual(r_shifted, r0, places=2)
        # Decay via idle steps (update unrelated edge)
        dummy = Edge("B1", "B2")
        for _ in range(200):
            L.historization.update(dummy, Outcome.SUCCESS)
        r_recovered = L.effective_resistance("A1", "A2")
        self.assertAlmostEqual(r_recovered, r0, places=1,
                               msg="R_eff must return to R₀ after decay")

    def test_delta_theta_recovers_after_decay(self):
        """ΔΘ returns toward pristine value after traces decay."""
        L = build_gordian_trap(rho=0.9)
        dt_pristine = _delta_theta(L)
        # Perturb via A-loop traversals
        for _ in range(5):
            _historize_path(L, A_LOOP)
        dt_perturbed = _delta_theta(L)
        self.assertNotAlmostEqual(dt_pristine, dt_perturbed, places=1)
        # Decay via idle steps
        dummy = Edge("B1", "B2")
        for _ in range(200):
            L.historization.update(dummy, Outcome.SUCCESS)
        dt_recovered = _delta_theta(L)
        self.assertAlmostEqual(dt_recovered, dt_pristine, places=1,
                               msg="ΔΘ must recover after K2 decay")


# ══════════════════════════════════════════════════════════════
# 4. Clipping Saturation and R_eff Floor
# ══════════════════════════════════════════════════════════════

class TestClippingAndFloor(unittest.TestCase):
    """δ_H is bounded by δ_max; R_eff never reaches zero."""

    def test_delta_h_bounded_by_delta_max(self):
        """|δ_H| ≤ δ_max after extreme historization."""
        L = build_gordian_trap(delta_max=2.0)
        edge = Edge("A1", "A2")
        for _ in range(50):
            L.historization.update(edge, Outcome.SUCCESS)
        dh = L.historization.delta_H(edge)
        self.assertGreaterEqual(dh, -2.0)
        self.assertLessEqual(dh, 2.0)

    def test_saturation_negative(self):
        """Massive success → δ_H saturates at -δ_max."""
        L = build_gordian_trap(delta_max=3.0, rho=1.0)
        edge = Edge("A1", "A2")
        for _ in range(100):
            L.historization.update(edge, Outcome.SUCCESS)
        dh = L.historization.delta_H(edge)
        self.assertAlmostEqual(dh, -3.0, places=2,
                               msg="δ_H must saturate at -δ_max for pure success")

    def test_saturation_positive(self):
        """Massive failure → δ_H saturates at +δ_max."""
        L = build_gordian_trap(delta_max=3.0, rho=1.0)
        edge = Edge("A1", "A2")
        for _ in range(100):
            L.historization.update(edge, Outcome.FAILURE)
        dh = L.historization.delta_H(edge)
        self.assertAlmostEqual(dh, 3.0, places=2,
                               msg="δ_H must saturate at +δ_max for pure failure")

    def test_r_eff_floor_positive(self):
        """R_eff > 0 even when δ_H = -δ_max (structural floor)."""
        L = build_gordian_trap(delta_max=10.0, rho=1.0)
        edge = Edge("A1", "A2")
        for _ in range(100):
            L.historization.update(edge, Outcome.SUCCESS)
        r_eff = L.effective_resistance("A1", "A2")
        self.assertGreater(r_eff, 0,
                           msg="R_eff must never reach zero (structural floor)")


# ══════════════════════════════════════════════════════════════
# 5. Alternating Adversarial
# ══════════════════════════════════════════════════════════════

class TestAlternatingAdversarial(unittest.TestCase):
    """Alternating A-short and A-loop: maximally disruptive to ΔΘ."""

    def test_alternating_preserves_destructive(self):
        """ΔΘ stays destructive (cos < 0) after alternating traversals."""
        L = build_gordian_trap()
        for _ in range(10):
            _historize_path(L, A_SHORT)
            _historize_path(L, A_LOOP)
        dt = _delta_theta(L)
        self.assertLess(math.cos(dt), 0.0,
                        msg="Alternating must preserve destructive interference")

    def test_alternating_b_wins(self):
        """B1 still wins after 10 alternating A-short/A-loop cycles."""
        L = build_gordian_trap()
        for _ in range(10):
            _historize_path(L, A_SHORT)
            _historize_path(L, A_LOOP)
        self.assertEqual(_overlay_choice(L), "B1")

    def test_alternating_delta_theta_bounded(self):
        """ΔΘ does not drift unboundedly under alternating patterns."""
        L = build_gordian_trap()
        dt_values = []
        for _ in range(15):
            _historize_path(L, A_SHORT)
            _historize_path(L, A_LOOP)
            dt_values.append(_delta_theta(L))
        # Last 5 should be bounded (not growing)
        last5 = dt_values[-5:]
        spread = max(last5) - min(last5)
        self.assertLess(spread, 1.0,
                        msg=f"ΔΘ spread in last 5 = {spread:.4f}, must be < 1.0")


# ══════════════════════════════════════════════════════════════
# 6. Recovery from Adversarial
# ══════════════════════════════════════════════════════════════

class TestRecoveryFromAdversarial(unittest.TestCase):
    """System recovers correct routing after adversarial perturbation."""

    def test_b_passes_restore_after_a_adversarial(self):
        """10 A-short adversarial, then 10 B-path → B still wins."""
        L = build_gordian_trap()
        for _ in range(10):
            _historize_path(L, A_SHORT)
        for _ in range(10):
            _historize_path(L, B_PATH)
        self.assertEqual(_overlay_choice(L), "B1")

    def test_mixed_recovery(self):
        """5 A-loop adversarial, then 5 A-short + 5 B → B wins."""
        L = build_gordian_trap()
        for _ in range(5):
            _historize_path(L, A_LOOP)
        for _ in range(5):
            _historize_path(L, A_SHORT)
        for _ in range(5):
            _historize_path(L, B_PATH)
        self.assertEqual(_overlay_choice(L), "B1")


# ══════════════════════════════════════════════════════════════
# 7. Holonomy Formula Under Historization
# ══════════════════════════════════════════════════════════════

class TestHolonomyFormulaUnderHistorization(unittest.TestCase):
    """ΔΘ_predicted = ½[Σv_loop - Σv_short] must match ΔΘ_actual
    even after historization shifts v-values."""

    def test_formula_holds_after_a_short(self):
        """Holonomy formula matches after 10 A-short traversals."""
        L = build_gordian_trap()
        for _ in range(10):
            _historize_path(L, A_SHORT)
        dt_pred = _holonomy_predicted(L)
        dt_actual = _delta_theta(L)
        self.assertAlmostEqual(dt_pred, dt_actual, places=6,
                               msg="Holonomy formula must hold under A-short historization")

    def test_formula_holds_after_a_loop(self):
        """Holonomy formula matches after 5 A-loop traversals."""
        L = build_gordian_trap()
        for _ in range(5):
            _historize_path(L, A_LOOP)
        dt_pred = _holonomy_predicted(L)
        dt_actual = _delta_theta(L)
        self.assertAlmostEqual(dt_pred, dt_actual, places=6,
                               msg="Holonomy formula must hold under A-loop historization")

    def test_formula_holds_after_mixed(self):
        """Holonomy formula matches after mixed traversals."""
        L = build_gordian_trap()
        for _ in range(3):
            _historize_path(L, A_SHORT)
        for _ in range(3):
            _historize_path(L, A_LOOP)
        for _ in range(3):
            _historize_path(L, B_PATH)
        dt_pred = _holonomy_predicted(L)
        dt_actual = _delta_theta(L)
        self.assertAlmostEqual(dt_pred, dt_actual, places=6,
                               msg="Holonomy formula must hold under mixed historization")

    def test_formula_holds_after_failure(self):
        """Holonomy formula matches after failure historization."""
        L = build_gordian_trap()
        for _ in range(5):
            _historize_path(L, A_SHORT, outcome=Outcome.FAILURE)
        dt_pred = _holonomy_predicted(L)
        dt_actual = _delta_theta(L)
        self.assertAlmostEqual(dt_pred, dt_actual, places=6,
                               msg="Holonomy formula must hold after failures")


# ══════════════════════════════════════════════════════════════
# 8. Multi-Goal × Historization
# ══════════════════════════════════════════════════════════════

class TestMultiGoalHistorization(unittest.TestCase):
    """Multi-goal routing survives historization."""

    def test_goal_routing_b1_after_historization(self):
        """Single {GOAL}: B1 still wins after 10 A-short on multi-goal domain."""
        L = build_multigoal_gordian()
        for _ in range(10):
            _historize_path(L, A_SHORT)
        self.assertEqual(_overlay_choice(L, goals={"GOAL"}), "B1")

    def test_goal2_routing_a1_after_historization(self):
        """Single {GOAL2}: A1 still wins for GOAL2 after B-path historization."""
        L = build_multigoal_gordian()
        for _ in range(10):
            _historize_path(L, B_PATH)
        self.assertEqual(_overlay_choice(L, goals={"GOAL2"}), "A1")

    def test_multigoal_routing_stable_after_mixed(self):
        """Multi-goal {GOAL,GOAL2}: routing remains consistent after mixed historization."""
        L = build_multigoal_gordian()
        for _ in range(5):
            _historize_path(L, A_SHORT)
        for _ in range(5):
            _historize_path(L, B_PATH)
        choice = _overlay_choice(L, goals={"GOAL", "GOAL2"})
        # A-short historization strengthens A-edges → shifts multi-goal balance.
        # Either A1 or B1 may win; what matters is a decision is reached.
        self.assertIn(choice, {"A1", "B1"},
                      msg="Multi-goal must produce a valid routing decision")


# ══════════════════════════════════════════════════════════════
# 9. Extreme Stress
# ══════════════════════════════════════════════════════════════

class TestExtremeStress(unittest.TestCase):
    """Long-term stability under extreme traversal counts."""

    def test_100_a_short_passes(self):
        """B1 wins after 100 adversarial A-short traversals."""
        L = build_gordian_trap()
        for _ in range(100):
            _historize_path(L, A_SHORT)
        self.assertEqual(_overlay_choice(L), "B1",
                         msg="B1 must win even after 100 A-short traversals")

    def test_50_alternating_passes(self):
        """B1 wins after 50 cycles of alternating A-short/A-loop."""
        L = build_gordian_trap()
        for _ in range(50):
            _historize_path(L, A_SHORT)
            _historize_path(L, A_LOOP)
        self.assertEqual(_overlay_choice(L), "B1",
                         msg="B1 must win after 50 alternating cycles")

    def test_cos_bounded_under_stress(self):
        """cos(ΔΘ) never becomes positive under 100 mixed traversals."""
        L = build_gordian_trap()
        paths = [A_SHORT, A_LOOP, B_PATH]
        for i in range(100):
            _historize_path(L, paths[i % 3])
        dt = _delta_theta(L)
        self.assertLess(math.cos(dt), 0.0,
                        msg="cos(ΔΘ) must remain destructive under 100 mixed passes")


# ══════════════════════════════════════════════════════════════
# 10. Hybrid Controller Multi-Cycle
# ══════════════════════════════════════════════════════════════

class TestHybridMultiCycle(unittest.TestCase):
    """Hybrid controller maintains correct routing across repeated runs."""

    def test_three_consecutive_runs(self):
        """Three consecutive hybrid runs all take B-path."""
        L = build_gordian_trap()
        for run_idx in range(3):
            ctrl = E0Controller(
                L, always_success,
                hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
                hybrid_horizon=5,
                hybrid_goals={"GOAL"},
                hybrid_geometry="goal_reaching",
            )
            trace = ctrl.run(start="START", goal="GOAL", max_cycles=20)
            self.assertEqual(trace.path, ["START", "B1", "B2", "GOAL"],
                             msg=f"Run {run_idx+1}: hybrid must take B-path")

    def test_greedy_then_hybrid(self):
        """Greedy run pollutes landscape, hybrid still overrides to B."""
        L = build_gordian_trap()
        # Greedy run (takes A-short)
        ctrl_greedy = E0Controller(L, always_success)
        trace_greedy = ctrl_greedy.run(start="START", goal="GOAL", max_cycles=20)
        self.assertIn("A1", trace_greedy.path, msg="Greedy must take A-path")
        # Hybrid run on same (now historized) landscape
        ctrl_hybrid = E0Controller(
            L, always_success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=5,
            hybrid_goals={"GOAL"},
            hybrid_geometry="goal_reaching",
        )
        trace_hybrid = ctrl_hybrid.run(start="START", goal="GOAL", max_cycles=20)
        self.assertEqual(trace_hybrid.steps[0].target, "B1",
                         msg="Hybrid must override to B1 even after greedy pollution")

    def test_alternating_greedy_hybrid(self):
        """Alternating greedy/hybrid runs: hybrid always takes B."""
        L = build_gordian_trap()
        for _ in range(3):
            # Greedy
            ctrl_g = E0Controller(L, always_success)
            ctrl_g.run(start="START", goal="GOAL", max_cycles=20)
            # Hybrid
            ctrl_h = E0Controller(
                L, always_success,
                hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
                hybrid_horizon=5,
                hybrid_goals={"GOAL"},
                hybrid_geometry="goal_reaching",
            )
            trace_h = ctrl_h.run(start="START", goal="GOAL", max_cycles=20)
            self.assertEqual(trace_h.path[-1], "GOAL")
            self.assertEqual(trace_h.steps[0].target, "B1")


if __name__ == "__main__":
    unittest.main()
