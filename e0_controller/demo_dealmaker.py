"""
E₀ Demo — Dealmaker (C301)
===========================
First real-world use case: E₀ bootstraps a Landscape from domain knowledge
and navigates it to recommend the next best action in a complex deal.

This demonstrates ARC-I in full:
    Phase 1 — BOOTSTRAP
        InteractiveBootstrapSession receives 3 knowledge chunks
        (customer context, competitor analysis, own strengths)
        LLM extracts decision states and transitions (Option B: guided)
        → stable Landscape, ready for navigation

    Phase 2 — NAVIGATE
        E0Turn(landscape, LlmE2Port) runs on the bootstrapped Landscape
        E₀ selects paths; LLM executes transitions
        Outcome: E₀ recommends prioritised next actions

    Phase 3 — LEARN
        TrajectoryRecord saved for future deals
        Same pattern → MetaLandscape over time

─────────────────────────────────────────────────────────────

Domain: pre-bid deal strategy
    3 competitors, 3-year equipment + services contract
    Customer: uncertainty about what drives them
    Goal: identify the one argument that shifts their decision

─────────────────────────────────────────────────────────────
Usage:
    py -3 -m e0_controller.demo_dealmaker

Requires: OPENAI_API_KEY in .env or environment.
For offline demo (no API key): use --dry-run flag (fake LLM responses).
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import List

from e0_controller.e0_turn import E0Turn
from e0_controller.e2_port import LambdaE2Port
from e0_controller.landscape_bootstrapper import (
    BootstrapResult,
    BootstrapValidationError,
    InteractiveBootstrapSession,
)
from e0_controller.llm_adapter import LLMConfig, LLMCallFn
from e0_controller.llm_e2_port import LlmE2Port
from e0_controller.primitives import Outcome


# ── Domain knowledge chunks ───────────────────────────────────────────────────
# Three independent knowledge sources about this deal situation.
# In production these would come from CRM, research notes, discovery calls.

CHUNK_CUSTOMER = """
Customer Profile — Municipal Infrastructure Authority (MIA):
- 1200 employees, public sector procurement, decision by committee (5 members)
- Historical behaviour: conservative — prefers proven vendors over innovators
- Primary stated concerns: compliance, uptime guarantees, vendor stability
- Unstated signal (from discovery call): cost overruns in last contract caused
  internal political pressure; CFO is now the effective blocker
- Contract duration preference: 3 years with optional extension
- Decision timeline: offer deadline in 4 weeks, award in 8 weeks
- Key unknown: does the committee weight price or risk-avoidance higher?
"""

CHUNK_COMPETITOR = """
Competitor Analysis — Three bidders including us:
Competitor A (incumbent): strong relationship, known issues with response time,
  currently under pricing pressure from their own supply chain problems.
  Likely to underbid on base price but load services fees.
Competitor B (new entrant): aggressive pricing, no local reference customers,
  weak on compliance documentation.
Our position: mid-market pricing, strong compliance track record,
  3 local reference customers in same sector.
Key differentiator we have: dedicated local service team (others use
  remote support). This reduces perceived operational risk.
Weakness: our core product is 8% more expensive than Competitor A base price.
"""

CHUNK_OWN_STRENGTHS = """
Our Offer Strengths and Constraints:
- Product: certified for all required compliance frameworks (others: 1 of 3)
- Service: local team, 4h response SLA (industry standard: 8h)
- Reference customers: 3 comparable public sector contracts, all renewed
- Price: 8% above cheapest competitor on equipment; services margin flexible
- Constraint: cannot reduce equipment margin below 12%
- Flexibility: can bundle extended warranty, reduce services price
- Key insight from references: customers in this sector most fear political
  fallout from a failed rollout, not the initial price difference
"""

# What E₀ navigates toward
DEAL_GOAL = "WINNING_ARGUMENT_IDENTIFIED"
DEAL_START = "INTEL_GAP"

# Categories for Option-B guided extraction
CATEGORIES = [
    "decision point",
    "information state",
    "risk assessment",
    "action",
]

# ── Dry-run fake LLM responses ────────────────────────────────────────────────

_BOOTSTRAP_RESPONSE = json.dumps({
    "domain_summary": "Pre-bid deal strategy for public sector equipment contract",
    "edges": [
        {
            "source": "INTEL_GAP",
            "target": "CUSTOMER_DRIVER_KNOWN",
            "delta": 0.7,
            "resistance": 0.9,
            "label": "discovery call or reference check reveals primary driver",
        },
        {
            "source": "INTEL_GAP",
            "target": "RISK_PROFILE_ASSESSED",
            "delta": 0.5,
            "resistance": 0.6,
            "label": "analyse committee composition and political context",
        },
        {
            "source": "CUSTOMER_DRIVER_KNOWN",
            "target": "ARGUMENT_DESIGNED",
            "delta": 0.6,
            "resistance": 0.5,
            "label": "construct argument targeting primary driver",
        },
        {
            "source": "RISK_PROFILE_ASSESSED",
            "target": "ARGUMENT_DESIGNED",
            "delta": 0.5,
            "resistance": 0.4,
            "label": "frame argument around risk reduction",
        },
        {
            "source": "ARGUMENT_DESIGNED",
            "target": "COMPETITOR_RESPONSE_MODELLED",
            "delta": 0.4,
            "resistance": 0.5,
            "label": "stress-test argument against known competitor strengths",
        },
        {
            "source": "COMPETITOR_RESPONSE_MODELLED",
            "target": "WINNING_ARGUMENT_IDENTIFIED",
            "delta": 0.3,
            "resistance": 0.3,
            "label": "validate argument survives competitor comparison",
        },
    ],
})

_NAVIGATE_SUCCESS = json.dumps({
    "outcome": "success",
    "result": (
        "Transition executed. The local service team + 4h SLA argument "
        "directly addresses the committee's fear of a failed rollout. "
        "Risk-avoidance framing outweighs the 8% price delta when political "
        "cost of failure is higher than procurement savings."
    ),
})


def _make_dry_run_bootstrap_fn() -> LLMCallFn:
    """Returns a fake call_fn for bootstrap that returns the static response."""
    def _fn(system: str, user: str, config: LLMConfig) -> str:
        return _BOOTSTRAP_RESPONSE
    return _fn


def _make_dry_run_navigate_fn() -> LLMCallFn:
    """Returns a fake call_fn for navigation that always returns success."""
    def _fn(system: str, user: str, config: LLMConfig) -> str:
        return _NAVIGATE_SUCCESS
    return _fn


# ── Display helpers ───────────────────────────────────────────────────────────

def _bar(value: float, width: int = 14) -> str:
    filled = max(0, min(width, round(value * width)))
    return "[" + "█" * filled + "·" * (width - filled) + f"] {value:.2f}"


def print_landscape(result: BootstrapResult) -> None:
    schema = result.schema
    ls = result.landscape
    print(f"\n  Domain: {schema.domain_summary}")
    print(f"  States ({len(schema.states)}): {sorted(schema.states)}")
    print(f"  Edges  ({len(schema.edges)}):")
    for edge_spec in schema.edges:
        print(
            f"    {edge_spec.source:<32} → {edge_spec.target:<34}"
            f"  δ={edge_spec.delta:.2f}  R={edge_spec.resistance:.2f}"
        )
        if edge_spec.label:
            print(f"      → '{edge_spec.label}'")
    if schema.warnings:
        print(f"\n  Warnings:")
        for w in schema.warnings:
            print(f"    ⚠ {w}")
    if schema.skipped_edges:
        print(f"\n  Skipped edges: {len(schema.skipped_edges)}")


def print_turn(turn) -> None:
    sym = {Outcome.SUCCESS: "✓", Outcome.FAILURE: "✗", None: "—"}.get(
        turn.outcome, "?"
    )
    esc = " [ESC]" if turn.escalated else ""
    il = " [E1]" if turn.inertia_low else ""
    print(
        f"  T{turn.turn_index:02d} {sym}{esc}{il}  "
        f"{turn.state_before:<32} → {turn.action or '—':<32}  "
        f"→ {turn.state_after}"
    )
    if turn.payload and isinstance(turn.payload, str) and turn.payload.strip():
        # Show first 120 chars of LLM output
        preview = turn.payload.strip().replace("\n", " ")[:120]
        if len(turn.payload.strip()) > 120:
            preview += "…"
        print(f"         [{preview}]")


def print_landscape_inertia(ls) -> None:
    h = ls.historization
    print(f"\n  {'Edge':<66}  {'Inertia':>8}  U  F")
    print("  " + "─" * 82)
    for edge in sorted(ls.edges, key=lambda e: e.source):
        inertia = h.inertia_factor(edge)
        u = h._U.get(edge, 0.0)
        f = h._F.get(edge, 0.0)
        arrow = f"  {edge.source!r:<32} → {edge.target!r:<32}"
        print(f"{arrow}  {_bar(inertia, 8)}  U={u:.1f}  F={f:.1f}")


# ── Phase 1: Bootstrap ────────────────────────────────────────────────────────

def run_bootstrap(dry_run: bool) -> BootstrapResult:
    print("  Building InteractiveBootstrapSession ...")
    print(f"  Categories: {CATEGORIES}")
    print()

    session = InteractiveBootstrapSession(
        categories=CATEGORIES,
        config=LLMConfig(model="gpt-4.1-mini", temperature=0.1),
        call_fn=_make_dry_run_bootstrap_fn() if dry_run else None,
        max_states=12,
    )

    chunks = [CHUNK_CUSTOMER, CHUNK_COMPETITOR, CHUNK_OWN_STRENGTHS]
    labels = ["customer_profile", "competitor_analysis", "own_strengths"]

    for i, (chunk, label) in enumerate(zip(chunks, labels), start=1):
        count = session.add_chunk(chunk)
        preview = chunk.strip().splitlines()[0][:60]
        print(f"  Chunk {i} ({label}): {preview!r}  [total: {count}]")

    print(f"\n  Calling LLM{'(dry-run)' if dry_run else '(live)'}  ...")
    result = session.finalize(start=DEAL_START, goal=DEAL_GOAL)
    print(f"  Landscape built: {len(result.schema.states)} states, "
          f"{len(result.schema.edges)} edges")
    return result


# ── Phase 2: Navigate ─────────────────────────────────────────────────────────

def run_navigate(result: BootstrapResult, dry_run: bool, max_turns: int) -> None:
    ls = result.landscape
    schema = result.schema

    if dry_run:
        port = LlmE2Port(
            task=(
                "You are advising a sales team in a pre-bid deal strategy. "
                "Analyse the domain context and recommend the best action "
                "for each transition."
            ),
            config=LLMConfig(model="gpt-4.1-mini"),
            call_fn=_make_dry_run_navigate_fn(),
        )
    else:
        port = LlmE2Port(
            task=(
                "You are advising a sales team in a pre-bid deal strategy. "
                "Analyse the domain context and recommend the best action "
                "for each transition."
            ),
            config=LLMConfig(model="gpt-4.1-mini"),
        )

    session = E0Turn(ls, port)
    print(f"  E0Turn: start={schema.start!r}  goal={schema.goal!r}  "
          f"max_turns={max_turns}")
    print()

    history = list(
        session.run(schema.start, max_turns=max_turns, goal=schema.goal)
    )

    for turn in history:
        print_turn(turn)

    reached = history and history[-1].state_after == schema.goal
    st = session.status()
    print(
        f"\n  Goal reached: {'YES ✓' if reached else 'NO'} | "
        f"Turns: {st['turn_count']} | "
        f"Success: {st['success_count']}"
    )


# ── Phase 3: Inertia readout ──────────────────────────────────────────────────

def print_post_navigation(result: BootstrapResult) -> None:
    print("\n  Landscape inertia after navigation:")
    print("  (higher inertia → E₀ trusts this path; lower → explore more)")
    print_landscape_inertia(result.landscape)


# ── Main ──────────────────────────────────────────────────────────────────────

def run_demo(dry_run: bool = True, max_turns: int = 8) -> None:
    print()
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║   E₀ — Dealmaker Demo  (C301)                                  ║")
    print("║   ARC-I: Bootstrap Landscape from domain knowledge             ║")
    print("╚══════════════════════════════════════════════════════════════════╝")

    print("""
  Domain: Pre-bid Deal Strategy
  ─────────────────────────────────────────────────────────────
  3 competitors, 3-year equipment + services contract
  Customer: public sector committee, risk-averse, CFO as blocker
  Goal: identify the one argument that shifts their decision
  ─────────────────────────────────────────────────────────────
""")

    # ── Phase 1: Bootstrap ────────────────────────────────────────────────────
    print("═" * 70)
    print("  PHASE 1 — BOOTSTRAP  (domain knowledge → Landscape)")
    print("═" * 70)
    print()

    try:
        result = run_bootstrap(dry_run=dry_run)
    except BootstrapValidationError as exc:
        print(f"\n  ERROR: Bootstrap failed — {exc}")
        print(f"  Errors: {exc.errors}")
        return

    print_landscape(result)

    # ── Phase 2: Navigate ─────────────────────────────────────────────────────
    if not result.landscape.edges:
        print("\n  [No edges — cannot navigate]")
        return

    print()
    print("═" * 70)
    print("  PHASE 2 — NAVIGATE  (E0Turn on bootstrapped Landscape)")
    print("═" * 70)
    print("""
  E0Turn uses the same SELECT→EXECUTE→HISTORIZE loop as every other domain.
  The Landscape was built from text — E₀ does not know this.
""")

    run_navigate(result, dry_run=dry_run, max_turns=max_turns)

    # ── Phase 3: Inertia ──────────────────────────────────────────────────────
    print()
    print("═" * 70)
    print("  PHASE 3 — LEARN  (Historization readout)")
    print("═" * 70)

    print_post_navigation(result)

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    print("═" * 70)
    print("  ARC-I PROOF")
    print("═" * 70)
    print("""
  Bootstrap: 3 knowledge chunks → LLM extraction → Landscape
             Option B: category-guided extraction ensures
             only decision-relevant states are produced.

  Navigate:  E0Turn(bootstrapped_landscape, LlmE2Port)
             Identical to any other E₀ domain.
             E₀ does not know the Landscape was built from text.

  Learn:     Inertia on edges encodes which paths worked.
             Next deal with similar profile: reuse Landscape structure
             or build MetaLandscape over trajectory history.

  Phase contract respected:
             Landscape frozen at finalize() — all Historization valid.
             No edges added during navigation.
""")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="E₀ Dealmaker Demo (C301)")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use live OpenAI API (requires OPENAI_API_KEY in .env)",
    )
    parser.add_argument(
        "--max-turns", type=int, default=8, help="Max navigation turns"
    )
    args = parser.parse_args()
    run_demo(dry_run=not args.live, max_turns=args.max_turns)
