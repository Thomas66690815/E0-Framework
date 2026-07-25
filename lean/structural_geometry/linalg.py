"""
structural_geometry.linalg — minimal linear algebra, zero dependencies.
=======================================================================

Only what the Helmholtz solve needs:

    solve_spd_dense(A, b)   — Cholesky, exact, O(n³/3). Best for n ≲ 400.
    solve_cg(matvec, b)     — conjugate gradients, sparse, O(nnz · iters).

Both expect a symmetric positive-definite system.  The reduced graph
Laplacian (one node pinned per connected component) is exactly that.

Why two solvers
---------------
The parent framework uses ``numpy.linalg.lstsq`` on a dense n×n matrix.
That is correct but allocates O(n²) and costs O(n³) regardless of how
sparse the graph is.  Navigation graphs are extremely sparse (a 4-connected
grid has ~4 edges per node), so conjugate gradients on the sparse operator
is the better default above a few hundred nodes.

``solve_cg`` never materialises the matrix — it only needs a matrix-vector
product, which the Laplacian provides in O(edges).

# e0-structural-geometry-twehner
"""

from __future__ import annotations

import math
from typing import Callable, List, Sequence

__all__ = ["solve_spd_dense", "solve_cg", "CholeskyError"]


class CholeskyError(ValueError):
    """Raised when a matrix is not positive definite."""


def solve_spd_dense(A: List[List[float]], b: Sequence[float]) -> List[float]:
    """Solve ``A x = b`` for symmetric positive-definite ``A`` via Cholesky.

    ``A`` is consumed as a nested list and is *not* modified.
    Raises :class:`CholeskyError` if ``A`` is not positive definite.
    """
    n = len(A)
    if n == 0:
        return []
    if len(b) != n:
        raise ValueError(f"dimension mismatch: A is {n}x{n}, b has {len(b)}")

    # Lower-triangular Cholesky factor: A = L Lᵀ
    L = [[0.0] * n for _ in range(n)]
    for i in range(n):
        row_i = L[i]
        for j in range(i + 1):
            row_j = L[j]
            acc = A[i][j]
            for k in range(j):
                acc -= row_i[k] * row_j[k]
            if i == j:
                if acc <= 0.0:
                    raise CholeskyError(
                        f"matrix is not positive definite (pivot {acc!r} at index {i})"
                    )
                row_i[j] = math.sqrt(acc)
            else:
                row_i[j] = acc / row_j[j]

    # Forward substitution: L y = b
    y = [0.0] * n
    for i in range(n):
        acc = b[i]
        row_i = L[i]
        for k in range(i):
            acc -= row_i[k] * y[k]
        y[i] = acc / row_i[i]

    # Back substitution: Lᵀ x = y
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        acc = y[i]
        for k in range(i + 1, n):
            acc -= L[k][i] * x[k]
        x[i] = acc / L[i][i]
    return x


def solve_cg(
    matvec: Callable[[Sequence[float]], List[float]],
    b: Sequence[float],
    *,
    tol: float = 1e-10,
    max_iter: int | None = None,
) -> List[float]:
    """Solve ``A x = b`` by conjugate gradients, given only ``A``'s action.

    Parameters
    ----------
    matvec:
        Callable mapping a vector to ``A @ vector``.  ``A`` must be
        symmetric positive-definite; it is never materialised.
    b:
        Right-hand side.
    tol:
        Relative residual tolerance ``‖r‖ / ‖b‖``.
    max_iter:
        Iteration cap.  Defaults to ``max(2 · len(b), 64)``.
    """
    n = len(b)
    if n == 0:
        return []
    if max_iter is None:
        max_iter = max(2 * n, 64)

    b_norm = math.sqrt(sum(v * v for v in b))
    if b_norm == 0.0:
        return [0.0] * n

    x = [0.0] * n
    r = list(b)                      # r = b − A·0
    p = list(r)
    rs_old = sum(v * v for v in r)

    for _ in range(max_iter):
        if math.sqrt(rs_old) / b_norm <= tol:
            break
        ap = matvec(p)
        denom = sum(p[i] * ap[i] for i in range(n))
        if denom <= 0.0:
            # Not positive definite along p — stop with what we have.
            break
        alpha = rs_old / denom
        for i in range(n):
            x[i] += alpha * p[i]
            r[i] -= alpha * ap[i]
        rs_new = sum(v * v for v in r)
        beta = rs_new / rs_old
        for i in range(n):
            p[i] = r[i] + beta * p[i]
        rs_old = rs_new

    return x
