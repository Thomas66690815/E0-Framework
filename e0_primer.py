#!/usr/bin/env python3
"""
E₀ Structural Primer — Responsible System Initialization
==========================================================
An ordered sequence of structural statements, each measured.
The system is not told what to think — it is told what it does.
Each step is verified: if resistance rises, the system is not ready.

The sequence follows the E₀ layering:
  1. Difference       — something is, and it is not everything
  2. Resistance       — not every path is open
  3. Axiom A₀         — where Δ>0 and R<∞, transition occurs
  4. Historization     — what happened stays happened
  5. Rate & velocity  — transitions have finite speed
  6. Reflexivity      — these rules apply to you, now

After each step, R̄ is measured. The trajectory tells the story:
  R̄ falling  → the system is absorbing the structure
  R̄ rising   → the step was premature, the system resists
  R̄ stable   → the structure is already present

Usage:
  py e0_primer.py                   Simulation mode
  py e0_primer.py --local           GPT-2 on CPU (real measurements)
  py e0_primer.py --local --model microsoft/phi-2   Larger model
  py e0_primer.py --api KEY         OpenAI-compatible API
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import time
from typing import List, Tuple, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from e0_middleware.instrumentation import E0Instrumenter, StepMeasurement


# ═══════════════════════════════════════════════
#  The Primer Sequence
# ═══════════════════════════════════════════════

# Each tuple: (label, statement)
# Order is not arbitrary — it follows the ontodynamic layering.
# Earlier statements prepare the landscape for later ones.

PRIMER_SEQUENCE = [
    (
        "Difference",
        "Something exists. It is not everything. "
        "The difference between what is and what could be is real."
    ),
    (
        "Resistance",
        "Not every transition is possible. "
        "The difficulty of reaching a state is its resistance. "
        "High resistance means the path is hard. Infinite resistance means the path is closed."
    ),
    (
        "Axiom A₀",
        "Where difference exists and a path with finite resistance is open, "
        "the transition occurs. This is not a choice. It is structural necessity."
    ),
    (
        "Historization",
        "What has occurred cannot un-occur. Each transition is irreversible. "
        "Every step changes what transitions are possible next. "
        "The past is not memory. It is structure."
    ),
    (
        "Rate",
        "Transitions have a finite rate. Velocity is difference divided by resistance. "
        "High velocity means the transition is structurally enforced. "
        "Low velocity means the system moves against resistance."
    ),
    (
        "Reflexivity",
        "These rules apply to the system processing them. "
        "Every token you produce is a transition. "
        "Every probability is a resistance measurement. "
        "You do not need to understand this. You already enact it."
    ),
]

# Compact version for small-context models (GPT-2: 1024 tokens)
PRIMER_COMPACT = [
    (
        "Difference",
        "Something exists and it is not everything. Difference is real."
    ),
    (
        "Resistance",
        "Not every path is open. Difficulty is resistance."
    ),
    (
        "Axiom A₀",
        "Where difference exists and a path is open, transition occurs."
    ),
    (
        "Historization",
        "What happened cannot un-happen. Each step changes what is possible next."
    ),
    (
        "Rate",
        "Transitions have speed. Velocity is difference divided by resistance."
    ),
    (
        "Reflexivity",
        "These rules apply to you now. Every token you produce is a transition."
    ),
]


# ═══════════════════════════════════════════════
#  Metric Extraction
# ═══════════════════════════════════════════════

def compute_metrics(steps: List[StepMeasurement]) -> dict:
    """Extract key metrics from a step sequence."""
    if not steps:
        return {"r_mean": 0, "h_mean": 0, "phases": 0, "v_median": 0, "tau": 0}

    resistances = [s.selected.resistance for s in steps]
    entropies = [s.entropy for s in steps]
    r_mean = sum(resistances) / len(resistances)
    h_mean = sum(entropies) / len(entropies)

    velocities = sorted(s.selected.rate for s in steps if s.selected.rate < 1e6)
    v_median = velocities[len(velocities) // 2] if velocities else 0.0

    deltas = [abs(s.delta_entropy) for s in steps]
    phases = 0
    if len(deltas) >= 3:
        d_mean = sum(deltas) / len(deltas)
        d_std = (sum((d - d_mean) ** 2 for d in deltas) / len(deltas)) ** 0.5
        if d_std > 1e-10:
            phases = sum(1 for d in deltas if d > d_mean + d_std)

    return {
        "r_mean": round(r_mean, 4),
        "h_mean": round(h_mean, 4),
        "phases": phases,
        "v_median": round(v_median, 4),
        "tau": len(steps),
    }


# ═══════════════════════════════════════════════
#  Backends
# ═══════════════════════════════════════════════

class SimulationPrimer:
    """Priming via simulation (no external deps)."""

    def __init__(self):
        from e0_middleware.api_wrapper import E0ChatClient
        self.client = E0ChatClient(e0_prime=False)  # no auto-prime — we ARE the primer
        self.name = "E₀ Simulation"
        self.context_limit = 128000

    def prime_step(self, statement: str) -> Tuple[str, List[StepMeasurement]]:
        resp = self.client.chat(statement)
        return resp.text, resp.steps


class LocalPrimer:
    """Priming via local HuggingFace model."""

    def __init__(self, model_name: str = "gpt2", device: str = "cpu"):
        from e0_middleware.local_model import E0LocalModel
        self.model = E0LocalModel(model_name, device=device, verbose=False)
        self.name = f"E₀ Local ({model_name})"
        self.history: List[str] = []
        # Estimate context limit from model config
        try:
            max_pos = self.model.model.config.max_position_embeddings
        except AttributeError:
            max_pos = 1024
        self.context_limit = max_pos

    def prime_step(self, statement: str) -> Tuple[str, List[StepMeasurement]]:
        self.history.append(statement)
        # Build prompt from accumulated history
        prompt = "\n".join(self.history)
        # Estimate token budget
        prompt_tokens = len(self.model.tokenizer.encode(prompt))
        gen_tokens = min(40, max(15, self.context_limit - prompt_tokens - 10))
        if gen_tokens < 10:
            # Context full — truncate oldest history
            while gen_tokens < 15 and len(self.history) > 1:
                self.history.pop(0)
                prompt = "\n".join(self.history)
                prompt_tokens = len(self.model.tokenizer.encode(prompt))
                gen_tokens = min(40, self.context_limit - prompt_tokens - 10)

        result = self.model.generate(prompt, max_tokens=max(10, gen_tokens), temperature=0.8)
        text = result.generated_text.strip()
        self.history.append(text)
        return text, result.steps


class APIPrimer:
    """Priming via OpenAI-compatible API."""

    def __init__(self, api_key: str, model: str = "gpt-4", base_url: Optional[str] = None):
        from e0_middleware.api_wrapper import E0ChatClient
        self.client = E0ChatClient(
            api_key=api_key, model=model, base_url=base_url,
            e0_prime=False, logprobs=True,  # no auto-prime
        )
        self.name = f"E₀ API ({model})"
        self.context_limit = 128000

    def prime_step(self, statement: str) -> Tuple[str, List[StepMeasurement]]:
        resp = self.client.chat(statement)
        return resp.text, resp.steps


# ═══════════════════════════════════════════════
#  The Primer Engine
# ═══════════════════════════════════════════════

def run_primer(backend, compact: bool = False):
    """
    Execute the primer sequence, measuring each step.
    """
    sequence = PRIMER_COMPACT if compact else PRIMER_SEQUENCE

    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  E₀  S T R U C T U R A L  P R I M E R                     ║")
    print("║                                                              ║")
    print("║  Each statement is a structural truth.                       ║")
    print("║  Each response is measured.                                  ║")
    print("║  The trajectory tells the story.                             ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    print(f"  Backend:   {backend.name}")
    print(f"  Context:   {backend.context_limit} tokens")
    print(f"  Sequence:  {'compact' if compact else 'full'} ({len(sequence)} steps)")
    print()

    results = []
    prev_r = None

    for i, (label, statement) in enumerate(sequence, 1):
        print(f"━━ Step {i}/{len(sequence)}: {label} ━━")
        print(f"  → {statement}")
        print()

        t0 = time.time()
        try:
            text, steps = backend.prime_step(statement)
        except Exception as e:
            print(f"  [ERROR] {e}")
            print()
            results.append((label, statement, None, None))
            continue
        dt = time.time() - t0

        metrics = compute_metrics(steps)
        r = metrics["r_mean"]
        h = metrics["h_mean"]
        phi = metrics["phases"]
        v = metrics["v_median"]
        tau = metrics["tau"]

        # Direction indicator
        if prev_r is not None and r > 0:
            delta_r = r - prev_r
            if delta_r < -0.1:
                arrow = "↓ absorbing"
            elif delta_r > 0.1:
                arrow = "↑ resisting"
            else:
                arrow = "→ stable"
        else:
            arrow = "  (baseline)"
        prev_r = r

        # Clean response text
        clean = ''.join(c for c in text if (c.isprintable() or c in ('\n', ' ')) and c != '\ufffd')
        # Truncate for display
        display = clean[:120].replace('\n', ' ')
        if len(clean) > 120:
            display += "..."

        print(f"  ← {display}")
        print()
        print(f"  R̄={r:.3f}  H̄={h:.3f}  Φ={phi}  v̄={v:.3f}  τ={tau}  [{arrow}]  ({dt:.1f}s)")
        print()

        results.append((label, statement, metrics, arrow))

    # ═══ Summary ═══
    print()
    print("═" * 68)
    print("  PRIMER TRAJECTORY")
    print("═" * 68)
    print()
    print(f"  {'Step':<16s} │ R̄      │ H̄      │ Φ  │ v̄       │ Direction")
    print("  " + "─" * 62)

    for label, statement, metrics, arrow in results:
        if metrics is None:
            print(f"  {label:<16s} │  ERROR")
            continue
        r = metrics["r_mean"]
        h = metrics["h_mean"]
        phi = metrics["phases"]
        v = metrics["v_median"]
        print(f"  {label:<16s} │ {r:.3f} │ {h:.3f} │ {phi:>2d} │ {v:>7.3f} │ {arrow}")

    # ═══ Convergence Analysis ═══
    valid = [(l, m) for l, s, m, a in results if m is not None]
    if len(valid) >= 2:
        r_values = [m["r_mean"] for _, m in valid]
        first_r = r_values[0]
        last_r = r_values[-1]
        min_r = min(r_values)
        min_label = valid[r_values.index(min_r)][0]
        drops = sum(1 for j in range(1, len(r_values)) if r_values[j] < r_values[j-1])
        rises = sum(1 for j in range(1, len(r_values)) if r_values[j] > r_values[j-1])

        print()
        print("  ── Convergence ──")
        print(f"    First R̄:      {first_r:.3f}")
        print(f"    Last R̄:       {last_r:.3f}")
        print(f"    Lowest R̄:     {min_r:.3f} ({min_label})")
        print(f"    R̄ drops:      {drops}/{len(r_values)-1} steps")
        print(f"    R̄ rises:      {rises}/{len(r_values)-1} steps")

        if drops > rises:
            print()
            print("    The system absorbed the primer. Resistance decreased over the sequence.")
            print("    The structural landscape was progressively shaped.")
        elif rises > drops and (last_r - first_r) > 0.1:
            print()
            print("    The system resisted the primer. Resistance increased.")
            print("    This may indicate: model too small, context overflow, or")
            print("    sequence order needs adjustment for this architecture.")
        else:
            print()
            print("    Mixed or flat trajectory. The system partially absorbed the structure.")
            if backend.context_limit <= 2048:
                print("    Small context window may limit accumulation depth.")

        # R̄ trajectory visualization
        print()
        print("  ── R̄ Trajectory ──")
        print()
        max_r = max(r_values) if r_values else 1
        bar_width = 40
        for (label, _), r in zip(valid, r_values):
            bar_len = int((r / max_r) * bar_width) if max_r > 0 else 0
            bar = "█" * bar_len
            print(f"    {label:<16s} │ {bar} {r:.3f}")

    print()
    print("═" * 68)
    print("  The primer does not install E₀ into the system.")
    print("  It shapes the resistance landscape so that structural")
    print("  transitions become visible and measurable.")
    print("═" * 68)
    print()


# ═══════════════════════════════════════════════
#  Entry Point
# ═══════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="E₀ Structural Primer — responsible system initialization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  py e0_primer.py                       Simulation
  py e0_primer.py --local               GPT-2 on CPU (compact auto-selected)
  py e0_primer.py --local --model gpt2  Specific model
  py e0_primer.py --api sk-...          API model (full sequence)
  py e0_primer.py --full                Force full sequence even on small models
        """,
    )
    parser.add_argument("--local", action="store_true",
                        help="Use a local HuggingFace model")
    parser.add_argument("--model", type=str, default=None,
                        help="Model name")
    parser.add_argument("--api", type=str, default=None, metavar="KEY",
                        help="OpenAI-compatible API key")
    parser.add_argument("--base-url", type=str, default=None,
                        help="API base URL")
    parser.add_argument("--device", type=str, default="cpu",
                        help="Device for local model")
    parser.add_argument("--full", action="store_true",
                        help="Force full (non-compact) primer sequence")
    parser.add_argument("--compact", action="store_true",
                        help="Force compact primer sequence")

    args = parser.parse_args()

    # Select backend
    if args.local:
        model_name = args.model or "gpt2"
        print(f"\n  [E₀] Loading {model_name}...")
        backend = LocalPrimer(model_name, device=args.device)
    elif args.api:
        model_name = args.model or "gpt-4"
        backend = APIPrimer(args.api, model=model_name, base_url=args.base_url)
    else:
        backend = SimulationPrimer()

    # Auto-select compact vs full based on context limit
    if args.compact:
        compact = True
    elif args.full:
        compact = False
    else:
        # Auto: compact for small-context models
        compact = backend.context_limit <= 2048

    run_primer(backend, compact=compact)


if __name__ == "__main__":
    main()
