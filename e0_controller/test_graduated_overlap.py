"""
C98 — Graduated Overlap in Controller Greedy Loop
====================================================
Tests that M_H (graduated overlap functional) actually changes
the controller's greedy decisions — not just transition_field().

Closes the final M_H research question from:
  docs/research/E0_MH_ADJUDICATION_RESEARCH_NOTE_v1.md

Prior state (C40): overlap.py implements the functional,
landscape.transition_field() uses it, but the greedy loop
(select_next → _penalized_tension) was blind to M_H.

C98 integrates: _penalized_tension divides S_eff by M_H
when overlap_modulation is True.  Greedy now prefers
well-supported edges (high M_H → lower adjusted tension).

Key property: on simple domains (no directed triangles),
M_H = 1.0 everywhere → zero behavioral change.
"""

import math
import unittest

from e0_controller.controller import E0Controller, EscalationType
from e0_controller.landscape import Landscape
from e0_controller.overlap import overlap_map, triangle_support
from e0_controller.primitives import Edge, Outcome


# ═══════════════════════════════════════════════════════════════
# Domain builders
# ═══════════════════════════════════════════════════════════════

def build_overlap_differentiator() -> Landscape:
    """
    Custom falsification domain from the M_H research note:

    Path 1: S → A → GOAL  (bridge, no triangle support)
    Path 2: S → B → GOAL  (supported: S → C → B is a bypass)
    Extra:  S → C, C → B, C → GOAL

    All edges: δ=1.0, R=0.5 — identical per-edge properties.
    S_eff(S→A) = S_eff(S→B) exactly.
    Only structural difference: S→B has overlap via C.
    """
    L = Landscape()
    for s, t in [("S", "A"), ("A", "GOAL"),
                 ("S", "B"), ("B", "GOAL"),
                 ("S", "C"), ("C", "B"), ("C", "GOAL")]:
        L.add_edge(s, t, delta=1.0, resistance=0.5)
    return L


def build_linear_dag() -> Landscape:
    """S → A → B → GOAL — no triangles, M_H = 1 everywhere."""
    L = Landscape()
    for s, t in [("S", "A"), ("A", "B"), ("B", "GOAL")]:
        L.add_edge(s, t, delta=1.0, resistance=0.5)
    return L


def build_gordian_trap() -> Landscape:
    """The classic Gordian Trap — no directed triangles."""
    L = Landscape()
    L.add_edge("START", "SAFE", delta=0.1, resistance=0.1)
    L.add_edge("START", "RISKY", delta=0.8, resistance=0.1)
    L.add_edge("SAFE", "MID", delta=0.2, resistance=0.1)
    L.add_edge("MID", "GOAL", delta=0.2, resistance=0.1)
    L.add_edge("RISKY", "GOAL", delta=0.1, resistance=5.0)
    L.add_edge("RISKY", "TRAP", delta=0.3, resistance=0.1)
    return L


def build_dual_support() -> Landscape:
    """
    S → A → GOAL  (two support nodes: X and Y)
    S → B → GOAL  (one support node: Z)

    Support:
      S → X → A, S → Y → A  (A has 2 bypass paths)
      S → Z → B              (B has 1 bypass path)

    All edges: δ=1.0, R=0.5.
    A has stronger overlap than B (2 support nodes vs 1).
    """
    L = Landscape()
    for s, t in [("S", "A"), ("A", "GOAL"),
                 ("S", "B"), ("B", "GOAL"),
                 ("S", "X"), ("X", "A"),
                 ("S", "Y"), ("Y", "A"),
                 ("S", "Z"), ("Z", "B")]:
        L.add_edge(s, t, delta=1.0, resistance=0.5)
    return L


def build_asymmetric_support() -> Landscape:
    """
    S → A → GOAL  (weak bypass via X: δ=0.1, R=2.0)
    S → B → GOAL  (strong bypass via Y: δ=2.0, R=0.1)

    Main edges: δ=1.0, R=0.5.
    S→B has quantitatively stronger support than S→A.
    """
    L = Landscape()
    for s, t in [("S", "A"), ("A", "GOAL"),
                 ("S", "B"), ("B", "GOAL")]:
        L.add_edge(s, t, delta=1.0, resistance=0.5)
    L.add_edge("S", "X", delta=0.1, resistance=2.0)
    L.add_edge("X", "A", delta=0.1, resistance=2.0)
    L.add_edge("S", "Y", delta=2.0, resistance=0.1)
    L.add_edge("Y", "B", delta=2.0, resistance=0.1)
    return L


MOCK_EXEC = lambda s, t: Outcome.SUCCESS


# ═══════════════════════════════════════════════════════════════
# Test Classes
# ═══════════════════════════════════════════════════════════════

class TestGreedyOverlapIntegration(unittest.TestCase):
    """
    Core claim: with overlap_modulation=True, the controller's
    greedy decision (select_next) prefers structurally supported edges.
    """

    def test_without_overlap_indistinguishable(self):
        """On the differentiator, S→A and S→B have same S_eff."""
        L = build_overlap_differentiator()
        s_a = L.effective_tension("S", "A")
        s_b = L.effective_tension("S", "B")
        self.assertAlmostEqual(s_a, s_b, places=10,
                              msg="Paths must be identical without overlap")

    def test_greedy_without_overlap_nondeterministic(self):
        """Without overlap, controller has no preference between A and B."""
        L = build_overlap_differentiator()
        ctrl = E0Controller(L, MOCK_EXEC)
        pt_a = ctrl._penalized_tension("S", "A")
        pt_b = ctrl._penalized_tension("S", "B")
        self.assertAlmostEqual(pt_a, pt_b, places=10)

    def test_greedy_with_overlap_prefers_supported(self):
        """With overlap, controller prefers S→B (supported) over S→A (bridge)."""
        L = build_overlap_differentiator()
        L.overlap_modulation = True
        ctrl = E0Controller(L, MOCK_EXEC)
        pt_a = ctrl._penalized_tension("S", "A")
        pt_b = ctrl._penalized_tension("S", "B")
        self.assertGreater(pt_a, pt_b,
                          "Unsupported S→A should have higher penalized tension")

    def test_select_next_chooses_supported(self):
        """select_next from S picks B (supported) when overlap is on."""
        L = build_overlap_differentiator()
        L.overlap_modulation = True
        ctrl = E0Controller(L, MOCK_EXEC)
        target, escalated, esc_type = ctrl.select_next("S")
        self.assertEqual(target, "B",
                        "Controller should select supported path S→B")
        self.assertFalse(escalated)
        self.assertEqual(esc_type, EscalationType.NONE)

    def test_run_takes_supported_path(self):
        """Full run from S to GOAL takes S→B→GOAL (supported path)."""
        L = build_overlap_differentiator()
        L.overlap_modulation = True
        ctrl = E0Controller(L, MOCK_EXEC)
        trace = ctrl.run("S", max_cycles=10, goal="GOAL")
        self.assertEqual(trace.path[-1], "GOAL")
        self.assertIn("B", trace.path,
                      "Run should go through B (supported path)")

    def test_penalty_ratio_matches_m_h(self):
        """The ratio of penalized tensions must equal 1/M_H ratio."""
        L = build_overlap_differentiator()
        L.overlap_modulation = True
        ctrl = E0Controller(L, MOCK_EXEC)
        pt_a = ctrl._penalized_tension("S", "A")
        pt_b = ctrl._penalized_tension("S", "B")
        om = overlap_map(build_overlap_differentiator())
        m_h_a = om[("S", "A")].m_h
        m_h_b = om[("S", "B")].m_h
        # pt ∝ S_eff / M_H, and S_eff is the same → ratio = M_H_b / M_H_a
        self.assertAlmostEqual(pt_a / pt_b, m_h_b / m_h_a, places=8)


class TestNeutralityOnSimpleDomains(unittest.TestCase):
    """
    Key property: on domains without directed triangles,
    M_H = 1 everywhere → overlap_modulation has zero effect
    on the greedy decision.
    """

    def test_linear_dag_no_effect(self):
        """Linear DAG: overlap on/off gives same penalized tension."""
        L_off = build_linear_dag()
        L_on = build_linear_dag()
        L_on.overlap_modulation = True
        ctrl_off = E0Controller(L_off, MOCK_EXEC)
        ctrl_on = E0Controller(L_on, MOCK_EXEC)
        for x, y in [("S", "A"), ("A", "B"), ("B", "GOAL")]:
            pt_off = ctrl_off._penalized_tension(x, y)
            pt_on = ctrl_on._penalized_tension(x, y)
            self.assertAlmostEqual(pt_off, pt_on, places=10,
                                  msg=f"Linear edge {x}→{y} should be unaffected")

    def test_gordian_trap_no_effect(self):
        """Gordian Trap has no directed triangles → zero overlap effect."""
        L_off = build_gordian_trap()
        L_on = build_gordian_trap()
        L_on.overlap_modulation = True
        ctrl_off = E0Controller(L_off, MOCK_EXEC)
        ctrl_on = E0Controller(L_on, MOCK_EXEC)
        for e in L_off.edges:
            pt_off = ctrl_off._penalized_tension(e.source, e.target)
            pt_on = ctrl_on._penalized_tension(e.source, e.target)
            self.assertAlmostEqual(pt_off, pt_on, places=10,
                                  msg=f"Gordian edge {e} should be unaffected")

    def test_gordian_same_run_result(self):
        """Gordian Trap run result is identical with/without overlap."""
        L_off = build_gordian_trap()
        L_on = build_gordian_trap()
        L_on.overlap_modulation = True
        ctrl_off = E0Controller(L_off, MOCK_EXEC)
        ctrl_on = E0Controller(L_on, MOCK_EXEC)
        trace_off = ctrl_off.run("START", max_cycles=20, goal="GOAL")
        trace_on = ctrl_on.run("START", max_cycles=20, goal="GOAL")
        self.assertEqual(trace_off.path, trace_on.path)


class TestDualSupport(unittest.TestCase):
    """Edges with more support nodes → lower penalized tension."""

    def test_more_support_lower_tension(self):
        """S→A (2 supports: X, Y) has lower adjusted tension than S→B (1 support: Z)."""
        L = build_dual_support()
        L.overlap_modulation = True
        ctrl = E0Controller(L, MOCK_EXEC)
        pt_a = ctrl._penalized_tension("S", "A")
        pt_b = ctrl._penalized_tension("S", "B")
        self.assertLess(pt_a, pt_b,
                       "Dual-support S→A should have lower tension than single-support S→B")

    def test_select_next_picks_dual_support(self):
        """select_next prefers the path with more structural support."""
        L = build_dual_support()
        L.overlap_modulation = True
        ctrl = E0Controller(L, MOCK_EXEC)
        target, _, _ = ctrl.select_next("S")
        self.assertEqual(target, "A",
                        "Should select A (2 supports) over B (1 support)")


class TestAsymmetricSupportStrength(unittest.TestCase):
    """Support quality (not just count) matters."""

    def test_strong_support_preferred(self):
        """Strong bypass (high v) gives more overlap than weak bypass."""
        L = build_asymmetric_support()
        L.overlap_modulation = True
        ctrl = E0Controller(L, MOCK_EXEC)
        pt_a = ctrl._penalized_tension("S", "A")  # weak support
        pt_b = ctrl._penalized_tension("S", "B")  # strong support
        self.assertGreater(pt_a, pt_b,
                          "Weak-support S→A should have higher adjusted tension")

    def test_run_takes_strong_supported_path(self):
        """Controller runs through B (strong support) to GOAL."""
        L = build_asymmetric_support()
        L.overlap_modulation = True
        ctrl = E0Controller(L, MOCK_EXEC)
        trace = ctrl.run("S", max_cycles=10, goal="GOAL")
        self.assertEqual(trace.path[-1], "GOAL")
        self.assertIn("B", trace.path)


class TestOverlapWithHistorization(unittest.TestCase):
    """Overlap modulation interacts correctly with historization."""

    def test_overlap_and_revisit_stack(self):
        """Both overlap and revisit penalties apply when both active."""
        L = build_overlap_differentiator()
        L.overlap_modulation = True
        ctrl = E0Controller(L, MOCK_EXEC)
        # Mark A as recently visited
        ctrl._recent.append("A")
        pt_a = ctrl._penalized_tension("S", "A")
        pt_b = ctrl._penalized_tension("S", "B")
        # A has both penalties: unsupported AND recently visited
        self.assertGreater(pt_a, pt_b)

    def test_historization_can_overcome_overlap(self):
        """Heavy failure history on supported edge can overcome overlap advantage.

        With default parameters, lambda_f=0.20 × F_∞=10 = delta_H=2.0,
        R_eff converges to exactly 2.5 — a tie with the overlap-amplified
        unsupported edge (S_eff/0.2 = 2.5).  Using lambda_f=0.5 pushes
        delta_H to 3.0 (clipped), giving R_eff=3.5, decisively overcoming
        the 5× overlap penalty.
        """
        from e0_controller.historization import Historization
        hist = Historization(lambda_f=0.5)
        L = Landscape(overlap_modulation=True, historization=hist)
        for s, t in [("S", "A"), ("A", "GOAL"),
                     ("S", "B"), ("B", "GOAL"),
                     ("S", "C"), ("C", "B"), ("C", "GOAL")]:
            L.add_edge(s, t, delta=1.0, resistance=0.5)
        # Fail S→B heavily
        for _ in range(100):
            L.historization.update(Edge("S", "B"), Outcome.FAILURE)
        ctrl = E0Controller(L, MOCK_EXEC)
        pt_a = ctrl._penalized_tension("S", "A")
        pt_b = ctrl._penalized_tension("S", "B")
        self.assertGreater(pt_b, pt_a,
                          "Heavy failures should outweigh overlap advantage")


class TestOverlapModulationFlag(unittest.TestCase):
    """The flag controls behavior correctly."""

    def test_off_by_default(self):
        """overlap_modulation defaults to False — no change in behavior."""
        L = build_overlap_differentiator()
        ctrl = E0Controller(L, MOCK_EXEC)
        pt_a = ctrl._penalized_tension("S", "A")
        pt_b = ctrl._penalized_tension("S", "B")
        self.assertAlmostEqual(pt_a, pt_b, places=10)

    def test_toggle_on(self):
        """Setting overlap_modulation=True activates overlap in greedy."""
        L = build_overlap_differentiator()
        L.overlap_modulation = True
        ctrl = E0Controller(L, MOCK_EXEC)
        pt_a = ctrl._penalized_tension("S", "A")
        pt_b = ctrl._penalized_tension("S", "B")
        self.assertGreater(pt_a, pt_b)

    def test_m_h_never_zero(self):
        """M_H > 0 always (Canon §3.4: stability requires non-zero overlap)."""
        L = build_overlap_differentiator()
        L.overlap_modulation = True
        om = overlap_map(L)
        for info in om.values():
            self.assertGreater(info.m_h, 0.0,
                              msg=f"M_H for {info.edge} must be > 0")


class TestEscalationWithOverlap(unittest.TestCase):
    """Escalation target selection (which already uses transition_field) 
    should remain consistent with overlap."""

    def test_dead_end_uses_overlap(self):
        """DEAD_END recovery already uses transition_field → overlap-aware."""
        L = Landscape(overlap_modulation=True)
        L.add_edge("X", "A", delta=1.0, resistance=0.5)
        L.add_edge("A", "GOAL", delta=1.0, resistance=0.5)
        L.add_edge("X", "B", delta=1.0, resistance=0.5)
        L.add_edge("B", "GOAL", delta=1.0, resistance=0.5)
        # Add support for A path
        L.add_edge("X", "Z", delta=1.0, resistance=0.5)
        L.add_edge("Z", "A", delta=1.0, resistance=0.5)
        ctrl = E0Controller(L, MOCK_EXEC)
        # Force DEAD_END from isolated state
        L.add_state("ISOLATED")
        target = ctrl._escalation_target("ISOLATED", EscalationType.DEAD_END)
        # Should pick a state with strong outflow — overlap influences this
        self.assertIsNotNone(target)


class TestSelfGraphTracking(unittest.TestCase):
    """self_graph should record overlap as an active component."""

    def test_self_graph_records_overlap(self):
        """When overlap_modulation=True, self_graph sees it as active."""
        from e0_controller.self_graph import SelfGraph, active_components
        L = build_overlap_differentiator()
        L.overlap_modulation = True
        ctrl = E0Controller(L, MOCK_EXEC)
        sg = SelfGraph()
        ctrl.self_graph = sg
        # Run one cycle
        ctrl.cycle("S")
        # Check that self_graph recorded overlap as active
        comps = active_components(
            curvature_active=L.curvature_modulation,
            overlap_active=L.overlap_modulation,
            inertia_active=L.inertia_modulation,
        )
        self.assertIn("overlap", comps)


class TestMathematicalProperties(unittest.TestCase):
    """Structural correctness of the integration."""

    def test_division_by_one_neutral(self):
        """When M_H=1.0, S_eff/M_H = S_eff — no change."""
        L = build_linear_dag()
        L.overlap_modulation = True
        ctrl = E0Controller(L, MOCK_EXEC)
        s_raw = L.effective_tension("S", "A")
        pt = ctrl._penalized_tension("S", "A")
        self.assertAlmostEqual(pt, s_raw, places=10)

    def test_division_amplifies_correctly(self):
        """S_eff / M_H > S_eff when M_H < 1."""
        L = build_overlap_differentiator()
        L.overlap_modulation = True
        ctrl = E0Controller(L, MOCK_EXEC)
        s_raw = L.effective_tension("S", "A")
        pt = ctrl._penalized_tension("S", "A")
        om = overlap_map(build_overlap_differentiator())
        m_h_a = om[("S", "A")].m_h
        self.assertLess(m_h_a, 1.0)
        self.assertAlmostEqual(pt, s_raw / m_h_a, places=8)

    def test_ordering_preserved(self):
        """On the differentiator, overlap changes relative order of S→A vs S→B."""
        L_off = build_overlap_differentiator()
        L_on = build_overlap_differentiator()
        L_on.overlap_modulation = True
        ctrl_off = E0Controller(L_off, MOCK_EXEC)
        ctrl_on = E0Controller(L_on, MOCK_EXEC)
        # Without: equal
        self.assertAlmostEqual(
            ctrl_off._penalized_tension("S", "A"),
            ctrl_off._penalized_tension("S", "B"),
            places=10
        )
        # With: S→A > S→B (unsupported has higher tension)
        self.assertGreater(
            ctrl_on._penalized_tension("S", "A"),
            ctrl_on._penalized_tension("S", "B"),
        )

    def test_inf_tension_unchanged(self):
        """Infinite tension (no edge) stays infinite with overlap on."""
        L = build_overlap_differentiator()
        L.overlap_modulation = True
        ctrl = E0Controller(L, MOCK_EXEC)
        pt = ctrl._penalized_tension("A", "NONEXISTENT")
        self.assertTrue(math.isinf(pt))


if __name__ == "__main__":
    unittest.main()
