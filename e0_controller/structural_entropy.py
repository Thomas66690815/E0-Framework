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
    anchor_score(s) = |q̄_s| · m_max(s) · log(1 + degree(s))
    decay_candidate(s) = anchor_score < θ_decay AND dormant > τ_dormant

Self-calibrating via Structural Temperature:
    T_s = m̄ / q̄
    where m̄ = mean trace_load, q̄ = mean |trace_quality|.

Parameter-free: all thresholds derived from existing ρ, μ, and
landscape statistics. No new tuning parameters for Type 1.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from .primitives import Edge, Outcome
from .historization import Historization
from .landscape import Landscape


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
# Dream Pressure (sleep–wake coupling)
# ---------------------------------------------------------------------------

def dream_pressure(hist: Historization, mu: float = 5.0) -> float:
    """
    How strongly the system wants to dream.

    dream_pressure = T_s / (T_s + μ)     ∈ [0, 1)

    Uses the same sigmoid shape as inertia_factor — the system's
    own half-load constant μ determines the tipping point.

    - Cold system (T_s ≈ 0): pressure ≈ 0 → keep learning
    - Warm system (T_s = μ): pressure = 0.5 → threshold
    - Hot system (T_s >> μ): pressure → 1 → dream immediately

    Parameters
    ----------
    hist : Historization
        Current historization state.
    mu : float
        Half-load reference. Same μ as inertia_factor. Default 5.0.

    Returns
    -------
    float ∈ [0, 1)
    """
    T_s = structural_temperature(hist)
    return T_s / (T_s + mu)


def should_dream(hist: Historization, mu: float = 5.0) -> bool:
    """
    Whether the system should enter dream mode.

    should_dream ⟺ dream_pressure > 0.5 ⟺ T_s > μ

    No new parameters — μ is the same half-load constant used
    throughout the system (inertia_factor, inscription_threshold,
    adaptive_mu). The threshold 0.5 is the natural midpoint of the
    sigmoid, not a tuning parameter.

    Parameters
    ----------
    hist : Historization
        Current historization state.
    mu : float
        Half-load reference. Default 5.0.

    Returns
    -------
    bool
        True if the system has accumulated enough heat to benefit
        from consolidation.
    """
    return dream_pressure(hist, mu) > 0.5


def dream_pressure_report(
    domains: Dict[str, Historization],
    mu: float = 5.0,
) -> Dict[str, Dict[str, float]]:
    """
    Dream pressure for multiple domains.

    Returns
    -------
    Dict mapping domain name → {"T_s": float, "pressure": float, "should_dream": bool}
    """
    report: Dict[str, Dict[str, float]] = {}
    for name, hist in domains.items():
        T_s = structural_temperature(hist)
        p = T_s / (T_s + mu)
        report[name] = {
            "T_s": T_s,
            "pressure": p,
            "should_dream": float(p > 0.5),
        }
    return report


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


# ---------------------------------------------------------------------------
# Anchor Analysis (Type 2 — structural decay)
# ---------------------------------------------------------------------------

def _incident_edges(state: str, all_edges: List[Edge]) -> List[Edge]:
    """Return all edges incident to a state (source or target)."""
    return [e for e in all_edges if e.source == state or e.target == state]


def anchor_score(state: str, hist: Historization,
                 all_edges: List[Edge]) -> float:
    """
    Anchor score for a state — how structurally important it is.

    anchor_score(s) = |q̄_s| · m_max(s) · log(1 + degree(s))

    Components:
    - |q̄_s|: mean |trace_quality| of incident edges — emotional clarity
    - m_max(s): max trace_load of incident edges — depth of experience
    - log(1 + degree(s)): structural centrality — hub vs leaf

    A state with strong emotional valence, deep experience, and many
    connections is an anchor. A state that is neutral, lightly
    experienced, and peripheral is not.

    Returns
    -------
    float ≥ 0
    """
    incident = _incident_edges(state, all_edges)
    if not incident:
        return 0.0

    degree = len(incident)
    total_abs_quality = 0.0
    max_load = 0.0

    for e in incident:
        total_abs_quality += abs(hist.trace_quality(e))
        load = hist.trace_load(e)
        if load > max_load:
            max_load = load

    mean_abs_quality = total_abs_quality / degree
    return mean_abs_quality * max_load * math.log(1 + degree)


def state_dormancy(state: str, hist: Historization,
                   all_edges: List[Edge]) -> int:
    """
    How many cycles since any edge incident to this state was touched.

    Returns τ − max(τ_last(e)) over incident edges.
    If no incident edges have been historized, returns τ (= fully dormant).
    """
    incident = _incident_edges(state, all_edges)
    if not incident:
        return hist.tau

    max_tau_last = 0
    any_historized = False
    for e in incident:
        tau_last = hist._tau_last.get(e, 0)
        if e in hist._U or e in hist._F:
            any_historized = True
            if tau_last > max_tau_last:
                max_tau_last = tau_last

    if not any_historized:
        return hist.tau

    return hist.tau - max_tau_last


@dataclass(frozen=True)
class DecayCandidate:
    """A state identified as eligible for structural decay."""
    state: str
    anchor_score: float
    dormancy: int
    incident_edge_count: int


def find_decay_candidates(
    states: Set[str],
    hist: Historization,
    all_edges: List[Edge],
    theta_base: float = 0.5,
    T_s: Optional[float] = None,
    tau_dormant: Optional[int] = None,
    protected: Optional[Set[str]] = None,
) -> List[DecayCandidate]:
    """
    Identify states eligible for structural decay.

    A state is a decay candidate when:
    1. anchor_score(s) < θ_decay(T_s)  — structurally unimportant
    2. dormancy(s) > τ_dormant         — has been dormant long enough
    3. s ∉ protected                    — not start/goal/current

    Parameters
    ----------
    states : Set[str]
        All states in the landscape.
    hist : Historization
        Current historization state.
    all_edges : List[Edge]
        All edges in the landscape.
    theta_base : float
        Baseline anchor threshold. The only new parameter in
        Structural Entropy. Default 0.5 (to be calibrated empirically).
    T_s : float, optional
        Structural temperature. If None, computed from hist.
    tau_dormant : int, optional
        Dormancy threshold. If None, derived from hist.rho.
    protected : Set[str], optional
        States that must never be decay candidates (start, goal, current).

    Returns
    -------
    List[DecayCandidate]
        States eligible for decay, sorted by anchor_score ascending
        (weakest anchors first).
    """
    if T_s is None:
        T_s = structural_temperature(hist)
    if tau_dormant is None:
        rho = hist.rho
        tau_dormant = dormancy_threshold(rho)
    if protected is None:
        protected = set()

    # θ_decay increases with temperature — hotter system prunes more
    theta_decay = theta_base * (1.0 + T_s)

    candidates = []
    for s in states:
        if s in protected:
            continue
        score = anchor_score(s, hist, all_edges)
        if score >= theta_decay:
            continue
        dorm = state_dormancy(s, hist, all_edges)
        if dorm < tau_dormant:
            continue
        incident = _incident_edges(s, all_edges)
        candidates.append(DecayCandidate(
            state=s,
            anchor_score=score,
            dormancy=dorm,
            incident_edge_count=len(incident),
        ))

    candidates.sort(key=lambda c: c.anchor_score)
    return candidates


def find_anchors(
    states: Set[str],
    hist: Historization,
    all_edges: List[Edge],
    theta_base: float = 0.5,
    T_s: Optional[float] = None,
) -> Set[str]:
    """
    Identify anchor states — those that will survive decay.

    An anchor is any state with anchor_score ≥ θ_decay(T_s).
    Anchors are the "landmarks" of the landscape — states with
    strong emotional (quality) signatures that serve as memory anchors.

    Returns
    -------
    Set[str]
        States that are anchors (will not decay).
    """
    if T_s is None:
        T_s = structural_temperature(hist)
    theta_decay = theta_base * (1.0 + T_s)

    return {
        s for s in states
        if anchor_score(s, hist, all_edges) >= theta_decay
    }


# ---------------------------------------------------------------------------
# DecayTrace + DecayReport (Type 2 — structural decay execution)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DecayTrace:
    """What remains after structural decay — the anchor's memory of the lost.

    An anecdote: not the full experience, but enough to recognize it
    if encountered again.  Stored per surviving neighbor state.
    """
    original_state: str
    surviving_neighbors: Tuple[str, ...]
    mean_quality: float     # was the experience good or bad?
    peak_load: float        # how significant was it?
    decayed_at_tau: int     # when it dissolved


@dataclass(frozen=True)
class DecayReport:
    """Summary of a structural decay pass."""
    removed_states: Tuple[str, ...]
    removed_edges: Tuple[Edge, ...]
    traces: Tuple[DecayTrace, ...]


def _build_decay_trace(state: str, hist: Historization,
                       all_edges: List[Edge],
                       surviving_states: Set[str]) -> DecayTrace:
    """Build a DecayTrace for a state about to be removed."""
    incident = _incident_edges(state, all_edges)

    # Surviving neighbors: states on the other end that are NOT being removed
    neighbors = set()
    for e in incident:
        other = e.target if e.source == state else e.source
        if other in surviving_states:
            neighbors.add(other)

    # Quality and load from incident edges
    qualities = []
    peak_load = 0.0
    for e in incident:
        qualities.append(hist.trace_quality(e))
        load = hist.trace_load(e)
        if load > peak_load:
            peak_load = load

    mean_q = sum(qualities) / len(qualities) if qualities else 0.0

    return DecayTrace(
        original_state=state,
        surviving_neighbors=tuple(sorted(neighbors)),
        mean_quality=mean_q,
        peak_load=peak_load,
        decayed_at_tau=hist.tau,
    )


def apply_decay(landscape: Landscape,
                candidates: List[DecayCandidate]) -> DecayReport:
    """
    Execute structural decay: remove states and create DecayTraces.

    For each candidate state:
    1. Build DecayTrace from current data
    2. Remove state + incident edges from landscape
    3. Clean up historization entries for removed edges

    The _log (audit trail) is preserved — historical events remain.

    Parameters
    ----------
    landscape : Landscape
        The landscape to modify (mutated in place).
    candidates : List[DecayCandidate]
        States to remove (from find_decay_candidates).

    Returns
    -------
    DecayReport
        Summary of removed states, edges, and traces.
    """
    if not candidates:
        return DecayReport(
            removed_states=(),
            removed_edges=(),
            traces=(),
        )

    hist = landscape.historization
    all_edges = landscape.edges
    states_to_remove = {c.state for c in candidates}
    surviving_states = landscape.states - states_to_remove

    # Phase 1: build traces BEFORE removing anything
    traces = []
    for c in candidates:
        trace = _build_decay_trace(c.state, hist, all_edges, surviving_states)
        traces.append(trace)

    # Phase 2: remove states + edges from landscape
    all_removed_edges: List[Edge] = []
    for c in candidates:
        removed = landscape.remove_state(c.state)
        all_removed_edges.extend(removed)

    # Phase 3: clean up historization
    # Deduplicate — an edge between two removed states appears twice
    unique_removed = list(dict.fromkeys(all_removed_edges))
    hist.remove_edges(unique_removed)

    return DecayReport(
        removed_states=tuple(c.state for c in candidates),
        removed_edges=tuple(unique_removed),
        traces=tuple(traces),
    )
