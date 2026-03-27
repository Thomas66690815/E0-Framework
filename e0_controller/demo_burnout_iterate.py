"""E₀ Live Demo — Burnout Iterative (C37 Continuum)
=====================================================
Runs the Burnout-Domäne through Session.iterate() — multiple
controller runs until tension equilibrium, stagnation, or budget.

This is the first demo where the number of iterations is NOT
prescribed — it emerges from the landscape's tension structure.

Shows:
  - LLM-bootstrapped landscape (same 5 fragments as demo_burnout_composite)
  - Session.iterate() with ResidualTensionMap per iteration
  - Automatic stopping when residual tension is resolved
  - Inter-iteration reflection when tension amplifies

Usage:
    # Live LLM (requires OPENAI_API_KEY in .env):
    py -3 -m e0_controller.demo_burnout_iterate

    # Mock mode (no API key needed):
    py -3 -m e0_controller.demo_burnout_iterate --mock
"""

from __future__ import annotations

import os
import sys

from e0_controller import (
    Landscape,
    Session,
    HybridMode,
    E0Envelope,
    TransportRegime,
    CanonRef,
    E0LLMAdapter,
    LLMConfig,
    materialize_landscape,
    task_map_from_proposal,
    graph_quality,
    format_residual_map,
)
from e0_controller.demo_burnout_composite import (
    ALL_FRAGMENTS,
    BURNOUT_TASK,
    DEFAULT_START,
    DEFAULT_GOAL,
    composite_source_text,
    mock_llm_call,
)

ENVELOPE = E0Envelope(
    mode=HybridMode.AMPLITUDE_ON_DISAGREE,
    geometry="goal_reaching",
    horizon=4,
    transport=TransportRegime.U1,
    goals=frozenset({DEFAULT_GOAL}),
    alpha=0.5,
)


def run_iterative_demo(use_mock: bool = False) -> None:
    source_text = composite_source_text()

    print("=" * 64)
    print("E₀ — Burnout Iterative Demo (C37 Continuum)")
    print("=" * 64)
    print(f"\nFragmente: {len(ALL_FRAGMENTS)}")
    for label in ALL_FRAGMENTS:
        print(f"  • {label}")
    print(f"\nEnvelope: {ENVELOPE.summary()}")

    # ── 1. LLM generates landscape ──────────────────────────────
    if use_mock:
        print("\nMode: MOCK")
        adapter = E0LLMAdapter(call_fn=mock_llm_call)
    else:
        config = LLMConfig(model="gpt-4.1-mini", temperature=0.3, max_tokens=2048)
        adapter = E0LLMAdapter(config=config)
        print(f"\nMode: LIVE (model={config.model})")

    print("\n── Phase 1: Landscape Generation ──")
    task_with_source = BURNOUT_TASK + source_text
    proposal = adapter.build_landscape(
        task_with_source, DEFAULT_START, DEFAULT_GOAL,
        goals=set(ENVELOPE.goals),
    )
    L = materialize_landscape(proposal)
    task_map = task_map_from_proposal(proposal)

    print(f"   States: {len(L.states)}, Edges: {len(L.edges)}")
    for e in proposal.edges:
        print(f"     {e['source']:35s} → {e['target']:35s}  "
              f"(Δ={e['delta']:.2f}, R₀={e['resistance']:.2f})")

    gq = graph_quality(L, DEFAULT_START, DEFAULT_GOAL)
    print(f"\n   Graph quality: {gq.score:.2f}")
    if not gq.ok():
        print("   ⚠ Graph quality check failed — proceeding for analysis")

    # ── 2. Build execute function ───────────────────────────────
    result_log = []
    execute_fn = adapter.as_execute_fn(
        task_map,
        scenario_block=source_text,
        result_log=result_log,
    )

    # ── 3. Session.iterate() — the Continuum ────────────────────
    print(f"\n── Phase 2: Iterative Runs (max 5 iterations) ──")
    print(f"   Stopping: tension equilibrium | stagnation | budget")
    print(f"   Iteration count is NOT prescribed — it emerges.\n")

    session = Session(
        session_id="burnout-iterate",
        landscape=L,
        execute_fn=execute_fn,
        base_dir="memos/_burnout_iterate",
        canon_refs=[CanonRef("e0-canon", "v1", "canon/e0-canon-plain.txt")],
        controller_kwargs=ENVELOPE.to_controller_kwargs(),
    )

    iter_result = session.iterate(
        DEFAULT_START,
        goal=DEFAULT_GOAL,
        max_cycles=20,
        max_iterations=5,
        tension_threshold=0.15,
    )

    # ── 4. Display per-iteration results ────────────────────────
    print(f"\n{'=' * 64}")
    print(f"Iterations completed: {iter_result.iterations}")
    print(f"Stop reason: {iter_result.stop_reason}")
    print(f"{'=' * 64}")

    for i, (res, verdict) in enumerate(
        zip(iter_result.results, iter_result.verdicts), 1
    ):
        trace = res.trace
        path_str = " → ".join(trace.path)
        m = trace.metrics()
        reached = DEFAULT_GOAL in trace.path

        print(f"\n── Iteration {i} ──")
        print(f"   Path: {path_str}")
        print(f"   Steps: {int(m['steps'])}, "
              f"Success: {m['success_rate']:.0%}, "
              f"Revisits: {int(m['revisit_count'])}, "
              f"Goal: {'✓' if reached else '✗'}")
        print(f"   Avg tension: {m['avg_tension']:.4f}")
        if ENVELOPE.mode != HybridMode.GREEDY:
            print(f"   Hybrid overrides: {int(m['hybrid_override_count'])}")

        rmap = verdict.residual_map
        print(f"\n   Residual Tension Map:")
        print(f"     Max S_eff: {rmap.max_residual:.4f}")
        print(f"     Mean S_eff: {rmap.mean_residual:.4f}")
        print(f"     Resolved: {len(rmap.resolved)} edges")
        print(f"     Amplified: {len(rmap.amplified)} edges")
        if rmap.hotspots:
            print(f"     Hotspots:")
            for h in rmap.hotspots[:3]:
                print(f"       {h.edge.source}→{h.edge.target}: "
                      f"S_eff={h.s_eff:.4f}, ΔS={h.delta_s:+.4f}")

        print(f"\n   Verdict: {'CONTINUE' if verdict.should_continue else 'STOP'}"
              f" ({verdict.reason})")
        if verdict.should_reflect:
            print(f"   → Reflection recommended before next iteration")

    # ── 5. Final tension map ────────────────────────────────────
    if iter_result.final_map:
        print(f"\n{'=' * 64}")
        print("Final ResidualTensionMap")
        print(f"{'=' * 64}")
        print(format_residual_map(iter_result.final_map))

    # ── 6. Summary ──────────────────────────────────────────────
    first_trace = iter_result.results[0].trace
    last_trace = iter_result.results[-1].trace
    first_reached = DEFAULT_GOAL in first_trace.path
    last_reached = DEFAULT_GOAL in last_trace.path

    print(f"\n{'=' * 64}")
    print("Burnout Iterative — Summary")
    print(f"{'=' * 64}")
    print(f"  Iterations:     {iter_result.iterations} (emerged, not prescribed)")
    print(f"  Stop reason:    {iter_result.stop_reason}")
    print(f"  First run goal: {'REACHED' if first_reached else 'MISSED'}")
    print(f"  Last run goal:  {'REACHED' if last_reached else 'MISSED'}")
    if iter_result.final_map:
        print(f"  Final max S:    {iter_result.final_map.max_residual:.4f}")
        print(f"  Final mean S:   {iter_result.final_map.mean_residual:.4f}")
    print(f"\n  Envelope: {ENVELOPE.summary()}")

    if not use_mock:
        print(f"\n  ⚠  Landscape was LLM-generated, not pre-designed.")
        print(f"     Iteration count emerged from tension structure.")


if __name__ == "__main__":
    use_mock = "--mock" in sys.argv
    run_iterative_demo(use_mock=use_mock)
