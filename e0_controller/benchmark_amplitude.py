"""
Amplitude Benchmark (C55)
===========================
All 10 C53 domains × 3 controller modes:
  GREEDY, AMPLITUDE_ON_DISAGREE, BORN_SAMPLING.

Measures whether amplitude-aware modes preserve or improve
domain-invariance across the full benchmark suite.

BORN_SAMPLING is stochastic — each domain runs N trials and
reports median steps, goal-reach rate, and rating distribution.

Usage:
  python -m e0_controller.benchmark_amplitude          # pretty table
  python -m e0_controller.benchmark_amplitude --json   # machine-readable
"""

from __future__ import annotations

import json
import random
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from e0_controller.benchmark_domain_invariance import (
    ALL_DOMAINS,
    DomainSpec,
    build_all_domains,
)
from e0_controller.controller import E0Controller, HybridMode, RunTrace
from e0_controller.evaluation import evaluate_run, RunEvaluation
from e0_controller.primitives import Outcome


# ══════════════════════════════════════════════
# Result types
# ══════════════════════════════════════════════

@dataclass
class ModeResult:
    """Result of running one domain in one mode."""
    domain: str
    mode: str
    goal_reached: bool
    steps: int
    rating: str
    success_rate: float
    escalations: int
    revisits: int
    efficiency: float
    avg_tension: float
    unique_states: int
    hybrid_overrides: int


@dataclass
class BornTrialSummary:
    """Aggregated result of N Born-sampling trials for one domain."""
    domain: str
    trials: int
    goal_reach_rate: float
    median_steps: int
    best_rating: str
    worst_rating: str
    median_rating: str
    mean_overrides: float


@dataclass
class AmplitudeBenchmarkResult:
    """Full benchmark: all domains × all modes."""
    greedy: List[ModeResult]
    amplitude: List[ModeResult]
    born: List[BornTrialSummary]


# ══════════════════════════════════════════════
# Runner helpers
# ══════════════════════════════════════════════

def _fresh_landscape(spec_builder) -> DomainSpec:
    """Build a fresh domain spec (fresh landscape, no prior historization)."""
    return spec_builder()


def _run_one(
    spec: DomainSpec,
    mode: HybridMode,
    max_cycles: int = 50,
    horizon: int = 3,
) -> ModeResult:
    """Run one domain in one mode, return ModeResult."""
    goals = {spec.goal}
    ctrl = E0Controller(
        spec.landscape,
        spec.execute_fn,
        alpha=2.0,
        recent_k=3,
        hybrid_mode=mode,
        hybrid_horizon=horizon,
        hybrid_goals=goals,
    )
    trace = ctrl.run(spec.start, max_cycles=max_cycles, goal=spec.goal)
    metrics = trace.metrics()

    goal_reached = spec.goal in trace.path

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

    override_count = sum(
        1 for s in trace.steps if getattr(s, "hybrid_overridden", False)
    )

    return ModeResult(
        domain=spec.name,
        mode=mode.value,
        goal_reached=goal_reached,
        steps=len(trace.steps),
        rating=ev.rating,
        success_rate=round(metrics["success_rate"], 3),
        escalations=int(metrics["escalation_count"]),
        revisits=int(metrics["revisit_count"]),
        efficiency=ev.goal_reach_efficiency,
        avg_tension=round(metrics["avg_tension"], 4),
        unique_states=int(metrics["unique_states"]),
        hybrid_overrides=override_count,
    )


def _rating_rank(r: str) -> int:
    return "ABCDF".index(r)


def _median_rating(ratings: List[str]) -> str:
    ranked = sorted(ratings, key=_rating_rank)
    return ranked[len(ranked) // 2]


def _run_born_trials(
    builder,
    n_trials: int = 20,
    max_cycles: int = 50,
    horizon: int = 3,
    seed: int = 42,
) -> BornTrialSummary:
    """Run N independent Born-sampling trials for one domain."""
    rng = random.Random(seed)
    results: List[ModeResult] = []
    for i in range(n_trials):
        random.seed(rng.randint(0, 2**31))
        spec = builder()  # fresh landscape each trial
        r = _run_one(spec, HybridMode.BORN_SAMPLING, max_cycles, horizon)
        results.append(r)

    steps_list = sorted(r.steps for r in results)
    ratings = [r.rating for r in results]
    goal_reached_count = sum(1 for r in results if r.goal_reached)
    overrides = [r.hybrid_overrides for r in results]

    return BornTrialSummary(
        domain=results[0].domain,
        trials=n_trials,
        goal_reach_rate=round(goal_reached_count / n_trials, 2),
        median_steps=steps_list[len(steps_list) // 2],
        best_rating=min(ratings, key=_rating_rank),
        worst_rating=max(ratings, key=_rating_rank),
        median_rating=_median_rating(ratings),
        mean_overrides=round(sum(overrides) / n_trials, 1),
    )


# ══════════════════════════════════════════════
# Full benchmark
# ══════════════════════════════════════════════

def run_amplitude_benchmark(
    max_cycles: int = 50,
    born_trials: int = 20,
    horizon: int = 3,
) -> AmplitudeBenchmarkResult:
    """Run all 10 domains × 3 modes."""
    greedy_results = []
    amp_results = []
    born_results = []

    for builder in ALL_DOMAINS:
        # GREEDY — fresh landscape
        spec = builder()
        greedy_results.append(
            _run_one(spec, HybridMode.GREEDY, max_cycles, horizon)
        )

        # AMPLITUDE_ON_DISAGREE — fresh landscape
        spec = builder()
        amp_results.append(
            _run_one(spec, HybridMode.AMPLITUDE_ON_DISAGREE, max_cycles, horizon)
        )

        # BORN_SAMPLING — N trials, each with fresh landscape
        born_results.append(
            _run_born_trials(builder, born_trials, max_cycles, horizon)
        )

    return AmplitudeBenchmarkResult(
        greedy=greedy_results,
        amplitude=amp_results,
        born=born_results,
    )


# ══════════════════════════════════════════════
# Output
# ══════════════════════════════════════════════

def print_results(result: AmplitudeBenchmarkResult) -> None:
    """Pretty-print benchmark comparison table."""
    print("\n" + "=" * 100)
    print("  E₀ Amplitude Benchmark — 10 Domains × 3 Modes (C55)")
    print("=" * 100)

    # ── Deterministic modes side-by-side ──
    print("\n── GREEDY vs AMPLITUDE_ON_DISAGREE ──\n")
    header = (
        f"{'Domain':<28} │ {'G·Steps':>7} {'G·Rate':>5} "
        f"│ {'A·Steps':>7} {'A·Rate':>5} {'A·Ovr':>5} "
        f"│ {'G':>1} {'A':>1}"
    )
    print(header)
    print("─" * 80)

    for g, a in zip(result.greedy, result.amplitude):
        g_ok = "✓" if g.goal_reached else "✗"
        a_ok = "✓" if a.goal_reached else "✗"
        print(
            f"{g.domain:<28} │ {g.steps:>5} {g_ok:>1} {g.success_rate:>5.1%} "
            f"│ {a.steps:>5} {a_ok:>1} {a.success_rate:>5.1%} {a.hybrid_overrides:>5} "
            f"│ {g.rating:>1} {a.rating:>1}"
        )

    # Summary
    g_all = all(r.goal_reached for r in result.greedy)
    a_all = all(r.goal_reached for r in result.amplitude)
    g_worst = max((r.rating for r in result.greedy), key=_rating_rank)
    a_worst = max((r.rating for r in result.amplitude), key=_rating_rank)
    print("─" * 80)
    print(f"  GREEDY:    all goals={'YES' if g_all else 'NO'}, worst={g_worst}")
    print(f"  AMPLITUDE: all goals={'YES' if a_all else 'NO'}, worst={a_worst}")

    # ── Born sampling ──
    print("\n── BORN_SAMPLING (20 trials each) ──\n")
    header = (
        f"{'Domain':<28} │ {'Reach%':>6} {'Med·S':>5} "
        f"│ {'Best':>4} {'Med':>4} {'Wrst':>4} "
        f"│ {'Ovr':>4}"
    )
    print(header)
    print("─" * 70)

    for b in result.born:
        print(
            f"{b.domain:<28} │ {b.goal_reach_rate:>5.0%} {b.median_steps:>6} "
            f"│ {b.best_rating:>4} {b.median_rating:>4} {b.worst_rating:>4} "
            f"│ {b.mean_overrides:>4.1f}"
        )

    b_all_100 = all(b.goal_reach_rate >= 1.0 for b in result.born)
    b_worst_median = max(
        (b.median_rating for b in result.born), key=_rating_rank
    )
    print("─" * 70)
    print(f"  All 100% reach: {'YES' if b_all_100 else 'NO'}")
    print(f"  Worst median:   {b_worst_median}")
    print()


def results_to_dict(result: AmplitudeBenchmarkResult) -> Dict:
    """Convert to serializable dict."""
    return {
        "benchmark": "amplitude_v1",
        "modes": ["greedy", "amplitude_on_disagree", "born_sampling"],
        "domains": 10,
        "greedy": {
            "all_goals": all(r.goal_reached for r in result.greedy),
            "worst_rating": max(
                (r.rating for r in result.greedy), key=_rating_rank
            ),
            "results": [
                {
                    "domain": r.domain, "goal": r.goal_reached,
                    "steps": r.steps, "rating": r.rating,
                    "success_rate": r.success_rate,
                    "overrides": r.hybrid_overrides,
                }
                for r in result.greedy
            ],
        },
        "amplitude": {
            "all_goals": all(r.goal_reached for r in result.amplitude),
            "worst_rating": max(
                (r.rating for r in result.amplitude), key=_rating_rank
            ),
            "results": [
                {
                    "domain": r.domain, "goal": r.goal_reached,
                    "steps": r.steps, "rating": r.rating,
                    "success_rate": r.success_rate,
                    "overrides": r.hybrid_overrides,
                }
                for r in result.amplitude
            ],
        },
        "born": {
            "trials_per_domain": result.born[0].trials if result.born else 0,
            "all_100_reach": all(
                b.goal_reach_rate >= 1.0 for b in result.born
            ),
            "results": [
                {
                    "domain": b.domain,
                    "reach_rate": b.goal_reach_rate,
                    "median_steps": b.median_steps,
                    "best_rating": b.best_rating,
                    "median_rating": b.median_rating,
                    "worst_rating": b.worst_rating,
                    "mean_overrides": b.mean_overrides,
                }
                for b in result.born
            ],
        },
    }


# ══════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════

if __name__ == "__main__":
    result = run_amplitude_benchmark()
    if "--json" in sys.argv:
        print(json.dumps(results_to_dict(result), indent=2))
    else:
        print_results(result)
