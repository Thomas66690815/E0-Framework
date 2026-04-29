"""
Tests for E1Monitor (C288).

Verifies:
  - Node registration + proposed state tracking
  - record_round: outcome recording, deduplication, skip non-E1 / unknown community
  - impact_quality, dampening_factor, impact_profile
  - has_data
  - Serialization round-trip
  - Backward-compat: from_dict(None) → fresh instance
  - DifferenzPort ABC compliance (port_name, record_outcome)
"""

from __future__ import annotations

import pytest

from e0_controller.e1_monitor import E1Monitor
from e0_controller.primitives import Outcome


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _communities(*groups):
    """Build a community list: each group is a list of node ids."""
    return [list(g) for g in groups]


# ──────────────────────────────────────────────────────────────────────────────
# TestE1MonitorRegistration
# ──────────────────────────────────────────────────────────────────────────────

class TestE1MonitorRegistration:
    """Node registration and basic identity."""

    def test_fresh_monitor_has_no_proposed_nodes(self):
        m = E1Monitor()
        assert m.proposed_nodes() == set()

    def test_register_node_adds_to_proposed(self):
        m = E1Monitor()
        m.register_node("T:A", "propose_domain_graph")
        assert "T:A" in m.proposed_nodes()

    def test_register_node_stores_function_name(self):
        m = E1Monitor()
        m.register_node("T:A", "deepen_domain_graph")
        assert m.function_for("T:A") == "deepen_domain_graph"

    def test_register_multiple_nodes(self):
        m = E1Monitor()
        m.register_node("T:A", "propose_domain_graph")
        m.register_node("T:B", "deepen_domain_graph")
        assert m.proposed_nodes() == {"T:A", "T:B"}

    def test_function_for_unknown_node_is_none(self):
        m = E1Monitor()
        assert m.function_for("T:UNKNOWN") is None

    def test_port_name_is_E1(self):
        assert E1Monitor().port_name() == "E1"

    def test_reraise_same_node_updates_function(self):
        m = E1Monitor()
        m.register_node("T:A", "propose_domain_graph")
        m.register_node("T:A", "deepen_domain_graph")
        assert m.function_for("T:A") == "deepen_domain_graph"


# ──────────────────────────────────────────────────────────────────────────────
# TestE1MonitorRecordRound
# ──────────────────────────────────────────────────────────────────────────────

class TestE1MonitorRecordRound:
    """record_round: outcome recording + edge cases."""

    def test_record_round_records_success(self):
        m = E1Monitor()
        m.register_node("T:A", "propose_domain_graph")
        communities = _communities(["T:A", "T:B"])
        m.record_round(["T:A"], Outcome.SUCCESS, communities)
        assert m.has_data()

    def test_record_round_records_failure(self):
        m = E1Monitor()
        m.register_node("T:A", "propose_domain_graph")
        communities = _communities(["T:A"])
        m.record_round(["T:A"], Outcome.FAILURE, communities)
        profile = m.impact_profile()
        assert len(profile) == 1
        assert profile[0]["load"] > 0

    def test_record_round_deduplicates_same_pair(self):
        m = E1Monitor()
        m.register_node("T:A", "propose_domain_graph")
        m.register_node("T:B", "propose_domain_graph")
        communities = _communities(["T:A", "T:B"])  # same community → same pair
        m.record_round(["T:A", "T:B"], Outcome.SUCCESS, communities)
        profile = m.impact_profile()
        # Only one edge: (community=0, function=propose_domain_graph)
        assert len(profile) == 1

    def test_record_round_skips_non_e1_nodes(self):
        m = E1Monitor()
        m.register_node("T:A", "propose_domain_graph")
        communities = _communities(["T:A", "T:X"])
        # Path contains T:X which is NOT registered as E1
        m.record_round(["T:X"], Outcome.SUCCESS, communities)
        assert not m.has_data()

    def test_record_round_skips_empty_path(self):
        m = E1Monitor()
        m.register_node("T:A", "propose_domain_graph")
        communities = _communities(["T:A"])
        m.record_round([], Outcome.SUCCESS, communities)
        assert not m.has_data()

    def test_record_round_skips_empty_communities(self):
        m = E1Monitor()
        m.register_node("T:A", "propose_domain_graph")
        m.record_round(["T:A"], Outcome.SUCCESS, [])
        assert not m.has_data()

    def test_record_round_noop_when_no_proposed_states(self):
        m = E1Monitor()
        communities = _communities(["T:A"])
        m.record_round(["T:A"], Outcome.SUCCESS, communities)
        assert not m.has_data()

    def test_record_round_node_not_in_any_community_skipped(self):
        m = E1Monitor()
        m.register_node("T:ORPHAN", "propose_domain_graph")
        communities = _communities(["T:OTHER"])  # T:ORPHAN not in communities
        m.record_round(["T:ORPHAN"], Outcome.SUCCESS, communities)
        assert not m.has_data()

    def test_record_round_two_functions_two_edges(self):
        m = E1Monitor()
        m.register_node("T:A", "propose_domain_graph")
        m.register_node("T:B", "deepen_domain_graph")
        # Put each in a different community so domain_idx differs
        communities = _communities(["T:A"], ["T:B"])
        m.record_round(["T:A", "T:B"], Outcome.SUCCESS, communities)
        profile = m.impact_profile()
        assert len(profile) == 2


# ──────────────────────────────────────────────────────────────────────────────
# TestE1MonitorImpact
# ──────────────────────────────────────────────────────────────────────────────

class TestE1MonitorImpact:
    """impact_quality, dampening_factor, impact_profile."""

    def test_no_data_quality_is_zero(self):
        assert E1Monitor().impact_quality() == 0.0

    def test_no_data_dampening_is_one(self):
        assert E1Monitor().dampening_factor() == 1.0

    def test_pure_success_quality_positive(self):
        m = E1Monitor()
        m.register_node("T:A", "propose_domain_graph")
        communities = _communities(["T:A"])
        for _ in range(8):
            m.record_round(["T:A"], Outcome.SUCCESS, communities)
        assert m.impact_quality() > 0.0

    def test_pure_failure_quality_negative(self):
        m = E1Monitor()
        m.register_node("T:A", "propose_domain_graph")
        communities = _communities(["T:A"])
        for _ in range(8):
            m.record_round(["T:A"], Outcome.FAILURE, communities)
        assert m.impact_quality() < 0.0

    def test_mixed_dampening_below_one(self):
        m = E1Monitor()
        m.register_node("T:A", "propose_domain_graph")
        communities = _communities(["T:A"])
        for _ in range(4):
            m.record_round(["T:A"], Outcome.SUCCESS, communities)
        for _ in range(4):
            m.record_round(["T:A"], Outcome.FAILURE, communities)
        assert m.dampening_factor() < 1.0

    def test_profile_contains_warn_for_negative_quality(self):
        m = E1Monitor()
        m.register_node("T:A", "propose_domain_graph")
        communities = _communities(["T:A"])
        for _ in range(10):
            m.record_round(["T:A"], Outcome.FAILURE, communities)
        profile = m.impact_profile()
        assert any(p["warn"] for p in profile)

    def test_profile_no_warn_for_positive_quality(self):
        m = E1Monitor()
        m.register_node("T:A", "propose_domain_graph")
        communities = _communities(["T:A"])
        for _ in range(10):
            m.record_round(["T:A"], Outcome.SUCCESS, communities)
        profile = m.impact_profile()
        assert not any(p["warn"] for p in profile)


# ──────────────────────────────────────────────────────────────────────────────
# TestE1MonitorRecordOutcome
# ──────────────────────────────────────────────────────────────────────────────

class TestE1MonitorRecordOutcome:
    """DifferenzPort ABC: record_outcome (aggregate, no path detail)."""

    def test_record_outcome_creates_data(self):
        m = E1Monitor()
        m.record_outcome(Outcome.SUCCESS)
        assert m.has_data()

    def test_record_outcome_aggregate_edge(self):
        m = E1Monitor()
        m.record_outcome(Outcome.SUCCESS)
        profile = m.impact_profile()
        assert len(profile) == 1
        assert profile[0]["edge"].source == "E1"
        assert profile[0]["edge"].target == "aggregate"


# ──────────────────────────────────────────────────────────────────────────────
# TestE1MonitorSerialization
# ──────────────────────────────────────────────────────────────────────────────

class TestE1MonitorSerialization:
    """to_dict / from_dict round-trips and backward-compat."""

    def test_round_trip_preserves_proposed_states(self):
        m = E1Monitor()
        m.register_node("T:A", "propose_domain_graph")
        m.register_node("T:B", "deepen_domain_graph")
        restored = E1Monitor.from_dict(m.to_dict())
        assert restored.proposed_nodes() == {"T:A", "T:B"}

    def test_round_trip_preserves_function_names(self):
        m = E1Monitor()
        m.register_node("T:A", "deepen_domain_graph")
        restored = E1Monitor.from_dict(m.to_dict())
        assert restored.function_for("T:A") == "deepen_domain_graph"

    def test_round_trip_preserves_history(self):
        m = E1Monitor()
        m.register_node("T:A", "propose_domain_graph")
        communities = _communities(["T:A"])
        for _ in range(5):
            m.record_round(["T:A"], Outcome.SUCCESS, communities)
        restored = E1Monitor.from_dict(m.to_dict())
        assert restored.has_data()
        assert restored.impact_quality() > 0.0

    def test_from_dict_none_returns_fresh(self):
        m = E1Monitor.from_dict(None)
        assert isinstance(m, E1Monitor)
        assert not m.has_data()
        assert m.proposed_nodes() == set()

    def test_from_dict_empty_dict_returns_fresh(self):
        m = E1Monitor.from_dict({})
        assert not m.has_data()
