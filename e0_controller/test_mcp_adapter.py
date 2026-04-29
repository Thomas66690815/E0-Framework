"""
Tests for E₀ MCP Adapter (C291)
=================================
Tests the pure-Python adapter logic without any MCP dependency.

Classes:
  TestObserve         — observe() and observe_edge() basics
  TestRecommend       — cold start, steering after inscriptions
  TestPersistence     — save/load round-trip
  TestStatus          — status() reflects landscape state
  TestEdgeGrowth      — landscape auto-grows from observe_edge calls
"""

import json
import tempfile
import unittest
from pathlib import Path

from e0_controller.mcp_adapter import E0AdapterSession, MIN_INSCRIPTIONS, RecommendResult
from e0_controller.primitives import Outcome


# ── TestObserve ───────────────────────────────────────────────────────────────

class TestObserve(unittest.TestCase):
    """observe() and observe_edge() record outcomes correctly."""

    def setUp(self):
        self.session = E0AdapterSession()

    def test_observe_returns_ok(self):
        result = self.session.observe("search", "success")
        self.assertTrue(result["ok"])
        self.assertEqual(result["signal_id"], "search")
        self.assertEqual(result["outcome"], "success")
        self.assertEqual(result["inscriptions"], 1)

    def test_observe_increments_count(self):
        for _ in range(3):
            self.session.observe("search", "success")
        self.assertEqual(self.session._inscription_count, 3)

    def test_observe_unknown_outcome_defaults_to_failure(self):
        result = self.session.observe("step", "unknown_garbage")
        self.assertEqual(result["outcome"], "failure")

    def test_observe_partial(self):
        result = self.session.observe("analyze", "partial")
        self.assertEqual(result["outcome"], "partial")

    def test_observe_edge_creates_landscape_edge(self):
        self.session.observe_edge("start", "search", "success")
        edges = {(e.source, e.target) for e in self.session._landscape.edges}
        self.assertIn(("start", "search"), edges)

    def test_observe_edge_records_in_port(self):
        self.session.observe_edge("start", "search", "success")
        # Port records "start→search" as signal_id
        signals = self.session._port.observed_signals()
        self.assertIn("start→search", signals)

    def test_observe_edge_repeated_success_raises_quality(self):
        for _ in range(5):
            self.session.observe_edge("A", "B", "success")
        from e0_controller.primitives import Edge
        q = self.session._landscape.historization.trace_quality(Edge("A", "B"))
        self.assertGreater(q, 0.0)

    def test_observe_edge_repeated_failure_lowers_quality(self):
        for _ in range(5):
            self.session.observe_edge("A", "B", "failure")
        from e0_controller.primitives import Edge
        q = self.session._landscape.historization.trace_quality(Edge("A", "B"))
        self.assertLess(q, 0.0)


# ── TestRecommend ─────────────────────────────────────────────────────────────

class TestRecommend(unittest.TestCase):
    """recommend() returns None on cold start, steers after inscriptions."""

    def setUp(self):
        self.session = E0AdapterSession()

    def test_cold_start_returns_none(self):
        result = self.session.recommend("start", ["search", "llm_direct"])
        self.assertIsInstance(result, RecommendResult)
        self.assertIsNone(result.recommended)
        self.assertIn("cold start", result.reason)

    def test_cold_start_empty_candidates_returns_none(self):
        result = self.session.recommend("start", [])
        self.assertIsNone(result.recommended)

    def test_after_min_inscriptions_returns_a_candidate(self):
        # Record enough edges to pass cold start
        for _ in range(MIN_INSCRIPTIONS):
            self.session.observe_edge("start", "search", "success")
        result = self.session.recommend("start", ["search", "llm_direct"])
        self.assertIsNotNone(result.recommended)
        self.assertIn(result.recommended, ["search", "llm_direct"])

    def test_recommend_prefers_success_over_failure(self):
        # Give A→good many successes, A→bad many failures
        for _ in range(10):
            self.session.observe_edge("A", "good", "success")
        for _ in range(10):
            self.session.observe_edge("A", "bad", "failure")
        # Now ask with both candidates
        result = self.session.recommend("A", ["good", "bad"])
        self.assertEqual(result.recommended, "good")

    def test_recommend_result_quality_is_float(self):
        for _ in range(MIN_INSCRIPTIONS):
            self.session.observe_edge("X", "Y", "success")
        result = self.session.recommend("X", ["Y", "Z"])
        self.assertIsInstance(result.quality, float)

    def test_recommend_auto_creates_missing_edges(self):
        # Force past cold start with unrelated edges
        for _ in range(MIN_INSCRIPTIONS):
            self.session.observe_edge("other", "thing", "success")
        # These edges don't exist yet
        self.session.recommend("new_state", ["opt_a", "opt_b"])
        edges = {(e.source, e.target) for e in self.session._landscape.edges}
        self.assertIn(("new_state", "opt_a"), edges)
        self.assertIn(("new_state", "opt_b"), edges)

    def test_recommend_inscription_count_correct(self):
        for _ in range(MIN_INSCRIPTIONS):
            self.session.observe_edge("s", "t", "success")
        result = self.session.recommend("s", ["t"])
        self.assertEqual(result.inscriptions, MIN_INSCRIPTIONS)


# ── TestStatus ────────────────────────────────────────────────────────────────

class TestStatus(unittest.TestCase):
    """status() reflects current state correctly."""

    def setUp(self):
        self.session = E0AdapterSession()

    def test_status_fresh_session(self):
        s = self.session.status()
        self.assertEqual(s["inscriptions"], 0)
        self.assertEqual(s["landscape_nodes"], 0)
        self.assertEqual(s["landscape_edges"], 0)
        self.assertTrue(s["cold_start"])

    def test_status_after_observe_edge(self):
        self.session.observe_edge("A", "B", "success")
        s = self.session.status()
        self.assertEqual(s["landscape_edges"], 1)
        self.assertEqual(s["landscape_nodes"], 2)
        self.assertEqual(s["inscriptions"], 1)

    def test_status_cold_start_flips_after_min_inscriptions(self):
        for _ in range(MIN_INSCRIPTIONS):
            self.session.observe_edge("A", "B", "success")
        s = self.session.status()
        self.assertFalse(s["cold_start"])


# ── TestEdgeGrowth ────────────────────────────────────────────────────────────

class TestEdgeGrowth(unittest.TestCase):
    """Landscape grows from observations — structure emerges, not designed."""

    def setUp(self):
        self.session = E0AdapterSession()

    def test_fresh_landscape_is_empty(self):
        self.assertEqual(len(list(self.session._landscape.edges)), 0)

    def test_edges_added_on_observe_edge(self):
        self.session.observe_edge("start", "search", "success")
        self.session.observe_edge("search", "browse", "failure")
        self.session.observe_edge("browse", "synthesize", "success")
        edges = {(e.source, e.target) for e in self.session._landscape.edges}
        self.assertEqual(len(edges), 3)

    def test_duplicate_observe_edge_does_not_duplicate_edge(self):
        for _ in range(5):
            self.session.observe_edge("A", "B", "success")
        edges = list(self.session._landscape.edges)
        # Should have exactly one A→B edge
        ab_edges = [(e.source, e.target) for e in edges if e.source == "A"]
        self.assertEqual(len(ab_edges), 1)


# ── TestPersistence ───────────────────────────────────────────────────────────

class TestPersistence(unittest.TestCase):
    """save/load round-trip preserves state."""

    def test_save_load_inscription_count(self):
        session = E0AdapterSession()
        for _ in range(3):
            session.observe("step", "success")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.json"
            session.save(path)
            restored = E0AdapterSession.load(path)
        self.assertEqual(restored._inscription_count, 3)

    def test_save_load_landscape_edges(self):
        session = E0AdapterSession()
        session.observe_edge("A", "B", "success")
        session.observe_edge("B", "C", "failure")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.json"
            session.save(path)
            restored = E0AdapterSession.load(path)
        edges = {(e.source, e.target) for e in restored._landscape.edges}
        self.assertIn(("A", "B"), edges)
        self.assertIn(("B", "C"), edges)

    def test_save_load_historization_traces(self):
        session = E0AdapterSession()
        for _ in range(5):
            session.observe_edge("A", "B", "success")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.json"
            session.save(path)
            restored = E0AdapterSession.load(path)
        from e0_controller.primitives import Edge
        q_original = session._landscape.historization.trace_quality(Edge("A", "B"))
        q_restored = restored._landscape.historization.trace_quality(Edge("A", "B"))
        self.assertAlmostEqual(q_original, q_restored, places=4)

    def test_load_missing_file_returns_fresh_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nonexistent.json"
            session = E0AdapterSession.load(path)
        self.assertEqual(session._inscription_count, 0)

    def test_load_corrupted_file_returns_fresh_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.json"
            path.write_text("not valid json", encoding="utf-8")
            session = E0AdapterSession.load(path)
        self.assertEqual(session._inscription_count, 0)

    def test_save_creates_parent_directories(self):
        session = E0AdapterSession()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "deep" / "nested" / "session.json"
            session.save(path)
            self.assertTrue(path.exists())

    def test_save_file_is_valid_json(self):
        session = E0AdapterSession()
        session.observe_edge("A", "B", "success")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.json"
            session.save(path)
            data = json.loads(path.read_text())
        self.assertIn("inscription_count", data)
        self.assertIn("landscape", data)
        self.assertIn("port", data)


if __name__ == "__main__":
    unittest.main()
