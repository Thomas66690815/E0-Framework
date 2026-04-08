"""
E₀ End-to-End Multiverse — Full Capability Exercise (C183)
=============================================================
Builds a complete E₀ multiverse from scratch exercising ALL 14 layers:

  Layer 1-3: Foundation (Landscape, Historization, Controller)
  Layer 4:   Amplitude (Overlay, WavePath, Spinor, Perspective)
  Layer 5:   Bootstrap (Bootstrapper, Canon Loader)
  Layer 6:   Self-Graph (SelfGraph, Dual Reflection)
  Layer 7:   Reflexion (Integrated Reflexion, Scoped Reflexion)
  Layer 8:   Mutation (Structural Mutation)
  Layer 9:   Multiverse (MultiverseController, Coupling Router)
  Layer 10:  Cross-Reflexion
  Layer 11:  Dream (DreamObserver, SleepWake)
  Layer 12:  Entropy (Structural Temperature, Decay, Inscription)
  Layer 13:  Interface (Perception, Communication, UIEmitter, UIRenderer)
  Layer 14:  Session (MemOS, Session, Provenance)

The result is a single JSON file capturing the full multiverse state
after all capabilities have been exercised.

No LLM adapter — all execution is structural (mock execute_fn).
"""

from __future__ import annotations

import json
import math
import os
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

# ── Layer 1-3: Foundation ──
from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.historization import Historization
from e0_controller.tension import tension, coherence
from e0_controller.controller import (
    E0Controller, HybridMode, RunTrace, StepResult, EscalationType,
)
from e0_controller.config import DEFAULTS

# ── Layer 4: Amplitude ──
from e0_controller.amplitude_overlay import (
    OverlayReport, analyze_controller_state,
)
from e0_controller.wavepath import psi as path_psi
from e0_controller.spinor_connection import spinor_psi as path_psi_su2
from e0_controller.connection import omega
from e0_controller.perspective_diagnostic import perspective_check

# ── Layer 5: Bootstrap ──
from e0_controller.bootstrapper import bootstrap_landscape
from e0_controller.canon_loader import load_canon, list_canons, CanonLandscape

# ── Layer 6: Self-Graph ──
from e0_controller.self_graph import SelfGraph, active_components, ALL_COMPONENTS
from e0_controller.dual_reflection import (
    diagnose_self_graph, SelfGraphDiagnosis, DualReflectionReport,
)

# ── Layer 7: Reflexion ──
from e0_controller.integrated_reflexion import (
    integrated_reflexion, IntegratedReflexionResult,
)
from e0_controller.scoped_reflexion import compute_reflexion_scope

# ── Layer 8: Mutation ──
from e0_controller.structural_mutation import (
    StructuralMutation, MutationType, MutationRecord, MutationHistory,
    apply_structural_mutation, revert_structural_mutation,
)

# ── Layer 9: Multiverse ──
from e0_controller.multiverse import (
    Universe, MultiverseController, MultiverseResult,
)
from e0_controller.coupling_router import CouplingRouter

# ── Layer 10: Cross-Reflexion ──
from e0_controller.cross_reflexion import (
    cross_propose_edges, CrossReflexionResult,
    cross_reflexion_turn,
)

# ── Layer 11: Dream ──
from e0_controller.dream_mode import (
    DreamObserver, DreamCycleResult,
    find_equivalences, dream_readiness,
    edge_fingerprint, domain_fingerprints,
)
from e0_controller.sleep_wake import SleepWakeCycle

# ── Layer 12: Entropy ──
from e0_controller.structural_entropy import (
    structural_temperature, dream_pressure, should_dream,
    novelty as inscription_novelty, inscription_threshold,
)

# ── Layer 13: Interface ──
from e0_controller.perception import build_perception_domain, PerceptionDomain
from e0_controller.communication import detect_intents, IntentReport
from e0_controller.ui_emitter import emit_ui_spec, UISpec
from e0_controller.ui_renderer import render_html

# ── Layer 14: Session ──
from e0_controller.memory_os import E0MemoryOS, LandscapeSnapshot as MemOSSnapshot
from e0_controller.provenance import ProvenanceLog

# ── Utilities ──
from e0_controller.graph_validation import graph_quality, goal_reachable
from e0_controller.exploration_policy import ExplorationPolicy
from e0_controller.dynamic_horizon import topology_adaptive
from e0_controller.evaluation import evaluate_run
from e0_controller.reflexive_action import apply_reflexive_actions
from e0_controller.canon_self_bridge import build_self_exposition


# ═══════════════════════════════════════════════════════════════════
# Domain Specs — Two structurally distinct domains for the multiverse
# ═══════════════════════════════════════════════════════════════════

LOGISTICS_SPEC = {
    "nodes": ["DEPOT", "SORT", "LOAD", "ROUTE_A", "ROUTE_B",
              "CUSTOMS", "WAREHOUSE", "DELIVER", "RETURN", "AUDIT"],
    "edges": [
        {"from": "DEPOT", "to": "SORT", "delta": 0.4, "resistance": 0.3,
         "initial_U": 8, "initial_F": 2, "confidence": 0.9},
        {"from": "SORT", "to": "LOAD", "delta": 0.3, "resistance": 0.25,
         "initial_U": 7, "initial_F": 3, "confidence": 0.8},
        {"from": "LOAD", "to": "ROUTE_A", "delta": 0.5, "resistance": 0.4,
         "initial_U": 6, "initial_F": 2, "confidence": 0.85},
        {"from": "LOAD", "to": "ROUTE_B", "delta": 0.6, "resistance": 0.35,
         "initial_U": 5, "initial_F": 3, "confidence": 0.7},
        {"from": "ROUTE_A", "to": "CUSTOMS", "delta": 0.7, "resistance": 0.5,
         "initial_U": 4, "initial_F": 4, "confidence": 0.6},
        {"from": "ROUTE_B", "to": "WAREHOUSE", "delta": 0.35, "resistance": 0.3,
         "initial_U": 7, "initial_F": 1, "confidence": 0.9},
        {"from": "CUSTOMS", "to": "WAREHOUSE", "delta": 0.4, "resistance": 0.4,
         "initial_U": 5, "initial_F": 3, "confidence": 0.65},
        {"from": "WAREHOUSE", "to": "DELIVER", "delta": 0.3, "resistance": 0.2,
         "initial_U": 9, "initial_F": 1, "confidence": 0.95},
        {"from": "DELIVER", "to": "AUDIT", "delta": 0.25, "resistance": 0.15,
         "initial_U": 8, "initial_F": 2, "confidence": 0.9},
        {"from": "RETURN", "to": "DEPOT", "delta": 0.8, "resistance": 0.6,
         "initial_U": 3, "initial_F": 5, "confidence": 0.5},
        {"from": "DELIVER", "to": "RETURN", "delta": 0.9, "resistance": 0.7,
         "initial_U": 2, "initial_F": 6, "confidence": 0.4},
        {"from": "SORT", "to": "AUDIT", "delta": 1.0, "resistance": 0.8,
         "initial_U": 1, "initial_F": 7, "confidence": 0.3},
    ],
}

RESEARCH_SPEC = {
    "nodes": ["QUESTION", "LITERATURE", "HYPOTHESIS", "DESIGN",
              "EXPERIMENT", "DATA", "ANALYSIS", "INTERPRET",
              "PUBLISH", "REVIEW"],
    "edges": [
        {"from": "QUESTION", "to": "LITERATURE", "delta": 0.35, "resistance": 0.25,
         "initial_U": 7, "initial_F": 3, "confidence": 0.8},
        {"from": "LITERATURE", "to": "HYPOTHESIS", "delta": 0.5, "resistance": 0.4,
         "initial_U": 6, "initial_F": 2, "confidence": 0.85},
        {"from": "HYPOTHESIS", "to": "DESIGN", "delta": 0.4, "resistance": 0.3,
         "initial_U": 8, "initial_F": 2, "confidence": 0.9},
        {"from": "DESIGN", "to": "EXPERIMENT", "delta": 0.6, "resistance": 0.5,
         "initial_U": 5, "initial_F": 3, "confidence": 0.7},
        {"from": "EXPERIMENT", "to": "DATA", "delta": 0.3, "resistance": 0.2,
         "initial_U": 9, "initial_F": 1, "confidence": 0.95},
        {"from": "DATA", "to": "ANALYSIS", "delta": 0.4, "resistance": 0.3,
         "initial_U": 7, "initial_F": 2, "confidence": 0.85},
        {"from": "ANALYSIS", "to": "INTERPRET", "delta": 0.55, "resistance": 0.45,
         "initial_U": 5, "initial_F": 3, "confidence": 0.7},
        {"from": "INTERPRET", "to": "PUBLISH", "delta": 0.3, "resistance": 0.2,
         "initial_U": 8, "initial_F": 2, "confidence": 0.9},
        {"from": "PUBLISH", "to": "REVIEW", "delta": 0.45, "resistance": 0.35,
         "initial_U": 6, "initial_F": 4, "confidence": 0.65},
        {"from": "REVIEW", "to": "QUESTION", "delta": 0.7, "resistance": 0.5,
         "initial_U": 4, "initial_F": 4, "confidence": 0.55},
        {"from": "HYPOTHESIS", "to": "EXPERIMENT", "delta": 0.8, "resistance": 0.6,
         "initial_U": 3, "initial_F": 5, "confidence": 0.45},
        {"from": "DATA", "to": "HYPOTHESIS", "delta": 0.65, "resistance": 0.55,
         "initial_U": 4, "initial_F": 5, "confidence": 0.4},
    ],
}


# ═══════════════════════════════════════════════════════════════════
# Execute function — deterministic mock
# ═══════════════════════════════════════════════════════════════════

# Edges that always fail (structural traps)
_FAIL_EDGES = {
    ("DELIVER", "RETURN"),
    ("SORT", "AUDIT"),
    ("HYPOTHESIS", "EXPERIMENT"),
    ("DATA", "HYPOTHESIS"),
}


def execute_fn(source: str, target: str) -> Outcome:
    """Deterministic execution: some edges always fail, rest succeed."""
    if (source, target) in _FAIL_EDGES:
        return Outcome.FAILURE
    return Outcome.SUCCESS


# ═══════════════════════════════════════════════════════════════════
# Phase results — one dataclass per phase
# ═══════════════════════════════════════════════════════════════════

@dataclass
class PhaseResult:
    """Base for all phase results."""
    phase: str
    duration_s: float
    summary: str


@dataclass
class E2EState:
    """Complete E2E multiverse state after all phases."""
    created_at: str = ""
    total_duration_s: float = 0.0
    phases: List[Dict[str, Any]] = field(default_factory=list)
    # Snapshots from each phase
    canon_names: List[str] = field(default_factory=list)
    logistics_states: int = 0
    logistics_edges: int = 0
    research_states: int = 0
    research_edges: int = 0
    controller_runs: List[Dict[str, Any]] = field(default_factory=list)
    amplitude_analysis: Dict[str, Any] = field(default_factory=dict)
    self_graph_snapshot: Dict[str, Any] = field(default_factory=dict)
    diagnosis: Dict[str, Any] = field(default_factory=dict)
    reflexion_result: Dict[str, Any] = field(default_factory=dict)
    mutations_applied: List[Dict[str, Any]] = field(default_factory=list)
    multiverse_summary: Dict[str, Any] = field(default_factory=dict)
    cross_reflexion: Dict[str, Any] = field(default_factory=dict)
    dream_result: Dict[str, Any] = field(default_factory=dict)
    entropy_metrics: Dict[str, Any] = field(default_factory=dict)
    ui_spec: Dict[str, Any] = field(default_factory=dict)
    html_length: int = 0
    session_id: str = ""
    provenance_stages: int = 0
    graph_quality_logistics: Dict[str, Any] = field(default_factory=dict)
    graph_quality_research: Dict[str, Any] = field(default_factory=dict)
    canon_self_bridge: str = ""


# ═══════════════════════════════════════════════════════════════════
# Phase 1: Canon Training
# ═══════════════════════════════════════════════════════════════════

def phase_01_canon_training(state: E2EState) -> None:
    """Load all canon landscapes and train them with runs."""
    t0 = time.perf_counter()

    canons = {}
    for name in ["english_basic", "german_basic", "ontodynamics"]:
        cl = load_canon(name)
        canons[name] = cl
        state.canon_names.append(name)

    # Train each canon with a short controller run
    for name, cl in canons.items():
        ls = cl.landscape
        nodes = sorted(ls.states)
        if len(nodes) < 2:
            continue
        # Find a reachable goal
        start = nodes[0]
        goal = None
        for n in reversed(nodes):
            if goal_reachable(ls, start, n) and n != start:
                goal = n
                break
        if goal is None:
            continue
        ctrl = E0Controller(ls, execute_fn, hybrid_mode=HybridMode.GREEDY)
        ctrl.run(start, max_cycles=20, goal=goal)

    state._canons = canons  # stash for later phases
    dt = time.perf_counter() - t0
    state.phases.append({
        "phase": "01_canon_training",
        "canons_loaded": list(canons.keys()),
        "duration_s": round(dt, 3),
    })
    print(f"  Phase 01: Canon Training — {len(canons)} canons, {dt:.2f}s")


# ═══════════════════════════════════════════════════════════════════
# Phase 2: Bootstrap Domains
# ═══════════════════════════════════════════════════════════════════

def phase_02_bootstrap(state: E2EState) -> None:
    """Bootstrap the two multiverse domains."""
    t0 = time.perf_counter()

    ls_logis = bootstrap_landscape(LOGISTICS_SPEC)
    ls_research = bootstrap_landscape(RESEARCH_SPEC)

    state.logistics_states = len(ls_logis.states)
    state.logistics_edges = len(ls_logis.edges)
    state.research_states = len(ls_research.states)
    state.research_edges = len(ls_research.edges)

    state._ls_logis = ls_logis
    state._ls_research = ls_research

    dt = time.perf_counter() - t0
    state.phases.append({
        "phase": "02_bootstrap",
        "logistics": {"states": state.logistics_states, "edges": state.logistics_edges},
        "research": {"states": state.research_states, "edges": state.research_edges},
        "duration_s": round(dt, 3),
    })
    print(f"  Phase 02: Bootstrap — logistics={state.logistics_states}s/{state.logistics_edges}e, "
          f"research={state.research_states}s/{state.research_edges}e, {dt:.2f}s")


# ═══════════════════════════════════════════════════════════════════
# Phase 3: Graph Validation
# ═══════════════════════════════════════════════════════════════════

def phase_03_graph_validation(state: E2EState) -> None:
    """Validate both domain graphs."""
    t0 = time.perf_counter()

    gq_logis = graph_quality(state._ls_logis, "DEPOT", "AUDIT")
    gq_research = graph_quality(state._ls_research, "QUESTION", "REVIEW")

    state.graph_quality_logistics = {
        "reachable": gq_logis.reachable,
        "happy_path": gq_logis.happy_path,
        "happy_path_length": gq_logis.happy_path_length,
        "traps": gq_logis.traps,
        "recovery_edges": gq_logis.recovery_count,
    }
    state.graph_quality_research = {
        "reachable": gq_research.reachable,
        "happy_path": gq_research.happy_path,
        "happy_path_length": gq_research.happy_path_length,
        "traps": gq_research.traps,
        "recovery_edges": gq_research.recovery_count,
    }

    dt = time.perf_counter() - t0
    state.phases.append({
        "phase": "03_graph_validation",
        "logistics": state.graph_quality_logistics,
        "research": state.graph_quality_research,
        "duration_s": round(dt, 3),
    })
    print(f"  Phase 03: Graph Validation — logistics reachable={gq_logis.reachable}, "
          f"research reachable={gq_research.reachable}, {dt:.2f}s")


# ═══════════════════════════════════════════════════════════════════
# Phase 4: Controller Runs (all 3 HybridModes)
# ═══════════════════════════════════════════════════════════════════

def phase_04_controller_runs(state: E2EState) -> None:
    """Run controllers on both domains with all 3 hybrid modes."""
    t0 = time.perf_counter()

    runs = []
    for mode in [HybridMode.GREEDY, HybridMode.AMPLITUDE_ON_DISAGREE, HybridMode.BORN_SAMPLING]:
        for domain_name, ls, start, goal in [
            ("logistics", state._ls_logis, "DEPOT", "AUDIT"),
            ("research", state._ls_research, "QUESTION", "REVIEW"),
        ]:
            ctrl = E0Controller(
                ls, execute_fn,
                alpha=2.0,
                hybrid_mode=mode,
                hybrid_horizon=3,
                hybrid_goals={goal},
                hybrid_geometry="goal_reaching",
                horizon_strategy=topology_adaptive(),
            )
            # Attach self-graph
            sg = SelfGraph()
            ctrl.self_graph = sg

            trace = ctrl.run(start, max_cycles=40, goal=goal,
                             overlay_horizon=3, perspective_horizon=3)
            metrics = trace.metrics()

            runs.append({
                "domain": domain_name,
                "mode": mode.value,
                "steps": metrics["steps"],
                "success_rate": metrics["success_rate"],
                "goal_reached": trace.path[-1] == goal if trace.path else False,
                "hybrid_override_count": metrics["hybrid_override_count"],
                "escalation_count": metrics["escalation_count"],
            })

    state.controller_runs = runs
    # Keep the last controllers for later phases
    state._ctrl_logis = E0Controller(
        state._ls_logis, execute_fn,
        alpha=2.0,
        hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
        hybrid_horizon=3,
        hybrid_goals={"AUDIT"},
        hybrid_geometry="goal_reaching",
    )
    state._sg = SelfGraph()
    state._ctrl_logis.self_graph = state._sg

    # Additional training run to build self-graph traces
    for _ in range(5):
        state._ctrl_logis.run("DEPOT", max_cycles=30, goal="AUDIT")

    dt = time.perf_counter() - t0
    state.phases.append({
        "phase": "04_controller_runs",
        "runs": len(runs),
        "modes_tested": ["GREEDY", "AMPLITUDE_ON_DISAGREE", "BORN_SAMPLING"],
        "duration_s": round(dt, 3),
    })
    print(f"  Phase 04: Controller Runs — {len(runs)} runs across 3 modes, {dt:.2f}s")


# ═══════════════════════════════════════════════════════════════════
# Phase 5: Amplitude Overlay Analysis
# ═══════════════════════════════════════════════════════════════════

def phase_05_amplitude(state: E2EState) -> None:
    """Run amplitude overlay analysis on both domains."""
    t0 = time.perf_counter()

    report = analyze_controller_state(
        state._ctrl_logis, "DEPOT",
        horizon_edges=3, goals={"AUDIT"}, geometry="goal_reaching",
    )

    # Also compute wavepath and spinor for one path
    ls = state._ls_logis
    path = ["DEPOT", "SORT", "LOAD"]
    psi_u1 = path_psi(ls, path)
    psi_su2 = path_psi_su2(ls, path)
    omega_val = omega(ls, "DEPOT", "SORT")

    # Perspective diagnostic
    persp = perspective_check(state._ctrl_logis, "DEPOT", horizon=3)

    state.amplitude_analysis = {
        "overlay_actions": len(report.action_infos),
        "amplitude_choice": report.amplitude_choice,
        "deterministic_choice": report.deterministic_choice,
        "geometry": report.geometry,
        "psi_u1_real": psi_u1.real,
        "psi_u1_imag": psi_u1.imag,
        "psi_u1_abs": abs(psi_u1),
        "psi_su2_norm": float(sum(abs(x)**2 for x in psi_su2)),
        "omega_DEPOT_SORT": omega_val,
        "perspective_robust": persp.robust if persp else None,
        "perspective_agreement": persp.ranking_agreement if persp else None,
    }

    dt = time.perf_counter() - t0
    state.phases.append({
        "phase": "05_amplitude",
        "amplitude_details": state.amplitude_analysis,
        "duration_s": round(dt, 3),
    })
    print(f"  Phase 05: Amplitude — choice={report.amplitude_choice}, "
          f"ψ_U(1)={abs(psi_u1):.4f}, {dt:.2f}s")


# ═══════════════════════════════════════════════════════════════════
# Phase 6: Self-Graph + Diagnosis
# ═══════════════════════════════════════════════════════════════════

def phase_06_self_graph(state: E2EState) -> None:
    """Diagnose self-graph health and build canon self-bridge."""
    t0 = time.perf_counter()

    sg = state._sg
    diagnosis = diagnose_self_graph(sg)
    snapshot = sg.snapshot()

    # Canon self-bridge
    onto = state._canons.get("ontodynamics")
    bridge_text = ""
    if onto:
        bridge_text = build_self_exposition(onto, sg)

    state.self_graph_snapshot = snapshot
    state.diagnosis = {
        "healthy": diagnosis.healthy,
        "confused": diagnosis.confused,
        "harmful": diagnosis.harmful,
        "insufficient_data": diagnosis.insufficient_data,
        "deactivation_candidates": diagnosis.deactivation_candidates,
        "meta_actions": diagnosis.meta_actions,
    }
    state.canon_self_bridge = bridge_text[:2000]  # truncate for JSON

    dt = time.perf_counter() - t0
    state.phases.append({
        "phase": "06_self_graph",
        "components": len(snapshot),
        "healthy": len(diagnosis.healthy),
        "confused": len(diagnosis.confused),
        "duration_s": round(dt, 3),
    })
    print(f"  Phase 06: Self-Graph — {len(diagnosis.healthy)} healthy, "
          f"{len(diagnosis.confused)} confused, {dt:.2f}s")


# ═══════════════════════════════════════════════════════════════════
# Phase 7: Reflexive Actions + Edge Proposals
# ═══════════════════════════════════════════════════════════════════

def phase_07_reflexion(state: E2EState) -> None:
    """Run integrated reflexion on the logistics domain."""
    t0 = time.perf_counter()

    # Build a DualReflectionReport from self-graph for flag reflexion
    diagnosis = diagnose_self_graph(state._sg)
    dual_report = DualReflectionReport(
        domain_report=None,
        self_diagnosis=diagnosis,
    )

    result = integrated_reflexion(
        state._ls_logis, "DEPOT", "AUDIT",
        report=dual_report,
        scoped=True,
    )

    # Also compute reflexion scope
    scope = compute_reflexion_scope(state._ls_logis, "DEPOT")

    state.reflexion_result = {
        "flag_changes": result.flags_changed,
        "edge_proposals": len(result.edge_proposals),
        "edges_applied": result.edges_added,
        "scope_center": scope.center,
        "scope_radius": scope.radius,
        "scope_size": scope.scope_size,
        "scope_locality": round(scope.locality, 3),
    }

    dt = time.perf_counter() - t0
    state.phases.append({
        "phase": "07_reflexion",
        "details": state.reflexion_result,
        "duration_s": round(dt, 3),
    })
    print(f"  Phase 07: Reflexion — {result.edges_added} edges applied, "
          f"scope locality={scope.locality:.2f}, {dt:.2f}s")


# ═══════════════════════════════════════════════════════════════════
# Phase 8: Structural Mutation
# ═══════════════════════════════════════════════════════════════════

def phase_08_mutation(state: E2EState) -> None:
    """Apply and revert a structural mutation."""
    t0 = time.perf_counter()

    ls = state._ls_logis
    old_R = ls.base_resistance("DEPOT", "SORT")

    mutation = StructuralMutation(
        mutation_type=MutationType.ADJUST_RESISTANCE,
        source="DEPOT",
        target="SORT",
        old_value=old_R,
        new_value=old_R * 1.5,
        motivation="E2E test: increase resistance on first edge",
    )

    record = apply_structural_mutation(mutation, ls)
    new_R = ls.base_resistance("DEPOT", "SORT")

    # Now revert
    revert_structural_mutation(mutation, ls)
    restored_R = ls.base_resistance("DEPOT", "SORT")

    state.mutations_applied.append({
        "type": mutation.mutation_type.value,
        "edge": f"{mutation.source}→{mutation.target}",
        "old_value": old_R,
        "new_value": new_R,
        "restored": restored_R,
        "revert_success": abs(restored_R - old_R) < 1e-6,
    })

    dt = time.perf_counter() - t0
    state.phases.append({
        "phase": "08_mutation",
        "mutations": state.mutations_applied,
        "duration_s": round(dt, 3),
    })
    print(f"  Phase 08: Mutation — R₀ {old_R:.3f}→{new_R:.3f}→{restored_R:.3f}, {dt:.2f}s")


# ═══════════════════════════════════════════════════════════════════
# Phase 9: Multiverse
# ═══════════════════════════════════════════════════════════════════

def phase_09_multiverse(state: E2EState) -> None:
    """Run a two-universe multiverse with novelty-gated historization."""
    t0 = time.perf_counter()

    universe_a = Universe(
        name="logistics",
        landscape=state._ls_logis,
        execute_fn=execute_fn,
        start="DEPOT",
        goal="AUDIT",
    )
    universe_b = Universe(
        name="research",
        landscape=state._ls_research,
        execute_fn=execute_fn,
        start="QUESTION",
        goal="REVIEW",
    )

    mc = MultiverseController(universe_a, universe_b)
    result = mc.run(max_turns=12)

    state.multiverse_summary = {
        "total_turns": result.total_turns,
        "total_novelty": result.total_novelty,
        "novelty_rate": round(result.novelty_rate, 3),
        "converged": result.converged,
        "convergence_turn": result.convergence_turn,
        "divergence_count": result.divergence_count,
        "novelty_edges_added": result.novelty_edges_added,
    }

    state._multiverse = mc

    dt = time.perf_counter() - t0
    state.phases.append({
        "phase": "09_multiverse",
        "details": state.multiverse_summary,
        "duration_s": round(dt, 3),
    })
    print(f"  Phase 09: Multiverse — {result.total_turns} turns, "
          f"novelty={result.novelty_rate:.0%}, {dt:.2f}s")


# ═══════════════════════════════════════════════════════════════════
# Phase 10: Cross-Reflexion
# ═══════════════════════════════════════════════════════════════════

def phase_10_cross_reflexion(state: E2EState) -> None:
    """Cross-universe edge proposal from research→logistics."""
    t0 = time.perf_counter()

    result = cross_propose_edges(
        state._ls_logis,
        state._ls_research,
        "DEPOT",
        "AUDIT",
        scoped=True,
    )

    state.cross_reflexion = {
        "proposals": len(result.proposals),
        "edges_added": result.edges_added,
        "frontier_node": result.frontier_node,
        "donor_name": result.donor_name,
    }

    dt = time.perf_counter() - t0
    state.phases.append({
        "phase": "10_cross_reflexion",
        "details": state.cross_reflexion,
        "duration_s": round(dt, 3),
    })
    print(f"  Phase 10: Cross-Reflexion — {result.edges_added} edges from research→logistics, {dt:.2f}s")


# ═══════════════════════════════════════════════════════════════════
# Phase 11: Dream Cycle
# ═══════════════════════════════════════════════════════════════════

def phase_11_dream(state: E2EState) -> None:
    """Run dream cycles across all domains including canons."""
    t0 = time.perf_counter()

    observer = DreamObserver(
        readiness_threshold=0.0,  # accept all domains (E2E)
        quantile=0.2,
        node_equivalence_method="wl",
    )

    # Register domain landscapes
    observer.register("logistics", state._ls_logis)
    observer.register("research", state._ls_research)

    # Register canon landscapes
    for name, cl in state._canons.items():
        observer.register(f"canon_{name}", cl.landscape)

    # Run 3 dream cycles
    total_eq = 0
    total_new = 0
    for _ in range(3):
        dr = observer.dream_cycle()
        total_eq += dr.equivalences_found
        total_new += dr.equivalences_new

    # Check dream readiness
    readiness_logis = dream_readiness(state._ls_logis)
    readiness_research = dream_readiness(state._ls_research)

    dl = observer.dream_landscape
    state.dream_result = {
        "cycles": 3,
        "domains_observed": observer.domain_names,
        "total_equivalences_found": total_eq,
        "total_new_equivalences": total_new,
        "dream_landscape_states": len(dl.states) if dl else 0,
        "dream_landscape_edges": len(dl.edges) if dl else 0,
        "readiness_logistics": round(readiness_logis, 3),
        "readiness_research": round(readiness_research, 3),
    }

    state._observer = observer

    dt = time.perf_counter() - t0
    state.phases.append({
        "phase": "11_dream",
        "details": state.dream_result,
        "duration_s": round(dt, 3),
    })
    print(f"  Phase 11: Dream — {total_eq} equivalences, "
          f"DL={state.dream_result['dream_landscape_states']}s/"
          f"{state.dream_result['dream_landscape_edges']}e, {dt:.2f}s")


# ═══════════════════════════════════════════════════════════════════
# Phase 12: Sleep-Wake Cycle
# ═══════════════════════════════════════════════════════════════════

def phase_12_sleep_wake(state: E2EState) -> None:
    """Run a short sleep-wake cycle."""
    t0 = time.perf_counter()

    observer = state._observer

    # Create controllers for sleep-wake
    ctrl_logis = E0Controller(
        state._ls_logis, execute_fn,
        alpha=2.0, hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
        hybrid_horizon=3, hybrid_goals={"AUDIT"},
    )
    ctrl_research = E0Controller(
        state._ls_research, execute_fn,
        alpha=2.0, hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
        hybrid_horizon=3, hybrid_goals={"REVIEW"},
    )

    swc = SleepWakeCycle(observer, mu=5.0, max_dream_cycles=3)
    swc.register("logistics", ctrl_logis, start="DEPOT", goal="AUDIT")
    swc.register("research", ctrl_research, start="QUESTION", goal="REVIEW")
    swc.wire_peer_fns()

    episodes = swc.run(n_episodes=4, max_cycles_per_run=30)

    n_slept = sum(1 for ep in episodes if ep.slept)

    dt = time.perf_counter() - t0
    state.phases.append({
        "phase": "12_sleep_wake",
        "episodes": len(episodes),
        "slept": n_slept,
        "duration_s": round(dt, 3),
    })
    print(f"  Phase 12: Sleep-Wake — {len(episodes)} episodes, {n_slept} sleep phases, {dt:.2f}s")


# ═══════════════════════════════════════════════════════════════════
# Phase 13: Structural Entropy
# ═══════════════════════════════════════════════════════════════════

def phase_13_entropy(state: E2EState) -> None:
    """Measure structural entropy metrics."""
    t0 = time.perf_counter()

    h_logis = state._ls_logis.historization
    h_research = state._ls_research.historization

    T_logis = structural_temperature(h_logis)
    T_research = structural_temperature(h_research)
    dp_logis = dream_pressure(h_logis)
    dp_research = dream_pressure(h_research)
    sd_logis = should_dream(h_logis)
    sd_research = should_dream(h_research)

    # Check inscription mechanics on one edge
    edge = Edge("DEPOT", "SORT")
    novelty = inscription_novelty(edge, Outcome.SUCCESS, h_logis)
    threshold = inscription_threshold(edge, h_logis, T_logis)

    state.entropy_metrics = {
        "T_s_logistics": round(T_logis, 3),
        "T_s_research": round(T_research, 3),
        "dream_pressure_logistics": round(dp_logis, 3),
        "dream_pressure_research": round(dp_research, 3),
        "should_dream_logistics": sd_logis,
        "should_dream_research": sd_research,
        "inscription_novelty_DEPOT_SORT": round(novelty, 4),
        "inscription_threshold_DEPOT_SORT": round(threshold, 4),
    }

    dt = time.perf_counter() - t0
    state.phases.append({
        "phase": "13_entropy",
        "details": state.entropy_metrics,
        "duration_s": round(dt, 3),
    })
    print(f"  Phase 13: Entropy — T_s(logis)={T_logis:.2f}, T_s(res)={T_research:.2f}, {dt:.2f}s")


# ═══════════════════════════════════════════════════════════════════
# Phase 14: Perception + Communication + UI
# ═══════════════════════════════════════════════════════════════════

def phase_14_interface(state: E2EState) -> None:
    """Build perception domain, detect intents, emit UI spec, render HTML."""
    t0 = time.perf_counter()

    # Perception domain
    perception = build_perception_domain()

    # Communication intents
    intent_report = detect_intents(
        self_graph=state._sg,
        dream_observer=state._observer,
        dream_domain="logistics",
        landscape=state._ls_logis,
        goal="AUDIT",
        include_status=True,
    )

    # UI spec
    ui_spec = emit_ui_spec(
        intent_report, perception,
        context="E2E multiverse exploration",
    )

    # Render HTML
    html = render_html(ui_spec, title="E₀ E2E Multiverse")

    state.ui_spec = ui_spec.to_dict()
    state.html_length = len(html)

    dt = time.perf_counter() - t0
    state.phases.append({
        "phase": "14_interface",
        "perception_primitives": len(perception.primitives),
        "intents_detected": intent_report.count,
        "max_urgency": round(intent_report.max_urgency, 2),
        "ui_panels": ui_spec.panel_count,
        "html_bytes": state.html_length,
        "duration_s": round(dt, 3),
    })
    print(f"  Phase 14: Interface — {intent_report.count} intents, "
          f"{ui_spec.panel_count} panels, {state.html_length} bytes HTML, {dt:.2f}s")


# ═══════════════════════════════════════════════════════════════════
# Phase 15: Session Persist + Provenance
# ═══════════════════════════════════════════════════════════════════

def phase_15_session(state: E2EState) -> None:
    """Persist state via MemOS and record provenance."""
    t0 = time.perf_counter()

    # Use temp dir for MemOS to avoid polluting workspace
    with tempfile.TemporaryDirectory(prefix="e0_e2e_") as tmp:
        session_id = f"e2e_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

        # MemOS snapshot
        memos = E0MemoryOS(base_dir=tmp)
        snap_logis = MemOSSnapshot.from_landscape(state._ls_logis)
        snap_research = MemOSSnapshot.from_landscape(state._ls_research)

        # Provenance log
        prov = ProvenanceLog(source_id="e2e_multiverse")
        prov.record_input("End-to-end multiverse exploration — all 14 layers")
        # Record landscape
        prov.record_landscape(state._ls_logis, "DEPOT", "AUDIT")

        # Run controller through provenance
        trace = state._ctrl_logis.run("DEPOT", max_cycles=20, goal="AUDIT")
        prov.record_run(trace, controller_config={
            "alpha": 2.0,
            "hybrid_mode": "amplitude_on_disagree",
        })

        # Evaluate — evaluate_run takes individual metrics, not a trace
        m = trace.metrics()
        gq = graph_quality(state._ls_logis, "DEPOT", "AUDIT")
        eval_result = evaluate_run(
            path=trace.path,
            steps=int(m["steps"]),
            escalation_count=int(m["escalation_count"]),
            revisit_count=int(m["revisit_count"]),
            success_rate=m["success_rate"],
            avg_tension=m["avg_tension"],
            total_tension=trace.total_tension,
            reached_goal=trace.path[-1] == "AUDIT" if trace.path else False,
            happy_path_length=gq.happy_path_length,
            hybrid_override_count=int(m.get("hybrid_override_count", 0)),
            hybrid_override_rate=m.get("hybrid_override_rate", 0.0),
            overlay_agree_rate=m.get("overlay_agree", 1.0),
            overlay_count=int(m.get("overlay_count", 0)),
        )
        prov.record_evaluation(asdict(eval_result))

        # Save provenance
        prov_path = Path(tmp) / "provenance.json"
        prov.save(str(prov_path))
        prov_stages = sum([
            prov.input is not None,
            prov.landscape is not None,
            len(prov.runs),
            prov.evaluation is not None,
        ])

        state.session_id = session_id
        state.provenance_stages = prov_stages

    dt = time.perf_counter() - t0
    state.phases.append({
        "phase": "15_session",
        "session_id": state.session_id,
        "provenance_stages": state.provenance_stages,
        "duration_s": round(dt, 3),
    })
    print(f"  Phase 15: Session — id={state.session_id}, "
          f"{state.provenance_stages} provenance stages, {dt:.2f}s")


# ═══════════════════════════════════════════════════════════════════
# Main Orchestrator
# ═══════════════════════════════════════════════════════════════════

def run_e2e_multiverse() -> E2EState:
    """Run the full E2E multiverse exploration through all 15 phases."""
    print("=" * 60)
    print("E₀ End-to-End Multiverse — Full Capability Exercise")
    print("=" * 60)

    state = E2EState()
    state.created_at = datetime.now(timezone.utc).isoformat()

    t_total = time.perf_counter()

    phases = [
        phase_01_canon_training,
        phase_02_bootstrap,
        phase_03_graph_validation,
        phase_04_controller_runs,
        phase_05_amplitude,
        phase_06_self_graph,
        phase_07_reflexion,
        phase_08_mutation,
        phase_09_multiverse,
        phase_10_cross_reflexion,
        phase_11_dream,
        phase_12_sleep_wake,
        phase_13_entropy,
        phase_14_interface,
        phase_15_session,
    ]

    for phase_fn in phases:
        phase_fn(state)

    state.total_duration_s = round(time.perf_counter() - t_total, 3)

    # Clean up internal references before JSON serialization
    for attr in ["_canons", "_ls_logis", "_ls_research", "_ctrl_logis",
                 "_sg", "_multiverse", "_observer"]:
        if hasattr(state, attr):
            delattr(state, attr)

    print()
    print(f"Total: {state.total_duration_s:.1f}s, {len(state.phases)} phases")
    print("=" * 60)

    return state


def save_state(state: E2EState, path: str = "memos/e2e_multiverse_state.json") -> str:
    """Save complete E2E state to JSON."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(state)
    p.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    print(f"State saved to {p}")
    return str(p)


# ═══════════════════════════════════════════════════════════════════
# Entry Point
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    state = run_e2e_multiverse()
    save_state(state)
