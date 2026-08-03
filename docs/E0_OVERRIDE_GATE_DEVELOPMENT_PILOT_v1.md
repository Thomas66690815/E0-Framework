# E0 Override-Gate Development Pilot v1

**Work package:** WP-GATE-0.9

**Date:** 2026-08-03

**Status:** scaling cause isolated on development seed 0; no protected split
access; no gate result

## Purpose and boundary

The completed v1 calibration contained 2,116 records labelled
`algorithm_timeout`. WP-GATE-0.9 tests whether those timeouts measure the
closed-loop candidate or the additional paired-branch instrumentation.

The pilot accepts only G1 development seeds, only `wall_grid`, at most 40
parent interactions, and at most 120 seconds per killable child process. The
executed pilot used seed 0 and a 30-second case limit. It cannot construct
calibration, verification, or protected-holdout domains and emits
`not_gate_result=true`.

Raw records are retained under
`artifacts/override_gate/development/wp_gate_0_9/`.

## Cost result

The same disabled parent policy was measured with paired branch collection on
and off:

| Scale | Parent only | Paired evidence | Wall-time factor | Geometry decisions | Result |
|---:|---:|---:|---:|---:|---|
| 100 | 0.438 s | 8.098 s | 18.48× | 21 → 518 | both complete |
| 500 | 2.951 s | 16.225 s | 5.50× | 40 → 1,356 | both complete |
| 1,000 | 6.762 s | >30.232 s | >4.47× | 40 → unknown | paired timeout only |

At `N=100`, 17 guard-eligible parent disagreements launched 34 branch
rollouts and 497 additional branch interactions. At `N=500`, 29 disagreements
launched 58 rollouts and 1,316 additional interactions. The parent itself had
only 21 or 40 decisions.

This is the scaling cause: every eligible parent disagreement synchronously
forks two counterfactual trajectories, and every branch step recomputes
`E_FULL_GEOMETRY`. A branch may consume the remaining full interaction budget.
The instrumentation therefore multiplies both the number and increasing
per-scale cost of geometry decisions.

## Timeout classification defect

The v1 worker wraps `run_instrumented_episode` in the episode deadline.
`run_instrumented_episode` contains both the parent trajectory and all paired
rollouts. The replicate deadline encloses the same combined work.

Consequently, a v1 `algorithm_timeout` does not distinguish:

- the candidate parent exceeding its algorithm budget;
- a counterfactual diagnostic branch consuming its budget; or
- accumulated geometry cost across many paired branches.

The `N=1000` pilot demonstrates the defect directly: the parent-only case
finishes in 6.762 seconds, while the same parent with paired evidence exceeds
30 seconds. Calling the latter an algorithm-performance failure of the parent
would be incorrect.

The v1 selection remains mechanically reproducible under its frozen rules and
continues to select `gate_disabled`. Scientifically, however, its 2,116
timeout records are measurement-confounded and cannot establish a clean
closed-loop threshold ranking.

## Gate activation result

The pilot also resolves whether the zero-override calibration was a dead code
path. At `N=100`, budget 40:

| Policy | Overrides | Parent result | Local paired evidence |
|---|---:|---|---|
| `gate_disabled` | 0 | goal in 21 steps | 15 harmful, 0 beneficial, 2 neutral |
| `margin_000` | 9 | budget exhausted at 40 | 2 harmful, 1 beneficial, 6 neutral |
| `margin_040` | 0 | goal in 21 steps | same trajectory as disabled |

The active zero-margin policy therefore executed real overrides and converted
this development parent from success into failure. The `0.40` policy remained
inactive because the maximum observed support margin was
`0.3989492644040752`.

This is a scoped mechanism diagnosis, not a selected threshold and not a
universal rejection of the gate.

## Required v2 experiment structure

A rerun with larger timeouts would preserve the confound and is not justified.
The next versioned design must separate the two preregistered stages:

1. **Stage A — paired decision evidence:** collect a frozen sample of decision
   snapshots and evaluate greedy/lookahead branches under its own explicit
   instrumentation budget and status. Instrumentation time must never become a
   parent algorithm timeout.
2. **Stage B — closed-loop policy evaluation:** run each candidate without
   synchronous paired rollouts. Time and score only the parent trajectory,
   while recording observed disagreements, common-guard eligibility, and
   executed overrides.

Before any new full calibration, this separation must pass a development-only
pilot at all three scales and demonstrate that parent results are invariant to
whether Stage-A evidence is collected separately.

Because timeout semantics and the evidence-generation contract change, this
requires a new versioned experiment instance and a new authorization. The
current verification and protected holdout remain closed.

## WP-GATE-0.10 follow-up

The required development-only stage-separation pilot is complete. Stage A now
uses a separate instrumentation process and a one-pair sample cap; Stage B
runs the closed-loop parent without branches. All eight bounded cases
completed, including N=1000, with no timeout or worker error.

At N=100, N=500, and N=1000, the independent Stage-A and Stage-B disabled
control replays had identical parent summaries and identical parent decision
trace digests. The branch-free N=100 `margin_000` parent also reproduced nine
executed overrides and budget exhaustion. This validates the architecture,
not a threshold. See `E0_OVERRIDE_GATE_V2_DEVELOPMENT_ARCHITECTURE_v1.md`.
