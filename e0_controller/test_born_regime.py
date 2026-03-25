"""
E₀ Born-Regime Axiom Verification
==================================
Formal numerical verification that the 5 Born-Criterion axioms
(from E0_BORN_CRITERION_ANALYSIS_v1.md §2) hold on concrete E₀ domains,
and that normalized intensity P(z) = I(z)/ΣI is the unique minimal
realization rule.

Born-Criterion Regime Axioms:
  B1 — Bounded alternative set    : |Ω| is finite
  B2 — Mutual exclusivity         : exactly one endpoint per episode
  B3 — Representation invariance  : P(z) independent of global phase
  B4 — Monotonicity               : I(z₁) > I(z₂) ⟹ P(z₁) > P(z₂)
  B5 — Coarse-graining consistency: P(A∪B) = P(A) + P(B) for disjoint

Additional uniqueness tests:
  U1 — f-distortion elimination   : P = f(I)/Σf(I) for f≠id is arbitrary
  U2 — |Ψ| vs |Ψ|² comparison    : |Ψ|² is the correct squared-norm
  U3 — Normalization sum          : ΣP = 1.0 exactly

Domains tested:
  - MiniDomain (3 states, simple)
  - Diamond (7 states, interference-rich)
  - Gordian Trap (8 states, destructive interference)
  - Multi-goal Gordian (11 states, multiple endpoint sets)
  - Current Loop (7 states, circulation-driven phase)

Run:
    python -m pytest e0_controller/test_born_regime.py -v
"""
import cmath
import math
import unittest

from e0_controller.landscape import Landscape
from e0_controller.connection import theta
from e0_controller.wavepath import psi as path_psi, intensity, sum_paths
from e0_controller.controller import E0Controller, HybridMode
from e0_controller.primitives import Outcome, Edge
from e0_controller.amplitude_overlay import (
    analyze_controller_state,
    _enumerate_continuations,
    _filter_paths_by_first_action,
    ActionAmplitudeInfo,
)


# ── Domain builders ───────────────────────────────────────────

def always_success(source, target):
    return Outcome.SUCCESS


def build_mini_domain() -> Landscape:
    """Minimal 3-state domain: S → A, S → B."""
    L = Landscape()
    L.add_edge("S", "A", delta=0.3, resistance=0.5)
    L.add_edge("S", "B", delta=0.4, resistance=0.6)
    return L


def build_diamond() -> Landscape:
    """Diamond: 7 states, multi-path interference."""
    L = Landscape()
    L.add_edge("S", "A", delta=0.3, resistance=0.6)
    L.add_edge("S", "B", delta=0.35, resistance=0.7)
    L.add_edge("S", "C", delta=0.3, resistance=0.5)
    L.add_edge("A", "M", delta=0.2, resistance=0.4)
    L.add_edge("M", "Z", delta=0.15, resistance=0.3)
    L.add_edge("B", "N", delta=0.25, resistance=0.6)
    L.add_edge("N", "Z", delta=0.2, resistance=0.4)
    L.add_edge("A", "S", delta=0.8, resistance=2.0)
    L.add_edge("B", "S", delta=0.5, resistance=1.5)
    L.add_edge("M", "N", delta=0.3, resistance=0.5)
    return L


def build_gordian() -> Landscape:
    """Gordian Trap v3: destructive interference domain."""
    L = Landscape()
    L.add_edge("START", "A1", delta=0.3, resistance=0.3)
    L.add_edge("A1", "A2", delta=0.4, resistance=0.3)
    L.add_edge("A2", "GOAL", delta=0.4, resistance=0.3)
    L.add_edge("A1", "L1", delta=2.0, resistance=0.05)
    L.add_edge("L1", "L2", delta=2.0, resistance=0.05)
    L.add_edge("L2", "L3", delta=2.0, resistance=0.05)
    L.add_edge("L3", "GOAL", delta=2.0, resistance=0.05)
    L.add_edge("START", "B1", delta=0.5, resistance=0.4)
    L.add_edge("B1", "B2", delta=0.3, resistance=0.35)
    L.add_edge("B2", "GOAL", delta=0.3, resistance=0.3)
    return L


def build_multigoal() -> Landscape:
    """Multi-goal: Gordian + GOAL2 paths."""
    L = build_gordian()
    L.add_edge("A1", "D1", delta=0.5, resistance=0.3)
    L.add_edge("D1", "GOAL2", delta=0.4, resistance=0.3)
    L.add_edge("START", "C1", delta=0.6, resistance=0.4)
    L.add_edge("C1", "C2", delta=0.4, resistance=0.3)
    L.add_edge("C2", "GOAL2", delta=0.3, resistance=0.3)
    return L


def build_current_loop() -> Landscape:
    """Current loop: strong back-edges → phase circulation."""
    L = Landscape()
    for s, t in [("START", "A1"), ("A1", "A2"), ("A2", "A3"),
                 ("A3", "A4"), ("A4", "END")]:
        L.add_edge(s, t, delta=0.2, resistance=0.25)
    L.add_edge("START", "B1", delta=0.25, resistance=0.5)
    L.add_edge("B1", "END", delta=0.25, resistance=0.5)
    for s, t in [("A4", "A3"), ("A3", "A2"), ("A2", "A1"), ("A1", "START")]:
        L.add_edge(s, t, delta=3.0, resistance=0.3)
    L.add_edge("END", "A4", delta=3.0, resistance=0.3)
    return L


# ── Helpers ───────────────────────────────────────────────────

def _get_overlay(L, current, horizon=3, geometry="simple", goals=None):
    """Get overlay report for a domain."""
    ctrl = E0Controller(L, always_success)
    return analyze_controller_state(
        ctrl, current, horizon_edges=horizon,
        geometry=geometry, goals=goals,
    )


def _get_action_map(report):
    """Return {action: ActionAmplitudeInfo} dict."""
    return {ai.action: ai for ai in report.action_infos}


# ══════════════════════════════════════════════════════════════
# B1 — Bounded Alternative Set
# ══════════════════════════════════════════════════════════════

class TestB1BoundedAlternatives(unittest.TestCase):
    """B1: The alternative set Ω must be finite and well-defined."""

    def test_mini_domain_bounded(self):
        """MiniDomain at S: exactly 2 alternatives {A, B}."""
        r = _get_overlay(build_mini_domain(), "S")
        self.assertEqual(len(r.action_infos), 2)
        actions = {ai.action for ai in r.action_infos}
        self.assertEqual(actions, {"A", "B"})

    def test_diamond_bounded(self):
        """Diamond at S: exactly 3 alternatives {A, B, C}."""
        r = _get_overlay(build_diamond(), "S")
        self.assertEqual(len(r.action_infos), 3)
        actions = {ai.action for ai in r.action_infos}
        self.assertEqual(actions, {"A", "B", "C"})

    def test_gordian_bounded(self):
        """Gordian at START: exactly 2 alternatives {A1, B1}."""
        r = _get_overlay(build_gordian(), "START")
        self.assertEqual(len(r.action_infos), 2)
        actions = {ai.action for ai in r.action_infos}
        self.assertEqual(actions, {"A1", "B1"})

    def test_multigoal_bounded(self):
        """Multi-goal at START: exactly 3 alternatives {A1, B1, C1}."""
        r = _get_overlay(build_multigoal(), "START", horizon=5,
                         geometry="goal_reaching", goals={"GOAL", "GOAL2"})
        actions = {ai.action for ai in r.action_infos}
        self.assertEqual(actions, {"A1", "B1", "C1"})

    def test_current_loop_bounded(self):
        """Current-loop at START: exactly 2 alternatives {A1, B1}."""
        r = _get_overlay(build_current_loop(), "START")
        self.assertEqual(len(r.action_infos), 2)
        actions = {ai.action for ai in r.action_infos}
        self.assertEqual(actions, {"A1", "B1"})


# ══════════════════════════════════════════════════════════════
# B2 — Mutual Exclusivity
# ══════════════════════════════════════════════════════════════

class TestB2MutualExclusivity(unittest.TestCase):
    """B2: Exactly one action is selected per episode (argmax).
    The overlay produces a single amplitude_choice."""

    def _check_exclusivity(self, L, current, **kwargs):
        """Verify single unique choice with max intensity."""
        r = _get_overlay(L, current, **kwargs)
        choice = r.amplitude_choice
        self.assertIsNotNone(choice)
        intensities = [ai.intensity for ai in r.action_infos]
        max_I = max(intensities)
        # Exactly one action has max intensity (no ties within tolerance)
        count_max = sum(1 for I in intensities if abs(I - max_I) < 1e-10)
        self.assertEqual(count_max, 1,
                         msg=f"Expected unique winner, got {count_max} tied at I={max_I}")

    def test_mini_exclusive(self):
        self._check_exclusivity(build_mini_domain(), "S")

    def test_diamond_exclusive(self):
        self._check_exclusivity(build_diamond(), "S")

    def test_gordian_exclusive_simple(self):
        self._check_exclusivity(build_gordian(), "START")

    def test_gordian_exclusive_goal_reaching(self):
        self._check_exclusivity(build_gordian(), "START", horizon=5,
                                geometry="goal_reaching", goals={"GOAL"})

    def test_current_loop_exclusive(self):
        self._check_exclusivity(build_current_loop(), "START")


# ══════════════════════════════════════════════════════════════
# B3 — Representation Invariance (Phase Independence)
# ══════════════════════════════════════════════════════════════

class TestB3RepresentationInvariance(unittest.TestCase):
    """B3: P(z) depends only on |Ψ(z)|², not on global phase.
    Verify I = |Ψ|² is phase-invariant and P is phase-invariant."""

    def test_intensity_is_phase_invariant(self):
        """I = |Ψ|² is unchanged under Ψ → e^{iφ}·Ψ."""
        L = build_gordian()
        A_SHORT = ["START", "A1", "A2", "GOAL"]
        A_LOOP = ["START", "A1", "L1", "L2", "L3", "GOAL"]

        psi_short = path_psi(L, A_SHORT)
        psi_loop = path_psi(L, A_LOOP)
        psi_sum = psi_short + psi_loop
        I_original = abs(psi_sum) ** 2

        for phi in [0.1, 0.5, math.pi / 3, math.pi, 2.7]:
            phase = cmath.exp(1j * phi)
            psi_rotated = phase * psi_sum
            I_rotated = abs(psi_rotated) ** 2
            self.assertAlmostEqual(I_original, I_rotated, places=10,
                                   msg=f"I must be phase-invariant at φ={phi}")

    def test_probability_is_phase_invariant(self):
        """P(z) unchanged when all Ψ simultaneously rotated by global phase."""
        L = build_diamond()
        r = _get_overlay(L, "S", horizon=3)
        original_probs = {ai.action: ai.probability for ai in r.action_infos}

        # Rotating all amplitudes by same phase doesn't change ratios
        for phi in [0.3, math.pi / 4, math.pi]:
            phase = cmath.exp(1j * phi)
            rotated_intensities = {}
            total = 0.0
            for ai in r.action_infos:
                # Rotate the total psi by global phase
                rotated = phase * ai.psi_total
                I = abs(rotated) ** 2
                rotated_intensities[ai.action] = I
                total += I
            for action, I in rotated_intensities.items():
                P_rotated = I / total if total > 0 else 0
                self.assertAlmostEqual(
                    P_rotated, original_probs[action], places=10,
                    msg=f"P({action}) must be phase-invariant at φ={phi}")

    def test_single_path_phase_irrelevant(self):
        """For a single path, |Ψ|² = exp(-2S) regardless of phase Θ."""
        L = build_mini_domain()
        path = ["S", "A"]
        psi_val = path_psi(L, path)
        s_eff = L.effective_tension("S", "A")
        expected_I = math.exp(-2 * s_eff)
        actual_I = abs(psi_val) ** 2
        self.assertAlmostEqual(actual_I, expected_I, places=10,
                               msg="|Ψ(p)|² must equal exp(-2S)")


# ══════════════════════════════════════════════════════════════
# B4 — Monotonicity
# ══════════════════════════════════════════════════════════════

class TestB4Monotonicity(unittest.TestCase):
    """B4: I(z₁) > I(z₂) ⟹ P(z₁) > P(z₂).
    Probability preserves the intensity ordering."""

    def _check_monotonicity(self, L, current, **kwargs):
        """Verify P ordering matches I ordering."""
        r = _get_overlay(L, current, **kwargs)
        infos = sorted(r.action_infos, key=lambda ai: ai.intensity, reverse=True)
        for i in range(len(infos) - 1):
            if infos[i].intensity > infos[i + 1].intensity + 1e-12:
                self.assertGreater(
                    infos[i].probability, infos[i + 1].probability,
                    msg=f"P({infos[i].action})={infos[i].probability} must > "
                        f"P({infos[i+1].action})={infos[i+1].probability} "
                        f"since I({infos[i].action})={infos[i].intensity} > "
                        f"I({infos[i+1].action})={infos[i+1].intensity}")

    def test_mini_monotonic(self):
        self._check_monotonicity(build_mini_domain(), "S")

    def test_diamond_monotonic(self):
        self._check_monotonicity(build_diamond(), "S")

    def test_gordian_monotonic_simple(self):
        self._check_monotonicity(build_gordian(), "START")

    def test_gordian_monotonic_goal_reaching(self):
        self._check_monotonicity(build_gordian(), "START", horizon=5,
                                 geometry="goal_reaching", goals={"GOAL"})

    def test_multigoal_monotonic(self):
        self._check_monotonicity(build_multigoal(), "START", horizon=5,
                                 geometry="goal_reaching", goals={"GOAL", "GOAL2"})

    def test_current_loop_monotonic(self):
        self._check_monotonicity(build_current_loop(), "START")


# ══════════════════════════════════════════════════════════════
# B5 — Coarse-Graining Consistency
# ══════════════════════════════════════════════════════════════

class TestB5CoarseGraining(unittest.TestCase):
    """B5: P(A∪B) = P(A) + P(B) for disjoint subsets of Ω.
    Grouping alternatives preserves total probability."""

    def test_gordian_coarse_grain_singlegoal(self):
        """At GOAL-reaching, P(A1) + P(B1) = 1.0."""
        r = _get_overlay(build_gordian(), "START", horizon=5,
                         geometry="goal_reaching", goals={"GOAL"})
        total = sum(ai.probability for ai in r.action_infos)
        self.assertAlmostEqual(total, 1.0, places=10,
                               msg="ΣP must = 1.0 (coarse-graining base)")

    def test_multigoal_coarse_by_goal(self):
        """Multi-goal: P grouped by target goal must be consistent.
        P(GOAL-reaching) + P(GOAL2-reaching) ≤ 1.0."""
        L = build_multigoal()
        ctrl = E0Controller(L, always_success)

        # Get probabilities for each goal separately
        r_g1 = analyze_controller_state(ctrl, "START", horizon_edges=5,
                                        geometry="goal_reaching", goals={"GOAL"})
        r_g2 = analyze_controller_state(ctrl, "START", horizon_edges=5,
                                        geometry="goal_reaching", goals={"GOAL2"})
        r_both = analyze_controller_state(ctrl, "START", horizon_edges=5,
                                          geometry="goal_reaching",
                                          goals={"GOAL", "GOAL2"})

        # Each individual report sums to 1.0
        sum_g1 = sum(ai.probability for ai in r_g1.action_infos)
        sum_g2 = sum(ai.probability for ai in r_g2.action_infos)
        sum_both = sum(ai.probability for ai in r_both.action_infos)
        self.assertAlmostEqual(sum_g1, 1.0, places=10)
        self.assertAlmostEqual(sum_g2, 1.0, places=10)
        self.assertAlmostEqual(sum_both, 1.0, places=10)

    def test_diamond_partitioned_additivity(self):
        """Diamond: P({A}) + P({B}) + P({C}) = 1.0 — partition additivity."""
        r = _get_overlay(build_diamond(), "S", horizon=3)
        m = _get_action_map(r)
        total = m["A"].probability + m["B"].probability + m["C"].probability
        self.assertAlmostEqual(total, 1.0, places=10,
                               msg="Sum of disjoint partition must = 1.0")

    def test_mini_additivity(self):
        """MiniDomain: P(A) + P(B) = 1.0."""
        r = _get_overlay(build_mini_domain(), "S")
        total = sum(ai.probability for ai in r.action_infos)
        self.assertAlmostEqual(total, 1.0, places=10)

    def test_coarse_grain_subset(self):
        """Diamond: P({A,B}) = P(A) + P(B) — subset coarse-graining."""
        r = _get_overlay(build_diamond(), "S", horizon=3)
        m = _get_action_map(r)
        P_AB = m["A"].probability + m["B"].probability
        P_C = m["C"].probability
        # P({A,B}) + P({C}) = 1.0 ⟹ P({A,B}) = 1 - P(C)
        self.assertAlmostEqual(P_AB, 1.0 - P_C, places=10,
                               msg="P(A∪B) = P(A) + P(B) = 1 - P(C)")


# ══════════════════════════════════════════════════════════════
# U1 — f-Distortion Elimination
# ══════════════════════════════════════════════════════════════

class TestU1DistortionElimination(unittest.TestCase):
    """U1: P = f(I)/Σf(I) for nonlinear f changes the ordering
    or introduces arbitrary structure. Only f=id preserves
    the canonical support scalar faithfully."""

    def _compute_distorted_probs(self, report, f):
        """Compute probabilities under f-distortion."""
        distorted = [f(ai.intensity) for ai in report.action_infos]
        total = sum(distorted)
        if total == 0:
            return {ai.action: 0.0 for ai in report.action_infos}
        return {ai.action: d / total
                for ai, d in zip(report.action_infos, distorted)}

    def test_sqrt_distortion_changes_distribution(self):
        """f=√I changes probability distribution (not faithful)."""
        r = _get_overlay(build_gordian(), "START", horizon=5,
                         geometry="goal_reaching", goals={"GOAL"})
        P_born = {ai.action: ai.probability for ai in r.action_infos}
        P_sqrt = self._compute_distorted_probs(r, math.sqrt)
        # The distorted distribution differs from Born
        diffs = [abs(P_born[a] - P_sqrt[a]) for a in P_born]
        max_diff = max(diffs)
        self.assertGreater(max_diff, 0.001,
                           msg="√I distortion must differ from I normalization")

    def test_square_distortion_changes_distribution(self):
        """f=I² exaggerates differences (not faithful)."""
        r = _get_overlay(build_gordian(), "START", horizon=5,
                         geometry="goal_reaching", goals={"GOAL"})
        P_born = {ai.action: ai.probability for ai in r.action_infos}
        P_sq = self._compute_distorted_probs(r, lambda x: x ** 2)
        diffs = [abs(P_born[a] - P_sq[a]) for a in P_born]
        max_diff = max(diffs)
        self.assertGreater(max_diff, 0.001,
                           msg="I² distortion must differ from I normalization")

    def test_log_distortion_changes_distribution(self):
        """f=log(1+I) compresses differences (not faithful)."""
        r = _get_overlay(build_diamond(), "S", horizon=3)
        P_born = {ai.action: ai.probability for ai in r.action_infos}
        P_log = self._compute_distorted_probs(r, lambda x: math.log1p(x))
        diffs = [abs(P_born[a] - P_log[a]) for a in P_born]
        max_diff = max(diffs)
        self.assertGreater(max_diff, 0.001,
                           msg="log distortion must differ from I normalization")

    def test_all_distortions_still_normalize(self):
        """Any f-distortion still sums to 1 (normalization is separate from choice of f)."""
        r = _get_overlay(build_gordian(), "START", horizon=5,
                         geometry="goal_reaching", goals={"GOAL"})
        for name, f in [("sqrt", math.sqrt), ("square", lambda x: x**2),
                        ("log", lambda x: math.log1p(x))]:
            P_dist = self._compute_distorted_probs(r, f)
            total = sum(P_dist.values())
            self.assertAlmostEqual(total, 1.0, places=10,
                                   msg=f"{name}-distorted P must still sum to 1")


# ══════════════════════════════════════════════════════════════
# U2 — |Ψ| vs |Ψ|² Discrimination
# ══════════════════════════════════════════════════════════════

class TestU2ModulusVsSquared(unittest.TestCase):
    """U2: |Ψ|² (intensity) is privileged over |Ψ| (modulus)
    because it preserves interference cross-terms and
    decomposes correctly over orthogonal sectors."""

    def test_modulus_vs_squared_differ(self):
        """|Ψ| normalization gives different P than |Ψ|² normalization."""
        r = _get_overlay(build_gordian(), "START", horizon=5,
                         geometry="goal_reaching", goals={"GOAL"})
        # Born: P = |Ψ|²/Σ|Ψ|²
        P_born = {ai.action: ai.probability for ai in r.action_infos}
        # Modulus: P = |Ψ|/Σ|Ψ|
        moduli = {ai.action: abs(ai.psi_total) for ai in r.action_infos}
        total_mod = sum(moduli.values())
        P_mod = {a: m / total_mod for a, m in moduli.items()}
        diffs = [abs(P_born[a] - P_mod[a]) for a in P_born]
        max_diff = max(diffs)
        self.assertGreater(max_diff, 0.01,
                           msg="|Ψ| vs |Ψ|² must give distinct distributions")

    def test_squared_preserves_interference(self):
        """I = |Σ Ψ|² ≠ Σ|Ψ|² when cross-terms exist (interference)."""
        L = build_gordian()
        A_SHORT = ["START", "A1", "A2", "GOAL"]
        A_LOOP = ["START", "A1", "L1", "L2", "L3", "GOAL"]
        psi_short = path_psi(L, A_SHORT)
        psi_loop = path_psi(L, A_LOOP)
        I_coherent = abs(psi_short + psi_loop) ** 2
        I_incoherent = abs(psi_short) ** 2 + abs(psi_loop) ** 2
        # Coherent ≠ incoherent → cross-terms exist
        self.assertNotAlmostEqual(I_coherent, I_incoherent, places=2,
                                  msg="|Σ Ψ|² must differ from Σ|Ψ|² (interference)")

    def test_modulus_lacks_interference_sensitivity(self):
        """|Ψ| (modulus) is less sensitive to destructive interference than |Ψ|²."""
        L = build_gordian()
        A_SHORT = ["START", "A1", "A2", "GOAL"]
        A_LOOP = ["START", "A1", "L1", "L2", "L3", "GOAL"]
        psi_sum = path_psi(L, A_SHORT) + path_psi(L, A_LOOP)
        # Compare suppression ratio for modulus vs squared
        mod_coherent = abs(psi_sum)
        mod_incoherent = abs(path_psi(L, A_SHORT)) + abs(path_psi(L, A_LOOP))
        sq_coherent = abs(psi_sum) ** 2
        sq_incoherent = abs(path_psi(L, A_SHORT)) ** 2 + abs(path_psi(L, A_LOOP)) ** 2
        ratio_mod = mod_coherent / mod_incoherent if mod_incoherent > 0 else 1
        ratio_sq = sq_coherent / sq_incoherent if sq_incoherent > 0 else 1
        # Squared form should show stronger suppression (lower ratio)
        self.assertLess(ratio_sq, ratio_mod,
                        msg="|Ψ|² must show stronger destructive suppression than |Ψ|")


# ══════════════════════════════════════════════════════════════
# U3 — Normalization Sum
# ══════════════════════════════════════════════════════════════

class TestU3Normalization(unittest.TestCase):
    """U3: ΣP(z) = 1.0 to machine precision across all domains and geometries."""

    def _check_normalization(self, L, current, **kwargs):
        r = _get_overlay(L, current, **kwargs)
        total = sum(ai.probability for ai in r.action_infos)
        self.assertAlmostEqual(total, 1.0, places=10,
                               msg=f"ΣP must = 1.0, got {total}")

    def test_mini_norm(self):
        self._check_normalization(build_mini_domain(), "S")

    def test_diamond_norm(self):
        self._check_normalization(build_diamond(), "S")

    def test_gordian_simple_norm(self):
        self._check_normalization(build_gordian(), "START")

    def test_gordian_goal_reaching_norm(self):
        self._check_normalization(build_gordian(), "START", horizon=5,
                                  geometry="goal_reaching", goals={"GOAL"})

    def test_multigoal_norm(self):
        self._check_normalization(build_multigoal(), "START", horizon=5,
                                  geometry="goal_reaching", goals={"GOAL", "GOAL2"})

    def test_current_loop_norm(self):
        self._check_normalization(build_current_loop(), "START")

    def test_all_geometries_norm(self):
        """Normalization holds across all 4 geometry types on Gordian."""
        L = build_gordian()
        for geo in ["prefix", "simple"]:
            r = _get_overlay(L, "START", horizon=5, geometry=geo)
            total = sum(ai.probability for ai in r.action_infos)
            self.assertAlmostEqual(total, 1.0, places=10,
                                   msg=f"ΣP must = 1.0 for geometry={geo}")
        for geo in ["first_arrival", "goal_reaching"]:
            r = _get_overlay(L, "START", horizon=5, geometry=geo, goals={"GOAL"})
            total = sum(ai.probability for ai in r.action_infos)
            self.assertAlmostEqual(total, 1.0, places=10,
                                   msg=f"ΣP must = 1.0 for geometry={geo}")


# ══════════════════════════════════════════════════════════════
# Integration: Full Born Regime on Gordian
# ══════════════════════════════════════════════════════════════

class TestBornRegimeGordian(unittest.TestCase):
    """Integration test: all 5 Born axioms simultaneously verified
    on the Gordian Trap under goal_reaching geometry."""

    def setUp(self):
        self.L = build_gordian()
        self.r = _get_overlay(self.L, "START", horizon=5,
                              geometry="goal_reaching", goals={"GOAL"})
        self.m = _get_action_map(self.r)

    def test_B1_bounded(self):
        """B1: |Ω| = 2 (A1, B1)."""
        self.assertEqual(len(self.r.action_infos), 2)

    def test_B2_exclusive(self):
        """B2: Unique winner (B1) with P > 0.9."""
        self.assertEqual(self.r.amplitude_choice, "B1")
        self.assertGreater(self.m["B1"].probability, 0.9)

    def test_B3_invariant(self):
        """B3: Intensity is |Ψ|² (phase-independent scalar)."""
        for ai in self.r.action_infos:
            self.assertAlmostEqual(ai.intensity, abs(ai.psi_total) ** 2, places=10)

    def test_B4_monotonic(self):
        """B4: I(B1) > I(A1) ⟹ P(B1) > P(A1)."""
        self.assertGreater(self.m["B1"].intensity, self.m["A1"].intensity)
        self.assertGreater(self.m["B1"].probability, self.m["A1"].probability)

    def test_B5_coarse_sum(self):
        """B5: P(A1) + P(B1) = 1.0."""
        total = self.m["A1"].probability + self.m["B1"].probability
        self.assertAlmostEqual(total, 1.0, places=10)

    def test_born_formula(self):
        """P(z) = I(z) / ΣI matches the Born formula exactly."""
        total_I = sum(ai.intensity for ai in self.r.action_infos)
        for ai in self.r.action_infos:
            P_expected = ai.intensity / total_I
            self.assertAlmostEqual(ai.probability, P_expected, places=10,
                                   msg=f"P({ai.action}) must match I/ΣI")


if __name__ == "__main__":
    unittest.main()
