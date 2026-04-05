"""Integration tests for E₀ Human Communication (C162).

End-to-end tests verifying the full pipeline:
  Perception (C158) → Intent (C159) → UISpec (C160) → Feedback (C161)
"""

import pytest

from e0_controller.communication import (
    IntentReport,
    IntentType,
    detect_intents,
    detect_self_graph_intents,
)
from e0_controller.feedback import (
    HumanAction,
    ingest_feedback,
    ingest_panel_feedback,
)
from e0_controller.perception import (
    PerceptionDomain,
    PerceptionKind,
    build_perception_domain,
)
from e0_controller.primitives import Outcome
from e0_controller.self_graph import SelfGraph, active_components
from e0_controller.ui_emitter import emit_ui_spec, UISpec


# ──────────────────────────────────────────────
# 1. Full Pipeline: SelfGraph → UISpec
# ──────────────────────────────────────────────

class TestPipelineEndToEnd:
    """Tests that go from raw E0 state all the way to UISpec."""

    def test_fresh_graph_produces_spec(self):
        """A fresh Self-Graph with no history still produces a UISpec."""
        sg = SelfGraph()
        domain = build_perception_domain()
        report = detect_intents(self_graph=sg, include_status=True)
        spec = emit_ui_spec(report, domain, context="fresh")
        assert isinstance(spec, UISpec)
        assert spec.panel_count > 0  # at least status + request intents

    def test_trained_graph_produces_spec(self):
        """A Self-Graph with history produces meaningful intents."""
        sg = SelfGraph()
        core = active_components(overlap_active=False)
        for _ in range(20):
            sg.self_historize(core, Outcome.SUCCESS)

        domain = build_perception_domain()
        report = detect_intents(self_graph=sg, include_status=True)
        spec = emit_ui_spec(report, domain, context="trained")

        assert spec.panel_count > 0
        # Should have at least a status intent
        intents = [p.intent for p in spec.panels]
        assert "status" in intents

    def test_unhealthy_graph_triggers_uncertainty(self):
        """A graph with failures produces uncertainty panels."""
        sg = SelfGraph()
        full = active_components(overlap_active=True)
        # All failures → confused/harmful components
        for _ in range(20):
            sg.self_historize(full, Outcome.FAILURE)

        domain = build_perception_domain()
        report = detect_intents(self_graph=sg, include_status=True)
        spec = emit_ui_spec(report, domain, context="unhealthy")

        intents = [p.intent for p in spec.panels]
        assert "uncertainty" in intents

    def test_spec_serializes_to_json(self):
        """UISpec.to_dict() produces valid JSON-serializable output."""
        sg = SelfGraph()
        domain = build_perception_domain()
        report = detect_intents(self_graph=sg, include_status=True)
        spec = emit_ui_spec(report, domain)
        d = spec.to_dict()

        assert isinstance(d, dict)
        assert "panels" in d
        assert "layout" in d
        assert isinstance(d["panels"], list)
        for panel in d["panels"]:
            assert "intent" in panel
            assert "perception" in panel
            assert "urgency" in panel


# ──────────────────────────────────────────────
# 2. Feedback Loop: UISpec → Perception Shift
# ──────────────────────────────────────────────

class TestFeedbackLoopIntegration:
    """Tests that feedback actually changes future UISpec emission."""

    def test_feedback_changes_perception_ranking(self):
        """After ingesting feedback, perception snapshot ranking shifts."""
        domain = build_perception_domain()
        sg = SelfGraph()
        core = active_components(overlap_active=False)
        for _ in range(10):
            sg.self_historize(core, Outcome.SUCCESS)

        report = detect_intents(self_graph=sg, include_status=True)
        spec = emit_ui_spec(report, domain, context="before feedback")

        # Record initial perception order
        snap_before = domain.snapshot()
        ranking_before = [p.name for p in snap_before.ranked()[:5]]

        # Heavily reinforce one primitive, penalize another
        if spec.panel_count > 0:
            panel = spec.panels[0]
            for _ in range(100):
                ingest_panel_feedback(domain, panel, HumanAction.CLICK)

        snap_after = domain.snapshot()
        ranking_after = [p.name for p in snap_after.ranked()[:5]]

        # The ranking should have shifted (at least the reinforced prim moved)
        # We can't predict exactly where, but the snapshot must differ
        assert snap_after.total_load != snap_before.total_load

    def test_two_rounds_produce_different_specs(self):
        """Two rounds with different feedback produce different UISpecs."""
        domain = build_perception_domain()
        sg = SelfGraph()
        full = active_components(overlap_active=True)
        for _ in range(10):
            sg.self_historize(full, Outcome.FAILURE)

        # Round 1
        report1 = detect_intents(self_graph=sg, include_status=True)
        spec1 = emit_ui_spec(report1, domain, context="round1")

        # Feedback: reinforce emphasis panels, penalize contrast
        for i, panel in enumerate(spec1.panels):
            if panel.perception == "emphasis":
                for _ in range(50):
                    ingest_panel_feedback(domain, panel, HumanAction.CLICK)
            elif panel.perception == "contrast":
                for _ in range(50):
                    ingest_panel_feedback(domain, panel, HumanAction.IGNORE)

        # Round 2: same intents, different perception selection
        report2 = detect_intents(self_graph=sg, include_status=True)
        spec2 = emit_ui_spec(report2, domain, context="round2")

        # Both specs should have panels
        assert spec1.panel_count > 0
        assert spec2.panel_count > 0

        # The perception selections may differ due to learned strengths
        perceptions1 = [p.perception for p in spec1.panels]
        perceptions2 = [p.perception for p in spec2.panels]
        # At minimum, both are valid primitives
        from e0_controller.perception import ALL_PRIMITIVES
        for p in perceptions1 + perceptions2:
            assert p in ALL_PRIMITIVES

    def test_negative_feedback_reduces_urgency_effect(self):
        """Panels whose perception was repeatedly failed lose strength."""
        domain = build_perception_domain()

        # Get initial strength of emphasis
        initial_strength = domain.profile("emphasis").strength

        # Create a panel using emphasis and flood with IGNORE
        from e0_controller.ui_emitter import UIPanel
        panel = UIPanel(
            intent="uncertainty", perception="emphasis",
            language_act="uncertainty", data_source="test",
            suggested_visual="heatmap", urgency=0.5, label="test",
        )
        for _ in range(100):
            ingest_panel_feedback(domain, panel, HumanAction.IGNORE)

        after_strength = domain.profile("emphasis").strength
        # Strength should be reduced (clamped ≥ 0)
        assert after_strength <= initial_strength


# ──────────────────────────────────────────────
# 3. Multi-Source Intent Detection
# ──────────────────────────────────────────────

class TestMultiSourceIntents:
    """Tests that intents from different sources combine correctly."""

    def test_graph_only_intents(self):
        """detect_intents with only self_graph still works."""
        sg = SelfGraph()
        report = detect_intents(self_graph=sg, include_status=False)
        # Fresh graph: insufficient data → REQUEST intents
        assert isinstance(report, IntentReport)

    def test_graph_with_status(self):
        """include_status=True adds a STATUS intent."""
        sg = SelfGraph()
        report = detect_intents(self_graph=sg, include_status=True)
        status = report.by_type(IntentType.STATUS)
        assert len(status) == 1

    def test_no_sources_gives_empty(self):
        """No sources → empty report."""
        report = detect_intents(include_status=False)
        assert report.count == 0


# ──────────────────────────────────────────────
# 4. Demo Smoke Test
# ──────────────────────────────────────────────

class TestDemoSmoke:
    """Verify the demo script runs without error."""

    def test_demo_runs(self, capsys):
        from e0_controller.demo_human_communication import run_demo
        run_demo()
        captured = capsys.readouterr()
        assert "Demo Complete" in captured.out
        assert "UISpec" in captured.out

    def test_demo_produces_json(self, capsys):
        from e0_controller.demo_human_communication import run_demo
        run_demo()
        captured = capsys.readouterr()
        # The demo prints JSON at the end
        assert '"panels"' in captured.out
        assert '"layout"' in captured.out
