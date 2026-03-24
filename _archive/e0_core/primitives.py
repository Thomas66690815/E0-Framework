"""
E₀ — Primitives Module
=======================
Implements the seven irreducible concepts of the E₀ canon:
  State, Difference (Δ), Path (P), Resistance (R),
  Historization (H), Time (τ), Rate (v)

Design principle:
  Every class maps 1:1 to a canonical concept.
  No semantic, agentive, or domain-specific assumptions are made.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ─────────────────────────────────────────────
# 2.1  State — a distinguishable configuration
# ─────────────────────────────────────────────

@dataclass
class State:
    """
    A distinguishable configuration.

    States carry no meaning, value, or interpretation.
    They are only required to be distinguishable from other states.

    In LLM terms: a hidden-state vector at any layer or timestep.
    """
    vector: List[float]
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    @property
    def dim(self) -> int:
        return len(self.vector)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, State):
            return NotImplemented
        return self.vector == other.vector

    def __hash__(self) -> int:
        return hash(tuple(self.vector))

    def __repr__(self) -> str:
        preview = self.vector[:4]
        suffix = ", ..." if len(self.vector) > 4 else ""
        return f"State({self.id} | {preview}{suffix})"


# ─────────────────────────────────────────────
# 2.2  Difference (Δ) — non-identity measure
# ─────────────────────────────────────────────

def difference(s1: State, s2: State) -> float:
    """
    Δ(s1, s2) — Measure of non-identity between two states.

    Δ = 0  ⇔  states are identical
    Δ > 0  ⇔  states are non-identical

    Without difference, no transition is possible.

    In LLM terms: distance between current hidden state and
    an attractor state (e.g. predicted next-token embedding vs. target).
    """
    if s1.dim != s2.dim:
        raise ValueError(f"State dimensions mismatch: {s1.dim} vs {s2.dim}")
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(s1.vector, s2.vector)))


# ─────────────────────────────────────────────
# 2.3  Path (P) — structural admissibility
# ─────────────────────────────────────────────

@dataclass
class Path:
    """
    Structural admissibility condition for a transition.

    A path is NOT an object or dynamic — it specifies WHETHER
    a transition is structurally allowed.

    A path exists iff its total resistance is finite.

    In LLM terms: attention-weighted connection between states;
    the softmax gate that determines if information can flow.
    """
    source: State
    target: State
    _resistance: float = 1.0

    @property
    def exists(self) -> bool:
        """A path exists iff resistance is finite."""
        return not math.isinf(self._resistance)

    @property
    def resistance(self) -> float:
        return self._resistance

    @resistance.setter
    def resistance(self, value: float) -> None:
        if value < 0:
            raise ValueError("Resistance cannot be negative")
        self._resistance = value

    def __repr__(self) -> str:
        status = "open" if self.exists else "blocked"
        return f"Path({self.source.id}→{self.target.id} | R={self._resistance:.4f} | {status})"


# ─────────────────────────────────────────────
# 2.4  Resistance (R) — structural inertia
# ─────────────────────────────────────────────

def resistance(path: Path) -> float:
    """
    R(P) — Structural inertia of a transition.

    R > 0   for all real transitions
    R = ∞   ⇒ transition is non-existent

    Resistance is a property of the state space, not of an agent.

    In LLM terms: inverse attention weight; low probability paths
    carry high resistance. Masked positions have R = ∞.
    """
    return path.resistance


# ─────────────────────────────────────────────
# 2.5  Historization (H) — memory of the space
# ─────────────────────────────────────────────

@dataclass
class HistorizationEvent:
    """Record of a single realized transition."""
    source_id: str
    target_id: str
    delta: float
    resistance_before: float
    resistance_after: float
    tau: int  # time-index — ordering of historizations


class Historization:
    """
    Modification of the resistance landscape by realized transitions.

    Properties (canonical):
      - Only realized transitions historize
      - Historization lowers future resistance of the same transition
      - Historization is non-invertible

    In LLM terms:
      - Training: weight updates (gradient descent lowers R on realized paths)
      - Inference: KV-cache accumulation (prior context lowers R for related tokens)
      - RLHF: human feedback reshapes the resistance landscape
    """

    def __init__(self, decay_factor: float = 0.9):
        self.events: List[HistorizationEvent] = []
        self.decay_factor = decay_factor  # how much R is reduced per historization

    @property
    def tau(self) -> int:
        """Current time = number of historizations (τ ordering)."""
        return len(self.events)

    def historize(self, path: Path, delta: float) -> HistorizationEvent:
        """
        Record a realized transition and lower future resistance.

        This is non-invertible: once historized, the landscape is
        permanently changed. There is no 'undo'.
        """
        r_before = path.resistance

        # Lower resistance for this path (learning / path dependence)
        # R_new = R_old * decay_factor — never reaches zero
        path.resistance = max(path.resistance * self.decay_factor, 1e-10)

        event = HistorizationEvent(
            source_id=path.source.id,
            target_id=path.target.id,
            delta=delta,
            resistance_before=r_before,
            resistance_after=path.resistance,
            tau=self.tau,
        )
        self.events.append(event)
        return event

    def is_invertible(self) -> bool:
        """Historization is canonically non-invertible."""
        return False

    def __repr__(self) -> str:
        return f"Historization(τ={self.tau} | events={len(self.events)})"


# ─────────────────────────────────────────────
# 2.6  Time (τ) — ordering of historizations
# ─────────────────────────────────────────────

def time(history: Historization) -> int:
    """
    τ — Time is the ordering of historizations.

    Time is not a dimension, not a container, not assumed a priori.
    If no historization occurs, no time progresses.

    In LLM terms: not the positional encoding (that's imposed),
    but the emergent sequence of attention + generation steps
    that actually change the model's state.
    """
    return history.tau


# ─────────────────────────────────────────────
# 2.7  Rate (v) — transition ordering
# ─────────────────────────────────────────────

def rate(delta: float, r: float, v_max: float = 1e6) -> float:
    """
    v := Δ / R

    Rate orders transition realization.
    Rate is not probability.
    A maximum rate exists.

    In LLM terms: tokens with high Δ (surprise/loss) and low R
    (high attention weight) are generated first / with higher priority.
    The softmax temperature acts as a global rate modifier.
    """
    if r <= 0:
        raise ValueError("Resistance must be > 0 for real transitions")
    if math.isinf(r):
        return 0.0
    return min(delta / r, v_max)
