"""
E₀ Controller v0.3
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

Phase 2c (MemOS):
  - Persist / Restore / Summarize / Retrieve
  - Session-persistent E₀ state management

Phase 3a (LLM Adapter):
  - extract_delta / propose_states / execute_transition
  - Structured LLM ↔ Controller interface (A3 Hybrid)

See E0_CONTROLLER_STATUS.md for full project context.
"""

__version__ = "0.3.0"

from .primitives import Edge, Outcome
from .historization import Historization, TraceRecord
from .tension import tension, path_tension, coherence
from .landscape import Landscape
from .controller import E0Controller, StepResult, RunTrace, EscalationType
from .potential import phi, phi_map, v_raw, v_grad, v_rot, decomposition
from .connection import omega, theta, holonomy, omega_map
from .wavepath import psi, path_intensity, sum_paths, intensity, interference_analysis
from .memory_os import E0MemoryOS, CanonRef, MemOSContext
from .llm_adapter import E0LLMAdapter, LLMConfig, DeltaEstimate, ProposedState, TransitionResult
