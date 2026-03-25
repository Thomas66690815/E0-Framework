"""
E₀ MemOS Geometry Tests (Phase 3g)
====================================
Validates that MemOS correctly persists, restores, and summarizes
the amplitude overlay geometry (hybrid_geometry) and confidence
threshold (confidence_threshold) across save/load cycles.

Test families:
    G1  — Geometry stored in RuntimeSnapshot          (3 tests)
    G2  — Geometry round-trip save → load → restore   (4 tests)
    G3  — All four geometries preserved                (4 tests)
    G4  — Confidence threshold persistence             (3 tests)
    G5  — Overlay summary uses correct geometry        (4 tests)
    G6  — Backward compat (no geometry in old data)    (3 tests)
    G7  — Diamond domain geometry round-trip           (4 tests)
    G8  — Gordian domain geometry round-trip           (4 tests)
    G9  — Multi-run geometry consistency               (3 tests)
    G10 — RunRecord with geometry-specific metrics     (2 tests)
"""

from __future__ import annotations

import json
import math
import os
import shutil
import tempfile
import unittest

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller, HybridMode, RunTrace
from e0_controller.memory_os import (
    E0MemoryOS,
    RuntimeSnapshot,
)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _success(source: str, target: str) -> Outcome:
    return Outcome.SUCCESS


def _build_diamond():
    """S→A, S→B, A→G, B→G. Two paths to goal."""
    L = Landscape()
    L.add_edge("S", "A", delta=0.5, resistance=1.0)
    L.add_edge("S", "B", delta=0.6, resistance=1.0)
    L.add_edge("A", "G", delta=0.5, resistance=1.0)
    L.add_edge("B", "G", delta=0.4, resistance=1.0)
    return L


def _build_gordian():
    """S→A (trap-loop A→A_loop→A), S→B→G (correct path)."""
    L = Landscape()
    L.add_edge("S", "A", delta=0.1, resistance=1.0)
    L.add_edge("S", "B", delta=0.8, resistance=1.0)
    L.add_edge("A", "A_loop", delta=0.1, resistance=1.0)
    L.add_edge("A_loop", "A", delta=0.1, resistance=1.0)
    L.add_edge("B", "G", delta=0.3, resistance=1.0)
    return L


def _build_mini():
    """A→B→C→D, simple linear path."""
    L = Landscape()
    L.add_edge("A", "B", delta=0.5, resistance=1.0)
    L.add_edge("B", "C", delta=0.5, resistance=1.0)
    L.add_edge("C", "D", delta=0.5, resistance=1.0)
    return L


def _make_hybrid_ctrl(L, geometry="simple", threshold=0.0,
                      goals=None, horizon=3):
    """Create a HYBRID controller with specified geometry/threshold."""
    return E0Controller(
        L, _success,
        hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
        hybrid_horizon=horizon,
        hybrid_goals=goals,
        hybrid_geometry=geometry,
        confidence_threshold=threshold,
    )


# ──────────────────────────────────────────────
# G1 — Geometry stored in RuntimeSnapshot
# ──────────────────────────────────────────────

class TestG1SnapshotGeometry(unittest.TestCase):
    """Verify RuntimeSnapshot captures hybrid_geometry."""

    def test_default_geometry_stored(self):
        """Default geometry='simple' appears in snapshot."""
        L = _build_diamond()
        ctrl = _make_hybrid_ctrl(L)
        snap = RuntimeSnapshot.from_controller(ctrl)
        self.assertEqual(
            snap.controller_params["hybrid_geometry"], "simple")

    def test_explicit_geometry_stored(self):
        """Non-default geometry='goal_reaching' captured."""
        L = _build_diamond()
        ctrl = _make_hybrid_ctrl(L, geometry="goal_reaching", goals={"G"})
        snap = RuntimeSnapshot.from_controller(ctrl)
        self.assertEqual(
            snap.controller_params["hybrid_geometry"], "goal_reaching")

    def test_confidence_threshold_stored(self):
        """confidence_threshold captured in snapshot."""
        L = _build_diamond()
        ctrl = _make_hybrid_ctrl(L, threshold=0.42)
        snap = RuntimeSnapshot.from_controller(ctrl)
        self.assertAlmostEqual(
            snap.controller_params["confidence_threshold"], 0.42)


# ──────────────────────────────────────────────
# G2 — Geometry round-trip save → load → restore
# ──────────────────────────────────────────────

class TestG2GeometryRoundTrip(unittest.TestCase):
    """Full save → load → restore preserves geometry."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.memos = E0MemoryOS(base_dir=self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_simple_round_trip(self):
        L = _build_diamond()
        ctrl = _make_hybrid_ctrl(L, geometry="simple")
        ctx = self.memos.snapshot_from_runtime("g2-simple", L, ctrl)
        self.memos.save_context(ctx)
        ctx2 = self.memos.load_context("g2-simple")
        L2 = self.memos.restore_landscape(ctx2)
        ctrl2 = self.memos.restore_controller(ctx2, L2, _success)
        self.assertEqual(ctrl2.hybrid_geometry, "simple")

    def test_goal_reaching_round_trip(self):
        L = _build_diamond()
        ctrl = _make_hybrid_ctrl(L, geometry="goal_reaching", goals={"G"})
        ctx = self.memos.snapshot_from_runtime("g2-gr", L, ctrl)
        self.memos.save_context(ctx)
        ctx2 = self.memos.load_context("g2-gr")
        L2 = self.memos.restore_landscape(ctx2)
        ctrl2 = self.memos.restore_controller(ctx2, L2, _success)
        self.assertEqual(ctrl2.hybrid_geometry, "goal_reaching")
        self.assertEqual(ctrl2.hybrid_goals, {"G"})

    def test_confidence_threshold_round_trip(self):
        L = _build_diamond()
        ctrl = _make_hybrid_ctrl(L, threshold=0.75)
        ctx = self.memos.snapshot_from_runtime("g2-ct", L, ctrl)
        self.memos.save_context(ctx)
        ctx2 = self.memos.load_context("g2-ct")
        L2 = self.memos.restore_landscape(ctx2)
        ctrl2 = self.memos.restore_controller(ctx2, L2, _success)
        self.assertAlmostEqual(ctrl2.confidence_threshold, 0.75)

    def test_json_has_geometry_field(self):
        """Persisted JSON file contains hybrid_geometry."""
        L = _build_diamond()
        ctrl = _make_hybrid_ctrl(L, geometry="first_arrival", goals={"G"})
        ctx = self.memos.snapshot_from_runtime("g2-json", L, ctrl)
        path = self.memos.save_context(ctx)
        data = json.loads(path.read_text(encoding="utf-8"))
        params = data["runtime"]["controller_params"]
        self.assertEqual(params["hybrid_geometry"], "first_arrival")
        self.assertIn("confidence_threshold", params)


# ──────────────────────────────────────────────
# G3 — All four geometries preserved
# ──────────────────────────────────────────────

class TestG3AllGeometries(unittest.TestCase):
    """Each of the 4 geometry types survives round-trip."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.memos = E0MemoryOS(base_dir=self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _round_trip(self, geometry):
        L = _build_diamond()
        goals = {"G"} if geometry in ("first_arrival", "goal_reaching") else None
        ctrl = _make_hybrid_ctrl(L, geometry=geometry, goals=goals)
        sid = f"g3-{geometry}"
        ctx = self.memos.snapshot_from_runtime(sid, L, ctrl)
        self.memos.save_context(ctx)
        ctx2 = self.memos.load_context(sid)
        L2 = self.memos.restore_landscape(ctx2)
        ctrl2 = self.memos.restore_controller(ctx2, L2, _success)
        return ctrl2

    def test_prefix(self):
        ctrl = self._round_trip("prefix")
        self.assertEqual(ctrl.hybrid_geometry, "prefix")

    def test_simple(self):
        ctrl = self._round_trip("simple")
        self.assertEqual(ctrl.hybrid_geometry, "simple")

    def test_first_arrival(self):
        ctrl = self._round_trip("first_arrival")
        self.assertEqual(ctrl.hybrid_geometry, "first_arrival")

    def test_goal_reaching(self):
        ctrl = self._round_trip("goal_reaching")
        self.assertEqual(ctrl.hybrid_geometry, "goal_reaching")


# ──────────────────────────────────────────────
# G4 — Confidence threshold persistence
# ──────────────────────────────────────────────

class TestG4ConfidenceThreshold(unittest.TestCase):
    """Confidence threshold values survive round-trip."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.memos = E0MemoryOS(base_dir=self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_zero_threshold(self):
        L = _build_diamond()
        ctrl = _make_hybrid_ctrl(L, threshold=0.0)
        ctx = self.memos.snapshot_from_runtime("g4-zero", L, ctrl)
        self.memos.save_context(ctx)
        ctx2 = self.memos.load_context("g4-zero")
        L2 = self.memos.restore_landscape(ctx2)
        ctrl2 = self.memos.restore_controller(ctx2, L2, _success)
        self.assertEqual(ctrl2.confidence_threshold, 0.0)

    def test_high_threshold(self):
        L = _build_diamond()
        ctrl = _make_hybrid_ctrl(L, threshold=0.95)
        ctx = self.memos.snapshot_from_runtime("g4-high", L, ctrl)
        self.memos.save_context(ctx)
        ctx2 = self.memos.load_context("g4-high")
        L2 = self.memos.restore_landscape(ctx2)
        ctrl2 = self.memos.restore_controller(ctx2, L2, _success)
        self.assertAlmostEqual(ctrl2.confidence_threshold, 0.95)

    def test_fractional_threshold(self):
        L = _build_diamond()
        ctrl = _make_hybrid_ctrl(L, threshold=0.333)
        ctx = self.memos.snapshot_from_runtime("g4-frac", L, ctrl)
        self.memos.save_context(ctx)
        ctx2 = self.memos.load_context("g4-frac")
        L2 = self.memos.restore_landscape(ctx2)
        ctrl2 = self.memos.restore_controller(ctx2, L2, _success)
        self.assertAlmostEqual(ctrl2.confidence_threshold, 0.333, places=3)


# ──────────────────────────────────────────────
# G5 — Overlay summary uses correct geometry
# ──────────────────────────────────────────────

class TestG5OverlayGeometry(unittest.TestCase):
    """summarize_for_llm produces overlay with correct geometry."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.memos = E0MemoryOS(base_dir=self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _summarize(self, geometry, goals=None):
        L = _build_diamond()
        ctrl = _make_hybrid_ctrl(L, geometry=geometry, goals=goals)
        ctx = self.memos.snapshot_from_runtime("g5", L, ctrl)
        summary = self.memos.summarize_for_llm(ctx, "S", landscape=L,
                                                controller=ctrl)
        return summary

    def test_simple_geometry_in_overlay(self):
        s = self._summarize("simple")
        self.assertEqual(s["amplitude_overlay"]["geometry"], "simple")

    def test_prefix_geometry_in_overlay(self):
        s = self._summarize("prefix")
        self.assertEqual(s["amplitude_overlay"]["geometry"], "prefix")

    def test_first_arrival_geometry_in_overlay(self):
        s = self._summarize("first_arrival", goals={"G"})
        self.assertEqual(s["amplitude_overlay"]["geometry"], "first_arrival")

    def test_goal_reaching_geometry_in_overlay(self):
        s = self._summarize("goal_reaching", goals={"G"})
        self.assertEqual(s["amplitude_overlay"]["geometry"], "goal_reaching")


# ──────────────────────────────────────────────
# G6 — Backward compat (old data without geometry)
# ──────────────────────────────────────────────

class TestG6BackwardCompat(unittest.TestCase):
    """Old sessions without hybrid_geometry restore as 'simple'."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.memos = E0MemoryOS(base_dir=self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_missing_geometry_defaults_simple(self):
        """If persisted data lacks hybrid_geometry, default to 'simple'."""
        L = _build_diamond()
        ctrl = _make_hybrid_ctrl(L)
        ctx = self.memos.snapshot_from_runtime("g6-old", L, ctrl)
        # Manually remove geometry from serialized params (simulates old data)
        ctx.runtime["controller_params"].pop("hybrid_geometry", None)
        self.memos.save_context(ctx)
        ctx2 = self.memos.load_context("g6-old")
        L2 = self.memos.restore_landscape(ctx2)
        ctrl2 = self.memos.restore_controller(ctx2, L2, _success)
        self.assertEqual(ctrl2.hybrid_geometry, "simple")

    def test_missing_threshold_defaults_zero(self):
        """If persisted data lacks confidence_threshold, default to 0.0."""
        L = _build_diamond()
        ctrl = _make_hybrid_ctrl(L)
        ctx = self.memos.snapshot_from_runtime("g6-noct", L, ctrl)
        ctx.runtime["controller_params"].pop("confidence_threshold", None)
        self.memos.save_context(ctx)
        ctx2 = self.memos.load_context("g6-noct")
        L2 = self.memos.restore_landscape(ctx2)
        ctrl2 = self.memos.restore_controller(ctx2, L2, _success)
        self.assertEqual(ctrl2.confidence_threshold, 0.0)

    def test_old_data_still_runs(self):
        """Controller restored from old data (no geometry field) can run."""
        L = _build_diamond()
        ctrl = _make_hybrid_ctrl(L, goals={"G"})
        ctx = self.memos.snapshot_from_runtime("g6-run", L, ctrl)
        ctx.runtime["controller_params"].pop("hybrid_geometry", None)
        ctx.runtime["controller_params"].pop("confidence_threshold", None)
        self.memos.save_context(ctx)
        ctx2 = self.memos.load_context("g6-run")
        L2 = self.memos.restore_landscape(ctx2)
        ctrl2 = self.memos.restore_controller(ctx2, L2, _success)
        trace = ctrl2.run("S", goal="G", max_cycles=10)
        self.assertIn("G", trace.path)


# ──────────────────────────────────────────────
# G7 — Diamond domain geometry round-trip
# ──────────────────────────────────────────────

class TestG7DiamondRoundTrip(unittest.TestCase):
    """Diamond domain: geometry affects overlay after restore."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.memos = E0MemoryOS(base_dir=self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _save_and_restore(self, geometry, goals=None):
        L = _build_diamond()
        ctrl = _make_hybrid_ctrl(L, geometry=geometry, goals=goals)
        ctx = self.memos.snapshot_from_runtime(f"g7-{geometry}", L, ctrl)
        self.memos.save_context(ctx)
        ctx2 = self.memos.load_context(f"g7-{geometry}")
        L2 = self.memos.restore_landscape(ctx2)
        ctrl2 = self.memos.restore_controller(ctx2, L2, _success)
        return ctrl2

    def test_diamond_simple_restore(self):
        ctrl = self._save_and_restore("simple")
        t, esc, esc_type, overlay, overridden = ctrl.select_hybrid("S")
        self.assertIsNotNone(overlay)
        self.assertEqual(overlay.geometry, "simple")

    def test_diamond_goal_reaching_restore(self):
        ctrl = self._save_and_restore("goal_reaching", goals={"G"})
        t, esc, esc_type, overlay, overridden = ctrl.select_hybrid("S")
        self.assertIsNotNone(overlay)
        self.assertEqual(overlay.geometry, "goal_reaching")

    def test_diamond_prefix_restore(self):
        ctrl = self._save_and_restore("prefix")
        t, esc, esc_type, overlay, overridden = ctrl.select_hybrid("S")
        self.assertIsNotNone(overlay)
        self.assertEqual(overlay.geometry, "prefix")

    def test_diamond_first_arrival_restore(self):
        ctrl = self._save_and_restore("first_arrival", goals={"G"})
        t, esc, esc_type, overlay, overridden = ctrl.select_hybrid("S")
        self.assertIsNotNone(overlay)
        self.assertEqual(overlay.geometry, "first_arrival")


# ──────────────────────────────────────────────
# G8 — Gordian domain geometry round-trip
# ──────────────────────────────────────────────

class TestG8GordianRoundTrip(unittest.TestCase):
    """Gordian domain: geometry survives and overlay behaves correctly."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.memos = E0MemoryOS(base_dir=self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _save_and_restore(self, geometry, goals=None, threshold=0.0):
        L = _build_gordian()
        ctrl = _make_hybrid_ctrl(L, geometry=geometry, goals=goals,
                                  threshold=threshold)
        ctx = self.memos.snapshot_from_runtime(f"g8-{geometry}", L, ctrl)
        self.memos.save_context(ctx)
        ctx2 = self.memos.load_context(f"g8-{geometry}")
        L2 = self.memos.restore_landscape(ctx2)
        ctrl2 = self.memos.restore_controller(ctx2, L2, _success)
        return ctrl2

    def test_gordian_simple_restore(self):
        ctrl = self._save_and_restore("simple")
        t, esc, esc_type, overlay, overridden = ctrl.select_hybrid("S")
        self.assertEqual(overlay.geometry, "simple")

    def test_gordian_goal_reaching_restore(self):
        ctrl = self._save_and_restore("goal_reaching", goals={"G"})
        t, esc, esc_type, overlay, overridden = ctrl.select_hybrid("S")
        self.assertEqual(overlay.geometry, "goal_reaching")

    def test_gordian_threshold_restore(self):
        """Confidence threshold survives round-trip on Gordian."""
        ctrl = self._save_and_restore("simple", threshold=0.8)
        self.assertAlmostEqual(ctrl.confidence_threshold, 0.8)

    def test_gordian_restored_run_reaches_goal(self):
        """Restored controller with goal_reaching+goals can run."""
        ctrl = self._save_and_restore("goal_reaching", goals={"G"})
        trace = ctrl.run("S", goal="G", max_cycles=10)
        self.assertIn("G", trace.path)


# ──────────────────────────────────────────────
# G9 — Multi-run geometry consistency
# ──────────────────────────────────────────────

class TestG9MultiRun(unittest.TestCase):
    """Geometry persists correctly across multiple save/restore cycles."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.memos = E0MemoryOS(base_dir=self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_geometry_stable_after_two_saves(self):
        """Save→restore→run→save→restore: geometry stays."""
        L = _build_diamond()
        ctrl = _make_hybrid_ctrl(L, geometry="first_arrival", goals={"G"})
        # First save
        ctx = self.memos.snapshot_from_runtime("g9-multi", L, ctrl)
        self.memos.save_context(ctx)
        # First restore + run
        ctx2 = self.memos.load_context("g9-multi")
        L2 = self.memos.restore_landscape(ctx2)
        ctrl2 = self.memos.restore_controller(ctx2, L2, _success)
        ctrl2.run("S", goal="G", max_cycles=10)
        # Second save
        ctx3 = self.memos.snapshot_from_runtime("g9-multi", L2, ctrl2)
        self.memos.save_context(ctx3)
        # Second restore
        ctx4 = self.memos.load_context("g9-multi")
        L3 = self.memos.restore_landscape(ctx4)
        ctrl3 = self.memos.restore_controller(ctx4, L3, _success)
        self.assertEqual(ctrl3.hybrid_geometry, "first_arrival")

    def test_threshold_stable_after_two_saves(self):
        """Confidence threshold persists across two save/restore cycles."""
        L = _build_diamond()
        ctrl = _make_hybrid_ctrl(L, threshold=0.6)
        ctx = self.memos.snapshot_from_runtime("g9-ct", L, ctrl)
        self.memos.save_context(ctx)
        ctx2 = self.memos.load_context("g9-ct")
        L2 = self.memos.restore_landscape(ctx2)
        ctrl2 = self.memos.restore_controller(ctx2, L2, _success)
        ctx3 = self.memos.snapshot_from_runtime("g9-ct", L2, ctrl2)
        self.memos.save_context(ctx3)
        ctx4 = self.memos.load_context("g9-ct")
        L3 = self.memos.restore_landscape(ctx4)
        ctrl3 = self.memos.restore_controller(ctx4, L3, _success)
        self.assertAlmostEqual(ctrl3.confidence_threshold, 0.6)

    def test_different_sessions_different_geometries(self):
        """Two sessions with different geometries stay independent."""
        L = _build_diamond()
        ctrl_s = _make_hybrid_ctrl(L, geometry="simple")
        ctrl_g = _make_hybrid_ctrl(L, geometry="goal_reaching", goals={"G"})
        ctx_s = self.memos.snapshot_from_runtime("g9-s", L, ctrl_s)
        ctx_g = self.memos.snapshot_from_runtime("g9-g", L, ctrl_g)
        self.memos.save_context(ctx_s)
        self.memos.save_context(ctx_g)
        # Restore each
        cs = self.memos.load_context("g9-s")
        cg = self.memos.load_context("g9-g")
        Ls = self.memos.restore_landscape(cs)
        Lg = self.memos.restore_landscape(cg)
        rs = self.memos.restore_controller(cs, Ls, _success)
        rg = self.memos.restore_controller(cg, Lg, _success)
        self.assertEqual(rs.hybrid_geometry, "simple")
        self.assertEqual(rg.hybrid_geometry, "goal_reaching")


# ──────────────────────────────────────────────
# G10 — RunRecord with geometry-specific metrics
# ──────────────────────────────────────────────

class TestG10RunRecord(unittest.TestCase):
    """RunRecord from a geometry-enabled controller has correct metrics."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.memos = E0MemoryOS(base_dir=self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_run_record_with_geometry(self):
        """save_run on a goal_reaching controller produces valid record."""
        L = _build_diamond()
        ctrl = _make_hybrid_ctrl(L, geometry="goal_reaching", goals={"G"})
        trace = ctrl.run("S", goal="G", max_cycles=10)
        record = self.memos.save_run("g10-rec", trace, goal="G")
        self.assertTrue(record.reached_goal)
        self.assertIn("avg_override_confidence", record.metrics)

    def test_run_record_has_override_confidence(self):
        """avg_override_confidence metric present in RunRecord."""
        L = _build_diamond()
        ctrl = _make_hybrid_ctrl(L, threshold=0.5)
        trace = ctrl.run("S", goal="G", max_cycles=10)
        record = self.memos.save_run("g10-oc", trace, goal="G")
        self.assertIn("avg_override_confidence", record.metrics)
        self.assertIsInstance(record.metrics["avg_override_confidence"], float)


if __name__ == "__main__":
    unittest.main()
