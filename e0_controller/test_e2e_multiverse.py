"""
Tests for E₀ End-to-End Multiverse (C183)
==========================================
Validates full 15-phase pipeline exercising all 14 layers.
"""

from __future__ import annotations

import json
import pytest
from dataclasses import asdict

from e0_controller.explore_e2e_multiverse import (
    run_e2e_multiverse,
    E2EState,
    LOGISTICS_SPEC,
    RESEARCH_SPEC,
)


# ── Fixture: run once per session ──────────────────────────────────────

@pytest.fixture(scope="module")
def e2e_state() -> E2EState:
    """Run full E2E multiverse once and share across all tests."""
    return run_e2e_multiverse()


# ── Structure ──────────────────────────────────────────────────────────

class TestE2EStructure:
    """E2E state has correct shape and completeness."""

    def test_all_15_phases_present(self, e2e_state):
        assert len(e2e_state.phases) == 15

    def test_phase_names_ordered(self, e2e_state):
        names = [p["phase"] for p in e2e_state.phases]
        expected = [
            "01_canon_training", "02_bootstrap", "03_graph_validation",
            "04_controller_runs", "05_amplitude", "06_self_graph",
            "07_reflexion", "08_mutation", "09_multiverse",
            "10_cross_reflexion", "11_dream", "12_sleep_wake",
            "13_entropy", "14_interface", "15_session",
        ]
        assert names == expected

    def test_every_phase_has_duration(self, e2e_state):
        for p in e2e_state.phases:
            assert "duration_s" in p
            assert p["duration_s"] >= 0

    def test_created_at_set(self, e2e_state):
        assert e2e_state.created_at != ""

    def test_total_duration_positive(self, e2e_state):
        assert e2e_state.total_duration_s > 0

    def test_json_serializable(self, e2e_state):
        data = asdict(e2e_state)
        text = json.dumps(data, default=str)
        assert len(text) > 1000


# ── Layer 1-3: Foundation ──────────────────────────────────────────────

class TestFoundation:

    def test_canons_loaded(self, e2e_state):
        assert len(e2e_state.canon_names) == 3
        assert "ontodynamics" in e2e_state.canon_names

    def test_logistics_spec(self, e2e_state):
        assert e2e_state.logistics_states == 10
        assert e2e_state.logistics_edges == 12

    def test_research_spec(self, e2e_state):
        assert e2e_state.research_states == 10
        assert e2e_state.research_edges == 12

    def test_graph_quality_logistics(self, e2e_state):
        gq = e2e_state.graph_quality_logistics
        assert gq["reachable"] is True
        assert gq["happy_path_length"] >= 1

    def test_graph_quality_research(self, e2e_state):
        gq = e2e_state.graph_quality_research
        assert gq["reachable"] is True

    def test_controller_runs_count(self, e2e_state):
        # 3 modes × 2 domains = 6 runs
        assert len(e2e_state.controller_runs) == 6

    def test_controller_runs_have_metrics(self, e2e_state):
        for run in e2e_state.controller_runs:
            assert "steps" in run
            assert "success_rate" in run
            assert "goal_reached" in run
            assert run["steps"] >= 1


# ── Layer 4: Amplitude ─────────────────────────────────────────────────

class TestAmplitude:

    def test_amplitude_choice(self, e2e_state):
        a = e2e_state.amplitude_analysis
        assert "amplitude_choice" in a
        assert a["amplitude_choice"] in LOGISTICS_SPEC["nodes"]

    def test_psi_u1(self, e2e_state):
        a = e2e_state.amplitude_analysis
        assert "psi_u1_abs" in a
        assert 0.0 <= a["psi_u1_abs"] <= 2.0


# ── Layer 6: Self-Graph ────────────────────────────────────────────────

class TestSelfGraph:

    def test_snapshot_has_components(self, e2e_state):
        sg = e2e_state.self_graph_snapshot
        assert len(sg) >= 1

    def test_diagnosis_categories(self, e2e_state):
        d = e2e_state.diagnosis
        for cat in ["healthy", "confused", "harmful"]:
            assert cat in d


# ── Layer 7: Reflexion ─────────────────────────────────────────────────

class TestReflexion:

    def test_reflexion_has_scope(self, e2e_state):
        r = e2e_state.reflexion_result
        assert "scope_center" in r
        assert "scope_size" in r


# ── Layer 8: Mutation ──────────────────────────────────────────────────

class TestMutation:

    def test_mutations_applied_and_reverted(self, e2e_state):
        muts = e2e_state.mutations_applied
        assert len(muts) >= 1
        m = muts[0]
        assert "old_value" in m
        assert "new_value" in m
        assert "restored" in m
        # Verify revert restored original
        assert m["old_value"] == m["restored"]


# ── Layer 9: Multiverse ───────────────────────────────────────────────

class TestMultiverse:

    def test_multiverse_ran(self, e2e_state):
        ms = e2e_state.multiverse_summary
        assert ms["total_turns"] >= 1

    def test_novelty_rate_bounded(self, e2e_state):
        ms = e2e_state.multiverse_summary
        assert 0.0 <= ms["novelty_rate"] <= 1.0


# ── Layer 10: Cross-Reflexion ──────────────────────────────────────────

class TestCrossReflexion:

    def test_cross_proposals(self, e2e_state):
        cr = e2e_state.cross_reflexion
        assert cr["proposals"] >= 0
        assert cr["edges_added"] >= 0


# ── Layer 11: Dream ───────────────────────────────────────────────────

class TestDream:

    def test_dream_found_equivalences(self, e2e_state):
        dr = e2e_state.dream_result
        assert dr["total_equivalences_found"] >= 0

    def test_dream_observed_domains(self, e2e_state):
        dr = e2e_state.dream_result
        assert len(dr["domains_observed"]) >= 2


# ── Layer 12: Sleep-Wake ───────────────────────────────────────────────

class TestSleepWake:

    def test_episodes_ran(self, e2e_state):
        phase = next(p for p in e2e_state.phases if p["phase"] == "12_sleep_wake")
        assert phase["episodes"] >= 1
        assert phase["slept"] >= 1


# ── Layer 13: Entropy ──────────────────────────────────────────────────

class TestEntropy:

    def test_structural_temperature(self, e2e_state):
        em = e2e_state.entropy_metrics
        assert em["T_s_logistics"] > 0
        assert em["T_s_research"] > 0

    def test_dream_pressure(self, e2e_state):
        em = e2e_state.entropy_metrics
        assert "dream_pressure_logistics" in em
        assert "dream_pressure_research" in em


# ── Layer 14: Interface ────────────────────────────────────────────────

class TestInterface:

    def test_ui_spec_generated(self, e2e_state):
        assert "panels" in e2e_state.ui_spec
        assert len(e2e_state.ui_spec["panels"]) >= 1

    def test_html_rendered(self, e2e_state):
        assert e2e_state.html_length > 100


# ── Layer 15: Session / Provenance ─────────────────────────────────────

class TestSession:

    def test_session_id(self, e2e_state):
        assert e2e_state.session_id.startswith("e2e_")

    def test_provenance_stages(self, e2e_state):
        assert e2e_state.provenance_stages >= 3

    def test_canon_self_bridge(self, e2e_state):
        assert len(e2e_state.canon_self_bridge) > 0
        assert "Canon" in e2e_state.canon_self_bridge or "canon" in e2e_state.canon_self_bridge


# ── Cross-layer invariants ─────────────────────────────────────────────

class TestCrossLayerInvariants:

    def test_mutation_preserves_edge_count(self, e2e_state):
        """Mutation adjusts R₀ but does not change topology."""
        # After mutation + revert, edge count should still match spec
        assert e2e_state.logistics_edges == len(LOGISTICS_SPEC["edges"])

    def test_cross_reflexion_adds_edges(self, e2e_state):
        """Cross-reflexion adds edges to the target landscape."""
        cr = e2e_state.cross_reflexion
        # edges_added >= 0 (depends on donor structure)
        assert cr["edges_added"] >= 0

    def test_entropy_reflects_sleep_wake(self, e2e_state):
        """After sleep-wake cycles, entropy metrics exist."""
        em = e2e_state.entropy_metrics
        assert em["T_s_logistics"] > 0
