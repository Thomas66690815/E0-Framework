"""
Tests for C295: RoutingE2Port (E2Port Registry)
================================================
Covers:
    TestRoutingRule              — predicate logic, priority, label
    TestRoutingE2PortInterface   — ABC compliance, port_id, can_execute
    TestRoutingE2PortDispatch    — routing logic, priority order, fallback
    TestRoutingE2PortExecute     — delegation, error wrapping, FAILURE
    TestRoutingE2PortInspection  — ports(), status(), dispatch_counts
    TestRoutingE2PortConstructors — for_states, for_actions, for_action_prefixes, for_pairs
    TestRoutingE2PortE0Integration — full E0Turn with RoutingE2Port
"""

from __future__ import annotations

import pytest

from e0_controller.e2_port import E2Port, ExecutionResult, LambdaE2Port
from e0_controller.e2_port_registry import RoutingE2Port, RoutingRule
from e0_controller.e0_turn import E0Turn
from e0_controller.landscape import Landscape
from e0_controller.primitives import Outcome


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_port(name: str, outcome: Outcome = Outcome.SUCCESS) -> LambdaE2Port:
    """Create a named LambdaE2Port with fixed outcome."""
    def fn(state, action):
        return ExecutionResult(
            new_state=action if outcome != Outcome.FAILURE else state,
            outcome=outcome,
            payload=f"{name}:{state}→{action}",
        )
    return LambdaE2Port(fn=fn, name=name)


def make_raising_port(name: str) -> E2Port:
    """Create a port whose execute() raises (contract violation)."""
    class RaisingPort(E2Port):
        def port_id(self): return name
        def execute(self, state, action):
            raise RuntimeError(f"{name} exploded")
    return RaisingPort()


def simple_landscape() -> Landscape:
    ls = Landscape()
    ls.add_edge("A", "B", delta=0.5, resistance=1.0)
    ls.add_edge("B", "C", delta=0.5, resistance=1.0)
    return ls


def multi_landscape() -> Landscape:
    ls = Landscape()
    ls.add_edge("DRAFT", "REVIEW", delta=0.5, resistance=1.0)
    ls.add_edge("REVIEW", "APPROVE", delta=0.5, resistance=1.0)
    ls.add_edge("APPROVE", "PUBLISH", delta=0.5, resistance=1.0)
    return ls


# ── TestRoutingRule ───────────────────────────────────────────────────────────

class TestRoutingRule:
    def test_matches_true(self):
        port = make_port("p")
        rule = RoutingRule(port=port, predicate=lambda s, a: s == "A")
        assert rule.matches("A", "B") is True

    def test_matches_false(self):
        port = make_port("p")
        rule = RoutingRule(port=port, predicate=lambda s, a: s == "X")
        assert rule.matches("A", "B") is False

    def test_matches_never_raises(self):
        port = make_port("p")
        rule = RoutingRule(port=port, predicate=lambda s, a: 1 / 0)
        assert rule.matches("A", "B") is False

    def test_label_stored(self):
        port = make_port("p")
        rule = RoutingRule(port=port, predicate=lambda s, a: True, label="my_rule")
        assert rule.label == "my_rule"

    def test_priority_default(self):
        port = make_port("p")
        rule = RoutingRule(port=port, predicate=lambda s, a: True)
        assert rule.priority == 0


# ── TestRoutingE2PortInterface ────────────────────────────────────────────────

class TestRoutingE2PortInterface:
    def test_is_e2port_subclass(self):
        fallback = make_port("fb")
        router = RoutingE2Port(fallback=fallback)
        assert isinstance(router, E2Port)

    def test_default_port_id(self):
        fallback = make_port("fb")
        router = RoutingE2Port(fallback=fallback)
        assert router.port_id() == "router"

    def test_custom_port_id(self):
        fallback = make_port("fb")
        router = RoutingE2Port(fallback=fallback, name="my_router")
        assert router.port_id() == "my_router"

    def test_can_execute_delegates_to_route(self):
        fallback = make_port("fb")
        router = RoutingE2Port(fallback=fallback)
        # Default can_execute on LambdaE2Port is True
        assert router.can_execute("A", "B") is True

    def test_can_execute_respects_matched_port(self):
        class RestrictedPort(E2Port):
            def port_id(self): return "restricted"
            def execute(self, s, a): return ExecutionResult(a, Outcome.SUCCESS)
            def can_execute(self, s, a): return False

        restricted = RestrictedPort()
        fallback = make_port("fb")
        router = RoutingE2Port(fallback=fallback)
        router.add(restricted, predicate=lambda s, a: s == "A")
        assert router.can_execute("A", "B") is False
        assert router.can_execute("X", "B") is True  # fallback → True


# ── TestRoutingE2PortDispatch ─────────────────────────────────────────────────

class TestRoutingE2PortDispatch:
    def test_no_rules_returns_fallback(self):
        fallback = make_port("fb")
        router = RoutingE2Port(fallback=fallback)
        assert router.route("A", "B") is fallback

    def test_matching_rule_returns_port(self):
        fallback = make_port("fb")
        p1 = make_port("p1")
        router = RoutingE2Port(fallback=fallback)
        router.add(p1, predicate=lambda s, a: s == "A")
        assert router.route("A", "B") is p1

    def test_non_matching_rule_returns_fallback(self):
        fallback = make_port("fb")
        p1 = make_port("p1")
        router = RoutingE2Port(fallback=fallback)
        router.add(p1, predicate=lambda s, a: s == "X")
        assert router.route("A", "B") is fallback

    def test_higher_priority_wins(self):
        fallback = make_port("fb")
        p_low  = make_port("low")
        p_high = make_port("high")
        router = RoutingE2Port(fallback=fallback)
        # Both match "A" — high priority wins
        router.add(p_low,  predicate=lambda s, a: s == "A", priority=0)
        router.add(p_high, predicate=lambda s, a: s == "A", priority=10)
        assert router.route("A", "B") is p_high

    def test_first_insertion_wins_equal_priority(self):
        fallback = make_port("fb")
        p1 = make_port("first")
        p2 = make_port("second")
        router = RoutingE2Port(fallback=fallback)
        router.add(p1, predicate=lambda s, a: True, priority=5)
        router.add(p2, predicate=lambda s, a: True, priority=5)
        # Python's stable sort guarantees first-inserted comes first
        assert router.route("A", "B") is p1

    def test_add_returns_self_for_chaining(self):
        fallback = make_port("fb")
        p1 = make_port("p1")
        router = RoutingE2Port(fallback=fallback)
        result = router.add(p1, predicate=lambda s, a: True)
        assert result is router

    def test_multiple_rules_correct_dispatch(self):
        fallback = make_port("fb")
        p_a = make_port("p_a")
        p_b = make_port("p_b")
        router = RoutingE2Port(fallback=fallback)
        router.add(p_a, predicate=lambda s, a: s == "A")
        router.add(p_b, predicate=lambda s, a: s == "B")
        assert router.route("A", "C") is p_a
        assert router.route("B", "C") is p_b
        assert router.route("X", "C") is fallback


# ── TestRoutingE2PortExecute ──────────────────────────────────────────────────

class TestRoutingE2PortExecute:
    def test_execute_returns_execution_result(self):
        fallback = make_port("fb")
        router = RoutingE2Port(fallback=fallback)
        result = router.execute("A", "B")
        assert isinstance(result, ExecutionResult)

    def test_execute_fallback_on_no_match(self):
        fallback = make_port("fb", Outcome.SUCCESS)
        router = RoutingE2Port(fallback=fallback)
        result = router.execute("A", "B")
        assert result.outcome == Outcome.SUCCESS
        assert result.payload == "fb:A→B"

    def test_execute_matched_port(self):
        fallback = make_port("fb")
        p1 = make_port("p1", Outcome.SUCCESS)
        router = RoutingE2Port(fallback=fallback)
        router.add(p1, predicate=lambda s, a: s == "A")
        result = router.execute("A", "B")
        assert result.payload == "p1:A→B"

    def test_execute_failure_outcome_passthrough(self):
        fallback = make_port("fb", Outcome.FAILURE)
        router = RoutingE2Port(fallback=fallback)
        result = router.execute("A", "B")
        assert result.outcome == Outcome.FAILURE

    def test_execute_raising_port_returns_failure(self):
        """If a port raises (contract violation), router returns FAILURE."""
        bad = make_raising_port("bad")
        fallback = make_port("fb")
        router = RoutingE2Port(fallback=fallback)
        router.add(bad, predicate=lambda s, a: True, priority=10)
        result = router.execute("A", "B")
        assert result.outcome == Outcome.FAILURE
        assert result.error is not None

    def test_execute_raising_port_state_unchanged(self):
        bad = make_raising_port("bad")
        fallback = make_port("fb")
        router = RoutingE2Port(fallback=fallback)
        router.add(bad, predicate=lambda s, a: True, priority=10)
        result = router.execute("A", "B")
        assert result.new_state == "A"

    def test_execute_never_raises(self):
        bad = make_raising_port("bad")
        fallback = make_port("fb")
        router = RoutingE2Port(fallback=fallback)
        router.add(bad, predicate=lambda s, a: True, priority=10)
        try:
            router.execute("A", "B")
        except Exception as e:
            pytest.fail(f"execute() raised: {e}")


# ── TestRoutingE2PortInspection ───────────────────────────────────────────────

class TestRoutingE2PortInspection:
    def test_ports_includes_fallback(self):
        fallback = make_port("fb")
        router = RoutingE2Port(fallback=fallback)
        assert "fb" in router.ports()

    def test_ports_includes_registered(self):
        fallback = make_port("fb")
        p1 = make_port("p1")
        router = RoutingE2Port(fallback=fallback)
        router.add(p1, predicate=lambda s, a: True)
        assert "p1" in router.ports()
        assert "fb" in router.ports()

    def test_status_port_id(self):
        fallback = make_port("fb")
        router = RoutingE2Port(fallback=fallback, name="myrouter")
        assert router.status()["port_id"] == "myrouter"

    def test_status_rule_count(self):
        fallback = make_port("fb")
        p1 = make_port("p1")
        p2 = make_port("p2")
        router = RoutingE2Port(fallback=fallback)
        router.add(p1, predicate=lambda s, a: True)
        router.add(p2, predicate=lambda s, a: True)
        assert router.status()["rule_count"] == 2

    def test_status_fallback_name(self):
        fallback = make_port("my_fallback")
        router = RoutingE2Port(fallback=fallback)
        assert router.status()["fallback"] == "my_fallback"

    def test_dispatch_counts_increment(self):
        fallback = make_port("fb")
        p1 = make_port("p1")
        router = RoutingE2Port(fallback=fallback)
        router.add(p1, predicate=lambda s, a: s == "A")
        router.execute("A", "B")
        router.execute("A", "B")
        router.execute("X", "B")  # fallback
        counts = router.status()["dispatch_counts"]
        assert counts.get("p1", 0) == 2
        assert counts.get("fb", 0) == 1

    def test_status_rules_list(self):
        fallback = make_port("fb")
        p1 = make_port("p1")
        router = RoutingE2Port(fallback=fallback)
        router.add(p1, predicate=lambda s, a: True, label="my_rule")
        rules = router.status()["rules"]
        assert len(rules) == 1
        assert rules[0]["label"] == "my_rule"
        assert rules[0]["port"] == "p1"


# ── TestRoutingE2PortConstructors ─────────────────────────────────────────────

class TestRoutingE2PortConstructors:
    def test_for_states_matches_state(self):
        fallback = make_port("fb")
        p1 = make_port("p1")
        router = RoutingE2Port.for_states({"DRAFT": p1}, fallback=fallback)
        assert router.route("DRAFT", "REVIEW") is p1

    def test_for_states_fallback_on_mismatch(self):
        fallback = make_port("fb")
        p1 = make_port("p1")
        router = RoutingE2Port.for_states({"DRAFT": p1}, fallback=fallback)
        assert router.route("REVIEW", "APPROVE") is fallback

    def test_for_actions_matches_action(self):
        fallback = make_port("fb")
        p1 = make_port("p1")
        router = RoutingE2Port.for_actions({"PUBLISH": p1}, fallback=fallback)
        assert router.route("X", "PUBLISH") is p1

    def test_for_actions_fallback_on_mismatch(self):
        fallback = make_port("fb")
        p1 = make_port("p1")
        router = RoutingE2Port.for_actions({"PUBLISH": p1}, fallback=fallback)
        assert router.route("X", "REVIEW") is fallback

    def test_for_action_prefixes_matches_prefix(self):
        fallback = make_port("fb")
        p1 = make_port("p1")
        router = RoutingE2Port.for_action_prefixes({"LLM_": p1}, fallback=fallback)
        assert router.route("A", "LLM_DRAFT") is p1
        assert router.route("A", "DB_QUERY") is fallback

    def test_for_pairs_matches_exact(self):
        fallback = make_port("fb")
        p1 = make_port("p1")
        router = RoutingE2Port.for_pairs({("A", "B"): p1}, fallback=fallback)
        assert router.route("A", "B") is p1
        assert router.route("A", "C") is fallback
        assert router.route("X", "B") is fallback

    def test_for_states_multiple_states(self):
        fallback = make_port("fb")
        p1 = make_port("p1")
        p2 = make_port("p2")
        router = RoutingE2Port.for_states(
            {"DRAFT": p1, "REVIEW": p2}, fallback=fallback
        )
        assert router.route("DRAFT", "X") is p1
        assert router.route("REVIEW", "X") is p2
        assert router.route("DONE", "X") is fallback

    def test_constructor_returns_routing_e2port(self):
        fallback = make_port("fb")
        router = RoutingE2Port.for_states({}, fallback=fallback)
        assert isinstance(router, RoutingE2Port)


# ── TestRoutingE2PortE0Integration ────────────────────────────────────────────

class TestRoutingE2PortE0Integration:
    def test_e0turn_with_router_runs(self):
        ls = simple_landscape()
        fallback = make_port("fb")
        router = RoutingE2Port(fallback=fallback)
        session = E0Turn(ls, router)
        result = session.run_turn("A")
        assert result is not None

    def test_e0turn_router_reaches_goal(self):
        ls = simple_landscape()
        fallback = make_port("fb", Outcome.SUCCESS)
        router = RoutingE2Port(fallback=fallback)
        session = E0Turn(ls, router)
        turns = list(session.run("A", max_turns=10, goal="C"))
        final_states = [t.state_after for t in turns]
        assert "C" in final_states

    def test_e0turn_router_dispatches_per_turn(self):
        """Different turns use different ports based on state."""
        ls = multi_landscape()
        p_draft  = make_port("p_draft",  Outcome.SUCCESS)
        p_review = make_port("p_review", Outcome.SUCCESS)
        fallback = make_port("fb",       Outcome.SUCCESS)
        router = RoutingE2Port(fallback=fallback)
        router.add(p_draft,  predicate=lambda s, a: s == "DRAFT")
        router.add(p_review, predicate=lambda s, a: s == "REVIEW")
        session = E0Turn(ls, router)
        list(session.run("DRAFT", max_turns=10, goal="PUBLISH"))
        counts = router.status()["dispatch_counts"]
        # DRAFT→REVIEW dispatched to p_draft; REVIEW→APPROVE to p_review
        assert counts.get("p_draft", 0) >= 1
        assert counts.get("p_review", 0) >= 1

    def test_e0turn_router_status_port_id(self):
        ls = simple_landscape()
        fallback = make_port("fb")
        router = RoutingE2Port(fallback=fallback, name="my_router")
        session = E0Turn(ls, router)
        assert session.status()["port_id"] == "my_router"

    def test_e0turn_router_failure_recorded(self):
        ls = simple_landscape()
        fallback = make_port("fb", Outcome.FAILURE)
        router = RoutingE2Port(fallback=fallback)
        session = E0Turn(ls, router)
        session.run_turn("A")
        assert session.history()[0].outcome == Outcome.FAILURE

    def test_e0turn_payload_from_selected_port(self):
        ls = simple_landscape()
        p_special = make_port("special", Outcome.SUCCESS)
        fallback = make_port("fb", Outcome.SUCCESS)
        router = RoutingE2Port(fallback=fallback)
        router.add(p_special, predicate=lambda s, a: s == "A", priority=10)
        session = E0Turn(ls, router)
        result = session.run_turn("A")
        assert result.payload == "special:A→B"

    def test_e0turn_router_for_states_constructor(self):
        """for_states() constructor works with E0Turn end-to-end."""
        ls = multi_landscape()
        p_llm    = make_port("llm", Outcome.SUCCESS)
        fallback = make_port("fb",  Outcome.SUCCESS)
        router   = RoutingE2Port.for_states(
            {"DRAFT": p_llm, "REVIEW": p_llm},
            fallback=fallback,
        )
        session = E0Turn(ls, router)
        turns = list(session.run("DRAFT", max_turns=10, goal="PUBLISH"))
        assert any(t.state_after == "PUBLISH" for t in turns)
