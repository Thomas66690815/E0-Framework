"""
C269 — Parameter-Default Regression Tests (Audit Rule 3)
============================================================
Each test asserts that a code default matches the value stated
in the corresponding paper.  If a default changes, the paper
must be updated (or the test explicitly adjusted with a commit
reference explaining why).

Cross-reference: docs/E0_PAPER_AUDIT_v1.md §7.1 Rule 3

Papers referenced:
  P1 = docs/papers/PAPER1_MANUSCRIPT_v1.md
  P5 = docs/papers/PAPER5_MANUSCRIPT_v1.md
  P6 = docs/papers/PAPER6_MANUSCRIPT_v1.md
"""

import inspect
import unittest

from e0_controller.config import E0Config, DEFAULTS
from e0_controller.historization import Historization
from e0_controller.multiverse import NoveltyGate
from e0_controller.scoped_reflexion import (
    compute_reflexion_scope,
    landscape_mu,
)
from e0_controller.emergent_locality import (
    snapshot_locality,
    track_locality_evolution,
    track_inscription_locality,
    track_nonuniform_convergence,
    compute_regional_profile,
    find_phase_transition,
    LocalityEvolution,
)
from e0_controller.primitives import Edge
from e0_controller.landscape import Landscape


class TestPaper1Defaults(unittest.TestCase):
    """P1 §9.1 states: α=2.0, k=3, ρ=0.9, λ_s=0.15, λ_f=0.20, δ_max=3.0"""

    def test_alpha(self):
        self.assertEqual(DEFAULTS.alpha, 2.0)

    def test_recent_k(self):
        self.assertEqual(DEFAULTS.recent_k, 3)

    def test_rho(self):
        self.assertEqual(DEFAULTS.rho, 0.9)

    def test_lambda_s(self):
        self.assertEqual(DEFAULTS.lambda_s, 0.15)

    def test_lambda_f(self):
        self.assertEqual(DEFAULTS.lambda_f, 0.20)

    def test_delta_max(self):
        self.assertEqual(DEFAULTS.delta_max, 3.0)


class TestPaper5Defaults(unittest.TestCase):
    """P5 §2.2: inertia_alpha=0.5. P5 §4.1/§10.4: μ defaults."""

    def test_inertia_alpha(self):
        """P5 §2.2: α=0.5 (maximum dampening)."""
        self.assertEqual(DEFAULTS.inertia_alpha, 0.5)

    def test_global_mu(self):
        """DEFAULTS.mu=5.0 — used by sleep_wake, dream_mode, etc.
        P5 §2.2 mentions μ=5.0 as half-activation threshold."""
        self.assertEqual(DEFAULTS.mu, 5.0)

    def test_locality_mu_topology_derived(self):
        """P5 §10.4 (C105): locality μ = |E|/|V| (mean out-degree).
        emergent_locality and scoped_reflexion default to None → derived."""
        sig = inspect.signature(compute_reflexion_scope)
        self.assertIsNone(sig.parameters["mu"].default)

        sig = inspect.signature(snapshot_locality)
        self.assertIsNone(sig.parameters["mu"].default)

    def test_landscape_mu_formula(self):
        """landscape_mu() returns |E|/|V| for a known graph."""
        L = Landscape()
        L.add_edge("A", "B", delta=1.0, resistance=1.0)
        L.add_edge("B", "C", delta=1.0, resistance=1.0)
        L.add_edge("C", "A", delta=1.0, resistance=1.0)
        # 3 edges, 3 nodes → μ = 1.0
        self.assertAlmostEqual(landscape_mu(L), 1.0)

    def test_landscape_mu_dense(self):
        """Dense graph: μ scales with out-degree."""
        L = Landscape()
        nodes = ["A", "B", "C"]
        for s in nodes:
            for t in nodes:
                if s != t:
                    L.add_edge(s, t, delta=1.0, resistance=1.0)
        # 6 edges, 3 nodes → μ = 2.0
        self.assertAlmostEqual(landscape_mu(L), 2.0)

    def test_emergent_locality_defaults_none(self):
        """All emergent_locality public functions default mu=None (C269)."""
        for fn in [snapshot_locality, track_locality_evolution,
                   track_inscription_locality, track_nonuniform_convergence,
                   compute_regional_profile, find_phase_transition]:
            sig = inspect.signature(fn)
            self.assertIsNone(
                sig.parameters["mu"].default,
                f"{fn.__name__} should default mu=None"
            )

    def test_locality_evolution_dataclass_default(self):
        """LocalityEvolution.mu defaults to None (topology-derived)."""
        evo = LocalityEvolution()
        self.assertIsNone(evo.mu)


class TestPaper6Defaults(unittest.TestCase):
    """P6 §4.3: NoveltyGate θ — paper will be updated to state 0.0 (F6)."""

    def test_novelty_gate_threshold(self):
        """Code default θ=0.0 (any positive Δ-growth = novelty).
        Paper 6 will be updated from 0.5 to 0.0 per F6."""
        gate = NoveltyGate()
        self.assertEqual(gate.delta_threshold, 0.0)


class TestHistorizationDefaults(unittest.TestCase):
    """Historization parameters derive from DEFAULTS (config.py)."""

    def test_historization_uses_config_rho(self):
        """Historization default ρ matches DEFAULTS.rho."""
        h = Historization()
        self.assertEqual(h.rho, DEFAULTS.rho)

    def test_historization_uses_config_lambdas(self):
        h = Historization()
        self.assertEqual(h.lambda_s, DEFAULTS.lambda_s)
        self.assertEqual(h.lambda_f, DEFAULTS.lambda_f)

    def test_historization_uses_config_delta_max(self):
        h = Historization()
        self.assertEqual(h.delta_max, DEFAULTS.delta_max)


if __name__ == "__main__":
    unittest.main()
