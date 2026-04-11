"""Tests for E₀ Self-Knowledge Seed (C220).

Validates:
  - Self-learning improves coverage over baseline
  - Export produces valid JSON with expected structure
  - Load restores landscape, unified_nodes, and edge metadata
  - Round-trip (export → load) preserves traces
  - build_session loads seed as warm start
  - Early stagnation exit works
  - Targeted passes and direct inscription reach unreachable nodes
"""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from e0_controller.explore_self_knowledge import (
    SEED_PATH,
    SelfKnowledgeResult,
    _get_visited,
    _inscribe_unreachable,
    _targeted_passes,
    export_seed,
    learn_self,
    load_seed,
)
from e0_controller.snapshot_codec import encode_landscape


# ── Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def learned():
    """Run self-learning once for the whole module (expensive)."""
    landscape, unified_nodes, stats, result = learn_self(
        max_rounds=15, steps_per_round=40, target_coverage=0.95,
        verbose=False,
    )
    return landscape, unified_nodes, stats, result


@pytest.fixture
def seed_path(learned, tmp_path):
    """Export a seed to a temp file and return its path."""
    landscape, unified_nodes, stats, result = learned
    path = str(tmp_path / "test_seed.json")
    export_seed(landscape, unified_nodes, stats, result, path)
    return path


# ── Self-Learning ──────────────────────────────────────────────────────


class TestLearnSelf:
    """Phase 1-3: self-learning cycle."""

    def test_coverage_improves_over_baseline(self, learned):
        """Coverage after learning exceeds the ~54% fresh baseline."""
        _, _, _, result = learned
        assert result.final_coverage > 0.80

    def test_canon_coverage(self, learned):
        """Canon domain reaches meaningful coverage."""
        _, _, _, result = learned
        assert result.canon_coverage > 0.60

    def test_bootstrap_coverage(self, learned):
        """Bootstrap domain starts high and stays high."""
        _, _, _, result = learned
        assert result.bootstrap_coverage > 0.90

    def test_en_coverage(self, learned):
        """EN domain gets explored."""
        _, _, _, result = learned
        assert result.en_coverage > 0.60

    def test_shortcut_edges_created(self, learned):
        """Navigation discovers shortcut edges."""
        _, _, _, result = learned
        assert result.shortcut_edges_created > 0

    def test_result_dataclass(self, learned):
        """Result has all expected fields."""
        _, _, _, result = learned
        assert isinstance(result, SelfKnowledgeResult)
        assert result.rounds > 0
        assert result.total_nodes > 0
        assert result.total_edges > 0


class TestEarlyExit:
    """Stagnation detection exits early."""

    def test_stagnation_exits_before_max(self):
        """With high max_rounds, sustained stagnation triggers early exit."""
        _, _, _, result = learn_self(
            max_rounds=50, steps_per_round=30,
            target_coverage=0.999, verbose=False,
        )
        # Should exit well before 50 rounds due to stagnation
        assert result.rounds < 50


# ── Export ─────────────────────────────────────────────────────────────


class TestExportSeed:
    """Seed JSON structure and content."""

    def test_file_created(self, seed_path):
        """Export creates a JSON file."""
        assert os.path.exists(seed_path)

    def test_valid_json(self, seed_path):
        """File is valid JSON."""
        with open(seed_path) as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_meta_keys(self, seed_path):
        """Meta section has expected keys."""
        with open(seed_path) as f:
            data = json.load(f)
        meta = data["meta"]
        for key in ("version", "coverage", "node_count", "edge_count",
                     "rounds_to_converge", "converged"):
            assert key in meta, f"Missing meta key: {key}"

    def test_landscape_present(self, seed_path):
        """Landscape snapshot is included."""
        with open(seed_path) as f:
            data = json.load(f)
        ls = data["landscape"]
        assert "states" in ls
        assert "edges" in ls
        assert "historization" in ls

    def test_unified_nodes_present(self, seed_path):
        """Unified nodes metadata is included."""
        with open(seed_path) as f:
            data = json.load(f)
        nodes = data["unified_nodes"]
        assert len(nodes) > 100  # 148 expected
        # Check a few expected prefixes exist
        prefixes = {k.split(":")[0] for k in nodes}
        assert "C" in prefixes
        assert "B" in prefixes
        assert "EN" in prefixes

    def test_edge_meta_present(self, seed_path):
        """Edge metadata is included (at least some entries)."""
        with open(seed_path) as f:
            data = json.load(f)
        # May be empty if no metadata was set, but key must exist
        assert "edge_meta" in data

    def test_coverage_matches_result(self, learned, seed_path):
        """Exported coverage matches learning result."""
        _, _, _, result = learned
        with open(seed_path) as f:
            data = json.load(f)
        assert data["meta"]["coverage"] == round(result.final_coverage, 4)


# ── Import ─────────────────────────────────────────────────────────────


class TestLoadSeed:
    """Loading a seed restores full state."""

    def test_load_returns_tuple(self, seed_path):
        """load_seed returns (landscape, unified_nodes, meta)."""
        landscape, unified_nodes, meta = load_seed(seed_path)
        assert landscape is not None
        assert isinstance(unified_nodes, dict)
        assert isinstance(meta, dict)

    def test_states_preserved(self, learned, seed_path):
        """All states are preserved through round-trip."""
        orig_landscape, _, _, _ = learned
        loaded_landscape, _, _ = load_seed(seed_path)
        assert set(loaded_landscape.states) == set(orig_landscape.states)

    def test_edge_count_preserved(self, learned, seed_path):
        """Edge count matches after round-trip."""
        orig_landscape, _, _, _ = learned
        loaded_landscape, _, _ = load_seed(seed_path)
        assert loaded_landscape.edge_count() == orig_landscape.edge_count()

    def test_unified_nodes_preserved(self, learned, seed_path):
        """Unified nodes are identical after round-trip."""
        _, orig_nodes, _, _ = learned
        _, loaded_nodes, _ = load_seed(seed_path)
        assert set(loaded_nodes.keys()) == set(orig_nodes.keys())
        # Spot-check a node's label
        for nid in list(orig_nodes.keys())[:5]:
            assert loaded_nodes[nid]["label"] == orig_nodes[nid]["label"]

    def test_traces_preserved(self, learned, seed_path):
        """Historization traces survive round-trip."""
        orig_landscape, _, _, _ = learned
        loaded_landscape, _, _ = load_seed(seed_path)
        # Compare trace_load on a sample of edges
        sample = list(orig_landscape.edges)[:20]
        for e in sample:
            orig_load = orig_landscape.historization.trace_load(e)
            if loaded_landscape.has_edge(e.source, e.target):
                from e0_controller.primitives import Edge
                le = Edge(e.source, e.target)
                loaded_load = loaded_landscape.historization.trace_load(le)
                assert abs(orig_load - loaded_load) < 0.01, (
                    f"Trace mismatch on {e}: {orig_load} vs {loaded_load}"
                )

    def test_edge_meta_restored(self, learned, seed_path):
        """Edge metadata is restored after round-trip."""
        orig_landscape, _, _, _ = learned
        loaded_landscape, _, _ = load_seed(seed_path)
        # Find some edges with metadata in original
        restored = 0
        for e in list(orig_landscape.edges)[:50]:
            meta = orig_landscape.edge_meta(e.source, e.target)
            if meta:
                loaded_meta = loaded_landscape.edge_meta(e.source, e.target)
                assert loaded_meta == meta, (
                    f"Meta mismatch on {e}: {meta} vs {loaded_meta}"
                )
                restored += 1
        # At least some edges should have metadata
        assert restored > 0


# ── Build Session Integration ──────────────────────────────────────────


class TestBuildSessionWithSeed:
    """build_session loads seed as warm start."""

    def test_warm_start_coverage(self, seed_path):
        """Session built from seed starts with high coverage."""
        from e0_controller.explore_learning_cycle_multidomain import assess
        from e0_controller.interactive_session import build_session

        state = build_session(
            steps_per_round=20,
            self_knowledge_path=seed_path,
        )
        a = assess(state.landscape, state.unified_nodes)
        assert a.coverage > 0.80

    def test_warm_start_stats(self, seed_path):
        """Session stats reflect seed metadata."""
        from e0_controller.interactive_session import build_session

        state = build_session(
            steps_per_round=20,
            self_knowledge_path=seed_path,
        )
        assert state.stats["total_nodes"] > 100
        assert state.stats["seed"] == seed_path

    def test_nonexistent_seed_falls_back(self, tmp_path):
        """build_session with nonexistent seed path builds fresh."""
        from e0_controller.interactive_session import build_session

        fake_path = str(tmp_path / "nonexistent.json")
        state = build_session(
            steps_per_round=20,
            self_knowledge_path=fake_path,
        )
        assert state.landscape is not None
        assert len(state.unified_nodes) > 100


# ── Helpers ────────────────────────────────────────────────────────────


class TestHelpers:
    """Internal helper functions."""

    def test_get_visited(self, learned):
        """_get_visited returns non-empty set after learning."""
        landscape, _, _, _ = learned
        visited = _get_visited(landscape)
        assert len(visited) > 100

    def test_get_visited_fresh(self):
        """_get_visited on fresh landscape returns bootstrap-traced nodes."""
        from e0_controller.explore_learning_cycle_multidomain import (
            build_multidomain_landscape,
        )
        landscape, _, _ = build_multidomain_landscape()
        visited = _get_visited(landscape)
        # Fresh landscape has ~54% coverage from bootstrap traces
        assert len(visited) > 50


# ── Snapshot Codec Fix ─────────────────────────────────────────────────


class TestSnapshotCodecFix:
    """encode_landscape handles confirmations/surprises Edge keys."""

    def test_encode_with_confirmations(self, learned):
        """encode_landscape succeeds when historization has confirmations."""
        landscape, _, _, _ = learned
        data = encode_landscape(landscape)
        assert "historization" in data
        hist = data["historization"]
        # confirmations/surprises should be serialized with string keys
        if "confirmations" in hist:
            for key in hist["confirmations"]:
                assert isinstance(key, str)
        if "surprises" in hist:
            for key in hist["surprises"]:
                assert isinstance(key, str)

    def test_encode_roundtrip_json_safe(self, learned):
        """Full encode_landscape output is JSON-serializable."""
        landscape, _, _, _ = learned
        data = encode_landscape(landscape)
        # This would raise TypeError if any keys aren't serializable
        json_str = json.dumps(data)
        assert len(json_str) > 0
