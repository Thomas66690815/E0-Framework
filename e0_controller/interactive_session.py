"""E₀ Interactive Text Session (C213, extended C214/C216/C217/C228–C233).

REPL loop on the real multi-domain landscape. The user types commands,
E₀ responds with structured communication through the full pipeline.

C214 adds a feedback loop: the user rates panels (helpful / not helpful),
and the session-scoped perception domain learns via HumanAction historization.
perception_pretrained.json is loaded as seed; learning stays in-session.

C216 adds transition-level detail: `detail` shows the last round edge by
edge, `inspect <source> <target>` shows the full inscription narrative
for a single edge.

C217 adds Human Peer Input: `task <text>` accepts free-text differences.
E₀ matches against landscape structure (node IDs via token overlap).
If matches found → shows connectivity + navigates. If not → calls LLM peer.

C218 adds LLM Peer Structuring: when E₀ structural matching finds 0 hits,
the LLM adapter proposes a domain graph (nodes/edges). The result is injected
into the live landscape with T: prefix, bridged to existing structure, and
navigated from the new anchor.

C228 adds Observation Dashboard: `trajectory` shows coverage/T_s/mode
progression over rounds as a table. `diagnose` performs per-domain
stagnation analysis with bottleneck identification and escalation hints.

C229 adds Stagnation Escalation: when stagnation persists, E₀ escalates
through 6 levels instead of stopping: focus shift → exploration boost →
bridge creation → edge proposal → accept limit. Each level is measured.
`escalate` command triggers manual escalation.

C230 adds Teaching Pipeline: `teach <concept>` explicitly teaches E₀ new
material. Always invokes LLM structuring (L: prefix), injects with
persistent consolidation (dry_run=False), runs multiple exploration passes
to absorb the material, and reports what was learned.

C231 adds Session Journal: structured per-session log with metrics snapshots,
human annotations, and cross-session trajectory. Events are auto-recorded
for rounds, teach, and escalation. `journal note <text>` adds human
annotations. Journal persists to memos/session_journal.json and accumulates
across sessions.

C232 adds Meta-Reflection: `reflect` synthesizes trajectory, domain diagnosis,
escalation history, and journal events to identify systematic stagnation
patterns. Reports mode effectiveness, domain trajectories, stagnation
episodes, and generates actionable recommendations.

C233 adds Curriculum Command: `curriculum [canon]` runs a structured
hierarchical learning sequence using CurriculumRunner. Teaches the session
progressively (derivation-level turns), transfers learned historization back
into the session landscape (prefix-aware coupling), and records journal events.

C234 adds Dream Command: `dream [N]` runs N dream consolidation cycles on
the session landscape. Extracts domain sub-landscapes (C:/B:/EN:/M:),
creates DreamObserver, detects cross-domain equivalences, reports readiness
and compatibility. Observer persists on session state for reuse.

C235 adds Sleep-Wake Integration: `sleep [N]` runs N wake-sleep episodes on
the session landscape. Extracts domain sub-landscapes, creates E0Controllers
per domain, orchestrates via SleepWakeCycle (wake=navigate, sleep=dream when
T_s > \u03bc). Transfers historization back to session (C233 coupling). Couples
curriculum (C233) + dream (C234) into an automatic rhythm.

C236 adds Tune Command: `tune [N]` runs auto-tuning on each domain
sub-landscape. For each domain: extracts sub-landscape, builds E0Controller,
runs auto_tune (Self-Graph diagnosis \u2192 perturbation \u2192 evaluation) for up to
N rounds. Reports per-domain quality changes, adopted parameter modifications,
and contextual patterns from meta-reflection.

C237 adds Auto-Mode: `auto [N]` runs an autonomous learning loop for up to N
steps. Each step: _choose_action analyzes session state (coverage, domain
status, stagnation, confused edges) and picks the best action (run/escalate/
dream/sleep/curriculum/tune/stop). Orchestrates all C233\u2013C236 capabilities
without human input. Stops on saturation, coverage \u226595%, or max steps.

C238 adds Self-Learn: `selflearn` orchestrates E\u2080 learning its own structure
before external domains. Three phases: (1) curriculum ontodynamics \u2014 learn the
theoretical foundation (WHAT), (2) curriculum mechanism_e0 \u2014 learn functional
mechanisms (HOW), (3) dream consolidation \u2014 cross-domain equivalences between
canon and mechanism. Concludes with a self-mastery assessment: per-domain
coverage, canon\u2194process alignment, overall readiness score. Implements the
"Self-Graph First" principle: E\u2080 must know itself before external domains.

C239 adds Ask Command: `ask <question>` is the on-demand question-answering
pipeline. Orchestrates: (1) knowledge assessment — extract question terms and
match against landscape structure, (2) gap detection — identify terms with no
structural match, (3) on-demand learning — teach_concept for each gap term
(max 3) via LLM, (4) re-assessment — measure coverage improvement after
learning, (5) navigation — navigate from best match through combined knowledge,
(6) confidence — term coverage ratio as honest signal. Unlike `task` (which
matches or delegates to LLM), `ask` detects PARTIAL knowledge and fills gaps
selectively before answering.

Commands:
  run [N]       — Execute the next N rounds (default: 1)
  task <text>   — Introduce a difference in natural language
  teach <text>  — Explicitly teach E₀ a new concept
  ask <question> — On-demand Q&A: assess → gap-detect → learn → answer
  status        — Show current landscape overview
  focus <domain> — Zoom into canon, bootstrap, or en
  trajectory    — Coverage/T_s/mode over time
  diagnose      — Per-domain stagnation analysis
  escalate      — Manually trigger stagnation escalation
  journal [note <text>] — Session journal: view or annotate
  reflect       — Meta-reflection: analyze learning patterns
  curriculum [c] — Run structured curriculum (ontodynamics, mechanism_e0, …)
  dream [N]     — Run N dream consolidation cycles (default: 3)
  sleep [N]     — Run N wake-sleep episodes (auto curriculum + dream)
  tune [N]      — Self-tune parameters per domain (Self-Graph diagnosis)
  auto [N]      — Autonomous learning loop (max N steps, default 10)
  selflearn     — Self-learn: E₀ learns itself first (canon → mechanism → dream)
  why           — Explain the last round's decision
  detail [N]    — Show last round edge by edge (or round N)
  inspect <src> <tgt> — Deep view of a single edge
  rate <i> helpful|not — Rate panel i from last output
  summary       — Full cycle summary so far
  help          — Show available commands
  quit / exit   — End session

Usage:
  py -3 -m e0_controller.interactive_session
  py -3 -m e0_controller.interactive_session --steps 30 --format markdown
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from e0_controller.communication import (
    CommunicationIntent,
    IntentReport,
    IntentType,
    detect_round_intents,
)
from e0_controller.curriculum import CurriculumRunner, transfer_historization
from e0_controller.dream_mode import DreamCycleResult, DreamObserver
from e0_controller.sleep_wake import EpisodeResult, SleepWakeCycle
from e0_controller.parameter_sensitivity import (
    AutoTuneResult, apply_config, auto_tune,
)
from e0_controller.config import E0Config, DEFAULTS
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
from e0_controller.feedback import (
    HumanAction,
    FeedbackResult,
    ingest_panel_feedback,
)
from e0_controller.perception import PerceptionDomain, build_perception_domain
from e0_controller.primitives import Edge, Outcome
from e0_controller.ui_emitter import UISpec
from e0_controller.coupling_router import (
    CouplingRouter,
    CouplingReason,
    CouplingSelection,
    structural_distance,
)
from e0_controller.multiverse import Universe


# ── Universe State (C245) ─────────────────────────────────────────────


@dataclass
class UniverseState:
    """One E₀ universe — isolated landscape with own learned nodes.

    C245: Each universe has its own landscape, unified_nodes, and stats.
    The 'main' universe is the default (= the session's original landscape).
    Additional universes can be created for domain isolation.
    """

    name: str
    landscape: Any
    unified_nodes: Dict[str, Any]
    stats: Dict[str, int]
    history: List[MultiDomainRoundResult] = field(default_factory=list)
    round_num: int = 0
    stagnation_streak: int = 0


# ── Session State ──────────────────────────────────────────────────────


@dataclass
class SessionState:
    """Persistent state across REPL interactions."""

    landscape: Any
    unified_nodes: Dict[str, Any]
    stats: Dict[str, int]
    perception: Optional[PerceptionDomain] = None
    history: List[MultiDomainRoundResult] = field(default_factory=list)
    stagnation_streak: int = 0
    round_num: int = 0
    steps_per_round: int = 40
    output_format: str = "text"
    last_spec: Optional[UISpec] = None
    llm_adapter: Optional[Any] = None  # E0LLMAdapter, lazy-init
    session_id: str = ""  # C231: unique session identifier
    journal: List[Dict[str, Any]] = field(default_factory=list)  # C231
    dream_observer: Optional[DreamObserver] = None  # C234: persistent observer
    coupling_router: Optional[CouplingRouter] = None  # C247: inter-universe coupling
    # C245: Multiverse support — multiple isolated E₀ universes
    universes: Dict[str, UniverseState] = field(default_factory=dict)
    active_universe: str = "main"


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

        # Consolidate (persist round results to learning_state.json)
        consolidate(result, nav["new_edges"], dry_run=False,
                    universe=state.active_universe)

        # Stagnation tracking
        if coverage_delta <= 0.001:
            state.stagnation_streak += 1
        else:
            state.stagnation_streak = 0

        # Auto-escalation on persistent stagnation
        if state.stagnation_streak >= 3:
            esc = escalate(state)
            esc_lines = [f"  ⚠ Stagnation ({state.stagnation_streak} rounds) — auto-escalating..."]
            if esc["resolved"]:
                esc_lines.append(
                    f"  ✓ Resolved at L{esc['level']} ({esc['name']}): "
                    f"Δcov={esc['coverage_delta']:+.3%}"
                )
            else:
                esc_lines.append(
                    "  ✗ All escalation levels exhausted — structural limit."
                )
            parts.append("\n".join(esc_lines))

        # Journal: record round event (C231)
        record_journal_event(state, "round", {
            "mode": mode,
            "coverage_delta": round(coverage_delta, 6),
            "steps": nav["steps"],
            "domain_crossings": nav["domain_crossings"],
        })

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
        state.perception,
        context=f"Status after {state.round_num} rounds",
    )
    state.last_spec = spec

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

    # Map user input to prefix — dynamic detection (C250)
    detected = _detect_domains(state.landscape)
    prefix_map: Dict[str, str] = {}
    for p, dname in detected:
        prefix_map[dname.lower()] = p
        prefix_map[p.rstrip(":").lower()] = p
    # Common aliases
    prefix_map.update({
        "boot": "B:", "english": "EN:", "mech": "M:", "learn": "L:",
    })
    prefix = prefix_map.get(domain.lower())
    if prefix is None:
        available = ", ".join(name for _, name in detected) or "none"
        return f"Unknown domain '{domain}'. Available: {available}."

    domain_label = next(
        (name for p, name in detected if p == prefix),
        _PREFIX_DISPLAY.get(prefix, prefix.rstrip(":")),
    )
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
        state.perception,
        context=f"Focus: {domain_label} domain",
    )
    state.last_spec = spec

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
    ]
    # Per-domain coverages (all known Assessment domains with nodes > 0)
    for prefix, name in _DOMAINS:
        attr = _DOMAIN_ATTR[prefix]
        cov = getattr(a, f"{attr}_coverage", 0)
        nodes = getattr(a, f"{attr}_nodes", 0)
        if nodes > 0:
            lines.append(f"  {name + ':':14s}{cov:.1%}")

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


# ── C228: Observation Dashboard ────────────────────────────────────────

# Mapping from state prefix to assessment attribute prefix
# (backward compat — used for reading historical Assessment attrs)
_DOMAIN_ATTR = {
    "C:": "canon",
    "B:": "bootstrap",
    "EN:": "en",
    "M:": "mech",
}

# Ordered domain list for consistent output (backward compat)
_DOMAINS = [
    ("C:", "Canon"),
    ("B:", "Bootstrap"),
    ("EN:", "EN"),
    ("M:", "Mechanism"),
]

# ── C250: Dynamic Domain Detection ────────────────────────────────────

import re as _re_domain

# Canonical display names for known prefixes
_PREFIX_DISPLAY: Dict[str, str] = {
    "C:": "Canon",
    "B:": "Bootstrap",
    "EN:": "EN",
    "M:": "Mechanism",
    "L:": "Learned",
}

# Canonical ordering for known prefixes (unknown ones sort after)
_CANONICAL_ORDER = ["C:", "B:", "EN:", "M:", "L:"]

_PREFIX_RE = _re_domain.compile(r'^([A-Z]+:)')


def _detect_domains(landscape: Any) -> List[Tuple[str, str]]:
    """Detect all domain prefixes present in the landscape.

    Scans landscape.states for ^[A-Z]+: patterns.
    Returns list of (prefix, display_name) tuples in canonical order,
    with unknown prefixes sorted alphabetically after known ones.
    """
    prefixes: set = set()
    for state_name in landscape.states:
        m = _PREFIX_RE.match(state_name)
        if m:
            prefixes.add(m.group(1))

    result: List[Tuple[str, str]] = []
    for p in _CANONICAL_ORDER:
        if p in prefixes:
            result.append((p, _PREFIX_DISPLAY[p]))
            prefixes.discard(p)
    for p in sorted(prefixes):
        result.append((p, _PREFIX_DISPLAY.get(p, p.rstrip(":"))))
    return result


def _compute_domain_stats(
    landscape: Any,
    prefix: str,
    visited_set: Optional[set] = None,
) -> Dict[str, Any]:
    """Compute coverage stats for a single domain prefix.

    Works directly from landscape — independent of Assessment fields.
    If *visited_set* is provided, reuses it (avoids recomputation
    when called in a loop).
    """
    hist = landscape.historization
    if visited_set is None:
        visited_set = set()
        for e in landscape.edges:
            if hist.trace_load(e) > 0:
                visited_set.add(e.source)
                visited_set.add(e.target)

    all_states = {n for n in landscape.states if n.startswith(prefix)}
    domain_visited = visited_set & all_states
    total = len(all_states)
    vis = len(domain_visited)
    coverage = vis / max(1, total)

    return {
        "prefix": prefix,
        "total": total,
        "visited": vis,
        "coverage": coverage,
    }


def compute_trajectory(state: SessionState) -> Dict[str, Any]:
    """Compute learning trajectory data from session history.

    Returns a structured dict with per-round metrics and overall trends.
    Designed for both display (cmd_trajectory) and programmatic use
    (C229+ escalation logic).
    """
    if not state.history:
        return {"rounds": [], "summary": None}

    rounds = []
    for r in state.history:
        a = r.assessment_after
        rounds.append({
            "round_num": r.round_num,
            "coverage": a.coverage,
            "coverage_delta": r.coverage_delta,
            "T_s": a.T_s,
            "T_s_delta": r.T_s_delta,
            "mode": r.mode,
            "domain_crossings": r.domain_crossings,
            "frontier_size": a.frontier_size,
            "new_edges": r.new_edges,
            "steps": r.steps,
        })

    first_a = state.history[0].assessment_before
    last_a = state.history[-1].assessment_after

    # Per-domain trajectory (known domains from Assessment history)
    domain_trends = {}
    for prefix, name in _DOMAINS:
        attr = _DOMAIN_ATTR[prefix]
        c_before = getattr(first_a, f"{attr}_coverage", 0)
        c_after = getattr(last_a, f"{attr}_coverage", 0)
        nodes = getattr(last_a, f"{attr}_nodes", 0)
        if nodes > 0:
            domain_trends[name] = {
                "coverage_start": c_before,
                "coverage_end": c_after,
                "delta": c_after - c_before,
                "nodes": nodes,
            }

    # Detected domains not in Assessment: current snapshot only
    known_prefixes = {p for p, _ in _DOMAINS}
    for prefix, name in _detect_domains(state.landscape):
        if prefix not in known_prefixes and name not in domain_trends:
            stats = _compute_domain_stats(state.landscape, prefix)
            if stats["total"] > 0:
                domain_trends[name] = {
                    "coverage_start": stats["coverage"],
                    "coverage_end": stats["coverage"],
                    "delta": 0,
                    "nodes": stats["total"],
                }

    # Mode progression
    modes = [r.mode for r in state.history]
    unique_modes = list(dict.fromkeys(modes))

    return {
        "rounds": rounds,
        "summary": {
            "total_rounds": len(state.history),
            "coverage_start": first_a.coverage,
            "coverage_end": last_a.coverage,
            "coverage_delta": last_a.coverage - first_a.coverage,
            "T_s_start": first_a.T_s,
            "T_s_end": last_a.T_s,
            "mode_progression": unique_modes,
            "stagnation_streak": state.stagnation_streak,
            "domain_trends": domain_trends,
        },
    }


def cmd_trajectory(state: SessionState) -> str:
    """Show learning trajectory: coverage/T_s/mode over rounds."""
    traj = compute_trajectory(state)
    if not traj["rounds"]:
        return "No rounds executed yet. Use 'run' first."

    md = state.output_format == "markdown"

    if md:
        lines = [
            "## Learning Trajectory",
            "",
            "| Rnd | Coverage | \u0394Cov | T_s | \u0394T_s | Mode | Cross | Front |",
            "|----:|--------:|------:|-----:|------:|------|------:|------:|",
        ]
    else:
        lines = [
            "Learning Trajectory",
            "\u2550" * 70,
            f"{'Rnd':>4} {'Coverage':>8} {'ΔCov':>7} {'T_s':>6} "
            f"{'ΔT_s':>7} {'Mode':<10} {'Cross':>5} {'Front':>5}",
            "\u2500" * 70,
        ]

    for rd in traj["rounds"]:
        cov = f"{rd['coverage']:.1%}"
        dcov = f"{rd['coverage_delta']:+.1%}"
        ts = f"{rd['T_s']:.3f}"
        dts = f"{rd['T_s_delta']:+.3f}"
        mode = rd["mode"][:10]
        cross = str(rd["domain_crossings"])
        front = str(rd["frontier_size"])

        if md:
            lines.append(
                f"| {rd['round_num']} | {cov} | {dcov} | {ts} | "
                f"{dts} | {mode} | {cross} | {front} |"
            )
        else:
            lines.append(
                f"{rd['round_num']:>4} {cov:>8} {dcov:>7} {ts:>6} "
                f"{dts:>7} {mode:<10} {cross:>5} {front:>5}"
            )

    # Summary
    s = traj["summary"]
    lines.append("")
    lines.append(
        f"  Overall: {s['coverage_start']:.1%} \u2192 {s['coverage_end']:.1%} "
        f"(\u0394={s['coverage_delta']:+.1%} in {s['total_rounds']} rounds)"
    )

    # Per-domain trends
    if s["domain_trends"]:
        lines.append("")
        lines.append("  Per-domain:")
        for name, dt in s["domain_trends"].items():
            trend = (
                "\u2191" if dt["delta"] > 0.005
                else ("\u2192" if dt["delta"] > -0.005 else "\u2193")
            )
            lines.append(
                f"    {name:12s} {dt['coverage_start']:.1%} \u2192 "
                f"{dt['coverage_end']:.1%} "
                f"(\u0394={dt['delta']:+.1%}) {trend}"
            )

    # Mode progression
    lines.append("")
    lines.append(f"  Mode progression: {' → '.join(s['mode_progression'])}")

    if s["stagnation_streak"] > 0:
        lines.append(
            f"  \u26a0 Stagnation streak: {s['stagnation_streak']} rounds"
        )

    return "\n".join(lines)


def diagnose_session(state: SessionState) -> Dict[str, Any]:
    """Per-domain stagnation analysis with bottleneck identification.

    Returns structured diagnostic data for each domain:
      - coverage, frontier, isolated nodes, velocity, status, suggestion
    Plus overall diagnosis with bottleneck identification.

    Domain status values:
      SATURATED — coverage ≥ 95%, fully explored
      BLOCKED   — unvisited nodes exist but no reachable frontier
      STAGNANT  — frontier exists but velocity ≈ 0 for ≥ 3 rounds
      GROWING   — positive velocity, learning is progressing
      IDLE      — no history yet
    """
    a = assess(state.landscape, state.unified_nodes)
    hist = state.landscape.historization

    # Compute visited set (global, once)
    visited_set: set = set()
    for e in state.landscape.edges:
        if hist.trace_load(e) > 0:
            visited_set.add(e.source)
            visited_set.add(e.target)

    domain_results = []

    for prefix, name in _detect_domains(state.landscape):
        all_states = {n for n in state.landscape.states
                      if n.startswith(prefix)}
        total = len(all_states)

        if total == 0:
            continue

        domain_visited = visited_set & all_states
        vis = len(domain_visited)
        coverage = vis / max(1, total)
        unvisited = all_states - visited_set

        qualities: List[float] = []
        loads: List[float] = []
        for e in state.landscape.edges:
            if e.source.startswith(prefix) or e.target.startswith(prefix):
                m = hist.trace_load(e)
                if m > 0:
                    qualities.append(hist.trace_quality(e))
                    loads.append(m)

        # Frontier: reachable from visited, not yet visited, in this domain
        frontier: set = set()
        for e in state.landscape.edges:
            if (e.source in visited_set
                    and e.target in unvisited
                    and e.target in all_states):
                frontier.add(e.target)

        # Isolated: unvisited and not in frontier
        isolated = unvisited - frontier

        # Recent velocity (last 5 rounds)
        # For known domains, use historical Assessment attrs; otherwise 0
        recent_deltas: List[float] = []
        attr = _DOMAIN_ATTR.get(prefix)
        if attr and state.history:
            for r in state.history[-5:]:
                before_cov = getattr(
                    r.assessment_before, f"{attr}_coverage", 0,
                )
                after_cov = getattr(
                    r.assessment_after, f"{attr}_coverage", 0,
                )
                recent_deltas.append(after_cov - before_cov)
        velocity = (
            sum(recent_deltas) / len(recent_deltas)
            if recent_deltas else 0.0
        )

        # Confused edges: high load, low quality
        mean_q = (
            sum(qualities) / len(qualities) if qualities else 0.0
        )
        mean_m = sum(loads) / len(loads) if loads else 0.0
        confused = sum(
            1 for q, m in zip(qualities, loads)
            if m > 3 and abs(q) < 0.2
        )

        # Determine status and suggestion
        if coverage >= 0.95:
            status = "SATURATED"
            suggestion = "fully explored"
        elif len(frontier) == 0 and len(unvisited) > 0:
            status = "BLOCKED"
            suggestion = (
                "no reachable frontier — needs new edges "
                "(teach / dream / task)"
            )
        elif velocity <= 0.001 and len(state.history) >= 3:
            status = "STAGNANT"
            if confused > len(qualities) * 0.3:
                suggestion = (
                    "many confused edges — try dream or curriculum"
                )
            elif len(frontier) < 3:
                suggestion = (
                    "thin frontier — try focus or LLM teaching"
                )
            else:
                suggestion = (
                    "has frontier but not advancing — "
                    "try different mode or focus"
                )
        elif velocity > 0:
            status = "GROWING"
            suggestion = "continue current approach"
        else:
            status = "IDLE"
            suggestion = "no history yet — run rounds"

        domain_results.append({
            "name": name,
            "prefix": prefix,
            "coverage": coverage,
            "total": total,
            "visited": vis,
            "frontier": len(frontier),
            "isolated": len(isolated),
            "active_edges": len(qualities),
            "mean_quality": round(mean_q, 4),
            "mean_load": round(mean_m, 2),
            "confused_edges": confused,
            "velocity": round(velocity, 6),
            "status": status,
            "suggestion": suggestion,
        })

    # Overall: bottleneck is lowest-coverage domain that isn't saturated
    active = [d for d in domain_results if d["coverage"] < 0.95]
    bottleneck = (
        min(active, key=lambda d: d["coverage"])["name"]
        if active else None
    )
    blocked = [d["name"] for d in domain_results if d["status"] == "BLOCKED"]

    return {
        "domains": domain_results,
        "overall": {
            "coverage": a.coverage,
            "T_s": round(a.T_s, 4),
            "frontier_size": a.frontier_size,
            "stagnation_streak": state.stagnation_streak,
            "bottleneck": bottleneck,
            "blocked_domains": blocked,
        },
    }


def cmd_diagnose(state: SessionState) -> str:
    """Per-domain stagnation analysis with escalation hints."""
    diag = diagnose_session(state)
    md = state.output_format == "markdown"

    if md:
        lines = ["## Diagnostic Report", ""]
    else:
        lines = ["Diagnostic Report", "\u2550" * 60]

    for d in diag["domains"]:
        if md:
            lines.append(f"### {d['name']} ({d['prefix']})")
        else:
            lines.append(f"\n  {d['name']} ({d['prefix']})")
            lines.append(f"  {'─' * 40}")

        indent = "  " if md else "    "
        lines.append(
            f"{indent}Coverage:      {d['coverage']:.1%} "
            f"({d['visited']}/{d['total']})"
        )
        lines.append(f"{indent}Frontier:      {d['frontier']} nodes")
        if d["isolated"] > 0:
            lines.append(
                f"{indent}Isolated:      {d['isolated']} unreachable nodes"
            )
        lines.append(
            f"{indent}Active edges:  {d['active_edges']} "
            f"(mean q={d['mean_quality']:+.3f}, "
            f"mean m={d['mean_load']:.1f})"
        )
        if d["confused_edges"] > 0:
            lines.append(
                f"{indent}Confused:      {d['confused_edges']} edges "
                f"(high load, low quality)"
            )
        if state.history:
            lines.append(
                f"{indent}Velocity:      "
                f"{d['velocity']:+.4f}/round (last "
                f"{min(5, len(state.history))})"
            )
        lines.append(f"{indent}Status:        {d['status']}")
        lines.append(f"{indent}Suggestion:    {d['suggestion']}")

    # Overall
    ov = diag["overall"]
    if md:
        lines.append("")
        lines.append("### Overall")
    else:
        lines.append(f"\n{'─' * 60}")
        lines.append("  Overall Diagnosis:")

    indent = "  " if md else "    "
    lines.append(
        f"{indent}Coverage: {ov['coverage']:.1%}  "
        f"T_s: {ov['T_s']:.3f}  "
        f"Frontier: {ov['frontier_size']}"
    )
    if ov["bottleneck"]:
        lines.append(f"{indent}Bottleneck: {ov['bottleneck']}")
    if ov["stagnation_streak"] > 0:
        lines.append(
            f"{indent}\u26a0 Stagnation: "
            f"{ov['stagnation_streak']} consecutive rounds"
        )
        if ov["stagnation_streak"] >= 3:
            lines.append(
                f"{indent}\u2192 Consider: focus <weakest_domain>, "
                f"dream, or teach new material"
            )
    if ov["blocked_domains"]:
        lines.append(
            f"{indent}\u26a0 Blocked domains: "
            f"{', '.join(ov['blocked_domains'])}"
        )
        lines.append(
            f"{indent}\u2192 These need new structure "
            f"(teach / dream / manual edges)"
        )

    return "\n".join(lines)


# ── C229: Stagnation Escalation ────────────────────────────────────────

# Escalation levels: each attempts to break stagnation via a different
# strategy. Levels are tried in order; if a level produces coverage_delta
# > 0.001, escalation succeeds and the level is reported.

_ESCALATION_LEVELS = [
    # (level, name, description)
    (1, "focus_shift", "Navigate from bottleneck domain"),
    (2, "exploration_boost", "Double steps + frontier-adjacent start"),
    (3, "bridge_creation", "Create edges between isolated and visited nodes"),
    (4, "edge_proposal", "Propose shortcut edges for thin-frontier domains"),
    (5, "accept", "Accept structural limit"),
]


def _escalate_focus_shift(
    state: SessionState, diag: Dict[str, Any],
) -> Tuple[float, str]:
    """Level 1: Run a round focused on the bottleneck domain."""
    bottleneck = diag["overall"].get("bottleneck")
    if not bottleneck:
        return 0.0, "no bottleneck identified"

    # Map name → prefix
    prefix_map = {d["name"]: d["prefix"] for d in diag["domains"]}
    prefix = prefix_map.get(bottleneck, "")
    if not prefix:
        return 0.0, f"unknown domain: {bottleneck}"

    # Find a frontier-adjacent node in this domain
    hist = state.landscape.historization
    visited = set()
    for e in state.landscape.edges:
        if hist.trace_load(e) > 0:
            visited.add(e.source)
            visited.add(e.target)

    # Prefer starting from a visited node adjacent to unvisited domain nodes
    candidates = []
    for e in state.landscape.edges:
        if (e.source in visited
                and e.target not in visited
                and e.target.startswith(prefix)):
            candidates.append(e.source)

    if not candidates:
        # Fall back to any visited node in this domain
        candidates = [n for n in visited if n.startswith(prefix)]

    if not candidates:
        return 0.0, f"no accessible nodes in {bottleneck}"

    start = candidates[0]
    a_before = assess(state.landscape, state.unified_nodes)

    nav = navigate(
        state.landscape, state.unified_nodes,
        "explore", state.steps_per_round, start=start,
    )
    validate_confidence(nav["path"])

    a_after = assess(state.landscape, state.unified_nodes)
    delta = a_after.coverage - a_before.coverage

    return delta, f"focused on {bottleneck} from {start}, {nav['steps']} steps"


def _escalate_exploration_boost(
    state: SessionState, diag: Dict[str, Any],
) -> Tuple[float, str]:
    """Level 2: Double the step budget, start from frontier."""
    a_before = assess(state.landscape, state.unified_nodes)

    # Start from a frontier-adjacent node
    start = _pick_start_node(
        state.landscape, state.unified_nodes, "explore",
    )
    boosted_steps = state.steps_per_round * 2

    nav = navigate(
        state.landscape, state.unified_nodes,
        "explore", boosted_steps, start=start,
    )
    validate_confidence(nav["path"])

    a_after = assess(state.landscape, state.unified_nodes)
    delta = a_after.coverage - a_before.coverage

    return delta, f"boosted exploration: {boosted_steps} steps from {start}"


def _escalate_bridge_creation(
    state: SessionState, diag: Dict[str, Any],
) -> Tuple[float, str]:
    """Level 3: Create edges from visited nodes to isolated nodes.

    Targets domains with status BLOCKED or with isolated nodes.
    Creates bidirectional edges from the nearest visited node
    to up to 3 isolated nodes per domain.
    """
    hist = state.landscape.historization
    visited = set()
    for e in state.landscape.edges:
        if hist.trace_load(e) > 0:
            visited.add(e.source)
            visited.add(e.target)

    bridges_created = 0
    details = []

    for d in diag["domains"]:
        if d["isolated"] == 0:
            continue

        prefix = d["prefix"]
        all_states = {n for n in state.landscape.states
                      if n.startswith(prefix)}
        domain_visited = visited & all_states

        # Find isolated nodes (not in frontier, not visited)
        frontier = set()
        for e in state.landscape.edges:
            if (e.source in visited
                    and e.target not in visited
                    and e.target in all_states):
                frontier.add(e.target)
        isolated = all_states - visited - frontier

        if not isolated or not domain_visited:
            continue

        # Pick up to 3 isolated nodes, connect to nearest visited
        for iso_node in sorted(isolated)[:3]:
            # Pick first visited domain node as anchor
            anchor = sorted(domain_visited)[0]
            if not state.landscape.has_edge(anchor, iso_node):
                state.landscape.add_edge(
                    anchor, iso_node, 0.4, 1.2,
                    relation_type="escalation_bridge",
                )
                state.landscape.add_edge(
                    iso_node, anchor, 0.4, 1.2,
                    relation_type="escalation_bridge",
                )
                bridges_created += 1
                details.append(f"{anchor}↔{iso_node}")

    if bridges_created == 0:
        return 0.0, "no isolated nodes to bridge"

    # Re-navigate to use new bridges
    a_before = assess(state.landscape, state.unified_nodes)
    start = _pick_start_node(
        state.landscape, state.unified_nodes, "explore",
    )
    nav = navigate(
        state.landscape, state.unified_nodes,
        "explore", state.steps_per_round, start=start,
    )
    validate_confidence(nav["path"])
    a_after = assess(state.landscape, state.unified_nodes)
    delta = a_after.coverage - a_before.coverage

    return delta, (
        f"created {bridges_created} bridges "
        f"({', '.join(details[:3])})"
        + (f" +{bridges_created - 3} more" if bridges_created > 3 else "")
    )


def _escalate_edge_proposal(
    state: SessionState, diag: Dict[str, Any],
) -> Tuple[float, str]:
    """Level 4: Propose shortcut edges for domains with thin frontiers.

    Creates shortcut edges between visited nodes in different domains
    to open new cross-domain paths. Targets the bottleneck domain.
    """
    bottleneck = diag["overall"].get("bottleneck")
    hist = state.landscape.historization

    visited = set()
    for e in state.landscape.edges:
        if hist.trace_load(e) > 0:
            visited.add(e.source)
            visited.add(e.target)

    # Find visited nodes in bottleneck domain and other domains
    if bottleneck:
        prefix_map = {d["name"]: d["prefix"] for d in diag["domains"]}
        bn_prefix = prefix_map.get(bottleneck, "")
        bn_visited = sorted(n for n in visited if n.startswith(bn_prefix))
        other_visited = sorted(
            (n for n in visited if not n.startswith(bn_prefix)),
        )
    else:
        bn_visited = sorted(visited)[:5]
        other_visited = sorted(visited)[5:]

    shortcuts = 0
    for bn_node in bn_visited[:3]:
        for other in other_visited[:3]:
            if not state.landscape.has_edge(bn_node, other):
                state.landscape.add_edge(
                    bn_node, other, 0.35, 1.0,
                    relation_type="escalation_shortcut",
                )
                state.landscape.add_edge(
                    other, bn_node, 0.35, 1.0,
                    relation_type="escalation_shortcut",
                )
                shortcuts += 1

    if shortcuts == 0:
        return 0.0, "no new shortcuts possible"

    a_before = assess(state.landscape, state.unified_nodes)
    start = _pick_start_node(
        state.landscape, state.unified_nodes, "explore",
    )
    nav = navigate(
        state.landscape, state.unified_nodes,
        "explore", state.steps_per_round, start=start,
    )
    validate_confidence(nav["path"])
    a_after = assess(state.landscape, state.unified_nodes)
    delta = a_after.coverage - a_before.coverage

    target = bottleneck or "landscape"
    return delta, f"proposed {shortcuts} cross-domain shortcuts for {target}"


def escalate(state: SessionState) -> Dict[str, Any]:
    """Run stagnation escalation through levels 1→5.

    Tries each level in order. If a level produces coverage_delta > 0.001,
    escalation succeeds and stops. Level 5 (accept) always terminates.

    Returns structured result:
      level: int — which level resolved (or 5 for accept)
      name: str — level name
      coverage_delta: float — improvement from escalation
      detail: str — human-readable explanation
      attempts: list — each attempted level with its result
    """
    diag = diagnose_session(state)
    a_start = assess(state.landscape, state.unified_nodes)
    attempts = []

    level_fns = [
        (1, "focus_shift", _escalate_focus_shift),
        (2, "exploration_boost", _escalate_exploration_boost),
        (3, "bridge_creation", _escalate_bridge_creation),
        (4, "edge_proposal", _escalate_edge_proposal),
    ]

    for level, name, fn in level_fns:
        delta, detail = fn(state, diag)
        attempts.append({
            "level": level,
            "name": name,
            "coverage_delta": round(delta, 6),
            "detail": detail,
        })

        if delta > 0.001:
            # Success — this level broke the stagnation
            state.stagnation_streak = 0
            a_end = assess(state.landscape, state.unified_nodes)
            return {
                "resolved": True,
                "level": level,
                "name": name,
                "coverage_delta": round(
                    a_end.coverage - a_start.coverage, 6,
                ),
                "detail": detail,
                "attempts": attempts,
            }

    # Level 5: accept structural limit
    a_end = assess(state.landscape, state.unified_nodes)
    total_delta = a_end.coverage - a_start.coverage
    attempts.append({
        "level": 5,
        "name": "accept",
        "coverage_delta": round(total_delta, 6),
        "detail": "structural limit reached — no escalation level broke stagnation",
    })

    return {
        "resolved": False,
        "level": 5,
        "name": "accept",
        "coverage_delta": round(total_delta, 6),
        "detail": "structural limit reached",
        "attempts": attempts,
    }


def cmd_escalate(state: SessionState) -> str:
    """Manually trigger stagnation escalation."""
    result = escalate(state)

    # Journal: record escalation event (C231)
    record_journal_event(state, "escalate", {
        "level": result["level"],
        "resolved": result["resolved"],
        "coverage_delta": result["coverage_delta"],
    })

    lines = [
        "Stagnation Escalation",
        "\u2550" * 50,
    ]

    for a in result["attempts"]:
        marker = "\u2713" if a["coverage_delta"] > 0.001 else "\u2717"
        lines.append(
            f"  L{a['level']} {a['name']:<20s} "
            f"{marker} \u0394cov={a['coverage_delta']:+.3%}  "
            f"{a['detail']}"
        )

    lines.append("")
    if result["resolved"]:
        lines.append(
            f"  \u2192 Resolved at Level {result['level']} "
            f"({result['name']}): "
            f"\u0394cov={result['coverage_delta']:+.3%}"
        )
        lines.append("  Stagnation streak reset.")
    else:
        lines.append(
            "  \u2192 Structural limit reached. All levels attempted."
        )
        lines.append(
            "  Consider: teach new material, introduce new domain, "
            "or accept current coverage."
        )

    return "\n".join(lines)


def cmd_detail(state: SessionState, round_num: Optional[int] = None) -> str:
    """Show the last round's path edge by edge.

    Each transition is displayed with: source→target, domain info,
    trace_quality, trace_load, inertia_factor, edge role/type.
    """
    if not state.history:
        return "No rounds executed yet. Use 'run' first."

    if round_num is not None:
        matches = [r for r in state.history if r.round_num == round_num]
        if not matches:
            return (
                f"Round {round_num} not found. "
                f"Available: {', '.join(str(r.round_num) for r in state.history)}"
            )
        result = matches[0]
    else:
        result = state.history[-1]

    path = result.path
    if len(path) < 2:
        return f"Round {result.round_num}: path too short ({len(path)} nodes)."

    hist = state.landscape.historization
    lines = [
        f"Round {result.round_num} — Transition Detail",
        f"{'─' * 60}",
        f"  Mode: {result.mode} · {result.steps} steps · "
        f"{result.domain_crossings} crossings",
        "",
    ]

    md = state.output_format == "markdown"
    if md:
        lines = [
            f"## Round {result.round_num} — Transition Detail",
            f"Mode: {result.mode} · {result.steps} steps · "
            f"{result.domain_crossings} crossings",
            "",
            "| # | Transition | Cross | Quality | Load | Inertia | Type |",
            "|---|-----------|-------|---------|------|---------|------|",
        ]

    for i in range(len(path) - 1):
        src, tgt = path[i], path[i + 1]
        edge = Edge(src, tgt)
        q = hist.trace_quality(edge)
        m = hist.trace_load(edge)
        inertia = hist.inertia_factor(edge)
        meta = state.landscape.edge_meta(src, tgt)
        rel_type = meta.get("relation_type", "")
        bridge = meta.get("bridge_type", "")
        cross = _domain_of(src) != _domain_of(tgt)

        type_label = rel_type or bridge or "—"
        cross_label = "✗" if cross else ""

        if md:
            q_str = f"{q:+.3f}"
            m_str = f"{m:.1f}"
            i_str = f"{inertia:.3f}"
            lines.append(
                f"| {i + 1} | `{src}` → `{tgt}` | {cross_label} | "
                f"{q_str} | {m_str} | {i_str} | {type_label} |"
            )
        else:
            cross_tag = " [CROSS]" if cross else ""
            q_bar = _quality_bar(q)
            lines.append(
                f"  {i + 1:>3}. {src} → {tgt}{cross_tag}"
            )
            lines.append(
                f"       q={q:+.3f} {q_bar}  m={m:.1f}  I={inertia:.3f}"
                f"  {type_label}"
            )

    # Summary line
    lines.append("")
    crossings = sum(
        1 for i in range(len(path) - 1)
        if _domain_of(path[i]) != _domain_of(path[i + 1])
    )
    lines.append(
        f"  {len(path) - 1} transitions, {crossings} domain crossings"
    )

    return "\n".join(lines)


def _quality_bar(q: float, width: int = 10) -> str:
    """Small ASCII quality indicator: [████░░░░░░] for q in [-1,+1]."""
    normalized = (q + 1) / 2  # 0..1
    filled = int(round(normalized * width))
    return "[" + "█" * filled + "░" * (width - filled) + "]"


def cmd_inspect(state: SessionState, source: str, target: str) -> str:
    """Deep inspection of a single edge's inscription narrative."""
    hist = state.landscape.historization
    edge = Edge(source, target)

    m = hist.trace_load(edge)
    q = hist.trace_quality(edge)
    inertia = hist.inertia_factor(edge)

    if m == 0:
        # Try reverse direction
        rev = Edge(target, source)
        if hist.trace_load(rev) > 0:
            return (
                f"Edge {source}→{target} has no inscriptions.\n"
                f"Did you mean: {target}→{source}? "
                f"(load={hist.trace_load(rev):.1f})"
            )
        return f"Edge {source}→{target} has no inscriptions (load=0)."

    meta = state.landscape.edge_meta(source, target)
    summary = hist.inscription_summary(edge)

    lines = [
        f"Edge: {source} → {target}",
        f"{'─' * 60}",
        f"  Domains:     {_domain_of(source)} → {_domain_of(target)}"
        + (" [CROSS-DOMAIN]" if _domain_of(source) != _domain_of(target) else ""),
        f"  trace_load:  {m:.2f}",
        f"  quality:     {q:+.4f}  {_quality_bar(q)}",
        f"  inertia:     {inertia:.4f}",
    ]

    # Metadata
    if meta:
        rel = meta.get("relation_type", "")
        bridge = meta.get("bridge_type", "")
        if rel:
            lines.append(f"  relation:    {rel}")
        if bridge:
            lines.append(f"  bridge:      {bridge}")

    lines.append("")

    # Inscription narrative
    count = summary.get("count", 0)
    lines.append(f"  Inscriptions: {count}")

    if count > 0:
        sr = summary.get("success_rate", 0)
        lines.append(f"  Success rate: {sr:.0%}")

        modes = summary.get("modes", {})
        if modes:
            mode_parts = [f"{k}={v}" for k, v in sorted(modes.items())]
            lines.append(f"  Modes:        {', '.join(mode_parts)}")

        roles = summary.get("roles", {})
        if roles:
            role_parts = [f"{k}={v}" for k, v in sorted(roles.items())]
            lines.append(f"  Roles:        {', '.join(role_parts)}")

        rel_types = summary.get("relation_types", {})
        if rel_types:
            type_parts = [f"{k}={v}" for k, v in sorted(rel_types.items())]
            lines.append(f"  Types:        {', '.join(type_parts)}")

        dp = summary.get("domain_pairs", {})
        if dp:
            dp_parts = [f"{k}={v}" for k, v in sorted(dp.items())]
            lines.append(f"  Domain flow:  {', '.join(dp_parts)}")

    # Recent inscriptions (last 5)
    contexts = hist.edge_inscriptions(edge)
    if contexts:
        lines.append("")
        recent = contexts[-5:]
        lines.append(f"  Recent inscriptions (last {len(recent)} of {len(contexts)}):")
        for ctx in recent:
            outcome_sym = "✓" if ctx.outcome.value == "success" else "✗"
            role = ctx.role or "—"
            lines.append(
                f"    τ={ctx.tau:>4}  {outcome_sym} {ctx.mode or '—':12s} "
                f"role={role:12s} step={ctx.step}"
            )

    return "\n".join(lines)


# ── C217: Human Peer Input ─────────────────────────────────────────────


def _stem(word: str) -> str:
    """Lightweight English suffix stripper for matching.

    Strips common inflectional suffixes so 'logistics'/'logistic',
    'processing'/'process', 'received'/'receive' compare equal.
    No external dependency — covers the most common cases.
    """
    w = word.lower()
    # Order matters: longest suffix first
    for suffix, min_stem in [
        ("ation", 3), ("tion", 3), ("sion", 3),
        ("ness", 4), ("ment", 3), ("ence", 3), ("ance", 3),
        ("ible", 3), ("able", 3),
        ("ling", 3),
        ("ing", 3),
        ("ous", 3), ("ive", 5),
        ("ics", 3),
        ("ies", 3),
        ("ied", 3),
        ("ful", 3),
        ("ers", 3),
        ("est", 4),
        ("ic", 3),
        ("ed", 4),
        ("er", 4),
        ("ly", 3),
        ("es", 4),
        ("al", 4),
        ("s", 4),
    ]:
        if w.endswith(suffix) and len(w) - len(suffix) >= min_stem:
            # Don't strip bare 's' after 's' (process, dress, etc.)
            if suffix == "s" and len(w) >= 2 and w[-2] == "s":
                continue
            return w[: -len(suffix)]
    return w


def _match_nodes(
    text: str,
    landscape: Any,
    unified_nodes: Optional[Dict[str, Any]] = None,
) -> List[Tuple[str, float]]:
    """Match free text against landscape node IDs AND descriptions.

    Tokenizes the query and scores each node by token overlap with:
    1. Node concept name (from ID after prefix)
    2. Node label/description (from unified_nodes metadata)

    Returns (node_id, relevance) pairs sorted by relevance descending.
    """
    raw = text.lower()
    tokens = set(raw.split())
    # Drop very short tokens (articles, prepositions)
    tokens = {t for t in tokens if len(t) > 2}
    if not tokens:
        return []

    # Build stemmed lookup for fuzzy suffix matching
    stemmed_tokens = {_stem(t) for t in tokens}

    node_meta = unified_nodes or {}
    results: List[Tuple[str, float]] = []

    for node_id in sorted(landscape.states):
        # Extract concept name after prefix (C:, B:, EN:)
        if ":" in node_id:
            concept = node_id.split(":", 1)[1].lower()
        else:
            concept = node_id.lower()

        parts = set(concept.replace("_", " ").replace("-", " ").split())

        # Exact word overlap on concept name
        id_overlap = len(parts & tokens)

        # Stemmed overlap: catches logistics/logistic, processing/process
        if id_overlap == 0:
            stemmed_parts = {_stem(p) for p in parts}
            stem_overlap = len(stemmed_parts & stemmed_tokens)
            # Stem matches count as 0.8 (slightly less than exact)
            id_overlap = stem_overlap * 0.8

        # Also match against label and description
        meta = node_meta.get(node_id, {})
        label = str(meta.get("label", "")).lower()
        desc = str(meta.get("description", "")).lower()
        semantic = f"{label} {desc}"
        sem_words = set(semantic.replace("_", " ").replace("-", " ").split())
        sem_words = {w for w in sem_words if len(w) > 2}
        sem_overlap = len(sem_words & tokens)

        # Stemmed semantic overlap
        if sem_overlap == 0 and sem_words:
            stemmed_sem = {_stem(w) for w in sem_words}
            stem_sem = len(stemmed_sem & stemmed_tokens)
            sem_overlap = stem_sem * 0.8

        # Best of: ID match or semantic match (weighted lower)
        overlap = id_overlap + sem_overlap * 0.5

        # Substring fallback for longer tokens (≥4 chars)
        if overlap == 0:
            for token in tokens:
                if len(token) >= 4:
                    if token in concept or concept in token:
                        overlap = 0.5
                        break
                    if token in semantic:
                        overlap = 0.3
                        break

        if overlap > 0:
            total_parts = max(1, len(parts))
            relevance = overlap / total_parts
            results.append((node_id, relevance))

    results.sort(key=lambda x: (-x[1], x[0]))
    return results


def _get_llm_adapter(state: SessionState) -> Any:
    """Lazy-init the LLM adapter on first use."""
    if state.llm_adapter is not None:
        return state.llm_adapter
    from e0_controller.llm_adapter import E0LLMAdapter
    state.llm_adapter = E0LLMAdapter()
    return state.llm_adapter


def _inject_spec_into_landscape(
    state: SessionState, spec: Dict[str, Any], prefix: str = "T:",
) -> Tuple[List[str], List[Tuple[str, str]]]:
    """Inject LLM-proposed nodes/edges into the live landscape.

    Prefixes nodes with `prefix` to distinguish LLM-generated structure
    from the existing Canon/Bootstrap/EN domains.

    Returns (new_node_ids, new_edge_pairs).
    """
    from e0_controller.bootstrapper import _inject_traces, _apply_confidence

    landscape = state.landscape
    hist = landscape.historization
    new_nodes: List[str] = []
    new_edges: List[Tuple[str, str]] = []

    # Add nodes
    for raw_name in spec.get("nodes", []):
        node_id = f"{prefix}{raw_name}"
        if node_id not in landscape.states:
            landscape.add_state(node_id)
            state.unified_nodes[node_id] = {
                "type": "task",
                "description": raw_name,
                "U": 0.0,
                "F": 0.0,
            }
            new_nodes.append(node_id)

    # Add edges
    for e in spec.get("edges", []):
        src = f"{prefix}{e['from']}"
        tgt = f"{prefix}{e['to']}"
        if src not in landscape.states or tgt not in landscape.states:
            continue

        edge = Edge(src, tgt)
        # Skip if edge already exists
        if edge in landscape.edges:
            continue

        delta = e.get("delta", 0.5)
        resistance = e.get("resistance", 1.0)
        confidence = e.get("confidence", 1.0)
        landscape.add_edge(
            src, tgt, delta, resistance,
            relation_type="llm_proposed", confidence=confidence,
        )
        new_edges.append((src, tgt))

        # Inject conservative initial traces
        initial_U = e.get("initial_U", 0.0)
        initial_F = e.get("initial_F", 0.0)
        if initial_U > 0 or initial_F > 0:
            U_adj, F_adj = _apply_confidence(initial_U, initial_F, confidence)
            _inject_traces(hist, edge, U_adj, F_adj)

    # Bridge: connect to existing landscape via best structural match
    bridges = _create_bridges(state, new_nodes, text_hint="")
    new_edges.extend(bridges)

    return new_nodes, new_edges


def _create_bridges(
    state: SessionState,
    new_nodes: List[str],
    text_hint: str = "",
) -> List[Tuple[str, str]]:
    """Connect new LLM-generated nodes to existing landscape structure.

    For each new node, finds the closest existing node by concept overlap
    and creates a bidirectional bridge edge.
    """
    bridges: List[Tuple[str, str]] = []
    existing = [n for n in state.landscape.states if not n.startswith("T:")]

    for new_id in new_nodes:
        concept = new_id.split(":", 1)[1].lower() if ":" in new_id else new_id.lower()
        concept_parts = set(concept.replace("_", " ").replace("-", " ").split())

        best_match = ""
        best_score = 0.0
        for existing_id in existing:
            if ":" in existing_id:
                ex_concept = existing_id.split(":", 1)[1].lower()
            else:
                ex_concept = existing_id.lower()
            ex_parts = set(ex_concept.replace("_", " ").replace("-", " ").split())

            overlap = len(concept_parts & ex_parts)
            if overlap == 0:
                for cp in concept_parts:
                    for ep in ex_parts:
                        if len(cp) >= 4 and (cp in ep or ep in cp):
                            overlap = 0.3
                            break
                    if overlap > 0:
                        break

            if overlap > best_score:
                best_score = overlap
                best_match = existing_id

        if best_match and best_score > 0:
            # Bidirectional bridge
            state.landscape.add_edge(
                new_id, best_match, 0.4, 1.2,
                relation_type="task_bridge", bridge_type="llm_structural",
            )
            state.landscape.add_edge(
                best_match, new_id, 0.4, 1.2,
                relation_type="task_bridge", bridge_type="llm_structural",
            )
            bridges.append((new_id, best_match))
            bridges.append((best_match, new_id))

    return bridges


def _llm_peer_structure(state: SessionState, text: str) -> str:
    """LLM peer: structure free text into navigable landscape nodes/edges.

    Called when E₀ structural matching finds 0 matches. The LLM
    proposes a domain graph, which is injected into the live landscape.
    """
    lines = [
        "── LLM Peer Structuring ──",
        f"  Query: \"{text}\"",
        f"  E₀ structural matching: 0 matches",
        f"  Invoking LLM peer...",
        "",
    ]

    try:
        adapter = _get_llm_adapter(state)
        spec = adapter.propose_domain_graph(text)
    except Exception as exc:
        import sys
        diag = f"[LLM PEER DIAG] {type(exc).__name__}: {exc}"
        if hasattr(exc, "raw_response") and exc.raw_response:
            preview = exc.raw_response[:500]
            diag += f"\n[LLM PEER DIAG] raw_response ({len(exc.raw_response)} chars): {preview}"
        if hasattr(exc, "finish_reason") and exc.finish_reason:
            diag += f"\n[LLM PEER DIAG] finish_reason={exc.finish_reason}"
        if hasattr(exc, "usage") and exc.usage:
            diag += f"\n[LLM PEER DIAG] usage={exc.usage}"
        print(diag, file=sys.stderr, flush=True)

        lines.append(f"  LLM peer error: {exc}")
        lines.append("")
        lines.append("  Falling back to structural gap report.")
        node_count = len(list(state.landscape.states))
        lines.append(
            f"  Landscape: {node_count} nodes searched, 0 matches."
        )
        return "\n".join(lines)

    if not spec.get("nodes"):
        lines.append("  LLM returned no structure.")
        return "\n".join(lines)

    new_nodes, new_edges = _inject_spec_into_landscape(state, spec)

    lines.append(f"  LLM proposed: {len(spec['nodes'])} nodes, "
                 f"{len(spec['edges'])} edges")
    lines.append(f"  Injected: {len(new_nodes)} new nodes, "
                 f"{len(new_edges)} new edges (incl. bridges)")

    if new_nodes:
        for nid in new_nodes[:6]:
            lines.append(f"    + {nid}")
        if len(new_nodes) > 6:
            lines.append(f"    ... and {len(new_nodes) - 6} more")

    # Navigate from injected structure
    anchor = new_nodes[0] if new_nodes else None
    if anchor:
        lines.append("")
        lines.append("── Navigation from LLM structure ──")

        state.round_num += 1
        a_before = assess(state.landscape, state.unified_nodes)

        nav = navigate(
            state.landscape, state.unified_nodes,
            "explore", state.steps_per_round,
            start=anchor,
        )
        validate_confidence(nav["path"])
        a_after = assess(state.landscape, state.unified_nodes)
        coverage_delta = a_after.coverage - a_before.coverage

        reason_short = text[:60] + ("…" if len(text) > 60 else "")
        result = MultiDomainRoundResult(
            round_num=state.round_num,
            mode="task_llm",
            reason=f"LLM peer: \"{reason_short}\"",
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
        consolidate(result, nav["new_edges"], dry_run=True,
                    universe=state.active_universe)

        if coverage_delta <= 0.001:
            state.stagnation_streak += 1
        else:
            state.stagnation_streak = 0

        lines.append(f"  Anchor: {anchor}")
        lines.append(
            f"  Steps: {nav['steps']}  "
            f"Crossings: {nav['domain_crossings']}"
        )
        lines.append(
            f"  Coverage: {a_before.coverage:.1%} → {a_after.coverage:.1%} "
            f"(Δ={coverage_delta:+.1%})"
        )

        text_out = communicate_round(
            result, state.landscape,
            stagnation_count=state.stagnation_streak,
            output_format=state.output_format,
        )
        lines.append("")
        lines.append(text_out)

    return "\n".join(lines)


# ── C230: Teaching Pipeline ────────────────────────────────────────────

_TEACH_EXPLORE_ROUNDS = 3  # exploration passes after injection


# ── C243: Iterative Teaching (self-directed follow-up) ─────────────────

def _diagnose_learning_gaps(
    state: SessionState, prefix: str = "L:",
    concept_nodes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Examine recently taught material and identify structural gaps.

    Looks at nodes with the given prefix and analyzes:
    - frontier_nodes: reachable but unvisited (trace_load == 0 on all edges)
    - weak_edges: navigated but low trace_quality (|q| < 0.3)
    - thin_nodes: nodes with ≤ 1 outgoing edge (dead-end risk)
    - leaf_nodes: nodes with 0 outgoing edges to other prefix nodes

    When concept_nodes is given, diagnosis is scoped to only those
    nodes (prevents cross-contamination from prior teach sessions).

    Returns a structured gap report.
    """
    hist = state.landscape.historization
    if concept_nodes is not None:
        prefix_nodes = [
            n for n in concept_nodes if n in state.landscape.states
        ]
    else:
        prefix_nodes = [
            n for n in state.landscape.states if n.startswith(prefix)
        ]

    frontier_nodes: List[str] = []
    thin_nodes: List[str] = []
    leaf_nodes: List[str] = []
    weak_edges: List[Tuple[str, str, float]] = []

    for node in prefix_nodes:
        outgoing = [
            e for e in state.landscape.edges
            if e.source == node and e.target.startswith(prefix)
        ]
        all_outgoing = [
            e for e in state.landscape.edges if e.source == node
        ]

        # Leaf: no outgoing to same-prefix nodes
        if len(outgoing) == 0:
            leaf_nodes.append(node)
        # Thin: only 1 outgoing within prefix
        elif len(outgoing) <= 1:
            thin_nodes.append(node)

        # Frontier: no traces on any edge touching this node
        node_edges = [
            e for e in state.landscape.edges
            if e.source == node or e.target == node
        ]
        has_any_trace = any(hist.trace_load(e) > 0 for e in node_edges)
        if not has_any_trace and len(node_edges) > 0:
            frontier_nodes.append(node)

        # Weak edges from this node
        for e in all_outgoing:
            if hist.trace_load(e) > 0:
                q = hist.trace_quality(e)
                if abs(q) < 0.3:
                    weak_edges.append((e.source, e.target, q))

    return {
        "frontier_nodes": frontier_nodes,
        "weak_edges": weak_edges,
        "thin_nodes": thin_nodes,
        "leaf_nodes": leaf_nodes,
        "total_prefix_nodes": len(prefix_nodes),
        "has_gaps": bool(frontier_nodes or weak_edges or thin_nodes or leaf_nodes),
    }


def _formulate_followup(
    concept: str,
    gaps: Dict[str, Any],
    prefix: str = "L:",
) -> str:
    """Translate structural gaps into a natural-language follow-up prompt.

    E₀ decides what to ask the LLM based on what it found weak
    or missing in its own landscape.
    """
    parts: List[str] = []

    def _strip(node_id: str) -> str:
        return node_id.split(":", 1)[1] if ":" in node_id else node_id

    if gaps["leaf_nodes"]:
        names = [_strip(n) for n in gaps["leaf_nodes"][:4]]
        parts.append(
            f"These concepts are dead ends with no further connections: "
            f"{', '.join(names)}. Elaborate what leads FROM them."
        )

    if gaps["thin_nodes"]:
        names = [_strip(n) for n in gaps["thin_nodes"][:4]]
        parts.append(
            f"These concepts have very few connections: "
            f"{', '.join(names)}. Add more transitions between them "
            f"and to other concepts."
        )

    if gaps["frontier_nodes"]:
        names = [_strip(n) for n in gaps["frontier_nodes"][:4]]
        parts.append(
            f"These concepts were never reached during navigation: "
            f"{', '.join(names)}. Create better pathways to reach them."
        )

    if gaps["weak_edges"]:
        pairs = [
            f"{_strip(s)} → {_strip(t)}"
            for s, t, _q in gaps["weak_edges"][:4]
        ]
        parts.append(
            f"These transitions are uncertain (low quality): "
            f"{', '.join(pairs)}. Add intermediate steps or "
            f"alternative routes."
        )

    if not parts:
        parts.append(
            f"Provide deeper detail on the internal mechanisms "
            f"and sub-processes within {concept}."
        )

    return (
        f"Original topic: {concept}. "
        + " ".join(parts)
    )


def teach_concept(
    state: SessionState, text: str, rounds: int = 1,
) -> Dict[str, Any]:
    """Teach E₀ a new concept via LLM structuring + persistent exploration.

    Unlike task (which matches existing structure first), teach always
    invokes LLM structuring to create new landscape material and then
    runs multiple exploration passes with persistent consolidation.

    C243: When rounds > 1, E₀ self-directs the learning process:
    after each teach round, it diagnoses structural gaps in the
    learned material, formulates a follow-up question, and asks the
    LLM to elaborate on the weak spots. This deepens understanding
    iteratively — E₀ decides what it doesn't understand.

    Returns structured result:
      nodes_added: list[str] — new node IDs injected (L: prefix)
      edges_added: list[tuple] — new edge pairs
      coverage_before: float — coverage before teaching
      coverage_after: float — coverage after exploration
      coverage_delta: float — improvement
      rounds_run: int — exploration passes completed
      domain_crossings: int — total crossings across passes
      absorbed: int — edges visited (trace_load > 0) from new material
      total_new_edges: int — total new edges in injected subgraph
      teach_rounds: list[dict] — per-round detail (C243)
    """
    rounds = max(1, min(rounds, 5))  # cap at 5
    a_start = assess(state.landscape, state.unified_nodes)

    all_nodes: List[str] = []
    all_edges: List[Tuple[str, str]] = []
    teach_rounds_detail: List[Dict[str, Any]] = []

    for teach_round in range(rounds):
        # ── Phase 1: LLM structuring ──
        try:
            adapter = _get_llm_adapter(state)
            if teach_round == 0:
                spec = adapter.propose_domain_graph(text)
            else:
                # Diagnose gaps from previous round — scoped to THIS concept
                gaps = _diagnose_learning_gaps(
                    state, prefix="L:", concept_nodes=all_nodes,
                )
                if not gaps["has_gaps"]:
                    teach_rounds_detail.append({
                        "round": teach_round + 1,
                        "action": "no_gaps",
                        "nodes_added": 0,
                        "edges_added": 0,
                    })
                    break

                followup = _formulate_followup(text, gaps)
                existing_raw = [
                    n.split(":", 1)[1] if ":" in n else n
                    for n in all_nodes
                ]
                spec = adapter.deepen_domain_graph(
                    original_concept=text,
                    existing_nodes=existing_raw,
                    gap_description=followup,
                )
        except Exception as exc:
            # ── Diagnostic: surface LLM error details ──
            import sys
            diag = f"[TEACH DIAG] Round {teach_round+1} error: {type(exc).__name__}: {exc}"
            if hasattr(exc, "raw_response") and exc.raw_response:
                preview = exc.raw_response[:500]
                diag += f"\n[TEACH DIAG] raw_response ({len(exc.raw_response)} chars): {preview}"
            if hasattr(exc, "finish_reason") and exc.finish_reason:
                diag += f"\n[TEACH DIAG] finish_reason={exc.finish_reason}"
            if hasattr(exc, "usage") and exc.usage:
                diag += f"\n[TEACH DIAG] usage={exc.usage}"
            print(diag, file=sys.stderr, flush=True)

            if teach_round == 0:
                return {
                    "error": str(exc),
                    "nodes_added": [],
                    "edges_added": [],
                    "coverage_before": a_start.coverage,
                    "coverage_after": a_start.coverage,
                    "coverage_delta": 0.0,
                    "rounds_run": 0,
                    "domain_crossings": 0,
                    "absorbed": 0,
                    "total_new_edges": 0,
                    "teach_rounds": [],
                }
            # Later rounds: LLM failure is non-fatal, stop iterating
            teach_rounds_detail.append({
                "round": teach_round + 1,
                "action": "llm_error",
                "error": str(exc),
                "nodes_added": 0,
                "edges_added": 0,
            })
            break

        if not spec.get("nodes"):
            if teach_round == 0:
                return {
                    "error": "LLM returned no structure",
                    "nodes_added": [],
                    "edges_added": [],
                    "coverage_before": a_start.coverage,
                    "coverage_after": a_start.coverage,
                    "coverage_delta": 0.0,
                    "rounds_run": 0,
                    "domain_crossings": 0,
                    "absorbed": 0,
                    "total_new_edges": 0,
                    "teach_rounds": [],
                }
            teach_rounds_detail.append({
                "round": teach_round + 1,
                "action": "no_structure",
                "nodes_added": 0,
                "edges_added": 0,
            })
            break

        # ── Phase 2: Inject ──
        # For deepen rounds, the spec may reference existing L: nodes
        # in edges but only NEW nodes in the nodes list. _inject handles
        # this because it skips nodes that already exist.
        new_nodes, new_edges = _inject_spec_into_landscape(
            state, spec, prefix="L:",
        )
        all_nodes.extend(new_nodes)
        all_edges.extend(new_edges)

        # ── Phase 3: Explore ──
        total_crossings = 0
        explore_rounds = 0

        for i in range(_TEACH_EXPLORE_ROUNDS):
            anchor = new_nodes[i % len(new_nodes)] if new_nodes else None
            if not anchor:
                break

            state.round_num += 1
            a_before = assess(state.landscape, state.unified_nodes)

            nav = navigate(
                state.landscape, state.unified_nodes,
                "explore", state.steps_per_round, start=anchor,
            )
            validate_confidence(nav["path"])

            a_after = assess(state.landscape, state.unified_nodes)
            coverage_delta = a_after.coverage - a_before.coverage

            reason_short = text[:60] + ("…" if len(text) > 60 else "")
            round_label = (
                f"teach: \"{reason_short}\" (R{teach_round + 1} pass {i + 1})"
            )
            result = MultiDomainRoundResult(
                round_num=state.round_num,
                mode="teach",
                reason=round_label,
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
            consolidate(result, nav["new_edges"], dry_run=False,
                        universe=state.active_universe)
            total_crossings += nav["domain_crossings"]
            explore_rounds += 1

            if coverage_delta <= 0.001:
                state.stagnation_streak += 1
            else:
                state.stagnation_streak = 0

        followup_used = None
        if teach_round > 0:
            followup_used = followup  # noqa: F821 — set in else branch above

        teach_rounds_detail.append({
            "round": teach_round + 1,
            "action": "initial" if teach_round == 0 else "deepen",
            "nodes_added": len(new_nodes),
            "edges_added": len(new_edges),
            "explore_rounds": explore_rounds,
            "domain_crossings": total_crossings,
            "followup": followup_used,
        })

    # Measure absorption: how many new edges got visited?
    hist = state.landscape.historization
    absorbed = 0
    for src, tgt in all_edges:
        e = Edge(src, tgt)
        if e in state.landscape.edges and hist.trace_load(e) > 0:
            absorbed += 1

    a_end = assess(state.landscape, state.unified_nodes)

    return {
        "nodes_added": all_nodes,
        "edges_added": all_edges,
        "coverage_before": round(a_start.coverage, 6),
        "coverage_after": round(a_end.coverage, 6),
        "coverage_delta": round(a_end.coverage - a_start.coverage, 6),
        "rounds_run": sum(
            r.get("explore_rounds", 0) for r in teach_rounds_detail
        ),
        "domain_crossings": sum(
            r.get("domain_crossings", 0) for r in teach_rounds_detail
        ),
        "absorbed": absorbed,
        "total_new_edges": len(all_edges),
        "teach_rounds": teach_rounds_detail,
    }


def cmd_teach(state: SessionState, text: str) -> str:
    """Explicitly teach E₀ a new concept.

    Always invokes LLM structuring, injects with persistent traces,
    and runs multiple exploration passes to absorb the material.

    C243: 'teach water 3' runs 3 iterative rounds. After round 1,
    E₀ diagnoses its own gaps and formulates follow-up questions.
    """
    # Parse optional round count from end of text
    parts = text.rsplit(None, 1)
    teach_rounds = 1
    concept = text
    if len(parts) == 2:
        try:
            teach_rounds = int(parts[1])
            concept = parts[0]
        except ValueError:
            pass  # last word isn't a number — use full text

    lines = [
        "Teaching Pipeline",
        "═" * 50,
        f"  Concept: \"{concept}\"",
        f"  Rounds: {teach_rounds}",
        "  Invoking LLM peer for structuring...",
        "",
    ]

    result = teach_concept(state, concept, rounds=teach_rounds)

    if result.get("error"):
        lines.append(f"  Error: {result['error']}")
        return "\n".join(lines)

    # Journal: record teach event (C231)
    record_journal_event(state, "teach", {
        "concept": concept[:80],
        "nodes_added": len(result["nodes_added"]),
        "coverage_delta": result["coverage_delta"],
        "teach_rounds": len(result.get("teach_rounds", [])),
    })

    # Per-round detail (C243)
    for rd in result.get("teach_rounds", []):
        action = rd.get("action", "?")
        rn = rd.get("round", "?")
        if action == "initial":
            lines.append(f"  Round {rn}: Initial structuring")
        elif action == "deepen":
            lines.append(f"  Round {rn}: Self-directed deepening")
            if rd.get("followup"):
                # Show truncated follow-up
                fu = rd["followup"]
                if len(fu) > 120:
                    fu = fu[:117] + "..."
                lines.append(f"    E₀ asked: {fu}")
        elif action == "no_gaps":
            lines.append(f"  Round {rn}: No structural gaps found — stopping")
        elif action == "llm_error":
            lines.append(f"  Round {rn}: LLM error — {rd.get('error', '?')}")
        elif action == "no_structure":
            lines.append(f"  Round {rn}: LLM returned no new structure")

        nodes_n = rd.get("nodes_added", 0)
        edges_n = rd.get("edges_added", 0)
        if nodes_n > 0 or edges_n > 0:
            lines.append(f"    +{nodes_n} nodes, +{edges_n} edges")
        lines.append("")

    lines.append(
        f"  Injected total: {len(result['nodes_added'])} nodes, "
        f"{result['total_new_edges']} edges (L: prefix)"
    )
    if result["nodes_added"]:
        for nid in result["nodes_added"][:6]:
            lines.append(f"    + {nid}")
        if len(result["nodes_added"]) > 6:
            lines.append(
                f"    ... and {len(result['nodes_added']) - 6} more"
            )

    lines.append("")
    lines.append(
        f"  Exploration: {result['rounds_run']} passes, "
        f"{result['domain_crossings']} domain crossings"
    )
    lines.append(
        f"  Coverage: {result['coverage_before']:.1%} → "
        f"{result['coverage_after']:.1%} "
        f"(Δ={result['coverage_delta']:+.1%})"
    )

    if result["total_new_edges"] > 0:
        pct = result["absorbed"] / result["total_new_edges"]
        lines.append(
            f"  Absorbed: {result['absorbed']}/{result['total_new_edges']} "
            f"edges visited ({pct:.0%})"
        )
    else:
        lines.append("  Absorbed: 0 edges (no new edges injected)")

    lines.append("")
    if result["coverage_delta"] > 0.01:
        lines.append("  ✓ Material successfully integrated.")
    elif result["coverage_delta"] > 0.001:
        lines.append("  ~ Partial integration. Consider running more rounds.")
    else:
        lines.append(
            "  ✗ Minimal coverage change. Material may overlap "
            "with existing knowledge."
        )

    return "\n".join(lines)


# ── C231: Session Journal ──────────────────────────────────────────────

JOURNAL_PATH = os.path.join("memos", "session_journal.json")


def _metrics_snapshot(state: SessionState) -> Dict[str, Any]:
    """Take a lightweight metrics snapshot for a journal entry."""
    a = assess(state.landscape, state.unified_nodes)
    snapshot: Dict[str, Any] = {
        "coverage": round(a.coverage, 4),
        "T_s": round(a.T_s, 4),
        "frontier_size": a.frontier_size,
        "visited_nodes": a.visited_nodes,
        "total_nodes": a.total_nodes,
        "canon_coverage": round(a.canon_coverage, 4),
        "bootstrap_coverage": round(a.bootstrap_coverage, 4),
        "en_coverage": round(a.en_coverage, 4),
        "mech_coverage": round(a.mech_coverage, 4),
        "stagnation_streak": state.stagnation_streak,
    }
    # C250: add all detected domains
    domain_coverages: Dict[str, float] = {}
    for prefix, name in _detect_domains(state.landscape):
        stats = _compute_domain_stats(state.landscape, prefix)
        if stats["total"] > 0:
            domain_coverages[name] = round(stats["coverage"], 4)
    snapshot["domain_coverages"] = domain_coverages
    return snapshot


def record_journal_event(
    state: SessionState,
    event_type: str,
    detail: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Record a journal event with automatic metrics snapshot.

    Event types: session_start, round, teach, escalate, note, session_end.
    Returns the created entry.
    """
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "session_id": state.session_id,
        "event_type": event_type,
        "round_num": state.round_num,
        "metrics": _metrics_snapshot(state),
    }
    if detail:
        entry["detail"] = detail

    state.journal.append(entry)
    return entry


def save_journal(state: SessionState, path: Optional[str] = None) -> str:
    """Save journal entries to JSON, appending to existing cross-session log.

    Loads existing journal file (if any), appends current session entries,
    deduplicates by timestamp+session_id, and writes back.
    Returns the absolute path of the written file.
    """
    import json

    path = path or JOURNAL_PATH

    # Load existing entries from prior sessions
    existing: List[Dict[str, Any]] = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                existing = data.get("entries", [])
        except (json.JSONDecodeError, KeyError):
            pass

    # Merge: append current session, deduplicate
    seen = {
        (e.get("timestamp", ""), e.get("session_id", ""), e.get("event_type", ""),
         e.get("round_num", 0))
        for e in existing
    }
    for entry in state.journal:
        key = (entry.get("timestamp", ""), entry.get("session_id", ""),
               entry.get("event_type", ""), entry.get("round_num", 0))
        if key not in seen:
            existing.append(entry)
            seen.add(key)

    data = {
        "version": "1.0",
        "purpose": "E₀ session journal — cross-session learning trajectory",
        "entries": existing,
    }

    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return os.path.abspath(path)


def load_journal(path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Load all journal entries from disk."""
    import json

    path = path or JOURNAL_PATH
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("entries", [])
    except (json.JSONDecodeError, KeyError):
        return []


def cmd_journal(state: SessionState, arg: Optional[str] = None) -> str:
    """Display session journal or add a note.

    Usage:
      journal          — Show current session entries
      journal all      — Show cross-session trajectory
      journal note <text> — Add a human annotation
    """
    if arg and arg.startswith("note "):
        note_text = arg[5:].strip()
        if not note_text:
            return "Usage: journal note <your annotation>"
        record_journal_event(state, "note", {"text": note_text})
        return f"  ✓ Journal note recorded: \"{note_text}\""

    if arg == "all":
        # Cross-session view: load from disk + merge current
        all_entries = load_journal()
        # Add current session entries not yet saved
        current_ids = {
            (e.get("timestamp", ""), e.get("session_id", ""))
            for e in all_entries
        }
        for entry in state.journal:
            key = (entry.get("timestamp", ""), entry.get("session_id", ""))
            if key not in current_ids:
                all_entries.append(entry)
        return _format_journal(all_entries, cross_session=True)

    # Default: current session only
    return _format_journal(state.journal, cross_session=False)


def _format_journal(
    entries: List[Dict[str, Any]], cross_session: bool = False,
) -> str:
    """Format journal entries for display."""
    if not entries:
        if cross_session:
            return "No journal entries found across sessions."
        return "No journal entries yet. Run some rounds first."

    lines = []
    if cross_session:
        lines.append("Session Journal — Cross-Session Trajectory")
        lines.append("═" * 55)
    else:
        lines.append("Session Journal")
        lines.append("═" * 55)

    current_session = ""
    for entry in entries:
        sid = entry.get("session_id", "?")
        if cross_session and sid != current_session:
            current_session = sid
            lines.append(f"\n  Session {sid}")
            lines.append("  " + "─" * 40)

        ts = entry.get("timestamp", "?")
        etype = entry.get("event_type", "?")
        rnum = entry.get("round_num", 0)
        metrics = entry.get("metrics", {})
        detail = entry.get("detail", {})

        cov = metrics.get("coverage", 0)
        ts_val = metrics.get("T_s", 0)

        # Event icon
        icons = {
            "session_start": "▶",
            "session_end": "■",
            "round": "●",
            "teach": "📖",
            "escalate": "⚡",
            "note": "✎",
        }
        icon = icons.get(etype, "·")

        # Compact line
        time_short = ts[11:19] if len(ts) >= 19 else ts
        line = f"  {icon} {time_short} R{rnum:>3d}  cov={cov:.1%}  T_s={ts_val:.2f}"

        if etype == "note":
            line += f"  \"{detail.get('text', '')}\""
        elif etype == "teach":
            concept = detail.get("concept", "")
            nodes = detail.get("nodes_added", 0)
            line += f"  teach: {concept[:30]} (+{nodes} nodes)"
        elif etype == "escalate":
            level = detail.get("level", "?")
            resolved = detail.get("resolved", False)
            line += f"  escalate: L{level} {'✓' if resolved else '✗'}"
        elif etype == "round":
            mode = detail.get("mode", "?")
            delta = detail.get("coverage_delta", 0)
            line += f"  {mode} Δ={delta:+.1%}"
        elif etype == "session_start":
            line += "  session started"
        elif etype == "session_end":
            line += "  session ended"

        lines.append(line)

    # Summary line
    if entries:
        first_m = entries[0].get("metrics", {})
        last_m = entries[-1].get("metrics", {})
        cov_start = first_m.get("coverage", 0)
        cov_end = last_m.get("coverage", 0)
        total = len(entries)
        lines.append("")
        lines.append(
            f"  {total} entries  "
            f"coverage: {cov_start:.1%} → {cov_end:.1%}  "
            f"Δ={cov_end - cov_start:+.1%}"
        )

    return "\n".join(lines)


# ── C232: Meta-Reflection ──────────────────────────────────────────────


def meta_reflect(state: SessionState) -> Dict[str, Any]:
    """Analyze the learning trajectory for systematic stagnation patterns.

    Synthesizes three data sources:
      1. Trajectory: per-round coverage/mode/domain dynamics
      2. Diagnosis: current domain stagnation status
      3. Journal: event history for pattern extraction

    Returns a structured reflection with identified patterns,
    correlations, and actionable recommendations.
    """
    traj = compute_trajectory(state)
    diag = diagnose_session(state)
    rounds = traj["rounds"]

    # ── 1. Stagnation episodes: consecutive Δcov ≤ 0.001 ──
    episodes: List[Dict[str, Any]] = []
    current_ep: Optional[Dict[str, Any]] = None
    for r in rounds:
        if r["coverage_delta"] <= 0.001:
            if current_ep is None:
                current_ep = {
                    "start": r["round_num"],
                    "end": r["round_num"],
                    "length": 1,
                    "modes": [r["mode"]],
                }
            else:
                current_ep["end"] = r["round_num"]
                current_ep["length"] += 1
                current_ep["modes"].append(r["mode"])
        else:
            if current_ep is not None:
                episodes.append(current_ep)
                current_ep = None
    if current_ep is not None:
        episodes.append(current_ep)

    # ── 2. Mode effectiveness: mode → avg coverage_delta ──
    mode_stats: Dict[str, Dict[str, Any]] = {}
    for r in rounds:
        m = r["mode"]
        if m not in mode_stats:
            mode_stats[m] = {"deltas": [], "crossings": [], "rounds": 0}
        mode_stats[m]["deltas"].append(r["coverage_delta"])
        mode_stats[m]["crossings"].append(r["domain_crossings"])
        mode_stats[m]["rounds"] += 1

    mode_effectiveness: List[Dict[str, Any]] = []
    for mode, ms in sorted(mode_stats.items()):
        avg_delta = sum(ms["deltas"]) / len(ms["deltas"]) if ms["deltas"] else 0
        avg_cross = sum(ms["crossings"]) / len(ms["crossings"]) if ms["crossings"] else 0
        stagnant_count = sum(1 for d in ms["deltas"] if d <= 0.001)
        mode_effectiveness.append({
            "mode": mode,
            "rounds": ms["rounds"],
            "avg_delta": round(avg_delta, 6),
            "avg_crossings": round(avg_cross, 2),
            "stagnant_rounds": stagnant_count,
            "stagnation_rate": round(stagnant_count / ms["rounds"], 3)
                               if ms["rounds"] > 0 else 0,
        })

    # ── 3. Domain trajectory: coverage over time per domain ──
    # Dynamic: use all domains from diagnose_session instead of hardcoded list
    domain_trajectories: Dict[str, Dict[str, Any]] = {}
    for d_diag in diag["domains"]:
        name = d_diag["name"]
        dt = traj["summary"]["domain_trends"].get(name, {})
        domain_trajectories[name] = {
            "coverage_start": dt.get("coverage_start", d_diag["coverage"]),
            "coverage_end": dt.get("coverage_end", d_diag["coverage"]),
            "delta": dt.get("delta", 0),
            "status": d_diag["status"],
            "velocity": d_diag["velocity"],
            "confused_edges": d_diag["confused_edges"],
            "frontier": d_diag["frontier"],
            "isolated": d_diag["isolated"],
        }

    # ── 4. Escalation history from journal ──
    escalation_events = [
        e for e in state.journal if e.get("event_type") == "escalate"
    ]
    escalation_summary: Dict[str, Any] = {
        "total": len(escalation_events),
        "resolved": sum(
            1 for e in escalation_events
            if e.get("detail", {}).get("resolved", False)
        ),
        "levels_reached": [
            e.get("detail", {}).get("level", 0) for e in escalation_events
        ],
    }

    # ── 5. Teaching history from journal ──
    teach_events = [
        e for e in state.journal if e.get("event_type") == "teach"
    ]
    teach_summary: Dict[str, Any] = {
        "total": len(teach_events),
        "total_nodes_added": sum(
            e.get("detail", {}).get("nodes_added", 0) for e in teach_events
        ),
        "avg_coverage_delta": round(
            sum(e.get("detail", {}).get("coverage_delta", 0)
                for e in teach_events) / len(teach_events), 6
        ) if teach_events else 0,
    }

    # ── 6. Pattern identification ──
    patterns: List[str] = []

    # Pattern: persistent stagnation
    long_eps = [ep for ep in episodes if ep["length"] >= 3]
    if long_eps:
        longest = max(long_eps, key=lambda e: e["length"])
        patterns.append(
            f"Persistent stagnation: {longest['length']} rounds "
            f"(R{longest['start']}–R{longest['end']}) in modes "
            f"{', '.join(set(longest['modes']))}"
        )

    # Pattern: mode ineffectiveness
    for me in mode_effectiveness:
        if me["rounds"] >= 3 and me["stagnation_rate"] > 0.6:
            patterns.append(
                f"Mode '{me['mode']}' is largely ineffective: "
                f"{me['stagnation_rate']:.0%} stagnation rate "
                f"over {me['rounds']} rounds"
            )

    # Pattern: blocked domains
    blocked = [
        name for name, dt in domain_trajectories.items()
        if dt["status"] == "BLOCKED"
    ]
    if blocked:
        patterns.append(
            f"Blocked domains: {', '.join(blocked)} — "
            f"need new edges (teach/dream/task)"
        )

    # Pattern: confused edges
    total_confused = sum(
        dt["confused_edges"] for dt in domain_trajectories.values()
    )
    if total_confused > 5:
        worst = max(domain_trajectories.items(),
                    key=lambda x: x[1]["confused_edges"])
        patterns.append(
            f"{total_confused} confused edges total, "
            f"worst in {worst[0]} ({worst[1]['confused_edges']})"
        )

    # Pattern: escalation exhaustion
    if (escalation_summary["total"] >= 2
            and escalation_summary["resolved"] == 0):
        patterns.append(
            "Escalation exhausted: "
            f"{escalation_summary['total']} attempts, none resolved"
        )

    # Pattern: teaching effectiveness
    if teach_summary["total"] >= 2 and teach_summary["avg_coverage_delta"] < 0.001:
        patterns.append(
            "Teaching has low impact: "
            f"{teach_summary['total']} teaches with avg Δ={teach_summary['avg_coverage_delta']:.4f}"
        )

    # Pattern: coverage plateau
    if (rounds and len(rounds) >= 5
            and traj["summary"]["coverage_delta"] < 0.01):
        patterns.append(
            f"Coverage plateau: only {traj['summary']['coverage_delta']:+.3%} "
            f"over {traj['summary']['total_rounds']} rounds"
        )

    # ── 7. Recommendations ──
    recommendations: List[str] = []

    # Based on blocked domains
    for name in blocked:
        dt = domain_trajectories[name]
        if dt["isolated"] > 0:
            recommendations.append(
                f"Teach new material bridging into {name} "
                f"({dt['isolated']} isolated nodes)"
            )

    # Based on mode ineffectiveness
    ineffective_modes = [
        me["mode"] for me in mode_effectiveness
        if me["rounds"] >= 3 and me["stagnation_rate"] > 0.6
    ]
    if ineffective_modes and "explore" in ineffective_modes:
        recommendations.append(
            "Exploration is stagnating — try targeted teaching "
            "or manual focus on weak domains"
        )

    # Based on confused edges
    if total_confused > 5:
        recommendations.append(
            "Dream consolidation (sleep-wake cycle) may resolve "
            f"{total_confused} confused edges"
        )

    # Based on frontier availability
    growing_domains = [
        name for name, dt in domain_trajectories.items()
        if dt["status"] == "GROWING"
    ]
    if not growing_domains and rounds:
        recommendations.append(
            "No domains currently growing — consider escalation "
            "or teaching new material"
        )

    # Based on escalation history
    if escalation_summary["total"] == 0 and state.stagnation_streak >= 2:
        recommendations.append(
            "Stagnation detected but no escalation attempted — try 'escalate'"
        )

    if not patterns:
        patterns.append("No problematic patterns detected — learning is healthy")
    if not recommendations:
        recommendations.append("Continue current approach — trajectory is positive")

    # Record journal event
    record_journal_event(state, "reflect", {
        "patterns_found": len(patterns),
        "recommendations": len(recommendations),
        "stagnation_episodes": len(episodes),
    })

    return {
        "stagnation_episodes": episodes,
        "mode_effectiveness": mode_effectiveness,
        "domain_trajectories": domain_trajectories,
        "escalation_summary": escalation_summary,
        "teach_summary": teach_summary,
        "patterns": patterns,
        "recommendations": recommendations,
        "overall": {
            "total_rounds": traj["summary"]["total_rounds"],
            "coverage": traj["summary"]["coverage_end"],
            "coverage_delta": traj["summary"]["coverage_delta"],
            "stagnation_streak": state.stagnation_streak,
        },
    }


def cmd_reflect(state: SessionState) -> str:
    """Meta-reflection: analyze learning trajectory for systematic patterns."""
    if not state.history:
        return "No history yet. Run some rounds first."

    ref = meta_reflect(state)
    md = state.output_format == "markdown"

    if md:
        lines = ["## Meta-Reflection", ""]
    else:
        lines = ["Meta-Reflection", "\u2550" * 60]

    # Overview
    ov = ref["overall"]
    lines.append(
        f"  {ov['total_rounds']} rounds  "
        f"coverage={ov['coverage']:.1%}  "
        f"Δ={ov['coverage_delta']:+.3%}  "
        f"stagnation={ov['stagnation_streak']}"
    )
    lines.append("")

    # Mode effectiveness
    if md:
        lines.append("### Mode Effectiveness")
    else:
        lines.append("  Mode Effectiveness")
        lines.append("  " + "\u2500" * 40)
    for me in ref["mode_effectiveness"]:
        bar = "\u2588" * max(1, int(me["avg_delta"] * 500))
        stag_pct = f"{me['stagnation_rate']:.0%}"
        lines.append(
            f"    {me['mode']:12s}  {me['rounds']:2d} rounds  "
            f"avg\u0394={me['avg_delta']:+.4f}  "
            f"stag={stag_pct:>4s}  "
            f"cross={me['avg_crossings']:.1f}"
        )
    lines.append("")

    # Domain trajectories
    if md:
        lines.append("### Domain Trajectories")
    else:
        lines.append("  Domain Trajectories")
        lines.append("  " + "\u2500" * 40)
    for name, dt in ref["domain_trajectories"].items():
        status_icon = {
            "SATURATED": "\u2713", "GROWING": "\u25b2",
            "STAGNANT": "\u25ac", "BLOCKED": "\u2716",
            "IDLE": "\u00b7",
        }.get(dt["status"], "?")
        lines.append(
            f"    {status_icon} {name:12s}  "
            f"{dt['coverage_start']:.1%}\u2192{dt['coverage_end']:.1%}  "
            f"v={dt['velocity']:+.4f}  "
            f"frontier={dt['frontier']}  "
            f"confused={dt['confused_edges']}"
        )
    lines.append("")

    # Stagnation episodes
    if ref["stagnation_episodes"]:
        if md:
            lines.append("### Stagnation Episodes")
        else:
            lines.append("  Stagnation Episodes")
            lines.append("  " + "\u2500" * 40)
        for ep in ref["stagnation_episodes"]:
            modes = ", ".join(set(ep["modes"]))
            marker = " \u26a0" if ep["length"] >= 3 else ""
            lines.append(
                f"    R{ep['start']:>3d}\u2013R{ep['end']:>3d}  "
                f"{ep['length']} rounds  [{modes}]{marker}"
            )
        lines.append("")

    # Escalation + Teaching summaries
    esc = ref["escalation_summary"]
    teach = ref["teach_summary"]
    if esc["total"] > 0 or teach["total"] > 0:
        if md:
            lines.append("### Interventions")
        else:
            lines.append("  Interventions")
            lines.append("  " + "\u2500" * 40)
        if esc["total"] > 0:
            lines.append(
                f"    Escalations: {esc['total']} "
                f"({esc['resolved']} resolved)"
            )
        if teach["total"] > 0:
            lines.append(
                f"    Teaches: {teach['total']} "
                f"(+{teach['total_nodes_added']} nodes, "
                f"avg \u0394={teach['avg_coverage_delta']:+.4f})"
            )
        lines.append("")

    # Patterns
    if md:
        lines.append("### Identified Patterns")
    else:
        lines.append("  Identified Patterns")
        lines.append("  " + "\u2500" * 40)
    for p in ref["patterns"]:
        lines.append(f"    \u25cf {p}")
    lines.append("")

    # Recommendations
    if md:
        lines.append("### Recommendations")
    else:
        lines.append("  Recommendations")
        lines.append("  " + "\u2500" * 40)
    for r in ref["recommendations"]:
        lines.append(f"    \u25b8 {r}")

    return "\n".join(lines)


# ── Curriculum Command (C233) ──────────────────────────────────────────

# Map canon names to the prefix used in the multi-domain session landscape
_CANON_PREFIX = {
    "ontodynamics": "C:",
    "mechanism_e0": "M:",
    "english_basic_enriched": "EN:",
}

AVAILABLE_CANONS = list(_CANON_PREFIX.keys())


def _transfer_to_session(
    curriculum_landscape: Any,
    session_landscape: Any,
    prefix: str,
) -> int:
    """Transfer historization from curriculum landscape to session landscape.

    Curriculum landscapes use raw node IDs (e.g. "E0", "Difference"),
    while the session uses prefixed IDs (e.g. "C:E0", "C:Difference").
    This adapter maps edges correspondingly.

    Returns the number of edges transferred.
    """
    src_hist = curriculum_landscape.historization
    tgt_hist = session_landscape.historization
    transferred = 0

    for edge in curriculum_landscape.edges:
        prefixed_src = f"{prefix}{edge.source}"
        prefixed_tgt = f"{prefix}{edge.target}"
        if session_landscape.has_edge(prefixed_src, prefixed_tgt):
            U = src_hist._U.get(edge, 0.0)
            F = src_hist._F.get(edge, 0.0)
            if U > 0 or F > 0:
                # Find the corresponding session edge
                for se in session_landscape.edges:
                    if se.source == prefixed_src and se.target == prefixed_tgt:
                        tgt_hist._U[se] = tgt_hist._U.get(se, 0.0) + U
                        tgt_hist._F[se] = tgt_hist._F.get(se, 0.0) + F
                        tgt_hist._tau_last[se] = tgt_hist._tau
                        transferred += 1
                        break

    return transferred


def curriculum_run(
    state: SessionState,
    canon_name: str = "ontodynamics",
) -> Dict[str, Any]:
    """Run a structured curriculum on a canon and couple back to session.

    1. Create CurriculumRunner for the canon
    2. Execute all turns (derivation-level hierarchy)
    3. Transfer learned historization back into session landscape
    4. Record journal event

    Returns a result dict with turn_results, transferred_edges, summary.
    """
    # execute_fn: curriculum runs structurally, no external execution needed
    runner = CurriculumRunner(
        canon_name,
        lambda s, t: Outcome.SUCCESS,
        max_episodes_per_turn=10,
        max_cycles_per_episode=30,
    )

    turn_results = runner.run()

    # Transfer historization from curriculum's final landscape to session
    prefix = _CANON_PREFIX.get(canon_name, "")
    transferred = 0
    if prefix and runner.final_landscape is not None:
        transferred = _transfer_to_session(
            runner.final_landscape, state.landscape, prefix,
        )

    # Record journal event
    record_journal_event(state, "curriculum", {
        "canon": canon_name,
        "turns": len(turn_results),
        "total_steps": sum(r.total_steps for r in turn_results),
        "equilibrium_reached": [r.equilibrium_reached for r in turn_results],
        "transferred_edges": transferred,
    })

    return {
        "canon_name": canon_name,
        "turn_results": turn_results,
        "transferred_edges": transferred,
        "summary": runner.summary(),
        "info": runner.info,
    }


def cmd_curriculum(state: SessionState, arg: Optional[str] = None) -> str:
    """Run a structured curriculum and display results."""
    canon_name = "ontodynamics"
    if arg:
        arg_clean = arg.strip().lower()
        # Allow partial matches
        for name in AVAILABLE_CANONS:
            if arg_clean in name or name.startswith(arg_clean):
                canon_name = name
                break
        else:
            return (
                f"Unknown canon: '{arg}'. "
                f"Available: {', '.join(AVAILABLE_CANONS)}"
            )

    result = curriculum_run(state, canon_name)
    md = state.output_format == "markdown"

    if md:
        lines = [f"## Curriculum: {canon_name}", ""]
    else:
        lines = [f"Curriculum: {canon_name}", "\u2550" * 60]

    info = result["info"]
    lines.append(f"  Canon: {info.name} v{info.version}")
    lines.append(f"  Turns: {len(result['turn_results'])}")
    lines.append("")

    # Per-turn details
    if md:
        lines.append("### Turn Results")
    else:
        lines.append("  Turn Results")
        lines.append("  " + "\u2500" * 40)

    for i, tr in enumerate(result["turn_results"], 1):
        eq = "\u2713 equilibrium" if tr.equilibrium_reached else "\u2717 max episodes"
        lines.append(
            f"    Turn {i} ({tr.turn.scope}):  "
            f"{tr.episodes} ep, {tr.total_steps} steps, "
            f"T_s={tr.final_T_s:.2f}, {eq}"
        )
    lines.append("")

    # Coupling back to session
    if md:
        lines.append("### Session Coupling")
    else:
        lines.append("  Session Coupling")
        lines.append("  " + "\u2500" * 40)

    prefix = _CANON_PREFIX.get(canon_name, "?")
    transferred = result["transferred_edges"]
    lines.append(
        f"    {transferred} edges transferred "
        f"({prefix}* \u2192 session landscape)"
    )

    return "\n".join(lines)


# ── Dream Command (C234) ──────────────────────────────────────────────

# Domain prefix → observer registration name
_DOMAIN_PREFIXES = {
    "C:": "canon", "B:": "bootstrap", "EN:": "en", "M:": "mechanism",
    "L:": "learned",  # C249: include learned nodes in dream consolidation
}


def _extract_domain_landscapes(
    landscape: Any,
) -> Dict[str, Any]:
    """Extract per-domain sub-landscapes from the unified session landscape.

    Each domain gets its own Landscape with intra-domain edges and
    historization copied from the session landscape.
    """
    from e0_controller.landscape import Landscape

    # Group edges by domain (intra-domain only)
    domain_edges: Dict[str, list] = {}
    domain_nodes: Dict[str, set] = {}
    for edge in landscape.edges:
        src_prefix = next(
            (p for p in _DOMAIN_PREFIXES if edge.source.startswith(p)), None
        )
        tgt_prefix = next(
            (p for p in _DOMAIN_PREFIXES if edge.target.startswith(p)), None
        )
        if src_prefix and src_prefix == tgt_prefix:
            name = _DOMAIN_PREFIXES[src_prefix]
            domain_edges.setdefault(name, []).append(edge)
            domain_nodes.setdefault(name, set()).update(
                [edge.source, edge.target]
            )

    # Build sub-landscapes with matching historization
    result = {}
    hist = landscape.historization
    for name, edges in domain_edges.items():
        ls = Landscape()
        ls.inertia_modulation = True
        for node in domain_nodes[name]:
            ls.add_state(node)
        for edge in edges:
            ls.add_edge(edge.source, edge.target, delta=0.3, resistance=0.2)
            # Copy historization
            sub_edge = Edge(edge.source, edge.target)
            U = hist._U.get(edge, 0.0)
            F = hist._F.get(edge, 0.0)
            if U > 0 or F > 0:
                ls.historization._U[sub_edge] = U
                ls.historization._F[sub_edge] = F
                ls.historization._tau_last[sub_edge] = ls.historization._tau
        result[name] = ls

    return result


def _get_or_create_observer(state: SessionState) -> DreamObserver:
    """Get the session's DreamObserver, creating one if needed."""
    if state.dream_observer is None:
        state.dream_observer = DreamObserver(
            node_equivalence_method="hungarian",
            compatibility_threshold=0.6,
        )
    return state.dream_observer


def dream_run(
    state: SessionState,
    cycles: int = 3,
) -> Dict[str, Any]:
    """Run dream consolidation cycles on the session landscape.

    1. Extract domain sub-landscapes from united session landscape
    2. Register domains with DreamObserver (refreshed each run)
    3. Run N dream cycles
    4. Record journal event

    Returns dict with cycle_results, total stats, readiness report.
    """
    observer = _get_or_create_observer(state)

    # Extract and register domain sub-landscapes from active universe
    domain_landscapes = _extract_domain_landscapes(state.landscape)
    for name, ls in domain_landscapes.items():
        observer.register(name, ls)

    # C249: Cross-universe dream — register L: sub-landscapes from other universes
    _ensure_main_universe(state)
    cross_universe_domains: List[str] = []
    for uname, ustate in state.universes.items():
        if uname == state.active_universe:
            continue
        other_domains = _extract_domain_landscapes(ustate.landscape)
        learned = other_domains.get("learned")
        if learned and learned.states:
            reg_name = f"learned_{uname}"
            observer.register(reg_name, learned)
            domain_landscapes[reg_name] = learned
            cross_universe_domains.append(reg_name)

    # Run dream cycles — C251: adaptive threshold relaxation
    cycle_results: List[DreamCycleResult] = []
    relaxed = False
    for i in range(cycles):
        result = observer.dream_cycle()
        cycle_results.append(result)
        # After first cycle: if ALL pairs skipped and none compatible,
        # relax threshold by 1.5× for remaining cycles (E₀ escalation pattern).
        if (
            i == 0
            and not relaxed
            and result.compatibility_skipped
            and result.equivalences_found == 0
            and result.node_equivalences_found == 0
        ):
            relaxed_threshold = observer._compatibility_threshold * 1.5
            relaxed = True
            # Re-run remaining cycles with relaxed threshold
            for _ in range(cycles - 1):
                result2 = observer.dream_cycle(
                    compatibility_threshold=relaxed_threshold,
                )
                cycle_results.append(result2)
            break

    # Readiness report
    readiness = observer.readiness_report()

    # Totals
    total_eq = sum(r.equivalences_found for r in cycle_results)
    total_new = sum(r.equivalences_new for r in cycle_results)
    total_node_eq = sum(r.node_equivalences_found for r in cycle_results)
    total_node_new = sum(r.node_equivalences_new for r in cycle_results)

    # Record journal event
    record_journal_event(state, "dream", {
        "cycles": len(cycle_results),
        "domains_registered": list(domain_landscapes.keys()),
        "cross_universe_domains": cross_universe_domains,
        "total_equivalences": total_eq,
        "new_equivalences": total_new,
        "node_equivalences": total_node_eq,
        "threshold_relaxed": relaxed,
        "dream_landscape_edges": (
            cycle_results[-1].dream_landscape_edges if cycle_results else 0
        ),
    })

    return {
        "cycle_results": cycle_results,
        "cycles": len(cycle_results),
        "domains": list(domain_landscapes.keys()),
        "cross_universe_domains": cross_universe_domains,
        "readiness": readiness,
        "total_equivalences": total_eq,
        "total_new_equivalences": total_new,
        "total_node_equivalences": total_node_eq,
        "total_node_new": total_node_new,
        "threshold_relaxed": relaxed,
        "dream_landscape_edges": (
            cycle_results[-1].dream_landscape_edges if cycle_results else 0
        ),
        "dream_landscape_states": (
            cycle_results[-1].dream_landscape_states if cycle_results else 0
        ),
    }


def cmd_dream(state: SessionState, arg: Optional[str] = None) -> str:
    """Run dream consolidation and display results."""
    cycles = 3
    if arg:
        try:
            cycles = int(arg)
            cycles = max(1, min(cycles, 20))
        except ValueError:
            return f"Invalid cycle count: '{arg}'. Usage: dream [N]"

    result = dream_run(state, cycles)
    md = state.output_format == "markdown"

    if md:
        lines = ["## Dream Consolidation", ""]
    else:
        lines = ["Dream Consolidation", "\u2550" * 60]

    lines.append(f"  {result['cycles']} cycles across {len(result['domains'])} domains")
    lines.append(f"  Domains: {', '.join(result['domains'])}")
    lines.append("")

    # Readiness
    if md:
        lines.append("### Domain Readiness")
    else:
        lines.append("  Domain Readiness")
        lines.append("  " + "\u2500" * 40)
    for domain, score in result["readiness"].items():
        ready = "\u2713" if score >= 0.7 else "\u2717"
        lines.append(f"    {ready} {domain:12s}  inertia={score:.2f}")
    lines.append("")

    # Per-cycle summary
    if md:
        lines.append("### Cycle Results")
    else:
        lines.append("  Cycle Results")
        lines.append("  " + "\u2500" * 40)

    # C251: Show threshold relaxation notice
    if result.get("threshold_relaxed"):
        lines.append("    \u26a0 Threshold relaxed (1.5\u00d7) — "
                      "all pairs were incompatible at default threshold")
        lines.append("")

    for i, cr in enumerate(result["cycle_results"], 1):
        lines.append(
            f"    Cycle {i}: "
            f"{cr.equivalences_found} eq ({cr.equivalences_new} new), "
            f"{cr.node_equivalences_found} node-eq ({cr.node_equivalences_new} new)"
        )
        if cr.compatibility_skipped:
            pairs = ", ".join(
                f"{a}\u2194{b}" for a, b in cr.compatibility_skipped
            )
            lines.append(f"           skipped (incompatible): {pairs}")
        # C251: Show compatibility scores for first cycle
        if i == 1 and cr.compatibility_scores:
            lines.append("           scores: " + ", ".join(
                f"{a}\u2194{b}={s:.2f}"
                for (a, b), s in sorted(cr.compatibility_scores.items())
            ))
    lines.append("")

    # Dream Landscape stats
    if md:
        lines.append("### Dream Landscape")
    else:
        lines.append("  Dream Landscape")
        lines.append("  " + "\u2500" * 40)
    lines.append(
        f"    {result['dream_landscape_states']} states, "
        f"{result['dream_landscape_edges']} edges"
    )
    lines.append(
        f"    {result['total_equivalences']} equivalences total "
        f"({result['total_new_equivalences']} new this run)"
    )
    if result["total_node_equivalences"] > 0:
        lines.append(
            f"    {result['total_node_equivalences']} node equivalences "
            f"({result['total_node_new']} new)"
        )

    return "\n".join(lines)


# ── Sleep-Wake Command (C235) ─────────────────────────────────────────


def _pick_domain_start(landscape: Any, domain_prefix: str) -> Optional[str]:
    """Pick a start node for a domain sub-landscape.

    Prefers the node with lowest trace_load (least explored).
    Falls back to first state if all have zero load.
    """
    best_node = None
    best_load = float("inf")
    hist = landscape.historization
    for state_name in landscape.states:
        if not state_name.startswith(domain_prefix):
            continue
        # Sum trace_load for all edges from this node
        load = 0.0
        for edge in landscape.edges:
            if edge.source == state_name:
                load += hist.trace_load(edge)
        if load < best_load:
            best_load = load
            best_node = state_name
    return best_node


def sleep_wake_run(
    state: SessionState,
    episodes: int = 5,
    max_cycles: int = 30,
) -> Dict[str, Any]:
    """Run a sleep-wake cycle on the session landscape.

    Combines wake (per-domain E0Controller navigation) with sleep
    (DreamObserver consolidation when T_s > μ).

    1. Extract domain sub-landscapes
    2. Create E0Controller per domain
    3. Create/reuse DreamObserver, register domains
    4. Set up SleepWakeCycle, register controllers
    5. Run N episodes
    6. Transfer learned historization back to session landscape
    7. Record journal event

    Returns result dict with episode_results, pressure_report, summary.
    """
    from e0_controller.controller import E0Controller
    from e0_controller.structural_entropy import structural_temperature

    # Extract domain sub-landscapes
    domain_landscapes = _extract_domain_landscapes(state.landscape)

    # Create/reuse DreamObserver
    observer = _get_or_create_observer(state)

    # Register domains with observer
    for name, ls in domain_landscapes.items():
        observer.register(name, ls)

    # Create E0Controller per domain + register with SleepWakeCycle
    swc = SleepWakeCycle(observer, mu=5.0, max_dream_cycles=5)

    prefix_map = {v: k for k, v in _DOMAIN_PREFIXES.items()}  # name→prefix
    for name, ls in domain_landscapes.items():
        ctrl = E0Controller(ls, lambda s, t: Outcome.SUCCESS,
                            inscription_threshold=True)
        prefix = prefix_map.get(name, "")
        start = _pick_domain_start(state.landscape, prefix)
        if start is None and ls.states:
            start = next(iter(ls.states))
        if start is not None:
            swc.register(name, ctrl, start=start)

    # Wire dream peer_fns for cross-domain bridge hypotheses
    if len(swc.domain_names) >= 2:
        swc.wire_peer_fns()

    # Run episodes
    episode_results = swc.run(n_episodes=episodes, max_cycles_per_run=max_cycles)

    # Transfer historization back to session landscape
    total_transferred = 0
    for name, ls in domain_landscapes.items():
        prefix = prefix_map.get(name, "")
        if prefix:
            transferred = _transfer_to_session(ls, state.landscape, prefix)
            total_transferred += transferred

    # Pressure report
    pressure = swc.pressure_report()

    # Count sleep phases
    sleep_count = sum(1 for ep in episode_results if ep.slept)
    total_steps = sum(
        len(ep.wake.trace.steps) for ep in episode_results
    )
    total_dream_cycles = sum(
        len(ep.sleep.dream_results)
        for ep in episode_results
        if ep.slept and ep.sleep is not None
    )

    # Record journal event
    record_journal_event(state, "sleep_wake", {
        "episodes": episodes,
        "domains": list(domain_landscapes.keys()),
        "sleep_phases": sleep_count,
        "total_steps": total_steps,
        "dream_cycles": total_dream_cycles,
        "transferred_edges": total_transferred,
    })

    return {
        "episode_results": episode_results,
        "episodes": episodes,
        "domains": list(domain_landscapes.keys()),
        "sleep_count": sleep_count,
        "total_steps": total_steps,
        "total_dream_cycles": total_dream_cycles,
        "transferred_edges": total_transferred,
        "pressure": pressure,
        "summary": swc.summary(),
    }


def cmd_sleep(state: SessionState, arg: Optional[str] = None) -> str:
    """Run sleep-wake episodes and display results."""
    episodes = 5
    if arg:
        try:
            episodes = int(arg)
            episodes = max(1, min(episodes, 50))
        except ValueError:
            return f"Invalid episode count: '{arg}'. Usage: sleep [N]"

    result = sleep_wake_run(state, episodes)
    md = state.output_format == "markdown"

    if md:
        lines = ["## Sleep-Wake Cycle", ""]
    else:
        lines = ["Sleep-Wake Cycle", "\u2550" * 60]

    lines.append(
        f"  {result['episodes']} episodes across "
        f"{len(result['domains'])} domains"
    )
    lines.append(f"  Domains: {', '.join(result['domains'])}")
    lines.append("")

    # Episode summary
    if md:
        lines.append("### Episodes")
    else:
        lines.append("  Episodes")
        lines.append("  " + "\u2500" * 40)

    for ep in result["episode_results"]:
        wake = ep.wake
        sleep_tag = ""
        if ep.slept and ep.sleep is not None:
            n_dreams = len(ep.sleep.dream_results)
            sleep_tag = f" \u2192 sleep ({n_dreams} dream cycles)"
        lines.append(
            f"    Ep {ep.episode}: {wake.domain}  "
            f"T_s={wake.T_s_before:.2f}\u2192{wake.T_s_after:.2f}  "
            f"p={wake.pressure_after:.2f}{sleep_tag}"
        )
    lines.append("")

    # Aggregate stats
    if md:
        lines.append("### Summary")
    else:
        lines.append("  Summary")
        lines.append("  " + "\u2500" * 40)

    lines.append(f"    {result['total_steps']} navigation steps")
    lines.append(
        f"    {result['sleep_count']} sleep phases "
        f"({result['total_dream_cycles']} dream cycles)"
    )
    lines.append(
        f"    {result['transferred_edges']} edges transferred "
        f"back to session"
    )
    lines.append("")

    # Pressure
    if md:
        lines.append("### Domain Pressure")
    else:
        lines.append("  Domain Pressure")
        lines.append("  " + "\u2500" * 40)
    for name, info in result["pressure"].items():
        indicator = "\u25cf" if info["pressure"] > 0.5 else "\u25cb"
        lines.append(
            f"    {indicator} {name:12s}  "
            f"T_s={info['T_s']:.2f}  "
            f"pressure={info['pressure']:.2f}"
        )

    return "\n".join(lines)


# ── Tune Command (C236) ─────────────────────────────────────────────


def tune_run(
    state: SessionState,
    max_rounds: int = 3,
) -> Dict[str, Any]:
    """Run auto-tuning on each domain sub-landscape.

    For each domain: extract sub-landscape, build E0Controller,
    run auto_tune() (Self-Graph diagnosis → perturbation → evaluation),
    collect results. If any domain improves, reports the best config
    changes found.

    Uses meta_reflect patterns to add context about what's problematic.

    Returns dict with per-domain tuning results, patterns from
    meta_reflect, and overall improvement summary.
    """
    from e0_controller.controller import E0Controller

    domain_landscapes = _extract_domain_landscapes(state.landscape)
    prefix_map = {v: k for k, v in _DOMAIN_PREFIXES.items()}

    domain_results: List[Dict[str, Any]] = []
    any_improved = False

    for name, ls in domain_landscapes.items():
        prefix = prefix_map.get(name, "")
        start = _pick_domain_start(state.landscape, prefix)
        if start is None and ls.states:
            start = next(iter(ls.states))
        if start is None:
            continue

        # Pick a goal: the node with highest trace_load (most visited)
        goal = None
        best_load = -1.0
        for s in ls.states:
            tl = sum(
                ls.historization.trace_load(e)
                for e in ls.edges if e.source == s
            )
            if tl > best_load:
                best_load = tl
                goal = s

        result = auto_tune(
            ls,
            lambda s, t: Outcome.SUCCESS,
            start,
            goal=goal,
            max_rounds=max_rounds,
        )

        domain_results.append({
            "domain": name,
            "initial_quality": result.initial_quality,
            "final_quality": result.final_quality,
            "improved": result.improved,
            "improvement": result.improvement,
            "rounds": len(result.rounds),
            "trials": result.total_trials,
            "best_config": result.best_config,
            "summary": result.summary(),
        })

        if result.improved:
            any_improved = True

    # Gather meta-reflect patterns for context
    patterns: List[str] = []
    if state.history:
        ref = meta_reflect(state)
        patterns = ref.get("patterns", [])

    # Record journal event
    improved_domains = [d["domain"] for d in domain_results if d["improved"]]
    record_journal_event(state, "tune", {
        "domains_tuned": len(domain_results),
        "domains_improved": len(improved_domains),
        "improved_names": improved_domains,
        "max_rounds": max_rounds,
        "total_trials": sum(d["trials"] for d in domain_results),
    })

    return {
        "domain_results": domain_results,
        "any_improved": any_improved,
        "improved_count": len(improved_domains),
        "patterns": patterns,
    }


def cmd_tune(state: SessionState, arg: Optional[str] = None) -> str:
    """Self-tune E₀ parameters via Self-Graph diagnosis."""
    max_rounds = 3
    if arg:
        try:
            max_rounds = int(arg)
            max_rounds = max(1, min(max_rounds, 10))
        except ValueError:
            return f"Invalid round count: '{arg}'. Usage: tune [N]"

    result = tune_run(state, max_rounds)
    md = state.output_format == "markdown"

    if md:
        lines = ["## Auto-Tune", ""]
    else:
        lines = ["Auto-Tune", "\u2550" * 60]

    if not result["domain_results"]:
        lines.append("  No domains with reachable nodes to tune.")
        return "\n".join(lines)

    lines.append(
        f"  {len(result['domain_results'])} domains, "
        f"max {max_rounds} rounds per domain"
    )
    lines.append("")

    # Per-domain results
    if md:
        lines.append("### Domain Results")
    else:
        lines.append("  Domain Results")
        lines.append("  " + "\u2500" * 40)

    for dr in result["domain_results"]:
        indicator = "\u2714" if dr["improved"] else "\u2500"
        lines.append(
            f"    {indicator} {dr['domain']:12s}  "
            f"quality {dr['initial_quality']:+.3f} \u2192 {dr['final_quality']:+.3f}  "
            f"\u0394={dr['improvement']:+.3f}  "
            f"({dr['rounds']}r/{dr['trials']}t)"
        )

        # Show changed parameters if improved
        if dr["improved"]:
            cfg = dr["best_config"]
            changes = []
            for f_name in E0Config.__dataclass_fields__:
                new_val = getattr(cfg, f_name)
                default_val = getattr(DEFAULTS, f_name)
                if new_val != default_val and isinstance(new_val, (int, float)):
                    changes.append(f"{f_name}={new_val}")
            if changes:
                lines.append(f"      Config: {', '.join(changes)}")

    lines.append("")

    # Summary
    if md:
        lines.append("### Summary")
    else:
        lines.append("  Summary")
        lines.append("  " + "\u2500" * 40)

    if result["any_improved"]:
        lines.append(
            f"    {result['improved_count']} domain(s) found better parameters"
        )
    else:
        lines.append("    All domains already at optimal parameters")

    # Context from meta-reflect
    if result["patterns"]:
        lines.append("")
        if md:
            lines.append("### Context (from meta-reflection)")
        else:
            lines.append("  Context (from meta-reflection)")
            lines.append("  " + "\u2500" * 40)
        for p in result["patterns"][:3]:
            lines.append(f"    \u25b8 {p}")

    return "\n".join(lines)


# ── Auto-Mode (C237) ────────────────────────────────────────────────


def _choose_action(state: SessionState) -> Tuple[str, str]:
    """Decide the next autonomous action based on session state.

    Returns (action, reason) where action is one of:
      run, escalate, couple, dream, sleep, curriculum, tune, stop
    """
    a = assess(state.landscape, state.unified_nodes)

    # Stop: high coverage or structural saturation
    if a.coverage >= 0.95 and a.frontier_size == 0:
        return "stop", f"coverage {a.coverage:.1%}, no frontier"

    diag = diagnose_session(state)
    domains = diag.get("domains", [])

    # Count domain statuses
    blocked = [d for d in domains if d["status"] == "BLOCKED"]
    stagnant = [d for d in domains if d["status"] == "STAGNANT"]
    growing = [d for d in domains if d["status"] == "GROWING"]
    saturated = [d for d in domains if d["status"] == "SATURATED"]

    # All explored domains saturated → stop
    active = [d for d in domains if d["status"] != "IDLE"]
    if active and all(d["status"] == "SATURATED" for d in active):
        return "stop", "all domains SATURATED"

    # C248: Stagnation + ≥2 universes → try coupling before escalate
    if state.stagnation_streak >= 3 and len(state.universes) >= 2:
        return "couple", f"stagnation streak = {state.stagnation_streak}, {len(state.universes)} universes available"

    # High stagnation → escalate
    if state.stagnation_streak >= 3:
        return "escalate", f"stagnation streak = {state.stagnation_streak}"

    # Count confused edges across domains
    total_confused = sum(d.get("confused_edges", 0) for d in domains)
    if total_confused > 5:
        return "dream", f"{total_confused} confused edges need consolidation"

    # Blocked domains → try curriculum to add structure
    if blocked:
        names = [d["name"] for d in blocked]
        return "curriculum", f"blocked domains: {', '.join(names)}"

    # Many stagnant, few growing → sleep-wake for combined approach
    if len(stagnant) >= 2 and not growing:
        return "sleep", f"{len(stagnant)} stagnant domains, none growing"

    # Low coverage → keep running
    if a.coverage < 0.8:
        return "run", f"coverage {a.coverage:.1%} — keep exploring"

    # High coverage but still frontier → run a few more
    if a.frontier_size > 0 and growing:
        return "run", f"frontier={a.frontier_size}, {len(growing)} growing"

    # Plateau with some stagnant → tune parameters
    if stagnant and state.round_num >= 5:
        return "tune", f"{len(stagnant)} stagnant domains, trying parameter tuning"

    # Default: keep running
    return "run", "default action"


def auto_run(
    state: SessionState,
    max_steps: int = 10,
    rounds_per_step: int = 3,
) -> Dict[str, Any]:
    """Autonomous learning loop: E₀ decides what to do next.

    Each step:
      1. _choose_action() analyzes session state
      2. Execute the chosen action (run/escalate/dream/sleep/curriculum/tune)
      3. Log the action and result
      4. Check stopping conditions

    Returns structured log of all actions, final coverage, and summary.
    """
    actions_log: List[Dict[str, Any]] = []
    a_start = assess(state.landscape, state.unified_nodes)
    start_coverage = a_start.coverage
    start_round = state.round_num

    for step in range(1, max_steps + 1):
        action, reason = _choose_action(state)

        if action == "stop":
            actions_log.append({
                "step": step, "action": "stop", "reason": reason,
            })
            break

        # Execute action
        if action == "run":
            cmd_run(state, rounds_per_step)
            detail = f"{rounds_per_step} rounds"

        elif action == "escalate":
            result = escalate(state)
            record_journal_event(state, "escalate", {
                "level": result["level"],
                "resolved": result["resolved"],
                "coverage_delta": result["coverage_delta"],
            })
            detail = (
                f"L{result['level']} {result['name']}, "
                f"resolved={result['resolved']}"
            )

        elif action == "dream":
            dream_run(state, cycles=3)
            detail = "3 dream cycles"

        elif action == "sleep":
            sleep_wake_run(state, episodes=3, max_cycles=20)
            detail = "3 sleep-wake episodes"

        elif action == "curriculum":
            # Pick the first available canon
            canon = AVAILABLE_CANONS[0] if AVAILABLE_CANONS else "ontodynamics"
            curriculum_run(state, canon)
            detail = f"curriculum '{canon}'"

        elif action == "tune":
            tune_run(state, max_rounds=2)
            detail = "2 tune rounds"

        elif action == "couple":
            result = couple_run(state, reason=CouplingReason.RECOVERY)
            if "error" not in result:
                transferred = result["nodes_transferred"] + result["edges_transferred"]
                detail = (
                    f"coupled with '{result['partner']}' "
                    f"({result['reason']}), "
                    f"+{result['nodes_transferred']} nodes, "
                    f"+{result['edges_transferred']} edges"
                )
                record_journal_event(state, "auto_couple", {
                    "partner": result["partner"],
                    "reason": result["reason"],
                    "nodes_transferred": result["nodes_transferred"],
                    "edges_transferred": result["edges_transferred"],
                    "outcome": result["outcome"],
                })
                # If coupling gained something, reset stagnation
                if transferred > 0:
                    state.stagnation_streak = 0
            else:
                detail = f"couple failed: {result['error']}"

        else:
            detail = "unknown"

        a_now = assess(state.landscape, state.unified_nodes)
        actions_log.append({
            "step": step,
            "action": action,
            "reason": reason,
            "detail": detail,
            "coverage_after": round(a_now.coverage, 4),
            "T_s": round(a_now.T_s, 3),
            "round_num": state.round_num,
        })

    # Final assessment
    a_end = assess(state.landscape, state.unified_nodes)

    # Record journal event
    record_journal_event(state, "auto_mode", {
        "steps": len(actions_log),
        "actions": [a["action"] for a in actions_log],
        "coverage_start": round(start_coverage, 4),
        "coverage_end": round(a_end.coverage, 4),
        "rounds_executed": state.round_num - start_round,
    })

    return {
        "actions": actions_log,
        "total_steps": len(actions_log),
        "coverage_start": start_coverage,
        "coverage_end": a_end.coverage,
        "coverage_delta": a_end.coverage - start_coverage,
        "rounds_executed": state.round_num - start_round,
        "T_s_end": a_end.T_s,
        "stopped_reason": (
            actions_log[-1]["reason"]
            if actions_log and actions_log[-1]["action"] == "stop"
            else "max_steps reached"
        ),
    }


def cmd_auto(state: SessionState, arg: Optional[str] = None) -> str:
    """Run autonomous learning loop."""
    max_steps = 10
    if arg:
        try:
            max_steps = int(arg)
            max_steps = max(1, min(max_steps, 50))
        except ValueError:
            return f"Invalid step count: '{arg}'. Usage: auto [N]"

    result = auto_run(state, max_steps)
    md = state.output_format == "markdown"

    if md:
        lines = ["## Auto-Mode", ""]
    else:
        lines = ["Auto-Mode", "\u2550" * 60]

    lines.append(
        f"  {result['total_steps']} steps, "
        f"{result['rounds_executed']} rounds executed"
    )
    lines.append(
        f"  Coverage: {result['coverage_start']:.1%} "
        f"\u2192 {result['coverage_end']:.1%}  "
        f"\u0394={result['coverage_delta']:+.3%}"
    )
    lines.append(f"  T_s: {result['T_s_end']:.3f}")
    lines.append(f"  Stopped: {result['stopped_reason']}")
    lines.append("")

    # Action log
    if md:
        lines.append("### Actions")
    else:
        lines.append("  Actions")
        lines.append("  " + "\u2500" * 40)

    _ACTION_ICONS = {
        "run": "\u25b6", "escalate": "\u26a1", "dream": "\u2601",
        "sleep": "\u263e", "curriculum": "\u2709", "tune": "\u2699",
        "stop": "\u25a0",
    }

    for a in result["actions"]:
        icon = _ACTION_ICONS.get(a["action"], "\u00b7")
        detail = a.get("detail", "")
        cov = a.get("coverage_after", "")
        cov_str = f"  cov={cov:.1%}" if isinstance(cov, float) else ""
        lines.append(
            f"    {icon} Step {a['step']}: {a['action']:<12s} "
            f"{detail}{cov_str}"
        )
        if a.get("reason"):
            lines.append(f"      reason: {a['reason']}")

    return "\n".join(lines)


# ── Self-Learn Command (C238) ──────────────────────────────────────────


def _assess_self_mastery(state: SessionState) -> Dict[str, Any]:
    """Assess E₀'s self-knowledge completeness after self-learning.

    Checks:
      1. Canon coverage (C: prefix — ontodynamics domain)
      2. Mechanism coverage (M: prefix — mechanism domain)
      3. Canon ↔ Process alignment (static, from canon_self_bridge)
    Returns mastery dict with per-domain coverage, alignment, overall score.
    """
    from e0_controller.canon_self_bridge import canon_coverage as _canon_cov
    from e0_controller.canon_loader import load_canon

    landscape = state.landscape
    hist = landscape.historization

    # Coverage per self-knowledge domain
    self_domains = {"canon": "C:", "mechanism": "M:"}
    domain_coverage: Dict[str, Dict[str, Any]] = {}
    for name, prefix in self_domains.items():
        total_nodes = [n for n in landscape.states if n.startswith(prefix)]
        visited = []
        for node in total_nodes:
            for edge in landscape.edges:
                if edge.source == node and hist.trace_load(edge) > 0:
                    visited.append(node)
                    break
        ratio = len(visited) / len(total_nodes) if total_nodes else 0.0
        domain_coverage[name] = {
            "total": len(total_nodes),
            "visited": len(visited),
            "ratio": ratio,
        }

    # Canon ↔ Process alignment (static analysis)
    try:
        cl = load_canon("ontodynamics")
        cov = _canon_cov(cl)
        alignment_ratio = cov["coverage_ratio"]
    except Exception:
        alignment_ratio = 0.0

    # Overall mastery: average of domain coverages + alignment
    onto_cov = domain_coverage.get("canon", {}).get("ratio", 0.0)
    mech_cov = domain_coverage.get("mechanism", {}).get("ratio", 0.0)
    overall = (onto_cov + mech_cov + alignment_ratio) / 3.0

    return {
        "domain_coverage": domain_coverage,
        "canon_alignment_ratio": alignment_ratio,
        "overall_mastery": overall,
        "ready": overall >= 0.5,
    }


def selflearn_run(state: SessionState) -> Dict[str, Any]:
    """E₀ learns itself: ontodynamics → mechanism → dream → self-assessment.

    Phase 1: Curriculum ontodynamics (WHAT E₀ believes — canon concepts)
    Phase 2: Curriculum mechanism_e0 (HOW E₀ works — functional mechanisms)
    Phase 3: Dream consolidation (cross-domain pattern recognition)
    Phase 4: Self-mastery assessment (coverage + alignment check)

    Returns a result dict with per-phase data and mastery report.
    """
    phases: List[Tuple[str, Dict[str, Any]]] = []

    # Phase 1: Ontodynamics — learn the theoretical foundation
    onto_result = curriculum_run(state, "ontodynamics")
    phases.append(("ontodynamics", onto_result))

    # Phase 2: Mechanism — learn how you work
    mech_result = curriculum_run(state, "mechanism_e0")
    phases.append(("mechanism_e0", mech_result))

    # Phase 3: Dream consolidation — find cross-domain equivalences
    dream_result = dream_run(state, cycles=3)

    # Phase 4: Self-mastery assessment
    mastery = _assess_self_mastery(state)

    # Journal event
    record_journal_event(state, "selflearn", {
        "phases": [p[0] for p in phases],
        "onto_turns": len(onto_result["turn_results"]),
        "onto_steps": sum(r.total_steps for r in onto_result["turn_results"]),
        "onto_transferred": onto_result["transferred_edges"],
        "mech_turns": len(mech_result["turn_results"]),
        "mech_steps": sum(r.total_steps for r in mech_result["turn_results"]),
        "mech_transferred": mech_result["transferred_edges"],
        "dream_equivalences": dream_result["total_equivalences"],
        "mastery_overall": mastery["overall_mastery"],
        "mastery_ready": mastery["ready"],
    })

    return {
        "phases": phases,
        "dream": dream_result,
        "mastery": mastery,
    }


def cmd_selflearn(state: SessionState) -> str:
    """Run self-learning sequence and display results."""
    result = selflearn_run(state)
    md = state.output_format == "markdown"

    if md:
        lines = ["## Self-Learn: E₀ Learns Itself", ""]
    else:
        lines = ["Self-Learn: E₀ Learns Itself", "\u2550" * 60]

    # Phase results
    for canon_name, phase in result["phases"]:
        turns = phase["turn_results"]
        total_steps = sum(r.total_steps for r in turns)
        transferred = phase["transferred_edges"]
        lines.append(f"  Phase: {canon_name}")
        lines.append(
            f"    {len(turns)} turns, {total_steps} steps, "
            f"{transferred} edges transferred"
        )
        for i, tr in enumerate(turns, 1):
            eq = "\u2713" if tr.equilibrium_reached else "\u2717"
            lines.append(
                f"      Turn {i}: {tr.episodes} ep, "
                f"{tr.total_steps} steps, T_s={tr.final_T_s:.2f} {eq}"
            )
        lines.append("")

    # Dream
    dream = result["dream"]
    lines.append("  Dream Consolidation")
    lines.append(
        f"    {dream['cycles']} cycles, "
        f"{dream['total_equivalences']} equivalences "
        f"({dream['total_new_equivalences']} new), "
        f"{dream['total_node_equivalences']} node-EQ"
    )
    lines.append("")

    # Mastery assessment
    mastery = result["mastery"]
    if md:
        lines.append("### Self-Mastery Assessment")
    else:
        lines.append("  Self-Mastery Assessment")
        lines.append("  " + "\u2500" * 40)

    for name, cov in mastery["domain_coverage"].items():
        bar = "\u2588" * int(cov["ratio"] * 20) + "\u2591" * (20 - int(cov["ratio"] * 20))
        lines.append(
            f"    {name:12s} {bar} {cov['ratio']:.0%} "
            f"({cov['visited']}/{cov['total']})"
        )

    lines.append(
        f"    {'alignment':12s} "
        f"{mastery['canon_alignment_ratio']:.0%} (canon \u2194 process)"
    )
    lines.append("")

    overall = mastery["overall_mastery"]
    ready = mastery["ready"]
    status = "\u2713 ready for external domains" if ready else "\u2717 continue self-learning"
    lines.append(f"  Overall mastery: {overall:.0%} — {status}")

    return "\n".join(lines)


# ── C239: Ask Command — On-Demand Question Answering ──────────────────

_ASK_STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "do", "does", "did", "have", "has", "had", "will", "would", "shall",
    "should", "can", "could", "may", "might", "must",
    "and", "or", "but", "not", "no", "nor",
    "in", "on", "at", "to", "for", "of", "with", "by", "from", "as",
    "into", "about", "between", "through", "after", "before",
    "this", "that", "these", "those", "it", "its",
    "what", "which", "who", "whom", "how", "when", "where", "why",
    "if", "then", "than", "so", "too", "also", "very",
})

_ASK_MAX_GAP_LEARN = 3  # max gap terms to auto-learn per question


def _extract_question_terms(question: str) -> List[str]:
    """Extract meaningful terms from a question for gap analysis.

    Tokenizes on word boundaries, filters stopwords and short tokens.
    Returns deduplicated terms in order of first appearance.
    """
    import re as _re
    raw_tokens = _re.findall(r"\b\w+\b", question)
    seen: set = set()
    result: List[str] = []
    for t in raw_tokens:
        low = t.lower()
        # Keep ALL-CAPS tokens even if short (E0, QM, AI, ...)
        is_acronym = t.isupper() and len(t) >= 2
        if not is_acronym and (len(low) <= 2 or low in _ASK_STOPWORDS):
            continue
        if low in seen:
            continue
        seen.add(low)
        result.append(low)
    return result


def _assess_knowledge(
    state: SessionState, question: str,
) -> Dict[str, Any]:
    """Assess what E₀ structurally knows about a question.

    For each extracted term, checks if any landscape node covers it
    (term appears as exact word in node concept name, not substring).
    Requires minimum relevance from _match_nodes to filter homonyms.
    Enriches confidence with trace_load depth signal.

    Returns:
      matches: full _match_nodes result
      terms: extracted question terms
      covered: {term: (node_id, score)} for matched terms
      gaps: list of unmatched terms
      coverage_ratio: fraction of terms with at least one match
      knowledge_depth: weighted confidence (navigated=1.0, structural=0.3)
    """
    _MIN_TERM_RELEVANCE = 0.4  # minimum _match_nodes score to accept

    matches = _match_nodes(question, state.landscape, state.unified_nodes)
    terms = _extract_question_terms(question)

    covered: Dict[str, Tuple[str, float]] = {}
    for term in terms:
        best_score = 0.0
        best_node: Optional[str] = None
        stemmed_term = _stem(term)
        for node_id, score in matches:
            if score < _MIN_TERM_RELEVANCE:
                continue
            concept = (
                node_id.split(":", 1)[1].lower()
                if ":" in node_id
                else node_id.lower()
            )
            concept_words = set(
                concept.replace("_", " ").replace("-", " ").split()
            )
            # Exact word match first
            if term in concept_words:
                if score > best_score:
                    best_score = score
                    best_node = node_id
            # Stemmed fallback: logistics↔logistic, processing↔process
            elif stemmed_term in {_stem(w) for w in concept_words}:
                # Slightly penalize stem match vs exact
                adj_score = score * 0.9
                if adj_score > best_score:
                    best_score = adj_score
                    best_node = node_id
        if best_node is not None:
            covered[term] = (best_node, best_score)

    gaps = [t for t in terms if t not in covered]
    coverage_ratio = (
        len(covered) / len(terms) if terms else 1.0
    )

    # Knowledge depth: check trace_load on matched nodes' edges
    hist = state.landscape.historization
    deep_count = 0
    for term, (node_id, _score) in covered.items():
        has_trace = False
        for edge in state.landscape.edges:
            if edge.source == node_id or edge.target == node_id:
                if hist.trace_load(edge) > 0:
                    has_trace = True
                    break
        if has_trace:
            deep_count += 1

    structural_count = len(covered) - deep_count
    if terms:
        knowledge_depth = (
            (deep_count * 1.0 + structural_count * 0.3) / len(terms)
        )
    else:
        knowledge_depth = 1.0

    return {
        "matches": matches,
        "terms": terms,
        "covered": covered,
        "gaps": gaps,
        "coverage_ratio": coverage_ratio,
        "knowledge_depth": knowledge_depth,
        "deep_count": deep_count,
        "structural_count": structural_count,
    }


def _format_path_evidence(
    state: SessionState, path: List[str],
) -> str:
    """Format navigation path as readable evidence for answer synthesis.

    For each node in the path, includes: concept name, domain, description.
    For each edge transition, includes: relation type, quality.
    Deduplicates consecutive visits to the same node.
    """
    if not path:
        return "(no navigation path)"

    hist = state.landscape.historization
    node_meta = state.unified_nodes or {}
    lines: List[str] = []
    seen_nodes: set = set()

    for i, node_id in enumerate(path):
        if node_id in seen_nodes:
            continue
        seen_nodes.add(node_id)

        # Node info
        meta = node_meta.get(node_id, {})
        label = meta.get("label", node_id)
        desc = meta.get("description", "")
        domain = meta.get("domain", "unknown")

        node_line = f"  [{domain}] {label}"
        if desc:
            # Truncate long descriptions
            short = desc[:120] + "..." if len(desc) > 120 else desc
            node_line += f": {short}"
        lines.append(node_line)

        # Edge info (to next node)
        if i + 1 < len(path):
            next_node = path[i + 1]
            from e0_controller.landscape import Edge
            edge = Edge(node_id, next_node)
            edge_meta = state.landscape.edge_meta(node_id, next_node)
            rel_type = edge_meta.get("relation_type", "")
            q = hist.trace_quality(edge) if edge in state.landscape.edges else 0.0
            arrow = f"  → ({rel_type})" if rel_type else "  →"
            if q != 0.0:
                arrow += f" [quality={q:.2f}]"
            lines.append(arrow)

    return "\n".join(lines)


def _structural_answer(
    question: str, path: List[str], state: SessionState,
) -> str:
    """Generate a structural answer without LLM, from path + descriptions."""
    if not path:
        return "No structural evidence found for this question."

    node_meta = state.unified_nodes or {}
    seen: set = set()
    concepts: List[str] = []

    for node_id in path:
        if node_id in seen:
            continue
        seen.add(node_id)
        meta = node_meta.get(node_id, {})
        desc = meta.get("description", "")
        label = meta.get("label", node_id)
        if desc:
            concepts.append(f"{label}: {desc}")
        else:
            concepts.append(label)

    if not concepts:
        return "Navigation completed but no concept descriptions available."

    header = f"Based on {len(concepts)} connected concepts:"
    body = "\n".join(f"  • {c}" for c in concepts[:8])
    return f"{header}\n{body}"


def ask_run(
    state: SessionState, question: str, auto_learn: bool = True,
) -> Dict[str, Any]:
    """On-demand question answering: assess → gap-detect → learn → navigate.

    Pipeline:
      1. Knowledge assessment: match question terms against landscape
      2. Gap detection: identify terms with no structural match
      3. On-demand learning: teach_concept for each gap term (max 3)
      4. Re-assessment: measure coverage improvement
      5. Navigation: navigate from best match through combined knowledge
      6. Confidence: term coverage ratio as honest confidence signal

    Args:
        state: current session
        question: free-text question in natural language
        auto_learn: if True, automatically learn gap terms via LLM

    Returns structured result with assessment, gaps, learning, navigation.
    """
    # Phase 1: Knowledge assessment
    assessment = _assess_knowledge(state, question)

    # Phase 2: Learn gaps (if any and auto_learn)
    learned: List[Dict[str, Any]] = []
    if assessment["gaps"] and auto_learn:
        for term in assessment["gaps"][:_ASK_MAX_GAP_LEARN]:
            # Pass question context so LLM builds the right domain
            contextual = f"{term} (in context: {question})"
            result = teach_concept(state, contextual)
            learned.append({"term": term, "result": result})

    # Phase 3: Re-assess after learning
    if learned:
        assessment_after = _assess_knowledge(state, question)
    else:
        assessment_after = assessment

    # Phase 4: Navigate from best match
    anchor: Optional[str] = None
    nav_path: List[str] = []
    nav_steps = 0
    nav_crossings = 0
    nav_coverage_delta = 0.0
    all_matches = assessment_after["matches"]
    if all_matches:
        anchor = all_matches[0][0]
        _task_navigate(state, question, anchor, mode="ask")
        if state.history:
            last_round = state.history[-1]
            nav_path = last_round.path
            nav_steps = last_round.steps
            nav_crossings = last_round.domain_crossings
            nav_coverage_delta = last_round.coverage_delta

    # Phase 5: Answer synthesis
    answer: Optional[str] = None
    synthesis: Optional[Dict[str, Any]] = None
    if nav_path:
        try:
            adapter = _get_llm_adapter(state)
            evidence = _format_path_evidence(state, nav_path)
            synthesis = adapter.synthesize_answer(
                question=question,
                path_evidence=evidence,
                steps=nav_steps,
                domain_crossings=nav_crossings,
                coverage_delta=nav_coverage_delta,
            )
            answer = synthesis.get("answer")
        except Exception as exc:
            # LLM unavailable — structural fallback
            import sys
            diag = f"[ASK SYNTH DIAG] {type(exc).__name__}: {exc}"
            if hasattr(exc, "raw_response") and exc.raw_response:
                preview = exc.raw_response[:500]
                diag += f"\n[ASK SYNTH DIAG] raw ({len(exc.raw_response)} chars): {preview}"
            if hasattr(exc, "finish_reason"):
                diag += f"  finish_reason={exc.finish_reason}"
            print(diag, file=sys.stderr, flush=True)
            answer = _structural_answer(question, nav_path, state)
    elif nav_path == [] and anchor is None:
        answer = _structural_answer(question, [], state)

    # Confidence = knowledge depth (coverage weighted by trace_load)
    confidence = assessment_after["knowledge_depth"]

    # Journal event
    record_journal_event(state, "ask", {
        "question": question[:80],
        "terms": len(assessment["terms"]),
        "gaps_before": len(assessment["gaps"]),
        "gaps_after": len(assessment_after["gaps"]),
        "learned_count": len(learned),
        "coverage_before": assessment["coverage_ratio"],
        "coverage_after": assessment_after["coverage_ratio"],
        "depth_before": assessment["knowledge_depth"],
        "depth_after": assessment_after["knowledge_depth"],
        "confidence": confidence,
    })

    # Phase 6: Feedback on failure — low confidence signals unresolved gap
    if confidence < 0.2 and assessment_after["gaps"]:
        state.stagnation_streak += 1
        record_journal_event(state, "knowledge_gap_unresolved", {
            "question": question[:80],
            "unresolved_gaps": assessment_after["gaps"],
            "confidence": confidence,
            "stagnation_streak": state.stagnation_streak,
        })

    return {
        "question": question,
        "terms": assessment["terms"],
        "assessment_before": assessment,
        "learned": learned,
        "assessment_after": assessment_after,
        "anchor": anchor,
        "nav_path": nav_path,
        "confidence": confidence,
        "answer": answer,
        "synthesis": synthesis,
    }


def cmd_ask(state: SessionState, question: str) -> str:
    """Answer a question using on-demand gap detection and learning."""
    if not question.strip():
        return "Usage: ask <your question in natural language>"

    result = ask_run(state, question)
    md = state.output_format == "markdown"

    if md:
        lines = ["## Ask: On-Demand Q&A", ""]
    else:
        lines = ["Ask: On-Demand Q&A", "\u2550" * 60]

    lines.append(f"  Question: \"{question}\"")
    lines.append("")

    # ── Knowledge Assessment ──
    ab = result["assessment_before"]
    n_covered = len(ab["terms"]) - len(ab["gaps"])
    lines.append("  Knowledge Assessment")
    lines.append(f"    Terms: {', '.join(ab['terms'])}")
    lines.append(
        f"    Coverage: {ab['coverage_ratio']:.0%} "
        f"({n_covered}/{len(ab['terms'])} terms matched)"
    )

    if ab["covered"]:
        lines.append("    Known:")
        for term, (node, score) in ab["covered"].items():
            lines.append(
                f"      \u2713 {term} \u2192 {node} (relevance={score:.2f})"
            )
        if ab["deep_count"] > 0 or ab["structural_count"] > 0:
            lines.append(
                f"    Depth: {ab['deep_count']} navigated, "
                f"{ab['structural_count']} structural only"
            )

    if ab["gaps"]:
        lines.append("    Gaps:")
        for gap in ab["gaps"]:
            lines.append(f"      \u2717 {gap}")

    # ── On-Demand Learning ──
    if result["learned"]:
        lines.append("")
        lines.append("  On-Demand Learning")
        for item in result["learned"]:
            r = item["result"]
            if r.get("error"):
                lines.append(f"    \u2717 {item['term']}: {r['error']}")
            else:
                lines.append(
                    f"    \u2713 {item['term']}: "
                    f"{len(r['nodes_added'])} nodes, "
                    f"{r['total_new_edges']} edges "
                    f"(coverage \u0394={r['coverage_delta']:+.1%})"
                )

        aa = result["assessment_after"]
        lines.append(
            f"    Coverage: {ab['coverage_ratio']:.0%} "
            f"\u2192 {aa['coverage_ratio']:.0%}"
        )

    # ── Navigation ──
    if result["anchor"]:
        lines.append("")
        lines.append("  Navigation")
        lines.append(f"    Anchor: {result['anchor']}")
        if state.history:
            last = state.history[-1]
            lines.append(
                f"    Steps: {last.steps}  "
                f"Crossings: {last.domain_crossings}"
            )
            lines.append(
                f"    Coverage: "
                f"{last.assessment_before.coverage:.1%} \u2192 "
                f"{last.assessment_after.coverage:.1%} "
                f"(\u0394={last.coverage_delta:+.1%})"
            )

    # ── Answer ──
    if result.get("answer"):
        lines.append("")
        if md:
            lines.append("### Answer")
        else:
            lines.append("  Answer")
            lines.append("  " + "\u2500" * 56)
        for ans_line in result["answer"].split("\n"):
            lines.append(f"    {ans_line}")
        if result.get("synthesis") and result["synthesis"].get("key_concepts"):
            concepts = result["synthesis"]["key_concepts"]
            lines.append(f"    Key concepts: {', '.join(concepts)}")
        if result.get("synthesis") and not result["synthesis"].get(
            "evidence_sufficient", True
        ):
            lines.append(
                "    \u26a0 Evidence may be insufficient for a complete answer"
            )

    # ── Confidence ──
    lines.append("")
    conf = result["confidence"]
    if conf >= 0.8:
        verdict = "high \u2014 most terms structurally covered"
    elif conf >= 0.5:
        verdict = "moderate \u2014 partial structural coverage"
    else:
        verdict = "low \u2014 significant knowledge gaps remain"
    lines.append(f"  Confidence: {conf:.0%} \u2014 {verdict}")

    return "\n".join(lines)


def cmd_task(state: SessionState, text: str) -> str:
    """Process a user-provided difference as natural text.

    Three-tier matching:
    1. Single strong match (≥0.8) → known path, navigate directly
    2. Multiple matches → check/create connections, navigate
    3. No matches → LLM peer structures the input (C218)
    """
    if not text.strip():
        return "Usage: task <your question or observation in natural language>"

    matches = _match_nodes(text, state.landscape, state.unified_nodes)

    if not matches:
        # ── Tier 3: LLM Peer Structuring (C218) ──
        return _llm_peer_structure(state, text)

    top = matches[:8]
    best_rel = top[0][1]
    hist = state.landscape.historization

    # ── Tier 1: Strong single match — known concept ──
    if best_rel >= 0.8 and (len(top) < 2 or top[1][1] < 0.5):
        return _task_known_path(state, text, top[0])

    # ── Tier 2: Multiple matches — check/create connections ──
    if len(top) >= 2:
        return _task_connection(state, text, top)

    # Single weak match — still navigate from it
    return _task_known_path(state, text, top[0])


def _task_navigate(
    state: SessionState, text: str, anchor: str, mode: str = "task",
) -> Tuple[str, MultiDomainRoundResult]:
    """Shared navigation from anchor. Returns (output_lines, round_result)."""
    state.round_num += 1
    a_before = assess(state.landscape, state.unified_nodes)

    nav = navigate(
        state.landscape, state.unified_nodes,
        "explore", state.steps_per_round,
        start=anchor,
    )
    validate_confidence(nav["path"])
    a_after = assess(state.landscape, state.unified_nodes)
    coverage_delta = a_after.coverage - a_before.coverage

    reason_short = text[:60] + ("…" if len(text) > 60 else "")
    result = MultiDomainRoundResult(
        round_num=state.round_num,
        mode=mode,
        reason=f"User task: \"{reason_short}\"",
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
    consolidate(result, nav["new_edges"], dry_run=True,
                universe=state.active_universe)

    if coverage_delta <= 0.001:
        state.stagnation_streak += 1
    else:
        state.stagnation_streak = 0

    lines = [
        f"  Anchor: {anchor}",
        f"  Steps: {nav['steps']}  "
        f"Crossings: {nav['domain_crossings']}",
        f"  Coverage: {a_before.coverage:.1%} → {a_after.coverage:.1%} "
        f"(Δ={coverage_delta:+.1%})",
    ]

    text_out = communicate_round(
        result, state.landscape,
        stagnation_count=state.stagnation_streak,
        output_format=state.output_format,
    )

    return "\n".join(lines), text_out, nav["path"]


def _task_known_path(
    state: SessionState,
    text: str,
    match: Tuple[str, float],
) -> str:
    """Tier 1: Strong match on a known concept — navigate from it."""
    node_id, rel = match
    domain = _domain_of(node_id)
    meta = state.unified_nodes.get(node_id, {})
    label = meta.get("label", "")
    hist = state.landscape.historization

    lines = [
        "── Known Concept ──",
        f"  Query: \"{text}\"",
        f"  Match: {node_id} (relevance={rel:.2f})",
    ]
    if label:
        lines.append(f"  Label: {label}")
    lines.append(f"  Domain: {domain}")

    # Show neighborhood
    neighbors = []
    for edge in state.landscape.edges:
        if edge.source == node_id:
            m = hist.trace_load(edge)
            if m > 0:
                q = hist.trace_quality(edge)
                neighbors.append((edge.target, q, m))
    neighbors.sort(key=lambda x: -x[2])

    if neighbors:
        lines.append(f"  Neighborhood ({len(neighbors)} outgoing):")
        for tgt, q, m in neighbors[:6]:
            bar = _quality_bar(q)
            lines.append(f"    → {tgt}  q={q:+.3f} {bar}  m={m:.1f}")
        if len(neighbors) > 6:
            lines.append(f"    ... and {len(neighbors) - 6} more")

    lines.append("")
    lines.append("── Navigation ──")
    nav_lines, comm_out, path = _task_navigate(state, text, node_id)
    lines.append(nav_lines)
    lines.append("")
    lines.append(comm_out)

    return "\n".join(lines)


def _task_connection(
    state: SessionState,
    text: str,
    matches: List[Tuple[str, float]],
) -> str:
    """Tier 2: Multiple matches — check existing connections, create if needed."""
    hist = state.landscape.historization
    top = matches[:5]

    lines = [
        "── Structural Matching ──",
        f"  Query: \"{text}\"",
        f"  {len(matches)} matching node(s):",
        "",
    ]

    for node_id, rel in matches[:8]:
        domain = _domain_of(node_id)
        meta = state.unified_nodes.get(node_id, {})
        label = meta.get("label", "")
        label_str = f"  ({label})" if label else ""
        lines.append(
            f"  {node_id:<35s} [{domain:>9s}]  "
            f"relevance={rel:.2f}{label_str}"
        )
    if len(matches) > 8:
        lines.append(f"  ... and {len(matches) - 8} more")

    # ── Check connectivity between top matches ──
    lines.append("")
    lines.append("── Connectivity ──")
    existing = []
    missing = []
    for i, (src_id, _) in enumerate(top):
        for j, (tgt_id, _) in enumerate(top):
            if i >= j:
                continue
            edge = Edge(src_id, tgt_id)
            m = hist.trace_load(edge)
            if m > 0:
                q = hist.trace_quality(edge)
                existing.append((src_id, tgt_id, q, m))
            else:
                # Check reverse
                rev = Edge(tgt_id, src_id)
                m_rev = hist.trace_load(rev)
                if m_rev > 0:
                    q_rev = hist.trace_quality(rev)
                    existing.append((tgt_id, src_id, q_rev, m_rev))
                else:
                    missing.append((src_id, tgt_id))

    if existing:
        lines.append("  Existing connections:")
        for src, tgt, q, m in existing[:6]:
            bar = _quality_bar(q)
            lines.append(
                f"    {src} → {tgt}  q={q:+.3f} {bar}  m={m:.1f}"
            )

    # ── Create missing connections (the Δ becomes structure) ──
    created = []
    if missing:
        lines.append(f"  Creating {len(missing)} new connection(s):")
        for src_id, tgt_id in missing:
            state.landscape.add_edge(
                src_id, tgt_id, 0.4, 1.0,
                relation_type="human_structural",
            )
            state.landscape.add_edge(
                tgt_id, src_id, 0.4, 1.0,
                relation_type="human_structural",
            )
            created.append((src_id, tgt_id))
            lines.append(f"    + {src_id} ↔ {tgt_id}")

    if not existing and not missing:
        lines.append("  Single-node matches only.")

    # ── Navigate from anchor ──
    anchor = top[0][0]
    lines.append("")
    lines.append("── Navigation ──")
    mode = "task_connect" if created else "task"
    nav_lines, comm_out, path = _task_navigate(state, text, anchor, mode)
    lines.append(nav_lines)

    visited = [n for n, _ in matches[:8] if n in path]
    unvisited = [n for n, _ in matches[:8] if n not in path]
    if visited:
        lines.append(f"  Visited matched nodes: {', '.join(visited)}")
    if unvisited:
        lines.append(f"  Not reached: {', '.join(unvisited[:5])}")

    lines.append("")
    lines.append(comm_out)

    return "\n".join(lines)


# Rating → HumanAction mapping
_RATING_ACTION = {
    "helpful": HumanAction.CLICK,
    "yes": HumanAction.CLICK,
    "good": HumanAction.CLICK,
    "+": HumanAction.CLICK,
    "not": HumanAction.DISMISS,
    "no": HumanAction.DISMISS,
    "bad": HumanAction.DISMISS,
    "-": HumanAction.DISMISS,
    "confused": HumanAction.CONFUSION,
    "?": HumanAction.CONFUSION,
}


def cmd_rate(state: SessionState, panel_idx: int, rating: str) -> str:
    """Rate a panel from the last output. Feeds back into perception."""
    if state.last_spec is None:
        return "No output to rate yet. Run a command first."

    if state.perception is None:
        return "No perception domain loaded. Feedback unavailable."

    panels = state.last_spec.panels
    if panel_idx < 0 or panel_idx >= len(panels):
        return (
            f"Panel index {panel_idx} out of range. "
            f"Valid: 0–{len(panels) - 1} ({len(panels)} panels)."
        )

    action = _RATING_ACTION.get(rating.lower())
    if action is None:
        return (
            f"Unknown rating '{rating}'. "
            f"Use: helpful / not / confused  (or +/-/?)"
        )

    panel = panels[panel_idx]
    event = ingest_panel_feedback(state.perception, panel, action)

    # Show what happened
    profile = state.perception.profile(panel.perception)
    return (
        f"Rated panel {panel_idx} ({panel.label}): "
        f"{action.value} → {event.outcome.value}\n"
        f"  Perception '{panel.perception}': "
        f"load={profile.trace_load:.1f}, quality={profile.quality:+.3f}"
    )


# ── Universe Management (C245) ────────────────────────────────────────


def _ensure_main_universe(state: SessionState) -> None:
    """Ensure the 'main' universe exists in the registry.

    Lazily creates it from the session's top-level landscape on first access.
    This maintains backward compatibility — existing sessions that lack
    universes get a 'main' universe wrapping their current landscape.
    """
    if "main" not in state.universes:
        state.universes["main"] = UniverseState(
            name="main",
            landscape=state.landscape,
            unified_nodes=state.unified_nodes,
            stats=state.stats,
            history=state.history,
            round_num=state.round_num,
            stagnation_streak=state.stagnation_streak,
        )


def _sync_active_to_session(state: SessionState) -> None:
    """Sync the active universe's data back to session top-level fields.

    The session's top-level landscape/unified_nodes/stats always mirror
    the active universe. This ensures all existing commands work unchanged.
    """
    u = state.universes.get(state.active_universe)
    if u is None:
        return
    state.landscape = u.landscape
    state.unified_nodes = u.unified_nodes
    state.stats = u.stats
    state.history = u.history
    state.round_num = u.round_num
    state.stagnation_streak = u.stagnation_streak


def _sync_session_to_active(state: SessionState) -> None:
    """Sync session top-level fields back to the active universe.

    Called after commands that modify session state (run, teach, etc.)
    to keep the universe registry in sync.
    """
    u = state.universes.get(state.active_universe)
    if u is None:
        return
    u.landscape = state.landscape
    u.unified_nodes = state.unified_nodes
    u.stats = state.stats
    u.history = state.history
    u.round_num = state.round_num
    u.stagnation_streak = state.stagnation_streak


def universe_create(state: SessionState, name: str) -> str:
    """Create a new empty universe with a fresh landscape."""
    _ensure_main_universe(state)

    if name in state.universes:
        return f"Universe '{name}' already exists."

    if not name.isidentifier():
        return (
            f"Invalid universe name '{name}'. "
            f"Use letters, digits, underscores (no spaces)."
        )

    landscape, unified_nodes, stats = build_multidomain_landscape()
    u = UniverseState(
        name=name,
        landscape=landscape,
        unified_nodes=unified_nodes,
        stats=stats,
    )
    state.universes[name] = u

    record_journal_event(state, "universe_created", {"name": name})
    return (
        f"Universe '{name}' created "
        f"({stats['total_nodes']} nodes, {stats['total_edges']} edges).\n"
        f"  Switch with: universe switch {name}"
    )


def universe_list(state: SessionState) -> str:
    """List all universes with basic stats."""
    _ensure_main_universe(state)

    lines = ["Universes:"]
    for name, u in state.universes.items():
        marker = " ◀ active" if name == state.active_universe else ""
        n_states = len(list(u.landscape.states))
        n_edges = len(list(u.landscape.edges))
        l_nodes = sum(
            1 for s in u.landscape.states if s.startswith("L:")
        )
        lines.append(
            f"  {name}: {n_states} states, {n_edges} edges, "
            f"{l_nodes} learned (L:), round {u.round_num}{marker}"
        )
    return "\n".join(lines)


def universe_switch(state: SessionState, name: str) -> str:
    """Switch to a different universe."""
    _ensure_main_universe(state)

    if name not in state.universes:
        available = ", ".join(state.universes.keys())
        return f"Universe '{name}' not found. Available: {available}"

    if name == state.active_universe:
        return f"Already in universe '{name}'."

    # Save current universe state
    _sync_session_to_active(state)

    # Switch
    state.active_universe = name
    _sync_active_to_session(state)

    record_journal_event(state, "universe_switched", {"to": name})

    u = state.universes[name]
    n_states = len(list(u.landscape.states))
    n_edges = len(list(u.landscape.edges))
    return (
        f"Switched to universe '{name}' "
        f"({n_states} states, {n_edges} edges, round {u.round_num})."
    )


def universe_delete(state: SessionState, name: str) -> str:
    """Delete a universe (cannot delete the active one)."""
    _ensure_main_universe(state)

    if name not in state.universes:
        return f"Universe '{name}' not found."

    if name == "main":
        return "Cannot delete the 'main' universe."

    if name == state.active_universe:
        return (
            f"Cannot delete active universe '{name}'. "
            f"Switch to another universe first."
        )

    del state.universes[name]
    record_journal_event(state, "universe_deleted", {"name": name})
    return f"Universe '{name}' deleted."


def cmd_universe(state: SessionState, arg: str) -> str:
    """Handle universe subcommands: create, list, switch, delete."""
    if not arg:
        return universe_list(state)

    parts = arg.split(None, 1)
    subcmd = parts[0].lower()
    subarg = parts[1].strip() if len(parts) > 1 else ""

    if subcmd == "list":
        return universe_list(state)

    if subcmd == "create":
        if not subarg:
            return "Usage: universe create <name>"
        return universe_create(state, subarg)

    if subcmd == "switch":
        if not subarg:
            return "Usage: universe switch <name>"
        return universe_switch(state, subarg)

    if subcmd == "delete":
        if not subarg:
            return "Usage: universe delete <name>"
        return universe_delete(state, subarg)

    return (
        f"Unknown subcommand '{subcmd}'. "
        f"Usage: universe [create|list|switch|delete] [name]"
    )


# ── CouplingRouter Integration (C247) ─────────────────────────────────


def _universe_to_coupling(us: UniverseState) -> Universe:
    """Convert a session UniverseState to a CouplingRouter Universe.

    CouplingRouter needs execute_fn/start/goal which don't apply in
    interactive-session context.  We provide inert stubs.
    """
    return Universe(
        name=us.name,
        landscape=us.landscape,
        execute_fn=lambda s, t: Outcome.SUCCESS,
        start="",
        goal="",
    )


def _ensure_coupling_router(state: SessionState) -> Optional[CouplingRouter]:
    """Lazily create or update the CouplingRouter when ≥2 universes exist.

    Returns the router if ≥2 universes, None otherwise.
    """
    _ensure_main_universe(state)
    if len(state.universes) < 2:
        state.coupling_router = None
        return None

    universes = [_universe_to_coupling(u) for u in state.universes.values()]

    if state.coupling_router is None:
        state.coupling_router = CouplingRouter(universes)
    else:
        # Sync membership: add new, remove departed
        existing = set(state.coupling_router.universes.keys())
        current = {u.name for u in universes}
        for u in universes:
            if u.name not in existing:
                state.coupling_router.add_universe(u)
        for name in existing - current:
            state.coupling_router.remove_universe(name)
        # Update structural distances (landscapes may have changed)
        # Refresh Universe objects (landscape references may have changed)
        for u in universes:
            if u.name in state.coupling_router.universes:
                state.coupling_router.universes[u.name] = u
        state.coupling_router.update_distances()

    return state.coupling_router


def _transfer_l_nodes(
    source_landscape: Any,
    target_landscape: Any,
) -> Tuple[int, int]:
    """Transfer L: nodes and L:-related edges from source to target.

    Returns (nodes_added, edges_added).
    """
    source_l_nodes = {n for n in source_landscape.states if n.startswith("L:")}
    existing_nodes = target_landscape.states

    nodes_added = 0
    for node in source_l_nodes:
        if node not in existing_nodes:
            target_landscape.add_state(node)
            nodes_added += 1

    edges_added = 0
    for edge in source_landscape.edges:
        src, tgt = edge.source, edge.target
        if not (src.startswith("L:") or tgt.startswith("L:")):
            continue
        if src in target_landscape.states and tgt in target_landscape.states:
            if not target_landscape.has_edge(src, tgt):
                delta = source_landscape.difference(src, tgt)
                resistance = source_landscape.effective_resistance(src, tgt)
                target_landscape.add_edge(
                    src, tgt,
                    delta=delta if delta is not None else 0.5,
                    resistance=max(resistance, 0.1) if resistance is not None else 1.0,
                    relation_type="coupled",
                )
                edges_added += 1

    return nodes_added, edges_added


def couple_run(
    state: SessionState,
    partner_name: Optional[str] = None,
    reason: CouplingReason = CouplingReason.RECOVERY,
    confidence_threshold: float = 0.3,
) -> Dict[str, Any]:
    """Bidirectional L: transfer between active universe and partner.

    If *partner_name* is given, couples with that specific universe.
    Otherwise uses CouplingRouter.select_partner() to pick the best
    partner based on *reason* (RECOVERY or EXPLORATION).

    Transfers L: nodes and their edges in **both directions**:
    partner → active AND active → partner.  Only edges with both
    endpoints present after node transfer are copied.  The coupling
    outcome is historized on the router.

    Returns a result dict with transfer statistics.
    """
    _ensure_main_universe(state)
    router = _ensure_coupling_router(state)

    if router is None:
        return {"error": "Need ≥2 universes for coupling. Use 'universe create <name>'."}

    active_name = state.active_universe
    active_us = state.universes[active_name]
    active_cu = _universe_to_coupling(active_us)

    # Select partner
    if partner_name:
        if partner_name not in state.universes:
            return {"error": f"Universe '{partner_name}' not found."}
        if partner_name == active_name:
            return {"error": "Cannot couple a universe with itself."}
        partner_us = state.universes[partner_name]
        selection = CouplingSelection(
            partner=_universe_to_coupling(partner_us),
            reason=reason,
            score=0.0,
            edge_delta=structural_distance(active_cu, _universe_to_coupling(partner_us)),
            coupling_quality=0.0,
        )
    else:
        selections = router.select_partner(active_cu, reason)
        if not selections:
            return {"error": "No coupling partner available."}
        selection = selections[0]
        partner_us = state.universes[selection.partner.name]

    # Bidirectional transfer: partner → active AND active → partner
    partner_landscape = partner_us.landscape
    active_landscape = state.landscape  # = active_us.landscape via sync

    nodes_in, edges_in = _transfer_l_nodes(partner_landscape, active_landscape)
    nodes_out, edges_out = _transfer_l_nodes(active_landscape, partner_landscape)

    # Historize on router — based on total gained
    gained = nodes_in + edges_in + nodes_out + edges_out
    outcome = Outcome.SUCCESS if gained > 0 else Outcome.FAILURE
    router.historize(active_name, selection.partner.name, outcome)

    return {
        "partner": selection.partner.name,
        "reason": selection.reason.value,
        "score": round(selection.score, 4),
        "edge_delta": round(selection.edge_delta, 4),
        "nodes_transferred": nodes_in + nodes_out,
        "edges_transferred": edges_in + edges_out,
        "inbound": {"nodes": nodes_in, "edges": edges_in},
        "outbound": {"nodes": nodes_out, "edges": edges_out},
        "outcome": outcome.name,
    }


def couple_status(state: SessionState) -> str:
    """Show coupling router status: universes, weights, distances."""
    router = _ensure_coupling_router(state)
    if router is None:
        return "Coupling inactive (need ≥2 universes)."
    return router.summary()


def cmd_couple(state: SessionState, arg: str) -> str:
    """Handle couple subcommands: <name>, explore, recover, status."""
    if not arg:
        # Default: auto-select via RECOVERY
        result = couple_run(state)
        if "error" in result:
            return result["error"]
        return _format_couple_result(result)

    parts = arg.split(None, 1)
    subcmd = parts[0].lower()

    if subcmd == "status":
        return couple_status(state)

    if subcmd == "explore":
        result = couple_run(state, reason=CouplingReason.EXPLORATION)
        if "error" in result:
            return result["error"]
        return _format_couple_result(result)

    if subcmd == "recover":
        result = couple_run(state, reason=CouplingReason.RECOVERY)
        if "error" in result:
            return result["error"]
        return _format_couple_result(result)

    # Treat as partner name
    result = couple_run(state, partner_name=subcmd)
    if "error" in result:
        return result["error"]
    return _format_couple_result(result)


def _format_couple_result(result: Dict[str, Any]) -> str:
    """Format couple_run result for display."""
    inb = result.get("inbound", {})
    outb = result.get("outbound", {})
    lines = [
        f"Coupled with '{result['partner']}' ({result['reason']})",
        f"  Structural distance: {result['edge_delta']:.4f}",
        f"  Inbound  (partner → active): {inb.get('nodes', 0)} nodes, {inb.get('edges', 0)} edges",
        f"  Outbound (active → partner): {outb.get('nodes', 0)} nodes, {outb.get('edges', 0)} edges",
        f"  Total: {result['nodes_transferred']} nodes, {result['edges_transferred']} edges",
        f"  Outcome: {result['outcome']}",
    ]
    return "\n".join(lines)


HELP_TEXT = """
E₀ Interactive Session — Commands
──────────────────────────────────
  run [N]          Execute next N rounds (default: 1)
  teach <concept>  Teach E₀ new material (LLM → inject → explore)
  status           Current landscape overview
  focus <domain>   Zoom into canon, bootstrap, or en
  trajectory       Coverage/T_s/mode progression over rounds
  diagnose         Per-domain stagnation analysis + bottleneck
  escalate         Manually trigger stagnation escalation (levels 1—5)
  journal [note]   Session journal: view events or annotate
  reflect          Meta-reflection: analyze learning patterns
  curriculum [c]   Run structured curriculum (ontodynamics, …)
  dream [N]        Dream consolidation: cross-domain equivalences
  sleep [N]        Wake-sleep cycle: navigate + auto-dream
  tune [N]         Self-tune parameters via Self-Graph (max N rounds)
  auto [N]         Autonomous learning loop (max N steps)
  selflearn        Self-learn: E₀ learns itself first (canon → mechanism → dream)
  ask <question>   On-demand Q&A: assess → gap-detect → learn → answer
  universe [sub]   Manage E₀ universes (create|list|switch|delete)
  couple [sub]     Couple with another universe (explore|recover|status|<name>)
  why              Explain the last decision
  detail [N]       Last round's path edge by edge (or round N)
  inspect <s> <t>  Deep view of edge s→t
  rate <i> <rating> Rate panel i (helpful / not / confused)
  save [path]      Save session state to disk
  regenerate       Regenerate seed from current session + discoveries
  summary          Full cycle summary so far
  help             Show this help
  quit / exit      End session (auto-saves)

  Or just type any text — E₀ will try to match it structurally,
  and call the LLM peer if needed.
"""


# ── Session Persistence (C225, extended C226) ─────────────────────────

SESSION_STATE_PATH = os.path.join("memos", "session_state.json")
_PERCEPTION_SEED = os.path.join("memos", "perception_pretrained.json")


def _assessment_to_dict(a: "MultiDomainAssessment") -> dict:
    """Serialize a MultiDomainAssessment to a lightweight dict."""
    return {
        "total_nodes": a.total_nodes,
        "total_edges": a.total_edges,
        "visited_nodes": a.visited_nodes,
        "coverage": round(a.coverage, 6),
        "frontier_size": a.frontier_size,
        "T_s": round(a.T_s, 6),
        "mean_quality": round(a.mean_quality, 6),
        "stale_edges": a.stale_edges,
        "canon_coverage": round(a.canon_coverage, 6),
        "bootstrap_coverage": round(a.bootstrap_coverage, 6),
        "en_coverage": round(a.en_coverage, 6),
        "canon_nodes": a.canon_nodes,
        "bootstrap_nodes": a.bootstrap_nodes,
        "en_nodes": a.en_nodes,
        "canon_visited": a.canon_visited,
        "bootstrap_visited": a.bootstrap_visited,
        "en_visited": a.en_visited,
        "mech_coverage": round(a.mech_coverage, 6),
        "mech_nodes": a.mech_nodes,
        "mech_visited": a.mech_visited,
    }


def _dict_to_assessment(d: dict) -> "MultiDomainAssessment":
    """Restore a MultiDomainAssessment from a serialized dict."""
    return MultiDomainAssessment(**d)


def _round_to_dict(result: "MultiDomainRoundResult") -> dict:
    """Serialize a round result for persistence (lightweight, no live refs)."""
    return {
        "round_num": result.round_num,
        "mode": result.mode,
        "reason": result.reason,
        "steps": result.steps,
        "path": result.path,
        "new_edges": result.new_edges,
        "domain_crossings": result.domain_crossings,
        "crossing_rate": round(result.crossing_rate, 4),
        "coverage_delta": round(result.coverage_delta, 4),
        "T_s_delta": round(result.T_s_delta, 3),
        "en_canon_crossings": result.en_canon_crossings,
        "en_bootstrap_crossings": result.en_bootstrap_crossings,
        "canon_bootstrap_crossings": result.canon_bootstrap_crossings,
        "mech_canon_crossings": result.mech_canon_crossings,
        "mech_bootstrap_crossings": result.mech_bootstrap_crossings,
        "mech_en_crossings": result.mech_en_crossings,
        "type_usage": result.type_usage,
        "assessment_before": _assessment_to_dict(result.assessment_before),
        "assessment_after": _assessment_to_dict(result.assessment_after),
    }


def _dict_to_round(d: dict) -> "MultiDomainRoundResult":
    """Restore a MultiDomainRoundResult from a serialized dict."""
    return MultiDomainRoundResult(
        round_num=d["round_num"],
        mode=d["mode"],
        reason=d["reason"],
        steps=d["steps"],
        path=d.get("path", []),
        new_edges=d["new_edges"],
        domain_crossings=d["domain_crossings"],
        crossing_rate=d.get("crossing_rate", 0.0),
        coverage_delta=d["coverage_delta"],
        T_s_delta=d["T_s_delta"],
        en_canon_crossings=d.get("en_canon_crossings", 0),
        en_bootstrap_crossings=d.get("en_bootstrap_crossings", 0),
        canon_bootstrap_crossings=d.get("canon_bootstrap_crossings", 0),
        mech_canon_crossings=d.get("mech_canon_crossings", 0),
        mech_bootstrap_crossings=d.get("mech_bootstrap_crossings", 0),
        mech_en_crossings=d.get("mech_en_crossings", 0),
        type_usage=d.get("type_usage", {}),
        assessment_before=_dict_to_assessment(d["assessment_before"]),
        assessment_after=_dict_to_assessment(d["assessment_after"]),
    )


def _perception_to_dict(perception: "PerceptionDomain") -> dict:
    """Serialize perception domain to an inline dict."""
    hist = perception.landscape.historization
    edges = []
    for edge in perception.landscape.edges:
        U, F = hist._effective_traces(edge)
        edges.append({
            "from": edge.source,
            "to": edge.target,
            "delta": perception.landscape.difference(edge.source, edge.target),
            "resistance": perception.landscape.base_resistance(
                edge.source, edge.target,
            ),
            "initial_U": round(U, 6),
            "initial_F": round(F, 6),
            "confidence": 1.0,
        })
    return {
        "tau": hist._tau,
        "spec": {
            "nodes": list(perception.primitives),
            "edges": edges,
        },
    }


def save_session(state: SessionState, path: Optional[str] = None,
                 write_back_perception: bool = False) -> str:
    """Save session state to JSON for later resume.

    Persists the full landscape (all traces), unified node metadata,
    edge metadata, perception domain, round history, and session
    bookkeeping.

    C226: History is serialized as lightweight dicts (no live Assessment
    refs). write_back_perception updates perception_pretrained.json so
    perception learning survives across sessions.

    Returns the absolute path of the written file.
    """
    import json
    import os
    import time
    from e0_controller.snapshot_codec import encode_landscape

    path = path or SESSION_STATE_PATH

    # Landscape + edge metadata
    landscape_data = encode_landscape(state.landscape)
    edge_meta = {}
    for e in state.landscape.edges:
        meta = state.landscape.edge_meta(e.source, e.target)
        if meta:
            edge_meta[f"{e.source}→{e.target}"] = meta

    # Perception (inline using same format as PerceptionDomain.save_state)
    perception_data = None
    if state.perception:
        perception_data = _perception_to_dict(state.perception)

    # History (C226: lightweight round dicts)
    history_data = [_round_to_dict(r) for r in state.history]

    data = {
        "meta": {
            "version": "1.1",
            "purpose": "E₀ session state — resume learning across restarts",
            "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "round_num": state.round_num,
            "stagnation_streak": state.stagnation_streak,
            "steps_per_round": state.steps_per_round,
            "output_format": state.output_format,
            "history_rounds": len(state.history),
        },
        "stats": state.stats,
        "landscape": landscape_data,
        "unified_nodes": state.unified_nodes,
        "edge_meta": edge_meta,
        "perception": perception_data,
        "history": history_data,
    }

    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # C226: Write-back perception learning
    if write_back_perception and state.perception:
        state.perception.save_state(_PERCEPTION_SEED)

    # C231: Persist session journal
    save_journal(state)

    return os.path.abspath(path)


def load_session(path: str) -> SessionState:
    """Load session state from a saved JSON file.

    Restores landscape, unified_nodes, perception, history, and session
    metadata. C226: History is fully restored from lightweight dicts —
    summary, detail, and why commands work after reload.

    Returns a ready-to-use SessionState.
    """
    import json
    from e0_controller.snapshot_codec import decode_landscape
    from e0_controller.bootstrapper import bootstrap_landscape

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    meta = data["meta"]
    landscape = decode_landscape(data["landscape"])

    # Restore edge metadata
    for key, emeta in data.get("edge_meta", {}).items():
        parts = key.split("→")
        if len(parts) == 2:
            source, target = parts
            if landscape.has_edge(source, target):
                landscape.set_edge_meta(source, target, **emeta)

    unified_nodes = data["unified_nodes"]
    stats = data["stats"]

    # Restore perception
    perception = None
    if data.get("perception"):
        pdata = data["perception"]
        p_landscape = bootstrap_landscape(pdata["spec"])
        perception = PerceptionDomain(p_landscape, pdata["spec"]["nodes"])

    # Restore history (C226)
    history = [_dict_to_round(d) for d in data.get("history", [])]

    return SessionState(
        landscape=landscape,
        unified_nodes=unified_nodes,
        stats=stats,
        perception=perception,
        history=history,
        round_num=meta.get("round_num", 0),
        stagnation_streak=meta.get("stagnation_streak", 0),
        steps_per_round=meta.get("steps_per_round", 40),
        output_format=meta.get("output_format", "text"),
    )


def cmd_save(state: SessionState, path: Optional[str] = None) -> str:
    """Save session state and return confirmation."""
    saved_path = save_session(state, path, write_back_perception=True)
    return (
        f"Session saved: {saved_path}\n"
        f"  Rounds: {state.round_num}, "
        f"Nodes: {state.stats.get('total_nodes', '?')}, "
        f"Edges: {state.stats.get('total_edges', '?')}"
    )


# ── Seed Regeneration (C227) ──────────────────────────────────────────


def regenerate_seed(
    state: SessionState,
    confidence_threshold: float = 0.4,
    path: Optional[str] = None,
) -> Dict[str, Any]:
    """Regenerate the self-knowledge seed from the current session.

    Three-step process:
      1. Materialize qualifying discovered_edges from learning_state.json
         into the session landscape (edges with confidence ≥ threshold
         that don't already exist).
      2. Re-assess to compute fresh coverage stats.
      3. Export via export_seed format (full snapshot).

    This closes the multi-session learning loop: Session A navigates,
    discovers edges → learning_state.json. Session B loads seed, runs
    more rounds. regenerate_seed folds A's + B's discoveries back into
    the seed so Session C starts with the union.

    Returns a result dict with stats about the regeneration.
    """
    from e0_controller.explore_bootstrap_landscape import load_learning_state
    from e0_controller.explore_self_knowledge import (
        SEED_PATH, SelfKnowledgeResult, export_seed,
    )

    path = path or SEED_PATH
    landscape = state.landscape

    # ── Step 1: Materialize discovered edges ──
    ls = load_learning_state()
    discovered = ls.get("discovered_edges", {}).get("edges", [])
    # C246: only materialize edges belonging to the active universe
    universe = getattr(state, "active_universe", "main")
    discovered = [e for e in discovered
                  if e.get("universe", "main") == universe]
    materialized = 0
    skipped_existing = 0
    skipped_low_conf = 0

    for edge_spec in discovered:
        src = edge_spec.get("from", "")
        tgt = edge_spec.get("to", "")
        conf = edge_spec.get("confidence", 0.0)

        if conf < confidence_threshold:
            skipped_low_conf += 1
            continue

        if not (src in landscape.states and tgt in landscape.states):
            continue  # nodes not in this landscape

        if landscape.has_edge(src, tgt):
            skipped_existing += 1
            continue

        delta = edge_spec.get("delta", 0.5)
        resistance = edge_spec.get("resistance", 1.0)
        landscape.add_edge(
            src, tgt,
            delta=delta,
            resistance=resistance,
            relation_type="discovered",
        )
        materialized += 1

    # ── Step 2: Re-assess ──
    a = assess(landscape, state.unified_nodes)

    # ── Step 3: Export ──
    result = SelfKnowledgeResult(
        rounds=state.round_num,
        targeted_passes=0,
        final_coverage=a.coverage,
        canon_coverage=a.canon_coverage,
        bootstrap_coverage=a.bootstrap_coverage,
        mech_coverage=a.mech_coverage,
        en_coverage=a.en_coverage,
        total_nodes=a.total_nodes,
        total_edges=landscape.edge_count(),
        shortcut_edges_created=materialized,
        converged=a.coverage >= 0.95,
    )

    seed_stats = {
        "total_nodes": a.total_nodes,
        "total_edges": landscape.edge_count(),
        "canon_nodes": a.canon_nodes,
        "bootstrap_nodes": a.bootstrap_nodes,
        "en_nodes": a.en_nodes,
    }

    saved_path = export_seed(
        landscape, state.unified_nodes, seed_stats, result, path,
    )

    return {
        "path": saved_path,
        "materialized_edges": materialized,
        "skipped_existing": skipped_existing,
        "skipped_low_confidence": skipped_low_conf,
        "total_discovered": len(discovered),
        "coverage": round(a.coverage, 4),
        "canon_coverage": round(a.canon_coverage, 4),
        "bootstrap_coverage": round(a.bootstrap_coverage, 4),
        "mech_coverage": round(a.mech_coverage, 4),
        "en_coverage": round(a.en_coverage, 4),
        "total_nodes": a.total_nodes,
        "total_edges": landscape.edge_count(),
    }


def cmd_regenerate(state: SessionState, path: Optional[str] = None) -> str:
    """Regenerate the self-knowledge seed and return status."""
    result = regenerate_seed(state, path=path)
    lines = [
        f"Seed regenerated: {result['path']}",
        f"  Coverage: {result['coverage']:.1%} "
        f"(Canon {result['canon_coverage']:.1%}, "
        f"Bootstrap {result['bootstrap_coverage']:.1%}, "
        f"Mech {result['mech_coverage']:.1%})",
        f"  Nodes: {result['total_nodes']}, "
        f"Edges: {result['total_edges']}",
        f"  Discovered edges materialized: "
        f"{result['materialized_edges']}/{result['total_discovered']} "
        f"(skipped: {result['skipped_existing']} existing, "
        f"{result['skipped_low_confidence']} low confidence)",
    ]
    return "\n".join(lines)


def cmd_help() -> str:
    """Show help text."""
    return HELP_TEXT.strip()


# ── REPL ───────────────────────────────────────────────────────────────


def build_session(
    steps_per_round: int = 40,
    output_format: str = "text",
    perception_path: Optional[str] = None,
    self_knowledge_path: Optional[str] = None,
    auto_detect: bool = False,
) -> SessionState:
    """Build an interactive session with the multi-domain landscape.

    C225: Fallback chain for warm start:
      1. Explicit ``self_knowledge_path`` (if provided and exists)
      2. ``memos/session_state.json`` (if auto_detect=True and exists)
      3. ``memos/self_knowledge_seed.json`` (if auto_detect=True and exists)
      4. Cold start via ``build_multidomain_landscape()``

    A session_state.json restored via ``load_session`` returns a full
    SessionState directly (landscape + perception + round_num, etc.).

    Args:
        self_knowledge_path: Explicit path to seed JSON.
        auto_detect: If True, try session_state then seed.
            Default is False (backward-compatible). Entry points
            (run_interactive, run_server) set True explicitly.
    """
    from e0_controller.explore_self_knowledge import SEED_PATH

    # ── Fallback chain: session_state → seed → cold start ──

    # 1. Try explicit path
    if self_knowledge_path and os.path.exists(self_knowledge_path):
        resolved = self_knowledge_path
    # 2. Auto-detect session state
    elif auto_detect and os.path.exists(SESSION_STATE_PATH):
        state = load_session(SESSION_STATE_PATH)
        state.steps_per_round = steps_per_round
        state.output_format = output_format
        return state
    # 3. Auto-detect seed
    elif auto_detect and os.path.exists(SEED_PATH):
        resolved = SEED_PATH
    else:
        resolved = None

    if resolved:
        from e0_controller.explore_self_knowledge import load_seed
        landscape, unified_nodes, meta = load_seed(resolved)
        stats = {
            "total_nodes": meta["node_count"],
            "total_edges": meta["edge_count"],
            "canon_nodes": sum(1 for n in unified_nodes if n.startswith("C:")),
            "bootstrap_nodes": sum(1 for n in unified_nodes
                                   if n.startswith("B:")),
            "en_nodes": sum(1 for n in unified_nodes
                            if n.startswith("EN:")),
            "canon_bootstrap_bridges": 0,   # not tracked in seed
            "en_bridges": 0,                # not tracked in seed
            "seed": resolved,
        }
    else:
        landscape, unified_nodes, stats = build_multidomain_landscape()

    # Load perception seed (session-scoped copy — never written back)
    _PERCEPTION_SEED = os.path.join("memos", "perception_pretrained.json")
    seed = perception_path or _PERCEPTION_SEED
    perception: Optional[PerceptionDomain] = None
    if os.path.exists(seed):
        perception = PerceptionDomain.from_saved(seed)
    else:
        perception = build_perception_domain()

    session_id = time.strftime("%Y%m%d_%H%M%S")
    state = SessionState(
        landscape=landscape,
        unified_nodes=unified_nodes,
        stats=stats,
        perception=perception,
        steps_per_round=steps_per_round,
        output_format=output_format,
        session_id=session_id,
    )

    # Journal: record session start (C231)
    record_journal_event(state, "session_start")

    return state


def dispatch(state: SessionState, user_input: str) -> Optional[str]:
    """Parse and dispatch a single user command.

    Returns the output string, or None for quit.

    C245: Syncs active universe before/after command execution.
    """
    # C245: Ensure universe registry exists and is synced
    if state.universes:
        _sync_active_to_session(state)

    result = _dispatch_inner(state, user_input)

    # C245: After any mutating command, sync back to active universe
    if state.universes and result is not None:
        _sync_session_to_active(state)

    return result


def _dispatch_inner(state: SessionState, user_input: str) -> Optional[str]:
    """Inner dispatch without universe sync (called by dispatch)."""
    raw = user_input.strip()
    if not raw:
        return ""

    parts = raw.split(None, 1)
    cmd = parts[0].lower().rstrip(":")
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

    if cmd == "task":
        if not arg:
            return "Usage: task <your question or observation in natural language>"
        return cmd_task(state, arg)

    if cmd == "teach":
        if not arg:
            return "Usage: teach <concept> [rounds]  (e.g. teach water 3)"
        return cmd_teach(state, arg)

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

    if cmd == "trajectory":
        return cmd_trajectory(state)

    if cmd == "diagnose":
        return cmd_diagnose(state)

    if cmd == "escalate":
        return cmd_escalate(state)

    if cmd == "journal":
        return cmd_journal(state, arg if arg else None)

    if cmd == "reflect":
        return cmd_reflect(state)

    if cmd == "curriculum":
        return cmd_curriculum(state, arg if arg else None)

    if cmd == "dream":
        return cmd_dream(state, arg if arg else None)

    if cmd == "sleep":
        return cmd_sleep(state, arg if arg else None)

    if cmd == "tune":
        return cmd_tune(state, arg if arg else None)

    if cmd == "auto":
        return cmd_auto(state, arg if arg else None)

    if cmd == "selflearn":
        return cmd_selflearn(state)

    if cmd == "ask":
        if not arg:
            return "Usage: ask <your question in natural language>"
        return cmd_ask(state, arg)

    if cmd == "detail":
        round_n = None
        if arg:
            try:
                round_n = int(arg)
            except ValueError:
                return f"Invalid round number: '{arg}'. Usage: detail [N]"
        return cmd_detail(state, round_n)

    if cmd == "inspect":
        if not arg:
            return "Usage: inspect <source> <target>"
        inspect_parts = arg.split()
        if len(inspect_parts) < 2:
            return "Usage: inspect <source> <target>"
        return cmd_inspect(state, inspect_parts[0], inspect_parts[1])

    if cmd == "rate":
        if not arg:
            return "Usage: rate <panel_index> <helpful|not|confused>"
        rate_parts = arg.split(None, 1)
        if len(rate_parts) < 2:
            return "Usage: rate <panel_index> <helpful|not|confused>"
        try:
            idx = int(rate_parts[0])
        except ValueError:
            return f"Invalid panel index: '{rate_parts[0]}'. Must be a number."
        return cmd_rate(state, idx, rate_parts[1])

    if cmd == "save":
        return cmd_save(state, arg if arg else None)

    if cmd == "universe":
        return cmd_universe(state, arg)

    if cmd == "couple":
        return cmd_couple(state, arg)

    if cmd == "regenerate":
        return cmd_regenerate(state, arg if arg else None)

    # Unrecognized command → treat entire input as free-text task
    return cmd_task(state, raw)


def run_interactive(
    steps_per_round: int = 40,
    output_format: str = "text",
    seed_path: Optional[str] = None,
) -> None:
    """Main REPL entry point.  C225: auto-detect seed, auto-save on quit."""
    state = build_session(
        steps_per_round=steps_per_round,
        output_format=output_format,
        self_knowledge_path=seed_path,
        auto_detect=True,
    )

    source = state.stats.get("seed", "cold start")
    print(f"\n{'═' * 60}")
    print(f"  E₀ Interactive Session")
    print(f"{'═' * 60}")
    print(f"  Source:    {source}")
    print(f"  Landscape: {state.stats['total_nodes']} nodes, "
          f"{state.stats['total_edges']} edges")
    print(f"  Domains:   Canon ({state.stats['canon_nodes']}), "
          f"Bootstrap ({state.stats['bootstrap_nodes']}), "
          f"EN ({state.stats['en_nodes']})")
    print(f"  Format:    {output_format}")
    if state.perception is not None:
        snap = state.perception.snapshot()
        print(f"  Perception: {len(state.perception.primitives)} primitives, "
              f"load={snap.total_load:.0f} (session-scoped)")
    print(f"  Type 'help' for commands, 'quit' to exit.")
    print(f"{'═' * 60}\n")

    while True:
        try:
            user_input = input("E₀> ")
        except (EOFError, KeyboardInterrupt):
            print("\n  Auto-saving session...")
            save_session(state, write_back_perception=True)
            print("Session ended.")
            break

        result = dispatch(state, user_input)
        if result is None:
            if state.history:
                print(f"\n  {len(state.history)} rounds completed. "
                      f"Final coverage: "
                      f"{state.history[-1].assessment_after.coverage:.1%}")
            print("  Auto-saving session...")
            save_session(state, write_back_perception=True)
            print("Session ended.")
            break

        if result:
            print(result)


# ── CLI ────────────────────────────────────────────────────────────────


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="E₀ Interactive Text Session (C213/C225)")
    parser.add_argument("--steps", type=int, default=40,
                        help="Steps per round (default: 40)")
    parser.add_argument("--format", dest="fmt", default="text",
                        choices=["text", "markdown", "md"],
                        help="Output format (default: text)")
    parser.add_argument("--seed", type=str, default=None,
                        help="Path to seed/session JSON (auto-detects if omitted)")
    args = parser.parse_args()

    fmt = "markdown" if args.fmt == "md" else args.fmt

    run_interactive(
        steps_per_round=args.steps,
        output_format=fmt,
        seed_path=args.seed,
    )


if __name__ == "__main__":
    main()
