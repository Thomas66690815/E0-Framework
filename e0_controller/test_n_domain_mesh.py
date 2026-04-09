"""
C179 — N-Domain Mesh Tests (N=3: EN + DE + ONTO)

Tests for the integration of DreamObserver + CouplingRouter + SleepWakeCycle
across 3 canon domains with compatibility-gated dreaming.
"""

import pytest

from e0_controller.canon_loader import load_canon
from e0_controller.controller import E0Controller, HybridMode
from e0_controller.coupling_router import (
    CouplingRouter,
    CouplingReason,
    Universe,
    update_weights_from_dream,
)
from e0_controller.curriculum import CurriculumRunner
from e0_controller.dream_mode import (
    DreamObserver,
    dream_compatibility,
)
from e0_controller.primitives import Outcome


EXEC_FN = lambda s, t: Outcome.SUCCESS

CANONS = [
    ("EN",   "english_basic_enriched",  "thing",      "self"),
    ("DE",   "german_basic_enriched",   "ding",       "selbst"),
    ("ONTO", "ontodynamics",            "difference", "negative_necessity"),
]


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def trained_landscapes():
    """Curriculum-trained landscapes for all 3 domains."""
    result = {}
    for label, canon, start, goal in CANONS:
        runner = CurriculumRunner(
            canon, EXEC_FN,
            equilibrium_threshold=2.0,
            equilibrium_patience=3,
            max_episodes_per_turn=15,
            max_cycles_per_episode=40,
        )
        runner.run()
        result[label] = {
            "landscape": runner.final_landscape,
            "start": start,
            "goal": goal,
        }
    return result


@pytest.fixture(scope="module")
def mesh_components(trained_landscapes):
    """Build DreamObserver + CouplingRouter + Controllers."""
    observer = DreamObserver(
        readiness_threshold=0.0,
        node_equivalence_method="hungarian",
        compatibility_threshold=0.6,
    )
    universes = []
    controllers = {}
    for label, _, start, goal in CANONS:
        L = trained_landscapes[label]["landscape"]
        observer.register(label, L)
        ctrl = E0Controller(L, EXEC_FN, hybrid_mode=HybridMode.GREEDY)
        controllers[label] = ctrl
        universes.append(Universe(
            name=label, landscape=L,
            execute_fn=EXEC_FN, start=start, goal=goal,
        ))
    router = CouplingRouter(universes)
    return observer, router, controllers


# ── Compatibility Tests ──────────────────────────────────────────────

class TestCompatibilityMatrix:
    """C179: Pairwise dream compatibility for 3 canon domains."""

    def test_en_de_compatible(self, trained_landscapes):
        """EN↔DE are structurally compatible (score < 0.6)."""
        score = dream_compatibility(
            trained_landscapes["EN"]["landscape"],
            trained_landscapes["DE"]["landscape"],
        )
        assert score < 0.6

    def test_en_onto_compatible_with_v3(self, trained_landscapes):
        """EN↔ONTO are compatible with v3.0 ontodynamics (score < 0.6)."""
        score = dream_compatibility(
            trained_landscapes["EN"]["landscape"],
            trained_landscapes["ONTO"]["landscape"],
        )
        assert score < 0.6

    def test_de_onto_incompatible(self, trained_landscapes):
        """DE↔ONTO are incompatible (score > 0.6)."""
        score = dream_compatibility(
            trained_landscapes["DE"]["landscape"],
            trained_landscapes["ONTO"]["landscape"],
        )
        assert score > 0.6

    def test_en_de_closest_pair(self, trained_landscapes):
        """EN↔DE is the closest pair (lowest compatibility score)."""
        scores = {}
        labels = ["EN", "DE", "ONTO"]
        for i, a in enumerate(labels):
            for b in labels[i + 1:]:
                scores[f"{a}↔{b}"] = dream_compatibility(
                    trained_landscapes[a]["landscape"],
                    trained_landscapes[b]["landscape"],
                )
        closest = min(scores, key=scores.get)
        assert closest == "EN↔DE"


# ── Dream Cycle Tests ────────────────────────────────────────────────

class TestDreamCycleN3:
    """C179: Dream cycle with 3 domains and compatibility gating."""

    def test_en_de_equivalences_found(self, mesh_components):
        """EN↔DE produces dream equivalences."""
        observer, _, _ = mesh_components
        result = observer.dream_cycle()
        assert result.equivalences_found > 0

    def test_de_onto_skipped(self, mesh_components):
        """DE↔ONTO is compatibility-skipped."""
        observer, _, _ = mesh_components
        result = observer.dream_cycle()
        skipped_labels = [(a, b) for a, b in result.compatibility_skipped]
        assert ("DE", "ONTO") in skipped_labels

    def test_en_de_has_edge_equivalences(self, mesh_components):
        """EN has edge equivalences with DE partner."""
        observer, _, _ = mesh_components
        observer.dream_cycle()
        eqs = observer.equivalences_for("EN")
        de_eqs = [e for e in eqs if e["partner_state"].startswith("DE:")]
        assert len(de_eqs) > 0

    def test_de_onto_no_equivalences(self, mesh_components):
        """DE has 0 edge equivalences with ONTO partner."""
        observer, _, _ = mesh_components
        observer.dream_cycle()
        eqs = observer.equivalences_for("DE")
        onto_eqs = [e for e in eqs if e["partner_state"].startswith("ONTO:")]
        assert len(onto_eqs) == 0


# ── Coupling Router Tests ────────────────────────────────────────────

class TestCouplingRouterN3:
    """C179: CouplingRouter with 3 domains."""

    def test_router_has_3_universes(self, mesh_components):
        _, router, _ = mesh_components
        assert len(router.universes) == 3

    def test_initial_weights_equal(self, mesh_components):
        _, router, _ = mesh_components
        for label, *_ in CANONS:
            assert router.get_weight(label) == 1.0

    def test_recovery_selection(self, mesh_components):
        """Recovery selects a partner (any of the 3)."""
        _, router, _ = mesh_components
        en_universe = router.universes["EN"]
        partners = router.select_partner(en_universe, CouplingReason.RECOVERY)
        assert len(partners) >= 1

    def test_exploration_selection(self, mesh_components):
        """Exploration selects a partner."""
        _, router, _ = mesh_components
        en_universe = router.universes["EN"]
        partners = router.select_partner(en_universe, CouplingReason.EXPLORATION)
        assert len(partners) >= 1


# ── Integration: Episode Cycle ───────────────────────────────────────

class TestEpisodeCycle:
    """C179: Full episode cycle (wake → dream → weight update)."""

    def test_episode_cycle_runs(self, mesh_components, trained_landscapes):
        """One full episode cycle completes without error."""
        observer, router, controllers = mesh_components

        # Wake: run each controller
        for label, _, start, goal in CANONS:
            controllers[label].run(start, max_cycles=10, goal=goal)

        # Sleep: dream
        result = observer.dream_cycle()
        assert result.equivalences_found >= 0

        # Weight update
        report = update_weights_from_dream(router, observer)
        assert report is not None

    def test_en_de_equivalences_increase_over_episodes(
            self, trained_landscapes):
        """EN↔DE equivalences grow with episodes."""
        observer = DreamObserver(
            readiness_threshold=0.0,
            node_equivalence_method="hungarian",
            compatibility_threshold=0.6,
        )
        controllers = {}
        for label, _, start, goal in CANONS:
            L = trained_landscapes[label]["landscape"]
            observer.register(label, L)
            controllers[label] = E0Controller(
                L, EXEC_FN, hybrid_mode=HybridMode.GREEDY)

        counts = []
        for _ in range(3):
            for label, _, start, goal in CANONS:
                controllers[label].run(start, max_cycles=10, goal=goal)
            observer.dream_cycle()
            eqs = observer.equivalences_for("EN")
            de_count = sum(1 for e in eqs
                           if e["partner_state"].startswith("DE:"))
            counts.append(de_count)

        # Equivalences should be non-decreasing (dream landscape accumulates)
        assert counts[-1] >= counts[0]
        assert counts[0] > 0
