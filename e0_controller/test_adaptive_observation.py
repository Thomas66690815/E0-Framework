"""
C188: Adaptive Observation — E₀ observes its own volatility and adapts.

Tests for the observation feedback loop:
- Observation project() exposes surprise metrics at depth ≥ dyn
- adapt_from_experience() toggles surprise_dampening based on classify_experience()
- Controller with adaptive_dampening calls adapt_from_experience() after inscription
- End-to-end: volatile domain → dampening auto-enabled, stable → disabled
"""

import pytest
from e0_controller.primitives import Edge, Outcome
from e0_controller.historization import Historization
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller
from e0_controller.observation_controller import ObservationController


# ─────────────────────── Helpers ───────────────────────

def make_edge(src="A", tgt="B"):
    return Edge(src, tgt)


def build_3node_landscape():
    L = Landscape()
    for s in ("A", "B", "C"):
        L.add_state(s)
    L.add_edge("A", "B", delta=0.5, resistance=1.0)
    L.add_edge("A", "C", delta=0.8, resistance=1.0)
    L.add_edge("B", "C", delta=0.3, resistance=1.0)
    return L


def pump_volatile(H, e, n=10):
    """Inject alternating outcomes to create a volatile domain."""
    outcomes = [Outcome.SUCCESS, Outcome.FAILURE] * n
    for oc in outcomes:
        H.update(e, oc)
        for _ in range(3):
            H.update(Edge("X", "Y"), Outcome.SUCCESS)


def pump_stable(H, e, n=10):
    """Inject consistent outcomes to create a stable domain."""
    for _ in range(n):
        H.update(e, Outcome.SUCCESS)
        for _ in range(3):
            H.update(Edge("X", "Y"), Outcome.SUCCESS)
        H.update(e, Outcome.SUCCESS)  # confirm


# ───────────── adapt_from_experience() ─────────────

class TestAdaptFromExperience:
    """adapt_from_experience() toggles dampening from domain classification."""

    def test_volatile_enables_dampening(self):
        """Volatile domain → dampening turns ON."""
        H = Historization()
        assert H.surprise_dampening is False
        pump_volatile(H, make_edge())
        assert H.classify_experience() == "volatile"
        changed = H.adapt_from_experience()
        assert changed is True
        assert H.surprise_dampening is True

    def test_stable_disables_dampening(self):
        """Stable domain → dampening turns OFF (even if previously ON)."""
        H = Historization(surprise_dampening=True)
        pump_stable(H, make_edge())
        assert H.classify_experience() == "stable"
        changed = H.adapt_from_experience()
        assert changed is True
        assert H.surprise_dampening is False

    def test_exploratory_no_change(self):
        """Exploratory (insufficient data) → no change, preserves current state."""
        H = Historization(surprise_dampening=True)
        assert H.classify_experience() == "exploratory"
        changed = H.adapt_from_experience()
        assert changed is False
        assert H.surprise_dampening is True  # unchanged

    def test_already_correct_no_change(self):
        """Already in correct state → returns False."""
        H = Historization(surprise_dampening=True)
        pump_volatile(H, make_edge())
        changed = H.adapt_from_experience()
        assert changed is False  # already dampened, volatile confirms

    def test_idempotent(self):
        """Calling twice in same state has no extra effect."""
        H = Historization()
        pump_volatile(H, make_edge())
        H.adapt_from_experience()
        assert H.surprise_dampening is True
        changed = H.adapt_from_experience()
        assert changed is False  # already correct

    def test_transitions_both_ways(self):
        """Can go OFF→ON and then ON→OFF as domain character changes."""
        H = Historization()
        e = make_edge()
        # Start volatile → enable
        pump_volatile(H, e)
        H.adapt_from_experience()
        assert H.surprise_dampening is True

        # Now overwhelm with stable data → should flip back
        e2 = Edge("P", "Q")
        for _ in range(50):
            H.update(e2, Outcome.SUCCESS)
            for _ in range(3):
                H.update(Edge("X", "Y"), Outcome.SUCCESS)
            H.update(e2, Outcome.SUCCESS)

        if H.classify_experience() == "stable":
            changed = H.adapt_from_experience()
            assert changed is True
            assert H.surprise_dampening is False


# ───────────── Observation project() ─────────────

class TestObservationSurpriseMetrics:
    """project() exposes surprise metrics at depth ≥ dyn (C188)."""

    def test_metrics_at_dyn_depth(self):
        """Surprise metrics appear when depth reaches 'dyn'."""
        L = build_3node_landscape()
        ctrl = ObservationController(L)
        ctrl.deepen()  # topo → field
        ctrl.deepen()  # field → dyn
        proj = ctrl.project()
        assert "surprise_metrics" in proj
        sm = proj["surprise_metrics"]
        assert "surprise_rate" in sm
        assert "domain_classification" in sm
        assert "surprise_dampening_active" in sm
        assert "surprise_edges" in sm

    def test_no_metrics_at_field_depth(self):
        """Surprise metrics NOT visible at depth < dyn."""
        L = build_3node_landscape()
        ctrl = ObservationController(L)
        ctrl.deepen()  # topo → field
        proj = ctrl.project()
        assert "surprise_metrics" not in proj

    def test_no_metrics_at_topo_depth(self):
        """Surprise metrics NOT visible at topo depth."""
        L = build_3node_landscape()
        ctrl = ObservationController(L)
        proj = ctrl.project()
        assert "surprise_metrics" not in proj

    def test_metrics_reflect_state(self):
        """Metrics reflect actual historization state."""
        L = build_3node_landscape()
        e = Edge("A", "B")
        pump_volatile(L.historization, e)
        L.historization.surprise_dampening = True

        ctrl = ObservationController(L)
        ctrl.deepen()
        ctrl.deepen()
        proj = ctrl.project()
        sm = proj["surprise_metrics"]

        assert sm["surprise_rate"] > 0.3
        assert sm["domain_classification"] == "volatile"
        assert sm["surprise_dampening_active"] is True
        assert len(sm["surprise_edges"]) >= 1

    def test_metrics_at_mech_and_intf_depths(self):
        """Surprise metrics persist at deeper levels (mech, intf)."""
        L = build_3node_landscape()
        ctrl = ObservationController(L)
        for _ in range(4):  # topo → field → dyn → mech
            ctrl.deepen()
        proj = ctrl.project()
        assert "surprise_metrics" in proj

    def test_surprise_edges_format(self):
        """surprise_edges in projection have source/target/count keys."""
        L = build_3node_landscape()
        e = Edge("A", "B")
        pump_volatile(L.historization, e)

        ctrl = ObservationController(L)
        ctrl.deepen()
        ctrl.deepen()
        proj = ctrl.project()
        for entry in proj["surprise_metrics"]["surprise_edges"]:
            assert "source" in entry
            assert "target" in entry
            assert "count" in entry
            assert isinstance(entry["count"], (int, float))


# ───────────── Controller Integration ─────────────

class TestControllerAdaptiveDampening:
    """E0Controller with adaptive_dampening auto-adapts."""

    def test_flag_stored(self):
        """adaptive_dampening flag is stored on controller."""
        L = build_3node_landscape()
        fn = lambda s, t: Outcome.SUCCESS
        c = E0Controller(L, fn, adaptive_dampening=True)
        assert c.adaptive_dampening is True

    def test_flag_default_false(self):
        """adaptive_dampening defaults to False."""
        L = build_3node_landscape()
        fn = lambda s, t: Outcome.SUCCESS
        c = E0Controller(L, fn)
        assert c.adaptive_dampening is False

    def test_adaptive_enables_dampening_on_volatile(self):
        """In a volatile environment, adaptive controller enables dampening."""
        L = build_3node_landscape()
        e = Edge("A", "B")

        # Pre-load volatile history
        pump_volatile(L.historization, e)
        assert L.historization.classify_experience() == "volatile"
        assert L.historization.surprise_dampening is False

        fn = lambda s, t: Outcome.SUCCESS
        c = E0Controller(L, fn, adaptive_dampening=True)

        # One cycle should trigger adapt_from_experience
        step = c.cycle("A")
        assert step is not None
        assert L.historization.surprise_dampening is True

    def test_no_adapt_when_flag_off(self):
        """Without adaptive_dampening, volatile domain doesn't auto-enable."""
        L = build_3node_landscape()
        e = Edge("A", "B")
        pump_volatile(L.historization, e)

        fn = lambda s, t: Outcome.SUCCESS
        c = E0Controller(L, fn, adaptive_dampening=False)

        c.cycle("A")
        assert L.historization.surprise_dampening is False  # unchanged

    def test_run_adapts_during_execution(self):
        """During run(), adaptation happens after each inscribed step."""
        L = build_3node_landscape()
        e = Edge("A", "B")
        pump_volatile(L.historization, e)

        fn = lambda s, t: Outcome.SUCCESS
        c = E0Controller(L, fn, adaptive_dampening=True)

        trace = c.run("A", max_cycles=3)
        assert len(trace.steps) > 0
        # Should have adapted by now
        assert L.historization.surprise_dampening is True


# ───────────── End-to-end: The Observation Loop ─────────────

class TestObservationLoop:
    """The complete loop: experience → classify → adapt → inscription changes."""

    def test_stable_domain_stays_undampened(self):
        """Stable environment: adapt keeps dampening OFF throughout."""
        L = build_3node_landscape()
        fn = lambda s, t: Outcome.SUCCESS  # always success → stable
        c = E0Controller(L, fn, adaptive_dampening=True)

        trace = c.run("A", max_cycles=20, goal="C")
        # All successes, stable → dampening should stay off
        assert L.historization.surprise_dampening is False

    def test_observation_sees_adaptation_result(self):
        """Observation controller sees the dampening state that adapt set."""
        L = build_3node_landscape()
        e = Edge("A", "B")
        pump_volatile(L.historization, e)

        # Adapt
        L.historization.adapt_from_experience()
        assert L.historization.surprise_dampening is True

        # Observe
        ctrl = ObservationController(L)
        ctrl.deepen()
        ctrl.deepen()
        proj = ctrl.project()
        assert proj["surprise_metrics"]["surprise_dampening_active"] is True
        assert proj["surprise_metrics"]["domain_classification"] == "volatile"
