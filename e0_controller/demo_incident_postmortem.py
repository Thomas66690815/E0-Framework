"""
E₀ Demo — Incident / Outage Postmortem Briefing (Phase 3b)
==============================================================
Second open-domain test: the LLM bootstraps a state graph for
analysing a raw incident report and producing a structured postmortem.

This domain was chosen because it is:
  - semantically open enough for the LLM-bootstrap to be meaningful,
  - structurally rigid enough to be empirically verifiable
    (timeline, trigger, root cause, impact, mitigations, follow-ups),
  - rich in natural error/recovery paths (incomplete logs, ambiguous
    cause, human review needed).

Usage:
    # With real API:
    python -m e0_controller.demo_incident_postmortem

    # With mock (no API key needed):
    python -m e0_controller.demo_incident_postmortem --mock

    # With hybrid amplitude controller (B3):
    python -m e0_controller.demo_incident_postmortem --mock --hybrid

    # Custom incident description:
    python -m e0_controller.demo_incident_postmortem --task "Database cluster failed over due to disk saturation"

Requires OPENAI_API_KEY in .env or environment (unless --mock).
"""

from __future__ import annotations

import json
import os
import sys

from e0_controller.controller import E0Controller, HybridMode
from e0_controller.memory_os import E0MemoryOS, CanonRef, edge_to_key
from e0_controller.primitives import Edge
from e0_controller.tension import coherence
from e0_controller.llm_adapter import (
    E0LLMAdapter,
    LLMConfig,
    LandscapeProposal,
    materialize_landscape,
    task_map_from_proposal,
)
from e0_controller.graph_validation import graph_quality
from e0_controller.scenario_loader import ScenarioPacket, load_scenario, find_scenario


# ──────────────────────────────────────────────
# Default task
# ──────────────────────────────────────────────

DEFAULT_TASK = (
    "A production payment-processing service experienced a 47-minute outage "
    "during peak hours. The monitoring dashboard showed elevated error rates "
    "starting at 14:02 UTC, followed by full service unavailability at 14:11 UTC. "
    "The service was restored at 14:58 UTC via a rollback of the most recent "
    "deployment. Preliminary indicators point to a database connection pool "
    "exhaustion caused by a missing index on a newly deployed query path. "
    "Produce a structured postmortem briefing that covers: incident timeline, "
    "trigger identification, root cause analysis, impact assessment, "
    "mitigations applied, and follow-up actions."
)
DEFAULT_START = "RAW_INCIDENT_REPORT"
DEFAULT_GOAL = "POSTMORTEM_DELIVERED"


# ──────────────────────────────────────────────
# Mock LLM for --mock mode
# ──────────────────────────────────────────────

def mock_llm_call(system: str, user: str, config: LLMConfig) -> str:
    """Deterministic mock for incident-postmortem demo.

    The mock landscape models 12 states (8 happy-path + 4 recovery)
    and 15 edges including natural error/retry loops.
    """
    import json as _json

    if "design the complete state graph" in user:
        return _json.dumps({
            "states": [
                # Happy path
                "RAW_INCIDENT_REPORT",
                "TIMELINE_PARSED",
                "IMPACT_IDENTIFIED",
                "TRIGGER_HYPOTHESIZED",
                "ROOT_CAUSE_ANALYZED",
                "MITIGATIONS_IDENTIFIED",
                "FOLLOWUPS_DRAFTED",
                "POSTMORTEM_ASSEMBLED",
                "POSTMORTEM_DELIVERED",
                # Recovery / error states
                "TIMELINE_INCOMPLETE",
                "LOGS_INSUFFICIENT",
                "CAUSE_AMBIGUOUS",
                "HUMAN_REVIEW",
            ],
            "edges": [
                # ── Happy path ──
                {"source": "RAW_INCIDENT_REPORT", "target": "TIMELINE_PARSED",
                 "delta": 0.3, "resistance": 0.5,
                 "description": "Extract chronological event sequence from the raw report."},
                {"source": "TIMELINE_PARSED", "target": "IMPACT_IDENTIFIED",
                 "delta": 0.4, "resistance": 0.7,
                 "description": "Identify affected systems, users, and business impact."},
                {"source": "IMPACT_IDENTIFIED", "target": "TRIGGER_HYPOTHESIZED",
                 "delta": 0.5, "resistance": 0.9,
                 "description": "Formulate hypothesis for the immediate trigger event."},
                {"source": "TRIGGER_HYPOTHESIZED", "target": "ROOT_CAUSE_ANALYZED",
                 "delta": 0.6, "resistance": 1.1,
                 "description": "Perform root cause analysis tracing trigger to underlying fault."},
                {"source": "ROOT_CAUSE_ANALYZED", "target": "MITIGATIONS_IDENTIFIED",
                 "delta": 0.4, "resistance": 0.8,
                 "description": "Identify mitigations applied during incident and their effectiveness."},
                {"source": "MITIGATIONS_IDENTIFIED", "target": "FOLLOWUPS_DRAFTED",
                 "delta": 0.3, "resistance": 0.6,
                 "description": "Draft follow-up action items with owners and deadlines."},
                {"source": "FOLLOWUPS_DRAFTED", "target": "POSTMORTEM_ASSEMBLED",
                 "delta": 0.3, "resistance": 0.4,
                 "description": "Assemble all sections into structured postmortem document."},
                {"source": "POSTMORTEM_ASSEMBLED", "target": "POSTMORTEM_DELIVERED",
                 "delta": 0.1, "resistance": 0.2,
                 "description": "Final review card and delivery to stakeholders."},
                # ── Error / recovery paths ──
                {"source": "RAW_INCIDENT_REPORT", "target": "TIMELINE_INCOMPLETE",
                 "delta": 0.3, "resistance": 1.5,
                 "description": "Report lacks timestamps or contains inconsistent chronology."},
                {"source": "TIMELINE_INCOMPLETE", "target": "LOGS_INSUFFICIENT",
                 "delta": 0.2, "resistance": 1.8,
                 "description": "Attempt to fill gaps from logs but logs are also incomplete."},
                {"source": "LOGS_INSUFFICIENT", "target": "HUMAN_REVIEW",
                 "delta": 0.4, "resistance": 2.0,
                 "description": "Escalate to human operator for manual timeline reconstruction."},
                {"source": "HUMAN_REVIEW", "target": "TIMELINE_PARSED",
                 "delta": 0.3, "resistance": 0.8,
                 "description": "Human provides corrected timeline, resume normal flow."},
                {"source": "TIMELINE_INCOMPLETE", "target": "TIMELINE_PARSED",
                 "delta": 0.4, "resistance": 1.2,
                 "description": "Best-effort timeline reconstruction with caveats noted."},
                # ── Root-cause ambiguity loop ──
                {"source": "TRIGGER_HYPOTHESIZED", "target": "CAUSE_AMBIGUOUS",
                 "delta": 0.4, "resistance": 1.6,
                 "description": "Multiple plausible triggers, cannot isolate single cause."},
                {"source": "CAUSE_AMBIGUOUS", "target": "ROOT_CAUSE_ANALYZED",
                 "delta": 0.5, "resistance": 1.4,
                 "description": "Narrow hypotheses via elimination, document uncertainty."},
            ],
        })

    if "Execute the transition" in user:
        return _json.dumps({
            "outcome": "SUCCESS",
            "result": "Transition completed successfully.",
            "confidence": 0.85,
        })

    if "Estimate the structural resistance" in user:
        return _json.dumps({
            "resistance": 0.9,
            "reasoning": "Incident analysis transition with moderate uncertainty.",
        })

    # Default (extract_delta etc.)
    return _json.dumps({
        "delta": 0.45,
        "reasoning": "Moderate structural change in incident analysis.",
    })


# ──────────────────────────────────────────────
# Main Demo
# ──────────────────────────────────────────────

def run_demo(
    task: str = DEFAULT_TASK,
    start: str = DEFAULT_START,
    goal: str = DEFAULT_GOAL,
    use_mock: bool = False,
    use_hybrid: bool = False,
    scenario: ScenarioPacket | None = None,
):
    """Run incident-postmortem demo with LLM-bootstrapped landscape."""

    # Override from scenario packet if provided
    if scenario:
        task = f"{scenario.objective}\n\nSource material:\n{scenario.source_text}"
        start = scenario.start_state or start
        goal = scenario.goal_state or goal

    print("=" * 64)
    print("E₀ Controller — Incident Postmortem Demo (Phase 3b)")
    print("=" * 64)
    if scenario:
        print(f"\nScenario: {scenario.title} [{scenario.scenario_id}]")
    print(f"\nTask: {task[:200]}{'...' if len(task) > 200 else ''}")
    print(f"Start: {start} → Goal: {goal}")

    # 1. Setup LLM adapter
    if use_mock:
        print("\nMode: MOCK (no API calls)")
        adapter = E0LLMAdapter(call_fn=mock_llm_call)
    else:
        config = LLMConfig(model="gpt-5.4-mini", temperature=0.3)
        adapter = E0LLMAdapter(config=config)
        print(f"\nMode: LIVE (model={config.model})")
    if use_hybrid:
        print("Hybrid: AMPLITUDE_ON_DISAGREE (B3)")

    # 2. LLM designs the landscape
    print("\n── Step 1: LLM designs state graph ──")
    sc_block = scenario.as_prompt_block() if scenario else ""
    proposal = adapter.build_landscape(task, start, goal, scenario_block=sc_block)
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

    # 5. Create execute function with live summary (uses actual source state)
    session_id = "demo-incident-postmortem"
    _recent: list = []  # tracks recent states during run
    _ctrl_ref: list = [None]

    def live_summary(source: str):
        """Build LLM context from the actual source state per call."""
        neighbors = L.admissible_neighbors(source)
        neighbor_info = {}
        for n in neighbors:
            s_eff = L.effective_tension(source, n)
            neighbor_info[n] = {
                "s_eff": round(s_eff, 4),
                "coherence": round(coherence(s_eff), 4),
                "v": round(L.transition_field(source, n), 4),
            }
        edge_history = {}
        for n in neighbors:
            e = Edge(source, n)
            ek = edge_to_key(e)
            edge_history[ek] = {
                "delta_H": round(L.historization.delta_H(e), 4),
            }
        _recent.append(source)
        summary = {
            "current_state": source,
            "admissible_neighbors": neighbor_info,
            "edge_history": edge_history,
            "runtime": {"recent_states": _recent[-5:]},
        }
        if _ctrl_ref[0] is not None and _ctrl_ref[0].hybrid_mode != HybridMode.GREEDY:
            ov = memos._build_overlay_summary(_ctrl_ref[0], source)
            if ov:
                summary["amplitude_overlay"] = ov
        return summary

    execute_fn = adapter.as_execute_fn(
        task_map, live_summary=live_summary,
        scenario_block=sc_block,
        result_log=(result_log := []),
    )

    # 6. Build controller and run
    print("\n── Step 2: Controller runs ──")
    hybrid_mode = HybridMode.AMPLITUDE_ON_DISAGREE if use_hybrid else HybridMode.GREEDY
    ctrl = E0Controller(L, execute_fn, alpha=2.0, recent_k=3,
                        hybrid_mode=hybrid_mode,
                        hybrid_goals={goal} if use_hybrid else None)
    _ctrl_ref[0] = ctrl
    trace = ctrl.run(start=start, goal=goal, max_cycles=25)

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
    if hybrid_mode != HybridMode.GREEDY:
        print(f"  Hybrid overrides:  {int(metrics['hybrid_override_count'])}")
        print(f"  Override rate:     {metrics['hybrid_override_rate']:.0%}")

    # 7b. Display LLM results per step
    if result_log:
        print(f"\n── Transition Details ──")
        for i, (step, res) in enumerate(zip(trace.steps, result_log)):
            esc = " [ESCALATION]" if step.escalated else ""
            print(f"\n  Step {i+1}: {step.source} → {step.target}{esc}")
            print(f"    Outcome:    {step.outcome.name} (confidence: {res.confidence:.0%})")
            print(f"    S_eff:      {step.s_eff:.4f}")
            if res.result:
                text = res.result[:200] + ("..." if len(res.result) > 200 else "")
                print(f"    LLM Result: {text}")

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

    return trace, proposal, result_log


if __name__ == "__main__":
    use_mock = "--mock" in sys.argv
    use_hybrid = "--hybrid" in sys.argv
    task = DEFAULT_TASK
    sc = None
    for i, arg in enumerate(sys.argv):
        if arg == "--scenario" and i + 1 < len(sys.argv):
            sc = load_scenario(sys.argv[i + 1])
        elif arg == "--task" and i + 1 < len(sys.argv):
            task = sys.argv[i + 1]
    if sc is None and task == DEFAULT_TASK:
        path = find_scenario("incident_postmortem")
        if path:
            sc = load_scenario(path)
    run_demo(task=task, use_mock=use_mock, use_hybrid=use_hybrid, scenario=sc)
