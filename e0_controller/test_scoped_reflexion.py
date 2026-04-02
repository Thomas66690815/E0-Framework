"""
Tests for Scoped Reflexion (C101)
====================================
Validates historization-driven locality for reflexive proposals.

Key claims:
  1. Fresh systems produce global scope (locality ≈ 0, full radius)
  2. Historized systems produce local scope (locality > 0, reduced radius)
  3. Scoped proposals are confined to scope boundary
  4. Scoped pattern extraction uses only local edges
  5. On fresh landscapes, scoped reflexion ≡ global (no regression)
  6. On historized landscapes, fewer proposals (precision over recall)
  7. Runner reaches goal with scoped reflexion
"""

from __future__ import annotations

import pytest
from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.scoped_reflexion import (
    ReflexionScope,
    compute_reflexion_scope,
    landscape_mu,
    scoped_experienced_pattern,
    scoped_propose_edges,
    run_with_scoped_reflexion,
    _bfs_neighborhood,
    _graph_diameter_estimate,
)
from e0_controller.reflexive_edge_proposal import (
    experienced_pattern,
    find_candidate_targets,
    propose_edges,
    run_with_proactive_reflexion,
)


# ══════════════════════════════════════════════
# Test fixtures
# ══════════════════════════════════════════════

def _make_chain(n: int = 6) -> Landscape:
    """Linear chain: S → A → B → C → D → G (n nodes)."""
    L = Landscape()
    names = ["S"] + [chr(65 + i) for i in range(n - 2)] + ["G"]
    for i in range(len(names) - 1):
        L.add_edge(names[i], names[i + 1], delta=0.5, resistance=1.0)
    return L


def _make_star(center: str = "S", arms: int = 5) -> Landscape:
    """Star: center connects to arm_0..arm_N. No inter-arm edges."""
    L = Landscape()
    for i in range(arms):
        name = f"arm_{i}"
        L.add_edge(center, name, delta=0.5, resistance=1.0)
        L.add_edge(name, center, delta=0.5, resistance=1.0)
    # Goal is last arm
    L.add_state("G")
    return L


def _make_grid() -> Landscape:
    """3×3 grid: 9 nodes, 4-connected. S=top-left, G=bottom-right."""
    L = Landscape()
    names = [
        ["S",  "A1", "A2"],
        ["B0", "B1", "B2"],
        ["C0", "C1", "G"],
    ]
    for r in range(3):
        for c in range(3):
            if c + 1 < 3:
                L.add_edge(names[r][c], names[r][c + 1], delta=0.5, resistance=1.0)
                L.add_edge(names[r][c + 1], names[r][c], delta=0.5, resistance=1.0)
            if r + 1 < 3:
                L.add_edge(names[r][c], names[r + 1][c], delta=0.5, resistance=1.0)
                L.add_edge(names[r + 1][c], names[r][c], delta=0.5, resistance=1.0)
    return L


def _inscribe_region(L: Landscape, edges: list, n: int = 10):
    """Inscribe edges with alternating success/failure n times each (interleaved)."""
    for _ in range(n):
        for src, tgt in edges:
            e = Edge(src, tgt)
            L.historization.update(e, Outcome.SUCCESS)
            L.historization.update(e, Outcome.FAILURE)


def _inscribe_success(L: Landscape, edges: list, n: int = 10):
    """Inscribe edges with pure success n times."""
    for src, tgt in edges:
        e = Edge(src, tgt)
        for _ in range(n):
            L.historization.update(e, Outcome.SUCCESS)


# ══════════════════════════════════════════════
# TestScopeComputation
# ══════════════════════════════════════════════

class TestScopeComputation:
    """Verify scope radius, locality, and boundaries."""

    def test_fresh_landscape_is_global(self):
        """Fresh landscape → locality ≈ 0, radius = diameter."""
        L = _make_chain(6)
        scope = compute_reflexion_scope(L, "S")
        assert scope.locality == 0.0
        assert scope.is_global
        assert scope.included_states == set(L.states)

    def test_historized_landscape_is_local(self):
        """Heavily inscribed landscape → locality > 0, radius < diameter."""
        L = _make_chain(6)
        # Inscribe ALL edges heavily — interleaved to avoid lazy decay gaps
        edges = list(L.edges)
        for _ in range(30):
            for edge in edges:
                L.historization.update(edge, Outcome.SUCCESS)
                L.historization.update(edge, Outcome.FAILURE)
        # With ρ=0.9 and 5 interleaved edges, steady-state mean_load ≈ 2.0
        # Use μ=1.0 to test locality effect (locality = 2/(2+1) ≈ 0.67)
        scope = compute_reflexion_scope(L, "S", mu=1.0)
        assert scope.locality > 0.5
        assert not scope.is_global
        assert len(scope.included_states) < len(L.states)

    def test_locality_monotonic_with_inscription(self):
        """More inscription → higher locality."""
        L = _make_chain(6)
        localities = []
        for round_n in range(5):
            for edge in L.edges:
                for _ in range(5):
                    L.historization.update(edge, Outcome.SUCCESS)
            scope = compute_reflexion_scope(L, "S")
            localities.append(scope.locality)
        # Each round should be >= previous (monotonic)
        for i in range(1, len(localities)):
            assert localities[i] >= localities[i - 1]

    def test_scope_always_includes_center(self):
        """Center node is always in scope."""
        L = _make_chain(6)
        scope = compute_reflexion_scope(L, "B")
        assert "B" in scope.included_states

    def test_scope_radius_at_least_one(self):
        """Radius never drops below 1 — at minimum, neighbors are included."""
        L = _make_chain(6)
        # Even if we inscribe massively
        for edge in L.edges:
            for _ in range(100):
                L.historization.update(edge, Outcome.SUCCESS)
        scope = compute_reflexion_scope(L, "B")
        assert scope.radius >= 1
        # At radius 1, at least center + one neighbor
        assert len(scope.included_states) >= 2

    def test_mu_parameter_controls_sensitivity(self):
        """Lower μ → faster locality increase."""
        L = _make_chain(6)
        for edge in L.edges:
            for _ in range(5):
                L.historization.update(edge, Outcome.SUCCESS)
        scope_low_mu = compute_reflexion_scope(L, "S", mu=2.0)
        scope_high_mu = compute_reflexion_scope(L, "S", mu=20.0)
        assert scope_low_mu.locality > scope_high_mu.locality

    def test_empty_landscape(self):
        """Edge case: landscape with no edges."""
        L = Landscape()
        L.add_state("S")
        scope = compute_reflexion_scope(L, "S")
        assert scope.included_states == {"S"}
        assert scope.locality == 0.0


# ══════════════════════════════════════════════
# TestBfsNeighborhood
# ══════════════════════════════════════════════

class TestBfsNeighborhood:
    """Verify undirected BFS neighborhood."""

    def test_radius_zero(self):
        L = _make_chain(6)
        nb = _bfs_neighborhood(L, "S", 0)
        assert nb == {"S"}

    def test_radius_one(self):
        L = _make_chain(6)
        nb = _bfs_neighborhood(L, "B", 1)
        assert "B" in nb
        assert "A" in nb  # forward neighbor
        assert "C" in nb  # backward neighbor (undirected)

    def test_radius_covers_full_chain(self):
        L = _make_chain(6)
        nb = _bfs_neighborhood(L, "S", 10)
        assert nb == set(L.states)

    def test_grid_neighborhood(self):
        L = _make_grid()
        nb = _bfs_neighborhood(L, "B1", 1)
        # B1 is center of grid: neighbors are A1, B0, B2, C1
        assert "B1" in nb
        assert "A1" in nb
        assert "B0" in nb
        assert "B2" in nb
        assert "C1" in nb
        # Not reachable in 1 hop
        assert "S" not in nb
        assert "G" not in nb


# ══════════════════════════════════════════════
# TestGraphDiameter
# ══════════════════════════════════════════════

class TestGraphDiameter:
    """Verify diameter estimation."""

    def test_chain_diameter(self):
        L = _make_chain(6)
        d = _graph_diameter_estimate(L)
        assert d == 5  # S→A→B→C→D→G = 5 hops

    def test_single_node(self):
        L = Landscape()
        L.add_state("X")
        d = _graph_diameter_estimate(L)
        assert d == 1

    def test_fully_connected(self):
        L = Landscape.fully_connected(["A", "B", "C", "D"])
        d = _graph_diameter_estimate(L)
        assert d == 1  # all directly connected


# ══════════════════════════════════════════════
# TestScopedPattern
# ══════════════════════════════════════════════

class TestScopedPattern:
    """Verify pattern extraction respects scope boundary."""

    def test_scoped_pattern_uses_local_edges_only(self):
        """Pattern from scoped region ignores edges outside scope."""
        L = _make_chain(6)
        # Inscribe S→A with high Δ success
        L.adjust_delta("S", "A", 2.0)
        _inscribe_success(L, [("S", "A")], n=10)
        # Inscribe D→G with low Δ success
        L.adjust_delta("D", "G", 0.1)
        _inscribe_success(L, [("D", "G")], n=10)

        # Scope around S with radius 1: only sees S and A
        scope_s = ReflexionScope(
            center="S", radius=1,
            included_states={"S", "A"},
            locality=0.8,
        )
        pattern_s = scoped_experienced_pattern(L, scope_s)
        assert pattern_s.median_delta == 2.0  # only S→A

        # Scope around G with radius 1: only sees D and G
        scope_g = ReflexionScope(
            center="G", radius=1,
            included_states={"D", "G"},
            locality=0.8,
        )
        pattern_g = scoped_experienced_pattern(L, scope_g)
        assert pattern_g.median_delta == 0.1  # only D→G

    def test_global_scope_equals_global_pattern(self):
        """When scope includes all states, result matches global pattern."""
        L = _make_chain(6)
        _inscribe_success(L, [("S", "A"), ("A", "B"), ("B", "C")], n=5)

        global_scope = ReflexionScope(
            center="S", radius=100,
            included_states=set(L.states),
            locality=0.0,
        )
        scoped = scoped_experienced_pattern(L, global_scope)
        global_p = experienced_pattern(L)
        assert scoped.median_delta == global_p.median_delta
        assert scoped.median_r0 == global_p.median_r0
        assert scoped.sample_size == global_p.sample_size

    def test_no_local_experience_falls_back(self):
        """Scope with no inscribed edges returns non-zero fallback."""
        L = _make_chain(6)
        scope = ReflexionScope(
            center="S", radius=1,
            included_states={"S", "A"},
        )
        pattern = scoped_experienced_pattern(L, scope)
        assert pattern.sample_size == 0
        assert pattern.median_delta > 0
        assert pattern.median_r0 > 0


# ══════════════════════════════════════════════
# TestScopedProposals
# ══════════════════════════════════════════════

class TestScopedProposals:
    """Verify proposals are confined to scope."""

    def test_proposals_within_scope_only(self):
        """All proposed targets must be within scope."""
        L = _make_grid()
        scope = ReflexionScope(
            center="S", radius=1,
            included_states={"S", "A1", "B0"},
            locality=0.7,
        )
        proposals = scoped_propose_edges(L, "S", "G", scope)
        for p in proposals:
            assert p.target in scope.included_states

    def test_fresh_scope_proposes_globally(self):
        """Fresh landscape: scoped proposals = global proposals."""
        L = _make_chain(6)
        # Break chain so S is a frontier: remove S→A
        L.remove_edge("S", "A")

        # Scoped (auto-compute with goal, fresh → global)
        scoped = scoped_propose_edges(L, "S", "G")
        # Global
        global_p = propose_edges(L, "S", "G", proactive=True)

        scoped_targets = {p.target for p in scoped}
        global_targets = {p.target for p in global_p}
        assert scoped_targets == global_targets

    def test_historized_scope_proposes_locally(self):
        """Historized landscape: scoped proposals are subset of global."""
        L = _make_grid()
        # Heavily inscribe ALL edges — interleaved
        edges = list(L.edges)
        for _ in range(30):
            for edge in edges:
                L.historization.update(edge, Outcome.SUCCESS)
                L.historization.update(edge, Outcome.FAILURE)
        # Remove S→A1 to create frontier at S
        L.remove_edge("S", "A1")

        scope = compute_reflexion_scope(L, "S", goal="G")
        scoped = scoped_propose_edges(L, "S", "G", scope)
        global_p = propose_edges(L, "S", "G", proactive=True)

        scoped_targets = {p.target for p in scoped}
        global_targets = {p.target for p in global_p}
        # Scoped proposals are confined to scope boundary
        assert scoped_targets <= scope.included_states
        # With high locality, scoped should not exceed global count
        if scope.locality > 0.5:
            assert len(scoped_targets) <= len(global_targets)

    def test_rationale_contains_scope_info(self):
        """Proposal rationale mentions scope metadata."""
        L = _make_chain(6)
        L.remove_edge("S", "A")
        proposals = scoped_propose_edges(L, "S", "G")
        for p in proposals:
            assert "Scoped" in p.rationale
            assert "locality=" in p.rationale

    def test_no_candidates_returns_empty(self):
        """If all scope states are reachable, no proposals."""
        L = _make_chain(6)
        # S→A exists, scope={S,A}: A is reachable, no candidates
        scope = ReflexionScope(
            center="S", radius=1,
            included_states={"S", "A"},
            locality=0.9,
        )
        proposals = scoped_propose_edges(L, "S", "G", scope)
        assert proposals == []


# ══════════════════════════════════════════════
# TestFreshDegeneracy
# ══════════════════════════════════════════════

class TestFreshDegeneracy:
    """Verify: fresh landscape → scoped reflexion ≡ global reflexion."""

    def test_chain_fresh_same_results(self):
        """On a fresh chain, scoped run and proactive run reach same goal."""
        L_scoped = _make_chain(6)
        # Break at B→C to force reflexion
        L_scoped.remove_edge("B", "C")

        L_global = _make_chain(6)
        L_global.remove_edge("B", "C")

        exec_fn = lambda s, t: Outcome.SUCCESS

        trace_s, props_s, scopes_s = run_with_scoped_reflexion(
            L_scoped, exec_fn, "S", "G", mu=5.0,
        )
        trace_g, props_g = run_with_proactive_reflexion(
            L_global, exec_fn, "S", "G",
        )

        # Both should reach goal
        assert trace_s.steps[-1].target == "G"
        assert trace_g.steps[-1].target == "G"

        # On fresh landscape, all scopes should be global
        for scope in scopes_s:
            assert scope.is_global

    def test_grid_fresh_same_proposal_count(self):
        """Fresh grid: scoped and global produce same number of proposals."""
        L_s = _make_grid()
        L_s.remove_edge("S", "A1")  # frontier at S

        L_g = _make_grid()
        L_g.remove_edge("S", "A1")

        scope = compute_reflexion_scope(L_s, "S")
        scoped = scoped_propose_edges(L_s, "S", "G", scope)
        global_p = propose_edges(L_g, "S", "G", proactive=True)

        assert len(scoped) == len(global_p)


# ══════════════════════════════════════════════
# TestHistorizedLocality
# ══════════════════════════════════════════════

class TestHistorizedLocality:
    """Verify: historized landscape → scoped reflexion narrows proposals."""

    def test_inscription_narrows_scope(self):
        """Heavy inscription reduces scope size."""
        L = _make_grid()
        scope_before = compute_reflexion_scope(L, "S")

        # Heavily inscribe ALL edges — interleaved
        edges = list(L.edges)
        for _ in range(30):
            for edge in edges:
                L.historization.update(edge, Outcome.SUCCESS)
                L.historization.update(edge, Outcome.FAILURE)

        scope_after = compute_reflexion_scope(L, "S")
        assert scope_after.scope_size <= scope_before.scope_size
        assert scope_after.locality > scope_before.locality

    def test_fewer_proposals_when_historized(self):
        """Historized landscape produces fewer proposals at same node."""
        L = _make_grid()
        L.remove_edge("S", "A1")  # create frontier

        # Fresh: all candidates available
        proposals_fresh = scoped_propose_edges(L, "S", "G")

        # Inscribe heavily — interleaved
        edges = list(L.edges)
        for _ in range(30):
            for edge in edges:
                L.historization.update(edge, Outcome.SUCCESS)
                L.historization.update(edge, Outcome.FAILURE)

        # Historized: fewer candidates (scope narrower)
        proposals_hist = scoped_propose_edges(L, "S", "G")

        assert len(proposals_hist) <= len(proposals_fresh)

    def test_local_pattern_differs_from_global(self):
        """Scoped pattern reflects local experience, not global average."""
        L = _make_grid()
        # Region A: high-Δ successes near S
        L.adjust_delta("S", "B0", 3.0)
        _inscribe_success(L, [("S", "B0")], n=20)
        # Region B: low-Δ successes near G
        L.adjust_delta("C1", "G", 0.1)
        _inscribe_success(L, [("C1", "G")], n=20)

        # Global pattern: mix of high and low
        global_p = experienced_pattern(L)

        # Local scope around S
        scope_s = ReflexionScope(
            center="S", radius=1,
            included_states={"S", "A1", "B0"},
            locality=0.8,
        )
        local_p = scoped_experienced_pattern(L, scope_s)

        # Local pattern should reflect high-Δ region
        assert local_p.median_delta > global_p.median_delta


# ══════════════════════════════════════════════
# TestRunner
# ══════════════════════════════════════════════

class TestRunner:
    """Verify scoped reflexion runner reaches goals."""

    def test_runner_reaches_goal(self):
        """Basic: runner navigates broken chain with scoped reflexion."""
        L = _make_chain(6)
        L.remove_edge("B", "C")  # force reflexion at B

        trace, proposals, scopes = run_with_scoped_reflexion(
            L, lambda s, t: Outcome.SUCCESS, "S", "G",
        )
        assert trace.steps[-1].target == "G"
        assert len(proposals) > 0  # reflexion was triggered

    def test_runner_grid_reaches_goal(self):
        """Diamond with frontier: scoped runner proposes and finds path."""
        L = Landscape()
        L.add_edge("S", "A", delta=0.5, resistance=1.0)
        L.add_edge("S", "B", delta=0.5, resistance=1.0)
        L.add_edge("A", "M", delta=0.5, resistance=1.0)
        L.add_edge("B", "M", delta=0.5, resistance=1.0)
        # M → G missing: frontier at M
        L.add_state("G")

        trace, proposals, scopes = run_with_scoped_reflexion(
            L, lambda s, t: Outcome.SUCCESS, "S", "G",
        )
        assert len(proposals) > 0
        assert trace.steps[-1].target == "G"
        assert trace.steps[-1].target == "G"

    def test_runner_records_scopes(self):
        """Runner returns scope at each frontier."""
        L = _make_chain(6)
        L.remove_edge("B", "C")

        _, _, scopes = run_with_scoped_reflexion(
            L, lambda s, t: Outcome.SUCCESS, "S", "G",
        )
        assert len(scopes) >= 1
        assert all(isinstance(s, ReflexionScope) for s in scopes)
        # Each scope has a center
        assert all(s.center for s in scopes)

    def test_runner_with_inscription_narrows_scopes(self):
        """Runner on historized landscape produces narrower scopes."""
        L = _make_chain(8)
        # Inscribe the first part heavily
        for edge in L.edges:
            for _ in range(20):
                L.historization.update(edge, Outcome.SUCCESS)
        # Break at E→F to force reflexion
        L.remove_edge("E", "F")

        _, _, scopes = run_with_scoped_reflexion(
            L, lambda s, t: Outcome.SUCCESS, "S", "G",
        )
        assert len(scopes) >= 1
        # At least one scope should NOT be global
        assert any(not s.is_global for s in scopes)


# ══════════════════════════════════════════════
# TestMathematicalProperties
# ══════════════════════════════════════════════

class TestMathematicalProperties:
    """Verify formal properties of scope computation."""

    def test_locality_bounded_01(self):
        """locality ∈ [0, 1) for any trace_load."""
        L = _make_chain(6)
        for multiplier in [0, 1, 5, 20, 100]:
            for edge in L.edges:
                for _ in range(multiplier):
                    L.historization.update(edge, Outcome.SUCCESS)
            scope = compute_reflexion_scope(L, "S")
            assert 0.0 <= scope.locality < 1.0

    def test_radius_bounded(self):
        """radius ∈ [1, diameter]."""
        L = _make_chain(6)
        d = _graph_diameter_estimate(L)
        for multiplier in [0, 5, 50]:
            for edge in L.edges:
                for _ in range(multiplier):
                    L.historization.update(edge, Outcome.SUCCESS)
            scope = compute_reflexion_scope(L, "S")
            assert 1 <= scope.radius <= d

    def test_scope_subset_of_landscape(self):
        """included_states ⊆ landscape.states always."""
        L = _make_grid()
        for edge in L.edges:
            for _ in range(10):
                L.historization.update(edge, Outcome.SUCCESS)
        scope = compute_reflexion_scope(L, "B1")
        assert scope.included_states <= set(L.states)

    def test_scope_dataclass_properties(self):
        """is_global and scope_size are consistent."""
        scope = ReflexionScope(
            center="X", radius=5,
            included_states={"X", "Y", "Z"},
            locality=0.01,
        )
        assert scope.is_global  # locality < 0.05
        assert scope.scope_size == 3

        scope2 = ReflexionScope(
            center="X", radius=1,
            included_states={"X", "Y"},
            locality=0.8,
        )
        assert not scope2.is_global
        assert scope2.scope_size == 2


# ══════════════════════════════════════════════
# TestAdaptiveMu (C105)
# ══════════════════════════════════════════════

class TestAdaptiveMu:
    """Validate adaptive μ = |E|/|V| derivation from landscape topology.

    C105 resolves P5 §10.4 open question 1 (optimal μ): the sensitivity
    threshold is not a free parameter but a structural property of the
    landscape — its mean out-degree.
    """

    def test_landscape_mu_formula(self):
        """μ = |E|/|V| for any landscape."""
        L = _make_chain(6)  # 5 edges, 6 nodes
        assert landscape_mu(L) == pytest.approx(5 / 6)

    def test_landscape_mu_star(self):
        """Star: 10 edges (bidirectional), 7 nodes (5 arms + center + G)."""
        L = _make_star()
        mu = landscape_mu(L)
        assert mu == pytest.approx(len(L.edges) / len(L.states))

    def test_landscape_mu_grid(self):
        """Grid: 24 edges (bidirectional), 9 nodes."""
        L = _make_grid()
        mu = landscape_mu(L)
        assert mu == pytest.approx(24 / 9)

    def test_sparse_graph_low_mu(self):
        """Sparse (chain) → μ < 1: fast localization."""
        L = _make_chain(6)
        assert landscape_mu(L) < 1.0

    def test_dense_graph_high_mu(self):
        """Dense (grid, bidirectional) → μ > 2: slower localization."""
        L = _make_grid()
        assert landscape_mu(L) > 2.0

    def test_mu_scales_with_density(self):
        """Denser graph → larger μ → slower localization."""
        mu_chain = landscape_mu(_make_chain(6))
        mu_grid = landscape_mu(_make_grid())
        assert mu_grid > mu_chain

    def test_adaptive_mu_default(self):
        """mu=None (default) uses landscape_mu()."""
        L = _make_chain(6)
        scope = compute_reflexion_scope(L, "S")  # mu=None default
        expected_mu = landscape_mu(L)
        assert f"μ={expected_mu:.2f}" in scope.rationale

    def test_explicit_mu_overrides(self):
        """Explicit mu=5.0 ignores landscape topology (backward compat)."""
        L = _make_chain(6)
        scope = compute_reflexion_scope(L, "S", mu=5.0)
        assert "μ=5.0" in scope.rationale

    def test_adaptive_fresh_still_global(self):
        """Fresh landscape with adaptive μ still produces global scope."""
        L = _make_chain(6)
        scope = compute_reflexion_scope(L, "S")
        assert scope.is_global
        assert scope.locality == 0.0

    def test_adaptive_historized_localizes(self):
        """With adaptive μ, historized landscape reaches locality > 0.5."""
        L = _make_chain(6)
        mu = landscape_mu(L)
        # Inscribe enough to exceed μ on average
        for edge in L.edges:
            for _ in range(5):
                L.historization.update(edge, Outcome.SUCCESS)
        scope = compute_reflexion_scope(L, "S")
        # mean_load = 5.0, μ ≈ 0.83 → locality ≈ 5.0/5.83 ≈ 0.86
        assert scope.locality > 0.5
        assert not scope.is_global

    def test_adaptive_chain_localizes_faster_than_fixed(self):
        """Chain with adaptive μ reaches locality > 0.5 sooner than μ=5."""
        L = _make_chain(6)
        for edge in L.edges:
            L.historization.update(edge, Outcome.SUCCESS)
        # mean_load = 1.0. Adaptive μ ≈ 0.83 → ℓ ≈ 0.55.  Fixed μ=5 → ℓ ≈ 0.17.
        scope_auto = compute_reflexion_scope(L, "S")
        scope_fixed = compute_reflexion_scope(L, "S", mu=5.0)
        assert scope_auto.locality > scope_fixed.locality

    def test_adaptive_runner_reaches_goal(self):
        """Runner with adaptive μ reaches goal on chain."""
        L = _make_chain(6)
        fn = lambda s, t: Outcome.SUCCESS
        trace, proposals, scopes = run_with_scoped_reflexion(
            L, fn, "S", "G", max_cycles=30,
        )
        assert trace.steps[-1].target == "G"

    def test_adaptive_runner_reaches_goal_diamond(self):
        """Runner with adaptive μ reaches goal on diamond with frontier."""
        L = Landscape()
        L.add_edge("S", "A", delta=0.5, resistance=1.0)
        L.add_edge("S", "B", delta=0.5, resistance=1.0)
        L.add_edge("A", "M", delta=0.5, resistance=1.0)
        L.add_edge("B", "M", delta=0.5, resistance=1.0)
        L.add_state("G")  # M → G missing: frontier at M
        fn = lambda s, t: Outcome.SUCCESS
        trace, proposals, scopes = run_with_scoped_reflexion(
            L, fn, "S", "G", max_cycles=30,
        )
        assert trace.steps[-1].target == "G"
        assert len(proposals) > 0  # reflexion was needed

    def test_degenerate_empty_landscape(self):
        """Empty landscape returns μ=1.0 (safe default)."""
        L = Landscape()
        assert landscape_mu(L) == 1.0

    def test_single_edge_landscape(self):
        """Single edge: |E|=1, |V|=2, μ=0.5."""
        L = Landscape()
        L.add_edge("A", "B", delta=1.0, resistance=1.0)
        assert landscape_mu(L) == pytest.approx(0.5)
