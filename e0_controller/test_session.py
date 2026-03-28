"""
Tests for Session Orchestrator
================================
Verifies automatic MemOS persistence, resume from disk,
tuning memory carry-over, and the full lifecycle.

14 tests in 3 test classes.
"""

import shutil
import tempfile
import unittest

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller, RunTrace
from e0_controller.memory_os import CanonRef, E0MemoryOS
from e0_controller.self_tuning import TuningMemory, load_tuning_memory
from e0_controller.session import Session, SessionResult


def _make_landscape():
    """Simple A → B → C → GOAL landscape."""
    L = Landscape()
    L.add_edge("A", "B", delta=1.0, resistance=1.0)
    L.add_edge("B", "C", delta=1.0, resistance=1.0)
    L.add_edge("C", "GOAL", delta=1.0, resistance=1.0)
    return L


def _success_fn(state, target):
    return Outcome.SUCCESS


# ──────────────────────────────────────────────
# 1. Basic Session Lifecycle
# ──────────────────────────────────────────────

class TestSessionLifecycle(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_run_returns_session_result(self):
        L = _make_landscape()
        s = Session("test1", L, _success_fn, base_dir=self.tmpdir)
        result = s.run("A", goal="GOAL", max_cycles=10)

        self.assertIsInstance(result, SessionResult)
        self.assertEqual(result.session_id, "test1")
        self.assertFalse(result.resumed)
        self.assertEqual(result.trace.path[-1], "GOAL")

    def test_auto_save_creates_files(self):
        L = _make_landscape()
        s = Session("test2", L, _success_fn, base_dir=self.tmpdir)
        s.run("A", goal="GOAL")

        # Session context should exist on disk
        self.assertTrue(s.exists_on_disk)

        # Tuning memory should be saved
        mem = load_tuning_memory("test2", base_dir=self.tmpdir)
        self.assertIsInstance(mem, TuningMemory)

    def test_auto_save_false_skips_disk(self):
        L = _make_landscape()
        s = Session("test3", L, _success_fn, base_dir=self.tmpdir)
        s.run("A", goal="GOAL", auto_save=False)

        self.assertFalse(s.exists_on_disk)

    def test_run_record_saved(self):
        L = _make_landscape()
        s = Session("test4", L, _success_fn, base_dir=self.tmpdir)
        s.run("A", goal="GOAL")

        runs = s.recent_runs(limit=5)
        self.assertEqual(len(runs), 1)
        self.assertTrue(runs[0]["reached_goal"])

    def test_multiple_runs_append(self):
        L = _make_landscape()
        s = Session("test5", L, _success_fn, base_dir=self.tmpdir)
        s.run("A", goal="GOAL")
        s.run("A", goal="GOAL")

        runs = s.recent_runs(limit=5)
        self.assertEqual(len(runs), 2)

    def test_canon_refs_persisted(self):
        L = _make_landscape()
        refs = [CanonRef("ontodynamics", "1.0", "canon/ontodynamics.txt")]
        s = Session("test6", L, _success_fn,
                    base_dir=self.tmpdir, canon_refs=refs)
        result = s.run("A", goal="GOAL")

        self.assertEqual(len(result.context.canon_refs), 1)
        self.assertEqual(result.context.canon_refs[0]["name"], "ontodynamics")

    def test_controller_kwargs_forwarded(self):
        L = _make_landscape()
        s = Session("test7", L, _success_fn,
                    base_dir=self.tmpdir,
                    controller_kwargs={"alpha": 5.0})
        self.assertAlmostEqual(s.controller.alpha, 5.0)


# ──────────────────────────────────────────────
# 2. Resume from Disk
# ──────────────────────────────────────────────

class TestSessionResume(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_resume_restores_session(self):
        """Save session → resume → controller is functional."""
        L = _make_landscape()
        s1 = Session("resume1", L, _success_fn, base_dir=self.tmpdir)
        s1.run("A", goal="GOAL")

        # Resume in a "new process"
        s2 = Session.resume("resume1", _success_fn, base_dir=self.tmpdir)
        self.assertTrue(s2._resumed)
        result = s2.run("A", goal="GOAL")
        self.assertEqual(result.trace.path[-1], "GOAL")
        self.assertTrue(result.resumed)

    def test_resume_preserves_historization(self):
        """Historization from first run should persist into resumed session."""
        L = _make_landscape()
        s1 = Session("resume2", L, _success_fn, base_dir=self.tmpdir)
        s1.run("A", goal="GOAL")

        # Check historization was modified
        edge = Edge("A", "B")
        dh_after_run = s1.landscape.historization.delta_H(edge)

        s2 = Session.resume("resume2", _success_fn, base_dir=self.tmpdir)
        dh_restored = s2.landscape.historization.delta_H(edge)
        self.assertAlmostEqual(dh_after_run, dh_restored, places=4)

    def test_resume_nonexistent_raises(self):
        with self.assertRaises(FileNotFoundError):
            Session.resume("nonexistent", _success_fn, base_dir=self.tmpdir)

    def test_resume_accumulates_runs(self):
        """Run records accumulate across sessions."""
        L = _make_landscape()
        s1 = Session("resume3", L, _success_fn, base_dir=self.tmpdir)
        s1.run("A", goal="GOAL")

        s2 = Session.resume("resume3", _success_fn, base_dir=self.tmpdir)
        s2.run("A", goal="GOAL")

        runs = s2.recent_runs(limit=10)
        self.assertEqual(len(runs), 2)


# ──────────────────────────────────────────────
# 3. Tuning Memory Integration
# ──────────────────────────────────────────────

class TestSessionTuningMemory(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_tuning_memory_saved(self):
        L = _make_landscape()
        s = Session("tuning1", L, _success_fn, base_dir=self.tmpdir)
        s.run("A", goal="GOAL")

        loaded = load_tuning_memory("tuning1", base_dir=self.tmpdir)
        self.assertIsInstance(loaded, TuningMemory)

    def test_tuning_memory_survives_resume(self):
        """Tuning memory persists across session resume."""
        L = _make_landscape()
        s1 = Session("tuning2", L, _success_fn, base_dir=self.tmpdir)

        # Manually add an entry to tuning memory
        from e0_controller.self_tuning import TuningSnapshot
        snap = TuningSnapshot(
            timestamp="2026-03-26T00:00:00+00:00",
            quality=0.7, goal_reached=True,
            tau_eff=0.5, tau_loop=0.0, tau_esc=0.0,
            tau_progress=0.8, tau_efficiency=0.9,
            params={"alpha": 2.0}, applied_changes=[], accepted=False,
        )
        s1.tuning_memory.record(snap)
        s1.run("A", goal="GOAL")

        # Resume and check memory
        s2 = Session.resume("tuning2", _success_fn, base_dir=self.tmpdir)
        self.assertGreaterEqual(len(s2.tuning_memory.entries), 1)
        self.assertAlmostEqual(s2.tuning_memory.entries[0].quality, 0.7)


if __name__ == "__main__":
    unittest.main()
