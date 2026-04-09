# E₀ Dream Mode — Cross-Domain Pattern Recognition through Passive Observation

**Status**: Implemented (C109–C112)  
**Date**: 2026-04-02  
**Depends on**: C94–C97 (Observation Layer), C62/C107 (Cross-Reflexion), C66–C67 (CouplingRouter)  
**Canon alignment**: §5 Reflexivity Emergence, §9 Structural Admissibility

---

## 1. Problem Statement

E₀ currently operates in isolated domains. Cross-reflexion (C62) transfers patterns between universes, but only when triggered by frontier stagnation — it's reactive. The Observer (C94–C97) can passively inspect a single domain but produces no output beyond projections.

**Missing capability**: There is no mechanism that passively watches multiple domains and recognizes that structurally different situations share the same functional signature. This is exactly what analogical reasoning does — and what happens in dreams: reorganization without intervention.

**The gap in E₀ terms**: Two edges in different domains with similar historization profiles (similar trace_quality, similar trace_load trajectory, similar inertia_factor) are *functionally equivalent* — they play the same navigational role despite operating in completely different state spaces. No current mechanism detects or exploits this.

---

## 2. Core Idea

**Dream Mode = Passive multi-domain observation → functional equivalence detection → bridge hypothesis generation.**

Three properties distinguish Dream Mode from existing mechanisms:

| Property | Reflexion (Stufe 1–3) | Cross-Reflexion (C62) | Dream Mode |
|---|---|---|---|
| Trigger | Stuck / frontier | Frontier stagnation | Continuous (passive) |
| Action | Modifies own landscape | Proposes edges from donor | Generates bridge hypotheses |
| Scope | Single domain | Two coupled universes | N domains, uncoupled |
| Mutation | Yes (adds/modifies edges) | Yes (proposes edges) | **No** (hypothesis only) |
| Output | Modified landscape | ProposedEdge list | Equivalence map + bridge candidates |

The key constraint: **Dream Mode never modifies any domain.** It produces a *hypothesis landscape* — a separate structure that maps functional equivalences across domains. These hypotheses become actionable only when explicitly consumed by cross-reflexion or a controller.

---

## 3. Mechanism

### 3.1 Edge Fingerprint

Every edge in any domain has a historization profile that evolves over time. We define an **edge fingerprint** as the tuple:

```
f(e) = (trace_quality(e), trace_load(e), inertia_factor(e))
     = (q, m, I) ∈ (-1,1) × [0,∞) × [0,1]
```

Two edges $e_A$ in domain A and $e_B$ in domain B are **functionally equivalent** if their fingerprints are close:

$$d_f(e_A, e_B) = \sqrt{(q_A - q_B)^2 + \left(\frac{m_A}{m_A + \mu} - \frac{m_B}{m_B + \mu}\right)^2 + (I_A - I_B)^2}$$

The trace_load term is normalized via the same $m/(m+\mu)$ sigmoid used in inertia_factor, ensuring scale-invariance across domains with different activity levels.

### 3.2 Functional Equivalence Threshold

Two edges are functionally equivalent when $d_f < \epsilon$ with $\epsilon$ a domain-pair-specific threshold. We do **not** fix $\epsilon$ globally — the Dream Mode discovers it empirically:

1. Compute all pairwise $d_f$ between domain A edges and domain B edges
2. The distribution of $d_f$ values determines what counts as "close"
3. Equivalences in the bottom quantile (e.g., 10th percentile) are candidates

This avoids arbitrary thresholds and lets the mechanism adapt to domain-pair similarity.

### 3.3 Dream Landscape

The Dream Mode produces a **Dream Landscape** $L_D$ where:

- **States** = domain-qualified edges: `"A:src→tgt"`, `"B:src→tgt"`
- **Edges** = functional equivalences between domain edges
- **Δ** = fingerprint distance $d_f$ (low distance = high similarity = high relevance)
- **R₀** = baseline cost of recognizing the equivalence (parameterized)
- **Historization** = tracks which equivalences have been useful (consumed by cross-reflexion and led to SUCCESS)

The Dream Landscape is itself a valid E₀ Landscape. It can be navigated by E0Controller. It historizes. It has trace_quality. This means: **E₀ learns which cross-domain analogies are productive and which are noise.**

### 3.4 Bridge Hypothesis

A **bridge hypothesis** is a ProposedEdge in domain A, derived from a functionally equivalent edge in domain B:

```
Given: e_B = Edge(src_B, tgt_B) in domain B with fingerprint f(e_B)
       e_A_partial = some edge in domain A with similar fingerprint
       
Hypothesis: If src_B→tgt_B works well in B (high q, high m),
            and node X in A has structural similarity to src_B,
            then X→Y (for some appropriate Y) might work in A.
```

The hypothesis is a `ProposedEdge` with:
- `confidence` = 1 − $d_f$ (higher confidence for closer fingerprints)
- `resistance` = scaled by inverse confidence (speculative hypotheses are expensive)
- `rationale` = references the source domain and equivalent edge

Bridge hypotheses are stored in the Dream Landscape and offered to cross-reflexion when a domain requests help.

---

## 4. Architecture

### 4.1 Component Diagram

```
┌──────────────────────────────────────────────┐
│                  DreamObserver                │
│                                              │
│  ┌─────────────┐  ┌─────────────┐            │
│  │ ObsCtrl(A)  │  │ ObsCtrl(B)  │  ...       │
│  │ (read-only) │  │ (read-only) │            │
│  └──────┬──────┘  └──────┬──────┘            │
│         │                │                    │
│         ▼                ▼                    │
│  ┌──────────────────────────────┐            │
│  │    Fingerprint Extraction    │            │
│  │  f(e) = (q, m, I) per edge  │            │
│  └──────────────┬───────────────┘            │
│                 │                             │
│                 ▼                             │
│  ┌──────────────────────────────┐            │
│  │  Equivalence Detection       │            │
│  │  d_f(e_A, e_B) < ε(A,B)     │            │
│  └──────────────┬───────────────┘            │
│                 │                             │
│                 ▼                             │
│  ┌──────────────────────────────┐            │
│  │  Dream Landscape L_D         │            │
│  │  (E₀ Landscape — navigable)  │            │
│  └──────────────┬───────────────┘            │
│                 │                             │
│                 ▼                             │
│  ┌──────────────────────────────┐            │
│  │  Bridge Hypothesis Generator  │            │
│  │  → ProposedEdge candidates    │            │
│  └───────────────────────────────┘            │
└──────────────────────────────────────────────┘
         │
         ▼ (on request)
  ┌──────────────────┐
  │  cross_reflexion  │ ← consumes bridge hypotheses
  │  coupling_router  │ ← uses equivalence map for partner selection
  └──────────────────┘
```

### 4.2 Data Flow

1. **Input**: N domain landscapes (read-only references)
2. **Observation**: DreamObserver holds N ObservationControllers, navigates each passively
3. **Fingerprinting**: At `dyn` depth, extract (q, m, I) for all visible edges in each domain
4. **Matching**: Compute pairwise fingerprint distances across domains
5. **Dream Landscape**: Build/update $L_D$ with equivalences as edges
6. **Hypotheses**: On query, extract bridge hypotheses from high-equivalence regions
7. **Consumption**: Cross-reflexion or controller consumes hypotheses like any ProposedEdge

### 4.3 Integration with Existing Infrastructure

| Component | Integration |
|---|---|
| `ObservationController` | One per domain, used for projection (no new API needed) |
| `Landscape` | Dream Landscape is a standard Landscape instance |
| `Historization` | Dream equivalences historize — productive analogies strengthen |
| `cross_reflexion.blend_patterns()` | Bridge hypotheses feed directly as donor patterns |
| `CouplingRouter` | Equivalence density between domains → coupling_weight bias |
| `ModeController` | Dream Mode runs in LEARN mode (exploring analogies) |
| `SelfGraph` | Dream accuracy could feed self-graph component assessment |

---

## 5. Formal Properties

### 5.1 No New Primitives

Dream Mode introduces **zero new primitives**. It composes:
- Landscape (states, edges, Δ, R₀, historization) — for Dream Landscape
- ObservationController (project, navigate) — for passive domain access
- Fingerprint = (trace_quality, trace_load, inertia_factor) — already computed
- ProposedEdge — existing dataclass from cross_reflexion

This satisfies Canon §7 (domain invariance) and §8 (architectural non-uniqueness): Dream Mode is not a new mechanism, it is E₀ applied to the problem of recognizing E₀ patterns.

### 5.2 Passivity Constraint (No Mutation)

Dream Mode **never** calls:
- `landscape.set_delta()`
- `landscape.add_state()` / `add_edge()`
- `historization.update()`

on any domain. It only reads projections via `ObservationController.project()`. The Dream Landscape is a separate structure. This is the formal equivalent of "you cannot intervene in a dream."

### 5.3 Self-Limiting Behavior

The Dream Landscape historizes. If an equivalence is consumed and leads to FAILURE in the target domain, the Dream Landscape's trace_quality for that equivalence becomes negative. R_eff increases. The system stops proposing that analogy.

Bad analogies die through the same mechanism that kills bad edges in any E₀ domain.

### 5.4 Convergence

In the limit, the Dream Landscape converges to a stable map of productive cross-domain analogies. trace_load grows on equivalences that get repeatedly confirmed, inertia_factor settles, and the bridge hypothesis list stabilizes. This is the same convergence behavior as any E₀ domain (C78, C108).

---

## 6. Testable Predictions

### P1: Functional Equivalence is Detectable
Given two structurally different domains that share a navigational pattern (e.g., "avoid the high-resistance corridor"), edges implementing that pattern should have $d_f < \epsilon$ while unrelated edges should not.

### P2: Bridge Hypotheses Accelerate Learning
When domain A is stuck at a frontier and the Dream Landscape offers bridge hypotheses from domain B, domain A should reach goal faster than with random edge proposals (and no slower than with standard cross-reflexion).

### P3: Bad Analogies Self-Correct
Deliberately inject a false equivalence (connect edges with opposite trace_quality). After consumption and FAILURE feedback, the Dream Landscape should suppress that equivalence — trace_quality drops below 0, R_eff rises.

### P4: Historization Filters Noise
In domains with many edges but few true equivalences, the Dream Landscape should converge to a sparse set of high-trace_load equivalences (most candidates pruned by low trace_quality).

### P5: Domain Order Does Not Matter
Observing domains in order A→B→C should produce the same stable equivalence map as B→C→A (up to historization noise). The Dream Landscape's structure reflects domain relationships, not observation order.

---

## 7. Implementation Plan

### Phase 1: Fingerprint + Equivalence (C109)
- `edge_fingerprint(edge, landscape) → (q, m, I)` — extract from historization
- `fingerprint_distance(f1, f2, mu) → float` — normalized distance
- `find_equivalences(landscape_a, landscape_b, mu, quantile) → List[Equivalence]`
- Tests: P1 (detectable), P5 (order-invariant)

### Phase 2: Dream Landscape (C110)
- `DreamObserver` class: holds N ObservationControllers
- `build_dream_landscape(equivalences) → Landscape`
- `dream_cycle(observer) → updated Dream Landscape` — one observation pass
- Tests: P4 (noise filtering), dream landscape is valid E₀ landscape

### Phase 3: Bridge Hypothesis Generation (C111)
- `propose_bridges(dream_landscape, target_domain, frontier_node) → List[ProposedEdge]`
- Integration with `cross_reflexion.blend_patterns()` — dream patterns as additional donor
- Tests: P2 (acceleration), P3 (self-correction)

### Phase 4: Exploration Script (C112)
- `explore_dream_mode.py` — end-to-end demonstration
- Multiple domain types (gridworld, corridor, chess-like)
- Measure: transfer acceleration, equivalence precision, convergence speed
- Write up findings for potential P7 paper section

---

## 8. Design Decisions (resolved)

### Q1: Observation Depth for Fingerprinting → Start with `dyn`, extend empirically
Fingerprints require `dyn` depth (trace_load, trace_quality). We start there. If we encounter domains where fingerprints are identical but topology diverges (recognition limit), we extend to topology-matching. This is an empirical boundary, not an upfront architecture decision.

### Q2: Temporal Dynamics → Already solved by self-historization
Temporal evolution of equivalences *is* historization on the Dream Landscape. trace_load on an equivalence edge shows how long the analogy has existed. trace_quality shows whether it was productive. The Dream Landscape historizes itself — like any E₀ Landscape. No additional mechanism needed.

### Q3: Dream Frequency → Data-driven via dream_readiness
Neither continuous (too expensive) nor process-bound ("after task X" — E₀ has no process concept; this would violate structural admissibility). Instead, self-triggered by domain stability:

```
dream_readiness(domain) = mean(inertia_factor(e) for e in domain.edges)
```

When `dream_readiness > threshold`, fingerprints have stabilized enough for cross-domain comparison. This mirrors natural dreaming: you don't dream about experiences *while* they happen — you dream about consolidated experience, when patterns have settled. The mechanism is:
- Not processual (no "after step N" or "at task end")
- Not continuous (not every step)
- Data-driven (E₀ decides when a domain is ripe)
- Self-consistent (inertia_factor is already computed, zero new primitives)

Reflexion runs synchronously because it *writes* to the landscape — the next decision needs the result. Dream Mode only *reads* — its output waits in the Dream Landscape until requested. Therefore it does not need to run synchronously.

### Q4: Scaling → Practical for current scale, three strategies for growth
O(N²·E²) is tractable for our scale (2–5 domains, 10–100 edges each). For future growth:
1. **Observation scope**: Compare only edges visible in current scope, not all
2. **Incremental**: Re-compare only edges whose fingerprint changed since last cycle (Δ trace_load > ε)
3. **Bin quantization**: Discretize fingerprints into bins (q→0.1 steps, m/(m+μ)→0.1, I→0.1 = 2000 bins). Hash-match within bins instead of brute force.

---

## 9. The Dream Analogy — Why It Fits

| Dream Property | E₀ Dream Mode |
|---|---|
| Cannot intervene | Passivity constraint: no domain mutation |
| Patterns reorganize | Equivalences detected across unrelated domains |
| Not goal-directed | Dream cycle runs without specific frontier need |
| Output is implicit | Bridge hypotheses stored, not immediately applied |
| Useful only sometimes | Most equivalences are noise; historization filters |
| Happens during "rest" | Triggers when domain is stable (dream_readiness) |
| Same brain, different mode | Same E₀ primitives, different composition |

The key structural insight: **Dreams are E₀ running on the observation of E₀, without write permission.** Reflexion is E₀ modifying E₀. Cross-reflexion is E₀ domains exchanging patterns. Dream Mode is E₀ recognizing that patterns exist across domains — without being asked, and without acting on it until asked.

---

*This concept note will be refined after user review. Implementation begins with Phase 1 (C109) only after conceptual approval.*
