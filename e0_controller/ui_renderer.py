"""
E₀ UI Renderer (C163)
========================
Stateless renderer: UISpec → self-contained HTML.

This is the "dumb wrapper" that translates E0's structured UI
specification into a visual format humans can see. Zero E0 knowledge.
Zero state. Pure format transformation.

All intelligence (what to show, why, which perceptual strategy) lies
in E0 (C158–C162). The renderer only maps:
  - layout → CSS grid / single-column / alert banner
  - suggested_visual → HTML component (heatmap, tree, timeline, ...)
  - urgency → color (green 0.0 → yellow 0.5 → red 1.0)
  - evidence → collapsible detail section

See docs/E0_HUMAN_COMMUNICATION_DESIGN_v1.md §8.
"""

from __future__ import annotations

import html
import json
import pathlib
import webbrowser
from typing import Any, Dict, List, Optional

from .ui_emitter import UIPanel, UISpec


# ──────────────────────────────────────────────
# 1. Color Utilities
# ──────────────────────────────────────────────

def urgency_color(urgency: float) -> str:
    """Map urgency [0,1] to a CSS color: green → yellow → red."""
    u = max(0.0, min(1.0, urgency))
    if u <= 0.5:
        # green (76,175,80) → yellow (255,235,59)
        t = u / 0.5
        r = int(76 + (255 - 76) * t)
        g = int(175 + (235 - 175) * t)
        b = int(80 + (59 - 80) * t)
    else:
        # yellow (255,235,59) → red (244,67,54)
        t = (u - 0.5) / 0.5
        r = int(255 + (244 - 255) * t)
        g = int(235 + (67 - 235) * t)
        b = int(59 + (54 - 59) * t)
    return f"rgb({r},{g},{b})"


def urgency_text_color(urgency: float) -> str:
    """Return black or white text depending on urgency background."""
    return "#fff" if urgency > 0.6 else "#222"


# ──────────────────────────────────────────────
# 2. Visual Renderers (suggested_visual → HTML)
# ──────────────────────────────────────────────

def _render_evidence(evidence: Dict[str, Any]) -> str:
    """Render evidence as a collapsible detail section."""
    if not evidence:
        return ""
    escaped = html.escape(json.dumps(evidence, indent=2, default=str))
    return (
        '<details class="evidence">'
        "<summary>Evidence</summary>"
        f"<pre>{escaped}</pre>"
        "</details>"
    )


def _render_heatmap(panel: UIPanel) -> str:
    """Urgency heatmap: colored cell with data source."""
    bg = urgency_color(panel.urgency)
    fg = urgency_text_color(panel.urgency)
    src = html.escape(panel.data_source)
    return (
        f'<div class="visual-heatmap" '
        f'style="background:{bg};color:{fg};padding:12px;border-radius:6px">'
        f'<strong>{src}</strong><br>'
        f'urgency: {panel.urgency:.2f}'
        f'</div>'
    )


def _render_tree(panel: UIPanel) -> str:
    """Tree view: nested list from evidence keys."""
    items = panel.evidence if panel.evidence else {"(no data)": "—"}
    parts = ['<ul class="visual-tree">']
    for k, v in items.items():
        ek = html.escape(str(k))
        ev = html.escape(str(v))
        parts.append(f"<li><strong>{ek}:</strong> {ev}</li>")
    parts.append("</ul>")
    return "\n".join(parts)


def _render_timeline(panel: UIPanel) -> str:
    """Timeline: vertical sequence."""
    items = panel.evidence if panel.evidence else {}
    parts = ['<div class="visual-timeline">']
    for k, v in items.items():
        ek = html.escape(str(k))
        ev = html.escape(str(v))
        parts.append(
            f'<div class="timeline-entry">'
            f'<span class="timeline-dot">●</span> '
            f'<strong>{ek}</strong>: {ev}'
            f'</div>'
        )
    parts.append("</div>")
    return "\n".join(parts)


def _render_bar(panel: UIPanel) -> str:
    """Bar chart: CSS bar from urgency."""
    pct = int(panel.urgency * 100)
    bg = urgency_color(panel.urgency)
    return (
        f'<div class="visual-bar">'
        f'<div style="width:{pct}%;background:{bg};height:24px;'
        f'border-radius:4px;transition:width 0.3s"></div>'
        f'<span>{panel.urgency:.2f}</span>'
        f'</div>'
    )


def _render_highlight(panel: UIPanel) -> str:
    """Highlight box: bordered accent card."""
    bg = urgency_color(panel.urgency)
    src = html.escape(panel.data_source)
    label = html.escape(panel.label)
    return (
        f'<div class="visual-highlight" '
        f'style="border-left:4px solid {bg};padding:8px 12px">'
        f'<strong>{label}</strong><br>'
        f'<em>{src}</em>'
        f'</div>'
    )


def _render_text(panel: UIPanel) -> str:
    """Plain text rendering."""
    label = html.escape(panel.label)
    src = html.escape(panel.data_source)
    return (
        f'<div class="visual-text">'
        f'<p>{label}</p>'
        f'<p class="data-source">{src}</p>'
        f'</div>'
    )


def _render_dashboard_visual(panel: UIPanel) -> str:
    """Dashboard summary card with key metrics."""
    parts = [f'<div class="visual-dashboard">']
    if panel.evidence:
        for k, v in list(panel.evidence.items())[:6]:
            ek = html.escape(str(k))
            ev = html.escape(str(v))
            parts.append(
                f'<div class="metric"><span class="metric-key">{ek}</span>'
                f'<span class="metric-val">{ev}</span></div>'
            )
    parts.append("</div>")
    return "\n".join(parts)


_VISUAL_RENDERERS = {
    "heatmap": _render_heatmap,
    "tree": _render_tree,
    "timeline": _render_timeline,
    "bar": _render_bar,
    "text": _render_text,
    "highlight": _render_highlight,
    "dashboard": _render_dashboard_visual,
}


def _render_visual(panel: UIPanel) -> str:
    """Dispatch to the appropriate visual renderer."""
    renderer = _VISUAL_RENDERERS.get(panel.suggested_visual, _render_text)
    return renderer(panel)


# ──────────────────────────────────────────────
# 3. Panel Card
# ──────────────────────────────────────────────

def _render_panel(panel: UIPanel, index: int) -> str:
    """Render a single panel as an HTML card."""
    bg = urgency_color(panel.urgency)
    label = html.escape(panel.label)
    intent = html.escape(panel.intent)
    perception = html.escape(panel.perception)
    lang_act = html.escape(panel.language_act)

    visual_html = _render_visual(panel)
    evidence_html = _render_evidence(panel.evidence)

    return f"""<div class="panel" data-index="{index}">
  <div class="panel-header">
    <span class="urgency-badge" style="background:{bg}" title="urgency {panel.urgency:.2f}"></span>
    <span class="panel-label">{label}</span>
  </div>
  <div class="panel-tags">
    <span class="tag intent-tag">{intent}</span>
    <span class="tag perception-tag">{perception}</span>
    <span class="tag lang-tag">{lang_act}</span>
  </div>
  <div class="panel-body">
    {visual_html}
  </div>
  {evidence_html}
  <div class="panel-feedback">
    <button onclick="feedback({index},'click')">Engage</button>
    <button onclick="feedback({index},'acknowledge')">Acknowledge</button>
    <button onclick="feedback({index},'confusion')">Confused</button>
    <button onclick="feedback({index},'dismiss')">Dismiss</button>
  </div>
</div>"""


# ──────────────────────────────────────────────
# 4. Layout CSS
# ──────────────────────────────────────────────

def _layout_css(layout: str) -> str:
    """Return layout-specific CSS for the panels container."""
    if layout == "alert":
        return (
            ".panels { display:flex; flex-direction:column; gap:16px; "
            "max-width:800px; margin:0 auto; }\n"
            ".panel:first-child { border:3px solid #f44336; "
            "transform:scale(1.02); }\n"
        )
    if layout == "narrative":
        return (
            ".panels { display:flex; flex-direction:column; gap:16px; "
            "max-width:700px; margin:0 auto; }\n"
        )
    # dashboard (default)
    return (
        ".panels { display:grid; "
        "grid-template-columns:repeat(auto-fill,minmax(340px,1fr)); "
        "gap:16px; }\n"
    )


# ──────────────────────────────────────────────
# 5. Full HTML Assembly
# ──────────────────────────────────────────────

_CSS = """
* { box-sizing:border-box; margin:0; padding:0; }
body { font-family:'Segoe UI',system-ui,sans-serif; background:#f5f5f5;
       color:#222; padding:24px; }
h1 { font-size:1.4rem; margin-bottom:4px; }
.meta { color:#666; font-size:0.85rem; margin-bottom:20px; }
.panel { background:#fff; border-radius:8px; padding:16px;
         box-shadow:0 1px 3px rgba(0,0,0,0.12); }
.panel-header { display:flex; align-items:center; gap:8px;
                margin-bottom:8px; }
.urgency-badge { width:12px; height:12px; border-radius:50%;
                 display:inline-block; flex-shrink:0; }
.panel-label { font-weight:600; font-size:1rem; }
.panel-tags { display:flex; gap:6px; margin-bottom:10px; flex-wrap:wrap; }
.tag { font-size:0.75rem; padding:2px 8px; border-radius:10px;
       background:#e0e0e0; color:#333; }
.intent-tag { background:#e3f2fd; color:#1565c0; }
.perception-tag { background:#fce4ec; color:#c62828; }
.lang-tag { background:#f3e5f5; color:#6a1b9a; }
.panel-body { margin-bottom:10px; }
.panel-feedback { display:flex; gap:6px; margin-top:8px; }
.panel-feedback button { font-size:0.8rem; padding:4px 10px;
  border:1px solid #ccc; border-radius:4px; background:#fafafa;
  cursor:pointer; }
.panel-feedback button:hover { background:#e0e0e0; }
.evidence summary { font-size:0.8rem; color:#666; cursor:pointer;
                    margin-top:6px; }
.evidence pre { font-size:0.75rem; background:#f9f9f9; padding:8px;
                border-radius:4px; overflow-x:auto; margin-top:4px; }
.visual-tree { list-style:none; padding-left:16px; }
.visual-tree li { margin:2px 0; font-size:0.9rem; }
.visual-timeline { padding-left:8px; }
.timeline-entry { margin:4px 0; font-size:0.9rem; }
.timeline-dot { color:#1976d2; }
.visual-bar { display:flex; align-items:center; gap:8px; }
.visual-bar span { font-size:0.85rem; color:#666; }
.visual-dashboard { display:flex; flex-wrap:wrap; gap:8px; }
.metric { background:#f5f5f5; padding:6px 10px; border-radius:4px;
          font-size:0.85rem; }
.metric-key { color:#666; margin-right:4px; }
.metric-val { font-weight:600; }
.data-source { font-size:0.8rem; color:#888; font-style:italic; }
.feedback-section { margin-top:24px; padding:16px; background:#fff;
  border-radius:8px; box-shadow:0 1px 3px rgba(0,0,0,0.12); }
.feedback-section h2 { font-size:1.1rem; margin-bottom:8px; }
.feedback-section textarea { width:100%; height:80px; font-family:monospace;
  font-size:0.8rem; border:1px solid #ccc; border-radius:4px; padding:8px; }
"""

_JS = """
var feedbackLog = [];
function feedback(panelIndex, action) {
  feedbackLog.push({panel: panelIndex, action: action});
  var btn = event.target;
  btn.style.background = '#c8e6c9';
  btn.textContent += ' ✓';
  btn.disabled = true;
  document.getElementById('feedback-json').value =
    JSON.stringify(feedbackLog, null, 2);
}
"""


def render_html(spec: UISpec, *, title: str = "E₀ Communication") -> str:
    """Render a UISpec as a self-contained HTML string.

    Args:
        spec: The UISpec to render.
        title: HTML page title.

    Returns:
        Complete HTML document as a string.
    """
    esc_title = html.escape(title)
    esc_context = html.escape(spec.context) if spec.context else ""
    esc_time = html.escape(spec.generated_at)
    layout = spec.layout or "dashboard"

    panels_html = "\n".join(
        _render_panel(p, i) for i, p in enumerate(spec.panels)
    )

    layout_extra = _layout_css(layout)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc_title}</title>
<style>
{_CSS}
{layout_extra}
</style>
</head>
<body>
<h1>{esc_title}</h1>
<div class="meta">
  Layout: {html.escape(layout)} · Panels: {spec.panel_count} ·
  Max urgency: {spec.max_urgency:.2f} · {esc_time}
  {f'<br>{esc_context}' if esc_context else ''}
</div>
<div class="panels">
{panels_html}
</div>
<div class="feedback-section">
  <h2>Feedback</h2>
  <p style="font-size:0.85rem;color:#666;margin-bottom:8px">
    Click the buttons on each panel. Copy the JSON below to feed back into E0.
  </p>
  <textarea id="feedback-json" readonly>[]</textarea>
</div>
<script>
{_JS}
</script>
</body>
</html>"""


def render_to_file(
    spec: UISpec,
    path: str | pathlib.Path,
    *,
    title: str = "E₀ Communication",
) -> pathlib.Path:
    """Render a UISpec to an HTML file on disk.

    Args:
        spec: The UISpec to render.
        path: File path for the output HTML.
        title: HTML page title.

    Returns:
        The resolved Path of the written file.
    """
    p = pathlib.Path(path)
    p.write_text(render_html(spec, title=title), encoding="utf-8")
    return p.resolve()


def render_and_open(
    spec: UISpec,
    path: str | pathlib.Path = "e0_communication.html",
    *,
    title: str = "E₀ Communication",
) -> pathlib.Path:
    """Render a UISpec to HTML and open it in the default browser.

    Args:
        spec: The UISpec to render.
        path: File path for the output HTML.
        title: HTML page title.

    Returns:
        The resolved Path of the written file.
    """
    resolved = render_to_file(spec, path, title=title)
    webbrowser.open(resolved.as_uri())
    return resolved
