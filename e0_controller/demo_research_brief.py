"""
E₀ Demo — Scientific Paper → Research Brief (Phase 3c)
========================================================
Third open-domain test: the LLM bootstraps a state graph for
analysing a scientific paper abstract and producing a structured
research brief.

This domain was chosen because it:
  - requires semantic verdichtung (compression) — the LLM must
    decompose research logic into meaningful states,
  - is prüfbar (verifiable) — problem, method, results, limitations
    can be checked against the source text,
  - is structurally different from the previous process-centric
    domains (Invoice, Incident), testing whether 3b/3c generalise.

Usage:
    # With real API:
    python -m e0_controller.demo_research_brief

    # With mock (no API key needed):
    python -m e0_controller.demo_research_brief --mock

    # Custom paper abstract:
    python -m e0_controller.demo_research_brief --task "We present a novel ..."

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
    "Analyze the following paper abstract and produce a structured research "
    "brief for a technical audience.\n\n"
    "ABSTRACT: We present a transformer-based architecture for low-resource "
    "machine translation that combines pre-trained multilingual embeddings "
    "with a novel cross-lingual attention mechanism. On four language pairs "
    "with fewer than 100k parallel sentences, our method improves BLEU scores "
    "by 3.2–5.8 points over strong baselines, including back-translation and "
    "transfer learning from related high-resource pairs. Ablation studies "
    "show that the cross-lingual attention layer contributes 60% of the gain, "
    "while the remaining improvement comes from curriculum-based fine-tuning. "
    "Limitations include degraded performance on morphologically rich targets "
    "and reliance on a multilingual pre-training corpus that may not cover "
    "all low-resource languages equally. We release code and models.\n\n"
    "The brief should cover: research problem, method, key results, "
    "limitations, implications, and open questions."
)
DEFAULT_START = "RAW_PAPER_TEXT"
DEFAULT_GOAL = "RESEARCH_BRIEF_DELIVERED"


# ──────────────────────────────────────────────
# Mock LLM for --mock mode
# ──────────────────────────────────────────────

def mock_llm_call(system: str, user: str, config: LLMConfig) -> str:
    """Deterministic mock for research-brief demo.

    Models 11 states (8 happy-path + 3 recovery) and 13 edges.
    """
    import json as _json

    if "design the complete state graph" in user:
        return _json.dumps({
            "states": [
                # Happy path
                "RAW_PAPER_TEXT",
                "ABSTRACT_PARSED",
                "PROBLEM_IDENTIFIED",
                "METHOD_EXTRACTED",
                "RESULTS_EXTRACTED",
                "LIMITATIONS_IDENTIFIED",
                "IMPLICATIONS_DRAFTED",
                "BRIEF_ASSEMBLED",
                "RESEARCH_BRIEF_DELIVERED",
                # Recovery / error states
                "METHOD_AMBIGUOUS",
                "RESULTS_INCOMPLETE",
                "HUMAN_REVIEW",
            ],
            "edges": [
                # ── Happy path ──
                {"source": "RAW_PAPER_TEXT", "target": "ABSTRACT_PARSED",
                 "delta": 0.2, "resistance": 0.3,
                 "description": "Parse abstract into structured sections (objective, method, results)."},
                {"source": "ABSTRACT_PARSED", "target": "PROBLEM_IDENTIFIED",
                 "delta": 0.3, "resistance": 0.5,
                 "description": "Identify the core research problem and motivation."},
                {"source": "PROBLEM_IDENTIFIED", "target": "METHOD_EXTRACTED",
                 "delta": 0.4, "resistance": 0.7,
                 "description": "Extract the proposed method, architecture, and key innovations."},
                {"source": "METHOD_EXTRACTED", "target": "RESULTS_EXTRACTED",
                 "delta": 0.5, "resistance": 0.8,
                 "description": "Extract quantitative results, metrics, and comparisons."},
                {"source": "RESULTS_EXTRACTED", "target": "LIMITATIONS_IDENTIFIED",
                 "delta": 0.3, "resistance": 0.6,
                 "description": "Identify stated limitations and potential weaknesses."},
                {"source": "LIMITATIONS_IDENTIFIED", "target": "IMPLICATIONS_DRAFTED",
                 "delta": 0.4, "resistance": 0.7,
                 "description": "Draft implications for the field and open questions."},
                {"source": "IMPLICATIONS_DRAFTED", "target": "BRIEF_ASSEMBLED",
                 "delta": 0.2, "resistance": 0.4,
                 "description": "Assemble all sections into a coherent research brief."},
                {"source": "BRIEF_ASSEMBLED", "target": "RESEARCH_BRIEF_DELIVERED",
                 "delta": 0.1, "resistance": 0.2,
                 "description": "Final review and delivery of research brief."},
                # ── Error / recovery paths ──
                {"source": "PROBLEM_IDENTIFIED", "target": "METHOD_AMBIGUOUS",
                 "delta": 0.3, "resistance": 1.2,
                 "description": "Method description is unclear or uses non-standard terminology."},
                {"source": "METHOD_AMBIGUOUS", "target": "METHOD_EXTRACTED",
                 "delta": 0.4, "resistance": 1.0,
                 "description": "Re-read with domain context, extract method with caveats."},
                {"source": "METHOD_EXTRACTED", "target": "RESULTS_INCOMPLETE",
                 "delta": 0.3, "resistance": 1.3,
                 "description": "Key metrics missing or results only partially reported."},
                {"source": "RESULTS_INCOMPLETE", "target": "HUMAN_REVIEW",
                 "delta": 0.4, "resistance": 1.8,
                 "description": "Escalate to human reviewer for missing data assessment."},
                {"source": "HUMAN_REVIEW", "target": "RESULTS_EXTRACTED",
                 "delta": 0.3, "resistance": 0.8,
                 "description": "Human provides clarification, resume with corrected results."},
            ],
        })

    if "Execute the transition" in user:
        return _json.dumps({
            "outcome": "SUCCESS",
            "result": "Transition completed successfully.",
            "confidence": 0.90,
        })

    if "Estimate the structural resistance" in user:
        return _json.dumps({
            "resistance": 0.7,
            "reasoning": "Research analysis transition with moderate complexity.",
        })

    # Default (extract_delta etc.)
    return _json.dumps({
        "delta": 0.35,
        "reasoning": "Moderate structural change in research analysis.",
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
    """Run research-brief demo with LLM-bootstrapped landscape."""

    print("=" * 64)
    print("E₀ Controller — Research Brief Demo (Phase 3c)")
    print("=" * 64)
    print(f"\nTask: {task[:120]}...")
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
    session_id = "demo-research-brief"

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
    for i, arg in enumerate(sys.argv):
        if arg == "--task" and i + 1 < len(sys.argv):
            task = sys.argv[i + 1]
    run_demo(task=task, use_mock=use_mock)
