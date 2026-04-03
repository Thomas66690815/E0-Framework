"""
E₀ Controller — Structural Entropy
====================================
Forgetting as structural necessity: the destructive complement to inscription.

Design reference: docs/E0_STRUCTURAL_ENTROPY_DESIGN_v1.md

Two forgetting types:

  Type 1 — Inscription Threshold (Non-Inscription):
    Routine transitions are not recorded when the outcome is expected.
    novelty(e, outcome) = |signal(outcome) − trace_quality(e)|
    inscription gate: novelty > ε(e)
    where ε(e) = ε₀(T_s) · (1 − exp(−trace_load(e)/μ))

  Type 2 — Structural Decay (Anchor-Based Pruning):
    → Implemented in a later commit (C116).

Self-calibrating via Structural Temperature:
    T_s = m̄ / q̄
    where m̄ = mean trace_load, q̄ = mean |trace_quality|.

Parameter-free: all thresholds derived from existing ρ, μ, and
landscape statistics. No new tuning parameters for Type 1.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from .primitives import Edge, Outcome
from .historization import Historization


# ---------------------------------------------------------------------------
# Structural Temperature
# ---------------------------------------------------------------------------

def structural_temperature(hist: Historization) -> float:
    """
    Structural temperature of a historized system.

    T_s = m̄ / q̄

    where:
      m̄ = mean(trace_load(e)) over all historized edges
      q̄ = mean(|trace_quality(e)|) over all historized edges + ε

    High T_s: much experience, little clarity → system "runs hot"
    Low T_s:  little experience or clear judgments → system is "cold"
    T_s = 0:  no historized edges (virgin system)

    Returns
    -------
    float ≥ 0
    """
    all_edges = list(set(hist._U.keys()) | set(hist._F.keys()))
    if not all_edges:
        return 0.0

    total_load = 0.0
    total_abs_quality = 0.0
    for e in all_edges:
        total_load += hist.trace_load(e)
        total_abs_quality += abs(hist.trace_quality(e))

    n = len(all_edges)
    mean_load = total_load / n
    mean_abs_quality = total_abs_quality / n + 1e-12

    return mean_load / mean_abs_quality


# ---------------------------------------------------------------------------
# Inscription Threshold (Type 1)
# ---------------------------------------------------------------------------

def _signal(outcome: Outcome) -> float:
    """Map outcome to signal value."""
    if outcome == Outcome.SUCCESS:
        return 1.0
    elif outcome == Outcome.FAILURE:
        return -1.0
    else:
        return 0.0  # PARTIAL


def novelty(edge: Edge, outcome: Outcome, hist: Historization) -> float:
    """
    Novelty of an outcome on an edge given prior experience.

    novelty(e, outcome) = |signal(outcome) − trace_quality(e)|

    Range: [0, 2]
      0 = outcome perfectly matches expectation
      2 = outcome is maximally surprising (expected +1, got -1)

    Virgin edges have trace_quality ≈ 0, so any definite outcome
    has novelty ≈ 1.
    """
    expected = hist.trace_quality(edge)
    return abs(_signal(outcome) - expected)


def inscription_threshold(edge: Edge, hist: Historization,
                          T_s: float,
                          mu: float = 5.0) -> float:
    """
    Per-edge inscription threshold.

    ε(e) = ε₀(T_s) · (1 − exp(−trace_load(e) / μ))

    where ε₀(T_s) = 1 − exp(−T_s / μ)

    Properties:
    - Virgin edge (trace_load = 0) → ε = 0 → always inscribed
    - Cold system (T_s ≈ 0) → ε₀ ≈ 0 → everything inscribed
    - Hot system (T_s >> μ) → ε₀ → 1 → only extreme surprises inscribed
    - Experienced edge (trace_load >> μ) → ε ≈ ε₀ → full threshold active

    Parameters
    ----------
    edge : Edge
        The edge to compute threshold for.
    hist : Historization
        Historization state.
    T_s : float
        Structural temperature (precomputed).
    mu : float
        Half-load reference (same as inertia_factor). Default 5.0.

    Returns
    -------
    float in [0, 1)
    """
    epsilon_0 = 1.0 - math.exp(-T_s / mu)
    m = hist.trace_load(edge)
    load_factor = 1.0 - math.exp(-m / mu)
    return epsilon_0 * load_factor


def should_inscribe(edge: Edge, outcome: Outcome,
                    hist: Historization,
                    T_s: Optional[float] = None,
                    mu: float = 5.0) -> bool:
    """
    Decide whether a transition outcome should be inscribed.

    should_inscribe = novelty(e, outcome) > ε(e)

    When False: historize_outcome() should be skipped, along with
    reflexive overhead (self_graph, dual_reflection, dream_mode).
    The controller operates on "autopilot" — navigating on inertia.

    Parameters
    ----------
    edge : Edge
        The edge that was traversed.
    outcome : Outcome
        The outcome of the transition.
    hist : Historization
        Current historization state.
    T_s : float, optional
        Structural temperature. If None, computed from hist.
    mu : float
        Half-load reference. Default 5.0.

    Returns
    -------
    bool
        True if the outcome should be inscribed (it's novel enough).
    """
    if T_s is None:
        T_s = structural_temperature(hist)

    n = novelty(edge, outcome, hist)
    eps = inscription_threshold(edge, hist, T_s, mu)
    return n > eps


def dormancy_threshold(rho: float, trace_floor: float = 0.01) -> int:
    """
    How many cycles of inactivity before a state is eligible for decay.

    τ_dormant = ⌈log(trace_floor) / log(ρ)⌉

    Derived from existing ρ — no new parameter.

    At ρ = 0.95: ~90 cycles
    At ρ = 0.99: ~459 cycles
    At ρ = 0.90: ~44 cycles

    Parameters
    ----------
    rho : float
        Decay rate from Historization.
    trace_floor : float
        Fraction of peak below which trace is considered dormant.
        Default 0.01 (1% of peak).

    Returns
    -------
    int ≥ 1
    """
    if rho <= 0.0 or rho >= 1.0:
        raise ValueError(f"rho must be in (0, 1), got {rho}")
    return max(1, math.ceil(math.log(trace_floor) / math.log(rho)))
