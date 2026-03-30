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
        self.assertEqual(spec["version"], "1.2")

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
        self.assertEqual(self.info.version, "1.2")

    def test_source_reference(self):
        self.assertIn("ontodynamics.txt", self.info.source)
        self.assertIn("e0-canon-plain.txt", self.info.source)
        self.assertIn("e0-agi-blueprint.md", self.info.source)

    def test_node_count(self):
        self.assertEqual(len(self.info.nodes), 19)

    def test_edge_count(self):
        self.assertEqual(len(self.info.edges), 31)

    def test_five_primitives(self):
        primitives = [n for n in self.info.nodes if n.is_primitive]
        self.assertEqual(len(primitives), 5)
        primitive_ids = {n.id for n in primitives}
        self.assertEqual(primitive_ids, {
            "differenz", "lokale_realisierung", "verbindung",
            "gradueller_overlap", "historisierung",
        })

    def test_derived_concepts(self):
        derived = [n for n in self.info.nodes if not n.is_primitive]
        self.assertEqual(len(derived), 14)
        derived_ids = {n.id for n in derived}
        self.assertEqual(derived_ids, {
            "zustand", "widerstand", "zeit",
            "rate", "raumzeit", "masse",
            "pfad", "axiom_a0",
            "operationaler_zyklus", "strukturelle_zulaessigkeit",
            "reflexivitaet", "strukturelle_ausrichtung",
            "domaeneninvarianz", "negative_notwendigkeit",
        })

    def test_derivation_levels(self):
        levels = {n.id: n.derivation_level for n in self.info.nodes}
        self.assertEqual(levels["differenz"], 0)
        self.assertEqual(levels["lokale_realisierung"], 1)
        self.assertEqual(levels["verbindung"], 2)
        # overlap and historisierung at level 3
        self.assertEqual(levels["gradueller_overlap"], 3)
        self.assertEqual(levels["historisierung"], 3)
        # derived at levels 4-5
        self.assertGreaterEqual(levels["zustand"], 4)
        self.assertGreaterEqual(levels["masse"], 5)
        # Canon Plain additions
        self.assertEqual(levels["pfad"], 4)
        self.assertEqual(levels["axiom_a0"], 5)
        # Blueprint additions
        self.assertEqual(levels["operationaler_zyklus"], 6)
        self.assertEqual(levels["strukturelle_zulaessigkeit"], 6)
        self.assertEqual(levels["reflexivitaet"], 7)
        self.assertEqual(levels["strukturelle_ausrichtung"], 7)
        self.assertEqual(levels["domaeneninvarianz"], 7)
        self.assertEqual(levels["negative_notwendigkeit"], 8)

    def test_goal_states(self):
        self.assertEqual(self.info.goal_states, ["negative_notwendigkeit"])

    def test_necessary_consequences(self):
        self.assertEqual(len(self.info.necessary_consequences), 10)
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
        self.assertEqual(len(self.bs_spec["nodes"]), 19)

    def test_edge_count_preserved(self):
        self.assertEqual(len(self.bs_spec["edges"]), 31)

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
        expected = {
            "differenz", "lokale_realisierung", "verbindung",
            "gradueller_overlap", "historisierung",
            "zustand", "widerstand", "zeit",
            "rate", "raumzeit", "masse",
            "pfad", "axiom_a0",
            "operationaler_zyklus", "strukturelle_zulaessigkeit",
            "reflexivitaet", "strukturelle_ausrichtung",
            "domaeneninvarianz", "negative_notwendigkeit",
        }
        self.assertEqual(states, expected)

    def test_landscape_has_edges(self):
        edges = self.cl.landscape.edges
        self.assertEqual(len(edges), 31)

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
            ("differenz", "lokale_realisierung"),
            ("lokale_realisierung", "verbindung"),
            ("verbindung", "gradueller_overlap"),
            ("verbindung", "historisierung"),
        ]
        edge_set = {(e.source, e.target) for e in self.ls.edges}
        for src, tgt in spine:
            self.assertIn((src, tgt), edge_set, f"Missing spine edge {src}→{tgt}")

    def test_cycle_closure(self):
        """historisierung → differenz closes the ontological cycle."""
        edge_set = {(e.source, e.target) for e in self.ls.edges}
        self.assertIn(("historisierung", "differenz"), edge_set)

    def test_goal_reachable_from_differenz(self):
        """masse must be reachable from differenz."""
        self.assertTrue(goal_reachable(self.ls, "differenz", "masse"))

    def test_all_primitives_reach_historisierung(self):
        """Every primitive can reach historisierung."""
        primitives = [
            "differenz", "lokale_realisierung", "verbindung",
            "gradueller_overlap",
        ]
        for p in primitives:
            self.assertTrue(
                goal_reachable(self.ls, p, "historisierung"),
                f"{p} cannot reach historisierung",
            )

    def test_happy_path_to_masse(self):
        """A path from differenz to masse must exist."""
        path = find_happy_path(self.ls, "differenz", "masse")
        self.assertIsNotNone(path)
        self.assertGreater(len(path), 0)

    def test_raumzeit_needs_two_inputs(self):
        """raumzeit receives from both zustand and zeit."""
        incoming = [
            e for e in self.ls.edges if e.target == "raumzeit"
        ]
        sources = {e.source for e in incoming}
        self.assertIn("zustand", sources)
        self.assertIn("zeit", sources)

    def test_historisierung_is_hub(self):
        """historisierung has the most outgoing edges (hub concept)."""
        out_counts = {}
        for e in self.ls.edges:
            out_counts[e.source] = out_counts.get(e.source, 0) + 1
        max_out = max(out_counts.values())
        self.assertEqual(out_counts["historisierung"], max_out)

    def test_pfad_requires_verbindung_and_widerstand(self):
        """Path derives from Connection + Resistance."""
        incoming = [e for e in self.ls.edges if e.target == "pfad"]
        sources = {e.source for e in incoming}
        self.assertIn("verbindung", sources)
        self.assertIn("widerstand", sources)

    def test_axiom_a0_requires_differenz_and_pfad(self):
        """A0 derives from Difference + Path."""
        incoming = [e for e in self.ls.edges if e.target == "axiom_a0"]
        sources = {e.source for e in incoming}
        self.assertIn("differenz", sources)
        self.assertIn("pfad", sources)

    def test_pfad_feeds_rate(self):
        """Rate is realized along structurally admissible paths."""
        edge_set = {(e.source, e.target) for e in self.ls.edges}
        self.assertIn(("pfad", "rate"), edge_set)

    def test_rate_has_two_inputs(self):
        """Rate receives from both Resistance and Path."""
        incoming = [e for e in self.ls.edges if e.target == "rate"]
        sources = {e.source for e in incoming}
        self.assertIn("widerstand", sources)
        self.assertIn("pfad", sources)

    def test_axiom_a0_reachable_from_differenz(self):
        """The foundational axiom must be reachable from differenz."""
        self.assertTrue(goal_reachable(self.ls, "differenz", "axiom_a0"))

    # ── Blueprint topology ──

    def test_operationaler_zyklus_requires_axiom_and_historisierung(self):
        """The cycle instantiates A0 with historization."""
        incoming = [e for e in self.ls.edges if e.target == "operationaler_zyklus"]
        sources = {e.source for e in incoming}
        self.assertIn("axiom_a0", sources)
        self.assertIn("historisierung", sources)

    def test_reflexivitaet_requires_cycle_and_historisierung(self):
        """Reflexivity emerges from the cycle operating on itself + historization."""
        incoming = [e for e in self.ls.edges if e.target == "reflexivitaet"]
        sources = {e.source for e in incoming}
        self.assertIn("operationaler_zyklus", sources)
        self.assertIn("historisierung", sources)

    def test_negative_notwendigkeit_has_three_inputs(self):
        """The thesis derives from reflexivity, alignment, and domain invariance."""
        incoming = [e for e in self.ls.edges if e.target == "negative_notwendigkeit"]
        sources = {e.source for e in incoming}
        self.assertEqual(sources, {"reflexivitaet", "strukturelle_ausrichtung", "domaeneninvarianz"})

    def test_full_journey_differenz_to_negative_notwendigkeit(self):
        """The full derivation path from differenz to negative_notwendigkeit must exist."""
        self.assertTrue(goal_reachable(self.ls, "differenz", "negative_notwendigkeit"))

    def test_happy_path_to_negative_notwendigkeit(self):
        """A happy path from differenz to the thesis must exist."""
        path = find_happy_path(self.ls, "differenz", "negative_notwendigkeit")
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
            ("differenz", "lokale_realisierung"),
            ("lokale_realisierung", "verbindung"),
        ]
        for src, tgt in primitive_edges:
            self.assertLessEqual(
                self.deltas[(src, tgt)], 0.4,
                f"Primitive edge {src}→{tgt} should have low Δ",
            )

    def test_derived_edges_higher_delta(self):
        """Cross-level edges to derived concepts have higher Δ than primitive edges."""
        # Only consider edges that cross from a lower level to a higher level
        cross_level_derived = [
            d for (s, t), d in self.deltas.items()
            if self.levels.get(t, 0) >= 4
            and self.levels.get(s, 0) < self.levels.get(t, 0)
        ]
        min_cross_derived_delta = min(cross_level_derived)
        max_primitive_delta = max(
            d for (s, t), d in self.deltas.items()
            if self.levels.get(t, 0) <= 3 and self.levels.get(s, 0) <= 3
            and (s, t) != ("historisierung", "differenz")  # cycle closure is special
        )
        self.assertGreaterEqual(min_cross_derived_delta, max_primitive_delta)

    def test_masse_highest_delta(self):
        """The edge to masse has the highest Δ (most emergent)."""
        masse_delta = self.deltas[("historisierung", "masse")]
        self.assertEqual(masse_delta, 1.0)

    def test_confidence_decreases_with_derivation(self):
        """Confidence decreases for more derived concepts."""
        confidences = {}
        for e in self.spec["edges"]:
            confidences[(e["from"], e["to"])] = e.get("confidence", 1.0)

        # Primitive edge confidence
        prim_conf = confidences[("differenz", "lokale_realisierung")]
        # Most derived edge confidence
        masse_conf = confidences[("historisierung", "masse")]
        self.assertGreater(prim_conf, masse_conf)


# ──────────────────────────────────────────────
# 8. Initial Traces
# ──────────────────────────────────────────────

class TestCanonTraces(unittest.TestCase):
    """Verify initial traces are injected by the Bootstrapper."""

    def setUp(self):
        self.ls = load_canon("ontodynamics").landscape

    def test_primitive_edges_have_traces(self):
        """Primitive derivation edges should have U-traces."""
        edge = Edge("differenz", "lokale_realisierung")
        tl = self.ls.historization.trace_load(edge)
        self.assertGreater(tl, 0.0)

    def test_primitive_edges_positive_quality(self):
        """Primitive edges have high confidence → positive quality."""
        edge = Edge("differenz", "lokale_realisierung")
        q = self.ls.historization.trace_quality(edge)
        self.assertGreater(q, 0.5)

    def test_masse_edge_cautious_quality(self):
        """The masse edge (confidence=0.5) should have near-zero quality."""
        edge = Edge("historisierung", "masse")
        q = self.ls.historization.trace_quality(edge)
        # confidence=0.5, U=3, F=2 → heavily moderated
        self.assertLess(q, 0.5)

    def test_overlap_to_historisierung_has_traces(self):
        """The stability edge (overlap→historisierung) should have traces."""
        edge = Edge("gradueller_overlap", "historisierung")
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

    def test_cycle_from_differenz(self):
        """Controller can run a cycle starting from differenz."""
        result = self.ctrl.cycle("differenz")
        self.assertIsNotNone(result)

    def test_navigate_spine(self):
        """Can navigate multiple steps from differenz."""
        current = "differenz"
        for _ in range(3):
            result = self.ctrl.cycle(current)
            self.assertIsNotNone(result)
            current = result.target

    def test_navigate_from_historisierung(self):
        """Can navigate from historisierung (hub with many outgoing edges)."""
        result = self.ctrl.cycle("historisierung")
        self.assertIsNotNone(result)

    def test_run_multi_step(self):
        """Multi-step traversal through the canon."""
        results = []
        current = "differenz"
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
        self.assertIn("v1.2", self.summary)

    def test_contains_primitive_tier(self):
        self.assertIn("Primitive", self.summary)

    def test_contains_derived_tier(self):
        self.assertIn("Derived", self.summary)

    def test_contains_all_concept_labels(self):
        labels = [n.label for n in self.info.nodes]
        for label in labels:
            self.assertIn(label, self.summary)

    def test_contains_derivation_relationships(self):
        self.assertIn("differenz -> lokale_realisierung", self.summary)

    def test_contains_goal_states(self):
        self.assertIn("negative_notwendigkeit", self.summary)

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

    def test_quality_no_traps_masse(self):
        """Only terminal derivations (leaves) are traps — no structural traps."""
        ls = load_canon("ontodynamics").landscape
        gq = graph_quality(ls, "differenz", "masse")
        trap_set = set(gq.traps)
        # raumzeit, strukturelle_zulaessigkeit are terminal; negative_notwendigkeit is goal but also leaf
        expected_traps = {"raumzeit", "strukturelle_zulaessigkeit", "negative_notwendigkeit"}
        self.assertTrue(trap_set.issubset(expected_traps), f"Unexpected traps: {trap_set - expected_traps}")

    def test_quality_to_negative_notwendigkeit(self):
        """The full journey from differenz to negative_notwendigkeit."""
        ls = load_canon("ontodynamics").landscape
        gq = graph_quality(ls, "differenz", "negative_notwendigkeit")
        trap_set = set(gq.traps)
        expected_traps = {"raumzeit", "masse", "strukturelle_zulaessigkeit"}
        self.assertTrue(trap_set.issubset(expected_traps), f"Unexpected traps: {trap_set - expected_traps}")

    def test_quality_no_trivial_loops(self):
        ls = load_canon("ontodynamics").landscape
        gq = graph_quality(ls, "differenz", "negative_notwendigkeit")
        self.assertEqual(len(gq.trivial_loops), 0)


if __name__ == "__main__":
    unittest.main()
