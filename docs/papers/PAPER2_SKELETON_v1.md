# Paper 2 — Skeleton & Production Plan

## E₀-II: Spinor Amplitudes and the Born Criterion on Discrete Transition Graphs

**Working title alternatives:**
- "From U(1) to SU(2): Spinor Lift and Emergent Probability in Structural Decision Systems"
- "The Born Criterion as Structural Consequence: SU(2) Amplitudes on Directed Graphs"
- "E₀-II: Non-Commutative Phase Geometry and Emergent Probability"

**Target venue:** JAIR (Journal of Artificial Intelligence Research)
- Same venue as Paper 1 for coherence
- Alternative: Physical Review E (complex systems), Foundations of Physics

**Estimated length:** 20–30 pages

**Authors:** Thomas Wehner

**Prerequisite:** Paper 1 (E₀ framework, U(1) amplitudes, geometry dominance)

---

## Core Contribution Statement (1 paragraph)

Paper 1 established that the E₀ framework derives complex path amplitudes
Ψ = exp(−S + iΘ) ∈ ℂ exhibiting interference on directed graphs. This paper
asks: why ℂ? We show that the requirement of encoding *internal difference*
— rotational structure that distinguishes structurally distinct transitions
even when they share scalar magnitude — forces the minimal carrier space to
be ℂ², yielding SU(2)-valued path transport instead of U(1) phases. The
spinor lift Ψ : path → ℂ² introduces three qualitatively new effects:
(1) 720° periodicity — the transport operator returns to identity only after
two full rotations, (2) phase halving — interference patterns change because
SU(2) transport halves effective phase differences, and (3) non-commutativity
— multi-axis transport operators do not commute, making path ordering
physically significant. We then derive the Born criterion: under bounded
exclusive realization (exactly one endpoint realizes), the probability
P(z) = |Ψ(z)|²/Σ|Ψ(w)|² is the unique structurally non-arbitrary
distribution over outcomes under the BER axioms. This probability is not assumed — it emerges
as the minimal gauge-invariant intensity measure. We validate these results
across the benchmark domains from Paper 1 and identify conditions under
which SU(2) produces qualitatively different decisions than U(1).

---

## Section Structure

### Abstract (≤ 200 words)
- Paper 1 recap: U(1) amplitude, interference, geometry dominance
- This paper: why ℂ²? Internal difference → minimal carrier → SU(2)
- Three new effects: 720° periodicity, phase halving, non-commutativity
- Born criterion: emergent probability from structural amplitude
- Validation: when does SU(2) diverge from U(1)?
- Scope: what is derived, what is empirical, what is open

### 1. Introduction (3–4 pages)

**1.1 Motivation: Beyond scalar phase**
- Paper 1 showed amplitude interference requires non-zero holonomy
- But the scalar phase Θ is derived up to a gauge class (Paper 1, §3.6)
- Natural question: is there a *richer* phase structure that resolves
  gauge ambiguity and adds structural content?
- The answer comes from a carrier-space argument

**1.2 The internal-difference argument**
- Key insight: distinguishing transitions that share scalar magnitude
  but differ rotationally requires a multi-component carrier
- ℂ is insufficient (1-dimensional, only rotation = phase)
- ℂ² is the minimal space supporting internal orientation
- This forces SU(2) transport, not U(1)

**1.3 Contributions**
1. Carrier minimality theorem: internal difference requires ℂ², forcing SU(2) (§3)
2. SU(2) path transport with three emergent effects (§4)
3. Born criterion derivation under bounded exclusive realization (§5)
4. Empirical comparison: when SU(2) ≠ U(1) in decision outcomes (§6)
5. Multi-goal analysis under spinor amplitudes (§7)

**1.4 Scope and honesty**
- What is derived vs. empirical vs. open
- What this paper does NOT claim (not a quantum theory, no continuous limit)
- Forward reference to honesty classification table

**Source material:**
- E0_INTERNAL_DIFFERENCE_TO_SPINOR_BRIDGE_v0.md (carrier minimality)
- E0_SPINOR_EXPLORATION_v0.md (720°, phase halving)
- Paper 1 §3.6 gauge freedom remark

---

### 2. Related Work (2–3 pages)

**2.1 Spinor structures in classical systems**
- Geometric algebra on graphs (Grady & Polimeni)
- Clifford algebras in signal processing
- Distinction: E₀ derives spinor need from carrier minimality, not from
  embedding in physical space

**2.2 The Born rule: derivations and alternatives**
- Gleason's theorem (Hilbert space → Born, but requires Hilbert axioms)
- Zurek's envariance (decoherence-based Born derivation)
- Deutsch-Wallace decision-theoretic Born derivation
- Distinction: E₀ derives Born from structural amplitude + bounded exclusivity,
  not from Hilbert space axioms

**2.3 Gauge theory on discrete structures**
- Lattice gauge theory (Wilson, Kogut-Susskind)
- Gauge equivariant neural networks (Cohen-Welling, Favoni et al.)
- Distinction: E₀ uses SU(2) as decision operator, not representation

**2.4 Non-commutative geometry in AI**
- Sheaf neural networks (Bodnar et al.)
- Connection Laplacian methods (Singer-Wu)
- Distinction: E₀'s non-commutativity affects action selection, not learning

**2.5 Positioning of Paper 2**
- Table: tradition vs E₀ analog vs key difference
- Central claim: first derivation of Born-like probability from structural
  graph primitives without quantum axioms

**Source material:** Paper 1 §2 references + new literature on Born derivations

---

### 3. Carrier Minimality: Why ℂ² (3–4 pages)

**Mathematical core section.** This is the key theoretical contribution.

**3.1 The encoding problem**
- Setup: given the connection ω(x,y) from Paper 1, what is the minimal
  algebraic structure for path transport?
- U(1): phase rotation exp(iθ), 1-dimensional, commutative
- Problem: U(1) cannot distinguish rotations in different planes

**3.2 Internal difference**
- Definition: internal difference between two edges that share Δ, R
  but differ in rotational orientation
- Formalization: requires transport operators U₁, U₂ with
  U₁ · U₂ ≠ U₂ · U₁ (non-commutativity)
- This is impossible in U(1) (commutative group)

**3.3 Carrier minimality theorem**
- Statement: the minimal group supporting non-commutative transport is SU(2)
  (up to isomorphism among compact connected Lie groups of rank 1)
- Proof sketch: U(1) is abelian → excluded. SU(2) is the unique simply
  connected compact rank-1 Lie group. SO(3) ≅ SU(2)/ℤ₂ has the wrong
  topology (non-simply-connected → sign ambiguity on paths)
- Corollary: minimal carrier space is ℂ² (fundamental representation of SU(2))

**3.4 From scalar to spinor: the lift**
- Paper 1 connection: ω(x,y) ∈ ℝ (scalar)
- Paper 2 connection: A⃗(x,y) ∈ ℝ³ (vector-valued)
- Transport: U(x→y) = exp(-i/2 · ‖A⃗‖ · n̂·σ⃗) ∈ SU(2)
- Minimal embedding: A⃗ = (0, 0, ω) recovers U(1) as subgroup

**Source material:**
- E0_INTERNAL_DIFFERENCE_TO_SPINOR_BRIDGE_v0.md (full argument)
- E0_COMPLEX_CARRIER_MINIMALITY_v1.md
- spinor_connection.py (implementation)

---

### 4. SU(2) Path Transport (3–4 pages)

**4.1 Spinor path amplitude**
- Definition: Ψ_SU(2)(p) = U(e_n) · ... · U(e_1) · |ref⟩ ∈ ℂ²
  where |ref⟩ = (1, 0)ᵀ is a reference spinor
- Modulus: ‖Ψ_SU(2)(p)‖ = exp(-S(p)) = C(p) [same as U(1)]
- Phase: now a direction on S², not a point on S¹

**4.2 Effect 1: 720° periodicity**
- exp(-i·2π·n̂·σ⃗/2) = -𝕀 (360° → sign flip)
- exp(-i·4π·n̂·σ⃗/2) = +𝕀 (720° → identity)
- This is the defining property of spinors vs. vectors
- Consequence: path phases that accumulate 2π do NOT return to start

**4.3 Effect 2: Phase halving**
- SU(2) transport halves the effective phase angle: θ → θ/2
- Impact on interference: cos(ΔΘ) → cos(ΔΘ/2)
- Destructive interference (ΔΘ ≈ π) becomes partial (cos(π/2) = 0)
  instead of full (cos(π) = -1)
- Gordian domain: I(A1) goes from 0.018 (U(1)) to 0.838 (SU(2) minimal)

**4.4 Effect 3: Non-commutativity**
- Multi-axis transport: [U₁, U₂] ≠ 0
- Path ordering becomes significant: p₁ ∘ p₂ ≠ p₂ ∘ p₁ in amplitude
- This is absent in U(1) where all phases commute
- Geometric connection A⃗ = (A₁, A₂, A₃) from Helmholtz vorticity

**4.5 Consistency**
- Single-path equivalence: ‖Ψ_SU(2)‖ = |Ψ_U(1)| (proven across all domains)
- Minimal embedding recovers U(1) identically
- Non-trivial divergence only under multi-path interference

**Source material:**
- E0_SPINOR_EXPLORATION_v0.md (Q1–Q4 verdicts)
- spinor_connection.py (Phase 4a, 4b)
- test_spinor.py (52 tests)

---

### 5. The Born Criterion (3–4 pages)

**Central derivation section.**

**5.1 The measurement problem on graphs**
- Setup: amplitude Ψ(z) assigns complex (or ℂ²) values to endpoints
- Question: what is the probability of "realizing" endpoint z?
- This is NOT the quantum measurement problem — there is no wave function
  collapse. It is the question: given structural amplitudes, what
  distribution over outcomes is structurally non-arbitrary?

**5.2 Bounded exclusive realization**
- Axiom 1: Bounded alternative set — finite set Ω of possible endpoints
- Axiom 2: Exclusive realization — exactly one z ∈ Ω realizes
- Axiom 3: Amplitude carrier — the support of P equals the support of Ψ
  (no probability without amplitude, no amplitude without probability)
- Axiom 4: No extra-structure rule — probability depends only on Ψ, Ω,
  no additional external function

**5.3 Derivation**
- From Axioms 1–4: P must be a function of |Ψ(z)|² only
  (gauge invariance eliminates phase dependence)
- Normalization: Σ P(z) = 1 with support = carrier
- Unique solution: P(z) = |Ψ(z)|²/Σ_w |Ψ(w)|²
- This is the Born rule, derived from structure, not postulated

**5.4 Relationship to Born sampling mode**
- Paper 1 introduced BORN_SAMPLING as opt-in mode
- This section provides its structural justification
- Under the axioms: Born sampling is not a design choice but the
  unique non-arbitrary sampling strategy
- Outside the axioms (e.g., non-exclusive realization): Born is one
  option among several

**5.5 Status: conditional derivation**
- The derivation is valid IF Axioms 1–4 hold
- Axiom 2 (exclusive realization) is the strongest assumption
- Open: when does exclusive realization hold in E₀ operationally?
- Honest classification: Born criterion is DERIVED (conditional),
  not empirical and not heuristic

**Source material:**
- E0_BORN_CRITERION_ANALYSIS_v1.md (full derivation)
- E0_CONTROLLER_VS_BORN_REALIZATION_REGIMES_v1.md (regime analysis)
- test_born_sampling.py (27 tests)

---

### 6. When Does SU(2) ≠ U(1)? (3–4 pages)

**Empirical comparison section.**

**6.1 Experimental design**
- Same benchmark domains as Paper 1: Diamond, Gordian, G5, Triangle
- Compare: U(1) intensity vs SU(2) intensity (minimal and geometric)
- Metric: divergence = |I_SU(2) - I_U(1)| / max(I_SU(2), I_U(1))

**6.2 Single-path equivalence (universal)**
- ‖Ψ_SU(2)(p)‖ = |Ψ_U(1)(p)| for all paths (proven, 52 tests)
- No divergence possible without interference

**6.3 Multi-path interference divergence**
- Phase halving changes interference pattern
- Gordian A-family: cos(π) = -1 → cos(π/2) = 0 → less destructive
- Result: I(A1) changes from 0.018 to 0.838 (4600% increase)
- BUT: A1 still loses to B1 under SU(2) minimal (B1 coherent)

**6.4 Geometric coupling divergence**
- Multi-axis A⃗ from Helmholtz vorticity
- Gordian loop path: 55.3% intensity divergence from minimal
- Triangle: 16.7% divergence
- Leaf edges: <0.01% (no interference → no divergence)

**6.5 Decision flip analysis**
- Key question: does SU(2) ever change the action selection?
- Current finding: NOT YET on tested domains
- Both minimal and geometric SU(2) select same winner as U(1)
  (though with different intensities)
- This is an open frontier, not a negative result

**Source material:**
- explore_spinor.py (6 domains, Q1–Q4)
- test_spinor.py (divergence tests)
- E0_SPINOR_EXPLORATION_v0.md

---

### 7. Multi-Goal Analysis Under Spinor Amplitudes (2–3 pages)

**7.1 G5 multi-goal with SU(2)**
- Three competing goals with different path structures
- Born sampling under SU(2): does coverage change?
- Phase halving effect on multi-goal interference

**7.2 Goal rescue under spinor lift**
- Rescue scenario: delta compression from 1.0 to 0.01
- Does SU(2) rescue differently than U(1)?

**7.3 Topology dependence**
- 380-graph scan: does SU(2) change override predictions?
- Phase opposition threshold under halving

**Source material:**
- E0_G5_EDGE_CASE_SUITE_v1.md (5-family stress test)
- test_born_sampling.py (H3–H5)

---

### 8. Implementation (1–2 pages)

**8.1 Code-definition mapping**
- spinor_connection.py functions ↔ definitions
- Phase 4a (minimal) vs Phase 4b (geometric)

**8.2 Test registry**
- 52 SU(2) tests + 27 Born tests
- Organization by claim

**8.3 Reproducibility**
- Same framework as Paper 1
- All experiments with fixed seeds

---

### 9. Limitations and Open Questions (2 pages)

**9.1 Formal status**
- Derived: carrier minimality, Born criterion (conditional), 720° periodicity
- Empirical: phase halving effects, divergence magnitudes
- Open: decision flip conditions, geometric coupling optimality,
  continuous endpoint density

**9.2 The decision flip frontier**
- SU(2) changes intensities but not (yet) winners
- What topology would produce a flip?
- Specific prediction: graphs with near-threshold phase opposition
  (ΔΘ near π/2) should be most sensitive to halving

**9.3 Universality of exclusive realization**
- Born criterion holds under Axiom 2
- When does Axiom 2 hold in practice?
- E₀'s action selection is not exclusive realization — it's argmax or sampling
- The gap between the axiom and the operational mode

**9.4 Scalability**
- Same O(k^h) as Paper 1
- SU(2) adds matrix multiplication overhead (2×2 complex)
- Constant factor, not complexity class change

---

### 10. Discussion (2 pages)

**10.1 From U(1) to SU(2): structural necessity vs. empirical utility**
- The carrier minimality argument is structural (derived)
- The practical impact is still limited (empirical: no winner flip yet)
- The gap is the frontier for future work

**10.2 Born rule without quantum mechanics**
- Comparison to Gleason, Zurek, Deutsch-Wallace
- E₀'s derivation: weaker axioms (no Hilbert space), stronger scope limitation
  (only bounded exclusive realization)
- What this means for foundations of probability

**10.3 Non-commutativity as structural signal**
- [U₁, U₂] ≠ 0 captures path-order-dependent information
- This is information that scalar phase cannot represent
- Potential applications: workflow routing where order matters,
  planning with irreversible transitions

**10.4 Toward a complete structural decision theory**
- Paper 1: interference as decision mechanism
- Paper 2: spinor structure and emergent probability
- Open horizon: measurement theory, observer structure, continuous limits

---

### 11. Conclusion (1 page)

Summarize:
1. Carrier minimality: internal difference → ℂ² → SU(2)
2. Three SU(2) effects: 720°, phase halving, non-commutativity
3. Born criterion: structural derivation under bounded exclusivity
4. Empirical: SU(2) changes intensities, not yet decisions
5. Open frontier: decision flip conditions, universality of Born axioms

---

## Appendices

### Appendix A. Pauli Algebra Reference
- σ₁, σ₂, σ₃ definitions
- Anticommutation relations {σᵢ, σⱼ} = 2δᵢⱼ𝕀
- Exponential map: exp(-iθ/2 · n̂·σ⃗) ∈ SU(2)
- 720° periodicity proof

### Appendix B. Born Criterion Derivation (Full)
- Detailed proof from Axioms 1–4 → P = |Ψ|²/Σ|Ψ|²
- Uniqueness argument

### Appendix C. Geometric Connection A⃗ Construction
- Helmholtz vorticity decomposition
- Three-component extraction: A₁ (gradient), A₂ (face curvature), A₃ (ω)
- Antisymmetry and unitarity proofs

### Appendix D. Divergence Data Tables
- Full U(1) vs SU(2) comparison across all domains
- Single-path and multi-path results

### Appendix E. Derived / Empirical / Open Classification
- Honesty map for Paper 2 claims
- Cross-reference to Paper 1 classifications

---

## Figures Plan

**Fig. 1:** Carrier space hierarchy: ℝ → ℂ → ℂ² (and why each step is forced)
**Fig. 2:** U(1) vs SU(2) transport on the Gordian domain (Bloch sphere visualization)
**Fig. 3:** Phase halving effect on interference: cos(ΔΘ) vs cos(ΔΘ/2)
**Fig. 4:** Geometric connection A⃗ on Gordian (3-component vector field)
**Fig. 5:** Born criterion: P(z) = |Ψ|²/Σ|Ψ|² under varying interference
**Fig. 6:** Divergence heatmap: U(1) vs SU(2) across 380 topologies

---

## Dependencies on Paper 1

| Paper 2 section | Paper 1 reference | Status |
|----------------|-------------------|--------|
| §1 motivation | §3.6 gauge freedom | ✅ Fixed in v2 |
| §3 carrier argument | §3 full derivation chain | ✅ Complete |
| §4 SU(2) transport | §3.7 complex amplitude | ✅ Complete |
| §5 Born criterion | §5.4 Born sampling mode | ✅ Complete |
| §6 comparison | §6 geometry dominance, §7 topology | ✅ Complete |
| §7 multi-goal | §4 summation geometries | ✅ Complete |

---

## Production Sequence

| Phase | Action | Dependencies |
|-------|--------|-------------|
| A | Write §3 (carrier minimality) — this is the theoretical core | None |
| B | Write §4 (SU(2) effects) — extract from spinor exploration | §3 |
| C | Write §5 (Born criterion) — formalize from analysis doc | §4 |
| D | Write §6 (U(1) vs SU(2)) — extract from test data | §4 |
| E | Write §1–2 (intro, related work) — frame the contribution | §3–6 |
| F | Write §7–8 (multi-goal, implementation) | §4–6 |
| G | Write §9–11 (limitations, discussion, conclusion) | All |
| H | Internal review: notation, cross-references, honesty check | All |
| I | Abstract — write last | All |

---

## Quality Checklist

- [ ] Every definition is numbered and referenced
- [ ] Every theorem/proposition has proof or proof sketch
- [ ] Every empirical claim references specific tests
- [ ] Honesty table complete and consistent with text
- [ ] Related work covers Born-derivation literature (≥ 10 references)
- [ ] All figures have captions with explicit takeaway
- [ ] No claim exceeds its evidence category
- [ ] Paper 1 references are explicit (section numbers, not vague)
- [ ] Code repository tagged and linked
- [ ] Abstract ≤ 200 words
- [ ] All notation consistent with Paper 1 where shared
- [ ] SU(2) vs U(1) distinction is clear throughout

---

## Key Definitions to Number (preliminary)

| # | Name | Section |
|---|------|---------|
| 1 | Internal difference | §3.2 |
| 2 | Carrier space | §3.2 |
| 3 | Carrier minimality | §3.3 |
| 4 | SU(2) edge transport | §4.1 |
| 5 | Spinor path amplitude | §4.1 |
| 6 | Reference spinor | §4.1 |
| 7 | Spinor intensity | §4.1 |
| 8 | Geometric connection vector A⃗ | §4.4 |
| 9 | Bounded alternative set | §5.2 |
| 10 | Exclusive realization | §5.2 |
| 11 | Amplitude carrier axiom | §5.2 |
| 12 | No extra-structure rule | §5.2 |
| 13 | Born probability | §5.3 |
| 14 | Spinor divergence metric | §6.1 |

---

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| SU(2) never flips a decision | High | Acknowledge as open frontier; value is structural derivation, not empirical dominance |
| Born criterion axioms too restrictive | Medium | Explicit scope; compare to Gleason's stronger axioms |
| Paper rejected as "physics not AI" | Medium | Position as structural decision theory, cite AI venues |
| Reviewer says "just implement quantum walks" | Medium | §2 distinction paragraph; E₀ derives, not postulates |
| Computational overhead of SU(2) | Low | Constant factor only; same O(k^h) |
