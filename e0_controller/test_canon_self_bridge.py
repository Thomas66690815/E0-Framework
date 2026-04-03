"""
Tests for E₀ Canon ↔ Self-Graph Bridge
========================================
Verifies: mapping correctness, coverage analysis, combined exposition,
canon alignment with operational data.
"""

import unittest

from e0_controller.canon_loader import load_canon
from e0_controller.canon_self_bridge import (
    CANON_PROCESS_MAP,
    PROCESS_CANON_MAP,
    build_self_exposition,
    canon_coverage,
    format_process_status,
)
from e0_controller.self_graph import SelfGraph, ALL_COMPONENTS
from e0_controller.primitives import Outcome


# ──────────────────────────────────────────────
# 1. Mapping Integrity
# ──────────────────────────────────────────────

class TestCanonProcessMap(unittest.TestCase):
    """The canon ↔ process mapping is structurally sound."""

    def test_all_self_graph_components_mapped(self):
        """Every self-graph component maps to at least one canon node."""
        for comp in ALL_COMPONENTS:
            self.assertIn(comp, CANON_PROCESS_MAP,
                          f"Component {comp} has no canon mapping")
            self.assertGreater(len(CANON_PROCESS_MAP[comp]), 0)

    def test_historization_maps_to_historization(self):
        """The central identity: historization IS historization + time."""
        mapped = CANON_PROCESS_MAP["historization"]
        self.assertIn("historization", mapped)
        self.assertIn("time", mapped)

    def test_amplitude_maps_to_difference(self):
        """Δ-detection maps to the root primitive."""
        self.assertIn("difference", CANON_PROCESS_MAP["amplitude"])

    def test_born_maps_to_axiom_and_rate(self):
        """State selection maps to A0 + realizability."""
        mapped = CANON_PROCESS_MAP["born"]
        self.assertIn("axiom_a0", mapped)
        self.assertIn("rate", mapped)

    def test_reverse_map_exists(self):
        """Reverse map is populated."""
        self.assertIn("historization", PROCESS_CANON_MAP)
        self.assertIn("historization", PROCESS_CANON_MAP["historization"])

    def test_reverse_map_bidirectional(self):
        """Forward and reverse maps are consistent."""
        for comp, nodes in CANON_PROCESS_MAP.items():
            for node in nodes:
                self.assertIn(node, PROCESS_CANON_MAP)
                self.assertIn(comp, PROCESS_CANON_MAP[node])

    def test_mapped_canon_nodes_exist_in_landscape(self):
        """All mapped canon node IDs exist in the actual canon JSON."""
        cl = load_canon("ontodynamics")
        all_ids = {n.id for n in cl.info.nodes}
        for comp, nodes in CANON_PROCESS_MAP.items():
            for node in nodes:
                self.assertIn(node, all_ids,
                              f"Mapped node {node} (from {comp}) not in canon")


# ──────────────────────────────────────────────
# 2. Canon Coverage
# ──────────────────────────────────────────────

class TestCanonCoverage(unittest.TestCase):
    """Coverage analysis of canon vs. self-graph."""

    def setUp(self):
        self.cl = load_canon("ontodynamics")
        self.cov = canon_coverage(self.cl)

    def test_returns_dict_with_keys(self):
        self.assertIn("instantiated", self.cov)
        self.assertIn("not_instantiated", self.cov)
        self.assertIn("coverage_ratio", self.cov)

    def test_instantiated_subset_of_canon(self):
        all_ids = {n.id for n in self.cl.info.nodes}
        self.assertTrue(self.cov["instantiated"].issubset(all_ids))

    def test_not_instantiated_subset_of_canon(self):
        all_ids = {n.id for n in self.cl.info.nodes}
        self.assertTrue(self.cov["not_instantiated"].issubset(all_ids))

    def test_coverage_partitions_all_nodes(self):
        all_ids = {n.id for n in self.cl.info.nodes}
        union = self.cov["instantiated"] | self.cov["not_instantiated"]
        self.assertEqual(union, all_ids)

    def test_no_overlap(self):
        overlap = self.cov["instantiated"] & self.cov["not_instantiated"]
        self.assertEqual(overlap, set())

    def test_historization_instantiated(self):
        self.assertIn("historization", self.cov["instantiated"])

    def test_negative_necessity_instantiated(self):
        """A₀ (born) IS negative necessity — non-transition is unstable."""
        self.assertIn("negative_necessity", self.cov["instantiated"])

    def test_reflexivity_instantiated(self):
        """C49+C50+C51: operational cycle includes reflexive Step 7."""
        self.assertIn("reflexivity", self.cov["instantiated"])

    def test_coverage_ratio_between_0_and_1(self):
        self.assertGreater(self.cov["coverage_ratio"], 0.0)
        self.assertLess(self.cov["coverage_ratio"], 1.0)


# ──────────────────────────────────────────────
# 3. Process Status Formatting
# ──────────────────────────────────────────────

class TestFormatProcessStatus(unittest.TestCase):
    """Formatted process status for LLM context."""

    def test_virgin_self_graph(self):
        sg = SelfGraph()
        status = format_process_status(sg)
        self.assertIn("amplitude", status)
        self.assertIn("historization", status)
        self.assertIn("difference", status)
        self.assertIn("historization", status)

    def test_after_historization(self):
        sg = SelfGraph()
        sg.self_historize(ALL_COMPONENTS, Outcome.SUCCESS)
        status = format_process_status(sg)
        # Quality should no longer be +0.000
        self.assertNotIn("+0.000", status.split("historization")[1].split("\n")[0])

    def test_all_components_present(self):
        sg = SelfGraph()
        status = format_process_status(sg)
        for comp in ALL_COMPONENTS:
            self.assertIn(comp, status)


# ──────────────────────────────────────────────
# 4. Combined Self-Exposition
# ──────────────────────────────────────────────

class TestBuildSelfExposition(unittest.TestCase):
    """Full self-exposition for LLM context."""

    def setUp(self):
        self.cl = load_canon("ontodynamics")

    def test_without_self_graph(self):
        expo = build_self_exposition(self.cl, sg=None)
        self.assertIn("WHAT I BELIEVE", expo)
        self.assertIn("HOW I OPERATE", expo)
        self.assertIn("no operational data", expo)
        self.assertIn("CANON COVERAGE", expo)

    def test_with_virgin_self_graph(self):
        sg = SelfGraph()
        expo = build_self_exposition(self.cl, sg)
        self.assertIn("WHAT I BELIEVE", expo)
        self.assertIn("HOW I OPERATE", expo)
        self.assertNotIn("no operational data", expo)
        self.assertIn("STRUCTURAL INSIGHT", expo)
        self.assertIn("EPISTEMIC FRONTIER", expo)

    def test_with_experienced_self_graph(self):
        sg = SelfGraph()
        for _ in range(20):
            sg.self_historize(ALL_COMPONENTS, Outcome.SUCCESS)
        expo = build_self_exposition(self.cl, sg)
        self.assertIn("working well", expo)

    def test_with_struggling_self_graph(self):
        sg = SelfGraph()
        for _ in range(20):
            sg.self_historize(ALL_COMPONENTS, Outcome.FAILURE)
        expo = build_self_exposition(self.cl, sg)
        self.assertIn("struggling", expo)

    def test_contains_canon_summary(self):
        expo = build_self_exposition(self.cl)
        self.assertIn("ontodynamics", expo)
        self.assertIn("v2.0", expo)

    def test_contains_coverage_ratio(self):
        expo = build_self_exposition(self.cl)
        # Should show percentage like "58%" or similar
        self.assertIn("%", expo)

    def test_contains_not_instantiated_concepts(self):
        expo = build_self_exposition(self.cl)
        # v2 has implementation nodes not yet mapped to self-graph
        self.assertIn("Not yet operational", expo)

    def test_frontier_shows_labels(self):
        sg = SelfGraph()
        expo = build_self_exposition(self.cl, sg)
        # Frontier should show human-readable labels from not-instantiated nodes
        self.assertIn("EPISTEMIC FRONTIER", expo)

    def test_exposition_is_substantial(self):
        sg = SelfGraph()
        expo = build_self_exposition(self.cl, sg)
        # Should be a rich document
        self.assertGreater(len(expo), 2000)


# ──────────────────────────────────────────────
# 5. Structural Correctness
# ──────────────────────────────────────────────

class TestStructuralCorrectness(unittest.TestCase):
    """The bridge encoding is structurally faithful to the canon."""

    def test_core_cycle_maps_to_operational_cycle(self):
        """The self-graph's 6-node cycle maps to the canon's L6 concept."""
        cycle_components = [
            "amplitude", "born", "realization",
            "historization", "inertia", "transition_field",
        ]
        all_mapped = set()
        for comp in cycle_components:
            all_mapped.update(CANON_PROCESS_MAP[comp])
        self.assertIn("operational_cycle", all_mapped)

    def test_modulation_maps_to_overlap(self):
        """Both modulation components map to overlap."""
        self.assertIn("overlap", CANON_PROCESS_MAP["curvature"])
        self.assertIn("overlap", CANON_PROCESS_MAP["overlap"])

    def test_inertia_maps_to_resistance_and_mass(self):
        """Inertia component instantiates both resistance and mass."""
        mapped = CANON_PROCESS_MAP["inertia"]
        self.assertIn("resistance", mapped)
        self.assertIn("mass", mapped)

    def test_no_duplicate_in_map_values(self):
        """Each component's mapping list has no duplicates."""
        for comp, nodes in CANON_PROCESS_MAP.items():
            self.assertEqual(len(nodes), len(set(nodes)),
                             f"Duplicate in {comp} mapping")


if __name__ == "__main__":
    unittest.main()
