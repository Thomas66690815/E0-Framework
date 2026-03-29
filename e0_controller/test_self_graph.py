"""
Tests for E₀ Self-Graph (C43)
===============================
Verify that E0 can build, update, and query a structural model of itself.
"""

import pytest

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller
from e0_controller.self_graph import (
    SelfGraph,
    ALL_COMPONENTS,
    CORE_COMPONENTS,
    MODULATION_COMPONENTS,
    CORE_EDGES,
    MODULATION_EDGES,
    active_components,
)


# ──────────────────────────────────────────────
# 1. Topology Tests
# ──────────────────────────────────────────────

class TestSelfGraphTopology:
    """The self-graph initializes with the correct E0 operational structure."""

    def test_all_core_nodes_present(self):
        sg = SelfGraph()
        states = sg.landscape._states
        for comp in CORE_COMPONENTS:
            assert comp in states, f"Missing core node: {comp}"

    def test_all_modulation_nodes_present(self):
        sg = SelfGraph()
        states = sg.landscape._states
        for comp in MODULATION_COMPONENTS:
            assert comp in states, f"Missing modulation node: {comp}"

    def test_core_edges_exist(self):
        sg = SelfGraph()
        for src, tgt in CORE_EDGES:
            assert sg.landscape.has_edge(src, tgt), f"Missing core edge: {src}→{tgt}"

    def test_modulation_edges_exist(self):
        sg = SelfGraph()
        for src, tgt in MODULATION_EDGES:
            assert sg.landscape.has_edge(src, tgt), f"Missing mod edge: {src}→{tgt}"

    def test_core_edges_have_tight_coupling(self):
        sg = SelfGraph()
        for src, tgt in CORE_EDGES:
            e = Edge(src, tgt)
            assert sg.landscape._delta[e] == 0.5
            assert sg.landscape._R0[e] == 0.3

    def test_modulation_edges_have_loose_coupling(self):
        sg = SelfGraph()
        for src, tgt in MODULATION_EDGES:
            e = Edge(src, tgt)
            assert sg.landscape._delta[e] == 1.0
            assert sg.landscape._R0[e] == 1.0

    def test_total_node_count(self):
        sg = SelfGraph()
        assert len(sg.landscape._states) == len(ALL_COMPONENTS)

    def test_total_edge_count(self):
        sg = SelfGraph()
        expected = len(CORE_EDGES) + len(MODULATION_EDGES)
        assert len(sg.landscape._R0) == expected


# ──────────────────────────────────────────────
# 2. Active Components
# ──────────────────────────────────────────────

class TestActiveComponents:
    """active_components() returns the right set based on flags."""

    def test_default_core_only(self):
        result = active_components()
        assert set(result) == set(CORE_COMPONENTS)

    def test_with_curvature(self):
        result = active_components(curvature_active=True)
        assert "curvature" in result
        assert "overlap" not in result

    def test_with_overlap(self):
        result = active_components(overlap_active=True)
        assert "overlap" in result
        assert "curvature" not in result

    def test_all_active(self):
        result = active_components(
            curvature_active=True, overlap_active=True, inertia_active=True
        )
        assert set(result) == set(ALL_COMPONENTS)

    def test_inertia_always_in_core(self):
        # inertia is a core component (always in graph), the flag
        # only changes whether it _modulates_
        result = active_components(inertia_active=False)
        assert "inertia" in result


# ──────────────────────────────────────────────
# 3. Self-Historization
# ──────────────────────────────────────────────

class TestSelfHistorize:
    """self_historize() correctly updates traces on participating edges."""

    def test_success_increases_load(self):
        sg = SelfGraph()
        components = list(CORE_COMPONENTS)
        sg.self_historize(components, Outcome.SUCCESS)
        # All core cycle edges should now have trace_load > 0
        for src, tgt in CORE_EDGES:
            load = sg.landscape.historization.trace_load(Edge(src, tgt))
            assert load > 0, f"{src}→{tgt} should have load > 0"

    def test_modulation_not_historized_when_absent(self):
        sg = SelfGraph()
        # Only core components active — modulation edges untouched
        sg.self_historize(list(CORE_COMPONENTS), Outcome.SUCCESS)
        for src, tgt in MODULATION_EDGES:
            load = sg.landscape.historization.trace_load(Edge(src, tgt))
            assert load == 0.0, f"{src}→{tgt} should not be historized"

    def test_modulation_historized_when_present(self):
        sg = SelfGraph()
        components = list(ALL_COMPONENTS)
        sg.self_historize(components, Outcome.SUCCESS)
        for src, tgt in MODULATION_EDGES:
            load = sg.landscape.historization.trace_load(Edge(src, tgt))
            assert load > 0, f"{src}→{tgt} should be historized"

    def test_only_matching_edges_updated(self):
        sg = SelfGraph()
        # Only curvature + transition_field active — should only update
        # curvature→transition_field, not any core edges
        sg.self_historize(["curvature", "transition_field"], Outcome.SUCCESS)
        e_mod = Edge("curvature", "transition_field")
        assert sg.landscape.historization.trace_load(e_mod) > 0

        # Core edges should be untouched
        e_core = Edge("amplitude", "born")
        assert sg.landscape.historization.trace_load(e_core) == 0.0

    def test_failure_recorded_correctly(self):
        sg = SelfGraph()
        sg.self_historize(list(CORE_COMPONENTS), Outcome.FAILURE)
        e = Edge("born", "realization")
        assert sg.landscape.historization.failure_trace(e) > 0
        assert sg.landscape.historization.success_trace(e) == 0.0

    def test_accumulation_over_multiple_updates(self):
        sg = SelfGraph()
        components = list(CORE_COMPONENTS)
        for _ in range(10):
            sg.self_historize(components, Outcome.SUCCESS)
        e = Edge("amplitude", "born")
        assert sg.landscape.historization.trace_load(e) > 5.0


# ──────────────────────────────────────────────
# 4. Component Quality Queries
# ──────────────────────────────────────────────

class TestComponentQueries:
    """Query APIs return meaningful values from self-graph state."""

    def test_virgin_components_have_zero_load(self):
        sg = SelfGraph()
        for comp in ALL_COMPONENTS:
            assert sg.component_load(comp) == 0.0

    def test_virgin_components_have_zero_quality(self):
        sg = SelfGraph()
        for comp in ALL_COMPONENTS:
            assert sg.component_quality(comp) == 0.0

    def test_virgin_components_have_neutral_inertia(self):
        sg = SelfGraph()
        for comp in ALL_COMPONENTS:
            assert sg.component_inertia(comp) == 1.0

    def test_success_produces_positive_quality(self):
        sg = SelfGraph()
        for _ in range(5):
            sg.self_historize(list(CORE_COMPONENTS), Outcome.SUCCESS)
        q = sg.component_quality("born")
        assert q > 0.5, f"Expected positive quality, got {q}"

    def test_failure_produces_negative_quality(self):
        sg = SelfGraph()
        for _ in range(5):
            sg.self_historize(list(CORE_COMPONENTS), Outcome.FAILURE)
        q = sg.component_quality("born")
        assert q < -0.5, f"Expected negative quality, got {q}"

    def test_mixed_outcomes_produce_low_quality(self):
        sg = SelfGraph()
        components = list(CORE_COMPONENTS)
        for _ in range(10):
            sg.self_historize(components, Outcome.SUCCESS)
        for _ in range(10):
            sg.self_historize(components, Outcome.FAILURE)
        q = sg.component_quality("born")
        assert abs(q) < 0.3, f"Expected low |quality| for mixed, got {q}"

    def test_mixed_outcomes_produce_low_inertia(self):
        sg = SelfGraph()
        components = list(CORE_COMPONENTS)
        for _ in range(10):
            sg.self_historize(components, Outcome.SUCCESS)
        for _ in range(10):
            sg.self_historize(components, Outcome.FAILURE)
        i = sg.component_inertia("born")
        assert i < 0.9, f"Expected dampened inertia for mixed, got {i}"

    def test_clear_success_produces_high_inertia(self):
        sg = SelfGraph()
        for _ in range(10):
            sg.self_historize(list(CORE_COMPONENTS), Outcome.SUCCESS)
        i = sg.component_inertia("born")
        # Clear quality → low confusion → inertia stays near 1.0
        assert i > 0.9, f"Expected high inertia for clear success, got {i}"

    def test_load_increases_with_updates(self):
        sg = SelfGraph()
        components = list(CORE_COMPONENTS)
        sg.self_historize(components, Outcome.SUCCESS)
        load1 = sg.component_load("amplitude")
        sg.self_historize(components, Outcome.SUCCESS)
        load2 = sg.component_load("amplitude")
        assert load2 > load1

    def test_nonexistent_component_returns_defaults(self):
        sg = SelfGraph()
        # A component with no outgoing edges returns defaults
        assert sg.component_load("nonexistent") == 0.0
        assert sg.component_quality("nonexistent") == 0.0
        assert sg.component_inertia("nonexistent") == 1.0


# ──────────────────────────────────────────────
# 5. Snapshot and Summary
# ──────────────────────────────────────────────

class TestSnapshotAndSummary:
    """Snapshot exports and summary formatting work."""

    def test_snapshot_has_all_components(self):
        sg = SelfGraph()
        snap = sg.snapshot()
        assert set(snap.keys()) == set(ALL_COMPONENTS)

    def test_snapshot_has_expected_keys(self):
        sg = SelfGraph()
        snap = sg.snapshot()
        for comp in ALL_COMPONENTS:
            assert "load" in snap[comp]
            assert "quality" in snap[comp]
            assert "inertia" in snap[comp]

    def test_snapshot_reflects_updates(self):
        sg = SelfGraph()
        sg.self_historize(list(CORE_COMPONENTS), Outcome.SUCCESS)
        snap = sg.snapshot()
        assert snap["amplitude"]["load"] > 0
        assert snap["curvature"]["load"] == 0  # not historized

    def test_summary_is_string(self):
        sg = SelfGraph()
        s = sg.summary()
        assert isinstance(s, str)
        assert "SelfGraph Status:" in s

    def test_summary_contains_all_components(self):
        sg = SelfGraph()
        s = sg.summary()
        for comp in ALL_COMPONENTS:
            assert comp in s


# ──────────────────────────────────────────────
# 6. Convergence Behavior
# ──────────────────────────────────────────────

class TestConvergence:
    """Self-graph traces converge under consistent patterns."""

    def test_quality_converges_to_positive_under_success(self):
        sg = SelfGraph()
        components = list(CORE_COMPONENTS)
        for _ in range(50):
            sg.self_historize(components, Outcome.SUCCESS)
        q = sg.component_quality("born")
        assert q > 0.9, f"Expected convergence to +1, got {q}"

    def test_quality_converges_to_negative_under_failure(self):
        sg = SelfGraph()
        components = list(CORE_COMPONENTS)
        for _ in range(50):
            sg.self_historize(components, Outcome.FAILURE)
        q = sg.component_quality("born")
        assert q < -0.9, f"Expected convergence to -1, got {q}"

    def test_modulation_stays_neutral_when_unused(self):
        sg = SelfGraph()
        # Only core components used — modulation stays virgin
        for _ in range(50):
            sg.self_historize(list(CORE_COMPONENTS), Outcome.SUCCESS)
        assert sg.component_load("curvature") == 0.0
        assert sg.component_quality("curvature") == 0.0
        assert sg.component_inertia("curvature") == 1.0

    def test_inertia_drops_under_contradictory_evidence(self):
        sg = SelfGraph()
        components = list(CORE_COMPONENTS)
        # Alternate success/failure to build contradictory traces
        for _ in range(30):
            sg.self_historize(components, Outcome.SUCCESS)
            sg.self_historize(components, Outcome.FAILURE)
        i = sg.component_inertia("born")
        assert i < 0.85, f"Expected inertia drop under contradiction, got {i}"
        # But load should be high
        assert sg.component_load("born") > 3.0


# ──────────────────────────────────────────────
# 7. Controller Integration
# ──────────────────────────────────────────────

def _build_test_landscape():
    """Simple 3-node landscape for integration tests."""
    ls = Landscape()
    ls.add_edge("A", "B", delta=1.0, resistance=0.5)
    ls.add_edge("B", "C", delta=1.0, resistance=0.5)
    ls.add_edge("A", "C", delta=2.0, resistance=1.0)
    return ls


class TestControllerIntegration:
    """SelfGraph updates automatically during controller cycles."""

    def test_self_graph_none_by_default(self):
        ls = _build_test_landscape()
        ctrl = E0Controller(ls, lambda s, t: Outcome.SUCCESS)
        assert ctrl.self_graph is None

    def test_self_graph_attached(self):
        ls = _build_test_landscape()
        ctrl = E0Controller(ls, lambda s, t: Outcome.SUCCESS)
        sg = SelfGraph()
        ctrl.self_graph = sg
        assert ctrl.self_graph is sg

    def test_cycle_updates_self_graph(self):
        ls = _build_test_landscape()
        sg = SelfGraph()
        ctrl = E0Controller(ls, lambda s, t: Outcome.SUCCESS)
        ctrl.self_graph = sg
        # Before cycle: all loads are zero
        assert sg.component_load("born") == 0.0
        # Run one cycle
        ctrl.cycle("A")
        # After cycle: core components should be historized
        assert sg.component_load("born") > 0.0
        assert sg.component_load("amplitude") > 0.0

    def test_multiple_cycles_accumulate(self):
        ls = _build_test_landscape()
        sg = SelfGraph()
        ctrl = E0Controller(ls, lambda s, t: Outcome.SUCCESS)
        ctrl.self_graph = sg
        ctrl.cycle("A")
        load1 = sg.component_load("born")
        ctrl.cycle("A")
        load2 = sg.component_load("born")
        assert load2 > load1

    def test_failure_outcome_recorded(self):
        ls = _build_test_landscape()
        sg = SelfGraph()
        ctrl = E0Controller(ls, lambda s, t: Outcome.FAILURE)
        ctrl.self_graph = sg
        ctrl.cycle("A")
        q = sg.component_quality("born")
        assert q < 0, f"Expected negative quality for failure, got {q}"

    def test_modulation_components_reflected(self):
        ls = _build_test_landscape()
        ls.curvature_modulation = True
        sg = SelfGraph()
        ctrl = E0Controller(ls, lambda s, t: Outcome.SUCCESS)
        ctrl.self_graph = sg
        ctrl.cycle("A")
        # Curvature was active → should be historized
        assert sg.component_load("curvature") > 0.0
        # Overlap was NOT active → should stay zero
        assert sg.component_load("overlap") == 0.0

    def test_run_updates_self_graph(self):
        ls = _build_test_landscape()
        sg = SelfGraph()
        ctrl = E0Controller(ls, lambda s, t: Outcome.SUCCESS)
        ctrl.self_graph = sg
        ctrl.run("A", max_cycles=5)
        # After 5 cycles, significant load should have accumulated
        assert sg.component_load("born") > 2.0

    def test_no_self_graph_no_error(self):
        ls = _build_test_landscape()
        ctrl = E0Controller(ls, lambda s, t: Outcome.SUCCESS)
        # self_graph is None — cycle should work without issues
        result = ctrl.cycle("A")
        assert result is not None

    def test_snapshot_after_run(self):
        ls = _build_test_landscape()
        sg = SelfGraph()
        ctrl = E0Controller(ls, lambda s, t: Outcome.SUCCESS)
        ctrl.self_graph = sg
        ctrl.run("A", max_cycles=10)
        snap = sg.snapshot()
        # Core components should have non-zero load
        assert snap["born"]["load"] > 0
        assert snap["amplitude"]["load"] > 0
        # Quality should be positive (all successes)
        assert snap["born"]["quality"] > 0.5
