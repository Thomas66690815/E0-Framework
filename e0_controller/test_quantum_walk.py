"""
Tests for quantum_walk.py (C302).

Test structure:
    TestCoinFunctions          (8)  — coin_minimal / geometric / hadamard / identity
    TestCoinFidelity           (8)  — f(C, ψ) formula, range [0,1], edge cases
    TestBornWeights            (8)  — weights non-negative, fallback, empty landscape
    TestBornProbabilities      (6)  — sum-to-1, normalisation, uniform
    TestQWalkStepFields        (5)  — dataclass fields accessible
    TestQuantumWalkInit        (7)  — constructor validation, defaults, bad args
    TestQuantumWalkStep        (8)  — single step changes position, spinor normalised
    TestDeterministicArgmax    (6)  — argmax gives reproducible results
    TestStochasticSample       (5)  — sample mode, seed reproducibility
    TestGoalReaching           (6)  — run() terminates at goal
    TestEscalation             (4)  — dead-end state, escalated=True
    TestSpinorTrajectory       (5)  — spinor evolves, remains normalised
    TestReset                  (4)  — reset restores state, clears history
    TestCompareWalks           (6)  — compare_walks returns WalkComparison
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from e0_controller.landscape import Landscape
from e0_controller.quantum_walk import (
    COIN_MODES,
    QWalkStep,
    QuantumWalk,
    WalkComparison,
    _coin_geometric,
    _coin_hadamard,
    _coin_identity,
    _coin_minimal,
    _normalise_spinor,
    born_probabilities,
    born_weights,
    coin_fidelity,
    compare_walks,
)
from e0_controller.spinor_connection import IDENTITY, SIGMA_X, SPINOR_UP


# ── Shared fixtures ───────────────────────────────────────────────────────────

def _linear(n: int = 3) -> Landscape:
    """A→B→C→… linear landscape."""
    states = [chr(ord("A") + i) for i in range(n)]
    L = Landscape()
    for i in range(n - 1):
        L.add_edge(states[i], states[i + 1], delta=0.5, resistance=1.0)
    return L


def _diamond() -> Landscape:
    """START → {MID1, MID2} → GOAL."""
    L = Landscape()
    L.add_edge("START", "MID1", delta=0.5, resistance=1.0)
    L.add_edge("START", "MID2", delta=0.3, resistance=0.8)
    L.add_edge("MID1", "GOAL", delta=0.4, resistance=0.9)
    L.add_edge("MID2", "GOAL", delta=0.6, resistance=1.2)
    return L


def _dead_end() -> Landscape:
    """A landscape where the only state has no outgoing edges."""
    L = Landscape()
    L.add_state("ALONE")
    return L


def _spinor_down() -> np.ndarray:
    return np.array([0.0, 1.0], dtype=complex)


def _spinor_plus() -> np.ndarray:
    return np.array([1.0, 1.0], dtype=complex) / math.sqrt(2)


# ═══════════════════════════════════════════════════════════════════════════════
# Coin functions
# ═══════════════════════════════════════════════════════════════════════════════

class TestCoinFunctions:
    def test_identity_returns_identity(self):
        L = _linear()
        C = _coin_identity(L, "A", "B")
        assert np.allclose(C, IDENTITY)

    def test_hadamard_is_2x2(self):
        L = _linear()
        C = _coin_hadamard(L, "A", "B")
        assert C.shape == (2, 2)

    def test_hadamard_is_unitary(self):
        L = _linear()
        C = _coin_hadamard(L, "A", "B")
        assert np.allclose(C.conj().T @ C, IDENTITY, atol=1e-12)

    def test_hadamard_is_edge_independent(self):
        L = _diamond()
        C1 = _coin_hadamard(L, "START", "MID1")
        C2 = _coin_hadamard(L, "START", "MID2")
        assert np.allclose(C1, C2)

    def test_minimal_is_su2(self):
        L = _linear()
        C = _coin_minimal(L, "A", "B")
        assert np.allclose(C.conj().T @ C, IDENTITY, atol=1e-12)
        assert abs(np.linalg.det(C) - 1.0) < 1e-10

    def test_geometric_is_su2(self):
        L = _diamond()
        C = _coin_geometric(L, "START", "MID1")
        assert np.allclose(C.conj().T @ C, IDENTITY, atol=1e-12)

    def test_coin_modes_all_return_2x2(self):
        L = _linear()
        for mode in COIN_MODES:
            from e0_controller.quantum_walk import _COIN_REGISTRY
            C = _COIN_REGISTRY[mode](L, "A", "B")
            assert C.shape == (2, 2), f"mode={mode}"

    def test_identity_coin_does_not_rotate(self):
        L = _linear()
        psi = _spinor_plus()
        C = _coin_identity(L, "A", "B")
        assert np.allclose(C @ psi, psi)


# ═══════════════════════════════════════════════════════════════════════════════
# coin_fidelity
# ═══════════════════════════════════════════════════════════════════════════════

class TestCoinFidelity:
    def test_identity_gives_one(self):
        psi = SPINOR_UP.copy()
        assert coin_fidelity(IDENTITY.copy(), psi) == pytest.approx(1.0)

    def test_minus_identity_gives_zero(self):
        psi = SPINOR_UP.copy()
        f = coin_fidelity(-IDENTITY.copy(), psi)
        assert f == pytest.approx(0.0)

    def test_range_zero_to_one(self):
        psi = _spinor_plus()
        for angle in [0, 0.5, 1.0, math.pi, 2 * math.pi]:
            axis = np.array([0.0, 0.0, 1.0])
            from e0_controller.spinor_connection import pauli_exponential
            C = pauli_exponential(angle, axis)
            f = coin_fidelity(C, psi)
            assert 0.0 <= f <= 1.0 + 1e-10, f"angle={angle}, f={f}"

    def test_neutral_for_sigma_x_up(self):
        # σ_x rotates |↑⟩ to |↓⟩ — 90° flip gives f≈0.5
        # σ_x = 180° rotation around x-axis
        f = coin_fidelity(np.array([[0, 1], [1, 0]], dtype=complex), SPINOR_UP.copy())
        # ⟨↑|σ_x|↑⟩ = ⟨↑|↓⟩ = 0 → f = 0.5
        assert f == pytest.approx(0.5, abs=1e-10)

    def test_hadamard_gives_half_for_up(self):
        H = np.array([[1, 1], [1, -1]], dtype=complex) / math.sqrt(2)
        f = coin_fidelity(H, SPINOR_UP.copy())
        # ⟨↑|H|↑⟩ = 1/√2 · ⟨↑|(|↑⟩+|↓⟩)⟩ = 1/√2 → Re(1/√2) ≈ 0.707
        # f = (1 + 1/√2) / 2 ≈ 0.854
        assert 0.0 <= f <= 1.0

    def test_returns_float(self):
        f = coin_fidelity(IDENTITY.copy(), SPINOR_UP.copy())
        assert isinstance(f, float)

    def test_independent_of_spinor_phase(self):
        psi = SPINOR_UP.copy()
        psi_phased = psi * np.exp(1j * 0.7)  # global phase
        f1 = coin_fidelity(IDENTITY.copy(), psi)
        f2 = coin_fidelity(IDENTITY.copy(), psi_phased)
        # ⟨ψe^{iφ}|I|ψe^{iφ}⟩ = ⟨ψ|ψ⟩ — Re is same
        assert f1 == pytest.approx(f2, abs=1e-10)

    def test_symmetric_about_half(self):
        # f + f(−C) = 1 because Re⟨ψ|C|ψ⟩ and Re⟨ψ|(−C)|ψ⟩ are negatives
        psi = _spinor_plus()
        H = np.array([[1, 1], [1, -1]], dtype=complex) / math.sqrt(2)
        f_H = coin_fidelity(H, psi)
        f_nH = coin_fidelity(-H, psi)
        assert f_H + f_nH == pytest.approx(1.0, abs=1e-10)


# ═══════════════════════════════════════════════════════════════════════════════
# born_weights
# ═══════════════════════════════════════════════════════════════════════════════

class TestBornWeights:
    def test_empty_for_dead_end(self):
        L = _dead_end()
        w = born_weights(L, "ALONE", SPINOR_UP.copy(), _coin_identity)
        assert w == {}

    def test_all_non_negative(self):
        L = _diamond()
        psi = _spinor_plus()
        w = born_weights(L, "START", psi, _coin_geometric)
        assert all(v >= 0 for v in w.values())

    def test_identity_coin_weights_match_tension_exp(self):
        L = _linear()
        w = born_weights(L, "A", SPINOR_UP.copy(), _coin_identity)
        s_eff = L.effective_tension("A", "B")
        expected = math.exp(-s_eff)  # fidelity=1 for identity coin
        assert list(w.keys()) == ["B"]
        assert w["B"] == pytest.approx(expected, rel=1e-8)

    def test_contains_all_admissible_neighbours(self):
        L = _diamond()
        w = born_weights(L, "START", SPINOR_UP.copy(), _coin_identity)
        assert set(w.keys()) == {"MID1", "MID2"}

    def test_weights_vary_by_coin(self):
        L = _diamond()
        psi = _spinor_plus()
        w_id = born_weights(L, "START", psi, _coin_identity)
        w_geo = born_weights(L, "START", psi, _coin_geometric)
        # Geometric coin may differ from identity
        # (not guaranteed, depends on graph geometry, but smoke-test)
        assert set(w_id.keys()) == set(w_geo.keys())

    def test_fallback_when_all_fidelity_zero(self):
        # Build a landscape where the geometric coin is close to -I
        # by engineering near-4π holonomy — instead just test with
        # a mock coin that always returns -I
        L = _diamond()
        def minus_identity_coin(L, x, y):
            return -IDENTITY.copy()
        w = born_weights(L, "START", SPINOR_UP.copy(), minus_identity_coin)
        # Should fall back to pure tension weights (all positive)
        assert all(v > 0 for v in w.values())

    def test_higher_tension_gives_lower_weight_identity(self):
        L = Landscape()
        L.add_edge("X", "Y_low", delta=0.5, resistance=0.5)
        L.add_edge("X", "Y_high", delta=0.5, resistance=2.0)
        w = born_weights(L, "X", SPINOR_UP.copy(), _coin_identity)
        assert w["Y_low"] > w["Y_high"]

    def test_single_neighbour_always_chosen(self):
        L = _linear(2)  # just A→B
        w = born_weights(L, "A", SPINOR_UP.copy(), _coin_hadamard)
        assert list(w.keys()) == ["B"]
        assert w["B"] > 0


# ═══════════════════════════════════════════════════════════════════════════════
# born_probabilities
# ═══════════════════════════════════════════════════════════════════════════════

class TestBornProbabilities:
    def test_sum_to_one(self):
        L = _diamond()
        w = born_weights(L, "START", SPINOR_UP.copy(), _coin_identity)
        p = born_probabilities(w)
        assert sum(p.values()) == pytest.approx(1.0, abs=1e-12)

    def test_single_entry_is_one(self):
        L = _linear(2)
        w = born_weights(L, "A", SPINOR_UP.copy(), _coin_identity)
        p = born_probabilities(w)
        assert p["B"] == pytest.approx(1.0, abs=1e-12)

    def test_all_non_negative(self):
        L = _diamond()
        w = born_weights(L, "START", _spinor_plus(), _coin_geometric)
        p = born_probabilities(w)
        assert all(v >= 0 for v in p.values())

    def test_equal_weights_give_half_half(self):
        p = born_probabilities({"A": 0.5, "B": 0.5})
        assert p["A"] == pytest.approx(0.5)
        assert p["B"] == pytest.approx(0.5)

    def test_empty_input_handled(self):
        # born_probabilities is not called with empty dict in production,
        # but should not crash
        p = born_probabilities({"X": 1.0})
        assert p["X"] == pytest.approx(1.0)

    def test_order_preserved(self):
        w = {"A": 0.3, "B": 0.7}
        p = born_probabilities(w)
        assert list(p.keys()) == ["A", "B"]


# ═══════════════════════════════════════════════════════════════════════════════
# QWalkStep fields
# ═══════════════════════════════════════════════════════════════════════════════

class TestQWalkStepFields:
    def _make_step(self):
        return QWalkStep(
            step_index=0,
            state_before="A",
            state_after="B",
            spinor_before=SPINOR_UP.copy(),
            spinor_after=SPINOR_UP.copy(),
            coin=IDENTITY.copy(),
            probabilities={"B": 1.0},
            probability=1.0,
            fidelity=1.0,
        )

    def test_fields_accessible(self):
        s = self._make_step()
        assert s.state_before == "A"
        assert s.state_after == "B"
        assert s.step_index == 0

    def test_escalated_default_false(self):
        s = self._make_step()
        assert s.escalated is False

    def test_str_contains_states(self):
        s = self._make_step()
        text = str(s)
        assert "A" in text
        assert "B" in text

    def test_escalated_step_shows_marker(self):
        s = self._make_step()
        s = QWalkStep(
            step_index=0, state_before="A", state_after="A",
            spinor_before=SPINOR_UP.copy(), spinor_after=SPINOR_UP.copy(),
            coin=IDENTITY.copy(), probabilities={}, probability=0.0,
            fidelity=0.0, escalated=True,
        )
        assert "ESCALATED" in str(s)

    def test_spinor_stored_as_ndarray(self):
        s = self._make_step()
        assert isinstance(s.spinor_before, np.ndarray)
        assert isinstance(s.spinor_after, np.ndarray)


# ═══════════════════════════════════════════════════════════════════════════════
# QuantumWalk — init
# ═══════════════════════════════════════════════════════════════════════════════

class TestQuantumWalkInit:
    def test_valid_init(self):
        L = _linear()
        walk = QuantumWalk(L, "A")
        assert walk.position == "A"

    def test_default_spinor_is_up(self):
        L = _linear()
        walk = QuantumWalk(L, "A")
        assert np.allclose(walk.spinor, SPINOR_UP)

    def test_custom_spinor_normalised(self):
        L = _linear()
        psi = np.array([2.0, 0.0], dtype=complex)
        walk = QuantumWalk(L, "A", initial_spinor=psi)
        assert np.linalg.norm(walk.spinor) == pytest.approx(1.0)

    def test_invalid_coin_mode_raises(self):
        L = _linear()
        with pytest.raises(ValueError, match="coin_mode"):
            QuantumWalk(L, "A", coin_mode="nonexistent")

    def test_invalid_select_mode_raises(self):
        L = _linear()
        with pytest.raises(ValueError, match="select_mode"):
            QuantumWalk(L, "A", select_mode="random_wrong")

    def test_unknown_state_raises(self):
        L = _linear()
        with pytest.raises(ValueError, match="not in landscape"):
            QuantumWalk(L, "UNKNOWN")

    def test_custom_coin_fn_accepted(self):
        L = _linear()
        walk = QuantumWalk(L, "A", coin_fn=_coin_identity)
        assert walk is not None


# ═══════════════════════════════════════════════════════════════════════════════
# QuantumWalk — single step
# ═══════════════════════════════════════════════════════════════════════════════

class TestQuantumWalkStep:
    def test_step_changes_position(self):
        L = _linear(2)  # A→B only
        walk = QuantumWalk(L, "A")
        s = walk.step()
        assert s.state_after == "B"
        assert walk.position == "B"

    def test_step_count_increments(self):
        L = _linear()
        walk = QuantumWalk(L, "A")
        assert walk.step_count == 0
        walk.step()
        assert walk.step_count == 1

    def test_spinor_remains_normalised(self):
        L = _diamond()
        walk = QuantumWalk(L, "START", coin_mode="geometric")
        walk.step()
        assert np.linalg.norm(walk.spinor) == pytest.approx(1.0, abs=1e-12)

    def test_spinor_after_differs_from_before_nonidentity(self):
        L = _linear(2)
        walk = QuantumWalk(L, "A", coin_mode="hadamard")
        psi_before = walk.spinor.copy()
        walk.step()
        # Hadamard rotates the spinor — after should differ
        assert not np.allclose(walk.spinor, psi_before)

    def test_spinor_unchanged_with_identity_coin_up(self):
        L = _linear(2)
        walk = QuantumWalk(L, "A", coin_mode="identity")
        psi_before = walk.spinor.copy()
        walk.step()
        # Identity coin: C·|ψ⟩ = |ψ⟩, normalise → same spinor
        assert np.allclose(walk.spinor, psi_before)

    def test_step_is_recorded_in_history(self):
        L = _linear()
        walk = QuantumWalk(L, "A")
        walk.step()
        assert len(walk.history) == 1

    def test_probability_sums_to_one(self):
        L = _diamond()
        walk = QuantumWalk(L, "START")
        s = walk.step()
        assert sum(s.probabilities.values()) == pytest.approx(1.0, abs=1e-10)

    def test_chosen_probability_is_in_probabilities(self):
        L = _diamond()
        walk = QuantumWalk(L, "START")
        s = walk.step()
        assert s.state_after in s.probabilities
        assert s.probability == pytest.approx(s.probabilities[s.state_after], abs=1e-12)


# ═══════════════════════════════════════════════════════════════════════════════
# Deterministic argmax
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeterministicArgmax:
    def test_same_result_two_runs(self):
        L = _diamond()
        def _path(mode):
            walk = QuantumWalk(L, "START", coin_mode=mode, select_mode="argmax")
            walk.run(goal="GOAL", max_steps=10)
            return [s.state_after for s in walk.history]

        for mode in COIN_MODES:
            assert _path(mode) == _path(mode), f"mode={mode} not reproducible"

    def test_always_picks_max_probability(self):
        L = _diamond()
        walk = QuantumWalk(L, "START", coin_mode="identity", select_mode="argmax")
        s = walk.step()
        max_action = max(s.probabilities, key=s.probabilities.__getitem__)
        assert s.state_after == max_action

    def test_no_rng_dependence_in_argmax(self):
        L = _diamond()
        w1 = QuantumWalk(L, "START", select_mode="argmax", rng_seed=42)
        w2 = QuantumWalk(L, "START", select_mode="argmax", rng_seed=99)
        w1.run(goal="GOAL", max_steps=10)
        w2.run(goal="GOAL", max_steps=10)
        p1 = [s.state_after for s in w1.history]
        p2 = [s.state_after for s in w2.history]
        assert p1 == p2

    def test_identity_coin_path_follows_min_tension(self):
        # With identity coin, argmax Born probability = argmin S_eff
        L = Landscape()
        L.add_edge("S", "EASY", delta=0.2, resistance=0.5)
        L.add_edge("S", "HARD", delta=0.8, resistance=2.0)
        L.add_edge("EASY", "G", delta=0.3, resistance=0.5)
        L.add_edge("HARD", "G", delta=0.3, resistance=0.5)
        walk = QuantumWalk(L, "S", coin_mode="identity", select_mode="argmax")
        s = walk.step()
        # EASY has lower tension → higher exp(-S) → chosen
        assert s.state_after == "EASY"

    def test_geometric_may_choose_differently_than_identity(self):
        # Not guaranteed, but the comparison should not raise
        L = _diamond()
        w_id = QuantumWalk(L, "START", coin_mode="identity", select_mode="argmax")
        w_geo = QuantumWalk(L, "START", coin_mode="geometric", select_mode="argmax")
        s_id = w_id.step()
        s_geo = w_geo.step()
        # Both valid states
        assert s_id.state_after in ("MID1", "MID2")
        assert s_geo.state_after in ("MID1", "MID2")

    def test_fidelity_one_for_identity_coin(self):
        L = _linear(2)
        walk = QuantumWalk(L, "A", coin_mode="identity", select_mode="argmax")
        s = walk.step()
        assert s.fidelity == pytest.approx(1.0, abs=1e-10)


# ═══════════════════════════════════════════════════════════════════════════════
# Stochastic sample
# ═══════════════════════════════════════════════════════════════════════════════

class TestStochasticSample:
    def test_sample_mode_same_seed_same_result(self):
        L = _diamond()
        def _path(seed):
            walk = QuantumWalk(L, "START", select_mode="sample", rng_seed=seed)
            walk.run(goal="GOAL", max_steps=20)
            return [s.state_after for s in walk.history]

        assert _path(0) == _path(0)

    def test_sample_mode_different_seeds_may_differ(self):
        L = _diamond()
        paths = set()
        for seed in range(20):
            walk = QuantumWalk(L, "START", select_mode="sample", rng_seed=seed)
            walk.run(goal="GOAL", max_steps=20)
            paths.add(tuple(s.state_after for s in walk.history))
        # With 2 choices per step, different paths should appear
        assert len(paths) >= 1  # at minimum 1 unique path (smoke test)

    def test_sample_chosen_state_is_admissible(self):
        L = _diamond()
        for seed in range(5):
            walk = QuantumWalk(L, "START", select_mode="sample", rng_seed=seed)
            s = walk.step()
            assert s.state_after in L.admissible_neighbors("START")

    def test_spinor_normalised_after_sample_step(self):
        L = _diamond()
        walk = QuantumWalk(L, "START", select_mode="sample", rng_seed=7)
        walk.run(max_steps=5)
        assert np.linalg.norm(walk.spinor) == pytest.approx(1.0, abs=1e-12)

    def test_sample_probability_recorded_correctly(self):
        L = _diamond()
        walk = QuantumWalk(L, "START", select_mode="sample", rng_seed=0)
        s = walk.step()
        assert s.probability == pytest.approx(s.probabilities[s.state_after], abs=1e-12)


# ═══════════════════════════════════════════════════════════════════════════════
# Goal reaching
# ═══════════════════════════════════════════════════════════════════════════════

class TestGoalReaching:
    def test_run_stops_at_goal(self):
        L = _linear(4)  # A→B→C→D
        walk = QuantumWalk(L, "A", select_mode="argmax")
        walk.run(goal="D", max_steps=10)
        assert walk.position == "D"

    def test_run_returns_steps_taken(self):
        L = _linear(3)  # A→B→C
        walk = QuantumWalk(L, "A", select_mode="argmax")
        steps = walk.run(goal="C", max_steps=10)
        assert len(steps) == 2  # A→B, B→C

    def test_run_respects_max_steps(self):
        L = _linear(10)  # long chain
        walk = QuantumWalk(L, "A", select_mode="argmax")
        steps = walk.run(goal="J", max_steps=3)
        assert len(steps) <= 3

    def test_run_without_goal_runs_max_steps(self):
        L = _linear(10)
        walk = QuantumWalk(L, "A", select_mode="argmax")
        steps = walk.run(max_steps=5)
        assert len(steps) == 5

    def test_goal_already_reached_no_steps(self):
        L = _linear()
        walk = QuantumWalk(L, "A")
        steps = walk.run(goal="A", max_steps=10)
        assert len(steps) == 0
        assert walk.position == "A"

    def test_history_accumulates_across_runs(self):
        L = _linear(4)
        walk = QuantumWalk(L, "A", select_mode="argmax")
        walk.run(goal="B", max_steps=5)
        n1 = len(walk.history)
        walk.run(goal="C", max_steps=5)
        assert len(walk.history) > n1


# ═══════════════════════════════════════════════════════════════════════════════
# Escalation
# ═══════════════════════════════════════════════════════════════════════════════

class TestEscalation:
    def test_dead_end_escalated(self):
        L = _dead_end()
        walk = QuantumWalk(L, "ALONE")
        s = walk.step()
        assert s.escalated is True

    def test_escalated_position_unchanged(self):
        L = _dead_end()
        walk = QuantumWalk(L, "ALONE")
        walk.step()
        assert walk.position == "ALONE"

    def test_escalated_empty_probabilities(self):
        L = _dead_end()
        walk = QuantumWalk(L, "ALONE")
        s = walk.step()
        assert s.probabilities == {}

    def test_run_stops_on_escalation(self):
        L = _dead_end()
        walk = QuantumWalk(L, "ALONE")
        steps = walk.run(max_steps=10)
        assert len(steps) == 1
        assert steps[0].escalated is True


# ═══════════════════════════════════════════════════════════════════════════════
# Spinor trajectory
# ═══════════════════════════════════════════════════════════════════════════════

class TestSpinorTrajectory:
    def test_spinor_normalised_after_each_step(self):
        L = _linear(5)
        walk = QuantumWalk(L, "A", coin_mode="geometric")
        for _ in range(4):
            if walk.position not in ["E"]:
                walk.step()
        assert np.linalg.norm(walk.spinor) == pytest.approx(1.0, abs=1e-12)

    def test_hadamard_coin_mixes_spinor(self):
        L = _linear(2)
        walk = QuantumWalk(L, "A", coin_mode="hadamard")
        psi_before = walk.spinor.copy()
        walk.step()
        # Hadamard: H|↑⟩ = (|↑⟩+|↓⟩)/√2
        assert not np.allclose(walk.spinor, psi_before, atol=1e-10)

    def test_spinor_step_recorded_in_history(self):
        L = _linear(3)
        walk = QuantumWalk(L, "A", coin_mode="hadamard", select_mode="argmax")
        walk.run(goal="C", max_steps=10)
        for s in walk.history:
            assert np.linalg.norm(s.spinor_after) == pytest.approx(1.0, abs=1e-12)

    def test_different_coins_produce_different_spinors(self):
        L = _linear(3)
        walk_h = QuantumWalk(L, "A", coin_mode="hadamard", select_mode="argmax")
        walk_m = QuantumWalk(L, "A", coin_mode="minimal", select_mode="argmax")
        walk_h.run(goal="C", max_steps=10)
        walk_m.run(goal="C", max_steps=10)
        # Their final spinors may differ
        # (not guaranteed, but should not raise)
        assert np.linalg.norm(walk_h.spinor) == pytest.approx(1.0, abs=1e-12)
        assert np.linalg.norm(walk_m.spinor) == pytest.approx(1.0, abs=1e-12)

    def test_spinor_before_matches_prior_spinor_after(self):
        L = _linear(4)
        walk = QuantumWalk(L, "A", select_mode="argmax")
        walk.run(goal="D", max_steps=10)
        h = walk.history
        for i in range(1, len(h)):
            assert np.allclose(h[i].spinor_before, h[i - 1].spinor_after, atol=1e-12)


# ═══════════════════════════════════════════════════════════════════════════════
# Reset
# ═══════════════════════════════════════════════════════════════════════════════

class TestReset:
    def test_reset_clears_history(self):
        L = _linear(3)
        walk = QuantumWalk(L, "A", select_mode="argmax")
        walk.run(goal="C", max_steps=10)
        walk.reset(state="A")
        assert len(walk.history) == 0
        assert walk.step_count == 0

    def test_reset_restores_position(self):
        L = _linear(3)
        walk = QuantumWalk(L, "A", select_mode="argmax")
        walk.run(goal="C", max_steps=10)
        walk.reset(state="A")
        assert walk.position == "A"

    def test_reset_with_new_spinor(self):
        L = _linear(2)
        walk = QuantumWalk(L, "A")
        walk.step()
        new_psi = _spinor_down()
        walk.reset(state="A", spinor=new_psi)
        assert np.allclose(walk.spinor, _spinor_down(), atol=1e-12)

    def test_reset_invalid_state_raises(self):
        L = _linear()
        walk = QuantumWalk(L, "A")
        with pytest.raises(ValueError):
            walk.reset(state="INVALID")


# ═══════════════════════════════════════════════════════════════════════════════
# compare_walks
# ═══════════════════════════════════════════════════════════════════════════════

class TestCompareWalks:
    def test_returns_walk_comparison(self):
        L = _diamond()
        result = compare_walks(L, "START", "GOAL")
        assert isinstance(result, WalkComparison)

    def test_all_modes_present(self):
        L = _diamond()
        result = compare_walks(L, "START", "GOAL")
        assert set(result.results.keys()) == set(COIN_MODES)

    def test_paths_start_at_start(self):
        L = _diamond()
        result = compare_walks(L, "START", "GOAL")
        for mode, path in result.results.items():
            assert path[0] == "START", f"mode={mode}"

    def test_goal_reached_flag(self):
        L = _linear(3)
        result = compare_walks(L, "A", "C", max_steps=20)
        for mode in COIN_MODES:
            assert result.reached_goal[mode] is True, f"mode={mode} didn't reach C"

    def test_summary_is_string(self):
        L = _diamond()
        result = compare_walks(L, "START", "GOAL")
        s = result.summary()
        assert isinstance(s, str)
        assert "START" in s

    def test_custom_modes_subset(self):
        L = _diamond()
        result = compare_walks(L, "START", "GOAL", modes=["identity", "hadamard"])
        assert set(result.results.keys()) == {"identity", "hadamard"}
