"""
E₀ Controller — Potential & Spec-Aligned Decomposition
========================================================
Diskrete Zerlegung des Transitionsfelds in Gradient- und Rotationskomponente.

Spec coverage: §9 (Lokales Potential Φ), §10 (v_grad), §11 (v_rot).

Core equations:
    Φ(x)         = Σ_{y ∈ N(x)} Δ(x,y) · R_eff(x,y)     — §9 Lokales Potential
    v_grad(x, y) = Φ(x) − Φ(y)                            — §10 Gradient-Komponente
    v_rot(x, y)  = v(x, y) − v_grad(x, y)                 — §11 Rotations-Komponente

Mathematische Anmerkung:
    Die Spec definiert Φ als lokale Summation über Nachbarn, nicht als Lösung
    eines Graph-Laplacian-Systems. Das bedeutet: v_grad ist die konservative
    Komponente, die sich aus Potenzial-Differenzen ergibt. v_rot ist der
    verbleibende nicht-integrable Rest — genau die Komponente, die Holonomie ≠ 0
    erzeugen kann.

    WICHTIG: Diese Zerlegung ist NICHT eine volle diskrete Helmholtz-Zerlegung
    (die min ||v_rot||² über den Graph-Laplacian L = D − A löst). Die
    Spec-Zerlegung ist deterministisch und berechenbar, aber v_rot ist im
    Allgemeinen nicht orthogonal zu v_grad. Wir nennen sie deshalb bewusst
    "Spec-Aligned Decomposition", nicht "Helmholtz-Zerlegung".

    Für spätere Versionen kann eine echte diskrete Helmholtz-Zerlegung
    implementiert werden.

Konvention für gerichtete Kanten:
    - v(x, y) ist nur definiert, wenn Kante x→y existiert.
    - Φ(x) summiert nur über existierende Ausgangskanten.
    - v_grad(x, y) = Φ(x) − Φ(y) ist auch definiert, wenn keine direkte
      Kante x→y existiert. Aber v_rot(x, y) ist nur sinnvoll für existierende
      Kanten.
    - Fehlende Kante → v(x, y) = 0.0 (keine Transitionskapazität).
"""

from __future__ import annotations

from typing import Dict, Optional

from .landscape import Landscape


def phi(L: Landscape, x: str) -> float:
    """
    §9: Lokales Potential.

    Φ(x) = Σ_{y ∈ N(x)} Δ(x,y) · R_eff(x,y)

    Summe der Tension-Beiträge über alle Ausgangskanten.
    States ohne Ausgangskanten (Dead-Ends) haben Φ = 0.

    Interpretationshinweis (C2): Φ = 0 bei Dead-Ends bedeutet "keine
    ausgehenden Beiträge", NICHT "ontologisch spannungsfrei". Ein
    Dead-End kann durchaus innere Spannung tragen — es hat lediglich
    keine definierten Ausgangstransitionen, über die sich diese Spannung
    als Potential manifestieren könnte.

    Allgemein: Φ(x) misst die „strukturelle Spannung" eines Zustands.
    Hohe Φ = viel unaufgelöste Differenz, starker Druck zur Transition.
    """
    total = 0.0
    for edge in L.edges:
        if edge.source == x:
            delta = L.difference(x, edge.target)
            if delta is not None:
                r_eff = L.effective_resistance(x, edge.target)
                if not _is_inf(r_eff):
                    total += delta * r_eff
    return total


def phi_map(L: Landscape) -> Dict[str, float]:
    """Φ(x) for all states. Convenience function."""
    return {x: phi(L, x) for x in L.states}


def v_raw(L: Landscape, x: str, y: str) -> float:
    """
    §2.4: Transition field v(x, y) = Δ(x,y) · exp(-S_eff(x→y))

    Wraps Landscape.transition_field().
    Returns 0.0 if edge does not exist (no transition capacity).
    """
    return L.transition_field(x, y)


def v_grad(L: Landscape, x: str, y: str) -> float:
    """
    §10: Gradient-Komponente des Transitionsfelds.

    v_grad(x, y) = Φ(x) − Φ(y)

    The conservative part — derivable from a potential function.
    Can be computed for any pair of states, even without a direct edge.

    Positive: x has higher potential than y (downhill transition).
    Negative: y has higher potential (uphill transition).
    Zero: even potential (no gradient drive).
    """
    return phi(L, x) - phi(L, y)


def v_rot(L: Landscape, x: str, y: str) -> Optional[float]:
    """
    §11: Rotations-Komponente des Transitionsfelds.

    v_rot(x, y) = v(x, y) − v_grad(x, y)

    The non-conservative remainder — this is what creates holonomy.
    Only defined for edges that actually exist in the landscape.

    Returns None if edge x→y does not exist (v_rot is undefined there).

    Konvention für fehlende Rückkanten:
        Wenn Kante y→x nicht existiert, ist v_rot(y, x) nicht berechenbar.
        Dieses Modul gibt None zurück. Die Connection-Schicht (connection.py)
        definiert die ω-Konvention für diesen Fall.
    """
    delta = L.difference(x, y)
    if delta is None:
        return None  # Edge does not exist
    v = v_raw(L, x, y)
    vg = v_grad(L, x, y)
    return v - vg


def decomposition(L: Landscape, x: str, y: str) -> Dict[str, Optional[float]]:
    """
    Full v-decomposition for an edge.

    Returns:
        v_raw:  transition field value (0.0 if no edge)
        v_grad: gradient component (always computable)
        v_rot:  rotation component (None if no edge)
        phi_x:  potential at source
        phi_y:  potential at target
    """
    return {
        "v_raw": v_raw(L, x, y),
        "v_grad": v_grad(L, x, y),
        "v_rot": v_rot(L, x, y),
        "phi_x": phi(L, x),
        "phi_y": phi(L, y),
    }


def decomposition_table(L: Landscape) -> list:
    """
    Full decomposition for all edges in the landscape.
    Returns list of dicts, one per edge.
    """
    rows = []
    for edge in L.edges:
        d = decomposition(L, edge.source, edge.target)
        d["edge"] = str(edge)
        d["source"] = edge.source
        d["target"] = edge.target
        rows.append(d)
    return rows


def _is_inf(val: float) -> bool:
    """Check for infinity."""
    import math
    return math.isinf(val)
