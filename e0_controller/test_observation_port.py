"""
Tests for ObservationPort (C290).

ObservationPort is the second concrete DifferenzPort — for direct outcome
signals (sensor, human, external agent). These tests verify:
  - Basic construction and identity
  - Signal recording via observe() and record_outcome()
  - Impact reporting: impact_quality, dampening_factor
  - Introspection: observed_signals, has_data
  - Serialization: to_dict / from_dict round-trip
"""

from __future__ import annotations

import pytest

from e0_controller.observation_port import ObservationPort
from e0_controller.primitives import Edge, Outcome


# ──────────────────────────────────────────────────────────────────────────────
# TestObservationPortBasic
# ──────────────────────────────────────────────────────────────────────────────

class TestObservationPortBasic:
    """C290: Construction and identity.

    Claims:
      1. Fresh port has no data.
      2. Default name is 'observation'.
      3. Custom name is returned by port_name().
      4. observe() creates data (has_data True).
      5. record_outcome() also creates data.
    """

    def test_fresh_port_has_no_data(self):
        """Fresh ObservationPort has no history."""
        port = ObservationPort()
        assert not port.has_data()

    def test_default_name_is_observation(self):
        """Default port_name() returns 'observation'."""
        port = ObservationPort()
        assert port.port_name() == "observation"

    def test_custom_name_is_returned(self):
        """Custom name passed to constructor is returned by port_name()."""
        port = ObservationPort(name="sensor_A")
        assert port.port_name() == "sensor_A"

    def test_observe_creates_data(self):
        """After observe(), has_data() returns True."""
        port = ObservationPort()
        port.observe("temp_check", Outcome.SUCCESS)
        assert port.has_data()

    def test_record_outcome_creates_data(self):
        """After record_outcome(), has_data() returns True."""
        port = ObservationPort()
        port.record_outcome(Outcome.SUCCESS)
        assert port.has_data()


# ──────────────────────────────────────────────────────────────────────────────
# TestObservationPortSignals
# ──────────────────────────────────────────────────────────────────────────────

class TestObservationPortSignals:
    """C290: Signal tracking via observe().

    Claims:
      1. observed_signals() returns empty list for fresh port.
      2. observe() adds signal_id to observed_signals().
      3. Different signal_ids are tracked independently (separate edges).
      4. record_outcome() adds 'aggregate' to observed_signals().
      5. Multiple observe() calls on same signal accumulate traces.
    """

    def test_observed_signals_empty_for_fresh_port(self):
        """Fresh port has no observed signals."""
        port = ObservationPort()
        assert port.observed_signals() == []

    def test_observe_adds_signal_id(self):
        """observe() makes signal_id appear in observed_signals()."""
        port = ObservationPort()
        port.observe("temp_check", Outcome.SUCCESS)
        assert "temp_check" in port.observed_signals()

    def test_different_signals_tracked_separately(self):
        """Two different signal_ids → two separate edges in historization."""
        port = ObservationPort(name="sensor")
        port.observe("sig_A", Outcome.SUCCESS)
        port.observe("sig_B", Outcome.FAILURE)
        u_a, f_a = port._hist._effective_traces(Edge("sensor", "sig_A"))
        u_b, f_b = port._hist._effective_traces(Edge("sensor", "sig_B"))
        assert u_a > 0 and f_a == 0.0
        assert f_b > 0 and u_b == 0.0

    def test_record_outcome_adds_aggregate_signal(self):
        """record_outcome() records under 'aggregate' signal_id."""
        port = ObservationPort()
        port.record_outcome(Outcome.FAILURE)
        assert "aggregate" in port.observed_signals()

    def test_multiple_observe_same_signal_accumulates(self):
        """Multiple observe() calls on same signal accumulate trace_load."""
        port = ObservationPort(name="p")
        port.observe("sig", Outcome.SUCCESS)
        port.observe("sig", Outcome.SUCCESS)
        load = port._hist.trace_load(Edge("p", "sig"))
        assert load > 1  # two updates → load > 1 (exact value depends on discounting)


# ──────────────────────────────────────────────────────────────────────────────
# TestObservationPortImpact
# ──────────────────────────────────────────────────────────────────────────────

class TestObservationPortImpact:
    """C290: impact_quality and dampening_factor.

    Claims:
      1. impact_quality() returns 0.0 for fresh port.
      2. dampening_factor() returns 1.0 for fresh port.
      3. Pure SUCCESS history → impact_quality > 0.
      4. Pure FAILURE history → impact_quality < 0.
      5. Mixed history → dampening_factor < 1.0.
      6. Pure SUCCESS → dampening_factor near 1.0.
    """

    def test_impact_quality_no_data_is_zero(self):
        """Fresh port → impact_quality == 0.0."""
        port = ObservationPort()
        assert port.impact_quality() == 0.0

    def test_dampening_factor_no_data_is_one(self):
        """Fresh port → dampening_factor == 1.0."""
        port = ObservationPort()
        assert port.dampening_factor() == pytest.approx(1.0)

    def test_pure_success_quality_positive(self):
        """Many successes → impact_quality > 0."""
        port = ObservationPort()
        for _ in range(10):
            port.observe("sig", Outcome.SUCCESS)
        assert port.impact_quality() > 0

    def test_pure_failure_quality_negative(self):
        """Many failures → impact_quality < 0."""
        port = ObservationPort()
        for _ in range(10):
            port.observe("sig", Outcome.FAILURE)
        assert port.impact_quality() < 0

    def test_mixed_dampening_below_one(self):
        """Mixed history → dampening_factor < 1.0."""
        port = ObservationPort()
        for _ in range(5):
            port.observe("sig", Outcome.SUCCESS)
            port.observe("sig", Outcome.FAILURE)
        assert port.dampening_factor() < 1.0

    def test_pure_success_dampening_near_one(self):
        """Pure success → dampening_factor > 0.95."""
        port = ObservationPort()
        for _ in range(10):
            port.observe("sig", Outcome.SUCCESS)
        assert port.dampening_factor() > 0.95


# ──────────────────────────────────────────────────────────────────────────────
# TestObservationPortSerialization
# ──────────────────────────────────────────────────────────────────────────────

class TestObservationPortSerialization:
    """C290: to_dict / from_dict round-trip.

    Claims:
      1. to_dict() returns a dict.
      2. from_dict(None) returns a fresh ObservationPort.
      3. Round-trip preserves port name.
      4. Round-trip preserves history (impact_quality matches).
      5. from_dict({}) returns a fresh ObservationPort (backward compat).
    """

    def test_to_dict_returns_dict(self):
        """to_dict() returns a dict."""
        port = ObservationPort(name="test_port")
        port.observe("sig", Outcome.SUCCESS)
        d = port.to_dict()
        assert isinstance(d, dict)
        assert "name" in d
        assert "hist" in d

    def test_from_dict_none_returns_fresh(self):
        """from_dict(None) returns a fresh ObservationPort."""
        port = ObservationPort.from_dict(None)
        assert isinstance(port, ObservationPort)
        assert not port.has_data()

    def test_round_trip_preserves_name(self):
        """Port name survives to_dict / from_dict."""
        port = ObservationPort(name="my_sensor")
        port2 = ObservationPort.from_dict(port.to_dict())
        assert port2.port_name() == "my_sensor"

    def test_round_trip_preserves_history(self):
        """impact_quality survives to_dict / from_dict."""
        port = ObservationPort(name="p")
        for _ in range(5):
            port.observe("sig", Outcome.SUCCESS)
        q_before = port.impact_quality()
        port2 = ObservationPort.from_dict(port.to_dict())
        assert port2.impact_quality() == pytest.approx(q_before)

    def test_from_dict_empty_dict_returns_fresh(self):
        """from_dict({}) returns a fresh ObservationPort (backward compat)."""
        port = ObservationPort.from_dict({})
        assert isinstance(port, ObservationPort)
        assert not port.has_data()
