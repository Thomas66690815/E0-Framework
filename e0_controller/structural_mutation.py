"""
Bridge 4 — Structural Mutation Infrastructure (Stufe 2 + Stufe 4a)
===================================================================

Provides the data layer and mechanics for *structural* self-modification:
adding/removing edges, adjusting Δ/R₀ at the topology level.

This sits between:
- Stufe 1 (landscape.py mutation API — mechanical primitives)
- Stufe 3 (tuning integration — when to trigger, Session.iterate() hook)
- Stufe 4a (identity invariant — what must survive self-modification)

Core components:
  StructuralMutation        — typed intent ("adjust_resistance on S→A to 1.5")
  MutationRecord            — auditable outcome (applied, quality Δ, reverted?)
  MutationHistory           — bounded cross-run log with oscillation protection
  IdentityInvariantResult   — B4-S4a: result of post-mutation identity check
  propose_structural_mutations()  — StructuralDiagnostic → mutations
  apply_structural_mutation()     — execute on Landscape
  revert_structural_mutation()    — undo via stored old value
  is_admissible()                 — E₀ admissibility gate
  check_identity_invariant()      — B4-S4a: three-part post-mutation check

Canon basis:
  AGI Blueprint §5 — "self-modification becomes one admissible transition
  among others, and historization constrains future self-changes."

  E₀ Canonical Reference §2.7 / §4 — "Non-transition is structurally
  unstable" (A₀).  After any self-modification, A₀ must remain enforceable
  for the reachable sub-graph — otherwise the system has modified itself
  into a structurally dead configuration.

  Structural Deep Review v1 §6.1 — Identity Invariant analysis:
  three necessary conditions that must hold after every structural mutation.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

from .primitives import Edge

if TYPE_CHECKING:
    from .landscape import Landscape


# ──────────────────────────────────────────────
# 1. Mutation Types
# ──────────────────────────────────────────────

class MutationType(Enum):
    """Kind of structural change."""
    REMOVE_EDGE = "remove_edge"
    ADD_EDGE = "add_edge"
    ADJUST_RESISTANCE = "adjust_resistance"
    ADJUST_DELTA = "adjust_delta"


@dataclass
class StructuralMutation:
    """A proposed structural change to the Landscape.

    Analogous to TuningProposal for parametric changes.
    Carries the full intent so apply/revert can be mechanical.
    """
    mutation_type: MutationType
    source: str
    target: str
    old_value: Optional[float] = None   # for undo (R₀, Δ, or None for add)
    new_value: Optional[float] = None   # proposed value (or None for remove)
    motivation: str = ""                # link to diagnostic finding
    # For add_edge: delta and resistance are both needed
    add_delta: Optional[float] = None
    add_resistance: Optional[float] = None

    @property
    def edge(self) -> Edge:
        return Edge(self.source, self.target)

    def describe(self) -> str:
        """Human-readable one-liner."""
        if self.mutation_type == MutationType.REMOVE_EDGE:
            return f"remove {self.source}→{self.target}"
        if self.mutation_type == MutationType.ADD_EDGE:
            return (f"add {self.source}→{self.target} "
                    f"(Δ={self.add_delta}, R₀={self.add_resistance})")
        label = "R₀" if self.mutation_type == MutationType.ADJUST_RESISTANCE else "Δ"
        return (f"adjust {label} on {self.source}→{self.target}: "
                f"{self.old_value} → {self.new_value}")


# ──────────────────────────────────────────────
# 2. Mutation Record (audit trail)
# ──────────────────────────────────────────────

@dataclass
class MutationRecord:
    """Outcome of an applied structural mutation.

    Analogous to TuningSnapshot — records what happened,
    whether it was accepted, and what the quality delta was.
    """
    mutation: StructuralMutation
    quality_before: float = 0.0
    quality_after: Optional[float] = None
    accepted: bool = False
    reverted: bool = False

    @property
    def delta_quality(self) -> Optional[float]:
        if self.quality_after is None:
            return None
        return self.quality_after - self.quality_before


# ──────────────────────────────────────────────
# 3. Identity Invariant (Bridge 4, Stufe 4a)
# ──────────────────────────────────────────────

@dataclass(frozen=True)
class IdentityInvariantResult:
    """Result of the E₀ identity invariant check after structural mutation.

    Canon basis: Structural Deep Review v1 §6.1 — three conditions that
    must hold after any structural self-modification for the system to
    remain "the same" system:

    1. **goal_reachable** — If a goal is set, it must remain reachable
       from the start state.  A mutation that severs the goal-path
       destroys the purpose of the state space.

    2. **a0_compliant** — Every state reachable from *start* must have
       at least one admissible outgoing transition.  This ensures that
       Axiom A₀ ("non-transition is structurally unstable") remains
       enforceable throughout the reachable subgraph.  A mutation that
       leaves a reachable state with no exits turns A₀ into a lie for
       that state.

    3. **historization_continuous** — Mutations touch only _delta and
       _R0, never historization traces (δ_H, U/F-traces, τ).  This is
       enforced by architecture (all mutation primitives are restricted
       to the static structural dicts), so this invariant is always True
       and recorded here as a *design guarantee* rather than a runtime
       check.

    Attributes
    ----------
    satisfied : bool
        True if all three invariants hold; False otherwise.
    violated_check : Optional[str]
        Name of the first failing check ("goal_reachable", "a0_compliant"),
        or None when satisfied.
    goal_reachable : bool
        Invariant 1 result.
    a0_compliant : bool
        Invariant 2 result.
    historization_continuous : bool
        Invariant 3 result (always True — architectural guarantee).
    unreachable_dead_ends : List[str]
        States reachable from *start* that have no admissible outgoing
        transition (the witness set for a0_compliant = False).
    """
    satisfied: bool
    violated_check: Optional[str]
    goal_reachable: bool
    a0_compliant: bool
    historization_continuous: bool
    unreachable_dead_ends: List[str]


def check_identity_invariant(
    landscape: "Landscape",
    start: str,
    goal: Optional[str] = None,
) -> IdentityInvariantResult:
    """Check the three E₀ identity invariants after structural mutation.

    Should be called immediately after applying mutations and before
    accepting them.  If the result is not satisfied, the caller must
    revert all mutations and reject the cycle.

    Parameters
    ----------
    landscape : Landscape
        The (mutated) landscape to check.
    start : str
        Current start state (used for reachability analysis).
    goal : str, optional
        Target state for Invariant 1.  If None, Invariant 1 is skipped
        (vacuously True).

    Returns
    -------
    IdentityInvariantResult
        Full result including per-invariant flags and witness information.
    """
    from collections import deque

    # ── BFS: collect all states reachable from start ──
    reachable: Set[str] = set()
    queue: deque = deque([start])
    while queue:
        node = queue.popleft()
        if node in reachable:
            continue
        reachable.add(node)
        for neighbor in landscape.admissible_neighbors(node):
            if neighbor not in reachable:
                queue.append(neighbor)

    # ── Invariant 1: goal reachable ──
    inv1: bool
    if goal is None:
        inv1 = True
    else:
        inv1 = goal in reachable

    # ── Invariant 2: A₀ compliance (no reachable dead-ends) ──
    dead_ends: List[str] = [
        s for s in reachable
        if not landscape.admissible_neighbors(s)
    ]
    # The goal state itself may legitimately have no outgoing transitions;
    # that is the terminal condition, not a violation.
    if goal is not None:
        dead_ends = [s for s in dead_ends if s != goal]
    inv2 = len(dead_ends) == 0

    # ── Invariant 3: historization continuity (architectural guarantee) ──
    inv3 = True  # always: mutations never touch Historization object

    satisfied = inv1 and inv2 and inv3
    violated: Optional[str] = None
    if not inv1:
        violated = "goal_reachable"
    elif not inv2:
        violated = "a0_compliant"

    return IdentityInvariantResult(
        satisfied=satisfied,
        violated_check=violated,
        goal_reachable=inv1,
        a0_compliant=inv2,
        historization_continuous=inv3,
        unreachable_dead_ends=dead_ends,
    )


# ──────────────────────────────────────────────
# 4. Admissibility (renumbered from 3)
# ──────────────────────────────────────────────

_MAX_MUTATIONS_PER_CYCLE = 3


def is_admissible(mutation: StructuralMutation, landscape) -> bool:
    """E₀ admissibility gate for a structural mutation.

    Constraints (from concept note §2):
    1. Locality   — mutation targets exactly one edge.         (structural)
    2. No orphans — remove_edge must not isolate a state.      (topology-safety)
    3. Non-negative — new Δ, R₀ ≥ 0.                          (value-safety)
    4. Edge exists — adjust/remove require existing edge.      (precondition)
    5. Edge absent — add requires non-existing edge.           (no overwrite)

    Returns True if the mutation passes all checks.
    """
    mt = mutation.mutation_type

    if mt == MutationType.REMOVE_EDGE:
        if not landscape.has_edge(mutation.source, mutation.target):
            return False
        orphans = landscape.would_orphan(mutation.source, mutation.target)
        if orphans:
            return False
        return True

    if mt == MutationType.ADD_EDGE:
        if landscape.has_edge(mutation.source, mutation.target):
            return False
        if mutation.add_delta is None or mutation.add_delta < 0:
            return False
        if mutation.add_resistance is None or mutation.add_resistance < 0:
            return False
        return True

    if mt == MutationType.ADJUST_RESISTANCE:
        if not landscape.has_edge(mutation.source, mutation.target):
            return False
        if mutation.new_value is None or mutation.new_value < 0:
            return False
        return True

    if mt == MutationType.ADJUST_DELTA:
        if not landscape.has_edge(mutation.source, mutation.target):
            return False
        if mutation.new_value is None or mutation.new_value < 0:
            return False
        return True

    return False  # unknown type


# ──────────────────────────────────────────────
# 5. Apply / Revert (renumbered from 4)
# ──────────────────────────────────────────────

def apply_structural_mutation(
    mutation: StructuralMutation,
    landscape,
) -> StructuralMutation:
    """Apply a mutation to a Landscape, filling in old_value for undo.

    Returns the mutation with old_value populated (for revert).
    Raises if the mutation is not admissible.
    """
    if not is_admissible(mutation, landscape):
        raise ValueError(
            f"Mutation not admissible: {mutation.describe()}"
        )

    mt = mutation.mutation_type

    if mt == MutationType.REMOVE_EDGE:
        # Store old values for potential re-add
        edge = mutation.edge
        mutation.old_value = landscape.base_resistance(
            mutation.source, mutation.target)
        mutation.add_delta = landscape.difference(
            mutation.source, mutation.target)
        mutation.add_resistance = mutation.old_value
        landscape.remove_edge(mutation.source, mutation.target)

    elif mt == MutationType.ADD_EDGE:
        landscape.add_edge(
            mutation.source, mutation.target,
            delta=mutation.add_delta,
            resistance=mutation.add_resistance,
        )

    elif mt == MutationType.ADJUST_RESISTANCE:
        mutation.old_value = landscape.adjust_base_resistance(
            mutation.source, mutation.target, mutation.new_value)

    elif mt == MutationType.ADJUST_DELTA:
        mutation.old_value = landscape.adjust_delta(
            mutation.source, mutation.target, mutation.new_value)

    return mutation


def revert_structural_mutation(
    mutation: StructuralMutation,
    landscape,
) -> None:
    """Undo a previously applied mutation using stored old_value."""
    mt = mutation.mutation_type

    if mt == MutationType.REMOVE_EDGE:
        # Re-add the edge with its original values
        landscape.add_edge(
            mutation.source, mutation.target,
            delta=mutation.add_delta,
            resistance=mutation.add_resistance,
        )

    elif mt == MutationType.ADD_EDGE:
        landscape.remove_edge(mutation.source, mutation.target)

    elif mt == MutationType.ADJUST_RESISTANCE:
        landscape.adjust_base_resistance(
            mutation.source, mutation.target, mutation.old_value)

    elif mt == MutationType.ADJUST_DELTA:
        landscape.adjust_delta(
            mutation.source, mutation.target, mutation.old_value)


# ──────────────────────────────────────────────
# 6. Proposal Logic (renumbered from 5)
# ──────────────────────────────────────────────

# Resistance adjustment factor: multiply R₀ by this on chronic failure
_RESISTANCE_INCREASE_FACTOR = 1.5
_RESISTANCE_DECREASE_FACTOR = 0.7
_DEAD_STATE_DELTA_BOOST = 1.5


def propose_structural_mutations(
    diagnostic,
    landscape,
    mutation_history: Optional["MutationHistory"] = None,
) -> List[StructuralMutation]:
    """Generate structural mutation proposals from a StructuralDiagnostic.

    Translates diagnostic findings into concrete, admissible mutations:
    - dead_states     → increase Δ on edges *toward* the dead state
    - loop_states     → increase R₀ on the loop-back edge
    - plateau_evidence → increase Δ on lowest-field edges (shake up)
    - parameter_bounds_hit → no structural action (informational only)

    Proposals are filtered for admissibility and oscillation.
    """
    proposals: List[StructuralMutation] = []

    # Dead states: boost Δ on edges leading to dead state
    for dead in diagnostic.dead_states:
        for edge in landscape.edges:
            if edge.target == dead:
                old_delta = landscape.difference(edge.source, edge.target)
                new_delta = max(old_delta * _DEAD_STATE_DELTA_BOOST,
                                old_delta + 0.5)
                m = StructuralMutation(
                    mutation_type=MutationType.ADJUST_DELTA,
                    source=edge.source,
                    target=edge.target,
                    old_value=old_delta,
                    new_value=new_delta,
                    motivation=f"dead state '{dead}': boost Δ to attract visits",
                )
                if is_admissible(m, landscape):
                    proposals.append(m)

    # Loop states: increase R₀ on loop-back edges to break cycles
    loop_set = set(diagnostic.loop_states)
    seen_loops: Set[tuple] = set()
    for edge in landscape.edges:
        if edge.source in loop_set and edge.target in loop_set:
            # Check it's actually a 2-cycle back-edge
            if landscape.has_edge(edge.target, edge.source):
                pair = tuple(sorted([edge.source, edge.target]))
                if pair in seen_loops:
                    continue
                seen_loops.add(pair)

                old_r = landscape.base_resistance(edge.source, edge.target)
                new_r = old_r * _RESISTANCE_INCREASE_FACTOR
                m = StructuralMutation(
                    mutation_type=MutationType.ADJUST_RESISTANCE,
                    source=edge.source,
                    target=edge.target,
                    old_value=old_r,
                    new_value=new_r,
                    motivation=(f"loop states '{edge.source}'↔'{edge.target}': "
                                f"raise R₀ to discourage cycling"),
                )
                if is_admissible(m, landscape):
                    proposals.append(m)

    # Filter oscillations via history
    if mutation_history is not None:
        proposals = [
            p for p in proposals
            if not mutation_history.would_oscillate(p)
        ]

    # Bound to max per cycle
    return proposals[:_MAX_MUTATIONS_PER_CYCLE]


# ──────────────────────────────────────────────
# 7. Mutation History (renumbered from 6)
# ──────────────────────────────────────────────

@dataclass
class MutationHistory:
    """Bounded cross-run log of structural mutations.

    Analogous to TuningMemory — records what was tried, whether it
    helped, and blocks oscillation (e.g. raise R₀ then lower R₀
    on same edge in alternating cycles).
    """
    records: List[MutationRecord] = field(default_factory=list)
    max_records: int = 100

    def record(self, rec: MutationRecord) -> None:
        """Append a record, dropping oldest if at capacity."""
        self.records.append(rec)
        if len(self.records) > self.max_records:
            self.records = self.records[-self.max_records:]

    def would_oscillate(self, proposal: StructuralMutation) -> bool:
        """H_meta for structural mutations: block ping-pong on same edge.

        If the last two mutations on this edge went in opposite
        directions (increase then decrease or vice versa), freeze.
        Also blocks add/remove ping-pong on the same edge.
        """
        edge_key = (proposal.source, proposal.target)

        # Cross-type oscillation: add ↔ remove on same edge
        if proposal.mutation_type == MutationType.REMOVE_EDGE:
            add_count = sum(
                1 for r in self.records[-6:]
                if (r.mutation.source, r.mutation.target) == edge_key
                and r.mutation.mutation_type == MutationType.ADD_EDGE
                and r.accepted
            )
            if add_count > 0:
                return True

        if proposal.mutation_type == MutationType.ADD_EDGE:
            rem_count = sum(
                1 for r in self.records[-6:]
                if (r.mutation.source, r.mutation.target) == edge_key
                and r.mutation.mutation_type == MutationType.REMOVE_EDGE
                and r.accepted
            )
            if rem_count > 0:
                return True

        # Same-type oscillation: alternating direction on same edge
        recent = [
            r for r in self.records
            if (r.mutation.source, r.mutation.target) == edge_key
            and r.mutation.mutation_type == proposal.mutation_type
            and r.accepted
        ]
        if len(recent) < 2:
            return False

        last = recent[-1].mutation
        prev = recent[-2].mutation

        if proposal.mutation_type in (MutationType.ADJUST_RESISTANCE,
                                       MutationType.ADJUST_DELTA):
            if (last.old_value is not None and last.new_value is not None
                    and prev.old_value is not None and prev.new_value is not None):
                d1 = last.new_value - last.old_value
                d2 = prev.new_value - prev.old_value
                if abs(d1) > 1e-10 and abs(d2) > 1e-10:
                    return (d1 > 0) != (d2 > 0)

        return False

    def accepted_count(self) -> int:
        """Number of accepted mutations in history."""
        return sum(1 for r in self.records if r.accepted)

    def reverted_count(self) -> int:
        """Number of reverted mutations in history."""
        return sum(1 for r in self.records if r.reverted)

    def edge_mutation_count(self, source: str, target: str) -> int:
        """Total mutations on a specific edge."""
        return sum(
            1 for r in self.records
            if r.mutation.source == source and r.mutation.target == target
        )

    # ── Serialization ──

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "max_records": self.max_records,
            "records": [
                {
                    "mutation": {
                        "mutation_type": r.mutation.mutation_type.value,
                        "source": r.mutation.source,
                        "target": r.mutation.target,
                        "old_value": r.mutation.old_value,
                        "new_value": r.mutation.new_value,
                        "motivation": r.mutation.motivation,
                        "add_delta": r.mutation.add_delta,
                        "add_resistance": r.mutation.add_resistance,
                    },
                    "quality_before": r.quality_before,
                    "quality_after": r.quality_after,
                    "accepted": r.accepted,
                    "reverted": r.reverted,
                }
                for r in self.records
            ],
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MutationHistory":
        """Reconstruct from serialized dict."""
        h = cls(max_records=d.get("max_records", 100))
        for rd in d.get("records", []):
            md = rd["mutation"]
            mut = StructuralMutation(
                mutation_type=MutationType(md["mutation_type"]),
                source=md["source"],
                target=md["target"],
                old_value=md.get("old_value"),
                new_value=md.get("new_value"),
                motivation=md.get("motivation", ""),
                add_delta=md.get("add_delta"),
                add_resistance=md.get("add_resistance"),
            )
            rec = MutationRecord(
                mutation=mut,
                quality_before=rd.get("quality_before", 0.0),
                quality_after=rd.get("quality_after"),
                accepted=rd.get("accepted", False),
                reverted=rd.get("reverted", False),
            )
            h.records.append(rec)
        return h


# ──────────────────────────────────────────────
# 8. Structural Tuning Cycle (renumbered from 7)
# ──────────────────────────────────────────────

@dataclass
class StructuralTuningCycleResult:
    """Complete output of one structural tuning feedback cycle.

    Analogous to TuningCycleResult in self_tuning.py but for
    topology-level changes instead of parameter adjustments.
    """
    # Before
    quality_before: float

    # Diagnostic + proposals
    diagnostic: Any  # StructuralDiagnostic from reflection.py
    proposals: List[StructuralMutation]
    applied_mutations: List[StructuralMutation]

    # After (None if no proposals)
    quality_after: Optional[float] = None
    delta_quality: Optional[float] = None

    # Outcome
    accepted: bool = False
    reverted: bool = False
    mutation_records: List[MutationRecord] = field(default_factory=list)

    # B4-S4a: Identity Invariant result (None if mutations never applied)
    identity_invariant: Optional[IdentityInvariantResult] = None


def structural_tuning_cycle(
    controller,
    start: str,
    goal: Optional[str] = None,
    max_cycles: int = 50,
    mutation_history: Optional[MutationHistory] = None,
    tuning_memory: Optional[Any] = None,
) -> StructuralTuningCycleResult:
    """Execute one complete structural tuning feedback cycle.

    Analogous to tuning_cycle() in self_tuning.py but operates on
    landscape *topology* instead of controller parameters.

    The cycle:
    1. Run controller from *start* (baseline).
    2. Build StructuralDiagnostic from run + tuning_memory.
    3. Propose structural mutations from diagnostic.
    4. If proposals exist: apply mutations.
    4b. Check Identity Invariant (B4-S4a): goal reachable + A₀ compliant.
        If violated: revert all mutations and return without re-running.
    5. Reset + re-run controller.
    6. Compute Q_after and Δ = Q_after − Q_before.
    7. If Δ < 0 (regression): revert all mutations.
    8. Record outcome in mutation_history.

    Returns StructuralTuningCycleResult with full audit trail.
    """
    from .self_tuning import (
        quality_score,
        field_summary_from_run,
        _reset_landscape,
    )
    from .reflection import build_structural_diagnostic
    from .evaluation import evaluate_run, ScenarioEvaluation

    if mutation_history is None:
        mutation_history = MutationHistory()

    landscape = controller.landscape

    # ── Phase 1: Baseline run ──
    _reset_landscape(landscape)
    controller._recent = []
    controller._escalation_edges = {}

    trace_before = controller.run(start, max_cycles=max_cycles, goal=goal)
    fs_before = field_summary_from_run(landscape, trace_before)
    goal_reached = (
        trace_before.path[-1] == goal if (goal and trace_before.path) else False
    )
    q_before = quality_score(fs_before, goal_reached)

    # ── Phase 2: Build diagnostic ──
    # Construct a minimal ScenarioEvaluation for the diagnostic builder
    metrics = trace_before.metrics()
    happy_len = int(metrics["steps"])
    eval_result = evaluate_run(
        path=trace_before.path,
        steps=int(metrics["steps"]),
        escalation_count=int(metrics.get("escalation_count", 0)),
        revisit_count=int(metrics["revisit_count"]),
        success_rate=metrics["success_rate"],
        avg_tension=metrics["avg_tension"],
        total_tension=trace_before.total_tension,
        reached_goal=goal_reached,
        happy_path_length=happy_len,
    )
    scenario_eval = ScenarioEvaluation(
        scenario_id="structural_tuning",
        domain="structural",
        graph_score=1.0,
        run_evaluation=eval_result,
        semantic_evaluation=None,
        hard_failure=None,
        overall_score=None,
    )
    diagnostic = build_structural_diagnostic(
        scenario_eval, tuning_memory, landscape,
    )

    # ── Phase 3: Propose ──
    proposals = propose_structural_mutations(
        diagnostic, landscape, mutation_history,
    )

    if not proposals:
        return StructuralTuningCycleResult(
            quality_before=q_before,
            diagnostic=diagnostic,
            proposals=[],
            applied_mutations=[],
            accepted=False,
        )

    # ── Phase 4: Apply and re-run ──
    applied: List[StructuralMutation] = []
    for m in proposals:
        try:
            applied_m = apply_structural_mutation(m, landscape)
            applied.append(applied_m)
        except ValueError:
            pass  # skip non-admissible (race with prior mutation)

    if not applied:
        return StructuralTuningCycleResult(
            quality_before=q_before,
            diagnostic=diagnostic,
            proposals=proposals,
            applied_mutations=[],
            accepted=False,
        )

    # ── Phase 4b: Identity Invariant check (B4-S4a) ──
    # Before re-running, verify the mutated landscape preserves E₀ identity.
    # If the goal is unreachable or reachable states lack exits, revert.
    identity = check_identity_invariant(landscape, start, goal)
    if not identity.satisfied:
        for m in reversed(applied):
            revert_structural_mutation(m, landscape)

        records = [
            MutationRecord(
                mutation=m,
                quality_before=q_before,
                quality_after=None,
                accepted=False,
                reverted=True,
            )
            for m in applied
        ]
        for r in records:
            mutation_history.record(r)

        return StructuralTuningCycleResult(
            quality_before=q_before,
            diagnostic=diagnostic,
            proposals=proposals,
            applied_mutations=applied,
            accepted=False,
            reverted=True,
            mutation_records=records,
            identity_invariant=identity,
        )

    # Reset for clean re-run
    _reset_landscape(landscape)
    controller._recent = []
    controller._escalation_edges = {}

    trace_after = controller.run(start, max_cycles=max_cycles, goal=goal)
    fs_after = field_summary_from_run(landscape, trace_after)
    goal_reached_after = (
        trace_after.path[-1] == goal if (goal and trace_after.path) else False
    )
    q_after = quality_score(fs_after, goal_reached_after)
    delta = q_after - q_before

    # ── Phase 5: Accept or revert ──
    if delta < 0:
        # Regression: revert all applied mutations (reverse order)
        for m in reversed(applied):
            revert_structural_mutation(m, landscape)

        records = [
            MutationRecord(
                mutation=m,
                quality_before=q_before,
                quality_after=q_after,
                accepted=False,
                reverted=True,
            )
            for m in applied
        ]
        for r in records:
            mutation_history.record(r)

        return StructuralTuningCycleResult(
            quality_before=q_before,
            diagnostic=diagnostic,
            proposals=proposals,
            applied_mutations=applied,
            quality_after=q_after,
            delta_quality=delta,
            accepted=False,
            reverted=True,
            mutation_records=records,
            identity_invariant=identity,
        )

    # Improvement (or neutral): accept
    records = [
        MutationRecord(
            mutation=m,
            quality_before=q_before,
            quality_after=q_after,
            accepted=True,
            reverted=False,
        )
        for m in applied
    ]
    for r in records:
        mutation_history.record(r)

    return StructuralTuningCycleResult(
        quality_before=q_before,
        diagnostic=diagnostic,
        proposals=proposals,
        applied_mutations=applied,
        quality_after=q_after,
        delta_quality=delta,
        accepted=True,
        reverted=False,
        mutation_records=records,
        identity_invariant=identity,
    )
