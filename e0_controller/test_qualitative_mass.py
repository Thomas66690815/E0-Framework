"""
E₀ Structural Inscription & Inertia — Tests (C42)
===================================================
Tests for the layered mass model per Ontodynamics §4:

  Layer 1: Historization — the process (update/decay)
  Layer 2: Structural Inscription — trace_load, trace_quality
  Layer 3: Inertia — inertia_factor, inertia_modulation
  Layer 4: Mass — emergent outward appearance (not computed)

Covers:
  1. trace_load() — total accumulated inscription (U + F)
  2. trace_quality() — normalized success/failure balance
  3. inertia_factor() — dampening for conflicted edges
  4. Landscape integration — inertia_modulation flag
  5. Interaction with existing modulations (overlap, curvature)
  6. K2 lazy decay behavior
  7. Consistency with δ_H
  8. Backward-compatible aliases

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


def _build_simple_landscape(inertia=False):
    """A→B and A→C with Δ=1, R₀=1."""
    L = Landscape(inertia_modulation=inertia)
    L.add_edge("A", "B", delta=1.0, resistance=1.0)
    L.add_edge("A", "C", delta=1.0, resistance=1.0)
    return L


# ─────────────────────────────────────────────
# 1. trace_load() — total accumulated inscription
# ─────────────────────────────────────────────

class TestTraceLoad(unittest.TestCase):
    """trace_load(e) = U(e) + F(e): total structural inscription."""

    def test_virgin_edge_zero(self):
        """Never-used edge has zero trace load."""
        H = Historization()
        self.assertAlmostEqual(H.trace_load(_make_edge()), 0.0)

    def test_single_success(self):
        """One success → trace_load = 1."""
        H = Historization()
        e = _make_edge()
        H.update(e, Outcome.SUCCESS)
        self.assertAlmostEqual(H.trace_load(e), 1.0)

    def test_single_failure(self):
        """One failure → trace_load = 1."""
        H = Historization()
        e = _make_edge()
        H.update(e, Outcome.FAILURE)
        self.assertAlmostEqual(H.trace_load(e), 1.0)

    def test_mixed_outcomes_additive(self):
        """5 successes + 3 failures → trace_load = 8 (no decay)."""
        H = Historization(rho=1.0)
        e = _make_edge()
        for _ in range(5):
            H.update(e, Outcome.SUCCESS)
        for _ in range(3):
            H.update(e, Outcome.FAILURE)
        self.assertAlmostEqual(H.trace_load(e), 8.0)

    def test_always_non_negative(self):
        """trace_load ≥ 0 regardless of outcome mix."""
        H = Historization()
        e = _make_edge()
        for _ in range(10):
            H.update(e, Outcome.SUCCESS)
        self.assertGreaterEqual(H.trace_load(e), 0.0)

    def test_decay_reduces_load(self):
        """With ρ < 1, trace load decays over time."""
        H = Historization(rho=0.5)
        e = _make_edge()
        H.update(e, Outcome.SUCCESS)
        m1 = H.trace_load(e)
        other = _make_edge("X", "Y")
        for _ in range(5):
            H.update(other, Outcome.SUCCESS)
        m2 = H.trace_load(e)
        self.assertLess(m2, m1)


# ─────────────────────────────────────────────
# 2. trace_quality() — normalized balance
# ─────────────────────────────────────────────

class TestTraceQuality(unittest.TestCase):
    """trace_quality(e) = (U−F)/(U+F+ε) ∈ (−1, +1)."""

    def test_virgin_edge_zero(self):
        """No inscription → q ≈ 0."""
        H = Historization()
        self.assertAlmostEqual(H.trace_quality(_make_edge()), 0.0, places=5)

    def test_pure_success(self):
        """Only successes → q → +1."""
        H = Historization(rho=1.0)
        e = _make_edge()
        for _ in range(10):
            H.update(e, Outcome.SUCCESS)
        q = H.trace_quality(e)
        self.assertGreater(q, 0.99)

    def test_pure_failure(self):
        """Only failures → q → −1."""
        H = Historization(rho=1.0)
        e = _make_edge()
        for _ in range(10):
            H.update(e, Outcome.FAILURE)
        q = H.trace_quality(e)
        self.assertLess(q, -0.99)

    def test_balanced_near_zero(self):
        """Equal successes and failures → q ≈ 0."""
        H = Historization(rho=1.0)
        e = _make_edge()
        for _ in range(10):
            H.update(e, Outcome.SUCCESS)
            H.update(e, Outcome.FAILURE)
        q = H.trace_quality(e)
        self.assertAlmostEqual(q, 0.0, places=1)

    def test_bounded(self):
        """q always in (−1, +1)."""
        H = Historization()
        e = _make_edge()
        for _ in range(100):
            H.update(e, Outcome.SUCCESS)
        self.assertLess(H.trace_quality(e), 1.0)
        self.assertGreater(H.trace_quality(e), -1.0)

    def test_sign_matches_outcome(self):
        """More successes → positive, more failures → negative."""
        H = Historization(rho=1.0)
        e = _make_edge()
        for _ in range(7):
            H.update(e, Outcome.SUCCESS)
        for _ in range(3):
            H.update(e, Outcome.FAILURE)
        self.assertGreater(H.trace_quality(e), 0.0)


# ─────────────────────────────────────────────
# 3. inertia_factor — dampening (Layer 3)
# ─────────────────────────────────────────────

class TestInertiaFactor(unittest.TestCase):
    """I(e) = 1 − α · (m/(m+μ)) · (1 − |q|)."""

    def test_virgin_edge_neutral(self):
        """No inscription → I = 1.0."""
        H = Historization()
        self.assertAlmostEqual(
            H.inertia_factor(_make_edge()), 1.0
        )

    def test_pure_success_neutral(self):
        """Clear success → |q| ≈ 1 → no dampening."""
        H = Historization(rho=1.0)
        e = _make_edge()
        for _ in range(20):
            H.update(e, Outcome.SUCCESS)
        self.assertAlmostEqual(H.inertia_factor(e), 1.0, places=2)

    def test_pure_failure_neutral(self):
        """Clear failure → |q| ≈ 1 → no dampening."""
        H = Historization(rho=1.0)
        e = _make_edge()
        for _ in range(20):
            H.update(e, Outcome.FAILURE)
        self.assertAlmostEqual(H.inertia_factor(e), 1.0, places=2)

    def test_conflicted_dampens(self):
        """High inscription + low clarity → significant dampening."""
        H = Historization(rho=1.0)
        e = _make_edge()
        for _ in range(20):
            H.update(e, Outcome.SUCCESS)
            H.update(e, Outcome.FAILURE)
        self.assertLess(H.inertia_factor(e), 0.7)

    def test_low_inscription_mild(self):
        """Even with confusion, low inscription → mild dampening."""
        H = Historization(rho=1.0)
        e = _make_edge()
        H.update(e, Outcome.SUCCESS)
        H.update(e, Outcome.FAILURE)
        self.assertGreater(H.inertia_factor(e), 0.8)

    def test_alpha_controls_strength(self):
        """Higher α → stronger dampening for conflicted edges."""
        H = Historization(rho=1.0)
        e = _make_edge()
        for _ in range(20):
            H.update(e, Outcome.SUCCESS)
            H.update(e, Outcome.FAILURE)
        low = H.inertia_factor(e, alpha=0.2)
        high = H.inertia_factor(e, alpha=0.8)
        self.assertGreater(low, high)

    def test_mu_controls_sensitivity(self):
        """Higher μ → slower build-up → less dampening."""
        H = Historization(rho=1.0)
        e = _make_edge()
        for _ in range(5):
            H.update(e, Outcome.SUCCESS)
            H.update(e, Outcome.FAILURE)
        low_mu = H.inertia_factor(e, mu=2.0)
        high_mu = H.inertia_factor(e, mu=50.0)
        self.assertLess(low_mu, high_mu)

    def test_always_positive(self):
        """I > 0 always (never blocks a transition completely)."""
        H = Historization(rho=1.0)
        e = _make_edge()
        for _ in range(100):
            H.update(e, Outcome.SUCCESS)
            H.update(e, Outcome.FAILURE)
        self.assertGreater(
            H.inertia_factor(e, alpha=0.99, mu=1.0), 0.0
        )

    def test_at_most_one(self):
        """I ≤ 1.0 always (never enhances beyond neutral)."""
        H = Historization(rho=1.0)
        e = _make_edge()
        for _ in range(50):
            H.update(e, Outcome.SUCCESS)
        self.assertLessEqual(
            H.inertia_factor(e), 1.0 + 1e-10
        )

    def test_exact_formula(self):
        """Verify exact calculation with known inputs."""
        H = Historization(rho=1.0)
        e = _make_edge()
        for _ in range(3):
            H.update(e, Outcome.SUCCESS)
        for _ in range(3):
            H.update(e, Outcome.FAILURE)
        alpha, mu = 0.5, 5.0
        # m=6, m_norm=6/11, q=0, confusion=1
        expected = 1.0 - alpha * (6.0 / 11.0) * 1.0
        actual = H.inertia_factor(e, alpha=alpha, mu=mu)
        self.assertAlmostEqual(actual, expected, places=4)


# ─────────────────────────────────────────────
# 4. Landscape integration (Layer 3)
# ─────────────────────────────────────────────

class TestInertiaModulationLandscape(unittest.TestCase):
    """inertia_modulation flag integration into transition_field."""

    def test_disabled_by_default(self):
        """inertia_modulation is False by default."""
        L = Landscape()
        self.assertFalse(L.inertia_modulation)

    def test_no_effect_when_disabled(self):
        """Conflicted history does not affect v when flag is off.

        With ρ=1.0 and equal λ, balanced U/F → δ_H exactly 0,
        so v is unchanged. The test isolates inertia_modulation from
        the asymmetric-rate effect of the default parameters.
        """
        L = _build_simple_landscape(inertia=False)
        L.historization.rho = 1.0
        L.historization.lambda_s = 0.2
        L.historization.lambda_f = 0.2
        e = Edge("A", "B")
        v_before = L.transition_field("A", "B")
        for _ in range(10):
            L.historization.update(e, Outcome.SUCCESS)
            L.historization.update(e, Outcome.FAILURE)
        v_after = L.transition_field("A", "B")
        self.assertAlmostEqual(v_before, v_after, places=10)

    def test_dampens_conflicted_when_enabled(self):
        """Conflicted edge has lower v when inertia_modulation=True."""
        L = _build_simple_landscape(inertia=True)
        e_ab = Edge("A", "B")
        v_clean = L.transition_field("A", "C")
        for _ in range(20):
            L.historization.update(e_ab, Outcome.SUCCESS)
            L.historization.update(e_ab, Outcome.FAILURE)
        v_conflicted = L.transition_field("A", "B")
        self.assertLess(v_conflicted, v_clean)

    def test_clear_history_not_dampened(self):
        """Edge with clear history (only successes) is NOT dampened."""
        L = _build_simple_landscape(inertia=True)
        e_ab = Edge("A", "B")
        for _ in range(10):
            L.historization.update(e_ab, Outcome.SUCCESS)
        v_success = L.transition_field("A", "B")
        self.assertGreater(v_success, 0.0)

    def test_compatible_with_overlap_modulation(self):
        """Both overlap and inertia modulation can be active."""
        L = Landscape(inertia_modulation=True, overlap_modulation=True)
        L.add_edge("A", "B", delta=1.0, resistance=1.0)
        L.add_edge("A", "C", delta=1.0, resistance=1.0)
        L.add_edge("C", "B", delta=1.0, resistance=1.0)
        v = L.transition_field("A", "B")
        self.assertGreater(v, 0.0)
        self.assertTrue(math.isfinite(v))


# ─────────────────────────────────────────────
# 5. K2 lazy decay behavior
# ─────────────────────────────────────────────

class TestInscriptionDecay(unittest.TestCase):
    """trace_load() and trace_quality() respect K2 lazy global decay."""

    def test_load_decays_with_time(self):
        """Trace load decays when edge is not touched."""
        H = Historization(rho=0.5)
        e = _make_edge()
        H.update(e, Outcome.SUCCESS)
        m1 = H.trace_load(e)
        other = _make_edge("X", "Y")
        for _ in range(10):
            H.update(other, Outcome.SUCCESS)
        m2 = H.trace_load(e)
        self.assertLess(m2, m1 * 0.1)

    def test_quality_preserved_under_symmetric_decay(self):
        """Decay is multiplicative → q = (ρ^k·U − ρ^k·F)/(ρ^k·U + ρ^k·F)
        simplifies to (U−F)/(U+F) — quality is decay-invariant."""
        H = Historization(rho=0.8)
        e = _make_edge()
        for _ in range(5):
            H.update(e, Outcome.SUCCESS)
        for _ in range(2):
            H.update(e, Outcome.FAILURE)
        q1 = H.trace_quality(e)
        other = _make_edge("X", "Y")
        for _ in range(20):
            H.update(other, Outcome.SUCCESS)
        q2 = H.trace_quality(e)
        self.assertAlmostEqual(q1, q2, places=3)

    def test_inertia_factor_approaches_neutral_with_decay(self):
        """As inscription decays to 0, inertia_factor → 1.0 (neutral)."""
        H = Historization(rho=0.5)
        e = _make_edge()
        for _ in range(10):
            H.update(e, Outcome.SUCCESS)
            H.update(e, Outcome.FAILURE)
        early = H.inertia_factor(e)
        other = _make_edge("X", "Y")
        for _ in range(50):
            H.update(other, Outcome.SUCCESS)
        late = H.inertia_factor(e)
        self.assertLess(early, late)
        self.assertAlmostEqual(late, 1.0, places=2)


# ─────────────────────────────────────────────
# 6. Consistency with δ_H
# ─────────────────────────────────────────────

class TestInscriptionConsistency(unittest.TestCase):
    """Structural inscription is consistent with δ_H."""

    def test_delta_h_sign_matches_quality_sign(self):
        """When quality > 0 (success-dominated), δ_H < 0 (resistance lowered)."""
        H = Historization(rho=1.0)
        e = _make_edge()
        for _ in range(10):
            H.update(e, Outcome.SUCCESS)
        q = H.trace_quality(e)
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
        self.assertAlmostEqual(H.delta_H(e), 0.0, places=5)

    def test_high_load_low_delta_h_detectable(self):
        """The key case: high load + δ_H ≈ 0. trace_load reveals hidden inscription."""
        H = Historization(rho=1.0, lambda_s=0.2, lambda_f=0.2)
        e = _make_edge()
        for _ in range(50):
            H.update(e, Outcome.SUCCESS)
            H.update(e, Outcome.FAILURE)
        dh = H.delta_H(e)
        m = H.trace_load(e)
        q = H.trace_quality(e)
        self.assertAlmostEqual(dh, 0.0, places=3)
        self.assertGreater(m, 50.0)
        self.assertAlmostEqual(q, 0.0, places=1)


# ─────────────────────────────────────────────
# 7. Backward-compatible aliases
# ─────────────────────────────────────────────

class TestBackwardCompatAliases(unittest.TestCase):
    """Old names (mass, quality, mass_modulation_factor, mass_modulation)
    still work via aliases."""

    def test_mass_alias(self):
        """H.mass(e) is the same function as H.trace_load(e)."""
        H = Historization(rho=1.0)
        e = _make_edge()
        H.update(e, Outcome.SUCCESS)
        self.assertEqual(H.mass(e), H.trace_load(e))

    def test_quality_alias(self):
        """H.quality(e) is the same function as H.trace_quality(e)."""
        H = Historization(rho=1.0)
        e = _make_edge()
        H.update(e, Outcome.SUCCESS)
        self.assertEqual(H.quality(e), H.trace_quality(e))

    def test_mass_modulation_factor_alias(self):
        """H.mass_modulation_factor(e) is the same as H.inertia_factor(e)."""
        H = Historization(rho=1.0)
        e = _make_edge()
        H.update(e, Outcome.SUCCESS)
        H.update(e, Outcome.FAILURE)
        self.assertEqual(
            H.mass_modulation_factor(e),
            H.inertia_factor(e),
        )

    def test_landscape_mass_modulation_property(self):
        """L.mass_modulation proxies to L.inertia_modulation."""
        L = Landscape()
        self.assertFalse(L.mass_modulation)
        L.mass_modulation = True
        self.assertTrue(L.inertia_modulation)
        L.inertia_modulation = False
        self.assertFalse(L.mass_modulation)


if __name__ == "__main__":
    unittest.main()
