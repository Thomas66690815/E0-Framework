"""Tests for E0Config — Central Parameter Registry (C148)."""

import math
import pytest

from e0_controller.config import E0Config, DEFAULTS


# ── Singleton and identity ──────────────────────────────────────

class TestSingleton:
    def test_defaults_is_e0config(self):
        assert isinstance(DEFAULTS, E0Config)

    def test_defaults_uses_default_values(self):
        fresh = E0Config()
        for f in E0Config.__dataclass_fields__:
            assert getattr(DEFAULTS, f) == getattr(fresh, f), f


# ── Frozen immutability ─────────────────────────────────────────

class TestImmutability:
    def test_cannot_set_attribute(self):
        with pytest.raises(AttributeError):
            DEFAULTS.alpha = 99.0  # type: ignore[misc]

    def test_cannot_set_mu(self):
        with pytest.raises(AttributeError):
            DEFAULTS.mu = 1.0  # type: ignore[misc]


# ── Core defaults ───────────────────────────────────────────────

class TestCoreDefaults:
    def test_controller_defaults(self):
        assert DEFAULTS.alpha == 2.0
        assert DEFAULTS.recent_k == 3
        assert DEFAULTS.max_escalation_R == 5.0
        assert DEFAULTS.s_max == math.inf
        assert DEFAULTS.c_min == 0.0
        assert DEFAULTS.hybrid_horizon == 3
        assert DEFAULTS.confidence_threshold == 0.0
        assert DEFAULTS.overload_threshold == 3.0

    def test_historization_defaults(self):
        assert DEFAULTS.rho == 0.9
        assert DEFAULTS.lambda_s == 0.15
        assert DEFAULTS.lambda_f == 0.20
        assert DEFAULTS.delta_max == 3.0

    def test_mu_default(self):
        assert DEFAULTS.mu == 5.0

    def test_mode_controller_defaults(self):
        assert DEFAULTS.learn_ratio == 0.8

    def test_self_graph_diagnosis_defaults(self):
        assert DEFAULTS.sg_load_min == 3.0
        assert DEFAULTS.sg_quality_confused == 0.1
        assert DEFAULTS.sg_quality_harmful == -0.2
        assert DEFAULTS.sg_inertia_warn == 0.3

    def test_self_graph_topology_defaults(self):
        assert DEFAULTS.sg_core_delta == 0.5
        assert DEFAULTS.sg_core_R0 == 0.3
        assert DEFAULTS.sg_modulation_delta == 1.0
        assert DEFAULTS.sg_modulation_R0 == 1.0
        assert DEFAULTS.sg_rho == 1.0

    def test_multiverse_defaults(self):
        assert DEFAULTS.convergence_window == 3
        assert DEFAULTS.max_steps_per_turn == 10
        assert DEFAULTS.coupling_delta == 1.0
        assert DEFAULTS.coupling_resistance == 0.5

    def test_dream_defaults(self):
        assert DEFAULTS.dream_readiness == 0.8
        assert DEFAULTS.dream_quantile == 0.1
        assert DEFAULTS.dream_alpha == 0.5
        assert DEFAULTS.dream_base_resistance == 0.5
        assert DEFAULTS.wl_depth == 2

    def test_sleep_wake_defaults(self):
        assert DEFAULTS.max_dream_cycles == 10

    def test_structural_entropy_defaults(self):
        assert DEFAULTS.theta_base == 0.5

    def test_overlap_defaults(self):
        assert DEFAULTS.overlap_floor == 0.2

    def test_exploration_defaults(self):
        assert DEFAULTS.warmup == 0
        assert DEFAULTS.convergence_threshold == 0.0

    def test_reflexion_defaults(self):
        assert DEFAULTS.max_proposals == 5
        assert DEFAULTS.coupling_discount == 0.5
        assert DEFAULTS.gamma_min == 0.3

    def test_reflection_thresholds(self):
        assert DEFAULTS.refl_efficiency_floor == 0.0
        assert DEFAULTS.refl_quality_efficiency_ceil == 0.5
        assert DEFAULTS.refl_plateau_slope == 0.01
        assert DEFAULTS.refl_chronic_ratio == 0.5

    def test_router_defaults(self):
        assert DEFAULTS.router_base_resistance == 1.0
        assert DEFAULTS.router_min_delta == 0.1


# ── Custom config ───────────────────────────────────────────────

class TestCustomConfig:
    def test_override_single_field(self):
        custom = E0Config(alpha=1.5)
        assert custom.alpha == 1.5
        assert custom.mu == 5.0  # others unchanged

    def test_override_multiple_fields(self):
        custom = E0Config(mu=10.0, rho=0.95)
        assert custom.mu == 10.0
        assert custom.rho == 0.95
        assert custom.alpha == 2.0


# ── Summary ─────────────────────────────────────────────────────

class TestSummary:
    def test_all_defaults_summary(self):
        assert "all defaults" in DEFAULTS.summary()

    def test_modified_summary(self):
        custom = E0Config(alpha=1.5, mu=10.0)
        s = custom.summary()
        assert "alpha" in s
        assert "mu" in s
        assert "1.5" in s or "→" in s


# ── Wiring spot-checks ─────────────────────────────────────────

class TestWiringSpotChecks:
    """Verify that production modules actually consume DEFAULTS."""

    def test_historization_uses_config_rho(self):
        from e0_controller.historization import Historization
        h = Historization()
        assert h.rho == DEFAULTS.rho

    def test_controller_uses_config_alpha(self):
        from e0_controller.controller import E0Controller
        from e0_controller.landscape import Landscape
        from e0_controller.primitives import Outcome
        L = Landscape()
        L.add_edge("A", "B", delta=1.0, resistance=1.0)
        ctrl = E0Controller(L, lambda s, t: Outcome.SUCCESS)
        assert ctrl.alpha == DEFAULTS.alpha
        assert ctrl.recent_k == DEFAULTS.recent_k

    def test_exploration_policy_uses_config_warmup(self):
        from e0_controller.exploration_policy import ExplorationPolicy
        pol = ExplorationPolicy()
        assert pol.warmup == DEFAULTS.warmup
        assert pol.convergence_threshold == DEFAULTS.convergence_threshold

    def test_dream_observer_uses_config_mu(self):
        from e0_controller.dream_mode import DreamObserver
        obs = DreamObserver()
        assert obs._mu == DEFAULTS.mu
        assert obs._readiness_threshold == DEFAULTS.dream_readiness

    def test_multiverse_uses_config_convergence(self):
        from e0_controller.multiverse import MultiverseController, Universe
        from e0_controller.landscape import Landscape
        from e0_controller.primitives import Outcome
        L1, L2 = Landscape(), Landscape()
        for L in (L1, L2):
            L.add_edge("A", "B", delta=1.0, resistance=1.0)
        u1 = Universe("u1", L1, lambda s, t: Outcome.SUCCESS, "A", "B")
        u2 = Universe("u2", L2, lambda s, t: Outcome.SUCCESS, "A", "B")
        mc = MultiverseController(u1, u2)
        assert mc.convergence_window == DEFAULTS.convergence_window
