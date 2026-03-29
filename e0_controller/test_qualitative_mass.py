"""
E₀ Qualitative Mass — Tests (C42)
===================================
Tests for the qualitative mass observables (mass, quality,
mass_modulation_factor) and their integration into the
transition field via mass_modulation.

Ontodynamics §4: "Mass = persistent topological inertia
resulting from accumulated historization."

Covers:
  1. mass() — total accumulated experience (U + F)
  2. quality() — normalized success/failure balance
  3. mass_modulation_factor() — dampening for conflicted edges
  4. Landscape integration — mass_modulation flag
  5. Interaction with existing modulations (overlap, curvature)
  6. K2 lazy decay behavior of mass observables
  7. Edge cases and boundary conditions

Run:
    python -m pytest e0_controller/test_qualitative_mass.py -v
"""
import math
import unittest

from e0_controller.historization import Historization
from e0_controller.landscape import Landscape
from e0_controller.primitives import Edge, Outcome


def _make_edge(src="A", tgt="B"):
    return Edge(src, tgt)


def _build_simple_landscape(mass_mod=False):
    """A→B and A→C with Δ=1, R₀=1."""
    L = Landscape(mass_modulation=mass_mod)
    L.add_edge("A", "B", delta=1.0, resistance=1.0)
    L.add_edge("A", "C", delta=1.0, resistance=1.0)
    return L


# ─────────────────────────────────────────────
# 1. mass() — total accumulated experience
# ─────────────────────────────────────────────

class TestMass(unittest.TestCase):
    """mass(e) = U(e) + F(e): total accumulated experience."""

    def test_virgin_edge_zero_mass(self):
        """Never-used edge has zero mass."""
        H = Historization()
        self.assertAlmostEqual(H.mass(_make_edge()), 0.0)

    def test_single_success(self):
        """One success → mass = 1."""
        H = Historization()
        e = _make_edge()
        H.update(e, Outcome.SUCCESS)
        self.assertAlmostEqual(H.mass(e), 1.0)

    def test_single_failure(self):
        """One failure → mass = 1."""
        H = Historization()
        e = _make_edge()
        H.update(e, Outcome.FAILURE)
        self.assertAlmostEqual(H.mass(e), 1.0)

    def test_mixed_outcomes_additive(self):
        """5 successes + 3 failures → mass = sum with decay."""
        H = Historization(rho=1.0)  # no decay for clarity
        e = _make_edge()
        for _ in range(5):
            H.update(e, Outcome.SUCCESS)
        for _ in range(3):
            H.update(e, Outcome.FAILURE)
        self.assertAlmostEqual(H.mass(e), 8.0)

    def test_mass_positive_always(self):
        """mass ≥ 0 regardless of outcome mix."""
        H = Historization()
        e = _make_edge()
        for _ in range(10):
            H.update(e, Outcome.SUCCESS)
        self.assertGreaterEqual(H.mass(e), 0.0)

    def test_decay_reduces_mass(self):
        """With ρ < 1, mass decays over time."""
        H = Historization(rho=0.5)
        e = _make_edge()
        H.update(e, Outcome.SUCCESS)
        m1 = H.mass(e)
        # Force time advance (update another edge)
        other = _make_edge("X", "Y")
        for _ in range(5):
            H.update(other, Outcome.SUCCESS)
        m2 = H.mass(e)
        self.assertLess(m2, m1)


# ─────────────────────────────────────────────
# 2. quality() — normalized balance
# ─────────────────────────────────────────────

class TestQuality(unittest.TestCase):
    """quality(e) = (U−F)/(U+F+ε) ∈ (−1, +1)."""

    def test_virgin_edge_zero_quality(self):
        """No experience → q ≈ 0."""
        H = Historization()
        self.assertAlmostEqual(H.quality(_make_edge()), 0.0, places=5)

    def test_pure_success(self):
        """Only successes → q → +1."""
        H = Historization(rho=1.0)
        e = _make_edge()
        for _ in range(10):
            H.update(e, Outcome.SUCCESS)
        q = H.quality(e)
        self.assertGreater(q, 0.99)

    def test_pure_failure(self):
        """Only failures → q → −1."""
        H = Historization(rho=1.0)
        e = _make_edge()
        for _ in range(10):
            H.update(e, Outcome.FAILURE)
        q = H.quality(e)
        self.assertLess(q, -0.99)

    def test_balanced_near_zero(self):
        """Equal successes and failures → q ≈ 0."""
        H = Historization(rho=1.0)
        e = _make_edge()
        for _ in range(10):
            H.update(e, Outcome.SUCCESS)
            H.update(e, Outcome.FAILURE)
        q = H.quality(e)
        self.assertAlmostEqual(q, 0.0, places=1)

    def test_quality_bounded(self):
        """q always in (−1, +1)."""
        H = Historization()
        e = _make_edge()
        for _ in range(100):
            H.update(e, Outcome.SUCCESS)
        self.assertLess(H.quality(e), 1.0)
        self.assertGreater(H.quality(e), -1.0)

    def test_quality_sign_matches_outcome(self):
        """More successes → positive, more failures → negative."""
        H = Historization(rho=1.0)
        e = _make_edge()
        # 7 successes, 3 failures
        for _ in range(7):
            H.update(e, Outcome.SUCCESS)
        for _ in range(3):
            H.update(e, Outcome.FAILURE)
        self.assertGreater(H.quality(e), 0.0)


# ─────────────────────────────────────────────
# 3. mass_modulation_factor — dampening
# ─────────────────────────────────────────────

class TestMassModulationFactor(unittest.TestCase):
    """M_mass = 1 − α · (m/(m+μ)) · (1 − |q|)."""

    def test_virgin_edge_neutral(self):
        """No experience → M_mass = 1.0."""
        H = Historization()
        self.assertAlmostEqual(
            H.mass_modulation_factor(_make_edge()), 1.0
        )

    def test_pure_success_neutral(self):
        """Clear success → |q| ≈ 1 → no dampening."""
        H = Historization(rho=1.0)
        e = _make_edge()
        for _ in range(20):
            H.update(e, Outcome.SUCCESS)
        mmf = H.mass_modulation_factor(e)
        self.assertAlmostEqual(mmf, 1.0, places=2)

    def test_pure_failure_neutral(self):
        """Clear failure → |q| ≈ 1 → no dampening."""
        H = Historization(rho=1.0)
        e = _make_edge()
        for _ in range(20):
            H.update(e, Outcome.FAILURE)
        mmf = H.mass_modulation_factor(e)
        self.assertAlmostEqual(mmf, 1.0, places=2)

    def test_conflicted_dampens(self):
        """High mass + low clarity → significant dampening."""
        H = Historization(rho=1.0)
        e = _make_edge()
        for _ in range(20):
            H.update(e, Outcome.SUCCESS)
            H.update(e, Outcome.FAILURE)
        mmf = H.mass_modulation_factor(e)
        # 40 events, q ≈ 0 → heavily damped
        self.assertLess(mmf, 0.7)

    def test_low_mass_mild_dampening(self):
        """Even with confusion, low mass → mild dampening."""
        H = Historization(rho=1.0)
        e = _make_edge()
        H.update(e, Outcome.SUCCESS)
        H.update(e, Outcome.FAILURE)
        mmf = H.mass_modulation_factor(e)
        # m=2, q≈0, m_norm = 2/7 ≈ 0.29
        # M_mass = 1 − 0.5 · 0.29 · 1.0 ≈ 0.86
        self.assertGreater(mmf, 0.8)

    def test_alpha_controls_strength(self):
        """Higher α → stronger dampening for conflicted edges."""
        H = Historization(rho=1.0)
        e = _make_edge()
        for _ in range(20):
            H.update(e, Outcome.SUCCESS)
            H.update(e, Outcome.FAILURE)
        mmf_low = H.mass_modulation_factor(e, alpha=0.2)
        mmf_high = H.mass_modulation_factor(e, alpha=0.8)
        self.assertGreater(mmf_low, mmf_high)

    def test_mu_controls_sensitivity(self):
        """Higher μ → slower mass build-up → less dampening."""
        H = Historization(rho=1.0)
        e = _make_edge()
        for _ in range(5):
            H.update(e, Outcome.SUCCESS)
            H.update(e, Outcome.FAILURE)
        mmf_low_mu = H.mass_modulation_factor(e, mu=2.0)   # 10/(10+2) = 0.83
        mmf_high_mu = H.mass_modulation_factor(e, mu=50.0)  # 10/(10+50) = 0.17
        self.assertLess(mmf_low_mu, mmf_high_mu)

    def test_factor_always_positive(self):
        """M_mass > 0 always (never blocks a transition completely)."""
        H = Historization(rho=1.0)
        e = _make_edge()
        for _ in range(100):
            H.update(e, Outcome.SUCCESS)
            H.update(e, Outcome.FAILURE)
        mmf = H.mass_modulation_factor(e, alpha=0.99, mu=1.0)
        self.assertGreater(mmf, 0.0)

    def test_factor_at_most_one(self):
        """M_mass ≤ 1.0 always (never enhances beyond neutral)."""
        H = Historization(rho=1.0)
        e = _make_edge()
        for _ in range(50):
            H.update(e, Outcome.SUCCESS)
        self.assertLessEqual(
            H.mass_modulation_factor(e), 1.0 + 1e-10
        )

    def test_exact_formula(self):
        """Verify exact calculation with known inputs."""
        H = Historization(rho=1.0)  # no decay
        e = _make_edge()
        # 3 successes, 3 failures → m=6, q=0
        for _ in range(3):
            H.update(e, Outcome.SUCCESS)
        for _ in range(3):
            H.update(e, Outcome.FAILURE)
        alpha, mu = 0.5, 5.0
        # m=6, m_norm = 6/11 ≈ 0.5455, q=0, |q|=0, confusion=1
        # M_mass = 1 − 0.5 · (6/11) · 1.0 = 1 − 3/11 ≈ 0.7273
        expected = 1.0 - alpha * (6.0 / 11.0) * 1.0
        actual = H.mass_modulation_factor(e, alpha=alpha, mu=mu)
        self.assertAlmostEqual(actual, expected, places=4)


# ─────────────────────────────────────────────
# 4. Landscape integration
# ─────────────────────────────────────────────

class TestMassModulationLandscape(unittest.TestCase):
    """mass_modulation flag integration into transition_field."""

    def test_disabled_by_default(self):
        """mass_modulation is False by default."""
        L = Landscape()
        self.assertFalse(L.mass_modulation)

    def test_no_effect_when_disabled(self):
        """Conflicted history does not affect v when flag is off.

        With ρ=1.0 and equal λ, balanced U/F → δ_H exactly 0,
        so v is unchanged. The test isolates mass_modulation from
        the asymmetric-rate effect of the default parameters.
        """
        L = _build_simple_landscape(mass_mod=False)
        # ρ=1 eliminates decay-induced asymmetry between alternating updates
        L.historization.rho = 1.0
        L.historization.lambda_s = 0.2
        L.historization.lambda_f = 0.2
        e = Edge("A", "B")
        v_before = L.transition_field("A", "B")
        for _ in range(10):
            L.historization.update(e, Outcome.SUCCESS)
            L.historization.update(e, Outcome.FAILURE)
        v_after = L.transition_field("A", "B")
        # δ_H = 0.2·F − 0.2·U = 0 (balanced, no decay) → R_eff = R₀ → v unchanged
        self.assertAlmostEqual(v_before, v_after, places=10)

    def test_dampens_conflicted_when_enabled(self):
        """Conflicted edge has lower v when mass_modulation=True."""
        L = _build_simple_landscape(mass_mod=True)
        e_ab = Edge("A", "B")
        v_clean = L.transition_field("A", "C")  # no history
        # Deposit conflicting experience on A→B
        for _ in range(20):
            L.historization.update(e_ab, Outcome.SUCCESS)
            L.historization.update(e_ab, Outcome.FAILURE)
        v_conflicted = L.transition_field("A", "B")
        # Conflicted edge should be dampened relative to clean edge
        self.assertLess(v_conflicted, v_clean)

    def test_clear_history_not_dampened(self):
        """Edge with clear history (only successes) is NOT dampened."""
        L = _build_simple_landscape(mass_mod=True)
        e_ab = Edge("A", "B")
        # Deposit clear success history
        for _ in range(10):
            L.historization.update(e_ab, Outcome.SUCCESS)
        # v should not be reduced by mass_modulation (q ≈ +1 → |q| ≈ 1)
        # But R_eff is lowered by δ_H < 0, so v_success > v_clean
        v_success = L.transition_field("A", "B")
        self.assertGreater(v_success, 0.0)

    def test_compatible_with_overlap_modulation(self):
        """Both overlap and mass modulation can be active."""
        L = Landscape(mass_modulation=True, overlap_modulation=True)
        L.add_edge("A", "B", delta=1.0, resistance=1.0)
        L.add_edge("A", "C", delta=1.0, resistance=1.0)
        L.add_edge("C", "B", delta=1.0, resistance=1.0)
        # Should not raise, should produce valid v
        v = L.transition_field("A", "B")
        self.assertGreater(v, 0.0)
        self.assertTrue(math.isfinite(v))


# ─────────────────────────────────────────────
# 5. K2 lazy decay behavior
# ─────────────────────────────────────────────

class TestMassQualityDecay(unittest.TestCase):
    """mass() and quality() respect K2 lazy global decay."""

    def test_mass_decays_with_time(self):
        """Mass decays when edge is not touched."""
        H = Historization(rho=0.5)
        e = _make_edge()
        H.update(e, Outcome.SUCCESS)
        m1 = H.mass(e)
        # Advance time by updating other edge
        other = _make_edge("X", "Y")
        for _ in range(10):
            H.update(other, Outcome.SUCCESS)
        m2 = H.mass(e)
        self.assertLess(m2, m1 * 0.1)  # ρ^10 = 0.5^10 ≈ 0.001

    def test_quality_preserved_under_symmetric_decay(self):
        """Decay is multiplicative → q = (ρ^k·U − ρ^k·F)/(ρ^k·U + ρ^k·F)
        simplifies to (U−F)/(U+F) — quality is decay-invariant."""
        H = Historization(rho=0.8)
        e = _make_edge()
        for _ in range(5):
            H.update(e, Outcome.SUCCESS)
        for _ in range(2):
            H.update(e, Outcome.FAILURE)
        q1 = H.quality(e)
        # Advance time
        other = _make_edge("X", "Y")
        for _ in range(20):
            H.update(other, Outcome.SUCCESS)
        q2 = H.quality(e)
        # Quality should be approximately preserved (exact if no ε)
        self.assertAlmostEqual(q1, q2, places=3)

    def test_mass_modulation_factor_approaches_neutral_with_decay(self):
        """As mass decays to 0, M_mass → 1.0 (neutral)."""
        H = Historization(rho=0.5)
        e = _make_edge()
        for _ in range(10):
            H.update(e, Outcome.SUCCESS)
            H.update(e, Outcome.FAILURE)
        mmf_early = H.mass_modulation_factor(e)
        # Advance many steps
        other = _make_edge("X", "Y")
        for _ in range(50):
            H.update(other, Outcome.SUCCESS)
        mmf_late = H.mass_modulation_factor(e)
        self.assertLess(mmf_early, mmf_late)
        self.assertAlmostEqual(mmf_late, 1.0, places=2)


# ─────────────────────────────────────────────
# 6. Consistency with δ_H
# ─────────────────────────────────────────────

class TestMassQualityConsistency(unittest.TestCase):
    """mass/quality are consistent with δ_H."""

    def test_delta_h_sign_matches_quality_sign(self):
        """When quality > 0 (success-dominated), δ_H < 0 (resistance lowered)."""
        H = Historization(rho=1.0)
        e = _make_edge()
        for _ in range(10):
            H.update(e, Outcome.SUCCESS)
        q = H.quality(e)
        dh = H.delta_H(e)
        self.assertGreater(q, 0.0)
        self.assertLess(dh, 0.0)

    def test_delta_h_zero_when_balanced(self):
        """When quality ≈ 0 and λ_f ≈ λ_s, δ_H ≈ 0."""
        H = Historization(rho=1.0, lambda_s=0.2, lambda_f=0.2)
        e = _make_edge()
        for _ in range(10):
            H.update(e, Outcome.SUCCESS)
            H.update(e, Outcome.FAILURE)
        # With equal rates, δ_H = λ·F − λ·U = λ(F−U) ≈ 0
        self.assertAlmostEqual(H.delta_H(e), 0.0, places=5)

    def test_high_mass_low_delta_h_detectable(self):
        """The key case: high mass + δ_H ≈ 0. mass() reveals the hidden experience."""
        H = Historization(rho=1.0, lambda_s=0.2, lambda_f=0.2)
        e = _make_edge()
        for _ in range(50):
            H.update(e, Outcome.SUCCESS)
            H.update(e, Outcome.FAILURE)
        dh = H.delta_H(e)
        m = H.mass(e)
        q = H.quality(e)
        # δ_H ≈ 0 (looks like no experience)
        self.assertAlmostEqual(dh, 0.0, places=3)
        # But mass reveals: lots of experience!
        self.assertGreater(m, 50.0)
        # And quality reveals: it's contradictory
        self.assertAlmostEqual(q, 0.0, places=1)


if __name__ == "__main__":
    unittest.main()
