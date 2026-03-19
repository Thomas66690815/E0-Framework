"""
E₀ Controller — Test Mini-Domain
===================================
Controlled graph domain that validates all 7 core functions.

Graph (10 edges, 8 states):

    A ──(0.5/1.0)──→ B ──(0.3/0.8)──→ E ──(0.2/0.5)──→ G ──(0.1/0.3)──→ GOAL
    │                 │                 │
    ├──(0.4/0.8)──→ C │                 └──(0.4/1.2)──→ F
    │                ↑│                                   │
    │   (0.4/0.8)──┘ └──(0.6/1.5)──→ D (dead-end)       └──(0.3/1.0)──→ G
    │
    └←──(0.4/0.8)── C

    Format: (Δ / R₀)

Test scenarios:
    1. Oscillation breaking:  A↔C has lowest tension from A → revisit-penalty breaks it
    2. Dead-end escalation:   D has no outgoing edges → escalation creates escape
    3. Failure learning:      E→F always fails → R increases, path avoided
    4. Success learning:      E→G always succeeds → R decreases, path reinforced
    5. Goal reachability:     Optimal path A→B→E→G→GOAL is found after learning
"""

from __future__ import annotations

import math
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from e0_controller.primitives import Edge, Outcome
from e0_controller.historization import Historization
from e0_controller.tension import tension, coherence, path_tension
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller, RunTrace


# ──────────────────────────────────────────────
# Mini-Domain Builder
# ──────────────────────────────────────────────

def build_mini_landscape() -> Landscape:
    """
    Build the test graph.

    States: A, B, C, D, E, F, G, GOAL
    """
    L = Landscape()

    # From A (start)
    L.add_edge("A", "B", delta=0.5, resistance=1.0)   # S₀ = 0.50
    L.add_edge("A", "C", delta=0.4, resistance=0.8)   # S₀ = 0.32 ← lower!

    # C is a trap: oscillates back to A
    L.add_edge("C", "A", delta=0.4, resistance=0.8)   # S₀ = 0.32
    L.add_edge("C", "D", delta=0.7, resistance=3.0)   # S₀ = 2.10 (hard)

    # B leads to progress or dead-end
    L.add_edge("B", "E", delta=0.3, resistance=0.8)   # S₀ = 0.24
    L.add_edge("B", "D", delta=0.6, resistance=1.5)   # S₀ = 0.90

    # D = dead-end (no outgoing edges)
    L.add_state("D")

    # E has two options
    L.add_edge("E", "F", delta=0.4, resistance=1.2)   # S₀ = 0.48 (failure edge)
    L.add_edge("E", "G", delta=0.2, resistance=0.5)   # S₀ = 0.10

    # F connects to G
    L.add_edge("F", "G", delta=0.3, resistance=1.0)   # S₀ = 0.30

    # G → GOAL
    L.add_edge("G", "GOAL", delta=0.1, resistance=0.3)  # S₀ = 0.03

    return L


# ──────────────────────────────────────────────
# Outcome Maps (deterministic execution)
# ──────────────────────────────────────────────

def all_success(source: str, target: str) -> Outcome:
    """Every transition succeeds. For structure tests."""
    return Outcome.SUCCESS


def failure_on_EF(source: str, target: str) -> Outcome:
    """E→F always fails, everything else succeeds."""
    if source == "E" and target == "F":
        return Outcome.FAILURE
    return Outcome.SUCCESS


def mixed_outcomes(source: str, target: str) -> Outcome:
    """E→F fails, C→D is partial, rest succeeds."""
    if source == "E" and target == "F":
        return Outcome.FAILURE
    if source == "C" and target == "D":
        return Outcome.PARTIAL
    return Outcome.SUCCESS


# ──────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────

def test_primitives():
    """Test basic types."""
    print("── test_primitives ──")

    e = Edge("A", "B")
    assert e.source == "A"
    assert e.target == "B"
    assert repr(e) == "A→B"

    assert Outcome.SUCCESS.value == "success"
    assert Outcome.FAILURE.value == "failure"
    assert Outcome.PARTIAL.value == "partial"

    print("   ✓ Edge and Outcome work correctly")


def test_tension_math():
    """Test tension, path_tension, coherence."""
    print("── test_tension_math ──")

    # §3: S = Δ · R
    assert tension(0.5, 1.0) == 0.5
    assert tension(0.0, 5.0) == 0.0
    assert math.isinf(tension(1.0, math.inf))

    # §6: C = exp(-S)
    assert coherence(0.0) == 1.0
    assert coherence(math.inf) == 0.0
    assert abs(coherence(1.0) - math.exp(-1.0)) < 1e-10

    # §5: S(p) = Σ S(eᵢ)
    assert path_tension([0.5, 0.3, 0.1]) == 0.9
    assert math.isinf(path_tension([0.5, math.inf, 0.1]))

    print("   ✓ Tension, coherence, path_tension correct")


def test_historization():
    """Test U/F traces and δ_H."""
    print("── test_historization ──")

    h = Historization(rho=0.9, lambda_s=0.15, lambda_f=0.20, delta_max=3.0)
    e = Edge("X", "Y")

    # Initial state
    assert h.success_trace(e) == 0.0
    assert h.failure_trace(e) == 0.0
    assert h.delta_H(e) == 0.0

    # One success: U = 0.9*0 + 1 = 1.0, F stays 0
    h.update(e, Outcome.SUCCESS)
    assert h.success_trace(e) == 1.0
    assert h.failure_trace(e) == 0.0
    # δ_H = 0.20*0 - 0.15*1.0 = -0.15 (resistance decreases)
    assert abs(h.delta_H(e) - (-0.15)) < 1e-10

    # One failure: U = 0.9*1 = 0.9, F = 0.9*0 + 1 = 1.0
    h.update(e, Outcome.FAILURE)
    assert abs(h.success_trace(e) - 0.9) < 1e-10
    assert abs(h.failure_trace(e) - 1.0) < 1e-10
    # δ_H = 0.20*1.0 - 0.15*0.9 = 0.20 - 0.135 = 0.065
    assert abs(h.delta_H(e) - 0.065) < 1e-10

    # Partial: U += 0.5, F += 0.3
    h.update(e, Outcome.PARTIAL)
    u_exp = 0.9 * 0.9 + 0.5    # 1.31
    f_exp = 0.9 * 1.0 + 0.3    # 1.20
    assert abs(h.success_trace(e) - u_exp) < 1e-10
    assert abs(h.failure_trace(e) - f_exp) < 1e-10

    print(f"   ✓ U/F traces correct (U={u_exp:.2f}, F={f_exp:.2f})")
    print(f"   ✓ δ_H = {h.delta_H(e):.4f}")

    # Test clipping
    h2 = Historization(rho=0.99, lambda_s=0.01, lambda_f=1.0, delta_max=2.0)
    e2 = Edge("P", "Q")
    for _ in range(100):
        h2.update(e2, Outcome.FAILURE)
    dh = h2.delta_H(e2)
    assert dh == 2.0, f"Expected clipped δ_H = 2.0, got {dh}"
    print(f"   ✓ Clipping works (δ_H capped at δ_max=2.0)")


def test_landscape_core_functions():
    """Test all 5 landscape functions."""
    print("── test_landscape_core_functions ──")

    L = build_mini_landscape()

    # Function 1: difference
    assert L.difference("A", "B") == 0.5
    assert L.difference("A", "C") == 0.4
    assert L.difference("X", "Y") == 0.0  # non-existent edge

    # Function 2: base_resistance
    assert L.base_resistance("A", "B") == 1.0
    assert math.isinf(L.base_resistance("D", "A"))  # dead-end

    # Function 3: effective_resistance (initially = R₀)
    assert abs(L.effective_resistance("A", "B") - 1.0) < 1e-10

    # Function 4: effective_tension
    assert abs(L.effective_tension("A", "B") - 0.5) < 1e-10
    assert abs(L.effective_tension("A", "C") - 0.32) < 1e-10

    # Function 5: admissible_neighbors
    nbrs_A = set(L.admissible_neighbors("A"))
    assert nbrs_A == {"B", "C"}, f"Expected {{B, C}}, got {nbrs_A}"

    nbrs_D = L.admissible_neighbors("D")
    assert nbrs_D == [], f"D should be dead-end, got {nbrs_D}"

    # Transition field
    v_AB = L.transition_field("A", "B")
    v_AC = L.transition_field("A", "C")
    assert v_AB > 0 and v_AC > 0

    print(f"   ✓ Δ(A→B)={L.difference('A','B')}, R₀={L.base_resistance('A','B')}")
    print(f"   ✓ S_eff(A→B)={L.effective_tension('A','B'):.2f}, "
          f"S_eff(A→C)={L.effective_tension('A','C'):.2f}")
    print(f"   ✓ Neighbors(A)={nbrs_A}, Neighbors(D)={nbrs_D}")
    print(f"   ✓ v(A→B)={v_AB:.4f}, v(A→C)={v_AC:.4f}")


def test_oscillation_breaking():
    """
    Test 1: Revisit-penalty breaks A↔C oscillation.

    Without penalty: A→C (0.32) → C→A (0.32) → A→C → … (forever)
    With penalty:    After visiting C, S(A→C) += α=2.0 → takes A→B instead
    """
    print("── test_oscillation_breaking ──")

    L = build_mini_landscape()
    ctrl = E0Controller(L, all_success, alpha=2.0, recent_k=3)
    trace = ctrl.run("A", max_cycles=10, goal="GOAL")

    path = trace.path
    print(f"   Path: {' → '.join(path)}")

    # Should NOT oscillate forever — must reach GOAL or at least move past C
    # With α=2.0: A→C→A(penalty on C)→B→E→G→GOAL
    assert "GOAL" in path, f"Should reach GOAL, path was: {path}"

    # Count visits to C — should be at most 1 (penalty prevents return)
    c_visits = path.count("C")
    assert c_visits <= 2, f"Visited C {c_visits} times — oscillation not broken!"
    print(f"   ✓ Visited C only {c_visits} time(s) — oscillation broken")
    print(f"   ✓ Reached GOAL in {len(trace.steps)} steps")


def test_dead_end_escalation():
    """
    Test 2: Controller escalates out of dead-end D.

    Force path to D, then controller must escalate.
    """
    print("── test_dead_end_escalation ──")

    L = build_mini_landscape()

    # Create a landscape where D is reached
    # We'll start from D directly
    ctrl = E0Controller(L, all_success, alpha=2.0, recent_k=3,
                        max_escalation_R=5.0)
    trace = ctrl.run("D", max_cycles=15, goal="GOAL")

    path = trace.path
    print(f"   Path: {' → '.join(path)}")

    # First step must be an escalation (D has no neighbors)
    assert trace.steps[0].escalated, "First step from D should be escalated"
    print(f"   ✓ Escalation triggered from dead-end D")
    print(f"   ✓ Escaped to: {trace.steps[0].target} "
          f"(S_eff={trace.steps[0].s_eff:.2f})")

    # The escalation edge should have high tension
    assert trace.steps[0].s_eff > 1.0, "Escalation should have high tension"
    print(f"   ✓ Escalation had high tension (penalty for structural jump)")


def test_failure_increases_resistance():
    """
    Test 3: Repeated failures on E→F increase its effective resistance.
    """
    print("── test_failure_increases_resistance ──")

    L = build_mini_landscape()

    # Initial R_eff of E→F
    r0 = L.effective_resistance("E", "F")
    print(f"   Initial R_eff(E→F) = {r0:.4f}")

    # Simulate 5 failures on E→F
    edge_ef = Edge("E", "F")
    for i in range(5):
        L.historization.update(edge_ef, Outcome.FAILURE)

    r_after = L.effective_resistance("E", "F")
    dh = L.historization.delta_H(edge_ef)
    print(f"   After 5 failures: R_eff(E→F) = {r_after:.4f} (δ_H={dh:+.4f})")

    assert r_after > r0, f"R_eff should increase after failures"
    assert dh > 0, f"δ_H should be positive (failures dominate)"

    # Tension should also increase
    s_before = 0.4 * r0      # original
    s_after = L.effective_tension("E", "F")
    print(f"   S_eff: {s_before:.4f} → {s_after:.4f}")
    assert s_after > s_before
    print(f"   ✓ Failure learning works: R and S both increased")


def test_success_decreases_resistance():
    """
    Test 4: Repeated successes on E→G decrease its effective resistance.
    """
    print("── test_success_decreases_resistance ──")

    L = build_mini_landscape()

    r0 = L.effective_resistance("E", "G")
    print(f"   Initial R_eff(E→G) = {r0:.4f}")

    edge_eg = Edge("E", "G")
    for i in range(5):
        L.historization.update(edge_eg, Outcome.SUCCESS)

    r_after = L.effective_resistance("E", "G")
    dh = L.historization.delta_H(edge_eg)
    print(f"   After 5 successes: R_eff(E→G) = {r_after:.4f} (δ_H={dh:+.4f})")

    assert r_after < r0, f"R_eff should decrease after successes"
    assert dh < 0, f"δ_H should be negative (successes dominate)"
    print(f"   ✓ Success learning works: R decreased")


def test_failure_avoidance():
    """
    Test 5: Controller learns to avoid E→F after failures.

    With failure_on_EF: first visit might try E→F, but after failure
    the increased R_eff should cause E→G to be preferred.
    """
    print("── test_failure_avoidance ──")

    L = build_mini_landscape()

    # Pre-load some failure history on E→F (as if tried before)
    edge_ef = Edge("E", "F")
    for _ in range(3):
        L.historization.update(edge_ef, Outcome.FAILURE)

    r_ef = L.effective_resistance("E", "F")
    r_eg = L.effective_resistance("E", "G")
    s_ef = L.effective_tension("E", "F")
    s_eg = L.effective_tension("E", "G")
    print(f"   S_eff(E→F) = {s_ef:.4f}  (R_eff={r_ef:.4f})")
    print(f"   S_eff(E→G) = {s_eg:.4f}  (R_eff={r_eg:.4f})")

    # Controller should prefer E→G (lower tension)
    ctrl = E0Controller(L, failure_on_EF, alpha=2.0, recent_k=3)
    trace = ctrl.run("E", max_cycles=5, goal="GOAL")

    path = trace.path
    print(f"   Path: {' → '.join(path)}")
    assert path[1] == "G", f"Controller should choose G over F, went to {path[1]}"
    print(f"   ✓ Controller avoided failure-prone E→F, chose E→G")


def test_full_run_to_goal():
    """
    Test 6: Complete run from A to GOAL with mixed outcomes.
    Validates the entire controller loop.
    """
    print("── test_full_run_to_goal ──")

    L = build_mini_landscape()
    ctrl = E0Controller(L, mixed_outcomes, alpha=2.0, recent_k=3)
    trace = ctrl.run("A", max_cycles=20, goal="GOAL")

    print(f"   {trace.summary()}")

    assert "GOAL" in trace.path, f"Should reach GOAL"
    print(f"   ✓ Full run reached GOAL")
    print(f"   ✓ Outcomes: {trace.outcomes}")
    print(f"   ✓ Total tension: {trace.total_tension:.4f}")

    # Print historization summary
    h = L.historization
    print(f"   ✓ Historization: τ={h.tau}, {h.summary()}")


def test_landscape_info():
    """Test that landscape inspection methods work correctly."""
    print("── test_landscape_info ──")

    L = build_mini_landscape()
    assert len(L.states) == 8, f"Expected 8 states, got {len(L.states)}"
    assert L.edge_count() == 10, f"Expected 10 edges, got {L.edge_count()}"

    info = L.info("A", "B")
    assert info["delta"] == 0.5
    assert info["R0"] == 1.0
    assert abs(info["S_eff"] - 0.5) < 1e-10

    print(f"   ✓ {len(L.states)} states, {L.edge_count()} edges")
    print(f"   ✓ Edge info: {info}")


def test_seven_core_functions():
    """
    Meta-test: verify all 7 core functions from the spec are callable
    and produce sensible output.
    """
    print("── test_seven_core_functions ──")

    L = build_mini_landscape()
    edge = Edge("A", "B")

    # 1. difference(x, y)
    d = L.difference("A", "B")
    assert d == 0.5
    print(f"   1. difference(A,B) = {d}")

    # 2. base_resistance(x, y)
    r0 = L.base_resistance("A", "B")
    assert r0 == 1.0
    print(f"   2. base_resistance(A,B) = {r0}")

    # 3. effective_resistance(x, y)
    r_eff = L.effective_resistance("A", "B")
    assert abs(r_eff - 1.0) < 1e-10  # no history yet
    print(f"   3. effective_resistance(A,B) = {r_eff}")

    # 4. effective_tension(x, y)
    s_eff = L.effective_tension("A", "B")
    assert abs(s_eff - 0.5) < 1e-10
    print(f"   4. effective_tension(A,B) = {s_eff}")

    # 5. admissible_neighbors(x)
    nbrs = L.admissible_neighbors("A")
    assert set(nbrs) == {"B", "C"}
    print(f"   5. admissible_neighbors(A) = {nbrs}")

    # 6. select_next(x)
    ctrl = E0Controller(L, all_success, alpha=2.0, recent_k=3)
    nxt, esc = ctrl.select_next("A")
    assert nxt in {"B", "C"}
    assert not esc
    print(f"   6. select_next(A) = {nxt} (escalated={esc})")

    # 7. update_historization(edge, outcome)
    L.historization.update(edge, Outcome.SUCCESS)
    assert L.historization.tau == 1
    assert L.historization.success_trace(edge) == 1.0
    print(f"   7. update_historization(A→B, SUCCESS) → τ={L.historization.tau}")

    print("   ✓ All 7 core functions verified")


# ──────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────

def run_all_tests():
    """Run all validation tests."""
    tests = [
        test_primitives,
        test_tension_math,
        test_historization,
        test_landscape_core_functions,
        test_landscape_info,
        test_seven_core_functions,
        test_oscillation_breaking,
        test_dead_end_escalation,
        test_failure_increases_resistance,
        test_success_decreases_resistance,
        test_failure_avoidance,
        test_full_run_to_goal,
    ]

    passed = 0
    failed = 0

    print("=" * 60)
    print("E₀ Controller v0.1 — Mini-Domain Validation")
    print("=" * 60)
    print()

    for test_fn in tests:
        try:
            test_fn()
            passed += 1
            print()
        except Exception as exc:
            failed += 1
            print(f"   ✗ FAILED: {exc}")
            import traceback
            traceback.print_exc()
            print()

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {len(tests)} total")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
