"""
E₀ Session Runner (C165)
=========================
Unified entry point that wires ALL existing pieces end-to-end:

  Bootstrap → Controller → Intents → UI → Feedback → Save

This is the piece that was missing: a single command that takes a task,
runs E0 on it, shows the result in a browser, and persists everything
for the next run.

Lifecycle:
    1. Load or create perception domain (C164 pretrained or fresh)
    2. Load or bootstrap task landscape (LLM-generated or scenario)
    3. Run Session.iterate() — E0 navigates the landscape
    4. Detect communication intents from the result (C159)
    5. Emit UI specification (C160)
    6. Render HTML and open in browser (C163)
    7. Save perception domain for next time

Usage:
    # First run (mock, no API key needed):
    py -3 -m e0_controller.e0_session --mock

    # Live LLM:
    py -3 -m e0_controller.e0_session

    # Custom task:
    py -3 -m e0_controller.e0_session --task "Design a REST API for a bookstore"

    # With scenario:
    py -3 -m e0_controller.e0_session --scenario scenarios/competitor_brief

    # Resume previous session:
    py -3 -m e0_controller.e0_session --resume my-session-id

    # Skip browser:
    py -3 -m e0_controller.e0_session --mock --no-browser
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .communication import detect_intents, IntentReport
from .feedback import HumanAction, ingest_feedback, FeedbackResult
from .llm_adapter import E0LLMAdapter, LLMConfig, LLMCallFn
from .perception import PerceptionDomain, build_perception_domain
from .primitives import Outcome, Edge
from .scenario_loader import ScenarioPacket, load_scenario, find_scenario
from .self_graph import SelfGraph
from .ui_emitter import emit_ui_spec, UISpec
from .ui_renderer import render_and_open, render_to_file

from . import (
    Landscape,
    Session,
    HybridMode,
    E0Envelope,
    TransportRegime,
    ExplorationPolicy,
    CanonRef,
    materialize_landscape,
    task_map_from_proposal,
    graph_quality,
    format_residual_map,
)


# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

MEMO_DIR = "memos"
PERCEPTION_MEMO = os.path.join(MEMO_DIR, "perception_pretrained.json")
SESSION_BASE = os.path.join(MEMO_DIR, "sessions")

DEFAULT_TASK = (
    "Analyze a competitor's product announcement and produce a structured "
    "briefing for the executive team."
)
DEFAULT_START = "RAW_ANNOUNCEMENT"
DEFAULT_GOAL = "BRIEFING_DELIVERED"

DEFAULT_ENVELOPE = E0Envelope(
    mode=HybridMode.AMPLITUDE_ON_DISAGREE,
    geometry="goal_reaching",
    horizon=4,
    transport=TransportRegime.U1,
    goals=frozenset({DEFAULT_GOAL}),
    alpha=0.5,
)

DEFAULT_POLICY = ExplorationPolicy.born_warmup(
    warmup=2,
    convergence_threshold=0.15,
)


# ──────────────────────────────────────────────
# Session Result
# ──────────────────────────────────────────────

@dataclass
class E0SessionResult:
    """Complete result of an end-to-end E0 session run."""
    session_id: str
    task: str
    iterations: int
    stop_reason: str
    goal_reached: bool
    intent_report: IntentReport
    ui_spec: UISpec
    html_path: Optional[Path]
    perception_saved: Optional[Path]
    resumed: bool

    def summary(self) -> str:
        lines = [
            f"Session: {self.session_id}",
            f"Task: {self.task[:80]}{'...' if len(self.task) > 80 else ''}",
            f"Iterations: {self.iterations} ({self.stop_reason})",
            f"Goal: {'REACHED' if self.goal_reached else 'MISSED'}",
            f"Intents: {len(self.intent_report.intents)}",
            f"UI Panels: {self.ui_spec.panel_count}",
        ]
        if self.html_path:
            lines.append(f"HTML: {self.html_path}")
        if self.perception_saved:
            lines.append(f"Perception saved: {self.perception_saved}")
        if self.resumed:
            lines.append("(Resumed from previous run)")
        return "\n".join(lines)


# ──────────────────────────────────────────────
# Mock LLM for testing
# ──────────────────────────────────────────────

def _mock_llm_call(system: str, user: str, config: LLMConfig) -> str:
    """Deterministic mock for end-to-end testing."""
    if "design the complete state graph" in user:
        return json.dumps({
            "states": [
                "RAW_ANNOUNCEMENT", "TEXT_PARSED", "KEY_FACTS_EXTRACTED",
                "MARKET_CONTEXT_GATHERED", "IMPACT_ASSESSED",
                "RESPONSES_DRAFTED", "BRIEFING_ASSEMBLED", "BRIEFING_DELIVERED",
            ],
            "edges": [
                {"source": "RAW_ANNOUNCEMENT", "target": "TEXT_PARSED",
                 "delta": 0.3, "resistance": 0.4,
                 "description": "Parse announcement into sections."},
                {"source": "TEXT_PARSED", "target": "KEY_FACTS_EXTRACTED",
                 "delta": 0.5, "resistance": 0.8,
                 "description": "Extract key facts."},
                {"source": "KEY_FACTS_EXTRACTED", "target": "MARKET_CONTEXT_GATHERED",
                 "delta": 0.4, "resistance": 1.0,
                 "description": "Research market context."},
                {"source": "MARKET_CONTEXT_GATHERED", "target": "IMPACT_ASSESSED",
                 "delta": 0.6, "resistance": 1.2,
                 "description": "Assess strategic impact."},
                {"source": "IMPACT_ASSESSED", "target": "RESPONSES_DRAFTED",
                 "delta": 0.5, "resistance": 1.0,
                 "description": "Draft response options."},
                {"source": "RESPONSES_DRAFTED", "target": "BRIEFING_ASSEMBLED",
                 "delta": 0.3, "resistance": 0.5,
                 "description": "Assemble briefing document."},
                {"source": "BRIEFING_ASSEMBLED", "target": "BRIEFING_DELIVERED",
                 "delta": 0.2, "resistance": 0.3,
                 "description": "Final review and delivery."},
            ],
        })

    if "Execute the transition" in user:
        return json.dumps({
            "outcome": "SUCCESS",
            "result": "Transition completed.",
            "confidence": 0.88,
        })

    return json.dumps({"delta": 0.4, "reasoning": "Moderate change."})


# ──────────────────────────────────────────────
# Core Session Runner
# ──────────────────────────────────────────────

def run_session(
    *,
    task: str = DEFAULT_TASK,
    start: str = DEFAULT_START,
    goal: str = DEFAULT_GOAL,
    session_id: str = "e0-session",
    use_mock: bool = False,
    scenario: Optional[ScenarioPacket] = None,
    envelope: Optional[E0Envelope] = None,
    policy: Optional[ExplorationPolicy] = None,
    perception_path: Optional[str] = None,
    open_browser: bool = True,
    max_iterations: int = 5,
    resume: bool = False,
) -> E0SessionResult:
    """Run a complete E0 session: bootstrap → navigate → communicate → save.

    Args:
        task: What E0 should work on (natural language).
        start: Start state name.
        goal: Goal state name.
        session_id: Identifier for memo persistence.
        use_mock: Use deterministic mock instead of live LLM.
        scenario: Optional scenario packet for structured tasks.
        envelope: E0 controller envelope. Defaults to amplitude-on-disagree.
        policy: Exploration policy. Defaults to Born warmup.
        perception_path: Path to pretrained perception. Auto-detects if None.
        open_browser: Open the rendered UI in the default browser.
        max_iterations: Maximum iteration rounds.
        resume: Resume a previous session from disk.

    Returns:
        E0SessionResult with full pipeline output.
    """
    if envelope is None:
        envelope = E0Envelope(
            mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            geometry="goal_reaching",
            horizon=4,
            transport=TransportRegime.U1,
            goals=frozenset({goal}),
            alpha=0.5,
        )
    if policy is None:
        policy = DEFAULT_POLICY

    # Override from scenario
    if scenario:
        task = f"{scenario.objective}\n\n{scenario.source_text}"
        start = scenario.start_state or start
        goal = scenario.goal_state or goal
        if not session_id or session_id == "e0-session":
            session_id = scenario.scenario_id

    _print(f"{'='*60}")
    _print(f"  E₀ Session Runner")
    _print(f"{'='*60}")
    _print(f"  Task: {task[:100]}{'...' if len(task) > 100 else ''}")
    _print(f"  Start: {start} → Goal: {goal}")
    _print(f"  Session: {session_id}")

    # ── 1. Load or create perception ─────────────────────
    _print(f"\n[1] Perception Domain")
    domain = _load_perception(perception_path)

    # ── 2. Build or resume session ───────────────────────
    _print(f"\n[2] Task Landscape")
    if resume:
        session, was_resumed = _resume_session(session_id, use_mock)
    else:
        session, was_resumed = _bootstrap_session(
            task, start, goal, session_id, use_mock, scenario, envelope,
        )

    # ── 3. Run the controller ────────────────────────────
    _print(f"\n[3] Running E0 Controller")
    _print(f"    Mode: {'MOCK' if use_mock else 'LIVE'}")
    _print(f"    Policy: {policy.label}")

    iter_result = session.iterate(
        start,
        goal=goal,
        max_cycles=20,
        max_iterations=max_iterations,
        tension_threshold=0.15,
        exploration_policy=policy,
    )

    last_trace = iter_result.results[-1].trace
    goal_reached = goal in last_trace.path

    _print(f"    Iterations: {iter_result.iterations} ({iter_result.stop_reason})")
    _print(f"    Goal: {'REACHED' if goal_reached else 'MISSED'}")

    for i, res in enumerate(iter_result.results, 1):
        path_str = " → ".join(res.trace.path)
        m = res.trace.metrics()
        _print(f"    [{i}] {path_str}")
        _print(f"        Steps: {int(m['steps'])}, "
               f"Success: {m['success_rate']:.0%}, "
               f"Tension: {m['avg_tension']:.4f}")

    # ── 4. Detect intents ────────────────────────────────
    _print(f"\n[4] Communication Intents")
    last_session_result = iter_result.results[-1]
    last_step = last_session_result.trace.steps[-1] if last_session_result.trace.steps else None
    report = detect_intents(
        self_graph=session.self_graph,
        step_result=last_step,
        include_status=True,
    )
    _print(f"    {report.summary()}")
    for intent in report.intents:
        _print(f"    • [{intent.type.value:12s}] "
               f"urgency={intent.urgency:.2f}  {intent.summary}")

    # ── 5. Emit UI spec ─────────────────────────────────
    _print(f"\n[5] UI Specification")
    spec = emit_ui_spec(
        report, domain,
        context=f"Session '{session_id}': {task[:60]}",
    )
    _print(f"    Layout: {spec.layout}")
    _print(f"    Panels: {spec.panel_count}")
    for i, panel in enumerate(spec.panels):
        _print(f"      [{i}] {panel.intent:12s} → "
               f"{panel.perception:10s} via {panel.suggested_visual:10s} "
               f"({panel.language_act}) urgency={panel.urgency:.2f}")

    # ── 6. Render UI ─────────────────────────────────────
    _print(f"\n[6] Rendering")
    html_path = None
    html_file = f"e0_session_{session_id}.html"
    if open_browser:
        html_path = render_and_open(
            spec, html_file,
            title=f"E₀ — {session_id}",
        )
        _print(f"    Opened: {html_path}")
    else:
        html_path = render_to_file(spec, html_file,
                                   title=f"E₀ — {session_id}")
        _print(f"    Written: {html_path}")

    # ── 7. Save perception ───────────────────────────────
    _print(f"\n[7] Saving State")
    save_path = domain.save_state(PERCEPTION_MEMO)
    _print(f"    Perception: {save_path}")

    _print(f"\n{'='*60}")
    _print(f"  Session complete.")
    _print(f"{'='*60}")

    return E0SessionResult(
        session_id=session_id,
        task=task,
        iterations=iter_result.iterations,
        stop_reason=iter_result.stop_reason,
        goal_reached=goal_reached,
        intent_report=report,
        ui_spec=spec,
        html_path=html_path,
        perception_saved=save_path,
        resumed=was_resumed,
    )


# ──────────────────────────────────────────────
# Internal Helpers
# ──────────────────────────────────────────────

def _print(msg: str) -> None:
    print(msg)


def _load_perception(path: Optional[str]) -> PerceptionDomain:
    """Load pretrained perception or build fresh."""
    if path is None:
        path = PERCEPTION_MEMO

    if os.path.exists(path):
        domain = PerceptionDomain.from_saved(path)
        snap = domain.snapshot()
        _print(f"    Loaded from: {path}")
        _print(f"    {len(domain.primitives)} primitives, "
               f"total load={snap.total_load:.0f}")
        return domain

    _print(f"    No pretrained perception found at: {path}")
    _print(f"    Building fresh domain (cold start)")
    domain = build_perception_domain()
    _print(f"    {len(domain.primitives)} primitives, "
           f"{len(domain.landscape.edges)} edges")
    return domain


def _bootstrap_session(
    task: str,
    start: str,
    goal: str,
    session_id: str,
    use_mock: bool,
    scenario: Optional[ScenarioPacket],
    envelope: E0Envelope,
) -> tuple:
    """Create a new session with LLM-bootstrapped landscape."""
    if use_mock:
        adapter = E0LLMAdapter(call_fn=_mock_llm_call)
        _print(f"    Mode: MOCK (deterministic)")
    else:
        config = LLMConfig(model="gpt-4.1-mini", temperature=0.3, max_tokens=2048)
        adapter = E0LLMAdapter(config=config)
        _print(f"    Mode: LIVE ({config.model})")

    sc_block = scenario.as_prompt_block() if scenario else ""
    proposal = adapter.build_landscape(
        task, start, goal,
        goals=set(envelope.goals) if envelope.goals else None,
        scenario_block=sc_block,
    )
    L = materialize_landscape(proposal)
    task_map = task_map_from_proposal(proposal)

    _print(f"    States: {len(L.states)}, Edges: {len(L.edges)}")
    for e in proposal.edges:
        desc = e.get("description", "")[:50]
        _print(f"      {e['source']:25s} → {e['target']:25s}  {desc}")

    gq = graph_quality(L, start, goal)
    _print(f"    Graph quality: {gq.score:.2f}")

    execute_fn = adapter.as_execute_fn(task_map, scenario_block=sc_block)

    base = os.path.join(SESSION_BASE, session_id)
    session = Session(
        session_id=session_id,
        landscape=L,
        execute_fn=execute_fn,
        base_dir=base,
        canon_refs=[CanonRef("e0-canon", "v1", "canon/e0-canon-plain.txt")],
        controller_kwargs=envelope.to_controller_kwargs(),
    )

    return session, False


def _resume_session(
    session_id: str,
    use_mock: bool,
) -> tuple:
    """Resume a previously saved session."""
    base = os.path.join(SESSION_BASE, session_id)
    _print(f"    Resuming: {session_id}")

    if use_mock:
        execute_fn = _mock_llm_call_as_execute()
    else:
        config = LLMConfig(model="gpt-4.1-mini", temperature=0.3, max_tokens=2048)
        adapter = E0LLMAdapter(config=config)
        execute_fn = adapter.as_execute_fn({})

    session = Session.resume(
        session_id=session_id,
        execute_fn=execute_fn,
        base_dir=base,
    )
    _print(f"    Restored: {len(session.landscape.states)} states, "
           f"{len(session.landscape.edges)} edges")
    return session, True


def _mock_llm_call_as_execute():
    """Create a simple execute_fn from the mock."""
    def execute_fn(state, target):
        return Outcome.SUCCESS
    return execute_fn


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def main() -> None:
    """CLI entry point."""
    args = sys.argv[1:]
    use_mock = "--mock" in args
    no_browser = "--no-browser" in args
    do_resume = "--resume" in args

    task = DEFAULT_TASK
    start = DEFAULT_START
    goal = DEFAULT_GOAL
    session_id = "e0-session"
    scenario = None

    for i, arg in enumerate(args):
        if arg == "--task" and i + 1 < len(args):
            task = args[i + 1]
        elif arg == "--start" and i + 1 < len(args):
            start = args[i + 1]
        elif arg == "--goal" and i + 1 < len(args):
            goal = args[i + 1]
        elif arg == "--session" and i + 1 < len(args):
            session_id = args[i + 1]
        elif arg == "--scenario" and i + 1 < len(args):
            sc_arg = args[i + 1]
            if os.path.isfile(sc_arg):
                scenario = load_scenario(sc_arg)
            elif os.path.isdir(sc_arg):
                # scenarios/competitor_brief → find first JSON
                files = [f for f in sorted(os.listdir(sc_arg))
                         if f.endswith(".json")]
                if files:
                    scenario = load_scenario(os.path.join(sc_arg, files[0]))
            else:
                # Try as domain name
                path = find_scenario(sc_arg)
                if path:
                    scenario = load_scenario(path)
            if scenario is None:
                print(f"Warning: Scenario '{sc_arg}' not found, proceeding without.")

    if do_resume:
        # --resume expects the session ID as next arg
        for i, arg in enumerate(args):
            if arg == "--resume" and i + 1 < len(args):
                session_id = args[i + 1]
                break

    run_session(
        task=task,
        start=start,
        goal=goal,
        session_id=session_id,
        use_mock=use_mock,
        scenario=scenario,
        open_browser=not no_browser,
        resume=do_resume,
    )


if __name__ == "__main__":
    main()
