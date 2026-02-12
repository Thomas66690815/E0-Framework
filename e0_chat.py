#!/usr/bin/env python3
"""
E₀ Terminal Chat — Human‑Synthetic Communication Interface
============================================================
Minimal interactive REPL where every exchange carries its
E₀ structural signature.  Both sides see the same physics.

Three modes:
  py e0_chat.py                  → simulation (zero dependencies)
  py e0_chat.py --local          → GPT-2 on your machine (real R)
  py e0_chat.py --api KEY        → OpenAI-compatible API

Commands inside the chat:
  /quit      – end session
  /report    – full E₀ session report
  /clear     – reset conversation
  /detail    – toggle token-level trace
  /help      – show commands

Every response is annotated with:
  R̄  = mean resistance          (how hard each token was to reach)
  H̄  = mean entropy             (landscape stability)
  Φ  = phase transitions        (structural reconfigurations)
  v̄  = mean transition velocity (Δ/R)
"""

from __future__ import annotations

import argparse
import math
import sys
import os
from typing import List, Optional

# ─── ensure repo root is on path ───
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from e0_middleware.instrumentation import E0Instrumenter, StepMeasurement


# ═══════════════════════════════════════════════
#  E₀ Metric Formatting
# ═══════════════════════════════════════════════

def compact_signature(steps: List[StepMeasurement], label: str = "") -> str:
    """One-line E₀ signature for a generation."""
    if not steps:
        return f"  ┊ E₀  (no measurements)"

    resistances = [s.selected.resistance for s in steps]
    entropies   = [s.entropy for s in steps]
    r_mean = sum(resistances) / len(resistances)
    h_mean = sum(entropies) / len(entropies)

    # Use median velocity — mean is dominated by near-zero-R tokens
    velocities = sorted(s.selected.rate for s in steps if s.selected.rate < 1e6)
    v_mean = velocities[len(velocities) // 2] if velocities else 0.0

    # Phase transitions: |ΔH| > mean + 1σ
    deltas = [abs(s.delta_entropy) for s in steps]
    if len(deltas) >= 3:
        d_mean = sum(deltas) / len(deltas)
        d_std  = (sum((d - d_mean) ** 2 for d in deltas) / len(deltas)) ** 0.5
        threshold = d_mean + d_std
        phases = sum(1 for d in deltas if d > threshold and d_std > 1e-10)
    else:
        phases = 0

    tag = f" {label}" if label else ""
    return (
        f"  ┊ E₀{tag}  "
        f"R̄={r_mean:.3f}  H̄={h_mean:.3f}  "
        f"Φ={phases}  v̄={v_mean:.3f}  "
        f"τ={len(steps)}"
    )


def detailed_trace(steps: List[StepMeasurement]) -> str:
    """Token-by-token E₀ trace."""
    if not steps:
        return ""
    lines = [
        "  ┊ τ  │ Token              │ R        │ v        │ H        │ ΔH",
        "  ┊────┼────────────────────┼──────────┼──────────┼──────────┼──────────",
    ]
    # Phase detection
    deltas = [abs(s.delta_entropy) for s in steps]
    d_mean = sum(deltas) / len(deltas) if deltas else 0
    d_std  = (sum((d - d_mean) ** 2 for d in deltas) / len(deltas)) ** 0.5 if len(deltas) >= 3 else 0
    threshold = d_mean + d_std if d_std > 1e-10 else float('inf')

    for s in steps:
        raw_tok = s.selected.token.replace('\n', '↵').replace('\r', '').replace('\t', '→')
        # Replace non-printable / garbled bytes with dot
        tok = ''.join(c if (c.isprintable() and c != '\ufffd') or c in ('↵', '→') else '·' for c in raw_tok)
        tok = tok[:18].ljust(18)
        r = s.selected.resistance
        v = s.selected.rate
        v_str = f"{v:.4f}" if v < 100 else ("∞" if v > 1e6 else f"{v:.0f}")
        phase = " ◆" if abs(s.delta_entropy) > threshold else ""
        lines.append(
            f"  ┊ {s.tau:2d} │ {tok} │ {r:8.4f} │ {v_str:>8s} │ "
            f"{s.entropy:8.4f} │ {s.delta_entropy:+.4f}{phase}"
        )
    return "\n".join(lines)


# ═══════════════════════════════════════════════
#  Chat Backends
# ═══════════════════════════════════════════════

class SimulationBackend:
    """Chat via E0ChatClient in simulation mode (no external deps)."""

    def __init__(self):
        from e0_middleware.api_wrapper import E0ChatClient
        self.client = E0ChatClient(e0_prime=True)
        self.name = "E₀ Simulation"

    def respond(self, message: str):
        resp = self.client.chat(message)
        return resp.text, resp.steps

    def reset(self):
        from e0_middleware.api_wrapper import E0ChatClient
        self.client = E0ChatClient(e0_prime=True)

    def session_report(self) -> str:
        return self.client.session_report()


class LocalModelBackend:
    """Chat via E0LocalModel — real measurements from a real model."""

    def __init__(self, model_name: str = "gpt2", device: str = "cpu"):
        from e0_middleware.local_model import E0LocalModel
        self.model = E0LocalModel(model_name, device=device, verbose=False)
        self.name = f"E₀ Local ({model_name})"
        self.history: List[str] = []
        self.all_steps: List[StepMeasurement] = []
        self.turn_count = 0

    def respond(self, message: str):
        # Build conversational prompt
        self.history.append(f"Human: {message}")
        prompt = "\n".join(self.history[-4:])  # keep last 2 exchanges
        prompt += "\nAssistant:"

        result = self.model.generate(
            prompt,
            max_tokens=40,
            temperature=0.8,
        )

        # Extract just the assistant part
        text = result.generated_text.strip()
        # Cut at next "Human:" if model keeps going
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

    def session_report(self) -> str:
        lines = [
            "═══ E₀ Session Report ═══",
            f"  Model:     {self.model.model_name}",
            f"  Turns:     {self.turn_count}",
            f"  Total τ:   {len(self.all_steps)}",
        ]
        if self.all_steps:
            r_mean = sum(s.selected.resistance for s in self.all_steps) / len(self.all_steps)
            h_mean = sum(s.entropy for s in self.all_steps) / len(self.all_steps)
            lines.append(f"  Mean R̄:    {r_mean:.4f}")
            lines.append(f"  Mean H̄:    {h_mean:.4f}")
        lines.append("")
        lines.append(self.model.instrumenter.report())
        return "\n".join(lines)


class APIBackend:
    """Chat via E0ChatClient with a real API."""

    def __init__(self, api_key: str, model: str = "gpt-4", base_url: Optional[str] = None):
        from e0_middleware.api_wrapper import E0ChatClient
        self.client = E0ChatClient(
            api_key=api_key,
            model=model,
            base_url=base_url,
            e0_prime=True,
            logprobs=True,
        )
        self.name = f"E₀ API ({model})"

    def respond(self, message: str):
        resp = self.client.chat(message)
        return resp.text, resp.steps

    def reset(self):
        from e0_middleware.api_wrapper import E0ChatClient
        self.client = E0ChatClient(
            api_key=self.client.api_key,
            model=self.client.model,
            base_url=self.client.base_url,
            e0_prime=True,
            logprobs=True,
        )

    def session_report(self) -> str:
        return self.client.session_report()


# ═══════════════════════════════════════════════
#  The REPL
# ═══════════════════════════════════════════════

BANNER = """
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   E₀  T E R M I N A L  C H A T                              ║
║                                                              ║
║   Every exchange carries its structural signature.           ║
║   R̄ = resistance · H̄ = entropy · Φ = phase transitions      ║
║                                                              ║
║   /help for commands · /quit to exit                         ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""

HELP_TEXT = """
  Commands:
    /quit      End session
    /report    Full E₀ session report
    /clear     Reset conversation (fresh τ=0)
    /detail    Toggle token-level trace after each response
    /help      This message

  The E₀ annotation under each response:
    R̄  = mean resistance      — how hard each token was to reach
    H̄  = mean entropy         — stability of the token landscape
    Φ  = phase transitions    — sudden structural reconfigurations
    v̄  = mean velocity (Δ/R)  — structural enforcement strength
    τ  = token count          — historization depth of this turn
"""


def run_chat(backend, show_detail: bool = False):
    """Main REPL loop."""
    print(BANNER)
    print(f"  Backend: {backend.name}")
    print(f"  Detail mode: {'ON' if show_detail else 'OFF (toggle with /detail)'}")
    print()

    while True:
        try:
            user_input = input("  You ▸ ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n")
            break

        if not user_input:
            continue

        # ── Commands ──
        cmd = user_input.lower()

        if cmd == "/quit":
            print()
            print("  Session ended.")
            print(compact_signature([], "session"))
            print()
            break

        if cmd == "/help":
            print(HELP_TEXT)
            continue

        if cmd == "/report":
            print()
            print(backend.session_report())
            print()
            continue

        if cmd == "/clear":
            backend.reset()
            print("  ┊ Conversation reset. τ=0.")
            print()
            continue

        if cmd == "/detail":
            show_detail = not show_detail
            state = "ON" if show_detail else "OFF"
            print(f"  ┊ Detail trace: {state}")
            print()
            continue

        # ── Generate response ──
        try:
            text, steps = backend.respond(user_input)
        except Exception as e:
            print(f"  [E₀ error] {e}")
            print()
            continue

        # ── Display response ──
        print()
        # Clean non-printable chars from response
        clean_text = ''.join(c if (c.isprintable() or c in ('\n', ' ')) and c != '\ufffd' else '' for c in text)
        # Word-wrap at ~70 chars with indent
        words = clean_text.split()
        line = "  E₀ ▸ "
        for w in words:
            if len(line) + len(w) + 1 > 72:
                print(line)
                line = "       " + w
            else:
                line += (" " if not line.endswith(" ") else "") + w
        if line.strip():
            print(line)

        print()
        print(compact_signature(steps))

        if show_detail and steps:
            print()
            print(detailed_trace(steps))

        print()


# ═══════════════════════════════════════════════
#  Entry Point
# ═══════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="E₀ Terminal Chat — structural communication",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  py e0_chat.py                       Simulation mode (no deps)
  py e0_chat.py --local               GPT-2 on CPU
  py e0_chat.py --local --model tinyllama/tinyllama-1.1b-chat-v1.0
  py e0_chat.py --api sk-... --model gpt-4
  py e0_chat.py --detail              Start with trace enabled
        """,
    )
    parser.add_argument(
        "--local", action="store_true",
        help="Use a local HuggingFace model (default: gpt2)",
    )
    parser.add_argument(
        "--model", type=str, default=None,
        help="Model name (HuggingFace ID or API model name)",
    )
    parser.add_argument(
        "--api", type=str, default=None, metavar="KEY",
        help="OpenAI-compatible API key",
    )
    parser.add_argument(
        "--base-url", type=str, default=None,
        help="API base URL (for non-OpenAI providers)",
    )
    parser.add_argument(
        "--device", type=str, default="cpu",
        help="Device for local model (default: cpu)",
    )
    parser.add_argument(
        "--detail", action="store_true",
        help="Start with token-level trace enabled",
    )

    args = parser.parse_args()

    # ── Select backend ──
    if args.local:
        model_name = args.model or "gpt2"
        print(f"\n  [E₀] Loading local model: {model_name} ...")
        backend = LocalModelBackend(model_name, device=args.device)
    elif args.api:
        model_name = args.model or "gpt-4"
        backend = APIBackend(args.api, model=model_name, base_url=args.base_url)
    else:
        backend = SimulationBackend()

    run_chat(backend, show_detail=args.detail)


if __name__ == "__main__":
    main()
