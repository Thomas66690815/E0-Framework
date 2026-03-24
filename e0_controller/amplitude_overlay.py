"""
E₀ Controller — Amplitude Overlay (analysis only)
=================================================

Bounded-horizon analysis layer that compares the current deterministic
controller choice against amplitude-derived support over the same local
candidate set.

This module is intentionally NON-invasive:
- it does not change controller behavior,
- it does not sample actions,
- it does not replace argmin(S_penalized),
- it only computes an alternative support view for inspection.

Core idea
---------
For the current controller state x and each admissible next action y,
compute a bounded family of continuations starting with x→y:

    Ψ_action(y; h) = Σ_{p starts at x, first hop y, len(p)≤h} Ψ(p)

where

    Ψ(p) = exp(-S(p)) * exp(iΘ(p))

using the existing wavepath / connection machinery.

Then derive:

    I_action(y; h) = |Ψ_action(y; h)|²
    P_action(y; h) = I_action(y; h) / Σ I_action

This lets us compare:
- current controller ranking      (argmin penalized tension)
- amplitude support ranking       (argmax intensity)
- Born-like normalized support    (P_action)

without modifying the operational controller.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set

from .controller import E0Controller
from .wavepath import psi as path_psi


# Supported summation geometries (§4 of Summation Geometry Program)
GEOMETRIES = ("prefix", "simple", "first_arrival", "goal_reaching")


@dataclass
class ActionAmplitudeInfo:
    """Analysis bundle for one immediate action y from current state x."""
    action: str
    direct_s_eff: float
    penalized_s: float
    path_count: int
    paths: List[List[str]]
    psi_total: complex
    intensity: float
    probability: float = 0.0


@dataclass
class OverlayReport:
    """Comparison between deterministic controller choice and amplitude view."""
    current: str
    horizon_edges: int
    geometry: str
    admissible_actions: List[str]
    deterministic_choice: str | None
    deterministic_escalated: bool
    action_infos: List[ActionAmplitudeInfo]

    @property
    def amplitude_choice(self) -> str | None:
        if not self.action_infos:
            return None
        return max(self.action_infos, key=lambda a: a.intensity).action

    def summary(self) -> str:
        lines = [
            f"OverlayReport(current={self.current!r}, horizon_edges={self.horizon_edges}, geometry={self.geometry!r})",
            f"  admissible: {self.admissible_actions}",
            f"  controller_choice: {self.deterministic_choice!r}",
            f"  amplitude_choice: {self.amplitude_choice!r}",
        ]
        for info in sorted(self.action_infos, key=lambda a: a.intensity, reverse=True):
            lines.append(
                "  "
                f"{info.action}: I={info.intensity:.6f}, P={info.probability:.6f}, "
                f"paths={info.path_count}, S_eff={info.direct_s_eff:.6f}, "
                f"S_pen={info.penalized_s:.6f}"
            )
        return "\n".join(lines)


def _enumerate_continuations(
    controller: E0Controller,
    current: str,
    horizon_edges: int,
    geometry: str = "simple",
    goals: Optional[Set[str]] = None,
) -> List[List[str]]:
    """
    Enumerate bounded admissible paths from current state.

    Paths are returned as state lists [x0, x1, ..., xn].

    Geometry modes (§4 Summation Geometry Program):

    - "prefix":  Include every admissible prefix path with length 1..horizon_edges.
                  Current baseline — measures total coherent forward support.
    - "simple":  Include only paths with no repeated states (G4).
                  Suppresses loop inflation.
    - "first_arrival":  Include only paths that stop upon first reaching a goal
                         state (G3).  Requires `goals` set.  Non-goal prefixes
                         are still included (intermediate support).
    - "goal_reaching":  Include only paths whose final state is in `goals` (G5).
                         Requires `goals` set.  Non-goal prefixes are excluded.
                         Born-criterion aligned: only transition-completing paths
                         contribute to interference.
    """
    if horizon_edges <= 0:
        return []
    if geometry not in GEOMETRIES:
        raise ValueError(f"Unknown geometry {geometry!r}. Must be one of {GEOMETRIES}")
    if geometry in ("first_arrival", "goal_reaching") and not goals:
        raise ValueError(f"{geometry} geometry requires a non-empty goals set")

    results: List[List[str]] = []

    def dfs(path: List[str], depth_used: int) -> None:
        if depth_used >= horizon_edges:
            return
        x = path[-1]

        # first_arrival / goal_reaching: stop extending once we've reached a goal
        if geometry in ("first_arrival", "goal_reaching") and x in goals and depth_used > 0:
            return

        neighbors = controller._admissible_neighbors(x)
        for y in neighbors:
            # simple-path: skip if state already visited
            if geometry == "simple" and y in path:
                continue

            new_path = path + [y]
            # goal_reaching: only include paths that end at a goal state
            if geometry == "goal_reaching":
                if new_path[-1] in goals:
                    results.append(new_path)
            else:
                results.append(new_path)
            dfs(new_path, depth_used + 1)

    dfs([current], 0)
    return results


def _filter_paths_by_first_action(paths: Sequence[List[str]], action: str) -> List[List[str]]:
    """Keep only paths whose first hop is the given action."""
    return [p for p in paths if len(p) >= 2 and p[1] == action]


def analyze_controller_state(
    controller: E0Controller,
    current: str,
    horizon_edges: int = 3,
    geometry: str = "simple",
    goals: Optional[Set[str]] = None,
) -> OverlayReport:
    """
    Build an analysis-only amplitude overlay for one controller decision point.

    Parameters
    ----------
    controller:
        Existing E0Controller instance.
    current:
        Current controller state.
    horizon_edges:
        Maximum path length (in edges) used for bounded continuation analysis.
        Must be >= 1. Small values (2–4) are recommended.
    geometry:
        Summation geometry — "prefix" (default/G1), "simple" (G4),
        "first_arrival" (G3), "goal_reaching" (G5).
    goals:
        Required for "first_arrival" and "goal_reaching" geometries.
        Set of goal states.
    """
    if horizon_edges < 1:
        raise ValueError("horizon_edges must be >= 1")

    # Current controller decision (without changing controller state).
    deterministic_choice, escalated, _esc_type = controller.select_next(current)
    admissible = controller._admissible_neighbors(current)

    # Enumerate bounded admissible continuations from the current state.
    all_paths = _enumerate_continuations(controller, current, horizon_edges,
                                          geometry=geometry, goals=goals)

    action_infos: List[ActionAmplitudeInfo] = []
    total_intensity = 0.0

    for action in admissible:
        action_paths = _filter_paths_by_first_action(all_paths, action)

        # Safety fallback: ensure the direct one-edge path exists in the analysis set.
        # For goal_reaching, skip unless the action itself is a goal state.
        if [current, action] not in action_paths:
            if geometry != "goal_reaching" or (goals and action in goals):
                action_paths = [[current, action]] + action_paths

        psi_total = sum((path_psi(controller.landscape, p) for p in action_paths), start=complex(0.0, 0.0))
        intensity = abs(psi_total) ** 2
        info = ActionAmplitudeInfo(
            action=action,
            direct_s_eff=controller._effective_tension(current, action),
            penalized_s=controller._penalized_tension(current, action),
            path_count=len(action_paths),
            paths=action_paths,
            psi_total=psi_total,
            intensity=intensity,
        )
        action_infos.append(info)
        total_intensity += intensity

    if total_intensity > 0.0:
        for info in action_infos:
            info.probability = info.intensity / total_intensity

    # Sort highest-support first for readability.
    action_infos.sort(key=lambda a: a.intensity, reverse=True)

    return OverlayReport(
        current=current,
        horizon_edges=horizon_edges,
        geometry=geometry,
        admissible_actions=admissible,
        deterministic_choice=deterministic_choice,
        deterministic_escalated=escalated,
        action_infos=action_infos,
    )
