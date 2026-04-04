# E0 Integration Stories v1

**Status:** Draft — integration planning only  
**Date:** 2026-04-04  
**Scope:** Identify how underused capabilities become first-class runtime features without code edits yet.  
**Out of scope:** Implementation, parameter tuning, or UI polish.

---

## 1. Purpose & Method
- Enumerate high-value subsystems that currently exist but remain dormant outside of tests or exploratory scripts.
- Describe an integration story per subsystem: trigger surface, runtime path, instrumentation, and open questions.
- Provide a checklist to convert stories into backlog items later.

| Layer | Capability | Current Usage | Integration Story Goal |
|-------|------------|---------------|------------------------|
| Field Theory | SU(2) multi-axis transport & resonator modulation | Only via unit tests / explore_* scripts | Offer a reference demo + envelope preset that enables SU(2) transport and resonator boosts on a real domain (e.g., Gordian Trap). |
| Reflexion | Self-Graph ? Integrated Reflexion pipeline | Exercised in tests, not in live runs | Embed reflexion cycles into a standard Session so diagnostics/mutations appear in demo outputs. |
| Multiverse | Coupling, NoveltyGate, divergence pressure | Language-learning exploration and benchmarks only | Launch a turnkey multiverse run (e.g., two invoice controllers) that showcases novelty accounting and peer consultation. |
| Observation/UI | Observation controller, FastAPI service, Cytoscape client | Existing UI code, but not linked in quickstart | Publish a reproducible “observe any session” workflow with CLI + browser steps. |
| Structural Entropy & Sleep–Wake | Automatic inscription thresholds, decay, dream pressure orchestration | Only in explore_language_learning.py | Let standard demos opt into entropy + sleep-wake so forgetting/dream metrics show up in logs. |
| Dream Mode (general) | Edge/Node/WL equivalence detection | Language-learning focus | Define a domain-agnostic dream pipeline (e.g., cross-scenario comparison) and surface its findings in a report artifact. |

---

## 2. Story Templates
Each story follows the same skeleton:
1. **Trigger Surface:** CLI flag, envelope preset, or API endpoint that enables the feature.
2. **Runtime Path:** Modules/functions that should execute when the trigger is on.
3. **User-Facing Evidence:** Logs, reports, artifacts, or UI views proving the feature ran.
4. **Instrumentation & Tests:** Existing coverage leveraged + gaps to fill.
5. **Open Questions:** Design decisions still unresolved.

---

## 3. Detailed Stories

### Story A — SU(2) Transport & Resonator Boost Demo
- **Trigger Surface:** `python -m e0_controller.demo_greedy_trap --transport su2_geometric --resonator` (new flags referencing existing controller kwargs `use_su2` and `resonator_modulation`).
- **Runtime Path:**
  - `E0Controller(..., use_su2="geometric", axis_fn=...)` and `resonator_modulation=True`.
  - Overlay computation (`amplitude_overlay.compute_overlay`) receives SU(2) carrier and resonance modifier.
- **User Evidence:**
  - CLI output contrasts U(1) vs SU(2) intensities + notes resonator weighting when cycles exist.
  - Optional MatPlot or textual dump of path phases showing 720° periodicity.
- **Instrumentation:** Reuse `test_spinor.py`, `test_multi_axis_su2.py`, `test_resonator_integration.py` assertions; add demo smoke test to ensure flags wire through.
- **Open Questions:** Choose default `axis_fn`; define heuristics for domains without resonance (should the flag auto-disable?).

### Story B — Reflexion-Backed Session
- **Trigger Surface:** Session config `--with-reflexion` or envelope field `enable_reflexion=true`.
- **Runtime Path:**
  - `session.run()` invokes `integrated_reflexion.run_with_reflexion(...)` every N turns.
  - Reflexive journal persists in MemOS; `evaluation.py` includes reflexion findings in final grade.
- **User Evidence:**
  - Session log snippet summarizing Stufe?1–2 diagnostics, recommended mutations, and whether they executed.
  - Exported `reflexion_report.json` in session folder.
- **Instrumentation:** Build on `test_integrated_reflexion.py` and `test_integrated_scoped_reflexion.py`; add end-to-end test that toggles the session flag and asserts journal files exist.
- **Open Questions:** What policy governs mutation application (auto vs manual review)? How to keep deterministic demos reproducible once structural mutations occur?

### Story C — Multiverse Quickstart
- **Trigger Surface:** `python -m e0_controller.demo_invoice_llm --multiverse 2` or a dedicated script `demo_multiverse_invoice.py`.
- **Runtime Path:**
  - Instantiate `MultiverseController(Universe A, Universe B)` with shared/independent landscapes; attach `cross_reflexion.cross_reflexion_turn` as turn fn.
  - Collect NoveltyGate metrics, divergence pressure events, overload escalations.
- **User Evidence:**
  - Summary table after run: novelty rate, number of peer consultations, edges discovered via cross-reflexion.
  - Optional side-by-side MemOS snapshots for both universes.
- **Instrumentation:** Use `test_multiverse.py` + `benchmark_multiverse.py` as foundations; add a smoke test that the quickstart completes and logs novelty stats.
- **Open Questions:** Which domain pair best demonstrates the coupling necessity theorem? How to expose peer callbacks without requiring live LLM keys?

### Story D — Observation & Service Onboarding
- **Trigger Surface:** Documentation recipe “Start server + client to inspect any session” referencing `python -m uvicorn server.main:app` and the bundled React client.
- **Runtime Path:**
  - `service.py` instantiates `ObservationController` lazily when a session is loaded.
  - WebSocket streams GraphView updates; snapshot codec ensures parity with MemOS states.
- **User Evidence:**
  - Screencast or step list verifying that the UI renders nodes/edges, allows focus/depth navigation, and overlays run traces.
  - CLI command `python tools/observe_session.py --session foo` that fetches snapshots without the browser (for headless proof).
- **Instrumentation:** Reference `test_service_layer.py`, `test_observation_controller.py`, `test_rendering_adapter.py`; add doc tests verifying API endpoints respond.
- **Open Questions:** Auth/security for public deployments; resource footprint when observation runs alongside heavy controllers.

### Story E — Structural Entropy & Sleep–Wake in Standard Demos
- **Trigger Surface:** Flag `--entropy` on demos toggling `inscription_threshold=True` and enabling `SleepWakeCycle` orchestration.
- **Runtime Path:**
  - During wake phases, controller tracks non-inscription metrics; after threshold, `structural_entropy.apply_decay` prunes states.
  - Dream phases triggered via `sleep_wake.SleepWakeCycle.run()` schedule DreamObserver cycles.
- **User Evidence:**
  - Demo output includes Type?1/Type?2 decay summaries, dream pressure values, and Sleep/Wake transitions.
  - MemOS snapshots store `structural_entropy` reports.
- **Instrumentation:** Lean on `test_structural_entropy.py` (already includes SleepWakeCycle) and add scenario-level tests verifying decay reports exist when the flag is set.
- **Open Questions:** Default µ / dream-pressure parameters for short demos; user safeguards to avoid destructive decay on reference canons.

### Story F — Domain-Agnostic Dream Mode Report
- **Trigger Surface:** CLI `python tools/run_dream_cycle.py --domains scenario/*` or session flag `--dream-report`.
- **Runtime Path:**
  - Register multiple landscapes (e.g., canon, invoice, research) with `DreamObserver`.
  - Execute `dream_cycle` after run completion, store edge and node equivalences.
- **User Evidence:**
  - Artifact `dream_report.md/json` summarizing top bridge hypotheses, WL fingerprint matches, and confidence distribution.
  - Optionally push cross-domain discoveries back into MemOS for later runs.
- **Instrumentation:** Extend `test_dream_mode.py` coverage with a multi-domain smoke test; ensure report serialization is deterministic for snapshot testing.
- **Open Questions:** How to gate promotion of dream-discovered edges (auto vs manual review)? What minimum fingerprint confidence qualifies for inclusion?

---

## 4. Next Steps Checklist
1. Prioritize stories based on effort/user impact (suggested order: Multiverse quickstart ? Reflexion session ? Entropy/Sleep–Wake ? SU(2) demo ? Dream report ? Observation onboarding).
2. For each story, define concrete CLI/API signatures and expected artifacts.
3. Update README/Quickstart once a story ships so the capability becomes discoverable.
4. Track story status in `bootstrap.json` (new section `integration_stories`).

---

*Prepared by Codex — 2026-04-04*
