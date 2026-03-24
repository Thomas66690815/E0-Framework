"""
Ontodynamics — Admissibility Layer
===================================
Implements the pre-physical constraints from:
  "Ontodynamics – A Minimal Pre-Physical Canon"

This is the DEEPEST layer — it sits BELOW E₀.
While E₀ says WHEN transitions are enforced,
Ontodynamics constrains WHICH transitions are realizable at all.

Ontodynamics primitives:
  1. Difference    — effective, directed, scaled (more fundamental than State)
  2. Connection    — elementary topological operation
  3. Overlap       — graduated degree of connection
  4. Locality      — realization is necessarily partial/local
  5. Historization — realized connections leave irreversible trace

Key insight: In Ontodynamics, State and Resistance are DERIVED,
not primitive. States emerge from stabilized difference.
This layer constrains E₀ silently — it is never a "module",
but an admissibility envelope.

In LLM terms:
  - Ontodynamics = the constraints that make a weight matrix trainable at all
  - Connection topology = which neurons CAN connect (architecture)
  - Overlap = shared representations across layers/heads
  - Locality = finite receptive fields, bounded attention
  - The reason a transformer works is not its design —
    it's that the design accidentally satisfies ontodynamic admissibility
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from .primitives import State, Path, Historization, HistorizationEvent, difference


# ─────────────────────────────────────────────
# 3.1  Difference (ontodynamic: primitive, directed, scaled)
# ─────────────────────────────────────────────

@dataclass
class DirectedDifference:
    """
    Ontodynamic Difference — more primitive than E₀'s Δ.

    Properties (from canon):
      - Primitive: not derived from non-identity
      - Effective: if difference exists, stability is not neutral
      - Directed: not symmetric or inert
      - Scaled: admits degrees, not binary

    E₀'s symmetric Δ(s1,s2) is a REDUCTION of this.
    Ontodynamic difference has direction: from → toward.

    In LLM terms: the gradient vector — it's not just a magnitude,
    it has direction showing WHERE the loss landscape pushes.
    """
    source: State
    target: State

    @property
    def magnitude(self) -> float:
        """Scaled measure of difference (≥ 0)."""
        return difference(self.source, self.target)

    @property
    def direction(self) -> List[float]:
        """Direction vector from source toward target (unnormalized)."""
        return [t - s for s, t in zip(self.source.vector, self.target.vector)]

    @property
    def is_effective(self) -> bool:
        """If difference exists, stability is not neutral."""
        return self.magnitude > 0

    def __repr__(self) -> str:
        return f"DirectedΔ({self.source.id}→{self.target.id} | |Δ|={self.magnitude:.4f})"


# ─────────────────────────────────────────────
# 3.3  Connection — elementary topological operation
# ─────────────────────────────────────────────

@dataclass
class Connection:
    """
    The elementary topological operation.

    Properties (from canon):
      - Precedes separation
      - Not spatial, causal, or relational between pre-existing entities
      - Means: multiple difference components are realized TOGETHER

    In LLM terms: a weight connecting two neurons — the fact that
    information CAN flow. The architecture defines what connections
    are possible; training determines their strength.
    """
    node_a: str  # abstract identifiers — not "entities"
    node_b: str
    overlap: float = 0.0  # graduated degree [0, 1]
    historized: bool = False

    @property
    def is_stable(self) -> bool:
        """Stability requires non-zero overlap (§3.4)."""
        return self.overlap > 0

    @property
    def pair(self) -> FrozenSet[str]:
        return frozenset({self.node_a, self.node_b})

    def __repr__(self) -> str:
        h = "H" if self.historized else "·"
        return f"Conn({self.node_a}↔{self.node_b} | overlap={self.overlap:.3f} {h})"


# ─────────────────────────────────────────────
# 3.4  Topology — the realized connection structure
# ─────────────────────────────────────────────

class Topology:
    """
    The realized connection structure of the state space.

    This is the ontodynamic 'substrate' that E₀ operates on.
    Not all conceivable transitions are topologically connected —
    only those with realized connections can become E₀ paths.

    In LLM terms: the architecture graph.
    - Transformer layers define topology
    - Attention heads define local connection patterns
    - Skip connections create non-local topology
    - Pruned weights = severed connections
    """

    def __init__(self):
        self._connections: Dict[FrozenSet[str], Connection] = {}

    def connect(self, a: str, b: str, overlap: float = 0.1) -> Connection:
        """Create or strengthen a connection."""
        pair = frozenset({a, b})
        if pair in self._connections:
            conn = self._connections[pair]
            # Overlap can grow, never shrink (historization is irreversible)
            conn.overlap = max(conn.overlap, overlap)
            return conn
        conn = Connection(node_a=a, node_b=b, overlap=overlap)
        self._connections[pair] = conn
        return conn

    def get_connection(self, a: str, b: str) -> Optional[Connection]:
        return self._connections.get(frozenset({a, b}))

    def overlap_between(self, a: str, b: str) -> float:
        conn = self.get_connection(a, b)
        return conn.overlap if conn else 0.0

    def neighbors(self, node: str) -> List[str]:
        """All nodes connected to this one (with non-zero overlap)."""
        result = []
        for pair, conn in self._connections.items():
            if node in pair and conn.is_stable:
                others = [n for n in pair if n != node]
                if others:
                    result.append(others[0])
        return result

    def is_connected(self, a: str, b: str) -> bool:
        """Is there a topological path (possibly multi-hop) between a and b?"""
        if a == b:
            return True
        visited: Set[str] = set()
        queue = [a]
        while queue:
            current = queue.pop(0)
            if current == b:
                return True
            visited.add(current)
            for neighbor in self.neighbors(current):
                if neighbor not in visited:
                    queue.append(neighbor)
        return False

    def historize_connection(self, a: str, b: str) -> None:
        """Mark a connection as historized (irreversible structural trace)."""
        conn = self.get_connection(a, b)
        if conn:
            conn.historized = True

    @property
    def all_connections(self) -> List[Connection]:
        return list(self._connections.values())

    @property
    def historized_connections(self) -> List[Connection]:
        return [c for c in self._connections.values() if c.historized]

    def structural_integrity(self) -> float:
        """
        Measure of overall topological coherence.
        Ratio of historized overlap to total possible connections.
        If this drops, the system is losing structure.
        """
        if not self._connections:
            return 0.0
        total_overlap = sum(c.overlap for c in self._connections.values())
        historized_overlap = sum(
            c.overlap for c in self._connections.values() if c.historized
        )
        return historized_overlap / total_overlap if total_overlap > 0 else 0.0

    def __repr__(self) -> str:
        n_conn = len(self._connections)
        n_hist = len(self.historized_connections)
        return f"Topology(connections={n_conn} | historized={n_hist})"


# ─────────────────────────────────────────────
# Admissibility Constraints
# ─────────────────────────────────────────────

class OntodynamicAdmissibility:
    """
    The silent constraint layer.

    Determines which E₀ transitions are ontodynamically REALIZABLE.
    A transition may satisfy Axiom A₀ (Δ > 0, R < ∞) but still be
    inadmissible if it violates ontodynamic constraints:

      1. Locality:     Transition must be local (bounded scope)
      2. Connection:   Source and target must be topologically connected
      3. Overlap:      Sufficient graduated overlap must exist
      4. Integration:  Transition must be integrable into historized structure

    In LLM terms:
      - Locality = finite attention window / context length
      - Connection = architectural connectivity (can this layer see that layer?)
      - Overlap = shared representation space (embedding alignment)
      - Integration = coherence constraint (new token must fit context)
    """

    def __init__(
        self,
        topology: Topology,
        locality_radius: float = 5.0,
        min_overlap: float = 0.01,
        max_integrity_loss: float = 0.3,
    ):
        self.topology = topology
        self.locality_radius = locality_radius
        self.min_overlap = min_overlap
        self.max_integrity_loss = max_integrity_loss

    def check_locality(self, source: State, target: State) -> bool:
        """
        §3.2: Realization is necessarily LOCAL with respect to scale.

        A transition spanning too large a Δ without intermediate
        steps violates locality. This prevents 'teleportation'
        in the state space.

        In LLM terms: you can't jump from token 1 to a completely
        unrelated token 1000 — the attention window is finite.
        """
        delta = difference(source, target)
        return delta <= self.locality_radius

    def check_connection(self, source: State, target: State) -> bool:
        """
        §3.3: Source and target must be topologically connected.

        Without connection, realization is impossible —
        there is no structure, only possibility.

        In LLM terms: if two neurons have no weight path between them,
        no information can flow, regardless of how large Δ is.
        """
        return self.topology.is_connected(source.id, target.id)

    def check_overlap(self, source: State, target: State) -> bool:
        """
        §3.4: Connections must have sufficient graduated overlap.

        Zero overlap = no stability = transition cannot persist.

        In LLM terms: the embeddings must share enough representational
        space. 'Cat' can transition to 'sat' because they share context;
        'cat' cannot transition to 'π' because overlap ≈ 0.
        """
        overlap = self.topology.overlap_between(source.id, target.id)
        return overlap >= self.min_overlap

    def check_integrability(
        self, path: Path, history: Historization
    ) -> bool:
        """
        A transition is inadmissible if it would collapse or destroy
        a significant portion of historized structure.

        From E₀-AGI §9: "A transition is structurally inadmissible if it
        collapses partial realization into global replacement" or
        "cannot be integrated into existing historized structure."

        In LLM terms: catastrophic forgetting — a weight update that
        destroys previously learned representations is structurally
        inadmissible. Fine-tuning must be integrable.
        """
        if history.tau == 0:
            return True  # No history to violate

        integrity_before = self.topology.structural_integrity()
        # Simulate: would this transition reduce integrity too much?
        # (We estimate based on whether the path touches historized connections)
        conn = self.topology.get_connection(path.source.id, path.target.id)
        if conn and conn.historized:
            return True  # Reinforcing existing structure is always integrable

        # New paths that don't connect to historized structure risk fragmentation
        source_neighbors = set(self.topology.neighbors(path.source.id))
        target_neighbors = set(self.topology.neighbors(path.target.id))
        shared_neighborhood = source_neighbors & target_neighbors

        if not shared_neighborhood and integrity_before > 0.5:
            # Isolated transition in a well-historized space = risky
            return False

        return True

    def is_admissible(
        self, path: Path, history: Historization
    ) -> Tuple[bool, List[str]]:
        """
        Full admissibility check. Returns (admissible, [reasons_if_not]).

        This is the silent ontodynamic envelope that constrains E₀.
        """
        violations: List[str] = []

        if not self.check_locality(path.source, path.target):
            violations.append(
                f"LOCALITY: Δ={difference(path.source, path.target):.3f} "
                f"exceeds radius {self.locality_radius}"
            )

        if not self.check_connection(path.source, path.target):
            violations.append(
                f"CONNECTION: {path.source.id} ↔ {path.target.id} "
                f"not topologically connected"
            )

        if not self.check_overlap(path.source, path.target):
            overlap = self.topology.overlap_between(path.source.id, path.target.id)
            violations.append(
                f"OVERLAP: {overlap:.4f} < minimum {self.min_overlap}"
            )

        if not self.check_integrability(path, history):
            violations.append(
                f"INTEGRABILITY: transition would fragment historized structure"
            )

        return (len(violations) == 0, violations)

    def __repr__(self) -> str:
        return (
            f"OntodynamicAdmissibility("
            f"locality_r={self.locality_radius} | "
            f"min_overlap={self.min_overlap} | "
            f"topology={self.topology})"
        )
