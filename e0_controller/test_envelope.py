"""
Tests for E0Envelope and TransportRegime
==========================================
Validates the structural core envelope: typed configuration,
serialization, backward compatibility, and controller integration.

Tests cover:
  1. TransportRegime enum values and identity
  2. Transport ↔ use_su2 bridge functions
  3. E0Envelope defaults and construction
  4. E0Envelope.to_controller_kwargs backward compatibility
  5. E0Envelope.to_dict / from_dict serialization round-trip
  6. E0Envelope.from_controller extraction
  7. Controller.transport property
  8. E0Envelope with Session (integration)
  9. E0Envelope immutability (frozen)
  10. E0Envelope.summary human-readable output
"""

import math
import unittest

from e0_controller.primitives import Edge, Outcome, TransportRegime
from e0_controller.controller import E0Controller, HybridMode
from e0_controller.landscape import Landscape
from e0_controller.envelope import (
    E0Envelope,
    transport_to_use_su2,
    use_su2_to_transport,
)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _make_landscape():
    """Minimal 3-state landscape for testing."""
    L = Landscape()
    for s in ("A", "B", "GOAL"):
        L.add_state(s)
    L.add_edge("A", "B", delta=1.0, resistance=1.0)
    L.add_edge("B", "GOAL", delta=1.0, resistance=1.0)
    return L


def _success_fn(src, tgt):
    return Outcome.SUCCESS


# ──────────────────────────────────────────────
# 1. TransportRegime enum
# ──────────────────────────────────────────────

class TestTransportRegime(unittest.TestCase):
    """TransportRegime enum has correct values and is a proper Enum."""

    def test_u1_value(self):
        self.assertEqual(TransportRegime.U1.value, "u1")

    def test_su2_minimal_value(self):
        self.assertEqual(TransportRegime.SU2_MINIMAL.value, "su2_minimal")

    def test_su2_geometric_value(self):
        self.assertEqual(TransportRegime.SU2_GEOMETRIC.value, "su2_geometric")

    def test_construct_from_string(self):
        self.assertIs(TransportRegime("u1"), TransportRegime.U1)
        self.assertIs(TransportRegime("su2_minimal"), TransportRegime.SU2_MINIMAL)
        self.assertIs(TransportRegime("su2_geometric"), TransportRegime.SU2_GEOMETRIC)

    def test_three_members(self):
        self.assertEqual(len(TransportRegime), 3)


# ──────────────────────────────────────────────
# 2. Transport ↔ use_su2 bridge
# ──────────────────────────────────────────────

class TestTransportBridge(unittest.TestCase):
    """Bidirectional conversion between TransportRegime and legacy use_su2."""

    def test_u1_to_false(self):
        self.assertIs(transport_to_use_su2(TransportRegime.U1), False)

    def test_su2_minimal_to_true(self):
        self.assertIs(transport_to_use_su2(TransportRegime.SU2_MINIMAL), True)

    def test_su2_geometric_to_string(self):
        self.assertEqual(transport_to_use_su2(TransportRegime.SU2_GEOMETRIC), "geometric")

    def test_false_to_u1(self):
        self.assertIs(use_su2_to_transport(False), TransportRegime.U1)

    def test_true_to_su2_minimal(self):
        self.assertIs(use_su2_to_transport(True), TransportRegime.SU2_MINIMAL)

    def test_geometric_to_su2_geometric(self):
        self.assertIs(use_su2_to_transport("geometric"), TransportRegime.SU2_GEOMETRIC)

    def test_roundtrip_all(self):
        """Every TransportRegime survives use_su2 round-trip."""
        for regime in TransportRegime:
            legacy = transport_to_use_su2(regime)
            back = use_su2_to_transport(legacy)
            self.assertIs(back, regime)


# ──────────────────────────────────────────────
# 3. E0Envelope defaults
# ──────────────────────────────────────────────

class TestEnvelopeDefaults(unittest.TestCase):
    """E0Envelope has correct defaults matching controller defaults."""

    def test_default_mode(self):
        env = E0Envelope()
        self.assertIs(env.mode, HybridMode.GREEDY)

    def test_default_geometry(self):
        self.assertEqual(E0Envelope().geometry, "simple")

    def test_default_horizon(self):
        self.assertEqual(E0Envelope().horizon, 3)

    def test_default_transport(self):
        self.assertIs(E0Envelope().transport, TransportRegime.U1)

    def test_default_goals_none(self):
        self.assertIsNone(E0Envelope().goals)

    def test_default_alpha(self):
        self.assertEqual(E0Envelope().alpha, 2.0)

    def test_default_s_max_inf(self):
        self.assertTrue(math.isinf(E0Envelope().s_max))

    def test_default_c_min(self):
        self.assertEqual(E0Envelope().c_min, 0.0)

    def test_default_confidence(self):
        self.assertEqual(E0Envelope().confidence_threshold, 0.0)


# ──────────────────────────────────────────────
# 4. to_controller_kwargs backward compatibility
# ──────────────────────────────────────────────

class TestEnvelopeToKwargs(unittest.TestCase):
    """to_controller_kwargs produces valid E0Controller kwargs."""

    def test_default_kwargs(self):
        kwargs = E0Envelope().to_controller_kwargs()
        self.assertEqual(kwargs["hybrid_mode"], HybridMode.GREEDY)
        self.assertEqual(kwargs["hybrid_geometry"], "simple")
        self.assertEqual(kwargs["hybrid_horizon"], 3)
        self.assertIs(kwargs["use_su2"], False)
        self.assertNotIn("hybrid_goals", kwargs)  # None goals → absent

    def test_su2_kwargs(self):
        env = E0Envelope(transport=TransportRegime.SU2_MINIMAL)
        kwargs = env.to_controller_kwargs()
        self.assertIs(kwargs["use_su2"], True)

    def test_geometric_kwargs(self):
        env = E0Envelope(transport=TransportRegime.SU2_GEOMETRIC)
        kwargs = env.to_controller_kwargs()
        self.assertEqual(kwargs["use_su2"], "geometric")

    def test_goals_converted_to_set(self):
        env = E0Envelope(goals=frozenset({"G1", "G2"}))
        kwargs = env.to_controller_kwargs()
        self.assertEqual(kwargs["hybrid_goals"], {"G1", "G2"})
        self.assertIsInstance(kwargs["hybrid_goals"], set)

    def test_creates_working_controller(self):
        """Kwargs actually work with E0Controller.__init__."""
        L = _make_landscape()
        env = E0Envelope(
            mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            geometry="goal_reaching",
            horizon=4,
            goals=frozenset({"GOAL"}),
        )
        ctrl = E0Controller(L, _success_fn, **env.to_controller_kwargs())
        self.assertEqual(ctrl.hybrid_mode, HybridMode.AMPLITUDE_ON_DISAGREE)
        self.assertEqual(ctrl.hybrid_geometry, "goal_reaching")
        self.assertEqual(ctrl.hybrid_horizon, 4)
        self.assertEqual(ctrl.hybrid_goals, {"GOAL"})


# ──────────────────────────────────────────────
# 5. Serialization round-trip
# ──────────────────────────────────────────────

class TestEnvelopeSerialization(unittest.TestCase):
    """to_dict / from_dict preserves all fields."""

    def test_default_roundtrip(self):
        env = E0Envelope()
        d = env.to_dict()
        env2 = E0Envelope.from_dict(d)
        self.assertEqual(env, env2)

    def test_full_roundtrip(self):
        env = E0Envelope(
            mode=HybridMode.BORN_SAMPLING,
            geometry="goal_reaching",
            horizon=5,
            transport=TransportRegime.SU2_GEOMETRIC,
            goals=frozenset({"RED", "GREEN"}),
            alpha=3.5,
            s_max=100.0,
            c_min=0.2,
            confidence_threshold=0.6,
        )
        d = env.to_dict()
        env2 = E0Envelope.from_dict(d)
        self.assertEqual(env, env2)

    def test_inf_s_max_serializes_as_null(self):
        d = E0Envelope().to_dict()
        self.assertIsNone(d["s_max"])

    def test_finite_s_max_serializes(self):
        d = E0Envelope(s_max=50.0).to_dict()
        self.assertEqual(d["s_max"], 50.0)

    def test_goals_sorted_in_dict(self):
        d = E0Envelope(goals=frozenset({"C", "A", "B"})).to_dict()
        self.assertEqual(d["goals"], ["A", "B", "C"])

    def test_no_goals_key_when_none(self):
        d = E0Envelope().to_dict()
        self.assertNotIn("goals", d)

    def test_dict_values_are_json_safe(self):
        """All values in to_dict() are JSON-serializable types."""
        import json
        d = E0Envelope(
            mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            transport=TransportRegime.SU2_MINIMAL,
            goals=frozenset({"G"}),
        ).to_dict()
        # Should not raise
        json.dumps(d)


# ──────────────────────────────────────────────
# 6. from_controller extraction
# ──────────────────────────────────────────────

class TestEnvelopeFromController(unittest.TestCase):
    """from_controller extracts configuration from a live controller."""

    def test_extract_defaults(self):
        L = _make_landscape()
        ctrl = E0Controller(L, _success_fn)
        env = E0Envelope.from_controller(ctrl)
        self.assertIs(env.mode, HybridMode.GREEDY)
        self.assertEqual(env.geometry, "simple")
        self.assertEqual(env.horizon, 3)
        self.assertIs(env.transport, TransportRegime.U1)
        self.assertIsNone(env.goals)

    def test_extract_custom(self):
        L = _make_landscape()
        ctrl = E0Controller(
            L, _success_fn,
            hybrid_mode=HybridMode.BORN_SAMPLING,
            hybrid_geometry="goal_reaching",
            hybrid_horizon=6,
            use_su2=True,
            hybrid_goals={"GOAL"},
            alpha=4.0,
            confidence_threshold=0.5,
        )
        env = E0Envelope.from_controller(ctrl)
        self.assertIs(env.mode, HybridMode.BORN_SAMPLING)
        self.assertEqual(env.geometry, "goal_reaching")
        self.assertEqual(env.horizon, 6)
        self.assertIs(env.transport, TransportRegime.SU2_MINIMAL)
        self.assertEqual(env.goals, frozenset({"GOAL"}))
        self.assertEqual(env.alpha, 4.0)
        self.assertEqual(env.confidence_threshold, 0.5)

    def test_extract_geometric_su2(self):
        L = _make_landscape()
        ctrl = E0Controller(L, _success_fn, use_su2="geometric")
        env = E0Envelope.from_controller(ctrl)
        self.assertIs(env.transport, TransportRegime.SU2_GEOMETRIC)


# ──────────────────────────────────────────────
# 7. Controller.transport property
# ──────────────────────────────────────────────

class TestControllerTransportProperty(unittest.TestCase):
    """E0Controller.transport returns correct TransportRegime."""

    def test_default_u1(self):
        L = _make_landscape()
        ctrl = E0Controller(L, _success_fn)
        self.assertIs(ctrl.transport, TransportRegime.U1)

    def test_su2_minimal(self):
        L = _make_landscape()
        ctrl = E0Controller(L, _success_fn, use_su2=True)
        self.assertIs(ctrl.transport, TransportRegime.SU2_MINIMAL)

    def test_su2_geometric(self):
        L = _make_landscape()
        ctrl = E0Controller(L, _success_fn, use_su2="geometric")
        self.assertIs(ctrl.transport, TransportRegime.SU2_GEOMETRIC)


# ──────────────────────────────────────────────
# 8. E0Envelope immutability
# ──────────────────────────────────────────────

class TestEnvelopeImmutability(unittest.TestCase):
    """E0Envelope is frozen — cannot be modified after creation."""

    def test_cannot_set_attribute(self):
        env = E0Envelope()
        with self.assertRaises(AttributeError):
            env.horizon = 5

    def test_hashable(self):
        """Frozen dataclass is hashable — can be used as dict key."""
        env = E0Envelope()
        d = {env: "test"}
        self.assertEqual(d[env], "test")


# ──────────────────────────────────────────────
# 9. E0Envelope.summary
# ──────────────────────────────────────────────

class TestEnvelopeSummary(unittest.TestCase):
    """summary() produces human-readable one-liner."""

    def test_default_summary(self):
        s = E0Envelope().summary()
        self.assertIn("greedy", s)
        self.assertIn("simple", s)
        self.assertIn("u1", s)

    def test_goals_in_summary(self):
        s = E0Envelope(goals=frozenset({"G1", "G2"})).summary()
        self.assertIn("G1", s)
        self.assertIn("G2", s)

    def test_confidence_in_summary(self):
        s = E0Envelope(confidence_threshold=0.5).summary()
        self.assertIn("conf=0.5", s)

    def test_custom_alpha_in_summary(self):
        s = E0Envelope(alpha=5.0).summary()
        self.assertIn("α=5.0", s)

    def test_default_alpha_not_in_summary(self):
        s = E0Envelope().summary()
        self.assertNotIn("α=", s)


# ──────────────────────────────────────────────
# 10. Integration: Envelope → Controller → run
# ──────────────────────────────────────────────

class TestEnvelopeIntegration(unittest.TestCase):
    """Full pipeline: Envelope → Controller → run → from_controller."""

    def test_envelope_roundtrip_via_controller(self):
        """Create from envelope, run, extract back — configs match."""
        L = _make_landscape()
        env = E0Envelope(
            mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            geometry="goal_reaching",
            horizon=2,
            transport=TransportRegime.U1,
            goals=frozenset({"GOAL"}),
            confidence_threshold=0.3,
        )
        ctrl = E0Controller(L, _success_fn, **env.to_controller_kwargs())
        trace = ctrl.run("A", goal="GOAL")
        self.assertTrue(len(trace.steps) > 0)

        # Extract back
        env2 = E0Envelope.from_controller(ctrl)
        self.assertEqual(env.mode, env2.mode)
        self.assertEqual(env.geometry, env2.geometry)
        self.assertEqual(env.horizon, env2.horizon)
        self.assertEqual(env.transport, env2.transport)
        self.assertEqual(env.goals, env2.goals)
        self.assertEqual(env.confidence_threshold, env2.confidence_threshold)

    def test_serialization_roundtrip_via_controller(self):
        """Envelope → dict → envelope → controller — works end to end."""
        env = E0Envelope(
            mode=HybridMode.BORN_SAMPLING,
            geometry="first_arrival",
            horizon=4,
            transport=TransportRegime.SU2_GEOMETRIC,
            goals=frozenset({"GOAL"}),
            alpha=3.0,
        )
        d = env.to_dict()
        env2 = E0Envelope.from_dict(d)
        L = _make_landscape()
        ctrl = E0Controller(L, _success_fn, **env2.to_controller_kwargs())
        self.assertEqual(ctrl.hybrid_mode, HybridMode.BORN_SAMPLING)
        self.assertEqual(ctrl.hybrid_geometry, "first_arrival")
        self.assertIs(ctrl.transport, TransportRegime.SU2_GEOMETRIC)


if __name__ == "__main__":
    unittest.main()
