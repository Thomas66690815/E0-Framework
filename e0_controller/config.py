"""E₀ Parameter Registry — Central Default Configuration (C148)
================================================================
Every numerical default that governs E₀ behavior is defined here,
exactly once.  Module constructors import their defaults from this
registry instead of embedding magic numbers.

Design principles:
  1. Single source of truth — change a default here, it changes everywhere.
  2. No new behavior — this is pure transparency.
  3. Frozen dataclass — immutable after creation, safe to share.
  4. Grouped by subsystem — controller, historization, diagnosis, etc.
  5. Each field is documented with its purpose and canonical range.

Usage:
    from e0_controller.config import DEFAULTS

    # Read a default:
    alpha = DEFAULTS.alpha              # 2.0

    # Create a modified config:
    custom = E0Config(alpha=1.5)        # everything else stays default

    # Pass to constructor:
    ctrl = E0Controller(L, exec_fn, alpha=custom.alpha)

Future (C150+): adaptive parameter tuning via Self-Graph attribution.
The registry makes this possible by centralizing what "default" means.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class E0Config:
    """Central parameter registry for the E₀ framework.

    All numerical defaults in one place.  Grouped by subsystem.
    """

    # ── Controller (controller.py) ───────────────────────────────
    # Revisit penalty: penalizes recently-visited states.
    # Higher α = stronger avoidance of revisits.
    alpha: float = 2.0

    # Number of recent states subject to revisit penalty.
    recent_k: int = 3

    # Maximum base resistance assigned during escalation.
    max_escalation_R: float = 5.0

    # Admissibility filter: maximum tension (K11).  inf = no filter.
    s_max: float = math.inf

    # Admissibility filter: minimum coherence (K11).  0.0 = no filter.
    c_min: float = 0.0

    # Amplitude overlay: bounded-horizon path count.
    hybrid_horizon: int = 3

    # Confidence threshold for amplitude override.
    # 0.0 = amplitude always active when mode allows.
    confidence_threshold: float = 0.0

    # Overload index threshold for peer consultation (C63).
    overload_threshold: float = 3.0

    # ── Historization (historization.py) ──────────────────────────
    # Decay rate: 0.0 = instant forget, 1.0 = perfect memory.
    rho: float = 0.9

    # Learning rates: how much each outcome adds to traces.
    lambda_s: float = 0.15  # success learning rate
    lambda_f: float = 0.20  # failure learning rate

    # Historization correction clipping bound.
    delta_max: float = 3.0

    # ── Half-load constant (mu) ──────────────────────────────────
    # Used in 5 subsystems for sigmoid normalization.
    # Controls the "experience threshold" — at load=mu, the
    # sigmoid is at 50%.  Below mu = under-explored.
    #   mode_controller.py:   under-explored edge detection
    #   sleep_wake.py:        dream pressure computation
    #   structural_entropy.py: inscription threshold + dream trigger
    #   dream_mode.py:        fingerprint distance normalization
    #   integrated_reflexion.py: scoped diagnosis
    mu: float = 5.0

    # ── Mode Controller (mode_controller.py) ─────────────────────
    # Fraction of under-explored edges that triggers LEARN mode.
    learn_ratio: float = 0.8

    # ── Self-Graph Diagnosis (dual_reflection.py) ────────────────
    # Minimum load before a component can be judged.
    sg_load_min: float = 3.0

    # |quality| below this with sufficient load = "confused".
    sg_quality_confused: float = 0.1

    # quality below this = "harmful" (deactivation candidate).
    sg_quality_harmful: float = -0.2

    # inertia below this = warning (contradictory data).
    sg_inertia_warn: float = 0.3

    # ── Self-Graph Topology (self_graph.py) ──────────────────────
    # Edge parameters for the 8-node self-knowledge graph.
    sg_core_delta: float = 0.5
    sg_core_R0: float = 0.3
    sg_modulation_delta: float = 1.0
    sg_modulation_R0: float = 1.0

    # Self-graph decay: 1.0 = cumulative (no forgetting).
    sg_rho: float = 1.0

    # ── Multiverse (multiverse.py) ───────────────────────────────
    # Cycles without novelty before divergence pressure.
    convergence_window: int = 3

    # Maximum controller steps per multiverse turn.
    max_steps_per_turn: int = 10

    # Delta and resistance for coupling edges.
    coupling_delta: float = 1.0
    coupling_resistance: float = 0.5

    # ── Dream Mode (dream_mode.py) ───────────────────────────────
    # Readiness threshold for dream cycle activation.
    dream_readiness: float = 0.8

    # Bottom quantile of pairwise distances = equivalences.
    dream_quantile: float = 0.1

    # Inertia dampening alpha: used in inertia_factor across all
    # subsystems (historization, dream, self-graph, coupling).
    # I(e) = 1 − α·(m/(m+μ))·(1−|q|).  Higher α = stronger dampening.
    inertia_alpha: float = 0.5

    # Base resistance for dream landscape edges.
    dream_base_resistance: float = 0.5

    # WL recursive fingerprint depth.
    wl_depth: int = 2

    # ── Sleep-Wake (sleep_wake.py) ───────────────────────────────
    # Safety cap on dream cycles per sleep phase.
    max_dream_cycles: int = 10

    # ── Structural Entropy (structural_entropy.py) ───────────────
    # Anchor threshold for decay candidate detection.
    theta_base: float = 0.5

    # ── Overlap (overlap.py) ─────────────────────────────────────
    # Floor for M_H on unsupported edges.
    overlap_floor: float = 0.2

    # ── Exploration Policy (exploration_policy.py) ────────────────
    # Warmup iterations using explore mode before exploitation.
    warmup: int = 0

    # Tension threshold for early warmup→exploit switch.
    convergence_threshold: float = 0.0

    # ── Reflexion (integrated_reflexion.py, cross_reflexion.py) ──
    # Maximum edge proposals per reflexion cycle.
    max_proposals: int = 5

    # Cross-reflexion: trust discount for foreign experience.
    coupling_discount: float = 0.5

    # Cross-reflexion: minimum gamma for proposal filtering.
    gamma_min: float = 0.3

    # ── Reflection Quality Thresholds (reflection.py) ────────────
    # These 14 constants define the boundaries between
    # quality grades (A/B/C/D/F) in the reflection system.
    refl_efficiency_floor: float = 0.0
    refl_quality_efficiency_ceil: float = 0.5
    refl_loop_penalty_ceil: float = 0.15
    refl_semantic_ceil: float = 0.6
    refl_escalation_ratio: float = 0.3
    refl_progress_floor: float = 0.5
    refl_opportunity_efficiency: float = 0.8
    refl_opportunity_graph_score: float = 0.9
    refl_amplitude_drift: float = 0.3
    refl_coherence_quality: float = 0.3
    refl_coherence_opportunity: float = 0.8
    refl_theta_opportunity: float = 0.9
    refl_mass_trap_imbalance: float = 3.0
    refl_plateau_slope: float = 0.01
    refl_chronic_ratio: float = 0.5

    # ── Bootstrapper (bootstrapper.py) ───────────────────────────
    # Coupling router base resistance and minimum delta.
    router_base_resistance: float = 1.0
    router_min_delta: float = 0.1

    def summary(self) -> str:
        """Human-readable summary of all non-default parameters."""
        default = E0Config()
        lines = []
        for f in self.__dataclass_fields__:
            val = getattr(self, f)
            default_val = getattr(default, f)
            if val != default_val:
                lines.append(f"  {f}: {default_val} → {val}")
        if not lines:
            return "E0Config: all defaults"
        return "E0Config (modified):\n" + "\n".join(lines)


# Singleton: the canonical defaults.
DEFAULTS = E0Config()
