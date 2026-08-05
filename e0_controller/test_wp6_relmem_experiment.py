"""
Contract tests for the WP-6.2 harness (`E0-WP6-RELMEM-v1`).

These are no-outcome tests: they validate determinism, seed separation, arm
semantics, budget accounting, metric definitions, and the object-under-test
freeze. They do not produce or interpret preregistered decision outcomes.
"""
from __future__ import annotations

import random

import pytest

from e0_controller.wp6_relmem_experiment import (
    ARMS,
    CALL_BUDGET,
    DRIFT_AT_CALL,
    GENERATOR_SEEDS,
    K_TOOLS,
    PROTOCOL_ID,
    REGIMES,
    RELIABILITY_LEVELS,
    STEP_TYPES,
    TOOLS,
    MemoryArm,
    OracleArm,
    StickyArm,
    ToolEnvironment,
    _recovery_metrics,
    build_arm,
    evaluate,
    paired_bootstrap,
    run_replicate,
    verify_object_under_test,
)


class TestObjectUnderTestFreeze:
    def test_lean_package_matches_frozen_hashes(self):
        verify_object_under_test()


class TestEnvironment:
    def test_table_is_deterministic_per_seed(self):
        a = ToolEnvironment("R1_persistent", 3)
        b = ToolEnvironment("R1_persistent", 3)
        assert a._table == b._table

    def test_tables_differ_across_seeds_and_regimes(self):
        assert ToolEnvironment("R1_persistent", 0)._table != ToolEnvironment(
            "R1_persistent", 1
        )._table
        assert ToolEnvironment("R1_persistent", 0)._table != ToolEnvironment(
            "R2_drift", 0
        )._table

    def test_reliabilities_come_from_frozen_levels(self):
        env = ToolEnvironment("R3_context", 7)
        assert set(env._table.values()) <= set(RELIABILITY_LEVELS)

    def test_r1_table_never_changes(self):
        env = ToolEnvironment("R1_persistent", 0)
        before = dict(env._table)
        for _ in range(CALL_BUDGET):
            env.call(0, STEP_TYPES[0], TOOLS[0])
        assert env._table == before
        assert env.call_count == CALL_BUDGET

    def test_r2_drift_redraws_at_call_500(self):
        env = ToolEnvironment("R2_drift", 0)
        before = dict(env._table)
        for _ in range(DRIFT_AT_CALL):
            env.call(0, STEP_TYPES[0], TOOLS[0])
        assert env._table == before, "no drift during the first 500 calls"
        env.call(0, STEP_TYPES[0], TOOLS[0])
        assert env.drifted
        assert env._table != before

    def test_r3_reliability_depends_on_task_type(self):
        for seed in GENERATOR_SEEDS:
            env = ToolEnvironment("R3_context", seed)
            values = {
                (tt, step, tool): env.reliability(tt, step, tool)
                for tt in range(3)
                for step in STEP_TYPES
                for tool in TOOLS
            }
            if len(set(values.values())) > 1 and any(
                values[(0, s, t)] != values[(1, s, t)]
                for s in STEP_TYPES
                for t in TOOLS
            ):
                return
        pytest.fail("no seed shows task-type-dependent reliabilities")

    def test_budget_is_enforced(self):
        env = ToolEnvironment("R1_persistent", 0)
        for _ in range(CALL_BUDGET):
            env.call(0, STEP_TYPES[0], TOOLS[0])
        with pytest.raises(RuntimeError):
            env.call(0, STEP_TYPES[0], TOOLS[0])


class TestArms:
    def test_sticky_repeats_success_and_forgets_on_failure(self):
        arm = StickyArm(random.Random(0), "R1_persistent")
        env = ToolEnvironment("R1_persistent", 0)
        arm.observe(0, STEP_TYPES[0], "tool_2", True)
        assert arm.choose(env, 0, STEP_TYPES[0]) == "tool_2"
        arm.observe(0, STEP_TYPES[0], "tool_2", False)
        assert arm._last_success.get(STEP_TYPES[0]) is None

    def test_sticky_context_key_includes_task_type_only_in_r3(self):
        r1 = StickyArm(random.Random(0), "R1_persistent")
        r3 = StickyArm(random.Random(0), "R3_context")
        assert r1._context(2, STEP_TYPES[1]) == STEP_TYPES[1]
        assert r3._context(2, STEP_TYPES[1]) == f"t2:{STEP_TYPES[1]}"

    def test_oracle_picks_argmax_of_current_table(self):
        env = ToolEnvironment("R1_persistent", 5)
        arm = OracleArm()
        for step in STEP_TYPES:
            best = arm.choose(env, 0, step)
            best_rel = env.reliability(0, step, best)
            assert best_rel == max(env.reliability(0, step, t) for t in TOOLS)

    def test_memory_arm_is_context_free_in_r3(self):
        arm = build_arm("MEMORY", "R3_context", 0)
        for tt in range(3):
            for _ in range(3):
                arm.observe(tt, STEP_TYPES[0], "tool_1", True)
        rec = arm.store.recommend(STEP_TYPES[0], list(TOOLS))
        assert rec.recommended == "tool_1", "observations pool across task types"

    def test_memory_arm_learns_away_from_failing_tool(self):
        arm = build_arm("MEMORY", "R1_persistent", 0)
        for _ in range(10):
            arm.observe(0, STEP_TYPES[0], "tool_0", False)
            arm.observe(0, STEP_TYPES[0], "tool_3", True)
        env = ToolEnvironment("R1_persistent", 0)
        assert arm.choose(env, 0, STEP_TYPES[0]) == "tool_3"


class TestReplicates:
    def test_replicate_is_deterministic(self):
        a = run_replicate("R1_persistent", "MEMORY", 0)
        b = run_replicate("R1_persistent", "MEMORY", 0)
        assert a.record() == b.record()

    def test_replicate_spends_exactly_the_budget(self):
        for arm in ARMS:
            r = run_replicate("R1_persistent", arm, 1)
            assert r.calls == CALL_BUDGET

    def test_wasted_calls_only_counts_low_reliability_tools(self):
        r = run_replicate("R1_persistent", "ORACLE", 2)
        env = ToolEnvironment("R1_persistent", 2)
        best_rels = {
            step: max(env.reliability(0, step, t) for t in TOOLS)
            for step in STEP_TYPES
        }
        if all(rel > 0.25 for rel in best_rels.values()):
            assert r.wasted_calls == 0

    def test_r2_records_recovery_fields(self):
        r = run_replicate("R2_drift", "STICKY", 0)
        data = r.record()
        assert "pre_drift_level" in data and "recovery_calls" in data

    def test_recovery_metric_on_synthetic_log(self):
        log = [1] * DRIFT_AT_CALL + [0] * 100 + [1] * 400
        pre, recovery, recovered = _recovery_metrics(log)
        assert pre == 1.0
        assert recovered
        # first trailing-50 window at >= 90% of 1.0 needs 45 successes:
        # windows start containing successes from call 600 on.
        assert 100 < recovery <= 200

    def test_zero_pre_drift_level_short_circuits(self):
        log = [0] * DRIFT_AT_CALL + [1] * DRIFT_AT_CALL
        pre, recovery, recovered = _recovery_metrics(log)
        assert pre == 0.0 and recovery == 0 and recovered


class TestStatisticsAndCriteria:
    def test_paired_bootstrap_is_deterministic_and_sane(self):
        t = [3.0, 5.0, 5.0, 4.0, 7.0] * 6
        c = [2.0, 3.0, 4.5, 3.0, 5.0] * 6
        a = paired_bootstrap(t, c)
        b = paired_bootstrap(t, c)
        assert a == b
        assert a["mean_difference"] == pytest.approx(1.3)
        assert a["ci95_lower"] <= a["mean_difference"] + 1e-9
        assert a["mean_difference"] <= a["ci95_upper"] + 1e-9
        assert a["ci95_lower"] > 0

    def test_paired_bootstrap_rejects_unpaired_input(self):
        with pytest.raises(ValueError):
            paired_bootstrap([1.0], [1.0, 2.0])

    def test_evaluate_applies_frozen_criteria_shape(self):
        results = []
        for regime in REGIMES:
            for arm in ARMS:
                for seed in range(3):
                    r = run_replicate(regime, arm, seed)
                    results.append(r)
        summary = evaluate(results)
        assert summary["protocol_id"] == PROTOCOL_ID
        assert summary["verdict"] in ("PASS", "FAIL")
        assert set(summary["criteria"]) == {
            "c1_r1_beats_no_memory_lift10",
            "c2_r1_beats_sticky",
            "c3_stress_non_inferiority",
            "sticky_doc_note_required",
        }
        for regime in REGIMES:
            assert "MEMORY_vs_NO_MEMORY" in summary["comparisons"][regime]
            assert "MEMORY_vs_STICKY" in summary["comparisons"][regime]
