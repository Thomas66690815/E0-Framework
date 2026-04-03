"""
Structural Entropy — End-to-End Exploration (C120)
===================================================
Demonstrates the full Structural Entropy pipeline:

  1. Build a domain with anchor + peripheral structure
  2. Run the controller with inscription_threshold=True (Type 1 autopilot)
  3. Observe non-inscription rate as the system matures
  4. Run dream cycles with decay_enabled=True (Type 2 consolidation)
  5. Measure: landscape compression, anchor survival, temperature dynamics

Metrics measured:
  - Non-inscription rate: fraction of routine transitions skipped
  - Structural temperature dynamics: T_s evolution over time
  - Anchor survival: do important states survive decay?
  - Landscape compression: how much structure is shed?
  - Consistency: do surviving edges have valid historization?

Usage:
  py -3 -m e0_controller.explore_structural_entropy
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Dict, List

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape
from e0_controller.controller import E0Controller
from e0_controller.dream_mode import DreamObserver
from e0_controller.structural_entropy import (
    structural_temperature,
    find_decay_candidates,
    find_anchors,
    apply_decay,
)


# ══════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════

N_EPISODES = 30             # controller runs to build experience
MAX_CYCLES_PER_RUN = 40     # steps per run
N_DREAM_CYCLES = 3          # consolidation cycles
THETA_BASE = 0.5            # anchor threshold


# ══════════════════════════════════════════════
# Domain builders
# ══════════════════════════════════════════════

def build_hub_spoke(n_spokes: int = 6) -> Landscape:
    """Hub-and-spoke domain: HUB connects to S1..Sn, each spoke
    has a chain of 3 peripheral nodes.

    HUB ↔ S1 → S1a → S1b
    HUB ↔ S2 → S2a → S2b
    ...
    HUB ↔ GOAL

    The hub and goal are anchors. Spokes are exploration periphery.
    """
    la = Landscape()
    la.add_edge("HUB", "GOAL", delta=0.8, resistance=1.0)
    la.add_edge("GOAL", "HUB", delta=0.3, resistance=1.0)

    for i in range(1, n_spokes + 1):
        spoke = f"S{i}"
        la.add_edge("HUB", spoke, delta=0.5, resistance=1.0)
        la.add_edge(spoke, "HUB", delta=0.5, resistance=1.0)
        # Peripheral chain
        a, b = f"S{i}a", f"S{i}b"
        la.add_edge(spoke, a, delta=0.3, resistance=1.5)
        la.add_edge(a, b, delta=0.2, resistance=2.0)

    return la


def build_two_clusters() -> Landscape:
    """Two clusters connected by a single bridge.

    Cluster A: A1 ↔ A2 ↔ A3
    Cluster B: B1 ↔ B2 ↔ B3
    Bridge: A3 ↔ B1

    With experience, the bridge should be an anchor.
    Peripheral nodes in each cluster may decay.
    """
    la = Landscape()
    for s, t in [("A1", "A2"), ("A2", "A1"), ("A2", "A3"), ("A3", "A2"),
                  ("A3", "B1"), ("B1", "A3"),
                  ("B1", "B2"), ("B2", "B1"), ("B2", "B3"), ("B3", "B2")]:
        la.add_edge(s, t, delta=0.5, resistance=1.0)
    return la


# ══════════════════════════════════════════════
# Execute function (stochastic)
# ══════════════════════════════════════════════

_call_count = 0

def stochastic_execute(source: str, target: str) -> Outcome:
    """Mostly SUCCESS, occasional FAILURE on peripheral edges."""
    global _call_count
    _call_count += 1
    # Peripheral edges fail more often
    if "a" in target or "b" in target:
        if _call_count % 3 == 0:
            return Outcome.FAILURE
    return Outcome.SUCCESS


# ══════════════════════════════════════════════
# Main exploration
# ══════════════════════════════════════════════

@dataclass
class PhaseResult:
    """Result of one exploration phase."""
    name: str
    metrics: Dict[str, float] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)


def run_exploration() -> List[PhaseResult]:
    """End-to-end structural entropy exploration."""
    results: List[PhaseResult] = []

    # ── Phase 1: Build + Inscribe ──
    print("=" * 60)
    print("Phase 1: Build domain + inscribe experience")
    print("=" * 60)

    la = build_hub_spoke(n_spokes=6)
    states_initial = len(la.states)
    edges_initial = la.edge_count()
    print(f"  Domain: {states_initial} states, {edges_initial} edges")

    # Run controller with inscription threshold
    ctrl = E0Controller(
        la,
        stochastic_execute,
        inscription_threshold=True,
    )

    total_steps = 0
    total_non_inscribed = 0
    temperature_trace: List[float] = []

    for ep in range(N_EPISODES):
        trace = ctrl.run("HUB", goal="GOAL", max_cycles=MAX_CYCLES_PER_RUN)
        m = trace.metrics()
        total_steps += int(m["steps"])
        total_non_inscribed += int(m["non_inscription_count"])
        T_s = structural_temperature(la.historization)
        temperature_trace.append(T_s)

    non_inscription_rate = total_non_inscribed / max(1, total_steps)
    T_final = temperature_trace[-1] if temperature_trace else 0.0

    phase1 = PhaseResult("Inscription", metrics={
        "total_steps": total_steps,
        "non_inscription_count": total_non_inscribed,
        "non_inscription_rate": non_inscription_rate,
        "T_s_initial": temperature_trace[0] if temperature_trace else 0.0,
        "T_s_final": T_final,
        "states": len(la.states),
        "edges": la.edge_count(),
    })
    results.append(phase1)

    print(f"  Total steps: {total_steps}")
    print(f"  Non-inscription count: {total_non_inscribed}")
    print(f"  Non-inscription rate: {non_inscription_rate:.1%}")
    print(f"  T_s: {temperature_trace[0]:.3f} → {T_final:.3f}")
    print()

    # ── Phase 2: Analyze anchor structure ──
    print("=" * 60)
    print("Phase 2: Anchor analysis (before decay)")
    print("=" * 60)

    anchors = find_anchors(
        la.states, la.historization, la.edges, theta_base=THETA_BASE
    )
    candidates = find_decay_candidates(
        la.states, la.historization, la.edges,
        theta_base=THETA_BASE,
        protected={"HUB", "GOAL"},
    )

    phase2 = PhaseResult("Anchor Analysis", metrics={
        "anchor_count": len(anchors),
        "candidate_count": len(candidates),
        "T_s": T_final,
    })
    results.append(phase2)

    print(f"  Anchors ({len(anchors)}): {sorted(anchors)}")
    print(f"  Decay candidates ({len(candidates)}):")
    for c in candidates:
        print(f"    {c.state}: score={c.anchor_score:.3f}, "
              f"dormancy={c.dormancy}, edges={c.incident_edge_count}")
    print()

    # ── Phase 3: Dream consolidation ──
    print("=" * 60)
    print("Phase 3: Dream consolidation (decay_enabled=True)")
    print("=" * 60)

    # Build a second domain for dream observation
    la2 = build_two_clusters()
    ctrl2 = E0Controller(la2, stochastic_execute, inscription_threshold=True)
    for _ in range(N_EPISODES):
        ctrl2.run("A1", goal="B3", max_cycles=MAX_CYCLES_PER_RUN)

    obs = DreamObserver(
        readiness_threshold=0.0,
        decay_enabled=True,
        theta_base=THETA_BASE,
        protected_fn=lambda name: {"HUB", "GOAL"} if name == "hub_spoke" else {"A1", "B3"},
    )
    obs.register("hub_spoke", la)
    obs.register("two_clusters", la2)

    total_removed_states = 0
    total_removed_edges = 0
    total_traces = 0

    for cycle_i in range(N_DREAM_CYCLES):
        result = obs.dream_cycle()
        cycle_removed = 0
        for domain, report in result.decay_reports.items():
            n_removed = len(report.removed_states)
            cycle_removed += n_removed
            total_removed_states += n_removed
            total_removed_edges += len(report.removed_edges)
            total_traces += len(report.traces)
            if n_removed > 0:
                print(f"  Cycle {cycle_i + 1}: {domain} — removed {n_removed} states "
                      f"({', '.join(report.removed_states)})")
        if cycle_removed == 0:
            print(f"  Cycle {cycle_i + 1}: no decay (all states active or anchored)")

    T_after_decay = structural_temperature(la.historization)

    phase3 = PhaseResult("Dream Consolidation", metrics={
        "dream_cycles": N_DREAM_CYCLES,
        "total_removed_states": total_removed_states,
        "total_removed_edges": total_removed_edges,
        "total_traces": total_traces,
        "states_after": len(la.states),
        "edges_after": la.edge_count(),
        "states_la2_after": len(la2.states),
        "T_s_after_decay": T_after_decay,
    })
    results.append(phase3)

    print(f"\n  Summary:")
    print(f"    Removed: {total_removed_states} states, {total_removed_edges} edges")
    print(f"    Traces created: {total_traces}")
    print(f"    Hub-spoke: {states_initial} → {len(la.states)} states, "
          f"{edges_initial} → {la.edge_count()} edges")
    print(f"    T_s after decay: {T_after_decay:.3f}")
    print()

    # ── Phase 4: Post-decay consistency ──
    print("=" * 60)
    print("Phase 4: Post-decay consistency check")
    print("=" * 60)

    errors = []
    for e in la.edges:
        if e.source not in la.states:
            errors.append(f"Orphan edge source: {e.source}")
        if e.target not in la.states:
            errors.append(f"Orphan edge target: {e.target}")

    # Check historization consistency
    h = la.historization
    for e in la.edges:
        load = h.trace_load(e)
        quality = h.trace_quality(e)
        if load < 0:
            errors.append(f"Negative trace_load on {e}")
        if not -1.0 <= quality <= 1.0:
            errors.append(f"Invalid trace_quality {quality} on {e}")

    # Verify anchors survived
    anchors_after = find_anchors(
        la.states, la.historization, la.edges, theta_base=THETA_BASE
    )

    phase4 = PhaseResult("Consistency", metrics={
        "errors": len(errors),
        "anchors_after": len(anchors_after),
    }, notes=errors if errors else ["All checks passed"])
    results.append(phase4)

    if errors:
        for err in errors:
            print(f"  ERROR: {err}")
    else:
        print("  All consistency checks passed ✓")
    print(f"  Anchors after decay: {sorted(anchors_after)}")
    print(f"  HUB survived: {'HUB' in la.states}")
    print(f"  GOAL survived: {'GOAL' in la.states}")
    print()

    # ── Phase 5: Temperature dynamics ──
    print("=" * 60)
    print("Phase 5: Temperature dynamics")
    print("=" * 60)

    print(f"  T_s trajectory ({len(temperature_trace)} episodes):")
    for i, t in enumerate(temperature_trace):
        bar = "█" * int(t * 5)
        print(f"    Episode {i + 1:3d}: T_s = {t:.3f} {bar}")
    print(f"  After decay: T_s = {T_after_decay:.3f}")

    phase5 = PhaseResult("Temperature Dynamics", metrics={
        "T_s_min": min(temperature_trace) if temperature_trace else 0.0,
        "T_s_max": max(temperature_trace) if temperature_trace else 0.0,
        "T_s_final": T_final,
        "T_s_after_decay": T_after_decay,
    })
    results.append(phase5)

    # ── Summary ──
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    compression = 1.0 - len(la.states) / states_initial if states_initial > 0 else 0.0
    print(f"  Landscape compression: {compression:.0%} "
          f"({states_initial} → {len(la.states)} states)")
    print(f"  Non-inscription rate: {non_inscription_rate:.1%} "
          f"({total_non_inscribed}/{total_steps} transitions)")
    print(f"  Temperature: {temperature_trace[0]:.3f} → {T_final:.3f} → "
          f"{T_after_decay:.3f} (build → mature → decay)")
    print(f"  Decay: {total_removed_states} states, {total_traces} traces")
    print(f"  Anchors: {len(anchors)} before → {len(anchors_after)} after decay")
    print(f"  Consistency: {'✓' if not errors else '✗'}")
    print()

    return results


# ══════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════

if __name__ == "__main__":
    results = run_exploration()

    # Exit with error if consistency failed
    for r in results:
        if r.name == "Consistency" and r.metrics.get("errors", 0) > 0:
            sys.exit(1)
    sys.exit(0)
