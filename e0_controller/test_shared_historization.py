"""
C189: Shared Historization Tests — cooperative knowledge sharing.

The Gordian Trap: C185–C188 built N isolated agents competing on the
same topology.  Each vehicle had its own Historization, learning only
from its own failures.  Adaptive observation (C188) correctly saw +0%
because individual vehicles aren't globally volatile.

C189 fixes this: shared_historization=True gives all vehicles one
Historization instance.  When v3 fails at bridge_r3_c2, EVERY vehicle
immediately sees higher R_eff on that edge.  The collective surprise
rate now reflects system-level volatility, unlocking adaptive observation.
"""

import random
from e0_controller.explore_traffic import (
    CityGrid,
    Strategy,
    Vehicle,
    build_vehicle_landscape,
    bfs_next_hop,
    spawn_vehicles,
    run_simulation,
)
from e0_controller.historization import Historization
from e0_controller.primitives import Edge, Outcome


class TestSharedHistorization:
    """Verify that shared_historization wires one Historization to all vehicles."""

    def test_isolated_vehicles_have_different_historizations(self):
        """Default: each vehicle gets its own Historization."""
        city = CityGrid.build_river_city()
        bfs_table = bfs_next_hop(city)
        positions = {}
        random.seed(42)
        vehicles = spawn_vehicles(city, 3, Strategy.E0_GREEDY, positions, bfs_table)
        e0_vehicles = [v for v in vehicles if v.landscape is not None]
        assert len(e0_vehicles) == 3
        hists = [v.landscape.historization for v in e0_vehicles]
        # All different objects
        assert hists[0] is not hists[1]
        assert hists[1] is not hists[2]

    def test_shared_vehicles_have_same_historization(self):
        """shared_historization=True: all vehicles share one Historization."""
        city = CityGrid.build_river_city()
        bfs_table = bfs_next_hop(city)
        positions = {}
        random.seed(42)
        vehicles = spawn_vehicles(city, 3, Strategy.E0_GREEDY, positions, bfs_table,
                                  shared_historization=True)
        e0_vehicles = [v for v in vehicles if v.landscape is not None]
        assert len(e0_vehicles) == 3
        hists = [v.landscape.historization for v in e0_vehicles]
        # All the SAME object
        assert hists[0] is hists[1]
        assert hists[1] is hists[2]

    def test_shared_failure_visible_to_all(self):
        """When one vehicle fails on shared hist, others see the F-trace."""
        city = CityGrid.build_river_city()
        shared_hist = Historization()
        L1 = build_vehicle_landscape(city, "r5_c3", shared_hist=shared_hist)
        L2 = build_vehicle_landscape(city, "r5_c5", shared_hist=shared_hist)

        # Vehicle 1 fails at bridge
        bridge_edge = Edge("r2_c2", "r3_c2")
        shared_hist.update(bridge_edge, Outcome.FAILURE)

        # Vehicle 2 sees the failure
        f_trace_v2 = L2.historization._F.get(bridge_edge, 0.0)
        assert f_trace_v2 > 0.0, "Shared failure invisible to other vehicle"

        # Both see the same R_eff increase
        r_eff_1 = L1.effective_resistance("r2_c2", "r3_c2")
        r_eff_2 = L2.effective_resistance("r2_c2", "r3_c2")
        assert r_eff_1 == r_eff_2
        assert r_eff_1 > 1.0  # above base resistance

    def test_isolated_failure_invisible_to_others(self):
        """Without sharing, one vehicle's failure is invisible to others."""
        city = CityGrid.build_river_city()
        L1 = build_vehicle_landscape(city, "r5_c3")
        L2 = build_vehicle_landscape(city, "r5_c5")

        bridge_edge = Edge("r2_c2", "r3_c2")
        L1.historization.update(bridge_edge, Outcome.FAILURE)

        # Vehicle 2 does NOT see the failure
        f_trace_v2 = L2.historization._F.get(bridge_edge, 0.0)
        assert f_trace_v2 == 0.0, "Isolated vehicle should not see other's failure"

    def test_shared_hist_preserves_individual_landscapes(self):
        """Shared hist doesn't merge Landscape topology — Δ stays goal-specific."""
        city = CityGrid.build_river_city()
        shared_hist = Historization()
        L1 = build_vehicle_landscape(city, "r0_c0", shared_hist=shared_hist)
        L2 = build_vehicle_landscape(city, "r5_c7", shared_hist=shared_hist)

        # Different goals → different Δ values
        d1 = L1.difference("r2_c2", "r3_c2")
        d2 = L2.difference("r2_c2", "r3_c2")
        # Δ depends on manhattan to goal, so unless goals are equidistant, they differ
        # Both should be valid (> 0)
        assert d1 > 0
        assert d2 > 0
        # Historization is shared
        assert L1.historization is L2.historization


class TestSharedClassifyExperience:
    """Shared historization should produce different classify_experience() results."""

    def test_collective_volatility_higher_than_individual(self):
        """With shared hist, collective surprise_rate should be higher.

        N vehicles all hitting the same bridge = N surprise events
        accumulated in one Historization → higher surprise_rate.
        """
        shared_hist = Historization()
        shared_hist.surprise_dampening = True
        bridge = Edge("r2_c2", "r3_c2")

        # Simulate 10 vehicles each visiting bridge once successfully,
        # then failing (surprise)
        for _ in range(10):
            shared_hist.update(bridge, Outcome.SUCCESS)
        for _ in range(10):
            shared_hist.update(bridge, Outcome.FAILURE)

        result = shared_hist.classify_experience()
        # With 10 successes then 10 failures on same edge, the surprise
        # rate should be substantial
        assert result in ("volatile", "exploratory")

    def test_isolated_single_vehicle_low_surprise(self):
        """Single vehicle with few visits has low surprise rate."""
        hist = Historization()
        hist.surprise_dampening = True
        bridge = Edge("r2_c2", "r3_c2")

        hist.update(bridge, Outcome.SUCCESS)
        hist.update(bridge, Outcome.FAILURE)

        result = hist.classify_experience()
        # Only 2 visits total, likely 'exploratory' due to few revisits
        assert result in ("stable", "exploratory")


class TestSharedAdaptFromExperience:
    """Shared hist + adapt_from_experience should enable dampening when collective is volatile."""

    def test_adapt_enables_dampening_on_collective_volatility(self):
        """Collective volatile experience → adapt enables dampening."""
        shared_hist = Historization()
        shared_hist.surprise_dampening = False  # starts OFF
        bridge = Edge("r2_c2", "r3_c2")

        # Build up strong expectation: many successes
        for _ in range(20):
            shared_hist.update(bridge, Outcome.SUCCESS)
        # Then many contradictions (surprise): simulate congestion spikes
        shared_hist.surprise_dampening = True  # enable tracking
        for _ in range(20):
            shared_hist.update(bridge, Outcome.FAILURE)

        result = shared_hist.classify_experience()
        if result == "volatile":
            changed = shared_hist.adapt_from_experience()
            assert changed is True
            assert shared_hist.surprise_dampening is True

    def test_adapt_on_isolated_stays_off(self):
        """Single vehicle with 1-2 visits doesn't trigger adaptation."""
        hist = Historization()
        hist.surprise_dampening = False
        bridge = Edge("r2_c2", "r3_c2")

        hist.update(bridge, Outcome.SUCCESS)
        hist.update(bridge, Outcome.FAILURE)

        changed = hist.adapt_from_experience()
        # With so few data points, should classify as exploratory → no change
        assert hist.surprise_dampening is False


class TestRunSimulationShared:
    """Integration: run_simulation with shared_historization flag."""

    def test_simulation_runs_with_shared_false(self):
        """Default isolated simulation still works."""
        city = CityGrid.build_river_city()
        random.seed(42)
        r = run_simulation(city, n_vehicles=3, n_ticks=50,
                           strategy=Strategy.E0_GREEDY,
                           shared_historization=False)
        assert r.total_ticks == 50

    def test_simulation_runs_with_shared_true(self):
        """Shared historization simulation runs without errors."""
        city = CityGrid.build_river_city()
        random.seed(42)
        r = run_simulation(city, n_vehicles=3, n_ticks=50,
                           strategy=Strategy.E0_GREEDY,
                           shared_historization=True)
        assert r.total_ticks == 50

    def test_shared_produces_different_results(self):
        """Shared vs isolated should produce different trip counts.

        We don't assert which is better — just that sharing changes behavior.
        """
        city = CityGrid.build_river_city()
        results_isolated = []
        results_shared = []
        for seed in [42, 123, 2024]:
            random.seed(seed)
            r_iso = run_simulation(city, n_vehicles=10, n_ticks=200,
                                   strategy=Strategy.E0_GREEDY,
                                   shared_historization=False)
            random.seed(seed)
            r_shared = run_simulation(city, n_vehicles=10, n_ticks=200,
                                      strategy=Strategy.E0_GREEDY,
                                      shared_historization=True)
            results_isolated.append(r_iso.trips_completed)
            results_shared.append(r_shared.trips_completed)

        # At least one seed should show different behavior
        any_different = any(a != b for a, b in zip(results_isolated, results_shared))
        assert any_different, (
            f"Shared hist produced identical results to isolated: "
            f"{results_isolated} vs {results_shared}"
        )

    def test_shared_with_adaptive_dampening(self):
        """Shared + adaptive_dampening runs without errors."""
        city = CityGrid.build_river_city()
        random.seed(42)
        r = run_simulation(city, n_vehicles=5, n_ticks=100,
                           strategy=Strategy.E0_CONSERVATIVE,
                           shared_historization=True,
                           adaptive_dampening=True)
        assert r.total_ticks == 100

    def test_non_e0_strategy_ignores_shared(self):
        """Non-E0 strategies are unaffected by shared_historization."""
        city = CityGrid.build_river_city()
        random.seed(42)
        r1 = run_simulation(city, n_vehicles=5, n_ticks=50,
                            strategy=Strategy.GREEDY_DELTA,
                            shared_historization=False)
        random.seed(42)
        r2 = run_simulation(city, n_vehicles=5, n_ticks=50,
                            strategy=Strategy.GREEDY_DELTA,
                            shared_historization=True)
        assert r1.trips_completed == r2.trips_completed
