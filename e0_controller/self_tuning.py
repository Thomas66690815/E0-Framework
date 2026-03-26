"""
E₀ Self-Tuning Layer (B4.1 – B4.4)
=====================================
Reflexivity as self-application of E₀ dynamics.

The key insight: reflexivity is NOT a new primitive.  It is the E₀
controller's transition logic applied to its own parameter space.

Meta-Landscape
--------------
Object level:   states = {A, B, C, …},  v(x, y) = Δ · M_H · exp(−S_eff)
Meta level:     states = {θ₁, θ₂, …},   v_meta(θ, θ') = Δ_meta · exp(−S_meta)

where θ = (alpha, s_max, override_confidence, …) is the controller
parameter vector.

Derived Thresholds
------------------
Instead of ad-hoc constants the reflection layer uses field-derived
thresholds that emerge from the run's own transition structure:

    τ_eff  = ⟨v⟩ / v_max         normalised mean field (0–1)
    τ_loop = repeated_cycles / |X| topology-relative loop measure
    τ_esc  = escalations / |E|     edge-relative escalation pressure

These are ratios of observable field quantities — no magic numbers.

Sensitivity Attribution
-----------------------
Layer attribution is replaced by a per-parameter sensitivity estimate:

    sensitivity(θ_i) = |Δ B_meta / Δ θ_i|

computed from the meta-landscape's local gradient.  Parameters with
high sensitivity are the most impactful candidates for adjustment.

Bounded Adjustment (Oscillation Protection)
-------------------------------------------
Meta-historization H_meta prevents oscillation: a parameter that was
recently adjusted in one direction cannot be immediately pushed back.
This mirrors the object-level historization semantics exactly.

Tuning Cycle (B4.2)
--------------------
The feedback loop closes the reflection → tuning → verification arc:

    1. Run controller on landscape
    2. Extract RunFieldSummary from the run
    3. Propose parameter adjustments via meta-layer
    4. Apply adjustments and re-run
    5. Measure Δ_meta = quality_after − quality_before
    6. Accept if improved, revert if degraded (meta-admissibility)

Cross-Run Memory (B4.3)
-----------------------
TuningMemory persists a bounded history of TuningSnapshots across
runs.  Each snapshot captures Q, the 5 τ metrics, controller params,
and applied changes.  Analysis functions extract:

    quality_trend   — linear slope of Q over last N runs
    recurring_issues — which τ dimensions trigger issues repeatedly
    parameter_drift — net parameter movement over time
    suggest_from_history — cross-run pattern → actionable insight

Serialization via to_dict/from_dict integrates with MemOS.

True Sensitivity Analysis (B4.4)
---------------------------------
Replace heuristic sensitivity attribution with empirical
finite-difference gradients:

    ∂Q/∂θ_i ≈ (Q(θ + ε_i) − Q(θ − ε_i)) / 2ε

Each parameter is perturbed independently, the controller re-runs
under identical conditions, and the quality delta is measured.
This replaces the heuristic rules in compute_parameter_sensitivities
with ground-truth gradients from the actual landscape.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ──────────────────────────────────────────────
# 1. Run Field Summary
# ──────────────────────────────────────────────

@dataclass
class RunFieldSummary:
    """Field-derived quantities from a single controller run.

    All values are normalised and emerge from the run's own
    transition structure — no external constants required.
    """
    # Transition field statistics
    v_mean: float               # ⟨v(x→y)⟩ over all traversed edges
    v_max: float                # max v(x→y) over entire landscape
    v_total: float              # Σ v across all landscape edges

    # Topology-relative counts
    num_states: int             # |X| — total states in landscape
    num_edges: int              # |E| — total directed edges
    steps: int                  # τ_final — steps taken
    escalations: int            # escalation count
    repeated_cycles: int        # 2-cycle count
    unique_states_visited: int  # distinct states visited

    @property
    def tau_eff(self) -> float:
        """Normalised mean field: ⟨v⟩ / v_max ∈ [0, 1].

        High τ_eff means the run traversed strong-field edges on average.
        Low τ_eff means the run used weak or marginal transitions.
        """
        if self.v_max <= 0:
            return 0.0
        return min(self.v_mean / self.v_max, 1.0)

    @property
    def tau_loop(self) -> float:
        """Topology-relative loop measure: repeated_cycles / |X|.

        Normalises looping against the landscape size.
        A 2-cycle in a 100-state graph is less alarming than in a 5-state graph.
        """
        if self.num_states <= 0:
            return 0.0
        return self.repeated_cycles / self.num_states

    @property
    def tau_esc(self) -> float:
        """Edge-relative escalation pressure: escalations / |E|.

        High τ_esc means the graph's edge structure is insufficient
        for the controller — frequent escape required.
        """
        if self.num_edges <= 0:
            return 0.0
        return self.escalations / self.num_edges

    @property
    def tau_progress(self) -> float:
        """Field-normalised progress: unique_visited / |X|.

        How much of the landscape was explored relative to its size.
        """
        if self.num_states <= 0:
            return 0.0
        return min(self.unique_states_visited / self.num_states, 1.0)

    @property
    def tau_efficiency(self) -> float:
        """Step-normalised exploration: unique_visited / steps.

        1.0 = every step discovered a new state (no revisits).
        Low values indicate looping or oscillation.
        """
        if self.steps <= 0:
            return 0.0
        return min(self.unique_states_visited / self.steps, 1.0)


# ──────────────────────────────────────────────
# 2. Build RunFieldSummary from Controller State
# ──────────────────────────────────────────────

def field_summary_from_run(landscape, trace) -> RunFieldSummary:
    """Extract a RunFieldSummary from a Landscape and RunTrace.

    Computes transition field statistics over the entire landscape
    and maps the run trace to topology-relative metrics.
    """
    # Landscape-level field statistics
    all_v = []
    for edge in landscape._R0:
        v = landscape.transition_field(edge.source, edge.target)
        all_v.append(v)

    v_max = max(all_v) if all_v else 0.0
    v_total = sum(all_v)

    # Traversed-edge field values
    traversed_v = []
    for step in trace.steps:
        v = landscape.transition_field(step.source, step.target)
        traversed_v.append(v)

    v_mean = (sum(traversed_v) / len(traversed_v)) if traversed_v else 0.0

    # Topology counts
    num_states = len(landscape.states)
    num_edges = len(landscape._R0)

    # Run trace counts
    path = trace.path
    unique = set(path)

    # 2-cycle detection
    repeated_cycles = 0
    for i in range(len(path) - 2):
        if path[i] == path[i + 2] and path[i] != path[i + 1]:
            repeated_cycles += 1

    escalations = sum(1 for s in trace.steps if s.escalated)

    return RunFieldSummary(
        v_mean=v_mean,
        v_max=v_max,
        v_total=v_total,
        num_states=num_states,
        num_edges=num_edges,
        steps=len(trace.steps),
        escalations=escalations,
        repeated_cycles=repeated_cycles,
        unique_states_visited=len(unique),
    )


# ──────────────────────────────────────────────
# 3. Derived Reflection Thresholds
# ──────────────────────────────────────────────

@dataclass
class DerivedThresholds:
    """Reflection trigger thresholds derived from field quantities.

    Every threshold is a ratio of landscape/run observables.
    No magic numbers — they emerge from the structure itself.
    """
    # Quality triggers (reflect when below/above these)
    quality_efficiency: float     # if tau_efficiency < this → quality issue
    quality_loop: float           # if tau_loop > this → looping issue
    quality_escalation: float     # if tau_esc > this → escalation issue
    quality_progress: float       # if tau_progress < this → progress issue

    # Opportunity triggers (reflect when above these)
    opportunity_efficiency: float
    opportunity_progress: float


def derive_thresholds(fs: RunFieldSummary) -> DerivedThresholds:
    """Derive reflection thresholds from a RunFieldSummary.

    The thresholds scale with τ_eff — the normalised mean field
    strength of the run.  When the field is strong (high τ_eff),
    we expect clean traversal so thresholds are tighter.  When the
    field is weak, we are more tolerant.

    Quality boundary:
        quality_efficiency = τ_eff / 2
        → strong field   (τ_eff=0.8) → expect efficiency ≥ 0.4
        → weak field     (τ_eff=0.2) → expect efficiency ≥ 0.1

    Loop tolerance:
        quality_loop = (1 − τ_eff) / |X|
        → strong field → almost no loops tolerated
        → weak field   → more loops accepted (terrain is hard)

    Escalation tolerance:
        quality_escalation = (1 − τ_eff) / 2
        → strong field → low escalation expected
        → weak field   → some escalation accepted

    Progress expectation:
        quality_progress = τ_eff / 2
        → mirrors efficiency

    Opportunity boundary:
        opportunity_efficiency = (1 + τ_eff) / 2
        → high bar when field is strong, moderate when weak
    """
    tau = fs.tau_eff

    # Quality: expect more when field is strong
    q_eff = tau / 2.0
    q_loop = (1.0 - tau) / max(fs.num_states, 1)
    q_esc = (1.0 - tau) / 2.0
    q_prog = tau / 2.0

    # Opportunity: require proportionally more
    o_eff = (1.0 + tau) / 2.0
    o_prog = (1.0 + tau) / 2.0

    return DerivedThresholds(
        quality_efficiency=q_eff,
        quality_loop=q_loop,
        quality_escalation=q_esc,
        quality_progress=q_prog,
        opportunity_efficiency=o_eff,
        opportunity_progress=o_prog,
    )


# ──────────────────────────────────────────────
# 4. Meta-Parameter Space
# ──────────────────────────────────────────────

# Tunable controller parameters with their bounds
TUNABLE_PARAMS = {
    "alpha":                  (0.5, 10.0),    # revisit penalty weight
    "s_max":                  (1.0, 1e6),     # tension ceiling
    "c_min":                  (0.0, 0.9),     # coherence floor
    "confidence_threshold":   (0.0, 0.95),    # hybrid override gate
    "hybrid_horizon":         (1, 10),        # amplitude lookahead
}


@dataclass
class ParameterSensitivity:
    """Sensitivity of run quality to a single controller parameter.

    sensitivity = |Δ quality / Δ θ_i|  (normalised)

    Higher sensitivity → this parameter has more potential to
    improve the run if adjusted.
    """
    name: str
    current_value: float
    sensitivity: float      # |∂ quality / ∂ θ_i| (normalised, 0–1)
    suggested_direction: str  # "increase" | "decrease" | "stable"
    bounds: Tuple[float, float]


def compute_parameter_sensitivities(
    fs: RunFieldSummary,
    controller_params: Dict[str, float],
) -> List[ParameterSensitivity]:
    """Estimate per-parameter sensitivity from field summary.

    This uses structural heuristics from the meta-landscape:

    alpha (revisit penalty):
        - high tau_loop → low alpha causes cycles → increase alpha
        - sensitivity ∝ tau_loop

    s_max (tension ceiling):
        - high tau_esc with FILTERED escalation → s_max too low
        - sensitivity ∝ tau_esc

    c_min (coherence floor):
        - high tau_esc → c_min might filter too aggressively
        - sensitivity ∝ tau_esc · (1 - tau_eff)

    confidence_threshold (hybrid gate):
        - meaningful only when hybrid active
        - sensitivity ∝ (1 - tau_eff) · override rate

    hybrid_horizon (lookahead):
        - longer horizon helps in weak fields
        - sensitivity ∝ (1 - tau_eff)
    """
    results: List[ParameterSensitivity] = []

    for name, bounds in TUNABLE_PARAMS.items():
        current = controller_params.get(name, bounds[0])

        if name == "alpha":
            sens = fs.tau_loop * 2.0  # normalise to ~[0, 1]
            direction = "increase" if fs.tau_loop > 0 else "stable"
        elif name == "s_max":
            sens = fs.tau_esc
            direction = "increase" if fs.tau_esc > 0.1 else "stable"
        elif name == "c_min":
            sens = fs.tau_esc * (1.0 - fs.tau_eff)
            direction = "decrease" if fs.tau_esc > 0.1 else "stable"
        elif name == "confidence_threshold":
            sens = (1.0 - fs.tau_eff) * 0.5
            direction = "decrease" if fs.tau_eff < 0.3 else "stable"
        elif name == "hybrid_horizon":
            sens = 1.0 - fs.tau_eff
            direction = "increase" if fs.tau_eff < 0.5 else "stable"
        else:
            sens = 0.0
            direction = "stable"

        sens = min(max(sens, 0.0), 1.0)

        results.append(ParameterSensitivity(
            name=name,
            current_value=current,
            sensitivity=sens,
            suggested_direction=direction,
            bounds=bounds,
        ))

    # Sort by sensitivity descending
    results.sort(key=lambda p: p.sensitivity, reverse=True)
    return results


# ──────────────────────────────────────────────
# 5. Tuning Proposal
# ──────────────────────────────────────────────

@dataclass
class TuningProposal:
    """A bounded parameter adjustment proposed by the meta-layer.

    Contains old → new values plus the field-derived justification.
    """
    parameter: str
    old_value: float
    new_value: float
    sensitivity: float
    reason: str


@dataclass
class MetaTuningResult:
    """Complete output of one meta-tuning cycle."""
    field_summary: RunFieldSummary
    derived_thresholds: DerivedThresholds
    sensitivities: List[ParameterSensitivity]
    proposals: List[TuningProposal]
    meta_historization: Dict[str, List[float]]  # param → history of values


# Meta-historization: tracks recent parameter adjustments
# to prevent oscillation (mirrors object-level H)
_PARAM_HISTORY_WINDOW = 5    # remember last N values per parameter
_STEP_FRACTION = 0.15        # max 15% change per tuning cycle


def propose_tuning(
    fs: RunFieldSummary,
    controller_params: Dict[str, float],
    param_history: Optional[Dict[str, List[float]]] = None,
    step_fraction: float = _STEP_FRACTION,
) -> MetaTuningResult:
    """Generate bounded tuning proposals from a run's field summary.

    The meta-layer proposes parameter adjustments based on:
    1. Field-derived thresholds (what *should* have happened)
    2. Parameter sensitivities (which lever to pull)
    3. Meta-historization (prevent oscillation)

    Adjustments are bounded to ±step_fraction of the parameter range
    per cycle.  Parameters recently adjusted in the opposite direction
    are frozen (oscillation protection via H_meta).
    """
    thresholds = derive_thresholds(fs)
    sensitivities = compute_parameter_sensitivities(fs, controller_params)

    if param_history is None:
        param_history = {}

    proposals: List[TuningProposal] = []

    for ps in sensitivities:
        if ps.sensitivity < 0.05 or ps.suggested_direction == "stable":
            continue

        # H_meta: oscillation check
        history = param_history.get(ps.name, [])
        if _would_oscillate(history, ps.suggested_direction):
            continue

        current = ps.current_value
        lo, hi = ps.bounds

        # Bounded step: proportional to sensitivity and range
        param_range = hi - lo
        max_step = param_range * step_fraction * ps.sensitivity

        if ps.suggested_direction == "increase":
            new_val = min(current + max_step, hi)
            reason = f"tau_{_metric_for(ps.name)}={_metric_value(fs, ps.name):.3f} → increase {ps.name}"
        else:
            new_val = max(current - max_step, lo)
            reason = f"tau_{_metric_for(ps.name)}={_metric_value(fs, ps.name):.3f} → decrease {ps.name}"

        if abs(new_val - current) < 1e-10:
            continue  # no effective change

        proposals.append(TuningProposal(
            parameter=ps.name,
            old_value=current,
            new_value=new_val,
            sensitivity=ps.sensitivity,
            reason=reason,
        ))

        # Update history
        new_history = list(history) + [new_val]
        if len(new_history) > _PARAM_HISTORY_WINDOW:
            new_history = new_history[-_PARAM_HISTORY_WINDOW:]
        param_history[ps.name] = new_history

    return MetaTuningResult(
        field_summary=fs,
        derived_thresholds=thresholds,
        sensitivities=sensitivities,
        proposals=proposals,
        meta_historization=dict(param_history),
    )


def _would_oscillate(history: List[float], direction: str) -> bool:
    """H_meta: detect oscillation in parameter history.

    If the last two adjustments went in alternating directions,
    freeze this parameter to prevent ping-pong.
    """
    if len(history) < 3:
        return False

    # Extract direction of last two changes
    d1 = history[-1] - history[-2]
    d2 = history[-2] - history[-3]

    if abs(d1) < 1e-10 or abs(d2) < 1e-10:
        return False

    # Alternating sign = oscillation
    return (d1 > 0) != (d2 > 0)


def _metric_for(param_name: str) -> str:
    """Map parameter name to its driving metric."""
    return {
        "alpha": "loop",
        "s_max": "esc",
        "c_min": "esc",
        "confidence_threshold": "eff",
        "hybrid_horizon": "eff",
    }.get(param_name, "eff")


def _metric_value(fs: RunFieldSummary, param_name: str) -> float:
    """Get the metric value driving a parameter's sensitivity."""
    key = _metric_for(param_name)
    return {
        "loop": fs.tau_loop,
        "esc": fs.tau_esc,
        "eff": fs.tau_eff,
        "progress": fs.tau_progress,
    }.get(key, 0.0)


# ──────────────────────────────────────────────
# 6. Apply Tuning to Controller
# ──────────────────────────────────────────────

def apply_tuning(controller, proposals: List[TuningProposal]) -> List[str]:
    """Apply approved tuning proposals to a controller instance.

    Returns a list of applied change descriptions.
    Only modifies parameters that exist as controller attributes.
    """
    applied: List[str] = []

    for p in proposals:
        if not hasattr(controller, p.parameter):
            continue

        old = getattr(controller, p.parameter)
        setattr(controller, p.parameter, p.new_value)
        applied.append(
            f"{p.parameter}: {old:.4f} → {p.new_value:.4f} "
            f"(sensitivity={p.sensitivity:.3f}, {p.reason})"
        )

    return applied


# ──────────────────────────────────────────────
# 7. Quality Score (Meta-Burden)
# ──────────────────────────────────────────────

def quality_score(fs: RunFieldSummary, goal_reached: bool) -> float:
    """Compute a scalar quality score Q ∈ [0, 1] from field summary.

    Q is the *negative meta-burden*: higher is better.

    Q = w_goal · 𝟙[goal] + w_eff · τ_efficiency + w_prog · τ_progress
        − w_loop · τ_loop − w_esc · τ_esc

    The weights reflect E₀ priorities:
    - Goal achievement dominates (0.4)
    - Efficiency and progress contribute positively
    - Loops and escalations are costs

    Result is clamped to [0, 1].
    """
    raw = (
        0.4 * (1.0 if goal_reached else 0.0)
        + 0.25 * fs.tau_efficiency
        + 0.15 * fs.tau_progress
        - 0.1 * min(fs.tau_loop, 1.0)
        - 0.1 * min(fs.tau_esc, 1.0)
    )
    return max(0.0, min(1.0, raw))


# ──────────────────────────────────────────────
# 8. Tuning Cycle (B4.2)
# ──────────────────────────────────────────────

@dataclass
class TuningCycleResult:
    """Complete output of one tuning feedback cycle.

    Documents the before/after state so the improvement
    (or regression) is fully auditable.
    """
    # Before tuning
    quality_before: float
    field_before: RunFieldSummary
    goal_reached_before: bool

    # Tuning decision
    tuning: MetaTuningResult
    applied_changes: List[str]

    # After tuning (None if no proposals or tuning skipped)
    quality_after: Optional[float] = None
    field_after: Optional[RunFieldSummary] = None
    goal_reached_after: Optional[bool] = None

    # Meta-result
    delta_quality: Optional[float] = None  # Q_after − Q_before
    accepted: bool = False                 # True if improvement accepted
    reverted: bool = False                 # True if regression was reverted


def _extract_controller_params(controller) -> Dict[str, float]:
    """Extract current tunable parameter values from a controller."""
    params = {}
    for name in TUNABLE_PARAMS:
        if hasattr(controller, name):
            params[name] = float(getattr(controller, name))
    return params


def _reset_landscape(landscape) -> None:
    """Reset historization for a clean re-run.

    Clears δ_H and trace records so the landscape is structurally
    identical but without run history.
    """
    from .historization import Historization
    # Preserve learning parameters, reset state
    old_h = landscape.historization
    landscape.historization = Historization(
        rho=old_h.rho,
        lambda_s=old_h.lambda_s,
        lambda_f=old_h.lambda_f,
        delta_max=old_h.delta_max,
    )
    # Invalidate M_H cache if curvature modulation is active
    if hasattr(landscape, '_M_H_cache'):
        delattr(landscape, '_M_H_cache')


def tuning_cycle(
    controller,
    start: str,
    goal: Optional[str] = None,
    max_cycles: int = 50,
    param_history: Optional[Dict[str, List[float]]] = None,
    step_fraction: float = _STEP_FRACTION,
) -> TuningCycleResult:
    """Execute one complete tuning feedback cycle.

    The cycle:
    1. Run the controller from *start* (baseline run).
    2. Extract field summary and compute quality score Q_before.
    3. Propose tuning adjustments via meta-layer.
    4. If proposals exist: apply, reset landscape, re-run.
    5. Compute Q_after and Δ_meta = Q_after − Q_before.
    6. If Δ_meta < 0 (regression): revert parameters.

    The controller's landscape historization is reset between runs
    so both runs face the same structural conditions.

    Returns a TuningCycleResult documenting the full cycle.
    """
    if param_history is None:
        param_history = {}

    # ── Phase 1: Baseline run ──
    _reset_landscape(controller.landscape)
    controller._recent = []
    controller._escalation_edges = {}

    trace_before = controller.run(start, max_cycles=max_cycles, goal=goal)
    fs_before = field_summary_from_run(controller.landscape, trace_before)
    goal_reached_before = (
        trace_before.path[-1] == goal if (goal and trace_before.path) else False
    )
    q_before = quality_score(fs_before, goal_reached_before)

    # ── Phase 2: Propose tuning ──
    params = _extract_controller_params(controller)
    tuning_result = propose_tuning(
        fs_before, params,
        param_history=param_history,
        step_fraction=step_fraction,
    )

    if not tuning_result.proposals:
        return TuningCycleResult(
            quality_before=q_before,
            field_before=fs_before,
            goal_reached_before=goal_reached_before,
            tuning=tuning_result,
            applied_changes=[],
            accepted=False,
        )

    # ── Phase 3: Apply and re-run ──
    # Save old values for potential revert
    saved_params = dict(params)
    applied = apply_tuning(controller, tuning_result.proposals)

    # Reset for clean re-run
    _reset_landscape(controller.landscape)
    controller._recent = []
    controller._escalation_edges = {}

    trace_after = controller.run(start, max_cycles=max_cycles, goal=goal)
    fs_after = field_summary_from_run(controller.landscape, trace_after)
    goal_reached_after = (
        trace_after.path[-1] == goal if (goal and trace_after.path) else False
    )
    q_after = quality_score(fs_after, goal_reached_after)

    delta = q_after - q_before

    # ── Phase 4: Accept or revert ──
    if delta < 0:
        # Regression: revert all changed parameters
        for p in tuning_result.proposals:
            if hasattr(controller, p.parameter) and p.parameter in saved_params:
                setattr(controller, p.parameter, saved_params[p.parameter])

        return TuningCycleResult(
            quality_before=q_before,
            field_before=fs_before,
            goal_reached_before=goal_reached_before,
            tuning=tuning_result,
            applied_changes=applied,
            quality_after=q_after,
            field_after=fs_after,
            goal_reached_after=goal_reached_after,
            delta_quality=delta,
            accepted=False,
            reverted=True,
        )

    # Improvement (or neutral): accept
    return TuningCycleResult(
        quality_before=q_before,
        field_before=fs_before,
        goal_reached_before=goal_reached_before,
        tuning=tuning_result,
        applied_changes=applied,
        quality_after=q_after,
        field_after=fs_after,
        goal_reached_after=goal_reached_after,
        delta_quality=delta,
        accepted=True,
        reverted=False,
    )


# ──────────────────────────────────────────────
# 9. Multi-Cycle Tuning
# ──────────────────────────────────────────────

@dataclass
class MultiCycleTuningResult:
    """Output of a multi-iteration tuning session."""
    cycles: List[TuningCycleResult]
    total_delta: float                  # cumulative Δ Q
    final_params: Dict[str, float]      # controller params after all cycles
    converged: bool                     # True if last cycle had no proposals


def tune(
    controller,
    start: str,
    goal: Optional[str] = None,
    max_cycles_per_run: int = 50,
    max_tuning_iterations: int = 5,
    step_fraction: float = _STEP_FRACTION,
) -> MultiCycleTuningResult:
    """Run multiple tuning cycles until convergence or iteration limit.

    Each cycle: run → diagnose → adjust → verify → accept/revert.
    Stops when:
    - No proposals are generated (converged), or
    - max_tuning_iterations reached, or
    - Two consecutive reversions (stuck)

    Returns a MultiCycleTuningResult with the complete history.
    """
    param_history: Dict[str, List[float]] = {}
    cycles: List[TuningCycleResult] = []
    consecutive_reverts = 0

    for _ in range(max_tuning_iterations):
        result = tuning_cycle(
            controller, start, goal=goal,
            max_cycles=max_cycles_per_run,
            param_history=param_history,
            step_fraction=step_fraction,
        )
        cycles.append(result)

        # Propagate meta-historization
        param_history = dict(result.tuning.meta_historization)

        # Check stopping conditions
        if not result.tuning.proposals:
            break  # converged — no more adjustments needed

        if result.reverted:
            consecutive_reverts += 1
            if consecutive_reverts >= 2:
                break  # stuck — stop tuning
        else:
            consecutive_reverts = 0

    total_delta = sum(
        (c.delta_quality for c in cycles if c.delta_quality is not None),
        0.0,
    )
    final_params = _extract_controller_params(controller)
    converged = bool(cycles) and not cycles[-1].tuning.proposals

    return MultiCycleTuningResult(
        cycles=cycles,
        total_delta=total_delta,
        final_params=final_params,
        converged=converged,
    )


# ──────────────────────────────────────────────
# 10. Cross-Run Memory (B4.3)
# ──────────────────────────────────────────────

@dataclass
class TuningSnapshot:
    """Serializable record of one run's tuning-relevant data.

    Captures everything needed for cross-run pattern recognition:
    quality score, field metrics, parameter state, and changes.
    """
    timestamp: str                       # ISO UTC
    quality: float                       # Q ∈ [0, 1]
    goal_reached: bool
    tau_eff: float
    tau_loop: float
    tau_esc: float
    tau_progress: float
    tau_efficiency: float
    params: Dict[str, float]             # controller θ at time of run
    applied_changes: List[str]           # human-readable change log
    accepted: bool                       # True if tuning was accepted


def snapshot_from_cycle(result: TuningCycleResult) -> TuningSnapshot:
    """Extract a TuningSnapshot from a completed TuningCycleResult."""
    fs = result.field_after if result.field_after is not None else result.field_before
    q = result.quality_after if result.quality_after is not None else result.quality_before
    goal = result.goal_reached_after if result.goal_reached_after is not None else result.goal_reached_before

    return TuningSnapshot(
        timestamp=datetime.now(timezone.utc).isoformat(),
        quality=q,
        goal_reached=goal,
        tau_eff=fs.tau_eff,
        tau_loop=fs.tau_loop,
        tau_esc=fs.tau_esc,
        tau_progress=fs.tau_progress,
        tau_efficiency=fs.tau_efficiency,
        params=dict(result.tuning.meta_historization.get("__snapshot_params", {})
                    or {p.parameter: p.old_value for p in result.tuning.proposals}
                    or {}),
        applied_changes=list(result.applied_changes),
        accepted=result.accepted,
    )


def _snapshot_from_cycle_with_params(
    result: TuningCycleResult,
    params: Dict[str, float],
) -> TuningSnapshot:
    """Internal: snapshot with explicit param dict (avoids re-extraction)."""
    fs = result.field_after if result.field_after is not None else result.field_before
    q = result.quality_after if result.quality_after is not None else result.quality_before
    goal = (
        result.goal_reached_after
        if result.goal_reached_after is not None
        else result.goal_reached_before
    )
    return TuningSnapshot(
        timestamp=datetime.now(timezone.utc).isoformat(),
        quality=q,
        goal_reached=goal,
        tau_eff=fs.tau_eff,
        tau_loop=fs.tau_loop,
        tau_esc=fs.tau_esc,
        tau_progress=fs.tau_progress,
        tau_efficiency=fs.tau_efficiency,
        params=dict(params),
        applied_changes=list(result.applied_changes),
        accepted=result.accepted,
    )


# ── Issue detection thresholds (from DerivedThresholds defaults) ──
_ISSUE_LOOP_THRESHOLD = 0.25     # τ_loop above this → loop issue
_ISSUE_ESC_THRESHOLD = 0.2       # τ_esc above this → escalation issue
_ISSUE_EFFICIENCY_FLOOR = 0.4    # τ_efficiency below this → efficiency issue
_ISSUE_PROGRESS_FLOOR = 0.5      # τ_progress below this → progress issue


@dataclass
class TuningMemory:
    """Bounded cross-run tuning history with analysis.

    Stores TuningSnapshots and provides temporal analysis:
    quality trends, recurring issues, parameter drift, and
    cross-run insights.  Serializable for MemOS persistence.
    """
    entries: List[TuningSnapshot] = field(default_factory=list)
    max_entries: int = 50

    def record(self, snapshot: TuningSnapshot) -> None:
        """Append a snapshot, dropping oldest if at capacity."""
        self.entries.append(snapshot)
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]

    def quality_trend(self, n: int = 5) -> float:
        """Linear slope of Q over the last *n* entries.

        Positive = improving, negative = degrading, ~0 = stable.
        Uses simple least-squares regression on indices.
        Returns 0.0 if fewer than 2 entries.
        """
        recent = self.entries[-n:] if n > 0 else []
        if len(recent) < 2:
            return 0.0

        m = len(recent)
        xs = list(range(m))
        ys = [e.quality for e in recent]
        x_mean = sum(xs) / m
        y_mean = sum(ys) / m

        num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
        den = sum((x - x_mean) ** 2 for x in xs)
        return num / den if den > 0 else 0.0

    def recurring_issues(self, n: int = 10) -> Dict[str, int]:
        """Count which τ dimensions triggered issues over last *n* runs.

        Returns e.g. {"loop": 3, "escalation": 2, "efficiency": 5}.
        A dimension counts as an issue if it exceeds its threshold.
        """
        recent = self.entries[-n:] if n > 0 else []
        counts: Dict[str, int] = {}
        for e in recent:
            if e.tau_loop > _ISSUE_LOOP_THRESHOLD:
                counts["loop"] = counts.get("loop", 0) + 1
            if e.tau_esc > _ISSUE_ESC_THRESHOLD:
                counts["escalation"] = counts.get("escalation", 0) + 1
            if e.tau_efficiency < _ISSUE_EFFICIENCY_FLOOR:
                counts["efficiency"] = counts.get("efficiency", 0) + 1
            if e.tau_progress < _ISSUE_PROGRESS_FLOOR:
                counts["progress"] = counts.get("progress", 0) + 1
        return counts

    def parameter_drift(self, param: str, n: int = 10) -> float:
        """Net change of *param* over the last *n* entries.

        Returns last_value − first_value.  0.0 if param not found or
        fewer than 2 entries.
        """
        recent = self.entries[-n:] if n > 0 else []
        values = [e.params.get(param) for e in recent if param in e.params]
        if len(values) < 2:
            return 0.0
        return values[-1] - values[0]

    def effective_proposals(self, n: int = 10) -> List[str]:
        """Proposals from accepted cycles over the last *n* entries."""
        recent = self.entries[-n:] if n > 0 else []
        result: List[str] = []
        for e in recent:
            if e.accepted and e.applied_changes:
                result.extend(e.applied_changes)
        return result

    def suggest_from_history(self) -> List[str]:
        """Generate cross-run insights from accumulated history.

        Looks for persistent patterns that single-run analysis misses:
        - Chronic issues: same τ dimension triggers in >50% of recent runs
        - Plateau: quality stable despite tuning → structural limit
        - Drift: parameter moves monotonically → may be approaching bound
        """
        suggestions: List[str] = []
        if len(self.entries) < 3:
            return suggestions

        # Chronic issues (>50% of last 10 runs)
        issues = self.recurring_issues(10)
        n_recent = min(len(self.entries), 10)
        for dim, count in issues.items():
            if count > n_recent * 0.5:
                suggestions.append(
                    f"Chronic {dim} issue: triggered in {count}/{n_recent} "
                    f"recent runs — may indicate structural landscape problem"
                )

        # Quality plateau (slope near zero despite tuning)
        trend = self.quality_trend(5)
        has_tuning = any(
            e.applied_changes for e in self.entries[-5:]
        )
        if abs(trend) < 0.01 and has_tuning:
            suggestions.append(
                "Quality plateau: tuning active but Q stable — "
                "consider landscape restructuring instead of parameter adjustment"
            )

        # Parameter drift toward bounds
        for param, (lo, hi) in TUNABLE_PARAMS.items():
            drift = self.parameter_drift(param, 10)
            if abs(drift) < 1e-6:
                continue
            # Check if last value is near a bound
            last_values = [
                e.params.get(param) for e in self.entries[-5:]
                if param in e.params
            ]
            if not last_values:
                continue
            last_val = last_values[-1]
            param_range = hi - lo
            if param_range <= 0:
                continue
            if (last_val - lo) / param_range < 0.1:
                suggestions.append(
                    f"{param} drifting toward lower bound "
                    f"({last_val:.3f} → {lo}) — may need "
                    f"landscape or strategy change"
                )
            elif (hi - last_val) / param_range < 0.1:
                suggestions.append(
                    f"{param} drifting toward upper bound "
                    f"({last_val:.3f} → {hi}) — may need "
                    f"landscape or strategy change"
                )

        return suggestions

    # ── Serialization ──

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "max_entries": self.max_entries,
            "entries": [asdict(e) for e in self.entries],
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TuningMemory":
        """Reconstruct from a serialized dict."""
        mem = cls(max_entries=d.get("max_entries", 50))
        for entry_d in d.get("entries", []):
            mem.entries.append(TuningSnapshot(**entry_d))
        return mem


# ──────────────────────────────────────────────
# 11. tune() with Memory (B4.3)
# ──────────────────────────────────────────────

def tune_with_memory(
    controller,
    start: str,
    goal: Optional[str] = None,
    max_cycles_per_run: int = 50,
    max_tuning_iterations: int = 5,
    step_fraction: float = _STEP_FRACTION,
    memory: Optional[TuningMemory] = None,
) -> MultiCycleTuningResult:
    """Like tune() but records each cycle into a TuningMemory.

    If *memory* is provided, snapshots are appended to it.
    If None, a fresh TuningMemory is created (and discarded).

    The memory can be persisted via MemOS between sessions
    to enable cross-run pattern recognition.
    """
    if memory is None:
        memory = TuningMemory()

    param_history: Dict[str, List[float]] = {}
    cycles: List[TuningCycleResult] = []
    consecutive_reverts = 0

    for _ in range(max_tuning_iterations):
        result = tuning_cycle(
            controller, start, goal=goal,
            max_cycles=max_cycles_per_run,
            param_history=param_history,
            step_fraction=step_fraction,
        )
        cycles.append(result)

        # Record snapshot into cross-run memory
        params = _extract_controller_params(controller)
        snapshot = _snapshot_from_cycle_with_params(result, params)
        memory.record(snapshot)

        # Propagate meta-historization
        param_history = dict(result.tuning.meta_historization)

        # Check stopping conditions
        if not result.tuning.proposals:
            break

        if result.reverted:
            consecutive_reverts += 1
            if consecutive_reverts >= 2:
                break
        else:
            consecutive_reverts = 0

    total_delta = sum(
        (c.delta_quality for c in cycles if c.delta_quality is not None),
        0.0,
    )
    final_params = _extract_controller_params(controller)
    converged = bool(cycles) and not cycles[-1].tuning.proposals

    return MultiCycleTuningResult(
        cycles=cycles,
        total_delta=total_delta,
        final_params=final_params,
        converged=converged,
    )


# ──────────────────────────────────────────────
# 12. MemOS Persistence Bridge (B4.3)
# ──────────────────────────────────────────────

_TUNING_DIR = "tuning"


def save_tuning_memory(
    memory: TuningMemory,
    session_id: str,
    base_dir: str = "memos",
) -> Path:
    """Persist a TuningMemory as JSON under the MemOS directory tree.

    Writes to ``{base_dir}/tuning/{session_id}.json``.
    """
    d = Path(base_dir) / _TUNING_DIR
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{session_id}.json"
    path.write_text(
        json.dumps(memory.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def load_tuning_memory(
    session_id: str,
    base_dir: str = "memos",
    max_entries: int = 50,
) -> TuningMemory:
    """Load a persisted TuningMemory, or return an empty one."""
    path = Path(base_dir) / _TUNING_DIR / f"{session_id}.json"
    if not path.exists():
        return TuningMemory(max_entries=max_entries)
    data = json.loads(path.read_text(encoding="utf-8"))
    return TuningMemory.from_dict(data)


# ──────────────────────────────────────────────
# 13. True Sensitivity Analysis (B4.4)
# ──────────────────────────────────────────────

_DEFAULT_EPSILON_FRAC = 0.05   # perturb by 5% of param range


def _run_and_score(
    controller,
    start: str,
    goal: Optional[str],
    max_cycles: int,
) -> Tuple[float, RunFieldSummary]:
    """Reset landscape, run controller, return (Q, field_summary)."""
    _reset_landscape(controller.landscape)
    controller._recent = []
    controller._escalation_edges = {}

    trace = controller.run(start, max_cycles=max_cycles, goal=goal)
    fs = field_summary_from_run(controller.landscape, trace)
    goal_reached = (
        trace.path[-1] == goal if (goal and trace.path) else False
    )
    return quality_score(fs, goal_reached), fs


def perturbation_sensitivity(
    controller,
    start: str,
    goal: Optional[str] = None,
    max_cycles: int = 50,
    epsilon_frac: float = _DEFAULT_EPSILON_FRAC,
    params: Optional[List[str]] = None,
) -> List[ParameterSensitivity]:
    """∂Q/∂θ via central finite differences on real controller runs.

    For each tunable parameter θ_i:
        1. Set θ_i = current + ε, run → Q⁺
        2. Set θ_i = current − ε, run → Q⁻
        3. gradient_i = (Q⁺ − Q⁻) / 2ε
        4. Restore θ_i to original value

    The gradient magnitude gives true sensitivity.
    The sign gives direction: positive = increasing θ helps.

    Parameters
    ----------
    controller : E0Controller
        The controller whose parameters are perturbed.
    start : str
        Start state for each probe run.
    goal : str, optional
        Goal state.
    max_cycles : int
        Max cycles per probe run.
    epsilon_frac : float
        Perturbation as fraction of parameter range (default 5%).
    params : list of str, optional
        Subset of TUNABLE_PARAMS to probe. None = all.

    Returns
    -------
    List[ParameterSensitivity]
        Sorted by sensitivity descending, with empirical gradients.
    """
    param_names = params or list(TUNABLE_PARAMS.keys())
    results: List[ParameterSensitivity] = []

    for name in param_names:
        if name not in TUNABLE_PARAMS:
            continue
        if not hasattr(controller, name):
            continue

        lo, hi = TUNABLE_PARAMS[name]
        current = float(getattr(controller, name))
        param_range = hi - lo
        if param_range <= 0:
            continue

        eps = param_range * epsilon_frac

        # θ + ε (clamped to upper bound)
        val_plus = min(current + eps, hi)
        setattr(controller, name, val_plus)
        q_plus, _ = _run_and_score(controller, start, goal, max_cycles)

        # θ − ε (clamped to lower bound)
        val_minus = max(current - eps, lo)
        setattr(controller, name, val_minus)
        q_minus, _ = _run_and_score(controller, start, goal, max_cycles)

        # Restore
        setattr(controller, name, current)

        # Central difference
        denom = val_plus - val_minus
        if abs(denom) < 1e-12:
            gradient = 0.0
        else:
            gradient = (q_plus - q_minus) / denom

        # Normalise gradient to [0, 1] sensitivity
        # Scale by param_range so sensitivity is dimensionless
        raw_sens = abs(gradient) * param_range
        sens = min(max(raw_sens, 0.0), 1.0)

        # Direction from sign of gradient
        if abs(gradient) < 1e-8:
            direction = "stable"
        elif gradient > 0:
            direction = "increase"
        else:
            direction = "decrease"

        results.append(ParameterSensitivity(
            name=name,
            current_value=current,
            sensitivity=sens,
            suggested_direction=direction,
            bounds=(lo, hi),
        ))

    results.sort(key=lambda p: p.sensitivity, reverse=True)
    return results


def propose_tuning_empirical(
    controller,
    start: str,
    goal: Optional[str] = None,
    max_cycles: int = 50,
    param_history: Optional[Dict[str, List[float]]] = None,
    step_fraction: float = _STEP_FRACTION,
    epsilon_frac: float = _DEFAULT_EPSILON_FRAC,
) -> MetaTuningResult:
    """Like propose_tuning but uses empirical sensitivity (B4.4).

    Performs 2·|params| probe runs to compute true ∂Q/∂θ,
    then generates bounded proposals using the same oscillation
    protection as the heuristic variant.
    """
    # Run baseline to get field summary
    q_base, fs = _run_and_score(controller, start, goal, max_cycles)
    thresholds = derive_thresholds(fs)

    # Get empirical sensitivities
    sensitivities = perturbation_sensitivity(
        controller, start, goal=goal,
        max_cycles=max_cycles,
        epsilon_frac=epsilon_frac,
    )

    if param_history is None:
        param_history = {}

    controller_params = _extract_controller_params(controller)
    proposals: List[TuningProposal] = []

    for ps in sensitivities:
        if ps.sensitivity < 0.05 or ps.suggested_direction == "stable":
            continue

        # H_meta: oscillation check
        history = param_history.get(ps.name, [])
        if _would_oscillate(history, ps.suggested_direction):
            continue

        current = ps.current_value
        lo, hi = ps.bounds
        param_range = hi - lo
        max_step = param_range * step_fraction * ps.sensitivity

        if ps.suggested_direction == "increase":
            new_val = min(current + max_step, hi)
            reason = f"∂Q/∂{ps.name}={ps.sensitivity:.3f} → increase {ps.name}"
        else:
            new_val = max(current - max_step, lo)
            reason = f"∂Q/∂{ps.name}={ps.sensitivity:.3f} → decrease {ps.name}"

        if abs(new_val - current) < 1e-10:
            continue

        proposals.append(TuningProposal(
            parameter=ps.name,
            old_value=current,
            new_value=new_val,
            sensitivity=ps.sensitivity,
            reason=reason,
        ))

        new_history = list(history) + [new_val]
        if len(new_history) > _PARAM_HISTORY_WINDOW:
            new_history = new_history[-_PARAM_HISTORY_WINDOW:]
        param_history[ps.name] = new_history

    return MetaTuningResult(
        field_summary=fs,
        derived_thresholds=thresholds,
        sensitivities=sensitivities,
        proposals=proposals,
        meta_historization=dict(param_history),
    )
