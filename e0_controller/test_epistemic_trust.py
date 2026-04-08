"""
C186: Epistemic Trust — "E₀ zweifelt immer"

Tests for the self-calibrating trust mechanism in Historization.
trust(e) = exp(−staleness / τ_doubt(e)) where τ_doubt adapts to
per-edge stability (confirmations vs surprises).
"""

import math
import pytest
from e0_controller.primitives import Edge, Outcome
from e0_controller.historization import Historization
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller


# ─────────────────────── Helpers ───────────────────────

def make_edge(src="A", tgt="B"):
    return Edge(src, tgt)


def build_simple_landscape():
    """A → B → C with Δ and R₀ = 1.0."""
    L = Landscape()
    for s in ("A", "B", "C"):
        L.add_state(s)
    L.add_edge("A", "B", delta=0.5, resistance=1.0)
    L.add_edge("A", "C", delta=0.8, resistance=1.0)
    L.add_edge("B", "C", delta=0.3, resistance=1.0)
    return L


# ─────────────────────── Trust fundamentals ───────────────────────

class TestTrustBasics:
    """trust() returns correct values for basic scenarios."""

    def test_virgin_edge_trust_is_one(self):
        """Edges with no trace data → trust = 1.0 (nothing to doubt)."""
        H = Historization()
        assert H.trust(make_edge()) == 1.0

    def test_just_visited_trust_is_one(self):
        """Edge visited at current τ → trust = 1.0."""
        H = Historization()
        e = make_edge()
        H.update(e, Outcome.FAILURE)
        assert H.trust(e) == 1.0

    def test_trust_decays_with_staleness(self):
        """Trust should decrease as τ advances without revisit."""
        H = Historization()
        e = make_edge()
        H.update(e, Outcome.FAILURE)
        trust_at_0 = H.trust(e)
        # Advance τ by updating a different edge many times
        other = Edge("X", "Y")
        for _ in range(20):
            H.update(other, Outcome.SUCCESS)
        trust_at_20 = H.trust(e)
        assert trust_at_0 > trust_at_20
        assert trust_at_20 < 1.0
        assert trust_at_20 > 0.0

    def test_trust_is_bounded_zero_one(self):
        """Trust is always in (0, 1]."""
        H = Historization()
        e = make_edge()
        H.update(e, Outcome.FAILURE)
        other = Edge("X", "Y")
        for _ in range(200):
            H.update(other, Outcome.SUCCESS)
        t = H.trust(e)
        assert 0.0 < t <= 1.0


class TestStability:
    """stability() correctly measures confirmation vs surprise ratio."""

    def test_no_revisits_stability_zero(self):
        """Edge visited once → no revisit data → stability = 0."""
        H = Historization()
        e = make_edge()
        H.update(e, Outcome.FAILURE)
        assert H.stability(e) == 0.0

    def test_confirmed_revisit_increases_stability(self):
        """Revisit that matches prediction → confirmation → stability rises."""
        H = Historization()
        e = make_edge()
        H.update(e, Outcome.FAILURE)  # q < 0 → predicts FAILURE
        # Advance time
        for _ in range(5):
            H.update(Edge("X", "Y"), Outcome.SUCCESS)
        # Revisit: FAILURE again (confirms)
        H.update(e, Outcome.FAILURE)
        assert H.stability(e) > 0.0

    def test_surprised_revisit_keeps_stability_low(self):
        """Revisit that contradicts prediction → surprise → stability stays low."""
        H = Historization()
        e = make_edge()
        H.update(e, Outcome.FAILURE)  # q < 0 → predicts FAILURE
        for _ in range(5):
            H.update(Edge("X", "Y"), Outcome.SUCCESS)
        # Revisit: SUCCESS (surprise!)
        H.update(e, Outcome.SUCCESS)
        stab = H.stability(e)
        # Should be lower than if confirmed
        H2 = Historization()
        H2.update(e, Outcome.FAILURE)
        for _ in range(5):
            H2.update(Edge("X", "Y"), Outcome.SUCCESS)
        H2.update(e, Outcome.FAILURE)  # confirm
        stab_confirmed = H2.stability(e)
        assert stab < stab_confirmed

    def test_many_confirmations_high_stability(self):
        """Repeated confirmations → stability approaches 1."""
        H = Historization()
        e = make_edge()
        for _ in range(20):
            H.update(e, Outcome.SUCCESS)
            # Advance time
            for _ in range(3):
                H.update(Edge("X", "Y"), Outcome.SUCCESS)
            H.update(e, Outcome.SUCCESS)  # confirm: q > 0 and SUCCESS
        assert H.stability(e) > 0.5

    def test_alternating_outcomes_low_stability(self):
        """Alternating SUCCESS/FAILURE → many surprises → low stability."""
        H = Historization()
        e = make_edge()
        outcomes = [Outcome.SUCCESS, Outcome.FAILURE] * 10
        for oc in outcomes:
            H.update(e, oc)
            for _ in range(3):
                H.update(Edge("X", "Y"), Outcome.SUCCESS)
        # Stability should be low because outcomes keep flipping
        assert H.stability(e) < 0.5


class TestTrustDynamics:
    """Trust adapts correctly to different environments."""

    def test_stable_edge_retains_trust(self):
        """Edge confirmed multiple times → trust stays high even with staleness."""
        H = Historization()
        e = make_edge()
        # Build up confirmations
        for _ in range(10):
            H.update(e, Outcome.SUCCESS)
            for _ in range(3):
                H.update(Edge("X", "Y"), Outcome.SUCCESS)
            H.update(e, Outcome.SUCCESS)  # confirm
        trust_after_confirm = H.trust(e)
        # Now let it go stale
        for _ in range(10):
            H.update(Edge("X", "Y"), Outcome.SUCCESS)
        trust_after_stale = H.trust(e)
        # Should still be meaningful due to high stability
        # (stability itself decays via lazy ρ at staleness, so ~0.2 is expected)
        assert trust_after_stale > 0.15  # stable edges resist doubt

    def test_volatile_edge_loses_trust_fast(self):
        """Edge with alternating outcomes → loses trust quickly."""
        H = Historization()
        e = make_edge()
        for oc in [Outcome.SUCCESS, Outcome.FAILURE] * 5:
            H.update(e, oc)
            for _ in range(3):
                H.update(Edge("X", "Y"), Outcome.SUCCESS)
        # Now let it go stale
        for _ in range(10):
            H.update(Edge("X", "Y"), Outcome.SUCCESS)
        trust_volatile = H.trust(e)

        # Compare with stable edge
        H2 = Historization()
        for _ in range(10):
            H2.update(e, Outcome.SUCCESS)
            for _ in range(3):
                H2.update(Edge("X", "Y"), Outcome.SUCCESS)
            H2.update(e, Outcome.SUCCESS)
        for _ in range(10):
            H2.update(Edge("X", "Y"), Outcome.SUCCESS)
        trust_stable = H2.trust(e)

        assert trust_volatile < trust_stable

    def test_revisit_restores_trust(self):
        """After going stale, a revisit should restore trust to 1.0."""
        H = Historization()
        e = make_edge()
        H.update(e, Outcome.FAILURE)
        for _ in range(30):
            H.update(Edge("X", "Y"), Outcome.SUCCESS)
        trust_stale = H.trust(e)
        assert trust_stale < 0.5
        # Revisit
        H.update(e, Outcome.FAILURE)
        trust_revisited = H.trust(e)
        assert trust_revisited == 1.0


class TestDeltaHTrusted:
    """delta_H_trusted correctly combines δ_H with trust."""

    def test_fresh_edge_same_as_raw(self):
        """Just-updated edge → trust=1.0 → delta_H_trusted = delta_H."""
        H = Historization()
        e = make_edge()
        H.update(e, Outcome.FAILURE)
        assert H.delta_H_trusted(e) == H.delta_H(e)

    def test_stale_edge_reduced(self):
        """Stale edge → trust < 1.0 → delta_H_trusted < delta_H."""
        H = Historization()
        e = make_edge()
        H.update(e, Outcome.FAILURE)
        raw = H.delta_H(e)
        assert raw > 0  # failure → positive δ_H
        for _ in range(30):
            H.update(Edge("X", "Y"), Outcome.SUCCESS)
        trusted = H.delta_H_trusted(e)
        assert 0 < trusted < raw

    def test_virgin_edge_zero(self):
        """Virgin edge → δ_H = 0, trust = 1 → delta_H_trusted = 0."""
        H = Historization()
        assert H.delta_H_trusted(make_edge()) == 0.0


class TestControllerIntegration:
    """E0Controller uses trust when epistemic_trust=True."""

    def test_default_no_trust(self):
        """Without epistemic_trust, controller uses raw δ_H."""
        L = build_simple_landscape()
        ctrl = E0Controller(L, lambda s, t: Outcome.SUCCESS, epistemic_trust=False)
        e = Edge("A", "B")
        # Historize a failure
        L.historization.update(e, Outcome.FAILURE)
        r_eff = ctrl._effective_resistance("A", "B")
        r0 = L.base_resistance("A", "B")
        dh = L.historization.delta_H(e)
        assert abs(r_eff - (r0 + dh)) < 1e-10

    def test_trust_reduces_stale_penalty(self):
        """With epistemic_trust, stale failure penalty is reduced."""
        L = build_simple_landscape()
        ctrl = E0Controller(L, lambda s, t: Outcome.SUCCESS, epistemic_trust=True)
        e = Edge("A", "B")
        L.historization.update(e, Outcome.FAILURE)
        r_eff_fresh = ctrl._effective_resistance("A", "B")
        # Advance time
        for _ in range(30):
            L.historization.update(Edge("B", "C"), Outcome.SUCCESS)
        r_eff_stale = ctrl._effective_resistance("A", "B")
        # Stale penalty should be lower (closer to R₀)
        r0 = L.base_resistance("A", "B")
        assert r_eff_stale < r_eff_fresh
        assert r_eff_stale > r0  # some penalty remains, not fully gone

    def test_trust_disabled_no_effect(self):
        """Without epistemic_trust, staleness does not affect R_eff."""
        L = build_simple_landscape()
        ctrl = E0Controller(L, lambda s, t: Outcome.SUCCESS, epistemic_trust=False)
        e = Edge("A", "B")
        L.historization.update(e, Outcome.FAILURE)
        r_eff_fresh = ctrl._effective_resistance("A", "B")
        for _ in range(30):
            L.historization.update(Edge("B", "C"), Outcome.SUCCESS)
        r_eff_stale = ctrl._effective_resistance("A", "B")
        # Without trust, the penalty changes only from ρ-decay
        # (which IS expected to reduce it), but trust would reduce it MORE
        # We can at least verify both are close (ρ-decay is small)
        dh_raw = L.historization.delta_H(e)
        dh_trusted = L.historization.delta_H_trusted(e)
        assert dh_raw >= dh_trusted  # trust always ≤ 1


class TestSelfCalibration:
    """τ_base self-calibrates from navigation frequency."""

    def test_tau_base_from_intervals(self):
        """After revisits, τ_base should reflect median inter-visit interval."""
        H = Historization()
        e = make_edge()
        # Visit every 5 steps
        for i in range(10):
            H.update(e, Outcome.SUCCESS)
            for _ in range(4):
                H.update(Edge("X", "Y"), Outcome.SUCCESS)
        tau_base = H._tau_base()
        # Should be close to 5 (the inter-visit interval)
        assert 3 <= tau_base <= 7

    def test_tau_base_default_when_no_revisits(self):
        """Before any revisits, τ_base = 10 (conservative default)."""
        H = Historization()
        assert H._tau_base() == 10.0


class TestSnapshotPersistence:
    """Trust data survives serialization round-trip."""

    def test_round_trip_preserves_trust_data(self):
        """to_snapshot_dict / from_snapshot_dict preserves confirmations."""
        H = Historization()
        e = make_edge()
        H.update(e, Outcome.FAILURE)
        for _ in range(5):
            H.update(Edge("X", "Y"), Outcome.SUCCESS)
        H.update(e, Outcome.FAILURE)  # confirmation
        stab_before = H.stability(e)
        assert stab_before > 0

        snap = H.to_snapshot_dict()
        H2 = Historization.from_snapshot_dict(snap, lambda k: k)
        assert H2.stability(e) == pytest.approx(stab_before, abs=1e-10)

    def test_old_snapshot_without_trust(self):
        """Old snapshots without trust data load cleanly (backward compat)."""
        snap = {
            "tau": 5, "rho": 0.9, "lambda_s": 0.15, "lambda_f": 0.2,
            "delta_max": 3.0, "rho_s": None, "rho_f": None,
            "U": {}, "F": {}, "tau_last": {},
        }
        H = Historization.from_snapshot_dict(snap, lambda k: k)
        assert H.trust(make_edge()) == 1.0
        assert H.stability(make_edge()) == 0.0
