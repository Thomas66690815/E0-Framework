"""Tests for C205: Edge Metadata in Landscape.

Verifies that edge metadata (relation_type, derivation, confidence, bridge_type)
survives the full pipeline from JSON → canon_loader → bootstrapper → Landscape.
"""

import json
import pytest

from e0_controller.landscape import Landscape
from e0_controller.primitives import Edge
from e0_controller.bootstrapper import bootstrap_landscape
from e0_controller.canon_loader import load_canon


# ── Unit: Landscape._metadata ───────────────────────────────────────────


class TestLandscapeMetadata:
    """Core metadata storage on the Landscape."""

    def test_add_edge_no_metadata(self):
        """Existing callers without metadata still work."""
        ls = Landscape()
        ls.add_edge("A", "B", 0.5, 1.0)
        assert ls.has_edge("A", "B")
        assert ls.edge_meta("A", "B") == {}

    def test_add_edge_with_metadata(self):
        """Metadata kwargs are stored on the edge."""
        ls = Landscape()
        ls.add_edge("A", "B", 0.5, 1.0,
                     relation_type="is_a", derivation="test")
        meta = ls.edge_meta("A", "B")
        assert meta["relation_type"] == "is_a"
        assert meta["derivation"] == "test"

    def test_metadata_per_edge(self):
        """Different edges carry independent metadata."""
        ls = Landscape()
        ls.add_edge("A", "B", 0.5, 1.0, relation_type="is_a")
        ls.add_edge("B", "C", 0.3, 0.5, relation_type="part_of")
        assert ls.edge_meta("A", "B")["relation_type"] == "is_a"
        assert ls.edge_meta("B", "C")["relation_type"] == "part_of"

    def test_edge_meta_nonexistent(self):
        """Querying metadata for a nonexistent edge returns empty dict."""
        ls = Landscape()
        assert ls.edge_meta("X", "Y") == {}

    def test_set_edge_meta(self):
        """set_edge_meta merges new keys into existing metadata."""
        ls = Landscape()
        ls.add_edge("A", "B", 0.5, 1.0, relation_type="is_a")
        ls.set_edge_meta("A", "B", confidence=0.9, bridge_type="static")
        meta = ls.edge_meta("A", "B")
        assert meta["relation_type"] == "is_a"  # preserved
        assert meta["confidence"] == 0.9  # added
        assert meta["bridge_type"] == "static"  # added

    def test_set_edge_meta_nonexistent_raises(self):
        """set_edge_meta on nonexistent edge raises KeyError."""
        ls = Landscape()
        with pytest.raises(KeyError):
            ls.set_edge_meta("X", "Y", foo="bar")

    def test_remove_edge_cleans_metadata(self):
        """Removing an edge also removes its metadata."""
        ls = Landscape()
        ls.add_edge("A", "B", 0.5, 1.0, relation_type="is_a")
        ls.remove_edge("A", "B")
        assert ls.edge_meta("A", "B") == {}

    def test_remove_state_cleans_metadata(self):
        """Removing a state cleans metadata for all incident edges."""
        ls = Landscape()
        ls.add_edge("A", "B", 0.5, 1.0, relation_type="is_a")
        ls.add_edge("B", "C", 0.3, 0.5, relation_type="part_of")
        ls.remove_state("B")
        assert ls.edge_meta("A", "B") == {}
        assert ls.edge_meta("B", "C") == {}

    def test_metadata_does_not_affect_navigation(self):
        """Metadata is passive — delta/R0/tension unchanged."""
        ls = Landscape()
        ls.add_edge("A", "B", 0.5, 1.0, relation_type="is_a",
                     derivation="derives from A")
        assert ls.difference("A", "B") == 0.5
        assert ls.base_resistance("A", "B") == 1.0
        assert ls.effective_tension("A", "B") > 0


# ── Integration: Bootstrapper ───────────────────────────────────────────


class TestBootstrapperMetadata:
    """Bootstrapper passes confidence through to edge metadata."""

    def test_confidence_in_metadata(self):
        """bootstrap_landscape stores confidence in edge metadata."""
        spec = {
            "nodes": ["A", "B"],
            "edges": [{"from": "A", "to": "B", "delta": 0.5,
                        "resistance": 1.0, "confidence": 0.8}],
        }
        ls = bootstrap_landscape(spec)
        meta = ls.edge_meta("A", "B")
        assert meta.get("confidence") == 0.8

    def test_default_confidence_in_metadata(self):
        """Default confidence (1.0) is stored when not specified."""
        spec = {
            "nodes": ["A", "B"],
            "edges": [{"from": "A", "to": "B", "delta": 0.5,
                        "resistance": 1.0}],
        }
        ls = bootstrap_landscape(spec)
        meta = ls.edge_meta("A", "B")
        assert meta.get("confidence") == 1.0


# ── Integration: Canon Loader ───────────────────────────────────────────


class TestCanonMetadata:
    """Canon loader injects edge metadata from JSON spec."""

    @pytest.fixture(scope="class")
    def en_canon(self):
        return load_canon("english_basic_enriched")

    @pytest.fixture(scope="class")
    def onto_canon(self):
        return load_canon("ontodynamics")

    def test_en_edges_have_relation_type(self, en_canon):
        """EN canon edges carry relation_type from JSON 'type' field."""
        ls = en_canon.landscape
        edges_with_type = [
            e for e in ls.edges
            if ls.edge_meta(e.source, e.target).get("relation_type")
        ]
        assert len(edges_with_type) > 0, "EN edges should have relation_type"

    def test_en_relation_types_meaningful(self, en_canon):
        """EN relation types include known values like is_a, part_of."""
        ls = en_canon.landscape
        types = set()
        for e in ls.edges:
            rt = ls.edge_meta(e.source, e.target).get("relation_type", "")
            if rt:
                types.add(rt)
        assert len(types) >= 2, f"Expected multiple relation types, got {types}"

    def test_en_edges_have_derivation(self, en_canon):
        """EN canon edges carry derivation text."""
        ls = en_canon.landscape
        edges_with_deriv = [
            e for e in ls.edges
            if ls.edge_meta(e.source, e.target).get("derivation")
        ]
        assert len(edges_with_deriv) > 0

    def test_onto_edges_have_derivation(self, onto_canon):
        """Ontodynamics canon edges carry derivation text."""
        ls = onto_canon.landscape
        edges_with_deriv = [
            e for e in ls.edges
            if ls.edge_meta(e.source, e.target).get("derivation")
        ]
        assert len(edges_with_deriv) > 0

    def test_canon_metadata_count(self, onto_canon):
        """Most Ontodynamics edges should have some metadata."""
        ls = onto_canon.landscape
        total = len(list(ls.edges))
        with_meta = sum(
            1 for e in ls.edges
            if ls.edge_meta(e.source, e.target)
        )
        ratio = with_meta / max(1, total)
        assert ratio > 0.5, f"Only {ratio:.0%} of edges have metadata"


# ── Integration: inject_edge_metadata ───────────────────────────────────


class TestInjectEdgeMetadata:
    """The inject_edge_metadata utility wires metadata from edge dicts."""

    def test_injects_from_dicts(self):
        from e0_controller.explore_bootstrap_landscape import inject_edge_metadata
        ls = Landscape()
        ls.add_edge("A", "B", 0.5, 1.0)
        edges = [{"from": "A", "to": "B", "derivation": "test",
                   "bridge_type": "static", "confidence": 0.7}]
        inject_edge_metadata(ls, edges)
        meta = ls.edge_meta("A", "B")
        assert meta["derivation"] == "test"
        assert meta["bridge_type"] == "static"
        assert meta["confidence"] == 0.7

    def test_normalizes_type_to_relation_type(self):
        from e0_controller.explore_bootstrap_landscape import inject_edge_metadata
        ls = Landscape()
        ls.add_edge("A", "B", 0.5, 1.0)
        edges = [{"from": "A", "to": "B", "type": "is_a"}]
        inject_edge_metadata(ls, edges)
        meta = ls.edge_meta("A", "B")
        assert meta["relation_type"] == "is_a"
        assert "type" not in meta  # normalized

    def test_skips_missing_edges(self):
        from e0_controller.explore_bootstrap_landscape import inject_edge_metadata
        ls = Landscape()
        ls.add_edge("A", "B", 0.5, 1.0)
        edges = [{"from": "X", "to": "Y", "derivation": "ghost"}]
        inject_edge_metadata(ls, edges)  # should not raise
        assert ls.edge_meta("A", "B") == {}


# ── Integration: Multidomain Landscape ──────────────────────────────────


class TestMultidomainMetadata:
    """C204 multidomain landscape carries edge metadata after C205."""

    @pytest.fixture(scope="class")
    def multidomain(self):
        from e0_controller.explore_learning_cycle_multidomain import (
            build_multidomain_landscape,
        )
        landscape, nodes, stats = build_multidomain_landscape(include_en=True)
        return landscape, nodes, stats

    def test_en_bridges_have_bridge_type(self, multidomain):
        """EN↔Canon/Bootstrap bridges carry bridge_type='en_semantic'."""
        ls, nodes, _ = multidomain
        en_bridges = [
            e for e in ls.edges
            if ls.edge_meta(e.source, e.target).get("bridge_type") == "en_semantic"
        ]
        assert len(en_bridges) > 0, "EN bridges should have bridge_type"

    def test_en_intra_edges_have_relation_type(self, multidomain):
        """EN intra-domain edges carry relation_type from JSON."""
        ls, nodes, _ = multidomain
        en_typed = [
            e for e in ls.edges
            if e.source.startswith("EN:") and e.target.startswith("EN:")
            and ls.edge_meta(e.source, e.target).get("relation_type")
        ]
        assert len(en_typed) > 0, "EN edges should carry relation_type"

    def test_canon_edges_have_derivation(self, multidomain):
        """Canon edges carry derivation text."""
        ls, nodes, _ = multidomain
        canon_derived = [
            e for e in ls.edges
            if e.source.startswith("C:") and e.target.startswith("C:")
            and ls.edge_meta(e.source, e.target).get("derivation")
        ]
        assert len(canon_derived) > 0

    def test_bootstrap_edges_have_derivation(self, multidomain):
        """Bootstrap edges carry derivation text."""
        ls, nodes, _ = multidomain
        bs_derived = [
            e for e in ls.edges
            if e.source.startswith("B:") and e.target.startswith("B:")
            and ls.edge_meta(e.source, e.target).get("derivation")
        ]
        assert len(bs_derived) > 0

    def test_static_bridges_have_metadata(self, multidomain):
        """Canon↔Bootstrap static bridges carry bridge_type and derivation."""
        ls, nodes, _ = multidomain
        static = [
            e for e in ls.edges
            if ls.edge_meta(e.source, e.target).get("bridge_type") == "static"
        ]
        assert len(static) > 0, "Static bridges should be tagged"
        # Check they also have derivation
        for e in static[:3]:
            meta = ls.edge_meta(e.source, e.target)
            assert "derivation" in meta

    def test_metadata_coverage(self, multidomain):
        """Most edges in unified landscape should carry some metadata."""
        ls, nodes, _ = multidomain
        total = len(list(ls.edges))
        with_meta = sum(
            1 for e in ls.edges
            if ls.edge_meta(e.source, e.target)
        )
        ratio = with_meta / max(1, total)
        assert ratio > 0.7, f"Only {ratio:.0%} of edges have metadata — expected >70%"

    def test_three_metadata_types_present(self, multidomain):
        """At least three distinct metadata keys appear across all edges."""
        ls, nodes, _ = multidomain
        all_keys = set()
        for e in ls.edges:
            all_keys.update(ls.edge_meta(e.source, e.target).keys())
        assert len(all_keys) >= 3, f"Only {all_keys} metadata keys found"
