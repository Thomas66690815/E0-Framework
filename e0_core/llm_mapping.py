"""
E₀ → LLM Mapping Layer
=======================
Demonstrates how standard LLM components map onto E₀ primitives.

This module does NOT re-implement a transformer.
It shows the structural isomorphism between E₀ dynamics
and what a transformer already does.

┌─────────────────────────────────────────────────────────┐
│           E₀ Primitive  →  LLM Component                │
│─────────────────────────────────────────────────────────│
│  State (S)              →  Hidden-state vector h_t      │
│  Difference (Δ)         →  Loss / cross-entropy / δh    │
│  Path (P)               →  Attention weight > 0         │
│  Resistance (R)         →  1/attention_weight (or mask)  │
│  Historization (H)      →  KV-cache / weight update     │
│  Time (τ)               →  Autoregressive step count    │
│  Rate (v = Δ/R)         →  Effective token probability  │
│  Axiom A₀               →  "Generate until EOS"        │
│  Central Law             →  Autoregressive enforcement  │
└─────────────────────────────────────────────────────────┘

Key insight:
  An LLM does not 'choose' to generate the next token.
  The E₀ structure shows it MUST generate it —
  because Δ > 0 (the sequence is incomplete)
  and P exists with R < ∞ (the model has learned paths).
  Non-transition (silence) is structurally unstable.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .primitives import (
    State,
    Path,
    Historization,
    difference,
    rate,
)
from .engine import TransitionEngine, TransitionResult


# ─────────────────────────────────────────────
# Vocabulary as State Space
# ─────────────────────────────────────────────

@dataclass
class Token:
    """A token is a named state in the vocabulary space."""
    text: str
    state: State


class VocabularySpace:
    """
    The vocabulary as an E₀ state space.

    Each token is a distinguishable state.
    The 'embedding' is the state vector.
    Attention weights become path resistances.
    """

    def __init__(self, dim: int = 8):
        self.dim = dim
        self.tokens: Dict[str, Token] = {}

    def add_token(self, text: str, vector: Optional[List[float]] = None) -> Token:
        if vector is None:
            vector = [random.gauss(0, 1) for _ in range(self.dim)]
        state = State(vector=vector)
        token = Token(text=text, state=state)
        self.tokens[text] = token
        return token

    def get(self, text: str) -> Token:
        return self.tokens[text]

    def all_states(self) -> List[State]:
        return [t.state for t in self.tokens.values()]

    def state_to_text(self, state: State) -> str:
        for token in self.tokens.values():
            if token.state == state:
                return token.text
        return f"<unknown:{state.id}>"


# ─────────────────────────────────────────────
# Attention as Resistance Landscape
# ─────────────────────────────────────────────

class AttentionAsResistance:
    """
    Maps attention weights to E₀ resistance values.

    High attention weight  →  Low resistance  →  Path is easy
    Low attention weight   →  High resistance →  Path is hard
    Zero attention (mask)  →  R = ∞           →  Path blocked

    The correct formula is R = -log(p), not R = 1/p.

    Why: The QM reconstruction (see qm_reconstruction.py) shows that
    probability = |amplitude|² (Born rule) emerges from conserved
    realization. The resistance R = -log(p) is the unique measure
    that makes resistance ADDITIVE along paths:
      R(A→C) = R(A→B) + R(B→C)  iff  p(A→C) = p(A→B) · p(B→C)
    This is the same relationship underlying Shannon information.

    Structural insight: softmax(Q·K^T/√d_k) computes the graduated
    overlap (inner product) between query and key states. The output
    IS the Born probability |⟨q|k⟩|². Attention is not a 'weight'.
    It is a measurement of structural admissibility.
    """

    def attention_to_resistance(self, attention_weight: float) -> float:
        """Convert attention weight [0,1] to resistance (0, ∞].

        R = -log(p) — the structurally correct formula.
        Consistent with e0_middleware instrumentation and QM reconstruction.
        """
        if attention_weight <= 1e-10:
            return math.inf  # Masked — no path
        return -math.log(attention_weight)

    def build_paths(
        self,
        source: State,
        targets: List[State],
        attention_weights: List[float],
    ) -> List[Path]:
        """
        Build E₀ paths from a source state to all candidate targets,
        weighted by attention scores.
        """
        paths = []
        for target, weight in zip(targets, attention_weights):
            r = self.attention_to_resistance(weight)
            paths.append(Path(source=source, target=target, _resistance=r))
        return paths


# ─────────────────────────────────────────────
# KV-Cache as Historization
# ─────────────────────────────────────────────

class KVCacheAsHistorization(Historization):
    """
    The KV-cache IS historization:

    - Each appended key-value pair is a realized transition
    - It lowers resistance for contextually related future tokens
    - It is non-invertible within a generation pass
      (you can't un-attend to something already in the cache)
    - It creates path dependence:
      early tokens shape what later tokens can easily become

    Training weight updates are a DEEPER historization:
    - They reshape the global resistance landscape
    - They persist across sessions
    - They are the 'geological' memory of the state space
    """

    def __init__(self, decay_factor: float = 0.85):
        super().__init__(decay_factor=decay_factor)
        self.cache: List[Tuple[str, str]] = []  # (source_id, target_id)

    def historize(self, path, delta):
        event = super().historize(path, delta)
        self.cache.append((path.source.id, path.target.id))
        return event

    @property
    def context_length(self) -> int:
        return len(self.cache)


# ─────────────────────────────────────────────
# LLM Generation as E₀ Transition Loop
# ─────────────────────────────────────────────

class E0LanguageModel:
    """
    A minimal 'language model' built entirely from E₀ primitives.

    This is NOT a real transformer. It demonstrates that the
    autoregressive generation loop IS the E₀ transition law:

      while Δ > 0 and ∃P with R < ∞:
          select path with max v = Δ/R
          realize transition
          historize
          advance τ

    That loop IS what GPT/Claude/Gemini do on every forward pass.
    The E₀ framework reveals it is not a design choice —
    it is structurally enforced.
    """

    def __init__(self, vocab: VocabularySpace):
        self.vocab = vocab
        self.attention = AttentionAsResistance()
        self.history = KVCacheAsHistorization()
        self.engine = TransitionEngine(
            history=self.history,
            convergence_threshold=0.1,
        )

    def _compute_attention_weights(
        self, source: State, targets: List[State]
    ) -> List[float]:
        """
        Simplified attention: computes graduated overlap via softmax.

        In a real transformer this is:
          softmax(Q·K^T / √d_k)

        Q·K^T is the inner product — the graduated overlap between
        query and key states (Ontodynamics §3.4). The softmax converts
        this to Born probabilities: P(k) = |⟨q|k⟩|² (see Step 3 of
        qm_reconstruction.py).

        Before token selection, the distribution IS a superposition:
        multiple tokens partially realized, connected, phase-correlated.
        Selection = measurement = historization (irreversible collapse).
        """
        deltas = [difference(source, t) for t in targets]
        if not deltas or max(deltas) == 0:
            return [0.0] * len(targets)

        # Negative distance → softmax ≈ inner product structure
        # This is the simplified form of softmax(Q·K^T / √d)
        scale = 1.0 / math.sqrt(source.dim) if source.dim > 0 else 1.0
        scores = [-d * scale for d in deltas]
        max_score = max(scores)
        exp_scores = [math.exp(s - max_score) for s in scores]
        total = sum(exp_scores)
        return [e / total for e in exp_scores] if total > 0 else [0.0] * len(exp_scores)

    def generate_step(self, current_token: Token) -> Optional[TransitionResult]:
        """
        One generation step = one E₀ transition = one quantum measurement.

        Before this step: the model is in SUPERPOSITION over all tokens.
        Each token is partially realized with amplitude α_k.
        The softmax output gives P(k) = |α_k|² (Born rule).

        This step: a token is selected. This is HISTORIZATION.
        The superposition collapses irreversibly to one outcome.
        The KV-cache records the trace. The transition cannot be undone.

        The model MUST generate if Δ > 0 and a path exists.
        This is not a choice. It is the Central Law.
        """
        targets = [
            t.state for t in self.vocab.tokens.values()
            if t.state != current_token.state
        ]
        if not targets:
            return None

        weights = self._compute_attention_weights(current_token.state, targets)
        paths = self.attention.build_paths(current_token.state, targets, weights)

        return self.engine.step(current_token.state, paths)

    def generate(
        self, prompt_token: str, max_tokens: int = 10
    ) -> List[str]:
        """
        Autoregressive generation loop — the Central Law in action.

        Generates tokens until:
          - Δ → 0 (convergence)
          - No path with R < ∞ (structural blockade)
          - max_tokens hit (context budget)
        """
        current = self.vocab.get(prompt_token)
        output = [current.text]

        for _ in range(max_tokens):
            result = self.generate_step(current)
            if result is None:
                break

            next_text = self.vocab.state_to_text(result.target)
            output.append(next_text)

            # Advance state
            current = Token(text=next_text, state=result.target)

        return output

    def report(self) -> str:
        """Summary of the E₀ state after generation."""
        lines = [
            "═══ E₀ Language Model — State Report ═══",
            f"  τ (time)          : {self.engine.tau}",
            f"  Transitions       : {len(self.engine.transition_log)}",
            f"  KV-Cache depth    : {self.history.context_length}",
            f"  Vocabulary size   : {len(self.vocab.tokens)}",
            "",
            "  Transition History:",
        ]
        for tr in self.engine.transition_log:
            src = self.vocab.state_to_text(tr.source)
            tgt = self.vocab.state_to_text(tr.target)
            lines.append(
                f"    τ={tr.historization_event.tau:3d} | "
                f"{src:>12s} → {tgt:<12s} | "
                f"Δ={tr.delta:.4f}  R={tr.resistance:.4f}  v={tr.rate:.4f}"
            )
        return "\n".join(lines)
