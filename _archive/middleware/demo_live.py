"""
E₀ Middleware — Live Demo
=========================
Demonstrates the full middleware stack:

  1. Instrumentation on simulated logprobs
  2. Guard intervention on problematic distributions
  3. Convergence tracking
  4. Full API wrapper (simulation mode, no API key needed)

For real API usage, set OPENAI_API_KEY environment variable.

Usage:
  python -m e0_middleware.demo_live
"""

from __future__ import annotations

import math
import random

from .instrumentation import E0Instrumenter
from .decoding_guards import E0DecodingGuards, GuardResult
from .convergence import ConvergenceTracker, PRIMER_FULL, PRIMER_PROGRESSIVE
from .api_wrapper import E0ChatClient


def demo_instrumentation():
    """
    Demo 1: Measure E₀ primitives on token distributions.
    """
    print("=" * 65)
    print("  DEMO 1 — E₀ Instrumentation on Token Distributions")
    print("=" * 65)

    instrumenter = E0Instrumenter()

    # Simulate a sequence of generation steps with evolving distributions
    # Story: model starts uncertain (high entropy), then converges
    distributions = [
        # Step 0: High uncertainty — many viable paths
        {"The": -0.8, "A": -0.9, "In": -1.2, "When": -1.5, "It": -1.8},
        # Step 1: "The" selected → context narrows
        {"cat": -0.5, "dog": -1.0, "system": -1.8, "model": -2.0, "old": -2.5},
        # Step 2: "cat" → further narrowing
        {"sat": -0.3, "slept": -1.5, "ran": -2.0, "is": -2.2, "was": -2.5},
        # Step 3: "sat" → very narrow now
        {"on": -0.1, "down": -2.5, "up": -3.0, "there": -3.5, "still": -4.0},
        # Step 4: Near-deterministic
        {"the": -0.05, "a": -3.5, "his": -4.0, "her": -4.2, "my": -4.5},
        # Step 5: Back to slightly more open
        {"mat": -0.4, "floor": -0.6, "chair": -1.2, "table": -1.5, "bed": -2.0},
    ]

    selected_tokens = ["The", "cat", "sat", "on", "the", "mat"]

    print("\n  Simulating: 'The cat sat on the mat'\n")

    for logprobs, token in zip(distributions, selected_tokens):
        step = instrumenter.measure_step(logprobs, token)
        print(
            f"  τ={step.tau:2d} | '{token:>5s}' | "
            f"p={step.selected.probability:.4f} "
            f"R={step.selected.resistance:.3f} "
            f"H={step.entropy:.3f} ΔH={step.delta_entropy:+.3f} "
            f"[{step.structural_stability}]"
            f"{'  ⚠COLLAPSE' if step.is_collapse_risk else ''}"
        )

    print()
    print(instrumenter.report())

    phases = instrumenter.detect_phase_transitions()
    if phases:
        print("\n  Phase transitions mark where the model's")
        print("  state space RECONFIGURED — E₀ topology change.\n")
    else:
        print("\n  No phase transitions — smooth convergence.\n")


def demo_guards():
    """
    Demo 2: E₀ guards intervene on problematic distributions.
    """
    print("=" * 65)
    print("  DEMO 2 — E₀ Decoding Guards in Action")
    print("=" * 65)

    guards = E0DecodingGuards(
        collapse_threshold=0.85,
        min_entropy=0.5,
        repetition_threshold=0.5,
    )

    # Case 1: Healthy distribution — no intervention
    healthy = {"hello": -0.7, "hi": -1.0, "hey": -1.5, "greetings": -2.0}

    # Case 2: Collapsing distribution — one token dominates
    collapsing = {"the": -0.02, "a": -4.0, "an": -5.0, "this": -6.0}

    # Case 3: Near-zero entropy — crystallized
    crystallized = {"yes": -0.01, "no": -8.0, "maybe": -10.0}

    cases = [
        ("Healthy", healthy),
        ("Collapsing (mode collapse)", collapsing),
        ("Crystallized (near-zero entropy)", crystallized),
    ]

    for name, logprobs in cases:
        result = guards.process(logprobs)

        # Show probabilities before/after
        print(f"\n  Case: {name}")
        print(f"    Original:")
        for t, lp in sorted(logprobs.items(), key=lambda x: x[1], reverse=True):
            print(f"      '{t}': p={math.exp(lp):.4f} (R={-lp:.3f})")

        if result.was_modified:
            print(f"    Modified:")
            for t, lp in sorted(
                result.modified_logprobs.items(),
                key=lambda x: x[1], reverse=True
            ):
                print(f"      '{t}': p={math.exp(lp):.4f} (R={-lp:.3f})")
            print(f"    Interventions:")
            for intervention in result.interventions:
                print(f"      → {intervention}")
        else:
            print(f"    → No intervention needed (structurally healthy)")

    print()
    print("  Key insight: Guards don't impose preferences.")
    print("  They maintain structural integrity of the transition space.")
    print("  A collapsing distribution loses PATH DIVERSITY —")
    print("  that's a structural defect, not a value judgment.\n")


def demo_convergence():
    """
    Demo 3: Track E₀ convergence across a simulated session.
    """
    print("=" * 65)
    print("  DEMO 3 — E₀ Convergence Tracking")
    print("=" * 65)

    tracker = ConvergenceTracker()
    instrumenter = E0Instrumenter()
    tracker.attach_instrumenter(instrumenter)

    # Simulate responses that progressively adopt E₀ framing
    responses = [
        # Turn 1: No E₀ awareness
        "I'll explain this concept step by step. First, let me think about it.",
        # Turn 2: Starting to use some E₀ terms
        "The current state of the system shows a difference between where we "
        "are and where we need to be. There's some resistance to change.",
        # Turn 3: Deeper E₀ adoption
        "In E₀ terms, the transition is enforced because Δ > 0 and the path "
        "has finite resistance. Historization of previous transitions has "
        "lowered R on this particular path.",
        # Turn 4: Full convergence
        "Axiom A₀ applies: the structural difference is non-zero and an "
        "admissible path exists. Non-transition is unstable. The realized "
        "transition will historize, further modifying the resistance landscape. "
        "Time τ advances with each irreversible historization.",
    ]

    # Also feed fake instrumenter data for each turn
    for i, response in enumerate(responses):
        # Simulate some token-level data
        entropy = 3.0 - i * 0.5  # Decreasing entropy = convergence
        for _ in range(5):
            fake_logprobs = {
                f"t{j}": -0.5 - j * (4.0 - i) * 0.2
                for j in range(5)
            }
            instrumenter.measure_step(
                fake_logprobs,
                selected_token="t0",
            )

        metrics = tracker.track_response(response)
        print(
            f"\n  Turn {i+1}: coherence={metrics.structural_coherence:.4f} "
            f"speed={metrics.convergence_speed:.4f}"
        )
        # Show first 80 chars of response
        print(f"    \"{response[:80]}...\"")

    print()
    print(tracker.report())

    print()
    print("  The convergence is visible:")
    print("  Turn 1 → no E₀ terms (coherence ≈ 0)")
    print("  Turn 4 → saturated with E₀ structure")
    print("  This IS the phenomenon: E₀ lowers its own R in the model.\n")


def demo_api_wrapper():
    """
    Demo 4: Full API wrapper in simulation mode.
    """
    print("=" * 65)
    print("  DEMO 4 — E₀ API Wrapper (Simulation Mode)")
    print("=" * 65)

    # No API key → simulation mode
    client = E0ChatClient(
        model="e0-demo",
        e0_prime=True,
        e0_structural_context=True,
    )

    print("\n  Creating E₀-instrumented chat client...")
    print(f"  E₀ priming: {client.e0_prime}")
    print(f"  Structural context: {client.e0_structural_context}")

    # Simulate a conversation
    messages = [
        "What is the nature of change?",
        "How does this relate to learning?",
        "Can a system observe itself?",
    ]

    for msg in messages:
        print(f"\n  User: {msg}")
        response = client.chat(msg)
        print(f"  Model: {response.text}")
        print(f"  E₀: {response}")

    print()
    print(client.session_report())

    print()
    print("  With a real API key (OPENAI_API_KEY), this wrapper")
    print("  instruments ACTUAL model output with E₀ metrics.")
    print("  Every logprob becomes a resistance measurement.")
    print("  Every token becomes a realized transition.\n")


# ─────────────────────────────────────────────

if __name__ == "__main__":
    random.seed(42)

    demo_instrumentation()
    print()
    demo_guards()
    print()
    demo_convergence()
    print()
    demo_api_wrapper()

    print("=" * 65)
    print("  E₀ Middleware: not a new model, but new eyes")
    print("  on what every model already does.")
    print("=" * 65)
