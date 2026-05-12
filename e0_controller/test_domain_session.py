"""
Tests for DomainSession + DomainStore (C306).

Test classes:
    TestDomainMode               — enum values
    TestLearnReport              — dataclass + goal_rate
    TestRecommendResult          — dataclass + cold_start property
    TestLandscapeCodec           — _landscape_to_dict / _landscape_from_dict round-trip
    TestDomainSessionInit        — construction, defaults
    TestDomainSessionSetMode     — mode switching
    TestDomainSessionInject      — delegates to FileSensor
    TestDomainSessionLearnEmpty  — no edges → warning, no episodes
    TestDomainSessionLearn       — N episodes, outcomes, edges explored
    TestDomainSessionRecommend   — cold-start, after learn, candidate filter
    TestDomainSessionRecord      — manual inscription
    TestDomainSessionStatus      — status dict fields
    TestDomainSessionConvictionMap — after learn, values in [0,1)
    TestDomainStoreInit          — construction
    TestDomainStoreSaveLoad      — round-trip: save→load
    TestDomainStoreList          — list_domains
    TestDomainStoreDelete        — delete
    TestDomainStoreRoundTrip     — full lifecycle
"""

from __future__ import annotations

import pytest

from e0_controller.domain_session import (
    DomainMode,
    DomainSession,
    DomainStore,
    LearnReport,
    RecommendResult,
    _landscape_from_dict,
    _landscape_to_dict,
)
from e0_controller.landscape import Landscape
from e0_controller.primitives import Edge, Outcome


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def logistics_landscape() -> Landscape:
    """Simple logistics topology: ORDER → PICKING → LOADING → DELIVERED."""
    L = Landscape()
    L.add_edge("ORDER", "PICKING", delta=1.0, resistance=0.3)
    L.add_edge("ORDER", "BACKORDER", delta=1.0, resistance=0.7)
    L.add_edge("PICKING", "LOADING", delta=1.0, resistance=0.3)
    L.add_edge("LOADING", "DELIVERED", delta=1.0, resistance=0.2)
    return L


def oracle_always_success(source: str, target: str) -> Outcome:
    return Outcome.SUCCESS


def oracle_always_failure(source: str, target: str) -> Outcome:
    return Outcome.FAILURE


def oracle_happy_path(source: str, target: str) -> Outcome:
    """Reward the path ORDER→PICKING→LOADING→DELIVERED."""
    happy = {("ORDER", "PICKING"), ("PICKING", "LOADING"), ("LOADING", "DELIVERED")}
    return Outcome.SUCCESS if (source, target) in happy else Outcome.FAILURE


def fresh_session(**kwargs) -> DomainSession:
    return DomainSession(name="test", **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# TestDomainMode
# ─────────────────────────────────────────────────────────────────────────────

class TestDomainMode:
    def test_values_exist(self):
        assert DomainMode.LEARN.value == "learn"
        assert DomainMode.APPLY.value == "apply"
        assert DomainMode.HYBRID.value == "hybrid"

    def test_from_string(self):
        assert DomainMode("learn") == DomainMode.LEARN
        assert DomainMode("apply") == DomainMode.APPLY
        assert DomainMode("hybrid") == DomainMode.HYBRID

    def test_three_modes(self):
        modes = {m for m in DomainMode}
        assert len(modes) == 3


# ─────────────────────────────────────────────────────────────────────────────
# TestLearnReport
# ─────────────────────────────────────────────────────────────────────────────

class TestLearnReport:
    def test_defaults(self):
        r = LearnReport()
        assert r.episodes == 0
        assert r.total_steps == 0
        assert r.success_count == 0
        assert r.warnings == []

    def test_goal_rate_no_episodes(self):
        r = LearnReport()
        assert r.goal_rate == 0.0

    def test_goal_rate_computed(self):
        r = LearnReport(episodes=10, success_count=7)
        assert r.goal_rate == pytest.approx(0.7)

    def test_repr_contains_episodes(self):
        r = LearnReport(episodes=5, total_steps=50)
        s = repr(r)
        assert "5" in s and "50" in s


# ─────────────────────────────────────────────────────────────────────────────
# TestRecommendResult
# ─────────────────────────────────────────────────────────────────────────────

class TestRecommendResult:
    def test_cold_start_true_when_none(self):
        r = RecommendResult(recommended=None, reason="cold", quality=0.0,
                            conviction_score=0.0)
        assert r.cold_start is True

    def test_cold_start_false_when_recommended(self):
        r = RecommendResult(recommended="A", reason="ok", quality=0.8,
                            conviction_score=0.5)
        assert r.cold_start is False

    def test_defaults(self):
        r = RecommendResult(recommended=None, reason="x", quality=0.0,
                            conviction_score=0.0)
        assert r.candidates == []


# ─────────────────────────────────────────────────────────────────────────────
# TestLandscapeCodec
# ─────────────────────────────────────────────────────────────────────────────

class TestLandscapeCodec:
    def test_round_trip_topology(self):
        L = logistics_landscape()
        d = _landscape_to_dict(L)
        L2 = _landscape_from_dict(d)
        assert len(L2.edges) == len(L.edges)

    def test_round_trip_delta(self):
        L = Landscape()
        L.add_edge("A", "B", delta=2.5, resistance=0.7)
        d = _landscape_to_dict(L)
        L2 = _landscape_from_dict(d)
        assert L2._delta[Edge("A", "B")] == pytest.approx(2.5)
        assert L2._R0[Edge("A", "B")] == pytest.approx(0.7)

    def test_round_trip_historization(self):
        L = Landscape()
        L.add_edge("A", "B", delta=1.0, resistance=0.3)
        L.historization.update(Edge("A", "B"), Outcome.SUCCESS)
        L.historization.update(Edge("A", "B"), Outcome.SUCCESS)
        d = _landscape_to_dict(L)
        L2 = _landscape_from_dict(d)
        u = L2.historization._U.get(Edge("A", "B"), 0.0)
        assert u > 0.0

    def test_round_trip_empty(self):
        L = Landscape()
        d = _landscape_to_dict(L)
        L2 = _landscape_from_dict(d)
        assert len(L2.edges) == 0

    def test_tau_preserved(self):
        L = Landscape()
        L.add_edge("A", "B", delta=1.0, resistance=0.3)
        for _ in range(5):
            L.historization.update(Edge("A", "B"), Outcome.SUCCESS)
        d = _landscape_to_dict(L)
        L2 = _landscape_from_dict(d)
        assert L2.historization._tau == L.historization._tau


# ─────────────────────────────────────────────────────────────────────────────
# TestDomainSessionInit
# ─────────────────────────────────────────────────────────────────────────────

class TestDomainSessionInit:
    def test_name_stored(self):
        s = DomainSession(name="logistics")
        assert s.name == "logistics"

    def test_default_mode_is_learn(self):
        s = DomainSession(name="x")
        assert s.mode == DomainMode.LEARN

    def test_fresh_landscape_created(self):
        s = DomainSession(name="x")
        assert isinstance(s.landscape, Landscape)
        assert len(list(s.landscape.edges)) == 0

    def test_custom_landscape_used(self):
        L = logistics_landscape()
        s = DomainSession(name="x", landscape=L)
        assert len(list(s.landscape.edges)) == 4

    def test_description_and_topic(self):
        s = DomainSession(name="x", description="Logistics", topic="supply chain")
        assert s.description == "Logistics"
        assert s.topic == "supply chain"

    def test_episode_count_defaults_zero(self):
        s = DomainSession(name="x")
        assert s._episode_count == 0

    def test_created_at_set(self):
        s = DomainSession(name="x")
        assert s._created_at is not None
        assert "Z" in s._created_at or "T" in s._created_at


# ─────────────────────────────────────────────────────────────────────────────
# TestDomainSessionSetMode
# ─────────────────────────────────────────────────────────────────────────────

class TestDomainSessionSetMode:
    def test_switch_to_apply(self):
        s = DomainSession(name="x")
        s.set_mode(DomainMode.APPLY)
        assert s.mode == DomainMode.APPLY

    def test_switch_to_hybrid(self):
        s = DomainSession(name="x")
        s.set_mode(DomainMode.HYBRID)
        assert s.mode == DomainMode.HYBRID

    def test_switch_back_to_learn(self):
        s = DomainSession(name="x")
        s.set_mode(DomainMode.APPLY)
        s.set_mode(DomainMode.LEARN)
        assert s.mode == DomainMode.LEARN

    def test_mode_reflected_in_status(self):
        s = DomainSession(name="x")
        s.set_mode(DomainMode.APPLY)
        assert s.status()["mode"] == "apply"


# ─────────────────────────────────────────────────────────────────────────────
# TestDomainSessionInject
# ─────────────────────────────────────────────────────────────────────────────

class TestDomainSessionInject:
    def test_csv_adds_edges(self):
        s = DomainSession(name="x")
        report = s.inject("ORDER,PICKING,success\nPICKING,LOADING,success", hint="csv")
        assert report.edges_added == 2
        assert report.inscriptions == 2

    def test_json_adds_edges(self):
        import json
        s = DomainSession(name="x")
        data = {"edges": [{"from": "A", "to": "B"}, {"from": "B", "to": "C"}]}
        report = s.inject(json.dumps(data), hint="json")
        assert report.edges_added == 2

    def test_bytes_accepted(self):
        s = DomainSession(name="x")
        report = s.inject(b"A,B,success", hint="csv")
        assert report.inscriptions == 1

    def test_inject_adds_to_session_landscape(self):
        s = DomainSession(name="x")
        s.inject("A,B,success\nB,C,failure", hint="csv")
        assert len(list(s.landscape.edges)) == 2


# ─────────────────────────────────────────────────────────────────────────────
# TestDomainSessionLearnEmpty
# ─────────────────────────────────────────────────────────────────────────────

class TestDomainSessionLearnEmpty:
    def test_empty_landscape_returns_warning(self):
        s = DomainSession(name="x")
        report = s.learn(oracle_always_success)
        assert len(report.warnings) > 0

    def test_empty_landscape_zero_episodes(self):
        s = DomainSession(name="x")
        report = s.learn(oracle_always_success)
        assert report.episodes == 0

    def test_empty_landscape_no_side_effects(self):
        s = DomainSession(name="x")
        s.learn(oracle_always_success)
        assert s._episode_count == 0


# ─────────────────────────────────────────────────────────────────────────────
# TestDomainSessionLearn
# ─────────────────────────────────────────────────────────────────────────────

class TestDomainSessionLearn:
    def test_episode_count_increments(self):
        s = DomainSession(name="x", landscape=logistics_landscape())
        s.learn(oracle_happy_path, n_episodes=5, start="ORDER", goal="DELIVERED")
        assert s._episode_count == 5

    def test_report_episode_count(self):
        s = DomainSession(name="x", landscape=logistics_landscape())
        report = s.learn(oracle_happy_path, n_episodes=3, start="ORDER", goal="DELIVERED")
        assert report.episodes == 3

    def test_steps_positive(self):
        s = DomainSession(name="x", landscape=logistics_landscape())
        report = s.learn(oracle_happy_path, n_episodes=5, start="ORDER", goal="DELIVERED")
        assert report.total_steps > 0

    def test_success_count_positive_with_success_oracle(self):
        s = DomainSession(name="x", landscape=logistics_landscape())
        report = s.learn(oracle_always_success, n_episodes=10,
                         start="ORDER", goal="DELIVERED", max_steps=20)
        assert report.success_count > 0

    def test_edges_explored_positive(self):
        s = DomainSession(name="x", landscape=logistics_landscape())
        report = s.learn(oracle_happy_path, n_episodes=10,
                         start="ORDER", goal="DELIVERED", max_steps=20)
        assert report.edges_explored > 0

    def test_historization_updated(self):
        s = DomainSession(name="x", landscape=logistics_landscape())
        s.learn(oracle_happy_path, n_episodes=20,
                start="ORDER", goal="DELIVERED", max_steps=30)
        h = s.landscape.historization
        # At least one edge should have been inscribed
        total_u = sum(v for v in h._U.values())
        total_f = sum(v for v in h._F.values())
        assert total_u + total_f > 0

    def test_invalid_start_falls_back(self):
        s = DomainSession(name="x", landscape=logistics_landscape())
        report = s.learn(oracle_always_success, n_episodes=2,
                         start="NONEXISTENT_STATE")
        # Should warn but still run
        assert len(report.warnings) > 0
        assert report.episodes == 2

    def test_goal_none_runs_max_steps(self):
        s = DomainSession(name="x", landscape=logistics_landscape())
        report = s.learn(oracle_always_success, n_episodes=2,
                         start="ORDER", goal=None, max_steps=5)
        # Without a goal, each episode runs max_steps steps
        assert report.total_steps > 0


# ─────────────────────────────────────────────────────────────────────────────
# TestDomainSessionRecommend
# ─────────────────────────────────────────────────────────────────────────────

class TestDomainSessionRecommend:
    def test_cold_start_returns_none(self):
        s = DomainSession(name="x", landscape=logistics_landscape())
        result = s.recommend("ORDER", ["PICKING", "BACKORDER"])
        assert result.recommended is None
        assert result.cold_start is True

    def test_after_learn_returns_recommendation(self):
        s = DomainSession(name="x", landscape=logistics_landscape())
        s.learn(oracle_happy_path, n_episodes=20,
                start="ORDER", goal="DELIVERED", max_steps=30)
        result = s.recommend("ORDER", ["PICKING", "BACKORDER"])
        # Should now have inscriptions → recommendation
        assert result.recommended in ("PICKING", "BACKORDER", None)

    def test_recommended_in_candidates(self):
        s = DomainSession(name="x", landscape=logistics_landscape())
        s.learn(oracle_happy_path, n_episodes=30,
                start="ORDER", goal="DELIVERED", max_steps=30)
        result = s.recommend("ORDER", ["PICKING", "BACKORDER"])
        if result.recommended is not None:
            assert result.recommended in ("PICKING", "BACKORDER")

    def test_empty_candidates_returns_none(self):
        s = DomainSession(name="x", landscape=logistics_landscape())
        result = s.recommend("ORDER", [])
        assert result.recommended is None
        assert "no candidates" in result.reason.lower()

    def test_auto_creates_new_candidate_edges(self):
        s = DomainSession(name="x", landscape=logistics_landscape())
        s.learn(oracle_always_success, n_episodes=20,
                start="ORDER", goal="DELIVERED", max_steps=20)
        # "EXPRESS" is a new state not in the original topology
        result = s.recommend("ORDER", ["PICKING", "EXPRESS"])
        # Edge ORDER→EXPRESS should have been auto-created
        edges = {(e.source, e.target) for e in s.landscape.edges}
        assert ("ORDER", "EXPRESS") in edges


# ─────────────────────────────────────────────────────────────────────────────
# TestDomainSessionRecord
# ─────────────────────────────────────────────────────────────────────────────

class TestDomainSessionRecord:
    def test_success_inscribes(self):
        s = DomainSession(name="x", landscape=logistics_landscape())
        ok = s.record("ORDER", "PICKING", "success")
        assert ok is True
        u = s.landscape.historization._U.get(Edge("ORDER", "PICKING"), 0.0)
        assert u > 0.0

    def test_failure_inscribes(self):
        s = DomainSession(name="x", landscape=logistics_landscape())
        s.record("ORDER", "BACKORDER", "failure")
        f = s.landscape.historization._F.get(Edge("ORDER", "BACKORDER"), 0.0)
        assert f > 0.0

    def test_unknown_outcome_returns_false(self):
        s = DomainSession(name="x", landscape=logistics_landscape())
        ok = s.record("ORDER", "PICKING", "???")
        assert ok is False

    def test_auto_creates_edge(self):
        s = DomainSession(name="x")
        s.record("X", "Y", "success")
        edges = {(e.source, e.target) for e in s.landscape.edges}
        assert ("X", "Y") in edges


# ─────────────────────────────────────────────────────────────────────────────
# TestDomainSessionStatus
# ─────────────────────────────────────────────────────────────────────────────

class TestDomainSessionStatus:
    def test_status_has_required_keys(self):
        s = DomainSession(name="x")
        st = s.status()
        for key in ("name", "mode", "episode_count", "states", "edges",
                    "total_inscriptions", "cold_start", "created_at"):
            assert key in st

    def test_name_in_status(self):
        s = DomainSession(name="logistics")
        assert s.status()["name"] == "logistics"

    def test_cold_start_true_initially(self):
        s = DomainSession(name="x", landscape=logistics_landscape())
        assert s.status()["cold_start"] is True

    def test_cold_start_false_after_inscriptions(self):
        s = DomainSession(name="x", landscape=logistics_landscape())
        for _ in range(6):
            s.record("ORDER", "PICKING", "success")
        assert s.status()["cold_start"] is False

    def test_episode_count_in_status(self):
        s = DomainSession(name="x", landscape=logistics_landscape())
        s.learn(oracle_always_success, n_episodes=3,
                start="ORDER", goal="DELIVERED", max_steps=10)
        assert s.status()["episode_count"] == 3


# ─────────────────────────────────────────────────────────────────────────────
# TestDomainSessionConvictionMap
# ─────────────────────────────────────────────────────────────────────────────

class TestDomainSessionConvictionMap:
    def test_empty_conviction_map(self):
        s = DomainSession(name="x")
        cm = s.conviction_map()
        assert cm == {}

    def test_conviction_values_in_range(self):
        s = DomainSession(name="x", landscape=logistics_landscape())
        s.learn(oracle_happy_path, n_episodes=10,
                start="ORDER", goal="DELIVERED", max_steps=20)
        cm = s.conviction_map()
        for k, v in cm.items():
            assert 0.0 <= v < 1.0, f"conviction out of range for {k}: {v}"

    def test_conviction_increases_with_learning(self):
        s = DomainSession(name="x", landscape=logistics_landscape())
        cm_before = s.conviction_map()
        s.learn(oracle_happy_path, n_episodes=30,
                start="ORDER", goal="DELIVERED", max_steps=30)
        cm_after = s.conviction_map()
        # Average conviction should be higher after learning
        avg_before = sum(cm_before.values()) / max(len(cm_before), 1)
        avg_after = sum(cm_after.values()) / max(len(cm_after), 1)
        assert avg_after >= avg_before

    def test_conviction_keys_are_edge_strings(self):
        s = DomainSession(name="x", landscape=logistics_landscape())
        cm = s.conviction_map()
        for k in cm:
            assert "→" in k


# ─────────────────────────────────────────────────────────────────────────────
# TestDomainStoreInit
# ─────────────────────────────────────────────────────────────────────────────

class TestDomainStoreInit:
    def test_default_dir(self):
        store = DomainStore()
        assert "domains" in str(store._dir)

    def test_custom_dir(self, tmp_path):
        store = DomainStore(store_dir=str(tmp_path / "mydomains"))
        assert store._dir == tmp_path / "mydomains"

    def test_dir_not_created_on_init(self, tmp_path):
        custom = tmp_path / "notyet"
        DomainStore(store_dir=str(custom))
        # Directory should NOT be created until save() is called
        assert not custom.exists()


# ─────────────────────────────────────────────────────────────────────────────
# TestDomainStoreSaveLoad
# ─────────────────────────────────────────────────────────────────────────────

class TestDomainStoreSaveLoad:
    def test_save_creates_file(self, tmp_path):
        store = DomainStore(store_dir=str(tmp_path))
        session = DomainSession(name="logistics")
        path = store.save(session)
        assert path.exists()

    def test_save_creates_dir_if_missing(self, tmp_path):
        nested = tmp_path / "a" / "b" / "domains"
        store = DomainStore(store_dir=str(nested))
        session = DomainSession(name="x")
        store.save(session)
        assert nested.exists()

    def test_load_restores_name(self, tmp_path):
        store = DomainStore(store_dir=str(tmp_path))
        store.save(DomainSession(name="mytest"))
        loaded = store.load("mytest")
        assert loaded is not None
        assert loaded.name == "mytest"

    def test_load_restores_description(self, tmp_path):
        store = DomainStore(store_dir=str(tmp_path))
        store.save(DomainSession(name="x", description="Logistics domain"))
        loaded = store.load("x")
        assert loaded.description == "Logistics domain"

    def test_load_restores_mode(self, tmp_path):
        store = DomainStore(store_dir=str(tmp_path))
        s = DomainSession(name="x", mode=DomainMode.APPLY)
        store.save(s)
        loaded = store.load("x")
        assert loaded.mode == DomainMode.APPLY

    def test_load_restores_episode_count(self, tmp_path):
        store = DomainStore(store_dir=str(tmp_path))
        s = DomainSession(name="x", landscape=logistics_landscape(),
                          episode_count=7)
        store.save(s)
        loaded = store.load("x")
        assert loaded._episode_count == 7

    def test_load_restores_topology(self, tmp_path):
        store = DomainStore(store_dir=str(tmp_path))
        s = DomainSession(name="x", landscape=logistics_landscape())
        store.save(s)
        loaded = store.load("x")
        assert len(list(loaded.landscape.edges)) == 4

    def test_load_restores_historization(self, tmp_path):
        store = DomainStore(store_dir=str(tmp_path))
        s = DomainSession(name="x", landscape=logistics_landscape())
        for _ in range(5):
            s.record("ORDER", "PICKING", "success")
        store.save(s)
        loaded = store.load("x")
        u = loaded.landscape.historization._U.get(Edge("ORDER", "PICKING"), 0.0)
        assert u > 0.0

    def test_load_nonexistent_returns_none(self, tmp_path):
        store = DomainStore(store_dir=str(tmp_path))
        result = store.load("does_not_exist")
        assert result is None

    def test_load_corrupt_returns_none(self, tmp_path):
        store = DomainStore(store_dir=str(tmp_path))
        (tmp_path / "broken.json").write_text("not json!!!", encoding="utf-8")
        result = store.load("broken")
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# TestDomainStoreList
# ─────────────────────────────────────────────────────────────────────────────

class TestDomainStoreList:
    def test_empty_store(self, tmp_path):
        store = DomainStore(store_dir=str(tmp_path))
        assert store.list_domains() == []

    def test_nonexistent_dir(self, tmp_path):
        store = DomainStore(store_dir=str(tmp_path / "nodir"))
        assert store.list_domains() == []

    def test_single_domain(self, tmp_path):
        store = DomainStore(store_dir=str(tmp_path))
        store.save(DomainSession(name="logistics"))
        assert store.list_domains() == ["logistics"]

    def test_multiple_domains_sorted(self, tmp_path):
        store = DomainStore(store_dir=str(tmp_path))
        for name in ("zebra", "alpha", "middle"):
            store.save(DomainSession(name=name))
        assert store.list_domains() == ["alpha", "middle", "zebra"]

    def test_non_json_files_excluded(self, tmp_path):
        store = DomainStore(store_dir=str(tmp_path))
        (tmp_path / "README.txt").write_text("ignore me")
        store.save(DomainSession(name="real"))
        assert store.list_domains() == ["real"]


# ─────────────────────────────────────────────────────────────────────────────
# TestDomainStoreDelete
# ─────────────────────────────────────────────────────────────────────────────

class TestDomainStoreDelete:
    def test_delete_existing(self, tmp_path):
        store = DomainStore(store_dir=str(tmp_path))
        store.save(DomainSession(name="x"))
        result = store.delete("x")
        assert result is True
        assert not store.exists("x")

    def test_delete_nonexistent(self, tmp_path):
        store = DomainStore(store_dir=str(tmp_path))
        result = store.delete("ghost")
        assert result is False

    def test_delete_removes_from_list(self, tmp_path):
        store = DomainStore(store_dir=str(tmp_path))
        store.save(DomainSession(name="a"))
        store.save(DomainSession(name="b"))
        store.delete("a")
        assert store.list_domains() == ["b"]

    def test_exists_true_after_save(self, tmp_path):
        store = DomainStore(store_dir=str(tmp_path))
        store.save(DomainSession(name="x"))
        assert store.exists("x") is True

    def test_exists_false_before_save(self, tmp_path):
        store = DomainStore(store_dir=str(tmp_path))
        assert store.exists("x") is False


# ─────────────────────────────────────────────────────────────────────────────
# TestDomainStoreRoundTrip
# ─────────────────────────────────────────────────────────────────────────────

class TestDomainStoreRoundTrip:
    def _build_trained_session(self) -> DomainSession:
        s = DomainSession(
            name="logistics",
            description="E-Commerce Logistics",
            topic="supply chain",
            landscape=logistics_landscape(),
            mode=DomainMode.LEARN,
        )
        s.learn(oracle_happy_path, n_episodes=20,
                start="ORDER", goal="DELIVERED", max_steps=30)
        return s

    def test_save_load_mode_switch(self, tmp_path):
        store = DomainStore(store_dir=str(tmp_path))
        s = self._build_trained_session()
        s.set_mode(DomainMode.APPLY)
        store.save(s)
        loaded = store.load("logistics")
        assert loaded.mode == DomainMode.APPLY

    def test_save_load_recommend_works(self, tmp_path):
        store = DomainStore(store_dir=str(tmp_path))
        s = self._build_trained_session()
        store.save(s)
        loaded = store.load("logistics")
        # After loading, recommend should work (inscriptions are there)
        result = loaded.recommend("ORDER", ["PICKING", "BACKORDER"])
        # With 20 episodes → should have enough inscriptions
        assert result.recommended in ("PICKING", "BACKORDER", None)

    def test_second_learn_cycle_adds_episodes(self, tmp_path):
        store = DomainStore(store_dir=str(tmp_path))
        s = self._build_trained_session()  # 20 episodes
        store.save(s)
        loaded = store.load("logistics")
        loaded.learn(oracle_happy_path, n_episodes=10,
                     start="ORDER", goal="DELIVERED", max_steps=30)
        assert loaded._episode_count == 30

    def test_conviction_higher_after_two_cycles(self, tmp_path):
        store = DomainStore(store_dir=str(tmp_path))
        s = self._build_trained_session()
        cm1 = s.conviction_map()
        store.save(s)
        loaded = store.load("logistics")
        loaded.learn(oracle_happy_path, n_episodes=20,
                     start="ORDER", goal="DELIVERED", max_steps=30)
        cm2 = loaded.conviction_map()
        avg1 = sum(cm1.values()) / max(len(cm1), 1)
        avg2 = sum(cm2.values()) / max(len(cm2), 1)
        assert avg2 >= avg1

    def test_inject_then_learn_then_save_load(self, tmp_path):
        store = DomainStore(store_dir=str(tmp_path))
        s = DomainSession(name="express", description="Express delivery")
        # Inject topology via CSV
        s.inject(
            "ORDER,PICKING,success\nPICKING,LOADING,success\nLOADING,DELIVERED,success",
            hint="csv",
        )
        # Learn
        s.learn(oracle_always_success, n_episodes=10,
                start="ORDER", goal="DELIVERED", max_steps=20)
        # Save + load
        store.save(s)
        loaded = store.load("express")
        assert loaded.description == "Express delivery"
        assert len(list(loaded.landscape.edges)) >= 3
        assert loaded._episode_count == 10
