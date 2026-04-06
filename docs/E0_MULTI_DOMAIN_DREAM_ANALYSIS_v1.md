# E₀ Multi-Domain Dream Analysis v1

**Date**: 2026-03-30  
**Context**: Pre-implementation analysis for C168  
**Question**: Does WL+Hungarian cross-domain translation generalize beyond near-isomorphic language pairs?

---

## 1. Mechanism: What WL+Hungarian Actually Does

### WL Fingerprints (81-dim at depth=2)

Each node gets an 81-dimensional feature vector:

| Round | Dimensions | Content |
|-------|-----------|---------|
| 0 | 9 | mean_q, std_q, degree, pos_frac, min_q, max_q, median_q, trace_load_mean, trace_load_std |
| 1 | +18 = 27 | For each of 9 Round-0 dims: (mean, std) over neighbors |
| 2 | +54 = 81 | For each of 27 Round-1 dims: (mean, std) over neighbors |

Features encode: **local quality statistics** × **recursive neighborhood context**.

### Hungarian Algorithm

Computes globally optimal 1:1 assignment minimizing total Euclidean distance across all node pairs. Returns `min(|V_a|, |V_b|)` matches. Uses `scipy.optimize.linear_sum_assignment`.

### What It Matches

Two nodes match when they have:
1. Similar edge quality distributions (Round 0)
2. Similar neighborhood quality patterns (Round 1+)
3. Similar degree (encoded as feature dim 2)

It does **not** match semantic meaning — it matches **structural fingerprint similarity**.

---

## 2. Why C137 Works: The Load-Bearing Assumptions

C137 achieved 44/44 = 100% cognate accuracy on EN↔DE. The pipeline:

```
Base canons (44 nodes each)
  → Add shared noise edges (100-300, mirrored across both languages)
  → LLM monolingual scoring (0-10 relatedness per language)
  → Inject scores → bootstrap landscapes
  → WL+Hungarian depth=2 → 44/44 correct
```

**Three conditions that make this work:**

1. **Isomorphic topology** — Noise edges are *mirrored*: if EN gets `finger→water`, DE gets `Finger→Wasser`. The graphs are isomorphic by construction.

2. **Correlated LLM scores** — "finger→hand" scores high in both English and German because the semantic relationship is language-independent. This creates correlated quality values across cognate pairs.

3. **Same node count** — Both landscapes have exactly 44 nodes, so Hungarian produces a perfect bijection.

C138c confirmed: **"Score correlation is the load-bearing assumption."** With uncorrelated scores, accuracy drops to near-random even on isomorphic topology.

---

## 3. Empirical Findings

### 3.1 Structural Survey of Available Canons

| Canon | |V| | |E| | avg_deg | q_mean | q_std |
|-------|-----|-----|---------|--------|-------|
| english_basic_enriched | 44 | 127 | 5.8 | 0.261 | 0.097 |
| german_basic_enriched | 44 | 135 | 6.1 | 0.266 | 0.090 |
| ontodynamics | 51 | 93 | 3.6 | 0.353 | 0.055 |
| ontodynamics_v1 | 19 | 31 | 3.3 | 0.406 | 0.092 |

EN and DE enriched are structurally similar (same |V|, similar |E|, similar quality distributions).
Ontodynamics is structurally different: more nodes, fewer edges, higher quality mean, narrower quality std, 53% degree-1 nodes.

### 3.2 Cross-Domain Distance Matrix (Curriculum-Trained)

All landscapes trained with `CurriculumRunner` + `Outcome.SUCCESS`:

| Pair | Matches | Mean Dist | Std | Range | Gap vs Reflexive |
|------|---------|-----------|-----|-------|-----------------|
| DE↔DE (reflexive) | 44 | **0.0000** | 0.0 | [0.00, 0.00] | baseline |
| EN↔DE (near-iso) | 44 | **0.3749** | 0.132 | [0.16, 0.64] | +0.37 |
| EN↔Onto (non-iso) | 44 | **0.8699** | 0.108 | [0.64, 1.12] | +0.87 |
| Onto↔Onto_v1 (same domain, diff scale) | 19 | **0.8798** | 0.181 | [0.65, 1.21] | +0.88 |
| DE↔Onto (non-iso) | 44 | **1.0138** | 0.104 | [0.81, 1.28] | +1.01 |

### 3.3 Key Finding: Perfect Separation

```
                    EN↔DE           EN↔Onto
                 [0.16 ──── 0.64] [0.64 ──── 1.12]
                                  ^
                         NO OVERLAP
```

The distance distributions do **not overlap** between near-isomorphic and non-isomorphic pairs. The worst EN↔DE match (0.64) equals the best EN↔Onto match (0.64). This means:

> **Mean WL distance is a reliable discriminator for structural compatibility.**

### 3.4 Cognate Accuracy

| Condition | Accuracy | Notes |
|-----------|----------|-------|
| C137 (LLM-scored, iso topology) | 44/44 (100%) | Correlated scores + mirrored edges |
| Raw canons EN↔DE | 1/15 (7%) | No score differentiation |
| Curriculum-trained EN↔DE | 1/15 (7%) | Training doesn't create semantic signal |

Curriculum training (always-SUCCESS execution) does **not** produce semantic differentiation. It adds uniform trace_load proportional to traversal frequency, which doesn't correlate across languages.

### 3.5 Structural Role Matching

| Pair | Degree Correlation (r) |
|------|----------------------|
| EN↔DE (raw) | 0.223 |
| EN↔Onto (raw) | 0.293 |
| EN↔DE (trained) | 0.223 |
| EN↔Onto (trained) | 0.387 |

Degree correlation is weak across all conditions. WL fingerprints include degree as only 1 of 81 features — quality statistics dominate the matching. Hub-to-hub mapping is not reliable.

---

## 4. Hypothesis Evaluation

### H1: Structural Role Transfer
**FALSIFIED.** WL+Hungarian does not reliably map nodes by structural role (hub↔hub, leaf↔leaf). Degree correlation r ≈ 0.2–0.4 across all conditions. Example: EN "self" (deg=11, biggest hub) → Onto "tension" (deg=3).

### H2: Distance Distribution as Discriminator
**CONFIRMED.** Mean WL distance perfectly separates near-isomorphic (0.37) from non-isomorphic (0.87–1.01) pairs after training. Zero overlap in ranges. This is a usable signal for "should these domains dream together?"

### H3: Cross-Domain Transfer Quality
**PARTIALLY CONFIRMED.** The matches are not semantically meaningful (for non-isomorphic domains there IS no "correct" mapping), but the *distance itself* carries information:
- Low distance → domains are structurally compatible → dream equivalences likely meaningful
- High distance → domains are structurally incompatible → dream equivalences are noise

### Emergent Finding: Same-Domain Different-Scale
Onto↔Onto_v1 (51 vs 19 nodes, same philosophical domain) produces mean distance 0.88 — nearly identical to cross-domain EN↔Onto (0.87). **Scale mismatch is as damaging as domain mismatch.** This makes sense: the 19-node Onto_v1 is a coarse abstraction of the 51-node Onto, so neighborhood structure is fundamentally different.

---

## 5. Implications for C168

### What Multi-Domain Dream Can Do

1. **Compatibility Scoring**: Use mean WL distance as a `dream_compatibility(domain_a, domain_b) → float` metric. Threshold ≈ 0.5 separates compatible from incompatible.

2. **Selective Dreaming**: DreamObserver should only run cross-domain matching on compatible pairs. Currently it matches ALL ready domain pairs — this wastes computation and produces noise for structurally incompatible domains.

3. **Transfer Confidence**: Each NodeEquivalence already has a `distance` field. For compatible domains, low-distance matches are high-confidence; for incompatible domains, even the best match is noise.

### What Multi-Domain Dream Cannot Do (Without Extension)

1. **Cross-domain semantic mapping** between structurally different domains. WL fingerprints match structure, not meaning. You need *correlated quality signals* (like LLM scoring) to get semantic correspondence.

2. **Scale-bridging**: Matching a 19-node domain to a 51-node domain doesn't work, even within the same conceptual space. You'd need a coarsening/refinement step.

3. **Topology-independent matching**: If two domains have genuinely different organizational principles (tree vs mesh, hub-and-spoke vs distributed), WL provides no meaningful mapping.

### Design Decision for C168

The falsification question "does WL+Hungarian work beyond isomorphic domains?" has a nuanced answer:

> **The matching itself degrades gracefully — but the degradation is detectable.** Mean WL distance is a reliable compatibility metric. The system can know when it's producing noise vs signal.

**Recommended C168 scope:**
1. `dream_compatibility()` function: pairwise structural compatibility metric
2. Compatibility-gated dreaming in DreamObserver: skip incompatible pairs
3. Exploration with trained landscapes (LLM-scored, not just curriculum) for genuinely different domains
4. Test: does LLM scoring create any correlation between truly different domains?

---

## 6. Open Questions

1. **Can LLM scoring create meaningful cross-domain correlations?** If an LLM scores "finger→hand" as 8/10 in English and "state→transition" as 8/10 in ontodynamics, that score correlation is semantically meaningless — but structurally it might still enable WL matching. Is that useful?

2. **What is the right threshold for dream_compatibility?** Our data suggests 0.5, but this is based on only 3 domain pairs. Need more data points.

3. **Can partial structure matching work?** Instead of matching the full graph, match subgraphs (clusters) across domains. A 5-node chain in EN might genuinely correspond to a 5-node chain in Onto if they share local quality patterns.

4. **Does the distance metric generalize to LLM-scored landscapes?** Our experiments used curriculum-trained (always-SUCCESS) landscapes. C137 used LLM-scored landscapes. The distance behavior might be different with richer quality differentiation.
