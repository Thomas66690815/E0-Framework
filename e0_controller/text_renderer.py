"""
E₀ Text Renderer (C208)
========================
Stateless renderer: UISpec → plain text / Markdown.

Parallel dispatcher to render_html() (C163). Same UISpec input,
different surface: structured text instead of HTML. Zero E0 knowledge.
Zero state. Pure format transformation.

7 text renderers (one per suggested_visual):
  heatmap   → urgency bar + data source
  tree      → indented key-value list
  timeline  → sequential markers
  bar       → ASCII progress bar
  text      → paragraph
  highlight → boxed emphasis
  dashboard → metric table

Urgency mapping:
  0.0–0.3  → informational (no marker)
  0.3–0.6  → notable (▸ prefix)
  0.6–0.8  → warning (⚠ prefix)
  0.8–1.0  → critical (‼ prefix, UPPER subject)

See docs/E0_HUMAN_COMMUNICATION_DESIGN_v1.md §8.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any, Dict

from .ui_emitter import UIPanel, UISpec


# ──────────────────────────────────────────────
# 1. Urgency Utilities
# ──────────────────────────────────────────────

def urgency_prefix(urgency: float) -> str:
    """Map urgency [0,1] to a text prefix marker."""
    if urgency >= 0.8:
        return "‼ "
    if urgency >= 0.6:
        return "⚠ "
    if urgency >= 0.3:
        return "▸ "
    return ""


def urgency_bar(urgency: float, width: int = 20) -> str:
    """ASCII bar: [████████░░░░░░░░░░░░] 0.42"""
    filled = int(urgency * width)
    empty = width - filled
    return f"[{'█' * filled}{'░' * empty}] {urgency:.2f}"


def urgency_label(urgency: float) -> str:
    """Human-readable urgency label."""
    if urgency >= 0.8:
        return "CRITICAL"
    if urgency >= 0.6:
        return "warning"
    if urgency >= 0.3:
        return "notable"
    return "info"


# ──────────────────────────────────────────────
# 2. Evidence Formatting
# ──────────────────────────────────────────────

def _format_evidence(evidence: Dict[str, Any], indent: int = 4) -> str:
    """Format evidence dict as indented key-value pairs."""
    if not evidence:
        return ""
    pad = " " * indent
    lines = []
    for k, v in evidence.items():
        if isinstance(v, float):
            lines.append(f"{pad}{k}: {v:.3f}")
        else:
            lines.append(f"{pad}{k}: {v}")
    return "\n".join(lines)


# ──────────────────────────────────────────────
# 3. Text Renderers (suggested_visual → text)
# ──────────────────────────────────────────────

def _render_heatmap_text(panel: UIPanel) -> str:
    """Urgency heatmap as text bar + data source."""
    prefix = urgency_prefix(panel.urgency)
    bar = urgency_bar(panel.urgency)
    return f"{prefix}{panel.data_source}\n  {bar}"


def _render_tree_text(panel: UIPanel) -> str:
    """Tree view as indented key-value list."""
    items = panel.evidence if panel.evidence else {"(no data)": "—"}
    lines = []
    for k, v in items.items():
        if isinstance(v, float):
            lines.append(f"  ├─ {k}: {v:.3f}")
        else:
            lines.append(f"  ├─ {k}: {v}")
    if lines:
        lines[-1] = lines[-1].replace("├─", "└─", 1)
    return "\n".join(lines)


def _render_timeline_text(panel: UIPanel) -> str:
    """Timeline as sequential markers."""
    items = panel.evidence if panel.evidence else {}
    if not items:
        return "  (no events)"
    lines = []
    entries = list(items.items())
    for i, (k, v) in enumerate(entries):
        marker = "●" if i < len(entries) - 1 else "◉"
        lines.append(f"  {marker} {k}: {v}")
    return "\n".join(lines)


def _render_bar_text(panel: UIPanel) -> str:
    """Bar as ASCII progress indicator."""
    return f"  {urgency_bar(panel.urgency, width=30)}"


def _render_text_text(panel: UIPanel) -> str:
    """Plain text paragraph."""
    return f"  {panel.label}\n  ({panel.data_source})"


def _render_highlight_text(panel: UIPanel) -> str:
    """Highlight as boxed emphasis."""
    prefix = urgency_prefix(panel.urgency)
    border = "─" * max(len(panel.label) + 4, 40)
    return (
        f"  ┌{border}┐\n"
        f"  │ {prefix}{panel.label:<{len(border) - 2}} │\n"
        f"  │ {panel.data_source:<{len(border) - 2}} │\n"
        f"  └{border}┘"
    )


def _render_dashboard_text(panel: UIPanel) -> str:
    """Dashboard as metric table."""
    if not panel.evidence:
        return "  (no metrics)"
    lines = []
    items = list(panel.evidence.items())[:6]
    max_key = max(len(str(k)) for k, _ in items) if items else 0
    for k, v in items:
        if isinstance(v, float):
            lines.append(f"  {str(k):<{max_key}}  {v:.3f}")
        else:
            lines.append(f"  {str(k):<{max_key}}  {v}")
    return "\n".join(lines)


_TEXT_RENDERERS = {
    "heatmap": _render_heatmap_text,
    "tree": _render_tree_text,
    "timeline": _render_timeline_text,
    "bar": _render_bar_text,
    "text": _render_text_text,
    "highlight": _render_highlight_text,
    "dashboard": _render_dashboard_text,
}


def _render_visual_text(panel: UIPanel) -> str:
    """Dispatch to the appropriate text renderer."""
    renderer = _TEXT_RENDERERS.get(panel.suggested_visual, _render_text_text)
    return renderer(panel)


# ──────────────────────────────────────────────
# 4. Panel Rendering
# ──────────────────────────────────────────────

_LABEL_MAX_LEN = 80


def _truncate_label(label: str, max_len: int = _LABEL_MAX_LEN) -> str:
    """Truncate long labels with ellipsis."""
    if len(label) <= max_len:
        return label
    return label[:max_len - 1] + "\u2026"


# Visual types that already render evidence data in their output.
# For these, skip the separate Evidence: block to avoid redundancy.
_EVIDENCE_IN_VISUAL = {"dashboard", "tree", "timeline", "heatmap"}


def _render_panel_text(panel: UIPanel, index: int) -> str:
    """Render a single panel as a text block."""
    prefix = urgency_prefix(panel.urgency)
    label = urgency_label(panel.urgency)

    header = f"[{index + 1}] {prefix}{_truncate_label(panel.label)}  ({label})"
    tags = f"    intent={panel.intent}  perception={panel.perception}  act={panel.language_act}"

    visual = _render_visual_text(panel)

    parts = [header, tags, visual]

    # Only show evidence block when the visual doesn't already display it
    if panel.suggested_visual not in _EVIDENCE_IN_VISUAL:
        evidence = _format_evidence(panel.evidence)
        if evidence:
            parts.append(f"    Evidence:")
            parts.append(evidence)

    return "\n".join(parts)


# ──────────────────────────────────────────────
# 5. Full Text Assembly
# ──────────────────────────────────────────────

def render_text(spec: UISpec, *, title: str = "E₀ Communication") -> str:
    """Render a UISpec as structured plain text.

    Args:
        spec: The UISpec to render.
        title: Document title.

    Returns:
        Complete text document as a string.
    """
    layout = spec.layout or "dashboard"
    separator = "═" * 60

    lines = [
        separator,
        f"  {title}",
        separator,
        f"  Layout: {layout} · Panels: {spec.panel_count} · "
        f"Max urgency: {spec.max_urgency:.2f}",
        f"  {spec.generated_at}",
    ]

    if spec.context:
        lines.append(f"  {spec.context}")

    lines.append(separator)
    lines.append("")

    for i, panel in enumerate(spec.panels):
        lines.append(_render_panel_text(panel, i))
        lines.append("")

    lines.append(separator)
    return "\n".join(lines)


def render_markdown(spec: UISpec, *, title: str = "E₀ Communication") -> str:
    """Render a UISpec as Markdown.

    Args:
        spec: The UISpec to render.
        title: Document title.

    Returns:
        Markdown document as a string.
    """
    layout = spec.layout or "dashboard"

    lines = [
        f"# {title}",
        "",
        f"**Layout:** {layout} · **Panels:** {spec.panel_count} · "
        f"**Max urgency:** {spec.max_urgency:.2f}  ",
        f"*{spec.generated_at}*",
    ]

    if spec.context:
        lines.append(f"  \n> {spec.context}")

    lines.append("")

    for i, panel in enumerate(spec.panels):
        prefix = urgency_prefix(panel.urgency)
        label = urgency_label(panel.urgency)

        lines.append(f"## {prefix}{panel.label}")
        lines.append("")
        lines.append(
            f"`{panel.intent}` · `{panel.perception}` · "
            f"`{panel.language_act}` · urgency: **{label}** ({panel.urgency:.2f})"
        )
        lines.append("")

        # Visual content
        visual = _render_visual_text(panel)
        lines.append("```")
        lines.append(visual)
        lines.append("```")
        lines.append("")

        # Evidence as collapsible
        if panel.evidence:
            lines.append("<details><summary>Evidence</summary>")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(panel.evidence, indent=2, default=str))
            lines.append("```")
            lines.append("")
            lines.append("</details>")
            lines.append("")

    return "\n".join(lines)


def render_to_text_file(
    spec: UISpec,
    path: str | pathlib.Path,
    *,
    title: str = "E₀ Communication",
    fmt: str = "text",
) -> pathlib.Path:
    """Render a UISpec to a text file on disk.

    Args:
        spec: The UISpec to render.
        path: File path for the output.
        title: Document title.
        fmt: "text" or "markdown".

    Returns:
        The resolved Path of the written file.
    """
    p = pathlib.Path(path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "markdown":
        content = render_markdown(spec, title=title)
    else:
        content = render_text(spec, title=title)
    p.write_text(content, encoding="utf-8")
    return p
