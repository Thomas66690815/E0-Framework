"""E₀ Interactive Text Session (C213).

REPL loop on the real multi-domain landscape. The user types commands,
E₀ responds with structured communication through the full pipeline.

Commands:
  run [N]       — Execute the next N rounds (default: 1)
  status        — Show current landscape overview
  focus <domain> — Zoom into canon, bootstrap, or en
  why           — Explain the last round's decision
  summary       — Full cycle summary so far
  help          — Show available commands
  quit / exit   — End session

Usage:
  py -3 -m e0_controller.interactive_session
  py -3 -m e0_controller.interactive_session --steps 30 --format markdown
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from e0_controller.communication import (
    CommunicationIntent,
    IntentReport,
    IntentType,
    detect_round_intents,
)
from e0_controller.explore_learning_cycle_multidomain import (
    MultiDomainAssessment,
    MultiDomainRoundResult,
    assess,
    build_multidomain_landscape,
    communicate_round,
    communicate_summary,
    consolidate,
    navigate,
    plan,
    validate_confidence,
    _domain_of,
    _pick_start_node,
)


# ── Session State ──────────────────────────────────────────────────────


@dataclass
class SessionState:
    """Persistent state across REPL interactions."""

    landscape: Any
    unified_nodes: Dict[str, Any]
    stats: Dict[str, int]
    history: List[MultiDomainRoundResult] = field(default_factory=list)
    stagnation_streak: int = 0
    round_num: int = 0
    steps_per_round: int = 40
    output_format: str = "text"


# ── Commands ───────────────────────────────────────────────────────────


def cmd_run(state: SessionState, n: int = 1) -> str:
    """Execute N rounds and return communication output."""
    parts = []

    for _ in range(n):
        state.round_num += 1
        a_before = assess(state.landscape, state.unified_nodes)

        # Check saturation
        if a_before.frontier_size == 0 and a_before.coverage > 0.9:
            parts.append(
                f"  Structural saturation reached: "
                f"coverage={a_before.coverage:.1%}, no frontier."
            )
            break

        # Plan
        mode, steps, reason = plan(
            a_before, state.round_num, state.history, state.steps_per_round,
        )

        # Navigate
        start = _pick_start_node(state.landscape, state.unified_nodes, mode)
        nav = navigate(
            state.landscape, state.unified_nodes, mode, steps, start=start,
        )

        # Validate
        validate_confidence(nav["path"])

        # Assess after
        a_after = assess(state.landscape, state.unified_nodes)
        coverage_delta = a_after.coverage - a_before.coverage

        result = MultiDomainRoundResult(
            round_num=state.round_num,
            mode=mode,
            reason=reason,
            steps=nav["steps"],
            assessment_before=a_before,
            assessment_after=a_after,
            path=nav["path"],
            new_edges=len(nav["new_edges"]),
            domain_crossings=nav["domain_crossings"],
            crossing_rate=nav["crossing_rate"],
            coverage_delta=coverage_delta,
            T_s_delta=a_after.T_s - a_before.T_s,
            en_canon_crossings=nav["en_canon_crossings"],
            en_bootstrap_crossings=nav["en_bootstrap_crossings"],
            canon_bootstrap_crossings=nav["canon_bootstrap_crossings"],
            type_usage=nav.get("type_usage", {}),
        )
        state.history.append(result)

        # Consolidate (dry run — no disk writes in interactive mode)
        consolidate(result, nav["new_edges"], dry_run=True)

        # Stagnation tracking
        if coverage_delta <= 0.001:
            state.stagnation_streak += 1
        else:
            state.stagnation_streak = 0

        # Communication output
        text = communicate_round(
            result, state.landscape,
            stagnation_count=state.stagnation_streak,
            output_format=state.output_format,
        )
        parts.append(text)

    return "\n".join(parts)


def cmd_status(state: SessionState) -> str:
    """Show current landscape status as communication output."""
    from e0_controller.ui_emitter import emit_ui_spec
    from e0_controller.text_renderer import render_text, render_markdown
    from e0_controller.evidence_interpreter import interpret_panel

    a = assess(state.landscape, state.unified_nodes)

    # Build intents for current state
    report = detect_round_intents(
        round_num=state.round_num,
        mode="status",
        reason=f"Interactive status after {state.round_num} rounds",
        steps=0,
        coverage_before=a.coverage,
        coverage_after=a.coverage,
        coverage_delta=0.0,
        T_s_before=a.T_s,
        T_s_after=a.T_s,
        domain_crossings=0,
        crossing_rate=0.0,
        canon_coverage=a.canon_coverage,
        bootstrap_coverage=a.bootstrap_coverage,
        en_coverage=a.en_coverage,
        new_edges=0,
        total_nodes=a.total_nodes,
        visited_nodes=a.visited_nodes,
        stagnation_count=state.stagnation_streak,
    )

    spec = emit_ui_spec(
        report,
        context=f"Status after {state.round_num} rounds",
    )

    title = f"E₀ Status — Round {state.round_num}"
    if state.output_format == "markdown":
        text = render_markdown(spec, title=title)
    else:
        text = render_text(spec, title=title)

    parts = [text]
    sep = "\n## Interpretations\n" if state.output_format == "markdown" else "\n--- Interpretations ---"
    parts.append(sep)
    for panel in spec.panels:
        if state.output_format == "markdown":
            parts.append(f"### {panel.label}\n")
        parts.append(interpret_panel(panel))

    return "\n".join(parts)


def cmd_focus(state: SessionState, domain: str) -> str:
    """Zoom into a specific domain's state."""
    from e0_controller.ui_emitter import emit_ui_spec
    from e0_controller.text_renderer import render_text, render_markdown
    from e0_controller.evidence_interpreter import interpret_panel, interpret_trace

    # Map user input to prefix
    prefix_map = {
        "canon": "C:", "c": "C:",
        "bootstrap": "B:", "boot": "B:", "b": "B:",
        "en": "EN:", "english": "EN:", "e": "EN:",
    }
    prefix = prefix_map.get(domain.lower())
    if prefix is None:
        return f"Unknown domain '{domain}'. Use: canon, bootstrap, or en."

    domain_label = {"C:": "Canon", "B:": "Bootstrap", "EN:": "EN"}[prefix]
    hist = state.landscape.historization

    # Gather domain-specific data
    all_nodes = [n for n in state.landscape.states if n.startswith(prefix)]
    visited = set()
    edge_data = []
    for e in state.landscape.edges:
        load = hist.trace_load(e)
        quality = hist.trace_quality(e)
        if load > 0:
            visited.add(e.source)
            visited.add(e.target)
        # Edges within or touching this domain
        if e.source.startswith(prefix) or e.target.startswith(prefix):
            if load > 0:
                edge_data.append({
                    "edge": f"{e.source} → {e.target}",
                    "load": load,
                    "quality": quality,
                    "cross": _domain_of(e.source) != _domain_of(e.target),
                })

    domain_visited = [n for n in visited if n.startswith(prefix)]
    coverage = len(domain_visited) / max(1, len(all_nodes))

    # Sort edges: most active first
    edge_data.sort(key=lambda x: x["load"], reverse=True)
    top_edges = edge_data[:8]
    cross_edges = [e for e in edge_data if e["cross"]]

    # Build intents for focus view
    intents = []

    intents.append(CommunicationIntent(
        type=IntentType.STATUS,
        urgency=0.4,
        subject=f"focus_{domain_label.lower()}",
        summary=(
            f"{domain_label}: {len(domain_visited)}/{len(all_nodes)} nodes "
            f"visited ({coverage:.0%}), "
            f"{len(edge_data)} active edges, "
            f"{len(cross_edges)} cross-domain"
        ),
        evidence={
            "task": f"{domain_label} domain detail",
            "goal_reached": coverage > 0.9,
            "states": sorted(all_nodes),
            "edge_count": len(edge_data),
            "steps": state.round_num,
            "success_rate": coverage,
            "avg_tension": 0.0,
        },
    ))

    # Top edges as patterns
    for ed in top_edges[:3]:
        intents.append(CommunicationIntent(
            type=IntentType.PATTERN,
            urgency=0.2 + abs(ed["quality"]) * 0.3,
            subject=ed["edge"],
            summary=ed["edge"],
            evidence={
                "r_eff_before": max(0.001, 1.0 - ed["quality"]),
                "r_eff_after": max(0.001, 1.0 - ed["quality"] - 0.1),
                "drop_pct": 0.1,
            },
        ))

    # Struggling edges
    struggling = [e for e in edge_data if e["quality"] < -0.2]
    for ed in struggling[:2]:
        intents.append(CommunicationIntent(
            type=IntentType.UNCERTAINTY,
            urgency=0.5 + abs(ed["quality"]) * 0.3,
            subject=ed["edge"],
            summary=f"Struggling: {ed['edge']} (q={ed['quality']:+.3f})",
            evidence={
                "status": "confused",
                "quality": ed["quality"],
                "load": ed["load"],
            },
        ))

    # Unvisited nodes
    unvisited = sorted(set(all_nodes) - set(domain_visited))
    if unvisited:
        sample = unvisited[:5]
        intents.append(CommunicationIntent(
            type=IntentType.REQUEST,
            urgency=0.3 + (1.0 - coverage) * 0.3,
            subject=f"unvisited_{domain_label.lower()}",
            summary=(
                f"{len(unvisited)} unvisited {domain_label} nodes"
                + (f" (e.g. {', '.join(sample)})" if sample else "")
            ),
            evidence={
                "state": f"{domain_label}_unvisited",
                "admissible_neighbors": sample,
                "goal": f"Full {domain_label} coverage",
            },
        ))

    intents.sort(key=lambda i: i.urgency, reverse=True)
    report = IntentReport(intents=intents)

    spec = emit_ui_spec(
        report,
        context=f"Focus: {domain_label} domain",
    )

    title = f"E₀ Focus — {domain_label}"
    if state.output_format == "markdown":
        text = render_markdown(spec, title=title)
    else:
        text = render_text(spec, title=title)

    parts = [text]
    sep = "\n## Interpretations\n" if state.output_format == "markdown" else "\n--- Interpretations ---"
    parts.append(sep)
    for panel in spec.panels:
        if state.output_format == "markdown":
            parts.append(f"### {panel.label}\n")
        parts.append(interpret_panel(panel))

    return "\n".join(parts)


def cmd_why(state: SessionState) -> str:
    """Explain the last round's decision."""
    if not state.history:
        return "No rounds executed yet. Use 'run' first."

    last = state.history[-1]
    a = last.assessment_before

    lines = [
        f"Round {last.round_num} Decision",
        f"{'─' * 40}",
        f"  Mode:   {last.mode}",
        f"  Reason: {last.reason}",
        f"  Steps:  {last.steps}",
        "",
        f"Context before round:",
        f"  Coverage:   {a.coverage:.1%} ({a.visited_nodes}/{a.total_nodes})",
        f"  T_s:        {a.T_s:.3f}",
        f"  Frontier:   {a.frontier_size} nodes",
        f"  Canon:      {a.canon_coverage:.1%}",
        f"  Bootstrap:  {a.bootstrap_coverage:.1%}",
        f"  EN:         {a.en_coverage:.1%}",
    ]

    # What happened
    result_a = last.assessment_after
    lines.extend([
        "",
        f"Outcome:",
        f"  Coverage:   {a.coverage:.1%} → {result_a.coverage:.1%} "
        f"(Δ={last.coverage_delta:+.1%})",
        f"  Crossings:  {last.domain_crossings} "
        f"({last.crossing_rate:.0%} of steps)",
        f"  New edges:  {last.new_edges}",
    ])

    # Path sample
    path = last.path
    if len(path) > 10:
        sample = path[:3] + ["..."] + path[-3:]
    else:
        sample = path
    lines.append(f"  Path:       {' → '.join(sample)}")

    # What would happen next
    a_now = assess(state.landscape, state.unified_nodes)
    next_mode, next_steps, next_reason = plan(
        a_now, state.round_num + 1, state.history, state.steps_per_round,
    )
    lines.extend([
        "",
        f"Next round would be:",
        f"  Mode:   {next_mode} ({next_steps} steps)",
        f"  Reason: {next_reason}",
    ])

    return "\n".join(lines)


def cmd_summary(state: SessionState) -> str:
    """Full cycle summary."""
    if not state.history:
        return "No rounds executed yet. Use 'run' first."
    return communicate_summary(
        state.history, state.landscape,
        output_format=state.output_format,
    )


HELP_TEXT = """
E₀ Interactive Session — Commands
──────────────────────────────────
  run [N]          Execute next N rounds (default: 1)
  status           Current landscape overview
  focus <domain>   Zoom into canon, bootstrap, or en
  why              Explain the last decision
  summary          Full cycle summary so far
  help             Show this help
  quit / exit      End session
"""


def cmd_help() -> str:
    """Show help text."""
    return HELP_TEXT.strip()


# ── REPL ───────────────────────────────────────────────────────────────


def build_session(
    steps_per_round: int = 40,
    output_format: str = "text",
) -> SessionState:
    """Build a fresh interactive session with the multi-domain landscape."""
    landscape, unified_nodes, stats = build_multidomain_landscape()
    return SessionState(
        landscape=landscape,
        unified_nodes=unified_nodes,
        stats=stats,
        steps_per_round=steps_per_round,
        output_format=output_format,
    )


def dispatch(state: SessionState, user_input: str) -> Optional[str]:
    """Parse and dispatch a single user command.

    Returns the output string, or None for quit.
    """
    raw = user_input.strip()
    if not raw:
        return ""

    parts = raw.split(None, 1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd in ("quit", "exit", "q"):
        return None

    if cmd == "help" or cmd == "?":
        return cmd_help()

    if cmd == "run":
        n = 1
        if arg:
            try:
                n = int(arg)
                n = max(1, min(n, 20))
            except ValueError:
                return f"Invalid count: '{arg}'. Usage: run [N]"
        return cmd_run(state, n)

    if cmd == "status":
        return cmd_status(state)

    if cmd == "focus":
        if not arg:
            return "Usage: focus <domain> (canon, bootstrap, en)"
        return cmd_focus(state, arg)

    if cmd == "why":
        return cmd_why(state)

    if cmd == "summary":
        return cmd_summary(state)

    return f"Unknown command: '{cmd}'. Type 'help' for available commands."


def run_interactive(
    steps_per_round: int = 40,
    output_format: str = "text",
) -> None:
    """Main REPL entry point."""
    state = build_session(
        steps_per_round=steps_per_round,
        output_format=output_format,
    )

    print(f"\n{'═' * 60}")
    print(f"  E₀ Interactive Session")
    print(f"{'═' * 60}")
    print(f"  Landscape: {state.stats['total_nodes']} nodes, "
          f"{state.stats['total_edges']} edges")
    print(f"  Domains:   Canon ({state.stats['canon_nodes']}), "
          f"Bootstrap ({state.stats['bootstrap_nodes']}), "
          f"EN ({state.stats['en_nodes']})")
    print(f"  Format:    {output_format}")
    print(f"  Type 'help' for commands, 'quit' to exit.")
    print(f"{'═' * 60}\n")

    while True:
        try:
            user_input = input("E₀> ")
        except (EOFError, KeyboardInterrupt):
            print("\nSession ended.")
            break

        result = dispatch(state, user_input)
        if result is None:
            if state.history:
                print(f"\n  {len(state.history)} rounds completed. "
                      f"Final coverage: "
                      f"{state.history[-1].assessment_after.coverage:.1%}")
            print("Session ended.")
            break

        if result:
            print(result)


# ── CLI ────────────────────────────────────────────────────────────────


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="E₀ Interactive Text Session (C213)")
    parser.add_argument("--steps", type=int, default=40,
                        help="Steps per round (default: 40)")
    parser.add_argument("--format", dest="fmt", default="text",
                        choices=["text", "markdown", "md"],
                        help="Output format (default: text)")
    args = parser.parse_args()

    fmt = "markdown" if args.fmt == "md" else args.fmt

    run_interactive(
        steps_per_round=args.steps,
        output_format=fmt,
    )


if __name__ == "__main__":
    main()
