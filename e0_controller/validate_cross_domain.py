"""
E₀ Cross-Domain Validation (Phase 3d)
=======================================
Systematic comparison across all open-domain demos.

Runs all three domains (mock or live), collects graph quality
and run metrics, and produces a structured comparison report.

Usage:
    # Mock comparison (no API key needed):
    python -m e0_controller.validate_cross_domain

    # Live comparison:
    python -m e0_controller.validate_cross_domain --live

Requires OPENAI_API_KEY in .env or environment (for --live mode).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from e0_controller.graph_validation import graph_quality, GraphQuality
from e0_controller.llm_adapter import (
    E0LLMAdapter,
    LandscapeProposal,
    TransitionResult,
    materialize_landscape,
    task_map_from_proposal,
)
from e0_controller.controller import RunTrace
from e0_controller.scenario_loader import ScenarioPacket, load_scenario, find_scenario


# ──────────────────────────────────────────────
# Result container
# ──────────────────────────────────────────────

@dataclass
class DomainResult:
    """Collected results for one domain run."""
    name: str
    mode: str  # "mock" or "live"
    state_count: int
    edge_count: int
    gq: GraphQuality
    steps: int
    success_rate: float
    escalation_count: int
    unique_states: int
    revisits: int
    avg_tension: float
    total_tension: float
    reached_goal: bool
    trap_warnings: int
    loop_warnings: int
    result_log: List[TransitionResult]


# ──────────────────────────────────────────────
# Run one domain
# ──────────────────────────────────────────────

def _run_domain(run_fn, name: str, use_mock: bool,
                scenario: ScenarioPacket | None = None) -> Optional[DomainResult]:
    """Run a domain demo and collect structured results."""
    try:
        result = run_fn(use_mock=use_mock, scenario=scenario)
        trace, proposal, result_log = result
    except Exception as e:
        print(f"  ERROR in {name}: {e}")
        return None

    if trace is None:
        print(f"  ABORTED: {name} (graph failed quality checks)")
        return None

    L = materialize_landscape(proposal)
    start = proposal.states[0] if proposal.states else ""
    goal = proposal.states[-1] if proposal.states else ""
    # Infer goal from the demo's default
    for s in proposal.states:
        if "DELIVERED" in s:
            goal = s
            break

    gq = graph_quality(L, start, goal)
    metrics = trace.metrics()

    traps = len(gq.traps)
    loops = len(gq.trivial_loops)

    return DomainResult(
        name=name,
        mode="mock" if use_mock else "live",
        state_count=len(proposal.states),
        edge_count=len(proposal.edges),
        gq=gq,
        steps=int(metrics["steps"]),
        success_rate=metrics["success_rate"],
        escalation_count=int(metrics["escalation_count"]),
        unique_states=int(metrics["unique_states"]),
        revisits=int(metrics["revisit_count"]),
        avg_tension=metrics["avg_tension"],
        total_tension=trace.total_tension,
        reached_goal=trace.path[-1] == goal if trace.path else False,
        trap_warnings=traps,
        loop_warnings=loops,
        result_log=result_log,
    )


# ──────────────────────────────────────────────
# Comparison report
# ──────────────────────────────────────────────

def _print_comparison(results: List[DomainResult]) -> None:
    """Print a structured cross-domain comparison table."""
    print("\n" + "=" * 78)
    print("E₀ Cross-Domain Validation Report (Phase 3d)")
    print("=" * 78)

    # Header
    col_w = 24
    header = f"{'Metric':<28}"
    for r in results:
        header += f"{r.name[:col_w]:>{col_w}}"
    print(f"\n{header}")
    print("-" * (28 + col_w * len(results)))

    # Rows
    rows = [
        ("Mode",           [r.mode for r in results]),
        ("States",         [str(r.state_count) for r in results]),
        ("Edges",          [str(r.edge_count) for r in results]),
        ("Graph Score",    [f"{r.gq.score:.2f}" for r in results]),
        ("Happy Path",     [str(r.gq.happy_path_length) for r in results]),
        ("Recovery Edges", [str(r.gq.recovery_count) for r in results]),
        ("Traps",          [str(r.trap_warnings) for r in results]),
        ("Trivial Loops",  [str(r.loop_warnings) for r in results]),
        ("",               ["" for _ in results]),  # separator
        ("Steps",          [str(r.steps) for r in results]),
        ("Reached Goal",   ["YES" if r.reached_goal else "NO" for r in results]),
        ("Success Rate",   [f"{r.success_rate:.0%}" for r in results]),
        ("Escalations",    [str(r.escalation_count) for r in results]),
        ("Unique States",  [str(r.unique_states) for r in results]),
        ("Revisits",       [str(r.revisits) for r in results]),
        ("Avg Tension",    [f"{r.avg_tension:.4f}" for r in results]),
        ("Total Tension",  [f"{r.total_tension:.2f}" for r in results]),
    ]

    for label, values in rows:
        if not label:
            print()
            continue
        row = f"{label:<28}"
        for v in values:
            row += f"{v:>{col_w}}"
        print(row)

    # Warnings summary
    print(f"\n{'─' * 78}")
    print("Warnings:")
    any_warning = False
    for r in results:
        for w in r.gq.warnings:
            print(f"  [{r.name}] {w}")
            any_warning = True
    if not any_warning:
        print("  (none)")

    # Overall assessment
    print(f"\n{'─' * 78}")
    all_reached = all(r.reached_goal for r in results)
    all_ok = all(r.gq.ok() for r in results)
    avg_score = sum(r.gq.score for r in results) / len(results) if results else 0

    print(f"All goals reached:     {'YES' if all_reached else 'NO'}")
    print(f"All graphs valid:      {'YES' if all_ok else 'NO'}")
    print(f"Mean graph score:      {avg_score:.2f}")

    # Cross-domain insights
    if len(results) >= 2:
        scores = [r.gq.score for r in results]
        spread = max(scores) - min(scores)
        print(f"Score spread:          {spread:.2f}")

        tensions = [r.avg_tension for r in results]
        hardest = results[tensions.index(max(tensions))]
        easiest = results[tensions.index(min(tensions))]
        print(f"Hardest domain:        {hardest.name} (avg tension {hardest.avg_tension:.4f})")
        print(f"Easiest domain:        {easiest.name} (avg tension {easiest.avg_tension:.4f})")

    print("=" * 78)


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def run_validation(use_mock: bool = True) -> List[DomainResult]:
    """Run all domains and produce comparison report."""
    # Import demos
    from e0_controller.demo_open_domain import run_demo as run_open
    from e0_controller.demo_incident_postmortem import run_demo as run_incident
    from e0_controller.demo_research_brief import run_demo as run_research

    # Auto-discover scenario packets
    sc_open = None
    sc_incident = None
    sc_research = None
    for domain, var_name in [("competitor_brief", "sc_open"),
                              ("incident_postmortem", "sc_incident"),
                              ("research_brief", "sc_research")]:
        path = find_scenario(domain)
        if path:
            sc = load_scenario(path)
            if var_name == "sc_open":
                sc_open = sc
            elif var_name == "sc_incident":
                sc_incident = sc
            elif var_name == "sc_research":
                sc_research = sc

    domains = [
        (run_open, "Competitor Brief", sc_open),
        (run_incident, "Incident Postmortem", sc_incident),
        (run_research, "Research Brief", sc_research),
    ]

    results: List[DomainResult] = []
    for run_fn, name, sc in domains:
        print(f"\n{'━' * 64}")
        print(f"  Running: {name}")
        if sc:
            print(f"  Scenario: {sc.title} [{sc.scenario_id}]")
        print(f"{'━' * 64}")
        dr = _run_domain(run_fn, name, use_mock, scenario=sc)
        if dr:
            results.append(dr)

    if results:
        _print_comparison(results)

    return results


if __name__ == "__main__":
    use_mock = "--live" not in sys.argv
    run_validation(use_mock=use_mock)
