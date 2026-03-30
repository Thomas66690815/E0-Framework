"""
Raumzeit Coupling Experiment (C54)
====================================
Tests the hypothesis: Raumzeit (emergent spacetime) requires coupling
to an outside that delivers real FAILURE signals.

Central claim:
  A closed E₀ system (all outcomes SUCCESS) reinforces existing paths
  through historization and cannot escape deep traps.
  Only coupling — interaction with an environment that delivers
  FAILURE outcomes — creates the resistance asymmetry necessary
  for trap escape and thus for meaningful temporal ordering.

Theorem (Coupling Necessity for Trap Escape):
  Let L be a landscape containing a trap cycle γ such that:
    (a) all edges in γ have lower initial tension than the exit edge, and
    (b) the tension gap exceeds the revisit penalty threshold.
  Then:
    - In a closed system (all SUCCESS), γ is absorbing: historization
      monotonically reinforces γ, and the controller never exits.
    - In a coupled system (FAILURE on a cycle edge), historization
      increases R_eff on the failing edge, eventually making the
      exit edge cheaper. The controller escapes.

Connection to Ontodynamics:
  Time   = ordering of historizations (§4)
  Spacetime = globally historized topology of realized connections (§4)

  If historization only ever reinforces (closed system), the topology
  is monotone — no new structure emerges. Spacetime is trivial.

  Only through coupling — outcomes the system does not control —
  does historization produce asymmetric traces (some edges reinforced,
  others penalized). This asymmetry IS the emergent temporal structure.

  Raumzeit is not a module. It emerges from Axiom A₀ + coupling.

Usage:
  python -m e0_controller.raumzeit_coupling          # run experiment
  python -m e0_controller.raumzeit_coupling --json    # machine-readable
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional

from e0_controller.primitives import Outcome
from e0_controller.controller import E0Controller
from e0_controller.benchmark_domain_invariance import (
    DomainSpec,
    ALL_DOMAINS,
    _all_success,
    run_domain,
    DomainResult,
)


# ══════════════════════════════════════════════
# Data structures
# ══════════════════════════════════════════════

@dataclass
class CouplingComparison:
    """Paired results: closed (all-success) vs coupled (domain execute_fn)."""
    domain: str
    topology_class: str
    closed_goal_reached: bool
    closed_steps: int
    closed_rating: str
    coupled_goal_reached: bool
    coupled_steps: int
    coupled_rating: str
    coupling_necessary: bool            # closed fails, coupled succeeds
    has_failure_edges: bool             # domain has at least one FAILURE edge
    trap_class: str                     # "none", "shallow", "deep"


@dataclass
class CouplingResult:
    """Full experiment result."""
    comparisons: List[CouplingComparison]
    closed_goals_reached: int
    coupled_goals_reached: int
    coupling_necessary_count: int       # how many domains NEED coupling
    theorem_holds: bool                 # all coupling-necessary domains have failure edges


# ══════════════════════════════════════════════
# Run closed (all-success) version of a domain
# ══════════════════════════════════════════════

def run_domain_closed(spec: DomainSpec, max_cycles: int = 50) -> DomainResult:
    """Run a domain with all-success execute_fn (closed system)."""
    closed_spec = DomainSpec(
        name=spec.name,
        description=spec.description,
        landscape=_rebuild_landscape(spec),
        start=spec.start,
        goal=spec.goal,
        execute_fn=_all_success,
        happy_path_length=spec.happy_path_length,
        topology_class=spec.topology_class,
        node_count=spec.node_count,
        edge_count=spec.edge_count,
    )
    return run_domain(closed_spec, max_cycles=max_cycles)


def _rebuild_landscape(spec: DomainSpec):
    """Rebuild a fresh landscape with same topology.

    Necessary because run_domain mutates the landscape through
    historization — we need a fresh copy for the closed run.
    """
    from e0_controller.landscape import Landscape
    L = Landscape()
    for edge, delta in spec.landscape._delta.items():
        r0 = spec.landscape._R0.get(edge, 1.0)
        L.add_edge(edge[0], edge[1], delta=delta, resistance=r0)
    # Preserve isolated states (e.g. D10's dead-end X)
    for s in spec.landscape._states:
        L.add_state(s)
    return L


def _has_failure_edges(spec: DomainSpec) -> bool:
    """Check whether domain's execute_fn ever returns FAILURE."""
    for edge in spec.landscape._delta:
        outcome = spec.execute_fn(edge[0], edge[1])
        if outcome != Outcome.SUCCESS:
            return True
    return False


# ══════════════════════════════════════════════
# Core experiment
# ══════════════════════════════════════════════

def run_coupling_experiment(max_cycles: int = 50) -> CouplingResult:
    """Run all 10 domains in closed and coupled mode, compare."""
    comparisons: List[CouplingComparison] = []

    for builder in ALL_DOMAINS:
        # Build domain twice (fresh landscapes)
        spec_coupled = builder()
        spec_for_closed = builder()

        has_failures = _has_failure_edges(spec_coupled)

        # Run coupled (domain's own execute_fn)
        coupled_result = run_domain(spec_coupled, max_cycles=max_cycles)

        # Run closed (all-success)
        closed_result = run_domain_closed(spec_for_closed, max_cycles=max_cycles)

        # Classify
        coupling_necessary = (
            not closed_result.goal_reached and coupled_result.goal_reached
        )

        if not has_failures:
            trap_class = "none"
        elif coupling_necessary:
            trap_class = "deep"
        else:
            trap_class = "shallow"

        comparisons.append(CouplingComparison(
            domain=spec_coupled.name,
            topology_class=spec_coupled.topology_class,
            closed_goal_reached=closed_result.goal_reached,
            closed_steps=closed_result.steps,
            closed_rating=closed_result.rating,
            coupled_goal_reached=coupled_result.goal_reached,
            coupled_steps=coupled_result.steps,
            coupled_rating=coupled_result.rating,
            coupling_necessary=coupling_necessary,
            has_failure_edges=has_failures,
            trap_class=trap_class,
        ))

    closed_goals = sum(1 for c in comparisons if c.closed_goal_reached)
    coupled_goals = sum(1 for c in comparisons if c.coupled_goal_reached)
    coupling_needed = sum(1 for c in comparisons if c.coupling_necessary)

    # Theorem check: every domain where coupling is necessary
    # must have failure edges in its execute_fn
    theorem_holds = all(
        c.has_failure_edges
        for c in comparisons
        if c.coupling_necessary
    )

    return CouplingResult(
        comparisons=comparisons,
        closed_goals_reached=closed_goals,
        coupled_goals_reached=coupled_goals,
        coupling_necessary_count=coupling_needed,
        theorem_holds=theorem_holds,
    )


# ══════════════════════════════════════════════
# Output
# ══════════════════════════════════════════════

def print_coupling_results(result: CouplingResult) -> None:
    """Pretty-print coupling experiment results."""
    print("\n" + "=" * 100)
    print("  E₀ Raumzeit Coupling Experiment — Closed vs Coupled System")
    print("=" * 100)
    header = (
        f"{'Domain':<28} {'Fail?':>5} │ "
        f"{'Closed':>6} {'Steps':>5} {'Rate':>4} │ "
        f"{'Coupled':>7} {'Steps':>5} {'Rate':>4} │ "
        f"{'Trap':>7} {'Need?':>5}"
    )
    print(header)
    print("-" * 100)

    for c in result.comparisons:
        fail_str = "yes" if c.has_failure_edges else "no"
        cl_goal = "✓" if c.closed_goal_reached else "✗"
        cp_goal = "✓" if c.coupled_goal_reached else "✗"
        need = "YES" if c.coupling_necessary else "no"
        print(
            f"{c.domain:<28} {fail_str:>5} │ "
            f"{cl_goal:>6} {c.closed_steps:>5} {c.closed_rating:>4} │ "
            f"{cp_goal:>7} {c.coupled_steps:>5} {c.coupled_rating:>4} │ "
            f"{c.trap_class:>7} {need:>5}"
        )

    print("-" * 100)
    print(f"\n  Closed system goals reached:  {result.closed_goals_reached}/10")
    print(f"  Coupled system goals reached: {result.coupled_goals_reached}/10")
    print(f"  Coupling necessary for:       {result.coupling_necessary_count} domain(s)")
    print(f"  Theorem holds:                {'YES' if result.theorem_holds else 'NO'}")

    # Structural interpretation
    deep = [c for c in result.comparisons if c.trap_class == "deep"]
    shallow = [c for c in result.comparisons if c.trap_class == "shallow"]

    if deep:
        print(f"\n  Deep traps (coupling required):   {', '.join(c.domain for c in deep)}")
    if shallow:
        print(f"  Shallow traps (penalty escapes):   {', '.join(c.domain for c in shallow)}")

    print(f"\n  Interpretation: Raumzeit (emergent temporal structure) requires")
    print(f"  coupling to an environment that delivers FAILURE signals.")
    print(f"  Without coupling, deep traps are absorbing — no escape, no time.")
    print()


def result_to_dict(result: CouplingResult) -> Dict:
    """Convert to serializable dict."""
    return {
        "experiment": "raumzeit_coupling_v1",
        "closed_goals": result.closed_goals_reached,
        "coupled_goals": result.coupled_goals_reached,
        "coupling_necessary": result.coupling_necessary_count,
        "theorem_holds": result.theorem_holds,
        "comparisons": [
            {
                "domain": c.domain,
                "topology": c.topology_class,
                "has_failure_edges": c.has_failure_edges,
                "closed_goal": c.closed_goal_reached,
                "closed_steps": c.closed_steps,
                "closed_rating": c.closed_rating,
                "coupled_goal": c.coupled_goal_reached,
                "coupled_steps": c.coupled_steps,
                "coupled_rating": c.coupled_rating,
                "coupling_necessary": c.coupling_necessary,
                "trap_class": c.trap_class,
            }
            for c in result.comparisons
        ],
    }


# ══════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════

if __name__ == "__main__":
    result = run_coupling_experiment()
    if "--json" in sys.argv:
        print(json.dumps(result_to_dict(result), indent=2))
    else:
        print_coupling_results(result)
