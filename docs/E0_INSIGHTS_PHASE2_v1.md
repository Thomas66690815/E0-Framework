# E₀ — Insights Phase 2

**Status:** Reflective Synthesis  
**Date:** 2026-03-27  
**Scope:** Commits `f2782d5` through `c41a0ff` (ProvenanceLog → C37b Reflection in Iterate Loop)  
**Test count:** 1483 (from 1138 → +345 tests, +30%)  

---

## 0. What This Is About

This document captures the insights that emerged since the last comprehensive review (`E0_CODE_ANALYSIS_2026-03-26.md`, test count 1138).  It is not a code analysis — it is an **insight synthesis**.

Phase 1 (the first 7 days) built the machine: Controller, Amplitude Overlay, SU(2), Curvature, Evaluation, Reflection, Self-Tuning, Born Regime, MemOS, LLM Adapter.

Phase 2 **used** the machine — and in doing so, understood what it actually does.

---

## 1. The Three Domains

### 1.1 Package Insert (Domain 1)

The first real-world domain — a medical package insert, LLM-parsed into a Landscape with 8 states and 10 edges.  This is where the **Mass Trap** was discovered: The amplitude overlay produces constructive interference at the NEBENWIRKUNG (side effect) node because path families branch there.  The controller cycles; greedy mode escapes.

Insight: The phenomenon is **amplitude-structural**, not graph-structural.

### 1.2 ECB Interest Rate Decision (Domain 2)

ECB monetary policy with 11 states and 16 edges.  Three scenarios:

1. **Inflation control:** INFLATION_HOCH → PREISSTABILITAET (straightforward, rate hike required)
2. **Recession with multi-goal:** REZESSION → {WACHSTUM, PREISSTABILITAET} (first real multi-goal application)
3. **Stagflation as Gordian Trap:** STAGFLATION has three exits, all with high resistance — a genuine trap, not an artificial deadlock

**Key insight:** The Mass Trap also occurs here.  INFLATION_HOCH → STAGFLATION produces the same constructive interference as NEBENWIRKUNG in the package insert.  Greedy escapes, amplitude cycles.  `path_count_imbalance > 3.0` confirms the pattern cross-domain.

→ **The Mass Trap is not a domain artifact.  It is a structural phenomenon of the amplitude overlay.**

### 1.3 Burnout Composite (Domain 3)

Five source fragments (economic, psychological, journalistic, first-person account, autofictional) are combined.  The landscape is for the first time **entirely LLM-generated** — no pre-designed graph.

The LLM typically produces 11–13 states, 14–17 edges, with feedback loops (LOOP_UNRESOLVED → REFRAMING_NEEDED) and error recovery paths.  Graph quality is 0.97–1.00.

**Key insight:** The LLM-generated topology is structurally sound.  The controller engine navigates it cleanly.  But the controller consistently chooses the shortest path to the goal and **ignores** unvisited branches (first-person account, autofiction, error recovery).  Those branches retain their full tension.

→ **The controller optimizes locally correctly but does not fully utilize the landscape.  This is not a bug — it is a structural characteristic that only becomes visible through residual tension measurement.**

---

## 2. The Five Structural Insights

### Insight 1: The Mass Trap Is Cross-Domain

| Domain | Trigger Node | Imbalance | Behavior |
|---|---|---|---|
| Package insert | NEBENWIRKUNG | > 3.0 | Amplitude cycles, greedy escapes |
| ECB | INFLATION_HOCH → STAGFLATION | > 3.0 | Amplitude cycles, greedy escapes |

**Mechanism:** When a node receives significantly more path families than others (due to topological branching), constructive interference arises.  This interference is correctly computed — it reflects actual structural dominance.  But the resulting decision can be pathological: the controller follows the interference into a cycle.

**Solution:** The Mass Trap Detector identifies `path_count_imbalance > 3.0 + repeated_cycles > 0` and **inverts** the self-tuning response: instead of increasing the horizon (which amplifies the interference), it is reduced.  Simultaneously, `confidence_threshold` rises to make amplitude override harder.

**Why this matters:** This is not a heuristic — it is a principled correction.  The diagnosis (imbalance) and the therapy (horizon inversion) follow from the same structural argument.

### Insight 2: Domains Before Schema

During the schema review (v0.1), a decision was needed: should the schema drive implementation, or should real domains inform the schema?

**Decision:** Domains → Schema.

| Component | Status |
|---|---|
| Core (E0Envelope, TransportRegime) | ✅ implemented (48 tests) |
| Ingress (Parsing, Proposal) | ⏳ waiting for 2–3 domain comparison |
| Reflection (pre-decision gate) | ⏳ waiting for concrete mechanisms |
| Egress (Output, Integration) | ⏳ waiting for first integration target |

**Rationale:** Premature standardization risks freezing the wrong abstractions.  Better: build three real domains (Package insert ✅, ECB ✅, Burnout ✅), then compare what was actually the same.

→ **The domains have different ingress paths but identical core mechanics (tension, interference, mass trap).  The schema must capture this asymmetry.**

### Insight 3: Iteration as Tension Carrier

The most important conceptual insight of this phase.

**Starting question:** How many iterations does a problem need?

**Wrong answer:** "We prescribe it" (max_iterations=5).

**Right answer:** "It emerges" — from the tension structure of the landscape.

The insight came from the discussion about the Continuum: *"In iterations, one must endure tensions and carry them into the next iteration."*  This is exactly Axiom A₀ at the iteration level:

> **Rest requires explanation. Change does not.**

When residual tension between iterations does not change (stagnation: `|Δmean| < 0.02`), that requires explanation — it is not normal.  When it changes, the process continues.

**The ResidualTensionMap** makes this operational:

- **Before the run:** `snapshot_tensions()` — S_eff of every edge
- **After the run:** `compute_residual_map()` — what changed?
- **Decision:** `should_continue()` — equilibrium, stagnation, or continue?
- **Reflection:** On stagnation or amplification → `reflect()` fires

The iterate loop is not a retry mechanism.  It is a **tension processor**.  Each iteration transforms the landscape (through historization), and the residual tension shows whether that transformation leads to rest or generates new tension.

### Insight 4: Reflection Closes the Loop

Phase 1 had reflection as **post-run diagnostics**: Was the run good?  What went wrong?  Recommendation for next time.

Phase 2 made reflection an **active part of the iterate loop**:

```
run → measure → reflect → next iteration (or stop)
```

The two-stage filtering is important:

1. **Iterate level:** `verdict.should_reflect` is a hint ("there is reason to reflect")
2. **Reflection level:** `reflect()` decides whether conditions actually warrant a report

This means `should_reflect = True` can fire (because stagnation was detected), but `reflect()` may produce no report (because the run had an A-rating and the reflection layer finds no trigger).  Or conversely: on the final stop, reflection is *always* attempted — but only when there is a genuine finding does a report appear.

**Observations from live demos:**

| Stop Reason | Reflection Type | Content |
|---|---|---|
| Stagnation (Burnout, mock) | opportunity | "A-rated run, graph_design has potential" |
| Stagnation (Burnout, live) | opportunity | "High efficiency, unused branches" |
| Goal not reached | failure | "Goal not reached" + path analysis |

Reflection correctly distinguishes between "ran poorly" (failure) and "ran well, but more is possible" (opportunity).  This is the structurally correct diagnosis: the controller reached its goal, but the landscape offers more than it uses.

### Insight 5: Provenance as Result Chain

The ProvenanceLog creates something that was previously missing: **traceability**.

Six stages, gap-free:

```
InputRecord → LLMCallRecord → ProposalRecord → LandscapeRecord → RunRecord → EvaluationRecord
```

Each step has: timestamp, SHA256 fingerprint (input), raw data (LLM response), structured data (proposal, landscape, trace), evaluation.  The chain is serializable (`to_dict()/from_dict()`) and persistent (`save()/load()`).

**Why this matters:**

The system makes decisions based on LLM-generated landscapes.  Without provenance, it is impossible to trace why the controller chose a particular route — you only see the result.  With provenance, you see: which text was input → what the LLM made of it → how it was materialized → how the controller ran → how it was evaluated.

This is the prerequisite for any form of **audit, debugging, and trust**.

---

## 3. Architecture After Phase 2

```
┌─────────────────────────────────────────────────────────────┐
│                     Session.iterate()                        │
│  ┌────────┐   ┌──────────┐   ┌──────────┐   ┌───────────┐  │
│  │  run() │ → │ residual │ → │ verdict  │ → │ reflect() │  │
│  │        │   │ tension  │   │          │   │           │  │
│  └────────┘   │   map    │   │ continue │   │ failure   │  │
│       ↑       └──────────┘   │ stagnate │   │ quality   │  │
│       │                      │ equilib. │   │ opportun. │  │
│       │                      │ budget   │   │ structur. │  │
│       │                      └──────────┘   └───────────┘  │
│       │                                          │          │
│       └──────────────────────────────────────────┘          │
│                    (next iteration)                          │
└─────────────────────────────────────────────────────────────┘
         ↕                    ↕                    ↕
    Historization        TuningMemory         ProvenanceLog
    (edges learn)        (parameters learn)   (audit chain)
```

**New layers since Phase 1:**

| Layer | Phase 1 | Phase 2 |
|---|---|---|
| Iterate control | — | ResidualTensionMap, should_continue(), emergent iteration count |
| Inter-iteration reflection | — | _inter_iteration_reflect(), ReflectionReport between runs |
| Structural reflection | — | StructuralDiagnostic, rebuild_landscape(), REBUILD_LANDSCAPE_PROMPT |
| Configuration | kwargs dictionary | E0Envelope (frozen, typed, serializable) |
| Transport regime | `use_su2=True/False/"geometric"` | TransportRegime enum (U1, SU2_MINIMAL, SU2_GEOMETRIC) |
| Mass trap | Observed (package insert) | Detected + corrected (path_count_imbalance, horizon inversion) |
| Provenance | — | 6-stage result chain, input to evaluation |
| Domains | 1 (package insert) | 3 (+ ECB, + Burnout), cross-domain validated |

---

## 4. Open Items

### 4.1 The Controller Does Not Fully Utilize Landscapes

Observation from Domain 3: The controller finds the shortest path to the goal and ignores side branches.  The ResidualTensionMap shows this (unvisited hotspots), reflection diagnoses it (opportunity: graph_design), but **nobody acts on it**.

Next step: Reflection must have consequences — either the controller deliberately explores unvisited branches, or the landscape is restructured (C36 Structural Reflection has the tooling, but it is not called automatically).

### 4.2 Ingress Is Not Standardized

Three domains have three different ingress paths:
- Package insert: single text → LLM → landscape
- ECB: hand-designed graph (test fixture)
- Burnout: 5 fragments → assembled → LLM → landscape

What can be generalized is only clear after comparison.

### 4.3 Schema v0.2 Is Pending

The three domains now provide enough evidence for a second schema attempt.  In particular:
- Core block (E0Envelope) is stable
- Ingress block must accommodate the asymmetry of text→LLM vs. fixture
- Reflection block in the schema is a pre-decision gate; in code it is post-run diagnostics — this must be reconciled

### 4.4 Egress Is Entirely Missing

The system produces traces, evaluations, reflections, provenance — but there is no standardized output path.  No API endpoint, no UI format, no actuator interface.  This is deliberately deferred (schema decision), but it limits usability.

### 4.5 Automatic Landscape Repair

C36 provides `StructuralDiagnostic` and `REBUILD_LANDSCAPE_PROMPT`.  C37 detects stagnation.  But there is no automatic path from "stagnation detected" → "rebuild landscape" → "re-iterate".  That would be the next closure step.

---

## 5. Metrics

| Metric | Phase 1 (Day 7) | Phase 2 (Day 10) | Delta |
|---|---|---|---|
| Tests | 1138 | 1483 | +345 (+30%) |
| Test files | 29 | 40+ | +11 |
| Modules (e0_controller/) | ~22 | ~26 | +4 |
| Domains | 1 | 3 | +2 |
| Commits (phase) | 25 | ~15 | — |
| Live LLM tests | 0 (mixed) | 41 (separated) | Cleanly separated |
| Provenance chain | — | 6/6 stages | Complete |

---

## 6. Conclusion

Phase 1 showed that E₀ **works**: tension navigation, interference, Gordian traps, Born regime.

Phase 2 showed what E₀ **means**:

1. **The Mass Trap is real and cross-domain.**  It is not a bug but a structural phenomenon of amplitude interference that can be corrected on principle.

2. **Iteration is not retry.**  It is a tension process whose length emerges from the landscape.  Stagnation requires explanation; change does not.

3. **Reflection is not thinking about the run.**  It is part of the run — embedded between iterations, with concrete triggers and typed reports.

4. **Provenance makes decisions traceable.**  Without it, the controller is a black box; with it, an auditable decision chain.

5. **Schema follows evidence, not the other way around.**  Three real domains show: the core is stable; the rest must still find itself.

The machine runs.  Now it must learn to use what it sees.
