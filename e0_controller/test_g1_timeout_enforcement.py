"""Regression tests for the preregistered WP-2.4 wall-time boundaries."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from .g1_ablations import build_ablation_adapter, run_ablation_episode
from .g1_baselines import build_adapter, run_episode
from .g1_development_report import (
    DevelopmentTask,
    _summarize_replicate,
    execute_development_task,
)
from .g1_domains import build_domain


class TestEpisodeDeadline(unittest.TestCase):
    def test_baseline_stops_at_decision_boundary(self):
        domain = build_domain("wall_grid", 100, 0)
        adapter = build_adapter("MEMORYLESS_GREEDY", domain)
        with patch(
            "e0_controller.g1_baselines.time.perf_counter",
            side_effect=[0.0, 61.0],
        ):
            summary = run_episode(domain, adapter, 0)
        self.assertEqual("algorithm_timeout", summary.terminal_reason)
        self.assertFalse(summary.goal_reached)
        self.assertEqual(0.0, summary.success_adjusted_efficiency)
        self.assertEqual(0, summary.interactions_used)

    def test_ablation_propagates_deadline_status(self):
        domain = build_domain("wall_grid", 100, 0)
        adapter = build_ablation_adapter("A_HIST", domain)
        with patch(
            "e0_controller.g1_baselines.time.perf_counter",
            side_effect=[0.0, 0.0, 61.0, 61.0],
        ):
            result = run_ablation_episode(domain, adapter, 0)
        self.assertEqual("algorithm_timeout", result.status)
        self.assertEqual("algorithm_timeout", result.summary.terminal_reason)
        self.assertFalse(result.summary.goal_reached)
        self.assertEqual(0.0, result.summary.success_adjusted_efficiency)


class TestValidNegativeScoring(unittest.TestCase):
    def test_any_timeout_zeros_replicate_primary_score(self):
        task = DevelopmentTask("wall_grid", 100, 0, "A_STAR", "abc123")
        shard = execute_development_task(task.to_dict())
        episodes = shard["evaluation_episodes"]
        self.assertTrue(any(item["success_adjusted_efficiency"] > 0.0 for item in episodes))
        episodes[0]["status"] = "algorithm_timeout"
        episodes[0]["terminal_reason"] = "algorithm_timeout"
        raw = _summarize_replicate(task, episodes, 1.0, 1)
        self.assertEqual("algorithm_timeout", raw["status"])
        self.assertEqual(0.0, raw["success_adjusted_efficiency"])


if __name__ == "__main__":
    unittest.main()
