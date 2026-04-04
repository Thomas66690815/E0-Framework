"""Tests for demo_reflexion — C144 smoke tests.

Validates the reflexion demo pipeline: standard fails, reactive succeeds
(late), proactive succeeds (early), integrated succeeds (early + SelfGraph).
Core reflexion logic is covered by test_reflexive_edge_proposal.py,
test_integrated_reflexion.py, etc.
"""

import pytest

from e0_controller.demo_reflexion import run_demo, build_research_domain
from e0_controller.reflexive_edge_proposal import is_frontier


class TestReflexionDomain:
    """C144: Research pipeline domain structure."""

    def test_domain_has_7_states(self):
        L = build_research_domain()
        assert len(L.states) == 7

    def test_domain_has_6_edges(self):
        L = build_research_domain()
        assert L.edge_count() == 6

    def test_goal_unreachable_from_start(self):
        """PUBLISH is not reachable from START — structural gap."""
        L = build_research_domain()
        assert is_frontier(L, "START", "PUBLISH")

    def test_review_reachable_from_review(self):
        """PUBLISH is reachable from REVIEW (post-gap)."""
        L = build_research_domain()
        assert not is_frontier(L, "REVIEW", "PUBLISH")


class TestReflexionDemo:
    """C144: Reflexion demo — end-to-end comparison."""

    def test_demo_returns_expected_keys(self):
        result = run_demo()
        expected = {
            "domain_edges", "domain_states",
            "standard", "reactive", "proactive", "integrated",
        }
        assert expected <= set(result.keys())

    def test_standard_fails(self):
        """Standard controller cannot reach PUBLISH."""
        result = run_demo()
        assert not result["standard"]["reached"]

    def test_standard_uses_all_cycles(self):
        """Standard controller exhausts all 40 cycles."""
        result = run_demo()
        assert result["standard"]["steps"] == 40

    def test_reactive_reaches_goal(self):
        """Reactive reflexion reaches PUBLISH."""
        result = run_demo()
        assert result["reactive"]["reached"]

    def test_reactive_proposes_edges(self):
        """Reactive reflexion proposes at least one edge."""
        result = run_demo()
        assert result["reactive"]["proposals"] > 0

    def test_proactive_reaches_goal(self):
        """Proactive reflexion reaches PUBLISH."""
        result = run_demo()
        assert result["proactive"]["reached"]

    def test_proactive_faster_than_reactive(self):
        """Proactive reaches goal in fewer steps than reactive."""
        result = run_demo()
        assert result["proactive"]["steps"] < result["reactive"]["steps"]

    def test_integrated_reaches_goal(self):
        """Integrated reflexion reaches PUBLISH."""
        result = run_demo()
        assert result["integrated"]["reached"]

    def test_integrated_has_journal(self):
        """Integrated reflexion produces a journal."""
        result = run_demo()
        assert result["integrated"]["journal"] is not None


class TestReflexionDemoEntropy:
    """C144: Reflexion demo with --entropy flag."""

    def test_entropy_flag_produces_result(self):
        result = run_demo(use_entropy=True)
        assert "entropy" in result

    def test_entropy_result_structure(self):
        result = run_demo(use_entropy=True)
        ent = result["entropy"]
        assert "episodes" in ent
        assert "sleep_phases" in ent
        assert "dream_cycles" in ent
        assert "pressure_report" in ent
