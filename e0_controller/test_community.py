"""
Tests for C255: Community Detection from R_eff
================================================
Claim: Communities emerge from Historization, not from imposed labels.

Test structure:
    TestCommunityBasics    — API contract, edge cases
    TestCommunityTopology  — connected components, clusters
    TestCommunityHistorization — R_eff drives community formation
    TestCommunityProperties — determinism, cold start, self-similarity
"""

import math
from e0_controller.landscape import Landscape
from e0_controller.community import detect_communities
from e0_controller.primitives import Edge, Outcome
from e0_controller.historization import Historization


# ── Helpers ──────────────────────────────────────────────────────

def _make_two_clusters(inter_R: float = 5.0, intra_R: float = 0.5):
    """Two tight clusters (A1-A3, B1-B3) with configurable inter-cluster R."""
    la = Landscape()
    # Cluster A: low internal resistance
    for a in ["A1", "A2", "A3"]:
        for b in ["A1", "A2", "A3"]:
            if a != b:
                la.add_edge(a, b, delta=0.5, resistance=intra_R)
    # Cluster B: low internal resistance
    for a in ["B1", "B2", "B3"]:
        for b in ["B1", "B2", "B3"]:
            if a != b:
                la.add_edge(a, b, delta=0.5, resistance=intra_R)
    # Inter-cluster: high resistance bridge
    la.add_edge("A1", "B1", delta=0.5, resistance=inter_R)
    la.add_edge("B1", "A1", delta=0.5, resistance=inter_R)
    return la


def _historize_edge(landscape, source, target, outcome, n=1):
    """Record n outcomes on an edge."""
    edge = Edge(source, target)
    for _ in range(n):
        landscape.historization.update(edge, outcome)


def _historize_edges_interleaved(landscape, pairs, outcome, n=1):
    """Record n rounds of outcomes on multiple edges (round-robin).

    Avoids the decay problem where sequential batch updates cause
    early-updated edges to decay by the time later edges are processed.
    """
    edges = [Edge(s, t) for s, t in pairs]
    for _ in range(n):
        for edge in edges:
            landscape.historization.update(edge, outcome)


# ── TestCommunityBasics ──────────────────────────────────────────

class TestCommunityBasics:
    """API contract and edge cases."""

    def test_empty_landscape(self):
        """Empty landscape → empty list."""
        la = Landscape()
        result = detect_communities(la)
        assert result == []

    def test_single_node_no_edges(self):
        """Single isolated node → one singleton community."""
        la = Landscape()
        la.add_state("X")
        result = detect_communities(la)
        assert len(result) == 1
        assert result[0] == {"X"}

    def test_two_connected_nodes(self):
        """Two connected nodes → one community."""
        la = Landscape()
        la.add_edge("A", "B", delta=0.5, resistance=1.0)
        result = detect_communities(la)
        assert len(result) == 1
        assert result[0] == {"A", "B"}

    def test_return_type(self):
        """Returns List[Set[str]]."""
        la = Landscape()
        la.add_edge("A", "B", delta=0.5, resistance=1.0)
        result = detect_communities(la)
        assert isinstance(result, list)
        assert all(isinstance(c, set) for c in result)
        assert all(isinstance(n, str) for c in result for n in c)

    def test_all_nodes_covered(self):
        """Every state in the landscape appears in exactly one community."""
        la = _make_two_clusters()
        result = detect_communities(la)
        all_nodes = set()
        for community in result:
            assert not (all_nodes & community), "Node in multiple communities"
            all_nodes |= community
        assert all_nodes == la.states

    def test_max_iterations_respected(self):
        """max_iterations=0 → each node stays in its own community."""
        la = Landscape()
        la.add_edge("A", "B", delta=0.5, resistance=1.0)
        result = detect_communities(la, max_iterations=0)
        # No propagation → each node is its own community
        assert len(result) == 2


# ── TestCommunityTopology ────────────────────────────────────────

class TestCommunityTopology:
    """Communities match topological structure."""

    def test_disconnected_components(self):
        """Disconnected components → separate communities."""
        la = Landscape()
        la.add_edge("A1", "A2", delta=0.5, resistance=1.0)
        la.add_edge("B1", "B2", delta=0.5, resistance=1.0)
        result = detect_communities(la)
        assert len(result) == 2
        assert {"A1", "A2"} in result
        assert {"B1", "B2"} in result

    def test_two_clusters_separate(self):
        """Two tight clusters with weak bridge → two communities."""
        la = _make_two_clusters(inter_R=10.0, intra_R=0.3)
        result = detect_communities(la)
        assert len(result) == 2
        a_cluster = next(c for c in result if "A1" in c)
        b_cluster = next(c for c in result if "B1" in c)
        assert a_cluster == {"A1", "A2", "A3"}
        assert b_cluster == {"B1", "B2", "B3"}

    def test_two_clusters_merge_when_bridge_strong(self):
        """Dense low-R cross-cluster connections → one community."""
        la = Landscape()
        # Two groups, but cross-group R is much lower than intra-group R
        for a in ["A1", "A2", "A3"]:
            for b in ["A1", "A2", "A3"]:
                if a != b:
                    la.add_edge(a, b, delta=0.5, resistance=2.0)
        for a in ["B1", "B2", "B3"]:
            for b in ["B1", "B2", "B3"]:
                if a != b:
                    la.add_edge(a, b, delta=0.5, resistance=2.0)
        # Every A connects to every B with very low R
        for a in ["A1", "A2", "A3"]:
            for b in ["B1", "B2", "B3"]:
                la.add_edge(a, b, delta=0.5, resistance=0.1)
                la.add_edge(b, a, delta=0.5, resistance=0.1)
        result = detect_communities(la)
        assert len(result) == 1
        assert result[0] == {"A1", "A2", "A3", "B1", "B2", "B3"}

    def test_star_topology(self):
        """Hub connected to leaves → one community."""
        la = Landscape()
        for leaf in ["L1", "L2", "L3", "L4"]:
            la.add_edge("H", leaf, delta=0.5, resistance=1.0)
            la.add_edge(leaf, "H", delta=0.5, resistance=1.0)
        result = detect_communities(la)
        assert len(result) == 1
        assert result[0] == {"H", "L1", "L2", "L3", "L4"}

    def test_chain_topology(self):
        """A—B—C—D chain → one community (all connected)."""
        la = Landscape()
        for a, b in [("A", "B"), ("B", "C"), ("C", "D")]:
            la.add_edge(a, b, delta=0.5, resistance=1.0)
            la.add_edge(b, a, delta=0.5, resistance=1.0)
        result = detect_communities(la)
        assert len(result) == 1

    def test_three_clusters(self):
        """Three well-separated clusters → three communities."""
        la = Landscape()
        # Three clusters
        for prefix in ["X", "Y", "Z"]:
            for i in range(1, 4):
                for j in range(1, 4):
                    if i != j:
                        la.add_edge(f"{prefix}{i}", f"{prefix}{j}",
                                    delta=0.5, resistance=0.3)
        # Weak inter-cluster bridges
        la.add_edge("X1", "Y1", delta=0.5, resistance=15.0)
        la.add_edge("Y1", "Z1", delta=0.5, resistance=15.0)
        result = detect_communities(la)
        assert len(result) == 3

    def test_fully_connected_homogeneous(self):
        """Fully connected with equal R → one community."""
        la = Landscape.fully_connected(["A", "B", "C", "D"])
        result = detect_communities(la)
        assert len(result) == 1

    def test_isolated_plus_cluster(self):
        """Isolated node + connected cluster → two communities."""
        la = Landscape()
        la.add_state("LONE")
        la.add_edge("A", "B", delta=0.5, resistance=1.0)
        la.add_edge("B", "A", delta=0.5, resistance=1.0)
        result = detect_communities(la)
        assert len(result) == 2
        assert {"LONE"} in result
        assert {"A", "B"} in result


# ── TestCommunityHistorization ───────────────────────────────────

class TestCommunityHistorization:
    """R_eff changes from navigation drive community formation."""

    def test_failure_splits_community(self):
        """Repeated failures on a bridge raise R_eff → splits community."""
        # Two clusters with moderate bridge — starts as one community
        la = _make_two_clusters(inter_R=1.5, intra_R=0.5)
        # Fail the bridge heavily → R_eff climbs to R₀ + δ_max
        _historize_edge(la, "A1", "B1", Outcome.FAILURE, n=20)
        _historize_edge(la, "B1", "A1", Outcome.FAILURE, n=20)
        # Bridge R_eff now much higher than intra-cluster R
        result = detect_communities(la)
        assert len(result) == 2
        a_cluster = next(c for c in result if "A1" in c)
        b_cluster = next(c for c in result if "B1" in c)
        assert a_cluster == {"A1", "A2", "A3"}
        assert b_cluster == {"B1", "B2", "B3"}

    def test_success_merges_community(self):
        """Successes on a bridge lower R_eff → merges communities."""
        la = Landscape()
        # Aggressive params so test can accumulate meaningful δ_H
        la.historization = Historization(lambda_s=1.0, delta_max=5.0)
        # Two tight pairs
        la.add_edge("A1", "A2", delta=0.5, resistance=0.5)
        la.add_edge("A2", "A1", delta=0.5, resistance=0.5)
        la.add_edge("B1", "B2", delta=0.5, resistance=0.5)
        la.add_edge("B2", "B1", delta=0.5, resistance=0.5)
        # Bridge with R₀ ≤ δ_max so success can push R_eff → ε
        la.add_edge("A1", "B1", delta=0.5, resistance=4.0)
        la.add_edge("B1", "A1", delta=0.5, resistance=4.0)
        assert len(detect_communities(la)) == 2
        # Succeed on bridge (interleaved so both edges accumulate trace)
        _historize_edges_interleaved(
            la, [("A1", "B1"), ("B1", "A1")], Outcome.SUCCESS, n=30)
        result = detect_communities(la)
        assert len(result) == 1

    def test_cold_start_equals_topology(self):
        """Fresh landscape (δ_H=0) → communities from R₀ topology only."""
        la = _make_two_clusters(inter_R=10.0, intra_R=0.5)
        # No historization events → δ_H = 0 for all edges
        result = detect_communities(la)
        # Should still detect topology-based clusters
        assert len(result) == 2

    def test_mixed_history(self):
        """Success in cluster A, failure in cluster B → structure diverges."""
        la = _make_two_clusters(inter_R=5.0, intra_R=1.0)
        # Succeed within A → lower internal R_eff
        for a in ["A1", "A2", "A3"]:
            for b in ["A1", "A2", "A3"]:
                if a != b:
                    _historize_edge(la, a, b, Outcome.SUCCESS, n=5)
        # Fail within B → raise internal R_eff
        for a in ["B1", "B2", "B3"]:
            for b in ["B1", "B2", "B3"]:
                if a != b:
                    _historize_edge(la, a, b, Outcome.FAILURE, n=5)
        result = detect_communities(la)
        # A cluster should stay tight; B cluster may fragment
        a_community = next(c for c in result if "A1" in c)
        assert {"A1", "A2", "A3"} <= a_community
        # B nodes should NOT all be in same community as A
        assert not ({"B1", "B2", "B3"} <= a_community)


# ── TestCommunityProperties ──────────────────────────────────────

class TestCommunityProperties:
    """Structural properties: determinism, order independence."""

    def test_deterministic(self):
        """Same landscape → same communities every time."""
        la = _make_two_clusters(inter_R=8.0, intra_R=0.5)
        r1 = detect_communities(la)
        r2 = detect_communities(la)
        r3 = detect_communities(la)
        assert r1 == r2 == r3

    def test_output_sorted_deterministically(self):
        """Communities are sorted by smallest member."""
        la = Landscape()
        la.add_edge("Z1", "Z2", delta=0.5, resistance=1.0)
        la.add_edge("A1", "A2", delta=0.5, resistance=1.0)
        result = detect_communities(la)
        assert len(result) == 2
        # "A1" < "Z1" → first community contains A nodes
        assert "A1" in result[0] or "A2" in result[0]

    def test_unidirectional_edges(self):
        """Works with purely unidirectional edges."""
        la = Landscape()
        la.add_edge("A", "B", delta=0.5, resistance=1.0)
        la.add_edge("B", "C", delta=0.5, resistance=1.0)
        # Unidirectional chain A→B→C — still one community
        result = detect_communities(la)
        assert len(result) == 1
        assert result[0] == {"A", "B", "C"}

    def test_no_side_effects(self):
        """detect_communities does not modify the landscape."""
        la = _make_two_clusters()
        states_before = la.states.copy()
        edges_before = la.edges.copy()
        tau_before = la.historization.tau
        detect_communities(la)
        assert la.states == states_before
        assert la.edges == edges_before
        assert la.historization.tau == tau_before

    def test_communities_correlate_with_but_differ_from_prefixes(self):
        """Community detection finds similar structure to prefixes
        but is not constrained by them."""
        la = Landscape()
        # Aggressive params for meaningful δ_H in test
        la.historization = Historization(lambda_s=1.0, delta_max=5.0)
        # Two "domains" by prefix convention — tight intra, weak bridge
        la.add_edge("C:1", "C:2", delta=0.5, resistance=0.5)
        la.add_edge("C:2", "C:1", delta=0.5, resistance=0.5)
        la.add_edge("EN:1", "EN:2", delta=0.5, resistance=0.5)
        la.add_edge("EN:2", "EN:1", delta=0.5, resistance=0.5)
        # Bridge, R₀ ≤ δ_max so successes can push R_eff → ε
        la.add_edge("C:1", "EN:1", delta=0.5, resistance=4.0)
        la.add_edge("EN:1", "C:1", delta=0.5, resistance=4.0)
        result = detect_communities(la)
        assert len(result) == 2
        c_community = next(c for c in result if "C:1" in c)
        en_community = next(c for c in result if "EN:1" in c)
        assert all(n.startswith("C:") for n in c_community)
        assert all(n.startswith("EN:") for n in en_community)
        # Succeed on bridge → R_eff drops to ε → merge regardless of prefix
        _historize_edges_interleaved(
            la, [("C:1", "EN:1"), ("EN:1", "C:1")], Outcome.SUCCESS, n=30)
        result2 = detect_communities(la)
        assert len(result2) == 1  # prefixes don't prevent merging

    def test_scale_moderate(self):
        """Works on moderate-sized landscape (100 nodes)."""
        la = Landscape()
        # 10 clusters of 10 nodes each
        for c in range(10):
            for i in range(10):
                for j in range(10):
                    if i != j:
                        la.add_edge(f"C{c}N{i}", f"C{c}N{j}",
                                    delta=0.5, resistance=0.5)
        # Chain bridges between clusters
        for c in range(9):
            la.add_edge(f"C{c}N0", f"C{c+1}N0", delta=0.5, resistance=20.0)
        result = detect_communities(la)
        assert len(result) == 10
        # Each cluster is one community
        for c in range(10):
            cluster_nodes = {f"C{c}N{i}" for i in range(10)}
            assert any(cluster_nodes <= comm for comm in result)
