"""
C104 — Emergent Locality: Historization Creates Locality
===========================================================
Demonstrates that locality is an emergent property of historization:
the system self-tunes from global exploration to local refinement
as inscription accumulates.

Core insight (user's analogy from physics):
  Early universe: inscriptions (physical laws) act globally because
  global WAS local — the system had no structure to differentiate.
  Later transitions become local because accumulated historization
  creates spatial differentiation.

In E₀ terms:
  - Fresh system: mean_load ≈ 0 → locality ≈ 0 → radius = diameter → global
  - Historized system: mean_load >> μ → locality → 1 → radius → 1 → local
  - This is NOT imposed — it emerges from the formula:
      locality = mean_load / (mean_load + μ)
      radius = max(1, ⌈(1 - locality) × D⌉)

This module provides analysis tools to observe and verify emergent
locality in running systems.

Usage:
  from e0_controller.emergent_locality import (
      track_locality_evolution,
      compute_regional_profile,
      find_phase_transition,
  )
  # Track locality evolution during navigation
  evolution = track_locality_evolution(landscape, execute_fn, start, goal)
  print(evolution.summary())
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller, RunTrace
from e0_controller.scoped_reflexion import (
    ReflexionScope,
    compute_reflexion_scope,
    _graph_diameter_estimate,
    _bfs_neighborhood,
)


# ══════════════════════════════════════════════
# Locality snapshot
# ══════════════════════════════════════════════

@dataclass
class LocalitySnapshot:
    """State of locality at one point in time."""
    step: int
    mean_load: float
    locality: float
    radius: int
    scope_size: int
    total_states: int
    diameter: int

    @property
    def coverage(self) -> float:
        """Fraction of total states included in scope."""
        return self.scope_size / self.total_states if self.total_states > 0 else 0.0


@dataclass
class RegionalProfile:
    """Per-region locality analysis within a landscape."""
    state: str
    local_mean_load: float        # mean trace_load of edges touching this state
    local_locality: float         # locality computed from local_mean_load
    global_locality: float        # system-wide locality for comparison
    edge_count: int               # edges touching this state
    differentiation: float        # |local - global| — how different from system

    @property
    def is_hot(self) -> bool:
        """Region is more historized than average."""
        return self.local_mean_load > 0 and self.differentiation > 0.1


@dataclass
class LocalityEvolution:
    """Complete record of locality evolution during navigation."""
    snapshots: List[LocalitySnapshot] = field(default_factory=list)
    mu: float = 5.0

    @property
    def initial_locality(self) -> float:
        return self.snapshots[0].locality if self.snapshots else 0.0

    @property
    def final_locality(self) -> float:
        return self.snapshots[-1].locality if self.snapshots else 0.0

    @property
    def locality_increase(self) -> float:
        return self.final_locality - self.initial_locality

    @property
    def is_monotonic(self) -> bool:
        """Locality never decreases between snapshots."""
        for i in range(1, len(self.snapshots)):
            if self.snapshots[i].locality < self.snapshots[i - 1].locality - 1e-9:
                return False
        return True

    @property
    def radius_monotonic(self) -> bool:
        """Radius never increases between snapshots."""
        for i in range(1, len(self.snapshots)):
            if self.snapshots[i].radius > self.snapshots[i - 1].radius:
                return False
        return True

    @property
    def phase_transition_step(self) -> Optional[int]:
        """Step where locality first crosses 0.5 (if ever)."""
        for s in self.snapshots:
            if s.locality >= 0.5:
                return s.step
        return None

    def summary(self) -> str:
        if not self.snapshots:
            return "No snapshots recorded."
        lines = [
            f"Locality Evolution: {len(self.snapshots)} snapshots, μ={self.mu}",
            f"  Initial: locality={self.initial_locality:.4f}, "
            f"radius={self.snapshots[0].radius}, "
            f"scope={self.snapshots[0].scope_size}/{self.snapshots[0].total_states}",
            f"  Final:   locality={self.final_locality:.4f}, "
            f"radius={self.snapshots[-1].radius}, "
            f"scope={self.snapshots[-1].scope_size}/{self.snapshots[-1].total_states}",
            f"  Increase: {self.locality_increase:+.4f}",
            f"  Monotonic: {self.is_monotonic}",
            f"  Phase transition at step: {self.phase_transition_step}",
        ]
        return "\n".join(lines)


# ══════════════════════════════════════════════
# Locality snapshot computation
# ══════════════════════════════════════════════

def snapshot_locality(
    landscape: Landscape,
    current: str,
    step: int,
    *,
    goal: Optional[str] = None,
    mu: float = 5.0,
) -> LocalitySnapshot:
    """Capture a locality snapshot at the current state."""
    scope = compute_reflexion_scope(landscape, current, goal=goal, mu=mu)
    diameter = _graph_diameter_estimate(landscape)
    return LocalitySnapshot(
        step=step,
        mean_load=scope.mean_load,
        locality=scope.locality,
        radius=scope.radius,
        scope_size=scope.scope_size,
        total_states=len(landscape.states),
        diameter=diameter,
    )


# ══════════════════════════════════════════════
# Locality evolution tracker
# ══════════════════════════════════════════════

ExecuteFn = Callable[[str, str], Outcome]


def track_locality_evolution(
    landscape: Landscape,
    execute_fn: ExecuteFn,
    start: str,
    goal: str,
    *,
    max_cycles: int = 50,
    snapshot_interval: int = 1,
    mu: float = 5.0,
) -> LocalityEvolution:
    """Run navigation and track locality at each step.

    Records how locality, radius, and scope_size evolve as the
    controller navigates and historization accumulates.

    Parameters:
        landscape: Navigation landscape
        execute_fn: Outcome function
        start: Start state
        goal: Goal state
        max_cycles: Maximum navigation steps
        snapshot_interval: Record snapshot every N steps
        mu: Half-load parameter for locality computation
    """
    evolution = LocalityEvolution(mu=mu)
    ctrl = E0Controller(landscape, execute_fn, alpha=2.0, recent_k=3)

    # Initial snapshot (step 0, before any navigation)
    snap = snapshot_locality(landscape, start, step=0, goal=goal, mu=mu)
    evolution.snapshots.append(snap)

    current = start
    for step in range(1, max_cycles + 1):
        if current == goal:
            break

        result = ctrl.cycle(current)
        if result is None:
            break
        current = result.target

        if step % snapshot_interval == 0:
            snap = snapshot_locality(
                landscape, current, step=step, goal=goal, mu=mu,
            )
            evolution.snapshots.append(snap)

    return evolution


# ══════════════════════════════════════════════
# Manual inscription tracking
# ══════════════════════════════════════════════

def track_inscription_locality(
    landscape: Landscape,
    current: str,
    *,
    rounds: int = 20,
    goal: Optional[str] = None,
    mu: float = 5.0,
) -> LocalityEvolution:
    """Track locality as uniform inscription rounds accumulate.

    Each round inscribes all edges once with SUCCESS. This isolates
    the effect of inscription depth on locality without navigation
    side effects.

    Parameters:
        landscape: Navigation landscape
        current: Center node for scope computation
        rounds: Number of inscription rounds
        goal: Optional goal node
        mu: Half-load parameter
    """
    evolution = LocalityEvolution(mu=mu)
    hist = landscape.historization

    # Snapshot before any inscription
    snap = snapshot_locality(landscape, current, step=0, goal=goal, mu=mu)
    evolution.snapshots.append(snap)

    edges = list(landscape._delta.keys())
    for r in range(1, rounds + 1):
        # Inscribe all edges uniformly
        for e in edges:
            hist.update(e, Outcome.SUCCESS)

        snap = snapshot_locality(landscape, current, step=r, goal=goal, mu=mu)
        evolution.snapshots.append(snap)

    return evolution


# ══════════════════════════════════════════════
# Regional profile
# ══════════════════════════════════════════════

def compute_regional_profile(
    landscape: Landscape,
    mu: float = 5.0,
) -> List[RegionalProfile]:
    """Compute per-state locality profile.

    For each state, computes local_mean_load from edges touching
    that state, derives local_locality, and compares to the global
    system locality.

    This reveals regional differentiation: which parts of the
    landscape are more historized than others.
    """
    hist = landscape.historization
    all_edges = list(landscape._delta.keys())

    if not all_edges:
        return []

    # Global mean
    global_loads = [hist.trace_load(e) for e in all_edges]
    global_mean = sum(global_loads) / len(global_loads)
    global_locality = global_mean / (global_mean + mu)

    # Per-state analysis
    profiles: List[RegionalProfile] = []
    for state in sorted(landscape.states):
        # Edges where this state is source or target
        touching = [e for e in all_edges
                    if e.source == state or e.target == state]
        if not touching:
            profiles.append(RegionalProfile(
                state=state,
                local_mean_load=0.0,
                local_locality=0.0,
                global_locality=round(global_locality, 4),
                edge_count=0,
                differentiation=round(global_locality, 4),
            ))
            continue

        local_loads = [hist.trace_load(e) for e in touching]
        local_mean = sum(local_loads) / len(local_loads)
        local_loc = local_mean / (local_mean + mu) if (local_mean + mu) > 0 else 0.0

        profiles.append(RegionalProfile(
            state=state,
            local_mean_load=round(local_mean, 4),
            local_locality=round(local_loc, 4),
            global_locality=round(global_locality, 4),
            edge_count=len(touching),
            differentiation=round(abs(local_loc - global_locality), 4),
        ))

    return profiles


# ══════════════════════════════════════════════
# Phase transition finder
# ══════════════════════════════════════════════

def find_phase_transition(
    landscape: Landscape,
    current: str,
    *,
    max_rounds: int = 100,
    goal: Optional[str] = None,
    mu: float = 5.0,
) -> Optional[int]:
    """Find the inscription round where locality first crosses 0.5.

    Inscribes all edges uniformly until locality ≥ 0.5 or max_rounds.
    Returns the round number, or None if never reached.

    The phase transition point equals μ: when mean_load = μ,
    locality = μ/(μ+μ) = 0.5. For uniform inscription with n rounds
    and ρ-decay, the crossing depends on ρ and edge count.
    """
    hist = landscape.historization
    edges = list(landscape._delta.keys())

    if not edges:
        return None

    for r in range(1, max_rounds + 1):
        for e in edges:
            hist.update(e, Outcome.SUCCESS)

        loads = [hist.trace_load(e) for e in edges]
        mean_load = sum(loads) / len(loads)
        locality = mean_load / (mean_load + mu)

        if locality >= 0.5:
            return r

    return None


def theoretical_phase_transition(mu: float, rho: float = 0.9) -> float:
    """Theoretical inscription rounds for locality = 0.5.

    Under uniform SUCCESS inscription with decay ρ, the steady-state
    trace_load per edge after n rounds is approximately:
        trace_load ≈ (1 - ρ^n) / (1 - ρ)    (geometric series)

    At phase transition: mean_load = μ
    Therefore: (1 - ρ^n) / (1 - ρ) = μ
    Solving: n = log(1 - μ·(1-ρ)) / log(ρ)

    If μ·(1-ρ) ≥ 1, the system never reaches phase transition
    under these parameters (mean_load bounded below μ).

    Returns predicted round count (may be fractional), or inf.
    """
    factor = mu * (1 - rho)
    if factor >= 1.0:
        return float("inf")
    return math.log(1 - factor) / math.log(rho)


# ══════════════════════════════════════════════
# Non-uniform convergence analysis (C108 / Q4)
# ══════════════════════════════════════════════

def theoretical_equilibrium_nonuniform(
    k: int,
    edge_count: int,
    mu: float,
    rho: float = 0.9,
) -> float:
    """Theoretical locality equilibrium under non-uniform inscription.

    When k edges are inscribed per round (out of |E| total), each
    inscribed edge gains 1 to its trace_load while all edges decay
    by ρ. The mean load evolves as:

        m̄_{t+1} = ρ · m̄_t + k/|E|

    Converging to m̄* = k / (|E|·(1−ρ)).

    The equilibrium locality is:

        ℓ* = m̄* / (m̄* + μ) = k / (k + |E|·μ·(1−ρ))

    Parameters:
        k: Number of edges inscribed per round
        edge_count: Total edges in graph |E|
        mu: Locality sensitivity (μ)
        rho: Decay parameter

    Returns:
        Theoretical equilibrium locality ℓ*.
    """
    if edge_count == 0 or k == 0:
        return 0.0
    m_star = k / (edge_count * (1.0 - rho))
    return m_star / (m_star + mu)


def convergence_rate_bound(
    rho: float,
    n: int,
    m_star: float,
    mu: float,
) -> float:
    """Upper bound on |ℓ* − ℓ_n| after n inscription rounds.

    The locality gap decays geometrically:
        |ℓ* − ℓ_n| ≤ μ · ρ^n · m̄* / (m̄* + μ)²

    The rate ρ^n is topology-independent; the bound magnitude
    depends on m̄* and μ (which are topology-dependent via k/|E|).

    Parameters:
        rho: Decay parameter
        n: Number of rounds
        m_star: Steady-state mean load
        mu: Locality sensitivity

    Returns:
        Upper bound on the convergence gap.
    """
    denominator = (m_star + mu) ** 2
    if denominator < 1e-12:
        return 0.0
    return mu * (rho ** n) * m_star / denominator


def track_nonuniform_convergence(
    landscape: Landscape,
    current: str,
    inscribed_edges: List[Edge],
    *,
    rounds: int = 30,
    goal: Optional[str] = None,
    mu: float = 5.0,
) -> LocalityEvolution:
    """Track locality under non-uniform inscription.

    Only the specified edges receive inscription each round,
    simulating a controller that traverses a fixed subset of the
    graph (e.g., a single path through a larger topology).

    Parameters:
        landscape: Navigation landscape
        current: Center for scope computation
        inscribed_edges: Subset of edges that get inscribed each round
        rounds: Number of inscription rounds
        goal: Optional goal node
        mu: Half-load parameter
    """
    evolution = LocalityEvolution(mu=mu)
    hist = landscape.historization

    snap = snapshot_locality(landscape, current, step=0, goal=goal, mu=mu)
    evolution.snapshots.append(snap)

    for r in range(1, rounds + 1):
        for e in inscribed_edges:
            hist.update(e, Outcome.SUCCESS)

        snap = snapshot_locality(landscape, current, step=r, goal=goal, mu=mu)
        evolution.snapshots.append(snap)

    return evolution
