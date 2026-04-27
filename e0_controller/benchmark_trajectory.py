"""C279 — Trajectory Experience Benchmark (Stage 1).

Validates that classify_trajectory_experience() discriminates between
three synthetic session regimes.

This is Stage 1 of the C279 instrumentation plan:
  Stage 1 (C279): Synthetic — controlled sessions with known expected
    classifications.  Does the classifier discriminate stable/volatile/
    exploratory at all?  Uses programmatic TrajectoryRecord sequences
    (no navigate() or run_multidomain_cycle() — fast and deterministic).
  Stage 2 (future): Semi-synthetic on public knowledge graphs
    (ConceptNet/WordNet/arXiv citation networks) where topology is not
    hand-crafted and friction emerges from real structure.

Key design constraint (identified in C279 analysis):
  2-community landscapes produce at most 4 distinct signatures:
  {(0,), (1,), (0,1), (1,0)}.  Birthday paradox: 20 rounds over 4
  signatures → ~5 visits per signature → ~4 revisit events each →
  reliable classification.
  4+ communities → exponentially larger signature space → revisits
  accumulate too slowly for classification within typical session lengths.

Session regimes:
  stable:      consistent quality predictions hold → surprise_rate < 0.3
  volatile:    quality predictions frequently contradicted → rate ≥ 0.3
  exploratory: too few revisit events (< 3) for classification

Usage:
  from e0_controller.benchmark_trajectory import run_all_benchmarks
  result = run_all_benchmarks()
  print(result.summary())
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from e0_controller.trajectory import (
    PathSignature,
    TrajectoryHistorization,
    TrajectoryRecord,
)


# ══════════════════════════════════════════════════════════════════
# Result types
# ══════════════════════════════════════════════════════════════════

@dataclass
class SignatureStats:
    """Per-signature breakdown within a benchmark regime."""
    signature: PathSignature
    trace_load: int
    trace_quality: float
    confirmations: int
    surprises: int

    @property
    def events(self) -> int:
        return self.confirmations + self.surprises

    @property
    def surprise_rate(self) -> float:
        return self.surprises / self.events if self.events > 0 else 0.0


@dataclass
class RegimeResult:
    """Result for one synthetic session regime."""
    regime: str                       # 'stable', 'volatile', 'exploratory'
    expected_classification: str      # what we expect
    total_inscriptions: int
    total_revisit_events: int
    trajectory_surprise_rate: float
    classification: str               # actual classify_trajectory_experience()
    per_signature: List[SignatureStats] = field(default_factory=list)

    @property
    def matches_expectation(self) -> bool:
        return self.classification == self.expected_classification


@dataclass
class TrajectoryBenchmarkResult:
    """Full benchmark result across all three regimes."""
    regimes: List[RegimeResult] = field(default_factory=list)

    @property
    def all_match(self) -> bool:
        return all(r.matches_expectation for r in self.regimes)

    def summary(self) -> str:
        lines = [
            "",
            "═" * 72,
            "  TRAJECTORY EXPERIENCE BENCHMARK  (C279 Stage 1)",
            "═" * 72,
            f"  {'Regime':<14} {'Inscr':>6} {'Events':>7} "
            f"{'SurprRate':>10} {'Classification':<16} {'Expected':<16} {'Match':>5}",
            "  " + "─" * 70,
        ]
        for r in self.regimes:
            match = "✓" if r.matches_expectation else "✗"
            lines.append(
                f"  {r.regime:<14} {r.total_inscriptions:>6} "
                f"{r.total_revisit_events:>7} "
                f"{r.trajectory_surprise_rate:>10.3f} "
                f"{r.classification:<16} {r.expected_classification:<16} "
                f"{match:>5}"
            )
        lines.append("  " + "─" * 70)

        if self.all_match:
            lines.append(
                f"\n  All {len(self.regimes)} regimes correctly classified.  "
                "Instrument discriminates as expected."
            )
        else:
            failed = [r.regime for r in self.regimes if not r.matches_expectation]
            lines.append(
                f"\n  MISMATCH in: {', '.join(failed)}.  "
                "Heuristic thresholds may need recalibration."
            )

        # Per-regime detail
        for r in self.regimes:
            lines.append(
                f"\n  ── {r.regime.upper()} regime "
                f"(expected: '{r.expected_classification}') ──"
            )
            if not r.per_signature:
                lines.append("    (no signatures)")
                continue
            lines.append(
                f"  {'Signature':<14} {'Load':>5} {'Quality':>8} "
                f"{'Conf':>5} {'Surp':>5} {'Rate':>7}"
            )
            for s in sorted(r.per_signature, key=lambda x: x.signature):
                lines.append(
                    f"  {str(s.signature):<14} {s.trace_load:>5} "
                    f"{s.trace_quality:>8.3f} "
                    f"{s.confirmations:>5} {s.surprises:>5} "
                    f"{s.surprise_rate:>7.3f}"
                )

        lines.append("\n" + "═" * 72)
        return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════
# Synthetic session patterns
# ══════════════════════════════════════════════════════════════════

def _stable_session() -> List[TrajectoryRecord]:
    """20-round session that produces 'stable' classification.

    Two signatures from a 2-community landscape:
      (0, 1): 8 productive, then 2 stagnant
      (0,):   8 stagnant,   then 2 productive

    Derivation for (0, 1) (p=productive, s=stagnant):
      First p: U=1,F=0, quality=0.5.  No event.
      p×7 more: 7 CONF (quality rises to ~0.889).
      s: quality=0.889→predict p→actual s→SURP.  U=8,F=1, quality=0.7.
      s: quality=0.7→predict p→actual s→SURP.    U=8,F=2, quality=0.545.
      Events for (0,1): 7 CONF + 2 SURP = 9.

    Derivation for (0,) (s=stagnant, p=productive):
      First s: U=0,F=1, quality=-0.5.  No event.
      s×7 more: 7 CONF (quality falls to ~-0.889).
      p: quality=-0.889→predict s→actual p→SURP.  U=1,F=8, quality=-0.7.
      p: quality=-0.7→predict s→actual p→SURP.    U=2,F=8, quality=-0.545.
      Events for (0,): 7 CONF + 2 SURP = 9.

    Totals: 14 CONF + 4 SURP = 18 events.  surprise_rate = 4/18 ≈ 0.222 < 0.3 → stable.
    """
    records: List[TrajectoryRecord] = []
    for _ in range(8):
        records.append(TrajectoryRecord((0, 1), "explore", 0.05, 2))  # productive
    for _ in range(2):
        records.append(TrajectoryRecord((0, 1), "explore", 0.0,  0))  # stagnant
    for _ in range(8):
        records.append(TrajectoryRecord((0,),   "explore", 0.0,  0))  # stagnant
    for _ in range(2):
        records.append(TrajectoryRecord((0,),   "explore", 0.05, 1))  # productive
    return records


def _volatile_session() -> List[TrajectoryRecord]:
    """20-round session that produces 'volatile' classification.

    One signature alternates productive / stagnant, so every stagnant
    inscription surprises the positive-quality predictor and vice-versa.

    Derivation for (0, 1) with pattern p,s,p,s,...:
      i=1 (p): U=1,F=0, quality=0.5.  No event.
      i=2 (s): quality=0.5→predict p→actual s→SURP.  U=1,F=1, quality=0.
      i=3 (p): quality=0→predict p→actual p→CONF.    U=2,F=1, quality=0.25.
      i=4 (s): quality=0.25→predict p→actual s→SURP. U=2,F=2, quality=0.
      …pattern stabilises: quality oscillates around 0; every stagnant → SURP,
       every productive → CONF (since quality ≥ 0 after each productive step).
      After 20 inscriptions (10p, 10s): 9 CONF + 10 SURP = 19 events.
      surprise_rate = 10/19 ≈ 0.526 ≥ 0.3 → volatile.
    """
    records: List[TrajectoryRecord] = []
    for i in range(20):
        if i % 2 == 0:
            records.append(TrajectoryRecord((0, 1), "explore", 0.05, 2))  # productive
        else:
            records.append(TrajectoryRecord((0, 1), "explore", 0.0,  0))  # stagnant
    return records


def _exploratory_session() -> List[TrajectoryRecord]:
    """4-round session that stays 'exploratory'.

    Four distinct signatures inscribed exactly once: no revisits, so
    the total revisit event count = 0 < 3 threshold → exploratory.
    Represents a genuinely novel session where every round traverses
    new territory with no repeated path shapes.
    """
    return [
        TrajectoryRecord((0,),    "explore", 0.05, 0),
        TrajectoryRecord((1,),    "explore", 0.02, 0),
        TrajectoryRecord((0, 1),  "explore", 0.03, 1),
        TrajectoryRecord((1, 0),  "explore", 0.01, 1),
    ]


# ══════════════════════════════════════════════════════════════════
# Runner
# ══════════════════════════════════════════════════════════════════

def _run_regime(
    name: str,
    records: List[TrajectoryRecord],
    expected: str,
) -> RegimeResult:
    """Replay a scripted session through TrajectoryHistorization and collect stats."""
    th = TrajectoryHistorization()
    for rec in records:
        th.inscribe(rec)

    total_events = sum(
        th._confirmations.get(sig, 0) + th._surprises.get(sig, 0)
        for sig in th.known_signatures()
    )
    rate = th.trajectory_surprise_rate()
    classification = th.classify_trajectory_experience()

    per_sig: List[SignatureStats] = []
    for sig in th.known_signatures():
        confs = th._confirmations.get(sig, 0)
        surps = th._surprises.get(sig, 0)
        per_sig.append(SignatureStats(
            signature=sig,
            trace_load=th.trace_load(sig),
            trace_quality=th.trace_quality(sig),
            confirmations=confs,
            surprises=surps,
        ))

    return RegimeResult(
        regime=name,
        expected_classification=expected,
        total_inscriptions=len(records),
        total_revisit_events=total_events,
        trajectory_surprise_rate=rate,
        classification=classification,
        per_signature=per_sig,
    )


def run_all_benchmarks() -> TrajectoryBenchmarkResult:
    """Run all three synthetic regime benchmarks and return a combined result."""
    result = TrajectoryBenchmarkResult()
    result.regimes.append(
        _run_regime("stable",      _stable_session(),      "stable")
    )
    result.regimes.append(
        _run_regime("volatile",    _volatile_session(),    "volatile")
    )
    result.regimes.append(
        _run_regime("exploratory", _exploratory_session(), "exploratory")
    )
    return result


# ══════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════

def main() -> None:
    result = run_all_benchmarks()
    print(result.summary())
    if not result.all_match:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
