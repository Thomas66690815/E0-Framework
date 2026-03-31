"""
E₀ LLM Co-Cognition — Two LLMs coupled via Multiverse (C71)
============================================================

Capstone integration: two independent LLM-bootstrapped landscapes,
coupled through MultiverseController with NoveltyGate, exchanging
structural knowledge to escape Δ-Kollaps (premature consensus).

Architecture::

    LLM_A (temp=0.2) → build_landscape → Landscape_A → Universe_A ─┐
                                                                     │
                                                      MultiverseController
                                                      knowledge_exchange_turn
                                                      NoveltyGate evaluation
                                                                     │
    LLM_B (temp=0.6) → build_landscape → Landscape_B → Universe_B ─┘
                                                                     │
                                                      CoCognitionResult
                                                      (enrichment, novelty, traces)

Key design decisions:
- Uses knowledge_exchange_turn (C69: edge copying beats edge creation)
- Different temperatures produce genuinely different topologies
- Post-coupling navigation measures whether enrichment helps

Usage (live)::

    from e0_controller.llm_cocognition import run_cocognition
    result = run_cocognition(
        task="Analyze competitor announcement → produce briefing",
        start="RAW_ANNOUNCEMENT",
        goal="BRIEFING_DELIVERED",
    )
    print(result.summary())

Usage (deterministic)::

    result = run_cocognition_from_universes(universe_a, universe_b)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List

from e0_controller.primitives import Outcome
from e0_controller.controller import E0Controller, RunTrace
from e0_controller.multiverse import (
    Universe,
    MultiverseController,
    MultiverseResult,
)
from e0_controller.benchmark_multiverse import knowledge_exchange_turn
from e0_controller.coupling_router import structural_distance


# ══════════════════════════════════════════════
# Result Types
# ══════════════════════════════════════════════

@dataclass
class CoCognitionResult:
    """Result of a two-LLM co-cognition run."""

    # Bootstrap phase
    universe_a_name: str
    universe_b_name: str
    a_initial_states: int
    a_initial_edges: int
    b_initial_states: int
    b_initial_edges: int
    structural_distance_before: float

    # Multiverse coupling phase
    multiverse_result: MultiverseResult
    structural_distance_after: float

    # Post-coupling navigation
    trace_a: RunTrace
    trace_b: RunTrace
    a_reached_goal: bool
    b_reached_goal: bool

    # Final metrics
    a_final_states: int
    a_final_edges: int
    b_final_states: int
    b_final_edges: int

    @property
    def a_new_edges(self) -> int:
        """Edges A gained from coupling."""
        return self.a_final_edges - self.a_initial_edges

    @property
    def b_new_edges(self) -> int:
        """Edges B gained from coupling."""
        return self.b_final_edges - self.b_initial_edges

    @property
    def total_enrichment(self) -> int:
        """Total new edges across both universes."""
        return self.a_new_edges + self.b_new_edges

    @property
    def novelty_rate(self) -> float:
        """Fraction of multiverse turns that produced novelty."""
        return self.multiverse_result.novelty_rate

    @property
    def convergence_turn(self) -> Optional[int]:
        return self.multiverse_result.convergence_turn

    @property
    def divergence_count(self) -> int:
        return self.multiverse_result.divergence_count

    def summary(self) -> str:
        lines = [
            "═══ E₀ Co-Cognition Result ═══",
            "",
            f"Universe A ({self.universe_a_name}):"
            f" {self.a_initial_states}S/{self.a_initial_edges}E"
            f" → {self.a_final_states}S/{self.a_final_edges}E"
            f" (+{self.a_new_edges}E)",
            f"Universe B ({self.universe_b_name}):"
            f" {self.b_initial_states}S/{self.b_initial_edges}E"
            f" → {self.b_final_states}S/{self.b_final_edges}E"
            f" (+{self.b_new_edges}E)",
            f"Structural distance:"
            f" {self.structural_distance_before:.3f}"
            f" → {self.structural_distance_after:.3f}",
            "",
            f"Multiverse:"
            f" {self.multiverse_result.total_turns} turns,"
            f" novelty rate {self.novelty_rate:.0%}",
        ]
        if self.convergence_turn is not None:
            lines.append(f"Convergence: turn {self.convergence_turn}")
        else:
            lines.append("Convergence: not reached")
        lines += [
            f"Divergence pressure: {self.divergence_count}×",
            "",
            f"Goal reached: A={self.a_reached_goal}, B={self.b_reached_goal}",
            f"Steps: A={len(self.trace_a.steps)}, B={len(self.trace_b.steps)}",
            f"Total enrichment: {self.total_enrichment} edges",
        ]
        return "\n".join(lines)


# ══════════════════════════════════════════════
# Core: run from pre-built universes
# ══════════════════════════════════════════════

def run_cocognition_from_universes(
    universe_a: Universe,
    universe_b: Universe,
    *,
    max_turns: int = 10,
    max_steps_per_turn: int = 5,
    convergence_window: int = 3,
    max_nav_cycles: int = 20,
) -> CoCognitionResult:
    """Run co-cognition on pre-built universes.

    This is the core function — works with any universes (mock or LLM).

    Args:
        universe_a: First universe (any origin).
        universe_b: Second universe (any origin).
        max_turns: Maximum multiverse interaction turns.
        max_steps_per_turn: Controller cycles per turn.
        convergence_window: Turns without novelty to detect convergence.
        max_nav_cycles: Maximum cycles for post-coupling navigation.

    Returns:
        CoCognitionResult with bootstrap, coupling, and navigation data.
    """
    # Capture initial metrics
    a_init_states = len(universe_a.landscape.states)
    a_init_edges = universe_a.landscape.edge_count()
    b_init_states = len(universe_b.landscape.states)
    b_init_edges = universe_b.landscape.edge_count()
    dist_before = structural_distance(universe_a, universe_b)

    # Multiverse coupling with knowledge exchange
    mvc = MultiverseController(
        universe_a, universe_b,
        convergence_window=convergence_window,
        max_steps_per_turn=max_steps_per_turn,
    )
    mv_result = mvc.run(
        max_turns=max_turns,
        turn_fn=knowledge_exchange_turn,
    )

    dist_after = structural_distance(universe_a, universe_b)

    # Post-coupling navigation: each controller runs on enriched landscape
    ctrl_a = E0Controller(
        universe_a.landscape, universe_a.execute_fn,
        alpha=2.0, recent_k=3,
    )
    trace_a = ctrl_a.run(
        start=universe_a.start, goal=universe_a.goal,
        max_cycles=max_nav_cycles,
    )

    ctrl_b = E0Controller(
        universe_b.landscape, universe_b.execute_fn,
        alpha=2.0, recent_k=3,
    )
    trace_b = ctrl_b.run(
        start=universe_b.start, goal=universe_b.goal,
        max_cycles=max_nav_cycles,
    )

    a_goal = (trace_a.path[-1] == universe_a.goal) if trace_a.path else False
    b_goal = (trace_b.path[-1] == universe_b.goal) if trace_b.path else False

    return CoCognitionResult(
        universe_a_name=universe_a.name,
        universe_b_name=universe_b.name,
        a_initial_states=a_init_states,
        a_initial_edges=a_init_edges,
        b_initial_states=b_init_states,
        b_initial_edges=b_init_edges,
        structural_distance_before=dist_before,
        multiverse_result=mv_result,
        structural_distance_after=dist_after,
        trace_a=trace_a,
        trace_b=trace_b,
        a_reached_goal=a_goal,
        b_reached_goal=b_goal,
        a_final_states=len(universe_a.landscape.states),
        a_final_edges=universe_a.landscape.edge_count(),
        b_final_states=len(universe_b.landscape.states),
        b_final_edges=universe_b.landscape.edge_count(),
    )


# ══════════════════════════════════════════════
# LLM Bootstrap: Universe from LLM adapter
# ══════════════════════════════════════════════

def bootstrap_llm_universe(
    adapter: "E0LLMAdapter",
    task: str,
    name: str,
    start: str,
    goal: str,
    *,
    scenario_block: str = "",
    result_log: Optional[List] = None,
) -> "Universe":
    """Bootstrap a Universe from an LLM adapter.

    The adapter builds a landscape and provides an execute_fn that
    delegates transitions to the LLM.

    Args:
        adapter: Configured E0LLMAdapter instance.
        task: Task description for the LLM.
        name: Universe name (e.g., "LLM_A").
        start: Start state name.
        goal: Goal state name.
        scenario_block: Optional scenario context.
        result_log: Optional list to collect TransitionResults.

    Returns:
        Universe with LLM-backed execute_fn.
    """
    from e0_controller.llm_adapter import (
        materialize_landscape,
        task_map_from_proposal,
    )

    proposal = adapter.build_landscape(
        task, start, goal, scenario_block=scenario_block,
    )
    landscape = materialize_landscape(proposal)
    task_map = task_map_from_proposal(proposal)
    execute_fn = adapter.as_execute_fn(
        task_map,
        scenario_block=scenario_block,
        result_log=result_log,
    )
    return Universe(
        name=name,
        landscape=landscape,
        execute_fn=execute_fn,
        start=start,
        goal=goal,
    )


# ══════════════════════════════════════════════
# Full LLM Co-Cognition Pipeline
# ══════════════════════════════════════════════

def run_cocognition(
    task: str,
    start: str,
    goal: str,
    *,
    config_a: Optional["LLMConfig"] = None,
    config_b: Optional["LLMConfig"] = None,
    scenario_block: str = "",
    max_turns: int = 10,
    max_nav_cycles: int = 20,
) -> CoCognitionResult:
    """Run full LLM co-cognition: bootstrap → couple → navigate.

    Two LLMs independently bootstrap landscapes for the same task,
    then exchange structural knowledge via multiverse coupling.
    Post-coupling, each controller navigates its enriched landscape.

    Args:
        task: Task description for both LLMs.
        start: Start state name.
        goal: Goal state name.
        config_a: LLM config for universe A (default: temp=0.2).
        config_b: LLM config for universe B (default: temp=0.6).
        scenario_block: Optional scenario context.
        max_turns: Maximum multiverse interaction turns.
        max_nav_cycles: Max cycles for post-coupling navigation.

    Returns:
        CoCognitionResult with full pipeline data.
    """
    from e0_controller.llm_adapter import E0LLMAdapter, LLMConfig

    cfg_a = config_a or LLMConfig(temperature=0.2)
    cfg_b = config_b or LLMConfig(temperature=0.6)

    adapter_a = E0LLMAdapter(config=cfg_a)
    adapter_b = E0LLMAdapter(config=cfg_b)

    universe_a = bootstrap_llm_universe(
        adapter_a, task, "LLM_A", start, goal,
        scenario_block=scenario_block,
    )
    universe_b = bootstrap_llm_universe(
        adapter_b, task, "LLM_B", start, goal,
        scenario_block=scenario_block,
    )

    return run_cocognition_from_universes(
        universe_a, universe_b,
        max_turns=max_turns,
        max_nav_cycles=max_nav_cycles,
    )
