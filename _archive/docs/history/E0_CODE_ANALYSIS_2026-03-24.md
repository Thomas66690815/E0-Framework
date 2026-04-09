# E₀ Runtime Code Analysis — 2026‑03‑24

**Status:** Read-only review (no code changes)  
**Purpose:** Summarise the current implementation state of the controller/amplitude/hybrid stack before making further changes.  
**Scope:** Controller workflow, amplitude overlay & geometry handling, persistence/reporting, and existing tests/tools.

---

## 1. Controller & Hybrid Pipeline

**Files:** `e0_controller/controller.py`, `docs/E0_HYBRID_CONTROLLER_SPEC_v1.md`

Observed behaviour:

- `cycle()` calls `select_hybrid()`; hybrid mode is effectively a wrapper around `select_next()`.  
- In `HybridMode.GREEDY`, the path is identical to the legacy controller.  
- In `AMPLITUDE_ON_DISAGREE`, `_compute_overlay()` (horizon = `hybrid_horizon`, default 3) runs every decision unless the step is escalated. This matches the spec’s rule “do not override escalations”.
- Overrides only fire when the amplitude choice differs from greedy _and_ the action is currently admissible. The `hybrid_overridden` flag propagates into `StepResult` → `RunTrace` → evaluation metrics.
- Metrics `hybrid_override_count` / `hybrid_override_rate` are computed inside `RunTrace.metrics()` and surfaced through `evaluation.py`.

Potential follow-ups:

- Controller exposes a single global `hybrid_horizon`. Future geometry experiments might require per-domain horizons or dynamic adjustment hooks.
- Override decisions do not (yet) incorporate geometry confidence or phase diagnostics; they are binary. Any future “partial override” logic would need a new data channel.

---

## 2. Amplitude Overlay & Summation Geometry

**Files:** `e0_controller/amplitude_overlay.py`, `docs/E0_SUMMATION_GEOMETRY_COMPARISON_v1.md`

Key points:

- `_enumerate_continuations()` implements the three geometries described in the comparison note:
  - `prefix`: include every prefix path up to `horizon_edges`.
  - `simple`: skip states already in `path` (no repeats).
  - `first_arrival`: stop once a goal is reached (requires `goals` set).
- Default geometry is `"simple"`. `HybridMode` currently hardcodes this via `_compute_overlay` (no CLI/config switch yet).
- `analyze_controller_state()` ensures each action has at least the direct `[current, action]` path to avoid missing-data artefacts.
- Path amplitude sums use `psi_total = Σ exp(-S(p)) exp(iΘ(p))`. Any issues with `Θ` derivation feed straight into intensity calculations.

Potential follow-ups:

- Geometry selection is still an argument to `_compute_overlay` but never varied by the controller; hooking it to a config flag would simplify experiments.
- Path enumeration is DFS with branching factor `k` and depth `h` → O(k^h). For larger domains we will need pruning or sampling.
- No instrumentation yet for measuring phase shifts or verifying `simple` vs `prefix` within live runs.

---

## 3. Persistence, Evaluation, Reflection

**Files:** `e0_controller/memory_os.py`, `e0_controller/evaluation.py`, `e0_controller/reflection.py`

Findings:

- MemOS snapshots now store `hybrid_mode`, `hybrid_horizon`, `hybrid_goals` (lines 185–187) and restore them when rehydrating a controller. Snapshot summaries include overlay data when hybrid mode is active (`summarize_for_llm` pulls hybrid metrics for current neighbors).
- Evaluation (`RunEvaluation`) captures `hybrid_override_count`/`rate`, warns when override rate >50%. Scenario-level reports print hybrid stats when any overrides occurred.
- Reflection layer does not yet look at hybrid metrics explicitly; reflection decisions still hinge on goal/efficiency/loop/semantic criteria. Hooks would be needed to reflect on “overrides too frequent” or “phase disagreement recurring”.

Potential follow-ups:

- MemOS currently stores geometry implicitly (through overlay snapshots). Explicit field for `geometry` would simplify diffing between runs.
- Reflection triggers could use override data (e.g., “quality reflection if override_rate > x and progress still low”).

---

## 4. Tests & Tools

Relevant suites:

- `e0_controller/test_amplitude_overlay.py` — unit tests for overlay enumeration, ψ sums, geometry edge cases.
- `e0_controller/test_phase2_minidomain.py` / `test_phase2_invoice.py` — structural maths + domain behaviours, but still primarily greedy-mode.
- `test_evaluation.py`, `test_memory_os.py` — cover new metrics & persistence, though more hybrid-specific fixtures could be added (e.g., verifying override count round-trips through MemOS).
- Demos (`demo_* --hybrid`) + `validate_cross_domain --hybrid` serve as manual/system tests; logs in `memos/runs/` now record override metrics.

Potential follow-ups:

- Automated “trap benchmarks” and geometry stress tests (as suggested in `E0_EVIDENCE_AND_FALSIFICATION_STATUS_v1.md`) are not yet coded; would likely sit under `tests/` or a new `tools/benchmark/` folder.
- No regression tests yet for phase perturbations; would require fixtures manipulating `Θ`.

---

## 5. Hook Points for Future Work

| Area | Hook point |
|------|------------|
| Verdichtungssnapshots | `RunTrace` / `MemOS` snapshot logic — add structured summaries per step |
| Inline reflection | `controller.cycle()` before `StepResult` return — opportunity to log “self-corrections” |
| Geometry switching | CLI/config → pass geometry into `_compute_overlay` via controller init |
| Hybrid metrics | Extend `Evaluation`/`Reflection` to consider override cause, not just count |

---

This document intentionally records **observations only**. No code was changed during this analysis.
