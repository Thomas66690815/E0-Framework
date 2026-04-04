# E0 Integration Stories v1

**Status:** Draft — integration planning  
**Date:** 2026-04-04  
**Origin:** Initial analysis by Codex, reviewed and revised with Copilot  
**Scope:** Identify how underused capabilities become first-class runtime features.  
**Out of scope:** UI polish, parameter tuning minutiae.

---

## 1. Purpose & Method
- Enumerate high-value subsystems that currently exist but remain dormant outside of tests or exploratory scripts.
- Describe an integration story per subsystem: trigger surface, runtime path, instrumentation, and open questions.
- Provide a checklist to convert stories into backlog items later.

| Layer | Capability | Current Usage | Integration Story Goal |
|-------|------------|---------------|------------------------|
| **Dream Mode (Hungarian+WL)** | WL fingerprints + Hungarian optimal assignment (C135–C138) | Explore scripts only; DreamObserver still uses old Edge-EQ (C109) | Upgrade DreamObserver.dream_cycle() to use Hungarian+WL matcher. **Primary integration target.** |
| LLM Bootstrap | Bootstrapper: LLM scores → Landscape (C44, C134) | Only in explore_c134_bootstrapper_teacher.py | Standalone demo: LLM evaluates a new domain → ready Landscape, no manual spec. |
| Structural Entropy & Sleep–Wake | Inscription thresholds, decay, dream pressure | Only in explore_language_learning.py | Let standard demos opt into entropy + sleep-wake so forgetting/dream metrics show up in logs. |
| Multiverse | Coupling, NoveltyGate, divergence pressure | Language-learning exploration and benchmarks only | Turnkey multiverse run with cross-domain dream discovery post-C139. |
| Reflexion | Self-Graph → Integrated Reflexion pipeline | Exercised in tests, not in live runs | Embed reflexion cycles into a standard Session. Mutation policy needs design. |
| Curriculum | CurriculumRunner, EquilibriumDetector (C123) | Tested, never used in any demo | Curriculum-driven demo on ontodynamics canon, showing level-by-level learning. |
| Field Theory | SU(2) multi-axis transport & resonator modulation | Only via unit tests / explore_* scripts | Reference demo + envelope preset. Low urgency — no practical advantage demonstrated yet. |
| Observation/UI | Observation controller, FastAPI service, Cytoscape client | Existing UI code, not linked in quickstart | Reproducible "observe any session" workflow with CLI + browser steps. |

---

## 2. Story Templates
Each story follows the same skeleton:
1. **Trigger Surface:** Code change, CLI flag, envelope preset, or API endpoint.
2. **Runtime Path:** Modules/functions that should execute.
3. **User-Facing Evidence:** Logs, reports, artifacts, or UI views proving the feature ran.
4. **Instrumentation & Tests:** Existing coverage leveraged + gaps to fill.
5. **Open Questions:** Design decisions still unresolved.

---

## 3. Prioritized Stories

### Priority 1 — DreamObserver + Hungarian (C139) ✅ DONE

**Problem:** `DreamObserver.dream_cycle()` (C110) uses edge-fingerprint equivalence detection from C109 — comparing per-edge (q,m,I) tuples with quantile thresholds. This gave ~2% accuracy on language canons. Meanwhile, C137 proved that WL+Hungarian achieves 100% (44/44), validated robust to noise (C138a), score perturbation (C138b), and scaling to 500 nodes (C138c). The proven algorithm sits in explore scripts. The runtime uses the obsolete one.

**Resolution (commit `998f1f6`, 2026-04-04):**
- `DreamObserver.__init__`: new `node_equivalence_method` param (None/`"hungarian"`/`"wl"`), `wl_depth` (default 2), with validation
- `DreamCycleResult`: +`node_equivalences_found`, +`node_equivalences_new` fields
- `dream_cycle()`: node-EQ step runs **after** edge-EQ for each domain pair — layered approach (both coexist)
- `_update_dream_landscape_nodes()`: creates `"domain:node"` states in Dream Landscape, bidirectional edges with confidence-scaled resistance
- `_node_equivalence_state()`: helper encodes NodeFingerprint as `"domain:node"`
- Backward compatible: `node_equivalence_method=None` (default) preserves all existing behavior
- 10 new tests in `TestNodeEquivalenceIntegration` (3540 total, was 3530)

**Open Questions Resolved:**
- Edge-EQ + node-EQ both run (layered, not replacement) — edge-EQ is cheap, node-EQ is thorough
- Node states coexist with edge states in the same Dream Landscape using different encoding (`domain:node` vs `domain:src→tgt`)
- Same `_known_edges` deduplication prevents re-adding across cycles

---

### Priority 2 — Bootstrapper Demo (C140) ✅ DONE

**Problem:** The Bootstrapper (C44) + LLM Teaching (C134) pipeline is proven but buried in explore scripts. A user cannot easily create a new domain Landscape from an LLM evaluation.

**Resolution (commit pending, 2026-04-04):**
- `demo_bootstrap_domain.py` — complete cold-start demo with two paths:
  - Path A: LLM designs topology from natural-language description (`propose_and_bootstrap`)
  - Path B: Load JSON spec + bootstrap directly
- Built-in mock spec (9 states, 10 edges, onboarding domain) — runs without API keys
- 4-phase output: Landscape Creation → Mode Analysis → Navigation → Post-Navigation Mode
- Shows confidence scaling, inertia dampening, mode transitions
- CLI: `--live` for real LLM, `--task` for custom, `--spec` for JSON file
- 6 smoke tests in `test_demo_bootstrap.py` (3546 total)

**Key insight demonstrated:** Bootstrapper creates skeptical traces (confidence-scaled U/F), E₀ navigates immediately but inertia dampening keeps it cautious until real experience accumulates.

---

### Priority 3 — Entropy/Sleep–Wake in Standard Demos ✅ DONE

**Problem:** Structural entropy (C114–C121) — inscription thresholds, decay, dream pressure, and sleep-wake orchestration — existed only in explore scripts and tests. Standard demos had no way to show forgetting/consolidation metrics.

**Resolution (commit pending, C141):**
- `demo_bootstrap_domain.py` extended with `--entropy` flag and `use_entropy` parameter
- Phase 3: `E0Controller(inscription_threshold=True)` — tracks inscribed vs skipped transitions
- Phase 3 output: T_s, dream_pressure, inscription count
- New Phase 5: `SleepWakeCycle` with `DreamObserver(decay_enabled=True)`, 3 episodes
- Output: per-episode T_s dynamics, wake/sleep transitions, anchor analysis, decay candidates
- `protected_fn` protects start + goal states from decay
- 7 new tests in `TestBootstrapDemoEntropy` (13 total in file, was 6)

**Key observations from demo run:**
- 6/7 transitions skipped by inscription threshold (high trace_load from bootstrap → high ε)
- T_s = 24.28, pressure = 0.83 → immediately triggers dreaming
- Single-domain demo: decay requires dormancy, so no structural pruning in short run
- All anchors/candidates analysis visible in output

**Open Questions Resolved:**
- Default θ = 0.5 (standard theta_base), μ = 5.0 (system-wide)
- Safety: `protected_fn` prevents start/goal removal; short demos don't produce dormant states anyway

**Effort:** Small. Flag + wiring, no new algorithms.

---

### Priority 4 — Multiverse Quickstart

**Trigger Surface:** Dedicated `demo_multiverse_invoice.py` or flag `--multiverse 2` on existing demos.

**Runtime Path:**
- `MultiverseController(Universe A, Universe B)` with `cross_reflexion_turn` as turn fn.
- Post-run: DreamObserver with Hungarian (after C139) discovers structural correspondences between the two universes.

**Why after C139:** Multiverse becomes much more compelling when DreamObserver can actually find meaningful cross-domain matches. With old edge-EQ this was noise.

**User Evidence:** Summary table: novelty rate, peer consultations, edges via cross-reflexion. Dream report with node-level matches.

**Open Questions:** Best domain pair to demonstrate coupling necessity? How to expose peer callbacks without LLM keys? (Mock execute_fn sufficient for demo.)

**Effort:** Medium. Assembly, but needs C139 to be compelling.

---

### Priority 5 — Reflexion-Backed Session

**Trigger Surface:** Session config `--with-reflexion` or envelope field `enable_reflexion=true`.

**Runtime Path:**
- `session.run()` invokes `integrated_reflexion.run_with_reflexion(...)` every N turns.
- Reflexive journal persists in MemOS; `evaluation.py` includes reflexion findings in final grade.

**User Evidence:** Session log with Stufe 1–2 diagnostics, recommended mutations, execution status. Exported `reflexion_report.json`.

**Open Questions (blocking):**
- **Mutation policy:** Auto-apply vs manual review? Auto makes demos non-reproducible. Manual defeats automation.
- **Scope interaction:** How does scoped reflexion (C101–C106) interact with Session lifecycle?
- These questions need design work before implementation.

**Effort:** Large. Policy design required.

---

### Priority 6 — Curriculum Demo

**Problem:** `CurriculumRunner` (C123) is fully implemented and tested (35 tests) but never appears in any demo. It's the natural way to explore the ontodynamics canon level by level.

**Trigger Surface:** `demo_curriculum_canon.py` running CurriculumRunner on `ontodynamics_v2` canon.

**User Evidence:** Level-by-level learning progress, T_s equilibrium detection, transfer_historization between turns.

**Effort:** Small. Existing API, just needs a demo script.

---

### Priority 7 — SU(2) Transport Demo

Low urgency. SU(2) is theoretically elegant and fully tested, but no practical advantage over U(1) has been demonstrated on any real domain. Worth revisiting when a domain naturally benefits from multi-axis transport.

**Effort:** Small (just flags), but value unclear.

---

### Priority 8 — Observation & Service Onboarding

**Problem:** The observation UI (C94–C97) works but onboarding docs are missing. This is a documentation/DevX task more than an integration task.

**Effort:** Medium (documentation + onboarding recipe). Not blocked by anything.

---

## 4. Gap Analysis: What Codex Missed

| Missing Item | Status | Why It Matters |
|---|---|---|
| DreamObserver still uses C109 edge-EQ, not C137 Hungarian | **Critical gap** — Priority 1 | The proven 100% algorithm isn't wired into runtime |
| Bootstrapper+LLM-Teaching pipeline (C134) | Not mentioned | The cold-start solution exists but has no demo |
| Curriculum (C123) | Not mentioned | 35 tests, zero demos |
| C43–C47 Self-Graph architecture | Not referenced | The overarching integration framework for "E0 learns E0" |
| Score correlation as scaling assumption | Not flagged | C138c showed this is the load-bearing assumption — affects all multi-domain stories |

---

## 5. Next Steps
1. ~~C139: DreamObserver + Hungarian~~ — ✅ DONE (commit `998f1f6`)
2. ~~C140: Bootstrapper demo~~ — ✅ DONE (commit `d3adfe1`)
3. ~~C141: Entropy/Sleep–Wake flags~~ — ✅ DONE
4. Multiverse quickstart (Priority 4) — now compelling with C139 Hungarian in runtime
5. Reflexion needs design discussion before implementation
6. Update README/Quickstart as each capability ships

---

*Initial analysis by Codex, 2026-04-04. Reviewed and revised with Copilot.*
