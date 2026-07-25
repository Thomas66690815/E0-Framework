"""
structural_geometry.overlay — the influence map you actually call.
===================================================================

For an agent standing at ``current``, score every next move by the
interfering support of the bounded family of paths that begins with it:

    Ψ(a; h) = Σ_{p: current → a → …, |p| ≤ h} Ψ(p)
    I(a; h) = |Ψ(a; h)|²
    P(a; h) = I(a) / Σ I

``I(a)`` is a complex-valued influence map over next moves.  Unlike the
usual real-valued one, a move whose continuations mostly loop back or dead
end has its own contributions cancel, so it scores *low* even though it has
many paths.

Two rankings, and when to trust the second
------------------------------------------
``report.greedy`` is the cheapest immediate edge.  ``report.best`` is the
move with the strongest forward support.  They usually agree.  When they
disagree, the interference view has seen something at depth that the single
edge cannot show — but it is also where interference can be wrong.

:meth:`InfluenceReport.should_override` encodes the empirically validated
gate.  In the parent framework's 1000-tick congestion study, overriding
greedy on *every* disagreement made throughput worse than not overriding at
all; overriding only on high-confidence disagreements made it the best of
six strategies.  The defaults here (``min_confidence=0.85``,
``max_imbalance=3.0``) are those validated values.  Lower them and you will
reproduce the failure, not a speedup.

Summation geometries
--------------------
``"simple"``          no repeated nodes.  Suppresses loop inflation.  Default.
``"prefix"``          every admissible prefix.  Maximal support, loop-prone.
``"first_arrival"``   stop extending once a goal is reached.
``"goal_reaching"``   keep only paths that *end* at a goal.

# e0-structural-geometry-twehner
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field as _dc_field
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Set

from .amplitude import psi, sum_paths
from .field import NavField

__all__ = [
    "GEOMETRIES",
    "DEFAULT_MAX_PATHS",
    "ActionSupport",
    "InfluenceReport",
    "enumerate_continuations",
    "influence_map",
]

GEOMETRIES = ("simple", "prefix", "first_arrival", "goal_reaching")

#: Safety valve for path enumeration. Dense branching grows as O(b^h);
#: past this many paths enumeration stops and the report says so.
DEFAULT_MAX_PATHS = 20_000


@dataclass
class ActionSupport:
    """Interference support for one candidate next move."""

    action: str
    cost: float
    path_count: int
    psi_total: complex
    intensity: float
    probability: float = 0.0
    paths: List[List[str]] = _dc_field(default_factory=list)


@dataclass
class InfluenceReport:
    """Result of :func:`influence_map` for one decision point."""

    current: str
    horizon: int
    geometry: str
    actions: List[ActionSupport]
    truncated: bool = False

    @property
    def best(self) -> Optional[str]:
        """Move with the strongest interfering forward support."""
        if not self.actions:
            return None
        return max(self.actions, key=lambda a: a.intensity).action

    @property
    def greedy(self) -> Optional[str]:
        """Cheapest immediate edge — the one-step baseline."""
        if not self.actions:
            return None
        return min(self.actions, key=lambda a: a.cost).action

    @property
    def disagrees(self) -> bool:
        """True when interference and the one-step baseline point elsewhere."""
        b, g = self.best, self.greedy
        return b is not None and g is not None and b != g

    @property
    def confidence(self) -> float:
        """``P_best − P_second`` ∈ [0, 1]. Zero when tied or single-candidate."""
        probs = sorted((a.probability for a in self.actions), reverse=True)
        if len(probs) < 2:
            return 0.0
        return probs[0] - probs[1]

    @property
    def path_imbalance(self) -> float:
        """``max(path_count) / min(path_count)`` over candidates with paths.

        Above ~3 the intensity ranking is materially biased by how many
        continuations each move happens to have, rather than by their
        quality.  This is the known failure mode of amplitude summation;
        it is surfaced rather than hidden.
        """
        counts = [a.path_count for a in self.actions if a.path_count > 0]
        if len(counts) < 2:
            return 1.0
        return max(counts) / min(counts)

    def should_override(
        self,
        *,
        min_confidence: float = 0.85,
        max_imbalance: float = 3.0,
    ) -> bool:
        """Whether to follow :attr:`best` instead of :attr:`greedy`.

        Returns ``True`` only when the two disagree, the probability gap
        clears ``min_confidence``, and the path counts are balanced enough
        that the gap is not an artefact of enumeration.

        These defaults are the validated conservative gate.  See the module
        docstring before changing them.
        """
        if not self.disagrees:
            return False
        if self.path_imbalance > max_imbalance:
            return False
        return self.confidence >= min_confidence

    def decide(self, **gate: float) -> Optional[str]:
        """The move to actually take: :attr:`best` if the gate passes, else :attr:`greedy`."""
        return self.best if self.should_override(**gate) else self.greedy

    def summary(self) -> str:
        lines = [
            f"InfluenceReport(current={self.current!r}, horizon={self.horizon}, "
            f"geometry={self.geometry!r})",
            f"  greedy={self.greedy!r}  best={self.best!r}  "
            f"confidence={self.confidence:.3f}  imbalance={self.path_imbalance:.2f}",
            f"  override={self.should_override()}  decide={self.decide()!r}"
            + ("  [TRUNCATED]" if self.truncated else ""),
        ]
        for a in sorted(self.actions, key=lambda x: x.intensity, reverse=True):
            lines.append(
                f"    {a.action}: I={a.intensity:.6f} P={a.probability:.4f} "
                f"paths={a.path_count} cost={a.cost:.4f}"
            )
        return "\n".join(lines)


def enumerate_continuations(
    field: NavField,
    current: str,
    horizon: int,
    *,
    geometry: str = "simple",
    goals: Optional[Iterable[str]] = None,
    max_paths: int = DEFAULT_MAX_PATHS,
) -> tuple:
    """Bounded forward path family from ``current``.

    Returns ``(paths, truncated)`` where ``paths`` is a list of node lists,
    each starting at ``current``, and ``truncated`` says whether the
    ``max_paths`` cap was hit.  A truncated enumeration is still usable but
    its intensities are no longer comparable across moves — the report
    propagates the flag so you can refuse to act on it.
    """
    if horizon <= 0:
        return [], False
    if geometry not in GEOMETRIES:
        raise ValueError(f"unknown geometry {geometry!r}; must be one of {GEOMETRIES}")
    goal_set: Set[str] = set(goals or ())
    if geometry in ("first_arrival", "goal_reaching") and not goal_set:
        raise ValueError(f"{geometry} geometry requires a non-empty goals set")

    results: List[List[str]] = []
    truncated = False

    def walk(path: List[str], depth: int) -> None:
        nonlocal truncated
        if truncated or depth >= horizon:
            return
        x = path[-1]
        if geometry in ("first_arrival", "goal_reaching") and depth > 0 and x in goal_set:
            return
        for y in field.neighbors(x):
            if geometry == "simple" and y in path:
                continue
            nxt = path + [y]
            if geometry == "goal_reaching":
                if y in goal_set:
                    results.append(nxt)
            else:
                results.append(nxt)
            if len(results) >= max_paths:
                truncated = True
                return
            walk(nxt, depth + 1)
            if truncated:
                return

    walk([current], 0)
    return results, truncated


def influence_map(
    field: NavField,
    current: str,
    *,
    horizon: int = 3,
    geometry: str = "simple",
    goals: Optional[Iterable[str]] = None,
    candidates: Optional[Sequence[str]] = None,
    max_paths: int = DEFAULT_MAX_PATHS,
    modifier: Optional[Callable[[str, float], float]] = None,
    keep_paths: bool = False,
) -> InfluenceReport:
    """Score every next move from ``current`` by interfering path support.

    Parameters
    ----------
    horizon:
        Maximum path length in hops. 2–4 is the useful range; cost grows as
        O(branching^horizon).
    candidates:
        Restrict scoring to these moves. Defaults to all out-neighbours.
    modifier:
        Optional ``(action, intensity) → intensity`` hook applied before
        normalisation, for domain boosts.
    keep_paths:
        Retain the enumerated paths on each :class:`ActionSupport`. Off by
        default — they are large and only useful for debugging.
    """
    if horizon < 1:
        raise ValueError("horizon must be >= 1")

    goal_set: Set[str] = set(goals or ())
    moves = list(candidates) if candidates is not None else field.neighbors(current)

    all_paths, truncated = enumerate_continuations(
        field, current, horizon, geometry=geometry, goals=goal_set, max_paths=max_paths
    )

    by_first: Dict[str, List[List[str]]] = {m: [] for m in moves}
    for p in all_paths:
        if len(p) >= 2:
            bucket = by_first.get(p[1])
            if bucket is not None:
                bucket.append(p)

    supports: List[ActionSupport] = []
    total = 0.0
    for m in moves:
        paths = by_first[m]
        # The direct one-hop path always belongs to the family, unless
        # goal_reaching explicitly excludes non-goal endpoints.
        direct = [current, m]
        if direct not in paths:
            if geometry != "goal_reaching" or m in goal_set:
                paths = [direct] + paths

        total_psi = sum_paths(field, paths)
        i = abs(total_psi) ** 2
        supports.append(
            ActionSupport(
                action=m,
                cost=field.cost(current, m),
                path_count=len(paths),
                psi_total=total_psi,
                intensity=i,
                paths=[list(p) for p in paths] if keep_paths else [],
            )
        )
        total += i

    if modifier is not None:
        total = 0.0
        for s in supports:
            s.intensity = modifier(s.action, s.intensity)
            total += s.intensity

    if total > 0.0:
        for s in supports:
            s.probability = s.intensity / total

    supports.sort(key=lambda s: (-s.intensity, s.action))

    return InfluenceReport(
        current=current,
        horizon=horizon,
        geometry=geometry,
        actions=supports,
        truncated=truncated,
    )
