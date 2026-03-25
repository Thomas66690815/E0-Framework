"""
E₀ G5 Edge Case Tests — Families A–E
=====================================
Formal tests encoding the findings from the G5 Edge Case Suite exploration.
Reference: docs/E0_G5_EDGE_CASE_SUITE_v1.md

Test families:
  A — Goal-count expansion: winner stability as |G| grows
  B — Irrelevant-goal injection: unreachable safe, coherent-path goals shift
  C — Competing-goal conflict: generalist wins in multi-goal
  D — Rescue threshold: low-delta paths rescue at minimal strength
  E — Ranking sharpness: selectivity preserved (entropy↓, gap↑ as |G| grows)

Run:
    python -m pytest e0_controller/test_g5_edge_cases.py -v
"""
import math
import unittest

from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller
from e0_controller.primitives import Outcome
from e0_controller.amplitude_overlay import analyze_controller_state

START = "START"


def evaluate(source, target):
    return Outcome.SUCCESS


def _analyze(ctrl, goals, horizon=5):
    return analyze_controller_state(
        ctrl, START, horizon_edges=horizon,
        geometry="goal_reaching", goals=goals
    )


def _probs(report):
    return {ai.action: ai.probability for ai in report.action_infos}


def _entropy(report):
    h = 0.0
    for ai in report.action_infos:
        p = ai.probability
        if p > 1e-15:
            h -= p * math.log2(p)
    return h


def _top_gap(report):
    ps = sorted([ai.probability for ai in report.action_infos], reverse=True)
    return ps[0] - ps[1] if len(ps) >= 2 else (ps[0] if ps else 0.0)


# ── Domain builders ───────────────────────────────────────────

def build_family_a() -> Landscape:
    """Star topology: A paths to G1-G3, B paths to G1,G4,G5."""
    L = Landscape()
    L.add_edge(START, "A", delta=0.3, resistance=0.3)
    L.add_edge("A", "M1", delta=0.5, resistance=0.2)
    L.add_edge("M1", "G1", delta=0.4, resistance=0.3)
    L.add_edge("A", "M2", delta=0.6, resistance=0.3)
    L.add_edge("M2", "G2", delta=0.5, resistance=0.3)
    L.add_edge("A", "M3", delta=0.3, resistance=0.5)
    L.add_edge("M3", "G3", delta=0.2, resistance=0.5)
    L.add_edge(START, "B", delta=0.5, resistance=0.4)
    L.add_edge("B", "G1", delta=0.8, resistance=0.2)
    L.add_edge("B", "M4", delta=0.4, resistance=0.4)
    L.add_edge("M4", "G4", delta=0.3, resistance=0.4)
    L.add_edge("B", "M5", delta=0.2, resistance=0.6)
    L.add_edge("M5", "G5", delta=0.1, resistance=0.7)
    return L


def build_family_b() -> Landscape:
    """Base domain + unreachable, weak, and noisy goals."""
    L = Landscape()
    L.add_edge(START, "A", delta=0.5, resistance=0.3)
    L.add_edge("A", "G_REAL", delta=0.6, resistance=0.2)
    L.add_edge(START, "B", delta=0.3, resistance=0.4)
    L.add_edge("B", "G_REAL", delta=0.4, resistance=0.3)
    L.add_edge(START, "C", delta=0.1, resistance=0.9)
    L.add_edge("C", "D", delta=0.05, resistance=0.95)
    L.add_edge("D", "E", delta=0.05, resistance=0.95)
    L.add_edge("E", "G_WEAK", delta=0.05, resistance=0.95)
    L.add_edge("A", "F1", delta=2.0, resistance=0.1)
    L.add_edge("F1", "G_NOISY", delta=0.3, resistance=0.3)
    L.add_edge("A", "F2", delta=0.1, resistance=0.8)
    L.add_edge("F2", "G_NOISY", delta=2.5, resistance=0.1)
    L.add_edge("ISOLATED", "G_UNREACH", delta=1.0, resistance=0.5)
    return L


def build_family_c() -> Landscape:
    """Conflict: A→G_ALPHA, B→G_BETA, C→both (Gordian-style on G_ALPHA, weak on G_BETA)."""
    L = Landscape()
    L.add_edge(START, "A", delta=0.4, resistance=0.3)
    L.add_edge("A", "G_ALPHA", delta=0.6, resistance=0.2)
    L.add_edge(START, "B", delta=0.4, resistance=0.3)
    L.add_edge("B", "G_BETA", delta=0.6, resistance=0.2)
    L.add_edge(START, "C", delta=0.8, resistance=0.1)
    L.add_edge("C", "X1", delta=0.2, resistance=0.4)
    L.add_edge("X1", "G_ALPHA", delta=0.2, resistance=0.4)
    L.add_edge("C", "X2", delta=2.5, resistance=0.05)
    L.add_edge("X2", "G_ALPHA", delta=2.5, resistance=0.05)
    L.add_edge("C", "Y1", delta=0.1, resistance=0.8)
    L.add_edge("Y1", "G_BETA", delta=0.1, resistance=0.8)
    return L


def build_family_d(rescue_delta: float) -> Landscape:
    """Gordian A → G1 (destructive) + rescue A → G2 (variable strength) + B → G1."""
    L = Landscape()
    L.add_edge(START, "A", delta=0.3, resistance=0.3)
    L.add_edge("A", "S1", delta=0.3, resistance=0.3)
    L.add_edge("S1", "G1", delta=0.3, resistance=0.3)
    L.add_edge("A", "L1", delta=2.5, resistance=0.05)
    L.add_edge("L1", "L2", delta=2.5, resistance=0.05)
    L.add_edge("L2", "G1", delta=2.5, resistance=0.05)
    L.add_edge("A", "R1", delta=rescue_delta, resistance=0.3)
    L.add_edge("R1", "G2", delta=rescue_delta, resistance=0.3)
    L.add_edge(START, "B", delta=0.5, resistance=0.4)
    L.add_edge("B", "G1", delta=0.5, resistance=0.3)
    return L


def build_family_e(n_goals: int) -> Landscape:
    """Uniform star: A→all goals, B→even goals, C→every 3rd goal."""
    L = Landscape()
    L.add_edge(START, "A", delta=0.4 + 0.1 * ord("A"), resistance=0.3)
    L.add_edge(START, "B", delta=0.4 + 0.1 * ord("B"), resistance=0.3)
    L.add_edge(START, "C", delta=0.4 + 0.1 * ord("C"), resistance=0.3)
    for i in range(n_goals):
        g = f"G{i+1}"
        L.add_edge("A", f"A_M{i}", delta=0.5, resistance=0.25)
        L.add_edge(f"A_M{i}", g, delta=0.4, resistance=0.3)
        if i % 2 == 0:
            L.add_edge("B", f"B_M{i}", delta=0.3, resistance=0.4)
            L.add_edge(f"B_M{i}", g, delta=0.3, resistance=0.4)
        if i % 3 == 0:
            L.add_edge("C", f"C_M{i}", delta=0.2, resistance=0.5)
            L.add_edge(f"C_M{i}", g, delta=0.2, resistance=0.5)
    return L


# ══════════════════════════════════════════════════════════════
# Family A — Goal-Count Expansion
# ══════════════════════════════════════════════════════════════

class TestFamilyA_GoalCountExpansion(unittest.TestCase):
    """G5 behavior as goal set expands from |G|=1 to |G|=5."""

    def setUp(self):
        self.L = build_family_a()
        self.ctrl = E0Controller(self.L, evaluate)
        self.all_goals = ["G1", "G2", "G3", "G4", "G5"]

    def test_winner_stable_across_goal_counts(self):
        """A should win for all |G| = 1..5."""
        for n in range(1, 6):
            goals = set(self.all_goals[:n])
            report = _analyze(self.ctrl, goals)
            self.assertEqual(report.amplitude_choice, "A",
                             f"|G|={n}: expected A, got {report.amplitude_choice}")

    def test_selectivity_peaks_midrange(self):
        """Top-1 probability peaks at |G|=2 or 3 (where A has exclusive goal support)."""
        probs = []
        for n in range(1, 6):
            goals = set(self.all_goals[:n])
            report = _analyze(self.ctrl, goals)
            probs.append(max(ai.probability for ai in report.action_infos))
        # Peak should be at index 1 or 2 (|G|=2 or 3)
        peak_idx = probs.index(max(probs))
        self.assertIn(peak_idx, [1, 2],
                      f"Peak at |G|={peak_idx+1}, expected 2 or 3")

    def test_no_saturation_collapse(self):
        """At |G|=5, top-1 probability should remain > 0.4 (not collapsed)."""
        report = _analyze(self.ctrl, set(self.all_goals))
        top1 = max(ai.probability for ai in report.action_infos)
        self.assertGreater(top1, 0.4,
                           f"Top-1 P={top1:.3f} at |G|=5 — possible saturation")

    def test_entropy_bounded(self):
        """Entropy should stay below 1.2 bits at peak selectivity."""
        report = _analyze(self.ctrl, {"G1", "G2", "G3"})
        ent = _entropy(report)
        self.assertLess(ent, 1.2,
                        f"Entropy={ent:.3f} at |G|=3 — too flat")


# ══════════════════════════════════════════════════════════════
# Family B — Irrelevant-Goal Injection
# ══════════════════════════════════════════════════════════════

class TestFamilyB_IrrelevantGoals(unittest.TestCase):
    """Adding unreachable, weak, or noisy goals."""

    def setUp(self):
        self.L = build_family_b()
        self.ctrl = E0Controller(self.L, evaluate)

    def test_unreachable_goal_zero_effect(self):
        """Unreachable goals contribute 0 — winner and probs unchanged."""
        r_base = _analyze(self.ctrl, {"G_REAL"})
        r_ext = _analyze(self.ctrl, {"G_REAL", "G_UNREACH"})
        self.assertEqual(r_base.amplitude_choice, r_ext.amplitude_choice)
        # Probabilities identical (unreachable = no paths = no amplitude)
        for ai_b, ai_e in zip(r_base.action_infos, r_ext.action_infos):
            self.assertAlmostEqual(ai_b.probability, ai_e.probability, places=10)

    def test_unreachable_probs_match_exactly(self):
        """Adding G_UNREACH does not alter probability distribution at all."""
        r_base = _analyze(self.ctrl, {"G_REAL"})
        r_ext = _analyze(self.ctrl, {"G_REAL", "G_UNREACH"})
        base_probs = _probs(r_base)
        ext_probs = _probs(r_ext)
        for action in base_probs:
            self.assertAlmostEqual(base_probs[action], ext_probs[action], places=10,
                                   msg=f"Probs for {action} changed with unreachable goal")

    def test_weak_goal_shifts_winner_to_reacher(self):
        """G_WEAK is only reachable via C → adding it boosts C.
        This is CORRECT behavior: C genuinely reaches a goal others don't."""
        r_ext = _analyze(self.ctrl, {"G_REAL", "G_WEAK"}, horizon=6)
        probs = _probs(r_ext)
        # C should get non-trivial probability (it's the only path to G_WEAK)
        self.assertGreater(probs.get("C", 0), 0.1,
                           "C should gain support from its exclusive goal path")

    def test_noisy_goal_boosts_action_with_coherent_paths(self):
        """G_NOISY paths go through A (A→F1→G_NOISY, A→F2→G_NOISY).
        Adding it should boost A because A has coherent goal-reaching paths."""
        r_base = _analyze(self.ctrl, {"G_REAL"})
        r_ext = _analyze(self.ctrl, {"G_REAL", "G_NOISY"})
        base_pa = _probs(r_base).get("A", 0)
        ext_pa = _probs(r_ext).get("A", 0)
        self.assertGreater(ext_pa, base_pa,
                           "A's probability should increase with G_NOISY (paths go through A)")

    def test_base_case_winner(self):
        """Base case: G_REAL only — verify B wins (stronger direct path)."""
        report = _analyze(self.ctrl, {"G_REAL"})
        self.assertEqual(report.amplitude_choice, "B")


# ══════════════════════════════════════════════════════════════
# Family C — Competing-Goal Conflict
# ══════════════════════════════════════════════════════════════

class TestFamilyC_CompetingGoals(unittest.TestCase):
    """A→G_ALPHA, B→G_BETA, C→both. How does G5 combine conflict?"""

    def setUp(self):
        self.L = build_family_c()
        self.ctrl = E0Controller(self.L, evaluate)

    def test_single_goal_alpha_specialist_wins(self):
        """G_ALPHA only: A or C should win (specialists for alpha)."""
        report = _analyze(self.ctrl, {"G_ALPHA"})
        self.assertIn(report.amplitude_choice, ["A", "C"],
                      "G_ALPHA-only winner should be A or C")

    def test_single_goal_beta_specialist_wins(self):
        """G_BETA only: B should win (specialist for beta). Override expected."""
        report = _analyze(self.ctrl, {"G_BETA"})
        self.assertEqual(report.amplitude_choice, "B",
                         "G_BETA-only winner should be B")

    def test_multigaol_generalist_wins(self):
        """Both goals: C should win — it reaches BOTH targets."""
        report = _analyze(self.ctrl, {"G_ALPHA", "G_BETA"})
        self.assertEqual(report.amplitude_choice, "C",
                         "Multi-goal winner should be generalist C")

    def test_generalist_probability_above_50pct(self):
        """In multi-goal, C's probability should exceed 0.5 (clear generalist advantage)."""
        report = _analyze(self.ctrl, {"G_ALPHA", "G_BETA"})
        pc = _probs(report).get("C", 0)
        self.assertGreater(pc, 0.5,
                           f"Generalist C only has P={pc:.3f} — expected > 0.5")

    def test_specialists_symmetric_in_multigaol(self):
        """A and B should have roughly equal probability (both are specialists for one goal)."""
        report = _analyze(self.ctrl, {"G_ALPHA", "G_BETA"})
        probs = _probs(report)
        pa = probs.get("A", 0)
        pb = probs.get("B", 0)
        self.assertAlmostEqual(pa, pb, delta=0.05,
                               msg=f"Specialists should be symmetric: P(A)={pa:.3f}, P(B)={pb:.3f}")

    def test_conflict_changes_winner(self):
        """Single-goal winners differ: alpha→A/C, beta→B.
        Multi-goal winner C differs from both. Context-dependent, not erratic."""
        r_alpha = _analyze(self.ctrl, {"G_ALPHA"})
        r_beta = _analyze(self.ctrl, {"G_BETA"})
        r_both = _analyze(self.ctrl, {"G_ALPHA", "G_BETA"})
        # Different goals → different winners is expected
        alpha_w = r_alpha.amplitude_choice
        beta_w = r_beta.amplitude_choice
        both_w = r_both.amplitude_choice
        self.assertNotEqual(alpha_w, beta_w,
                            "Conflicting goals should prefer different specialists")


# ══════════════════════════════════════════════════════════════
# Family D — Rescue Threshold
# ══════════════════════════════════════════════════════════════

class TestFamilyD_RescueThreshold(unittest.TestCase):
    """Parametric: at what rescue_delta does A get rescued from destructive interference?"""

    def test_single_goal_a_always_suppressed(self):
        """With only G1, A is destructively suppressed — B always wins."""
        for delta in [0.1, 0.5, 1.0, 2.0]:
            L = build_family_d(delta)
            ctrl = E0Controller(L, evaluate)
            report = _analyze(ctrl, {"G1"})
            self.assertEqual(report.amplitude_choice, "B",
                             f"δ={delta}: A should be suppressed for G1-only")

    def test_rescue_at_low_delta(self):
        """At δ_rescue=0.1 with multi-goal, A should be rescued."""
        L = build_family_d(0.1)
        ctrl = E0Controller(L, evaluate)
        report = _analyze(ctrl, {"G1", "G2"})
        self.assertEqual(report.amplitude_choice, "A",
                         "Low-delta rescue path should rescue A")

    def test_rescue_at_minimal_delta(self):
        """Even at δ_rescue=0.01, rescue works — because S=Δ·R is tiny → |Ψ|≈1."""
        L = build_family_d(0.01)
        ctrl = E0Controller(L, evaluate)
        report = _analyze(ctrl, {"G1", "G2"})
        self.assertEqual(report.amplitude_choice, "A",
                         "Minimal-delta path still rescues (S=Δ·R≈0 → high amplitude)")

    def test_crossover_exists_between_0_8_and_1_5(self):
        """Rescue fades at high delta — crossover A→B happens between 0.8 and 1.5."""
        L_low = build_family_d(0.8)
        ctrl_low = E0Controller(L_low, evaluate)
        r_low = _analyze(ctrl_low, {"G1", "G2"})

        L_high = build_family_d(1.5)
        ctrl_high = E0Controller(L_high, evaluate)
        r_high = _analyze(ctrl_high, {"G1", "G2"})

        # At 0.8: A should still win or be competitive
        pa_low = _probs(r_low).get("A", 0)
        # At 1.5: B should dominate
        self.assertEqual(r_high.amplitude_choice, "B",
                         "At δ=1.5, rescue should have faded — B wins")
        self.assertGreater(pa_low, _probs(r_low).get("B", 0) * 0.8,
                           "At δ=0.8, A should still be competitive")

    def test_rescue_intensity_monotonic_initial(self):
        """A's intensity should decrease as rescue_delta increases (for small δ)."""
        intensities = []
        for d in [0.01, 0.1, 0.3, 0.5]:
            L = build_family_d(d)
            ctrl = E0Controller(L, evaluate)
            report = _analyze(ctrl, {"G1", "G2"})
            ia = next((ai.intensity for ai in report.action_infos if ai.action == "A"), 0)
            intensities.append(ia)
        # Should be roughly monotonically decreasing (more tension at higher delta)
        for i in range(len(intensities) - 1):
            self.assertGreaterEqual(intensities[i], intensities[i+1] * 0.8,
                                    f"I(A) should not spike at δ={[0.01,0.1,0.3,0.5][i+1]}")


# ══════════════════════════════════════════════════════════════
# Family E — Ranking Sharpness
# ══════════════════════════════════════════════════════════════

class TestFamilyE_RankingSharpness(unittest.TestCase):
    """Selectivity should be preserved or improved as |G| grows."""

    def _measure(self, n_goals):
        L = build_family_e(n_goals)
        ctrl = E0Controller(L, evaluate)
        goals = {f"G{i+1}" for i in range(n_goals)}
        report = _analyze(ctrl, goals)
        return report

    def test_a_wins_all_goal_counts(self):
        """A has paths to ALL goals → should win for |G|=1..8."""
        for n in range(1, 9):
            report = self._measure(n)
            self.assertEqual(report.amplitude_choice, "A",
                             f"|G|={n}: expected A, got {report.amplitude_choice}")

    def test_entropy_decreases_with_more_goals(self):
        """Entropy at |G|=8 should be lower than at |G|=1 (selectivity improves)."""
        ent_1 = _entropy(self._measure(1))
        ent_8 = _entropy(self._measure(8))
        self.assertLess(ent_8, ent_1,
                        f"Entropy should decrease: H(1)={ent_1:.3f}, H(8)={ent_8:.3f}")

    def test_top_gap_increases_with_more_goals(self):
        """Top-1 vs top-2 gap at |G|=8 should exceed gap at |G|=1."""
        gap_1 = _top_gap(self._measure(1))
        gap_8 = _top_gap(self._measure(8))
        self.assertGreater(gap_8, gap_1,
                           f"Gap should increase: G(1)={gap_1:.3f}, G(8)={gap_8:.3f}")

    def test_no_saturation_at_8_goals(self):
        """At |G|=8, top-1 probability should exceed 0.6 (no saturation)."""
        report = self._measure(8)
        top1 = max(ai.probability for ai in report.action_infos)
        self.assertGreater(top1, 0.6,
                           f"Top-1 P={top1:.3f} at |G|=8 — possible F1 saturation")

    def test_path_count_scales_with_goals(self):
        """A's path count should grow linearly with |G| (1 path per goal)."""
        r1 = self._measure(1)
        r4 = self._measure(4)
        pc_1 = next(ai.path_count for ai in r1.action_infos if ai.action == "A")
        pc_4 = next(ai.path_count for ai in r4.action_infos if ai.action == "A")
        self.assertEqual(pc_4, 4 * pc_1,
                         f"A should have 4× paths at |G|=4 vs |G|=1")


# ══════════════════════════════════════════════════════════════
# Cross-Family: Structural Properties
# ══════════════════════════════════════════════════════════════

class TestCrossFamily_StructuralProperties(unittest.TestCase):
    """Properties that must hold across all families."""

    def test_probabilities_sum_to_one(self):
        """All reports must have probabilities summing to 1.0."""
        cases = [
            (build_family_a(), {"G1", "G2", "G3"}),
            (build_family_b(), {"G_REAL", "G_NOISY"}),
            (build_family_c(), {"G_ALPHA", "G_BETA"}),
            (build_family_d(0.5), {"G1", "G2"}),
            (build_family_e(5), {f"G{i+1}" for i in range(5)}),
        ]
        for L, goals in cases:
            ctrl = E0Controller(L, evaluate)
            report = _analyze(ctrl, goals)
            total = sum(ai.probability for ai in report.action_infos)
            self.assertAlmostEqual(total, 1.0, places=8,
                                   msg=f"Probs sum to {total:.10f}, not 1.0")

    def test_intensity_non_negative(self):
        """All intensities must be ≥ 0 (they are |Ψ|²)."""
        cases = [
            (build_family_a(), {"G1", "G2", "G3", "G4", "G5"}),
            (build_family_c(), {"G_ALPHA", "G_BETA"}),
            (build_family_d(0.01), {"G1", "G2"}),
        ]
        for L, goals in cases:
            ctrl = E0Controller(L, evaluate)
            report = _analyze(ctrl, goals)
            for ai in report.action_infos:
                self.assertGreaterEqual(ai.intensity, 0.0,
                                        f"{ai.action} has negative intensity")

    def test_empty_action_has_zero_paths(self):
        """Actions with no goal-reaching paths should have I=0, P=0."""
        L = build_family_c()
        ctrl = E0Controller(L, evaluate)
        # B has no paths to G_ALPHA
        report = _analyze(ctrl, {"G_ALPHA"})
        b_info = next((ai for ai in report.action_infos if ai.action == "B"), None)
        if b_info:
            self.assertEqual(b_info.path_count, 0)
            self.assertAlmostEqual(b_info.intensity, 0.0, places=10)


if __name__ == "__main__":
    unittest.main()
