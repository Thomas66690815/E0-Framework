"""
Cross-Universe Reflexive Edge Discovery (C62, C107)
=====================================================
When Universe A is stuck at a frontier, Universe B's accumulated
experience informs hypothesis edges in A's topology.

Key distinction from existing mechanisms:

  - C56 Reactive Reflexion:  A proposes edges from A's own experience.
  - C57 Proactive Reflexion: A proposes edges before getting stuck.
  - C61 Knowledge Exchange:  Copy existing edges from A → B.
  - C62 Cross Reflexion:     B's experience pattern (Δ/R₀ medians)
                              parameterizes NEW edges in A that never
                              existed in either universe.
  - C107 Scoped Cross Reflexion: Like C62, but donor pattern extraction
                              respects the donor's historization-derived
                              locality.  Discount scales with donor ℓ.

Core insight: "Die Erfahrung des Anderen ist nicht meine eigene,
aber sie kann meine Hypothesen informieren."

The coupling discount (default 0.5) inflates R₀ for cross-proposed
edges — the structural recognition that foreign experience carries
more uncertainty than self-experience.  With scoped=True (C107), the
effective discount is further modulated by donor locality:
  effective = discount × (γ_min + (1 − γ_min) × ℓ_donor)

Usage:
  from e0_controller.cross_reflexion import (
      cross_propose_edges, apply_cross_proposals,
      cross_reflexion_turn, scoped_cross_reflexion_turn,
  )

  # Standalone (global):
  result = cross_propose_edges(stuck_landscape, donor_landscape, "X", "GOAL")

  # Standalone (scoped / C107):
  result = cross_propose_edges(stuck, donor, "X", "GOAL", scoped=True)

  # As MultiverseController turn function:
  ctrl = MultiverseController(universe_a, universe_b)
  result = ctrl.run(max_turns=20, turn_fn=scoped_cross_reflexion_turn)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Set

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.config import DEFAULTS
from e0_controller.controller import E0Controller
from e0_controller.reflexive_edge_proposal import (
    EdgePattern,
    ProposedEdge,
    experienced_pattern,
    find_candidate_targets,
    is_frontier,
    apply_proposals,
    _goal_proximity,
)
from e0_controller.multiverse import Universe
from e0_controller.scoped_reflexion import (
    compute_reflexion_scope,
    scoped_experienced_pattern,
    ReflexionScope,
)


# ══════════════════════════════════════════════
# Cross-reflexion result
# ══════════════════════════════════════════════

@dataclass
class CrossReflexionResult:
    """Outcome of a cross-universe reflexive edge proposal."""
    proposals: List[ProposedEdge]
    self_pattern: EdgePattern
    donor_pattern: EdgePattern
    edges_added: int
    frontier_node: str
    donor_name: str


# ══════════════════════════════════════════════
# Blended pattern
# ══════════════════════════════════════════════

def blend_patterns(
    self_pattern: EdgePattern,
    donor_pattern: EdgePattern,
    coupling_discount: float = 0.5,
) -> EdgePattern:
    """Blend own experience with donor experience.

    If own pattern has samples, weight it more (it's local knowledge).
    If own has no samples (no successful edges), use donor entirely.

    The coupling_discount scales the donor's contribution weight.
    """
    self_w = self_pattern.sample_size
    donor_w = donor_pattern.sample_size * coupling_discount

    total = self_w + donor_w
    if total == 0:
        # Neither has experience — use donor's raw values as best guess
        return EdgePattern(
            median_delta=donor_pattern.median_delta,
            median_r0=donor_pattern.median_r0,
            sample_size=0,
            coverage=0.0,
        )

    # Weighted blend
    delta = (
        self_pattern.median_delta * self_w
        + donor_pattern.median_delta * donor_w
    ) / total
    r0 = (
        self_pattern.median_r0 * self_w
        + donor_pattern.median_r0 * donor_w
    ) / total

    return EdgePattern(
        median_delta=round(delta, 4),
        median_r0=round(r0, 4),
        sample_size=self_pattern.sample_size + donor_pattern.sample_size,
        coverage=(
            self_pattern.coverage * self_w
            + donor_pattern.coverage * donor_w
        ) / total,
    )


# ══════════════════════════════════════════════
# Donor scope helpers (C107)
# ══════════════════════════════════════════════

# Minimum discount floor: even a fresh donor contributes γ_min weight.
_GAMMA_MIN = DEFAULTS.gamma_min


def _donor_scope_center(donor: Landscape, current: str) -> str:
    """Choose scope center in donor landscape.

    If `current` exists in donor, use it directly.
    Otherwise, pick the node with the highest total trace_load
    (the donor's expertise center).  Falls back to the first
    state alphabetically if all loads are zero.
    """
    if current in donor.states:
        return current
    best, best_load = None, -1.0
    hist = donor.historization
    for edge in donor._delta:
        load = hist.trace_load(edge)
        if load > best_load:
            best_load = load
            best = edge.source
        # also consider target side
        if load > best_load:
            best = edge.target
    if best is not None:
        return best
    return min(donor.states) if donor.states else current


def _locality_modulated_discount(
    base_discount: float,
    donor_locality: float,
) -> float:
    """Scale coupling discount by donor locality (C107).

    effective = base × (γ_min + (1 − γ_min) × ℓ_donor)

    Fresh donor (ℓ ≈ 0):  effective ≈ base × 0.3  (little trust)
    Expert donor (ℓ → 1): effective → base          (full trust)
    """
    return base_discount * (_GAMMA_MIN + (1.0 - _GAMMA_MIN) * donor_locality)


# ══════════════════════════════════════════════
# Cross proposal engine
# ══════════════════════════════════════════════

def cross_propose_edges(
    landscape: Landscape,
    donor: Landscape,
    current: str,
    goal: str,
    *,
    max_proposals: int = DEFAULTS.max_proposals,
    coupling_discount: float = DEFAULTS.coupling_discount,
    donor_name: str = "donor",
    scoped: bool = False,
) -> CrossReflexionResult:
    """Propose hypothesis edges using blended self + donor experience.

    Pipeline:
      1. Extract self pattern (own successful edges)
      2. Extract donor pattern (donor's successful edges)
      3. Blend with coupling discount (donor weighted less)
      4. Find candidate targets in own landscape
      5. Scale R₀ by blended confidence (lower → more cautious)
      6. Sort by goal proximity

    The coupling_discount (0–1) controls how much donor experience
    contributes. 1.0 = full trust, 0.0 = ignore donor entirely.

    If scoped=True (C107), the donor pattern is extracted from the
    donor's historization-derived scope rather than globally, and the
    coupling discount is modulated by donor locality:
      effective_discount = discount × (γ_min + (1 − γ_min) × ℓ_donor)
    Fresh donors contribute less; experienced donors contribute more.
    """
    self_pattern = experienced_pattern(landscape)

    if scoped:
        center = _donor_scope_center(donor, current)
        donor_scope = compute_reflexion_scope(donor, center, goal=goal)
        donor_pattern = scoped_experienced_pattern(donor, donor_scope)
        effective_discount = _locality_modulated_discount(
            coupling_discount, donor_scope.locality,
        )
    else:
        donor_pattern = experienced_pattern(donor)
        effective_discount = coupling_discount

    blended = blend_patterns(self_pattern, donor_pattern, effective_discount)

    candidates = find_candidate_targets(landscape, current)
    if not candidates:
        return CrossReflexionResult(
            proposals=[],
            self_pattern=self_pattern,
            donor_pattern=donor_pattern,
            edges_added=0,
            frontier_node=current,
            donor_name=donor_name,
        )

    # Confidence: blend coverage, capped at 0.7 (cross is more uncertain)
    confidence = min(blended.coverage, 0.7)

    # Inflate R₀ by inverse confidence — cross hypotheses are cautious
    r0_scaled = blended.median_r0 / max(confidence, 0.1)

    proposals = []
    for target in candidates:
        rationale_parts = [
            f"Cross-reflexion from {donor_name}: ",
            f"self({self_pattern.sample_size} samples) + ",
            f"donor({donor_pattern.sample_size} samples), ",
            f"blended Δ={blended.median_delta:.2f}, ",
            f"R₀={blended.median_r0:.2f}, ",
            f"discount={effective_discount:.3f}",
        ]
        if scoped:
            rationale_parts.append(
                f" [scoped: ℓ_donor={donor_scope.locality:.2f}, "
                f"{donor_scope.scope_size} states]"
            )
        proposals.append(ProposedEdge(
            source=current,
            target=target,
            delta=blended.median_delta,
            resistance=round(r0_scaled, 4),
            confidence=round(confidence, 3),
            rationale="".join(rationale_parts),
        ))

    # Prioritize targets closer to goal
    proposals.sort(key=lambda p: _goal_proximity(landscape, p.target, goal))

    proposals = proposals[:max_proposals]
    added = apply_proposals(landscape, proposals)

    return CrossReflexionResult(
        proposals=proposals,
        self_pattern=self_pattern,
        donor_pattern=donor_pattern,
        edges_added=added,
        frontier_node=current,
        donor_name=donor_name,
    )


def apply_cross_proposals(
    landscape: Landscape,
    proposals: List[ProposedEdge],
) -> int:
    """Apply cross-proposed edges. Thin wrapper over apply_proposals."""
    return apply_proposals(landscape, proposals)


# ══════════════════════════════════════════════
# MultiverseController turn function
# ══════════════════════════════════════════════

def cross_reflexion_turn(
    active: Universe, passive: Universe, *, scoped: bool = False,
) -> None:
    """Turn function for MultiverseController: navigate + cross-propose.

    1. Run controller in active universe (up to 5 cycles)
    2. Check if active is at a frontier
    3. If stuck, use passive's experience to propose edges in active

    If scoped=True (C107), donor pattern extraction respects the
    donor's historization-derived locality.

    This is a TurnFn compatible with MultiverseController.run().
    """
    ctrl = E0Controller(
        active.landscape, active.execute_fn,
        alpha=2.0, recent_k=3,
    )
    trace = ctrl.run(active.start, max_cycles=5, goal=active.goal)

    # Determine current position after navigation
    if trace.steps:
        current = trace.steps[-1].target
    else:
        current = active.start

    # Cross-reflexion: if stuck at frontier, consult passive's experience
    if is_frontier(active.landscape, current, active.goal):
        cross_propose_edges(
            active.landscape,
            passive.landscape,
            current,
            active.goal,
            max_proposals=3,
            donor_name=passive.name,
            scoped=scoped,
        )


def scoped_cross_reflexion_turn(active: Universe, passive: Universe) -> None:
    """Convenience wrapper: cross_reflexion_turn with scoped=True (C107)."""
    cross_reflexion_turn(active, passive, scoped=True)


# ══════════════════════════════════════════════
# Standalone integrated run
# ══════════════════════════════════════════════

def run_with_cross_reflexion(
    universe_a: Universe,
    universe_b: Universe,
    max_cycles: int = 50,
    coupling_discount: float = 0.5,
    scoped: bool = False,
) -> CrossReflexionRunResult:
    """Run Universe A with cross-reflexive proposals from Universe B.

    Phase 1: Run B for max_cycles/2 to build donor experience.
    Phase 2: Run A, using B's experience at every frontier.

    If scoped=True (C107), donor experience is extracted from the
    donor's historization-derived locality, and coupling discount is
    modulated by donor locality.

    Returns aggregate result tracking all proposals.
    """
    all_results: List[CrossReflexionResult] = []
    proposed_from: Set[str] = set()

    # Phase 1: Let donor accumulate experience
    donor_ctrl = E0Controller(
        universe_b.landscape, universe_b.execute_fn,
        alpha=2.0, recent_k=3,
    )
    donor_ctrl.run(universe_b.start, max_cycles=max_cycles // 2,
                   goal=universe_b.goal)

    # Phase 2: Run target with cross-reflexion
    ctrl = E0Controller(
        universe_a.landscape, universe_a.execute_fn,
        alpha=2.0, recent_k=3,
    )

    from e0_controller.controller import RunTrace
    trace = RunTrace()
    current = universe_a.start

    for cycle in range(max_cycles):
        if current == universe_a.goal:
            break

        # Cross-reflexion at every new frontier
        if (current not in proposed_from
                and is_frontier(universe_a.landscape, current,
                                universe_a.goal)):
            result = cross_propose_edges(
                universe_a.landscape,
                universe_b.landscape,
                current,
                universe_a.goal,
                coupling_discount=coupling_discount,
                donor_name=universe_b.name,
                scoped=scoped,
            )
            if result.edges_added > 0:
                all_results.append(result)
                proposed_from.add(current)
                # Rebuild controller to see new edges
                ctrl = E0Controller(
                    universe_a.landscape, universe_a.execute_fn,
                    alpha=2.0, recent_k=3,
                )

        step = ctrl.cycle(current)
        if step is None:
            break
        trace.steps.append(step)
        current = step.target

    return CrossReflexionRunResult(
        trace=trace,
        reflexions=all_results,
        goal_reached=current == universe_a.goal,
    )


@dataclass
class CrossReflexionRunResult:
    """Result of a full run with cross-reflexion."""
    trace: object  # RunTrace
    reflexions: List[CrossReflexionResult] = field(default_factory=list)
    goal_reached: bool = False

    @property
    def total_proposals(self) -> int:
        return sum(len(r.proposals) for r in self.reflexions)

    @property
    def total_edges_added(self) -> int:
        return sum(r.edges_added for r in self.reflexions)

    @property
    def frontier_nodes(self) -> List[str]:
        return [r.frontier_node for r in self.reflexions]
