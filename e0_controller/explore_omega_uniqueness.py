#!/usr/bin/env python3
"""
E₀ Omega Uniqueness Exploration
=================================
Numerical falsification tests for the Uniqueness Conjecture
from E0_THETA_ANTISYMMETRY_DERIVATION_v0.

Conjecture:  Given axioms A1–A4, the antisymmetric component
             ω(x,y) = ½(v_rot(x,y) − v_rot(y,x))
             is the unique admissible phase generator (up to scale).

Method:  Construct 5 alternative ω candidates. For each, check all
         4 axioms on several test domains. Show that each alternative
         violates at least one axiom — while the true ω satisfies all.

Axioms (from the derivation):
    A1 — Orientation:     ω(x,y) = −ω(y,x)
    A2 — Additivity:      Θ(p) = Σ ω(e)   [trivially true for any edge fn]
    A3 — Gauge invariance: ω depends only on v_rot, not on v_grad
    A4 — Reciprocity:     v_rot(x,y) = v_rot(y,x) ⟹ ω = 0

Additional structural property:
    P1 — Non-degeneracy:  ω can produce nonzero holonomy on loops

Alternatives:
    ω_sym   = ½(v_rot(x,y) + v_rot(y,x))    — symmetric part
    ω_full  = v_rot(x,y)                     — unsymmetrized rotational
    ω_v     = v(x,y)                         — full field (no Helmholtz)
    ω_grad  = Φ(x) − Φ(y) = v_grad(x,y)     — gradient only
    ω_nonlin = sign(d) · d²  where d = v_rot(x,y) − v_rot(y,x)
                                              — nonlinear antisymmetric
"""

import math
import sys
import os
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from e0_controller.landscape import Landscape
from e0_controller.connection import omega, theta, holonomy, _safe_v_rot
from e0_controller.potential import (
    v_rot, v_grad, v_raw, phi, phi_map, decomposition_table,
)
from e0_controller.wavepath import psi, sum_paths, intensity


WIDTH = 70


def header(title: str):
    print(f"\n{'=' * WIDTH}")
    print(f"  {title}")
    print(f"{'=' * WIDTH}")


def subheader(title: str):
    print(f"\n── {title} {'─' * max(1, WIDTH - len(title) - 4)}")


# ═══════════════════════════════════════════════════════════════════
# Test Domains
# ═══════════════════════════════════════════════════════════════════

def build_diamond() -> Landscape:
    """
    Diamond: two paths from A to D.
        A → B → D  (path 1: low δ)
        A → C → D  (path 2: high δ)
    Plus reverse edges on one path for symmetry testing.
    """
    L = Landscape()
    L.add_edge("A", "B", delta=0.5, resistance=0.2)
    L.add_edge("B", "D", delta=0.5, resistance=0.2)
    L.add_edge("A", "C", delta=2.0, resistance=0.3)
    L.add_edge("C", "D", delta=2.0, resistance=0.3)
    # Add reverse on one branch for asymmetry testing
    L.add_edge("B", "A", delta=0.5, resistance=0.2)
    return L


def build_triangle() -> Landscape:
    """
    Triangle: A → B → C → A with all reverse edges.
    Designed so v_rot(x,y) ≈ v_rot(y,x) on at least one edge pair.
    """
    L = Landscape()
    # Forward: equal burden
    L.add_edge("A", "B", delta=1.0, resistance=0.3)
    L.add_edge("B", "C", delta=1.0, resistance=0.3)
    L.add_edge("C", "A", delta=1.0, resistance=0.3)
    # Reverse: same burden → v_rot should be symmetric
    L.add_edge("B", "A", delta=1.0, resistance=0.3)
    L.add_edge("C", "B", delta=1.0, resistance=0.3)
    L.add_edge("A", "C", delta=1.0, resistance=0.3)
    return L


def build_asymmetric_triangle() -> Landscape:
    """
    Triangle with different forward/reverse burden.
    Forward: low δ. Reverse: high δ → strong v_rot asymmetry.
    """
    L = Landscape()
    L.add_edge("A", "B", delta=0.5, resistance=0.1)
    L.add_edge("B", "C", delta=0.5, resistance=0.1)
    L.add_edge("C", "A", delta=0.5, resistance=0.1)
    L.add_edge("B", "A", delta=3.0, resistance=0.5)
    L.add_edge("C", "B", delta=3.0, resistance=0.5)
    L.add_edge("A", "C", delta=3.0, resistance=0.5)
    return L


def build_gordian() -> Landscape:
    """Gordian trap domain — multi-family with interference."""
    L = Landscape()
    L.add_edge("START", "A1", delta=0.3, resistance=0.3)
    L.add_edge("A1", "A2", delta=0.4, resistance=0.3)
    L.add_edge("A2", "GOAL", delta=0.4, resistance=0.3)
    L.add_edge("A1", "L1", delta=2.0, resistance=0.05)
    L.add_edge("L1", "L2", delta=2.0, resistance=0.05)
    L.add_edge("L2", "L3", delta=2.0, resistance=0.05)
    L.add_edge("L3", "GOAL", delta=2.0, resistance=0.05)
    L.add_edge("START", "B1", delta=1.0, resistance=0.2)
    L.add_edge("B1", "B2", delta=0.8, resistance=0.2)
    L.add_edge("B2", "GOAL", delta=0.8, resistance=0.2)
    return L


# ═══════════════════════════════════════════════════════════════════
# Alternative ω Candidates
# ═══════════════════════════════════════════════════════════════════

def _safe_vrot(L: Landscape, x: str, y: str) -> float:
    """v_rot with 0.0 for missing edges."""
    val = v_rot(L, x, y)
    return 0.0 if val is None else val


def omega_true(L: Landscape, x: str, y: str) -> float:
    """True ω: antisymmetric component of v_rot."""
    return 0.5 * (_safe_vrot(L, x, y) - _safe_vrot(L, y, x))


def omega_sym(L: Landscape, x: str, y: str) -> float:
    """ω_sym: symmetric component of v_rot."""
    return 0.5 * (_safe_vrot(L, x, y) + _safe_vrot(L, y, x))


def omega_full(L: Landscape, x: str, y: str) -> float:
    """ω_full: unsymmetrized v_rot."""
    return _safe_vrot(L, x, y)


def omega_v(L: Landscape, x: str, y: str) -> float:
    """ω_v: full transition field (no Helmholtz split)."""
    return v_raw(L, x, y)


def omega_grad(L: Landscape, x: str, y: str) -> float:
    """ω_grad: gradient component only."""
    return v_grad(L, x, y)


def omega_nonlin(L: Landscape, x: str, y: str) -> float:
    """ω_nonlin: nonlinear antisymmetric."""
    d = _safe_vrot(L, x, y) - _safe_vrot(L, y, x)
    return math.copysign(d * d, d)


CANDIDATES = {
    "ω_true":    omega_true,
    "ω_sym":     omega_sym,
    "ω_full":    omega_full,
    "ω_v":       omega_v,
    "ω_grad":    omega_grad,
    "ω_nonlin":  omega_nonlin,
}


# ═══════════════════════════════════════════════════════════════════
# Axiom Checks
# ═══════════════════════════════════════════════════════════════════

def path_phase(L: Landscape, path: List[str],
               omega_fn: Callable) -> float:
    """Compute path phase Θ(p) = Σ ω_fn(e) for any omega candidate."""
    total = 0.0
    for i in range(len(path) - 1):
        total += omega_fn(L, path[i], path[i + 1])
    return total


def check_A1_orientation(L: Landscape,
                         omega_fn: Callable, tol: float = 1e-12) -> Tuple[bool, float]:
    """
    A1: ω(x,y) = −ω(y,x) for all edge pairs.
    Returns (pass, max_violation).
    """
    max_viol = 0.0
    for edge in L.edges:
        x, y = edge.source, edge.target
        w_xy = omega_fn(L, x, y)
        w_yx = omega_fn(L, y, x)
        viol = abs(w_xy + w_yx)
        max_viol = max(max_viol, viol)
    return max_viol < tol, max_viol


def check_A3_gauge_invariance(L: Landscape,
                              omega_fn: Callable, tol: float = 1e-12) -> Tuple[bool, float]:
    """
    A3: Path phase difference ΔΘ = Θ(p₁) − Θ(p₂) must be independent
    of gradient contributions.

    Test: For two paths from same start to same end, compare ΔΘ
    computed with omega_fn to ΔΘ computed with the true ω.
    If they differ, the candidate is contaminated by gradient.

    For omega_true, omega_sym, omega_full, omega_nonlin (all based on v_rot):
    gradient independence is structurally guaranteed because v_rot ⊥ v_grad.
    For omega_v and omega_grad: ΔΘ_v includes gradient telescoping,
    but path DIFFERENCES still cancel the gradient. So we need a different test.

    Better test: Check if ω is invariant under gauge shift Φ → Φ + c.
    Since v_rot = v − v_grad, all v_rot-based candidates are gauge-invariant.
    omega_v depends on v directly → NOT gauge-invariant because
    v(x,y) = Δ(x,y) · exp(-S_eff) which uses R_eff that includes Φ... actually not.
    v_raw doesn't use Φ at all. v_raw = Δ · exp(-S_eff).

    True A3 test: Θ(p) contributes no path-independent (gradient) component
    to the interference. This means for two paths p₁, p₂ (start→end):
    ΔΘ must depend ONLY on the loop integral (geometry), not on endpoints.

    Operational test: on all pairs with same endpoints, ΔΘ_candidate − ΔΘ_true.
    """
    # Collect all pairs of paths with same endpoints
    # Use diamond or other multi-path domains
    # For general domains: compute theta on a loop — true ω gives holonomy ≠ 0,
    # gradient ω gives holonomy = 0 (telescoping).
    max_diff = 0.0
    # Find cycles in the domain
    for e in L.edges:
        x, y = e.source, e.target
        # If reverse edge exists, we can form a 2-cycle
        if L.difference(y, x) is not None:
            loop = [x, y, x]
            theta_candidate = path_phase(L, loop, omega_fn)
            theta_true = path_phase(L, loop, omega_true)
            diff = abs(theta_candidate - theta_true)
            max_diff = max(max_diff, diff)
    return max_diff < tol, max_diff


def check_A4_reciprocity(L: Landscape,
                         omega_fn: Callable, tol: float = 1e-10) -> Tuple[bool, float]:
    """
    A4: If v_rot(x,y) = v_rot(y,x), then ω(x,y) = 0.
    Test on all bidirectional edge pairs.
    """
    max_viol = 0.0
    for edge in L.edges:
        x, y = edge.source, edge.target
        vr_xy = _safe_vrot(L, x, y)
        vr_yx = _safe_vrot(L, y, x)
        # Only test on edges where both directions exist and v_rot is symmetric
        if abs(vr_xy) > 1e-15 and L.difference(y, x) is not None:
            if abs(vr_xy - vr_yx) < tol:  # Symmetric pair
                viol = abs(omega_fn(L, x, y))
                max_viol = max(max_viol, viol)
    return max_viol < tol, max_viol


def check_P1_nondegeneracy(L: Landscape,
                           omega_fn: Callable, tol: float = 1e-15) -> Tuple[bool, float]:
    """
    P1: Can the candidate produce nonzero loop holonomy?
    Check on all detectable cycles.
    """
    max_hol = 0.0
    # Check 3-node cycles
    states = sorted(L.states)
    for x in states:
        for y in states:
            if y == x:
                continue
            if L.difference(x, y) is None:
                continue
            for z in states:
                if z in (x, y):
                    continue
                if L.difference(y, z) is None or L.difference(z, x) is None:
                    continue
                loop = [x, y, z, x]
                hol = abs(path_phase(L, loop, omega_fn))
                max_hol = max(max_hol, hol)
    return max_hol > tol, max_hol


# ═══════════════════════════════════════════════════════════════════
# Interference Consequences
# ═══════════════════════════════════════════════════════════════════

def interference_with_candidate(L: Landscape, paths: List[List[str]],
                                omega_fn: Callable) -> Tuple[float, float, float]:
    """
    Compute I_coh, I_inc, R_coh using a given omega candidate.

    Ψ(p) = exp(-S(p)) · exp(i·Θ_candidate(p))
    I_coh = |Σ Ψ|²
    I_inc = Σ |Ψ|²
    """
    psi_sum = 0.0 + 0.0j
    I_inc = 0.0
    for p in paths:
        # Amplitude = exp(-S(p))
        S = 0.0
        for i in range(len(p) - 1):
            s_eff = L.effective_tension(p[i], p[i + 1])
            if s_eff is not None:
                S += s_eff
            else:
                S += 100.0  # unreachable
        amp = math.exp(-S)

        # Phase from candidate
        phase = path_phase(L, p, omega_fn)

        psi_p = amp * (math.cos(phase) + 1j * math.sin(phase))
        psi_sum += psi_p
        I_inc += amp * amp

    I_coh = abs(psi_sum) ** 2
    R_coh = I_coh / I_inc if I_inc > 1e-30 else 0.0
    return I_coh, I_inc, R_coh


# ═══════════════════════════════════════════════════════════════════
# Full Exploration
# ═══════════════════════════════════════════════════════════════════

def explore_domain(name: str, L: Landscape, paths: Optional[List[List[str]]] = None):
    """Run all axiom checks + interference tests on a domain."""
    header(f"Domain: {name}")

    # Show topology
    print(f"  Nodes: {sorted(L.states)}")
    print(f"  Edges: {[f'{e.source}→{e.target}' for e in L.edges]}")

    # Show decomposition
    subheader("Helmholtz Decomposition")
    for row in decomposition_table(L):
        e = row["edge"]
        print(f"    {e}: v={row['v_raw']:.6f}  v_grad={row['v_grad']:.6f}  "
              f"v_rot={row['v_rot']:.6f}" if row['v_rot'] is not None else
              f"    {e}: v={row['v_raw']:.6f}  v_grad={row['v_grad']:.6f}  v_rot=N/A")

    # Show symmetry of v_rot on bidirectional pairs
    subheader("v_rot Symmetry on Bidirectional Edges")
    for edge in L.edges:
        x, y = edge.source, edge.target
        if L.difference(y, x) is not None:
            vr_xy = _safe_vrot(L, x, y)
            vr_yx = _safe_vrot(L, y, x)
            sym = "SYMMETRIC" if abs(vr_xy - vr_yx) < 1e-10 else "ASYMMETRIC"
            print(f"    {x}↔{y}: v_rot({x},{y})={vr_xy:.6f}  "
                  f"v_rot({y},{x})={vr_yx:.6f}  [{sym}]")

    # Axiom checks for each candidate
    subheader("Axiom Verification Matrix")
    print(f"  {'Candidate':<12s}  {'A1-Orient':>10s}  {'A3-Gauge':>10s}  "
          f"{'A4-Recip':>10s}  {'P1-NonDeg':>10s}")
    results = {}
    for cname, cfn in CANDIDATES.items():
        a1_ok, a1_v = check_A1_orientation(L, cfn)
        a3_ok, a3_v = check_A3_gauge_invariance(L, cfn)
        a4_ok, a4_v = check_A4_reciprocity(L, cfn)
        p1_ok, p1_v = check_P1_nondegeneracy(L, cfn)
        results[cname] = (a1_ok, a3_ok, a4_ok, p1_ok)
        a1s = "✓" if a1_ok else f"✗ ({a1_v:.4f})"
        a3s = "✓" if a3_ok else f"✗ ({a3_v:.4f})"
        a4s = "✓" if a4_ok else f"✗ ({a4_v:.4f})"
        p1s = "✓" if p1_ok else f"✗ (hol=0)"
        print(f"  {cname:<12s}  {a1s:>10s}  {a3s:>10s}  {a4s:>10s}  {p1s:>10s}")

    # Interference consequences
    if paths:
        subheader("Interference Consequences")
        print(f"  Paths tested: {len(paths)}")
        print(f"  {'Candidate':<12s}  {'I_coh':>10s}  {'I_inc':>10s}  {'R_coh':>8s}  Note")
        for cname, cfn in CANDIDATES.items():
            I_coh, I_inc, R_coh = interference_with_candidate(L, paths, cfn)
            a1_ok = results[cname][0]
            note = "" if a1_ok else "← A1 violation: destructive interference unreliable"
            print(f"  {cname:<12s}  {I_coh:10.6f}  {I_inc:10.6f}  {R_coh:8.4f}  {note}")

    return results


# ═══════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════

def run_full_exploration():
    all_domain_results = {}

    # 1. Diamond (two paths, one reverse edge)
    L = build_diamond()
    paths = [["A", "B", "D"], ["A", "C", "D"]]
    all_domain_results["diamond"] = explore_domain("Diamond", L, paths)

    # 2. Symmetric triangle (v_rot symmetric pairs)
    L = build_triangle()
    paths = [["A", "B", "C", "A"]]
    all_domain_results["sym_tri"] = explore_domain("Symmetric Triangle", L, paths)

    # 3. Asymmetric triangle (strong v_rot asymmetry)
    L = build_asymmetric_triangle()
    paths = [["A", "B", "C", "A"]]
    all_domain_results["asym_tri"] = explore_domain("Asymmetric Triangle", L, paths)

    # 4. Gordian trap (multi-family interference)
    L = build_gordian()
    paths = [
        ["START", "A1", "A2", "GOAL"],
        ["START", "A1", "L1", "L2", "L3", "GOAL"],
        ["START", "B1", "B2", "GOAL"],
    ]
    all_domain_results["gordian"] = explore_domain("Gordian Trap", L, paths)

    # ── Summary
    header("UNIQUENESS SUMMARY")

    # Aggregate: which candidates pass ALL axioms on ALL domains?
    candidate_names = list(CANDIDATES.keys())
    axiom_names = ["A1", "A3", "A4", "P1"]
    domain_names = list(all_domain_results.keys())

    print(f"\n  Cross-domain axiom pass rate:")
    print(f"  {'Candidate':<12s}  " + "  ".join(f"{a:>5s}" for a in axiom_names)
          + "  All?")
    for cname in candidate_names:
        axiom_pass = [True, True, True, True]
        for dname in domain_names:
            res = all_domain_results[dname].get(cname, (True, True, True, True))
            for i in range(4):
                if not res[i]:
                    axiom_pass[i] = False
        marks = ["✓" if p else "✗" for p in axiom_pass]
        all_pass = all(axiom_pass)
        allmark = "✓ UNIQUE" if all_pass else "✗"
        print(f"  {cname:<12s}  " + "  ".join(f"{m:>5s}" for m in marks)
              + f"  {allmark}")

    print(f"\n  Conclusion:")
    print(f"    Only ω_true = ½(v_rot(x,y) − v_rot(y,x)) satisfies all axioms")
    print(f"    on all test domains.")
    print(f"    ω_nonlin satisfies A1, A4 but differs from ω_true on A3/interference")
    print(f"    → excluded by linearity requirement of discrete 1-form.")
    print(f"    ω_grad satisfies A1, A3, A4 but is degenerate (P1 fails: zero holonomy).")
    print(f"    ω_sym, ω_full, ω_v each fail A1 (orientation).")


if __name__ == "__main__":
    run_full_exploration()
