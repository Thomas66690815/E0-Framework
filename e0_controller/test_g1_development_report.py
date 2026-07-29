"""WP-2.4 tests for full development execution, statistics, and artifacts."""

from __future__ import annotations

import gzip
import json
import tempfile
import unittest
from pathlib import Path

from .g1_ablations import ABLATION_METHODS
from .g1_baselines import ALL_BASELINE_METHODS, COMPETITIVE_METHODS
from .g1_development_report import (
    ALL_DEVELOPMENT_METHODS,
    ARTIFACT_FILES,
    DevelopmentTask,
    _comparison_summary,
    _load_shard,
    _paired_values,
    _peak_rss_bytes,
    _stratified_bootstrap,
    _task_grid,
    development_environment,
    execute_development_task,
    render_development_report,
    run_full_development,
    select_primary_control,
    summarize_development_records,
)
from .g1_domains import HoldoutAccessError


def _record(
    method: str,
    *,
    family: str = "wall_grid",
    scale: int = 100,
    seed: int = 0,
    score: float = 0.5,
    goal_rate: float = 0.8,
    wall_time_ms: float = 100.0,
) -> dict:
    return {
        "protocol_id": "E0-G1-v1",
        "artifact_kind": "development_full_run",
        "not_g1_result": True,
        "holdout_accessed": False,
        "split": "development",
        "commit": "abc123",
        "run_id": f"dev-{family}-N{scale}-s{seed:04d}-{method.lower()}",
        "domain_family": family,
        "target_node_count": scale,
        "actual_node_count": scale,
        "generator_seed": seed,
        "outcome_seed": 200000 + seed,
        "policy_seed": 300000 + seed,
        "method": method,
        "config_hash": "0" * 64,
        "interaction_budget": 4 * scale,
        "interactions_used": 10,
        "success_adjusted_efficiency": score,
        "goal_rate": goal_rate,
        "wall_time_ms": wall_time_ms,
        "peak_rss_bytes": 1,
        "paths_expanded": 0,
        "path_cap_hits": 0,
        "status": "completed",
    }


def _complete_synthetic_records() -> list[dict]:
    records = []
    scores = {
        "A_HIST": 0.60,
        "B_INCOHERENT": 0.65,
        "C_THETA_ZERO": 0.65,
        "D_U1_PHASE": 0.68,
        "E_FULL_GEOMETRY": 0.72,
        "Q_LEARNING": 0.50,
        "UCB1_EDGE": 0.55,
        "RANDOM_RESTART_GREEDY": 0.45,
        "MEMORYLESS_GREEDY": 0.40,
        "EPSILON_GREEDY": 0.42,
        "UNIFORM_RANDOM": 0.20,
        "A_STAR": 0.90,
        "D_STAR_LITE": 0.90,
    }
    for family_index, family in enumerate(
        ("wall_grid", "trap_grid_v2", "decoy_dag", "nonstationary_parallel")
    ):
        for scale in (100, 500, 1000):
            for seed in (0, 1):
                for method in ALL_DEVELOPMENT_METHODS:
                    score = scores[method] + family_index * 0.005 + seed * 0.001
                    wall = 50.0 if method == "C_THETA_ZERO" else 100.0
                    records.append(
                        _record(
                            method,
                            family=family,
                            scale=scale,
                            seed=seed,
                            score=score,
                            goal_rate=min(1.0, score + 0.1),
                            wall_time_ms=wall,
                        )
                    )
    return records


class TestDevelopmentTaskRegistry(unittest.TestCase):
    def test_all_thirteen_methods_are_included(self):
        self.assertEqual(
            (*ABLATION_METHODS, *ALL_BASELINE_METHODS),
            ALL_DEVELOPMENT_METHODS,
        )
        self.assertEqual(13, len(ALL_DEVELOPMENT_METHODS))

    def test_full_task_grid_has_1560_replicates(self):
        tasks = _task_grid("abc123")
        self.assertEqual(1560, len(tasks))
        self.assertEqual(1560, len({task.run_id for task in tasks}))

    def test_task_grid_stable_order(self):
        first = _task_grid(
            "abc123",
            families=["wall_grid"],
            scales=[100],
            seeds=[0],
            methods=["A_HIST", "Q_LEARNING"],
        )
        second = _task_grid(
            "abc123",
            families=["wall_grid"],
            scales=[100],
            seeds=[0],
            methods=["A_HIST", "Q_LEARNING"],
        )
        self.assertEqual(first, second)
        self.assertEqual(
            ["A_HIST", "Q_LEARNING"],
            [task.method for task in first],
        )

    def test_task_id_and_shard_name_are_stable(self):
        task = DevelopmentTask("wall_grid", 100, 3, "D_STAR_LITE", "abc")
        self.assertEqual(
            "dev-wall_grid-N100-s0003-d_star_lite",
            task.run_id,
        )
        self.assertEqual(
            "wall_grid__N100__s0003__d_star_lite.json",
            task.shard_name,
        )

    def test_holdout_seed_is_rejected(self):
        with self.assertRaises(HoldoutAccessError):
            _task_grid(
                "abc",
                families=["wall_grid"],
                scales=[100],
                seeds=[1000],
                methods=["A_HIST"],
            )

    def test_unknown_method_is_rejected(self):
        with self.assertRaises(ValueError):
            _task_grid(
                "abc",
                families=["wall_grid"],
                scales=[100],
                seeds=[0],
                methods=["NOT_A_METHOD"],
            )


class TestWorkerRecords(unittest.TestCase):
    def test_baseline_worker_runs_full_protocol(self):
        result = execute_development_task(
            DevelopmentTask(
                "wall_grid",
                100,
                0,
                "Q_LEARNING",
                "abc123",
            ).to_dict()
        )
        self.assertNotIn("infrastructure_error", result)
        self.assertEqual(20, len(result["evaluation_episodes"]))
        raw = result["raw_run"]
        self.assertEqual(30, raw["episode_count"])
        self.assertEqual(20, raw["evaluation_episode_count"])
        self.assertEqual("completed", raw["status"])

    def test_ablation_worker_records_path_metrics(self):
        result = execute_development_task(
            DevelopmentTask(
                "wall_grid",
                100,
                0,
                "B_INCOHERENT",
                "abc123",
            ).to_dict()
        )
        raw = result["raw_run"]
        self.assertGreater(raw["paths_expanded"], 0)
        self.assertEqual(20, len(result["evaluation_episodes"]))

    def test_worker_minimum_raw_fields(self):
        result = execute_development_task(
            DevelopmentTask(
                "wall_grid",
                100,
                0,
                "A_HIST",
                "abc123",
            ).to_dict()
        )
        raw = result["raw_run"]
        required = {
            "protocol_id",
            "commit",
            "run_id",
            "domain_family",
            "target_node_count",
            "actual_node_count",
            "generator_seed",
            "outcome_seed",
            "policy_seed",
            "method",
            "config_hash",
            "interaction_budget",
            "interactions_used",
            "success_adjusted_efficiency",
            "goal_rate",
            "wall_time_ms",
            "peak_rss_bytes",
            "paths_expanded",
            "status",
        }
        self.assertTrue(required.issubset(raw))
        self.assertTrue(raw["not_g1_result"])
        self.assertFalse(raw["holdout_accessed"])

    def test_peak_rss_and_environment_are_available(self):
        self.assertGreaterEqual(_peak_rss_bytes(), 0)
        environment = development_environment()
        self.assertIn("logical_cpu_count", environment)
        self.assertIn("total_physical_memory_bytes", environment)
        self.assertIn("resolution_seconds", environment["timer"])
        self.assertIn("scipy", environment["packages"])


class TestControlSelectionAndStatistics(unittest.TestCase):
    def test_control_selection_uses_mean_then_wall_time(self):
        records = [
            _record("A_HIST", score=0.5, wall_time_ms=10),
            _record("B_INCOHERENT", score=0.6, wall_time_ms=100),
            _record("C_THETA_ZERO", score=0.6, wall_time_ms=50),
        ]
        selection = select_primary_control(records)
        self.assertEqual("C_THETA_ZERO", selection["selected"])
        self.assertEqual(
            ["C_THETA_ZERO", "B_INCOHERENT", "A_HIST"],
            [item["method"] for item in selection["ranking"]],
        )

    def test_control_selection_uses_only_development_records(self):
        selection = select_primary_control(_complete_synthetic_records())
        self.assertEqual("C_THETA_ZERO", selection["selected"])
        self.assertFalse(selection["holdout_accessed"])
        self.assertEqual("development only", selection["data"])

    def test_paired_values_align_identical_units(self):
        records = [
            _record("E_FULL_GEOMETRY", seed=0, score=0.8),
            _record("C_THETA_ZERO", seed=0, score=0.5),
            _record("E_FULL_GEOMETRY", seed=1, score=0.7),
            _record("C_THETA_ZERO", seed=1, score=0.6),
        ]
        pairs = _paired_values(records, "E_FULL_GEOMETRY", "C_THETA_ZERO")
        self.assertEqual(2, len(pairs))
        self.assertEqual((0.8, 0.5, 0.8, 0.8), pairs[("wall_grid", 100, 0)])

    def test_stratified_bootstrap_is_deterministic(self):
        pairs = {
            ("wall_grid", 100, seed): (
                0.7 + seed * 0.01,
                0.5,
                0.8,
                0.7,
            )
            for seed in range(5)
        }
        first = _stratified_bootstrap(pairs, resamples=200, seed=42)
        second = _stratified_bootstrap(pairs, resamples=200, seed=42)
        self.assertEqual(first, second)
        self.assertGreater(first["mean_difference"], 0)
        self.assertEqual(5, first["paired_units"])

    def test_comparison_has_family_and_overall_intervals(self):
        comparison = _comparison_summary(
            _complete_synthetic_records(),
            "E_FULL_GEOMETRY",
            "C_THETA_ZERO",
            seed_offset=0,
        )
        self.assertEqual(4, len(comparison["families"]))
        self.assertEqual(24, comparison["overall"]["paired_units"])
        self.assertEqual(2, len(comparison["overall"]["ci95"]))

    def test_summary_selects_control_and_keeps_gate_boundary(self):
        summary = summarize_development_records(_complete_synthetic_records())
        self.assertEqual(
            "C_THETA_ZERO",
            summary["primary_control_selection"]["selected"],
        )
        self.assertIn(
            "G1_A_full_geometry_vs_selected_control",
            summary["development_diagnostics_not_gate_results"],
        )
        self.assertTrue(summary["not_g1_result"])
        self.assertFalse(summary["holdout_accessed"])
        self.assertIn("do not pass or fail", summary["interpretation"])

    def test_baseline_comparator_uses_protocol_methods(self):
        self.assertEqual(
            ("Q_LEARNING", "UCB1_EDGE", "RANDOM_RESTART_GREEDY"),
            COMPETITIVE_METHODS,
        )
        summary = summarize_development_records(_complete_synthetic_records())
        item = summary["development_diagnostics_not_gate_results"][
            "G1_B_A_HIST_vs_competitive_baseline_median"
        ]
        self.assertEqual("BASELINE_MEDIAN", item["control"])

    def test_report_is_derived_and_explicitly_not_gate_result(self):
        summary = summarize_development_records(_complete_synthetic_records())
        report = render_development_report(summary)
        self.assertIn("Selected: **`C_THETA_ZERO`**", report)
        self.assertIn("Gate result:** none", report)
        self.assertIn("No holdout seed", report)


class TestFullDevelopmentArtifacts(unittest.TestCase):
    METHODS = (
        "A_HIST",
        "B_INCOHERENT",
        "C_THETA_ZERO",
        "D_U1_PHASE",
        "E_FULL_GEOMETRY",
        "Q_LEARNING",
        "UCB1_EDGE",
        "RANDOM_RESTART_GREEDY",
    )

    def test_small_complete_run_writes_required_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            events = []
            manifest = run_full_development(
                output,
                families=["wall_grid"],
                scales=[100],
                seeds=[0],
                methods=self.METHODS,
                workers=2,
                progress=events.append,
            )
            self.assertEqual(8, manifest["counts"]["completed_replicates"])
            self.assertEqual(160, manifest["counts"]["evaluation_episode_records"])
            self.assertEqual(0, manifest["counts"]["infrastructure_failures"])
            self.assertEqual(
                set(ARTIFACT_FILES),
                {path.name for path in output.iterdir() if path.is_file()},
            )
            self.assertTrue((output / "shards").is_dir())
            raw = (output / "raw_runs.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(8, len(raw))
            with gzip.open(output / "episodes.jsonl.gz", "rt", encoding="utf-8") as handle:
                episodes = [json.loads(line) for line in handle]
            self.assertEqual(160, len(episodes))
            self.assertEqual("start", events[0]["event"])
            self.assertEqual(8, events[-1]["completed"])

    def test_resume_reuses_complete_shards(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            run_full_development(
                output,
                families=["wall_grid"],
                scales=[100],
                seeds=[0],
                methods=self.METHODS,
                workers=2,
            )
            events = []
            run_full_development(
                output,
                families=["wall_grid"],
                scales=[100],
                seeds=[0],
                methods=self.METHODS,
                workers=2,
                progress=events.append,
            )
            self.assertEqual(8, events[0]["resumed"])
            self.assertEqual(0, events[0]["pending"])
            self.assertEqual(1, len(events))

    def test_invalid_shard_is_not_resumed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text("{}", encoding="utf-8")
            task = DevelopmentTask("wall_grid", 100, 0, "A_HIST", "abc")
            self.assertIsNone(_load_shard(path, task))

    def test_existing_artifacts_require_resume_or_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "manifest.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                run_full_development(
                    output,
                    families=["wall_grid"],
                    scales=[100],
                    seeds=[0],
                    methods=self.METHODS,
                    workers=1,
                    resume=False,
                )

    def test_full_runner_rejects_holdout(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(HoldoutAccessError):
                run_full_development(
                    Path(directory),
                    families=["wall_grid"],
                    scales=[100],
                    seeds=[1000],
                    methods=self.METHODS,
                    workers=1,
                )


if __name__ == "__main__":
    unittest.main()
