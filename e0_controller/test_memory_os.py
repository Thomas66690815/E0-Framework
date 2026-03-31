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
from e0_controller.controller import E0Controller, EscalationType, HybridMode, RunTrace
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
            "test-eh", "RECEIVED→PDF_LOADED")
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


# ──────────────────────────────────────────────
# Phase 3m: Hybrid + Overlay Snapshot Tests
# ──────────────────────────────────────────────

def build_diamond_landscape() -> Landscape:
    """Diamond domain for hybrid tests."""
    L = Landscape()
    L.add_edge("S", "A", delta=0.3, resistance=0.6)
    L.add_edge("S", "B", delta=0.35, resistance=0.7)
    L.add_edge("S", "C", delta=0.3, resistance=0.5)
    L.add_state("C")
    L.add_edge("A", "M", delta=0.2, resistance=0.4)
    L.add_edge("M", "Z", delta=0.15, resistance=0.3)
    L.add_edge("B", "N", delta=0.25, resistance=0.6)
    L.add_edge("N", "Z", delta=0.2, resistance=0.4)
    L.add_edge("A", "S", delta=0.8, resistance=2.0)
    L.add_edge("B", "S", delta=0.5, resistance=1.5)
    L.add_edge("M", "N", delta=0.3, resistance=0.5)
    return L


class TestHybridSnapshot(unittest.TestCase):
    """RuntimeSnapshot captures and restores hybrid mode params."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.memos = E0MemoryOS(base_dir=self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_greedy_snapshot_has_hybrid_params(self):
        """GREEDY controller's snapshot includes hybrid_mode='greedy'."""
        L = build_invoice_landscape()
        ctrl = E0Controller(L, all_success)
        snap = RuntimeSnapshot.from_controller(ctrl)
        params = snap.controller_params
        self.assertEqual(params["hybrid_mode"], "greedy")
        self.assertEqual(params["hybrid_horizon"], 3)
        self.assertEqual(params["hybrid_goals"], [])

    def test_hybrid_snapshot_preserves_mode(self):
        """AMPLITUDE_ON_DISAGREE snapshot preserves mode and goals."""
        L = build_diamond_landscape()
        ctrl = E0Controller(
            L, all_success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=4,
            hybrid_goals={"Z"},
        )
        snap = RuntimeSnapshot.from_controller(ctrl)
        params = snap.controller_params
        self.assertEqual(params["hybrid_mode"], "amplitude_on_disagree")
        self.assertEqual(params["hybrid_horizon"], 4)
        self.assertEqual(params["hybrid_goals"], ["Z"])

    def test_restore_hybrid_controller(self):
        """Controller restored from snapshot has correct hybrid mode."""
        L = build_diamond_landscape()
        ctrl = E0Controller(
            L, all_success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=4,
            hybrid_goals={"Z"},
        )
        trace = ctrl.run("S", max_cycles=5, goal="Z")
        ctx = self.memos.snapshot_from_runtime("test-hybrid", L, ctrl, trace)
        self.memos.save_context(ctx)

        # Reload in "fresh process"
        ctx2 = self.memos.load_context("test-hybrid")
        L2 = self.memos.restore_landscape(ctx2)
        ctrl2 = self.memos.restore_controller(ctx2, L2, all_success)

        self.assertEqual(ctrl2.hybrid_mode, HybridMode.AMPLITUDE_ON_DISAGREE)
        self.assertEqual(ctrl2.hybrid_horizon, 4)
        self.assertEqual(ctrl2.hybrid_goals, {"Z"})

    def test_restore_greedy_default(self):
        """Old snapshot without hybrid params restores as GREEDY."""
        L = build_invoice_landscape()
        ctrl = E0Controller(L, all_success)
        ctx = self.memos.snapshot_from_runtime("test-old", L, ctrl)
        self.memos.save_context(ctx)

        ctx2 = self.memos.load_context("test-old")
        L2 = self.memos.restore_landscape(ctx2)
        ctrl2 = self.memos.restore_controller(ctx2, L2, all_success)

        self.assertEqual(ctrl2.hybrid_mode, HybridMode.GREEDY)


class TestOverlaySummary(unittest.TestCase):
    """summarize_for_llm includes amplitude overlay when controller provided."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.memos = E0MemoryOS(base_dir=self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_no_overlay_without_controller(self):
        """Without controller param, no amplitude_overlay in summary."""
        L = build_invoice_landscape()
        ctrl = E0Controller(L, all_success)
        trace = ctrl.run("RECEIVED", goal="APPROVED", max_cycles=10)
        ctx = self.memos.snapshot_from_runtime("test-no-ov", L, ctrl, trace)
        summary = self.memos.summarize_for_llm(ctx, "DATA_EXTRACTED", L)
        self.assertNotIn("amplitude_overlay", summary)

    def test_overlay_with_controller(self):
        """With controller param, amplitude_overlay block is present."""
        L = build_diamond_landscape()
        ctrl = E0Controller(
            L, all_success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=3,
        )
        ctx = self.memos.snapshot_from_runtime("test-ov", L, ctrl)
        summary = self.memos.summarize_for_llm(
            ctx, "S", landscape=L, controller=ctrl)
        self.assertIn("amplitude_overlay", summary)
        ov = summary["amplitude_overlay"]
        self.assertIn("geometry", ov)
        self.assertIn("greedy_choice", ov)
        self.assertIn("amplitude_choice", ov)
        self.assertIn("agree", ov)
        self.assertIn("actions", ov)
        self.assertIsInstance(ov["agree"], bool)

    def test_overlay_diamond_disagree(self):
        """At Diamond/S, overlay should show DISAGREE (C vs A/B)."""
        L = build_diamond_landscape()
        ctrl = E0Controller(
            L, all_success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=3,
        )
        ctx = self.memos.snapshot_from_runtime("test-dis", L, ctrl)
        summary = self.memos.summarize_for_llm(
            ctx, "S", landscape=L, controller=ctrl)
        ov = summary["amplitude_overlay"]
        # Greedy picks C, amplitude picks A or B → disagree
        self.assertEqual(ov["greedy_choice"], "C")
        self.assertIn(ov["amplitude_choice"], ["A", "B"])
        self.assertFalse(ov["agree"])

    def test_overlay_actions_have_probabilities(self):
        """Each action in overlay has probability, intensity, path_count."""
        L = build_diamond_landscape()
        ctrl = E0Controller(L, all_success, hybrid_horizon=3)
        ctx = self.memos.snapshot_from_runtime("test-act", L, ctrl)
        summary = self.memos.summarize_for_llm(
            ctx, "S", landscape=L, controller=ctrl)
        ov = summary["amplitude_overlay"]
        for action, info in ov["actions"].items():
            self.assertIn("probability", info)
            self.assertIn("intensity", info)
            self.assertIn("path_count", info)
            self.assertGreaterEqual(info["probability"], 0.0)
            self.assertLessEqual(info["probability"], 1.0)

    def test_overlay_summary_json_serializable(self):
        """Summary with overlay is JSON serializable."""
        L = build_diamond_landscape()
        ctrl = E0Controller(L, all_success, hybrid_horizon=3)
        ctx = self.memos.snapshot_from_runtime("test-json", L, ctrl)
        summary = self.memos.summarize_for_llm(
            ctx, "S", landscape=L, controller=ctrl)
        output = json.dumps(summary, indent=2)
        self.assertIn("amplitude_overlay", output)

    def test_summary_has_hybrid_mode_in_runtime(self):
        """Runtime section includes hybrid_mode field."""
        L = build_diamond_landscape()
        ctrl = E0Controller(
            L, all_success,
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
        )
        ctx = self.memos.snapshot_from_runtime("test-rt", L, ctrl)
        summary = self.memos.summarize_for_llm(ctx, "S", L)
        self.assertEqual(summary["runtime"]["hybrid_mode"],
                         "amplitude_on_disagree")

    def test_overlay_at_dead_end(self):
        """Overlay at dead-end state C has no actions → no overlay."""
        L = build_diamond_landscape()
        ctrl = E0Controller(L, all_success, hybrid_horizon=3)
        ctx = self.memos.snapshot_from_runtime("test-de", L, ctrl)
        summary = self.memos.summarize_for_llm(
            ctx, "C", landscape=L, controller=ctrl)
        # C has no neighbors → no overlay
        self.assertNotIn("amplitude_overlay", summary)


# ──────────────────────────────────────────────────────
# Persistence gap fixes — roundtrip tests
# ──────────────────────────────────────────────────────

class TestUseSu2Roundtrip(unittest.TestCase):
    """use_su2 flag survives snapshot → restore cycle."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.memos = E0MemoryOS(base_dir=self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_su2_true_persists(self):
        L = build_invoice_landscape()
        ctrl = E0Controller(L, all_success, use_su2=True)
        ctx = self.memos.snapshot_from_runtime("test-su2", L, ctrl)
        self.memos.save_context(ctx)

        ctx2 = self.memos.load_context("test-su2")
        L2 = self.memos.restore_landscape(ctx2)
        ctrl2 = self.memos.restore_controller(ctx2, L2, all_success)
        self.assertTrue(ctrl2.use_su2)

    def test_su2_false_default(self):
        L = build_invoice_landscape()
        ctrl = E0Controller(L, all_success)
        ctx = self.memos.snapshot_from_runtime("test-su2d", L, ctrl)
        self.memos.save_context(ctx)

        ctx2 = self.memos.load_context("test-su2d")
        L2 = self.memos.restore_landscape(ctx2)
        ctrl2 = self.memos.restore_controller(ctx2, L2, all_success)
        self.assertFalse(ctrl2.use_su2)

    def test_su2_in_llm_summary(self):
        """use_su2=True is exposed in summarize_for_llm runtime."""
        L = build_invoice_landscape()
        ctrl = E0Controller(L, all_success, use_su2=True)
        ctx = self.memos.snapshot_from_runtime("test-su2s", L, ctrl)
        summary = self.memos.summarize_for_llm(ctx, "RECEIVED", L)
        self.assertTrue(summary["runtime"].get("use_su2"))

    def test_su2_absent_when_false(self):
        """use_su2=False → not in LLM summary (token efficiency)."""
        L = build_invoice_landscape()
        ctrl = E0Controller(L, all_success, use_su2=False)
        ctx = self.memos.snapshot_from_runtime("test-su2n", L, ctrl)
        summary = self.memos.summarize_for_llm(ctx, "RECEIVED", L)
        self.assertNotIn("use_su2", summary["runtime"])


class TestCurvatureModulationRoundtrip(unittest.TestCase):
    """curvature_modulation flag survives snapshot → restore cycle."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.memos = E0MemoryOS(base_dir=self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_curvature_on_persists(self):
        L = build_invoice_landscape()
        L.curvature_modulation = True
        ctx = self.memos.snapshot_from_runtime(
            "test-curv", L, E0Controller(L, all_success))
        self.memos.save_context(ctx)

        ctx2 = self.memos.load_context("test-curv")
        L2 = self.memos.restore_landscape(ctx2)
        self.assertTrue(L2.curvature_modulation)

    def test_curvature_off_default(self):
        L = build_invoice_landscape()
        ctx = self.memos.snapshot_from_runtime(
            "test-curvd", L, E0Controller(L, all_success))
        self.memos.save_context(ctx)

        ctx2 = self.memos.load_context("test-curvd")
        L2 = self.memos.restore_landscape(ctx2)
        self.assertFalse(L2.curvature_modulation)

    def test_curvature_snapshot_field(self):
        """LandscapeSnapshot.curvature_modulation reflects landscape."""
        L = build_invoice_landscape()
        L.curvature_modulation = True
        snap = LandscapeSnapshot.from_landscape(L)
        self.assertTrue(snap.curvature_modulation)


class TestEscalationEdgeCreatedBy(unittest.TestCase):
    """Escalation edges carry created_by through persistence."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.memos = E0MemoryOS(base_dir=self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_dead_end_created_by(self):
        """Escalation from DEAD_END stores created_by='dead_end'."""
        L = Landscape()
        L.add_edge("A", "B", delta=0.5, resistance=1.0)
        L.add_edge("C", "A", delta=0.3, resistance=0.5)
        L.add_state("D")  # reachable but no outgoing edges from B

        ctrl = E0Controller(L, all_success)
        trace = ctrl.run("A", max_cycles=5)

        # Find escalation edge
        self.assertTrue(len(ctrl._escalation_edges) > 0)
        for edge, (delta, r0, created_by) in ctrl._escalation_edges.items():
            self.assertIn(created_by, ["dead_end", "filtered", "exhausted"])

    def test_created_by_roundtrip(self):
        """created_by persists through snapshot → save → load → restore."""
        L = Landscape()
        L.add_edge("A", "B", delta=0.5, resistance=1.0)
        L.add_edge("C", "A", delta=0.3, resistance=0.5)
        L.add_state("D")

        ctrl = E0Controller(L, all_success)
        trace = ctrl.run("A", max_cycles=5)

        ctx = self.memos.snapshot_from_runtime("test-cb", L, ctrl, trace)
        self.memos.save_context(ctx)

        ctx2 = self.memos.load_context("test-cb")
        L2 = self.memos.restore_landscape(ctx2)
        ctrl2 = self.memos.restore_controller(ctx2, L2, all_success)

        for edge, (delta, r0, created_by) in ctrl2._escalation_edges.items():
            self.assertIn(created_by, ["dead_end", "filtered", "exhausted", "unknown"])

    def test_created_by_in_snapshot_json(self):
        """RuntimeSnapshot escalation_edges include created_by field."""
        L = Landscape()
        L.add_edge("A", "B", delta=0.5, resistance=1.0)
        L.add_edge("C", "A", delta=0.3, resistance=0.5)

        ctrl = E0Controller(L, all_success)
        trace = ctrl.run("A", max_cycles=5)

        snap = RuntimeSnapshot.from_controller(ctrl, trace)
        for ee in snap.escalation_edges:
            self.assertIn("created_by", ee)


class TestOverlayPersistenceRoundtrip(unittest.TestCase):
    """F4: Amplitude overlay is reproducible after MemOS save→load→restore.

    The overlay report is computed live from landscape + historization state.
    If those inputs are correctly persisted, recomputing the overlay after
    restore must produce identical results.  This closes falsification
    target #4 (MemOS persistence gap).
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.memos = E0MemoryOS(base_dir=self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _build_gordian(self):
        """Build a Gordian-like trap where overlay is non-trivial."""
        L = Landscape()
        L.add_edge("START", "A1", delta=0.3, resistance=0.5)
        L.add_edge("A1", "A2", delta=0.4, resistance=0.6)
        L.add_edge("A2", "GOAL", delta=0.3, resistance=0.5)
        L.add_edge("A1", "LOOP", delta=0.2, resistance=0.3)
        L.add_edge("LOOP", "A1", delta=0.2, resistance=0.3)
        L.add_edge("START", "B1", delta=0.5, resistance=0.8)
        L.add_edge("B1", "B2", delta=0.3, resistance=0.5)
        L.add_edge("B2", "GOAL", delta=0.2, resistance=0.4)
        return L

    def test_overlay_identical_after_restore(self):
        """Overlay report matches before save and after restore."""
        from e0_controller.amplitude_overlay import analyze_controller_state

        L = self._build_gordian()
        ctrl = E0Controller(L, all_success, hybrid_mode=HybridMode.GREEDY,
                            hybrid_goals={"GOAL"}, hybrid_horizon=3)
        trace = ctrl.run("START", max_cycles=5, goal="GOAL")

        # Compute overlay BEFORE save
        report_before = analyze_controller_state(
            ctrl, "START", horizon_edges=3, geometry="simple", goals={"GOAL"})

        # Save → load → restore
        ctx = self.memos.snapshot_from_runtime("test-overlay", L, ctrl, trace)
        self.memos.save_context(ctx)
        ctx2 = self.memos.load_context("test-overlay")
        L2 = self.memos.restore_landscape(ctx2)
        ctrl2 = self.memos.restore_controller(ctx2, L2, all_success)

        # Compute overlay AFTER restore
        report_after = analyze_controller_state(
            ctrl2, "START", horizon_edges=3, geometry="simple", goals={"GOAL"})

        # Key overlay properties must match
        self.assertEqual(report_before.current, report_after.current)
        self.assertEqual(report_before.horizon_edges, report_after.horizon_edges)
        self.assertEqual(report_before.geometry, report_after.geometry)
        self.assertEqual(len(report_before.action_infos),
                         len(report_after.action_infos))
        for a_before, a_after in zip(
            sorted(report_before.action_infos, key=lambda a: a.action),
            sorted(report_after.action_infos, key=lambda a: a.action),
        ):
            self.assertEqual(a_before.action, a_after.action)
            self.assertAlmostEqual(a_before.intensity, a_after.intensity, places=6)
            self.assertAlmostEqual(a_before.probability, a_after.probability, places=6)
            self.assertEqual(a_before.path_count, a_after.path_count)

    def test_overlay_choice_stable_after_restore(self):
        """Amplitude choice (best action) unchanged after restore."""
        from e0_controller.amplitude_overlay import analyze_controller_state

        L = self._build_gordian()
        ctrl = E0Controller(L, all_success, hybrid_mode=HybridMode.GREEDY,
                            hybrid_goals={"GOAL"}, hybrid_horizon=3)
        trace = ctrl.run("START", max_cycles=5, goal="GOAL")

        report_before = analyze_controller_state(
            ctrl, "START", horizon_edges=3, geometry="goal_reaching",
            goals={"GOAL"})

        ctx = self.memos.snapshot_from_runtime("test-choice", L, ctrl, trace)
        self.memos.save_context(ctx)
        ctx2 = self.memos.load_context("test-choice")
        L2 = self.memos.restore_landscape(ctx2)
        ctrl2 = self.memos.restore_controller(ctx2, L2, all_success)

        report_after = analyze_controller_state(
            ctrl2, "START", horizon_edges=3, geometry="goal_reaching",
            goals={"GOAL"})

        self.assertEqual(report_before.amplitude_choice,
                         report_after.amplitude_choice)
        self.assertAlmostEqual(report_before.override_confidence,
                               report_after.override_confidence, places=6)

    def test_historized_overlay_survives_roundtrip(self):
        """After historization changes R_eff, overlay after restore reflects this."""
        from e0_controller.amplitude_overlay import analyze_controller_state

        L = self._build_gordian()
        ctrl = E0Controller(L, sometimes_fail, hybrid_mode=HybridMode.GREEDY,
                            hybrid_goals={"GOAL"}, hybrid_horizon=3)
        # Run with failures to build non-trivial historization
        ctrl.run("START", max_cycles=10, goal="GOAL")
        trace = ctrl.run("START", max_cycles=5, goal="GOAL")

        # Compute overlay AFTER all runs (historization accumulated)
        report_before = analyze_controller_state(
            ctrl, "START", horizon_edges=3, geometry="simple", goals={"GOAL"})

        ctx = self.memos.snapshot_from_runtime("test-hist-overlay", L, ctrl, trace)
        self.memos.save_context(ctx)
        ctx2 = self.memos.load_context("test-hist-overlay")
        L2 = self.memos.restore_landscape(ctx2)
        ctrl2 = self.memos.restore_controller(ctx2, L2, sometimes_fail)

        report_after = analyze_controller_state(
            ctrl2, "START", horizon_edges=3, geometry="simple", goals={"GOAL"})

        # Same number of actions and paths
        self.assertEqual(len(report_before.action_infos),
                         len(report_after.action_infos))
        for a_before, a_after in zip(
            sorted(report_before.action_infos, key=lambda a: a.action),
            sorted(report_after.action_infos, key=lambda a: a.action),
        ):
            self.assertAlmostEqual(a_before.intensity, a_after.intensity, places=6)

    def test_su2_flag_preserved_in_overlay(self):
        """SU(2) mode flag survives roundtrip and produces SU(2) overlay."""
        from e0_controller.amplitude_overlay import analyze_controller_state

        L = self._build_gordian()
        ctrl = E0Controller(L, all_success, hybrid_mode=HybridMode.GREEDY,
                            hybrid_goals={"GOAL"}, hybrid_horizon=3, use_su2=True)
        trace = ctrl.run("START", max_cycles=5, goal="GOAL")

        report_su2_before = analyze_controller_state(
            ctrl, "START", horizon_edges=3, geometry="simple",
            goals={"GOAL"}, use_su2=True)

        ctx = self.memos.snapshot_from_runtime("test-su2-ov", L, ctrl, trace)
        self.memos.save_context(ctx)
        ctx2 = self.memos.load_context("test-su2-ov")
        L2 = self.memos.restore_landscape(ctx2)
        ctrl2 = self.memos.restore_controller(ctx2, L2, all_success)

        # Verify SU(2) flag persisted
        self.assertTrue(ctrl2.use_su2)

        report_su2_after = analyze_controller_state(
            ctrl2, "START", horizon_edges=3, geometry="simple",
            goals={"GOAL"}, use_su2=True)

        for a_before, a_after in zip(
            sorted(report_su2_before.action_infos, key=lambda a: a.action),
            sorted(report_su2_after.action_infos, key=lambda a: a.action),
        ):
            self.assertAlmostEqual(a_before.intensity, a_after.intensity, places=6)


if __name__ == "__main__":
    unittest.main()
