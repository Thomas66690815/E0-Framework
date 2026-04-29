"""
Tests for DifferenzPort ABC compliance (C288).

Verifies that any DifferenzPort implementation satisfies the contract.
Uses E1Monitor as the reference implementation.

These tests are deliberately abstract — they test the protocol, not
the implementation. A new port (ObservationPort, SensorPort, ...) must
pass these same tests.
"""

from __future__ import annotations

import pytest

from e0_controller.differenz_port import DifferenzPort
from e0_controller.e1_monitor import E1Monitor
from e0_controller.observation_port import ObservationPort
from e0_controller.primitives import Outcome


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _all_port_implementations():
    """Return all known DifferenzPort implementations for parametrize."""
    return [E1Monitor, ObservationPort]


# ──────────────────────────────────────────────────────────────────────────────
# TestDifferenzPortABCCompliance
# ──────────────────────────────────────────────────────────────────────────────

class TestDifferenzPortABCCompliance:
    """Every DifferenzPort implementation must satisfy this contract."""

    @pytest.mark.parametrize("cls", _all_port_implementations())
    def test_is_subclass_of_differenz_port(self, cls):
        assert issubclass(cls, DifferenzPort)

    @pytest.mark.parametrize("cls", _all_port_implementations())
    def test_port_name_returns_string(self, cls):
        port = cls()
        name = port.port_name()
        assert isinstance(name, str)
        assert len(name) > 0

    @pytest.mark.parametrize("cls", _all_port_implementations())
    def test_record_outcome_does_not_raise(self, cls):
        port = cls()
        port.record_outcome(Outcome.SUCCESS)
        port.record_outcome(Outcome.FAILURE)

    @pytest.mark.parametrize("cls", _all_port_implementations())
    def test_impact_quality_returns_float(self, cls):
        port = cls()
        q = port.impact_quality()
        assert isinstance(q, float)

    @pytest.mark.parametrize("cls", _all_port_implementations())
    def test_impact_quality_no_data_is_zero(self, cls):
        port = cls()
        assert port.impact_quality() == 0.0

    @pytest.mark.parametrize("cls", _all_port_implementations())
    def test_dampening_factor_no_data_is_one(self, cls):
        port = cls()
        assert port.dampening_factor() == 1.0

    @pytest.mark.parametrize("cls", _all_port_implementations())
    def test_dampening_factor_in_range(self, cls):
        port = cls()
        for _ in range(5):
            port.record_outcome(Outcome.SUCCESS)
        for _ in range(5):
            port.record_outcome(Outcome.FAILURE)
        f = port.dampening_factor()
        assert 0.0 < f <= 1.0

    @pytest.mark.parametrize("cls", _all_port_implementations())
    def test_to_dict_returns_dict(self, cls):
        port = cls()
        port.record_outcome(Outcome.SUCCESS)
        d = port.to_dict()
        assert isinstance(d, dict)

    @pytest.mark.parametrize("cls", _all_port_implementations())
    def test_from_dict_none_returns_instance(self, cls):
        port = cls.from_dict(None)
        assert isinstance(port, cls)

    @pytest.mark.parametrize("cls", _all_port_implementations())
    def test_serialization_round_trip(self, cls):
        port = cls()
        for _ in range(3):
            port.record_outcome(Outcome.SUCCESS)
        restored = cls.from_dict(port.to_dict())
        assert isinstance(restored, cls)
        # After round-trip, impact_quality should be non-zero (data survived)
        assert restored.impact_quality() != 0.0


# ──────────────────────────────────────────────────────────────────────────────
# TestDifferenzPortCannotInstantiateABC
# ──────────────────────────────────────────────────────────────────────────────

class TestDifferenzPortCannotInstantiateABC:
    """DifferenzPort is abstract — cannot be instantiated directly."""

    def test_abstract_class_raises_on_instantiation(self):
        with pytest.raises(TypeError):
            DifferenzPort()  # type: ignore[abstract]
