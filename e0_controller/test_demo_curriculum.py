"""Tests for demo_curriculum — C143 smoke tests.

Validates the curriculum demo pipeline works end-to-end.
Core curriculum logic is covered by test_curriculum.py (35 tests).
"""

import pytest

from e0_controller.demo_curriculum import run_demo


class TestCurriculumDemo:
    """C143: Curriculum demo — end-to-end smoke tests."""

    def test_demo_returns_expected_keys(self):
        """run_demo returns dict with all expected keys."""
        result = run_demo()
        expected = {
            "canon_info", "results", "final_landscape",
            "total_episodes", "total_steps", "equilibrium_count",
        }
        assert expected <= set(result.keys())

    def test_ontodynamics_three_turns(self):
        """Default ontodynamics curriculum produces 3 turns."""
        result = run_demo()
        assert len(result["results"]) == 3

    def test_final_landscape_has_all_nodes(self):
        """Final landscape contains all 51 ontodynamics nodes."""
        result = run_demo()
        L = result["final_landscape"]
        assert L is not None
        assert len(L.states) == 51

    def test_final_landscape_has_all_edges(self):
        """Final landscape contains all 93 ontodynamics edges."""
        result = run_demo()
        L = result["final_landscape"]
        assert L is not None
        assert L.edge_count() == 93

    def test_equilibrium_reached_in_all_turns(self):
        """All turns reach equilibrium with mock executor."""
        result = run_demo()
        assert result["equilibrium_count"] == len(result["results"])

    def test_total_steps_positive(self):
        """Curriculum produces nonzero steps."""
        result = run_demo()
        assert result["total_steps"] > 0

    def test_ts_decreases_across_turns(self):
        """T_s should generally decrease as the system learns."""
        result = run_demo()
        ts_values = [r.final_T_s for r in result["results"]]
        # At minimum first turn should have higher T_s than last
        assert ts_values[0] >= ts_values[-1]

    def test_custom_boundaries(self):
        """Custom boundaries produce the expected number of turns."""
        result = run_demo(boundaries=[8, 17])
        assert len(result["results"]) == 2

    def test_custom_canon(self):
        """Demo works with a different canon."""
        result = run_demo(canon_name="english_basic")
        assert result["canon_info"].name == "english_basic"
        assert len(result["results"]) > 0


class TestCurriculumDemoEntropy:
    """C143: Curriculum demo with --entropy flag."""

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
        assert "anchor_count" in ent
        assert "pressure_report" in ent
