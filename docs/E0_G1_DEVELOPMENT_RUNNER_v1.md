# E0-G1 Development Runner v1

**Work package:** WP-2.4  
**Protocol:** `E0-G1-v1`  
**Scope:** Development data only. This runner neither reads holdout seeds nor
produces a Gate-G1 decision.

## Purpose

`e0_controller.g1_development_report` executes the preregistered full-budget
development matrix for all five E0 ablations and all eight baseline methods.
It replaces compatibility-only smoke runs with the exact interaction protocol:
10 adaptation episodes followed by 20 evaluation episodes per replicate.

The complete matrix contains:

- 4 domain families x 3 scales x 10 development seeds = 120 instances;
- 13 methods per instance;
- 1,560 independent replicates;
- 31,200 evaluation-episode records.

## Reproducible execution

From the repository root:

```powershell
py -3 -m e0_controller.g1_development_report --workers 4
```

The default output directory is:

```text
artifacts/g1/E0-G1-v1/development/wp2_4
```

The command resumes from valid per-replicate shards. Each pending replicate is
executed in a fresh worker process so peak-memory measurements and mutable
controller state do not leak between replicates. The shard directory is
regenerable and therefore ignored by Git; the six consolidated artifacts are
the reviewable evidence bundle.

Use `--no-resume` to reject an existing output directory or `--overwrite` to
replace consolidated artifacts and rerun the selected matrix. Narrow
`--families`, `--scales`, `--seeds`, and `--methods` selections exist for
engineering tests only and are not substitutes for the full WP-2.4 run.

## Evidence bundle

The complete run writes:

| File | Role |
|---|---|
| `manifest.json` | Protocol/source identity, scope guards, counts, file hashes |
| `frozen_configs.json` | Exact baseline/ablation configs and selected simpler control |
| `raw_runs.jsonl` | One full-budget replicate record per method and instance |
| `episodes.jsonl.gz` | Evaluation-episode records with deterministic gzip encoding |
| `summary.json` | Aggregates, development diagnostics, paired uncertainty intervals |
| `environment.json` | Runtime, platform, memory, and package environment |

The Markdown report is derived from `summary.json` and written to
`docs/research/E0_DECISION_BENCHMARK_v1.md`.

## Statistical and decision boundary

- The simpler primary control is selected only from `A_HIST`,
  `B_INCOHERENT`, and `C_THETA_ZERO`.
- Selection maximizes pooled mean efficiency; exact ties prefer lower median
  wall time.
- Paired bootstrap intervals use 10,000 resamples, seed `20260728`, the
  instance as resampling unit, and family x scale strata.
- Development comparisons are diagnostics used to freeze the control before
  holdout access.
- A valid negative result remains evidence and is not converted into an
  infrastructure failure.
- No WP-2.4 artifact passes or fails G1-A or G1-B. That requires the separately
  authorized held-out phase.

## Safety and recovery

Holdout seeds are rejected before task creation. Every raw and manifest record
states `holdout_accessed=false`; final output states
`holdout_execution_started=false` and `not_g1_result=true`.

Writes are atomic. A shard is resumed only when its run ID, method, instance,
protocol identity, episode count, and status contract validate. Missing or
invalid shards are recomputed. Infrastructure failures prevent consolidation,
while protocol-valid negative outcomes remain in the bundle.
