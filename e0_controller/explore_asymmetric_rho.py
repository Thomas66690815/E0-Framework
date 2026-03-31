"""
Asymmetric ρ Experiment (C79)
===============================
Test whether asymmetric decay (ρ_F > ρ_S) — where failures are remembered
longer than successes — improves learning in stochastic environments.

Motivation (user insight): "Aus Fehlern lernt man mehr als aus den richtigen
Entscheidungen, denn sie zeigen einem viel mehr als nur den Fehler selbst
sondern zeigen viele andere Wege die man ab jetzt gehen kann anstatt nur
den einen der bisher funktioniert hat."

Formally: when ρ_F > ρ_S, failure traces decay slower → dead ends stay
"hot" longer → controller avoids re-exploring them → fewer wasted steps.

Part 1: Symmetric vs asymmetric ρ on branching corridors (cold start).
         Does asymmetric ρ alone reduce steps?

Part 2: Asymmetric ρ + transfer vs symmetric ρ + transfer.
         Does asymmetric ρ make transfer redundant?

Part 3: ρ_F sensitivity sweep. How much asymmetry is optimal?

Stationarity note: high ρ_F is safe because DEAD_END escalation (K12)
and exploration policy already re-examine failed paths when needed.

Usage:
  py -3 -m e0_controller.explore_asymmetric_rho
"""

from __future__ import annotations

import random
from typing import List, Tuple

from e0_controller.primitives import Edge, Outcome
from e0_controller.controller import E0Controller
from e0_controller.explore_transfer_learning import (
    build_branching_corridor,
    run_stochastic_episodes,
    inject_strategy,
    EpisodeRecord,
    SEED_STRENGTH,
)


# ══════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════

N_TRIALS = 30
N_EPS = 30
N_SOURCE_EPS = 15

# Corridor configs
CORRIDORS = [
    (5, 4, "5L×4D"),
    (8, 3, "8L×3D"),
]

# Asymmetric ρ configs
RHO_SYMMETRIC = 0.9
RHO_S_ASYM = 0.85       # success decays faster (forget successes sooner)
RHO_F_ASYM = 0.97       # failure decays slower (remember failures longer)


# ══════════════════════════════════════════════
# Part 1: Symmetric vs Asymmetric (cold start)
# ══════════════════════════════════════════════

def run_cold_comparison(n_levels: int, n_dead_ends: int, label: str):
    """Compare symmetric ρ=0.9 vs asymmetric ρ_S=0.85/ρ_F=0.97 (cold start)."""

    sym_curves = []
    asym_curves = []

    for trial in range(N_TRIALS):
        # Symmetric ρ=0.9
        spec = build_branching_corridor(
            n_levels, n_dead_ends, rng=random.Random(2000 + trial))
        # Default rho=0.9, rho_s=None, rho_f=None → symmetric
        sym_eps, _ = run_stochastic_episodes(
            spec, N_EPS, random.Random(3000 + trial))
        sym_curves.append([e.steps for e in sym_eps])

        # Asymmetric ρ_S=0.85, ρ_F=0.97
        spec2 = build_branching_corridor(
            n_levels, n_dead_ends, rng=random.Random(2000 + trial))
        spec2.landscape.historization.rho_s = RHO_S_ASYM
        spec2.landscape.historization.rho_f = RHO_F_ASYM
        asym_eps, _ = run_stochastic_episodes(
            spec2, N_EPS, random.Random(3000 + trial))
        asym_curves.append([e.steps for e in asym_eps])

    # Average curves
    avg_sym = [sum(sym_curves[t][ep] for t in range(N_TRIALS)) / N_TRIALS
               for ep in range(N_EPS)]
    avg_asym = [sum(asym_curves[t][ep] for t in range(N_TRIALS)) / N_TRIALS
                for ep in range(N_EPS)]

    print(f"\n─── {label} (happy path: {n_levels} steps) ───\n")
    print(f"    {'Ep':>3}  {'Sym μ':>7}  {'Asym μ':>7}  {'Δ':>7}  {'Note'}")
    print(f"    {'---':>3}  {'------':>7}  {'------':>7}  {'-----':>7}")
    for ep in range(N_EPS):
        delta = avg_sym[ep] - avg_asym[ep]
        note = ""
        if delta > 0.5:
            note = "◀ asym faster"
        elif delta < -0.5:
            note = "◀ sym faster"
        print(f"    {ep:>3}  {avg_sym[ep]:>7.1f}  {avg_asym[ep]:>7.1f}  "
              f"{delta:>+7.1f}  {note}")

    sym_mean = sum(avg_sym) / len(avg_sym)
    asym_mean = sum(avg_asym) / len(avg_asym)
    speedup = sym_mean / asym_mean if asym_mean > 0 else 0.0

    sym_first5 = sum(avg_sym[:5]) / 5
    asym_first5 = sum(avg_asym[:5]) / 5
    sym_last5 = sum(avg_sym[-5:]) / 5
    asym_last5 = sum(avg_asym[-5:]) / 5

    print(f"\n    Overall:      sym={sym_mean:.1f}  asym={asym_mean:.1f}  "
          f"speedup={speedup:.2f}×")
    print(f"    First 5 eps:  sym={sym_first5:.1f}  asym={asym_first5:.1f}  "
          f"speedup={sym_first5 / asym_first5:.2f}×" if asym_first5 > 0 else "")
    print(f"    Last 5 eps:   sym={sym_last5:.1f}   asym={asym_last5:.1f}   "
          f"speedup={sym_last5 / asym_last5:.2f}×" if asym_last5 > 0 else "")

    asym_wins = sum(1 for ep in range(N_EPS) if avg_asym[ep] < avg_sym[ep] - 0.5)
    sym_wins = sum(1 for ep in range(N_EPS) if avg_sym[ep] < avg_asym[ep] - 0.5)
    draws = N_EPS - asym_wins - sym_wins
    print(f"    Episodes:     asym wins {asym_wins}, sym wins {sym_wins}, "
          f"draws {draws} (of {N_EPS})")

    return sym_mean, asym_mean, speedup


# ══════════════════════════════════════════════
# Part 2: Asymmetric ρ + Transfer vs Symmetric ρ + Transfer
# ══════════════════════════════════════════════

def run_transfer_comparison(n_levels: int, n_dead_ends: int, label: str):
    """4-way comparison: sym-cold, sym-warm, asym-cold, asym-warm.

    Key question: does asym-cold match/beat sym-warm?
    If yes → asymmetric ρ makes transfer redundant.
    """
    sym_cold_curves = []
    sym_warm_curves = []
    asym_cold_curves = []
    asym_warm_curves = []

    for trial in range(N_TRIALS):
        seed_base = 6000 + trial

        # ── Symmetric cold ──
        spec = build_branching_corridor(
            n_levels, n_dead_ends, rng=random.Random(seed_base))
        eps, _ = run_stochastic_episodes(spec, N_EPS, random.Random(seed_base + 1000))
        sym_cold_curves.append([e.steps for e in eps])

        # ── Symmetric warm (with transfer) ──
        source_spec = build_branching_corridor(
            n_levels, n_dead_ends, rng=random.Random(seed_base))
        _, source_ctrl = run_stochastic_episodes(
            source_spec, N_SOURCE_EPS, random.Random(seed_base + 2000))
        strategy = source_ctrl.landscape.historization.strategy_profile()

        warm_spec = build_branching_corridor(
            n_levels, n_dead_ends, rng=random.Random(seed_base))
        inject_strategy(warm_spec.landscape.historization, strategy)
        eps, _ = run_stochastic_episodes(warm_spec, N_EPS, random.Random(seed_base + 1000))
        sym_warm_curves.append([e.steps for e in eps])

        # ── Asymmetric cold ──
        spec2 = build_branching_corridor(
            n_levels, n_dead_ends, rng=random.Random(seed_base))
        spec2.landscape.historization.rho_s = RHO_S_ASYM
        spec2.landscape.historization.rho_f = RHO_F_ASYM
        eps, _ = run_stochastic_episodes(spec2, N_EPS, random.Random(seed_base + 1000))
        asym_cold_curves.append([e.steps for e in eps])

        # ── Asymmetric warm (with transfer) ──
        source_spec2 = build_branching_corridor(
            n_levels, n_dead_ends, rng=random.Random(seed_base))
        source_spec2.landscape.historization.rho_s = RHO_S_ASYM
        source_spec2.landscape.historization.rho_f = RHO_F_ASYM
        _, source_ctrl2 = run_stochastic_episodes(
            source_spec2, N_SOURCE_EPS, random.Random(seed_base + 2000))
        strategy2 = source_ctrl2.landscape.historization.strategy_profile()

        warm_spec2 = build_branching_corridor(
            n_levels, n_dead_ends, rng=random.Random(seed_base))
        warm_spec2.landscape.historization.rho_s = RHO_S_ASYM
        warm_spec2.landscape.historization.rho_f = RHO_F_ASYM
        inject_strategy(warm_spec2.landscape.historization, strategy2)
        eps, _ = run_stochastic_episodes(warm_spec2, N_EPS, random.Random(seed_base + 1000))
        asym_warm_curves.append([e.steps for e in eps])

    # Average
    def avg_curve(curves):
        return [sum(curves[t][ep] for t in range(N_TRIALS)) / N_TRIALS
                for ep in range(N_EPS)]

    avg_sc = avg_curve(sym_cold_curves)
    avg_sw = avg_curve(sym_warm_curves)
    avg_ac = avg_curve(asym_cold_curves)
    avg_aw = avg_curve(asym_warm_curves)

    print(f"\n─── {label} — 4-way comparison ───\n")
    print(f"    {'Ep':>3}  {'Sym-C':>7}  {'Sym-W':>7}  {'Asym-C':>7}  {'Asym-W':>7}  {'Best'}")
    print(f"    {'---':>3}  {'-----':>7}  {'-----':>7}  {'------':>7}  {'------':>7}")
    for ep in range(N_EPS):
        vals = [avg_sc[ep], avg_sw[ep], avg_ac[ep], avg_aw[ep]]
        labels = ["Sym-C", "Sym-W", "Asym-C", "Asym-W"]
        best_idx = vals.index(min(vals))
        best = labels[best_idx]
        print(f"    {ep:>3}  {avg_sc[ep]:>7.1f}  {avg_sw[ep]:>7.1f}  "
              f"{avg_ac[ep]:>7.1f}  {avg_aw[ep]:>7.1f}  {best}")

    sc_mean = sum(avg_sc) / len(avg_sc)
    sw_mean = sum(avg_sw) / len(avg_sw)
    ac_mean = sum(avg_ac) / len(avg_ac)
    aw_mean = sum(avg_aw) / len(avg_aw)

    print(f"\n    Means:  Sym-Cold={sc_mean:.1f}  Sym-Warm={sw_mean:.1f}  "
          f"Asym-Cold={ac_mean:.1f}  Asym-Warm={aw_mean:.1f}")
    print(f"\n    Asym-cold vs Sym-cold:  {sc_mean/ac_mean:.2f}× speedup"
          if ac_mean > 0 else "")
    print(f"    Asym-cold vs Sym-warm:  {sw_mean/ac_mean:.2f}× "
          f"({'asym-cold BEATS transfer' if ac_mean <= sw_mean else 'transfer still helps'})"
          if ac_mean > 0 else "")
    print(f"    Asym-warm vs Sym-warm:  {sw_mean/aw_mean:.2f}× speedup"
          if aw_mean > 0 else "")
    print(f"    Asym-warm vs Asym-cold: {ac_mean/aw_mean:.2f}× speedup"
          if aw_mean > 0 else "")


# ══════════════════════════════════════════════
# Part 3: ρ_F Sensitivity Sweep
# ══════════════════════════════════════════════

def run_rho_f_sweep(n_levels: int = 8, n_dead_ends: int = 3):
    """Sweep ρ_F from 0.85 to 0.99 with fixed ρ_S=0.85."""

    rho_s_fixed = 0.85
    rho_f_values = [0.85, 0.90, 0.93, 0.95, 0.97, 0.99]

    print(f"\n─── ρ_F Sweep (ρ_S={rho_s_fixed} fixed, {n_levels}L×{n_dead_ends}D) ───\n")
    print(f"    {'ρ_F':>5}  {'Mean Steps':>10}  {'First5':>7}  {'Last5':>7}  {'vs ρ_F=ρ_S':>10}")
    print(f"    {'---':>5}  {'----------':>10}  {'------':>7}  {'------':>7}  {'----------':>10}")

    baseline_mean = None

    for rho_f in rho_f_values:
        all_curves = []
        for trial in range(N_TRIALS):
            spec = build_branching_corridor(
                n_levels, n_dead_ends, rng=random.Random(7000 + trial))
            spec.landscape.historization.rho_s = rho_s_fixed
            spec.landscape.historization.rho_f = rho_f
            eps, _ = run_stochastic_episodes(
                spec, N_EPS, random.Random(8000 + trial))
            all_curves.append([e.steps for e in eps])

        avg = [sum(all_curves[t][ep] for t in range(N_TRIALS)) / N_TRIALS
               for ep in range(N_EPS)]
        mean = sum(avg) / len(avg)
        first5 = sum(avg[:5]) / 5
        last5 = sum(avg[-5:]) / 5

        if baseline_mean is None:
            baseline_mean = mean

        ratio = baseline_mean / mean if mean > 0 else 0.0
        marker = " (baseline)" if rho_f == rho_s_fixed else ""
        print(f"    {rho_f:>5.2f}  {mean:>10.1f}  {first5:>7.1f}  {last5:>7.1f}  "
              f"{ratio:>9.2f}×{marker}")


# ══════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════

def main():
    print("=" * 95)
    print("ASYMMETRIC ρ EXPERIMENT (C79)")
    print(f"Symmetric: ρ={RHO_SYMMETRIC}")
    print(f"Asymmetric: ρ_S={RHO_S_ASYM} (successes forgotten faster), "
          f"ρ_F={RHO_F_ASYM} (failures remembered longer)")
    print(f"Trials: {N_TRIALS}, Episodes: {N_EPS}")
    print("=" * 95)

    # Part 1: Cold start comparison
    print("\n" + "=" * 95)
    print("PART 1: SYMMETRIC vs ASYMMETRIC ρ (cold start)")
    print("=" * 95)
    for n_levels, n_dead_ends, label in CORRIDORS:
        run_cold_comparison(n_levels, n_dead_ends, label)

    # Part 2: 4-way transfer comparison
    print("\n\n" + "=" * 95)
    print("PART 2: 4-WAY COMPARISON (sym/asym × cold/warm)")
    print("Question: does asym-cold match sym-warm (i.e. make transfer redundant)?")
    print("=" * 95)
    for n_levels, n_dead_ends, label in CORRIDORS:
        run_transfer_comparison(n_levels, n_dead_ends, label)

    # Part 3: ρ_F sensitivity
    print("\n\n" + "=" * 95)
    print("PART 3: ρ_F SENSITIVITY SWEEP")
    print("=" * 95)
    run_rho_f_sweep()


if __name__ == "__main__":
    main()
