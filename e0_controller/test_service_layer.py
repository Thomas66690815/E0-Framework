"""Tests for Layer B — Service Layer (C83).

Covers:
  - SnapshotCodec: encode/decode landscape, step, strategy profile, edge info
  - InputPipeline: from_json, from_canon, available_canons
  - PeerBridge: sync fallback, submit_response, is_waiting
  - ServiceSession: lifecycle, events, step, run_sync, pause/resume, snapshot
  - SessionManager: create, get, remove, list
"""

import random
from unittest.mock import MagicMock

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.historization import Historization
from e0_controller.controller import (
    E0Controller,
    EscalationType,
    StepResult,
    RunTrace,
)
from e0_controller.mode_controller import OperatingMode


# ══════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════

def _success(s, t):
    return Outcome.SUCCESS


def _linear_landscape(n: int = 5) -> Landscape:
    """A→B→C→D→E linear chain."""
    states = [chr(65 + i) for i in range(n)]
    L = Landscape()
    for s in states:
        L.add_state(s)
    for i in range(n - 1):
        L.add_edge(states[i], states[i + 1], delta=0.5, resistance=1.0)
    return L


def _diamond_landscape() -> Landscape:
    """A→B, A→C, B→D, C→D diamond."""
    L = Landscape()
    for s in ["A", "B", "C", "D"]:
        L.add_state(s)
    L.add_edge("A", "B", delta=0.5, resistance=1.0)
    L.add_edge("A", "C", delta=0.5, resistance=1.0)
    L.add_edge("B", "D", delta=0.5, resistance=1.0)
    L.add_edge("C", "D", delta=0.5, resistance=1.0)
    return L


def _fc_landscape(n: int = 10) -> Landscape:
    """Fully-connected landscape with n states."""
    states = [f"S{i}" for i in range(n)]
    return Landscape.fully_connected(states, delta=0.5, resistance=1.0)


# ══════════════════════════════════════════════
# SnapshotCodec Tests
# ══════════════════════════════════════════════

class TestSnapshotCodecLandscape:
    """Encode/decode roundtrip for Landscape."""

    def test_encode_contains_states_and_edges(self):
        from e0_controller.snapshot_codec import encode_landscape
        L = _linear_landscape()
        data = encode_landscape(L)
        assert data["states"] == ["A", "B", "C", "D", "E"]
        assert len(data["edges"]) == 4  # A→B, B→C, C→D, D→E

    def test_edge_info_fields_present(self):
        from e0_controller.snapshot_codec import encode_landscape
        L = _linear_landscape()
        data = encode_landscape(L)
        edge = data["edges"]["A→B"]
        for field in ["source", "target", "delta", "R0", "R_eff", "S_eff",
                      "delta_H", "coherence", "v", "U", "F",
                      "trace_quality", "trace_load"]:
            assert field in edge, f"Missing field: {field}"

    def test_modulation_flags(self):
        from e0_controller.snapshot_codec import encode_landscape
        L = _linear_landscape()
        L.inertia_modulation = True
        data = encode_landscape(L)
        assert data["modulation"]["inertia"] is True
        assert data["modulation"]["curvature"] is False

    def test_roundtrip_preserves_structure(self):
        from e0_controller.snapshot_codec import encode_landscape, decode_landscape
        L = _linear_landscape()
        # Run some updates to create historization state
        ctrl = E0Controller(L, _success)
        ctrl.run("A", max_cycles=4, goal="E")

        data = encode_landscape(L)
        L2 = decode_landscape(data)

        assert L2.states == L.states
        assert len(L2.edges) == len(L.edges)
        assert L2.inertia_modulation == L.inertia_modulation
        # Historization roundtrip: tau preserved
        assert L2.historization.tau == L.historization.tau

    def test_roundtrip_preserves_traces(self):
        from e0_controller.snapshot_codec import encode_landscape, decode_landscape
        L = _linear_landscape()
        L.historization.update(Edge("A", "B"), Outcome.SUCCESS)
        L.historization.update(Edge("A", "B"), Outcome.SUCCESS)
        L.historization.update(Edge("A", "B"), Outcome.FAILURE)

        data = encode_landscape(L)
        L2 = decode_landscape(data)

        q_orig = L.historization.trace_quality(Edge("A", "B"))
        q_restored = L2.historization.trace_quality(Edge("A", "B"))
        assert abs(q_orig - q_restored) < 1e-10

    def test_historization_summary_included(self):
        from e0_controller.snapshot_codec import encode_landscape
        L = _linear_landscape()
        data = encode_landscape(L)
        assert "summary" in data
        assert "tau" in data["summary"]


class TestSnapshotCodecStep:
    """Encode StepResult."""

    def test_encode_step_fields(self):
        from e0_controller.snapshot_codec import encode_step
        step = StepResult(
            tau=1, source="A", target="B",
            outcome=Outcome.SUCCESS, s_eff=0.5,
            r_eff_before=1.0, r_eff_after=0.9,
            candidates=["B", "C"],
        )
        data = encode_step(step)
        assert data["tau"] == 1
        assert data["outcome"] == "success"
        assert data["escalation_type"] == "none"
        assert data["candidates"] == ["B", "C"]

    def test_encode_step_with_escalation(self):
        from e0_controller.snapshot_codec import encode_step
        step = StepResult(
            tau=2, source="X", target="Y",
            outcome=Outcome.FAILURE, s_eff=3.0,
            r_eff_before=2.0, r_eff_after=2.5,
            candidates=["Y"],
            escalated=True,
            escalation_type=EscalationType.EXHAUSTED,
        )
        data = encode_step(step)
        assert data["escalated"] is True
        assert data["escalation_type"] == "exhausted"


class TestSnapshotCodecRunTrace:
    """Encode RunTrace."""

    def test_encode_run_trace(self):
        from e0_controller.snapshot_codec import encode_run_trace
        L = _linear_landscape()
        ctrl = E0Controller(L, _success)
        trace = ctrl.run("A", max_cycles=4, goal="E")
        data = encode_run_trace(trace)
        assert "steps" in data
        assert "path" in data
        assert "metrics" in data
        assert len(data["steps"]) == len(trace.steps)


class TestSnapshotCodecStrategy:
    """Encode strategy profile."""

    def test_encode_strategy_profile(self):
        from e0_controller.snapshot_codec import encode_strategy_profile
        L = _linear_landscape()
        L.historization.update(Edge("A", "B"), Outcome.SUCCESS)
        L.historization.update(Edge("B", "C"), Outcome.FAILURE)
        profile = encode_strategy_profile(L.historization)
        assert len(profile) >= 2
        assert "trace_quality" in profile[0]
        assert "edge" in profile[0]
        # First should be highest quality → A→B (success)
        assert profile[0]["edge"] == "A→B"


class TestSnapshotCodecEdgeInfo:
    """Encode edge info for peer dialog."""

    def test_encode_edge_info(self):
        from e0_controller.snapshot_codec import encode_edge_info
        L = _diamond_landscape()
        info = encode_edge_info(L, "A", ["B", "C"])
        assert "B" in info
        assert "C" in info
        assert "S_eff" in info["B"]
        assert "trace_quality" in info["B"]


# ══════════════════════════════════════════════
# InputPipeline Tests
# ══════════════════════════════════════════════

class TestInputPipelineJSON:
    """from_json path."""

    def test_from_json_creates_landscape(self):
        from e0_controller.input_pipeline import InputPipeline
        pipe = InputPipeline()
        spec = {
            "nodes": ["A", "B", "C"],
            "edges": [
                {"from": "A", "to": "B", "delta": 0.5, "resistance": 1.0},
                {"from": "B", "to": "C", "delta": 0.5, "resistance": 1.0},
            ],
        }
        result = pipe.from_json(spec)
        assert result.source == "json"
        assert "A" in result.landscape.states
        assert len(result.landscape.edges) == 2
        assert result.spec_used is spec

    def test_from_json_validates(self):
        from e0_controller.input_pipeline import InputPipeline
        from e0_controller.bootstrapper import BootstrapError
        pipe = InputPipeline()
        import pytest
        with pytest.raises(BootstrapError):
            pipe.from_json({"nodes": [], "edges": []})


class TestInputPipelineCanon:
    """from_canon path."""

    def test_available_canons_returns_list(self):
        from e0_controller.input_pipeline import InputPipeline
        pipe = InputPipeline()
        canons = pipe.available_canons()
        assert isinstance(canons, list)

    def test_from_canon_with_known_canon(self):
        from e0_controller.input_pipeline import InputPipeline
        pipe = InputPipeline()
        canons = pipe.available_canons()
        if not canons:
            import pytest
            pytest.skip("No canons available")
        result = pipe.from_canon(canons[0])
        assert result.source == "canon"
        assert result.canon_name == canons[0]
        assert len(result.landscape.states) > 0

    def test_from_canon_unknown_raises(self):
        from e0_controller.input_pipeline import InputPipeline
        pipe = InputPipeline()
        import pytest
        with pytest.raises(FileNotFoundError):
            pipe.from_canon("nonexistent_canon_xyz")


# ══════════════════════════════════════════════
# PeerBridge Tests
# ══════════════════════════════════════════════

class TestPeerBridgeSync:
    """Synchronous (no event loop) behavior."""

    def test_sync_returns_random_choice(self):
        from e0_controller.peer_bridge import PeerBridge
        bridge = PeerBridge(session_id="test")
        fn = bridge.as_peer_fn()
        L = _diamond_landscape()
        result = fn(L, "A", ["B", "C"])
        assert result in ["B", "C"]

    def test_sync_deterministic_with_seed(self):
        from e0_controller.peer_bridge import PeerBridge
        bridge = PeerBridge(session_id="test")
        fn = bridge.as_peer_fn()
        L = _diamond_landscape()
        r1 = fn(L, "A", ["B", "C"])

        bridge2 = PeerBridge(session_id="test")
        fn2 = bridge2.as_peer_fn()
        r2 = fn2(L, "A", ["B", "C"])
        assert r1 == r2  # Same seed → same choice

    def test_is_waiting_false_initially(self):
        from e0_controller.peer_bridge import PeerBridge
        bridge = PeerBridge(session_id="test")
        assert bridge.is_waiting is False

    def test_pending_request_none_initially(self):
        from e0_controller.peer_bridge import PeerBridge
        bridge = PeerBridge(session_id="test")
        assert bridge.pending_request is None

    def test_submit_response_no_pending(self):
        from e0_controller.peer_bridge import PeerBridge
        bridge = PeerBridge(session_id="test")
        assert bridge.submit_response("B") is False


class TestPeerBridgeOnRequest:
    """on_request callback."""

    def test_on_request_not_called_in_sync_mode(self):
        from e0_controller.peer_bridge import PeerBridge
        mock = MagicMock()
        bridge = PeerBridge(session_id="test", on_request=mock)
        fn = bridge.as_peer_fn()
        L = _diamond_landscape()
        fn(L, "A", ["B", "C"])
        # In sync mode, _sync_peer is called directly — no on_request
        mock.assert_not_called()


# ══════════════════════════════════════════════
# ServiceSession Tests
# ══════════════════════════════════════════════

class TestServiceSessionLifecycle:
    """Basic lifecycle: create → start → step → complete."""

    def test_initial_state(self):
        from e0_controller.service import ServiceSession, SessionState
        L = _linear_landscape()
        s = ServiceSession(L, _success)
        assert s.state == SessionState.CREATED
        assert s.current_position is None

    def test_start_sets_running(self):
        from e0_controller.service import ServiceSession, SessionState
        L = _linear_landscape()
        s = ServiceSession(L, _success)
        s.start("A", goal="E")
        assert s.state == SessionState.RUNNING
        assert s.current_position == "A"

    def test_start_invalid_state_raises(self):
        from e0_controller.service import ServiceSession
        L = _linear_landscape()
        s = ServiceSession(L, _success)
        import pytest
        with pytest.raises(ValueError, match="not in landscape"):
            s.start("Z")

    def test_step_advances_position(self):
        from e0_controller.service import ServiceSession
        L = _linear_landscape()
        s = ServiceSession(L, _success)
        s.start("A", goal="E")
        event = s.step()
        assert event is not None
        assert event.source == "A"
        assert event.target == "B"
        assert s.current_position == "B"

    def test_step_before_start_raises(self):
        from e0_controller.service import ServiceSession
        L = _linear_landscape()
        s = ServiceSession(L, _success)
        import pytest
        with pytest.raises(RuntimeError, match="not started"):
            s.step()

    def test_run_sync_reaches_goal(self):
        from e0_controller.service import ServiceSession, SessionState
        L = _linear_landscape()
        s = ServiceSession(L, _success)
        events = s.run_sync("A", goal="E", max_cycles=10)
        assert s.state == SessionState.COMPLETED
        assert s.current_position == "E"
        assert len(events) == 4  # A→B→C→D→E = 4 steps

    def test_run_sync_stops_at_max_cycles(self):
        from e0_controller.service import ServiceSession, SessionState
        L = _fc_landscape(10)
        s = ServiceSession(L, _success)
        events = s.run_sync("S0", max_cycles=5)
        assert len(events) == 5
        assert s.state == SessionState.COMPLETED


class TestServiceSessionEvents:
    """Event emission."""

    def test_step_emits_event(self):
        from e0_controller.service import ServiceSession
        L = _linear_landscape()
        s = ServiceSession(L, _success)
        received = []
        s.add_listener(lambda t, d: received.append((t, d)))
        s.start("A", goal="E")
        s.step()
        types = [r[0] for r in received]
        assert "started" in types
        assert "step" in types

    def test_completion_emits_completed(self):
        from e0_controller.service import ServiceSession
        L = _linear_landscape()
        s = ServiceSession(L, _success)
        received = []
        s.add_listener(lambda t, d: received.append((t, d)))
        s.run_sync("A", goal="E")
        types = [r[0] for r in received]
        assert "completed" in types

    def test_step_event_has_mode(self):
        from e0_controller.service import ServiceSession
        L = _linear_landscape()
        s = ServiceSession(L, _success)
        s.start("A", goal="E")
        event = s.step()
        assert event.mode in ["learn", "execute", "combination"]


class TestServiceSessionPauseResume:
    """Pause and resume."""

    def test_pause_resume_cycle(self):
        from e0_controller.service import ServiceSession, SessionState
        L = _linear_landscape()
        s = ServiceSession(L, _success)
        s.start("A", goal="E")
        s.step()
        s.pause()
        assert s.state == SessionState.PAUSED
        s.resume()
        assert s.state == SessionState.RUNNING
        event = s.step()
        assert event is not None


class TestServiceSessionSnapshot:
    """Snapshot serialization."""

    def test_snapshot_contains_required_fields(self):
        from e0_controller.service import ServiceSession
        L = _linear_landscape()
        s = ServiceSession(L, _success)
        s.start("A", goal="E")
        s.step()
        snap = s.snapshot()
        assert snap["session_id"] == s.id
        assert snap["state"] == "running"
        assert snap["current_position"] == "B"
        assert "landscape" in snap
        assert "mode" in snap

    def test_strategy_returns_profile(self):
        from e0_controller.service import ServiceSession
        L = _linear_landscape()
        s = ServiceSession(L, _success)
        s.run_sync("A", goal="E")
        profile = s.strategy()
        assert len(profile) >= 4  # At least 4 edges traversed


class TestServiceSessionHistory:
    """History tracking."""

    def test_history_accumulates(self):
        from e0_controller.service import ServiceSession
        L = _linear_landscape()
        s = ServiceSession(L, _success)
        s.run_sync("A", goal="E")
        assert len(s.history) == 4


class TestServiceSessionWithPeer:
    """Integration with PeerBridge in sync mode."""

    def test_peer_bridge_integrates(self):
        from e0_controller.service import ServiceSession
        from e0_controller.peer_bridge import PeerBridge
        L = _fc_landscape(15)
        bridge = PeerBridge(session_id="test")
        s = ServiceSession(L, _success, peer_bridge=bridge,
                           controller_kwargs={"overload_threshold": 0.1})
        # In sync mode, peer_fn falls back to random
        events = s.run_sync("S0", max_cycles=5)
        assert len(events) == 5


# ══════════════════════════════════════════════
# SessionManager Tests
# ══════════════════════════════════════════════

class TestSessionManager:
    """Create, get, remove sessions."""

    def test_create_from_json(self):
        from e0_controller.service import SessionManager
        mgr = SessionManager()
        spec = {
            "nodes": ["A", "B", "C"],
            "edges": [
                {"from": "A", "to": "B", "delta": 0.5, "resistance": 1.0},
                {"from": "B", "to": "C", "delta": 0.5, "resistance": 1.0},
            ],
        }
        s = mgr.create_from_json(spec, _success)
        assert s.id is not None
        assert mgr.get(s.id) is s

    def test_create_from_landscape(self):
        from e0_controller.service import SessionManager
        mgr = SessionManager()
        L = _linear_landscape()
        s = mgr.create_from_landscape(L, _success)
        assert mgr.get(s.id) is s

    def test_remove_session(self):
        from e0_controller.service import SessionManager
        mgr = SessionManager()
        L = _linear_landscape()
        s = mgr.create_from_landscape(L, _success)
        assert mgr.remove(s.id) is True
        assert mgr.get(s.id) is None

    def test_remove_nonexistent(self):
        from e0_controller.service import SessionManager
        mgr = SessionManager()
        assert mgr.remove("nonexistent") is False

    def test_list_sessions(self):
        from e0_controller.service import SessionManager
        mgr = SessionManager()
        L = _linear_landscape()
        mgr.create_from_landscape(L, _success)
        mgr.create_from_landscape(L, _success)
        listing = mgr.list_sessions()
        assert len(listing) == 2
        assert "session_id" in listing[0]
        assert "state" in listing[0]

    def test_multiple_sessions_independent(self):
        from e0_controller.service import SessionManager, SessionState
        mgr = SessionManager()
        L1 = _linear_landscape()
        L2 = _diamond_landscape()
        s1 = mgr.create_from_landscape(L1, _success)
        s2 = mgr.create_from_landscape(L2, _success)
        s1.run_sync("A", goal="E")
        assert s1.state == SessionState.COMPLETED
        assert s2.state == SessionState.CREATED  # s2 unaffected
