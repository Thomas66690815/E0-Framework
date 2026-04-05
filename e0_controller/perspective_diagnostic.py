"""E₀ SU(2) Perspective Diagnostic (C153)
========================================
Compares action rankings under U(1) and SU(2) interference to detect
perspective-dependent assessments.

When U(1) and SU(2) agree on the best action, the structure is
perspective-robust — parameters can be tuned within the current frame.
When they disagree, the structure is perspective-fragile — the frame
itself may be the problem. This is meta-cognition: not "which parameter
is wrong?" but "is my observation angle wrong?"

Three layers of E0 meta-cognition:
  - Structural Entropy removes (local)
  - Dream Mode discovers (lateral)
  - SU(2) Perspective validates (vertical)

Usage::

    from e0_controller.perspective_diagnostic import perspective_check

    report = perspective_check(controller, current="S", horizon=3)
    if report and report.fragile:
        print("Frame questioning triggered")
        for action in report.fragile_actions:
            print(f"  {action}: perspective-dependent ranking")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from .controller import E0Controller

from .amplitude_overlay import OverlayReport, analyze_controller_state


# ──────────────────────────────────────────────
# 1. Data Structures
# ──────────────────────────────────────────────

@dataclass
class PerspectiveReport:
    """Result of comparing U(1) vs SU(2) action rankings at one decision point.

    Attributes:
        current: State where the comparison was made
        u1_ranking: Actions ordered by U(1) intensity (descending)
        su2_ranking: Actions ordered by SU(2) intensity (descending)
        geo_ranking: Actions ordered by geometric SU(2) (if computed)
        top_agrees: Whether U(1) and SU(2) agree on the best action
        ranking_agreement: Fraction of pairwise orderings that agree [0, 1]
        robust: True if the ranking is perspective-stable (top action agrees)
        fragile_actions: Actions whose rank position changed between perspectives
        u1_intensities: Per-action U(1) intensities
        su2_intensities: Per-action SU(2) intensities
        geo_intensities: Per-action geometric SU(2) intensities (if computed)
    """
    current: str
    u1_ranking: List[str]
    su2_ranking: List[str]
    geo_ranking: Optional[List[str]] = None

    top_agrees: bool = True
    ranking_agreement: float = 1.0
    robust: bool = True

    fragile_actions: List[str] = field(default_factory=list)

    u1_intensities: Dict[str, float] = field(default_factory=dict)
    su2_intensities: Dict[str, float] = field(default_factory=dict)
    geo_intensities: Optional[Dict[str, float]] = None

    @property
    def fragile(self) -> bool:
        """Inverse of robust — perspective-dependent assessment detected."""
        return not self.robust


# ──────────────────────────────────────────────
# 2. Ranking Extraction & Comparison
# ──────────────────────────────────────────────

def _ranking_from_overlay(report: OverlayReport) -> tuple:
    """Extract (ranking, intensities) from an OverlayReport.

    Returns:
        ranking: List of action names sorted by intensity descending
        intensities: Dict of action → intensity
    """
    infos = sorted(report.action_infos, key=lambda a: a.intensity, reverse=True)
    ranking = [a.action for a in infos]
    intensities = {a.action: a.intensity for a in infos}
    return ranking, intensities


def _ranking_agreement(ranking_a: List[str], ranking_b: List[str]) -> float:
    """Pairwise ranking agreement (Kendall tau variant).

    Returns 1.0 for identical rankings, 0.0 for completely reversed.
    For ≤1 action, returns 1.0 (trivially robust).
    """
    n = len(ranking_a)
    if n <= 1:
        return 1.0

    pos_b = {action: i for i, action in enumerate(ranking_b)}

    concordant = 0
    total = 0
    for i in range(n):
        for j in range(i + 1, n):
            a_i, a_j = ranking_a[i], ranking_a[j]
            if pos_b[a_i] < pos_b[a_j]:
                concordant += 1
            total += 1

    return concordant / total


def _fragile_actions(ranking_a: List[str], ranking_b: List[str]) -> List[str]:
    """Actions whose rank position changed between two rankings."""
    pos_a = {action: i for i, action in enumerate(ranking_a)}
    pos_b = {action: i for i, action in enumerate(ranking_b)}
    return [action for action in ranking_a if pos_a[action] != pos_b[action]]


# ──────────────────────────────────────────────
# 3. Core Diagnostic Function
# ──────────────────────────────────────────────

def perspective_check(
    controller: "E0Controller",
    current: str,
    horizon: int = 3,
    geometry: str = "simple",
    goals: Optional[Set[str]] = None,
    include_geometric: bool = False,
) -> Optional[PerspectiveReport]:
    """Compare action rankings under U(1) vs SU(2) interference.

    Runs analyze_controller_state twice (U(1) and SU(2) minimal) on
    the same decision point and compares the resulting action rankings.

    Parameters:
        controller: E0Controller with a landscape
        current: Current state to analyze
        horizon: Path horizon for overlay computation (edges)
        geometry: Overlay geometry mode
        goals: Optional goal states for overlay
        include_geometric: Also compute geometric SU(2) ranking

    Returns:
        PerspectiveReport, or None if fewer than 2 admissible actions
        (perspective comparison requires at least 2 choices)
    """
    # U(1) overlay
    u1_report = analyze_controller_state(
        controller, current,
        horizon_edges=horizon,
        geometry=geometry,
        goals=goals,
        use_su2=False,
    )

    if len(u1_report.action_infos) < 2:
        return None

    # SU(2) minimal overlay
    su2_report = analyze_controller_state(
        controller, current,
        horizon_edges=horizon,
        geometry=geometry,
        goals=goals,
        use_su2=True,
        axis_fn=getattr(controller, "axis_fn", None),
    )

    u1_ranking, u1_intensities = _ranking_from_overlay(u1_report)
    su2_ranking, su2_intensities = _ranking_from_overlay(su2_report)

    top_agrees = u1_ranking[0] == su2_ranking[0]
    agreement = _ranking_agreement(u1_ranking, su2_ranking)
    fragile = _fragile_actions(u1_ranking, su2_ranking)

    # Optional geometric comparison
    geo_ranking = None
    geo_intensities = None
    if include_geometric:
        geo_report = analyze_controller_state(
            controller, current,
            horizon_edges=horizon,
            geometry=geometry,
            goals=goals,
            use_su2="geometric",
        )
        geo_ranking, geo_intensities = _ranking_from_overlay(geo_report)

    return PerspectiveReport(
        current=current,
        u1_ranking=u1_ranking,
        su2_ranking=su2_ranking,
        geo_ranking=geo_ranking,
        top_agrees=top_agrees,
        ranking_agreement=agreement,
        robust=top_agrees,
        fragile_actions=fragile,
        u1_intensities=u1_intensities,
        su2_intensities=su2_intensities,
        geo_intensities=geo_intensities,
    )
