"""
E₀ — Quantum Walk (C302)
=========================
Discrete coined quantum walk on an E₀ Landscape.

Architecture
------------
Classical E₀ controller:  greedy argmin(S_penalized) — deterministic.
Quantum Walk (this module): Born-rule selection weighted by coin-fidelity × tension.

At each node x with current spin |ψ⟩ ∈ ℂ², the walk:

    COIN    — for each admissible neighbor y compute the SU(2) coin C(x,y)
    BORN    — weight w(y) = f(C, ψ) · exp(−S_eff(x,y))
              where f(C, ψ) = (1 + Re⟨ψ|C|ψ⟩) / 2  ∈ [0, 1]
    SELECT  — choose next state (deterministic argmax or stochastic sampling)
    STEP    — move position, update spinor: |ψ'⟩ = C(x,y*)|ψ⟩ / ‖…‖

The SU(2) coin C(x,y) comes from the existing spinor_connection layer:
    "minimal"   — U(x,y) = exp(−iω/2·σ_z)             (U(1) embedded in SU(2))
    "geometric" — su2_geometric_transport(L, x, y)     (full A₁,A₂,A₃ coupling)
    "hadamard"  — H = 1/√2·[[1,1],[1,−1]]              (topology-independent)
    "identity"  — 𝕀 ∈ ℂ²ˣ² (degenerate, reduces to Boltzmann walk)

Fidelity factor f(C, ψ)
-----------------------
f = (1 + Re⟨ψ|C|ψ⟩) / 2   always in [0, 1].

Interpretation:
    f = 1   → C = 𝕀     — coin preserves spin direction (maximum weight)
    f = 0.5 → C is a 90° rotation — spin-neutral
    f = 0   → C = −𝕀    — complete phase reversal (quantum suppression)

Classical limit: coin_mode="identity" → f=1 for all edges → p(y) ∝ exp(−S_eff).
Quantum effect:  geometry-derived coins vary by edge → different neighbours receive
                 different spin-dependent weight boosts/suppressions.

Connection to classical E₀
---------------------------
select_mode="argmax", coin_mode="identity" ≈ greedy E₀ (without revisit penalty).
select_mode="argmax", coin_mode="geometric" = quantum walk in deterministic mode —
    coin rotations shift which neighbour has the highest weight, potentially
    overriding the purely tension-based greedy choice.

Phase contract
--------------
This module does NOT modify the Landscape or its Historization.
Landscape is read-only here.
Historization coupling lives in quantum_walk_historized.py (C303).

Usage
-----
    walk = QuantumWalk(landscape, "START", coin_mode="geometric")
    history = walk.run(goal="GOAL", max_steps=20)
    for step in history:
        print(step)
"""

from __future__ import annotations

import math
import dataclasses
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from .landscape import Landscape
from .spinor_connection import (
    IDENTITY,
    SPINOR_UP,
    pauli_exponential,
    su2_edge_transport,
    su2_geometric_transport,
)

# ── Type alias ────────────────────────────────────────────────────────────────

CoinFn = Callable[[Landscape, str, str], np.ndarray]

# ── Coin factories ─────────────────────────────────────────────────────────────

def _coin_minimal(L: Landscape, x: str, y: str) -> np.ndarray:
    """Minimal embedding: U(1) phase ω(x,y) lifted to SU(2) on σ_z axis."""
    return su2_edge_transport(L, x, y)   # default axis = ẑ


def _coin_geometric(L: Landscape, x: str, y: str) -> np.ndarray:
    """Full geometry-derived SU(2) coin: A₁(σ_x) + A₂(σ_y) + A₃(σ_z) coupling."""
    return su2_geometric_transport(L, x, y)


_HADAMARD = np.array([[1, 1], [1, -1]], dtype=complex) / math.sqrt(2)

def _coin_hadamard(L: Landscape, x: str, y: str) -> np.ndarray:
    """Topology-independent Hadamard coin H = 1/√2·[[1,1],[1,−1]]."""
    return _HADAMARD.copy()


def _coin_identity(L: Landscape, x: str, y: str) -> np.ndarray:
    """Identity coin — classical limit, no spin-dependent weighting."""
    return IDENTITY.copy()


_COIN_REGISTRY: Dict[str, CoinFn] = {
    "minimal":   _coin_minimal,
    "geometric": _coin_geometric,
    "hadamard":  _coin_hadamard,
    "identity":  _coin_identity,
}

COIN_MODES = tuple(_COIN_REGISTRY.keys())


# ── Core helpers ──────────────────────────────────────────────────────────────

def _normalise_spinor(v: np.ndarray) -> np.ndarray:
    """Return normalised ℂ² vector. If near-zero, return |↑⟩."""
    n = float(np.linalg.norm(v))
    if n < 1e-15:
        return SPINOR_UP.copy()
    return v / n


def coin_fidelity(coin: np.ndarray, spinor: np.ndarray) -> float:
    """
    Quantum fidelity factor for one edge coin applied to current spinor.

    f(C, ψ) = (1 + Re⟨ψ|C|ψ⟩) / 2    ∈ [0, 1]

    When C = 𝕀:   f = 1  (coin preserves spin, maximum weight).
    When C = −𝕀:  f = 0  (complete phase reversal, zero weight).
    When C = σ_x, ψ = |↑⟩: f = 0.5 (neutral — no spin preference).
    """
    expectation = np.vdot(spinor, coin @ spinor)   # ψ†·C·ψ ∈ ℂ
    return (1.0 + float(np.real(expectation))) / 2.0


def born_weights(
    L: Landscape,
    current: str,
    spinor: np.ndarray,
    coin_fn: CoinFn,
) -> Dict[str, float]:
    """
    Raw Born weights for each admissible neighbour of *current*.

    w(y) = coin_fidelity(C(current, y), ψ) · exp(−S_eff(current, y))

    Falls back to pure tension weights (f=1) if all fidelity-weighted
    sums are zero (avoids degenerate dead-end from quantum suppression).

    Returns {} when there are no admissible neighbours.
    """
    raw: Dict[str, float] = {}
    for y in L.admissible_neighbors(current):
        s_eff = L.effective_tension(current, y)
        if math.isinf(s_eff):
            continue
        coin = coin_fn(L, current, y)
        f = coin_fidelity(coin, spinor)
        raw[y] = f * math.exp(-s_eff)

    if not raw:
        return {}

    # Fallback: if all quantum weights are zero (e.g. all coins = −𝕀)
    # use pure tension weighting to stay functional.
    if sum(raw.values()) < 1e-30:
        return {
            y: math.exp(-L.effective_tension(current, y))
            for y in raw
        }
    return raw


def born_probabilities(weights: Dict[str, float]) -> Dict[str, float]:
    """Normalise raw Born weights to probabilities (sum = 1)."""
    total = sum(weights.values())
    if total < 1e-30:
        n = len(weights)
        return {y: 1.0 / n for y in weights}
    return {y: w / total for y, w in weights.items()}


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class QWalkStep:
    """
    Record of one quantum walk step.

    Attributes
    ----------
    step_index    : 0-based step counter.
    state_before  : Position before the step.
    state_after   : Position after the step (= action taken).
    spinor_before : Spinor |ψ⟩ before coin application (normalised ℂ²).
    spinor_after  : Spinor |ψ'⟩ = C·|ψ⟩/‖…‖ (normalised ℂ²).
    coin          : 2×2 SU(2) matrix applied on the selected edge.
    probabilities : Born probabilities for all neighbours at this step.
    probability   : Born probability of the chosen action.
    fidelity      : Coin fidelity f(C, ψ) for the chosen edge.
    escalated     : True when no admissible neighbours exist.
    """
    step_index:    int
    state_before:  str
    state_after:   str
    spinor_before: np.ndarray
    spinor_after:  np.ndarray
    coin:          np.ndarray
    probabilities: Dict[str, float]
    probability:   float
    fidelity:      float
    escalated:     bool = False

    def __str__(self) -> str:
        esc = " [ESCALATED]" if self.escalated else ""
        return (
            f"QW T{self.step_index:02d}{esc}  "
            f"{self.state_before} → {self.state_after}  "
            f"p={self.probability:.3f}  f={self.fidelity:.3f}"
        )


# ── QuantumWalk ───────────────────────────────────────────────────────────────

class QuantumWalk:
    """
    Discrete coined quantum walk on an E₀ Landscape.

    Parameters
    ----------
    landscape       : E₀ Landscape (read-only during the walk).
    initial_state   : Starting position.
    coin_mode       : One of "minimal", "geometric", "hadamard", "identity".
    select_mode     : "argmax" (deterministic) or "sample" (stochastic).
    initial_spinor  : Starting ℂ² spinor. Defaults to |↑⟩ = [1, 0].
    coin_fn         : Custom coin callable (L, x, y) → 2×2 matrix.
                      Overrides coin_mode when provided.
    rng_seed        : Optional seed for reproducibility in "sample" mode.
    """

    def __init__(
        self,
        landscape: Landscape,
        initial_state: str,
        coin_mode: str = "geometric",
        select_mode: str = "argmax",
        initial_spinor: Optional[np.ndarray] = None,
        coin_fn: Optional[CoinFn] = None,
        rng_seed: Optional[int] = None,
    ) -> None:
        if coin_mode not in COIN_MODES and coin_fn is None:
            raise ValueError(
                f"coin_mode must be one of {COIN_MODES}, got {coin_mode!r}"
            )
        if select_mode not in ("argmax", "sample"):
            raise ValueError(
                f"select_mode must be 'argmax' or 'sample', got {select_mode!r}"
            )
        if initial_state not in landscape.states:
            raise ValueError(
                f"initial_state {initial_state!r} not in landscape"
            )

        self._L = landscape
        self._coin_fn: CoinFn = coin_fn or _COIN_REGISTRY[coin_mode]
        self._select_mode = select_mode
        self._rng = np.random.default_rng(rng_seed)

        # Walk state
        self._position = initial_state
        self._spinor = _normalise_spinor(
            initial_spinor.copy() if initial_spinor is not None
            else SPINOR_UP.copy()
        )
        self._step_count = 0
        self._history: List[QWalkStep] = []

    # ── Properties ──────────────────────────────────────────────────

    @property
    def position(self) -> str:
        return self._position

    @property
    def spinor(self) -> np.ndarray:
        return self._spinor.copy()

    @property
    def step_count(self) -> int:
        return self._step_count

    @property
    def history(self) -> List[QWalkStep]:
        return list(self._history)

    # ── Core step ───────────────────────────────────────────────────

    def step(self) -> QWalkStep:
        """
        Execute one quantum walk step.

        Returns a QWalkStep record. If no admissible neighbours exist,
        returns an escalated step (position unchanged, spinor unchanged).
        """
        x = self._position
        psi_before = self._spinor.copy()

        weights = born_weights(self._L, x, psi_before, self._coin_fn)

        if not weights:
            # No admissible neighbours — escalation
            step = QWalkStep(
                step_index=self._step_count,
                state_before=x,
                state_after=x,
                spinor_before=psi_before,
                spinor_after=psi_before.copy(),
                coin=IDENTITY.copy(),
                probabilities={},
                probability=0.0,
                fidelity=0.0,
                escalated=True,
            )
            self._step_count += 1
            self._history.append(step)
            return step

        probs = born_probabilities(weights)

        # Select next state
        if self._select_mode == "argmax":
            y = max(probs, key=lambda s: probs[s])
        else:
            states_list = list(probs.keys())
            prob_array = np.array([probs[s] for s in states_list])
            idx = int(self._rng.choice(len(states_list), p=prob_array))
            y = states_list[idx]

        # Apply coin and update spinor
        coin = self._coin_fn(self._L, x, y)
        psi_after = _normalise_spinor(coin @ psi_before)
        f = coin_fidelity(coin, psi_before)

        step = QWalkStep(
            step_index=self._step_count,
            state_before=x,
            state_after=y,
            spinor_before=psi_before,
            spinor_after=psi_after,
            coin=coin.copy(),
            probabilities=dict(probs),
            probability=probs[y],
            fidelity=f,
            escalated=False,
        )

        self._position = y
        self._spinor = psi_after
        self._step_count += 1
        self._history.append(step)
        return step

    def run(
        self,
        goal: Optional[str] = None,
        max_steps: int = 50,
    ) -> List[QWalkStep]:
        """
        Run the walk until goal is reached or max_steps exceeded.

        Stops immediately when:
            - position == goal (if goal is specified), OR
            - an escalated step is returned, OR
            - max_steps steps have been taken.

        Returns the history of steps taken during this call.
        """
        steps_taken: List[QWalkStep] = []
        for _ in range(max_steps):
            if goal is not None and self._position == goal:
                break
            s = self.step()
            steps_taken.append(s)
            if s.escalated:
                break
        return steps_taken

    def reset(
        self,
        state: Optional[str] = None,
        spinor: Optional[np.ndarray] = None,
    ) -> None:
        """
        Reset position and/or spinor without changing coin/select config.

        Clears step history.
        """
        if state is not None:
            if state not in self._L.states:
                raise ValueError(f"State {state!r} not in landscape")
            self._position = state
        if spinor is not None:
            self._spinor = _normalise_spinor(spinor.copy())
        self._step_count = 0
        self._history = []


# ── Convenience: compare walk modes ──────────────────────────────────────────

@dataclass
class WalkComparison:
    """
    Side-by-side comparison of multiple walk modes on the same landscape.

    Fields
    ------
    start         : Starting state.
    goal          : Target state.
    results       : Dict mapping mode name → list of visited states.
    step_counts   : Dict mapping mode name → steps taken.
    reached_goal  : Dict mapping mode name → bool.
    """
    start:        str
    goal:         str
    results:      Dict[str, List[str]]
    step_counts:  Dict[str, int]
    reached_goal: Dict[str, bool]

    def summary(self) -> str:
        lines = [f"WalkComparison  {self.start} → {self.goal}"]
        for mode, path in self.results.items():
            r = "✓" if self.reached_goal[mode] else "✗"
            lines.append(
                f"  {mode:<12}  {r}  steps={self.step_counts[mode]:3d}  "
                f"path={' → '.join(path)}"
            )
        return "\n".join(lines)


def compare_walks(
    L: Landscape,
    start: str,
    goal: str,
    max_steps: int = 30,
    modes: Optional[List[str]] = None,
    initial_spinor: Optional[np.ndarray] = None,
) -> WalkComparison:
    """
    Run multiple coin modes on the same landscape, return comparison.

    Default modes: all four COIN_MODES.
    All walks use select_mode="argmax" for reproducibility.
    """
    if modes is None:
        modes = list(COIN_MODES)

    results: Dict[str, List[str]] = {}
    step_counts: Dict[str, int] = {}
    reached: Dict[str, bool] = {}

    for mode in modes:
        walk = QuantumWalk(
            L, start,
            coin_mode=mode,
            select_mode="argmax",
            initial_spinor=initial_spinor,
        )
        walk.run(goal=goal, max_steps=max_steps)
        path = [start] + [s.state_after for s in walk.history]
        results[mode] = path
        step_counts[mode] = walk.step_count
        reached[mode] = walk.position == goal

    return WalkComparison(
        start=start,
        goal=goal,
        results=results,
        step_counts=step_counts,
        reached_goal=reached,
    )
