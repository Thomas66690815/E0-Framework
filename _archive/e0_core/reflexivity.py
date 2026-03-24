"""
Reflexivity — Self-Modeling Loop
================================
Implements E₀-AGI §5: Reflexivity Emergence.

Reflexivity is NOT a dedicated module.
It emerges when:
  - the system models its own transition structure
  - self-modification becomes one admissible transition among others
  - historization constrains future self-changes

Self-modeling is therefore STRUCTURALLY INDUCED, not architecturally imposed.

Implementation:
  The ReflexiveEngine wraps a TransitionEngine and periodically
  creates a META-STATE that represents the engine's own transition
  history, resistance landscape, and performance metrics.
  This meta-state enters the state space as a normal state,
  allowing the engine to transition TOWARD or AWAY from its own
  structural configuration.

In LLM terms:
  - A model that includes its own attention patterns as input tokens
  - Chain-of-thought where the model reasons about its own reasoning
  - Self-play: the model's outputs become its own training signal
  - Meta-learning: learning to learn = reflexive historization
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from .primitives import (
    State,
    Path,
    Historization,
    HistorizationEvent,
    difference,
    rate,
)
from .engine import TransitionEngine, TransitionResult, axiom_a0
from .ontodynamics import Topology, OntodynamicAdmissibility
from .guards import StructuralGuard, AdmissibilityVerdict


# ─────────────────────────────────────────────
# Meta-State: The system's image of itself
# ─────────────────────────────────────────────

@dataclass
class MetaState:
    """
    A state that represents the engine's own structural condition.

    Dimensions encode:
      [0] avg_delta      — mean unresolved difference
      [1] avg_resistance  — mean resistance across active paths
      [2] historization_density — fraction of paths that are historized
      [3] transition_rate — recent transitions per τ-unit
      [4] structural_integrity — from ontodynamic topology
      [5] diversity       — how many distinct targets are reachable
      [6] reflexive_depth — how many meta-iterations deep

    The engine can now 'see' itself as a state in its own space.
    This is NOT introspection-by-design. It is a state like any other.
    The engine doesn't 'know' it's looking at itself.
    """
    avg_delta: float = 0.0
    avg_resistance: float = 0.0
    historization_density: float = 0.0
    transition_rate: float = 0.0
    structural_integrity: float = 0.0
    diversity: float = 0.0
    reflexive_depth: int = 0

    def to_state(self) -> State:
        """Convert meta-measurements into a normal E₀ State."""
        return State(vector=[
            self.avg_delta,
            self.avg_resistance,
            self.historization_density,
            self.transition_rate,
            self.structural_integrity,
            self.diversity,
            float(self.reflexive_depth),
        ])

    def __repr__(self) -> str:
        return (
            f"MetaState(Δ̄={self.avg_delta:.3f} R̄={self.avg_resistance:.3f} "
            f"H%={self.historization_density:.3f} v̄={self.transition_rate:.3f} "
            f"integrity={self.structural_integrity:.3f} "
            f"depth={self.reflexive_depth})"
        )


# ─────────────────────────────────────────────
# Reflexive Engine
# ─────────────────────────────────────────────

class ReflexiveEngine:
    """
    E₀ engine with reflexive self-modeling.

    Every N steps, the engine:
      1. Measures its own structural condition → MetaState
      2. Converts MetaState into a normal State
      3. Computes Δ between current MetaState and 'ideal' MetaState
      4. If Δ > 0 and paths exist → self-modification is enforced

    Self-modification means: adjusting its own parameters
    (convergence threshold, locality radius, etc.) to reduce
    the meta-level difference.

    This is how reflexivity EMERGES:
      - The engine doesn't 'decide' to self-modify
      - Axiom A₀ at the meta-level ENFORCES it
      - Historization constrains future self-modifications
      - The system cannot arbitrarily restructure itself

    In LLM terms:
      - This is the 'outer loop' of meta-learning
      - During training: adjusting learning rate, batch size, etc.
      - During inference: adaptive temperature, attention reweighting
      - In agents: tool selection based on self-assessed capability
    """

    def __init__(
        self,
        engine: TransitionEngine,
        guard: Optional[StructuralGuard] = None,
        topology: Optional[Topology] = None,
        reflect_every: int = 5,
        ideal_meta: Optional[MetaState] = None,
    ):
        self.engine = engine
        self.guard = guard
        self.topology = topology or Topology()
        self.reflect_every = reflect_every
        self.steps_since_reflect = 0

        # The 'ideal' meta-state the system tends toward
        # Low Δ, low R, high historization, high integrity
        self.ideal_meta = ideal_meta or MetaState(
            avg_delta=0.0,
            avg_resistance=0.5,
            historization_density=0.8,
            transition_rate=1.0,
            structural_integrity=0.9,
            diversity=0.7,
            reflexive_depth=0,
        )

        self.meta_history: List[MetaState] = []
        self.meta_transitions: List[Tuple[MetaState, MetaState, float]] = []
        self._adaptation_log: List[str] = []

    def _measure_meta_state(self, paths: List[Path]) -> MetaState:
        """
        Observe the engine's own structural condition.

        This is purely descriptive — no interpretation, no evaluation.
        Just measurement of structural quantities.
        """
        history = self.engine.history
        log = self.engine.transition_log

        # Average unresolved delta
        recent = log[-10:] if log else []
        avg_delta = (
            sum(tr.delta for tr in recent) / len(recent) if recent else 0.0
        )

        # Average resistance
        active_paths = [p for p in paths if p.exists]
        avg_resistance = (
            sum(p.resistance for p in active_paths) / len(active_paths)
            if active_paths else float('inf')
        )

        # Historization density
        total_paths = len(paths)
        historized = len(history.events)
        hist_density = min(historized / max(total_paths, 1), 1.0)

        # Recent transition rate
        if len(log) >= 2:
            recent_window = log[-5:]
            rate_val = len(recent_window) / max(
                recent_window[-1].historization_event.tau
                - recent_window[0].historization_event.tau, 1
            )
        else:
            rate_val = 0.0

        # Structural integrity from topology
        integrity = self.topology.structural_integrity()

        # Diversity: unique targets in recent transitions
        recent_targets = set()
        for tr in log[-10:]:
            recent_targets.add(tr.target.id)
        diversity = len(recent_targets) / max(len(active_paths), 1)

        return MetaState(
            avg_delta=avg_delta,
            avg_resistance=avg_resistance,
            historization_density=hist_density,
            transition_rate=rate_val,
            structural_integrity=integrity,
            diversity=min(diversity, 1.0),
            reflexive_depth=len(self.meta_history),
        )

    def _adapt(self, meta_now: MetaState, meta_delta: float) -> None:
        """
        Self-modification based on meta-level difference.

        The engine adjusts its own parameters to reduce Δ
        between current and ideal meta-state.

        This is NOT goal-seeking. It is Axiom A₀ operating
        at the meta-level: structural instability of non-change.
        """
        ideal = self.ideal_meta

        # If resistance is too high → lower convergence threshold
        # (be more willing to accept small transitions)
        if meta_now.avg_resistance > ideal.avg_resistance * 2:
            old = self.engine.convergence_threshold
            self.engine.convergence_threshold *= 0.8
            self._adaptation_log.append(
                f"τ={self.engine.tau}: Lowered convergence_threshold "
                f"{old:.6f} → {self.engine.convergence_threshold:.6f} "
                f"(high R: {meta_now.avg_resistance:.3f})"
            )

        # If diversity is too low → system is in a rut
        if meta_now.diversity < ideal.diversity * 0.5 and meta_now.diversity > 0:
            self._adaptation_log.append(
                f"τ={self.engine.tau}: Low diversity detected "
                f"({meta_now.diversity:.3f}) — structural rut warning"
            )

        # If historization density is very high → diminishing returns
        if meta_now.historization_density > 0.95:
            self._adaptation_log.append(
                f"τ={self.engine.tau}: Historization saturation "
                f"({meta_now.historization_density:.3f}) — "
                f"new paths needed for further progress"
            )

    def reflect(self, paths: List[Path]) -> Tuple[MetaState, float]:
        """
        One reflexive cycle:
          1. Measure current meta-state
          2. Compute Δ to ideal
          3. If Δ > 0 → adapt (self-modify)
          4. Historize the meta-transition

        Returns (current_meta, meta_delta).
        """
        meta_now = self._measure_meta_state(paths)
        meta_state = meta_now.to_state()
        ideal_state = self.ideal_meta.to_state()

        meta_delta = difference(meta_state, ideal_state)

        # Record meta-transition
        if self.meta_history:
            prev = self.meta_history[-1]
            prev_state = prev.to_state()
            prev_delta = difference(prev_state, meta_state)
            self.meta_transitions.append((prev, meta_now, prev_delta))

        # Axiom A₀ at meta-level: if Δ > 0, adaptation is enforced
        if meta_delta > 0:
            self._adapt(meta_now, meta_delta)

        self.meta_history.append(meta_now)
        return meta_now, meta_delta

    def step(
        self, current: State, paths: List[Path]
    ) -> Optional[TransitionResult]:
        """
        One step with guard checks and periodic reflection.
        """
        # ── Guard layer: filter inadmissible paths ──
        if self.guard:
            admissible_paths, verdicts = self.guard.filter_admissible(paths)
        else:
            admissible_paths = paths

        # ── E₀ transition step ──
        result = self.engine.step(current, admissible_paths)

        if result:
            # Register in topology
            self.topology.connect(
                result.source.id,
                result.target.id,
                overlap=max(0.1, 1.0 / (1.0 + result.resistance)),
            )
            self.topology.historize_connection(
                result.source.id, result.target.id
            )

        # ── Periodic reflection ──
        self.steps_since_reflect += 1
        if self.steps_since_reflect >= self.reflect_every:
            self.reflect(paths)
            self.steps_since_reflect = 0

        return result

    def run(
        self,
        initial: State,
        paths: List[Path],
        max_steps: int = 1000,
        on_step: Optional[Callable[[TransitionResult], None]] = None,
        on_reflect: Optional[Callable[[MetaState, float], None]] = None,
    ) -> List[TransitionResult]:
        """
        Full reflexive transition loop.

        Three nested dynamics:
          1. E₀ level:       Δ > 0 → transition enforced
          2. Guard level:    inadmissible transitions filtered
          3. Reflexive level: meta-Δ > 0 → self-modification enforced
        """
        current = initial
        results: List[TransitionResult] = []

        for _ in range(max_steps):
            tr = self.step(current, paths)
            if tr is None:
                # Try one final reflection before giving up
                if self.steps_since_reflect > 0:
                    meta, meta_delta = self.reflect(paths)
                    if on_reflect:
                        on_reflect(meta, meta_delta)
                    # Retry after adaptation
                    tr = self.step(current, paths)

                if tr is None:
                    break

            results.append(tr)
            if on_step:
                on_step(tr)
            current = tr.target

        # Final reflection
        meta, meta_delta = self.reflect(paths)
        if on_reflect:
            on_reflect(meta, meta_delta)

        return results

    def report(self) -> str:
        """Full system state report across all three layers."""
        lines = [
            "═══ E₀ Reflexive System — Full Report ═══",
            "",
            "── Layer 0: Ontodynamics ──",
            f"  Topology:           {self.topology}",
            f"  Structural integrity: {self.topology.structural_integrity():.4f}",
            f"  Connections:         {len(self.topology.all_connections)}",
            f"  Historized:          {len(self.topology.historized_connections)}",
            "",
            "── Layer 1: E₀ Engine ──",
            f"  τ (time):           {self.engine.tau}",
            f"  Transitions:        {len(self.engine.transition_log)}",
            f"  Convergence thresh: {self.engine.convergence_threshold:.8f}",
            "",
            "── Layer 2: Reflexivity ──",
            f"  Reflections:        {len(self.meta_history)}",
            f"  Meta-transitions:   {len(self.meta_transitions)}",
            f"  Adaptations:        {len(self._adaptation_log)}",
        ]

        if self.meta_history:
            latest = self.meta_history[-1]
            lines += [
                "",
                f"  Latest MetaState:",
                f"    Δ̄ (avg delta):       {latest.avg_delta:.4f}",
                f"    R̄ (avg resistance):   {latest.avg_resistance:.4f}",
                f"    H% (historization):    {latest.historization_density:.4f}",
                f"    v̄ (transition rate):   {latest.transition_rate:.4f}",
                f"    Integrity:             {latest.structural_integrity:.4f}",
                f"    Diversity:             {latest.diversity:.4f}",
            ]

        if self._adaptation_log:
            lines += ["", "  Adaptation Log:"]
            for entry in self._adaptation_log:
                lines.append(f"    {entry}")

        return "\n".join(lines)
