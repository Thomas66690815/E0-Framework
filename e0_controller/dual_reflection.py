"""
E₀ Dual Reflection — Domain + Self-Graph Reflection (C47)
==========================================================
Extends the Reflection Layer (Phase 3g) with self-graph diagnosis.

After every controller cycle, C43 already updates the self-graph with
component-level outcomes.  C47 harvests that data: which components
are effective, which are confused, and which should be deactivated.

Three outputs:
  1. Domain reflection — standard ReflectionReport (existing)
  2. Self-graph diagnosis — component health assessment (new)
  3. Meta-actions — deactivation / investigation recommendations (new)

Meta-control principle (from Architecture §6 Level 3):
  If a modulation component (curvature, overlap) shows persistently
  negative quality despite sufficient trace load, recommend disabling
  it.  Core components cannot be disabled, but are flagged for
  investigation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .reflection import (
    ReflectionReport,
    ReflectionCallFn,
    reflect,
    should_reflect,
)
from .self_graph import SelfGraph, CORE_COMPONENTS, MODULATION_COMPONENTS, ALL_COMPONENTS
from .llm_adapter import LLMConfig


# ──────────────────────────────────────────────
# 1. Thresholds
# ──────────────────────────────────────────────

# Minimum trace load before judging a component
LOAD_MIN_THRESHOLD = 3.0

# |quality| below this (with sufficient load) → confused
QUALITY_CONFUSED_THRESHOLD = 0.1

# Negative quality below this → actively harmful
QUALITY_HARMFUL_THRESHOLD = -0.2

# Inertia below this → contradictory history
INERTIA_WARN_THRESHOLD = 0.3


# ──────────────────────────────────────────────
# 2. Component Assessment
# ──────────────────────────────────────────────

@dataclass
class ComponentAssessment:
    """Health assessment for a single E0 component."""
    name: str
    load: float
    quality: float
    inertia: float
    status: str            # "healthy" | "confused" | "harmful" | "insufficient_data"
    is_modulation: bool    # True for curvature/overlap (can be disabled)


@dataclass
class SelfGraphDiagnosis:
    """Complete self-graph health assessment."""
    components: List[ComponentAssessment] = field(default_factory=list)
    healthy: List[str] = field(default_factory=list)
    confused: List[str] = field(default_factory=list)
    harmful: List[str] = field(default_factory=list)
    insufficient_data: List[str] = field(default_factory=list)
    deactivation_candidates: List[str] = field(default_factory=list)  # modulation only
    meta_actions: List[str] = field(default_factory=list)


def _assess_component(
    name: str,
    sg: SelfGraph,
    *,
    load_min: float = LOAD_MIN_THRESHOLD,
    quality_confused: float = QUALITY_CONFUSED_THRESHOLD,
    quality_harmful: float = QUALITY_HARMFUL_THRESHOLD,
    inertia_warn: float = INERTIA_WARN_THRESHOLD,
) -> ComponentAssessment:
    """Assess a single component's health from self-graph metrics."""
    load = sg.component_load(name)
    quality = sg.component_quality(name)
    inertia = sg.component_inertia(name)
    is_mod = name in MODULATION_COMPONENTS

    if load < load_min:
        status = "insufficient_data"
    elif quality < quality_harmful:
        status = "harmful"
    elif abs(quality) < quality_confused:
        status = "confused"
    else:
        status = "healthy"

    return ComponentAssessment(
        name=name,
        load=load,
        quality=quality,
        inertia=inertia,
        status=status,
        is_modulation=is_mod,
    )


def diagnose_self_graph(
    sg: SelfGraph,
    *,
    load_min: float = LOAD_MIN_THRESHOLD,
    quality_confused: float = QUALITY_CONFUSED_THRESHOLD,
    quality_harmful: float = QUALITY_HARMFUL_THRESHOLD,
    inertia_warn: float = INERTIA_WARN_THRESHOLD,
) -> SelfGraphDiagnosis:
    """Analyze the self-graph and return a component health diagnosis.

    Classifies each component as:
      - healthy: positive quality, sufficient data
      - confused: |quality| ≈ 0 despite sufficient load (mixed outcomes)
      - harmful: negative quality — component actively hurts decisions
      - insufficient_data: not enough traces yet

    Modulation components (curvature, overlap) that are harmful become
    deactivation candidates.
    """
    diag = SelfGraphDiagnosis()
    for name in ALL_COMPONENTS:
        ca = _assess_component(
            name, sg,
            load_min=load_min,
            quality_confused=quality_confused,
            quality_harmful=quality_harmful,
            inertia_warn=inertia_warn,
        )
        diag.components.append(ca)

        if ca.status == "healthy":
            diag.healthy.append(name)
        elif ca.status == "confused":
            diag.confused.append(name)
        elif ca.status == "harmful":
            diag.harmful.append(name)
        else:
            diag.insufficient_data.append(name)

        # Deactivation: only modulation components
        if ca.is_modulation and ca.status == "harmful":
            diag.deactivation_candidates.append(name)

    # Build meta-actions
    if diag.deactivation_candidates:
        for comp in diag.deactivation_candidates:
            ca = next(c for c in diag.components if c.name == comp)
            diag.meta_actions.append(
                f"Disable {comp} modulation "
                f"(quality={ca.quality:+.3f}, load={ca.load:.1f})"
            )

    if diag.confused:
        for comp in diag.confused:
            ca = next(c for c in diag.components if c.name == comp)
            diag.meta_actions.append(
                f"Investigate {comp}: contradictory outcomes "
                f"(quality={ca.quality:+.3f}, load={ca.load:.1f})"
            )

    for ca in diag.components:
        if ca.load >= load_min and ca.inertia < inertia_warn:
            diag.meta_actions.append(
                f"Warning: {ca.name} has very low inertia "
                f"({ca.inertia:.3f}) — inconsistent history"
            )

    if not diag.harmful and not diag.confused and diag.healthy:
        diag.meta_actions.append("All assessed components are healthy")

    return diag


# ──────────────────────────────────────────────
# 3. Dual Reflection Report
# ──────────────────────────────────────────────

@dataclass
class DualReflectionReport:
    """Combined domain + self-graph reflection.

    Attributes:
        domain_report: Standard ReflectionReport (None if not triggered)
        self_diagnosis: Self-graph component health assessment
        meta_actions: Synthesized meta-level recommendations
        mode_info: Optional mode controller summary (from C46)
    """
    domain_report: Optional[ReflectionReport]
    self_diagnosis: SelfGraphDiagnosis
    meta_actions: List[str] = field(default_factory=list)
    mode_info: Optional[Dict[str, object]] = None


def _cross_reference(
    domain: Optional[ReflectionReport],
    diag: SelfGraphDiagnosis,
) -> List[str]:
    """Derive meta-actions from cross-referencing domain and self issues."""
    actions: List[str] = list(diag.meta_actions)

    if domain is None:
        return actions

    # If domain says "controller" is a problem layer AND self-graph
    # shows harmful/confused core components → targeted diagnosis
    controller_flagged = "controller" in domain.likely_layers
    graph_flagged = "graph_design" in domain.likely_layers

    if controller_flagged:
        for comp in ("amplitude", "born", "realization"):
            ca = next((c for c in diag.components if c.name == comp), None)
            if ca and ca.status in ("harmful", "confused"):
                actions.append(
                    f"Domain flags controller issues + {comp} is {ca.status} "
                    f"— prioritize {comp} investigation"
                )

    if graph_flagged:
        for comp in ("transition_field", "historization"):
            ca = next((c for c in diag.components if c.name == comp), None)
            if ca and ca.status in ("harmful", "confused"):
                actions.append(
                    f"Domain flags graph issues + {comp} is {ca.status} "
                    f"— structural review needed"
                )

    # If domain suggests structural mutation AND modulation is harmful
    # → deactivate before mutating
    structural_action = any(
        "restructur" in a.lower() or "rebuild" in a.lower()
        for a in domain.recommended_actions
    )
    if structural_action and diag.deactivation_candidates:
        actions.append(
            f"Deactivate {', '.join(diag.deactivation_candidates)} "
            f"before restructuring landscape"
        )

    return actions


# ──────────────────────────────────────────────
# 4. Main Entry Point
# ──────────────────────────────────────────────

def reflect_dual(
    ev: Any,
    self_graph: SelfGraph,
    *,
    call_fn: Optional[ReflectionCallFn] = None,
    config: Optional[LLMConfig] = None,
    result_log: Optional[list] = None,
    tuning_memory: Optional[Any] = None,
    landscape: Optional[Any] = None,
    mode_summary: Optional[Dict[str, object]] = None,
) -> DualReflectionReport:
    """Run dual reflection: domain + self-graph diagnosis.

    Combines standard `reflect()` for the domain evaluation with
    `diagnose_self_graph()` for component health, then cross-references
    them for targeted meta-actions.

    Parameters:
        ev: ScenarioEvaluation for domain reflection
        self_graph: SelfGraph instance with accumulated traces
        call_fn: Optional LLM call function for domain reflection
        config: Optional LLM config for domain reflection
        result_log: Optional transition result log
        tuning_memory: Optional TuningMemory for structural triggers
        landscape: Optional Landscape for structural analysis
        mode_summary: Optional mode controller summary dict (from C46)

    Returns:
        DualReflectionReport with domain report, self-diagnosis, and meta-actions
    """
    # 1. Domain reflection (existing system)
    domain_report = reflect(
        ev,
        call_fn=call_fn,
        config=config,
        result_log=result_log,
        tuning_memory=tuning_memory,
        landscape=landscape,
    )

    # 2. Self-graph diagnosis
    self_diag = diagnose_self_graph(self_graph)

    # 3. Cross-reference for meta-actions
    meta = _cross_reference(domain_report, self_diag)

    return DualReflectionReport(
        domain_report=domain_report,
        self_diagnosis=self_diag,
        meta_actions=meta,
        mode_info=mode_summary,
    )


# ──────────────────────────────────────────────
# 5. Formatting
# ──────────────────────────────────────────────

def format_dual_report(report: DualReflectionReport) -> str:
    """Format a DualReflectionReport as human-readable text."""
    lines: List[str] = []
    lines.append("")
    lines.append("=" * 78)
    lines.append("E₀ Dual Reflection Report (C47)")
    lines.append("=" * 78)

    # Mode info
    if report.mode_info:
        lines.append("")
        lines.append(f"Operating Mode: {report.mode_info.get('mode', '?')}")
        lines.append(
            f"  Coverage: {report.mode_info.get('explored', '?')}/"
            f"{report.mode_info.get('total', '?')} edges explored "
            f"({report.mode_info.get('ratio', 0):.0%})"
        )

    # Domain reflection
    lines.append("")
    lines.append("─" * 78)
    lines.append("Domain Reflection:")
    lines.append("─" * 78)
    if report.domain_report:
        r = report.domain_report
        lines.append(f"  Type: {r.reflection_type}")
        if r.observed_patterns:
            lines.append("  Patterns:")
            for p in r.observed_patterns:
                lines.append(f"    • {p}")
        if r.likely_layers:
            lines.append(f"  Layers: {', '.join(r.likely_layers)}")
        if r.recommended_actions:
            lines.append("  Actions:")
            for a in r.recommended_actions:
                lines.append(f"    ▸ {a}")
        if r.preservations:
            lines.append("  Preserve:")
            for p in r.preservations:
                lines.append(f"    ★ {p}")
    else:
        lines.append("  No domain reflection triggered.")

    # Self-graph diagnosis
    lines.append("")
    lines.append("─" * 78)
    lines.append("Self-Graph Diagnosis:")
    lines.append("─" * 78)
    d = report.self_diagnosis
    for ca in d.components:
        icon = {"healthy": "✓", "confused": "?", "harmful": "✗",
                "insufficient_data": "·"}.get(ca.status, " ")
        mod_tag = " [mod]" if ca.is_modulation else ""
        lines.append(
            f"  {icon} {ca.name:20s}  load={ca.load:.1f}  "
            f"quality={ca.quality:+.3f}  inertia={ca.inertia:.3f}"
            f"  [{ca.status}]{mod_tag}"
        )

    if d.deactivation_candidates:
        lines.append("")
        lines.append(f"  Deactivation candidates: {', '.join(d.deactivation_candidates)}")

    # Meta-actions
    lines.append("")
    lines.append("─" * 78)
    lines.append("Meta-Actions:")
    lines.append("─" * 78)
    if report.meta_actions:
        for a in report.meta_actions:
            lines.append(f"  ► {a}")
    else:
        lines.append("  No meta-actions.")

    lines.append("=" * 78)
    return "\n".join(lines)
