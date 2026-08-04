# E₀ Decision Benchmark — Development Report v1

**Protocol:** `E0-G1-v1`  
**Split:** development only  
**Holdout accessed:** no  
**Gate result:** none

## Scope

This report contains the full WP-2.4 development execution. It freezes
the preregistered simpler G1-A control but does not pass or fail Gate G1.
All positive and negative values below are development diagnostics.

## Method overview

| Method | Replicates | Mean efficiency | Goal rate | Median wall-time ms | Valid negatives |
|---|---:|---:|---:|---:|---:|
| `A_HIST` | 120 | 0.208333 | 0.208333 | 8797.097 | 0 |
| `B_INCOHERENT` | 120 | 0.208333 | 0.208333 | 28250.608 | 0 |
| `C_THETA_ZERO` | 120 | 0.208333 | 0.208333 | 32245.823 | 0 |
| `D_U1_PHASE` | 120 | 0.208333 | 0.208333 | 146041.539 | 0 |
| `E_FULL_GEOMETRY` | 120 | 0.208333 | 0.208333 | 138759.614 | 3 |
| `Q_LEARNING` | 120 | 0.384998 | 0.770833 | 4268.773 | 0 |
| `UCB1_EDGE` | 120 | 0.392776 | 0.395833 | 3223.412 | 0 |
| `RANDOM_RESTART_GREEDY` | 120 | 0.463955 | 0.537500 | 3453.717 | 0 |
| `MEMORYLESS_GREEDY` | 120 | 0.125000 | 0.125000 | 7168.377 | 0 |
| `EPSILON_GREEDY` | 120 | 0.157901 | 0.158333 | 6691.849 | 0 |
| `UNIFORM_RANDOM` | 120 | 0.272642 | 0.348750 | 4256.277 | 0 |
| `A_STAR` | 120 | 0.875000 | 0.875000 | 192.657 | 0 |
| `D_STAR_LITE` | 120 | 0.875000 | 0.875000 | 309.104 | 0 |

## Frozen simpler-control selection

Selected: **`A_HIST`**.

| Candidate | Pooled mean efficiency | Median wall-time ms |
|---|---:|---:|
| `A_HIST` | 0.208333 | 8797.097 |
| `B_INCOHERENT` | 0.208333 | 28250.608 |
| `C_THETA_ZERO` | 0.208333 | 32245.823 |

## Paired development diagnostics

### Full geometry versus selected control

Treatment `E_FULL_GEOMETRY`; control `A_HIST`.

| Scope | Mean difference | 95% paired bootstrap CI | Treatment mean | Control mean | Goal-rate difference |
|---|---:|---:|---:|---:|---:|
| Overall | 0.000000 | [0.000000, 0.000000] | 0.208333 | 0.208333 | 0.000000 |
| `decoy_dag` | 0.000000 | [0.000000, 0.000000] | 0.000000 | 0.000000 | 0.000000 |
| `nonstationary_parallel` | 0.000000 | [0.000000, 0.000000] | 0.500000 | 0.500000 | 0.000000 |
| `trap_grid_v2` | 0.000000 | [0.000000, 0.000000] | 0.000000 | 0.000000 | 0.000000 |
| `wall_grid` | 0.000000 | [0.000000, 0.000000] | 0.333333 | 0.333333 | 0.000000 |

### U(1) phase versus Θ=0

Treatment `D_U1_PHASE`; control `C_THETA_ZERO`.

| Scope | Mean difference | 95% paired bootstrap CI | Treatment mean | Control mean | Goal-rate difference |
|---|---:|---:|---:|---:|---:|
| Overall | 0.000000 | [0.000000, 0.000000] | 0.208333 | 0.208333 | 0.000000 |
| `decoy_dag` | 0.000000 | [0.000000, 0.000000] | 0.000000 | 0.000000 | 0.000000 |
| `nonstationary_parallel` | 0.000000 | [0.000000, 0.000000] | 0.500000 | 0.500000 | 0.000000 |
| `trap_grid_v2` | 0.000000 | [0.000000, 0.000000] | 0.000000 | 0.000000 | 0.000000 |
| `wall_grid` | 0.000000 | [0.000000, 0.000000] | 0.333333 | 0.333333 | 0.000000 |

### A_HIST versus competitive baseline median

Treatment `A_HIST`; control `BASELINE_MEDIAN`.

| Scope | Mean difference | 95% paired bootstrap CI | Treatment mean | Control mean | Goal-rate difference |
|---|---:|---:|---:|---:|---:|
| Overall | -0.198651 | [-0.205581, -0.191707] | 0.208333 | 0.406984 | -0.277917 |
| `decoy_dag` | -0.762916 | [-0.780061, -0.744228] | 0.000000 | 0.762916 | -0.773333 |
| `nonstationary_parallel` | -0.283333 | [-0.295000, -0.270000] | 0.500000 | 0.783333 | -0.283333 |
| `trap_grid_v2` | -0.007859 | [-0.021232, 0.000000] | 0.000000 | 0.007859 | -0.010000 |
| `wall_grid` | 0.259506 | [0.247958, 0.271976] | 0.333333 | 0.073828 | -0.045000 |

## Interpretation boundary

- Development seeds are used for implementation checking and control selection.
- No holdout seed was instantiated or read.
- These diagnostics do not constitute Gate G1 evidence.
- `summary.json` is derived solely from `raw_runs.jsonl`; evaluation
  episodes are retained in `episodes.jsonl.gz`.

