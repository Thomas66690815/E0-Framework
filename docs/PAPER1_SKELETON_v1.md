# Paper 1 — Skeleton & Production Plan

## E₀: Structural Interference in Discrete Transition Systems

**Working title alternatives:**
- "Emergent Path-Family Interference from Structural Primitives in Discrete Transition Systems"
- "E₀: A Transition Framework Where Geometry Determines Control"
- "From Structural Difference to Path Interference: A Deterministic Framework for Transition Systems"

**Target venue:** JAIR (Journal of Artificial Intelligence Research)
- Rigorous, long-form, open access, no page limit
- Reviewers expect: formal definitions, theorems with proofs, reproducible experiments, honest limitations
- Alternative: AIJ (Artificial Intelligence), Foundations and Trends in ML

**Estimated length:** 25–35 pages (JAIR format)

**Authors:** Thomas Wehner (+ acknowledgment of HSCP methodology)

---

## Core Contribution Statement (1 paragraph)

We introduce E₀, a formal framework for discrete transition systems built on
three primitive quantities — structural difference (Δ), resistance (R), and
historization (H). From these primitives, without postulating probabilities or
energies, we derive a complete chain of structural quantities culminating in
complex path amplitudes Ψ = exp(−S + iΘ) that exhibit constructive and
destructive interference. We show that this interference can be used to
construct a hybrid controller that escapes structural traps undetectable by
local greedy methods. Our central empirical finding is that the choice of
summation geometry — which paths contribute to the amplitude — dominates
over the choice of decision rule (deterministic vs. probabilistic). We
validate this across 380 randomly generated graph topologies and identify
precise topological predictors for when interference-based routing provides
advantage over greedy control.

---

## Section Structure

### Abstract (200 words)
- Problem: local greedy methods fall into structural traps
- Approach: structural primitives → path amplitudes → interference → hybrid control
- Key results: trap escape, geometry dominance, topology classification
- Scope statement: what is derived, what is empirical

### 1. Introduction (3–4 pages)

**1.1 Problem statement**
- Greedy local optimization in discrete transition systems is trapped by myopic evaluation
- Examples: planning, workflow routing, state-machine control
- Existing solutions (look-ahead, RL, MCTS) add complexity without structural guarantees

**1.2 Our approach**
- Start from three primitives: Δ, R, H
- Derive (not postulate) path amplitudes with interference
- Use interference to detect and escape structural traps
- Key insight: the mathematical structure is analogous to path integrals, but derived from first principles without physics postulates

**1.3 Contributions**
1. A formal framework deriving complex path amplitudes from structural primitives (§3–4)
2. A hybrid controller that uses amplitude-based interference to override greedy traps (§5)
3. Four summation geometries with empirical comparison and the result that geometry dominates decision rule (§6)
4. A 380-graph topology scan identifying structural predictors for interference utility (§7)
5. An explicit derived/empirical/heuristic classification of all claims (Table 1)

**1.4 Scope and honesty**
- What is derived vs. empirical vs. heuristic (forward reference to Table 1)
- What this paper does NOT claim (no continuous limit, no physics, no probabilistic guarantees)

**Source material:** To be written fresh. Canon files for motivation.

---

### 2. Related Work (2–3 pages)

**2.1 Greedy and look-ahead methods in discrete systems**
- A* and variants, beam search
- Limitation: require explicit heuristics

**2.2 Reinforcement learning approaches**
- Q-learning, policy gradient
- Limitation: require reward signal, sample inefficiency

**2.3 Monte Carlo Tree Search**
- MCTS, AlphaZero-style
- Limitation: requires simulation model, convergence guarantees limited

**2.4 Path-integral and amplitude-based methods in AI**
- Quantum-inspired optimization (quantum annealing analogies)
- Path-integral control theory (Kappen, Todorov)
- Limitation: typically postulate the amplitude structure rather than deriving it

**2.5 Topological and geometric methods in decision-making**
- Persistent homology in data analysis
- Topological complexity in motion planning
- Connection to our geometry-determines-control result

**2.6 Positioning of E₀**
- E₀ derives amplitude structure from structural primitives
- No quantum postulates, no reward function, no simulation model
- Closest relatives: path-integral control theory, structural causal models

**Source material:** TO BE WRITTEN. This is the biggest gap. Requires literature review.

**Key references to find:**
- Kappen (2005) — path integral control
- Todorov (2007) — linearly solvable MDPs
- Ghrist (2008) — topological methods in robotics
- Recent work on quantum-inspired classical optimization
- Structural causal models (Pearl, Bareinboim)

---

### 3. The E₀ Framework: Primitives and Derived Quantities (5–6 pages)

This is the mathematical core. Each subsection has a Definition + derivation.

**3.1 States and transitions**
- Definition 1: Directed transition graph (X, E)
- Notation conventions

**3.2 Structural difference**
- Definition 2: Δ : E → ℝ₊
- Properties and interpretation

**3.3 Resistance and historization**
- Definition 3: Base resistance R₀ : E → ℝ₊
- Definition 4: Historization H(e) = (U(e), F(e))
- Definition 5: Correction δ_H = λ_f · F − λ_s · U
- Definition 6: Effective resistance R_eff = R₀ + δ_H

**3.4 Tension and coherence**
- Definition 7: Edge tension S(x→y) = Δ(x,y) · R_eff(x→y)
- Definition 8: Path tension S(p) = Σ S(eᵢ)
- Definition 9: Path coherence C(p) = exp(−S(p))
- Proposition 1: C ∈ (0, 1], monotonically decreasing in S

**3.5 Local potential and field decomposition**
- Definition 10: Local potential Φ(x) = Σ Δ · R_eff
- Definition 11: Gradient component v_grad = Φ(x) − Φ(y)
- Definition 12: Rotational component v_rot = v − v_grad

**3.6 Connection and phase**
- Definition 13: Connection ω(x,y) = ½(v_rot(x,y) − v_rot(y,x))
- Definition 14: Path phase Θ(p) = Σ ω(eᵢ)
- Definition 15: Holonomy Hol(γ) = Θ(γ) for closed γ
- **Theorem 1 (Holonomy Independence):** For two paths p₁, p₂ from x to y, the phase difference ΔΘ = Θ(p₁) − Θ(p₂) depends only on edges in p₁ and p₂, not on external graph structure. *(Proof: Φ cancels in the difference.)*

**3.7 Complex path amplitude**
- Definition 16: Ψ(p) = exp(−S(p)) · exp(iΘ(p))
- Definition 17: Endpoint amplitude Ψ(a) = Σ_{p∈Paths(a,h)} Ψ(p)
- Definition 18: Intensity I(a) = |Ψ(a)|²
- Definition 19: Normalized intensity P(a) = I(a) / Σ I
- Proposition 2: I exhibits interference — I(a) ≠ Σ|Ψ(p)|² in general
- Proposition 3: For zero holonomy, I reduces to squared sum of coherences

**Source material:** `E0_FORMAL_PAPER_DRAFT_v1.md` (§2–9), canon files, `E0_MATH_IMPL_MAPPING_v1.md`. Core mathematics is stable. Needs formal theorem/proof formatting.

**Figures:**
- Fig. 1: Derivation chain diagram (Δ → R₀ → H → ... → Ψ)
- Fig. 2: Example: Diamond graph showing constructive/destructive interference

---

### 4. Summation Geometries (3–4 pages)

**4.1 The geometry problem**
- Definition 20: Summation geometry G determines which paths contribute to Ψ(a)
- Motivation: different path sets → different interference patterns → different decisions

**4.2 Four geometries**
- Definition 21: Simple (all paths ≤ h)
- Definition 22: Prefix (all prefixes of all paths)
- Definition 23: First-arrival (first visit to each state)
- Definition 24: Goal-reaching (only paths terminating at a goal state)

**4.3 Structural justification for goal-reaching**
- Proposition 4: Under goal-oriented semantics, non-goal-terminating paths introduce intensity inflation that can invert action rankings
- Demonstration: Gordian Trap under simple (A wins) vs. goal_reaching (B wins)

**4.4 Empirical comparison**
- Table 3: Geometry comparison across domains (Diamond, Gordian, G5, Invoice)
- Result: simple is robust default; goal_reaching is required for trap domains
- Result: prefix overcounts, first_arrival needs further study

**Source material:** `E0_SUMMATION_GEOMETRY_COMPARISON_v1.md`, `test_amplitude_overlay.py` (125 tests), `test_gordian_trap.py`. Data exists, needs formatting.

**Figures:**
- Fig. 3: Gordian Trap topology diagram
- Fig. 4: Intensity comparison under 4 geometries on Gordian Trap
- Table 3: Geometry × Domain results matrix

---

### 5. Hybrid Controller (3–4 pages)

**5.1 Greedy controller**
- Algorithm 1: Local burden minimization (argmin S_eff)
- Escalation types (DEAD_END, FILTERED, EXHAUSTED)
- Limitation: falls into greedy traps

**5.2 Amplitude overlay**
- Algorithm 2: Bounded path enumeration → Ψ → I → P
- Computational complexity: O(k^h) where k = max branching, h = horizon

**5.3 Hybrid arbitration**
- Algorithm 3: AMPLITUDE_ON_DISAGREE
  - If greedy = amplitude → follow greedy
  - If greedy ≠ amplitude → follow amplitude
  - Safety conditions (escalation, invalid overlay)
  - Confidence gating (override_confidence threshold)

**5.4 Correctness properties**
- Proposition 5: On acyclic graphs, hybrid never performs worse than greedy
- Proposition 6: On Gordian-class traps with goal_reaching geometry, hybrid always escapes
- Proposition 7: Hybrid preserves determinism (same input → same output)

**5.5 Metrics**
- override_count, override_rate, agreement_rate, avg_horizon, avg_override_confidence
- Table 4: Metrics across domains

**Source material:** `E0_HYBRID_CONTROLLER_SPEC_v1.md`, `controller.py`, test suites. Well-documented, needs academic formatting.

**Figures:**
- Fig. 5: Hybrid decision pipeline diagram
- Table 4: Hybrid metrics across 4 benchmark domains

---

### 6. Central Result: Geometry Dominates Decision Rule (2–3 pages)

This is the headline result of the paper.

**6.1 Experimental setup**
- Compare argmax(I) vs sample(P∝I) across geometries and domains
- 50–100 trials per configuration, fixed random seeds

**6.2 Results**
- **Theorem 2 (informal):** On Gordian-class traps, the choice of summation geometry (simple vs goal_reaching) determines success or failure. The choice of decision rule (argmax vs sampling) is secondary.
  - With goal_reaching: argmax = 100%, born ≈ 96% → both succeed
  - With simple: argmax = 0%, born ≈ 24% → both fail (born escapes randomly)
- Table 5: Success rates by geometry × decision rule × domain

**6.3 Interpretation**
- Geometry determines which structural information reaches the decision rule
- A bad geometry feeds wrong information to any decision rule
- A good geometry makes even sampling nearly as good as argmax
- This is analogous to: feature selection > model choice in ML

**6.4 Implications**
- Practical: invest in geometry selection before decision rule tuning
- Theoretical: summation geometry is the critical degree of freedom, not the selection rule

**Source material:** Path H tests (`test_born_sampling.py`, 27 tests), ADR-0007-v1. Data exists, needs presentation.

**Figures:**
- Fig. 6: Bar chart — success rate by geometry × decision rule
- Table 5: Full results matrix

---

### 7. Topology Classification: When Does Interference Help? (3–4 pages)

**7.1 Question**
- Not all graph topologies benefit from interference-based routing
- Can we predict when amplitude overlay will override greedy?

**7.2 Methodology**
- Generate 380 graphs: 180 structured + 200 random
- For each: compute greedy path, amplitude path, check override
- Classify by topological features

**7.3 Results**
- **Proposition 8:** Override requires ≥ 2 path families to the same endpoint
- **Empirical finding:** Phase opposition |ΔΘ| > π/2 is the strongest predictor
- Table 6: Override rates by topology class
  - Triangle: 0%
  - Diamond: 37%
  - Gordian: 93%
  - Random: varies (correlated with path-family count and phase spread)
- Goal-reaching geometry (G5) produces 30.3% exclusive overrides (not seen in other geometries)

**7.4 Predictive model**
- When to use interference-based routing:
  1. Multiple path families exist
  2. Phase opposition is present
  3. Goal-reaching geometry is active
- When NOT to use it:
  - Linear chains, trees, single-family topologies

**Source material:** `test_topology_classification.py` (23 tests, 380 graphs). Quantitative data exists.

**Figures:**
- Fig. 7: Override rate vs topology class (bar chart)
- Fig. 8: Phase opposition as predictor (scatter plot or decision boundary)
- Table 6: Topology classification results

---

### 8. Implementation and Reproducibility (1–2 pages)

**8.1 Implementation overview**
- Python 3.11, ~3000 LOC in `e0_controller/`
- 936 unit tests across 27 test files
- Open-source repository (link)

**8.2 Test registry**
- 22 verified claims (C1–C22)
- Derived / Empirical / Heuristic classification for every component

**8.3 Reproducibility**
- All experiments use fixed random seeds
- All benchmark domains are defined in test code (no external data)
- Run instructions: `python -m unittest discover -s e0_controller -p "test_*.py"`

**Source material:** `E0_TEST_REGISTRY_v1.md`, `E0_TEST_REGISTRY_v2.md`. Straightforward.

---

### 9. Limitations and Falsification Targets (2 pages)

**9.1 What is NOT derived**
- Phase Θ — constructed from v_rot decomposition, not fully derived from first principles
- Summation geometry — empirically selected, no minimality proof
- Revisit penalty, escalation logic — heuristic operational choices

**9.2 Computational limitations**
- Path enumeration is O(k^h) — not scalable to large branching factors
- Current implementation limited to h ≤ 10 on graphs with k ≤ 5

**9.3 Domain limitations**
- Validated on synthetic benchmark domains only
- No real-world deployment evidence
- LLM integration exists but is not core to the theoretical contribution

**9.4 Active falsification targets**
- Find a graph where hybrid consistently underperforms greedy
- Produce a domain where phase Θ does not influence interference outcomes
- Demonstrate that summation geometry choice is irrelevant on some topology class

**Source material:** `E0_EVIDENCE_AND_FALSIFICATION_STATUS_v1.md`, `E0_DERIVED_EMPIRICAL_HEURISTIC_MAP_v1.md`.

---

### 10. Discussion (2–3 pages)

**10.1 Relation to path-integral control**
- Similarities: complex amplitudes, path summation, interference
- Differences: E₀ derives amplitude from structural primitives, not physics postulates

**10.2 Structural vs. statistical learning**
- E₀ learns through historization (resistance updates), not gradient descent
- No objective function, no loss landscape — transitions alter future structure

**10.3 The geometry insight**
- Analogous to: kernel choice > model choice in kernel methods
- Geometry is the "right question" — the decision rule merely executes

**10.4 Implications for AI systems**
- Structural decision layers as alternative to reward-maximizing agents
- Hybrid architecture: domain-agnostic structural core + domain-specific semantic interface

**Source material:** Partially in existing docs, but needs fresh academic writing.

---

### 11. Conclusion (1 page)

- Summarize contributions 1–5
- Emphasize: interference is derived, not postulated
- Emphasize: geometry > decision rule
- Forward reference to Paper 2 (spinor extension, Born sampling)

---

### Appendices

**A. Proof of Theorem 1 (Holonomy Independence)**
- Full proof with Φ cancellation argument

**B. Benchmark Domain Specifications**
- Formal definition of Diamond, Gordian Trap, G5, Invoice domains
- State/edge/delta/resistance values

**C. Derived / Empirical / Heuristic Classification (Table 1)**
- Full version of the honesty map as a paper table

**D. Test Registry Summary**
- Claims C1–C22 with evidence pointers

---

## Figures and Tables Plan

| ID | Type | Content | Section | Status |
|----|------|---------|---------|--------|
| Fig. 1 | Diagram | Derivation chain Δ → ... → Ψ | §3 | To create |
| Fig. 2 | Example | Diamond graph interference | §3 | To create |
| Fig. 3 | Topology | Gordian Trap diagram | §4 | To create |
| Fig. 4 | Bar chart | Intensity under 4 geometries | §4 | Data exists |
| Fig. 5 | Flowchart | Hybrid decision pipeline | §5 | To create |
| Fig. 6 | Bar chart | Geometry × decision rule success | §6 | Data exists |
| Fig. 7 | Bar chart | Override rate by topology | §7 | Data exists |
| Fig. 8 | Scatter | Phase opposition predictor | §7 | Data exists |
| Tab. 1 | Table | Derived/Empirical/Heuristic map | §1, App. C | Exists |
| Tab. 2 | Table | Notation summary | §3 | To create |
| Tab. 3 | Table | Geometry × domain results | §4 | Data exists |
| Tab. 4 | Table | Hybrid metrics by domain | §5 | Data exists |
| Tab. 5 | Table | Geometry × rule × success | §6 | Data exists |
| Tab. 6 | Table | Topology classification | §7 | Data exists |

---

## Writing Status per Section

| Section | Content status | Effort |
|---------|---------------|--------|
| Abstract | Not written | Small (last) |
| §1 Introduction | Fragments in outline | Medium |
| §2 Related Work | **NOTHING EXISTS** | **Large** — literature review needed |
| §3 Theory | `E0_FORMAL_PAPER_DRAFT_v1.md` covers 90% | Medium (reformat) |
| §4 Geometries | Data + docs exist, needs formatting | Medium |
| §5 Hybrid Controller | Spec + tests exist | Medium |
| §6 Geometry > Rule | Data exists (Path H) | Small–Medium |
| §7 Topology Scan | Data exists (23 tests, 380 graphs) | Medium |
| §8 Implementation | Registries exist | Small |
| §9 Limitations | Evidence + falsification docs exist | Small |
| §10 Discussion | Needs fresh thinking | Medium |
| §11 Conclusion | Standard | Small |
| Appendices | Material exists | Small–Medium |

**Biggest gap: §2 Related Work — requires actual literature research.**

---

## Quality Checklist (before submission)

- [ ] Every definition is numbered and referenced
- [ ] Every theorem/proposition has a proof or proof sketch
- [ ] Every empirical claim references specific tests with reproducibility instructions
- [ ] Table 1 (honesty map) is complete and consistent with text
- [ ] Related work covers at least 25 references from relevant fields
- [ ] All figures have captions with explicit takeaway message
- [ ] Falsification targets are specific and testable
- [ ] No claim exceeds its evidence category (derived/empirical/heuristic)
- [ ] Code repository is tagged and linked
- [ ] Abstract is ≤ 200 words and contains the geometry > rule result
- [ ] All notation is consistent throughout (cross-check Notation Table)

---

## Production Sequence

1. **Phase A — Theory sections** (§3): Reformat formal paper draft into Definition/Theorem style
2. **Phase B — Experiments** (§4, §6, §7): Extract data from tests, create figures/tables
3. **Phase C — Controller** (§5): Formalize algorithms, state propositions
4. **Phase D — Introduction & Discussion** (§1, §10, §11): Frame the contribution
5. **Phase E — Related Work** (§2): Literature review (needs external research)
6. **Phase F — Polish** (Abstract, §8, §9, Appendices, cross-references)
7. **Phase G — Internal review**: Full read-through, honesty check, notation audit

---

_End of skeleton._
