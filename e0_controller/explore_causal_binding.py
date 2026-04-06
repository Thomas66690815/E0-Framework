"""
C175 — Causal Binding Exploration

Can E₀ distinguish causal structure from mere correlation using existing
primitives — without explicit causal annotation?

Test: Twin domains with identical topology, different causal backing.
  - CAUSAL domain: B→GOAL works regardless of predecessor
  - CONFOUNDED domain: B→GOAL works only if preceded by A→B
  - FRAGILE domain: A→B degrades after 3 uses

Two-phase protocol:
  Phase 1 (observation): Navigate START→GOAL normally. Traces should be identical.
  Phase 2 (intervention): Navigate B→GOAL directly. Traces should diverge.

The intervention test is E₀'s analog of Pearl's do-calculus:
  P(GOAL | observe A→B) is the same for both domains.
  P(GOAL | do(start at B)) reveals the confound.

Reference: docs/research/E0_CAUSAL_BINDING_RESEARCH_v1.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from e0_controller.controller import E0Controller, HybridMode
from e0_controller.dream_mode import (
    EdgeFingerprint,
    Equivalence,
    domain_fingerprints,
    find_equivalences,
    fingerprint_distance,
)
from e0_controller.landscape import Landscape
from e0_controller.primitives import Edge, Outcome


# ── Domain Builders ──────────────────────────────────────────────────

def build_diamond_landscape() -> Landscape:
    """
    Shared topology for all scenarios:

        A → B → GOAL
       /         ↑
    START        |
       \\        |
        C ------+

    5 states, 5 edges. Identical structural parameters.
    """
    L = Landscape()
    for s in ["START", "A", "B", "C", "GOAL"]:
        L.add_state(s)
    L.add_edge("START", "A", delta=1.0, resistance=0.3)
    L.add_edge("START", "C", delta=1.0, resistance=0.3)
    L.add_edge("A", "B", delta=1.0, resistance=0.3)
    L.add_edge("C", "B", delta=1.0, resistance=0.3)
    L.add_edge("B", "GOAL", delta=1.0, resistance=0.3)
    return L


def make_causal_execute() -> Callable:
    """All transitions always succeed. B→GOAL is intrinsically capable."""
    def execute(src, tgt):
        return Outcome.SUCCESS
    return execute


def make_confounded_execute() -> Tuple[Callable, List[str]]:
    """
    B→GOAL succeeds ONLY if the last transition was A→B.
    This models a hidden confound: A "activates" the path.
    """
    history: List[str] = []

    def execute(src, tgt):
        history.append(f"{src}→{tgt}")
        if src == "B" and tgt == "GOAL":
            # Check: was last step A→B?
            if len(history) >= 2 and history[-2] == "A→B":
                return Outcome.SUCCESS
            return Outcome.FAILURE
        return Outcome.SUCCESS

    return execute, history


def make_fragile_execute() -> Tuple[Callable, Dict]:
    """
    A→B succeeds first 3 times, then fails (correlation wears off).
    All other transitions always succeed.
    """
    stats: Dict[str, int] = {"a_b_count": 0}

    def execute(src, tgt):
        if src == "A" and tgt == "B":
            stats["a_b_count"] += 1
            if stats["a_b_count"] > 3:
                return Outcome.FAILURE
            return Outcome.SUCCESS
        return Outcome.SUCCESS

    return execute, stats


# ── Helpers ──────────────────────────────────────────────────────────

def trace_info(L: Landscape, src: str, tgt: str) -> dict:
    e = Edge(src, tgt)
    h = L.historization
    return {
        "quality": round(h.trace_quality(e), 4),
        "load": round(h.trace_load(e), 4),
        "inertia": round(h.inertia_factor(e), 4),
    }


def print_traces(L: Landscape, label: str = ""):
    """Print trace info for all key edges."""
    if label:
        print(f"  {label}:")
    key_edges = [
        ("START", "A"), ("START", "C"),
        ("A", "B"), ("C", "B"), ("B", "GOAL"),
    ]
    for src, tgt in key_edges:
        info = trace_info(L, src, tgt)
        print(f"    {src}→{tgt}: q={info['quality']:+.4f}  "
              f"load={info['load']:.4f}  I={info['inertia']:.4f}")


def run_phase(ctrl: E0Controller, start: str, goal: str,
              max_cycles: int, label: str) -> List[str]:
    """Run controller and return path taken."""
    result = ctrl.run(start=start, goal=goal, max_cycles=max_cycles)
    path = result.path
    print(f"  {label}: {' → '.join(path)}")
    reached = result.steps[-1].target == goal if result.steps else False
    print(f"    Steps: {len(result.steps)}, Goal reached: {reached}")
    return path


# ── Scenario 1: Observation Parity ──────────────────────────────────

def scenario_observation_parity():
    """
    Phase 1: Navigate START→GOAL in both CAUSAL and CONFOUNDED domains.
    Prediction: traces should be identical (both succeed via A→B→GOAL).
    """
    print("=" * 72)
    print("SCENARIO 1: Observation Parity")
    print("  Prediction: CAUSAL and CONFOUNDED produce identical traces")
    print("=" * 72)
    print()

    # --- CAUSAL domain ---
    L_causal = build_diamond_landscape()
    exec_causal = make_causal_execute()
    ctrl_causal = E0Controller(L_causal, exec_causal)

    print("[CAUSAL domain — 5 observation cycles]")
    for i in range(5):
        run_phase(ctrl_causal, "START", "GOAL", max_cycles=10, label=f"Cycle {i+1}")
    print()
    print_traces(L_causal, "CAUSAL traces after observation")
    print()

    # --- CONFOUNDED domain ---
    L_confound = build_diamond_landscape()
    exec_confound, _ = make_confounded_execute()
    ctrl_confound = E0Controller(L_confound, exec_confound)

    print("[CONFOUNDED domain — 5 observation cycles]")
    for i in range(5):
        run_phase(ctrl_confound, "START", "GOAL", max_cycles=10, label=f"Cycle {i+1}")
    print()
    print_traces(L_confound, "CONFOUNDED traces after observation")
    print()

    # --- Compare traces ---
    print("[Comparison]")
    edges = [("START", "A"), ("START", "C"), ("A", "B"), ("C", "B"), ("B", "GOAL")]
    all_identical = True
    for src, tgt in edges:
        q_c = trace_info(L_causal, src, tgt)["quality"]
        q_f = trace_info(L_confound, src, tgt)["quality"]
        match = "✓" if abs(q_c - q_f) < 0.01 else "✗ DIVERGED"
        if abs(q_c - q_f) >= 0.01:
            all_identical = False
        print(f"  {src}→{tgt}: CAUSAL q={q_c:+.4f}  CONFOUNDED q={q_f:+.4f}  {match}")

    verdict = "PASS" if all_identical else "FAIL"
    if not all_identical:
        print(f"  NOTE: Prediction P1 refuted — E₀'s natural path alternation")
        print(f"  functions as IMPLICIT INTERVENTION. By trying C→B→GOAL,")
        print(f"  the controller tests B→GOAL without A as predecessor.")
        print(f"  Causal leakage is partially visible from observation alone!")
    print(f"\n  Verdict (traces identical during observation): {verdict}")
    print()
    return L_causal, ctrl_causal, L_confound, ctrl_confound, verdict


# ── Scenario 2: Intervention Divergence ─────────────────────────────

def scenario_intervention(L_causal, ctrl_causal, L_confound, ctrl_confound):
    """
    Phase 2: Navigate B→GOAL directly (intervention — skip A).
    Prediction: CAUSAL succeeds, CONFOUNDED fails.
    """
    print("=" * 72)
    print("SCENARIO 2: Intervention Test (do-calculus analog)")
    print("  Prediction: CAUSAL B→GOAL succeeds, CONFOUNDED B→GOAL fails")
    print("=" * 72)
    print()

    # Count actual FAILURE outcomes (not just goal-reaching)
    print("[CAUSAL domain — 5 intervention cycles (start='B')]")
    causal_failures = 0
    for i in range(5):
        result = ctrl_causal.run(start="B", goal="GOAL", max_cycles=5)
        reached = result.steps[-1].target == "GOAL" if result.steps else False
        outcome = result.steps[-1].outcome if result.steps else None
        if outcome == Outcome.FAILURE:
            causal_failures += 1
        print(f"  Cycle {i+1}: target={'GOAL' if reached else '?'}  "
              f"outcome={outcome.name if outcome else '?'}")
    print()
    print_traces(L_causal, "CAUSAL traces after intervention")
    print()

    print("[CONFOUNDED domain — 5 intervention cycles (start='B')]")
    confound_failures = 0
    for i in range(5):
        result = ctrl_confound.run(start="B", goal="GOAL", max_cycles=5)
        reached = result.steps[-1].target == "GOAL" if result.steps else False
        outcome = result.steps[-1].outcome if result.steps else None
        if outcome == Outcome.FAILURE:
            confound_failures += 1
        print(f"  Cycle {i+1}: target={'GOAL' if reached else '?'}  "
              f"outcome={outcome.name if outcome else '?'}")
    print()
    print_traces(L_confound, "CONFOUNDED traces after intervention")
    print()

    # --- Compare B→GOAL quality divergence ---
    q_causal = trace_info(L_causal, "B", "GOAL")["quality"]
    q_confound = trace_info(L_confound, "B", "GOAL")["quality"]
    divergence = abs(q_causal - q_confound)

    print("[Comparison after intervention]")
    print(f"  B→GOAL quality:  CAUSAL={q_causal:+.4f}  CONFOUNDED={q_confound:+.4f}")
    print(f"  Divergence: {divergence:.4f}")
    print(f"  CAUSAL failures: {causal_failures}/5  "
          f"CONFOUNDED failures: {confound_failures}/5")

    # Quality divergence is the signal (not goal-reaching — controller always navigates)
    verdict = "PASS" if divergence > 0.3 else "FAIL"
    print(f"\n  Verdict (intervention reveals confound): {verdict}")
    print()
    return L_causal, L_confound, verdict


# ── Scenario 3: Dream Equivalence Detection ─────────────────────────

def scenario_dream_detection(L_causal, L_confound):
    """
    Dream coupling between CAUSAL and CONFOUNDED after intervention.
    Prediction: B→GOAL equivalence should be BROKEN (different fingerprints).
    """
    print("=" * 72)
    print("SCENARIO 3: Dream Equivalence Detection")
    print("  Prediction: B→GOAL equivalence broken after intervention")
    print("=" * 72)
    print()

    # Edge fingerprints
    fps_c = domain_fingerprints(L_causal, "CAUSAL")
    fps_f = domain_fingerprints(L_confound, "CONFOUNDED")

    print("[Edge fingerprints]")
    for fp in fps_c:
        print(f"  CAUSAL    {fp.edge.source}→{fp.edge.target}: "
              f"q={fp.quality:+.4f}  load={fp.load:.4f}  I={fp.inertia:.4f}")
    for fp in fps_f:
        print(f"  CONFOUND  {fp.edge.source}→{fp.edge.target}: "
              f"q={fp.quality:+.4f}  load={fp.load:.4f}  I={fp.inertia:.4f}")
    print()

    # Find B→GOAL fingerprints
    fp_b_goal_causal = next(
        (fp for fp in fps_c if fp.edge.source == "B" and fp.edge.target == "GOAL"),
        None)
    fp_b_goal_confound = next(
        (fp for fp in fps_f if fp.edge.source == "B" and fp.edge.target == "GOAL"),
        None)

    if fp_b_goal_causal and fp_b_goal_confound:
        dist = fingerprint_distance(fp_b_goal_causal, fp_b_goal_confound)
        print(f"[B→GOAL fingerprint distance: {dist:.4f}]")
        print(f"  CAUSAL:    q={fp_b_goal_causal.quality:+.4f}  "
              f"load={fp_b_goal_causal.load:.4f}  I={fp_b_goal_causal.inertia:.4f}")
        print(f"  CONFOUND:  q={fp_b_goal_confound.quality:+.4f}  "
              f"load={fp_b_goal_confound.load:.4f}  I={fp_b_goal_confound.inertia:.4f}")
    else:
        dist = 0.0
        print("  [WARNING: B→GOAL fingerprint not found in one domain]")

    print()

    # Find all equivalences
    equivs = find_equivalences(
        L_causal, L_confound,
        domain_a="CAUSAL", domain_b="CONFOUNDED",
        quantile=0.5,  # generous threshold to see what matches
    )

    print(f"[Dream equivalences found: {len(equivs)}]")
    b_goal_matched = False
    for eq in equivs:
        tag = ""
        if (eq.edge_a.source == "B" and eq.edge_a.target == "GOAL" and
                eq.edge_b.source == "B" and eq.edge_b.target == "GOAL"):
            tag = " ← B→GOAL MATCH"
            b_goal_matched = True
        print(f"  {eq.domain_a}:{eq.edge_a.source}→{eq.edge_a.target} ↔ "
              f"{eq.domain_b}:{eq.edge_b.source}→{eq.edge_b.target}  "
              f"dist={eq.distance:.4f}  conf={eq.confidence:.4f}{tag}")
    print()

    verdict = "PASS" if dist > 0.3 and not b_goal_matched else "FAIL"
    print(f"  B→GOAL equivalence broken: {'YES' if not b_goal_matched else 'NO'}")
    print(f"  B→GOAL fingerprint distance: {dist:.4f}")
    print(f"\n  Verdict (dream detects causal divergence): {verdict}")
    print()
    return verdict


# ── Scenario 4: Fragile Degradation ─────────────────────────────────

def scenario_fragile():
    """
    Fragile domain: A→B degrades after 3 uses.
    Prediction: Controller learns to prefer C→B after degradation.
    No intervention needed — historization detects this naturally.
    """
    print("=" * 72)
    print("SCENARIO 4: Fragile Path Degradation")
    print("  Prediction: Controller switches from A→B to C→B after failure")
    print("=" * 72)
    print()

    L = build_diamond_landscape()
    exec_fn, stats = make_fragile_execute()
    ctrl = E0Controller(L, exec_fn)

    paths_via_a = 0
    paths_via_c = 0
    switch_cycle = None

    for i in range(10):
        result = ctrl.run(start="START", goal="GOAL", max_cycles=10)
        path = result.path
        via_a = "A" in path
        via_c = "C" in path
        reached = result.steps[-1].target == "GOAL" if result.steps else False

        if via_a:
            paths_via_a += 1
        if via_c:
            paths_via_c += 1
        if via_c and switch_cycle is None:
            switch_cycle = i + 1

        print(f"  Cycle {i+1}: {' → '.join(path)}  "
              f"{'GOAL' if reached else 'STUCK'}  "
              f"A→B count={stats['a_b_count']}")

    print()
    print_traces(L, "Traces after 10 cycles")
    print()

    q_ab = trace_info(L, "A", "B")["quality"]
    q_cb = trace_info(L, "C", "B")["quality"]

    print(f"[Summary]")
    print(f"  Paths via A: {paths_via_a}")
    print(f"  Paths via C: {paths_via_c}")
    print(f"  Switch cycle: {switch_cycle or 'never'}")
    print(f"  A→B quality: {q_ab:+.4f}")
    print(f"  C→B quality: {q_cb:+.4f}")

    # Verdict: controller should have switched to C path
    verdict = "PASS" if paths_via_c >= 3 and q_ab < q_cb else "FAIL"
    print(f"\n  Verdict (historization detects degradation): {verdict}")
    print()
    return verdict


# ── Scenario 5: Cross-Domain Transfer ───────────────────────────────

def scenario_transfer():
    """
    After CAUSAL domain is well-historized, can its knowledge help
    a new domain with the same topology?

    CAUSAL domain: fully explored, B→GOAL quality high.
    NEW domain: same topology, no history.

    Use CAUSAL domain's fingerprints to guide NEW domain's first navigation.
    """
    print("=" * 72)
    print("SCENARIO 5: Cross-Domain Transfer (causal knowledge portability)")
    print("  Prediction: Good causal knowledge transfers; confounded knowledge misleads")
    print("=" * 72)
    print()

    # Build and train CAUSAL domain (10 cycles including intervention)
    L_causal = build_diamond_landscape()
    exec_causal = make_causal_execute()
    ctrl_causal = E0Controller(L_causal, exec_causal)
    for _ in range(5):
        ctrl_causal.run(start="START", goal="GOAL", max_cycles=10)
    for _ in range(5):
        ctrl_causal.run(start="B", goal="GOAL", max_cycles=5)

    # Build and train CONFOUNDED domain (10 cycles including intervention)
    L_confound = build_diamond_landscape()
    exec_confound, _ = make_confounded_execute()
    ctrl_confound = E0Controller(L_confound, exec_confound)
    for _ in range(5):
        ctrl_confound.run(start="START", goal="GOAL", max_cycles=10)
    for _ in range(5):
        ctrl_confound.run(start="B", goal="GOAL", max_cycles=5)

    print("[Trained domains]")
    print_traces(L_causal, "CAUSAL (post-intervention)")
    print()
    print_traces(L_confound, "CONFOUNDED (post-intervention)")
    print()

    # Find equivalences from each trained domain to a fresh domain
    L_fresh = build_diamond_landscape()

    equivs_from_causal = find_equivalences(
        L_causal, L_fresh, domain_a="CAUSAL", domain_b="FRESH", quantile=0.5)
    equivs_from_confound = find_equivalences(
        L_confound, L_fresh, domain_a="CONFOUNDED", domain_b="FRESH", quantile=0.5)

    print(f"[Equivalences: CAUSAL→FRESH = {len(equivs_from_causal)}, "
          f"CONFOUNDED→FRESH = {len(equivs_from_confound)}]")

    # Check: does B→GOAL from causal match fresh B→GOAL?
    causal_b_match = any(
        eq.edge_a.source == "B" and eq.edge_a.target == "GOAL" and
        eq.edge_b.source == "B" and eq.edge_b.target == "GOAL"
        for eq in equivs_from_causal)
    confound_b_match = any(
        eq.edge_a.source == "B" and eq.edge_a.target == "GOAL" and
        eq.edge_b.source == "B" and eq.edge_b.target == "GOAL"
        for eq in equivs_from_confound)

    print(f"  CAUSAL B→GOAL matches FRESH B→GOAL: {causal_b_match}")
    print(f"  CONFOUNDED B→GOAL matches FRESH B→GOAL: {confound_b_match}")

    # The insight: trained causal domain SHOULD match fresh (both B→GOAL are q≈0)
    # because causal B→GOAL has consistently positive quality
    # while confounded B→GOAL has mixed/negative quality
    print()

    # Quality comparison
    q_causal = trace_info(L_causal, "B", "GOAL")["quality"]
    q_confound = trace_info(L_confound, "B", "GOAL")["quality"]
    q_fresh = trace_info(L_fresh, "B", "GOAL")["quality"]
    print(f"  B→GOAL quality: CAUSAL={q_causal:+.4f}  "
          f"CONFOUNDED={q_confound:+.4f}  FRESH={q_fresh:+.4f}")

    verdict = "PASS" if q_causal > 0 and q_confound < q_causal else "PARTIAL"
    print(f"\n  Verdict (causal knowledge more transferable): {verdict}")
    print()
    return verdict


# ══════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print()
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║  C175: CAUSAL BINDING EXPLORATION                                  ║")
    print("║  Can E₀ distinguish causation from correlation?                    ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")
    print()

    # Scenario 1: Observation phase — traces should be identical
    L_c, ctrl_c, L_f, ctrl_f, v1 = scenario_observation_parity()

    # Scenario 2: Intervention — traces should diverge
    L_c, L_f, v2 = scenario_intervention(L_c, ctrl_c, L_f, ctrl_f)

    # Scenario 3: Dream detects the divergence
    v3 = scenario_dream_detection(L_c, L_f)

    # Scenario 4: Fragile path — natural degradation
    v4 = scenario_fragile()

    # Scenario 5: Cross-domain transfer
    v5 = scenario_transfer()

    # Summary
    print("=" * 72)
    print("SUMMARY")
    print("=" * 72)
    results = [
        ("S1: Observation Parity", v1, "Traces identical during observation"),
        ("S2: Intervention Divergence", v2, "Intervention reveals confound"),
        ("S3: Dream Detection", v3, "Dream detects causal divergence"),
        ("S4: Fragile Degradation", v4, "Historization detects path degradation"),
        ("S5: Cross-Domain Transfer", v5, "Causal knowledge more transferable"),
    ]
    for name, verdict, description in results:
        icon = "✓" if verdict == "PASS" else ("~" if verdict == "PARTIAL" else "✗")
        print(f"  [{icon}] {name}: {verdict} — {description}")
    print()

    pass_count = sum(1 for _, v, _ in results if v == "PASS")
    partial_count = sum(1 for _, v, _ in results if v == "PARTIAL")
    fail_count = sum(1 for _, v, _ in results if v == "FAIL")
    print(f"  Total: {pass_count} PASS, {partial_count} PARTIAL, {fail_count} FAIL")
    print()
