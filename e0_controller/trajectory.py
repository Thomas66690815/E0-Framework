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

    C278 — Experience Classification (mirrors C186/C187 at edge level):
    At inscription time, if a signature has prior history (load ≥ 1),
    we predict the expected outcome from trace_quality and compare
    to the actual outcome.  Matches accumulate as confirmations;
    mismatches accumulate as surprises.

    trajectory_surprise_rate() is the trajectory-level analogue of
    surprise_rate() in Historization — a global signal for whether
    trajectory predictions are reliable.

    classify_trajectory_experience() maps this signal to the same
    three categories as classify_experience():
        'stable'      — low trajectory surprise rate (< 30%)
        'volatile'    — high trajectory surprise rate (≥ 30%)
        'exploratory' — fewer than 3 revisit events (insufficient data)
    """

    def __init__(self) -> None:
        self._traces: Dict[PathSignature, Tuple[int, int]] = {}
        # C278: per-signature revisit statistics
        self._confirmations: Dict[PathSignature, int] = {}
        self._surprises: Dict[PathSignature, int] = {}

    def inscribe(self, record: TrajectoryRecord) -> None:
        """Record one round's outcome for its signature.

        C278: If the signature has prior history (load ≥ 1), record
        whether the actual outcome confirms or surprises the prediction
        derived from trace_quality.  First observations are never
        tracked — there is no prior to compare against.
        """
        sig = record.signature
        u, f = self._traces.get(sig, (0, 0))

        # C278: track prediction accuracy on revisits
        if u + f >= 1:
            q = (u - f) / (u + f + 1)
            predicted_productive = q >= 0.0
            actual_productive = record.outcome in ("productive", "improving")
            if predicted_productive == actual_productive:
                self._confirmations[sig] = self._confirmations.get(sig, 0) + 1
            else:
                self._surprises[sig] = self._surprises.get(sig, 0) + 1

        if record.outcome in ("productive", "improving"):
            self._traces[sig] = (u + 1, f)
        else:
            self._traces[sig] = (u, f + 1)

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

    # --- Experience Classification (C278) ---

    def trajectory_surprise_rate(self) -> float:
        """Global fraction of trajectory revisits that contradicted the prediction.

        Analogous to Historization.surprise_rate() at edge level.
        Returns float in [0, 1].  0.0 when no revisit data exists.
        """
        total_conf = sum(self._confirmations.values())
        total_surp = sum(self._surprises.values())
        total = total_conf + total_surp
        if total < 1e-12:
            return 0.0
        return total_surp / total

    def classify_trajectory_experience(self) -> str:
        """Classify trajectory reliability from accumulated revisit data.

        C278: Trajectory-level analogue of Historization.classify_experience().

        Returns one of:
            'stable'      — low surprise rate (< 30%), predictions hold
            'volatile'    — high surprise rate (≥ 30%), patterns are unreliable
            'exploratory' — fewer than 3 revisit events, insufficient data

        The 'exploratory' guard mirrors the edge-level threshold in
        classify_experience() (total < 3.0).  Trajectory signatures
        accumulate data more slowly than edges, so this guard is
        critical: a single mismatched revisit should not trigger 'volatile'.
        """
        total_conf = sum(self._confirmations.values())
        total_surp = sum(self._surprises.values())
        total = total_conf + total_surp
        if total < 3:
            return "exploratory"
        sr = total_surp / total
        if sr >= 0.3:
            return "volatile"
        return "stable"

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

    def stable_quality_profile(self, min_load: int = 1) -> str:
        """Second axis of the (predictability × quality) profile.

        C283: classify_trajectory_experience() measures *predictability*
        (stable / volatile / exploratory).  stable_quality_profile() measures
        the *quality* of that stability — i.e., what kind of outcomes the
        stable patterns actually produce.

        Only signatures with trace_load ≥ min_load contribute.
        Default min_load=1 includes every observed signature.

        Returns one of:
            'productive' — mean trace_quality > 0: patterns are net positive
                           (stable-and-productive: healthy domain)
            'stagnant'   — mean trace_quality ≤ 0: patterns are net negative
                           (stable-and-stagnant: chronic trap — e.g. the (0,3,0)
                           structural pendulum documented in C282)
            'unknown'    — no signatures with sufficient load observed yet

        Relationship to open_thread 'Stable Underdetermination' (C282):
            classify_trajectory_experience() returns 'stable' for both healthy
            domains and chronic traps.  This method breaks that ambiguity.
            Used by adapt_from_trajectory_experience() to differentiate the
            two stable regimes at the adaptation level.
        """
        qualifying = [
            sig for sig in self._traces
            if self.trace_load(sig) >= min_load
        ]
        if not qualifying:
            return "unknown"
        mean_q = sum(self.trace_quality(sig) for sig in qualifying) / len(qualifying)
        if mean_q > 0.0:
            return "productive"
        return "stagnant"

    def adapt_from_trajectory_experience(self) -> dict:
        """Return threshold adaptations for plan() based on trajectory experience.

        C280: Trajectory-level analogue of C188 adapt_from_experience().
        C283: Extended to differentiate stable-productive from stable-stagnant
              using stable_quality_profile() — closing the 'Stable Underdetermination'
              open thread (C282).

        Maps classify_trajectory_experience() × stable_quality_profile() to
        concrete plan() parameters:

            volatile:
                quality_threshold=-0.15 (lower → fires sooner, patterns are
                unreliable so catch problems early), step_multiplier=1.5
                (moderate response — signal is noisy, avoid over-committing)

            stable + productive (healthy domain):
                quality_threshold=-0.3 (default — signal is trustworthy),
                step_multiplier=2.0 (decisive response — act on reliable signal)

            stable + stagnant (chronic trap — e.g. (0,3,0) structural pendulum):
                quality_threshold=-0.1 (fires even sooner — stagnation is
                reliably confirmed, not a noise artifact), step_multiplier=3.0
                (strong push to break the pattern — stable-stagnant requires
                more aggressive intervention than volatile, because the trap
                is structural, not random)

            stable + unknown:
                same as stable + productive (no negative evidence yet)

            exploratory:
                same as stable + productive (no evidence to deviate from defaults)

        Returns:
            dict with keys:
                'quality_threshold': float — passed to low_quality_warning()
                'step_multiplier':   float — multiplied by base_steps in plan()
                'experience':        str   — classify_trajectory_experience() result
                'quality_profile':   str   — stable_quality_profile() result
        """
        experience = self.classify_trajectory_experience()
        quality_profile = self.stable_quality_profile()

        if experience == "volatile":
            return {
                "quality_threshold": -0.15,
                "step_multiplier": 1.5,
                "experience": experience,
                "quality_profile": quality_profile,
            }
        if experience == "stable" and quality_profile == "stagnant":
            return {
                "quality_threshold": -0.1,
                "step_multiplier": 3.0,
                "experience": experience,
                "quality_profile": quality_profile,
            }
        # stable+productive, stable+unknown, exploratory: E₀-safe defaults
        return {
            "quality_threshold": -0.3,
            "step_multiplier": 2.0,
            "experience": experience,
            "quality_profile": quality_profile,
        }
