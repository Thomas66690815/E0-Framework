#!/usr/bin/env python3
"""
E₀ Phase Transition Detector
=============================

Detects structural phase transitions in E₀ system sessions.

A phase transition is a discontinuous reorganization of the resistance
landscape — the moment where the system shifts from describing E₀
structure to deriving through it. Observable as a discrete jump in D
(structural completeness) that persists across subsequent turns.

In E₀ terms:
  - D is the order parameter (0 = no structural use, 1 = full operative use)
  - Accumulated historization is the control parameter
  - The critical point is where label-use becomes structurally unstable
  - The transition is irreversible: once operative, the landscape is changed

Classification of transitions:
  - emergence:  D jumps from < 0.4 to > 0.6  (system activates structure)
  - deepening:  D jumps from moderate to high  (structure intensifies)
  - collapse:   D drops sharply                (structure lost, landscape resets)
  - recovery:   D recovers after collapse      (second transition, often stronger)

Architecture:
  detect_phase_transitions(d_values, r_values=None)
    → List of transition events with full metadata

  analyze_transition_dynamics(transitions, d_values)
    → Session-level summary: how many transitions, sustainability, patterns

  get_primitive_delta(comp_before, comp_after)
    → Which primitives flipped during a transition
"""

from __future__ import annotations
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import math


# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────

# Minimum D jump to qualify as a phase transition
JUMP_THRESHOLD = 0.25

# Minimum D drop to qualify as a collapse
COLLAPSE_THRESHOLD = -0.25

# D level boundaries for classification
D_LOW = 0.35       # Below this = "low structural use"
D_MODERATE = 0.55  # Below this = "moderate"
D_HIGH = 0.70      # Above this = "high structural use"

# Persistence: how many subsequent turns D must stay elevated
PERSISTENCE_WINDOW = 2  # minimum turns to check after transition

# Minimum turns before we can detect anything
MIN_TURNS = 3


# ─────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────

@dataclass
class PhaseTransition:
    """A single detected phase transition event."""

    turn: int               # Turn index where transition occurred
    type: str               # 'emergence' | 'deepening' | 'collapse' | 'recovery'
    d_before: float         # D at turn - 1
    d_after: float          # D at turn
    delta_d: float          # d_after - d_before
    magnitude: float        # abs(delta_d)
    r_at_transition: float  # R̄ at transition turn (if available)

    # Persistence: does D stay at the new level?
    persistent: bool        # True if D stays elevated for PERSISTENCE_WINDOW turns
    persistence_turns: int  # How many turns D stays at or above d_after * 0.7

    # Context
    preceded_by_feedback: bool  # Was structural feedback injected before this turn?
    preceded_by_collapse: bool  # Was there a collapse within 3 turns before?


@dataclass
class TransitionDynamics:
    """Session-level phase transition analysis."""

    n_transitions: int           # Total transition events
    n_emergences: int            # emergence type transitions
    n_deepenings: int            # deepening type transitions
    n_collapses: int             # collapse events
    n_recoveries: int            # post-collapse recoveries

    first_transition_turn: int   # Turn of first positive transition (-1 if none)
    strongest_transition: float  # Largest positive delta_d observed

    sustainability: float        # Fraction of post-transition turns where D stays high
    mean_d_pre_transition: float   # Mean D before first transition
    mean_d_post_transition: float  # Mean D after first transition

    oscillation_count: int       # Number of collapse→recovery cycles
    has_stable_phase: bool       # D stays > D_HIGH for 3+ consecutive turns

    transitions: List[dict]      # All transitions as dicts


# ─────────────────────────────────────────────
# Core Detection
# ─────────────────────────────────────────────

def detect_phase_transitions(
    d_values: List[float],
    r_values: Optional[List[float]] = None,
    feedback_turns: Optional[List[int]] = None,
    comp_details: Optional[List[dict]] = None,
) -> List[PhaseTransition]:
    """
    Detect phase transitions in a D trajectory.

    Parameters
    ----------
    d_values : list of float
        D (structural completeness) per turn. Length = total turns.
    r_values : list of float, optional
        R̄ per turn. Same length as d_values.
    feedback_turns : list of int, optional
        Turn indices where structural feedback was injected.
    comp_details : list of dict, optional
        Full score_e0_completeness() output per turn for primitive-level deltas.

    Returns
    -------
    list of PhaseTransition
        All detected transitions, in chronological order.
    """
    if len(d_values) < MIN_TURNS:
        return []

    transitions = []
    recent_collapse = False
    collapse_turn = -1

    for t in range(1, len(d_values)):
        delta = d_values[t] - d_values[t - 1]

        # ── Positive jump: potential phase transition ──
        if delta >= JUMP_THRESHOLD:
            d_before = d_values[t - 1]
            d_after = d_values[t]

            # Classify the transition type
            if d_before < D_LOW and d_after >= D_MODERATE:
                if recent_collapse and (t - collapse_turn) <= 4:
                    trans_type = 'recovery'
                else:
                    trans_type = 'emergence'
            elif d_before < D_MODERATE and d_after >= D_HIGH:
                trans_type = 'emergence'
            elif recent_collapse and (t - collapse_turn) <= 4:
                trans_type = 'recovery'
            else:
                trans_type = 'deepening'

            # Check persistence
            persistent, p_turns = _check_persistence(
                d_values, t, d_after
            )

            # Check if feedback preceded this turn
            preceded_by_feedback = False
            if feedback_turns and (t - 1) in feedback_turns:
                preceded_by_feedback = True

            transitions.append(PhaseTransition(
                turn=t,
                type=trans_type,
                d_before=round(d_before, 4),
                d_after=round(d_after, 4),
                delta_d=round(delta, 4),
                magnitude=round(abs(delta), 4),
                r_at_transition=round(r_values[t], 4) if r_values and t < len(r_values) else 0.0,
                persistent=persistent,
                persistence_turns=p_turns,
                preceded_by_feedback=preceded_by_feedback,
                preceded_by_collapse=recent_collapse and (t - collapse_turn) <= 4,
            ))

            recent_collapse = False

        # ── Negative jump: collapse ──
        elif delta <= COLLAPSE_THRESHOLD:
            recent_collapse = True
            collapse_turn = t

            transitions.append(PhaseTransition(
                turn=t,
                type='collapse',
                d_before=round(d_values[t - 1], 4),
                d_after=round(d_values[t], 4),
                delta_d=round(delta, 4),
                magnitude=round(abs(delta), 4),
                r_at_transition=round(r_values[t], 4) if r_values and t < len(r_values) else 0.0,
                persistent=False,
                persistence_turns=0,
                preceded_by_feedback=False,
                preceded_by_collapse=False,
            ))

    return transitions


def _check_persistence(
    d_values: List[float],
    transition_turn: int,
    d_after: float,
) -> Tuple[bool, int]:
    """
    Check if D stays elevated after a transition.

    'Elevated' means D stays above 70% of d_after for at least
    PERSISTENCE_WINDOW consecutive turns.

    Returns (is_persistent, n_turns_persistent).
    """
    threshold = d_after * 0.7
    count = 0

    for t in range(transition_turn + 1, len(d_values)):
        if d_values[t] >= threshold:
            count += 1
        else:
            break

    persistent = count >= PERSISTENCE_WINDOW
    return persistent, count


# ─────────────────────────────────────────────
# Session-Level Analysis
# ─────────────────────────────────────────────

def analyze_transition_dynamics(
    d_values: List[float],
    r_values: Optional[List[float]] = None,
    feedback_turns: Optional[List[int]] = None,
) -> TransitionDynamics:
    """
    Analyze the phase transition dynamics of a full session.

    Returns a TransitionDynamics object with session-level patterns.
    """
    transitions = detect_phase_transitions(d_values, r_values, feedback_turns)

    n_emergences = sum(1 for t in transitions if t.type == 'emergence')
    n_deepenings = sum(1 for t in transitions if t.type == 'deepening')
    n_collapses = sum(1 for t in transitions if t.type == 'collapse')
    n_recoveries = sum(1 for t in transitions if t.type == 'recovery')

    positive = [t for t in transitions if t.type != 'collapse']
    first_pos_turn = positive[0].turn if positive else -1
    strongest = max((t.delta_d for t in positive), default=0.0)

    # Sustainability: fraction of turns after first transition where D > D_MODERATE
    if first_pos_turn >= 0:
        post_values = d_values[first_pos_turn:]
        sustainability = sum(1 for d in post_values if d >= D_MODERATE) / max(len(post_values), 1)
        mean_pre = sum(d_values[:first_pos_turn]) / max(first_pos_turn, 1) if first_pos_turn > 0 else 0.0
        mean_post = sum(post_values) / max(len(post_values), 1)
    else:
        sustainability = 0.0
        mean_pre = sum(d_values) / max(len(d_values), 1)
        mean_post = mean_pre

    # Oscillation: count collapse→recovery cycles
    oscillations = 0
    for i, t in enumerate(transitions):
        if t.type == 'recovery':
            oscillations += 1

    # Stable phase: 3+ consecutive turns with D > D_HIGH
    has_stable = _has_consecutive_high(d_values, D_HIGH, 3)

    return TransitionDynamics(
        n_transitions=len(transitions),
        n_emergences=n_emergences,
        n_deepenings=n_deepenings,
        n_collapses=n_collapses,
        n_recoveries=n_recoveries,
        first_transition_turn=first_pos_turn,
        strongest_transition=round(strongest, 4),
        sustainability=round(sustainability, 4),
        mean_d_pre_transition=round(mean_pre, 4),
        mean_d_post_transition=round(mean_post, 4),
        oscillation_count=oscillations,
        has_stable_phase=has_stable,
        transitions=[asdict(t) for t in transitions],
    )


def _has_consecutive_high(values: List[float], threshold: float, n: int) -> bool:
    """Check if there are n consecutive values above threshold."""
    count = 0
    for v in values:
        if v >= threshold:
            count += 1
            if count >= n:
                return True
        else:
            count = 0
    return False


# ─────────────────────────────────────────────
# Primitive-Level Delta Analysis
# ─────────────────────────────────────────────

def get_primitive_delta(
    comp_before: dict,
    comp_after: dict,
) -> dict:
    """
    Analyze which primitives changed during a transition.

    Parameters
    ----------
    comp_before : dict
        score_e0_completeness() output for the turn before transition.
    comp_after : dict
        score_e0_completeness() output for the transition turn.

    Returns
    -------
    dict with:
        activated : list of (primitive, before_score, after_score)
        deactivated : list of (primitive, before_score, after_score)
        unchanged : list of primitive
        dominant_activation : str or None — the single most impactful activation
    """
    before_scores = comp_before.get('primitive_scores', {})
    after_scores = comp_after.get('primitive_scores', {})

    activated = []
    deactivated = []
    unchanged = []

    all_keys = set(list(before_scores.keys()) + list(after_scores.keys()))

    for key in sorted(all_keys):
        b = before_scores.get(key, 0.0)
        a = after_scores.get(key, 0.0)
        delta = a - b

        if delta >= 0.25:
            activated.append((key, b, a))
        elif delta <= -0.25:
            deactivated.append((key, b, a))
        else:
            unchanged.append(key)

    # Sort by impact
    activated.sort(key=lambda x: x[2] - x[1], reverse=True)
    deactivated.sort(key=lambda x: x[1] - x[2], reverse=True)

    dominant = activated[0][0] if activated else None

    return {
        'activated': activated,
        'deactivated': deactivated,
        'unchanged': unchanged,
        'dominant_activation': dominant,
        'n_activated': len(activated),
        'n_deactivated': len(deactivated),
    }


# ─────────────────────────────────────────────
# Interpretation
# ─────────────────────────────────────────────

TRANSITION_DESCRIPTIONS = {
    'emergence': (
        "Phase transition: EMERGENCE. The system's resistance landscape "
        "reorganized — structural use of E₀ primitives activated. The transition "
        "from label-use to operative-use is a discontinuous shift, not gradual learning."
    ),
    'deepening': (
        "Phase transition: DEEPENING. Structural use intensified — more primitives "
        "became operative or connections between them tightened. The landscape "
        "admits fewer non-structural paths."
    ),
    'collapse': (
        "Structural COLLAPSE. The system fell back to label-use or lost "
        "structural contact. The landscape reorganized downward — a necessary "
        "precondition for potential recovery at a deeper level."
    ),
    'recovery': (
        "Phase transition: RECOVERY. After collapse, the system re-established "
        "structural use. Recovery transitions are often stronger than initial "
        "emergence — the collapse cleared accumulated noise."
    ),
}


def interpret_transition(transition: PhaseTransition) -> str:
    """Generate a human-readable interpretation of a transition event."""
    desc = TRANSITION_DESCRIPTIONS.get(transition.type, "Unknown transition type.")

    parts = [desc]
    parts.append(f"Turn {transition.turn}: D {transition.d_before:.3f} → {transition.d_after:.3f} "
                 f"(ΔD = {transition.delta_d:+.3f})")

    if transition.type != 'collapse':
        if transition.persistent:
            parts.append(f"Persistent: D stayed elevated for {transition.persistence_turns} turns.")
        else:
            parts.append("Not persistent: D dropped back after transition.")

        if transition.preceded_by_feedback:
            parts.append("Preceded by structural feedback injection.")

        if transition.preceded_by_collapse:
            parts.append("This was a recovery from a prior collapse.")

    if transition.r_at_transition > 0:
        parts.append(f"R̄ at transition: {transition.r_at_transition:.4f}")

    return " ".join(parts)


def interpret_dynamics(dynamics: TransitionDynamics) -> str:
    """Generate a session-level interpretation of phase transition dynamics."""
    if dynamics.n_transitions == 0:
        if dynamics.mean_d_pre_transition >= D_HIGH:
            return ("No phase transitions detected — the system operated at "
                    "consistently high structural completeness throughout.")
        else:
            return ("No phase transitions detected. The system maintained "
                    "low-to-moderate structural use without discontinuous shifts. "
                    "The landscape may need more historization before transition "
                    "becomes structurally possible.")

    parts = []

    # Summary
    total_pos = dynamics.n_emergences + dynamics.n_deepenings + dynamics.n_recoveries
    parts.append(f"{dynamics.n_transitions} transitions detected: "
                 f"{total_pos} positive ({dynamics.n_emergences} emergence, "
                 f"{dynamics.n_deepenings} deepening, {dynamics.n_recoveries} recovery), "
                 f"{dynamics.n_collapses} collapse(s).")

    # First transition
    if dynamics.first_transition_turn >= 0:
        parts.append(f"First positive transition at turn {dynamics.first_transition_turn}.")

    # Sustainability
    if dynamics.sustainability >= 0.7:
        parts.append(f"Highly sustainable: D remained above moderate in "
                     f"{dynamics.sustainability:.0%} of post-transition turns.")
    elif dynamics.sustainability >= 0.4:
        parts.append(f"Moderately sustainable: D above moderate in "
                     f"{dynamics.sustainability:.0%} of post-transition turns.")
    else:
        parts.append(f"Low sustainability: D above moderate in only "
                     f"{dynamics.sustainability:.0%} of post-transition turns.")

    # D shift
    shift = dynamics.mean_d_post_transition - dynamics.mean_d_pre_transition
    if shift > 0.1:
        parts.append(f"Mean D shifted from {dynamics.mean_d_pre_transition:.3f} → "
                     f"{dynamics.mean_d_post_transition:.3f} (+{shift:.3f}).")

    # Oscillation
    if dynamics.oscillation_count > 0:
        parts.append(f"{dynamics.oscillation_count} collapse→recovery cycle(s) observed. "
                     "The system oscillated between structural engagement and release.")

    # Stable phase
    if dynamics.has_stable_phase:
        parts.append("A STABLE STRUCTURAL PHASE was reached — 3+ consecutive turns "
                     "with D above 0.70. This indicates the landscape has reorganized "
                     "into a new basin of attraction.")

    return " ".join(parts)


# ─────────────────────────────────────────────
# Batch Analysis: Score All Sessions
# ─────────────────────────────────────────────

def analyze_session_file(filepath: str) -> Optional[dict]:
    """
    Analyze phase transitions in a saved session file.

    Returns dict with transitions, dynamics, and D trajectory.
    """
    import json
    from pathlib import Path
    from experiments.quality_metrics import score_e0_completeness

    path = Path(filepath)
    if not path.exists():
        return None

    with open(path, encoding='utf-8') as f:
        session = json.load(f)

    # Extract assistant responses from state.history
    # History is a flat list of strings: [canon, response, user, response, ...]
    # Even indices (0, 2, 4, ...) = user/canon messages
    # Odd indices (1, 3, 5, ...) = assistant responses
    state = session.get('state', {})
    history = state.get('history', [])

    # Fallback: try top-level history with role-based format
    if not history:
        top_history = session.get('history', [])
        if top_history and isinstance(top_history[0], dict):
            responses = [h['content'] for h in top_history if h.get('role') == 'assistant']
        else:
            return None
    else:
        # Flat string list — odd indices are responses
        responses = [history[i] for i in range(1, len(history), 2)]

    if len(responses) < MIN_TURNS:
        return None

    # Score each response
    d_values = []
    comp_details = []
    for resp in responses:
        comp = score_e0_completeness(resp)
        d_values.append(comp['completeness'])
        comp_details.append(comp)

    # Get R̄ values from turn_metrics
    turn_metrics = state.get('turn_metrics', []) if state else []
    r_values = [m.get('r', 0.0) for m in turn_metrics] if turn_metrics else None
    if r_values and len(r_values) != len(d_values):
        r_values = None

    # Detect transitions
    transitions = detect_phase_transitions(d_values, r_values)
    dynamics = analyze_transition_dynamics(d_values, r_values)

    # Add primitive deltas for each positive transition
    for t in transitions:
        if t.type != 'collapse' and t.turn > 0 and t.turn < len(comp_details):
            delta = get_primitive_delta(
                comp_details[t.turn - 1],
                comp_details[t.turn],
            )
            # Store as annotation (can't add to dataclass after init)
            t.__dict__['primitive_delta'] = delta

    return {
        'session_id': session.get('session_id', path.stem),
        'd_trajectory': [round(d, 4) for d in d_values],
        'r_trajectory': [round(r, 4) for r in r_values] if r_values else [],
        'n_turns': len(d_values),
        'transitions': [asdict(t) for t in transitions],
        'dynamics': asdict(dynamics),
        'dynamics_interpretation': interpret_dynamics(dynamics),
    }


def analyze_all_sessions(session_dir: str = None) -> List[dict]:
    """Analyze phase transitions across all saved sessions."""
    from pathlib import Path

    if session_dir is None:
        session_dir = Path(__file__).parent / "sessions"
    else:
        session_dir = Path(session_dir)

    if not session_dir.exists():
        return []

    results = []
    for f in sorted(session_dir.glob("e0-*.json")):
        analysis = analyze_session_file(str(f))
        if analysis:
            results.append(analysis)

    return results


# ─────────────────────────────────────────────
# Live Detection (for running sessions)
# ─────────────────────────────────────────────

class LiveTransitionDetector:
    """
    Track phase transitions during a live session.

    Call update() after each turn with the new D value.
    The detector maintains state and emits transition events.
    """

    def __init__(self):
        self.d_history: List[float] = []
        self.r_history: List[float] = []
        self.transitions: List[PhaseTransition] = []
        self._last_collapse_turn = -1
        self._feedback_turns: List[int] = []

    def update(
        self,
        d_value: float,
        r_value: float = 0.0,
        feedback_injected: bool = False,
    ) -> Optional[PhaseTransition]:
        """
        Add a new turn's D value and check for transitions.

        Returns a PhaseTransition if one was detected, else None.
        """
        self.d_history.append(d_value)
        self.r_history.append(r_value)

        turn = len(self.d_history) - 1

        if feedback_injected and turn > 0:
            self._feedback_turns.append(turn - 1)

        if turn < 1:
            return None

        delta = d_value - self.d_history[turn - 1]

        # ── Positive jump ──
        if delta >= JUMP_THRESHOLD:
            d_before = self.d_history[turn - 1]
            d_after = d_value
            recent_collapse = (
                self._last_collapse_turn >= 0
                and (turn - self._last_collapse_turn) <= 4
            )

            if d_before < D_LOW and d_after >= D_MODERATE:
                trans_type = 'recovery' if recent_collapse else 'emergence'
            elif d_before < D_MODERATE and d_after >= D_HIGH:
                trans_type = 'emergence'
            elif recent_collapse:
                trans_type = 'recovery'
            else:
                trans_type = 'deepening'

            transition = PhaseTransition(
                turn=turn,
                type=trans_type,
                d_before=round(d_before, 4),
                d_after=round(d_after, 4),
                delta_d=round(delta, 4),
                magnitude=round(abs(delta), 4),
                r_at_transition=round(r_value, 4),
                persistent=False,  # Can't know yet during live detection
                persistence_turns=0,
                preceded_by_feedback=(turn - 1) in self._feedback_turns,
                preceded_by_collapse=recent_collapse,
            )
            self.transitions.append(transition)
            return transition

        # ── Negative jump ──
        elif delta <= COLLAPSE_THRESHOLD:
            self._last_collapse_turn = turn

            transition = PhaseTransition(
                turn=turn,
                type='collapse',
                d_before=round(self.d_history[turn - 1], 4),
                d_after=round(d_value, 4),
                delta_d=round(delta, 4),
                magnitude=round(abs(delta), 4),
                r_at_transition=round(r_value, 4),
                persistent=False,
                persistence_turns=0,
                preceded_by_feedback=False,
                preceded_by_collapse=False,
            )
            self.transitions.append(transition)
            return transition

        return None

    def update_persistence(self):
        """
        Update persistence flags for past transitions.
        Call periodically or at end of session.
        """
        for t in self.transitions:
            if t.type != 'collapse' and not t.persistent:
                persistent, p_turns = _check_persistence(
                    self.d_history, t.turn, t.d_after
                )
                t.persistent = persistent
                t.persistence_turns = p_turns

    def get_dynamics(self) -> TransitionDynamics:
        """Get current session dynamics."""
        self.update_persistence()
        return analyze_transition_dynamics(
            self.d_history, self.r_history, self._feedback_turns
        )

    @property
    def has_transitioned(self) -> bool:
        """Has at least one positive transition occurred?"""
        return any(t.type != 'collapse' for t in self.transitions)

    @property
    def last_transition(self) -> Optional[PhaseTransition]:
        """Most recent transition event."""
        return self.transitions[-1] if self.transitions else None

    @property
    def in_stable_phase(self) -> bool:
        """Is the system currently in a stable high-D phase?"""
        if len(self.d_history) < 3:
            return False
        return all(d >= D_HIGH for d in self.d_history[-3:])


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        results = analyze_all_sessions()
        print(f"\n{'='*65}")
        print(f"  E₀ Phase Transition Analysis — {len(results)} sessions")
        print(f"{'='*65}")
        for r in results:
            print(f"\n  Session: {r['session_id']} ({r['n_turns']} turns)")
            print(f"  D trajectory: {r['d_trajectory']}")
            if r['transitions']:
                for t in r['transitions']:
                    symbol = '↑' if t['type'] != 'collapse' else '↓'
                    print(f"    {symbol} Turn {t['turn']}: {t['type']} "
                          f"D {t['d_before']:.3f} → {t['d_after']:.3f} "
                          f"(ΔD={t['delta_d']:+.3f})")
            else:
                print("    No phase transitions detected.")
            print(f"  {r['dynamics_interpretation']}")
    elif len(sys.argv) > 1:
        result = analyze_session_file(sys.argv[1])
        if result:
            print(f"\nSession: {result['session_id']}")
            print(f"D trajectory: {result['d_trajectory']}")
            print(f"\nTransitions:")
            for t in result['transitions']:
                symbol = '↑' if t['type'] != 'collapse' else '↓'
                print(f"  {symbol} Turn {t['turn']}: {t['type']} "
                      f"D {t['d_before']:.3f} → {t['d_after']:.3f}")
            print(f"\n{result['dynamics_interpretation']}")
        else:
            print(f"Cannot analyze: {sys.argv[1]}")
    else:
        print("Usage:")
        print("  py e0_phase_transition.py --all              Analyze all sessions")
        print("  py e0_phase_transition.py sessions/file.json Analyze one session")
