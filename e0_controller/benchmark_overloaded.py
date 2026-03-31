"""
C70 — OVERLOADED Benchmark: Peer Consultation × 10 Domains
=============================================================
Runs the same 10 C53 domains under two modes:

  Mode A: BASELINE     — no peer_fn, standard E₀ navigation
  Mode B: PEER         — peer_fn from a pre-experienced advisor

The central question (Multiverse Open Question #5):
  How does peer consultation affect domain-scale performance?
  Does OVERLOADED escalation fire on wide topologies?
  Does it self-resolve as experience builds?

The peer strategy: build a separate E₀ controller that pre-navigates
the domain for 30 cycles, accumulating historization.  Its trace
quality informs the peer_fn: recommend the neighbor with the best
trace quality in the advisor's landscape (if the state exists there).

Usage:
  from e0_controller.benchmark_overloaded import run_overloaded_benchmark
  result = run_overloaded_benchmark()
  print(result.summary())
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller, EscalationType, RunTrace
from e0_controller.evaluation import evaluate_run, RunEvaluation
from e0_controller.benchmark_domain_invariance import (
    DomainSpec,
    build_all_domains,
    ALL_DOMAINS,
)


# ══════════════════════════════════════════════
# Result types
# ══════════════════════════════════════════════

@dataclass
class OverloadDomainResult:
    """Result of running one domain in one mode."""
    domain: str
    mode: str                 # "baseline" | "peer"
    goal_reached: bool
    steps: int
    rating: str
    escalations: int
    overload_count: int       # OVERLOADED escalations specifically
    revisits: int
    success_rate: float
    efficiency: float


@dataclass
class OverloadComparisonResult:
    """Side-by-side result for one domain under both modes."""
    domain: str
    baseline: OverloadDomainResult
    peer: OverloadDomainResult

    @property
    def step_delta(self) -> int:
        """Negative = peer is faster."""
        return self.peer.steps - self.baseline.steps

    @property
    def overload_delta(self) -> int:
        """Negative = peer has fewer overloads (expected)."""
        return self.peer.overload_count - self.baseline.overload_count


@dataclass
class OverloadBenchmarkResult:
    """Full benchmark across all 10 domains."""
    comparisons: List[OverloadComparisonResult] = field(default_factory=list)

    @property
    def baseline_avg_steps(self) -> float:
        if not self.comparisons:
            return 0.0
        return sum(c.baseline.steps for c in self.comparisons) / len(self.comparisons)

    @property
    def peer_avg_steps(self) -> float:
        if not self.comparisons:
            return 0.0
        return sum(c.peer.steps for c in self.comparisons) / len(self.comparisons)

    @property
    def baseline_overload_total(self) -> int:
        return sum(c.baseline.overload_count for c in self.comparisons)

    @property
    def peer_overload_total(self) -> int:
        return sum(c.peer.overload_count for c in self.comparisons)

    @property
    def peer_improves_count(self) -> int:
        """Domains where peer has fewer steps than baseline."""
        return sum(1 for c in self.comparisons if c.step_delta < 0)

    @property
    def baseline_goal_rate(self) -> float:
        if not self.comparisons:
            return 0.0
        return sum(1 for c in self.comparisons if c.baseline.goal_reached) / len(self.comparisons)

    @property
    def peer_goal_rate(self) -> float:
        if not self.comparisons:
            return 0.0
        return sum(1 for c in self.comparisons if c.peer.goal_reached) / len(self.comparisons)

    def summary(self) -> str:
        lines = [
            "OVERLOADED Benchmark: Baseline vs Peer Consultation",
            "=" * 80,
            f"{'Domain':<28} {'B.Steps':>7} {'P.Steps':>7} {'Δ':>4} "
            f"{'B.OL':>4} {'P.OL':>4} {'B.Esc':>5} {'P.Esc':>5} "
            f"{'B.Rate':>6} {'P.Rate':>6}",
            "-" * 80,
        ]
        for c in self.comparisons:
            b, p = c.baseline, c.peer
            delta = c.step_delta
            delta_s = f"{delta:+d}" if delta != 0 else "="
            lines.append(
                f"{c.domain:<28} "
                f"{b.steps:>7} {p.steps:>7} {delta_s:>4} "
                f"{b.overload_count:>4} {p.overload_count:>4} "
                f"{b.escalations:>5} {p.escalations:>5} "
                f"{b.rating:>6} {p.rating:>6}"
            )
        lines.append("-" * 80)
        lines.append(
            f"Avg steps:  baseline={self.baseline_avg_steps:.1f}  "
            f"peer={self.peer_avg_steps:.1f}  |  "
            f"Overloads: baseline={self.baseline_overload_total}  "
            f"peer={self.peer_overload_total}"
        )
        lines.append(
            f"Goal rate:  baseline={self.baseline_goal_rate:.0%}  "
            f"peer={self.peer_goal_rate:.0%}  |  "
            f"Peer improves: {self.peer_improves_count}/{len(self.comparisons)}"
        )
        return "\n".join(lines)


# ══════════════════════════════════════════════
# Experienced peer construction
# ══════════════════════════════════════════════

def make_experienced_peer(
    builder: Callable,
    pre_cycles: int = 30,
) -> Callable:
    """Build a peer_fn from a pre-experienced controller.

    1. Create a fresh landscape from the same builder
    2. Pre-run the controller for pre_cycles to build historization
    3. Return a peer_fn that recommends neighbors based on
       the advisor's trace quality
    """
    advisor_spec = builder()
    advisor_ctrl = E0Controller(
        advisor_spec.landscape,
        advisor_spec.execute_fn,
        alpha=2.0,
        recent_k=3,
    )
    advisor_ctrl.run(
        advisor_spec.start,
        max_cycles=pre_cycles,
        goal=advisor_spec.goal,
    )
    advisor_landscape = advisor_spec.landscape

    def peer_fn(
        landscape: Landscape,
        current: str,
        neighbors: List[str],
    ) -> Optional[str]:
        """Recommend the neighbor with best trace quality in advisor."""
        best_target = None
        best_quality = -2.0

        for n in neighbors:
            edge = Edge(current, n)
            if edge in advisor_landscape._delta:
                q = advisor_landscape.historization.trace_quality(edge)
                if q > best_quality:
                    best_quality = q
                    best_target = n

        # Only recommend if the advisor has positive experience
        if best_target is not None and best_quality > 0.0:
            return best_target
        return None

    return peer_fn


# ══════════════════════════════════════════════
# Single domain run
# ══════════════════════════════════════════════

def _count_overloaded(trace: RunTrace) -> int:
    """Count OVERLOADED escalations in a trace."""
    return sum(
        1 for s in trace.steps
        if s.escalation_type == EscalationType.OVERLOADED
    )


def run_domain_mode(
    spec: DomainSpec,
    mode: str,
    peer_fn: Optional[Callable] = None,
    max_cycles: int = 50,
    overload_threshold: float = 3.0,
) -> OverloadDomainResult:
    """Run one domain in one mode."""
    ctrl = E0Controller(
        spec.landscape,
        spec.execute_fn,
        alpha=2.0,
        recent_k=3,
        peer_fn=peer_fn,
        overload_threshold=overload_threshold,
    )
    trace = ctrl.run(spec.start, max_cycles=max_cycles, goal=spec.goal)
    metrics = trace.metrics()
    goal_reached = spec.goal in trace.path
    overload_count = _count_overloaded(trace)

    ev = evaluate_run(
        path=trace.path,
        steps=len(trace.steps),
        escalation_count=int(metrics["escalation_count"]),
        revisit_count=int(metrics["revisit_count"]),
        success_rate=metrics["success_rate"],
        avg_tension=metrics["avg_tension"],
        total_tension=float(trace.total_tension),
        reached_goal=goal_reached,
        happy_path_length=spec.happy_path_length,
    )

    return OverloadDomainResult(
        domain=spec.name,
        mode=mode,
        goal_reached=goal_reached,
        steps=len(trace.steps),
        rating=ev.rating,
        escalations=int(metrics["escalation_count"]),
        overload_count=overload_count,
        revisits=int(metrics["revisit_count"]),
        success_rate=round(metrics["success_rate"], 3),
        efficiency=ev.goal_reach_efficiency,
    )


# ══════════════════════════════════════════════
# Comparison runner
# ══════════════════════════════════════════════

def run_domain_comparison(
    builder: Callable,
    max_cycles: int = 50,
    pre_cycles: int = 30,
    overload_threshold: float = 3.0,
) -> OverloadComparisonResult:
    """Run one domain under baseline and peer modes."""
    spec_base = builder()
    baseline = run_domain_mode(
        spec_base, "baseline", max_cycles=max_cycles,
        overload_threshold=overload_threshold,
    )

    spec_peer = builder()
    peer_fn = make_experienced_peer(builder, pre_cycles=pre_cycles)
    peer = run_domain_mode(
        spec_peer, "peer", peer_fn=peer_fn, max_cycles=max_cycles,
        overload_threshold=overload_threshold,
    )

    return OverloadComparisonResult(
        domain=spec_base.name,
        baseline=baseline,
        peer=peer,
    )


# ══════════════════════════════════════════════
# Full benchmark
# ══════════════════════════════════════════════

def run_overloaded_benchmark(
    max_cycles: int = 50,
    pre_cycles: int = 30,
    overload_threshold: float = 3.0,
) -> OverloadBenchmarkResult:
    """Run all 10 domains under baseline and peer modes."""
    result = OverloadBenchmarkResult()
    for builder in ALL_DOMAINS:
        comp = run_domain_comparison(
            builder,
            max_cycles=max_cycles,
            pre_cycles=pre_cycles,
            overload_threshold=overload_threshold,
        )
        result.comparisons.append(comp)
    return result
