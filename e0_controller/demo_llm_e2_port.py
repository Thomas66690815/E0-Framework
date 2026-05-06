"""
E₀ Demo — LlmE2Port: LLM as Execution Target (C294)
=====================================================
Demonstrates the "E₀ = Skeleton, LLM = Muscle" architecture:

    E₀ selects which transition to take  (structural, traceable)
    LlmE2Port asks the LLM to execute it (generative, domain-specific)
    E₀ historizes the result              (learning, without training data)

Domain: Incident Briefing Workflow
    INCIDENT_REPORTED → CONTEXT_GATHERED → IMPACT_ASSESSED
    → MITIGATION_PROPOSED → BRIEFING_DRAFTED → DELIVERED

A second run replays the same landscape — but E₀ has learned from the
first run. The inertia profile shows which paths became more confident.

Usage:
    # Mock mode (no API key needed):
    py -3 -m e0_controller.demo_llm_e2_port

    # Live mode (requires OPENAI_API_KEY in .env):
    py -3 -m e0_controller.demo_llm_e2_port --live

    # With E1-callout: show turns where LLM triggered inertia_low hint:
    py -3 -m e0_controller.demo_llm_e2_port --show-payloads
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap

from e0_controller.e0_turn import E0Turn
from e0_controller.e2_port import ExecutionResult
from e0_controller.landscape import Landscape
from e0_controller.llm_adapter import LLMConfig
from e0_controller.llm_e2_port import LlmE2Port
from e0_controller.primitives import Edge, Outcome


# ─── Domain ──────────────────────────────────────────────────────────────────

STATES = [
    "INCIDENT_REPORTED",
    "CONTEXT_GATHERED",
    "IMPACT_ASSESSED",
    "MITIGATION_PROPOSED",
    "BRIEFING_DRAFTED",
    "DELIVERED",
]

# Linear happy path with side edge: IMPACT_ASSESSED can hit BLOCKED
EDGES = [
    ("INCIDENT_REPORTED",   "CONTEXT_GATHERED",    0.6, 0.4),
    ("CONTEXT_GATHERED",    "IMPACT_ASSESSED",      0.5, 0.3),
    ("IMPACT_ASSESSED",     "MITIGATION_PROPOSED",  0.5, 0.3),
    ("MITIGATION_PROPOSED", "BRIEFING_DRAFTED",     0.4, 0.3),
    ("BRIEFING_DRAFTED",    "DELIVERED",            0.3, 0.2),
    # Recovery path: IMPACT_ASSESSED can stall → go back for more context
    ("IMPACT_ASSESSED",     "CONTEXT_GATHERED",     0.8, 0.8),
]

TASK_DESCRIPTIONS = {
    ("INCIDENT_REPORTED",   "CONTEXT_GATHERED"):    (
        "Gather context for the incident: timeline, affected systems, "
        "stakeholders involved, and initial impact estimate. "
        "Be specific and concise."
    ),
    ("CONTEXT_GATHERED",    "IMPACT_ASSESSED"):     (
        "Assess the full impact of the incident: technical severity, "
        "business exposure, compliance risk, and affected user count. "
        "Quantify where possible."
    ),
    ("IMPACT_ASSESSED",     "MITIGATION_PROPOSED"): (
        "Propose a concrete mitigation plan: immediate containment actions, "
        "short-term remediation steps, and long-term prevention measures."
    ),
    ("MITIGATION_PROPOSED", "BRIEFING_DRAFTED"):    (
        "Draft an executive briefing (≤200 words): incident summary, "
        "business impact, mitigation actions taken, and next steps."
    ),
    ("BRIEFING_DRAFTED",    "DELIVERED"):           (
        "Final delivery check: review the briefing for completeness, "
        "accuracy, and appropriate tone. Confirm it is ready to send."
    ),
    ("IMPACT_ASSESSED",     "CONTEXT_GATHERED"):    (
        "Impact assessment is incomplete — gather additional context: "
        "missing data sources, unclear system boundaries, or open questions."
    ),
}

SCENARIO = textwrap.dedent("""\
    Incident: Production database cluster experienced unexpected failover
    at 03:42 UTC. 15% of API requests returned 500 errors for 23 minutes.
    Primary cause: storage controller firmware bug triggered by scheduled
    backup job. Incident resolved by 04:05 UTC via manual failover.
    Incident ID: INC-2026-0417. Severity: SEV-2.
""")


def build_landscape() -> Landscape:
    ls = Landscape()
    for source, target, delta, resistance in EDGES:
        ls.add_edge(source, target, delta=delta, resistance=resistance)
    return ls


# ─── Mock call_fn ─────────────────────────────────────────────────────────────

_MOCK_RESPONSES = {
    ("INCIDENT_REPORTED",   "CONTEXT_GATHERED"):    (
        "SUCCESS",
        "Context gathered: SEV-2 production DB failover at 03:42 UTC. "
        "Duration: 23 min. Affected: payment-api (~15% of requests). "
        "Root cause: firmware bug in storage controller (StorageOS v4.1.2). "
        "Stakeholders: SRE, Platform Eng, Finance.",
    ),
    ("CONTEXT_GATHERED",    "IMPACT_ASSESSED"):     (
        "SUCCESS",
        "Impact: 3,847 failed requests (est. €4,200 in lost transactions). "
        "No data loss. SLA breach threshold: not crossed (< 30 min). "
        "Compliance: no PII exposed. Customer-facing: partial degradation "
        "of checkout flow. Severity confirmed at SEV-2.",
    ),
    ("IMPACT_ASSESSED",     "MITIGATION_PROPOSED"): (
        "SUCCESS",
        "Mitigation: (1) Immediate — rolled back StorageOS to v4.0.8. "
        "(2) Short-term — disabled concurrent backup+failover scheduling. "
        "(3) Long-term — upgrade to StorageOS v4.2.0 (scheduled May 15). "
        "Canary testing protocol added for firmware updates.",
    ),
    ("MITIGATION_PROPOSED", "BRIEFING_DRAFTED"):    (
        "SUCCESS",
        "Executive Briefing — INC-2026-0417:\n"
        "On May 6 at 03:42 UTC, a storage firmware bug triggered an "
        "unplanned database failover affecting ~15% of payment API traffic "
        "for 23 minutes. No data loss occurred. Estimated revenue impact: "
        "€4,200. Immediate fix applied (firmware rollback). "
        "Longer-term prevention underway (StorageOS upgrade, canary testing). "
        "Full post-mortem scheduled for May 10.",
    ),
    ("BRIEFING_DRAFTED",    "DELIVERED"):           (
        "SUCCESS",
        "Briefing reviewed and confirmed ready for distribution. "
        "Tone: appropriate for C-level audience. All key facts verified "
        "against incident timeline. Delivery approved.",
    ),
    ("IMPACT_ASSESSED",     "CONTEXT_GATHERED"):    (
        "FAILURE",
        "Additional context request attempted but no new data sources "
        "identified — returning to available evidence.",
    ),
}


def mock_call_fn(system: str, user: str, config: LLMConfig) -> str:
    """Deterministic mock responses keyed by source→target in the prompt."""
    for (src, tgt), (outcome, result) in _MOCK_RESPONSES.items():
        if src in user and tgt in user:
            return json.dumps({
                "outcome": outcome,
                "result": result,
                "confidence": 0.88,
            })
    return json.dumps({
        "outcome": "SUCCESS",
        "result": "Transition completed.",
        "confidence": 0.75,
    })


# ─── Display helpers ──────────────────────────────────────────────────────────

OUTCOME_SYMBOL = {
    Outcome.SUCCESS: "✓",
    Outcome.FAILURE: "✗",
    Outcome.PARTIAL: "~",
    None: "—",
}


def _bar(value: float, width: int = 20) -> str:
    """ASCII progress bar: value in [0, 1]."""
    filled = max(0, min(width, round(value * width)))
    return "[" + "█" * filled + "·" * (width - filled) + f"] {value:.2f}"


def print_turn(turn, show_payload: bool) -> None:
    sym = OUTCOME_SYMBOL.get(turn.outcome, "?")
    esc = " [ESC]" if turn.escalated else ""
    il  = " [E1-hint]" if turn.inertia_low else ""
    print(f"  T{turn.turn_index:02d} {sym}{esc}{il}  "
          f"{turn.state_before:<28} → {turn.action or '—'}")
    if show_payload and turn.payload:
        snippet = str(turn.payload)[:120].replace("\n", " ")
        print(f"       LLM: {snippet}{'…' if len(str(turn.payload)) > 120 else ''}")


def print_inertia_table(landscape: Landscape, title: str) -> None:
    print(f"\n  {title}")
    print(f"  {'Edge':<50} {'Inertia':>7}  {'Trace (U/F)':>12}")
    print("  " + "─" * 74)
    for edge in sorted(landscape.edges, key=lambda e: (e.source, e.target)):
        h = landscape.historization
        inertia = h.inertia_factor(edge)
        u = h._U.get(edge, 0.0)
        f = h._F.get(edge, 0.0)
        arrow = f"{edge.source} → {edge.target}"
        bar = _bar(inertia, 12)
        print(f"  {arrow:<50} {bar}  U={u:.1f} F={f:.1f}")


# ─── Runs ─────────────────────────────────────────────────────────────────────

def run_session(
    landscape: Landscape,
    port: LlmE2Port,
    start: str = "INCIDENT_REPORTED",
    goal: str = "DELIVERED",
    max_turns: int = 12,
    show_payload: bool = False,
    label: str = "Session",
) -> E0Turn:
    session = E0Turn(landscape, port)
    print(f"\n  {label}: {start} → {goal}")
    print("  " + "─" * 60)
    turns = list(session.run(start, max_turns=max_turns, goal=goal))
    for t in turns:
        print_turn(t, show_payload)
    st = session.status()
    reached = (turns and turns[-1].state_after == goal)
    print(f"\n  Goal reached: {'YES' if reached else 'NO'} | "
          f"Turns: {st['turn_count']} | "
          f"Success: {st['success_count']} | "
          f"Failures: {st['failure_count']} | "
          f"E1-hints: {st['inertia_low_count']}")
    return session


def run_demo(live: bool = False, show_payloads: bool = False) -> None:
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║        E₀ — LlmE2Port Demo  (C294)                         ║")
    print("║        E₀ = Skeleton    LLM = Muscle                        ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    mode = "LIVE (real API)" if live else "MOCK (injectable call_fn)"
    print(f"\n  Mode:    {mode}")
    print(f"  Domain:  Incident Briefing Workflow")
    print(f"  Payloads shown: {show_payloads}")

    # ── Build port ────────────────────────────────────────────────────────────

    call_fn = None if live else mock_call_fn
    task = (
        "Produce a structured incident briefing for INC-2026-0417 "
        "(production DB failover, SEV-2, 23 min, €4200 impact)."
    )
    port = LlmE2Port(
        task=task,
        config=LLMConfig(model="gpt-5.4-mini", temperature=0.2),
        name="briefing_agent",
        call_fn=call_fn,
        scenario_block=SCENARIO,
    )
    print(f"\n  Port:    {port.port_id()}")
    print(f"  Model:   {port.status()['model']}")

    # ── Run 1: cold start (no historical knowledge) ───────────────────────────

    ls1 = build_landscape()

    print("\n" + "═" * 66)
    print("  RUN 1 — Cold start (empty historization)")
    print("═" * 66)
    print_inertia_table(ls1, "Inertia before Run 1 (all edges cold):")

    session1 = run_session(ls1, port, show_payload=show_payloads,
                           label="Run 1 (cold)")

    print_inertia_table(ls1, "Inertia after Run 1 (inscribed):")

    # ── Run 2: same landscape — E₀ has learned ────────────────────────────────

    print("\n" + "═" * 66)
    print("  RUN 2 — Same landscape, E₀ has learned from Run 1")
    print("═" * 66)

    session2 = run_session(ls1, port, show_payload=show_payloads,
                           label="Run 2 (warm)")

    print_inertia_table(ls1, "Inertia after Run 2 (further inscribed):")

    # ── Port swap: compare same landscape with a lambda port ──────────────────

    print("\n" + "═" * 66)
    print("  PORTABILITY — Same landscape, Lambda port (no LLM)")
    print("  (Same E0Turn loop. Only execution target swapped.)")
    print("═" * 66)

    from e0_controller.e2_port import LambdaE2Port

    ls2 = build_landscape()
    lambda_port = LambdaE2Port(
        fn=lambda state, action: Outcome.SUCCESS,
        name="always_success",
    )
    run_session(ls2, lambda_port, show_payload=False,
                label="Lambda port (E0Turn unchanged)")

    # ── with_task() demo ──────────────────────────────────────────────────────

    print("\n" + "═" * 66)
    print("  WITH_TASK — Immutable port update (same adapter, new task)")
    print("═" * 66)

    port2 = port.with_task(
        "Produce a brief for a DIFFERENT incident: "
        "INC-2026-0418 (memory leak in analytics service, SEV-3)."
    )
    ls3 = build_landscape()
    session3 = run_session(ls3, port2, show_payload=show_payloads,
                           label="port.with_task(new_task)")

    # ── Final summary ─────────────────────────────────────────────────────────

    print("\n" + "═" * 66)
    print("  SUMMARY")
    print("═" * 66)
    print(f"  E₀ ran {session1.status()['turn_count'] + session2.status()['turn_count']}"
          f" turns across 2 LLM sessions on the same landscape.")
    print(f"  Inertia profile inscribed — Run 2 is faster/more confident.")
    print(f"  Same E0Turn loop ran identically with LambdaE2Port.")
    print(f"  with_task() produced an independent port for a different briefing.")
    print()


# ─── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="E₀ LlmE2Port Demo — Incident Briefing Workflow"
    )
    parser.add_argument(
        "--live", action="store_true",
        help="Use real LLM (requires OPENAI_API_KEY). Default: mock mode."
    )
    parser.add_argument(
        "--show-payloads", action="store_true",
        help="Print LLM output snippet for each turn."
    )
    args = parser.parse_args()

    if args.live:
        # Load .env for API key
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
        if not os.environ.get("OPENAI_API_KEY"):
            print("ERROR: --live requires OPENAI_API_KEY in environment or .env")
            sys.exit(1)

    run_demo(live=args.live, show_payloads=args.show_payloads)


if __name__ == "__main__":
    main()
