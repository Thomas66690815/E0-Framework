"""E₀ Demo — Bootstrap Domain from Scratch (C140)
====================================================
Demonstrates the complete cold-start pipeline:
  LLM describes a domain → scores edges → Bootstrapper creates Landscape
  → E0Controller navigates → ModeController monitors learning progress.

Two paths supported:
  Path A: LLM designs topology from natural-language description
          (propose_domain_graph → bootstrap_landscape)
  Path B: Manual JSON spec + LLM scores each edge monolingually
          (inject_scores → bootstrap_landscape)

This demo uses Path A with a built-in mock so it runs without API keys.

Usage:
    # Mock mode (no API key needed):
    py -3 -m e0_controller.demo_bootstrap_domain

    # Live LLM (requires OPENAI_API_KEY in .env):
    py -3 -m e0_controller.demo_bootstrap_domain --live

    # Custom task:
    py -3 -m e0_controller.demo_bootstrap_domain --task "Patient discharge workflow"

    # From JSON spec file:
    py -3 -m e0_controller.demo_bootstrap_domain --spec my_domain.json
"""

from __future__ import annotations

import json
import os
import sys

from e0_controller.primitives import Outcome
from e0_controller.landscape import Landscape
from e0_controller.bootstrapper import bootstrap_landscape
from e0_controller.controller import E0Controller, RunTrace
from e0_controller.llm_adapter import E0LLMAdapter, LLMConfig, materialize_landscape
from e0_controller.mode_controller import ModeController


# ── Default task ──────────────────────────────────────────────────────

DEFAULT_TASK = (
    "Onboard a new team member: collect documents, set up accounts, "
    "assign a buddy, schedule orientation sessions, complete first-week review."
)
DEFAULT_START = "NEW_HIRE_ARRIVED"
DEFAULT_GOAL = "ONBOARDING_COMPLETE"


# ── Mock LLM ──────────────────────────────────────────────────────────

MOCK_SPEC = {
    "nodes": [
        "NEW_HIRE_ARRIVED", "DOCUMENTS_COLLECTED", "ACCOUNTS_CREATED",
        "BUDDY_ASSIGNED", "ORIENTATION_SCHEDULED", "ORIENTATION_DONE",
        "FIRST_WEEK_REVIEW", "ONBOARDING_COMPLETE",
        "DOCUMENTS_INCOMPLETE",
    ],
    "edges": [
        {"from": "NEW_HIRE_ARRIVED", "to": "DOCUMENTS_COLLECTED",
         "delta": 0.3, "resistance": 0.4,
         "initial_U": 8, "initial_F": 2, "confidence": 0.8},
        {"from": "DOCUMENTS_COLLECTED", "to": "ACCOUNTS_CREATED",
         "delta": 0.4, "resistance": 0.6,
         "initial_U": 7, "initial_F": 3, "confidence": 0.7},
        {"from": "ACCOUNTS_CREATED", "to": "BUDDY_ASSIGNED",
         "delta": 0.2, "resistance": 0.3,
         "initial_U": 9, "initial_F": 1, "confidence": 0.9},
        {"from": "BUDDY_ASSIGNED", "to": "ORIENTATION_SCHEDULED",
         "delta": 0.3, "resistance": 0.5,
         "initial_U": 8, "initial_F": 2, "confidence": 0.8},
        {"from": "ORIENTATION_SCHEDULED", "to": "ORIENTATION_DONE",
         "delta": 0.5, "resistance": 0.8,
         "initial_U": 6, "initial_F": 4, "confidence": 0.6},
        {"from": "ORIENTATION_DONE", "to": "FIRST_WEEK_REVIEW",
         "delta": 0.4, "resistance": 0.7,
         "initial_U": 7, "initial_F": 3, "confidence": 0.7},
        {"from": "FIRST_WEEK_REVIEW", "to": "ONBOARDING_COMPLETE",
         "delta": 0.2, "resistance": 0.3,
         "initial_U": 9, "initial_F": 1, "confidence": 0.9},
        # Error path
        {"from": "NEW_HIRE_ARRIVED", "to": "DOCUMENTS_INCOMPLETE",
         "delta": 0.3, "resistance": 1.5,
         "initial_U": 2, "initial_F": 8, "confidence": 0.8},
        {"from": "DOCUMENTS_INCOMPLETE", "to": "DOCUMENTS_COLLECTED",
         "delta": 0.4, "resistance": 1.0,
         "initial_U": 5, "initial_F": 5, "confidence": 0.6},
        # Shortcut: skip orientation if experienced hire
        {"from": "BUDDY_ASSIGNED", "to": "FIRST_WEEK_REVIEW",
         "delta": 0.6, "resistance": 1.2,
         "initial_U": 4, "initial_F": 6, "confidence": 0.5},
    ],
}


def mock_llm_call(system: str, user: str, config: LLMConfig) -> str:
    """Deterministic mock for bootstrap demo."""
    if "design the complete state graph" in user or "domain graph" in user.lower():
        return json.dumps(MOCK_SPEC)
    if "Execute the transition" in user:
        return json.dumps({
            "outcome": "SUCCESS",
            "result": "Transition completed.",
            "confidence": 0.85,
        })
    return json.dumps({"delta": 0.4, "reasoning": "Moderate change."})


# ── Demo runner ───────────────────────────────────────────────────────

def run_demo(
    task: str = DEFAULT_TASK,
    start: str = DEFAULT_START,
    goal: str = DEFAULT_GOAL,
    use_mock: bool = True,
    spec_file: str | None = None,
) -> dict:
    """Run the bootstrap demo. Returns results dict.

    Args:
        task: Natural-language domain description (Path A).
        start: Start state name.
        goal: Goal state name.
        use_mock: If True, use deterministic mock LLM.
        spec_file: If provided, load JSON spec from file (Path B).
    """
    print("=" * 64)
    print("E₀ — Bootstrap Domain Demo (C140)")
    print("=" * 64)

    # ── Phase 1: Create Landscape ────────────────────────────────
    print("\n── Phase 1: Landscape Creation ──")

    if spec_file:
        # Path B: Load spec from JSON file
        print(f"   Path B: Loading spec from {spec_file}")
        with open(spec_file) as f:
            spec = json.load(f)
        L = bootstrap_landscape(spec)
        path_used = "B (JSON spec)"
    elif use_mock:
        # Path A with mock: use built-in spec directly
        print("   Path A (MOCK): Using built-in domain spec")
        L = bootstrap_landscape(MOCK_SPEC)
        path_used = "A (mock)"
    else:
        # Path A with live LLM: propose_and_bootstrap
        config = LLMConfig(model="gpt-4.1-mini", temperature=0.3, max_tokens=2048)
        adapter = E0LLMAdapter(config=config)
        print(f"   Path A (LIVE): LLM designs domain graph (model={config.model})")
        print(f"   Task: {task[:120]}{'...' if len(task) > 120 else ''}")
        L = adapter.propose_and_bootstrap(task)
        path_used = "A (live LLM)"

    print(f"\n   Landscape ready:")
    print(f"     States: {len(L.states)}")
    print(f"     Edges:  {L.edge_count()}")
    print(f"     Path:   {path_used}")

    # Show edge details
    for edge in L.edges:
        h = L.historization
        q = h.trace_quality(edge)
        m = h.trace_load(edge)
        I = h.inertia_factor(edge)
        print(f"     {edge.source:30s} → {edge.target:30s}  "
              f"q={q:+.2f}  m={m:.0f}  I={I:.2f}")

    # ── Phase 2: Mode analysis ───────────────────────────────────
    print("\n── Phase 2: Mode Analysis ──")
    mc = ModeController(L)
    mode = mc.current_mode()
    cov = mc.coverage()

    print(f"   Operating mode: {mode.value}")
    print(f"   Coverage:       {cov['explored']}/{cov['total']} edges explored "
          f"({cov['ratio']:.0%})")

    unexplored = mc.unexplored_edges()
    if unexplored:
        print(f"   Unexplored:     {len(unexplored)} edges need real experience")
        for e in unexplored[:5]:
            print(f"     - {e.source} → {e.target}")
        if len(unexplored) > 5:
            print(f"     ... and {len(unexplored) - 5} more")

    # ── Phase 3: Navigation ──────────────────────────────────────
    print(f"\n── Phase 3: Navigation ({start} → {goal}) ──")

    execute_fn = lambda s, t: Outcome.SUCCESS
    ctrl = E0Controller(L, execute_fn)
    trace = ctrl.run(start, goal=goal, max_cycles=30)

    path_str = " → ".join(trace.path)
    m = trace.metrics()
    reached = goal in trace.path

    print(f"   Path:     {path_str}")
    print(f"   Steps:    {int(m['steps'])}")
    print(f"   Goal:     {'✓ reached' if reached else '✗ not reached'}")
    print(f"   Success:  {m['success_rate']:.0%}")
    print(f"   Avg S_eff: {m['avg_tension']:.4f}")

    # ── Phase 4: Post-navigation mode check ──────────────────────
    print("\n── Phase 4: Post-Navigation Mode ──")
    mode_after = mc.current_mode()
    cov_after = mc.coverage()
    print(f"   Mode:     {mode_after.value}")
    print(f"   Coverage: {cov_after['explored']}/{cov_after['total']} "
          f"({cov_after['ratio']:.0%})")

    if mode_after != mode:
        print(f"   ↳ Mode changed: {mode.value} → {mode_after.value}")

    # ── Summary ──────────────────────────────────────────────────
    print(f"\n{'=' * 64}")
    print("Summary")
    print(f"{'=' * 64}")
    print(f"  Domain:       {task[:80]}{'...' if len(task) > 80 else ''}")
    print(f"  Bootstrap:    {path_used}")
    print(f"  Topology:     {len(L.states)} states, {L.edge_count()} edges")
    print(f"  Navigation:   {int(m['steps'])} steps, goal {'reached' if reached else 'missed'}")
    print(f"  Mode:         {mode.value} → {mode_after.value}")
    print(f"  Key insight:  Bootstrapper creates skeptical traces (confidence-scaled),")
    print(f"                E₀ navigates immediately but inertia dampening keeps it cautious.")
    print(f"{'=' * 64}")

    return {
        "landscape": L,
        "trace": trace,
        "goal_reached": reached,
        "mode_before": mode.value,
        "mode_after": mode_after.value,
        "path_used": path_used,
    }


# ── CLI ───────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    task = DEFAULT_TASK
    start = DEFAULT_START
    goal = DEFAULT_GOAL
    use_mock = True
    spec_file = None

    i = 0
    while i < len(args):
        if args[i] == "--live":
            use_mock = False
        elif args[i] == "--task" and i + 1 < len(args):
            task = args[i + 1]
            i += 1
        elif args[i] == "--start" and i + 1 < len(args):
            start = args[i + 1]
            i += 1
        elif args[i] == "--goal" and i + 1 < len(args):
            goal = args[i + 1]
            i += 1
        elif args[i] == "--spec" and i + 1 < len(args):
            spec_file = args[i + 1]
            i += 1
        elif args[i] in ("--help", "-h"):
            print(__doc__)
            return
        i += 1

    run_demo(
        task=task,
        start=start,
        goal=goal,
        use_mock=use_mock,
        spec_file=spec_file,
    )


if __name__ == "__main__":
    main()
