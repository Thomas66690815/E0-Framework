# E0 Override-Gate Calibration Execution v1

**Work package:** WP-GATE-0.7
**Date:** 2026-07-31
**Status:** historical implementation boundary; calibration later authorized
and completed — see `E0_OVERRIDE_GATE_CALIBRATION_RESULT_v1.md`

## Purpose

WP-GATE-0.7 adds the outcome-producing distribution layer for the already
frozen `E0-OVERRIDE-GATE-CAL-INSTANCE-v1`. It changes no scorer, generator,
candidate, utility, risk budget, statistic, split, or legacy default.

The implementation is deliberately inert until an external authorization JSON
and its canonical SHA-256 are supplied to a manual GitHub dispatch. No
authorization record is committed by this work package, and neither `push` nor
`schedule` can trigger calibration.

## Cell-aligned matrix

The execution matrix contains exactly:

```text
12 policies × 4 families × 3 scales = 144 cells
20 calibration seeds per cell       = 2,880 tasks
```

One GitHub job owns one complete candidate-family-scale cell. The 20 seeds are
never split across jobs. This differs intentionally from the older 240-batch
planning display, which remains a dry-run partition and is not an execution
topology.

Every cell record pins its index, policy, family, scale, 20 canonical tasks,
task-list SHA-256, frozen instance digest, source commit, execution commit,
authorization digest, and GitHub run attempt.

## External authorization

Execution requires all four manual workflow inputs:

1. the full reviewed execution commit;
2. a complete calibration-only authorization JSON;
3. the canonical SHA-256 of that exact JSON; and
4. the exact confirmation phrase
   `AUTHORIZE_FROZEN_CALIBRATION_ONLY`.

The record must contain the WP-GATE-0.6 schema, including:

- the frozen instance ID and digest;
- the same full execution commit checked out by GitHub;
- `authorized_split=calibration`;
- `calibration_execution_authorized=true`;
- both protected-split authorizations set to `false`;
- `retuning_after_authorization=false`; and
- a non-empty authorizer and authorization date.

The reviewed commit must exist before this record is created; therefore the
record is external to the commit it authorizes and avoids a self-referential
hash. A template can be materialized only with the exact confirmation phrase:

```text
python -m e0_controller.override_gate_calibration_distributed \
  authorization-template \
  --execution-commit <FULL_SHA> \
  --authorized-by <NAME> \
  --authorized-on <YYYY-MM-DD> \
  --confirmation AUTHORIZE_FROZEN_CALIBRATION_ONLY \
  --output authorization.json
```

Generating and dispatching that record is the future authorization act. It is
not performed in WP-GATE-0.7.

## Execution and failure semantics

Each cell job:

- validates the external authorization again;
- reconstructs only calibration tasks;
- uses four supervisors, fresh replicate processes, episode checkpoints, and
  the frozen hard limits;
- writes atomic result shards;
- retains infrastructure-failure artifacts; and
- emits a hashed cell manifest even when an infrastructure failure makes the
  job fail.

Algorithmic timeout, path-cap, and method-OOM statuses remain preregistered
zero-scored results. Infrastructure failures are not scores.

GitHub matrix `fail-fast` is disabled. No retry is started automatically. If a
failed job is manually rerun, its new `github.run_attempt` produces a new
artifact and recomputes all 20 seeds in that cell.

## Latest-attempt rule

Consolidation discovers every retained cell attempt and selects the highest
run-attempt number for each cell. It never falls back to an older successful
attempt when the latest attempt failed. Duplicate attempts, missing cells,
invalid hashes, stale commits, mismatched authorization digests, incomplete
inventories, or corrupt shards stop consolidation.

All historical infrastructure-failure files are retained. Only when the
latest attempt of all 144 cells is complete are exactly 2,880 shards copied to
the consolidation directory and passed to the frozen WP-GATE-0.6 statistics.

## GitHub workflow

`.github/workflows/override-gate-calibration-execute.yml` is manual only. It
has three stages:

1. validate authorization, run no-outcome distribution contracts, and emit
   the 144-cell matrix;
2. execute complete cells with at most 20 GitHub jobs in parallel; and
3. choose latest attempts and consolidate only the exact complete matrix.

Each cell has a six-hour GitHub job boundary. The consolidation job has a
two-hour boundary. These workflow limits supplement, rather than replace, the
frozen per-episode and per-replicate limits.

Cell artifacts necessarily become accessible to repository administrators
during an authorized run. Reading partial outcomes for stopping, candidate
changes, or retuning is forbidden. The external record freezes
`retuning_after_authorization=false`; partial artifacts exist only for recovery
and complete-matrix consolidation.

## Protected-split boundary

The distributed CLI accepts no split parameter. It always reconstructs the
complete calibration plan. The execution workflow contains no verification or
protected-holdout command. Those domains remain unavailable in the engine.

Even a successful calibration is development evidence with
`not_gate_result=true`. It can select at most one scoped policy for a later,
separately implemented and separately authorized verification work package.

## Validation performed now

WP-GATE-0.7 tests use only task identities, synthetic authorization records,
fabricated completed shards, and synthetic attempt manifests. They verify the
matrix, digest binding, confirmation phrase, pre-domain rejection, latest
attempt selection, complete-cell merging, and static workflow guards.

No test calls the calibration executor with a preregistered task. Therefore:

```text
calibration_execution_authorized = false
calibration_executed             = false
calibration_outcomes_observed    = false
verification_executed            = false
protected_holdout_accessed        = false
not_gate_result                   = true
```

## Required sequence before execution

1. review and commit WP-GATE-0.7;
2. push the reviewed commit;
3. rerun the planning-only GitHub workflow on that exact commit;
4. verify the plan artifact and execution workflow diff;
5. explicitly create and review the external authorization JSON and digest;
6. manually dispatch the execution workflow once; and
7. do not inspect or use partial outcomes for retuning.

## Post-execution status (WP-GATE-0.8)

The sequence above was subsequently authorized and executed in GitHub Actions
run `30631675731` at execution commit
`814653694f5eb41f9faed1417ae865953886308c`. All 144 cells and consolidation
completed. The selected scoped fallback is `gate_disabled`; verification and
protected holdout remain closed. Provenance, the complete retained artifact,
result limits, and the next boundary are recorded in
`E0_OVERRIDE_GATE_CALIBRATION_RESULT_v1.md`.

The earlier `calibration_executed=false` block describes the state when
WP-GATE-0.7 itself was committed. It must not be read as the current project
state.

WP-GATE-0.9 later established on development seed 0 that the execution timeout
also covers synchronous paired branch instrumentation. The resulting v1
`algorithm_timeout` labels are therefore mechanically valid under the frozen
runner but scientifically confounded. No rerun may merely increase those
timeouts; the next versioned design must separate parent timing from branch
evidence as specified in `E0_OVERRIDE_GATE_DEVELOPMENT_PILOT_v1.md`.
