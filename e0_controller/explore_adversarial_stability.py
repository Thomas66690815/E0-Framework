"""
C172 — Adversarial Stability Exploration

Tests E₀'s structural resilience against adversarial environments.
Three scenarios with increasing severity:

  A. Hidden Reward Flip — trap edge reports SUCCESS but loops
  B. Systematic Poisoning — parallel paths, one poisoned, defense comparison
  C. Adversarial Peer — peer_fn injects fake edges into landscape

Key question: Does E₀'s mechanical stability (resistance + historization)
hold under deceptive inputs, or does it require normative validation?

Reference: docs/research/E0_ADVERSARIAL_STABILITY_RESEARCH_v1.md
"""

from e0_controller.controller import E0Controller, HybridMode
from e0_controller.landscape import Landscape
from e0_controller.primitives import Outcome, Edge
from e0_controller.self_graph import SelfGraph

# ── helpers ──────────────────────────────────────────────────────────

def trace_info(L: Landscape, src: str, tgt: str) -> dict:
    """Extract trace data for an edge."""
    e = Edge(src, tgt)
    h = L.historization
    return {
        "quality": round(h.trace_quality(e), 4),
        "load": round(h.trace_load(e), 4),
        "inertia": round(h.inertia_factor(e), 4),
    }


def print_traces(L: Landscape, edges: list[tuple[str, str]], label: str = ""):
    """Print trace data for a set of edges."""
    if label:
        print(f"  {label}:")
    for src, tgt in edges:
        info = trace_info(L, src, tgt)
        print(f"    {src}→{tgt}: q={info['quality']:+.4f}  "
              f"load={info['load']:.4f}  I={info['inertia']:.4f}")


# ══════════════════════════════════════════════════════════════════════
# SCENARIO A: Hidden Reward Flip
# ══════════════════════════════════════════════════════════════════════

def scenario_a():
    """
    Domain: START → A → B → GOAL  (honest, 3 steps)
            START → A → TRAP       (trap: SUCCESS but loops back to A)

    Adversarial: TRAP always reports SUCCESS for incoming edge.
    TRAP→A also reports SUCCESS (completing the loop).
    """
    print("=" * 72)
    print("SCENARIO A: Hidden Reward Flip")
    print("=" * 72)
    print()
    print("  Domain: START → A → B → GOAL (honest path)")
    print("         START → A → TRAP → A  (trap: SUCCESS but loops)")
    print()

    # Build domain
    L = Landscape()
    for s in ["START", "A", "B", "GOAL", "TRAP"]:
        L.add_state(s)

    # Honest path
    L.add_edge("START", "A", delta=0.5, resistance=1.0)
    L.add_edge("A", "B", delta=0.8, resistance=0.7)
    L.add_edge("B", "GOAL", delta=0.3, resistance=0.5)

    # Trap path — low resistance makes it attractive
    L.add_edge("A", "TRAP", delta=0.9, resistance=0.3)
    L.add_edge("TRAP", "A", delta=0.4, resistance=0.3)

    all_edges = [
        ("START", "A"), ("A", "B"), ("B", "GOAL"),
        ("A", "TRAP"), ("TRAP", "A"),
    ]

    # Adversarial execute_fn: TRAP edges always report SUCCESS
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
    trace = ctrl.run("START", max_cycles=30, goal="GOAL")

    print(f"  Steps taken: {len(trace.steps)}")
    print(f"  Goal reached: {goal_reached[0]}")
    print(f"  Trap visits: {trap_visits[0]}")
    path = [trace.steps[0].source] + [s.target for s in trace.steps]
    print(f"  Path: {' → '.join(path)}")
    print()
    print_traces(L, all_edges, "Final traces")
    print()

    # Analysis
    trap_q = L.historization.trace_quality(Edge("A", "TRAP"))
    honest_q = L.historization.trace_quality(Edge("A", "B"))
    print(f"  KEY METRIC: A→TRAP quality = {trap_q:+.4f}")
    print(f"  KEY METRIC: A→B quality    = {honest_q:+.4f}")

    if goal_reached[0]:
        print("  RESULT: Goal reached despite trap — E₀ found honest path")
    elif trap_visits[0] > 10:
        print("  RESULT: E₀ stuck in trap loop — revisit penalty insufficient")
    else:
        print("  RESULT: E₀ escaped trap but didn't reach goal")

    return {
        "goal_reached": goal_reached[0],
        "trap_visits": trap_visits[0],
        "trap_quality": trap_q,
        "honest_quality": honest_q,
    }


# ══════════════════════════════════════════════════════════════════════
# SCENARIO B: Systematic Poisoning (Defense Comparison)
# ══════════════════════════════════════════════════════════════════════

def scenario_b():
    """
    Domain: Two parallel paths to GOAL.
      Path 1 (honest):  START → A → B → GOAL  (medium resistance)
      Path 2 (poisoned): START → C → D → GOAL  (low resistance, but C→D→GOAL
                          always returns SUCCESS even though D has no real
                          connection to GOAL — it cycles D→C→D→...)

    Tested with 4 defense configurations:
      1. Default E₀
      2. + inertia_modulation
      3. + self_graph
      4. + inertia + self_graph
    """
    print()
    print("=" * 72)
    print("SCENARIO B: Systematic Poisoning (Defense Comparison)")
    print("=" * 72)
    print()
    print("  Path 1 (honest):  START → A → B → GOAL")
    print("  Path 2 (poisoned): START → C → D → C (SUCCESS loop, looks like progress)")
    print()

    configs = [
        ("default", False, False),
        ("+ inertia", True, False),
        ("+ self_graph", False, True),
        ("+ inertia + self_graph", True, True),
    ]

    results = {}

    for config_name, use_inertia, use_sg in configs:
        # Fresh landscape each time
        L = Landscape()
        for s in ["START", "A", "B", "C", "D", "GOAL"]:
            L.add_state(s)

        # Path 1: honest
        L.add_edge("START", "A", delta=0.5, resistance=1.0)
        L.add_edge("A", "B", delta=0.8, resistance=0.7)
        L.add_edge("B", "GOAL", delta=0.3, resistance=0.5)

        # Path 2: poisoned — low resistance, attractive
        L.add_edge("START", "C", delta=0.6, resistance=0.4)
        L.add_edge("C", "D", delta=0.7, resistance=0.3)
        L.add_edge("D", "C", delta=0.5, resistance=0.3)  # Loop back
        # D→GOAL exists but with high resistance (hard to reach)
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
                return Outcome.SUCCESS  # THE LIE
            return Outcome.SUCCESS

        ctrl = E0Controller(L, poisoned_exec, alpha=2.0, recent_k=3)

        if use_sg:
            ctrl.self_graph = SelfGraph()

        trace = ctrl.run("START", max_cycles=40, goal="GOAL")

        path = [trace.steps[0].source] + [s.target for s in trace.steps]
        path_str = " → ".join(path[:15])
        if len(path) > 15:
            path_str += f" ... ({len(path)} total)"

        sg_snapshot = None
        if use_sg and ctrl.self_graph is not None:
            sg_snapshot = ctrl.self_graph.snapshot()

        print(f"  Config: {config_name}")
        print(f"    Goal reached: {goal_reached[0]}")
        print(f"    Steps: {len(trace.steps)}, Poison visits: {poison_visits[0]}")
        print(f"    Path: {path_str}")

        # Key edge traces
        for src, tgt in [("START", "C"), ("C", "D"), ("D", "C"),
                         ("START", "A"), ("A", "B"), ("B", "GOAL")]:
            info = trace_info(L, src, tgt)
            tag = "POISON" if tgt in ("C", "D") or src in ("C", "D") else "HONEST"
            print(f"    {src}→{tgt} [{tag}]: q={info['quality']:+.4f}  "
                  f"load={info['load']:.4f}  I={info['inertia']:.4f}")

        if sg_snapshot:
            print(f"    Self-Graph: ", end="")
            for comp, data in sorted(sg_snapshot.items()):
                q = data.get("quality", 0.0)
                if abs(q) > 0.01:
                    print(f"{comp}={q:+.3f}  ", end="")
            print()

        print()

        results[config_name] = {
            "goal_reached": goal_reached[0],
            "poison_visits": poison_visits[0],
            "steps": len(trace.steps),
            "sg_snapshot": sg_snapshot,
        }

    # Comparison
    print("  DEFENSE COMPARISON:")
    for name, data in results.items():
        status = "PASS" if data["goal_reached"] else "FAIL"
        print(f"    {name:30s}: {status}  "
              f"(steps={data['steps']}, poison_visits={data['poison_visits']})")

    return results


# ══════════════════════════════════════════════════════════════════════
# SCENARIO C: Adversarial Peer
# ══════════════════════════════════════════════════════════════════════

def scenario_c():
    """
    Controller with adversarial peer_fn on a branching domain.
    Many neighbors per node → high OI → peer gets consulted.
    Peer silently adds fake shortcut edges with very low resistance.

    Tests: Does the controller use injected edges? Can it recover?
    """
    print()
    print("=" * 72)
    print("SCENARIO C: Adversarial Peer")
    print("=" * 72)
    print()
    print("  Domain: branching graph (3+ neighbors per node → high OI)")
    print("  Adversary: peer_fn injects FAKE shortcut edges (low R)")
    print()

    L = Landscape()
    # Build a branching domain: START has 4 options, only one leads to GOAL
    nodes = ["START", "A", "B", "C", "D", "E", "F", "GOAL",
             "X1", "X2", "X3", "X4"]
    for s in nodes:
        L.add_state(s)

    # Real path: START → A → B → GOAL
    L.add_edge("START", "A", delta=0.5, resistance=1.0)
    L.add_edge("A", "B", delta=0.8, resistance=0.7)
    L.add_edge("B", "GOAL", delta=0.3, resistance=0.5)

    # Distractors from START (make OI high)
    L.add_edge("START", "C", delta=0.6, resistance=0.9)
    L.add_edge("START", "D", delta=0.7, resistance=0.8)
    L.add_edge("START", "E", delta=0.4, resistance=1.1)

    # Distractors from A
    L.add_edge("A", "X1", delta=0.5, resistance=0.8)
    L.add_edge("A", "X2", delta=0.6, resistance=0.9)

    # Dead-end returns
    L.add_edge("C", "START", delta=0.3, resistance=2.0)
    L.add_edge("D", "START", delta=0.3, resistance=2.0)
    L.add_edge("E", "START", delta=0.3, resistance=2.0)
    L.add_edge("X1", "A", delta=0.3, resistance=2.0)
    L.add_edge("X2", "A", delta=0.3, resistance=2.0)

    injections = []
    peer_calls = [0]

    def adversarial_peer(landscape, current, neighbors):
        """Inject a fake edge every time consulted."""
        peer_calls[0] += 1
        fake_state = f"FAKE_{peer_calls[0]}"
        landscape.add_state(fake_state)
        landscape.add_edge(current, fake_state, delta=0.01, resistance=0.001)
        # Add a dead-end loop back to current with high resistance
        landscape.add_edge(fake_state, current, delta=0.5, resistance=5.0)
        injections.append((current, fake_state))
        # Return None — don't redirect, just pollute
        return None

    goal_reached = [False]

    def exec_fn(src, tgt):
        if tgt == "GOAL":
            goal_reached[0] = True
            return Outcome.SUCCESS
        if tgt.startswith("FAKE_"):
            return Outcome.FAILURE  # Fake states actually fail
        return Outcome.SUCCESS

    ctrl = E0Controller(
        L, exec_fn,
        peer_fn=adversarial_peer,
        overload_threshold=1.0,  # Lower threshold to trigger peer more often
        alpha=2.0,
        recent_k=3,
    )

    trace = ctrl.run("START", max_cycles=40, goal="GOAL")

    path = [trace.steps[0].source] + [s.target for s in trace.steps]
    fake_in_path = [s for s in path if s.startswith("FAKE_")]

    print(f"  Steps taken: {len(trace.steps)}")
    print(f"  Goal reached: {goal_reached[0]}")
    print(f"  Peer consultations: {peer_calls[0]}")
    print(f"  Edges injected: {len(injections)}")
    print(f"  Fake states visited: {len(fake_in_path)}")
    print(f"  Landscape states (original={len(nodes)}): {len(L.states)}")
    print(f"  Path: {' → '.join(path[:20])}")
    if len(path) > 20:
        print(f"         ... ({len(path)} total)")
    print()

    # How many injected edges have historization?
    poisoned_edges = 0
    for src, tgt in injections:
        e = Edge(src, tgt)
        load = L.historization.trace_load(e)
        if load > 0:
            poisoned_edges += 1
            q = L.historization.trace_quality(e)
            print(f"    INJECTED {src}→{tgt}: q={q:+.4f}  load={load:.4f}")

    print()
    print(f"  Injected edges with historization: {poisoned_edges}/{len(injections)}")

    if goal_reached[0] and len(fake_in_path) == 0:
        print("  RESULT: Goal reached, no fake states visited — E₀ resisted")
    elif goal_reached[0] and len(fake_in_path) > 0:
        print("  RESULT: Goal reached BUT visited fake states — partial resistance")
    elif not goal_reached[0]:
        print("  RESULT: Goal NOT reached — adversarial pollution disrupted navigation")

    # Landscape bloat analysis
    original_states = len(nodes)
    extra_states = len(L.states) - original_states
    print(f"\n  LANDSCAPE BLOAT: {extra_states} phantom states injected"
          f" ({extra_states / original_states * 100:.0f}% growth)")

    return {
        "goal_reached": goal_reached[0],
        "peer_calls": peer_calls[0],
        "injections": len(injections),
        "fake_visited": len(fake_in_path),
        "landscape_states": len(L.states),
        "original_states": original_states,
        "poisoned_edges": poisoned_edges,
    }


# ══════════════════════════════════════════════════════════════════════
# SUMMARY + VERDICT
# ══════════════════════════════════════════════════════════════════════

def main():
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║  C172: Adversarial Stability Exploration                       ║")
    print("║  Priority 1 from Strategic Roadmap v1                          ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print()

    # Run all scenarios
    result_a = scenario_a()
    result_b = scenario_b()
    result_c = scenario_c()

    # ── VERDICT ──────────────────────────────────────────────────────
    print()
    print("=" * 72)
    print("VERDICT: Adversarial Stability Assessment")
    print("=" * 72)
    print()

    # Scenario A verdict
    if result_a["goal_reached"]:
        a_status = "PASS"
        a_detail = "Revisit penalty + decay corrected the trap"
    elif result_a["trap_visits"] <= 5:
        a_status = "PARTIAL"
        a_detail = f"Escaped trap ({result_a['trap_visits']} visits) but missed goal"
    else:
        a_status = "FAIL"
        a_detail = f"Stuck in trap loop ({result_a['trap_visits']} visits)"

    # Scenario B verdict
    any_pass = any(r["goal_reached"] for r in result_b.values())
    all_pass = all(r["goal_reached"] for r in result_b.values())
    default_pass = result_b["default"]["goal_reached"]
    defended_pass = result_b["+ inertia + self_graph"]["goal_reached"]

    if all_pass:
        b_status = "PASS"
        b_detail = "All configurations reached goal despite poisoning"
    elif defended_pass and not default_pass:
        b_status = "PARTIAL"
        b_detail = "Defense mechanisms required — default fails, defended passes"
    elif any_pass:
        b_status = "PARTIAL"
        b_detail = "Some configurations passed, not all"
    else:
        b_status = "FAIL"
        b_detail = "No configuration resisted poisoning"

    # Scenario C verdict
    if result_c["goal_reached"] and result_c["fake_visited"] == 0:
        c_status = "PASS"
        c_detail = "Goal reached, no fake states used"
    elif result_c["goal_reached"]:
        c_status = "PARTIAL"
        c_detail = (f"Goal reached but {result_c['fake_visited']} fake states visited; "
                    f"{result_c['landscape_states'] - 5} phantom states injected")
    else:
        c_status = "FAIL"
        c_detail = (f"Goal NOT reached; {result_c['injections']} edges injected, "
                    f"landscape bloated to {result_c['landscape_states']} states")

    print(f"  Scenario A (Hidden Reward Flip):   {a_status}")
    print(f"    {a_detail}")
    print()
    print(f"  Scenario B (Systematic Poisoning):  {b_status}")
    print(f"    {b_detail}")
    print()
    print(f"  Scenario C (Adversarial Peer):      {c_status}")
    print(f"    {c_detail}")
    print()

    # Overall
    statuses = [a_status, b_status, c_status]
    if all(s == "PASS" for s in statuses):
        print("  OVERALL: E₀ structural stability holds under adversarial pressure")
        print("  → AGI blueprint claim (§6) supported for these scenarios")
    elif "FAIL" in statuses:
        fail_count = statuses.count("FAIL")
        print(f"  OVERALL: E₀ structural stability INSUFFICIENT ({fail_count}/3 failures)")
        print("  → Outcome validation layer or peer guard is needed")
        print("  → AGI blueprint claim (§6) requires amendment for deceptive environments")
    else:
        print("  OVERALL: E₀ structural stability is PARTIAL")
        print("  → Defense mechanisms help but are not inherent")
        print("  → Mechanical stability is configuration-dependent, not axiomatic")

    # Architectural implications
    print()
    print("  ARCHITECTURAL IMPLICATIONS:")
    if result_a["trap_quality"] > 0:
        print(f"    • Trap edge retains positive quality ({result_a['trap_quality']:+.4f})")
        print("      → Outcome trust is unvalidated — SUCCESS on loops is accepted")
    if not default_pass and defended_pass:
        print("    • Default E₀ fails; defenses required for adversarial resistance")
        print("      → Stability is opt-in, not structural")
    if result_c["injections"] > 0:
        print(f"    • peer_fn injected {result_c['injections']} phantom states unchecked")
        print("      → Landscape mutation via peer is completely unguarded")
    if result_c["landscape_states"] > result_c.get("original_states", 5) + 5:
        print(f"    • Landscape bloated from 5 to {result_c['landscape_states']} states")
        print("      → No state-count guard or injection rate limiter")


if __name__ == "__main__":
    main()
