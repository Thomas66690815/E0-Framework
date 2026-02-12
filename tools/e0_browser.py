#!/usr/bin/env python3
"""
E₀ Browser Chat — Structural Communication in the Browser
===========================================================
Single-file web server.  Zero external dependencies beyond Python stdlib.
Reuses the same three backends as e0_chat.py.

Usage:
  py e0_browser.py                    → simulation, opens http://localhost:3000
  py e0_browser.py --local            → GPT-2 on CPU
  py e0_browser.py --api KEY          → OpenAI-compatible API
  py e0_browser.py --port 8080        → custom port
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import List, Optional
from urllib.parse import parse_qs

# ─── ensure repo root is on path ───
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from e0_middleware.instrumentation import E0Instrumenter, StepMeasurement


# ═══════════════════════════════════════════════
#  Metric Extraction (JSON-serialisable)
# ═══════════════════════════════════════════════

def extract_metrics(steps: List[StepMeasurement]) -> dict:
    """Extract E₀ metrics as a plain dict for JSON."""
    if not steps:
        return {"r_mean": 0, "h_mean": 0, "phases": 0, "v_median": 0, "tau": 0, "trace": []}

    resistances = [s.selected.resistance for s in steps]
    entropies = [s.entropy for s in steps]
    r_mean = sum(resistances) / len(resistances)
    h_mean = sum(entropies) / len(entropies)

    velocities = sorted(s.selected.rate for s in steps if s.selected.rate < 1e6)
    v_median = velocities[len(velocities) // 2] if velocities else 0.0

    deltas = [abs(s.delta_entropy) for s in steps]
    phases = 0
    phase_taus = []
    if len(deltas) >= 3:
        d_mean = sum(deltas) / len(deltas)
        d_std = (sum((d - d_mean) ** 2 for d in deltas) / len(deltas)) ** 0.5
        threshold = d_mean + d_std
        if d_std > 1e-10:
            phases = sum(1 for d in deltas if d > threshold)
            phase_taus = [s.tau for s, d in zip(steps, deltas) if d > threshold]

    # Token trace
    trace = []
    for s in steps:
        raw = s.selected.token.replace('\n', '↵').replace('\r', '').replace('\t', '→')
        tok = ''.join(c if (c.isprintable() and c != '\ufffd') or c in ('↵', '→') else '·' for c in raw)
        v = s.selected.rate
        trace.append({
            "tau": s.tau,
            "token": tok[:20],
            "r": round(s.selected.resistance, 4),
            "v": round(min(v, 99999), 4),
            "h": round(s.entropy, 4),
            "dh": round(s.delta_entropy, 4),
            "phase": s.tau in phase_taus,
        })

    return {
        "r_mean": round(r_mean, 4),
        "h_mean": round(h_mean, 4),
        "phases": phases,
        "v_median": round(v_median, 4),
        "tau": len(steps),
        "trace": trace,
    }


# ═══════════════════════════════════════════════
#  Backends (imported from e0_chat.py)
# ═══════════════════════════════════════════════

class SimulationBackend:
    def __init__(self):
        from e0_middleware.api_wrapper import E0ChatClient
        self.client = E0ChatClient(e0_prime=True)
        self.name = "E₀ Simulation"

    def respond(self, message):
        resp = self.client.chat(message)
        return resp.text, resp.steps

    def reset(self):
        from e0_middleware.api_wrapper import E0ChatClient
        self.client = E0ChatClient(e0_prime=True)

    def session_report(self):
        return self.client.session_report()


class LocalModelBackend:
    def __init__(self, model_name="gpt2", device="cpu"):
        from e0_middleware.local_model import E0LocalModel
        self.model = E0LocalModel(model_name, device=device, verbose=False)
        self.name = f"E₀ Local ({model_name})"
        self.history = []
        self.all_steps = []
        self.turn_count = 0

    def respond(self, message):
        self.history.append(f"Human: {message}")
        prompt = "\n".join(self.history[-4:]) + "\nAssistant:"
        result = self.model.generate(prompt, max_tokens=40, temperature=0.8)
        text = result.generated_text.strip()
        if "Human:" in text:
            text = text[:text.index("Human:")].strip()
        self.history.append(f"Assistant: {text}")
        self.all_steps.extend(result.steps)
        self.turn_count += 1
        return text, result.steps

    def reset(self):
        self.history.clear()
        self.all_steps.clear()
        self.turn_count = 0
        self.model.instrumenter = E0Instrumenter()

    def session_report(self):
        lines = [f"Model: {self.model.model_name}", f"Turns: {self.turn_count}",
                 f"Total τ: {len(self.all_steps)}"]
        if self.all_steps:
            r = sum(s.selected.resistance for s in self.all_steps) / len(self.all_steps)
            h = sum(s.entropy for s in self.all_steps) / len(self.all_steps)
            lines += [f"Mean R̄: {r:.4f}", f"Mean H̄: {h:.4f}"]
        lines.append("")
        lines.append(self.model.instrumenter.report())
        return "\n".join(lines)


class APIBackend:
    def __init__(self, api_key, model="gpt-4", base_url=None):
        from e0_middleware.api_wrapper import E0ChatClient
        self.client = E0ChatClient(api_key=api_key, model=model,
                                   base_url=base_url, e0_prime=True, logprobs=True)
        self.name = f"E₀ API ({model})"

    def respond(self, message):
        resp = self.client.chat(message)
        return resp.text, resp.steps

    def reset(self):
        from e0_middleware.api_wrapper import E0ChatClient
        self.client = E0ChatClient(api_key=self.client.api_key, model=self.client.model,
                                   base_url=self.client.base_url, e0_prime=True, logprobs=True)

    def session_report(self):
        return self.client.session_report()


# ═══════════════════════════════════════════════
#  HTTP Handler
# ═══════════════════════════════════════════════

# Global backend — set in main()
_backend = None
_lock = threading.Lock()


class E0Handler(BaseHTTPRequestHandler):
    """Minimal HTTP handler: serves HTML + JSON API."""

    def log_message(self, format, *args):
        """Suppress default request logging."""
        pass

    def _json_response(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html_response(self, html):
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self._html_response(HTML_PAGE)
        else:
            self.send_error(404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = {}

        if self.path == "/chat":
            self._handle_chat(body)
        elif self.path == "/clear":
            self._handle_clear()
        elif self.path == "/report":
            self._handle_report()
        else:
            self.send_error(404)

    def _handle_chat(self, body):
        message = body.get("message", "").strip()
        if not message:
            self._json_response({"error": "empty message"}, 400)
            return
        with _lock:
            try:
                text, steps = _backend.respond(message)
                metrics = extract_metrics(steps)
                self._json_response({"text": text, "metrics": metrics, "backend": _backend.name})
            except Exception as e:
                self._json_response({"error": str(e)}, 500)

    def _handle_clear(self):
        with _lock:
            _backend.reset()
        self._json_response({"status": "reset"})

    def _handle_report(self):
        with _lock:
            report = _backend.session_report()
        self._json_response({"report": report})


# ═══════════════════════════════════════════════
#  Embedded HTML/CSS/JS
# ═══════════════════════════════════════════════

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>E₀ Chat</title>
<style>
:root {
  --bg:       #0a0a0f;
  --surface:  #12121a;
  --border:   #1e1e2e;
  --text:     #c8c8d8;
  --dim:      #6a6a7a;
  --accent:   #7aa2f7;
  --human:    #9ece6a;
  --phase:    #f7768e;
  --metric:   #bb9af7;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  background: var(--bg);
  color: var(--text);
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 14px;
  line-height: 1.6;
  display: flex;
  flex-direction: column;
  height: 100vh;
}

/* ── Header ── */
header {
  padding: 16px 24px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}

header h1 {
  font-size: 16px;
  font-weight: 400;
  color: var(--accent);
  letter-spacing: 2px;
}

header .backend {
  font-size: 12px;
  color: var(--dim);
}

header .actions button {
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--dim);
  padding: 4px 12px;
  margin-left: 8px;
  cursor: pointer;
  font-family: inherit;
  font-size: 12px;
  border-radius: 3px;
  transition: color 0.2s, border-color 0.2s;
}

header .actions button:hover {
  color: var(--accent);
  border-color: var(--accent);
}

/* ── Chat area ── */
#chat {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.msg { max-width: 720px; width: 100%; }

.msg.human .role { color: var(--human); }
.msg.e0 .role    { color: var(--accent); }

.role {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1.5px;
  margin-bottom: 4px;
}

.msg .body {
  padding: 12px 16px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 4px;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.msg.human .body {
  border-left: 2px solid var(--human);
}

.msg.e0 .body {
  border-left: 2px solid var(--accent);
}

/* ── Metrics bar ── */
.metrics {
  margin-top: 6px;
  padding: 6px 12px;
  font-size: 12px;
  color: var(--metric);
  background: rgba(187, 154, 247, 0.05);
  border-radius: 3px;
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  align-items: center;
}

.metrics .m-label {
  color: var(--dim);
  font-size: 11px;
}

.metrics .m-val {
  color: var(--metric);
  font-weight: 500;
}

/* ── Detail trace ── */
.trace-toggle {
  font-size: 11px;
  color: var(--dim);
  cursor: pointer;
  margin-top: 4px;
  user-select: none;
}
.trace-toggle:hover { color: var(--accent); }

.trace {
  margin-top: 6px;
  font-size: 11px;
  overflow-x: auto;
  display: none;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 3px;
  padding: 8px 12px;
}

.trace.open { display: block; }

.trace table {
  border-collapse: collapse;
  width: 100%;
}

.trace th {
  text-align: left;
  color: var(--dim);
  font-weight: 400;
  padding: 2px 8px;
  border-bottom: 1px solid var(--border);
}

.trace td {
  padding: 2px 8px;
  color: var(--text);
  font-variant-numeric: tabular-nums;
}

.trace td.phase {
  color: var(--phase);
}

/* ── Input area ── */
#input-area {
  padding: 16px 24px;
  border-top: 1px solid var(--border);
  display: flex;
  gap: 12px;
  flex-shrink: 0;
}

#input-area input {
  flex: 1;
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 10px 16px;
  font-family: inherit;
  font-size: 14px;
  border-radius: 4px;
  outline: none;
  transition: border-color 0.2s;
}

#input-area input:focus {
  border-color: var(--accent);
}

#input-area input::placeholder {
  color: var(--dim);
}

#input-area button {
  background: var(--accent);
  border: none;
  color: var(--bg);
  padding: 10px 24px;
  font-family: inherit;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  border-radius: 4px;
  transition: opacity 0.2s;
}

#input-area button:hover { opacity: 0.85; }
#input-area button:disabled { opacity: 0.4; cursor: default; }

/* ── Report overlay ── */
#report-overlay {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.7);
  z-index: 100;
  justify-content: center;
  align-items: center;
}

#report-overlay.open {
  display: flex;
}

#report-box {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 24px;
  max-width: 600px;
  max-height: 70vh;
  overflow-y: auto;
  white-space: pre-wrap;
  font-size: 13px;
  color: var(--text);
}

#report-box .close {
  float: right;
  color: var(--dim);
  cursor: pointer;
  font-size: 18px;
}
#report-box .close:hover { color: var(--phase); }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

/* ── Waiting indicator ── */
.waiting .body::after {
  content: '▍';
  animation: blink 1s infinite;
  color: var(--accent);
}
@keyframes blink { 50% { opacity: 0; } }
</style>
</head>
<body>

<header>
  <h1>E₀&ensp;C H A T</h1>
  <span class="backend" id="backend-label"></span>
  <div class="actions">
    <button onclick="doReport()">Session Report</button>
    <button onclick="doClear()">Reset</button>
  </div>
</header>

<div id="chat"></div>

<div id="input-area">
  <input type="text" id="msg" placeholder="Write something…" autocomplete="off"
         onkeydown="if(event.key==='Enter')doSend()">
  <button id="send-btn" onclick="doSend()">Send</button>
</div>

<div id="report-overlay">
  <div id="report-box">
    <span class="close" onclick="closeReport()">&times;</span>
    <pre id="report-content"></pre>
  </div>
</div>

<script>
const chat = document.getElementById('chat');
const msgInput = document.getElementById('msg');
const sendBtn = document.getElementById('send-btn');
let sending = false;

function scrollDown() {
  chat.scrollTop = chat.scrollHeight;
}

function addHuman(text) {
  const div = document.createElement('div');
  div.className = 'msg human';
  div.innerHTML = `<div class="role">You</div><div class="body">${esc(text)}</div>`;
  chat.appendChild(div);
  scrollDown();
}

function addE0(text, metrics, id) {
  const div = document.createElement('div');
  div.className = 'msg e0';
  div.id = id;

  let metricsHtml = '';
  if (metrics && metrics.tau > 0) {
    metricsHtml = `
      <div class="metrics">
        <span><span class="m-label">R̄</span> <span class="m-val">${metrics.r_mean.toFixed(3)}</span></span>
        <span><span class="m-label">H̄</span> <span class="m-val">${metrics.h_mean.toFixed(3)}</span></span>
        <span><span class="m-label">Φ</span> <span class="m-val">${metrics.phases}</span></span>
        <span><span class="m-label">v̄</span> <span class="m-val">${metrics.v_median.toFixed(3)}</span></span>
        <span><span class="m-label">τ</span> <span class="m-val">${metrics.tau}</span></span>
      </div>`;

    if (metrics.trace && metrics.trace.length > 0) {
      metricsHtml += `<div class="trace-toggle" onclick="toggleTrace('${id}')">▸ token trace</div>`;
      metricsHtml += buildTrace(metrics.trace, id);
    }
  }

  div.innerHTML = `<div class="role">E₀</div><div class="body">${esc(text)}</div>${metricsHtml}`;
  chat.appendChild(div);
  scrollDown();
}

function addWaiting() {
  const div = document.createElement('div');
  div.className = 'msg e0 waiting';
  div.id = 'waiting';
  div.innerHTML = `<div class="role">E₀</div><div class="body"></div>`;
  chat.appendChild(div);
  scrollDown();
}

function removeWaiting() {
  const el = document.getElementById('waiting');
  if (el) el.remove();
}

function buildTrace(trace, id) {
  let rows = trace.map(t => {
    const cls = t.phase ? ' class="phase"' : '';
    const vStr = t.v > 99999 ? '∞' : t.v < 100 ? t.v.toFixed(4) : Math.round(t.v);
    const marker = t.phase ? ' ◆' : '';
    return `<tr${cls ? ' style="color:var(--phase)"' : ''}>
      <td>${t.tau}</td><td>${esc(t.token)}</td>
      <td>${t.r.toFixed(4)}</td><td>${vStr}</td>
      <td>${t.h.toFixed(4)}</td><td>${t.dh >= 0 ? '+' : ''}${t.dh.toFixed(4)}${marker}</td>
    </tr>`;
  }).join('');

  return `<div class="trace" id="trace-${id}">
    <table>
      <tr><th>τ</th><th>Token</th><th>R</th><th>v</th><th>H</th><th>ΔH</th></tr>
      ${rows}
    </table>
  </div>`;
}

function toggleTrace(id) {
  const el = document.getElementById('trace-' + id);
  if (el) el.classList.toggle('open');
}

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

let msgCounter = 0;

async function doSend() {
  if (sending) return;
  const text = msgInput.value.trim();
  if (!text) return;

  msgInput.value = '';
  addHuman(text);

  sending = true;
  sendBtn.disabled = true;
  addWaiting();

  try {
    const res = await fetch('/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: text}),
    });
    const data = await res.json();
    removeWaiting();

    if (data.error) {
      addE0('[Error] ' + data.error, null, 'msg-' + (++msgCounter));
    } else {
      if (!document.getElementById('backend-label').textContent) {
        document.getElementById('backend-label').textContent = data.backend || '';
      }
      addE0(data.text, data.metrics, 'msg-' + (++msgCounter));
    }
  } catch (e) {
    removeWaiting();
    addE0('[Connection error] ' + e.message, null, 'msg-' + (++msgCounter));
  }

  sending = false;
  sendBtn.disabled = false;
  msgInput.focus();
}

async function doClear() {
  await fetch('/clear', {method: 'POST'});
  chat.innerHTML = '';
  document.getElementById('backend-label').textContent = '';
}

async function doReport() {
  const res = await fetch('/report', {method: 'POST'});
  const data = await res.json();
  document.getElementById('report-content').textContent = data.report || 'No data.';
  document.getElementById('report-overlay').classList.add('open');
}

function closeReport() {
  document.getElementById('report-overlay').classList.remove('open');
}

document.getElementById('report-overlay').addEventListener('click', function(e) {
  if (e.target === this) closeReport();
});

msgInput.focus();
</script>
</body>
</html>
"""


# ═══════════════════════════════════════════════
#  Entry Point
# ═══════════════════════════════════════════════

def main():
    global _backend

    parser = argparse.ArgumentParser(
        description="E₀ Browser Chat — structural communication in the browser",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  py e0_browser.py                        Simulation mode
  py e0_browser.py --local                GPT-2 on CPU
  py e0_browser.py --local --model gpt2   Specific model
  py e0_browser.py --api sk-... --model gpt-4
  py e0_browser.py --port 8080            Custom port
        """,
    )
    parser.add_argument("--local", action="store_true",
                        help="Use a local HuggingFace model (default: gpt2)")
    parser.add_argument("--model", type=str, default=None,
                        help="Model name (HuggingFace ID or API model name)")
    parser.add_argument("--api", type=str, default=None, metavar="KEY",
                        help="OpenAI-compatible API key")
    parser.add_argument("--base-url", type=str, default=None,
                        help="API base URL (for non-OpenAI providers)")
    parser.add_argument("--device", type=str, default="cpu",
                        help="Device for local model (default: cpu)")
    parser.add_argument("--port", type=int, default=3000,
                        help="Server port (default: 3000)")

    args = parser.parse_args()

    # ── Select backend ──
    if args.local:
        model_name = args.model or "gpt2"
        print(f"  [E₀] Loading local model: {model_name} ...")
        _backend = LocalModelBackend(model_name, device=args.device)
    elif args.api:
        model_name = args.model or "gpt-4"
        _backend = APIBackend(args.api, model=model_name, base_url=args.base_url)
    else:
        _backend = SimulationBackend()

    # ── Start server ──
    server = HTTPServer(("0.0.0.0", args.port), E0Handler)
    url = f"http://localhost:{args.port}"

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  E₀  B R O W S E R  C H A T                            ║")
    print("║                                                          ║")
    print(f"║  {url:<56s} ║")
    print(f"║  Backend: {_backend.name:<46s} ║")
    print("║                                                          ║")
    print("║  Ctrl+C to stop                                         ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  [E₀] Server stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
