# E₀ Documentation Priorities
## What should be documented now after the hybrid-controller milestone

**Status:** Working note  
**Date:** 2026-03-24  
**Language:** English  
**Purpose:** Identify the documentation that is now necessary after the transition from an analysis-only amplitude layer to an integrated hybrid controller architecture.

---

## 1. Why this note exists

The project has crossed an important threshold.

It is no longer enough to document:

- the canon,
- the deterministic controller,
- and the mathematical derivation path.

The repository now contains:

- an empirically compared summation-geometry layer,
- a hybrid controller mode,
- MemOS persistence of hybrid runtime state,
- LLM-visible overlay summaries,
- and demo-level integration across multiple application domains.

This means the central documentation task has changed.

We now need to document not only **what E₀ is**, but also:

- what the system actually does,
- which parts are derived vs empirical vs heuristic,
- when the hybrid layer intervenes,
- what remains open,
- and how the project can be falsified.

---

## 2. The five documentation blocks that now matter most

### D1 — Current architecture overview

A concise document that explains the actual current stack:

```text
Canon
→ deterministic controller
→ amplitude overlay
→ summation geometry
→ hybrid arbitration
→ MemOS persistence
→ LLM demo integration
```

This should be the first technical orientation document for any serious reader.

---

### D2 — Derived vs empirical vs heuristic map

This is now essential.

We should explicitly classify every major subsystem or claim into one of three buckets:

- **Derived** — follows from the current formal chain
- **Empirical** — discovered by tests or comparisons
- **Heuristic / operational bridge** — works in runtime, not yet derived

Examples:

- `S = Δ · R_eff` → derived
- `simple` as default summation geometry → empirical
- escalation policy / some controller overlays → heuristic / operational bridge

Without this map, readers will over-assume closure.

---

### D3 — Hybrid mode specification

A dedicated document should define exactly:

- GREEDY mode
- AMPLITUDE_ON_DISAGREE mode
- override conditions
- safety conditions (e.g. escalation not overridden)
- what metrics mean (`hybrid_override_count`, `hybrid_override_rate`)
- what the hybrid mode is claiming operationally

This should be treated as a first-class spec, not scattered across commits.

---

### D4 — Evidence and falsification status

A compact research-status note should state:

- which key findings are now empirically supported,
- which ones are geometry-stable,
- which ones remain open,
- and what specific tests would falsify current claims.

This is especially important now that the project is entering a real validation phase.

---

### D5 — External handoff package

For external systems and reviewers, the minimum package should now be curated explicitly.

Recommended contents:

1. README top pitch
2. example walkthrough
3. summation geometry comparison
4. one criticism / audit note
5. one current-state / milestone note

This should be maintained intentionally, not left implicit.

---

## 3. Recommended priority order

### Priority 1 — Immediate

1. **README update**
2. **Hybrid mode specification**
3. **Derived / empirical / heuristic map**

These three are the minimum needed to prevent misunderstanding of the current system.

### Priority 2 — Very soon after

4. **Architecture overview**
5. **Evidence / falsification status note**

These are the documents that make the project reviewable.

### Priority 3 — Ongoing

6. **External handoff package maintenance**
7. **Per-milestone summary notes**

These keep the project intelligible as it keeps moving.

---

## 4. Recommended concrete document set

The following new or updated documents would cover the current need well.

### 4.1 Update

- `README.md`

### 4.2 New

- `docs/E0_HYBRID_CONTROLLER_SPEC_v1.md`
- `docs/E0_DERIVED_EMPIRICAL_HEURISTIC_MAP_v1.md`
- `docs/E0_ARCHITECTURE_OVERVIEW_v1.md`
- `docs/E0_EVIDENCE_AND_FALSIFICATION_STATUS_v1.md`

### 4.3 Maintain

- `docs/E0_SUMMATION_GEOMETRY_COMPARISON_v1.md`
- `docs/E0_EXTERNAL_VALIDATION_AND_HANDOFF_NOTE_v1.md`
- `docs/README_TOP_PITCH_v1.md`
- `docs/README_EXAMPLE_WALKTHROUGH_v1.md`

---

## 5. What should be stated explicitly now

At this stage, the documentation should explicitly say all of the following.

### 5.1 What has genuinely changed

The repository no longer contains only a deterministic controller.  
It now contains a hybrid architecture in which amplitude-based path-family support can override greedy local choice.

### 5.2 What is still open

At least these remain open:

- full derivation status of the chosen summation geometry,
- scalable amplitude aggregation beyond explicit bounded enumeration,
- phase / `Θ` derivation robustness,
- relationship between hybrid mode and full Born-style semantics.

### 5.3 What is already strong

At least these are now strong enough to say plainly:

- trap-correction is empirically demonstrated,
- summation geometry comparison has been performed,
- `simple` is currently the strongest default geometry,
- hybrid overrides are real and measurable,
- the architecture is integrated into MemOS and demos.

---

## 6. One-sentence documentation rule going forward

For every major new capability, always document:

> what it is, why it exists, what evidence supports it, and what would falsify it.

This should be treated as part of the architecture, not as optional writing.

---

## 7. Final recommendation

If only three documents can be written next, they should be:

1. `README.md` refresh
2. `E0_HYBRID_CONTROLLER_SPEC_v1.md`
3. `E0_DERIVED_EMPIRICAL_HEURISTIC_MAP_v1.md`

Those three would make the current system understandable again at the new level of complexity.

---

## End of Note
