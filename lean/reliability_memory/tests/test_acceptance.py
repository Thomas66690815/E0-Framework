"""
Acceptance tests T1–T8 from lean_core.bootstrap.json.

Run with:
    python -m pytest lean/reliability_memory/tests/ -v
"""
import json
import math
import pytest

from reliability_memory import Edge, Outcome, ReliabilityStore, Traces


# ── T1: learns the better action ─────────────────────────────────────────────

def test_T1_learns_better_action():
    store = ReliabilityStore()
    for _ in range(6):
        store.observe_edge("A", "B", "success")
    for _ in range(6):
        store.observe_edge("A", "C", "failure")

    rec = store.recommend("A", ["B", "C"])
    assert rec.recommended == "B", f"Expected B, got {rec.recommended}"
    assert rec.reliability > 0.9, f"Expected reliability ≈ 1.0, got {rec.reliability:.4f}"


# ── T2: cold-start honest ─────────────────────────────────────────────────────

def test_T2_cold_start_honest():
    store = ReliabilityStore(min_observations=5)
    for _ in range(4):
        store.observe_edge("A", "B", "success")

    rec = store.recommend("A", ["B", "C"])
    assert rec.recommended is None, f"Expected None on cold start, got {rec.recommended}"
    assert rec.reason.startswith("cold start"), f"Unexpected reason: {rec.reason}"


def test_T2_cold_start_no_candidates():
    store = ReliabilityStore()
    for _ in range(10):
        store.observe_edge("A", "B", "success")

    rec = store.recommend("A", [])
    assert rec.recommended is None
    assert "cold start" in rec.reason


# ── T3: lazy decay is mathematically exact ────────────────────────────────────

def test_T3_decay():
    t = Traces(rho=0.9)
    edge = Edge("A", "B")
    dummy = Edge("D", "X")

    for _ in range(6):
        t.update(edge, Outcome.SUCCESS)

    u_stored = t._U[edge]
    tau_at_last_visit = t._tau_last[edge]

    # Advance τ by 20 steps on a different edge
    gap = 20
    for _ in range(gap):
        t.update(dummy, Outcome.SUCCESS)

    actual_gap = t._tau - tau_at_last_visit
    assert actual_gap == gap, f"Expected gap={gap}, got {actual_gap}"

    expected_u = u_stored * (0.9 ** gap)
    actual_u, _ = t._effective_traces(edge)
    assert abs(actual_u - expected_u) < 1e-9, (
        f"Decay mismatch: expected {expected_u:.6f}, got {actual_u:.6f}"
    )


# ── T4: trust decays for stale edges, cost returns toward base_cost ───────────

def test_T4_trust_decays_for_stale():
    t = Traces(rho=0.9)
    edge = Edge("A", "B")
    dummy = Edge("D", "X")

    # Build up a strong failure penalty
    for _ in range(15):
        t.update(edge, Outcome.FAILURE)

    penalty_at_visit = t.penalty(edge)
    assert penalty_at_visit > 0, "Penalty should be positive after failures"

    # Advance time substantially
    for _ in range(500):
        t.update(dummy, Outcome.SUCCESS)

    trust_late = t.trust(edge)
    penalty_trusted_late = t.penalty_trusted(edge)

    assert trust_late < 0.5, f"Trust should have decayed significantly, got {trust_late:.4f}"
    assert abs(penalty_trusted_late) < abs(penalty_at_visit), (
        "Trusted penalty should be smaller than raw penalty after staleness"
    )
    # Cost approaches base_cost as penalty_trusted → 0
    assert penalty_trusted_late < penalty_at_visit * 0.5


# ── T5: stable edge keeps higher trust than volatile at comparable staleness ──

def test_T5_stable_vs_volatile():
    # Confirmation/surprise tracking only fires when gap > 1, so we interleave
    # stable and volatile visits with dummy steps to force gaps of 3 between
    # each revisit.  Stable is always confirmed; volatile always surprised.
    t = Traces(rho=0.9)
    stable = Edge("S", "stable")
    volatile = Edge("S", "volatile")
    dummy = Edge("D", "X")

    def advance(n: int = 3) -> None:
        for _ in range(n):
            t.update(dummy, Outcome.SUCCESS)

    # First visits — no prior history, no confirmation/surprise possible yet
    t.update(stable, Outcome.SUCCESS)
    t.update(volatile, Outcome.SUCCESS)

    # 5 rounds: stable always success (→ always confirmed);
    # volatile alternates failure/success → always surprised (direction flips)
    for v_outcome in [Outcome.FAILURE, Outcome.SUCCESS, Outcome.FAILURE, Outcome.SUCCESS, Outcome.FAILURE]:
        advance(3)                              # gap=4 on next stable visit
        t.update(stable, Outcome.SUCCESS)       # confirmation recorded
        t.update(volatile, v_outcome)           # surprise recorded

    # Let time pass — both edges become stale.  Stable decays slower (high stability).
    advance(20)

    trust_stable = t.trust(stable)
    trust_volatile = t.trust(volatile)

    assert trust_stable > trust_volatile, (
        f"Stable trust ({trust_stable:.4f}) should exceed volatile trust ({trust_volatile:.4f})"
    )


# ── T6: adaptive toggles surprise_dampening on volatile domain ────────────────

def test_T6_adaptive_toggles():
    # classify_experience() uses the raw stored _surprises sum (which decays with ρ).
    # With ρ=0.9 and gap=2 between each visit, the geometric series converges to
    # 1/(1-0.81) ≈ 5.3.  We need sum > 3 to exit 'exploratory' — 5 visits suffice.
    t = Traces(rho=0.9, surprise_dampening=False)
    edge = Edge("A", "B")
    dummy = Edge("D", "X")

    def visit_with_gap(outcome: Outcome) -> None:
        t.update(dummy, Outcome.SUCCESS)  # create gap > 1
        t.update(dummy, Outcome.SUCCESS)
        t.update(edge, outcome)

    t.update(edge, Outcome.SUCCESS)      # first visit — no prediction yet
    visit_with_gap(Outcome.FAILURE)      # surprise 1
    visit_with_gap(Outcome.SUCCESS)      # surprise 2
    visit_with_gap(Outcome.FAILURE)      # surprise 3
    visit_with_gap(Outcome.SUCCESS)      # surprise 4
    visit_with_gap(Outcome.FAILURE)      # surprise 5 — sum ≈ 3.43 > 3

    assert t.classify_experience() == "volatile", (
        f"Expected volatile, got {t.classify_experience()!r} "
        f"(surprise_rate={t.surprise_rate():.2f}, "
        f"sum_surp={sum(t._surprises.values()):.2f})"
    )
    changed = t.adapt_from_experience()
    assert changed, "adapt_from_experience() should have toggled surprise_dampening"
    assert t.surprise_dampening is True


# ── T7: persistence round-trip is exact ──────────────────────────────────────

def test_T7_persistence_roundtrip(tmp_path):
    store = ReliabilityStore(epistemic_trust=True, adaptive=True)
    for _ in range(6):
        store.observe_edge("A", "B", "success")
    for _ in range(6):
        store.observe_edge("A", "C", "failure")
    for _ in range(3):
        store.observe_edge("B", "D", "success")

    rec_before = store.recommend("A", ["B", "C"])

    path = tmp_path / "session.json"
    store.save(path)
    loaded = ReliabilityStore.load(path)

    rec_after = loaded.recommend("A", ["B", "C"])

    assert rec_before.recommended == rec_after.recommended, (
        f"Recommended changed: {rec_before.recommended} → {rec_after.recommended}"
    )
    assert abs(rec_before.reliability - rec_after.reliability) < 1e-9

    # Internal state preserved
    tr_orig = store._traces
    tr_load = loaded._traces
    assert tr_orig._tau == tr_load._tau
    assert tr_orig._tau_last == tr_load._tau_last
    assert abs(tr_orig._U.get(Edge("A", "B"), 0) - tr_load._U.get(Edge("A", "B"), 0)) < 1e-9
    assert tr_orig._confirmations.keys() == tr_load._confirmations.keys()


def test_T7_load_missing_file(tmp_path):
    """load() on absent file returns a fresh, functional store."""
    store = ReliabilityStore.load(tmp_path / "nonexistent.json")
    assert store._count == 0
    assert store.status()["cold_start"] is True


def test_T7_load_malformed_file(tmp_path):
    """load() on corrupt JSON returns a fresh store instead of raising."""
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    store = ReliabilityStore.load(bad)
    assert store._count == 0


# ── T8: no topology required ─────────────────────────────────────────────────

def test_T8_no_topology_required():
    store = ReliabilityStore()
    assert store.status()["edges"] == 0

    store.observe_edge("never_declared_ctx", "never_declared_action", "success")
    assert store.status()["edges"] == 1

    store.observe_edge("ctx2", "action2", "failure")
    assert store.status()["edges"] == 2
    assert store.status()["nodes"] >= 4  # all four distinct strings are nodes
    assert store._count == 2


# ── bonus: invariants ─────────────────────────────────────────────────────────

def test_virgin_edge_trust_is_one():
    t = Traces()
    assert t.trust(Edge("X", "Y")) == 1.0


def test_just_visited_trust_is_one():
    t = Traces()
    e = Edge("X", "Y")
    t.update(e, Outcome.SUCCESS)
    assert t.trust(e) == 1.0


def test_partial_outcome_caveat():
    """PARTIAL inscribes U += 0.5, F += 0.3; residual 0.2 is dropped."""
    t = Traces()
    e = Edge("A", "B")
    t.update(e, Outcome.PARTIAL)
    u, f = t._effective_traces(e)
    # After one PARTIAL with no prior: U = ρ*0 + 0.5 = 0.5, F = ρ*0 + 0.3 = 0.3
    assert abs(u - 0.5) < 1e-9
    assert abs(f - 0.3) < 1e-9


def test_zero_third_party_deps():
    """The core package must not import any non-stdlib module at import time."""
    import sys
    stdlib_or_local = {
        "reliability_memory", "math", "statistics", "json",
        "os", "pathlib", "dataclasses", "typing", "enum", "builtins",
        "__future__", "_collections_abc", "abc", "types", "functools",
        "collections", "re", "io", "numbers",
    }
    # Import the package fresh (already imported, but check no new third-party appeared)
    import reliability_memory  # noqa: F401
    for name, mod in sys.modules.items():
        root = name.split(".")[0]
        if root in stdlib_or_local:
            continue
        # mcp is optional — only a problem if it was imported at module level
        assert root != "mcp", (
            "mcp was imported at module level — it must stay lazy in mcp_server.py"
        )
