"""Tests for explore_bootstrap_landscape.py — C195.

Validates the structural mechanisms:
1. bootstrap.json parsing (nodes, edges, traces)
2. Transition potential formula: T(e) = Δ · 1/(1 + m/μ)
3. Local vs global potential (the key insight)
4. Structural creation from exploration paths
"""

import pytest
from e0_controller.explore_bootstrap_landscape import (
    load_bootstrap,
    extract_nodes,
    extract_edges,
    build_spec,
    inject_node_traces,
    make_execute_fn,
    make_revisit_aware_execute,
    transition_potential,
    compute_state_potential,
    autonomous_goal,
    local_transition_potential,
    local_autonomous_step,
    MU,
)
from e0_controller.bootstrapper import bootstrap_landscape
from e0_controller.landscape import Edge, Outcome
from e0_controller.primitives import Outcome


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def bootstrap_data():
    """Load bootstrap.json once for all tests."""
    bs = load_bootstrap()
    nodes = extract_nodes(bs)
    edges = extract_edges(bs, nodes)
    return bs, nodes, edges


@pytest.fixture
def landscape_with_traces(bootstrap_data):
    """Fresh landscape with injected traces."""
    _, nodes, edges = bootstrap_data
    spec = build_spec(nodes, edges)
    ls = bootstrap_landscape(spec)
    inject_node_traces(ls, nodes)
    return ls, nodes, edges


# ---------------------------------------------------------------------------
# Phase 1: Parsing
# ---------------------------------------------------------------------------


class TestParsing:
    """bootstrap.json → nodes + edges."""

    def test_nodes_non_empty(self, bootstrap_data):
        _, nodes, _ = bootstrap_data
        assert len(nodes) >= 30, f"Expected ≥30 nodes, got {len(nodes)}"

    def test_node_types(self, bootstrap_data):
        _, nodes, _ = bootstrap_data
        types = {n["type"] for n in nodes.values()}
        expected = {"gordian_trap", "breakthrough", "working_principle",
                    "perspective_check", "arch_layer", "open_thread",
                    "current_state"}
        assert expected.issubset(types), f"Missing types: {expected - types}"

    def test_edges_non_empty(self, bootstrap_data):
        _, _, edges = bootstrap_data
        assert len(edges) >= 40, f"Expected ≥40 edges, got {len(edges)}"

    def test_here_node_exists(self, bootstrap_data):
        _, nodes, _ = bootstrap_data
        assert "HERE" in nodes
        assert nodes["HERE"]["type"] == "current_state"

    def test_open_threads_exist(self, bootstrap_data):
        _, nodes, _ = bootstrap_data
        open_threads = [n for n, info in nodes.items() if info["type"] == "open_thread"]
        assert len(open_threads) >= 1, "Expected at least one open thread"

    def test_gordian_traps_have_traces(self, bootstrap_data):
        """Gordian traps carry U/F from real commit history."""
        _, nodes, _ = bootstrap_data
        gts = {nid: n for nid, n in nodes.items() if n["type"] == "gordian_trap"}
        assert gts, "No gordian traps found"
        for gt_id, gt in gts.items():
            assert gt.get("U", 0) + gt.get("F", 0) > 0, \
                f"{gt_id} has no U/F traces"

    def test_edges_connect_existing_nodes(self, bootstrap_data):
        _, nodes, edges = bootstrap_data
        for edge in edges:
            src, tgt = edge["from"], edge["to"]
            assert src in nodes, f"Edge source '{src}' not in nodes"
            assert tgt in nodes, f"Edge target '{tgt}' not in nodes"


# ---------------------------------------------------------------------------
# Phase 2: Landscape construction
# ---------------------------------------------------------------------------


class TestLandscapeConstruction:
    """Nodes + edges → navigable Landscape."""

    def test_landscape_state_count(self, landscape_with_traces):
        ls, nodes, _ = landscape_with_traces
        assert len(ls.states) == len(nodes)

    def test_landscape_edge_count(self, landscape_with_traces):
        ls, _, edges = landscape_with_traces
        assert ls.edge_count() == len(edges)

    def test_traces_injected(self, landscape_with_traces):
        """Injected traces produce non-zero trace_load on some edges."""
        ls, _, _ = landscape_with_traces
        loads = [ls.historization.trace_load(e) for e in ls.edges]
        non_zero = sum(1 for m in loads if m > 0)
        assert non_zero > 0, "No traces were injected"

    def test_difference_positive(self, landscape_with_traces):
        """All edges should have Δ > 0."""
        ls, _, _ = landscape_with_traces
        for e in ls.edges:
            d = ls.difference(e.source, e.target)
            assert d is not None and d > 0, \
                f"Edge {e.source}→{e.target} has Δ={d}"


# ---------------------------------------------------------------------------
# Phase 3: Transition Potential
# ---------------------------------------------------------------------------


class TestTransitionPotential:
    """T(e) = Δ(e) · 1/(1 + m(e)/μ)."""

    def test_formula_zero_load(self, landscape_with_traces):
        """With m=0: T = Δ."""
        ls, _, _ = landscape_with_traces
        # Find an edge with zero load
        for e in ls.edges:
            if ls.historization.trace_load(e) == 0:
                t = transition_potential(ls, e)
                delta = ls.difference(e.source, e.target)
                assert abs(t - delta) < 1e-6, \
                    f"Expected T={delta}, got T={t} for zero-load edge"
                return
        pytest.skip("No zero-load edges found")

    def test_formula_with_load(self, landscape_with_traces):
        """With m>0: T < Δ."""
        ls, _, _ = landscape_with_traces
        for e in ls.edges:
            m = ls.historization.trace_load(e)
            if m > 0:
                t = transition_potential(ls, e)
                delta = ls.difference(e.source, e.target)
                assert t < delta, \
                    f"T={t} should be < Δ={delta} when m={m}"
                # Verify formula
                expected = delta * (1.0 / (1.0 + m / MU))
                assert abs(t - expected) < 1e-6
                return
        pytest.skip("No loaded edges found")

    def test_high_load_suppresses_potential(self, landscape_with_traces):
        """More load → less potential (diminishing returns)."""
        ls, _, _ = landscape_with_traces
        for e in ls.edges:
            d = ls.difference(e.source, e.target) or 0
            if d <= 0:
                continue
            # T at current load
            t_now = transition_potential(ls, e)
            # Simulate higher load
            m_now = ls.historization.trace_load(e)
            m_high = m_now + 10.0
            t_high = d * (1.0 / (1.0 + m_high / MU))
            assert t_high < t_now, "Higher load should reduce potential"
            return


# ---------------------------------------------------------------------------
# Phase 4: Local vs Global potential (the key insight of Exp 7)
# ---------------------------------------------------------------------------


class TestLocalVsGlobal:
    """Local potential avoids popularity bias of global aggregation."""

    def test_local_returns_only_neighbors(self, landscape_with_traces):
        """Local potential keys are direct neighbors of current."""
        ls, nodes, _ = landscape_with_traces
        local = local_transition_potential(ls, nodes, "HERE", horizon=1)
        # All keys should be targets of edges from HERE
        actual_neighbors = {e.target for e in ls.edges if e.source == "HERE"}
        assert set(local.keys()) == actual_neighbors

    def test_local_open_threads_highest_from_here(self, landscape_with_traces):
        """From HERE, open threads have highest local T (horizon=1)."""
        ls, nodes, _ = landscape_with_traces
        local = local_transition_potential(ls, nodes, "HERE", horizon=1)
        if not local:
            pytest.skip("No neighbors from HERE")
        best_nbr = max(local, key=local.get)
        best_type = nodes.get(best_nbr, {}).get("type", "")
        assert best_type == "open_thread", \
            f"Expected open_thread as best, got {best_type} ({best_nbr})"

    def test_global_hub_bias(self, landscape_with_traces):
        """Global aggregation biases toward hub nodes (L5, L6), not open threads."""
        ls, nodes, _ = landscape_with_traces
        potentials, _ = compute_state_potential(ls, nodes)
        # Remove HERE from comparison
        candidates = {s: p for s, p in potentials.items() if s != "HERE" and p > 0}
        if not candidates:
            pytest.skip("No potential")
        best_global = max(candidates, key=candidates.get)
        best_type = nodes.get(best_global, {}).get("type", "")
        # Global best should be an arch_layer (hub), NOT an open_thread
        assert best_type == "arch_layer", \
            f"Expected arch_layer as global best, got {best_type} ({best_global})"

    def test_local_horizon_enriches(self, landscape_with_traces):
        """Horizon=3 should give higher potential than horizon=1 (looks further)."""
        ls, nodes, _ = landscape_with_traces
        h1 = local_transition_potential(ls, nodes, "HERE", horizon=1)
        h3 = local_transition_potential(ls, nodes, "HERE", horizon=3)
        # Same keys, but h3 values should be >= h1 values
        for nbr in h1:
            assert h3.get(nbr, 0) >= h1[nbr] - 1e-9, \
                f"Horizon=3 should enrich, not reduce: {nbr}"

    def test_autonomous_step_prefers_open(self, landscape_with_traces):
        """Local autonomous step from HERE should pick an open thread."""
        ls, nodes, _ = landscape_with_traces
        nbr, potential = local_autonomous_step(ls, nodes, "HERE", horizon=3)
        assert nbr is not None
        assert potential > 0
        nbr_type = nodes.get(nbr, {}).get("type", "")
        assert nbr_type == "open_thread", \
            f"Expected open_thread, got {nbr_type} ({nbr})"


# ---------------------------------------------------------------------------
# Phase 5: Execute functions
# ---------------------------------------------------------------------------


class TestExecuteFunctions:
    """Domain-aware execute: open_threads = FAILURE, layers = SUCCESS."""

    def test_basic_execute(self, bootstrap_data):
        _, nodes, _ = bootstrap_data
        execute = make_execute_fn(nodes)
        # execute(source, target) — looks up TARGET node
        # Arch layer → SUCCESS
        result = execute("HERE", "L3")
        assert result == Outcome.SUCCESS
        # Open thread → FAILURE
        open_ids = [n for n, info in nodes.items() if info["type"] == "open_thread"]
        if open_ids:
            result = execute("HERE", open_ids[0])
            assert result == Outcome.FAILURE

    def test_revisit_aware_execute(self, bootstrap_data):
        _, nodes, _ = bootstrap_data
        execute = make_revisit_aware_execute(nodes)
        # execute(source, target) — first visit to arch_layer → SUCCESS
        result = execute("HERE", "L3")
        assert result == Outcome.SUCCESS
        # Second visit → FAILURE (revisit penalty)
        result = execute("HERE", "L3")
        assert result == Outcome.FAILURE


# ---------------------------------------------------------------------------
# Phase 6: Structural creation
# ---------------------------------------------------------------------------


class TestStructuralCreation:
    """Exploration paths create new edges (Phase D of Exp 7)."""

    def test_shortcut_creates_edge(self, landscape_with_traces):
        """Path A→B→C where A→C doesn't exist → we can add A→C."""
        ls, nodes, _ = landscape_with_traces
        initial_edges = ls.edge_count()
        # Find a 2-step path where direct edge doesn't exist
        for e1 in ls.edges:
            for e2 in ls.edges:
                if e1.target == e2.source and e1.source != e2.target:
                    if not ls.has_edge(e1.source, e2.target):
                        d1 = ls.difference(e1.source, e1.target) or 0
                        d2 = ls.difference(e2.source, e2.target) or 0
                        avg_delta = (d1 + d2) / 2
                        if avg_delta > 0.1:
                            ls.add_edge(e1.source, e2.target, avg_delta, 1.0)
                            assert ls.edge_count() == initial_edges + 1
                            assert ls.has_edge(e1.source, e2.target)
                            return
        pytest.skip("No suitable 2-step shortcut found")

    def test_new_edge_is_navigable(self, landscape_with_traces):
        """A newly created edge has valid Δ and can be traversed."""
        ls, nodes, _ = landscape_with_traces
        # Add an edge that probably doesn't exist
        src, tgt = "OPEN-1", "OPEN-2"
        if not ls.has_edge(src, tgt) and src in ls.states and tgt in ls.states:
            ls.add_edge(src, tgt, 0.6, 1.0)
            assert ls.difference(src, tgt) == 0.6
            assert ls.effective_tension(src, tgt) < float("inf")
            # Transition potential should be positive
            tp = transition_potential(ls, Edge(src, tgt))
            assert tp > 0
