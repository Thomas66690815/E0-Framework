"""Tests for Unified Structural Resonance (C260).

C260: find_structural_resonance() works on arbitrary landscape subsets.
Dream uses it intra-landscape (community ↔ community).
Coupling uses it inter-landscape (universe ↔ universe).
Same algorithm, different scale.

Key claims tested:
  1. StructuralResonance dataclass fields and properties
  2. Identical landscapes → perfect resonance
  3. Disjoint landscapes → zero resonance
  4. Empty landscapes → degenerate resonance
  5. dream_compatibility() delegated to find_structural_resonance()
  6. CouplingRouter.resonance() uses unified function
  7. Scale-invariance: same function at community and universe scale
  8. Resonance score monotonicity: more similar → higher score
"""

import math
import pytest

from e0_controller.landscape import Landscape
from e0_controller.multiverse import Universe
from e0_controller.primitives import Edge, Outcome
from e0_controller.dream_mode import (
    StructuralResonance,
    find_structural_resonance,
    dream_compatibility,
    is_dream_compatible,
    NodeEquivalence,
)
from e0_controller.coupling_router import (
    CouplingRouter,
    structural_distance,
)


# ═══════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════

def _build_chain(prefix: str, n: int = 3) -> Landscape:
    """Build a simple chain: prefix_0 → prefix_1 → ... → prefix_{n-1}."""
    L = Landscape()
    for i in range(n - 1):
        L.add_edge(f"{prefix}_{i}", f"{prefix}_{i+1}", delta=0.5, resistance=1.0)
    return L


def _build_diamond(prefix: str) -> Landscape:
    """S → A → G, S → B → G diamond topology."""
    L = Landscape()
    L.add_edge(f"{prefix}_S", f"{prefix}_A", delta=0.3, resistance=0.5)
    L.add_edge(f"{prefix}_A", f"{prefix}_G", delta=0.3, resistance=0.5)
    L.add_edge(f"{prefix}_S", f"{prefix}_B", delta=0.8, resistance=1.5)
    L.add_edge(f"{prefix}_B", f"{prefix}_G", delta=0.8, resistance=1.5)
    return L


def _inscribe(landscape: Landscape, path: list[str], outcome: Outcome, n: int = 1):
    """Inscribe a path into a landscape's historization n times."""
    for _ in range(n):
        for i in range(len(path) - 1):
            edge = Edge(path[i], path[i + 1])
            landscape.historization.update(edge, outcome)


def _make_universe(name: str, states: list, edges: list) -> Universe:
    """Build a universe with the given topology."""
    L = Landscape()
    for s in states:
        pass  # States appear implicitly via edges
    for s, t, d, r in edges:
        L.add_edge(s, t, delta=d, resistance=r)
    return Universe(name=name, landscape=L, start="start", goal="goal",
                    execute_fn=lambda s, t: Outcome.SUCCESS)


# ═══════════════════════════════════════════════
# StructuralResonance dataclass
# ═══════════════════════════════════════════════

class TestStructuralResonanceDataclass:
    """C260: StructuralResonance fields and properties."""

    def test_fields_present(self):
        sr = StructuralResonance(
            node_equivalences=(),
            compatibility=0.3,
            structural_distance=0.2,
            resonance_score=0.7,
            nodes_a=4,
            nodes_b=4,
            matched_nodes=4,
        )
        assert sr.compatibility == 0.3
        assert sr.structural_distance == 0.2
        assert sr.resonance_score == 0.7
        assert sr.nodes_a == 4
        assert sr.nodes_b == 4
        assert sr.matched_nodes == 4

    def test_is_compatible_below_threshold(self):
        sr = StructuralResonance(
            node_equivalences=(), compatibility=0.3,
            structural_distance=0.0, resonance_score=0.7,
            nodes_a=3, nodes_b=3, matched_nodes=3,
        )
        assert sr.is_compatible is True

    def test_is_compatible_above_threshold(self):
        sr = StructuralResonance(
            node_equivalences=(), compatibility=0.7,
            structural_distance=0.5, resonance_score=0.2,
            nodes_a=3, nodes_b=3, matched_nodes=3,
        )
        assert sr.is_compatible is False

    def test_is_compatible_at_boundary(self):
        sr = StructuralResonance(
            node_equivalences=(), compatibility=0.5,
            structural_distance=0.0, resonance_score=0.5,
            nodes_a=3, nodes_b=3, matched_nodes=3,
        )
        assert sr.is_compatible is False  # not strictly < 0.5

    def test_top_matches_returns_first_five(self):
        eqs = tuple(
            NodeEquivalence(fp_a=f"a{i}", fp_b=f"b{i}", distance=i * 0.1)
            for i in range(8)
        )
        sr = StructuralResonance(
            node_equivalences=eqs, compatibility=0.3,
            structural_distance=0.2, resonance_score=0.7,
            nodes_a=8, nodes_b=8, matched_nodes=8,
        )
        assert len(sr.top_matches) == 5
        assert sr.top_matches[0].distance == 0.0

    def test_frozen(self):
        sr = StructuralResonance(
            node_equivalences=(), compatibility=0.3,
            structural_distance=0.2, resonance_score=0.7,
            nodes_a=3, nodes_b=3, matched_nodes=3,
        )
        with pytest.raises(AttributeError):
            sr.compatibility = 0.9


# ═══════════════════════════════════════════════
# find_structural_resonance — basic cases
# ═══════════════════════════════════════════════

class TestFindStructuralResonance:
    """C260: Core function on arbitrary landscape pairs."""

    def test_identical_landscapes_high_resonance(self):
        """Same topology → resonance_score near 1.0."""
        L = _build_chain("x", 4)
        sr = find_structural_resonance(L, L)
        assert sr.resonance_score > 0.8
        assert sr.compatibility < 0.3
        assert sr.structural_distance == 0.0  # same state set
        assert sr.is_compatible is True
        assert sr.nodes_a == sr.nodes_b == 4
        assert sr.matched_nodes == 4

    def test_isomorphic_landscapes_high_resonance(self):
        """Same topology, different names → high resonance from WL match."""
        L_a = _build_chain("domain1", 4)
        L_b = _build_chain("domain2", 4)
        sr = find_structural_resonance(L_a, L_b, domain_a="d1", domain_b="d2")
        # WL fingerprints should match well (same topology)
        assert sr.resonance_score > 0.3
        # But structural_distance is 1.0 (disjoint state names)
        assert sr.structural_distance == 1.0
        assert sr.matched_nodes == 4

    def test_disjoint_topology_low_resonance(self):
        """Completely different topology → low resonance."""
        L_a = _build_chain("x", 3)  # linear chain
        L_b = Landscape()
        # Star topology: center connects to 5 leaves
        for i in range(5):
            L_b.add_edge("center", f"leaf_{i}", delta=0.5, resistance=1.0)
        sr = find_structural_resonance(L_a, L_b)
        # Different topology + different states → low resonance
        assert sr.resonance_score < 0.5

    def test_empty_landscape_a(self):
        """Empty first landscape → degenerate result."""
        L_a = Landscape()
        L_b = _build_chain("x", 3)
        sr = find_structural_resonance(L_a, L_b)
        assert sr.resonance_score == 0.0
        assert sr.compatibility == float("inf")
        assert sr.structural_distance == 1.0
        assert sr.nodes_a == 0
        assert sr.nodes_b == 3
        assert sr.matched_nodes == 0

    def test_empty_landscape_b(self):
        """Empty second landscape → degenerate result."""
        L_a = _build_chain("x", 3)
        L_b = Landscape()
        sr = find_structural_resonance(L_a, L_b)
        assert sr.resonance_score == 0.0
        assert sr.matched_nodes == 0

    def test_both_empty(self):
        """Both empty → degenerate result."""
        sr = find_structural_resonance(Landscape(), Landscape())
        assert sr.resonance_score == 0.0
        assert sr.nodes_a == 0
        assert sr.nodes_b == 0

    def test_single_edge_landscapes(self):
        """Minimal case: two single-edge landscapes."""
        L_a = Landscape()
        L_a.add_edge("a", "b", delta=0.5, resistance=1.0)
        L_b = Landscape()
        L_b.add_edge("c", "d", delta=0.5, resistance=1.0)
        sr = find_structural_resonance(L_a, L_b)
        assert sr.nodes_a == 2
        assert sr.nodes_b == 2
        assert sr.matched_nodes == 2
        assert 0.0 <= sr.resonance_score <= 1.0

    def test_asymmetric_sizes(self):
        """Different-sized landscapes → matched_nodes = min(n_a, n_b)."""
        L_a = _build_chain("x", 3)  # 3 nodes
        L_b = _build_chain("y", 6)  # 6 nodes
        sr = find_structural_resonance(L_a, L_b)
        assert sr.nodes_a == 3
        assert sr.nodes_b == 6
        assert sr.matched_nodes == 3  # min(3, 6)

    def test_resonance_score_in_unit_interval(self):
        """Resonance score is always in [0.0, 1.0]."""
        for n_a, n_b in [(3, 3), (4, 6), (2, 8)]:
            L_a = _build_chain("a", n_a)
            L_b = _build_chain("b", n_b)
            sr = find_structural_resonance(L_a, L_b)
            assert 0.0 <= sr.resonance_score <= 1.0, (
                f"Score {sr.resonance_score} out of bounds "
                f"for {n_a}×{n_b}"
            )


# ═══════════════════════════════════════════════
# Backward compatibility
# ═══════════════════════════════════════════════

class TestBackwardCompatibility:
    """C260: dream_compatibility() still works via delegation."""

    def test_dream_compatibility_returns_float(self):
        L = _build_chain("x", 4)
        val = dream_compatibility(L, L)
        assert isinstance(val, float)
        assert val < 0.5  # identical topology

    def test_dream_compatibility_empty_returns_inf(self):
        assert dream_compatibility(Landscape(), _build_chain("x", 3)) == float("inf")
        assert dream_compatibility(_build_chain("x", 3), Landscape()) == float("inf")

    def test_is_dream_compatible_delegates(self):
        L_a = _build_chain("a", 4)
        L_b = _build_chain("b", 4)
        # Isomorphic topologies should be compatible
        result = is_dream_compatible(L_a, L_b)
        assert isinstance(result, bool)

    def test_dream_compatibility_matches_resonance(self):
        """dream_compatibility() == find_structural_resonance().compatibility."""
        L_a = _build_diamond("d1")
        L_b = _build_diamond("d2")
        compat = dream_compatibility(L_a, L_b)
        sr = find_structural_resonance(L_a, L_b)
        assert compat == sr.compatibility


# ═══════════════════════════════════════════════
# CouplingRouter.resonance()
# ═══════════════════════════════════════════════

class TestCouplingRouterResonance:
    """C260: CouplingRouter.resonance() uses unified function."""

    def _make_router(self):
        u1 = _make_universe("alpha", [],
                            [("a", "b", 0.5, 1.0), ("b", "c", 0.5, 1.0)])
        u2 = _make_universe("beta", [],
                            [("x", "y", 0.5, 1.0), ("y", "z", 0.5, 1.0)])
        u3 = _make_universe("gamma", [],
                            [("a", "b", 0.5, 1.0), ("b", "c", 0.5, 1.0),
                             ("c", "d", 0.5, 1.0)])
        return CouplingRouter([u1, u2, u3])

    def test_resonance_returns_structural_resonance(self):
        router = self._make_router()
        sr = router.resonance("alpha", "beta")
        assert isinstance(sr, StructuralResonance)

    def test_resonance_self_comparison(self):
        """Same universe → high resonance."""
        router = self._make_router()
        sr = router.resonance("alpha", "alpha")
        assert sr.resonance_score > 0.8
        assert sr.structural_distance == 0.0

    def test_resonance_isomorphic_universes(self):
        """Isomorphic universes (alpha ≅ beta) → decent resonance."""
        router = self._make_router()
        sr = router.resonance("alpha", "beta")
        assert sr.matched_nodes == 3

    def test_resonance_asymmetric_sizes(self):
        """alpha (3 nodes) vs gamma (4 nodes) → 3 matched."""
        router = self._make_router()
        sr = router.resonance("alpha", "gamma")
        assert sr.nodes_a == 3
        assert sr.nodes_b == 4
        assert sr.matched_nodes == 3

    def test_resonance_consistent_with_structural_distance(self):
        """Router.resonance().structural_distance ≈ structural_distance()."""
        router = self._make_router()
        sr = router.resonance("alpha", "beta")
        sd = structural_distance(
            router.universes["alpha"], router.universes["beta"]
        )
        assert sr.structural_distance == pytest.approx(sd)


# ═══════════════════════════════════════════════
# Scale invariance
# ═══════════════════════════════════════════════

class TestScaleInvariance:
    """C260: Same function works at different scales (community vs universe)."""

    def _build_community_landscapes(self):
        """Simulate two community sub-landscapes from a partitioned landscape."""
        # Community 0: chain A→B→C
        c0 = Landscape()
        c0.add_edge("A", "B", delta=0.5, resistance=1.0)
        c0.add_edge("B", "C", delta=0.5, resistance=1.0)

        # Community 1: chain X→Y→Z (isomorphic to community 0)
        c1 = Landscape()
        c1.add_edge("X", "Y", delta=0.5, resistance=1.0)
        c1.add_edge("Y", "Z", delta=0.5, resistance=1.0)

        return c0, c1

    def _build_universe_landscapes(self):
        """Simulate two full universe landscapes."""
        # Universe A: chain a→b→c
        u_a = Landscape()
        u_a.add_edge("a", "b", delta=0.5, resistance=1.0)
        u_a.add_edge("b", "c", delta=0.5, resistance=1.0)

        # Universe B: chain x→y→z (isomorphic to A)
        u_b = Landscape()
        u_b.add_edge("x", "y", delta=0.5, resistance=1.0)
        u_b.add_edge("y", "z", delta=0.5, resistance=1.0)

        return u_a, u_b

    def test_same_function_community_and_universe(self):
        """find_structural_resonance() works at both scales."""
        c0, c1 = self._build_community_landscapes()
        u_a, u_b = self._build_universe_landscapes()

        # Community-level (intra-landscape)
        sr_community = find_structural_resonance(c0, c1)
        # Universe-level (inter-landscape)
        sr_universe = find_structural_resonance(u_a, u_b)

        # Both produce valid StructuralResonance objects
        assert isinstance(sr_community, StructuralResonance)
        assert isinstance(sr_universe, StructuralResonance)

        # Both have same number of matched nodes (identical topology)
        assert sr_community.matched_nodes == sr_universe.matched_nodes == 3

    def test_scale_invariance_ranking(self):
        """Resonance ranking is consistent across scales.

        If community_A ≅ community_B and community_A ≇ community_C,
        then at universe scale: universe_A ≅ universe_B should also rank higher
        than universe_A ≅ universe_C.
        """
        # Similar pairs (chains)
        chain_a = _build_chain("a", 4)
        chain_b = _build_chain("b", 4)

        # Dissimilar pair (chain vs star)
        star = Landscape()
        for i in range(5):
            star.add_edge("hub", f"spoke_{i}", delta=0.5, resistance=1.0)

        sr_similar = find_structural_resonance(chain_a, chain_b)
        sr_dissimilar = find_structural_resonance(chain_a, star)

        # Ranking preserved: similar pair has higher resonance
        assert sr_similar.resonance_score > sr_dissimilar.resonance_score

    def test_diamond_isomorphism_detected(self):
        """Isomorphic diamonds at any scale produce high resonance."""
        d1 = _build_diamond("d1")
        d2 = _build_diamond("d2")
        sr = find_structural_resonance(d1, d2)
        assert sr.matched_nodes == 4
        assert sr.is_compatible is True

    def test_chain_vs_diamond_distinguishable(self):
        """Different topologies produce lower resonance than isomorphic ones."""
        chain = _build_chain("c", 4)
        diamond = _build_diamond("d")

        sr_different = find_structural_resonance(chain, diamond)

        # Compare with same-topology
        chain2 = _build_chain("c2", 4)
        sr_same = find_structural_resonance(chain, chain2)

        # Same topology should have higher resonance
        assert sr_same.resonance_score >= sr_different.resonance_score


# ═══════════════════════════════════════════════
# Monotonicity
# ═══════════════════════════════════════════════

class TestResonanceMonotonicity:
    """C260: More similar landscapes → higher resonance score."""

    def test_resonance_ordering(self):
        """Self > isomorphic > different topology."""
        chain = _build_chain("c", 4)
        chain_iso = _build_chain("d", 4)
        star = Landscape()
        for i in range(6):
            star.add_edge("center", f"leaf_{i}", delta=0.5, resistance=1.0)

        sr_self = find_structural_resonance(chain, chain)
        sr_iso = find_structural_resonance(chain, chain_iso)
        sr_diff = find_structural_resonance(chain, star)

        # Self comparison should have highest resonance
        assert sr_self.resonance_score >= sr_iso.resonance_score
        # Isomorphic should beat different topology
        assert sr_iso.resonance_score >= sr_diff.resonance_score

    def test_compatibility_ordering(self):
        """More similar → lower compatibility distance."""
        chain = _build_chain("c", 4)
        chain_iso = _build_chain("d", 4)
        star = Landscape()
        for i in range(6):
            star.add_edge("center", f"leaf_{i}", delta=0.5, resistance=1.0)

        compat_self = find_structural_resonance(chain, chain).compatibility
        compat_iso = find_structural_resonance(chain, chain_iso).compatibility
        compat_diff = find_structural_resonance(chain, star).compatibility

        assert compat_self <= compat_iso
        assert compat_iso <= compat_diff
