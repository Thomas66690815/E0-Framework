# E0 Override-Gate v2 Development Architecture v1

**Work package:** WP-GATE-0.10

**Date:** 2026-08-03

**Status:** stage separation demonstrated on development seed 0; no experiment
instance, authorization, calibration, verification, holdout access, or gate result

## Decision

The v1 calibration must not be repeated with a larger timeout. Its episode
timer enclosed both the closed-loop parent and synchronous paired-branch
diagnostics. WP-GATE-0.10 implements and tests the required v2 measurement
boundary:

- **Stage A — paired evidence:** replay the disabled control and sample at most
  one guard-eligible disagreement per case. The two counterfactual branches run
  under a dedicated instrumentation timer and status.
- **Stage B — closed-loop parent:** execute the candidate with paired branches
  disabled. Only this branch-free execution produces parent wall time and
  closed-loop outcomes.

Each case runs in a separate killable process. Stage-A time is stored only as
`instrumentation_wall_time_ms`; Stage-B time is stored only as
`parent_wall_time_ms`. The two values cannot be substituted for one another.

The implementation is development-only. The v1 defaults remain unchanged,
and both branch suppression and branch caps reject calibration namespaces.

## Bounded pilot

The pilot used `wall_grid`, development seed 0, episode 0, an interaction
budget of 40, and a 30-second hard limit per process. Stage A sampled one
paired decision at each of N=100, N=500, and N=1000. Stage B ran the disabled
control at all three scales and `margin_000` plus `margin_040` at N=100.

All eight cases completed. There were zero prototype timeouts and zero worker
errors.

| Stage | N | Policy | Time | Decisions | Observed / eligible / overrides | Parent result |
|---|---:|---|---:|---:|---:|---|
| A | 100 | `gate_disabled` | 0.835 s instrumentation | 21 | 17 / 17 / 0 | goal in 21 |
| B | 100 | `gate_disabled` | 0.196 s parent | 21 | 17 / 17 / 0 | goal in 21 |
| B | 100 | `margin_000` | 0.401 s parent | 40 | 9 / 9 / 9 | budget exhausted |
| B | 100 | `margin_040` | 0.169 s parent | 21 | 17 / 17 / 0 | goal in 21 |
| A | 500 | `gate_disabled` | 1.032 s instrumentation | 40 | 29 / 29 / 0 | budget exhausted |
| B | 500 | `gate_disabled` | 0.251 s parent | 40 | 29 / 29 / 0 | budget exhausted |
| A | 1,000 | `gate_disabled` | 1.824 s instrumentation | 40 | 36 / 35 / 0 | budget exhausted |
| B | 1,000 | `gate_disabled` | 0.487 s parent | 40 | 36 / 35 / 0 | budget exhausted |

The Stage-A durations include branch instrumentation and are not performance
comparisons against Stage B. Process startup, cache state, and the sampled
branch also differ. Their purpose is only to demonstrate bounded feasibility.

## Parent invariance

For each scale, Stage A and the independent Stage-B disabled control used the
same domain, seed, episode, policy, and interaction budget. Two independent
checks passed at N=100, N=500, and N=1000:

1. the complete parent `EpisodeSummary` records were equal;
2. SHA-256 digests of the ordered parent decision traces were equal.

The trace digest covers state, greedy/preferred/selected actions, path-family
signature, path-cap state, confidence, path imbalance, override state, and
phase regime. It excludes branch data and wall time.

This is direct evidence that bounded Stage-A branch evaluation did not mutate
the replayed parent in these three development cases.

## What the pilot establishes

WP-GATE-0.10 establishes that:

- paired evidence can be bounded independently at all three target scales;
- parent outcome and timing can be collected without synchronous branches;
- the full disagreement funnel can be recorded in Stage B without executing
  counterfactual rollouts;
- the nine harmful `margin_000` overrides at N=100 reproduce in a clean
  branch-free parent run; and
- instrumentation did not change the disabled control trace in the tested
  replays.

It does **not** establish a threshold, a population effect, or a gate result.
Only one development seed was used, Stage A sampled only the first eligible
decision, and no inferential rule has yet been frozen.

## Required next work package

WP-GATE-0.11 should specify and review a new immutable v2 experiment instance
before execution. At minimum it must freeze:

1. deterministic Stage-A snapshot sampling across domains, scales, seeds, and
   episodes;
2. Stage-A branch budgets, censoring semantics, utility comparison, and
   inference rule;
3. Stage-B candidate population, parent-only timeout semantics, metrics, and
   eligibility rule;
4. the rule linking Stage-A safety evidence to Stage-B policy selection;
5. multiplicity, missingness, infrastructure retry, and fallback handling;
6. a fresh authorization digest and continued closure of verification and the
   protected holdout.

No GitHub full calibration should start until that contract is frozen and
explicitly authorized.

## WP-GATE-0.11 freeze

The v2 contract is now frozen in
`E0_OVERRIDE_GATE_CALIBRATION_INSTANCE_v2.json`. It uses new 5000/6000/7000
split ranges, branch-free Stage-B parents, and at most four deterministic
hash-priority Stage-A samples per active candidate and seed replicate. Stage-A
timeouts fail safety eligibility but cannot relabel the parent.

A development-only cap-four feasibility run completed all cases and preserved
all three parent invariance checks. This freezes a design; it does not
authorize execution or select a threshold. See
`E0_OVERRIDE_GATE_CALIBRATION_PREREGISTRATION_v2.md`.

## Evidence

- `artifacts/override_gate/development/wp_gate_0_10/pilot.json`
- `artifacts/override_gate/development/wp_gate_0_10/diagnosis.json`
- pilot SHA-256:
  `d31f8e5d8d37645cc3e2cddbf7a7d94280bf0a9b110696240d8390bcad2f52b3`
