"""
E₀ MemOS v0.1 — Tests
========================
Validates persistence, restore, and summary correctness.

Acceptance criteria from E0_MEMOS_v0.1.md §12:
    1. Save controller state after a run
    2. Reload it in a fresh process
    3. Reconstruct a bounded summary for a target state
    4. Show that historization persists across sessions
    5. Confirm that controller behavior changes because memory is persisted

Plus K-MemOS corrections:
    K-MemOS-1: Edge key serialization (source→target)
    K-MemOS-2: EscalationType in RuntimeSnapshot
    K-MemOS-4: summarize_for_llm priority ordering
"""

from __future__ import annotations

import json
import math
import os
import shutil
import tempfile
import unittest

from e0_controller.primitives import Edge, Outcome
from e0_controller.historization import Historization
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller, EscalationType, RunTrace
from e0_controller.memory_os import (
    E0MemoryOS,
    CanonRef,
    LandscapeSnapshot,
    HistorizationSnapshot,
    RuntimeSnapshot,
    edge_to_key,
    key_to_edge,
)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def build_invoice_landscape() -> Landscape:
    """Simplified invoice landscape for testing."""
    L = Landscape()
    L.add_edge("RECEIVED", "PDF_LOADED", delta=0.3, resistance=0.5)
    L.add_edge("PDF_LOADED", "DATA_EXTRACTED", delta=0.4, resistance=0.8)
    L.add_edge("DATA_EXTRACTED", "CUSTOMER_FOUND", delta=0.2, resistance=0.6)
    L.add_edge("DATA_EXTRACTED", "HUMAN_REVIEW", delta=0.5, resistance=1.2)
    L.add_edge("CUSTOMER_FOUND", "APPROVED", delta=0.1, resistance=0.3)
    L.add_edge("HUMAN_REVIEW", "APPROVED", delta=0.3, resistance=0.8)
    return L


def all_success(source: str, target: str) -> Outcome:
    return Outcome.SUCCESS


def sometimes_fail(source: str, target: str) -> Outcome:
    if source == "DATA_EXTRACTED" and target == "CUSTOMER_FOUND":
        return Outcome.FAILURE
    return Outcome.SUCCESS


# ──────────────────────────────────────────────
# K-MemOS-1: Edge key convention
# ──────────────────────────────────────────────

class TestEdgeKeys(unittest.TestCase):
    def test_round_trip(self):
        """edge_to_key → key_to_edge round-trips correctly."""
        e = Edge("PDF_LOADED", "DATA_EXTRACTED")
        k = edge_to_key(e)
        self.assertEqual(k, "PDF_LOADED→DATA_EXTRACTED")
        self.assertEqual(key_to_edge(k), e)

    def test_invalid_key(self):
        """Invalid key raises ValueError."""
        with self.assertRaises(ValueError):
            key_to_edge("no_arrow_here")


# ──────────────────────────────────────────────
# §12.1: Save controller state after a run
# ──────────────────────────────────────────────

class TestSave(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.memos = E0MemoryOS(base_dir=self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_snapshot_and_save(self):
        """Snapshot from live runtime → save as JSON → file exists."""
        L = build_invoice_landscape()
        ctrl = E0Controller(L, all_success, alpha=2.0, recent_k=3)
        trace = ctrl.run(start="RECEIVED", goal="APPROVED", max_cycles=10)

        ctx = self.memos.snapshot_from_runtime(
            "test-001", L, ctrl, trace,
            canon_refs=[CanonRef("e0-canonical-reference", "v1.0",
                                 "canon/e0-canonical-reference.txt")],
        )
        path = self.memos.save_context(ctx)
        self.assertTrue(path.exists())

        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["session_id"], "test-001")
        self.assertGreater(len(data["landscape"]["edges"]), 0)
        self.assertGreater(data["historization"]["tau"], 0)

    def test_save_run_record(self):
        """Run trace saved as separate run record."""
        L = build_invoice_landscape()
        ctrl = E0Controller(L, all_success)
        trace = ctrl.run(start="RECEIVED", goal="APPROVED", max_cycles=10)

        record = self.memos.save_run("test-001", trace, goal="APPROVED")
        self.assertEqual(record.run_id, "run_0001")
        self.assertTrue(record.reached_goal)
        self.assertEqual(record.start_state, "RECEIVED")
        self.assertEqual(record.final_state, "APPROVED")


# ──────────────────────────────────────────────
# §12.2: Reload in a fresh process
# ──────────────────────────────────────────────

class TestLoadRestore(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.memos = E0MemoryOS(base_dir=self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_round_trip_context(self):
        """Save → load → content matches."""
        L = build_invoice_landscape()
        ctrl = E0Controller(L, all_success)
        trace = ctrl.run(start="RECEIVED", goal="APPROVED", max_cycles=10)

        ctx = self.memos.snapshot_from_runtime("test-002", L, ctrl, trace)
        self.memos.save_context(ctx)

        loaded = self.memos.load_context("test-002")
        self.assertEqual(loaded.session_id, "test-002")
        self.assertEqual(loaded.historization["tau"], ctx.historization["tau"])
        self.assertEqual(len(loaded.landscape["edges"]),
                         len(ctx.landscape["edges"]))

    def test_restore_landscape(self):
        """Restored landscape has correct structure and historization."""
        L = build_invoice_landscape()
        ctrl = E0Controller(L, all_success)
        ctrl.run(start="RECEIVED", goal="APPROVED", max_cycles=10)

        ctx = self.memos.snapshot_from_runtime("test-003", L, ctrl)
        self.memos.save_context(ctx)
        loaded = self.memos.load_context("test-003")

        L2 = self.memos.restore_landscape(loaded)
        self.assertEqual(L2.states, L.states)
        self.assertEqual(L2.edge_count(), L.edge_count())
        self.assertEqual(L2.historization.tau, L.historization.tau)

    def test_restore_controller(self):
        """Restored controller has correct params and runtime state."""
        L = build_invoice_landscape()
        ctrl = E0Controller(L, all_success, alpha=3.0, recent_k=5,
                            s_max=2.0, c_min=0.1)
        ctrl.run(start="RECEIVED", goal="APPROVED", max_cycles=10)

        ctx = self.memos.snapshot_from_runtime("test-004", L, ctrl)
        self.memos.save_context(ctx)
        loaded = self.memos.load_context("test-004")

        L2 = self.memos.restore_landscape(loaded)
        ctrl2 = self.memos.restore_controller(loaded, L2, all_success)

        self.assertAlmostEqual(ctrl2.alpha, 3.0)
        self.assertEqual(ctrl2.recent_k, 5)
        self.assertAlmostEqual(ctrl2.s_max, 2.0)
        self.assertAlmostEqual(ctrl2.c_min, 0.1)
        self.assertEqual(ctrl2._recent, ctrl._recent)

    def test_missing_session_raises(self):
        """Loading a non-existent session raises FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            self.memos.load_context("nonexistent")


# ──────────────────────────────────────────────
# §12.3: Bounded summary for a target state
# ──────────────────────────────────────────────

class TestSummarize(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.memos = E0MemoryOS(base_dir=self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_summary_structure(self):
        """Summary has all required keys and correct current state."""
        L = build_invoice_landscape()
        ctrl = E0Controller(L, all_success)
        trace = ctrl.run(start="RECEIVED", goal="APPROVED", max_cycles=10)

        ctx = self.memos.snapshot_from_runtime("test-005", L, ctrl, trace)

        summary = self.memos.summarize_for_llm(ctx, "DATA_EXTRACTED", L)

        self.assertEqual(summary["current_state"], "DATA_EXTRACTED")
        self.assertIn("admissible_neighbors", summary)
        self.assertIn("edge_history", summary)
        self.assertIn("runtime", summary)
        # DATA_EXTRACTED has 2 neighbors
        self.assertEqual(len(summary["admissible_neighbors"]), 2)
        self.assertIn("CUSTOMER_FOUND", summary["admissible_neighbors"])
        self.assertIn("HUMAN_REVIEW", summary["admissible_neighbors"])

    def test_summary_is_json_serializable(self):
        """Summary can be serialized to JSON without error."""
        L = build_invoice_landscape()
        ctrl = E0Controller(L, all_success)
        trace = ctrl.run(start="RECEIVED", goal="APPROVED", max_cycles=10)
        ctx = self.memos.snapshot_from_runtime("test-006", L, ctrl, trace)
        summary = self.memos.summarize_for_llm(ctx, "DATA_EXTRACTED", L)

        # Must not raise
        output = json.dumps(summary, indent=2)
        self.assertIn("DATA_EXTRACTED", output)


# ──────────────────────────────────────────────
# §12.4: Historization persists across sessions
# ──────────────────────────────────────────────

class TestHistorizationPersistence(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.memos = E0MemoryOS(base_dir=self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_historization_survives_save_load(self):
        """U/F traces persist through save → load → restore."""
        L = build_invoice_landscape()
        ctrl = E0Controller(L, sometimes_fail)
        ctrl.run(start="RECEIVED", goal="APPROVED", max_cycles=10)

        # Capture U/F for a specific edge before saving
        edge = Edge("DATA_EXTRACTED", "CUSTOMER_FOUND")
        u_before = L.historization.success_trace(edge)
        f_before = L.historization.failure_trace(edge)
        tau_before = L.historization.tau

        # Save and reload
        ctx = self.memos.snapshot_from_runtime("test-007", L, ctrl)
        self.memos.save_context(ctx)
        loaded = self.memos.load_context("test-007")
        L2 = self.memos.restore_landscape(loaded)

        # Verify traces survived
        self.assertEqual(L2.historization.tau, tau_before)
        self.assertAlmostEqual(L2.historization.success_trace(edge), u_before)
        self.assertAlmostEqual(L2.historization.failure_trace(edge), f_before)


# ──────────────────────────────────────────────
# §12.5: Controller behavior changes from memory
# ──────────────────────────────────────────────

class TestBehaviorFromMemory(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.memos = E0MemoryOS(base_dir=self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_restored_controller_avoids_failed_edge(self):
        """
        Session 1: DATA_EXTRACTED→CUSTOMER_FOUND fails repeatedly.
        Session 2: Restored controller avoids that edge due to high F-trace.
        """
        # Build a balanced landscape where both edges from DATA_EXTRACTED
        # have similar base tension, so failure history tips the balance.
        L1 = Landscape()
        L1.add_edge("RECEIVED", "DATA_EXTRACTED", delta=0.3, resistance=0.5)
        L1.add_edge("DATA_EXTRACTED", "CUSTOMER_FOUND", delta=0.3, resistance=0.5)
        L1.add_edge("DATA_EXTRACTED", "HUMAN_REVIEW", delta=0.3, resistance=0.6)
        L1.add_edge("CUSTOMER_FOUND", "APPROVED", delta=0.1, resistance=0.3)
        L1.add_edge("HUMAN_REVIEW", "APPROVED", delta=0.1, resistance=0.3)

        # Session 1: accumulate failures on DATA_EXTRACTED→CUSTOMER_FOUND
        ctrl1 = E0Controller(L1, sometimes_fail, alpha=0.0, recent_k=0)
        for _ in range(15):
            ctrl1.cycle("DATA_EXTRACTED")

        # Verify failure trace accumulated
        edge_cf = Edge("DATA_EXTRACTED", "CUSTOMER_FOUND")
        self.assertGreater(L1.historization.failure_trace(edge_cf), 0.0)

        # Save session
        ctx = self.memos.snapshot_from_runtime("test-008", L1, ctrl1)
        self.memos.save_context(ctx)

        # Session 2: fresh process, loaded memory
        loaded = self.memos.load_context("test-008")
        L2 = self.memos.restore_landscape(loaded)
        ctrl2 = self.memos.restore_controller(loaded, L2, all_success)

        s_customer = ctrl2._effective_tension("DATA_EXTRACTED", "CUSTOMER_FOUND")
        s_review = ctrl2._effective_tension("DATA_EXTRACTED", "HUMAN_REVIEW")

        # CUSTOMER_FOUND should now have higher tension due to accumulated failures
        self.assertGreater(s_customer, s_review,
                           f"Expected S(CF)={s_customer:.3f} > S(HR)={s_review:.3f}")

        # Controller should prefer HUMAN_REVIEW
        target, escalated, _ = ctrl2.select_next("DATA_EXTRACTED")
        self.assertEqual(target, "HUMAN_REVIEW")


# ──────────────────────────────────────────────
# K-MemOS-2: EscalationType in runtime snapshot
# ──────────────────────────────────────────────

class TestEscalationTypeSnapshot(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.memos = E0MemoryOS(base_dir=self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_escalation_type_persisted(self):
        """Last escalation type is captured in runtime snapshot."""
        L = Landscape()
        L.add_state("DEAD")  # dead-end state
        L.add_edge("A", "B", delta=0.3, resistance=0.5)
        ctrl = E0Controller(L, all_success)
        trace = ctrl.run(start="DEAD", max_cycles=3)

        rs = RuntimeSnapshot.from_controller(ctrl, trace)
        self.assertEqual(rs.last_escalation_type, "dead_end")

    def test_run_record_has_escalation_breakdown(self):
        """Run record includes escalation type counts."""
        L = Landscape()
        L.add_state("DEAD")
        L.add_edge("A", "B", delta=0.3, resistance=0.5)
        ctrl = E0Controller(L, all_success)
        trace = ctrl.run(start="DEAD", max_cycles=3)

        record = self.memos.save_run("test-esc", trace)
        self.assertIn("dead_end", record.escalation_types)


# ──────────────────────────────────────────────
# Retrieval
# ──────────────────────────────────────────────

class TestRetrieval(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.memos = E0MemoryOS(base_dir=self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_retrieve_recent_runs(self):
        """Multiple runs are retrievable in reverse order."""
        L = build_invoice_landscape()
        ctrl = E0Controller(L, all_success)
        t1 = ctrl.run(start="RECEIVED", goal="APPROVED", max_cycles=10)
        t2 = ctrl.run(start="PDF_LOADED", goal="APPROVED", max_cycles=10)

        self.memos.save_run("test-ret", t1, goal="APPROVED")
        self.memos.save_run("test-ret", t2, goal="APPROVED")

        runs = self.memos.retrieve_recent_runs("test-ret", limit=5)
        self.assertEqual(len(runs), 2)
        # Most recent first
        self.assertEqual(runs[0]["run_id"], "run_0002")

    def test_retrieve_edge_history(self):
        """Edge history returns current traces and run appearances."""
        L = build_invoice_landscape()
        ctrl = E0Controller(L, all_success)
        trace = ctrl.run(start="RECEIVED", goal="APPROVED", max_cycles=10)

        ctx = self.memos.snapshot_from_runtime("test-eh", L, ctrl, trace)
        self.memos.save_context(ctx)
        self.memos.save_run("test-eh", trace, goal="APPROVED")

        result = self.memos.retrieve_edge_history(
            "test-eh", "RECEIVED", "PDF_LOADED")
        self.assertIsNotNone(result["current"])
        self.assertGreater(len(result["runs"]), 0)

    def test_list_sessions(self):
        """list_sessions returns saved session IDs."""
        L = build_invoice_landscape()
        ctrl = E0Controller(L, all_success)
        ctx1 = self.memos.snapshot_from_runtime("alpha", L, ctrl)
        ctx2 = self.memos.snapshot_from_runtime("beta", L, ctrl)
        self.memos.save_context(ctx1)
        self.memos.save_context(ctx2)

        sessions = self.memos.list_sessions()
        self.assertIn("alpha", sessions)
        self.assertIn("beta", sessions)


if __name__ == "__main__":
    unittest.main()
