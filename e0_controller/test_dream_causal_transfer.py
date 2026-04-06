"""
C178 — Dream Causal Transfer tests

Tests for context_sensitivity integration into EdgeFingerprint and
fingerprint_distance (4D fingerprint extension).
"""

import math

import pytest

from e0_controller.dream_mode import (
    DreamObserver,
    EdgeFingerprint,
    domain_fingerprints,
    edge_fingerprint,
    find_equivalences,
    fingerprint_distance,
)
from e0_controller.landscape import Landscape
from e0_controller.primitives import Edge, Outcome


# ── Fingerprint Extension ────────────────────────────────────────────

class TestFingerprintContextSensitivity:
    """C178: EdgeFingerprint carries context_sensitivity."""

    def test_default_cs_zero(self):
        """Backward compatibility: cs defaults to 0.0."""
        fp = EdgeFingerprint("A", Edge("x", "y"), 0.5, 10.0, 0.8)
        assert fp.context_sensitivity == 0.0

    def test_explicit_cs(self):
        fp = EdgeFingerprint("A", Edge("x", "y"), 0.5, 10.0, 0.8,
                             context_sensitivity=1.5)
        assert fp.context_sensitivity == 1.5

    def test_distance_zero_cs_unchanged(self):
        """When both cs=0, distance is identical to 3D formula."""
        fa = EdgeFingerprint("A", Edge("x", "y"), 0.5, 10.0, 0.8)
        fb = EdgeFingerprint("B", Edge("p", "q"), -0.3, 5.0, 0.9)
        d = fingerprint_distance(fa, fb)
        # Manual 3D calculation
        dq = 0.5 - (-0.3)
        dm = 10.0 / (10.0 + 5.0) - 5.0 / (5.0 + 5.0)
        di = 0.8 - 0.9
        expected = math.sqrt(dq**2 + dm**2 + di**2)
        assert abs(d - expected) < 1e-10

    def test_distance_includes_cs(self):
        """cs difference increases fingerprint distance."""
        fa = EdgeFingerprint("A", Edge("x", "y"), 0.5, 10.0, 0.8,
                             context_sensitivity=0.0)
        fb = EdgeFingerprint("B", Edge("p", "q"), 0.5, 10.0, 0.8,
                             context_sensitivity=2.0)
        d = fingerprint_distance(fa, fb)
        # q, load, inertia identical → distance = |0.0 - 2.0| = 2.0
        assert abs(d - 2.0) < 1e-10

    def test_distance_cs_increases_total(self):
        """cs adds orthogonal dimension — total distance never decreases."""
        fa = EdgeFingerprint("A", Edge("x", "y"), 0.5, 10.0, 0.8,
                             context_sensitivity=0.0)
        fb = EdgeFingerprint("B", Edge("p", "q"), -0.3, 5.0, 0.9,
                             context_sensitivity=1.0)
        d_with_cs = fingerprint_distance(fa, fb)
        # Same but without cs contribution
        fa0 = EdgeFingerprint("A", Edge("x", "y"), 0.5, 10.0, 0.8)
        fb0 = EdgeFingerprint("B", Edge("p", "q"), -0.3, 5.0, 0.9)
        d_without_cs = fingerprint_distance(fa0, fb0)
        assert d_with_cs > d_without_cs

    def test_identical_fingerprints_with_cs(self):
        """Identical fingerprints (including cs) → distance 0."""
        fa = EdgeFingerprint("A", Edge("x", "y"), 0.5, 10.0, 0.8,
                             context_sensitivity=1.5)
        fb = EdgeFingerprint("B", Edge("p", "q"), 0.5, 10.0, 0.8,
                             context_sensitivity=1.5)
        assert fingerprint_distance(fa, fb) < 1e-10

    def test_max_cs_difference(self):
        """Maximum cs difference (0 vs 2) contributes 2.0 to distance."""
        fa = EdgeFingerprint("A", Edge("x", "y"), 0.0, 0.0, 1.0,
                             context_sensitivity=0.0)
        fb = EdgeFingerprint("B", Edge("p", "q"), 0.0, 0.0, 1.0,
                             context_sensitivity=2.0)
        d = fingerprint_distance(fa, fb)
        assert abs(d - 2.0) < 1e-10


# ── Edge Fingerprint Extraction ──────────────────────────────────────

class TestEdgeFingerprintExtraction:
    """C178: edge_fingerprint() extracts cs from historization."""

    def test_no_predecessor_cs_zero(self):
        """Edge without predecessor data → cs=0.0."""
        L = Landscape()
        L.add_state("A")
        L.add_state("B")
        L.add_edge("A", "B", delta=1.0, resistance=0.3)
        L.historization.record(Edge("A", "B"), Outcome.SUCCESS, 0.3, 0.25)
        fp = edge_fingerprint(Edge("A", "B"), L, "test")
        assert fp.context_sensitivity == 0.0

    def test_single_predecessor_cs_zero(self):
        """Edge with one predecessor → cs=0.0 (need ≥2)."""
        L = Landscape()
        L.add_state("A")
        L.add_state("B")
        L.add_edge("A", "B", delta=1.0, resistance=0.3)
        pred = Edge("X", "A")
        L.historization.record(Edge("A", "B"), Outcome.SUCCESS, 0.3, 0.25, predecessor=pred)
        L.historization.record(Edge("A", "B"), Outcome.SUCCESS, 0.3, 0.25, predecessor=pred)
        fp = edge_fingerprint(Edge("A", "B"), L, "test")
        assert fp.context_sensitivity == 0.0

    def test_confounded_edge_high_cs(self):
        """Edge with 2 predecessors, opposite outcomes → cs=2.0."""
        L = Landscape()
        for s in ["A", "B", "C"]:
            L.add_state(s)
        L.add_edge("B", "C", delta=1.0, resistance=0.3)

        pred_a = Edge("A", "B")
        pred_x = Edge("X", "B")

        # From A→B: always succeeds
        for _ in range(5):
            L.historization.record(Edge("B", "C"), Outcome.SUCCESS,
                                  0.3, 0.25, predecessor=pred_a)
        # From X→B: always fails
        for _ in range(5):
            L.historization.record(Edge("B", "C"), Outcome.FAILURE,
                                  0.3, 0.35, predecessor=pred_x)

        fp = edge_fingerprint(Edge("B", "C"), L, "test")
        assert abs(fp.context_sensitivity - 2.0) < 1e-10

    def test_clean_edge_zero_cs(self):
        """Edge with 2 predecessors, same outcome → cs=0.0."""
        L = Landscape()
        for s in ["A", "B", "C"]:
            L.add_state(s)
        L.add_edge("B", "C", delta=1.0, resistance=0.3)

        pred_a = Edge("A", "B")
        pred_x = Edge("X", "B")

        for _ in range(5):
            L.historization.record(Edge("B", "C"), Outcome.SUCCESS,
                                  0.3, 0.25, predecessor=pred_a)
        for _ in range(5):
            L.historization.record(Edge("B", "C"), Outcome.SUCCESS,
                                  0.3, 0.25, predecessor=pred_x)

        fp = edge_fingerprint(Edge("B", "C"), L, "test")
        assert fp.context_sensitivity == 0.0


# ── Equivalence Filtering ────────────────────────────────────────────

class TestEquivalenceWithCS:
    """C178: find_equivalences respects context_sensitivity."""

    def _make_twin_landscapes(self):
        """Build CAUSAL (cs=0) and CONFOUNDED (cs=2) landscapes."""
        # CAUSAL: B→GOAL works from any predecessor
        L_causal = Landscape()
        for s in ["A", "B", "C", "GOAL"]:
            L_causal.add_state(s)
        L_causal.add_edge("A", "B", delta=1.0, resistance=0.3)
        L_causal.add_edge("C", "B", delta=1.0, resistance=0.3)
        L_causal.add_edge("B", "GOAL", delta=1.0, resistance=0.3)

        pred_a = Edge("A", "B")
        pred_c = Edge("C", "B")
        # B→GOAL always succeeds regardless of predecessor
        for _ in range(5):
            L_causal.historization.record(
                Edge("B", "GOAL"), Outcome.SUCCESS, 0.3, 0.25,
                predecessor=pred_a)
            L_causal.historization.record(
                Edge("B", "GOAL"), Outcome.SUCCESS, 0.3, 0.25,
                predecessor=pred_c)

        # CONFOUNDED: B→GOAL depends on predecessor
        L_confound = Landscape()
        for s in ["A", "B", "C", "GOAL"]:
            L_confound.add_state(s)
        L_confound.add_edge("A", "B", delta=1.0, resistance=0.3)
        L_confound.add_edge("C", "B", delta=1.0, resistance=0.3)
        L_confound.add_edge("B", "GOAL", delta=1.0, resistance=0.3)

        for _ in range(5):
            L_confound.historization.record(
                Edge("B", "GOAL"), Outcome.SUCCESS, 0.3, 0.25,
                predecessor=pred_a)
            L_confound.historization.record(
                Edge("B", "GOAL"), Outcome.FAILURE, 0.3, 0.35,
                predecessor=pred_c)

        # Also record A→B and C→B identically in both
        for L in [L_causal, L_confound]:
            for _ in range(5):
                L.historization.record(Edge("A", "B"), Outcome.SUCCESS,
                                      0.3, 0.25)
                L.historization.record(Edge("C", "B"), Outcome.SUCCESS,
                                      0.3, 0.25)

        return L_causal, L_confound

    def test_causal_b_goal_cs_zero(self):
        L_causal, _ = self._make_twin_landscapes()
        fp = edge_fingerprint(Edge("B", "GOAL"), L_causal, "CAUSAL")
        assert fp.context_sensitivity == 0.0

    def test_confounded_b_goal_cs_two(self):
        _, L_confound = self._make_twin_landscapes()
        fp = edge_fingerprint(Edge("B", "GOAL"), L_confound, "CONF")
        assert abs(fp.context_sensitivity - 2.0) < 1e-10

    def test_b_goal_not_equivalent(self):
        """B→GOAL should NOT be matched between CAUSAL and CONFOUNDED."""
        L_causal, L_confound = self._make_twin_landscapes()
        equivs = find_equivalences(
            L_causal, L_confound,
            domain_a="CAUSAL", domain_b="CONFOUNDED",
            quantile=0.5,
        )
        b_goal_matched = any(
            eq.edge_a == Edge("B", "GOAL") and
            eq.edge_b == Edge("B", "GOAL")
            for eq in equivs
        )
        assert not b_goal_matched

    def test_clean_edges_still_match(self):
        """A→B and C→B (identical in both domains) should still match."""
        L_causal, L_confound = self._make_twin_landscapes()
        equivs = find_equivalences(
            L_causal, L_confound,
            domain_a="CAUSAL", domain_b="CONFOUNDED",
            quantile=0.5,
        )
        a_b_matched = any(
            eq.edge_a == Edge("A", "B") and
            eq.edge_b == Edge("A", "B")
            for eq in equivs
        )
        assert a_b_matched

    def test_cs_increases_b_goal_distance(self):
        """Distance for B→GOAL includes cs dimension.

        CAUSAL B→GOAL: q=+1.0, cs=0.0
        CONFOUNDED B→GOAL: q=0.0, cs=2.0
        Without cs: distance ≈ 1.0 (from quality alone)
        With cs: distance > 2.0 (quality + cs divergence)
        """
        L_causal, L_confound = self._make_twin_landscapes()
        fp_causal = edge_fingerprint(Edge("B", "GOAL"), L_causal, "C")
        fp_confound = edge_fingerprint(Edge("B", "GOAL"), L_confound, "F")
        d = fingerprint_distance(fp_causal, fp_confound)
        assert d > 1.99  # cs=2.0 dominates distance


# ── Domain Fingerprints ──────────────────────────────────────────────

class TestDomainFingerprintsWithCS:
    """C178: domain_fingerprints includes cs values."""

    def test_fingerprints_carry_cs(self):
        """domain_fingerprints includes context_sensitivity for each edge."""
        L = Landscape()
        for s in ["A", "B", "C"]:
            L.add_state(s)
        L.add_edge("A", "B", delta=1.0, resistance=0.3)
        L.add_edge("B", "C", delta=1.0, resistance=0.3)

        pred_a = Edge("A", "B")
        pred_x = Edge("X", "B")
        for _ in range(3):
            L.historization.record(Edge("B", "C"), Outcome.SUCCESS,
                                  0.3, 0.25, predecessor=pred_a)
            L.historization.record(Edge("B", "C"), Outcome.FAILURE,
                                  0.3, 0.35, predecessor=pred_x)

        fps = domain_fingerprints(L, "test")
        fp_bc = next(fp for fp in fps if fp.edge == Edge("B", "C"))
        assert abs(fp_bc.context_sensitivity - 2.0) < 1e-10

        fp_ab = next(fp for fp in fps if fp.edge == Edge("A", "B"))
        assert fp_ab.context_sensitivity == 0.0
