"""E₀ Demo — Human Communication (C162, Proof-of-Concept)
==========================================================
End-to-end proof that E0 can:
  1. Build a perception landscape (C158)
  2. Detect communication intents from its own state (C159)
  3. Emit a UI specification for a coding agent (C160)
  4. Ingest human feedback and adapt (C161)

This demo runs the full loop three times, simulating different
human responses. After each round, the perception landscape
changes — E0 learns which perceptual strategies work.

Usage:
    py -3 -m e0_controller.demo_human_communication
"""

from __future__ import annotations

import json

from e0_controller.communication import (
    CommunicationIntent,
    IntentReport,
    IntentType,
    detect_intents,
    detect_self_graph_intents,
    detect_status_intent,
)
from e0_controller.feedback import (
    HumanAction,
    ingest_feedback,
)
from e0_controller.perception import (
    PerceptionDomain,
    build_perception_domain,
)
from e0_controller.self_graph import SelfGraph
from e0_controller.primitives import Outcome
from e0_controller.ui_emitter import emit_ui_spec


# ──────────────────────────────────────────────
# Simulated human behaviors
# ──────────────────────────────────────────────

ROUND_BEHAVIORS = [
    # Round 1: Human engages with uncertainty, ignores status
    {
        "name": "Engaged with uncertainty",
        "mapping": lambda panels: {
            i: HumanAction.CLICK if p.intent == "uncertainty" else
               HumanAction.FOLLOWUP if p.intent == "request" else
               HumanAction.IGNORE
            for i, p in enumerate(panels)
        },
    },
    # Round 2: Human confused by hierarchy, acknowledges patterns
    {
        "name": "Confused by patterns",
        "mapping": lambda panels: {
            i: HumanAction.CONFUSION if p.intent == "pattern" else
               HumanAction.ACKNOWLEDGE if p.intent == "status" else
               HumanAction.CLICK
            for i, p in enumerate(panels)
        },
    },
    # Round 3: Human dismisses everything except anomalies
    {
        "name": "Only anomalies matter",
        "mapping": lambda panels: {
            i: HumanAction.CLICK if p.intent == "anomaly" else
               HumanAction.DISMISS
            for i, p in enumerate(panels)
        },
    },
]


def _print_header(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def _print_perception_top(domain: PerceptionDomain, n: int = 5) -> None:
    snap = domain.snapshot()
    print(f"  Perception ranking (top {n}):")
    for i, p in enumerate(snap.ranked()[:n]):
        print(f"    {i+1}. {p.name:12s}  strength={p.strength:.3f}  "
              f"quality={p.quality:+.3f}  load={p.trace_load:.1f}")


def run_demo() -> None:
    """Run the end-to-end Human Communication demo."""

    _print_header("E₀ Human Communication — End-to-End Demo (C162)")

    # ── Step 1: Build perception domain ──────────────────────
    print("\n[1] Building perception domain (C158)...")
    domain = build_perception_domain()
    print(f"    {len(domain.primitives)} primitives, "
          f"{len(domain.landscape.edges)} edges")
    _print_perception_top(domain)

    # ── Step 2: Create a Self-Graph with some history ────────
    print("\n[2] Creating Self-Graph with mixed history...")
    sg = SelfGraph()
    # Simulate: some components working well, some not
    from e0_controller.self_graph import active_components
    core = active_components(overlap_active=False)
    full = active_components(overlap_active=True)

    # 15 successes (core components learn)
    for _ in range(15):
        sg.self_historize(core, Outcome.SUCCESS)
    # 5 failures (overlap component gets confused)
    for _ in range(5):
        sg.self_historize(full, Outcome.FAILURE)

    # ── Run 3 feedback rounds ────────────────────────────────
    for round_idx, behavior in enumerate(ROUND_BEHAVIORS, 1):
        _print_header(f"Round {round_idx}: {behavior['name']}")

        # Step 3: Detect intents (C159)
        print(f"\n  [3.{round_idx}] Detecting intents (C159)...")
        report = detect_intents(self_graph=sg, include_status=True)
        print(f"    {report.summary()}")

        # Step 4: Emit UI spec (C160)
        print(f"\n  [4.{round_idx}] Emitting UISpec (C160)...")
        spec = emit_ui_spec(
            report, domain,
            context=f"Demo round {round_idx}: {behavior['name']}",
        )
        print(f"    Layout: {spec.layout}")
        print(f"    Panels: {spec.panel_count}")
        for i, panel in enumerate(spec.panels):
            print(f"      [{i}] {panel.intent:12s} → "
                  f"{panel.perception:10s} ({panel.language_act}) "
                  f"urgency={panel.urgency:.2f}")

        # Step 5: Simulate human feedback (C161)
        print(f"\n  [5.{round_idx}] Simulating human feedback (C161)...")
        actions = behavior["mapping"](spec.panels)
        for i, action in sorted(actions.items()):
            print(f"      Panel [{i}]: {action.value}")

        result = ingest_feedback(domain, spec, actions)
        print(f"    → {result.event_count} events, "
              f"{result.success_count} success, "
              f"{result.failure_count} failure, "
              f"{result.edges_updated} edges updated")

        # Show perception shift
        _print_perception_top(domain)

    # ── Final: serialize the last UISpec ─────────────────────
    _print_header("Final UISpec (JSON)")
    spec_dict = spec.to_dict()
    print(json.dumps(spec_dict, indent=2))

    _print_header("Demo Complete")
    print("  E0 has completed 3 feedback rounds.")
    print("  Perception landscape has adapted to simulated human behavior.")
    print("  A coding agent can consume the UISpec JSON above to build a UI.")


if __name__ == "__main__":
    run_demo()
