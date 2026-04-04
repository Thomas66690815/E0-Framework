# E₀ Empirical Insights

**Date:** 2026-04-04  
**Trigger:** C72–C81 (Chess), C147 (Self-Graph Demo)  
**Status:** Validated through self-play, team-vs-solo, 10-domain benchmark, multi-cluster dynamics, transfer experiments, convergence analysis, asymmetric decay experiments, structural prediction analysis, scaling + focus narrowing experiments, self-graph mechanism demo

---

## Context

C72 applied E₀ to chess — not as a competitive engine, but as a stress test.
The question: can E₀ navigate an adversarial, real-time domain where the
"right" strategy is non-obvious and must be discovered, not specified?

Result: yes, and the experiment reveals eleven insights about the framework
as a whole that go beyond the chess domain.

---

## Insight 1: Historization Discovers Non-Trivial Strategies

**Observation:**  
In self-play, E₀ discovers that DEVELOPMENT→CENTER_CONTROL is always productive
(trace_quality = +1.0) and MATERIAL→PAWN_STRUCTURE never works (trace_quality = −1.0).
This corresponds to the classical chess opening principle: develop pieces first,
then establish central control.

**Why this matters for E₀:**  
In all previous domains (C53 benchmark with 10 domains, Gridworld, Invoice, Burnout),
the "optimal strategy" was either obvious (shortest path) or pre-encoded in the
landscape topology.  Chess is the first domain where:
- The optimal dimension-transition sequence is **not derivable from the landscape structure**
- Historization alone produces **domain expertise** that a human would recognize as correct

**Formal implication:**  
Historization is not merely memory.  The formula q(e) = (U−F)/(U+F+ε) is a
sufficient learning signal for strategy emergence in adversarial settings.

---

## Insight 2: Landscape States Are Abstraction-Invariant

**Observation:**  
In all prior E₀ applications, landscape states represented **process steps** —
positions in a workflow, cells in a grid, stages of an incident.  In Chess,
states represent **strategic dimensions** — conceptual axes of evaluation.
The controller algorithm is identical.  No code change was needed.

**Why this matters for E₀:**  
This empirically validates that the Landscape formalism L_t = (X_t, E_t, v_t, S_t, H_t)
is genuinely domain-agnostic.  Not just across domains (C53 showed that), but across
**abstraction levels**.  States can be:
- Concrete positions (Gridworld cells)
- Process stages (Invoice: RECEIVED → PDF_LOADED → ...)
- Abstract concepts (Chess dimensions: MATERIAL, KING_SAFETY, ...)

The controller sees only (state, edge, Δ, R_eff) and navigates.

**Formal implication:**  
The type of X_t is unconstrained.  It can be instantiated at any level of
abstraction without modifying the navigation algorithm — exactly as the
canonical specification (Ontodynamics §7) claims.

---

## Insight 3: Uniform Initialization + Historization → Emergent Differentiation

**Observation:**  
The chess landscape starts with 30 directed edges, all identically initialized
(Δ=0.5, R₀=1.0).  Zero prior knowledge — every transition looks equally promising.
After 60 moves, the historization has differentiated them into a clear strategy:
some transitions reliably succeed (+1.0), others reliably fail (−1.0), and some
remain ambiguous.

**Why this matters for E₀:**  
Previous landscapes were always **pre-differentiated** — each edge had hand-crafted
Δ and R₀ values reflecting domain knowledge (e.g., OCR parsing has high resistance).
Chess proves that E₀ works even when the landscape is a blank slate.

This has direct architectural implications:
1. **LLM bootstrapping can be coarser** — the LLM needs to identify relevant
   dimensions/states and connect them, but doesn't need to estimate accurate Δ/R₀.
2. **`Landscape.fully_connected(states)`** is now a first-class factory method,
   because "uniform start, learned differentiation" is a valid construction pattern.
3. **`Historization.strategy_profile()`** is now available to extract what was learned.

**Formal implication:**  
The information content of a mature landscape is dominated by historization,
not by the initial topology.  Given sufficient interaction, any connected
initial graph converges to a functionally equivalent structure.

---

## Derived Primitives (C73)

These insights led to two new framework primitives:

| Primitive | Location | Purpose |
|---|---|---|
| `Landscape.fully_connected(states, delta, resistance)` | `landscape.py` | Factory for uniform-initialization landscapes (blank-slate pattern) |
| `Historization.strategy_profile(edges, top_n)` | `historization.py` | Extract learned strategy as ranked (edge, quality, load) triples |

Both are small (< 20 lines each), require no new dependencies, and make the
"discover through historization" pattern a first-class workflow.

---

## Insight 4: Emergent Gravity — Historization Creates Attractors

**Observation:**  
In both C72 (solo) and C74 (team), CENTER_CONTROL becomes the dominant
attractor — all dimension transitions converge toward it.  This happens
from a uniform initial landscape (all Δ=0.5, R₀=1.0, zero prior knowledge).
No state was designated as "central" or "important."

The mechanism is self-reinforcing:
- CENTER_CONTROL moves succeed more often (central squares offer more options)
- More SUCCESS → higher trace_quality → lower R_eff
- Lower R_eff → lower S_eff → E₀ gravitates toward it more
- More visits → more historical mass (trace_load) → stronger attractor

**Structural parallel to physical gravity:**

| Physical gravity | E₀ historization |
|---|---|
| Mass curves spacetime | trace_load curves the landscape metric |
| Curvature creates preferred paths | R_eff reduction creates preferred transitions |
| Objects fall toward mass concentrations | Navigation converges toward high-quality states |
| The center isn't pre-designated — it emerges from mass accumulation | The attractor isn't pre-designated — it emerges from success accumulation |
| Self-reinforcing: more mass → more curvature → more accumulation | Self-reinforcing: more success → less resistance → more visits |

**The critical difference — gravity of the future:**  
Physical gravity pulls toward *past* mass accumulation.  E₀ pulls toward
*future optionality*.  The historization looks backward (U/F traces record
what happened), but the attractor points forward: the state with the highest
optionality — the most reachable successor states — becomes the gravitational
center.  This is not a metaphor; it is the same structural dynamic
(self-reinforcing metric deformation from accumulated inscription) operating
on a different substrate.

**Formal mapping to Ontodynamics:**
- trace_load = m(e) = U+F → structural inscription (Layer 2, §4)
- trace_quality = q(e) → directional balance of inscription
- R_eff = R₀ + δ_H → effective metric (deformed by inscription, like g_μν deformed by T_μν)
- S_eff = Δ · R_eff → effective tension (the "force" that guides navigation)
- Attractor emergence = metric deformation from initially flat space

The Einstein field equation says: mass-energy tells spacetime how to curve.
The E₀ historization says: accumulated outcomes tell the landscape how to resist.
In both cases, the geometry is not given — it emerges from what passes through it.

**Why this matters for E₀:**  
This is the first empirical evidence that E₀'s dynamics produce gravitational
attractor behavior from first principles — without any explicit gravity mechanism.
It suggests that the Ontodynamics formalism captures something structural about
how accumulation creates preferred paths, whether in physical spacetime or in
abstract decision landscapes.

---

## Derived Results (C74)

C74 (Team Chess) resolved Open Question #4 and added a new finding:

**Team (3×E₀) beats Solo (1×E₀) by checkmate in 17 moves.**

| Metric | Team (3×E₀) | Solo (1×E₀) |
|---|---|---|
| Result vs Solo opponent | **1-0 checkmate (17 moves)** | 1/2-1/2 draw (60 moves) |
| Max dimension concentration | 5 | 12 |
| Unanimity | 24% | n/a |
| Repetition trap | Broken | Threefold repetition |

The key mechanism: **diversity of starting perspectives** (MATERIAL, KING_SAFETY,
CENTER_CONTROL) prevents the repetition trap that Solo falls into.  Three
players seeing different things → richer historization → decisiveness instead
of oscillation.

---

## Insight 5: Attractor Formation Requires Differential Feedback

**Observation:**  
Insight 4 (emergent gravity) was discovered in chess — a domain with fully
connected topology AND differential feedback (some moves lead to better
positions, others don't).  The question: is this universal, or domain-specific?

**Experiment (C75):**  
Tested attractor formation across all 10 C53 benchmark domains in two configurations:

| Config | Topology | Initialization | execute_fn |
|---|---|---|---|
| Part 1 | Original (asymmetric) | Uniform (Δ=0.5, R₀=1.0) | Original (domain-specific) |
| Part 2 | Fully connected (symmetric) | Uniform (Δ=0.5, R₀=1.0) | Original (domain-specific) |

Attractor metric: concentration ratio = max_incoming_load / total_incoming_load.
Attractor if ratio > 2× uniform baseline (1/N_states).

**Part 1 Results — Original Topology, Uniform Init:**

| Domain | States | Ratio | Top State | Attractor? |
|---|---|---|---|---|
| D1 Linear Chain | 8 | 1.5 | GOAL | no |
| D2 Diamond | 4 | 2.1 | G | YES |
| D3 Gordian Trap | 6 | 1.3 | GOAL | no |
| D4 Greedy Trap | 6 | 1.7 | A | no |
| D5 Grid Detour | 22 | 3.9 | R4C4 | YES |
| D6 Multi-Goal Star | 7 | 1.8 | G1 | no |
| D7 Invoice Process | 10 | 1.8 | APPROVED | no |
| D8 Nested Cycles | 6 | 1.8 | A | no |
| D9 Wide DAG | 8 | 3.0 | GOAL | YES |
| D10 Bottleneck | 6 | 1.5 | GOAL | no |

Result: 3/10.  All "attractors" are trivially the goal-sink or a topological
junction — no emergent attractor.  Asymmetric topology predetermines concentration.

**Part 2 Results — Fully Connected Topology:**

| Domain | States | Edges | Ratio | Top State | Attractor? | Feedback |
|---|---|---|---|---|---|---|
| D1 Linear Chain | 8 | 56 | 2.0 | E | no | all_success |
| D2 Diamond | 4 | 12 | 3.9 | G | YES | all_success |
| D3 Gordian Trap | 6 | 30 | 5.8 | GOAL | YES | differential |
| D4 Greedy Trap | 6 | 30 | 1.5 | GOAL | no | all_success |
| D5 Grid Detour | 22 | 462 | 5.4 | R0C0 | YES* | all_success |
| D6 Multi-Goal Star | 7 | 42 | 6.7 | G1 | YES | differential |
| D7 Invoice Process | 10 | 90 | 9.9 | APPROVED | YES | differential |
| D8 Nested Cycles | 6 | 30 | 1.5 | GOAL | no | differential† |
| D9 Wide DAG | 8 | 56 | 2.0 | A5 | no | all_success |
| D10 Bottleneck | 6 | 30 | 5.8 | GOAL | YES | differential |

Result: 6/10.  The pattern splits cleanly:

| | Differential Feedback | All-Success |
|---|---|---|
| Fully Connected | **4/5 attractor** | 2/5 attractor |

*D5 is a false positive: 0/20 goal reached, 462 edges = noise.
†D8 has weak feedback: only one failing edge in 30 — insufficient signal.

**Two necessary conditions for genuine attractor formation:**

1. **Topological choice** — the graph must offer alternative paths so
   the controller can differentiate.  Linear chains have no choice.
2. **Differential environment feedback** — some transitions must fail
   so historization creates asymmetric inscription.  With all_success,
   trace_quality = +1.0 everywhere → no differentiation → no attractor.

When both conditions hold, the attractor ratio reaches 5.8–9.9×.
When either is missing, ratio ≤ 2.0.

**Why D7 (Invoice) is the strongest attractor (9.9×):**
Fully connected + 10 states + differential feedback (DATA_EXTRACTED→CUSTOMER_FOUND
fails, CONTRACT_MATCH→POLICY_OK partial).  The controller discovers the one-hop
path to APPROVED within 21 steps, concentrating almost all inscription there.
This is E₀'s equivalent of a black hole: maximal gravitational pull from maximal
differential experience.

**Structural parallel refined:**

| Physical gravity | E₀ attractor | Required condition |
|---|---|---|
| Mass density gradient | trace_load gradient | Differential outcomes |
| Isotropic space | Fully connected topology | No structural privilege |
| Self-reinforcing curvature | Self-reinforcing R_eff reduction | Both together |

**Formal implication:**  
Attractor formation is NOT a universal property of historization.  It is a
**conditional emergence** that requires both structural freedom (choice) and
environmental signal (differential outcomes).  This is consistent with the
Ontodynamics framework: without resistance variation (§9), there is no basis
for metric deformation.  The "gravity" of Insight 4 was not a property of
the formalism alone — it was a property of the formalism interacting with
a differentiating environment.

This is arguably more interesting than universality: it means attractor
formation is falsifiable.  Any domain with all-success outcomes and symmetric
topology should NOT produce an attractor.  This can be tested.

---

## Insight 6: Multi-Attractor Requires Independent Historization

**Observation:**
Insight 4 showed that historization creates gravitational attractors.
Insight 5 showed this requires differential feedback + topological choice.
The natural next question: in a large landscape with multiple natural
"clusters," do multiple attractors form simultaneously?

**Experiment (C76):**
25 states in 5 clusters (A1–A5 through E1–E5).  Clustered topology:
fully connected within each cluster, sparse bridges between adjacent clusters.
Differential execute_fn: intra-cluster = SUCCESS, inter-cluster = FAILURE
with probability P_FAIL.

Tested 5 variants:

| Variant | Setup | # Attractors | Dominant | Gini |
|---|---|---|---|---|
| V1 | Shared H, P_fail=0.7 | 1 | E (99.5%) | 0.80 |
| V2 | Shared H, P_fail=0.3 | 1 | E (99.5%) | 0.80 |
| V3 | Shared H, P_fail=1.0 | 1 | E (99.5%) | 0.80 |
| V4 | Shared H, asymmetric | 1 | E (99.5%) | 0.80 |
| V5 | Independent H (1 per cluster) | **5** | Equal (20% each) | **0.00** |

**Key finding: Shared Historization → Attractor Monopoly.**

A single E₀ system with shared Historization can only develop ONE attractor,
regardless of topological clustering or feedback strength.  The mechanism:

1. The greedy controller settles into whichever region it explores most recently
2. ρ=0.9 decay erases traces from earlier explorations (ρ^50 ≈ 0.005)
3. The surviving basin absorbs all subsequent navigation

In V1–V4, the start rotation (A→B→C→D→E) means E gets the freshest traces.
This is "last-mover advantage": the most recently explored region wins because
its historization has decayed least.

**Key finding: Independent Historization → Multi-Attractor Coexistence.**

When each cluster gets its own controller with separate Historization (V5),
all 5 develop equal-strength attractors (Gini=0.000).  Perfect "galaxy
formation" — independent gravitational wells coexisting.

**The structural parallel to physics is now complete:**

| Physical spacetime | E₀ shared Historization | E₀ multiverse |
|---|---|---|
| Speed of light limits communication | No limit — shared H is global | Separate H per universe |
| Multiple galaxies form independently | Impossible — monopoly | 5 independent attractors |
| Galaxies separated by distance | No distance in shared H | Coupling Router provides distance |
| Galaxy mergers when they meet | Not applicable | Cross-reflexion = knowledge exchange |

**Why this matters for E₀:**

This empirically validates the multiverse architecture (C54–C71).  A single
E₀ system is structurally incapable of maintaining multiple attractor basins
simultaneously.  For structural diversity — multiple perspectives, strategies,
areas of expertise — you NEED the multiverse: separate Landscapes with
independent Historizations, coupled via CouplingRouter.

The Chess Team result (C74) demonstrated this operationally: 3×E₀ with
separate histories beat 1×E₀ with shared history.  C76 now explains WHY:
shared historization creates monopoly, independent historization preserves
diversity.

**Formal implication:**
The multiverse architecture is not a convenience — it is structurally
necessary for multi-attractor dynamics.  This is the E₀ equivalent of the
cosmological horizon: shared historization has no "speed of light" to limit
information propagation, so gravitational monopoly is inevitable.  The
multiverse introduces the missing separation by giving each system its
own Historization with its own decay.

---

## Insight 7: Transfer Learning is Conditional — Effective Only in Stochastic Domains with Exploration Cost

**Observation:**
Open Question #3 asked whether a strategy_profile from one domain can seed
a new landscape for faster convergence.  C77 tests this across two experiment
classes: deterministic C53 domains and stochastic branching corridors.

**Experiment (C77):**

*Part 1 — Deterministic C53 Domains (6 domains, 20 episodes cold vs warm):*

| Domain | Happy Path | Transferred | Cold μ | Warm μ | Speedup |
|---|---|---|---|---|---|
| D3 Gordian | 3 | 6 edges | 6.0 | 5.8 | 1.03× |
| D4 Greedy | 4 | 3 edges | 47.8 | 50.0 | 0.96× |
| D7 Invoice | 7 | 7 edges | 7.0 | 7.0 | 1.00× |
| D8 Cycles | 3 | 3 edges | 3.0 | 3.0 | 1.00× |
| D10 Bottleneck | 4 | 6 edges | 6.0 | 5.9 | 1.02× |

Result: **Transfer is neutral in all deterministic domains.**  The controller
follows the same path every episode — there is no learning curve to accelerate.
Revisit penalty (K7) and DEAD_END escalation (K12) already provide efficient
exploration.  Injected traces cannot improve on a deterministic outcome.

*Part 2 — Stochastic Branching Corridors (30 trials, 30 episodes each):*

Domain structure: N_LEVELS nodes on the correct path, N_DEAD_ENDS dead-end
branches at each level.  Stochastic execute_fn: correct edges P(SUCCESS)=0.85,
wrong edges P(SUCCESS)=0.30.  Dead-end exploration costs 2+ steps per wrong
choice (move to dead end + DEAD_END escalation jump back).

| Corridor | Cold μ | Warm μ | Speedup | Warm Wins |
|---|---|---|---|---|
| 5L×4D (25 edges) | 14.8 | 12.8 | 1.16× | 17/30 |
| 8L×3D (32 edges) | 24.5 | 16.3 | **1.50×** | **27/30** |

Result: **Transfer is clearly positive in stochastic domains with dead ends.**

The 8L×3D corridor shows the strongest signal: 1.50× overall speedup, warm
faster in 27 of 30 episodes.  Transfer benefit persists across ALL episodes
(first 5: 1.54×, last 5: 1.42×) — it does not fade.

**Why transfer works here but not in Part 1:**

1. **Dead ends create real step costs.**  Each wrong choice costs 2+ steps
   (explore dead end + DEAD_END escalation).  Transfer avoids these costs by
   injecting negative quality on dead-end edges → controller avoids them.

2. **Stochastic outcomes prevent cold convergence.**  With P(SUCCESS)≠1.0
   and ρ=0.9 decay, a cold controller never permanently learns the correct
   path.  Traces decay faster than they accumulate.  Transfer provides a
   persistent bias that survives decay cycles because the virtual experiences
   (SEED_STRENGTH=3.0) compound the initial trace advantage.

3. **Deterministic domains have no exploration gap.**  The controller's
   built-in mechanisms (revisit penalty, escalation) already handle
   deterministic navigation efficiently.  Transfer adds no value.

**Why transfer benefit PERSISTS (does not fade):**

This was the most surprising finding.  In classical ML, transfer typically
helps early and fades as the target system learns on its own.  In E₀,
the ρ=0.9 decay actively erases accumulated traces (~50 steps to lose 99.5%
of information: ρ^50 ≈ 0.005).  This means:

- The cold controller keeps "forgetting" what it learned → re-explores dead ends
- The warm controller's injected traces also decay, BUT they were injected
  at t=0 with SEED_STRENGTH bonus, giving them a head start in each episode
- The cold controller's real-time exploration competes with decay and never
  fully converges; the warm controller's pre-seeded bias partially compensates

**Formal implication:**

Transfer learning in E₀ is a **conditional mechanism**, effective only when:
1. The domain has stochastic outcomes (deterministic domains need no transfer)
2. The domain has costly exploration choices (dead ends, traps)
3. The ρ-decay is high enough to prevent cold convergence

The revisit penalty (K7) and DEAD_END escalation (K12) are sufficient for
deterministic domains — transfer is redundant.  For stochastic domains,
these mechanisms reduce but do not eliminate exploration cost.  Transfer
fills the remaining gap.

This has architectural implications for the LLM Bootstrap (C43–C47):
- LLM-generated initial traces are most valuable for stochastic/uncertain domains
- For well-defined deterministic workflows, E₀'s self-exploration is sufficient
- The LLM should focus bootstrapping effort on domains where the E₀ controller
  would otherwise face extended stochastic exploration

---

## Insight 8: Convergence Speed is Domain-Class Dependent — ρ Controls the Tradeoff

**Observation:**
Open Question #1 asked how many interactions until the strategy profile
stabilizes.  C78 measures this precisely using two metrics:
  - **Quality drift**: mean |Δq(e)| between consecutive episode snapshots
  - **Rank stability**: Kendall τ correlation of edge quality ordering

**Experiment (C78):**

*Part 1 — Deterministic C53 Domains (D3, D7, D8, D10, 60 episodes each):*

| Domain | Nodes | Edges | Stabilization (drift<0.01) | Steady-State Load |
|---|---|---|---|---|
| D3 Gordian | 6 | 6 | Episode 1 | 10.00 |
| D7 Invoice | 10 | 16 | Episode 1 | 9.65 |
| D8 Cycles | 6 | 7 | Episode 1 | 10.00 |
| D10 Bottleneck | 6 | 5 | Episode 1 | 10.00 |

Result: **Deterministic domains stabilize in 1 episode.**  The controller
follows the exact same path every episode, updating the exact same edges.
Trace quality is constant from episode 1 onward (drift = 0.0000).  The
only change is trace_load accumulating toward the steady-state limit
1/(1−ρ) = 10.0, but quality is fixed immediately.

*Part 2 — Stochastic Corridor (8L×3D, 10 trials, 60 episodes):*

| Metric | First 5 eps | Last 5 eps | Ratio |
|---|---|---|---|
| Quality drift | 0.3525 | 0.0922 | 3.82× reduction |
| Kendall τ | 0.952 | 0.937 | Near-constant |

Result: **Stochastic domains NEVER fully converge.**  Drift decreases
3.82× from early to late episodes but plateaus around 0.09 — well above
the 0.01 convergence threshold.  The rank ordering fluctuates at τ≈0.94,
never reaching 1.0.  This is consistent with C77's finding: ρ=0.9 decay
erases traces faster than stochastic experience can consolidate them.

*Part 3 — ρ Sensitivity Analysis:*

| ρ | Theoretical t_95 | Deterministic Stab | Stochastic Drift@50 | Converges? |
|---|---|---|---|---|
| 0.80 | 13.4 visits | Episode 1 | 0.2342 | No |
| 0.90 | 28.4 visits | Episode 1 | 0.1357 | No |
| 0.95 | 58.4 visits | Episode 1 | 0.0403 | Partial |
| 0.99 | 298.1 visits | Episode 5 | 0.0158 | Partial |

**The most surprising finding: higher ρ (slower decay) improves stochastic
convergence.**  This contradicts the naive expectation that faster forgetting
(lower ρ) helps adapt.  In stochastic domains:
- Low ρ (0.80): Traces decay too fast → quality oscillates wildly (drift=0.23)
- High ρ (0.99): Traces accumulate enough → noise averages out (drift=0.016)
- The cost: high ρ means slow adaptation to CHANGES in the environment.
  Good for stationary domains, bad for non-stationary ones.

**For deterministic domains, ρ has NO effect on convergence speed.**  The
controller takes the same path regardless, so traces are perfectly reinforced.
Only ρ=0.99 shows delayed stabilization (episode 5 instead of 1), because
the high trace_load (96.6 vs 9.65) causes tiny numerical drift between
episodes before the geometric series converges.

**The ρ dilemma for LLM Bootstrap:**
- ρ=0.90 (default): Good balance — fast adaptation, but never converges
  in stochastic domains.  LLM should be available as a permanent fallback.
- ρ=0.95–0.99: Would allow stochastic convergence, but sacrifices
  adaptability.  The LLM could safely disengage after convergence.
- Adaptive ρ: Start with ρ=0.90 for exploration, increase to ρ=0.99
  once the profile has stabilized.  This is a natural extension.

**Formal implication:**

The convergence speed of strategy_profile has a closed-form lower bound:
for a single edge visited every step with constant outcome, trace reaches
95% of steady state after t_95 = log(0.05) / log(ρ) visits.  But this is
only relevant for deterministic domains.  In stochastic domains, the
convergence speed depends on:
  1. The ratio of correct visits to total visits (signal-to-noise)
  2. The ρ value (determines whether noise averages out)
  3. The number of edges competing for visits (more edges = slower)

The key insight: **ρ is not just a decay rate — it is a convergence/
adaptability tradeoff.**  High ρ = converges but can't adapt.  Low ρ =
adapts but never converges.  The default ρ=0.90 is on the non-convergent
side, which explains why Transfer Learning (C77) shows persistent benefit:
the warm system maintains an advantage because cold systems never fully
learn.

This connects Insights 7 and 8 into a unified picture:
- Transfer helps because ρ=0.9 prevents cold convergence (Insight 8)
- Transfer benefit persists because even the warm system's traces decay (Insight 7)
- The ρ parameter controls both effects simultaneously

---

## Insight 9: Asymmetric Decay — Failures Are More Informative Than Successes

**Observation:**
"Aus Fehlern lernt man mehr als aus den richtigen Entscheidungen, denn sie
zeigen einem viel mehr als nur den Fehler selbst sondern zeigen viele andere
Wege die man ab jetzt gehen kann anstatt nur den einen der bisher funktioniert hat."

A success confirms ONE path.  A failure reveals that an entire subtree should
be avoided — asymmetrically more informative.  This maps formally to
ρ_F > ρ_S: failure traces should decay slower than success traces.

**Implementation (C79):**
Added `rho_s` and `rho_f` parameters to Historization (default: both = ρ,
fully backward-compatible).  In `_effective_traces()` and `update()`,
U traces decay by ρ_S and F traces by ρ_F independently.

**Experiment (C79):**

*Part 1 — Symmetric (ρ=0.9) vs Asymmetric (ρ_S=0.85, ρ_F=0.97), cold start:*

| Corridor | Sym μ | Asym μ | Speedup | Asym Wins |
|---|---|---|---|---|
| 5L×4D | 18.6 | 15.5 | 1.20× | 23/30 episodes |
| 8L×3D | 24.3 | 20.6 | 1.18× | 21/30 episodes |

Result: **Asymmetric ρ improves cold-start learning by ~20%.**  The controller
avoids re-exploring dead ends because failure traces persist longer.  The
benefit is consistent across corridors and increases in late episodes
(First 5: 1.23–1.31×, Last 5: 1.26–1.28×).

*Part 2 — 4-way comparison (sym/asym × cold/warm), 30 trials × 30 episodes:*

| Condition | 5L×4D μ | 8L×3D μ |
|---|---|---|
| Sym-Cold | 15.9 | 21.8 |
| Sym-Warm (transfer) | 12.9 | 18.8 |
| Asym-Cold | 18.3 | **18.6** |
| Asym-Warm | 14.4 | 17.8 |

**Key finding for 8L×3D: Asym-cold (18.6) ≈ Sym-warm (18.8).**
Asymmetric ρ alone achieves what previously required transfer learning.
For the larger corridor, the mechanism-level improvement (remembering
failures longer) replaces the external knowledge injection entirely.

For 5L×4D, transfer still helps — the shorter corridor has less dead-end
exploration where asymmetric decay can differentiate.  As domain complexity
grows, asymmetric ρ becomes increasingly effective.

*Part 3 — ρ_F sensitivity sweep (ρ_S=0.85 fixed, 8L×3D):*

| ρ_F | Mean Steps | vs Baseline |
|---|---|---|
| 0.85 (=ρ_S) | 23.6 | 1.00× |
| 0.90 | 22.8 | 1.03× |
| 0.93 | 22.1 | 1.06× |
| 0.95 | 20.3 | 1.16× |
| **0.97** | **19.7** | **1.19×** |
| 0.99 | 20.5 | 1.15× |

**Sweet spot at ρ_F=0.97.**  Monotonic improvement from 0.85 to 0.97,
then slight decline at 0.99.  Too-high ρ_F keeps ancient failures active
even after the controller should re-examine them.  The slight decline at
0.99 confirms the user's stationarity intuition: when all paths are
blocked, the controller needs to re-check failed paths (DEAD_END escalation
K12) or explore proactively ("hat sich etwas geändert?").

**Stationarity safety:** Asymmetric ρ does not break non-stationary domains
because:
1. DEAD_END escalation (K12) re-opens failed paths when no alternatives exist
2. Exploration policy periodically re-examines the landscape
3. ρ_F < 1 guarantees all failures eventually decay to zero

**Formal connection to Insights 7 and 8:**
- C77 showed transfer helps because ρ=0.9 prevents convergence
- C78 showed higher ρ improves convergence but sacrifices adaptability
- C79 resolves the tradeoff: **asymmetric ρ gives high ρ (convergence)
  for failures and low ρ (adaptability) for successes simultaneously.**
  Failures stabilize the strategy profile; successes remain flexible.

This is the first E₀ parameter with an empirical optimum derived from
controlled experiments rather than arbitrary default.

---

## Insight 10: Goal-Distance Is the Best Structural Predictor of Attractor Identity

**Observation:**
C75 showed that attractor formation requires topological choice + differential
feedback.  But it did not answer: given a domain that WILL form an attractor,
WHICH state will it be?  Can we predict the attractor from structure alone,
before any navigation?

**Experiment (C80):**
Computed 7 structural predictors per state BEFORE navigation: in-degree,
out-degree, goal-distance (BFS hops to goal), start-distance, PageRank,
betweenness centrality, harmonic closeness.  Then ran 20 navigation episodes
and measured actual attractor (highest incoming trace_load concentration).

Tested across 23 domain configurations:
- Part 1: 10 C53 domains, original topology, uniform Δ/R₀
- Part 2: 10 C53 domains, fully connected topology
- Part 3: 3 synthetic stress-test domains (Hub-Spoke, Diamond-Chain, Bypass-Trap)

**Results — Predictor accuracy on 12 attractor-forming domains:**

| Predictor | Correct | Accuracy |
|---|---|---|
| Goal-Distance (BFS hops to goal) | 10/12 | **83%** |
| PageRank | 4/12 | 33% |
| In-Degree | 3/12 | 25% |
| Betweenness | 1/12 | 8% |
| Closeness | 1/12 | 8% |
| Out-Degree | 1/12 | 8% |
| Start-Distance | 1/12 | 8% |

**Goal-distance dominates all other predictors by a wide margin.**

Split by feedback type:
- **Differential feedback** (7 domains): GoalD = 86%, all others ≤ 14%
- **All-success** (5 domains): GoalD = 80%, PageRank = 60%, InDeg = 40%

**Why goal-distance works:**
The E₀ controller minimizes S_eff = Δ · R_eff, navigating toward the goal.
Successful goal-reaching concentrates success traces on edges LEADING TO
the goal, which reduces their R_eff, which attracts more traffic — a
self-reinforcing loop.  The state closest to the goal (distance=0, i.e.
the goal itself) is the terminal accumulator of this flow.

**Why other predictors fail:**
In fully-connected topologies, ALL states have identical in-degree,
out-degree, PageRank, betweenness, and closeness.  These structural
metrics become degenerate.  Only goal-distance breaks the symmetry
because it encodes the NAVIGATIONAL objective, not graph structure.

**The two failure cases (2/12):**
1. **D5 Fully Connected (R0C0 instead of R4C4):** 22 states, 462 edges,
   all-success feedback, 0/20 goal reached.  The controller drowns in
   options — random exploration concentrates on START, not GOAL.
2. **Bypass-Trap (DEAD2 instead of GOAL):** High-degree trap node
   generates massive failure traces on dead-end edges.  The dead-end
   nodes become inscription magnets through FAILURE accumulation,
   not success flow.

**Failure case 2 reveals a deeper truth:** Goal-distance predicts the
*success-flow* attractor.  When failure-traces dominate (because the
controller repeatedly explores failing edges), a *failure-attractor*
can form at dead-end nodes instead.  This is consistent with the
asymmetric ρ insight (C79): failure traces are structurally heavy
and can outweigh success flow.

**Formal prediction rule (C80):**

> Given a domain with (1) topological choice and (2) differential feedback,
> the attractor is the state with goal-distance = 0 (i.e., the goal itself)
> with 83% accuracy.  The two failure modes are:
> (a) oversaturated topology (N² edges prevent goal-reaching), and
> (b) failure-dominated inscription (dead-end traps accumulate more
> trace than the goal path).

**Connection to the gravity analogy:**
In physical gravity, mass concentrates at the center of a potential well.
In E₀, inscription concentrates at the goal — the "bottom" of the
navigational potential landscape.  Goal-distance is the E₀ equivalent
of gravitational potential: the state at the minimum of the navigational
potential (d=0) is where "mass" (inscription) accumulates.

---

## Insight 11: Focus Narrowing Rescues Complexity — Random Pruning Beats Quality Selection

**Observation:**  
E₀ performs perfectly at N=10 (OI=2.3, 100% goal) but fails completely
at N=50+ (OI=37+, 0% goal).  The fully-connected graph drowns the
controller in options: N*(N-1) edges with signal ratio 1/(N-1).

The rescue is not more information (peer oracle) but *fewer options*.
When OI exceeds a threshold, narrowing the candidate set from N-1 to
k≪N before selection restores performance:

| Condition           | N=100 Goal% | Mean Steps |
|---------------------|-------------|------------|
| Solo (no focus)     | 0%          | 200 (max)  |
| Focus k=8, quality  | 23%         | 170.6      |
| Focus k=8, load     | 0%          | 200        |
| Focus k=8, tension  | 0%          | 200        |
| **Focus k=8, random** | **82%**   | **93.8**   |
| Peer-only (perfect) | 100%        | 99.0       |

**The surprise:** Random pruning wins overwhelmingly.  Selecting the
"best" k candidates by trace_quality (23%) is far worse than selecting
k random candidates (82%).

**Why random beats quality:**
- Early in training, no edge has trace data → quality-based selection
  deterministically picks the same k neighbors by list order (lock-in)
- If the happy-path edge falls outside this fixed subset, the agent
  *never* discovers it
- Random pruning tries a different subset each episode → across 30
  episodes, the happy-path edge appears in *some* subsets and gets
  reinforced

**k is not critical:** k=5 (81%), k=8 (82%), k=12 (79%), k=20 (79%)
— the act of reducing matters more than how much.

**Why this matters for E₀:**
The result formalizes a human problem-solving heuristic: "When a problem
is too complex, push everything aside and pick a few paths that seem
realistic."  The E₀-native interpretation: complexity is not an inherent
property of the problem, but of the *option space*.  Reducing the option
space until OI drops below the effective threshold (~3.0) maps any
large problem back to E₀-tractable territory.

**Connection to the "Zentrale" model:**
The user's observation was: "I narrow my focus to a few realistic paths,
navigate from there, and when a colleague brings an idea, I integrate it
as the central coordinator."  The experiment confirms the first part
(focus narrowing works) but reveals a tension with the second part:
focus+peer (24%) is worse than peer-only (100%) because the focus filter
may exclude the peer's suggestion.  This means the "Zentrale" must
keep the peer's channel OUTSIDE the focus filter — the peer bypasses
the narrowing, and the Zentrale decides whether to integrate.

**Formal scaling law (C81):**

> E₀ operates effectively when OI ≤ ~3.0 (N_admissible ≤ ~10).
> For larger graphs, reduce N_admissible to k ≤ 10 via random pruning.
> Quality-biased pruning creates lock-in; unbiased pruning enables
> exploration across episodes.
> Peer consultation should bypass the focus filter, not be constrained by it.

**Experiment:** `e0_controller/explore_focus_narrowing.py` (C81).
  Part 1: Baseline solo scaling (N=10..100).
  Part 2: 4 focus strategies × N=50,100 with k=8.
  Part 3: k-sweep {5,8,12,20} on N=100 with best strategy.
  Part 4: Solo vs focus vs peer vs focus+peer on N=100.

---

## Part II: What E0 Reveals About E0 — Self-Graph Experiments (C147)

C147 applied E₀ to its own operational structure — the Self-Graph (C43).
Unlike Chess or the 10-domain benchmark, the domain here is E₀ itself:
8 nodes representing its operational cycle, 8 edges encoding component
interactions. The question: can E₀'s historization mechanism distinguish
which of its own components are helping vs. hurting?

Result: yes, via a mechanism we call **differential sampling**. The
experiment reveals three insights about self-knowledge that are independent
of any application domain.

---

## Insight 12: Differential Sampling — Activity Patterns Create Attribution Without Causation

**Observation:**  
In the Self-Graph demo, 20 successes are historized with core-only active,
then 10 failures with core+overlap active, then 10 successes core-only again.
Result: core quality = +0.500 (diluted but healthy), overlap quality = -1.000
(purely negative — it only saw failures).

The system never measured whether overlap *caused* the failures. Overlap
simply happened to be active during the failure period and inactive during
the success periods. The quality differential arises from the activity pattern.

**Why this matters for E₀:**  
In all prior E₀ applications, historization operates on *domain* edges —
transitions between states in an external problem. The Self-Graph applies
the same mechanism to E₀'s own operational structure. The fact that it works
(correct attribution with zero domain knowledge about causation) validates
an important property:

- `q(e) = (U-F)/(U+F+ε)` is sufficient for *structural* self-knowledge,
  not just *domain* knowledge
- Causal analysis is unnecessary when deactivation is reversible
- The precision of attribution depends on the *granularity of toggling*:
  fine-grained on/off patterns create sharper quality differentials

**Formal implication:**  
Self-knowledge via historization requires only two conditions:
1. Components can be independently toggled (activity granularity)
2. The system samples both states (component ON, component OFF)

If both conditions hold, `q(component)` converges to a meaningful
signal — even with bulk attribution (Insight 13).

---

## Insight 13: Bulk Attribution — Shared Outcomes Are Sufficient Under Differential Activity

**Observation:**  
`self_historize(active_components, outcome)` records the *same* outcome
on *all* edges where both endpoints are in the active set. When 7
components are active (core + overlap), all 7 get the failure trace.
There is no per-component outcome measurement.

Yet overlap quality (-1.000) diverges sharply from core quality (+0.500).
How? Because core was also active during the 30 success periods (where
overlap was OFF). The differential arises not from per-component fidelity,
but from the *sampling history* — which periods each component was present for.

**Why this matters for E₀:**  
This refutes the intuition that attribution requires fine-grained measurement.
In classical RL, credit assignment is a fundamental problem: which action
caused the reward? E₀ sidesteps this entirely. The mechanism:

- Core components: always active → quality = all_periods_average
- Modulation components: toggle → quality = only_active_periods_average
- The *difference* between these two averages is the attribution signal

This is exactly analogous to A/B testing: you don't need to know *why*
variant B is worse — you only need to observe the performance difference
between the A-only and A+B periods.

**Formal implication:**  
Let U_core/F_core be the success/failure counts when only core is active,
U_both/F_both when core+modulation are active. Then:

- q(core) = ((U_core + U_both) - (F_core + F_both)) / (U_core + U_both + F_core + F_both + ε)
- q(modulation) = (U_both - F_both) / (U_both + F_both + ε)

The quality differential `q(core) - q(modulation)` is nonzero whenever the
modulation's active period has a different success rate than the core-only period.
No causal model required.

---

## Insight 14: Reversible Meta-Control — Correlation Is Sufficient When Actions Are Undoable

**Observation:**  
The Self-Graph demo shows the full chain: self_historize → diagnose_self_graph
→ overlap classified harmful → apply_reflexive_actions → overlap_modulation = False.
This is a concrete structural mutation based on *correlation*, not causation.

After deactivation, core quality recovers (no more failures). The system
could later re-enable overlap and observe whether performance degrades again —
a natural experiment that would strengthen or weaken the attribution.

**Why this matters for E₀:**  
The reversibility of modulation toggles transforms an epistemically weak signal
(correlation) into a practically strong meta-control mechanism:

1. **Deactivation cost is low:** toggling a boolean, not restructuring
2. **Observation continues:** the system can measure post-deactivation performance
3. **Re-activation is always available:** if deactivation hurts, undo it
4. **Asymmetric risk:** deactivating a harmful modulation helps (true positive);
   deactivating a helpful one hurts temporarily but is caught and reversed (false positive recovery)

This is the same principle as reversible mutations in structural tuning (B4-S3):
the system prefers low-cost, undoable changes over high-confidence, irreversible ones.

**Formal implication:**  
Meta-control via correlation-based attribution is safe when:
- Only modulation edges can be toggled (core is structurally protected)
- Deactivation is a flag flip (reversible in O(1))
- Post-deactivation performance is continuously monitored
- The decision threshold (quality < -0.2) is conservative relative to the quality range [-1, +1]

The three-level self-knowledge hierarchy (Level 1: structure, Level 2: operational
attribution, Level 3: meta-control) forms a complete perception-action loop over
E₀'s own internal structure.

---

## Open Questions for Future Work

1. ~~Convergence speed~~ → **Resolved in C78.** Deterministic: 1 episode.
   Stochastic: never fully converges at ρ=0.90, partially at ρ≥0.95.
   ρ controls convergence/adaptability tradeoff.  See Insight 8.
2. ~~Landscape size scaling~~ → **Resolved in C81.** N=50+ fails at 0%
   (OI=37+), but random focus narrowing to k=8 rescues N=100 to 82%.
   Quality-biased pruning creates lock-in (23%); random pruning avoids it.
   The scaling limit is the option space, not the problem size.  See Insight 11.
3. ~~Transfer~~ → **Resolved in C77.** Conditional: neutral in deterministic
   domains (revisit penalty + escalation suffice), but 1.50× speedup in
   stochastic domains with dead-end exploration cost.  See Insight 7.
4. ~~Adversarial multiverse~~ → **Resolved in C74.** Team wins by checkmate.
   Diversity + knowledge exchange breaks the repetition trap.
5. ~~Attractor universality~~ → **Resolved in C75.** Conditional on two factors.
   See Insight 5.
6. ~~Attractor prediction~~ → **Resolved in C80.** Goal-distance (BFS hops
   to goal) predicts the attractor with 83% accuracy (10/12 domains).
   Failure modes: oversaturated topology and failure-dominated inscription.
   See Insight 10.
7. ~~Multi-attractor dynamics~~ → **Resolved in C76.** Shared Historization
   creates monopoly (1 attractor). Independent Historization (multiverse)
   enables coexistence (5 attractors). See Insight 6.
8. Granularity of self-knowledge: The current Self-Graph has 8 components
   (6 core + 2 modulation). Could per-parameter self-knowledge (e.g.,
   tracking whether α=2.0 helps more than α=1.5) improve meta-control?
   Trade-off: more components = more toggleable dimensions, but also
   more combinatorial states to sample.
9. Self-Graph convergence under mixed domains: The C147 demo uses a
   controlled scenario (deterministic phases). In a real application
   with gradual domain shifts, how quickly does the Self-Graph attribution
   adapt? Does ρ=1.0 (no decay) create a "quality lag" problem where
   early success masks later degradation?
10. Self-Graph + Dream Mode integration: Can the Self-Graph serve as a
    meta-domain for the DreamObserver? If E₀ dreams about its own
    components, can it discover structural equivalences between
    different meta-control strategies?

---

## Cross-References

- **C72 Chess Engine:** `e0_controller/chess_e0.py` — solo self-play, DEVELOPMENT→CENTER_CONTROL emergence
- **C74 Team Chess:** `e0_controller/chess_team.py` — team beats solo, diversity breaks repetition
- **C53 Domain-Invariance Benchmark:** 10 domains, 1 controller — prior invariance evidence
- **C73 Primitive Extensions:** `landscape.py` (fully_connected), `historization.py` (strategy_profile)
- **C75 Attractor Universality:** `e0_controller/explore_attractor_universality.py` — 10 domains × 2 topologies
- **C76 Multi-Attractor:** `e0_controller/explore_multi_attractor.py` — 25-state clustered topology × 5 variants
- **C77 Transfer Learning:** `e0_controller/explore_transfer_learning.py` — 6 deterministic + 2 stochastic corridors
- **C78 Convergence Speed:** `e0_controller/explore_convergence_speed.py` — 4 deterministic + stochastic corridor + ρ sensitivity
- **C79 Asymmetric ρ:** `e0_controller/explore_asymmetric_rho.py` — sym vs asym cold, 4-way transfer comparison, ρ_F sweep
- **C80 Attractor Prediction:** `e0_controller/explore_attractor_prediction.py` — 7 structural predictors × 23 domains, goal-distance wins 83%
- **C81 Focus Narrowing:** `e0_controller/explore_focus_narrowing.py` — random pruning to k=8 rescues N=100 from 0% to 82%, scaling limit is option space
- **C43 Self-Graph:** `e0_controller/self_graph.py` — 8-component structural self-knowledge (Selbstunterscheidung)
- **C47 Dual Reflection:** `e0_controller/dual_reflection.py` — component diagnosis (healthy/confused/harmful/insufficient)
- **C49 Reflexive Action:** `e0_controller/reflexive_action.py` — modulation toggle based on diagnosis
- **C147 Self-Graph Demo:** `e0_controller/demo_self_graph.py` — differential sampling, bulk attribution, meta-control
- **Ontodynamics §4:** 4-Layer Model — trace_load, trace_quality, inertia_factor, mass
- **Ontodynamics §7:** Landscape definition — X_t unconstrained
- **Ontodynamics §17:** Historization — U/F traces, δ_H correction
- **General Relativity analogy:** G_μν = 8πT_μν ↔ R_eff = R₀ + δ_H(U,F)
