"""
Tests for E₀ Canon Loader (C48)
================================
Verifies: JSON loading, metadata extraction, bootstrapper conversion,
landscape materialization, ontodynamics topology, derivation ordering,
navigability, LLM summary formatting.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from e0_controller.canon_loader import (
    CANON_DIR,
    CanonInfo,
    CanonLandscape,
    EdgeInfo,
    NodeInfo,
    _extract_info,
    _to_bootstrapper_spec,
    format_canon_summary,
    list_canons,
    load_canon,
    load_canon_spec,
)
from e0_controller.bootstrapper import BootstrapError
from e0_controller.graph_validation import (
    goal_reachable,
    find_happy_path,
    graph_quality,
)
from e0_controller.primitives import Edge, Outcome


# ──────────────────────────────────────────────
# 1. Directory + File Discovery
# ──────────────────────────────────────────────

class TestListCanons(unittest.TestCase):
    """Canon directory listing."""

    def test_canons_directory_exists(self):
        self.assertTrue(CANON_DIR.is_dir())

    def test_ontodynamics_available(self):
        names = list_canons()
        self.assertIn("ontodynamics", names)

    def test_returns_sorted_list(self):
        names = list_canons()
        self.assertEqual(names, sorted(names))


# ──────────────────────────────────────────────
# 2. Raw JSON Loading
# ──────────────────────────────────────────────

class TestLoadCanonSpec(unittest.TestCase):
    """Loading and parsing the raw JSON."""

    def test_load_ontodynamics(self):
        spec = load_canon_spec("ontodynamics")
        self.assertEqual(spec["name"], "ontodynamics")
        self.assertEqual(spec["version"], "2.0")

    def test_has_nodes_and_edges(self):
        spec = load_canon_spec("ontodynamics")
        self.assertGreater(len(spec["nodes"]), 0)
        self.assertGreater(len(spec["edges"]), 0)

    def test_not_found_raises(self):
        with self.assertRaises(FileNotFoundError) as ctx:
            load_canon_spec("nonexistent_canon")
        self.assertIn("nonexistent_canon", str(ctx.exception))

    def test_not_found_lists_available(self):
        with self.assertRaises(FileNotFoundError) as ctx:
            load_canon_spec("no_such_canon")
        self.assertIn("ontodynamics", str(ctx.exception))


# ──────────────────────────────────────────────
# 3. Metadata Extraction
# ──────────────────────────────────────────────

class TestExtractInfo(unittest.TestCase):
    """CanonInfo extraction from raw spec."""

    def setUp(self):
        self.spec = load_canon_spec("ontodynamics")
        self.info = _extract_info(self.spec)

    def test_name_and_version(self):
        self.assertEqual(self.info.name, "ontodynamics")
        self.assertEqual(self.info.version, "2.0")

    def test_source_reference(self):
        self.assertIn("ontodynamics.txt", self.info.source)
        self.assertIn("e0-canon-plain.txt", self.info.source)
        self.assertIn("e0-agi-blueprint.md", self.info.source)

    def test_node_count(self):
        self.assertEqual(len(self.info.nodes), 51)

    def test_edge_count(self):
        self.assertEqual(len(self.info.edges), 86)

    def test_five_primitives(self):
        primitives = [n for n in self.info.nodes if n.is_primitive]
        self.assertEqual(len(primitives), 5)
        primitive_ids = {n.id for n in primitives}
        self.assertEqual(primitive_ids, {
            "difference", "local_realization", "connection",
            "overlap", "historization",
        })

    def test_derived_concepts(self):
        derived = [n for n in self.info.nodes if not n.is_primitive]
        self.assertEqual(len(derived), 46)
        # Verify canonical derived concepts are present
        canonical_derived = {
            "state", "resistance", "time",
            "rate", "spacetime", "mass",
            "path", "axiom_a0",
            "operational_cycle", "structural_admissibility",
            "reflexivity", "structural_alignment",
            "domain_invariance", "negative_necessity",
        }
        derived_ids = {n.id for n in derived}
        self.assertTrue(canonical_derived.issubset(derived_ids))

    def test_derivation_levels(self):
        levels = {n.id: n.derivation_level for n in self.info.nodes}
        self.assertEqual(levels["difference"], 0)
        self.assertEqual(levels["local_realization"], 1)
        self.assertEqual(levels["connection"], 2)
        # overlap and historization at level 3
        self.assertEqual(levels["overlap"], 3)
        self.assertEqual(levels["historization"], 3)
        # derived at levels 4-5
        self.assertGreaterEqual(levels["state"], 4)
        self.assertGreaterEqual(levels["mass"], 5)
        # Canon Plain additions
        self.assertEqual(levels["path"], 4)
        self.assertEqual(levels["axiom_a0"], 5)
        # Blueprint additions
        self.assertEqual(levels["operational_cycle"], 6)
        self.assertEqual(levels["structural_admissibility"], 6)
        self.assertEqual(levels["reflexivity"], 7)
        self.assertEqual(levels["structural_alignment"], 7)
        self.assertEqual(levels["domain_invariance"], 7)
        self.assertEqual(levels["negative_necessity"], 8)
        # Implementation layers
        self.assertEqual(levels["tension"], 9)
        self.assertEqual(levels["greedy_navigation"], 9)
        self.assertEqual(levels["dream_mode"], 15)
        self.assertEqual(levels["sleep_wake_cycle"], 17)

    def test_goal_states(self):
        self.assertEqual(self.info.goal_states, ["negative_necessity", "sleep_wake_cycle"])

    def test_necessary_consequences(self):
        self.assertEqual(len(self.info.necessary_consequences), 15)
        self.assertIn("irreversibility", self.info.necessary_consequences)
        self.assertIn("transition_enforcement", self.info.necessary_consequences)
        self.assertIn("causal_ordering", self.info.necessary_consequences)

    def test_edge_derivations_non_empty(self):
        for e in self.info.edges:
            self.assertTrue(e.derivation, f"Edge {e.source}→{e.target} has no derivation")

    def test_node_descriptions_non_empty(self):
        for n in self.info.nodes:
            self.assertTrue(n.description, f"Node {n.id} has no description")

    def test_node_labels_non_empty(self):
        for n in self.info.nodes:
            self.assertTrue(n.label, f"Node {n.id} has no label")


# ──────────────────────────────────────────────
# 4. Bootstrapper Spec Conversion
# ──────────────────────────────────────────────

class TestToBootstrapperSpec(unittest.TestCase):
    """Conversion to bootstrapper-compatible format."""

    def setUp(self):
        self.spec = load_canon_spec("ontodynamics")
        self.bs_spec = _to_bootstrapper_spec(self.spec)

    def test_nodes_are_strings(self):
        for n in self.bs_spec["nodes"]:
            self.assertIsInstance(n, str)

    def test_node_count_preserved(self):
        self.assertEqual(len(self.bs_spec["nodes"]), 51)

    def test_edge_count_preserved(self):
        self.assertEqual(len(self.bs_spec["edges"]), 86)

    def test_edges_have_bootstrapper_fields(self):
        for e in self.bs_spec["edges"]:
            self.assertIn("from", e)
            self.assertIn("to", e)
            self.assertIn("delta", e)
            self.assertIn("resistance", e)

    def test_metadata_stripped(self):
        for e in self.bs_spec["edges"]:
            self.assertNotIn("derivation", e)

    def test_no_metadata_in_nodes(self):
        for n in self.bs_spec["nodes"]:
            self.assertNotIsInstance(n, dict)


# ──────────────────────────────────────────────
# 5. Full Materialization
# ──────────────────────────────────────────────

class TestLoadCanon(unittest.TestCase):
    """Full round-trip: JSON → CanonLandscape."""

    def setUp(self):
        self.cl = load_canon("ontodynamics")

    def test_returns_canon_landscape(self):
        self.assertIsInstance(self.cl, CanonLandscape)

    def test_has_landscape(self):
        from e0_controller.landscape import Landscape
        self.assertIsInstance(self.cl.landscape, Landscape)

    def test_has_info(self):
        self.assertIsInstance(self.cl.info, CanonInfo)

    def test_landscape_has_all_nodes(self):
        states = self.cl.landscape.states
        # Verify canonical nodes present (English IDs)
        canonical = {
            "difference", "local_realization", "connection",
            "overlap", "historization",
            "state", "resistance", "time",
            "rate", "spacetime", "mass",
            "path", "axiom_a0",
            "operational_cycle", "structural_admissibility",
            "reflexivity", "structural_alignment",
            "domain_invariance", "negative_necessity",
        }
        self.assertTrue(canonical.issubset(states))
        # v2 has implementation nodes too
        self.assertEqual(len(states), 51)

    def test_landscape_has_edges(self):
        edges = self.cl.landscape.edges
        self.assertEqual(len(edges), 86)

    def test_inertia_modulation_enabled(self):
        self.assertTrue(self.cl.landscape.inertia_modulation)


# ──────────────────────────────────────────────
# 6. Ontodynamics Topology
# ──────────────────────────────────────────────

class TestOntodynamicsTopology(unittest.TestCase):
    """Structural properties of the canon landscape."""

    def setUp(self):
        self.cl = load_canon("ontodynamics")
        self.ls = self.cl.landscape

    def test_derivation_spine(self):
        """The primitive chain must exist as edges."""
        spine = [
            ("difference", "local_realization"),
            ("local_realization", "connection"),
            ("connection", "overlap"),
            ("connection", "historization"),
        ]
        edge_set = {(e.source, e.target) for e in self.ls.edges}
        for src, tgt in spine:
            self.assertIn((src, tgt), edge_set, f"Missing spine edge {src}→{tgt}")

    def test_cycle_closure(self):
        """historization → difference closes the ontological cycle."""
        edge_set = {(e.source, e.target) for e in self.ls.edges}
        self.assertIn(("historization", "difference"), edge_set)

    def test_goal_reachable_from_difference(self):
        """mass must be reachable from difference."""
        self.assertTrue(goal_reachable(self.ls, "difference", "mass"))

    def test_all_primitives_reach_historization(self):
        """Every primitive can reach historization."""
        primitives = [
            "difference", "local_realization", "connection",
            "overlap",
        ]
        for p in primitives:
            self.assertTrue(
                goal_reachable(self.ls, p, "historization"),
                f"{p} cannot reach historization",
            )

    def test_happy_path_to_mass(self):
        """A path from difference to mass must exist."""
        path = find_happy_path(self.ls, "difference", "mass")
        self.assertIsNotNone(path)
        self.assertGreater(len(path), 0)

    def test_spacetime_needs_two_inputs(self):
        """spacetime receives from both state and time."""
        incoming = [
            e for e in self.ls.edges if e.target == "spacetime"
        ]
        sources = {e.source for e in incoming}
        self.assertIn("state", sources)
        self.assertIn("time", sources)

    def test_historization_is_hub(self):
        """historization has the most outgoing edges (hub concept)."""
        out_counts = {}
        for e in self.ls.edges:
            out_counts[e.source] = out_counts.get(e.source, 0) + 1
        max_out = max(out_counts.values())
        self.assertEqual(out_counts["historization"], max_out)

    def test_path_requires_connection_and_resistance(self):
        """Path derives from Connection + Resistance."""
        incoming = [e for e in self.ls.edges if e.target == "path"]
        sources = {e.source for e in incoming}
        self.assertIn("connection", sources)
        self.assertIn("resistance", sources)

    def test_axiom_a0_requires_difference_and_path(self):
        """A0 derives from Difference + Path."""
        incoming = [e for e in self.ls.edges if e.target == "axiom_a0"]
        sources = {e.source for e in incoming}
        self.assertIn("difference", sources)
        self.assertIn("path", sources)

    def test_path_feeds_rate(self):
        """Rate is realized along structurally admissible paths."""
        edge_set = {(e.source, e.target) for e in self.ls.edges}
        self.assertIn(("path", "rate"), edge_set)

    def test_rate_has_two_inputs(self):
        """Rate receives from both Resistance and Path."""
        incoming = [e for e in self.ls.edges if e.target == "rate"]
        sources = {e.source for e in incoming}
        self.assertIn("resistance", sources)
        self.assertIn("path", sources)

    def test_axiom_a0_reachable_from_difference(self):
        """The foundational axiom must be reachable from difference."""
        self.assertTrue(goal_reachable(self.ls, "difference", "axiom_a0"))

    # ── Blueprint topology ──

    def test_operational_cycle_requires_axiom_and_historization(self):
        """The cycle instantiates A0 with historization."""
        incoming = [e for e in self.ls.edges if e.target == "operational_cycle"]
        sources = {e.source for e in incoming}
        self.assertIn("axiom_a0", sources)
        self.assertIn("historization", sources)

    def test_reflexivity_requires_cycle_and_historization(self):
        """Reflexivity emerges from the cycle operating on itself + historization."""
        incoming = [e for e in self.ls.edges if e.target == "reflexivity"]
        sources = {e.source for e in incoming}
        self.assertIn("operational_cycle", sources)
        self.assertIn("historization", sources)

    def test_negative_necessity_has_three_canonical_inputs(self):
        """The thesis derives from reflexivity, alignment, and domain invariance."""
        incoming = [e for e in self.ls.edges if e.target == "negative_necessity"]
        sources = {e.source for e in incoming}
        self.assertIn("reflexivity", sources)
        self.assertIn("structural_alignment", sources)
        self.assertIn("domain_invariance", sources)

    def test_full_journey_difference_to_negative_necessity(self):
        """The full derivation path from difference to negative_necessity must exist."""
        self.assertTrue(goal_reachable(self.ls, "difference", "negative_necessity"))

    def test_happy_path_to_negative_necessity(self):
        """A happy path from difference to the thesis must exist."""
        path = find_happy_path(self.ls, "difference", "negative_necessity")
        self.assertIsNotNone(path)
        self.assertGreaterEqual(len(path), 5)  # must cross multiple derivation levels


# ──────────────────────────────────────────────
# 7. Derivation Order in Delta Values
# ──────────────────────────────────────────────

class TestDerivationOrder(unittest.TestCase):
    """Delta encodes derivation cost — rises with derivation distance."""

    def setUp(self):
        self.cl = load_canon("ontodynamics")
        self.info = self.cl.info
        self.spec = load_canon_spec("ontodynamics")
        # Build delta lookup
        self.deltas = {}
        for e in self.spec["edges"]:
            self.deltas[(e["from"], e["to"])] = e["delta"]
        # Build level lookup
        self.levels = {}
        for n in self.spec["nodes"]:
            self.levels[n["id"]] = n["derivation_level"]

    def test_primitive_chain_low_delta(self):
        """Edges between primitives of adjacent levels have low Δ."""
        primitive_edges = [
            ("difference", "local_realization"),
            ("local_realization", "connection"),
        ]
        for src, tgt in primitive_edges:
            self.assertLessEqual(
                self.deltas[(src, tgt)], 0.4,
                f"Primitive edge {src}→{tgt} should have low Δ",
            )

    def test_derived_edges_higher_delta(self):
        """Cross-level edges to derived concepts have higher Δ than primitive edges."""
        # Only consider canonical edges (levels 0-8)
        cross_level_derived = [
            d for (s, t), d in self.deltas.items()
            if self.levels.get(t, 0) >= 4
            and self.levels.get(t, 0) <= 8
            and self.levels.get(s, 0) < self.levels.get(t, 0)
        ]
        min_cross_derived_delta = min(cross_level_derived)
        max_primitive_delta = max(
            d for (s, t), d in self.deltas.items()
            if self.levels.get(t, 0) <= 3 and self.levels.get(s, 0) <= 3
            and (s, t) != ("historization", "difference")  # cycle closure is special
        )
        self.assertGreaterEqual(min_cross_derived_delta, max_primitive_delta)

    def test_mass_highest_canonical_delta(self):
        """The edge to mass has the highest canonical Δ (most emergent)."""
        mass_delta = self.deltas[("historization", "mass")]
        self.assertEqual(mass_delta, 1.0)

    def test_confidence_decreases_with_derivation(self):
        """Confidence decreases for more derived concepts."""
        confidences = {}
        for e in self.spec["edges"]:
            confidences[(e["from"], e["to"])] = e.get("confidence", 1.0)

        # Primitive edge confidence
        prim_conf = confidences[("difference", "local_realization")]
        # Most derived canonical edge confidence
        mass_conf = confidences[("historization", "mass")]
        self.assertGreater(prim_conf, mass_conf)


# ──────────────────────────────────────────────
# 8. Initial Traces
# ──────────────────────────────────────────────

class TestCanonTraces(unittest.TestCase):
    """Verify initial traces are injected by the Bootstrapper."""

    def setUp(self):
        self.ls = load_canon("ontodynamics").landscape

    def test_primitive_edges_have_traces(self):
        """Primitive derivation edges should have U-traces."""
        edge = Edge("difference", "local_realization")
        tl = self.ls.historization.trace_load(edge)
        self.assertGreater(tl, 0.0)

    def test_primitive_edges_positive_quality(self):
        """Primitive edges have high confidence → positive quality."""
        edge = Edge("difference", "local_realization")
        q = self.ls.historization.trace_quality(edge)
        self.assertGreater(q, 0.5)

    def test_mass_edge_cautious_quality(self):
        """The mass edge (confidence=0.5) should have near-zero quality."""
        edge = Edge("historization", "mass")
        q = self.ls.historization.trace_quality(edge)
        # confidence=0.5, U=3, F=2 → heavily moderated
        self.assertLess(q, 0.5)

    def test_overlap_to_historization_has_traces(self):
        """The stability edge (overlap→historization) should have traces."""
        edge = Edge("overlap", "historization")
        tl = self.ls.historization.trace_load(edge)
        self.assertGreater(tl, 0.0)


# ──────────────────────────────────────────────
# 9. Navigability with E0Controller
# ──────────────────────────────────────────────

class TestCanonNavigation(unittest.TestCase):
    """E0Controller can navigate the materialized canon landscape."""

    def setUp(self):
        from e0_controller.controller import E0Controller
        self.cl = load_canon("ontodynamics")
        self.ctrl = E0Controller(
            self.cl.landscape,
            lambda s, t: Outcome.SUCCESS,
        )

    def test_cycle_from_difference(self):
        """Controller can run a cycle starting from difference."""
        result = self.ctrl.cycle("difference")
        self.assertIsNotNone(result)

    def test_navigate_spine(self):
        """Can navigate multiple steps from difference."""
        current = "difference"
        for _ in range(3):
            result = self.ctrl.cycle(current)
            self.assertIsNotNone(result)
            current = result.target

    def test_navigate_from_historization(self):
        """Can navigate from historization (hub with many outgoing edges)."""
        result = self.ctrl.cycle("historization")
        self.assertIsNotNone(result)

    def test_run_multi_step(self):
        """Multi-step traversal through the canon."""
        results = []
        current = "difference"
        for _ in range(5):
            r = self.ctrl.cycle(current)
            if r is None:
                break
            results.append(r)
            current = r.target
        self.assertGreaterEqual(len(results), 3)


# ──────────────────────────────────────────────
# 10. LLM Summary Formatting
# ──────────────────────────────────────────────

class TestFormatCanonSummary(unittest.TestCase):
    """Human-readable formatting for LLM context."""

    def setUp(self):
        self.info = _extract_info(load_canon_spec("ontodynamics"))
        self.summary = format_canon_summary(self.info)

    def test_contains_canon_name(self):
        self.assertIn("ontodynamics", self.summary)

    def test_contains_version(self):
        self.assertIn("v2.0", self.summary)

    def test_contains_primitive_tier(self):
        self.assertIn("Primitive", self.summary)

    def test_contains_derived_tier(self):
        self.assertIn("Derived", self.summary)

    def test_contains_all_concept_labels(self):
        labels = [n.label for n in self.info.nodes]
        for label in labels:
            self.assertIn(label, self.summary)

    def test_contains_derivation_relationships(self):
        self.assertIn("difference -> local_realization", self.summary)

    def test_contains_goal_states(self):
        self.assertIn("negative_necessity", self.summary)

    def test_contains_consequences(self):
        self.assertIn("irreversibility", self.summary)

    def test_summary_is_multiline(self):
        lines = self.summary.split("\n")
        self.assertGreater(len(lines), 20)


# ──────────────────────────────────────────────
# 11. Graph Quality
# ──────────────────────────────────────────────

class TestCanonGraphQuality(unittest.TestCase):
    """The ontodynamics landscape passes graph quality checks."""

    def test_quality_no_traps_mass(self):
        """Sink nodes are structural endpoints, not accidental traps."""
        ls = load_canon("ontodynamics").landscape
        gq = graph_quality(ls, "difference", "mass")
        trap_set = set(gq.traps)
        # v2 has many leaf nodes by design (sleep_wake_cycle, negative_necessity, etc.)
        # Just verify no canonical primitive is a trap
        canonical_primitives = {"difference", "local_realization", "connection", "overlap", "historization"}
        unexpected = trap_set & canonical_primitives
        self.assertEqual(unexpected, set(), f"Primitives should not be traps: {unexpected}")

    def test_quality_to_negative_necessity(self):
        """The full journey from difference to negative_necessity."""
        ls = load_canon("ontodynamics").landscape
        gq = graph_quality(ls, "difference", "negative_necessity")
        # Just verify the path exists (no traps block it)
        self.assertTrue(goal_reachable(ls, "difference", "negative_necessity"))

    def test_quality_no_trivial_loops(self):
        ls = load_canon("ontodynamics").landscape
        gq = graph_quality(ls, "differenz", "negative_notwendigkeit")
        self.assertEqual(len(gq.trivial_loops), 0)


if __name__ == "__main__":
    unittest.main()
