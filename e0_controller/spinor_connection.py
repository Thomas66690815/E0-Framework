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

Convention:
    Rotation axis n̂: For a single edge x→y, v_rot defines a scalar.
    We embed this into SU(2) by choosing n̂ = ẑ (σ_z generator),
    which reduces SU(2) to U(1) for single-axis rotations.
    Multi-axis structure emerges only when the graph has loops
    through states with different local orientations.

    This is the MINIMAL embedding: maximally conservative, reduces
    to the existing U(1) theory in the absence of non-trivial topology.

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
