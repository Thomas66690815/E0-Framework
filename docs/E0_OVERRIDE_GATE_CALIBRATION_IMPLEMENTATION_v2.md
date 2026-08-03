# E0 Override-Gate Calibration v2 — No-Outcome Implementation

**Work package:** WP-GATE-0.12

**Date:** 2026-08-03

**Status:** sampler, planning, artifact contracts, and joint statistics
implemented; outcome runners and authorization not implemented; no fresh split
access

## Outcome

WP-GATE-0.12 translates the immutable v2 instance into executable pure
contracts without making a v2 experimental observation. The implementation
has four parts:

1. an outcome-blind deterministic Stage-A sampler;
2. separate Stage-A and Stage-B cell plans and artifact schemas;
3. joint fail-closed statistics exercised on complete synthetic matrices; and
4. a manual GitHub workflow that can emit planning evidence only.

There is deliberately no `run-cell` command, no fresh-split domain builder,
no external authorization generator, and no outcome workflow.

## Frozen Stage-A sampler

`override_gate_calibration_v2_sampler.py` accepts a complete active-candidate
Stage-B decision trace and validates its instance digest, split, seed, policy,
trace completeness, holdout flag, and decision identities.

Only executed overrides in evaluation episodes enter the sampling frame. Each
priority hashes exactly the fields frozen in the v2 instance plus the frozen
salt. Outcome and utility fields are ignored. Input record order does not
affect the result. The four lowest unique SHA-256 priorities are selected; a
smaller frame is retained completely, including a valid empty manifest for a
zero-override replicate.

The sample manifest is itself canonically hashed. Tests demonstrate that
outcome changes and input reordering do not change selection, while seed,
policy, digest, cap, order, or manifest mutation fails closed.

## Separate matrix plans

The planning unit is a stage × candidate × family × scale cell containing the
complete split seed manifest.

| Split | Stage B | Stage A | Replicates | Maximum pairs |
|---|---:|---:|---:|---:|
| Calibration | 144 cells | 132 cells | 2,880 B / 2,640 A | 10,560 |
| Verification | 12 cells | 12 cells | 360 / 360 | 1,440 |
| Protected holdout | 12 cells | 12 cells | 360 / 360 | 1,440 |

The disabled control is present only in Stage B. Verification and holdout plans
contain a visible selected-policy placeholder because no policy exists yet.
Stage A and Stage B form separate matrices; each remains below GitHub's
256-job limit.

The planner refuses every non-planning request unconditionally. It neither
imports nor calls a domain generator.

## Artifact contracts

Stage-B replicate records require parent-only wall time, the full disagreement
funnel, exact override counts, algorithm/path-cap status, and an explicit
`branch_time_charged_to_parent=false` assertion.

Stage-A replicate records require the sample-manifest digest, replay-trace
equality, no more than four paired decisions, unresolved counts, and
`instrumentation_time_is_parent_performance=false`.

Selection artifacts require both record populations. Common validators bind
the instance digest, source commit, full execution commit, split, holdout flag,
and `not_gate_result=true`.

## Joint statistics

`override_gate_calibration_v2_statistics.py` requires the exact complete
2,880-record Stage-B matrix and one Stage-A replicate record for every active
candidate unit, totalling 2,640.

It verifies:

- complete and unique candidate/family/scale/seed identities;
- `override <= eligible <= observed`;
- Stage-A sampling-frame equality with Stage-B executed overrides;
- the frozen four-sample cap and sorted unique priorities;
- valid completed/unresolved utility semantics; and
- zero infrastructure-invalid records before selection.

The estimator keeps Stage-A samples clustered inside seed replicates, applies
the frozen stratified bootstrap and Holm family, and then combines inferential
bounds with activation, severe-harm, unresolved, parent-timeout, and path-cap
sentinels. Stage A supplies safety eligibility; Stage B supplies benefit and
optimization.

Complete synthetic matrices demonstrate the intended decisions:

- equal eligible benefits select the highest, more conservative threshold;
- one severe Stage-A harm excludes only that candidate;
- one unresolved Stage-A pair cannot be imputed and excludes that candidate;
- one clean Stage-B parent timeout excludes that candidate; and
- incomplete matrices, funnel drift, sample-frame drift, and unapproved
  bootstrap counts are rejected.

Synthetic tests prove code-path semantics, not empirical safety or benefit.

## Planning-only GitHub workflow

`.github/workflows/override-gate-calibration-v2-plan.yml` is manual
`workflow_dispatch` only. It runs the no-outcome contracts, seals the dry-run,
and writes the two calibration matrix plans. It contains no `push`, `schedule`,
or outcome command.

The local dry-run records:

- `execution_prohibited=true`;
- `outcome_commands_exposed=false`;
- `domains_instantiated=0`;
- `outcomes_observed=0`;
- `calibration_executed=false`;
- `protected_holdout_accessed=false`; and
- `not_gate_result=true`.

Manifest SHA-256:
`b145f556f491d2e773a8e765d67e46554b021655ce5b271365f37381272e8114`.

## Remaining boundary

WP-GATE-0.12 does not yet make the calibration runnable. Missing components
are:

- the killable branch-free Stage-B parent worker;
- exact Stage-A replay and branch workers with independent deadlines;
- atomic immutable cell attempts and latest-attempt consolidation;
- external authorization record validation; and
- an authorization-gated outcome workflow.

The next work package should implement and development-test those workers and
distribution boundaries without instantiating seeds 5000–7029. Only after an
execution commit is frozen and independently reviewed may a separate
calibration authorization be created.

## WP-GATE-0.13 development worker follow-up

The first three missing components above are now implemented and exercised at
the development boundary: killable branch-free Stage B, exact Stage-A replay
with an independent process per selected pair, and immutable atomic attempts
with latest-attempt/no-fallback consolidation. The production split remains
unreachable and the authorization validator and outcome workflow remain
unimplemented. See `E0_OVERRIDE_GATE_CALIBRATION_WORKERS_v2.md`.

## Evidence

- `artifacts/override_gate/development/wp_gate_0_12/dry_run.json`
- `artifacts/override_gate/development/wp_gate_0_12/diagnosis.json`
- dry-run file SHA-256:
  `ee4a92013add1ade15ca4d7294274aff6322ff34731a59b4651d61550aba4a25`
