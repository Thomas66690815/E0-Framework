# E0 Override-Gate Calibration v2 — Locked Execution Layer

**Work package:** WP-GATE-0.15

**Date:** 2026-08-04

**Status:** complete calibration-only execution layer and manual workflow
implemented; not authorized, not dispatched, no fresh-split outcomes observed

## Outcome

WP-GATE-0.15 implements the production execution path frozen by the v2
instance while leaving it technically locked. Every command capable of
constructing seed 5000–5019 first validates the external authorization,
canonical authorization digest, full execution commit, byte-exact execution
manifest, byte-exact workflow file, and independent confirmation phrase.

There is no verification or protected-holdout command.

## Stage B

Stage B contains 144 candidate × family × scale cells. Each cell contains all
20 calibration seeds and is retried only as a whole.

Each seed replicate runs 10 adaptation and 20 evaluation episodes, suppresses
paired branches and branch snapshots, enforces the frozen 60-second episode
and 1,800-second replicate boundaries, records the complete parent trace, and
computes parent-only timing and evaluation utility. Algorithm timeout, method
OOM, and path-cap results are retained as valid negatives. Method OOM remains
separately visible and also trips the zero-tolerance parent algorithm-failure
sentinel, so it cannot leave a candidate eligible.

## Stage A

Stage A contains 132 active-candidate × family × scale cells and cannot begin
until the complete latest-attempt Stage-B matrix has consolidated.

For every complete Stage-B replicate it builds the frozen outcome-blind
cap-four manifest, independently replays the branch-free parent, requires the
exact trace digest, and replays only the selected identities. Each branch has
60 seconds and each pair process 150 seconds. Unresolved branch timeouts are
never imputed. The GitHub command also has the frozen 3,600-second cell limit.

An incomplete Stage-B trace caused by a valid parent timeout emits a visible
empty Stage-A skip record. The joint validator accepts it only when the matching
Stage-B timeout exists; that candidate is already ineligible.

## Attempts and consolidation

Each cell writes one digest-bound immutable attempt through a flushed temporary
file and atomic hard-link publication. A complete attempt requires all 20 seed
identities, stage-correct records, exact Stage-B traces, zero infrastructure
failures, and the exact cell, authorization, manifest, and execution digests.

Consolidation chooses the greatest attempt number before parsing it. A corrupt,
partial, or invalid newest attempt fails; an older successful attempt is never
used. Final selection requires all 2,880 Stage-B and 2,640 Stage-A records and
applies the frozen joint statistical rule.

## Manual GitHub workflow

`.github/workflows/override-gate-calibration-v2-execute.yml` is
`workflow_dispatch` only. Its ordered flow is authorization and matrices → 144
Stage-B cells → Stage-B consolidation → 132 Stage-A cells → consolidation and
joint selection. It contains neither `push` nor `schedule`. Every mutating
command revalidates authorization, manifest, workflow, commit, and confirmation.

## No-outcome review

The local dry run records 144/2,880 Stage-B cells/replicates and 132/2,640
Stage-A cells/replicates, with the workflow present and commands exposed but
locked. It records no operational authorization, no execution manifest, no
frozen execution commit, zero domains, zero outcomes, and no calibration,
verification, holdout, or gate result.

No actual seed 5000–5019 domain was constructed in WP-GATE-0.15. Synthetic
records and development seed 0 are not empirical calibration evidence.

## WP-GATE-0.16 audit closeout

The externally supplied audit of WP-GATE-0.1 through WP-GATE-0.15 found no
critical defect in the execution or authorization boundary. Its three
documentation findings are closed by the recorded audit, new Evidence Ledger
claims, an explicit preregistration erratum, and the current bootstrap state.

WP-GATE-0.16 changes no production code, workflow, frozen instance, candidate,
criterion, seed range, authorization rule, or observed outcome. Its commit is
therefore the post-audit candidate to declare as the execution commit. That
declaration still does not authorize calibration.

## Next authorization act

After WP-GATE-0.16 is committed, its exact commit may be declared as the
candidate execution commit and the execution manifest generated from that
checkout. The manifest must be reviewed before the user creates a separate
external authorization and explicitly dispatches the workflow. Any subsequent
edit requires a new commit, manifest, workflow hash, and authorization digest.

## Evidence

- implementation: `e0_controller/override_gate_calibration_v2_execution.py`
- tests: `e0_controller/test_override_gate_calibration_v2_execution.py`
- workflow: `.github/workflows/override-gate-calibration-v2-execute.yml`
- workflow SHA-256:
  `1ad603d6555a43def84b59efc50f107577fdddb282dcbff500ba4e530e08b9bd`
- dry run: `artifacts/override_gate/development/wp_gate_0_15/dry-run.json`
- dry-run SHA-256:
  `4d5d89bcc5d47e0c01f845c6fa76d6a62d7ea4ab5c89dd6990918d818bccb40a`
- focused execution-layer validation: 92 tests passed
- adjacent G1/engine/worker/sampler validation: 81 tests plus 20 subtests passed
- audit closeout: `docs/E0_OVERRIDE_GATE_AUDIT_WP_GATE_0_15.md`
