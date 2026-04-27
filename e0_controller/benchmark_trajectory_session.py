"""C282 — Trajectory Session Benchmark (Stage 2: Real Sessions).

Stage 2 of the trajectory validation plan.
Runs an actual interactive session (build_session → cmd_run × N rounds)
and observes whether the trajectory adaptation machinery from C277–C281
fires in practice.

Scientific questions
--------------------
  Q1: Does classify_trajectory_experience() ever leave "exploratory"?
      Requires ≥ 3 revisit events on the same PathSignature.
      Depends on real landscape topology (community count) and session length.

  Q2: Does adapt_from_trajectory_experience() ever return "volatile"?
      Requires trajectory_surprise_rate ≥ 0.3 and ≥ 3 revisit events.

  Q3: Does the trajectory escalation (low_quality_warning in plan()) fire?
      Detectable from round.reason starting with "Trajectory pattern".

  Q4: What is the effective signature diversity?
      unique_signatures / rounds_run → collision rate.
      High diversity (→ 1.0) means the landscape is too sparse for
      trajectory patterns to form within typical session lengths.

Stage context
-------------
  Stage 1 (C279): Validated that the classifier discriminates stable/volatile/
    exploratory given controlled TrajectoryRecord sequences.
  Stage 2 (C282): Real sessions — topology not hand-crafted.

Honest finding: "adaptation never fires" is a valid result.
If the real landscape has too many communities (large signature space),
revisit patterns cannot accumulate within typical session lengths.
That is a regime boundary, not a failure.

Usage
-----
  py -3 -m e0_controller.benchmark_trajectory_session
  py -3 -m e0_controller.benchmark_trajectory_session --rounds 50 --steps 15
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from e0_controller.trajectory import PathSignature, TrajectoryHistorization


# ══════════════════════════════════════════════════════════════════
# Result types
# ══════════════════════════════════════════════════════════════════


@dataclass
class SignatureProfile:
    """Per-signature observation from a real session."""
    signature: PathSignature
    trace_load: int
    trace_quality: float
    confirmations: int
    surprises: int

    @property
    def revisit_events(self) -> int:
        return self.confirmations + self.surprises

    @property
    def surprise_rate(self) -> float:
        if self.revisit_events == 0:
            return 0.0
        return self.surprises / self.revisit_events


@dataclass
class SessionBenchmarkResult:
    """Aggregate result of one Stage 2 real-session benchmark run.

    All observations are derived from state.trajectory_hist and
    state.history after N rounds of cmd_run().
    """

    # Session parameters
    rounds_run: int
    steps_per_round: int

    # Landscape topology
    communities_count: int

    # Trajectory statistics
    unique_signatures: int
    experience_category: str       # classify_trajectory_experience()
    adaptation: dict               # adapt_from_trajectory_experience()
    trajectory_surprise_rate: float
    total_revisit_events: int      # sum of (conf + surp) across all signatures

    # Escalation
    trajectory_escalation_fired: bool
    escalation_count: int          # rounds where plan() returned "Trajectory pattern..."
    escalation_details: List[Tuple[int, str]] = field(default_factory=list)

    # Per-signature breakdown
    per_signature: List[SignatureProfile] = field(default_factory=list)

    @property
    def signature_diversity(self) -> float:
        """unique_signatures / rounds_run.

        → 1.0: every round produced a new signature (no revisits).
        → 0.0: all rounds produced the same signature.
        High diversity means the adaptation machinery cannot accumulate
        evidence because patterns don't repeat.
        """
        if self.rounds_run == 0:
            return 0.0
        return min(1.0, self.unique_signatures / self.rounds_run)

    @property
    def collision_rate(self) -> float:
        """Fraction of rounds that revisited a known signature.

        collision_rate = 1 - signature_diversity.
        High collision rate means patterns repeat → trajectory learning
        can accumulate meaningful evidence.
        """
        return 1.0 - self.signature_diversity

    def summary(self) -> str:
        lines = [
            "═" * 60,
            "C282 — Trajectory Session Benchmark (Stage 2)",
            "═" * 60,
            "",
            "── Session parameters ───────────────────────────────",
            f"  rounds_run       : {self.rounds_run}",
            f"  steps_per_round  : {self.steps_per_round}",
            f"  communities      : {self.communities_count}",
            "",
            "── Trajectory statistics ────────────────────────────",
            f"  unique_signatures: {self.unique_signatures}",
            f"  signature_diversity  : {self.signature_diversity:.3f}  "
            f"(1.0 = all unique, 0.0 = one pattern repeated)",
            f"  collision_rate       : {self.collision_rate:.3f}  "
            f"(fraction of rounds that revisited a signature)",
            f"  total_revisit_events : {self.total_revisit_events}",
            f"  trajectory_surprise_rate: {self.trajectory_surprise_rate:.3f}",
            "",
            "── Adaptation status ────────────────────────────────",
            f"  experience_category : {self.experience_category}",
            f"  adaptation params   : quality_threshold={self.adaptation.get('quality_threshold')}, "
            f"step_multiplier={self.adaptation.get('step_multiplier')}",
            "",
            "── Escalation ───────────────────────────────────────",
            f"  trajectory_escalation_fired: {self.trajectory_escalation_fired}",
            f"  escalation_count           : {self.escalation_count}",
        ]

        if self.escalation_details:
            lines.append("  escalation rounds:")
            for rnum, reason in self.escalation_details:
                lines.append(f"    Round {rnum}: {reason[:80]}...")

        if self.per_signature:
            lines += [
                "",
                "── Per-signature breakdown ──────────────────────────",
            ]
            for sp in sorted(self.per_signature, key=lambda x: -x.revisit_events):
                lines.append(
                    f"  sig={sp.signature}  "
                    f"load={sp.trace_load}  q={sp.trace_quality:+.2f}  "
                    f"conf={sp.confirmations}  surp={sp.surprises}  "
                    f"events={sp.revisit_events}  surp_rate={sp.surprise_rate:.2f}"
                )

        lines += [
            "",
            "── Interpretation ───────────────────────────────────",
        ]
        if self.experience_category == "exploratory":
            lines.append(
                f"  FINDING: Session remained 'exploratory' after {self.rounds_run} rounds."
            )
            lines.append(
                f"  With {self.communities_count} communities and "
                f"{self.unique_signatures} unique signatures in {self.rounds_run} rounds,"
            )
            lines.append(
                "  the signature space is too large for revisit events to accumulate."
            )
            lines.append(
                "  Stage 2 regime boundary: trajectory adaptation requires either"
            )
            lines.append(
                "  longer sessions or a landscape with fewer active communities."
            )
        elif self.experience_category == "stable":
            lines.append(
                f"  FINDING: Session reached 'stable' after {self.rounds_run} rounds."
            )
            lines.append(
                "  Trajectory patterns are consistent — adaptation defaults hold."
            )
        elif self.experience_category == "volatile":
            lines.append(
                f"  FINDING: Session reached 'volatile' after {self.rounds_run} rounds."
            )
            lines.append(
                "  Trajectory patterns are inconsistent — adaptive sensitivity active."
            )

        if self.trajectory_escalation_fired:
            lines.append(
                f"  ESCALATION: low_quality_warning fired {self.escalation_count} time(s) — "
                "trajectory adaptation is live in this session."
            )
        else:
            lines.append(
                "  ESCALATION: low_quality_warning did not fire — "
                "trajectory escalation is reachable but dormant in this session."
            )

        lines.append("═" * 60)
        return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════
# Core benchmark function
# ══════════════════════════════════════════════════════════════════


def run_session_benchmark(
    rounds: int = 30,
    steps_per_round: int = 15,
) -> SessionBenchmarkResult:
    """Run a real interactive session and return trajectory observations.

    Builds a cold-start session (no persisted state), runs *rounds* rounds
    of cmd_run(), then extracts all trajectory-relevant observables.

    Args:
        rounds: Number of cmd_run() rounds to execute.
        steps_per_round: Navigation steps per round.

    Returns:
        SessionBenchmarkResult with all observables populated.
    """
    from e0_controller.interactive_session import build_session, cmd_run

    state = build_session(steps_per_round=steps_per_round)
    cmd_run(state, rounds)

    th: TrajectoryHistorization = state.trajectory_hist
    rounds_run = len(state.history)

    # Community count
    communities_count = len(state.communities) if state.communities else 0

    # Per-signature breakdown
    known_sigs = th.known_signatures()
    per_signature: List[SignatureProfile] = []
    for sig in known_sigs:
        conf = th._confirmations.get(sig, 0)
        surp = th._surprises.get(sig, 0)
        per_signature.append(SignatureProfile(
            signature=sig,
            trace_load=th.trace_load(sig),
            trace_quality=th.trace_quality(sig),
            confirmations=conf,
            surprises=surp,
        ))

    total_revisit_events = sum(sp.revisit_events for sp in per_signature)

    # Escalation detection — plan() returns reason starting with
    # "Trajectory pattern" when low_quality_warning fires
    escalation_details: List[Tuple[int, str]] = []
    for r in state.history:
        if r.reason and r.reason.startswith("Trajectory pattern"):
            escalation_details.append((r.round_num, r.reason))

    return SessionBenchmarkResult(
        rounds_run=rounds_run,
        steps_per_round=steps_per_round,
        communities_count=communities_count,
        unique_signatures=len(known_sigs),
        experience_category=th.classify_trajectory_experience(),
        adaptation=th.adapt_from_trajectory_experience(),
        trajectory_surprise_rate=th.trajectory_surprise_rate(),
        total_revisit_events=total_revisit_events,
        trajectory_escalation_fired=len(escalation_details) > 0,
        escalation_count=len(escalation_details),
        escalation_details=escalation_details,
        per_signature=per_signature,
    )


# ══════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════


def main() -> None:
    parser = argparse.ArgumentParser(
        description="C282 — Trajectory Session Benchmark (Stage 2)"
    )
    parser.add_argument(
        "--rounds", type=int, default=30,
        help="Number of cmd_run() rounds (default: 30)",
    )
    parser.add_argument(
        "--steps", type=int, default=15,
        help="Navigation steps per round (default: 15)",
    )
    args = parser.parse_args()

    print(f"Running {args.rounds} rounds × {args.steps} steps/round …")
    result = run_session_benchmark(rounds=args.rounds, steps_per_round=args.steps)
    print(result.summary())

    if result.experience_category == "exploratory" and not result.trajectory_escalation_fired:
        sys.exit(0)   # Valid result — not a failure


if __name__ == "__main__":
    main()
