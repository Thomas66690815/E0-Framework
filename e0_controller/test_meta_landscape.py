"""
Tests for C296: MetaLandscape + C297: MetaController
======================================================
Covers:
    TestSigConversion        — sig_to_meta_state / meta_state_to_sig
    TestMetaLandscapeEmpty   — edge cases (empty, single record)
    TestMetaLandscapeEdges   — edge construction from consecutive sigs
    TestMetaLandscapeQuality — use_quality_seed option
    TestMetaLandscapeFromSigs— from_signatures() convenience method
    TestMakeMetaExecuteFn    — factory function and defaults
    TestMetaControllerProof  — E0Controller on MetaLandscape (self-similarity)
    TestMetaE0TurnProof      — E0Turn on MetaLandscape (full loop)
"""

from __future__ import annotations

import pytest

from e0_controller.controller import E0Controller
from e0_controller.e0_turn import E0Turn
from e0_controller.e2_port import LambdaE2Port
from e0_controller.landscape import Landscape
from e0_controller.meta_controller import make_meta_execute_fn, make_domain_meta_execute_fn
from e0_controller.meta_landscape import (
    MetaLandscape,
    meta_state_to_sig,
    sig_to_meta_state,
)
from e0_controller.primitives import Edge, Outcome
from e0_controller.trajectory import (
    PathSignature,
    TrajectoryHistorization,
    TrajectoryRecord,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_record(
    sig: PathSignature,
    coverage_delta: float = 0.01,
    mode: str = "teach",
) -> TrajectoryRecord:
    return TrajectoryRecord(
        signature=sig,
        mode=mode,
        coverage_delta=coverage_delta,
        community_crossings=len(sig) - 1,
    )


def make_traj_hist(records: list) -> TrajectoryHistorization:
    th = TrajectoryHistorization()
    for r in records:
        th.inscribe(r)
    return th


# ── TestSigConversion ─────────────────────────────────────────────────────────

class TestSigConversion:
    def test_single_element(self):
        sig = (0,)
        assert sig_to_meta_state(sig) == "(0,)"

    def test_two_elements(self):
        sig = (0, 1)
        assert sig_to_meta_state(sig) == "(0, 1)"

    def test_three_elements(self):
        sig = (0, 1, 0)
        assert sig_to_meta_state(sig) == "(0, 1, 0)"

    def test_empty_sig(self):
        sig = ()
        assert sig_to_meta_state(sig) == "()"

    def test_roundtrip_single(self):
        sig = (2,)
        assert meta_state_to_sig(sig_to_meta_state(sig)) == sig

    def test_roundtrip_triple(self):
        sig = (0, 1, 0)
        assert meta_state_to_sig(sig_to_meta_state(sig)) == sig

    def test_roundtrip_two(self):
        sig = (1, 2)
        assert meta_state_to_sig(sig_to_meta_state(sig)) == sig

    def test_meta_state_to_sig_invalid_raises(self):
        with pytest.raises(ValueError):
            meta_state_to_sig("not a tuple")

    def test_meta_state_to_sig_empty(self):
        assert meta_state_to_sig("()") == ()

    def test_meta_state_to_sig_non_int_raises(self):
        with pytest.raises(ValueError):
            meta_state_to_sig("('a', 'b')")


# ── TestMetaLandscapeEmpty ────────────────────────────────────────────────────

class TestMetaLandscapeEmpty:
    def test_empty_records_returns_landscape(self):
        ls = MetaLandscape.from_records([])
        assert isinstance(ls, Landscape)

    def test_empty_records_no_states(self):
        ls = MetaLandscape.from_records([])
        assert len(ls.states) == 0

    def test_empty_records_no_edges(self):
        ls = MetaLandscape.from_records([])
        assert len(ls.edges) == 0

    def test_single_record_one_state(self):
        records = [make_record((0, 1, 0))]
        ls = MetaLandscape.from_records(records)
        assert len(ls.states) == 1

    def test_single_record_no_edges(self):
        records = [make_record((0, 1, 0))]
        ls = MetaLandscape.from_records(records)
        assert len(ls.edges) == 0

    def test_single_record_state_label(self):
        records = [make_record((0, 1, 0))]
        ls = MetaLandscape.from_records(records)
        assert "(0, 1, 0)" in ls.states

    def test_consecutive_identical_sigs_no_edge(self):
        records = [make_record((0,)), make_record((0,))]
        ls = MetaLandscape.from_records(records)
        assert len(ls.edges) == 0
        assert len(ls.states) == 1


# ── TestMetaLandscapeEdges ────────────────────────────────────────────────────

class TestMetaLandscapeEdges:
    def test_two_different_sigs_one_edge(self):
        records = [make_record((0,)), make_record((0, 1))]
        ls = MetaLandscape.from_records(records)
        assert len(ls.edges) == 1

    def test_edge_source_and_target(self):
        records = [make_record((0,)), make_record((0, 1))]
        ls = MetaLandscape.from_records(records)
        edge = ls.edges[0]
        assert edge.source == "(0,)"
        assert edge.target == "(0, 1)"

    def test_three_different_sigs_two_edges(self):
        records = [make_record((0,)), make_record((0, 1)), make_record((0,))]
        ls = MetaLandscape.from_records(records)
        assert len(ls.edges) == 2

    def test_return_edge_in_both_directions(self):
        records = [make_record((0,)), make_record((0, 1)), make_record((0,))]
        ls = MetaLandscape.from_records(records)
        sources = {e.source for e in ls.edges}
        targets = {e.target for e in ls.edges}
        assert "(0,)" in sources
        assert "(0, 1)" in sources
        assert "(0,)" in targets
        assert "(0, 1)" in targets

    def test_duplicate_edges_not_repeated(self):
        # (0,)→(0,1) appears twice — should be one edge
        records = [
            make_record((0,)), make_record((0, 1)),
            make_record((0,)), make_record((0, 1)),
        ]
        ls = MetaLandscape.from_records(records)
        # Only unique directed edges
        edge_pairs = [(e.source, e.target) for e in ls.edges]
        assert len(edge_pairs) == len(set(edge_pairs))

    def test_two_states_registered(self):
        records = [make_record((0,)), make_record((0, 1))]
        ls = MetaLandscape.from_records(records)
        assert "(0,)" in ls.states
        assert "(0, 1)" in ls.states

    def test_default_delta_is_half(self):
        records = [make_record((0,)), make_record((0, 1))]
        ls = MetaLandscape.from_records(records)
        edge = ls.edges[0]
        assert ls._delta[edge] == pytest.approx(0.5)

    def test_default_resistance_is_one(self):
        records = [make_record((0,)), make_record((0, 1))]
        ls = MetaLandscape.from_records(records)
        edge = ls.edges[0]
        assert ls._R0[edge] == pytest.approx(1.0)

    def test_custom_delta_and_resistance(self):
        records = [make_record((0,)), make_record((0, 1))]
        ls = MetaLandscape.from_records(records, delta=0.3, resistance=0.7)
        edge = ls.edges[0]
        assert ls._delta[edge] == pytest.approx(0.3)
        assert ls._R0[edge] == pytest.approx(0.7)

    def test_long_sequence_all_states_registered(self):
        sigs = [(0,), (0, 1), (0, 1, 2), (0,), (0, 1)]
        records = [make_record(s) for s in sigs]
        ls = MetaLandscape.from_records(records)
        assert "(0,)" in ls.states
        assert "(0, 1)" in ls.states
        assert "(0, 1, 2)" in ls.states


# ── TestMetaLandscapeQuality ──────────────────────────────────────────────────

class TestMetaLandscapeQuality:
    def test_quality_seed_cold_falls_back_to_default(self):
        """Cold sigs (trace_load=0) → use base delta even when use_quality_seed=True."""
        records = [make_record((0,)), make_record((0, 1))]
        traj_hist = TrajectoryHistorization()  # no inscriptions — cold
        ls = MetaLandscape.from_records(
            records, traj_hist=traj_hist,
            delta=0.5, use_quality_seed=True,
        )
        edge = ls.edges[0]
        assert ls._delta[edge] == pytest.approx(0.5)

    def test_quality_seed_warm_uses_quality_diff(self):
        """Warm sigs → delta = abs(quality_b - quality_a)."""
        sig_a = (0,)
        sig_b = (0, 1)
        rec_a = make_record(sig_a, coverage_delta=0.02)  # productive → U+1
        rec_b = make_record(sig_b, coverage_delta=0.0)   # stagnant   → F+1
        records = [rec_a, rec_b]
        traj_hist = make_traj_hist(records)
        ls = MetaLandscape.from_records(
            records, traj_hist=traj_hist,
            delta=0.5, use_quality_seed=True,
        )
        edge = ls.edges[0]
        qa = traj_hist.trace_quality(sig_a)
        qb = traj_hist.trace_quality(sig_b)
        expected = max(0.05, min(1.0, abs(qb - qa)))
        assert ls._delta[edge] == pytest.approx(expected)

    def test_quality_seed_false_uses_base_delta(self):
        """use_quality_seed=False always uses base delta."""
        sig_a = (0,)
        sig_b = (0, 1)
        records = [make_record(sig_a), make_record(sig_b)]
        traj_hist = make_traj_hist(records)
        ls = MetaLandscape.from_records(
            records, traj_hist=traj_hist,
            delta=0.4, use_quality_seed=False,
        )
        edge = ls.edges[0]
        assert ls._delta[edge] == pytest.approx(0.4)


# ── TestMetaLandscapeFromSigs ─────────────────────────────────────────────────

class TestMetaLandscapeFromSigs:
    def test_empty_returns_landscape(self):
        ls = MetaLandscape.from_signatures([])
        assert isinstance(ls, Landscape)

    def test_single_sig_one_state(self):
        ls = MetaLandscape.from_signatures([(0,)])
        assert len(ls.states) == 1

    def test_two_sigs_one_edge(self):
        ls = MetaLandscape.from_signatures([(0,), (0, 1)])
        assert len(ls.edges) == 1

    def test_consecutive_identical_no_edge(self):
        ls = MetaLandscape.from_signatures([(0,), (0,), (0, 1)])
        assert len(ls.edges) == 1

    def test_custom_delta(self):
        ls = MetaLandscape.from_signatures([(0,), (0, 1)], delta=0.3)
        edge = ls.edges[0]
        assert ls._delta[edge] == pytest.approx(0.3)


# ── TestMakeMetaExecuteFn ─────────────────────────────────────────────────────

class TestMakeMetaExecuteFn:
    def test_returns_callable(self):
        fn = make_meta_execute_fn()
        assert callable(fn)

    def test_default_success(self):
        fn = make_meta_execute_fn()
        assert fn("(0,)", "(0, 1)") == Outcome.SUCCESS

    def test_default_failure(self):
        fn = make_meta_execute_fn(default=Outcome.FAILURE)
        assert fn("(0,)", "(0, 1)") == Outcome.FAILURE

    def test_explicit_outcome_overrides_default(self):
        fn = make_meta_execute_fn(
            outcomes={("(0,)", "(0, 1)"): Outcome.FAILURE},
            default=Outcome.SUCCESS,
        )
        assert fn("(0,)", "(0, 1)") == Outcome.FAILURE
        assert fn("(0,)", "(0, 1, 0)") == Outcome.SUCCESS

    def test_unmatched_pair_uses_default(self):
        fn = make_meta_execute_fn(
            outcomes={("A", "B"): Outcome.FAILURE},
            default=Outcome.SUCCESS,
        )
        assert fn("X", "Y") == Outcome.SUCCESS

    def test_empty_outcomes_all_default(self):
        fn = make_meta_execute_fn(outcomes={}, default=Outcome.PARTIAL)
        assert fn("any", "thing") == Outcome.PARTIAL

    def test_make_domain_meta_execute_fn_success(self):
        fn = make_domain_meta_execute_fn(domain_run_fn=lambda t, n: True)
        assert fn("(0,)", "(0, 1)") == Outcome.SUCCESS

    def test_make_domain_meta_execute_fn_failure(self):
        fn = make_domain_meta_execute_fn(domain_run_fn=lambda t, n: False)
        assert fn("(0,)", "(0, 1)") == Outcome.FAILURE

    def test_make_domain_meta_execute_fn_exception_is_failure(self):
        def raising_fn(t, n): raise RuntimeError("boom")
        fn = make_domain_meta_execute_fn(domain_run_fn=raising_fn)
        assert fn("(0,)", "(0, 1)") == Outcome.FAILURE


# ── TestMetaControllerProof ───────────────────────────────────────────────────
# This is the structural self-similarity proof:
# E0Controller runs on a MetaLandscape WITHOUT ANY MODIFICATION.

class TestMetaControllerProof:
    """Structural self-similarity proof: E0Controller on MetaLandscape.

    The E0Controller code is identical for domain-level and meta-level.
    These tests verify that the controller operates correctly at Level 2
    (PathSignature navigation) using the same loop as Level 1 (domain navigation).
    """

    def test_e0controller_accepts_meta_landscape(self):
        """E0Controller can be constructed with MetaLandscape — no changes needed."""
        sigs = [(0,), (0, 1), (0,)]
        meta_ls = MetaLandscape.from_signatures(sigs)
        meta_exec = make_meta_execute_fn()
        # This line is the proof: same constructor, same API, different Landscape
        ctrl = E0Controller(meta_ls, meta_exec)
        assert ctrl is not None

    def test_e0controller_meta_cycle_runs(self):
        sigs = [(0,), (0, 1), (0,)]
        meta_ls = MetaLandscape.from_signatures(sigs)
        meta_exec = make_meta_execute_fn()
        ctrl = E0Controller(meta_ls, meta_exec)
        step = ctrl.cycle("(0,)")
        # cycle() returns StepResult or None — not None when edges exist
        assert step is not None

    def test_e0controller_meta_run_to_goal(self):
        sigs = [(0,), (0, 1), (0, 1, 0)]
        meta_ls = MetaLandscape.from_signatures(sigs)
        meta_exec = make_meta_execute_fn()
        ctrl = E0Controller(meta_ls, meta_exec)
        trace = ctrl.run(start="(0,)", goal="(0, 1, 0)", max_cycles=10)
        assert trace is not None

    def test_e0controller_meta_historization_updated(self):
        """After meta-cycle, meta-landscape historization is inscribed."""
        sigs = [(0,), (0, 1)]
        meta_ls = MetaLandscape.from_signatures(sigs)
        meta_exec = make_meta_execute_fn()
        ctrl = E0Controller(meta_ls, meta_exec)
        edge = Edge("(0,)", "(0, 1)")
        inertia_before = meta_ls.historization.inertia_factor(edge)
        ctrl.cycle("(0,)")
        inertia_after = meta_ls.historization.inertia_factor(edge)
        assert inertia_after != inertia_before

    def test_meta_failure_historized(self):
        """FAILURE on meta transition → trace_load > 0 after inscription."""
        sigs = [(0,), (0, 1)]
        meta_ls = MetaLandscape.from_signatures(sigs)
        meta_exec = make_meta_execute_fn(
            outcomes={("(0,)", "(0, 1)"): Outcome.FAILURE}
        )
        ctrl = E0Controller(meta_ls, meta_exec)
        edge = Edge("(0,)", "(0, 1)")
        load_before = meta_ls.historization.trace_load(edge)
        ctrl.cycle("(0,)")
        load_after = meta_ls.historization.trace_load(edge)
        # FAILURE is inscribed → trace_load increases
        assert load_after > load_before

    def test_meta_success_inscribed(self):
        """Multiple SUCCESS meta-cycles → trace_load increases on traversed edge."""
        sigs = [(0,), (0, 1)]
        meta_ls = MetaLandscape.from_signatures(sigs)
        meta_exec = make_meta_execute_fn()
        ctrl = E0Controller(meta_ls, meta_exec)
        edge = Edge("(0,)", "(0, 1)")
        for _ in range(5):
            ctrl.cycle("(0,)")
        # After 5 successes, edge is well-known (trace_load > 0)
        assert meta_ls.historization.trace_load(edge) > 0

    def test_meta_from_records_same_controller_works(self):
        """from_records() path also works with E0Controller."""
        sigs = [(0,), (0, 1), (0, 1, 2)]
        records = [make_record(s) for s in sigs]
        traj_hist = make_traj_hist(records)
        meta_ls = MetaLandscape.from_records(records, traj_hist)
        meta_exec = make_meta_execute_fn()
        ctrl = E0Controller(meta_ls, meta_exec)
        trace = ctrl.run(start="(0,)", goal="(0, 1, 2)", max_cycles=10)
        assert trace is not None


# ── TestMetaE0TurnProof ───────────────────────────────────────────────────────

class TestMetaE0TurnProof:
    """E0Turn also operates on MetaLandscape — full loop proof."""

    def test_e0turn_accepts_meta_landscape(self):
        sigs = [(0,), (0, 1), (0,)]
        meta_ls = MetaLandscape.from_signatures(sigs)
        meta_port = LambdaE2Port(fn=lambda s, a: Outcome.SUCCESS, name="meta_port")
        session = E0Turn(meta_ls, meta_port)
        assert session is not None

    def test_e0turn_meta_run_turn(self):
        sigs = [(0,), (0, 1)]
        meta_ls = MetaLandscape.from_signatures(sigs)
        meta_port = LambdaE2Port(fn=lambda s, a: Outcome.SUCCESS, name="meta_port")
        session = E0Turn(meta_ls, meta_port)
        result = session.run_turn("(0,)")
        assert result is not None
        assert result.outcome == Outcome.SUCCESS

    def test_e0turn_meta_run_to_goal(self):
        sigs = [(0,), (0, 1), (0, 1, 0)]
        meta_ls = MetaLandscape.from_signatures(sigs)
        meta_port = LambdaE2Port(fn=lambda s, a: Outcome.SUCCESS, name="meta_port")
        session = E0Turn(meta_ls, meta_port)
        turns = list(session.run("(0,)", max_turns=10, goal="(0, 1, 0)"))
        final = turns[-1].state_after if turns else None
        assert final == "(0, 1, 0)"

    def test_e0turn_meta_state_labels_are_sig_strings(self):
        sigs = [(0,), (0, 1)]
        meta_ls = MetaLandscape.from_signatures(sigs)
        meta_port = LambdaE2Port(fn=lambda s, a: Outcome.SUCCESS, name="meta_port")
        session = E0Turn(meta_ls, meta_port)
        result = session.run_turn("(0,)")
        assert result.state_before == "(0,)"
        assert result.action == "(0, 1)"

    def test_e0turn_meta_history_records_turns(self):
        sigs = [(0,), (0, 1), (0,)]
        meta_ls = MetaLandscape.from_signatures(sigs)
        meta_port = LambdaE2Port(fn=lambda s, a: Outcome.SUCCESS, name="meta_port")
        session = E0Turn(meta_ls, meta_port)
        list(session.run("(0,)", max_turns=5))
        assert len(session.history()) > 0
