"""Tests for C206: Typed Navigation — edge metadata influences navigation.

Verifies that:
1. _edge_type_bonus reads relation_type and bridge_type correctly
2. RELATION_TYPE_BONUS and BRIDGE_TYPE_BONUS contain expected entries
3. Typed navigation scores differ from untyped navigation
4. Type usage is tracked and reported in round results
5. Full cycle uses typed navigation (type_usage non-empty)
"""

import pytest

from e0_controller.landscape import Landscape
from e0_controller.primitives import Edge, Outcome
from e0_controller.explore_learning_cycle_multidomain import (
    RELATION_TYPE_BONUS,
    BRIDGE_TYPE_BONUS,
    _edge_type_bonus,
    _domain_of,
    navigate,
    MultiDomainRoundResult,
)


# ── Unit: Bonus Dicts ──────────────────────────────────────────────────


class TestBonusDicts:
    """RELATION_TYPE_BONUS and BRIDGE_TYPE_BONUS are well-formed."""

    def test_relation_type_bonus_has_entries(self):
        assert len(RELATION_TYPE_BONUS) >= 8

    def test_bridge_type_bonus_has_entries(self):
        assert len(BRIDGE_TYPE_BONUS) >= 2

    def test_enables_is_highest_relation(self):
        """enables should be the strongest relation bonus."""
        assert RELATION_TYPE_BONUS["enables"] >= max(
            v for k, v in RELATION_TYPE_BONUS.items() if k != "enables"
        )

    def test_opposite_of_is_penalty(self):
        """opposite_of should be below 1.0 (mild penalty)."""
        assert RELATION_TYPE_BONUS["opposite_of"] < 1.0

    def test_all_bonuses_positive(self):
        """All bonuses must be > 0 (never zero out navigation)."""
        for v in RELATION_TYPE_BONUS.values():
            assert v > 0
        for v in BRIDGE_TYPE_BONUS.values():
            assert v > 0

    def test_en_semantic_bridge_valued(self):
        """EN semantic bridges should be valued above 1.0."""
        assert BRIDGE_TYPE_BONUS["en_semantic"] > 1.0

    def test_static_bridge_valued(self):
        """Static bridges should be valued above 1.0."""
        assert BRIDGE_TYPE_BONUS["static"] > 1.0


# ── Unit: _edge_type_bonus ─────────────────────────────────────────────


class TestEdgeTypeBonus:
    """_edge_type_bonus computes multiplier from edge metadata."""

    def test_no_metadata_returns_1(self):
        """Edge without metadata → neutral bonus."""
        ls = Landscape()
        ls.add_edge("A", "B", 0.5, 1.0)
        assert _edge_type_bonus(ls, "A", "B") == 1.0

    def test_relation_type_applied(self):
        """Edge with relation_type gets that bonus."""
        ls = Landscape()
        ls.add_edge("A", "B", 0.5, 1.0, relation_type="enables")
        bonus = _edge_type_bonus(ls, "A", "B")
        assert bonus == RELATION_TYPE_BONUS["enables"]

    def test_bridge_type_applied(self):
        """Edge with bridge_type gets that bonus."""
        ls = Landscape()
        ls.add_edge("A", "B", 0.5, 1.0, bridge_type="en_semantic")
        bonus = _edge_type_bonus(ls, "A", "B")
        assert bonus == BRIDGE_TYPE_BONUS["en_semantic"]

    def test_both_types_multiply(self):
        """Edge with both relation_type and bridge_type → multiplicative."""
        ls = Landscape()
        ls.add_edge("A", "B", 0.5, 1.0,
                     relation_type="enables", bridge_type="static")
        bonus = _edge_type_bonus(ls, "A", "B")
        expected = RELATION_TYPE_BONUS["enables"] * BRIDGE_TYPE_BONUS["static"]
        assert abs(bonus - expected) < 1e-6

    def test_unknown_type_neutral(self):
        """Unknown relation/bridge types → 1.0 (neutral)."""
        ls = Landscape()
        ls.add_edge("A", "B", 0.5, 1.0, relation_type="unknown_type")
        assert _edge_type_bonus(ls, "A", "B") == 1.0

    def test_nonexistent_edge_returns_1(self):
        """Querying bonus for nonexistent edge → 1.0."""
        ls = Landscape()
        assert _edge_type_bonus(ls, "X", "Y") == 1.0


# ── Unit: Typed navigation changes scoring ─────────────────────────────


class TestTypedNavigationScoring:
    """Type bonuses change which edges are chosen."""

    def _build_choice_landscape(self, type_a="enables", type_b="opposite_of"):
        """Build a landscape where A→B and A→C compete.

        Both have same delta/resistance but different relation types.
        """
        ls = Landscape()
        # A→B: typed with type_a (high bonus expected)
        ls.add_edge("A", "B", 0.5, 1.0, relation_type=type_a)
        # A→C: typed with type_b (low bonus expected)
        ls.add_edge("A", "C", 0.5, 1.0, relation_type=type_b)
        # Need some continuation from B and C so horizon > 1 works
        ls.add_edge("B", "D", 0.5, 1.0)
        ls.add_edge("C", "D", 0.5, 1.0)
        return ls

    def test_enables_preferred_over_opposite_of(self):
        """Navigation prefers 'enables' over 'opposite_of' at equal delta/R0."""
        ls = self._build_choice_landscape("enables", "opposite_of")
        nodes = {
            "A": {"type": "test", "U": 0, "F": 0},
            "B": {"type": "test", "U": 0, "F": 0},
            "C": {"type": "test", "U": 0, "F": 0},
            "D": {"type": "test", "U": 0, "F": 0},
        }
        result = navigate(ls, nodes, mode="explore", steps=1, start="A")
        # Should choose B (enables=1.4) over C (opposite_of=0.85)
        assert result["path"] == ["A", "B"]

    def test_is_a_preferred_over_co_occurs(self):
        """Navigation prefers 'is_a' (1.3) over 'co_occurs' (1.0)."""
        ls = self._build_choice_landscape("is_a", "co_occurs")
        nodes = {
            "A": {"type": "test", "U": 0, "F": 0},
            "B": {"type": "test", "U": 0, "F": 0},
            "C": {"type": "test", "U": 0, "F": 0},
            "D": {"type": "test", "U": 0, "F": 0},
        }
        result = navigate(ls, nodes, mode="explore", steps=1, start="A")
        assert result["path"] == ["A", "B"]

    def test_bridge_bonus_attracts_crossing(self):
        """EN semantic bridge bonus pulls navigation to EN domain."""
        ls = Landscape()
        # B:HERE → C:diff (no bridge type, plain edge)
        ls.add_edge("B:HERE", "C:diff", 0.5, 1.0)
        # B:HERE → EN:thing (en_semantic bridge)
        ls.add_edge("B:HERE", "EN:thing", 0.5, 1.0,
                     bridge_type="en_semantic")
        # Continuations
        ls.add_edge("C:diff", "C:other", 0.5, 1.0)
        ls.add_edge("EN:thing", "EN:other", 0.5, 1.0)
        nodes = {
            "B:HERE": {"type": "state", "U": 0, "F": 0},
            "C:diff": {"type": "canon_concept", "U": 0, "F": 0},
            "C:other": {"type": "canon_concept", "U": 0, "F": 0},
            "EN:thing": {"type": "en_vocabulary", "U": 0, "F": 0},
            "EN:other": {"type": "en_vocabulary", "U": 0, "F": 0},
        }
        result = navigate(ls, nodes, mode="explore", steps=1, start="B:HERE")
        # EN:thing gets bridge bonus (1.25) + cross-domain bonus (1.5)
        # C:diff gets cross-domain bonus (1.5) only
        assert result["path"][1] == "EN:thing"


# ── Integration: Type usage tracking ───────────────────────────────────


class TestTypeUsageTracking:
    """Navigate returns type_usage dict and it appears in RoundResult."""

    def test_navigate_returns_type_usage(self):
        """Navigate result includes type_usage dict."""
        ls = Landscape()
        ls.add_edge("A", "B", 0.5, 1.0, relation_type="is_a")
        ls.add_edge("B", "C", 0.5, 1.0, relation_type="part_of")
        nodes = {
            "A": {"type": "test", "U": 0, "F": 0},
            "B": {"type": "test", "U": 0, "F": 0},
            "C": {"type": "test", "U": 0, "F": 0},
        }
        result = navigate(ls, nodes, mode="explore", steps=5, start="A")
        assert "type_usage" in result
        assert isinstance(result["type_usage"], dict)

    def test_type_usage_counts_correct(self):
        """type_usage counts match actual types traversed."""
        ls = Landscape()
        ls.add_edge("A", "B", 0.5, 1.0, relation_type="is_a")
        ls.add_edge("B", "C", 0.5, 1.0, relation_type="is_a")
        ls.add_edge("C", "D", 0.5, 1.0, relation_type="part_of")
        nodes = {
            "A": {"type": "test", "U": 0, "F": 0},
            "B": {"type": "test", "U": 0, "F": 0},
            "C": {"type": "test", "U": 0, "F": 0},
            "D": {"type": "test", "U": 0, "F": 0},
        }
        result = navigate(ls, nodes, mode="explore", steps=3, start="A")
        usage = result["type_usage"]
        assert usage.get("is_a", 0) == 2
        assert usage.get("part_of", 0) == 1

    def test_empty_type_usage_for_untyped(self):
        """Edges without metadata → empty type_usage."""
        ls = Landscape()
        ls.add_edge("A", "B", 0.5, 1.0)
        ls.add_edge("B", "C", 0.5, 1.0)
        nodes = {
            "A": {"type": "test", "U": 0, "F": 0},
            "B": {"type": "test", "U": 0, "F": 0},
            "C": {"type": "test", "U": 0, "F": 0},
        }
        result = navigate(ls, nodes, mode="explore", steps=3, start="A")
        assert result["type_usage"] == {}


# ── Integration: Full cycle with typed navigation ──────────────────────


class TestFullCycleTyped:
    """Full multidomain learning cycle uses typed navigation."""

    @pytest.fixture(scope="class")
    def cycle_result(self):
        from e0_controller.explore_learning_cycle_multidomain import (
            run_multidomain_cycle,
        )
        history = run_multidomain_cycle(
            max_rounds=3, steps_per_round=20, verbose=False,
        )
        return history

    def test_type_usage_present_in_results(self, cycle_result):
        """Each round result has type_usage."""
        for r in cycle_result:
            assert hasattr(r, "type_usage")

    def test_some_types_used(self, cycle_result):
        """At least some edge types were traversed across all rounds."""
        all_types = set()
        for r in cycle_result:
            all_types.update(r.type_usage.keys())
        assert len(all_types) >= 2, f"Only {all_types} types used"

    def test_bridge_types_used(self, cycle_result):
        """Bridge types (static or en_semantic) appear in type_usage."""
        all_usage = {}
        for r in cycle_result:
            for t, c in r.type_usage.items():
                all_usage[t] = all_usage.get(t, 0) + c
        bridge_types = {"static", "en_semantic"}
        assert bridge_types & set(all_usage.keys()), \
            f"No bridge types in usage: {all_usage}"

    def test_enables_used_more_than_opposite_of(self, cycle_result):
        """enables (bonus 1.4) should be used more than opposite_of (0.85)."""
        all_usage = {}
        for r in cycle_result:
            for t, c in r.type_usage.items():
                all_usage[t] = all_usage.get(t, 0) + c
        enables_count = all_usage.get("enables", 0)
        opposite_count = all_usage.get("opposite_of", 0)
        # enables has 15 edges vs opposite_of 7, AND higher bonus
        # so it should be used at least as much
        assert enables_count >= opposite_count
