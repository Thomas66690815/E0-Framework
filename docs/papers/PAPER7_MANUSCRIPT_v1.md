# E₀-VII: Emergent Consolidation — Dream, Entropy, and the Sleep–Wake Cycle

**Thomas Wehner**

---

## Abstract

Papers 1–6 construct a transition framework that navigates, inscribes,
reflects, couples, and localizes — but never forgets. This paper addresses
the structural consequence: unbounded historization leads to information
overload, where every transition is inscribed regardless of novelty and
every state persists regardless of relevance. We construct three tightly
coupled mechanisms — all derived from the existing primitives ($\Delta$,
$R$, $H$) — that close the consolidation loop. (1) *Structural Entropy*
introduces a parameter-free forgetting mechanism in two types:
non-inscription (Type 1), where an edge-specific threshold
$\varepsilon(e) = \varepsilon_0(T_s) \cdot (1 - e^{-m/\mu})$ gates
routine outcomes; and anchor-based decay (Type 2), where dormant,
structurally unimportant states are pruned while ghost traces preserve
recognition capacity. Both types are governed by a single scalar,
structural temperature $T_s = \bar{m}/\bar{q}$, computed from existing
historization statistics. (2) *Dream Mode* detects cross-domain structural
patterns through a hierarchy of fingerprinting algorithms — 4D edge
fingerprints, sorted quality vectors, and Weisfeiler–Leman recursive
neighborhood encodings — matched via Hungarian optimal assignment. Detected
equivalences populate a *Dream Landscape* that is itself an E₀ landscape,
subject to the same historization and decay. Bridge hypotheses translate
dream equivalences into concrete cross-reflexion proposals, closing the
loop between passive observation and active navigation. (3) The
*Sleep–Wake Cycle* orchestrates the rhythm: navigation raises $T_s$,
inscription slows, dream pressure $p = T_s/(T_s + \mu)$ crosses the
threshold at $T_s = \mu$, triggering consolidation that lowers $T_s$
and restores inscription sensitivity. The trigger is parameter-free:
$\mu$ is the same half-load constant used by inertia factor, inscription
threshold, and adaptive exploration. Together these mechanisms implement
biological sleep consolidation in structural form: experience is extracted
as cross-domain patterns, then the graph is compressed. All constructions
use existing parameters ($\rho$, $\mu$, $\alpha$); no new tuning
constants are introduced. 186 tests validate all mechanisms.
All claims are classified as derived, empirical, or heuristic.

---

## 1. Introduction

### 1.1 The Problem: Unbounded Inscription

The E₀ framework inscribes every transition outcome into historization:
SUCCESS increments $U(e)$, FAILURE increments $F(e)$, and trace quality
$q(e) = (U - F)/(U + F)$ encodes the accumulated judgment. Papers 1–5
demonstrate that this mechanism produces emergent path selection, locality,
and reflexive self-modification. But they implicitly assume that
inscription is always useful.

Three problems follow from unbounded inscription:

1. **Noise accumulation.** A well-understood transition (traversed 100
   times, quality ≈ 1.0) gains nothing from transition 101. Yet the
   system inscribes it, incrementing $\tau$ and triggering reflexive
   overhead (self-graph updates, dual reflection, dream observation).

2. **Graph bloat.** Exploratory states visited once and abandoned persist
   indefinitely. The landscape grows without bound, increasing search
   costs and polluting pattern detection.

3. **Missing consolidation.** Biological systems alternate between active
   experience (wake) and passive consolidation (sleep). E₀ has no
   structural analogue — it is always "awake," always inscribing.

### 1.2 Approach

We derive all three mechanisms from the existing primitives. The key
construction is *structural temperature*:

$$T_s = \frac{\bar{m}}{\bar{q}} = \frac{\text{mean trace\_load}}{\text{mean } |q|}$$

$T_s$ is a ratio of two quantities already computed by historization.
It requires no new parameters and has a natural interpretation: a system
with much experience but little clarity "runs hot" (high $T_s$); a system
with clear judgments or little experience is "cold" (low $T_s$).

From $T_s$, three consequences follow:
- **Type 1 forgetting** (§2): inscription slows as the system heats
- **Type 2 forgetting** (§3): dormant states are pruned
- **Dream trigger** (§8): consolidation begins when $T_s > \mu$

The structural temperature is computed once per cycle and governs all
three mechanisms, ensuring coherent behavior without parameter tuning.

[impl: `structural_entropy.structural_temperature`, line 42]

### 1.3 Paper Structure

§2 derives Type 1 forgetting (inscription threshold). §3 derives Type 2
forgetting (structural decay). §4–§6 construct the dream fingerprinting
hierarchy. §7 describes the Dream Landscape and DreamObserver lifecycle.
§8 builds the Sleep–Wake Cycle. §9 covers bridge hypothesis generation.
§10 presents the unified Structural Resonance metric. §11 summarizes
empirical validation. §12 classifies all claims. §13 concludes.

---

## 2. Type 1 Forgetting: Inscription Threshold

### 2.1 Novelty

An outcome's novelty measures how surprising it is given prior experience:

$$\text{novelty}(e, o) = |\text{signal}(o) - q(e)|$$

where $\text{signal}(\text{SUCCESS}) = 1$, $\text{signal}(\text{FAILURE}) = -1$,
$\text{signal}(\text{PARTIAL}) = 0$. The range is $[0, 2]$: zero when the
outcome matches expectation exactly, two when expectation is maximally wrong
(expected $+1$, got $-1$).

[impl: `structural_entropy.novelty`, line 170]

### 2.2 Per-Edge Threshold

The inscription threshold adapts to both system-level heat and edge-level
experience:

$$\varepsilon(e) = \varepsilon_0(T_s) \cdot \left(1 - e^{-m(e)/\mu}\right)$$

where

$$\varepsilon_0(T_s) = 1 - e^{-T_s/\mu}$$

**Properties:**

| Condition | $\varepsilon(e)$ | Effect |
|-----------|-------------------|--------|
| Virgin edge ($m = 0$) | 0 | Always inscribed |
| Cold system ($T_s \approx 0$) | $\approx 0$ | Everything inscribed |
| Hot system ($T_s \gg \mu$) | $\to 1$ | Only extreme surprises inscribed |
| Experienced edge ($m \gg \mu$) | $\approx \varepsilon_0$ | Full threshold active |

The threshold uses $\mu$ — the same half-load constant from inertia factor.
No new parameter.

[impl: `structural_entropy.inscription_threshold`, line 196]

### 2.3 Inscription Decision

$$\text{should\_inscribe}(e, o) \iff \text{novelty}(e, o) > \varepsilon(e)$$

When `should_inscribe` returns False, the entire downstream chain is
skipped: historization, self-graph update, dual reflection, dream
observation. The system navigates on inertia — "autopilot" mode.

[impl: `structural_entropy.should_inscribe`, line 229]

### 2.4 Structural Interpretation

Type 1 forgetting is *non-inscription* — it does not erase existing
traces but prevents new ones from forming. The system's selectivity
increases as experience accumulates. This is structurally analogous to
habituation: repeated identical stimuli stop producing responses.

The exponential form $1 - e^{-x/\mu}$ appears three times in the framework:
inertia factor, inscription base threshold, and per-edge inscription factor.
This is not coincidence — all three measure the same thing (saturation
relative to the half-load constant) in different contexts.

---

## 3. Type 2 Forgetting: Structural Decay

### 3.1 Anchor Score

Not all states deserve to persist. The anchor score quantifies structural
importance:

$$\text{anchor}(s) = |\bar{q}_s| \cdot m_{\max}(s) \cdot \log(1 + \deg(s))$$

Three components, each from existing primitives:

- $|\bar{q}_s|$: mean absolute trace quality of incident edges — *emotional
  clarity*. A state connected to edges with strong, consistent judgments is
  important.
- $m_{\max}(s)$: maximum trace load of incident edges — *depth of experience*.
  A state with at least one deeply inscribed edge has structural weight.
- $\log(1 + \deg(s))$: logarithmic degree — *structural centrality*.
  Hubs score higher than leaves, with diminishing returns.

A state with strong emotional valence, deep experience, and many connections
is an *anchor* — a structural landmark that resists decay. A state that is
neutral, lightly experienced, and peripheral is a *decay candidate*.

[impl: `structural_entropy.anchor_score`, line 310]

### 3.2 Dormancy Threshold

A state must be dormant long enough before it becomes eligible for decay:

$$\tau_{\text{dormant}} = \left\lceil \frac{\log(\text{trace\_floor})}{\log(\rho)} \right\rceil$$

At $\rho = 0.95$: $\sim 90$ cycles. At $\rho = 0.99$: $\sim 459$ cycles.
At $\rho = 0.90$: $\sim 44$ cycles.

The threshold uses $\rho$ — the existing trace decay rate. No new parameter.

[impl: `structural_entropy.dormancy_threshold`, line 268]

### 3.3 Decay Decision

A state is a decay candidate when:

1. $\text{anchor}(s) < \theta_{\text{decay}}(T_s)$ — structurally unimportant
2. $\text{dormancy}(s) > \tau_{\text{dormant}}$ — dormant long enough
3. $s \notin \text{protected}$ — not start, goal, or current state

where $\theta_{\text{decay}}(T_s) = \theta_{\text{base}} \cdot (1 + T_s)$.
The temperature coupling means hotter systems prune more aggressively —
consolidation intensifies as the system accumulates experience.

[impl: `structural_entropy.find_decay_candidates`, line 368]

### 3.4 Ghost Traces (DecayTrace)

When a state is removed, it does not vanish completely. A *DecayTrace*
preserves recognition capacity — enough to re-establish the state if
encountered again:

```
DecayTrace:
  original_state: str       # what was lost
  surviving_neighbors: tuple # who remembers it
  mean_quality: float        # was the experience good or bad?
  peak_load: float           # how significant was it?
  decayed_at_tau: int        # when it dissolved
```

This is the *anecdote* — not the full experience, but a compressed
summary stored per surviving neighbor. The anchor's memory of the lost.

[impl: `structural_entropy.DecayTrace`, line 506]

### 3.5 Decay Execution

Decay proceeds in three phases:

1. **Build traces** from current data (before any removal)
2. **Remove states** and incident edges from the landscape
3. **Clean up** historization entries for removed edges

The audit trail (`_log`) is preserved — historical events remain even
after the structures that produced them are gone.

[impl: `structural_entropy.apply_decay`, line 531]

---

## 4. Edge Fingerprinting

### 4.1 The 4D Edge Fingerprint

Dream mode begins with fingerprinting: encoding each edge's behavioral
identity as a feature vector that is domain-independent. The
`EdgeFingerprint` is a 4-dimensional vector:

$$\mathbf{f}(e) = \left(q(e),\; \sigma(m(e)),\; I(e),\; \text{cs}(e)\right)$$

| Component | Source | Meaning |
|-----------|--------|---------|
| $q(e)$ | `trace_quality` | Valence: good or bad experience |
| $\sigma(m)$ | $m/(m+\mu)$ | Normalized load (sigmoid, $\in [0,1)$) |
| $I(e)$ | `inertia_factor` | How resistant to change |
| $\text{cs}(e)$ | `context_sensitivity` | How variable across contexts |

All four components are derived from historization. No new measurements.

[impl: `dream_mode.EdgeFingerprint`, line 31]

### 4.2 Fingerprint Distance

The distance between two fingerprints uses Euclidean distance with
sigmoid normalization on the load component:

$$d(\mathbf{f}_a, \mathbf{f}_b) = \sqrt{dq^2 + dm^2 + di^2 + dcs^2}$$

where $dq = q_a - q_b$, $dm = \sigma(m_a) - \sigma(m_b)$ (both
pre-normalized), $di = I_a - I_b$, $dcs = \text{cs}_a - \text{cs}_b$.

The sigmoid normalization on load is critical: raw load values can differ
by orders of magnitude (edge at $m = 3$ vs. $m = 300$), but both represent
"well-established" if $m \gg \mu$. The sigmoid compresses this into $[0, 1)$.

[impl: `dream_mode.fingerprint_distance`, line 75]

### 4.3 Fingerprint Extraction

`fingerprint_edges` extracts fingerprints for all edges in a landscape,
tagging each with a domain label. The domain qualification enables
cross-domain comparison: two edges from different domains with similar
fingerprints have similar behavioral signatures.

[impl: `dream_mode.fingerprint_edges`, line 91]

---

## 5. Equivalence Detection

### 5.1 All-Pairs Quantile Filtering

Given two domains with $n$ and $m$ edges, `find_equivalences` computes
all $n \times m$ pairwise distances, then selects those below the
$p$-th quantile as equivalences. The confidence of each equivalence
is $1 - d/d_{\max}$: a zero-distance pair has confidence 1.0.

The quantile approach avoids an absolute threshold — what counts as
"similar" adapts to the actual distribution of distances in each
domain pair. The default quantile (0.25) selects the closest quarter.

[impl: `dream_mode.find_equivalences`, line 126]

### 5.2 Equivalence as Structural Hypothesis

An equivalence is not an assertion of identity. It is a *hypothesis*:
"this edge in domain A behaves like that edge in domain B." The
hypothesis enters the Dream Landscape as an edge between domain-qualified
states, where it is subject to historization. Good analogies strengthen
(via feedback); bad ones decay. This is Paper 3's self-correction at
the meta-level.

---

## 6. Node-Level Fingerprinting

### 6.1 Limitations of Edge Fingerprinting

Edge fingerprints capture behavioral similarity but not structural role.
Two edges with identical $(q, m, I, \text{cs})$ vectors could occupy
radically different positions in their respective graphs — one at the
center of a hub, another at a dead-end leaf. Edge-level equivalence
misses topological context.

### 6.2 NodeFingerprint (Sorted Quality Vector)

The simplest node fingerprint is the sorted vector of trace qualities
on incident edges:

$$\mathbf{n}(s) = \text{sort}\left(\{q(e) : e \in \text{incident}(s)\}\right)$$

Sorting makes the fingerprint invariant to edge labeling. Two nodes
with the same distribution of edge qualities — regardless of which
specific edges carry which quality — are structurally similar.

[impl: `dream_mode.NodeFingerprint`, line 310]

### 6.3 WL Node Fingerprint (Recursive Neighborhood Encoding)

The Weisfeiler–Leman (WL) algorithm encodes not just a node's immediate
edges but its recursive neighborhood. At each depth level, features from
neighbors are aggregated:

**Base features** (9 per node):
- Mean, min, max of incident edge qualities (3)
- Mean, min, max of incident edge loads (3)
- Mean, min, max of incident edge inertia factors (3)

**Recursive aggregation** (depth $d$):
At depth $k$, the node's feature vector is extended with the mean
base features of all nodes at BFS distance $k$. Each depth level
contributes 9 features, and the vectors at each depth are concatenated.

For depth 2 (default): $9 \times (1 + 2^0 + 2^1) = 9 \times 3 = 27$
base features per depth, yielding up to 81 floats total. In practice
the concatenation follows: base (9) + depth-1 neighbors (9) + depth-2
neighbors (9) = 27 base features padded to depth × 9.

The recursive encoding captures structural role: a hub node in a star
graph produces a different WL fingerprint than a node in a chain, even
if their immediate edge statistics are identical.

[impl: `dream_mode.WLNodeFingerprint`, line 361]
[impl: `dream_mode.wl_node_fingerprints`, line 394]

### 6.4 WL Distance

WL fingerprint distance uses Euclidean distance on the feature vectors,
with zero-padding for dimension mismatch:

$$d_{\text{WL}}(\mathbf{w}_a, \mathbf{w}_b) = \sqrt{\sum_i (w_{a,i} - w_{b,i})^2}$$

[impl: `dream_mode.wl_fingerprint_distance`, line 462]

---

## 7. Hungarian Optimal Assignment

### 7.1 The Matching Problem

Given two landscapes $A$ and $B$ with $n_A$ and $n_B$ nodes, we seek
the optimal bijective matching that minimizes total WL distance. This
is the classical assignment problem, solved by the Hungarian algorithm
in $O(\max(n_A, n_B)^3)$.

### 7.2 Implementation

`find_wl_node_equivalences_hungarian` constructs the cost matrix of
pairwise WL distances and calls `scipy.optimize.linear_sum_assignment`
for the optimal matching. Each matched pair becomes a `NodeEquivalence`
with:

- `fp_a`, `fp_b`: the WL fingerprints of the matched nodes
- `distance`: WL distance under optimal assignment
- `confidence`: $1 - d/d_{\max}$ (same formula as edge equivalences)

[impl: `dream_mode.find_wl_node_equivalences_hungarian`, line 487]

### 7.3 Why Hungarian over Greedy

The greedy alternative (mutual-best matching via `find_wl_node_equivalences`)
is faster but suboptimal: it can miss the globally best assignment when
local best-matches conflict. Hungarian guarantees the assignment that
minimizes total distance — the canonical E₀ property: optimality emerges
from the structure, not from heuristic ordering.

This was proven empirically in BT-1 (C137): Hungarian matching detected
structural isomorphisms that greedy matching missed.

---

## 8. The Sleep–Wake Cycle

### 8.1 Dream Pressure

The trigger for consolidation is *dream pressure*:

$$p = \frac{T_s}{T_s + \mu} \in [0, 1)$$

This is the same sigmoid shape as inertia factor — the system's own
half-load constant $\mu$ determines the tipping point.

| $T_s$ | $p$ | Interpretation |
|-------|-----|----------------|
| $\approx 0$ | $\approx 0$ | Cold system, keep learning |
| $= \mu$ | $0.5$ | Threshold — dream if exceeded |
| $\gg \mu$ | $\to 1$ | Hot system, dream immediately |

`should_dream` $\iff$ $p > 0.5$ $\iff$ $T_s > \mu$. No new parameter —
$\mu$ and the threshold 0.5 (the sigmoid's natural midpoint) are both
pre-existing.

[impl: `structural_entropy.dream_pressure`, line 82]
[impl: `structural_entropy.should_dream`, line 110]

### 8.2 The Cycle

`SleepWakeCycle` orchestrates alternation between active navigation
and passive consolidation:

```
WAKE:  controller.run()  →  T_s rises  →  inscription slows
CHECK: should_dream(hist) →  any domain over threshold?
SLEEP: DreamObserver.dream_cycle() × max  →  decay lowers T_s
WAKE:  inscription resumes  →  new experience  →  T_s rises …
```

The cycle does not modify the controller or dream observer. It only
decides *when* to call `dream_cycle()`, based on dream pressure.

Each episode produces a `WakePhase` (controller trace, $T_s$ before/after,
pressure) and optionally a `SleepPhase` (dream cycle results,
$T_s$ before/after). The sleep phase runs dream cycles until no domain
exceeds the pressure threshold or the safety cap is reached.

[impl: `sleep_wake.SleepWakeCycle`, line 82]

### 8.3 Multi-Domain Coordination

`SleepWakeCycle` supports N domain controllers. The dream trigger fires
when *any* domain exceeds the pressure threshold — the hottest domain
controls the cycle. During sleep, `dream_cycle()` observes *all* ready
domains, enabling cross-domain pattern extraction even though only one
domain triggered the transition.

[impl: `sleep_wake.SleepWakeCycle.run`, line 161]

### 8.4 Dream Peer Wiring

`wire_peer_fns()` auto-creates a peer function for each registered
controller that consults dream equivalences during overload. This is a
non-invasive integration: the controller's `peer_fn` interface accepts
`(landscape, current, neighbors) → Optional[str]`, and the dream-based
implementation transparently proposes bridge targets from dream state.

[impl: `sleep_wake.SleepWakeCycle.wire_peer_fns`, line 129]

---

## 9. Dream Landscape and DreamObserver

### 9.1 The Dream Landscape as Meta-Landscape

Detected equivalences are stored in a *Dream Landscape* — not an external
database but an E₀ landscape itself. States are domain-qualified edges
(`"chess:A→B"`) or domain-qualified nodes (`"chess:A"`). Edges represent
equivalence hypotheses with:

- $\Delta$ = fingerprint distance (low distance = high similarity)
- $R_0$ = `base_resistance / confidence` (uncertain hypotheses are expensive)

Because the Dream Landscape is a standard E₀ landscape, it is subject to
the same historization and decay as any domain landscape. Good analogies
accumulate SUCCESS historization and strengthen; bad ones accumulate FAILURE
and eventually fall below the anchor threshold. This is Paper 3's
self-correction operating at the meta-level.

[impl: `dream_mode.build_dream_landscape`, line 796]

### 9.2 DreamObserver Lifecycle

The `DreamObserver` is a passive multi-domain watcher:

1. **Registration**: domains are registered as read-only landscape references
2. **Readiness check**: `dream_readiness(landscape)` — mean inertia factor
   over all edges; must exceed threshold to ensure fingerprints are stable
3. **Compatibility check** (C168): pairwise structural compatibility via
   `StructuralResonance`; incompatible pairs are skipped
4. **Edge equivalence detection**: `find_equivalences()` on each compatible pair
5. **Node equivalence detection** (C139): `find_wl_node_equivalences_hungarian()`
   for structural role matching
6. **Dream Landscape update**: incremental — new equivalences are added,
   existing ones retain their historization
7. **Structural decay** (C119, optional): if `decay_enabled`, consolidate
   each domain landscape — patterns are extracted *before* decay, then
   graphs are compressed

The observer does not modify domain landscapes during fingerprinting
or equivalence detection. Structural decay (step 7) is the only mutating
operation and is explicitly opt-in.

[impl: `dream_mode.DreamObserver`, line 844]
[impl: `dream_mode.DreamObserver.dream_cycle`, line 931]

### 9.3 Incremental Dream Landscape Update

The Dream Landscape is updated incrementally across cycles:

- New equivalences are added as new states and edges
- Existing equivalences are *not* re-added — their historization persists
- A `_known_edges` set provides $O(1)$ deduplication

This means the Dream Landscape accumulates experience across cycles. An
equivalence that was productive in cycle 5 retains its trace quality in
cycle 50, even if the specific domain configurations have changed. The
Dream Landscape has its own *memory* — independent of, but derived from,
domain landscapes.

[impl: `dream_mode.DreamObserver._update_dream_landscape`, line 1068]

### 9.4 Feedback Loop

When a bridge hypothesis derived from a dream equivalence is used in
cross-reflexion, the outcome feeds back into the Dream Landscape:

```
DreamObserver.feedback("chess:A→B", "invoice:X→Y", Outcome.SUCCESS)
```

This historizes both directions of the equivalence edge. Good analogies
strengthen; bad ones weaken. The feedback loop is what gives the Dream
Landscape its self-correcting character.

[impl: `dream_mode.DreamObserver.feedback`, line 1167]

---

## 10. Bridge Hypothesis Generation

### 10.1 Edge-Level Bridges (C111)

`propose_bridges` translates dream equivalences into concrete
cross-reflexion proposals:

1. Query dream equivalences for the target domain, filtered by quality
2. Group by partner domain, take best quality per partner
3. For each partner: compute coupling discount from equivalence quality
4. Call `cross_propose_edges(target, partner, current, goal)` with discount
5. Wrap in `BridgeHypothesis`

The coupling discount formula:

$$d_{\text{coupling}} = d_{\text{base}} \cdot \max(0, q_{\text{eq}})$$

- $q_{\text{eq}} = 1.0$ → full discount (complete trust)
- $q_{\text{eq}} = 0.5$ → half discount (partial trust)
- $q_{\text{eq}} \leq 0$ → zero discount (no trust — bad analogy suppressed)

This is the key integration: dream observation ↔ cross-reflexion.
The Dream Landscape's historization (via feedback) determines which
partner domains are trusted — Paper 3's self-correction at the
cross-domain level.

[impl: `dream_mode.propose_bridges`, line 1381]
[impl: `dream_mode.dream_coupling_discount`, line 1352]

### 10.2 Node-Level Bridges (C154)

`propose_node_bridges` uses node-level equivalences from Hungarian
matching for structural transfer:

1. Find donor nodes matching `current` via Dream Landscape
2. For each donor match: list donor's outgoing edges
3. For each donor edge target: check reverse mapping back to target domain
4. Propose `current → mapped_target` with discounted parameters

This is topological analogy: "if my structural equivalent in domain B
goes from X to Y, maybe I should go from here to the mapped Y."

The donor's navigation pattern is proposed as a hypothesis for the target
domain. Resistance is inflated by the inverse discount ($R_0 / d$),
encoding uncertainty in the structural transfer.

A `confidence_floor` (default 0.1) breaks the bootstrapping chicken-and-egg:
without it, no proposals would be generated until historization confirms
them — but historization requires proposals to exist first.

[impl: `dream_mode.propose_node_bridges`, line 1555]

### 10.3 Dream Peer Function

`make_dream_peer_fn` creates a `peer_fn` compatible with
`E0Controller.peer_fn` that transparently consults dream equivalences:

1. Try edge-level bridges first (`propose_bridges`)
2. If no proposals, try node-level bridges (`propose_node_bridges`)
3. If a proposal target is in the current admissible neighbors, return it
4. Otherwise return `None` (controller handles normally)

The controller never knows it is consulting dream equivalences. It
receives a peer suggestion through the standard interface.

[impl: `dream_mode.make_dream_peer_fn`, line 1693]

---

## 11. Structural Resonance

### 11.1 Unified Comparison Metric (C260)

`StructuralResonance` combines WL-Hungarian node matching with Jaccard
structural distance into a single metric:

$$r = 0.7 \cdot c_{\text{compat}} + 0.3 \cdot c_{\text{overlap}}$$

where:
- $c_{\text{compat}} = \max(0, 1 - \bar{d}_{\text{WL}})$ — topology match
  (1.0 for identical WL fingerprints, 0.0 for distance ≥ 1.0)
- $c_{\text{overlap}} = 1 - d_{\text{Jaccard}}$ — state set overlap
  (1.0 for identical states, 0.0 for disjoint)

The 70/30 weighting reflects a design judgment: topological similarity
(WL) matters more than naming overlap (Jaccard) for structural
comparison. This is classified as heuristic — the specific ratio
is empirically motivated but not derived.

### 11.2 Compatibility Gating (C168)

`StructuralResonance.compatibility` (mean WL distance under Hungarian
assignment) serves as the compatibility gate for dream cycles:

| Compatibility | Interpretation |
|---------------|----------------|
| < 0.5 | Structurally compatible (near-isomorphic) |
| 0.5–0.7 | Borderline |
| > 0.7 | Incompatible (dream matching is noise) |

When `compatibility_threshold` is set, the DreamObserver skips domain
pairs that exceed it — preventing spurious equivalence detection between
structurally incompatible domains.

[impl: `dream_mode.find_structural_resonance`, line 671]
[impl: `dream_mode.dream_compatibility`, line 606]

---

## 12. Empirical Validation

### 12.1 Test Coverage

The three modules are covered by 186 tests:

| Module | Test File | Tests |
|--------|-----------|-------|
| `structural_entropy.py` | `test_structural_entropy.py` | ~60 |
| `dream_mode.py` | `test_dream_mode.py`, `test_dream_node_equiv.py` | ~100 |
| `sleep_wake.py` | `test_sleep_wake.py` | ~26 |

### 12.2 Key Validated Properties

**Structural temperature:**
- $T_s = 0$ for empty historization (virgin systems)
- $T_s > 0$ for any non-empty historization
- $T_s$ increases monotonically with trace load at fixed quality

**Type 1 forgetting:**
- Virgin edges ($m = 0$) always inscribed ($\varepsilon = 0$)
- Cold systems ($T_s \approx 0$) inscribe everything
- Experienced edges filter routine outcomes
- should_inscribe is monotonically selective with $T_s$

**Type 2 forgetting:**
- Anchor states resist decay (high score = protected)
- Dormancy threshold derived from $\rho$ alone
- DecayTraces preserve recognition capacity
- Protected states (start, goal, current) are never candidates

**Dream fingerprinting:**
- Identical edges have distance 0
- Distance metric is symmetric
- Sigmoid normalization compresses load into $[0, 1)$
- WL fingerprints distinguish topologically distinct nodes
- Hungarian matching detects structural isomorphisms (BT-1, C137)

**Sleep–Wake cycle:**
- Dream pressure follows sigmoid with $\mu$ as midpoint
- $T_s = \mu$ is the exact trigger point ($p = 0.5$)
- Consolidation lowers $T_s$ (via decay)
- Cycle converges to a rhythm (not a one-shot operation)

**Bridge hypotheses:**
- Coupling discount scales linearly with equivalence quality
- Negative quality → zero discount (bad analogies suppressed)
- Node-level bridges respect confidence floor for bootstrapping

---

## 13. Honesty Classification

### 13.1 Derived (from $\Delta$, $R$, $H$ and proven predecessors)

| Claim | Derivation |
|-------|------------|
| $T_s = \bar{m}/\bar{q}$ | Ratio of existing historization statistics |
| Dream pressure $p = T_s/(T_s+\mu)$ | Same sigmoid as inertia factor with existing $\mu$ |
| Inscription threshold $\varepsilon(e) = \varepsilon_0 \cdot (1 - e^{-m/\mu})$ | Existing $\mu$, same exponential form |
| Virgin edges always inscribed | $m = 0 \Rightarrow \varepsilon = 0$ (algebraic) |
| $\tau_{\text{dormant}}$ from $\rho$ | $\lceil \log(\text{floor})/\log(\rho) \rceil$ (algebraic) |
| Edge fingerprint components ($q$, $m$, $I$, cs) | All from existing historization |
| Dream Landscape is an E₀ landscape | Same `Landscape` class, same primitives |
| `should_dream` $\iff T_s > \mu$ | $p > 0.5 \iff T_s/(T_s+\mu) > 0.5 \iff T_s > \mu$ |

### 13.2 Empirical (validated by tests but not proven in general)

| Claim | Status |
|-------|--------|
| WL depth 2 sufficient for tested graphs | 186 tests pass; may need more for exotic topologies |
| Quantile 0.25 selects meaningful equivalences | Works on all tested domain pairs; not proven optimal |
| Hungarian matching detects isomorphisms | Proven for tested cases (BT-1); correct by algorithm guarantees |
| $T_s$ decreases after dream cycle with decay | Observed in tests; monotonicity not proven for all configurations |
| Bridge hypotheses improve navigation | Observed in cross-domain benchmarks; not guaranteed |
| Compatibility threshold 0.5 separates signal from noise | Empirically calibrated; domain-dependent |

### 13.3 Heuristic (design choices not derived from axioms)

| Choice | Rationale |
|--------|-----------|
| Euclidean distance for fingerprints | Simple, interpretable; other metrics possible |
| Sigmoid for load normalization | Consistent with inertia factor form |
| WL depth 2 (default) | Computational cost vs. discriminative power tradeoff |
| $\theta_{\text{base}} = 0.5$ | Baseline anchor threshold; empirically calibrated |
| 70/30 weighting in resonance score | Topology matters more than naming; ratio is judgment |
| `base_resistance = 0.5` for Dream Landscape | Sets speculation cost; could be calibrated |
| `confidence_floor = 0.1` for node bridges | Bootstrap threshold; not derived |

---

## 14. Conclusion

### 14.1 Summary

This paper closes E₀'s consolidation gap. Three mechanisms — inscription
threshold, structural decay, and the sleep–wake cycle — implement
selective forgetting, graph compression, and automatic rhythm respectively.
Dream mode detects cross-domain patterns through a hierarchy of
fingerprinting algorithms, populating a meta-landscape that is itself
subject to E₀'s dynamics. Bridge hypotheses translate dream observations
into navigation proposals.

The key structural insight: **consolidation is not an addition to E₀
but a consequence of its existing parameters.** $T_s$ is a ratio of $\bar{m}$
and $\bar{q}$; dream pressure uses $\mu$; dormancy uses $\rho$; inscription
uses $\mu$ again. The only new parameter is $\theta_{\text{base}}$ for
anchor-based decay — and even that is scaled by $T_s$, coupling it to the
system's own experience statistics.

### 14.2 Structural Claim

*Claim:* A system with $\Delta$, $R$, and $H$ that operates long enough
will accumulate structural temperature until inscription gate and dream
cycle engage. Consolidation is *inevitable* in any sufficiently active
E₀ system — it is the structural dual of experience accumulation.

*Classification:* Derived (from the monotonic growth of $\bar{m}$ under
active navigation and the sigmoid threshold at $T_s = \mu$).

### 14.3 Open Questions

1. **Optimal decay threshold.** $\theta_{\text{base}} = 0.5$ is
   empirically calibrated. Can it be derived from $\Delta$, $R$, $H$?
2. **WL depth scaling.** Depth 2 suffices for tested graphs (≤ 100
   states). Does discriminative power degrade on larger topologies?
3. **Dream Landscape persistence.** The current implementation starts
   fresh per session. How should dream knowledge persist across
   restarts?
4. **Multi-level resonance.** Communities (Paper 9) partition
   landscapes. Should dream mode operate on community sub-landscapes
   rather than full domain landscapes?

---

## Appendix A: Formula Reference

| Symbol | Definition | Source |
|--------|-----------|--------|
| $T_s$ | $\bar{m}/\bar{q}$ | `structural_temperature` |
| $p$ | $T_s/(T_s + \mu)$ | `dream_pressure` |
| $\varepsilon_0(T_s)$ | $1 - e^{-T_s/\mu}$ | `inscription_threshold` |
| $\varepsilon(e)$ | $\varepsilon_0 \cdot (1 - e^{-m/\mu})$ | `inscription_threshold` |
| novelty$(e, o)$ | $|\text{signal}(o) - q(e)|$ | `novelty` |
| anchor$(s)$ | $|\bar{q}_s| \cdot m_{\max} \cdot \log(1+\deg)$ | `anchor_score` |
| $\tau_{\text{dormant}}$ | $\lceil \log(\text{floor})/\log(\rho) \rceil$ | `dormancy_threshold` |
| $\theta_{\text{decay}}$ | $\theta_{\text{base}} \cdot (1 + T_s)$ | `find_decay_candidates` |
| $d(\mathbf{f}_a, \mathbf{f}_b)$ | $\sqrt{dq^2 + dm^2 + di^2 + dcs^2}$ | `fingerprint_distance` |
| $d_{\text{coupling}}$ | $d_{\text{base}} \cdot \max(0, q_{\text{eq}})$ | `dream_coupling_discount` |
| $r$ | $0.7 \cdot c_{\text{compat}} + 0.3 \cdot c_{\text{overlap}}$ | `find_structural_resonance` |

## Appendix B: Module Architecture

```
structural_entropy.py (599 lines)
├── structural_temperature()          T_s computation
├── dream_pressure()                  Sigmoid trigger
├── should_dream()                    Binary decision
├── inscription_threshold()           Per-edge ε(e)
├── should_inscribe()                 novelty > ε gate
├── anchor_score()                    State importance
├── find_decay_candidates()           State pruning candidates
├── find_anchors()                    Surviving landmarks
├── apply_decay()                     Execute removal + DecayTrace
└── dormancy_threshold()              τ_dormant from ρ

dream_mode.py (1742 lines)
├── EdgeFingerprint                   4D behavioral vector
├── fingerprint_distance()            Euclidean + sigmoid
├── Equivalence                       Edge-level hypothesis
├── find_equivalences()               All-pairs quantile
├── NodeFingerprint                   Sorted quality vector
├── WLNodeFingerprint                 Recursive neighborhood
├── find_wl_node_equivalences_hungarian()  Optimal assignment
├── StructuralResonance               Unified comparison
├── find_structural_resonance()       WL + Jaccard combined
├── DreamObserver                     Multi-domain lifecycle
│   ├── dream_cycle()                 Full observation pass
│   ├── feedback()                    Bridge result → historization
│   ├── equivalences_for()            Query edge equivalences
│   └── node_equivalences_for()       Query node equivalences
├── BridgeHypothesis                  Cross-reflexion proposal
├── propose_bridges()                 Edge-level transfer
├── propose_node_bridges()            Node-level transfer
└── make_dream_peer_fn()              Controller integration

sleep_wake.py (270 lines)
├── WakePhase                         Controller run result
├── SleepPhase                        Dream consolidation result
├── EpisodeResult                     Wake + optional sleep
└── SleepWakeCycle                    Orchestrator
    ├── register()                    Add domain controller
    ├── wire_peer_fns()               Auto-create dream bridges
    └── run()                         N-episode wake/sleep loop
```

## Appendix C: Commit Provenance

| Commit | Content |
|--------|---------|
| C109 | Dream Mode: edge fingerprinting + equivalence detection |
| C110 | DreamObserver: passive multi-domain watcher |
| C111 | Bridge hypotheses: dream → cross-reflexion integration |
| C112 | Dream Landscape: meta-landscape of equivalences |
| C114–C120 | Structural Entropy: Type 1 + Type 2 forgetting |
| C119 | Decay during dream: consolidation after pattern extraction |
| C121 | Sleep–Wake Cycle: automatic rhythm |
| C137 | BT-1: Hungarian optimal assignment for node matching |
| C139 | WL node fingerprints in DreamObserver |
| C154 | Node-level bridge proposals + dream peer wiring |
| C168 | Compatibility-gated dreaming |
| C260 | Unified Structural Resonance metric |

## Appendix D: Biological Analogy Reference

| E₀ Mechanism | Biological Analogue | Structural Parallel |
|-------------|---------------------|---------------------|
| Inscription threshold | Habituation | Repeated stimuli stop producing responses |
| Structural decay | Synaptic pruning | Unused connections dissolve |
| DecayTrace | Priming / déjà vu | Compressed trace enables re-recognition |
| Anchor score | Long-term potentiation | Strong, central, emotional = preserved |
| Dream fingerprinting | Pattern completion | Abstract features from specific instances |
| Dream equivalences | Analogical transfer | Map structure across domains |
| Sleep–Wake rhythm | Circadian sleep cycle | Activity → heat → consolidation → clarity |
| Dream Landscape | Semantic memory | Patterns extracted from episodic experience |
| Bridge hypothesis | Creative insight | "What if X works like Y?" |
