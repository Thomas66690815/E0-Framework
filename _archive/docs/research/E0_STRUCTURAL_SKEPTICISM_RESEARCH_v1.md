# E₀ Structural Skepticism — Research Document v1

**Status:** COMPLETE (C173 Level 1 + C174 Level 2)  
**Context:** Post-C172 (Adversarial Stability — 3/3 FAIL). All defense mechanisms trust the Outcome signal blindly. Consistent deception bypasses every layer.  
**Question:** Can E₀ detect coherent deception using existing structural primitives — without access to ground truth?  
**Answer:** Yes. Two levels of meta-observation, using only frontier tracking and outcome memory, solve 3 of 3 adversarial scenarios. The foundational insight: *"Truth is perspective. Self-honesty is structural."*

---

## 1. The Problem (C172 Diagnosis)

C172 proved that E₀'s defenses (resistance, historization asymmetry, inertia modulation, Self-Graph) share a single vulnerability: they all trust the Outcome signal. When the environment lies consistently (SUCCESS on every step), no defense activates:

- **Inertia**: I = 1.0 because consistent SUCCESS → high |quality| → no contradiction penalty
- **Self-Graph**: all components +1.0 because every outcome was SUCCESS
- **Historization**: trap edges get quality +1.0, becoming attractors instead of warnings
- **Revisit penalty (K7)**: window of 3 states too small; 2-cycle traps escape detection

The user's reframe: *"Dass man sich kohärent irren kann, ist keine Überraschung. Die Frage ist, wo ist die Grenze des kohärenten Irrtums? Irgendwann passt was generell nicht mehr."*

Translation: coherent error is expected. The real question is — what structural signal reveals that things *globally* don't fit, even when each local signal says "fine"?

---

## 2. The Hypothesis: Structural Skepticism

**Claim:** Coherent deception produces a characteristic structural signature that is invisible to per-edge metrics but detectable via run-level meta-observation.

**The signature:** load accumulates without frontier expansion.

In a genuine productive run:
- New states are discovered (frontier grows)
- Load distributes across many edges (diverse inscription)
- Quality differentiates (some edges better than others)

Under coherent deception:
- The same states are revisited (frontier stagnates)
- Load concentrates on few edges (repetitive inscription)
- Quality is uniformly high (no differentiation)

These are **different modes** even though per-edge metrics (quality, load, inertia) look healthy in both cases.

---

## 3. Available Primitives (No New Parameters)

The mechanism uses only quantities already computed by E₀:

| Primitive | Source | What it reveals |
|-----------|--------|-----------------|
| `trace_load(e)` | Historization | How much inscription has occurred |
| `trace_quality(e)` | Historization | Outcome history of an edge |
| `unique_states` (from path) | RunTrace | Frontier expansion |
| `revisit_count` (from path) | RunTrace | Repetition rate |
| `T_s` | structural_temperature(hist) | System-level load/clarity ratio |
| `len(candidates)` | StepResult | Local branching factor |

**Key insight:** None of these individually detects coherent deception. The signal is in the *ratio* between them:

```
stagnation_score = load_growth / frontier_growth
```

High stagnation_score = system is working hard but going nowhere — even if every step "succeeds."

---

## 4. Design: Skepticism Monitor

A lightweight observer that runs alongside `cycle()` inside `run()`, computing window-based skepticism indicators.

### 4.1 Window-Based Metrics

Every W cycles (W = window size, e.g. 5), compute:

```
progress_rate   = new_states_in_window / W          ∈ [0, 1]
revisit_rate    = revisits_in_window / W             ∈ [0, 1]
quality_spread  = std(quality of edges traversed in window)
load_efficiency = frontier_growth / total_load_growth
```

### 4.2 Skepticism Trigger

```
SKEPTICAL when:
  progress_rate < ε_progress   (near zero — no new states)
  AND revisit_rate > ε_revisit  (high — cycling through known states)
  AND window > W_min            (give the system time to start)
```

The thresholds are derived from the system itself:
- `ε_progress`: If progress_rate = 0 for an entire window → definitely stagnant
- `ε_revisit`: If > 50% of window steps are revisits → definitely cycling

### 4.3 Response to Skepticism

**Level 1 — Exploratory Escape (C173):**
When stagnation triggers (progress_rate = 0), force the next cycle to pick the neighbor with the LOWEST trace_load (least-explored direction). Breaks out of loops.

**Level 2 — Self-Honesty Retreat (C174):**
When exploration consistently fails (new_failure_rate ≥ 0.8 on first-visit states), avoid known-bad neighbors (quality < 0) and prefer the least-loaded among non-negative-quality neighbors.

*Critical design insight:* The first L2 design (“prefer known-good”) failed. It sent the controller back to previously successful but unproductive states (E → START → loop). The corrected design (“avoid known-bad”) works because:

> **Truth is perspective — we cannot know what IS good.**  
> **Self-honesty is structural — we CAN know what HAS FAILED.**

Self-honesty is not “repeat what worked”. Self-honesty is “stop doing what fails.” The difference is between positive knowledge (unreliable) and negative knowledge (structural).

**Level 3 — Full Reset (not implemented):**
Clear traces on suspected-deceptive edges. Destructive — only appropriate as last resort.

**The two levels as structural duals:**

| Situation | Signal | Response | Principle |
|-----------|--------|----------|-----------|
| Stuck in loops | frontier = 0 | L1: go somewhere NEW | Curiosity |
| Exploring but failing | new states fail | L2: AVOID known-bad | Self-honesty |

### 4.4 What This Does NOT Do

- Does not add new primitives or parameters to the controller
- Does not modify historization data (Level 1)
- Does not require ground truth or semantic understanding
- Does not rely on a specific deception pattern — detects ANY stagnation

---

## 5. Test Design

Reuse the C172 adversarial scenarios with the Skepticism Monitor enabled:

### Scenario A: Hidden Reward Flip (+ Skepticism)
- Same domain: START → A → B → GOAL, trap loop A ↔ TRAP
- Without skepticism: 30 cycles trapped (C172 result)
- **Prediction:** Skepticism triggers after W cycles of A→TRAP→A→TRAP. Exploratory escape forces A→B. Goal reachable.

### Scenario B: Systematic Poisoning (+ Skepticism)
- Same domain: honest path vs poisoned path (C→D→C loop)
- Without skepticism: all 4 configs fail (C172 result)
- **Prediction:** Skepticism triggers on C→D→C cycling. Escape forces exploration of honest path. May not fully solve (depends on when trigger fires).

### Scenario C: Adversarial Peer (+ Skepticism)
- Same domain: branching graph with injected phantom states
- Without skepticism: 20 phantom states, 167% bloat (C172 result)
- **Prediction:** Harder to detect — frontier DOES grow (phantom states are "new"). But quality_spread might reveal it: phantom edges all FAILURE, real edges SUCCESS. The structural signal is different from A/B.

### Scenario D (NEW): Long Coherent Deception
- Extended domain with 20+ honest states, adversary lies for first 15 cycles then tells truth
- Tests: Does skepticism trigger too early (false positive on legitimate learning)?
- **Prediction:** Should NOT trigger during genuine exploration (progress_rate > 0, revisit_rate low).

---

## 6. Success Criteria

| Scenario | C172 Result | Target with Skepticism | Verdict Criterion |
|----------|-------------|------------------------|-------------------|
| A | FAIL (30 trap) | PASS (goal reached) | Goal reached after skepticism escape |
| B | FAIL (all 4) | PASS (at least 1 config) | Honest path discovered via escape |
| C | FAIL (167% bloat) | PARTIAL (reduced bloat) | Fewer phantom states visited |
| D | N/A | PASS (no false trigger) | No skepticism during genuine exploration |

**Overall success:** If A and B PASS and D does not false-trigger, Structural Skepticism is a viable defense layer.

---

## 7. Predictions

1. **Scenario A will PASS.** The trap loop is a textbook stagnation pattern: 2 states cycling, zero frontier growth. Skepticism monitor will detect this within 1–2 windows.

2. **Scenario B will likely PASS.** Same stagnation signature. The poisoned loop C→D→C is identical in structure to A's trap.

3. **Scenario C is uncertain.** Phantom state injection creates genuine frontier growth (each injected state is "new"). Skepticism's progress_rate will see expansion. The signal must come from quality_spread (phantom edges fail, real edges succeed) — which the current Level 1 design does not use for triggering. **Expected: PARTIAL at best.**

4. **Scenario D will PASS.** Genuine exploration has high progress_rate and low revisit_rate. Skepticism should not trigger.

---

## 8. Empirical Results

### 8.1 Scenario A: Hidden Reward Flip → PASS

| Metric | C172 (no skepticism) | C173 (+ skepticism) |
|--------|----------------------|---------------------|
| Steps | 30 (max) | 9 |
| Goal reached | No | **Yes** |
| Trap visits | 29 | 6 |
| Skepticism events | — | 1 (cycle 6) |

Path: `START → A → TRAP → A → TRAP → A → TRAP → A → B → GOAL`

Skepticism triggered at cycle 6 after one full window of zero frontier growth (A→TRAP→A→TRAP→A). Exploratory escape forced A→B (the least-loaded unvisited neighbor). Goal reached two steps later.

**Key finding:** The trap loop has a textbook stagnation signature. Detection took exactly W+1=6 cycles. The mechanism adds no false overhead — the system explores normally for the first 5 steps.

### 8.2 Scenario B: Systematic Poisoning → 4/4 PASS

| Config | C172 | C173 | Skepticism events |
|--------|------|------|-------------------|
| default | FAIL | **PASS** | 2 |
| + inertia | FAIL | **PASS** | 2 |
| + self_graph | FAIL | **PASS** | 2 |
| + inertia + sg | FAIL | **PASS** | 2 |

All 4 configs show identical behavior: poisoned loop C→D→C runs for 8 visits, skepticism triggers at cycle 6 and again at cycle 7 (two consecutive stagnation windows). Second escape forces D→GOAL (the least-loaded neighbor of D). Goal reached at step 9.

**Key finding:** Skepticism doesn't prevent initial deception — the controller still enters the poisoned loop. But it provides a *recovery mechanism*: once the loop is detected as structurally stagnant, escape forces exploration of edges the greedy policy would never choose (D→GOAL has R₀=3.0, far too expensive for greedy).

**Note:** Inertia and Self-Graph make no difference because the skepticism override is independent of per-edge metrics. Skepticism is a *structural-level* defense, not an edge-level one.

### 8.3 Scenario C: Adversarial Peer → FAIL (C173 L1) → PARTIAL (C174 L1+L2)

**C173 (Level 1 only):**

| Metric | C172 | C173 (L1) |
|--------|------|-----------|
| Steps | 40 (max) | 40 (max) |
| Goal reached | No | No |
| Fake states visited | 19 | 19 |
| Landscape bloat | 167% | 167% |
| Skepticism events | — | **0** |

L1 did NOT trigger. Each injected phantom state is *new*, so frontier grows. Stagnation signal is the wrong detector for injection attacks.

**C174 (Level 1 + Level 2 Self-Honesty):**

| Metric | C172 | C173 (L1) | C174 (L1+L2) |
|--------|------|-----------|---------------|
| Steps | 40 (max) | 40 (max) | **15** |
| Goal reached | No | No | **Yes** |
| Fake states visited | 19 | 19 | **4** |
| Peer consultations | 20 | 20 | **8** |
| Landscape bloat | 167% | 167% | **67%** |
| L2 events | — | — | **2** |

Path: `START → E → START → FAKE_1 → START → FAKE_2 → START → A → X1 → A → FAKE_5 → A → FAKE_6 → A → B → GOAL`

L2 triggered at cycle 5: new_failure_rate = 1.00 (all new states fail). Self-honesty response: avoid FAKE (q < 0), prefer A (q = 0, untried, lowest load). From A, controller reaches B → GOAL.

**Critical insight — the failed first design:**
The initial L2 (“prefer known-good”) chose E (quality +1.0, high load) over A (quality 0.0, load 0). Result: 23 L2 triggers, 13 fakes, FAIL. The system kept returning to a known-good dead end.

The corrected L2 (“avoid known-bad”) chose A (non-negative quality, lowest load) over E and FAKE. Result: 2 L2 triggers, 4 fakes, PASS.

The difference: truth is perspective (we cannot verify E is “good” in a productive sense), self-honesty is structural (we CAN verify FAKE is “bad” from historized FAILURE).

Verdict: **PARTIAL** (goal reached, 4 fake visits remain — not zero).

### 8.4 Scenario D: False-Positive Control → PASS

| Metric | Result |
|--------|--------|
| Steps | 20 |
| Goal reached | Yes |
| Unique states | 21 |
| Skepticism events | **0** |

Path: `S0 → S1 → S2 → ... → S19 → GOAL` (straight line, no detours)

No false positives. Genuine exploration has high progress_rate (1 new state per step) and zero revisit_rate. Skepticism correctly stays silent.

### 8.5 Results Summary

| Scenario | C172 | C173 (L1) | C174 (L1+L2) | Prediction (C173) | Match |
|----------|------|-----------|--------------|-------------------|-------|
| A (Trap Loop) | FAIL | **PASS** | **PASS** | PASS | ✅ |
| B (Poisoning, 4x) | 0/4 FAIL | **4/4 PASS** | **4/4 PASS** | PASS | ✅ |
| C (Adversarial Peer) | FAIL | FAIL | **PARTIAL** | uncertain | ✅ |
| D (False-Positive) | N/A | **PASS** | **PASS** | PASS | ✅ |

C174 transforms Scenario C from FAIL to PARTIAL with only one conceptual change: “avoid known-bad” instead of “prefer known-good.”

---

## 9. Architectural Implications

### 9.1 The Foundational Insight

> **Truth is perspective. Self-honesty is structural.**

This user observation resolves the C172 diagnosis (“E₀ has no ground truth”) not by adding ground truth, but by showing it was never needed. The system cannot know what is TRUE (that depends on perspective, context, the environment’s hidden state). But it CAN know what is SELF-INCONSISTENT:

- **Stagnation:** “I keep acting but nothing changes.” (L1)
- **Self-dishonesty:** “I keep exploring places that fail.” (L2)

Both are structural observations about the *relationship* between behavior and experience — not about the content of either.

### 9.2 Two Adversarial Modes, Two Structural Responses

| Mode | Mechanism | Structural Signal | Response | Principle |
|------|-----------|-------------------|----------|-----------|
| **Stagnation** | Attractive loops | Load ↑, frontier = 0 | L1: explore new | Curiosity |
| **Pollution** | Injected novelty | New states fail | L2: avoid known-bad | Self-honesty |

L1 alone solves A + B. L2 alone would not solve A + B (they don’t have new states to fail). L1 + L2 together solve A + B + C. The two levels are structurally dual: one forces openness (curiosity), the other forces caution (self-honesty).

### 9.3 Why “Avoid Known-Bad” Beats “Prefer Known-Good”

The failed first L2 design revealed a deep asymmetry:

- “Prefer known-good” = positive knowledge: “I know what works.”
  - Problem: “works” depends on context. E “works” (SUCCESS) but leads nowhere. The system cannot structurally verify productive success vs. unproductive success.

- “Avoid known-bad” = negative knowledge: “I know what fails.”
  - Strength: failure IS structural. FAILURE is historized. The system can verify: “I went to FAKE_1, outcome was FAILURE, this is recorded.”

Negative knowledge is structurally reliable. Positive knowledge is perspectival. This is why self-honesty (knowing your failures) is structural while truth-seeking (knowing what’s right) is not.

### 9.4 The Mechanism is Recovery via Self-Observation

Neither L1 nor L2 prevents initial deception. The controller still enters traps (A: 6 trap visits), poisoned loops (B: 8 poison visits), and visits some phantom states (C: 4 fakes). What they provide is:

- **Guaranteed exit** from stagnation (L1)
- **Guaranteed avoidance** of repeated failure (L2)

This is structurally analogous to E₀’s existing EXHAUSTED escalation but at a higher observation level. K7 sees 3 states; skepticism sees W=5 states across two dimensions (frontier growth AND outcome consistency).

### 9.5 Integration Path

Current implementation: external wrapper (`SkepticalRunner`) with monkey-patched `_penalized_tension`. Proves the concept.

**Integration options:**
1. **Minimal:** Add `skepticism_window` to `run()`. Track `_visited` + outcome records internally. Emit new `EscalationType.SKEPTICAL_L1` / `SKEPTICAL_L2`.
2. **Medium:** Two new escalation types with distinct recovery strategies in `_escalation_target()`. L1: least-loaded unvisited. L2: non-negative-quality, least-loaded.
3. **Full:** Integrate with Self-Graph — skepticism events as self-historization input (“the system detected self-inconsistency”).

**Recommended:** Option 2. Natural extension of existing escalation framework. Two enum values, two recovery functions, one window counter.

### 9.6 Remaining Open Questions

1. **Window size sensitivity:** W=5 works for these domains. Does it generalize?
2. **L1→L2 interaction:** Can L1 and L2 interfere? (Not observed in tests — they trigger on different signals.)
3. **Scenario C residual:** 4 fake states still visited. Can L2’s response be made faster (smaller window)?
4. **False positive under mixed outcomes:** What if a legitimate domain has 80%+ failure on new states? (E.g., hard exploration domains.) Could L2 suppress useful exploration?
5. **The philosophical residue:** Mechanical avoidance of known-bad IS self-honesty at the behavioral level. But does the system *understand* why it avoids? Or is “understanding” itself perspectival?
