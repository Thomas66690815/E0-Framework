"""Tests for E₀ Visual Pretraining + Learnable Rendering (C164)."""

import json
import pytest
from pathlib import Path

from e0_controller.perception import (
    ALL_PRIMITIVES,
    RENDERING_PRIMITIVES,
    VISUAL_PRIMITIVES,
    LANGUAGE_PRIMITIVES,
    PerceptionDomain,
    PerceptionKind,
    build_perception_domain,
    primitive_kind,
)
from e0_controller.primitives import Edge, Outcome
from e0_controller.communication import detect_intents
from e0_controller.ui_emitter import emit_ui_spec, UISpec
from e0_controller.feedback import (
    HumanAction,
    ingest_panel_feedback,
    ingest_feedback,
)
from e0_controller.visual_pretraining import (
    PretrainingResult,
    RenderingEval,
    mock_eval_call,
    run_pretraining,
    score_to_outcome,
)


# ──────────────────────────────────────────────
# 1. Rendering Primitives in Perception Domain
# ──────────────────────────────────────────────

class TestRenderingPrimitives:
    def test_rendering_primitives_exist(self):
        assert len(RENDERING_PRIMITIVES) == 7
        assert "heatmap" in RENDERING_PRIMITIVES
        assert "tree" in RENDERING_PRIMITIVES
        assert "text" in RENDERING_PRIMITIVES

    def test_all_primitives_includes_rendering(self):
        assert len(ALL_PRIMITIVES) == 22  # 10 + 5 + 7
        for rp in RENDERING_PRIMITIVES:
            assert rp in ALL_PRIMITIVES

    def test_primitive_kind_rendering(self):
        for rp in RENDERING_PRIMITIVES:
            assert primitive_kind(rp) == PerceptionKind.RENDERING

    def test_primitive_kind_still_works(self):
        assert primitive_kind("emphasis") == PerceptionKind.VISUAL
        assert primitive_kind("assertion") == PerceptionKind.LANGUAGE

    def test_domain_has_rendering(self):
        domain = build_perception_domain()
        assert domain.has_rendering
        assert len(domain.rendering_primitives) == 7

    def test_domain_rendering_edges_exist(self):
        domain = build_perception_domain()
        # Key edges from _DEFAULT_EDGES
        assert domain.landscape.has_edge("emphasis", "heatmap")
        assert domain.landscape.has_edge("hierarchy", "tree")
        assert domain.landscape.has_edge("sequence", "timeline")
        assert domain.landscape.has_edge("label", "text")
        assert domain.landscape.has_edge("grouping", "dashboard")


# ──────────────────────────────────────────────
# 2. suggest_rendering()
# ──────────────────────────────────────────────

class TestSuggestRendering:
    def test_emphasis_returns_rendering(self):
        domain = build_perception_domain()
        rend = domain.suggest_rendering("emphasis")
        assert rend in RENDERING_PRIMITIVES

    def test_hierarchy_prefers_tree(self):
        """hierarchy→tree has highest initial_U, should win cold-start."""
        domain = build_perception_domain()
        rend = domain.suggest_rendering("hierarchy")
        assert rend == "tree"

    def test_sequence_prefers_timeline(self):
        domain = build_perception_domain()
        rend = domain.suggest_rendering("sequence")
        assert rend == "timeline"

    def test_label_prefers_text(self):
        domain = build_perception_domain()
        rend = domain.suggest_rendering("label")
        assert rend == "text"

    def test_no_rendering_edge_falls_back_to_text(self):
        domain = build_perception_domain()
        # "assertion" is a language primitive with no rendering edges
        rend = domain.suggest_rendering("assertion")
        assert rend == "text"

    def test_rendering_shifts_with_feedback(self):
        """After repeated FAILURE on one rendering, another should win."""
        domain = build_perception_domain()
        hist = domain.landscape.historization
        # Poison emphasis→heatmap with failures
        edge_hm = Edge("emphasis", "heatmap")
        for _ in range(20):
            hist.update(edge_hm, Outcome.FAILURE)
        # emphasis should now prefer highlight or bar
        rend = domain.suggest_rendering("emphasis")
        assert rend != "heatmap"
        assert rend in RENDERING_PRIMITIVES


# ──────────────────────────────────────────────
# 3. UISpec now uses learnable rendering
# ──────────────────────────────────────────────

class TestLearnableUISpec:
    def test_emit_uses_suggest_rendering(self):
        """UISpec panels should use domain.suggest_rendering()."""
        from e0_controller.self_graph import SelfGraph, active_components
        sg = SelfGraph()
        core = active_components(overlap_active=False)
        for _ in range(10):
            sg.self_historize(core, Outcome.SUCCESS)

        domain = build_perception_domain()
        report = detect_intents(self_graph=sg, include_status=True)
        spec = emit_ui_spec(report, domain, context="test")

        # Every suggested_visual must be a valid rendering primitive
        for panel in spec.panels:
            assert panel.suggested_visual in RENDERING_PRIMITIVES

    def test_emit_without_domain_uses_static_fallback(self):
        """Without a domain, UISpec falls back to static mapping."""
        from e0_controller.self_graph import SelfGraph, active_components
        sg = SelfGraph()
        core = active_components(overlap_active=False)
        for _ in range(10):
            sg.self_historize(core, Outcome.SUCCESS)

        report = detect_intents(self_graph=sg, include_status=True)
        spec = emit_ui_spec(report, context="test")
        # Should still work, panels have suggested_visual
        assert spec.panel_count > 0
        for panel in spec.panels:
            assert panel.suggested_visual in RENDERING_PRIMITIVES


# ──────────────────────────────────────────────
# 4. Feedback targets rendering edge
# ──────────────────────────────────────────────

class TestRenderingFeedback:
    def test_feedback_historizes_rendering_edge(self):
        domain = build_perception_domain()
        hist = domain.landscape.historization
        edge = Edge("emphasis", "heatmap")

        q_before = hist.trace_quality(edge)
        from e0_controller.ui_emitter import UIPanel
        test_panel = UIPanel(
            intent="uncertainty",
            perception="emphasis",
            language_act="uncertainty",
            data_source="test",
            suggested_visual="heatmap",
            urgency=0.8,
            label="test",
            evidence={},
        )
        # Multiple successes to overcome initial bootstrapper traces
        for _ in range(10):
            ingest_panel_feedback(domain, test_panel, HumanAction.CLICK)
        q_after = hist.trace_quality(edge)
        assert q_after > q_before

    def test_feedback_distinguishes_rendering(self):
        """Used rendering gets double signal, alternatives get single."""
        domain = build_perception_domain()
        hist = domain.landscape.historization

        edge_used = Edge("emphasis", "heatmap")
        edge_alt = Edge("emphasis", "highlight")

        from e0_controller.ui_emitter import UIPanel
        panel = UIPanel(
            intent="uncertainty",
            perception="emphasis",
            language_act="uncertainty",
            data_source="test",
            suggested_visual="heatmap",  # heatmap was used
            urgency=0.8,
            label="test",
            evidence={},
        )
        # Run enough feedback to build clear signal
        for _ in range(15):
            ingest_panel_feedback(domain, panel, HumanAction.CLICK)

        q_used = hist.trace_quality(edge_used)
        q_alt = hist.trace_quality(edge_alt)

        # Used rendering should have higher quality (double signal)
        assert q_used > q_alt


# ──────────────────────────────────────────────
# 5. Score → Outcome
# ──────────────────────────────────────────────

class TestScoreMapping:
    def test_low_scores_fail(self):
        for s in range(0, 5):
            assert score_to_outcome(s) == Outcome.FAILURE

    def test_high_scores_succeed(self):
        for s in range(5, 11):
            assert score_to_outcome(s) == Outcome.SUCCESS


# ──────────────────────────────────────────────
# 6. Pretraining Loop
# ──────────────────────────────────────────────

class TestPretraining:
    def test_mock_pretraining_runs(self):
        domain = build_perception_domain()
        result = run_pretraining(
            domain, mock_eval_call, rounds=1,
            intents=["uncertainty", "status"],
        )
        assert result.total_evals > 0
        assert result.rounds == 1
        assert 0.0 <= result.success_rate <= 1.0

    def test_pretraining_changes_traces(self):
        domain = build_perception_domain()
        hist = domain.landscape.historization
        edge = Edge("emphasis", "heatmap")
        q_before = hist.trace_quality(edge)

        run_pretraining(
            domain, mock_eval_call, rounds=3,
            intents=["uncertainty", "status", "anomaly"],
        )
        q_after = hist.trace_quality(edge)
        # Mock gives emphasis→heatmap score 8 (SUCCESS)
        # Quality should improve
        assert q_after > q_before

    def test_pretraining_result_summary(self):
        domain = build_perception_domain()
        result = run_pretraining(
            domain, mock_eval_call, rounds=1,
            intents=["status"],
        )
        summary = result.summary()
        assert "Pretraining" in summary
        assert "Success rate" in summary

    def test_mock_eval_scores(self):
        """Mock produces known scores for known pairs."""
        from e0_controller.llm_adapter import LLMConfig
        config = LLMConfig()
        raw = mock_eval_call(
            "",
            "Perception: emphasis\nRendering widget: highlight\n",
            config,
        )
        data = json.loads(raw)
        assert data["score"] == 9  # from _MOCK_SCORES


# ──────────────────────────────────────────────
# 7. Save / Load Persistence
# ──────────────────────────────────────────────

class TestPersistence:
    def test_save_and_load(self, tmp_path):
        domain = build_perception_domain()
        # Train a bit
        run_pretraining(
            domain, mock_eval_call, rounds=1,
            intents=["uncertainty"],
        )
        memo_path = tmp_path / "perception.json"
        domain.save_state(memo_path)

        assert memo_path.exists()
        loaded = PerceptionDomain.from_saved(memo_path)
        assert loaded.has_rendering
        assert len(loaded.primitives) == len(domain.primitives)

    def test_saved_traces_preserved(self, tmp_path):
        domain = build_perception_domain()
        # Make a clear signal
        edge = Edge("emphasis", "heatmap")
        for _ in range(10):
            domain.landscape.historization.update(edge, Outcome.SUCCESS)

        q_before = domain.landscape.historization.trace_quality(edge)

        memo_path = tmp_path / "perception.json"
        domain.save_state(memo_path)
        loaded = PerceptionDomain.from_saved(memo_path)

        q_after = loaded.landscape.historization.trace_quality(
            Edge("emphasis", "heatmap")
        )
        # Quality should be preserved (positive)
        assert q_after > 0
        assert abs(q_after - q_before) < 0.1  # close match

    def test_memo_is_valid_json(self, tmp_path):
        domain = build_perception_domain()
        memo_path = tmp_path / "test.json"
        domain.save_state(memo_path)

        data = json.loads(memo_path.read_text(encoding="utf-8"))
        assert data["version"] == "1.0"
        assert "spec" in data
        assert "saved_at" in data
        assert len(data["spec"]["nodes"]) == 22
        assert len(data["spec"]["edges"]) > 0

    def test_load_nonexistent_raises(self):
        with pytest.raises(FileNotFoundError):
            PerceptionDomain.from_saved("nonexistent.json")

    def test_saved_suggest_rendering_matches(self, tmp_path):
        """Loaded domain gives same rendering suggestion as original."""
        domain = build_perception_domain()
        # Strong signal: hierarchy → tree
        edge = Edge("hierarchy", "tree")
        for _ in range(15):
            domain.landscape.historization.update(edge, Outcome.SUCCESS)

        original_choice = domain.suggest_rendering("hierarchy")

        memo_path = tmp_path / "perception.json"
        domain.save_state(memo_path)
        loaded = PerceptionDomain.from_saved(memo_path)

        loaded_choice = loaded.suggest_rendering("hierarchy")
        assert loaded_choice == original_choice


# ──────────────────────────────────────────────
# 8. Integration: pretrain → emit → render
# ──────────────────────────────────────────────

class TestIntegration:
    def test_pretrained_domain_produces_spec(self):
        from e0_controller.self_graph import SelfGraph, active_components

        domain = build_perception_domain()
        run_pretraining(
            domain, mock_eval_call, rounds=2,
            intents=["uncertainty", "status"],
        )

        sg = SelfGraph()
        core = active_components(overlap_active=False)
        for _ in range(10):
            sg.self_historize(core, Outcome.SUCCESS)

        report = detect_intents(self_graph=sg, include_status=True)
        spec = emit_ui_spec(report, domain, context="pretrained test")

        assert spec.panel_count > 0
        for panel in spec.panels:
            assert panel.suggested_visual in RENDERING_PRIMITIVES

    def test_pretrained_domain_renders_html(self):
        from e0_controller.ui_renderer import render_html

        domain = build_perception_domain()
        run_pretraining(
            domain, mock_eval_call, rounds=1,
            intents=["status"],
        )

        report = detect_intents(include_status=True)
        spec = emit_ui_spec(report, domain, context="render test")
        html = render_html(spec)
        assert "<!DOCTYPE html>" in html

    def test_full_cycle_pretrain_emit_feedback_save(self, tmp_path):
        """Full cycle: pretrain → emit → feedback → save → reload."""
        from e0_controller.self_graph import SelfGraph, active_components

        domain = build_perception_domain()
        run_pretraining(domain, mock_eval_call, rounds=1,
                        intents=["uncertainty"])

        sg = SelfGraph()
        core = active_components(overlap_active=False)
        for _ in range(10):
            sg.self_historize(core, Outcome.SUCCESS)

        report = detect_intents(self_graph=sg, include_status=True)
        spec = emit_ui_spec(report, domain, context="cycle test")

        # Simulate user feedback
        actions = {i: HumanAction.CLICK for i in range(spec.panel_count)}
        result = ingest_feedback(domain, spec, actions)
        assert result.event_count > 0

        # Save
        memo = tmp_path / "pretrained.json"
        domain.save_state(memo)

        # Reload
        loaded = PerceptionDomain.from_saved(memo)
        assert loaded.has_rendering
        assert loaded.suggest_rendering("emphasis") in RENDERING_PRIMITIVES
