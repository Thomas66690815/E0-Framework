"""
Tests for E₀ Domain Bootstrapper (C44)
========================================
Verify that structured domain specs produce valid, initialized Landscapes.
"""

import pytest

from e0_controller.primitives import Edge, Outcome
from e0_controller.bootstrapper import (
    BootstrapError,
    EdgeSpec,
    bootstrap_landscape,
    validate_spec,
    _apply_confidence,
)


# ──────────────────────────────────────────────
# Helper: minimal valid spec
# ──────────────────────────────────────────────

def _valid_spec(**overrides):
    """Return a minimal valid domain spec, with optional overrides."""
    spec = {
        "nodes": ["A", "B", "C"],
        "edges": [
            {"from": "A", "to": "B", "delta": 1.0, "resistance": 0.5,
             "initial_U": 8.0, "initial_F": 2.0, "confidence": 0.7},
            {"from": "B", "to": "C", "delta": 1.5, "resistance": 1.0,
             "initial_U": 5.0, "initial_F": 5.0, "confidence": 0.3},
            {"from": "A", "to": "C", "delta": 2.0, "resistance": 1.5},
        ],
    }
    spec.update(overrides)
    return spec


# ──────────────────────────────────────────────
# 1. Validation Tests
# ──────────────────────────────────────────────

class TestValidation:
    """validate_spec catches structural problems."""

    def test_valid_spec_passes(self):
        edges = validate_spec(_valid_spec())
        assert len(edges) == 3

    def test_empty_nodes_rejected(self):
        with pytest.raises(BootstrapError, match="non-empty.*nodes"):
            validate_spec({"nodes": [], "edges": [{"from": "A", "to": "B"}]})

    def test_missing_nodes_rejected(self):
        with pytest.raises(BootstrapError, match="non-empty.*nodes"):
            validate_spec({"edges": [{"from": "A", "to": "B"}]})

    def test_empty_edges_rejected(self):
        with pytest.raises(BootstrapError, match="non-empty.*edges"):
            validate_spec({"nodes": ["A"], "edges": []})

    def test_invalid_node_name_rejected(self):
        with pytest.raises(BootstrapError, match="Invalid node"):
            validate_spec({"nodes": ["A", ""], "edges": [{"from": "A", "to": "B"}]})

    def test_source_not_in_nodes_rejected(self):
        with pytest.raises(BootstrapError, match="source.*not in nodes"):
            validate_spec({
                "nodes": ["A", "B"],
                "edges": [{"from": "X", "to": "B", "delta": 1.0, "resistance": 0.5}],
            })

    def test_target_not_in_nodes_rejected(self):
        with pytest.raises(BootstrapError, match="target.*not in nodes"):
            validate_spec({
                "nodes": ["A", "B"],
                "edges": [{"from": "A", "to": "X", "delta": 1.0, "resistance": 0.5}],
            })

    def test_self_loop_rejected(self):
        with pytest.raises(BootstrapError, match="self-loop"):
            validate_spec({
                "nodes": ["A"],
                "edges": [{"from": "A", "to": "A", "delta": 1.0, "resistance": 0.5}],
            })

    def test_duplicate_edge_rejected(self):
        with pytest.raises(BootstrapError, match="duplicate"):
            validate_spec({
                "nodes": ["A", "B"],
                "edges": [
                    {"from": "A", "to": "B", "delta": 1.0, "resistance": 0.5},
                    {"from": "A", "to": "B", "delta": 2.0, "resistance": 1.0},
                ],
            })

    def test_negative_delta_rejected(self):
        with pytest.raises(BootstrapError, match="delta must be"):
            validate_spec({
                "nodes": ["A", "B"],
                "edges": [{"from": "A", "to": "B", "delta": -1.0, "resistance": 0.5}],
            })

    def test_negative_resistance_rejected(self):
        with pytest.raises(BootstrapError, match="resistance must be"):
            validate_spec({
                "nodes": ["A", "B"],
                "edges": [{"from": "A", "to": "B", "delta": 1.0, "resistance": -0.5}],
            })

    def test_negative_initial_U_rejected(self):
        with pytest.raises(BootstrapError, match="initial_U must be"):
            validate_spec({
                "nodes": ["A", "B"],
                "edges": [{"from": "A", "to": "B", "delta": 1.0, "resistance": 0.5,
                           "initial_U": -1.0}],
            })

    def test_confidence_out_of_range_rejected(self):
        with pytest.raises(BootstrapError, match="confidence"):
            validate_spec({
                "nodes": ["A", "B"],
                "edges": [{"from": "A", "to": "B", "delta": 1.0, "resistance": 0.5,
                           "confidence": 1.5}],
            })

    def test_non_dict_rejected(self):
        with pytest.raises(BootstrapError, match="must be a dict"):
            validate_spec("not a dict")

    def test_edge_missing_from_rejected(self):
        with pytest.raises(BootstrapError, match="missing.*from"):
            validate_spec({"nodes": ["A", "B"], "edges": [{"to": "B"}]})

    def test_defaults_for_optional_fields(self):
        edges = validate_spec({
            "nodes": ["A", "B"],
            "edges": [{"from": "A", "to": "B", "delta": 1.0, "resistance": 0.5}],
        })
        assert edges[0].initial_U == 0.0
        assert edges[0].initial_F == 0.0
        assert edges[0].confidence == 1.0


# ──────────────────────────────────────────────
# 2. Confidence Scaling Tests
# ──────────────────────────────────────────────

class TestConfidenceScaling:
    """_apply_confidence correctly scales traces toward midpoint."""

    def test_full_confidence_unchanged(self):
        U, F = _apply_confidence(8.0, 2.0, 1.0)
        assert U == 8.0
        assert F == 2.0

    def test_zero_confidence_equals_midpoint(self):
        U, F = _apply_confidence(8.0, 2.0, 0.0)
        assert abs(U - 5.0) < 1e-10
        assert abs(F - 5.0) < 1e-10

    def test_half_confidence_halfway_to_midpoint(self):
        U, F = _apply_confidence(8.0, 2.0, 0.5)
        # midpoint = 5.0, U offset = 3.0, F offset = -3.0
        # U' = 5.0 + 0.5*3.0 = 6.5, F' = 5.0 - 0.5*3.0 = 3.5
        assert abs(U - 6.5) < 1e-10
        assert abs(F - 3.5) < 1e-10

    def test_preserves_total_load(self):
        U, F = _apply_confidence(10.0, 2.0, 0.3)
        assert abs((U + F) - 12.0) < 1e-10

    def test_zero_total_returns_zeros(self):
        U, F = _apply_confidence(0.0, 0.0, 0.5)
        assert U == 0.0
        assert F == 0.0

    def test_symmetric_input_unchanged(self):
        U, F = _apply_confidence(5.0, 5.0, 0.3)
        assert abs(U - 5.0) < 1e-10
        assert abs(F - 5.0) < 1e-10

    def test_quality_decreases_with_lower_confidence(self):
        """Lower confidence → closer to midpoint → lower |quality|."""
        from e0_controller.historization import Historization
        h = Historization(rho=1.0)
        edge = Edge("X", "Y")

        # High confidence
        U_hi, F_hi = _apply_confidence(9.0, 1.0, 0.9)
        h._U[edge] = U_hi
        h._F[edge] = F_hi
        q_hi = abs(h.trace_quality(edge))

        # Low confidence
        U_lo, F_lo = _apply_confidence(9.0, 1.0, 0.2)
        h._U[edge] = U_lo
        h._F[edge] = F_lo
        q_lo = abs(h.trace_quality(edge))

        assert q_hi > q_lo


# ──────────────────────────────────────────────
# 3. Landscape Building Tests
# ──────────────────────────────────────────────

class TestBootstrapLandscape:
    """bootstrap_landscape produces valid, initialized Landscapes."""

    def test_produces_landscape(self):
        ls = bootstrap_landscape(_valid_spec())
        assert ls is not None

    def test_all_nodes_present(self):
        ls = bootstrap_landscape(_valid_spec())
        assert "A" in ls.states
        assert "B" in ls.states
        assert "C" in ls.states

    def test_all_edges_present(self):
        ls = bootstrap_landscape(_valid_spec())
        assert ls.has_edge("A", "B")
        assert ls.has_edge("B", "C")
        assert ls.has_edge("A", "C")

    def test_delta_values_correct(self):
        ls = bootstrap_landscape(_valid_spec())
        assert ls.difference("A", "B") == 1.0
        assert ls.difference("B", "C") == 1.5
        assert ls.difference("A", "C") == 2.0

    def test_resistance_values_correct(self):
        ls = bootstrap_landscape(_valid_spec())
        assert ls.base_resistance("A", "B") == 0.5
        assert ls.base_resistance("B", "C") == 1.0
        assert ls.base_resistance("A", "C") == 1.5

    def test_inertia_modulation_enabled(self):
        ls = bootstrap_landscape(_valid_spec())
        assert ls.inertia_modulation is True

    def test_initial_traces_injected(self):
        ls = bootstrap_landscape(_valid_spec())
        e_ab = Edge("A", "B")
        # A→B has initial_U=8, initial_F=2, confidence=0.7
        load = ls.historization.trace_load(e_ab)
        assert load > 0, "Initial traces should be injected"
        # Total load preserved: 8 + 2 = 10
        assert abs(load - 10.0) < 1e-10

    def test_no_initial_traces_when_zero(self):
        ls = bootstrap_landscape(_valid_spec())
        e_ac = Edge("A", "C")
        # A→C has no initial_U/initial_F specified (defaults to 0)
        assert ls.historization.trace_load(e_ac) == 0.0

    def test_confidence_affects_quality(self):
        ls = bootstrap_landscape(_valid_spec())
        e_ab = Edge("A", "B")
        e_bc = Edge("B", "C")
        # A→B: U=8, F=2, confidence=0.7 → still directional
        q_ab = ls.historization.trace_quality(e_ab)
        # B→C: U=5, F=5, confidence=0.3 → already balanced, stays balanced
        q_bc = ls.historization.trace_quality(e_bc)
        assert abs(q_ab) > abs(q_bc), \
            f"A→B should have higher |quality| than B→C: {q_ab} vs {q_bc}"

    def test_low_confidence_produces_high_inertia_dampening(self):
        """Low confidence → balanced traces → high confusion → low inertia_factor."""
        spec = {
            "nodes": ["X", "Y"],
            "edges": [
                {"from": "X", "to": "Y", "delta": 1.0, "resistance": 0.5,
                 "initial_U": 10.0, "initial_F": 0.0, "confidence": 0.1},
            ],
        }
        ls = bootstrap_landscape(spec)
        e = Edge("X", "Y")
        i = ls.historization.inertia_factor(e)
        # With confidence=0.1: traces nearly balanced → high confusion → low inertia
        assert i < 0.85, f"Expected dampened inertia at low confidence, got {i}"

    def test_high_confidence_produces_low_dampening(self):
        spec = {
            "nodes": ["X", "Y"],
            "edges": [
                {"from": "X", "to": "Y", "delta": 1.0, "resistance": 0.5,
                 "initial_U": 10.0, "initial_F": 0.0, "confidence": 1.0},
            ],
        }
        ls = bootstrap_landscape(spec)
        e = Edge("X", "Y")
        i = ls.historization.inertia_factor(e)
        # Full confidence: traces as-is (10, 0) → clear quality → minimal dampening
        assert i > 0.95, f"Expected high inertia at full confidence, got {i}"


# ──────────────────────────────────────────────
# 4. Edge Cases
# ──────────────────────────────────────────────

class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_single_edge_graph(self):
        spec = {
            "nodes": ["A", "B"],
            "edges": [{"from": "A", "to": "B", "delta": 0.5, "resistance": 0.3}],
        }
        ls = bootstrap_landscape(spec)
        assert ls.has_edge("A", "B")
        assert len(ls.states) == 2

    def test_isolated_node_preserved(self):
        """Nodes listed but not on any edge are still in the landscape."""
        spec = {
            "nodes": ["A", "B", "C"],
            "edges": [{"from": "A", "to": "B", "delta": 1.0, "resistance": 0.5}],
        }
        ls = bootstrap_landscape(spec)
        assert "C" in ls.states

    def test_large_initial_traces(self):
        spec = {
            "nodes": ["A", "B"],
            "edges": [{"from": "A", "to": "B", "delta": 1.0, "resistance": 0.5,
                       "initial_U": 100.0, "initial_F": 50.0, "confidence": 0.5}],
        }
        ls = bootstrap_landscape(spec)
        e = Edge("A", "B")
        assert abs(ls.historization.trace_load(e) - 150.0) < 1e-10

    def test_zero_confidence_balanced_traces(self):
        spec = {
            "nodes": ["A", "B"],
            "edges": [{"from": "A", "to": "B", "delta": 1.0, "resistance": 0.5,
                       "initial_U": 10.0, "initial_F": 0.0, "confidence": 0.0}],
        }
        ls = bootstrap_landscape(spec)
        e = Edge("A", "B")
        q = ls.historization.trace_quality(e)
        assert abs(q) < 0.01, f"Zero confidence should produce q≈0, got {q}"

    def test_controller_can_run_on_bootstrapped_landscape(self):
        """The resulting landscape works with E0Controller."""
        from e0_controller.controller import E0Controller
        spec = {
            "nodes": ["start", "middle", "end"],
            "edges": [
                {"from": "start", "to": "middle", "delta": 1.0, "resistance": 0.5,
                 "initial_U": 5.0, "initial_F": 1.0, "confidence": 0.8},
                {"from": "middle", "to": "end", "delta": 1.0, "resistance": 0.5,
                 "initial_U": 3.0, "initial_F": 3.0, "confidence": 0.5},
            ],
        }
        ls = bootstrap_landscape(spec)
        ctrl = E0Controller(ls, lambda s, t: Outcome.SUCCESS)
        trace = ctrl.run("start", max_cycles=5)
        assert len(trace.steps) > 0


# ──────────────────────────────────────────────
# 5. Round-Trip: Bootstrap → Run → Verify Historization
# ──────────────────────────────────────────────

class TestBootstrapRoundTrip:
    """End-to-end: bootstrap → controller run → verify traces evolve."""

    def test_traces_evolve_beyond_initial(self):
        spec = {
            "nodes": ["A", "B"],
            "edges": [
                {"from": "A", "to": "B", "delta": 1.0, "resistance": 0.5,
                 "initial_U": 2.0, "initial_F": 1.0, "confidence": 0.8},
                {"from": "B", "to": "A", "delta": 1.0, "resistance": 0.5,
                 "initial_U": 1.0, "initial_F": 0.5, "confidence": 0.6},
            ],
        }
        ls = bootstrap_landscape(spec)
        e_ab = Edge("A", "B")
        u_before = ls.historization.success_trace(e_ab)

        from e0_controller.controller import E0Controller
        ctrl = E0Controller(ls, lambda s, t: Outcome.SUCCESS)
        ctrl.run("A", max_cycles=20)

        u_after = ls.historization.success_trace(e_ab)
        assert u_after > u_before, \
            "Success trace should grow with repeated successes"

    def test_quality_shifts_with_experience(self):
        spec = {
            "nodes": ["A", "B"],
            "edges": [
                {"from": "A", "to": "B", "delta": 1.0, "resistance": 0.5,
                 "initial_U": 5.0, "initial_F": 5.0, "confidence": 0.5},
                {"from": "B", "to": "A", "delta": 1.0, "resistance": 0.5},
            ],
        }
        ls = bootstrap_landscape(spec)
        e_ab = Edge("A", "B")
        q_before = ls.historization.trace_quality(e_ab)

        from e0_controller.controller import E0Controller
        ctrl = E0Controller(ls, lambda s, t: Outcome.SUCCESS)
        ctrl.run("A", max_cycles=20)

        q_after = ls.historization.trace_quality(e_ab)
        # All successes → quality should shift positive
        assert q_after > q_before, \
            f"Quality should improve with successes: {q_before} → {q_after}"
