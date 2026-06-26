from __future__ import annotations

from enum import Enum
from typing import NamedTuple


class Edge(NamedTuple):
    """Directed edge: context → action."""
    source: str
    target: str

    def __repr__(self) -> str:
        return f"{self.source}→{self.target}"


class Outcome(Enum):
    """Result of executing a transition.

    SUCCESS and FAILURE are canonical. PARTIAL is a runtime convenience that
    splits weight as U += 0.5, F += 0.3; the unresolved residual (0.2) is
    silently dropped — prefer binary outcomes where possible (E₀ open gap GT-8).
    """
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
