"""
E₀ Controller — Primitives
===========================
Minimal types for the controller domain.

Spec coverage: §2.1 (Difference), §2.2 (Resistance), §2.3 (Historization basics).

Design decision: States are string-IDs (graph domain).
Δ and R₀ are defined per-edge in the Landscape, not per-state-vector.
This keeps the controller domain-invariant — any graph works.
"""

from __future__ import annotations

from enum import Enum
from typing import NamedTuple


class Outcome(Enum):
    """Result of executing a transition."""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"


class Edge(NamedTuple):
    """Directed edge between two states."""
    source: str
    target: str

    def __repr__(self) -> str:
        return f"{self.source}→{self.target}"
