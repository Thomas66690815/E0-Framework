# WP-6 — Reliability Memory Decision Experiment, Preregistration v1

**Protocol ID:** `E0-WP6-RELMEM-v1`

**Work package:** WP-6.1 (C336)

**Date frozen:** 2026-08-05

**Status:** preregistered design; NOT implemented, NOT executed. Execution
(WP-6.2) requires prior user review of this document and a declared
execution commit.

**Object under test:** `lean/reliability_memory` exactly as of source commit
`2687a5e` (C335). The package may not be modified between this freeze and
the end of execution; any fix requires a v2 protocol.

## 1. Decision question

This is the last experiment of the E₀ program (see
`E0_G1_CLOSURE_v1.md`). It decides between two ends:

- **PASS → maintained library:** `reliability_memory` continues as a small,
  documented, maintained tool with scoped claims.
- **FAIL → full archive:** the repository is archived with its negative
  record complete.

**Hypothesis H1:** An agent that persists tool-reliability memory across
tasks completes more work per call budget than the same agent without
memory, in environments with *persistent structural tool failure* and no
training phase.

This hypothesis is not addressed by Gate G1 (whose baselines received
training budgets on navigation tasks). It matches the one positive G1
finding: failure memory wins where failure is persistent and structural
(`wall_grid`, +0.260).

## 2. Why no LLM in the loop

The object under test is the memory, not an agent's reasoning. An LLM in the
loop adds cost and variance without informing H1, and would turn a
reproducible decision experiment into a prompt-sensitivity study. The
experiment therefore uses a deterministic scripted agent. A post-decision
LLM demo is explicitly out of scope for the PASS/FAIL decision.

## 3. Environment (frozen)

A task is a sequence of 5 steps. Each step exposes k = 4 functionally
equivalent tools (redundant endpoints). A tool call either succeeds
(step completes) or fails (call is spent, step repeats). An episode budget
of 1,000 tool calls per replicate; tasks are processed until the budget is
exhausted.

Per-tool success behavior is seeded per replicate. Three regimes:

- **R1 — persistent structure (confirmatory):** per (step-type, tool),
  reliability is drawn once from {0.95, 0.6, 0.25, 0.05} (weights
  0.25/0.25/0.25/0.25) and never changes. The wall_grid analog.
- **R2 — drift (stress):** as R1, but at call 500 every step-type's tool
  reliabilities are redrawn. The nonstationary analog; memory may hurt here.
- **R3 — context dependence (stress):** as R1, but reliability depends on
  (task-type × tool) with 3 task types; a tool good for one type may be bad
  for another. Tests whether context-free memory misleads.

Environment RNG and agent RNG are separate; all seeds preregistered:
generator seeds 0–29 per regime, environment outcome seed = 400000 + seed,
agent seed = 500000 + seed.

## 4. Arms (frozen)

| Arm | Behavior |
|---|---|
| `MEMORY` | `ReliabilityStore` persisted across all tasks of a replicate; choose `recommend()`; on cold start uniform random; `observe_edge()` after every call |
| `NO_MEMORY` | uniform random among the k tools at every attempt |
| `STICKY` | keep using the tool that last succeeded for this step-type; on failure switch uniformly at random; no decay, no store (the embarrassing cheap competitor) |
| `ORACLE` | knows true current reliabilities, always picks the best tool (upper reference, excluded from the comparator) |

State key for `MEMORY` and `STICKY`: step-type identifier in R1/R2;
(task-type, step-type) in R3 for STICKY, while MEMORY is run **context-free
(step-type only)** in R3 — deliberately, to test the library as shipped.

## 5. Metrics (frozen)

- **Primary:** completed tasks per 1,000 calls.
- **Secondary:** wasted calls on tools with true reliability ≤ 0.25;
  post-drift recovery (calls from drift until rolling success rate over 50
  calls returns to within 90 % of the pre-drift level; R2 only).

## 6. Statistics (frozen)

Per regime: 30 paired replicates (same environment seeds across arms).
Paired bootstrap over replicates, 10,000 resamples, bootstrap seed
20260805, two-sided 95 % percentile intervals, relative lift =
(MEMORY − comparator) / comparator on the primary metric.

## 7. Decision criteria (frozen)

**PASS requires all of:**

1. R1: MEMORY beats `NO_MEMORY` with CI lower bound > 0 **and** relative
   lift ≥ 0.10.
2. R1: MEMORY beats `STICKY` with CI lower bound > 0. No minimum lift —
   but if the point lift over STICKY is < 0.05, the library documentation
   MUST state that a stateless sticky heuristic captures most of the value.
3. R2 and R3: MEMORY is non-inferior to `NO_MEMORY` (CI lower bound of the
   difference > −0.05 × NO_MEMORY mean). A regime that fails non-inferiority
   but stays above −0.20 × NO_MEMORY mean does not fail the gate, but the
   corresponding warning becomes a mandatory, permanent part of the
   library's README.

**FAIL** otherwise. In particular: losing to STICKY in R1 is a FAIL —
if a one-line heuristic beats the library, the library has no reason to
exist.

**No tuning after data:** `ReliabilityStore` runs with its shipped defaults.
If defaults fail, the result is FAIL; a retuned variant would need a v2
protocol and fresh seeds.

## 8. Execution plan (WP-6.2, after user review)

1. User reviews this preregistration; any change before implementation
   produces v1.1 with a labeled changelog.
2. Implement harness + no-outcome contract tests (deterministic replay,
   seed separation, arm isolation, budget accounting) in `e0_controller/`;
   the lean package itself is not touched.
3. Declare the execution commit; run all 3 × 30 × 4 = 360 replicates
   locally (estimated minutes, not hours; no CI matrix needed); write
   atomic per-replicate artifacts and a consolidated summary with SHA-256
   manifest under `artifacts/wp6/E0-WP6-RELMEM-v1/`.
4. Report PASS/FAIL with all numbers, update the Evidence Ledger
   (`E0-WP6-RELMEM-001`), and execute the corresponding closure end.

## 9. Interpretation boundary

- This experiment tests the shipped library under its intended usage
  pattern, not E₀ navigation. It cannot revive any G1 claim.
- A PASS supports exactly one sentence: "persistent failure memory beats
  memoryless and sticky selection under persistent structural tool failure,
  and is safe (or explicitly caveated) under drift and context shift."
- Simulated Bernoulli tools are a model of persistent endpoint failure, not
  evidence about any specific production system.
