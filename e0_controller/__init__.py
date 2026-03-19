"""
E₀ Controller v0.1
===================
Deterministic Transition Order for Historically Stabilized Intelligence.

Implements §2–6, §17–18 of the E₀ Controller Specification:
  - Primitives: State, Δ, R, Tension S, Coherence C
  - Landscape: L_t = (X, E, v, S, H)
  - Historization: U/F-Traces, δ_H, Clipping
  - Controller: candidates → argmin S_eff → escalate → execute → historize

See E0_CONTROLLER_STATUS.md for full project context.
"""

__version__ = "0.1.0"

from .primitives import Edge, Outcome
from .historization import Historization, TraceRecord
from .tension import tension, path_tension, coherence
from .landscape import Landscape
from .controller import E0Controller, StepResult, RunTrace
