# E₀-IX: Emergent Structure — Community Detection from Historization

**Thomas Wehner**

---

## Abstract

Papers 1–6 assume that structural groupings (domains, clusters) are
provided externally. This paper removes that assumption. We show that
community structure emerges from Historization data alone, using weighted
Label Propagation on edge resistance values. The construction addresses
GT-7 (Coherent Domain Error, C233–C254): a 22-commit arc that imposed
semantic prefixes as structural tokens — a violation of E₀'s domain
invariance principle. The resolution (C255–C267) replaces all prefix-based
partitioning with a single algorithm that operates on R_eff = R₀ + δ_H,
requiring zero additional parameters. We prove three structural properties:
(1) cold start equivalence — fresh landscapes yield connected-component
partitions identical to topology; (2) dynamic adaptation — success lowers
inter-community resistance (merging), failure raises it (splitting);
(3) determinism — identical landscapes produce identical partitions.
Normalized Mutual Information between emergent communities and the legacy
prefix partition shows NMI ≥ 0.7 across all tested domains, validating
that the emergent structure recovers semantic boundaries without being
told they exist. The complete migration (macro + micro level) is validated
by 65 unit tests and zero regressions on the existing 5741-test suite.
All claims are classified as derived, empirical, or heuristic.

---

## 1. Introduction

### 1.1 The Problem: Where Do Domains Come From?

E₀'s canon states: *"E₀ is not a theory of objects, meanings, goals,
agents, or domains."* Yet the implementation (C233–C254) organized its
landscape into named regions using string prefixes — `C:`, `EN:`, `M:`,
`B:`, `L:` — as architectural domain boundaries. Dream mode partitioned
by prefix. Sleep-Wake cycled per prefix domain. Diagnostics reported per
prefix group.

This worked. For 22 commits, every feature was individually correct and
every test passed. The error was *coherent*: internally consistent across
all subsystems, which made it hard to detect.

### 1.2 How GT-7 Was Detected

The system's own dynamics exposed the problem through two symptoms:

1. **C253 — Teach→Ask Disconnect.** Teaching a concept placed it in one
   prefix domain; asking about it searched a different one. The prefix
   boundary was invisible to the knowledge graph.

2. **C254 — Dream Dead-End.** Dream mode detected equivalences *within*
   prefix domains but could not discover cross-domain structure, because
   its partitioning was the same labels it was trying to transcend.

Both symptoms reduce to the same root cause: string prefixes encode E₂
(instantiation-level) semantics as E₀ (primitive-level) structure. This
violates domain invariance — the property that E₀ dynamics should be
independent of what the states *mean*.

### 1.3 Our Approach

We replace all imposed partitioning with a single algorithm that discovers
community structure from the landscape's own data:

1. **Detection** (§2): Weighted Label Propagation on R_eff edge weights.
2. **Validation** (§3): Normalized Mutual Information between emergent
   and prefix-based partitions.
3. **Migration** (§4): Complete replacement at macro level (C255–C262)
   and micro level (C263–C267).
4. **Properties** (§5): Cold start, dynamic adaptation, determinism.

The algorithm adds zero new parameters — it reuses R_eff, which already
encodes the full path structure including Historization.

---

## 2. Community Detection Algorithm

### 2.1 Weighted Label Propagation

Given a landscape $L_t = (X_t, E_t, v_t, S_t, H_t)$, we define the
community partition $\mathcal{C}$ as the fixed point of weighted Label
Propagation Algorithm (LPA) on the undirected graph induced by R_eff.

**[impl: community.detect_communities, line 38]**

**Step 1 — Build undirected weighted adjacency.**
For each directed edge $e = (s, t) \in E_t$:
$$w(s, t) \mathrel{+}= \frac{1}{R_{\text{eff}}(s, t)}$$
$$w(t, s) \mathrel{+}= \frac{1}{R_{\text{eff}}(s, t)}$$

where $R_{\text{eff}}(s, t) = R_0(s, t) + \delta_H(s, t)$ is the effective
resistance including historization. If both $(s, t)$ and $(t, s)$ exist
as directed edges, both contribute to $w(s, t)$.

**Step 2 — Initialize labels.**
Each node receives a unique integer label: $\ell_i = i$ for
$i = 0, \ldots, |X_t| - 1$ (nodes in sorted order).

**Step 3 — Propagate.**
Repeat until convergence or max_iterations:
$$\ell_i \leftarrow \arg\min_{\ell^*} \left( -\sum_{j \in \mathcal{N}(i) : \ell_j = \ell^*} w(i, j), \; \ell^* \right)$$

This selects the label with the highest total weight among neighbors, with
ties broken by the smallest label value.

**Step 4 — Extract communities.**
Group nodes by final label: $C_k = \{x_i : \ell_i = k\}$.
Return communities sorted by smallest member.

### 2.2 Key Design Choices

**Undirected treatment.** Directed edges are symmetrized because community
membership is a symmetric relation — if $A$ and $B$ are in the same
community, both directions contribute evidence.

**Inverse resistance weighting.** Low $R_{\text{eff}}$ means the transition
is reliable and well-traveled. $w = 1/R_{\text{eff}}$ makes reliable
connections attract nodes together.

**Determinism.** Nodes are processed in sorted order, and ties are broken
by smallest label. This ensures that `detect_communities(L)` produces
identical output for identical input — a requirement for reproducibility
and for caching in `SessionState.communities`.

**No tuning parameters.** The algorithm uses $R_{\text{eff}}$ directly.
No clustering threshold, no target community count, no distance metric.
The only safety parameter is `max_iterations=100`, which is never reached
in practice (typical convergence: 3–8 iterations).

---

## 3. Validation: Normalized Mutual Information

To verify that emergent communities recover meaningful structure,
we compare them against the legacy prefix partition using NMI.

**[impl: community.normalized_mutual_information, line 128]**

### 3.1 Definition

Given two partitions $A$ and $B$ over the same node set,
Normalized Mutual Information is:

$$\text{NMI}(A, B) = \frac{2 \cdot \text{MI}(A, B)}{H(A) + H(B)}$$

where $H(\cdot)$ is Shannon entropy and $\text{MI}(A, B)$ is mutual
information. NMI ∈ [0, 1]: 0 means independent, 1 means identical.

### 3.2 Interpretation

We use `compare_partitions()` to classify alignment:

| NMI Range | Verdict | Meaning |
|-----------|---------|---------|
| ≥ 0.70 | `aligned` | Emergent structure recovers semantic boundaries |
| 0.30–0.69 | `partial` | Partial overlap — some semantic structure emerges |
| < 0.30 | `divergent` | Emergent structure disagrees with prefixes |

**[impl: community.compare_partitions, line 314]**

### 3.3 Empirical Result

Across all tested configurations with established Historization:
NMI ≥ 0.7 between emergent communities and prefix-based domains.
The emergent algorithm discovers the same boundaries that were previously
hard-coded — without being told they exist.

---

## 4. The GT-7 Migration (C255–C267)

### 4.1 Macro Level (C255–C262)

| Commit | Subsystem | Change |
|--------|-----------|--------|
| C255–C256 | Foundation | community.py: LPA + NMI + compare_partitions |
| C257 | Dream Mode | Default: `partition='community'` |
| C258–C261 | Sleep-Wake, Curriculum, Diagnostics | All use communities |
| C262 | Macro Audit | Verified all macro-level prefix usage replaced |

### 4.2 Micro Level (C263–C267)

| Commit | Change |
|--------|--------|
| C263 | Cold start: `include_en=False` by default |
| C264 | Structural resonance replaces lexical fallback for bridges |
| C265 | `SessionState.communities` cache + `refresh_communities()` |
| C266 | `navigate()` uses `community_of()` instead of `_domain_of()` |
| C267 | DeprecationWarning on all prefix fallbacks. Single partition world. |

### 4.3 The Micro-Level Migration Problem

Post C262, the macro level used communities but the micro level still used
prefixes. This created two partitioning worlds in the same system — a
structural contradiction detected by the perspective check *"If I migrated
the macro level to mechanism X — does the micro level still use mechanism Y?"*

Eight decision points in `navigate()` required migration:

1. Crossing detection (`is_crossing`)
2. Bridge bonus scoring
3. Domain context in navigation results
4. Teach bridge proposal
5. Dream bridge proposal
6. Coupling router domain identification
7. Type usage tracking
8. Multi-domain round result aggregation

All eight were migrated to use `community_of(node, communities)` in
C265–C267. The `_domain_of()` function now emits a `DeprecationWarning`.

---

## 5. Structural Properties

### 5.1 Cold Start Equivalence

**Claim (Derived):** When $\delta_H = 0$ for all edges (no historization),
`detect_communities()` returns the connected components of the landscape.

**Proof:** With $\delta_H = 0$, $R_{\text{eff}} = R_0$ for all edges.
All edges within a connected component have finite positive $R_0$, so
$w > 0$. Label propagation on a connected subgraph converges to a single
label (the smallest, by tie-breaking). Nodes in different connected
components have $w = 0$ between them, so labels never cross.

**[test: test_community.py::TestCommunityHistorization::test_cold_start_equals_topology]**

This means the algorithm degenerates gracefully: before any navigation
has occurred, communities are exactly the topological components — the
most conservative possible partition.

### 5.2 Dynamic Adaptation

**Claim (Derived):** Repeated SUCCESS on an edge lowers $R_{\text{eff}}$
and increases the weight $w = 1/R_{\text{eff}}$, making the connected
nodes more likely to share a community label. Repeated FAILURE has the
opposite effect.

**Proof:** By the historization update rules (Paper 1, §2), SUCCESS
increments $U$, which via trace quality $q = (U - F)/(U + F + 1)$
reduces $\delta_H$ (high quality → low correction). FAILURE increments
$F$, which increases $\delta_H$. Since $R_{\text{eff}} = R_0 + \delta_H$,
success lowers $R_{\text{eff}}$ and failure raises it.

In Label Propagation, higher $w$ means stronger attraction toward the
same label. Therefore, frequently successful transitions pull their
endpoints into the same community, and failing transitions push theirs
apart.

**[test: test_community.py::TestCommunityHistorization::test_success_merges_communities]**

**[test: test_community.py::TestCommunityHistorization::test_failure_splits_community]**

### 5.3 Determinism

**Claim (Derived):** `detect_communities(L)` is a deterministic function.
Identical landscapes produce identical partitions.

**Proof:** The algorithm has no random state. Node iteration order is
fixed (sorted string comparison). Tie-breaking is fixed (smallest label).
Weight computation is a pure function of $R_{\text{eff}}$. Therefore the
full computation is deterministic.

**[test: test_community.py::TestCommunityProperties::test_determinism_same_result_twice]**

### 5.4 No Side Effects

**Claim (Derived):** `detect_communities(L)` does not modify the
landscape. It is a pure read operation.

**[test: test_community.py::TestCommunityProperties::test_no_side_effects_on_landscape]**

---

## 6. Sub-Landscape Extraction

### 6.1 Purpose

For subsystems that operate per-domain (Dream, Sleep-Wake, Self-Tuning),
we need to extract sub-landscapes preserving intra-community edges and
their historization traces.

**[impl: community.extract_community_landscapes, line 209]**

### 6.2 Algorithm

Given communities $\mathcal{C} = \{C_0, C_1, \ldots\}$:

1. For each community $C_k$, create a new Landscape $L_k$.
2. Add all nodes $x \in C_k$ to $L_k$.
3. For each edge $e = (s, t)$ where $s, t \in C_k$:
   - Copy $\Delta(e)$ and $R_0(e)$ from the source landscape.
   - Copy historization traces $(U, F)$ from the source landscape.
4. Name the sub-landscape `community_k`.

Inter-community edges are excluded. This preserves the intra-community
dynamics while isolating each community for independent processing.

**[test: test_community.py::TestExtractCommunityLandscapes (8 tests)]**

---

## 7. Benchmark: Prefix vs. Emergent Partitioning

### 7.1 Setup

We compare three partitioning strategies on landscapes with established
historization:

1. **Prefix** — Legacy `_domain_of()` using string prefix regex.
2. **Community** — `detect_communities()` on R_eff.
3. **Ground truth** — Manual partition based on semantic understanding.

### 7.2 Result

| Metric | Prefix vs. Truth | Community vs. Truth | Community vs. Prefix |
|--------|:----------------:|:-------------------:|:--------------------:|
| NMI | 1.00 (by design) | ≥ 0.70 | ≥ 0.70 |
| Requires labels | Yes | No | — |
| Adapts to navigation | No | Yes | — |
| Works on cold start | Yes (if prefixed) | Yes (→ topology) | — |
| Works without prefixes | No | Yes | — |

The prefix partition achieves perfect NMI with truth because truth *was*
the prefix scheme. The emergent partition independently discovers
equivalent structure, without access to the prefix labels, and additionally
adapts as navigation history accumulates.

---

## 8. The GT-7 Lesson: Coherent Errors

### 8.1 Why It Took 22 Commits to Detect

GT-7 is unusual because each individual commit was correct. The error was
in the assumption shared across all commits: that string prefixes are valid
E₀-level structure. This assumption was:

- **Consistent:** Dream, Sleep-Wake, Curriculum all used the same prefixes.
- **Functional:** All tests passed because the tests encoded the same assumption.
- **Invisible:** No single subsystem could detect the problem in isolation.

### 8.2 How E₀'s Own Dynamics Exposed It

The symptoms (§1.2) were not external observations — they were the
system's behavior telling us the partitioning was wrong:

1. Dream could not discover cross-domain equivalences because it was
   already partitioned by the labels it was trying to transcend.
2. Teach placed knowledge in one prefix domain while the query searched
   another — the knowledge graph did not respect the prefix boundaries.

Both symptoms are impossible if the partitioning reflects the actual
structure. Their occurrence *requires* that the partition is imposed
rather than emergent.

### 8.3 The Lesson

> **Domains are E₂ artifacts, not E₀ primitives.** Structure must emerge
> from Historization, not from labels. Coherent errors are the hardest to
> find because each commit is individually correct. E₀'s own dynamics
> expose them: symptoms are the system telling us the assumption is wrong.

This is now working principle #9 in bootstrap.json with 8 confirmations
and 0 contradictions (trace quality q = 0.89).

---

## 9. Discussion

### 9.1 Self-Similarity

The community detection algorithm applies the same E₀ primitive (R_eff)
at the partition level that the controller uses at the navigation level.
This is not a coincidence — it is a consequence of E₀'s self-similar
architecture. The same quantity that guides which edge to traverse also
determines which nodes belong together.

### 9.2 Relationship to Standard Community Detection

Weighted LPA is a well-known algorithm in network science (Raghavan et al.,
2007). Our contribution is not the algorithm itself but:

1. **The weight function** — using $1/R_{\text{eff}}$ where $R_{\text{eff}}$
   includes historization data. This makes the partition dynamic.
2. **The application** — replacing imposed domain labels in a self-modifying
   system.
3. **The validation** — showing that emergent structure recovers semantic
   structure (NMI ≥ 0.7) without access to semantic labels.

### 9.3 Limitations

1. **LPA convergence is not guaranteed for all graphs.** On certain
   pathological topologies, labels can oscillate. The `max_iterations=100`
   cap prevents infinite loops but may yield sub-optimal partitions.
   In practice, convergence occurs in 3–8 iterations on all tested
   landscapes (up to N=500).

2. **NMI validation assumes prefix labels are ground truth.** The ≥ 0.7
   threshold validates consistency, not correctness. The emergent partition
   could be *better* than the prefix partition — we cannot distinguish
   this case from imperfect detection.

3. **Single-scale detection.** LPA finds one partition level. Hierarchical
   community structure (communities within communities) is not detected.
   This is sufficient for current use but may become a limitation for
   deeply nested landscapes.

---

## 10. Honesty Classification

### 10.1 Derived Claims (provable from definitions)

| Claim | Section | Evidence |
|-------|---------|----------|
| Cold start = connected components | §5.1 | Proof from R_eff definition |
| Success merges, failure splits | §5.2 | Proof from historization update rules |
| Determinism | §5.3 | No random state, fixed order/tiebreaker |
| No side effects | §5.4 | Pure read, no landscape mutation |

### 10.2 Empirical Claims (bounded by test conditions)

| Claim | Section | Conditions | Tests |
|-------|---------|------------|-------|
| NMI ≥ 0.7 on navigated landscapes | §3.3 | All tested configurations | 5 |
| LPA converges in 3–8 iterations | §9.3 | Tested up to N=500 | 8 |
| 100-node landscape → correct 10 clusters | §5 | Synthetic benchmark | 1 |

### 10.3 Heuristic Claims (observed, not proven)

| Claim | Section | Status |
|-------|---------|--------|
| Emergent partitions are *better* than prefix partitions | §7.2 | Plausible but unproven — no oracle |
| Single partition world eliminates all prefix bugs | §4.3 | Confirmed up to C270; cannot prove absence |

---

## 11. Conclusion

Community structure in E₀ landscapes is not a feature to be added — it is
a quantity that already exists in the historization data and needs only to
be read. Weighted Label Propagation on $1/R_{\text{eff}}$ discovers, at
zero parameter cost, the same domain boundaries that 22 commits of
prefix-based engineering tried to impose. The migration (C255–C267)
replaced every prefix-based decision across macro and micro levels with a
single emergent mechanism, validated by NMI comparison and 65 dedicated
tests.

GT-7 is the project's most instructive error. Not because the code was
wrong — it worked for 22 commits — but because the assumption was wrong
and the system's own behavior was the signal. The lesson — *domains are
E₂ artifacts, not E₀ primitives* — has been confirmed 8 times since and
is the most validated working principle in the project.

---

## Appendix A: Module Inventory

| Module | Lines | Functions | Purpose |
|--------|------:|----------:|---------|
| community.py | 379 | 5 | LPA detection, NMI, sub-landscape extraction |
| test_community.py | ~600 | 65 tests | Full coverage of all 5 functions |

## Appendix B: Formula Chain

$$R_{\text{eff}}(s, t) = R_0(s, t) + \delta_H(s, t)$$
$$w(s, t) = \frac{1}{R_{\text{eff}}(s, t)}$$
$$\ell_i = \arg\min_{\ell^*} \left( -\sum_{j : \ell_j = \ell^*} w(i, j), \; \ell^* \right)$$
$$\text{NMI}(A, B) = \frac{2 \cdot \text{MI}(A, B)}{H(A) + H(B)}$$

## Appendix C: Relationship to Prior Papers

| Paper | Connection |
|-------|-----------|
| P1 (Interference) | R_eff is the quantity communities are built from |
| P4 (Reflexion) | Structural mutation → `refresh_communities()` updates partition |
| P5 (Emergence) | Scoped reflexion operates per-community (was per-prefix) |
| P6 (Coupling) | Coupling Router uses community boundaries for exchange |
| P7 (Dream) | Dream partitions by community; equivalences found within/across |

## Appendix D: GT-7 Perspective Check

> *"If I migrated the macro level to mechanism X — does the micro level
> still use mechanism Y? Two partitioning worlds = incomplete migration."*

This perspective check was added after the C255–C262 macro migration
discovered that the micro level (navigate crossings, teach bridges) still
used prefix-based partitioning. It has been triggered once (C262 post-arc
audit) and prevented the same class of error from recurring.
