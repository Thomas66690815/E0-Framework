"""E₀ Interactive Text Session (C213, extended C214/C216/C217).

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

Commands:
  run [N]       — Execute the next N rounds (default: 1)
  task <text>   — Introduce a difference in natural language
  status        — Show current landscape overview
  focus <domain> — Zoom into canon, bootstrap, or en
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
from e0_controller.feedback import (
    HumanAction,
    FeedbackResult,
    ingest_panel_feedback,
)
from e0_controller.perception import PerceptionDomain, build_perception_domain
from e0_controller.primitives import Edge, Outcome
from e0_controller.ui_emitter import UISpec


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

        # Also match against label and description
        meta = node_meta.get(node_id, {})
        label = str(meta.get("label", "")).lower()
        desc = str(meta.get("description", "")).lower()
        semantic = f"{label} {desc}"
        sem_words = set(semantic.replace("_", " ").replace("-", " ").split())
        sem_words = {w for w in sem_words if len(w) > 2}
        sem_overlap = len(sem_words & tokens)

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
        consolidate(result, nav["new_edges"], dry_run=True)

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
    consolidate(result, nav["new_edges"], dry_run=True)

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


HELP_TEXT = """
E₀ Interactive Session — Commands
──────────────────────────────────
  run [N]          Execute next N rounds (default: 1)
  status           Current landscape overview
  focus <domain>   Zoom into canon, bootstrap, or en
  why              Explain the last decision
  detail [N]       Last round's path edge by edge (or round N)
  inspect <s> <t>  Deep view of edge s→t
  rate <i> <rating> Rate panel i (helpful / not / confused)
  summary          Full cycle summary so far
  help             Show this help
  quit / exit      End session

  Or just type any text — E₀ will try to match it structurally,
  and call the LLM peer if needed.
"""


def cmd_help() -> str:
    """Show help text."""
    return HELP_TEXT.strip()


# ── REPL ───────────────────────────────────────────────────────────────


def build_session(
    steps_per_round: int = 40,
    output_format: str = "text",
    perception_path: Optional[str] = None,
    self_knowledge_path: Optional[str] = None,
) -> SessionState:
    """Build an interactive session with the multi-domain landscape.

    If a self-knowledge seed exists (C220), loads it as warm start
    instead of building from scratch.  Perception is loaded separately.

    Args:
        self_knowledge_path: Explicit path to seed JSON.
            If None, builds fresh (no auto-detection).
    """
    import os

    if self_knowledge_path and os.path.exists(self_knowledge_path):
        from e0_controller.explore_self_knowledge import load_seed
        landscape, unified_nodes, meta = load_seed(self_knowledge_path)
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
            "seed": self_knowledge_path,
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

    return SessionState(
        landscape=landscape,
        unified_nodes=unified_nodes,
        stats=stats,
        perception=perception,
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

    if cmd == "task":
        if not arg:
            return "Usage: task <your question or observation in natural language>"
        return cmd_task(state, arg)

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

    # Unrecognized command → treat entire input as free-text task
    return cmd_task(state, raw)


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
