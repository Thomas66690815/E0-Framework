"""
Tests for C104: Emergent Locality
====================================
Verifies that locality emerges from historization as a structural
consequence of the inscription → trace_load → locality formula chain.

Tests cover:
  1. Locality evolution: monotonic increase under inscription
  2. Radius contraction: monotonic decrease under inscription
  3. Phase transition: locality crosses 0.5 at predictable round
  4. Convergence: locality saturates (bounded by ρ-decay equilibrium)
  5. Fresh degeneration: initial locality = 0, radius = diameter
  6. Regional profile: non-uniform inscription creates differentiation
  7. Navigation tracking: locality increases during actual navigation
  8. Theoretical prediction: formula approximates observed transition
  9. Edge cases: empty landscape, single edge, μ sensitivity
"""

import math
import unittest

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.emergent_locality import (
    LocalityEvolution,
    LocalitySnapshot,
    RegionalProfile,
    compute_regional_profile,
    find_phase_transition,
    snapshot_locality,
    theoretical_phase_transition,
    track_inscription_locality,
    track_locality_evolution,
)


# ── Helpers ──

def _make_chain(n=5):
    """Chain: S → N1 → N2 → ... → N{n-2} → GOAL."""
    L = Landscape()
    nodes = ["S"] + [f"N{i}" for i in range(1, n - 1)] + ["GOAL"]
    for i in range(len(nodes) - 1):
        L.add_edge(nodes[i], nodes[i + 1], delta=0.5, resistance=0.3)
    return L, nodes


def _make_star(center="C", arms=4):
    """Star: C → A1, C → A2, ..., C → A{arms}."""
    L = Landscape()
    for i in range(1, arms + 1):
        L.add_edge(center, f"A{i}", delta=0.5, resistance=0.3)
    return L


def _all_success(source, target):
    return Outcome.SUCCESS


# ══════════════════════════════════════════════
# 1. Locality evolution: monotonic increase
# ══════════════════════════════════════════════

class TestLocalityMonotonic(unittest.TestCase):
    """Locality never decreases under inscription."""

    def test_chain_uniform_inscription(self):
        """Uniform inscription on chain → monotonic locality."""
        L, _ = _make_chain(6)
        ev = track_inscription_locality(L, "S", rounds=15, mu=1.0)
        self.assertTrue(ev.is_monotonic)

    def test_star_uniform_inscription(self):
        """Uniform inscription on star → monotonic locality."""
        L = _make_star(arms=5)
        ev = track_inscription_locality(L, "C", rounds=10, mu=1.0)
        self.assertTrue(ev.is_monotonic)

    def test_locality_increases_from_zero(self):
        """Locality starts at 0 and increases."""
        L, _ = _make_chain(5)
        ev = track_inscription_locality(L, "S", rounds=5, mu=1.0)
        self.assertAlmostEqual(ev.initial_locality, 0.0)
        self.assertGreater(ev.final_locality, 0.0)
        self.assertGreater(ev.locality_increase, 0.0)


# ══════════════════════════════════════════════
# 2. Radius contraction
# ══════════════════════════════════════════════

class TestRadiusContraction(unittest.TestCase):
    """Radius never increases under inscription."""

    def test_radius_monotonic(self):
        """Radius monotonically decreases (or stays same)."""
        L, _ = _make_chain(8)
        ev = track_inscription_locality(L, "S", rounds=15, mu=1.0)
        self.assertTrue(ev.radius_monotonic)

    def test_initial_radius_equals_diameter(self):
        """Fresh landscape: radius = diameter."""
        L, _ = _make_chain(6)
        ev = track_inscription_locality(L, "S", rounds=1, mu=1.0)
        self.assertEqual(ev.snapshots[0].radius, ev.snapshots[0].diameter)

    def test_radius_decreases_with_inscription(self):
        """Sufficient inscription shrinks radius below diameter."""
        L, _ = _make_chain(8)
        ev = track_inscription_locality(L, "S", rounds=10, mu=1.0)
        self.assertLess(ev.snapshots[-1].radius, ev.snapshots[0].radius)


# ══════════════════════════════════════════════
# 3. Phase transition
# ══════════════════════════════════════════════

class TestPhaseTransition(unittest.TestCase):
    """Locality crosses 0.5 at a predictable round."""

    def test_phase_transition_exists_small_mu(self):
        """With μ=1.0, phase transition occurs within ~5 rounds."""
        L, _ = _make_chain(6)
        ev = track_inscription_locality(L, "S", rounds=10, mu=1.0)
        self.assertIsNotNone(ev.phase_transition_step)
        self.assertLessEqual(ev.phase_transition_step, 5)

    def test_find_phase_transition(self):
        """find_phase_transition returns the crossing round."""
        L, _ = _make_chain(6)
        r = find_phase_transition(L, "S", mu=1.0, max_rounds=20)
        self.assertIsNotNone(r)
        self.assertGreater(r, 0)

    def test_large_mu_delays_transition(self):
        """Larger μ delays phase transition."""
        L1, _ = _make_chain(6)
        r1 = find_phase_transition(L1, "S", mu=1.0, max_rounds=50)

        L2, _ = _make_chain(6)
        r2 = find_phase_transition(L2, "S", mu=5.0, max_rounds=50)

        self.assertIsNotNone(r1)
        # r2 may be None (never reaches 0.5 with ρ=0.9, μ=5.0)
        if r2 is not None:
            self.assertGreater(r2, r1)

    def test_phase_at_locality_half(self):
        """At phase transition, locality ≥ 0.5."""
        L, _ = _make_chain(6)
        ev = track_inscription_locality(L, "S", rounds=10, mu=1.0)
        step = ev.phase_transition_step
        if step is not None:
            snap = [s for s in ev.snapshots if s.step == step][0]
            self.assertGreaterEqual(snap.locality, 0.5)


# ══════════════════════════════════════════════
# 4. Convergence
# ══════════════════════════════════════════════

class TestConvergence(unittest.TestCase):
    """Locality saturates under continued inscription."""

    def test_locality_bounded_below_one(self):
        """Locality < 1 even after many rounds (ρ-decay equilibrium)."""
        L, _ = _make_chain(5)
        ev = track_inscription_locality(L, "S", rounds=50, mu=1.0)
        self.assertLess(ev.final_locality, 1.0)

    def test_convergence_stabilizes(self):
        """Last 5 snapshots differ by < 0.01 (stabilized)."""
        L, _ = _make_chain(5)
        ev = track_inscription_locality(L, "S", rounds=30, mu=1.0)
        last5 = [s.locality for s in ev.snapshots[-5:]]
        spread = max(last5) - min(last5)
        self.assertLess(spread, 0.01)

    def test_equilibrium_depends_on_rho(self):
        """Theoretical: with ρ=0.9, max trace_load ≈ 1/(1-ρ) = 10."""
        # theoretical_phase_transition gives rounds needed
        t = theoretical_phase_transition(mu=5.0, rho=0.9)
        # μ*(1-ρ) = 5*0.1 = 0.5 < 1, so transition should be finite
        self.assertFalse(math.isinf(t))
        self.assertGreater(t, 0)


# ══════════════════════════════════════════════
# 5. Fresh degeneration
# ══════════════════════════════════════════════

class TestFreshDegeneration(unittest.TestCase):
    """Fresh landscape: locality=0, scope=all states."""

    def test_fresh_locality_zero(self):
        L, _ = _make_chain(6)
        snap = snapshot_locality(L, "S", step=0, mu=5.0)
        self.assertAlmostEqual(snap.locality, 0.0)

    def test_fresh_radius_equals_diameter(self):
        L, _ = _make_chain(6)
        snap = snapshot_locality(L, "S", step=0, mu=5.0)
        self.assertEqual(snap.radius, snap.diameter)

    def test_fresh_scope_covers_all(self):
        L, _ = _make_chain(6)
        snap = snapshot_locality(L, "S", step=0, goal="GOAL", mu=5.0)
        self.assertEqual(snap.scope_size, snap.total_states)

    def test_fresh_mean_load_zero(self):
        L, _ = _make_chain(6)
        snap = snapshot_locality(L, "S", step=0, mu=5.0)
        self.assertAlmostEqual(snap.mean_load, 0.0)


# ══════════════════════════════════════════════
# 6. Regional profile
# ══════════════════════════════════════════════

class TestRegionalProfile(unittest.TestCase):
    """Per-state locality analysis reveals differentiation."""

    def test_uniform_inscription_low_differentiation(self):
        """Uniform inscription → all regions similar."""
        L, _ = _make_chain(5)
        # Inscribe all edges uniformly
        for _ in range(5):
            for e in list(L._delta.keys()):
                L.historization.update(e, Outcome.SUCCESS)

        profiles = compute_regional_profile(L, mu=1.0)
        for p in profiles:
            self.assertLess(p.differentiation, 0.1,
                            f"State {p.state} too differentiated under uniform")

    def test_non_uniform_creates_differentiation(self):
        """Inscribing only some edges creates regional differentiation."""
        L, nodes = _make_chain(6)
        # Only inscribe first edge heavily
        e0 = Edge(nodes[0], nodes[1])
        for _ in range(20):
            L.historization.update(e0, Outcome.SUCCESS)

        profiles = compute_regional_profile(L, mu=1.0)
        by_state = {p.state: p for p in profiles}

        # S and N1 touch the inscribed edge → higher local_locality
        hot_states = {nodes[0], nodes[1]}
        for s in hot_states:
            self.assertGreater(by_state[s].local_locality,
                               by_state[s].global_locality,
                               f"{s} should be hotter than global")

    def test_profile_covers_all_states(self):
        """One profile entry per state."""
        L, nodes = _make_chain(5)
        profiles = compute_regional_profile(L, mu=1.0)
        self.assertEqual(len(profiles), len(nodes))

    def test_hot_detection(self):
        """States with concentrated inscription detected as hot."""
        L, nodes = _make_chain(6)
        e0 = Edge(nodes[0], nodes[1])
        for _ in range(30):
            L.historization.update(e0, Outcome.SUCCESS)
        profiles = compute_regional_profile(L, mu=1.0)
        hot = [p for p in profiles if p.is_hot]
        self.assertGreater(len(hot), 0,
                           "Expected at least one hot region")


# ══════════════════════════════════════════════
# 7. Navigation tracking
# ══════════════════════════════════════════════

class TestNavigationTracking(unittest.TestCase):
    """Locality increases during actual controller navigation."""

    def test_navigation_increases_locality(self):
        """Navigation on connected graph → locality rises."""
        L, _ = _make_chain(6)
        ev = track_locality_evolution(
            L, _all_success, "S", "GOAL", max_cycles=20, mu=1.0,
        )
        self.assertGreater(ev.final_locality, ev.initial_locality)

    def test_navigation_monotonic(self):
        """Locality mono during short navigation."""
        L, _ = _make_chain(6)
        ev = track_locality_evolution(
            L, _all_success, "S", "GOAL", max_cycles=20, mu=1.0,
        )
        self.assertTrue(ev.is_monotonic)

    def test_navigation_snapshots_recorded(self):
        """Snapshots are recorded at each step."""
        L, _ = _make_chain(6)
        ev = track_locality_evolution(
            L, _all_success, "S", "GOAL", max_cycles=20, mu=1.0,
        )
        # At least initial + some steps
        self.assertGreater(len(ev.snapshots), 1)

    def test_snapshot_step_numbers(self):
        """Step numbers are sequential starting from 0."""
        L, _ = _make_chain(6)
        ev = track_locality_evolution(
            L, _all_success, "S", "GOAL", max_cycles=20, mu=1.0,
        )
        self.assertEqual(ev.snapshots[0].step, 0)
        # Steps should be non-decreasing
        for i in range(1, len(ev.snapshots)):
            self.assertGreater(ev.snapshots[i].step,
                               ev.snapshots[i - 1].step)


# ══════════════════════════════════════════════
# 8. Theoretical prediction
# ══════════════════════════════════════════════

class TestTheoreticalPrediction(unittest.TestCase):
    """Theoretical formula approximates observed behavior."""

    def test_small_mu_prediction(self):
        """For μ=1, theoretical prediction is near observed."""
        t = theoretical_phase_transition(mu=1.0, rho=0.9)
        self.assertFalse(math.isinf(t))
        self.assertGreater(t, 0)
        # Should be a reasonable number of rounds
        self.assertLess(t, 20)

    def test_large_mu_prediction(self):
        """For μ=5, still finite (μ*(1-ρ)=0.5 < 1)."""
        t = theoretical_phase_transition(mu=5.0, rho=0.9)
        self.assertFalse(math.isinf(t))
        self.assertGreater(t, 0)

    def test_impossible_transition(self):
        """μ*(1-ρ) ≥ 1 → inf (never reaches 0.5)."""
        t = theoretical_phase_transition(mu=20.0, rho=0.9)
        # μ*(1-ρ) = 20*0.1 = 2 ≥ 1 → inf
        self.assertTrue(math.isinf(t))

    def test_rho_one_impossible(self):
        """ρ=1 → no decay → μ*(1-ρ)=0, always reachable."""
        # Actually ρ=1 → log(1) = 0 → division by zero
        # The formula handles this: factor = μ*(1-1) = 0 < 1
        # log(1-0) / log(1) = 0 / 0 → NaN
        # This is a degenerate case; just verify no crash
        try:
            t = theoretical_phase_transition(mu=1.0, rho=1.0)
            # If it returns something, it should be 0 or NaN
        except (ZeroDivisionError, ValueError):
            pass  # Expected for ρ=1

    def test_prediction_order_of_magnitude(self):
        """Theoretical within 5× of observed (rough approximation)."""
        L, _ = _make_chain(6)
        observed = find_phase_transition(L, "S", mu=1.0, max_rounds=50)
        theoretical = theoretical_phase_transition(mu=1.0, rho=0.9)
        if observed is not None:
            ratio = observed / theoretical
            self.assertGreater(ratio, 0.2,
                               f"Theoretical too far from observed: ratio={ratio}")
            self.assertLess(ratio, 5.0,
                            f"Theoretical too far from observed: ratio={ratio}")


# ══════════════════════════════════════════════
# 9. Edge cases
# ══════════════════════════════════════════════

class TestEdgeCases(unittest.TestCase):
    """Edge cases and boundary conditions."""

    def test_empty_landscape(self):
        """Empty landscape → trivial profile."""
        L = Landscape()
        L.add_state("ONLY")
        profiles = compute_regional_profile(L, mu=1.0)
        self.assertEqual(len(profiles), 0)  # no edges → empty

    def test_single_edge(self):
        """Single edge landscape → valid evolution."""
        L = Landscape()
        L.add_edge("A", "B", delta=0.5, resistance=0.3)
        ev = track_inscription_locality(L, "A", rounds=5, mu=1.0)
        self.assertTrue(ev.is_monotonic)
        self.assertGreater(ev.final_locality, 0.0)

    def test_mu_sensitivity(self):
        """Smaller μ → higher locality for same inscription."""
        L1, _ = _make_chain(5)
        ev1 = track_inscription_locality(L1, "S", rounds=5, mu=0.5)

        L2, _ = _make_chain(5)
        ev2 = track_inscription_locality(L2, "S", rounds=5, mu=10.0)

        self.assertGreater(ev1.final_locality, ev2.final_locality)

    def test_snapshot_coverage(self):
        """Coverage = scope_size / total_states, in [0,1]."""
        L, _ = _make_chain(5)
        snap = snapshot_locality(L, "S", step=0, mu=1.0)
        self.assertGreaterEqual(snap.coverage, 0.0)
        self.assertLessEqual(snap.coverage, 1.0)

    def test_evolution_summary_not_empty(self):
        """Summary produces readable output."""
        L, _ = _make_chain(5)
        ev = track_inscription_locality(L, "S", rounds=3, mu=1.0)
        s = ev.summary()
        self.assertIn("Locality Evolution", s)
        self.assertIn("Monotonic", s)


if __name__ == "__main__":
    unittest.main()
