"""Tests for demo_multiverse — C142 smoke tests.

Validates the multiverse demo pipeline works end-to-end without LLM keys.
Core multiverse logic is covered by test_multiverse.py.
Core dream logic is covered by test_dream_mode.py.
"""

import pytest

from e0_controller.demo_multiverse import (
    run_demo, DOMAIN_A_SPEC, DOMAIN_B_SPEC,
)
from e0_controller.bootstrapper import bootstrap_landscape
from e0_controller.multiverse import MultiverseResult


class TestMultiverseDemo:
    """C142: Multiverse demo — end-to-end smoke tests."""

    def test_demo_returns_expected_keys(self):
        """run_demo returns dict with all expected keys."""
        result = run_demo()
        expected = {
            "landscape_a", "landscape_b", "multiverse_result",
            "dream_observer", "dream_results", "total_equivalences",
        }
        assert expected <= set(result.keys())

    def test_both_landscapes_valid(self):
        """Both domain specs bootstrap into valid landscapes."""
        L_a = bootstrap_landscape(DOMAIN_A_SPEC)
        L_b = bootstrap_landscape(DOMAIN_B_SPEC)
        assert len(L_a.states) == 9
        assert len(L_b.states) == 9
        assert L_a.edge_count() == 10
        assert L_b.edge_count() == 10

    def test_multiverse_runs_20_turns(self):
        """Multiverse runs the expected number of turns."""
        result = run_demo()
        mv = result["multiverse_result"]
        assert mv.total_turns == 20

    def test_novelty_rate_positive(self):
        """Divergence pressure creates at least some novelty."""
        result = run_demo()
        mv = result["multiverse_result"]
        assert mv.novelty_rate > 0

    def test_dream_discovers_node_equivalences(self):
        """DreamObserver with Hungarian finds node-level matches."""
        result = run_demo()
        dr_list = result["dream_results"]
        # First cycle should find node equivalences
        assert dr_list[0].node_equivalences_found > 0

    def test_dream_discovers_edge_equivalences(self):
        """DreamObserver finds edge-level equivalences."""
        result = run_demo()
        dr_list = result["dream_results"]
        assert dr_list[0].equivalences_found > 0

    def test_total_equivalences_positive(self):
        """Some cross-domain equivalences are recorded."""
        result = run_demo()
        assert result["total_equivalences"] > 0

    def test_dream_landscape_built(self):
        """Dream Landscape is constructed after dream cycles."""
        result = run_demo()
        dl = result["dream_observer"].dream_landscape
        assert dl is not None
        assert len(dl.states) > 0
        assert len(dl.edges) > 0


class TestMultiverseDemoEntropy:
    """C142: Multiverse demo with --entropy flag."""

    def test_entropy_flag_produces_result(self):
        """Demo with use_entropy=True completes and adds entropy key."""
        result = run_demo(use_entropy=True)
        assert "entropy" in result

    def test_entropy_result_structure(self):
        """Entropy result contains expected fields."""
        result = run_demo(use_entropy=True)
        ent = result["entropy"]
        assert "episodes" in ent
        assert "sleep_phases" in ent
        assert "dream_cycles" in ent
        assert "pressure_report" in ent

    def test_entropy_has_both_domains(self):
        """Pressure report includes both domains."""
        result = run_demo(use_entropy=True)
        pr = result["entropy"]["pressure_report"]
        assert "Domain-A" in pr
        assert "Domain-B" in pr
