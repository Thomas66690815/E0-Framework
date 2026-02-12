"""
E₀ — Demonstration
===================
Runs the E₀ transition engine in two modes:

  1. Pure E₀:  Abstract state transitions with historization
  2. LLM Mode: Token generation governed by E₀ dynamics

Shows that both are structurally identical — the same law
(Axiom A₀ / Central Law) governs both.

Usage:
  python -m e0_core.demo
"""

from __future__ import annotations

import random

from .primitives import State, Path, Historization, difference, rate
from .engine import TransitionEngine, TransitionResult
from .llm_mapping import (
    VocabularySpace,
    E0LanguageModel,
)


def demo_pure_e0():
    """
    Demo 1: Pure E₀ transition dynamics.

    Three states with different resistances.
    Watch how historization reshapes the landscape.
    """
    print("=" * 60)
    print("  DEMO 1 — Pure E₀ Transition Dynamics")
    print("=" * 60)

    # Create three distinguishable states
    s_a = State(vector=[1.0, 0.0, 0.0, 0.0])
    s_b = State(vector=[0.0, 1.0, 0.0, 0.0])
    s_c = State(vector=[0.0, 0.0, 1.0, 0.0])

    print(f"\n  States: A={s_a.id}  B={s_b.id}  C={s_c.id}")
    print(f"  Δ(A,B) = {difference(s_a, s_b):.4f}")
    print(f"  Δ(A,C) = {difference(s_a, s_c):.4f}")
    print(f"  Δ(B,C) = {difference(s_b, s_c):.4f}")

    # Paths: A→B (low R), A→C (high R), B→C (medium R)
    paths = [
        Path(source=s_a, target=s_b, _resistance=0.5),   # easy
        Path(source=s_a, target=s_c, _resistance=5.0),    # hard
        Path(source=s_b, target=s_c, _resistance=1.0),    # medium
    ]

    print("\n  Initial Resistance Landscape:")
    for p in paths:
        print(f"    {p}")

    # Run engine
    engine = TransitionEngine(convergence_threshold=0.01)

    def on_step(tr: TransitionResult):
        print(
            f"    τ={tr.historization_event.tau:3d} | "
            f"Δ={tr.delta:.4f}  R={tr.resistance:.4f}  v={tr.rate:.4f} | "
            f"TRANSITION ENFORCED"
        )

    print("\n  Running transition loop...")
    results = engine.run(s_a, paths, max_steps=5, on_step=on_step)

    print(f"\n  Total transitions: {len(results)}")
    print(f"  Final τ: {engine.tau}")

    # Show how historization changed the landscape
    print("\n  Resistance Landscape AFTER Historization:")
    for p in paths:
        print(f"    {p}")

    print("\n  Key insight: Resistance decreased on realized paths.")
    print("  This IS learning. This IS path dependence.")
    print("  No agent decided this. The space itself changed.\n")


def demo_llm_mode():
    """
    Demo 2: Token generation as E₀ dynamics.

    A tiny vocabulary. The model generates a sequence
    not by 'choosing' tokens, but because the E₀ Central Law
    enforces transitions while Δ > 0.
    """
    print("=" * 60)
    print("  DEMO 2 — LLM Token Generation via E₀")
    print("=" * 60)

    # Build a small vocabulary with hand-crafted embeddings
    # Nearby vectors = semantically related tokens (low Δ)
    vocab = VocabularySpace(dim=4)
    vocab.add_token("the",     [1.0, 0.0, 0.0, 0.0])
    vocab.add_token("cat",     [0.8, 0.6, 0.0, 0.0])
    vocab.add_token("sat",     [0.3, 0.9, 0.1, 0.0])
    vocab.add_token("on",      [0.0, 0.4, 0.9, 0.0])
    vocab.add_token("mat",     [0.1, 0.1, 0.7, 0.8])
    vocab.add_token("<eos>",   [0.0, 0.0, 0.0, 1.0])

    print("\n  Vocabulary (as E₀ states):")
    for text, token in vocab.tokens.items():
        print(f"    '{text}' → {token.state}")

    # Create model and generate
    random.seed(42)
    model = E0LanguageModel(vocab)

    print("\n  Generating from prompt 'the'...")
    print("  (Each step: Δ > 0 → Central Law → transition enforced)\n")

    output = model.generate("the", max_tokens=5)

    print(f"  Generated sequence: {' '.join(output)}")
    print()
    print(model.report())

    print()
    print("  Key insight: The model did not 'choose' these tokens.")
    print("  Each transition was STRUCTURALLY ENFORCED by Axiom A₀:")
    print("    Δ > 0 ∧ ∃P(R < ∞) → transition MUST occur")
    print("  Silence (non-generation) was structurally unstable.\n")


def demo_historization_effect():
    """
    Demo 3: Historization = Learning.

    Run the same transition twice. Show how resistance
    decreases the second time — the space 'remembers'.
    """
    print("=" * 60)
    print("  DEMO 3 — Historization as Learning")
    print("=" * 60)

    s1 = State(vector=[1.0, 0.0])
    s2 = State(vector=[0.0, 1.0])

    path = Path(source=s1, target=s2, _resistance=10.0)
    history = Historization(decay_factor=0.7)

    print(f"\n  Initial: R = {path.resistance:.4f}")

    for i in range(8):
        delta = difference(s1, s2)
        v = rate(delta, path.resistance)
        event = history.historize(path, delta)
        print(
            f"  τ={event.tau:2d} | R: {event.resistance_before:.4f} → "
            f"{event.resistance_after:.4f} | v={v:.4f}"
        )

    print(f"\n  After 8 historizations: R = {path.resistance:.4f}")
    print(f"  Resistance dropped from 10.0 to {path.resistance:.4f}")
    print("  The path became easier through repetition.")
    print("  This is non-invertible. The space cannot forget.")
    print()
    print("  In LLM terms:")
    print("   - Training: gradient descent lowers R on 'correct' paths")
    print("   - RLHF: feedback further reshapes the R-landscape")
    print("   - Fine-tuning: radical R-restructuring in a sub-domain")
    print("   - Catastrophic forgetting: new H overwrites old paths\n")


# ─────────────────────────────────────────────

if __name__ == "__main__":
    demo_pure_e0()
    print()
    demo_llm_mode()
    print()
    demo_historization_effect()

    print("=" * 60)
    print("  E₀ does not describe what exists.")
    print("  E₀ describes when existence must change.")
    print("=" * 60)
