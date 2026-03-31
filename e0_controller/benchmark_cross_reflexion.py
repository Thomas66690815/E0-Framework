"""
C69 — Cross-Reflexion Benchmark: Edge Creation vs Edge Copying
================================================================
Compares two coupling strategies on the same 5 domain pairings:

  Mode A: knowledge_exchange_turn (C61) — copy existing edges
  Mode B: cross_reflexion_turn (C62)    — create new edges from experience

The central question (Multiverse Open Question #4):
  Does foreign-experience-based edge CREATION outperform simple
  edge COPYING?  On which domain pairings?  By how much?

Metrics per pairing:
  - novelty_rate:  fraction of turns producing NoveltyGate SUCCESS
  - coupling_edges: total coupling topology growth
  - converged:     did the pairing stall?

The benchmark runs each mode independently on fresh landscapes,
then produces a comparative summary showing deltas.

Usage:
  from e0_controller.benchmark_cross_reflexion import run_comparison_benchmark
  result = run_comparison_benchmark()
  print(result.summary())
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

from e0_controller.multiverse import MultiverseController, Universe
from e0_controller.benchmark_multiverse import (
    PairingResult,
    PAIRINGS,
    knowledge_exchange_turn,
)
from e0_controller.benchmark_domain_invariance import DomainSpec
from e0_controller.cross_reflexion import cross_reflexion_turn


# ══════════════════════════════════════════════
# Result types
# ══════════════════════════════════════════════

@dataclass
class ComparisonPairingResult:
    """Side-by-side result for one pairing under both strategies."""
    name: str
    exchange: PairingResult    # knowledge_exchange_turn
    reflexion: PairingResult   # cross_reflexion_turn

    @property
    def novelty_delta(self) -> float:
        """Positive = cross-reflexion wins."""
        return self.reflexion.novelty_rate - self.exchange.novelty_rate


@dataclass
class ComparisonBenchmarkResult:
    """Full comparison across all pairings."""
    pairings: List[ComparisonPairingResult] = field(default_factory=list)

    @property
    def exchange_avg_novelty(self) -> float:
        if not self.pairings:
            return 0.0
        return sum(p.exchange.novelty_rate for p in self.pairings) / len(self.pairings)

    @property
    def reflexion_avg_novelty(self) -> float:
        if not self.pairings:
            return 0.0
        return sum(p.reflexion.novelty_rate for p in self.pairings) / len(self.pairings)

    @property
    def avg_novelty_delta(self) -> float:
        return self.reflexion_avg_novelty - self.exchange_avg_novelty

    @property
    def reflexion_wins(self) -> int:
        return sum(1 for p in self.pairings if p.novelty_delta > 0)

    @property
    def exchange_wins(self) -> int:
        return sum(1 for p in self.pairings if p.novelty_delta < 0)

    def summary(self) -> str:
        lines = [
            "Cross-Reflexion Benchmark: Edge Copying vs Edge Creation",
            "=" * 72,
            f"{'Pairing':<35} {'Exch':>6} {'Refl':>6} {'Δ':>6} {'Winner':>8}",
            "-" * 72,
        ]
        for p in self.pairings:
            delta = p.novelty_delta
            winner = "refl" if delta > 0 else ("exch" if delta < 0 else "tie")
            lines.append(
                f"{p.name:<35} "
                f"{p.exchange.novelty_rate:>5.0%} "
                f"{p.reflexion.novelty_rate:>5.0%} "
                f"{delta:>+5.0%} "
                f"{winner:>8}"
            )
        lines.append("-" * 72)
        lines.append(
            f"Avg novelty:  exchange={self.exchange_avg_novelty:.0%}  "
            f"reflexion={self.reflexion_avg_novelty:.0%}  "
            f"Δ={self.avg_novelty_delta:+.0%}"
        )
        lines.append(
            f"Wins: reflexion={self.reflexion_wins}  "
            f"exchange={self.exchange_wins}  "
            f"tie={len(self.pairings) - self.reflexion_wins - self.exchange_wins}"
        )
        return "\n".join(lines)


# ══════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════

def _spec_to_universe(spec: DomainSpec) -> Universe:
    """Convert a DomainSpec into a Universe."""
    return Universe(
        name=spec.name,
        landscape=spec.landscape,
        execute_fn=spec.execute_fn,
        start=spec.start,
        goal=spec.goal,
    )


def _run_pairing_with_turn_fn(
    name: str,
    builder_a: Callable,
    builder_b: Callable,
    turn_fn: Callable,
    max_turns: int = 12,
    convergence_window: int = 3,
) -> PairingResult:
    """Run one pairing with a given turn function."""
    spec_a = builder_a()
    spec_b = builder_b()
    u_a = _spec_to_universe(spec_a)
    u_b = _spec_to_universe(spec_b)

    ctrl = MultiverseController(
        u_a, u_b,
        convergence_window=convergence_window,
    )
    mv = ctrl.run(max_turns=max_turns, turn_fn=turn_fn)

    return PairingResult(
        name=name,
        domain_a=spec_a.name,
        domain_b=spec_b.name,
        total_turns=mv.total_turns,
        total_novelty=mv.total_novelty,
        novelty_rate=mv.novelty_rate,
        converged=mv.converged,
        convergence_turn=mv.convergence_turn,
        divergence_count=mv.divergence_count,
        novelty_edges_added=mv.novelty_edges_added,
        coupling_edge_count=len(ctrl.coupling._delta),
    )


# ══════════════════════════════════════════════
# Single comparison
# ══════════════════════════════════════════════

def run_comparison_pairing(
    name: str,
    builder_a: Callable,
    builder_b: Callable,
    max_turns: int = 12,
    convergence_window: int = 3,
) -> ComparisonPairingResult:
    """Run one pairing under both strategies (fresh landscapes each)."""
    exchange = _run_pairing_with_turn_fn(
        name, builder_a, builder_b,
        knowledge_exchange_turn,
        max_turns=max_turns,
        convergence_window=convergence_window,
    )
    reflexion = _run_pairing_with_turn_fn(
        name, builder_a, builder_b,
        cross_reflexion_turn,
        max_turns=max_turns,
        convergence_window=convergence_window,
    )
    return ComparisonPairingResult(
        name=name,
        exchange=exchange,
        reflexion=reflexion,
    )


# ══════════════════════════════════════════════
# Full benchmark
# ══════════════════════════════════════════════

def run_comparison_benchmark(
    max_turns: int = 12,
    convergence_window: int = 3,
) -> ComparisonBenchmarkResult:
    """Run all 5 pairings under both strategies."""
    result = ComparisonBenchmarkResult()
    for name, builder_a, builder_b in PAIRINGS:
        cp = run_comparison_pairing(
            name, builder_a, builder_b,
            max_turns=max_turns,
            convergence_window=convergence_window,
        )
        result.pairings.append(cp)
    return result
