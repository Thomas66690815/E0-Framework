"""C150 — Parameter Sensitivity via Self-Graph Attribution
==========================================================

The Self-Graph evaluates parameter choices.  Given a landscape and
multiple E0Config variants, the system runs each config independently
and compares Self-Graph diagnoses to identify which parameters
matter most and which values produce the healthiest system.

This is the evaluation infrastructure, not adaptive control.
The system does not automatically adopt better parameters — it
provides the data for an informed human or automated decision.

Core mechanism:
  1. run_trial()              – execute controller with a specific config,
                                return Self-Graph metrics alongside RunTrace
  2. sensitivity_analysis()   – compare trials across configs
  3. suggest_perturbations()  – given a diagnosis, propose parameter
                                variants worth testing (exploratory,
                                not prescriptive)

Usage::

    from e0_controller.parameter_sensitivity import (
        run_trial, sensitivity_analysis, suggest_perturbations,
    )
    from e0_controller.config import E0Config, DEFAULTS

    baseline = run_trial(landscape, exec_fn, "S")
    variants = suggest_perturbations(baseline.diagnosis)
    report  = sensitivity_analysis(
        landscape, exec_fn, "S", None,
        configs=[DEFAULTS] + variants,
    )
    print(report.summary())
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
    "amplitude":        [],
    "born":             [],
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
