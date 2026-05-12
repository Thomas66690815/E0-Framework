"""
Tests for FileSensor (C305).

Test classes:
    TestParseOutcomeStr        — string → Outcome mapping
    TestInjectionReportMerge   — InjectionReport.merge()
    TestFileSensorInit         — construction, defaults
    TestInjectCsvTopologyOnly  — CSV without outcome column
    TestInjectCsvWithOutcomes  — CSV with outcome column
    TestInjectCsvEdgeCases     — empty, malformed, self-loops, headers
    TestInjectJsonSchemaA      — edge list (Schema A)
    TestInjectJsonSchemaB      — DomainSpec topology (Schema B)
    TestInjectJsonSchemaC      — trace log (Schema C)
    TestInjectJsonEdgeCases    — malformed JSON, missing keys
    TestInjectTextNoCaller     — inject_text without call_fn
    TestInjectAutoDetect       — generic inject() format detection
    TestIdempotency            — duplicate edges are no-ops
    TestHistorizationState     — U/F traces correct after injection
    TestLandscapeSummary       — landscape_summary() counts
"""

from __future__ import annotations

import json
import pytest

from e0_controller.file_sensor import FileSensor, InjectionReport, parse_outcome_str
from e0_controller.landscape import Landscape
from e0_controller.primitives import Edge, Outcome


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def fresh() -> tuple[Landscape, FileSensor]:
    L = Landscape()
    return L, FileSensor(L)


def edge_set(L: Landscape) -> set[tuple[str, str]]:
    return {(e.source, e.target) for e in L.edges}


def hist_u(L: Landscape, src: str, tgt: str) -> float:
    return L.historization._U.get(Edge(src, tgt), 0.0)


def hist_f(L: Landscape, src: str, tgt: str) -> float:
    return L.historization._F.get(Edge(src, tgt), 0.0)


# ─────────────────────────────────────────────────────────────────────────────
# TestParseOutcomeStr
# ─────────────────────────────────────────────────────────────────────────────

class TestParseOutcomeStr:
    def test_success_variants(self):
        for s in ("success", "SUCCESS", "ok", "OK", "1", "true", "True"):
            assert parse_outcome_str(s) == Outcome.SUCCESS, s

    def test_failure_variants(self):
        for s in ("failure", "FAILURE", "fail", "error", "0", "false"):
            assert parse_outcome_str(s) == Outcome.FAILURE, s

    def test_partial_variants(self):
        for s in ("partial", "PARTIAL", "p", "half"):
            assert parse_outcome_str(s) == Outcome.PARTIAL, s

    def test_unknown_returns_none(self):
        assert parse_outcome_str("unknown") is None
        assert parse_outcome_str("") is None
        assert parse_outcome_str("  ") is None

    def test_whitespace_stripped(self):
        assert parse_outcome_str("  success  ") == Outcome.SUCCESS


# ─────────────────────────────────────────────────────────────────────────────
# TestInjectionReportMerge
# ─────────────────────────────────────────────────────────────────────────────

class TestInjectionReportMerge:
    def test_merge_sums_fields(self):
        a = InjectionReport(edges_added=2, inscriptions=3, skipped=1, warnings=["w1"])
        b = InjectionReport(edges_added=5, inscriptions=7, skipped=2, warnings=["w2", "w3"])
        c = a.merge(b)
        assert c.edges_added == 7
        assert c.inscriptions == 10
        assert c.skipped == 3
        assert c.warnings == ["w1", "w2", "w3"]

    def test_merge_empty(self):
        a = InjectionReport(edges_added=1)
        b = InjectionReport()
        c = a.merge(b)
        assert c.edges_added == 1
        assert c.inscriptions == 0

    def test_repr_contains_counts(self):
        r = InjectionReport(edges_added=3, inscriptions=5, skipped=1, warnings=["x"])
        s = repr(r)
        assert "3" in s and "5" in s and "1" in s


# ─────────────────────────────────────────────────────────────────────────────
# TestFileSensorInit
# ─────────────────────────────────────────────────────────────────────────────

class TestFileSensorInit:
    def test_default_parameters(self):
        L = Landscape()
        s = FileSensor(L)
        assert s._default_delta == 1.0
        assert s._default_resistance == 0.3

    def test_custom_parameters(self):
        L = Landscape()
        s = FileSensor(L, default_delta=0.5, default_resistance=0.8)
        assert s._default_delta == 0.5
        assert s._default_resistance == 0.8

    def test_holds_landscape_reference(self):
        L = Landscape()
        s = FileSensor(L)
        assert s._L is L


# ─────────────────────────────────────────────────────────────────────────────
# TestInjectCsvTopologyOnly
# ─────────────────────────────────────────────────────────────────────────────

class TestInjectCsvTopologyOnly:
    def test_two_column_csv_adds_edges(self):
        L, s = fresh()
        report = s.inject_csv("A,B\nB,C\nC,D")
        assert report.edges_added == 3
        assert ("A", "B") in edge_set(L)

    def test_two_column_uses_partial_prior(self):
        L, s = fresh()
        s.inject_csv("A,B")
        # PARTIAL → U += 0.5, F += 0.3
        assert hist_u(L, "A", "B") == pytest.approx(0.5)
        assert hist_f(L, "A", "B") == pytest.approx(0.3)

    def test_header_row_skipped(self):
        L, s = fresh()
        report = s.inject_csv("source,target\nA,B\nB,C")
        assert report.edges_added == 2
        assert ("source", "target") not in edge_set(L)

    def test_from_to_header_skipped(self):
        L, s = fresh()
        report = s.inject_csv("from,to\nX,Y")
        assert report.edges_added == 1

    def test_whitespace_cells_trimmed(self):
        L, s = fresh()
        report = s.inject_csv("  A  ,  B  ")
        assert report.edges_added == 1
        assert ("A", "B") in edge_set(L)


# ─────────────────────────────────────────────────────────────────────────────
# TestInjectCsvWithOutcomes
# ─────────────────────────────────────────────────────────────────────────────

class TestInjectCsvWithOutcomes:
    def test_success_inscribes_u(self):
        L, s = fresh()
        s.inject_csv("A,B,success")
        # SUCCESS → U += 1.0, F += 0
        assert hist_u(L, "A", "B") == pytest.approx(1.0)
        assert hist_f(L, "A", "B") == pytest.approx(0.0)

    def test_failure_inscribes_f(self):
        L, s = fresh()
        s.inject_csv("A,B,failure")
        assert hist_u(L, "A", "B") == pytest.approx(0.0)
        assert hist_f(L, "A", "B") > 0

    def test_multiple_rows_accumulate(self):
        # After 2 SUCCESS + 1 FAILURE with rho-decay:
        # U: 0 → 1.0 → 1.9 → 1.71 (decayed by failure step)
        L, s = fresh()
        s.inject_csv("A,B,success\nA,B,success\nA,B,failure")
        assert hist_u(L, "A", "B") > 1.0  # success-dominant trace remains

    def test_report_counts_inscriptions(self):
        L, s = fresh()
        report = s.inject_csv("A,B,success\nB,C,failure\nC,D,partial")
        assert report.inscriptions == 3
        assert report.edges_added == 3

    def test_three_column_header_skipped(self):
        L, s = fresh()
        report = s.inject_csv("source,target,outcome\nA,B,success")
        assert report.inscriptions == 1
        assert report.edges_added == 1


# ─────────────────────────────────────────────────────────────────────────────
# TestInjectCsvEdgeCases
# ─────────────────────────────────────────────────────────────────────────────

class TestInjectCsvEdgeCases:
    def test_empty_csv(self):
        L, s = fresh()
        report = s.inject_csv("")
        assert report.edges_added == 0
        assert len(report.warnings) > 0

    def test_blank_lines_ignored(self):
        L, s = fresh()
        report = s.inject_csv("A,B,success\n\n\nB,C,failure")
        assert report.inscriptions == 2

    def test_self_loop_skipped(self):
        L, s = fresh()
        report = s.inject_csv("A,A,success")
        assert report.skipped == 1
        assert report.edges_added == 0

    def test_unknown_outcome_skips_row(self):
        L, s = fresh()
        report = s.inject_csv("A,B,garbage")
        assert report.skipped == 1
        assert report.inscriptions == 0

    def test_single_column_row_skipped(self):
        L, s = fresh()
        report = s.inject_csv("OnlyOneColumn")
        assert report.skipped == 1

    def test_empty_source_skipped(self):
        L, s = fresh()
        report = s.inject_csv(",B,success")
        assert report.skipped == 1


# ─────────────────────────────────────────────────────────────────────────────
# TestInjectJsonSchemaA
# ─────────────────────────────────────────────────────────────────────────────

class TestInjectJsonSchemaA:
    def test_edges_without_outcome(self):
        L, s = fresh()
        data = {"edges": [{"from": "A", "to": "B"}, {"from": "B", "to": "C"}]}
        report = s.inject_json(json.dumps(data))
        assert report.edges_added == 2
        assert report.inscriptions == 0

    def test_edges_with_outcome(self):
        L, s = fresh()
        data = {"edges": [
            {"from": "A", "to": "B", "outcome": "success"},
            {"from": "B", "to": "C", "outcome": "failure"},
        ]}
        report = s.inject_json(json.dumps(data))
        assert report.inscriptions == 2

    def test_custom_delta_resistance(self):
        L, s = fresh()
        data = {"edges": [{"from": "A", "to": "B", "delta": 2.0, "resistance": 0.7}]}
        s.inject_json(json.dumps(data))
        e = Edge("A", "B")
        assert L._delta[e] == pytest.approx(2.0)
        assert L._R0[e] == pytest.approx(0.7)

    def test_source_target_alias(self):
        L, s = fresh()
        data = {"edges": [{"source": "X", "target": "Y", "outcome": "success"}]}
        report = s.inject_json(json.dumps(data))
        assert ("X", "Y") in edge_set(L)
        assert report.inscriptions == 1

    def test_unknown_outcome_skipped(self):
        L, s = fresh()
        data = {"edges": [{"from": "A", "to": "B", "outcome": "bogus"}]}
        report = s.inject_json(json.dumps(data))
        assert report.skipped == 1
        assert report.inscriptions == 0


# ─────────────────────────────────────────────────────────────────────────────
# TestInjectJsonSchemaB
# ─────────────────────────────────────────────────────────────────────────────

class TestInjectJsonSchemaB:
    def test_domain_spec_adds_topology(self):
        L, s = fresh()
        spec = {
            "nodes": ["A", "B", "C"],
            "edges": [
                {"from": "A", "to": "B", "delta": 1.0, "resistance": 0.5},
                {"from": "B", "to": "C", "delta": 0.8, "resistance": 0.3},
            ],
        }
        report = s.inject_json(json.dumps(spec))
        assert report.edges_added == 2
        assert ("A", "B") in edge_set(L)

    def test_domain_spec_no_inscriptions(self):
        L, s = fresh()
        spec = {"nodes": ["A", "B"], "edges": [{"from": "A", "to": "B"}]}
        report = s.inject_json(json.dumps(spec))
        assert report.inscriptions == 0

    def test_self_loop_in_spec_skipped(self):
        L, s = fresh()
        spec = {"nodes": ["A"], "edges": [{"from": "A", "to": "A"}]}
        report = s.inject_json(json.dumps(spec))
        assert report.skipped == 1
        assert report.edges_added == 0


# ─────────────────────────────────────────────────────────────────────────────
# TestInjectJsonSchemaC
# ─────────────────────────────────────────────────────────────────────────────

class TestInjectJsonSchemaC:
    def test_trace_list_inscriptions(self):
        L, s = fresh()
        data = {"traces": [
            {"source": "A", "target": "B", "outcome": "success"},
            {"source": "B", "target": "C", "outcome": "failure"},
        ]}
        report = s.inject_json(json.dumps(data))
        assert report.inscriptions == 2
        assert report.edges_added == 2

    def test_trace_from_to_alias(self):
        L, s = fresh()
        data = {"traces": [{"from": "X", "to": "Y", "outcome": "success"}]}
        report = s.inject_json(json.dumps(data))
        assert ("X", "Y") in edge_set(L)
        assert report.inscriptions == 1

    def test_trace_bad_outcome_skipped(self):
        L, s = fresh()
        data = {"traces": [{"source": "A", "target": "B", "outcome": "??"}]}
        report = s.inject_json(json.dumps(data))
        assert report.skipped == 1

    def test_trace_self_loop_skipped(self):
        L, s = fresh()
        data = {"traces": [{"source": "A", "target": "A", "outcome": "success"}]}
        report = s.inject_json(json.dumps(data))
        assert report.skipped == 1


# ─────────────────────────────────────────────────────────────────────────────
# TestInjectJsonEdgeCases
# ─────────────────────────────────────────────────────────────────────────────

class TestInjectJsonEdgeCases:
    def test_invalid_json(self):
        L, s = fresh()
        report = s.inject_json("{not valid json}")
        assert report.skipped >= 1
        assert any("JSON" in w or "parse" in w.lower() for w in report.warnings)

    def test_json_array_root(self):
        L, s = fresh()
        report = s.inject_json("[1, 2, 3]")
        assert report.skipped >= 1

    def test_empty_edges_list(self):
        L, s = fresh()
        report = s.inject_json('{"edges": []}')
        assert report.edges_added == 0
        assert report.inscriptions == 0

    def test_missing_edges_key(self):
        L, s = fresh()
        report = s.inject_json('{"something": "else"}')
        assert len(report.warnings) > 0

    def test_non_dict_edge_entry_skipped(self):
        L, s = fresh()
        report = s.inject_json('{"edges": ["not_a_dict"]}')
        assert report.skipped == 1


# ─────────────────────────────────────────────────────────────────────────────
# TestInjectTextNoCaller
# ─────────────────────────────────────────────────────────────────────────────

class TestInjectTextNoCaller:
    def test_no_call_fn_returns_warning(self):
        L, s = fresh()
        report = s.inject_text("Some free text about logistics")
        assert report.edges_added == 0
        assert len(report.warnings) > 0
        assert "call_fn" in report.warnings[0]

    def test_no_changes_to_landscape(self):
        L, s = fresh()
        s.inject_text("Build a logistics landscape")
        assert len(L.edges) == 0


# ─────────────────────────────────────────────────────────────────────────────
# TestInjectAutoDetect
# ─────────────────────────────────────────────────────────────────────────────

class TestInjectAutoDetect:
    def test_hint_csv(self):
        L, s = fresh()
        report = s.inject("A,B,success", hint="csv")
        assert report.inscriptions == 1

    def test_hint_json(self):
        L, s = fresh()
        data = json.dumps({"edges": [{"from": "A", "to": "B", "outcome": "success"}]})
        report = s.inject(data, hint="json")
        assert report.inscriptions == 1

    def test_autodetect_json(self):
        L, s = fresh()
        data = json.dumps({"edges": [{"from": "X", "to": "Y"}]})
        report = s.inject(data)
        assert report.edges_added == 1

    def test_autodetect_csv(self):
        L, s = fresh()
        report = s.inject("A,B,success\nB,C,failure")
        assert report.inscriptions == 2

    def test_bytes_input(self):
        L, s = fresh()
        report = s.inject(b"A,B,success", hint="csv")
        assert report.inscriptions == 1

    def test_unsupported_type(self):
        L, s = fresh()
        report = s.inject(12345)
        assert report.skipped >= 1

    def test_hint_text_no_callfn(self):
        L, s = fresh()
        report = s.inject("some text", hint="text")
        # No call_fn → warning, no changes
        assert len(report.warnings) > 0
        assert report.edges_added == 0


# ─────────────────────────────────────────────────────────────────────────────
# TestIdempotency
# ─────────────────────────────────────────────────────────────────────────────

class TestIdempotency:
    def test_duplicate_csv_rows_no_new_edge(self):
        L, s = fresh()
        s.inject_csv("A,B,success")
        report2 = s.inject_csv("A,B,failure")
        # Edge already exists → edges_added = 0 on second call
        assert report2.edges_added == 0
        # But inscription still happens
        assert report2.inscriptions == 1

    def test_duplicate_json_edges_no_new_edge(self):
        L, s = fresh()
        data = {"edges": [{"from": "A", "to": "B"}]}
        s.inject_json(json.dumps(data))
        report2 = s.inject_json(json.dumps(data))
        assert report2.edges_added == 0

    def test_existing_edge_delta_preserved(self):
        """FileSensor must not overwrite delta/resistance of existing edges."""
        L = Landscape()
        L.add_edge("A", "B", delta=2.0, resistance=0.9)
        s = FileSensor(L)
        s.inject_csv("A,B,success")
        assert L._delta[Edge("A", "B")] == pytest.approx(2.0)
        assert L._R0[Edge("A", "B")] == pytest.approx(0.9)


# ─────────────────────────────────────────────────────────────────────────────
# TestHistorizationState
# ─────────────────────────────────────────────────────────────────────────────

class TestHistorizationState:
    def test_csv_success_u_increment(self):
        # Rho-decay: after 2 SUCCESSes U = rho + 1 = 0.9 + 1 = 1.9
        L, s = fresh()
        s.inject_csv("A,B,success\nA,B,success")
        assert hist_u(L, "A", "B") == pytest.approx(1.9)
        assert hist_f(L, "A", "B") == pytest.approx(0.0)

    def test_csv_failure_f_increment(self):
        L, s = fresh()
        s.inject_csv("A,B,failure\nA,B,failure")
        u = hist_u(L, "A", "B")
        f = hist_f(L, "A", "B")
        assert f > 0
        assert f > u  # failure-dominant

    def test_csv_partial_balanced(self):
        L, s = fresh()
        s.inject_csv("A,B\nA,B\nA,B\nA,B")  # 4 PARTIAL inscriptions
        u = hist_u(L, "A", "B")
        f = hist_f(L, "A", "B")
        assert u > 0
        assert f > 0

    def test_json_mixed_outcomes_accumulate(self):
        # 2 SUCCESS then FAILURE: U = rho*(rho+1) = 0.9*1.9 = 1.71
        L, s = fresh()
        data = {"edges": [
            {"from": "A", "to": "B", "outcome": "success"},
            {"from": "A", "to": "B", "outcome": "success"},
            {"from": "A", "to": "B", "outcome": "failure"},
        ]}
        s.inject_json(json.dumps(data))
        assert hist_u(L, "A", "B") == pytest.approx(1.71)

    def test_trace_list_u_accumulates(self):
        # 3 SUCCESSes: U = rho^2 + rho + 1 = 0.81 + 0.9 + 1 = 2.71
        L, s = fresh()
        data = {"traces": [
            {"source": "X", "target": "Y", "outcome": "success"},
            {"source": "X", "target": "Y", "outcome": "success"},
            {"source": "X", "target": "Y", "outcome": "success"},
        ]}
        s.inject_json(json.dumps(data))
        assert hist_u(L, "X", "Y") == pytest.approx(2.71)

    def test_quality_positive_after_success_bulk(self):
        """After 10 successes, trace_quality should be clearly positive."""
        L, s = fresh()
        csv_text = "\n".join(["A,B,success"] * 10)
        s.inject_csv(csv_text)
        q = L.historization.trace_quality(Edge("A", "B"))
        assert q > 0.5

    def test_quality_negative_after_failure_bulk(self):
        """After 10 failures, trace_quality should be clearly negative."""
        L, s = fresh()
        csv_text = "\n".join(["A,B,failure"] * 10)
        s.inject_csv(csv_text)
        q = L.historization.trace_quality(Edge("A", "B"))
        assert q < -0.5


# ─────────────────────────────────────────────────────────────────────────────
# TestLandscapeSummary
# ─────────────────────────────────────────────────────────────────────────────

class TestLandscapeSummary:
    def test_empty_landscape(self):
        L, s = fresh()
        summary = s.landscape_summary()
        assert summary["states"] == 0
        assert summary["edges"] == 0
        assert summary["total_inscriptions"] == 0

    def test_after_csv_injection(self):
        L, s = fresh()
        s.inject_csv("A,B,success\nB,C,failure\nC,D,partial")
        summary = s.landscape_summary()
        assert summary["edges"] == 3
        assert summary["states"] == 4
        # total_inscriptions sums U+F per edge (float, rho-decayed)
        assert summary["total_inscriptions"] > 0

    def test_topology_only_has_zero_inscriptions(self):
        L, s = fresh()
        spec = {"nodes": ["A", "B"], "edges": [{"from": "A", "to": "B"}]}
        s.inject_json(json.dumps(spec))
        summary = s.landscape_summary()
        assert summary["total_inscriptions"] == 0
        assert summary["edges"] == 1
