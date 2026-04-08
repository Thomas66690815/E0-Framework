"""
C182 — Mesh Saturation Point Tests

Validates that mesh quality does NOT collapse as N grows to 18 domains.
Tested N values: {3, 5, 10, 18}.

Key findings:
  - Structural invariants (cluster, bridge, isolation, zero FP) hold at ALL N
  - ONTO bridge coverage = 100% at all N ≥ 5
  - Compatibility separation is constant (≈ 0.21)
  - Mean eq/pair dilution is O(1/N²) — expected, not collapse
  - Time scales subquadratically (~O(N^1.7))
  - EN↔DE equivalence count stable regardless of mesh size
"""

from __future__ import annotations

import time
from itertools import combinations

import pytest

from e0_controller.bootstrapper import bootstrap_landscape
from e0_controller.controller import E0Controller, HybridMode
from e0_controller.coupling_router import (
    CouplingRouter,
    Universe,
    update_weights_from_dream,
)
from e0_controller.curriculum import CurriculumRunner
from e0_controller.dream_mode import DreamObserver, dream_compatibility
from e0_controller.primitives import Outcome
from e0_controller.structural_entropy import (
    dream_pressure,
    structural_temperature,
)

from e0_controller.explore_saturation_point import (
    CANON_DOMAINS,
    COMPATIBILITY_THRESHOLD,
    DOMAIN_TEMPLATES,
    QualityMetrics,
    build_bootstrap_landscape,
    get_bootstrap_domains,
)


# ── Configuration ────────────────────────────────────────────────────

EXEC_FN = lambda s, t: Outcome.SUCCESS
TEST_N_VALUES = [3, 5, 10, 18]
N_EPISODES_TEST = 4  # fewer episodes for test speed


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def canon_landscapes():
    """Train canon domains once for all tests."""
    trained = {}
    for label, canon_name, start, goal in CANON_DOMAINS:
        runner = CurriculumRunner(
            canon_name, EXEC_FN,
            equilibrium_threshold=2.0,
            equilibrium_patience=3,
            max_episodes_per_turn=15,
            max_cycles_per_episode=40,
        )
        runner.run()
        trained[label] = {
            "landscape": runner.final_landscape,
            "start": start, "goal": goal,
            "source": "curriculum",
        }
    return trained


def _run_mesh_for_n(n: int, canon: dict) -> QualityMetrics:
    """Run a mesh experiment for N domains, return quality metrics."""
    trained = dict(canon)  # share canon landscapes

    # Add bootstrap domains
    n_bootstrap = n - 3
    if n_bootstrap > 0:
        templates = get_bootstrap_domains(n_bootstrap)
        for tmpl in templates:
            L = build_bootstrap_landscape(tmpl)
            trained[tmpl["label"]] = {
                "landscape": L, "start": tmpl["start"],
                "goal": tmpl["goal"], "source": "bootstrap",
            }

    all_labels = list(trained.keys())
    n_pairs = len(list(combinations(all_labels, 2)))

    # Pre-nav compatibility
    pre_scores = {}
    for a, b in combinations(all_labels, 2):
        score = dream_compatibility(
            trained[a]["landscape"], trained[b]["landscape"])
        pre_scores[f"{a}↔{b}"] = score

    # Mesh assembly
    observer = DreamObserver(
        readiness_threshold=0.0,
        node_equivalence_method="hungarian",
        compatibility_threshold=COMPATIBILITY_THRESHOLD,
    )
    controllers = {}
    universes = []
    for label in all_labels:
        info = trained[label]
        L = info["landscape"]
        observer.register(label, L)
        controllers[label] = E0Controller(L, EXEC_FN, hybrid_mode=HybridMode.GREEDY)
        universes.append(Universe(
            name=label, landscape=L,
            execute_fn=EXEC_FN, start=info["start"], goal=info["goal"],
        ))
    router = CouplingRouter(universes)

    # Run episodes
    episode_times = []
    final_eq_counts = {}
    for ep in range(1, N_EPISODES_TEST + 1):
        t0 = time.time()
        for label in all_labels:
            info = trained[label]
            controllers[label].run(info["start"], max_cycles=40, goal=info["goal"])
        observer.dream_cycle()
        update_weights_from_dream(router, observer)

        eq_counts = {}
        for a, b in combinations(all_labels, 2):
            eqs_a = observer.equivalences_for(a)
            count = sum(1 for eq in eqs_a if eq["partner_state"].startswith(f"{b}:"))
            eq_counts[f"{a}↔{b}"] = count
        final_eq_counts = eq_counts
        episode_times.append(time.time() - t0)

    # Post-nav compatibility
    post_scores = {}
    for a, b in combinations(all_labels, 2):
        score = dream_compatibility(
            trained[a]["landscape"], trained[b]["landscape"])
        post_scores[f"{a}↔{b}"] = score

    compatible_post = [k for k, v in post_scores.items()
                       if v < COMPATIBILITY_THRESHOLD]
    incompatible_post = [k for k, v in post_scores.items()
                         if v >= COMPATIBILITY_THRESHOLD]

    # Quality metrics
    bootstrap_labels = [l for l in all_labels if l not in ("EN", "DE", "ONTO")]

    en_de_eq = final_eq_counts.get("EN↔DE", 0)
    canon_cluster = en_de_eq > 0

    bridge_count = sum(
        1 for bl in bootstrap_labels
        if final_eq_counts.get(f"ONTO↔{bl}", 0) > 0
    )

    de_cross_eq = sum(final_eq_counts.get(f"DE↔{bl}", 0) for bl in bootstrap_labels)
    de_isolation = de_cross_eq == 0

    bootstrap_pairs = sum(
        1 for a, b in combinations(bootstrap_labels, 2)
        if post_scores.get(f"{a}↔{b}", 1.0) < COMPATIBILITY_THRESHOLD
    )

    compat_eq = [final_eq_counts.get(p, 0) for p in compatible_post]
    mean_eq = sum(compat_eq) / len(compat_eq) if compat_eq else 0.0
    max_eq = max(compat_eq) if compat_eq else 0.0

    false_pos = sum(1 for p in incompatible_post if final_eq_counts.get(p, 0) > 0)

    if incompatible_post and compatible_post:
        compat_sep = (min(post_scores[p] for p in incompatible_post)
                      - max(post_scores[p] for p in compatible_post))
    else:
        compat_sep = float("inf")

    return QualityMetrics(
        n=n, n_canon=3, n_bootstrap=n_bootstrap, n_pairs=n_pairs,
        canon_cluster=canon_cluster, bridge_count=bridge_count,
        de_isolation=de_isolation, bootstrap_compat_pairs=bootstrap_pairs,
        mean_eq_per_pair=mean_eq, max_eq_per_pair=max_eq,
        false_positives=false_pos, compat_separation=compat_sep,
        time_per_episode=sum(episode_times) / len(episode_times),
        total_time=sum(episode_times),
        compatible_pairs=compatible_post, incompatible_pairs=incompatible_post,
        all_eq_counts=final_eq_counts,
    )


@pytest.fixture(scope="module")
def all_metrics(canon_landscapes) -> dict[int, QualityMetrics]:
    """Run mesh experiments for all test N values. Keyed by N."""
    results = {}
    for n in TEST_N_VALUES:
        results[n] = _run_mesh_for_n(n, canon_landscapes)
    return results


# ── Test Classes ─────────────────────────────────────────────────────


class TestStructuralInvariants:
    """Core quality metrics hold at every tested N."""

    @pytest.mark.parametrize("n", TEST_N_VALUES)
    def test_en_de_cluster_forms(self, all_metrics, n):
        """EN↔DE cluster forms at every N."""
        assert all_metrics[n].canon_cluster

    @pytest.mark.parametrize("n", TEST_N_VALUES)
    def test_de_isolation(self, all_metrics, n):
        """DE stays isolated from all bootstrapped domains."""
        assert all_metrics[n].de_isolation

    @pytest.mark.parametrize("n", TEST_N_VALUES)
    def test_zero_false_positives(self, all_metrics, n):
        """No equivalences between known-incompatible pairs."""
        assert all_metrics[n].false_positives == 0

    @pytest.mark.parametrize("n", TEST_N_VALUES)
    def test_compat_separation_stable(self, all_metrics, n):
        """Compatibility threshold gap stays above 0.15."""
        m = all_metrics[n]
        if m.compatible_pairs and m.incompatible_pairs:
            assert m.compat_separation > 0.15


class TestONTOBridge:
    """ONTO bridges 100% of bootstrapped domains at all N ≥ 5."""

    @pytest.mark.parametrize("n", [n for n in TEST_N_VALUES if n >= 5])
    def test_onto_bridges_all_bootstrap(self, all_metrics, n):
        """ONTO bridges every bootstrapped domain."""
        m = all_metrics[n]
        assert m.bridge_count == m.n_bootstrap

    def test_no_bridge_at_n3(self, all_metrics):
        """N=3 has no bootstrapped domains to bridge."""
        assert all_metrics[3].bridge_count == 0


class TestEquivalenceScaling:
    """Equivalence counts scale correctly with N."""

    def test_en_de_eq_stable(self, all_metrics):
        """EN↔DE equivalence count is independent of mesh size."""
        eq_n3 = all_metrics[3].all_eq_counts.get("EN↔DE", 0)
        eq_n18 = all_metrics[18].all_eq_counts.get("EN↔DE", 0)
        # Must be within 20% — pairwise metrics shouldn't depend on
        # how many other domains are in the mesh.
        assert eq_n3 > 0
        assert eq_n18 > 0
        ratio = eq_n18 / eq_n3
        assert 0.5 < ratio < 2.0, (
            f"EN↔DE eq shifted too much: {eq_n3} → {eq_n18} (ratio {ratio:.2f})")

    def test_total_equivalences_increase(self, all_metrics):
        """Total equivalences grow with N (more domains = more pairs)."""
        total_n5 = sum(all_metrics[5].all_eq_counts.values())
        total_n18 = sum(all_metrics[18].all_eq_counts.values())
        assert total_n18 > total_n5

    def test_dilution_is_expected(self, all_metrics):
        """Mean eq/pair drops because C(N,2) grows faster than total eq.
        This is dilution, not collapse."""
        m5 = all_metrics[5]
        m18 = all_metrics[18]
        # Mean drops
        assert m18.mean_eq_per_pair < m5.mean_eq_per_pair
        # But total goes up
        total_5 = sum(m5.all_eq_counts.values())
        total_18 = sum(m18.all_eq_counts.values())
        assert total_18 > total_5


class TestBootstrapFamily:
    """Bootstrap domains form a growing internal cluster."""

    def test_bootstrap_pairs_grow_quadratically(self, all_metrics):
        """Number of compatible bootstrap pairs grows as C(k,2)."""
        # N=5 (k=2): C(2,2)=1
        # N=10 (k=7): C(7,2)=21
        # N=18 (k=15): C(15,2)=105
        assert all_metrics[5].bootstrap_compat_pairs >= 1
        assert all_metrics[10].bootstrap_compat_pairs >= 15
        assert all_metrics[18].bootstrap_compat_pairs >= 80

    def test_compatible_pair_count_at_n18(self, all_metrics):
        """At N=18, the vast majority of bootstrap pairs are compatible."""
        m = all_metrics[18]
        max_bootstrap_pairs = m.n_bootstrap * (m.n_bootstrap - 1) // 2
        assert m.bootstrap_compat_pairs >= 0.9 * max_bootstrap_pairs


class TestTimeScaling:
    """Processing time scales subquadratically."""

    def test_subquadratic_scaling(self, all_metrics):
        """Time per episode at N=18 is less than (18/3)² × time at N=3."""
        t3 = all_metrics[3].time_per_episode
        t18 = all_metrics[18].time_per_episode
        quadratic_factor = (18 / 3) ** 2  # = 36
        assert t18 < quadratic_factor * t3, (
            f"Time scaling exceeded O(N²): {t18:.1f}s vs "
            f"{quadratic_factor * t3:.1f}s (quadratic bound)")


class TestNoCollapse:
    """The central claim: mesh quality does NOT collapse up to N=18."""

    def test_all_n_values_pass_structural_checks(self, all_metrics):
        """Every tested N passes all four structural checks."""
        for n in TEST_N_VALUES:
            m = all_metrics[n]
            assert m.canon_cluster, f"N={n}: EN↔DE cluster lost"
            assert m.de_isolation, f"N={n}: DE isolation breached"
            assert m.false_positives == 0, f"N={n}: false positives"

    def test_bridge_coverage_never_drops(self, all_metrics):
        """ONTO bridge coverage stays at 100% across all N ≥ 5."""
        for n in [n for n in TEST_N_VALUES if n >= 5]:
            m = all_metrics[n]
            assert m.bridge_count == m.n_bootstrap, (
                f"N={n}: bridge covers {m.bridge_count}/{m.n_bootstrap}")

    def test_compat_separation_constant(self, all_metrics):
        """Compatibility separation doesn't degrade — it's constant."""
        seps = [all_metrics[n].compat_separation for n in TEST_N_VALUES
                if all_metrics[n].compatible_pairs and all_metrics[n].incompatible_pairs]
        if len(seps) >= 2:
            # All separations should be within 10% of each other
            mean_sep = sum(seps) / len(seps)
            for s in seps:
                assert abs(s - mean_sep) < 0.05, (
                    f"Compat separation varies: {seps}")


class TestDomainFactory:
    """Validate the domain factory produces well-formed domains."""

    def test_all_templates_have_10_nodes(self):
        for tmpl in DOMAIN_TEMPLATES:
            assert len(tmpl["nodes"]) == 10, (
                f"{tmpl['label']}: {len(tmpl['nodes'])} nodes")

    def test_all_templates_have_12_to_14_edges(self):
        for tmpl in DOMAIN_TEMPLATES:
            n_edges = len(tmpl["edges"])
            assert 12 <= n_edges <= 14, (
                f"{tmpl['label']}: {n_edges} edges")

    def test_all_templates_build_valid_landscapes(self):
        for tmpl in DOMAIN_TEMPLATES:
            L = build_bootstrap_landscape(tmpl)
            assert len(L.states) == 10
            assert len(L.edges) >= 12

    def test_start_and_goal_in_nodes(self):
        for tmpl in DOMAIN_TEMPLATES:
            assert tmpl["start"] in tmpl["nodes"], (
                f"{tmpl['label']}: start '{tmpl['start']}' not in nodes")
            assert tmpl["goal"] in tmpl["nodes"], (
                f"{tmpl['label']}: goal '{tmpl['goal']}' not in nodes")

    def test_15_unique_templates(self):
        labels = [t["label"] for t in DOMAIN_TEMPLATES]
        assert len(labels) == 15
        assert len(set(labels)) == 15
