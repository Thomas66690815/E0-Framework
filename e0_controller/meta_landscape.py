"""
E₀ MetaLandscape (C296)
========================
Builds a navigable Landscape from PathSignature session history.

The core claim of structural self-similarity:

    The same E0Controller that navigates domain edges (Level 1)
    can navigate PathSignatures (Level 2) — without modification.

Level 1 (domain):
    State        = domain node           ("INBOX", "APPROVED")
    Edge         = domain transition     (INBOX → APPROVED)
    Outcome      = executor result       (SUCCESS / FAILURE)

Level 2 (meta):
    MetaState    = str(PathSignature)    ("(0, 1, 0)", "(0,)")
    MetaEdge     = consecutive sig pair  ((0,1,0) followed by (0,))
    MetaOutcome  = meta_execute_fn result (SUCCESS / FAILURE)

MetaLandscape.from_records() constructs a standard Landscape from
TrajectoryRecord history. The returned Landscape satisfies all E₀
primitives — E0Controller sees only states and edges.

Delta / Resistance defaults:
    delta=0.5, resistance=1.0 — uniform cold start.
    All structure emerges from MetaHistorization (same as domain L).
    Optional: traj_hist + use_quality_seed=True seeds delta from
    trace_quality differences between consecutive signatures.

Consecutive identical signatures are collapsed (no self-loops):
    (0,1,0), (0,1,0), (0,) → edge (0,1,0)→(0,) only.

Usage:
    from e0_controller.trajectory import TrajectoryHistorization, TrajectoryRecord
    from e0_controller.meta_landscape import MetaLandscape
    from e0_controller.controller import E0Controller

    traj_hist = TrajectoryHistorization()
    records = [...]  # from a domain session
    for r in records:
        traj_hist.inscribe(r)

    meta_ls = MetaLandscape.from_records(records, traj_hist)

    # E0Controller unchanged — self-similarity proven by construction:
    ctrl = E0Controller(meta_ls, meta_execute_fn)
    trace = ctrl.run(start=str(records[0].signature), goal=target_meta_state)
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from .landscape import Landscape
from .trajectory import PathSignature, TrajectoryHistorization, TrajectoryRecord


# ── String ↔ PathSignature conversion ─────────────────────────────────────────

def sig_to_meta_state(sig: PathSignature) -> str:
    """Convert PathSignature tuple to MetaState string label.

    The canonical form is Python's default tuple __repr__:
        (0,)     → "(0,)"
        (0, 1)   → "(0, 1)"
        (0, 1, 0) → "(0, 1, 0)"

    This is stable, unique per signature, and human-readable.
    """
    return str(sig)


def meta_state_to_sig(meta_state: str) -> PathSignature:
    """Convert MetaState string label back to PathSignature tuple.

    Inverse of sig_to_meta_state. Raises ValueError on malformed input.

    Args:
        meta_state: string produced by sig_to_meta_state,
                    e.g. "(0, 1, 0)" or "(0,)"

    Returns:
        PathSignature tuple

    Raises:
        ValueError: if meta_state cannot be parsed as a tuple of ints
    """
    try:
        parsed = eval(meta_state)  # noqa: S307 — controlled: only used on our own labels
    except Exception:
        raise ValueError(f"Cannot parse MetaState: {meta_state!r}")

    if isinstance(parsed, int):
        # Edge case: single-element tuple without trailing comma, e.g. "(0)"
        return (parsed,)
    if not isinstance(parsed, tuple):
        raise ValueError(
            f"MetaState must parse to a tuple, got {type(parsed).__name__}: "
            f"{meta_state!r}"
        )
    if not all(isinstance(x, int) for x in parsed):
        raise ValueError(
            f"MetaState elements must be ints: {meta_state!r}"
        )
    return parsed


# ── MetaLandscape ─────────────────────────────────────────────────────────────

class MetaLandscape:
    """Factory for building a Landscape from PathSignature history.

    MetaLandscape is not instantiated — use the class methods directly.
    The output is a standard Landscape, operable by E0Controller without
    any modification (self-similarity by construction).
    """

    @classmethod
    def from_records(
        cls,
        records: List[TrajectoryRecord],
        traj_hist: Optional[TrajectoryHistorization] = None,
        delta: float = 0.5,
        resistance: float = 1.0,
        use_quality_seed: bool = False,
    ) -> Landscape:
        """Build a navigable MetaLandscape from trajectory session records.

        For each consecutive pair of records with different signatures,
        adds a directed MetaEdge. Consecutive identical signatures are
        collapsed — staying in the same pattern is not a structural transition.

        Args:
            records:          List of TrajectoryRecord from a domain session.
                              Order matters: consecutive pairs form MetaEdges.
            traj_hist:        Optional TrajectoryHistorization with accumulated
                              U/F traces. Required when use_quality_seed=True.
            delta:            Base delta for MetaEdges (default 0.5, uniform).
            resistance:       Base resistance for MetaEdges (default 1.0).
            use_quality_seed: If True and traj_hist provided, computes delta
                              from abs(trace_quality_b - trace_quality_a)
                              when both signatures have trace_load >= 1.
                              Falls back to base delta otherwise.

        Returns:
            Landscape — standard E₀ Landscape with MetaStates as nodes
            and consecutive-signature transitions as edges.
            Empty records → empty Landscape (no states, no edges).
            Single record → one MetaState, no edges.

        Example:
            records = [rec(sig=(0,1,0)), rec(sig=(0,)), rec(sig=(0,1,0))]
            → Landscape with states {"(0, 1, 0)", "(0,)"}
              and edges (0,1,0)→(0,) and (0,)→(0,1,0)
        """
        ls = Landscape()

        if not records:
            return ls

        # Register all unique MetaStates
        seen_sigs = {r.signature for r in records}
        for sig in seen_sigs:
            ls.add_state(sig_to_meta_state(sig))

        # Add MetaEdges from consecutive distinct signatures
        seen_edges: set = set()
        for i in range(len(records) - 1):
            sig_a = records[i].signature
            sig_b = records[i + 1].signature

            # Skip self-loops (same signature consecutive)
            if sig_a == sig_b:
                continue

            meta_a = sig_to_meta_state(sig_a)
            meta_b = sig_to_meta_state(sig_b)
            edge_key = (meta_a, meta_b)

            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)

            # Compute edge delta
            edge_delta = delta
            if use_quality_seed and traj_hist is not None:
                load_a = traj_hist.trace_load(sig_a)
                load_b = traj_hist.trace_load(sig_b)
                if load_a >= 1 and load_b >= 1:
                    qa = traj_hist.trace_quality(sig_a)
                    qb = traj_hist.trace_quality(sig_b)
                    edge_delta = max(0.05, min(1.0, abs(qb - qa)))

            ls.add_edge(meta_a, meta_b, delta=edge_delta, resistance=resistance)

        return ls

    @classmethod
    def from_signatures(
        cls,
        signature_sequence: List[PathSignature],
        delta: float = 0.5,
        resistance: float = 1.0,
    ) -> Landscape:
        """Build a MetaLandscape from a raw sequence of PathSignatures.

        Convenience method when TrajectoryRecord objects are not available.
        Equivalent to from_records() with synthetic records (no traj_hist).

        Args:
            signature_sequence: Ordered list of PathSignature tuples.
            delta:              Uniform delta for all MetaEdges.
            resistance:         Uniform resistance for all MetaEdges.

        Returns:
            Landscape with MetaStates and MetaEdges.
        """
        ls = Landscape()

        if not signature_sequence:
            return ls

        seen_sigs = set(signature_sequence)
        for sig in seen_sigs:
            ls.add_state(sig_to_meta_state(sig))

        seen_edges: set = set()
        for i in range(len(signature_sequence) - 1):
            sig_a = signature_sequence[i]
            sig_b = signature_sequence[i + 1]
            if sig_a == sig_b:
                continue
            meta_a = sig_to_meta_state(sig_a)
            meta_b = sig_to_meta_state(sig_b)
            edge_key = (meta_a, meta_b)
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)
            ls.add_edge(meta_a, meta_b, delta=delta, resistance=resistance)

        return ls
