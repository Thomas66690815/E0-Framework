"""
C103 — Scoped Reflexion Benchmark: 10 Domains × 2 Modes
==========================================================
Compares global proactive reflexion (C57) against scoped reflexion (C101)
on all 10 standard benchmark domains.

Question: Does historization-scoped reflexion maintain goal reach while
producing fewer, more locally informed proposals?

Hypothesis:
  - On fresh domains (minimal historization), scoped ≡ global (degeneration)
  - On domains where reflexion fires (frontier disconnection), scoped
    produces the same or fewer proposals with equal or better efficiency
  - Scoped NEVER degrades goal reach (it IS global when trace_load ≈ 0)

Usage:
  from e0_controller.benchmark_scoped_reflexion import run_scoped_benchmark
  result = run_scoped_benchmark()
  print(result.summary())
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

from e0_controller.primitives import Outcome
from e0_controller.controller import E0Controller, RunTrace
from e0_controller.evaluation import evaluate_run
from e0_controller.benchmark_domain_invariance import (
    ALL_DOMAINS,
    DomainSpec,
)
from e0_controller.reflexive_edge_proposal import (
    ProposedEdge,
    run_with_proactive_reflexion,
)
from e0_controller.scoped_reflexion import (
    ReflexionScope,
    run_with_scoped_reflexion,
)


# ══════════════════════════════════════════════
# Result types
# ══════════════════════════════════════════════

@dataclass
class ScopedResult:
    """One domain × one mode (GLOBAL or SCOPED)."""
    domain: str
    mode: str                 # "GLOBAL" | "SCOPED"
    goal_reached: bool
    steps: int
    rating: str
    proposals: int
    efficiency: float
    avg_locality: float       # mean locality across scopes (-1 for GLOBAL)
    max_locality: float       # max locality (-1 for GLOBAL)
    scope_count: int          # number of reflexion scopes computed


@dataclass
class ScopedComparison:
    """Compare GLOBAL vs SCOPED for one domain."""
    domain: str
    global_result: ScopedResult
    scoped_result: ScopedResult

    @property
    def scoped_improves(self) -> bool:
        """Scoped reaches goal when global doesn't."""
        return self.scoped_result.goal_reached and not self.global_result.goal_reached

    @property
    def equal_goal_reach(self) -> bool:
        """Both modes reach (or miss) goal identically."""
        return self.global_result.goal_reached == self.scoped_result.goal_reached

    @property
    def fewer_proposals(self) -> bool:
        """Scoped produces strictly fewer proposals."""
        return self.scoped_result.proposals < self.global_result.proposals

    @property
    def equal_or_fewer_proposals(self) -> bool:
        """Scoped produces same or fewer proposals."""
        return self.scoped_result.proposals <= self.global_result.proposals

    @property
    def steps_delta(self) -> int:
        """Negative = scoped uses fewer steps."""
        return self.scoped_result.steps - self.global_result.steps


@dataclass
class ScopedBenchmarkResult:
    """Full benchmark: 10 domains × 2 modes."""
    comparisons: List[ScopedComparison] = field(default_factory=list)

    @property
    def global_goal_count(self) -> int:
        return sum(1 for c in self.comparisons if c.global_result.goal_reached)

    @property
    def scoped_goal_count(self) -> int:
        return sum(1 for c in self.comparisons if c.scoped_result.goal_reached)

    @property
    def scoped_improves_count(self) -> int:
        return sum(1 for c in self.comparisons if c.scoped_improves)

    @property
    def fewer_proposals_count(self) -> int:
        return sum(1 for c in self.comparisons if c.fewer_proposals)

    @property
    def equal_or_fewer_count(self) -> int:
        return sum(1 for c in self.comparisons if c.equal_or_fewer_proposals)

    @property
    def equal_goal_reach_count(self) -> int:
        return sum(1 for c in self.comparisons if c.equal_goal_reach)

    def summary(self) -> str:
        lines = ["Scoped Reflexion Benchmark: 10 Domains × 2 Modes",
                 "=" * 70]
        lines.append(
            f"{'Domain':<25} {'GLOBAL':>10} {'SCOPED':>10} "
            f"{'ΔSteps':>6} {'ΔProp':>6} {'Locality':>8}"
        )
        lines.append("-" * 70)
        for c in self.comparisons:
            g, s = c.global_result, c.scoped_result

            def _fmt(r: ScopedResult) -> str:
                return f"{r.rating}({r.steps})" if r.goal_reached else f"F({r.steps})"

            d_steps = f"{c.steps_delta:+d}" if c.steps_delta != 0 else "="
            d_props = s.proposals - g.proposals
            d_props_s = f"{d_props:+d}" if d_props != 0 else "="
            loc = f"{s.avg_locality:.2f}" if s.avg_locality >= 0 else "—"

            lines.append(
                f"{c.domain:<25} {_fmt(g):>10} {_fmt(s):>10} "
                f"{d_steps:>6} {d_props_s:>6} {loc:>8}"
            )
        lines.append("-" * 70)
        lines.append(
            f"Goal reach:  GLOBAL={self.global_goal_count}/10  "
            f"SCOPED={self.scoped_goal_count}/10"
        )
        lines.append(f"Equal goal reach: {self.equal_goal_reach_count}/10")
        lines.append(f"Fewer proposals (scoped): {self.fewer_proposals_count}/10")
        lines.append(f"Equal-or-fewer proposals: {self.equal_or_fewer_count}/10")
        return "\n".join(lines)


# ══════════════════════════════════════════════
# Evaluation helper
# ══════════════════════════════════════════════

def _evaluate(
    spec: DomainSpec,
    trace: RunTrace,
    mode: str,
    proposals: List[ProposedEdge],
    scopes: List[ReflexionScope],
) -> ScopedResult:
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

    if scopes:
        avg_loc = sum(s.locality for s in scopes) / len(scopes)
        max_loc = max(s.locality for s in scopes)
    else:
        avg_loc = -1.0
        max_loc = -1.0

    return ScopedResult(
        domain=spec.name,
        mode=mode,
        goal_reached=goal_reached,
        steps=len(trace.steps),
        rating=ev.rating,
        proposals=len(proposals),
        efficiency=ev.goal_reach_efficiency,
        avg_locality=avg_loc,
        max_locality=max_loc,
        scope_count=len(scopes),
    )


# ══════════════════════════════════════════════
# Runners
# ══════════════════════════════════════════════

def _run_global(spec: DomainSpec, max_cycles: int = 50) -> ScopedResult:
    """Proactive reflexion with global scope (C57)."""
    trace, proposals = run_with_proactive_reflexion(
        spec.landscape, spec.execute_fn, spec.start, spec.goal,
        max_cycles=max_cycles,
    )
    return _evaluate(spec, trace, "GLOBAL", proposals, scopes=[])


def _run_scoped(
    spec: DomainSpec, max_cycles: int = 50, mu: Optional[float] = None,
) -> ScopedResult:
    """Proactive reflexion with historization scope (C101)."""
    trace, proposals, scopes = run_with_scoped_reflexion(
        spec.landscape, spec.execute_fn, spec.start, spec.goal,
        max_cycles=max_cycles, mu=mu,
    )
    return _evaluate(spec, trace, "SCOPED", proposals, scopes)


def _run_domain(
    builder: Callable, max_cycles: int = 50, mu: Optional[float] = None,
) -> ScopedComparison:
    """Run one domain under both modes (fresh landscape each)."""
    spec_g = builder()
    r_global = _run_global(spec_g, max_cycles)

    spec_s = builder()
    r_scoped = _run_scoped(spec_s, max_cycles, mu)

    return ScopedComparison(
        domain=spec_g.name,
        global_result=r_global,
        scoped_result=r_scoped,
    )


def run_scoped_benchmark(
    max_cycles: int = 50,
    mu: Optional[float] = None,
) -> ScopedBenchmarkResult:
    """Run all 10 domains × 2 modes (GLOBAL vs SCOPED)."""
    result = ScopedBenchmarkResult()
    for builder in ALL_DOMAINS:
        comp = _run_domain(builder, max_cycles, mu)
        result.comparisons.append(comp)
    return result
