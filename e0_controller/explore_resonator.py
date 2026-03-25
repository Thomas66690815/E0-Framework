#!/usr/bin/env python3
"""
E₀ Resonator Exploration — Minimal Resonator Test
=====================================================
Implements the experimental protocol from E0_MINIMAL_RESONATOR_TEST_DESIGN_v0.

Domain:
    3-node loop: A → B → C → A, plus leakage C → OUT.
    Paths: loop family {A→B→C→A, A→B→C→A→B→C→A, ...}
           leakage     {A→B→C→OUT}

Questions:
    R1. Does the loop family reproduce Ψ ≈ const across cycles?
    R2. Does I_coh(t) remain bounded away from zero?
    R3. Is leakage I_out(t) < I_coh(t) in stable regime?
    R4. Is ΔI_coh/Δt not strongly negative under historization?

Regimes:
    M1 — low loop support, strong leakage (expect: transient)
    M2 — balanced (expect: borderline)
    M3 — reinforced loop, weak leakage (expect: resonator candidate)

Historization modes:
    H0 — frozen (pure wave baseline)
    H1 — live updates (memory-reinforced)

Controls:
    C1 — acyclic (remove closing edge C→A)
    C2 — dephased (same topology, high resistance destroys coherence)

Phase 4 research — results feed into docs, NOT into controller.
"""

import math
import sys
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from e0_controller.landscape import Landscape
from e0_controller.primitives import Edge, Outcome
from e0_controller.connection import omega, theta, holonomy
from e0_controller.wavepath import (
    psi, sum_paths, intensity, path_tension, path_analysis,
)
from e0_controller.spinor_connection import (
    spinor_intensity, spinor_sum_paths, su2_holonomy,
    compare_u1_su2, is_identity, is_minus_identity, is_su2,
    spinor_geometric_intensity, su2_geometric_path_transport,
    IDENTITY,
)

WIDTH = 70


def header(title: str):
    print(f"\n{'=' * WIDTH}")
    print(f"  {title}")
    print(f"{'=' * WIDTH}")


def subheader(title: str):
    print(f"\n── {title} {'─' * max(1, WIDTH - len(title) - 4)}")


# ═══════════════════════════════════════════════════════════════════
# Domain Builders
# ═══════════════════════════════════════════════════════════════════

def build_resonator_domain(
    loop_delta: float = 1.0,
    loop_R: float = 0.2,
    leak_delta: float = 0.5,
    leak_R: float = 0.5,
    close_loop: bool = True,
    dephase: bool = False,
) -> Landscape:
    """
    Minimal 3-node loop + leakage edge.

        A → B → C → A   (closed loop, if close_loop=True)
                 ↓
                OUT

    Parameters control the regime:
        loop_delta/R: burden on loop edges (low R = easy loop)
        leak_delta/R: burden on leakage edge (high R = weak leakage)
        close_loop: if False → acyclic control (C1)
        dephase: if True → high R on one loop edge to kill coherence (C2)
    """
    L = Landscape()
    L.add_edge("A", "B", delta=loop_delta, resistance=loop_R)
    L.add_edge("B", "C", delta=loop_delta, resistance=loop_R)

    if dephase:
        # C2: same topology but one edge has high resistance → kills phase coherence
        L.add_edge("C", "A", delta=loop_delta, resistance=5.0)
    elif close_loop:
        L.add_edge("C", "A", delta=loop_delta, resistance=loop_R)

    # Leakage path
    L.add_edge("C", "OUT", delta=leak_delta, resistance=leak_R)

    return L


# Three canonical regimes from the design doc
def regime_M1() -> Landscape:
    """M1: Low loop support, strong leakage → transient."""
    return build_resonator_domain(loop_delta=1.0, loop_R=0.8,
                                  leak_delta=2.0, leak_R=0.1)

def regime_M2() -> Landscape:
    """M2: Balanced → borderline."""
    return build_resonator_domain(loop_delta=1.0, loop_R=0.3,
                                  leak_delta=0.5, leak_R=0.5)

def regime_M3() -> Landscape:
    """M3: Reinforced loop, weak leakage → resonator candidate."""
    return build_resonator_domain(loop_delta=0.5, loop_R=0.1,
                                  leak_delta=0.3, leak_R=1.5)

def control_C1() -> Landscape:
    """C1: Acyclic — remove loop-closing edge."""
    return build_resonator_domain(close_loop=False)

def control_C2() -> Landscape:
    """C2: Dephased — same topology, high R kills coherence."""
    return build_resonator_domain(dephase=True)


# ═══════════════════════════════════════════════════════════════════
# Path Families
# ═══════════════════════════════════════════════════════════════════

def loop_paths(n_cycles: int) -> List[List[str]]:
    """
    Generate loop path family for n full cycles.

    Cycle 1: A → B → C → A
    Cycle 2: A → B → C → A → B → C → A
    ...

    Returns a list of paths, one per cycle count (1..n_cycles).
    """
    paths = []
    for k in range(1, n_cycles + 1):
        path = ["A"]
        for _ in range(k):
            path.extend(["B", "C", "A"])
        paths.append(path)
    return paths


def leakage_path() -> List[str]:
    """Single leakage path: A → B → C → OUT."""
    return ["A", "B", "C", "OUT"]


# ═══════════════════════════════════════════════════════════════════
# Measurement Protocol
# ═══════════════════════════════════════════════════════════════════

@dataclass
class CycleMetrics:
    """Measurements for one cycle count."""
    cycle: int
    # §4.1 Coherent intensity
    I_coh: float
    # §4.2 Incoherent reference
    I_inc: float
    # §4.3 Coherence ratio
    R_coh: float
    # §4.4 Local historization density
    H_loop: float
    # §4.5 Leakage intensity
    I_out: float
    # Phase info
    theta_loop: float
    # SU(2) info
    I_coh_su2: float = 0.0
    I_coh_geo: float = 0.0


def measure_cycle(L: Landscape, n_cycles: int) -> CycleMetrics:
    """
    Full measurement for a given cycle depth on the current landscape state.
    """
    # Loop paths up to this cycle count
    paths = loop_paths(n_cycles)
    leak = leakage_path()

    # §4.1: I_coh = |Σ Ψ_loop|²
    psi_total = sum_paths(L, paths)
    I_coh = abs(psi_total) ** 2

    # §4.2: I_inc = Σ |Ψ(p)|²
    I_inc = sum(abs(psi(L, p)) ** 2 for p in paths)

    # §4.3: R_coh
    R_coh = I_coh / I_inc if I_inc > 1e-30 else 0.0

    # §4.4: H_loop (sum of |δ_H| on loop edges)
    loop_edges = [Edge("A", "B"), Edge("B", "C"), Edge("C", "A")]
    H_loop = sum(abs(L.historization.delta_H(e)) for e in loop_edges
                 if L.difference(e.source, e.target) is not None)

    # §4.5: I_out
    if L.difference("C", "OUT") is not None:
        psi_out = psi(L, leak)
        I_out = abs(psi_out) ** 2
    else:
        I_out = 0.0

    # Phase: total theta for one cycle
    one_cycle = ["A", "B", "C", "A"]
    if L.difference("C", "A") is not None:
        theta_loop = theta(L, one_cycle)
    else:
        theta_loop = 0.0

    # SU(2) coherent intensities
    I_coh_su2 = spinor_intensity(L, paths)
    I_coh_geo = spinor_geometric_intensity(L, paths)

    return CycleMetrics(
        cycle=n_cycles,
        I_coh=I_coh, I_inc=I_inc, R_coh=R_coh,
        H_loop=H_loop, I_out=I_out, theta_loop=theta_loop,
        I_coh_su2=I_coh_su2, I_coh_geo=I_coh_geo,
    )


def apply_loop_historization(L: Landscape, outcome: Outcome = Outcome.SUCCESS):
    """
    Simulate one full loop traversal's historization effect.

    Updates A→B, B→C, C→A with the given outcome.
    """
    for src, tgt in [("A", "B"), ("B", "C"), ("C", "A")]:
        edge = Edge(src, tgt)
        if L.difference(src, tgt) is not None:
            L.historization.update(edge, outcome)


# ═══════════════════════════════════════════════════════════════════
# Stability Classification
# ═══════════════════════════════════════════════════════════════════

def classify_resonator(metrics_history: List[CycleMetrics]) -> str:
    """
    Classify outcome based on R1-R4 criteria:
        DECAY      — I_coh effectively zero or no loop support
        METASTABLE — some coherence but leakage-dominated or oscillatory
        RESONATOR  — I_coh bounded away from zero, R_coh stable, leakage non-dominant
    """
    if len(metrics_history) < 3:
        return "INSUFFICIENT_DATA"

    intensities = [m.I_coh for m in metrics_history]

    # R2: Absolute minimum — below this is noise, not resonance
    I_ABS_MIN = 0.001
    if max(intensities) < I_ABS_MIN:
        return "DECAY"

    # Late-phase analysis (second half of history)
    n = len(metrics_history)
    late = metrics_history[n // 2:]

    # Late R_coh average
    avg_late_R = np.mean([m.R_coh for m in late])

    # R3: Leakage dominance fraction in late cycles
    leak_frac = sum(1 for m in late if m.I_out > m.I_coh) / len(late)

    # Final intensity relative to peak (envelope decay)
    peak_I = max(intensities)
    final_ratio = intensities[-1] / peak_I if peak_I > 1e-30 else 0.0

    # RESONATOR: stable coherence, bounded intensity, leakage non-dominant
    if avg_late_R > 0.3 and leak_frac < 0.75 and final_ratio > 0.05:
        return "RESONATOR"
    # METASTABLE: some coherence present but not stable
    elif avg_late_R > 0.05 or final_ratio > 0.1:
        return "METASTABLE"
    else:
        return "DECAY"


# ═══════════════════════════════════════════════════════════════════
# Exploration Runs
# ═══════════════════════════════════════════════════════════════════

def run_regime(name: str, L: Landscape, max_cycles: int = 8,
               n_hist_rounds: int = 0) -> List[CycleMetrics]:
    """
    Run measurement protocol on a regime.

    n_hist_rounds: number of historization updates to apply before measuring.
                   0 = H0 (frozen), >0 = H1 (live).
    """
    mode = "H0 (frozen)" if n_hist_rounds == 0 else f"H1 ({n_hist_rounds} rounds)"
    subheader(f"{name} — {mode}")

    # Apply historization rounds
    for _ in range(n_hist_rounds):
        apply_loop_historization(L)

    # Measure at each cycle depth
    history = []
    print(f"  {'cyc':>3s}  {'I_coh':>10s}  {'I_inc':>10s}  {'R_coh':>8s}  "
          f"{'I_out':>10s}  {'H_loop':>8s}  {'Θ_loop':>8s}  "
          f"{'I_su2':>10s}  {'I_geo':>10s}")
    for k in range(1, max_cycles + 1):
        m = measure_cycle(L, k)
        history.append(m)
        print(f"  {k:3d}  {m.I_coh:10.6f}  {m.I_inc:10.6f}  {m.R_coh:8.4f}  "
              f"{m.I_out:10.6f}  {m.H_loop:8.5f}  {m.theta_loop:+8.4f}  "
              f"{m.I_coh_su2:10.6f}  {m.I_coh_geo:10.6f}")

    label = classify_resonator(history)
    print(f"\n  Classification: {label}")

    # R1: Reproduction check
    if len(history) >= 3:
        psi_vals = [sum_paths(L, loop_paths(k+1)) for k in range(min(5, max_cycles))]
        phases = [math.degrees(math.atan2(p.imag, p.real)) for p in psi_vals if abs(p) > 1e-15]
        if phases:
            print(f"  Ψ_total phases: {', '.join(f'{p:.1f}°' for p in phases)}")

    # R3: Leakage dominance check
    if history:
        leak_dominant = sum(1 for m in history if m.I_out > m.I_coh)
        print(f"  Leakage > Coherent in {leak_dominant}/{len(history)} cycles")

    return history


def run_single_regime_full(name: str, builder, max_cycles: int = 8):
    """Run a regime in both H0 and H1 modes."""
    header(f"Regime {name}")

    # Topology info
    L_info = builder()
    print(f"  Nodes: {sorted(L_info.states)}")
    print(f"  Edges: {[f'{e.source}→{e.target}' for e in L_info.edges]}")

    # Phase info
    one_cycle = ["A", "B", "C", "A"]
    if L_info.difference("C", "A") is not None:
        theta_1 = theta(L_info, one_cycle)
        print(f"  Θ(1 cycle) = {theta_1:.6f} rad ({math.degrees(theta_1):.2f}°)")

        # SU(2) holonomy
        U_cycle = su2_holonomy(L_info, one_cycle)
        U_geo = su2_geometric_path_transport(L_info, one_cycle)
        print(f"  SU(2)-min tr(U) = {np.trace(U_cycle):.4f}  SU(2)={is_su2(U_cycle)}")
        print(f"  SU(2)-geo tr(U) = {np.trace(U_geo):.4f}  SU(2)={is_su2(U_geo)}")
    else:
        print(f"  [No loop closure — acyclic control]")

    # Connection info
    for e in L_info.edges:
        w = omega(L_info, e.source, e.target)
        s = L_info.effective_tension(e.source, e.target)
        print(f"    {e.source}→{e.target}: ω={w:+.5f}, S_eff={s:.4f}")

    # H0: frozen historization
    L_H0 = builder()
    h0 = run_regime(f"{name}/H0", L_H0, max_cycles)

    # H1: live historization (5, 10, 20 rounds)
    results = {"H0": h0}
    for n_rounds in [5, 10, 20]:
        L_H1 = builder()
        h1 = run_regime(f"{name}/H1", L_H1, max_cycles, n_hist_rounds=n_rounds)
        results[f"H1_{n_rounds}"] = h1

    return results


# ═══════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════

def run_summary(all_results: Dict[str, Dict]):
    header("SUMMARY — Resonator Classification")

    print(f"\n  {'Regime':<12s}  {'Mode':<10s}  {'Class':<12s}  "
          f"{'I_coh(1)':>10s}  {'I_coh(8)':>10s}  {'R_coh(8)':>8s}")
    for regime_name, modes in all_results.items():
        for mode, history in modes.items():
            if history:
                label = classify_resonator(history)
                I1 = history[0].I_coh
                I8 = history[-1].I_coh
                R8 = history[-1].R_coh
                print(f"  {regime_name:<12s}  {mode:<10s}  {label:<12s}  "
                      f"{I1:10.6f}  {I8:10.6f}  {R8:8.4f}")

    print(f"\n  Stability criteria:")
    print(f"    R1 — Recurrent reconstruction: Ψ_loop(t+T) ≈ Ψ_loop(t)")
    print(f"    R2 — Bounded coherent support: I_coh ≥ I_min > 0")
    print(f"    R3 — Non-dominant leakage: I_out < I_coh")
    print(f"    R4 — Historization balance: ΔI_coh/Δt not strongly negative")


# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    all_results = {}

    # Main regimes
    all_results["M1"] = run_single_regime_full("M1 (transient)", regime_M1)
    all_results["M2"] = run_single_regime_full("M2 (balanced)", regime_M2)
    all_results["M3"] = run_single_regime_full("M3 (reinforced)", regime_M3)

    # Negative controls
    all_results["C1"] = run_single_regime_full("C1 (acyclic)", control_C1)
    all_results["C2"] = run_single_regime_full("C2 (dephased)", control_C2)

    run_summary(all_results)
