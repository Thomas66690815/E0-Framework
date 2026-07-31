"""Versioned override-gate policies with exact legacy mappings.

The historical ``confidence_threshold`` value is a support margin
(``P_best - P_second``), not a calibrated success probability.  This module
keeps the scalar API available while making the complete gate contract
serializable and explicit.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, replace
from enum import Enum
from types import MappingProxyType
from typing import Any, Dict, Mapping, Optional

SCORE_SEMANTICS = "probability_gap_best_minus_second"
DISABLED_LEGACY_THRESHOLD = 1.01
REVISIT_GUARDS = {"none", "controller_if_self_graph_present"}
HEALTH_GUARDS = {"none", "self_graph_if_present"}


class OverrideGateMode(str, Enum):
    """Lifecycle mode of an override-gate policy."""

    DISABLED = "disabled"
    LEGACY_FIXED = "legacy_fixed"
    FIXED = "fixed"
    CALIBRATED = "calibrated"


def _freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _freeze_json(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    raise TypeError(f"Policy metadata is not JSON-compatible: {type(value).__name__}")


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


@dataclass(frozen=True)
class OverrideGatePolicy:
    """Immutable, serializable contract for lookahead overrides."""

    policy_id: str
    policy_version: str
    mode: OverrideGateMode
    min_support_margin: Optional[float]
    max_path_imbalance: Optional[float]
    forbid_path_cap_hit: bool
    revisit_guard: str
    health_guard: str
    scope: Mapping[str, Any] = field(default_factory=dict)
    provenance: Mapping[str, Any] = field(default_factory=dict)
    calibration_artifact: Optional[str] = None
    score_semantics: str = SCORE_SEMANTICS

    def __post_init__(self) -> None:
        if isinstance(self.mode, str):
            object.__setattr__(self, "mode", OverrideGateMode(self.mode))
        if not isinstance(self.policy_id, str):
            raise TypeError("policy_id must be a string")
        if not isinstance(self.policy_version, str):
            raise TypeError("policy_version must be a string")
        if not self.policy_id.strip():
            raise ValueError("policy_id must not be empty")
        if not self.policy_version.strip():
            raise ValueError("policy_version must not be empty")
        if not isinstance(self.forbid_path_cap_hit, bool):
            raise TypeError("forbid_path_cap_hit must be boolean")
        if not isinstance(self.revisit_guard, str):
            raise TypeError("revisit_guard must be a string")
        if not isinstance(self.health_guard, str):
            raise TypeError("health_guard must be a string")
        if not isinstance(self.scope, Mapping):
            raise TypeError("scope must be a mapping")
        if not isinstance(self.provenance, Mapping):
            raise TypeError("provenance must be a mapping")
        if (
            self.calibration_artifact is not None
            and not isinstance(self.calibration_artifact, str)
        ):
            raise TypeError("calibration_artifact must be a string or null")
        if self.score_semantics != SCORE_SEMANTICS:
            raise ValueError(
                f"Unsupported score_semantics: {self.score_semantics!r}"
            )
        if self.revisit_guard not in REVISIT_GUARDS:
            raise ValueError(f"Unsupported revisit_guard: {self.revisit_guard!r}")
        if self.health_guard not in HEALTH_GUARDS:
            raise ValueError(f"Unsupported health_guard: {self.health_guard!r}")
        if self.mode is OverrideGateMode.DISABLED:
            if self.min_support_margin is not None:
                raise ValueError("disabled policy must not define a support margin")
        elif self.min_support_margin is None:
            raise ValueError(f"{self.mode.value} policy requires a support margin")
        else:
            if isinstance(self.min_support_margin, bool) or not isinstance(
                self.min_support_margin, (int, float)
            ):
                raise TypeError("min_support_margin must be a number")
            margin = float(self.min_support_margin)
            if not math.isfinite(margin) or not 0.0 <= margin <= 1.0:
                raise ValueError("min_support_margin must be in [0, 1]")
            object.__setattr__(self, "min_support_margin", margin)
        if self.max_path_imbalance is not None:
            if isinstance(self.max_path_imbalance, bool) or not isinstance(
                self.max_path_imbalance, (int, float)
            ):
                raise TypeError("max_path_imbalance must be a number or null")
            imbalance = float(self.max_path_imbalance)
            if not math.isfinite(imbalance) or imbalance < 1.0:
                raise ValueError("max_path_imbalance must be finite and >= 1")
            object.__setattr__(self, "max_path_imbalance", imbalance)
        if (
            self.mode is OverrideGateMode.CALIBRATED
            and not self.calibration_artifact
        ):
            raise ValueError("calibrated policy requires calibration_artifact")
        object.__setattr__(self, "scope", _freeze_json(self.scope))
        object.__setattr__(self, "provenance", _freeze_json(self.provenance))

    @property
    def legacy_threshold_alias(self) -> float:
        """Numeric compatibility alias for historical serializers."""
        if self.min_support_margin is None:
            return DISABLED_LEGACY_THRESHOLD
        return float(self.min_support_margin)

    def allows_override(
        self,
        *,
        disagrees: bool,
        support_margin: float,
        path_imbalance: Optional[float] = None,
        path_cap_hit: Optional[bool] = None,
    ) -> bool:
        """Apply the policy's measurable action-boundary guards.

        Missing evidence fails closed when the policy requires that evidence.
        Revisit and health guards remain controller responsibilities because
        they depend on live controller state.
        """
        if self.mode is OverrideGateMode.CALIBRATED:
            raise NotImplementedError(
                "calibrated policy execution requires a frozen artifact evaluator"
            )
        if self.mode is OverrideGateMode.DISABLED or not disagrees:
            return False
        margin = float(support_margin)
        if not math.isfinite(margin):
            return False
        if margin < float(self.min_support_margin):
            return False
        if self.max_path_imbalance is not None:
            if path_imbalance is None:
                return False
            imbalance = float(path_imbalance)
            if not math.isfinite(imbalance):
                return False
            if imbalance > float(self.max_path_imbalance):
                return False
        if self.forbid_path_cap_hit and path_cap_hit is not False:
            return False
        return True

    def with_legacy_support_margin(self, value: float) -> OverrideGatePolicy:
        """Return an updated legacy policy for the mutable scalar API."""
        if (
            self.mode is not OverrideGateMode.LEGACY_FIXED
            or self.policy_id != "legacy_controller_v1"
        ):
            raise ValueError(
                "Only legacy_controller_v1 may be changed through "
                "confidence_threshold"
            )
        return replace(self, min_support_margin=float(value))

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-compatible policy record."""
        return {
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "mode": self.mode.value,
            "score_semantics": self.score_semantics,
            "min_support_margin": self.min_support_margin,
            "max_path_imbalance": self.max_path_imbalance,
            "forbid_path_cap_hit": self.forbid_path_cap_hit,
            "revisit_guard": self.revisit_guard,
            "health_guard": self.health_guard,
            "scope": _thaw_json(self.scope),
            "provenance": _thaw_json(self.provenance),
            "calibration_artifact": self.calibration_artifact,
        }

    @classmethod
    def from_dict(cls, record: Mapping[str, Any]) -> OverrideGatePolicy:
        """Restore a policy from its serialized representation."""
        return cls(
            policy_id=str(record["policy_id"]),
            policy_version=str(record["policy_version"]),
            mode=OverrideGateMode(record["mode"]),
            score_semantics=str(record.get("score_semantics", SCORE_SEMANTICS)),
            min_support_margin=record.get("min_support_margin"),
            max_path_imbalance=record.get("max_path_imbalance"),
            forbid_path_cap_hit=record.get("forbid_path_cap_hit", False),
            revisit_guard=str(record.get("revisit_guard", "none")),
            health_guard=str(record.get("health_guard", "none")),
            scope=record.get("scope", {}),
            provenance=record.get("provenance", {}),
            calibration_artifact=record.get("calibration_artifact"),
        )

    @classmethod
    def legacy_controller(
        cls,
        confidence_threshold: float = 0.0,
    ) -> OverrideGatePolicy:
        """Exact general-controller legacy contract."""
        return cls(
            policy_id="legacy_controller_v1",
            policy_version="1.0",
            mode=OverrideGateMode.LEGACY_FIXED,
            min_support_margin=float(confidence_threshold),
            max_path_imbalance=None,
            forbid_path_cap_hit=False,
            revisit_guard="controller_if_self_graph_present",
            health_guard="self_graph_if_present",
            scope={
                "component": "e0_controller.E0Controller",
                "portable": False,
            },
            provenance={"kind": "legacy_mapping"},
        )

    @classmethod
    def legacy_structural_geometry(cls) -> OverrideGatePolicy:
        """Exact Structural Geometry ``should_override`` defaults."""
        return cls(
            policy_id="legacy_structural_geometry_v1",
            policy_version="1.0",
            mode=OverrideGateMode.LEGACY_FIXED,
            min_support_margin=0.85,
            max_path_imbalance=3.0,
            forbid_path_cap_hit=False,
            revisit_guard="none",
            health_guard="none",
            scope={
                "component": "lean.structural_geometry.InfluenceReport",
                "portable": False,
            },
            provenance={
                "kind": "legacy_mapping",
                "evidence": "C185_TRAFFIC_VALIDATION_REPORT_v1",
            },
        )

    @classmethod
    def legacy_g1_v1(cls) -> OverrideGatePolicy:
        """Frozen E0-G1-v1 B-E gate contract."""
        return cls(
            policy_id="legacy_g1_v1",
            policy_version="1.0",
            mode=OverrideGateMode.LEGACY_FIXED,
            min_support_margin=0.85,
            max_path_imbalance=3.0,
            forbid_path_cap_hit=True,
            revisit_guard="none",
            health_guard="none",
            scope={
                "component": "E0-G1-v1 variants B-E",
                "portable": False,
                "frozen": True,
            },
            provenance={
                "kind": "legacy_mapping",
                "protocol_id": "E0-G1-v1",
            },
        )

    @classmethod
    def disabled(
        cls,
        *,
        policy_id: str = "override_disabled_v1",
    ) -> OverrideGatePolicy:
        """Explicit no-override policy."""
        return cls(
            policy_id=policy_id,
            policy_version="1.0",
            mode=OverrideGateMode.DISABLED,
            min_support_margin=None,
            max_path_imbalance=None,
            forbid_path_cap_hit=False,
            revisit_guard="none",
            health_guard="none",
            scope={"portable": True},
            provenance={"kind": "explicit_policy"},
        )

    def __hash__(self) -> int:
        return hash(json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")))
