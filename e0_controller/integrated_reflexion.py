"""
Integrated Reflexion (C59)
=============================
Unifies C49 (reflexive flag action) and C57 (reflexive edge proposal)
into a single reflexive response pipeline.

Insight: "Reflexion ist kein Spezialfall — sie ist der Normalfall
für alles Neue."  Both flag toggling and topology construction are
reflexive responses to diagnosis.  C59 makes them available as one
coherent mechanism.

Pipeline:
  1. Dual reflection diagnosis (C47) → SelfGraphDiagnosis
  2. Flag reflexion (C49): toggle harmful modulations
  3. Topology reflexion (C57): propose edges at frontier nodes
  4. Unified result with both kinds of actions
  5. Journal records everything

Usage:
  # As standalone function:
  result = integrated_reflexion(landscape, current, goal, report=report)

  # As full runner with SelfGraph awareness:
  trace, result, journal = run_with_integrated_reflexion(
      landscape, execute_fn, "S", "GOAL",
  )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Set, Tuple

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller, RunTrace
from e0_controller.reflexive_action import (
    ReflexiveAction,
    ReflexiveActionResult,
    ReflexiveJournal,
    apply_reflexive_actions,
    plan_reflexive_actions,
)
from e0_controller.reflexive_edge_proposal import (
    ProposedEdge,
    apply_proposals,
    is_frontier,
    propose_edges,
)
from e0_controller.dual_reflection import (
    DualReflectionReport,
    SelfGraphDiagnosis,
    diagnose_self_graph,
)
from e0_controller.self_graph import SelfGraph


# ══════════════════════════════════════════════
# Unified result
# ══════════════════════════════════════════════

@dataclass
class IntegratedReflexionResult:
    """Unified outcome of both flag reflexion (C49) and topology reflexion (C57).

    Combines modulation flag toggles with edge proposals into a single
    result with joint undo capability.
    """
    flag_result: Optional[ReflexiveActionResult] = None
    edge_proposals: List[ProposedEdge] = field(default_factory=list)
    edges_added: int = 0
    diagnosis_used: Optional[SelfGraphDiagnosis] = None

    @property
    def any_changes(self) -> bool:
        flag_changed = self.flag_result is not None and self.flag_result.any_changes
        return flag_changed or self.edges_added > 0

    @property
    def flags_changed(self) -> bool:
        return self.flag_result is not None and self.flag_result.any_changes

    @property
    def topology_changed(self) -> bool:
        return self.edges_added > 0

    def restore(self, landscape: Landscape) -> int:
        """Undo all reflexive changes — flags and edges.

        Returns total number of items restored.
        """
        count = 0
        # Restore flags (reverse order)
        if self.flag_result is not None:
            count += self.flag_result.restore(landscape)
        # Remove proposed edges
        for p in self.edge_proposals:
            if landscape.has_edge(p.source, p.target):
                landscape.remove_edge(p.source, p.target)
                count += 1
        return count

    def summary(self) -> str:
        """Human-readable summary."""
        lines = []
        if self.flag_result is not None:
            flag_sum = self.flag_result.summary()
            if flag_sum != "No reflexive actions needed.":
                lines.append("Flag reflexion (C49):")
                lines.append(flag_sum)
        if self.edge_proposals:
            lines.append(f"Topology reflexion (C57): {self.edges_added} edges proposed")
            for p in self.edge_proposals:
                lines.append(f"  {p.source} → {p.target} (confidence={p.confidence:.2f})")
        if not lines:
            return "No reflexive changes."
        return "\n".join(lines)


# ══════════════════════════════════════════════
# Core function
# ══════════════════════════════════════════════

def integrated_reflexion(
    landscape: Landscape,
    current: str,
    goal: str,
    *,
    report: Optional[DualReflectionReport] = None,
    enable_flags: bool = True,
    enable_topology: bool = True,
    proactive: bool = True,
    max_proposals: int = 5,
) -> IntegratedReflexionResult:
    """Unified reflexion: diagnosis → flags + topology.

    Combines C49 flag reflexion and C57 edge proposal into one call.

    Parameters:
        landscape: Current navigation landscape
        current: Current position
        goal: Target state
        report: Optional DualReflectionReport for flag reflexion (C49)
        enable_flags: Whether to apply flag reflexion
        enable_topology: Whether to propose new edges
        proactive: If True, use median R₀ for proposals (C57 Stufe 2)
        max_proposals: Maximum edge proposals
    """
    result = IntegratedReflexionResult()

    # C49: Flag reflexion (requires diagnosis)
    if enable_flags and report is not None:
        result.flag_result = apply_reflexive_actions(report, landscape)
        result.diagnosis_used = report.self_diagnosis

    # C57: Topology reflexion (requires frontier)
    if enable_topology and is_frontier(landscape, current, goal):
        proposals = propose_edges(
            landscape, current, goal, max_proposals,
            proactive=proactive,
        )
        result.edge_proposals = proposals
        result.edges_added = apply_proposals(landscape, proposals)

    return result


# ══════════════════════════════════════════════
# Extended journal
# ══════════════════════════════════════════════

def record_integrated(
    journal: ReflexiveJournal,
    result: IntegratedReflexionResult,
    iteration: int,
) -> int:
    """Record an IntegratedReflexionResult in the journal.

    Records flag changes via the journal's existing mechanism.
    Returns total entries recorded.
    """
    count = 0
    if result.flag_result is not None and result.flag_result.any_changes:
        count += journal.record(result.flag_result, iteration)
    return count


# ══════════════════════════════════════════════
# Integrated runner
# ══════════════════════════════════════════════

ExecuteFn = Callable[[str, str], Outcome]


def run_with_integrated_reflexion(
    landscape: Landscape,
    execute_fn: ExecuteFn,
    start: str,
    goal: str,
    max_cycles: int = 50,
    max_proposals: int = 5,
    diagnosis_interval: int = 10,
) -> Tuple[RunTrace, IntegratedReflexionResult, ReflexiveJournal]:
    """Run with full integrated reflexion: C49 flags + C57 topology.

    NEW capability beyond C56/C57 standalone:
    - SelfGraph awareness during navigation (self-historization via controller)
    - Diagnosis-driven flag toggling at intervals (C49)
    - Proactive edge proposals at every frontier (C57)
    - Unified result and journal

    Parameters:
        landscape: Navigation landscape
        execute_fn: Transition execution function
        start: Start state
        goal: Goal state
        max_cycles: Maximum navigation cycles
        max_proposals: Max edge proposals per frontier
        diagnosis_interval: Cycles between SelfGraph diagnoses

    Returns:
        (trace, integrated_result, journal)
    """
    sg = SelfGraph()
    journal = ReflexiveJournal()

    ctrl = E0Controller(landscape, execute_fn, alpha=2.0, recent_k=3)
    ctrl.self_graph = sg

    trace = RunTrace()
    current = start
    proposed_from: Set[str] = set()
    all_proposals: List[ProposedEdge] = []
    all_flag_actions: List[ReflexiveAction] = []

    for cycle in range(max_cycles):
        if current == goal:
            break

        # ── C57: Proactive topology reflexion at frontiers ──
        if current not in proposed_from and is_frontier(landscape, current, goal):
            proposals = propose_edges(
                landscape, current, goal, max_proposals,
                proactive=True,
            )
            proposed_from.add(current)
            if proposals:
                apply_proposals(landscape, proposals)
                all_proposals.extend(proposals)
                ctrl = E0Controller(
                    landscape, execute_fn, alpha=2.0, recent_k=3,
                )
                ctrl.self_graph = sg

        # ── C49: Periodic diagnosis-driven flag reflexion ──
        if cycle > 0 and cycle % diagnosis_interval == 0:
            diag = diagnose_self_graph(sg)
            if diag.deactivation_candidates:
                planned = plan_reflexive_actions(diag, landscape)
                flag_result = ReflexiveActionResult()
                for action in planned:
                    setattr(landscape, action.flag_name, action.new_value)
                    flag_result.actions_taken.append(action)
                    all_flag_actions.append(action)
                if flag_result.any_changes:
                    journal.record(flag_result, cycle)
                    ctrl = E0Controller(
                        landscape, execute_fn, alpha=2.0, recent_k=3,
                    )
                    ctrl.self_graph = sg

        step = ctrl.cycle(current)
        if step is None:
            break
        trace.steps.append(step)
        current = step.target

    # Build unified result
    final_flag_result = None
    if all_flag_actions:
        final_flag_result = ReflexiveActionResult(
            actions_taken=all_flag_actions,
        )

    result = IntegratedReflexionResult(
        flag_result=final_flag_result,
        edge_proposals=all_proposals,
        edges_added=len(all_proposals),
    )

    return trace, result, journal
