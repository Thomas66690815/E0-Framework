# E₀ — Computational Core
# A Python implementation of E₀ pre-domain ontodynamics
#
# This package maps the seven canonical primitives and Axiom A₀
# into executable code, demonstrating how LLM-like inference
# can be understood as E₀-governed transition dynamics.
#
# Architecture (3 layers):
#   ontodynamics.py  — Layer 0: Admissibility (what CAN be real)
#   primitives.py    — Layer 1: E₀ Primitives (S, Δ, P, R, H, τ, v)
#   engine.py        — Layer 1: Axiom A₀ + Central Law
#   guards.py        — Layer 1→0: Structural Admissibility Guards
#   reflexivity.py   — Layer 2: Self-Modeling Loop
#   llm_mapping.py   — Layer 2: LLM structural isomorphism

from .primitives import State, Path, Historization, HistorizationEvent, difference, rate
from .engine import TransitionEngine, TransitionResult, axiom_a0
from .ontodynamics import (
    DirectedDifference, Connection, Topology, OntodynamicAdmissibility,
)
from .guards import StructuralGuard, AdmissibilityVerdict, ViolationType
from .reflexivity import ReflexiveEngine, MetaState
