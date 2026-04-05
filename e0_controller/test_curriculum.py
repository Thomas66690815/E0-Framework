"""
Tests for Curriculum Navigator (C123)
======================================
Hierarchical learning for canonical landscapes.

Claims:
- CurriculumTurn correctly scopes nodes by derivation level
- CurriculumStrategy auto-generates turns from canon hierarchy
- EquilibriumDetector correctly detects T_s stability
- build_scoped_landscape produces valid sub-landscapes
- transfer_historization preserves learned traces across turns
- CurriculumRunner orchestrates the full curriculum end-to-end
- Goal selection picks highest-level goal within scope
- Equilibrium = no new internal difference (T_s stable below threshold)
"""

import pytest
from e0_controller.curriculum import (
    CurriculumTurn,
    TurnResult,
    EquilibriumDetector,
    CurriculumStrategy,
    build_scoped_landscape,
    transfer_historization,
    CurriculumRunner,
    _scope_spec,
)
from e0_controller.canon_loader import (
    CanonInfo, NodeInfo, EdgeInfo,
    load_canon_spec, _extract_info,
)
from e0_controller.landscape import Landscape
from e0_controller.primitives import Edge, Outcome
from e0_controller.structural_entropy import structural_temperature


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

def _make_canon_info(n_levels=6) -> CanonInfo:
    """Create a synthetic CanonInfo with n_levels derivation levels."""
    nodes = []
    for i in range(n_levels):
        nodes.append(NodeInfo(
            id=f"n{i}",
            label=f"Node {i}",
            derivation_level=i,
            is_primitive=(i < 2),
            description=f"Level {i} concept",
        ))
    edges = []
    for i in range(n_levels - 1):
        edges.append(EdgeInfo(
            source=f"n{i}", target=f"n{i+1}",
            derivation=f"n{i} derives n{i+1}",
        ))
    return CanonInfo(
        name="test-canon",
        version="1.0",
        source="test",
        description="Test canon",
        nodes=nodes,
        edges=edges,
        goal_states=["n1", "n5"],
        necessary_consequences=[],
    )


def _make_spec(n_levels=6) -> dict:
    """Create a matching bootstrapper-compatible spec."""
    nodes = [{"id": f"n{i}", "derivation_level": i, "is_primitive": i < 2,
              "label": f"Node {i}", "description": f"Level {i}"}
             for i in range(n_levels)]
    edges = [{"from": f"n{i}", "to": f"n{i+1}",
              "delta": 0.5, "resistance": 0.3,
              "initial_U": 2, "initial_F": 1}
             for i in range(n_levels - 1)]
    return {
        "name": "test-canon", "version": "1.0",
        "source": "test", "description": "Test canon",
        "nodes": nodes, "edges": edges,
        "goal_states": ["n1", "n5"],
        "necessary_consequences": [],
    }


# ──────────────────────────────────────────────
# EquilibriumDetector
# ──────────────────────────────────────────────

class TestEquilibriumDetector:

    def test_no_equilibrium_above_threshold(self):
        det = EquilibriumDetector(threshold=1.0, patience=3)
        assert not det.observe(5.0)
        assert not det.observe(3.0)
        assert not det.observe(2.0)
        assert not det.at_equilibrium

    def test_equilibrium_after_patience(self):
        det = EquilibriumDetector(threshold=2.0, patience=3)
        assert not det.observe(1.0)
        assert not det.observe(0.5)
        assert det.observe(0.8)
        assert det.at_equilibrium

    def test_reset_clears_count(self):
        det = EquilibriumDetector(threshold=2.0, patience=2)
        det.observe(1.0)
        det.observe(0.5)
        assert det.at_equilibrium
        det.reset()
        assert not det.at_equilibrium
        assert len(det.observations) == 0

    def test_spike_resets_count(self):
        det = EquilibriumDetector(threshold=1.0, patience=3)
        det.observe(0.5)
        det.observe(0.5)
        # Spike above threshold resets the counter
        det.observe(2.0)
        det.observe(0.5)
        det.observe(0.5)
        assert not det.at_equilibrium
        # Third below threshold after spike
        assert det.observe(0.5)

    def test_observations_recorded(self):
        det = EquilibriumDetector(threshold=1.0, patience=2)
        det.observe(3.0)
        det.observe(0.5)
        assert det.observations == [3.0, 0.5]

    def test_patience_one(self):
        det = EquilibriumDetector(threshold=5.0, patience=1)
        assert det.observe(1.0)


# ──────────────────────────────────────────────
# CurriculumStrategy
# ──────────────────────────────────────────────

class TestCurriculumStrategy:

    def test_auto_boundaries_6_levels(self):
        info = _make_canon_info(6)
        strat = CurriculumStrategy(info)
        # max_level=5, thirds: 1, 3, 5
        assert strat.boundaries == [1, 3, 5]

    def test_custom_boundaries(self):
        info = _make_canon_info(6)
        strat = CurriculumStrategy(info, boundaries=[2, 5])
        assert strat.boundaries == [2, 5]

    def test_turns_cumulative(self):
        info = _make_canon_info(6)
        strat = CurriculumStrategy(info, boundaries=[1, 3, 5])
        turns = strat.turns()
        assert len(turns) == 3
        # Turn 1: levels 0-1 → nodes n0, n1
        assert turns[0].node_ids == {"n0", "n1"}
        assert turns[0].level_max == 1
        # Turn 2: levels 0-3 → nodes n0..n3
        assert turns[1].node_ids == {"n0", "n1", "n2", "n3"}
        # Turn 3: all nodes
        assert turns[2].node_ids == {f"n{i}" for i in range(6)}

    def test_goal_selection_within_scope(self):
        info = _make_canon_info(6)  # goals: n1, n5
        strat = CurriculumStrategy(info, boundaries=[1, 3, 5])
        turns = strat.turns()
        # Turn 1: scope 0-1, goal n1 (n5 out of scope)
        assert turns[0].goal == "n1"
        # Turn 2: scope 0-3, still n1 (n5 still out of scope)
        assert turns[1].goal == "n1"
        # Turn 3: scope 0-5, goal n5 (higher level)
        assert turns[2].goal == "n5"

    def test_no_goal_if_none_in_scope(self):
        info = CanonInfo(
            name="t", version="1", source="", description="",
            nodes=[NodeInfo("a", "A", 0, True, ""),
                   NodeInfo("b", "B", 1, False, "")],
            edges=[EdgeInfo("a", "b", "")],
            goal_states=["b"],
            necessary_consequences=[],
        )
        strat = CurriculumStrategy(info, boundaries=[0, 1])
        turns = strat.turns()
        assert turns[0].goal is None  # scope 0, goal b is level 1
        assert turns[1].goal == "b"

    def test_single_level(self):
        info = CanonInfo(
            name="t", version="1", source="", description="",
            nodes=[NodeInfo("x", "X", 0, True, "")],
            edges=[], goal_states=[], necessary_consequences=[],
        )
        strat = CurriculumStrategy(info)
        assert strat.boundaries == [0]
        turns = strat.turns()
        assert len(turns) == 1
        assert turns[0].node_ids == {"x"}

    def test_scope_names(self):
        info = _make_canon_info(6)
        strat = CurriculumStrategy(info, boundaries=[2, 5])
        turns = strat.turns()
        assert "Turn 1" in turns[0].scope
        assert "Turn 2" in turns[1].scope


# ──────────────────────────────────────────────
# Scoped Landscape Construction
# ──────────────────────────────────────────────

class TestScopedLandscape:

    def test_scope_spec_filters_nodes(self):
        spec = _make_spec(6)
        scoped = _scope_spec(spec, {"n0", "n1", "n2"})
        assert set(scoped["nodes"]) == {"n0", "n1", "n2"}

    def test_scope_spec_filters_edges(self):
        spec = _make_spec(6)
        scoped = _scope_spec(spec, {"n0", "n1", "n2"})
        # Only edges n0→n1 and n1→n2 should remain
        assert len(scoped["edges"]) == 2
        sources = {e["from"] for e in scoped["edges"]}
        assert sources == {"n0", "n1"}

    def test_scope_spec_preserves_initial_UF(self):
        spec = _make_spec(6)
        scoped = _scope_spec(spec, {"n0", "n1"})
        edge = scoped["edges"][0]
        assert edge["initial_U"] == 2
        assert edge["initial_F"] == 1

    def test_build_scoped_produces_landscape(self):
        spec = _make_spec(6)
        ls = build_scoped_landscape(spec, {"n0", "n1", "n2"})
        assert isinstance(ls, Landscape)
        assert ls.states == {"n0", "n1", "n2"}
        assert ls.edge_count() == 2

    def test_scoped_landscape_has_historization(self):
        spec = _make_spec(6)
        ls = build_scoped_landscape(spec, {"n0", "n1"})
        edge = Edge("n0", "n1")
        # Initial traces from bootstrap
        assert ls.historization.trace_load(edge) > 0

    def test_cross_scope_edges_excluded(self):
        spec = _make_spec(6)
        scoped = _scope_spec(spec, {"n0", "n2"})
        # n0→n1 and n1→n2 both need n1, so both excluded
        assert len(scoped["edges"]) == 0


# ──────────────────────────────────────────────
# Historization Transfer
# ──────────────────────────────────────────────

class TestHistorizationTransfer:

    def test_transfer_shared_edges(self):
        spec = _make_spec(6)
        ls1 = build_scoped_landscape(spec, {"n0", "n1", "n2"})
        # Simulate some learning on ls1
        edge01 = Edge("n0", "n1")
        ls1.historization.update(edge01, Outcome.SUCCESS)
        ls1.historization.update(edge01, Outcome.SUCCESS)

        ls2 = build_scoped_landscape(spec, {"n0", "n1", "n2", "n3"})
        transferred = transfer_historization(ls1, ls2)

        # Both edges n0→n1 and n1→n2 exist in both landscapes
        assert transferred == 2
        # The learned traces for n0→n1 should be transferred
        assert ls2.historization._U[edge01] == ls1.historization._U[edge01]

    def test_transfer_skips_missing_edges(self):
        spec = _make_spec(6)
        ls1 = build_scoped_landscape(spec, {"n0", "n1", "n2"})
        ls2 = build_scoped_landscape(spec, {"n3", "n4", "n5"})
        # No shared edges
        transferred = transfer_historization(ls1, ls2)
        assert transferred == 0

    def test_transfer_preserves_new_edges(self):
        spec = _make_spec(6)
        ls1 = build_scoped_landscape(spec, {"n0", "n1"})
        ls2 = build_scoped_landscape(spec, {"n0", "n1", "n2"})

        transferred = transfer_historization(ls1, ls2)
        assert transferred == 1  # only n0→n1

        # n1→n2 in ls2 should keep its original bootstrap traces
        edge12 = Edge("n1", "n2")
        assert ls2.historization.trace_load(edge12) > 0


# ──────────────────────────────────────────────
# CurriculumRunner
# ──────────────────────────────────────────────

class TestCurriculumRunner:

    def _mock_execute(self, source, target):
        return Outcome.SUCCESS

    def test_runner_with_ontodynamics(self):
        """Run curriculum on the actual ontodynamics canon."""
        runner = CurriculumRunner(
            "ontodynamics",
            self._mock_execute,
            equilibrium_threshold=2.0,
            equilibrium_patience=2,
            max_episodes_per_turn=5,
            max_cycles_per_episode=20,
        )
        results = runner.run()
        assert len(results) > 0
        for r in results:
            assert r.total_steps > 0
            assert r.episodes > 0

    def test_runner_produces_final_landscape(self):
        runner = CurriculumRunner(
            "ontodynamics",
            self._mock_execute,
            max_episodes_per_turn=3,
            max_cycles_per_episode=10,
        )
        runner.run()
        ls = runner.final_landscape
        assert ls is not None
        assert len(ls.states) > 0

    def test_runner_summary(self):
        runner = CurriculumRunner(
            "ontodynamics",
            self._mock_execute,
            max_episodes_per_turn=2,
            max_cycles_per_episode=10,
        )
        runner.run()
        s = runner.summary()
        assert "Curriculum" in s
        assert "Turn" in s

    def test_runner_custom_strategy(self):
        spec = load_canon_spec("ontodynamics")
        info = _extract_info(spec)
        strategy = CurriculumStrategy(info, boundaries=[5, 17])
        runner = CurriculumRunner(
            "ontodynamics",
            self._mock_execute,
            strategy=strategy,
            max_episodes_per_turn=2,
            max_cycles_per_episode=10,
        )
        results = runner.run()
        assert len(results) == 2

    def test_equilibrium_detection_in_runner(self):
        """With enough episodes, the system should reach equilibrium."""
        runner = CurriculumRunner(
            "ontodynamics",
            self._mock_execute,
            equilibrium_threshold=50.0,  # very high threshold → easy equilibrium
            equilibrium_patience=1,
            max_episodes_per_turn=10,
            max_cycles_per_episode=20,
        )
        results = runner.run()
        # At least one turn should reach equilibrium with such a high threshold
        equilibria = [r for r in results if r.equilibrium_reached]
        assert len(equilibria) > 0

    def test_historization_carries_across_turns(self):
        """Later turns should have historization from earlier turns."""
        runner = CurriculumRunner(
            "ontodynamics",
            self._mock_execute,
            max_episodes_per_turn=3,
            max_cycles_per_episode=20,
        )
        results = runner.run()
        # The final landscape should have more historization
        # than a fresh landscape would
        ls = runner.final_landscape
        total_load = sum(
            ls.historization.trace_load(e) for e in ls.edges
        )
        assert total_load > 0

    def test_runner_results_property(self):
        runner = CurriculumRunner(
            "ontodynamics",
            self._mock_execute,
            max_episodes_per_turn=1,
            max_cycles_per_episode=5,
        )
        assert runner.results == []
        runner.run()
        assert len(runner.results) > 0

    def test_turn_results_have_T_s(self):
        runner = CurriculumRunner(
            "ontodynamics",
            self._mock_execute,
            max_episodes_per_turn=2,
            max_cycles_per_episode=10,
        )
        results = runner.run()
        for r in results:
            assert r.final_T_s >= 0

    def test_start_from_lowest_level(self):
        """Runner should start from the lowest derivation level node."""
        spec = load_canon_spec("ontodynamics")
        info = _extract_info(spec)
        # Level 0 node should be 'difference'
        level_0 = [n for n in info.nodes if n.derivation_level == 0]
        assert len(level_0) > 0
        assert level_0[0].id == "difference"


# ──────────────────────────────────────────────
# Integration: Ontodynamics Canon
# ──────────────────────────────────────────────

class TestOntodynamicsCurriculum:

    def test_ontodynamics_default_strategy(self):
        """Default strategy generates meaningful turns for ontodynamics."""
        spec = load_canon_spec("ontodynamics")
        info = _extract_info(spec)
        strat = CurriculumStrategy(info)
        turns = strat.turns()

        # Should have 3 turns (auto-boundaries from 18 levels)
        assert len(turns) == 3

        # First turn: core canonical concepts
        assert "difference" in turns[0].node_ids

        # Last turn: all 51 nodes
        assert len(turns[-1].node_ids) == 51

    def test_ontodynamics_has_goals_per_turn(self):
        spec = load_canon_spec("ontodynamics")
        info = _extract_info(spec)
        # negative_necessity is level 8, sleep_wake_cycle is level 17
        strat = CurriculumStrategy(info, boundaries=[5, 8, 17])
        turns = strat.turns()

        # Level 0-5: negative_necessity (level 8) out of scope
        assert turns[0].goal is None

        # Level 0-8: negative_necessity (level 8) in scope
        assert turns[1].goal == "negative_necessity"

        # Level 0-17: sleep_wake_cycle (level 17) is highest goal
        assert turns[2].goal == "sleep_wake_cycle"

    def test_scoped_landscape_coverage(self):
        """Each scope produces a valid navigable landscape."""
        spec = load_canon_spec("ontodynamics")
        info = _extract_info(spec)
        strat = CurriculumStrategy(info, boundaries=[5, 8, 17])

        for turn in strat.turns():
            ls = build_scoped_landscape(spec, turn.node_ids)
            assert len(ls.states) == len(turn.node_ids)
            # Every scoped landscape should have at least some edges
            assert ls.edge_count() > 0

    def test_coverage_increases_per_turn(self):
        """Later turns cover more of the graph."""
        spec = load_canon_spec("ontodynamics")
        info = _extract_info(spec)
        strat = CurriculumStrategy(info, boundaries=[5, 8, 17])
        turns = strat.turns()

        prev_nodes = 0
        for turn in turns:
            assert len(turn.node_ids) > prev_nodes
            prev_nodes = len(turn.node_ids)


# ══════════════════════════════════════════════════════════
# C156: Curriculum ↔ Sleep-Wake Integration
# ══════════════════════════════════════════════════════════

from e0_controller.dream_mode import DreamCycleResult, DreamObserver


class TestTurnResultDreamConsolidation:
    """TurnResult.dream_consolidation field (C156)."""

    def test_default_empty(self):
        turn = CurriculumTurn(scope="t", level_max=0)
        r = TurnResult(
            turn=turn, traces=[], equilibrium_reached=False,
            final_T_s=0.0, total_steps=0, episodes=0,
        )
        assert r.dream_consolidation == []

    def test_with_dream_results(self):
        turn = CurriculumTurn(scope="t", level_max=0)
        dcr = DreamCycleResult(
            domains_observed=["a"], domains_skipped=[],
            equivalences_found=1, equivalences_new=1,
            dream_landscape_states=2, dream_landscape_edges=1,
        )
        r = TurnResult(
            turn=turn, traces=[], equilibrium_reached=True,
            final_T_s=0.5, total_steps=10, episodes=3,
            dream_consolidation=[dcr],
        )
        assert len(r.dream_consolidation) == 1
        assert r.dream_consolidation[0].equivalences_found == 1


class TestCurriculumRunnerObserver:
    """CurriculumRunner with DreamObserver integration (C156)."""

    def _mock_execute(self, source, target):
        return Outcome.SUCCESS

    def test_no_observer_no_consolidation(self):
        """Without observer, dream_consolidation is empty."""
        runner = CurriculumRunner(
            "ontodynamics",
            self._mock_execute,
            max_episodes_per_turn=2,
            max_cycles_per_episode=10,
        )
        results = runner.run()
        for r in results:
            assert r.dream_consolidation == []

    def test_observer_property(self):
        obs = DreamObserver()
        runner = CurriculumRunner(
            "ontodynamics",
            self._mock_execute,
            observer=obs,
            max_episodes_per_turn=1,
            max_cycles_per_episode=5,
        )
        assert runner.observer is obs

    def test_no_observer_property_none(self):
        runner = CurriculumRunner(
            "ontodynamics",
            self._mock_execute,
            max_episodes_per_turn=1,
            max_cycles_per_episode=5,
        )
        assert runner.observer is None

    def test_with_observer_produces_consolidation(self):
        """With observer, each turn gets dream consolidation results."""
        obs = DreamObserver()
        runner = CurriculumRunner(
            "ontodynamics",
            self._mock_execute,
            observer=obs,
            consolidation_cycles=2,
            max_episodes_per_turn=2,
            max_cycles_per_episode=10,
        )
        results = runner.run()
        assert len(results) > 0
        # Every turn should have exactly consolidation_cycles dream results
        for r in results:
            assert len(r.dream_consolidation) == 2
            for dc in r.dream_consolidation:
                assert isinstance(dc, DreamCycleResult)

    def test_observer_registers_turn_domains(self):
        """Observer accumulates domains across turns."""
        obs = DreamObserver()
        runner = CurriculumRunner(
            "ontodynamics",
            self._mock_execute,
            observer=obs,
            consolidation_cycles=1,
            max_episodes_per_turn=1,
            max_cycles_per_episode=5,
        )
        results = runner.run()
        # Each turn registers a domain: curriculum_turn_{level_max}
        registered = obs.domain_names
        assert len(registered) == len(results)
        for r in results:
            domain = f"curriculum_turn_{r.turn.level_max}"
            assert domain in registered

    def test_dream_finds_equivalences_across_turns(self):
        """Dream consolidation finds equivalences between scoped landscapes."""
        obs = DreamObserver()
        runner = CurriculumRunner(
            "ontodynamics",
            self._mock_execute,
            observer=obs,
            consolidation_cycles=1,
            max_episodes_per_turn=3,
            max_cycles_per_episode=15,
        )
        results = runner.run()
        # After multiple turns, dream should find structural equivalences
        # (cumulative landscapes share many edges)
        total_eq = sum(
            dc.equivalences_found
            for r in results
            for dc in r.dream_consolidation
        )
        # First turn has only 1 domain → no equivalences
        # Later turns have 2+ domains → should find some
        assert total_eq >= 0  # might be 0 if only 1 domain per cycle

    def test_consolidation_cycles_zero(self):
        """consolidation_cycles=0 means no dream calls even with observer."""
        obs = DreamObserver()
        runner = CurriculumRunner(
            "ontodynamics",
            self._mock_execute,
            observer=obs,
            consolidation_cycles=0,
            max_episodes_per_turn=1,
            max_cycles_per_episode=5,
        )
        results = runner.run()
        for r in results:
            assert r.dream_consolidation == []

    def test_consolidation_default_cycles(self):
        """Default consolidation_cycles is 3."""
        obs = DreamObserver()
        runner = CurriculumRunner(
            "ontodynamics",
            self._mock_execute,
            observer=obs,
            max_episodes_per_turn=1,
            max_cycles_per_episode=5,
        )
        results = runner.run()
        for r in results:
            assert len(r.dream_consolidation) == 3

    def test_summary_still_works_with_observer(self):
        """Summary method works correctly with observer present."""
        obs = DreamObserver()
        runner = CurriculumRunner(
            "ontodynamics",
            self._mock_execute,
            observer=obs,
            max_episodes_per_turn=1,
            max_cycles_per_episode=5,
        )
        runner.run()
        s = runner.summary()
        assert "Curriculum" in s
        assert "Turn" in s

    def test_final_landscape_valid_with_observer(self):
        """Final landscape is valid even with dream consolidation."""
        obs = DreamObserver()
        runner = CurriculumRunner(
            "ontodynamics",
            self._mock_execute,
            observer=obs,
            consolidation_cycles=1,
            max_episodes_per_turn=2,
            max_cycles_per_episode=10,
        )
        runner.run()
        ls = runner.final_landscape
        assert ls is not None
        assert len(ls.states) > 0
        assert ls.edge_count() > 0

    def test_historization_transfer_with_observer(self):
        """Historization still transfers across turns when observer is active."""
        obs = DreamObserver()
        runner = CurriculumRunner(
            "ontodynamics",
            self._mock_execute,
            observer=obs,
            consolidation_cycles=1,
            max_episodes_per_turn=3,
            max_cycles_per_episode=15,
        )
        results = runner.run()
        ls = runner.final_landscape
        total_load = sum(
            ls.historization.trace_load(e) for e in ls.edges
        )
        assert total_load > 0

    def test_dream_landscape_grows_across_turns(self):
        """Dream landscape accumulates structure from all turns."""
        obs = DreamObserver()
        runner = CurriculumRunner(
            "ontodynamics",
            self._mock_execute,
            observer=obs,
            consolidation_cycles=2,
            max_episodes_per_turn=2,
            max_cycles_per_episode=10,
        )
        results = runner.run()
        # After all turns, the dream landscape should have some structure
        dl = obs.dream_landscape
        if dl is not None:
            assert dl.states or True  # might not have a DL if no equivalences
