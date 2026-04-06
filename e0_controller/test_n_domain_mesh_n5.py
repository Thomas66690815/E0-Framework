"""
C180 — N-Domain Mesh Tests (N=5: EN + DE + ONTO + COOK + PROJ)

Tests for 5-domain mesh with curriculum-trained canon landscapes
and bootstrapped workflow landscapes.

Key findings validated:
  - EN↔DE cluster persists from N=3
  - COOK↔PROJ form a second cluster (same topology: 10n/13e)
  - ONTO acts as bridge node (compat shifts >1.0 post-navigation)
  - DE stays isolated from bootstrapped domains
"""

import pytest
from itertools import combinations

from e0_controller.bootstrapper import bootstrap_landscape
from e0_controller.controller import E0Controller, HybridMode
from e0_controller.coupling_router import (
    CouplingRouter,
    Universe,
    update_weights_from_dream,
)
from e0_controller.curriculum import CurriculumRunner
from e0_controller.dream_mode import (
    DreamObserver,
    dream_compatibility,
)
from e0_controller.primitives import Outcome
from e0_controller.explore_n_domain_mesh_n5 import (
    build_cooking_landscape,
    build_project_landscape,
)


EXEC_FN = lambda s, t: Outcome.SUCCESS

CANON_DOMAINS = [
    ("EN",   "english_basic_enriched",  "thing",      "self"),
    ("DE",   "german_basic_enriched",   "ding",       "selbst"),
    ("ONTO", "ontodynamics",            "difference", "negative_necessity"),
]

BOOTSTRAP_DOMAINS = [
    ("COOK", build_cooking_landscape, "PLANNING", "SERVING"),
    ("PROJ", build_project_landscape, "PLANNING", "DEPLOYMENT"),
]

ALL_LABELS = [c[0] for c in CANON_DOMAINS] + [b[0] for b in BOOTSTRAP_DOMAINS]
COMPATIBILITY_THRESHOLD = 0.6


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def all_landscapes():
    """Prepare all 5 domain landscapes."""
    result = {}

    # Canon: curriculum-trained
    for label, canon, start, goal in CANON_DOMAINS:
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

    # Bootstrapped
    for label, builder_fn, start, goal in BOOTSTRAP_DOMAINS:
        result[label] = {
            "landscape": builder_fn(),
            "start": start,
            "goal": goal,
        }

    return result


@pytest.fixture(scope="module")
def mesh_n5(all_landscapes):
    """Build DreamObserver + CouplingRouter + Controllers for N=5."""
    observer = DreamObserver(
        readiness_threshold=0.0,
        node_equivalence_method="hungarian",
        compatibility_threshold=COMPATIBILITY_THRESHOLD,
    )
    universes = []
    controllers = {}
    for label in ALL_LABELS:
        info = all_landscapes[label]
        L = info["landscape"]
        observer.register(label, L)
        ctrl = E0Controller(L, EXEC_FN, hybrid_mode=HybridMode.GREEDY)
        controllers[label] = ctrl
        universes.append(Universe(
            name=label, landscape=L,
            execute_fn=EXEC_FN, start=info["start"], goal=info["goal"],
        ))
    router = CouplingRouter(universes)
    return observer, router, controllers


@pytest.fixture(scope="module")
def after_episodes(mesh_n5, all_landscapes):
    """Run 4 episodes and return final dream result."""
    observer, router, controllers = mesh_n5
    for _ in range(4):
        for label in ALL_LABELS:
            info = all_landscapes[label]
            controllers[label].run(info["start"], max_cycles=20, goal=info["goal"])
        observer.dream_cycle()
        update_weights_from_dream(router, observer)
    return observer, router


# ── Bootstrap Domain Tests ───────────────────────────────────────────

class TestBootstrapDomains:
    """C180: Bootstrapped landscape structure."""

    def test_cook_has_10_nodes(self):
        L = build_cooking_landscape()
        assert len(L.states) == 10

    def test_cook_has_13_edges(self):
        L = build_cooking_landscape()
        assert len(L.edges) == 13

    def test_proj_has_10_nodes(self):
        L = build_project_landscape()
        assert len(L.states) == 10

    def test_proj_has_13_edges(self):
        L = build_project_landscape()
        assert len(L.edges) == 13

    def test_cook_start_node_exists(self):
        L = build_cooking_landscape()
        assert "PLANNING" in L.states

    def test_cook_goal_node_exists(self):
        L = build_cooking_landscape()
        assert "SERVING" in L.states

    def test_proj_start_node_exists(self):
        L = build_project_landscape()
        assert "PLANNING" in L.states

    def test_proj_goal_node_exists(self):
        L = build_project_landscape()
        assert "DEPLOYMENT" in L.states


# ── Pre-Navigation Compatibility ─────────────────────────────────────

class TestPreNavCompatibility:
    """C180: Compatibility matrix before navigation (10 pairs)."""

    def test_en_de_compatible(self, all_landscapes):
        score = dream_compatibility(
            all_landscapes["EN"]["landscape"],
            all_landscapes["DE"]["landscape"])
        assert score < COMPATIBILITY_THRESHOLD

    def test_cook_proj_compatible(self, all_landscapes):
        score = dream_compatibility(
            all_landscapes["COOK"]["landscape"],
            all_landscapes["PROJ"]["landscape"])
        assert score < COMPATIBILITY_THRESHOLD

    def test_cook_proj_very_close(self, all_landscapes):
        """Same topology → very low score (< 0.3)."""
        score = dream_compatibility(
            all_landscapes["COOK"]["landscape"],
            all_landscapes["PROJ"]["landscape"])
        assert score < 0.3

    def test_en_onto_incompatible_pre_nav(self, all_landscapes):
        score = dream_compatibility(
            all_landscapes["EN"]["landscape"],
            all_landscapes["ONTO"]["landscape"])
        assert score > COMPATIBILITY_THRESHOLD

    def test_cross_family_all_incompatible(self, all_landscapes):
        """All canon↔bootstrapped pairs incompatible pre-navigation."""
        cross = [("EN", "COOK"), ("EN", "PROJ"),
                 ("DE", "COOK"), ("DE", "PROJ"),
                 ("ONTO", "COOK"), ("ONTO", "PROJ")]
        for a, b in cross:
            score = dream_compatibility(
                all_landscapes[a]["landscape"],
                all_landscapes[b]["landscape"])
            assert score > COMPATIBILITY_THRESHOLD, f"{a}↔{b} = {score}"

    def test_exactly_2_compatible_pairs(self, all_landscapes):
        """Pre-navigation: only EN↔DE and COOK↔PROJ compatible."""
        compatible = []
        labels = list(all_landscapes.keys())
        for a, b in combinations(labels, 2):
            score = dream_compatibility(
                all_landscapes[a]["landscape"],
                all_landscapes[b]["landscape"])
            if score < COMPATIBILITY_THRESHOLD:
                compatible.append(f"{a}↔{b}")
        assert len(compatible) == 2
        assert "EN↔DE" in compatible
        assert "COOK↔PROJ" in compatible


# ── Dream Cycle N=5 ──────────────────────────────────────────────────

class TestDreamCycleN5:
    """C180: Dream cycle with 5 domains."""

    def test_observer_has_5_domains(self, mesh_n5):
        observer, _, _ = mesh_n5
        assert len(observer._domains) == 5

    def test_dream_cycle_finds_equivalences(self, mesh_n5):
        observer, _, _ = mesh_n5
        result = observer.dream_cycle()
        assert result.equivalences_found > 0

    def test_en_de_equivalences_present(self, after_episodes):
        observer, _ = after_episodes
        eqs = observer.equivalences_for("EN")
        de_eqs = [e for e in eqs if e["partner_state"].startswith("DE:")]
        assert len(de_eqs) > 0

    def test_cook_proj_equivalences_present(self, after_episodes):
        observer, _ = after_episodes
        eqs = observer.equivalences_for("COOK")
        proj_eqs = [e for e in eqs if e["partner_state"].startswith("PROJ:")]
        assert len(proj_eqs) > 0

    def test_de_cook_no_equivalences(self, after_episodes):
        """DE has no equivalences with COOK."""
        observer, _ = after_episodes
        eqs = observer.equivalences_for("DE")
        cook_eqs = [e for e in eqs if e["partner_state"].startswith("COOK:")]
        assert len(cook_eqs) == 0

    def test_de_proj_no_equivalences(self, after_episodes):
        """DE has no equivalences with PROJ."""
        observer, _ = after_episodes
        eqs = observer.equivalences_for("DE")
        proj_eqs = [e for e in eqs if e["partner_state"].startswith("PROJ:")]
        assert len(proj_eqs) == 0


# ── Coupling Router N=5 ─────────────────────────────────────────────

class TestCouplingRouterN5:
    """C180: CouplingRouter with 5 universes."""

    def test_router_has_5_universes(self, mesh_n5):
        _, router, _ = mesh_n5
        assert len(router.universes) == 5

    def test_initial_weights_all_1(self, mesh_n5):
        _, router, _ = mesh_n5
        for label in ALL_LABELS:
            assert router.get_weight(label) == 1.0


# ── ONTO Bridge Effect ──────────────────────────────────────────────

class TestOntoBridge:
    """C180: ONTO becomes bridge between canon and bootstrapped clusters."""

    def test_onto_cook_equivalences_emerge(self, after_episodes):
        """ONTO↔COOK equivalences appear after navigation."""
        observer, _ = after_episodes
        eqs = observer.equivalences_for("ONTO")
        cook_eqs = [e for e in eqs if e["partner_state"].startswith("COOK:")]
        assert len(cook_eqs) > 0

    def test_onto_proj_equivalences_emerge(self, after_episodes):
        """ONTO↔PROJ equivalences appear after navigation."""
        observer, _ = after_episodes
        eqs = observer.equivalences_for("ONTO")
        proj_eqs = [e for e in eqs if e["partner_state"].startswith("PROJ:")]
        assert len(proj_eqs) > 0

    def test_onto_compat_shift_cook(self, all_landscapes, after_episodes):
        """ONTO↔COOK compatibility drops post-navigation."""
        score = dream_compatibility(
            all_landscapes["ONTO"]["landscape"],
            all_landscapes["COOK"]["landscape"])
        # Pre-nav was ~1.65, post-nav should be < 0.6
        assert score < COMPATIBILITY_THRESHOLD

    def test_onto_compat_shift_proj(self, all_landscapes, after_episodes):
        """ONTO↔PROJ compatibility drops post-navigation."""
        score = dream_compatibility(
            all_landscapes["ONTO"]["landscape"],
            all_landscapes["PROJ"]["landscape"])
        assert score < COMPATIBILITY_THRESHOLD


# ── Integration: Full Episode Cycle ─────────────────────────────────

class TestEpisodeCycleN5:
    """C180: Full episode cycle with 5 domains."""

    def test_episode_cycle_runs(self, mesh_n5, all_landscapes):
        """One cycle (wake → dream → weight update) completes."""
        observer, router, controllers = mesh_n5
        for label in ALL_LABELS:
            info = all_landscapes[label]
            controllers[label].run(info["start"], max_cycles=10, goal=info["goal"])
        result = observer.dream_cycle()
        assert result.equivalences_found >= 0
        report = update_weights_from_dream(router, observer)
        assert report is not None

    def test_two_clusters_form(self, after_episodes):
        """Both EN↔DE and COOK↔PROJ clusters have equivalences."""
        observer, _ = after_episodes
        en_eqs = observer.equivalences_for("EN")
        de_count = sum(1 for e in en_eqs if e["partner_state"].startswith("DE:"))
        cook_eqs = observer.equivalences_for("COOK")
        proj_count = sum(1 for e in cook_eqs if e["partner_state"].startswith("PROJ:"))
        assert de_count > 0, "EN↔DE cluster missing"
        assert proj_count > 0, "COOK↔PROJ cluster missing"
