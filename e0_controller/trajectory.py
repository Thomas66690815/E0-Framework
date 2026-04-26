"""C277: Trajectory-level historization.

A PathSignature is a tuple of community indices traversed during one round.
Unlike node-ID paths (instance-specific), signatures are:
  - domain-invariant: community 0 might be Canon or Bootstrap depending
    on the detected topology — no prefix assumption
  - structure-aware: the same pattern of boundary crossings maps to the
    same signature regardless of which specific nodes were visited
  - historizable: U/F traces accumulate on signatures across rounds

This is the first E₀ mechanism that is explicitly non-Markov:
plan() can now consult the *history of trajectory shapes*, not just
the current state, when choosing a strategy.

Relationship to F4 (non-Markov paths, previously 0%):
  TrajectoryHistorization accumulates evidence that a particular path
  *shape* is productive or stagnant.  plan() uses this to escape patterns
  that have historically led nowhere — proactively, before stagnation
  is detected through coverage_delta alone.

Relationship to Paper C48 (path critique, three-level skepticism):
  This module provides the first-class trajectory object required for
  path critique.  The query "has this trajectory shape been productive?"
  is the simplest instantiation of path-level doubt.

BT-5 (new breakthrough, analogous to BT-3 at trajectory level):
  BT-3: F=0 traps the system at the edge level — allowing doubt is
        structurally necessary.
  BT-5: A fixed trajectory shape traps the system at the round level —
        trajectory-level historization is structurally necessary for
        escape from pattern-level stagnation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

# A PathSignature is a compressed sequence of community indices.
# Consecutive duplicates are removed: staying in the same community
# for multiple steps is not structurally distinct.
PathSignature = Tuple[int, ...]


def compute_path_signature(
    path: List[str],
    communities: List[Set[str]],
) -> PathSignature:
    """Convert a node-ID path to a community-index signature.

    Each node maps to its community index (-1 if not found).
    Consecutive duplicates are removed — only boundary crossings
    matter for the signature.

    Args:
        path: Sequence of node IDs from one navigation round.
        communities: Community partition (list of node sets).

    Returns:
        Tuple of community indices with consecutive duplicates removed.

    Example::
        path = ["C:omega", "C:zeta", "B:HERE", "B:L4", "C:omega"]
        communities = [{"C:omega", "C:zeta"}, {"B:HERE", "B:L4"}]
        → (0, 1, 0)   # two boundary crossings
    """
    if not communities:
        return ()

    # Import locally to avoid circular import at module load time
    from e0_controller.explore_learning_cycle_multidomain import community_of

    indices = [community_of(node, communities) for node in path]

    # Compress: remove consecutive duplicates
    compressed: List[int] = []
    for idx in indices:
        if not compressed or compressed[-1] != idx:
            compressed.append(idx)

    return tuple(compressed)


@dataclass
class TrajectoryRecord:
    """One round's trajectory summarised as a historizable signature.

    outcome is derived from coverage_delta:
      - productive  : Δcoverage ≥ 0.01   (clear progress)
      - improving   : Δcoverage ≥ 0.001  (marginal progress)
      - stagnant    : Δcoverage < 0.001  (no progress)
    """

    signature: PathSignature
    mode: str
    coverage_delta: float
    community_crossings: int

    @property
    def outcome(self) -> str:
        if self.coverage_delta >= 0.01:
            return "productive"
        elif self.coverage_delta >= 0.001:
            return "improving"
        else:
            return "stagnant"


class TrajectoryHistorization:
    """Accumulates U/F traces on PathSignatures across rounds.

    U = rounds where this signature was productive or improving
        (coverage_delta ≥ 0.001)
    F = rounds where this signature was stagnant
        (coverage_delta < 0.001)

    trace_quality(sig) = (U - F) / (U + F + 1)
        — same formula as E₀ Historization at edge level.
        Range: (-1, 1).  Negative → historically stagnant pattern.

    trace_load(sig) = U + F
        — how many times this pattern has been observed.
        Low load → insufficient evidence to act on.
    """

    def __init__(self) -> None:
        self._traces: Dict[PathSignature, Tuple[int, int]] = {}

    def inscribe(self, record: TrajectoryRecord) -> None:
        """Record one round's outcome for its signature."""
        u, f = self._traces.get(record.signature, (0, 0))
        if record.outcome in ("productive", "improving"):
            self._traces[record.signature] = (u + 1, f)
        else:
            self._traces[record.signature] = (u, f + 1)

    def trace_load(self, sig: PathSignature) -> int:
        """Number of times this signature has been observed (U + F)."""
        u, f = self._traces.get(sig, (0, 0))
        return u + f

    def trace_quality(self, sig: PathSignature) -> float:
        """Quality of this signature: (U - F) / (U + F + 1).

        Returns 0.0 for unseen signatures (no evidence yet).
        """
        u, f = self._traces.get(sig, (0, 0))
        return (u - f) / (u + f + 1)

    def known_signatures(self) -> List[PathSignature]:
        """All signatures that have been observed at least once."""
        return list(self._traces.keys())

    def low_quality_warning(
        self,
        sig: PathSignature,
        quality_threshold: float = -0.3,
        min_load: int = 2,
    ) -> bool:
        """Return True if this signature has been seen enough times
        and its quality is below the threshold.

        Used by plan() to trigger a proactive mode switch.

        Args:
            sig: The signature to check.
            quality_threshold: Quality below which the pattern is
                considered problematic. Default -0.3.
            min_load: Minimum number of observations before acting.
                Default 2 (requires at least 2 data points).
        """
        return (
            self.trace_load(sig) >= min_load
            and self.trace_quality(sig) < quality_threshold
        )
