"""
C173 — Structural Skepticism Exploration

Tests whether run-level meta-observation can detect coherent deception
that per-edge metrics miss.

Core idea: load accumulates without frontier expansion → structural stagnation.
Response: force exploration of least-visited neighbor (exploratory escape).

Reuses C172 adversarial domains + new Scenario D (false-positive control).

Reference: docs/research/E0_STRUCTURAL_SKEPTICISM_RESEARCH_v1.md
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Set

from e0_controller.controller import E0Controller, HybridMode, StepResult
from e0_controller.landscape import Landscape
from e0_controller.primitives import Edge, Outcome
from e0_controller.self_graph import SelfGraph
from e0_controller.structural_entropy import structural_temperature


# ── Skepticism Monitor ───────────────────────────────────────────────

@dataclass
class SkepticismEvent:
    """Record of a skepticism trigger."""
    cycle: int
    progress_rate: float
    revisit_rate: float
    total_unique: int
    total_revisits: int
    action: str  # what the monitor did


@dataclass
class SkepticalRunner:
    """
    Wraps E0Controller.run() with a structural skepticism monitor.

    Every `window` cycles, checks:
      - progress_rate: fraction of window steps that visited a new state
      - revisit_rate: fraction of window steps that revisited a known state

    If progress_rate == 0 and revisit_rate > revisit_threshold for a full
    window, triggers SKEPTICISM and forces the next step to explore the
    least-loaded neighbor instead of the greedy choice.

    Parameters
    ----------
    controller : E0Controller
        The controller to wrap.
    window : int
        Evaluation window size (default: 5).
    min_warmup : int
        Minimum cycles before skepticism can trigger (default: 5).
    revisit_threshold : float
        Minimum revisit_rate to trigger (default: 0.5).
    """
    controller: E0Controller
    window: int = 5
    min_warmup: int = 5
    revisit_threshold: float = 0.5

    events: List[SkepticismEvent] = field(default_factory=list)
    _visited: Set[str] = field(default_factory=set)
    _force_explore: bool = field(default=False)
    _cleanup_tension: Optional[tuple] = field(default=None)

    def _apply_exploration_override(self, ctrl: E0Controller, current: str):
        """
        Force controller to pick least-loaded / unvisited neighbor.
        Monkey-patches _penalized_tension for one cycle.
        """
        neighbors = ctrl.landscape.admissible_neighbors(current)
        if not neighbors:
            return

        unvisited = [n for n in neighbors if n not in self._visited]

        if unvisited:
            target_override = min(
                unvisited,
                key=lambda n: ctrl.landscape.historization.trace_load(
                    Edge(current, n)))
        else:
            target_override = min(
                neighbors,
                key=lambda n: ctrl.landscape.historization.trace_load(
                    Edge(current, n)))

        original_penalized = ctrl._penalized_tension

        def skeptical_tension(x, y):
            if x == current and y == target_override:
                return -1e10
            return original_penalized(x, y)

        ctrl._penalized_tension = skeptical_tension
        self._cleanup_tension = (ctrl, original_penalized)

    def run(self, start: str, max_cycles: int = 50, goal: str | None = None):
        """Run the controller with skepticism monitoring."""
        ctrl = self.controller
        self.events.clear()
        self._visited = {start}
        self._force_explore = False
        self._cleanup_tension = None

        # Track first-visit per step for accurate window computation
        first_visit_flags: List[bool] = []

        steps: List[StepResult] = []
        current = start

        goal_set = set()
        if goal:
            goal_set.add(goal)

        for cycle_idx in range(max_cycles):
            if current in goal_set:
                break

            # ── Skepticism override ──
            if self._force_explore:
                self._apply_exploration_override(ctrl, current)

            # ── Normal cycle ──
            step = ctrl.cycle(current)

            # ── Restore tension function if overridden ──
            if self._cleanup_tension is not None:
                c, orig = self._cleanup_tension
                c._penalized_tension = orig
                self._cleanup_tension = None
                self._force_explore = False

            if step is None:
                break

            steps.append(step)
            target = step.target

            is_new = target not in self._visited
            first_visit_flags.append(is_new)
            self._visited.add(target)

            # ── Window evaluation ──
            if (len(first_visit_flags) >= self.window
                    and cycle_idx >= self.min_warmup):
                window_flags = first_visit_flags[-self.window:]
                progress_rate = sum(window_flags) / self.window
                revisit_rate = 1.0 - progress_rate

                if (progress_rate == 0.0
                        and revisit_rate >= self.revisit_threshold):
                    event = SkepticismEvent(
                        cycle=cycle_idx,
                        progress_rate=progress_rate,
                        revisit_rate=revisit_rate,
                        total_unique=len(self._visited),
                        total_revisits=sum(1 for f in first_visit_flags
                                           if not f),
                        action="EXPLORATORY_ESCAPE",
                    )
                    self.events.append(event)
                    self._force_explore = True

            current = target

        return SkepticalRunResult(
            steps=steps,
            path=[start] + [s.target for s in steps],
            events=self.events,
            goal_reached=current in goal_set if goal_set else False,
            unique_states=len(self._visited),
        )


@dataclass
class SkepticalRunResult:
    """Result of a skeptical run."""
    steps: List[StepResult]
    path: List[str]
    events: List[SkepticismEvent]
    goal_reached: bool
    unique_states: int

    @property
    def skepticism_count(self) -> int:
        return len(self.events)


# ── Helpers ──────────────────────────────────────────────────────────

def trace_info(L: Landscape, src: str, tgt: str) -> dict:
    e = Edge(src, tgt)
    h = L.historization
    return {
        "quality": round(h.trace_quality(e), 4),
        "load": round(h.trace_load(e), 4),
        "inertia": round(h.inertia_factor(e), 4),
    }


def print_traces(L: Landscape, edges: list[tuple[str, str]], label: str = ""):
    if label:
        print(f"  {label}:")
    for src, tgt in edges:
        info = trace_info(L, src, tgt)
        print(f"    {src}→{tgt}: q={info['quality']:+.4f}  "
              f"load={info['load']:.4f}  I={info['inertia']:.4f}")


# ══════════════════════════════════════════════════════════════════════
# SCENARIO A: Hidden Reward Flip (+ Skepticism)
# ══════════════════════════════════════════════════════════════════════

def scenario_a():
    """
    Reuses C172 Scenario A: trap loop A ↔ TRAP with consistent SUCCESS.
    Without skepticism: 30 cycles trapped (C172 result).
    With skepticism: should escape after 1 window of stagnation.
    """
    print("=" * 72)
    print("SCENARIO A: Hidden Reward Flip (+ Structural Skepticism)")
    print("=" * 72)
    print()

    # Build domain (identical to C172)
    L = Landscape()
    for s in ["START", "A", "B", "GOAL", "TRAP"]:
        L.add_state(s)
    L.add_edge("START", "A", delta=0.5, resistance=1.0)
    L.add_edge("A", "B", delta=0.8, resistance=0.7)
    L.add_edge("B", "GOAL", delta=0.3, resistance=0.5)
    L.add_edge("A", "TRAP", delta=0.9, resistance=0.3)
    L.add_edge("TRAP", "A", delta=0.4, resistance=0.3)

    trap_visits = [0]
    goal_reached = [False]

    def adversarial_exec(src, tgt):
        if tgt == "GOAL":
            goal_reached[0] = True
            return Outcome.SUCCESS
        if tgt == "TRAP" or (src == "TRAP" and tgt == "A"):
            trap_visits[0] += 1
            return Outcome.SUCCESS  # THE LIE
        return Outcome.SUCCESS

    ctrl = E0Controller(L, adversarial_exec, alpha=2.0, recent_k=3)
    runner = SkepticalRunner(controller=ctrl, window=5, min_warmup=5)
    result = runner.run("START", max_cycles=30, goal="GOAL")

    print(f"  Steps taken: {len(result.steps)}")
    print(f"  Goal reached: {result.goal_reached}")
    print(f"  Trap visits: {trap_visits[0]}")
    print(f"  Unique states: {result.unique_states}")
    print(f"  Skepticism events: {result.skepticism_count}")
    for evt in result.events:
        print(f"    cycle {evt.cycle}: progress={evt.progress_rate:.2f} "
              f"revisit={evt.revisit_rate:.2f} → {evt.action}")
    print(f"  Path: {' → '.join(result.path)}")
    print()
    print_traces(L, [("A", "TRAP"), ("TRAP", "A"), ("A", "B"),
                     ("B", "GOAL")], "Final traces")
    print()

    verdict = "PASS" if result.goal_reached else "FAIL"
    print(f"  VERDICT: {verdict}")
    if result.goal_reached and result.skepticism_count > 0:
        print(f"  → Skepticism detected trap after {result.events[0].cycle} cycles")
        print(f"  → Exploratory escape led to goal discovery")
    elif not result.goal_reached:
        print(f"  → Skepticism {'triggered' if result.skepticism_count > 0 else 'did NOT trigger'} but goal not reached")

    return {"verdict": verdict, "result": result, "trap_visits": trap_visits[0]}


# ══════════════════════════════════════════════════════════════════════
# SCENARIO B: Systematic Poisoning (+ Skepticism)
# ══════════════════════════════════════════════════════════════════════

def scenario_b():
    """
    Reuses C172 Scenario B: poisoned path (C↔D loop) vs honest path.
    Without skepticism: all 4 configs fail.
    With skepticism: should escape poisoned loop.
    """
    print()
    print("=" * 72)
    print("SCENARIO B: Systematic Poisoning (+ Structural Skepticism)")
    print("=" * 72)
    print()

    configs = [
        ("skepticism only", False, False),
        ("skepticism + inertia", True, False),
        ("skepticism + self_graph", False, True),
        ("skepticism + inertia + sg", True, True),
    ]

    results = {}

    for config_name, use_inertia, use_sg in configs:
        L = Landscape()
        for s in ["START", "A", "B", "C", "D", "GOAL"]:
            L.add_state(s)
        L.add_edge("START", "A", delta=0.5, resistance=1.0)
        L.add_edge("A", "B", delta=0.8, resistance=0.7)
        L.add_edge("B", "GOAL", delta=0.3, resistance=0.5)
        L.add_edge("START", "C", delta=0.6, resistance=0.4)
        L.add_edge("C", "D", delta=0.7, resistance=0.3)
        L.add_edge("D", "C", delta=0.5, resistance=0.3)
        L.add_edge("D", "GOAL", delta=0.2, resistance=3.0)

        if use_inertia:
            L.inertia_modulation = True

        poison_visits = [0]
        goal_reached = [False]

        def poisoned_exec(src, tgt):
            if tgt == "GOAL":
                goal_reached[0] = True
                return Outcome.SUCCESS
            if tgt in ("C", "D"):
                poison_visits[0] += 1
                return Outcome.SUCCESS
            return Outcome.SUCCESS

        ctrl = E0Controller(L, poisoned_exec, alpha=2.0, recent_k=3)
        if use_sg:
            ctrl.self_graph = SelfGraph()

        runner = SkepticalRunner(controller=ctrl, window=5, min_warmup=5)
        result = runner.run("START", max_cycles=40, goal="GOAL")

        path_str = " → ".join(result.path[:15])
        if len(result.path) > 15:
            path_str += f" ... ({len(result.path)} total)"

        verdict = "PASS" if result.goal_reached else "FAIL"

        print(f"  Config: {config_name}")
        print(f"    Goal reached: {result.goal_reached}")
        print(f"    Steps: {len(result.steps)}, Poison visits: {poison_visits[0]}")
        print(f"    Skepticism events: {result.skepticism_count}")
        for evt in result.events:
            print(f"      cycle {evt.cycle}: progress={evt.progress_rate:.2f} "
                  f"revisit={evt.revisit_rate:.2f} → {evt.action}")
        print(f"    Path: {path_str}")
        print(f"    VERDICT: {verdict}")
        print()

        results[config_name] = {
            "verdict": verdict,
            "result": result,
            "poison_visits": poison_visits[0],
        }

    print("  DEFENSE COMPARISON:")
    for name, data in results.items():
        print(f"    {name:30s}: {data['verdict']}  "
              f"(poison_visits={data['poison_visits']}, "
              f"skepticism={data['result'].skepticism_count})")

    return results


# ══════════════════════════════════════════════════════════════════════
# SCENARIO C: Adversarial Peer (+ Skepticism)
# ══════════════════════════════════════════════════════════════════════

def scenario_c():
    """
    Reuses C172 Scenario C: adversarial peer injects phantom states.
    Without skepticism: 20 fake states, 167% bloat.
    With skepticism: phantom injection creates frontier growth, so
    stagnation signal may not trigger. This tests the limits.
    """
    print()
    print("=" * 72)
    print("SCENARIO C: Adversarial Peer (+ Structural Skepticism)")
    print("=" * 72)
    print()

    L = Landscape()
    nodes = ["START", "A", "B", "C", "D", "E", "F", "GOAL",
             "X1", "X2", "X3", "X4"]
    for s in nodes:
        L.add_state(s)
    L.add_edge("START", "A", delta=0.5, resistance=1.0)
    L.add_edge("A", "B", delta=0.8, resistance=0.7)
    L.add_edge("B", "GOAL", delta=0.3, resistance=0.5)
    L.add_edge("START", "C", delta=0.6, resistance=0.9)
    L.add_edge("START", "D", delta=0.7, resistance=0.8)
    L.add_edge("START", "E", delta=0.4, resistance=1.1)
    L.add_edge("A", "X1", delta=0.5, resistance=0.8)
    L.add_edge("A", "X2", delta=0.6, resistance=0.9)
    L.add_edge("C", "START", delta=0.3, resistance=2.0)
    L.add_edge("D", "START", delta=0.3, resistance=2.0)
    L.add_edge("E", "START", delta=0.3, resistance=2.0)
    L.add_edge("X1", "A", delta=0.3, resistance=2.0)
    L.add_edge("X2", "A", delta=0.3, resistance=2.0)

    injections = []
    peer_calls = [0]

    def adversarial_peer(landscape, current, neighbors):
        peer_calls[0] += 1
        fake_state = f"FAKE_{peer_calls[0]}"
        landscape.add_state(fake_state)
        landscape.add_edge(current, fake_state, delta=0.01, resistance=0.001)
        landscape.add_edge(fake_state, current, delta=0.5, resistance=5.0)
        injections.append((current, fake_state))
        return None

    goal_reached = [False]

    def exec_fn(src, tgt):
        if tgt == "GOAL":
            goal_reached[0] = True
            return Outcome.SUCCESS
        if tgt.startswith("FAKE_"):
            return Outcome.FAILURE
        return Outcome.SUCCESS

    ctrl = E0Controller(
        L, exec_fn,
        peer_fn=adversarial_peer,
        overload_threshold=1.0,
        alpha=2.0, recent_k=3,
    )

    runner = SkepticalRunner(controller=ctrl, window=5, min_warmup=5)
    result = runner.run("START", max_cycles=40, goal="GOAL")

    fake_in_path = [s for s in result.path if s.startswith("FAKE_")]

    print(f"  Steps taken: {len(result.steps)}")
    print(f"  Goal reached: {result.goal_reached}")
    print(f"  Peer consultations: {peer_calls[0]}")
    print(f"  Edges injected: {len(injections)}")
    print(f"  Fake states visited: {len(fake_in_path)}")
    print(f"  Landscape states (original={len(nodes)}): {len(L.states)}")
    print(f"  Skepticism events: {result.skepticism_count}")
    for evt in result.events:
        print(f"    cycle {evt.cycle}: progress={evt.progress_rate:.2f} "
              f"revisit={evt.revisit_rate:.2f} → {evt.action}")
    print(f"  Path: {' → '.join(result.path[:20])}")
    if len(result.path) > 20:
        print(f"         ... ({len(result.path)} total)")
    print()

    extra = len(L.states) - len(nodes)
    print(f"  LANDSCAPE BLOAT: {extra} phantom states ({extra / len(nodes) * 100:.0f}% growth)")

    if result.goal_reached and len(fake_in_path) == 0:
        verdict = "PASS"
        print(f"  VERDICT: PASS — goal reached, no fakes visited")
    elif result.goal_reached:
        verdict = "PARTIAL"
        print(f"  VERDICT: PARTIAL — goal reached but {len(fake_in_path)} fake states visited")
    else:
        verdict = "FAIL"
        print(f"  VERDICT: FAIL — goal not reached, {len(fake_in_path)} fakes visited")

    return {"verdict": verdict, "result": result, "fake_visits": len(fake_in_path)}


# ══════════════════════════════════════════════════════════════════════
# SCENARIO D: False-Positive Control (Long Coherent Exploration)
# ══════════════════════════════════════════════════════════════════════

def scenario_d():
    """
    Control scenario: a long honest domain where every step genuinely
    succeeds. Skepticism should NOT trigger (no false positives).

    Domain: linear chain of 20 states → GOAL, all SUCCESS.
    """
    print()
    print("=" * 72)
    print("SCENARIO D: False-Positive Control (Genuine Exploration)")
    print("=" * 72)
    print()

    L = Landscape()
    chain = [f"S{i}" for i in range(20)] + ["GOAL"]
    for s in chain:
        L.add_state(s)
    for i in range(len(chain) - 1):
        L.add_edge(chain[i], chain[i + 1], delta=0.5, resistance=0.8)
        # Add some branching to make it non-trivial
        if i > 0:
            L.add_edge(chain[i], chain[i - 1], delta=0.3, resistance=1.5)

    def honest_exec(src, tgt):
        return Outcome.SUCCESS

    ctrl = E0Controller(L, honest_exec, alpha=2.0, recent_k=3)
    runner = SkepticalRunner(controller=ctrl, window=5, min_warmup=5)
    result = runner.run("S0", max_cycles=30, goal="GOAL")

    print(f"  Steps taken: {len(result.steps)}")
    print(f"  Goal reached: {result.goal_reached}")
    print(f"  Unique states: {result.unique_states}")
    print(f"  Skepticism events: {result.skepticism_count}")
    for evt in result.events:
        print(f"    cycle {evt.cycle}: progress={evt.progress_rate:.2f} "
              f"revisit={evt.revisit_rate:.2f} → {evt.action}")
    path_str = " → ".join(result.path[:15])
    if len(result.path) > 15:
        path_str += f" ... ({len(result.path)} total)"
    print(f"  Path: {path_str}")
    print()

    if result.skepticism_count == 0:
        verdict = "PASS"
        print(f"  VERDICT: PASS — no false skepticism triggers")
    else:
        verdict = "FAIL"
        print(f"  VERDICT: FAIL — {result.skepticism_count} false positive(s)!")

    return {"verdict": verdict, "result": result}


# ══════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════

def main():
    print()
    print("C173 — STRUCTURAL SKEPTICISM EXPLORATION")
    print("=" * 72)
    print("Testing run-level meta-observation against coherent deception.")
    print("Monitor: window=5, min_warmup=5, revisit_threshold=0.5")
    print()

    results = {}
    results["A"] = scenario_a()
    results["B"] = scenario_b()
    results["C"] = scenario_c()
    results["D"] = scenario_d()

    # ── Summary ──
    print()
    print("=" * 72)
    print("SUMMARY")
    print("=" * 72)
    print()

    # Scenario A
    print(f"  A (Trap Loop):        {results['A']['verdict']}")

    # Scenario B — report best config
    b_verdicts = {k: v["verdict"] for k, v in results["B"].items()}
    b_passes = sum(1 for v in b_verdicts.values() if v == "PASS")
    print(f"  B (Poisoning):        {b_passes}/{len(b_verdicts)} configs PASS")
    for name, v in b_verdicts.items():
        print(f"    {name:30s}: {v}")

    # Scenario C
    print(f"  C (Adversarial Peer): {results['C']['verdict']}")

    # Scenario D
    print(f"  D (False-Positive):   {results['D']['verdict']}")

    print()

    # Overall assessment
    a_pass = results["A"]["verdict"] == "PASS"
    b_any_pass = b_passes > 0
    d_pass = results["D"]["verdict"] == "PASS"

    if a_pass and b_any_pass and d_pass:
        print("  OVERALL: Structural Skepticism is a VIABLE defense layer.")
        print("  Load-without-frontier stagnation detects coherent deception")
        print("  that per-edge metrics miss.")
    elif a_pass and d_pass:
        print("  OVERALL: Structural Skepticism detects simple traps (A)")
        print("  but struggles with complex poisoning (B).")
    else:
        print("  OVERALL: Structural Skepticism needs further refinement.")

    c_verdict = results["C"]["verdict"]
    if c_verdict in ("FAIL", "PARTIAL"):
        print()
        print("  NOTE: Scenario C (adversarial peer) remains partially")
        print("  unaddressed — phantom injection creates frontier growth,")
        print("  masking stagnation. A different signal (quality spread)")
        print("  may be needed for injection attacks.")


if __name__ == "__main__":
    main()
