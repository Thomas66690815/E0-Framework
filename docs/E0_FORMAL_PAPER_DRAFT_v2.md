# E₀ — A Domain-Invariant Transition Framework with Empirical Benchmark

## Draft v2.0

**Status:** Pre-submission draft  
**Scope:** Formal framework + operational realization + empirical validation  
**Language:** English  
**Repository:** https://github.com/Thomas66690815/E0-Framework  
**DOI (Zenodo):** https://doi.org/10.5281/zenodo.15007953

---

## Abstract

We present E₀, a deterministic framework for transition-centered systems built from three primitive quantities: structural difference Δ, resistance R, and historization H. From these, E₀ derives tension S = Δ · R_eff, coherence C = exp(−S), local transition fields, non-integrable connection, holonomy, and a complex path amplitude Ψ(p) = exp(−S(p)) · exp(iΘ(p)). The framework yields a transition-centered dynamic system that operates both locally, through tension-minimizing selection, and globally, through phase-bearing path interference.

We demonstrate domain-invariance empirically: a single controller implementation with fixed parameters (α = 2.0, k = 3, greedy selection) solves 10 structurally diverse domains — including linear chains, diamonds, Gordian traps, 2-cycle traps, grid worlds with obstacles, multi-goal fan-outs, a real-world invoice processing workflow, nested cycles, wide DAGs, and bottleneck funnels. All 10 goals are reached; ratings range from A to B with no domain-specific tuning.

The central claim is that transition dynamics need not be derived from probability, energy, or agent-level reasoning. They can be derived from the structural instability of unresolved difference under finite resistance — Axiom A₀.

---

## 1. Introduction

Formal systems for describing change typically begin by assuming one of:

- objects (set theory, type theory),
- states (automata, Markov chains),
- probabilities (Bayesian inference, statistical mechanics),
- energies (Hamiltonian dynamics),
- or agents (game theory, reinforcement learning).

E₀ begins elsewhere. Its starting point is the observation that the minimal structural unit of development is not the object, but the **transition under difference**. What matters first is not what a thing *is*, but what structural difference exists, what resists its resolution, and how prior realized transitions alter the future transition landscape.

The framework is built around three primitive quantities: difference Δ, resistance R, and historization H. From these, without additional assumptions, E₀ derives:

1. **Tension** S = Δ · R_eff — the integration burden of difference
2. **Coherence** C = exp(−S) — a bounded measure of path stability
3. **Transition field** v(x,y) = Δ · M_H · exp(−S) — local transition capacity
4. **Connection** ω(x,y) — non-integrable phase shift per edge
5. **Holonomy** Hol(γ) = Σ_e ω(e) — accumulated phase around closed cycles
6. **Path amplitude** Ψ(p) = exp(−S) · exp(iΘ) — complex path representation
7. **Interference** I(z) = |Σ_p Ψ(p)|² — constructive/destructive path interaction

The derivation chain is strictly monotonic: each quantity depends only on previously defined quantities. No circularity exists in the mathematical structure.

This paper presents:

- the formal mathematical core (§2–§9),
- the operational controller realization (§10),
- the domain-invariance benchmark with 10 structurally diverse domains (§11),
- a discussion of domain-invariance as a structural property (§12),
- and the relationship to related work and scope limitations (§13–§14).

---

## 2. Primitive Structure

### 2.1 States and Directed Transitions

Let X be a finite set of distinguishable states and E ⊆ X × X a set of directed edges. A directed transition exists only if (x → y) ∈ E. E₀ does not assume symmetric accessibility.

### 2.2 Difference

For each directed edge e = (x → y), define structural difference:

    Δ : E → ℝ₊

Properties:
- Δ is defined only on existing directed edges
- Δ(x,y) ≥ 0
- Δ(x,y) = 0 indicates no structural difference along that transition

### 2.3 Base Resistance

For each directed edge, define base resistance:

    R₀ : E → ℝ₊

R₀(x→y) expresses the baseline structural inertia of the transition, independent of realized transition history.

### 2.4 Historization

For each edge e, define historization as:

    H(e) = (U(e), F(e))

where U(e) is the accumulated success trace and F(e) is the accumulated failure trace. Historization modifies future transition resistance:

    δ_H(e) = λ_f · F(e) − λ_s · U(e)

with historization rates λ_f, λ_s ≥ 0. Successes lower future resistance; failures increase it.

### 2.5 Time

Time τ is the ordering of historizations. If no historization occurs, no time progresses. Time is not assumed a priori — it is derived from the irreversibility of realized transitions.

---

## 3. Derived Quantities: Tension and Coherence

### 3.1 Effective Resistance

    R_eff(e) = max(R₀(e) + δ_H(e), ε)

where ε > 0 is a structural floor preventing collapse.

### 3.2 Tension

    S(x→y) = Δ(x,y) · R_eff(x→y)

Tension is the fundamental dynamic quantity. It expresses not merely difference, not merely resistance, but the integration burden of difference under resistance.

### 3.3 Coherence

    C(x→y) = exp(−S(x→y))

Properties: 0 < C ≤ 1. Lower tension implies higher coherence. Coherence is not a probability but a bounded structural measure.

### 3.4 Path Tension

For a path p = (x₀ → x₁ → ... → xₙ):

    S(p) = Σᵢ S(xᵢ → xᵢ₊₁)

---

## 4. Axiom A₀ — Structural Instability of Non-Transition

**Axiom A₀.** If a difference Δ > 0 exists and there is a structurally admissible path with finite resistance R < ∞, then non-transition is structurally less stable than transition.

**Central Law.** If Δ > 0 and an admissible path with R_eff < ∞ exists, a transition must occur.

This axiom introduces no goals, values, or agents. It formalizes the instability of unresolved difference when resolution is structurally possible.

From A₀ alone, the following are necessary consequences:

- **Transition enforcement:** change is structurally obligatory, not optional
- **Directionality of time:** historization is irreversible
- **Structural memory:** past transitions alter future resistance
- **Learning and path dependence:** repeated transitions modify the landscape
- **Bounded maximum rate:** unlimited realization would collapse historization ordering

---

## 5. Transition Field

At time τ, the system is represented as a landscape:

    L_τ = (X, E, Δ, R_eff, H)

### 5.1 Local Transition Field

    v(x,y) = Δ(x,y) · M_H(x,y) · exp(−S_eff(x→y))

where M_H is a historization modulation term. In the minimal form M_H = 1, yielding:

    v(x,y) = Δ(x,y) · exp(−S(x→y))

The transition field is not probabilistic. It expresses local structural openness — how readily a transition can be realized.

### 5.2 Local Potential

    Φ(x) = Σ_{y ∈ N⁺(x)} S(x→y)

Φ(x) measures the total transition burden at state x.

---

## 6. Connection and Holonomy

### 6.1 Gradient and Rotational Decomposition

    v_grad(x,y) = Φ(x) − Φ(y)
    v_rot(x,y)  = v(x,y) − v_grad(x,y)

### 6.2 Connection

    ω(x,y) = ½ · (v_rot(x,y) − v_rot(y,x))

For directed graphs where the reverse edge is absent, the reverse rotational term is treated as 0.

### 6.3 Path Phase

    Θ(p) = Σ_{e ∈ p} ω(e)

### 6.4 Holonomy

For a closed cycle γ:

    Hol(γ) = Θ(γ)

Hol(γ) ≠ 0 indicates non-integrable, path-dependent structure. The orientation is not merely local cost — it carries irreducible positional information.

**Key result (Gordian Trap Theorem):** The holonomy between two path families sharing endpoints depends only on forward-edge transition fields. The potential Φ cancels exactly:

    ΔΘ = ½ · [Σ v(loop edges) − Σ v(short edges)]

This result is verified computationally (44 tests, see §11).

---

## 7. Complex Path Representation

### 7.1 Path Amplitude

    Ψ(p) = exp(−S(p)) · exp(iΘ(p))

This is not a quantum postulate. It is the mathematically natural compact representation combining path magnitude (via tension) and path orientation (via connection phase).

### 7.2 Endpoint Summation

For a target state z, over a bounded path set P(z):

    Ψ(z) = Σ_{p ∈ P(z)} Ψ(p)

### 7.3 Intensity

    I(z) = |Ψ(z)|²

Intensity yields constructive or destructive interference between path families to the same target. This is a structural effect, not a probabilistic postulate.

---

## 8. Historization Dynamics

After each realized transition outcome:

- **Success:** U(e) += 1 → δ_H decreases → R_eff decreases → S decreases → path becomes easier
- **Failure:** F(e) += 1 → δ_H increases → R_eff increases → S increases → path becomes harder

This gives E₀ its learning-like property: the future is changed because realized transitions alter resistance structure. The system does not fit parameters to data — it structurally accumulates experience.

---

## 9. Mathematical Dependency Chain

The complete derivation is strictly monotonic:

    Δ → R₀ → H → δ_H → R_eff → S → C → v → Φ → v_grad/v_rot → ω → Θ → Ψ → I

Every quantity is derived from previously defined quantities. The controller selection law argmin S_eff operates on this chain.

---

## 10. Operational Controller Realization

### 10.1 Selection Law

Given current state x, the controller selects:

    y* = argmin_{y ∈ A(x)} S_pen(x→y)

where A(x) is the admissible neighbor set and S_pen includes a revisit penalty:

    S_pen(x→y) = S_eff(x→y) · (1 + α · 𝟙[y ∈ recent(k)])

with penalty weight α and sliding window of size k.

### 10.2 Admissibility

A neighbor y is admissible from x if:

1. S_eff(x→y) < ∞ (edge exists)
2. S_eff(x→y) ≤ S_max (optional tension ceiling)
3. C(x→y) ≥ C_min (optional coherence floor)

### 10.3 Escalation

When no admissible neighbor exists, the controller classifies the situation:

- **DEAD_END:** no outgoing edges → field-based global jump
- **FILTERED:** edges exist but fail admissibility → relax threshold
- **EXHAUSTED:** all admissible neighbors recently visited → least-recent selection

Escalation is typed, not random. This is a decisive difference from always-answer systems.

### 10.4 Cycle: Select → Execute → Historize

Each controller cycle:

1. Select next state y* (greedy + revisit penalty + escalation)
2. Execute transition (x → y*) → Outcome ∈ {SUCCESS, FAILURE, PARTIAL}
3. Historize: update H(x→y*) based on outcome
4. Update sliding window

The controller parameters are:

| Parameter | Symbol | Default | Description |
|-----------|--------|---------|-------------|
| Revisit penalty | α | 2.0 | Multiplicative penalty for recently visited states |
| Recent window | k | 3 | Number of recent states tracked |
| Max escalation R | R_esc | 5.0 | Maximum resistance for escalation edges |
| Tension ceiling | S_max | ∞ | Admissibility upper bound |
| Coherence floor | C_min | 0.0 | Admissibility lower bound |

These parameters are **fixed across all benchmark domains** (§11). No domain-specific tuning is performed.

---

## 11. Empirical Benchmark: Domain-Invariance

### 11.1 Claim

E₀'s controller is domain-invariant: the same algorithm with identical parameters navigates any well-formed landscape. The controller derives its behavior entirely from the landscape's tension structure.

### 11.2 Benchmark Design

We construct 10 structurally diverse domains spanning different topology classes, scales, and challenges:

| # | Domain | Nodes | Edges | Topology | Challenge |
|---|--------|-------|-------|----------|-----------|
| D1 | Linear Chain | 8 | 7 | linear | Pure forward, no branching |
| D2 | Diamond | 4 | 4 | diamond | 2-family path discrimination |
| D3 | Gordian Trap | 6 | 6 | gordian | Decoy loop with failure signal |
| D4 | Greedy Trap | 6 | 6 | cycle_trap | 2-cycle oscillation escape |
| D5 | Grid Detour | 22 | 56 | grid | 5×5 spatial navigation around wall |
| D6 | Multi-Goal Star | 7 | 8 | star | 3 goals, 1 failing path + recovery |
| D7 | Invoice Process | 10 | 16 | process | Real-world business workflow |
| D8 | Nested Cycles | 6 | 7 | cyclic | Overlapping loops + goal exit |
| D9 | Wide DAG | 8 | 11 | dag | 5 parallel paths, no cycles |
| D10 | Bottleneck | 6 | 5 | bottleneck | Dead-end decoy + chokepoint |

**Invariance constraint:** All domains use the same E0Controller with α = 2.0, k = 3, HybridMode.GREEDY. No parameter is adjusted per domain. Domain-specific execute_fn outcomes (SUCCESS/FAILURE/PARTIAL) represent the domain's physics — not controller tuning.

### 11.3 Results

| Domain | Goal | Steps | Success Rate | Esc | Rev | Efficiency | Avg Tension | Rating |
|--------|------|-------|-------------|-----|-----|-----------|-------------|--------|
| D1 Linear Chain | ✓ | 7 | 100% | 0 | 0 | 1.00 | 0.150 | A |
| D2 Diamond | ✓ | 2 | 100% | 0 | 0 | 1.00 | 0.560 | A |
| D3 Gordian Trap | ✓ | 6 | 83% | 1 | 1 | 0.50 | 0.917 | B |
| D4 Greedy Trap | ✓ | 6 | 100% | 1 | 1 | 0.67 | 0.927 | B |
| D5 Grid Detour | ✓ | 8 | 100% | 0 | 0 | 1.00 | 0.083 | A |
| D6 Multi-Goal Star | ✓ | 5 | 80% | 1 | 1 | 0.40 | 1.108 | B |
| D7 Invoice Process | ✓ | 7 | 71% | 0 | 0 | 1.00 | 0.256 | A |
| D8 Nested Cycles | ✓ | 3 | 100% | 0 | 0 | 1.00 | 0.073 | A |
| D9 Wide DAG | ✓ | 3 | 100% | 0 | 0 | 1.00 | 0.073 | A |
| D10 Bottleneck | ✓ | 6 | 83% | 1 | 1 | 0.67 | 0.917 | B |

**Summary:**
- All 10 goals reached: **YES**
- Worst rating: **B**
- Domain-invariant: **YES**

### 11.4 Rating Methodology

Each run is evaluated along multiple dimensions:

- **Goal reached** (binary)
- **Efficiency** = happy_path_length / actual_steps (capped at 1.0)
- **Loop penalty** = repeated 2-cycles / steps
- **Success rate** = SUCCESS outcomes / steps

Ratings:
- **A:** efficiency ≥ 0.7, loop penalty < 0.1
- **B:** efficiency ≥ 0.4, loop penalty < 0.2
- **C:** goal reached, lower quality
- **D:** goal not reached, progress > 50%
- **F:** goal not reached or hard failure

### 11.5 Analysis

**Optimal domains (A-rated):** D1, D2, D5, D7, D8, D9. These domains have clear forward paths or well-structured topologies where greedy selection with revisit penalty finds the optimal solution directly. The controller achieves happy-path efficiency of 1.0.

**Challenging domains (B-rated):** D3, D4, D6, D10. These domains contain structural traps (cycles, dead-ends, failing edges) that require the controller to learn through historization. The typical escape mechanism:

1. Controller enters trap (lowest initial tension)
2. Execute_fn returns FAILURE on the trap edge
3. Historization increases resistance: R_eff(trap) += λ_f
4. Revisit penalty multiplies: S_pen = S_eff · (1 + α)
5. Forward path becomes relatively cheaper
6. Controller escapes trap on next visit

This mechanism is not domain-specific — it is the structural consequence of Axiom A₀ operating through historization.

**Key insight:** Trap escape requires FAILURE outcomes. When all edges succeed, historization reinforces successful loops. This is correct behavior: if a cycle works reliably, there is no structural reason to leave it. The controller escapes only when the domain's physics signals that the trap is unproductive.

### 11.6 Test Infrastructure

The benchmark is backed by 30 automated tests in 5 classes:

- **TestDomainSpecIntegrity** (10): each domain well-formed
- **TestAllDomainsReachGoal** (1): all 10 goals reached
- **TestDomainInvariance** (6): cross-domain invariance assertions
- **TestIndividualDomains** (10): per-domain behavioral expectations
- **TestBenchmarkRunner** (3): infrastructure correctness

Total tests in the framework: 2278 (pytest), 0 failures.

---

## 12. Domain-Invariance as Structural Property

The benchmark results support a stronger claim: domain-invariance in E₀ is not an empirical accident but a structural consequence of the framework's design.

The controller uses only:

- **S_eff(x→y)** = tension, derived from Δ and R_eff
- **recent(k)** = a sliding window of visited states
- **Outcome** = the result of executing a transition

None of these quantities are domain-specific. They are structural properties of the landscape. The controller cannot distinguish between an invoice processing step and a grid navigation step — both are simply transitions with tension, resistance, and outcomes.

This is the operational meaning of E₀'s Axiom A₀: the instability of non-transition given Δ > 0 and R < ∞ is independent of what the states "mean."

The three mechanisms that produce effective navigation across all domains are:

1. **Greedy selection** (argmin S_eff): locally optimal in smooth landscapes
2. **Revisit penalty** (α · 𝟙[recent]): breaks cycles
3. **Historization** (δ_H from outcomes): learns from failure

These three mechanisms are sufficient for all 10 domains. No reward function, no utility maximization, no goal-specific heuristic is required.

---

## 13. Related Work

E₀ relates to several formal traditions while differing from each:

**Markov Decision Processes (MDPs):** MDPs operate on transition probabilities and reward functions. E₀ uses deterministic tension minimization with historization. There is no reward signal — the controller minimizes structural burden, not accumulated return.

**Reinforcement Learning (RL):** RL agents learn value functions through repeated interaction. E₀'s historization superficially resembles value learning but differs structurally: historization modifies the resistance landscape (the environment), not a separate value estimate. The controller has no value function.

**Graph search (A*, Dijkstra):** Classical search algorithms find optimal paths in weighted graphs. E₀'s controller is not a path planner — it makes greedy local decisions with revisit penalty. The amplitude overlay (§7) provides path-level analysis but does not replace greedy selection in the default mode.

**Category theory / process algebras:** E₀ shares the emphasis on morphisms (transitions) over objects (states) but is concrete rather than abstract — it specifies numeric quantities and operational selection laws.

**Information geometry / statistical manifolds:** The connection ω and holonomy Hol(γ) give E₀ a geometric structure reminiscent of information geometry, but E₀'s base space is a directed graph, not a smooth manifold.

---

## 14. Scope and Limitations

This paper presents E₀ as currently stabilized. It does **not** claim:

- a continuous-limit generalization to smooth manifolds,
- a completed connection to quantum mechanics (despite the formal parallel of Ψ),
- empirical validation over unrestricted open-world domains,
- a replacement for probabilistic or energy-based frameworks,
- that the benchmark covers all possible failure modes.

Open questions include:

- **Raumzeit (emergent spacetime):** The Ontodynamics canon predicts emergent spacetime from historized topology. E₀ currently operates as a closed system with no external coupling. Emergent spacetime would require coupling to an environment.
- **Reactivation policy:** The controller can deactivate failing components but lacks a protocol for re-enabling them. This is a structural gap, not a bug.
- **Amplitude mode benchmark:** The current benchmark uses only GREEDY mode. Future work should benchmark AMPLITUDE_ON_DISAGREE and BORN_SAMPLING modes across the same 10 domains.
- **Scalability:** The current benchmark domains range from 4 to 22 nodes. Behavior on large-scale landscapes (n > 1000) is tested separately (see scaling tests) but not benchmarked for domain-invariance.

---

## 15. Conclusion

E₀ offers a formal alternative to probability-first and energy-first reasoning systems. By treating transitions under difference and resistance as primitive, it derives tension, coherence, local transition fields, non-integrable connection, and complex path amplitude without additional assumptions.

The empirical benchmark demonstrates that this is not merely a formal exercise: a single controller with fixed parameters navigates 10 structurally diverse domains — from linear chains to real-world invoice processing — with all goals reached and no domain-specific tuning.

The central insight is:

> The structural instability of unresolved difference under finite resistance — Axiom A₀ — is sufficient to produce effective, adaptive navigation without goals, probabilities, or reward functions.

The framework is publicly available at https://github.com/Thomas66690815/E0-Framework and archived on Zenodo.

---

## Appendix A: Notation Summary

| Symbol | Definition | Domain |
|--------|-----------|--------|
| X | Set of states | finite |
| E | Directed edges | E ⊆ X × X |
| Δ(x,y) | Structural difference | ℝ₊ |
| R₀(x,y) | Base resistance | ℝ₊ |
| H(e) | Historization (U, F) | ℕ₀ × ℕ₀ |
| δ_H(e) | Historization correction | ℝ |
| R_eff(e) | Effective resistance | ℝ₊ |
| S(x→y) | Tension | ℝ₊ |
| C(x→y) | Coherence | (0, 1] |
| v(x,y) | Transition field | ℝ₊ |
| Φ(x) | Local potential | ℝ₊ |
| ω(x,y) | Connection | ℝ |
| Θ(p) | Path phase | ℝ |
| Ψ(p) | Path amplitude | ℂ |
| I(z) | Intensity | ℝ₊ |
| τ | Time (historization count) | ℕ₀ |
| α | Revisit penalty weight | ℝ₊ |
| k | Recent window size | ℕ |

---

## Appendix B: Benchmark Reproduction

To reproduce the benchmark results:

```bash
git clone https://github.com/Thomas66690815/E0-Framework.git
cd E0-Framework
pip install -e .

# Run benchmark (human-readable)
python -m e0_controller.benchmark_domain_invariance

# Run benchmark (JSON)
python -m e0_controller.benchmark_domain_invariance --json

# Run all tests (2278 tests)
python -m pytest e0_controller/ -q
```

All code is deterministic. Results are reproducible across runs.

---

## Appendix C: Canon Reference

The canonical E₀ core is defined in 155 lines of plain text (see `canon/e0-canon-plain.txt`). The seven primitive concepts are:

1. **State** — a distinguishable configuration
2. **Difference** — a measure of non-identity between states
3. **Path** — a structural admissibility condition for transitions
4. **Resistance** — structural inertia of a transition
5. **Historization** — irreversible modification of resistance by realized transitions
6. **Time** — the ordering of historizations
7. **Rate** — difference divided by resistance (derived but operationally necessary)

From these seven primitives and Axiom A₀, the entire derivation chain follows.

---

*End of paper.*
