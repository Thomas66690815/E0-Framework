"""
C56 — Reflexive Edge Proposal Tests
======================================
Proves that reflexive edge construction enables navigation
through structural gaps that are unsolvable without it.

Core claim: Historisierung informiert Topologie, nicht nur Widerstand.

Test domain "Frontier Gap":
  Known region:    S → A → B → FRONTIER → S  (cycle)
  Isolated region: BRIDGE → D → GOAL         (exists, disconnected)
  Gap:             no edge FRONTIER → anything except S

Without reflexive proposal: controller loops forever.
With reflexive proposal: controller proposes FRONTIER→BRIDGE, reaches GOAL.

Test classes:
  TestFrontierDetection     (4) — frontier node detection
  TestPatternExtraction     (4) — parameter estimation from history
  TestCandidateTargets      (3) — finding unreachable states
  TestEdgeProposal          (4) — full proposal pipeline
  TestRunWithReflexion      (5) — integrated run with proposal
  TestProposalWithFailures  (3) — some proposals fail, system adapts

Total: 23 tests.
"""

from __future__ import annotations

import unittest

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller, RunTrace
from e0_controller.reflexive_edge_proposal import (
    ProposedEdge,
    EdgePattern,
    ReflexionResult,
    apply_proposals,
    detect_stuckness,
    experienced_pattern,
    find_candidate_targets,
    is_frontier,
    propose_edges,
    run_with_reflexion,
    _bfs_reachable,
    _outgoing_neighbors,
)


# ══════════════════════════════════════════════
# Test domains
# ══════════════════════════════════════════════

def _all_success(source: str, target: str) -> Outcome:
    return Outcome.SUCCESS


def _build_frontier_gap() -> Landscape:
    """Frontier Gap domain: cycle + disconnected goal region.

    Known:    S → A → B → FRONTIER → S
    Isolated: BRIDGE → D → GOAL
    Gap:      no edge from FRONTIER to {BRIDGE, D, GOAL}
    """
    L = Landscape()
    # Known region (cycle)
    L.add_edge("S", "A", delta=0.3, resistance=0.5)
    L.add_edge("A", "B", delta=0.3, resistance=0.5)
    L.add_edge("B", "FRONTIER", delta=0.3, resistance=0.5)
    L.add_edge("FRONTIER", "S", delta=0.5, resistance=0.8)
    # Isolated region (disconnected from known)
    L.add_edge("BRIDGE", "D", delta=0.3, resistance=0.5)
    L.add_edge("D", "GOAL", delta=0.2, resistance=0.3)
    return L


def _build_historized_frontier_gap() -> Landscape:
    """Same as frontier gap, but with historization from prior navigation."""
    L = _build_frontier_gap()
    hist = L.historization
    # Simulate 3 cycles through the known region
    for _ in range(3):
        hist.update(Edge("S", "A"), Outcome.SUCCESS)
        hist.update(Edge("A", "B"), Outcome.SUCCESS)
        hist.update(Edge("B", "FRONTIER"), Outcome.SUCCESS)
        hist.update(Edge("FRONTIER", "S"), Outcome.SUCCESS)
    return L


def _build_frontier_with_failure_edges() -> Landscape:
    """Frontier gap where some proposals will fail."""
    L = _build_frontier_gap()
    # Add more isolated states to create dead-end proposals
    L.add_state("DEADEND1")
    L.add_state("DEADEND2")
    return L


def _frontier_failure_execute(source: str, target: str) -> Outcome:
    """Proposals to dead ends fail."""
    if target in ("DEADEND1", "DEADEND2"):
        return Outcome.FAILURE
    return Outcome.SUCCESS


# ══════════════════════════════════════════════
# Test: Frontier Detection
# ══════════════════════════════════════════════

class TestFrontierDetection(unittest.TestCase):
    """Detecting when a node is a frontier (no path to goal)."""

    def test_frontier_is_frontier(self):
        """FRONTIER has no path to GOAL — it's a frontier."""
        L = _build_frontier_gap()
        self.assertTrue(is_frontier(L, "FRONTIER", "GOAL"))

    def test_start_is_frontier(self):
        """S also has no path to GOAL (entire known region is disconnected)."""
        L = _build_frontier_gap()
        self.assertTrue(is_frontier(L, "S", "GOAL"))

    def test_bridge_is_not_frontier(self):
        """BRIDGE has a path to GOAL (BRIDGE→D→GOAL)."""
        L = _build_frontier_gap()
        self.assertFalse(is_frontier(L, "BRIDGE", "GOAL"))

    def test_after_proposal_not_frontier(self):
        """After adding FRONTIER→BRIDGE, FRONTIER is no longer a frontier."""
        L = _build_frontier_gap()
        L.add_edge("FRONTIER", "BRIDGE", delta=0.3, resistance=0.5)
        self.assertFalse(is_frontier(L, "FRONTIER", "GOAL"))


# ══════════════════════════════════════════════
# Test: Pattern Extraction
# ══════════════════════════════════════════════

class TestPatternExtraction(unittest.TestCase):
    """Extracting Δ/R₀ patterns from historized edges."""

    def test_no_history_uses_landscape_medians(self):
        """Without history, pattern uses landscape-wide medians."""
        L = _build_frontier_gap()
        pattern = experienced_pattern(L)
        self.assertEqual(pattern.sample_size, 0)
        self.assertEqual(pattern.coverage, 0.0)
        # Medians of all edges: Δ values are {0.2, 0.3, 0.3, 0.3, 0.3, 0.5}
        self.assertGreater(pattern.median_delta, 0)
        self.assertGreater(pattern.median_r0, 0)

    def test_with_history_extracts_successful(self):
        """With historization, pattern reflects successful edges."""
        L = _build_historized_frontier_gap()
        pattern = experienced_pattern(L)
        self.assertGreater(pattern.sample_size, 0)
        self.assertGreater(pattern.coverage, 0)

    def test_pattern_reflects_known_edges(self):
        """Successful edges have Δ=0.3, R₀=0.5 (known region median)."""
        L = _build_historized_frontier_gap()
        pattern = experienced_pattern(L)
        # Known region edges: Δ=0.3 (×3), Δ=0.5 (×1), R₀=0.5 (×3), R₀=0.8 (×1)
        self.assertAlmostEqual(pattern.median_delta, 0.3, places=1)
        self.assertAlmostEqual(pattern.median_r0, 0.5, places=1)

    def test_coverage_increases_with_history(self):
        """More historized edges → higher coverage."""
        L_no = _build_frontier_gap()
        L_yes = _build_historized_frontier_gap()
        p_no = experienced_pattern(L_no)
        p_yes = experienced_pattern(L_yes)
        self.assertGreater(p_yes.coverage, p_no.coverage)


# ══════════════════════════════════════════════
# Test: Candidate Targets
# ══════════════════════════════════════════════

class TestCandidateTargets(unittest.TestCase):
    """Finding states not directly reachable from a node."""

    def test_frontier_candidates(self):
        """FRONTIER can only reach S — all others are candidates."""
        L = _build_frontier_gap()
        candidates = find_candidate_targets(L, "FRONTIER")
        # FRONTIER→S exists, so S is NOT a candidate
        self.assertNotIn("S", candidates)
        self.assertNotIn("FRONTIER", candidates)
        # All others should be candidates
        for state in ("A", "B", "BRIDGE", "D", "GOAL"):
            self.assertIn(state, candidates)

    def test_s_candidates(self):
        """S can reach A — all except A are candidates."""
        L = _build_frontier_gap()
        candidates = find_candidate_targets(L, "S")
        self.assertNotIn("A", candidates)  # S→A exists
        self.assertIn("GOAL", candidates)

    def test_no_candidates_when_fully_connected(self):
        """A node reaching all others has no candidates."""
        L = Landscape()
        L.add_edge("X", "A", delta=0.1, resistance=0.1)
        L.add_edge("X", "B", delta=0.1, resistance=0.1)
        candidates = find_candidate_targets(L, "X")
        self.assertEqual(candidates, [])


# ══════════════════════════════════════════════
# Test: Edge Proposal
# ══════════════════════════════════════════════

class TestEdgeProposal(unittest.TestCase):
    """Full proposal pipeline: pattern → candidates → proposals."""

    def test_proposals_generated(self):
        """Proposals are generated for frontier node."""
        L = _build_historized_frontier_gap()
        proposals = propose_edges(L, "FRONTIER", "GOAL")
        self.assertGreater(len(proposals), 0)

    def test_goal_proximity_sorting(self):
        """Proposals closer to goal are sorted first."""
        L = _build_historized_frontier_gap()
        proposals = propose_edges(L, "FRONTIER", "GOAL")
        # GOAL itself (proximity=0) or BRIDGE/D (proximity=1, have path to goal)
        # should come before A/B (proximity=2, no path to goal)
        first = proposals[0]
        self.assertIn(first.target, {"GOAL", "BRIDGE", "D"})

    def test_confidence_scales_resistance(self):
        """Low confidence inflates R₀ — more cautious hypothesis."""
        L = _build_frontier_gap()  # no history → coverage=0 → low confidence
        proposals = propose_edges(L, "FRONTIER", "GOAL")
        if proposals:
            # With zero coverage, confidence is 0 → R₀ scaled up
            pattern = experienced_pattern(L)
            self.assertGreater(proposals[0].resistance, pattern.median_r0)

    def test_apply_proposals_adds_edges(self):
        """apply_proposals adds new edges to landscape."""
        L = _build_historized_frontier_gap()
        proposals = propose_edges(L, "FRONTIER", "GOAL")
        before = len(L._delta)
        added = apply_proposals(L, proposals)
        after = len(L._delta)
        self.assertEqual(after - before, added)
        self.assertGreater(added, 0)


# ══════════════════════════════════════════════
# Test: Integrated Run
# ══════════════════════════════════════════════

class TestRunWithReflexion(unittest.TestCase):
    """run_with_reflexion: end-to-end navigation through gap."""

    def test_without_reflexion_goal_unreachable(self):
        """Without reflexive proposal, controller loops forever."""
        L = _build_frontier_gap()
        ctrl = E0Controller(L, _all_success, alpha=2.0, recent_k=3)
        trace = ctrl.run("S", max_cycles=30, goal="GOAL")
        self.assertNotIn("GOAL", trace.path)

    def test_with_reflexion_goal_reached(self):
        """With reflexive proposal, controller reaches GOAL."""
        L = _build_frontier_gap()
        trace, proposals = run_with_reflexion(
            L, _all_success, "S", "GOAL",
            max_cycles=30, proposal_trigger=8,
        )
        self.assertIn("GOAL", trace.path)
        self.assertGreater(len(proposals), 0)

    def test_proposals_include_bridge(self):
        """Proposals include a target with path to GOAL."""
        L = _build_frontier_gap()
        trace, proposals = run_with_reflexion(
            L, _all_success, "S", "GOAL",
            max_cycles=30, proposal_trigger=8,
        )
        targets = {p.target for p in proposals}
        # At least one of BRIDGE, D, or GOAL should be proposed
        self.assertTrue(targets & {"BRIDGE", "D", "GOAL"})

    def test_stuckness_detected(self):
        """Controller cycling S→A→B→FRONTIER→S is detected as stuck."""
        L = _build_frontier_gap()
        ctrl = E0Controller(L, _all_success, alpha=2.0, recent_k=3)
        trace = ctrl.run("S", max_cycles=12, goal="GOAL")
        self.assertTrue(detect_stuckness(trace, window=8))

    def test_reflexion_produces_rationale(self):
        """Every proposed edge has a rationale explaining the hypothesis."""
        L = _build_frontier_gap()
        _, proposals = run_with_reflexion(
            L, _all_success, "S", "GOAL",
            max_cycles=30, proposal_trigger=8,
        )
        for p in proposals:
            self.assertTrue(len(p.rationale) > 0)
            self.assertIn("Pattern", p.rationale)


# ══════════════════════════════════════════════
# Test: Proposals with Failures
# ══════════════════════════════════════════════

class TestProposalWithFailures(unittest.TestCase):
    """Some proposed edges fail — system handles gracefully."""

    def test_dead_end_proposals_fail(self):
        """Proposals to dead-end states get FAILURE outcomes."""
        L = _build_frontier_with_failure_edges()
        # Pre-historize to have patterns
        hist = L.historization
        for _ in range(3):
            for s, t in [("S", "A"), ("A", "B"), ("B", "FRONTIER"),
                         ("FRONTIER", "S")]:
                hist.update(Edge(s, t), Outcome.SUCCESS)

        proposals = propose_edges(L, "FRONTIER", "GOAL", max_proposals=10)
        # Should include DEADEND1, DEADEND2 as candidates
        targets = {p.target for p in proposals}
        self.assertTrue(targets & {"DEADEND1", "DEADEND2"})

    def test_with_failures_still_reaches_goal(self):
        """Even with failed proposals, system finds GOAL through valid ones."""
        L = _build_frontier_with_failure_edges()
        trace, proposals = run_with_reflexion(
            L, _frontier_failure_execute, "S", "GOAL",
            max_cycles=40, proposal_trigger=8,
            max_proposals=8,  # propose enough to include BRIDGE
        )
        self.assertIn("GOAL", trace.path)

    def test_multiple_proposals_generated(self):
        """With dead ends, more candidates exist → more proposals."""
        L = _build_frontier_with_failure_edges()
        hist = L.historization
        for _ in range(3):
            for s, t in [("S", "A"), ("A", "B"), ("B", "FRONTIER"),
                         ("FRONTIER", "S")]:
                hist.update(Edge(s, t), Outcome.SUCCESS)

        proposals = propose_edges(L, "FRONTIER", "GOAL", max_proposals=10)
        # Should have proposals for BRIDGE, D, GOAL, DEADEND1, DEADEND2, A, B
        self.assertGreaterEqual(len(proposals), 5)


if __name__ == "__main__":
    unittest.main()
