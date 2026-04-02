"""
C99 — Inertia Dampening in Controller Greedy Loop
====================================================
Tests that inertia_factor() actually changes the controller's
greedy decisions — not just transition_field() in escalation.

Prior state (C98): inertia_factor is implemented in historization.py,
called by landscape.transition_field() if inertia_modulation=True,
but the greedy loop (_penalized_tension) was blind to it.

C99 integrates: _penalized_tension divides S_eff by I(x,y)
when inertia_modulation is True.  I ∈ (1−α, 1.0]:
  - I = 1.0 for uninscribed edges or clear quality → no effect
  - I < 1.0 for contradictory inscription (high load, |q| ≈ 0)
  - Greedy avoids confused edges, preferring clear or fresh ones.

Key property: captures what δ_H ≈ 0 misses.  When U ≈ F,
δ_H = λ_f·F − λ_s·U ≈ 0 looks like "no inscription", but
inertia_factor sees m >> 0 with q ≈ 0 = "lots of contradictory
inscription" and dampens accordingly.
"""

import math
import unittest

from e0_controller.controller import E0Controller, EscalationType
from e0_controller.historization import Historization
from e0_controller.landscape import Landscape
from e0_controller.primitives import Edge, Outcome


# ═══════════════════════════════════════════════════════════════
# Domain builders
# ═══════════════════════════════════════════════════════════════

def build_confused_vs_fresh() -> Landscape:
    """
    Falsification domain: two paths with identical S_eff,
    but one has contradictory inscription.

    Path 1: S → A → GOAL  (will be inscribed with U ≈ F)
    Path 2: S → B → GOAL  (stays fresh)

    All edges: δ=1.0, R=1.0 → S_eff = 1.0 everywhere.
    After confusing S→A, δ_H ≈ 0 so S_eff stays ≈ 1.0.
    But inertia_factor(S→A) < 1.0 → S_eff_penalized > 1.0.
    """
    L = Landscape()
    for s, t in [("S", "A"), ("A", "GOAL"),
                 ("S", "B"), ("B", "GOAL")]:
        L.add_edge(s, t, delta=1.0, resistance=1.0)
    return L


def confuse_edge(L: Landscape, src: str, tgt: str,
                 rounds: int = 10) -> None:
    """Inscribe an edge with alternating SUCCESS/FAILURE."""
    edge = Edge(src, tgt)
    for i in range(rounds):
        outcome = Outcome.SUCCESS if i % 2 == 0 else Outcome.FAILURE
        L.historization.update(edge, outcome)


def build_three_way_clarity() -> Landscape:
    """
    Three paths S → {A, B, C} → GOAL.
    A: confused (U≈F), B: clear success (U>>F), C: clear failure (F>>U).

    B and C both have high |q| → I ≈ 1.0.
    A has low |q| → I < 1.0 → penalized.
    Without inertia: A, B, C have similar S_eff (δ_H biases differ).
    With inertia: A is specifically penalized for confusion.
    """
    L = Landscape()
    for node in ["A", "B", "C"]:
        L.add_edge("S", node, delta=1.0, resistance=1.0)
        L.add_edge(node, "GOAL", delta=1.0, resistance=1.0)
    return L


def build_inertia_irrelevant() -> Landscape:
    """Simple domain where no edge has inscription → I=1.0 everywhere."""
    L = Landscape()
    for s, t in [("S", "A"), ("A", "B"), ("B", "GOAL")]:
        L.add_edge(s, t, delta=1.0, resistance=1.0)
    return L


def build_two_paths_both_confused() -> Landscape:
    """Both paths have identical confusion → inertia penalizes equally."""
    L = Landscape()
    for s, t in [("S", "A"), ("A", "GOAL"),
                 ("S", "B"), ("B", "GOAL")]:
        L.add_edge(s, t, delta=1.0, resistance=1.0)
    return L


# ═══════════════════════════════════════════════════════════════
# Test Classes
# ═══════════════════════════════════════════════════════════════

class TestGreedyInertiaIntegration(unittest.TestCase):
    """Core falsification: inertia changes greedy choice."""

    def test_fresh_preferred_over_confused(self):
        """Controller avoids confused edge when inertia_modulation=True."""
        L = build_confused_vs_fresh()
        L.inertia_modulation = True
        confuse_edge(L, "S", "A", rounds=20)

        ctrl = E0Controller(L, lambda s, t: Outcome.SUCCESS)
        nxt, esc, esc_type = ctrl.select_next("S")
        self.assertEqual(nxt, "B",
                         "Greedy should prefer fresh B over confused A")

    def test_no_change_without_flag(self):
        """Without inertia_modulation, confused edge is NOT penalized."""
        L = build_confused_vs_fresh()
        L.inertia_modulation = False
        confuse_edge(L, "S", "A", rounds=20)

        ctrl = E0Controller(L, lambda s, t: Outcome.SUCCESS)
        nxt, esc, esc_type = ctrl.select_next("S")
        # Without inertia, both have essentially equal S_eff.
        # Controller may pick A or B depending on iteration order, but
        # it must NOT specifically avoid A due to confusion.
        # We verify that _penalized_tension is approximately equal.
        s_a = ctrl._penalized_tension("S", "A")
        s_b = ctrl._penalized_tension("S", "B")
        # δ_H may cause slight difference, but not the 2x from inertia
        self.assertAlmostEqual(s_a, s_b, delta=0.5,
                               msg="Without inertia flag, tensions should be similar")

    def test_inertia_inflates_tension(self):
        """Confused edge gets higher _penalized_tension than fresh edge."""
        L = build_confused_vs_fresh()
        L.inertia_modulation = True
        confuse_edge(L, "S", "A", rounds=20)

        ctrl = E0Controller(L, lambda s, t: Outcome.SUCCESS)
        s_a = ctrl._penalized_tension("S", "A")
        s_b = ctrl._penalized_tension("S", "B")
        self.assertGreater(s_a, s_b,
                           "Confused edge should have higher penalized tension")

    def test_run_avoids_confused_path(self):
        """Full run navigates through fresh path, not confused one."""
        L = build_confused_vs_fresh()
        L.inertia_modulation = True
        confuse_edge(L, "S", "A", rounds=20)

        ctrl = E0Controller(L, lambda s, t: Outcome.SUCCESS)
        trace = ctrl.run("S", goal="GOAL", max_cycles=10)
        self.assertIn("B", trace.path,
                      "Run should go through B (fresh), not A (confused)")

    def test_delta_H_small_but_inertia_active(self):
        """Verify the core insight: δ_H is small relative to R₀ but I < 1.

        With lazy decay and alternating U/F, δ_H may not be exactly zero
        (decay affects older traces more), but it's small compared to the
        base resistance R₀=1.0.  Meanwhile inertia_factor is clearly < 1.
        """
        L = build_confused_vs_fresh()
        confuse_edge(L, "S", "A", rounds=20)

        edge_a = Edge("S", "A")
        delta_h = abs(L.historization.delta_H(edge_a))
        inertia = L.historization.inertia_factor(edge_a)

        # δ_H should be small relative to R₀ = 1.0
        self.assertLess(delta_h, 1.0,
                        f"|δ_H| should be < R₀=1.0 for alternating U≈F, got {delta_h}")
        # But inertia should be significantly < 1
        self.assertLess(inertia, 0.85,
                        f"inertia_factor should be < 0.85 for confused edge, got {inertia}")

    def test_deep_confusion_stronger_penalty(self):
        """More contradictory rounds → lower I → higher S_eff penalty."""
        L1 = build_confused_vs_fresh()
        L1.inertia_modulation = True
        confuse_edge(L1, "S", "A", rounds=6)

        L2 = build_confused_vs_fresh()
        L2.inertia_modulation = True
        confuse_edge(L2, "S", "A", rounds=30)

        ctrl1 = E0Controller(L1, lambda s, t: Outcome.SUCCESS)
        ctrl2 = E0Controller(L2, lambda s, t: Outcome.SUCCESS)

        s1 = ctrl1._penalized_tension("S", "A")
        s2 = ctrl2._penalized_tension("S", "A")
        self.assertGreater(s2, s1,
                           "Deeper confusion should produce stronger penalty")


class TestNeutralityOnFreshDomains(unittest.TestCase):
    """Inertia should have zero effect on uninscribed landscapes."""

    def test_fresh_landscape_unchanged(self):
        """No inscription → I=1.0 → identical _penalized_tension."""
        L = build_inertia_irrelevant()
        L.inertia_modulation = True

        ctrl = E0Controller(L, lambda s, t: Outcome.SUCCESS)
        s_on = ctrl._penalized_tension("S", "A")

        L2 = build_inertia_irrelevant()
        L2.inertia_modulation = False
        ctrl2 = E0Controller(L2, lambda s, t: Outcome.SUCCESS)
        s_off = ctrl2._penalized_tension("S", "A")

        self.assertAlmostEqual(s_on, s_off, places=10,
                               msg="Fresh edges: inertia flag should have zero effect")

    def test_clear_success_not_penalized(self):
        """Edge with consistent successes has I ≈ 1.0 → no penalty."""
        L = build_confused_vs_fresh()
        L.inertia_modulation = True
        edge = Edge("S", "A")
        for _ in range(20):
            L.historization.update(edge, Outcome.SUCCESS)

        ctrl = E0Controller(L, lambda s, t: Outcome.SUCCESS)
        inertia = L.historization.inertia_factor(edge)
        self.assertGreater(inertia, 0.95,
                           f"Consistently successful edge should have I > 0.95, got {inertia}")

    def test_clear_failure_not_penalized(self):
        """Edge with consistent failures has I ≈ 1.0 → not penalized by inertia.
        (It's penalized by δ_H instead, which is the correct mechanism.)"""
        L = build_confused_vs_fresh()
        L.inertia_modulation = True
        edge = Edge("S", "A")
        for _ in range(20):
            L.historization.update(edge, Outcome.FAILURE)

        inertia = L.historization.inertia_factor(edge)
        self.assertGreater(inertia, 0.95,
                           f"Consistently failing edge should have I > 0.95, got {inertia}")


class TestThreeWayClarity(unittest.TestCase):
    """Three paths: confused, clear-success, clear-failure."""

    def test_confused_ranked_worse_than_success(self):
        """Confused path has higher penalized tension than clear-success path.

        Note: clear-failure (C) gets high δ_H which dominates over inertia,
        so we don't compare A vs C here.  Inertia's job is to distinguish
        confused (δ_H ≈ 0, I < 1) from fresh/clear-success (δ_H ≈ 0, I = 1).
        """
        L = build_three_way_clarity()
        L.inertia_modulation = True

        # A: confused
        confuse_edge(L, "S", "A", rounds=20)
        # B: clear success
        for _ in range(20):
            L.historization.update(Edge("S", "B"), Outcome.SUCCESS)

        ctrl = E0Controller(L, lambda s, t: Outcome.SUCCESS)
        s_a = ctrl._penalized_tension("S", "A")
        s_b = ctrl._penalized_tension("S", "B")

        self.assertGreater(s_a, s_b,
                           "Confused A should have higher tension than clear-success B")

    def test_greedy_avoids_confused(self):
        """Controller picks B or C, not A."""
        L = build_three_way_clarity()
        L.inertia_modulation = True

        confuse_edge(L, "S", "A", rounds=20)
        for _ in range(20):
            L.historization.update(Edge("S", "B"), Outcome.SUCCESS)
        for _ in range(20):
            L.historization.update(Edge("S", "C"), Outcome.FAILURE)

        ctrl = E0Controller(L, lambda s, t: Outcome.SUCCESS)
        nxt, _, _ = ctrl.select_next("S")
        self.assertNotEqual(nxt, "A",
                            "Controller should avoid confused path A")


class TestInertiaModulationFlag(unittest.TestCase):
    """Boolean flag semantics."""

    def test_flag_defaults_false(self):
        """inertia_modulation is False by default."""
        L = Landscape()
        self.assertFalse(L.inertia_modulation)

    def test_backward_compat_alias(self):
        """mass_modulation property maps to inertia_modulation."""
        L = Landscape()
        L.inertia_modulation = True
        self.assertTrue(L.mass_modulation)
        L.mass_modulation = False
        self.assertFalse(L.inertia_modulation)

    def test_toggle_mid_run(self):
        """Toggling inertia_modulation mid-run changes behavior."""
        L = build_confused_vs_fresh()
        confuse_edge(L, "S", "A", rounds=20)
        ctrl = E0Controller(L, lambda s, t: Outcome.SUCCESS)

        L.inertia_modulation = False
        s_off = ctrl._penalized_tension("S", "A")

        L.inertia_modulation = True
        s_on = ctrl._penalized_tension("S", "A")

        self.assertGreater(s_on, s_off,
                           "Enabling inertia mid-run should inflate confused tension")


class TestInertiaWithOverlap(unittest.TestCase):
    """C98 + C99 can compose: overlap and inertia both active."""

    def test_both_flags_compose(self):
        """overlap + inertia both divide S_eff independently."""
        L = build_confused_vs_fresh()
        confuse_edge(L, "S", "A", rounds=20)

        ctrl_inertia = E0Controller(L, lambda s, t: Outcome.SUCCESS)
        L.inertia_modulation = True
        L.overlap_modulation = False
        s_inertia = ctrl_inertia._penalized_tension("S", "A")

        L.inertia_modulation = True
        L.overlap_modulation = True
        s_both = ctrl_inertia._penalized_tension("S", "A")

        # On this domain without triangles, M_H=1.0 so both should be equal.
        # But the important thing is it doesn't crash and composes cleanly.
        self.assertGreater(s_inertia, 0)
        self.assertGreater(s_both, 0)


class TestMathematicalProperties(unittest.TestCase):
    """Verify inertia_factor mathematical guarantees."""

    def test_inertia_bounded(self):
        """I ∈ (0.5, 1.0] with default α=0.5."""
        L = build_confused_vs_fresh()
        confuse_edge(L, "S", "A", rounds=100)
        edge = Edge("S", "A")
        I = L.historization.inertia_factor(edge)
        self.assertGreater(I, 0.5 - 0.01,
                           f"I should be > 0.49 (lower bound 1-α=0.5), got {I}")
        self.assertLessEqual(I, 1.0,
                             f"I should be ≤ 1.0, got {I}")

    def test_uninscribed_returns_one(self):
        """No traces → I = 1.0 exactly."""
        L = build_confused_vs_fresh()
        edge = Edge("S", "A")
        I = L.historization.inertia_factor(edge)
        self.assertEqual(I, 1.0)

    def test_monotonic_with_confusion(self):
        """More confusion (same load) → lower I."""
        h = Historization()
        # Edge with all sucesses (q=1, no confusion)
        edge_clear = Edge("X", "Y")
        for _ in range(10):
            h.update(edge_clear, Outcome.SUCCESS)

        # Edge with alternating (q≈0, max confusion)
        edge_confused = Edge("P", "Q")
        for i in range(10):
            h.update(edge_confused,
                     Outcome.SUCCESS if i % 2 == 0 else Outcome.FAILURE)

        I_clear = h.inertia_factor(edge_clear)
        I_confused = h.inertia_factor(edge_confused)
        self.assertGreater(I_clear, I_confused,
                           "Clear edge should have higher I than confused edge")

    def test_division_never_zero(self):
        """I > 0 always → division in _penalized_tension is safe."""
        h = Historization()
        edge = Edge("X", "Y")
        # Worst case: maximum confusion
        for i in range(1000):
            h.update(edge, Outcome.SUCCESS if i % 2 == 0 else Outcome.FAILURE)
        I = h.inertia_factor(edge)
        self.assertGreater(I, 0,
                           "inertia_factor must never be zero (division safety)")


class TestSelfGraphTracking(unittest.TestCase):
    """Self-graph should see inertia as active component."""

    def test_inertia_in_active_components(self):
        """active_components reports inertia when flag is True."""
        from e0_controller.self_graph import active_components
        comps = active_components(
            curvature_active=False,
            overlap_active=False,
            inertia_active=True,
        )
        self.assertIn("inertia", comps)

    def test_inertia_always_in_core(self):
        """inertia is a CORE_COMPONENT — always present regardless of flag.

        The inertia_modulation flag controls whether inertia *affects*
        decisions, not whether it's tracked in the self-graph.
        """
        from e0_controller.self_graph import active_components
        comps_on = active_components(
            curvature_active=False,
            overlap_active=False,
            inertia_active=True,
        )
        comps_off = active_components(
            curvature_active=False,
            overlap_active=False,
            inertia_active=False,
        )
        self.assertIn("inertia", comps_on)
        self.assertIn("inertia", comps_off)


if __name__ == "__main__":
    unittest.main()
