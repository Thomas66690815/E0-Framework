"""
E₀ Observation Controller (C95)
=================================
Intentional navigation of the O-Landscape + domain projection.

Canon basis:
  "The observer is not outside the system." (Ontodynamics §1)

The ObservationController wraps an O-Landscape and provides explicit
navigation primitives: focus, defocus, deepen, retreat, move.

Each operation is a single admissible step on the O-Landscape.
Historization applies identically: repeated observation lowers
resistance for that transition (the observer learns).

    ctrl = ObservationController(domain_landscape)

    ctrl.deepen()               # topo → field
    ctrl.focus("node_A")        # global → local(node_A)
    ctrl.deepen()               # field → dyn (in local scope)
    data = ctrl.project()       # returns visible domain data

The project() method is a pure projection: it reads the domain
Landscape through the lens of the current observation state.
What depth the observer has reached determines what data is visible.
What scope the observer has determines which nodes are visible.

Design decisions:
  - No autonomous run: the observer declares intent explicitly.
    Autonomous observation exploration is future work (E0Controller.run
    on O-Landscape with a navigation strategy).
  - Historization is per-session: a fresh ObservationController starts
    with no observation history.  Repeated focus on the same node
    lowers R_eff for that transition.
  - project() reads from domain but never mutates it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .landscape import Landscape
from .primitives import Edge, Outcome
from .observation import (
    DEPTHS,
    DEPTH_INDEX,
    build_observation_landscape,
    encode_state,
    decode_state,
    is_global,
    is_local,
    local_node,
    depth_of,
    observation_states,
    info_at,
)


# ── Result of a navigation step ──────────────────────────

@dataclass
class StepResult:
    """Outcome of a single observation navigation step."""
    success: bool
    previous: str
    current: str
    r_eff: float       # R_eff of the transition (inf if inadmissible)
    s_eff: float       # S_eff of the transition (inf if inadmissible)


# ── Observation Controller ────────────────────────────────

class ObservationController:
    """
    Intentional observer navigation on an O-Landscape.

    Provides five navigation primitives:
      focus(node_id)  — global → local(node) at same depth
      defocus()       — local → global at same depth
      move(node_id)   — local(x) → local(y) at same depth (domain neighbors)
      deepen()        — current depth → next deeper (same scope)
      retreat()       — current depth → next shallower (same scope)

    Plus:
      navigate(state_id)  — arbitrary adjacent step
      project()           — read domain through observation lens
    """

    def __init__(
        self,
        domain: Landscape,
        *,
        depths: Optional[List[str]] = None,
    ):
        self.domain = domain
        self.o_landscape = build_observation_landscape(domain, depths=depths)
        self._current = encode_state("g", (depths or list(DEPTHS))[0])
        self._history: List[str] = []

    # ── Properties ────────────────────────────────────────

    @property
    def current(self) -> str:
        """Current observation state ID."""
        return self._current

    @property
    def scope(self) -> str:
        """Current scope: 'g' or 'n:<id>'."""
        return decode_state(self._current)[0]

    @property
    def depth(self) -> str:
        """Current depth level."""
        return decode_state(self._current)[1]

    @property
    def depth_index(self) -> int:
        """Current depth as integer (0=topo, 4=intf)."""
        return DEPTH_INDEX[self.depth]

    @property
    def history(self) -> List[str]:
        """Observation trajectory (visited states)."""
        return list(self._history)

    @property
    def focused_node(self) -> Optional[str]:
        """Node ID if in local scope, else None."""
        return local_node(self._current)

    # ── Internal step mechanism ───────────────────────────

    def _step(self, target: str) -> StepResult:
        """Execute a single observation transition.

        Updates historization on success.
        Returns StepResult with success=False if transition is inadmissible.
        """
        previous = self._current

        if not self.o_landscape.has_edge(previous, target):
            return StepResult(
                success=False,
                previous=previous,
                current=previous,
                r_eff=math.inf,
                s_eff=math.inf,
            )

        r_eff = self.o_landscape.effective_resistance(previous, target)
        s_eff = self.o_landscape.effective_tension(previous, target)

        # Observation transitions always succeed (you can always look).
        edge = Edge(previous, target)
        self.o_landscape.historization.update(edge, Outcome.SUCCESS)

        self._history.append(previous)
        self._current = target

        return StepResult(
            success=True,
            previous=previous,
            current=target,
            r_eff=r_eff,
            s_eff=s_eff,
        )

    # ── Navigation primitives ─────────────────────────────

    def focus(self, node_id: str) -> StepResult:
        """Narrow observation from global to a specific node.

        Only works from global scope (same depth preserved).
        """
        target = encode_state(f"n:{node_id}", self.depth)
        return self._step(target)

    def defocus(self) -> StepResult:
        """Widen observation from local scope to global.

        Returns to global scope at the same depth.
        """
        target = encode_state("g", self.depth)
        return self._step(target)

    def move(self, node_id: str) -> StepResult:
        """Move from one local scope to an adjacent node's scope.

        Only works from local scope, and only to domain-graph neighbors.
        """
        target = encode_state(f"n:{node_id}", self.depth)
        return self._step(target)

    def deepen(self) -> StepResult:
        """Go one depth level deeper in current scope.

        topo → field → dyn → mech → intf
        Fails if already at deepest level.
        """
        idx = self.depth_index
        if idx >= len(DEPTHS) - 1:
            return StepResult(
                success=False,
                previous=self._current,
                current=self._current,
                r_eff=math.inf,
                s_eff=math.inf,
            )
        target = encode_state(self.scope, DEPTHS[idx + 1])
        return self._step(target)

    def retreat(self) -> StepResult:
        """Go one depth level shallower in current scope.

        intf → mech → dyn → field → topo
        Fails if already at shallowest level.
        """
        idx = self.depth_index
        if idx <= 0:
            return StepResult(
                success=False,
                previous=self._current,
                current=self._current,
                r_eff=math.inf,
                s_eff=math.inf,
            )
        target = encode_state(self.scope, DEPTHS[idx - 1])
        return self._step(target)

    def navigate(self, target_state: str) -> StepResult:
        """Navigate to an arbitrary adjacent observation state."""
        return self._step(target_state)

    # ── Observation options ───────────────────────────────

    def options(self) -> List[Dict[str, Any]]:
        """Return available transitions from current state with their costs.

        Each entry has: target, scope_change, depth_change, r_eff, s_eff.
        """
        neighbors = self.o_landscape.admissible_neighbors(self._current)
        cur_scope, cur_depth = decode_state(self._current)
        result = []
        for nb in neighbors:
            nb_scope, nb_depth = decode_state(nb)
            r_eff = self.o_landscape.effective_resistance(self._current, nb)
            s_eff = self.o_landscape.effective_tension(self._current, nb)
            result.append({
                "target": nb,
                "scope_change": nb_scope != cur_scope,
                "depth_change": nb_depth != cur_depth,
                "r_eff": r_eff,
                "s_eff": s_eff,
            })
        return sorted(result, key=lambda x: x["s_eff"])

    # ── Domain projection ─────────────────────────────────

    def project(self) -> Dict[str, Any]:
        """Project domain data through the current observation lens.

        What is visible depends on:
          scope — which nodes/edges
          depth — which data layers

        Depth levels (cumulative):
          topo  — nodes and edges exist (structure only)
          field — scalar field: Δ, R₀, R_eff, S_eff per edge
          dyn   — dynamics: historization traces, trace_load, trace_quality
          mech  — mechanism: (extension point for controller state)
          intf  — interference: (extension point for amplitude overlay)

        Returns a dict; higher depth levels add nested keys.
        """
        scope, depth = decode_state(self._current)
        d_idx = DEPTH_INDEX[depth]

        # ── Determine visible nodes ──
        if scope == "g":
            visible_nodes = sorted(self.domain._states)
        else:
            node = scope[2:]  # n:X → X
            visible_nodes = {node}
            for edge in self.domain._delta:
                if edge.source == node:
                    visible_nodes.add(edge.target)
                if edge.target == node:
                    visible_nodes.add(edge.source)
            visible_nodes = sorted(visible_nodes)

        # ── Determine visible edges ──
        visible_set = set(visible_nodes)
        visible_edges = [
            e for e in self.domain._delta
            if e.source in visible_set and e.target in visible_set
        ]

        # ── Layer 0: Topology ──
        result: Dict[str, Any] = {
            "state": self._current,
            "scope": scope,
            "depth": depth,
            "depth_index": d_idx,
            "nodes": visible_nodes,
            "edges": [
                {"source": e.source, "target": e.target}
                for e in visible_edges
            ],
        }

        # ── Layer 1: Field (Δ, R, S) ──
        if d_idx >= 1:
            field_data = {}
            for e in visible_edges:
                field_data[f"{e.source}→{e.target}"] = {
                    "delta": self.domain.difference(e.source, e.target),
                    "R0": self.domain.base_resistance(e.source, e.target),
                    "R_eff": self.domain.effective_resistance(
                        e.source, e.target,
                    ),
                    "S_eff": self.domain.effective_tension(
                        e.source, e.target,
                    ),
                }
            result["field"] = field_data

        # ── Layer 2: Dynamics (historization traces) ──
        if d_idx >= 2:
            hist = self.domain.historization
            dyn_data: Dict[str, Any] = {}
            for e in visible_edges:
                key = f"{e.source}→{e.target}"
                u = hist.success_trace(e)
                f = hist.failure_trace(e)
                tl = hist.trace_load(e)
                tq = hist.trace_quality(e) if tl > 0 else 0.0
                dyn_data[key] = {
                    "success_trace": u,
                    "failure_trace": f,
                    "trace_load": tl,
                    "trace_quality": tq,
                }
            result["dynamics"] = dyn_data

        # ── Layer 3: Mechanism (extension point) ──
        if d_idx >= 3:
            result["mechanism"] = {}

        # ── Layer 4: Interference (extension point) ──
        if d_idx >= 4:
            result["interference"] = {}

        return result

    # ── Observation meta-info ─────────────────────────────

    def info(self) -> Dict[str, Any]:
        """Describe the current observation state (human-readable)."""
        return info_at(self._current)

    def resistance_to(self, target_state: str) -> float:
        """R_eff for transitioning to a target state (inf if inadmissible)."""
        if not self.o_landscape.has_edge(self._current, target_state):
            return math.inf
        return self.o_landscape.effective_resistance(self._current, target_state)

    def tension_to(self, target_state: str) -> float:
        """S_eff for transitioning to a target state (inf if inadmissible)."""
        if not self.o_landscape.has_edge(self._current, target_state):
            return math.inf
        return self.o_landscape.effective_tension(self._current, target_state)

    def __repr__(self) -> str:
        return f"ObservationController(state={self._current!r})"
