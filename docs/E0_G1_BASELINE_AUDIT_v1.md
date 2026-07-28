# E₀ Gate G1 Baseline Audit v1

**Protocol:** `E0-G1-v1`
**Work package:** WP-2.2
**Status:** implemented and frozen before holdout access
**Holdout execution:** not started

## 1. Scope

WP-2.2 supplies method adapters and fixed global configurations. It does not
rank methods, select a winner, execute holdout seeds, or produce a Gate G1
finding.

The compatibility command is:

```text
py -3 -m e0_controller.g1_baseline_harness
```

On the complete development inventory it exercises:

```text
4 families × 3 scales × 10 development seeds × 8 methods = 960 adapter runs
```

The WP-2.2 acceptance run completed 960/960 adapter runs with
`holdout_accessed=false` and `not_g1_result=true`.

## 2. Why the historical runners are not reused as evidence

The repository already contained useful baseline prototypes:

- `benchmark_sota.py`: memoryless greedy, ε-greedy, tabular Q-learning, random;
- `benchmark_gridworld.py`: A* and grid-specific comparisons;
- `benchmark_scaling.py`: E₀, memoryless greedy, and random at larger N.

They remain historical evidence, but they do not implement the E0-G1-v1
interaction contract. In particular:

1. Q-learning was evaluated as a single navigation episode rather than the
   preregistered 10 adaptation plus 20 evaluation episodes.
2. FAILURE handling differed between runners: some advanced to the target,
   some retried another action, and some ignored the outcome.
3. Information access was not recorded, so map-informed A* could be compared
   as if it were equally informed.
4. Stochastic repetitions were averaged into one result instead of retaining
   the generator/outcome/policy seed pairing.

WP-2.2 therefore reuses the audited algorithmic intent, not the old result
records.

## 3. Shared interaction contract

Every adapter receives the same per-episode budget:

```text
4 × actual_node_count environment interactions
```

One action attempt consumes exactly one interaction. On SUCCESS the position
moves to the target. On FAILURE the position remains at the source. Position
and episodic executor state reset between episodes; method learning state is
preserved. Learning continues during evaluation.

Equal-information methods receive only:

- current state and goal identifier;
- currently outgoing edges;
- local Δ and base resistance;
- their own observed outcomes.

They do not receive the global topology, oracle cost, hidden success
probabilities, regime switch, or future outcomes.

## 4. Method audit

| Method | Protocol role | Reference/audit basis | G1-specific implementation |
|---|---|---|---|
| `Q_LEARNING` | competitive G1-B | [Watkins & Dayan 1992](https://doi.org/10.1007/BF00992698); existing `benchmark_sota.py` | Tabular off-policy update; one global α/γ/ε schedule; state persists across all 30 episodes |
| `UCB1_EDGE` | competitive G1-B | [Auer, Cesa-Bianchi & Fischer 2002](https://doi.org/10.1023/A:1013689704352) | Project operationalization: outgoing edges are arms; bounded episode success is Monte-Carlo credit assigned to traversed edges |
| `RANDOM_RESTART_GREEDY` | competitive G1-B | no single canonical reference procedure | Project operationalization: each protocol episode is a legal position restart; randomized local exploration and persistent failure/path penalties vary restarts; no free within-episode teleport |
| `MEMORYLESS_GREEDY` | diagnostic | audited repository baseline | Deterministic local `argmin(Δ × R₀)`, lexicographic tie-break, no learned state |
| `EPSILON_GREEDY` | diagnostic | audited repository baseline | Fixed ε=0.2 local exploration, no learned values |
| `UNIFORM_RANDOM` | diagnostic | audited repository baseline | Uniform local action selection |
| `A_STAR` | map-informed upper reference | [Hart, Nilsson & Raphael 1968](https://doi.org/10.1109/TSSC.1968.300136) | Full static topology, unit interaction cost, admissible zero heuristic; observed failed edge blocked for the current episode |
| `D_STAR_LITE` | map-informed upper reference | [Koenig & Likhachev 2002](https://publications.ri.cmu.edu/d-lite) | Incremental `g/rhs` replanning within an episode; unit cost and zero heuristic; observed failed edge changes to infinite cost for that episode |

The fixed machine-readable parameters live in
`docs/E0_G1_BASELINE_CONFIGS_v1.json`.

## 5. Explicit deviations and exclusions

### UCB1 edge credit

The original UCB1 problem is a bandit, not a graph-navigation specification.
Treating each outgoing edge as an arm and assigning delayed episode reward is
an explicit project operationalization. It is frozen here so that the rule
cannot be changed after seeing holdout behavior.

### Random-Restart-Greedy

There is no single canonical algorithm matching this name. A free teleport to
the start inside an episode would violate the shared interaction contract.
Restarts therefore occur only at the protocol's normal episode boundary.

### A*

State identifiers differ across families, so one common informative heuristic
would either be domain-specific or risk inadmissibility. The frozen zero
heuristic is admissible everywhere; A* consequently behaves as unit-cost
Dijkstra. BFS is retained as a test oracle and confirms the same optimal path
length. BFS is not an additional preregistered method.

### D* Lite

The implementation preserves D* Lite's incremental `g/rhs` repair after an
observed edge-cost change, but initializes a new planning problem at each
protocol episode. Hidden outcome probabilities and the nonstationary switch are
not exposed.

### Upper-reference exclusion

A* and D* Lite receive the full static topology. They are reported as upper
references but are excluded from the G1-B comparator exactly as preregistered.

## 6. Interpretation boundary

WP-2.2 establishes:

- executable method contracts;
- fixed information boundaries;
- fixed global configurations;
- complete development-domain compatibility.

It establishes no comparative performance claim. Development outcomes are not
Gate G1 evidence, and holdout access remains blocked.
