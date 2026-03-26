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

Phase 3b (Live + Open Domain):
  - estimate_resistance / build_landscape / materialize_landscape
  - LLM-bootstrapped Landscapes for arbitrary domains
  - compare_runs for Mock vs. Live validation

Phase 3c (Graph Validation):
  - goal_reachable / find_happy_path / detect_traps / detect_trivial_loops
  - graph_quality — composite pre-run structural assessment

Phase 3d (Cross-Domain Validation + Live Context Fix):
  - validate_cross_domain — runs all 3 domains, compares metrics
  - live_summary in as_execute_fn — uses actual source state per call
  - result_log capture for LLM semantic output inspection

Phase 3e (Scenario Packets):
  - scenario_loader — load/validate JSON Scenario Packets
  - Scenario context injected into LLM prompts (execute + landscape)
  - --scenario flag on all demos, auto-discovery in validate_cross_domain
  - 100% live success rate with grounded source material

Phase 3f (Evaluation Layer):
  - evaluation.py — RunEvaluation, SemanticEvaluation, ScenarioEvaluation
  - Hard failure detection gates before overall scoring
  - A–F rating scale with efficiency, loops, semantic completeness
  - Integrated into validate_cross_domain report output

Phase 3g (Reflection Layer):
  - reflection.py — ReflectionDecision, ReflectionReport
  - should_reflect() trigger logic: failure / quality / opportunity
  - reflect() bounded self-reference with layer attribution
  - reflect_with_llm() — LLM-backed reflection with rule-based fallback
  - Integrated into validate_cross_domain report output

Phase 3h–3j (Amplitude & Summation Geometry):
  - True Helmholtz decomposition, amplitude overlay, diamond domain
  - Summation geometries: prefix, simple, first_arrival
  - 3 geometries × 3 domains empirical comparison

Phase 3k–3m (Hybrid Controller):
  - Simple-default + trace integration
  - Amplitude-hybrid B3: AMPLITUDE_ON_DISAGREE mode
  - MemOS hybrid-aware snapshot + overlay summary

Phase 3n (LLM Demo Hybrid Integration):
  - --hybrid flag on all 4 demos
  - Hybrid metrics display and override tracking

Phase 3o (Evaluation Layer Hybrid Extension):
  - Hybrid override/agree metrics in RunEvaluation
  - Hybrid rows in cross-domain validation comparison

See E0_CONTROLLER_STATUS.md for full project context.
"""

__version__ = "0.10.8"

from .primitives import Edge, Outcome
from .historization import Historization, TraceRecord
from .tension import tension, path_tension, coherence
from .landscape import Landscape
from .controller import E0Controller, StepResult, RunTrace, EscalationType, HybridMode
from .potential import (
    phi, phi_map, v_raw, v_grad, v_rot, decomposition,
    div_v, graph_laplacian,
)
from .connection import omega, theta, holonomy, omega_map
from .wavepath import psi, path_intensity, sum_paths, intensity, interference_analysis
from .memory_os import E0MemoryOS, CanonRef, MemOSContext
from .llm_adapter import (
    E0LLMAdapter, LLMConfig, LLMResponseError,
    DeltaEstimate, ProposedState, TransitionResult,
    ResistanceEstimate, LandscapeProposal,
    materialize_landscape, task_map_from_proposal,
)
from .graph_validation import (
    goal_reachable, find_happy_path, find_recovery_edges,
    detect_traps, detect_trivial_loops, graph_quality, GraphQuality,
)
from .validate_cross_domain import run_validation
from .scenario_loader import ScenarioPacket, load_scenario, find_scenario
from .evaluation import (
    RunEvaluation, SemanticEvaluation, ScenarioEvaluation,
    evaluate_run, evaluate_semantics, evaluate_scenario,
    detect_hard_failure, format_evaluation_report,
)
from .reflection import (
    ReflectionDecision, ReflectionReport, ReflectionCallFn,
    should_reflect, reflect, reflect_with_llm, format_reflection_report,
)
from .self_tuning import (
    RunFieldSummary, DerivedThresholds, ParameterSensitivity,
    TuningProposal, MetaTuningResult,
    TuningCycleResult, MultiCycleTuningResult,
    field_summary_from_run, derive_thresholds,
    compute_parameter_sensitivities, propose_tuning, apply_tuning,
    quality_score, tuning_cycle, tune,
)
