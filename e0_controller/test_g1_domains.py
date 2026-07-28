"""WP-2.1 tests for preregistered G1 domains and development harness."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from e0_controller.g1_domains import (
    BUILDERS,
    HoldoutAccessError,
    build_development_matrix,
    build_domain,
    keyed_uniform,
    load_g1_protocol,
    validate_development_seed,
    validate_domain,
)
from e0_controller.g1_harness import run_development_inventory
from e0_controller.primitives import Outcome


class TestG1ProtocolBoundary(unittest.TestCase):
    def test_all_preregistered_families_have_builders(self):
        protocol = load_g1_protocol()
        configured = {item["id"] for item in protocol["domain_families"]}
        self.assertEqual(configured, set(BUILDERS))

    def test_holdout_seed_is_rejected(self):
        with self.assertRaises(HoldoutAccessError):
            validate_development_seed(1000)
        with self.assertRaises(HoldoutAccessError):
            build_domain("wall_grid", 100, 1029)

    def test_non_protocol_seed_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_development_seed(10)

    def test_non_protocol_scale_is_rejected(self):
        with self.assertRaises(ValueError):
            build_domain("wall_grid", 101, 0)


class TestG1DomainGenerators(unittest.TestCase):
    def test_all_families_and_scales_pass_invariants(self):
        for family in BUILDERS:
            for scale in (100, 500, 1000):
                with self.subTest(family=family, scale=scale):
                    domain = build_domain(family, scale, 0)
                    self.assertEqual(domain.actual_node_count, scale)
                    self.assertGreater(domain.edge_count, 0)
                    results = validate_domain(domain)
                    self.assertTrue(
                        all(item["passed"] for item in results),
                        msg=results,
                    )

    def test_generation_is_deterministic(self):
        for family in BUILDERS:
            with self.subTest(family=family):
                first = build_domain(family, 100, 3)
                second = build_domain(family, 100, 3)
                self.assertEqual(first.topology_sha256(), second.topology_sha256())
                self.assertEqual(first.to_record(), second.to_record())

    def test_seed_changes_instance_semantics(self):
        for family in BUILDERS:
            with self.subTest(family=family):
                first = build_domain(family, 100, 0)
                second = build_domain(family, 100, 1)
                self.assertNotEqual(first.topology_sha256(), second.topology_sha256())

    def test_wall_grid_requires_antigradient_detour(self):
        domain = build_domain("wall_grid", 100, 2)
        results = {item["id"]: item for item in validate_domain(domain)}
        self.assertTrue(results["direct_gradient_route_blocked"]["passed"])
        self.assertGreater(
            domain.oracle_cost_by_regime["stationary"],
            domain.metadata["cols"] - 1,
        )

    def test_trap_grid_has_real_terminal_failures(self):
        domain = build_domain("trap_grid_v2", 100, 2)
        results = {item["id"]: item for item in validate_domain(domain)}
        self.assertTrue(results["locally_attractive_trap_entry"]["passed"])
        self.assertTrue(results["downstream_failure_dead_end_or_return_cost"]["passed"])
        trap = domain.metadata["traps"][0]
        source, target = trap["failure_edge"].split("\u2192", 1)
        executor = domain.executor(0)
        self.assertEqual(executor(source, target), Outcome.FAILURE)
        self.assertEqual(domain.landscape.admissible_neighbors(target), [])

    def test_decoy_dag_is_acyclic_and_fails_late(self):
        domain = build_domain("decoy_dag", 500, 4)
        results = {item["id"]: item for item in validate_domain(domain)}
        self.assertTrue(results["acyclic"]["passed"])
        self.assertTrue(results["failure_depth_within_preregistered_range"]["passed"])
        self.assertAlmostEqual(domain.metadata["failed_path_fraction"], 0.4)

    def test_nonstationary_roles_reverse_before_evaluation_episode_11(self):
        domain = build_domain("nonstationary_parallel", 100, 0)
        switch = domain.metadata["switch_absolute_episode_index"]
        self.assertEqual(switch, 20)
        preferred = domain.metadata["pre_switch_successful_corridor"]
        rule = next(
            item for item in domain.outcome_rules if item.source.startswith(f"C{preferred}_")
        )
        self.assertEqual(rule.probability(19), 1.0)
        self.assertEqual(rule.probability(20), 0.0)


class TestKeyedOutcomeSchedule(unittest.TestCase):
    def test_keyed_uniform_is_reproducible(self):
        value = keyed_uniform(3, 7, "A\u2192B", 2)
        self.assertEqual(value, keyed_uniform(3, 7, "A\u2192B", 2))
        self.assertGreaterEqual(value, 0.0)
        self.assertLess(value, 1.0)

    def test_edge_attempt_streams_do_not_shift_each_other(self):
        direct = keyed_uniform(2, 5, "A\u2192B", 1)
        keyed_uniform(2, 5, "X\u2192Y", 0)
        keyed_uniform(2, 5, "X\u2192Y", 1)
        after_other_edges = keyed_uniform(2, 5, "A\u2192B", 1)
        self.assertEqual(direct, after_other_edges)

    def test_episode_executor_counts_attempts_per_edge(self):
        domain = build_domain("trap_grid_v2", 100, 0)
        trap = domain.metadata["traps"][0]
        source, target = trap["failure_edge"].split("\u2192", 1)
        executor = domain.executor(4)
        executor(source, target)
        executor(domain.start, "R0C1")
        executor(source, target)
        attempts = [
            event["edge_attempt_index"]
            for event in executor.events
            if event["edge_id"] == trap["failure_edge"]
        ]
        self.assertEqual(attempts, [0, 1])


class TestDevelopmentMatrix(unittest.TestCase):
    def test_matrix_order_and_size(self):
        domains = list(
            build_development_matrix(
                families=["wall_grid", "decoy_dag"],
                scales=[100],
                seeds=[0, 1],
            )
        )
        self.assertEqual(len(domains), 4)
        self.assertEqual(
            [(item.family, item.generator_seed) for item in domains],
            [
                ("wall_grid", 0),
                ("wall_grid", 1),
                ("decoy_dag", 0),
                ("decoy_dag", 1),
            ],
        )

    def test_matrix_rejects_holdout_before_generation(self):
        with self.assertRaises(HoldoutAccessError):
            list(build_development_matrix(scales=[100], seeds=[1000]))


class TestG1DevelopmentHarness(unittest.TestCase):
    def test_harness_writes_non_result_artifacts(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary:
            output = Path(temporary) / "run"
            manifest = run_development_inventory(
                output,
                scales=[100],
                seeds=[0],
            )
            self.assertTrue(manifest["not_g1_result"])
            self.assertFalse(manifest["holdout_accessed"])
            self.assertEqual(manifest["counts"]["domain_instances"], 4)
            self.assertEqual(manifest["counts"]["invariant_fail"], 0)
            records = [
                json.loads(line)
                for line in (output / "domain_instances.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            self.assertEqual(len(records), 4)
            self.assertTrue(all(record["not_g1_result"] for record in records))
            self.assertTrue(all(record["split"] == "development" for record in records))
            self.assertTrue((output / "environment.json").exists())
            self.assertTrue((output / "manifest.json").exists())

    def test_domain_records_are_byte_reproducible(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary:
            root = Path(temporary)
            first = root / "first"
            second = root / "second"
            run_development_inventory(first, scales=[100], seeds=[1])
            run_development_inventory(second, scales=[100], seeds=[1])
            self.assertEqual(
                (first / "domain_instances.jsonl").read_bytes(),
                (second / "domain_instances.jsonl").read_bytes(),
            )

    def test_existing_artifacts_require_explicit_overwrite(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary:
            output = Path(temporary)
            run_development_inventory(output, scales=[100], seeds=[0])
            with self.assertRaises(FileExistsError):
                run_development_inventory(output, scales=[100], seeds=[0])
            manifest = run_development_inventory(
                output,
                scales=[100],
                seeds=[0],
                overwrite=True,
            )
            self.assertEqual(manifest["counts"]["domain_instances"], 4)

    def test_harness_rejects_holdout_without_writing(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary:
            output = Path(temporary) / "forbidden"
            with self.assertRaises(HoldoutAccessError):
                run_development_inventory(output, scales=[100], seeds=[1000])
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
