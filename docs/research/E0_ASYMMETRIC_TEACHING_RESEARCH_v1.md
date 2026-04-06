# E₀ Asymmetric Teaching — Research Note v1

**Date**: 2026-04-06  
**Context**: Q4 from Multi-Domain Dream Analysis + bootstrap next_steps  
**Prior work**: C168 (compatibility gating), C169 (threshold calibration), C170 (partial matching negative)

---

## 1. The Question

Two related sub-questions converge here:

**Q4 (from E0_MULTI_DOMAIN_DREAM_ANALYSIS_v1.md §6):**
> Does the distance metric generalize to LLM-scored landscapes?
> Our experiments used curriculum-trained (always-SUCCESS) landscapes.
> C137 used LLM-scored landscapes. The distance behavior might be
> different with richer quality differentiation.

**bootstrap.json next_steps:**
> Asymmetric teaching: what if LLMs evaluate differently per language?

C169 already answered the first part: dream_compatibility() works on LLM-scored
landscapes (LLM_MED↔LLM_COOK=0.342, correctly identified as compatible).

The remaining question is about **directional asymmetry**: If the LLM produces
richer quality differentiation in one language than another, does transfer
direction matter?

---

## 2. The Load-Bearing Assumption

From the Dream Analysis document:

> **Score correlation is the load-bearing assumption.**

C137 achieved 44/44 because:
1. EN and DE have isomorphic topology (same 44 nodes, mirrored edges)
2. LLM scores correlate across languages (finger→hand ≈ Finger→Hand)
3. WL fingerprints encode quality distributions → correlated scores → similar fingerprints

**The asymmetry risk:** LLMs are typically English-dominant. This could manifest as:

| Dimension | English | German | Impact |
|-----------|---------|--------|--------|
| Score resolution | Fine (2, 4, 7, 9) | Coarser (3, 5, 7, 8) | Lower q_std in DE |
| Edge differentiation | High variance | Lower variance | Flatter fingerprints in DE |
| Rare-word handling | Confident | Uncertain | More uniform scores in DE |

If EN has richer quality differentiation, then:
- EN→DE transfer (using EN's richer signal) should be more reliable
- DE→EN transfer (using DE's coarser signal) could be noisier

---

## 3. Current Symmetry in the Pipeline

The dream pipeline is **symmetric at every stage**:

| Component | Symmetry | Detail |
|-----------|----------|--------|
| `find_equivalences()` | Symmetric | Euclidean distance d(a,b) = d(b,a) |
| `find_wl_node_equivalences_hungarian()` | Symmetric | Global optimal bijection, same either direction |
| `dream_compatibility()` | Symmetric | Mean of Hungarian distances |
| `_update_dream_landscape()` | Symmetric | Bidirectional edges, same δ and R₀ |
| `feedback()` | Symmetric | Updates BOTH directions with same outcome |
| `dream_cycle()` | Symmetric | Unordered pairs, no direction distinction |

Directionality exists **only in application**: `propose_bridges()` targets a specific domain.

**Existing asymmetric mechanisms** (already in codebase):
- CouplingRouter (C67): R₀(A→B) = base_resistance / weight(B)
- `update_weights_from_dream()` (C157): per-domain weights from equivalence quality
- `cross_propose_edges()`: explicitly directional (donor → requester)

---

## 4. Empirical Questions for Exploration

### 4.1 Quality Differentiation
Do EN and DE canon landscapes (after curriculum training) actually show
different quality statistics? Measure per-landscape:
- q_std distribution across nodes
- trace_load variance
- WL fingerprint information content (variance across dimensions)

### 4.2 Fingerprint Asymmetry  
When computing WL fingerprints for EN and DE:
- Is the feature variance higher in one language?
- Does one language produce more "distinctive" fingerprints?
- Measure: per-node fingerprint norm, inter-node distance spread

### 4.3 Transfer Direction
Using the existing dream pipeline:
- Run dream_cycle with EN↔DE
- Compare bridge quality when EN donates to DE vs. DE donates to EN
- Does the donor's fingerprint quality predict transfer success?

### 4.4 LLM Scoring Asymmetry (if API available)
- Have an LLM score the same edges in both EN and DE
- Compare score distributions (resolution, variance, range)
- Feed into bootstrapper → compare resulting fingerprint quality

---

## 5. Natural Insertion Points for Asymmetry

If the exploration confirms directional asymmetry, the minimal code change:

**Option A: Directional feedback (smallest change)**
Make `feedback()` update only the direction actually used. Over time, the Dream
Landscape develops directional trace_quality. Everything downstream (equivalences_for,
propose_bridges, dream_coupling_discount) automatically becomes asymmetric.

**Option B: Fingerprint-weighted compatibility**
Weight the compatibility score by fingerprint quality: a high-information domain
paired with a low-information domain gets an intermediate score, but transfer
direction is flagged.

**Option C: Domain quality metadata**
Add a `domain_info_quality` metric (e.g., mean fingerprint variance) to
DreamObserver. Use it in propose_bridges to prefer high-quality donors.

Option A is the most principled: it introduces no new parameters and lets
asymmetry emerge from data rather than imposing it structurally.

---

## 6. Prediction

Based on C169 results (training shifts compatibility by <0.002, WL fingerprints
are topology-dominated):

**Hypothesis:** For curriculum-trained canons (always-SUCCESS), quality
differentiation will be minimal because all edges get uniform U/F traces.
Asymmetry should only manifest with LLM-scored landscapes where the LLM
produces genuinely different score distributions per language.

If confirmed, asymmetric teaching is relevant **only** for LLM-bootstrapped
domains — not for curriculum-trained canons. This would scope the feature
precisely.
