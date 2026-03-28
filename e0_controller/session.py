"""
E₀ Session Orchestrator
========================
Thin orchestration layer between E₀ controller and MemOS persistence.

The controller stays pure — no persistence awareness.
The orchestrator manages the lifecycle:

    load  → (restore context + tuning memory from disk)
    run   → (delegate to controller.run)    iterate → (multi-run until tension equilibrium, C37)    save  → (persist context + run record + tuning memory)

This is the handoff point for external systems.  Anything that
wants to use E₀ as a core should go through Session, not through
the controller directly.

Usage
-----
    session = Session("my-session", landscape, execute_fn)
    trace   = session.run("START", goal="GOAL")
    # → context, run record, and tuning memory saved to disk

    # Later / new process:
    session2 = Session.resume("my-session", execute_fn)
    trace2   = session2.run("START", goal="GOAL")
    # → picks up where it left off (historization, params, memory)
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

from .controller import E0Controller, HybridMode, RunTrace
from .landscape import Landscape
from .memory_os import CanonRef, E0MemoryOS, MemOSContext
from .self_tuning import (
    TuningMemory,
    load_tuning_memory,
    save_tuning_memory,
)
from .provenance import ProvenanceLog
from .exploration_policy import ExplorationPolicy, PolicyDecision
from .residual_tension import (
    ResidualTensionMap,
    IterationVerdict,
    compute_residual_map,
    should_continue,
    snapshot_tensions,
)
from .evaluation import (
    evaluate_run,
    ScenarioEvaluation,
)
from .reflection import (
    ReflectionReport,
    reflect,
    should_reflect as _should_reflect,
)
from .structural_mutation import (
    MutationHistory,
    StructuralTuningCycleResult,
    structural_tuning_cycle,
)


@dataclass
class SessionResult:
    """Output of a single session run — everything external systems need."""
    trace: RunTrace
    context: MemOSContext
    tuning_memory: TuningMemory
    session_id: str
    resumed: bool             # True if loaded from prior state


@dataclass
class IterationResult:
    """Output of Session.iterate() — multi-run until equilibrium."""
    results: List[SessionResult]           # one per iteration
    verdicts: List[IterationVerdict]       # one per iteration
    reflections: List[Optional[ReflectionReport]]  # one per iteration (None if not triggered)
    final_map: Optional[ResidualTensionMap]  # last tension map
    iterations: int                        # how many runs were made
    stop_reason: str                       # "equilibrium" | "stagnation" | "budget"
    policy_phases: List[str] = field(default_factory=list)  # C41: per-iteration phase ("warmup"/"exploit"/"converged")
    structural_results: List[Optional[StructuralTuningCycleResult]] = field(default_factory=list)  # B4-S3: per-iteration structural tuning


class Session:
    """Orchestrates E₀ controller runs with automatic persistence.

    Manages the full lifecycle:
    1. Optionally resume from a prior session on disk
    2. Run the controller
    3. Persist everything (context, run record, tuning memory)

    The controller itself has zero persistence awareness.
    """

    def __init__(
        self,
        session_id: str,
        landscape: Landscape,
        execute_fn: Callable,
        *,
        base_dir: str = "memos",
        canon_refs: Optional[List[CanonRef]] = None,
        controller_kwargs: Optional[Dict[str, Any]] = None,
        provenance: Optional[ProvenanceLog] = None,
    ):
        """Create a new session (no disk load).

        Parameters
        ----------
        session_id : str
            Unique identifier for this session.
        landscape : Landscape
            The transition landscape.
        execute_fn : callable
            Edge execution function for the controller.
        base_dir : str
            Root directory for MemOS persistence.
        canon_refs : list of CanonRef, optional
            Canonical references to attach to the session.
        controller_kwargs : dict, optional
            Extra kwargs passed to E0Controller (alpha, hybrid_mode, …).
        """
        self.session_id = session_id
        self.landscape = landscape
        self.execute_fn = execute_fn
        self.base_dir = base_dir
        self.canon_refs = canon_refs or []
        self._resumed = False
        self._provenance = provenance

        kwargs = controller_kwargs or {}
        self.controller = E0Controller(landscape, execute_fn, **kwargs)

        self.memos = E0MemoryOS(base_dir=base_dir)
        self.tuning_memory = load_tuning_memory(
            session_id, base_dir=base_dir,
        )
        self.mutation_history = MutationHistory()

    @classmethod
    def resume(
        cls,
        session_id: str,
        execute_fn: Callable,
        *,
        base_dir: str = "memos",
    ) -> "Session":
        """Resume a session from disk.

        Restores landscape, historization, controller params,
        and tuning memory from a prior save.

        Raises FileNotFoundError if the session doesn't exist.
        """
        memos = E0MemoryOS(base_dir=base_dir)
        ctx = memos.load_context(session_id)

        landscape = memos.restore_landscape(ctx)
        controller = memos.restore_controller(ctx, landscape, execute_fn)

        # Reconstruct canon refs
        canon_refs = [
            CanonRef(
                name=cr.get("name", ""),
                version=cr.get("version", ""),
                path=cr.get("path", ""),
                sha=cr.get("sha"),
            )
            for cr in ctx.canon_refs
        ]

        obj = cls.__new__(cls)
        obj.session_id = session_id
        obj.landscape = landscape
        obj.execute_fn = execute_fn
        obj.base_dir = base_dir
        obj.canon_refs = canon_refs
        obj._resumed = True
        obj._provenance = None
        obj.controller = controller
        obj.memos = memos
        obj.tuning_memory = load_tuning_memory(
            session_id, base_dir=base_dir,
        )
        obj.mutation_history = MutationHistory()
        return obj

    def run(
        self,
        start: str,
        goal: Optional[str] = None,
        max_cycles: int = 50,
        *,
        auto_save: bool = True,
    ) -> SessionResult:
        """Run the controller and persist results.

        Parameters
        ----------
        start : str
            Start state.
        goal : str, optional
            Goal state.
        max_cycles : int
            Maximum controller cycles.
        auto_save : bool
            If True (default), save context + run record + tuning
            memory to disk after the run completes.

        Returns
        -------
        SessionResult
            Contains trace, context, tuning memory, and metadata.
        """
        if goal is not None and hasattr(self.controller, "hybrid_geometry"):
            geom = self.controller.hybrid_geometry
            if geom != "goal_reaching":
                warnings.warn(
                    f"Goal '{goal}' is set but hybrid_geometry='{geom}'. "
                    f"Without goal_reaching geometry, amplitude may prefer "
                    f"high-branching states over goal-directed paths. "
                    f"Consider hybrid_geometry='goal_reaching'.",
                    stacklevel=2,
                )

        trace = self.controller.run(start, max_cycles=max_cycles, goal=goal)

        if self._provenance is not None:
            ctrl = self.controller
            config = {
                "goal": goal or "",
                "max_cycles": max_cycles,
                "hybrid_mode": ctrl.hybrid_mode.value,
                "hybrid_geometry": ctrl.hybrid_geometry,
                "hybrid_horizon": ctrl.hybrid_horizon,
                "alpha": ctrl.alpha,
                "confidence_threshold": ctrl.confidence_threshold,
            }
            self._provenance.record_run(trace, config)

        ctx = self.memos.snapshot_from_runtime(
            self.session_id,
            self.landscape,
            self.controller,
            trace,
            canon_refs=self.canon_refs,
        )

        if auto_save:
            self.memos.save_context(ctx)
            self.memos.save_run(self.session_id, trace, goal=goal)
            save_tuning_memory(
                self.tuning_memory,
                self.session_id,
                base_dir=self.base_dir,
            )

        return SessionResult(
            trace=trace,
            context=ctx,
            tuning_memory=self.tuning_memory,
            session_id=self.session_id,
            resumed=self._resumed,
        )

    def recent_runs(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Retrieve recent run records from disk."""
        return self.memos.retrieve_recent_runs(self.session_id, limit=limit)

    def iterate(
        self,
        start: str,
        goal: Optional[str] = None,
        max_cycles: int = 50,
        *,
        max_iterations: int = 10,
        tension_threshold: float = 0.1,
        exploration_policy: Optional[ExplorationPolicy] = None,
    ) -> "IterationResult":
        """Run the controller repeatedly until tension equilibrium.

        Each iteration:
        1. Snapshot pre-run tensions
        2. Run the controller
        3. Compute residual tension map
        4. Decide: continue, reflect, or present

        Stops on: equilibrium, stagnation, or budget.
        The number of iterations is not prescribed — it emerges
        from the landscape's tension structure (Axiom A₀).

        Parameters
        ----------
        start : str
            Start state for each run.
        goal : str, optional
            Goal state.
        max_cycles : int
            Maximum controller cycles per run.
        max_iterations : int
            Hard budget limit on iterations.
        tension_threshold : float
            Residual tension below this is considered resolved.
        exploration_policy : ExplorationPolicy, optional
            C41: controls per-iteration explore→exploit mode switching.
            None = use controller's existing hybrid_mode throughout.

        Returns
        -------
        IterationResult
            Contains all session results, verdicts, and final map.
        """
        results: List[SessionResult] = []
        verdicts: List[IterationVerdict] = []
        reflections: List[Optional[ReflectionReport]] = []
        structural_results: List[Optional[StructuralTuningCycleResult]] = []
        policy_phases: List[str] = []
        prev_map: Optional[ResidualTensionMap] = None

        # C41: save original mode to restore after iterate()
        original_mode = self.controller.hybrid_mode

        for i in range(1, max_iterations + 1):
            # C41: apply exploration policy
            if exploration_policy is not None:
                decision = exploration_policy.decide(i, prev_map)
                self.controller.hybrid_mode = decision.mode
                policy_phases.append(decision.phase)
            else:
                policy_phases.append("fixed")
            # 1. Snapshot tensions before run
            pre = snapshot_tensions(self.landscape)

            # 2. Run
            result = self.run(start, goal=goal, max_cycles=max_cycles)
            results.append(result)

            # 3. Compute residual tension map
            rmap = compute_residual_map(
                self.landscape, result.trace, pre, iteration=i,
            )

            # 4. Decide
            verdict = should_continue(
                rmap, prev_map,
                iteration=i,
                max_iterations=max_iterations,
                tension_threshold=tension_threshold,
            )
            verdicts.append(verdict)
            prev_map = rmap

            # 5. Reflect between iterations if warranted
            report = None
            if verdict.should_reflect or not verdict.should_continue:
                report = self._inter_iteration_reflect(
                    result, goal, rmap,
                )
            reflections.append(report)

            # 6. Structural mutation (B4-S3) — only on structural trigger
            stc_result = None
            if (report is not None
                    and report.reflection_type == "structural"
                    and verdict.should_continue):
                stc_result = structural_tuning_cycle(
                    self.controller,
                    start,
                    goal=goal,
                    max_cycles=max_cycles,
                    mutation_history=self.mutation_history,
                    tuning_memory=self.tuning_memory,
                )
            structural_results.append(stc_result)

            if not verdict.should_continue:
                break

        # C41: restore original mode
        if exploration_policy is not None:
            self.controller.hybrid_mode = original_mode

        return IterationResult(
            results=results,
            verdicts=verdicts,
            reflections=reflections,
            final_map=prev_map,
            iterations=len(results),
            stop_reason=verdicts[-1].reason if verdicts else "empty",
            policy_phases=policy_phases,
            structural_results=structural_results,
        )

    def _inter_iteration_reflect(
        self,
        result: SessionResult,
        goal: Optional[str],
        rmap: ResidualTensionMap,
    ) -> Optional[ReflectionReport]:
        """Run reflection between iterations.

        Builds a ScenarioEvaluation from the last run and calls
        the reflection layer.  Returns ReflectionReport or None.
        """
        trace = result.trace
        m = trace.metrics()
        reached = goal in trace.path if goal else True

        # Find happy path length for efficiency calculation
        happy_len = int(m["steps"])
        try:
            from .graph_validation import find_happy_path
            hp = find_happy_path(self.landscape, trace.path[0], goal)
            if hp:
                happy_len = len(hp) - 1
        except Exception:
            pass

        eval_result = evaluate_run(
            path=trace.path,
            steps=int(m["steps"]),
            escalation_count=int(m.get("escalation_count", 0)),
            revisit_count=int(m["revisit_count"]),
            success_rate=m["success_rate"],
            avg_tension=m["avg_tension"],
            total_tension=trace.total_tension,
            reached_goal=reached,
            happy_path_length=happy_len,
        )

        scenario_eval = ScenarioEvaluation(
            scenario_id=self.session_id,
            domain="iterate",
            graph_score=1.0,
            run_evaluation=eval_result,
            semantic_evaluation=None,
            hard_failure=None,
            overall_score=None,
        )

        return reflect(
            scenario_eval,
            tuning_memory=self.tuning_memory,
            landscape=self.landscape,
        )

    @property
    def exists_on_disk(self) -> bool:
        """Check if this session has been saved before."""
        return self.memos.session_exists(self.session_id)
