"""Regression tests for WP-GATE-0.2 override policy migration."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError

from e0_controller.amplitude_overlay import ActionAmplitudeInfo, OverlayReport
from e0_controller.controller import E0Controller, HybridMode
from e0_controller.envelope import E0Envelope
from e0_controller.landscape import Landscape
from e0_controller.memory_os import E0MemoryOS, RuntimeSnapshot
from e0_controller.override_gate import OverrideGateMode, OverrideGatePolicy
from e0_controller.primitives import Outcome


def _success(_source: str, _target: str) -> Outcome:
    return Outcome.SUCCESS


def _landscape() -> Landscape:
    landscape = Landscape()
    landscape.add_edge("S", "A", delta=0.1, resistance=1.0)
    landscape.add_edge("S", "B", delta=0.2, resistance=1.0)
    landscape.add_edge("A", "G", delta=0.2, resistance=1.0)
    landscape.add_edge("B", "G", delta=0.2, resistance=1.0)
    return landscape


def _fixed_policy(
    *,
    margin: float = 0.4,
    imbalance: float | None = None,
    forbid_path_cap_hit: bool = False,
    revisit_guard: str = "controller_if_self_graph_present",
    health_guard: str = "self_graph_if_present",
) -> OverrideGatePolicy:
    return OverrideGatePolicy(
        policy_id="test_fixed_v1",
        policy_version="1.0",
        mode=OverrideGateMode.FIXED,
        min_support_margin=margin,
        max_path_imbalance=imbalance,
        forbid_path_cap_hit=forbid_path_cap_hit,
        revisit_guard=revisit_guard,
        health_guard=health_guard,
        scope={"geometry": "simple", "families": ["test"]},
        provenance={"kind": "test"},
    )


def _overlay(*, path_counts: tuple[int, int] = (1, 1)) -> OverlayReport:
    infos = [
        ActionAmplitudeInfo(
            action="A",
            direct_s_eff=0.1,
            penalized_s=0.1,
            path_count=path_counts[0],
            paths=[["S", "A"]],
            psi_total=complex(0.5, 0.0),
            intensity=0.25,
            probability=0.25,
        ),
        ActionAmplitudeInfo(
            action="B",
            direct_s_eff=0.2,
            penalized_s=0.2,
            path_count=path_counts[1],
            paths=[["S", "B"]],
            psi_total=complex(0.8660254037844386, 0.0),
            intensity=0.75,
            probability=0.75,
        ),
    ]
    return OverlayReport(
        current="S",
        horizon_edges=1,
        geometry="simple",
        admissible_actions=["A", "B"],
        deterministic_choice="A",
        deterministic_escalated=False,
        action_infos=infos,
    )


class TestLegacyProfiles(unittest.TestCase):
    def test_controller_profile_exact(self):
        policy = OverrideGatePolicy.legacy_controller(0.3)
        self.assertEqual(policy.policy_id, "legacy_controller_v1")
        self.assertIs(policy.mode, OverrideGateMode.LEGACY_FIXED)
        self.assertEqual(policy.min_support_margin, 0.3)
        self.assertIsNone(policy.max_path_imbalance)
        self.assertFalse(policy.forbid_path_cap_hit)

    def test_structural_geometry_profile_exact(self):
        policy = OverrideGatePolicy.legacy_structural_geometry()
        self.assertEqual(policy.min_support_margin, 0.85)
        self.assertEqual(policy.max_path_imbalance, 3.0)
        self.assertFalse(policy.forbid_path_cap_hit)

    def test_g1_profile_exact(self):
        policy = OverrideGatePolicy.legacy_g1_v1()
        self.assertEqual(policy.min_support_margin, 0.85)
        self.assertEqual(policy.max_path_imbalance, 3.0)
        self.assertTrue(policy.forbid_path_cap_hit)

    def test_disabled_profile_never_allows_override(self):
        policy = OverrideGatePolicy.disabled()
        self.assertFalse(
            policy.allows_override(disagrees=True, support_margin=1.0)
        )
        self.assertGreater(policy.legacy_threshold_alias, 1.0)


class TestPolicyValidation(unittest.TestCase):
    def test_margin_must_be_in_unit_interval(self):
        with self.assertRaises(ValueError):
            _fixed_policy(margin=1.01)

    def test_imbalance_must_be_at_least_one(self):
        with self.assertRaises(ValueError):
            _fixed_policy(imbalance=0.9)
        with self.assertRaises(ValueError):
            _fixed_policy(imbalance=float("inf"))

    def test_calibrated_policy_requires_artifact(self):
        with self.assertRaises(ValueError):
            OverrideGatePolicy(
                policy_id="calibrated_test_v1",
                policy_version="1.0",
                mode=OverrideGateMode.CALIBRATED,
                min_support_margin=0.5,
                max_path_imbalance=None,
                forbid_path_cap_hit=False,
                revisit_guard="none",
                health_guard="none",
            )

    def test_unknown_dynamic_guard_is_rejected(self):
        with self.assertRaises(ValueError):
            _fixed_policy(revisit_guard="unknown")
        with self.assertRaises(ValueError):
            _fixed_policy(health_guard="unknown")

    def test_malformed_json_types_are_rejected(self):
        record = _fixed_policy().to_dict()
        record["forbid_path_cap_hit"] = "false"
        with self.assertRaises(TypeError):
            OverrideGatePolicy.from_dict(record)

        record = _fixed_policy().to_dict()
        record["min_support_margin"] = "0.4"
        with self.assertRaises(TypeError):
            OverrideGatePolicy.from_dict(record)

    def test_policy_and_nested_metadata_are_immutable(self):
        policy = _fixed_policy()
        with self.assertRaises(FrozenInstanceError):
            policy.policy_id = "changed"
        with self.assertRaises(TypeError):
            policy.scope["geometry"] = "changed"

    def test_json_round_trip_and_hash(self):
        policy = _fixed_policy(imbalance=3.0)
        encoded = json.dumps(policy.to_dict())
        restored = OverrideGatePolicy.from_dict(json.loads(encoded))
        self.assertEqual(restored, policy)
        self.assertEqual(hash(restored), hash(policy))

    def test_calibrated_policy_is_representable_but_not_yet_executable(self):
        policy = OverrideGatePolicy(
            policy_id="calibrated_test_v1",
            policy_version="1.0",
            mode=OverrideGateMode.CALIBRATED,
            min_support_margin=0.5,
            max_path_imbalance=None,
            forbid_path_cap_hit=False,
            revisit_guard="none",
            health_guard="none",
            calibration_artifact="artifacts/calibration.json",
        )
        restored = OverrideGatePolicy.from_dict(policy.to_dict())
        self.assertEqual(restored, policy)
        with self.assertRaises(NotImplementedError):
            restored.allows_override(
                disagrees=True,
                support_margin=0.9,
            )


class TestPolicyDecision(unittest.TestCase):
    def test_threshold_is_inclusive(self):
        policy = _fixed_policy(margin=0.5)
        self.assertTrue(
            policy.allows_override(disagrees=True, support_margin=0.5)
        )

    def test_below_threshold_is_blocked(self):
        policy = _fixed_policy(margin=0.5)
        self.assertFalse(
            policy.allows_override(disagrees=True, support_margin=0.49)
        )

    def test_agreement_is_blocked(self):
        policy = _fixed_policy(margin=0.0)
        self.assertFalse(
            policy.allows_override(disagrees=False, support_margin=1.0)
        )

    def test_required_imbalance_missing_fails_closed(self):
        policy = _fixed_policy(imbalance=3.0)
        self.assertFalse(
            policy.allows_override(disagrees=True, support_margin=0.8)
        )

    def test_excess_imbalance_is_blocked(self):
        policy = _fixed_policy(imbalance=3.0)
        self.assertFalse(
            policy.allows_override(
                disagrees=True,
                support_margin=0.8,
                path_imbalance=3.01,
            )
        )

    def test_path_cap_measurement_missing_fails_closed(self):
        policy = _fixed_policy(forbid_path_cap_hit=True)
        self.assertFalse(
            policy.allows_override(disagrees=True, support_margin=0.8)
        )
        self.assertTrue(
            policy.allows_override(
                disagrees=True,
                support_margin=0.8,
                path_cap_hit=False,
            )
        )

    def test_non_finite_measurements_fail_closed(self):
        policy = _fixed_policy(imbalance=3.0)
        self.assertFalse(
            policy.allows_override(
                disagrees=True,
                support_margin=float("nan"),
                path_imbalance=1.0,
            )
        )
        self.assertFalse(
            policy.allows_override(
                disagrees=True,
                support_margin=0.8,
                path_imbalance=float("nan"),
            )
        )


class TestControllerIntegration(unittest.TestCase):
    def test_implicit_scalar_maps_to_legacy_policy(self):
        controller = E0Controller(
            _landscape(),
            _success,
            confidence_threshold=0.42,
        )
        self.assertEqual(controller.confidence_threshold, 0.42)
        self.assertEqual(
            controller.override_policy.policy_id,
            "legacy_controller_v1",
        )

    def test_legacy_scalar_setter_updates_policy(self):
        controller = E0Controller(_landscape(), _success)
        controller.confidence_threshold = 0.6
        self.assertEqual(controller.confidence_threshold, 0.6)
        self.assertEqual(controller.override_policy.min_support_margin, 0.6)

    def test_fixed_policy_rejects_legacy_scalar_mutation(self):
        controller = E0Controller(
            _landscape(),
            _success,
            override_policy=_fixed_policy(),
        )
        with self.assertRaises(ValueError):
            controller.confidence_threshold = 0.2

    def test_frozen_g1_policy_rejects_legacy_scalar_mutation(self):
        controller = E0Controller(
            _landscape(),
            _success,
            override_policy=OverrideGatePolicy.legacy_g1_v1(),
        )
        with self.assertRaises(ValueError):
            controller.confidence_threshold = 0.2

    def test_conflicting_explicit_scalar_is_rejected(self):
        with self.assertRaises(ValueError):
            E0Controller(
                _landscape(),
                _success,
                confidence_threshold=0.2,
                override_policy=_fixed_policy(margin=0.4),
            )

    def test_policy_dict_is_accepted(self):
        policy = _fixed_policy()
        controller = E0Controller(
            _landscape(),
            _success,
            override_policy=policy.to_dict(),
        )
        self.assertEqual(controller.override_policy, policy)
        self.assertEqual(controller.confidence_threshold, 0.4)

    def test_explicit_policy_controls_live_override(self):
        controller = E0Controller(
            _landscape(),
            _success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            override_policy=_fixed_policy(margin=0.4),
        )
        controller._compute_overlay = lambda *_args, **_kwargs: _overlay()
        target, _, _, _, overridden = controller.select_hybrid("S")
        self.assertEqual(target, "B")
        self.assertTrue(overridden)

    def test_explicit_imbalance_guard_controls_live_override(self):
        controller = E0Controller(
            _landscape(),
            _success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            override_policy=_fixed_policy(margin=0.4, imbalance=2.0),
        )
        controller._compute_overlay = lambda *_args, **_kwargs: _overlay(
            path_counts=(1, 3)
        )
        target, _, _, _, overridden = controller.select_hybrid("S")
        self.assertEqual(target, "A")
        self.assertFalse(overridden)

    def test_path_cap_policy_fails_closed_in_controller(self):
        controller = E0Controller(
            _landscape(),
            _success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            override_policy=_fixed_policy(
                margin=0.4,
                forbid_path_cap_hit=True,
            ),
        )
        controller._compute_overlay = lambda *_args, **_kwargs: _overlay()
        target, _, _, _, overridden = controller.select_hybrid("S")
        self.assertEqual(target, "A")
        self.assertFalse(overridden)

    def test_policy_can_disable_dynamic_guards(self):
        controller = E0Controller(
            _landscape(),
            _success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            override_policy=_fixed_policy(
                margin=0.4,
                revisit_guard="none",
                health_guard="none",
            ),
        )
        controller._compute_overlay = lambda *_args, **_kwargs: _overlay()
        controller._recent = ["B"]

        class HarmfulSelfGraph:
            @staticmethod
            def override_quality() -> float:
                return -1.0

        controller.self_graph = HarmfulSelfGraph()
        target, _, _, _, overridden = controller.select_hybrid("S")
        self.assertEqual(target, "B")
        self.assertTrue(overridden)


class TestEnvelopeMigration(unittest.TestCase):
    def test_legacy_dict_without_policy_is_unchanged(self):
        record = E0Envelope(confidence_threshold=0.3).to_dict()
        self.assertNotIn("override_policy", record)
        restored = E0Envelope.from_dict(record)
        self.assertIsNone(restored.override_policy)
        self.assertEqual(restored.confidence_threshold, 0.3)

    def test_policy_round_trip(self):
        policy = _fixed_policy()
        envelope = E0Envelope(
            confidence_threshold=0.4,
            override_policy=policy,
        )
        restored = E0Envelope.from_dict(envelope.to_dict())
        self.assertEqual(restored, envelope)
        controller = E0Controller(
            _landscape(),
            _success,
            **restored.to_controller_kwargs(),
        )
        self.assertEqual(controller.override_policy, policy)

    def test_policy_and_scalar_must_match(self):
        with self.assertRaises(ValueError):
            E0Envelope(
                confidence_threshold=0.2,
                override_policy=_fixed_policy(margin=0.4),
            )


class TestMemOSMigration(unittest.TestCase):
    def test_new_snapshot_contains_policy_and_scalar(self):
        controller = E0Controller(
            _landscape(),
            _success,
            confidence_threshold=0.3,
        )
        params = RuntimeSnapshot.from_controller(controller).controller_params
        self.assertEqual(params["confidence_threshold"], 0.3)
        self.assertEqual(
            params["override_policy"]["policy_id"],
            "legacy_controller_v1",
        )

    def test_old_snapshot_without_policy_restores_exact_scalar(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            memos = E0MemoryOS(base_dir=tmpdir)
            landscape = _landscape()
            controller = E0Controller(
                landscape,
                _success,
                confidence_threshold=0.37,
            )
            context = memos.snapshot_from_runtime(
                "legacy-policy",
                landscape,
                controller,
            )
            context.runtime["controller_params"].pop("override_policy")
            restored = memos.restore_controller(context, landscape, _success)
            self.assertEqual(restored.confidence_threshold, 0.37)
            self.assertEqual(
                restored.override_policy.policy_id,
                "legacy_controller_v1",
            )

    def test_explicit_policy_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            memos = E0MemoryOS(base_dir=tmpdir)
            landscape = _landscape()
            policy = _fixed_policy()
            controller = E0Controller(
                landscape,
                _success,
                override_policy=policy,
            )
            context = memos.snapshot_from_runtime(
                "fixed-policy",
                landscape,
                controller,
            )
            memos.save_context(context)
            loaded = memos.load_context("fixed-policy")
            restored_landscape = memos.restore_landscape(loaded)
            restored = memos.restore_controller(
                loaded,
                restored_landscape,
                _success,
            )
            self.assertEqual(restored.override_policy, policy)
            self.assertEqual(restored.confidence_threshold, 0.4)


if __name__ == "__main__":
    unittest.main()
