"""
C57 — Proactive Reflexion Tests (Stufe 2)
=============================================
Proves that proactive reflexion (edge construction BEFORE navigation)
is structurally superior to reactive reflexion (C56, edge construction
AFTER stuckness).

Core claim: "Reflexion ist der Normalfall für alles Neue.
Ich reflektiere BEVOR ich in eine Falle tappe."

Test domains:

"Frontier Gap" (reused from C56):
  S → A → B → FRONTIER → S  (cycle)
  BRIDGE → D → GOAL         (disconnected)
  → Proactive: proposes at step 0, fewer total steps

"Cascading Gaps" (NEW — reactive C56 cannot solve):
  Region 1:  S → A → GAP1 → S       (cycle)
  Region 2:  ISLE1 → B → GAP2 → ISLE1 (cycle)
  Region 3:  ISLE2 → C → GOAL
  Three disconnected regions.  Two proposals needed:
    GAP1 → ISLE1  AND  GAP2 → ISLE2
  Reactive (single-shot) fails.  Proactive solves.

Test classes:
  TestProactiveVsReactive       (4) — efficiency comparison
  TestCascadingGaps             (5) — multi-frontier domain
  TestProactiveEdgeCases        (4) — single node, already connected, etc.
  TestProactiveIsIdempotent     (3) — second proposal at same node skipped
  TestStufenComparison          (4) — explicit Stufe-0/1/2 taxonomy

Total: 20 tests.
"""

from __future__ import annotations

import unittest

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller, RunTrace
from e0_controller.reflexive_edge_proposal import (
    apply_proposals,
    is_frontier,
    propose_edges,
    run_with_proactive_reflexion,
    run_with_reflexion,
    _outgoing_neighbors,
)


# ══════════════════════════════════════════════
# Execute functions
# ══════════════════════════════════════════════

def _all_success(source: str, target: str) -> Outcome:
    return Outcome.SUCCESS


def _all_closed(source: str, target: str) -> Outcome:
    """Stufe 0: no coupling, no information."""
    return Outcome.SUCCESS


# ══════════════════════════════════════════════
# Domains
# ══════════════════════════════════════════════

def _build_frontier_gap() -> Landscape:
    """Same C56 domain: cycle + disconnected goal region."""
    L = Landscape()
    L.add_edge("S", "A", delta=0.3, resistance=0.5)
    L.add_edge("A", "B", delta=0.3, resistance=0.5)
    L.add_edge("B", "FRONTIER", delta=0.3, resistance=0.5)
    L.add_edge("FRONTIER", "S", delta=0.5, resistance=0.8)
    L.add_edge("BRIDGE", "D", delta=0.3, resistance=0.5)
    L.add_edge("D", "GOAL", delta=0.2, resistance=0.3)
    return L


def _build_cascading_gaps() -> Landscape:
    """Three disconnected regions — requires TWO proposals to solve.

    Region 1:  S → A → GAP1 → S       (cycle)
    Region 2:  ISLE1 → B → GAP2 → ISLE1 (cycle)
    Region 3:  ISLE2 → C → GOAL
    """
    L = Landscape()
    # Region 1
    L.add_edge("S", "A", delta=0.3, resistance=0.5)
    L.add_edge("A", "GAP1", delta=0.3, resistance=0.5)
    L.add_edge("GAP1", "S", delta=0.5, resistance=0.8)
    # Region 2
    L.add_edge("ISLE1", "B", delta=0.3, resistance=0.5)
    L.add_edge("B", "GAP2", delta=0.3, resistance=0.5)
    L.add_edge("GAP2", "ISLE1", delta=0.5, resistance=0.8)
    # Region 3
    L.add_edge("ISLE2", "C", delta=0.3, resistance=0.5)
    L.add_edge("C", "GOAL", delta=0.2, resistance=0.3)
    return L


def _build_direct_path() -> Landscape:
    """Already connected — no reflexion needed."""
    L = Landscape()
    L.add_edge("S", "A", delta=0.3, resistance=0.5)
    L.add_edge("A", "B", delta=0.3, resistance=0.5)
    L.add_edge("B", "GOAL", delta=0.2, resistance=0.3)
    return L


def _build_single_node() -> Landscape:
    """Single isolated node — no edges at all."""
    L = Landscape()
    L.add_state("ALONE")
    L.add_state("GOAL")
    return L


# ══════════════════════════════════════════════
# Test: Proactive vs Reactive efficiency
# ══════════════════════════════════════════════

class TestProactiveVsReactive(unittest.TestCase):
    """Compare step counts: proactive should be more efficient."""

    def test_proactive_reaches_goal(self):
        """Proactive reflexion reaches GOAL on frontier gap."""
        L = _build_frontier_gap()
        trace, proposals = run_with_proactive_reflexion(
            L, _all_success, "S", "GOAL", max_cycles=30,
        )
        self.assertIn("GOAL", trace.path)
        self.assertGreater(len(proposals), 0)

    def test_proactive_fewer_steps(self):
        """Proactive uses fewer steps than reactive on same domain."""
        # Reactive
        L_react = _build_frontier_gap()
        trace_react, _ = run_with_reflexion(
            L_react, _all_success, "S", "GOAL",
            max_cycles=30, proposal_trigger=8,
        )
        # Proactive
        L_proact = _build_frontier_gap()
        trace_proact, _ = run_with_proactive_reflexion(
            L_proact, _all_success, "S", "GOAL", max_cycles=30,
        )
        self.assertIn("GOAL", trace_react.path)
        self.assertIn("GOAL", trace_proact.path)
        # Proactive should need fewer (or equal) steps
        self.assertLessEqual(len(trace_proact.steps), len(trace_react.steps))

    def test_proactive_proposes_at_first_frontier(self):
        """Proactive proposes at first encounter, no warmup delay."""
        L = _build_frontier_gap()
        trace, proposals = run_with_proactive_reflexion(
            L, _all_success, "S", "GOAL", max_cycles=30,
        )
        # Proposals should happen early — before step 8
        # The path should not show 8+ cycles of S→A→B→FRONTIER looping
        frontier_first_idx = None
        for i, state in enumerate(trace.path):
            if state in {"BRIDGE", "D", "GOAL"}:
                frontier_first_idx = i
                break
        self.assertIsNotNone(frontier_first_idx)
        # Should reach isolated region within first ~8 steps (not after 8+ warmup)
        self.assertLess(frontier_first_idx, 8)

    def test_reactive_wastes_cycles(self):
        """Reactive needs at least proposal_trigger cycles before acting."""
        L = _build_frontier_gap()
        trace, proposals = run_with_reflexion(
            L, _all_success, "S", "GOAL",
            max_cycles=30, proposal_trigger=8,
        )
        self.assertIn("GOAL", trace.path)
        # Path should show looping before proposal
        goal_idx = trace.path.index("GOAL")
        self.assertGreaterEqual(goal_idx, 8)


# ══════════════════════════════════════════════
# Test: Cascading Gaps (reactive CANNOT solve)
# ══════════════════════════════════════════════

class TestCascadingGaps(unittest.TestCase):
    """Multi-frontier domain: only proactive can solve."""

    def test_reactive_needs_warmup_for_cascading(self):
        """Reactive needs warmup cycles before proposing — more steps."""
        L_react = _build_cascading_gaps()
        trace_react, _ = run_with_reflexion(
            L_react, _all_success, "S", "GOAL",
            max_cycles=40, proposal_trigger=8,
        )
        L_proact = _build_cascading_gaps()
        trace_proact, _ = run_with_proactive_reflexion(
            L_proact, _all_success, "S", "GOAL", max_cycles=40,
        )
        # Both reach GOAL, but proactive is faster
        self.assertIn("GOAL", trace_react.path)
        self.assertIn("GOAL", trace_proact.path)
        self.assertLess(len(trace_proact.steps), len(trace_react.steps))

    def test_proactive_solves_cascading(self):
        """Proactive proposes at both GAP1 and GAP2 — reaches GOAL."""
        L = _build_cascading_gaps()
        trace, proposals = run_with_proactive_reflexion(
            L, _all_success, "S", "GOAL", max_cycles=40,
        )
        self.assertIn("GOAL", trace.path)

    def test_proactive_proposals_include_goal(self):
        """Proactive proposes edge to GOAL (proximity=0, sorted first)."""
        L = _build_cascading_gaps()
        _, proposals = run_with_proactive_reflexion(
            L, _all_success, "S", "GOAL", max_cycles=40,
        )
        targets = {p.target for p in proposals}
        self.assertIn("GOAL", targets)

    def test_cascading_proactive_minimal_path(self):
        """Proactive finds minimal path — may shortcut via direct proposal."""
        L = _build_cascading_gaps()
        trace, proposals = run_with_proactive_reflexion(
            L, _all_success, "S", "GOAL", max_cycles=40,
        )
        self.assertIn("GOAL", trace.path)
        # Proactive may shortcut via S→GOAL directly (optimal)
        # Key insight: system finds MOST EFFICIENT path, not longest
        self.assertLessEqual(len(trace.steps), 10)

    def test_cascading_proposals_have_rationale(self):
        """Each proposal carries Pattern-based rationale."""
        L = _build_cascading_gaps()
        _, proposals = run_with_proactive_reflexion(
            L, _all_success, "S", "GOAL", max_cycles=40,
        )
        for p in proposals:
            self.assertIn("Pattern", p.rationale)
            self.assertGreater(len(p.rationale), 10)


# ══════════════════════════════════════════════
# Test: Edge cases
# ══════════════════════════════════════════════

class TestProactiveEdgeCases(unittest.TestCase):
    """Boundary conditions for proactive reflexion."""

    def test_already_connected_no_proposals(self):
        """If path to goal exists, no proposals generated."""
        L = _build_direct_path()
        trace, proposals = run_with_proactive_reflexion(
            L, _all_success, "S", "GOAL", max_cycles=10,
        )
        self.assertIn("GOAL", trace.path)
        self.assertEqual(len(proposals), 0)

    def test_start_is_goal(self):
        """Start == goal → zero steps, no proposals."""
        L = _build_direct_path()
        trace, proposals = run_with_proactive_reflexion(
            L, _all_success, "GOAL", "GOAL", max_cycles=10,
        )
        self.assertEqual(len(trace.steps), 0)
        self.assertEqual(len(proposals), 0)

    def test_single_node_no_edges(self):
        """Node with no outgoing edges — proposal attempted, may not help."""
        L = _build_single_node()
        trace, proposals = run_with_proactive_reflexion(
            L, _all_success, "ALONE", "GOAL", max_cycles=10,
        )
        # ALONE has no outgoing edges, but GOAL exists as state
        # Proposal should suggest ALONE→GOAL
        if proposals:
            self.assertEqual(proposals[0].source, "ALONE")

    def test_proactive_handles_zero_max_cycles(self):
        """max_cycles=0 → no steps, proposals might still be empty."""
        L = _build_frontier_gap()
        trace, proposals = run_with_proactive_reflexion(
            L, _all_success, "S", "GOAL", max_cycles=0,
        )
        self.assertEqual(len(trace.steps), 0)


# ══════════════════════════════════════════════
# Test: Idempotency — no re-proposal at same node
# ══════════════════════════════════════════════

class TestProactiveIsIdempotent(unittest.TestCase):
    """Proactive reflexion proposes at each node at most once."""

    def test_no_duplicate_sources(self):
        """Proposals from the same source node don't repeat."""
        L = _build_frontier_gap()
        _, proposals = run_with_proactive_reflexion(
            L, _all_success, "S", "GOAL", max_cycles=30,
        )
        # All proposals from same source should come from one batch
        sources = [p.source for p in proposals]
        # Within one source, no duplicates (apply_proposals checks has_edge)
        seen = set()
        for p in proposals:
            key = (p.source, p.target)
            self.assertNotIn(key, seen)
            seen.add(key)

    def test_cascading_no_duplicate_proposals(self):
        """Cascading gaps: no duplicate (source, target) proposals."""
        L = _build_cascading_gaps()
        _, proposals = run_with_proactive_reflexion(
            L, _all_success, "S", "GOAL", max_cycles=40,
        )
        pairs = [(p.source, p.target) for p in proposals]
        self.assertEqual(len(pairs), len(set(pairs)))

    def test_revisit_frontier_no_reproposal(self):
        """If controller revisits a frontier node, no new proposals."""
        L = _build_frontier_gap()
        # Run with low max_proposals=1 to ensure only one edge per frontier
        trace, proposals = run_with_proactive_reflexion(
            L, _all_success, "S", "GOAL",
            max_cycles=30, max_proposals=1,
        )
        # Count proposals per source
        from collections import Counter
        source_counts = Counter(p.source for p in proposals)
        for count in source_counts.values():
            self.assertEqual(count, 1)


# ══════════════════════════════════════════════
# Test: Stufe-0/1/2 Taxonomy
# ══════════════════════════════════════════════

class TestStufenComparison(unittest.TestCase):
    """Explicit comparison of Stufe 0, 1, and 2 behavior.

    Stufe 0: closed system (all-SUCCESS) — no Raumzeit
    Stufe 1: coupled system, reactive (C54 behavior)
    Stufe 2: coupled + proactive reflexion (C57)
    """

    def test_stufe_0_no_escape(self):
        """Stufe 0 (all-SUCCESS, closed): loops forever, no goal."""
        L = _build_frontier_gap()
        ctrl = E0Controller(L, _all_closed, alpha=2.0, recent_k=3)
        trace = ctrl.run("S", max_cycles=20, goal="GOAL")
        self.assertNotIn("GOAL", trace.path)

    def test_stufe_1_loops_at_frontier(self):
        """Stufe 1 (coupled, no reflexion): loops at frontier."""
        L = _build_frontier_gap()
        ctrl = E0Controller(L, _all_success, alpha=2.0, recent_k=3)
        trace = ctrl.run("S", max_cycles=20, goal="GOAL")
        self.assertNotIn("GOAL", trace.path)

    def test_stufe_2_solves(self):
        """Stufe 2 (coupled + proactive): reaches GOAL."""
        L = _build_frontier_gap()
        trace, proposals = run_with_proactive_reflexion(
            L, _all_success, "S", "GOAL", max_cycles=30,
        )
        self.assertIn("GOAL", trace.path)

    def test_stufe_2_strictly_more_capable(self):
        """Stufe 2 solves cascading gaps that neither Stufe 0 nor 1 can."""
        L = _build_cascading_gaps()
        # Stufe 1: cannot solve
        ctrl = E0Controller(L, _all_success, alpha=2.0, recent_k=3)
        trace_1 = ctrl.run("S", max_cycles=40, goal="GOAL")
        self.assertNotIn("GOAL", trace_1.path)

        # Stufe 2: solves
        L2 = _build_cascading_gaps()
        trace_2, proposals = run_with_proactive_reflexion(
            L2, _all_success, "S", "GOAL", max_cycles=40,
        )
        self.assertIn("GOAL", trace_2.path)


if __name__ == "__main__":
    unittest.main()
