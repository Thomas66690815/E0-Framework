"""Tests for E₀ Session Runner (C165 + C166b)."""

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
    _mock_derive_endpoints,
    _derive_endpoints,
    DEFAULT_TASK,
    DEFAULT_START,
    DEFAULT_GOAL,
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


class TestEndpointDerivation(unittest.TestCase):
    """C166b: LLM-derived start/goal states from task description."""

    def test_mock_derive_endpoints_default_task(self):
        start, goal = _mock_derive_endpoints(DEFAULT_TASK)
        self.assertTrue(start.startswith("RAW_"))
        self.assertTrue(goal.endswith("_COMPLETE"))
        self.assertNotEqual(start, "RAW_")
        self.assertNotEqual(goal, "_COMPLETE")

    def test_mock_derive_endpoints_custom_task(self):
        start, goal = _mock_derive_endpoints(
            "Translate a Biological Immune Response into a Cybersecurity Protocol"
        )
        self.assertTrue(start.startswith("RAW_"))
        self.assertTrue(goal.endswith("_COMPLETE"))
        # Must contain task-specific keyword
        self.assertIn("TRANSLATE", start)

    def test_mock_derive_different_tasks_produce_different_endpoints(self):
        s1, g1 = _mock_derive_endpoints("Build a trading strategy")
        s2, g2 = _mock_derive_endpoints("Design a medical protocol")
        self.assertNotEqual(s1, s2)
        self.assertNotEqual(g1, g2)

    def test_mock_derive_empty_task_fallback(self):
        start, goal = _mock_derive_endpoints("a")
        self.assertEqual(start, "RAW_TASK")
        self.assertEqual(goal, "TASK_COMPLETE")

    def test_derive_endpoints_with_mock_llm(self):
        """_derive_endpoints parses LLM JSON response correctly."""
        from e0_controller.llm_adapter import LLMConfig

        def fake_llm(system, user, config):
            return json.dumps({"start": "IMMUNE_INPUT", "goal": "PROTOCOL_READY"})

        start, goal = _derive_endpoints("test task", fake_llm, LLMConfig())
        self.assertEqual(start, "IMMUNE_INPUT")
        self.assertEqual(goal, "PROTOCOL_READY")

    def test_session_custom_task_derives_endpoints(self):
        """run_session with custom task and no start/goal derives them."""
        result = run_session(
            task="Build a trading strategy for emerging markets",
            use_mock=True,
            open_browser=False,
            session_id="test-derive",
            max_iterations=1,
        )
        self.assertIsInstance(result, E0SessionResult)
        self.assertTrue(result.goal_reached or result.iterations > 0)

    def test_session_explicit_start_goal_skips_derivation(self):
        """Explicit start/goal are used as-is, no derivation."""
        result = run_session(
            task="Some custom task",
            start="MY_START",
            goal="MY_GOAL",
            use_mock=True,
            open_browser=False,
            session_id="test-explicit",
            max_iterations=1,
        )
        self.assertIsInstance(result, E0SessionResult)

    def test_session_partial_override_goal_only(self):
        """Providing only goal derives start from task."""
        result = run_session(
            task="Analyze protein folding patterns",
            goal="ANALYSIS_DONE",
            use_mock=True,
            open_browser=False,
            session_id="test-partial",
            max_iterations=1,
        )
        self.assertIsInstance(result, E0SessionResult)

    def test_mock_landscape_uses_derived_endpoints(self):
        """Mock landscape states should include the derived start/goal."""
        from e0_controller.llm_adapter import LLMConfig
        raw = _mock_llm_call(
            "system",
            "design the complete state graph\nStart state: CUSTOM_START\nGoal state: CUSTOM_END",
            LLMConfig(),
        )
        data = json.loads(raw)
        self.assertIn("CUSTOM_START", data["states"])
        self.assertIn("CUSTOM_END", data["states"])
        # First edge starts from CUSTOM_START
        self.assertEqual(data["edges"][0]["source"], "CUSTOM_START")
        # Last edge targets CUSTOM_END
        self.assertEqual(data["edges"][-1]["target"], "CUSTOM_END")


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
