"""
C178 — Dream-Based Causal Transfer Exploration

Demonstrates that the 4D fingerprint (quality, load, inertia,
context_sensitivity) prevents false cross-domain equivalences
between causal and confounded edges.

Protocol:
  Phase 1: Train CAUSAL and CONFOUNDED domains (balanced observation)
  Phase 2: Extract 4D fingerprints, compare to 3D-only baseline
  Phase 3: Show find_equivalences correctly excludes confounded B→GOAL
  Phase 4: Introduce FRESH domain, verify no false transfer from CONFOUNDED

Reference: docs/research/E0_CAUSAL_BINDING_RESEARCH_v1.md §S7
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import List, Tuple, Callable

from e0_controller.controller import E0Controller, HybridMode
from e0_controller.dream_mode import (
    EdgeFingerprint,
    domain_fingerprints,
    find_equivalences,
    fingerprint_distance,
)
from e0_controller.landscape import Landscape
from e0_controller.primitives import Edge, Outcome


# ── Domain Builders ──────────────────────────────────────────────────

def build_diamond_landscape() -> Landscape:
    """
    Diamond topology:
        START → A → B → GOAL
        START → C → B → GOAL
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
    """All transitions always succeed."""
    return lambda src, tgt: Outcome.SUCCESS


def make_confounded_execute() -> Tuple[Callable, List[str]]:
    """B→GOAL succeeds only if preceded by A→B."""
    history: List[str] = []
    def execute(src, tgt):
        history.append(f"{src}→{tgt}")
        if src == "B" and tgt == "GOAL":
            if len(history) >= 2 and history[-2] == "A→B":
                return Outcome.SUCCESS
            return Outcome.FAILURE
        return Outcome.SUCCESS
    return execute, history


# ── Helpers ──────────────────────────────────────────────────────────

def print_fingerprint(fp: EdgeFingerprint, label: str = ""):
    """Print a single fingerprint with all 4 dimensions."""
    tag = f"  {label} " if label else "  "
    print(f"{tag}{fp.domain}/{fp.edge.source}→{fp.edge.target}: "
          f"q={fp.quality:+.4f}  load={fp.load:.1f}  "
          f"I={fp.inertia:.4f}  cs={fp.context_sensitivity:.4f}")


def distance_3d(a: EdgeFingerprint, b: EdgeFingerprint) -> float:
    """3D distance (quality, load, inertia) — WITHOUT context_sensitivity."""
    mu = 5.0
    dq = a.quality - b.quality
    dm = a.load / (a.load + mu) - b.load / (b.load + mu)
    di = a.inertia - b.inertia
    return math.sqrt(dq * dq + dm * dm + di * di)


def run_cycles(ctrl: E0Controller, start: str, goal: str,
               n: int, label: str = "") -> None:
    """Run n cycles, print summary."""
    for i in range(n):
        ctrl.run(start, max_cycles=10, goal=goal)
    if label:
        h = ctrl.landscape.historization
        e = Edge("B", "GOAL")
        q = h.trace_quality(e)
        cs = h.context_sensitivity(e)
        print(f"  {label}: {n} cycles → B→GOAL q={q:+.4f}, cs={cs:.4f}")


# ── Main ─────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("C178 — Dream-Based Causal Transfer Exploration")
    print("=" * 70)

    # ── Phase 1: Train Domains ───────────────────────────────────────
    print("\n▸ Phase 1: Training CAUSAL and CONFOUNDED domains")

    L_causal = build_diamond_landscape()
    ctrl_causal = E0Controller(
        L_causal, make_causal_execute(),
        hybrid_mode=HybridMode.GREEDY, recent_k=3,
    )
    run_cycles(ctrl_causal, "START", "GOAL", 10, "CAUSAL")

    execute_conf, _ = make_confounded_execute()
    L_confound = build_diamond_landscape()
    ctrl_confound = E0Controller(
        L_confound, execute_conf,
        hybrid_mode=HybridMode.GREEDY, recent_k=3,
    )
    run_cycles(ctrl_confound, "START", "GOAL", 10, "CONFOUNDED")

    # ── Phase 2: Compare 3D vs 4D Fingerprints ──────────────────────
    print("\n▸ Phase 2: Fingerprint Comparison (3D vs 4D)")

    fps_causal = domain_fingerprints(L_causal, "CAUSAL")
    fps_confound = domain_fingerprints(L_confound, "CONFOUNDED")

    fp_c_bg = next(fp for fp in fps_causal if fp.edge == Edge("B", "GOAL"))
    fp_f_bg = next(fp for fp in fps_confound if fp.edge == Edge("B", "GOAL"))

    print("\n  B→GOAL fingerprints:")
    print_fingerprint(fp_c_bg, "CAUSAL")
    print_fingerprint(fp_f_bg, "CONFOUNDED")

    d3 = distance_3d(fp_c_bg, fp_f_bg)
    d4 = fingerprint_distance(fp_c_bg, fp_f_bg)
    print(f"\n  3D distance (q, load, I):     {d3:.4f}")
    print(f"  4D distance (+cs):            {d4:.4f}")
    print(f"  cs contribution:              {abs(fp_c_bg.context_sensitivity - fp_f_bg.context_sensitivity):.4f}")
    gain = d4 - d3
    print(f"  4D gain over 3D:              {gain:+.4f}")

    # ── Phase 3: Dream Equivalences ──────────────────────────────────
    print("\n▸ Phase 3: Dream Equivalences (CAUSAL ↔ CONFOUNDED)")

    equivs = find_equivalences(
        L_causal, L_confound,
        domain_a="CAUSAL", domain_b="CONFOUNDED",
        quantile=0.5,
    )
    print(f"\n  Total equivalences found: {len(equivs)}")
    b_goal_matched = False
    for eq in equivs:
        tag = ""
        if eq.edge_a == Edge("B", "GOAL") and eq.edge_b == Edge("B", "GOAL"):
            tag = " ← B→GOAL MATCHED (FALSE POSITIVE!)"
            b_goal_matched = True
        print(f"    {eq.domain_a}/{eq.edge_a.source}→{eq.edge_a.target} ↔ "
              f"{eq.domain_b}/{eq.edge_b.source}→{eq.edge_b.target}  "
              f"dist={eq.distance:.4f}  conf={eq.confidence:.4f}{tag}")

    if b_goal_matched:
        print("\n  ⚠ B→GOAL falsely matched — 4D fingerprint insufficient!")
    else:
        print("\n  ✓ B→GOAL correctly excluded from equivalences")

    # ── Phase 4: Fresh Domain — No False Transfer ────────────────────
    print("\n▸ Phase 4: FRESH domain (no history)")

    L_fresh = build_diamond_landscape()
    # Record minimal exploration (1 cycle) to give fingerprints some data
    ctrl_fresh = E0Controller(
        L_fresh, make_causal_execute(),
        hybrid_mode=HybridMode.GREEDY, recent_k=3,
    )
    run_cycles(ctrl_fresh, "START", "GOAL", 2, "FRESH")

    fps_fresh = domain_fingerprints(L_fresh, "FRESH")
    fp_fresh_bg = next(fp for fp in fps_fresh if fp.edge == Edge("B", "GOAL"))

    print("\n  FRESH B→GOAL fingerprint:")
    print_fingerprint(fp_fresh_bg, "FRESH")

    # Distance from CONFOUNDED to FRESH
    d_conf_fresh_4d = fingerprint_distance(fp_f_bg, fp_fresh_bg)
    d_conf_fresh_3d = distance_3d(fp_f_bg, fp_fresh_bg)
    # Distance from CAUSAL to FRESH
    d_caus_fresh_4d = fingerprint_distance(fp_c_bg, fp_fresh_bg)
    d_caus_fresh_3d = distance_3d(fp_c_bg, fp_fresh_bg)

    print(f"\n  CONFOUNDED→FRESH distance: 3D={d_conf_fresh_3d:.4f}, 4D={d_conf_fresh_4d:.4f}")
    print(f"  CAUSAL→FRESH distance:     3D={d_caus_fresh_3d:.4f}, 4D={d_caus_fresh_4d:.4f}")

    # CONFOUNDED should be further from FRESH than CAUSAL is
    if d_conf_fresh_4d > d_caus_fresh_4d:
        print("\n  ✓ CONFOUNDED is further from FRESH than CAUSAL (correct)")
    else:
        print("\n  ⚠ CONFOUNDED is closer to FRESH — unexpected")

    # ── Verdict ──────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    checks = [
        ("B→GOAL excluded from equivalences", not b_goal_matched),
        ("4D distance > 3D distance", d4 > d3),
        ("CONFOUNDED further from FRESH (4D)", d_conf_fresh_4d > d_caus_fresh_4d),
        ("CAUSAL cs ≈ 0", fp_c_bg.context_sensitivity < 0.5),
        ("CONFOUNDED cs > 1.5", fp_f_bg.context_sensitivity > 1.5),
    ]
    all_pass = True
    for desc, ok in checks:
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        print(f"  [{status}] {desc}")

    print("\n" + ("  ◆ ALL CHECKS PASSED" if all_pass else "  ◆ SOME CHECKS FAILED"))
    print("=" * 70)


if __name__ == "__main__":
    main()
