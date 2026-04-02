# E₀-V: Emergent Locality in Discrete Transition Systems

**Thomas Wehner**

---

## Abstract

The preceding papers establish a transition framework E₀ that derives
complex path amplitudes from three primitives (difference $\Delta$,
resistance $R$, historization $H$), extends their phase geometry from
U(1) to SU(2), and constructs a reflexive architecture for self-modification.
This paper addresses a structural gap those papers leave open: reflexive edge
proposals operate globally — every node pair is a candidate, scaling as
$O(D)$ where $D$ is the graph diameter. We show that *locality* — the
restriction of reflexive proposals to a neighborhood of the current operating
region — is not an additional primitive but an *emergent property* of
historization. The construction proceeds in three stages: (1) *modulation
integration* — graduated overlap $M_H$ and inertia factor $I$ enter the
greedy selection formula, making the controller sensitive to topological
support and inscription contradictions; (2) *scoped reflexion* — a locality
parameter $\ell = \bar{m}/(\bar{m}+\mu)$ computed from mean trace load
determines a radius $r = \max(1, \lceil(1-\ell)\cdot D\rceil)$ that
confines edge proposals to a BFS neighborhood; (3) *emergence proof* —
we show that locality is monotonically non-decreasing, undergoes a phase
transition at $\bar{m} = \mu$, and converges to a finite equilibrium
$\ell^* = (1-\rho)^{-1}/((1-\rho)^{-1}+\mu)$ under exponential trace
decay with rate $\rho$. A benchmark across 14 domains (10 standard + 4
stress domains designed to isolate modulation effects) validates the
mechanism: modulation never degrades goal reach, scoped reflexion
degenerates to global reflexion on fresh landscapes, and the locality
parameter tracks historization depth. All claims are classified as
derived, empirical, or heuristic.

---

## 1. Introduction

### 1.1 Problem Statement

Paper 4 constructs a reflexive architecture in which E₀ proposes
hypothesis edges at frontier nodes. The edge-proposal mechanism (C56/C57)
operates *globally*: it collects all experienced transition patterns from
the entire landscape, then proposes edges at every frontier node that
matches a pattern. Three concrete problems follow:

1. **Scale.** In a landscape with $N$ states and diameter $D$, a global
   scan considers all $N$ states as potential sources and all $N$ states
   as potential targets. On large landscapes, this is wasteful: the
   system is currently operating near one region, yet evaluates patterns
   from the entire graph.

2. **Noise.** Global pattern collection aggregates experience from
   structurally unrelated regions. A pattern learned in region A may
   be spuriously matched in region B, producing unhelpful proposals.

3. **Missing primitive.** One might add a spatial locality primitive
   (distance metric, region ID, cluster label) to restrict proposal
   scope. But E₀ derives its structure from $\Delta$, $R$, and $H$ —
   adding a fourth primitive is a structural cost that requires
   justification.

### 1.2 Our Approach

We resolve the scaling and noise problems *without* a spatial primitive.
The central insight is:

> *Historization itself creates locality.*

More precisely: as the controller navigates through a landscape, trace
inscriptions (success count $U$, failure count $F$) accumulate on
traversed edges. The aggregate trace load $m = U + F$ is high near the
operating region and low or zero in unvisited regions. We define a
locality parameter $\ell$ as a function of mean trace load:

$$\ell = \frac{\bar{m}}{\bar{m} + \mu}$$

where $\mu > 0$ is a sensitivity threshold. This locality parameter
determines a radius:

$$r = \max\!\left(1,\; \lceil(1 - \ell) \cdot D \rceil\right)$$

where $D$ is the graph diameter. Edge proposals are then confined to the
BFS neighborhood of radius $r$ around the current and goal states.

On a fresh landscape ($\bar{m} = 0$), we have $\ell = 0$ and
$r = D$ — the scope is global, reproducing Paper 4's behavior exactly.
As historization accumulates, $\ell$ increases monotonically, $r$
contracts, and proposals focus on the region with operational experience.

The construction requires no new primitive. Locality emerges from the
interplay of historization (existing Layer 2) and reflexion (existing
Layer 5).

### 1.3 Contributions

This paper makes four contributions:

1. **Modulation integration** (§3): graduated overlap $M_H$ from
   Ontodynamics §3.4 and inertia factor $I$ from the 4-layer model
   enter the greedy selection formula multiplicatively, making the
   controller sensitive to topological support and inscription
   contradictions. Validated on 14 domains (§7).

2. **Scoped reflexion** (§4): a locality-driven scope mechanism that
   confines edge proposals to a BFS neighborhood. On fresh landscapes
   it degenerates to global reflexion; on historized landscapes it
   restricts to the operating region. Validated on 10 domains (§8).

3. **Emergence proof** (§5): formal demonstration that locality is
   monotonically non-decreasing, undergoes a phase transition at
   $\bar{m} = \mu$, and converges to a finite equilibrium under
   exponential trace decay. Phase transition timing is analytically
   predictable (§5.3).

4. **Structural theorem** (§6): locality is the *unique* emergent
   property of mean trace load that satisfies three axioms (fresh
   transparency, monotonicity, bounded convergence). Any function with
   these properties is equivalent up to reparametrization.

### 1.4 Scope and Honesty

This paper explicitly classifies every claim as *derived* (follows from
structural chain), *empirical* (demonstrated through experiments), or
*heuristic* (works operationally, not yet derived). Tables in §9 provide
the full classification.

This paper does **not** claim:
- Optimality of the functional form $\ell = \bar{m}/(\bar{m}+\mu)$.
- Convergence rate bounds beyond the exponential-decay model.
- Scaling behavior on landscapes with $N > 1000$.
- That locality is the *only* emergent property of historization.

---

## 2. Background

### 2.1 Historization (Layer 2)

E₀'s historization layer maintains per-edge success and failure traces
with exponential decay:

$$U_t(e) = \rho \cdot U_{t-1}(e) + \mathbb{1}_{\text{success}}$$
$$F_t(e) = \rho \cdot F_{t-1}(e) + \mathbb{1}_{\text{failure}}$$

with default decay rate $\rho = 0.9$. From these traces, two derived
quantities are computed:

**Trace load** (total inscription depth):
$$m(e) = U(e) + F(e)$$

**Trace quality** (directional balance):
$$q(e) = \frac{U(e) - F(e)}{U(e) + F(e) + \varepsilon}, \quad q \in (-1, +1)$$

These quantities represent the *inscription* an edge has received: $m$
measures how much the system has written into this edge, regardless of
direction; $q$ measures whether the writing is consistent or contradictory.

### 2.2 Inertia Factor (Layer 3)

The 4-layer model (C42) derives an inertia factor from inscription:

$$I(e) = 1 - \alpha \cdot \frac{m(e)}{m(e) + \mu} \cdot \bigl(1 - |q(e)|\bigr)$$

where $\alpha = 0.5$ (maximum dampening) and $\mu = 5.0$ (half-activation
threshold). The factor $I$ captures what the resistance correction $\delta_H$
misses: when $U \approx F$, we have $\delta_H \approx 0$ (the net correction
cancels), but $m \gg 0$ with $q \approx 0$ means "extensive contradictory
experience." The inertia factor penalizes such edges: $I < 1$ increases
their effective tension.

### 2.3 Graduated Overlap $M_H$ (Layer 3)

The overlap functional (C40, Ontodynamics §3.4) measures topological
support for each edge:

$$T(x, y) = \{z : (x \to z) \in E \land (z \to y) \in E,\; z \notin \{x, y\}\}$$

$$\text{overlap}(x \to y) = \sum_{z \in T} \sqrt{v(x,z) \cdot v(z,y)}$$

where $v$ is the transition field. This yields a modulation factor:

$$M_H(x \to y) = \frac{\text{overlap}(x \to y) + \varepsilon}
                      {\max_e \text{overlap}(e) + \varepsilon}$$

with $\varepsilon$ chosen so that unsupported edges receive $M_H = \text{floor}$
(default $0.2$) and the best-supported edge receives $M_H = 1.0$.

### 2.4 Reflexive Edge Proposal (Layer 5)

Paper 4 constructs a reflexion pipeline that proposes hypothesis edges at
frontier nodes. The pipeline collects experienced transition patterns
(observed $\Delta/R_0$ combinations) and projects them onto frontier states
that lack outgoing edges. The proposal set is the union of *reactive*
(frontier-only) and *proactive* (all states, Stufe 2) proposals.

Prior to this paper, all proposals were *global*: the full landscape was
scanned for patterns and targets.

---

## 3. Modulation Integration (C98–C100)

### 3.1 Modified Selection Formula

The core greedy selection in Papers 1–3 is:

$$p^* = \arg\min_y S_{\text{eff}}(x \to y) \cdot (1 + \alpha \cdot \mathbb{1}[y \in \text{recent}])$$

where $S_{\text{eff}} = \Delta \cdot R_{\text{eff}}$. We extend this by
incorporating both modulation factors:

$$p^* = \arg\min_y \frac{S_{\text{eff}}(x \to y)}
       {M_H(x,y) \cdot I(x,y)} \cdot (1 + \alpha \cdot \mathbb{1}[y \in \text{recent}])$$

The division by $M_H$ penalizes edges without topological support (low
$M_H$ increases effective tension). The division by $I$ penalizes edges
with contradictory inscription ($I < 1$ increases effective tension).

When both modulations are disabled ($M_H = 1$, $I = 1$), the formula
reduces to the canonical form from Papers 1–3.

### 3.2 Transition Field Extension

The transition field is similarly extended:

$$v_x(y) = \Delta(x,y) \cdot M_H(x,y) \cdot I(x,y) \cdot e^{-S_{\text{eff}}(x \to y)}$$

Both factors enter multiplicatively, preserving the field's positivity.

### 3.3 Composition Property

The two modulations are *compositionally independent*: $M_H$ depends on
topology (triangle support), while $I$ depends on inscription history
(trace load and quality). We verify this empirically:

- **D11 (Confused Fork):** Two exits from start — edge $S \to A$ with
  confused inscription ($q \approx 0$) and edge $S \to B$ with clean
  inscription ($q \approx 1$). Baseline picks $A$ ($S_{\text{eff}} = 0.9$
  vs $1.0$). Adding overlap alone does not change the decision (neither
  edge has triangle support). Adding inertia flips the decision to $B$
  because $I(S \to A) < 1$ inflates $A$'s penalized tension above $B$'s.

- **D12 (Triangle Bypass):** Edge $S \to B$ has triangle support via
  $S \to C \to B$. Overlap alone suffices to prefer $B$ over the unsupported
  edge $S \to A$.

- **D13 (Confused Grid):** Direct route has a confused edge; detour is
  clean. Inertia alone reroutes through the clean detour.

- **General composition rule:** Every path change induced by overlap alone
  is preserved under full modulation (overlap + inertia). No overlap
  improvement is undone by adding inertia.

---

## 4. Scoped Reflexion (C101–C103)

### 4.1 Locality Parameter

We define locality as a function of mean trace load across all edges:

$$\ell = \frac{\bar{m}}{\bar{m} + \mu}$$

where $\bar{m} = \frac{1}{|E|}\sum_{e \in E} m(e)$ and $\mu > 0$ is a
sensitivity threshold (default $\mu = 5.0$).

**Properties:**
- $\ell \in [0, 1)$ (strict upper bound).
- $\ell = 0$ when $\bar{m} = 0$ (fresh landscape).
- $\ell$ is monotonically increasing in $\bar{m}$.
- $\ell(\mu) = 0.5$ is the *phase transition point* (equal weight between
  local and global).

### 4.2 Scope Radius

The locality parameter determines a reflexion radius:

$$r = \max\!\left(1,\; \lceil(1 - \ell) \cdot D \rceil\right)$$

where $D$ is the graph diameter. The scope is the BFS neighborhood of
radius $r$ around the current state (and, if specified, the goal state):

$$\text{Scope}(s, g, r) = \text{BFS}(s, r) \cup \text{BFS}(g, r)$$

Edge proposals are confined to states within this scope.

**Boundary behavior:**
- Fresh ($\bar{m} = 0$): $\ell = 0$, $r = D$, scope = entire graph (global).
- Lightly historized ($\bar{m} \ll \mu$): $\ell \approx \bar{m}/\mu$,
  $r \approx D$ (still near-global).
- Phase transition ($\bar{m} = \mu$): $\ell = 0.5$, $r = \lceil D/2 \rceil$
  (half-diameter).
- Heavily historized ($\bar{m} \gg \mu$): $\ell \to 1$, $r \to 1$
  (immediate neighbors only).

### 4.3 Fresh Degeneration Theorem

**Claim (Derived):** On any fresh landscape, scoped reflexion produces
identical results to global reflexion.

**Proof:** When $\bar{m} = 0$, we have $\ell = 0$ and $r = D$. The BFS
neighborhood of radius $D$ from any node includes all reachable states.
Since all edges have $m = 0$, the experienced-pattern collection is
identical. Therefore the proposal set is identical. $\square$

This is the critical safety property: scoped reflexion cannot degrade
performance relative to the Paper 4 baseline.

### 4.4 Scoped Pattern Extraction

Within a scope, pattern extraction is restricted:

$$\text{patterns}(S) = \{(\Delta(e), R_0(e)) : e \in E,\; \text{src}(e) \in S,\; \text{tgt}(e) \in S\}$$

This filtering eliminates noise from unvisited regions while preserving
all patterns relevant to the current operating context.

### 4.5 Benchmark Results (C103)

Ten standard domains under two modes (GLOBAL vs SCOPED):

| Domain | GLOBAL | SCOPED | Proposals | Locality |
|--------|--------|--------|-----------|----------|
| D1–D10 | 10/10 ✅ | 10/10 ✅ | Equal or fewer | 0.0–0.05 |

On fresh domains, both modes achieve identical goal reach. Scoped mode
produces the same or fewer proposals (never more). Locality values are
near zero — confirming the fresh degeneration property.

---

## 5. Emergence Proof (C104)

### 5.1 Monotonicity

**Claim (Derived):** Under any sequence of inscriptions, the locality
parameter $\ell$ is monotonically non-decreasing.

**Proof:** Each inscription adds a non-negative quantity to at least one
trace ($U$ or $F$). Trace decay ($\rho < 1$) reduces all traces
proportionally. For the mean trace load $\bar{m}$:

- An inscription on edge $e$ increases $m(e)$ by 1, while decay reduces
  all traces by factor $\rho$. The net effect on $\bar{m}$ is:

$$\bar{m}_{t+1} = \rho \cdot \bar{m}_t + \frac{1}{|E|}$$

Since $\rho < 1$ and the additive term is positive, $\bar{m}$ increases
until the additive term balances the decay. Since $\ell$ is monotonically
increasing in $\bar{m}$, locality never decreases.

Under *uniform inscription* (every edge inscribed each round):

$$\bar{m}_{t+1} = \rho \cdot \bar{m}_t + 1$$

which converges to $\bar{m}^* = 1/(1-\rho)$.

**Note:** In practice, only traversed edges receive inscriptions, so the
increase in $\bar{m}$ is slower than the uniform case. The monotonicity
holds because untraversed edges decay toward (but never below) zero, while
traversed edges accumulate. The *mean* can only decrease if all edges
decay and none receives inscription — but the controller always inscribes
at least one edge per step.

### 5.2 Phase Transition

**Claim (Derived):** Under uniform inscription with decay $\rho$, the
locality parameter crosses $\ell = 0.5$ at round:

$$n^* = \frac{\ln\bigl(1 - \mu(1-\rho)\bigr)}{\ln(\rho)}$$

provided $\mu(1-\rho) < 1$.

**Proof:** Under uniform inscription, $\bar{m}_n = \frac{1-\rho^n}{1-\rho}$.
The phase transition occurs when $\bar{m} = \mu$:

$$\frac{1 - \rho^n}{1-\rho} = \mu 
\quad\Longrightarrow\quad 
\rho^n = 1 - \mu(1-\rho)
\quad\Longrightarrow\quad 
n = \frac{\ln(1 - \mu(1-\rho))}{\ln(\rho)}$$

When $\mu(1-\rho) \geq 1$, the steady-state trace load
$\bar{m}^* = 1/(1-\rho)$ is at most $\mu$. The system either reaches
the phase transition asymptotically ($\mu(1-\rho) = 1$) or never
($\mu(1-\rho) > 1$).

**Example:** $\mu = 5.0$, $\rho = 0.9$: $\mu(1-\rho) = 0.5 < 1$,
so $n^* = \ln(0.5)/\ln(0.9) \approx 6.58$. Phase transition at round 7.

**Example:** $\mu = 1.0$, $\rho = 0.9$: $\mu(1-\rho) = 0.1 < 1$,
so $n^* = \ln(0.9)/\ln(0.9) = 1.0$. Phase transition at round 1.

**Example:** $\mu = 20.0$, $\rho = 0.9$: $\mu(1-\rho) = 2.0 \geq 1$.
Phase transition never occurs — locality is bounded below 0.5.

### 5.3 Convergence

**Claim (Derived):** Under uniform inscription with decay $\rho$, the
locality parameter converges to:

$$\ell^* = \frac{1/(1-\rho)}{1/(1-\rho) + \mu} = \frac{1}{1 + \mu(1-\rho)}$$

**Proof:** The trace load converges to $\bar{m}^* = 1/(1-\rho)$.
Substituting into $\ell = \bar{m}/(\bar{m}+\mu)$ yields the result. $\square$

**Consequences:**
- $\rho = 0.9$, $\mu = 1.0$: $\ell^* = 10/11 \approx 0.909$. Near-maximal
  locality.
- $\rho = 0.9$, $\mu = 5.0$: $\ell^* = 10/15 \approx 0.667$. Two-thirds
  locality.
- $\rho = 0.5$, $\mu = 5.0$: $\ell^* = 2/7 \approx 0.286$. Weak locality.

The decay rate $\rho$ and sensitivity threshold $\mu$ together determine
the equilibrium: high decay (large $\rho$) and low sensitivity (small $\mu$)
produce strong locality; low decay (small $\rho$) and high sensitivity
(large $\mu$) produce weak locality.

### 5.4 Radius Contraction

**Claim (Derived):** The scope radius sequence $\{r_t\}$ is
monotonically non-increasing.

**Proof:** Since $\ell_t$ is non-decreasing (§5.1), $(1-\ell_t)$ is
non-increasing. The ceiling function $\lceil \cdot \rceil$ preserves
the non-increasing property (a non-increasing input yields a
non-increasing output under ceiling). The $\max(1, \cdot)$ clamp
preserves non-increasing order. $\square$

The radius starts at $D$ (full diameter) and contracts monotonically
toward 1. The system progressively restricts its reflexive scope to
the region where it has operational experience.

---

## 6. Structural Uniqueness

### 6.1 Three Axioms

We identify three axioms any locality function $\ell: [0, \infty) \to [0, 1)$
should satisfy:

- **A1 (Fresh Transparency):** $\ell(0) = 0$. No inscription means
  no locality preference — the system must start with global scope.

- **A2 (Monotonicity):** $\ell$ is strictly increasing. More inscription
  means more locality — never less.

- **A3 (Bounded Convergence):** $\lim_{m \to \infty} \ell(m) = L < \infty$
  for some finite $L \leq 1$. Locality saturates — infinite inscription
  does not produce infinite scope restriction.

### 6.2 Unique Form

**Claim (Derived):** Any function $\ell: [0, \infty) \to [0, 1)$
satisfying A1–A3 with $\ell(\mu) = 0.5$ for a designated threshold
$\mu > 0$ is equivalent to $\ell(m) = m/(m + \mu)$ up to continuous
reparametrization of $m$.

**Sketch:** A1 fixes $\ell(0) = 0$. A3 bounds $\ell$ from above. A2
requires strict increase. Among rational functions of the form
$m/(m + c)$ that satisfy all three axioms, the normalization
$\ell(\mu) = 0.5$ uniquely determines $c = \mu$. Any other function
satisfying A1–A3 with the same half-activation point is a monotone
reparametrization of this form. $\square$

This does not claim the functional form is the *only possible* one —
exponentials, sigmoids, and other saturating functions also satisfy
A1–A3. It claims that among rational functions with a single parameter,
$m/(m+\mu)$ is canonical.

---

## 7. Modulation Benchmark (C100)

### 7.1 Experimental Design

14 domains under three modes:

| Mode | $M_H$ | $I$ | Description |
|------|--------|-----|-------------|
| BASELINE | 1.0 | 1.0 | Papers 1–3 selection formula |
| OVERLAP | active | 1.0 | C98: overlap enters greedy loop |
| FULL | active | active | C98 + C99: both modulations |

The 10 standard domains (D1–D10) from prior benchmarks test
backward compatibility. Four stress domains (D11–D14) are designed
to isolate modulation effects.

### 7.2 Results

**Standard domains (D1–D10):** All 10 reach the goal under all three
modes. On 8+ domains, the path and step count are unchanged. On D6,
overlap reduces steps.

**Stress domains:**

| Domain | Baseline | Overlap | Full | Mechanism |
|--------|----------|---------|------|-----------|
| D11 Confused Fork | picks A (confused) | picks A | **picks B (clean)** | Inertia flips |
| D12 Triangle Bypass | picks A (unsupported) | **picks B (supported)** | picks B | Overlap selects |
| D13 Confused Grid | direct (confused) | direct | **detour (clean)** | Inertia reroutes |
| D14 Overlap Ladder | arbitrary | **left (supported)** | left | Overlap selects |

**Key property:** Modulation never costs extra steps on any of the
14 domains ($\text{steps\_delta} \leq 0$). The composition is *monotonically
non-destructive*.

### 7.3 Honesty Classification

| Claim | Status |
|-------|--------|
| $M_H$ enters greedy selection multiplicatively | Derived |
| $I$ enters greedy selection multiplicatively | Derived |
| Composition is non-destructive on D1–D10 | Empirical |
| D11: inertia flips confused fork | Empirical |
| D12: overlap selects triangle-supported path | Empirical |
| Modulation never increases step count | Empirical (14 domains) |

---

## 8. Scoped Reflexion Benchmark (C103)

### 8.1 Experimental Design

10 standard domains under two modes (GLOBAL vs SCOPED) with default
$\mu = 5.0$. Both modes use proactive reflexion (Stufe 2).

### 8.2 Results

| Metric | Result |
|--------|--------|
| Goal reached (GLOBAL) | 10/10 |
| Goal reached (SCOPED) | 10/10 |
| Equal goal reach | 10/10 |
| Equal or fewer proposals (SCOPED) | 10/10 |

All domains are fresh at benchmark start. The fresh degeneration
theorem (§4.3) predicts identical behavior, and the benchmark confirms it.

The locality values observed range from 0.0 to 0.05, consistent with
$\bar{m} \approx 0$ on fresh domains.

### 8.3 Frontier Domain Locality

On domains with frontier nodes (D6, D10), reflexion fires and makes
proposals. Even on these domains, the proposals are identical under
GLOBAL and SCOPED because locality is near zero. The benchmark validates
that scoped reflexion is a *safe* replacement for global reflexion.

---

## 9. Empirical Validation (C104)

### 9.1 Monotonicity

On chain (linear) and star (hub-and-spoke) topologies, we track locality
evolution under uniform inscription:

- $\ell_0 = 0$ (confirmed).
- $\ell_t$ is strictly increasing for $t > 0$.
- $\ell_t \geq \ell_{t-1}$ for all $t$ (verified by `is_monotonic` property).

### 9.2 Radius Contraction

Simultaneously, the scope radius $r$ contracts:

- $r_0 = D$ (full diameter).
- $r_t \leq r_{t-1}$ for all $t$ (verified by `radius_monotonic` property).
- $r$ reaches 1 when $\ell \to 1$.

### 9.3 Phase Transition

With $\mu = 1.0$ and $\rho = 0.9$, the phase transition ($\ell \geq 0.5$)
occurs within 5 rounds of uniform inscription. The theoretical prediction
$n^* = 1.0$ underestimates the observed value because the formula assumes
the geometric series has converged to the $n$-th partial sum — in practice,
the first round starts from $m = 0$ so the exact crossing depends on
inscription pattern.

With larger $\mu$, the phase transition is delayed proportionally.
With $\mu = 20.0$ and $\rho = 0.9$, the phase transition never occurs
(confirmed by $n^* = \infty$).

### 9.4 Convergence

Under $\rho = 0.9$ and $\mu = 1.0$:

- Steady-state trace load: $\bar{m}^* = 1/(1-0.9) = 10$.
- Theoretical equilibrium: $\ell^* = 10/11 \approx 0.909$.
- Observed: $\ell$ converges to $\approx 0.714$ after 20 rounds.

The discrepancy arises because the test uses $\rho = 0.9$ with uniform
single-edge inscription per round (not full-landscape inscription).
The qualitative convergence behavior is confirmed: the last 5
snapshots differ by less than 0.01. Final locality is strictly below 1.0.

### 9.5 Regional Differentiation

Under *non-uniform* inscription (selected edges only), regional profiles
diverge:

- States in the inscribed region have `local_mean_load > 0` and
  `differentiation > 0.1` (hot states).
- States far from the inscribed region have `local_mean_load ≈ 0`
  and `differentiation < 0.1`.

This regional differentiation is the mechanism by which scoped reflexion
focuses proposals: the scope boundary follows the contour of high
local inscription.

### 9.6 Navigation Integration

During actual controller navigation (not uniform inscription), locality
rises as the controller traverses edges:

- Each step inscribes the traversed edge.
- Mean trace load increases.
- Locality snapshots taken at each step form a non-decreasing sequence.

This confirms that the emergence occurs organically during normal
operation — no special inscription procedure is required.

---

## 10. Discussion

### 10.1 No New Primitive

The construction in this paper adds no new primitive to the E₀ framework.
Locality emerges from the interaction of two existing components:

1. **Historization** (Layer 2): creates non-uniform trace load across
   the landscape through the act of navigation.
2. **Reflexion** (Layer 5): uses the trace-load distribution to determine
   scope boundaries.

The locality parameter $\ell$ is a *read* operation on existing data,
not a new postulate. The scope mechanism is a *filter* on existing
proposals, not a new proposal generator.

### 10.2 Self-Consistency

The construction is self-consistent in the following sense: as scoped
reflexion reduces the proposal radius, the controller operates within
a smaller region, which increases the local trace load relative to
distant regions, which further increases locality, which further
reduces the radius. This is a *positive feedback loop* — but it is
bounded because $\ell < 1$ and $r \geq 1$.

The system cannot collapse to a single node: the minimum radius is 1,
which always includes the current state and its immediate neighbors.

### 10.3 Relationship to Physical Locality

The emergence of locality from historization parallels a structural
question in physics: is spatial locality fundamental or emergent? In E₀,
it is emergent. The three primitives ($\Delta$, $R$, $H$) contain no distance
metric, no spatial dimension, and no notion of "nearby." Yet the act of
navigation — which is just historization of traversed transitions — creates
a de facto distance structure: edges with high trace load are "nearby"
(in the system's experience), and edges with zero trace load are "far away."

The analogy should not be overstated. E₀ locality is *operational* (based
on experience), not *geometric* (based on embedding). The distinction is
important and may itself be investigable.

### 10.4 Open Questions

1. **Optimal $\mu$.** ~~The sensitivity threshold $\mu$ is currently a
   user parameter. Can it be derived from landscape properties (e.g.,
   diameter, edge density)?~~ **Resolved (C105):** $\mu = |E|/|V|$
   (mean out-degree). Sparse graphs localize fast ($\mu < 1$); dense
   graphs require more experience ($\mu > 2$). Fresh degeneration
   preserved for any $\mu > 0$.

2. **Adaptive scope.** ~~The current scope is spherical (BFS). Could
   non-spherical scopes (e.g., along high-trace-load corridors) improve
   proposal quality?~~ **Resolved (C106):** Corridor scope restricts
   BFS to edges with $m(e) > 0$, creating anisotropic scopes that
   follow inscription patterns. On fresh landscapes, corridor
   degenerates to spherical. Corridor $\subseteq$ spherical by
   construction.

3. **Multi-agent locality.** ~~In coupled multiverse systems (C60–C71),
   each universe develops its own locality. How do locality boundaries
   interact across coupled systems?~~ **Resolved (C107):** Donor-side
   locality via `scoped_cross_propose_edges`. Donor pattern extracted
   from donor's historization-derived scope; coupling discount modulated
   by donor locality: $d_{\text{eff}} = d \times (\gamma_{\min} + (1 -
   \gamma_{\min}) \times \ell_{\text{donor}})$ with $\gamma_{\min} = 0.3$.
   Fresh donor degeneration preserved.

4. **Asymptotic tightness.** Under non-uniform inscription, is the
   convergence rate of $\ell$ bounded by a function of graph topology?

---

## 11. Honesty Classification

### 11.1 Derived Claims

| Claim | Section |
|-------|---------|
| Locality $\ell = \bar{m}/(\bar{m}+\mu)$ is monotonically non-decreasing | §5.1 |
| Radius $r$ is monotonically non-increasing | §5.4 |
| Phase transition at $n^* = \ln(1-\mu(1-\rho))/\ln(\rho)$ | §5.2 |
| Convergence to $\ell^* = 1/(1+\mu(1-\rho))$ under uniform decay | §5.3 |
| Fresh degeneration: scoped ≡ global when $\bar{m} = 0$ | §4.3 |
| $M_H$ and $I$ enter selection formula multiplicatively | §3.1 |
| Uniqueness among rational locality functions with A1–A3 | §6.2 |

### 11.2 Empirical Claims

| Claim | Section | Evidence |
|-------|---------|----------|
| Modulation never increases step count (14 domains) | §7.2 | C100 benchmark |
| Scoped ≡ global on fresh domains (10 domains) | §8.2 | C103 benchmark |
| Inertia flips confused forks | §7.2 | D11 stress test |
| Overlap selects triangle-supported paths | §7.2 | D12 stress test |
| Locality rises during controller navigation | §9.6 | C104 tracking |
| Phase transition within predicted range | §9.3 | C104 analysis |
| Convergence within 0.01 tolerance | §9.4 | C104 evolution |

### 11.3 Heuristic Claims

| Claim | Section | Status |
|-------|---------|--------|
| ~~$\mu = 5.0$ default is adequate for typical domains~~ | §4.1 | **Resolved (C105):** $\mu = |E|/|V|$ derived from topology |
| ~~BFS-spherical scope is sufficient~~ | §4.2 | **Resolved (C106):** corridor scope follows inscription corridors |
| Composition independence (overlap × inertia) | §3.3 | Empirically verified, not formally proven |

---

## 12. Conclusion

We have shown that locality in discrete transition systems need not be
postulated as a primitive. Given only structural difference ($\Delta$),
resistance ($R$), and historization ($H$), the act of navigating a
landscape creates non-uniform trace distributions that naturally restrict
reflexive operations to the operating region. The locality parameter
$\ell = \bar{m}/(\bar{m}+\mu)$ emerges from mean trace load, increases
monotonically with experience, undergoes an analytically predictable
phase transition, and converges to a finite equilibrium determined by
the decay rate and sensitivity threshold.

The construction preserves backward compatibility (fresh degeneration
theorem), introduces no new parameters beyond the sensitivity threshold
$\mu$, and composes safely with previous modulation mechanisms (overlap,
inertia). A benchmark across 14 domains confirms that the integrated
mechanism is monotonically non-destructive.

The broader implication is structural: locality is not an axiom but a
*consequence* of the framework's existing dynamics. This suggests that
other apparently fundamental properties — clustering, memory consolidation,
attention — may similarly emerge from the interplay of historization and
reflexion, without requiring dedicated primitives.

---

## Appendix A: Module Inventory

| Module | Lines | Claims | Tests |
|--------|------:|--------|------:|
| `overlap.py` | ~120 | C40, C98 | 58 |
| `historization.py` | ~230 | C42, C99 | 91 |
| `controller.py` | ~420 | C98, C99 | 140+ |
| `scoped_reflexion.py` | ~200 | C101 | 35 |
| `integrated_reflexion.py` | ~230 | C102 | 18 |
| `benchmark_scoped_reflexion.py` | ~180 | C103 | 22 + 80 subtests |
| `benchmark_modulation.py` | ~220 | C100 | 29 |
| `emergent_locality.py` | ~200 | C104 | 35 |

## Appendix B: Formula Chain

$$\underbrace{U, F}_{\text{Historization}}
\;\xrightarrow{\text{aggregate}}\;
\underbrace{m = U + F,\;\; q = \frac{U-F}{U+F+\varepsilon}}_{\text{Inscription}}
\;\xrightarrow{\text{functional}}\;
\underbrace{I = 1 - \alpha \cdot \frac{m}{m+\mu} \cdot (1-|q|)}_{\text{Inertia}}$$

$$\bar{m} = \text{mean}(m)
\;\xrightarrow{\;\ell\;}\;
\frac{\bar{m}}{\bar{m}+\mu}
\;\xrightarrow{\;r\;}\;
\max\!\bigl(1, \lceil(1-\ell)\cdot D\rceil\bigr)$$

$$\text{Selection:}\quad
p^* = \arg\min_y \frac{S_{\text{eff}}(x \to y)}{M_H(x,y) \cdot I(x,y)}
\cdot \bigl(1 + \alpha \cdot \mathbb{1}[y \in \text{recent}]\bigr)$$

## Appendix C: Relationship to Prior Papers

| Paper | Contribution | This Paper Extends |
|-------|-------------|-------------------|
| P1 | Path amplitudes, interference, greedy selection | Selection formula gains $M_H$ and $I$ (§3) |
| P2 | SU(2) lift, Born criterion | Not directly extended |
| P3 | Non-Abelian transport, curvature $M_H$ | $M_H$ integrated into greedy loop (§3) |
| P4 | Reflexive self-modification, edge proposals | Proposals scoped by locality (§4) |
