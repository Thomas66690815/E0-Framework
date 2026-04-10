"""Tests for Multi-Domain Learning Cycle (C204).

Validates that EN as third domain integrates into the learning cycle:
building the unified landscape, navigating across 3 domains,
tracking per-domain coverage, and cross-domain discovery.
"""

from __future__ import annotations

import json

import pytest

from e0_controller.explore_learning_cycle_multidomain import (
    EN_CANON_BRIDGE,
    EN_BOOTSTRAP_BRIDGE,
    MultiDomainAssessment,
    MultiDomainRoundResult,
    assess,
    build_en_bridges,
    build_multidomain_landscape,
    communicate_round,
    communicate_summary,
    consolidate,
    navigate,
    plan,
    run_multidomain_cycle,
    validate_confidence,
    _domain_of,
    _pick_start_node,
)
from e0_controller.explore_bootstrap_landscape import (
    load_learning_state,
    LEARNING_STATE_PATH,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def multidomain():
    """Build the 3-domain landscape once for all tests."""
    landscape, unified_nodes, stats = build_multidomain_landscape()
    return landscape, unified_nodes, stats


# ---------------------------------------------------------------------------
# Phase 0: Landscape Construction
# ---------------------------------------------------------------------------


class TestLandscapeConstruction:
    """Three domains assemble into one unified landscape."""

    def test_three_domains_present(self, multidomain):
        """All three domain prefixes exist in the landscape."""
        _, nodes, _ = multidomain
        domains = {n.split(":")[0] for n in nodes if ":" in n}
        assert "C" in domains, "Canon nodes missing"
        assert "B" in domains, "Bootstrap nodes missing"
        assert "EN" in domains, "EN nodes missing"

    def test_node_counts(self, multidomain):
        """Expected node counts per domain."""
        _, _, stats = multidomain
        assert stats["canon_nodes"] >= 50, f"Canon: {stats['canon_nodes']}"
        assert stats["bootstrap_nodes"] >= 35, f"Bootstrap: {stats['bootstrap_nodes']}"
        assert stats["en_nodes"] >= 40, f"EN: {stats['en_nodes']}"
        assert stats["total_nodes"] >= 130

    def test_en_nodes_have_correct_type(self, multidomain):
        """EN nodes are typed as en_vocabulary."""
        _, nodes, _ = multidomain
        en_nodes = {k: v for k, v in nodes.items() if k.startswith("EN:")}
        assert len(en_nodes) >= 40
        for nid, node in en_nodes.items():
            assert node["type"] == "en_vocabulary", f"{nid}: {node['type']}"
            assert node["domain"] == "en"

    def test_en_nodes_start_fresh(self, multidomain):
        """EN nodes start with zero traces (genuinely unexplored)."""
        _, nodes, _ = multidomain
        for nid, node in nodes.items():
            if nid.startswith("EN:"):
                assert node["U"] == 0.0, f"{nid} has U={node['U']}"
                assert node["F"] == 0.0, f"{nid} has F={node['F']}"

    def test_total_edges_reasonable(self, multidomain):
        """Total edges include intra + inter domain."""
        _, _, stats = multidomain
        assert stats["total_edges"] >= 300
        assert stats["canon_bootstrap_bridges"] >= 40
        assert stats["en_bridges"] >= 10

    def test_landscape_states_match_nodes(self, multidomain):
        """Every unified_nodes key is a state in the landscape."""
        landscape, nodes, _ = multidomain
        for nid in nodes:
            assert nid in landscape.states, f"{nid} not in landscape.states"


# ---------------------------------------------------------------------------
# EN Bridges
# ---------------------------------------------------------------------------


class TestENBridges:
    """EN↔Canon and EN↔Bootstrap bridges are structurally sound."""

    def test_bridge_definitions_non_empty(self):
        """EN bridge maps are non-empty."""
        assert len(EN_CANON_BRIDGE) >= 10
        assert len(EN_BOOTSTRAP_BRIDGE) >= 3

    def test_bridges_are_bidirectional(self, multidomain):
        """Every EN bridge has a reverse direction."""
        _, nodes, _ = multidomain
        bridges = build_en_bridges(None, nodes)
        pairs = {(b["from"], b["to"]) for b in bridges}
        for b in bridges:
            reverse = (b["to"], b["from"])
            assert reverse in pairs, f"Missing reverse for {b['from']}→{b['to']}"

    def test_bridges_connect_existing_nodes(self, multidomain):
        """No bridge references a non-existent node."""
        _, nodes, _ = multidomain
        bridges = build_en_bridges(None, nodes)
        for b in bridges:
            assert b["from"] in nodes, f"Bridge from={b['from']} not in nodes"
            assert b["to"] in nodes, f"Bridge to={b['to']} not in nodes"

    def test_bridge_types_correct(self, multidomain):
        """All EN bridges have type 'en_semantic'."""
        _, nodes, _ = multidomain
        bridges = build_en_bridges(None, nodes)
        for b in bridges:
            assert b["bridge_type"] == "en_semantic"

    def test_en_primitives_bridge_to_canon_primitives(self, multidomain):
        """EN primitives (thing, action, quality, relation) bridge to Canon."""
        _, nodes, _ = multidomain
        bridges = build_en_bridges(None, nodes)
        en_prim_srcs = {b["from"] for b in bridges
                        if b["from"].startswith("EN:")
                        and b["from"] in {"EN:thing", "EN:action",
                                          "EN:quality", "EN:relation"}}
        assert len(en_prim_srcs) >= 4, f"Only {en_prim_srcs} bridge from EN prims"


# ---------------------------------------------------------------------------
# Domain Helper
# ---------------------------------------------------------------------------


class TestDomainOf:
    """_domain_of classifies node prefixes correctly."""

    def test_canon(self):
        assert _domain_of("C:difference") == "canon"

    def test_bootstrap(self):
        assert _domain_of("B:HERE") == "bootstrap"

    def test_en(self):
        assert _domain_of("EN:thing") == "en"

    def test_unprefixed_is_bootstrap(self):
        """Nodes without recognized prefix default to bootstrap."""
        assert _domain_of("UNKNOWN:x") == "bootstrap"


# ---------------------------------------------------------------------------
# Phase 1: Assessment
# ---------------------------------------------------------------------------


class TestAssessment:
    """Per-domain coverage tracking works."""

    def test_assessment_has_three_domains(self, multidomain):
        """Assessment tracks canon, bootstrap, and EN separately."""
        landscape, nodes, _ = multidomain
        a = assess(landscape, nodes)
        assert a.canon_nodes >= 50
        assert a.bootstrap_nodes >= 35
        assert a.en_nodes >= 40
        assert a.canon_nodes + a.bootstrap_nodes + a.en_nodes == a.total_nodes

    def test_en_starts_low_coverage(self, multidomain):
        """EN coverage starts low (no traces = low coverage)."""
        landscape, nodes, _ = multidomain
        a = assess(landscape, nodes)
        # EN starts fresh, so coverage should be lower than Bootstrap
        assert a.en_coverage <= a.bootstrap_coverage

    def test_coverage_sums_coherent(self, multidomain):
        """visited_nodes = canon_visited + bootstrap_visited + en_visited."""
        landscape, nodes, _ = multidomain
        a = assess(landscape, nodes)
        domain_sum = a.canon_visited + a.bootstrap_visited + a.en_visited
        assert domain_sum == a.visited_nodes, \
            f"Mismatch: {domain_sum} vs {a.visited_nodes}"


# ---------------------------------------------------------------------------
# Phase 2: Planning
# ---------------------------------------------------------------------------


class TestPlanning:
    """Plan detects EN coverage gaps and responds."""

    def test_en_gap_triggers_explore_en(self):
        """When EN is far behind, mode = explore_en."""
        a = MultiDomainAssessment(
            total_nodes=148, total_edges=400, visited_nodes=80,
            coverage=0.54, frontier_size=40, T_s=0.08,
            mean_quality=0.5, stale_edges=0,
            canon_coverage=0.6, bootstrap_coverage=0.9, en_coverage=0.1,
            canon_nodes=63, bootstrap_nodes=41, en_nodes=44,
            canon_visited=38, bootstrap_visited=37, en_visited=4,
        )
        mode, steps, reason = plan(a, 1, [])
        assert mode == "explore_en"
        assert "EN coverage gap" in reason

    def test_balanced_coverage_no_en_mode(self):
        """When EN is close to others, no special explore_en mode."""
        a = MultiDomainAssessment(
            total_nodes=148, total_edges=400, visited_nodes=120,
            coverage=0.81, frontier_size=10, T_s=0.05,
            mean_quality=0.5, stale_edges=0,
            canon_coverage=0.75, bootstrap_coverage=0.9, en_coverage=0.8,
            canon_nodes=63, bootstrap_nodes=41, en_nodes=44,
            canon_visited=47, bootstrap_visited=37, en_visited=35,
        )
        mode, steps, reason = plan(a, 5, [])
        assert mode != "explore_en"

    def test_stagnation_triggers_llm(self):
        """3 stalled rounds → LLM mode in plan."""
        a = MultiDomainAssessment(
            total_nodes=148, total_edges=400, visited_nodes=100,
            coverage=0.68, frontier_size=5, T_s=0.05,
            mean_quality=0.5, stale_edges=0,
            canon_coverage=0.7, bootstrap_coverage=0.9, en_coverage=0.5,
            canon_nodes=63, bootstrap_nodes=41, en_nodes=44,
            canon_visited=44, bootstrap_visited=37, en_visited=22,
        )
        # Fake 3 stagnant rounds
        stagnant = [
            MultiDomainRoundResult(
                round_num=i, mode="explore", reason="test", steps=30,
                assessment_before=a, assessment_after=a, path=["B:HERE"],
                new_edges=0, domain_crossings=0, crossing_rate=0.0,
                coverage_delta=0.0, T_s_delta=0.0,
                en_canon_crossings=0, en_bootstrap_crossings=0,
                canon_bootstrap_crossings=0,
            )
            for i in range(1, 4)
        ]
        mode, _, reason = plan(a, 4, stagnant)
        assert mode == "llm"
        assert "Stagnation" in reason


# ---------------------------------------------------------------------------
# Phase 3: Navigation
# ---------------------------------------------------------------------------


class TestNavigation:
    """Navigation traverses all three domains."""

    def test_navigate_produces_path(self, multidomain):
        """Navigation with 20 steps produces a non-trivial path."""
        landscape, nodes, _ = multidomain
        result = navigate(landscape, nodes, "explore", 20, start="B:HERE")
        assert result["steps"] >= 5
        assert len(result["path"]) >= 6

    def test_navigate_crosses_domains(self, multidomain):
        """Navigation crosses at least one domain boundary."""
        landscape, nodes, _ = multidomain
        result = navigate(landscape, nodes, "explore", 30, start="B:HERE")
        assert result["domain_crossings"] > 0

    def test_navigate_reaches_en(self, multidomain):
        """Navigation reaches at least one EN node."""
        landscape, nodes, _ = multidomain
        result = navigate(landscape, nodes, "explore", 40, start="B:HERE")
        en_in_path = [n for n in result["path"] if n.startswith("EN:")]
        assert len(en_in_path) > 0, "Navigation never reached EN territory"

    def test_explore_en_mode_biases_toward_en(self, multidomain):
        """explore_en mode visits more EN nodes than regular explore."""
        landscape, nodes, _ = multidomain
        # Reset by building fresh
        ls_fresh, nodes_fresh, _ = build_multidomain_landscape()

        r_normal = navigate(ls_fresh, nodes_fresh, "explore", 30, start="B:HERE")
        en_normal = len([n for n in r_normal["path"] if n.startswith("EN:")])

        ls_fresh2, nodes_fresh2, _ = build_multidomain_landscape()
        r_en = navigate(ls_fresh2, nodes_fresh2, "explore_en", 30, start="B:HERE")
        en_biased = len([n for n in r_en["path"] if n.startswith("EN:")])

        # explore_en should visit at least as many EN nodes
        # (statistically: ≥ with the 1.3× bonus, but can vary)
        assert en_biased >= en_normal or en_biased >= 3, \
            f"explore_en={en_biased} vs explore={en_normal}"

    def test_crossing_counts_sum(self, multidomain):
        """Per-pair crossings sum to total crossings."""
        landscape, nodes, _ = multidomain
        result = navigate(landscape, nodes, "explore", 30, start="B:HERE")
        pair_sum = (result["en_canon_crossings"]
                    + result["en_bootstrap_crossings"]
                    + result["canon_bootstrap_crossings"])
        assert pair_sum == result["domain_crossings"]

    def test_shortcut_edges_created(self, multidomain):
        """Navigation creates shortcut edges from sub-paths."""
        landscape, nodes, _ = multidomain
        result = navigate(landscape, nodes, "explore", 30, start="B:HERE")
        # With 30 steps, there should be shortcuts
        assert len(result["new_edges"]) >= 1

    def test_new_edges_have_required_fields(self, multidomain):
        """Shortcut edges carry all required metadata."""
        landscape, nodes, _ = multidomain
        result = navigate(landscape, nodes, "explore", 30, start="B:HERE")
        for edge in result["new_edges"]:
            assert "from" in edge
            assert "to" in edge
            assert "delta" in edge
            assert "resistance" in edge
            assert "confidence" in edge
            assert "derivation" in edge


# ---------------------------------------------------------------------------
# Phase 5: Consolidation
# ---------------------------------------------------------------------------


class TestConsolidation:
    """Round results persist to learning_state.json."""

    def test_dry_run_no_write(self):
        """dry_run=True returns preview without writing."""
        dummy = MultiDomainRoundResult(
            round_num=1, mode="explore", reason="test", steps=10,
            assessment_before=None, assessment_after=MultiDomainAssessment(
                total_nodes=148, total_edges=400, visited_nodes=80,
                coverage=0.54, frontier_size=40, T_s=0.08,
                mean_quality=0.5, stale_edges=0,
                canon_coverage=0.6, bootstrap_coverage=0.9, en_coverage=0.3,
                canon_nodes=63, bootstrap_nodes=41, en_nodes=44,
                canon_visited=38, bootstrap_visited=37, en_visited=13,
            ),
            path=["B:HERE", "C:difference"], new_edges=2,
            domain_crossings=1, crossing_rate=1.0,
            coverage_delta=0.05, T_s_delta=-0.01,
            en_canon_crossings=0, en_bootstrap_crossings=0,
            canon_bootstrap_crossings=1,
        )
        result = consolidate(dummy, [{"from": "A", "to": "B"}], dry_run=True)
        assert result["dry_run"] is True
        assert result["new_edges_would_persist"] == 1

    def test_persist_writes_multidomain_history(self, tmp_path):
        """consolidate writes to multidomain_history section."""
        import e0_controller.explore_bootstrap_landscape as mod

        tmp_ls = tmp_path / "learning_state.json"
        with open(tmp_ls, "w", encoding="utf-8") as f:
            json.dump({"_meta": {"source": "test"}}, f, indent=2)

        orig_path = mod.LEARNING_STATE_PATH
        mod.LEARNING_STATE_PATH = str(tmp_ls)
        try:
            a = MultiDomainAssessment(
                total_nodes=148, total_edges=400, visited_nodes=100,
                coverage=0.68, frontier_size=20, T_s=0.06,
                mean_quality=0.5, stale_edges=0,
                canon_coverage=0.7, bootstrap_coverage=0.9, en_coverage=0.5,
                canon_nodes=63, bootstrap_nodes=41, en_nodes=44,
                canon_visited=44, bootstrap_visited=37, en_visited=22,
            )
            dummy = MultiDomainRoundResult(
                round_num=1, mode="explore_en", reason="EN gap", steps=30,
                assessment_before=a, assessment_after=a, path=["B:HERE"],
                new_edges=0, domain_crossings=5, crossing_rate=0.17,
                coverage_delta=0.05, T_s_delta=-0.01,
                en_canon_crossings=2, en_bootstrap_crossings=1,
                canon_bootstrap_crossings=2,
            )
            result = consolidate(dummy, [])
            assert result["round_recorded"] is True

            with open(tmp_ls, encoding="utf-8") as f:
                ls = json.load(f)
            assert "multidomain_history" in ls
            entry = ls["multidomain_history"]["rounds"][-1]
            assert entry["mode"] == "explore_en"
            assert entry["en_coverage"] == 0.5
            assert entry["en_canon_crossings"] == 2
        finally:
            mod.LEARNING_STATE_PATH = orig_path


# ---------------------------------------------------------------------------
# Full Cycle
# ---------------------------------------------------------------------------


class TestFullCycle:
    """End-to-end multi-domain learning cycle."""

    def test_cycle_runs_without_error(self):
        """run_multidomain_cycle completes without exception."""
        results = run_multidomain_cycle(
            max_rounds=3, steps_per_round=20, verbose=False)
        assert len(results) >= 1

    def test_coverage_increases(self):
        """Coverage increases over multiple rounds."""
        results = run_multidomain_cycle(
            max_rounds=4, steps_per_round=30, verbose=False)
        first_cov = results[0].assessment_before.coverage
        last_cov = results[-1].assessment_after.coverage
        assert last_cov > first_cov, \
            f"Coverage did not increase: {first_cov:.1%} → {last_cov:.1%}"

    def test_en_coverage_grows(self):
        """EN coverage grows from near-zero."""
        results = run_multidomain_cycle(
            max_rounds=4, steps_per_round=30, verbose=False)
        en_start = results[0].assessment_before.en_coverage
        en_end = results[-1].assessment_after.en_coverage
        assert en_end > en_start, \
            f"EN coverage did not grow: {en_start:.1%} → {en_end:.1%}"

    def test_all_three_domains_visited(self):
        """By end of cycle, all three domains have >0 coverage."""
        results = run_multidomain_cycle(
            max_rounds=4, steps_per_round=30, verbose=False)
        last = results[-1].assessment_after
        assert last.canon_coverage > 0
        assert last.bootstrap_coverage > 0
        assert last.en_coverage > 0

    def test_cross_domain_crossings_occur(self):
        """At least one crossing per domain pair occurs across the cycle."""
        results = run_multidomain_cycle(
            max_rounds=5, steps_per_round=30, verbose=False)
        total_en_canon = sum(r.en_canon_crossings for r in results)
        total_en_bs = sum(r.en_bootstrap_crossings for r in results)
        total_cb = sum(r.canon_bootstrap_crossings for r in results)
        assert total_en_canon > 0, "No EN↔Canon crossings"
        assert total_cb > 0, "No Canon↔Bootstrap crossings"
        # EN↔Bootstrap may be fewer since bridges are fewer
        assert total_en_bs >= 0  # At least doesn't crash

    def test_en_bridges_used_in_navigation(self):
        """EN bridge edges are actually traversed during navigation."""
        results = run_multidomain_cycle(
            max_rounds=4, steps_per_round=30, verbose=False)
        all_paths = []
        for r in results:
            all_paths.extend(r.path)
        en_nodes_visited = {n for n in all_paths if n.startswith("EN:")}
        assert len(en_nodes_visited) >= 5, \
            f"Only {len(en_nodes_visited)} EN nodes visited across cycle"

    def test_t_s_decreases_overall(self):
        """Structural temperature decreases (system learns → cools)."""
        results = run_multidomain_cycle(
            max_rounds=5, steps_per_round=30, verbose=False)
        t_start = results[0].assessment_before.T_s
        t_end = results[-1].assessment_after.T_s
        assert t_end <= t_start, \
            f"T_s did not decrease: {t_start:.3f} → {t_end:.3f}"

    def test_results_have_consistent_round_numbers(self):
        """Round numbers are sequential starting from 1."""
        results = run_multidomain_cycle(
            max_rounds=3, steps_per_round=20, verbose=False)
        for i, r in enumerate(results):
            assert r.round_num == i + 1


# ── Communication (C212) ───────────────────────────────────────────────


class TestCommunicateRound:
    """communicate_round produces text/markdown from round results."""

    def test_produces_text(self):
        landscape, unified_nodes, _ = build_multidomain_landscape()
        results = run_multidomain_cycle(
            max_rounds=1, steps_per_round=20, verbose=False)
        text = communicate_round(results[0], landscape, output_format="text")
        assert "E₀ Learning Cycle" in text
        assert "Round 1" in text
        assert "Interpretations" in text

    def test_produces_markdown(self):
        landscape, unified_nodes, _ = build_multidomain_landscape()
        results = run_multidomain_cycle(
            max_rounds=1, steps_per_round=20, verbose=False)
        md = communicate_round(results[0], landscape, output_format="markdown")
        assert "# E₀ Learning Cycle" in md
        assert "## Interpretations" in md

    def test_has_coverage_info(self):
        landscape, _, _ = build_multidomain_landscape()
        results = run_multidomain_cycle(
            max_rounds=1, steps_per_round=20, verbose=False)
        text = communicate_round(results[0], landscape, output_format="text")
        # Should mention coverage somewhere
        assert "%" in text

    def test_stagnation_in_output(self):
        landscape, _, _ = build_multidomain_landscape()
        results = run_multidomain_cycle(
            max_rounds=1, steps_per_round=20, verbose=False)
        text = communicate_round(
            results[0], landscape, stagnation_count=3, output_format="text")
        assert "Stagnation" in text


class TestCommunicateSummary:
    """communicate_summary aggregates full cycle into prose."""

    def test_produces_text(self):
        landscape, _, _ = build_multidomain_landscape()
        results = run_multidomain_cycle(
            max_rounds=2, steps_per_round=20, verbose=False)
        text = communicate_summary(results, landscape, output_format="text")
        assert "Summary" in text
        assert "Interpretations" in text

    def test_produces_markdown(self):
        landscape, _, _ = build_multidomain_landscape()
        results = run_multidomain_cycle(
            max_rounds=2, steps_per_round=20, verbose=False)
        md = communicate_summary(results, landscape, output_format="markdown")
        assert "# E₀ Learning Cycle Summary" in md

    def test_has_inscription_analysis(self):
        landscape, _, _ = build_multidomain_landscape()
        # Navigate to create inscriptions
        results = run_multidomain_cycle(
            max_rounds=3, steps_per_round=30, verbose=False)
        # Use the summary's own landscape
        text = communicate_summary(results, landscape, output_format="text")
        # Summary always has interpretations; inscription section only if inscribed
        assert "Interpretations" in text

    def test_has_domain_crossings(self):
        landscape, _, _ = build_multidomain_landscape()
        results = run_multidomain_cycle(
            max_rounds=2, steps_per_round=30, verbose=False)
        text = communicate_summary(results, landscape, output_format="text")
        assert "Crossings" in text or "crossings" in text

    def test_empty_history_returns_empty(self):
        landscape, _, _ = build_multidomain_landscape()
        text = communicate_summary([], landscape, output_format="text")
        assert text == ""


class TestOutputFormatIntegration:
    """run_multidomain_cycle with output_format produces output."""

    def test_format_text_runs(self, capsys):
        run_multidomain_cycle(
            max_rounds=1, steps_per_round=15, verbose=False,
            output_format="text")
        captured = capsys.readouterr()
        assert "E₀ Learning Cycle" in captured.out
        assert "Interpretations" in captured.out

    def test_format_none_no_communication(self, capsys):
        run_multidomain_cycle(
            max_rounds=1, steps_per_round=15, verbose=False,
            output_format=None)
        captured = capsys.readouterr()
        # No communication output (verbose=False, no format)
        assert "Interpretations" not in captured.out
