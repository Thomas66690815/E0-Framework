# When Structure Is Not Enough: A Preregistered Negative Evaluation of a Training-Free Navigation Framework

**Thomas Wehner** (with AI collaborators)

**v2 — 2026-08-05 — WP-5.2 (C335, updated C339 with the executed WP-6
result). Cleared for arXiv (cs.AI) submission by user decision of
2026-08-05.**

---

## Abstract

We report the preregistered evaluation and closure of E₀, a training-free
structural navigation framework built on two mechanisms: *historization*
(persistent success/failure traces that modulate edge resistance) and a
*geometric interference layer* (an exact discrete Helmholtz decomposition
inducing a U(1) connection, path phases, and an amplitude-based lookahead).
Across 1,560 preregistered replicates on four designed domain families at
three scales under equal interaction budgets, we find: (1) the complete
geometric stack contributes exactly 0.0 over plain historization — a
mechanism-level diagnosis shows the interference layer is causally inactive
at the action boundary; (2) historization-only navigation is not competitive
with fairly trained standard baselines (success-adjusted efficiency 0.208
vs. 0.407 for the per-instance median of tabular Q-learning, UCB1, and
random-restart greedy; paired difference −0.199, 95 % CI [−0.206, −0.192]);
(3) the single exception is a family of wall-structured trap domains, where
failure memory beats the baseline median by +0.260 [+0.248, +0.272]. A
separately preregistered calibration of the framework's confidence-gated
override selected `gate_disabled`: no threshold met its eligibility criteria.
A final preregistered experiment then tested the one surviving mechanism in
its intended role — persistent tool-reliability memory for budget-constrained
agents — and passed: +48–54 % completed tasks over memoryless selection, with
the honest bound that a stateless sticky heuristic captures most of the
stationary value and the memory's real differentiator is recovery under
drift. We describe the preregistration, fair-baseline, causal-ablation, and
evidence-ledger methodology that produced these conclusions inside the same
repository that had strong incentives to avoid them, and we argue that the
mechanistic *why* of the null result — a conjunction of gating, phase-regime
degeneracy, and an implementation equivalence — is more informative than the
null itself.

---

## 1. Introduction

E₀ began as an ambitious research program: derive learning, forgetting,
lookahead, and self-reflection from a single structural axiom, with no
probabilities, no training data, and no free parameters at the foundation.
Over 330 numbered commits it grew to ~36,000 lines of production code, 7,166
tests, and fourteen integrated layers.

This paper is not about that ambition. It is about what happened when the
program was forced to answer one question under preregistered rules: *does
any of it beat the obvious alternatives under equal conditions?*

The honest answer is: mostly no, narrowly yes. We consider both halves of
that answer, and the machinery that extracted it, to be the program's actual
contribution. Negative results of this kind are rarely published with full
raw data, a frozen preregistration, causal ablations, and a mechanism-level
diagnosis of *why* the flagship mechanism cannot act. This paper provides
all four.

Contributions:

1. **A preregistered negative result** for a training-free structural
   navigation framework against fairly trained baselines, with all raw data
   retained (§5).
2. **A causal-ablation design** (five variants sharing one operationalization)
   that localizes all measured behavior in a single mechanism (§4, §5.1).
3. **A mechanism diagnosis** explaining the exact conjunction that keeps the
   interference layer inert (§6).
4. **A scoped positive finding**: edge-local failure memory wins where
   failures are persistent and structural (§5.2).
5. **A methodological account** of preregistration, evidence ledgers, and
   external audit inside a small human–AI research collaboration (§7).
6. **An honestly bounded positive closure**: a final preregistered
   experiment on the surviving mechanism's intended use case, passed with
   its caveats made mandatory documentation (§9).

## 2. The system under test

### 2.1 Historization

E₀ represents a domain as a landscape of states and edges. Each edge carries
a difference Δ and a resistance R. The controller greedily minimizes
structural burden S_eff = Δ · R_eff. After each transition the outcome is
*inscribed*: successes (U) reduce effective resistance, failures (F) raise
it, with decay. This is the entire learning mechanism: no value function, no
reward propagation, no training phase. Credit assignment is strictly
edge-local.

### 2.2 The geometric layer

The framework's distinctive construction: every flow field on a graph splits
uniquely (discrete Helmholtz) into a gradient part and a rotational part,
solved exactly via a graph-Laplacian system. The rotational component
induces a connection ω, hence path phases Θ, holonomy, and curvature. A
lookahead layer sums complex amplitudes Ψ = e^(−S)·e^(iΘ) over forward path
families; interference is meant to concentrate support on goal-reaching
actions. A confidence-gated override lets this layer replace the greedy
choice when its margin is large.

To our knowledge the decomposition-induced phase is novel in this context
(quantum walks and Projective Simulation interfere amplitudes on graphs but
do not derive the phase from an orthogonal field decomposition). Novelty,
as §5 shows, is not value.

## 3. Preregistered design

The full protocol (`E0-G1-v1`) was frozen before any full-budget run,
including domains, splits, budgets, ablations, metrics, statistics, and
error rules. Key elements:

- **Domain families (4):** `wall_grid` (walls, dead ends, traps),
  `trap_grid_v2` (dense trap structure), `decoy_dag` (attractive decoy
  paths), `nonstationary_parallel` (mid-run executor switches).
- **Scales:** N ∈ {100, 500, 1000} states; exact-N generators.
- **Splits:** development seeds 0–9 (implementation checks, control
  selection); holdout seeds 1000–1029, never opened.
- **Budgets:** identical interaction and episode budgets for every method;
  10 adaptation + 20 evaluation episodes per replicate; hard per-episode
  (60 s) and per-replicate (1,800 s) deadlines in killable subprocesses.
- **Causal ablations (5):** `A_HIST` (historization only), `B_INCOHERENT`
  (amplitudes without phase coherence), `C_THETA_ZERO` (coherent, phase
  forced to zero), `D_U1_PHASE` (U(1) phase active), `E_FULL_GEOMETRY`
  (full stack). All five share one frozen operationalization, path family,
  and override rule, so any outcome difference is attributable to the
  ablated component.
- **Baselines (8, fairly configured):** tabular Q-learning, UCB1-edge,
  random-restart greedy (the three *competitive* comparators, combined per
  instance as their median), plus ε-greedy, memoryless greedy, uniform
  random, and map-informed A*/D*-Lite as upper references excluded from the
  comparator.
- **Statistics:** per-instance pairing, stratified cluster bootstrap
  (10,000 resamples), fixed seeds, preregistered family-level criteria and
  aggregation rules.

Execution: GitHub Actions, 240 deterministic batches, atomic per-replicate
shards, fail-closed consolidation; 1,560/1,560 replicates completed, zero
infrastructure failures, three valid algorithmic timeouts (all
`E_FULL_GEOMETRY`). The consolidated bundle (raw runs, 31,200 evaluation
episodes, frozen configs, environment, manifest with SHA-256 file digests)
is retained in-repository.

## 4. Results I — the geometry is causally inert

Every geometry variant scores identically to plain historization:

| Comparison | Mean difference | 95 % CI |
|---|---:|---:|
| E_FULL_GEOMETRY − A_HIST (overall and every family) | 0.000 | [0.000, 0.000] |
| D_U1_PHASE − C_THETA_ZERO (phase attribution) | 0.000 | [0.000, 0.000] |

This is not approximate equality; across all 17,929,640 persisted evaluation
decisions of the B–E variants there is not a single executed override, not a
single interfering or wrapped phase regime, and not a single divergent
selected action. The only measured difference is cost: the full-geometry
variants spend 139–146 s median wall-time per replicate against 8.8 s for
A_HIST — a ~16× compute overhead for byte-identical outcomes.

## 5. Results II — historization alone is not competitive

### 5.1 Overall

Success-adjusted efficiency (primary metric), development split, 120 paired
instances:

| Method | Efficiency | Goal rate | Median wall-time |
|---|---:|---:|---:|
| A*/D*-Lite (map-informed reference) | 0.875 | 0.875 | 0.2–0.3 s |
| Random-restart greedy | 0.464 | 0.538 | 3.5 s |
| UCB1-edge | 0.393 | 0.396 | 3.2 s |
| Q-learning (tabular) | 0.385 | 0.771 | 4.3 s |
| Uniform random | 0.273 | 0.349 | 4.3 s |
| **A_HIST** | **0.208** | **0.208** | 8.8 s |
| ε-greedy | 0.158 | 0.158 | 6.7 s |
| Memoryless greedy | 0.125 | 0.125 | 7.2 s |

A_HIST vs. the competitive baseline median: −0.199 [−0.206, −0.192], goal
rate −27.8 pp. That uniform random outperforms the framework overall is the
kind of sentence a project only writes down if its rules force it to; our
rules forced it, and the number is real. (It reflects the low goal rates of
edge-local methods on decoy- and nonstationary-dominated families, where
random restarts escape what inscribed penalties do not.)

### 5.2 Per family — the niche is real

| Family | A_HIST − baseline median | 95 % CI | Verdict |
|---|---:|---:|---|
| `decoy_dag` | −0.763 | [−0.780, −0.744] | decisive loss |
| `nonstationary_parallel` | −0.283 | [−0.295, −0.270] | decisive loss |
| `trap_grid_v2` | −0.008 | [−0.021, 0.000] | both fail (~0) |
| `wall_grid` | **+0.260** | [+0.248, +0.272] | **clear win** |

One of four families meets the preregistered competitiveness bar; the gate
required three. But the `wall_grid` result is a clean, replicable positive:
where failure is *persistent and structural* — walls and dead ends that stay
walls and dead ends — cheap edge-local failure memory beats trained
baselines that must rediscover the same dead ends across episodes. Where
failure is *misleading* (decoys) or *transient* (nonstationarity), inscribed
penalties are at best useless and at worst poison.

### 5.3 The override gate calibrates to "off"

Independently of G1, the confidence-gated override was given its own
preregistered calibration (2,880 tasks, 12 candidate policies, clustered
bootstrap, Holm-corrected eligibility across 77 constraints). Outcome: no
active candidate was eligible; the preregistered fail-closed selection was
`gate_disabled`. A caveat we discovered afterwards and report openly: 73 %
of calibration replicates hit a timeout whose v1 label conflated parent
computation with diagnostic branch instrumentation, so the calibration
cannot cleanly rank thresholds; it can only support "no threshold met the
criteria as measured."

### 5.4 Confirmed structural limits

Two limits established earlier by falsification benchmarks stand: dense
branching (b ≥ 3) defeats the penalty mechanism combinatorially (F3), and
non-Markov dependencies cannot be learned because credit assignment is
edge-local (F4) — the system avoids the trap but cannot acquire the required
sequence.

## 6. Why the interference layer cannot act

The neutral result in §4 is not a tie between active mechanisms; it is a
conjunction of three blockers, each independently sufficient on these
domains:

1. **The gate never opens.** The preregistered override threshold is 0.85;
   the maximum conflict confidence ever observed when lookahead disagreed
   with greedy was 0.42 (probe over 9,600 decisions). High-confidence states
   exist, but only when lookahead already *agrees* with greedy — precisely
   when an override changes nothing. The threshold lies outside the support
   of the conflict distribution.
2. **The phase never leaves the gradient regime.** All 4,482,410 evaluation
   decisions per variant sit in the gradient regime; circulation on these
   families is too weak to produce interfering or wrapped phases. No
   circulation → no phase → interference degenerates to plain summation
   (consistent with an earlier finding that at typical weights interference
   is purely constructive; destructive cancellation needs phase gaps ≈ π,
   outside the stable ranking range).
3. **An implementation equivalence.** For the current influence-map
   construction, the packaged E path is mathematically equivalent to D, so
   even a phase-active regime would not separate the top two variants.

The general lesson: a mechanism can be mathematically real, correctly
implemented, fully tested — and still *causally unreachable* under the
system's own operating conditions. Only a causal ablation run at full
budget, not unit tests and not demos, exposes this.

## 7. Method: making a repository falsify itself

The interesting engineering problem was not statistical but institutional:
the same collaboration that spent months building the geometry had to be
able to kill it. Mechanisms that made this work:

- **Preregistration with freezes.** Domains, budgets, criteria, statistics,
  and seeds frozen before full-budget execution; post-freeze edits require
  labeled errata (one occurred, and an external audit caught its missing
  label).
- **Fair baselines with an audit trail.** Every baseline configuration
  frozen and audited; map-informed methods explicitly excluded from the
  comparator; the embarrassing baselines (uniform random, memoryless
  greedy) included.
- **An evidence ledger.** Every strategic claim maps to a ledger entry with
  status, sources, limitations, and raw artifacts; claims are downgraded in
  place when contradicted.
- **Split discipline.** Development seeds for selection, a holdout that was
  never opened — and, at closure, the honest refusal to open it merely to
  ceremonialize a conclusion the development data had already fixed.
- **Hard execution boundaries.** Killable per-episode and per-replicate
  deadlines after a first pilot showed unbounded timeouts silently
  corrupting attribution; the aborted pilot was quarantined as
  engineering-only evidence.
- **External audit.** An independent review verified hash chains, freeze
  integrity, count consistency, and authorization boundaries, and surfaced
  the one unreported result in the pipeline (the baseline comparison in
  §5), which was then retained and reported before its CI artifact expired.

We also name the anti-pattern we had to resist: **infrastructure regress** —
answering every ambiguous or unwelcome measurement by building a more
rigorous measurement apparatus instead of drawing the available conclusion.
The override-gate line (§5.3) consumed sixteen commits of exemplary
methodology to calibrate a knob on a mechanism that §4 shows never fires.
Rigor was necessary; more rigor was not the missing ingredient — a decision
was.

## 8. Limitations

- All results are on designed synthetic families; the strong `wall_grid`
  claim has not been validated on an external domain.
- The gate was closed on development evidence; no holdout PASS/FAIL exists.
  We report this as a strategic closure, not a formal gate outcome.
- Single implementation, single research group; no independent replication.
  The full raw data, frozen configs, and environment manifests are retained
  to make replication cheap.
- The baseline set is standard but not exhaustive; no deep-RL or LLM-based
  navigation baselines were included (they violate the equal-budget,
  training-free comparison frame).
- The final experiment (§9) models tool failure as seeded Bernoulli
  processes; no production tool ecosystem was measured, and no LLM was in
  the loop by design.

## 9. What survives — the final experiment

A ~600-line, dependency-free failure-memory library (`reliability_memory`)
embodies the one mechanism that carried all measured behavior. Its remaining
product hypothesis — that an agent which persistently remembers *which tools
and paths fail* outperforms the same agent without memory, in settings where
no training budget exists — is deliberately *not* addressed by the
experiments above, whose baselines received training budgets. We closed the
program with one preregistered decision experiment on this hypothesis
(protocol `E0-WP6-RELMEM-v1`; design frozen and externally approved before
implementation; shipped defaults, no tuning; the library bound by SHA-256).

Setup: simulated tool ecosystems — tasks of five steps, four redundant tools
per step, 1,000 calls per replicate — in three regimes: persistent failure
structure (R1), mid-run drift (R2), and task-type-dependent reliability
(R3). Four arms: the memory store, memoryless uniform selection, a stateless
*sticky* heuristic ("keep the tool that last worked"), and an oracle upper
reference; 30 paired seeds per regime, 10,000-resample paired bootstrap.
Losing to the sticky one-liner in R1 was preregistered as failure.

Results (completed tasks per 1,000 calls):

| Regime | Memory | No memory | Sticky | Oracle |
|---|---:|---:|---:|---:|
| R1 persistent | **125.9** | 85.1 | 122.8 | 153.3 |
| R2 drift | **124.2** | 80.9 | 118.3 | 148.0 |
| R3 context | 85.0 | 76.9 | **105.2** | 139.3 |

The verdict under the frozen criteria is **PASS**: +48.0 % over memoryless
selection in R1 (95 % CI of the absolute difference [+35.3, +46.8]), +53.5 %
in R2, +10.5 % in R3, and a positive CI against sticky in R1 (+3.2
[+1.4, +4.9]). The honest bounds are part of the result: in stationary
regimes the sticky heuristic captures most of the achievable value (memory's
edge is only +2.6 %, a mandatory caveat now permanent in the library's
documentation); the memory's real differentiator is *drift*, where decaying
traces recover and a last-success pointer does not (+5.0 % over sticky, CI
[+3.9, +8.0]); and where reliability depends on task context, a
context-keyed sticky heuristic beat the deliberately context-free store by
19.2 % — the state key must carry the context. The program therefore ends
with a small maintained tool whose claims are exactly as large as its
evidence, and no larger.

## 10. Conclusion

We set out to derive intelligent navigation from structure alone and built
the apparatus to test whether we had. We had not: the geometric layer is
causally inert on its own benchmark, and the memory mechanism alone loses to
thirty-year-old baselines everywhere except the one environment class whose
failure structure matches its assumptions. The same apparatus, pointed at
the surviving mechanism's actual use case, returned a scoped positive with
its caveats attached. We consider the preregistered negative, its
mechanistic explanation, the honestly bounded positive, and the
demonstration that a small research program can be made to falsify itself,
to be worth more than the framework was.

---

## Data availability

All raw runs, episode records, frozen configurations, environment manifests,
and SHA-256 manifests: `artifacts/g1/E0-G1-v1/development/run_30526724307/`
(Gate G1) and `artifacts/wp6/E0-WP6-RELMEM-v1/` (final experiment) in the
public repository. Evidence ledger: `docs/E0_EVIDENCE_LEDGER_v1.json`.
Closure record: `docs/E0_G1_CLOSURE_v1.md`.
