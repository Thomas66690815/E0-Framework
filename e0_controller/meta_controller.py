"""
E₀ MetaController (C297)
=========================
E0Controller operating on a MetaLandscape — the structural self-similarity
proof by construction.

Self-similarity theorem (E₀):
    For any Landscape L satisfying the E₀ primitives, E0Controller(L, exec)
    operates correctly without knowing what L represents.

    MetaLandscape satisfies all E₀ primitives by construction:
        - States are MetaState strings (PathSignature labels)
        - Edges are MetaEdges (consecutive distinct signatures)
        - Historization is a standard Historization instance

    Therefore E0Controller(MetaLandscape, meta_exec) ≡ E0Controller(L₁, exec₁)
    at the code level.  Zero lines of E0Controller are modified.

This module provides:
    make_meta_execute_fn() — creates a meta_execute_fn for use with
                             E0Controller on a MetaLandscape.

In production, the meta_execute_fn:
    1. Decodes meta_action → target PathSignature
    2. Runs a domain session toward that pattern
    3. Returns SUCCESS when the domain session reaches the target pattern,
       FAILURE otherwise.

For testing and self-similarity proofs:
    make_meta_execute_fn(outcomes, default) — returns a predictable callable
    that makes E0Controller.run() fully deterministic without domain execution.

Usage (test / proof):
    from e0_controller.meta_landscape import MetaLandscape
    from e0_controller.meta_controller import make_meta_execute_fn
    from e0_controller.controller import E0Controller
    from e0_controller.primitives import Outcome

    meta_ls = MetaLandscape.from_signatures([(0,), (0,1), (0,1,0)])
    meta_exec = make_meta_execute_fn(default=Outcome.SUCCESS)

    # E0Controller is NOT modified — self-similarity proven:
    ctrl = E0Controller(meta_ls, meta_exec)
    trace = ctrl.run(start="(0,)", goal="(0, 1, 0)", max_cycles=10)

Usage (production):
    def production_meta_exec(meta_state: str, meta_action: str) -> Outcome:
        target_sig = meta_state_to_sig(meta_action)
        # Run domain session toward target_sig pattern...
        reached = run_domain_until_signature(target_sig)
        return Outcome.SUCCESS if reached else Outcome.FAILURE

    ctrl = E0Controller(meta_ls, production_meta_exec)
"""

from __future__ import annotations

from typing import Callable, Dict, Optional, Tuple

from .meta_landscape import meta_state_to_sig
from .primitives import Outcome


# ── Meta execute_fn factory ────────────────────────────────────────────────────

def make_meta_execute_fn(
    outcomes: Optional[Dict[Tuple[str, str], Outcome]] = None,
    default: Outcome = Outcome.SUCCESS,
) -> Callable[[str, str], Outcome]:
    """Create a meta_execute_fn for E0Controller on a MetaLandscape.

    The returned callable has signature (meta_state: str, meta_action: str)
    → Outcome, which is exactly the execute_fn contract for E0Controller.

    Args:
        outcomes:   Optional explicit outcome mapping {(state, action): Outcome}.
                    When a (state, action) pair is found here, returns that
                    Outcome instead of default.
        default:    Outcome to return when no explicit mapping exists.
                    Default: Outcome.SUCCESS (optimistic meta-executor).

    Returns:
        Callable[(meta_state, meta_action) → Outcome]

    Example:
        # All transitions succeed:
        exec_fn = make_meta_execute_fn()

        # Specific failure:
        exec_fn = make_meta_execute_fn(
            outcomes={("(0, 1)", "(0,)"): Outcome.FAILURE},
            default=Outcome.SUCCESS,
        )

        # Plug into E0Controller:
        ctrl = E0Controller(meta_landscape, exec_fn)
    """
    _outcomes = outcomes or {}

    def meta_exec(meta_state: str, meta_action: str) -> Outcome:
        return _outcomes.get((meta_state, meta_action), default)

    return meta_exec


# ── Domain-session meta_execute_fn builder ────────────────────────────────────

def make_domain_meta_execute_fn(
    domain_run_fn: Callable[[str, int], bool],
    max_domain_turns: int = 20,
) -> Callable[[str, str], Outcome]:
    """Create a meta_execute_fn backed by real domain session execution.

    In production, this wires a domain session into the meta-level loop:
    when E₀ selects a meta_action (target PathSignature), it runs the
    domain session toward that pattern and reports back.

    Args:
        domain_run_fn:  Callable[(target_sig_str: str, max_turns: int) → bool]
                        True when the target pattern was reached, False otherwise.
                        The caller is responsible for constructing this from
                        their domain session (E0Turn + LlmE2Port, etc.)
        max_domain_turns: maximum turns to spend on one meta-step (default 20)

    Returns:
        Callable[(meta_state, meta_action) → Outcome]

    Example:
        def my_domain_run(target_sig_str: str, max_turns: int) -> bool:
            target_sig = meta_state_to_sig(target_sig_str)
            # ... run domain session, check if reached target_sig ...
            return reached

        meta_exec = make_domain_meta_execute_fn(my_domain_run)
        ctrl = E0Controller(meta_ls, meta_exec)
    """
    def meta_exec(meta_state: str, meta_action: str) -> Outcome:
        try:
            reached = domain_run_fn(meta_action, max_domain_turns)
            return Outcome.SUCCESS if reached else Outcome.FAILURE
        except Exception:
            return Outcome.FAILURE

    return meta_exec
