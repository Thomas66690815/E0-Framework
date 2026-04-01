"""
Tests for E₀ Rendering Adapter (C96)
======================================
Wire-format snapshot from observation projection.
"""

from __future__ import annotations

import unittest

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.observation_controller import ObservationController
from e0_controller.rendering_adapter import (
    render_observation,
    render_observation_landscape,
)


# ── Helpers ──────────────────────────────────────────────

def _triangle() -> Landscape:
    L = Landscape()
    L.add_edge("A", "B", delta=0.5, resistance=0.3)
    L.add_edge("B", "C", delta=0.5, resistance=0.3)
    L.add_edge("C", "A", delta=0.5, resistance=0.3)
    return L


def _greedy_trap() -> Landscape:
    L = Landscape()
    L.add_edge("S", "A", delta=0.3, resistance=0.4)
    L.add_edge("A", "B", delta=0.3, resistance=0.5)
    L.add_edge("B", "D", delta=0.3, resistance=0.5)
    L.add_edge("D", "GOAL", delta=0.2, resistance=0.3)
    L.add_edge("A", "C", delta=0.2, resistance=0.4)
    L.add_edge("C", "A", delta=0.2, resistance=0.4)
    return L


# ══════════════════════════════════════════════════════════
# 1. Basic Snapshot Structure
# ══════════════════════════════════════════════════════════

class TestSnapshotStructure(unittest.TestCase):

    def test_has_required_keys(self):
        oc = ObservationController(_triangle())
        snap = render_observation(oc)
        self.assertIn("states", snap)
        self.assertIn("edges", snap)
        self.assertIn("modulation", snap)
        self.assertIn("observation", snap)

    def test_states_list(self):
        oc = ObservationController(_triangle())
        snap = render_observation(oc)
        self.assertEqual(sorted(snap["states"]), ["A", "B", "C"])

    def test_edges_dict(self):
        oc = ObservationController(_triangle())
        snap = render_observation(oc)
        self.assertIsInstance(snap["edges"], dict)
        self.assertEqual(len(snap["edges"]), 3)

    def test_edge_keys_use_arrow(self):
        oc = ObservationController(_triangle())
        snap = render_observation(oc)
        for key in snap["edges"]:
            self.assertIn("→", key)

    def test_modulation_defaults(self):
        oc = ObservationController(_triangle())
        snap = render_observation(oc)
        mod = snap["modulation"]
        self.assertFalse(mod["curvature"])
        self.assertFalse(mod["overlap"])
        self.assertFalse(mod["inertia"])


# ══════════════════════════════════════════════════════════
# 2. Edge Data at Different Depths
# ══════════════════════════════════════════════════════════

class TestEdgeData(unittest.TestCase):

    def test_topo_depth_has_zero_values(self):
        """At topo depth, all numeric values are zero (structure only)."""
        oc = ObservationController(_triangle())
        snap = render_observation(oc)
        for key, e in snap["edges"].items():
            self.assertEqual(e["delta"], 0.0)
            self.assertEqual(e["R0"], 0.0)
            self.assertEqual(e["S_eff"], 0.0)
            self.assertEqual(e["trace_load"], 0.0)

    def test_field_depth_has_real_values(self):
        """At field depth, Δ, R₀, R_eff, S_eff are populated."""
        oc = ObservationController(_triangle())
        oc.deepen()
        snap = render_observation(oc)
        e = snap["edges"]["A→B"]
        self.assertAlmostEqual(e["delta"], 0.5)
        self.assertAlmostEqual(e["R0"], 0.3)
        self.assertGreater(e["R_eff"], 0)
        self.assertGreater(e["S_eff"], 0)

    def test_field_has_coherence(self):
        oc = ObservationController(_triangle())
        oc.deepen()
        snap = render_observation(oc)
        e = snap["edges"]["A→B"]
        self.assertIn("coherence", e)
        self.assertGreater(e["coherence"], 0)
        self.assertLessEqual(e["coherence"], 1.0)

    def test_field_has_delta_H(self):
        oc = ObservationController(_triangle())
        oc.deepen()
        snap = render_observation(oc)
        e = snap["edges"]["A→B"]
        self.assertIn("delta_H", e)

    def test_field_has_v(self):
        oc = ObservationController(_triangle())
        oc.deepen()
        snap = render_observation(oc)
        e = snap["edges"]["A→B"]
        self.assertIn("v", e)
        self.assertGreater(e["v"], 0)

    def test_dyn_depth_has_traces(self):
        """At dyn depth, historization traces are visible."""
        domain = _triangle()
        domain.historization.update(Edge("A", "B"), Outcome.SUCCESS)
        domain.historization.update(Edge("A", "B"), Outcome.SUCCESS)
        oc = ObservationController(domain)
        oc.deepen()
        oc.deepen()
        snap = render_observation(oc)
        e = snap["edges"]["A→B"]
        self.assertGreater(e["U"], 0)
        self.assertGreater(e["trace_load"], 0)
        self.assertGreater(e["trace_quality"], 0)

    def test_dyn_without_history_has_zero_traces(self):
        oc = ObservationController(_triangle())
        oc.deepen()
        oc.deepen()
        snap = render_observation(oc)
        e = snap["edges"]["A→B"]
        self.assertEqual(e["U"], 0.0)
        self.assertEqual(e["F"], 0.0)
        self.assertEqual(e["trace_load"], 0.0)

    def test_inertia_default_one(self):
        """Inertia = 1.0 when no trace_load."""
        oc = ObservationController(_triangle())
        snap = render_observation(oc)
        for e in snap["edges"].values():
            self.assertAlmostEqual(e["inertia"], 1.0)

    def test_inertia_with_history(self):
        """Inertia < 1.0 when trace_load > 0 and quality < 1."""
        domain = _triangle()
        # Mixed signals: some success, some failure
        for _ in range(5):
            domain.historization.update(Edge("A", "B"), Outcome.SUCCESS)
            domain.historization.update(Edge("A", "B"), Outcome.FAILURE)
        oc = ObservationController(domain)
        oc.deepen()
        oc.deepen()
        snap = render_observation(oc)
        e = snap["edges"]["A→B"]
        self.assertLess(e["inertia"], 1.0)

    def test_all_edges_have_required_fields(self):
        """Every edge has the full set of numeric fields."""
        required = {"source", "target", "delta", "R0", "R_eff", "S_eff",
                     "coherence", "delta_H", "v", "U", "F",
                     "trace_load", "trace_quality", "inertia"}
        oc = ObservationController(_triangle())
        snap = render_observation(oc)
        for key, e in snap["edges"].items():
            for field in required:
                self.assertIn(field, e, f"Missing {field} in {key}")


# ══════════════════════════════════════════════════════════
# 3. Scope Filtering
# ══════════════════════════════════════════════════════════

class TestScopeFiltering(unittest.TestCase):

    def test_global_shows_all_nodes(self):
        oc = ObservationController(_greedy_trap())
        snap = render_observation(oc)
        self.assertEqual(len(snap["states"]), 6)

    def test_local_limits_nodes(self):
        oc = ObservationController(_greedy_trap())
        oc.focus("A")
        snap = render_observation(oc)
        # A + neighborhood: S (incoming), B, C (outgoing)
        self.assertIn("A", snap["states"])
        self.assertIn("B", snap["states"])
        self.assertIn("C", snap["states"])
        self.assertIn("S", snap["states"])
        self.assertNotIn("D", snap["states"])
        self.assertNotIn("GOAL", snap["states"])

    def test_local_limits_edges(self):
        oc = ObservationController(_greedy_trap())
        oc.focus("A")
        snap = render_observation(oc)
        # Only edges between visible nodes
        for key, e in snap["edges"].items():
            self.assertIn(e["source"], snap["states"])
            self.assertIn(e["target"], snap["states"])

    def test_scope_change_updates_snapshot(self):
        oc = ObservationController(_greedy_trap())
        snap1 = render_observation(oc)
        oc.focus("D")
        snap2 = render_observation(oc)
        self.assertNotEqual(len(snap1["states"]), len(snap2["states"]))


# ══════════════════════════════════════════════════════════
# 4. Observation Metadata
# ══════════════════════════════════════════════════════════

class TestObservationMetadata(unittest.TestCase):

    def test_initial_metadata(self):
        oc = ObservationController(_triangle())
        snap = render_observation(oc)
        obs = snap["observation"]
        self.assertEqual(obs["state"], "g:topo")
        self.assertEqual(obs["scope"], "g")
        self.assertEqual(obs["depth"], "topo")
        self.assertEqual(obs["depth_index"], 0)
        self.assertIsNone(obs["focused_node"])
        self.assertEqual(obs["history"], [])

    def test_focused_metadata(self):
        oc = ObservationController(_triangle())
        oc.focus("B")
        snap = render_observation(oc)
        obs = snap["observation"]
        self.assertEqual(obs["scope"], "n:B")
        self.assertEqual(obs["focused_node"], "B")

    def test_options_present(self):
        oc = ObservationController(_triangle())
        snap = render_observation(oc)
        opts = snap["observation"]["options"]
        self.assertIsInstance(opts, list)
        self.assertGreater(len(opts), 0)
        # Each option has expected keys
        for o in opts:
            self.assertIn("target", o)
            self.assertIn("s_eff", o)
            self.assertIn("r_eff", o)
            self.assertIn("scope_change", o)
            self.assertIn("depth_change", o)

    def test_history_tracks_navigation(self):
        oc = ObservationController(_triangle())
        oc.deepen()
        oc.focus("A")
        snap = render_observation(oc)
        self.assertEqual(snap["observation"]["history"], ["g:topo", "g:field"])

    def test_info_present(self):
        oc = ObservationController(_triangle())
        snap = render_observation(oc)
        info = snap["observation"]["info"]
        self.assertIn("scope_desc", info)
        self.assertIn("depth_desc", info)


# ══════════════════════════════════════════════════════════
# 5. O-Landscape Meta-Snapshot
# ══════════════════════════════════════════════════════════

class TestOLandscapeSnapshot(unittest.TestCase):

    def test_has_structure(self):
        oc = ObservationController(_triangle())
        snap = render_observation_landscape(oc)
        self.assertIn("states", snap)
        self.assertIn("edges", snap)
        self.assertIn("observation", snap)

    def test_state_count(self):
        """O-Landscape for triangle: (1+3)×5 = 20 states."""
        oc = ObservationController(_triangle())
        snap = render_observation_landscape(oc)
        self.assertEqual(len(snap["states"]), 20)

    def test_edges_have_full_data(self):
        oc = ObservationController(_triangle())
        snap = render_observation_landscape(oc)
        required = {"source", "target", "delta", "R0", "R_eff", "S_eff",
                     "coherence", "delta_H", "v", "U", "F",
                     "trace_quality", "trace_load", "inertia"}
        for key, e in snap["edges"].items():
            for field in required:
                self.assertIn(field, e, f"Missing {field} in {key}")

    def test_meta_flag(self):
        oc = ObservationController(_triangle())
        snap = render_observation_landscape(oc)
        self.assertTrue(snap["observation"]["is_meta"])

    def test_current_state_tracked(self):
        oc = ObservationController(_triangle())
        oc.deepen()
        snap = render_observation_landscape(oc)
        self.assertEqual(snap["observation"]["state"], "g:field")


# ══════════════════════════════════════════════════════════
# 6. JSON Serializability
# ══════════════════════════════════════════════════════════

class TestJsonSafe(unittest.TestCase):

    def test_observation_snapshot_serializable(self):
        import json
        oc = ObservationController(_triangle())
        oc.deepen()
        oc.focus("A")
        snap = render_observation(oc)
        text = json.dumps(snap)
        self.assertIsInstance(text, str)

    def test_o_landscape_snapshot_serializable(self):
        import json
        oc = ObservationController(_triangle())
        snap = render_observation_landscape(oc)
        text = json.dumps(snap)
        self.assertIsInstance(text, str)


# ══════════════════════════════════════════════════════════
# 7. Composite Pipeline
# ══════════════════════════════════════════════════════════

class TestPipeline(unittest.TestCase):

    def test_drill_down_pipeline(self):
        """Full pipeline: navigate → project → render."""
        domain = _greedy_trap()
        # Simulate some domain activity
        domain.historization.update(Edge("S", "A"), Outcome.SUCCESS)
        domain.historization.update(Edge("A", "B"), Outcome.SUCCESS)
        domain.historization.update(Edge("A", "C"), Outcome.FAILURE)

        oc = ObservationController(domain)
        oc.focus("A")
        oc.deepen()
        oc.deepen()

        snap = render_observation(oc)

        # Verify scope: A + neighbors
        self.assertIn("A", snap["states"])
        self.assertNotIn("GOAL", snap["states"])

        # Verify depth: field + dynamics visible
        e = snap["edges"]["A→B"]
        self.assertGreater(e["delta"], 0)
        self.assertGreater(e["U"], 0)
        self.assertGreater(e["trace_load"], 0)

        # Failed edge visible too
        e_ac = snap["edges"]["A→C"]
        self.assertGreater(e_ac["F"], 0)
        self.assertLess(e_ac["trace_quality"], 0)

        # Observation metadata correct
        self.assertEqual(snap["observation"]["scope"], "n:A")
        self.assertEqual(snap["observation"]["depth"], "dyn")


if __name__ == "__main__":
    unittest.main()
