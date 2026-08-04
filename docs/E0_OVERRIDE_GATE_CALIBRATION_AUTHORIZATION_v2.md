# E0 Override-Gate Calibration v2 — Authorization Boundary

**Work package:** WP-GATE-0.14

**Date:** 2026-08-04

**Status:** external calibration-only authorization schema and validator
implemented; no operational authorization record; execution not ready

## Outcome

WP-GATE-0.14 implements the fail-closed authorization boundary without making
the v2 experiment executable. The repository contains a review template, not
an authorization. It still contains no production fresh-split builder and no
outcome workflow.

The validator binds an externally supplied record simultaneously to:

- the immutable v2 instance ID and canonical digest;
- the exact protocol-file SHA-256 and frozen source commit;
- one full 40-character execution commit;
- one complete execution-manifest file and its byte-level SHA-256;
- one exact outcome-workflow file and its byte-level SHA-256;
- the reviewed WP-GATE-0.13 no-outcome evidence digest;
- calibration-only Stage-A and Stage-B execution;
- latest-attempt-only, no-fallback retry semantics; and
- an external authorizer, ISO date, reason, and exact confirmation phrase.

Unknown or missing fields fail. Verification, protected holdout, prior holdout
access, post-authorization retuning, candidate removal, and fallback to an
earlier attempt must all remain explicitly false.

## Required execution manifest

Authorization cannot validate against a commit hash alone. A future execution
commit must supply a JSON manifest bound to the exact workflow file. The
manifest must assert the frozen 144 Stage-B and 132 Stage-A calibration cells,
seeds 5000–5019, stage separation, no branch time charged to parent timing,
complete implementation and tests, latest-attempt-only consolidation, and
continued closure of verification and protected holdout.

The validator hashes both manifest and workflow from disk. Changing either
after external authorization invalidates the record.

## Two-channel confirmation

The authorization record must contain
`AUTHORIZE_E0_OVERRIDE_GATE_V2_CALIBRATION_ONLY`, and the validating command
must receive the same phrase independently. This prevents possession of a JSON
file alone from becoming execution permission.

## Why there is no frozen execution commit yet

Commit `d279f587bb8ad2d4e8a3235a472c4ccb4b802781` is the reviewed
preauthorization baseline for the development-worker evidence. It is not an
authorizable execution commit: production fresh-split runners and the outcome
workflow do not yet exist.

Freezing that commit now would be false assurance, because adding the missing
execution layer would necessarily change the code. The execution commit may be
frozen only after the complete calibration-only layer and workflow exist and
pass no-outcome review. The external authorization must be created afterward,
outside that execution commit.

## Dry-run result

The WP-GATE-0.14 dry run records:

- `authorization_validator_implemented=true`;
- `operational_authorization_record_present=false`;
- `execution_manifest_present=false`;
- `outcome_workflow_present=false`;
- `authorization_request_ready=false`;
- `fresh_split_builders_exposed=false`;
- `outcome_commands_exposed=false`;
- zero instantiated domains and zero observed outcomes; and
- `protected_holdout_accessed=false`, `not_gate_result=true`.

## Remaining boundary

The next work package should implement the complete calibration-only
production layer and a manual workflow, then generate the execution manifest
from that exact commit. Its no-outcome review must precede both the execution
commit freeze and any external authorization act. Verification and protected
holdout remain separate later authorizations.

## WP-GATE-0.15 follow-up

The complete calibration-only production layer and manual authorization-gated
workflow are now implemented but have not been executed. The WP-GATE-0.15
commit may become the candidate execution commit only after review; an external
execution manifest and authorization still do not exist. See
`E0_OVERRIDE_GATE_CALIBRATION_EXECUTION_v2.md`.

## Evidence

- implementation:
  `e0_controller/override_gate_calibration_v2_authorization.py`
- tests:
  `e0_controller/test_override_gate_calibration_v2_authorization.py`
- review template:
  `artifacts/override_gate/development/wp_gate_0_14/authorization-review-template.json`
- review-template SHA-256:
  `53d2dbe6d81fce996e730ec3629e10ae0470e722ca38d05d5bccbe6fd4392939`
- dry run:
  `artifacts/override_gate/development/wp_gate_0_14/dry-run.json`
- dry-run SHA-256:
  `b5fba193b814bdd4382150525945625e57585f4bf961bac528daead64f8c397f`
- protocol-file SHA-256:
  `8cf978f6df7390e11297a4b00715dd2ce3c75ca4a542299dc53e5c1a917fe76d`
