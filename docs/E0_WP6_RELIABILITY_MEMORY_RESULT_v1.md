# WP-6 — Reliability Memory Decision Experiment, Result v1

**Protocol:** `E0-WP6-RELMEM-v1` (frozen 2026-08-05, user-approved before
implementation)

**Work package:** WP-6.2 (C338)

**Execution commit:** `16929d4e9926f610f723264b155fc08b9c6be884` (C337)

**Verdict: PASS — `lean/reliability_memory` continues as a maintained
library**, with one mandatory documentation note (below).

## Provenance

- Object under test: `lean/reliability_memory` bound by SHA-256
  (store/traces/primitives); `verify_object_under_test()` passed before
  execution. Shipped defaults, no tuning.
- 360/360 replicates (3 regimes × 4 arms × 30 paired seeds × 1,000 calls),
  executed locally and deterministically; a verification re-run produced
  byte-identical `raw_runs.jsonl` and `summary.json`.
- Artifacts with SHA-256 manifest: `artifacts/wp6/E0-WP6-RELMEM-v1/`
  (`raw_runs.jsonl`
  `6074669d27e9bec0a35bb5bb369f499dba90591601e176227b8cec6b309a56ef`,
  `summary.json`
  `1aa81fbd06a87a674954a0bec3692adb78f7fabba5de2ad9822f288af6075a68`).
- Note: the first run recorded a hand-assembled execution-commit string with
  one wrong character; it was regenerated from `git rev-parse HEAD` with
  outcome files verified byte-identical. Only `manifest.json` changed.

## Results (primary metric: completed tasks per 1,000 calls)

| Regime | MEMORY | NO_MEMORY | STICKY | ORACLE |
|---|---:|---:|---:|---:|
| R1 persistent | **125.9** | 85.1 | 122.8 | 153.3 |
| R2 drift | **124.2** | 80.9 | 118.3 | 148.0 |
| R3 context | 85.0 | 76.9 | **105.2** | 139.3 |

Paired comparisons (30 paired seeds, 10,000-resample bootstrap, seed
20260805):

| Comparison | Difference | 95 % CI | Relative lift |
|---|---:|---:|---:|
| R1: MEMORY − NO_MEMORY | +40.9 | [+35.3, +46.8] | **+48.0 %** |
| R1: MEMORY − STICKY | +3.2 | [+1.4, +4.9] | +2.6 % |
| R2: MEMORY − NO_MEMORY | +43.3 | [+37.0, +49.6] | +53.5 % |
| R2: MEMORY − STICKY | +5.9 | [+3.9, +8.0] | +5.0 % |
| R3: MEMORY − NO_MEMORY | +8.1 | [+5.4, +10.9] | +10.5 % |
| R3: MEMORY − STICKY | −20.2 | [−24.1, −16.5] | −19.2 % |

## Criteria (frozen §7)

1. **R1 vs. NO_MEMORY:** CI lower bound > 0 and lift ≥ 10 % → **pass**
   (+48.0 %).
2. **R1 vs. STICKY:** CI lower bound > 0 → **pass** (+2.6 %). Point lift
   < 5 % → the **mandatory documentation note** applies: *a stateless
   sticky heuristic captures most of the value in stationary regimes; the
   library documentation must say so.* (Applied in C338 to
   `lean/E0_LEAN_CORE.md` and the README.)
3. **R2/R3 non-inferiority vs. NO_MEMORY:** both regimes non-inferior →
   **pass** (both CIs entirely positive). No permanent warning required.

**Verdict: PASS.**

## Honest findings beyond the gate

- **The library's real differentiator is drift robustness.** Under drift
  (R2) memory beats even the sticky heuristic with the CI clear of zero
  (+5.9 [+3.9, +8.0]): decaying traces recover from redrawn reliabilities;
  a last-success pointer does not. In the purely stationary R1 the sticky
  heuristic captures most of the achievable value.
- **Context keys matter.** In R3 the context-*keyed* sticky heuristic beats
  the context-*free* memory by 19.2 %. This is a usage finding, not a
  library defect: the preregistration deliberately ran the store with
  step-type-only keys. Users whose tool reliability varies by task context
  should include that context in the state key. Recorded as documentation
  guidance; changing defaults or re-running with richer keys would require
  a protocol v2.
- The oracle gap (memory reaches ~82–84 % of oracle throughput in R1/R2)
  bounds what any memory can add here.

## Consequence

Per the preregistered decision rule, the closure arc ends in the
**maintained-library** branch: `lean/reliability_memory` remains a small,
documented, maintained tool with these scoped claims — persistent failure
memory beats memoryless selection everywhere tested (+48 to +54 %), beats a
sticky heuristic modestly in stationary and clearly in drifting regimes,
and must be keyed with task context where reliability is
context-dependent. Nothing here revives any Gate-G1 claim.
