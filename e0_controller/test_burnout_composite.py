"""Tests for demo_burnout_composite — Domäne 3 (composite multi-perspective).

All tests use the mock LLM (no API calls).
"""

import unittest
from unittest.mock import patch

from e0_controller.demo_burnout_composite import (
    ALL_FRAGMENTS,
    BURNOUT_TASK,
    DEFAULT_START,
    DEFAULT_GOAL,
    ENVELOPE_GREEDY,
    ENVELOPE_HYBRID,
    FRAGMENT_OEKONOMISCH,
    FRAGMENT_PSYCHOLOGISCH,
    FRAGMENT_JOURNALISMUS,
    FRAGMENT_ERFAHRUNGSBERICHT,
    FRAGMENT_AUTOFIKTIONAL,
    composite_source_text,
    mock_llm_call,
    run_demo,
)
from e0_controller import (
    E0Envelope,
    HybridMode,
    TransportRegime,
    LLMConfig,
    E0LLMAdapter,
    LandscapeProposal,
    materialize_landscape,
    task_map_from_proposal,
    graph_quality,
)


# ── Fragment data tests ──────────────────────────────────────────────────

class TestFragments(unittest.TestCase):
    """Verify fragment data is present and well-formed."""

    def test_five_fragments_present(self):
        self.assertEqual(len(ALL_FRAGMENTS), 5)

    def test_fragment_keys(self):
        expected = {"oekonomisch", "psychologisch", "journalismus",
                    "erfahrungsbericht", "autofiktional"}
        self.assertEqual(set(ALL_FRAGMENTS.keys()), expected)

    def test_all_fragments_non_empty(self):
        for key, text in ALL_FRAGMENTS.items():
            self.assertGreater(len(text), 50, f"Fragment '{key}' too short")

    def test_composite_source_text_contains_all(self):
        src = composite_source_text()
        for key in ALL_FRAGMENTS:
            self.assertIn(key, src)

    def test_composite_source_text_separators(self):
        src = composite_source_text()
        self.assertEqual(src.count("── Perspektive:"), 5)

    def test_oekonomisch_contains_burnout_content(self):
        self.assertIn("Fehltage", FRAGMENT_OEKONOMISCH)
        self.assertIn("Produktivität", FRAGMENT_OEKONOMISCH)

    def test_psychologisch_contains_feedback_loop(self):
        self.assertIn("Rückkopplungskreislauf", FRAGMENT_PSYCHOLOGISCH)
        self.assertIn("bidirektional", FRAGMENT_PSYCHOLOGISCH)

    def test_journalismus_contains_sector_data(self):
        self.assertIn("45 Prozent", FRAGMENT_JOURNALISMUS)
        self.assertIn("Identität", FRAGMENT_JOURNALISMUS)

    def test_erfahrungsbericht_first_person(self):
        self.assertIn("Ich", FRAGMENT_ERFAHRUNGSBERICHT)
        self.assertIn("Verbindung", FRAGMENT_ERFAHRUNGSBERICHT)

    def test_autofiktional_core_pattern(self):
        self.assertIn("Mehr Fokus", FRAGMENT_AUTOFIKTIONAL)
        self.assertIn("Rückkopplung", FRAGMENT_AUTOFIKTIONAL)
        self.assertIn("destabilisiert", FRAGMENT_AUTOFIKTIONAL)


# ── Mock LLM landscape tests ────────────────────────────────────────────

class TestMockLandscape(unittest.TestCase):
    """Verify mock LLM produces valid landscape."""

    def setUp(self):
        self.adapter = E0LLMAdapter(call_fn=mock_llm_call)
        self.proposal = self.adapter.build_landscape(
            BURNOUT_TASK, DEFAULT_START, DEFAULT_GOAL,
        )

    def test_proposal_has_states(self):
        self.assertGreater(len(self.proposal.states), 5)

    def test_proposal_has_edges(self):
        self.assertGreater(len(self.proposal.edges), 8)

    def test_start_state_present(self):
        self.assertIn(DEFAULT_START, self.proposal.states)

    def test_goal_state_present(self):
        self.assertIn(DEFAULT_GOAL, self.proposal.states)

    def test_feedback_loop_states(self):
        """Mock should include mass trap candidate states."""
        self.assertIn("LOOP_UNRESOLVED", self.proposal.states)
        self.assertIn("REFRAMING_NEEDED", self.proposal.states)

    def test_materialize_produces_landscape(self):
        L = materialize_landscape(self.proposal)
        self.assertEqual(len(L.states), len(self.proposal.states))
        self.assertEqual(len(L.edges), len(self.proposal.edges))

    def test_graph_quality_ok(self):
        L = materialize_landscape(self.proposal)
        gq = graph_quality(L, DEFAULT_START, DEFAULT_GOAL)
        self.assertTrue(gq.ok())
        self.assertGreater(gq.score, 0.9)

    def test_task_map_from_proposal(self):
        tmap = task_map_from_proposal(self.proposal)
        self.assertEqual(len(tmap), len(self.proposal.edges))
        for key in tmap:
            self.assertIn("→", key)


# ── Envelope tests ───────────────────────────────────────────────────────

class TestEnvelopePresets(unittest.TestCase):
    """Verify envelope presets are correctly configured."""

    def test_greedy_envelope(self):
        self.assertEqual(ENVELOPE_GREEDY.mode, HybridMode.GREEDY)
        self.assertEqual(ENVELOPE_GREEDY.geometry, "simple")
        self.assertIn(DEFAULT_GOAL, ENVELOPE_GREEDY.goals)

    def test_hybrid_envelope(self):
        self.assertEqual(ENVELOPE_HYBRID.mode, HybridMode.AMPLITUDE_ON_DISAGREE)
        self.assertEqual(ENVELOPE_HYBRID.geometry, "goal_reaching")
        self.assertEqual(ENVELOPE_HYBRID.horizon, 5)
        self.assertIn(DEFAULT_GOAL, ENVELOPE_HYBRID.goals)

    def test_envelope_to_kwargs(self):
        kwargs = ENVELOPE_HYBRID.to_controller_kwargs()
        self.assertEqual(kwargs["hybrid_mode"], HybridMode.AMPLITUDE_ON_DISAGREE)
        self.assertEqual(kwargs["hybrid_geometry"], "goal_reaching")
        self.assertEqual(kwargs["hybrid_horizon"], 5)

    def test_envelope_serialization(self):
        d = ENVELOPE_GREEDY.to_dict()
        restored = E0Envelope.from_dict(d)
        self.assertEqual(restored, ENVELOPE_GREEDY)


# ── Full demo run tests (mock) ───────────────────────────────────────────

class TestDemoMockRun(unittest.TestCase):
    """Run full demo in mock mode and verify results."""

    @classmethod
    def setUpClass(cls):
        import io
        import contextlib
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            cls.result = run_demo(use_mock=True, use_hybrid=False)
        cls.output = f.getvalue()

    def test_result_has_keys(self):
        for key in ("envelope", "proposal", "landscape", "trace",
                     "evaluation", "result_log", "graph_quality"):
            self.assertIn(key, self.result)

    def test_goal_reached(self):
        trace = self.result["trace"]
        self.assertIn(DEFAULT_GOAL, trace.path)

    def test_no_loops(self):
        ev = self.result["evaluation"]
        self.assertEqual(ev.repeated_cycles, 0)

    def test_rating_a(self):
        ev = self.result["evaluation"]
        self.assertEqual(ev.rating, "A")

    def test_graph_quality_ok(self):
        gq = self.result["graph_quality"]
        self.assertTrue(gq.ok())

    def test_result_log_populated(self):
        self.assertGreater(len(self.result["result_log"]), 0)

    def test_output_contains_summary(self):
        self.assertIn("Domäne 3 complete", self.output)
        self.assertIn("REACHED", self.output)

    def test_all_transitions_executed(self):
        trace = self.result["trace"]
        log = self.result["result_log"]
        self.assertEqual(len(trace.steps), len(log))


class TestDemoMockHybridRun(unittest.TestCase):
    """Run demo in mock hybrid mode."""

    @classmethod
    def setUpClass(cls):
        import io
        import contextlib
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            cls.result = run_demo(use_mock=True, use_hybrid=True)

    def test_goal_reached(self):
        trace = self.result["trace"]
        self.assertIn(DEFAULT_GOAL, trace.path)

    def test_envelope_is_hybrid(self):
        self.assertEqual(
            self.result["envelope"].mode,
            HybridMode.AMPLITUDE_ON_DISAGREE,
        )

    def test_no_crash(self):
        """Hybrid mode completes without exception."""
        self.assertIsNotNone(self.result["trace"])


class TestDemoCustomEnvelope(unittest.TestCase):
    """Run with a custom envelope."""

    def test_custom_envelope_run(self):
        import io
        import contextlib
        env = E0Envelope(
            mode=HybridMode.GREEDY,
            geometry="simple",
            horizon=2,
            transport=TransportRegime.U1,
            goals=frozenset({DEFAULT_GOAL}),
            alpha=1.0,
        )
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            result = run_demo(use_mock=True, envelope=env)
        self.assertIn(DEFAULT_GOAL, result["trace"].path)


# ── Structural topology tests (mock) ────────────────────────────────────

class TestMockTopology(unittest.TestCase):
    """Verify mock landscape has expected structural properties."""

    def setUp(self):
        self.adapter = E0LLMAdapter(call_fn=mock_llm_call)
        self.proposal = self.adapter.build_landscape(
            BURNOUT_TASK, DEFAULT_START, DEFAULT_GOAL,
        )
        self.L = materialize_landscape(self.proposal)

    def test_feedback_loop_exists(self):
        """The recovery path should form a loop: LOOP_UNRESOLVED → REFRAMING → PHASE_MODEL."""
        neighbors_unresolved = self.L.admissible_neighbors("LOOP_UNRESOLVED")
        self.assertIn("REFRAMING_NEEDED", neighbors_unresolved)
        self.assertIn("PHASE_MODEL_BUILT", neighbors_unresolved)

    def test_reframing_leads_to_phase_model(self):
        neighbors = self.L.admissible_neighbors("REFRAMING_NEEDED")
        self.assertIn("PHASE_MODEL_BUILT", neighbors)

    def test_happy_path_exists(self):
        """Direct path from FEEDBACK_LOOP to PHASE_MODEL exists."""
        neighbors = self.L.admissible_neighbors("FEEDBACK_LOOP_DETECTED")
        self.assertIn("PHASE_MODEL_BUILT", neighbors)

    def test_recovery_path_has_different_tension(self):
        """Recovery and happy path have different tension profiles."""
        from e0_controller.tension import tension
        s_happy = tension(0.5, 0.8)    # FEEDBACK→PHASE_MODEL (Δ·R₀)
        s_loop = tension(0.3, 1.2)     # FEEDBACK→LOOP_UNRESOLVED
        # Both are valid paths; greedy picks lowest S_eff per step
        self.assertNotEqual(s_happy, s_loop)

    def test_goal_reachable_from_start(self):
        from e0_controller import goal_reachable
        self.assertTrue(goal_reachable(self.L, DEFAULT_START, DEFAULT_GOAL))


if __name__ == "__main__":
    unittest.main()
