"""
E₀ Quantum Walk Demo (C304)
============================
Three-way comparison on the Gordian Trap landscape:

    1. Classical E₀ (U(1) greedy argmin) — deterministic baseline
    2. SU(2) Quantum Walk (argmax, geometric coin) — single-episode
    3. Historized Quantum Walk — 30 episodes, quantum→classical transition

The Gordian Trap
----------------
A landscape designed so that greedy tension-minimisation gets trapped.
The structurally optimal path (A1→A2→GOAL) has higher individual deltas
but lower total tension than the locally attractive trap (B1→B2→GOAL).

Greedy (U(1)): picks START→B1 (lower immediate tension) → B1→B2→GOAL.
Quantum Walk:  coin fidelity shifts weights → may prefer START→A1.
Historized:    after repeated successes on A1-path, walk converges there.

Usage
-----
    py -3 e0_controller/demo_quantum_walk.py
    py -3 e0_controller/demo_quantum_walk.py --verbose
    py -3 e0_controller/demo_quantum_walk.py --episodes 50
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import List, Optional

import numpy as np

# Make importable when run directly from the repo root
if __name__ == "__main__":
    sys.path.insert(0, ".")

from e0_controller.controller import E0Controller
from e0_controller.landscape import Landscape
from e0_controller.primitives import Edge, Outcome
from e0_controller.quantum_walk import compare_walks, QuantumWalk, COIN_MODES
from e0_controller.quantum_walk_historized import (
    HistorizedQuantumWalk,
    conviction,
    quantum_strength,
)
from e0_controller.spinor_connection import SPINOR_UP


# ── Landscape definition ──────────────────────────────────────────────────────

def gordian_trap() -> Landscape:
    """
    Gordian Trap landscape (from explore_gordian.py, confirmed SU(2) winner flip).

    Path A (optimal, higher individual deltas):
        START → A1 → A2 → GOAL   (total S_eff ≈ lower)

    Path B (greedy trap, lower first-step delta):
        START → B1 → B2 → GOAL   (first step looks better, total is worse)

    Lure path:
        A1 → L1 → L2 → L3 → GOAL  (high delta, dead lure)
    """
    L = Landscape()
    # Path A (structurally preferred)
    L.add_edge("START", "A1",  delta=0.3, resistance=0.3)
    L.add_edge("A1",    "A2",  delta=0.4, resistance=0.3)
    L.add_edge("A2",    "GOAL",delta=0.4, resistance=0.3)
    # Path B (greedy trap)
    L.add_edge("START", "B1",  delta=0.5, resistance=0.4)
    L.add_edge("B1",    "B2",  delta=0.3, resistance=0.35)
    L.add_edge("B2",    "GOAL",delta=0.3, resistance=0.30)
    # Lure (A1 exits to a costly dead-end)
    L.add_edge("A1",    "L1",  delta=2.0, resistance=0.05)
    L.add_edge("L1",    "L2",  delta=2.0, resistance=0.05)
    L.add_edge("L2",    "L3",  delta=2.0, resistance=0.05)
    L.add_edge("L3",    "GOAL",delta=2.0, resistance=0.05)
    return L


# ── Helpers ───────────────────────────────────────────────────────────────────

def _path_str(states: List[str]) -> str:
    return " → ".join(states)


def _tension_str(L: Landscape, path: List[str]) -> str:
    total = sum(L.effective_tension(path[i], path[i+1]) for i in range(len(path)-1))
    return f"S_eff={total:.4f}"


def _section(title: str) -> None:
    width = 60
    print()
    print("═" * width)
    print(f"  {title}")
    print("═" * width)


# ── Part 1: Classical E₀ ─────────────────────────────────────────────────────

def run_classical(L: Landscape, verbose: bool) -> List[str]:
    _section("Part 1 — Classical E₀ (U(1) greedy, argmin S_eff)")

    # E0Controller requires execute_fn as 2nd positional arg
    ctrl = E0Controller(L, lambda state, action: Outcome.SUCCESS)
    path: List[str] = ["START"]
    state = "START"
    for _ in range(10):
        if state == "GOAL":
            break
        neighbors = L.admissible_neighbors(state)
        if not neighbors:
            print("  Dead end — escalated")
            break
        # Greedy: argmin effective tension
        best = min(neighbors, key=lambda y: L.effective_tension(state, y))
        state = best
        path.append(state)

    print(f"  Path: {_path_str(path)}")
    print(f"  {_tension_str(L, path)}")
    if verbose:
        for i in range(len(path) - 1):
            s = L.effective_tension(path[i], path[i+1])
            print(f"    {path[i]:8s} → {path[i+1]:8s}  S_eff={s:.4f}")
    return path


# ── Part 2: Single-episode Quantum Walk (all coin modes) ─────────────────────

def run_single_quantum(L: Landscape, verbose: bool) -> dict:
    _section("Part 2 — SU(2) Quantum Walk (single episode, argmax)")

    comparison = compare_walks(L, "START", "GOAL", max_steps=20)
    paths = {}
    for mode in COIN_MODES:
        path = comparison.results[mode]
        reached = comparison.reached_goal[mode]
        n = comparison.step_counts[mode]
        status = "✓" if reached else f"stopped at {path[-1]}"
        print(f"  {mode:10s}  {_path_str(path):40s}  {_tension_str(L, path)}  steps={n}  {status}")
        paths[mode] = path
        if verbose and mode == "geometric":
            print(f"    Note: geometric coin uses full A₁,A₂,A₃ coupling from spinor_connection")
    return paths


# ── Part 3: Historized Quantum Walk — learning loop ──────────────────────────

def run_historized(L: Landscape, n_episodes: int, verbose: bool) -> None:
    _section(f"Part 3 — Historized Quantum Walk ({n_episodes} episodes)")

    # Oracle: SUCCESS if we're moving toward GOAL; FAILURE otherwise
    # Simplified: SUCCESS unless we entered the lure branch
    lure_states = {"L1", "L2", "L3"}
    def oracle(before: str, after: str) -> Outcome:
        if after in lure_states:
            return Outcome.FAILURE
        if after == "GOAL":
            return Outcome.SUCCESS
        return Outcome.PARTIAL

    # Statistics over episodes
    a_path_count = 0   # episodes that took A1 first step
    b_path_count = 0   # episodes that took B1 first step

    walk = HistorizedQuantumWalk(
        L, "START", coin_mode="geometric", select_mode="argmax", min_quantum=0.05
    )

    if verbose:
        print(f"  {'Ep':>4s}  {'Path':40s}  {'conviction(A1)':14s}  {'conviction(B1)':14s}")
        print("  " + "-" * 80)

    for ep in range(1, n_episodes + 1):
        walk.reset("START")
        results = walk.run_with_outcomes(oracle, goal="GOAL", max_steps=15)
        path = ["START"] + [s.state_after for s, _ in results]

        first_step = path[1] if len(path) > 1 else "?"
        if first_step == "A1":
            a_path_count += 1
        elif first_step == "B1":
            b_path_count += 1

        c_a1 = conviction(L, Edge("START", "A1"))
        c_b1 = conviction(L, Edge("START", "B1"))

        if verbose:
            print(f"  {ep:>4d}  {_path_str(path):40s}  {c_a1:14.4f}  {c_b1:14.4f}")

    # Final summary
    c_a1 = conviction(L, Edge("START", "A1"))
    c_b1 = conviction(L, Edge("START", "B1"))
    qs_a1 = quantum_strength(L, Edge("START", "A1"))
    qs_b1 = quantum_strength(L, Edge("START", "B1"))

    print()
    print(f"  After {n_episodes} episodes:")
    print(f"    A1 path chosen:  {a_path_count}/{n_episodes}")
    print(f"    B1 path chosen:  {b_path_count}/{n_episodes}")
    print()
    print(f"  Conviction:")
    print(f"    START→A1:  {c_a1:.4f}   quantum_strength={qs_a1:.4f}")
    print(f"    START→B1:  {c_b1:.4f}   quantum_strength={qs_b1:.4f}")
    print()
    print(f"  Quantum→Classical transition:")

    # Show quantum_strength for all edges on both paths
    a_path_edges = [Edge("START","A1"), Edge("A1","A2"), Edge("A2","GOAL")]
    b_path_edges = [Edge("START","B1"), Edge("B1","B2"), Edge("B2","GOAL")]
    for edges, label in [(a_path_edges, "A-path"), (b_path_edges, "B-path")]:
        print(f"    {label}:")
        for e in edges:
            qs = quantum_strength(L, e)
            c  = conviction(L, e)
            bar_q = "█" * int(qs * 20) + "░" * (20 - int(qs * 20))
            print(f"      {e.source:6s}→{e.target:6s}  qs={qs:.3f}  [{bar_q}]  conv={c:.3f}")


# ── Part 4: Spinor trajectory (single geometric walk) ────────────────────────

def run_spinor_trajectory(L: Landscape, verbose: bool) -> None:
    if not verbose:
        return
    _section("Part 4 — Spinor Trajectory (geometric coin, argmax)")

    walk = QuantumWalk(L, "START", coin_mode="geometric", select_mode="argmax")
    walk.run(goal="GOAL", max_steps=15)

    print(f"  {'Step':>4s}  {'From':8s} → {'To':8s}  "
          f"{'|ψ_before[0]|':14s}  {'fidelity':10s}  {'p(chosen)':10s}")
    for s in walk.history:
        psi = s.spinor_before
        print(
            f"  {s.step_index:>4d}  {s.state_before:8s} → {s.state_after:8s}  "
            f"  {abs(psi[0]):12.6f}    {s.fidelity:10.6f}    {s.probability:10.6f}"
        )


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="E₀ Quantum Walk Demo — Gordian Trap three-way comparison"
    )
    parser.add_argument("--verbose", action="store_true",
                        help="Print detailed per-step output")
    parser.add_argument("--episodes", type=int, default=30,
                        help="Number of historized walk episodes (default 30)")
    args = parser.parse_args()

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  E₀ QUANTUM WALK DEMO  (C304)                           ║")
    print("║  Gordian Trap: Classical vs Quantum vs Historized        ║")
    print("╚══════════════════════════════════════════════════════════╝")

    L = gordian_trap()

    # Effective tensions summary
    print()
    print("  Landscape: Gordian Trap")
    for (x, y) in [("START","A1"),("START","B1"),("A1","A2"),("B1","B2"),("A2","GOAL"),("B2","GOAL")]:
        s = L.effective_tension(x, y)
        print(f"    {x:6s}→{y:6s}  S_eff={s:.4f}")
    a_total = sum(L.effective_tension(*e) for e in [("START","A1"),("A1","A2"),("A2","GOAL")])
    b_total = sum(L.effective_tension(*e) for e in [("START","B1"),("B1","B2"),("B2","GOAL")])
    print(f"\n    Path A total: {a_total:.4f}   Path B total: {b_total:.4f}")
    print(f"    {'Path A is globally optimal ✓' if a_total < b_total else 'Path B is globally optimal ✓'}")

    classical_path  = run_classical(L, args.verbose)
    quantum_paths   = run_single_quantum(L, args.verbose)
    run_historized(L, args.episodes, args.verbose)
    run_spinor_trajectory(L, args.verbose)

    # Final verdict
    _section("Summary")
    print(f"  Classical (greedy):      {_path_str(classical_path)}")
    print(f"  Quantum (geometric):     {_path_str(quantum_paths.get('geometric', ['?']))}")
    print()
    print("  Key insight:")
    print("    Classical → locally greedy, often trapped by first-step tension.")
    print("    Quantum Walk → coin-fidelity can override tension, escaping traps.")
    print("    Historized → quantumness fades on confirmed paths (quantum→classical).")
    print("    Conflicted edges stay quantum; virgin edges are fully quantum.")
    print()
    print("  Theorem (classical limit):")
    print("    coin_mode='identity' → f=1 ∀e → Born weight ∝ exp(-S_eff)")
    print("    Historized with full conviction → same classical result.")
    print("    Knowledge consolidation is encoded in the coin scale, not the tension.")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
