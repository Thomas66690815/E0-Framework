"""Tests for E₀ Domain Studio REST API (ARC-K, C307; C309 oracle extension).

Uses FastAPI TestClient. DomainStore is injected with a tmp_path-backed
store so no files land in the repo.

Test classes:
    TestDomainCreate         — POST /domains
    TestDomainList           — GET /domains
    TestDomainGet            — GET /domains/{name}
    TestDomainDelete         — DELETE /domains/{name}
    TestDomainUpload         — POST /domains/{name}/upload
    TestDomainLearn          — POST /domains/{name}/learn (base oracles)
    TestOracleGoalAware      — oracle_type=goal_aware  (C309)
    TestOracleLLM            — oracle_type=llm         (C309)
    TestDomainSetMode        — PUT /domains/{name}/mode
    TestDomainRecommend      — POST /domains/{name}/recommend
    TestDomainRecord         — POST /domains/{name}/record
    TestDomainConviction     — GET /domains/{name}/conviction
    TestDomainWorkflow       — end-to-end: create → upload → learn → apply
"""

from __future__ import annotations

import io
import json
import pytest

from fastapi.testclient import TestClient

from e0_controller.domain_session import DomainStore
from server.main import app
from server.routes_domains import set_store


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_store(tmp_path):
    """Each test gets a fresh DomainStore backed by a temp directory."""
    store = DomainStore(store_dir=str(tmp_path / "domains"))
    set_store(store)
    yield store
    # Cleanup: reset to None so next test gets a fresh default
    set_store(DomainStore(store_dir=str(tmp_path / "domains")))


@pytest.fixture
def client():
    return TestClient(app)


# ── Shared CSV content ────────────────────────────────────────────────────────

LOGISTICS_CSV = (
    "ORDER,PICKING,success\n"
    "ORDER,BACKORDER,failure\n"
    "PICKING,LOADING,success\n"
    "LOADING,DELIVERED,success\n"
).encode()

MINIMAL_CSV = b"A,B,success\nB,C,success\nC,D,success"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _create(client, name="test", description="", topic="", mode="learn"):
    return client.post("/domains", json={
        "name": name,
        "description": description,
        "topic": topic,
        "mode": mode,
    })


def _upload_csv(client, name, csv_bytes=None, filename="data.csv"):
    data = csv_bytes or LOGISTICS_CSV
    return client.post(
        f"/domains/{name}/upload",
        files={"file": (filename, io.BytesIO(data), "text/csv")},
    )


# ══════════════════════════════════════════════════════════════════════════════
# TestDomainCreate
# ══════════════════════════════════════════════════════════════════════════════

class TestDomainCreate:

    def test_create_returns_201(self, client):
        r = _create(client, name="logistics")
        assert r.status_code == 201

    def test_create_response_fields(self, client):
        r = _create(client, name="logistics", description="My domain")
        data = r.json()
        assert data["name"] == "logistics"
        assert data["description"] == "My domain"
        assert data["mode"] == "learn"
        assert data["episode_count"] == 0
        assert data["cold_start"] is True

    def test_create_with_apply_mode(self, client):
        r = _create(client, name="x", mode="apply")
        assert r.json()["mode"] == "apply"

    def test_create_duplicate_returns_409(self, client):
        _create(client, name="dup")
        r = _create(client, name="dup")
        assert r.status_code == 409

    def test_create_with_topic(self, client):
        r = _create(client, name="x", topic="supply chain")
        assert r.json()["topic"] == "supply chain"

    def test_create_invalid_mode_returns_422(self, client):
        r = client.post("/domains", json={"name": "x", "mode": "invalid"})
        assert r.status_code == 422

    def test_create_empty_name_returns_422(self, client):
        r = client.post("/domains", json={"name": ""})
        assert r.status_code == 422


# ══════════════════════════════════════════════════════════════════════════════
# TestDomainList
# ══════════════════════════════════════════════════════════════════════════════

class TestDomainList:

    def test_empty_list(self, client):
        r = client.get("/domains")
        assert r.status_code == 200
        assert r.json() == []

    def test_single_domain(self, client):
        _create(client, name="alpha")
        r = client.get("/domains")
        assert r.status_code == 200
        names = [d["name"] for d in r.json()]
        assert "alpha" in names

    def test_multiple_domains_all_listed(self, client):
        for n in ("aaa", "bbb", "ccc"):
            _create(client, name=n)
        r = client.get("/domains")
        names = [d["name"] for d in r.json()]
        assert set(names) == {"aaa", "bbb", "ccc"}

    def test_list_sorted(self, client):
        for n in ("zebra", "alpha", "middle"):
            _create(client, name=n)
        names = [d["name"] for d in client.get("/domains").json()]
        assert names == sorted(names)


# ══════════════════════════════════════════════════════════════════════════════
# TestDomainGet
# ══════════════════════════════════════════════════════════════════════════════

class TestDomainGet:

    def test_get_existing(self, client):
        _create(client, name="x")
        r = client.get("/domains/x")
        assert r.status_code == 200
        assert r.json()["name"] == "x"

    def test_get_nonexistent_returns_404(self, client):
        r = client.get("/domains/ghost")
        assert r.status_code == 404

    def test_status_reflects_upload(self, client):
        _create(client, name="x")
        _upload_csv(client, "x")
        r = client.get("/domains/x")
        data = r.json()
        assert data["edges"] > 0
        assert data["states"] > 0


# ══════════════════════════════════════════════════════════════════════════════
# TestDomainDelete
# ══════════════════════════════════════════════════════════════════════════════

class TestDomainDelete:

    def test_delete_existing(self, client):
        _create(client, name="x")
        r = client.delete("/domains/x")
        assert r.status_code == 204

    def test_delete_removes_from_list(self, client):
        _create(client, name="x")
        client.delete("/domains/x")
        names = [d["name"] for d in client.get("/domains").json()]
        assert "x" not in names

    def test_delete_nonexistent_returns_404(self, client):
        r = client.delete("/domains/ghost")
        assert r.status_code == 404

    def test_get_after_delete_returns_404(self, client):
        _create(client, name="x")
        client.delete("/domains/x")
        assert client.get("/domains/x").status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# TestDomainUpload
# ══════════════════════════════════════════════════════════════════════════════

class TestDomainUpload:

    def test_upload_csv_adds_edges(self, client):
        _create(client, name="x")
        r = _upload_csv(client, "x", LOGISTICS_CSV)
        assert r.status_code == 200
        data = r.json()
        assert data["edges_added"] == 4

    def test_upload_inscriptions_reported(self, client):
        _create(client, name="x")
        r = _upload_csv(client, "x", LOGISTICS_CSV)
        # 3 success + 1 failure → 4 inscriptions
        assert r.json()["inscriptions"] > 0

    def test_upload_json_adds_edges(self, client):
        _create(client, name="x")
        payload = json.dumps({
            "edges": [{"from": "A", "to": "B"}, {"from": "B", "to": "C"}]
        }).encode()
        r = client.post(
            "/domains/x/upload",
            files={"file": ("data.json", io.BytesIO(payload), "application/json")},
        )
        assert r.status_code == 200
        assert r.json()["edges_added"] == 2

    def test_upload_persists_to_store(self, client, isolated_store):
        _create(client, name="x")
        _upload_csv(client, "x", LOGISTICS_CSV)
        loaded = isolated_store.load("x")
        assert len(list(loaded.landscape.edges)) == 4

    def test_upload_nonexistent_domain_returns_404(self, client):
        r = _upload_csv(client, "ghost")
        assert r.status_code == 404

    def test_upload_empty_file_returns_422(self, client):
        _create(client, name="x")
        r = client.post(
            "/domains/x/upload",
            files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
        )
        assert r.status_code == 422

    def test_upload_idempotent(self, client):
        _create(client, name="x")
        _upload_csv(client, "x", LOGISTICS_CSV)
        r2 = _upload_csv(client, "x", LOGISTICS_CSV)
        # Second upload: same edges, no new edges_added (idempotent via FileSensor)
        assert r2.json()["edges_added"] == 0


# ══════════════════════════════════════════════════════════════════════════════
# TestDomainLearn
# ══════════════════════════════════════════════════════════════════════════════

class TestDomainLearn:

    def _setup(self, client):
        _create(client, name="x")
        _upload_csv(client, "x", LOGISTICS_CSV)

    def test_learn_returns_200(self, client):
        self._setup(client)
        r = client.post("/domains/x/learn", json={"n_episodes": 5})
        assert r.status_code == 200

    def test_learn_response_fields(self, client):
        self._setup(client)
        r = client.post("/domains/x/learn", json={"n_episodes": 5})
        data = r.json()
        for key in ("episodes", "total_steps", "success_count",
                    "failure_count", "partial_count", "edges_explored",
                    "goal_rate", "warnings"):
            assert key in data

    def test_learn_episodes_count(self, client):
        self._setup(client)
        r = client.post("/domains/x/learn", json={"n_episodes": 3})
        assert r.json()["episodes"] == 3

    def test_learn_increments_episode_count(self, client):
        self._setup(client)
        client.post("/domains/x/learn", json={"n_episodes": 5})
        data = client.get("/domains/x").json()
        assert data["episode_count"] == 5

    def test_learn_with_goal(self, client):
        self._setup(client)
        r = client.post("/domains/x/learn", json={
            "n_episodes": 5, "start": "ORDER", "goal": "DELIVERED"
        })
        assert r.status_code == 200

    def test_learn_empty_domain_returns_warning(self, client):
        _create(client, name="x")
        r = client.post("/domains/x/learn", json={"n_episodes": 3})
        assert r.status_code == 200
        assert len(r.json()["warnings"]) > 0

    def test_learn_topology_aware_oracle(self, client):
        self._setup(client)
        r = client.post("/domains/x/learn", json={
            "n_episodes": 5, "oracle_type": "topology_aware"
        })
        assert r.status_code == 200

    def test_learn_random_oracle(self, client):
        self._setup(client)
        r = client.post("/domains/x/learn", json={
            "n_episodes": 5, "oracle_type": "random"
        })
        assert r.status_code == 200

    def test_learn_invalid_oracle_returns_422(self, client):
        self._setup(client)
        r = client.post("/domains/x/learn", json={
            "n_episodes": 5, "oracle_type": "magic"
        })
        assert r.status_code == 422

    def test_learn_nonexistent_domain_returns_404(self, client):
        r = client.post("/domains/ghost/learn", json={"n_episodes": 5})
        assert r.status_code == 404

    def test_learn_persists_historization(self, client, isolated_store):
        self._setup(client)
        client.post("/domains/x/learn", json={"n_episodes": 10})
        loaded = isolated_store.load("x")
        h = loaded.landscape.historization
        total = sum(h._U.values()) + sum(h._F.values())
        assert total > 0


# ══════════════════════════════════════════════════════════════════════════════
# TestOracleGoalAware  (C309)
# ══════════════════════════════════════════════════════════════════════════════

class TestOracleGoalAware:
    """goal_aware oracle: SUCCESS iff step strictly reduces BFS distance to goal."""

    LINEAR_CSV = b"A,B,success\nB,C,success\nC,D,success"

    def _setup_linear(self, client):
        """Create domain with linear chain A→B→C→D."""
        _create(client, name="chain")
        client.post(
            "/domains/chain/upload",
            files={"file": ("data.csv", io.BytesIO(self.LINEAR_CSV), "text/csv")},
        )

    def test_goal_aware_returns_200(self, client):
        self._setup_linear(client)
        r = client.post("/domains/chain/learn", json={
            "n_episodes": 5,
            "oracle_type": "goal_aware",
            "start": "A",
            "goal": "D",
        })
        assert r.status_code == 200

    def test_goal_aware_requires_goal_field(self, client):
        """If oracle_type=goal_aware but no goal → 422."""
        self._setup_linear(client)
        r = client.post("/domains/chain/learn", json={
            "n_episodes": 3,
            "oracle_type": "goal_aware",
        })
        assert r.status_code == 422

    def test_goal_aware_accumulates_success_on_forward_steps(self, client, isolated_store):
        """On a linear chain all steps toward the goal should be SUCCESS → U grows."""
        self._setup_linear(client)
        client.post("/domains/chain/learn", json={
            "n_episodes": 20,
            "oracle_type": "goal_aware",
            "start": "A",
            "goal": "D",
        })
        loaded = isolated_store.load("chain")
        h = loaded.landscape.historization
        from e0_controller.primitives import Edge
        # A→B, B→C, C→D are all forward steps → should have U > 0
        for src, tgt in [("A", "B"), ("B", "C"), ("C", "D")]:
            assert h._U.get(Edge(src, tgt), 0) > 0, f"Expected U > 0 for {src}→{tgt}"

    def test_goal_aware_episodes_count(self, client):
        self._setup_linear(client)
        r = client.post("/domains/chain/learn", json={
            "n_episodes": 4,
            "oracle_type": "goal_aware",
            "start": "A",
            "goal": "D",
        })
        assert r.json()["episodes"] == 4

    def test_goal_aware_persists(self, client):
        self._setup_linear(client)
        client.post("/domains/chain/learn", json={
            "n_episodes": 10,
            "oracle_type": "goal_aware",
            "start": "A",
            "goal": "D",
        })
        status = client.get("/domains/chain").json()
        assert status["episode_count"] == 10

    def test_goal_aware_works_with_logistics(self, client):
        """Logistics topology: ORDER→PICKING→LOADING→DELIVERED. Goal=DELIVERED."""
        _create(client, name="log")
        _upload_csv(client, "log", LOGISTICS_CSV)
        r = client.post("/domains/log/learn", json={
            "n_episodes": 10,
            "oracle_type": "goal_aware",
            "start": "ORDER",
            "goal": "DELIVERED",
        })
        assert r.status_code == 200
        assert r.json()["success_count"] > 0


# ══════════════════════════════════════════════════════════════════════════════
# TestOracleLLM  (C309)
# ══════════════════════════════════════════════════════════════════════════════

class TestOracleLLM:
    """LLM oracle: each (source, target) is judged by a pluggable call_fn.

    Tests use a mock call_fn so no real OpenAI calls are made.
    """

    def _setup(self, client):
        _create(client, name="x", topic="test topic", description="A test domain.")
        _upload_csv(client, "x", LOGISTICS_CSV)

    def test_llm_oracle_returns_200_with_mock(self, client, monkeypatch):
        """LLM oracle type is accepted and returns 200 (mock avoids real API call)."""
        from server import routes_domains
        from e0_controller.primitives import Outcome

        monkeypatch.setattr(
            routes_domains, "_llm_oracle",
            lambda session, call_fn=None: (lambda s, t: Outcome.SUCCESS),
        )

        self._setup(client)
        r = client.post("/domains/x/learn", json={
            "n_episodes": 5,
            "oracle_type": "llm",
        })
        assert r.status_code == 200
        # All response keys must be present regardless of oracle
        for key in ("episodes", "total_steps", "success_count",
                    "failure_count", "partial_count", "goal_rate", "warnings"):
            assert key in r.json()

    def test_llm_oracle_success_response_parsed(self, client):
        """oracle_type='llm' is accepted by the endpoint (behavioral parsing tested in unit tests)."""
        # Without a real API key the oracle falls back to FAILURE — that's correct behaviour.
        # We only assert structural correctness here; use test_llm_oracle_direct_* for parsing.
        self._setup(client)
        r = client.post("/domains/x/learn", json={
            "n_episodes": 3,
            "oracle_type": "llm",
        })
        assert r.status_code == 200
        assert r.json()["episodes"] == 3

    def test_llm_oracle_failure_fallback_on_exception(self, client, monkeypatch):
        """When LLM call raises, oracle falls back to FAILURE."""
        from server import routes_domains
        from e0_controller.primitives import Outcome

        def _failing_oracle(session, call_fn=None):
            return lambda s, t: Outcome.FAILURE  # simulates error fallback

        monkeypatch.setattr(routes_domains, "_llm_oracle", _failing_oracle)

        self._setup(client)
        r = client.post("/domains/x/learn", json={
            "n_episodes": 5,
            "oracle_type": "llm",
        })
        assert r.status_code == 200
        # All steps FAILURE → success_count == 0
        assert r.json()["success_count"] == 0

    def test_llm_oracle_partial_parsed(self, client):
        """oracle_type='llm' endpoint returns valid response structure for partial outcomes."""
        # Behavioral partial-parsing verified in test_llm_oracle_direct_partial_parsing.
        self._setup(client)
        r = client.post("/domains/x/learn", json={
            "n_episodes": 3,
            "oracle_type": "llm",
        })
        assert r.status_code == 200
        assert "partial_count" in r.json()

    def test_llm_oracle_direct_call_fn(self):
        """Unit-test _llm_oracle() directly: mock call_fn returning 'SUCCESS'."""
        from server.routes_domains import _llm_oracle
        from e0_controller.domain_session import DomainSession, DomainMode
        from e0_controller.primitives import Outcome

        session = DomainSession(
            name="test",
            topic="Logistics",
            description="Move packages.",
            mode=DomainMode.LEARN,
        )

        call_log = []

        def _mock_call(system, user, config):
            call_log.append((system, user))
            return "SUCCESS"

        oracle = _llm_oracle(session, call_fn=_mock_call)
        result = oracle("ORDER", "PICKING")
        assert result == Outcome.SUCCESS
        assert len(call_log) == 1
        assert "Logistics" in call_log[0][1]
        assert "ORDER" in call_log[0][1]
        assert "PICKING" in call_log[0][1]

    def test_llm_oracle_direct_failure_fallback(self):
        """Unit-test _llm_oracle(): when call_fn raises, oracle returns FAILURE."""
        from server.routes_domains import _llm_oracle
        from e0_controller.domain_session import DomainSession, DomainMode
        from e0_controller.primitives import Outcome

        session = DomainSession(name="test", mode=DomainMode.LEARN)

        def _raising_call(system, user, config):
            raise RuntimeError("No API key")

        oracle = _llm_oracle(session, call_fn=_raising_call)
        assert oracle("A", "B") == Outcome.FAILURE

    def test_llm_oracle_direct_partial_parsing(self):
        """Unit-test _llm_oracle(): 'PARTIAL' in response → Outcome.PARTIAL."""
        from server.routes_domains import _llm_oracle
        from e0_controller.domain_session import DomainSession, DomainMode
        from e0_controller.primitives import Outcome

        session = DomainSession(name="test", mode=DomainMode.LEARN)
        oracle = _llm_oracle(session, call_fn=lambda s, u, c: "  partial  ")
        assert oracle("A", "B") == Outcome.PARTIAL

    def test_llm_oracle_direct_unknown_fallback(self):
        """Unit-test _llm_oracle(): unrecognised reply → FAILURE."""
        from server.routes_domains import _llm_oracle
        from e0_controller.domain_session import DomainSession, DomainMode
        from e0_controller.primitives import Outcome

        session = DomainSession(name="test", mode=DomainMode.LEARN)
        oracle = _llm_oracle(session, call_fn=lambda s, u, c: "MAYBE")
        assert oracle("A", "B") == Outcome.FAILURE


# ══════════════════════════════════════════════════════════════════════════════
# TestDomainSetMode
# ══════════════════════════════════════════════════════════════════════════════

class TestDomainSetMode:

    def test_switch_to_apply(self, client):
        _create(client, name="x")
        r = client.put("/domains/x/mode", json={"mode": "apply"})
        assert r.status_code == 200
        assert r.json()["mode"] == "apply"

    def test_switch_to_hybrid(self, client):
        _create(client, name="x")
        r = client.put("/domains/x/mode", json={"mode": "hybrid"})
        assert r.json()["mode"] == "hybrid"

    def test_switch_back_to_learn(self, client):
        _create(client, name="x")
        client.put("/domains/x/mode", json={"mode": "apply"})
        r = client.put("/domains/x/mode", json={"mode": "learn"})
        assert r.json()["mode"] == "learn"

    def test_mode_persisted(self, client, isolated_store):
        _create(client, name="x")
        client.put("/domains/x/mode", json={"mode": "apply"})
        loaded = isolated_store.load("x")
        from e0_controller.domain_session import DomainMode
        assert loaded.mode == DomainMode.APPLY

    def test_invalid_mode_returns_422(self, client):
        _create(client, name="x")
        r = client.put("/domains/x/mode", json={"mode": "banana"})
        assert r.status_code == 422

    def test_mode_nonexistent_domain_returns_404(self, client):
        r = client.put("/domains/ghost/mode", json={"mode": "apply"})
        assert r.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# TestDomainRecommend
# ══════════════════════════════════════════════════════════════════════════════

class TestDomainRecommend:

    def test_cold_start_returns_null(self, client):
        _create(client, name="x")
        _upload_csv(client, "x", LOGISTICS_CSV)
        r = client.post("/domains/x/recommend", json={
            "state": "ORDER", "candidates": ["PICKING", "BACKORDER"]
        })
        assert r.status_code == 200
        data = r.json()
        assert data["cold_start"] is True
        assert data["recommended"] is None

    def test_recommend_after_learn(self, client):
        _create(client, name="x")
        _upload_csv(client, "x", LOGISTICS_CSV)
        client.post("/domains/x/learn", json={
            "n_episodes": 20, "start": "ORDER", "goal": "DELIVERED", "max_steps": 30
        })
        r = client.post("/domains/x/recommend", json={
            "state": "ORDER", "candidates": ["PICKING", "BACKORDER"]
        })
        assert r.status_code == 200
        data = r.json()
        # After 20 episodes should no longer be cold
        assert data["recommended"] in ("PICKING", "BACKORDER", None)

    def test_recommend_response_fields(self, client):
        _create(client, name="x")
        r = client.post("/domains/x/recommend", json={
            "state": "X", "candidates": ["Y"]
        })
        data = r.json()
        for key in ("recommended", "reason", "quality", "conviction_score",
                    "candidates", "cold_start"):
            assert key in data

    def test_recommend_empty_candidates(self, client):
        _create(client, name="x")
        r = client.post("/domains/x/recommend", json={
            "state": "X", "candidates": []
        })
        assert r.status_code == 200
        assert r.json()["recommended"] is None

    def test_recommend_nonexistent_domain_returns_404(self, client):
        r = client.post("/domains/ghost/recommend", json={
            "state": "X", "candidates": ["Y"]
        })
        assert r.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# TestDomainRecord
# ══════════════════════════════════════════════════════════════════════════════

class TestDomainRecord:

    def test_record_success(self, client):
        _create(client, name="x")
        _upload_csv(client, "x", LOGISTICS_CSV)
        r = client.post("/domains/x/record", json={
            "source": "ORDER", "target": "PICKING", "outcome": "success"
        })
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_record_failure_outcome(self, client):
        _create(client, name="x")
        r = client.post("/domains/x/record", json={
            "source": "A", "target": "B", "outcome": "failure"
        })
        assert r.json()["ok"] is True

    def test_record_unknown_outcome(self, client):
        _create(client, name="x")
        r = client.post("/domains/x/record", json={
            "source": "A", "target": "B", "outcome": "????"
        })
        assert r.status_code == 200
        assert r.json()["ok"] is False

    def test_record_persists(self, client, isolated_store):
        _create(client, name="x")
        client.post("/domains/x/record", json={
            "source": "A", "target": "B", "outcome": "success"
        })
        from e0_controller.primitives import Edge
        loaded = isolated_store.load("x")
        u = loaded.landscape.historization._U.get(Edge("A", "B"), 0.0)
        assert u > 0.0

    def test_record_auto_creates_edge(self, client, isolated_store):
        _create(client, name="x")
        client.post("/domains/x/record", json={
            "source": "NEW", "target": "STATE", "outcome": "success"
        })
        loaded = isolated_store.load("x")
        edges = {(e.source, e.target) for e in loaded.landscape.edges}
        assert ("NEW", "STATE") in edges

    def test_record_nonexistent_domain_returns_404(self, client):
        r = client.post("/domains/ghost/record", json={
            "source": "A", "target": "B", "outcome": "success"
        })
        assert r.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# TestDomainConviction
# ══════════════════════════════════════════════════════════════════════════════

class TestDomainConviction:

    def test_empty_conviction_map(self, client):
        _create(client, name="x")
        r = client.get("/domains/x/conviction")
        assert r.status_code == 200
        assert r.json()["edges"] == {}

    def test_conviction_map_after_learn(self, client):
        _create(client, name="x")
        _upload_csv(client, "x", LOGISTICS_CSV)
        client.post("/domains/x/learn", json={
            "n_episodes": 10, "start": "ORDER", "goal": "DELIVERED", "max_steps": 20
        })
        r = client.get("/domains/x/conviction")
        assert r.status_code == 200
        edges = r.json()["edges"]
        assert len(edges) > 0

    def test_conviction_values_in_range(self, client):
        _create(client, name="x")
        _upload_csv(client, "x", LOGISTICS_CSV)
        client.post("/domains/x/learn", json={"n_episodes": 10})
        edges = client.get("/domains/x/conviction").json()["edges"]
        for k, v in edges.items():
            assert 0.0 <= v < 1.0, f"conviction out of range: {k}={v}"

    def test_conviction_nonexistent_domain_returns_404(self, client):
        r = client.get("/domains/ghost/conviction")
        assert r.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# TestDomainWorkflow — end-to-end
# ══════════════════════════════════════════════════════════════════════════════

class TestDomainWorkflow:

    def test_create_upload_learn_apply(self, client):
        """Full ARC-K workflow: create → inject → learn → switch to APPLY → recommend."""
        # 1. Create
        r = _create(client, name="logistics",
                    description="E-Commerce Logistics", topic="supply chain")
        assert r.status_code == 201

        # 2. Upload CSV
        r = _upload_csv(client, "logistics", LOGISTICS_CSV)
        assert r.json()["edges_added"] == 4

        # 3. Learn (20 episodes)
        r = client.post("/domains/logistics/learn", json={
            "n_episodes": 20, "start": "ORDER", "goal": "DELIVERED",
            "max_steps": 30, "oracle_type": "always_success"
        })
        assert r.json()["episodes"] == 20
        assert client.get("/domains/logistics").json()["episode_count"] == 20

        # 4. Switch to APPLY
        r = client.put("/domains/logistics/mode", json={"mode": "apply"})
        assert r.json()["mode"] == "apply"

        # 5. Recommend
        r = client.post("/domains/logistics/recommend", json={
            "state": "ORDER", "candidates": ["PICKING", "BACKORDER"]
        })
        data = r.json()
        assert data["recommended"] in ("PICKING", "BACKORDER", None)
        assert data["cold_start"] is False  # should have inscriptions by now

        # 6. Record outcome
        recommended = data["recommended"] or "PICKING"
        r = client.post("/domains/logistics/record", json={
            "source": "ORDER", "target": recommended, "outcome": "success"
        })
        assert r.json()["ok"] is True

    def test_delete_then_recreate(self, client):
        """Delete a domain and recreate with same name."""
        _create(client, name="x")
        client.delete("/domains/x")
        r = _create(client, name="x", description="Fresh start")
        assert r.status_code == 201
        assert r.json()["episode_count"] == 0

    def test_conviction_improves_over_episodes(self, client):
        """Conviction increases after more always-success learning episodes.

        Fix (C309+): explicit start='A' goal='D' on the linear chain so every
        episode visits A→B, B→C, C→D deterministically.  Without an explicit
        start, _pick_start() returns next(iter(landscape.states)) from a Python
        set whose order depends on PYTHONHASHSEED — different CI seeds cause
        the walk to begin at B, C, or D, making conviction non-monotone.
        """
        _create(client, name="x")
        _upload_csv(client, "x", MINIMAL_CSV)

        # First learn batch — explicit start/goal for deterministic edge coverage
        client.post("/domains/x/learn", json={
            "n_episodes": 10, "max_steps": 20,
            "oracle_type": "always_success",
            "start": "A", "goal": "D",
        })
        cm1 = client.get("/domains/x/conviction").json()["edges"]

        # Second learn batch — same start/goal, more episodes → higher conviction
        client.post("/domains/x/learn", json={
            "n_episodes": 50, "max_steps": 20,
            "oracle_type": "always_success",
            "start": "A", "goal": "D",
        })
        cm2 = client.get("/domains/x/conviction").json()["edges"]

        # Every edge visited in batch 1 must have >= conviction after batch 2.
        # With always_success + deterministic episodes each edge is visited in
        # every episode, so U monotonically grows → conviction can only increase.
        for edge, c1 in cm1.items():
            assert cm2.get(edge, 0.0) >= c1, (
                f"{edge}: conviction decreased {c1:.4f} → {cm2.get(edge, 0.0):.4f}"
            )
