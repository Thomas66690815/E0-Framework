"""
Modulation Benchmark (C100)
==============================
All 10 C53 domains × 3 modulation modes:
  BASELINE      — overlap_modulation=False, inertia_modulation=False
  OVERLAP       — overlap_modulation=True  (C98)
  FULL          — overlap + inertia        (C98 + C99)

Plus 4 additional "stress domains" designed to exercise modulation:
  D11 Confused Fork    — contradictory inscription on one branch
  D12 Triangle Bypass  — directed triangle provides overlap support
  D13 Confused Grid    — 3×3 grid with confused central edges
  D14 Overlap Ladder   — parallel ladders with different bypass support

Measures whether modulation preserves domain-invariance on
standard domains AND provides measurable benefit on stress domains.

Key metrics per run:
  - goal_reached, steps, efficiency
  - decision_changed: whether modulation altered any step choice
  - For each domain × mode, we compare to BASELINE.

Usage:
  python -m e0_controller.benchmark_modulation          # pretty table
  python -m e0_controller.benchmark_modulation --json   # machine-readable
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from e0_controller.benchmark_domain_invariance import (
    ALL_DOMAINS,
    DomainSpec,
    build_all_domains,
)
from e0_controller.controller import E0Controller, RunTrace
from e0_controller.evaluation import evaluate_run, RunEvaluation
from e0_controller.landscape import Landscape
from e0_controller.primitives import Edge, Outcome


# ══════════════════════════════════════════════
# Modulation modes
# ══════════════════════════════════════════════

MODES = ["BASELINE", "OVERLAP", "FULL"]


def _configure_landscape(L: Landscape, mode: str) -> None:
    """Set modulation flags on landscape according to mode."""
    if mode == "BASELINE":
        L.overlap_modulation = False
        L.inertia_modulation = False
    elif mode == "OVERLAP":
        L.overlap_modulation = True
        L.inertia_modulation = False
    elif mode == "FULL":
        L.overlap_modulation = True
        L.inertia_modulation = True
    else:
        raise ValueError(f"Unknown mode: {mode}")


# ══════════════════════════════════════════════
# Result types
# ══════════════════════════════════════════════

@dataclass
class ModulationResult:
    """Result of running one domain in one modulation mode."""
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
    path: List[str]


@dataclass
class ModulationComparison:
    """Cross-mode comparison for one domain."""
    domain: str
    baseline: ModulationResult
    overlap: ModulationResult
    full: ModulationResult
    path_changed_overlap: bool
    path_changed_full: bool
    steps_delta_overlap: int   # negative = fewer steps = better
    steps_delta_full: int


# ══════════════════════════════════════════════
# Stress Domains (D11–D14)
# ══════════════════════════════════════════════

def _all_success(source: str, target: str) -> Outcome:
    return Outcome.SUCCESS


def _confuse_edge(L: Landscape, src: str, tgt: str,
                  rounds: int = 14) -> None:
    """Inscribe an edge with alternating SUCCESS/FAILURE."""
    edge = Edge(src, tgt)
    for i in range(rounds):
        outcome = Outcome.SUCCESS if i % 2 == 0 else Outcome.FAILURE
        L.historization.update(edge, outcome)


def build_d11_confused_fork() -> DomainSpec:
    """Two paths S →{A,B}→ GOAL.  S→A is confused but has lower
    base resistance, so δ_H alone doesn't overcome it.

    S→A: R₀=0.6, confused (alternating U/F) → δ_H ≈ 0.3
          S_eff ≈ 0.6+0.3 = 0.9,  but I ≈ 0.7 → S_eff/I ≈ 1.29
    S→B: R₀=1.0, fresh → δ_H = 0, S_eff = 1.0, I = 1.0

    Without inertia: S→A wins (0.9 < 1.0)
    With inertia:    S→B wins (1.0 < 1.29)
    """
    L = Landscape()
    L.add_edge("S", "A", delta=1.0, resistance=0.6)
    L.add_edge("A", "GOAL", delta=1.0, resistance=1.0)
    L.add_edge("S", "B", delta=1.0, resistance=1.0)
    L.add_edge("B", "GOAL", delta=1.0, resistance=1.0)
    _confuse_edge(L, "S", "A", rounds=20)
    return DomainSpec(
        name="D11_confused_fork",
        description="Confused fork — confused edge with lower R₀, inertia flips choice",
        landscape=L, start="S", goal="GOAL",
        execute_fn=_all_success,
        happy_path_length=2,
        topology_class="fork",
        node_count=4, edge_count=4,
    )


def build_d12_triangle_bypass() -> DomainSpec:
    """Two paths S →{A,B}→ GOAL.  S→B has triangle support via C.

    S → C → B bypass gives overlap M_H > 1 for S→B.
    Without overlap: S→A and S→B have equal S_eff.
    With overlap: S→B preferred (S_eff/M_H < S_eff).
    """
    L = Landscape()
    # Direct paths (equal tensions)
    L.add_edge("S", "A", delta=1.0, resistance=0.5)
    L.add_edge("A", "GOAL", delta=1.0, resistance=0.5)
    L.add_edge("S", "B", delta=1.0, resistance=0.5)
    L.add_edge("B", "GOAL", delta=1.0, resistance=0.5)
    # Bypass: S → C → B (creates directed triangle for S→B)
    L.add_edge("S", "C", delta=1.0, resistance=0.5)
    L.add_edge("C", "B", delta=1.0, resistance=0.5)
    L.add_edge("C", "GOAL", delta=1.0, resistance=0.5)
    return DomainSpec(
        name="D12_triangle_bypass",
        description="Triangle bypass — S→B has overlap support via C",
        landscape=L, start="S", goal="GOAL",
        execute_fn=_all_success,
        happy_path_length=2,
        topology_class="triangle",
        node_count=5, edge_count=7,
    )


def build_d13_confused_grid() -> DomainSpec:
    """3×3 grid, two routes to goal.  Direct route goes through confused
    edge R0C0→R0C1 (lower R₀=0.6, confused).  Detour goes via R1C0
    (R₀=1.0, clean).

    Without inertia: direct route wins (lower R₀ + δ_H small).
    With inertia: I < 1 inflates confused edge → detour wins.
    """
    L = Landscape()

    # Top row: R0C0 → R0C1 → R0C2 (confused at start, lower R₀)
    L.add_edge("R0C0", "R0C1", delta=1.0, resistance=0.6)  # confused
    L.add_edge("R0C1", "R0C2", delta=1.0, resistance=0.5)
    # Right column down
    L.add_edge("R0C2", "R1C2", delta=1.0, resistance=0.5)
    L.add_edge("R1C2", "R2C2", delta=1.0, resistance=0.5)
    # Left column: R0C0 → R1C0 → R2C0 (clean, R₀=1.0)
    L.add_edge("R0C0", "R1C0", delta=1.0, resistance=1.0)
    L.add_edge("R1C0", "R2C0", delta=1.0, resistance=0.5)
    # Bottom row
    L.add_edge("R2C0", "R2C1", delta=1.0, resistance=0.5)
    L.add_edge("R2C1", "R2C2", delta=1.0, resistance=0.5)

    # Confuse the direct route's first edge
    _confuse_edge(L, "R0C0", "R0C1", rounds=20)

    return DomainSpec(
        name="D13_confused_grid",
        description="3×3 grid — confused direct route, clean detour",
        landscape=L, start="R0C0", goal="R2C2",
        execute_fn=_all_success,
        happy_path_length=4,
        topology_class="grid",
        node_count=7, edge_count=8,
    )


def build_d14_overlap_ladder() -> DomainSpec:
    """Two parallel ladders S → {L,R}1 → {L,R}2 → GOAL.
    Left ladder has bypass support at each rung (triangles).
    Right ladder is pure chain (no bypass).

    Without overlap: L and R have equal S_eff.
    With overlap: L preferred (M_H > 1 from triangle support).
    """
    L = Landscape()
    # Left ladder with support
    L.add_edge("S", "L1", delta=1.0, resistance=0.5)
    L.add_edge("L1", "L2", delta=1.0, resistance=0.5)
    L.add_edge("L2", "GOAL", delta=1.0, resistance=0.5)
    # Left bypass triangles
    L.add_edge("S", "M1", delta=1.0, resistance=0.5)
    L.add_edge("M1", "L1", delta=1.0, resistance=0.5)
    L.add_edge("M1", "L2", delta=1.0, resistance=0.5)
    # Right ladder (bare)
    L.add_edge("S", "R1", delta=1.0, resistance=0.5)
    L.add_edge("R1", "R2", delta=1.0, resistance=0.5)
    L.add_edge("R2", "GOAL", delta=1.0, resistance=0.5)
    return DomainSpec(
        name="D14_overlap_ladder",
        description="Overlap ladder — left rungs have triangle support",
        landscape=L, start="S", goal="GOAL",
        execute_fn=_all_success,
        happy_path_length=3,
        topology_class="ladder",
        node_count=7, edge_count=9,
    )


STRESS_DOMAINS = [
    build_d11_confused_fork,
    build_d12_triangle_bypass,
    build_d13_confused_grid,
    build_d14_overlap_ladder,
]


def build_all_modulation_domains() -> List[DomainSpec]:
    """Build all 14 domains (10 standard + 4 stress)."""
    return build_all_domains() + [b() for b in STRESS_DOMAINS]


# ══════════════════════════════════════════════
# Runner
# ══════════════════════════════════════════════

def run_modulation_domain(
    spec: DomainSpec,
    mode: str,
    max_cycles: int = 50,
) -> ModulationResult:
    """Run one domain in one modulation mode."""
    _configure_landscape(spec.landscape, mode)

    ctrl = E0Controller(
        spec.landscape,
        spec.execute_fn,
        alpha=2.0,
        recent_k=3,
    )
    trace = ctrl.run(spec.start, max_cycles=max_cycles, goal=spec.goal)
    metrics = trace.metrics()
    goal_reached = spec.goal in trace.path

    return ModulationResult(
        domain=spec.name,
        mode=mode,
        goal_reached=goal_reached,
        steps=len(trace.steps),
        rating=evaluate_run(
            path=trace.path,
            steps=len(trace.steps),
            escalation_count=int(metrics["escalation_count"]),
            revisit_count=int(metrics["revisit_count"]),
            success_rate=metrics["success_rate"],
            avg_tension=metrics["avg_tension"],
            total_tension=float(trace.total_tension),
            reached_goal=goal_reached,
            happy_path_length=spec.happy_path_length,
        ).rating,
        success_rate=round(metrics["success_rate"], 3),
        escalations=int(metrics["escalation_count"]),
        revisits=int(metrics["revisit_count"]),
        efficiency=round(
            spec.happy_path_length / max(len(trace.steps), 1), 3
        ),
        avg_tension=round(metrics["avg_tension"], 4),
        unique_states=int(metrics["unique_states"]),
        path=trace.path,
    )


def run_modulation_comparison(
    spec_builders: List[Callable],
    max_cycles: int = 50,
) -> List[ModulationComparison]:
    """Run each domain in all 3 modes, compare paths."""
    comparisons = []
    for builder in spec_builders:
        results = {}
        for mode in MODES:
            spec = builder()  # fresh landscape per mode
            results[mode] = run_modulation_domain(spec, mode, max_cycles)

        baseline = results["BASELINE"]
        overlap = results["OVERLAP"]
        full = results["FULL"]

        comparisons.append(ModulationComparison(
            domain=baseline.domain,
            baseline=baseline,
            overlap=overlap,
            full=full,
            path_changed_overlap=baseline.path != overlap.path,
            path_changed_full=baseline.path != full.path,
            steps_delta_overlap=overlap.steps - baseline.steps,
            steps_delta_full=full.steps - baseline.steps,
        ))
    return comparisons


def run_benchmark(max_cycles: int = 50) -> List[ModulationComparison]:
    """Run full benchmark: 10 standard + 4 stress domains × 3 modes."""
    return run_modulation_comparison(
        ALL_DOMAINS + STRESS_DOMAINS, max_cycles
    )


# ══════════════════════════════════════════════
# Output
# ══════════════════════════════════════════════

def print_results(comparisons: List[ModulationComparison]) -> None:
    """Pretty-print benchmark comparison table."""
    print("\n" + "=" * 100)
    print("  E₀ Modulation Benchmark — C100")
    print("  10 Standard Domains + 4 Stress Domains × 3 Modes")
    print("  BASELINE (no modulation) | OVERLAP (C98) | FULL (C98+C99)")
    print("=" * 100)

    header = (
        f"{'Domain':<28} │ {'BASE':>4} {'stp':>4} {'eff':>5} │ "
        f"{'OVLP':>4} {'stp':>4} {'Δ':>3} {'chg':>3} │ "
        f"{'FULL':>4} {'stp':>4} {'Δ':>3} {'chg':>3}"
    )
    print(header)
    print("─" * 100)

    n_changed_overlap = 0
    n_changed_full = 0
    all_goals_base = True
    all_goals_overlap = True
    all_goals_full = True

    for c in comparisons:
        b = c.baseline
        o = c.overlap
        f = c.full

        b_goal = "✓" if b.goal_reached else "✗"
        o_goal = "✓" if o.goal_reached else "✗"
        f_goal = "✓" if f.goal_reached else "✗"

        o_delta = f"{c.steps_delta_overlap:+d}" if c.steps_delta_overlap != 0 else " ·"
        f_delta = f"{c.steps_delta_full:+d}" if c.steps_delta_full != 0 else " ·"

        o_chg = "YES" if c.path_changed_overlap else " · "
        f_chg = "YES" if c.path_changed_full else " · "

        if c.path_changed_overlap:
            n_changed_overlap += 1
        if c.path_changed_full:
            n_changed_full += 1

        all_goals_base = all_goals_base and b.goal_reached
        all_goals_overlap = all_goals_overlap and o.goal_reached
        all_goals_full = all_goals_full and f.goal_reached

        print(
            f"{c.domain:<28} │ {b_goal:>4} {b.steps:>4} {b.efficiency:>5.2f} │ "
            f"{o_goal:>4} {o.steps:>4} {o_delta:>3} {o_chg:>3} │ "
            f"{f_goal:>4} {f.steps:>4} {f_delta:>3} {f_chg:>3}"
        )

    print("─" * 100)
    total = len(comparisons)
    print(f"\n  Goals reached:   BASE={all_goals_base}  OVERLAP={all_goals_overlap}  FULL={all_goals_full}")
    print(f"  Path changed:    OVERLAP={n_changed_overlap}/{total}  FULL={n_changed_full}/{total}")
    print(f"  Total domains:   {total} (10 standard + 4 stress)")
    print()


def results_to_dict(comparisons: List[ModulationComparison]) -> dict:
    """Convert results to JSON-serializable dict."""
    return {
        "benchmark": "modulation_c100",
        "modes": MODES,
        "domains": [
            {
                "domain": c.domain,
                "baseline": {
                    "goal_reached": c.baseline.goal_reached,
                    "steps": c.baseline.steps,
                    "rating": c.baseline.rating,
                    "efficiency": c.baseline.efficiency,
                    "escalations": c.baseline.escalations,
                    "revisits": c.baseline.revisits,
                },
                "overlap": {
                    "goal_reached": c.overlap.goal_reached,
                    "steps": c.overlap.steps,
                    "rating": c.overlap.rating,
                    "efficiency": c.overlap.efficiency,
                    "escalations": c.overlap.escalations,
                    "revisits": c.overlap.revisits,
                },
                "full": {
                    "goal_reached": c.full.goal_reached,
                    "steps": c.full.steps,
                    "rating": c.full.rating,
                    "efficiency": c.full.efficiency,
                    "escalations": c.full.escalations,
                    "revisits": c.full.revisits,
                },
                "path_changed_overlap": c.path_changed_overlap,
                "path_changed_full": c.path_changed_full,
                "steps_delta_overlap": c.steps_delta_overlap,
                "steps_delta_full": c.steps_delta_full,
            }
            for c in comparisons
        ],
    }


# ══════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════

if __name__ == "__main__":
    results = run_benchmark()
    if "--json" in sys.argv:
        print(json.dumps(results_to_dict(results), indent=2))
    else:
        print_results(results)
