# E0-G1 Distributed Development Execution v1

**Work package:** WP-2.4
**Protocol:** `E0-G1-v1`
**Execution target:** standard GitHub-hosted Ubuntu runners
**Scope:** development only; no holdout access and no Gate-G1 decision

## Why the C327 run was stopped

The C327 local run persisted 196 of 1,560 atomic shards between
2026-07-28 14:45 CEST and 2026-07-29 08:45 CEST. It did not hang: four worker
processes remained CPU-active and continued to produce shards. The execution
was nevertheless practically non-terminating because the 60-second episode and
1,800-second replicate limits were evaluated only after the computation
returned. Several N=500 replicates consumed hours before receiving the valid
negative `algorithm_timeout` status.

The process tree was stopped deliberately. The 196 completed shards, empty
stderr log, and stdout event log remain local under:

```text
artifacts/g1/E0-G1-v1/development/wp2_4_c327_aborted_20260729
```

`manifest.partial.json` records hashes, coverage, counts, and disposition.
These files are engineering/scalability evidence. They must not be merged into
the corrected full evidence bundle.

## Corrected resource boundaries

The corrected runner applies both protocol limits operationally:

1. `run_episode` checks the 60-second deadline at decision boundaries. A timed
   out episode cannot report goal success or positive efficiency.
2. Each replicate runs in a dedicated child process.
3. The parent terminates and, if necessary, kills the child at the
   preregistered 1,800-second replicate boundary.
4. Hard termination produces a complete, explicitly censored valid-negative
   shard with primary score `0.0`.
5. Infrastructure failures remain distinct from valid algorithmic negatives.

The process boundary also isolates controller state, peak memory, exceptions,
and runaway computation between replicates.

## Deterministic GitHub partition

The 1,560 tasks are distributed by stable striding into 240 batches:

- 240 matrix jobs, within GitHub's 256-job matrix limit;
- 6 or 7 unique replicates per job;
- up to 20 jobs in parallel on GitHub Free;
- 4 bounded worker processes per four-core public runner;
- 120-minute job timeout, below GitHub's six-hour hosted-job limit;
- `fail-fast: false`, so one failed batch does not cancel unrelated evidence.

The workflow is manual-only:

```text
.github/workflows/g1-development.yml
```

It cannot start on a push or pull request. A human must invoke
`workflow_dispatch`.

## Artifact flow

Each matrix job uploads only its compressed atomic JSON shards. Artifact names
include the unique batch index. The consolidation job:

1. downloads all `g1-shards-*` artifacts;
2. merges their unique shard filenames into one directory;
3. validates all 1,560 task identities against the current commit;
4. rejects an incomplete or mixed-commit matrix;
5. invokes the existing deterministic consolidation and report renderer;
6. uploads the six protocol artifacts plus the Markdown report.

The final workflow artifact is `g1-development-evidence`. It remains a
development diagnostic and cannot pass or fail Gate G1.

## Local verification commands

Print and inspect the exact matrix:

```powershell
py -3 -m e0_controller.g1_development_distributed matrix --batch-count 240
```

Run one batch locally:

```powershell
py -3 -m e0_controller.g1_development_distributed run-batch `
  --batch-index 0 --batch-count 240 --workers 4
```

Consolidate only after all shards are present:

```powershell
py -3 -m e0_controller.g1_development_distributed consolidate
```

## Cost and publication boundary

The repository is public. Standard GitHub-hosted runners for public
repositories do not consume the private-repository minute quota. The workflow
does not request larger or paid runners. Shards are compressed and retained for
seven days to remain below the GitHub Free artifact-storage allowance.

No workflow can run until the corrected commit and workflow are pushed. That
push and the manual workflow dispatch require separate explicit authorization;
the local implementation does neither.
