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

    # Text output (no browser):
    py -3 -m e0_controller.e0_session --mock --format text

    # Markdown export:
    py -3 -m e0_controller.e0_session --mock --format markdown
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
from .text_renderer import render_text, render_markdown, render_to_text_file
from .evidence_interpreter import interpret_panel

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

_DERIVE_ENDPOINTS_SYSTEM = """\
You derive start and goal states for a task processing pipeline.
State names must be UPPER_CASE_WITH_UNDERSCORES, descriptive of the task."""

_DERIVE_ENDPOINTS_PROMPT = """\
Given this task, determine the appropriate start state (initial input/situation) \
and goal state (final deliverable/outcome).

Task: {task}

Respond with exactly this JSON (no other text):
{{"start": "START_STATE_NAME", "goal": "GOAL_STATE_NAME"}}"""

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
    output_path: Optional[Path]
    output_format: str
    perception_saved: Optional[Path]
    resumed: bool
    text_output: Optional[str] = None

    @property
    def html_path(self) -> Optional[Path]:
        """Backward-compatible alias."""
        return self.output_path if self.output_format == "html" else None

    def summary(self) -> str:
        lines = [
            f"Session: {self.session_id}",
            f"Task: {self.task[:80]}{'...' if len(self.task) > 80 else ''}",
            f"Iterations: {self.iterations} ({self.stop_reason})",
            f"Goal: {'REACHED' if self.goal_reached else 'MISSED'}",
            f"Intents: {len(self.intent_report.intents)}",
            f"UI Panels: {self.ui_spec.panel_count}",
            f"Format: {self.output_format}",
        ]
        if self.output_path:
            lines.append(f"Output: {self.output_path}")
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
        # Extract start/goal from prompt to produce matching landscape
        import re
        m_start = re.search(r"Start state:\s*(\S+)", user)
        m_goal = re.search(r"Goal state:\s*(\S+)", user)
        start = m_start.group(1) if m_start else "RAW_ANNOUNCEMENT"
        goal = m_goal.group(1) if m_goal else "BRIEFING_DELIVERED"
        return json.dumps({
            "states": [
                start, "STEP_PARSE", "STEP_EXTRACT",
                "STEP_CONTEXT", "STEP_ASSESS",
                "STEP_DRAFT", "STEP_ASSEMBLE", goal,
            ],
            "edges": [
                {"source": start, "target": "STEP_PARSE",
                 "delta": 0.3, "resistance": 0.4,
                 "description": "Parse input into sections."},
                {"source": "STEP_PARSE", "target": "STEP_EXTRACT",
                 "delta": 0.5, "resistance": 0.8,
                 "description": "Extract key elements."},
                {"source": "STEP_EXTRACT", "target": "STEP_CONTEXT",
                 "delta": 0.4, "resistance": 1.0,
                 "description": "Gather context."},
                {"source": "STEP_CONTEXT", "target": "STEP_ASSESS",
                 "delta": 0.6, "resistance": 1.2,
                 "description": "Assess situation."},
                {"source": "STEP_ASSESS", "target": "STEP_DRAFT",
                 "delta": 0.5, "resistance": 1.0,
                 "description": "Draft response."},
                {"source": "STEP_DRAFT", "target": "STEP_ASSEMBLE",
                 "delta": 0.3, "resistance": 0.5,
                 "description": "Assemble output."},
                {"source": "STEP_ASSEMBLE", "target": goal,
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
    start: Optional[str] = None,
    goal: Optional[str] = None,
    session_id: str = "e0-session",
    use_mock: bool = False,
    scenario: Optional[ScenarioPacket] = None,
    envelope: Optional[E0Envelope] = None,
    policy: Optional[ExplorationPolicy] = None,
    perception_path: Optional[str] = None,
    open_browser: bool = True,
    max_iterations: int = 5,
    resume: bool = False,
    output_format: str = "html",
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
        output_format: "html" (default), "text", or "markdown".

    Returns:
        E0SessionResult with full pipeline output.
    """
    if policy is None:
        policy = DEFAULT_POLICY

    # Override from scenario
    if scenario:
        task = f"{scenario.objective}\n\n{scenario.source_text}"
        start = scenario.start_state or start
        goal = scenario.goal_state or goal
        if not session_id or session_id == "e0-session":
            session_id = scenario.scenario_id

    # Derive start/goal from task when not provided
    if start is None or goal is None:
        if use_mock:
            derived_start, derived_goal = _mock_derive_endpoints(task)
        else:
            config = LLMConfig(model="gpt-4.1-mini", temperature=0.2)
            from .llm_adapter import openai_call
            derived_start, derived_goal = _derive_endpoints(
                task, openai_call, config,
            )
        if start is None:
            start = derived_start
        if goal is None:
            goal = derived_goal

    if envelope is None:
        envelope = E0Envelope(
            mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            geometry="goal_reaching",
            horizon=4,
            transport=TransportRegime.U1,
            goals=frozenset({goal}),
            alpha=0.5,
        )

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
    last_step = last_trace.steps[-1] if last_trace.steps else None
    report = detect_intents(
        self_graph=session.self_graph,
        step_result=last_step,
        landscape=session.landscape,
        trace=last_trace,
        goal=goal,
        task_description=task,
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

    # ── 6. Render output ─────────────────────────────────
    _print(f"\n[6] Rendering ({output_format})")
    output_path = None
    text_output = None
    title = f"E₀ — {session_id}"

    if output_format == "text":
        text_output = render_text(spec, title=title)
        # Append panel interpretations
        interp_lines = ["\n--- Interpretations ---"]
        for panel in spec.panels:
            interp_lines.append(interpret_panel(panel))
            interp_lines.append("")
        text_output += "\n".join(interp_lines)
        out_file = f"e0_session_{session_id}.txt"
        output_path = render_to_text_file(spec, out_file, title=title, fmt="text")
        _print(f"    Written: {output_path}")
        _print(text_output)
    elif output_format == "markdown":
        text_output = render_markdown(spec, title=title)
        # Append panel interpretations as section
        interp_lines = ["\n## Interpretations\n"]
        for panel in spec.panels:
            interp_lines.append(f"### {panel.label}\n")
            interp_lines.append(interpret_panel(panel))
            interp_lines.append("")
        text_output += "\n".join(interp_lines)
        out_file = f"e0_session_{session_id}.md"
        output_path = render_to_text_file(spec, out_file, title=title, fmt="markdown")
        _print(f"    Written: {output_path}")
    else:
        # HTML (default)
        html_file = f"e0_session_{session_id}.html"
        if open_browser:
            output_path = render_and_open(
                spec, html_file, title=title,
            )
            _print(f"    Opened: {output_path}")
        else:
            output_path = render_to_file(
                spec, html_file, title=title,
            )
            _print(f"    Written: {output_path}")

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
        output_path=output_path,
        output_format=output_format,
        perception_saved=save_path,
        resumed=was_resumed,
        text_output=text_output,
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


def _derive_endpoints(
    task: str,
    llm_call: LLMCallFn,
    config: LLMConfig,
) -> tuple:
    """Ask the LLM to derive appropriate start/goal states from a task."""
    from .llm_adapter import _parse_json_response, _normalize_state_name
    prompt = _DERIVE_ENDPOINTS_PROMPT.format(task=task)
    raw = llm_call(_DERIVE_ENDPOINTS_SYSTEM, prompt, config)
    data = _parse_json_response(raw, ["start", "goal"])
    start = _normalize_state_name(str(data["start"]))
    goal = _normalize_state_name(str(data["goal"]))
    return start, goal


def _mock_derive_endpoints(task: str) -> tuple:
    """Deterministic mock: extract meaningful start/goal from task keywords."""
    import re
    # Keep only alphanumeric words
    words = re.findall(r"[A-Za-z]+", task.upper())
    skip = {"THE", "AND", "FOR", "INTO", "THIS", "FROM", "WITH", "THAT", "A", "AN"}
    significant = [w for w in words if len(w) > 2 and w not in skip][:2]
    tag = "_".join(significant) if significant else "TASK"
    return f"RAW_{tag}", f"{tag}_COMPLETE"


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def main() -> None:
    """CLI entry point."""
    args = sys.argv[1:]
    use_mock = "--mock" in args
    no_browser = "--no-browser" in args
    do_resume = "--resume" in args
    output_format = "html"

    task = DEFAULT_TASK
    start: Optional[str] = None
    goal: Optional[str] = None
    session_id = "e0-session"
    scenario = None
    explicit_start = False
    explicit_goal = False

    for i, arg in enumerate(args):
        if arg == "--task" and i + 1 < len(args):
            task = args[i + 1]
        elif arg == "--start" and i + 1 < len(args):
            start = args[i + 1]
            explicit_start = True
        elif arg == "--goal" and i + 1 < len(args):
            goal = args[i + 1]
            explicit_goal = True
        elif arg == "--session" and i + 1 < len(args):
            session_id = args[i + 1]
        elif arg == "--format" and i + 1 < len(args):
            fmt = args[i + 1].lower()
            if fmt in ("text", "html", "markdown", "md"):
                output_format = "markdown" if fmt == "md" else fmt
            else:
                print(f"Warning: Unknown format '{fmt}', using html.")
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

    # If using the default task without explicit endpoints, use defaults
    if task == DEFAULT_TASK and not explicit_start:
        start = DEFAULT_START
    if task == DEFAULT_TASK and not explicit_goal:
        goal = DEFAULT_GOAL

    run_session(
        task=task,
        start=start,
        goal=goal,
        session_id=session_id,
        use_mock=use_mock,
        scenario=scenario,
        open_browser=not no_browser,
        resume=do_resume,
        output_format=output_format,
    )


if __name__ == "__main__":
    main()
