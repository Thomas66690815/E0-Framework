"""
E₀ Demo — Open Domain (Phase 3b)
===================================
The controller bootstraps its own Landscape from a task description.

This is the key Phase 3b capability: instead of a pre-wired domain
(like Invoice), the LLM proposes the state graph, estimates Δ and R₀,
and then executes transitions — all under deterministic E₀ control.

Usage:
    # With real API:
    python -m e0_controller.demo_open_domain

    # With mock (no API key needed):
    python -m e0_controller.demo_open_domain --mock

    # Custom task:
    python -m e0_controller.demo_open_domain --task "Write a project proposal"

Requires OPENAI_API_KEY in .env or environment (unless --mock).
"""

from __future__ import annotations

import json
import os
import sys

from e0_controller.controller import E0Controller
from e0_controller.memory_os import E0MemoryOS, CanonRef
from e0_controller.llm_adapter import (
    E0LLMAdapter,
    LLMConfig,
    LandscapeProposal,
    materialize_landscape,
    task_map_from_proposal,
)
from e0_controller.graph_validation import graph_quality


# ──────────────────────────────────────────────
# Default task
# ──────────────────────────────────────────────

DEFAULT_TASK = (
    "Analyze a competitor's product announcement and produce a structured "
    "briefing for the executive team. The briefing should cover: what the "
    "competitor announced, how it affects our market position, and recommended "
    "strategic responses."
)
DEFAULT_START = "RAW_ANNOUNCEMENT"
DEFAULT_GOAL = "BRIEFING_DELIVERED"


# ──────────────────────────────────────────────
# Mock LLM for --mock mode
# ──────────────────────────────────────────────

def mock_llm_call(system: str, user: str, config: LLMConfig) -> str:
    """Deterministic mock for open-domain demo."""
    import json as _json

    if "design the complete state graph" in user:
        return _json.dumps({
            "states": [
                "RAW_ANNOUNCEMENT", "TEXT_PARSED", "KEY_FACTS_EXTRACTED",
                "MARKET_CONTEXT_GATHERED", "IMPACT_ASSESSED",
                "RESPONSES_DRAFTED", "BRIEFING_ASSEMBLED", "BRIEFING_DELIVERED",
                "PARSE_FAILED",
            ],
            "edges": [
                {"source": "RAW_ANNOUNCEMENT", "target": "TEXT_PARSED",
                 "delta": 0.3, "resistance": 0.4,
                 "description": "Parse the announcement text into structured sections."},
                {"source": "TEXT_PARSED", "target": "KEY_FACTS_EXTRACTED",
                 "delta": 0.5, "resistance": 0.8,
                 "description": "Extract key facts: product name, features, pricing, timeline."},
                {"source": "KEY_FACTS_EXTRACTED", "target": "MARKET_CONTEXT_GATHERED",
                 "delta": 0.4, "resistance": 1.0,
                 "description": "Research market context: our position, competitor history, segment trends."},
                {"source": "MARKET_CONTEXT_GATHERED", "target": "IMPACT_ASSESSED",
                 "delta": 0.6, "resistance": 1.2,
                 "description": "Assess strategic impact on our product line and market share."},
                {"source": "IMPACT_ASSESSED", "target": "RESPONSES_DRAFTED",
                 "delta": 0.5, "resistance": 1.0,
                 "description": "Draft 2-3 strategic response options with pros/cons."},
                {"source": "RESPONSES_DRAFTED", "target": "BRIEFING_ASSEMBLED",
                 "delta": 0.3, "resistance": 0.5,
                 "description": "Assemble executive briefing document with all sections."},
                {"source": "BRIEFING_ASSEMBLED", "target": "BRIEFING_DELIVERED",
                 "delta": 0.2, "resistance": 0.3,
                 "description": "Final review and delivery of briefing."},
                # Error path
                {"source": "RAW_ANNOUNCEMENT", "target": "PARSE_FAILED",
                 "delta": 0.3, "resistance": 2.0,
                 "description": "Announcement text is unreadable or in unknown format."},
                {"source": "PARSE_FAILED", "target": "TEXT_PARSED",
                 "delta": 0.4, "resistance": 1.5,
                 "description": "Retry parsing with alternative extraction strategy."},
                # Recovery shortcut
                {"source": "KEY_FACTS_EXTRACTED", "target": "IMPACT_ASSESSED",
                 "delta": 0.7, "resistance": 1.8,
                 "description": "Skip market research, assess impact from facts alone (less accurate)."},
            ],
        })

    if "Execute the transition" in user:
        return _json.dumps({
            "outcome": "SUCCESS",
            "result": "Transition completed successfully.",
            "confidence": 0.88,
        })

    if "Estimate the structural resistance" in user:
        return _json.dumps({
            "resistance": 0.8,
            "reasoning": "Moderate complexity transition.",
        })

    # Default
    return _json.dumps({
        "delta": 0.4,
        "reasoning": "Moderate structural change.",
    })


# ──────────────────────────────────────────────
# Main Demo
# ──────────────────────────────────────────────

def run_demo(
    task: str = DEFAULT_TASK,
    start: str = DEFAULT_START,
    goal: str = DEFAULT_GOAL,
    use_mock: bool = False,
):
    """Run an open-domain demo with LLM-bootstrapped landscape."""

    print("=" * 64)
    print("E₀ Controller — Open Domain Demo (Phase 3b)")
    print("=" * 64)
    print(f"\nTask: {task}")
    print(f"Start: {start} → Goal: {goal}")

    # 1. Setup LLM adapter
    if use_mock:
        print("\nMode: MOCK (no API calls)")
        adapter = E0LLMAdapter(call_fn=mock_llm_call)
    else:
        config = LLMConfig(model="gpt-5.4-mini", temperature=0.3)
        adapter = E0LLMAdapter(config=config)
        print(f"\nMode: LIVE (model={config.model})")

    # 2. LLM designs the landscape
    print("\n── Step 1: LLM designs state graph ──")
    proposal = adapter.build_landscape(task, start, goal)
    print(f"   States: {len(proposal.states)}")
    for s in proposal.states:
        print(f"     • {s}")
    print(f"   Edges: {len(proposal.edges)}")
    for e in proposal.edges:
        print(f"     {e['source']} → {e['target']}  "
              f"(Δ={e['delta']:.1f}, R₀={e['resistance']:.1f})")

    # 3. Materialize into Landscape
    L = materialize_landscape(proposal)
    task_map = task_map_from_proposal(proposal)
    print(f"\n   Landscape: {len(L.states)} states, {len(L.edges)} edges")

    # 3b. Graph quality validation (Phase 3c)
    print("\n── Step 1b: Graph quality check ──")
    gq = graph_quality(L, start, goal)
    print(gq.summary())
    if not gq.ok():
        print("\n*** ABORTED: graph failed critical quality checks ***")
        return None, proposal

    # 4. Setup MemOS
    memos_dir = os.path.join(os.getcwd(), "memos")
    os.makedirs(memos_dir, exist_ok=True)
    memos = E0MemoryOS(base_dir=memos_dir)

    # 5. Create execute function with dynamic summary
    session_id = "demo-open-domain"

    def summary_provider():
        try:
            ctx = memos.load_context(session_id)
            current = (ctx.runtime.get("last_state", start)
                       if ctx.runtime else start)
            return memos.summarize_for_llm(ctx, current, landscape=L)
        except FileNotFoundError:
            return {}

    execute_fn = adapter.as_execute_fn(
        task_map, summary_provider=summary_provider,
    )

    # 6. Build controller and run
    print("\n── Step 2: Controller runs ──")
    ctrl = E0Controller(L, execute_fn, alpha=2.0, recent_k=3)
    trace = ctrl.run(start=start, goal=goal, max_cycles=20)

    # 7. Display results
    print(f"\n{'=' * 64}")
    print("Run Complete")
    print(f"{'=' * 64}")
    print(trace.summary())

    metrics = trace.metrics()
    print(f"\nMetrics:")
    print(f"  Steps:             {int(metrics['steps'])}")
    print(f"  Deterministic:     {metrics['deterministic_rate']:.0%}")
    print(f"  Success rate:      {metrics['success_rate']:.0%}")
    print(f"  Avg tension:       {metrics['avg_tension']:.4f}")
    print(f"  Unique states:     {int(metrics['unique_states'])}")
    print(f"  Revisits:          {int(metrics['revisit_count'])}")

    # 8. Save to MemOS
    ctx = memos.snapshot_from_runtime(
        session_id, L, ctrl, trace,
        canon_refs=[CanonRef(
            name="ontodynamics", version="1.0",
            path="canon/ontodynamics.txt",
        )],
    )
    memos.save_context(ctx)
    memos.save_run(session_id, trace, goal=goal)
    print(f"\nMemOS data persisted to: {memos_dir}")

    return trace, proposal


if __name__ == "__main__":
    use_mock = "--mock" in sys.argv
    task = DEFAULT_TASK
    # Simple --task override
    for i, arg in enumerate(sys.argv):
        if arg == "--task" and i + 1 < len(sys.argv):
            task = sys.argv[i + 1]
    run_demo(task=task, use_mock=use_mock)
