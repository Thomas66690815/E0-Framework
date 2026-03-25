"""
E₀ Controller — Spinor Connection (SU(2) Extension)
======================================================
Lifts the scalar U(1) connection ω to SU(2) matrix transport.

This module extends the existing Phase 2 layer (connection.py / wavepath.py)
WITHOUT modifying it. The U(1) layer remains the operational foundation;
this SU(2) layer is a parallel analysis tool.

Theory:
    Current U(1):  Ψ(p) = exp(−S + iΘ) ∈ ℂ

    SU(2) lift:
        Edge transport:   U(x,y) = exp(−i · ω(x,y) / 2 · n̂ · σ⃗)
        Path transport:   U(p)   = U(e_n) · U(e_{n-1}) · ... · U(e_1)
        Spinor amplitude: Ψ(p)   = exp(−S(p)) · U(p) · |ref⟩     ∈ ℂ²
        Intensity:        I(a)   = ‖Σ_p Ψ(p)‖²

    where σ⃗ = (σ_x, σ_y, σ_z) are Pauli matrices and n̂ is the
    rotation axis derived from the local v_rot structure.

Key predictions:
    1. 720° periodicity:  U(2π loop) = −𝕀,  U(4π loop) = +𝕀
    2. Non-commutativity: U(p₁∘p₂) ≠ U(p₂∘p₁) in general
    3. Richer interference: ℂ² superposition can differ from ℂ

Convention — Minimal embedding (Phase 4a):
    Rotation axis n̂: For a single edge x→y, v_rot defines a scalar.
    We embed this into SU(2) by choosing n̂ = ẑ (σ_z generator),
    which reduces SU(2) to U(1) for single-axis rotations.

Geometric coupling (Phase 4b — Gemini proposal):
    The full su(2) connection vector A⃗(x,y) has three components:
        A₃ = ω(x,y)           — direct connection (existing scalar phase)
        A₁ = δω_src − δω_tgt  — vorticity gradient across the edge
        A₂ = avg face holonomy — curvature from directed triangles

    All three are antisymmetric: A_i(y,x) = −A_i(x,y).
    The axis n̂ = A⃗/‖A⃗‖ and total angle ‖A⃗‖ emerge from geometry.
    When A₁ = A₂ = 0, this reduces exactly to the minimal embedding.

Phase 4 research module — NOT integrated into controller decisions.
"""

from __future__ import annotations

import cmath
import math
from typing import Dict, List, Optional, Tuple

import numpy as np

from .landscape import Landscape
from .connection import omega, theta
from .wavepath import path_tension


# ── Pauli matrices ──────────────────────────────────────────────────

SIGMA_X = np.array([[0, 1], [1, 0]], dtype=complex)
SIGMA_Y = np.array([[0, -1j], [1j, 0]], dtype=complex)
SIGMA_Z = np.array([[1, 0], [0, -1]], dtype=complex)
IDENTITY = np.eye(2, dtype=complex)

# Reference spinor |↑⟩ = (1, 0)^T
SPINOR_UP = np.array([1.0, 0.0], dtype=complex)


# ── SU(2) primitives ───────────────────────────────────────────────

def pauli_exponential(angle: float, axis: np.ndarray) -> np.ndarray:
    """
    exp(−i · angle/2 · n̂·σ⃗) = cos(angle/2)·𝕀 − i·sin(angle/2)·(n̂·σ⃗)

    This is the standard SU(2) rotation formula.
    axis must be a unit 3-vector [nx, ny, nz].
    """
    half = angle / 2.0
    c = math.cos(half)
    s = math.sin(half)
    n_dot_sigma = (axis[0] * SIGMA_X
                   + axis[1] * SIGMA_Y
                   + axis[2] * SIGMA_Z)
    return c * IDENTITY - 1j * s * n_dot_sigma


def su2_edge_transport(L: Landscape, x: str, y: str,
                       axis: Optional[np.ndarray] = None) -> np.ndarray:
    """
    SU(2) transport matrix for edge x → y.

    U(x,y) = exp(−i · ω(x,y) / 2 · n̂ · σ⃗)

    Default axis: ẑ = [0, 0, 1] (minimal embedding, reduces to U(1)).
    Custom axes enable multi-axis SU(2) structure on richer topologies.
    """
    w = omega(L, x, y)
    if axis is None:
        axis = np.array([0.0, 0.0, 1.0])
    return pauli_exponential(w, axis)


def su2_path_transport(L: Landscape, path: List[str],
                       axis_fn=None) -> np.ndarray:
    """
    SU(2) parallel transport along a path.

    U(p) = U(e_n) · U(e_{n-1}) · ... · U(e_1)

    Matrix multiplication is right-to-left: first edge applied first.
    axis_fn: optional callable (L, x, y) → unit 3-vector for per-edge axis.
    """
    if len(path) < 2:
        return IDENTITY.copy()

    U = IDENTITY.copy()
    for i in range(len(path) - 1):
        x, y = path[i], path[i + 1]
        if axis_fn is not None:
            axis = axis_fn(L, x, y)
        else:
            axis = None
        U_edge = su2_edge_transport(L, x, y, axis)
        U = U_edge @ U
    return U


def su2_holonomy(L: Landscape, cycle: List[str],
                 axis_fn=None) -> np.ndarray:
    """
    SU(2) holonomy: transport around a closed loop.

    For a trivial loop: U = 𝕀 (no net rotation).
    For 2π phase accumulation: U = −𝕀 (720° periodicity).
    For 4π: U = +𝕀.
    """
    return su2_path_transport(L, cycle, axis_fn)


# ── Spinor amplitude ───────────────────────────────────────────────

def spinor_psi(L: Landscape, path: List[str],
               ref: Optional[np.ndarray] = None,
               axis_fn=None) -> np.ndarray:
    """
    Spinor amplitude for a single path.

    Ψ(p) = exp(−S(p)) · U(p) · |ref⟩    ∈ ℂ²

    ref: reference spinor (default |↑⟩ = [1, 0]).
    Returns 2-component complex vector.
    """
    s = path_tension(L, path)
    if math.isinf(s):
        return np.zeros(2, dtype=complex)
    if ref is None:
        ref = SPINOR_UP.copy()
    U = su2_path_transport(L, path, axis_fn)
    return math.exp(-s) * (U @ ref)


def spinor_sum_paths(L: Landscape, paths: List[List[str]],
                     ref: Optional[np.ndarray] = None,
                     axis_fn=None) -> np.ndarray:
    """
    Spinor superposition.

    Ψ_total = Σ_p Ψ(p)    ∈ ℂ²

    Each path contributes a 2-component spinor.
    Interference happens component-wise.
    """
    total = np.zeros(2, dtype=complex)
    for path in paths:
        total += spinor_psi(L, path, ref, axis_fn)
    return total


def spinor_intensity(L: Landscape, paths: List[List[str]],
                     ref: Optional[np.ndarray] = None,
                     axis_fn=None) -> float:
    """
    Spinor intensity.

    I = ‖Ψ_total‖² = |Ψ₀|² + |Ψ₁|²

    This is the ℂ² norm squared — the spinor analog of |Ψ|² in U(1).
    """
    psi_total = spinor_sum_paths(L, paths, ref, axis_fn)
    return float(np.real(np.vdot(psi_total, psi_total)))


# ── Comparison: U(1) vs SU(2) ─────────────────────────────────────

def compare_u1_su2(L: Landscape, paths: List[List[str]],
                   ref: Optional[np.ndarray] = None,
                   axis_fn=None) -> Dict:
    """
    Side-by-side comparison of U(1) and SU(2) predictions for a path set.

    Returns:
        u1_intensity:    |Σ exp(−S+iΘ)|²
        su2_intensity:   ‖Σ exp(−S)·U·|ref⟩‖²
        ratio:           su2/u1
        deviation_pct:   |su2 − u1| / max(u1, su2) × 100
    """
    from .wavepath import intensity as u1_intensity_fn
    from .wavepath import sum_paths as u1_sum_fn

    u1_psi = u1_sum_fn(L, paths)
    u1_I = abs(u1_psi) ** 2

    su2_psi = spinor_sum_paths(L, paths, ref, axis_fn)
    su2_I = spinor_intensity(L, paths, ref, axis_fn)

    denom = max(u1_I, su2_I, 1e-30)
    return {
        "u1_psi": u1_psi,
        "u1_intensity": u1_I,
        "su2_psi": su2_psi,
        "su2_intensity": su2_I,
        "ratio": su2_I / max(u1_I, 1e-30),
        "deviation_pct": abs(su2_I - u1_I) / denom * 100,
    }


# ── Analysis helpers ───────────────────────────────────────────────

def spinor_path_analysis(L: Landscape, path: List[str],
                         ref: Optional[np.ndarray] = None,
                         axis_fn=None) -> Dict:
    """
    Complete spinor analysis of a single path.
    """
    s = path_tension(L, path)
    w = theta(L, path)
    U = su2_path_transport(L, path, axis_fn)
    psi_vec = spinor_psi(L, path, ref, axis_fn)

    return {
        "path": " → ".join(path),
        "tension": s,
        "theta": w,
        "U": U,
        "det_U": complex(np.linalg.det(U)),
        "trace_U": complex(np.trace(U)),
        "psi": psi_vec,
        "magnitude": float(np.linalg.norm(psi_vec)),
        "intensity": float(np.real(np.vdot(psi_vec, psi_vec))),
    }


def is_identity(M: np.ndarray, tol: float = 1e-10) -> bool:
    """Check if a 2×2 matrix is the identity."""
    return float(np.max(np.abs(M - IDENTITY))) < tol


def is_minus_identity(M: np.ndarray, tol: float = 1e-10) -> bool:
    """Check if a 2×2 matrix is −𝕀."""
    return float(np.max(np.abs(M + IDENTITY))) < tol


def is_su2(M: np.ndarray, tol: float = 1e-10) -> bool:
    """Check if a 2×2 matrix is in SU(2): det = 1, M†M = 𝕀."""
    det_ok = abs(np.linalg.det(M) - 1.0) < tol
    unitary_ok = float(np.max(np.abs(M.conj().T @ M - IDENTITY))) < tol
    return det_ok and unitary_ok


# ═══════════════════════════════════════════════════════════════════
# Phase 4b: Geometry-Derived SU(2) Connection
# ═══════════════════════════════════════════════════════════════════
#
# The rotation axis n̂ is NO LONGER external — it emerges from the
# local Helmholtz vorticity structure of the graph.
#
# Three antisymmetric su(2) components per edge:
#   A₃ = ω(x,y)                    — direct connection
#   A₁ = avg_ω(N(x)\y) − avg_ω(N(y)\x) — vorticity gradient
#   A₂ = avg triangle holonomy     — local gauge curvature
#
# When A₁ = A₂ = 0: reduces to minimal embedding (n̂ = ẑ).
# ═══════════════════════════════════════════════════════════════════


def su2_connection(L: Landscape, x: str, y: str) -> np.ndarray:
    """
    Full su(2) connection vector A⃗(x,y) from local Helmholtz geometry.

    Components (all antisymmetric — A_i(y,x) = −A_i(x,y)):

        A₁ (σ_x): Vorticity gradient across the edge.
            = mean ω at source neighbors − mean ω at target neighbors.
            Non-zero when source and target sit in regions of
            different rotational intensity → the field "tilts."

        A₂ (σ_y): Face holonomy from directed triangles through x→y.
            = mean holonomy of cycles x→y→z→x.
            Non-zero when the local face has gauge curvature.
            Discrete analog of the Yang-Mills field strength F_μν.

        A₃ (σ_z): Direct connection ω(x,y).
            The existing scalar phase — unchanged from Phase 2.

    Returns: 3-vector [A₁, A₂, A₃].
    """
    w = omega(L, x, y)

    # ── A₃: direct connection ────────────────────────────────────
    A3 = w

    # ── A₁: vorticity gradient ──────────────────────────────────
    # Neighbors of x (excluding y) and neighbors of y (excluding x)
    nbr_x = [e.target for e in L.edges if e.source == x and e.target != y]
    nbr_y = [e.target for e in L.edges if e.source == y and e.target != x]

    avg_omega_x = float(np.mean([omega(L, x, z) for z in nbr_x])) if nbr_x else 0.0
    avg_omega_y = float(np.mean([omega(L, y, z) for z in nbr_y])) if nbr_y else 0.0
    A1 = avg_omega_x - avg_omega_y

    # ── A₂: face holonomy (directed triangles x→y→z→x) ─────────
    # z must be reachable from y AND have an edge back to x
    y_targets = {e.target for e in L.edges if e.source == y}
    z_closing = {e.source for e in L.edges if e.target == x}
    triangles = (y_targets & z_closing) - {x, y}

    if triangles:
        holonomies = [omega(L, x, y) + omega(L, y, z) + omega(L, z, x)
                      for z in sorted(triangles)]
        A2 = float(np.mean(holonomies))
    else:
        A2 = 0.0

    return np.array([A1, A2, A3])


def su2_geometric_transport(L: Landscape, x: str, y: str) -> np.ndarray:
    """
    SU(2) edge transport using geometry-derived connection.

    U(x,y) = exp(−i/2 · A⃗(x,y) · σ⃗)

    where A⃗ = (A₁, A₂, A₃) comes from su2_connection().
    Total angle = ‖A⃗‖, axis = A⃗/‖A⃗‖.

    When A₁ = A₂ = 0: U = exp(−i·ω/2·σ_z) — identical to minimal.
    """
    A = su2_connection(L, x, y)
    norm = float(np.linalg.norm(A))
    if norm < 1e-15:
        return IDENTITY.copy()
    return pauli_exponential(norm, A / norm)


def su2_geometric_path_transport(L: Landscape, path: List[str]) -> np.ndarray:
    """
    SU(2) path transport using geometry-derived connection.

    U(p) = U(e_n) · U(e_{n-1}) · ... · U(e_1)

    Each edge uses su2_geometric_transport (full A⃗ coupling).
    """
    if len(path) < 2:
        return IDENTITY.copy()
    U = IDENTITY.copy()
    for i in range(len(path) - 1):
        U_edge = su2_geometric_transport(L, path[i], path[i + 1])
        U = U_edge @ U
    return U


def spinor_geometric_psi(L: Landscape, path: List[str],
                         ref: Optional[np.ndarray] = None) -> np.ndarray:
    """
    Spinor amplitude with geometry-derived SU(2) transport.

    Ψ(p) = exp(−S(p)) · U_geo(p) · |ref⟩   ∈ ℂ²
    """
    s = path_tension(L, path)
    if math.isinf(s):
        return np.zeros(2, dtype=complex)
    if ref is None:
        ref = SPINOR_UP.copy()
    U = su2_geometric_path_transport(L, path)
    return math.exp(-s) * (U @ ref)


def spinor_geometric_sum(L: Landscape, paths: List[List[str]],
                         ref: Optional[np.ndarray] = None) -> np.ndarray:
    """Spinor superposition with geometry-derived transport."""
    total = np.zeros(2, dtype=complex)
    for path in paths:
        total += spinor_geometric_psi(L, path, ref)
    return total


def spinor_geometric_intensity(L: Landscape, paths: List[List[str]],
                               ref: Optional[np.ndarray] = None) -> float:
    """Spinor intensity with geometry-derived transport: I = ‖Σ Ψ_geo‖²."""
    psi = spinor_geometric_sum(L, paths, ref)
    return float(np.real(np.vdot(psi, psi)))


def compare_minimal_geometric(L: Landscape, paths: List[List[str]],
                              ref: Optional[np.ndarray] = None) -> Dict:
    """
    Compare minimal (n̂ = ẑ) vs geometric (Helmholtz-derived) SU(2).

    Returns intensities and deviation for all three theories:
    U(1), SU(2)-minimal, SU(2)-geometric.
    """
    from .wavepath import sum_paths as u1_sum_fn

    u1_psi = u1_sum_fn(L, paths)
    u1_I = abs(u1_psi) ** 2

    min_I = spinor_intensity(L, paths, ref)
    geo_I = spinor_geometric_intensity(L, paths, ref)

    denom = max(u1_I, min_I, geo_I, 1e-30)
    return {
        "u1_intensity": u1_I,
        "minimal_intensity": min_I,
        "geometric_intensity": geo_I,
        "min_vs_u1_pct": abs(min_I - u1_I) / denom * 100,
        "geo_vs_u1_pct": abs(geo_I - u1_I) / denom * 100,
        "geo_vs_min_pct": abs(geo_I - min_I) / denom * 100,
    }


def connection_analysis(L: Landscape, x: str, y: str) -> Dict:
    """
    Detailed analysis of the su(2) connection on edge x→y.

    Shows all three components and the resulting axis/angle.
    """
    A = su2_connection(L, x, y)
    norm = float(np.linalg.norm(A))
    axis = A / norm if norm > 1e-15 else np.array([0.0, 0.0, 1.0])

    U_min = su2_edge_transport(L, x, y)
    U_geo = su2_geometric_transport(L, x, y)

    return {
        "edge": f"{x}→{y}",
        "omega": omega(L, x, y),
        "A_vector": A,
        "A_norm": norm,
        "axis": axis,
        "off_axis_fraction": float(np.sqrt(A[0]**2 + A[1]**2) / norm) if norm > 1e-15 else 0.0,
        "U_minimal": U_min,
        "U_geometric": U_geo,
        "transport_deviation": float(np.max(np.abs(U_geo - U_min))),
    }
