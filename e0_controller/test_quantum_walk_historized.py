"""
Tests for quantum_walk_historized.py (C303).

Coverage plan:
    TestScaleSu2               (10) — angle scaling, identity/full limits, axis preserved
    TestConvictionHelper        (8) — virgin=0, confirmed→high, conflicted≈0
    TestQuantumStrength         (5) — 1-conviction, min_quantum floor
    TestHistorizedInit          (8) — valid init, defaults, inheritance, conviction map
    TestHistorizedCoinGating    (8) — virgin edges → full coin, confirmed → scaled
    TestRecordOutcome           (6) — inscribes on landscape, escalated is no-op
    TestStepWithOutcome         (6) — convenience method, outcome recorded
    TestRunWithOutcomes         (8) — multi-step learning loop
    TestQuantumToClassical      (8) — after many successes, behavior converges
"""

from __future__ import annotations

import math
from typing import List

import numpy as np
import pytest

from e0_controller.landscape import Landscape
from e0_controller.primitives import Edge, Outcome
from e0_controller.quantum_walk import (
    _coin_geometric,
    _coin_hadamard,
    _coin_identity,
    _coin_minimal,
    COIN_MODES,
)
from e0_controller.quantum_walk_historized import (
    HistorizedQuantumWalk,
    conviction,
    quantum_strength,
    scale_su2,
)
from e0_controller.spinor_connection import (
    IDENTITY,
    SPINOR_UP,
    pauli_exponential,
)


# ── Shared fixtures ───────────────────────────────────────────────────────────

def _linear(n: int = 3) -> Landscape:
    states = [chr(ord("A") + i) for i in range(n)]
    L = Landscape()
    for i in range(n - 1):
        L.add_edge(states[i], states[i + 1], delta=0.5, resistance=1.0)
    return L


def _diamond() -> Landscape:
    L = Landscape()
    L.add_edge("START", "MID1", delta=0.5, resistance=1.0)
    L.add_edge("START", "MID2", delta=0.3, resistance=0.8)
    L.add_edge("MID1", "GOAL", delta=0.4, resistance=0.9)
    L.add_edge("MID2", "GOAL", delta=0.6, resistance=1.2)
    return L


def _inscribe(L: Landscape, edge: Edge, outcome: Outcome, n: int = 1) -> None:
    for _ in range(n):
        L.historization.inscribe(edge, outcome)


def _spinor_down() -> np.ndarray:
    return np.array([0.0, 1.0], dtype=complex)


# ═══════════════════════════════════════════════════════════════════════════════
# scale_su2
# ═══════════════════════════════════════════════════════════════════════════════

class TestScaleSu2:
    def test_scale_zero_gives_identity(self):
        C = pauli_exponential(1.0, np.array([0, 0, 1.0]))
        result = scale_su2(C, 0.0)
        assert np.allclose(result, IDENTITY, atol=1e-12)

    def test_scale_one_gives_original(self):
        C = pauli_exponential(0.8, np.array([0, 0, 1.0]))
        result = scale_su2(C, 1.0)
        assert np.allclose(result, C, atol=1e-12)

    def test_scale_half_gives_half_angle(self):
        angle = 1.2
        axis = np.array([0, 0, 1.0])
        C = pauli_exponential(angle, axis)
        half = scale_su2(C, 0.5)
        expected = pauli_exponential(angle * 0.5, axis)
        assert np.allclose(half, expected, atol=1e-10)

    def test_result_is_su2(self):
        C = pauli_exponential(0.7, np.array([1, 0, 0.0]) / 1)
        result = scale_su2(C, 0.3)
        assert np.allclose(result.conj().T @ result, IDENTITY, atol=1e-12)
        assert abs(np.linalg.det(result) - 1.0) < 1e-10

    def test_identity_input_gives_identity(self):
        result = scale_su2(IDENTITY.copy(), 0.7)
        assert np.allclose(result, IDENTITY, atol=1e-12)

    def test_interpolation_is_monotone_in_angle(self):
        """Larger scale → further from identity (larger effective rotation)."""
        C = pauli_exponential(math.pi / 2, np.array([0, 0, 1.0]))
        # scale 0.2 < scale 0.8 → |C_0.2 - I| < |C_0.8 - I|
        d02 = np.linalg.norm(scale_su2(C, 0.2) - IDENTITY)
        d08 = np.linalg.norm(scale_su2(C, 0.8) - IDENTITY)
        assert d02 < d08

    def test_axis_preserved_up_to_pi_rotation(self):
        """Scale=0.5 should not flip the rotation axis."""
        axis = np.array([1.0, 1.0, 0.0]) / math.sqrt(2)
        C = pauli_exponential(1.0, axis)
        half = scale_su2(C, 0.5)
        # half should equal pauli_exponential(0.5, axis)
        expected = pauli_exponential(0.5, axis)
        assert np.allclose(half, expected, atol=1e-10)

    def test_scale_with_minus_identity_gives_identity(self):
        # -I has trace = -2 → cos(α/2) = -1 → α = 2π → sin(α/2) = 0 → returns I
        result = scale_su2(-IDENTITY.copy(), 0.5)
        assert np.allclose(result, IDENTITY, atol=1e-12)

    def test_hadamard_scaled(self):
        H = np.array([[1, 1], [1, -1]], dtype=complex) / math.sqrt(2)
        result = scale_su2(H, 0.5)
        # Should be unitary and 2×2
        assert result.shape == (2, 2)
        assert np.allclose(result.conj().T @ result, IDENTITY, atol=1e-11)

    def test_scale_commutes_composition(self):
        """scale(C1·C2, s) ≠ scale(C1,s)·scale(C2,s) in general — smoke test only."""
        axis = np.array([0.0, 0.0, 1.0])
        C1 = pauli_exponential(0.4, axis)
        C2 = pauli_exponential(0.6, axis)
        # Same axis: C1·C2 = pauli_exponential(1.0, axis)
        product = C1 @ C2
        result = scale_su2(product, 0.5)
        expected = pauli_exponential(0.5, axis)
        assert np.allclose(result, expected, atol=1e-10)


# ═══════════════════════════════════════════════════════════════════════════════
# conviction helper
# ═══════════════════════════════════════════════════════════════════════════════

class TestConvictionHelper:
    def test_virgin_edge_gives_zero(self):
        L = _linear()
        edge = Edge("A", "B")
        assert conviction(L, edge) == pytest.approx(0.0)

    def test_pure_success_conviction_increases_with_n(self):
        L = _linear()
        edge = Edge("A", "B")
        c_prev = 0.0
        for _ in range(10):
            _inscribe(L, edge, Outcome.SUCCESS)
            c = conviction(L, edge)
            assert c >= c_prev
            c_prev = c

    def test_conviction_below_one(self):
        L = _linear()
        edge = Edge("A", "B")
        _inscribe(L, edge, Outcome.SUCCESS, n=100)
        assert conviction(L, edge) < 1.0

    def test_conflicted_gives_low_conviction(self):
        L = _linear()
        edge = Edge("A", "B")
        _inscribe(L, edge, Outcome.SUCCESS, n=5)
        _inscribe(L, edge, Outcome.FAILURE, n=5)
        # q ≈ 0 → |q| ≈ 0 → conviction ≈ 0
        c = conviction(L, edge)
        assert c < 0.2

    def test_pure_failure_gives_conviction(self):
        # |q| → 1 for pure failure too (negative direction, same magnitude)
        L = _linear()
        edge = Edge("A", "B")
        _inscribe(L, edge, Outcome.FAILURE, n=10)
        c = conviction(L, edge)
        assert c > 0.3

    def test_mu_controls_rate(self):
        L = _linear()
        edge = Edge("A", "B")
        _inscribe(L, edge, Outcome.SUCCESS, n=5)
        # Large mu → conviction grows slower (half-load at larger m)
        c_small_mu = conviction(L, edge, mu=1.0)
        c_large_mu = conviction(L, edge, mu=100.0)
        assert c_small_mu > c_large_mu

    def test_conviction_is_float(self):
        L = _linear()
        assert isinstance(conviction(L, Edge("A", "B")), float)

    def test_conviction_nonnegative(self):
        L = _linear()
        edge = Edge("A", "B")
        _inscribe(L, edge, Outcome.FAILURE, n=3)
        assert conviction(L, edge) >= 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# quantum_strength helper
# ═══════════════════════════════════════════════════════════════════════════════

class TestQuantumStrength:
    def test_virgin_gives_one(self):
        L = _linear()
        qs = quantum_strength(L, Edge("A", "B"))
        assert qs == pytest.approx(1.0)

    def test_decreases_with_inscriptions(self):
        L = _linear()
        edge = Edge("A", "B")
        qs_prev = 1.0
        for _ in range(20):
            _inscribe(L, edge, Outcome.SUCCESS)
            qs = quantum_strength(L, edge)
            assert qs <= qs_prev + 1e-12
            qs_prev = qs

    def test_min_quantum_floor_respected(self):
        L = _linear()
        edge = Edge("A", "B")
        _inscribe(L, edge, Outcome.SUCCESS, n=200)
        qs = quantum_strength(L, edge, min_quantum=0.1)
        assert qs >= 0.1

    def test_stays_in_zero_one(self):
        L = _linear()
        edge = Edge("A", "B")
        for outcome in [Outcome.SUCCESS, Outcome.FAILURE] * 5:
            _inscribe(L, edge, outcome)
            qs = quantum_strength(L, edge)
            assert 0.0 <= qs <= 1.0 + 1e-12

    def test_one_minus_conviction(self):
        L = _linear()
        edge = Edge("A", "B")
        _inscribe(L, edge, Outcome.SUCCESS, n=7)
        c = conviction(L, edge)
        qs = quantum_strength(L, edge)
        assert qs == pytest.approx(max(0.0, 1.0 - c))


# ═══════════════════════════════════════════════════════════════════════════════
# HistorizedQuantumWalk — init
# ═══════════════════════════════════════════════════════════════════════════════

class TestHistorizedInit:
    def test_basic_init(self):
        L = _linear()
        walk = HistorizedQuantumWalk(L, "A")
        assert walk.position == "A"

    def test_inherits_quantum_walk(self):
        from e0_controller.quantum_walk import QuantumWalk
        L = _linear()
        walk = HistorizedQuantumWalk(L, "A")
        assert isinstance(walk, QuantumWalk)

    def test_default_coin_mode_geometric(self):
        L = _linear()
        walk = HistorizedQuantumWalk(L, "A")
        # No validation of internal mode, just smoke test
        assert walk is not None

    def test_default_spinor_is_up(self):
        L = _linear()
        walk = HistorizedQuantumWalk(L, "A")
        assert np.allclose(walk.spinor, SPINOR_UP)

    def test_custom_mu(self):
        L = _linear()
        walk = HistorizedQuantumWalk(L, "A", mu=10.0)
        assert walk._mu == 10.0

    def test_min_quantum_stored(self):
        L = _linear()
        walk = HistorizedQuantumWalk(L, "A", min_quantum=0.2)
        assert walk._min_quantum == 0.2

    def test_conviction_map_returns_dict(self):
        L = _linear()
        walk = HistorizedQuantumWalk(L, "A")
        cmap = walk.conviction_map()
        assert isinstance(cmap, dict)

    def test_quantum_strength_map_all_edges(self):
        L = _diamond()
        walk = HistorizedQuantumWalk(L, "START")
        qmap = walk.quantum_strength_map()
        assert len(qmap) == len(L.edges)


# ═══════════════════════════════════════════════════════════════════════════════
# Coin gating
# ═══════════════════════════════════════════════════════════════════════════════

class TestHistorizedCoinGating:
    def test_virgin_coin_equals_base_coin(self):
        """Virgin edges: quantum_strength=1, gated coin = base coin."""
        L = _linear(2)
        walk = HistorizedQuantumWalk(L, "A", coin_mode="hadamard")
        # Gated coin on virgin edge should equal base (hadamard)
        gated = walk._gated_coin(L, "A", "B")
        base = _coin_hadamard(L, "A", "B")
        assert np.allclose(gated, base, atol=1e-12)

    def test_confirmed_edge_coin_approaches_identity(self):
        """After many successes, coin scales toward identity."""
        L = _linear(2)
        edge = Edge("A", "B")
        _inscribe(L, edge, Outcome.SUCCESS, n=200)
        walk = HistorizedQuantumWalk(L, "A", coin_mode="hadamard")
        gated = walk._gated_coin(L, "A", "B")
        # Should be closer to identity than the original hadamard
        dist_identity = np.linalg.norm(gated - IDENTITY)
        base = _coin_hadamard(L, "A", "B")
        dist_base = np.linalg.norm(base - IDENTITY)
        assert dist_identity < dist_base

    def test_gated_coin_is_unitary(self):
        L = _linear(2)
        walk = HistorizedQuantumWalk(L, "A", coin_mode="geometric")
        C = walk._gated_coin(L, "A", "B")
        assert np.allclose(C.conj().T @ C, IDENTITY, atol=1e-12)

    def test_gated_coin_still_su2_after_inscriptions(self):
        L = _linear(2)
        edge = Edge("A", "B")
        _inscribe(L, edge, Outcome.SUCCESS, n=5)
        walk = HistorizedQuantumWalk(L, "A", coin_mode="minimal")
        C = walk._gated_coin(L, "A", "B")
        assert np.allclose(C.conj().T @ C, IDENTITY, atol=1e-12)
        assert abs(np.linalg.det(C) - 1.0) < 1e-10

    def test_different_edges_different_coins(self):
        """Conviction differs per edge → coins differ."""
        L = _diamond()
        edge_mid1 = Edge("START", "MID1")
        _inscribe(L, edge_mid1, Outcome.SUCCESS, n=20)
        walk = HistorizedQuantumWalk(L, "START", coin_mode="hadamard")
        c_mid1 = walk._gated_coin(L, "START", "MID1")
        c_mid2 = walk._gated_coin(L, "START", "MID2")
        # MID1 has conviction > 0, MID2 is virgin
        assert not np.allclose(c_mid1, c_mid2, atol=1e-10)

    def test_min_quantum_respected_in_gated_coin(self):
        """With min_quantum>0, fully confirmed edge coin != identity."""
        L = _linear(2)
        edge = Edge("A", "B")
        _inscribe(L, edge, Outcome.SUCCESS, n=500)
        walk = HistorizedQuantumWalk(L, "A", coin_mode="hadamard", min_quantum=0.5)
        gated = walk._gated_coin(L, "A", "B")
        # Should not be identity (quantum_strength >= 0.5)
        assert not np.allclose(gated, IDENTITY, atol=1e-10)

    def test_identity_coin_mode_gives_identity_always(self):
        """Identity base coin: scale_su2(I, s) = I for any s."""
        L = _linear(2)
        edge = Edge("A", "B")
        _inscribe(L, edge, Outcome.SUCCESS, n=5)
        walk = HistorizedQuantumWalk(L, "A", coin_mode="identity")
        gated = walk._gated_coin(L, "A", "B")
        assert np.allclose(gated, IDENTITY, atol=1e-12)

    def test_gated_coin_shape(self):
        L = _linear(2)
        walk = HistorizedQuantumWalk(L, "A")
        C = walk._gated_coin(L, "A", "B")
        assert C.shape == (2, 2)


# ═══════════════════════════════════════════════════════════════════════════════
# record_outcome
# ═══════════════════════════════════════════════════════════════════════════════

class TestRecordOutcome:
    def test_inscribes_on_landscape(self):
        L = _linear()
        walk = HistorizedQuantumWalk(L, "A", select_mode="argmax")
        walk.step()
        edge = Edge("A", "B")
        before = L.historization.trace_load(edge)
        walk.record_outcome(Outcome.SUCCESS)
        after = L.historization.trace_load(edge)
        assert after > before

    def test_no_steps_raises(self):
        L = _linear()
        walk = HistorizedQuantumWalk(L, "A")
        with pytest.raises(RuntimeError):
            walk.record_outcome(Outcome.SUCCESS)

    def test_escalated_step_no_inscription(self):
        L = Landscape()
        L.add_state("ALONE")
        walk = HistorizedQuantumWalk(L, "ALONE")
        walk.step()
        # Should not raise, no inscription
        walk.record_outcome(Outcome.SUCCESS)
        # Landscape has no edges, so trace_load would fail anyway — just check no error

    def test_failure_increments_failure_trace(self):
        L = _linear()
        walk = HistorizedQuantumWalk(L, "A", select_mode="argmax")
        walk.step()
        edge = Edge("A", "B")
        walk.record_outcome(Outcome.FAILURE)
        f = L.historization.failure_trace(edge)
        assert f > 0

    def test_success_increments_success_trace(self):
        L = _linear()
        walk = HistorizedQuantumWalk(L, "A", select_mode="argmax")
        walk.step()
        edge = Edge("A", "B")
        walk.record_outcome(Outcome.SUCCESS)
        u = L.historization.success_trace(edge)
        assert u > 0

    def test_multiple_recordings_accumulate(self):
        L = _linear(3)
        walk = HistorizedQuantumWalk(L, "A", select_mode="argmax")
        walk.step()  # A→B
        walk.record_outcome(Outcome.SUCCESS)
        walk.step()  # B→C
        walk.record_outcome(Outcome.SUCCESS)
        edge_ab = Edge("A", "B")
        edge_bc = Edge("B", "C")
        assert L.historization.trace_load(edge_ab) > 0
        assert L.historization.trace_load(edge_bc) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# step_with_outcome
# ═══════════════════════════════════════════════════════════════════════════════

class TestStepWithOutcome:
    def test_returns_step_and_outcome(self):
        L = _linear()
        walk = HistorizedQuantumWalk(L, "A", select_mode="argmax")
        result = walk.step_with_outcome(lambda x, y: Outcome.SUCCESS)
        assert len(result) == 2
        step, outcome = result
        assert outcome is Outcome.SUCCESS

    def test_inscribes_on_landscape(self):
        L = _linear()
        walk = HistorizedQuantumWalk(L, "A", select_mode="argmax")
        walk.step_with_outcome(lambda x, y: Outcome.SUCCESS)
        assert L.historization.trace_load(Edge("A", "B")) > 0

    def test_execute_fn_receives_correct_states(self):
        L = _linear()
        walk = HistorizedQuantumWalk(L, "A", select_mode="argmax")
        received = []
        def execute(before, after):
            received.append((before, after))
            return Outcome.SUCCESS
        walk.step_with_outcome(execute)
        assert received == [("A", "B")]

    def test_step_count_increments(self):
        L = _linear()
        walk = HistorizedQuantumWalk(L, "A", select_mode="argmax")
        walk.step_with_outcome(lambda x, y: Outcome.SUCCESS)
        assert walk.step_count == 1

    def test_escalated_records_failure(self):
        L = Landscape()
        L.add_state("ALONE")
        walk = HistorizedQuantumWalk(L, "ALONE")
        step, outcome = walk.step_with_outcome(lambda x, y: Outcome.SUCCESS)
        assert step.escalated is True
        assert outcome is Outcome.FAILURE

    def test_spinor_normalised_after_step_with_outcome(self):
        L = _diamond()
        walk = HistorizedQuantumWalk(L, "START", coin_mode="geometric")
        walk.step_with_outcome(lambda x, y: Outcome.SUCCESS)
        assert np.linalg.norm(walk.spinor) == pytest.approx(1.0, abs=1e-12)


# ═══════════════════════════════════════════════════════════════════════════════
# run_with_outcomes
# ═══════════════════════════════════════════════════════════════════════════════

class TestRunWithOutcomes:
    def test_basic_run(self):
        L = _linear(3)
        walk = HistorizedQuantumWalk(L, "A", select_mode="argmax")
        results = walk.run_with_outcomes(lambda x, y: Outcome.SUCCESS, goal="C", max_steps=10)
        assert len(results) == 2  # A→B, B→C

    def test_stops_at_goal(self):
        L = _linear(4)
        walk = HistorizedQuantumWalk(L, "A", select_mode="argmax")
        results = walk.run_with_outcomes(lambda x, y: Outcome.SUCCESS, goal="D", max_steps=20)
        assert walk.position == "D"

    def test_respects_max_steps(self):
        L = _linear(10)
        walk = HistorizedQuantumWalk(L, "A", select_mode="argmax")
        results = walk.run_with_outcomes(lambda x, y: Outcome.SUCCESS, max_steps=3)
        assert len(results) == 3

    def test_outcome_list_matches_steps(self):
        L = _linear(3)
        walk = HistorizedQuantumWalk(L, "A", select_mode="argmax")
        results = walk.run_with_outcomes(lambda x, y: Outcome.FAILURE, max_steps=5)
        for step, outcome in results:
            if not step.escalated:
                assert outcome is Outcome.FAILURE

    def test_all_inscribed_after_run(self):
        L = _linear(3)
        walk = HistorizedQuantumWalk(L, "A", select_mode="argmax")
        walk.run_with_outcomes(lambda x, y: Outcome.SUCCESS, goal="C", max_steps=10)
        assert L.historization.trace_load(Edge("A", "B")) > 0
        assert L.historization.trace_load(Edge("B", "C")) > 0

    def test_returns_list_of_tuples(self):
        L = _linear(2)
        walk = HistorizedQuantumWalk(L, "A", select_mode="argmax")
        results = walk.run_with_outcomes(lambda x, y: Outcome.SUCCESS)
        assert isinstance(results, list)
        for item in results:
            assert len(item) == 2

    def test_stops_on_escalation(self):
        L = Landscape()
        L.add_state("ALONE")
        walk = HistorizedQuantumWalk(L, "ALONE")
        results = walk.run_with_outcomes(lambda x, y: Outcome.SUCCESS, max_steps=10)
        assert len(results) == 1
        assert results[0][0].escalated

    def test_execute_fn_called_for_each_step(self):
        L = _linear(3)
        walk = HistorizedQuantumWalk(L, "A", select_mode="argmax")
        calls = []
        def execute(x, y):
            calls.append((x, y))
            return Outcome.SUCCESS
        walk.run_with_outcomes(execute, goal="C", max_steps=10)
        assert len(calls) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# Quantum-to-classical transition
# ═══════════════════════════════════════════════════════════════════════════════

class TestQuantumToClassical:
    """
    Test that repeated successes on a path cause the walk to become
    increasingly classical (deterministic) on that path.
    """

    def _run_episode(self, L: Landscape, start: str, goal: str) -> List[str]:
        walk = HistorizedQuantumWalk(L, start, coin_mode="hadamard", select_mode="argmax")
        walk.run_with_outcomes(lambda x, y: Outcome.SUCCESS, goal=goal, max_steps=20)
        return [s.state_after for s, _ in walk.history]

    def test_initial_conviction_zero(self):
        L = _diamond()
        walk = HistorizedQuantumWalk(L, "START")
        for edge in L.edges:
            assert conviction(L, edge) == pytest.approx(0.0)

    def test_conviction_grows_after_run(self):
        L = _diamond()
        walk = HistorizedQuantumWalk(L, "START", select_mode="argmax")
        steps = walk.run_with_outcomes(lambda x, y: Outcome.SUCCESS, goal="GOAL", max_steps=20)
        traversed_edges = [
            Edge(s.state_before, s.state_after)
            for s, _ in steps
            if not s.escalated
        ]
        for edge in traversed_edges:
            assert conviction(L, edge) > 0.0

    def test_quantum_strength_decreases_after_confirmations(self):
        L = _linear(2)
        # Run many successful episodes
        for _ in range(30):
            walk = HistorizedQuantumWalk(L, "A", coin_mode="hadamard", select_mode="argmax")
            walk.run_with_outcomes(lambda x, y: Outcome.SUCCESS, goal="B", max_steps=5)
        edge = Edge("A", "B")
        qs = quantum_strength(L, edge)
        assert qs < 0.8  # should have decreased from 1.0

    def test_gated_coin_closer_to_identity_after_learning(self):
        L = _linear(2)
        edge = Edge("A", "B")
        walk_before = HistorizedQuantumWalk(L, "A", coin_mode="hadamard")
        coin_before = walk_before._gated_coin(L, "A", "B")
        dist_before = float(np.linalg.norm(coin_before - IDENTITY))

        # Inscribe many successes
        _inscribe(L, edge, Outcome.SUCCESS, n=100)

        walk_after = HistorizedQuantumWalk(L, "A", coin_mode="hadamard")
        coin_after = walk_after._gated_coin(L, "A", "B")
        dist_after = float(np.linalg.norm(coin_after - IDENTITY))

        assert dist_after < dist_before

    def test_conflicted_edge_stays_quantum(self):
        """Mixed SUCCESS/FAILURE → |q| low → higher quantum_strength than a confirmed edge."""
        # Conflicted: alternating inscriptions keep quality near zero
        L_mixed = _linear(2)
        edge = Edge("A", "B")
        for _ in range(5):
            L_mixed.historization.inscribe(edge, Outcome.SUCCESS)
            L_mixed.historization.inscribe(edge, Outcome.FAILURE)

        # Confirmed: pure success on a fresh landscape
        L_pure = _linear(2)
        _inscribe(L_pure, Edge("A", "B"), Outcome.SUCCESS, n=50)

        qs_mixed = quantum_strength(L_mixed, edge)
        qs_pure = quantum_strength(L_pure, Edge("A", "B"))

        # Conflicted edge retains higher quantum_strength than confirmed edge
        assert qs_mixed > qs_pure

    def test_two_edges_different_conviction(self):
        """One confirmed edge, one virgin → different quantum strengths."""
        L = _diamond()
        edge_confirmed = Edge("START", "MID1")
        _inscribe(L, edge_confirmed, Outcome.SUCCESS, n=50)

        walk = HistorizedQuantumWalk(L, "START", coin_mode="hadamard")
        c_mid1 = conviction(L, edge_confirmed)
        c_mid2 = conviction(L, Edge("START", "MID2"))
        assert c_mid1 > c_mid2

    def test_classical_identity_coin_unaffected(self):
        """identity base coin: gating has no effect (identity stays identity)."""
        L = _linear(2)
        edge = Edge("A", "B")
        _inscribe(L, edge, Outcome.SUCCESS, n=100)
        walk = HistorizedQuantumWalk(L, "A", coin_mode="identity")
        gated = walk._gated_coin(L, "A", "B")
        assert np.allclose(gated, IDENTITY, atol=1e-12)

    def test_learning_does_not_corrupt_spinor_norm(self):
        """After a full learning run, spinor must remain normalised."""
        L = _diamond()
        walk = HistorizedQuantumWalk(L, "START", coin_mode="geometric", select_mode="argmax")
        for _ in range(20):
            walk.run_with_outcomes(
                lambda x, y: Outcome.SUCCESS if "GOAL" in y else Outcome.PARTIAL,
                goal="GOAL",
                max_steps=10,
            )
            walk.reset("START")
        assert np.linalg.norm(walk.spinor) == pytest.approx(1.0, abs=1e-12)
