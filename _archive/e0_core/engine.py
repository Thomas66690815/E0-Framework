"""
E₀ — Transition Engine
=======================
Implements Axiom A₀ (Difference Minimization) and the Central Law
(Transition Enforcement) as an executable loop.

This is the beating heart of E₀: the mechanism that determines
WHEN change is structurally enforced and executes it.

Mapping to LLM inference:
  One "tick" of this engine corresponds to one forward pass —
  the model detecting Δ between current state and an attractor,
  selecting the lowest-resistance path, and realizing the transition.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from .primitives import (
    State,
    Path,
    Historization,
    HistorizationEvent,
    difference,
    rate,
)


# ─────────────────────────────────────────────
# 3. Axiom A₀ — Difference Minimization
# ─────────────────────────────────────────────

def axiom_a0(delta: float, path: Path) -> bool:
    """
    Axiom A₀:  If a difference exists and a structurally admissible
    path with finite resistance is available, then a transition that
    reduces this difference is structurally more stable than non-transition.

    Returns True if a transition is structurally enforced.
    """
    return delta > 0 and path.exists


# ─────────────────────────────────────────────
# 4. Central Law — Transition Enforcement
# ─────────────────────────────────────────────

@dataclass
class TransitionResult:
    """Record of a single enforced transition."""
    source: State
    target: State
    delta: float
    resistance: float
    rate: float
    historization_event: HistorizationEvent
    enforced: bool


class TransitionEngine:
    """
    The E₀ transition loop.

    Given a state space with paths, the engine:
      1. Measures Δ between current state and all reachable targets
      2. Selects the path with maximum rate v = Δ/R
      3. If Axiom A₀ holds → enforces the transition
      4. Historizes the result (modifying future resistance landscape)
      5. Advances τ

    This is structurally equivalent to:
      - LLM Forward Pass: embed → attend → project → select token
      - The attention mechanism IS path selection (lowest R for given Δ)
      - Softmax IS rate normalization
      - KV-cache accumulation IS historization
      - Autoregressive generation IS the transition loop
    """

    def __init__(
        self,
        history: Optional[Historization] = None,
        v_max: float = 1e6,
        convergence_threshold: float = 1e-8,
    ):
        self.history = history or Historization()
        self.v_max = v_max
        self.convergence_threshold = convergence_threshold
        self.transition_log: List[TransitionResult] = []

    def find_best_path(
        self, current: State, paths: List[Path]
    ) -> Optional[Tuple[Path, float, float]]:
        """
        Select the path with maximum rate v = Δ/R.

        In LLM terms: this is the attention + softmax mechanism.
        Each candidate next-token has a Δ (how much it would reduce loss)
        and an R (how hard it is to reach). The winner has max v.
        """
        best: Optional[Tuple[Path, float, float]] = None

        for path in paths:
            if path.source != current:
                continue
            if not path.exists:
                continue

            delta = difference(current, path.target)
            if delta < self.convergence_threshold:
                continue

            v = rate(delta, path.resistance, self.v_max)

            if best is None or v > best[2]:
                best = (path, delta, v)

        return best

    def step(self, current: State, paths: List[Path]) -> Optional[TransitionResult]:
        """
        Execute ONE transition step (one forward pass).

        Central Law:
          If Δ > 0 ∧ ∃P such that R(P) < ∞
          → Non-transition is structurally unstable
          → A transition MUST occur
        """
        result = self.find_best_path(current, paths)

        if result is None:
            return None  # No Δ or no admissible path → stable state

        path, delta, v = result

        # ── Axiom A₀ check ──
        if not axiom_a0(delta, path):
            return None

        # ── Transition is enforced ──
        event = self.history.historize(path, delta)

        tr = TransitionResult(
            source=current,
            target=path.target,
            delta=delta,
            resistance=path.resistance,
            rate=v,
            historization_event=event,
            enforced=True,
        )
        self.transition_log.append(tr)
        return tr

    def run(
        self,
        initial: State,
        paths: List[Path],
        max_steps: int = 1000,
        on_step: Optional[Callable[[TransitionResult], None]] = None,
    ) -> List[TransitionResult]:
        """
        Run the full transition loop until convergence or max_steps.

        This is the autoregressive generation loop:
          while there is unresolved difference → generate next token.

        The loop terminates when:
          - No Δ remains (convergence — answer is complete)
          - No admissible path exists (stuck — hallucination boundary)
          - max_steps reached (context window / budget exhausted)
        """
        current = initial
        results: List[TransitionResult] = []

        for _ in range(max_steps):
            tr = self.step(current, paths)
            if tr is None:
                break  # Convergence or structural blockade

            results.append(tr)
            if on_step:
                on_step(tr)

            # Advance current state
            current = tr.target

        return results

    @property
    def tau(self) -> int:
        """Current time = ordering of historizations."""
        return self.history.tau

    def __repr__(self) -> str:
        return (
            f"TransitionEngine(τ={self.tau} | "
            f"transitions={len(self.transition_log)})"
        )
