"""
Eâ‚€ Demo â€” MetaLandscape: Structural Self-Similarity (C298)
==========================================================
Demonstrates ARC-H: the same E0Controller that navigates a domain
graph at Level 1 also navigates a graph of PathSignatures at Level 2.

Proof by construction. Zero lines of E0Controller modified.

â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Level 1 â€” Domain: Support Ticket Pipeline
  OPEN â†’ TRIAGED â†’ INVESTIGATING â†’ RESOLVED â†’ CLOSED
  Communities: {OPEN, TRIAGED} = C0  |  {INVESTIGATING, RESOLVED, CLOSED} = C1

  Two trajectory shapes arise from the domain:
    Direct run : sig = (0, 1)        â€” stays in C0 then crosses to C1
    Retry  run : sig = (0, 1, 0, 1) â€” crosses back to C0, then C1 again

Level 2 â€” MetaLandscape (Eâ‚€ on PathSignatures):
  Built from Level-1 session history via MetaLandscape.from_records()
  MetaStates:  "(0, 1)"   and   "(0, 1, 0, 1)"
  E0Controller navigates between these pattern states â€” same code.
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

Usage:
    py -3 -m e0_controller.demo_meta_landscape
"""

from __future__ import annotations

from typing import List, Set, Tuple

from e0_controller.e0_turn import E0Turn
from e0_controller.e2_port import LambdaE2Port
from e0_controller.landscape import Landscape
from e0_controller.meta_controller import make_meta_execute_fn
from e0_controller.meta_landscape import MetaLandscape, sig_to_meta_state
from e0_controller.primitives import Outcome
from e0_controller.trajectory import (
    PathSignature,
    TrajectoryHistorization,
    TrajectoryRecord,
)


# â”€â”€ Domain definition â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

COMMUNITIES: List[Set[str]] = [
    {"OPEN", "TRIAGED"},                        # Community 0 â€” intake
    {"INVESTIGATING", "RESOLVED", "CLOSED"},    # Community 1 â€” resolution
]


def _community_of(node: str) -> int:
    for i, community in enumerate(COMMUNITIES):
        if node in community:
            return i
    return -1


def path_to_signature(path: List[str]) -> PathSignature:
    """Convert a node path to a PathSignature (community index tuple, compressed)."""
    if not path:
        return ()
    indices = [_community_of(n) for n in path]
    compressed: List[int] = []
    for idx in indices:
        if not compressed or compressed[-1] != idx:
            compressed.append(idx)
    return tuple(compressed)


def _count_crossings(path: List[str]) -> int:
    return sum(
        1 for i in range(len(path) - 1)
        if _community_of(path[i]) != _community_of(path[i + 1])
    )


# â”€â”€ Domain landscape for Level-1 verification â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def build_direct_landscape() -> Landscape:
    """Direct path only â€” no retry edge. E0 always takes OPENâ†’â€¦â†’CLOSED."""
    ls = Landscape()
    for src, tgt, delta, resistance in [
        ("OPEN",          "TRIAGED",       0.5, 0.5),
        ("TRIAGED",       "INVESTIGATING", 0.5, 0.4),
        ("INVESTIGATING", "RESOLVED",      0.5, 0.4),
        ("RESOLVED",      "CLOSED",        0.3, 0.3),
    ]:
        ls.add_edge(src, tgt, delta=delta, resistance=resistance)
    return ls


# â”€â”€ Display helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _bar(value: float, width: int = 16) -> str:
    filled = max(0, min(width, round(value * width)))
    return "[" + "â–ˆ" * filled + "Â·" * (width - filled) + f"] {value:.2f}"


def print_meta_turn(turn) -> None:
    sym = {Outcome.SUCCESS: "âœ“", Outcome.FAILURE: "âœ—", None: "â€”"}.get(turn.outcome, "?")
    esc = " [ESC]" if turn.escalated else ""
    il  = " [E1]"  if turn.inertia_low else ""
    print(f"  M{turn.turn_index:02d} {sym}{esc}{il}  "
          f"{turn.state_before:<22} â†’ {turn.action or 'â€”':<22}  "
          f"â†’ {turn.state_after}")


def print_meta_inertia(meta_ls: Landscape) -> None:
    print(f"  {'MetaEdge':<48} {'Inertia':>8}  {'U':>5}  {'F':>5}")
    print("  " + "â”€" * 68)
    h = meta_ls.historization
    for edge in sorted(meta_ls.edges, key=lambda e: (e.source, e.target)):
        inertia = h.inertia_factor(edge)
        u = h._U.get(edge, 0.0)
        f = h._F.get(edge, 0.0)
        arrow = f"{edge.source!r} â†’ {edge.target!r}"
        print(f"  {arrow:<48} {_bar(inertia, 10)}  U={u:.1f}  F={f:.1f}")


# â”€â”€ Level 1: Domain sessions (path-explicit) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#
# In production, these paths come from real E0Turn sessions on a domain
# landscape. Here we model them explicitly to show the two signature shapes
# that arise when some sessions take a direct route and others involve
# a community backtrack (triage rework).
#
# The sig= computation is real (path_to_signature uses the actual community
# partition). The meta-level computation is entirely real.

# Two canonical path shapes for the ticket domain:
DIRECT_PATH = ["OPEN", "TRIAGED", "INVESTIGATING", "RESOLVED", "CLOSED"]
RETRY_PATH  = ["OPEN", "TRIAGED", "INVESTIGATING", "TRIAGED",
               "INVESTIGATING", "RESOLVED", "CLOSED"]


def build_trajectory_records() -> Tuple[
    List[TrajectoryRecord], TrajectoryHistorization
]:
    """Build TrajectoryRecords from domain session path models.

    Alternates: direct, retry, direct, retry, direct.
    coverage_delta: direct=0.020 (productive), retry=0.008 (improving-stagnant).
    """
    session_specs = [
        ("direct", DIRECT_PATH, 0.020),
        ("retry",  RETRY_PATH,  0.008),
        ("direct", DIRECT_PATH, 0.020),
        ("retry",  RETRY_PATH,  0.008),
        ("direct", DIRECT_PATH, 0.020),
    ]

    traj_hist = TrajectoryHistorization()
    records: List[TrajectoryRecord] = []

    for i, (mode, path, coverage_delta) in enumerate(session_specs, start=1):
        sig = path_to_signature(path)
        crossings = _count_crossings(path)
        record = TrajectoryRecord(
            signature=sig,
            mode=mode,
            coverage_delta=coverage_delta,
            community_crossings=crossings,
        )
        traj_hist.inscribe(record)
        records.append(record)

        # Display
        sym = "â†’".join(path)
        print(f"  Run {i} ({mode}): {sym}")
        print(f"            sig={sig_to_meta_state(sig)}  "
              f"crossings={crossings}  Î”cov={coverage_delta:.3f}  "
              f"({record.outcome})")

    return records, traj_hist


# â”€â”€ Level-1 verification: real E0Turn on direct landscape â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def verify_level1() -> None:
    """Run a real E0Turn on the direct landscape â€” shows E0 in action."""
    ls = build_direct_landscape()
    port = LambdaE2Port(fn=lambda s, a: Outcome.SUCCESS, name="direct_port")
    session = E0Turn(ls, port)
    history = list(session.run("OPEN", max_turns=8, goal="CLOSED"))
    path = (["OPEN"] if not history else
            [history[0].state_before] + [t.state_after for t in history])
    sym = "â†’".join(path)
    sig = path_to_signature(path)
    print(f"\n  Live E0Turn:  {sym}")
    print(f"               sig={sig_to_meta_state(sig)}  "
          f"turns={len(history)}  "
          f"[confirms direct path â†’ (0, 1)]")


# â”€â”€ Level 2: MetaLandscape + E0Controller â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def run_meta_level(
    records: List[TrajectoryRecord],
    traj_hist: TrajectoryHistorization,
    max_meta_turns: int = 10,
) -> None:
    """Build MetaLandscape and run E0Controller + E0Turn on it."""

    # Build
    meta_ls = MetaLandscape.from_records(
        records,
        traj_hist=traj_hist,
        use_quality_seed=True,
        delta=0.5,
    )

    sorted_states = sorted(meta_ls.states)
    print(f"  MetaLandscape:")
    print(f"    MetaStates : {sorted_states}")
    print(f"    MetaEdges  : {len(meta_ls.edges)}")
    for edge in sorted(meta_ls.edges, key=lambda e: e.source):
        delta_val = meta_ls._delta.get(edge, 0.5)
        print(f"      {edge.source!r:>24} â†’ {edge.target!r:<24}  Î´={delta_val:.3f}")

    if not meta_ls.edges:
        print("\n  [No MetaEdges â€” all sessions produced the same signature]")
        return

    meta_start = sorted_states[0]
    meta_goal  = sorted_states[-1]

    print(f"\n  Meta-navigation:  start={meta_start!r}  â†’  goal={meta_goal!r}")
    print()

    # THE PROOF: same E0Turn constructor, same loop, different Landscape grain
    meta_port    = LambdaE2Port(fn=lambda s, a: Outcome.SUCCESS, name="meta_port")
    meta_session = E0Turn(meta_ls, meta_port)

    meta_history = list(
        meta_session.run(meta_start, max_turns=max_meta_turns, goal=meta_goal)
    )

    for turn in meta_history:
        print_meta_turn(turn)

    reached = meta_history and meta_history[-1].state_after == meta_goal
    st = meta_session.status()
    print(f"\n  MetaGoal reached: {'YES âœ“' if reached else 'NO'} | "
          f"Turns: {st['turn_count']} | "
          f"Success: {st['success_count']}")

    print()
    print("  MetaLandscape inertia after meta-navigation:")
    print_meta_inertia(meta_ls)


# â”€â”€ Main â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def run_demo() -> None:
    print()
    print("â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—")
    print("â•‘   Eâ‚€ â€” MetaLandscape Demo  (C298)                              â•‘")
    print("â•‘   Structural Self-Similarity: Eâ‚€ operates at any grain         â•‘")
    print("â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•")

    print("""
  Domain: Support Ticket Pipeline
  â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  OPEN(C0) â”€â”€â†’ TRIAGED(C0) â”€â”€â†’ INVESTIGATING(C1) â”€â”€â†’ RESOLVED(C1) â”€â”€â†’ CLOSED(C1)
                                     â†‘
                              TRIAGED(C0)  â† retry path (community backtrack)

  Direct run : OPEN â†’ TRIAGED â†’ INVESTIGATING â†’ RESOLVED â†’ CLOSED
               sig = (0, 1)   [two community segments]

  Retry  run : OPEN â†’ TRIAGED â†’ INVESTIGATING â†’ TRIAGED â†’ INVESTIGATING â†’ RESOLVED â†’ CLOSED
               sig = (0, 1, 0, 1)   [four community segments, backtrack once]
  â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
""")

    # â”€â”€ Level 1 â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    print("â•" * 70)
    print("  LEVEL 1 â€” Domain Sessions  (Support Ticket Pipeline)")
    print("â•" * 70)
    print()

    records, traj_hist = build_trajectory_records()
    verify_level1()

    # Summary
    sig_map = {}
    for r in records:
        key = sig_to_meta_state(r.signature)
        sig_map[r.signature] = sig_map.get(r.signature, 0) + 1

    print(f"\n  Session summary:")
    print(f"  {'Signature':<25}  {'Count':>5}  {'Quality':>8}  {'Load':>5}")
    print("  " + "â”€" * 48)
    for sig in sorted(sig_map, key=sig_to_meta_state):
        q = traj_hist.trace_quality(sig)
        load = traj_hist.trace_load(sig)
        print(f"  {sig_to_meta_state(sig):<25}  {sig_map[sig]:>5}  {q:>+8.3f}  {load:>5}")

    # â”€â”€ Level 2 â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    print()
    print("â•" * 70)
    print("  LEVEL 2 â€” MetaLandscape  (Eâ‚€ on PathSignatures)")
    print("â•" * 70)
    print("""
  E0Controller + E0Turn are called with the SAME constructor, SAME API.
  They do not know they are navigating PathSignature states instead of
  ticket pipeline states. Self-similarity is not an analogy â€” it is the
  same code running on a different grain.
""")

    run_meta_level(records, traj_hist)

    # â”€â”€ Proof statement â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    print()
    print("â•" * 70)
    print("  SELF-SIMILARITY PROOF  (ARC-H)")
    print("â•" * 70)
    print("""
  Level 1:  E0Turn(ticket_landscape, lambda_port)  â†’  state = "INVESTIGATING"
  Level 2:  E0Turn(meta_landscape,   lambda_port)  â†’  state = "(0, 1, 0, 1)"

  Same primitive:   SELECT â†’ EXECUTE â†’ HISTORIZE
  Same loop:        E0Turn.run_turn() / history() / status()
  Same landscape:   Landscape(states, edges, Historization)

  Different grain:
    L1 state: "INVESTIGATING"    â€” a ticket workflow step
    L2 state: "(0, 1, 0, 1)"    â€” a behavioral pattern shape

  Eâ‚€ is structurally self-similar.
  Zero lines of E0Controller or E0Turn modified.
""")


if __name__ == "__main__":
    run_demo()

