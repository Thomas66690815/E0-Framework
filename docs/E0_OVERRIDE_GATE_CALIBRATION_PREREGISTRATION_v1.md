# E₀ Override-Gate Calibration Preregistration v1

**Work package:** WP-GATE-0.3

**Status:** frozen, not executed

**Date:** 2026-07-31

**Machine-readable authority:** `E0_OVERRIDE_GATE_CALIBRATION_INSTANCE_v1.json`

## Decision

This work package freezes one executable scientific question:

> Within the four declared G1 domain families, at horizon 3, does a fixed
> support-margin gate improve `E_FULL_GEOMETRY` decisions over the same scorer
> with overrides disabled, within the stated harm budget?

It does not choose a threshold, run a domain, read a verification or holdout
result, or change a framework default. The result will not be portable to
other scorers, horizons, controllers, or domain populations.

## Why the control is the disabled gate

The scorer, path family, historization, interaction budget, and random outcome
schedule are identical in treatment and control. Only the permission to
replace the greedy action changes. This avoids attributing differences from
another scorer or another learning policy to the gate.

The candidates are `disabled` and fixed margins from `0.00` through `0.40` in
steps of `0.05`, plus `0.50` and the historical `0.85`. The broad grid includes
the reachable margin range observed during exploration and the historical
values without treating either as truth.

## Frozen population and splits

The population consists of:

- `wall_grid`, `trap_grid_v2`, `decoy_dag`, and
  `nonstationary_parallel`;
- scales 100, 500, and 1000; and
- the G1-v1 generator semantics at source commit
  `46313f60a1bf0ed8590ec1e05d8a71d31200481a`.

The new runner must copy those semantics into a calibration-specific seed
namespace. It must not relax the G1-v1 development-only validator.
Its execution commit will be recorded and frozen after runner review and before
calibration starts. That commit may implement only the listed prerequisites;
any change to the frozen scorer, generator, policy, utility, statistics, or
split semantics requires a new instance version.

| Split | Seeds | Role |
|---|---:|---|
| Historical exploration | 0–9 | Candidate motivation only; no execution |
| Calibration | 2000–2019 | Selection |
| Verification | 3000–3029 | One-time confirmation |
| Protected holdout | 4000–4029 | One-time scoped result after verification |

All new splits are mutually disjoint and disjoint from the unread G1-v1
holdout 1000–1029. Publishing the seed manifest does not instantiate or inspect
any generated domain.

## Utility and causal branch evidence

The primary closed-loop utility is mean `success_adjusted_efficiency` over 20
evaluation episodes after 10 adaptation episodes. Each candidate is paired
with the disabled gate by family, scale, and generator seed. Family-scale
cells receive equal weight.

At every otherwise eligible disagreement on each candidate's own closed-loop
trajectory, a complete state snapshot branches once into the greedy and
lookahead actions. The diagnostic branches do not mutate the parent run. Both
branches then use the disabled gate, common random numbers, and the same
remaining interaction budget until terminal state or budget exhaustion.
Branch utility uses the same `success_adjusted_efficiency` definition. A
candidate's harm rate includes only disagreements whose margin meets that
candidate's threshold and which it would therefore override.

A branch effect below `-0.01` is harmful; an effect at or below `-0.10` is
severely harmful. Individual decisions are not treated as independent
statistical units.

## Eligibility and risk budget

A non-disabled candidate is eligible only if all frozen conditions pass:

- at least 200 override decisions;
- overrides in at least 24 replicates;
- at least 1% of eligible disagreements overridden;
- harmful-override upper confidence bound at most 10%;
- severe-harm upper confidence bound at most 2%;
- each domain family's primary-effect lower confidence bound at least `-0.02`;
- pooled primary-effect lower confidence bound strictly above zero;
- zero path-cap rate; and
- no infrastructure-invalid cell.

Intervals use 20,000 paired, family-scale-stratified replicate-cluster
bootstrap resamples. Holm-Bonferroni controls family-wise alpha 0.05 over all
candidate eligibility tests within a split.

Among eligible policies within `0.005` utility units of the best point
estimate, the largest support margin wins. This is the deterministic
safety-favoring tie-breaker. If no candidate qualifies, the result is
`disabled`; this is a valid negative outcome.

## Verification boundary

Calibration selects at most one policy. Its complete record and artifact hash
must be frozen before verification is opened. Verification is single-use and
uses the same eligibility and risk rules. Failure selects `disabled` and keeps
the protected holdout closed. Passing permits one protected-holdout execution.
Neither verification nor holdout may feed back into tuning.

## What is and is not established now

This preregistration establishes that the future selection rule cannot be
silently chosen after seeing outcomes. It does not establish:

- that any margin value is useful;
- that the candidate grid contains an eligible value;
- that support margin is a calibrated probability;
- that phase is causally useful; or
- that a new default should replace any legacy policy.

Execution requires a separate reviewed work package and the prerequisites in
the machine-readable instance. Until then, `calibration_executed=false`,
`protected_holdout_accessed=false`, and `not_gate_result=true`.
The validator also pins the canonical instance document by SHA-256, so an
in-place semantic edit is rejected instead of silently redefining v1.
