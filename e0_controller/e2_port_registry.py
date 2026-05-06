"""
E₀ E2Port Registry / Routing (C295)
=====================================
A RoutingE2Port is itself an E2Port that dispatches execute() to one of
several registered ports based on routing rules.

Design principle:
    One E0Turn, many ports — each port handles a different subset of
    transitions. The router is transparent to E₀: it is just another E2Port.

    This makes E₀ multi-modal by composition, not by architecture change.
    Same SELECT → EXECUTE → HISTORIZE loop. Only the execution target changes
    per transition.

Architecture:
    RoutingE2Port
        .add(port, predicate)      — register port with routing rule
        .execute(state, action)    — dispatch to first matching port,
                                     or fallback if no rule matches
        .route(state, action)      — inspect: which port would be selected?
        .ports()                   → dict[port_id → E2Port]
        .status()                  → diagnostics snapshot

    Routing rules are evaluated in priority order (highest first, then
    insertion order). The first rule whose predicate returns True wins.
    If no rule matches, the fallback port is used.

Built-in routing helpers (class methods):
    RoutingE2Port.for_states(mapping, fallback)
        — map each state name to a specific port
    RoutingE2Port.for_action_prefixes(mapping, fallback)
        — route by action-label prefix (e.g. "LLM_" → llm_port)
    RoutingE2Port.for_pairs(mapping, fallback)
        — exact (state, action) pairs → port

Usage:
    from e0_controller.e2_port_registry import RoutingE2Port, RoutingRule
    from e0_controller.llm_e2_port import LlmE2Port
    from e0_controller.e2_port import LambdaE2Port
    from e0_controller.e0_turn import E0Turn

    llm_port    = LlmE2Port(task="analyze document", call_fn=my_fn)
    lambda_port = LambdaE2Port(fn=lambda s, a: Outcome.SUCCESS, name="fast")

    router = RoutingE2Port(
        fallback=lambda_port,
        name="my_router",
    )
    router.add(llm_port,    predicate=lambda s, a: a.startswith("ANALYZE"))
    router.add(lambda_port, predicate=lambda s, a: a == "FAST_SKIP", priority=10)

    # Or via class methods:
    router = RoutingE2Port.for_states(
        {"DRAFT": llm_port, "REVIEW": llm_port},
        fallback=lambda_port,
    )

    session = E0Turn(landscape, router)
    for turn in session.run("START", goal="DONE"):
        print(turn)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from .e2_port import E2Port, ExecutionResult
from .primitives import Outcome


# ── RoutingRule ───────────────────────────────────────────────────────────────

@dataclass
class RoutingRule:
    """A single routing rule: predicate → port.

    Args:
        port:       the E2Port to dispatch to when this rule matches
        predicate:  callable(state, action) → bool
        priority:   higher priority rules are evaluated first (default 0)
        label:      optional human-readable label for diagnostics
    """
    port: E2Port
    predicate: Callable[[str, str], bool]
    priority: int = 0
    label: str = ""

    def matches(self, state: str, action: str) -> bool:
        try:
            return bool(self.predicate(state, action))
        except Exception:
            return False


# ── RoutingE2Port ─────────────────────────────────────────────────────────────

class RoutingE2Port(E2Port):
    """E2Port dispatcher — routes execute() to registered sub-ports.

    The router is itself a valid E2Port. E0Turn sees only one port;
    internally, each transition is dispatched to the correct handler.

    Rules are evaluated in descending priority order (highest first),
    then insertion order for equal priorities. First match wins.
    If no rule matches, the fallback port handles the execution.

    Args:
        fallback:   port used when no rule matches (required)
        name:       port_id for this router (default "router")
    """

    def __init__(
        self,
        fallback: E2Port,
        name: str = "router",
    ) -> None:
        self._fallback = fallback
        self._name = name
        self._rules: List[RoutingRule] = []

        # Diagnostics: count how many times each port was selected
        self._dispatch_counts: Dict[str, int] = {}

    # ── Rule management ───────────────────────────────────────────────────────

    def add(
        self,
        port: E2Port,
        predicate: Callable[[str, str], bool],
        priority: int = 0,
        label: str = "",
    ) -> "RoutingE2Port":
        """Register a routing rule. Returns self for chaining.

        Args:
            port:       target E2Port when predicate returns True
            predicate:  callable(state: str, action: str) → bool
            priority:   evaluation order (higher = earlier); default 0
            label:      optional diagnostic label

        Returns:
            self (for fluent chaining: router.add(...).add(...))
        """
        rule_label = label or f"{port.port_id()}@p{priority}"
        self._rules.append(
            RoutingRule(port=port, predicate=predicate,
                        priority=priority, label=rule_label)
        )
        # Keep sorted: highest priority first, insertion-order-stable for ties
        self._rules.sort(key=lambda r: -r.priority)
        return self

    # ── Routing logic ─────────────────────────────────────────────────────────

    def route(self, state: str, action: str) -> E2Port:
        """Return the port that would handle (state, action).

        Evaluates rules in priority order. Returns fallback if none match.
        Does NOT execute — only routing decision.
        """
        for rule in self._rules:
            if rule.matches(state, action):
                return rule.port
        return self._fallback

    # ── E2Port interface ──────────────────────────────────────────────────────

    def port_id(self) -> str:
        return self._name

    def execute(self, state: str, action: str) -> ExecutionResult:
        """Dispatch to the matching port and return its ExecutionResult.

        Contract: NEVER raises. Fallback port handles unmatched cases.
        If the selected port raises (contract violation), returns FAILURE.
        """
        port = self.route(state, action)
        pid = port.port_id()
        self._dispatch_counts[pid] = self._dispatch_counts.get(pid, 0) + 1

        try:
            return port.execute(state, action)
        except Exception as exc:
            return ExecutionResult(
                new_state=state,
                outcome=Outcome.FAILURE,
                payload=None,
                error=f"{pid}: {exc}",
            )

    def can_execute(self, state: str, action: str) -> bool:
        """Delegates to the selected port's can_execute()."""
        return self.route(state, action).can_execute(state, action)

    # ── Inspection ────────────────────────────────────────────────────────────

    def ports(self) -> Dict[str, E2Port]:
        """Return dict of all registered ports (id → port).

        Includes fallback. Rules with the same port share one entry.
        """
        result: Dict[str, E2Port] = {self._fallback.port_id(): self._fallback}
        for rule in self._rules:
            result[rule.port.port_id()] = rule.port
        return result

    def status(self) -> dict:
        """Return diagnostics snapshot."""
        return {
            "port_id": self._name,
            "rule_count": len(self._rules),
            "fallback": self._fallback.port_id(),
            "registered_ports": list(self.ports().keys()),
            "dispatch_counts": dict(self._dispatch_counts),
            "rules": [
                {
                    "label": r.label,
                    "port": r.port.port_id(),
                    "priority": r.priority,
                }
                for r in self._rules
            ],
        }

    # ── Class method constructors ─────────────────────────────────────────────

    @classmethod
    def for_states(
        cls,
        mapping: Dict[str, E2Port],
        fallback: E2Port,
        name: str = "router",
    ) -> "RoutingE2Port":
        """Create router: route by exact source-state match.

        Args:
            mapping:  {state_name: port} — when state==key, use port
            fallback: port for states not in mapping
            name:     router port_id

        Example:
            RoutingE2Port.for_states(
                {"DRAFT": llm_port, "REVIEW": llm_port},
                fallback=fast_port,
            )
        """
        router = cls(fallback=fallback, name=name)
        for state_name, port in mapping.items():
            router.add(
                port=port,
                predicate=lambda s, a, _s=state_name: s == _s,
                label=f"state={state_name}→{port.port_id()}",
            )
        return router

    @classmethod
    def for_actions(
        cls,
        mapping: Dict[str, E2Port],
        fallback: E2Port,
        name: str = "router",
    ) -> "RoutingE2Port":
        """Create router: route by exact action/target-state match.

        Args:
            mapping:  {action_name: port} — when action==key, use port
            fallback: port for actions not in mapping
            name:     router port_id

        Example:
            RoutingE2Port.for_actions(
                {"DELIVERED": review_port, "REJECTED": audit_port},
                fallback=default_port,
            )
        """
        router = cls(fallback=fallback, name=name)
        for action_name, port in mapping.items():
            router.add(
                port=port,
                predicate=lambda s, a, _a=action_name: a == _a,
                label=f"action={action_name}→{port.port_id()}",
            )
        return router

    @classmethod
    def for_action_prefixes(
        cls,
        mapping: Dict[str, E2Port],
        fallback: E2Port,
        name: str = "router",
    ) -> "RoutingE2Port":
        """Create router: route by action-label prefix.

        Args:
            mapping:  {prefix: port} — when action.startswith(prefix), use port
            fallback: port when no prefix matches
            name:     router port_id

        Example:
            RoutingE2Port.for_action_prefixes(
                {"LLM_": llm_port, "DB_": db_port},
                fallback=lambda_port,
            )
        """
        router = cls(fallback=fallback, name=name)
        for prefix, port in mapping.items():
            router.add(
                port=port,
                predicate=lambda s, a, _p=prefix: a.startswith(_p),
                label=f"prefix={prefix}→{port.port_id()}",
            )
        return router

    @classmethod
    def for_pairs(
        cls,
        mapping: Dict[Tuple[str, str], E2Port],
        fallback: E2Port,
        name: str = "router",
    ) -> "RoutingE2Port":
        """Create router: route by exact (state, action) pair.

        Args:
            mapping:  {(state, action): port}
            fallback: port for unmatched pairs
            name:     router port_id

        Example:
            RoutingE2Port.for_pairs(
                {("INBOX", "PROCESSED"): fast_port,
                 ("DRAFT", "REVIEW"): llm_port},
                fallback=default_port,
            )
        """
        router = cls(fallback=fallback, name=name)
        for (src, tgt), port in mapping.items():
            router.add(
                port=port,
                predicate=lambda s, a, _s=src, _t=tgt: s == _s and a == _t,
                label=f"pair=({src},{tgt})→{port.port_id()}",
            )
        return router
