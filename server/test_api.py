"""Tests for E₀ API Gateway (Layer C).  C84.

Uses FastAPI TestClient for synchronous REST testing.
WebSocket tests use the TestClient's WebSocket support.
"""

from __future__ import annotations

import json
import pytest

from fastapi.testclient import TestClient

from server.main import app, manager
from server.routes_sessions import set_manager
from e0_controller.service import SessionManager


# ══════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════

@pytest.fixture(autouse=True)
def fresh_manager():
    """Reset the SessionManager for each test."""
    mgr = SessionManager()
    set_manager(mgr)
    # Also update the module-level manager in main
    import server.main
    server.main.manager = mgr
    yield mgr


@pytest.fixture
def client():
    return TestClient(app)


SIMPLE_SPEC = {
    "nodes": ["A", "B", "C", "D"],
    "edges": [
        {"from": "A", "to": "B", "delta": 0.5, "resistance": 1.0},
        {"from": "B", "to": "C", "delta": 0.5, "resistance": 1.0},
        {"from": "C", "to": "D", "delta": 0.5, "resistance": 1.0},
    ],
}


def _create_session(client, spec=None):
    """Helper: create a session and return the response."""
    return client.post("/sessions", json={
        "mode": "json",
        "spec": spec or SIMPLE_SPEC,
    })


# ══════════════════════════════════════════════
# Health
# ══════════════════════════════════════════════

class TestHealth:

    def test_health_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["active_sessions"] == 0

    def test_health_counts_sessions(self, client):
        _create_session(client)
        r = client.get("/health")
        assert r.json()["active_sessions"] == 1


# ══════════════════════════════════════════════
# Session CRUD
# ══════════════════════════════════════════════

class TestSessionCreate:

    def test_create_from_json(self, client):
        r = _create_session(client)
        assert r.status_code == 201
        data = r.json()
        assert "session_id" in data
        assert data["state"] == "created"
        assert data["landscape_states"] == 4
        assert data["landscape_edges"] == 3

    def test_create_missing_spec(self, client):
        r = client.post("/sessions", json={"mode": "json"})
        assert r.status_code == 400

    def test_create_invalid_spec(self, client):
        r = client.post("/sessions", json={
            "mode": "json",
            "spec": {"nodes": [], "edges": []},
        })
        assert r.status_code == 422

    def test_create_from_canon(self, client):
        from e0_controller.canon_loader import list_canons
        canons = list_canons()
        if not canons:
            pytest.skip("No canons available")
        r = client.post("/sessions", json={
            "mode": "canon",
            "canon_name": canons[0],
        })
        assert r.status_code == 201

    def test_create_canon_missing_name(self, client):
        r = client.post("/sessions", json={"mode": "canon"})
        assert r.status_code == 400

    def test_create_canon_unknown(self, client):
        r = client.post("/sessions", json={
            "mode": "canon",
            "canon_name": "nonexistent_xyz",
        })
        assert r.status_code == 404

    def test_create_text_missing(self, client):
        r = client.post("/sessions", json={"mode": "text"})
        assert r.status_code == 400

    def test_create_with_controller_kwargs(self, client):
        r = client.post("/sessions", json={
            "mode": "json",
            "spec": SIMPLE_SPEC,
            "controller_kwargs": {"focus_k": 5, "overload_threshold": 2.0},
        })
        assert r.status_code == 201


class TestSessionGet:

    def test_get_session(self, client):
        cr = _create_session(client).json()
        r = client.get(f"/sessions/{cr['session_id']}")
        assert r.status_code == 200
        data = r.json()
        assert data["session_id"] == cr["session_id"]
        assert data["state"] == "created"

    def test_get_nonexistent(self, client):
        r = client.get("/sessions/no_such_id")
        assert r.status_code == 404

    def test_list_sessions(self, client):
        _create_session(client)
        _create_session(client)
        r = client.get("/sessions")
        assert r.status_code == 200
        assert len(r.json()) == 2


class TestSessionDelete:

    def test_delete_session(self, client):
        cr = _create_session(client).json()
        r = client.delete(f"/sessions/{cr['session_id']}")
        assert r.status_code == 204
        r2 = client.get(f"/sessions/{cr['session_id']}")
        assert r2.status_code == 404

    def test_delete_nonexistent(self, client):
        r = client.delete("/sessions/no_such_id")
        assert r.status_code == 404


# ══════════════════════════════════════════════
# Session Lifecycle
# ══════════════════════════════════════════════

class TestSessionLifecycle:

    def test_start_session(self, client):
        cr = _create_session(client).json()
        sid = cr["session_id"]
        r = client.post(f"/sessions/{sid}/start", json={
            "start": "A", "goal": "D", "max_cycles": 50,
        })
        assert r.status_code == 200
        assert r.json()["state"] == "running"

    def test_start_invalid_state(self, client):
        cr = _create_session(client).json()
        sid = cr["session_id"]
        r = client.post(f"/sessions/{sid}/start", json={
            "start": "Z",
        })
        assert r.status_code == 422

    def test_step_before_start(self, client):
        cr = _create_session(client).json()
        sid = cr["session_id"]
        r = client.post(f"/sessions/{sid}/step")
        assert r.status_code == 409

    def test_step_returns_event(self, client):
        cr = _create_session(client).json()
        sid = cr["session_id"]
        client.post(f"/sessions/{sid}/start", json={"start": "A", "goal": "D"})
        r = client.post(f"/sessions/{sid}/step")
        assert r.status_code == 200
        data = r.json()
        assert data["source"] == "A"
        assert data["target"] == "B"
        assert data["outcome"] == "success"

    def test_full_run_via_steps(self, client):
        cr = _create_session(client).json()
        sid = cr["session_id"]
        client.post(f"/sessions/{sid}/start", json={"start": "A", "goal": "D"})
        events = []
        for _ in range(10):
            r = client.post(f"/sessions/{sid}/step")
            if r.status_code == 409:
                break
            data = r.json()
            if data is None:
                break
            events.append(data)
        assert len(events) == 3  # A→B, B→C, C→D

    def test_pause_resume(self, client):
        cr = _create_session(client).json()
        sid = cr["session_id"]
        client.post(f"/sessions/{sid}/start", json={"start": "A", "goal": "D"})
        client.post(f"/sessions/{sid}/step")

        r = client.post(f"/sessions/{sid}/pause")
        assert r.json()["state"] == "paused"

        r = client.post(f"/sessions/{sid}/resume")
        assert r.json()["state"] == "running"


# ══════════════════════════════════════════════
# Data Retrieval
# ══════════════════════════════════════════════

class TestDataRetrieval:

    def _run_session(self, client):
        cr = _create_session(client).json()
        sid = cr["session_id"]
        client.post(f"/sessions/{sid}/start", json={"start": "A", "goal": "D"})
        for _ in range(3):
            client.post(f"/sessions/{sid}/step")
        return sid

    def test_history(self, client):
        sid = self._run_session(client)
        r = client.get(f"/sessions/{sid}/history")
        assert r.status_code == 200
        assert len(r.json()) == 3

    def test_strategy(self, client):
        sid = self._run_session(client)
        r = client.get(f"/sessions/{sid}/strategy")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 3
        assert "trace_quality" in data[0]

    def test_snapshot(self, client):
        sid = self._run_session(client)
        r = client.get(f"/sessions/{sid}/snapshot")
        assert r.status_code == 200
        snap = r.json()
        assert "landscape" in snap
        assert "mode" in snap
        assert snap["state"] == "completed"


# ══════════════════════════════════════════════
# Canons
# ══════════════════════════════════════════════

class TestCanons:

    def test_list_canons(self, client):
        r = client.get("/canons")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_get_canon(self, client):
        from e0_controller.canon_loader import list_canons
        canons = list_canons()
        if not canons:
            pytest.skip("No canons available")
        r = client.get(f"/canons/{canons[0]}")
        assert r.status_code == 200
        data = r.json()
        assert "name" in data
        assert "node_count" in data

    def test_get_unknown_canon(self, client):
        r = client.get("/canons/nonexistent_xyz")
        assert r.status_code == 404


# ══════════════════════════════════════════════
# WebSocket
# ══════════════════════════════════════════════

class TestWebSocket:

    def test_ws_connect_invalid_session(self, client):
        with pytest.raises(Exception):
            with client.websocket_connect("/sessions/no_such/ws"):
                pass

    def test_ws_unknown_event(self, client):
        cr = _create_session(client).json()
        sid = cr["session_id"]
        with client.websocket_connect(f"/sessions/{sid}/ws") as ws:
            ws.send_text(json.dumps({"event": "unknown_event"}))
            msg = ws.receive_json()
            assert msg["event"] == "error"
            assert "Unknown event" in msg["data"]["message"]

    def test_ws_invalid_json(self, client):
        cr = _create_session(client).json()
        sid = cr["session_id"]
        with client.websocket_connect(f"/sessions/{sid}/ws") as ws:
            ws.send_text("not json at all")
            msg = ws.receive_json()
            assert msg["event"] == "error"
            assert "Invalid JSON" in msg["data"]["message"]

    def test_ws_pause_resume(self, client):
        cr = _create_session(client).json()
        sid = cr["session_id"]
        client.post(f"/sessions/{sid}/start", json={"start": "A", "goal": "D"})
        client.post(f"/sessions/{sid}/step")

        with client.websocket_connect(f"/sessions/{sid}/ws") as ws:
            ws.send_text(json.dumps({"event": "pause"}))
            r = client.get(f"/sessions/{sid}")
            assert r.json()["state"] == "paused"

            ws.send_text(json.dumps({"event": "resume"}))
            r = client.get(f"/sessions/{sid}")
            assert r.json()["state"] == "running"
