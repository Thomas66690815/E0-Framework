"""
E₀ LLM Context Enrichment — Unit Tests
========================================
Tests for:
  P1  Canon-Essence in SYSTEM_PROMPT
  P2  Curvature-aware MemOS summary
  P3  Override confidence & psi_phase in overlay summary
  P3b Evidence block: override count in reflection
"""

from __future__ import annotations

import json
import math
import unittest
from typing import List

from e0_controller.llm_adapter import SYSTEM_PROMPT
from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller
from e0_controller.memory_os import E0MemoryOS


# ──────────────────────────────────────────────
# P1: Canon-Essence in SYSTEM_PROMPT
# ──────────────────────────────────────────────

class TestCanonEssence(unittest.TestCase):
    """Verify SYSTEM_PROMPT contains key E₀ semantic concepts."""

    def test_contains_delta_explanation(self):
        self.assertIn("Δ (difference)", SYSTEM_PROMPT)

    def test_contains_tension(self):
        self.assertIn("Tension S", SYSTEM_PROMPT)

    def test_contains_coherence(self):
        self.assertIn("Coherence C = exp(−S)", SYSTEM_PROMPT)

    def test_contains_transition_field(self):
        self.assertIn("Transition field v", SYSTEM_PROMPT)

    def test_contains_connection(self):
        self.assertIn("Connection ω", SYSTEM_PROMPT)

    def test_contains_path_phase(self):
        self.assertIn("Path phase Θ", SYSTEM_PROMPT)

    def test_contains_amplitude(self):
        self.assertIn("Path amplitude Ψ", SYSTEM_PROMPT)

    def test_contains_intensity(self):
        self.assertIn("Intensity I = |Ψ|²", SYSTEM_PROMPT)

    def test_contains_M_H(self):
        self.assertIn("M_H", SYSTEM_PROMPT)
        self.assertIn("1/(1+κ)", SYSTEM_PROMPT)

    def test_contains_curvature_modulation(self):
        self.assertIn("curvature_modulation", SYSTEM_PROMPT)

    def test_contains_historization(self):
        self.assertIn("H (historization)", SYSTEM_PROMPT)

    def test_contains_resistance(self):
        self.assertIn("R (resistance)", SYSTEM_PROMPT)

    def test_json_instruction(self):
        self.assertIn("JSON format requested", SYSTEM_PROMPT)

    def test_no_markdown_instruction(self):
        self.assertIn("No markdown", SYSTEM_PROMPT)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _make_triangle_landscape(curvature_modulation: bool = False) -> Landscape:
    """A → B → C with asymmetric edges for non-zero ω."""
    L = Landscape()
    L.curvature_modulation = curvature_modulation
    for s, t in [("A", "B"), ("B", "C"), ("C", "A")]:
        L.add_edge(s, t, delta=5.0, resistance=0.1)
        L.add_edge(t, s, delta=0.1, resistance=0.9)
    return L


def _make_context(landscape: Landscape, current: str = "A"):
    """Build a minimal MemOSContext + MemOS for summarize_for_llm."""
    import tempfile
    from datetime import datetime, timezone
    from e0_controller.memory_os import MemOSContext
    tmpdir = tempfile.mkdtemp()
    memos = E0MemoryOS(base_dir=tmpdir)
    now = datetime.now(timezone.utc).isoformat()
    ctx = MemOSContext(
        session_id="test",
        created=now,
        updated=now,
        canon_refs=[],
        landscape={},          # not used when we pass landscape explicitly
        historization={
            "tau": 0,
            "success_traces": {},
            "failure_traces": {},
        },
        runtime={
            "recent_states": [],
            "last_escalation_type": "none",
            "controller_params": {"hybrid_mode": "greedy"},
        },
    )
    return memos, ctx


# ──────────────────────────────────────────────
# P2: Curvature-aware MemOS summary
# ──────────────────────────────────────────────

class TestSummaryCurvatureOff(unittest.TestCase):
    """When curvature_modulation=False, no M_H in neighbors."""

    def setUp(self):
        self.L = _make_triangle_landscape(curvature_modulation=False)
        self.memos, self.ctx = _make_context(self.L, "A")

    def test_no_M_H_key(self):
        summary = self.memos.summarize_for_llm(self.ctx, "A", self.L)
        for n, info in summary["admissible_neighbors"].items():
            self.assertNotIn("M_H", info)

    def test_no_curvature_modulation_in_runtime(self):
        summary = self.memos.summarize_for_llm(self.ctx, "A", self.L)
        self.assertNotIn("curvature_modulation", summary["runtime"])


class TestSummaryCurvatureOn(unittest.TestCase):
    """When curvature_modulation=True, M_H appears per neighbor."""

    def setUp(self):
        self.L = _make_triangle_landscape(curvature_modulation=True)
        self.memos, self.ctx = _make_context(self.L, "A")

    def test_M_H_present(self):
        summary = self.memos.summarize_for_llm(self.ctx, "A", self.L)
        for n, info in summary["admissible_neighbors"].items():
            self.assertIn("M_H", info)
            self.assertGreater(info["M_H"], 0.0)
            self.assertLessEqual(info["M_H"], 1.0)

    def test_curvature_modulation_in_runtime(self):
        summary = self.memos.summarize_for_llm(self.ctx, "A", self.L)
        self.assertTrue(summary["runtime"].get("curvature_modulation"))


# ──────────────────────────────────────────────
# P3: Override confidence & psi_phase in overlay
# ──────────────────────────────────────────────

class TestOverlaySummaryFields(unittest.TestCase):
    """Overlay summary includes override_confidence."""

    def _build_overlay(self):
        """Run _build_overlay_summary with a real controller."""
        L = _make_triangle_landscape()
        ctrl = E0Controller(
            landscape=L,
            execute_fn=lambda x, y: Outcome.SUCCESS,
            hybrid_mode="amplitude_on_disagree",
            hybrid_horizon=2,
            hybrid_goals={"C"},
        )
        import tempfile
        tmpdir = tempfile.mkdtemp()
        memos = E0MemoryOS(base_dir=tmpdir)
        return memos._build_overlay_summary(ctrl, "A")

    def test_override_confidence_present(self):
        result = self._build_overlay()
        if result is not None:
            self.assertIn("override_confidence", result)
            self.assertIsInstance(result["override_confidence"], float)

    def test_psi_phase_for_multipath(self):
        """Multi-path actions should have psi_phase."""
        result = self._build_overlay()
        if result is None:
            self.skipTest("No overlay produced for this graph")
        for action, info in result["actions"].items():
            if info["path_count"] > 1:
                self.assertIn("psi_phase", info)


# ──────────────────────────────────────────────
# P3b: Evidence block with override count
# ──────────────────────────────────────────────

class TestEvidenceBlockOverrides(unittest.TestCase):
    """_build_evidence_block includes override count when present."""

    def _make_eval(self, **run_kwargs):
        from e0_controller.evaluation import RunEvaluation, ScenarioEvaluation
        defaults = dict(
            goal_reached=True, steps=10, escalations=1, revisits=2,
            repeated_cycles=0, progress_ratio=0.8, avg_tension=0.5,
            total_tension=5.0, goal_reach_efficiency=0.5, loop_penalty=0.1,
            step_success_rate=0.9, rating="B",
            r_coh_avg=0.8, r_coh_min=0.6, r_coh_max=1.0,
            theta_consistency=0.9, amplitude_drift=0.1,
        )
        defaults.update(run_kwargs)
        run = RunEvaluation(**defaults)
        return ScenarioEvaluation(
            scenario_id="test", domain="test", graph_score=0.8,
            run_evaluation=run, semantic_evaluation=None,
            hard_failure=None, overall_score=0.7,
        )

    def test_override_count_included(self):
        from e0_controller.reflection import _build_evidence_block
        # RunEvaluation doesn't have override_count, so we monkey-patch
        ev = self._make_eval()
        ev.run_evaluation.override_count = 3  # type: ignore[attr-defined]
        evidence = _build_evidence_block(ev)
        self.assertIn("Overrides: 3", evidence)

    def test_no_override_count_when_zero(self):
        from e0_controller.reflection import _build_evidence_block
        ev = self._make_eval()
        ev.run_evaluation.override_count = 0  # type: ignore[attr-defined]
        evidence = _build_evidence_block(ev)
        self.assertNotIn("Overrides:", evidence)

    def test_no_override_count_attr(self):
        """When override_count is absent, no crash."""
        from e0_controller.reflection import _build_evidence_block
        ev = self._make_eval()
        evidence = _build_evidence_block(ev)
        self.assertNotIn("Overrides:", evidence)


if __name__ == "__main__":
    unittest.main()
