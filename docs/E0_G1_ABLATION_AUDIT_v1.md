# E₀ Gate G1 Causal Ablation Audit v1

**Protocol:** `E0-G1-v1`
**Work package:** WP-2.3
**Status:** implemented and frozen before holdout access
**Holdout execution:** not started

## 1. Scope

WP-2.3 implements the five preregistered E₀ variants and verifies their causal
boundaries on all development-domain shapes. It does not execute the full
30-episode experiment, rank variants, select the primary simpler control, read
holdout seeds, or produce a Gate G1 finding.

The bounded compatibility command is:

```text
py -3 -m e0_controller.g1_ablation_harness
```

By default it exercises one environment interaction in each cell:

```text
4 families × 3 scales × 10 development seeds × 5 variants = 600 adapter runs
```

Full-budget development raw data and the preregistered simpler-control
selection belong to WP-2.4.

## 2. Shared causal contract

All five variants begin with an empty learning state and share:

- the same static topology, edge difference, and base resistance;
- the same own observed SUCCESS/FAILURE outcomes;
- the same historization parameters and per-episode revisit reset;
- the same environment-interaction budget and FAILURE-as-no-transition rule.

They never receive hidden success probabilities, future keyed outcomes, the
nonstationary switch, oracle cost, or another method's observations.

`A_HIST` receives the shared representation but performs no path lookahead.
For B–E, candidates are the sorted local outgoing edges and the path family is
the same bounded `simple` family at horizon 3.

## 3. The five isolated variants

| ID | Decision support | Isolated mechanism |
|---|---|---|
| `A_HIST` | Historized effective-tension greedy plus recent-state penalty | Memory and revisit only |
| `B_INCOHERENT` | `Σ exp(-2S(p))` | Non-coherent lookahead |
| `C_THETA_ZERO` | `|Σ exp(-S(p))|²` | Coherent path mass with forced zero phase |
| `D_U1_PHASE` | `|Σ exp(-S(p)+iΘ(p))|²` | U(1) phase relative to C |
| `E_FULL_GEOMETRY` | `lean.structural_geometry.influence_map` | Packaged full geometry path |

The D implementation uses `structural_geometry.theta` manually. E invokes
`structural_geometry.influence_map` directly and verifies that its returned
paths are byte-for-byte equivalent to the family supplied to B–D.

## 4. Common override rule

B–E first compute the same historized/revisit greedy action. Lookahead replaces
that action only when:

1. the preferred lookahead action disagrees with greedy;
2. normalized support confidence is at least 0.85;
3. path-count imbalance is at most 3.0;
4. the 100,000-path cap was not hit.

Tie-breaking is lexicographic for every variant. A cap hit ends the decision,
is recorded as `path_cap_hit`, and gives primary score 0.0 under the
preregistered valid-negative rule.

## 5. Interpretation boundary

The WP-2.3 compatibility artifact establishes implementation reachability,
determinism, identical causal inputs, shared path enumeration, and explicit
failure reporting. Its one-interaction cells are deliberately not performance
data.

The `primary_control_selection.selected` field remains `null`. WP-2.4 must
generate the full development raw data, apply the fixed selection rule over
`A_HIST`, `B_INCOHERENT`, and `C_THETA_ZERO`, and freeze that name before any
holdout execution.
