"""
E₀ — Historized Quantum Walk (C303)
=====================================
Quantum Walk whose quantumness is governed by Historization.

Core innovation
---------------
In a standard quantum walk, the coin operator is fixed.
In the Historized Quantum Walk the coin is *conviction-gated*:

    conviction(e) = (m / (m + μ)) · |q(e)|    ∈ [0, 1]

where  m = trace_load(e)  and  q = trace_quality(e).

The coin rotation angle is scaled by its complement:

    quantum_strength(e) = 1 − conviction(e)   ∈ [0, 1]
    C_hist(e) = scale_su2(C_base(e), quantum_strength(e))

Meaning
-------
Virgin edge (m=0):       conviction=0, quantum_strength=1 → full quantum coin
Confirmed edge (|q|→1):  conviction→m/(m+μ) → coin scales toward Identity
Conflicted edge (|q|→0): conviction≈0, quantum_strength≈1 → full quantum coin

The walk behaves classically (tension-driven) on well-known territory and
quantumly (spin-driven exploration) on unfamiliar or contested edges.

This transition is emergent — it is not scheduled.
It arises from the Historization trace alone.

Learning cycle
--------------
The caller drives learning by calling record_outcome() after each step:

    walk = HistorizedQuantumWalk(landscape, "START", coin_mode="geometric")
    for _ in range(max_steps):
        step = walk.step()
        outcome = my_domain.execute(step.state_before, step.state_after)
        walk.record_outcome(outcome)

Over many episodes, confirmed paths consolidate into near-classical
behaviour.  Conflicted or unexplored paths remain quantum.

Phase contract
--------------
record_outcome() writes to the Landscape's Historization — this is the
ONLY mutation. No structural changes (no add_edge / remove_edge).
The quantum→classical transition is solely through trace accumulation.

Relationship to C302 (QuantumWalk)
------------------------------------
HistorizedQuantumWalk extends QuantumWalk by overriding the coin function.
All QuantumWalk behavior (Born weights, spinor update, run/reset) is
inherited unchanged.
"""

from __future__ import annotations

import math
from typing import Callable, List, Optional

import numpy as np

from .landscape import Landscape
from .primitives import Edge, Outcome
from .quantum_walk import (
    COIN_MODES,
    CoinFn,
    QuantumWalk,
    QWalkStep,
    _COIN_REGISTRY,
    _normalise_spinor,
)
from .spinor_connection import (
    IDENTITY,
    SPINOR_UP,
    pauli_exponential,
)


# ── SU(2) angle scaling ───────────────────────────────────────────────────────

def scale_su2(C: np.ndarray, scale: float) -> np.ndarray:
    """
    Scale the rotation angle of a SU(2) matrix by *scale* ∈ [0, 1].

    For C = exp(−i·θ/2·n̂·σ):

        scale_su2(C, s) = exp(−i·s·θ/2·n̂·σ)

    Special cases:
        scale = 0 → Identity  (no rotation — fully classical)
        scale = 1 → C         (full rotation — fully quantum)
        scale = 0.5 → half-angle rotation

    Decomposition:
        cos(θ/2) = Re(tr(C)) / 2
        n̂ extracted from off-diagonal elements.

    If C is already the identity (θ=0), returns Identity unchanged.
    """
    if scale < 1e-12:
        return IDENTITY.copy()
    if abs(scale - 1.0) < 1e-12:
        return C.copy()

    # Extract half-angle
    cos_half = float(np.real(np.trace(C))) / 2.0
    cos_half = max(-1.0, min(1.0, cos_half))   # clamp numerical noise
    sin_half = math.sqrt(max(0.0, 1.0 - cos_half ** 2))

    if sin_half < 1e-12:
        return IDENTITY.copy()  # C ≈ ±Identity — no axis to extract

    # Extract rotation axis from off-diagonal:
    #   C[0,0] = cos(θ/2) − i·sin(θ/2)·n_z  →  n_z = −Im(C[0,0]) / sin_half
    #   C[1,0] = −i·sin(θ/2)·(n_x + i·n_y)  →  n_x = −Im(C[1,0]) / sin_half
    #                                            n_y =  Re(C[1,0]) / sin_half
    nz = -float(np.imag(C[0, 0])) / sin_half
    nx = -float(np.imag(C[1, 0])) / sin_half
    ny =  float(np.real(C[1, 0])) / sin_half

    axis = np.array([nx, ny, nz])
    norm = float(np.linalg.norm(axis))
    if norm < 1e-12:
        axis = np.array([0.0, 0.0, 1.0])
    else:
        axis /= norm

    # Scaled rotation — full angle = 2·arccos(cos_half)
    full_angle = 2.0 * math.acos(cos_half)
    return pauli_exponential(full_angle * scale, axis)


# ── Conviction helper ─────────────────────────────────────────────────────────

def conviction(
    landscape: Landscape,
    edge: Edge,
    mu: float = 5.0,
) -> float:
    """
    Epistemic conviction for a single edge.

    conviction(e) = (m / (m + μ)) · |q(e)|    ∈ [0, 1]

    m = trace_load(e):   how much inscription
    q = trace_quality(e): how consistent the direction

    Zero for virgin edges (m=0) and for conflicted edges (|q|≈0).
    Approaches 1 as m → ∞ and |q| → 1 (high consistent experience).
    """
    h = landscape.historization
    m = h.trace_load(edge)
    if m < 1e-12:
        return 0.0
    q = h.trace_quality(edge)
    return (m / (m + mu)) * abs(q)


def quantum_strength(
    landscape: Landscape,
    edge: Edge,
    mu: float = 5.0,
    min_quantum: float = 0.0,
) -> float:
    """
    Quantum strength = 1 − conviction.

    Bounds: [min_quantum, 1].
    min_quantum > 0 ensures the walk never fully collapses to classical
    (preserves some irreducible quantum exploration).
    """
    q = conviction(landscape, edge, mu)
    return max(min_quantum, 1.0 - q)


# ── HistorizedQuantumWalk ─────────────────────────────────────────────────────

class HistorizedQuantumWalk(QuantumWalk):
    """
    Discrete coined quantum walk with conviction-gated coin operator.

    Extends QuantumWalk:
        - coin is scaled by quantum_strength(e) = 1 − conviction(e)
        - record_outcome(outcome) inscribes on the last step's edge
        - step_with_outcome(execute_fn) calls execute_fn and records

    Parameters
    ----------
    landscape        : E₀ Landscape (Historization is written by this walk).
    initial_state    : Starting position.
    coin_mode        : Base coin mode ("minimal", "geometric", etc.).
    select_mode      : "argmax" or "sample".
    initial_spinor   : Initial ℂ² spinor (default |↑⟩).
    coin_fn          : Custom base coin (overrides coin_mode).
    rng_seed         : Random seed for "sample" mode.
    mu               : Trace-load half-life for conviction (default 5.0).
    min_quantum      : Minimum quantum strength ∈ [0, 1] (default 0.0).
                       Set > 0 to preserve irreducible quantum exploration.
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
        mu: float = 5.0,
        min_quantum: float = 0.0,
    ) -> None:
        self._mu = mu
        self._min_quantum = min_quantum
        self._base_coin_fn: CoinFn = coin_fn or _COIN_REGISTRY[coin_mode]

        # We override coin_fn with our conviction-gated version.
        super().__init__(
            landscape=landscape,
            initial_state=initial_state,
            coin_mode=coin_mode,
            select_mode=select_mode,
            initial_spinor=initial_spinor,
            coin_fn=self._gated_coin,
            rng_seed=rng_seed,
        )

    def _gated_coin(self, L: Landscape, x: str, y: str) -> np.ndarray:
        """
        Conviction-gated coin.

        C_gated(x,y) = scale_su2(C_base(x,y), quantum_strength(edge))
        """
        base = self._base_coin_fn(L, x, y)
        edge = Edge(x, y)
        qs = quantum_strength(L, edge, mu=self._mu, min_quantum=self._min_quantum)
        return scale_su2(base, qs)

    # ── Outcome recording ────────────────────────────────────────────────────

    def record_outcome(self, outcome: Outcome) -> None:
        """
        Inscribe *outcome* on the edge traversed in the last step.

        Modifies the Landscape's Historization (the only mutation point).
        No-op if the last step was escalated (no edge to inscribe).
        Raises RuntimeError if no steps have been taken.
        """
        if not self._history:
            raise RuntimeError("No steps recorded — call step() first.")
        last = self._history[-1]
        if last.escalated:
            return
        edge = Edge(last.state_before, last.state_after)
        self._L.historization.inscribe(edge, outcome)

    def step_with_outcome(
        self,
        execute_fn: Callable[[str, str], Outcome],
    ) -> tuple[QWalkStep, Outcome]:
        """
        Execute one step and immediately record the outcome.

        execute_fn(state_before, state_after) → Outcome

        Returns (QWalkStep, Outcome) pair.
        Convenience wrapper around step() + record_outcome().
        """
        s = self.step()
        if not s.escalated:
            outcome = execute_fn(s.state_before, s.state_after)
        else:
            outcome = Outcome.FAILURE
        self.record_outcome(outcome)
        return s, outcome

    def run_with_outcomes(
        self,
        execute_fn: Callable[[str, str], Outcome],
        goal: Optional[str] = None,
        max_steps: int = 50,
    ) -> List[tuple[QWalkStep, Outcome]]:
        """
        Run the walk, recording outcomes at each step.

        execute_fn(state_before, state_after) → Outcome
        Stops at goal, escalation, or max_steps.
        """
        results: List[tuple[QWalkStep, Outcome]] = []
        for _ in range(max_steps):
            if goal is not None and self._position == goal:
                break
            s, outcome = self.step_with_outcome(execute_fn)
            results.append((s, outcome))
            if s.escalated:
                break
        return results

    # ── Conviction readout ───────────────────────────────────────────────────

    def conviction_map(self) -> dict:
        """
        Return conviction for every edge in the landscape.

        Useful for visualising how much of the graph has "gone classical".
        """
        result = {}
        for edge in self._L.edges:
            result[edge] = conviction(self._L, edge, mu=self._mu)
        return result

    def quantum_strength_map(self) -> dict:
        """Return quantum_strength for every edge in the landscape."""
        return {
            edge: quantum_strength(
                self._L, edge, mu=self._mu, min_quantum=self._min_quantum
            )
            for edge in self._L.edges  # type: ignore[union-attr]
        }
