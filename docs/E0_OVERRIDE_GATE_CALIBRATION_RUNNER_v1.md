# E₀ Override-Gate Calibration Execution Scaffold v1

**Work package:** WP-GATE-0.4

**Status:** domain-free preflight implemented; outcome execution unavailable

**Date:** 2026-07-31

## Outcome

WP-GATE-0.4 turns the frozen calibration instance into a deterministic
execution plan without constructing a domain or observing an outcome.

The scaffold provides:

- stable task and shard identities;
- exact calibration, verification, and protected-holdout task plans;
- deterministic GitHub matrix partitioning;
- explicit pairing with the disabled-gate control;
- protected-split authorization checks;
- record contracts for paired branches, closed-loop replicates, and selection;
- a sealed dry-run manifest; and
- a CLI exposing only `dry-run` and `matrix`.

There is intentionally no `run`, `run-batch`, or `consolidate` command.

## Planned execution units

| Split | Policy treatment | Tasks | Disabled control |
|---|---|---:|---|
| Calibration | All 11 fixed margins plus `gate_disabled` | 2,880 | One shared disabled task per family/scale/seed |
| Verification | Frozen selected policy placeholder | 360 | Co-executed in the same replicate task |
| Protected holdout | Frozen selected policy placeholder | 360 | Co-executed in the same replicate task |

The calibration matrix uses 240 balanced, strided batches of 12 tasks. Matrix
entries include the first and last run IDs plus a task-list SHA-256.

The co-executed control in verification and holdout is necessary because those
splits must estimate the selected policy's paired effect while retaining the
preregistered count of 360 selected-policy replicate tasks.

## Lifecycle protection

Planning may display the placeholder `__selected_policy__`; it does not grant
access. Non-planning task construction requires:

- a full 40-character execution commit;
- for verification, a frozen calibration selection artifact;
- for protected holdout, a passing verification artifact;
- a matching instance and selected policy;
- a 64-character predecessor-artifact SHA-256;
- `retuning_after_artifact=false`; and
- for holdout, `protected_holdout_accessed=false`.

Historical exploration is never executable. Calibration always includes the
complete frozen candidate set. Protected splits cannot select or retune a
policy.

These guards authorize future task construction only. WP-GATE-0.4 still has no
function capable of constructing or running a domain.

## Artifact boundary

The scaffold freezes required fields for:

1. paired decision branches, including complete identity, decision context,
   both utilities, `delta_utility`, and `parent_run_mutated=false`;
2. closed-loop replicate records, including treatment and disabled-control
   identity, primary effect, activation and harm counts, path caps,
   infrastructure status, and leakage flags; and
3. the calibration-only selection record, including every candidate report,
   statistics, selection/fallback, and artifact hashes.

Every future record must match the frozen instance digest and source commit,
carry a full execution commit, and maintain `not_gate_result=true`.
`holdout_accessed` must be false for calibration and verification and true only
for a protected-holdout record.

## Verified dry run

The domain-free command is:

```text
python -m e0_controller.override_gate_calibration_runner dry-run
```

The verified unfrozen-commit preflight produced:

```text
instance_sha256 = 0ec61ef75d1a80966518a050351b1e5933e9ef0221ab9be4352815722072d597
dry_run_sha256  = e7d5604d3e7aaf6f7e9a8879e79e9e822cbd4af5a9ad0c2221268fcb465b619d
calibration tasks       = 2880
verification tasks      = 360
protected-holdout tasks = 360
matrix batches          = 240
domains_instantiated    = 0
outcomes_observed       = 0
```

The dry-run hash changes when the execution commit or any planned task changes.
The final implementation review must supply the actual execution commit and
rerun the dry plan before outcome production.

## Remaining boundary

The following are deliberately not implemented:

- calibration-specific domain construction for seeds 2000–2019;
- deterministic complete-state snapshot and branch replay;
- the policy-parameterized `E_FULL_GEOMETRY` closed loop;
- hard process timeout and atomic result shards;
- statistical selection and verification reports;
- outcome-producing GitHub Actions jobs; and
- any verification or protected-holdout access.

Those components form the next reviewed work package. They must not weaken or
reuse the G1-v1 development-only seed validator, and they must preserve the
task, control, artifact, and lifecycle contracts frozen here.
