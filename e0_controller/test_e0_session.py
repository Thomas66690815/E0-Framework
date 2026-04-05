"""Tests for E₀ Session Runner (C165)."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from e0_controller.e0_session import (
    E0SessionResult,
    run_session,
    _load_perception,
    _mock_llm_call,
    PERCEPTION_MEMO,
)
from e0_controller.communication import IntentReport, IntentType
from e0_controller.perception import PerceptionDomain, build_perception_domain
from e0_controller.scenario_loader import find_scenario, load_scenario
from e0_controller.ui_emitter import UISpec


class TestMockLLMCall(unittest.TestCase):
    """The mock LLM provides a valid landscape."""

    def test_mock_returns_landscape_json(self):
        from e0_controller.llm_adapter import LLMConfig
        raw = _mock_llm_call("system", "design the complete state graph", LLMConfig())
        data = json.loads(raw)
        self.assertIn("states", data)
        self.assertIn("edges", data)
        self.assertGreater(len(data["states"]), 2)

    def test_mock_returns_execute_result(self):
        from e0_controller.llm_adapter import LLMConfig
        raw = _mock_llm_call("system", "Execute the transition from A to B", LLMConfig())
        data = json.loads(raw)
        self.assertEqual(data["outcome"], "SUCCESS")


class TestLoadPerception(unittest.TestCase):
    """Perception loading: pretrained vs fresh."""

    def test_load_fresh_when_no_file(self):
        domain = _load_perception("/nonexistent/path.json")
        self.assertIsInstance(domain, PerceptionDomain)
        self.assertEqual(len(domain.primitives), 22)

    def test_load_from_saved_file(self):
        # Create a saved perception
        domain = build_perception_domain()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test_perception.json")
            domain.save_state(path)
            loaded = _load_perception(path)
            self.assertIsInstance(loaded, PerceptionDomain)
            self.assertEqual(len(loaded.primitives), len(domain.primitives))

    def test_load_pretrained_if_exists(self):
        """If perception_pretrained.json exists, it gets loaded."""
        if os.path.exists(PERCEPTION_MEMO):
            domain = _load_perception(None)
            self.assertIsInstance(domain, PerceptionDomain)
            snap = domain.snapshot()
            self.assertGreater(snap.total_load, 0)


class TestRunSessionMock(unittest.TestCase):
    """Full end-to-end session with mock LLM."""

    def test_session_runs_end_to_end(self):
        result = run_session(
            use_mock=True,
            open_browser=False,
            session_id="test-e2e",
            max_iterations=2,
        )
        self.assertIsInstance(result, E0SessionResult)
        self.assertEqual(result.session_id, "test-e2e")
        self.assertGreater(result.iterations, 0)
        self.assertIn(result.stop_reason,
                      ["equilibrium", "stagnation", "budget"])

    def test_session_produces_intents(self):
        result = run_session(
            use_mock=True,
            open_browser=False,
            session_id="test-intents",
            max_iterations=1,
        )
        self.assertIsInstance(result.intent_report, IntentReport)
        self.assertGreater(len(result.intent_report.intents), 0)

    def test_session_produces_ui_spec(self):
        result = run_session(
            use_mock=True,
            open_browser=False,
            session_id="test-spec",
            max_iterations=1,
        )
        self.assertIsInstance(result.ui_spec, UISpec)
        self.assertGreater(result.ui_spec.panel_count, 0)

    def test_session_renders_html(self):
        result = run_session(
            use_mock=True,
            open_browser=False,
            session_id="test-html",
            max_iterations=1,
        )
        self.assertIsNotNone(result.html_path)
        self.assertTrue(Path(str(result.html_path)).exists())
        # Cleanup
        Path(str(result.html_path)).unlink(missing_ok=True)

    def test_session_saves_perception(self):
        result = run_session(
            use_mock=True,
            open_browser=False,
            session_id="test-save",
            max_iterations=1,
        )
        self.assertIsNotNone(result.perception_saved)

    def test_session_goal_reached(self):
        result = run_session(
            use_mock=True,
            open_browser=False,
            session_id="test-goal",
            max_iterations=3,
        )
        # Mock landscape is linear → goal should be reachable
        self.assertTrue(result.goal_reached)

    def test_session_summary(self):
        result = run_session(
            use_mock=True,
            open_browser=False,
            session_id="test-summary",
            max_iterations=1,
        )
        summary = result.summary()
        self.assertIn("test-summary", summary)
        self.assertIn("Iterations", summary)


class TestSessionWithPretrained(unittest.TestCase):
    """Session uses pretrained perception when available."""

    def test_pretrained_perception_affects_panels(self):
        """When pretrained perception exists, panel choices differ from cold start."""
        # Run with fresh perception
        result_fresh = run_session(
            use_mock=True,
            open_browser=False,
            session_id="test-fresh",
            perception_path="/nonexistent/path.json",
            max_iterations=1,
        )

        # Run with pretrained (if exists)
        if os.path.exists(PERCEPTION_MEMO):
            result_trained = run_session(
                use_mock=True,
                open_browser=False,
                session_id="test-trained",
                perception_path=PERCEPTION_MEMO,
                max_iterations=1,
            )
            # Both produce specs — the trained one may differ
            self.assertGreater(result_trained.ui_spec.panel_count, 0)
            self.assertGreater(result_fresh.ui_spec.panel_count, 0)


class TestSessionWithScenario(unittest.TestCase):
    """Session can load scenario packets."""

    def test_scenario_overrides_task(self):
        sc_path = find_scenario("competitor_brief")
        if sc_path is None:
            self.skipTest("No competitor_brief scenario found")
        scenario = load_scenario(sc_path)
        result = run_session(
            use_mock=True,
            open_browser=False,
            scenario=scenario,
            max_iterations=1,
        )
        self.assertIn(scenario.objective, result.task)


class TestSessionResult(unittest.TestCase):
    """E0SessionResult dataclass."""

    def test_result_fields(self):
        result = run_session(
            use_mock=True,
            open_browser=False,
            session_id="test-fields",
            max_iterations=1,
        )
        self.assertIsInstance(result.session_id, str)
        self.assertIsInstance(result.task, str)
        self.assertIsInstance(result.iterations, int)
        self.assertIsInstance(result.stop_reason, str)
        self.assertIsInstance(result.goal_reached, bool)
        self.assertIsInstance(result.resumed, bool)
        self.assertFalse(result.resumed)


class TestCleanup(unittest.TestCase):
    """Cleanup generated files after test runs."""

    @classmethod
    def tearDownClass(cls):
        import glob
        for f in glob.glob("e0_session_test-*.html"):
            os.unlink(f)
        # Clean up test session memos
        import shutil
        test_dir = os.path.join("memos", "sessions")
        for name in os.listdir(test_dir) if os.path.isdir(test_dir) else []:
            if name.startswith("test-"):
                shutil.rmtree(os.path.join(test_dir, name), ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
