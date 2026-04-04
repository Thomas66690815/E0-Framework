"""Tests for demo_bootstrap_domain — C140 smoke tests.

Validates the bootstrap demo pipeline works end-to-end without LLM keys.
Core bootstrapper logic is covered by test_bootstrapper.py (41 tests).
"""

import pytest

from e0_controller.demo_bootstrap_domain import run_demo, MOCK_SPEC
from e0_controller.bootstrapper import bootstrap_landscape
from e0_controller.mode_controller import ModeController, OperatingMode


class TestBootstrapDemo:
    """C140: Bootstrap domain demo — end-to-end smoke tests."""

    def test_mock_demo_reaches_goal(self):
        """Mock demo creates landscape, navigates, reaches goal."""
        result = run_demo(use_mock=True)
        assert result["goal_reached"] is True
        assert result["path_used"] == "A (mock)"

    def test_mock_spec_produces_valid_landscape(self):
        """MOCK_SPEC bootstraps into a valid landscape."""
        L = bootstrap_landscape(MOCK_SPEC)
        assert len(L.states) == 9
        assert L.edge_count() == 10
        assert "NEW_HIRE_ARRIVED" in L.states
        assert "ONBOARDING_COMPLETE" in L.states

    def test_confidence_scaling_visible(self):
        """Bootstrapped traces show confidence scaling effect."""
        L = bootstrap_landscape(MOCK_SPEC)
        h = L.historization
        # High confidence edge (0.9): quality closer to raw
        from e0_controller.primitives import Edge
        buddy_edge = Edge("ACCOUNTS_CREATED", "BUDDY_ASSIGNED")
        q_buddy = h.trace_quality(buddy_edge)

        # Low confidence edge (0.5): quality dampened toward 0
        shortcut_edge = Edge("BUDDY_ASSIGNED", "FIRST_WEEK_REVIEW")
        q_shortcut = h.trace_quality(shortcut_edge)

        # Buddy (conf=0.9, raw U=9/F=1) should have higher |quality|
        # than shortcut (conf=0.5, raw U=4/F=6)
        assert abs(q_buddy) > abs(q_shortcut)

    def test_mode_controller_starts_execute(self):
        """All edges bootstrapped with U+F=10 → initially all 'explored'."""
        L = bootstrap_landscape(MOCK_SPEC)
        mc = ModeController(L)
        # Bootstrap injects trace_load=10 for all edges, μ=5 → all explored
        assert mc.current_mode() == OperatingMode.EXECUTE

    def test_error_path_has_negative_quality(self):
        """Error path (U=2, F=8) produces negative quality."""
        L = bootstrap_landscape(MOCK_SPEC)
        h = L.historization
        from e0_controller.primitives import Edge
        error_edge = Edge("NEW_HIRE_ARRIVED", "DOCUMENTS_INCOMPLETE")
        assert h.trace_quality(error_edge) < 0

    def test_demo_returns_expected_keys(self):
        """run_demo returns dict with all expected keys."""
        result = run_demo(use_mock=True)
        expected = {"landscape", "trace", "goal_reached", "mode_before",
                    "mode_after", "path_used"}
        assert expected <= set(result.keys())
