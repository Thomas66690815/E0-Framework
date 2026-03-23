"""
E₀ Controller — Tests: Amplitude Overlay (Phase 3i)
====================================================
Unit tests for amplitude_overlay.py covering:

    1. Path enumeration (_enumerate_continuations)
    2. Path filtering by first action
    3. Ψ summation and intensity computation
    4. P normalization (probabilities sum to 1)
    5. Deterministic vs amplitude choice comparison
    6. Edge cases: dead-end, single neighbor, horizon=1
    7. Interference-rich domain: destructive / constructive effects

Test domains:
    - Mini-Domain (existing 8-state graph)
    - Diamond Domain (purpose-built for interference)

Diamond Domain (interference-rich):

       ┌──(0.3/0.6)──→ A ──(0.2/0.4)──→ M ──(0.15/0.3)──→ Z
       │                ↑                                    ↑
    S ─┤          (0.8/2.0) ← A          (0.3/0.5)──→ Z ← N
       │                                                     ↑
       ├──(0.35/0.7)──→ B ──(0.25/0.6)──→ N ──(0.2/0.4)──→ Z
       │                ↑
       │          (0.5/1.5) ← B
       │
       └──(0.3/0.5)──→ C  (dead-end: no outgoing)

    Key design choices:
    - A has a strong back-edge (0.8/2.0) — creates asymmetric v_rot → large ω
    - B has a milder back-edge (0.5/1.5) — different ω structure
    - Upper path (S→A→M→Z) and lower path (S→B→N→Z) have similar S
      but different Θ accumulation → interference at Z
    - C is a dead-end trap (tests amplitude vs greedy divergence)
    - S(S→A) = 0.18, S(S→B) = 0.245, S(S→C) = 0.15
      → greedy picks C (lowest S), but C is dead-end
"""

from __future__ import annotations

import cmath
import math
import unittest

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller
from e0_controller.amplitude_overlay import (
    analyze_controller_state,
    _enumerate_continuations,
    _filter_paths_by_first_action,
    ActionAmplitudeInfo,
    OverlayReport,
)
from e0_controller.wavepath import psi as path_psi
from e0_controller.connection import omega, theta
from e0_controller.test_minidomain import build_mini_landscape


# ──────────────────────────────────────────────
# Diamond Domain Builder
# ──────────────────────────────────────────────

def build_diamond_landscape() -> Landscape:
    """
    Build the interference-rich diamond domain.

    States: S, A, B, C, M, N, Z
    Design: two paths S→...→Z with similar S but different Θ,
    plus a dead-end trap C.
    """
    L = Landscape()

    # From S (start) — three choices
    L.add_edge("S", "A", delta=0.3, resistance=0.6)    # S_eff = 0.18
    L.add_edge("S", "B", delta=0.35, resistance=0.7)   # S_eff = 0.245
    L.add_edge("S", "C", delta=0.3, resistance=0.5)    # S_eff = 0.15 ← greedy picks this

    # C is a dead-end
    L.add_state("C")

    # Upper path: A → M → Z
    L.add_edge("A", "M", delta=0.2, resistance=0.4)    # S_eff = 0.08
    L.add_edge("M", "Z", delta=0.15, resistance=0.3)   # S_eff = 0.045

    # Lower path: B → N → Z
    L.add_edge("B", "N", delta=0.25, resistance=0.6)   # S_eff = 0.15
    L.add_edge("N", "Z", delta=0.2, resistance=0.4)    # S_eff = 0.08

    # Asymmetric back-edges (create v_rot asymmetry → non-trivial ω)
    L.add_edge("A", "S", delta=0.8, resistance=2.0)    # S_eff = 1.60 (heavy)
    L.add_edge("B", "S", delta=0.5, resistance=1.5)    # S_eff = 0.75 (medium)

    # Cross-link for extra interference: M connects to N
    L.add_edge("M", "N", delta=0.3, resistance=0.5)    # S_eff = 0.15

    return L


def diamond_all_success(source: str, target: str) -> Outcome:
    return Outcome.SUCCESS


# ──────────────────────────────────────────────
# Test Class 1: Path Enumeration
# ──────────────────────────────────────────────

class TestPathEnumeration(unittest.TestCase):
    """Tests for _enumerate_continuations: correctness and completeness."""

    def setUp(self):
        self.L = build_mini_landscape()
        self.ctrl = E0Controller(self.L, lambda s, t: Outcome.SUCCESS)

    def test_horizon_zero_returns_empty(self):
        """Horizon 0 means no paths."""
        paths = _enumerate_continuations(self.ctrl, "A", horizon_edges=0)
        self.assertEqual(paths, [])

    def test_horizon_one_returns_direct_neighbors(self):
        """Horizon 1: only immediate transitions."""
        paths = _enumerate_continuations(self.ctrl, "A", horizon_edges=1)
        # A has neighbors B and C
        self.assertEqual(len(paths), 2)
        self.assertIn(["A", "B"], paths)
        self.assertIn(["A", "C"], paths)

    def test_horizon_one_dead_end(self):
        """Dead-end state D has no neighbors → no paths."""
        paths = _enumerate_continuations(self.ctrl, "D", horizon_edges=0)
        self.assertEqual(paths, [])
        paths = _enumerate_continuations(self.ctrl, "D", horizon_edges=1)
        self.assertEqual(paths, [])

    def test_all_paths_start_with_current(self):
        """Every enumerated path starts with the current state."""
        paths = _enumerate_continuations(self.ctrl, "A", horizon_edges=3)
        for p in paths:
            self.assertEqual(p[0], "A", f"Path {p} doesn't start with A")

    def test_all_paths_respect_horizon(self):
        """No path has more edges than the horizon."""
        h = 3
        paths = _enumerate_continuations(self.ctrl, "A", horizon_edges=h)
        for p in paths:
            edges = len(p) - 1
            self.assertLessEqual(edges, h, f"Path {p} has {edges} edges > horizon {h}")

    def test_includes_prefix_paths(self):
        """Enumeration includes prefixes, not only max-depth leaves."""
        paths = _enumerate_continuations(self.ctrl, "B", horizon_edges=2)
        # Must include both 1-hop and 2-hop paths from B
        self.assertIn(["B", "E"], paths)
        self.assertIn(["B", "D"], paths)
        # And 2-hop
        two_hop = [p for p in paths if len(p) == 3]
        self.assertGreater(len(two_hop), 0, "Should have 2-hop paths")


class TestPathFiltering(unittest.TestCase):
    """Tests for _filter_paths_by_first_action."""

    def test_filter_selects_correct_first_hop(self):
        paths = [["A", "B", "E"], ["A", "C", "A"], ["A", "B", "D"]]
        filtered = _filter_paths_by_first_action(paths, "B")
        self.assertEqual(len(filtered), 2)
        for p in filtered:
            self.assertEqual(p[1], "B")

    def test_filter_empty_on_no_match(self):
        paths = [["A", "B", "E"], ["A", "B", "D"]]
        filtered = _filter_paths_by_first_action(paths, "C")
        self.assertEqual(filtered, [])

    def test_filter_ignores_single_node_paths(self):
        paths = [["A"], ["A", "B"]]
        filtered = _filter_paths_by_first_action(paths, "B")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0], ["A", "B"])


# ──────────────────────────────────────────────
# Test Class 2: Overlay Basics on Mini-Domain
# ──────────────────────────────────────────────

class TestOverlayBasicsMiniDomain(unittest.TestCase):
    """Core correctness tests on the existing mini-domain."""

    def setUp(self):
        self.L = build_mini_landscape()
        self.ctrl = E0Controller(self.L, lambda s, t: Outcome.SUCCESS, alpha=2.0)

    def test_report_fields_populated(self):
        """Report contains all expected fields."""
        report = analyze_controller_state(self.ctrl, "A", horizon_edges=2)
        self.assertEqual(report.current, "A")
        self.assertEqual(report.horizon_edges, 2)
        self.assertIsInstance(report.admissible_actions, list)
        self.assertGreater(len(report.admissible_actions), 0)
        self.assertIsNotNone(report.deterministic_choice)
        self.assertGreater(len(report.action_infos), 0)

    def test_probabilities_sum_to_one(self):
        """P values must sum to 1.0 when there are admissible actions."""
        report = analyze_controller_state(self.ctrl, "A", horizon_edges=3)
        total_p = sum(info.probability for info in report.action_infos)
        self.assertAlmostEqual(total_p, 1.0, places=10,
                               msg=f"Probabilities sum to {total_p}, not 1.0")

    def test_probabilities_sum_to_one_all_states(self):
        """P sums to 1 at every state with neighbors."""
        for state in ["A", "B", "C", "E", "F", "G"]:
            with self.subTest(state=state):
                neighbors = self.ctrl._admissible_neighbors(state)
                if not neighbors:
                    continue
                report = analyze_controller_state(self.ctrl, state, horizon_edges=3)
                total_p = sum(info.probability for info in report.action_infos)
                self.assertAlmostEqual(total_p, 1.0, places=10)

    def test_intensity_is_psi_squared(self):
        """I(action) = |Ψ_total|² for each action."""
        report = analyze_controller_state(self.ctrl, "E", horizon_edges=2)
        for info in report.action_infos:
            expected_I = abs(info.psi_total) ** 2
            self.assertAlmostEqual(info.intensity, expected_I, places=10,
                                   msg=f"I({info.action}) != |Ψ|²")

    def test_psi_total_is_sum_of_path_psis(self):
        """Ψ_total for an action = Σ Ψ(path) over its paths."""
        report = analyze_controller_state(self.ctrl, "E", horizon_edges=2)
        for info in report.action_infos:
            expected_psi = sum(
                (path_psi(self.L, p) for p in info.paths),
                start=complex(0.0, 0.0),
            )
            self.assertAlmostEqual(info.psi_total.real, expected_psi.real, places=10)
            self.assertAlmostEqual(info.psi_total.imag, expected_psi.imag, places=10)

    def test_horizon_must_be_positive(self):
        """horizon_edges < 1 raises ValueError."""
        with self.assertRaises(ValueError):
            analyze_controller_state(self.ctrl, "A", horizon_edges=0)

    def test_single_neighbor_probability_is_one(self):
        """State with exactly one neighbor: P = 1.0 for that action."""
        report = analyze_controller_state(self.ctrl, "G", horizon_edges=2)
        self.assertEqual(len(report.action_infos), 1)
        self.assertAlmostEqual(report.action_infos[0].probability, 1.0, places=10)
        self.assertEqual(report.action_infos[0].action, "GOAL")

    def test_deterministic_choice_in_admissible(self):
        """Controller's deterministic choice is one of the admissible actions."""
        report = analyze_controller_state(self.ctrl, "A", horizon_edges=2)
        if report.deterministic_choice is not None:
            self.assertIn(report.deterministic_choice, report.admissible_actions)

    def test_amplitude_choice_in_admissible(self):
        """Amplitude choice is one of the admissible actions."""
        report = analyze_controller_state(self.ctrl, "A", horizon_edges=2)
        if report.amplitude_choice is not None:
            self.assertIn(report.amplitude_choice, report.admissible_actions)

    def test_summary_is_string(self):
        """summary() returns a non-empty string."""
        report = analyze_controller_state(self.ctrl, "A", horizon_edges=2)
        s = report.summary()
        self.assertIsInstance(s, str)
        self.assertGreater(len(s), 0)


# ──────────────────────────────────────────────
# Test Class 3: Diamond Domain — Interference
# ──────────────────────────────────────────────

class TestDiamondDomainStructure(unittest.TestCase):
    """Verify diamond domain graph structure and basic properties."""

    def setUp(self):
        self.L = build_diamond_landscape()
        self.ctrl = E0Controller(self.L, diamond_all_success, alpha=2.0)

    def test_states_exist(self):
        """All 7 states are present."""
        for s in ["S", "A", "B", "C", "M", "N", "Z"]:
            self.assertIn(s, self.L.states, f"State {s} missing")

    def test_dead_end_C(self):
        """C has no outgoing edges — a dead end."""
        neighbors = self.ctrl._admissible_neighbors("C")
        self.assertEqual(neighbors, [])

    def test_greedy_picks_trap(self):
        """From S, greedy argmin(S_eff) picks C (S=0.15), the dead-end."""
        choice, escalated, _ = self.ctrl.select_next("S")
        self.assertEqual(choice, "C",
                         "Greedy should pick C (lowest immediate tension)")

    def test_two_paths_to_Z_have_different_theta(self):
        """Upper and lower paths to Z accumulate different total phase."""
        theta_upper = theta(self.L, ["S", "A", "M", "Z"])
        theta_lower = theta(self.L, ["S", "B", "N", "Z"])
        self.assertNotAlmostEqual(theta_upper, theta_lower, places=6,
                                  msg="Paths should have different Θ for interference")

    def test_omega_asymmetry_at_A(self):
        """A↔S has asymmetric edges → non-zero ω(S,A)."""
        w = omega(self.L, "S", "A")
        self.assertNotAlmostEqual(w, 0.0, places=6,
                                  msg="ω(S,A) should be non-zero due to asymmetric back-edge")

    def test_omega_asymmetry_at_B(self):
        """B↔S has asymmetric edges → non-zero ω(S,B)."""
        w = omega(self.L, "S", "B")
        self.assertNotAlmostEqual(w, 0.0, places=6,
                                  msg="ω(S,B) should be non-zero due to asymmetric back-edge")


class TestDiamondInterference(unittest.TestCase):
    """Tests verifying actual interference effects on the diamond domain."""

    def setUp(self):
        self.L = build_diamond_landscape()
        self.ctrl = E0Controller(self.L, diamond_all_success, alpha=2.0)

    def test_amplitude_avoids_dead_end(self):
        """Amplitude overlay should NOT pick C (dead-end) from S."""
        report = analyze_controller_state(self.ctrl, "S", horizon_edges=3)
        self.assertNotEqual(report.amplitude_choice, "C",
                            "Amplitude should see C is a dead-end (no forward paths)")

    def test_greedy_vs_amplitude_disagree_at_S(self):
        """At S, greedy picks C (trap) but amplitude should pick A or B."""
        report = analyze_controller_state(self.ctrl, "S", horizon_edges=3)
        self.assertEqual(report.deterministic_choice, "C",
                         "Greedy should pick C")
        self.assertIn(report.amplitude_choice, ["A", "B"],
                      "Amplitude should pick a productive path")

    def test_dead_end_has_minimal_intensity(self):
        """C's intensity should be minimal — only the direct 1-hop path."""
        report = analyze_controller_state(self.ctrl, "S", horizon_edges=3)
        c_info = next(i for i in report.action_infos if i.action == "C")
        self.assertEqual(c_info.path_count, 1,
                         "Dead-end C should have exactly 1 path (direct hop)")
        # A and B should both have more intensity than C
        for info in report.action_infos:
            if info.action in ["A", "B"]:
                self.assertGreater(info.intensity, c_info.intensity,
                                   f"{info.action} should have more intensity than dead-end C")

    def test_interference_affects_total_intensity(self):
        """
        Intensity at Z via action A and via action B should NOT simply equal
        sum of individual |Ψ(p)|² — the cross-term (interference) must matter.

        If Ψ_A = Σ Ψ(p_i), then |Ψ_A|² ≠ Σ |Ψ(p_i)|² when phases differ.
        """
        report = analyze_controller_state(self.ctrl, "S", horizon_edges=3)
        for info in report.action_infos:
            if info.path_count <= 1:
                continue  # no interference possible with 1 path
            # Compute incoherent sum (ignoring phase)
            incoherent = sum(abs(path_psi(self.L, p)) ** 2 for p in info.paths)
            # Coherent intensity
            coherent = info.intensity
            # If phases are non-trivial, these should differ
            # (constructive: coherent > incoherent, destructive: coherent < incoherent)
            if abs(incoherent - coherent) > 1e-10:
                # Interference is present — test passes
                return
        # If we get here, check that at least one multi-path action exists
        multi_path_actions = [i for i in report.action_infos if i.path_count > 1]
        if multi_path_actions:
            # Some multi-path action should show interference
            max_diff = max(
                abs(sum(abs(path_psi(self.L, p)) ** 2 for p in info.paths) - info.intensity)
                for info in multi_path_actions
            )
            self.assertGreater(max_diff, 1e-10,
                               "Expected detectable interference in multi-path actions")

    def test_probabilities_sum_to_one_diamond(self):
        """P normalization holds on the diamond domain."""
        for state in ["S", "A", "B", "M", "N"]:
            with self.subTest(state=state):
                neighbors = self.ctrl._admissible_neighbors(state)
                if not neighbors:
                    continue
                report = analyze_controller_state(self.ctrl, state, horizon_edges=3)
                total_p = sum(info.probability for info in report.action_infos)
                self.assertAlmostEqual(total_p, 1.0, places=10)

    def test_psi_consistency_diamond(self):
        """Ψ_total = Σ Ψ(path) for all actions on diamond domain."""
        report = analyze_controller_state(self.ctrl, "S", horizon_edges=3)
        for info in report.action_infos:
            expected_psi = sum(
                (path_psi(self.L, p) for p in info.paths),
                start=complex(0.0, 0.0),
            )
            self.assertAlmostEqual(
                abs(info.psi_total - expected_psi), 0.0, places=10,
                msg=f"Ψ inconsistency for action {info.action}",
            )

    def test_horizon_1_sees_only_direct(self):
        """With horizon=1, all actions have exactly 1 path (the direct hop)."""
        report = analyze_controller_state(self.ctrl, "S", horizon_edges=1)
        for info in report.action_infos:
            self.assertEqual(info.path_count, 1,
                             f"Horizon 1: action {info.action} should have 1 path")

    def test_higher_horizon_reveals_more_paths(self):
        """Horizon 3 should enumerate more paths than horizon 1."""
        r1 = analyze_controller_state(self.ctrl, "S", horizon_edges=1)
        r3 = analyze_controller_state(self.ctrl, "S", horizon_edges=3)
        paths_h1 = sum(i.path_count for i in r1.action_infos)
        paths_h3 = sum(i.path_count for i in r3.action_infos)
        self.assertGreater(paths_h3, paths_h1,
                           "More paths should be discovered at higher horizon")

    def test_cross_link_M_to_N_creates_extra_paths(self):
        """The M→N cross-link creates additional paths via action A."""
        report = analyze_controller_state(self.ctrl, "S", horizon_edges=3)
        a_info = next(i for i in report.action_infos if i.action == "A")
        # With cross-link: S→A→M→N is reachable → more paths
        paths_through_N = [p for p in a_info.paths if "N" in p]
        self.assertGreater(len(paths_through_N), 0,
                           "Cross-link M→N should create paths via A that reach N")


# ──────────────────────────────────────────────
# Test Class 4: Overlay Report API
# ──────────────────────────────────────────────

class TestOverlayReportAPI(unittest.TestCase):
    """Tests for the OverlayReport data structure and convenience methods."""

    def setUp(self):
        self.L = build_mini_landscape()
        self.ctrl = E0Controller(self.L, lambda s, t: Outcome.SUCCESS)

    def test_amplitude_choice_is_max_intensity(self):
        """amplitude_choice returns the action with highest intensity."""
        report = analyze_controller_state(self.ctrl, "E", horizon_edges=2)
        max_info = max(report.action_infos, key=lambda a: a.intensity)
        self.assertEqual(report.amplitude_choice, max_info.action)

    def test_amplitude_choice_none_when_no_actions(self):
        """amplitude_choice is None when there are no action_infos."""
        report = OverlayReport(
            current="X",
            horizon_edges=1,
            admissible_actions=[],
            deterministic_choice=None,
            deterministic_escalated=False,
            action_infos=[],
        )
        self.assertIsNone(report.amplitude_choice)

    def test_action_info_fields(self):
        """ActionAmplitudeInfo has all expected fields."""
        report = analyze_controller_state(self.ctrl, "B", horizon_edges=2)
        info = report.action_infos[0]
        self.assertIsInstance(info.action, str)
        self.assertIsInstance(info.direct_s_eff, float)
        self.assertIsInstance(info.penalized_s, float)
        self.assertIsInstance(info.path_count, int)
        self.assertIsInstance(info.paths, list)
        self.assertIsInstance(info.psi_total, complex)
        self.assertIsInstance(info.intensity, float)
        self.assertIsInstance(info.probability, float)

    def test_all_intensities_non_negative(self):
        """Intensity is always ≥ 0."""
        for state in ["A", "B", "C", "E", "F", "G"]:
            report = analyze_controller_state(self.ctrl, state, horizon_edges=2)
            for info in report.action_infos:
                self.assertGreaterEqual(info.intensity, 0.0)


if __name__ == "__main__":
    unittest.main()
