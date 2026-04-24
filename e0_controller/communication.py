"""
E₀ Communication Intent (C159)
================================
Detects what E0 wants to communicate to a human peer.

Intent detection reads E0's internal state — Self-Graph health,
controller step results, and dream equivalences — and produces a
list of CommunicationIntents. Each intent carries a type, urgency,
subject, and the raw evidence that triggered it.

This is Layer 2 of the Human Communication architecture
(docs/E0_HUMAN_COMMUNICATION_DESIGN_v1.md §2).

Intent types:
  - uncertainty:  a component is confused or has contradictory history
  - decision:     a transition was chosen among alternatives
  - pattern:      trace_load is growing on a specific path
  - request:      E0 cannot proceed without external input
  - status:       periodic summary of current state
  - anomaly:      unexpected cross-domain equivalence in dream

See docs/E0_HUMAN_COMMUNICATION_DESIGN_v1.md §2 Layer 2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .self_graph import SelfGraph
from .dual_reflection import (
    SelfGraphDiagnosis,
    diagnose_self_graph,
)
from .primitives import Edge


# ──────────────────────────────────────────────
# 1. Intent Types
# ──────────────────────────────────────────────

class IntentType(Enum):
    """Classification of communication intents."""
    UNCERTAINTY = "uncertainty"
    DECISION = "decision"
    PATTERN = "pattern"
    REQUEST = "request"
    STATUS = "status"
    ANOMALY = "anomaly"


# ──────────────────────────────────────────────
# 2. Communication Intent
# ──────────────────────────────────────────────

@dataclass(frozen=True)
class CommunicationIntent:
    """A single thing E0 wants to communicate.

    Attributes:
        type: What kind of intent this is.
        urgency: 0.0 = informational, 1.0 = critical.
        subject: What this is about (component name, edge, domain).
        summary: One-line human-readable description.
        evidence: Raw data supporting this intent.
    """
    type: IntentType
    urgency: float
    subject: str
    summary: str
    evidence: Dict[str, Any] = field(default_factory=dict)


# ──────────────────────────────────────────────
# 3. Intent Detection from Self-Graph
# ──────────────────────────────────────────────

def detect_self_graph_intents(
    sg: SelfGraph,
    *,
    diagnosis: Optional[SelfGraphDiagnosis] = None,
) -> List[CommunicationIntent]:
    """Detect communication intents from Self-Graph health.

    Produces:
      - UNCERTAINTY for confused components
      - UNCERTAINTY (high urgency) for harmful components
      - REQUEST for insufficient-data components

    Args:
        sg: The controller's Self-Graph.
        diagnosis: Pre-computed diagnosis. If None, computed fresh.

    Returns:
        List of intents, sorted by urgency descending.
    """
    if diagnosis is None:
        diagnosis = diagnose_self_graph(sg)

    intents: List[CommunicationIntent] = []

    for ca in diagnosis.components:
        if ca.status == "harmful":
            intents.append(CommunicationIntent(
                type=IntentType.UNCERTAINTY,
                urgency=min(1.0, 0.7 + abs(ca.quality) * 0.3),
                subject=ca.name,
                summary=(
                    f"Component '{ca.name}' is harmful "
                    f"(quality={ca.quality:+.3f}, load={ca.load:.1f})"
                ),
                evidence={
                    "status": ca.status,
                    "quality": ca.quality,
                    "load": ca.load,
                    "inertia": ca.inertia,
                    "is_modulation": ca.is_modulation,
                },
            ))
        elif ca.status == "confused":
            intents.append(CommunicationIntent(
                type=IntentType.UNCERTAINTY,
                urgency=0.4 + (1.0 - abs(ca.quality)) * 0.2,
                subject=ca.name,
                summary=(
                    f"Component '{ca.name}' has contradictory outcomes "
                    f"(quality={ca.quality:+.3f}, load={ca.load:.1f})"
                ),
                evidence={
                    "status": ca.status,
                    "quality": ca.quality,
                    "load": ca.load,
                    "inertia": ca.inertia,
                },
            ))
        elif ca.status == "insufficient_data":
            intents.append(CommunicationIntent(
                type=IntentType.REQUEST,
                urgency=0.3,
                subject=ca.name,
                summary=(
                    f"Component '{ca.name}' lacks data "
                    f"(load={ca.load:.1f})"
                ),
                evidence={
                    "status": ca.status,
                    "load": ca.load,
                },
            ))

    intents.sort(key=lambda i: i.urgency, reverse=True)
    return intents


# ──────────────────────────────────────────────
# 4. Intent Detection from Step Result
# ──────────────────────────────────────────────

def detect_step_intents(
    step_result: Any,
) -> List[CommunicationIntent]:
    """Detect communication intents from a controller StepResult.

    Produces:
      - DECISION when multiple candidates existed (choice was made)
      - UNCERTAINTY when escalation occurred
      - PATTERN when resistance dropped significantly (path is stabilizing)

    Args:
        step_result: A controller.StepResult object.

    Returns:
        List of intents.
    """
    intents: List[CommunicationIntent] = []

    # Decision: multiple candidates → a choice was made
    candidates = getattr(step_result, "candidates", [])
    if len(candidates) > 1:
        rejected = [c for c in candidates if c != step_result.target]
        intents.append(CommunicationIntent(
            type=IntentType.DECISION,
            urgency=min(1.0, 0.3 + len(rejected) * 0.1),
            subject=f"{step_result.source}→{step_result.target}",
            summary=(
                f"Chose '{step_result.target}' over {rejected} "
                f"from '{step_result.source}' "
                f"(S_eff={step_result.s_eff:.3f})"
            ),
            evidence={
                "source": step_result.source,
                "target": step_result.target,
                "rejected": rejected,
                "s_eff": step_result.s_eff,
                "outcome": step_result.outcome.value,
                "candidates": candidates,
            },
        ))

    # Escalation: E0 had to escape a dead-end or was overloaded
    if step_result.escalated:
        esc_type = getattr(step_result, "escalation_type", None)
        esc_name = esc_type.name if esc_type else "UNKNOWN"
        intents.append(CommunicationIntent(
            type=IntentType.UNCERTAINTY,
            urgency=0.7 if esc_name in ("DEAD_END", "EXHAUSTED") else 0.5,
            subject=f"escalation:{step_result.source}",
            summary=(
                f"Escalation at '{step_result.source}' "
                f"(type={esc_name})"
            ),
            evidence={
                "source": step_result.source,
                "escalation_type": esc_name,
                "target": step_result.target,
            },
        ))

    # Pattern: resistance dropped → path is stabilizing
    r_before = getattr(step_result, "r_eff_before", 0.0)
    r_after = getattr(step_result, "r_eff_after", 0.0)
    if r_before > 0 and r_after < r_before * 0.7:
        drop_pct = (r_before - r_after) / r_before
        intents.append(CommunicationIntent(
            type=IntentType.PATTERN,
            urgency=min(1.0, 0.2 + drop_pct),
            subject=f"{step_result.source}→{step_result.target}",
            summary=(
                f"Path '{step_result.source}→{step_result.target}' "
                f"is stabilizing (R_eff dropped {drop_pct:.0%})"
            ),
            evidence={
                "r_eff_before": r_before,
                "r_eff_after": r_after,
                "drop_pct": drop_pct,
            },
        ))

    return intents


# ──────────────────────────────────────────────
# 5. Intent Detection from Dream Equivalences
# ──────────────────────────────────────────────

def detect_dream_intents(
    observer: Any,
    domain: str,
    *,
    anomaly_threshold: float = -0.3,
) -> List[CommunicationIntent]:
    """Detect communication intents from dream equivalences.

    Produces:
      - ANOMALY for equivalences with negative trace_quality
        (unexpected or broken cross-domain mapping)
      - PATTERN for strong positive equivalences

    Args:
        observer: A DreamObserver instance.
        domain: The domain to query equivalences for.
        anomaly_threshold: Quality below this = anomaly.

    Returns:
        List of intents.
    """
    intents: List[CommunicationIntent] = []

    eqs = observer.equivalences_for(domain)
    for eq in eqs:
        quality = eq["trace_quality"]
        if quality < anomaly_threshold:
            intents.append(CommunicationIntent(
                type=IntentType.ANOMALY,
                urgency=min(1.0, 0.5 + abs(quality) * 0.5),
                subject=f"{eq['own_state']}↔{eq['partner_state']}",
                summary=(
                    f"Broken equivalence: {eq['own_state']} ↔ "
                    f"{eq['partner_state']} "
                    f"(quality={quality:+.3f})"
                ),
                evidence=eq,
            ))
        elif quality > 0.5:
            intents.append(CommunicationIntent(
                type=IntentType.PATTERN,
                urgency=0.2 + quality * 0.2,
                subject=f"{eq['own_state']}↔{eq['partner_state']}",
                summary=(
                    f"Strong analogy: {eq['own_state']} ↔ "
                    f"{eq['partner_state']} "
                    f"(quality={quality:+.3f})"
                ),
                evidence=eq,
            ))

    return intents


# ──────────────────────────────────────────────
# 6. Status Intent (periodic summary)
# ──────────────────────────────────────────────

def detect_status_intent(
    sg: SelfGraph,
    *,
    diagnosis: Optional[SelfGraphDiagnosis] = None,
) -> CommunicationIntent:
    """Generate a periodic status intent summarizing E0's state.

    Always produces exactly one STATUS intent with a snapshot of
    component health counts.

    Args:
        sg: The controller's Self-Graph.
        diagnosis: Pre-computed diagnosis. If None, computed fresh.
    """
    if diagnosis is None:
        diagnosis = diagnose_self_graph(sg)

    n_healthy = len(diagnosis.healthy)
    n_confused = len(diagnosis.confused)
    n_harmful = len(diagnosis.harmful)
    n_insuf = len(diagnosis.insufficient_data)
    total = n_healthy + n_confused + n_harmful + n_insuf

    if n_harmful > 0:
        urgency = 0.6
    elif n_confused > 0:
        urgency = 0.3
    else:
        urgency = 0.1

    return CommunicationIntent(
        type=IntentType.STATUS,
        urgency=urgency,
        subject="self_graph",
        summary=(
            f"{n_healthy}/{total} healthy, "
            f"{n_confused} confused, "
            f"{n_harmful} harmful, "
            f"{n_insuf} insufficient data"
        ),
        evidence={
            "healthy": diagnosis.healthy,
            "confused": diagnosis.confused,
            "harmful": diagnosis.harmful,
            "insufficient_data": diagnosis.insufficient_data,
            "meta_actions": diagnosis.meta_actions,
        },
    )


# ──────────────────────────────────────────────
# 7. Task-Landscape Intents (C166)
# ──────────────────────────────────────────────

def detect_landscape_intents(
    landscape: Any,
    *,
    trace: Any = None,
    goal: Optional[str] = None,
    task_description: str = "",
) -> List[CommunicationIntent]:
    """Detect communication intents from the task landscape and run trace.

    This is what makes the UI task-aware: it reads the actual problem
    graph (states, edges, tensions) and the path E0 took through it.

    Produces:
      - STATUS with task overview (states, edges, path taken, goal status)
      - DECISION for high-tension edges in the path
      - PATTERN for stabilizing edges (high trace_load, positive quality)
      - UNCERTAINTY for edges with negative quality (repeated failure)
      - ANOMALY for dead-end states (no outgoing admissible neighbors)

    Args:
        landscape: The task Landscape.
        trace: Optional RunTrace from the last iteration.
        goal: Optional goal state name.
        task_description: Human-readable task description.
    """
    intents: List[CommunicationIntent] = []
    hist = landscape.historization

    # ── Task overview (STATUS) ────────────────────────
    path = trace.path if trace else []
    goal_reached = goal in path if goal else False
    metrics = trace.metrics() if trace else {}

    task_label = task_description[:80] if task_description else "Task"
    path_str = " → ".join(path) if path else "(no path)"

    intents.append(CommunicationIntent(
        type=IntentType.STATUS,
        urgency=0.8 if goal_reached else 0.5,
        subject="task_landscape",
        summary=(
            f"{task_label}: {len(landscape.states)} states, "
            f"{landscape.edge_count()} edges. "
            f"{'Goal REACHED' if goal_reached else 'Goal pending'}. "
            f"Path: {path_str}"
        ),
        evidence={
            "task": task_description,
            "states": sorted(landscape.states),
            "edge_count": landscape.edge_count(),
            "path": path,
            "goal": goal,
            "goal_reached": goal_reached,
            "steps": int(metrics.get("steps", 0)),
            "success_rate": metrics.get("success_rate", 0.0),
            "avg_tension": metrics.get("avg_tension", 0.0),
        },
    ))

    if not trace or not trace.steps:
        return intents

    # ── Per-edge analysis along the path ──────────────
    for step in trace.steps:
        edge = Edge(step.source, step.target)
        s_eff = step.s_eff
        quality = hist.trace_quality(edge)
        load = hist.trace_load(edge)

        # High-tension decision (hard transition)
        if s_eff > 0.5:
            intents.append(CommunicationIntent(
                type=IntentType.DECISION,
                urgency=min(1.0, 0.4 + s_eff * 0.4),
                subject=f"{step.source}→{step.target}",
                summary=(
                    f"High tension at {step.source} → {step.target} "
                    f"(S_eff={s_eff:.3f}, outcome={step.outcome.value})"
                ),
                evidence={
                    "source": step.source,
                    "target": step.target,
                    "s_eff": s_eff,
                    "outcome": step.outcome.value,
                    "quality": quality,
                    "load": load,
                    "candidates": getattr(step, "candidates", []),
                },
            ))

        # Negative quality (repeated failure on this edge)
        if quality < -0.2 and load > 2.0:
            intents.append(CommunicationIntent(
                type=IntentType.UNCERTAINTY,
                urgency=min(1.0, 0.5 + abs(quality) * 0.5),
                subject=f"{step.source}→{step.target}",
                summary=(
                    f"Struggling at {step.source} → {step.target} "
                    f"(quality={quality:+.3f}, load={load:.1f})"
                ),
                evidence={
                    "source": step.source,
                    "target": step.target,
                    "quality": quality,
                    "load": load,
                    "outcome": step.outcome.value,
                },
            ))

        # Stabilizing (high load + positive quality → learned)
        if quality > 0.3 and load > 3.0:
            intents.append(CommunicationIntent(
                type=IntentType.PATTERN,
                urgency=0.2 + quality * 0.2,
                subject=f"{step.source}→{step.target}",
                summary=(
                    f"Path {step.source} → {step.target} is stable "
                    f"(quality={quality:+.3f}, load={load:.1f})"
                ),
                evidence={
                    "source": step.source,
                    "target": step.target,
                    "quality": quality,
                    "load": load,
                },
            ))

    # ── Dead-end detection ────────────────────────────
    current_state = path[-1] if path else None
    if current_state and not goal_reached:
        neighbors = landscape.admissible_neighbors(current_state)
        if not neighbors:
            intents.append(CommunicationIntent(
                type=IntentType.REQUEST,
                urgency=0.9,
                subject=current_state,
                summary=(
                    f"Dead end at '{current_state}': "
                    f"no admissible transitions"
                ),
                evidence={
                    "state": current_state,
                    "admissible_neighbors": [],
                    "goal": goal,
                },
            ))

    intents.sort(key=lambda i: i.urgency, reverse=True)
    return intents


# ──────────────────────────────────────────────
# 8. Unified Detection
# ──────────────────────────────────────────────

@dataclass
class IntentReport:
    """Complete intent detection report from all sources."""
    intents: List[CommunicationIntent] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.intents)

    @property
    def max_urgency(self) -> float:
        if not self.intents:
            return 0.0
        return max(i.urgency for i in self.intents)

    def by_type(self, intent_type: IntentType) -> List[CommunicationIntent]:
        return [i for i in self.intents if i.type == intent_type]

    def above_urgency(self, threshold: float) -> List[CommunicationIntent]:
        return [i for i in self.intents if i.urgency >= threshold]

    def summary(self) -> str:
        """One-line summary of the report."""
        if not self.intents:
            return "No communication intents detected."
        by_type = {}
        for i in self.intents:
            by_type.setdefault(i.type.value, 0)
            by_type[i.type.value] += 1
        parts = [f"{v}× {k}" for k, v in sorted(by_type.items())]
        return (
            f"{self.count} intents (max urgency={self.max_urgency:.2f}): "
            + ", ".join(parts)
        )


def detect_intents(
    *,
    self_graph: Optional[SelfGraph] = None,
    step_result: Optional[Any] = None,
    dream_observer: Optional[Any] = None,
    dream_domain: Optional[str] = None,
    landscape: Optional[Any] = None,
    trace: Optional[Any] = None,
    goal: Optional[str] = None,
    task_description: str = "",
    include_status: bool = True,
    anomaly_threshold: float = -0.3,
) -> IntentReport:
    """Unified intent detection from all available E0 sources.

    Combines intents from Self-Graph health, controller step results,
    dream equivalences, and task landscape into a single sorted report.

    Args:
        self_graph: Optional Self-Graph for health-based intents.
        step_result: Optional StepResult for decision/escalation intents.
        dream_observer: Optional DreamObserver for equivalence intents.
        dream_domain: Domain name to query in the DreamObserver.
        landscape: Optional task Landscape for task-aware intents (C166).
        trace: Optional RunTrace from the last iteration (C166).
        goal: Optional goal state for goal-reaching detection (C166).
        task_description: Human-readable task description (C166).
        include_status: Whether to include a status intent.
        anomaly_threshold: Dream quality below this = anomaly.

    Returns:
        IntentReport with all detected intents, sorted by urgency.
    """
    all_intents: List[CommunicationIntent] = []
    diagnosis = None

    if self_graph is not None:
        diagnosis = diagnose_self_graph(self_graph)
        all_intents.extend(detect_self_graph_intents(
            self_graph, diagnosis=diagnosis,
        ))
        if include_status:
            all_intents.append(detect_status_intent(
                self_graph, diagnosis=diagnosis,
            ))

    if step_result is not None:
        all_intents.extend(detect_step_intents(step_result))

    if dream_observer is not None and dream_domain is not None:
        all_intents.extend(detect_dream_intents(
            dream_observer, dream_domain,
            anomaly_threshold=anomaly_threshold,
        ))

    if landscape is not None:
        all_intents.extend(detect_landscape_intents(
            landscape,
            trace=trace,
            goal=goal,
            task_description=task_description,
        ))

    all_intents.sort(key=lambda i: i.urgency, reverse=True)
    return IntentReport(intents=all_intents)


# ──────────────────────────────────────────────
# 8. Learning Cycle Round Intents (C212)
# ──────────────────────────────────────────────


def detect_round_intents(
    *,
    round_num: int,
    mode: str,
    reason: str,
    steps: int,
    coverage_before: float,
    coverage_after: float,
    coverage_delta: float,
    T_s_before: float,
    T_s_after: float,
    domain_crossings: int,
    crossing_rate: float,
    canon_coverage: float,
    bootstrap_coverage: float,
    en_coverage: float,
    new_edges: int,
    total_nodes: int = 0,
    visited_nodes: int = 0,
    en_canon_crossings: int = 0,
    en_bootstrap_crossings: int = 0,
    canon_bootstrap_crossings: int = 0,
    stagnation_count: int = 0,
    inscription_stats: Optional[Dict[str, Any]] = None,
    # C276: node counts — -1 means "unknown/assume present" (backward compat)
    canon_nodes: int = -1,
    bootstrap_nodes: int = -1,
    en_nodes: int = -1,
) -> IntentReport:
    """Detect communication intents from a learning cycle round.

    Translates multi-domain round results into CommunicationIntents
    that the evidence interpreters can render as prose. Evidence dicts
    are shaped to match existing interpreter signatures.

    C276: canon_nodes / bootstrap_nodes / en_nodes filter which domains
    appear in the balance and crossing reports.  -1 means "not specified
    — assume the domain is present" (backward-compatible default).

    Returns:
        IntentReport with round-specific intents, sorted by urgency.
    """
    intents: List[CommunicationIntent] = []

    # ── 1. Round Decision (DECISION) ──────────────────
    intents.append(CommunicationIntent(
        type=IntentType.DECISION,
        urgency=0.3,
        subject=f"round_{round_num}",
        summary=(
            f"Round {round_num}: chose '{mode}' "
            f"({steps} steps). {reason}"
        ),
        evidence={
            "source": f"round_{round_num}",
            "target": mode,
            "outcome": "SUCCESS" if coverage_delta > 0 else "FAILURE",
            "s_eff": 1.0 - coverage_after,
            "steps": steps,
            "reason": reason,
        },
    ))

    # ── 2. Coverage Pattern (PATTERN) ─────────────────
    # Model coverage growth as resistance drop:
    # R_eff = 1 - coverage (the "resistance to full coverage")
    r_before = 1.0 - coverage_before
    r_after = 1.0 - coverage_after
    if r_before > 0:
        drop_pct = (r_before - r_after) / r_before
    else:
        drop_pct = 0.0

    cov_urgency = 0.3 if coverage_delta > 0.01 else 0.6
    intents.append(CommunicationIntent(
        type=IntentType.PATTERN,
        urgency=cov_urgency,
        subject="coverage",
        summary=(
            f"Coverage {coverage_before:.1%} → {coverage_after:.1%} "
            f"({visited_nodes}/{total_nodes} nodes). "
            f"Resistance to full coverage dropped {drop_pct:.0%}."
        ),
        evidence={
            "r_eff_before": round(r_before, 4),
            "r_eff_after": round(r_after, 4),
            "drop_pct": round(drop_pct, 4),
        },
    ))

    # ── 3. Domain Balance (STATUS) ────────────────────
    # C276: Only include domains that actually have nodes in the landscape.
    # -1 sentinel = unknown / caller didn't specify → assume present.
    def _has_domain(n: int) -> bool:
        return n != 0  # -1 (unknown) or >0 → include

    coverages: Dict[str, float] = {}
    if _has_domain(canon_nodes):
        coverages["Canon"] = canon_coverage
    if _has_domain(bootstrap_nodes):
        coverages["Bootstrap"] = bootstrap_coverage
    if _has_domain(en_nodes):
        coverages["EN"] = en_coverage

    if coverages:
        max_cov = max(coverages.values())
        min_cov = min(coverages.values())
        imbalance = max_cov - min_cov
        weakest = min(coverages, key=coverages.get)
        balance_summary = ", ".join(
            f"{name} {cov:.0%}" for name, cov in coverages.items()
        ) + (f" — {weakest} lagging" if imbalance > 0.15 else "")
    else:
        imbalance = 0.0
        balance_summary = f"Coverage {coverage_after:.1%}"

    balance_urgency = min(1.0, 0.2 + imbalance)
    intents.append(CommunicationIntent(
        type=IntentType.STATUS,
        urgency=balance_urgency,
        subject="domain_balance",
        summary=balance_summary,
        evidence={
            "task": "Multi-domain learning",
            "goal_reached": coverage_after > 0.9,
            "states": [],
            "edge_count": total_nodes,
            "steps": steps,
            "success_rate": coverage_after,
            "avg_tension": T_s_after,
            "canon_coverage": round(canon_coverage, 4),
            "bootstrap_coverage": round(bootstrap_coverage, 4),
            "en_coverage": round(en_coverage, 4),
        },
    ))

    # ── 4. Cross-Domain Activity (PATTERN) ────────────
    # C276: Only show EN-specific crossing stats when EN nodes exist.
    if steps > 0:
        has_en = _has_domain(en_nodes)
        crossing_parts = [
            f"{domain_crossings} domain crossings in {steps} steps "
            f"({crossing_rate:.0%})"
        ]
        if has_en:
            crossing_parts.append(
                f"EN↔Canon {en_canon_crossings}, "
                f"EN↔Boot {en_bootstrap_crossings}, "
                f"C↔B {canon_bootstrap_crossings}"
            )
        else:
            crossing_parts.append(f"C↔B {canon_bootstrap_crossings}")

        intents.append(CommunicationIntent(
            type=IntentType.PATTERN,
            urgency=0.3 if crossing_rate > 0.3 else 0.5,
            subject="domain_crossings",
            summary=": ".join(crossing_parts),
            evidence={
                "domain_crossings": domain_crossings,
                "crossing_rate": round(crossing_rate, 4),
                "en_canon": en_canon_crossings,
                "en_bootstrap": en_bootstrap_crossings,
                "canon_bootstrap": canon_bootstrap_crossings,
                "steps": steps,
            },
        ))

    # ── 5. Structural Temperature (UNCERTAINTY) ──────
    T_s_delta = T_s_after - T_s_before
    if T_s_after > 0.5:
        t_urgency = min(1.0, 0.4 + T_s_after * 0.3)
        intents.append(CommunicationIntent(
            type=IntentType.UNCERTAINTY,
            urgency=t_urgency,
            subject="structural_temperature",
            summary=(
                f"Structural temperature T_s={T_s_after:.3f} "
                f"(Δ={T_s_delta:+.3f})"
            ),
            evidence={
                "status": "confused" if T_s_after > 1.0 else "uncertain",
                "quality": -T_s_after,
                "load": float(steps),
            },
        ))

    # ── 6. Stagnation Warning (REQUEST) ───────────────
    if stagnation_count >= 2:
        intents.append(CommunicationIntent(
            type=IntentType.REQUEST,
            urgency=min(1.0, 0.6 + stagnation_count * 0.1),
            subject="stagnation",
            summary=(
                f"Stagnation: {stagnation_count} rounds with no "
                f"coverage progress. Current coverage: {coverage_after:.1%}"
            ),
            evidence={
                "state": f"round_{round_num}",
                "admissible_neighbors": [],
                "goal": f"coverage > 90% (current: {coverage_after:.1%})",
                "stagnation_count": stagnation_count,
            },
        ))

    # ── 7. New Edges (ANOMALY if many) ────────────────
    if new_edges > 5:
        intents.append(CommunicationIntent(
            type=IntentType.ANOMALY,
            urgency=0.4,
            subject="new_shortcuts",
            summary=(
                f"Discovered {new_edges} new shortcut edges "
                f"during navigation"
            ),
            evidence={
                "own_state": f"round_{round_num}",
                "partner_state": "shortcut_discovery",
                "trace_quality": coverage_delta,
                "new_edges": new_edges,
            },
        ))

    intents.sort(key=lambda i: i.urgency, reverse=True)
    return IntentReport(intents=intents)
