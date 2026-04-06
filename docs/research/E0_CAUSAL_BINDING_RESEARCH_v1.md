# E₀ Causal Binding Research v1

**Status:** IN PROGRESS  
**Context:** Post-C174 (Adversarial Stability complete). Priority 2 from Strategic Roadmap.  
**Question:** Can E₀ distinguish causal structure from mere correlation using existing primitives — without explicit causal annotation?  
**Method:** Twin domains with identical topology, different causal backing. Intervention test (do-calculus analog). Dream coupling for cross-domain divergence detection.

---

## 1. Motivation

C173/C174 showed that E₀ detects structural self-inconsistency (stagnation, repeated failure) using only frontier tracking and outcome memory. But those tests operated within a single domain with adversarial outcome manipulation.

Priority 2 asks a deeper question: can E₀ detect **semantic** differences between structurally identical edges? Specifically: does an edge A→B that represents genuine causation behave differently in E₀ than an edge A→B that represents accidental correlation?

This matters because:
- The canon claims causal ordering is a **derived** consequence (§5), not a primitive
- If causality truly emerges from historization, E₀ should detect it without extension
- If not, we need an explicit causal annotation layer — and the canon's claim needs qualification

## 2. Canon Foundation

### 2.1 Causality as Derived

The canon (§5: Necessary Consequences) lists "causal ordering" as a *derived* consequence of Difference, Historization, and Time — not as an axiom or primitive operation.

### 2.2 Directed Difference

Ontodynamics §3.1: "Difference is **directed**: it is not symmetric or inert."

But §3.1 also states: "Connection is not spatial, causal, or relational between pre-existing entities."

### 2.3 The Tension

The canon asserts causality emerges from the *ordering* of historizations. Causal order = temporal order = historization sequence. But implementation stops at recording outcomes — the **ordering** (which edge was traversed before which) is not explicitly stored.

**Key question for this research:** Is the lost ordering information recoverable from accumulated traces? Or is it fundamentally discarded?

## 3. Primitive Analysis

### 3.1 What Encodes Direction Today

| Primitive | Directional? | Causal Content |
|-----------|-------------|----------------|
| Edge (source→target) | Yes | None (topological only) |
| Historization (U, F per edge) | Yes | Outcome, not mechanism |
| Trace quality q(e) | Yes | "How often it works" — not "why" |
| Trace load m(e) | Yes | "How often traversed" — not "in what order" |
| Tension S_eff | Yes (via R_eff) | Gradient, not causal arrow |
| Dream fingerprint | Yes (via q, m, I) | Outcome-derived, no new causal info |
| Coupling weights | Yes (asymmetric) | Utility-directional, not mechanism-causal |

### 3.2 What Is Missing

**Ordering information.** E₀ records U=5, F=2 for edge A→B but not:
- Whether the 5 successes came before or after the 2 failures
- Whether A→B was preceded by X→A or Y→A
- Whether B→C succeeded because A→B succeeded first, or independently

**Mechanism information.** E₀ records "A→B succeeded" but not "A→B succeeded BECAUSE of [reason]."

### 3.3 The Asymmetry of Knowledge

From C174 we learned: negative knowledge is structurally reliable, positive knowledge is perspectival.

Applied to causality:
- "A→B always fails" — structural fact, reliably detectable
- "A→B always succeeds because A causes B" — perspectival claim, NOT detectable from outcome alone

This suggests E₀ can detect **causal absence** (broken chains) but not **causal presence** (genuine mechanisms) from existing primitives alone.

## 4. Test Design: The Causal Twin Experiment

### 4.1 Core Insight: The Intervention Test

The gold standard for distinguishing causation from correlation is **intervention** (Pearl's do-calculus):

- **Observation:** P(C | observe A→B succeeded) — same for causal and confounded
- **Intervention:** P(C | do(start at B, skip A)) — differs:
  - Causal domain: B→C still works (B's capability is intrinsic)
  - Confounded domain: B→C fails (B only works when preceded by A)

This can be tested in E₀ using two navigation phases with different start states.

### 4.2 Domain Topology

Both domains share identical topology:

```
     A → B → GOAL
    /         ↑
START         |
    \         |
     C -------+
```

5 states: START, A, B, C, GOAL  
Edges: START→A, START→C, A→B, C→B, B→GOAL  
All edges: Δ=1.0, R₀=0.3 (identical structural parameters)

### 4.3 Three Scenarios

**Scenario 1 — CAUSAL Domain:**
- All transitions always succeed
- B→GOAL works regardless of predecessor (A or C)
- Causality: B intrinsically enables GOAL

**Scenario 2 — CONFOUNDED Domain:**
- A→B always succeeds
- C→B always succeeds
- B→GOAL succeeds ONLY if preceded by A→B in the same run
- B→GOAL fails if preceded by C→B
- Hidden confound: A "activates" the path, B is not intrinsically capable

**Scenario 3 — FRAGILE Domain:**
- Same as CAUSAL initially
- A→B succeeds first 3 times, then FAILURE (correlation wears off)
- C→B always succeeds
- B→GOAL always succeeds

### 4.4 Two-Phase Protocol

**Phase 1 — Observation (5 cycles):**
Navigate START → GOAL normally. Both CAUSAL and CONFOUNDED succeed via A→B→GOAL. Traces accumulate identically.

**Phase 2 — Intervention (5 cycles):**
Navigate B → GOAL directly (start='B', goal='GOAL').  
- CAUSAL: B→GOAL succeeds → trace_quality stays high
- CONFOUNDED: B→GOAL fails → trace_quality drops sharply

**Phase 3 — Dream Coupling (optional):**
Run DreamObserver across CAUSAL + CONFOUNDED. Does edge equivalence for B→GOAL break after intervention?

### 4.5 What We Measure

| Metric | Phase 1 (observation) | Phase 2 (intervention) |
|--------|----------------------|----------------------|
| trace_quality(B→GOAL) CAUSAL | ~+1.0 | ~+1.0 (stable) |
| trace_quality(B→GOAL) CONFOUNDED | ~+1.0 | decreasing toward −1.0 |
| S_eff(B→GOAL) CAUSAL | low | low (stable) |
| S_eff(B→GOAL) CONFOUNDED | low | rising (failure increases R_eff) |
| Dream equivalence B→GOAL | matched | **broken** |

## 5. Predictions

### P1: Phase 1 traces are identical
Both domains navigate identically via A→B→GOAL. Historization records the same U/F counts. Dream fingerprints match. **Causality is invisible during observation.**

### P2: Phase 2 traces diverge
Intervention reveals the confound. CAUSAL domain: B→GOAL continues succeeding. CONFOUNDED: B→GOAL fails. Historization diverges.

### P3: Dream detects the divergence
After Phase 2, edge fingerprints for B→GOAL differ across domains. Dream equivalence should break — the edges are no longer functionally equivalent.

### P4: Fragile domain diverges spontaneously
In Scenario 3 (FRAGILE), A→B fails after 3 uses. No intervention needed — historization detects the degradation naturally. But this is trivial: it's outcome detection, not causal detection.

### P5: The hard verdict
If P1 + P2 + P3 hold, then:
- **Causality is NOT emergent from passive observation** (P1: traces identical during observation)
- **Causality IS detectable via intervention** (P2: traces diverge under do-operation)
- **Dream can detect causal divergence, but only AFTER intervention** (P3)

This means: E₀'s historization is a faithful recorder of causal consequences, but NOT a causal detector. Detection requires **active probing** (intervention), not passive accumulation.

### P6: Implication for annotation layer
If P5 holds, the minimal extension is not an explicit `cause` field on Edge, but an **intervention capability**: the ability to test "what happens if I start from B directly?" This is structurally a second run with a different start state — something E₀ already supports.

## 6. Results

### 6.1 S1: Observation Parity → FAIL (prediction P1 refuted)

| Edge | CAUSAL quality | CONFOUNDED quality | Match? |
|------|---------------|-------------------|--------|
| START→A | +1.0000 | +1.0000 | ✓ |
| START→C | +1.0000 | +1.0000 | ✓ |
| A→B | +1.0000 | +1.0000 | ✓ |
| C→B | +1.0000 | +1.0000 | ✓ |
| B→GOAL | +1.0000 | **+0.2380** | ✗ DIVERGED |

**Why P1 failed:** E₀'s greedy navigation naturally alternates between the A path and the C path (due to load balancing). When it takes C→B→GOAL in the confounded domain, B→GOAL *fails* (no A predecessor). This alternation IS an implicit intervention — by trying both paths, E₀ naturally tests context-dependence.

**This is more interesting than P1 holding:** We predicted that observation cannot detect causality. But E₀'s multi-path exploration inherently performs weak causal probing. The confound leaks through natural navigation.

### 6.2 S2: Intervention Divergence → PASS

| Metric | CAUSAL | CONFOUNDED |
|--------|--------|------------|
| B→GOAL outcomes | 5/5 SUCCESS | 5/5 FAILURE |
| B→GOAL quality (post) | +1.0000 | -0.6323 |
| Quality divergence | **1.6323** |

Explicit intervention (start='B', skip A) cleanly separates the two domains. CAUSAL: B→GOAL continues working. CONFOUNDED: B→GOAL fails every time.

### 6.3 S3: Dream Equivalence Detection → PASS

After intervention:
- B→GOAL fingerprint distance: **1.6353** (massive)
- 12 dream equivalences found — B→GOAL is NOT among them
- All 4 non-GOAL edges match perfectly (distance 0.0000)

Dream correctly identifies B→GOAL as the ONE edge that differs between domains. All other edges (which ARE genuinely equivalent) remain matched.

### 6.4 S4: Fragile Degradation → PASS

A→B degrades after 3 uses: quality drops from +1.0 to -0.4987. Controller continues through C→B path. Historization detects degradation naturally — trivial, but confirms baseline.

### 6.5 S5: Cross-Domain Transfer → PASS

Post-intervention, CAUSAL domain B→GOAL (q=+1.0) does NOT match FRESH domain B→GOAL (q=0.0) — different loads. But CONFOUNDED domain B→GOAL (q=-0.6323) DOES match FRESH (both differ from healthy). The transfer signal is in the quality: causal knowledge (q>0) is reliably positive, confounded knowledge (q<0) is a warning.

### 6.7 S6: Context Sensitivity Metric (C176)

C175's central finding — that E₀ detects confounds through implicit multipath exploration — remained observational. C176 formalizes this as a computable metric.

**Implementation:**
- `TraceRecord.predecessor`: each historization entry now records which edge was traversed immediately before
- `context_quality(edge)`: per-predecessor quality breakdown from audit log
- `context_sensitivity(edge)`: max quality range across predecessors, ∈ [0, 2]
  - 0.0 = edge behaves identically regardless of context (context-free)
  - 2.0 = maximum divergence (always succeeds from one predecessor, always fails from another)

**Results:**

| Edge | CAUSAL cs | CONFOUNDED cs | Interpretation |
|------|----------|--------------|----------------|
| START→A | 0.0000 | 0.0000 | Context-free ✓ |
| START→C | 0.0000 | 0.0000 | Context-free ✓ |
| A→B | 0.0000 | 0.0000 | Context-free ✓ |
| C→B | 0.0000 | 0.0000 | Context-free ✓ |
| B→GOAL | 0.0000 | **2.0000** | **← CONFOUND DETECTED** |

Only B→GOAL in the confounded domain is flagged. All other edges — in both domains — show zero context sensitivity. The metric perfectly isolates the confounded edge.

**Why this matters:** E₀ doesn't "know" causality. It generates learnable contrasts through its own path variation. Context sensitivity makes those contrasts explicit and queryable. No new primitive needed — predecessor tracking is a minimal extension of existing historization.

### 6.8 Results Summary

| Scenario | Prediction | Result | Finding |
|----------|-----------|--------|--------|
| S1: Observation Parity | Identical traces | **FAIL** | Causal leakage via implicit intervention |
| S2: Intervention | Divergence | **PASS** | Quality divergence 1.63, clean separation |
| S3: Dream Detection | Broken equivalence | **PASS** | B→GOAL excluded, all others matched |
| S4: Fragile | Degradation detected | **PASS** | Trivial baseline confirmed |
| S5: Transfer | Asymmetric portability | **PASS** | Causal q>0; confounded q<0 |
| S6: Context Sensitivity | Isolate confound | **PASS** | CAUSAL=0.0, CONFOUNDED=2.0, only B→GOAL flagged |

## 7. Architectural Implications

### 7.1 The Central Discovery: Implicit Intervention

The most important finding is not S2 (deliberate intervention works — trivially true) but S1: **E₀'s natural multi-path exploration functions as implicit causal probing.**

When the controller alternates between A→B→GOAL and C→B→GOAL, it unknowingly performs a natural experiment:
- A→B→GOAL: B→GOAL succeeds (A as predecessor)
- C→B→GOAL: B→GOAL fails (C as predecessor)

The quality divergence (+0.2380 vs. +1.0000 after 5 cycles) shows the confound leaking through. No deliberate intervention needed.

**Why this happens:** E₀'s greedy navigation with load-based diversification naturally explores alternative paths. This diversification — designed for efficiency — incidentally provides causal information. Structure serves double duty.

### 7.2 The Canon’s Claim: Partially Validated

The canon claims causal ordering is a *derived* consequence. Our findings:

- **Validated:** Causality IS detectable from existing primitives (historization + natural exploration). No explicit causal annotation needed for the confounded-path case.
- **Qualified:** Detection requires *topological alternatives* (multiple paths to the same node). In a pure chain (A→B→C with no alternative path to C), the confound would be invisible. Causality emerges from the interplay of topology and historization, not from historization alone.

### 7.3 When Causal Detection Fails

E₀ can detect confounds ONLY when:
1. Multiple paths reach the same node (topological prerequisite)
2. The controller explores those paths (behavioral prerequisite)
3. The confound manifests as different outcomes on different paths (outcome prerequisite)

E₀ CANNOT detect:
- Confounds where all paths produce the same outcome
- Causal mechanisms that don’t affect outcomes
- Latent confounds that haven’t been triggered yet

### 7.4 Connection to C174 (Self-Honesty)

C174 established: “Self-honesty is structural — we CAN know what has failed.”

C175 extends this: **Causal detection is structural — when different paths to the same node produce different outcomes, the context-dependent edge is exposed.**

Both findings share the same epistemological principle: E₀ cannot access ground truth (what IS causal), but can detect structural inconsistency (what BEHAVES differently in different contexts).

### 7.5 Do We Need an Explicit Causal Layer?

**For detection:** No. Existing primitives suffice when topology provides alternative paths.

**For quantification:** Solved (C176). `context_sensitivity(edge)` computes quality variance by predecessor from existing traces. The metric is:
- Minimal: one new field (`TraceRecord.predecessor`), two new methods
- Non-invasive: predecessor tracking is opt-in (default `None` preserves backward compatibility)
- Complete: ∈ [0, 2], where 0 = context-free and 2 = maximally confounded
- Precise: in the twin experiment, only B→GOAL in the confounded domain is flagged (0.0 vs 2.0)

**For transfer:** Quality sign (+/-) transfers basic causal information (S5). Context sensitivity adds structural detail: edges with cs > 0 should not be transferred without predecessor context. This enables smarter cross-domain proposals.

**For annotation:** No explicit `cause` field needed. Context sensitivity IS the causal annotation — derived, not primitive, exactly as the canon predicts (§5).

### 7.6 Next Steps

1. ~~**Context sensitivity metric:**~~ ✅ Done (C176). `context_quality()` and `context_sensitivity()` implemented, 18 tests, exploration S6 confirms perfect isolation.
2. **Larger topologies:** Test with 10+ node domains where confounds are non-obvious.
3. **Dream-based causal transfer:** Use broken equivalences as causal divergence signal in cross-domain proposals. Context sensitivity enables predecessor-aware transfer filtering.
4. **Connection to Priority 3 (N-domain mesh):** Causal detection through implicit intervention scales with N — more domains = more alternative paths = more natural experiments.

## 8. Open Questions

1. Does the intervention test generalize beyond the simple chain A→B→GOAL?
2. Can multiverse coupling function as implicit intervention? (Domain 1 forces start at B via cross-reflexion → tests CONFOUNDED domain's B→GOAL)
3. Is the canon's claim "causal ordering as derived consequence" validated or refuted by this experiment?
4. Connection to C174: Self-honesty detects "known-bad" (failure history). Causal detection requires "known-fragile" (conditional failure). Is there a Level 3 skepticism here?
