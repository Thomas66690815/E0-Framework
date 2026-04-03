# E₀ Language Learning via Partial Dictionaries — Concept Document v1

**Status**: Concept — pre-implementation  
**Depends on**: C124b (differentiated EN/DE canons)  
**Author**: C125 design phase

---

## 1. Problem Statement

C124 built EN↔DE vocabulary canons (44 nodes, 64 edges each) and ran the
full 12-layer pipeline.  Dream Mode found **614 equivalences, all at
q=0.000** — zero discrimination.

**Root cause**: `execute_fn = lambda s,t: Outcome.SUCCESS` for every edge.
Fingerprint = (trace_quality, trace_load, inertia_factor).  With uniform
SUCCESS, trace_quality → +1 for every visited edge.  All fingerprints
converge to the same (q, m, I) triplet.  Dream Mode's quantile-based
threshold returns the bottom 10% of a flat distance matrix — noise, not
signal.

C124b differentiated delta values (0.1–0.7 by relationship type), but
deltas affect which edge the Greedy selector picks, **not** the fingerprint
directly.  The fingerprint still depends on SUCCESS/FAILURE outcomes.

**Analogy**: Chess works because the engine provides heterogeneous
SUCCESS/FAILURE for legal vs. illegal moves.  Without the engine, every
move "succeeds" and no learning occurs.  Language learning without
validation is structurally identical.

| | Chess | Language |
|---|---|---|
| Domain landscape | Board positions + moves | Word graphs (EN, DE) |
| Validation engine | Chess engine (legal/illegal) | Dictionary (correct/wrong translation) |
| What creates FAILURE | Illegal moves | Unknown or wrong correspondences |
| Result of FAILURE | Fingerprint differentiation | Fingerprint differentiation |


## 2. Key Insight: Partial Dictionaries as Engines

A **partial dictionary** knows some correct translations within a semantic
domain but not all.  It serves the same architectural role as the chess
engine: providing SUCCESS/FAILURE signals that break fingerprint symmetry.

Two dictionaries with complementary coverage:

| Dictionary | Known EN→DE pairs | Domain |
|---|---|---|
| Dict-Body | hand→hand, arm→arm, finger→finger, ear→ohr | Body parts |
| Dict-Food | bread→brot, water→wasser, milk→milch, salt→salz | Food/drink |

**The experimental question**: Can E₀ derive UNKNOWN translations from
known ones via structural fingerprint matching?

Unknown body:  head↔kopf, foot↔fuss, eye↔auge, mouth↔mund  
Unknown food:  fruit↔frucht, apple↔apfel


## 3. Architecture: Dictionary-Mediated execute_fn

### 3.1 The Core Mechanism

Instead of `lambda s,t: SUCCESS`, the EN and DE landscapes use an
execute_fn that queries the partial dictionaries:

```
known_en = {hand, arm, finger, ear}  ∪  {bread, water, milk, salt}
known_de = {hand, arm, finger, ohr}  ∪  {brot, wasser, milch, salz}

def en_execute(source, target) → Outcome:
    return SUCCESS if target ∈ known_en else FAILURE

def de_execute(source, target) → Outcome:
    return SUCCESS if target ∈ known_de else FAILURE
```

This rule is semantically clean: "If you arrive at a word the dictionaries
cover, the transition is validated.  If not, it fails."  The dictionaries
are the only source of ground truth — without them, the system has no way
to assess structural correspondence.

### 3.2 Effect on EN Edges

Tracing all body-related edges with this execute_fn:

```
EN Edge              Target known?   Outcome    Fingerprint effect
─────────────────────────────────────────────────────────────────
body → hand          hand ✓          SUCCESS    q ↑
body → arm           arm ✓           SUCCESS    q ↑
body → ear           ear ✓           SUCCESS    q ↑
body → head          head ✗          FAILURE    q ↓
body → foot          foot ✗          FAILURE    q ↓
body → eye           eye ✗           FAILURE    q ↓
body → mouth         mouth ✗         FAILURE    q ↓
head → eye           eye ✗           FAILURE    q ↓
head → mouth         mouth ✗         FAILURE    q ↓
head → ear           ear ✓           SUCCESS    q ↑
hand → finger        finger ✓        SUCCESS    q ↑
arm  → hand          hand ✓          SUCCESS    q ↑
eye  → see           see ✗           FAILURE    q ↓
mouth → eat          eat ✗           FAILURE    q ↓
mouth → say          say ✗           FAILURE    q ↓
mouth → drink        drink ✗         FAILURE    q ↓
foot → go            go ✗            FAILURE    q ↓
ear  → hear          hear ✗          FAILURE    q ↓
hand → give          give ✗          FAILURE    q ↓
hand → take          take ✗          FAILURE    q ↓
hand → make          make ✗          FAILURE    q ↓
take → hand          hand ✓          SUCCESS    q ↑
```

### 3.3 Effect on DE Edges (Parallel)

```
DE Edge              Target known?   Outcome
──────────────────────────────────────────────
koerper → hand       hand ✓          SUCCESS
koerper → arm        arm ✓           SUCCESS
koerper → ohr        ohr ✓           SUCCESS
koerper → kopf       kopf ✗          FAILURE
koerper → fuss       fuss ✗          FAILURE
koerper → auge       auge ✗          FAILURE
koerper → mund       mund ✗          FAILURE
kopf → auge          auge ✗          FAILURE
kopf → mund          mund ✗          FAILURE
kopf → ohr           ohr ✓           SUCCESS
hand → finger        finger ✓        SUCCESS
arm  → hand          hand ✓          SUCCESS
auge → sehen         sehen ✗         FAILURE
mund → essen_v       essen_v ✗       FAILURE
mund → sagen         sagen ✗         FAILURE
mund → trinken       trinken ✗       FAILURE
fuss → gehen         gehen ✗         FAILURE
ohr  → hoeren        hoeren ✗        FAILURE
hand → geben         geben ✗         FAILURE
hand → nehmen        nehmen ✗        FAILURE
hand → machen        machen ✗        FAILURE
```

### 3.4 Resulting Fingerprint Patterns

After learning, each edge has a fingerprint shaped by its SUCCESS/FAILURE
history.  The critical observation: **parallel edges in EN and DE get
parallel outcomes**.

| EN edge | DE edge | Both get | Structural role |
|---|---|---|---|
| body→hand (S) | koerper→hand (S) | SUCCESS | Known body part |
| body→ear (S) | koerper→ohr (S) | SUCCESS | Known body part |
| body→mouth (F) | koerper→mund (F) | FAILURE | **Unknown** body part |
| body→eye (F) | koerper→auge (F) | FAILURE | **Unknown** body part |
| head→ear (S) | kopf→ohr (S) | SUCCESS | Known child of head |
| mouth→eat (F) | mund→essen_v (F) | FAILURE | Unknown action link |
| eye→see (F) | auge→sehen (F) | FAILURE | Unknown action link |
| hand→finger (S) | hand→finger (S) | SUCCESS | Known descendant |

Within the FAILURE group, edges STILL differ by their **local topology**:

- `mouth` has 3 outgoing FAILURE edges (→eat, →say, →drink)
- `eye` has 1 outgoing FAILURE edge (→see)
- `foot` has 1 outgoing FAILURE edge (→go)
- `head` has 2 FAILURE + 1 SUCCESS outgoing edge (→eye, →mouth, →ear)

The controller's traversal pattern differs: from `mouth`, traffic splits
across 3 FAILURE paths (each getting ~1/3 of visits); from `eye`, all
traffic goes to the single FAILURE edge.  This creates different
**trace_load** and **inertia_factor** values — fingerprint differentiation.


## 4. Dream Mode Equivalence Discovery

### 4.1 Edge-Level Matching

Dream Mode compares fingerprints of edges across domains (EN × DE).
Expected matches (low fingerprint_distance):

**Strong matches (parallel SUCCESS/FAILURE + parallel topology):**
- `EN:mouth→eat` ≈ `DE:mund→essen_v` — both FAILURE, both are one of 3 actions from a 3-action body part
- `EN:mouth→say` ≈ `DE:mund→sagen` — same pattern
- `EN:mouth→drink` ≈ `DE:mund→trinken` — same pattern
- `EN:eye→see` ≈ `DE:auge→sehen` — both FAILURE, sole action from a 1-action body part
- `EN:foot→go` ≈ `DE:fuss→gehen` — both FAILURE, sole action from a 1-action body part
- `EN:ear→hear` ≈ `DE:ohr→hoeren` — both FAILURE, sole action from a 1-action body part

**Weaker but valid matches:**
- `EN:body→mouth` ≈ `DE:koerper→mund` — both FAILURE from parent
- `EN:body→eye` ≈ `DE:koerper→auge` — both FAILURE from parent

### 4.2 From Edge Equivalences to Node Correspondences

Individual edge matches are ambiguous: `body→mouth (F)` also matches
`body→eye (F)` because both have the same parent and outcome.

**Convergent evidence** resolves ambiguity.  If MULTIPLE edges from/to
the same node pair match:

```
mouth→eat   ≈  mund→essen_v     (3-action pattern)
mouth→say   ≈  mund→sagen       (3-action pattern)
mouth→drink ≈  mund→trinken     (3-action pattern)
head→mouth  ≈  kopf→mund        (parent relationship)
body→mouth  ≈  koerper→mund     (grandparent relationship)
```

Five edges all point to **mouth ↔ mund**.  No other DE node produces
this consistent a match for all five EN edges around `mouth`.

Compare: `eye` has only 2 matching edges (`eye→see`, `body→eye`), but
they consistently point to `auge` (not `mund` or `kopf`).

### 4.3 Discrimination Power Assessment

| Unknown pair | Distinguishing feature | Matchable? |
|---|---|---|
| mouth ↔ mund | 3 outgoing action edges (eat/say/drink) | **Strong** — unique 3-edge pattern |
| eye ↔ auge | 1 outgoing (see), 1 incoming from head | Moderate — unique but thin |
| ear ↔ ohr | Already known (Dict-Body) | Confirmed |
| foot ↔ fuss | 1 outgoing (go), no head connection | Moderate — could confuse with eye |
| head ↔ kopf | 3 outgoing to body parts (2F + 1S) | **Strong** — only node with 3 body-part children |
| fruit ↔ frucht | 1 child (apple), parent = food | Moderate |
| apple ↔ apfel | Leaf, parent = fruit | Weak — leaf nodes lack context |

**Potential confusion**: `eye→see` and `foot→go` have identical topological
signatures (single FAILURE outgoing edge from unknown body part, parent =
head or body respectively).  Disambiguation requires second-order context:
eye is a child of head, foot is not.  Whether this is captured by current
fingerprints depends on whether the controller explores head→eye vs.
body→foot routes differently.


## 5. Enhancement: Expanded Dictionary Coverage

The base dictionaries (8 known words per language) leave 82% of nodes
unvalidated.  Most edges get FAILURE, reducing discrimination within the
FAILURE group.

**Proposal**: Add food-related verbs to Dict-Food:

| Extended Dict-Food | EN→DE pairs |
|---|---|
| Original | bread→brot, water→wasser, milk→milch, salt→salz |
| Added verbs | eat→essen_v, drink→trinken |

Effect:
```
mouth→eat:  eat now KNOWN → SUCCESS  (was FAILURE)
mouth→drink: drink now KNOWN → SUCCESS (was FAILURE)
mouth→say:  say still unknown → FAILURE
```

This gives mouth/mund a **unique mixed pattern** [S, S, F] — two SUCCESS
food-action edges plus one FAILURE communication edge.  No other body part
has this pattern.

Similarly, adding `hear→hoeren` to Dict-Body would give ear/ohr a SUCCESS
action edge, distinguishing it from eye and foot.

| Enrichment | Added pairs | Discriminates |
|---|---|---|
| eat→essen_v, drink→trinken in Dict-Food | food verbs | mouth from eye, foot |
| hear→hoeren in Dict-Body | hearing verb | ear from eye, foot |
| see→sehen in Dict-Body (optional) | vision verb | eye from foot |

**Trade-off**: More known words = better discrimination but less to
discover.  The experimental core remains: can the system infer the
unknown **noun** translations (mouth↔mund, eye↔auge, head↔kopf,
foot↔fuss, fruit↔frucht, apple↔apfel) from the known ones?


## 6. Implementation Plan

### Phase 1: Dictionary Data Structures

```python
@dataclass
class PartialDictionary:
    name: str
    translations: Dict[str, str]   # EN word → DE word

    @property
    def known_en(self) -> Set[str]:
        return set(self.translations.keys())

    @property
    def known_de(self) -> Set[str]:
        return set(self.translations.values())
```

Two instances:
- `dict_body = PartialDictionary("body", {"hand":"hand", "arm":"arm", "finger":"finger", "ear":"ohr"})`
- `dict_food = PartialDictionary("food", {"bread":"brot", "water":"wasser", "milk":"milch", "salt":"salz", "eat":"essen_v", "drink":"trinken"})`

### Phase 2: Dictionary-Mediated execute_fn

```python
def make_dict_execute(dicts: List[PartialDictionary], language: str):
    if language == "en":
        known = set().union(*(d.known_en for d in dicts))
    else:
        known = set().union(*(d.known_de for d in dicts))

    def execute(source: str, target: str) -> Outcome:
        return Outcome.SUCCESS if target in known else Outcome.FAILURE
    return execute
```

### Phase 3: Learning Pipeline

1. Load EN canon → Landscape with `en_execute`
2. Load DE canon → Landscape with `de_execute`
3. Run curriculum on both (edges acquire heterogeneous fingerprints)
4. Create DreamObserver, register both domains
5. Run dream_cycle → find equivalences
6. Analyze: which equivalences correspond to CORRECT translations?

### Phase 4: Dictionary Landscapes (Optional)

Separate Dict-Body and Dict-Food landscapes with correct + distractor edges
and their own execute_fn.  Register with DreamObserver as additional
domains.  This adds **cross-bridge** equivalences (e.g., Dict:hand→Hand ≈
Dict:bread→Brot as "both correct translations") that could further anchor
the matching.

This phase is optional — the core mechanism (Phase 2) may be
sufficient.


## 7. Success Criteria

### Minimum viable result
- Dream equivalences for mouth↔mund rank higher than mouth↔auge or
  mouth↔kopf
- At least 3 of the 6 unknown pairs appear in the top-20 equivalences

### Strong result
- All 6 unknown noun pairs (head↔kopf, foot↔fuss, eye↔auge, mouth↔mund,
  fruit↔frucht, apple↔apfel) appear as equivalences with distance
  significantly below the general FAILURE-group mean

### Stretch goal
- The system proposes correct translations for words that have NO
  dictionary coverage in any domain (e.g., from verb patterns alone)


## 8. The Deeper Principle: Differential Historization Under Partial Reality Barrier

*Insight surfaced via cross-cognition review.*

The core finding of this document is not about language.  It is:

> **An E₀ system does not learn from landscape structure alone.
> It learns from differential historization under a partial reality
> barrier.**

Without FAILURE signals, there is no differential quality — only visit
counts.  The "reality barrier" (here: partial dictionaries) creates the
asymmetry that makes form differences *learnable*.  This is the same
mechanism that makes chess work: the engine is the reality barrier.

**Implication beyond language**: Any domain where E₀ currently uses
`lambda s,t: SUCCESS` is structurally dead in the same way C124 was.
The partial-dictionary pattern generalizes: wherever a domain has external
validation for *some* edges but not all, E₀ can learn the missing ones
from structural parallels.


## 9. Validation Progression: Three Levels

The target-only execute_fn is a **bootstrap trick** — good enough to
create initial heterogeneity, but not the final form.  The cross-cognition
review correctly identifies this as the critical tension.

### Level 1: Target Known? (C125 — this experiment)
```
execute(source, target) → SUCCESS if target ∈ known else FAILURE
```
**Blind spot**: all edges to known targets get SUCCESS regardless of
relational role.  `body→hand`, `arm→hand`, `take→hand` all succeed
identically, even though their structural meaning differs.

**Sufficiency assessment**: For bootstrap learning where the question is
"can the system create ANY heterogeneous fingerprints at all?", Level 1
is appropriate.  The first experiment must prove the mechanism works
before adding complexity.

### Level 2: Relation + Target (future)
```
execute(source, target) → SUCCESS if (source, target) ∈ known_pairs else FAILURE
```
Validates the *edge*, not just the endpoint.  `body→hand` could succeed
while `take→hand` fails, because the dictionary knows "body has hand" but
not "take involves hand".  This preserves relational direction.

### Level 3: Topology-Aware Validation (speculative)
```
execute(source, target) → SUCCESS if local_pattern_matches(source, target)
```
Validates whether the local topological role of the edge (e.g., "one of 3
action-edges from a body part") matches what the dictionary expects.
This is second-order context and requires significant extension.

**C125 tests Level 1 only.**  If Level 1 already produces meaningful
discrimination, Level 2 becomes a refinement, not a necessity.


## 10. Open Design Questions

1. **Dictionary landscape role**: Are separate dictionary landscapes
   needed, or is the execute_fn mediation sufficient?  The 4-universe
   architecture is more E₀-native, but the 2-universe + dict-mediated
   design is cleaner.

2. **Coverage threshold**: How many words must dictionaries cover for
   meaningful discrimination?  Too few → most edges are FAILURE → flat.
   Too many → nothing left to discover.

3. **Second-order fingerprints**: Current fingerprints capture one edge's
   (q, m, I).  For fine discrimination (eye vs. foot), we may need
   neighborhood-aware fingerprints.  This would be a significant
   extension — note it but don't implement in C125.

4. **Convergent evidence aggregation**: Dream Mode returns edge
   equivalences, not node correspondences.  We need a post-processing
   step that clusters equivalences by shared nodes and proposes node
   translations.  Design: count how many edge equivalences point to
   each (EN-node, DE-node) pair.


## 11. Experimental Plan: Two Configurations

C125 runs both dictionary configurations and compares results:

### Config A: Nouns Only
- Dict-Body: hand→hand, arm→arm, finger→finger, ear→ohr (4 pairs)
- Dict-Food: bread→brot, water→wasser, milk→milch, salt→salz (4 pairs)
- Total known: 8 EN + 8 DE = 16 validated nodes
- Expected: Weak discrimination — most edges are FAILURE, including
  all action edges.  Mouth, eye, ear, foot look similar.

### Config B: Nouns + Verbs
- Dict-Body: hand→hand, arm→arm, finger→finger, ear→ohr, hear→hoeren (5 pairs)
- Dict-Food: bread→brot, water→wasser, milk→milch, salt→salz, eat→essen_v, drink→trinken (6 pairs)
- Total known: 11 EN + 11 DE = 22 validated nodes
- Expected: Stronger discrimination — mouth/mund get unique [S,S,F]
  pattern; ear/ohr get SUCCESS via hear→hoeren

### Comparison Metrics
1. Number of distinct fingerprint values (Config A vs. B)
2. Top-20 equivalences: how many are correct translations?
3. For each unknown noun pair: rank among all equivalences
4. Convergent evidence score: (EN-node, DE-node) pair vote counts


## 12. What This Is NOT

- **Not sentence-level NLP**: The system works on semantic graph structure,
  not word sequences.  "I eat bread" is a valid path, but path validation
  is not what we test here.

- **Not embedding similarity**: There are no vector representations.
  Fingerprints are derived from historization dynamics (SUCCESS/FAILURE
  traces), not from distributional semantics.

- **Not a practical translation system**: This is a proof-of-concept for
  E₀'s structural learning capability.  The question is architectural:
  can the same mechanism that plays chess also discover cross-domain
  correspondences?


## 13. Summary

The dictionary-mediated execute_fn converts the "uniform SUCCESS" problem
into heterogeneous historization.  Known words create SUCCESS signals,
unknown words create FAILURE signals.  Parallel EN/DE edges get parallel
outcomes because the graph topology mirrors and the dictionaries are
consistent across both languages.

Dream Mode then detects these parallel patterns as functional equivalences.
Convergent evidence (multiple edge matches pointing to the same node pair)
resolves ambiguity.

**The chess analogy completes**: dictionaries are the engine.  Without them,
the system sees no difference between correct and incorrect — just as chess
without move validation sees no difference between legal and illegal.

**The deeper principle**: E₀ does not learn from landscape structure.
It learns from *differential historization under a partial reality
barrier*.  The dictionaries are partial, the validation is selective,
and precisely this partiality creates the form differences that make
structural matching possible.  This may generalize far beyond language.
