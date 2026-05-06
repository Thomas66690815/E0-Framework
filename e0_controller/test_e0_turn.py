"""
Tests for C292: E2Port ABC + E0Turn
=====================================
Covers:
    TestE2Port          — LambdaE2Port satisfies ABC, ExecutionResult fields
    TestE2PortContract  — can_execute default, error contract
    TestTurnResult      — TurnResult.to_dict, __repr__
    TestE0TurnBasic     — single turn, landscape grows, historization updated
    TestE0TurnRun       — multi-turn loop, goal stopping, dead-end stopping
    TestE0TurnEscalation — escalated TurnResult on dead-end
    TestE0TurnInertia   — inertia_low flag after fresh edge vs. warm edge
    TestE0TurnDiagnostics — status(), history()
    TestE0TurnPersistence — save/load round-trip
    TestE0TurnPayload   — payload passed through from E2Port
    TestE0TurnNewState  — state_after from E2Port may differ from action
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from e0_controller.controller import EscalationType
from e0_controller.e2_port import E2Port, ExecutionResult, LambdaE2Port
from e0_controller.e0_turn import E0Turn, TurnResult
from e0_controller.landscape import Landscape
from e0_controller.primitives import Edge, Outcome


# ── Fixtures ──────────────────────────────────────────────────────────────────

def simple_landscape() -> Landscape:
    """Two-state landscape: A → B with standard parameters."""
    ls = Landscape()
    ls.add_edge("A", "B", delta=0.5, resistance=1.0)
    return ls


def isolated_landscape() -> Landscape:
    """Single-state landscape: STUCK with no edges.

    This is the only reliable way to trigger a true dead-end (cycle() returns
    None). DEAD_END escalation does a K5 global jump to another state — but
    if no other state exists, the jump also returns None.
    """
    ls = Landscape()
    ls.add_state("STUCK")
    return ls


def chain_landscape(states: list[str]) -> Landscape:
    """Linear chain: states[0] → states[1] → ... → states[-1]."""
    ls = Landscape()
    for src, tgt in zip(states[:-1], states[1:]):
        ls.add_edge(src, tgt, delta=0.5, resistance=1.0)
    return ls


def always_success_port(name: str = "mock") -> LambdaE2Port:
    return LambdaE2Port(lambda s, a: Outcome.SUCCESS, name=name)


def always_failure_port() -> LambdaE2Port:
    return LambdaE2Port(lambda s, a: Outcome.FAILURE, name="fail")


# ── TestE2Port ────────────────────────────────────────────────────────────────

class TestE2Port:
    def test_lambda_port_id(self):
        port = LambdaE2Port(lambda s, a: Outcome.SUCCESS, name="test_port")
        assert port.port_id() == "test_port"

    def test_lambda_port_default_name(self):
        port = LambdaE2Port(lambda s, a: Outcome.SUCCESS)
        assert port.port_id() == "lambda"

    def test_lambda_returns_outcome(self):
        port = LambdaE2Port(lambda s, a: Outcome.SUCCESS)
        result = port.execute("A", "B")
        assert isinstance(result, ExecutionResult)
        assert result.outcome == Outcome.SUCCESS
        assert result.new_state == "B"  # action → new_state on SUCCESS

    def test_lambda_failure_stays_at_source(self):
        port = LambdaE2Port(lambda s, a: Outcome.FAILURE)
        result = port.execute("A", "B")
        assert result.outcome == Outcome.FAILURE
        assert result.new_state == "A"  # source state on FAILURE

    def test_lambda_partial_treated_as_success_movement(self):
        port = LambdaE2Port(lambda s, a: Outcome.PARTIAL)
        result = port.execute("A", "B")
        assert result.outcome == Outcome.PARTIAL
        assert result.new_state == "B"  # non-FAILURE → moves

    def test_lambda_returns_execution_result_directly(self):
        er = ExecutionResult(new_state="C", outcome=Outcome.SUCCESS, payload=42)
        port = LambdaE2Port(lambda s, a: er)
        result = port.execute("A", "B")
        assert result.new_state == "C"
        assert result.payload == 42

    def test_lambda_returns_str_new_state(self):
        port = LambdaE2Port(lambda s, a: "C")  # string → success with that state
        result = port.execute("A", "B")
        assert result.new_state == "C"
        assert result.outcome == Outcome.SUCCESS

    def test_lambda_invalid_return_type_raises(self):
        port = LambdaE2Port(lambda s, a: 99)  # int → invalid
        with pytest.raises(TypeError):
            port.execute("A", "B")

    def test_can_execute_default_true(self):
        port = LambdaE2Port(lambda s, a: Outcome.SUCCESS)
        assert port.can_execute("A", "B") is True

    def test_e2port_is_abstract(self):
        """E2Port cannot be instantiated directly."""
        with pytest.raises(TypeError):
            E2Port()

    def test_e2port_subclass_must_implement_port_id(self):
        class IncompletePort(E2Port):
            def execute(self, state, action):
                return ExecutionResult(action, Outcome.SUCCESS)

        with pytest.raises(TypeError):
            IncompletePort()

    def test_e2port_subclass_must_implement_execute(self):
        class IncompletePort(E2Port):
            def port_id(self):
                return "test"

        with pytest.raises(TypeError):
            IncompletePort()

    def test_execution_result_error_field(self):
        er = ExecutionResult(
            new_state="A",
            outcome=Outcome.FAILURE,
            error="connection refused"
        )
        assert er.error == "connection refused"


# ── TestE2PortContract ────────────────────────────────────────────────────────

class TestE2PortContract:
    def test_can_execute_can_be_overridden(self):
        class RestrictedPort(E2Port):
            def port_id(self):
                return "restricted"

            def execute(self, state, action):
                return ExecutionResult(action, Outcome.SUCCESS)

            def can_execute(self, state, action):
                return action != "FORBIDDEN"

        port = RestrictedPort()
        assert port.can_execute("A", "B") is True
        assert port.can_execute("A", "FORBIDDEN") is False

    def test_execute_called_with_correct_args(self):
        calls = []

        class RecordingPort(E2Port):
            def port_id(self):
                return "recorder"

            def execute(self, state, action):
                calls.append((state, action))
                return ExecutionResult(action, Outcome.SUCCESS)

        port = RecordingPort()
        port.execute("X", "Y")
        assert calls == [("X", "Y")]


# ── TestTurnResult ────────────────────────────────────────────────────────────

class TestTurnResult:
    def test_to_dict_contains_all_fields(self):
        tr = TurnResult(
            turn_index=3,
            state_before="A",
            action="B",
            state_after="B",
            outcome=Outcome.SUCCESS,
        )
        d = tr.to_dict()
        assert d["turn_index"] == 3
        assert d["state_before"] == "A"
        assert d["action"] == "B"
        assert d["state_after"] == "B"
        assert d["outcome"] == "SUCCESS"
        assert d["escalated"] is False
        assert d["escalation_type"] == "NONE"
        assert d["inertia_low"] is False

    def test_to_dict_none_outcome(self):
        tr = TurnResult(
            turn_index=0,
            state_before="A",
            action=None,
            state_after="A",
            outcome=None,
            escalated=True,
            escalation_type=EscalationType.DEAD_END,
        )
        d = tr.to_dict()
        assert d["outcome"] is None
        assert d["action"] is None
        assert d["escalated"] is True
        assert d["escalation_type"] == "DEAD_END"

    def test_repr_normal_turn(self):
        tr = TurnResult(0, "A", "B", "B", Outcome.SUCCESS)
        r = repr(tr)
        assert "A" in r
        assert "B" in r
        assert "SUCCESS" in r

    def test_repr_shows_escalation(self):
        tr = TurnResult(
            0, "A", None, "A", None,
            escalated=True,
            escalation_type=EscalationType.DEAD_END,
        )
        r = repr(tr)
        assert "ESC:DEAD_END" in r

    def test_repr_shows_inertia_low(self):
        tr = TurnResult(0, "A", "B", "B", Outcome.SUCCESS, inertia_low=True)
        r = repr(tr)
        assert "LOW_I" in r


# ── TestE0TurnBasic ───────────────────────────────────────────────────────────

class TestE0TurnBasic:
    def test_run_turn_returns_turn_result(self):
        ls = simple_landscape()
        session = E0Turn(ls, always_success_port())
        result = session.run_turn("A")
        assert isinstance(result, TurnResult)

    def test_run_turn_state_before(self):
        ls = simple_landscape()
        session = E0Turn(ls, always_success_port())
        result = session.run_turn("A")
        assert result.state_before == "A"

    def test_run_turn_action_is_B(self):
        ls = simple_landscape()
        session = E0Turn(ls, always_success_port())
        result = session.run_turn("A")
        assert result.action == "B"

    def test_run_turn_state_after(self):
        ls = simple_landscape()
        session = E0Turn(ls, always_success_port())
        result = session.run_turn("A")
        assert result.state_after == "B"

    def test_run_turn_outcome_success(self):
        ls = simple_landscape()
        session = E0Turn(ls, always_success_port())
        result = session.run_turn("A")
        assert result.outcome == Outcome.SUCCESS

    def test_run_turn_increments_turn_count(self):
        ls = simple_landscape()
        session = E0Turn(ls, always_success_port())
        session.run_turn("A")
        assert session._turn_count == 1
        # run again from B (no edges → dead-end recorded but count still increments)
        session.run_turn("B")
        assert session._turn_count == 2

    def test_run_turn_historization_updated(self):
        """After a turn, inertia_factor on the edge should have changed."""
        ls = simple_landscape()
        edge = Edge("A", "B")
        # inertia_factor before: fresh edge (low trace_load)
        inertia_before = ls.historization.inertia_factor(edge)

        session = E0Turn(ls, always_success_port())
        session.run_turn("A")

        inertia_after = ls.historization.inertia_factor(edge)
        # After one successful turn, trace_load > 0 → inertia_factor changes
        assert inertia_after != inertia_before

    def test_run_turn_landscape_grows_on_implicit_edge(self):
        """E0Turn uses existing edges; no implicit growth needed in simple case."""
        ls = simple_landscape()
        initial_edge_count = len(ls.edges)
        session = E0Turn(ls, always_success_port())
        session.run_turn("A")
        # edge count unchanged — A→B was already there
        assert len(ls.edges) == initial_edge_count


# ── TestE0TurnRun ─────────────────────────────────────────────────────────────

class TestE0TurnRun:
    def test_run_yields_turn_results(self):
        ls = chain_landscape(["A", "B", "C"])
        session = E0Turn(ls, always_success_port())
        turns = list(session.run("A", max_turns=2))
        assert len(turns) == 2
        assert all(isinstance(t, TurnResult) for t in turns)

    def test_run_stops_at_goal(self):
        ls = chain_landscape(["A", "B", "C"])
        session = E0Turn(ls, always_success_port())
        turns = list(session.run("A", max_turns=10, goal="B"))
        # Should stop after reaching B
        assert all(t.state_before != "B" for t in turns)

    def test_run_stops_at_max_turns(self):
        # Cycle: A → B → A (loop)
        ls = Landscape()
        ls.add_edge("A", "B", delta=0.5, resistance=1.0)
        ls.add_edge("B", "A", delta=0.5, resistance=1.0)
        session = E0Turn(ls, always_success_port())
        turns = list(session.run("A", max_turns=5))
        assert len(turns) <= 5

    def test_run_stops_at_dead_end(self):
        # isolated_landscape has single state STUCK with no edges:
        # cycle() returns None → run() stops after 1 yielded dead-end turn
        ls = isolated_landscape()
        session = E0Turn(ls, always_success_port())
        turns = list(session.run("STUCK", max_turns=100))
        assert len(turns) == 1
        assert turns[0].escalated is True
        assert turns[0].action is None


# ── TestE0TurnEscalation ──────────────────────────────────────────────────────

class TestE0TurnEscalation:
    def test_dead_end_turns_escalated(self):
        # DEAD_END at B in simple_landscape: K5 global jump, escalated=True
        ls = simple_landscape()  # B has no outgoing edges, controller escalates
        session = E0Turn(ls, always_success_port())
        result = session.run_turn("B")
        assert result.escalated is True

    def test_true_dead_end_action_is_none(self):
        # Single-state landscape: no other state to jump to → cycle() returns None
        ls = isolated_landscape()
        session = E0Turn(ls, always_success_port())
        result = session.run_turn("STUCK")
        assert result.action is None

    def test_true_dead_end_state_unchanged(self):
        ls = isolated_landscape()
        session = E0Turn(ls, always_success_port())
        result = session.run_turn("STUCK")
        assert result.state_after == "STUCK"

    def test_true_dead_end_outcome_is_none(self):
        ls = isolated_landscape()
        session = E0Turn(ls, always_success_port())
        result = session.run_turn("STUCK")
        assert result.outcome is None

    def test_escalation_type_dead_end(self):
        # Both simple_landscape (K5 jump) and isolated give DEAD_END type
        ls = simple_landscape()
        session = E0Turn(ls, always_success_port())
        result = session.run_turn("B")
        assert result.escalation_type == EscalationType.DEAD_END

    def test_true_dead_end_escalation_type(self):
        ls = isolated_landscape()
        session = E0Turn(ls, always_success_port())
        result = session.run_turn("STUCK")
        assert result.escalation_type == EscalationType.DEAD_END


# ── TestE0TurnInertia ─────────────────────────────────────────────────────────

class TestE0TurnInertia:
    def test_inertia_low_on_fresh_edge(self):
        """Fresh edge: trace_load = 0 → inertia_factor < threshold → inertia_low."""
        ls = simple_landscape()
        # threshold=1.0 ensures any fresh edge triggers inertia_low
        session = E0Turn(ls, always_success_port(), inertia_threshold=1.0)
        result = session.run_turn("A")
        assert result.inertia_low is True

    def test_inertia_not_low_after_many_successes(self):
        """After many successful turns, inertia_factor rises above 0.3."""
        ls = Landscape()
        ls.add_edge("A", "B", delta=0.5, resistance=1.0)
        ls.add_edge("B", "A", delta=0.5, resistance=1.0)
        session = E0Turn(ls, always_success_port(), inertia_threshold=0.3)
        # Run 20 turns — inertia should stabilize well above 0.3
        turns = list(session.run("A", max_turns=20))
        assert any(not t.inertia_low for t in turns if t.action is not None)

    def test_custom_threshold_respected(self):
        """With threshold=0.0, inertia_low is never True."""
        ls = simple_landscape()
        session = E0Turn(ls, always_success_port(), inertia_threshold=0.0)
        result = session.run_turn("A")
        assert result.inertia_low is False


# ── TestE0TurnDiagnostics ─────────────────────────────────────────────────────

class TestE0TurnDiagnostics:
    def test_status_initial(self):
        ls = simple_landscape()
        session = E0Turn(ls, always_success_port("sensor"))
        s = session.status()
        assert s["port_id"] == "sensor"
        assert s["turn_count"] == 0
        assert s["last_turn"] is None

    def test_status_after_turn(self):
        ls = simple_landscape()
        session = E0Turn(ls, always_success_port())
        session.run_turn("A")
        s = session.status()
        assert s["turn_count"] == 1
        assert s["success_count"] == 1
        assert s["failure_count"] == 0
        assert s["last_turn"] is not None

    def test_status_counts_failures(self):
        ls = simple_landscape()
        session = E0Turn(ls, always_failure_port())
        session.run_turn("A")
        s = session.status()
        assert s["failure_count"] == 1
        assert s["success_count"] == 0

    def test_status_counts_escalations(self):
        ls = simple_landscape()
        session = E0Turn(ls, always_success_port())
        session.run_turn("B")  # dead-end
        s = session.status()
        assert s["escalation_count"] == 1

    def test_history_empty_initially(self):
        ls = simple_landscape()
        session = E0Turn(ls, always_success_port())
        assert session.history() == []

    def test_history_grows_per_turn(self):
        ls = simple_landscape()
        session = E0Turn(ls, always_success_port())
        session.run_turn("A")
        session.run_turn("B")
        assert len(session.history()) == 2

    def test_history_returns_copy(self):
        ls = simple_landscape()
        session = E0Turn(ls, always_success_port())
        session.run_turn("A")
        h = session.history()
        h.clear()
        assert len(session.history()) == 1  # original not affected

    def test_status_landscape_sizes(self):
        ls = simple_landscape()
        session = E0Turn(ls, always_success_port())
        s = session.status()
        assert s["landscape_states"] == 2
        assert s["landscape_edges"] == 1


# ── TestE0TurnPersistence ─────────────────────────────────────────────────────

class TestE0TurnPersistence:
    def test_save_creates_file(self):
        ls = simple_landscape()
        session = E0Turn(ls, always_success_port("s1"))
        session.run_turn("A")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "session.json")
            session.save(path)
            assert Path(path).exists()

    def test_save_valid_json(self):
        ls = simple_landscape()
        session = E0Turn(ls, always_success_port())
        session.run_turn("A")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "session.json")
            session.save(path)
            data = json.loads(Path(path).read_text())
            assert data["version"] == 1

    def test_save_contains_port_id(self):
        ls = simple_landscape()
        session = E0Turn(ls, always_success_port("port_x"))
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "session.json")
            session.save(path)
            data = json.loads(Path(path).read_text())
            assert data["port_id"] == "port_x"

    def test_save_contains_turn_count(self):
        ls = simple_landscape()
        session = E0Turn(ls, always_success_port())
        session.run_turn("A")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "session.json")
            session.save(path)
            data = json.loads(Path(path).read_text())
            assert data["turn_count"] == 1

    def test_save_contains_history(self):
        ls = simple_landscape()
        session = E0Turn(ls, always_success_port())
        session.run_turn("A")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "session.json")
            session.save(path)
            data = json.loads(Path(path).read_text())
            assert len(data["history"]) == 1
            assert data["history"][0]["state_before"] == "A"

    def test_load_history_returns_dict(self):
        ls = simple_landscape()
        session = E0Turn(ls, always_success_port())  # default name="mock"
        session.run_turn("A")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "session.json")
            session.save(path)
            loaded = E0Turn.load_history(path)
            assert loaded["turn_count"] == 1
            assert loaded["port_id"] == "mock"

    def test_round_trip_turn_count(self):
        ls = simple_landscape()
        session1 = E0Turn(ls, always_success_port())
        session1.run_turn("A")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "session.json")
            session1.save(path)
            data = E0Turn.load_history(path)

            ls2 = simple_landscape()
            session2 = E0Turn(ls2, always_success_port())
            session2._turn_count = data["turn_count"]
            assert session2._turn_count == 1


# ── TestE0TurnPayload ─────────────────────────────────────────────────────────

class TestE0TurnPayload:
    def test_payload_none_when_not_provided(self):
        ls = simple_landscape()
        session = E0Turn(ls, always_success_port())
        result = session.run_turn("A")
        assert result.payload is None

    def test_payload_passed_through(self):
        payload_data = {"sensor": "temperature", "value": 37.5}
        port = LambdaE2Port(
            lambda s, a: ExecutionResult("B", Outcome.SUCCESS, payload=payload_data)
        )
        ls = simple_landscape()
        session = E0Turn(ls, port)
        result = session.run_turn("A")
        assert result.payload == payload_data

    def test_payload_arbitrary_type(self):
        port = LambdaE2Port(
            lambda s, a: ExecutionResult("B", Outcome.SUCCESS, payload=[1, 2, 3])
        )
        ls = simple_landscape()
        session = E0Turn(ls, port)
        result = session.run_turn("A")
        assert result.payload == [1, 2, 3]


# ── TestE0TurnNewState ────────────────────────────────────────────────────────

class TestE0TurnNewState:
    def test_state_after_matches_action_on_success(self):
        ls = simple_landscape()
        session = E0Turn(ls, always_success_port())
        result = session.run_turn("A")
        assert result.state_after == result.action

    def test_state_after_can_differ_from_action(self):
        """E2Port may return unexpected new_state (e.g., actuator fault)."""
        # E0 selects B, but actuator ends up at C
        port = LambdaE2Port(
            lambda s, a: ExecutionResult("C", Outcome.PARTIAL)
        )
        ls = simple_landscape()
        session = E0Turn(ls, port)
        result = session.run_turn("A")
        assert result.action == "B"      # E0 intended B
        assert result.state_after == "C"  # world ended up at C

    def test_state_after_stays_at_source_on_failure(self):
        ls = simple_landscape()
        session = E0Turn(ls, always_failure_port())
        result = session.run_turn("A")
        assert result.state_after == "A"
        assert result.outcome == Outcome.FAILURE
