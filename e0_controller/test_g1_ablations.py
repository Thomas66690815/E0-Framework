"""WP-2.3 tests for the five causal Gate G1 E0 ablations."""

from __future__ import annotations

import copy
import json
import math
import tempfile
import unittest
from pathlib import Path

from lean.structural_geometry import theta

from .g1_ablation_harness import run_ablation_compatibility
from .g1_ablations import (
    ABLATION_METHODS,
    INFORMATION_ACCESS,
    LOOKAHEAD_METHODS,
    SIMPLER_CONTROL_CANDIDATES,
    E0AblationAdapter,
    _manual_scores,
    _nav_field,
    _path_family,
    ablation_config_sha256,
    build_ablation_adapter,
    load_ablation_configs,
    protocol_ablation_contracts,
    run_ablation_episode,
    run_ablation_replicate,
    validate_ablation_contract,
)
from .g1_baselines import _local_actions
from .g1_domains import (
    G1DomainInstance,
    HoldoutAccessError,
    OutcomeRule,
    build_development_matrix,
    build_domain,
    load_g1_protocol,
)
from .landscape import Landscape


def _small_domain(*, failing_first_edge: bool = False) -> G1DomainInstance:
    landscape = Landscape()
    landscape.add_edge("S", "A", delta=0.1, resistance=1.0)
    landscape.add_edge("S", "B", delta=0.5, resistance=1.0)
    landscape.add_edge("A", "S", delta=0.1, resistance=1.0)
    landscape.add_edge("A", "G", delta=1.0, resistance=1.0)
    landscape.add_edge("B", "G", delta=0.2, resistance=1.0)
    rules = (
        (
            OutcomeRule(
                "S",
                "A",
                success_probability_pre=0.0,
                semantic_role="test_failure",
            ),
        )
        if failing_first_edge
        else ()
    )
    return G1DomainInstance(
        family="test_domain",
        target_node_count=4,
        generator_seed=0,
        landscape=landscape,
        start="S",
        goal="G",
        oracle_cost_by_regime={"stationary": 2},
        outcome_rules=rules,
    )


class TestAblationRegistry(unittest.TestCase):
    def test_registry_exactly_matches_protocol(self):
        validate_ablation_contract()
        protocol_ids = tuple(item["id"] for item in load_g1_protocol()["e0_ablations"])
        self.assertEqual(ABLATION_METHODS, protocol_ids)

    def test_exact_five_methods_and_order(self):
        self.assertEqual(5, len(ABLATION_METHODS))
        self.assertEqual(
            (
                "A_HIST",
                "B_INCOHERENT",
                "C_THETA_ZERO",
                "D_U1_PHASE",
                "E_FULL_GEOMETRY",
            ),
            ABLATION_METHODS,
        )

    def test_protocol_contract_fields_are_preserved(self):
        contracts = protocol_ablation_contracts()
        for item in load_g1_protocol()["e0_ablations"]:
            with self.subTest(method=item["id"]):
                contract = contracts[item["id"]]
                self.assertEqual(item["lookahead"], contract.lookahead)
                self.assertEqual(item["aggregation"], contract.aggregation)
                self.assertEqual(item["phase"], contract.phase)

    def test_only_A_has_no_lookahead(self):
        contracts = protocol_ablation_contracts()
        self.assertFalse(contracts["A_HIST"].lookahead)
        self.assertTrue(all(contracts[item].lookahead for item in LOOKAHEAD_METHODS))

    def test_simpler_control_candidates_are_frozen(self):
        protocol = load_g1_protocol()
        self.assertEqual(
            SIMPLER_CONTROL_CANDIDATES,
            tuple(protocol["gate_G1_A"]["control_selection"]["candidates"]),
        )

    def test_frozen_config_is_protocol_bound(self):
        config = load_ablation_configs()
        self.assertTrue(config["frozen_before_holdout"])
        self.assertFalse(config["holdout_execution_started"])
        self.assertEqual(ABLATION_METHODS, tuple(config["methods"]))
        self.assertEqual(64, len(ablation_config_sha256()))

    def test_primary_control_is_not_prematurely_selected(self):
        selection = load_ablation_configs()["primary_control_selection"]
        self.assertIsNone(selection["selected"])
        self.assertIn("WP-2.4", selection["status"])

    def test_all_methods_share_information_boundary(self):
        self.assertIn("observed_outcomes", INFORMATION_ACCESS)
        self.assertNotIn("probabilities", INFORMATION_ACCESS)

    def test_holdout_domain_is_rejected_before_adapter_build(self):
        with self.assertRaises(HoldoutAccessError):
            build_domain("wall_grid", 100, 1000)

    def test_unknown_method_is_rejected(self):
        with self.assertRaises(ValueError):
            build_ablation_adapter("NOT_A_METHOD", _small_domain())


class TestCausalAggregations(unittest.TestCase):
    def setUp(self):
        self.domain = _small_domain()
        self.config = load_ablation_configs()
        self.adapter = build_ablation_adapter("B_INCOHERENT", self.domain)
        self.field = _nav_field(self.adapter.landscape)
        self.family = _path_family(
            self.field,
            "S",
            ("A", "B"),
            self.config["shared"],
        )

    def test_B_is_sum_of_individual_path_intensities(self):
        scores = _manual_scores("B_INCOHERENT", self.field, self.family)
        for action, paths in self.family.paths_by_action.items():
            expected = sum(math.exp(-2.0 * self.field.path_cost(path)) for path in paths)
            self.assertAlmostEqual(expected, scores[action])

    def test_C_is_squared_positive_real_mass(self):
        scores = _manual_scores("C_THETA_ZERO", self.field, self.family)
        for action, paths in self.family.paths_by_action.items():
            expected = sum(math.exp(-self.field.path_cost(path)) for path in paths) ** 2
            self.assertAlmostEqual(expected, scores[action])

    def test_D_is_U1_superposition(self):
        scores = _manual_scores("D_U1_PHASE", self.field, self.family)
        for action, paths in self.family.paths_by_action.items():
            amplitude = sum(
                (
                    math.exp(-self.field.path_cost(path))
                    * complex(
                        math.cos(theta(self.field, path)),
                        math.sin(theta(self.field, path)),
                    )
                    for path in paths
                ),
                start=0j,
            )
            self.assertAlmostEqual(abs(amplitude) ** 2, scores[action])

    def test_B_C_D_share_exact_path_family(self):
        signatures = []
        candidates = None
        path_counts = None
        for method in ("B_INCOHERENT", "C_THETA_ZERO", "D_U1_PHASE"):
            adapter = build_ablation_adapter(method, self.domain)
            adapter.select_action(0, "S", _local_actions(self.domain, "S"))
            record = adapter.decision_records[-1]
            signatures.append(record.path_family_signature)
            candidates = candidates or record.candidates
            path_counts = path_counts or record.path_counts
            self.assertEqual(candidates, record.candidates)
            self.assertEqual(path_counts, record.path_counts)
        self.assertEqual(1, len(set(signatures)))

    def test_E_uses_same_path_family_as_manual_variants(self):
        signatures = []
        for method in LOOKAHEAD_METHODS:
            adapter = build_ablation_adapter(method, self.domain)
            adapter.select_action(0, "S", _local_actions(self.domain, "S"))
            signatures.append(adapter.decision_records[-1].path_family_signature)
        self.assertEqual(1, len(set(signatures)))

    def test_D_and_E_match_on_same_U1_field(self):
        records = {}
        for method in ("D_U1_PHASE", "E_FULL_GEOMETRY"):
            adapter = build_ablation_adapter(method, self.domain)
            adapter.select_action(0, "S", _local_actions(self.domain, "S"))
            records[method] = adapter.decision_records[-1]
        for action in records["D_U1_PHASE"].scores:
            self.assertAlmostEqual(
                records["D_U1_PHASE"].scores[action],
                records["E_FULL_GEOMETRY"].scores[action],
                places=12,
            )

    def test_path_signature_is_deterministic(self):
        second = _path_family(
            self.field,
            "S",
            ("A", "B"),
            self.config["shared"],
        )
        self.assertEqual(self.family.signature, second.signature)
        self.assertEqual(self.family.paths_by_action, second.paths_by_action)

    def test_cap_hit_stops_decision_and_scores_zero(self):
        config = copy.deepcopy(self.config)
        config["shared"]["max_paths_per_decision"] = 1
        adapter = E0AblationAdapter("B_INCOHERENT", self.domain, config)
        episode = run_ablation_episode(
            self.domain,
            adapter,
            0,
            interaction_budget=4,
        )
        self.assertEqual("path_cap_hit", episode.status)
        self.assertEqual(1, episode.path_cap_hits)
        self.assertEqual(0, episode.summary.interactions_used)
        self.assertEqual(0.0, episode.summary.success_adjusted_efficiency)


class TestLearningAndFairness(unittest.TestCase):
    def test_domain_landscape_is_not_mutated(self):
        domain = _small_domain(failing_first_edge=True)
        before = domain.topology_sha256()
        run_ablation_replicate(
            domain,
            "A_HIST",
            episode_count=2,
            interaction_budget=1,
        )
        self.assertEqual(before, domain.topology_sha256())
        self.assertEqual(0, domain.landscape.historization.tau)

    def test_failure_consumes_interaction_and_stays_at_source(self):
        result = run_ablation_replicate(
            _small_domain(failing_first_edge=True),
            "A_HIST",
            episode_count=1,
            interaction_budget=1,
        )
        summary = result.episodes[0].summary
        self.assertEqual(1, summary.interactions_used)
        self.assertEqual(1, summary.failure_count)
        self.assertEqual("S", summary.final_state)
        self.assertEqual(("S",), summary.path)

    def test_failure_is_inscribed(self):
        domain = _small_domain(failing_first_edge=True)
        adapter = build_ablation_adapter("A_HIST", domain)
        run_ablation_episode(domain, adapter, 0, interaction_budget=1)
        self.assertGreater(
            adapter.landscape.historization.failure_trace(
                next(
                    edge
                    for edge in adapter.landscape.edges
                    if edge.source == "S" and edge.target == "A"
                )
            ),
            0.0,
        )

    def test_recent_window_resets_between_episodes(self):
        domain = _small_domain()
        adapter = build_ablation_adapter("A_HIST", domain)
        run_ablation_episode(domain, adapter, 0, interaction_budget=1)
        self.assertTrue(adapter.recent)
        adapter.start_episode(1, domain.start)
        self.assertEqual([], adapter.recent)

    def test_learning_state_persists_between_episodes(self):
        domain = _small_domain(failing_first_edge=True)
        adapter = build_ablation_adapter("A_HIST", domain)
        run_ablation_episode(domain, adapter, 0, interaction_budget=1)
        tau = adapter.landscape.historization.tau
        run_ablation_episode(domain, adapter, 1, interaction_budget=1)
        self.assertGreater(adapter.landscape.historization.tau, tau)

    def test_all_methods_receive_equal_bounded_budget(self):
        for method in ABLATION_METHODS:
            with self.subTest(method=method):
                result = run_ablation_replicate(
                    _small_domain(),
                    method,
                    episode_count=1,
                    interaction_budget=1,
                )
                self.assertEqual(1, result.episodes[0].summary.interaction_budget)
                self.assertLessEqual(
                    result.episodes[0].summary.interactions_used,
                    1,
                )

    def test_all_methods_complete_small_full_budget_episode(self):
        for method in ABLATION_METHODS:
            with self.subTest(method=method):
                result = run_ablation_replicate(
                    _small_domain(),
                    method,
                    episode_count=1,
                    interaction_budget=16,
                )
                self.assertEqual("completed", result.episodes[0].status)
                self.assertLessEqual(result.episodes[0].summary.interactions_used, 16)

    def test_replicate_is_deterministic_except_wall_clock(self):
        first = run_ablation_replicate(
            _small_domain(),
            "D_U1_PHASE",
            episode_count=2,
            interaction_budget=4,
        )
        second = run_ablation_replicate(
            _small_domain(),
            "D_U1_PHASE",
            episode_count=2,
            interaction_budget=4,
        )
        for left, right in zip(first.episodes, second.episodes):
            self.assertEqual(left.summary.to_record(), right.summary.to_record())
            left_record = left.to_record()
            right_record = right.to_record()
            left_record.pop("wall_time_ms")
            right_record.pop("wall_time_ms")
            self.assertEqual(left_record, right_record)

    def test_result_marks_no_holdout_and_no_g1_result(self):
        record = run_ablation_replicate(
            _small_domain(),
            "A_HIST",
            episode_count=1,
            interaction_budget=1,
        ).to_record()
        self.assertFalse(record["holdout_accessed"])
        self.assertTrue(record["not_g1_result"])
        self.assertEqual("development", record["split"])


class TestAblationCompatibilityHarness(unittest.TestCase):
    def test_complete_600_cell_development_matrix(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            manifest = run_ablation_compatibility(output)
            self.assertEqual(120, manifest["counts"]["domain_instances"])
            self.assertEqual(5, manifest["counts"]["methods"])
            self.assertEqual(600, manifest["counts"]["planned_adapter_runs"])
            self.assertEqual(600, manifest["counts"]["completed_adapter_runs"])
            self.assertEqual(0, manifest["counts"]["path_cap_hits"])
            records = [
                json.loads(line)
                for line in (output / "ablation_compatibility.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            self.assertEqual(600, len(records))
            self.assertEqual(set(ABLATION_METHODS), {item["method"] for item in records})
            self.assertEqual(
                {
                    (domain.family, domain.target_node_count, domain.generator_seed)
                    for domain in build_development_matrix()
                },
                {
                    (
                        item["domain_family"],
                        item["target_node_count"],
                        item["generator_seed"],
                    )
                    for item in records
                },
            )
            self.assertTrue(all(not item["full_protocol_budget"] for item in records))
            self.assertTrue(all(item["not_g1_result"] for item in records))
            self.assertTrue(all(not item["holdout_accessed"] for item in records))

    def test_harness_writes_only_declared_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            run_ablation_compatibility(
                output,
                families=["wall_grid"],
                scales=[100],
                seeds=[0],
                methods=["A_HIST"],
            )
            self.assertEqual(
                {
                    "frozen_configs.json",
                    "ablation_compatibility.jsonl",
                    "environment.json",
                    "manifest.json",
                },
                {path.name for path in output.iterdir()},
            )

    def test_harness_refuses_overwrite_without_flag(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            run_ablation_compatibility(
                output,
                families=["wall_grid"],
                scales=[100],
                seeds=[0],
                methods=["A_HIST"],
            )
            with self.assertRaises(FileExistsError):
                run_ablation_compatibility(
                    output,
                    families=["wall_grid"],
                    scales=[100],
                    seeds=[0],
                    methods=["A_HIST"],
                )
            run_ablation_compatibility(
                output,
                families=["wall_grid"],
                scales=[100],
                seeds=[0],
                methods=["A_HIST"],
                overwrite=True,
            )

    def test_harness_rejects_holdout_seed(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(HoldoutAccessError):
                run_ablation_compatibility(
                    Path(directory),
                    families=["wall_grid"],
                    scales=[100],
                    seeds=[1000],
                )

    def test_manifest_does_not_select_or_rank_methods(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = run_ablation_compatibility(
                Path(directory),
                families=["wall_grid"],
                scales=[100],
                seeds=[0],
            )
            encoded = json.dumps(manifest, sort_keys=True)
            self.assertNotIn("selected_control", encoded)
            self.assertNotIn("ranking", encoded)
            self.assertIn("No performance comparison", manifest["scope_note"])


if __name__ == "__main__":
    unittest.main()
