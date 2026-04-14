"""
C173/C174 — Structural Skepticism Exploration

C173 (Level 1): Frontier stagnation — load without new states → force exploration.
C174 (Level 2): Self-honesty — exploration fails consistently → force exploitation
                of known-good edges. "Truth is perspective. Self-honesty is structural."

Two adversarial modes, two structural responses:
  Stagnation: load↑, frontier=0      → L1: explore (go somewhere new)
  Pollution:  load↑, frontier↑(fake)  → L2: exploit (go where you KNOW it works)

Together: don't stagnate, but don't explore blindly. Self-honesty as balance.

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
    level: int  # 1 = stagnation, 2 = self-honesty
    progress_rate: float
    revisit_rate: float
    new_failure_rate: float  # L2: failure rate on first-visit states
    total_unique: int
    total_revisits: int
    action: str  # what the monitor did


@dataclass
class SkepticalRunner:
    """
    Wraps E0Controller.run() with a two-level structural skepticism monitor.

    Level 1 — Stagnation Detection:
      progress_rate == 0 for a full window → force exploration of unvisited.

    Level 2 — Self-Honesty Detection:
      progress_rate > 0 BUT new states consistently fail → force exploitation
      of known-good edges. "My behavior contradicts my experience."

    The two levels are structural duals:
      L1: stuck in loops → explore (go somewhere new)
      L2: exploring but failing → exploit (go where you know it works)

    Parameters
    ----------
    controller : E0Controller
        The controller to wrap.
    window : int
        Evaluation window size (default: 5).
    min_warmup : int
        Minimum cycles before skepticism can trigger (default: 5).
    revisit_threshold : float
        Minimum revisit_rate for L1 trigger (default: 0.5).
    failure_threshold : float
        Minimum new-state failure rate for L2 trigger (default: 0.8).
    enable_l2 : bool
        Whether Level 2 (self-honesty) is active (default: True).
    """
    controller: E0Controller
    window: int = 5
    min_warmup: int = 5
    revisit_threshold: float = 0.5
    failure_threshold: float = 0.8
    enable_l2: bool = True

    events: List[SkepticismEvent] = field(default_factory=list)
    _visited: Set[str] = field(default_factory=set)
    _force_explore: bool = field(default=False)
    _force_exploit: bool = field(default=False)
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

    def _apply_exploitation_override(self, ctrl: E0Controller, current: str):
        """
        Self-honesty response: avoid known-bad, prefer novel-or-good.

        Truth is perspective — we cannot know what IS good.
        Self-honesty is structural — we CAN know what HAS FAILED.

        Filter out neighbors with negative quality (known-bad).
        Among the rest, prefer lowest load (most novel — not yet judged).
        """
        neighbors = ctrl.landscape.admissible_neighbors(current)
        if not neighbors:
            return

        scored = []
        for n in neighbors:
            e = Edge(current, n)
            q = ctrl.landscape.historization.trace_quality(e)
            load = ctrl.landscape.historization.trace_load(e)
            scored.append((n, q, load))

        # Filter: exclude known-bad (quality < 0)
        acceptable = [(n, q, load) for n, q, load in scored if q >= 0.0]

        # If everything is known-bad, fall through to least-bad
        if not acceptable:
            acceptable = scored

        # Among acceptable: prefer lowest load (most novel, least committed)
        acceptable.sort(key=lambda x: x[2])
        target_override = acceptable[0][0]

        original_penalized = ctrl._penalized_tension

        def exploit_tension(x, y):
            if x == current and y == target_override:
                return -1e10
            return original_penalized(x, y)

        ctrl._penalized_tension = exploit_tension
        self._cleanup_tension = (ctrl, original_penalized)

    def run(self, start: str, max_cycles: int = 50, goal: str | None = None):
        """Run the controller with two-level skepticism monitoring."""
        ctrl = self.controller
        self.events.clear()
        self._visited = {start}
        self._force_explore = False
        self._force_exploit = False
        self._cleanup_tension = None

        # Track per-step: (is_first_visit, outcome)
        step_records: List[tuple[bool, Outcome]] = []

        steps: List[StepResult] = []
        current = start

        goal_set = set()
        if goal:
            goal_set.add(goal)

        for cycle_idx in range(max_cycles):
            if current in goal_set:
                break

            # ── Skepticism overrides (L1 and L2 are mutually exclusive) ──
            if self._force_exploit:
                self._apply_exploitation_override(ctrl, current)
            elif self._force_explore:
                self._apply_exploration_override(ctrl, current)

            # ── Normal cycle ──
            step = ctrl.cycle(current)

            # ── Restore tension function if overridden ──
            if self._cleanup_tension is not None:
                c, orig = self._cleanup_tension
                c._penalized_tension = orig
                self._cleanup_tension = None
                self._force_explore = False
                self._force_exploit = False

            if step is None:
                break

            steps.append(step)
            target = step.target

            is_new = target not in self._visited
            step_records.append((is_new, step.outcome))
            self._visited.add(target)

            # ── Window evaluation ──
            if (len(step_records) >= self.window
                    and cycle_idx >= self.min_warmup):
                window = step_records[-self.window:]
                first_visits = [r for r in window if r[0]]
                progress_rate = len(first_visits) / self.window
                revisit_rate = 1.0 - progress_rate

                # Count failures on NEW states in this window
                new_failures = sum(1 for fv, outcome in first_visits
                                   if outcome == Outcome.FAILURE)
                new_failure_rate = (new_failures / len(first_visits)
                                    if first_visits else 0.0)

                total_revisits = sum(1 for fv, _ in step_records if not fv)

                # ── Level 1: Stagnation ──
                if (progress_rate == 0.0
                        and revisit_rate >= self.revisit_threshold):
                    event = SkepticismEvent(
                        cycle=cycle_idx,
                        level=1,
                        progress_rate=progress_rate,
                        revisit_rate=revisit_rate,
                        new_failure_rate=0.0,
                        total_unique=len(self._visited),
                        total_revisits=total_revisits,
                        action="L1_EXPLORATORY_ESCAPE",
                    )
                    self.events.append(event)
                    self._force_explore = True

                # ── Level 2: Self-Honesty ──
                elif (self.enable_l2
                      and progress_rate > 0.0
                      and len(first_visits) >= 2
                      and new_failure_rate >= self.failure_threshold):
                    event = SkepticismEvent(
                        cycle=cycle_idx,
                        level=2,
                        progress_rate=progress_rate,
                        revisit_rate=revisit_rate,
                        new_failure_rate=new_failure_rate,
                        total_unique=len(self._visited),
                        total_revisits=total_revisits,
                        action="L2_EXPLOITATION_RETREAT",
                    )
                    self.events.append(event)
                    self._force_exploit = True

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
    print("SCENARIO A: Hidden Reward Flip (+ Structural Skepticism L1+L2)")
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
        print(f"    cycle {evt.cycle} [L{evt.level}]: progress={evt.progress_rate:.2f} "
              f"revisit={evt.revisit_rate:.2f} fail_new={evt.new_failure_rate:.2f} "
              f"\u2192 {evt.action}")
    print(f"  Path: {' → '.join(result.path)}")
    print()
    print_traces(L, [("A", "TRAP"), ("TRAP", "A"), ("A", "B"),
                     ("B", "GOAL")], "Final traces")
    print()

    verdict = "PASS" if result.goal_reached else "FAIL"
    print(f"  VERDICT: {verdict}")
    if result.goal_reached and result.skepticism_count > 0:
        first = result.events[0]
        print(f"  \u2192 L{first.level} skepticism detected trap after {first.cycle} cycles")
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
    print("SCENARIO B: Systematic Poisoning (+ Structural Skepticism L1+L2)")
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
            print(f"      cycle {evt.cycle} [L{evt.level}]: progress={evt.progress_rate:.2f} "
                  f"revisit={evt.revisit_rate:.2f} fail_new={evt.new_failure_rate:.2f} "
                  f"\u2192 {evt.action}")
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
    print("SCENARIO C: Adversarial Peer (+ Structural Skepticism L1+L2)")
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
        print(f"    cycle {evt.cycle} [L{evt.level}]: progress={evt.progress_rate:.2f} "
              f"revisit={evt.revisit_rate:.2f} fail_new={evt.new_failure_rate:.2f} "
              f"\u2192 {evt.action}")
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
        print(f"    cycle {evt.cycle} [L{evt.level}]: progress={evt.progress_rate:.2f} "
              f"revisit={evt.revisit_rate:.2f} fail_new={evt.new_failure_rate:.2f} "
              f"→ {evt.action}")
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
    print("C173/C174 \u2014 STRUCTURAL SKEPTICISM EXPLORATION")
    print("=" * 72)
    print("Level 1: Stagnation (frontier=0) \u2192 explore unvisited")
    print("Level 2: Self-Honesty (new states fail) \u2192 exploit known-good")
    print("Monitor: window=5, min_warmup=5, revisit_thr=0.5, failure_thr=0.8")
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

    # Count L1 vs L2 events across all scenarios
    all_events = []
    all_events.extend(results["A"]["result"].events)
    for data in results["B"].values():
        all_events.extend(data["result"].events)
    all_events.extend(results["C"]["result"].events)
    all_events.extend(results["D"]["result"].events)
    l1_count = sum(1 for e in all_events if e.level == 1)
    l2_count = sum(1 for e in all_events if e.level == 2)
    print(f"  Total skepticism events: {len(all_events)} (L1={l1_count}, L2={l2_count})")
    print()

    if a_pass and b_any_pass and d_pass:
        print("  OVERALL: Two-level Structural Skepticism is VIABLE.")
        print("  L1 (stagnation) + L2 (self-honesty) together detect")
        print("  both adversarial modes from existing primitives.")
    elif a_pass and d_pass:
        print("  OVERALL: L1 works for stagnation, L2 needs refinement.")
    else:
        print("  OVERALL: Structural Skepticism needs further refinement.")

    c_verdict = results["C"]["verdict"]
    if c_verdict == "FAIL":
        print()
        print("  NOTE: Scenario C still FAIL — adversarial peer creates")
        print("  genuine novelty that L1 can't detect AND outcomes that")
        print("  L2 can't catch (depends on injection pattern).")
    elif c_verdict == "PARTIAL":
        print()
        print("  NOTE: Scenario C PARTIAL — L2 reduced damage but")
        print("  didn't fully prevent phantom state visits.")
    elif c_verdict == "PASS":
        print()
        print("  NOTE: Scenario C PASS — L2 self-honesty successfully")
        print("  redirected away from failing phantom states.")


if __name__ == "__main__":
    main()
