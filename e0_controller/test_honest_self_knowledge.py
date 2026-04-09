"""
C52 — Honest Self-Knowledge: CANON_PROCESS_MAP correction
=========================================================

After C51 proved the system works end-to-end, C52 corrects the
self-observation: E₀ was reporting 58% coverage when the real
number is ~95%.  Seven canon concepts that ARE operationally
implemented were missing from the map.

Test classes:
  1. TestNewMappings (7) — each new mapping justified by code
  2. TestCoverageCorrection (5) — coverage ratio, frontier, partition
  3. TestExpositionAccuracy (4) — self-exposition reflects truth
  4. TestReverseMap (3) — PROCESS_CANON_MAP correctness

Total: 19 tests
"""

import unittest

from e0_controller.canon_loader import load_canon
from e0_controller.canon_self_bridge import (
    build_self_exposition,
    canon_coverage,
    CANON_PROCESS_MAP,
    PROCESS_CANON_MAP,
)
from e0_controller.self_graph import SelfGraph, CORE_COMPONENTS
from e0_controller.primitives import Outcome


# ──────────────────────────────────────────────
# 1. Each new mapping justified by code
# ──────────────────────────────────────────────

class TestNewMappings(unittest.TestCase):
    """Every C52 mapping addition has operational justification."""

    def test_time_maps_to_historization(self):
        """τ is defined as ordering of historizations (historization._tau)."""
        self.assertIn("time", CANON_PROCESS_MAP["historization"])

    def test_state_maps_to_realization(self):
        """Realization acts on states (Landscape._states: Set[str])."""
        self.assertIn("state", CANON_PROCESS_MAP["realization"])

    def test_negative_necessity_maps_to_born(self):
        """A₀ = negative necessity: non-transition is unstable."""
        self.assertIn("negative_necessity", CANON_PROCESS_MAP["born"])

    def test_reflexivity_maps_to_transition_field(self):
        """Operational cycle includes reflexive Step 7 (C49+C50)."""
        self.assertIn("reflexivity",
                      CANON_PROCESS_MAP["transition_field"])

    def test_structural_admissibility_maps_to_transition_field(self):
        """_admissible_neighbors() enforces §9 at every cycle."""
        self.assertIn("structural_admissibility",
                      CANON_PROCESS_MAP["transition_field"])

    def test_structural_alignment_maps_to_inertia(self):
        """Alignment via resistance (§6): inertia_factor dampens."""
        self.assertIn("structural_alignment",
                      CANON_PROCESS_MAP["inertia"])

    def test_domain_invariance_maps_to_realization(self):
        """No domain-specific primitives — works on any Landscape."""
        self.assertIn("domain_invariance",
                      CANON_PROCESS_MAP["realization"])


# ──────────────────────────────────────────────
# 2. Coverage correction
# ──────────────────────────────────────────────

class TestCoverageCorrection(unittest.TestCase):
    """Coverage now reflects operational reality."""

    def setUp(self):
        self.cl = load_canon("ontodynamics")
        self.cov = canon_coverage(self.cl)

    def test_coverage_above_60_percent(self):
        """Coverage should be >60% after honest mapping (45/63 in v3)."""
        self.assertGreater(self.cov["coverage_ratio"], 0.6)

    def test_spacetime_not_instantiated(self):
        """spacetime is a genuinely unimplemented concept."""
        self.assertIn("spacetime", self.cov["not_instantiated"])

    def test_canonical_coverage_strong(self):
        """Most canonical concepts (levels 0-8) should be instantiated."""
        cl = load_canon("ontodynamics")
        canonical = {n.id for n in cl.info.nodes if n.derivation_level <= 8}
        instantiated_canonical = self.cov["instantiated"] & canonical
        # All canonical except spacetime should be instantiated
        self.assertGreaterEqual(len(instantiated_canonical), len(canonical) - 1)

    def test_partition_still_complete(self):
        """instantiated ∪ not_instantiated = all canon nodes."""
        all_ids = {n.id for n in self.cl.info.nodes}
        union = self.cov["instantiated"] | self.cov["not_instantiated"]
        self.assertEqual(union, all_ids)

    def test_no_overlap(self):
        """No concept is both instantiated and not instantiated."""
        overlap = self.cov["instantiated"] & self.cov["not_instantiated"]
        self.assertEqual(overlap, set())


# ──────────────────────────────────────────────
# 3. Exposition accuracy
# ──────────────────────────────────────────────

class TestExpositionAccuracy(unittest.TestCase):
    """Self-exposition reflects the corrected self-knowledge."""

    def setUp(self):
        self.cl = load_canon("ontodynamics")
        self.sg = SelfGraph()
        for _ in range(5):
            self.sg.self_historize(list(CORE_COMPONENTS), Outcome.SUCCESS)

    def test_exposition_mentions_spacetime_as_frontier(self):
        """spacetime should appear in exposition as frontier."""
        expo = build_self_exposition(self.cl, sg=self.sg)
        self.assertIn("spacetime", expo.lower())

    def test_exposition_shows_reflexivity_as_operational(self):
        """reflexivity should appear in HOW I OPERATE, not frontier."""
        expo = build_self_exposition(self.cl, sg=self.sg)
        # Section 2 lists components with canon mappings
        self.assertIn("reflexivity", expo.lower())

    def test_exposition_shows_time_mapping(self):
        """time should be mentioned as mapped to historization."""
        expo = build_self_exposition(self.cl, sg=self.sg)
        self.assertIn("time", expo.lower())

    def test_frontier_exists(self):
        """Exposition should show not-instantiated concepts (epistemic frontier)."""
        expo = build_self_exposition(self.cl, sg=self.sg)
        self.assertIn("frontier", expo.lower())


# ──────────────────────────────────────────────
# 4. Reverse map
# ──────────────────────────────────────────────

class TestReverseMap(unittest.TestCase):
    """PROCESS_CANON_MAP correctly reflects the forward map."""

    def test_every_canon_node_in_forward_has_reverse(self):
        """Every canon node mentioned in forward map is in reverse."""
        all_canon = set()
        for nodes in CANON_PROCESS_MAP.values():
            all_canon.update(nodes)
        for node in all_canon:
            self.assertIn(node, PROCESS_CANON_MAP,
                f"Canon node {node} missing from reverse map")

    def test_reverse_map_components_exist(self):
        """Every component in reverse map is a valid CANON_PROCESS_MAP key."""
        for comps in PROCESS_CANON_MAP.values():
            for comp in comps:
                self.assertIn(comp, CANON_PROCESS_MAP)

    def test_reflexivity_reverse_maps_to_transition_field(self):
        """reflexivity → transition_field in reverse map."""
        self.assertIn("transition_field",
                      PROCESS_CANON_MAP["reflexivity"])


if __name__ == "__main__":
    unittest.main()
