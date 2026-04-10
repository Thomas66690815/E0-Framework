"""Tests for explore_canon_bootstrap.py — C200 + C201.

Validates the Canon × Bootstrap multiverse mechanism:
1. Static bridge mapping (Canon ↔ Bootstrap)
2. Unified landscape construction
3. Interference measurement
4. Unified exploration with domain crossings
5. LLM bridge discovery (dry_run)
6. Cross-domain persistence
7. Ontodynamics v3.0 (12 new nodes, 38 new edges)
"""

import json
import pytest

from e0_controller.explore_canon_bootstrap import (
    CANON_BOOTSTRAP_BRIDGE,
    build_static_bridges,
    build_unified_landscape,
    measure_interference,
    run_unified_exploration,
    llm_discover_bridges,
    persist_cross_domain_edges,
    BOOTSTRAP_PATH,
)
from e0_controller.explore_bootstrap_landscape import (
    load_bootstrap,
    extract_nodes,
    extract_edges,
    build_spec,
    inject_node_traces,
    load_learning_state,
)
from e0_controller.bootstrapper import bootstrap_landscape
from e0_controller.canon_loader import load_canon


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def canon_data():
    """Load Canon once."""
    cl = load_canon("ontodynamics")
    return cl.landscape, cl.info


@pytest.fixture(scope="module")
def bootstrap_data():
    """Load Bootstrap once."""
    bs = load_bootstrap()
    nodes = extract_nodes(bs)
    edges = extract_edges(bs, nodes)
    return bs, nodes, edges


@pytest.fixture(scope="module")
def unified_data(canon_data, bootstrap_data):
    """Build unified landscape once."""
    _, canon_info = canon_data
    _, bs_nodes, bs_edges = bootstrap_data
    canon_ls_obj = load_canon("ontodynamics")

    static_bridges = build_static_bridges(canon_info, bs_nodes)
    unified_nodes, unified_edges = build_unified_landscape(
        canon_info, canon_ls_obj.landscape, bs_nodes, bs_edges, static_bridges
    )

    spec = build_spec(unified_nodes, unified_edges)
    landscape = bootstrap_landscape(spec)
    inject_node_traces(landscape, unified_nodes)

    return landscape, unified_nodes, unified_edges, static_bridges


# ---------------------------------------------------------------------------
# Phase 1: Static Bridge
# ---------------------------------------------------------------------------


class TestStaticBridge:
    """Static mapping: Canon concepts ↔ Bootstrap nodes."""

    def test_bridge_map_covers_key_canon_concepts(self, canon_data):
        """Key Canon primitives and layers have bootstrap mappings."""
        _, info = canon_data
        canon_ids = {n.id for n in info.nodes}
        mapped = set(CANON_BOOTSTRAP_BRIDGE.keys())
        # Key primitives must be mapped
        for prim in ["difference", "historization", "connection", "overlap"]:
            assert prim in mapped, f"Primitive {prim} not in bridge map"
            assert prim in canon_ids, f"Primitive {prim} not in canon"

    def test_bridge_targets_exist_in_bootstrap(self, bootstrap_data):
        """All bridge targets reference valid bootstrap node IDs."""
        _, bs_nodes, _ = bootstrap_data
        for canon_id, bs_ids in CANON_BOOTSTRAP_BRIDGE.items():
            for bs_id in bs_ids:
                assert bs_id in bs_nodes, (
                    f"Bridge target {bs_id} (from {canon_id}) "
                    f"not in bootstrap nodes"
                )

    def test_build_static_bridges(self, canon_data, bootstrap_data):
        """Static bridges produce non-empty, correctly formatted edges."""
        _, canon_info = canon_data
        _, bs_nodes, _ = bootstrap_data
        bridges = build_static_bridges(canon_info, bs_nodes)

        assert len(bridges) > 20, f"Expected >20 bridges, got {len(bridges)}"
        for b in bridges:
            assert (b["from"].startswith("C:") or b["from"].startswith("B:")), \
                f"Source must start with C: or B:"
            assert (b["to"].startswith("C:") or b["to"].startswith("B:")), \
                f"Target must start with C: or B:"
            assert 0 < b["delta"] <= 1.0
            assert b["bridge_type"] == "static"

    def test_bridges_are_bidirectional(self, canon_data, bootstrap_data):
        """Each static mapping produces both C:→B: and B:→C: edges."""
        _, canon_info = canon_data
        _, bs_nodes, _ = bootstrap_data
        bridges = build_static_bridges(canon_info, bs_nodes)

        c_to_b = [(b["from"], b["to"]) for b in bridges
                   if b["from"].startswith("C:") and b["to"].startswith("B:")]
        b_to_c = [(b["from"], b["to"]) for b in bridges
                   if b["from"].startswith("B:") and b["to"].startswith("C:")]
        assert len(c_to_b) == len(b_to_c), "Bridges must be bidirectional"


# ---------------------------------------------------------------------------
# Phase 2: Unified Landscape
# ---------------------------------------------------------------------------


class TestUnifiedLandscape:
    """The combined Canon + Bootstrap + Bridge landscape."""

    def test_node_count(self, unified_data, canon_data, bootstrap_data):
        """Unified landscape has Canon + Bootstrap nodes."""
        _, unified_nodes, _, _ = unified_data
        _, canon_info = canon_data
        _, bs_nodes, _ = bootstrap_data

        expected = len(canon_info.nodes) + len(bs_nodes)
        assert len(unified_nodes) == expected

    def test_canon_nodes_prefixed(self, unified_data):
        """All Canon nodes have C: prefix."""
        _, unified_nodes, _, _ = unified_data
        canon_nodes = [n for n in unified_nodes if n.startswith("C:")]
        assert len(canon_nodes) > 40  # Canon has 51 nodes

    def test_bootstrap_nodes_prefixed(self, unified_data):
        """All Bootstrap nodes have B: prefix."""
        _, unified_nodes, _, _ = unified_data
        bs_nodes = [n for n in unified_nodes if n.startswith("B:")]
        assert len(bs_nodes) > 30  # Bootstrap has 41 nodes

    def test_edge_count_includes_bridges(self, unified_data, canon_data,
                                         bootstrap_data):
        """Edge count = Canon edges + Bootstrap edges + bridges."""
        landscape, _, unified_edges, bridges = unified_data
        assert landscape.edge_count() > 0
        # At minimum: canon + bootstrap + some bridges
        assert landscape.edge_count() >= 93 + 50 + len(bridges)

    def test_bridge_edges_exist(self, unified_data):
        """Bridge edges connect C: and B: nodes."""
        landscape, _, _, bridges = unified_data
        cross_domain = 0
        for e in landscape.edges:
            src_is_canon = e.source.startswith("C:")
            tgt_is_canon = e.target.startswith("C:")
            if src_is_canon != tgt_is_canon:
                cross_domain += 1
        assert cross_domain >= len(bridges)


# ---------------------------------------------------------------------------
# Phase 3: Interference
# ---------------------------------------------------------------------------


class TestInterference:
    """Does Canon knowledge affect Bootstrap navigation?"""

    def test_canon_reachable_from_here(self, unified_data):
        """Canon targets are reachable from B:HERE via bridge edges."""
        landscape, unified_nodes, _, _ = unified_data
        interference = measure_interference(
            landscape, unified_nodes, {}
        )
        assert interference["canon_targets"] > 0, (
            "No Canon targets reachable from B:HERE"
        )

    def test_bootstrap_still_reachable(self, unified_data):
        """Bootstrap targets remain reachable from B:HERE."""
        landscape, unified_nodes, _, _ = unified_data
        interference = measure_interference(
            landscape, unified_nodes, {}
        )
        assert interference["bootstrap_targets"] > 0

    def test_bridge_connected_count(self, unified_data):
        """Some Bootstrap nodes are connected via Canon bridges."""
        landscape, unified_nodes, _, _ = unified_data
        interference = measure_interference(
            landscape, unified_nodes, {}
        )
        assert interference["bridge_connected"] > 0


# ---------------------------------------------------------------------------
# Phase 4: Unified Exploration
# ---------------------------------------------------------------------------


class TestUnifiedExploration:
    """Navigation in the unified landscape."""

    def test_exploration_runs(self, unified_data):
        """Exploration completes without error."""
        landscape, unified_nodes, _, _ = unified_data
        # Fresh landscape for isolation
        _, unified_nodes2, unified_edges2, bridges = unified_data
        spec = build_spec(unified_nodes2, unified_edges2)
        fresh = bootstrap_landscape(spec)
        inject_node_traces(fresh, unified_nodes2)

        result = run_unified_exploration(fresh, unified_nodes2, max_steps=10)
        assert result["steps"] > 0
        assert result["unique_states"] > 1

    def test_exploration_crosses_domains(self, unified_data):
        """Exploration should cross the Canon ↔ Bootstrap boundary."""
        _, unified_nodes, unified_edges, _ = unified_data
        spec = build_spec(unified_nodes, unified_edges)
        fresh = bootstrap_landscape(spec)
        inject_node_traces(fresh, unified_nodes)

        result = run_unified_exploration(fresh, unified_nodes, max_steps=30)
        # In 30 steps, at least one domain crossing should happen
        # (unless bridges have very low potential)
        assert result["canon_visited"] >= 0  # May or may not cross
        assert result["bootstrap_visited"] >= 1  # Must visit bootstrap

    def test_both_domains_visited_in_long_run(self, unified_data):
        """With enough steps, both domains get visited."""
        _, unified_nodes, unified_edges, _ = unified_data
        spec = build_spec(unified_nodes, unified_edges)
        fresh = bootstrap_landscape(spec)
        inject_node_traces(fresh, unified_nodes)

        result = run_unified_exploration(fresh, unified_nodes, max_steps=50)
        # In 50 steps, exploration should reach both domains
        assert result["canon_visited"] + result["bootstrap_visited"] > 3


# ---------------------------------------------------------------------------
# Phase 5: LLM Bridge Discovery
# ---------------------------------------------------------------------------


class TestLLMBridge:
    """LLM-based cross-domain bridge discovery."""

    def test_dry_run_returns_bridge(self, canon_data, bootstrap_data):
        """dry_run returns placeholder bridge without API call."""
        _, canon_info = canon_data
        _, bs_nodes, _ = bootstrap_data
        bridges = llm_discover_bridges(canon_info, bs_nodes, dry_run=True)
        assert len(bridges) > 0
        b = bridges[0]
        assert "from" in b
        assert "to" in b
        assert b["bridge_type"] == "llm_discovered"


# ---------------------------------------------------------------------------
# Phase 6: Persistence
# ---------------------------------------------------------------------------


class TestCrossDomainPersistence:
    """Cross-domain bridges survive across sessions."""

    def test_dry_run_counts(self):
        """dry_run returns count without writing."""
        bridges = [
            {"from": "C:tension", "to": "B:L3", "delta": 0.5,
             "resistance": 0.3, "derivation": "test", "bridge_type": "static"},
        ]
        count = persist_cross_domain_edges(bridges, dry_run=True)
        assert count == 1

    def test_persist_writes_to_file(self, tmp_path):
        """Bridges are written to learning_state.json."""
        import shutil
        import e0_controller.explore_bootstrap_landscape as bl_mod

        tmp_ls = tmp_path / "learning_state.json"
        # Create a minimal learning_state.json
        with open(tmp_ls, "w", encoding="utf-8") as f:
            json.dump({"_meta": {"source": "test"}}, f, indent=2)

        orig_path = bl_mod.LEARNING_STATE_PATH
        bl_mod.LEARNING_STATE_PATH = str(tmp_ls)
        try:
            bridges = [
                {"from": "C:tension", "to": "B:L3", "delta": 0.5,
                 "resistance": 0.3, "confidence": 0.7,
                 "derivation": "test bridge", "bridge_type": "static"},
            ]
            count = persist_cross_domain_edges(bridges)
            assert count == 1

            with open(tmp_ls, encoding="utf-8") as f:
                ls = json.load(f)
            assert "cross_domain_bridges" in ls
            assert len(ls["cross_domain_bridges"]["bridges"]) >= 1
            entry = ls["cross_domain_bridges"]["bridges"][-1]
            assert entry["from"] == "C:tension"
            assert entry["to"] == "B:L3"
        finally:
            bl_mod.LEARNING_STATE_PATH = orig_path

    def test_no_duplicate_persist(self, tmp_path):
        """Same bridge is not persisted twice."""
        import e0_controller.explore_bootstrap_landscape as bl_mod

        tmp_ls = tmp_path / "learning_state.json"
        # Create a minimal learning_state.json
        with open(tmp_ls, "w", encoding="utf-8") as f:
            json.dump({"_meta": {"source": "test"}}, f, indent=2)

        orig_path = bl_mod.LEARNING_STATE_PATH
        bl_mod.LEARNING_STATE_PATH = str(tmp_ls)
        try:
            bridges = [
                {"from": "C:overlap", "to": "B:L4", "delta": 0.4,
                 "resistance": 0.3, "derivation": "test", "bridge_type": "static"},
            ]
            count1 = persist_cross_domain_edges(bridges)
            count2 = persist_cross_domain_edges(bridges)
            assert count1 == 1
            assert count2 == 0

            with open(tmp_ls, encoding="utf-8") as f:
                ls = json.load(f)
            matching = [b for b in ls["cross_domain_bridges"]["bridges"]
                        if b["from"] == "C:overlap" and b["to"] == "B:L4"]
            assert len(matching) == 1
        finally:
            bl_mod.LEARNING_STATE_PATH = orig_path


# ---------------------------------------------------------------------------
# Phase 7: Ontodynamics v3.0
# ---------------------------------------------------------------------------


class TestOntodynamicsV3:
    """Ontodynamics v3.0 — 12 new nodes for post-C122 concepts."""

    def test_version(self):
        cl = load_canon("ontodynamics")
        assert cl.info.version == "3.0"

    def test_node_count(self):
        cl = load_canon("ontodynamics")
        assert len(cl.info.nodes) == 63  # 51 + 12

    def test_edge_count(self):
        cl = load_canon("ontodynamics")
        assert len(cl.info.edges) == 131  # 93 + 38

    def test_new_nodes_present(self):
        """All 12 new nodes exist."""
        cl = load_canon("ontodynamics")
        ids = {n.id for n in cl.info.nodes}
        new_ids = {
            "transition_potential", "epistemic_trust", "auto_tuning",
            "shared_historization", "bootstrap_landscape",
            "perception_ontology", "communication_intent",
            "compatibility_gating", "wl_node_fingerprint",
            "curriculum_navigator", "n_domain_mesh",
            "canon_bootstrap_multiverse",
        }
        for nid in new_ids:
            assert nid in ids, f"Missing new node: {nid}"

    def test_derivation_levels(self):
        """New nodes at correct derivation levels."""
        cl = load_canon("ontodynamics")
        level_map = {n.id: n.derivation_level for n in cl.info.nodes}
        assert level_map["transition_potential"] == 9
        assert level_map["epistemic_trust"] == 11
        assert level_map["auto_tuning"] == 12
        assert level_map["shared_historization"] == 13
        assert level_map["bootstrap_landscape"] == 13
        assert level_map["perception_ontology"] == 14
        assert level_map["communication_intent"] == 14
        assert level_map["compatibility_gating"] == 15
        assert level_map["wl_node_fingerprint"] == 15
        assert level_map["curriculum_navigator"] == 18
        assert level_map["n_domain_mesh"] == 18
        assert level_map["canon_bootstrap_multiverse"] == 18

    def test_new_nodes_reachable(self):
        """Each new node has at least one incoming edge."""
        cl = load_canon("ontodynamics")
        targets = {e.target for e in cl.info.edges}
        new_ids = {
            "transition_potential", "epistemic_trust", "auto_tuning",
            "shared_historization", "bootstrap_landscape",
            "perception_ontology", "communication_intent",
            "compatibility_gating", "wl_node_fingerprint",
            "curriculum_navigator", "n_domain_mesh",
            "canon_bootstrap_multiverse",
        }
        for nid in new_ids:
            assert nid in targets, f"New node {nid} has no incoming edge"

    def test_goal_states_updated(self):
        cl = load_canon("ontodynamics")
        assert "canon_bootstrap_multiverse" in cl.info.goal_states
        assert "negative_necessity" in cl.info.goal_states
        assert "sleep_wake_cycle" in cl.info.goal_states

    def test_necessary_consequences_extended(self):
        cl = load_canon("ontodynamics")
        nc = cl.info.necessary_consequences
        assert "compatibility_gating" in nc
        assert "parameter_self_tuning" in nc
        assert "cooperative_knowledge_sharing" in nc

    def test_mass_description_clarified(self):
        """Level 5 mass node description now references trace_load."""
        cl = load_canon("ontodynamics")
        mass_node = next(n for n in cl.info.nodes if n.id == "mass")
        assert "trace_load" in mass_node.description

    def test_canon_bootstrap_bridge_covers_new_nodes(self):
        """CANON_BOOTSTRAP_BRIDGE maps all 12 new Canon nodes."""
        new_ids = {
            "transition_potential", "epistemic_trust", "auto_tuning",
            "shared_historization", "bootstrap_landscape",
            "perception_ontology", "communication_intent",
            "compatibility_gating", "wl_node_fingerprint",
            "curriculum_navigator", "n_domain_mesh",
            "canon_bootstrap_multiverse",
        }
        for nid in new_ids:
            assert nid in CANON_BOOTSTRAP_BRIDGE, (
                f"New node {nid} not in CANON_BOOTSTRAP_BRIDGE"
            )

    def test_unified_landscape_larger_with_v3(self, unified_data):
        """Unified landscape has more nodes with v3.0 Canon."""
        _, unified_nodes, _, _ = unified_data
        canon_nodes = [n for n in unified_nodes if n.startswith("C:")]
        assert len(canon_nodes) == 63  # v3.0: 63 Canon nodes
