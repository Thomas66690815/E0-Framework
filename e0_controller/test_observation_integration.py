"""Tests for observation integration in ServiceSession (C97).

Covers:
  - ServiceSession.observation_ctrl lazy init
  - ServiceSession.observation_snapshot() → GraphView-compatible format
  - ServiceSession.observation_meta_snapshot()
  - ServiceSession.observation_navigate() with all actions
  - REST route models (ObservationNavigateRequest)
"""

import math

import pytest

from e0_controller.primitives import Outcome
from e0_controller.landscape import Landscape
from e0_controller.service import ServiceSession
from server.models import ObservationNavigateRequest


# ── Helpers ──────────────────────────────────────────────

def _success(s, t):
    return Outcome.SUCCESS


def _triangle() -> Landscape:
    """A→B→C with A→C shortcut."""
    L = Landscape()
    for s in ["A", "B", "C"]:
        L.add_state(s)
    L.add_edge("A", "B", delta=0.3, resistance=0.4)
    L.add_edge("B", "C", delta=0.3, resistance=0.4)
    L.add_edge("A", "C", delta=0.5, resistance=0.6)
    return L


def _make_session() -> ServiceSession:
    return ServiceSession(_triangle(), _success)


# ── Lazy init ────────────────────────────────────────────

class TestObservationCtrl:
    def test_lazy_creates_controller(self):
        s = _make_session()
        assert s._observation_ctrl is None
        ctrl = s.observation_ctrl
        assert ctrl is not None
        assert s._observation_ctrl is ctrl

    def test_lazy_reuses_controller(self):
        s = _make_session()
        c1 = s.observation_ctrl
        c2 = s.observation_ctrl
        assert c1 is c2

    def test_ctrl_uses_session_landscape(self):
        s = _make_session()
        assert s.observation_ctrl.domain is s.landscape


# ── Observation snapshot ─────────────────────────────────

class TestObservationSnapshot:
    def test_has_landscape_key(self):
        s = _make_session()
        snap = s.observation_snapshot()
        assert "landscape" in snap
        assert "states" in snap["landscape"]
        assert "edges" in snap["landscape"]

    def test_states_are_domain_states(self):
        s = _make_session()
        snap = s.observation_snapshot()
        # At global/topo: all 3 nodes visible
        assert sorted(snap["landscape"]["states"]) == ["A", "B", "C"]

    def test_edges_in_snapshot_codec_format(self):
        s = _make_session()
        snap = s.observation_snapshot()
        edges = snap["landscape"]["edges"]
        assert "A→B" in edges
        e = edges["A→B"]
        assert "source" in e
        assert "target" in e
        assert e["source"] == "A"
        assert e["target"] == "B"

    def test_observation_metadata(self):
        s = _make_session()
        snap = s.observation_snapshot()
        assert "observation" in snap
        obs = snap["observation"]
        assert obs["scope"] == "g"
        assert obs["depth"] == "topo"
        assert obs["focused_node"] is None

    def test_session_id_in_snapshot(self):
        s = _make_session()
        snap = s.observation_snapshot()
        assert snap["session_id"] == s.id

    def test_modulation_in_snapshot(self):
        s = _make_session()
        snap = s.observation_snapshot()
        assert "modulation" in snap

    def test_after_focus_shows_local_view(self):
        s = _make_session()
        s.observation_ctrl.focus("A")
        snap = s.observation_snapshot()
        obs = snap["observation"]
        assert obs["focused_node"] == "A"
        assert obs["scope"] == "n:A"
        # Local to A: A and its neighbors (B, C)
        assert "A" in snap["landscape"]["states"]

    def test_after_deepen_shows_field_data(self):
        s = _make_session()
        s.observation_ctrl.deepen()
        snap = s.observation_snapshot()
        obs = snap["observation"]
        assert obs["depth"] == "field"
        # Field data should have nonzero values
        edges = snap["landscape"]["edges"]
        assert edges["A→B"]["R0"] > 0


# ── Meta snapshot ────────────────────────────────────────

class TestObservationMeta:
    def test_has_landscape_key(self):
        s = _make_session()
        snap = s.observation_meta_snapshot()
        assert "landscape" in snap
        assert "states" in snap["landscape"]
        assert "edges" in snap["landscape"]

    def test_states_are_obs_states(self):
        s = _make_session()
        snap = s.observation_meta_snapshot()
        states = snap["landscape"]["states"]
        # O-Landscape has (1 + N) * 5 states for N domain nodes
        assert len(states) == (1 + 3) * 5  # 20

    def test_observation_is_meta(self):
        s = _make_session()
        snap = s.observation_meta_snapshot()
        assert snap["observation"].get("is_meta") is True


# ── Navigate ─────────────────────────────────────────────

class TestObservationNavigate:
    def test_deepen(self):
        s = _make_session()
        result = s.observation_navigate("deepen")
        assert result["success"] is True
        assert s.observation_ctrl.depth == "field"

    def test_retreat(self):
        s = _make_session()
        s.observation_ctrl.deepen()
        result = s.observation_navigate("retreat")
        assert result["success"] is True
        assert s.observation_ctrl.depth == "topo"

    def test_focus(self):
        s = _make_session()
        result = s.observation_navigate("focus", "B")
        assert result["success"] is True
        assert s.observation_ctrl.focused_node == "B"

    def test_focus_requires_node_id(self):
        s = _make_session()
        with pytest.raises(ValueError, match="focus requires node_id"):
            s.observation_navigate("focus")

    def test_defocus(self):
        s = _make_session()
        s.observation_ctrl.focus("A")
        result = s.observation_navigate("defocus")
        assert result["success"] is True
        assert s.observation_ctrl.focused_node is None

    def test_move(self):
        s = _make_session()
        s.observation_ctrl.focus("A")
        result = s.observation_navigate("move", "B")
        assert result["success"] is True
        assert s.observation_ctrl.focused_node == "B"

    def test_move_requires_node_id(self):
        s = _make_session()
        s.observation_ctrl.focus("A")
        with pytest.raises(ValueError, match="move requires node_id"):
            s.observation_navigate("move")

    def test_unknown_action(self):
        s = _make_session()
        with pytest.raises(ValueError, match="Unknown observation action"):
            s.observation_navigate("fly")

    def test_result_has_r_eff_s_eff(self):
        s = _make_session()
        result = s.observation_navigate("deepen")
        assert "r_eff" in result
        assert "s_eff" in result
        assert result["r_eff"] < math.inf

    def test_retreat_at_topo_fails(self):
        s = _make_session()
        result = s.observation_navigate("retreat")
        assert result["success"] is False

    def test_navigate_then_snapshot(self):
        """Full round-trip: navigate then get snapshot."""
        s = _make_session()
        s.observation_navigate("focus", "A")
        s.observation_navigate("deepen")
        snap = s.observation_snapshot()
        assert snap["observation"]["focused_node"] == "A"
        assert snap["observation"]["depth"] == "field"
        edges = snap["landscape"]["edges"]
        # Should have nonzero field data
        for e in edges.values():
            assert "delta" in e


# ── Pydantic model ───────────────────────────────────────

class TestObservationModel:
    def test_valid_action(self):
        req = ObservationNavigateRequest(action="focus", node_id="A")
        assert req.action == "focus"
        assert req.node_id == "A"

    def test_action_without_node(self):
        req = ObservationNavigateRequest(action="deepen")
        assert req.node_id is None

    def test_invalid_action_rejected(self):
        with pytest.raises(Exception):
            ObservationNavigateRequest(action="jump")
