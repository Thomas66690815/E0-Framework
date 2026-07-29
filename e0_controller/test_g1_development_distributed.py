"""Tests for bounded and distributed WP-2.4 execution."""

from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from .g1_development_distributed import (
    MAX_GITHUB_MATRIX_JOBS,
    consolidate_distributed,
    execute_development_task_bounded,
    execute_task_set,
    github_matrix,
    partition_tasks,
    timeout_shard,
)
from .g1_development_report import DevelopmentTask, _task_grid


class TestDistributedPartition(unittest.TestCase):
    def test_full_matrix_partitions_without_duplicates(self):
        tasks = _task_grid("abc123")
        batches = partition_tasks(tasks, 240)
        flattened = [task for batch in batches for task in batch]
        self.assertEqual(240, len(batches))
        self.assertEqual(1560, len(flattened))
        self.assertEqual(1560, len({task.run_id for task in flattened}))
        self.assertEqual({6, 7}, {len(batch) for batch in batches})

    def test_matrix_is_within_github_limit(self):
        matrix = github_matrix(240)
        self.assertEqual(240, len(matrix["include"]))
        self.assertEqual(0, matrix["include"][0]["batch_index"])
        self.assertEqual(239, matrix["include"][-1]["batch_index"])

    def test_rejects_excessive_matrix(self):
        with self.assertRaises(ValueError):
            partition_tasks(_task_grid("abc123"), MAX_GITHUB_MATRIX_JOBS + 1)

    def test_matrix_json_is_compact_and_round_trips(self):
        encoded = json.dumps(github_matrix(10), separators=(",", ":"))
        self.assertEqual(10, len(json.loads(encoded)["include"]))


class TestHardTimeout(unittest.TestCase):
    def setUp(self):
        self.task = DevelopmentTask("wall_grid", 100, 0, "A_HIST", "abc123")

    def test_timeout_shard_preserves_protocol_shape(self):
        shard = timeout_shard(self.task.to_dict(), 1800000.0)
        raw = shard["raw_run"]
        self.assertEqual("algorithm_timeout", raw["status"])
        self.assertEqual(30, raw["episode_count"])
        self.assertEqual(20, raw["evaluation_episode_count"])
        self.assertEqual(20, len(shard["evaluation_episodes"]))
        self.assertEqual(0.0, raw["success_adjusted_efficiency"])
        self.assertTrue(raw["hard_timeout_enforced"])
        self.assertTrue(all(not item["executed"] for item in shard["evaluation_episodes"]))

    def test_process_timeout_is_enforced(self):
        started = time.perf_counter()
        shard = execute_development_task_bounded(
            self.task.to_dict(),
            timeout_seconds=0.01,
        )
        elapsed = time.perf_counter() - started
        self.assertEqual("algorithm_timeout", shard["raw_run"]["status"])
        self.assertLess(elapsed, 10.0)

    def test_normal_worker_result_survives_wrapper(self):
        shard = execute_development_task_bounded(
            self.task.to_dict(),
            timeout_seconds=30.0,
        )
        self.assertNotIn("infrastructure_error", shard)
        self.assertEqual(20, len(shard["evaluation_episodes"]))


class TestDistributedPersistence(unittest.TestCase):
    def test_task_set_writes_and_resumes_atomic_shard(self):
        task = DevelopmentTask("wall_grid", 100, 0, "A_HIST", "abc123")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            first = execute_task_set([task], output, workers=1)
            second = execute_task_set([task], output, workers=1)
            self.assertEqual(1, first["completed"])
            self.assertEqual(0, first["resumed"])
            self.assertEqual(1, second["completed"])
            self.assertEqual(1, second["resumed"])
            self.assertTrue((output / "shards" / task.shard_name).is_file())

    def test_incomplete_consolidation_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "incomplete"):
                consolidate_distributed(
                    Path(directory),
                    report=Path(directory) / "report.md",
                )


if __name__ == "__main__":
    unittest.main()
