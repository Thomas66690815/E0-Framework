"""
E₀ Curriculum Navigator (C123)
================================
Hierarchical learning for canonical landscapes.

Solves two problems:

1. **Goal redefinition:** Goals are not endpoints but direction-givers.
   The real stopping condition is *equilibrium* — when internal difference
   is exhausted (T_s stays below threshold). The system then waits for
   external difference.

2. **Large landscape learning:** A 51-node canon cannot be meaningfully
   learned in a single run (one greedy path covers ~12% of edges).
   Curriculum learning follows the derivation hierarchy: canonical core
   first, then border concepts, then implementation layer.

Design:

    CurriculumStrategy     — generates turns from derivation levels
    EquilibriumDetector    — detects when T_s is stable below threshold
    build_scoped_landscape — creates a sub-landscape for a turn's scope
    transfer_historization  — carries learned traces into the next turn
    CurriculumRunner       — orchestrates the full curriculum

The curriculum is *cumulative*: each turn includes all nodes from
previous turns plus new ones. Historization persists across turns
via explicit trace transfer.

See E0_ONTODYNAMICS_CANON_ANALYSIS_v1.md §4.6 and §6.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .canon_loader import CanonInfo, CanonLandscape, load_canon_spec, _extract_info, _to_bootstrapper_spec
from .bootstrapper import bootstrap_landscape
from .controller import E0Controller, RunTrace
from .landscape import Landscape
from .primitives import Edge, Outcome
from .structural_entropy import structural_temperature


# ──────────────────────────────────────────────
# 1. Data Structures
# ──────────────────────────────────────────────

@dataclass
class CurriculumTurn:
    """A scoped learning turn within a curriculum."""
    scope: str
    level_max: int
    node_ids: Set[str] = field(default_factory=set)
    goal: Optional[str] = None


@dataclass
class TurnResult:
    """Result of running a single curriculum turn."""
    turn: CurriculumTurn
    traces: List[RunTrace]
    equilibrium_reached: bool
    final_T_s: float
    total_steps: int
    episodes: int


# ──────────────────────────────────────────────
# 2. Equilibrium Detector
# ──────────────────────────────────────────────

class EquilibriumDetector:
    """Detects when a system has exhausted internal difference.

    Monitors structural temperature T_s across episodes.
    When T_s stays below the threshold for `patience` consecutive
    observations, the system is considered at equilibrium —
    no new internal difference is being generated.

    This replaces the traditional "goal reached" stopping condition.
    Equilibrium means: the system has finished with itself and
    is ready for external difference.
    """

    def __init__(self, threshold: float = 1.0, patience: int = 3):
        self._threshold = threshold
        self._patience = patience
        self._below_count: int = 0
        self._observations: List[float] = []

    def observe(self, T_s: float) -> bool:
        """Record a T_s observation. Returns True if equilibrium detected."""
        self._observations.append(T_s)
        if T_s < self._threshold:
            self._below_count += 1
        else:
            self._below_count = 0
        return self._below_count >= self._patience

    def reset(self) -> None:
        """Reset the detector for a new turn."""
        self._below_count = 0
        self._observations.clear()

    @property
    def threshold(self) -> float:
        return self._threshold

    @property
    def patience(self) -> int:
        return self._patience

    @property
    def observations(self) -> List[float]:
        return list(self._observations)

    @property
    def at_equilibrium(self) -> bool:
        return self._below_count >= self._patience


# ──────────────────────────────────────────────
# 3. Curriculum Strategy
# ──────────────────────────────────────────────

class CurriculumStrategy:
    """Generates curriculum turns from a canon's derivation hierarchy.

    Each turn is *cumulative*: it includes all nodes from previous
    turns plus new ones up to level_max. This mirrors the ontodynamic
    derivation order — you can't understand resistance without
    knowing difference first.

    Default boundaries split the derivation levels into thirds.
    Custom boundaries can be provided for fine-grained control.
    """

    def __init__(self, info: CanonInfo,
                 boundaries: Optional[List[int]] = None):
        self._info = info
        self._boundaries = sorted(boundaries) if boundaries else self._auto_boundaries()

    def _auto_boundaries(self) -> List[int]:
        """Split derivation levels into thirds."""
        levels = {n.derivation_level for n in self._info.nodes}
        if not levels:
            return [0]
        max_level = max(levels)
        if max_level <= 2:
            return [max_level]
        third = max_level / 3
        return [int(third), int(2 * third), max_level]

    def turns(self) -> List[CurriculumTurn]:
        """Generate ordered curriculum turns."""
        result = []
        for i, max_level in enumerate(self._boundaries):
            node_ids = {n.id for n in self._info.nodes
                        if n.derivation_level <= max_level}

            # Find the highest-level goal_state within scope
            goal = None
            best_level = -1
            for gs in self._info.goal_states:
                node = next((n for n in self._info.nodes if n.id == gs), None)
                if node and node.derivation_level <= max_level:
                    if node.derivation_level > best_level:
                        goal = gs
                        best_level = node.derivation_level

            scope = f"Turn {i + 1}: levels 0–{max_level}"
            result.append(CurriculumTurn(
                scope=scope,
                level_max=max_level,
                node_ids=node_ids,
                goal=goal,
            ))
        return result

    @property
    def boundaries(self) -> List[int]:
        return list(self._boundaries)

    @property
    def info(self) -> CanonInfo:
        return self._info


# ──────────────────────────────────────────────
# 4. Scoped Landscape Construction
# ──────────────────────────────────────────────

def build_scoped_landscape(spec: Dict[str, Any],
                           node_ids: Set[str]) -> Landscape:
    """Build a Landscape containing only the given nodes.

    Edges are included only if both source and target are in node_ids.
    Uses the same bootstrap pipeline as full canon loading.
    """
    scoped_spec = _scope_spec(spec, node_ids)
    return bootstrap_landscape(scoped_spec)


def _scope_spec(spec: Dict[str, Any], node_ids: Set[str]) -> Dict[str, Any]:
    """Filter a canon spec to only include the given nodes."""
    raw_nodes = spec.get("nodes", [])
    nodes = []
    for n in raw_nodes:
        nid = n["id"] if isinstance(n, dict) else str(n)
        if nid in node_ids:
            nodes.append(nid)

    edges = []
    for e in spec.get("edges", []):
        if e["from"] in node_ids and e["to"] in node_ids:
            edge: Dict[str, Any] = {
                "from": e["from"],
                "to": e["to"],
                "delta": e.get("delta", 0.5),
                "resistance": e.get("resistance", 0.3),
            }
            if "initial_U" in e:
                edge["initial_U"] = e["initial_U"]
            if "initial_F" in e:
                edge["initial_F"] = e["initial_F"]
            if "confidence" in e:
                edge["confidence"] = e["confidence"]
            edges.append(edge)

    return {"nodes": nodes, "edges": edges}


# ──────────────────────────────────────────────
# 5. Historization Transfer
# ──────────────────────────────────────────────

def transfer_historization(source: Landscape, target: Landscape) -> int:
    """Transfer U/F traces from source to target for shared edges.

    Copies the historization state (U, F, tau_last) for every edge
    that exists in both landscapes. Preserves the learning from
    previous curriculum turns.

    Returns the number of edges transferred.
    """
    src_hist = source.historization
    tgt_hist = target.historization
    transferred = 0

    for edge in source.edges:
        if target.has_edge(edge.source, edge.target):
            U = src_hist._U.get(edge, 0.0)
            F = src_hist._F.get(edge, 0.0)
            tau_last = src_hist._tau_last.get(edge, 0)
            if U > 0 or F > 0:
                tgt_hist._U[edge] = U
                tgt_hist._F[edge] = F
                tgt_hist._tau_last[edge] = tgt_hist._tau
                transferred += 1

    return transferred


# ──────────────────────────────────────────────
# 6. Curriculum Runner
# ──────────────────────────────────────────────

class CurriculumRunner:
    """Orchestrates hierarchical learning through curriculum turns.

    For each turn:
    1. Build a scoped landscape (cumulative nodes up to level_max)
    2. Run the controller repeatedly until equilibrium or max_episodes
    3. Transfer historization to the next turn's landscape
    4. Record results

    After all turns: the final landscape contains the full canon
    with historization accumulated from all turns.
    """

    def __init__(self, canon_name: str,
                 execute_fn: Callable,
                 *,
                 strategy: Optional[CurriculumStrategy] = None,
                 equilibrium_threshold: float = 1.0,
                 equilibrium_patience: int = 3,
                 max_episodes_per_turn: int = 20,
                 max_cycles_per_episode: int = 50):
        self._spec = load_canon_spec(canon_name)
        self._info = _extract_info(self._spec)
        self._execute_fn = execute_fn
        self._strategy = strategy or CurriculumStrategy(self._info)
        self._detector = EquilibriumDetector(
            threshold=equilibrium_threshold,
            patience=equilibrium_patience,
        )
        self._max_episodes = max_episodes_per_turn
        self._max_cycles = max_cycles_per_episode
        self._results: List[TurnResult] = []
        self._final_landscape: Optional[Landscape] = None

    def run(self) -> List[TurnResult]:
        """Execute the full curriculum. Returns results per turn."""
        turns = self._strategy.turns()
        prev_landscape: Optional[Landscape] = None

        for turn in turns:
            landscape = build_scoped_landscape(self._spec, turn.node_ids)

            # Transfer historization from previous turn
            if prev_landscape is not None:
                transfer_historization(prev_landscape, landscape)

            result = self._run_turn(turn, landscape)
            self._results.append(result)
            prev_landscape = landscape

        self._final_landscape = prev_landscape
        return list(self._results)

    def _run_turn(self, turn: CurriculumTurn,
                  landscape: Landscape) -> TurnResult:
        """Run a single curriculum turn until equilibrium or max episodes."""
        self._detector.reset()
        ctrl = E0Controller(landscape, self._execute_fn,
                            inscription_threshold=True)

        traces: List[RunTrace] = []
        total_steps = 0
        start = self._pick_start(turn, landscape)
        equilibrium = False

        for ep in range(self._max_episodes):
            trace = ctrl.run(start, max_cycles=self._max_cycles,
                             goal=turn.goal)
            traces.append(trace)
            total_steps += len(trace.steps)

            T_s = structural_temperature(landscape.historization)
            if self._detector.observe(T_s):
                equilibrium = True
                break

            # Next episode starts from where we ended
            if trace.steps:
                start = trace.steps[-1].target

        return TurnResult(
            turn=turn,
            traces=traces,
            equilibrium_reached=equilibrium,
            final_T_s=structural_temperature(landscape.historization),
            total_steps=total_steps,
            episodes=len(traces),
        )

    def _pick_start(self, turn: CurriculumTurn,
                    landscape: Landscape) -> str:
        """Pick a start node for a turn.

        Prefers the lowest-level node in the turn's scope.
        """
        nodes_by_level = []
        for n in self._info.nodes:
            if n.id in turn.node_ids:
                nodes_by_level.append((n.derivation_level, n.id))
        nodes_by_level.sort()
        return nodes_by_level[0][1] if nodes_by_level else next(iter(turn.node_ids))

    @property
    def results(self) -> List[TurnResult]:
        return list(self._results)

    @property
    def final_landscape(self) -> Optional[Landscape]:
        return self._final_landscape

    @property
    def info(self) -> CanonInfo:
        return self._info

    def summary(self) -> str:
        """Human-readable summary of the curriculum run."""
        lines = [f"Curriculum: {self._info.name} v{self._info.version}"]
        lines.append(f"Turns: {len(self._results)}")
        lines.append("")
        for r in self._results:
            eq = "✓ equilibrium" if r.equilibrium_reached else "✗ max episodes"
            lines.append(
                f"  {r.turn.scope}: {r.episodes} episodes, "
                f"{r.total_steps} steps, T_s={r.final_T_s:.2f}, {eq}"
            )
        return "\n".join(lines)
