# E₀ Paper Audit — Scientific Self-Review

**Date:** 2026-04-17
**Scope:** All 6 published papers (P1–P6) vs. current codebase (C268, 5755 tests)
**Method:** Systematic 3-phase audit: Coverage → Formula verification → Falsification
**Principle:** Falsification over confirmation. We document what's wrong, not what's right.

---

## 1. Executive Summary

The 6 papers cover commits C1–C108 of a codebase now at C268. **160 commits
have no paper coverage.** The papers' core structural claims (interference,
SU(2) lift, reflexion, emergence proofs) hold. All 398 benchmark tests pass.
However, we found:

- **4 formula mismatches** between papers and current code (2 high severity)
- **1 proof gap** (conclusion correct, reasoning incomplete)
- **27 substantial production modules** (~9,345 lines) with no paper coverage
- **Internal inconsistencies** within Paper 5 (stale §4.1 contradicts §10.4)
- **No external benchmarks** — zero comparison with SOTA methods
- **No scaling studies** beyond N ≈ 50 states

**Bottom line:** The papers are not *wrong*, but they are *incomplete* and
*stale*. The codebase has evolved significantly beyond what the papers describe,
and three formula/parameter discrepancies mean a reader cannot reproduce the
actual system behavior from the papers alone.

---

## 2. Paper-by-Paper Status

| Paper | Title | Commits | Status | Action |
|-------|-------|---------|--------|--------|
| P1 | Structural Interference | C1–C22 | ⚠️ **Stale** | Update select_next formula, add revisit penalty formalization |
| P2 | Spinor Amplitudes / Born | — | ✅ Stable | No changes needed |
| P3 | Non-Abelian Structure | C42 | ✅ Stable | No changes needed |
| P4 | Reflexive Self-Modification | C47–C59 | ✅ Stable | Minor: note override gates added post-paper |
| P5 | Emergent Locality | C40–C108 | ⚠️ **Inconsistent** | Fix μ default, restructure §10.4 |
| P6 | Coupled Transition Systems | C53–C71 | ⚠️ **Proof gap** | Fix coupling theorem, fix NoveltyGate θ |

---

## 3. Formula Mismatches

### 3.1 [HIGH] P1: select_next — Paper vs. Code

**Paper 1, Algorithm 1:**
$$p^* = \arg\min_y S_{\text{eff}}(x \to y)$$

**Current code** (`controller.py`, `_penalized_tension`):
$$p^* = \arg\min_y \frac{S_{\text{eff}}(x \to y)}{M_H(x,y) \cdot I(x,y)}
\cdot (1 + \alpha \cdot \mathbb{1}[y \in \text{recent}(k)])$$

**Discrepancy:** The paper presents pure `argmin S_eff`. The code uses a
penalized formula with three additions:
1. Revisit penalty `(1 + α·𝟙_recent)` — mentioned in P1 §7.5 but never
   formalized in Algorithm 1
2. Overlap modulation `S_eff / M_H` — from C98, documented in P5 §3.1
3. Inertia modulation `S_eff / I` — from C99, documented in P5 §3.1

**Impact:** A reader implementing P1's Algorithm 1 will get different behavior
than the actual system. The revisit penalty is essential for loop escape.

**Fix:** Update P1 Algorithm 1 to include the revisit penalty. Add a note
that M_H and I are optional extensions (see P5 §3). Mark the revisit penalty
as heuristic with explicit formula.

### 3.2 [HIGH] P5 §4.1: μ default — Internal inconsistency

**Paper 5, §4.1:**
> "μ > 0 is a sensitivity threshold (default μ = 5.0)"

**Paper 5, §10.4 (retroactive annotation):**
> "Resolved (C105): μ = |E|/|V| (mean out-degree)"

**Code** (`scoped_reflexion.py`):
```python
if mu is None:
    mu = landscape_mu(landscape)   # = |E| / |V|
```

**Code** (`emergent_locality.py`):
```python
DEFAULTS.mu = 5.0   # different default!
```

**Discrepancy:** Three-way conflict:
1. §4.1 says μ = 5.0
2. §10.4 says μ = |E|/|V|
3. Two code paths use different defaults

**Impact:** The proofs in §5 (phase transition timing, convergence equilibrium)
use μ as a parameter — they hold for any μ > 0. But the specific numerical
examples (§5.2, §5.3) use μ = 5.0, producing predictions that won't match
behavior of a system using μ = |E|/|V|.

**Fix:** Update §4.1 to state the derived default μ = |E|/|V| (C105). Keep
μ = 5.0 in numerical examples with explicit note. Align emergent_locality.py
to use landscape_mu() or document why it differs. Move §10.4 resolutions to
a dated addendum section.

### 3.3 [MEDIUM] P6 §4.3: NoveltyGate θ default

**Paper 6, §4.3:**
> "θ is the delta threshold (default 0.5)"

**Code** (`multiverse.py`):
```python
class NoveltyGate:
    def __init__(self, delta_threshold: float = 0.0):
```

**Discrepancy:** θ = 0.5 vs θ = 0.0. With θ = 0.0, any positive Δ-growth
counts as novelty. With θ = 0.5, substantial growth is required.

**Fix:** Update Paper 6 to state θ = 0.0 as default with note that θ = 0.5
was the original design parameter, changed to 0.0 after empirical testing
showed better convergence.

### 3.4 [MEDIUM] P6 §3.2: Coupling theorem — δ_max clipping omitted

**Paper 6, §3.2 proof argues:**
> "δ_H(e) = −λ_s·U(e), each traversal makes δ_H more negative... the gap
> S*−S_γ increases with each cycle traversal."

**Code** (`historization.py`):
```python
raw = self.lambda_f * f - self.lambda_s * u
return max(-self.delta_max, min(raw, self.delta_max))
```

**Discrepancy:** The proof claims monotonic widening of the gap. The code
clips δ_H at ±delta_max. Beyond the clipping boundary, further traversals
produce no additional decrease. The gap stops widening.

**Impact on conclusion:** The conclusion (closed SUCCESS system is absorbing)
still holds — once clipped, the gap is stable and positive, so the system
remains trapped. But the *mechanism* described (monotonic widening) is false
past the clip point.

**Fix:** Add clipping to the proof: "For U(e) < delta_max/λ_s, the gap
widens monotonically. Beyond this, δ_H saturates at −delta_max and the gap
stabilizes at S* − S_γ(δ_max), which remains positive. The absorbing
property holds in both regimes."

---

## 4. Evolved Code Beyond Papers

The following code features exist in the current system but are not described
in any paper. These are not *wrong* — they are extensions. But a reader of
the papers cannot know about them.

### 4.1 P1 Historization Extensions

| Feature | Code | Paper 1 |
|---------|------|---------|
| Split decay ρ_S / ρ_F | `rho_s`, `rho_f` in historization.py | Single ρ only |
| PARTIAL outcome | U += 0.5, F += 0.3 | SUCCESS/FAILURE only |
| Surprise dampening | w = 0.5 on surprise events | Not mentioned |
| Epistemic trust | trust(e) = exp(−staleness/τ) | Not mentioned |
| Contextual inscription | InscriptionContext metadata | Not mentioned |

### 4.2 P1 Controller Extensions

| Feature | Code | Paper 1 |
|---------|------|---------|
| Focus narrowing (OI > threshold) | Reduces candidates to focus_k | Not mentioned |
| Peer integration | External peer_fn suggestion | Not mentioned |
| Typed escalation | DEAD_END/FILTERED/EXHAUSTED/OVERLOADED | Only DEAD_END |
| SU(2) amplitude mode | use_su2 flag | Not mentioned (→ P2/P3) |
| Override gates | Revisit-aware, self-graph health | Not mentioned |

### 4.3 P5 Transition Field

The code's transition field includes optional `curvature_modulation`,
`overlap_modulation`, and `inertia_modulation` multipliers. The docstring
references the evolved formula but cites the internal spec ("§2.4"), not any
published paper.

---

## 5. Coverage Gaps — Modules Without Papers

### 5.1 Tier 1: Architecturally Novel (need dedicated papers)

| Module Group | Lines | Core Mechanism | Suggested Paper |
|-------------|------:|----------------|-----------------|
| dream_mode.py | 1,442 | Edge fingerprints, WL matching, cross-domain equivalence, consolidation | P7: "Emergent Consolidation" |
| structural_entropy.py + sleep_wake.py | 731 | T_s-driven forgetting, inscription threshold, automatic dream/wake rhythm | Part of P7 |
| self_tuning.py + parameter_sensitivity.py | 1,602 | Meta-landscape over parameter space, E₀ dynamics applied to own θ-vector | P8: "Self-Tuning via Meta-Landscapes" |
| structural_mutation.py | 693 | Topology self-modification with oscillation protection | Extend P4 or new paper |
| community.py | 283 | Emergent communities from R_eff via weighted LPA, GT-7 resolution | P9: "Emergent Structure" |
| perception.py + communication.py + ui_emitter.py + feedback.py | 1,529 | Perception ontology, intent detection, perception-driven UI, feedback loop | P10: "Perception-Driven Communication" |
| observation.py + observation_controller.py | 536 | Observation-as-domain, intentional O-Landscape navigation | Could fold into P4 addendum |

### 5.2 Tier 2: Significant but Foldable (addenda to existing papers)

| Module | Lines | Could extend |
|--------|------:|--------------|
| residual_tension.py | 234 | P1 (tension analysis) |
| resonator.py | 222 | P1 (interference) |
| dynamic_horizon.py | 129 | P1 (amplitude overlay) |
| exploration_policy.py | 101 | P1 (Born sampling) |
| mode_controller.py | 147 | P5 (mode switching by trace load) |
| perspective_diagnostic.py | 171 | P2/P3 (SU(2) vs U(1) comparison) |
| curriculum.py | 341 | P4 (hierarchical learning) |
| evidence_interpreter.py | 379 | Infrastructure — no paper needed |

### 5.3 Tier 3: Infrastructure (no paper coverage needed)

llm_adapter.py, memory_os.py, session.py, e0_session.py, interactive_session.py,
interactive_server.py, service.py, provenance.py, ui_renderer.py, text_renderer.py,
rendering_adapter.py, bootstrapper.py, canon_loader.py, graph_validation.py,
snapshot_codec.py, config.py, envelope.py, input_pipeline.py, peer_bridge.py,
scenario_loader.py, canon_self_bridge.py, visual_pretraining.py, domain_invoice.py,
chess_e0.py, chess_team.py

---

## 6. What We Actually Prove — Honest Assessment

### 6.1 Structurally Derived (strongest claims)

| Claim | Paper | Holds? |
|-------|-------|--------|
| Ψ = exp(−S + iΘ) produces interference on directed graphs | P1 | ✅ Yes |
| SU(2) lift is carrier-minimal for internal difference | P2 | ✅ Yes |
| Born criterion is unique under Bounded Exclusive Realization | P2 | ✅ Yes |
| Locality ℓ is monotonically non-decreasing | P5 | ✅ Yes |
| Fresh degeneration: scoped ≡ global when m̄ = 0 | P5 | ✅ Yes |
| Phase transition at analytically predictable n* | P5 | ✅ Yes |
| Closed SUCCESS system is absorbing | P6 | ✅ Yes (proof needs δ_max fix) |
| M_H and I enter selection multiplicatively | P5 | ✅ Yes |

### 6.2 Empirically Demonstrated (bounded claims)

| Claim | Paper | Domain count | Limitation |
|-------|-------|:------------:|------------|
| Geometry dominates decision rule | P1 | 380 graphs | All N < 50 |
| Modulation is non-destructive | P5 | 14 domains | All N < 20 |
| Reflexion is non-destructive | P4 | 10 domains | All N < 20 |
| Scoped ≡ global on fresh domains | P5 | 10 domains | All fresh start |
| Exchange beats reflexion for novelty | P6 | 5 pairings | Controlled setup |

### 6.3 What We Do NOT Prove

1. **No scaling evidence.** All benchmarks use N < 50 states. We have no
   data for N = 100, 500, 1000. The theoretical results (monotonicity,
   convergence) hold for any N, but the *practical* behavior is untested.

2. **No external comparison.** Zero benchmarks against A*, MCTS, RL,
   graph neural networks, or any published baseline. We cannot claim E₀
   is *better* than anything — only that it *works* on its own domains.

3. **No falsification failures.** Every test we wrote passes. This could
   mean the system is correct — or that we haven't written hard enough
   tests. The absence of failing falsification targets is itself a concern.

4. **Dream/Sleep-Wake/Community value unproven.** These subsystems exist
   and work, but we have no controlled experiment showing they outperform
   simpler alternatives (e.g., random restart, periodic reset, k-means
   clustering).

5. **Single-author codebase.** No independent reproduction. No external
   reviewer has verified the implementations match the mathematical claims.

---

## 7. Remediation Plan

### 7.1 Working Rules for Paper Consistency

**Rule 1: Papers are versioned documents.** When code evolves past a paper's
formulas, the paper gets an **Addendum** section at the end with dated
updates. The main text is NOT modified with inline strikes/patches.

**Rule 2: Every formula has a code citation.** Each paper formula includes
a reference to the exact function and file that implements it. Format:
`[impl: module.function, line N]`.

**Rule 3: Parameter defaults are tested.** Each paper that states a default
value (μ, θ, α, ρ) has a unit test that asserts the code default matches
the paper's stated value. Drift becomes a test failure.

**Rule 4: Empirical claims state their boundary.** Every "X holds on Y
domains" claim explicitly states N, |E|, and the domain construction method.
No implicit generalization.

**Rule 5: New subsystems get paper coverage within one arc.** Any module
exceeding 200 lines of novel mechanism gets documented in a paper (new or
addendum) before the next arc begins.

### 7.2 Immediate Fixes (existing papers)

These are corrections to make the papers match reality. Each is a specific,
bounded edit.

| ID | Paper | Section | Fix | Priority |
|----|-------|---------|-----|----------|
| F1 | P1 | Alg. 1 | Add revisit penalty formula: S_penalized = S_eff · (1 + α·𝟙[y ∈ recent(k)]). Classify as heuristic. | High |
| F2 | P1 | §5.1 | Note that M_H and I extensions exist (→ P5 §3) but are off by default | Medium |
| F3 | P5 | §4.1 | Change default from μ = 5.0 to μ = |E|/|V| with derivation reference (C105) | High |
| F4 | P5 | §10.4 | Move all "Resolved (CXxx)" annotations to a new "Addendum" section | Medium |
| F5 | P5 | §11.3 | Same treatment for resolved heuristic claims | Medium |
| F6 | P6 | §4.3 | Change θ default from 0.5 to 0.0. Add note on design evolution. | Medium |
| F7 | P6 | §3.2 | Add δ_max clipping to coupling theorem proof | Medium |
| F8 | P5 | Code | Align emergent_locality.py μ default with scoped_reflexion.py | High |

### 7.3 New Papers Needed

Listed by novelty and structural importance, not by ease.

| ID | Title | Coverage | Core modules | Est. scope |
|----|-------|----------|:------------:|------------|
| P7 | Emergent Consolidation: Dream, Entropy, Sleep-Wake | C109–C121, C135–C139, C154, C168, C178 | dream_mode.py, structural_entropy.py, sleep_wake.py | Major |
| P8 | Self-Tuning: E₀ Dynamics on Parameter Space | C150, C155, B4.1–B4.4 | self_tuning.py, parameter_sensitivity.py | Medium |
| P9 | Emergent Structure: Communities from Historization | C255–C267, GT-7 | community.py, + interactive_session changes | Medium |
| P10 | Perception-Driven Communication | C158–C164 | perception.py, communication.py, ui_emitter.py, feedback.py | Medium |

**P7 is the most urgent** — Dream mode alone is 1,442 lines of novel mechanism
with cross-domain pattern recognition, WL fingerprinting, Hungarian matching,
and bridge hypothesis generation. None of this is documented in paper form.

**P9 is the most structurally important** — it documents the GT-7 Coherent
Domain Error and its resolution, which is the single largest architectural
lesson in the project's history. It would formalize "Domains are E₂ artifacts,
not E₀ primitives."

### 7.4 Scaling and External Validation

These are not paper fixes but research tasks that address the fundamental
gaps in §6.3.

| ID | Task | Purpose | Prerequisite |
|----|------|---------|-------------|
| S1 | Scaling benchmark: N = 100, 500, 1000 | Test empirical claims beyond toy domains | Generate large structured landscapes |
| S2 | SOTA comparison on standard benchmarks | Position E₀ relative to existing methods | Identify suitable graph-navigation benchmarks |
| S3 | Independent reproduction protocol | Enable external verification | Clean API documentation + minimal example |
| S4 | Construct falsification targets that SHOULD fail | Test the boundaries of our claims | Identify conditions where E₀ provably cannot work |

### 7.5 Execution Order

```
Phase A — Consistency (papers match code):
  F1–F8: Fix all paper/code mismatches
  Rule 3: Add parameter-default tests
  
Phase B — Coverage (close the gap):
  P9: Emergent Structure (GT-7 story — most structural value)
  P7: Dream/Entropy/Sleep-Wake (largest undocumented subsystem)
  
Phase C — Honesty (test our limits):
  S4: Falsification targets
  S1: Scaling benchmarks
  
Phase D — Positioning (external context):
  S2: SOTA comparison
  S3: Reproduction protocol
  P8, P10: Remaining papers as needed
```

Each phase must complete before the next begins. Within a phase, items
are independent and can be parallelized.

---

## 8. Claim Registry — Cross-Paper Status

### 8.1 All Derived Claims (structural chain)

| # | Claim | Paper | Valid? | Note |
|---|-------|-------|--------|------|
| D1 | Ψ = exp(−S+iΘ) from Δ, R, H | P1 | ✅ | Code matches |
| D2 | Holonomy independence (Theorem 1) | P1 | ✅ | |
| D3 | SU(2) carrier minimality | P2 | ✅ | |
| D4 | Born criterion uniqueness | P2 | ✅ | |
| D5 | 720° periodicity | P2/P3 | ✅ | |
| D6 | Curvature M_H feedback loop convergence | P3 | ✅ | |
| D7 | Self-graph core protection | P4 | ✅ | |
| D8 | Reflexive action reversibility | P4 | ✅ | |
| D9 | Locality monotonicity | P5 | ✅ | |
| D10 | Phase transition timing | P5 | ✅ | |
| D11 | Convergence to ℓ* | P5 | ✅ | |
| D12 | Fresh degeneration | P5 | ✅ | |
| D13 | Uniqueness among rational functions (A1–A3) | P5 | ✅ | |
| D14 | Non-uniform convergence (§5.5) | P5 | ✅ | |
| D15 | Closed SUCCESS system is absorbing | P6 | ⚠️ | Proof needs δ_max fix |
| D16 | Coupling breaks reinforcement | P6 | ✅ | |

### 8.2 All Empirical Claims

| # | Claim | Paper | Tests pass? | Boundary |
|---|-------|-------|:-----------:|----------|
| E1 | Geometry dominates decision rule | P1 | ✅ | 380 graphs, N < 50 |
| E2 | Modulation non-destructive (14 domains) | P5 | ✅ | N < 20 |
| E3 | Scoped ≡ global on fresh (10 domains) | P5 | ✅ | All fresh |
| E4 | Inertia flips confused forks | P5 | ✅ | D11 only |
| E5 | Overlap selects triangle paths | P5 | ✅ | D12 only |
| E6 | Reflexion non-destructive (10×3) | P4 | ✅ | N < 20 |
| E7 | Exchange beats reflexion for novelty | P6 | ✅ | 5 pairings |
| E8 | Overload peer resolves without explicit comm | P6 | ✅ | Controlled |
| E9 | Locality rises during navigation | P5 | ✅ | Chain/star |

### 8.3 All Heuristic Claims

| # | Claim | Paper | Status |
|---|-------|-------|--------|
| H1 | Revisit penalty formula | P1 | Not formalized — **needs F1** |
| H2 | μ = 5.0 default | P5 | **Superseded** by C105 — needs F3 |
| H3 | BFS-spherical scope sufficient | P5 | **Superseded** by C106 (corridor) |
| H4 | θ = 0.5 NoveltyGate default | P6 | **Contradicted** by code (0.0) — needs F6 |
| H5 | Composition independence (M_H × I) | P5 | Empirically verified, not proven |
| H6 | α = 0.5 inertia dampening | P5 | Functional, not derived |
| H7 | ρ = 0.9 decay rate | P1 | Functional, not derived |

---

## 9. Appendix: Module Coverage Matrix

| Module | P1 | P2 | P3 | P4 | P5 | P6 | None |
|--------|:--:|:--:|:--:|:--:|:--:|:--:|:----:|
| primitives.py | | | | | | | ✗ |
| landscape.py | ✓ | | ✓ | | | | |
| historization.py | ✓ | | | | ✓ | | |
| tension.py | | | | | | | ✗ |
| controller.py | ✓ | ✓ | | | ✓ | ✓ | |
| potential.py | ✓ | | | | | | |
| connection.py | ✓ | | ✓ | | | | |
| wavepath.py | ✓ | | | | | | |
| amplitude_overlay.py | ✓ | | | | | | |
| spinor_connection.py | | ✓ | ✓ | | | | |
| overlap.py | | | | | ✓ | | |
| self_graph.py | | | | ✓ | | | |
| dual_reflection.py | | | | ✓ | | | |
| reflexive_action.py | | | | ✓ | | | |
| reflexive_edge_proposal.py | | | | ✓ | | | |
| integrated_reflexion.py | | | | ✓ | ✓ | | |
| scoped_reflexion.py | | | | | ✓ | | |
| emergent_locality.py | | | | | ✓ | | |
| multiverse.py | | | | | | ✓ | |
| raumzeit_coupling.py | | | | | | ✓ | |
| cross_reflexion.py | | | | | | ✓ | |
| coupling_router.py | | | | | | ✓ | |
| llm_cocognition.py | | | | | | ✓ | |
| dream_mode.py | | | | | | | ✗ |
| structural_entropy.py | | | | | | | ✗ |
| sleep_wake.py | | | | | | | ✗ |
| self_tuning.py | | | | | | | ✗ |
| structural_mutation.py | | | | | | | ✗ |
| community.py | | | | | | | ✗ |
| perception.py | | | | | | | ✗ |
| communication.py | | | | | | | ✗ |
| observation.py | | | | | | | ✗ |
| observation_controller.py | | | | | | | ✗ |
| curriculum.py | | | | | | | ✗ |
| resonator.py | | | | | | | ✗ |
| residual_tension.py | | | | | | | ✗ |
| exploration_policy.py | | | | | | | ✗ |

✓ = referenced in paper | ✗ = no paper coverage | Blank = not relevant

---

*This audit was generated through systematic code-vs-paper verification,
not self-assessment. All formula comparisons were done by reading both the
paper text and the implementing code independently.*
