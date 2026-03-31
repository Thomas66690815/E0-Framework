"""
E₀ Live LLM Co-Cognition Tests (C71)
=====================================

Live tests that validate the full co-cognition pipeline against OpenAI API.

These tests are NOT part of the standard suite (discover pattern: test_*.py).
They require OPENAI_API_KEY in the environment or .env file.

Run explicitly::

    python -m unittest e0_controller.live_test_cocognition -v

Two LLMs independently bootstrap landscapes for the same task,
then exchange structural knowledge via multiverse coupling.
"""

from __future__ import annotations

import os
import unittest

from e0_controller.llm_adapter import LLMConfig
from e0_controller.llm_cocognition import (
    CoCognitionResult,
    bootstrap_llm_universe,
    run_cocognition_from_universes,
)


def _has_openai() -> bool:
    try:
        import openai  # noqa: F401
        return True
    except ImportError:
        return False


def _has_api_key() -> bool:
    if os.environ.get("OPENAI_API_KEY"):
        return True
    env_path = os.path.join(os.getcwd(), ".env")
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("OPENAI_API_KEY="):
                    val = line.strip().split("=", 1)[1].strip()
                    if val:
                        return True
    return False


def _can_run_llm() -> bool:
    return _has_openai() and _has_api_key()


SKIP_MSG = "openai package or OPENAI_API_KEY not available — skipping live co-cognition tests"

# ──────────────────────────────────────────────
# Task definition
# ──────────────────────────────────────────────

TASK = (
    "Analyze a competitor's product announcement and produce a structured "
    "briefing for the executive team."
)
START = "RAW_ANNOUNCEMENT"
GOAL = "BRIEFING_DELIVERED"


# ──────────────────────────────────────────────
# Module-level cache (expensive — one LLM round-trip)
# ──────────────────────────────────────────────

_LIVE_RESULT: CoCognitionResult | None = None


def _get_live_result() -> CoCognitionResult:
    global _LIVE_RESULT
    if _LIVE_RESULT is None:
        from e0_controller.llm_adapter import E0LLMAdapter

        cfg_a = LLMConfig(temperature=0.2)
        cfg_b = LLMConfig(temperature=0.6)
        adapter_a = E0LLMAdapter(config=cfg_a)
        adapter_b = E0LLMAdapter(config=cfg_b)

        universe_a = bootstrap_llm_universe(
            adapter_a, TASK, "LLM_A", START, GOAL,
        )
        universe_b = bootstrap_llm_universe(
            adapter_b, TASK, "LLM_B", START, GOAL,
        )
        _LIVE_RESULT = run_cocognition_from_universes(
            universe_a, universe_b,
            max_turns=10,
            max_nav_cycles=20,
        )
    return _LIVE_RESULT


# ──────────────────────────────────────────────
# Test Class: Live Co-Cognition
# ──────────────────────────────────────────────

@unittest.skipUnless(_can_run_llm(), SKIP_MSG)
class TestLiveCoCognition(unittest.TestCase):
    """Full LLM co-cognition pipeline with real API calls."""

    @classmethod
    def setUpClass(cls):
        cls.result = _get_live_result()

    def test_both_universes_bootstrapped(self):
        """Both LLMs produce landscapes with states and edges."""
        self.assertGreater(self.result.a_initial_states, 3)
        self.assertGreater(self.result.b_initial_states, 3)
        self.assertGreater(self.result.a_initial_edges, 3)
        self.assertGreater(self.result.b_initial_edges, 3)

    def test_initial_distance_positive(self):
        """Two independent bootstraps produce different topologies."""
        self.assertGreater(self.result.structural_distance_before, 0.0)

    def test_at_least_one_reaches_goal(self):
        """At least one controller reaches the goal after coupling."""
        self.assertTrue(
            self.result.a_reached_goal or self.result.b_reached_goal,
            "Neither controller reached goal after co-cognition",
        )

    def test_enrichment_occurred(self):
        """Knowledge exchange adds edges to at least one universe."""
        self.assertGreater(self.result.total_enrichment, 0)

    def test_novelty_rate_positive(self):
        """At least some multiverse turns produce novelty."""
        self.assertGreater(self.result.novelty_rate, 0.0)

    def test_distance_decreases(self):
        """Structural distance decreases after coupling."""
        self.assertLessEqual(
            self.result.structural_distance_after,
            self.result.structural_distance_before,
        )

    def test_summary_parseable(self):
        """Summary produces non-empty text."""
        s = self.result.summary()
        self.assertIn("Co-Cognition", s)
        self.assertGreater(len(s), 100)


# ──────────────────────────────────────────────
# Test Class: Bootstrap produces valid Universe
# ──────────────────────────────────────────────

@unittest.skipUnless(_can_run_llm(), SKIP_MSG)
class TestLiveBootstrapUniverse(unittest.TestCase):
    """bootstrap_llm_universe creates a valid Universe with LLM."""

    @classmethod
    def setUpClass(cls):
        from e0_controller.llm_adapter import E0LLMAdapter
        cls.adapter = E0LLMAdapter(config=LLMConfig(temperature=0.2))
        cls.universe = bootstrap_llm_universe(
            cls.adapter, TASK, "TestU", START, GOAL,
        )

    def test_has_start_state(self):
        self.assertIn(START, self.universe.landscape.states)

    def test_has_goal_state(self):
        self.assertIn(GOAL, self.universe.landscape.states)

    def test_has_edges(self):
        self.assertGreater(self.universe.landscape.edge_count(), 0)

    def test_name_set(self):
        self.assertEqual(self.universe.name, "TestU")

    def test_execute_fn_callable(self):
        self.assertTrue(callable(self.universe.execute_fn))


if __name__ == "__main__":
    unittest.main()
