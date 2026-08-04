# E0 Override-Gate Audit through WP-GATE-0.15

**Audit supplied:** 2026-08-04

**Recorded by:** WP-GATE-0.16

**Audited scope:** the 16 commits from WP-GATE-0.1 through WP-GATE-0.15,
dated 2026-07-31 through 2026-08-04, covering Override-Gate calibration v1
and v2

**Provenance:** externally supplied repository review. The reviewer identity
and execution transcript were not supplied, so this record preserves the
reported checks without upgrading them to an independent replication.

## Overall assessment

The audit found the series to be in very good condition. Commit messages
matched their diffs, the freeze and authorization boundaries held, and the
reported tests passed. It reported three documentation findings and no
critical defect.

## Checks reported as verified

- All 318 Override-Gate tests passed: 204 v1 tests and 114 v2 tests.
- Collection reproduced 7,166 tests in 181 test files at WP-GATE-0.15.
- For GitHub Actions run `30631675731`, the SHA-256 values of
  `selection_report.json`, `policy_record.json`, `environment.json`, and the
  retained 7.8 MB evidence ZIP matched the manifest and result report.
- The v1 totals were internally consistent: 2,116 algorithm timeout records
  plus 764 completed records equal all 2,880 shards; the timeout split
  960/960/196 also sums to 2,116.
- The scoped v1 result was reported without promotion: `gate_disabled`,
  73.47% algorithm timeouts, and no universal threshold claim.
- The v1 and v2 instance files remained unchanged after their respective
  freeze commits. The canonical v2 instance hash reproduced the value in the
  authorization template. Later protocol changes were status metadata.
- No operational v2 authorization artifact existed. The validator rejected
  placeholders and bound an authorization to the canonical record digest,
  workflow hash, execution manifest, exact commit, and confirmation phrase.
- `.env` was ignored and had never been committed.

These are audit assertions backed by the repository paths named below. The
local WP-GATE-0.16 closeout revalidates JSON syntax, test collection, and the
Override-Gate tests; it does not rerun calibration or access any holdout.

## Findings and disposition

### A-01 — Evidence Ledger stale after WP-GATE-0.7

**Severity:** medium

The ledger did not record the executed WP-GATE-0.8 result, the WP-GATE-0.9
and WP-GATE-0.10 diagnosis, or the v2 WP-GATE-0.11 through WP-GATE-0.15
design and implementation line.

**Disposition:** corrected in WP-GATE-0.16 with distinct claims for the v1
calibration result, the timing-confound diagnosis, and v2 execution readiness.
Each claim explicitly lists its covered work packages and limitations.

### A-02 — Unmarked post-freeze prose correction

**Severity:** low to medium

WP-GATE-0.12 changed the v2 preregistration wording from “every family-scale
primary-effect lower bound” to “every domain-family primary-effect lower
bound.” The latter agrees with the unchanged frozen instance field
`stage_b_family_primary_effect_lower_confidence_bound_min`, but the correction
was not labeled after the fact.

**Disposition:** the preregistration now contains a dated erratum recording
both wordings, both commits, the unchanged machine-readable authority, and
the absence of any criterion or outcome change.

### A-03 — `bootstrap.json` stale

**Severity:** low

The pending bootstrap edit stopped at C328 and omitted C329 through C331 and
the complete WP-GATE series.

**Disposition:** WP-GATE-0.16 preserves the pending C328 timing update while
bringing state, active context, Gate-G1 status, and recent history through the
audited WP-GATE-0.15 base commit.

## Evidence pointers

- `docs/E0_EVIDENCE_LEDGER_v1.json`
- `docs/E0_OVERRIDE_GATE_CALIBRATION_RESULT_v1.md`
- `docs/E0_OVERRIDE_GATE_DEVELOPMENT_PILOT_v1.md`
- `docs/E0_OVERRIDE_GATE_CALIBRATION_PREREGISTRATION_v2.md`
- `docs/E0_OVERRIDE_GATE_CALIBRATION_INSTANCE_v2.json`
- `docs/E0_OVERRIDE_GATE_CALIBRATION_EXECUTION_v2.md`
- `artifacts/override_gate/E0-OVERRIDE-GATE-CAL-INSTANCE-v1/calibration/run_30631675731/`

## Boundary

This audit does not authorize calibration, verification, or protected-holdout
execution. It does not turn the internal v1 result into external replication.
After this closeout is committed, that new commit may be proposed as the v2
execution commit; a complete execution manifest and a separate explicit
external authorization are still required before any fresh calibration domain
may be instantiated.
