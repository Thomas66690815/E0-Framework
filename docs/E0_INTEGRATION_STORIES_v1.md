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

### Priority 1 — DreamObserver + Hungarian (C139)

**Problem:** `DreamObserver.dream_cycle()` (C110) uses edge-fingerprint equivalence detection from C109 — comparing per-edge (q,m,I) tuples with quantile thresholds. This gave ~2% accuracy on language canons. Meanwhile, C137 proved that WL+Hungarian achieves 100% (44/44), validated robust to noise (C138a), score perturbation (C138b), and scaling to 500 nodes (C138c). The proven algorithm sits in explore scripts. The runtime uses the obsolete one.

**Integration task:** Add a `node_equivalence_method` option to `DreamObserver` (or `dream_cycle`) that invokes `find_wl_node_equivalences_hungarian()` alongside or instead of the edge-fingerprint path. Node-level equivalences feed into bridge hypothesis generation.

**Runtime Path:**
- `DreamObserver.dream_cycle()` → call `find_wl_node_equivalences_hungarian(L_a, L_b, depth=2)` for each domain pair
- Node equivalences → `propose_bridges()` (existing C111 path, but fed with Hungarian results)
- `DreamCycleResult` extended with node-equivalence data

**User Evidence:**
- `dream_cycle()` returns node-level matches with WL distances
- Bridge proposals based on structurally matched nodes, not edge quantiles

**Tests:** Extend `test_dream_mode.py` with Hungarian-based dream cycle test. Reuse existing DreamObserver test structure.

**Open Questions:**
- Does `dream_cycle` replace edge-EQ entirely, or keep both? (Edge-EQ is cheap, node-EQ is thorough — layered approach?)
- How do WL node matches translate to bridge edge proposals? (Matched nodes → their edges become bridge candidates?)
- Does `_apply_confidence` from the Bootstrapper apply to dream-discovered edges?

**Effort:** Medium. The algorithm exists and is tested. The integration is wiring + API design.

---

### Priority 2 — Bootstrapper Demo

**Problem:** The Bootstrapper (C44) + LLM Teaching (C134) pipeline is proven but buried in explore scripts. A user cannot easily create a new domain Landscape from an LLM evaluation.

**Trigger Surface:** A demo script `demo_bootstrap_domain.py` that:
1. Takes a domain spec (JSON or natural language → LLM generates spec)
2. LLM scores each edge monolingually (0–10)
3. `inject_scores_into_spec()` → `bootstrap_landscape()` → ready Landscape

**User Evidence:** "Give me a topic" → LLM generates nodes+edges → scores them → Landscape ready for navigation. Complete cold-start-to-running in one script.

**Tests:** Smoke test that doesn't require LLM (mock scores). Existing `test_bootstrapper.py` (41 tests) covers the core.

**Open Questions:** Natural-language-to-spec is a separate LLM call (C45 LLM Adapter territory). Keep demo simple: JSON spec input first?

**Effort:** Small. Mostly assembling existing pieces.

---

### Priority 3 — Entropy/Sleep–Wake in Standard Demos

**Trigger Surface:** Flag `--entropy` on demos toggling `inscription_threshold=True` and enabling `SleepWakeCycle` orchestration.

**Runtime Path:**
- During wake phases, controller tracks non-inscription metrics; after threshold, `structural_entropy.apply_decay` prunes states.
- Dream phases triggered via `sleep_wake.SleepWakeCycle.run()` schedule DreamObserver cycles.

**User Evidence:** Demo output includes Type 1/Type 2 decay summaries, dream pressure values, and Sleep/Wake transitions.

**Tests:** Lean on `test_structural_entropy.py` (101 tests including SleepWakeCycle). Add scenario-level test verifying decay reports exist when flag is set.

**Open Questions:** Default θ / dream-pressure parameters for short demos. Safety: avoid destructive decay on reference canons (clone landscape before decay?).

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
1. **C139: DreamObserver + Hungarian** — Priority 1 implementation
2. After C139: Bootstrapper demo (Priority 2), then Entropy flags (Priority 3)
3. Multiverse quickstart after C139 makes dream reports meaningful
4. Reflexion needs design discussion before implementation
5. Update README/Quickstart as each capability ships

---

*Initial analysis by Codex, 2026-04-04. Reviewed and revised with Copilot.*
