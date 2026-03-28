"""Tests for ProvenanceLog — full evidence chain recording.

Validates:
- Stage recording (input, LLM call, proposal, landscape, run, evaluation)
- LLM call wrapping (transparent interception)
- Serialization round-trip (save/load JSON)
- Chain completeness checking
- Integration with E0LLMAdapter (provenance parameter)
- Integration with Session (provenance parameter)
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import tempfile
import unittest

from e0_controller import (
    E0Controller,
    E0LLMAdapter,
    HybridMode,
    Landscape,
    LandscapeProposal,
    LLMConfig,
    Outcome,
    ProvenanceLog,
    Session,
    materialize_landscape,
)
from e0_controller.provenance import (
    EvaluationRecord,
    InputRecord,
    LandscapeRecord,
    LLMCallRecord,
    ProposalRecord,
    RunRecord,
)


# ── Helpers ──────────────────────────────────────────────────────────────

def _mock_call_fn(system: str, user: str, config: LLMConfig) -> str:
    """Simple mock LLM that returns a minimal landscape."""
    return json.dumps({
        "states": ["START", "MIDDLE", "GOAL"],
        "edges": [
            {"source": "START", "target": "MIDDLE",
             "delta": 0.5, "resistance": 0.3, "description": "step 1"},
            {"source": "MIDDLE", "target": "GOAL",
             "delta": 0.6, "resistance": 0.2, "description": "step 2"},
            {"source": "START", "target": "GOAL",
             "delta": 0.9, "resistance": 0.8, "description": "shortcut"},
        ],
    })


def _build_simple_landscape() -> Landscape:
    """Build a minimal landscape for testing."""
    proposal = LandscapeProposal(
        states=["START", "MIDDLE", "GOAL"],
        edges=[
            {"source": "START", "target": "MIDDLE",
             "delta": 0.5, "resistance": 0.3, "description": "step 1"},
            {"source": "MIDDLE", "target": "GOAL",
             "delta": 0.6, "resistance": 0.2, "description": "step 2"},
            {"source": "START", "target": "GOAL",
             "delta": 0.9, "resistance": 0.8, "description": "shortcut"},
        ],
    )
    return materialize_landscape(proposal)


def _always_success(source: str, target: str) -> Outcome:
    return Outcome.SUCCESS


# ══════════════════════════════════════════════════════════════════════════
# 1. Stage Recording
# ══════════════════════════════════════════════════════════════════════════

class TestInputRecord(unittest.TestCase):
    """P1: Input text recording with SHA-256 fingerprint."""

    def test_record_input(self):
        log = ProvenanceLog(source_id="test")
        log.record_input("Hello World")
        self.assertIsNotNone(log.input)
        self.assertEqual(log.input.text, "Hello World")
        self.assertEqual(log.input.source_id, "test")

    def test_sha256_computed(self):
        log = ProvenanceLog()
        log.record_input("Hello World")
        expected = hashlib.sha256(b"Hello World").hexdigest()
        self.assertEqual(log.input.sha256, expected)

    def test_timestamp_set(self):
        log = ProvenanceLog()
        log.record_input("text")
        self.assertTrue(len(log.input.timestamp) > 0)

    def test_source_id_propagated(self):
        log = ProvenanceLog()
        log.record_input("text", source_id="ibuprofen")
        self.assertEqual(log.source_id, "ibuprofen")


class TestLLMCallRecord(unittest.TestCase):
    """P2: LLM call wrapping records prompt, response, model, timing."""

    def test_wrap_records_call(self):
        log = ProvenanceLog()
        wrapped = log.wrap_call_fn(_mock_call_fn)
        result = wrapped("system", "user", LLMConfig())
        self.assertEqual(len(log.llm_calls), 1)
        call = log.llm_calls[0]
        self.assertEqual(call.system_prompt, "system")
        self.assertEqual(call.user_prompt, "user")
        self.assertIn("states", call.raw_response)
        self.assertEqual(call.model, "gpt-5.4-mini")

    def test_wrap_returns_original_response(self):
        log = ProvenanceLog()
        wrapped = log.wrap_call_fn(_mock_call_fn)
        result = wrapped("sys", "usr", LLMConfig())
        direct = _mock_call_fn("sys", "usr", LLMConfig())
        self.assertEqual(result, direct)

    def test_duration_recorded(self):
        log = ProvenanceLog()
        wrapped = log.wrap_call_fn(_mock_call_fn)
        wrapped("s", "u", LLMConfig())
        self.assertIsNotNone(log.llm_calls[0].duration_ms)
        self.assertGreaterEqual(log.llm_calls[0].duration_ms, 0)

    def test_multiple_calls_accumulated(self):
        log = ProvenanceLog()
        wrapped = log.wrap_call_fn(_mock_call_fn)
        wrapped("s1", "u1", LLMConfig())
        wrapped("s2", "u2", LLMConfig())
        self.assertEqual(len(log.llm_calls), 2)


class TestProposalRecord(unittest.TestCase):
    """P3: Landscape proposal recording."""

    def test_record_proposal(self):
        log = ProvenanceLog()
        proposal = LandscapeProposal(
            states=["A", "B", "C"],
            edges=[{"source": "A", "target": "B", "delta": 0.5, "resistance": 0.3}],
        )
        log.record_proposal(proposal)
        self.assertIsNotNone(log.proposal)
        self.assertEqual(log.proposal.state_count, 3)
        self.assertEqual(log.proposal.edge_count, 1)
        self.assertEqual(log.proposal.states, ["A", "B", "C"])


class TestLandscapeRecord(unittest.TestCase):
    """P4: Materialized landscape metrics recording."""

    def test_record_landscape(self):
        log = ProvenanceLog()
        L = _build_simple_landscape()
        log.record_landscape(L, "START", "GOAL")
        self.assertIsNotNone(log.landscape)
        self.assertEqual(log.landscape.state_count, 3)
        self.assertEqual(log.landscape.start, "START")
        self.assertEqual(log.landscape.goal, "GOAL")
        self.assertTrue(log.landscape.goal_reachable)

    def test_s_eff_values_recorded(self):
        log = ProvenanceLog()
        L = _build_simple_landscape()
        log.record_landscape(L, "START", "GOAL")
        self.assertIn("START→MIDDLE", log.landscape.s_eff_values)
        self.assertIn("MIDDLE→GOAL", log.landscape.s_eff_values)
        # S_eff should be positive
        for v in log.landscape.s_eff_values.values():
            self.assertGreater(v, 0)


class TestRunRecord(unittest.TestCase):
    """P5: Controller run recording."""

    def test_record_run(self):
        log = ProvenanceLog()
        L = _build_simple_landscape()
        ctrl = E0Controller(L, _always_success)
        trace = ctrl.run("START", goal="GOAL", max_cycles=10)
        log.record_run(trace, {"goal": "GOAL", "hybrid_mode": "greedy"})
        self.assertEqual(len(log.runs), 1)
        self.assertIn("START", log.runs[0].path)
        self.assertTrue(log.runs[0].goal_reached)

    def test_multiple_runs(self):
        log = ProvenanceLog()
        L = _build_simple_landscape()
        ctrl = E0Controller(L, _always_success)
        t1 = ctrl.run("START", goal="GOAL", max_cycles=10)
        t2 = ctrl.run("START", goal="GOAL", max_cycles=10)
        log.record_run(t1, {"goal": "GOAL"})
        log.record_run(t2, {"goal": "GOAL"})
        self.assertEqual(len(log.runs), 2)


class TestEvaluationRecord(unittest.TestCase):
    """P6: Evaluation recording."""

    def test_record_evaluation(self):
        log = ProvenanceLog()
        log.record_evaluation({"goal_reached": True, "trap_detected": False})
        self.assertIsNotNone(log.evaluation)
        self.assertTrue(log.evaluation.findings["goal_reached"])


# ══════════════════════════════════════════════════════════════════════════
# 2. Serialization
# ══════════════════════════════════════════════════════════════════════════

class TestSerialization(unittest.TestCase):
    """P7: JSON round-trip for complete provenance log."""

    def _build_full_log(self) -> ProvenanceLog:
        log = ProvenanceLog(source_id="test-roundtrip")
        log.record_input("Test input text", source_id="test-roundtrip")

        wrapped = log.wrap_call_fn(_mock_call_fn)
        wrapped("sys", "usr", LLMConfig())

        proposal = LandscapeProposal(
            states=["A", "B"],
            edges=[{"source": "A", "target": "B", "delta": 0.5, "resistance": 0.3}],
        )
        log.record_proposal(proposal)

        L = _build_simple_landscape()
        log.record_landscape(L, "START", "GOAL")

        ctrl = E0Controller(L, _always_success)
        trace = ctrl.run("START", goal="GOAL", max_cycles=10)
        log.record_run(trace, {"goal": "GOAL"})

        log.record_evaluation({"goal_reached": True})
        log.metadata = {"framework_version": "0.5.0"}
        return log

    def test_to_dict_and_back(self):
        log = self._build_full_log()
        d = log.to_dict()
        restored = ProvenanceLog.from_dict(d)
        self.assertEqual(restored.source_id, "test-roundtrip")
        self.assertEqual(restored.input.text, "Test input text")
        self.assertEqual(len(restored.llm_calls), 1)
        self.assertEqual(restored.proposal.state_count, 2)
        self.assertTrue(restored.landscape.goal_reachable)
        self.assertEqual(len(restored.runs), 1)
        self.assertTrue(restored.evaluation.findings["goal_reached"])

    def test_save_and_load(self):
        log = self._build_full_log()
        tmpdir = tempfile.mkdtemp()
        try:
            path = os.path.join(tmpdir, "provenance", "test.json")
            log.save(path)
            self.assertTrue(os.path.exists(path))
            restored = ProvenanceLog.load(path)
            self.assertEqual(restored.source_id, log.source_id)
            self.assertEqual(restored.input.sha256, log.input.sha256)
            self.assertEqual(len(restored.runs), len(log.runs))
        finally:
            shutil.rmtree(tmpdir)

    def test_json_is_valid(self):
        log = self._build_full_log()
        d = log.to_dict()
        text = json.dumps(d, ensure_ascii=False)
        parsed = json.loads(text)
        self.assertIn("source_id", parsed)
        self.assertIn("llm_calls", parsed)


# ══════════════════════════════════════════════════════════════════════════
# 3. Chain Completeness
# ══════════════════════════════════════════════════════════════════════════

class TestChainCompleteness(unittest.TestCase):
    """P8: Chain completeness validation."""

    def test_empty_log_not_complete(self):
        log = ProvenanceLog()
        self.assertFalse(log.chain_complete())

    def test_full_log_complete(self):
        log = ProvenanceLog(source_id="full")
        log.record_input("text")

        wrapped = log.wrap_call_fn(_mock_call_fn)
        wrapped("s", "u", LLMConfig())

        log.record_proposal(LandscapeProposal(states=["A"], edges=[]))

        L = _build_simple_landscape()
        log.record_landscape(L, "START", "GOAL")

        ctrl = E0Controller(L, _always_success)
        trace = ctrl.run("START", goal="GOAL")
        log.record_run(trace, {"goal": "GOAL"})

        log.record_evaluation({"ok": True})
        self.assertTrue(log.chain_complete())

    def test_chain_summary_missing(self):
        log = ProvenanceLog(source_id="partial")
        log.record_input("text")
        summary = log.chain_summary()
        self.assertIn("1/6", summary)
        self.assertIn("missing", summary)

    def test_chain_summary_complete(self):
        log = ProvenanceLog(source_id="full")
        log.record_input("t")
        log.llm_calls.append(LLMCallRecord("s", "u", "r", "m", 0.2))
        log.proposal = ProposalRecord(["A"], [])
        log.landscape = LandscapeRecord(1, 0, "A", "A", {}, True)
        log.runs.append(RunRecord(["A"], 0, True, 0.0, 0, {}))
        log.record_evaluation({})
        self.assertIn("6/6", log.chain_summary())


# ══════════════════════════════════════════════════════════════════════════
# 4. E0LLMAdapter Integration
# ══════════════════════════════════════════════════════════════════════════

class TestAdapterProvenance(unittest.TestCase):
    """P9: ProvenanceLog integration with E0LLMAdapter."""

    def test_adapter_records_call(self):
        """Adapter with provenance logs every LLM call."""
        log = ProvenanceLog(source_id="adapter-test")
        adapter = E0LLMAdapter(call_fn=_mock_call_fn, provenance=log)
        proposal = adapter.build_landscape("task", "START", "GOAL")
        self.assertEqual(len(log.llm_calls), 1)
        self.assertIn("START", log.llm_calls[0].user_prompt)

    def test_adapter_records_proposal(self):
        """Adapter with provenance auto-records the proposal."""
        log = ProvenanceLog(source_id="adapter-test")
        adapter = E0LLMAdapter(call_fn=_mock_call_fn, provenance=log)
        proposal = adapter.build_landscape("task", "START", "GOAL")
        self.assertIsNotNone(log.proposal)
        self.assertEqual(log.proposal.state_count, 3)

    def test_adapter_without_provenance_unchanged(self):
        """Adapter without provenance works normally."""
        adapter = E0LLMAdapter(call_fn=_mock_call_fn)
        proposal = adapter.build_landscape("task", "START", "GOAL")
        self.assertEqual(len(proposal.states), 3)


# ══════════════════════════════════════════════════════════════════════════
# 5. Session Integration
# ══════════════════════════════════════════════════════════════════════════

class TestSessionProvenance(unittest.TestCase):
    """P10: ProvenanceLog integration with Session."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_session_records_run(self):
        """Session with provenance records the controller run."""
        log = ProvenanceLog(source_id="session-test")
        L = _build_simple_landscape()
        s = Session(
            "prov-test", L, _always_success,
            base_dir=self.tmpdir,
            provenance=log,
        )
        result = s.run("START", goal="GOAL", max_cycles=10)
        self.assertEqual(len(log.runs), 1)
        self.assertTrue(log.runs[0].goal_reached)
        self.assertEqual(log.runs[0].controller_config["hybrid_mode"], "greedy")
        self.assertEqual(log.runs[0].controller_config["hybrid_geometry"], "simple")

    def test_session_without_provenance_unchanged(self):
        """Session without provenance works normally."""
        L = _build_simple_landscape()
        s = Session("no-prov", L, _always_success, base_dir=self.tmpdir)
        result = s.run("START", goal="GOAL", max_cycles=10)
        self.assertIn("GOAL", result.trace.path)


# ══════════════════════════════════════════════════════════════════════════
# 6. End-to-End Pipeline with Mock
# ══════════════════════════════════════════════════════════════════════════

class TestEndToEndProvenance(unittest.TestCase):
    """P11: Full pipeline provenance with mock LLM."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_complete_pipeline(self):
        """Full pipeline: input → LLM → proposal → landscape → run → eval."""
        log = ProvenanceLog(source_id="e2e-mock")

        # 1. Input
        text = "Simple task with three states."
        log.record_input(text, source_id="e2e-mock")

        # 2. LLM → Proposal (via adapter integration)
        adapter = E0LLMAdapter(call_fn=_mock_call_fn, provenance=log)
        proposal = adapter.build_landscape(text, "START", "GOAL")

        # 3. Landscape
        L = materialize_landscape(proposal)
        log.record_landscape(L, "START", "GOAL")

        # 4. Run (via session integration)
        session = Session(
            "e2e", L, _always_success,
            base_dir=self.tmpdir,
            controller_kwargs={
                "hybrid_mode": HybridMode.AMPLITUDE_ON_DISAGREE,
                "hybrid_geometry": "goal_reaching",
                "hybrid_horizon": 4,
                "hybrid_goals": {"GOAL"},
            },
            provenance=log,
        )
        result = session.run("START", goal="GOAL", max_cycles=10)

        # 5. Evaluation
        log.record_evaluation({
            "goal_reached": "GOAL" in result.trace.path,
            "steps": len(result.trace.steps),
        })

        # Chain should be complete
        self.assertTrue(log.chain_complete())
        self.assertIn("6/6", log.chain_summary())

        # Save and verify
        path = os.path.join(self.tmpdir, "provenance.json")
        log.save(path)
        restored = ProvenanceLog.load(path)
        self.assertTrue(restored.chain_complete())
        self.assertEqual(restored.input.text, text)
        self.assertEqual(len(restored.llm_calls), 1)
        self.assertEqual(restored.proposal.state_count, 3)
        self.assertTrue(restored.landscape.goal_reachable)
        self.assertTrue(restored.runs[0].goal_reached)

    def test_geometry_comparison_recorded(self):
        """Two runs with different geometries, both in provenance."""
        log = ProvenanceLog(source_id="geometry-compare")
        log.record_input("comparison test")

        wrapped = log.wrap_call_fn(_mock_call_fn)
        wrapped("sys", "usr", LLMConfig())
        log.record_proposal(LandscapeProposal(
            states=["START", "MIDDLE", "GOAL"],
            edges=[{"source": "START", "target": "MIDDLE", "delta": 0.5, "resistance": 0.3}],
        ))

        L = _build_simple_landscape()
        log.record_landscape(L, "START", "GOAL")

        # Run 1: goal_reaching
        ctrl1 = E0Controller(
            L, _always_success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_geometry="goal_reaching",
            hybrid_goals={"GOAL"},
        )
        t1 = ctrl1.run("START", goal="GOAL", max_cycles=10)
        log.record_run(t1, {
            "goal": "GOAL",
            "hybrid_geometry": "goal_reaching",
            "hybrid_mode": "amplitude_on_disagree",
        })

        # Run 2: simple
        ctrl2 = E0Controller(
            L, _always_success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_geometry="simple",
            hybrid_goals={"GOAL"},
        )
        t2 = ctrl2.run("START", goal="GOAL", max_cycles=10)
        log.record_run(t2, {
            "goal": "GOAL",
            "hybrid_geometry": "simple",
            "hybrid_mode": "amplitude_on_disagree",
        })

        self.assertEqual(len(log.runs), 2)
        self.assertEqual(log.runs[0].controller_config["hybrid_geometry"], "goal_reaching")
        self.assertEqual(log.runs[1].controller_config["hybrid_geometry"], "simple")


if __name__ == "__main__":
    unittest.main()
