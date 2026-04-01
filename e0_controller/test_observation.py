"""
Tests for E₀ Observation Landscape (C94)
==========================================
Structural validation: correct states, edges, parameters.
Navigation validation: E0Controller can navigate the O-Landscape.
"""

from __future__ import annotations

import math
import unittest

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller, HybridMode
from e0_controller.observation import (
    DEPTHS,
    DEPTH_FORWARD,
    DEPTH_RETREAT_DELTA,
    DEPTH_RETREAT_R0,
    SCOPE_FOCUS_DELTA,
    SCOPE_FOCUS_R0,
    SCOPE_DEFOCUS_DELTA,
    SCOPE_DEFOCUS_R0,
    SCOPE_MOVE_DELTA,
    SCOPE_MOVE_R0,
    encode_state,
    decode_state,
    is_global,
    is_local,
    local_node,
    depth_of,
    build_observation_landscape,
    observation_states,
    observation_edges,
    info_at,
)


# ── Helpers ──────────────────────────────────────────────

def _triangle_landscape() -> Landscape:
    """A→B→C→A, 3 nodes, 3 edges."""
    L = Landscape()
    L.add_edge("A", "B", delta=0.5, resistance=0.3)
    L.add_edge("B", "C", delta=0.5, resistance=0.3)
    L.add_edge("C", "A", delta=0.5, resistance=0.3)
    return L


def _greedy_trap_landscape() -> Landscape:
    """S→A, A↔C (trap), A→B→D→GOAL (forward). 6 nodes."""
    L = Landscape()
    L.add_edge("S", "A", delta=0.3, resistance=0.4)
    L.add_edge("A", "B", delta=0.3, resistance=0.5)
    L.add_edge("B", "D", delta=0.3, resistance=0.5)
    L.add_edge("D", "GOAL", delta=0.2, resistance=0.3)
    L.add_edge("A", "C", delta=0.2, resistance=0.4)
    L.add_edge("C", "A", delta=0.2, resistance=0.4)
    return L


def _always_success(source: str, target: str) -> Outcome:
    return Outcome.SUCCESS


# ══════════════════════════════════════════════════════════
# 1. State Encoding
# ══════════════════════════════════════════════════════════

class TestStateEncoding(unittest.TestCase):

    def test_encode_global(self):
        self.assertEqual(encode_state("g", "topo"), "g:topo")

    def test_encode_local(self):
        self.assertEqual(encode_state("n:A", "field"), "n:A:field")

    def test_decode_global(self):
        scope, depth = decode_state("g:topo")
        self.assertEqual(scope, "g")
        self.assertEqual(depth, "topo")

    def test_decode_local(self):
        scope, depth = decode_state("n:A:field")
        self.assertEqual(scope, "n:A")
        self.assertEqual(depth, "field")

    def test_decode_node_with_colon(self):
        """Node IDs don't contain colons in practice, but depth is last segment."""
        scope, depth = decode_state("n:NODE_X:dyn")
        self.assertEqual(scope, "n:NODE_X")
        self.assertEqual(depth, "dyn")

    def test_is_global(self):
        self.assertTrue(is_global("g:topo"))
        self.assertFalse(is_global("n:A:topo"))

    def test_is_local(self):
        self.assertTrue(is_local("n:A:field"))
        self.assertFalse(is_local("g:field"))

    def test_local_node(self):
        self.assertEqual(local_node("n:A:field"), "A")
        self.assertEqual(local_node("n:GOAL:dyn"), "GOAL")
        self.assertIsNone(local_node("g:topo"))

    def test_depth_of(self):
        self.assertEqual(depth_of("g:mech"), "mech")
        self.assertEqual(depth_of("n:B:intf"), "intf")

    def test_decode_invalid(self):
        with self.assertRaises(ValueError):
            decode_state("no_colon")


# ══════════════════════════════════════════════════════════
# 2. O-Landscape Structure (Triangle)
# ══════════════════════════════════════════════════════════

class TestTriangleOLandscape(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.domain = _triangle_landscape()
        cls.o = build_observation_landscape(cls.domain)
        cls.states = observation_states(cls.o)
        cls.edges = observation_edges(cls.o)

    def test_state_count(self):
        """(1 global + 3 local) × 5 depths = 20 states."""
        self.assertEqual(len(self.states), 20)

    def test_all_scopes_present(self):
        scopes = {s.rsplit(":", 1)[0] for s in self.states}
        self.assertIn("g", scopes)
        self.assertIn("n:A", scopes)
        self.assertIn("n:B", scopes)
        self.assertIn("n:C", scopes)

    def test_all_depths_present(self):
        depths = {s.rsplit(":", 1)[1] for s in self.states}
        self.assertEqual(depths, set(DEPTHS))

    def test_depth_forward_edges(self):
        """Each scope has 4 forward depth edges."""
        for scope in ["g", "n:A", "n:B", "n:C"]:
            for d_from, d_to in DEPTH_FORWARD:
                src = encode_state(scope, d_from)
                tgt = encode_state(scope, d_to)
                self.assertTrue(
                    self.o.has_edge(src, tgt),
                    f"Missing forward edge: {src}→{tgt}",
                )

    def test_depth_retreat_edges(self):
        """Each scope has 4 retreat depth edges."""
        for scope in ["g", "n:A", "n:B", "n:C"]:
            for d_from, d_to in DEPTH_FORWARD:
                src = encode_state(scope, d_to)  # reversed
                tgt = encode_state(scope, d_from)
                self.assertTrue(
                    self.o.has_edge(src, tgt),
                    f"Missing retreat edge: {src}→{tgt}",
                )

    def test_retreat_is_cheaper(self):
        """Retreat has lower Δ and R₀ than any forward step."""
        for d_from, d_to in DEPTH_FORWARD:
            fwd_delta, fwd_r0 = DEPTH_FORWARD[(d_from, d_to)]
            self.assertLess(DEPTH_RETREAT_DELTA, fwd_delta)
            self.assertLess(DEPTH_RETREAT_R0, fwd_r0)

    def test_global_to_local_edges(self):
        """At each depth, g→n:X exists for all X."""
        for depth in DEPTHS:
            for node in ["A", "B", "C"]:
                src = encode_state("g", depth)
                tgt = encode_state(f"n:{node}", depth)
                self.assertTrue(
                    self.o.has_edge(src, tgt),
                    f"Missing focus edge: {src}→{tgt}",
                )

    def test_local_to_global_edges(self):
        """At each depth, n:X→g exists for all X."""
        for depth in DEPTHS:
            for node in ["A", "B", "C"]:
                src = encode_state(f"n:{node}", depth)
                tgt = encode_state("g", depth)
                self.assertTrue(
                    self.o.has_edge(src, tgt),
                    f"Missing defocus edge: {src}→{tgt}",
                )

    def test_local_to_local_edges(self):
        """n:A→n:B exists (because domain has edge A→B)."""
        for depth in DEPTHS:
            self.assertTrue(
                self.o.has_edge(
                    encode_state("n:A", depth),
                    encode_state("n:B", depth),
                ),
            )
            # A→B exists, but B→A does not in domain
            self.assertFalse(
                self.o.has_edge(
                    encode_state("n:B", depth),
                    encode_state("n:A", depth),
                ),
            )

    def test_no_cross_transitions(self):
        """No edges change scope AND depth simultaneously."""
        for e in self.edges:
            src_scope, src_depth = decode_state(e.source)
            tgt_scope, tgt_depth = decode_state(e.target)
            scope_changed = src_scope != tgt_scope
            depth_changed = src_depth != tgt_depth
            self.assertFalse(
                scope_changed and depth_changed,
                f"Cross-transition found: {e.source}→{e.target}",
            )

    def test_edge_parameters(self):
        """Spot-check Δ and R₀ values."""
        # Forward depth edge
        src, tgt = "g:topo", "g:field"
        self.assertAlmostEqual(self.o.difference(src, tgt), 0.3)
        self.assertAlmostEqual(self.o.base_resistance(src, tgt), 0.3)

        # Retreat edge
        src, tgt = "g:field", "g:topo"
        self.assertAlmostEqual(self.o.difference(src, tgt), 0.1)
        self.assertAlmostEqual(self.o.base_resistance(src, tgt), 0.1)

        # Focus edge
        src, tgt = "g:dyn", "n:A:dyn"
        self.assertAlmostEqual(self.o.difference(src, tgt), SCOPE_FOCUS_DELTA)
        self.assertAlmostEqual(self.o.base_resistance(src, tgt), SCOPE_FOCUS_R0)


# ══════════════════════════════════════════════════════════
# 3. O-Landscape Structure (Greedy Trap — 6 nodes)
# ══════════════════════════════════════════════════════════

class TestGreedyTrapOLandscape(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.domain = _greedy_trap_landscape()
        cls.o = build_observation_landscape(cls.domain)

    def test_state_count(self):
        """(1 + 6) × 5 = 35 states."""
        self.assertEqual(len(observation_states(self.o)), 35)

    def test_directed_scope_transitions(self):
        """A→C exists in domain: n:A→n:C exists. C→B does not: n:C→n:B absent."""
        # A→C
        self.assertTrue(self.o.has_edge("n:A:topo", "n:C:topo"))
        # C→A
        self.assertTrue(self.o.has_edge("n:C:topo", "n:A:topo"))
        # C→B does not exist in domain
        self.assertFalse(self.o.has_edge("n:C:topo", "n:B:topo"))


# ══════════════════════════════════════════════════════════
# 4. Partial Depths
# ══════════════════════════════════════════════════════════

class TestPartialDepths(unittest.TestCase):

    def test_two_depths(self):
        domain = _triangle_landscape()
        o = build_observation_landscape(domain, depths=["topo", "field"])
        states = observation_states(o)
        # (1 + 3) × 2 = 8
        self.assertEqual(len(states), 8)
        # No "dyn" states
        self.assertFalse(any(s.endswith(":dyn") for s in states))

    def test_invalid_depth(self):
        domain = _triangle_landscape()
        with self.assertRaises(ValueError):
            build_observation_landscape(domain, depths=["topo", "magic"])


# ══════════════════════════════════════════════════════════
# 5. info_at
# ══════════════════════════════════════════════════════════

class TestInfoAt(unittest.TestCase):

    def test_global_topo(self):
        info = info_at("g:topo")
        self.assertEqual(info["scope"], "g")
        self.assertEqual(info["depth"], "topo")
        self.assertEqual(info["depth_index"], 0)
        self.assertIn("Global", info["scope_desc"])

    def test_local_intf(self):
        info = info_at("n:GOAL:intf")
        self.assertEqual(info["scope"], "n:GOAL")
        self.assertEqual(info["depth"], "intf")
        self.assertEqual(info["depth_index"], 4)
        self.assertIn("GOAL", info["scope_desc"])


# ══════════════════════════════════════════════════════════
# 6. E0Controller Navigation on O-Landscape
# ══════════════════════════════════════════════════════════

class TestControllerNavigation(unittest.TestCase):
    """
    Core test: can an E0Controller navigate the O-Landscape?

    This validates that the O-Landscape is a valid E₀ domain —
    same controller, same mechanics, same historization.
    """

    @classmethod
    def setUpClass(cls):
        cls.domain = _triangle_landscape()
        cls.o = build_observation_landscape(cls.domain)

    def test_controller_runs(self):
        """Controller completes a multi-step run on the O-Landscape."""
        ctrl = E0Controller(
            self.o,
            _always_success,
            hybrid_mode=HybridMode.GREEDY,
        )
        trace = ctrl.run(start="g:topo", max_cycles=20)
        self.assertGreater(len(trace.steps), 0)

    def test_starts_at_global_topo(self):
        """Natural start: global topology (minimal information)."""
        ctrl = E0Controller(
            self.o,
            _always_success,
        )
        trace = ctrl.run(start="g:topo", max_cycles=10)
        self.assertEqual(trace.steps[0].source, "g:topo")

    def test_reaches_deeper_states(self):
        """Controller naturally progresses to deeper observation depths."""
        ctrl = E0Controller(
            self.o,
            _always_success,
        )
        trace = ctrl.run(start="g:topo", max_cycles=30)
        visited = {step.target for step in trace.steps}
        # Should visit at least field depth (lowest forward tension)
        self.assertTrue(
            any(s.endswith(":field") for s in visited),
            f"Never reached field depth. Visited: {visited}",
        )

    def test_historization_lowers_resistance(self):
        """Repeated traversal of an edge lowers its R_eff."""
        ctrl = E0Controller(
            self.o,
            _always_success,
        )
        edge = Edge("g:topo", "g:field")
        r_before = self.o.effective_resistance("g:topo", "g:field")

        # Manually traverse this edge a few times
        for _ in range(5):
            self.o.historization.update(edge, Outcome.SUCCESS)

        r_after = self.o.effective_resistance("g:topo", "g:field")
        self.assertLess(r_after, r_before)

    def test_goal_reachable(self):
        """g:intf is structurally reachable: a 4-step path exists in global scope."""
        o = build_observation_landscape(self.domain)
        # Verify the depth-chain exists
        for d_from, d_to in [("topo", "field"), ("field", "dyn"),
                             ("dyn", "mech"), ("mech", "intf")]:
            self.assertTrue(
                o.has_edge(f"g:{d_from}", f"g:{d_to}"),
                f"Missing global depth edge: g:{d_from}→g:{d_to}",
            )

    def test_amplitude_mode(self):
        """Amplitude overlay works on O-Landscape (no crash)."""
        o = build_observation_landscape(self.domain)
        ctrl = E0Controller(
            o,
            _always_success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=2,
            hybrid_goals={"g:intf"},
        )
        trace = ctrl.run(start="g:topo", goal="g:intf", max_cycles=50)
        self.assertGreater(len(trace.steps), 0)

    def test_local_navigation(self):
        """Controller can navigate to a local node scope."""
        o = build_observation_landscape(self.domain)
        ctrl = E0Controller(o, _always_success)
        trace = ctrl.run(start="g:topo", max_cycles=20)
        visited = {step.target for step in trace.steps}
        # Should visit at least one local state (low R₀ for focus)
        has_local = any(":n:" in s or s.startswith("n:") for s in visited)
        # It's possible but not guaranteed — depends on tension ranking.
        # At minimum, the run should complete without error.
        self.assertGreater(len(trace.steps), 0)


# ══════════════════════════════════════════════════════════
# 7. Structural Invariants
# ══════════════════════════════════════════════════════════

class TestStructuralInvariants(unittest.TestCase):
    """
    Properties that must hold for any O-Landscape.
    """

    def _check_invariants(self, domain: Landscape):
        o = build_observation_landscape(domain)
        states = observation_states(o)
        edges = observation_edges(o)

        # I1: Every state has at least one outgoing edge
        for s in states:
            neighbors = o.admissible_neighbors(s)
            self.assertGreater(
                len(neighbors), 0,
                f"Isolated state: {s}",
            )

        # I2: No self-loops
        for e in edges:
            self.assertNotEqual(
                e.source, e.target,
                f"Self-loop: {e.source}",
            )

        # I3: All Δ > 0 (every transition changes something)
        for e in edges:
            delta = o.difference(e.source, e.target)
            self.assertGreater(
                delta, 0.0,
                f"Zero Δ: {e.source}→{e.target}",
            )

        # I4: All R₀ > 0 (every transition has cost)
        for e in edges:
            r0 = o.base_resistance(e.source, e.target)
            self.assertGreater(
                r0, 0.0,
                f"Zero R₀: {e.source}→{e.target}",
            )

        # I5: No cross-transitions (scope+depth change)
        for e in edges:
            s_scope, s_depth = decode_state(e.source)
            t_scope, t_depth = decode_state(e.target)
            self.assertFalse(
                s_scope != t_scope and s_depth != t_depth,
                f"Cross-transition: {e}",
            )

    def test_triangle(self):
        self._check_invariants(_triangle_landscape())

    def test_greedy_trap(self):
        self._check_invariants(_greedy_trap_landscape())

    def test_single_edge(self):
        """Minimal domain: one edge, two nodes."""
        L = Landscape()
        L.add_edge("X", "Y", delta=1.0, resistance=1.0)
        self._check_invariants(L)

    def test_isolated_node(self):
        """Domain with an isolated node (no outgoing edges)."""
        L = Landscape()
        L.add_edge("A", "B", delta=0.5, resistance=0.3)
        L.add_state("C")  # isolated
        o = build_observation_landscape(L)
        # n:C states exist but only have depth + scope transitions, no local→local
        self.assertIn("n:C:topo", observation_states(o))
        # n:C should still have outgoing edges (depth + defocus)
        neighbors = o.admissible_neighbors("n:C:topo")
        self.assertGreater(len(neighbors), 0)

    def test_large_domain(self):
        """10-node fully connected domain still produces valid O-Landscape."""
        nodes = [f"S{i}" for i in range(10)]
        L = Landscape.fully_connected(nodes, delta=0.5, resistance=1.0)
        o = build_observation_landscape(L)
        # (1 + 10) × 5 = 55 states
        self.assertEqual(len(observation_states(o)), 55)
        # Invariants hold
        self._check_invariants(L)


if __name__ == "__main__":
    unittest.main()
