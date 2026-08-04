# E₀ Gate G1 — Development Result v1 (WP-2.4)

**Work package:** WP-2.4 closure (C332)

**Date:** 2026-08-04

**Run:** [GitHub Actions 30526724307](https://github.com/Thomas66690815/E0-Framework/actions/runs/30526724307)

**Status:** complete development raw data retained; development diagnostics
reported; **not a Gate-G1 result**; holdout unopened

## Why this report exists

The corrected WP-2.4 development run completed on 2026-07-30 and produced the
consolidated `g1-development-evidence` artifact. C331 analyzed its G1-A
mechanism neutrality, but the artifact itself — including the generated
development report and the G1-B baseline diagnostic it contains — was never
retained in the repository. The artifact expires on 2026-08-13 (per-batch
shards on 2026-08-06). C332 retains the verified bundle and reports all three
preregistered development diagnostics, including the previously unreported
baseline comparison.

## Verified provenance

- source commit: `3990b5dbd4195b6d4f3dd21bd4a48b0bb0efaa12` (C330), not dirty
- protocol: `E0-G1-v1`, SHA-256
  `e1017c197346e2176a6ddefb5e9d6a24cf140b59d80c7b7615265a4d8a1e3bbd`
- consolidated artifact `g1-development-evidence` (5,169,427 bytes) downloaded
  2026-08-04; all five file SHA-256 values match the in-bundle
  `manifest.json`
- retained byte-identical under
  `artifacts/g1/E0-G1-v1/development/run_30526724307/`
- the workflow-generated development report is committed unchanged as
  `docs/research/E0_DECISION_BENCHMARK_v1.md`
- completeness: 1,560/1,560 replicates, 31,200 evaluation episodes,
  0 infrastructure failures, 3 valid negative replicates (all
  `E_FULL_GEOMETRY` algorithm timeouts)
- `holdout_accessed=false`, `holdout_execution_started=false`,
  `not_g1_result=true` throughout

## Development diagnostic 1 — G1-A (full geometry vs. selected control)

`A_HIST` was selected as the frozen simpler control (highest pooled mean
success-adjusted efficiency; fastest wall-time among the five tied E₀
variants). `E_FULL_GEOMETRY` minus `A_HIST` is 0.0 in every family and
overall, with a degenerate [0.0, 0.0] bootstrap interval. The phase
attribution check (`D_U1_PHASE` vs. `C_THETA_ZERO`) is also 0.0 everywhere.
C331 diagnosed why: the lookahead is causally inactive at the action boundary
(confidence gate never permits an override; all 4,482,410 evaluation decisions
per method stay in the gradient phase regime). See
`E0_G1_MECHANISM_DIAGNOSIS_v1.md`.

## Development diagnostic 2 — G1-B (A_HIST vs. competitive baseline median)

Comparator: per-instance median of fairly trained `Q_LEARNING`, `UCB1_EDGE`,
and `RANDOM_RESTART_GREEDY` under identical budgets. Values are
success-adjusted efficiency; 10,000-resample paired stratified bootstrap.

| Scope | Mean difference | 95% CI | A_HIST | Baseline median | Goal-rate diff |
|---|---:|---:|---:|---:|---:|
| **Overall** | **−0.199** | [−0.206, −0.192] | 0.208 | 0.407 | −27.8 pp |
| `decoy_dag` | −0.763 | [−0.780, −0.744] | 0.000 | 0.763 | −77.3 pp |
| `nonstationary_parallel` | −0.283 | [−0.295, −0.270] | 0.500 | 0.783 | −28.3 pp |
| `trap_grid_v2` | −0.008 | [−0.021, 0.000] | 0.000 | 0.008 | −1.0 pp |
| `wall_grid` | **+0.260** | [+0.248, +0.272] | 0.333 | 0.074 | −4.5 pp |

Applying the preregistered family-competitiveness criteria to the development
data (point estimate at least equal, CI lower bound above −0.05, goal rate not
more than 10 pp worse):

- `wall_grid` qualifies (clear efficiency win; −4.5 pp goal rate within bound);
- `trap_grid_v2` fails criterion 1 narrowly (0.000 < 0.008); both methods
  essentially fail the family;
- `decoy_dag` and `nonstationary_parallel` fail decisively.

One of four families meets the bar; the preregistered gate requires three.
**At development level, historization-only navigation is not competitive with
the fairly trained baseline median.** This is a development diagnostic on
seeds 0–9, not a Gate-G1 result; the gate itself is defined on the unopened
holdout.

Additional context from the method aggregates:

- `A_HIST` (0.208 efficiency / 0.208 goal rate) is outscored overall by
  `UNIFORM_RANDOM` (0.273 / 0.349).
- `A_HIST` does beat `MEMORYLESS_GREEDY` (0.125) and `EPSILON_GREEDY` (0.158),
  consistent with the trap-escape claim E0-HIST-TRAPS-001.
- Median wall-time: `A_HIST` 8.8 s per replicate vs. 3.2–4.3 s for the three
  competitive baselines; the geometry variants D/E cost 139–146 s for
  identical scores.
- Map-informed upper references `A_STAR`/`D_STAR_LITE` reach 0.875.

## Interpretation boundary

- Development seeds are preregistered for implementation checking and control
  selection; reporting these diagnostics does not contaminate the holdout.
- No configuration was changed after these data were seen; all frozen configs
  remain frozen.
- No holdout seed was instantiated or read. No Gate-G1 PASS/FAIL exists.
- The strong `wall_grid` result is real but is one designed family; it is not
  evidence of general competitiveness.

## Consequences

1. Per the preregistered G1-B interpretation rule in
   `E0_UMSETZUNGSPLAN_v1.md`: when standard methods are robustly ahead, the
   lean packages are repositioned as a lightweight, explainable, training-free
   alternative with documented trade-offs, and superiority claims are not
   made. The development evidence now activates that rule at development
   level.
2. **USER DECISION — holdout lifecycle:** either (a) close G1-v1 on
   development evidence with the holdout permanently unopened and record the
   gate as not executed, or (b) authorize the one-time holdout run
   (~4,680 replicates, roughly 3× the development compute) to convert these
   diagnostics into a formal preregistered gate result. Until that decision,
   the holdout stays closed.
3. The Override-Gate v2 calibration remains parked behind its authorization
   boundary; calibrating an override threshold for a lookahead that is
   causally inactive and non-competitive is not a priority.
