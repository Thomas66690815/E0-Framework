"""C150/C155 — Parameter Sensitivity + Auto-Tuning
===================================================

The Self-Graph evaluates parameter choices.  Given a landscape and
multiple E0Config variants, the system runs each config independently
and compares Self-Graph diagnoses to identify which parameters
matter most and which values produce the healthiest system.

Core mechanism (C150):
  1. run_trial()              – execute controller with a specific config,
                                return Self-Graph metrics alongside RunTrace
  2. sensitivity_analysis()   – compare trials across configs
  3. suggest_perturbations()  – given a diagnosis, propose parameter
                                variants worth testing (exploratory,
                                not prescriptive)

Adaptive control (C155):
  4. auto_tune()              – closed loop: baseline → diagnose → perturb
                                → evaluate → adopt best; repeats until
                                healthy or budget exhausted
  5. apply_config()           – update a running controller's parameters
                                from an E0Config without reconstruction

Usage::

    from e0_controller.parameter_sensitivity import (
        run_trial, sensitivity_analysis, suggest_perturbations,
        auto_tune, apply_config,
    )
    from e0_controller.config import E0Config, DEFAULTS

    # Manual analysis (C150):
    baseline = run_trial(landscape, exec_fn, "S")
    variants = suggest_perturbations(baseline.diagnosis)
    report  = sensitivity_analysis(
        landscape, exec_fn, "S", None,
        configs=[DEFAULTS] + variants,
    )
    print(report.summary())

    # Automatic tuning (C155):
    result = auto_tune(landscape, exec_fn, "S", goal="G")
    if result.improved:
        apply_config(controller, result.best_config)
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from typing import Dict, List, Optional, Set

from .config import E0Config, DEFAULTS
from .controller import E0Controller, RunTrace
from .dual_reflection import SelfGraphDiagnosis, diagnose_self_graph
from .landscape import Landscape
from .self_graph import ALL_COMPONENTS, SelfGraph

# ══════════════════════════════════════════════════════════
# Component → parameter mapping
# Only parameters that run_trial can actually vary are listed.
# ══════════════════════════════════════════════════════════

COMPONENT_PARAMS: Dict[str, List[str]] = {
    "amplitude":        ["hybrid_mode", "confidence_threshold", "hybrid_horizon"],
    "born":             ["hybrid_mode", "use_su2", "hybrid_horizon"],
    "realization":      [],
    "historization":    ["rho", "lambda_s", "lambda_f", "delta_max"],
    "inertia":          [],
    "transition_field": ["alpha", "recent_k", "overload_threshold"],
    "curvature":        [],
    "overlap":          [],
}

# ══════════════════════════════════════════════════════════
# Trial result
# ══════════════════════════════════════════════════════════

@dataclass
class TrialResult:
    """Outcome of running the controller with a specific E0Config."""

    config: E0Config
    trace: RunTrace
    diagnosis: Optional[SelfGraphDiagnosis]
    component_qualities: Dict[str, float]

    @property
    def healthy_count(self) -> int:
        return len(self.diagnosis.healthy) if self.diagnosis else 0

    @property
    def harmful_count(self) -> int:
        return len(self.diagnosis.harmful) if self.diagnosis else 0

    @property
    def confused_count(self) -> int:
        return len(self.diagnosis.confused) if self.diagnosis else 0

    @property
    def quality_score(self) -> float:
        """Sum of component qualities.  Higher is better."""
        if not self.component_qualities:
            return 0.0
        return sum(self.component_qualities.values())

    @property
    def health_score(self) -> float:
        """+1 per healthy, −2 per harmful, −1 per confused."""
        if not self.diagnosis:
            return 0.0
        return (
            len(self.diagnosis.healthy)
            - 2 * len(self.diagnosis.harmful)
            - len(self.diagnosis.confused)
        )

# ══════════════════════════════════════════════════════════
# Sensitivity report
# ══════════════════════════════════════════════════════════

@dataclass
class SensitivityReport:
    """Comparison of multiple config trials."""

    trials: List[TrialResult]

    @property
    def best_trial(self) -> TrialResult:
        return max(self.trials, key=lambda t: t.quality_score)

    @property
    def worst_trial(self) -> TrialResult:
        return min(self.trials, key=lambda t: t.quality_score)

    def parameter_impact(self) -> Dict[str, float]:
        """Which varying parameters correlate most with quality changes?

        Returns {param_name: impact} sorted by impact descending.
        Only parameters that actually differ across trial configs appear.
        """
        if len(self.trials) < 2:
            return {}

        impact: Dict[str, float] = {}
        for f in E0Config.__dataclass_fields__:
            values = [getattr(t.config, f) for t in self.trials]
            if len(set(str(v) for v in values)) <= 1:
                continue
            groups: Dict[str, List[float]] = {}
            for trial, val in zip(self.trials, values):
                key = str(val)
                groups.setdefault(key, []).append(trial.quality_score)
            group_means = [sum(qs) / len(qs) for qs in groups.values()]
            if len(group_means) >= 2:
                impact[f] = max(group_means) - min(group_means)
        return dict(sorted(impact.items(), key=lambda x: x[1], reverse=True))

    def summary(self) -> str:
        lines = [f"Sensitivity Report: {len(self.trials)} trials"]
        for i, t in enumerate(self.trials):
            mod = t.config.summary()
            label = (
                "DEFAULTS"
                if "all defaults" in mod
                else mod.replace("E0Config (modified):\n", "").strip()
            )
            lines.append(
                f"  Trial {i}: quality={t.quality_score:+.3f}, "
                f"healthy={t.healthy_count}, harmful={t.harmful_count}, "
                f"confused={t.confused_count} [{label}]"
            )
        best = self.best_trial
        lines.append(f"  Best: quality_score={best.quality_score:+.3f}")
        impact = self.parameter_impact()
        if impact:
            top = list(impact.items())[:5]
            lines.append(
                "  Top impact: "
                + ", ".join(f"{k}={v:.3f}" for k, v in top)
            )
        return "\n".join(lines)

# ══════════════════════════════════════════════════════════
# Run trial
# ══════════════════════════════════════════════════════════

def run_trial(
    landscape: Landscape,
    execute_fn,
    start: str,
    goal: Optional[str] = None,
    config: E0Config = DEFAULTS,
    max_cycles: int = 50,
) -> TrialResult:
    """Execute a controller run with *config* and collect Self-Graph metrics.

    Deep-copies *landscape* so that every trial is independent.
    """
    L = copy.deepcopy(landscape)

    # Apply historization parameters from config
    L.historization.rho = config.rho
    L.historization.lambda_s = config.lambda_s
    L.historization.lambda_f = config.lambda_f
    L.historization.delta_max = config.delta_max

    ctrl = E0Controller(
        L,
        execute_fn,
        alpha=config.alpha,
        recent_k=config.recent_k,
        max_escalation_R=config.max_escalation_R,
        overload_threshold=config.overload_threshold,
        confidence_threshold=config.confidence_threshold,
        hybrid_mode=config.hybrid_mode,
        hybrid_horizon=config.hybrid_horizon,
        use_su2=config.use_su2,
    )

    sg = SelfGraph()
    ctrl.self_graph = sg

    trace = ctrl.run(start, max_cycles=max_cycles, goal=goal)

    diag = diagnose_self_graph(sg)

    comp_q: Dict[str, float] = {}
    for comp in ALL_COMPONENTS:
        if sg.component_load(comp) > 0:
            comp_q[comp] = sg.component_quality(comp)

    return TrialResult(
        config=config,
        trace=trace,
        diagnosis=diag,
        component_qualities=comp_q,
    )

# ══════════════════════════════════════════════════════════
# Sensitivity analysis
# ══════════════════════════════════════════════════════════

def sensitivity_analysis(
    landscape: Landscape,
    execute_fn,
    start: str,
    goal: Optional[str],
    configs: List[E0Config],
    max_cycles: int = 50,
) -> SensitivityReport:
    """Run trials with multiple configs and compare Self-Graph outcomes."""
    trials = [
        run_trial(landscape, execute_fn, start, goal, cfg, max_cycles)
        for cfg in configs
    ]
    return SensitivityReport(trials=trials)

# ══════════════════════════════════════════════════════════
# Perturbation suggestions
# ══════════════════════════════════════════════════════════

def suggest_perturbations(
    diagnosis: Optional[SelfGraphDiagnosis],
    base_config: E0Config = DEFAULTS,
    perturbation_factor: float = 0.2,
) -> List[E0Config]:
    """Propose config variants for harmful / confused components.

    For each problematic Self-Graph component, identifies related
    parameters (via COMPONENT_PARAMS) and generates ± perturbation
    variants.  Returns an empty list when the diagnosis is healthy.

    This function is *exploratory* — it proposes hypotheses, not
    prescriptions.  Feed the returned configs into
    ``sensitivity_analysis`` to evaluate them.
    """
    if diagnosis is None:
        return []

    problematic: Set[str] = set(diagnosis.harmful) | set(diagnosis.confused)
    if not problematic:
        return []

    params: Set[str] = set()
    for comp in problematic:
        params.update(COMPONENT_PARAMS.get(comp, []))
    if not params:
        return []

    variants: List[E0Config] = []
    for param in sorted(params):
        base_val = getattr(base_config, param)

        if not isinstance(base_val, (int, float)):
            continue
        if isinstance(base_val, float) and (
            base_val == float("inf") or base_val != base_val
        ):
            continue

        if isinstance(base_val, int):
            delta = max(1, int(base_val * perturbation_factor))
            up = replace(base_config, **{param: base_val + delta})
            down = replace(base_config, **{param: max(1, base_val - delta)})
        else:
            delta = 0.1 if base_val == 0.0 else abs(base_val) * perturbation_factor
            up = replace(base_config, **{param: round(base_val + delta, 4)})
            down = replace(
                base_config,
                **{param: round(max(0.01, base_val - delta), 4)},
            )

        variants.extend([up, down])

    return variants


# ══════════════════════════════════════════════════════════
# Auto-tuning (C155)
# ══════════════════════════════════════════════════════════

@dataclass
class AutoTuneRound:
    """One round of the auto-tuning loop."""

    round_nr: int
    baseline: TrialResult
    report: SensitivityReport
    adopted_config: E0Config
    improvement: float  # quality_score delta vs round baseline


@dataclass
class AutoTuneResult:
    """Full outcome of auto_tune()."""

    rounds: List[AutoTuneRound]
    initial_config: E0Config
    best_config: E0Config
    initial_quality: float
    final_quality: float

    @property
    def improved(self) -> bool:
        return self.final_quality > self.initial_quality

    @property
    def improvement(self) -> float:
        return self.final_quality - self.initial_quality

    @property
    def total_trials(self) -> int:
        return sum(len(r.report.trials) for r in self.rounds)

    @property
    def configs_tried(self) -> int:
        return self.total_trials

    def summary(self) -> str:
        lines = [
            f"AutoTune: {len(self.rounds)} round(s), "
            f"{self.total_trials} trials",
            f"  Initial quality: {self.initial_quality:+.3f}",
            f"  Final quality:   {self.final_quality:+.3f}",
            f"  Improvement:     {self.improvement:+.3f}",
        ]
        if self.improved:
            diff = self.best_config.summary()
            if "all defaults" not in diff:
                lines.append(f"  Best config: {diff}")
        for r in self.rounds:
            lines.append(
                f"  Round {r.round_nr}: "
                f"baseline={r.baseline.quality_score:+.3f}, "
                f"best={r.report.best_trial.quality_score:+.3f}, "
                f"Δ={r.improvement:+.3f}"
            )
        return "\n".join(lines)


def auto_tune(
    landscape: Landscape,
    execute_fn,
    start: str,
    goal: Optional[str] = None,
    *,
    base_config: E0Config = DEFAULTS,
    max_cycles: int = 50,
    max_rounds: int = 3,
    perturbation_factor: float = 0.2,
    min_improvement: float = 0.01,
) -> AutoTuneResult:
    """Closed-loop parameter tuning via Self-Graph diagnosis (C155).

    Each round:
    1. Run baseline trial with current config
    2. Diagnose Self-Graph (harmful/confused components)
    3. Generate perturbation variants for problematic parameters
    4. Run sensitivity analysis across all variants
    5. Adopt best config if it improves on baseline
    6. Repeat until healthy, no improvement, or budget exhausted

    Args:
        landscape: Domain landscape (deep-copied per trial).
        execute_fn: Transition execution function.
        start: Start state for each trial.
        goal: Goal state (optional).
        base_config: Initial configuration (default: DEFAULTS).
        max_cycles: Controller cycles per trial.
        max_rounds: Maximum tuning rounds.
        perturbation_factor: Magnitude of parameter perturbations.
        min_improvement: Minimum quality improvement to adopt a new config.

    Returns:
        AutoTuneResult with best config, improvement data, and full history.
    """
    current_config = base_config
    initial_quality: Optional[float] = None
    rounds: List[AutoTuneRound] = []

    for round_nr in range(1, max_rounds + 1):
        # 1. Baseline trial
        baseline = run_trial(
            landscape, execute_fn, start, goal, current_config, max_cycles,
        )

        if initial_quality is None:
            initial_quality = baseline.quality_score

        # 2. Check if already healthy (no harmful or confused)
        if (baseline.diagnosis is not None
                and not baseline.diagnosis.harmful
                and not baseline.diagnosis.confused):
            rounds.append(AutoTuneRound(
                round_nr=round_nr,
                baseline=baseline,
                report=SensitivityReport(trials=[baseline]),
                adopted_config=current_config,
                improvement=0.0,
            ))
            break

        # 3. Generate perturbation variants
        variants = suggest_perturbations(
            baseline.diagnosis, current_config, perturbation_factor,
        )
        if not variants:
            rounds.append(AutoTuneRound(
                round_nr=round_nr,
                baseline=baseline,
                report=SensitivityReport(trials=[baseline]),
                adopted_config=current_config,
                improvement=0.0,
            ))
            break

        # 4. Run sensitivity analysis (baseline + variants)
        report = sensitivity_analysis(
            landscape, execute_fn, start, goal,
            configs=[current_config] + variants,
            max_cycles=max_cycles,
        )

        # 5. Adopt best if it improves
        best = report.best_trial
        improvement = best.quality_score - baseline.quality_score

        if improvement >= min_improvement:
            adopted = best.config
        else:
            adopted = current_config
            improvement = 0.0

        rounds.append(AutoTuneRound(
            round_nr=round_nr,
            baseline=baseline,
            report=report,
            adopted_config=adopted,
            improvement=improvement,
        ))

        current_config = adopted

        # 6. Stop if no improvement this round
        if improvement < min_improvement:
            break

    final_quality = rounds[-1].report.best_trial.quality_score
    return AutoTuneResult(
        rounds=rounds,
        initial_config=base_config,
        best_config=current_config,
        initial_quality=initial_quality or 0.0,
        final_quality=final_quality,
    )


def apply_config(controller: E0Controller, config: E0Config) -> None:
    """Update a running controller's parameters from an E0Config (C155).

    Modifies the controller's fields in-place — no reconstruction needed.
    Also updates the controller's landscape historization parameters.
    """
    from .controller import HybridMode

    controller.alpha = config.alpha
    controller.recent_k = config.recent_k
    controller.max_escalation_R = config.max_escalation_R
    controller.overload_threshold = config.overload_threshold
    controller.confidence_threshold = config.confidence_threshold
    mode = config.hybrid_mode
    if isinstance(mode, str):
        mode = HybridMode(mode.lower())
    controller.hybrid_mode = mode
    controller.hybrid_horizon = config.hybrid_horizon
    controller.use_su2 = config.use_su2

    L = controller.landscape
    L.historization.rho = config.rho
    L.historization.lambda_s = config.lambda_s
    L.historization.lambda_f = config.lambda_f
    L.historization.delta_max = config.delta_max
