# E0 Override-Gate Calibration Pipeline v1

**Work package:** WP-GATE-0.6
**Date:** 2026-07-31
**Status:** historical pipeline boundary; calibration later authorized and
completed — see `E0_OVERRIDE_GATE_CALIBRATION_RESULT_v1.md`

## Purpose

WP-GATE-0.6 completes the calibration-side implementation needed to evaluate
the frozen `E0-OVERRIDE-GATE-CAL-INSTANCE-v1` without opening either protected
split. It adds:

- a calibration-only worker in a fresh process;
- hard replicate limits and, on the frozen Ubuntu runner, hard episode limits;
- atomic per-task shards and strict resume validation;
- infrastructure-failure retention and whole-cell retries;
- complete calibration consolidation;
- the frozen clustered bootstrap, multiplicity correction, eligibility checks,
  safety tie-breaker, and disabled fallback; and
- a manually dispatched GitHub workflow that performs planning and
  no-outcome contract tests only.

This work package does not authorize or execute the 2,880 calibration tasks.
It exposes no outcome-producing CLI or GitHub job.

## Execution boundary

Outcome execution requires a separately supplied authorization record bound to
all of the following:

- the frozen instance ID and canonical instance SHA-256;
- one full 40-character execution commit;
- `authorized_split=calibration`;
- explicit calibration authorization;
- explicit denial of verification and protected-holdout execution;
- `retuning_after_authorization=false`; and
- a non-empty authorizer and authorization date.

No such record is committed by WP-GATE-0.6. A Python caller cannot substitute
a boolean flag for this record. The existing planning CLI continues to expose
only `dry-run` and `matrix`; the new pipeline module has no CLI entry point.

## Bounded worker

Every task is reconstructed from its canonical identity before a domain can be
built. Only the calibration namespace, seeds 2000 through 2019, the frozen
candidate set, and a full execution commit are accepted.

The worker runs 10 adaptation and 20 evaluation episodes. On the frozen
`ubuntu-24.04` environment, `SIGALRM` supplies the per-episode hard deadline.
Every replicate is also isolated in a separately spawned, killable process
with the frozen replicate deadline. After each completed episode the child
sends a checkpoint to its supervising process. The replicate process is
therefore the portable hard boundary when a platform has no POSIX interval
timer, while already checkpointed episode evidence survives forced
termination.

Algorithmic limits are valid negative outcomes:

| Status | Primary utility | Evidence retained |
|---|---:|---|
| `algorithm_timeout` | 0 | Every completed episode before the deadline |
| `path_cap_hit` | 0 | Completed episodes and paired branches |
| `method_out_of_memory` | 0 | Every completed episode before the error |

Unexpected worker, transport, or host errors are infrastructure failures, not
algorithmic scores.

## Atomic shards and resume

One atomic JSON shard contains:

- the complete canonical task record;
- the closed-loop replicate record;
- every completed episode summary;
- every evaluation-stage paired branch record; and
- a canonical SHA-256 over the complete shard.

Resume accepts a shard only when its digest, instance, source commit, execution
commit, task identity, nested episode identity, branch identity, split flags,
episode prefix, and result status all validate. A corrupt, stale, leaking, or
incomplete completed shard is recomputed.

Execution subsets must contain complete candidate-family-scale cells: all 20
calibration seeds for one or more cells. If one seed has an infrastructure
failure, the failed artifact is kept under `failures/`, consolidation remains
blocked, and the next authorized attempt recomputes the entire 20-seed cell.
This implements the frozen no-selective-rerun rule.

## Consolidation and selection

Consolidation is fail-closed until all 2,880 canonical shards validate. It then
emits:

- `raw_runs.jsonl`;
- deterministic `paired_branches.jsonl.gz`;
- `selection_report.json`;
- `policy_record.json`;
- `environment.json`; and
- `manifest.json` with file and manifest hashes.

Selection requires the exact 12-policy by 4-family by 3-scale by 20-seed
matrix. Out-of-range or non-finite values, count contradictions,
infrastructure-invalid records, split leakage, duplicates, and missing records
are rejected. A path cap in either the parent trajectory or a diagnostic
branch makes the replicate a zero-scored `path_cap_hit`.

For each of the 11 non-disabled candidates, inference uses:

- effects paired by family, scale, and generator seed;
- equal weight for all 12 family-scale cells;
- 20,000 replicate-cluster bootstrap samples stratified by family and scale;
- the frozen calibration bootstrap seed;
- one-sided 95% percentile bounds;
- all activation, harm, severe-harm, family non-inferiority, pooled-positive,
  path-cap, and infrastructure conditions; and
- Holm-Bonferroni at family-wise alpha 0.05 across 77 directed constraints.

Eligible candidates within 0.005 utility units of the best point estimate are
ordered by the largest support margin, then by policy ID. If no candidate is
eligible, `gate_disabled` is selected as the valid negative result.

Within each family-scale stratum, every bootstrap replicate samples the 20
generator-seed replicates with replacement and preserves the stratum size.
Percentiles use linear interpolation at position `p * (B - 1)`. Harm
proportions are recomputed as the sum of replicate-level harm counts divided
by the sum of replicate-level overrides; a zero-override denominator maps to
1.0 and therefore cannot pass the risk budget.

For an observed estimate `t`, bootstrap draw `t*`, and frozen boundary `b`,
the one-sided raw bootstrap p-values are:

```text
lower-bound alternative t > b:  (1 + count(t* - t + b >= t)) / (B + 1)
upper-bound alternative t < b:  (1 + count(t* - t + b <= t)) / (B + 1)
```

The 77 raw p-values are sorted ascending with deterministic policy/constraint
tie-breaks. Holm adjusted values are the running maximum of
`(77 - rank + 1) * p`, capped at 1.0. A statistical constraint must pass both
its percentile-bound comparison and its Holm-adjusted test. Activation,
zero-path-cap, and zero-infrastructure checks are exact eligibility conditions,
not additional stochastic tests.

Tests may reduce the bootstrap count only with an explicit test-only marker.
Production consolidation always uses the frozen 20,000 samples.

## Planning-only GitHub workflow

`.github/workflows/override-gate-calibration-plan.yml` is manual and
read-only. It:

1. installs the frozen Python environment;
2. runs only no-outcome contract suites;
3. seals a dry-run manifest against the checked-out commit; and
4. uploads that planning manifest.

It imports no outcome runner, has no `run-batch` or `consolidate` command, and
does not instantiate verification or protected-holdout domains.

## Validation performed in this work package

The pipeline and statistical tests use fabricated episode summaries, synthetic
records, a four-node development fixture inherited from WP-GATE-0.5, or a
sleeping substitute process used solely to prove hard termination. They do not
call the calibration task worker with a preregistered task.

Consequently:

```text
calibration_executed         = false
calibration_outcomes_observed = false
verification_executed        = false
protected_holdout_accessed    = false
not_gate_result               = true
```

## Next boundary

Before the first calibration outcome:

1. review and freeze the WP-GATE-0.6 execution commit;
2. run the planning-only workflow at that exact commit;
3. create and review the separate calibration authorization record;
4. add an authorization-consuming, cell-aligned execution workflow in a new
   work package; and
5. do not inspect verification or protected-holdout data.

The calibration result, when eventually produced, may select a scoped margin
policy for one-time verification. It cannot by itself establish a universal E0
confidence threshold or justify changing legacy defaults.

## WP-GATE-0.7 extension

WP-GATE-0.7 implements the separate authorization-consuming distribution layer
described in `E0_OVERRIDE_GATE_CALIBRATION_EXECUTION_v1.md`. It uses 144
complete 20-seed cells, immutable per-attempt artifacts, a highest-attempt
no-fallback rule, and complete-matrix consolidation. Its GitHub workflow is
manual and cannot run without the exact external authorization JSON, digest,
execution commit, and confirmation phrase.

No operational authorization record was part of the WP-GATE-0.7 commit, so the
no-outcome statements above were true at that historical boundary.

## WP-GATE-0.8 post-run status

GitHub Actions run `30631675731` subsequently completed the authorized 144-cell
calibration and consolidation. The immutable result selected `gate_disabled`
with `no_eligible_candidate=true`; verification and protected holdout remain
closed. See `E0_OVERRIDE_GATE_CALIBRATION_RESULT_v1.md` and the retained bundle
under `artifacts/override_gate/E0-OVERRIDE-GATE-CAL-INSTANCE-v1/calibration/`.

Future shards use schema v2 to add the previously absent
`observed_disagreement_count` while retaining the v1 meanings of
`eligible_disagreement_count` and `override_count`. The executed v1 artifact
is not rewritten or reconsolidated under the new schema.

## WP-GATE-0.9 timeout diagnosis

A development-only parent-versus-paired pilot subsequently showed that the v1
episode deadline includes synchronous diagnostic branch work. At budget 40,
paired collection expanded 21 parent geometry decisions to 518 at `N=100` and
40 to 1,356 at `N=500`; at `N=1000`, parent-only completed while paired
collection hit its hard timeout. See
`E0_OVERRIDE_GATE_DEVELOPMENT_PILOT_v1.md`.

Accordingly, v1 `algorithm_timeout` is a frozen record label but not a clean
scientific attribution to parent algorithm performance. A future version must
time closed-loop parents separately from paired branch evidence. Raising the
existing timeout without that separation is forbidden.

## WP-GATE-0.10 development architecture

The required separation has now passed a bounded development pilot. Stage A
sampled one paired decision in a dedicated process at N=100, N=500, and
N=1000. Stage B ran five branch-free closed-loop parents. All cases completed
within their 30-second process limits, and the disabled-control parent summary
plus decision-trace digest matched across stages at every scale.

These changes are development diagnostics only; they do not alter the frozen
v1 execution defaults or authorize a v2 calibration. Before another GitHub
matrix, a new immutable instance must freeze Stage-A sampling and inference,
Stage-B selection and timing, cross-stage decision rules, and a fresh
authorization digest. See
`E0_OVERRIDE_GATE_V2_DEVELOPMENT_ARCHITECTURE_v1.md`.

## WP-GATE-0.11 frozen successor contract

The successor is now preregistered as
`E0-OVERRIDE-GATE-CAL-INSTANCE-v2`. It reserves new calibration,
verification, and protected-holdout seed ranges; earlier observed or reserved
ranges are not repurposed. Stage B is branch-free and snapshot-free. Stage A
samples at most four executed overrides per active candidate and seed replicate
using a frozen outcome-blind hash priority.

The v2 instance also freezes separate parent/branch timeout namespaces,
fail-closed unresolved evidence, activation minima, multiplicity, missingness,
tie-breaking, and the disabled fallback. Its implementation and authorization
remain future work. See
`E0_OVERRIDE_GATE_CALIBRATION_PREREGISTRATION_v2.md`.

## WP-GATE-0.12 no-outcome implementation

The v2 hash sampler, separate Stage-A/Stage-B cell plans, record validators,
joint fail-closed statistics, and manual planning workflow are now
implemented. A sealed dry-run produces 144 Stage-B and 132 Stage-A calibration
cell identities while recording zero domains and zero outcomes.

This remains pre-execution infrastructure. There is no Stage-B outcome worker,
Stage-A replay/branch worker, authorization validator, consolidation path, or
outcome workflow. See `E0_OVERRIDE_GATE_CALIBRATION_IMPLEMENTATION_v2.md`.

## WP-GATE-0.13 development workers

Killable Stage-B and exact Stage-A replay workers now pass a development-only
pilot. Stage B collected a complete branch-free parent trace. Stage A replayed
the same trace digest and evaluated only the four frozen hash-selected
decisions, one killable process per pair. Immutable atomic attempt files and
newest-attempt/no-fallback consolidation also passed their failure tests.

This does not expose a fresh-split builder or outcome workflow. Authorization
validation remains the next boundary. See
`E0_OVERRIDE_GATE_CALIBRATION_WORKERS_v2.md`.

## WP-GATE-0.14 authorization boundary

The v2 external authorization schema, inert review template, execution
manifest contract, and fail-closed validator are implemented. A valid record
must bind the exact instance, protocol, execution commit, manifest, workflow,
and reviewed development evidence while keeping verification and protected
holdout closed.

No operational authorization record, execution manifest, or outcome workflow
is present. Therefore calibration remains technically and procedurally
blocked. See `E0_OVERRIDE_GATE_CALIBRATION_AUTHORIZATION_v2.md`.
