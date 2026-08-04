# E0 Override-Gate Calibration Preregistration v2

**Work package:** WP-GATE-0.11

**Date:** 2026-08-03

**Status:** immutable design frozen; execution not implemented or authorized;
no v2 fresh-split outcomes observed

## Purpose

The support-margin threshold is a free parameter. Its presence in legacy code
or frequent mention in documentation is not evidence that any particular
value is correct. Version 2 therefore treats every threshold as a candidate in
a declared, multiplicity-controlled experiment and retains `gate_disabled` as
the mandatory fallback.

The complete machine-readable contract is
`E0_OVERRIDE_GATE_CALIBRATION_INSTANCE_v2.json`. Its canonical SHA-256 is:

`0210d41d5e76c7c6fd8be8da79040a3e99f55906d62393007356d8aa86678692`

The instance binds to source commit
`91c1f63cbfda3891be851acafa3beee3b6f9baa7`, the completed development-only
Stage-A/Stage-B prototype. A later execution commit may only implement this
contract. It may not revise it after outcomes are visible.

## Evidence boundary

The design rests on three different kinds of prior evidence:

1. The v1 run is mechanically reproducible but its 2,116 timeout labels mix
   parent work and branch instrumentation. It cannot supply a clean threshold
   ranking.
2. WP-GATE-0.9 identifies the concrete scaling mechanism and demonstrates nine
   harmful zero-margin overrides in one development case.
3. WP-GATE-0.10 demonstrates that separate branch instrumentation does not
   mutate the replayed parent at N=100, N=500, and N=1000.

These observations justify a new experiment. They do not determine its
answer. WP-GATE-0.11 is a normative preregistration, not another empirical
result.

## Fresh population

No observed v1 calibration seed is reused. Earlier unopened v1 verification
and holdout ranges also remain reserved rather than being reassigned.

| Split | Generator seeds | Role |
|---|---|---|
| Development history | 0–9 | design motivation only |
| Calibration v2 | 5000–5019 | may select |
| Verification v2 | 6000–6029 | may confirm only |
| Protected holdout v2 | 7000–7029 | single use after verification pass |

The G1-v1 holdout 1000–1029, observed v1 calibration 2000–2019, and reserved
v1 ranges 3000–3029 and 4000–4029 are forbidden.

The domain population remains the four G1 families at N=100, N=500, and
N=1000, with 10 adaptation and 20 evaluation episodes per seed replicate.

## Candidate parameter grid

The fixed active thresholds are 0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30,
0.35, 0.40, 0.50, and 0.85. The disabled control is the twelfth candidate.

The grid is not an assertion that one value is true. It is a finite decision
set. Every active candidate must pass the same safety, activation,
non-inferiority, runtime, and multiplicity rules. If none passes,
`gate_disabled` is selected.

## Stage B — closed-loop parents

Stage B runs first and is complete before Stage-A sampling manifests are
materialized. Each candidate runs without paired branches and without branch
snapshot cloning. Parent wall time therefore contains only the closed-loop
adapter and the required decision-record accounting.

Stage B records the complete disagreement funnel:

- observed preferred/greedy disagreement;
- common-guard-eligible disagreement; and
- executed override.

It also records an ordered parent decision-trace digest. Parent episode and
replicate deadlines are 60 and 1,800 seconds. A genuine Stage-B algorithm
timeout is a valid zero-utility parent outcome and makes an active candidate
ineligible under the frozen zero-timeout risk limit.

## Stage A — sampled paired safety evidence

Stage A applies only to active candidates. Its sampling frame is the complete
set of executed overrides in the candidate's Stage-B evaluation trace.

For each candidate and generator-seed replicate, at most four overrides are
selected by ascending SHA-256 priority. The hash binds the instance, candidate,
domain, scale, seed, episode, interaction, state, greedy action, and preferred
action to the frozen salt
`E0-OVERRIDE-GATE-v2-stage-a-sample-v1`. Outcome fields are forbidden from the
priority input. There is no manual choice. If fewer than four overrides exist,
all are selected.

Stage A deterministically replays the parent, captures complete snapshots only
at selected decisions, and rejects a replay whose decision-trace digest differs
from Stage B as infrastructure-invalid. The greedy and preferred branches use
common random numbers, equal remaining interaction budgets, and the disabled
control after their first forced action.

Stage-A replay time is instrumentation time. Each branch has a 60-second
algorithm limit; each pair has a 150-second killable-process limit. A branch
timeout becomes `stage_a_unresolved`, never a Parent algorithm timeout. Any
unresolved selected branch makes that candidate ineligible.

## Safety and support

An active candidate must satisfy all of the following:

- at least 200 exact Stage-B overrides across at least 24 seed replicates;
- at least one percent of guard-eligible disagreements overridden;
- at least 400 sampled Stage-A overrides across at least 120 seed replicates;
- one-sided 95% upper confidence bound for sampled harmful-override rate no
  greater than 0.10 after multiplicity control;
- zero observed severe harms (`delta_utility <= -0.10`) in Stage A;
- zero unresolved Stage-A samples;
- zero Stage-B algorithm timeouts and path-cap outcomes;
- every domain-family primary-effect lower bound at least -0.02; and
- overall primary-effect lower bound strictly greater than zero.

The severe-harm rule is deliberately a zero-tolerance sample sentinel, not a
claim that the population severe-harm rate is zero.

## Inference and selection

The statistical unit is the generator-seed replicate. Resampling is stratified
by family and scale, with 20,000 frozen bootstrap resamples. Stage-A samples
remain clustered within their seed replicate. Replicates with no sampled
override do not enter the conditional harm denominator but do count against
the minimum activation support.

Holm-Bonferroni controls family-wise alpha 0.05 across every active candidate
and every inferential eligibility constraint within a split. Optional stopping,
negative-seed removal, post-authorization candidate removal, and fallback to
an earlier retry attempt are forbidden.

Among eligible candidates, selection maximizes the equal-cell-weight Stage-B
primary effect. Candidates within 0.005 of the best point estimate are tied;
the largest support-margin threshold wins as the simpler, more conservative
policy. Exact remaining ties sort by policy ID.

Stage A is a safety filter. Stage B supplies benefit and optimization. Neither
stage may select a policy alone.

## Missingness and retries

Algorithmic outcomes are never silently reclassified as infrastructure errors:

- Stage-B algorithm timeout: valid zero-utility parent result and active
  candidate ineligible.
- Stage-A branch timeout: valid unresolved safety result and candidate
  ineligible.
- Stage-A replay mismatch, runner crash, or upload failure:
  infrastructure-invalid; retain the artifact and rerun the entire cell with
  identical inputs.
- Incomplete latest attempt or missing candidate cell: selection forbidden.

Only the highest immutable attempt may enter consolidation. There is no
fallback to an earlier successful attempt.

## Planned maximum work

- Stage B calibration: 2,880 candidate-seed replicates.
- Stage A calibration: at most 10,560 paired decisions.
- Verification: 360 Stage-B replicates and at most 1,440 Stage-A pairs for the
  single frozen selected policy.
- Protected holdout: the same maximum, only after a verification pass and a
  separate authorization.

The four-pair cap was exercised in a development-only feasibility pilot. All
eight cases completed, all three replay invariance checks passed, and N=1000
Stage-A instrumentation took 8.59 seconds at a 40-interaction budget. This
does not validate full-budget cost or the not-yet-implemented hash sampler.

## Authorization boundary and next step

No authorization record exists. The v2 fresh-split builders, sampler, runners,
statistics, distribution, consolidation, and workflow are not implemented.

WP-GATE-0.12 may implement those components and perform only no-outcome dry
runs. It must then freeze an execution commit and produce an externally
reviewable authorization template. Calibration execution requires a later,
explicit authorization. Verification and protected holdout remain closed.

## WP-GATE-0.12 implementation status

The deterministic sampler, domain-free cell plans, artifact contracts, and
joint Stage-A/Stage-B statistics are implemented and tested without fresh
domains. A manual GitHub workflow can produce planning evidence only. It
exposes no outcome command.

The parent and branch workers, immutable attempt consolidation, authorization
validator, and outcome workflow remain unimplemented. Therefore no execution
commit or authorization can yet be frozen. See
`E0_OVERRIDE_GATE_CALIBRATION_IMPLEMENTATION_v2.md`.

## WP-GATE-0.13 and WP-GATE-0.14 implementation status

Development-only killable workers, exact replay, immutable attempts, and
latest-attempt/no-fallback consolidation are implemented. The external
calibration-only authorization schema and validator are also implemented, but
the committed template is deliberately non-operational.

The production fresh-split runner, execution manifest, and outcome workflow
remain absent. Consequently no execution commit is frozen, no external
authorization record exists, and calibration remains prohibited. See
`E0_OVERRIDE_GATE_CALIBRATION_WORKERS_v2.md` and
`E0_OVERRIDE_GATE_CALIBRATION_AUTHORIZATION_v2.md`.

## WP-GATE-0.15 implementation status

The complete calibration-only execution and distribution layer is implemented
behind the external authorization boundary. It contains the separate 144-cell
Stage-B and 132-cell Stage-A workflow, frozen deadlines, exact sampled replay,
immutable attempts, latest-attempt/no-fallback consolidation, and joint
selection.

No execution commit has yet been declared externally, no execution manifest or
authorization record exists, and the workflow has not been dispatched. No
fresh-split outcome was observed. See
`E0_OVERRIDE_GATE_CALIBRATION_EXECUTION_v2.md`.

## Evidence

- `docs/E0_OVERRIDE_GATE_CALIBRATION_PROTOCOL_v2.json`
- `docs/E0_OVERRIDE_GATE_CALIBRATION_INSTANCE_v2.json`
- `artifacts/override_gate/development/wp_gate_0_11/sampling_cap4_pilot.json`
- `artifacts/override_gate/development/wp_gate_0_11/diagnosis.json`
- feasibility pilot SHA-256:
  `dc46c47f59ca6e7907870c5a4895704aa739608bff8fc42d4a42849adb9435fb`
