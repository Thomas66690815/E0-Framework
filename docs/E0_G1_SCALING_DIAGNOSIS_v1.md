# E₀ Gate G1 — Development Scaling Diagnosis v1

**Protocol:** `E0-G1-v1`

**Scope:** development only

**Holdout accessed:** no

**Gate result:** none

**Source run:** GitHub Actions `30438690300`, commit `af2ae45`

**Remediation:** `E0_G1_SCALING_REMEDIATION_v1.md`

## Finding

The WP-2.4 timeout pattern has a specific implementation cause. The phase-aware
methods rebuild the complete navigation field and solve a global graph-Laplacian
system from a zero initial state at every decision. This work is repeated after
each observed transition even though the graph topology is unchanged and only
edge costs have changed.

Path enumeration is not the scaling bottleneck. The frozen horizon is three,
the sampled `wall_grid` decision at `N=1000` expands 24 paths, and enumeration
takes about `0.14 ms`. The 100,000-path cap was not reached anywhere in the
WP-2.4 evidence.

## WP-2.4 signature

The consolidated development artifact contains 1,560/1,560 replicate records,
including 183 valid negative `algorithm_timeout` records and zero infrastructure
failures.

| Method | Algorithm timeouts | Timeout cells |
|---|---:|---|
| `B_INCOHERENT` | 10 | `wall_grid`, `N=1000` |
| `C_THETA_ZERO` | 13 | `wall_grid`, `N=1000`; three `trap_grid_v2`, `N=1000` |
| `D_U1_PHASE` | 80 | every family at `N=500` and `N=1000` |
| `E_FULL_GEOMETRY` | 80 | every family at `N=500` and `N=1000` |

The identical D/E timeout boundary isolates their shared phase path rather than
the `influence_map` wrapper as the primary cause.

## Cold-decision profile

`tools/profile_g1_scaling.py` profiles only development seeds and separates
field construction, path enumeration, aggregation, phase diagnostics, and the
complete decision. Representative seed-0 `wall_grid` measurements on the local
development machine are:

| Scale | B/C full decision | D/E full decision | Cold phase calculation | Path enumeration |
|---:|---:|---:|---:|---:|
| 100 | 1.25–1.31 ms | 10.0–10.9 ms | 8.7–10.2 ms | 0.08–0.11 ms |
| 500 | 6.49–7.26 ms | 78.2–79.3 ms | 72.0–76.2 ms | 0.14–0.18 ms |
| 1000 | 14.30–14.36 ms | 205.2–225.6 ms | 197.3–199.7 ms | 0.14 ms |

A bounded real-episode reproduction gives the same ordering:

| Domain | Budget | B | C | D | E |
|---|---:|---:|---:|---:|---:|
| `wall_grid`, `N=500` | 100 decisions | 779 ms | 789 ms | 8,229 ms | 8,187 ms |
| `wall_grid`, `N=1000` | 50 decisions | 826 ms | not sampled | 10,956 ms | 11,056 ms |

At the preregistered maximum of `4*N` decisions per episode and 30 episodes per
replicate, even the non-phase field rebuild is enough to put B/C close to the
30-minute replicate boundary on `wall_grid N=1000`. The phase solve makes D/E
unavoidably exceed it.

## Code-level cause

The repeated work is:

1. `E0AblationAdapter._lookahead_record()` calls `_nav_field()` for every
   decision.
2. `_nav_field()` copies every state and edge into a new `NavField`.
3. D calls `theta()` while aggregating paths; E calls it through
   `influence_map()`.
4. `theta()` requests the connection table.
5. The connection table calls `_solve_potential()` through `v_grad()`.
6. Because the `NavField` is new, no potential or connection cache survives
   from the previous decision.
7. For components larger than 256 nodes, `_solve_potential()` runs unpreconditioned
   conjugate gradients from `x=0`. The Laplacian topology is unchanged, but its
   operator, prior solution, and Krylov information are rebuilt and discarded.

A `cProfile` sample for `wall_grid N=1000` attributes the dominant cumulative
time to `_omega_table()`, `_solve_potential()`, `solve_cg()`, and its sparse
Python `matvec()`. The phase-regime scan on an already warm field is only about
5 ms; the cold solve is about 200 ms.

Two smaller costs remain:

- B/C also pay `O(E)` to rebuild the field on every decision.
- E enumerates and retains the same path family a second time to verify parity
  with B–D. At horizon three this is measurable but negligible relative to the
  phase solve.

## Timeout-boundary defect

The resource limits compose without any completion margin:

```text
30 episodes × 60 seconds per episode = 1,800 seconds per replicate
```

The hard replicate limit is also 1,800 seconds. A replicate in which every
episode reaches its allowed timeout cannot serialize a result before the hard
kill. The distributed wrapper therefore emits a valid negative but fully
censored synthetic shard, losing the partial episode measurements produced by
the child.

This boundary defect does not make the method fast enough; it explains why the
observed D/E records end at almost exactly 1,800 seconds and contain no partial
execution metrics.

## Interpretation

The WP-2.4 results remain valid evidence for the frozen implementation:
compute cost is part of the preregistered practical-value gate, and algorithmic
timeouts are valid negative outcomes. The diagnosis does not retroactively turn
those records into infrastructure failures.

It does show that the negative result combines method behavior with a concrete,
removable execution strategy. No holdout should be spent before a
development-only rerun establishes whether a semantics-preserving implementation
can meet the fixed resource limits.

## Recommended implementation sequence

### Semantics-preserving candidate

1. Keep one `NavField` per adapter and update only the changed edge cost.
2. Cache topology-dependent component indices, edge lists, and Laplacian
   operators separately from cost-dependent values.
3. Warm-start conjugate gradients from the previous potential. Add convergence
   status and residual reporting instead of silently returning the last iterate.
4. Avoid recomputing diagnostic `phase_regime()` after the same decision has
   already built the connection table.
5. Preserve exact B–E candidates, path families, scores, override decisions,
   and interaction traces within an explicit numerical tolerance.
6. Make timeout serialization graceful: retain completed episode records and
   synthesize only the unexecuted remainder when the replicate deadline is
   reached.

These changes can remain under `E0-G1-v1` only if parity tests demonstrate that
they change execution cost but not method semantics. They still require a
transparent implementation amendment and a complete development rerun before
holdout.

### Protocol-changing alternatives

Refreshing phase only every `k` decisions, using a local instead of global
decomposition, loosening solver tolerance without parity evidence, reducing the
path horizon, or changing the compute limits alters the tested method or gate.
Those options require a new preregistered protocol version rather than a silent
repair of `E0-G1-v1`.

## Reproduction

Examples:

```powershell
python -m tools.profile_g1_scaling --family wall_grid --scale 500 --seed 0 --method D_U1_PHASE
python -m tools.profile_g1_scaling --family wall_grid --scale 1000 --seed 0 --method E_FULL_GEOMETRY
```

The profiler calls `validate_development_seed()` before constructing a domain;
holdout seeds are rejected.
