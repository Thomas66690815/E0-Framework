"""E₀ Demo — Open Domain (Phase 3b, modernized)
===================================================
The controller bootstraps its own Landscape from an arbitrary task
description, then navigates it through Session.iterate() with
ExplorationPolicy — demonstrating that the same architecture
used for pre-designed domains (Beipackzettel, EZB, Burnout)
works identically on LLM-generated topology.

This is the universality proof: no code changes between domains.

Usage:
    # Mock mode (no API key needed):
    py -3 -m e0_controller.demo_open_domain --mock

    # Live LLM (requires OPENAI_API_KEY in .env):
    py -3 -m e0_controller.demo_open_domain

    # Custom task:
    py -3 -m e0_controller.demo_open_domain --mock --task "Write a project proposal"

    # With scenario packet:
    py -3 -m e0_controller.demo_open_domain --scenario scenarios/competitor_brief.json
"""

from __future__ import annotations

import json
import sys

from e0_controller import (
    Landscape,
    Session,
    HybridMode,
    E0Envelope,
    TransportRegime,
    ExplorationPolicy,
    CanonRef,
    E0LLMAdapter,
    LLMConfig,
    materialize_landscape,
    task_map_from_proposal,
    graph_quality,
    format_residual_map,
)
from e0_controller.scenario_loader import ScenarioPacket, load_scenario, find_scenario


# ── Default task ─────────────────────────────────────────────────────────

DEFAULT_TASK = (
    "Analyze a competitor's product announcement and produce a structured "
    "briefing for the executive team. The briefing should cover: what the "
    "competitor announced, how it affects our market position, and recommended "
    "strategic responses."
)
DEFAULT_START = "RAW_ANNOUNCEMENT"
DEFAULT_GOAL = "BRIEFING_DELIVERED"


# ── Envelope ─────────────────────────────────────────────────────────────

ENVELOPE = E0Envelope(
    mode=HybridMode.AMPLITUDE_ON_DISAGREE,
    geometry="goal_reaching",
    horizon=4,
    transport=TransportRegime.U1,
    goals=frozenset({DEFAULT_GOAL}),
    alpha=0.5,
)

EXPLORATION_POLICY = ExplorationPolicy.born_warmup(
    warmup=2,
    convergence_threshold=0.15,
)


# ── Mock LLM ─────────────────────────────────────────────────────────────

def mock_llm_call(system: str, user: str, config: LLMConfig) -> str:
    """Deterministic mock for open-domain demo."""
    if "design the complete state graph" in user:
        return json.dumps({
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
                # Recovery shortcut (higher burden — skip market research)
                {"source": "KEY_FACTS_EXTRACTED", "target": "IMPACT_ASSESSED",
                 "delta": 0.7, "resistance": 1.8,
                 "description": "Skip market research, assess impact from facts alone (less accurate)."},
            ],
        })

    if "Execute the transition" in user:
        return json.dumps({
            "outcome": "SUCCESS",
            "result": "Transition completed successfully.",
            "confidence": 0.88,
        })

    if "Estimate the structural resistance" in user:
        return json.dumps({
            "resistance": 0.8,
            "reasoning": "Moderate complexity transition.",
        })

    return json.dumps({
        "delta": 0.4,
        "reasoning": "Moderate structural change.",
    })


# ── Demo runner ──────────────────────────────────────────────────────────

def run_demo(
    task: str = DEFAULT_TASK,
    start: str = DEFAULT_START,
    goal: str = DEFAULT_GOAL,
    use_mock: bool = False,
    envelope: E0Envelope = ENVELOPE,
    exploration_policy: ExplorationPolicy = EXPLORATION_POLICY,
    scenario: ScenarioPacket | None = None,
) -> dict:
    """Run an open-domain demo with LLM-bootstrapped landscape.

    Returns dict with all results for programmatic inspection.
    """
    # Override from scenario packet if provided
    if scenario:
        task = f"{scenario.objective}\n\nSource material:\n{scenario.source_text}"
        start = scenario.start_state or start
        goal = scenario.goal_state or goal

    print("=" * 64)
    print("E₀ — Open Domain Demo (Phase 3b)")
    print("=" * 64)
    if scenario:
        print(f"\nScenario: {scenario.title} [{scenario.scenario_id}]")
    print(f"\nTask: {task[:200]}{'...' if len(task) > 200 else ''}")
    print(f"Start: {start} → Goal: {goal}")
    print(f"Envelope: {envelope.summary()}")
    print(f"Policy:   {exploration_policy.label}")

    # ── 1. LLM generates landscape ──────────────────────────────
    if use_mock:
        print("\nMode: MOCK")
        adapter = E0LLMAdapter(call_fn=mock_llm_call)
    else:
        config = LLMConfig(model="gpt-4.1-mini", temperature=0.3, max_tokens=2048)
        adapter = E0LLMAdapter(config=config)
        print(f"\nMode: LIVE (model={config.model})")

    print("\n── Phase 1: Landscape Generation ──")
    sc_block = scenario.as_prompt_block() if scenario else ""
    proposal = adapter.build_landscape(
        task, start, goal,
        goals=set(envelope.goals) if envelope.goals else None,
        scenario_block=sc_block,
    )
    L = materialize_landscape(proposal)
    task_map = task_map_from_proposal(proposal)

    print(f"   States: {len(L.states)}, Edges: {len(L.edges)}")
    for e in proposal.edges:
        print(f"     {e['source']:30s} → {e['target']:30s}  "
              f"(Δ={e['delta']:.2f}, R₀={e['resistance']:.2f})")

    gq = graph_quality(L, start, goal)
    print(f"\n   Graph quality: {gq.score:.2f}")
    if not gq.ok():
        print("   ⚠ Graph quality check failed — proceeding for analysis")

    # ── 2. Build execute function ───────────────────────────────
    result_log = []
    execute_fn = adapter.as_execute_fn(
        task_map,
        scenario_block=sc_block,
        result_log=result_log,
    )

    # ── 3. Session.iterate() — emergent iterations ──────────────
    print(f"\n── Phase 2: Iterative Runs (max 5 iterations) ──")
    print(f"   Stopping: tension equilibrium | stagnation | budget")
    print(f"   Iteration count is NOT prescribed — it emerges.")
    print(f"   Policy: {exploration_policy.label}\n")

    session = Session(
        session_id="open-domain",
        landscape=L,
        execute_fn=execute_fn,
        base_dir="memos/_open_domain",
        canon_refs=[CanonRef("e0-canon", "v1", "canon/e0-canon-plain.txt")],
        controller_kwargs=envelope.to_controller_kwargs(),
    )

    iter_result = session.iterate(
        start,
        goal=goal,
        max_cycles=20,
        max_iterations=5,
        tension_threshold=0.15,
        exploration_policy=exploration_policy,
    )

    # ── 4. Display per-iteration results ────────────────────────
    print(f"\n{'=' * 64}")
    print(f"Iterations completed: {iter_result.iterations}")
    print(f"Stop reason: {iter_result.stop_reason}")
    print(f"{'=' * 64}")

    for i, (res, verdict, refl) in enumerate(
        zip(iter_result.results, iter_result.verdicts, iter_result.reflections), 1
    ):
        trace = res.trace
        path_str = " → ".join(trace.path)
        m = trace.metrics()
        reached = goal in trace.path

        print(f"\n── Iteration {i} ──")
        print(f"   Path: {path_str}")
        print(f"   Steps: {int(m['steps'])}, "
              f"Success: {m['success_rate']:.0%}, "
              f"Revisits: {int(m['revisit_count'])}, "
              f"Goal: {'✓' if reached else '✗'}")
        print(f"   Avg tension: {m['avg_tension']:.4f}")
        if envelope.mode != HybridMode.GREEDY:
            print(f"   Hybrid overrides: {int(m['hybrid_override_count'])}")

        rmap = verdict.residual_map
        print(f"\n   Residual Tension Map:")
        print(f"     Max S_eff: {rmap.max_residual:.4f}")
        print(f"     Mean S_eff: {rmap.mean_residual:.4f}")
        print(f"     Resolved: {len(rmap.resolved)} edges")
        print(f"     Amplified: {len(rmap.amplified)} edges")

        print(f"\n   Verdict: {'CONTINUE' if verdict.should_continue else 'STOP'}"
              f" ({verdict.reason})")

    # ── 5. Final tension map ────────────────────────────────────
    if iter_result.final_map:
        print(f"\n{'=' * 64}")
        print("Final ResidualTensionMap")
        print(f"{'=' * 64}")
        print(format_residual_map(iter_result.final_map))

    # ── 6. Summary ──────────────────────────────────────────────
    first_trace = iter_result.results[0].trace
    last_trace = iter_result.results[-1].trace
    first_reached = goal in first_trace.path
    last_reached = goal in last_trace.path

    print(f"\n{'=' * 64}")
    print("Open Domain — Summary")
    print(f"{'=' * 64}")
    print(f"  Iterations:     {iter_result.iterations} (emerged, not prescribed)")
    print(f"  Stop reason:    {iter_result.stop_reason}")
    print(f"  Policy phases:  {iter_result.policy_phases}")
    reflections_triggered = sum(1 for r in iter_result.reflections if r is not None)
    print(f"  Reflections:    {reflections_triggered}")
    print(f"  First run goal: {'REACHED' if first_reached else 'MISSED'}")
    print(f"  Last run goal:  {'REACHED' if last_reached else 'MISSED'}")
    if iter_result.final_map:
        print(f"  Final max S:    {iter_result.final_map.max_residual:.4f}")
        print(f"  Final mean S:   {iter_result.final_map.mean_residual:.4f}")
    print(f"\n  Envelope: {envelope.summary()}")
    print(f"  Policy:   {exploration_policy.label}")

    if not use_mock:
        print(f"\n  ⚠  Landscape was LLM-generated, not pre-designed.")
        print(f"     Iteration count emerged from tension structure.")

    return {
        "iter_result": iter_result,
        "proposal": proposal,
        "landscape": L,
        "result_log": result_log,
        "graph_quality": gq,
    }


if __name__ == "__main__":
    use_mock = "--mock" in sys.argv
    task = DEFAULT_TASK
    sc = None
    for i, arg in enumerate(sys.argv):
        if arg == "--scenario" and i + 1 < len(sys.argv):
            sc = load_scenario(sys.argv[i + 1])
        elif arg == "--task" and i + 1 < len(sys.argv):
            task = sys.argv[i + 1]
    if sc is None and task == DEFAULT_TASK:
        path = find_scenario("competitor_brief")
        if path:
            sc = load_scenario(path)
    run_demo(task=task, use_mock=use_mock, scenario=sc)
