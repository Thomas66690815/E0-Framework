"""
structural_geometry.field — the navigation field.
==================================================

A directed graph whose edges carry two numbers:

    weight(u→v)  — how much "difference" the edge spans.  In a navigation
                   graph this is typically distance, or 1.0 if you only
                   care about topology.  (E₀: Δ)
    cost(u→v)    — traversal cost right now.  This is the dynamic part:
                   plug in congestion, danger, terrain, learned reliability,
                   anything.  Higher = worse.  (E₀: S_eff = Δ · R_eff)

From these one derived quantity is used everywhere downstream:

    flow(u→v) = weight(u→v) · exp(−cost(u→v))          (E₀: transition field v)

``exp(−cost)`` maps cost ∈ [0, ∞) to coherence ∈ (0, 1].  A cheap edge
carries almost all of its weight as flow; an expensive edge carries almost
none.  Missing edges have zero flow — they are not "cost ∞", they are
simply absent from the field.

This is the only state the geometry layer needs.  It holds no history, no
learning, no agents.  Point ``cost`` at whatever your simulation already
computes and the rest of the package works.

# e0-structural-geometry-twehner
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, Iterator, List, NamedTuple, Optional, Set, Tuple

__all__ = ["Edge", "NavField"]


class Edge(NamedTuple):
    """A directed edge. Hashable, comparable, cheap."""

    source: str
    target: str

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"{self.source}→{self.target}"


class NavField:
    """Directed graph with per-edge ``weight`` and ``cost``.

    Example
    -------
    >>> f = NavField()
    >>> f.add_edge("A", "B", cost=0.5)
    >>> f.add_edge("B", "C", cost=0.5)
    >>> round(f.flow("A", "B"), 6)
    0.606531
    >>> f.neighbors("A")
    ['B']
    """

    __slots__ = ("_nodes", "_weight", "_cost", "_out", "_in", "_token", "_cache")

    def __init__(self) -> None:
        self._nodes: Set[str] = set()
        self._weight: Dict[Edge, float] = {}
        self._cost: Dict[Edge, float] = {}
        self._out: Dict[str, List[str]] = {}
        self._in: Dict[str, List[str]] = {}
        self._token: int = 0
        self._cache: Dict[str, object] = {}

    # ── construction ────────────────────────────────────────────────

    def add_node(self, name: str) -> None:
        """Register an isolated node."""
        if name not in self._nodes:
            self._nodes.add(name)
            self._out.setdefault(name, [])
            self._in.setdefault(name, [])
            self._invalidate()

    def add_edge(
        self,
        source: str,
        target: str,
        *,
        cost: float = 1.0,
        weight: float = 1.0,
    ) -> None:
        """Add (or overwrite) a directed edge.

        Both endpoints are auto-registered.  ``cost`` must be finite and
        ``≥ 0``; ``weight`` must be ``≥ 0``.
        """
        if weight < 0:
            raise ValueError(f"weight must be >= 0, got {weight}")
        if cost < 0 or math.isinf(cost) or math.isnan(cost):
            raise ValueError(f"cost must be finite and >= 0, got {cost}")
        self.add_node(source)
        self.add_node(target)
        e = Edge(source, target)
        if e not in self._weight:
            self._out[source].append(target)
            self._in[target].append(source)
        self._weight[e] = float(weight)
        self._cost[e] = float(cost)
        self._invalidate()

    def remove_edge(self, source: str, target: str) -> None:
        """Remove a directed edge. Raises ``KeyError`` if absent."""
        e = Edge(source, target)
        if e not in self._weight:
            raise KeyError(f"edge {source}->{target} does not exist")
        del self._weight[e]
        del self._cost[e]
        self._out[source].remove(target)
        self._in[target].remove(source)
        self._invalidate()

    def set_cost(self, source: str, target: str, cost: float) -> None:
        """Update an existing edge's cost. This is the hot path."""
        e = Edge(source, target)
        if e not in self._cost:
            raise KeyError(f"edge {source}->{target} does not exist")
        if cost < 0 or math.isinf(cost) or math.isnan(cost):
            raise ValueError(f"cost must be finite and >= 0, got {cost}")
        self._cost[e] = float(cost)
        self._invalidate()

    def update_costs(self, costs: Dict[Tuple[str, str], float]) -> None:
        """Bulk cost update — one cache invalidation for the whole batch."""
        for (u, v), c in costs.items():
            e = Edge(u, v)
            if e not in self._cost:
                raise KeyError(f"edge {u}->{v} does not exist")
            if c < 0 or math.isinf(c) or math.isnan(c):
                raise ValueError(f"cost must be finite and >= 0, got {c}")
            self._cost[e] = float(c)
        self._invalidate()

    # ── queries ─────────────────────────────────────────────────────

    def has_edge(self, source: str, target: str) -> bool:
        return Edge(source, target) in self._weight

    def weight(self, source: str, target: str) -> float:
        """``weight(u→v)``, or ``0.0`` if the edge does not exist."""
        return self._weight.get(Edge(source, target), 0.0)

    def cost(self, source: str, target: str) -> float:
        """``cost(u→v)``, or ``inf`` if the edge does not exist."""
        return self._cost.get(Edge(source, target), math.inf)

    def flow(self, source: str, target: str) -> float:
        """``flow(u→v) = weight · exp(−cost)``. ``0.0`` for missing edges."""
        e = Edge(source, target)
        c = self._cost.get(e)
        if c is None:
            return 0.0
        return self._weight[e] * math.exp(-c)

    def path_cost(self, path: Iterable[str]) -> float:
        """``Σ cost`` along a node sequence. ``inf`` if any hop is missing."""
        nodes = list(path)
        total = 0.0
        for i in range(len(nodes) - 1):
            c = self._cost.get(Edge(nodes[i], nodes[i + 1]))
            if c is None:
                return math.inf
            total += c
        return total

    def neighbors(self, node: str) -> List[str]:
        """Outgoing neighbours, insertion-ordered."""
        return list(self._out.get(node, ()))

    def predecessors(self, node: str) -> List[str]:
        """Incoming neighbours, insertion-ordered."""
        return list(self._in.get(node, ()))

    @property
    def nodes(self) -> Set[str]:
        return set(self._nodes)

    @property
    def edges(self) -> List[Edge]:
        return list(self._weight.keys())

    def node_count(self) -> int:
        return len(self._nodes)

    def edge_count(self) -> int:
        return len(self._weight)

    def components(self) -> List[List[str]]:
        """Weakly connected components, each sorted, outer list sorted.

        Deterministic: identical graphs always yield identical output.
        """
        seen: Set[str] = set()
        out: List[List[str]] = []
        for start in sorted(self._nodes):
            if start in seen:
                continue
            stack = [start]
            seen.add(start)
            comp = []
            while stack:
                x = stack.pop()
                comp.append(x)
                for y in self._out.get(x, ()):
                    if y not in seen:
                        seen.add(y)
                        stack.append(y)
                for y in self._in.get(x, ()):
                    if y not in seen:
                        seen.add(y)
                        stack.append(y)
            out.append(sorted(comp))
        out.sort()
        return out

    # ── cache plumbing (used by helmholtz/connection) ───────────────

    def _invalidate(self) -> None:
        self._token += 1
        self._cache.clear()

    @property
    def token(self) -> int:
        """Monotonic revision counter — bumps on every structural change."""
        return self._token

    def cache_get(self, key: str) -> Optional[object]:
        return self._cache.get(key)

    def cache_put(self, key: str, value: object) -> None:
        self._cache[key] = value

    # ── serialization ───────────────────────────────────────────────

    def to_dict(self) -> dict:
        """JSON-safe snapshot."""
        return {
            "nodes": sorted(self._nodes),
            "edges": [
                {
                    "source": e.source,
                    "target": e.target,
                    "weight": self._weight[e],
                    "cost": self._cost[e],
                }
                for e in sorted(self._weight, key=lambda x: (x.source, x.target))
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NavField":
        f = cls()
        for n in data.get("nodes", ()):
            f.add_node(n)
        for e in data.get("edges", ()):
            f.add_edge(
                e["source"],
                e["target"],
                cost=e.get("cost", 1.0),
                weight=e.get("weight", 1.0),
            )
        return f

    def __iter__(self) -> Iterator[Edge]:
        return iter(self._weight.keys())

    def __repr__(self) -> str:  # pragma: no cover - display only
        return f"NavField(nodes={len(self._nodes)}, edges={len(self._weight)})"
