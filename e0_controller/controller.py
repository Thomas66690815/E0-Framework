"""
E₀ Controller — Core Loop
============================
The deterministic transition logic.

Spec coverage: §18 (Selection), §17 (Historization Update),
               Revisit-Penalty (v0.2 addition).

Core function implemented:
    6. select_next(x)           — Greedy + Revisit-Penalty + Escalation
    7. update_historization(…)  — handled via Landscape.historization.update()

Controller loop:
    select → execute → historize → repeat
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Set, Tuple

from .primitives import Edge, Outcome
from .landscape import Landscape
from .tension import tension, coherence

if TYPE_CHECKING:
    from .amplitude_overlay import OverlayReport


class EscalationType(Enum):
    """K12: Distinct escalation reasons."""
    NONE = "none"             # no escalation (normal transition)
    DEAD_END = "dead_end"     # no outgoing edges at all
    FILTERED = "filtered"     # edges exist but none pass admissibility
    EXHAUSTED = "exhausted"   # all admissible heavily penalized (revisit-dominant)


class HybridMode(Enum):
    """3l: Amplitude-hybrid selection modes."""
    GREEDY = "greedy"                         # pure deterministic (default)
    AMPLITUDE_ON_DISAGREE = "amplitude_on_disagree"  # B3: follow amplitude when DISAGREE


@dataclass
class StepResult:
    """One completed controller cycle."""
    tau: int                     # step number
    source: str                  # where we were
    target: str                  # where we went
    outcome: Outcome             # what happened
    s_eff: float                 # tension of chosen edge
    r_eff_before: float          # R_eff before historization update
    r_eff_after: float           # R_eff after historization update
    candidates: List[str]        # who was admissible
    escalated: bool = False      # was this an escalation?
    escalation_type: EscalationType = EscalationType.NONE  # K12: why
    overlay: Optional["OverlayReport"] = None  # 3k: amplitude overlay snapshot
    hybrid_overridden: bool = False  # 3l: True when amplitude overrode greedy


@dataclass
class RunTrace:
    """Complete trace of a controller run."""
    steps: List[StepResult] = field(default_factory=list)

    @property
    def path(self) -> List[str]:
        """Sequence of visited states."""
        if not self.steps:
            return []
        states = [self.steps[0].source]
        for s in self.steps:
            states.append(s.target)
        return states

    @property
    def total_tension(self) -> float:
        return sum(s.s_eff for s in self.steps if not math.isinf(s.s_eff))

    @property
    def outcomes(self) -> Dict[str, int]:
        counts = {"SUCCESS": 0, "FAILURE": 0, "PARTIAL": 0}
        for s in self.steps:
            counts[s.outcome.name] += 1
        return counts

    def summary(self) -> str:
        lines = [f"RunTrace: {len(self.steps)} steps"]
        lines.append(f"  Path: {' → '.join(self.path)}")
        lines.append(f"  Outcomes: {self.outcomes}")
        lines.append(f"  Total tension: {self.total_tension:.4f}")
        escalations = sum(1 for s in self.steps if s.escalated)
        if escalations:
            lines.append(f"  Escalations: {escalations}")
        return "\n".join(lines)

    def metrics(self) -> Dict[str, float]:
        """
        K13: Operative Metriken für den Lauf.

        Returns dict with:
            steps              — Anzahl Schritte
            deterministic_rate — Anteil nicht-eskalierter Entscheidungen
            escalation_count   — wie oft wurde eskaliert
            success_rate       — Anteil SUCCESS-Outcomes
            failure_rate       — Anteil FAILURE-Outcomes
            avg_tension        — mittlere Tension (nur endliche)
            avg_r_eff_shift    — mittlere Veränderung R_eff pro Step
            revisit_count      — wie oft ein State mehrfach besucht wurde
            unique_states      — Anzahl verschiedener besuchter States
            overlay_agree      — fraction of steps where controller == amplitude choice
            overlay_count      — number of steps with overlay attached
            hybrid_override_count — number of steps where amplitude overrode greedy
            hybrid_override_rate  — fraction of steps with hybrid override
        """
        n = len(self.steps)
        if n == 0:
            return {k: 0.0 for k in [
                "steps", "deterministic_rate", "escalation_count",
                "success_rate", "failure_rate", "avg_tension",
                "avg_r_eff_shift", "revisit_count", "unique_states",
                "overlay_agree", "overlay_count",
                "hybrid_override_count", "hybrid_override_rate",
            ]}

        esc = sum(1 for s in self.steps if s.escalated)
        oc = self.outcomes
        finite_tensions = [s.s_eff for s in self.steps
                           if not math.isinf(s.s_eff)]
        r_shifts = [abs(s.r_eff_after - s.r_eff_before) for s in self.steps]

        path = self.path
        unique = set(path)
        revisits = len(path) - len(unique)

        # Overlay agreement stats
        overlay_steps = [s for s in self.steps if s.overlay is not None]
        overlay_count = len(overlay_steps)
        overlay_agree_count = sum(
            1 for s in overlay_steps
            if s.overlay.amplitude_choice == s.target
        )

        return {
            "steps": float(n),
            "deterministic_rate": (n - esc) / n,
            "escalation_count": float(esc),
            "success_rate": oc["SUCCESS"] / n,
            "failure_rate": oc["FAILURE"] / n,
            "avg_tension": (sum(finite_tensions) / len(finite_tensions)
                           if finite_tensions else 0.0),
            "avg_r_eff_shift": sum(r_shifts) / n,
            "revisit_count": float(revisits),
            "unique_states": float(len(unique)),
            "overlay_agree": (overlay_agree_count / overlay_count
                              if overlay_count else 0.0),
            "overlay_count": float(overlay_count),
            "hybrid_override_count": float(sum(
                1 for s in self.steps if s.hybrid_overridden)),
            "hybrid_override_rate": (sum(
                1 for s in self.steps if s.hybrid_overridden) / n),
        }


# Type for the execution callback
ExecuteFn = Callable[[str, str], Outcome]


class E0Controller:
    """
    Deterministic E₀ Controller v0.3

    Implements greedy transition selection with:
    - Admissibility filter: S_max and C_min thresholds (K11)
    - Revisit-penalty: penalize recently visited states
    - Typed escalation: DEAD_END / FILTERED / EXHAUSTED (K12)
    - Historization: learn from each transition outcome
    - Hybrid mode (3l): optional amplitude-guided override on DISAGREE

    Parameters:
        landscape: The Landscape L_t
        execute_fn: Callback (source, target) → Outcome
        alpha: Revisit-penalty weight (default 2.0)
        recent_k: Number of recent states to penalize (default 3)
        max_escalation_R: Maximum R₀ to assign during escalation (default 5.0)
        s_max: Maximum admissible tension (K11, default ∞ = no filter)
        c_min: Minimum coherence to be admissible (K11, default 0.0 = no filter)
        hybrid_mode: HybridMode.GREEDY (default) or AMPLITUDE_ON_DISAGREE
        hybrid_horizon: Horizon for amplitude overlay in hybrid mode (default 3)
        hybrid_goals: Goal states for first_arrival geometry (default None)
    """

    def __init__(
        self,
        landscape: Landscape,
        execute_fn: ExecuteFn,
        alpha: float = 2.0,
        recent_k: int = 3,
        max_escalation_R: float = 5.0,
        s_max: float = math.inf,
        c_min: float = 0.0,
        hybrid_mode: HybridMode = HybridMode.GREEDY,
        hybrid_horizon: int = 3,
        hybrid_goals: Optional[Set[str]] = None,
    ):
        self.landscape = landscape
        self.execute_fn = execute_fn
        self.alpha = alpha
        self.recent_k = recent_k
        self.max_escalation_R = max_escalation_R
        self.s_max = s_max      # K11: tension ceiling
        self.c_min = c_min      # K11: coherence floor
        self.hybrid_mode = hybrid_mode    # 3l: hybrid selection mode
        self.hybrid_horizon = hybrid_horizon  # 3l: overlay horizon
        self.hybrid_goals = hybrid_goals  # 3l: goal states for overlay
        self._recent: List[str] = []   # sliding window of recent states

        # K1 fix: Escalation edges live here, NOT in the Landscape.
        self._escalation_edges: Dict[Edge, Tuple[float, float]] = {}

    # --- Edge resolution (landscape + escalation overlay) ---

    def _get_delta(self, x: str, y: str) -> Optional[float]:
        """Δ from escalation overlay or landscape. None = no edge (K3)."""
        edge = Edge(x, y)
        if edge in self._escalation_edges:
            return self._escalation_edges[edge][0]
        return self.landscape.difference(x, y)

    def _get_base_resistance(self, x: str, y: str) -> float:
        """R₀ from escalation overlay or landscape."""
        edge = Edge(x, y)
        if edge in self._escalation_edges:
            return self._escalation_edges[edge][1]
        return self.landscape.base_resistance(x, y)

    def _effective_resistance(self, x: str, y: str) -> float:
        """R_eff = R₀ + δ_H, checking escalation overlay first."""
        r0 = self._get_base_resistance(x, y)
        if math.isinf(r0):
            return math.inf
        dh = self.landscape.historization.delta_H(Edge(x, y))
        return max(r0 + dh, 1e-10)

    def _effective_tension(self, x: str, y: str) -> float:
        """S_eff = Δ · R_eff, checking escalation overlay first. ∞ if no edge (K3)."""
        delta = self._get_delta(x, y)
        if delta is None:
            return math.inf
        r_eff = self._effective_resistance(x, y)
        return tension(delta, r_eff)

    def _admissible_neighbors(self, x: str) -> List[str]:
        """
        K11: Full controller admissibility with configurable thresholds.

        This is the *controller-level* filter, stricter than
        Landscape.admissible_neighbors() (raw: only finite tension).

        A neighbor y is admissible from x if:
        1. S_eff(x→y) < ∞  (edge exists)            — raw layer
        2. S_eff(x→y) ≤ s_max  (tension ceiling)     — K11
        3. C(x→y) ≥ c_min  (coherence floor)          — K11

        With defaults (s_max=∞, c_min=0.0), this collapses to raw.
        """
        neighbors = []
        # Check landscape edges
        for edge in self.landscape._R0:
            if edge.source == x:
                s = self._effective_tension(x, edge.target)
                if self._passes_admissibility(s):
                    neighbors.append(edge.target)
        # Check escalation overlay
        for edge, (_delta, _r0) in self._escalation_edges.items():
            if edge.source == x and edge.target not in neighbors:
                s = self._effective_tension(x, edge.target)
                if self._passes_admissibility(s):
                    neighbors.append(edge.target)
        return neighbors

    def _raw_neighbors(self, x: str) -> List[str]:
        """All neighbors with finite tension (ignoring K11 filter)."""
        neighbors = []
        for edge in self.landscape._R0:
            if edge.source == x:
                if not math.isinf(self._effective_tension(x, edge.target)):
                    neighbors.append(edge.target)
        for edge in self._escalation_edges:
            if edge.source == x and edge.target not in neighbors:
                if not math.isinf(self._effective_tension(x, edge.target)):
                    neighbors.append(edge.target)
        return neighbors

    def _passes_admissibility(self, s_eff: float) -> bool:
        """K11: Check if a tension value passes the admissibility filter."""
        if math.isinf(s_eff):
            return False
        if s_eff > self.s_max:
            return False
        if self.c_min > 0.0:
            c = coherence(s_eff)
            if c < self.c_min:
                return False
        return True

    def _update_recent(self, state: str) -> None:
        """Maintain sliding window of recently visited states."""
        self._recent.append(state)
        if len(self._recent) > self.recent_k:
            self._recent = self._recent[-self.recent_k:]

    def _penalized_tension(self, x: str, y: str) -> float:
        """
        K7: S_revisit(x→y) = S_eff(x→y) · (1 + α · 𝟙[y ∈ recent(k)])

        Multiplicative penalty for revisiting recently-seen states.
        Scales with the local tension — avoids dominating at low S_eff
        or vanishing at high S_eff (K7 fix over former additive form).
        """
        s_eff = self._effective_tension(x, y)
        if math.isinf(s_eff):
            return math.inf
        if y in self._recent:
            s_eff *= (1 + self.alpha)
        return s_eff

    def select_next(self, current: str) -> Tuple[Optional[str], bool, EscalationType]:
        """
        Function 6: select_next(x) → (next_state, escalated?, escalation_type)

        §18: p* = argmin S_eff(p)

        Strategy: Greedy + Revisit-Penalty + Typed Escalation.
        1. Get admissible neighbors (K11 filtered).
        2. Pick argmin of penalized tension.
        3. If empty → classify WHY and escalate accordingly (K12).

        This is always the pure greedy decision. Hybrid logic wraps this
        via select_hybrid().
        """
        neighbors = self._admissible_neighbors(current)

        if neighbors:
            # Check EXHAUSTED: all admissible neighbors recently visited
            all_recent = all(y in self._recent for y in neighbors)
            if not all_recent:
                best = min(neighbors, key=lambda y: self._penalized_tension(current, y))
                return best, False, EscalationType.NONE
            # All neighbors recently visited → EXHAUSTED escalation
            esc_type = EscalationType.EXHAUSTED
        else:
            # --- K12: No admissible neighbors ---
            raw = self._raw_neighbors(current)

            if not raw:
                esc_type = EscalationType.DEAD_END
            else:
                esc_type = EscalationType.FILTERED

        # Recovery strategy depends on type
        target = self._escalation_target(current, esc_type)
        if target is None:
            return None, True, esc_type

        # Store escalation edge in controller buffer
        edge = Edge(current, target)
        self._escalation_edges[edge] = (1.0, self.max_escalation_R)
        return target, True, esc_type

    def _escalation_target(self, current: str, esc_type: EscalationType) -> Optional[str]:
        """
        K12: Different escalation strategies per type.

        DEAD_END:   Jump to state with most outgoing edges (max connectivity).
        FILTERED:   Lower bar — pick from raw neighbors (bypass K11 threshold).
        EXHAUSTED:  Pick least-recently-visited viable state.

        Note (K5 open): These strategies are operational heuristics, not
        yet fully derived from E₀ principles.  In particular the DEAD_END
        strategy ("most outgoing edges") is graph-structural, not
        tension-field-based.  A future version should select escalation
        targets via potential φ or transition field v.
        """
        if esc_type == EscalationType.FILTERED:
            # FILTERED: raw neighbors exist but fail K11 → pick cheapest raw
            raw = self._raw_neighbors(current)
            if raw:
                best = min(raw, key=lambda y: self._effective_tension(current, y))
                return best

        if esc_type == EscalationType.EXHAUSTED:
            # EXHAUSTED: all neighbors recently visited → pick least recent
            neighbors = self._admissible_neighbors(current)
            # Fallback to raw if admissible is truly empty
            if not neighbors:
                neighbors = self._raw_neighbors(current)
            if neighbors:
                # Prefer states NOT in recent window
                not_recent = [y for y in neighbors if y not in self._recent]
                if not_recent:
                    return min(not_recent, key=lambda y: self._effective_tension(current, y))
                return min(neighbors, key=lambda y: self._effective_tension(current, y))

        # DEAD_END (or fallback): global jump to most-connected state
        all_states = self.landscape.states - {current}
        if not all_states:
            return None

        viable = [s for s in all_states if self.landscape.admissible_neighbors(s)]
        if not viable:
            return None

        return max(viable, key=lambda s: len(self.landscape.admissible_neighbors(s)))

    def select_hybrid(
        self, current: str
    ) -> Tuple[Optional[str], bool, EscalationType, Optional["OverlayReport"], bool]:
        """
        3l: Hybrid selection — greedy + amplitude override on DISAGREE.

        Returns (target, escalated, esc_type, overlay_report, hybrid_overridden).

        In GREEDY mode: delegates to select_next, overlay/override are None/False.
        In AMPLITUDE_ON_DISAGREE mode:
            1. Compute greedy choice via select_next()
            2. Compute amplitude overlay
            3. If amplitude_choice != greedy choice AND amplitude_choice is
               admissible → override with amplitude_choice
            4. Record whether override happened
        """
        greedy_target, escalated, esc_type = self.select_next(current)

        if self.hybrid_mode == HybridMode.GREEDY:
            return greedy_target, escalated, esc_type, None, False

        if greedy_target is None:
            return None, escalated, esc_type, None, False

        # Skip hybrid override for escalated steps — escalation already
        # means the normal selection failed, let it handle recovery.
        if escalated:
            return greedy_target, escalated, esc_type, None, False

        # Compute overlay at this decision point
        overlay = self._compute_overlay(
            current, self.hybrid_horizon, self.hybrid_goals,
        )
        if overlay is None:
            return greedy_target, escalated, esc_type, None, False

        amp_choice = overlay.amplitude_choice
        if amp_choice is None or amp_choice == greedy_target:
            # AGREE — keep greedy
            return greedy_target, escalated, esc_type, overlay, False

        # DISAGREE — amplitude prefers a different action.
        # Only override if amplitude choice is in the admissible set.
        admissible = self._admissible_neighbors(current)
        if amp_choice in admissible:
            return amp_choice, escalated, esc_type, overlay, True

        # Amplitude choice not admissible — stay with greedy
        return greedy_target, escalated, esc_type, overlay, False

    def cycle(
        self,
        current: str,
        overlay_horizon: int = 0,
        overlay_goals: Optional[Set[str]] = None,
    ) -> Optional[StepResult]:
        """
        One complete controller cycle:
            select → execute → historize → report

        In hybrid mode, the selection may be overridden by amplitude analysis.
        If overlay_horizon > 0 (or hybrid mode is active), an amplitude overlay
        snapshot is attached to the StepResult.
        Returns None if no transition is possible.
        """
        target, escalated, esc_type, hybrid_overlay, overridden = \
            self.select_hybrid(current)
        if target is None:
            return None

        edge = Edge(current, target)

        # Capture state BEFORE execution (K6 fix: candidates at decision time)
        candidates = self._admissible_neighbors(current)
        r_eff_before = self._effective_resistance(current, target)
        s_eff = self._effective_tension(current, target)

        # Execute
        outcome = self.execute_fn(current, target)

        # Historize (Function 7)
        self.landscape.historization.update(edge, outcome)
        self.landscape.historization.record(
            edge, outcome, r_eff_before,
            self._effective_resistance(current, target)
        )

        # Capture R_eff after
        r_eff_after = self._effective_resistance(current, target)

        # Update recent window
        self._update_recent(current)

        # Overlay: use hybrid overlay if available, else compute on-demand
        overlay = hybrid_overlay or self._compute_overlay(
            current, overlay_horizon, overlay_goals,
        )

        return StepResult(
            tau=self.landscape.historization.tau,
            source=current,
            target=target,
            outcome=outcome,
            s_eff=s_eff,
            r_eff_before=r_eff_before,
            r_eff_after=r_eff_after,
            candidates=candidates,
            escalated=escalated,
            escalation_type=esc_type,
            overlay=overlay,
            hybrid_overridden=overridden,
        )

    def _compute_overlay(
        self,
        current: str,
        overlay_horizon: int,
        overlay_goals: Optional[Set[str]],
    ) -> Optional["OverlayReport"]:
        """Compute amplitude overlay if horizon > 0, else None."""
        if overlay_horizon <= 0:
            return None
        from .amplitude_overlay import analyze_controller_state
        return analyze_controller_state(
            self, current, horizon_edges=overlay_horizon, goals=overlay_goals,
        )

    def run(
        self,
        start: str,
        max_cycles: int = 50,
        goal: Optional[str] = None,
        overlay_horizon: int = 0,
        overlay_goals: Optional[Set[str]] = None,
    ) -> RunTrace:
        """
        Run the controller from start.

        If overlay_horizon > 0, each StepResult will carry an amplitude
        overlay snapshot for that decision point (analysis only, does NOT
        alter transitions).

        Stops when:
        - goal state is reached (if specified)
        - max_cycles exceeded
        - no transition possible (complete dead-end)
        """
        trace = RunTrace()
        current = start

        for _ in range(max_cycles):
            # Check goal
            if goal and current == goal:
                break

            step = self.cycle(current, overlay_horizon, overlay_goals)
            if step is None:
                break  # complete dead-end, no escalation possible

            trace.steps.append(step)
            current = step.target

        return trace
