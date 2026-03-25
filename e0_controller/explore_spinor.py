#!/usr/bin/env python3
"""
E₀ Spinor Exploration — SU(2) Extension Discovery
=====================================================
Empirical exploration of the SU(2) lift from scalar U(1) phase.

Domains:
    I.   Gordian Trap   — known holonomy, tests U(1) ↔ SU(2) equivalence
    II.  Phase Loop     — engineered 2π / 4π loops for 720° periodicity
    III. Multi-Axis     — non-commutative SU(2) via axis variation
    IV.  Current Loop   — strong back-edge holonomy

Questions:
    Q1.  Does SU(2) reduce to U(1) on z-axis-only domains? (Consistency)
    Q2.  Does U(2π-loop) = −𝕀 and U(4π-loop) = +𝕀? (720° periodicity)
    Q3.  Can multi-axis SU(2) break U(1) ↔ SU(2) equivalence? (Divergence)
    Q4.  Does SU(2) change winner selection on any existing domain? (Practical impact)

Phase 4 research — results feed into docs, NOT into controller.
"""

import math
import sys
import os

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from e0_controller.landscape import Landscape
from e0_controller.connection import omega, theta
from e0_controller.wavepath import psi, sum_paths, intensity, path_analysis
from e0_controller.spinor_connection import (
    pauli_exponential, su2_edge_transport, su2_path_transport,
    su2_holonomy, spinor_psi, spinor_sum_paths, spinor_intensity,
    compare_u1_su2, spinor_path_analysis,
    is_identity, is_minus_identity, is_su2,
    SIGMA_X, SIGMA_Y, SIGMA_Z, IDENTITY, SPINOR_UP,
    su2_connection, su2_geometric_transport,
    su2_geometric_path_transport, spinor_geometric_intensity,
    compare_minimal_geometric, connection_analysis,
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

def build_gordian_trap() -> Landscape:
    """Standard Gordian Trap — known holonomy from Phase 3Q."""
    L = Landscape()
    L.add_edge("START", "A1", delta=0.3, resistance=0.3)
    L.add_edge("A1", "A2", delta=0.4, resistance=0.3)
    L.add_edge("A2", "GOAL", delta=0.4, resistance=0.3)
    L.add_edge("A1", "L1", delta=2.0, resistance=0.05)
    L.add_edge("L1", "L2", delta=2.0, resistance=0.05)
    L.add_edge("L2", "L3", delta=2.0, resistance=0.05)
    L.add_edge("L3", "GOAL", delta=2.0, resistance=0.05)
    L.add_edge("START", "B1", delta=0.5, resistance=0.4)
    L.add_edge("B1", "B2", delta=0.3, resistance=0.35)
    L.add_edge("B2", "GOAL", delta=0.3, resistance=0.3)
    return L


def build_phase_loop(total_omega: float, n_edges: int = 6) -> Landscape:
    """
    Engineered loop domain with controlled total holonomy.
    
    Creates a cycle S → N1 → N2 → ... → N_{n-1} → S with back-edges
    designed to produce a specific total ω around the loop.
    Plus a direct path S → D → GOAL for interference comparison.
    
    total_omega: desired Θ(cycle) — set to π for 2π rotation, 2π for 4π.
    """
    L = Landscape()
    # Target ω per edge: we need strong v_rot asymmetry
    # ω = ½(v_rot(xy) - v_rot(yx)). For directed-only edge: ω = ½·v_rot(xy)
    # v_rot = v - v_grad; v = δ·R_eff, v_grad = Φ(x)-Φ(y)
    #
    # Strategy: Use high δ, low R for forward loop edges (high v),
    # and no back-edges (v_rot(yx)=0). Then ω ≈ ½·v_rot(fwd).
    #
    # The exact ω depends on the Helmholtz decomposition, which
    # we can't pre-compute. So we build and measure.
    
    loop_states = ["S"] + [f"N{i}" for i in range(1, n_edges)] + ["S"]
    
    # Loop edges: high delta, low resistance → high v → high v_rot → high ω
    delta_loop = 2.5
    r_loop = 0.05
    for i in range(n_edges):
        src = loop_states[i]
        tgt = loop_states[i + 1] if i < n_edges - 1 else loop_states[-1]
        # Avoid S→S self-loop: last edge goes to S
        if i == n_edges - 1:
            tgt = "S"
        L.add_edge(loop_states[i], loop_states[i + 1] if i < n_edges - 1 else "S",
                   delta=delta_loop, resistance=r_loop)
    
    # Path through loop to GOAL
    L.add_edge(loop_states[n_edges - 1] if n_edges > 1 else "S",
               "GOAL", delta=0.3, resistance=0.3)
    
    # Direct path: low tension, acts as phase reference
    L.add_edge("S", "D", delta=0.3, resistance=0.3)
    L.add_edge("D", "GOAL", delta=0.3, resistance=0.3)
    
    return L, loop_states


def build_multi_axis_domain() -> Landscape:
    """
    Domain where different edges need different SU(2) rotation axes.
    
    Triangle: S → A → B → GOAL, with back-edges S←A, A←B.
    We assign: S→A on σ_z, A→B on σ_x, B→GOAL on σ_y.
    
    This creates genuinely non-commutative SU(2) structure
    that CANNOT be reduced to U(1).
    """
    L = Landscape()
    # Forward path via triangle
    L.add_edge("S", "A", delta=0.5, resistance=0.3)
    L.add_edge("A", "B", delta=0.5, resistance=0.3)
    L.add_edge("B", "GOAL", delta=0.3, resistance=0.3)
    
    # Back-edges for v_rot asymmetry
    L.add_edge("A", "S", delta=1.5, resistance=0.1)  # strong back
    L.add_edge("B", "A", delta=1.5, resistance=0.1)  # strong back
    
    # Alternative direct path (reference)
    L.add_edge("S", "C", delta=0.4, resistance=0.4)
    L.add_edge("C", "GOAL", delta=0.4, resistance=0.3)
    
    return L


def build_current_loop() -> Landscape:
    """Current-loop domain with strong back-edges (from test_amplitude_overlay)."""
    L = Landscape()
    for s, t in [("START", "A1"), ("A1", "A2"), ("A2", "A3"),
                 ("A3", "A4"), ("A4", "END")]:
        L.add_edge(s, t, delta=0.2, resistance=0.25)
    L.add_edge("START", "B1", delta=0.25, resistance=0.5)
    L.add_edge("B1", "END", delta=0.25, resistance=0.5)
    for s, t in [("A4", "A3"), ("A3", "A2"), ("A2", "A1"), ("A1", "START")]:
        L.add_edge(s, t, delta=3.0, resistance=0.3)
    L.add_edge("END", "A4", delta=3.0, resistance=0.3)
    return L


# ═══════════════════════════════════════════════════════════════════
# Multi-axis function for Domain III
# ═══════════════════════════════════════════════════════════════════

def triangle_axis_fn(L, x, y):
    """Assign different Pauli axes to different edges in the triangle domain."""
    edge = (x, y)
    axis_map = {
        ("S", "A"): np.array([0, 0, 1.0]),      # σ_z
        ("A", "S"): np.array([0, 0, 1.0]),
        ("A", "B"): np.array([1.0, 0, 0]),       # σ_x
        ("B", "A"): np.array([1.0, 0, 0]),
        ("B", "GOAL"): np.array([0, 1.0, 0]),    # σ_y
        ("S", "C"): np.array([0, 0, 1.0]),       # reference path: σ_z
        ("C", "GOAL"): np.array([0, 0, 1.0]),
    }
    return axis_map.get(edge, np.array([0, 0, 1.0]))


# ═══════════════════════════════════════════════════════════════════
# Domain I: Gordian Trap — U(1) ↔ SU(2) consistency
# ═══════════════════════════════════════════════════════════════════

def run_domain_1():
    header("Domain I: Gordian Trap — U(1) ↔ SU(2) Consistency")
    L = build_gordian_trap()
    
    # Known paths from Phase 3Q
    paths = {
        "A-short": ["START", "A1", "A2", "GOAL"],
        "A-loop":  ["START", "A1", "L1", "L2", "L3", "GOAL"],
        "B-path":  ["START", "B1", "B2", "GOAL"],
    }
    
    subheader("Per-path U(1) vs SU(2) comparison (ẑ axis)")
    for name, path in paths.items():
        u1_psi_val = psi(L, path)
        sp = spinor_path_analysis(L, path)
        print(f"\n  {name}: {' → '.join(path)}")
        print(f"    U(1):  Ψ = {u1_psi_val:.6f},  |Ψ| = {abs(u1_psi_val):.6f},  Θ = {theta(L, path):.4f} rad")
        print(f"    SU(2): Ψ = [{sp['psi'][0]:.6f}, {sp['psi'][1]:.6f}],  ‖Ψ‖ = {sp['magnitude']:.6f}")
        print(f"    U:     det = {sp['det_U']:.6f},  tr = {sp['trace_U']:.6f}")
        print(f"    SU(2)? {is_su2(sp['U'])}")
    
    subheader("Action-level interference comparison")
    # Group paths by first action
    action_paths = {
        "A1": [paths["A-short"], paths["A-loop"]],
        "B1": [paths["B-path"]],
    }
    for action, path_list in action_paths.items():
        cmp = compare_u1_su2(L, path_list)
        print(f"\n  Action {action}:")
        print(f"    U(1) intensity:  {cmp['u1_intensity']:.8f}")
        print(f"    SU(2) intensity: {cmp['su2_intensity']:.8f}")
        print(f"    Deviation:       {cmp['deviation_pct']:.4f}%")
    
    subheader("Q1 verdict: U(1) ↔ SU(2) equivalence on z-axis")
    all_paths_list = list(paths.values())
    cmp_all = compare_u1_su2(L, all_paths_list)
    deviation = cmp_all["deviation_pct"]
    print(f"  Total deviation: {deviation:.6f}%")
    if deviation < 0.01:
        print("  ✓ CONFIRMED: SU(2) with ẑ-axis reduces exactly to U(1)")
    else:
        print(f"  ⚠ DEVIATION DETECTED: {deviation:.4f}% — investigate!")
    
    return deviation


# ═══════════════════════════════════════════════════════════════════
# Domain II: Phase Loop — 720° Periodicity
# ═══════════════════════════════════════════════════════════════════

def run_domain_2():
    header("Domain II: Phase Loop — 720° Periodicity Test")
    
    subheader("Building loop domain and measuring actual holonomy")
    L, loop_states = build_phase_loop(total_omega=math.pi, n_edges=6)
    
    # Measure the actual holonomy
    cycle = loop_states  # Already closed: S → N1 → ... → N5 → S
    theta_cycle = theta(L, cycle)
    U_cycle = su2_holonomy(L, cycle)
    
    print(f"  Loop: {' → '.join(cycle)}")
    print(f"  U(1) holonomy Θ(γ): {theta_cycle:.6f} rad  ({math.degrees(theta_cycle):.2f}°)")
    print(f"  SU(2) holonomy U(γ):")
    print(f"    {U_cycle[0]}")
    print(f"    {U_cycle[1]}")
    print(f"    det = {np.linalg.det(U_cycle):.6f}")
    print(f"    SU(2)? {is_su2(U_cycle)}")
    
    subheader("Single traverse (1× loop)")
    print(f"  Θ = {theta_cycle:.6f} rad")
    print(f"  U = exp(-iΘ/2·σ_z):")
    print(f"    Expected: cos(Θ/2) = {math.cos(theta_cycle/2):.6f}, -i·sin(Θ/2) = {-math.sin(theta_cycle/2):.6f}i")
    print(f"    Actual trace:  {np.trace(U_cycle):.6f}")
    print(f"    Expected trace: 2·cos(Θ/2) = {2*math.cos(theta_cycle/2):.6f}")
    
    subheader("720° test: accumulate N traversals")
    # How many loops to reach ~2π and ~4π?
    if abs(theta_cycle) > 0.01:
        n_for_2pi = round(2 * math.pi / abs(theta_cycle))
        n_for_4pi = 2 * n_for_2pi
    else:
        n_for_2pi = 100  # won't reach, but try
        n_for_4pi = 200
    
    print(f"  |Θ_cycle| = {abs(theta_cycle):.6f} rad")
    print(f"  Loops for ~2π: {n_for_2pi},  for ~4π: {n_for_4pi}")
    
    # Build U^n by matrix power
    U_2pi = np.linalg.matrix_power(U_cycle, n_for_2pi) if n_for_2pi > 0 else IDENTITY
    U_4pi = np.linalg.matrix_power(U_cycle, n_for_4pi) if n_for_4pi > 0 else IDENTITY
    
    total_theta_2pi = theta_cycle * n_for_2pi
    total_theta_4pi = theta_cycle * n_for_4pi
    
    print(f"\n  After {n_for_2pi} loops (Θ_total = {total_theta_2pi:.4f} rad ≈ {math.degrees(total_theta_2pi):.1f}°):")
    print(f"    U = −𝕀? {is_minus_identity(U_2pi)}")
    print(f"    tr(U) = {np.trace(U_2pi):.6f}  (expected ≈ -2 for −𝕀)")
    
    print(f"\n  After {n_for_4pi} loops (Θ_total = {total_theta_4pi:.4f} rad ≈ {math.degrees(total_theta_4pi):.1f}°):")
    print(f"    U = +𝕀? {is_identity(U_4pi)}")
    print(f"    tr(U) = {np.trace(U_4pi):.6f}  (expected ≈ +2 for +𝕀)")
    
    subheader("Direct algebraic verification (bypass graph)")
    # For σ_z axis: U(θ) = diag(e^{-iθ/2}, e^{iθ/2})
    # U(2π) = diag(-1, -1) = -𝕀  ✓
    # U(4π) = diag(1, 1) = +𝕀    ✓
    U_exact_2pi = pauli_exponential(2 * math.pi, np.array([0, 0, 1.0]))
    U_exact_4pi = pauli_exponential(4 * math.pi, np.array([0, 0, 1.0]))
    
    print(f"  exp(-iπ·σ_z) = −𝕀? {is_minus_identity(U_exact_2pi)}")
    print(f"  exp(-i2π·σ_z) = +𝕀? {is_identity(U_exact_4pi)}")
    
    subheader("Q2 verdict: 720° periodicity")
    algebraic_ok = is_minus_identity(U_exact_2pi) and is_identity(U_exact_4pi)
    graph_2pi = is_minus_identity(U_2pi) or abs(np.trace(U_2pi) + 2) < 0.5
    graph_4pi = is_identity(U_4pi) or abs(np.trace(U_4pi) - 2) < 0.5
    
    if algebraic_ok:
        print("  ✓ ALGEBRAIC: 720° periodicity holds (exp(-iπσ_z) = -𝕀, exp(-i2πσ_z) = +𝕀)")
    else:
        print("  ✗ ALGEBRAIC FAILURE — check Pauli exponential!")
    
    if graph_2pi and graph_4pi:
        print(f"  ✓ GRAPH: After {n_for_2pi}/{n_for_4pi} loops, U^n approaches −𝕀/+𝕀")
    else:
        print(f"  ⊘ GRAPH: Holonomy per loop = {theta_cycle:.6f} rad — may need more loops or different domain")
    
    return theta_cycle, algebraic_ok


# ═══════════════════════════════════════════════════════════════════
# Domain III: Multi-Axis — Non-commutative SU(2) Divergence
# ═══════════════════════════════════════════════════════════════════

def run_domain_3():
    header("Domain III: Multi-Axis — SU(2) ≠ U(1) Test")
    L = build_multi_axis_domain()
    
    # Two paths to GOAL
    path_triangle = ["S", "A", "B", "GOAL"]
    path_direct = ["S", "C", "GOAL"]
    
    subheader("ω values (scalar connection)")
    for p in [path_triangle, path_direct]:
        for i in range(len(p) - 1):
            w = omega(L, p[i], p[i+1])
            print(f"  ω({p[i]}→{p[i+1]}) = {w:.6f}")
    
    subheader("U(1) analysis (scalar phase)")
    for name, path in [("triangle", path_triangle), ("direct", path_direct)]:
        pa = path_analysis(L, path)
        print(f"  {name}: S={pa['tension']:.4f}, Θ={pa['phase']:.4f}, |Ψ|={pa['magnitude']:.6f}")
    
    u1_I_triangle = intensity(L, [path_triangle])
    u1_I_direct = intensity(L, [path_direct])
    print(f"\n  U(1) I(triangle) = {u1_I_triangle:.8f}")
    print(f"  U(1) I(direct)   = {u1_I_direct:.8f}")
    print(f"  U(1) winner: {'triangle' if u1_I_triangle > u1_I_direct else 'direct'}")
    
    subheader("SU(2) with ẑ-axis only (should match U(1))")
    cmp_z_tri = compare_u1_su2(L, [path_triangle])
    cmp_z_dir = compare_u1_su2(L, [path_direct])
    print(f"  z-only deviation (triangle): {cmp_z_tri['deviation_pct']:.6f}%")
    print(f"  z-only deviation (direct):   {cmp_z_dir['deviation_pct']:.6f}%")
    
    subheader("SU(2) with multi-axis (σ_z, σ_x, σ_y)")
    # Triangle path uses 3 different axes
    sp_tri = spinor_path_analysis(L, path_triangle, axis_fn=triangle_axis_fn)
    sp_dir = spinor_path_analysis(L, path_direct, axis_fn=triangle_axis_fn)
    
    print(f"\n  Triangle path (multi-axis):")
    print(f"    U = {sp_tri['U']}")
    print(f"    det = {sp_tri['det_U']:.6f},  SU(2)? {is_su2(sp_tri['U'])}")
    print(f"    Ψ = [{sp_tri['psi'][0]:.6f}, {sp_tri['psi'][1]:.6f}]")
    print(f"    ‖Ψ‖ = {sp_tri['magnitude']:.6f},  I = {sp_tri['intensity']:.8f}")
    
    print(f"\n  Direct path (z-axis reference):")
    print(f"    U = {sp_dir['U']}")
    print(f"    Ψ = [{sp_dir['psi'][0]:.6f}, {sp_dir['psi'][1]:.6f}]")
    print(f"    ‖Ψ‖ = {sp_dir['magnitude']:.6f},  I = {sp_dir['intensity']:.8f}")
    
    su2_I_triangle = sp_tri["intensity"]
    su2_I_direct = sp_dir["intensity"]
    
    subheader("Comparison: U(1) vs multi-axis SU(2)")
    print(f"  U(1):  I(tri)={u1_I_triangle:.8f},  I(dir)={u1_I_direct:.8f}")
    print(f"  SU(2): I(tri)={su2_I_triangle:.8f},  I(dir)={su2_I_direct:.8f}")
    
    u1_winner = "triangle" if u1_I_triangle > u1_I_direct else "direct"
    su2_winner = "triangle" if su2_I_triangle > su2_I_direct else "direct"
    
    deviation_tri = abs(su2_I_triangle - u1_I_triangle) / max(u1_I_triangle, su2_I_triangle, 1e-30) * 100
    deviation_dir = abs(su2_I_direct - u1_I_direct) / max(u1_I_direct, su2_I_direct, 1e-30) * 100
    
    print(f"\n  Intensity deviation (triangle): {deviation_tri:.4f}%")
    print(f"  Intensity deviation (direct):   {deviation_dir:.4f}%")
    print(f"  U(1) winner:  {u1_winner}")
    print(f"  SU(2) winner: {su2_winner}")
    
    subheader("Q3 verdict: Multi-axis SU(2) divergence")
    if u1_winner != su2_winner:
        print(f"  ★ DIVERGENCE! U(1) picks {u1_winner}, SU(2) picks {su2_winner}")
        print(f"    This is the first domain where SU(2) makes a DIFFERENT decision!")
    elif max(deviation_tri, deviation_dir) > 0.1:
        print(f"  ⊘ Same winner but intensities differ by {max(deviation_tri, deviation_dir):.4f}%")
        print(f"    SU(2) structure visible but doesn't flip winner here")
    else:
        print(f"  ✓ No divergence: multi-axis SU(2) ≈ U(1) on this domain")
    
    # Test non-commutativity explicitly
    subheader("Non-commutativity check")
    U_SA = su2_edge_transport(L, "S", "A", np.array([0, 0, 1.0]))
    U_AB = su2_edge_transport(L, "A", "B", np.array([1.0, 0, 0]))
    
    prod_1 = U_AB @ U_SA  # correct order
    prod_2 = U_SA @ U_AB  # reversed
    commutator_norm = np.linalg.norm(prod_1 - prod_2)
    print(f"  ‖U(AB)·U(SA) − U(SA)·U(AB)‖ = {commutator_norm:.6f}")
    if commutator_norm > 1e-6:
        print(f"  ✓ NON-COMMUTATIVE: matrix order matters (norm = {commutator_norm:.6f})")
    else:
        print(f"  ─ Commutative on this domain (ω values too small?)")
    
    return u1_winner, su2_winner, max(deviation_tri, deviation_dir)


# ═══════════════════════════════════════════════════════════════════
# Domain IV: Current Loop — Practical Impact
# ═══════════════════════════════════════════════════════════════════

def run_domain_4():
    header("Domain IV: Current Loop — Practical G5 Impact")
    L = build_current_loop()
    
    # Known paths from test_amplitude_overlay
    paths_A1 = [
        ["START", "A1", "A2", "A3", "A4", "END"],
    ]
    paths_B1 = [
        ["START", "B1", "END"],
    ]
    
    subheader("U(1) vs SU(2) per action")
    for name, paths in [("A1", paths_A1), ("B1", paths_B1)]:
        cmp = compare_u1_su2(L, paths)
        print(f"\n  Action {name}: {len(paths)} path(s)")
        print(f"    U(1)  I = {cmp['u1_intensity']:.8f}")
        print(f"    SU(2) I = {cmp['su2_intensity']:.8f}")
        print(f"    Deviation: {cmp['deviation_pct']:.4f}%")
    
    subheader("Holonomy on current loop cycle")
    cycle = ["START", "A1", "A2", "A3", "A4", "END", "A4", "A3", "A2", "A1", "START"]
    theta_c = theta(L, cycle)
    U_c = su2_holonomy(L, cycle)
    print(f"  Loop: {' → '.join(cycle[:6])} → ... → START")
    print(f"  Θ(cycle) = {theta_c:.6f} rad ({math.degrees(theta_c):.2f}°)")
    print(f"  tr(U) = {np.trace(U_c):.6f}")
    print(f"  SU(2)? {is_su2(U_c)}")
    
    subheader("Q4 verdict: Practical impact on current-loop domain")
    print("  (With ẑ-axis only, SU(2) should match U(1) exactly)")


# ═══════════════════════════════════════════════════════════════════
# Domain V: Holonomy Scan — Sweep loop parameters
# ═══════════════════════════════════════════════════════════════════

def run_domain_5():
    header("Domain V: Holonomy Parameter Scan")
    
    subheader("Edge count vs holonomy (loop domain)")
    for n in [3, 4, 5, 6, 8, 10]:
        L, loop_states = build_phase_loop(total_omega=math.pi, n_edges=n)
        theta_c = theta(L, loop_states)
        U_c = su2_holonomy(L, loop_states)
        det_U = np.linalg.det(U_c)
        tr_U = np.trace(U_c)
        print(f"  n={n:2d}: Θ={theta_c:+.4f} rad ({math.degrees(theta_c):+7.2f}°)  "
              f"tr(U)={tr_U:+.4f}  det(U)={det_U:.4f}  SU(2)={is_su2(U_c)}")
    
    subheader("Delta/R sweep for single loop edge")
    print(f"  {'delta':>6s} {'R':>6s} {'ω':>10s} {'ω_deg':>10s}")
    L_base = Landscape()
    L_base.add_edge("X", "Y", delta=1.0, resistance=0.5)
    for d in [0.5, 1.0, 2.0, 3.0, 5.0]:
        for r in [0.05, 0.1, 0.5, 1.0]:
            L_test = Landscape()
            L_test.add_edge("X", "Y", delta=d, resistance=r)
            w = omega(L_test, "X", "Y")
            print(f"  {d:6.1f} {r:6.2f} {w:+10.6f} {math.degrees(w):+10.4f}°")


# ═══════════════════════════════════════════════════════════════════
# Domain VI: Geometric Coupling — Helmholtz-derived axis
# ═══════════════════════════════════════════════════════════════════

def run_domain_6():
    header("Domain VI: Geometric Coupling — Axis from Helmholtz Vorticity")

    # ── Part A: Connection vector analysis on Gordian Trap ────────
    subheader("A. su(2) connection vectors on Gordian Trap")
    L = build_gordian_trap()
    print(f"  {'edge':>12s}  {'ω':>8s}  {'A₁':>8s}  {'A₂':>8s}  {'A₃':>8s}  {'‖A⃗‖':>8s}  {'off-axis%':>9s}")
    all_off_axis = []
    for edge in L.edges:
        x, y = edge.source, edge.target
        info = connection_analysis(L, x, y)
        A = info['A_vector']
        off = info['off_axis_fraction'] * 100
        all_off_axis.append(off)
        print(f"  {x+'→'+y:>12s}  {info['omega']:+8.4f}  {A[0]:+8.5f}  {A[1]:+8.5f}  {A[2]:+8.5f}  {info['A_norm']:8.5f}  {off:8.2f}%")
    avg_off = np.mean(all_off_axis) if all_off_axis else 0.0
    print(f"\n  Average off-axis fraction: {avg_off:.2f}%")

    # ── Part B: Antisymmetry check ───────────────────────────────
    subheader("B. Antisymmetry: A⃗(y,x) = −A⃗(x,y)?")
    max_violation = 0.0
    checked = 0
    for edge in L.edges:
        x, y = edge.source, edge.target
        A_xy = su2_connection(L, x, y)
        A_yx = su2_connection(L, y, x)
        viol = np.max(np.abs(A_xy + A_yx))
        max_violation = max(max_violation, viol)
        checked += 1
    print(f"  Checked {checked} edge pairs")
    print(f"  Max ‖A⃗(x,y) + A⃗(y,x)‖_∞ = {max_violation:.2e}")
    print(f"  Antisymmetric? {'✓ YES' if max_violation < 1e-10 else '✗ NO'}")

    # ── Part C: Transport reversal U(y,x) = U(x,y)† ─────────────
    subheader("C. Transport reversal: U_geo(y,x) = U_geo(x,y)†?")
    max_rev = 0.0
    for edge in L.edges:
        x, y = edge.source, edge.target
        U_xy = su2_geometric_transport(L, x, y)
        U_yx = su2_geometric_transport(L, y, x)
        rev_err = np.max(np.abs(U_yx - U_xy.conj().T))
        max_rev = max(max_rev, rev_err)
    print(f"  Max ‖U(y,x) − U(x,y)†‖_∞ = {max_rev:.2e}")
    print(f"  Reversal holds? {'✓ YES' if max_rev < 1e-10 else '✗ NO'}")

    # ── Part D: Minimal vs Geometric on Gordian paths ────────────
    subheader("D. Minimal vs Geometric intensity on Gordian Trap")
    paths_A_short = [["START", "A1", "A2", "GOAL"]]
    paths_A_loop = [["START", "A1", "A2", "GOAL"],
                    ["START", "A1", "L1", "L2", "L3", "GOAL"]]
    paths_B = [["START", "B1", "B2", "GOAL"]]

    for label, paths in [("A-short", paths_A_short),
                         ("A-short+loop", paths_A_loop),
                         ("B-path", paths_B)]:
        cmp = compare_minimal_geometric(L, paths)
        print(f"  {label}:")
        print(f"    U(1)       : I = {cmp['u1_intensity']:.6f}")
        print(f"    SU(2)-min  : I = {cmp['minimal_intensity']:.6f}")
        print(f"    SU(2)-geo  : I = {cmp['geometric_intensity']:.6f}")
        print(f"    geo vs min : {cmp['geo_vs_min_pct']:.4f}%")

    # ── Part E: Multi-axis domain ────────────────────────────────
    subheader("E. Geometric coupling on multi-axis domain")
    L_multi = build_multi_axis_domain()
    print(f"  {'edge':>12s}  {'A₁':>8s}  {'A₂':>8s}  {'A₃':>8s}  {'off-axis%':>9s}")
    for edge in L_multi.edges:
        x, y = edge.source, edge.target
        info = connection_analysis(L_multi, x, y)
        A = info['A_vector']
        off = info['off_axis_fraction'] * 100
        print(f"  {x+'→'+y:>12s}  {A[0]:+8.5f}  {A[1]:+8.5f}  {A[2]:+8.5f}  {off:8.2f}%")

    paths_multi = [["S", "A", "B", "GOAL"], ["S", "C", "GOAL"]]
    cmp_multi = compare_minimal_geometric(L_multi, paths_multi)
    print(f"\n  Three-theory comparison on multi-axis paths:")
    print(f"    U(1)      : I = {cmp_multi['u1_intensity']:.6f}")
    print(f"    SU(2)-min : I = {cmp_multi['minimal_intensity']:.6f}")
    print(f"    SU(2)-geo : I = {cmp_multi['geometric_intensity']:.6f}")
    print(f"    geo vs min: {cmp_multi['geo_vs_min_pct']:.4f}%")
    print(f"    geo vs U1 : {cmp_multi['geo_vs_u1_pct']:.4f}%")

    # ── Part F: Triangle domain (maximal face holonomy) ──────────
    subheader("F. Triangle domain — rich face holonomy")
    L_tri = Landscape()
    L_tri.add_edge("A", "B", delta=3.0, resistance=0.2)
    L_tri.add_edge("B", "C", delta=2.0, resistance=0.3)
    L_tri.add_edge("C", "A", delta=1.5, resistance=0.4)
    L_tri.add_edge("A", "C", delta=1.0, resistance=0.5)
    L_tri.add_edge("B", "A", delta=0.8, resistance=0.3)
    L_tri.add_edge("C", "B", delta=2.5, resistance=0.25)
    print(f"  Triangle landscape: 3 nodes, {len(list(L_tri.edges))} edges")

    for edge in L_tri.edges:
        x, y = edge.source, edge.target
        A = su2_connection(L_tri, x, y)
        norm = np.linalg.norm(A)
        off = np.sqrt(A[0]**2 + A[1]**2) / norm * 100 if norm > 1e-15 else 0.0
        print(f"  {x+'→'+y:>6s}: A⃗ = [{A[0]:+.5f}, {A[1]:+.5f}, {A[2]:+.5f}]  ‖A⃗‖={norm:.5f}  off-axis={off:.1f}%")

    paths_tri = [["A", "B", "C"], ["A", "C"]]
    cmp_tri = compare_minimal_geometric(L_tri, paths_tri)
    print(f"\n  Paths A→B→C vs A→C:")
    print(f"    U(1)      : I = {cmp_tri['u1_intensity']:.6f}")
    print(f"    SU(2)-min : I = {cmp_tri['minimal_intensity']:.6f}")
    print(f"    SU(2)-geo : I = {cmp_tri['geometric_intensity']:.6f}")
    geo_diverges = cmp_tri['geo_vs_min_pct'] > 0.1
    print(f"    geo vs min: {cmp_tri['geo_vs_min_pct']:.4f}% {'★ DIVERGES' if geo_diverges else '= matches'}")

    return avg_off, geo_diverges


# ═══════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════

def run_summary(dev_1, theta_2, alg_ok_2, u1_w_3, su2_w_3, dev_3):
    header("SUMMARY")
    
    print(f"\n  Q1. SU(2) reduces to U(1) on ẑ-axis?")
    if dev_1 < 0.01:
        print(f"      ✓ YES — deviation {dev_1:.6f}% (Gordian trap)")
    else:
        print(f"      ⚠ NO — deviation {dev_1:.4f}%")
    
    print(f"\n  Q2. 720° periodicity?")
    print(f"      {'✓' if alg_ok_2 else '✗'} ALGEBRAIC: exp(-iπσ)=-𝕀, exp(-i2πσ)=+𝕀")
    print(f"      Graph loop Θ = {theta_2:.6f} rad ({math.degrees(theta_2):.2f}°)")
    
    print(f"\n  Q3. Multi-axis SU(2) ≠ U(1)?")
    if u1_w_3 != su2_w_3:
        print(f"      ★ YES — U(1) picks {u1_w_3}, SU(2) picks {su2_w_3}")
    elif dev_3 > 0.1:
        print(f"      ⊘ Same winner but {dev_3:.4f}% intensity difference")
    else:
        print(f"      ─ No divergence detected (deviation {dev_3:.4f}%)")
    
    print(f"\n  Q4. Practical impact on current-loop?")
    print(f"      (See Domain IV output above)")
    
    print(f"\n{'=' * WIDTH}")
    print(f"  Phase 4 spinor exploration complete.")
    print(f"{'=' * WIDTH}")


# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    dev_1 = run_domain_1()
    theta_2, alg_ok_2 = run_domain_2()
    u1_w_3, su2_w_3, dev_3 = run_domain_3()
    run_domain_4()
    run_domain_5()
    avg_off, geo_div = run_domain_6()
    run_summary(dev_1, theta_2, alg_ok_2, u1_w_3, su2_w_3, dev_3)
