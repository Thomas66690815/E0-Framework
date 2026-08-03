# E0 Override-Gate Calibration Result v1

**Work package:** WP-GATE-0.8

**Date:** 2026-08-03

**Run:** [GitHub Actions 30631675731](https://github.com/Thomas66690815/E0-Framework/actions/runs/30631675731)

**Status:** complete negative calibration result; verification and holdout closed

## Decision

The preregistered calibration selected `gate_disabled` because no active
candidate was eligible. This is the binding fail-closed policy for the frozen
instance `E0-OVERRIDE-GATE-CAL-INSTANCE-v1`. It is not a universal E0 gate
result and does not identify an optimal confidence threshold.

The run produced actual commit- and authorization-bound outcomes. This report
therefore supersedes document-frequency inference about the confidence gate,
but only within the declared calibration scope.

## Verified provenance

- source commit: `46313f60a1bf0ed8590ec1e05d8a71d31200481a`
- execution commit: `814653694f5eb41f9faed1417ae865953886308c`
- authorization SHA-256:
  `9f7f2b41e4f25b100783b819d00dd86d8673ba616e8aba70864ce48ef0c93a13`
- instance SHA-256:
  `0ec61ef75d1a80966518a050351b1e5933e9ef0221ab9be4352815722072d597`
- downloaded evidence ZIP SHA-256:
  `768cefc986e40d392e22de4dff48dba09659b168d0a635eda84e9a61ab6d0d6d`
- 146 successful jobs: one authorization gate, 144 complete matrix cells, and
  one consolidation job
- zero failed, cancelled, or timed-out GitHub jobs

The complete 7.8 MB Actions artifact, including all 2,880 shards, is retained
at
`artifacts/override_gate/E0-OVERRIDE-GATE-CAL-INSTANCE-v1/calibration/run_30631675731/override-gate-calibration-evidence-attempt-1.zip`.
The adjacent readable manifest, selection report, policy record, environment,
and `diagnosis.json` make the retained bundle independently inspectable after
the original GitHub artifact expires.

## Observed result

| Measure | Value |
|---|---:|
| task shards / closed-loop records | 2,880 / 2,880 |
| completed replicates | 764 |
| algorithm timeouts | 2,116 (73.47%) |
| paired branch records | 17,397 |
| executed overrides | 0 |
| infrastructure failures | 0 |
| path-cap hits | 0 |
| eligible active candidates | 0 |
| selected policy | `gate_disabled` |

All 960 `N=500` and all 960 `N=1000` replicates timed out. At `N=100`, 764
of 960 replicates completed. The family concentration was strongest in
`wall_grid`: 676 of 720 replicates timed out.

These are algorithmic negative outcomes under the frozen budget, not GitHub
infrastructure failures.

## Activation interpretation

The v1 output contains two of the three counts needed for an unambiguous gate
funnel:

1. **observed disagreement** — preferred and greedy actions differ before
   guards; not emitted by v1;
2. **eligible disagreement** — the disagreement passes the common
   non-confidence guards and receives paired branch evidence; emitted as
   `eligible_disagreement_count`;
3. **executed override** — the eligible disagreement additionally passes the
   candidate support-margin threshold; emitted as `override_count`.

Thus the 6,297 eligible disagreements reported for `margin_040` do not mean
that 6,297 records passed the `0.40` threshold. Their largest support margin
was `0.398949264404075`; zero executed overrides is internally consistent.
The same maximum applies to `margin_050` and `margin_085`.

The candidates from `0.00` through `0.35` retained no evaluation-stage
eligible disagreement records. Their 60 completions each came from the three
non-wall families at `N=100`; the remaining 180 replicates timed out. The
experiment therefore supplies a valid operational rejection, but not a clean
causal threshold-effect estimate.

Shard schema v2 now adds `observed_disagreement_count` and enforces:

```text
override_count <= eligible_disagreement_count <= observed_disagreement_count
```

This changes future evidence observability, not the frozen v1 result.

## Concrete wall-grid mechanism

One retained `wall_grid/N100/seed-2000` paired decision has support margin
`0.29437236663855526` and path imbalance `3.0`:

- greedy branch: reaches the goal in 21 interactions, utility `1.0`;
- lookahead branch: fails to reach the goal in 400 interactions, utility `0.0`,
  with `interaction_budget_exhausted`.

A threshold at or below this margin would admit the harmful branch unless a
deterministic safety rule prevents the cycle. This is the first mechanism to
isolate before another calibration run. It does not by itself authorize adding
a new tunable guard.

The existing general-controller revisit guard is not such a demonstrated
solution. It is conditional on a Self-Graph and blocks only an immediate target
already present in the recent-state window. The diagnostic branch's first
target is new; the later 400-step loop occurs even though the paired rollout
switches back to the disabled policy and retains the shared greedy revisit
penalty. The v1 calibration correctly froze `revisit_guard=none`. Changing this
contract would be a new behavior-changing hypothesis and therefore requires a
new versioned instance rather than a silent rerun.

## Scientific conclusion

Established:

- the distributed execution and evidence chain completed correctly;
- no active candidate passed the frozen activation, risk, effect, and
  multiplicity contract;
- `gate_disabled` is the required scoped fallback;
- verification and the protected holdout must remain closed.

Not established:

- that the confidence gate is universally useless;
- that disabling it is globally optimal;
- a portable confidence threshold;
- a causal treatment ranking independent of the structured timeout pattern.

## Next boundary

Do not dispatch another complete 2,880-task matrix yet. The next work package
must be a calibration-only pilot that:

1. emits all three disagreement-funnel counts;
2. reproduces the `wall_grid` cycle with a small development-only seed set;
3. prototypes, outside protected splits, whether any deterministic cycle
   invariant can block the harmful branch without introducing another
   calibrated free parameter; the currently existing optional revisit guard
   is not sufficient evidence;
4. demonstrates at least one expected executed override and correct paired
   attribution in a bounded synthetic or development fixture;
5. estimates `N=100`, `N=500`, and `N=1000` runtime before any new full
   authorization.

Only a successful pilot permits a new versioned instance, new authorization,
and a fresh full calibration. Verification and protected holdout remain
forbidden throughout that work.

## WP-GATE-0.9 development diagnosis

The required pilot is now complete on development seed 0. It isolated a
measurement confound: synchronous paired rollouts amplify geometry decisions
by 24.67× at `N=100` and 33.9× at `N=500`. At `N=1000`, the parent-only case
completed in 6.762 seconds while paired instrumentation exceeded the 30-second
hard limit.

The v1 timeout encloses parent execution and paired diagnostic work. Therefore
the 2,116 `algorithm_timeout` labels cannot all be interpreted as clean parent
algorithm failures. The formal frozen fallback remains `gate_disabled`, but
the experiment does not supply a clean causal threshold ranking.

The pilot also executed nine real `margin_000` overrides: the disabled parent
reached its goal in 21 interactions, whereas the active zero-margin parent
exhausted its 40-interaction budget. See
`E0_OVERRIDE_GATE_DEVELOPMENT_PILOT_v1.md` for the complete diagnosis.

A new full run is blocked until a versioned design separates paired branch
evidence from closed-loop parent timing. Increasing the old timeout is not an
adequate correction.
