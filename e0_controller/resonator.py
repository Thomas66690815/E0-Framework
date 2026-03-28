"""
E₀ Resonator Integration Module
=================================
Connects the resonator kernel (explore_resonator.py) to the controller's
amplitude overlay pipeline.

Core idea:
    If the controller is at a state that participates in a resonant
    cycle (R_coh > threshold), actions entering that cycle should
    receive an intensity boost proportional to the cycle's coherence.
    This is analogous to M_H curvature modulation but operates on
    loop-level interference rather than edge-level curvature.

Design:
    1. detect_cycles()        — find simple cycles through a state
    2. cycle_coherence()      — compute R_coh for a detected cycle
    3. resonance_map()        — per-action resonance factors
    4. build_resonance_modifier() — callable for amplitude_overlay

The modifier is applied between intensity computation and probability
normalization in analyze_controller_state(), multiplying I(a) by the
resonance factor for action a.

Resonance factor:
    action not in any cycle  →  1.0  (no change)
    action in resonant cycle  →  1 + R_coh  (boost ∈ [1.0, 2.0])

This keeps the modifier bounded and interpretable:
    R_coh = 0  →  factor 1.0 (no coherent interference → no boost)
    R_coh = 1  →  factor 2.0 (perfect coherence → double intensity)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple

from .landscape import Landscape
from .wavepath import psi, sum_paths


# ──────────────────────────────────────────────
# 1. Cycle detection
# ──────────────────────────────────────────────

def detect_cycles(
    L: Landscape,
    state: str,
    max_length: int = 4,
) -> List[List[str]]:
    """
    Find all simple cycles through 'state' with length ≤ max_length edges.

    Returns cycles as node lists [state, ..., state] where the first
    and last element are the same (the cycle closes).

    Parameters
    ----------
    L : Landscape
        The landscape to search for cycles.
    state : str
        The state to find cycles through.
    max_length : int
        Maximum number of edges in a cycle (≥ 2).
        Default 4 keeps computation bounded.
    """
    if max_length < 2:
        return []

    cycles: List[List[str]] = []
    visited_cycles: Set[tuple] = set()

    def _dfs(path: List[str], remaining: int) -> None:
        current = path[-1]
        if remaining <= 0:
            return
        for neighbor in L.admissible_neighbors(current):
            if neighbor == state and len(path) > 2:
                cycle = tuple(sorted(path[1:]))
                if cycle not in visited_cycles:
                    visited_cycles.add(cycle)
                    cycles.append(path + [state])
            elif neighbor not in path:
                _dfs(path + [neighbor], remaining - 1)

    _dfs([state], max_length)
    return cycles


# ──────────────────────────────────────────────
# 2. Cycle coherence measurement
# ──────────────────────────────────────────────

def _cycle_loop_paths(
    ring_nodes: List[str],
    n_cycles: int,
) -> List[List[str]]:
    """
    Generate loop path family for a ring.

    ring_nodes: [A, B, C] (without closing element)
    n_cycles: how many full traversals (1..n_cycles)

    Returns paths like:
        n=1: [A, B, C, A]
        n=2: [A, B, C, A, B, C, A]
    """
    start = ring_nodes[0]
    body = ring_nodes[1:] + [start]
    paths = []
    for k in range(1, n_cycles + 1):
        path = [start]
        for _ in range(k):
            path.extend(body)
        paths.append(path)
    return paths


def cycle_coherence(
    L: Landscape,
    cycle_nodes: List[str],
    n_cycles: int = 3,
) -> float:
    """
    Compute coherence ratio R_coh for a cycle.

    Parameters
    ----------
    cycle_nodes : List[str]
        Ring nodes WITHOUT the closing element.
        E.g. ["A", "B", "C"] for cycle A→B→C→A.
    n_cycles : int
        Number of loop repetitions to measure (default 3).

    Returns
    -------
    R_coh : float
        Coherence ratio I_coh / I_inc.
        0.0 if cycle edges are broken or intensity is negligible.
    """
    # Verify all edges in the cycle exist
    for i in range(len(cycle_nodes)):
        src = cycle_nodes[i]
        tgt = cycle_nodes[(i + 1) % len(cycle_nodes)]
        if L.difference(src, tgt) is None:
            return 0.0

    paths = _cycle_loop_paths(cycle_nodes, n_cycles)

    # I_coh = |Σ Ψ(p)|²
    psi_total = sum_paths(L, paths)
    I_coh = abs(psi_total) ** 2

    # I_inc = Σ |Ψ(p)|²
    I_inc = sum(abs(psi(L, p)) ** 2 for p in paths)

    if I_inc < 1e-30:
        return 0.0

    return I_coh / I_inc


# ──────────────────────────────────────────────
# 3. Resonance map
# ──────────────────────────────────────────────

@dataclass
class ResonanceInfo:
    """Per-action resonance information."""
    action: str
    factor: float                     # intensity multiplier (1.0 = no effect)
    best_r_coh: float                 # best R_coh among cycles starting with this action
    cycle_count: int                  # number of cycles found for this action
    best_cycle: Optional[List[str]]   # the cycle with highest R_coh


def resonance_map(
    L: Landscape,
    state: str,
    max_cycle_length: int = 4,
    n_cycles: int = 3,
    r_coh_threshold: float = 0.05,
) -> Dict[str, ResonanceInfo]:
    """
    Compute per-action resonance factors for all admissible actions.

    Parameters
    ----------
    L : Landscape
    state : str
        Current state.
    max_cycle_length : int
        Maximum cycle length in edges (default 4).
    n_cycles : int
        Number of loop repetitions for coherence measurement (default 3).
    r_coh_threshold : float
        Minimum R_coh to count as resonant (default 0.05).
        Below this, factor stays at 1.0.

    Returns
    -------
    Dict[str, ResonanceInfo]
        Maps action → ResonanceInfo. Only includes actions that
        participate in at least one cycle. Non-cyclic actions are
        not included (their factor is implicitly 1.0).
    """
    cycles = detect_cycles(L, state, max_cycle_length)

    # Group cycles by first action
    action_cycles: Dict[str, List[List[str]]] = {}
    for cycle in cycles:
        if len(cycle) >= 3:
            first_action = cycle[1]
            action_cycles.setdefault(first_action, []).append(cycle)

    result: Dict[str, ResonanceInfo] = {}
    for action, cycs in action_cycles.items():
        best_r_coh = 0.0
        best_cycle: Optional[List[str]] = None

        for cyc in cycs:
            ring = cyc[:-1]  # remove closing node
            r_coh = cycle_coherence(L, ring, n_cycles)
            if r_coh > best_r_coh:
                best_r_coh = r_coh
                best_cycle = cyc

        factor = (1.0 + best_r_coh) if best_r_coh >= r_coh_threshold else 1.0

        result[action] = ResonanceInfo(
            action=action,
            factor=factor,
            best_r_coh=best_r_coh,
            cycle_count=len(cycs),
            best_cycle=best_cycle,
        )

    return result


# ──────────────────────────────────────────────
# 4. Intensity modifier for amplitude overlay
# ──────────────────────────────────────────────

def build_resonance_modifier(
    L: Landscape,
    state: str,
    max_cycle_length: int = 4,
    n_cycles: int = 3,
    r_coh_threshold: float = 0.05,
) -> Callable[[str, float], float]:
    """
    Build a callable intensity modifier for analyze_controller_state().

    Returns a function (action, intensity) → modified_intensity that
    multiplies I(a) by the resonance factor for action a.

    Usage:
        modifier = build_resonance_modifier(landscape, "A")
        report = analyze_controller_state(
            controller, "A", intensity_modifier=modifier
        )
    """
    rmap = resonance_map(L, state, max_cycle_length, n_cycles, r_coh_threshold)

    def modifier(action: str, raw_intensity: float) -> float:
        info = rmap.get(action)
        if info is None:
            return raw_intensity
        return raw_intensity * info.factor

    return modifier
