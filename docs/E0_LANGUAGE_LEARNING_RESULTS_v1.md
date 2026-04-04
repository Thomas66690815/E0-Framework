# E₀ Language Learning — Experimental Results v1

**Status:** Active — C124–C137 arc documented  
**Supersedes:** Pre-implementation concept in `E0_LANGUAGE_LEARNING_CONCEPT_v1.md`  
**Date:** 2026-04-04  
**Scope:** 15 explorations, 14 experiments, 3 falsifications, 2 breakthroughs  
**Tests:** 3499 (suite total, experiments are explorations not unit-tested)

---

## 1. Summary

E₀ learns unknown word translations from known ones by comparing structural
fingerprints across two independently learned vocabulary graphs (EN, DE).

**Phase 1 (C124–C128, seed-based):** Starting from 11 known translation pairs
(Config B), the system discovers new pairs through iterative bootstrap.
Level-3 Neighborhood Consistency (C128) achieves **100% confirmed accuracy**
(4/4 promoted = all correct) but saturates at 15/44.

**Phase 2 (C129–C137, seedless):** Can E₀ identify ALL 44 translations
without ANY seed? LLM teaches each language monolingually, then structural
matching discovers correspondences. **C137 achieves 44/44 = 100% correct,
0 wrong — pure structural identification without position knowledge.**

**Core insight:** "Sprache sind nicht Wörter sondern Bedeutungen, also
eigentlich selbst in einer Relation." Meaning is relational — a word's
identity is defined by its connections, not its isolated fingerprint.

---

## 2. Architecture

### 2.1 Canons

Two parallel vocabulary graphs (C124/C124b):

| Canon | Nodes | Edges | Levels | Unique edges |
|---|---|---|---|---|
| english_basic | 44 | 64 | 6 (L0–L5) | 5 EN-only |
| german_basic | 44 | 64 | 6 (L0–L5) | 5 DE-only |

Differentiated deltas (0.1–0.7) by relationship type.  ~26 divergent delta
values between canons (e.g., action→make: EN δ=0.5, DE δ=0.3 — reflecting
etymology).  5 EN-only + 5 DE-only edges create topological asymmetry.

### 2.2 Ground Truth

44 EN↔DE translation pairs across levels L0–L5:
- L0 primitives: thing↔ding, action↔handlung, quality↔eigenschaft, relation↔beziehung
- L1 domains: body↔koerper, food↔essen_n, self↔selbst
- L2 body parts: head↔kopf, hand↔hand, arm↔arm, foot↔fuss, eye↔auge, mouth↔mund, ear↔ohr
- L2 food items: water↔wasser, bread↔brot, fruit↔frucht, milk↔milch, salt↔salz
- L3 derived: finger↔finger, apple↔apfel, 10 verbs, 8 adjectives, 5 prepositions

### 2.3 Starting Dictionaries

**Config B** (11 canonical pairs — used in all experiments from C125 onward):

| Dictionary | Pairs |
|---|---|
| body | hand↔hand, arm↔arm, finger↔finger, ear↔ohr, hear↔hoeren |
| food | bread↔brot, water↔wasser, milk↔milch, salt↔salz, eat↔essen_v, drink↔trinken |

Config A (8 pairs, nouns only) was tested in C125 and produced weaker
discrimination (61% vs 73%).  All subsequent experiments use Config B.

### 2.4 Core Mechanism

```
                  ┌─────────────┐
                  │  Config B   │ (11 known pairs)
                  │ Partial Dict│
                  └──────┬──────┘
                         │ provides SUCCESS/FAILURE
              ┌──────────┼──────────┐
              ▼                     ▼
     ┌────────────────┐   ┌────────────────┐
     │   EN Landscape  │   │   DE Landscape  │
     │ curriculum learn│   │ curriculum learn│
     │ + full coverage │   │ + full coverage │
     └────────┬───────┘   └────────┬───────┘
              │                     │
              ▼                     ▼
     ┌────────────────┐   ┌────────────────┐
     │ EN Fingerprints│   │ DE Fingerprints│
     │ f(e)=(q,m,I)   │   │ f(e)=(q,m,I)   │
     └────────┬───────┘   └────────┬───────┘
              │                     │
              └──────────┬──────────┘
                         ▼
              ┌────────────────────┐
              │ find_equivalences  │ (quantile=0.15)
              │ EN×DE fingerprint  │
              │ distance matching  │
              └──────────┬─────────┘
                         ▼
              ┌────────────────────┐
              │ extract_best_      │
              │ correspondences    │ (bijective mutual best match)
              │ → new word pairs   │
              └──────────┬─────────┘
                         ▼
              ┌────────────────────┐
              │ expand dictionary  │ → next round
              └────────────────────┘
```

**Fingerprint**: f(edge) = (trace_quality, trace_load, inertia_factor)  
**Distance**: d(a,b) = √(dq² + dm² + di²) with sigmoid-normalized load  
**Equivalence**: edge pairs with distance in bottom 15%-quantile  
**Correspondence**: (EN_node, DE_node) from bijective mutual-best-match voting

---

## 3. Validation Levels — Theory and Practice

The concept document (§9) predicted three validation levels.  All three
were implemented and tested.  The progression validated the theoretical
hierarchy.

### Level 1: Target Known? (C125, C126, C126b, C126c)

```python
execute(source, target) → SUCCESS if target ∈ known else FAILURE
```

Validates the endpoint, not the edge.  `body→hand`, `arm→hand`, `take→hand`
all succeed identically.  Fast bootstrap, but easily floods SUCCESS as the
dictionary grows.

### Level 2: Pair-Based (C127, C127b)

```python
p(SUCCESS) = w(source) × w(target)
```

Multiplicative weighting: both endpoints must be known.  3× more restrictive
than Level 1 at baseline (8% vs 23% SUCCESS).  Prevents distance collapse.

### Level 3: Neighborhood Consistency (C128)

```python
w(effective) = base_weight × max(context_score, 0.1)
```

Context score = bidirectional neighborhood consistency:
- Forward: translate EN neighbors → are they DE neighbors of candidate?
- Backward: reverse-translate DE neighbors → are they EN neighbors?
- score = matches / translatable_neighbors

Validates relational identity, not just vote count.

---

## 4. Experimental Progression

### C124/C124b — Canon Construction

Built english_basic and german_basic canons (44 nodes, 64 edges each).
Differentiated deltas (0.1–0.7).  Without dictionary-mediated execute_fn,
Dream Mode found 614 equivalences at q=0.000 — zero discrimination.

**Finding**: Uniform SUCCESS produces no fingerprint differentiation.
Partial reality barrier is necessary.

### C125 — Dictionary-Mediated Learning

First successful experiment.  PartialDictionary + make_dict_execute create
heterogeneous fingerprints.  Full-coverage exploration (run from every node)
critical — curriculum alone covers only ~34% of edges.

| Config | Known pairs | Correct unknown translations | Accuracy |
|---|---|---|---|
| A (nouns only) | 8 | 25/41 in top-20 | 61% |
| B (nouns+verbs) | 11 | 30/41 in top-20 | 73% |

**Finding**: More known words = better discrimination.  Verb inclusion
breaks same-part-of-speech symmetry.

### C126 — Iterative Bootstrap

First bootstrap loop: discoveries from round N become dictionary entries
for round N+1.  4 rounds from Config B.

| Round | Dictionary | Discoveries | Accuracy |
|---|---|---|---|
| 1 | 11 → 16 | 5 new (3✓ 2✗) | 60% |
| 2 | 16 → 22 | 6 new (2✓ 4✗) | 33% |
| 3 | 22 → 25 | 3 new (1✓ 2✗) | 33% |
| 4 | 25 → 25 | 0 (saturated) | — |

**Finding**: Ungated expansion contaminates.  Wrong pairs enter dictionary,
distort fingerprints, cause cascading errors.  Rankings degrade:
mouth goes from 6%ile (R1) to 16%ile (R4).

**FALSIFICATION**: Iterative bootstrap without quality control degrades.

### C126b — Confidence-Gated Bootstrap

Added min_confidence threshold: only discoveries with votes ≥ 6 enter
the dictionary.  Compared gated vs ungated side by side.

| Variant | Growth | Accuracy | Rankings |
|---|---|---|---|
| Ungated (min=2) | 11→25 | 40% | DEGRADE |
| Gated (min=6) | 11→16 | 100% added | STABLE |

**Finding**: Quality gating preserves discrimination but limits growth.
Good discoveries (mouth↔mund, head↔kopf) blocked by threshold.

### C126c — Weighted 3-Tier Dictionary

Graduated expansion with three tiers:

| Tier | Weight | Behavior |
|---|---|---|
| canonical | 1.0 | Permanent, original Config B |
| tentative | 0.2–0.7 | Stochastic SUCCESS, boost/decay per round |
| confirmed | 1.0 | Promoted tentative, permanent |

**Result**: 4/4 confirmed pairs = 100% correct.  body↔koerper worked
its way from tentative R5 to confirmed R6.

**FALSIFICATION of mechanism**: Distance collapse by R2 (distinct
distances: 53→1→1→1...).  Level-1 floods SUCCESS as tentative entries
grow → all fingerprints converge → Dream Mode's quantile threshold
returns noise.

### C127 — Level-2 Pair-Based Validation

**BREAKTHROUGH**: Distance collapse prevented.

```
Distance diversity:
  Level-1 (C126c): 53 → 1 → 1 → 1 → 1 → 1 → 1 → 1   (collapse R2)
  Level-2 (C127):  64 → 52 → 99 → 154 → 116 → 135 → 77 → 68  (preserved!)
```

Multiplicative weighting p(SUCCESS) = w_source × w_target keeps SUCCESS
tight.  R7 produced 5✓ 0✗ (100% correct discoveries).  20/32 unknown
pairs in top-10%ile.

**Remaining problem**: Rankings oscillate between rounds (mouth:
3→5→11→20→28→3→8→7→5→4).  Stochastic execute_fn generates different
fingerprint patterns each round.

### C127b — Cumulative Vote Historization

Replaced per-round boost/decay with pure cumulative voting:
weight = min(cumulative_votes/30, 0.95).

**Hypothesis**: Cumulative votes = historization.  Correct pairs get
consistently voted → weight grows.  Wrong pairs get sporadic votes →
weight stays low.

**FALSIFICATION**: Wrong pairs also accumulate consistently.

| Entry | Cum. votes | Correct? | Root cause |
|---|---|---|---|
| quality↔eigenschaft | 44 | ✓ | |
| relation↔essen_n | 36 | **✗** | 12v per round, systematic structural false match |
| action↔handlung | 30 | ✓ | |
| food↔beziehung | 28 | **✗** | 13v R2 + 15v R6 |

Confirmed: 2/4 = 50%.  Pure accumulation amplifies systematic structural
false matches identically to correct signals.  The problem is not noise
(which accumulation fixes) — it is systematic false correspondence.

### C128 — Level-3 Neighborhood Consistency

**SOLUTION**: Validate candidates by checking structural neighborhood
consistency.

For each candidate pair en↔de:
- Forward: EN neighbors of en → translate via dictionary → in DE neighbors of de?
- Backward: DE neighbors of de → reverse-translate → in EN neighbors of en?
- context_score = matches / translatable_neighbors

Weight model: w = base_weight × max(context_score, 0.1)  
Promotion requires: cumulative_votes ≥ 25 **AND** context_score ≥ 50%

**Result**: 4/4 confirmed = 100% correct.

| Entry | Cum. votes | Context score | Promoted? |
|---|---|---|---|
| food↔essen_n | 32 | 100% (13/13) | R2 ✓ |
| quality↔eigenschaft | 126 | 50% (5/10) at promotion | R7 ✓ |
| action↔handlung | 27 | 67% (4/6) at promotion | R7 ✓ |
| relation↔beziehung | 72 | 100% (2/2) at promotion | R8 ✓ |

**C127b falsification resolved**:
- relation↔essen_n: **never appeared as discovery**.  essen_n's neighbors
  (wasser, brot, salz, milch) reverse-translate to (water, bread, salt,
  milk) — NOT neighbors of relation.  ctx=0% → effective weight ≈ 0 →
  suppressed by context-weighted execute_fn.
- food↔beziehung: also never appeared.  food's neighbors translate to
  wasser, brot, salz → NOT neighbors of beziehung → ctx=0%.

**Context score as discriminator** (wrong entries from C128 tentatives):

| Entry | Cum. votes | Context | Correct? |
|---|---|---|---|
| thing↔ding | 19 | 71% (5/7) | ✓ — on path to promotion |
| self↔selbst | 3 | 57% (4/7) | ✓ — too few votes |
| take↔machen | 2 | 100% (4/4) | ✗ — wrong but structurally plausible! |
| go↔kalt | 5 | 0% (0/3) | ✗ — caught by context |
| thing↔kalt | 12 | 0% (0/6) | ✗ — caught by context |
| mouth↔koerper | 6 | 0% (0/8) | ✗ — caught by context |

Note: take↔machen has ctx=100% but only 2 votes — the double-gate
(votes+context) prevents false promotion.

---

## 5. Comparison Table

| Experiment | Validation | Growth | Confirmed | Distance | Problem |
|---|---|---|---|---|---|
| C126 ungated | L1 | 11→25 | — | collapse | Contamination cascade |
| C126b gated | L1 | 11→16 | — | stable | Limited growth |
| C126c weighted | L1 | 11→15 | 4/4=100% | **collapse R2** | Distance collapse |
| C127 L2 | L2 | 11→12 | 1/1=100% | preserved | Rankings oscillate |
| C127b cumul | L2+cumul | 11→15 | **2/4=50%** | preserved | **False matches amplified** |
| **C128 context** | **L2+L3** | **11→15** | **4/4=100%** | preserved | Saturation at 15/44 |

---

## 6. Principled vs Heuristic Components

### Principled (derived from E₀ theory)

| Component | Basis | Reference |
|---|---|---|
| Edge fingerprint f(e) = (q, m, I) | Direct from Historization layer | C109, Ontodynamics §4 |
| Fingerprint distance | Euclidean with sigmoid normalization | C109, μ from C105 |
| Quantile-based equivalence threshold | Parameter-free (relative, not absolute) | C109, dream_mode.py |
| Bijective mutual-best-match | Structural constraint (1:1 mapping) | C126 |
| Context score (neighborhood consistency) | L3 — meaning is relational | C128 |
| Multiplicative L2 validation | Both endpoints must be known | C127 |
| Curriculum + full-coverage learning | Derivation-order + exhaustive exploration | C123/C125 |

### Heuristic (experimentally tuned, could be derived)

| Parameter | Value | Sensitivity | Path to derivation |
|---|---|---|---|
| VOTE_SCALE=30 | votes → weight mapping | Low — scales linearly, only affects speed | Could be |E|/|V| analog to μ |
| PROMOTION_VOTES=25 | confirmation threshold | Moderate — lower catches more but risks false positives | Statistical significance test? |
| MIN_CONTEXT_SCORE=0.5 | "half your neighbors must match" | **Low** — natural threshold (majority) | Information-theoretic derivation possible |
| STALE_ROUNDS=3 | garbage collection | Very low — only affects cleanup timing | Irrelevant for core mechanism |
| MIN_STALE_VOTES=5 | garbage collection | Very low | Irrelevant for core mechanism |
| quantile=0.15 | equivalence threshold | Moderate — affects discovery sensitivity | Could adapt via T_s |

---

## 7. Phase 2: Seedless Structural Matching (C129–C137)

### 7.1 The Seedless Question

C124–C128 require 11 known translation pairs to bootstrap. **Can E₀ discover
ALL 44 translations without any seed at all?** This shifts the problem from
"iterate with partial knowledge" to "identify structure from scratch."

### 7.2 Architecture Evolution (C129–C132)

| Experiment | Approach | Result | Finding |
|---|---|---|---|
| C129 | Seed expansion (11→more→dream) | Marginal | More seeds don't help — the mechanism saturates |
| C130 | Enriched canon (>64 edges) | **FALSIFIED** | More edges ≠ more signal — degrades discrimination |
| C131 | Bilingual LLM teacher | 13/44 (seed=11) | LLM as bilingual validator works but still needs seed |
| C132 | Bilingual LLM teacher refined | 20/44 (seed=8) | Better, but bilingual leaks cross-language info |

**Key insight (C132):** Bilingual teaching introduces implicit cross-language
leakage. The LLM sees both languages and its evaluations subtly correlate
translation pairs. This is architecturally impure.

### 7.3 Monolingual Teaching (C133–C134)

**Phase 1 redesign:** The LLM teaches each language SEPARATELY. It never
sees both languages simultaneously — no cross-language leakage.

#### C133 — Binary YES/NO Teaching

LLM evaluates each edge monolingually: "Is there a semantic relationship
between X and Y in English?" → YES/NO → `historization.update(edge, outcome)`.

Two seedless matching methods tested:
- **Position-based** (oracle): compare quality at corresponding edge positions → **44/44 (100%)**
- **find_equivalences** (framework): edge-level fingerprint matching → **1/44 (2%)**

**Finding:** Position-based matching proves the teaching signal is sufficient.
Edge-level matching fails because binary quality produces too many identical
fingerprints (72×85 = 6120 same-quality pairs at q=−1.0).

#### C134 — Bootstrapper as Teacher

Replace binary YES/NO with continuous score 0–10. The Bootstrapper's native
`_apply_confidence()` maps scores to initial_U/initial_F, creating a
continuous quality spectrum.

**C134a:** Score injection works. Quality distribution now spans 7+ distinct
levels instead of binary.

**C134b:** Node-level matching (sorted quality profile per node):
9/44 (20%) with 100 noise edges, 13/44 (30%) with 300 noise.
Sorting loses edge-position information — nodes with same degree and similar
quality distribution become indistinguishable.

### 7.4 WL Recursive Neighborhood (C135)

**The correct comparison unit is not the edge, not the node, but the node
plus its recursive neighborhood.**

Weisfeiler-Leman-style iterative refinement:

```
Round 0: node features f₀ = edge_quality_stats(node)
Round k: fₖ = fₖ₋₁ ⊕ aggregate(mean, std of each dim of neighbor fₖ₋₁)
```

Each round extends the feature vector by encoding neighborhood context
at increasing distance. Depth 2 captures 2-hop structural role.

| Depth | Features | Correct/44 | Wrong | Precision |
|---|---|---|---|---|
| D0 (stats only) | 4 | 11 | 10 | 52% |
| D1 (1-hop) | 12 | 31 | 1 | 97% |
| D2 (2-hop) | 36 | **33** | **0** | **100%** |

The D0→D1 jump (25%→70%) proves **1-hop neighborhood context is the decisive
signal**. D2 eliminates the last false match (100% precision). 11 nodes
unmatched — low degree, insufficient neighborhood context.

### 7.5 Feature Engineering (C136)

Round-0 features expanded from 4 to 9:

| # | Feature | Signal |
|---|---|---|
| 1–4 | mean_q, std_q, degree, pos_fraction | Quality statistics (C135) |
| 5–7 | min_q, max_q, median_q | Quality extremes + robust center |
| 8–9 | **trace_load_mean, trace_load_std** | **Volume dimension — independent from quality** |

trace_load (U+F) is independent from quality (U−F)/(U+F+ε). Two edges with
identical quality can have vastly different trace loads depending on
bootstrapper confidence — a new differentiation axis.

Feature vectors: D0=9, D1=27, D2=81 (was 4/12/36).

Result: 34/44 (+1), 0 wrong. Marginal improvement, BUT critical diagnostic:

| Group | Count | Problem |
|---|---|---|
| Mutual-best blocked | 6 | Correct pair IS closer, blocked by greedy assignment |
| Genuine confusion | 4 | Wrong partner structurally closer (see↔eye, take↔go) |

**Key finding:** The bottleneck is NOT feature quality — it's the matching
algorithm. Features already provide the correct signal for 40/44.

### 7.6 Hungarian Optimal Assignment (C137) — BREAKTHROUGH

**Problem:** Greedy mutual-best matching: for each EN node, find closest DE
node, then check if DE also picks that EN. If a third node "steals" a partner,
both are left unmatched.

**Solution:** Hungarian algorithm (`scipy.optimize.linear_sum_assignment`) —
globally optimal 1:1 assignment minimizing total WL distance across all
44×44 pairs.

| Method | Correct/44 | Wrong | Precision |
|---|---|---|---|
| Mutual-best D2 (C136) | 34 | 0 | 100% |
| **Hungarian D2 (C137)** | **44** | **0** | **100%** |

All 10 previously unmatched nodes recovered:
- 6 "mutual-best blocked" → resolved by global optimization
- 4 "genuine confusions" → ALSO resolved — global assignment avoids
  cascading errors that made local distances misleading

### 7.7 The Complete Pipeline

```
  ┌───────────────────────────────────────────────────────────────┐
  │                    Phase 1: TEACHING                          │
  │                                                               │
  │  ┌─────────────────┐         ┌─────────────────┐             │
  │  │  LLM evaluates  │         │  LLM evaluates  │             │
  │  │  EN edges 0-10  │         │  DE edges 0-10  │             │
  │  │  (monolingual)  │         │  (monolingual)  │             │
  │  └────────┬────────┘         └────────┬────────┘             │
  │           │                           │                       │
  │           ▼                           ▼                       │
  │  ┌─────────────────┐         ┌─────────────────┐             │
  │  │  bootstrap_     │         │  bootstrap_     │             │
  │  │  landscape()    │         │  landscape()    │             │
  │  │  score→U/F      │         │  score→U/F      │             │
  │  └────────┬────────┘         └────────┬────────┘             │
  │           │                           │                       │
  │           ▼                           ▼                       │
  │  ┌─────────────────┐         ┌─────────────────┐             │
  │  │  EN Landscape   │         │  DE Landscape   │             │
  │  │  44 nodes       │         │  44 nodes       │             │
  │  │  164 edges      │         │  164 edges      │             │
  │  └────────┬────────┘         └────────┬────────┘             │
  └───────────┼───────────────────────────┼───────────────────────┘
              │                           │
  ┌───────────┼───────────────────────────┼───────────────────────┐
  │           │    Phase 2: PLAYGROUND    │     (no LLM)          │
  │           ▼                           ▼                       │
  │  ┌─────────────────┐         ┌─────────────────┐             │
  │  │  WL fingerprints│         │  WL fingerprints│             │
  │  │  depth=2        │         │  depth=2        │             │
  │  │  81-dim vectors │         │  81-dim vectors │             │
  │  └────────┬────────┘         └────────┬────────┘             │
  │           │                           │                       │
  │           └──────────┬────────────────┘                       │
  │                      ▼                                        │
  │           ┌────────────────────┐                              │
  │           │  44×44 distance    │                              │
  │           │  matrix (WL dist)  │                              │
  │           └────────┬───────────┘                              │
  │                    ▼                                          │
  │           ┌────────────────────┐                              │
  │           │   Hungarian        │                              │
  │           │   algorithm        │                              │
  │           │   (global optimal) │                              │
  │           └────────┬───────────┘                              │
  │                    ▼                                          │
  │           ┌────────────────────┐                              │
  │           │  44/44 = 100%      │                              │
  │           │  correct, 0 wrong  │                              │
  │           └────────────────────┘                              │
  └───────────────────────────────────────────────────────────────┘
```

### 7.8 Key Files (Phase 2)

| File | Purpose |
|---|---|
| `explore_c133_playground.py` | Binary LLM teaching + seedless playground |
| `explore_c134_bootstrapper_teacher.py` | Bootstrapper as teacher (score 0–10) |
| `explore_c135_wl_matching.py` | WL recursive neighborhood at depth 0/1/2 |
| `explore_c136_feature_engineering.py` | 9-dim features + unmatched diagnostic |
| `explore_c137_hungarian.py` | Hungarian optimal assignment — breakthrough |
| `dream_mode.py` | WLNodeFingerprint, find_wl_node_equivalences_hungarian |
| `bootstrapper.py` | _apply_confidence, bootstrap_landscape (teacher role) |

---

## 8. Full Comparison Table (C124–C137)

| Phase | Experiment | Seed | Matching | Correct | Wrong | Precision | Key finding |
|---|---|---|---|---|---|---|---|
| **1** | C125 Config B | 11 | Edge fingerprint | 30/41 top-20 | — | 73% | First discrimination |
| **1** | C126 iterative | 11→25 | Edge + bootstrap | — | cascade | — | **FALSIFIED: ungated contamination** |
| **1** | C126b gated | 11→16 | Edge + gated | 16/16 | 0 | 100% | Gating preserves but limits |
| **1** | C126c weighted | 11→15 | Edge + L1 weighted | 4/4 confirmed | 0 | 100% | **FALSIFIED: distance collapse** |
| **1** | C127 L2 | 11→12 | Edge + L2 pair | 1/1 | 0 | 100% | Distance preserved |
| **1** | C127b cumul | 11→15 | Edge + L2 + votes | 2/4 | 2 | 50% | **FALSIFIED: false matches amplified** |
| **1** | **C128 L3** | **11→15** | **Edge + L3 context** | **4/4** | **0** | **100%** | **Neighborhood consistency** |
| **2** | C133 | **0** | Position oracle | 44/44 | 0 | 100% | Teaching signal sufficient |
| **2** | C134b | **0** | Node sorted profile | 9 | 4 | 69% | Sorting loses edge info |
| **2** | C135 | **0** | WL depth-2 (4-dim) | 33 | 0 | 100% | Neighborhood = right unit |
| **2** | C136 | **0** | WL depth-2 (9-dim) | 34 | 0 | 100% | Matching, not features |
| **2** | **C137** | **0** | **WL + Hungarian** | **44** | **0** | **100%** | **BREAKTHROUGH** |

---

## 9. Principled vs Heuristic Components (updated)

### Principled (Phase 1 + Phase 2)

| Component | Basis | Reference |
|---|---|---|
| Edge fingerprint f(e) = (q, m, I) | Direct from Historization layer | C109, Ontodynamics §4 |
| WL recursive neighborhood | Structural role from graph topology | C135, WL literature |
| trace_load as independent axis | U+F independent from (U−F)/(U+F+ε) | C136, Historization |
| Hungarian optimal assignment | Bipartite matching (Kuhn 1955) | C137, combinatorial optimization |
| Monolingual teaching | No cross-language leakage by construction | C133 |
| Bootstrapper as teacher | score → initial_U/F → continuous quality | C134, bootstrapper.py |
| Shared topology constraint | Without structural correspondence, domains are "aliens" | C133 |

### Heuristic (experimentally tuned)

| Parameter | Value | Sensitivity | Path to derivation |
|---|---|---|---|
| WL depth=2 | 2-hop neighborhood | Low — D2 >> D1, D3 likely overfits | Could derive from graph diameter |
| noise_edges=100 | Noise edges added | Low — works at 100, 300 | Could derive from |E| |
| 9-dim Round-0 features | Quality + load stats | Low — 4-dim already gets 33/44 | Minimal sufficient set TBD |
| quantile=0.15 (mutual-best) | Equivalence threshold | N/A — Hungarian makes this obsolete | Replaced by Hungarian |

**Assessment**: The **mechanisms** (context scoring, multiplicative validation,
cumulative voting) are principled.  The **thresholds** are heuristic but
low-sensitivity — the system is robust to 2× parameter variation.

---

## 7. Open Questions

### Q1: Saturation Limit

The system saturates at 15/44 pairs (34%).  Is this a fundamental limit
of the 11-pair Config B starting point, or can Level-3 break through with
more rounds?

**Test**: Run C128 with 20+ rounds.  If thing↔ding (cum=19, ctx=71%)
promotes, the system can grow beyond 15.

### Q2: Cold-Start Bootstrap

Context score needs translated neighbors to compute.  Words with no
translatable neighbors get ctx=None (neutral — no suppression, no boost).
This is correct but limits the mechanism's reach.

**Question**: Can the system bootstrap context from zero?  As more pairs
are confirmed, more neighbors become translatable, enabling context scoring
for previously unscoreable words.  Is this recursive process convergent?

### Q3: Parameter Derivation

Can VOTE_SCALE and PROMOTION_VOTES be derived from topology?
Candidate: VOTE_SCALE = |E_canon| / |V_canon| (edges per node, analogous
to μ = |E|/|V| in C105).  For 64/44 ≈ 1.45 — too small.  Perhaps
|E| × some factor.

### Q4: take↔machen Anomaly

take↔machen has ctx=100% (4/4 neighbors match) despite being wrong
(correct: take↔nehmen).  This happens because take and machen share
structural neighborhood overlap (both connect to hand).

**Question**: Is this a fundamental limit of 1-hop context?  Would
2-hop (neighbor-of-neighbor) resolve it?  Or does the vote threshold
suffice as safeguard?

### Q5: Scaling

44-node canons are toy scale.  With 500+ nodes:
- Does context scoring remain discriminative?
- Does the bijective constraint become too restrictive?
- Does the combinatorial space of false matches explode?

### Q6: Framework Integration

Context scoring is currently exploration-only.  Could it become a
framework mechanism?  Possible integration points:
- dream_mode.py: context-weighted equivalence confidence
- cross_reflexion.py: structural validation for bridge proposals
- observation.py: neighborhood-based focus selection

### Q7: Principled Promotion Threshold

Instead of fixed PROMOTION_VOTES=25, could promotion be triggered by
statistical significance?  E.g., "this pair's votes are significantly
above random expectation given the edge count and equivalence pool."

---

## 8. Falsification Log

| Hypothesis | Experiment | Result | Learning |
|---|---|---|---|
| Uniform SUCCESS enables learning | C124 | **Falsified** | Partial reality barrier is necessary |
| Ungated bootstrap improves with rounds | C126 | **Falsified** | Contamination cascades |
| High-confidence gating is sufficient | C126b | Partially valid | Stable but limited — not a path to coverage |
| L1 with graduated weights works | C126c | **Falsified** (mechanism) | Distance collapse under Level-1 |
| Pure vote accumulation ensures accuracy | C127b | **Falsified** | Systematic false matches amplify equally |
| Level-3 context rejects false matches | C128 | **Confirmed** | 4/4 confirmed, 0 false promotions |

---

## 9. Files

| File | Purpose | Commit |
|---|---|---|
| `canons/english_basic.json` | EN canon: 44 nodes, 64 edges, 6 levels | C124b |
| `canons/german_basic.json` | DE canon: 44 nodes, 64 edges, 6 levels | C124b |
| `explore_dict_learning.py` | C125: PartialDictionary, GROUND_TRUTH, config_a/b | C125 |
| `explore_bootstrap_learning.py` | C126/b: Bootstrap loop, extract_best_correspondences | C126b |
| `explore_weighted_learning.py` | C126c: WeightedDictionary, 3-tier graduation | C126c |
| `explore_level2_learning.py` | C127: Level-2 multiplicative validation | C127 |
| `explore_level2_cumulative.py` | C127b: Cumulative vote historization (falsified) | C127b |
| `explore_level3_learning.py` | C128: Level-3 neighborhood consistency | C128 |
| `E0_LANGUAGE_LEARNING_CONCEPT_v1.md` | Original concept document (pre-implementation) | C125 |

---

## 10. The Deeper Principle

The language learning arc confirms and extends the concept document's
§8 insight:

> **An E₀ system does not learn from landscape structure alone.
> It learns from differential historization under a partial reality barrier.**

C128 adds a second layer:

> **Validation of learned correspondences requires structural context,
> not just accumulated evidence.  A word's identity is its relation to
> other words — isolated fingerprint similarity is necessary but not
> sufficient.**

This parallels Saussure's foundational linguistic insight (meaning is
differential, defined by contrasts and relations) and aligns with E₀'s
own ontology: trace_load (mass) emerges from inscription, but identity
emerges from relational context.

The context_score mechanism is not language-specific.  Any cross-domain
correspondence validation (dream bridges, multiverse coupling) could
benefit from neighborhood-consistency checking.  This is a candidate for
framework integration (see Q6).
