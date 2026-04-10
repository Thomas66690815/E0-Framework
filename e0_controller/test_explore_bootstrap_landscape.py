"""Tests for explore_bootstrap_landscape.py — C195/C196/C199.

Validates the structural mechanisms:
1. bootstrap.json parsing (nodes, edges, traces)
2. Transition potential formula: T(e) = Δ · 1/(1 + m/μ)
3. Local vs global potential (the key insight)
4. Structural creation from exploration paths
5. Persistence cycle: discovered edges survive across sessions
6. Executable transitions: navigation produces output
"""

import json
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
    filter_discovered_edges,
    persist_discovered_edges,
    update_edge_confidence,
    llm_semantic_validation,
    EXECUTION_TEMPLATES,
    build_execution_context,
    format_execution_task,
    execute_bootstrap_transition,
    persist_execution_results,
    select_transitions_for_execution,
    load_learning_state,
    BOOTSTRAP_PATH,
    LEARNING_STATE_PATH,
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

    def test_semantic_modulation_scales_delta(self, bootstrap_data):
        """Discovered edges with semantic_score have Δ scaled by that score."""
        bs, nodes, edges = bootstrap_data
        ls = load_learning_state()
        disc = ls.get("discovered_edges", {}).get("edges", [])
        scored = [d for d in disc if "semantic_score" in d]
        if not scored:
            pytest.skip("No semantically scored edges")
        for de in scored:
            raw_delta = de["delta"]
            sem = de["semantic_score"]
            expected_delta = raw_delta * sem
            # Find this edge in the extracted edges
            matching = [e for e in edges
                        if e["from"] == de["from"] and e["to"] == de["to"]]
            if matching:
                actual_delta = matching[0]["delta"]
                assert abs(actual_delta - expected_delta) < 1e-6, \
                    f"{de['from']}→{de['to']}: expected Δ={expected_delta:.3f}, got {actual_delta:.3f}"

    def test_semantic_modulation_weakens_artifacts(self, bootstrap_data):
        """Low semantic score (0.3) reduces Δ to ~30% of raw value."""
        bs, nodes, edges = bootstrap_data
        ls = load_learning_state()
        disc = ls.get("discovered_edges", {}).get("edges", [])
        weak = [d for d in disc if d.get("semantic_score", 1.0) <= 0.3]
        if not weak:
            pytest.skip("No weak semantic edges")
        for de in weak:
            matching = [e for e in edges
                        if e["from"] == de["from"] and e["to"] == de["to"]]
            if matching:
                assert matching[0]["delta"] < de["delta"] * 0.35, \
                    f"Weak edge {de['from']}→{de['to']} should have reduced Δ"

    def test_hand_curated_unaffected(self, bootstrap_data):
        """Hand-curated edges (no semantic_score) keep their original Δ."""
        _, nodes, edges = bootstrap_data
        # GT-1→BT-2 is hand-curated with Δ=0.7
        gt_bt = [e for e in edges if e["from"] == "GT-1" and e["to"] == "BT-2"]
        assert gt_bt, "GT-1→BT-2 edge not found"
        assert abs(gt_bt[0]["delta"] - 0.7) < 1e-6, "Hand-curated Δ was modified"


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
        """Global aggregation biases toward high-connectivity nodes.

        With the original 56 edges, hubs (L5, L6) dominated.
        With discovered_edges enriching open_thread connectivity,
        open threads can also rank high. The key property:
        global aggregation sums ALL edges, favoring connected nodes.
        """
        ls, nodes, _ = landscape_with_traces
        potentials, _ = compute_state_potential(ls, nodes)
        candidates = {s: p for s, p in potentials.items() if s != "HERE" and p > 0}
        if not candidates:
            pytest.skip("No potential")
        best_global = max(candidates, key=candidates.get)
        best_type = nodes.get(best_global, {}).get("type", "")
        # Global best should be a high-connectivity node (arch_layer or open_thread)
        # — NOT a low-connectivity type like perspective_check or gordian_trap
        assert best_type in ("arch_layer", "open_thread"), \
            f"Expected high-connectivity type as global best, got {best_type} ({best_global})"

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


# ---------------------------------------------------------------------------
# Phase 7: Persistence cycle — discovered_edges survive across sessions
# ---------------------------------------------------------------------------


class TestEdgeFilter:
    """filter_discovered_edges selects structurally meaningful edges."""

    def test_cross_type_passes(self, bootstrap_data):
        """Cross-type edge (open_thread→arch_layer) passes filter."""
        _, nodes, edges = bootstrap_data
        # Use a pair that doesn't already exist in discovered_edges
        existing_pairs = {(e["from"], e["to"]) for e in edges}
        for open_id in sorted(nodes):
            if nodes[open_id]["type"] != "open_thread":
                continue
            for layer_id in sorted(nodes):
                if nodes[layer_id]["type"] != "arch_layer":
                    continue
                if (open_id, layer_id) not in existing_pairs:
                    candidates = [{
                        "from": open_id, "to": layer_id,
                        "delta": 0.5, "resistance": 0.6,
                        "derivation": "test",
                    }]
                    result = filter_discovered_edges(candidates, nodes, edges)
                    assert len(result) == 1, f"{open_id}→{layer_id} should pass"
                    return
        pytest.skip("No suitable cross-type pair found")

    def test_same_type_no_frontier_fails(self, bootstrap_data):
        """Same-type non-frontier edge (L1→L3) gets filtered out
        unless it's already missing from existing edges."""
        _, nodes, edges = bootstrap_data
        # L1→L3 might already exist — use a pair that exists
        # Test with an edge between two layers that already exists
        existing_pairs = {(e["from"], e["to"]) for e in edges}
        for src_id, src in nodes.items():
            for tgt_id, tgt in nodes.items():
                if (src["type"] == tgt["type"] == "arch_layer"
                        and src_id != tgt_id
                        and (src_id, tgt_id) not in existing_pairs
                        and src["type"] != "open_thread"):
                    candidates = [{
                        "from": src_id, "to": tgt_id,
                        "delta": 0.5, "resistance": 0.6,
                        "derivation": "test",
                    }]
                    result = filter_discovered_edges(candidates, nodes, edges)
                    assert len(result) == 0, \
                        f"Same-type {src_id}→{tgt_id} should be filtered"
                    return
        pytest.skip("No suitable same-type pair found")

    def test_low_delta_filtered(self, bootstrap_data):
        """Edge with Δ < 0.15 gets filtered out."""
        _, nodes, edges = bootstrap_data
        candidates = [{
            "from": "OPEN-1", "to": "L9",
            "delta": 0.1, "resistance": 0.6,
            "derivation": "test",
        }]
        result = filter_discovered_edges(candidates, nodes, edges)
        assert len(result) == 0

    def test_duplicate_filtered(self, bootstrap_data):
        """Edge that already exists in existing_edges gets filtered."""
        _, nodes, edges = bootstrap_data
        if edges:
            e = edges[0]
            candidates = [{
                "from": e["from"], "to": e["to"],
                "delta": 0.5, "resistance": 0.6,
                "derivation": "test",
            }]
            result = filter_discovered_edges(candidates, nodes, edges)
            assert len(result) == 0

    def test_frontier_bridging_passes(self, bootstrap_data):
        """open_thread→open_thread passes filter (frontier bridging)."""
        _, nodes, edges = bootstrap_data
        open_ids = [n for n, info in nodes.items() if info["type"] == "open_thread"]
        if len(open_ids) < 2:
            pytest.skip("Need at least 2 open threads")
        # Find a pair that doesn't already exist
        existing_pairs = {(e["from"], e["to"]) for e in edges}
        for a in open_ids:
            for b in open_ids:
                if a != b and (a, b) not in existing_pairs:
                    candidates = [{
                        "from": a, "to": b,
                        "delta": 0.5, "resistance": 1.0,
                        "derivation": "test frontier",
                    }]
                    result = filter_discovered_edges(candidates, nodes, edges)
                    assert len(result) == 1
                    return
        pytest.skip("All open-thread pairs already have edges")

    def test_self_loop_filtered(self, bootstrap_data):
        """Self-referential edge gets filtered."""
        _, nodes, edges = bootstrap_data
        candidates = [{
            "from": "OPEN-1", "to": "OPEN-1",
            "delta": 0.5, "resistance": 0.6,
            "derivation": "test",
        }]
        result = filter_discovered_edges(candidates, nodes, edges)
        assert len(result) == 0


class TestPersistenceCycle:
    """The full cycle: explore → discover → persist → reload."""

    def test_persist_dry_run(self, bootstrap_data):
        """dry_run=True returns filtered edges without writing."""
        _, nodes, edges = bootstrap_data
        # Use a pair that doesn't already exist
        existing_pairs = {(e["from"], e["to"]) for e in edges}
        for open_id in sorted(nodes):
            if nodes[open_id]["type"] != "open_thread":
                continue
            for layer_id in sorted(nodes):
                if nodes[layer_id]["type"] != "arch_layer":
                    continue
                if (open_id, layer_id) not in existing_pairs:
                    candidates = [{
                        "from": open_id, "to": layer_id,
                        "delta": 0.58, "resistance": 1.5,
                        "confidence": 0.5,
                        "derivation": f"discovered via {open_id} → test → {layer_id}",
                    }]
                    result = persist_discovered_edges(candidates, nodes, edges, dry_run=True)
                    assert len(result) == 1
                    assert result[0]["from"] == open_id
                    return
        pytest.skip("No suitable pair found")

    def test_round_trip(self, bootstrap_data, tmp_path):
        """Write edges → reload → edges appear in extracted graph."""
        import e0_controller.explore_bootstrap_landscape as mod

        bs_orig, nodes, edges = bootstrap_data

        # Create a tmp learning_state.json with a discovered edge
        tmp_ls = tmp_path / "learning_state.json"
        ls_data = {
            "_meta": {"source": "test"},
            "discovered_edges": {
                "edges": [{
                    "from": "OPEN-1",
                    "to": "OPEN-2",
                    "delta": 0.58,
                    "resistance": 1.5,
                    "confidence": 0.5,
                    "derivation": "test round-trip edge",
                }]
            }
        }
        with open(tmp_ls, "w", encoding="utf-8") as f:
            json.dump(ls_data, f, indent=2)

        orig_path = mod.LEARNING_STATE_PATH
        mod.LEARNING_STATE_PATH = str(tmp_ls)
        try:
            # Reload and extract (extract_edges reads from LEARNING_STATE_PATH)
            edges2 = extract_edges(bs_orig, nodes)

            # The discovered edge should appear
            edge_pairs = [(e["from"], e["to"]) for e in edges2]
            assert ("OPEN-1", "OPEN-2") in edge_pairs, \
                "Discovered edge not found after round-trip"
        finally:
            mod.LEARNING_STATE_PATH = orig_path

    def test_no_duplicate_on_rewrite(self, bootstrap_data, tmp_path):
        """Persisting the same edge twice doesn't create duplicates."""
        bs_orig, nodes, edges = bootstrap_data

        tmp_ls = tmp_path / "learning_state.json"
        with open(tmp_ls, "w", encoding="utf-8") as f:
            json.dump({"_meta": {"source": "test"}}, f, indent=2)

        # Patch LEARNING_STATE_PATH temporarily
        import e0_controller.explore_bootstrap_landscape as mod
        orig_path = mod.LEARNING_STATE_PATH
        mod.LEARNING_STATE_PATH = str(tmp_ls)
        try:
            edge = {
                "from": "OPEN-1", "to": "OPEN-2",
                "delta": 0.58, "resistance": 1.5,
                "confidence": 0.5,
                "derivation": "test",
            }
            # Write once (pass empty existing_edges to bypass graph-level filter)
            persist_discovered_edges([edge], nodes, [])
            # Write again
            persist_discovered_edges([edge], nodes, [])

            with open(tmp_ls, encoding="utf-8") as f:
                ls = json.load(f)
            discovered = ls.get("discovered_edges", {}).get("edges", [])
            matching = [e for e in discovered
                        if e["from"] == "OPEN-1" and e["to"] == "OPEN-2"]
            assert len(matching) == 1, f"Expected 1, got {len(matching)} duplicates"
        finally:
            mod.LEARNING_STATE_PATH = orig_path


class TestConfidenceUpdate:
    """Phase F: discovered edges learn from usage."""

    def test_used_edge_confidence_rises(self, bootstrap_data, tmp_path):
        """Edge traversed → confidence increases (meta-level: system chose this edge)."""
        import e0_controller.explore_bootstrap_landscape as mod
        from e0_controller.bootstrapper import bootstrap_landscape

        bs_orig, nodes, edges = bootstrap_data

        tmp_ls = tmp_path / "learning_state.json"
        ls_data = {
            "_meta": {"source": "test"},
            "discovered_edges": {
                "edges": [{
                    "from": "HERE", "to": "L3",
                    "delta": 0.8, "resistance": 1.3,
                    "confidence": 0.5,
                    "derivation": "test edge",
                }]
            }
        }
        with open(tmp_ls, "w", encoding="utf-8") as f:
            json.dump(ls_data, f, indent=2)

        spec = build_spec(nodes, edges)
        landscape = bootstrap_landscape(spec)
        inject_node_traces(landscape, nodes)

        orig_path = mod.LEARNING_STATE_PATH
        mod.LEARNING_STATE_PATH = str(tmp_ls)
        try:
            # Path that uses HERE→L3
            updates = update_edge_confidence(landscape, nodes, ["HERE", "L3", "HERE"])
            assert ("HERE", "L3") in updates
            assert updates[("HERE", "L3")] > 0.5  # confidence rose
        finally:
            mod.LEARNING_STATE_PATH = orig_path

    def test_unused_edge_decays(self, bootstrap_data, tmp_path):
        """Edge NOT traversed → slow confidence decay."""
        import e0_controller.explore_bootstrap_landscape as mod
        from e0_controller.bootstrapper import bootstrap_landscape

        _, nodes, edges = bootstrap_data

        tmp_ls = tmp_path / "learning_state.json"
        ls_data = {
            "_meta": {"source": "test"},
            "discovered_edges": {
                "edges": [{
                    "from": "OPEN-1", "to": "L9",
                    "delta": 0.55, "resistance": 0.6,
                    "confidence": 0.5,
                    "derivation": "test unused edge",
                }]
            }
        }
        with open(tmp_ls, "w", encoding="utf-8") as f:
            json.dump(ls_data, f, indent=2)

        spec = build_spec(nodes, edges)
        landscape = bootstrap_landscape(spec)
        inject_node_traces(landscape, nodes)

        orig_path = mod.LEARNING_STATE_PATH
        mod.LEARNING_STATE_PATH = str(tmp_ls)
        try:
            # Path that does NOT use OPEN-1→L9
            updates = update_edge_confidence(landscape, nodes, ["HERE", "OPEN-2", "HERE"])
            assert ("OPEN-1", "L9") in updates
            assert updates[("OPEN-1", "L9")] < 0.5  # decayed
            assert updates[("OPEN-1", "L9")] == 0.48  # exactly 0.5 - 0.02
        finally:
            mod.LEARNING_STATE_PATH = orig_path

    def test_traversed_open_thread_edge_rises(self, bootstrap_data, tmp_path):
        """Edge to open_thread traversed → confidence rises (exploration success)."""
        import e0_controller.explore_bootstrap_landscape as mod
        from e0_controller.bootstrapper import bootstrap_landscape

        _, nodes, edges = bootstrap_data

        tmp_ls = tmp_path / "learning_state.json"
        ls_data = {
            "_meta": {"source": "test"},
            "discovered_edges": {
                "edges": [{
                    "from": "HERE", "to": "OPEN-2",
                    "delta": 0.8, "resistance": 0.7,
                    "confidence": 0.5,
                    "derivation": "test open thread edge",
                }]
            }
        }
        with open(tmp_ls, "w", encoding="utf-8") as f:
            json.dump(ls_data, f, indent=2)

        spec = build_spec(nodes, edges)
        landscape = bootstrap_landscape(spec)
        inject_node_traces(landscape, nodes)

        orig_path = mod.LEARNING_STATE_PATH
        mod.LEARNING_STATE_PATH = str(tmp_ls)
        try:
            # Traversing to open_thread = exploration success → confidence rises
            updates = update_edge_confidence(landscape, nodes, ["HERE", "OPEN-2"])
            assert ("HERE", "OPEN-2") in updates
            assert updates[("HERE", "OPEN-2")] > 0.5  # rose, not dropped
        finally:
            mod.LEARNING_STATE_PATH = orig_path

    def test_confidence_persists_to_file(self, bootstrap_data, tmp_path):
        """Updated confidence is written back to learning_state.json."""
        import e0_controller.explore_bootstrap_landscape as mod
        from e0_controller.bootstrapper import bootstrap_landscape

        _, nodes, edges = bootstrap_data

        tmp_ls = tmp_path / "learning_state.json"
        ls_data = {
            "_meta": {"source": "test"},
            "discovered_edges": {
                "edges": [{
                    "from": "HERE", "to": "L3",
                    "delta": 0.8, "resistance": 1.3,
                    "confidence": 0.5,
                    "derivation": "persist test",
                }]
            }
        }
        with open(tmp_ls, "w", encoding="utf-8") as f:
            json.dump(ls_data, f, indent=2)

        spec = build_spec(nodes, edges)
        landscape = bootstrap_landscape(spec)
        inject_node_traces(landscape, nodes)

        orig_path = mod.LEARNING_STATE_PATH
        mod.LEARNING_STATE_PATH = str(tmp_ls)
        try:
            update_edge_confidence(landscape, nodes, ["HERE", "L3"])

            # Reread and verify
            with open(tmp_ls, encoding="utf-8") as f:
                reloaded = json.load(f)
            edge = reloaded["discovered_edges"]["edges"][0]
            assert edge["confidence"] == 0.6  # 0.5 + 0.1
        finally:
            mod.LEARNING_STATE_PATH = orig_path


class TestLLMSemanticValidation:
    """Phase G: LLM judges semantic plausibility of discovered edges."""

    def test_dry_run_returns_scores(self, bootstrap_data):
        """dry_run=True returns placeholder scores without API call."""
        _, nodes, _ = bootstrap_data
        results = llm_semantic_validation(nodes, dry_run=True)
        # Should have one result per discovered edge
        assert isinstance(results, list)
        for r in results:
            assert "edge" in r
            assert "score" in r
            assert r["score"] == 0.5  # dry_run placeholder

    def test_dry_run_no_edges(self, tmp_path):
        """No discovered edges → empty results."""
        import e0_controller.explore_bootstrap_landscape as mod

        tmp_ls = tmp_path / "learning_state.json"
        ls_data = {
            "_meta": {"source": "test"},
            "discovered_edges": {"edges": []}
        }
        with open(tmp_ls, "w", encoding="utf-8") as f:
            json.dump(ls_data, f, indent=2)

        orig_path = mod.LEARNING_STATE_PATH
        mod.LEARNING_STATE_PATH = str(tmp_ls)
        try:
            bs = load_bootstrap()
            nodes = extract_nodes(bs)
            results = llm_semantic_validation(nodes, dry_run=True)
            assert results == []
        finally:
            mod.LEARNING_STATE_PATH = orig_path


# ---------------------------------------------------------------------------
# Phase H: Executable Transitions
# ---------------------------------------------------------------------------


class TestExecutableTransitions:
    """Phase H: Navigation produces concrete output via LLM execution."""

    def test_execution_templates_cover_all_node_types(self, bootstrap_data):
        """Every node type in bootstrap.json has an execution template."""
        _, nodes, _ = bootstrap_data
        node_types = {n["type"] for n in nodes.values()}
        for ntype in node_types:
            assert ntype in EXECUTION_TEMPLATES, (
                f"No execution template for node type '{ntype}'"
            )

    def test_format_execution_task_per_type(self, bootstrap_data):
        """format_execution_task produces non-empty, type-specific prompts."""
        _, nodes, _ = bootstrap_data
        seen_types = set()
        for nid, node in nodes.items():
            ntype = node["type"]
            if ntype in seen_types:
                continue
            seen_types.add(ntype)
            task = format_execution_task(nodes, nid)
            assert len(task) > 50, f"Task for {nid} ({ntype}) too short"
            # Must contain the node's label
            assert node["label"][:20] in task or ntype in task

    def test_build_execution_context(self, bootstrap_data):
        """build_execution_context includes project state and architecture."""
        bs, nodes, _ = bootstrap_data
        ctx = build_execution_context(bs, nodes, "HERE", "OPEN-1")
        assert "E₀-Framework" in ctx
        assert "Tests:" in ctx
        assert "Architecture layers:" in ctx
        assert "Open threads:" in ctx
        assert "Gordian Traps" in ctx

    def test_execute_bootstrap_transition_dry_run(self, bootstrap_data):
        """dry_run returns preview without calling LLM."""
        bs, nodes, _ = bootstrap_data
        r = execute_bootstrap_transition(bs, nodes, "HERE", "OPEN-1", dry_run=True)
        assert r["source"] == "HERE"
        assert r["target"] == "OPEN-1"
        assert r["outcome"] == "DRY_RUN"
        assert r["target_type"] == "open_thread"
        assert not r["actionable"]
        assert "task_preview" in r
        assert len(r["task_preview"]) > 0

    def test_execute_dry_run_all_types(self, bootstrap_data):
        """dry_run works for every node type."""
        bs, nodes, _ = bootstrap_data
        seen_types = set()
        for nid, node in nodes.items():
            ntype = node["type"]
            if ntype in seen_types:
                continue
            seen_types.add(ntype)
            r = execute_bootstrap_transition(bs, nodes, "HERE", nid, dry_run=True)
            assert r["outcome"] == "DRY_RUN"
            assert r["target_type"] == ntype

    def test_select_transitions_prioritizes_open_threads(self, bootstrap_data):
        """Selection prioritizes open_thread targets over others."""
        _, nodes, edges = bootstrap_data
        # Build a path that visits different node types
        path = ["HERE", "OPEN-1", "L5", "GT-5", "BT-4", "OPEN-2", "L3"]
        spec = build_spec(nodes, edges)
        ls = bootstrap_landscape(spec)
        inject_node_traces(ls, nodes)

        selected = select_transitions_for_execution(path, nodes, ls)
        # Open threads should appear before other types
        assert len(selected) > 0
        target_types = [nodes.get(tgt, {}).get("type") for _, tgt in selected]
        # First entries should be open_thread (priority 3)
        first_open = [t for t in target_types if t == "open_thread"]
        assert len(first_open) >= 1, "At least one open_thread should be selected"

    def test_select_transitions_deduplicates_targets(self, bootstrap_data):
        """Selection doesn't execute the same target twice."""
        _, nodes, edges = bootstrap_data
        # Path with repeated visits to OPEN-1
        path = ["HERE", "OPEN-1", "L5", "OPEN-1", "L3", "OPEN-1"]
        spec = build_spec(nodes, edges)
        ls = bootstrap_landscape(spec)
        inject_node_traces(ls, nodes)

        selected = select_transitions_for_execution(path, nodes, ls)
        targets = [tgt for _, tgt in selected]
        assert len(targets) == len(set(targets)), "Targets should be unique"

    def test_select_transitions_max_limit(self, bootstrap_data):
        """Selection respects max_executions limit."""
        _, nodes, edges = bootstrap_data
        path = ["HERE", "OPEN-1", "OPEN-2", "OPEN-3", "L3", "L5",
                "GT-5", "BT-4", "L6", "L9"]
        spec = build_spec(nodes, edges)
        ls = bootstrap_landscape(spec)
        inject_node_traces(ls, nodes)

        selected = select_transitions_for_execution(
            path, nodes, ls, max_executions=3
        )
        assert len(selected) <= 3

    def test_persist_execution_results_dry_run(self, bootstrap_data):
        """dry_run counts actionable results without writing."""
        results = [
            {"source": "HERE", "target": "OPEN-1", "target_type": "open_thread",
             "outcome": "SUCCESS", "result": "analysis...", "confidence": 0.8,
             "actionable": True},
            {"source": "HERE", "target": "L5", "target_type": "arch_layer",
             "outcome": "SUCCESS", "result": "assessment...", "confidence": 0.3,
             "actionable": False},
        ]
        count = persist_execution_results(results, dry_run=True)
        assert count == 1  # Only 1 actionable

    def test_persist_execution_results_writes_to_file(self, tmp_path, bootstrap_data):
        """Actionable results are written to learning_state.json."""
        import e0_controller.explore_bootstrap_landscape as mod

        tmp_ls = tmp_path / "learning_state.json"
        with open(tmp_ls, "w", encoding="utf-8") as f:
            json.dump({"_meta": {"source": "test"}}, f, indent=2)

        orig_path = mod.LEARNING_STATE_PATH
        mod.LEARNING_STATE_PATH = str(tmp_ls)
        try:
            results = [
                {"source": "HERE", "target": "OPEN-1", "target_type": "open_thread",
                 "outcome": "SUCCESS", "result": "concrete next step: implement X",
                 "confidence": 0.8, "actionable": True},
            ]
            count = persist_execution_results(results)
            assert count == 1

            with open(tmp_ls, encoding="utf-8") as f:
                ls = json.load(f)
            assert "execution_results" in ls
            assert len(ls["execution_results"]["results"]) >= 1
            entry = ls["execution_results"]["results"][-1]
            assert entry["source"] == "HERE"
            assert entry["target"] == "OPEN-1"
            assert "executed_at" in entry
            assert entry["confidence"] == 0.8
        finally:
            mod.LEARNING_STATE_PATH = orig_path
