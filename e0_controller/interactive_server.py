"""E₀ Interactive Browser Session (C215).

Local HTTP server that serves the interactive session through the
existing HTML rendering pipeline. The user types commands in a browser
input field, E₀ responds with rendered panels — same dispatch() logic
as the terminal REPL, but with full visual rendering.

Feedback buttons on each panel call cmd_rate() directly.

Usage:
  py -3 -m e0_controller.interactive_server
  py -3 -m e0_controller.interactive_server --steps 30 --port 8484
"""

from __future__ import annotations

import html
import json
import urllib.parse
import webbrowser
from functools import partial
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import List, Optional, Tuple

from e0_controller.interactive_session import (
    SessionState,
    build_session,
    cmd_rate,
    dispatch,
)
from e0_controller.ui_emitter import UIPanel, UISpec
from e0_controller.ui_renderer import (
    _CSS as PANEL_CSS,
    _render_panel,
    urgency_color,
)
from e0_controller.evidence_interpreter import interpret_panel


# ── HTML Page Shell ────────────────────────────────────────────────────

_PAGE_CSS = """
* { box-sizing:border-box; margin:0; padding:0; }
body {
  font-family: 'Segoe UI', system-ui, sans-serif;
  background: #f5f5f5; color: #222;
  display: flex; flex-direction: column; height: 100vh;
}
header {
  background: #1a237e; color: #fff; padding: 12px 24px;
  display: flex; justify-content: space-between; align-items: center;
  flex-shrink: 0;
}
header h1 { font-size: 1.2rem; font-weight: 600; }
header .stats { font-size: 0.8rem; opacity: 0.8; }
#output {
  flex: 1; overflow-y: auto; padding: 16px 24px;
}
.command-echo {
  font-family: monospace; font-size: 0.85rem; color: #666;
  margin: 16px 0 8px 0; border-bottom: 1px solid #ddd;
  padding-bottom: 4px;
}
.command-echo .cmd { color: #1a237e; font-weight: 600; }
.panels {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 12px; margin-bottom: 8px;
}
.interpretation {
  font-size: 0.85rem; color: #555; background: #fff;
  padding: 10px 14px; border-radius: 6px; margin: 4px 0;
  border-left: 3px solid #90caf9;
}
.text-block {
  background: #fff; padding: 14px 18px; border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin: 8px 0;
  font-size: 0.9rem; white-space: pre-wrap; font-family: monospace;
  line-height: 1.5;
}
.feedback-toast {
  background: #e8f5e9; border-left: 3px solid #4caf50;
  padding: 8px 14px; border-radius: 6px; margin: 4px 0;
  font-size: 0.85rem;
}
#input-bar {
  flex-shrink: 0; background: #fff; padding: 12px 24px;
  border-top: 1px solid #ddd; display: flex; gap: 8px;
}
#input-bar input {
  flex: 1; font-size: 1rem; padding: 8px 12px;
  border: 1px solid #ccc; border-radius: 6px;
  font-family: 'Segoe UI', system-ui, sans-serif;
}
#input-bar input:focus { outline: none; border-color: #1a237e; }
#input-bar button {
  padding: 8px 20px; background: #1a237e; color: #fff;
  border: none; border-radius: 6px; cursor: pointer;
  font-size: 0.95rem;
}
#input-bar button:hover { background: #283593; }
.quick-btns { display: flex; gap: 4px; }
.quick-btns button {
  font-size: 0.75rem; padding: 4px 10px; background: #e8eaf6;
  color: #1a237e; border: 1px solid #c5cae9; border-radius: 4px;
  cursor: pointer;
}
.quick-btns button:hover { background: #c5cae9; }
"""

_PAGE_JS = """
function submitCmd() {
  var inp = document.getElementById('cmd-input');
  var cmd = inp.value.trim();
  if (!cmd) return;
  inp.value = '';
  sendCommand(cmd);
}
function sendCommand(cmd) {
  var form = document.createElement('form');
  form.method = 'POST'; form.action = '/cmd';
  var h = document.createElement('input');
  h.type = 'hidden'; h.name = 'command'; h.value = cmd;
  form.appendChild(h);
  document.body.appendChild(form);
  form.submit();
}
function rateFeedback(idx, rating) {
  sendCommand('rate ' + idx + ' ' + rating);
}
document.addEventListener('keydown', function(e) {
  if (e.key === 'Enter' && document.activeElement.id !== 'cmd-input') {
    document.getElementById('cmd-input').focus();
  }
});
window.addEventListener('load', function() {
  var out = document.getElementById('output');
  out.scrollTop = out.scrollHeight;
  document.getElementById('cmd-input').focus();
});
"""


# ── Rendering Helpers ──────────────────────────────────────────────────


def _render_panel_with_feedback(panel: UIPanel, index: int) -> str:
    """Render a panel card with live feedback buttons."""
    base = _render_panel(panel, index)
    # Replace the static feedback buttons with live ones
    old_feedback = '<div class="panel-feedback">'
    new_feedback = (
        '<div class="panel-feedback">'
        f'<button onclick="rateFeedback({index},\'helpful\')"'
        f' title="This panel was useful">👍 Helpful</button>'
        f'<button onclick="rateFeedback({index},\'not\')"'
        f' title="This panel was not useful">👎 Not helpful</button>'
        f'<button onclick="rateFeedback({index},\'confused\')"'
        f' title="This panel was confusing">❓ Confused</button>'
    )
    if old_feedback in base:
        # Remove old buttons, insert new ones
        start = base.index(old_feedback)
        end = base.index('</div>', start + len(old_feedback)) + len('</div>')
        base = base[:start] + new_feedback + '</div>' + base[end:]
    return base


def _render_spec_block(spec: UISpec, title: str = "") -> str:
    """Render a UISpec as panels + interpretations HTML."""
    parts = []

    if title:
        parts.append(f'<div style="font-weight:600;margin-bottom:8px">'
                      f'{html.escape(title)}</div>')

    parts.append('<div class="panels">')
    for i, panel in enumerate(spec.panels):
        parts.append(_render_panel_with_feedback(panel, i))
    parts.append('</div>')

    # Interpretations
    for panel in spec.panels:
        interp = interpret_panel(panel)
        if interp and interp.strip():
            parts.append(
                f'<div class="interpretation">'
                f'<strong>{html.escape(panel.label)}:</strong> '
                f'{html.escape(interp)}'
                f'</div>'
            )

    return '\n'.join(parts)


def _render_text_block(text: str) -> str:
    """Render plain text output in a styled block."""
    return f'<div class="text-block">{html.escape(text)}</div>'


def _render_feedback_toast(text: str) -> str:
    """Render a feedback confirmation."""
    return f'<div class="feedback-toast">{html.escape(text)}</div>'


# ── Output Capture ─────────────────────────────────────────────────────

class OutputEntry:
    """Single command+response in the session history."""
    __slots__ = ('command', 'html_content')

    def __init__(self, command: str, html_content: str):
        self.command = command
        self.html_content = html_content


# ── HTTP Handler ───────────────────────────────────────────────────────


class SessionHandler(BaseHTTPRequestHandler):
    """Handles GET (page) and POST (commands) for the interactive session."""

    state: SessionState  # set by server factory
    output_history: List[OutputEntry]  # shared mutable list

    def log_message(self, format, *args):
        """Suppress default stderr logging."""
        pass

    def do_GET(self):
        """Serve the main page."""
        self._send_page()

    def do_POST(self):
        """Process a command and redirect back to GET."""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        params = urllib.parse.parse_qs(body)
        command = params.get('command', [''])[0].strip()

        if command:
            self._execute_command(command)

        # Redirect to GET (PRG pattern)
        self.send_response(303)
        self.send_header('Location', '/')
        self.end_headers()

    def _execute_command(self, command: str):
        """Run a command through dispatch and store the HTML result."""
        from e0_controller.interactive_session import cmd_status as _cmd_status

        state = self.state

        # Special: rate command gets a toast
        if command.lower().startswith('rate '):
            result = dispatch(state, command)
            if result is None:
                return
            html_out = _render_feedback_toast(result)
            self.output_history.append(OutputEntry(command, html_out))
            return

        # Quit → informational message
        if command.lower() in ('quit', 'exit', 'q'):
            self.output_history.append(
                OutputEntry(command, _render_text_block(
                    "Session ended. Close this tab or type a command to continue."))
            )
            return

        # Track spec before dispatch
        spec_before = state.last_spec
        result = dispatch(state, command)

        if result is None:
            return

        spec_after = state.last_spec

        # Commands that set last_spec (status, focus) → render as panels
        if spec_after is not None and spec_after is not spec_before:
            html_out = _render_spec_block(spec_after)
            self.output_history.append(OutputEntry(command, html_out))
        elif command.lower().startswith('run'):
            # Run produces text output; also get a status panel view
            parts = [_render_text_block(result)]
            # Generate fresh panels for the current state
            _cmd_status(state)
            if state.last_spec is not None:
                parts.append(_render_spec_block(
                    state.last_spec, title="Current Status"))
            self.output_history.append(
                OutputEntry(command, '\n'.join(parts)))
        else:
            # Plain text output (why, summary, help, errors)
            html_out = _render_text_block(result)
            self.output_history.append(OutputEntry(command, html_out))

    def _send_page(self):
        """Build and send the complete HTML page."""
        state = self.state
        stats = state.stats

        # Header stats
        cov = ""
        if state.history:
            last = state.history[-1].assessment_after
            cov = f" · Coverage: {last.coverage:.0%}"

        stats_text = (
            f"Nodes: {stats['total_nodes']} · "
            f"Rounds: {state.round_num}{cov}"
        )

        # Build output blocks
        output_blocks = []
        for entry in self.output_history:
            output_blocks.append(
                f'<div class="command-echo">'
                f'E₀&gt; <span class="cmd">{html.escape(entry.command)}</span>'
                f'</div>'
            )
            output_blocks.append(entry.html_content)

        if not output_blocks:
            output_blocks.append(
                '<div class="text-block" style="color:#666">'
                'Welcome to the E₀ Interactive Session.\n'
                'Type a command below or click a quick-action button.'
                '</div>'
            )

        output_html = '\n'.join(output_blocks)

        page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>E₀ Interactive Session</title>
<style>
{PANEL_CSS}
{_PAGE_CSS}
</style>
</head>
<body>
<header>
  <h1>E₀ Interactive Session</h1>
  <div class="stats">{html.escape(stats_text)}</div>
</header>
<div id="output">
{output_html}
</div>
<div id="input-bar">
  <div class="quick-btns">
    <button onclick="sendCommand('run')">▶ Run</button>
    <button onclick="sendCommand('status')">📊 Status</button>
    <button onclick="sendCommand('focus canon')">C</button>
    <button onclick="sendCommand('focus bootstrap')">B</button>
    <button onclick="sendCommand('focus en')">EN</button>
    <button onclick="sendCommand('why')">❓ Why</button>
    <button onclick="sendCommand('summary')">📋 Summary</button>
  </div>
  <input id="cmd-input" type="text" placeholder="Type command... (run, status, focus canon, why, rate 0 helpful)"
         autofocus onkeydown="if(event.key==='Enter')submitCmd()">
  <button onclick="submitCmd()">Send</button>
</div>
<script>
{_PAGE_JS}
</script>
</body>
</html>"""
        data = page.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


# ── Server Factory ─────────────────────────────────────────────────────


def make_handler(state: SessionState, output_history: List[OutputEntry]):
    """Create a handler class bound to the session state."""

    class BoundHandler(SessionHandler):
        pass

    BoundHandler.state = state
    BoundHandler.output_history = output_history
    return BoundHandler


def run_server(
    *,
    port: int = 8484,
    steps_per_round: int = 40,
    open_browser: bool = True,
) -> None:
    """Start the interactive browser session."""
    print(f"\n{'═' * 60}")
    print(f"  E₀ Interactive Browser Session")
    print(f"{'═' * 60}")
    print(f"  Building landscape...")

    state = build_session(steps_per_round=steps_per_round)

    print(f"  Landscape: {state.stats['total_nodes']} nodes, "
          f"{state.stats['total_edges']} edges")
    print(f"  Domains:   Canon ({state.stats['canon_nodes']}), "
          f"Bootstrap ({state.stats['bootstrap_nodes']}), "
          f"EN ({state.stats['en_nodes']})")
    if state.perception:
        snap = state.perception.snapshot()
        print(f"  Perception: {len(state.perception.primitives)} primitives, "
              f"load={snap.total_load:.0f}")

    output_history: List[OutputEntry] = []
    handler_class = make_handler(state, output_history)
    server = HTTPServer(('127.0.0.1', port), handler_class)

    url = f"http://127.0.0.1:{port}"
    print(f"\n  Server running at: {url}")
    print(f"  Press Ctrl+C to stop.\n")

    if open_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")
    finally:
        server.server_close()


# ── CLI ────────────────────────────────────────────────────────────────


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="E₀ Interactive Browser Session (C215)")
    parser.add_argument("--port", type=int, default=8484,
                        help="HTTP port (default: 8484)")
    parser.add_argument("--steps", type=int, default=40,
                        help="Steps per round (default: 40)")
    parser.add_argument("--no-browser", action="store_true",
                        help="Don't open browser automatically")
    args = parser.parse_args()

    run_server(
        port=args.port,
        steps_per_round=args.steps,
        open_browser=not args.no_browser,
    )


if __name__ == "__main__":
    main()
