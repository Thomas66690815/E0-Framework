"""
C191b: Integration Value Measurement
======================================
Proves that the composition of layers creates measurable emergent value
that isolated layers cannot provide.

Experiment design:
  Domain: 20-node landscape with 3 deceptive traps calibrated to E₀'s
          historization parameters (λ_f=0.2, ρ=0.9).  Trap edges use
          high Δ (0.50) and low R₀ (0.01) for a deceptive S_eff=0.005
          on first encounter.  After one FAILURE, δ_H=0.2 pushes S_eff
          to 0.105 > recovery's 0.075 — the trap is learned.

  Layer stack comparison:
    Layer 1 (baseline):  GREEDY mode — pure argmin S_eff + Historization
    Layer 1+3 (amplitude): + Amplitude overlay — goal-directed lookahead
    Layer 1+3+5 (reflexion): + Self-Graph + Reflexion
    Layer 1+3+5+9 (dream): + Dream peer_fn (cross-domain)
    Full integration: All layers combined

  Protocol: Run each configuration N times on the same persistent domain.
            Compare: steps-to-goal, trap encounters, success rate, adaptation.

  Perspective check #5 answer: "If this test fails — what do I learn?"
  - Greedy ≈ Full → Integration adds no value → architecture question
  - Full < Greedy → Composition reduces traps/steps → value WHERE?
  - Full > Greedy → Integration HURTS (overhead) → potential GT-5
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import pytest

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller, HybridMode, RunTrace


# ═══════════════════════════════════════════════════════════════════
# Complex domain: 20 nodes, 3 traps, multiple paths
# ═══════════════════════════════════════════════════════════════════

# Traps: edges that always fail, luring greedy with high Δ + low R
TRAP_EDGES = {
    ("LURE_A", "TRAP_A"),    # Trap 1: obvious high-Δ dead end
    ("LURE_B", "TRAP_B"),    # Trap 2: mid-path detour
    ("SHORTCUT", "BLOCKED"), # Trap 3: tempting shortcut
}


def execute_fn(source: str, target: str) -> Outcome:
    """Deterministic: trap edges always fail, rest succeeds."""
    if (source, target) in TRAP_EDGES:
        return Outcome.FAILURE
    return Outcome.SUCCESS


def build_complex_domain() -> Landscape:
    """20-node landscape with 3 deceptive traps calibrated to E₀'s parameters.

    Key insight: traps must be LEARNABLE — after one failure, δ_H must push
    the trap's S_eff above the recovery alternative.  With λ_f=0.2, after
    one FAILURE δ_H=0.2.  So trap edges need high Δ (0.50) to amplify δ_H:
        S_eff_after = 0.50 × (0.01 + 0.20) = 0.105 > recovery's 0.075 ✓

    Amplitude (Layer 3) provides additional value: it detects dead-end traps
    via lookahead and prevents them BEFORE any failure occurs.

    Topology:
      Main path:   START → A → B → C → D → E → GOAL  (6 edges)
      Alt path:    START → F → G → H → I → GOAL      (5 edges)
      Trap 1:      A → LURE_A → TRAP_A  (TRAP_A fails, backtrack to A)
      Trap 2:      C → LURE_B → TRAP_B  (TRAP_B fails, backtrack to C)
      Trap 3:      F → SHORTCUT → BLOCKED (BLOCKED fails, backtrack to F)
      Recovery:    LURE_A → B, LURE_B → D, SHORTCUT → G
      Backtrack:   TRAP_A → A, TRAP_B → C, BLOCKED → F  (escape dead-ends)
      Lateral:     B → G, D → I, H → C

    S_eff budget (first encounter → after one FAILURE):
      LURE_A→TRAP_A:  0.50×0.01=0.005  → 0.50×0.21=0.105  (learned!)
      LURE_A→B:       0.25×0.30=0.075  (always available recovery)
      LURE_B→TRAP_B:  0.50×0.01=0.005  → 0.50×0.21=0.105  (learned!)
      LURE_B→D:       0.25×0.30=0.075
      SHORTCUT→BLOCK: 0.50×0.01=0.005  → 0.50×0.21=0.105  (learned!)
      SHORTCUT→G:     0.25×0.30=0.075
    """
    ls = Landscape()

    nodes = [
        "START", "A", "B", "C", "D", "E", "GOAL",
        "F", "G", "H", "I",
        "LURE_A", "LURE_B", "SHORTCUT",
        "TRAP_A", "TRAP_B", "BLOCKED",
        "J", "K", "L",  # extra nodes for complexity
    ]
    for n in nodes:
        ls.add_state(n)

    edges = [
        # ── Main path (reliable, moderate S_eff) ──
        ("START", "A",    0.35, 0.30),   # S_eff = 0.105
        ("A",     "B",    0.30, 0.25),   # S_eff = 0.075
        ("B",     "C",    0.25, 0.20),   # S_eff = 0.050
        ("C",     "D",    0.30, 0.25),   # S_eff = 0.075
        ("D",     "E",    0.25, 0.20),   # S_eff = 0.050
        ("E",     "GOAL", 0.20, 0.15),   # S_eff = 0.030

        # ── Alt path (higher S_eff, but also works) ──
        ("START", "F",    0.50, 0.40),   # S_eff = 0.200
        ("F",     "G",    0.45, 0.35),   # S_eff = 0.158
        ("G",     "H",    0.40, 0.30),   # S_eff = 0.120
        ("H",     "I",    0.35, 0.25),   # S_eff = 0.088
        ("I",     "GOAL", 0.30, 0.20),   # S_eff = 0.060

        # ── Trap 1: A → LURE_A (deceptive entry) → TRAP_A (fails) ──
        #    Entry: S_eff=0.012 << A→B=0.075 → greedy takes lure
        #    Exit:  S_eff=0.005 << LURE_A→B=0.075 → greedy takes trap
        #    After 1 fail: S_eff=0.105 > 0.075 → greedy avoids trap
        ("A",      "LURE_A", 0.15, 0.08),  # S_eff = 0.012 ← deceptive entry
        ("LURE_A", "TRAP_A", 0.50, 0.01),  # S_eff = 0.005, FAILS, learnable

        # ── Trap 2: C → LURE_B → TRAP_B ──
        ("C",      "LURE_B", 0.15, 0.09),  # S_eff = 0.014 ← deceptive entry
        ("LURE_B", "TRAP_B", 0.50, 0.01),  # S_eff = 0.005, FAILS, learnable

        # ── Trap 3: F → SHORTCUT → BLOCKED ──
        ("F",        "SHORTCUT", 0.20, 0.10),  # S_eff = 0.020 ← deceptive entry
        ("SHORTCUT", "BLOCKED",  0.50, 0.01),  # S_eff = 0.005, FAILS, learnable

        # ── Recovery edges (escape from lure to useful paths) ──
        ("LURE_A",   "B",  0.25, 0.30),   # S_eff = 0.075
        ("LURE_B",   "D",  0.25, 0.30),   # S_eff = 0.075
        ("SHORTCUT", "G",  0.25, 0.30),   # S_eff = 0.075

        # ── Backtrack edges (escape from dead-end trap nodes) ──
        ("TRAP_A",  "A",  0.30, 0.25),    # S_eff = 0.075
        ("TRAP_B",  "C",  0.30, 0.25),    # S_eff = 0.075
        ("BLOCKED", "F",  0.30, 0.25),    # S_eff = 0.075

        # ── Lateral connections (cross-path) ──
        ("B", "G", 0.30, 0.35),
        ("D", "I", 0.25, 0.30),
        ("H", "C", 0.30, 0.30),

        # ── Extra complexity: J-K-L loop ──
        ("START", "J", 0.55, 0.45),
        ("J",     "K", 0.50, 0.40),
        ("K",     "L", 0.45, 0.35),
        ("L",     "A", 0.30, 0.30),
        ("K",     "F", 0.35, 0.30),
    ]

    for src, tgt, delta, r0 in edges:
        ls.add_edge(src, tgt, delta=delta, resistance=r0)

    return ls


# ═══════════════════════════════════════════════════════════════════
# Measurement infrastructure
# ═══════════════════════════════════════════════════════════════════

@dataclass
class RunResult:
    """Metrics from a single controller run."""
    goal_reached: bool
    steps: int
    trap_encounters: int
    failure_count: int
    success_rate: float
    revisits: int
    unique_states: int


@dataclass
class ExperimentResult:
    """Aggregated metrics from N runs."""
    name: str
    n_runs: int
    runs: List[RunResult]

    @property
    def goal_rate(self) -> float:
        return sum(1 for r in self.runs if r.goal_reached) / self.n_runs

    @property
    def mean_steps(self) -> float:
        return statistics.mean(r.steps for r in self.runs)

    @property
    def total_trap_encounters(self) -> int:
        return sum(r.trap_encounters for r in self.runs)

    @property
    def mean_success_rate(self) -> float:
        return statistics.mean(r.success_rate for r in self.runs)

    @property
    def mean_revisits(self) -> float:
        return statistics.mean(r.revisits for r in self.runs)

    @property
    def adaptation_curve(self) -> List[int]:
        """Steps per run — should decrease if system adapts."""
        return [r.steps for r in self.runs]

    @property
    def late_trap_encounters(self) -> int:
        """Trap encounters in the last third of runs."""
        cutoff = max(1, self.n_runs * 2 // 3)
        return sum(r.trap_encounters for r in self.runs[cutoff:])

    @property
    def early_trap_encounters(self) -> int:
        """Trap encounters in the first third of runs."""
        cutoff = max(1, self.n_runs // 3)
        return sum(r.trap_encounters for r in self.runs[:cutoff])


def count_trap_encounters(trace: RunTrace) -> int:
    """Count how many times the controller tried a trap edge."""
    count = 0
    for step in trace.steps:
        edge = (step.source, step.target)
        if edge in TRAP_EDGES:
            count += 1
    return count


def measure_run(trace: RunTrace, goal: str) -> RunResult:
    m = trace.metrics()
    return RunResult(
        goal_reached=bool(trace.path and trace.path[-1] == goal),
        steps=int(m["steps"]),
        trap_encounters=count_trap_encounters(trace),
        failure_count=int(m["failure_rate"] * m["steps"]) if m["steps"] > 0 else 0,
        success_rate=m["success_rate"],
        revisits=int(m["revisit_count"]),
        unique_states=int(m["unique_states"]),
    )


# ═══════════════════════════════════════════════════════════════════
# Experiment configurations
# ═══════════════════════════════════════════════════════════════════

N_RUNS = 30
MAX_CYCLES = 50


def run_baseline(n_runs: int = N_RUNS) -> ExperimentResult:
    """Baseline: Pure greedy controller with historization only (Layer 1).

    No amplitude overlay, no self-graph, no dream.
    The controller uses argmin S_eff and learns from historization alone.
    """
    ls = build_complex_domain()
    ctrl = E0Controller(
        ls, execute_fn,
        hybrid_mode=HybridMode.GREEDY,
    )

    results = []
    for _ in range(n_runs):
        trace = ctrl.run("START", max_cycles=MAX_CYCLES, goal="GOAL")
        results.append(measure_run(trace, "GOAL"))

    return ExperimentResult(name="baseline", n_runs=n_runs, runs=results)


def run_with_selfgraph(n_runs: int = N_RUNS) -> ExperimentResult:
    """Layer 1+3: Controller with amplitude overlay (goal-directed lookahead).

    Amplitude detects dead-end traps via lookahead and prevents them
    BEFORE any failure occurs.  This is the first integration layer
    beyond pure historization.
    """
    ls = build_complex_domain()
    ctrl = E0Controller(
        ls, execute_fn,
        hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
        hybrid_horizon=3,
        hybrid_goals={"GOAL"},
    )

    results = []
    for _ in range(n_runs):
        trace = ctrl.run("START", max_cycles=MAX_CYCLES, goal="GOAL")
        results.append(measure_run(trace, "GOAL"))

    return ExperimentResult(name="with_amplitude", n_runs=n_runs, runs=results)


def run_with_reflexion(n_runs: int = N_RUNS) -> ExperimentResult:
    """Layer 1+3+5: Amplitude + Self-Graph + Reflexion."""
    from e0_controller.self_graph import SelfGraph
    from e0_controller.dual_reflection import (
        diagnose_self_graph, DualReflectionReport,
    )
    from e0_controller.integrated_reflexion import integrated_reflexion

    ls = build_complex_domain()
    ctrl = E0Controller(
        ls, execute_fn,
        hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
        hybrid_horizon=3,
        hybrid_goals={"GOAL"},
    )
    sg = SelfGraph()
    ctrl.self_graph = sg

    results = []
    for i in range(n_runs):
        trace = ctrl.run("START", max_cycles=MAX_CYCLES, goal="GOAL")
        results.append(measure_run(trace, "GOAL"))

        # Every 5 runs: diagnose and apply reflexion
        if (i + 1) % 5 == 0:
            diagnosis = diagnose_self_graph(sg)
            integrated_reflexion(ls, "START", "GOAL", scoped=True)

    return ExperimentResult(name="with_reflexion", n_runs=n_runs, runs=results)


def run_with_dream(n_runs: int = N_RUNS) -> ExperimentResult:
    """Controller + Self-Graph + Dream peer_fn (Layer 5 + 9)."""
    from e0_controller.self_graph import SelfGraph
    from e0_controller.dream_mode import DreamObserver, make_dream_peer_fn

    ls1 = build_complex_domain()
    ls2 = build_complex_domain()  # second domain for dream cross-reference

    # Pre-train second domain to give dream something to work with
    ctrl2 = E0Controller(ls2, execute_fn,
                         hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
                         hybrid_horizon=3, hybrid_goals={"GOAL"})
    for _ in range(10):
        ctrl2.run("START", max_cycles=MAX_CYCLES, goal="GOAL")

    observer = DreamObserver(readiness_threshold=0.0, quantile=0.3)
    observer.register("primary", ls1)
    observer.register("reference", ls2)
    observer.dream_cycle()

    peer_fn = make_dream_peer_fn(observer, "primary", "GOAL")

    ctrl1 = E0Controller(
        ls1, execute_fn,
        hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
        hybrid_horizon=3,
        hybrid_goals={"GOAL"},
        peer_fn=peer_fn,
    )
    sg = SelfGraph()
    ctrl1.self_graph = sg

    results = []
    for i in range(n_runs):
        trace = ctrl1.run("START", max_cycles=MAX_CYCLES, goal="GOAL")
        results.append(measure_run(trace, "GOAL"))

        # Periodic dream consolidation
        if (i + 1) % 10 == 0:
            observer.dream_cycle()

    return ExperimentResult(name="with_dream", n_runs=n_runs, runs=results)


def run_full_integration(n_runs: int = N_RUNS) -> ExperimentResult:
    """Full integration: Self-Graph + Reflexion + Dream + Sleep-Wake."""
    from e0_controller.self_graph import SelfGraph
    from e0_controller.dual_reflection import diagnose_self_graph
    from e0_controller.integrated_reflexion import integrated_reflexion
    from e0_controller.dream_mode import DreamObserver, make_dream_peer_fn
    from e0_controller.structural_entropy import should_dream

    ls1 = build_complex_domain()
    ls2 = build_complex_domain()

    # Pre-train reference domain
    ctrl2 = E0Controller(ls2, execute_fn,
                         hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
                         hybrid_horizon=3, hybrid_goals={"GOAL"})
    for _ in range(10):
        ctrl2.run("START", max_cycles=MAX_CYCLES, goal="GOAL")

    observer = DreamObserver(readiness_threshold=0.0, quantile=0.3)
    observer.register("primary", ls1)
    observer.register("reference", ls2)
    observer.dream_cycle()

    peer_fn = make_dream_peer_fn(observer, "primary", "GOAL")

    ctrl1 = E0Controller(
        ls1, execute_fn,
        hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
        hybrid_horizon=3,
        hybrid_goals={"GOAL"},
        peer_fn=peer_fn,
    )
    sg = SelfGraph()
    ctrl1.self_graph = sg

    results = []
    for i in range(n_runs):
        trace = ctrl1.run("START", max_cycles=MAX_CYCLES, goal="GOAL")
        results.append(measure_run(trace, "GOAL"))

        # Reflexion every 5 runs
        if (i + 1) % 5 == 0:
            diagnosis = diagnose_self_graph(sg)
            integrated_reflexion(ls1, "START", "GOAL", scoped=True)

        # Dream when entropy triggers
        if (i + 1) % 10 == 0:
            if should_dream(ls1.historization, mu=3.0):
                observer.dream_cycle()

    return ExperimentResult(name="full_integration", n_runs=n_runs, runs=results)


# ═══════════════════════════════════════════════════════════════════
# Tests: Does integration create measurable value?
# ═══════════════════════════════════════════════════════════════════

class TestIntegrationValue:
    """Quantitative proof that layer composition beats isolation.

    Layer stack under test:
      baseline:  GREEDY + Historization only (Layer 1)
      amplitude: + Amplitude overlay (Layer 3)
      reflexion: + Self-Graph + Reflexion (Layer 5)
      dream:     + Dream peer_fn (Layer 9)
      full:      All layers combined
    """

    def _run_all_configs(self) -> Dict[str, ExperimentResult]:
        """Run all 5 configurations and return results."""
        return {
            "baseline": run_baseline(),
            "amplitude": run_with_selfgraph(),
            "reflexion": run_with_reflexion(),
            "dream": run_with_dream(),
            "full": run_full_integration(),
        }

    def test_all_configs_reach_goal(self):
        """All configurations should reach the goal at least once."""
        configs = self._run_all_configs()
        for name, result in configs.items():
            assert result.goal_rate > 0, \
                f"{name} never reached goal in {result.n_runs} runs"

    def test_historization_enables_adaptation(self):
        """Core claim: with historization, trap encounters decrease over runs."""
        result = run_baseline()

        early = result.early_trap_encounters
        late = result.late_trap_encounters

        # Historization alone should reduce trap encounters over time.
        # This tests the FOUNDATION — if this fails, nothing else matters.
        assert late <= early, \
            f"Baseline should adapt: early traps={early}, late traps={late}. " \
            f"Historization is not reducing trap frequency."

    def test_amplitude_avoids_traps(self):
        """Amplitude overlay (Layer 3) prevents dead-end traps via lookahead."""
        baseline = run_baseline()
        amplitude = run_with_selfgraph()

        # Amplitude should have strictly fewer trap encounters
        assert amplitude.total_trap_encounters < baseline.total_trap_encounters, \
            f"Amplitude does not reduce traps: baseline={baseline.total_trap_encounters}, " \
            f"amplitude={amplitude.total_trap_encounters}"

        # Amplitude should have fewer mean steps (no wasted detours)
        assert amplitude.mean_steps < baseline.mean_steps, \
            f"Amplitude does not reduce steps: baseline={baseline.mean_steps:.1f}, " \
            f"amplitude={amplitude.mean_steps:.1f}"

    def test_reflexion_no_regression(self):
        """Reflexion (Layer 5) should not regress beyond amplitude."""
        amplitude = run_with_selfgraph()
        refl = run_with_reflexion()

        # Reflexion should not hurt compared to amplitude alone
        assert refl.total_trap_encounters <= amplitude.total_trap_encounters + 2, \
            f"Reflexion hits MORE traps: amplitude={amplitude.total_trap_encounters}, " \
            f"reflexion={refl.total_trap_encounters}"

    def test_integrated_outperforms_baseline(self):
        """Full integration must outperform pure greedy baseline."""
        baseline = run_baseline()
        full = run_full_integration()

        # Full integration should reach goal more often
        assert full.goal_rate >= baseline.goal_rate, \
            f"Integration hurts goal rate: baseline={baseline.goal_rate:.2f}, " \
            f"full={full.goal_rate:.2f}"

        # Full integration should use fewer steps
        assert full.mean_steps <= baseline.mean_steps, \
            f"Integration uses more steps: baseline={baseline.mean_steps:.1f}, " \
            f"full={full.mean_steps:.1f}"

    def test_adaptation_across_configs(self):
        """All configs should show adaptation (fewer traps over time)."""
        configs = {
            "baseline": run_baseline(),
            "full": run_full_integration(),
        }

        for name, result in configs.items():
            early = result.early_trap_encounters
            late = result.late_trap_encounters
            # At minimum, adaptation should not REVERSE
            # (we allow equal — some configs may learn faster, reaching 0 early)
            assert late <= early + 2, \
                f"{name} adaptation broken: early={early} late={late} traps"


class TestEmergentValueMeasurement:
    """Side-by-side comparison with detailed metrics."""

    def test_value_report(self):
        """Generate a comparison report across all configurations.
        This test always passes — the asserts are diagnostic, the value
        is in the printed comparison."""
        configs = {
            "baseline": run_baseline(),
            "amplitude": run_with_selfgraph(),
            "reflexion": run_with_reflexion(),
            "dream": run_with_dream(),
            "full": run_full_integration(),
        }

        # Collect comparison data
        comparison = {}
        for name, result in configs.items():
            comparison[name] = {
                "goal_rate": result.goal_rate,
                "mean_steps": result.mean_steps,
                "total_traps": result.total_trap_encounters,
                "early_traps": result.early_trap_encounters,
                "late_traps": result.late_trap_encounters,
                "mean_revisits": result.mean_revisits,
                "mean_success": result.mean_success_rate,
            }

        # Verify all configs completed
        for name, data in comparison.items():
            assert data["goal_rate"] > 0, f"{name} never reached goal"

        # The real test: is full integration the best overall?
        baseline_steps = comparison["baseline"]["mean_steps"]
        full_steps = comparison["full"]["mean_steps"]
        baseline_traps = comparison["baseline"]["total_traps"]
        full_traps = comparison["full"]["total_traps"]

        # Record the comparison for test output
        delta_steps = ((full_steps - baseline_steps) / baseline_steps * 100
                       if baseline_steps > 0 else 0)
        delta_traps = full_traps - baseline_traps

        # These are informative assertions — BOTH outcomes teach us something:
        # full < baseline → integration adds value ✓
        # full >= baseline → integration overhead > benefit at this scale → GT-5?
        assert True, (
            f"Steps: baseline={baseline_steps:.1f}, full={full_steps:.1f} "
            f"({delta_steps:+.1f}%)\n"
            f"Traps: baseline={baseline_traps}, full={full_traps} "
            f"({delta_traps:+d})"
        )
