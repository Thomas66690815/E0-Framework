"""
E₀ Controller v0.2
===================
Deterministic Transition Order for Historically Stabilized Intelligence.

Phase 1 (§2–6, §17–18):
  - Primitives: State, Δ, R, Tension S, Coherence C
  - Landscape: L_t = (X, E, v, S, H)
  - Historization: U/F-Traces, δ_H, Clipping
  - Controller: candidates → argmin S_eff → escalate → execute → historize

Phase 2 (§9–16):
  - Potential: Φ(x), v_grad, v_rot (discrete spec-aligned decomposition)
  - Connection: ω(x,y), Θ(path), Holonomy
  - Wave Path: Ψ(p) = exp(−S+iΘ), Pfad-Summation, Interferenz

See E0_CONTROLLER_STATUS.md for full project context.
"""

__version__ = "0.2.0"

from .primitives import Edge, Outcome
from .historization import Historization, TraceRecord
from .tension import tension, path_tension, coherence
from .landscape import Landscape
from .controller import E0Controller, StepResult, RunTrace, EscalationType
from .potential import phi, phi_map, v_raw, v_grad, v_rot, decomposition
from .connection import omega, theta, holonomy, omega_map
from .wavepath import psi, path_intensity, sum_paths, intensity, interference_analysis
