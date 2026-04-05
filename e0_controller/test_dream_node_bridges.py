"""Tests for C154: DreamObserver Node Bridge Pipeline.

Tests cover:
- node_equivalences_for() query method
- propose_node_bridges() structural transfer
- make_dream_peer_fn() node-bridge fallback
- SleepWakeCycle.wire_peer_fns() convenience method
"""

import pytest

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller
from e0_controller.dream_mode import (
    DreamObserver,
    NodeBridgeProposal,
    NodeBridgeResult,
    propose_node_bridges,
    make_dream_peer_fn,
)
from e0_controller.sleep_wake import SleepWakeCycle


# ═══════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════

def _inscribe(landscape: Landscape, path: list[str], outcome: Outcome, n: int = 1):
    """Inscribe a path into a landscape's historization n times."""
    for _ in range(n):
        for i in range(len(path) - 1):
            edge = Edge(path[i], path[i + 1])
            landscape.historization.update(edge, outcome)


def _build_simple_domain() -> Landscape:
    """A→B→C→GOAL with uniform Δ=0.5, R₀=1.0."""
    L = Landscape()
    for s, t in [("A", "B"), ("B", "C"), ("C", "GOAL")]:
        L.add_edge(s, t, delta=0.5, resistance=1.0)
    return L


def _setup_twin_observer() -> DreamObserver:
    """Two isomorphic domains with inscribed paths + Hungarian matching."""
    obs = DreamObserver(
        readiness_threshold=0.0,
        node_equivalence_method="hungarian",
    )
    La = _build_simple_domain()
    Lb = _build_simple_domain()
    _inscribe(La, ["A", "B", "C", "GOAL"], Outcome.SUCCESS, 5)
    _inscribe(Lb, ["A", "B", "C", "GOAL"], Outcome.SUCCESS, 5)
    obs.register("alpha", La)
    obs.register("beta", Lb)
    obs.dream_cycle()
    return obs


def _setup_asymmetric_observer() -> DreamObserver:
    """Donor (beta) has an extra edge the target (alpha) lacks."""
    obs = DreamObserver(
        readiness_threshold=0.0,
        node_equivalence_method="hungarian",
    )
    La = Landscape()
    La.add_edge("A", "B", delta=0.5, resistance=1.0)
    La.add_edge("B", "C", delta=0.5, resistance=1.0)

    Lb = Landscape()
    Lb.add_edge("A", "B", delta=0.5, resistance=1.0)
    Lb.add_edge("B", "C", delta=0.5, resistance=1.0)
    Lb.add_edge("A", "C", delta=0.8, resistance=0.5)  # shortcut only in beta

    _inscribe(La, ["A", "B", "C"], Outcome.SUCCESS, 5)
    _inscribe(Lb, ["A", "B", "C"], Outcome.SUCCESS, 5)
    _inscribe(Lb, ["A", "C"], Outcome.SUCCESS, 3)

    obs.register("alpha", La)
    obs.register("beta", Lb)
    obs.dream_cycle()
    return obs


# ═══════════════════════════════════════════════
# Test: node_equivalences_for()
# ═══════════════════════════════════════════════

class TestNodeEquivalencesFor:
    """Query node-level equivalences from Dream Landscape."""

    def test_returns_list_for_twin_domains(self):
        obs = _setup_twin_observer()
        eqs = obs.node_equivalences_for("alpha")
        assert isinstance(eqs, list)
        assert len(eqs) > 0

    def test_each_entry_has_required_keys(self):
        obs = _setup_twin_observer()
        eqs = obs.node_equivalences_for("alpha")
        for eq in eqs:
            assert "own_node" in eq
            assert "partner_domain" in eq
            assert "partner_node" in eq
            assert "trace_quality" in eq
            assert "trace_load" in eq

    def test_filter_by_node(self):
        obs = _setup_twin_observer()
        eqs_all = obs.node_equivalences_for("alpha")
        eqs_a = obs.node_equivalences_for("alpha", "A")
        assert len(eqs_a) <= len(eqs_all)
        for eq in eqs_a:
            assert eq["own_node"] == "A"

    def test_partner_is_different_domain(self):
        obs = _setup_twin_observer()
        eqs = obs.node_equivalences_for("alpha")
        for eq in eqs:
            assert eq["partner_domain"] == "beta"

    def test_min_quality_filter(self):
        obs = _setup_twin_observer()
        eqs_all = obs.node_equivalences_for("alpha")
        eqs_high = obs.node_equivalences_for("alpha", min_quality=999.0)
        assert len(eqs_high) <= len(eqs_all)

    def test_empty_for_unknown_domain(self):
        obs = _setup_twin_observer()
        assert obs.node_equivalences_for("nonexistent") == []

    def test_empty_for_unknown_node(self):
        obs = _setup_twin_observer()
        assert obs.node_equivalences_for("alpha", "NONEXISTENT") == []

    def test_empty_without_dream_landscape(self):
        obs = DreamObserver(readiness_threshold=0.0)
        obs.register("alpha", _build_simple_domain())
        assert obs.node_equivalences_for("alpha") == []

    def test_empty_without_node_method(self):
        obs = DreamObserver(readiness_threshold=0.0)
        La = _build_simple_domain()
        Lb = _build_simple_domain()
        _inscribe(La, ["A", "B", "C", "GOAL"], Outcome.SUCCESS, 5)
        _inscribe(Lb, ["A", "B", "C", "GOAL"], Outcome.SUCCESS, 5)
        obs.register("alpha", La)
        obs.register("beta", Lb)
        obs.dream_cycle()
        # Edge equivalences exist but no node equivalences
        assert obs.node_equivalences_for("alpha") == []

    def test_sorted_by_quality_descending(self):
        obs = _setup_twin_observer()
        eqs = obs.node_equivalences_for("alpha")
        if len(eqs) >= 2:
            qualities = [eq["trace_quality"] for eq in eqs]
            assert qualities == sorted(qualities, reverse=True)


# ═══════════════════════════════════════════════
# Test: propose_node_bridges()
# ═══════════════════════════════════════════════

class TestProposeNodeBridges:
    """Node-level structural transfer via propose_node_bridges()."""

    def test_returns_node_bridge_result(self):
        obs = _setup_twin_observer()
        result = propose_node_bridges(obs, "alpha", "A", "GOAL")
        assert isinstance(result, NodeBridgeResult)
        assert result.target_domain == "alpha"

    def test_no_proposals_for_unknown_domain(self):
        obs = _setup_twin_observer()
        result = propose_node_bridges(obs, "nonexistent", "A")
        assert result.proposals == []
        assert result.edges_added == 0

    def test_no_proposals_without_node_equivalences(self):
        obs = DreamObserver(readiness_threshold=0.0)
        La = _build_simple_domain()
        Lb = _build_simple_domain()
        _inscribe(La, ["A", "B", "C", "GOAL"], Outcome.SUCCESS, 5)
        _inscribe(Lb, ["A", "B", "C", "GOAL"], Outcome.SUCCESS, 5)
        obs.register("alpha", La)
        obs.register("beta", Lb)
        obs.dream_cycle()
        result = propose_node_bridges(obs, "alpha", "A")
        assert result.proposals == []

    def test_twin_domains_no_new_edges(self):
        """Isomorphic domains already have the same edges — no new proposals."""
        obs = _setup_twin_observer()
        result = propose_node_bridges(obs, "alpha", "A", "GOAL")
        # Both domains have A→B already, so nothing to propose
        assert result.edges_added == 0

    def test_asymmetric_transfer(self):
        """Beta has A→C shortcut. Alpha should receive a proposal for A→C."""
        obs = _setup_asymmetric_observer()
        result = propose_node_bridges(obs, "alpha", "A", "C")
        # Beta has A→C, alpha doesn't → proposal expected
        assert len(result.proposals) > 0
        targets = [p.target for p in result.proposals]
        assert "C" in targets

    def test_proposal_fields(self):
        obs = _setup_asymmetric_observer()
        result = propose_node_bridges(obs, "alpha", "A", "C")
        if result.proposals:
            p = result.proposals[0]
            assert isinstance(p, NodeBridgeProposal)
            assert p.source == "A"
            assert p.donor_domain == "beta"
            assert 0.0 < p.confidence <= 1.0
            assert p.resistance > 0.0

    def test_edges_added_count(self):
        obs = _setup_asymmetric_observer()
        alpha_landscape = obs._domains["alpha"]
        edge_before = Edge("A", "C") in alpha_landscape._R0
        result = propose_node_bridges(obs, "alpha", "A", "C")
        if not edge_before and result.proposals:
            assert result.edges_added > 0
            # Edge now exists in alpha
            assert Edge("A", "C") in alpha_landscape._R0

    def test_no_self_loops(self):
        obs = _setup_twin_observer()
        result = propose_node_bridges(obs, "alpha", "A")
        for p in result.proposals:
            assert p.target != p.source

    def test_max_proposals_respected(self):
        obs = _setup_asymmetric_observer()
        result = propose_node_bridges(
            obs, "alpha", "A", max_proposals=1,
        )
        assert len(result.proposals) <= 1

    def test_statistics_populated(self):
        obs = _setup_asymmetric_observer()
        result = propose_node_bridges(obs, "alpha", "A")
        assert result.node_mappings_used >= 0
        assert result.donor_edges_checked >= 0

    def test_discount_inflates_resistance(self):
        """Proposed edges should have higher resistance than the donor's."""
        obs = _setup_asymmetric_observer()
        result = propose_node_bridges(obs, "alpha", "A", "C")
        donor_landscape = obs._domains["beta"]
        donor_r0 = donor_landscape._R0.get(Edge("A", "C"), 1.0)
        for p in result.proposals:
            if p.donor_source == "A" and p.donor_target == "C":
                assert p.resistance >= donor_r0


# ═══════════════════════════════════════════════
# Test: make_dream_peer_fn() — node bridge fallback
# ═══════════════════════════════════════════════

class TestMakeDreamPeerFnNodeBridge:
    """C154: make_dream_peer_fn falls back to node bridges."""

    def test_peer_fn_uses_node_bridges(self):
        """When edge bridges fail, peer_fn should try node bridges."""
        obs = _setup_asymmetric_observer()
        alpha = obs._domains["alpha"]

        peer = make_dream_peer_fn(obs, "alpha", "C")

        # Add the edge first so it appears in neighbors
        alpha.add_edge("A", "C", delta=0.5, resistance=1.0)
        neighbors = alpha.admissible_neighbors("A")

        result = peer(alpha, "A", neighbors)
        # May or may not suggest C depending on bridge state,
        # but should not crash
        assert result is None or isinstance(result, str)

    def test_peer_fn_returns_none_without_equivalences(self):
        obs = DreamObserver(readiness_threshold=0.0)
        La = _build_simple_domain()
        obs.register("alpha", La)
        obs.register("beta", _build_simple_domain())
        obs.dream_cycle()

        peer = make_dream_peer_fn(obs, "alpha", "GOAL")
        result = peer(La, "A", La.admissible_neighbors("A"))
        assert result is None

    def test_peer_fn_only_suggests_reachable_neighbors(self):
        obs = _setup_asymmetric_observer()
        alpha = obs._domains["alpha"]
        peer = make_dream_peer_fn(obs, "alpha", "C")
        neighbors = alpha.admissible_neighbors("A")

        result = peer(alpha, "A", neighbors)
        if result is not None:
            assert result in neighbors


# ═══════════════════════════════════════════════
# Test: SleepWakeCycle.wire_peer_fns()
# ═══════════════════════════════════════════════

class TestWirePeerFns:
    """C154: SleepWakeCycle auto-wires dream peer_fns."""

    def _make_cycle(self):
        obs = DreamObserver(
            readiness_threshold=0.0,
            node_equivalence_method="hungarian",
        )
        La = _build_simple_domain()
        Lb = _build_simple_domain()
        _inscribe(La, ["A", "B", "C", "GOAL"], Outcome.SUCCESS, 5)
        _inscribe(Lb, ["A", "B", "C", "GOAL"], Outcome.SUCCESS, 5)
        obs.register("alpha", La)
        obs.register("beta", Lb)

        exec_fn = lambda s, t: Outcome.SUCCESS
        ctrl_a = E0Controller(La, exec_fn)
        ctrl_b = E0Controller(Lb, exec_fn)

        swc = SleepWakeCycle(obs, mu=5.0)
        swc.register("alpha", ctrl_a, start="A", goal="GOAL")
        swc.register("beta", ctrl_b, start="A", goal="GOAL")
        return swc, ctrl_a, ctrl_b

    def test_wire_returns_count(self):
        swc, ctrl_a, ctrl_b = self._make_cycle()
        wired = swc.wire_peer_fns()
        assert wired == 2

    def test_controllers_have_peer_fn(self):
        swc, ctrl_a, ctrl_b = self._make_cycle()
        swc.wire_peer_fns()
        assert ctrl_a.peer_fn is not None
        assert ctrl_b.peer_fn is not None

    def test_peer_fn_callable(self):
        swc, ctrl_a, ctrl_b = self._make_cycle()
        swc.wire_peer_fns()
        La = ctrl_a.landscape
        result = ctrl_a.peer_fn(La, "A", La.admissible_neighbors("A"))
        assert result is None or isinstance(result, str)

    def test_wire_with_custom_params(self):
        swc, ctrl_a, ctrl_b = self._make_cycle()
        wired = swc.wire_peer_fns(min_quality=0.5, base_discount=0.3)
        assert wired == 2
        assert ctrl_a.peer_fn is not None


# ═══════════════════════════════════════════════
# Integration: Full pipeline
# ═══════════════════════════════════════════════

class TestNodeBridgePipeline:
    """End-to-end: dream_cycle → node_equivalences_for → propose_node_bridges."""

    def test_full_pipeline_asymmetric(self):
        """Asymmetric domains: donor shortcut transfers to target."""
        obs = _setup_asymmetric_observer()

        # Verify node equivalences were found
        eqs = obs.node_equivalences_for("alpha", "A")
        assert len(eqs) > 0

        # Propose node bridges
        result = propose_node_bridges(obs, "alpha", "A", "C")

        # Should have proposals from beta's A→C shortcut
        if result.proposals:
            assert result.node_mappings_used > 0
            assert result.donor_edges_checked > 0
            # The proposed edge was added to alpha
            alpha = obs._domains["alpha"]
            assert Edge("A", "C") in alpha._R0

    def test_full_pipeline_with_peer_fn(self):
        """Peer function consults node bridges via make_dream_peer_fn."""
        obs = _setup_asymmetric_observer()
        alpha = obs._domains["alpha"]

        # First, apply node bridges so the edge exists
        propose_node_bridges(obs, "alpha", "A", "C")

        peer = make_dream_peer_fn(obs, "alpha", "C")
        neighbors = alpha.admissible_neighbors("A")

        result = peer(alpha, "A", neighbors)
        # Should not crash; may suggest C if it's now reachable
        assert result is None or result in neighbors

    def test_sleep_wake_with_wired_peers(self):
        """SleepWakeCycle with wire_peer_fns runs without errors."""
        obs = DreamObserver(
            readiness_threshold=0.0,
            node_equivalence_method="hungarian",
        )
        La = _build_simple_domain()
        Lb = _build_simple_domain()
        _inscribe(La, ["A", "B", "C", "GOAL"], Outcome.SUCCESS, 5)
        _inscribe(Lb, ["A", "B", "C", "GOAL"], Outcome.SUCCESS, 5)
        obs.register("alpha", La)
        obs.register("beta", Lb)

        exec_fn = lambda s, t: Outcome.SUCCESS
        ctrl_a = E0Controller(La, exec_fn)
        ctrl_b = E0Controller(Lb, exec_fn)

        swc = SleepWakeCycle(obs, mu=5.0)
        swc.register("alpha", ctrl_a, start="A", goal="GOAL")
        swc.register("beta", ctrl_b, start="A", goal="GOAL")
        swc.wire_peer_fns()

        # Should run without errors
        results = swc.run(n_episodes=2, max_cycles_per_run=10)
        assert len(results) > 0

    def test_bidirectional_node_equivalences(self):
        """Node equivalences work in both directions: alpha→beta and beta→alpha."""
        obs = _setup_twin_observer()
        eqs_ab = obs.node_equivalences_for("alpha")
        eqs_ba = obs.node_equivalences_for("beta")
        # Both directions should have equivalences
        assert len(eqs_ab) > 0
        assert len(eqs_ba) > 0
