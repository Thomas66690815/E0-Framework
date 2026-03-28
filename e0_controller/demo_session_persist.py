"""
E₀ Demo — Session Persistence (greedy-trap landscape)
======================================================
Runs the greedy-trap scenario through Session, verifying that
MemOS context, run records, and tuning memory are saved to disk.

Then resumes the session from disk and runs again, proving
cross-session persistence works.

Usage:
    python -m e0_controller.demo_session_persist
"""

from __future__ import annotations

import json
import os
import shutil
import sys

from .controller import HybridMode
from .landscape import Landscape
from .memory_os import CanonRef
from .primitives import Outcome
from .session import Session


DEMO_DIR = os.path.join("memos", "_demo_persist")
SESSION_ID = "greedy-trap-demo"


def build_trap_landscape() -> Landscape:
    """Same landscape as demo_greedy_trap — A↔C loop + forward path."""
    L = Landscape()
    L.add_edge("A", "C", delta=1.0, resistance=0.3)
    L.add_edge("C", "A", delta=1.0, resistance=0.3)
    L.add_edge("A", "B", delta=1.0, resistance=0.8)
    L.add_edge("B", "E", delta=1.0, resistance=0.5)
    L.add_edge("E", "G", delta=1.0, resistance=0.5)
    L.add_edge("G", "GOAL", delta=1.0, resistance=0.3)
    return L


def always_success(source: str, target: str) -> Outcome:
    return Outcome.SUCCESS


def print_json(path: str) -> None:
    """Pretty-print a JSON file."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    print(json.dumps(data, indent=2, default=str))


def run_demo() -> None:
    # Clean slate
    if os.path.exists(DEMO_DIR):
        shutil.rmtree(DEMO_DIR)

    print("=" * 60)
    print("E₀ Session Persistence Demo")
    print("=" * 60)

    # ── Run 1 ──────────────────────────────────────────────────
    print("\n── Run 1: new session (AMPLITUDE_ON_DISAGREE) ──")
    session = Session(
        SESSION_ID,
        build_trap_landscape(),
        always_success,
        base_dir=DEMO_DIR,
        canon_refs=[CanonRef("e0-canon", "v1", "canon/e0-canon-plain.txt")],
        controller_kwargs=dict(
            hybrid_mode=HybridMode.AMPLITUDE_ON_DISAGREE,
            hybrid_horizon=4,
            hybrid_goals={"GOAL"},
            alpha=0.5,
            recent_k=2,
        ),
    )
    result = session.run("A", goal="GOAL", max_cycles=10)

    print(f"  Path:    {' → '.join(result.trace.path)}")
    print(f"  Steps:   {len(result.trace.steps)}")
    print(f"  Reached: {result.trace.path[-1]}")
    print(f"  Resumed: {result.resumed}")

    # ── Show files ────────────────────────────────────────────
    print("\n── Persisted files ──")
    for root, dirs, files in os.walk(DEMO_DIR):
        for fname in sorted(files):
            fpath = os.path.join(root, fname)
            rel = os.path.relpath(fpath, DEMO_DIR)
            size = os.path.getsize(fpath)
            print(f"  {rel}  ({size} bytes)")

    session_path = os.path.join(DEMO_DIR, "sessions", f"{SESSION_ID}.json")
    print(f"\n── Session context ({SESSION_ID}.json) ──")
    print_json(session_path)

    runs_dir = os.path.join(DEMO_DIR, "runs", SESSION_ID)
    run_files = sorted(os.listdir(runs_dir))
    print(f"\n── Run record ({run_files[0]}) ──")
    print_json(os.path.join(runs_dir, run_files[0]))

    tuning_path = os.path.join(DEMO_DIR, "tuning", f"{SESSION_ID}.json")
    if os.path.exists(tuning_path):
        print(f"\n── Tuning memory ──")
        print_json(tuning_path)

    # ── Run 2: resume ─────────────────────────────────────────
    print("\n── Run 2: resume from disk ──")
    session2 = Session.resume(SESSION_ID, always_success, base_dir=DEMO_DIR)
    result2 = session2.run("A", goal="GOAL", max_cycles=10)

    print(f"  Path:    {' → '.join(result2.trace.path)}")
    print(f"  Steps:   {len(result2.trace.steps)}")
    print(f"  Resumed: {result2.resumed}")

    recent = session2.recent_runs(limit=5)
    print(f"  Run records on disk: {len(recent)}")

    print("\n── Done ──")
    print(f"All data lives in: {os.path.abspath(DEMO_DIR)}")


if __name__ == "__main__":
    run_demo()
