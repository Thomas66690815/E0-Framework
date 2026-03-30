"""
C58 — Reflexion Benchmark: 10 Domains × 3 Stufen
=====================================================
Runs all 10 C53 domains under three regimes:

  Stufe 1: Standard controller (no reflexion)
  Stufe 1R: Reactive reflexion (C56 — run_with_reflexion)
  Stufe 2: Proactive reflexion (C57 — run_with_proactive_reflexion)

Question: Which real domains benefit from reflexive edge proposal?
Hypothesis: Domains with structural gaps (frontier disconnection) improve;
domains with FAILURE-coupled traps or grid/cycle topology don't —
those are resistance problems, not frontier problems.

Usage:
  from e0_controller.benchmark_reflexion import run_reflexion_benchmark
  result = run_reflexion_benchmark()
  print(result.summary())
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from e0_controller.primitives import Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller, RunTrace
from e0_controller.evaluation import evaluate_run
from e0_controller.benchmark_domain_invariance import (
    ALL_DOMAINS,
    DomainSpec,
)
from e0_controller.reflexive_edge_proposal import (
    ProposedEdge,
    run_with_reflexion,
    run_with_proactive_reflexion,
)


# ══════════════════════════════════════════════
# Result types
# ══════════════════════════════════════════════

@dataclass
class StufeResult:
    """One domain × one Stufe."""
    domain: str
    stufe: str                # "S1", "S1R", "S2"
    goal_reached: bool
    steps: int
    rating: str
    proposals: int            # edges proposed (0 for S1)
    efficiency: float


@dataclass
class DomainComparison:
    """Compare three Stufen for one domain."""
    domain: str
    s1: StufeResult
    s1r: StufeResult
    s2: StufeResult

    @property
    def reflexion_helps(self) -> bool:
        """Does any reflexion mode improve over S1?"""
        return (self.s1r.goal_reached and not self.s1.goal_reached) or \
               (self.s2.goal_reached and not self.s1.goal_reached) or \
               (self.s2.steps < self.s1.steps and self.s2.goal_reached)

    @property
    def proactive_advantage(self) -> bool:
        """Does S2 improve over S1R?"""
        if self.s2.goal_reached and not self.s1r.goal_reached:
            return True
        if self.s2.goal_reached and self.s1r.goal_reached:
            return self.s2.steps < self.s1r.steps
        return False


@dataclass
class ReflexionBenchmarkResult:
    """Full benchmark: 10 domains × 3 Stufen."""
    comparisons: List[DomainComparison] = field(default_factory=list)

    @property
    def s1_goal_count(self) -> int:
        return sum(1 for c in self.comparisons if c.s1.goal_reached)

    @property
    def s1r_goal_count(self) -> int:
        return sum(1 for c in self.comparisons if c.s1r.goal_reached)

    @property
    def s2_goal_count(self) -> int:
        return sum(1 for c in self.comparisons if c.s2.goal_reached)

    @property
    def reflexion_helps_count(self) -> int:
        return sum(1 for c in self.comparisons if c.reflexion_helps)

    @property
    def proactive_advantage_count(self) -> int:
        return sum(1 for c in self.comparisons if c.proactive_advantage)

    def summary(self) -> str:
        lines = ["Reflexion Benchmark: 10 Domains × 3 Stufen",
                 "=" * 50]
        lines.append(f"{'Domain':<20} {'S1':>6} {'S1R':>6} {'S2':>6}  "
                      f"{'Helps?':>6} {'S2>S1R':>6}")
        lines.append("-" * 60)
        for c in self.comparisons:
            def _fmt(r: StufeResult) -> str:
                return f"{r.rating}({r.steps})" if r.goal_reached else f"F({r.steps})"
            lines.append(
                f"{c.domain:<20} {_fmt(c.s1):>6} {_fmt(c.s1r):>6} "
                f"{_fmt(c.s2):>6}  {'✓' if c.reflexion_helps else '—':>6} "
                f"{'✓' if c.proactive_advantage else '—':>6}"
            )
        lines.append("-" * 60)
        lines.append(f"Goal reach:  S1={self.s1_goal_count}/10  "
                      f"S1R={self.s1r_goal_count}/10  "
                      f"S2={self.s2_goal_count}/10")
        lines.append(f"Reflexion helps: {self.reflexion_helps_count}/10")
        lines.append(f"Proactive advantage: {self.proactive_advantage_count}/10")
        return "\n".join(lines)


# ══════════════════════════════════════════════
# Runners
# ══════════════════════════════════════════════

def _run_stufe1(spec: DomainSpec, max_cycles: int = 50) -> StufeResult:
    """Standard controller, no reflexion."""
    ctrl = E0Controller(spec.landscape, spec.execute_fn,
                        alpha=2.0, recent_k=3)
    trace = ctrl.run(spec.start, max_cycles=max_cycles, goal=spec.goal)
    return _evaluate(spec, trace, "S1", proposals=0)


def _run_stufe1r(spec: DomainSpec, max_cycles: int = 50) -> StufeResult:
    """Reactive reflexion (C56)."""
    trace, proposals = run_with_reflexion(
        spec.landscape, spec.execute_fn, spec.start, spec.goal,
        max_cycles=max_cycles, proposal_trigger=8,
    )
    return _evaluate(spec, trace, "S1R", proposals=len(proposals))


def _run_stufe2(spec: DomainSpec, max_cycles: int = 50) -> StufeResult:
    """Proactive reflexion (C57)."""
    trace, proposals = run_with_proactive_reflexion(
        spec.landscape, spec.execute_fn, spec.start, spec.goal,
        max_cycles=max_cycles,
    )
    return _evaluate(spec, trace, "S2", proposals=len(proposals))


def _evaluate(
    spec: DomainSpec,
    trace: RunTrace,
    stufe: str,
    proposals: int,
) -> StufeResult:
    """Evaluate a trace against domain spec."""
    goal_reached = spec.goal in trace.path
    metrics = trace.metrics()
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
    return StufeResult(
        domain=spec.name,
        stufe=stufe,
        goal_reached=goal_reached,
        steps=len(trace.steps),
        rating=ev.rating,
        proposals=proposals,
        efficiency=ev.goal_reach_efficiency,
    )


def _run_domain(builder: Callable, max_cycles: int = 50) -> DomainComparison:
    """Run one domain under all three Stufen (fresh landscape each)."""
    spec1 = builder()
    r1 = _run_stufe1(spec1, max_cycles)

    spec1r = builder()
    r1r = _run_stufe1r(spec1r, max_cycles)

    spec2 = builder()
    r2 = _run_stufe2(spec2, max_cycles)

    return DomainComparison(
        domain=spec1.name,
        s1=r1, s1r=r1r, s2=r2,
    )


def run_reflexion_benchmark(
    max_cycles: int = 50,
) -> ReflexionBenchmarkResult:
    """Run all 10 domains × 3 Stufen."""
    result = ReflexionBenchmarkResult()
    for builder in ALL_DOMAINS:
        comp = _run_domain(builder, max_cycles)
        result.comparisons.append(comp)
    return result
