"""
E₀ Domain Studio Demo — ARC-K (C308)
======================================
End-to-end logistics use-case: E₀ learns an order-fulfillment process
from historical CSV data and then applies its knowledge to recommend
the next step in real-time.

Two-phase workflow
------------------
PHASE 1 — LEARN
  1. Create a DomainSession("logistics")
  2. Inject historical CSV (edge topology + outcomes)
  3. Run 50 learning episodes via HistorizedQuantumWalk
     (oracle: happy-path rewards ORDER→PICKING→LOADING→DELIVERED)
  4. Persist to DomainStore
  5. Print conviction map (before APPLY)

PHASE 2 — APPLY
  6. Load session from DomainStore
  7. Switch mode to APPLY
  8. Simulate 10 order-fulfillment decisions:
       recommend() → execute (simulated) → record()
  9. Print final conviction map (after APPLY)
 10. Print domain status

Key E₀ properties shown
------------------------
- Cold-start detection (h._tau < 5 → no recommendation)
- Conviction accumulation: happy path edges dominate over time
- Persistence: Historization survives save/load round-trip
- Online learning: record() updates Historization during APPLY phase
- Topology auto-expansion: new edges created on-demand in recommend()

Usage:
    py -3 -m e0_controller.demo_domain_studio
"""

from __future__ import annotations

import os
import textwrap

from e0_controller.domain_session import DomainMode, DomainSession, DomainStore
from e0_controller.primitives import Outcome


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

DOMAIN_NAME = "logistics_demo"
STORE_DIR = os.path.join("memos", "domains_demo")

# Historical order-fulfillment data (CSV: source, target, outcome)
# Reflects a real distribution: most orders succeed, backorders are rare,
# defects trigger rework, damage leads to returns.
HISTORICAL_CSV = """\
ORDER_RECEIVED,PICKING,success
ORDER_RECEIVED,PICKING,success
ORDER_RECEIVED,PICKING,success
ORDER_RECEIVED,PICKING,success
ORDER_RECEIVED,BACKORDER,failure
ORDER_RECEIVED,BACKORDER,failure
PICKING,QUALITY_CHECK,success
PICKING,QUALITY_CHECK,success
PICKING,QUALITY_CHECK,success
PICKING,REWORK,failure
QUALITY_CHECK,LOADING,success
QUALITY_CHECK,LOADING,success
QUALITY_CHECK,LOADING,success
QUALITY_CHECK,REWORK,failure
LOADING,DISPATCHED,success
LOADING,DISPATCHED,success
LOADING,DISPATCHED,success
DISPATCHED,DELIVERED,success
DISPATCHED,DELIVERED,success
DISPATCHED,DELIVERED,success
DISPATCHED,DELIVERED,success
DISPATCHED,DAMAGED,failure
DAMAGED,RETURN,failure
RETURN,ORDER_RECEIVED,partial
REWORK,QUALITY_CHECK,partial
REWORK,QUALITY_CHECK,partial
BACKORDER,ORDER_RECEIVED,partial
""".strip()

# Happy-path oracle: rewards the express lane
# ORDER_RECEIVED → PICKING → QUALITY_CHECK → LOADING → DISPATCHED → DELIVERED
HAPPY_PATH = {
    ("ORDER_RECEIVED", "PICKING"),
    ("PICKING", "QUALITY_CHECK"),
    ("QUALITY_CHECK", "LOADING"),
    ("LOADING", "DISPATCHED"),
    ("DISPATCHED", "DELIVERED"),
}


def oracle(source: str, target: str) -> Outcome:
    return Outcome.SUCCESS if (source, target) in HAPPY_PATH else Outcome.FAILURE


# ─────────────────────────────────────────────────────────────────────────────
# Printing helpers
# ─────────────────────────────────────────────────────────────────────────────

def _hr(char: str = "─", width: int = 60) -> None:
    print(char * width)


def _section(title: str) -> None:
    print()
    _hr("═")
    print(f"  {title}")
    _hr("═")


def _print_conviction_map(cm: dict[str, float], label: str) -> None:
    print(f"\n  Conviction map — {label}")
    _hr()
    if not cm:
        print("  (empty — no inscriptions yet)")
        return
    happy_edges = {"ORDER_RECEIVED→PICKING", "PICKING→QUALITY_CHECK",
                   "QUALITY_CHECK→LOADING", "LOADING→DISPATCHED",
                   "DISPATCHED→DELIVERED"}
    for edge_key in sorted(cm):
        score = cm[edge_key]
        bar = "█" * int(score * 20)
        tag = " ← happy path" if edge_key in happy_edges else ""
        print(f"  {edge_key:<40s}  {score:.3f}  {bar}{tag}")
    avg = sum(cm.values()) / max(len(cm), 1)
    _hr()
    print(f"  avg conviction: {avg:.3f}   edges: {len(cm)}")


def _print_status(status: dict) -> None:
    _hr()
    print(f"  Domain  : {status['name']}")
    print(f"  Mode    : {status['mode']}")
    print(f"  Episodes: {status['episode_count']}")
    print(f"  States  : {status['states']}   Edges: {status['edges']}")
    print(f"  Insc.   : {status['total_inscriptions']:.2f} (rho-decayed)")
    print(f"  Cold?   : {status['cold_start']}")
    _hr()


# ─────────────────────────────────────────────────────────────────────────────
# Simulated order events for APPLY phase
# ─────────────────────────────────────────────────────────────────────────────

# Tuples of (current_state, candidates, simulated_real_outcome)
# Simulates 10 real orders arriving sequentially
APPLY_EVENTS = [
    ("ORDER_RECEIVED", ["PICKING", "BACKORDER"],          "success"),
    ("ORDER_RECEIVED", ["PICKING", "BACKORDER"],          "success"),
    ("PICKING",        ["QUALITY_CHECK", "REWORK"],       "success"),
    ("QUALITY_CHECK",  ["LOADING", "REWORK"],             "success"),
    ("LOADING",        ["DISPATCHED"],                    "success"),
    ("DISPATCHED",     ["DELIVERED", "DAMAGED"],          "success"),
    ("ORDER_RECEIVED", ["PICKING", "BACKORDER"],          "failure"),   # backorder event
    ("ORDER_RECEIVED", ["PICKING", "BACKORDER"],          "success"),
    ("PICKING",        ["QUALITY_CHECK", "REWORK"],       "failure"),   # rework event
    ("QUALITY_CHECK",  ["LOADING", "REWORK"],             "success"),
]


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 1 — LEARN
# ─────────────────────────────────────────────────────────────────────────────

def phase_learn(store: DomainStore) -> None:
    _section("PHASE 1 — LEARN: Building domain knowledge from historical data")

    # 1. Create session
    session = DomainSession(
        name=DOMAIN_NAME,
        description="E-Commerce Order Fulfillment",
        topic="logistics",
    )
    print(f"  Created DomainSession({DOMAIN_NAME!r}, mode=LEARN)")

    # 2. Inject historical CSV
    print(f"\n  Injecting {HISTORICAL_CSV.count(chr(10)) + 1} CSV rows ...")
    report = session.inject(HISTORICAL_CSV, hint="csv")
    print(f"  → edges_added={report.edges_added}, "
          f"inscriptions={report.inscriptions}, "
          f"skipped={report.skipped}")
    if report.warnings:
        for w in report.warnings:
            print(f"  ⚠ {w}")

    # Print conviction before learning (all zeros — cold start)
    cm_before = session.conviction_map()
    _print_conviction_map(cm_before, "after CSV injection (before learning)")

    # 3. Learn
    print(f"\n  Running 50 learning episodes (oracle: happy path) ...")
    learn_report = session.learn(
        oracle_fn=oracle,
        n_episodes=50,
        start="ORDER_RECEIVED",
        goal="DELIVERED",
        max_steps=40,
    )
    print(f"  → episodes={learn_report.episodes}, "
          f"steps={learn_report.total_steps}, "
          f"goal_rate={learn_report.goal_rate:.2f} (success steps/episode)")
    print(f"  → S={learn_report.success_count}  "
          f"F={learn_report.failure_count}  "
          f"P={learn_report.partial_count}  "
          f"edges_explored={learn_report.edges_explored}")
    if learn_report.warnings:
        for w in learn_report.warnings:
            print(f"  ⚠ {w}")

    cm_after_learn = session.conviction_map()
    _print_conviction_map(cm_after_learn, "after 50 learning episodes")

    # 4. Persist
    path = store.save(session)
    print(f"\n  Saved to: {path}")

    status = session.status()
    _print_status(status)


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2 — APPLY
# ─────────────────────────────────────────────────────────────────────────────

def phase_apply(store: DomainStore) -> None:
    _section("PHASE 2 — APPLY: Real-time order-fulfillment decisions")

    # 5. Load from store
    session = store.load(DOMAIN_NAME)
    assert session is not None, f"DomainStore could not load {DOMAIN_NAME!r}"
    print(f"  Loaded DomainSession from store. Episodes before: {session._episode_count}")

    # 6. Switch to APPLY
    session.set_mode(DomainMode.APPLY)
    print(f"  Mode → APPLY")

    # 7. Simulate 10 order events
    print(f"\n  Simulating {len(APPLY_EVENTS)} order events ...\n")
    _hr()
    correct = 0
    for i, (state, candidates, real_outcome) in enumerate(APPLY_EVENTS, 1):
        result = session.recommend(state, candidates)
        chosen = result.recommended or (candidates[0] if candidates else "?")
        cold_tag = " [cold-start]" if result.cold_start else ""
        conv_tag = f"  conviction={result.conviction_score:.3f}" if not result.cold_start else ""
        print(f"  #{i:02d}  {state:<22s} → recommend: {chosen:<18s}{cold_tag}{conv_tag}")

        # The system routes to `chosen`; real_outcome is what actually happened
        ok = session.record(state, chosen, real_outcome)
        outcome_sym = "✓" if real_outcome == "success" else ("⚡" if real_outcome == "partial" else "✗")
        print(f"       real outcome: {real_outcome:<8s} {outcome_sym}   record ok={ok}")

        # Track: did we recommend a path where real outcome was success?
        if real_outcome == "success":
            correct += 1

    _hr()
    accuracy = correct / len(APPLY_EVENTS)
    print(f"\n  Real outcomes: {correct}/{len(APPLY_EVENTS)} success = {accuracy:.0%}")

    # 8. Final conviction map
    cm_final = session.conviction_map()
    _print_conviction_map(cm_final, "after APPLY phase (with online learning)")

    # 9. Persist updated session
    store.save(session)

    # 10. Final status
    _section("Final domain status")
    _print_status(session.status())


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def run_demo() -> None:
    print()
    _hr("═")
    print("  E₀ Domain Studio — Logistics Demo (ARC-K / C308)")
    print("  Two-phase: LEARN from history → APPLY to live orders")
    _hr("═")

    store = DomainStore(store_dir=STORE_DIR)

    # Clean up any previous run
    if store.exists(DOMAIN_NAME):
        store.delete(DOMAIN_NAME)
        print(f"  (deleted previous demo run: {DOMAIN_NAME!r})")

    phase_learn(store)
    phase_apply(store)

    print()
    _hr("═")
    print("  Demo complete.")
    print(f"  Persisted at: {os.path.join(STORE_DIR, DOMAIN_NAME + '.json')}")
    _hr("═")
    print()


if __name__ == "__main__":
    run_demo()
