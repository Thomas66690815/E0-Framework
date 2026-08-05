# E₀ Gate G1 — Closure Record v1

**Work package:** C333 (closure arc, step 1)

**Date:** 2026-08-05

**Decision authority:** user decision of 2026-08-05 ("Wir machen den
Abschlussbogen"), taken after review of the complete development evidence and
the explicit alternative of a one-time holdout run.

## Decision

Gate G1-v1 is **CLOSED-NEGATIVE on development evidence**. The protected
holdout (generator seeds 1000–1029) was never instantiated or read and remains
**permanently unopened** for protocol `E0-G1-v1`. No holdout PASS/FAIL exists
or will exist for this protocol version; the closure is a strategic decision
grounded in development diagnostics, not a formal preregistered gate outcome.

Basis (all retained under `artifacts/g1/E0-G1-v1/development/run_30526724307/`
and reported in `E0_G1_DEVELOPMENT_RESULT_v1.md`):

1. **G1-A (geometry value):** `E_FULL_GEOMETRY` minus `A_HIST` is exactly 0.0
   in every family and overall. C331 established the mechanism: the lookahead
   is causally inactive at the action boundary. A holdout run cannot change a
   mechanism that never fires.
2. **G1-B (historization competitiveness):** `A_HIST` scores 0.208 against
   0.407 for the fair baseline median (−0.199, 95 % CI [−0.206, −0.192]);
   one of four families meets the preregistered bar where three are required.
3. The expected information value of the ~4,680-replicate holdout run is
   below its cost for every pending strategic decision: every consequence
   below follows identically from the development evidence alone.

## Consequences (binding for this repository)

- **P4b — research freeze for geometry.** `lean/structural_geometry` and the
  amplitude/phase/interference stack in `e0_controller` are frozen as research
  artifacts: kept importable and tested for reproducibility, no further
  development, no product claims. The C319 finding (interference constructive
  at typical weights) and C331 (mechanism neutrality) stand as the final word.
- **WP-2.5 (held-out BPI2017 validation) is closed unexecuted.** Without a
  competitive development result there is no claim left for it to validate.
- **Override-Gate v2 is permanently parked.** The WP-GATE-0.11–0.15 execution
  layer remains in the repository as engineering evidence behind its
  authorization boundary. No execution commit will be declared, no
  authorization created, and no calibration dispatched under this closure.
- **F3/F4 structural limits are final for this repository.** The confirmed
  branching (b≥3) and non-Markov limits are reported honestly in the closure
  paper; no engineering-around work is planned.
- **No G1-v2.** A successor gate would require a new hypothesis worth testing;
  none is currently held.

## What survives the closure

- `lean/reliability_memory` — historization as a small, training-free,
  explainable failure-memory. Its remaining product hypothesis (an LLM agent
  with persistent tool-reliability memory outperforms the same agent without
  one) is *not* addressed by G1-B, whose comparator was fairly trained RL
  under generous adaptation budgets. This hypothesis gets exactly one
  preregistered decision experiment (closure arc, WP-6.x); its outcome decides
  between "small maintained library" and "full archive".
- The negative result itself, the preregistration/ledger/audit methodology,
  and the complete raw evidence — the subject of the WP-5.2 closure paper.
- The `wall_grid` family win (+0.260 over the baseline median) as the honest,
  narrow statement of where edge-local failure memory helps: trap-heavy,
  wall-structured domains with persistent dead ends.

## Closure arc plan

| Step | Content | Commit |
|---|---|---|
| 1 | This closure record; governance state updated | C333 |
| 2 | WP-5.1 — README claims-to-ledger rewrite; reposition lean packages as lightweight, explainable, training-free alternatives with documented trade-offs; AGI blueprint to `_archive` | C334 |
| 3 | WP-5.2 — short closure paper: historization mechanism, F3/F4 limits, G1 design and negative result (submission is a USER DECISION) | C335 |
| 4 | WP-6.1 — preregister the final reliability_memory decision experiment | C336 |
| 5 | WP-6.2 — execute it after user review of the preregistration | pending |

Interpretation boundary: nothing in this record upgrades any development
diagnostic to a holdout result, and nothing in it removes the retained
evidence. `holdout_accessed` remains false everywhere.
