"""
E₀ Self-Tuning Layer (B4.1)
==============================
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
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


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
