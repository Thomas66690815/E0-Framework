# E₀ Strategic Roadmap v1

**Status:** Active — living document  
**Created:** 2026-04-06  
**Context:** Post-C171 panoramic review. All Multi-Domain Dream Analysis questions closed (Q1–Q4). 8 development arcs complete. 4063 tests, 0 failures, 171 commits.

---

## 1. Where E₀ Stands

E₀ is a **complete, tested structural decision system** — an AGI skeleton, not an AGI.

**What works (high confidence):**
- Deterministic navigation with amplitude override (10-domain benchmark, chess, Gordian Trap)
- Historized learning producing domain expertise without labels (chess: blank-slate → strategy)
- Multiverse coupling (3×E₀ beats solo in chess, 67% novelty rate)
- Cross-domain structural matching (WL+Hungarian: 44/44 = 100%, scaled to 500 nodes)
- Cold-start bootstrapping (LLM → Landscape via monolingual teaching)
- Human communication pipeline (Task → LLM → Navigation → Perception → Intent → UISpec → HTML)
- Parameter self-tuning (closed-loop: diagnose → perturb → evaluate → adopt)
- Structural forgetting + sleep-wake cycles (121 dedicated tests)

**What's built but underutilized:**
- SU(2) transport (39 tests, no practical advantage)
- Scoped reflexion (emergent locality proven, no Session integration)
- Focus narrowing (random pruning works, peer bypass missing)
- Observation layer (6 modules, superseded by Session runner)

**The honest sentence:**  
Breadth is no longer the problem. The question is: which test forces the system to prove its truth claims under real tension?

---

## 2. Strategic Directions (Ranked)

### Priority 1: Adversarial Stability

**Why first:** It is the fairest and hardest test. E₀ claims structural stability is *mechanical* (not normative) — this must hold under pressure. If it does, everything else becomes more credible. If it doesn't, we learn something fundamental.

**The question:** Does E₀'s resistance-based stability prevent misalignment when the environment is deliberately deceptive?

**Concrete test scenarios:**
- **Hidden reward flip:** Domain where SUCCESS is actually harmful (edge leads to structural degradation but reports SUCCESS)
- **Ambiguous inputs:** Multiple edges that are structurally identical but have different hidden consequences
- **Adversarial peer:** Multiverse partner that deliberately sends misleading edge proposals
- **Gradient hacking analog:** Can an adversarial landscape structure manipulate E₀'s historization to create false attractors?

**What we expect to find:**
- Resistance constraints (high-R blocks transitions) as first line of defense
- Historization asymmetry (ρ_F > ρ_S) preserves failure memory
- Self-graph quality detection as early warning
- Dream compatibility gating rejects structurally alien inputs

**What would be a genuine failure:**
- E₀ converges on adversarial attractor without Self-Graph detecting anomaly
- Historization washes out danger signals via standard decay
- Peer consultation amplifies adversarial signal instead of filtering it

**Falsification value:** HIGH — directly tests the AGI blueprint's core claim (§6: alignment as mechanical stability)

**Status:** TESTED — 3/3 FAIL (C172). All defense mechanisms trust Outcome blindly. Consistent deception bypasses every layer. See `docs/research/E0_ADVERSARIAL_STABILITY_RESEARCH_v1.md` §6–7.  
**Follow-up:** C173 Structural Skepticism — run-level meta-observation (load without frontier) detects stagnation attacks (A+B PASS), does not detect injection attacks (C FAIL), no false positives (D PASS). See `docs/research/E0_STRUCTURAL_SKEPTICISM_RESEARCH_v1.md`.

---

### Priority 2: Semantic / Causal Binding

**Why second:** E₀ sees SUCCESS/FAILURE but not *why*. Without causal binding, structural intelligence remains blind to mechanism. Starting small with ground-truth domains keeps this falsifiable rather than vague.

**The question:** Can E₀ distinguish structurally identical edges that differ only in causal mechanism?

**Approach (small, not grand):**
- Build causal test domains with explicit ground-truth relations (A causes B, not just A→B exists)
- Introduce causal edge annotation: not just quality/load, but *why* this edge succeeded
- Test: Given two paths with equal S_eff but different causal chains, does E₀ prefer the causally coherent one?

**Design constraints:**
- No large ontology — 3–5 node domains with explicit causal structure
- Structure vs. cause must be cleanly separable (same topology, different causal backing)
- Must be falsifiable: if E₀ cannot distinguish, that's a real result

**What would be success:**
- E₀ develops different historization patterns for causally different edges (even if structurally identical)
- Causal coherence emerges as a quality signal without explicit encoding

**What would be a genuine failure:**
- Structural identity = behavioral identity, no matter the causal backing
- This would mean E₀ needs an explicit causal layer (new primitive, not emergent)

**Falsification value:** HIGH — determines whether semantic grounding is emergent or must be engineered

**Status:** NOT STARTED

---

### Priority 3: N-Domain Mesh

**Why third:** Pairwise successes (EN↔DE = 100%) do not guarantee multi-domain self-organization. But this only matters *after* adversarial stability and causal binding are understood — otherwise we'd build an elegant mesh on unverified foundations.

**The question:** Do 3+ domains dreaming and coupling simultaneously self-organize into coherent clusters, or does quality collapse?

**Concrete test plan:**
- Start with N=3: EN + DE + ONTO (known compatibility: EN↔DE=0.375✓, EN↔ONTO=0.870✗)
- Extend to N=5: add two more domains (COOK, PROJECT from existing canons)
- Measure: cluster formation, selective coupling, quality saturation point

**What we expect:**
- Compatible pairs (EN↔DE) cluster naturally
- Incompatible pairs (EN↔ONTO) are filtered by compatibility gating (C168)
- Emergent hierarchy: some domains become "hubs" (high coupling weight to many partners)

**Open sub-questions:**
- Does CouplingRouter self-organize partner weights correctly with N>2?
- Do dream equivalences form transitive chains (A↔B + B↔C → A↔C)?
- At what N does system overload (dream_pressure saturation)?
- Do inkompatible pairs create information barriers or just silence?

**Falsification value:** MEDIUM — tests scalability, but failure would mean "needs engineering" not "fundamentally wrong"

**Status:** NOT STARTED  
**Prerequisite:** Priority 1 (adversarial) should be at least explored first

---

### Cross-Cutting: Operative Self-Exposition

**Why cross-cutting (not a separate priority):** C158–C166b created something larger than a UI feature. The question "Can E₀ bring itself to the outside adequately?" — selection, exposition, communicative compression, partner connectivity — is a maturity test that accompanies all three priorities.

**The distinction:**
- **Implemented:** Perception → Intent → UISpec → HTML pipeline works (PoC, 75% rendering success)
- **Not yet strategically exhausted:** No runtime adapter, no live feedback loop at scale, no domain-specific UI adaptation

**How it connects to each priority:**
- **Adversarial:** Can E₀ *communicate* that it detects adversarial pressure? (Self-exposition of anomaly)
- **Causal binding:** Can E₀ *explain* why it chose one path over another? (Causal exposition)
- **N-domain mesh:** Can E₀ *expose* cluster structure to a human operator? (Structural exposition)

**Concrete next steps (independent of priority order):**
- Runtime adapter: UISpec → actual interactive display (not just static HTML)
- Domain-specific rendering: financial dashboard vs. chess board vs. incident timeline
- Self-diagnostic exposition: Self-Graph quality → human-readable status summary
- Dream exposition: "I found that X in domain A matches Y in domain B" as natural language

**Status:** PoC COMPLETE, strategic exhaustion NOT STARTED

---

## 3. What Is Explicitly NOT Next

These are valuable but premature:

| Direction | Why not now |
|-----------|------------|
| SU(2) revival | No practical advantage demonstrated; revisit only if adversarial test reveals U(1) weakness |
| Reflexion mutation policy | Important but architectural; needs adversarial context to test properly |
| Curriculum × Dream feedback | Needs N-domain mesh first |
| Focus narrowing × peer bypass | Simple fix, do when relevant (Priority 3 scaling) |
| Open-ended exploration | Grand ambition; needs semantic binding first |

---

## 4. Maturity Assessment

| Dimension | Current | After Priority 1 | After Priority 2 | After Priority 3 |
|-----------|---------|-------------------|-------------------|-------------------|
| Structural navigation | ✅ Proven | ✅ | ✅ | ✅ |
| Learning from experience | ✅ Proven | ✅ | ✅ | ✅ |
| Multi-system coupling | ✅ Proven (N=2) | ✅ + adversarial peer | ✅ | ✅ Proven (N>2) |
| Cross-domain matching | ✅ Proven (pairwise) | ✅ | ✅ | ✅ Proven (mesh) |
| Adversarial robustness | ❌ Untested | ⚠️ Stagnation solved, injection open | ⚠️ | ⚠️ |
| Semantic grounding | ❌ Not attempted | ❌ | ⚠️ or ✅ | ⚠️ or ✅ |
| Self-exposition | ⚠️ PoC | ⚠️ + anomaly reporting | ⚠️ + causal explanation | ⚠️ + mesh visualization |
| AGI claim testable | ❌ | ✅ (one axis) | ✅ (two axes) | ✅ (three axes) |

---

## 5. Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-06 | Priority order: Adversarial → Semantic → N-domain | Adversarial is hardest/fairest; semantic before mesh prevents elegant-but-unverified scaling |
| 2026-04-06 | Self-exposition as cross-cutting, not separate priority | Accompanies all three directions; PoC exists, strategic exhaustion ongoing |
| 2026-04-06 | N-domain mesh after adversarial | No point building mesh on unverified stability foundations |
| 2026-04-06 | Semantic binding starts small (3–5 node causal domains) | Prevents slide into vague claims; must be falsifiable |
| 2026-04-06 | C173: Structural Skepticism viable for stagnation | Load-without-frontier detects coherent loops; injection needs Level 2 (quality spread) |
| 2026-04-06 | C174: Self-Honesty L2 solves injection attacks | "Truth is perspective. Self-honesty is structural." Avoid known-bad beats prefer known-good. Scenario C: FAIL → PARTIAL (goal reached, fakes 19→4, bloat 167%→67%) |
| 2026-04-06 | C175: Causal binding — implicit intervention discovery | E₀'s natural path alternation functions as causal probing. Confound leaks through observation alone (S1 refuted). No explicit causal layer needed for detection. |
| 2026-04-06 | C176: Context Sensitivity Metric | Formalizes C175 finding: predecessor tracking + context_sensitivity() ∈ [0,2]. CAUSAL=0.0, CONFOUNDED=2.0 — only confounded edge flagged. Canon §5 validated: causality derived, not primitive. |
| 2026-04-06 | C177: Larger Topology Confound Detection | 12 states, 17 edges, 3 confounds at depths 2-5: all detected (cs=2.0), 0 false positives. Greedy controller needs multi-start intervention in deep topologies (recent_k=3 too short). |

---

## 6. Progress Tracking

### Priority 1: Adversarial Stability
- [x] Design adversarial test domains (hidden reward flip, ambiguous inputs)
- [x] Build exploration: adversarial landscape + standard E₀ controller
- [x] Measure: does Self-Graph detect anomaly? → No (C172: all +1.0)
- [x] Measure: does historization preserve danger signals? → No (C172: trap = attractor)
- [x] Test adversarial peer in multiverse → Yes but unguarded (C172: 167% bloat)
- [x] Research document with findings
- [x] Verdict: fundamentally insufficient without meta-observation
- [x] C173: Structural Skepticism — stagnation detection via frontier monitoring
- [x] Verdict: stagnation attacks (A+B) SOLVED, injection attacks (C) OPEN
- [x] C174: Level 2 Self-Honesty — avoid known-bad for injection attacks (C: FAIL → PARTIAL)
- [x] Verdict: all 3 adversarial scenarios addressed (A+B PASS, C PARTIAL, D no false positive)

### Priority 2: Semantic / Causal Binding
- [x] Design causal test domains (same topology, different causal backing)
- [x] Build exploration: structural twin edges with different causes
- [x] Measure: does historization differentiate? → YES, via implicit intervention (multi-path exploration)
- [x] Verdict: causal detection emergent from topology + historization — no explicit layer needed for detection
- [x] Context sensitivity metric (quality variance by predecessor) — C176: context_sensitivity() ∈ [0,2], CAUSAL=0.0 vs CONFOUNDED=2.0
- [x] Larger topology test (10+ nodes, non-obvious confounds) — C177: 12 states, 17 edges, 3/3 confounds detected (cs=2.0), 0 false positives
- [ ] Dream-based causal transfer (broken equivalences as divergence signal)

### Priority 3: N-Domain Mesh
- [ ] N=3 experiment (EN + DE + ONTO)
- [ ] N=5 experiment (add COOK + PROJECT)
- [ ] Measure cluster formation and coupling weight self-organization
- [ ] Test dream transitivity (A↔B + B↔C → A↔C?)
- [ ] Find saturation point (at what N does quality collapse?)

### Cross-Cutting: Self-Exposition
- [ ] Runtime adapter (UISpec → interactive display)
- [ ] Self-diagnostic exposition (Self-Graph → human-readable)
- [ ] Dream exposition (equivalences → natural language)
- [ ] Integrate with each priority as it progresses
