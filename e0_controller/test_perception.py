"""
Tests for E₀ Perception Ontology (C158)
=========================================
Verify perception primitives, domain bootstrapping, profiles, and ranking.
"""

import pytest

from e0_controller.primitives import Edge, Outcome
from e0_controller.perception import (
    ALL_PRIMITIVES,
    LANGUAGE_PRIMITIVES,
    RENDERING_PRIMITIVES,
    VISUAL_PRIMITIVES,
    PerceptionDomain,
    PerceptionKind,
    PerceptionProfile,
    PerceptionSnapshot,
    build_perception_domain,
    default_perception_spec,
    from_landscape,
    primitive_kind,
)


# ──────────────────────────────────────────────
# 1. Primitive Constants
# ──────────────────────────────────────────────

class TestPrimitiveConstants:
    """Verify the primitive inventories are complete and non-overlapping."""

    def test_visual_count(self):
        assert len(VISUAL_PRIMITIVES) == 10

    def test_language_count(self):
        assert len(LANGUAGE_PRIMITIVES) == 5

    def test_all_primitives_is_union(self):
        assert ALL_PRIMITIVES == VISUAL_PRIMITIVES + LANGUAGE_PRIMITIVES + RENDERING_PRIMITIVES

    def test_no_overlap(self):
        assert set(VISUAL_PRIMITIVES) & set(LANGUAGE_PRIMITIVES) == set()

    def test_primitive_kind_visual(self):
        for p in VISUAL_PRIMITIVES:
            assert primitive_kind(p) == PerceptionKind.VISUAL

    def test_primitive_kind_language(self):
        for p in LANGUAGE_PRIMITIVES:
            assert primitive_kind(p) == PerceptionKind.LANGUAGE

    def test_primitive_kind_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown"):
            primitive_kind("bogus")


# ──────────────────────────────────────────────
# 2. Default Spec
# ──────────────────────────────────────────────

class TestDefaultSpec:
    """Default perception spec is valid and well-formed."""

    def test_spec_has_all_primitives(self):
        spec = default_perception_spec()
        assert set(spec["nodes"]) == set(ALL_PRIMITIVES)

    def test_spec_has_edges(self):
        spec = default_perception_spec()
        assert len(spec["edges"]) == 34

    def test_spec_edges_reference_valid_nodes(self):
        spec = default_perception_spec()
        nodes = set(spec["nodes"])
        for e in spec["edges"]:
            assert e["from"] in nodes, f"Unknown source: {e['from']}"
            assert e["to"] in nodes, f"Unknown target: {e['to']}"

    def test_spec_no_self_loops(self):
        spec = default_perception_spec()
        for e in spec["edges"]:
            assert e["from"] != e["to"]

    def test_spec_confidence_in_range(self):
        spec = default_perception_spec()
        for e in spec["edges"]:
            assert 0.0 <= e.get("confidence", 1.0) <= 1.0


# ──────────────────────────────────────────────
# 3. Domain Building
# ──────────────────────────────────────────────

class TestBuildDomain:
    """build_perception_domain produces a usable PerceptionDomain."""

    def test_default_build(self):
        dom = build_perception_domain()
        assert isinstance(dom, PerceptionDomain)
        assert len(dom.primitives) == 22

    def test_landscape_has_all_states(self):
        dom = build_perception_domain()
        assert dom.landscape.states == set(ALL_PRIMITIVES)

    def test_landscape_has_edges(self):
        dom = build_perception_domain()
        assert dom.landscape.edge_count() == 34

    def test_landscape_inertia_modulation_on(self):
        dom = build_perception_domain()
        assert dom.landscape.inertia_modulation is True

    def test_initial_traces_injected(self):
        dom = build_perception_domain()
        hist = dom.landscape.historization
        edge = Edge("proximity", "grouping")
        assert hist.trace_load(edge) > 0

    def test_confidence_scales_traces(self):
        """Lower confidence → traces closer to balanced (quality ≈ 0)."""
        dom = build_perception_domain()
        hist = dom.landscape.historization
        # High confidence edge: proximity→grouping (0.9)
        high = Edge("proximity", "grouping")
        # Low confidence edge: absence→uncertainty (0.5)
        low = Edge("absence", "uncertainty")
        q_high = abs(hist.trace_quality(high))
        q_low = abs(hist.trace_quality(low))
        assert q_high > q_low

    def test_visual_primitives_property(self):
        dom = build_perception_domain()
        assert set(dom.visual_primitives) == set(VISUAL_PRIMITIVES)

    def test_language_primitives_property(self):
        dom = build_perception_domain()
        assert set(dom.language_primitives) == set(LANGUAGE_PRIMITIVES)

    def test_custom_spec(self):
        spec = {
            "nodes": ["A", "B"],
            "edges": [
                {"from": "A", "to": "B", "delta": 0.5, "resistance": 1.0,
                 "initial_U": 5.0, "initial_F": 1.0, "confidence": 0.8},
            ],
        }
        dom = build_perception_domain(spec)
        assert dom.primitives == ["A", "B"]
        assert dom.landscape.edge_count() == 1


# ──────────────────────────────────────────────
# 4. Perception Profiles
# ──────────────────────────────────────────────

class TestProfiles:
    """Profile extraction from the perception landscape."""

    def test_profile_for_visual_primitive(self):
        dom = build_perception_domain()
        p = dom.profile("emphasis")
        assert p.name == "emphasis"
        assert p.kind == PerceptionKind.VISUAL
        assert p.trace_load > 0
        assert p.outgoing_edges > 0

    def test_profile_for_language_primitive(self):
        dom = build_perception_domain()
        p = dom.profile("question")
        assert p.name == "question"
        assert p.kind == PerceptionKind.LANGUAGE

    def test_profile_unknown_raises(self):
        dom = build_perception_domain()
        with pytest.raises(KeyError, match="Unknown"):
            dom.profile("bogus")

    def test_strength_positive_quality(self):
        dom = build_perception_domain()
        p = dom.profile("proximity")
        # proximity has high U, low F → quality > 0 → strength > 0
        assert p.strength > 0

    def test_strength_clamps_negative(self):
        """Strength is 0 when quality is negative."""
        p = PerceptionProfile(
            name="test", kind=PerceptionKind.VISUAL,
            trace_load=10.0, quality=-0.5,
            outgoing_edges=2, avg_outgoing_quality=-0.3,
        )
        assert p.strength == 0.0


# ──────────────────────────────────────────────
# 5. Snapshot and Ranking
# ──────────────────────────────────────────────

class TestSnapshot:
    """Snapshot provides a complete view and ranking of perception state."""

    def test_snapshot_all_primitives(self):
        dom = build_perception_domain()
        snap = dom.snapshot()
        assert len(snap.profiles) == 22

    def test_snapshot_total_load(self):
        dom = build_perception_domain()
        snap = dom.snapshot()
        assert snap.total_load > 0

    def test_snapshot_visual_language_split(self):
        dom = build_perception_domain()
        snap = dom.snapshot()
        # Both sub-totals should be positive (all have initial traces)
        assert snap.visual_load > 0
        assert snap.language_load > 0

    def test_by_name(self):
        dom = build_perception_domain()
        snap = dom.snapshot()
        p = snap.by_name("hierarchy")
        assert p.name == "hierarchy"

    def test_by_name_unknown_raises(self):
        dom = build_perception_domain()
        snap = dom.snapshot()
        with pytest.raises(KeyError):
            snap.by_name("bogus")

    def test_ranked_returns_all(self):
        dom = build_perception_domain()
        snap = dom.snapshot()
        ranked = snap.ranked()
        assert len(ranked) == 22

    def test_ranked_descending_order(self):
        dom = build_perception_domain()
        snap = dom.snapshot()
        ranked = snap.ranked()
        for i in range(len(ranked) - 1):
            assert ranked[i].strength >= ranked[i + 1].strength

    def test_ranked_filter_by_kind(self):
        dom = build_perception_domain()
        snap = dom.snapshot()
        vis = snap.ranked(PerceptionKind.VISUAL)
        assert all(p.kind == PerceptionKind.VISUAL for p in vis)
        assert len(vis) == 10

    def test_top_returns_n(self):
        dom = build_perception_domain()
        snap = dom.snapshot()
        top3 = snap.top(3)
        assert len(top3) == 3

    def test_top_respects_kind(self):
        dom = build_perception_domain()
        snap = dom.snapshot()
        top2_lang = snap.top(2, PerceptionKind.LANGUAGE)
        assert len(top2_lang) == 2
        assert all(p.kind == PerceptionKind.LANGUAGE for p in top2_lang)


# ──────────────────────────────────────────────
# 6. Suggest Perception
# ──────────────────────────────────────────────

class TestSuggestPerception:
    """suggest_perception returns strongest primitives."""

    def test_suggest_returns_strings(self):
        dom = build_perception_domain()
        result = dom.suggest_perception(3)
        assert len(result) == 3
        assert all(isinstance(s, str) for s in result)

    def test_suggest_are_valid_primitives(self):
        dom = build_perception_domain()
        result = dom.suggest_perception(5)
        for name in result:
            assert name in ALL_PRIMITIVES

    def test_suggest_visual_only(self):
        dom = build_perception_domain()
        result = dom.suggest_perception(3, PerceptionKind.VISUAL)
        for name in result:
            assert name in VISUAL_PRIMITIVES

    def test_suggest_language_only(self):
        dom = build_perception_domain()
        result = dom.suggest_perception(2, PerceptionKind.LANGUAGE)
        for name in result:
            assert name in LANGUAGE_PRIMITIVES


# ──────────────────────────────────────────────
# 7. Historization Integration
# ──────────────────────────────────────────────

class TestHistorizationIntegration:
    """Perception domain evolves through normal E0 historization."""

    def test_outcome_changes_traces(self):
        dom = build_perception_domain()
        edge = Edge("emphasis", "contrast")
        hist = dom.landscape.historization
        load_before = hist.trace_load(edge)
        hist.update(edge, Outcome.SUCCESS)
        load_after = hist.trace_load(edge)
        assert load_after > load_before

    def test_repeated_success_increases_quality(self):
        dom = build_perception_domain()
        edge = Edge("emphasis", "contrast")
        hist = dom.landscape.historization
        for _ in range(10):
            hist.update(edge, Outcome.SUCCESS)
        assert hist.trace_quality(edge) > 0.5

    def test_failure_decreases_quality(self):
        dom = build_perception_domain()
        edge = Edge("emphasis", "contrast")
        hist = dom.landscape.historization
        q_before = hist.trace_quality(edge)
        for _ in range(10):
            hist.update(edge, Outcome.FAILURE)
        q_after = hist.trace_quality(edge)
        assert q_after < q_before

    def test_profile_reflects_historization(self):
        dom = build_perception_domain()
        edge = Edge("emphasis", "contrast")
        hist = dom.landscape.historization
        for _ in range(20):
            hist.update(edge, Outcome.SUCCESS)
        p = dom.profile("emphasis")
        assert p.quality > 0.3
        assert p.strength > 0

    def test_suggest_adapts_to_learning(self):
        """After heavy reinforcement, the reinforced primitive should rank higher."""
        dom = build_perception_domain()
        hist = dom.landscape.historization
        # Heavily reinforce all edges touching "motion"
        motion_edges = [e for e in dom.landscape.edges if e.source == "motion"]
        for edge in motion_edges:
            for _ in range(50):
                hist.update(edge, Outcome.SUCCESS)
        top = dom.suggest_perception(3, PerceptionKind.VISUAL)
        assert "motion" in top


# ──────────────────────────────────────────────
# 8. from_landscape
# ──────────────────────────────────────────────

class TestFromLandscape:
    """from_landscape wraps an existing landscape."""

    def test_wrap_existing(self):
        dom1 = build_perception_domain()
        dom2 = from_landscape(dom1.landscape, dom1.primitives)
        assert dom2.primitives == dom1.primitives
        assert dom2.landscape is dom1.landscape

    def test_wrap_auto_primitives(self):
        dom1 = build_perception_domain()
        dom2 = from_landscape(dom1.landscape)
        assert set(dom2.primitives) == set(ALL_PRIMITIVES)

    def test_wrap_preserves_traces(self):
        dom1 = build_perception_domain()
        hist = dom1.landscape.historization
        edge = Edge("proximity", "grouping")
        for _ in range(10):
            hist.update(edge, Outcome.SUCCESS)
        load = hist.trace_load(edge)
        dom2 = from_landscape(dom1.landscape, dom1.primitives)
        assert dom2.landscape.historization.trace_load(edge) == load
