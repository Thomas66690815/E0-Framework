# E₀ Gate G1 — Development Scaling Remediation v1

**Protocol:** `E0-G1-v1`

**Scope:** development only

**Holdout accessed:** no

**Gate result:** none

**Predecessor:** `E0_G1_SCALING_DIAGNOSIS_v1.md`

**Development-result diagnosis:** `E0_G1_MECHANISM_DIAGNOSIS_v1.md`

## Result

C330 removes the implementation bottleneck identified after the first complete
WP-2.4 development run. The method definitions, candidate actions, bounded path
families, phase equations, override gate, interaction budgets, and timeout
limits are unchanged.

The optimized path:

1. keeps one `NavField` per lookahead adapter instead of rebuilding all nodes
   and edges for every decision;
2. synchronizes every previously observed edge after each historization event,
   preserving the global lazy-decay semantics;
3. separates value-cache invalidation from topology-cache invalidation;
4. reuses component indices, Laplacian edge structures, triangle topology, and
   reverse-edge relationships across cost updates;
5. uses one cached SciPy sparse factorization per fixed component topology when
   the `science` extra is available;
6. falls back to warm-started conjugate gradients when SciPy is unavailable;
7. computes the connection table once per decision and reuses it across all
   candidate path sums;
8. records the SciPy version in the reproducibility environment.

The manual GitHub Actions development workflow now installs `.[science]`
explicitly, so a rerun uses the tested sparse-direct backend rather than
depending on packages preinstalled on a runner image.

## Development-only performance

All values below use development seed 0 on the same local machine as the C329
diagnosis. They are engineering timings, not Gate G1 evidence.

### Bounded real episode path

| Domain | Budget | Method | Before C330 | After C330 | Approximate speedup |
|---|---:|---|---:|---:|---:|
| `wall_grid`, `N=500` | 100 | B | 779 ms | 69 ms | 11.3× |
| `wall_grid`, `N=500` | 100 | C | 789 ms | 56 ms | 14.1× |
| `wall_grid`, `N=500` | 100 | D | 8,229 ms | 517 ms | 15.9× |
| `wall_grid`, `N=500` | 100 | E | 8,187 ms | 535 ms | 15.3× |
| `wall_grid`, `N=1000` | 50 | B | 826 ms | 70 ms | 11.8× |
| `wall_grid`, `N=1000` | 50 | D | 10,956 ms | 518 ms | 21.1× |
| `wall_grid`, `N=1000` | 50 | E | 11,056 ms | 525 ms | 21.1× |

### Full worst-case episode budget

The original implementation could not complete D/E at `N=1000` within the
60-second episode limit. The remediated implementation completed all 4,000
allowed interactions without a path-cap hit:

| Domain | Method | Decisions | Wall time | Status |
|---|---|---:|---:|---|
| `wall_grid`, `N=1000`, seed 0 | D | 4,000 | 39.16 s | completed |
| `wall_grid`, `N=1000`, seed 0 | E | 4,000 | 38.12 s | completed |

This establishes local headroom of about 20 seconds for the sampled worst-case
episode. It does not substitute for the complete 1,560-replicate development
rerun on the target GitHub runner environment.

## Semantic parity checks

The focused test suite verifies:

- a persistent adapter field matches a freshly rebuilt reference field after
  historization updates;
- B–E path-family signatures and scores remain aligned;
- sparse-direct and CG phase solvers choose the same action on a real
  `wall_grid N=500` development instance;
- sparse-direct, CG, and dense Cholesky solve the same reduced Laplacian within
  explicit tolerances;
- a warm CG start converges to the cold solution;
- cost changes invalidate value-dependent geometry but preserve the topology
  revision;
- topology changes invalidate topology-dependent data;
- holdout construction remains rejected.

The optimization can change wall-time outcomes: cells that previously received
valid negative timeout scores may now finish and yield measured scores. That is
the purpose of the remediation, not a change to the action policy.

## Evidence status

The first WP-2.4 bundle remains the valid result for commit `af2ae45` and its
implementation. It must not be overwritten or silently reinterpreted.

C330 required a new, source-commit-bound full development execution. That
requirement was satisfied by GitHub Actions run `30526724307` on source commit
`3990b5d`; the resulting mechanism diagnosis is recorded in
`E0_G1_MECHANISM_DIAGNOSIS_v1.md`. The completed rerun:

1. retained the same development seeds and protocol constants;
2. reported the SciPy version and clean source commit;
3. validated all 1,560 shards and every timeout/path-cap status;
4. regenerated the development summary;
5. repeated and froze the preregistered simpler-control selection;
6. remained explicitly marked `not_g1_result`; and
7. left all holdout seeds unread.

The fixed implementation now has sufficient resource margin, but C331 finds no
development behavior that justifies spending the protected Gate G1 holdout.

## Remaining boundary issue

The exact equality

```text
30 episodes × 60 seconds = 1,800-second replicate hard limit
```

still leaves no serialization margin when every episode times out. C330 makes
that state substantially less likely but does not change the preregistered
limits or the hard-kill representation. Graceful partial-result preservation
should be handled as a separate, transparent execution-layer change.
