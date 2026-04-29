"""
E₀ DifferenzPort (C288)
========================
Universal protocol for injecting structural difference into E₀.

Core insight (Ontodynamics §2.1):
    Δ(x,y) is primary — not the agent that observes it, nor the medium
    through which it arrives. Any source of structural difference
    (LLM, sensor, human, another agent) must translate through this
    protocol before E₀ can historize it.

Design:
    DifferenzPort is an abstract base class. Each source of difference
    implements it. The impact of each port is tracked independently via
    Historization — E₀ learns how much to trust each input channel,
    just as it learns to trust any edge.

Implementations in this codebase:
    E1Monitor   (e1_monitor.py)    — LLM-proposed structure (ARC-D/E)
    ObservationPort (observation_port.py) — direct signal / sensor (C290)

Interface contract:
    port_name()        → identifier (used as source label in Edge keys)
    record_outcome()   → called after each navigation round
    impact_quality()   → trace_quality of this port's contributions
    dampening_factor() → analog signal: how much to scale downstream steps
    to_dict() / from_dict() → serialization for session persistence
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class DifferenzPort(ABC):
    """Abstract base: any source of structural difference entering E₀.

    A port does three things:
      1. Accepts structural proposals (nodes, edges, signals) — source-specific
      2. Records outcomes after E₀ navigates — via record_outcome()
      3. Reports its own impact quality — via impact_quality()

    E₀ treats every port as a hypothesis source. Low impact_quality means
    this port's proposals have confused E₀'s navigation → dampening_factor
    falls below 1.0 → E₀ applies fewer steps when this port's proposals
    dominate the landscape.
    """

    @abstractmethod
    def port_name(self) -> str:
        """Unique identifier for this port (used in Edge keys and diagnostics)."""

    @abstractmethod
    def record_outcome(self, outcome: "Outcome") -> None:  # type: ignore[name-defined]
        """Record a navigation outcome attributed to this port.

        Called by the session layer after each round. 'outcome' reflects
        whether E₀'s navigation produced coverage gain (SUCCESS) or not
        (FAILURE) in the context of this port's proposals.
        """

    @abstractmethod
    def impact_quality(self) -> float:
        """trace_quality of this port's contributions.

        Returns a value in [-1.0, +1.0]:
            +1.0  → port's proposals consistently helped navigation
             0.0  → mixed or no data
            -1.0  → port's proposals consistently confused navigation

        Returns 0.0 when no history is available.
        """

    @abstractmethod
    def dampening_factor(self) -> float:
        """Analog dampening signal for downstream step planning.

        Returns a value in (0.0, 1.0]:
            1.0   → no dampening (neutral or positive history)
            < 1.0 → reduce steps proportionally

        Derived from mean inertia_factor over all port edges.
        Returns 1.0 when no data — neutral, no overhead.
        """

    @abstractmethod
    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dict for session persistence."""

    @classmethod
    @abstractmethod
    def from_dict(cls, data: Optional[dict]) -> "DifferenzPort":
        """Restore from a serialized dict. Missing/None data → fresh instance."""
