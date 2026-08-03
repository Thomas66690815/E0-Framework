# E0 Override-Gate Calibration v2 — Development Workers

**Work package:** WP-GATE-0.13

**Date:** 2026-08-03

**Status:** development worker and immutable-attempt boundary implemented and
exercised; fresh-split execution and authorization remain absent

## Outcome

WP-GATE-0.13 implements the process and persistence boundary needed before a
v2 calibration can be authorized. It does not implement a production outcome
command. The executable pilot accepts only development seeds, currently seed
0, and every output records `calibration_executed=false`,
`verification_executed=false`, `protected_holdout_accessed=false`, and
`not_gate_result=true`.

The pilot demonstrated:

- one killable, branch-free and snapshot-free Stage-B parent worker;
- a complete development decision trace usable by the frozen outcome-blind
  sampler;
- a separately killable branch-free Stage-A parent replay with exact trace
  digest comparison;
- one independently killable process per selected paired decision;
- distinct algorithm-timeout and infrastructure-error classifications;
- immutable, digest-bound, atomically published attempt files; and
- newest-attempt-first consolidation that fails rather than falling back to an
  older valid attempt.

## Development pilot

The bounded case was `wall_grid`, N=100, development seed 0, active policy
`margin_000`, evaluation episode 10, and an interaction budget of 40.

Stage B completed 40 parent decisions with no paired branches or branch
snapshots. Nine decisions executed an override. The frozen hash sampler chose
the four lowest-priority overrides without reading any outcome field.

Stage A independently repeated the branch-free parent. Its decision-trace
SHA-256 equalled the Stage-B source digest. Four separate child processes then
replayed exactly the four selected decision identities; all four produced one
paired branch record. Branch instrumentation time was never reported as
closed-loop parent time.

Two attempt-1 files, one per stage, were written through a same-directory
temporary file, flushed, fsynced, and atomically hard-linked to their final
write-once names. The consolidation selected both latest attempts and recorded
`selected_latest_attempts_without_fallback=true`.

These numbers prove only the mechanics on a deliberately small development
case. They do not estimate benefit, safety, timeout rates, or a confidence-gate
threshold.

## Failure semantics

Stage B is enclosed by a hard replicate process deadline. Expiry yields
`algorithm_timeout`; a child exception yields `infrastructure_error`.

Stage A first runs its exact parent replay behind its own deadline. Each frozen
sample is then evaluated by a distinct child process. A pair deadline yields
`stage_a_unresolved`; the result is not imputed. A child exception is an
infrastructure error. Parent digest mismatch also fails as infrastructure
invalid.

The current development caps are deliberately smaller than the frozen
experiment: at most four episodes, at most 40 interactions, and at most 120
seconds per process. Production timeout values remain those in the immutable
v2 contract and have not been exercised here.

## Resume and attempt rules

Attempt names bind a safe cell ID and positive attempt number. Their envelope
binds stage, record digest, safety flags, and the full record. Existing attempt
paths cannot be overwritten.

Consolidation groups files by the filename identity, chooses the numerically
greatest attempt first, and only then parses and validates it. Therefore a
corrupt or invalid latest attempt stops consolidation even when an earlier
valid attempt exists. Missing and unexpected cells also fail closed.

## Remaining boundary

WP-GATE-0.13 still does not provide:

- a builder for calibration seeds 5000–5019;
- verification or protected-holdout builders;
- production-sized Stage-A or Stage-B matrix commands;
- an external authorization-record validator; or
- an authorization-gated GitHub outcome workflow.

The next work package should freeze the execution commit, add an independently
reviewable authorization record and validator, and expose the production
workflow only behind that exact digest. No fresh seed should be instantiated
before those controls pass review.

## Evidence

- implementation: `e0_controller/override_gate_calibration_v2_workers.py`
- tests: `e0_controller/test_override_gate_calibration_v2_workers.py`
- pilot: `artifacts/override_gate/development/wp_gate_0_13/pilot.json`
- pilot SHA-256:
  `467de7f261a9b8feaac2a212fbce9acec68c8a36cc09654c0d2f2cfcf0293ba2`
- immutable attempts:
  `artifacts/override_gate/development/wp_gate_0_13/attempts/`
- focused validation: 30 tests passed across worker, sampler, and earlier
  development-stage suites
