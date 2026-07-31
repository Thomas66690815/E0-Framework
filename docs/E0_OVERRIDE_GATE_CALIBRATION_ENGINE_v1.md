# E₀ Override-Gate Calibration Domain and Branch Engine v1

**Work package:** WP-GATE-0.5

**Status:** calibration-only engine implemented; matrix execution unavailable

**Date:** 2026-07-31

## Outcome

WP-GATE-0.5 implements the two semantic components required before a bounded
calibration runner can exist:

1. fresh domain construction for calibration seeds 2000–2019; and
2. deterministic, non-mutating greedy/lookahead branches at every
   common-guard-eligible disagreement.

It does not expose a CLI, task loop, result writer, verification builder, or
protected-holdout builder. No preregistered calibration episode was executed.

## Seed namespace

The four G1-v1 generator algorithms now accept an explicit internal seed
namespace. Their public default remains `g1_v1_development`, which still
accepts only seeds 0–9 and rejects the unread G1-v1 holdout 1000–1029.

The only additional namespace is `override_gate_calibration`. It accepts
exactly 2000–2019 from the sealed instance. Seeds from exploration,
verification, protected holdout, G1-v1 holdout, or any undeclared namespace
fail before generation.

The namespace changes access control only. Generator algorithms, random-seed
inputs, topology payloads, outcome seed formula, policy seed formula, and
domain invariants remain unchanged. Tests verify equal topology when the same
seed is admitted through both validators under a controlled test patch.

Calibration domains have `gate-cal-...` run IDs. Calling the legacy
development `to_record()` on one raises an error; the calibration-specific
record identifies:

- protocol and frozen instance;
- `split=calibration`;
- `holdout_accessed=false`;
- `not_gate_result=true`;
- exact-N and invariant results;
- topology hash; and
- `outcomes_observed=0`.

## Frozen policy adapter

`CalibrationEFullAdapter` always uses `E_FULL_GEOMETRY`. It accepts only an
exact serialized match to one of the 12 frozen candidates:

- `gate_disabled`; or
- the 11 fixed support margins from `margin_000` through `margin_085`.

Changing a threshold, guard, scope, or provenance creates a mismatch and is
rejected. The adapter changes only the override decision. Scores,
probabilities, path family, greedy action, and lookahead-preferred action are
computed by the existing E_FULL_GEOMETRY implementation.

Path-cap hits remain fail-closed and terminate with zero utility. The common
path-imbalance limit and truncation behavior come from the frozen policy.

## Complete decision snapshot

Before each parent decision, the engine snapshots every mutable component that
can influence subsequent decisions:

- current state, path, visits, interactions, costs, and failures;
- keyed outcome attempt counters;
- adapter RNG state and episode/observation counters;
- recent-state revisit memory;
- observed edges;
- complete historization traces and update times;
- confirmation and surprise traces;
- surprise-dampening and inter-visit state; and
- current structural-geometry field costs.

The policy object is immutable and shared by reference; all mutable adapter,
executor, and episode state is deeply copied. The canonical snapshot produces
a SHA-256 `state_hash`.

## Paired branch semantics

At every disagreement satisfying the common non-margin guards:

1. clone the same predecision adapter, executor, and episode state twice;
2. apply the greedy action in one branch;
3. apply the lookahead-preferred action in the other;
4. update historization with the respective first transition;
5. continue both branches with the disabled-gate E_FULL_GEOMETRY control;
6. use identical remaining interaction budgets and cloned keyed outcome
   counters; and
7. compute full-episode `success_adjusted_efficiency`.

The branch RNG identifier is `500000 + generator_seed`. Environment outcomes
retain the counter-keyed G1 semantics, so matching future edge attempts see
the same potential outcome even when trajectories diverge.

Diagnostic branches never mutate the parent episode. This is regression-tested
by comparing an instrumented parent to the ordinary uninstrumented episode:
the complete summary and decision-record sequence are identical.

## Test boundary

Calibration seeds are instantiated only for topology, exact-N, determinism,
namespace, and invariant tests. No executor is called for them.

Branch execution tests use a four-node synthetic development fixture that is
not part of any calibration, verification, or holdout split. It contains a
deliberate local/global disagreement and verifies:

- disabled versus zero-margin gate isolation;
- paired evidence and deterministic state hashes;
- common predecision state and equal budgets;
- deterministic replay;
- parent non-mutation; and
- fail-closed path-cap behavior.

These are engineering tests, not calibration results.

## Remaining boundary

WP-GATE-0.6 must add:

- a fresh-process calibration-only task worker;
- hard episode and replicate timeouts;
- atomic paired-branch and closed-loop shards;
- resume validation tied to task and execution-commit hashes;
- complete calibration consolidation;
- the frozen clustered bootstrap, multiplicity, eligibility, and selection
  report; and
- a planning-only GitHub workflow until explicit calibration authorization.

Verification and protected holdout remain out of scope until a selected policy
and the required predecessor artifacts actually exist.
