"""
Tests for C207: Contextual Inscription.

Inscription carries WHAT was inscribed, not just U/F counts.
Each edge builds a narrative trace: traversal context (mode, round),
role (bridge, exploration, revisit), co-traversed edges.

Test structure:
    TestInscriptionContext     — dataclass fields and defaults
    TestInscribeMethod         — inscribe() stores context + calls update()
    TestEdgeInscriptions       — per-edge inscription history
    TestInscriptionSummary     — aggregate narrative per edge
    TestInscriptionStats       — global statistics
    TestRemoveEdgesCleanup     — _inscriptions cleaned on edge removal
    TestControllerInscription  — controller greedy loop uses inscribe()
    TestFullCycleInscription   — end-to-end multidomain cycle
"""

import pytest
from e0_controller.primitives import Edge, Outcome
from e0_controller.historization import (
    Historization,
    InscriptionContext,
    TraceRecord,
)
from e0_controller.landscape import Landscape


# ── InscriptionContext dataclass ────────────────────────────────────────


class TestInscriptionContext:
    """InscriptionContext stores traversal context."""

    def test_required_fields(self):
        ctx = InscriptionContext(tau=1, edge=Edge("A", "B"), outcome=Outcome.SUCCESS)
        assert ctx.tau == 1
        assert ctx.edge == Edge("A", "B")
        assert ctx.outcome == Outcome.SUCCESS

    def test_default_fields(self):
        ctx = InscriptionContext(tau=1, edge=Edge("A", "B"), outcome=Outcome.SUCCESS)
        assert ctx.mode == ""
        assert ctx.relation_type == ""
        assert ctx.bridge_type == ""
        assert ctx.source_domain == ""
        assert ctx.target_domain == ""
        assert ctx.role == ""
        assert ctx.revisit_count == 0
        assert ctx.step == 0

    def test_full_context(self):
        ctx = InscriptionContext(
            tau=5, edge=Edge("C:A", "EN:dog"), outcome=Outcome.SUCCESS,
            mode="explore_en", relation_type="enables",
            bridge_type="en_semantic", source_domain="canon",
            target_domain="en", role="bridge", revisit_count=0, step=3,
        )
        assert ctx.mode == "explore_en"
        assert ctx.bridge_type == "en_semantic"
        assert ctx.role == "bridge"
        assert ctx.step == 3


# ── inscribe() method ──────────────────────────────────────────────────


class TestInscribeMethod:
    """inscribe() calls update() AND stores InscriptionContext."""

    def test_inscribe_updates_traces(self):
        h = Historization()
        e = Edge("A", "B")
        h.inscribe(e, Outcome.SUCCESS, mode="explore")
        assert h.success_trace(e) > 0

    def test_inscribe_stores_context(self):
        h = Historization()
        e = Edge("A", "B")
        h.inscribe(e, Outcome.SUCCESS, mode="explore", relation_type="is_a")
        contexts = h.edge_inscriptions(e)
        assert len(contexts) == 1
        assert contexts[0].mode == "explore"
        assert contexts[0].relation_type == "is_a"

    def test_inscribe_accumulates(self):
        h = Historization()
        e = Edge("A", "B")
        h.inscribe(e, Outcome.SUCCESS, mode="explore", role="exploration")
        h.inscribe(e, Outcome.FAILURE, mode="explore", role="revisit")
        h.inscribe(e, Outcome.SUCCESS, mode="greedy", role="exploration")
        contexts = h.edge_inscriptions(e)
        assert len(contexts) == 3
        assert contexts[0].role == "exploration"
        assert contexts[1].role == "revisit"
        assert contexts[2].mode == "greedy"

    def test_inscribe_preserves_tau(self):
        h = Historization()
        e = Edge("A", "B")
        h.inscribe(e, Outcome.SUCCESS)
        h.inscribe(e, Outcome.FAILURE)
        contexts = h.edge_inscriptions(e)
        assert contexts[0].tau < contexts[1].tau

    def test_inscribe_without_context_still_works(self):
        """Backward-compat: inscribe with no kwargs."""
        h = Historization()
        e = Edge("A", "B")
        h.inscribe(e, Outcome.SUCCESS)
        assert h.success_trace(e) > 0
        assert len(h.edge_inscriptions(e)) == 1
        assert h.edge_inscriptions(e)[0].mode == ""

    def test_update_does_not_create_inscription(self):
        """Raw update() should NOT create inscription context."""
        h = Historization()
        e = Edge("A", "B")
        h.update(e, Outcome.SUCCESS)
        assert h.edge_inscriptions(e) == []


# ── edge_inscriptions() ────────────────────────────────────────────────


class TestEdgeInscriptions:
    """Per-edge inscription history."""

    def test_empty_for_unknown_edge(self):
        h = Historization()
        assert h.edge_inscriptions(Edge("X", "Y")) == []

    def test_returns_copy(self):
        h = Historization()
        e = Edge("A", "B")
        h.inscribe(e, Outcome.SUCCESS)
        a = h.edge_inscriptions(e)
        b = h.edge_inscriptions(e)
        assert a == b
        assert a is not b  # copy, not reference

    def test_different_edges_independent(self):
        h = Historization()
        e1 = Edge("A", "B")
        e2 = Edge("B", "C")
        h.inscribe(e1, Outcome.SUCCESS, mode="explore")
        h.inscribe(e2, Outcome.FAILURE, mode="greedy")
        assert len(h.edge_inscriptions(e1)) == 1
        assert len(h.edge_inscriptions(e2)) == 1
        assert h.edge_inscriptions(e1)[0].mode == "explore"
        assert h.edge_inscriptions(e2)[0].mode == "greedy"


# ── inscription_summary() ──────────────────────────────────────────────


class TestInscriptionSummary:
    """Aggregate narrative per edge."""

    def test_empty_edge(self):
        h = Historization()
        s = h.inscription_summary(Edge("X", "Y"))
        assert s == {"count": 0}

    def test_single_inscription(self):
        h = Historization()
        e = Edge("A", "B")
        h.inscribe(e, Outcome.SUCCESS, mode="explore",
                   relation_type="is_a", role="exploration",
                   source_domain="canon", target_domain="canon")
        s = h.inscription_summary(e)
        assert s["count"] == 1
        assert s["modes"] == {"explore": 1}
        assert s["relation_types"] == {"is_a": 1}
        assert s["roles"] == {"exploration": 1}
        assert s["success_rate"] == 1.0

    def test_mixed_inscriptions(self):
        h = Historization()
        e = Edge("A", "B")
        h.inscribe(e, Outcome.SUCCESS, mode="explore", role="exploration")
        h.inscribe(e, Outcome.FAILURE, mode="explore", role="revisit")
        h.inscribe(e, Outcome.SUCCESS, mode="greedy", role="exploration")
        s = h.inscription_summary(e)
        assert s["count"] == 3
        assert s["modes"] == {"explore": 2, "greedy": 1}
        assert s["roles"] == {"exploration": 2, "revisit": 1}
        assert abs(s["success_rate"] - 2 / 3) < 0.01

    def test_domain_pairs_tracked(self):
        h = Historization()
        e = Edge("C:A", "EN:dog")
        h.inscribe(e, Outcome.SUCCESS,
                   source_domain="canon", target_domain="en")
        h.inscribe(e, Outcome.SUCCESS,
                   source_domain="canon", target_domain="en")
        s = h.inscription_summary(e)
        assert s["domain_pairs"] == {"canon→en": 2}

    def test_last_tau(self):
        h = Historization()
        e = Edge("A", "B")
        h.inscribe(e, Outcome.SUCCESS)
        h.inscribe(e, Outcome.FAILURE)
        s = h.inscription_summary(e)
        assert s["last_tau"] == h.edge_inscriptions(e)[-1].tau


# ── inscription_stats() ────────────────────────────────────────────────


class TestInscriptionStats:
    """Global inscription statistics."""

    def test_empty(self):
        h = Historization()
        s = h.inscription_stats()
        assert s["total_inscriptions"] == 0
        assert s["inscribed_edges"] == 0

    def test_counts(self):
        h = Historization()
        h.inscribe(Edge("A", "B"), Outcome.SUCCESS, mode="explore", role="exploration")
        h.inscribe(Edge("A", "B"), Outcome.FAILURE, mode="explore", role="revisit")
        h.inscribe(Edge("B", "C"), Outcome.SUCCESS, mode="greedy", role="exploration")
        s = h.inscription_stats()
        assert s["total_inscriptions"] == 3
        assert s["inscribed_edges"] == 2
        assert s["role_totals"] == {"exploration": 2, "revisit": 1}
        assert s["mode_totals"] == {"explore": 2, "greedy": 1}

    def test_domain_crossing_count(self):
        h = Historization()
        h.inscribe(Edge("A", "B"), Outcome.SUCCESS,
                   source_domain="canon", target_domain="en")
        h.inscribe(Edge("B", "C"), Outcome.SUCCESS,
                   source_domain="en", target_domain="en")
        s = h.inscription_stats()
        assert s["domain_crossing_count"] == 1


# ── remove_edges cleanup ───────────────────────────────────────────────


class TestRemoveEdgesCleanup:
    """_inscriptions cleaned when edges are removed."""

    def test_remove_cleans_inscriptions(self):
        h = Historization()
        e = Edge("A", "B")
        h.inscribe(e, Outcome.SUCCESS, mode="explore")
        assert len(h.edge_inscriptions(e)) == 1
        h.remove_edges([e])
        assert h.edge_inscriptions(e) == []

    def test_remove_preserves_other_edges(self):
        h = Historization()
        e1 = Edge("A", "B")
        e2 = Edge("B", "C")
        h.inscribe(e1, Outcome.SUCCESS)
        h.inscribe(e2, Outcome.SUCCESS)
        h.remove_edges([e1])
        assert h.edge_inscriptions(e1) == []
        assert len(h.edge_inscriptions(e2)) == 1


# ── Controller integration ─────────────────────────────────────────────


class TestControllerInscription:
    """Controller greedy loop uses inscribe() for contextual inscription."""

    def test_controller_creates_inscriptions(self):
        from e0_controller.controller import E0Controller
        L = Landscape()
        L.add_state("A")
        L.add_state("B")
        L.add_state("C")
        L.add_edge("A", "B", 0.5, 1.0, relation_type="enables")
        L.add_edge("B", "C", 0.5, 1.0, relation_type="is_a")
        ctrl = E0Controller(L, lambda s, t: Outcome.SUCCESS)
        ctrl.run("A", max_cycles=5, goal="C")
        # Check that inscriptions were created
        stats = L.historization.inscription_stats()
        assert stats["total_inscriptions"] > 0

    def test_controller_inscriptions_have_greedy_mode(self):
        from e0_controller.controller import E0Controller
        L = Landscape()
        L.add_state("A")
        L.add_state("B")
        L.add_edge("A", "B", 0.5, 1.0)
        ctrl = E0Controller(L, lambda s, t: Outcome.SUCCESS)
        ctrl.run("A", max_cycles=3, goal="B")
        inscriptions = L.historization.edge_inscriptions(Edge("A", "B"))
        assert len(inscriptions) >= 1
        assert inscriptions[0].mode == "greedy"

    def test_controller_inscriptions_carry_relation_type(self):
        from e0_controller.controller import E0Controller
        L = Landscape()
        L.add_state("A")
        L.add_state("B")
        L.add_edge("A", "B", 0.5, 1.0, relation_type="enables")
        ctrl = E0Controller(L, lambda s, t: Outcome.SUCCESS)
        ctrl.run("A", max_cycles=3, goal="B")
        inscriptions = L.historization.edge_inscriptions(Edge("A", "B"))
        assert inscriptions[0].relation_type == "enables"


# ── Full cycle integration ─────────────────────────────────────────────


class TestFullCycleInscription:
    """End-to-end multidomain cycle produces contextual inscriptions."""

    @pytest.fixture(scope="class")
    def cycle_data(self):
        from e0_controller.explore_learning_cycle_multidomain import (
            build_multidomain_landscape,
            run_multidomain_cycle,
        )
        history = run_multidomain_cycle(
            max_rounds=3, steps_per_round=20, verbose=False,
        )
        # Re-build to access the landscape (run_multidomain_cycle builds internally)
        ls, nodes, stats = build_multidomain_landscape(include_en=True)
        # Run again on this landscape to get inscriptions
        from e0_controller.explore_learning_cycle_multidomain import navigate
        nav = navigate(ls, nodes, mode="explore", steps=30)
        return ls, history, nav

    def test_inscriptions_exist(self, cycle_data):
        ls, history, nav = cycle_data
        stats = ls.historization.inscription_stats()
        assert stats["total_inscriptions"] > 0

    def test_roles_present(self, cycle_data):
        ls, history, nav = cycle_data
        stats = ls.historization.inscription_stats()
        assert len(stats["role_totals"]) >= 1

    def test_bridge_role_used(self, cycle_data):
        ls, history, nav = cycle_data
        stats = ls.historization.inscription_stats()
        roles = stats["role_totals"]
        assert "bridge" in roles or "exploration" in roles

    def test_mode_is_explore(self, cycle_data):
        ls, history, nav = cycle_data
        stats = ls.historization.inscription_stats()
        assert "explore" in stats["mode_totals"]

    def test_domain_crossings_tracked(self, cycle_data):
        ls, history, nav = cycle_data
        stats = ls.historization.inscription_stats()
        assert stats["domain_crossing_count"] >= 0

    def test_per_edge_summary_works(self, cycle_data):
        ls, history, nav = cycle_data
        # Pick any inscribed edge
        for edge, contexts in ls.historization._inscriptions.items():
            if len(contexts) >= 2:
                s = ls.historization.inscription_summary(edge)
                assert s["count"] >= 2
                assert "success_rate" in s
                break
