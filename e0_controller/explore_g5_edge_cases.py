"""
G5 Edge Case Exploration — Families A–E
========================================
Tests how G5 (goal_reaching geometry) behaves under stress:
  A — Goal-count expansion (|G| = 1..5)
  B — Irrelevant-goal injection
  C — Competing-goal conflict
  D — Rescue threshold (parametric)
  E — Ranking sharpness (entropy, top-gap)

Reference: docs/research/E0_G5_EDGE_CASE_SUITE_v1.md
"""
import math
import cmath
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

from e0_controller.landscape import Landscape
from e0_controller.connection import theta
from e0_controller.wavepath import psi
from e0_controller.controller import E0Controller
from e0_controller.primitives import Outcome
from e0_controller.amplitude_overlay import analyze_controller_state, OverlayReport

START = "START"


def evaluate(source, target):
    return Outcome.SUCCESS


# ── Metrics ───────────────────────────────────────────────────

def entropy(probs: List[float]) -> float:
    """Shannon entropy of a probability distribution."""
    h = 0.0
    for p in probs:
        if p > 1e-15:
            h -= p * math.log2(p)
    return h


def top_gap(probs: List[float]) -> float:
    """Gap between top-1 and top-2 probability."""
    s = sorted(probs, reverse=True)
    if len(s) < 2:
        return s[0] if s else 0.0
    return s[0] - s[1]


def report_metrics(report: OverlayReport) -> Dict:
    """Extract key metrics from an OverlayReport."""
    probs = [ai.probability for ai in report.action_infos]
    intensities = {ai.action: ai.intensity for ai in report.action_infos}
    return {
        "winner": report.amplitude_choice,
        "greedy": report.deterministic_choice,
        "override": report.amplitude_choice != report.deterministic_choice,
        "probs": {ai.action: ai.probability for ai in report.action_infos},
        "intensities": intensities,
        "entropy": entropy(probs),
        "top_gap": top_gap(probs),
        "top1_prob": max(probs) if probs else 0.0,
        "path_counts": {ai.action: ai.path_count for ai in report.action_infos},
    }


def goal_decomposition(ctrl: E0Controller, current: str, goals: Set[str],
                        horizon: int = 5) -> Dict[str, Dict[str, complex]]:
    """
    Decompose Ψ(a, G) = Σ_g Ψ(a, g) per-goal.
    Returns {action: {goal: Ψ(a,{g})}}.
    """
    decomp = defaultdict(dict)
    for g in goals:
        report = analyze_controller_state(
            ctrl, current, horizon_edges=horizon,
            geometry="goal_reaching", goals={g}
        )
        for ai in report.action_infos:
            decomp[ai.action][g] = ai.psi_total
    return dict(decomp)


def sep(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


# ── Family A: Goal-Count Expansion ───────────────────────────

def build_family_a() -> Landscape:
    """
    Star topology: START fans out to A, B.
    5 goals: G1..G5 at varying distances/coherence.
      A → M1 → G1  (strong coherent)
      A → M2 → G2  (moderate)
      A → M3 → G3  (weak)
      B → G1       (short, strong)
      B → M4 → G4  (moderate)
      B → M5 → G5  (weak)
    A dominates for G2,G3; B dominates for G1; mixed for G4,G5.
    """
    L = Landscape()
    # A paths
    L.add_edge(START, "A", delta=0.3, resistance=0.3)
    L.add_edge("A", "M1", delta=0.5, resistance=0.2)
    L.add_edge("M1", "G1", delta=0.4, resistance=0.3)
    L.add_edge("A", "M2", delta=0.6, resistance=0.3)
    L.add_edge("M2", "G2", delta=0.5, resistance=0.3)
    L.add_edge("A", "M3", delta=0.3, resistance=0.5)
    L.add_edge("M3", "G3", delta=0.2, resistance=0.5)
    # B paths
    L.add_edge(START, "B", delta=0.5, resistance=0.4)
    L.add_edge("B", "G1", delta=0.8, resistance=0.2)   # short + strong
    L.add_edge("B", "M4", delta=0.4, resistance=0.4)
    L.add_edge("M4", "G4", delta=0.3, resistance=0.4)
    L.add_edge("B", "M5", delta=0.2, resistance=0.6)
    L.add_edge("M5", "G5", delta=0.1, resistance=0.7)
    return L


def run_family_a():
    sep("Family A — Goal-Count Expansion")
    L = build_family_a()
    ctrl = E0Controller(L, evaluate)
    all_goals = ["G1", "G2", "G3", "G4", "G5"]

    print(f"\n  Expanding goal set from |G|=1 to |G|=5:")
    print(f"  {'|G|':>4s}  {'Goals':30s}  {'Winner':>6s}  {'Top1-P':>7s}  "
          f"{'Gap':>6s}  {'Entropy':>7s}  {'Override':>8s}")
    print(f"  {'-'*4}  {'-'*30}  {'-'*6}  {'-'*7}  {'-'*6}  {'-'*7}  {'-'*8}")

    results = []
    for n in range(1, 6):
        goals = set(all_goals[:n])
        report = analyze_controller_state(
            ctrl, START, horizon_edges=5, geometry="goal_reaching", goals=goals
        )
        m = report_metrics(report)
        results.append(m)
        g_str = ",".join(sorted(goals))
        print(f"  {n:4d}  {g_str:30s}  {m['winner']:>6s}  {m['top1_prob']:7.3f}  "
              f"{m['top_gap']:6.3f}  {m['entropy']:7.3f}  {'YES' if m['override'] else 'no':>8s}")

    # Goal decomposition at |G|=5
    print(f"\n  Goal decomposition at |G|=5:")
    decomp = goal_decomposition(ctrl, START, set(all_goals), horizon=5)
    print(f"  {'Action':>6s}  ", end="")
    for g in all_goals:
        print(f"{'I('+g+')':>10s}", end="")
    print(f"  {'Total I':>8s}")
    for action in sorted(decomp.keys()):
        total_psi = sum(decomp[action].values())
        print(f"  {action:>6s}  ", end="")
        for g in all_goals:
            psi_g = decomp[action].get(g, 0j)
            print(f"{abs(psi_g)**2:10.5f}", end="")
        print(f"  {abs(total_psi)**2:8.5f}")

    return results


# ── Family B: Irrelevant-Goal Injection ──────────────────────

def build_family_b() -> Landscape:
    """
    Clean base domain + 3 irrelevant goals:
      Base: START → A → G_REAL (strong), START → B → G_REAL (moderate)
      Irrelevant:
        G_UNREACH: no path from START
        G_WEAK: START → C → D → E → G_WEAK (very high resistance)
        G_NOISY: START → A → F → G_NOISY (many incoherent sub-paths)
    """
    L = Landscape()
    # Base domain
    L.add_edge(START, "A", delta=0.5, resistance=0.3)
    L.add_edge("A", "G_REAL", delta=0.6, resistance=0.2)
    L.add_edge(START, "B", delta=0.3, resistance=0.4)
    L.add_edge("B", "G_REAL", delta=0.4, resistance=0.3)

    # Weak goal (long, high-resistance path)
    L.add_edge(START, "C", delta=0.1, resistance=0.9)
    L.add_edge("C", "D", delta=0.05, resistance=0.95)
    L.add_edge("D", "E", delta=0.05, resistance=0.95)
    L.add_edge("E", "G_WEAK", delta=0.05, resistance=0.95)

    # Noisy goal (multiple crossing paths from A, likely incoherent)
    L.add_edge("A", "F1", delta=2.0, resistance=0.1)
    L.add_edge("F1", "G_NOISY", delta=0.3, resistance=0.3)
    L.add_edge("A", "F2", delta=0.1, resistance=0.8)
    L.add_edge("F2", "G_NOISY", delta=2.5, resistance=0.1)

    # G_UNREACH: exists as a state but no path from START
    L.add_edge("ISOLATED", "G_UNREACH", delta=1.0, resistance=0.5)

    return L


def run_family_b():
    sep("Family B — Irrelevant-Goal Injection")
    L = build_family_b()
    ctrl = E0Controller(L, evaluate)

    scenarios = [
        ("base",       {"G_REAL"}),
        ("+unreach",   {"G_REAL", "G_UNREACH"}),
        ("+weak",      {"G_REAL", "G_WEAK"}),
        ("+noisy",     {"G_REAL", "G_NOISY"}),
        ("+all_irrel", {"G_REAL", "G_UNREACH", "G_WEAK", "G_NOISY"}),
    ]

    print(f"\n  {'Scenario':>12s}  {'Goals':35s}  {'Winner':>6s}  {'P(A)':>6s}  "
          f"{'P(B)':>6s}  {'P(C)':>6s}  {'Top1-P':>7s}  {'Entropy':>7s}")
    print(f"  {'-'*12}  {'-'*35}  {'-'*6}  {'-'*6}  {'-'*6}  {'-'*6}  {'-'*7}  {'-'*7}")

    base_winner = None
    results = []
    for name, goals in scenarios:
        report = analyze_controller_state(
            ctrl, START, horizon_edges=6, geometry="goal_reaching", goals=goals
        )
        m = report_metrics(report)
        results.append((name, m))
        if base_winner is None:
            base_winner = m["winner"]
        g_str = ",".join(sorted(goals))
        pa = m["probs"].get("A", 0)
        pb = m["probs"].get("B", 0)
        pc = m["probs"].get("C", 0)
        print(f"  {name:>12s}  {g_str:35s}  {m['winner']:>6s}  {pa:6.3f}  "
              f"{pb:6.3f}  {pc:6.3f}  {m['top1_prob']:7.3f}  {m['entropy']:7.3f}")

    # Stability check
    drifted = [name for name, m in results if m["winner"] != base_winner]
    if drifted:
        print(f"\n  ⚠ DRIFT: Winner changed in scenarios: {drifted}")
    else:
        print(f"\n  ✓ STABLE: Winner '{base_winner}' preserved across all irrelevant injections")

    return results


# ── Family C: Competing-Goal Conflict ────────────────────────

def build_family_c() -> Landscape:
    """
    Explicit conflict: A is best for G_ALPHA, B is best for G_BETA.
    C is locally cheapest but incoherent for both.
      A → G_ALPHA (strong coherent)
      B → G_BETA  (strong coherent)
      C → G_ALPHA (weak, two cancelling paths)
      C → G_BETA  (weak)
    """
    L = Landscape()
    # A — strong toward G_ALPHA
    L.add_edge(START, "A", delta=0.4, resistance=0.3)
    L.add_edge("A", "G_ALPHA", delta=0.6, resistance=0.2)

    # B — strong toward G_BETA
    L.add_edge(START, "B", delta=0.4, resistance=0.3)
    L.add_edge("B", "G_BETA", delta=0.6, resistance=0.2)

    # C — locally cheapest but incoherent
    L.add_edge(START, "C", delta=0.8, resistance=0.1)   # cheap entry!
    # Two cancelling paths from C to G_ALPHA (Gordian-style)
    L.add_edge("C", "X1", delta=0.2, resistance=0.4)    # low v
    L.add_edge("X1", "G_ALPHA", delta=0.2, resistance=0.4)
    L.add_edge("C", "X2", delta=2.5, resistance=0.05)    # high v → phase shift
    L.add_edge("X2", "G_ALPHA", delta=2.5, resistance=0.05)
    # Weak path from C to G_BETA
    L.add_edge("C", "Y1", delta=0.1, resistance=0.8)
    L.add_edge("Y1", "G_BETA", delta=0.1, resistance=0.8)

    return L


def run_family_c():
    sep("Family C — Competing-Goal Conflict")
    L = build_family_c()
    ctrl = E0Controller(L, evaluate)

    scenarios = [
        ("G_ALPHA only",  {"G_ALPHA"}),
        ("G_BETA only",   {"G_BETA"}),
        ("Both goals",    {"G_ALPHA", "G_BETA"}),
    ]

    print(f"\n  {'Scenario':>15s}  {'Winner':>6s}  {'Greedy':>6s}  "
          f"{'P(A)':>6s}  {'P(B)':>6s}  {'P(C)':>6s}  {'Entropy':>7s}  {'Override':>8s}")
    print(f"  {'-'*15}  {'-'*6}  {'-'*6}  {'-'*6}  {'-'*6}  {'-'*6}  {'-'*7}  {'-'*8}")

    results = []
    for name, goals in scenarios:
        report = analyze_controller_state(
            ctrl, START, horizon_edges=5, geometry="goal_reaching", goals=goals
        )
        m = report_metrics(report)
        results.append((name, m))
        pa = m["probs"].get("A", 0)
        pb = m["probs"].get("B", 0)
        pc = m["probs"].get("C", 0)
        print(f"  {name:>15s}  {m['winner']:>6s}  {m['greedy']:>6s}  "
              f"{pa:6.3f}  {pb:6.3f}  {pc:6.3f}  {m['entropy']:7.3f}  "
              f"{'YES' if m['override'] else 'no':>8s}")

    # Goal decomposition
    print(f"\n  Goal decomposition (both goals):")
    decomp = goal_decomposition(ctrl, START, {"G_ALPHA", "G_BETA"}, horizon=5)
    for action in sorted(decomp.keys()):
        parts = []
        for g in ["G_ALPHA", "G_BETA"]:
            psi_g = decomp[action].get(g, 0j)
            parts.append(f"I({g})={abs(psi_g)**2:.5f}")
        total_psi = sum(decomp[action].values())
        parts.append(f"I_total={abs(total_psi)**2:.5f}")
        print(f"    {action}: {', '.join(parts)}")

    return results


# ── Family D: Rescue Threshold ───────────────────────────────

def build_family_d(rescue_delta: float) -> Landscape:
    """
    Gordian-style: A has destructive interference toward G1.
    A has one coherent rescue path toward G2 with variable strength.
    B is coherent toward G1.
    """
    L = Landscape()
    # A — destructive toward G1 (short + loop cancel)
    L.add_edge(START, "A", delta=0.3, resistance=0.3)
    L.add_edge("A", "S1", delta=0.3, resistance=0.3)      # short (low v)
    L.add_edge("S1", "G1", delta=0.3, resistance=0.3)
    L.add_edge("A", "L1", delta=2.5, resistance=0.05)      # loop (high v)
    L.add_edge("L1", "L2", delta=2.5, resistance=0.05)
    L.add_edge("L2", "G1", delta=2.5, resistance=0.05)

    # A — rescue path to G2 (variable strength)
    L.add_edge("A", "R1", delta=rescue_delta, resistance=0.3)
    L.add_edge("R1", "G2", delta=rescue_delta, resistance=0.3)

    # B — coherent to G1
    L.add_edge(START, "B", delta=0.5, resistance=0.4)
    L.add_edge("B", "G1", delta=0.5, resistance=0.3)

    return L


def run_family_d():
    sep("Family D — Rescue Threshold (parametric)")
    
    deltas = [0.01, 0.05, 0.1, 0.2, 0.3, 0.5, 0.8, 1.0, 1.5, 2.0]
    print(f"\n  rescue_delta = strength of A→G2 rescue path")
    print(f"  Testing under G = {{G1, G2}}:")
    print(f"\n  {'δ_rescue':>9s}  {'Winner':>6s}  {'P(A)':>6s}  {'P(B)':>6s}  "
          f"{'I(A)':>8s}  {'I(B)':>8s}  {'Gap':>6s}  {'Rescued?':>8s}")
    print(f"  {'-'*9}  {'-'*6}  {'-'*6}  {'-'*6}  {'-'*8}  {'-'*8}  {'-'*6}  {'-'*8}")

    # Also check single-goal baseline
    print(f"\n  Baseline: G = {{G1}} only (A should always lose)")
    for d in [0.3, 1.0]:
        L = build_family_d(d)
        ctrl = E0Controller(L, evaluate)
        report = analyze_controller_state(
            ctrl, START, horizon_edges=5, geometry="goal_reaching", goals={"G1"}
        )
        m = report_metrics(report)
        print(f"    δ={d:.2f}: winner={m['winner']}, P(A)={m['probs'].get('A',0):.3f}, "
              f"P(B)={m['probs'].get('B',0):.3f}")

    print(f"\n  Multi-goal sweep: G = {{G1, G2}}")
    results = []
    crossover = None
    prev_winner = None
    for d in deltas:
        L = build_family_d(d)
        ctrl = E0Controller(L, evaluate)
        report = analyze_controller_state(
            ctrl, START, horizon_edges=5, geometry="goal_reaching", goals={"G1", "G2"}
        )
        m = report_metrics(report)
        results.append((d, m))
        pa = m["probs"].get("A", 0)
        pb = m["probs"].get("B", 0)
        ia = m["intensities"].get("A", 0)
        ib = m["intensities"].get("B", 0)
        rescued = m["winner"] == "A"
        if prev_winner == "B" and m["winner"] == "A" and crossover is None:
            crossover = d
        prev_winner = m["winner"]
        print(f"  {d:9.2f}  {m['winner']:>6s}  {pa:6.3f}  {pb:6.3f}  "
              f"{ia:8.5f}  {ib:8.5f}  {pa-pb:+6.3f}  {'YES' if rescued else 'no':>8s}")

    if crossover is not None:
        print(f"\n  → Rescue crossover at δ_rescue ≈ {crossover:.2f}")
    else:
        a_winners = [d for d, m in results if m["winner"] == "A"]
        if a_winners:
            print(f"\n  → A wins from δ_rescue={min(a_winners):.2f}")
        else:
            print(f"\n  → A never rescued (B dominates throughout)")

    return results


# ── Family E: Ranking Sharpness ──────────────────────────────

def build_family_e(n_goals: int) -> Landscape:
    """
    Uniform star: START → {A, B, C}, each connecting to multiple goals.
    As n_goals grows, paths multiply, testing selectivity preservation.
    """
    L = Landscape()
    actions = ["A", "B", "C"]
    for act in actions:
        # Each action gets a dedicated entry edge
        L.add_edge(START, act, delta=0.4 + 0.1 * ord(act[0]),
                   resistance=0.3)

    # Create n_goals goals, distributing paths unevenly
    for i in range(n_goals):
        g = f"G{i+1}"
        # A gets paths to all goals (strong)
        L.add_edge("A", f"A_M{i}", delta=0.5, resistance=0.25)
        L.add_edge(f"A_M{i}", g, delta=0.4, resistance=0.3)
        # B gets paths to even-numbered goals (moderate)
        if i % 2 == 0:
            L.add_edge("B", f"B_M{i}", delta=0.3, resistance=0.4)
            L.add_edge(f"B_M{i}", g, delta=0.3, resistance=0.4)
        # C gets paths to every 3rd goal (weak)
        if i % 3 == 0:
            L.add_edge("C", f"C_M{i}", delta=0.2, resistance=0.5)
            L.add_edge(f"C_M{i}", g, delta=0.2, resistance=0.5)

    return L


def run_family_e():
    sep("Family E — Ranking Sharpness")

    print(f"\n  {'|G|':>4s}  {'Winner':>6s}  {'P(A)':>6s}  {'P(B)':>6s}  "
          f"{'P(C)':>6s}  {'Top1-P':>7s}  {'Gap':>6s}  {'Entropy':>7s}  "
          f"{'Paths_A':>7s}  {'Paths_B':>7s}  {'Paths_C':>7s}")
    print(f"  {'-'*4}  {'-'*6}  {'-'*6}  {'-'*6}  {'-'*6}  {'-'*7}  {'-'*6}  "
          f"{'-'*7}  {'-'*7}  {'-'*7}  {'-'*7}")

    results = []
    for n in range(1, 9):
        L = build_family_e(n)
        ctrl = E0Controller(L, evaluate)
        goals = {f"G{i+1}" for i in range(n)}
        report = analyze_controller_state(
            ctrl, START, horizon_edges=5, geometry="goal_reaching", goals=goals
        )
        m = report_metrics(report)
        results.append((n, m))
        pa = m["probs"].get("A", 0)
        pb = m["probs"].get("B", 0)
        pc = m["probs"].get("C", 0)
        pca = m["path_counts"].get("A", 0)
        pcb = m["path_counts"].get("B", 0)
        pcc = m["path_counts"].get("C", 0)
        print(f"  {n:4d}  {m['winner']:>6s}  {pa:6.3f}  {pb:6.3f}  {pc:6.3f}  "
              f"{m['top1_prob']:7.3f}  {m['top_gap']:6.3f}  {m['entropy']:7.3f}  "
              f"{pca:7d}  {pcb:7d}  {pcc:7d}")

    # Selectivity assessment
    first_ent = results[0][1]["entropy"]
    last_ent = results[-1][1]["entropy"]
    first_gap = results[0][1]["top_gap"]
    last_gap = results[-1][1]["top_gap"]
    print(f"\n  Entropy:  |G|=1 → {first_ent:.3f},  |G|={len(results)} → {last_ent:.3f}  "
          f"(Δ={last_ent - first_ent:+.3f})")
    print(f"  Top-gap:  |G|=1 → {first_gap:.3f},  |G|={len(results)} → {last_gap:.3f}  "
          f"(Δ={last_gap - first_gap:+.3f})")

    if last_gap < 0.05:
        print(f"  ⚠ SATURATION: Top-gap < 0.05 — selectivity may be degrading")
    elif last_gap > first_gap * 0.5:
        print(f"  ✓ SHARP: Selectivity preserved (top-gap > 50% of baseline)")
    else:
        print(f"  ~ MODERATE: Selectivity reduced but not collapsed")

    return results


# ── Main ─────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  G5 EDGE CASE SUITE — Exploration")
    print("  ref: docs/research/E0_G5_EDGE_CASE_SUITE_v1.md")
    print("=" * 60)

    results_a = run_family_a()
    results_b = run_family_b()
    results_c = run_family_c()
    results_d = run_family_d()
    results_e = run_family_e()

    sep("SUMMARY")
    print("""
  Family A (Goal-Count):     Does selectivity degrade as |G| grows?
  Family B (Irrelevant):     Does adding irrelevant goals perturb the winner?
  Family C (Conflict):       How does G5 combine genuinely conflicting goals?
  Family D (Rescue):         At what threshold does rescue occur?
  Family E (Sharpness):      Is the ranking still sharp at |G|=8?
    """)
    print("=" * 60)
    print("  EXPLORATION COMPLETE")
    print("=" * 60)
