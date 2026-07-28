"""WP-2.2 tests for fair Gate G1 baseline adapters."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from .g1_baseline_harness import run_baseline_compatibility
from .g1_baselines import (
    ALL_BASELINE_METHODS,
    COMPETITIVE_METHODS,
    CONFIG_PATH,
    DIAGNOSTIC_METHODS,
    MAP_REFERENCE_METHODS,
    METHOD_CONTRACTS,
    ActionView,
    AStarAdapter,
    DStarLiteAdapter,
    DStarLitePlanner,
    EpisodeSummary,
    MapView,
    MemorylessGreedyAdapter,
    QLearningAdapter,
    RandomRestartGreedyAdapter,
    UCB1EdgeAdapter,
    astar_shortest_path,
    baseline_config_sha256,
    bfs_shortest_path,
    build_adapter,
    load_baseline_configs,
    run_episode,
    run_replicate,
    validate_method_registry,
)
from .g1_domains import (
    G1DomainInstance,
    HoldoutAccessError,
    OutcomeRule,
    build_development_matrix,
    build_domain,
    load_g1_protocol,
)
from .landscape import Landscape


class TestBaselineRegistry(unittest.TestCase):
    def test_registry_exactly_matches_protocol(self):
        validate_method_registry()
        baselines = load_g1_protocol()["baselines"]
        self.assertEqual(
            COMPETITIVE_METHODS,
            tuple(baselines["competitive_G1_B"]),
        )
        self.assertEqual(DIAGNOSTIC_METHODS, tuple(baselines["diagnostic"]))
        self.assertEqual(
            MAP_REFERENCE_METHODS,
            tuple(baselines["map_informed_upper_references"]),
        )

    def test_all_eight_methods_have_one_contract(self):
        self.assertEqual(8, len(ALL_BASELINE_METHODS))
        self.assertEqual(set(ALL_BASELINE_METHODS), set(METHOD_CONTRACTS))

    def test_only_competitive_methods_are_comparator_eligible(self):
        eligible = {
            method for method, contract in METHOD_CONTRACTS.items() if contract.comparator_eligible
        }
        self.assertEqual(set(COMPETITIVE_METHODS), eligible)

    def test_only_upper_references_receive_map(self):
        informed = {
            method for method, contract in METHOD_CONTRACTS.items() if contract.receives_full_map
        }
        self.assertEqual(set(MAP_REFERENCE_METHODS), informed)

    def test_bfs_is_oracle_not_preregistered_method(self):
        self.assertNotIn("BFS", ALL_BASELINE_METHODS)
        config = load_baseline_configs()
        self.assertIn("oracle", config["audit"]["bfs"])

    def test_frozen_config_is_protocol_bound(self):
        config = load_baseline_configs()
        self.assertTrue(config["frozen_before_holdout"])
        self.assertFalse(config["holdout_execution_started"])
        self.assertEqual(set(ALL_BASELINE_METHODS), set(config["methods"]))
        self.assertEqual(64, len(baseline_config_sha256()))

    def test_config_records_primary_algorithm_sources(self):
        references = load_baseline_configs()["references"]
        self.assertEqual("10.1007/BF00992698", references["Q_LEARNING"]["doi"])
        self.assertEqual(
            "10.1023/A:1013689704352",
            references["UCB1_EDGE"]["doi"],
        )
        self.assertIn("publications.ri.cmu.edu", references["D_STAR_LITE"]["url"])


class TestInformationBoundary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.domain = build_domain("wall_grid", 100, 0)

    def test_equal_information_adapters_do_not_receive_map(self):
        for method in (*COMPETITIVE_METHODS, *DIAGNOSTIC_METHODS):
            with self.subTest(method=method):
                self.assertIsNone(build_adapter(method, self.domain).map_view)

    def test_upper_references_receive_map(self):
        for method in MAP_REFERENCE_METHODS:
            with self.subTest(method=method):
                adapter = build_adapter(method, self.domain)
                self.assertIsNotNone(adapter.map_view)
                self.assertEqual(100, len(adapter.map_view.states))

    def test_astar_rejects_missing_map(self):
        with self.assertRaises(ValueError):
            AStarAdapter(goal="G", policy_seed=1, config={}, map_view=None)

    def test_dstar_rejects_missing_map(self):
        with self.assertRaises(ValueError):
            DStarLiteAdapter(goal="G", policy_seed=1, config={}, map_view=None)


class TestMapReferences(unittest.TestCase):
    def test_astar_matches_bfs_on_all_families_and_scales(self):
        for family in (
            "wall_grid",
            "trap_grid_v2",
            "decoy_dag",
            "nonstationary_parallel",
        ):
            for scale in (100, 500, 1000):
                with self.subTest(family=family, scale=scale):
                    domain = build_domain(family, scale, 0)
                    view = MapView.from_domain(domain)
                    self.assertEqual(
                        bfs_shortest_path(view, domain.start),
                        astar_shortest_path(view, domain.start),
                    )

    def test_dstar_initial_path_has_bfs_length(self):
        domain = build_domain("wall_grid", 100, 1)
        view = MapView.from_domain(domain)
        planner = DStarLitePlanner(view, domain.start)
        path = [domain.start]
        while path[-1] != domain.goal:
            target = planner.next_target()
            self.assertIsNotNone(target)
            path.append(target)
            planner.move_start(target)
        self.assertEqual(len(bfs_shortest_path(view, domain.start)), len(path))

    def test_dstar_replans_after_observed_block(self):
        domain = build_domain("wall_grid", 100, 2)
        view = MapView.from_domain(domain)
        planner = DStarLitePlanner(view, domain.start)
        blocked_target = planner.next_target()
        self.assertIsNotNone(blocked_target)
        planner.block_edge(domain.start, blocked_target)
        replacement = planner.next_target()
        self.assertIsNotNone(replacement)
        self.assertNotEqual(blocked_target, replacement)

    def test_astar_does_not_receive_hidden_outcome_probabilities(self):
        domain = build_domain("nonstationary_parallel", 100, 0)
        view = MapView.from_domain(domain)
        encoded = repr(view)
        self.assertNotIn("success_probability", encoded)
        self.assertNotIn("switch_at_episode", encoded)


class TestLearningAdapters(unittest.TestCase):
    def setUp(self):
        self.actions = (
            ActionView("S", "A", 0.1, 1.0),
            ActionView("S", "B", 0.2, 1.0),
        )

    def test_memoryless_greedy_uses_base_cost(self):
        adapter = MemorylessGreedyAdapter(
            goal="G",
            policy_seed=1,
            config={},
        )
        self.assertEqual("A", adapter.select_action(0, "S", self.actions).target)

    def test_stochastic_policy_is_reproducible(self):
        domain = build_domain("wall_grid", 100, 3)
        first = run_replicate(domain, "UNIFORM_RANDOM", episode_count=2)
        second = run_replicate(domain, "UNIFORM_RANDOM", episode_count=2)
        self.assertEqual(first.to_record(), second.to_record())

    def test_q_learning_failure_lowers_action_value(self):
        adapter = QLearningAdapter(
            goal="G",
            policy_seed=1,
            config=load_baseline_configs()["methods"]["Q_LEARNING"]["parameters"],
        )
        domain = _failure_domain()
        summary = run_episode(domain, adapter, 0, interaction_budget=1)
        self.assertEqual(1, summary.failure_count)
        self.assertLess(adapter.q_values[("S", "A")], 0.0)

    def test_ucb_tries_unobserved_edge_after_episode_credit(self):
        adapter = UCB1EdgeAdapter(
            goal="G",
            policy_seed=7,
            config=load_baseline_configs()["methods"]["UCB1_EDGE"]["parameters"],
        )
        first = adapter.select_action(0, "S", self.actions)
        adapter._episode_edges = [("S", first.target)]
        adapter.end_episode(_summary(goal_reached=False))
        second = adapter.select_action(1, "S", self.actions)
        self.assertNotEqual(first.target, second.target)

    def test_random_restart_penalizes_failed_edge(self):
        adapter = RandomRestartGreedyAdapter(
            goal="G",
            policy_seed=1,
            config={
                "restart_exploration_probability": 0.0,
                "immediate_failure_penalty": 1.0,
                "failed_episode_credit_penalty": 0.25,
                "success_penalty_decay": 0.9,
            },
        )
        self.assertEqual("A", adapter.select_action(0, "S", self.actions).target)
        adapter.penalties[("S", "A")] = 1.0
        self.assertEqual("B", adapter.select_action(1, "S", self.actions).target)

    def test_learning_state_persists_across_episodes(self):
        domain = build_domain("wall_grid", 100, 0)
        result = run_replicate(domain, "Q_LEARNING", episode_count=3)
        self.assertEqual(3, len(result.episodes))
        self.assertGreater(sum(e.interactions_used for e in result.episodes), 0)


class TestFairEpisodeRunner(unittest.TestCase):
    def test_failure_consumes_budget_without_moving(self):
        domain = _failure_domain()
        adapter = MemorylessGreedyAdapter(goal="G", policy_seed=1, config={})
        summary = run_episode(domain, adapter, 0, interaction_budget=3)
        self.assertFalse(summary.goal_reached)
        self.assertEqual(3, summary.interactions_used)
        self.assertEqual(3, summary.failure_count)
        self.assertEqual("S", summary.final_state)
        self.assertEqual(("S",), summary.path)

    def test_every_method_gets_same_episode_budget(self):
        domain = build_domain("trap_grid_v2", 100, 0)
        for method in ALL_BASELINE_METHODS:
            with self.subTest(method=method):
                result = run_replicate(domain, method, episode_count=1)
                episode = result.episodes[0]
                self.assertEqual(400, episode.interaction_budget)
                self.assertLessEqual(episode.interactions_used, 400)

    def test_default_replicate_has_preregistered_phase_counts(self):
        domain = build_domain("trap_grid_v2", 100, 1)
        result = run_replicate(domain, "A_STAR")
        self.assertEqual(30, len(result.episodes))
        self.assertEqual(
            10,
            sum(episode.phase == "adaptation" for episode in result.episodes),
        )
        self.assertEqual(
            20,
            sum(episode.phase == "evaluation" for episode in result.episodes),
        )

    def test_primary_score_is_zero_on_failure(self):
        summary = run_episode(
            _failure_domain(),
            MemorylessGreedyAdapter(goal="G", policy_seed=1, config={}),
            0,
            interaction_budget=2,
        )
        self.assertEqual(0.0, summary.success_adjusted_efficiency)

    def test_primary_score_uses_oracle_over_observed_interactions(self):
        domain = build_domain("trap_grid_v2", 100, 0)
        summary = run_replicate(domain, "A_STAR", episode_count=1).episodes[0]
        self.assertTrue(summary.goal_reached)
        self.assertEqual(
            summary.oracle_cost / max(summary.interactions_used, summary.oracle_cost),
            summary.success_adjusted_efficiency,
        )

    def test_result_labels_upper_references_ineligible(self):
        domain = build_domain("wall_grid", 100, 0)
        for method in MAP_REFERENCE_METHODS:
            record = run_replicate(
                domain,
                method,
                episode_count=1,
            ).to_record(include_episodes=False)
            self.assertFalse(record["comparator_eligible"])
            self.assertEqual("full_static_topology", record["information_access"])

    def test_holdout_seed_rejected_before_method_execution(self):
        with self.assertRaises(HoldoutAccessError):
            build_domain("wall_grid", 100, 1000)


class TestCompatibilityMatrix(unittest.TestCase):
    def test_all_adapters_complete_every_development_instance(self):
        completed = 0
        domains = list(build_development_matrix())
        for domain in domains:
            for method in ALL_BASELINE_METHODS:
                result = run_replicate(domain, method, episode_count=1)
                self.assertEqual(1, len(result.episodes))
                completed += 1
        self.assertEqual(960, completed)

    def test_all_methods_complete_full_protocol_on_one_instance(self):
        domain = build_domain("trap_grid_v2", 100, 4)
        for method in ALL_BASELINE_METHODS:
            with self.subTest(method=method):
                result = run_replicate(domain, method)
                self.assertEqual(30, len(result.episodes))
                self.assertEqual(20, len(result.evaluation_episodes))
                self.assertTrue(all(e.interactions_used <= 400 for e in result.episodes))

    def test_harness_writes_small_matrix_and_exact_config_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            manifest = run_baseline_compatibility(
                output,
                families=["wall_grid"],
                scales=[100],
                seeds=[0],
            )
            self.assertEqual(8, manifest["counts"]["completed_adapter_runs"])
            self.assertFalse(manifest["holdout_accessed"])
            self.assertTrue(manifest["not_g1_result"])
            self.assertEqual(
                CONFIG_PATH.read_bytes(),
                (output / "frozen_configs.json").read_bytes(),
            )
            records = (
                (output / "baseline_compatibility.jsonl").read_text(encoding="utf-8").splitlines()
            )
            self.assertEqual(8, len(records))
            self.assertEqual(
                set(ALL_BASELINE_METHODS),
                {json.loads(record)["method"] for record in records},
            )

    def test_harness_refuses_accidental_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            run_baseline_compatibility(
                output,
                families=["wall_grid"],
                scales=[100],
                seeds=[0],
                methods=["A_STAR"],
            )
            with self.assertRaises(FileExistsError):
                run_baseline_compatibility(
                    output,
                    families=["wall_grid"],
                    scales=[100],
                    seeds=[0],
                    methods=["A_STAR"],
                )

    def test_harness_rejects_holdout_seed(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(HoldoutAccessError):
                run_baseline_compatibility(
                    Path(temporary),
                    families=["wall_grid"],
                    scales=[100],
                    seeds=[1000],
                    methods=["A_STAR"],
                )


def _summary(*, goal_reached: bool) -> EpisodeSummary:
    return EpisodeSummary(
        episode_index=0,
        phase="adaptation",
        goal_reached=goal_reached,
        interactions_used=1,
        interaction_budget=1,
        total_cost=1.0,
        oracle_cost=1,
        success_adjusted_efficiency=1.0 if goal_reached else 0.0,
        revisits=0,
        failure_count=0 if goal_reached else 1,
        terminal_reason="goal_reached" if goal_reached else "no_action",
        final_state="G" if goal_reached else "S",
        path=("S", "G") if goal_reached else ("S",),
    )


def _failure_domain() -> G1DomainInstance:
    landscape = Landscape()
    landscape.add_edge("S", "A", delta=0.01, resistance=0.1)
    landscape.add_edge("S", "G", delta=1.0, resistance=1.0)
    return G1DomainInstance(
        family="test_failure_domain",
        target_node_count=3,
        generator_seed=0,
        landscape=landscape,
        start="S",
        goal="G",
        oracle_cost_by_regime={"stationary": 1},
        outcome_rules=(OutcomeRule("S", "A", 0.0),),
    )


if __name__ == "__main__":
    unittest.main()
