"""
E₀ Structural Core Envelope
=============================
Typed configuration object for E₀ controller runs.

The E0Envelope captures the Core block of the structural schema:
mode, geometry, horizon, transport regime, goals, and tuning
parameters — everything needed to configure an E₀ controller
from a single, serializable object.

Design principles:
  - Envelope = configuration declaration, not data container.
    Landscape (states + edges) is separate.
  - Backward compatible: to_controller_kwargs() produces the dict
    that E0Controller.__init__(**kwargs) already accepts.
  - Serializable: to_dict() / from_dict() for JSON / MemOS.
  - Transport is a typed enum, not a boolean/string hack.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, FrozenSet, Optional, Set

from .primitives import TransportRegime
from .override_gate import OverrideGatePolicy


# Re-import HybridMode here to avoid forcing users to import from controller
from .controller import HybridMode


# ──────────────────────────────────────────────
# Transport ↔ use_su2 bridge
# ──────────────────────────────────────────────

def transport_to_use_su2(transport: TransportRegime) -> object:
    """Convert TransportRegime enum to legacy use_su2 value."""
    if transport == TransportRegime.SU2_GEOMETRIC:
        return "geometric"
    if transport == TransportRegime.SU2_MINIMAL:
        return True
    return False


def use_su2_to_transport(use_su2: object) -> TransportRegime:
    """Convert legacy use_su2 value to TransportRegime enum."""
    if use_su2 == "geometric":
        return TransportRegime.SU2_GEOMETRIC
    if use_su2:
        return TransportRegime.SU2_MINIMAL
    return TransportRegime.U1


# ──────────────────────────────────────────────
# E0Envelope
# ──────────────────────────────────────────────

@dataclass(frozen=True)
class E0Envelope:
    """Typed controller configuration envelope (Core block).

    Contains all parameters needed to configure an E₀ controller.
    Immutable (frozen) to ensure configuration integrity.

    Usage::

        env = E0Envelope(
            mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            geometry="goal_reaching",
            horizon=4,
            transport=TransportRegime.U1,
            goals=frozenset({"GOAL"}),
        )
        ctrl = E0Controller(landscape, execute_fn, **env.to_controller_kwargs())
    """

    # Mode & geometry
    mode: HybridMode = HybridMode.GREEDY
    geometry: str = "simple"
    horizon: int = 3
    transport: TransportRegime = TransportRegime.U1

    # Goals (frozenset for immutability)
    goals: Optional[FrozenSet[str]] = None

    # Controller tuning parameters
    alpha: float = 2.0
    s_max: float = math.inf
    c_min: float = 0.0
    confidence_threshold: float = 0.0
    override_policy: Optional[OverrideGatePolicy] = None

    def __post_init__(self) -> None:
        if self.override_policy is None:
            return
        expected = self.override_policy.legacy_threshold_alias
        if not math.isclose(self.confidence_threshold, expected):
            raise ValueError(
                "confidence_threshold must match override_policy "
                f"compatibility alias ({expected})"
            )

    def to_controller_kwargs(self) -> Dict[str, Any]:
        """Convert to kwargs dict for E0Controller.__init__.

        Produces backward-compatible parameters including the legacy
        use_su2 value derived from transport regime.
        """
        kwargs: Dict[str, Any] = {
            "hybrid_mode": self.mode,
            "hybrid_geometry": self.geometry,
            "hybrid_horizon": self.horizon,
            "use_su2": transport_to_use_su2(self.transport),
            "alpha": self.alpha,
            "s_max": self.s_max,
            "c_min": self.c_min,
            "confidence_threshold": self.confidence_threshold,
        }
        if self.goals is not None:
            kwargs["hybrid_goals"] = set(self.goals)
        if self.override_policy is not None:
            kwargs["override_policy"] = self.override_policy
        return kwargs

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        d: Dict[str, Any] = {
            "mode": self.mode.value,
            "geometry": self.geometry,
            "horizon": self.horizon,
            "transport": self.transport.value,
            "alpha": self.alpha,
            "c_min": self.c_min,
            "confidence_threshold": self.confidence_threshold,
        }
        # s_max: inf → null in JSON
        d["s_max"] = None if math.isinf(self.s_max) else self.s_max
        if self.goals is not None:
            d["goals"] = sorted(self.goals)
        if self.override_policy is not None:
            d["override_policy"] = self.override_policy.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> E0Envelope:
        """Deserialize from dict."""
        goals_raw = d.get("goals")
        goals = frozenset(goals_raw) if goals_raw is not None else None
        s_max = d.get("s_max")
        if s_max is None:
            s_max = math.inf
        policy_raw = d.get("override_policy")
        override_policy = (
            OverrideGatePolicy.from_dict(policy_raw)
            if policy_raw is not None
            else None
        )
        return cls(
            mode=HybridMode(d.get("mode", "greedy")),
            geometry=d.get("geometry", "simple"),
            horizon=d.get("horizon", 3),
            transport=TransportRegime(d.get("transport", "u1")),
            goals=goals,
            alpha=d.get("alpha", 2.0),
            s_max=s_max,
            c_min=d.get("c_min", 0.0),
            confidence_threshold=d.get("confidence_threshold", 0.0),
            override_policy=override_policy,
        )

    @classmethod
    def from_controller(cls, ctrl) -> E0Envelope:
        """Extract envelope from a configured E0Controller."""
        return cls(
            mode=ctrl.hybrid_mode,
            geometry=ctrl.hybrid_geometry,
            horizon=ctrl.hybrid_horizon,
            transport=use_su2_to_transport(ctrl.use_su2),
            goals=(frozenset(ctrl.hybrid_goals)
                   if ctrl.hybrid_goals is not None else None),
            alpha=ctrl.alpha,
            s_max=ctrl.s_max,
            c_min=ctrl.c_min,
            confidence_threshold=ctrl.confidence_threshold,
            override_policy=ctrl.override_policy,
        )

    def summary(self) -> str:
        """Human-readable one-line summary."""
        parts = [
            f"mode={self.mode.value}",
            f"geometry={self.geometry}",
            f"h={self.horizon}",
            f"transport={self.transport.value}",
        ]
        if self.goals:
            parts.append(f"goals={{{','.join(sorted(self.goals))}}}")
        if self.confidence_threshold > 0:
            parts.append(f"conf={self.confidence_threshold}")
        if self.override_policy is not None:
            parts.append(f"policy={self.override_policy.policy_id}")
        if self.alpha != 2.0:
            parts.append(f"α={self.alpha}")
        return f"E0Envelope({', '.join(parts)})"
