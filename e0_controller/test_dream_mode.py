"""Tests for Dream Mode — C109: Fingerprint + Equivalence Detection.

Tests cover:
  - Edge fingerprint extraction
  - Fingerprint distance metric properties
  - Functional equivalence detection across domains
  - Dream readiness trigger
  - Dream Landscape construction
  - Prediction P1: functional equivalence is detectable
  - Prediction P5: domain order does not matter
"""

import math
import pytest

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller
from e0_controller.benchmark_domain_invariance import (
    build_d1_linear_chain,
    build_d2_diamond,
    build_d3_gordian_trap,
    build_d4_greedy_trap,
)
from e0_controller.dream_mode import (
    EdgeFingerprint,
    Equivalence,
    edge_fingerprint,
    domain_fingerprints,
    fingerprint_distance,
    find_equivalences,
    dream_readiness,
    is_dream_ready,
    build_dream_landscape,
    _equivalence_state,
)


# ═══════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════

def _inscribe(landscape: Landscape, path: list[str], outcome: Outcome, n: int = 1):
    """Inscribe a path into a landscape's historization n times."""
    for _ in range(n):
        for i in range(len(path) - 1):
            edge = Edge(path[i], path[i + 1])
            landscape.historization.update(edge, outcome)


def _build_simple_domain(name: str = "test") -> Landscape:
    """A→B→C→GOAL with uniform Δ=0.5, R₀=1.0."""
    L = Landscape()
    for s, t in [("A", "B"), ("B", "C"), ("C", "GOAL")]:
        L.add_edge(s, t, delta=0.5, resistance=1.0)
    return L


def _build_parallel_domain() -> Landscape:
    """S→A→G and S→B→G with different Δ values."""
    L = Landscape()
    L.add_edge("S", "A", delta=0.3, resistance=0.5)
    L.add_edge("A", "G", delta=0.3, resistance=0.5)
    L.add_edge("S", "B", delta=0.8, resistance=1.5)
    L.add_edge("B", "G", delta=0.8, resistance=1.5)
    return L


# ═══════════════════════════════════════════════
# Test: Edge Fingerprint Extraction
# ═══════════════════════════════════════════════

class TestEdgeFingerprint:
    """Fingerprint extraction from historization data."""

    def test_fresh_edge_fingerprint(self):
        """Fresh edge has quality=0, load=0, inertia=1.0 (no dampening)."""
        L = _build_simple_domain()
        fp = edge_fingerprint(Edge("A", "B"), L, "dom")
        assert fp.quality == 0.0
        assert fp.load == 0.0
        assert fp.inertia == 1.0
        assert fp.domain == "dom"
        assert fp.edge == Edge("A", "B")

    def test_success_inscribed_fingerprint(self):
        """After SUCCESS inscriptions, quality > 0, load > 0."""
        L = _build_simple_domain()
        _inscribe(L, ["A", "B"], Outcome.SUCCESS, n=10)
        fp = edge_fingerprint(Edge("A", "B"), L, "dom")
        assert fp.quality > 0.0
        assert fp.load > 0.0
        assert fp.inertia < 1.0  # dampening kicks in

    def test_failure_inscribed_fingerprint(self):
        """After FAILURE inscriptions, quality < 0."""
        L = _build_simple_domain()
        _inscribe(L, ["A", "B"], Outcome.FAILURE, n=10)
        fp = edge_fingerprint(Edge("A", "B"), L, "dom")
        assert fp.quality < 0.0

    def test_domain_fingerprints_count(self):
        """domain_fingerprints returns one fingerprint per edge."""
        L = _build_simple_domain()
        fps = domain_fingerprints(L, "test")
        assert len(fps) == 3  # A→B, B→C, C→GOAL
        assert all(f.domain == "test" for f in fps)

    def test_fingerprint_frozen(self):
        """EdgeFingerprint is immutable (frozen dataclass)."""
        L = _build_simple_domain()
        fp = edge_fingerprint(Edge("A", "B"), L, "dom")
        with pytest.raises(AttributeError):
            fp.quality = 0.5  # type: ignore


# ═══════════════════════════════════════════════
# Test: Fingerprint Distance Metric
# ═══════════════════════════════════════════════

class TestFingerprintDistance:
    """Distance metric properties."""

    def test_identical_fingerprints_zero_distance(self):
        """Same fingerprint → distance = 0."""
        fp = EdgeFingerprint("A", Edge("x", "y"), 0.5, 10.0, 0.8)
        assert fingerprint_distance(fp, fp) == 0.0

    def test_symmetry(self):
        """d(a, b) = d(b, a)."""
        fa = EdgeFingerprint("A", Edge("x", "y"), 0.5, 10.0, 0.8)
        fb = EdgeFingerprint("B", Edge("p", "q"), -0.3, 5.0, 0.9)
        assert fingerprint_distance(fa, fb) == fingerprint_distance(fb, fa)

    def test_triangle_inequality(self):
        """d(a, c) ≤ d(a, b) + d(b, c)."""
        fa = EdgeFingerprint("A", Edge("a", "b"), 0.8, 20.0, 0.6)
        fb = EdgeFingerprint("B", Edge("c", "d"), 0.0, 5.0, 0.9)
        fc = EdgeFingerprint("C", Edge("e", "f"), -0.5, 0.0, 1.0)
        d_ac = fingerprint_distance(fa, fc)
        d_ab = fingerprint_distance(fa, fb)
        d_bc = fingerprint_distance(fb, fc)
        assert d_ac <= d_ab + d_bc + 1e-10

    def test_quality_dominates_when_opposite(self):
        """Opposite quality (±0.9) should produce large distance."""
        fa = EdgeFingerprint("A", Edge("x", "y"), 0.9, 10.0, 0.8)
        fb = EdgeFingerprint("B", Edge("p", "q"), -0.9, 10.0, 0.8)
        d = fingerprint_distance(fa, fb)
        assert d > 1.5  # quality diff alone is 1.8

    def test_load_normalized_by_sigmoid(self):
        """Load 100 and load 200 are much closer than load 0 and load 5."""
        fp_0 = EdgeFingerprint("A", Edge("x", "y"), 0.0, 0.0, 1.0)
        fp_5 = EdgeFingerprint("A", Edge("x", "y"), 0.0, 5.0, 1.0)
        fp_100 = EdgeFingerprint("A", Edge("x", "y"), 0.0, 100.0, 1.0)
        fp_200 = EdgeFingerprint("A", Edge("x", "y"), 0.0, 200.0, 1.0)

        d_05 = fingerprint_distance(fp_0, fp_5)
        d_100_200 = fingerprint_distance(fp_100, fp_200)
        assert d_05 > d_100_200  # sigmoid compresses large values

    def test_non_negative(self):
        """Distance is always ≥ 0."""
        fa = EdgeFingerprint("A", Edge("x", "y"), -1.0, 0.0, 0.5)
        fb = EdgeFingerprint("B", Edge("p", "q"), 1.0, 100.0, 1.0)
        assert fingerprint_distance(fa, fb) >= 0.0


# ═══════════════════════════════════════════════
# Test: Equivalence Detection
# ═══════════════════════════════════════════════

class TestEquivalenceDetection:
    """Finding functional equivalences across domains."""

    def test_find_equivalences_empty_domain(self):
        """Empty domain → no equivalences."""
        L1 = Landscape()
        L2 = _build_simple_domain()
        eqs = find_equivalences(L1, L2)
        assert eqs == []

    def test_find_equivalences_both_fresh(self):
        """Two fresh domains: all edges have identical fingerprints (0, 0, 1.0)."""
        L1 = _build_simple_domain()
        L2 = _build_simple_domain()
        eqs = find_equivalences(L1, L2, domain_a="D1", domain_b="D2")
        # All pairs have distance 0 — all are equivalences
        assert len(eqs) > 0
        assert all(eq.distance == 0.0 for eq in eqs)

    def test_equivalences_sorted_by_distance(self):
        """Returned equivalences are sorted ascending by distance."""
        L1 = _build_simple_domain()
        L2 = _build_parallel_domain()
        # Inscribe differently to create varied fingerprints
        _inscribe(L1, ["A", "B"], Outcome.SUCCESS, 10)
        _inscribe(L2, ["S", "A"], Outcome.SUCCESS, 10)
        _inscribe(L2, ["S", "B"], Outcome.FAILURE, 10)

        eqs = find_equivalences(L1, L2, quantile=1.0)  # keep all
        for i in range(len(eqs) - 1):
            assert eqs[i].distance <= eqs[i + 1].distance

    def test_quantile_filters(self):
        """Lower quantile → fewer equivalences."""
        L1 = _build_simple_domain()
        L2 = _build_parallel_domain()
        _inscribe(L1, ["A", "B", "C"], Outcome.SUCCESS, 5)
        _inscribe(L2, ["S", "A", "G"], Outcome.SUCCESS, 5)
        _inscribe(L2, ["S", "B"], Outcome.FAILURE, 5)

        all_eqs = find_equivalences(L1, L2, quantile=1.0)
        few_eqs = find_equivalences(L1, L2, quantile=0.1)
        assert len(few_eqs) <= len(all_eqs)
        assert len(few_eqs) >= 1  # at least 1

    def test_max_results_cap(self):
        """max_results limits output."""
        L1 = _build_simple_domain()
        L2 = _build_simple_domain()
        eqs = find_equivalences(L1, L2, quantile=1.0, max_results=2)
        assert len(eqs) == 2

    def test_equivalence_confidence(self):
        """Confidence is 1 - distance, clamped to [0, 1]."""
        fp_a = EdgeFingerprint("A", Edge("x", "y"), 0.5, 10.0, 0.8)
        fp_b = EdgeFingerprint("B", Edge("p", "q"), 0.5, 10.0, 0.8)
        eq = Equivalence(fp_a, fp_b, distance=0.0)
        assert eq.confidence == 1.0

        eq2 = Equivalence(fp_a, fp_b, distance=0.3)
        assert abs(eq2.confidence - 0.7) < 1e-10

    def test_equivalence_properties(self):
        """Equivalence exposes domain/edge convenience properties."""
        fp_a = EdgeFingerprint("dom_X", Edge("a", "b"), 0.0, 0.0, 1.0)
        fp_b = EdgeFingerprint("dom_Y", Edge("c", "d"), 0.0, 0.0, 1.0)
        eq = Equivalence(fp_a, fp_b, distance=0.0)
        assert eq.domain_a == "dom_X"
        assert eq.domain_b == "dom_Y"
        assert eq.edge_a == Edge("a", "b")
        assert eq.edge_b == Edge("c", "d")


# ═══════════════════════════════════════════════
# Test: Dream Readiness
# ═══════════════════════════════════════════════

class TestDreamReadiness:
    """Data-driven trigger for dream cycle."""

    def test_fresh_domain_readiness_high(self):
        """Fresh domain has inertia=1.0 everywhere → readiness=1.0.
        (No dampening because no contradictory history.
         But also no data — this is the cold-start edge case.)"""
        L = _build_simple_domain()
        r = dream_readiness(L)
        assert r == 1.0

    def test_empty_domain_readiness_zero(self):
        """Domain with no edges → 0.0 (cannot dream about nothing)."""
        L = Landscape()
        assert dream_readiness(L) == 0.0

    def test_inscribed_domain_readiness_below_fresh(self):
        """After inscription, inertia goes down → readiness decreases."""
        L = _build_simple_domain()
        # Mixed signals: some SUCCESS, some FAILURE → confused → low inertia
        _inscribe(L, ["A", "B"], Outcome.SUCCESS, 5)
        _inscribe(L, ["A", "B"], Outcome.FAILURE, 5)
        r = dream_readiness(L)
        assert r < 1.0

    def test_pure_success_still_dampened(self):
        """Consistent SUCCESS still dampens inertia (high load)."""
        L = _build_simple_domain()
        _inscribe(L, ["A", "B", "C", "GOAL"], Outcome.SUCCESS, 20)
        r = dream_readiness(L)
        # Inertia = 1 - α·(m/(m+μ))·(1-|q|)
        # With pure success: |q|→1 so (1-|q|)→0, inertia stays near 1.0
        assert r > 0.8

    def test_is_dream_ready_threshold(self):
        """is_dream_ready checks against threshold."""
        L = _build_simple_domain()
        assert is_dream_ready(L, threshold=0.9)
        assert not is_dream_ready(L, threshold=1.1)  # impossible to reach


# ═══════════════════════════════════════════════
# Test: Dream Landscape Construction
# ═══════════════════════════════════════════════

class TestDreamLandscape:
    """Building a navigable Dream Landscape from equivalences."""

    def test_empty_equivalences(self):
        """No equivalences → empty landscape."""
        dl = build_dream_landscape([])
        assert len(dl.states) == 0
        assert len(dl.edges) == 0

    def test_single_equivalence_creates_bidirectional(self):
        """One equivalence → 2 states, 2 edges (bidirectional)."""
        fp_a = EdgeFingerprint("D1", Edge("a", "b"), 0.5, 10.0, 0.8)
        fp_b = EdgeFingerprint("D2", Edge("x", "y"), 0.5, 10.0, 0.8)
        eq = Equivalence(fp_a, fp_b, distance=0.1)

        dl = build_dream_landscape([eq])
        assert len(dl.states) == 2
        assert len(dl.edges) == 2

    def test_state_encoding(self):
        """States are encoded as 'domain:src→tgt'."""
        fp = EdgeFingerprint("Chess", Edge("open", "develop"), 0.3, 5.0, 0.9)
        assert _equivalence_state(fp) == "Chess:open→develop"

    def test_resistance_scales_with_confidence(self):
        """Low confidence → high R₀ (speculative = expensive)."""
        fp_a = EdgeFingerprint("D1", Edge("a", "b"), 0.5, 10.0, 0.8)
        fp_b = EdgeFingerprint("D2", Edge("x", "y"), 0.5, 10.0, 0.8)

        eq_close = Equivalence(fp_a, fp_b, distance=0.1)  # conf=0.9
        eq_far = Equivalence(fp_a, fp_b, distance=0.8)    # conf=0.2

        dl_close = build_dream_landscape([eq_close])
        dl_far = build_dream_landscape([eq_far])

        r0_close = dl_close._R0[Edge("D1:a→b", "D2:x→y")]
        r0_far = dl_far._R0[Edge("D1:a→b", "D2:x→y")]
        assert r0_far > r0_close  # farther = more expensive

    def test_dream_landscape_is_valid_e0(self):
        """Dream Landscape is a valid E₀ Landscape — can historize."""
        fp_a = EdgeFingerprint("D1", Edge("a", "b"), 0.5, 10.0, 0.8)
        fp_b = EdgeFingerprint("D2", Edge("x", "y"), 0.5, 10.0, 0.8)
        eq = Equivalence(fp_a, fp_b, distance=0.1)

        dl = build_dream_landscape([eq])
        e = Edge("D1:a→b", "D2:x→y")
        dl.historization.update(e, Outcome.SUCCESS)
        assert dl.historization.trace_load(e) > 0

    def test_multiple_equivalences_share_states(self):
        """If an edge appears in multiple equivalences, state is not duplicated."""
        fp_a = EdgeFingerprint("D1", Edge("a", "b"), 0.5, 10.0, 0.8)
        fp_b = EdgeFingerprint("D2", Edge("x", "y"), 0.5, 10.0, 0.8)
        fp_c = EdgeFingerprint("D3", Edge("p", "q"), 0.5, 10.0, 0.8)

        eq1 = Equivalence(fp_a, fp_b, distance=0.1)
        eq2 = Equivalence(fp_a, fp_c, distance=0.2)

        dl = build_dream_landscape([eq1, eq2])
        assert len(dl.states) == 3  # D1:a→b, D2:x→y, D3:p→q
        assert len(dl.edges) == 4   # 2 per equivalence


# ═══════════════════════════════════════════════
# Test: P1 — Functional Equivalence is Detectable
# ═══════════════════════════════════════════════

class TestP1FunctionalEquivalence:
    """Prediction P1: edges with the same navigational role in different
    domains should have close fingerprints."""

    def test_same_pattern_detected(self):
        """Two domains with the same success-path pattern: the success edges
        should be closer to each other than to failure edges."""
        # Domain A: S→A→G (success path), S→B→G (failure path)
        La = Landscape()
        La.add_edge("S", "A", delta=0.3, resistance=0.5)
        La.add_edge("A", "G", delta=0.3, resistance=0.5)
        La.add_edge("S", "B", delta=0.3, resistance=0.5)
        La.add_edge("B", "G", delta=0.3, resistance=0.5)

        # Domain B: X→P→Z (success path), X→Q→Z (failure path)
        Lb = Landscape()
        Lb.add_edge("X", "P", delta=0.3, resistance=0.5)
        Lb.add_edge("P", "Z", delta=0.3, resistance=0.5)
        Lb.add_edge("X", "Q", delta=0.3, resistance=0.5)
        Lb.add_edge("Q", "Z", delta=0.3, resistance=0.5)

        # Inscribe: success path in both, failure path in both
        _inscribe(La, ["S", "A", "G"], Outcome.SUCCESS, 10)
        _inscribe(La, ["S", "B", "G"], Outcome.FAILURE, 10)
        _inscribe(Lb, ["X", "P", "Z"], Outcome.SUCCESS, 10)
        _inscribe(Lb, ["X", "Q", "Z"], Outcome.FAILURE, 10)

        # The closest match for A's success edge (S→A) should be B's success edge (X→P)
        eqs = find_equivalences(La, Lb, domain_a="A", domain_b="B", quantile=1.0)

        # Find the top equivalence
        best = eqs[0]
        # It should pair success-with-success or failure-with-failure
        a_edge_is_success = best.edge_a in [Edge("S", "A"), Edge("A", "G")]
        b_edge_is_success = best.edge_b in [Edge("X", "P"), Edge("P", "Z")]
        a_edge_is_failure = best.edge_a in [Edge("S", "B"), Edge("B", "G")]
        b_edge_is_failure = best.edge_b in [Edge("X", "Q"), Edge("Q", "Z")]

        # Best match should be same-role pairing
        assert (a_edge_is_success and b_edge_is_success) or \
               (a_edge_is_failure and b_edge_is_failure)

    def test_different_domains_same_inscription(self):
        """Run E0Controller on two structurally different domains.
        Edges that succeed in both should have similar fingerprints."""
        d1 = build_d1_linear_chain()
        d2 = build_d2_diamond()

        ctrl1 = E0Controller(d1.landscape, d1.execute_fn)
        ctrl1.run(start=d1.start, goal=d1.goal, max_cycles=30)

        ctrl2 = E0Controller(d2.landscape, d2.execute_fn)
        ctrl2.run(start=d2.start, goal=d2.goal, max_cycles=30)

        eqs = find_equivalences(
            d1.landscape, d2.landscape,
            domain_a="D1", domain_b="D2",
            quantile=0.2,
        )
        # Should find some equivalences (both domains have successful edges)
        assert len(eqs) > 0
        # Best equivalence should have low distance
        assert eqs[0].distance < 0.5


# ═══════════════════════════════════════════════
# Test: P5 — Domain Order Does Not Matter
# ═══════════════════════════════════════════════

class TestP5DomainOrder:
    """Prediction P5: equivalence detection is order-invariant."""

    def test_order_invariant(self):
        """find_equivalences(A, B) ≈ find_equivalences(B, A) up to direction."""
        La = _build_simple_domain()
        Lb = _build_parallel_domain()
        _inscribe(La, ["A", "B", "C", "GOAL"], Outcome.SUCCESS, 8)
        _inscribe(Lb, ["S", "A", "G"], Outcome.SUCCESS, 8)
        _inscribe(Lb, ["S", "B", "G"], Outcome.FAILURE, 8)

        eqs_ab = find_equivalences(La, Lb, domain_a="A", domain_b="B", quantile=1.0)
        eqs_ba = find_equivalences(Lb, La, domain_a="B", domain_b="A", quantile=1.0)

        # Same number of equivalences
        assert len(eqs_ab) == len(eqs_ba)

        # Same distances (sorted)
        dists_ab = sorted(eq.distance for eq in eqs_ab)
        dists_ba = sorted(eq.distance for eq in eqs_ba)
        for d1, d2 in zip(dists_ab, dists_ba):
            assert abs(d1 - d2) < 1e-10
